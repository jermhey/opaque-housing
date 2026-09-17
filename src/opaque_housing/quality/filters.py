"""Filter counts for the run manifest. Never drop rows without recording this."""

from dataclasses import dataclass


@dataclass(frozen=True)
class FilterCount:
    stage: str
    rule_id: str
    rows_in: int
    rows_out: int
