"""Master/control thread logic."""

import asyncio
import logging as log
from dataclasses import dataclass
from functools import cached_property

from .bitcoin import BitcoinRPC
from .config import Config


@dataclass
class Master:
    """Master/control thread."""

    conf: Config

    @cached_property
    def log(self):
        """Custom logger."""
        return log.getLogger(self.__class__.__name__)

    async def run(self):
        """Entry point for the master/control thread."""

        while True:
            self.log.info("thread started")

            bitcoin_rpc_api_thread = BitcoinRPC(self.conf.rpc_conf)

            await asyncio.gather(bitcoin_rpc_api_thread.run())
            self.log.info("sleeping for five")
            await asyncio.sleep(5)
            self.log.info("waking up")
