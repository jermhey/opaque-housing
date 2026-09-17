from opaque_housing.adapters.nyc.sources import NYS_DOS, resolve_ingest_specs


def test_resolve_ingest_specs_hpd_dos_opacity() -> None:
    hpd = resolve_ingest_specs("hpd")
    assert [spec.dataset_id for spec in hpd] == ["tesw-yqqr", "feu5-w2e2"]
    dos = resolve_ingest_specs("dos")
    assert dos == [NYS_DOS]
    assert NYS_DOS.host == "https://data.ny.gov"
    assert "data.ny.gov" in NYS_DOS.csv_url
    opacity = resolve_ingest_specs("opacity")
    assert [spec.name for spec in opacity] == ["hpd_registrations", "hpd_contacts", "nys_dos"]


def test_all_still_pluto_and_tract() -> None:
    names = [spec.name for spec in resolve_ingest_specs("all")]
    assert names == ["pluto", "tract_nta"]
