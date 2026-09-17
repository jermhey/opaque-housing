from pathlib import Path

import polars as pl

from opaque_housing.adapters.nyc.hpd import NycHpdAdapter

REGS = Path("tests/fixtures/nyc/hpd_registrations.csv")
CONTACTS = Path("tests/fixtures/nyc/hpd_contacts.csv")


def test_latest_registration_per_bbl_and_valid_lots() -> None:
    adapter = NycHpdAdapter()
    regs = adapter.load_registrations(REGS)
    assert "5000100001" not in regs["parcel_id"].to_list()
    latest = adapter.latest_registration_per_parcel(regs)
    by_parcel = {row["parcel_id"]: row["registrationid"] for row in latest.iter_rows(named=True)}
    assert by_parcel["3001000010"] == "101"
    dropped = next(item for item in adapter.filter_counts if item.rule_id == "valid_bbl")
    assert dropped.rows_out < dropped.rows_in


def test_o1_person_not_agent_or_stale_registration() -> None:
    adapter = NycHpdAdapter()
    regs = adapter.latest_registration_per_parcel(adapter.load_registrations(REGS))
    contacts = adapter.contacts_on_latest(adapter.load_contacts(CONTACTS), regs)
    people = contacts.filter(pl.col("is_o1_person"))
    assert set(people["type"].to_list()) == {"HeadOfficer"}
    assert "OLD" not in people["firstname"].to_list()
    assert "RILEY" not in people["firstname"].to_list()
