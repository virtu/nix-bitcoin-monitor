"""Master/control thread logic."""

import asyncio
import logging as log
from dataclasses import dataclass
from functools import cached_property

from .bitcoin.rpc import GetConnectionCount, GetPeerInfo
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

            get_connection_count = GetConnectionCount(self.conf.rpc_conf)
            get_peer_info = GetPeerInfo(self.conf.rpc_conf)

            await asyncio.gather(get_connection_count.run(), get_peer_info.run())
            self.log.info("sleeping for five")
            await asyncio.sleep(5)
            self.log.info("waking up")
