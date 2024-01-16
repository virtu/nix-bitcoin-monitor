"""This module contains the configuration options."""

import argparse
import importlib.metadata
from dataclasses import asdict, dataclass
from pathlib import Path

__version__ = importlib.metadata.version(__package__ or __name__)


@dataclass
class Config:
    """Configuration settings."""

    version: str
    log_level: str
    results_path: Path

    @classmethod
    def parse(cls, args):
        """Create class instance from arguments."""
        return cls(
            version=__version__,
            log_level=args.log_level.upper(),
            results_path=Path(args.result_path),
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

    args = parser.parse_args()
    return args
