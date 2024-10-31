import sys
import datetime
import asyncio
import logging

from utun.protocol import ProxyBackProtocol

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] - %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S%z",
    handlers=[
        logging.FileHandler(
            f"utun_backend_{datetime.datetime.now().strftime('%Y%m%d')}.log"
        ),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


async def main(
    host: str,
    port: int,
    origin_host: str,
    origin_port: int,
):
    loop = asyncio.get_running_loop()
    _ = await loop.create_server(
        lambda: ProxyBackProtocol(logger, origin_host, origin_port), host, port
    )
    while True:
        await asyncio.sleep(5)
