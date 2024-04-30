"""Bitcoin Core RPC API implementation."""

from dataclasses import dataclass
from typing import ClassVar

from . import BitcoinRPCBase


@dataclass
class GetNodeAddresses(BitcoinRPCBase):
    """Class implementing the `getconnectioncount` Bitcoin Core RPC."""

    CALL_NAME: ClassVar[str] = "getnodeaddresses"
    CALL_ARGUMENTS: ClassVar[list] = [0]
    CSV_FIELDS: ClassVar[list[str]] = ["ipv4", "ipv6", "onion", "i2p", "cjdns"]
    FREQUENCY: ClassVar[int] = 60 * 10  # every ten minutes

    def format_results(self, timestamp, data) -> list[dict]:
        """
        Format RPC call result.

        The RPC call result is a scalar integer: Nothing to do.
        """

        result = {"timestamp": timestamp}
        for net in GetNodeAddresses.CSV_FIELDS:
            net_addrs = [1 for addr in data if addr["network"] == net]
            result[net] = len(net_addrs)

        return [result]
