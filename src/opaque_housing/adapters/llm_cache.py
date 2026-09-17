"""DuckDB cache for LLM classifications. I/O only."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import duckdb

from opaque_housing.classify.llm import PROMPT_VERSION, LlmLabel
from opaque_housing.schema import OwnerClass

_DDL = """
CREATE TABLE IF NOT EXISTS llm_classifications (
    owner_key VARCHAR,
    name_normalized VARCHAR,
    prompt_version VARCHAR,
    model_id VARCHAR,
    owner_class VARCHAR,
    rationale VARCHAR,
    input_tokens INTEGER,
    output_tokens INTEGER,
    created_at VARCHAR,
    PRIMARY KEY (owner_key, prompt_version, model_id)
)
"""


class LlmCache:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._con = duckdb.connect(str(path))
        self._con.execute(_DDL)

    def close(self) -> None:
        self._con.close()

    def get(
        self, owner_key: str, model_id: str, prompt_version: str = PROMPT_VERSION
    ) -> LlmLabel | None:
        row = self._con.execute(
            """
            SELECT owner_class, rationale, model_id, prompt_version, input_tokens, output_tokens
            FROM llm_classifications
            WHERE owner_key = ? AND prompt_version = ? AND model_id = ?
            """,
            [owner_key, prompt_version, model_id],
        ).fetchone()
        if row is None:
            return None
        return LlmLabel(
            owner_class=OwnerClass(row[0]),
            rationale=row[1] or "",
            model_id=row[2],
            prompt_version=row[3],
            input_tokens=int(row[4] or 0),
            output_tokens=int(row[5] or 0),
        )

    def put(self, owner_key: str, name_normalized: str, label: LlmLabel) -> None:
        self._con.execute(
            """
            INSERT OR REPLACE INTO llm_classifications
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                owner_key,
                name_normalized,
                label.prompt_version,
                label.model_id,
                label.owner_class.value,
                label.rationale,
                label.input_tokens,
                label.output_tokens,
                datetime.now(tz=UTC).isoformat(),
            ],
        )
