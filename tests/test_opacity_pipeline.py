from datetime import date
from pathlib import Path

import polars as pl

from opaque_housing.adapters.nyc.hpd import NycHpdAdapter
from opaque_housing.adapters.nyc.nys_dos import NycDosAdapter
from opaque_housing.adapters.nyc.pluto import NycPlutoAdapter
from opaque_housing.classify.apply import classify_parcel_frame
from opaque_housing.metrics.opacity import attach_opacity, entity_owned, opacity_headlines
from opaque_housing.opacity.build import attach_parcel_owners, run_opacity
from opaque_housing.resolve.denylist import seed_agent_names
from opaque_housing.schema import OpacityTier

PLUTO = Path("tests/fixtures/nyc/pluto_sample.csv")
EQUIV = Path("tests/fixtures/nyc/tract_nta_equiv_sample.csv")
REGS = Path("tests/fixtures/nyc/hpd_registrations.csv")
CONTACTS = Path("tests/fixtures/nyc/hpd_contacts.csv")
DOS = Path("tests/fixtures/nyc/nys_dos.csv")
AGENTS = Path("src/opaque_housing/adapters/nyc/lookups/nys_dos_agent_names.csv")


def test_fixture_pipeline_assigns_o1_and_o4() -> None:
    adapter = NycPlutoAdapter(snapshot_date=date(2026, 8, 1), tract_equiv_path=EQUIV)
    parcels = classify_parcel_frame(adapter.load_parcels_snapshot(PLUTO))
    hpd = NycHpdAdapter()
    latest = hpd.latest_registration_per_parcel(hpd.load_registrations(REGS))
    joined = hpd.contacts_on_latest(hpd.load_contacts(CONTACTS), latest)
    contacts = attach_parcel_owners(joined, parcels)
    dos = NycDosAdapter().load_entities(DOS)
    seeds = seed_agent_names(pl.read_csv(AGENTS)["name_raw"].to_list())
    matched = NycDosAdapter().match_owners(dos, parcels.select("owner_key"))
    results, links, _denied, membership = run_opacity(
        parcels, contacts, matched, seeds=seeds, threshold=20
    )
    tagged = attach_opacity(parcels, results)
    entities, _ = entity_owned(tagged)
    by_name = {
        rec["name_normalized"]: rec["opacity_tier"] for rec in entities.iter_rows(named=True)
    }
    assert by_name["EXAMPLE HOLDINGS LLC"] == OpacityTier.O1.value
    assert by_name["EXAMPLE APARTMENTS LLC"] == OpacityTier.O4.value
    assert by_name["EXAMPLE MIXED LLC"] == OpacityTier.O1.value
    holdings = entities.filter(pl.col("name_normalized") == "EXAMPLE HOLDINGS LLC")
    mixed = entities.filter(pl.col("name_normalized") == "EXAMPLE MIXED LLC")
    holdings_key = holdings["owner_key"][0]
    mixed_key = mixed["owner_key"][0]
    assert membership[holdings_key] == membership[mixed_key]
    assert links.filter(pl.col("link_type") == "hpd_person").height >= 1
    headlines = opacity_headlines(tagged)
    assert headlines["entity_owned"]["parcels"] >= 3
