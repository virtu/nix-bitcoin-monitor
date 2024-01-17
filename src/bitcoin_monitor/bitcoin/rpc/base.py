"""Base class for Bitcoin RPC API calls."""

import asyncio
import csv
import datetime
import logging as log
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import ClassVar

import aiohttp

from ...config import RPCConfig


@dataclass
class BitcoinRPCBase:
    """Base class containing shared functionality related to Bitcoin Core's RPC API."""

    conf: RPCConfig
    CALL_NAME: ClassVar[str] = "dummy"
    FREQUENCY: ClassVar[int] = 60
    CSV_FIELDS: ClassVar[list[str]] = ["dummy"]

    @cached_property
    def log(self):
        """Custom logger."""
        return log.getLogger(self.__class__.__name__)

    async def run(self):
        """Code to fetch data from Bitcoin API."""
        self.log.info("BitcoinRPCBase:run() for call %s started", self.CALL_NAME)

        while True:
            call_time = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
            call_result = await self.rpc_call()
            data = self.format_results(call_time, call_result)
            self.write_result(data)

            self.log.info("Sleeping for %d seconds", self.FREQUENCY)
            await asyncio.sleep(self.FREQUENCY)
            self.log.info("Waking up")

    async def rpc_call(self):
        """Open RPC connection, perform RPC calls, and write results."""

        rpc_url = f"http://{self.conf.user}:{self.conf.password}@{self.conf.host}:{self.conf.port}/"
        rpc_data = {
            "method": self.CALL_NAME,
            "params": [],
            "jsonrpc": "2.0",
            "id": 1,
        }
        self.log.info("Initiating %s RPC call", self.CALL_NAME)
        async with aiohttp.ClientSession() as session:
            async with session.post(rpc_url, json=rpc_data) as response:
                if response.status == 200:
                    result = await response.json()
                else:
                    self.log.error(
                        "RPC response: status=%s, details=%s",
                        response.status,
                        await response.text(),
                    )
                    return "error"

        self.log.info("Reponse: %s bytes", response.headers["Content-Length"])
        return result["result"]

    def format_results(self, timestamp, data):
        """Format results obtained via API call. Since this is call-specific,
        the appropriate code resides in subclasses."""
        raise NotImplementedError("Needs to be overwritten in subclass!")

    def write_result(self, data):
        """Write CSV call results to CSV file.

        :param list data: a list of dicts containing data to be written
        """

        file = Path(f"results-{self.CALL_NAME}.csv")
        file_exists = file.exists()
        with open(file, "a", newline="", encoding="UTF-8") as f:
            csv_writer = csv.DictWriter(f, fieldnames=["timestamp"] + self.CSV_FIELDS)
            if not file_exists:
                csv_writer.writeheader()
            csv_writer.writerows(data)
