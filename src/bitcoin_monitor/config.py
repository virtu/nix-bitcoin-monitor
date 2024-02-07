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
            password=cls.get_password(args.rpc_password, args.rpc_password_file),
        )

    @staticmethod
    def get_password(password: str, password_file: Path):
        """Get password directly from command-line argument or from file."""

        if (password and password_file) or not (password or password_file):
            raise ValueError(
                "Exactly one of --rpc-password and --rpc-password-file must be used"
            )

        if password:
            return password

        if not password_file.exists():
            raise FileNotFoundError(f"Password file {password_file} does not exist")

        print(f"Using RPC password from {password_file}.")
        with open(password_file, "r", encoding="utf-8") as f:
            password = f.readline().strip("\n")

        return password

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

        # ensure result_path exists and is not a file
        args.result_path.mkdir(parents=True, exist_ok=True)

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
        required=True,
        help="Bitcoin Core RPC user",
    )

    parser.add_argument(
        "--rpc-password",
        type=str,
        help="Bitcoin Core RPC password",
    )

    parser.add_argument(
        "--rpc-password-file",
        type=Path,
        default=None,
        help="File containing Bitcoin Core RPC password",
    )

    args = parser.parse_args()
    return args
