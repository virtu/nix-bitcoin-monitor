"""Bitcoin Core RPC API implementation."""

from dataclasses import dataclass
from typing import ClassVar

from . import BitcoinRPCBase


@dataclass
class GetTxoutSetInfo(BitcoinRPCBase):
    """Class implementing the `gettxoutsetinfo` Bitcoin Core RPC."""

    # 'gettxoutsetinfo' takes ~3m to execute on contabo, so schedule only daily
    FREQUENCY: ClassVar[int] = 24 * 60 * 60
    CALL_NAME: ClassVar[str] = "gettxoutsetinfo"
    CSV_FIELDS: ClassVar[list[str]] = [
        "height",
        "bestblock",
        "txouts",
        "bogosize",
        "hash_serialized_2",
        "total_amount",
        "transactions",
        "disk_size",
    ]

    def format_results(self, timestamp, data) -> list[dict]:
        """
        Format RPC call result.

        The RPC call result is a scalar integer: Nothing to do.
        """

        result = {"timestamp": timestamp}
        result.update({key: data[key] for key in self.CSV_FIELDS if key in data})
        return [result]
