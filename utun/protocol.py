from enum import Enum
import time
import asyncio
import ipaddress
import logging
from typing import Optional, Union


class MessageType(Enum):
    DATA_TRANSFER = 0
    CONNECTION_OPEN = 1
    CONNECTION_CLOSE = 2


class Message:
    def __init__(
        self,
        message_type: MessageType,
        orig_addr: Union[str, bytes],
        orig_port: int,
        data: bytes,
    ):
        self.type = message_type
        self.orig_addr = ipaddress.ip_address(orig_addr)
        self.orig_port = orig_port
        if len(data) > 65507:
            raise Exception(f"Too long data length: {len(data)} > 65507")
        self.data = data

    @staticmethod
    def from_bytes(message_data: bytes):
        message_type = MessageType(int.from_bytes(message_data[:1], byteorder="big"))
        message_data = message_data[1:]
        orig_addr_type = int.from_bytes(message_data[:1], byteorder="big")
        message_data = message_data[1:]
        if orig_addr_type == 4:
            addr_len = 4
        elif orig_addr_type == 6:
            addr_len = 16
        else:
            raise Exception("Invalid ip version")
        orig_addr_bytes = message_data[:addr_len]
        message_data = message_data[addr_len:]
        orig_port = int.from_bytes(message_data[:2], byteorder="big")
        data = message_data[2:]
        return Message(message_type, orig_addr_bytes, orig_port, data)

    def to_bytes(self):
        message_type_bytes = self.type.value.to_bytes(1, byteorder="big")
        orig_addr_type_bytes = self.orig_addr.version.to_bytes(1, byteorder="big")
        orig_addr_bytes = self.orig_addr.packed
        orig_port_bytes = self.orig_port.to_bytes(2, byteorder="big")
        return (
            message_type_bytes
            + orig_addr_type_bytes
            + orig_addr_bytes
            + orig_port_bytes
            + self.data
        )


class ProxyFrontProtocol(asyncio.Protocol):
    def __init__(
        self,
        logger: logging.Logger,
        front_protocol: "FrontProtocol",
    ):
        self.logger = logger
        self.front_protocol = front_protocol

    def connection_made(self, transport):
        self.buffer = b""
        self.transport = transport
        self.logger.info(f"Connected to backend {transport.get_extra_info('peername')}")

    def eof_received(self):
        self.transport.close()
        self.logger.info(
            f"Backend {self.transport.get_extra_info('peername')} has disconnected"
        )

    def connection_lost(self, exc):
        if not exc is None:
            self.logger.warning(
                f"Connection to backend {self.transport.get_extra_info('peername')} has been lost: {exc}"
            )

    def data_received(self, raw_data):
        self.buffer += raw_data
        while len(self.buffer) > 2:
            message_data_len = int.from_bytes(self.buffer[:2], byteorder="big")
            if len(self.buffer) >= message_data_len + 2:
                message_data = self.buffer[2 : message_data_len + 2]
                self.buffer = self.buffer[message_data_len + 2 :]
                message = Message.from_bytes(message_data)
                if message.type is MessageType.CONNECTION_OPEN:
                    self.logger.info(
                        f"Client {(str(message.orig_addr), message.orig_port)} has connected"
                    )
                elif message.type is MessageType.CONNECTION_CLOSE:
                    self.logger.info(
                        f"Client {(str(message.orig_addr), message.orig_port)} has disconnected"
                    )
                else:
                    self.front_protocol.sendto(
                        message.data, (str(message.orig_addr), message.orig_port)
                    )

    def write(self, data: bytes):
        if not self.transport.is_closing():
            self.transport.write(len(data).to_bytes(2, "big") + data)

    def is_closing(self):
        return self.transport.is_closing()


class ProxyBackProtocol(asyncio.Protocol):
    def __init__(
        self,
        logger: logging.Logger,
        origin_host: str,
        origin_port: int,
    ):
        self.logger = logger
        self.origin_host = origin_host
        self.origin_port = origin_port
        self.back_protocols: dict[tuple[str, int], BackProtocol] = {}
        self.lock = asyncio.Lock()

    def connection_made(self, transport):
        self.buffer = b""
        self.transport = transport
        self.logger.info(
            f"Frontend {transport.get_extra_info('peername')} has connected"
        )
        self.task = asyncio.create_task(self.cleanup_back_protocols())

    def eof_received(self):
        self.transport.close()
        self.logger.info(
            f"Frontend {self.transport.get_extra_info('peername')} has disconnected"
        )

    def connection_lost(self, exc):
        if not exc is None:
            self.logger.warning(
                f"Connection from frontend {self.transport.get_extra_info('peername')} has been lost: {exc}"
            )

    def data_received(self, raw_data):
        self.buffer += raw_data
        while len(self.buffer) > 2:
            message_data_len = int.from_bytes(self.buffer[:2], byteorder="big")
            if len(self.buffer) >= message_data_len + 2:
                message_data = self.buffer[2 : message_data_len + 2]
                self.buffer = self.buffer[message_data_len + 2 :]
                message = Message.from_bytes(message_data)
                asyncio.ensure_future(self.forward_data(message))

    async def forward_data(self, message: Message):
        back_protocol = self.back_protocols.get(
            (str(message.orig_addr), message.orig_port)
        )
        if back_protocol is None or back_protocol.is_closing():
            async with self.lock:
                if back_protocol is None or back_protocol.is_closing():
                    self.logger.info(
                        f"Client {(str(message.orig_addr), message.orig_port)}"
                        f" via frontend {self.transport.get_extra_info('peername')} has connected"
                    )
                    # Notify frontend of client connection
                    self.write(
                        Message(
                            MessageType.CONNECTION_OPEN,
                            message.orig_addr.packed,
                            message.orig_port,
                            b"",
                        ).to_bytes()
                    )
                    loop = asyncio.get_running_loop()
                    _, back_protocol = await loop.create_datagram_endpoint(
                        lambda: BackProtocol(
                            self.logger, self, str(message.orig_addr), message.orig_port
                        ),
                        remote_addr=(self.origin_host, self.origin_port),
                    )
            self.back_protocols[(str(message.orig_addr), message.orig_port)] = (
                back_protocol
            )
        back_protocol.sendto(message.data)

    def write(self, data: bytes):
        if not self.transport.is_closing():
            self.transport.write(len(data).to_bytes(2, "big") + data)

    async def cleanup_back_protocols(self):
        while True:
            await asyncio.sleep(5)
            if self.transport.is_closing():
                return
            else:
                for addr, back_protocol in list(self.back_protocols.items()):
                    # Close unused ports
                    if time.time() - back_protocol.last_accessed > 5:
                        self.back_protocols.pop(addr)
                        if not back_protocol.is_closing():
                            back_protocol.close()
                        self.logger.info(
                            f"Client {addr} via frontend {self.transport.get_extra_info('peername')}"
                            f" has disconnected"
                        )
                        # Notify frontend of client disconnection
                        self.write(
                            Message(
                                MessageType.CONNECTION_CLOSE,
                                addr[0],
                                addr[1],
                                b"",
                            ).to_bytes()
                        )


class BackProtocol(asyncio.DatagramProtocol):
    def __init__(
        self,
        logger: logging.Logger,
        proxy_protocol: ProxyBackProtocol,
        orig_addr: str,
        orig_port: int,
    ):
        self.logger = logger
        self.proxy_protocol = proxy_protocol
        self.orig_addr = orig_addr
        self.orig_port = orig_port

    def connection_made(self, transport):
        self.transport = transport
        self.last_accessed = time.time()

    def error_received(self, exc):
        self.logger.warning(exc)

    def datagram_received(self, data, _):
        message = Message(
            MessageType.DATA_TRANSFER, self.orig_addr, self.orig_port, data
        )
        self.proxy_protocol.write(message.to_bytes())
        self.last_accessed = time.time()

    def sendto(self, data):
        self.transport.sendto(data)
        self.last_accessed = time.time()

    def close(self):
        self.transport.close()

    def is_closing(self):
        return self.transport.is_closing()


class FrontProtocol(asyncio.DatagramProtocol):
    def __init__(self, logger: logging.Logger, backend_host: str, backend_port: int):
        self.logger = logger
        self.backend_host = backend_host
        self.backend_port = backend_port
        self.proxy_protocol: Optional[ProxyFrontProtocol] = None
        self.error_count = 0
        self.lock = asyncio.Lock()

    def connection_made(self, transport):
        self.transport = transport

    def error_received(self, exc):
        self.logger.warning(exc)

    def datagram_received(self, data, addr):
        message = Message(MessageType.DATA_TRANSFER, addr[0], addr[1], data)
        asyncio.ensure_future(self.forward_data(message))

    async def forward_data(self, message: Message):
        if self.proxy_protocol is None or self.proxy_protocol.is_closing():
            async with self.lock:
                if self.proxy_protocol is None or self.proxy_protocol.is_closing():
                    try:
                        loop = asyncio.get_running_loop()
                        _, proxy_protocol = await loop.create_connection(
                            lambda: ProxyFrontProtocol(
                                self.logger, front_protocol=self
                            ),
                            self.backend_host,
                            self.backend_port,
                        )
                        self.proxy_protocol = proxy_protocol
                        self.error_count = 0
                    except ConnectionRefusedError as e:
                        self.error_count += 1
                        if self.error_count <= 10 or self.error_count % 10 == 0:
                            self.logger.warning(
                                f"Connection to backend {(self.backend_host,self.backend_port)}"
                                f" refused (count: {self.error_count}): {e}"
                            )
                        return
        self.proxy_protocol.write(message.to_bytes())

    def sendto(self, data, addr):
        self.transport.sendto(data, addr)
