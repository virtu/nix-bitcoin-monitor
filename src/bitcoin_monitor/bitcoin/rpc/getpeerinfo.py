"""Bitcoin Core RPC API implementation."""

from dataclasses import dataclass
from typing import ClassVar

from . import BitcoinRPCBase


@dataclass
class GetPeerInfo(BitcoinRPCBase):
    """Class implementing the `getpeerinfo` Bitcoin Core RPC."""

    CALL_NAME: ClassVar[str] = "getpeerinfo"
    CSV_FIELDS: ClassVar[list[str]] = [
        "addr",
        "network",
        "services",
        "relaytxes",
        "minping",
        "version",
        "subver",
        "inbound",
        "addr_relay_enabled",
        "addr_processed",
        "minfeefilter",
        "connection_type",
    ]

    def format_results(self, timestamp, data) -> list[dict]:
        """
        Format RPC call result.

        The RPC call result is a list of dictionaries: Iterate over list
        entries and extract relevant data from dict.
        """
        results = []
        for peer in data:
            result = {"timestamp": timestamp}
            result.update({key: peer[key] for key in self.CSV_FIELDS if key in peer})
            results.append(result)
        return results
