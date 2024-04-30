"""Base class for Bitcoin RPC API calls."""

import asyncio
import csv
import datetime
import logging as log
import time
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import ClassVar

import aiohttp

from ...config import RPCConfig


def human_readable_size(size_bytes: int) -> str:
    """Convert size in bytes to a human-readable string."""
    if size_bytes < 1000:
        return f"{size_bytes}B"
    if (size_kbytes := size_bytes / 1000) < 1000:
        return f"{size_kbytes:.1f}kB"
    return f"{(size_kbytes/1000):.1f}MB"


def human_readable_time(sec: float) -> str:
    """Convert seconds to a human-readable string."""
    if (msec := int(sec * 1000)) < 1000:
        return f"{msec}ms"
    if sec < 60:
        return f"{sec:.1f}s"
    if (min_ := sec / 60) < 60:
        return f"{min_:.1f}m"
    return f"{(min_/60):.1f}h"


@dataclass
class BitcoinRPCBase:
    """Base class containing shared functionality related to Bitcoin Core's RPC API."""

    conf: RPCConfig
    results_path: Path
    CALL_NAME: ClassVar[str] = "dummy"
    CALL_ARGUMENTS: ClassVar[list] = []
    FREQUENCY: ClassVar[int] = 60 * 60  # default polling frequency [s]
    CSV_FIELDS: ClassVar[list[str]] = ["dummy"]

    @cached_property
    def log(self):
        """Custom logger."""
        return log.getLogger(self.__class__.__name__)

    async def reschedule(self):
        """Reschedule the task by sleeping until the next multiple of FREQUENCY."""
        now = time.time() + 1  # avoid race condition where now % FREQUENCY == 0
        last_scheduled = now - now % self.FREQUENCY
        next_scheduled = last_scheduled + self.FREQUENCY
        wake_time = datetime.datetime.utcfromtimestamp(next_scheduled)
        sleep_time = next_scheduled - now
        self.log.info(
            "Scheduling next run at %s (sleeping for %s)",
            wake_time.isoformat() + "Z",
            human_readable_time(sleep_time),
        )
        await asyncio.sleep(sleep_time)
        self.log.info("Waking up")

    async def run(self):
        """Code to fetch data from Bitcoin API."""
        self.log.info(
            "BitcoinRPCBase:run() started for call=%s, arguments=%s",
            self.CALL_NAME,
            ",".join(str(arg) for arg in self.CALL_ARGUMENTS)
            if self.CALL_ARGUMENTS
            else "None",
        )

        while True:
            call_time = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
            try:
                call_result = await self.rpc_call()
                data = self.format_results(call_time, call_result)
                self.write_result(data)
            except ConnectionError as e:
                self.log.error(e)
            await self.reschedule()

    async def rpc_call(self):
        """Open RPC connection, perform RPC calls, and write results."""

        rpc_url = f"http://{self.conf.user}:{self.conf.password}@{self.conf.host}:{self.conf.port}/"
        rpc_data = {
            "method": self.CALL_NAME,
            "params": self.CALL_ARGUMENTS,
            "jsonrpc": "2.0",
            "id": 1,
        }
        self.log.info("Initiating %s RPC call", self.CALL_NAME)
        time_start = time.time()
        async with aiohttp.ClientSession() as session:
            async with session.post(rpc_url, json=rpc_data) as response:
                if response.status == 200:
                    result = await response.json()
                else:
                    raise ConnectionError(
                        f"unexpected RPC response: status={response.status}, reason={response.reason}"
                    )
        call_duration = time.time() - time_start
        self.log.info(
            "API response: size=%s, call_duration=%s",
            human_readable_size(int(response.headers["Content-Length"])),
            human_readable_time(call_duration),
        )
        return result["result"]

    def format_results(self, timestamp, data) -> list[dict]:
        """Format results obtained via API call. Since this is call-specific,
        the appropriate code resides in subclasses."""
        raise NotImplementedError("Needs to be overwritten in subclass!")

    def write_result(self, data):
        """Write CSV call results to CSV file.

        :param list data: a list of dicts containing data to be written
        """

        file = Path(f"{self.results_path}/{self.CALL_NAME}.csv")
        file_exists = file.exists()
        with open(file, "a", newline="", encoding="UTF-8") as f:
            csv_writer = csv.DictWriter(f, fieldnames=["timestamp"] + self.CSV_FIELDS)
            if not file_exists:
                csv_writer.writeheader()
            csv_writer.writerows(data)
