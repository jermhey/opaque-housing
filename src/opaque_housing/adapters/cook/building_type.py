"""Cook County class codes → canonical types.

Class descriptions are from the official CCAO class_dict. ``char_apts`` values
were read from live ``x54s-btds`` (year 2026, class 211) on 2026-09-18.
"""

from __future__ import annotations

from opaque_housing.schema import BuildingType

SFR_CLASSES = frozenset(
    {"202", "203", "204", "205", "206", "207", "208", "209", "210", "234", "278", "295"}
)
MF_2_6 = "211"
MIXED_2_6 = "212"
COOP = "213"
CONDO = frozenset({"299", "399"})
LARGE_MF = frozenset({"313", "314", "315", "318", "391", "396"})
OTHER_RES = frozenset({"218", "219", "225"})
RESIDENTIAL_CLASSES = SFR_CLASSES | CONDO | LARGE_MF | OTHER_RES | {MF_2_6, MIXED_2_6, COOP}

_APT_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "none": 0,
}


def normalize_class(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text


def parse_apts(value: object) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith(".0"):
        text = text[:-2]
    key = text.lower()
    if key in _APT_WORDS:
        count = _APT_WORDS[key]
        return count if count > 0 else None
    try:
        parsed = int(float(text))
    except ValueError:
        return None
    return parsed if parsed > 0 else None


def is_residential(class_code: object) -> bool:
    return normalize_class(class_code) in RESIDENTIAL_CLASSES


def is_truthy_flag(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "t", "1", "yes"}


def building_type_and_units(
    class_code: object,
    *,
    char_apts: object = None,
    parking: object = None,
    common_area: object = None,
) -> tuple[BuildingType, int] | None:
    code = normalize_class(class_code)
    if code not in RESIDENTIAL_CLASSES:
        return None
    if code in CONDO:
        if is_truthy_flag(parking) or is_truthy_flag(common_area):
            return None
        return BuildingType.CONDO_UNIT, 1
    if code in SFR_CLASSES:
        return BuildingType.SFR_1_4, 1
    if code == COOP:
        return BuildingType.COOP_BUILDING, 1
    if code in OTHER_RES:
        return BuildingType.OTHER_RES, 1
    units = parse_apts(char_apts)
    if code == MF_2_6:
        count = units or 2
        if count >= 5:
            return BuildingType.SMALL_MF, count
        return BuildingType.SFR_1_4, count
    if code == MIXED_2_6:
        return BuildingType.MIXED_USE_RES, units or 2
    if code in LARGE_MF:
        count = units or 7
        if count >= 20:
            return BuildingType.LARGE_MF, count
        return BuildingType.SMALL_MF, count
    return BuildingType.OTHER_RES, 1
