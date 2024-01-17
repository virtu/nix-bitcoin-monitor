#!/usr/bin/env python3

"""Command-line interface for the Bitcoin Core monitoring framework."""

import asyncio
import logging as log
import time

from .config import Config, parse_args
from .master import Master


def init_logger(log_level: str):
    """Initilize the logger. Use UTC-based timestamps and log to file if requested."""

    log.basicConfig(
        format="%(asctime)s | %(levelname)-8s | %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%SZ",
        level=log_level,
    )
    log.Formatter.converter = time.gmtime


def init():
    """
    Handle initialization.

    First, parse command-line arguments and create Config object, then
    initialize the logger.
    """

    args = parse_args()
    conf = Config.parse(args)
    init_logger(conf.log_level)
    log.info("Run config: %s", conf)
    return conf


def main():
    """Execution entry point.

    Initialize, execute crawler, and store results.
    """

    conf = init()
    master = Master(conf)
    asyncio.run(master.run())


if __name__ == "__main__":
    main()
