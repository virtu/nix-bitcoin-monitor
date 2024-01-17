"""Bitcoin Core RPC API implementation."""

from dataclasses import dataclass
from typing import ClassVar

from . import BitcoinRPCBase


@dataclass
class GetConnectionCount(BitcoinRPCBase):
    """Class implementing the `getconnectioncount` Bitcoin Core RPC."""

    CALL_NAME: ClassVar[str] = "getconnectioncount"
    CSV_FIELDS: ClassVar[list[str]] = ["connectioncount"]

    def format_results(self, timestamp, data):
        """
        Format RPC call result.

        The RPC call result is a scalar integer: Nothing to do.
        """
        return [{"timestamp": timestamp, "connectioncount": data}]
