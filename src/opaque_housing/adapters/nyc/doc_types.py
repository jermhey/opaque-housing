"""ACRIS document-type → canonical mapping. Codes come from the official table."""

from __future__ import annotations

from pathlib import Path

import polars as pl

from opaque_housing.schema import DocTypeCanonical

LOOKUP_DIR = Path(__file__).parent / "lookups"
DOC_CODES_PATH = LOOKUP_DIR / "acris_document_control_codes.csv"
CONVEYANCE_CLASS = "DEEDS AND OTHER CONVEYANCES"

# Official doc__type values. Membership is checked against the committed table.
SALE_DEED_CODES: frozenset[str] = frozenset(
    {
        "DEED",
        "DEED, RC",
        "DEEDP",
        "DEEDO",
        "REIT",
        "ASTU",
    }
)


def load_official_codes(path: Path = DOC_CODES_PATH) -> pl.DataFrame:
    table = pl.read_csv(path, infer_schema_length=0)
    return table.rename({name: name.lower() for name in table.columns})


def conveyance_codes(path: Path = DOC_CODES_PATH) -> frozenset[str]:
    table = load_official_codes(path)
    rows = table.filter(pl.col("class_code_description") == CONVEYANCE_CLASS)
    return frozenset(rows["doc__type"].to_list())


def assert_sale_codes_are_official(path: Path = DOC_CODES_PATH) -> None:
    official = conveyance_codes(path)
    missing = SALE_DEED_CODES - official
    if missing:
        raise ValueError(f"sale_deed codes not in official conveyance class: {sorted(missing)}")


def canonical_doc_type(
    doc_type_raw: str | None,
    conveyance: frozenset[str] | None = None,
) -> DocTypeCanonical:
    code = (doc_type_raw or "").strip()
    if code in SALE_DEED_CODES:
        return DocTypeCanonical.SALE_DEED
    known = conveyance if conveyance is not None else conveyance_codes()
    if code in known:
        return DocTypeCanonical.NONSALE_DEED
    return DocTypeCanonical.OTHER


def canonical_doc_type_expr(
    column: str = "doc_type",
    conveyance: frozenset[str] | None = None,
) -> pl.Expr:
    known = list(conveyance if conveyance is not None else conveyance_codes())
    return (
        pl.when(pl.col(column).cast(pl.Utf8).str.strip_chars().is_in(list(SALE_DEED_CODES)))
        .then(pl.lit(DocTypeCanonical.SALE_DEED.value))
        .when(pl.col(column).cast(pl.Utf8).str.strip_chars().is_in(known))
        .then(pl.lit(DocTypeCanonical.NONSALE_DEED.value))
        .otherwise(pl.lit(DocTypeCanonical.OTHER.value))
    )
