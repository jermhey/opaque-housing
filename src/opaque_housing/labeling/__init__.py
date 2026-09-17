"""Gold-set sampling. Interactive labeling I/O lives in the CLI."""

from opaque_housing.labeling.sample import (
    PRIVATE_GOLD_CLASSES,
    assign_splits,
    stratified_owner_sample,
)

__all__ = ["PRIVATE_GOLD_CLASSES", "assign_splits", "stratified_owner_sample"]
