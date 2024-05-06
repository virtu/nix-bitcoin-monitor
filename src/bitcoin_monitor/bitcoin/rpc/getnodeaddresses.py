"""Bitcoin Core RPC API implementation."""

import csv
import logging as log
import lzma
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from . import BitcoinRPCBase


@dataclass
class GetNodeAddresses(BitcoinRPCBase):
    """Class implementing the `getconnectioncount` Bitcoin Core RPC."""

    CALL_NAME: ClassVar[str] = "getnodeaddresses"
    CALL_ARGUMENTS: ClassVar[list] = [0]
    CSV_FIELDS: ClassVar[list[str]] = ["time", "services", "address", "port", "network"]
    FREQUENCY: ClassVar[int] = 60 * 60  # every hour

    def format_results(self, timestamp, data) -> list[dict]:
        """
        Format RPC call result.

        The RPC call result is a list of detailed address data entries.
        """

        results = []
        for addr in data:
            result = {"timestamp": timestamp}
            result.update({key: addr[key] for key in self.CSV_FIELDS if key in addr})
            results.append(result)

        return results

    def write_result(self, data):
        """Custom write result method."""

        timestamp_str = data[0]["timestamp"]
        file = Path(f"{self.results_path}/{self.CALL_NAME}/{timestamp_str}.csv.xz")

        if file.exists():
            log.error("output file %s already exists. Skipping.", file)
            return

        file.parent.mkdir(parents=True, exist_ok=True)
        with lzma.open(file, "wt") as f:
            csv_writer = csv.DictWriter(f, fieldnames=["timestamp"] + self.CSV_FIELDS)
            csv_writer.writeheader()
            csv_writer.writerows(data)
