import sys
import datetime
import asyncio
import logging

from utun.protocol import FrontProtocol

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] - %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S%z",
    handlers=[
        logging.FileHandler(
            f"utun_frontend_{datetime.datetime.now().strftime('%Y%m%d')}.log"
        ),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


async def main(host: str, port: int, backend_host: str, backend_port: int):
    loop = asyncio.get_running_loop()
    _ = await loop.create_datagram_endpoint(
        lambda: FrontProtocol(logger, backend_host, backend_port),
        local_addr=(host, port),
    )
    while True:
        await asyncio.sleep(5)
