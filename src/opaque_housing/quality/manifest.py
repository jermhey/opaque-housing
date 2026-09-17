"""Run-manifest records. Serialization is pure; writing files is the CLI's job."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from opaque_housing.quality.filters import FilterCount


@dataclass
class RunManifest:
    metro_id: str
    started_at: str
    finished_at: str | None
    source_paths: dict[str, str] = field(default_factory=dict)
    source_versions: dict[str, str] = field(default_factory=dict)
    rules_version: str = ""
    filter_counts: list[FilterCount] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["filter_counts"] = [asdict(item) for item in self.filter_counts]
        return payload
