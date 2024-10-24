"""Log ip accounting data for bitcoind."""

import asyncio
import csv
import datetime
import logging as log
import subprocess
import time
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import ClassVar


# TODO: This is taken from ../rpc/base.py; at some point, extract this
# functionality to avoid duplication
def human_readable_size(size_bytes: int) -> str:
    """Convert size in bytes to a human-readable string."""
    if size_bytes < 1000:
        return f"{size_bytes}B"
    if (size_kbytes := size_bytes / 1000) < 1000:
        return f"{size_kbytes:.1f}kB"
    return f"{(size_kbytes/1000):.1f}MB"


# TODO: This is taken from ../rpc/base.py; at some point, extract this
# functionality to avoid duplication
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
class IPAccounting:
    """
    Class implementing the collection of IP accounting statistics for the
    bitcoind service via systemd.
    """

    results_path: Path
    FREQUENCY: ClassVar[int] = 5  # 5 seconds
    CALL_NAME: ClassVar[str] = "ip_accounting"
    CSV_FIELDS: ClassVar[list[str]] = [
        "IPIngressPackets",
        "IPEgressPackets",
        "IPIngressBytes",
        "IPEgressBytes",
    ]

    # TODO: This is taken from ../rpc/base.py; at some point, extract this
    # functionality to avoid duplication
    @cached_property
    def log(self):
        """Custom logger."""
        return log.getLogger(self.__class__.__name__)

    # TODO: This is taken from ../rpc/base.py; at some point, extract this
    # functionality to avoid duplication
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
        """Code to fetch data from systemd."""
        self.log.info("systemd.IPAccounting:run() started")

        tz = datetime.timezone.utc
        while True:
            call_time = datetime.datetime.now(tz).strftime("%Y-%m-%dT%H:%M:%SZ")
            try:
                call_result = await self.systemd_call()
                data = self.format_results(call_time, call_result)
                if not data:
                    self.log.warning("no data returned by format_results")
                    break
                self.write_result(data)
            except ConnectionError as e:
                self.log.error(e)
            await self.reschedule()

    async def systemd_call(self, service_name="bitcoind.service") -> dict:
        try:
            result = subprocess.run(
                [
                    "systemctl",
                    "show",
                    service_name,
                    "-p",
                    "IPIngressBytes",
                    "-p",
                    "IPIngressPackets",
                    "-p",
                    "IPEgressBytes",
                    "-p",
                    "IPEgressPackets",
                    "-p",
                    "IPAccounting",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            print(f"Error: {e.stderr.strip()}")
            return {}

        data = {}
        for line in result.stdout.strip().split("\n"):
            if "=" in line:
                key, value = line.strip().split("=", 1)
                data[key] = value

        if data.get("IPAccounting", "no") != "yes":
            print(f"IP Accounting is not enabled for '{service_name}'.")
            return {}

        return data

    def format_results(self, timestamp, data) -> list[dict]:
        """
        Format call results: just add timestamp.
        """
        return [
            {"timestamp": timestamp}
            | {k: v for k, v in data.items() if k in self.CSV_FIELDS}
        ]

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
