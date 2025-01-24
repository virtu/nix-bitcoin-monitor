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
class SourcesConfig:
    """Configuration settings for data sources."""

    rpc_getconnectioncount: bool
    rpc_getpeerinfo: bool
    rpc_gettxoutsetinfo: bool
    rpc_getnodeaddresses: bool
    rpc_getrawaddrman: bool
    systemd_ipaccounting: bool
    iptables_p2ptraffic: bool
    tracepoints_net: bool

    @classmethod
    def parse(cls, args):
        """Create class instance from command-line arguments."""
        return cls(
            rpc_getconnectioncount=args.record_rpc_getconnectioncount,
            rpc_getpeerinfo=args.record_rpc_getpeerinfo,
            rpc_gettxoutsetinfo=args.record_rpc_gettxoutsetinfo,
            rpc_getnodeaddresses=args.record_rpc_getnodeaddresses,
            rpc_getrawaddrman=args.record_rpc_getrawaddrman,
            systemd_ipaccounting=args.record_systemd_ip_accounting,
            iptables_p2ptraffic=args.record_iptables_p2p_traffic,
            tracepoints_net=args.record_tracepoints_net,
        )


@dataclass
class Config:
    """Configuration settings."""

    version: str
    log_level: str
    results_path: Path
    rpc_conf: RPCConfig
    sources: SourcesConfig

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
            sources=SourcesConfig.parse(args),
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

    parser.add_argument(
        "--record-rpc-getconnectioncount",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Measure number of connections (getconnectioncount via RPC)",
    )

    parser.add_argument(
        "--record-rpc-getpeerinfo",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Record peer data (getpeerinfo via RPC)",
    )

    parser.add_argument(
        "--record-rpc-gettxoutsetinfo",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Record UTXO set data (gettxoutsetinfo via RPC)",
    )

    parser.add_argument(
        "--record-rpc-getnodeaddresses",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Record known peers addresses (getnodeaddresses via RPC)",
    )

    parser.add_argument(
        "--record-rpc-getrawaddrman",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Record raw addrman data (getrawaddrman via RPC)",
    )

    parser.add_argument(
        "--record-systemd-ip-accounting",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Record IP accounting statistics (via systemd)",
    )

    parser.add_argument(
        "--record-iptables-p2p-traffic",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Record Bitcoin Core P2P traffic (via iptables)",
    )

    parser.add_argument(
        "--record-tracepoints-net",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Record P2P network traffic (via tracepoints)",
    )

    args = parser.parse_args()
    return args
