import asyncio
import argparse


def frontend():
    from utun.frontend import main

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="frontend host, default: 0.0.0.0",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=9999,
        help="frontend port, default: 9999",
    )
    parser.add_argument(
        "--backend-host",
        default="127.0.0.1",
        help="backend host, default: 127.0.0.1",
    )
    parser.add_argument(
        "--backend-port",
        type=int,
        default=8888,
        help="backend port, default: 8888",
    )
    args = parser.parse_args()
    asyncio.run(
        main(
            args.host,
            args.port,
            args.backend_host,
            args.backend_port,
        )
    )


def backend():
    from utun.backend import main

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="backend host, default: 0.0.0.0",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8888,
        help="backend port, default: 8888",
    )
    parser.add_argument(
        "--origin-host",
        default="127.0.0.1",
        help="origin host, default: 127.0.0.1",
    )
    parser.add_argument(
        "--origin-port",
        type=int,
        default=8211,
        help="origin port, default: 8211",
    )
    args = parser.parse_args()
    asyncio.run(
        main(
            args.host,
            args.port,
            args.origin_host,
            args.origin_port,
        )
    )
