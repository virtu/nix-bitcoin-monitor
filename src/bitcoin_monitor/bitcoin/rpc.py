"""Bitcoin Core RPC API implementation."""

import asyncio
import logging as log
from dataclasses import dataclass
from functools import cached_property

from bitcoinrpc import BitcoinRPC as BitcoinRPC_

from ..config import RPCConfig

INTERVAL = 60


@dataclass
class BitcoinRPC:
    """Class implementing Bitcoin Core RPC API."""

    conf: RPCConfig

    @cached_property
    def log(self):
        """Custom logger."""
        return log.getLogger(self.__class__.__name__)

    async def run(self):
        """Code to fetch data from Bitcoin  API."""
        self.log.info("thread started")

        while True:
            self.log.info("running getconnectioncount...")

            rpc_url = f"http://{self.conf.host}:{self.conf.port}"
            rpc_credentials = (self.conf.user, self.conf.password)
            rpc = BitcoinRPC_.from_config(rpc_url, rpc_credentials)

            connectioncount = await rpc.getconnectioncount()
            await rpc.aclose()
            self.log.info("getconnectioncount result: %d", connectioncount)

            self.log.info("sleeping for %d seconds", INTERVAL)
            await asyncio.sleep(INTERVAL)
            self.log.info("waking up")
