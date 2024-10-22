"""Master/control thread logic."""

import asyncio
import logging as log
from dataclasses import dataclass
from functools import cached_property

from .bitcoin import rpc, systemd
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

            args = (self.conf.rpc_conf, self.conf.results_path)
            get_connection_count = rpc.GetConnectionCount(*args)
            get_peer_info = rpc.GetPeerInfo(*args)
            get_txoutset_info = rpc.GetTxoutSetInfo(*args)
            get_node_addresses = rpc.GetNodeAddresses(*args)
            get_raw_addrman = rpc.GetRawAddrman(*args)

            args = (self.conf.results_path,)
            ip_accounting = systemd.IPAccounting(*args)

            await asyncio.gather(
                get_connection_count.run(),
                get_peer_info.run(),
                get_txoutset_info.run(),
                get_node_addresses.run(),
                get_raw_addrman.run(),
                ip_accounting.run(),
            )
            self.log.info("sleeping for five")
            await asyncio.sleep(5)
            self.log.info("waking up")
