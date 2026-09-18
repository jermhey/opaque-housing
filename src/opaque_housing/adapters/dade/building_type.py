"""Miami-Dade DOR descriptions → canonical types.

``DOR_DESC`` values were read from live PaGis MapServer/24 on 2026-09-18.
"""

from __future__ import annotations

from opaque_housing.schema import BuildingType


def _desc(value: object) -> str:
    return "" if value is None else str(value).upper()


def _units(value: object) -> int | None:
    if value is None or value == "":
        return None
    try:
        parsed = int(float(str(value)))
    except ValueError:
        return None
    return parsed if parsed > 0 else None


def is_cancelled(flag: object) -> bool:
    return str(flag or "").strip().upper() == "Y"


def is_residential(description: object, cancel_flag: object = None) -> bool:
    if is_cancelled(cancel_flag):
        return False
    desc = _desc(description)
    if not desc or "VACANT" in desc or "REFERENCE FOLIO" in desc:
        return False
    if "PARKING" in desc or "COMMON AREA" in desc or "DOCK" in desc:
        return False
    if "HOTEL" in desc or "MOTEL" in desc:
        return False
    return any(
        token in desc
        for token in (
            "RESIDENTIAL - SINGLE FAMILY",
            "CONDOMINIUM - RESIDENTIAL",
            "TOWNHOUSE",
            "MULTIFAMILY 2-9 UNITS",
            "MULTIFAMILY 10 UNITS PLUS",
            "COOPERATIVE - RESIDENTIAL",
        )
    )


def building_type_and_units(description: object, unit_count: object) -> tuple[BuildingType, int]:
    desc = _desc(description)
    units = _units(unit_count)
    if "CONDOMINIUM - RESIDENTIAL" in desc:
        return BuildingType.CONDO_UNIT, 1
    if "COOPERATIVE - RESIDENTIAL" in desc:
        return BuildingType.COOP_BUILDING, units or 1
    if "MULTIFAMILY 10 UNITS PLUS" in desc:
        count = units or 10
        if count >= 20:
            return BuildingType.LARGE_MF, count
        return BuildingType.SMALL_MF, count
    if "MULTIFAMILY 2-9 UNITS" in desc:
        count = units or 5
        if 2 <= count <= 4:
            return BuildingType.SFR_1_4, count
        return BuildingType.SMALL_MF, count
    return BuildingType.SFR_1_4, units or 1
