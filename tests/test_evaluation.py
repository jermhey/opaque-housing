from pathlib import Path

from opaque_housing.classify.pipeline import classify_owner
from opaque_housing.metrics.evaluation import evaluation_report, macro_f1
from opaque_housing.schema import BuildingType

GOLD = Path("eval/gold/ci_dev.csv")


def test_perfect_diagonal_is_one() -> None:
    matrix = [[2, 0], [0, 3]]
    assert macro_f1(matrix) == 1.0


def test_ci_dev_gold_meets_baseline() -> None:
    lines = GOLD.read_text().splitlines()
    header = lines[0].split(",")
    rows = [dict(zip(header, line.split(","), strict=True)) for line in lines[1:]]
    test_rows = [row for row in rows if row["split"] == "test"]
    y_true = [row["owner_class"] for row in test_rows]
    y_pred = [
        classify_owner(
            row["name_raw"] or None,
            BuildingType(row["building_type"]) if row["building_type"] else None,
        ).owner_class.value
        for row in test_rows
    ]
    report = evaluation_report(y_true, y_pred)
    assert report["macro_f1"] == 1.0
    assert report["n"] == len(test_rows)
