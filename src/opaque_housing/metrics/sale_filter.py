"""Arm's-length sale filter. Pure; I/O stays in adapters and the CLI."""

from __future__ import annotations

from dataclasses import dataclass

import polars as pl

from opaque_housing.quality.filters import FilterCount
from opaque_housing.schema import DocTypeCanonical, PartyRole

FULL_INTEREST = 100.0
UNSPECIFIED_INTEREST = 0.0


@dataclass(frozen=True)
class SaleFilterConfig:
    min_consideration: float = 10_000.0
    treat_zero_amount_as_missing: bool = False
    require_named_grantee: bool = True
    require_full_interest: bool = False
    exclude_same_surname: bool = False
    drop_sale_codes: frozenset[str] = frozenset()


def _blank(column: str) -> pl.Expr:
    return pl.col(column).cast(pl.Utf8).fill_null("").str.strip_chars() == ""


def first_named_party(parties: pl.DataFrame, role: str, out_name: str) -> pl.DataFrame:
    named = (
        parties.filter(pl.col("role") == role)
        .with_columns(pl.col("name_raw").cast(pl.Utf8).fill_null("").str.strip_chars())
        .filter(pl.col("name_raw") != "")
        .sort(["doc_id", "name_raw"])
        .group_by("doc_id", maintain_order=True)
        .first()
        .select("doc_id", pl.col("name_raw").alias(out_name))
    )
    return named


def attach_primary_parties(transfers: pl.DataFrame, parties: pl.DataFrame) -> pl.DataFrame:
    grantees = first_named_party(parties, PartyRole.GRANTEE.value, "grantee_name_raw")
    grantors = first_named_party(parties, PartyRole.GRANTOR.value, "grantor_name_raw")
    return transfers.join(grantees, on="doc_id", how="left").join(grantors, on="doc_id", how="left")


def family_token(name: str | None) -> str:
    """First token after comma-split. ACRIS names are usually LAST FIRST."""
    text = " ".join((name or "").upper().replace(",", " ").split())
    if not text:
        return ""
    return text.split()[0]


def same_surname(grantor: str | None, grantee: str | None) -> bool:
    left = family_token(grantor)
    right = family_token(grantee)
    return bool(left) and left == right


def _consideration_ok(config: SaleFilterConfig) -> pl.Expr:
    amount = pl.col("consideration").cast(pl.Float64, strict=False)
    meets = amount >= config.min_consideration
    if config.treat_zero_amount_as_missing:
        zero_or_null = amount.is_null() | (amount == 0)
        return zero_or_null | meets
    return meets.fill_null(False)


def _full_interest_ok() -> pl.Expr:
    percent = pl.col("percent_trans").cast(pl.Float64, strict=False)
    return percent.is_null() | percent.is_in([UNSPECIFIED_INTEREST, FULL_INTEREST])


def apply_sale_filter(
    transfers: pl.DataFrame,
    config: SaleFilterConfig | None = None,
) -> tuple[pl.DataFrame, list[FilterCount]]:
    """Filter transfers to arm's-length sales. Logs every cut."""
    cfg = config or SaleFilterConfig()
    counts: list[FilterCount] = []
    work = transfers
    if "grantee_name_raw" not in work.columns:
        work = work.with_columns(pl.lit(None).cast(pl.Utf8).alias("grantee_name_raw"))
    if "grantor_name_raw" not in work.columns:
        work = work.with_columns(pl.lit(None).cast(pl.Utf8).alias("grantor_name_raw"))

    rows_in = work.height
    work = work.filter(pl.col("doc_type_canonical") == DocTypeCanonical.SALE_DEED.value)
    counts.append(
        FilterCount(
            stage="sale_filter",
            rule_id="sale_deed_type",
            rows_in=rows_in,
            rows_out=work.height,
        )
    )

    if cfg.drop_sale_codes:
        rows_in = work.height
        work = work.filter(~pl.col("doc_type_raw").is_in(list(cfg.drop_sale_codes)))
        counts.append(
            FilterCount(
                stage="sale_filter",
                rule_id="drop_sale_codes",
                rows_in=rows_in,
                rows_out=work.height,
            )
        )

    if cfg.require_named_grantee:
        rows_in = work.height
        work = work.filter(~_blank("grantee_name_raw"))
        counts.append(
            FilterCount(
                stage="sale_filter",
                rule_id="named_grantee",
                rows_in=rows_in,
                rows_out=work.height,
            )
        )

    rows_in = work.height
    work = work.filter(_consideration_ok(cfg))
    counts.append(
        FilterCount(
            stage="sale_filter",
            rule_id="min_consideration",
            rows_in=rows_in,
            rows_out=work.height,
        )
    )

    if cfg.require_full_interest and "percent_trans" in work.columns:
        rows_in = work.height
        work = work.filter(_full_interest_ok())
        counts.append(
            FilterCount(
                stage="sale_filter",
                rule_id="full_interest",
                rows_in=rows_in,
                rows_out=work.height,
            )
        )

    if cfg.exclude_same_surname:
        flags = [
            same_surname(row.get("grantor_name_raw"), row.get("grantee_name_raw"))
            for row in work.iter_rows(named=True)
        ]
        rows_in = work.height
        work = work.with_columns(pl.Series("same_surname", flags, dtype=pl.Boolean)).filter(
            ~pl.col("same_surname")
        )
        counts.append(
            FilterCount(
                stage="sale_filter",
                rule_id="exclude_same_surname",
                rows_in=rows_in,
                rows_out=work.height,
            )
        )
        if "same_surname" in work.columns:
            work = work.drop("same_surname")

    return work, counts
