"""Map verified OPA category / building-code descriptions to canonical types.

Field values were read from live ``opa_properties_public`` on 2026-09-17.
Unit counts are official description lower bounds (ADR 0010).
"""

from __future__ import annotations

import re

from opaque_housing.schema import BuildingType

RESIDENTIAL_CATEGORIES = frozenset({"1", "2", "3", "14"})
_DROP = re.compile(r"VACANT LAND|CONDO PARKING")
_CONDO = re.compile(r"\bRES CONDO\b")
_APT_2_4 = re.compile(r"APT 2-4 UNITS")
_APT_5_50 = re.compile(r"APTS 5-50 UNITS")
_APT_51_100 = re.compile(r"APTS 51-100 UNITS")
_APT_100 = re.compile(r"APTS 100\+ UNITS")


def normalize_category(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text


def is_residential(category: object, description: object) -> bool:
    if normalize_category(category) not in RESIDENTIAL_CATEGORIES:
        return False
    desc = "" if description is None else str(description).upper()
    return _DROP.search(desc) is None


def building_type_and_units(category: object, description: object) -> tuple[BuildingType, int]:
    """Return canonical type and a lower-bound unit count (ADR 0010)."""
    cat = normalize_category(category)
    desc = "" if description is None else str(description).upper()
    if _CONDO.search(desc):
        return BuildingType.CONDO_UNIT, 1
    if _APT_100.search(desc):
        return BuildingType.LARGE_MF, 100
    if _APT_51_100.search(desc):
        return BuildingType.LARGE_MF, 51
    if _APT_5_50.search(desc):
        return BuildingType.SMALL_MF, 5
    if cat == "14":
        return BuildingType.SMALL_MF, 5
    if _APT_2_4.search(desc) or cat == "2":
        return BuildingType.SFR_1_4, 2
    if cat == "3":
        return BuildingType.MIXED_USE_RES, 1
    return BuildingType.SFR_1_4, 1
