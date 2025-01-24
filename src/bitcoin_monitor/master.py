"""Master/control thread logic."""

import asyncio
import logging as log
from dataclasses import dataclass
from functools import cached_property

from .bitcoin import iptables, rpc, systemd, tracepoints
from .config import Config


@dataclass
class Master:
    """Master/control thread."""

    conf: Config

    @cached_property
    def log(self):
        """Custom logger."""
        return log.getLogger(self.__class__.__name__)

    async def prepare_sources(self) -> list:
        """Prepare data sources per configuration set via command-line arguments."""
        sources = []

        # RPC sources
        args = (self.conf.rpc_conf, self.conf.results_path)
        if self.conf.sources.rpc_getconnectioncount:
            sources.append(rpc.GetConnectionCount(*args))
        if self.conf.sources.rpc_getpeerinfo:
            sources.append(rpc.GetPeerInfo(*args))
        if self.conf.sources.rpc_gettxoutsetinfo:
            sources.append(rpc.GetTxoutSetInfo(*args))
        if self.conf.sources.rpc_getnodeaddresses:
            sources.append(rpc.GetNodeAddresses(*args))
        if self.conf.sources.rpc_getrawaddrman:
            sources.append(rpc.GetRawAddrman(*args))

        # tracepoint sources
        args = (self.conf.results_path,)
        if self.conf.sources.tracepoints_net:
            sources.append(tracepoints.Net(*args))

        # systemd sources
        args = (self.conf.results_path,)
        if self.conf.sources.systemd_ipaccounting:
            sources.append(systemd.IPAccounting(*args))

        # iptables sources
        args = (self.conf.results_path,)
        if self.conf.sources.iptables_p2ptraffic:
            sources.append(iptables.P2PTraffic(*args))

        log.info("Active sources: %s", [src.__class__.__name__ for src in sources])
        return sources

    async def run(self):
        """Entry point for the master/control thread."""

        while True:
            self.log.info("thread started")

            sources = await self.prepare_sources()
            await asyncio.gather(
                *[sensor.run() for sensor in sources],
            )
            self.log.info("sleeping for five")
            await asyncio.sleep(5)
            self.log.info("waking up")
