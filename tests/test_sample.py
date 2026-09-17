from datetime import date
from pathlib import Path

from opaque_housing.adapters.nyc.pluto import NycPlutoAdapter
from opaque_housing.classify.apply import classify_parcel_frame
from opaque_housing.labeling.sample import assign_splits, stratified_owner_sample

FIXTURE = Path("tests/fixtures/nyc/pluto_sample.csv")


def test_stratified_sample_and_split() -> None:
    adapter = NycPlutoAdapter(snapshot_date=date(2026, 8, 1))
    classified = classify_parcel_frame(adapter.load_parcels_snapshot(FIXTURE))
    sample = stratified_owner_sample(classified, n=4, seed=1)
    assert 1 <= sample.height <= 4
    assert sample["name_normalized"].null_count() == 0
    split = assign_splits(sample, seed=1)
    assert set(split["split"].to_list()) <= {"dev", "test"}
