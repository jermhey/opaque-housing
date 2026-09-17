"""Metro adapter protocol. A new metro is a new adapter, not a new pipeline."""

from pathlib import Path
from typing import Protocol, runtime_checkable

import polars as pl


@runtime_checkable
class MetroAdapter(Protocol):
    """Read metro-specific extracts into canonical tables.

    Network and file I/O live here and in the CLI. Classification and metrics
    stay pure.
    """

    metro_id: str

    def load_parcels_snapshot(self, source_path: Path) -> pl.DataFrame:
        """Return a DataFrame whose columns match ``ParcelSnapshot``."""
        ...
