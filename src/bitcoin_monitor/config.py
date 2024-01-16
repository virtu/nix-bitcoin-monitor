"""This module contains the configuration options."""

import argparse
import importlib.metadata
from dataclasses import asdict, dataclass
from pathlib import Path

__version__ = importlib.metadata.version(__package__ or __name__)


@dataclass
class RPCConfig:
    """Configuration settings for Bitcoin Core's RPC interface."""

    host: str
    port: int
    user: str
    password: str

    @classmethod
    def parse(cls, args):
        """Create class instance from command-line arguments."""
        return cls(
            host=args.rpc_host,
            port=args.rpc_port,
            user=args.rpc_user,
            password=args.rpc_password,
        )

    def __repr__(self):
        """Return redacted string."""
        return f"RPCConfig(host={self.host}, port={self.port}, user={self.user}, password=<redacted>)"


@dataclass
class Config:
    """Configuration settings."""

    version: str
    log_level: str
    results_path: Path
    rpc_conf: RPCConfig

    @classmethod
    def parse(cls, args):
        """Create class instance from command-line arguments."""
        return cls(
            version=__version__,
            log_level=args.log_level.upper(),
            results_path=Path(args.result_path),
            rpc_conf=RPCConfig.parse(args),
        )

    def to_dict(self):
        """Convert to dictionary."""
        return asdict(self)


def parse_args():
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        help="Logging verbosity",
    )

    parser.add_argument(
        "--result-path",
        type=Path,
        default="results",
        help="Directory for results",
    )

    parser.add_argument(
        "--rpc-host",
        type=str,
        default="127.0.0.1",
        help="Bitcoin Core RPC host",
    )

    parser.add_argument(
        "--rpc-port",
        type=int,
        default=8332,
        help="Bitcoin Core RPC port",
    )

    parser.add_argument(
        "--rpc-user",
        type=str,
        default="bitcoin",
        help="Bitcoin Core RPC user",
    )

    parser.add_argument(
        "--rpc-password",
        type=str,
        default="secretpassword",
        help="Bitcoin Core RPC password",
    )

    args = parser.parse_args()
    return args
