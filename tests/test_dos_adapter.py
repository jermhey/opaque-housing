from pathlib import Path

import polars as pl

from opaque_housing.adapters.nyc.nys_dos import NycDosAdapter, chairman_is_person
from opaque_housing.normalize.names import owner_key, primary_owner_name

DOS = Path("tests/fixtures/nyc/nys_dos.csv")


def test_dos_normalizes_and_matches_owner_keys() -> None:
    adapter = NycDosAdapter()
    entities = adapter.load_entities(DOS)
    assert entities.height == 4
    holdings = owner_key(primary_owner_name("EXAMPLE HOLDINGS LLC"))
    matched = adapter.match_owners(
        entities, pl.DataFrame({"owner_key": [holdings, "not-a-real-key"]})
    )
    assert matched.height == 1
    assert matched["entity_id"].to_list() == ["1001"]
    assert chairman_is_person(matched["chairman_name_normalized"][0])


def test_dos_requires_official_columns(tmp_path: Path) -> None:
    path = tmp_path / "bad.csv"
    path.write_text("foo\n1\n")
    try:
        NycDosAdapter().load_entities(path)
    except ValueError as exc:
        assert "dos_id" in str(exc) or "current_entity_name" in str(exc)
    else:
        raise AssertionError("expected missing-column error")
