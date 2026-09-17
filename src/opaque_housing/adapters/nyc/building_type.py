"""Map official NYC building class / land use / unit count to canonical types.

Class membership comes from the DOF building-classification list and the
PLUTO 26v2 data dictionary (DCP-created condo rollup codes). The mapping
rules themselves are ours and are unit-tested.
"""

from opaque_housing.schema import BuildingType

# Official DOF labels that are cooperatives (not inferred from "CORP").
COOP_CLASSES: frozenset[str] = frozenset(
    {
        "A8",  # bungalow colony, cooperatively owned land
        "C6",
        "C8",
        "CC",
        "D0",
        "D4",
        "DC",
        "H7",
        "R9",
    }
)

# Residential condominium classes, including DCP billing-lot rollups.
# PLUTO stores one row per condo *complex* (billing lot), not per unit.
RESIDENTIAL_CONDO_CLASSES: frozenset[str] = frozenset(
    {"R0", "R1", "R2", "R3", "R4", "R6", "RD", "RR"}
)

MIXED_USE_RES_CLASSES: frozenset[str] = frozenset(
    {
        "C7",
        "D6",
        "D7",
        "K4",
        "O8",
        "R8",
        "RM",
        "RX",
        "RZ",
        "S0",
        "S1",
        "S2",
        "S3",
        "S4",
        "S5",
        "S9",
    }
)

# 1–4 family from official DOF descriptions (not unit-count guesses).
SFR_1_4_CLASSES: frozenset[str] = frozenset(
    {
        "A0",
        "A1",
        "A2",
        "A3",
        "A4",
        "A5",
        "A6",
        "A7",
        "A9",
        "B1",
        "B2",
        "B3",
        "B9",
        "C0",  # three families
        "C3",  # four families
    }
)


def normalize_bldgclass(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip().upper()
    return text or None


def normalize_landuse(value: object) -> int | None:
    if value is None or value == "":
        return None
    return int(float(str(value)))


def normalize_unitsres(value: object) -> int:
    if value is None or value == "":
        return 0
    return int(float(str(value)))


RESIDENTIAL_LAND_USES: frozenset[int] = frozenset({1, 2, 3, 4})

# Primarily-residential mixed-use classes (S*). Commercial-leaning mix codes
# (K4, O8, R8, …) enter the snapshot only via land use 4 or unitsres >= 1.
PRIMARILY_RES_MIXED_CLASSES: frozenset[str] = frozenset({"S0", "S1", "S2", "S3", "S4", "S5", "S9"})


def is_residential_pluto(
    *,
    bldgclass: object,
    landuse: object,
    unitsres: object,
) -> bool:
    """Keep a PLUTO lot if it is residential housing.

    Official tests, any one of:
    - ``unitsres >= 1``
    - DCP land use 1–4 (1–2 family, walk-up MF, elevator MF, mixed res/comm)
    - official coop, residential-condo, 1–4 family, or S* mixed class
    """
    if normalize_unitsres(unitsres) >= 1:
        return True
    if normalize_landuse(landuse) in RESIDENTIAL_LAND_USES:
        return True
    code = normalize_bldgclass(bldgclass)
    if code is None:
        return False
    return code in (
        COOP_CLASSES | RESIDENTIAL_CONDO_CLASSES | SFR_1_4_CLASSES | PRIMARILY_RES_MIXED_CLASSES
    )


def building_type_from_pluto(
    *,
    bldgclass: object,
    landuse: object,
    unitsres: object,
) -> BuildingType:
    """Assign a canonical building type. Never returns None."""
    code = normalize_bldgclass(bldgclass)
    units = normalize_unitsres(unitsres)
    use = normalize_landuse(landuse)

    if code in COOP_CLASSES:
        return BuildingType.COOP_BUILDING
    if code in RESIDENTIAL_CONDO_CLASSES:
        return BuildingType.CONDO_UNIT
    if code in MIXED_USE_RES_CLASSES or use == 4:
        return BuildingType.MIXED_USE_RES
    if code in SFR_1_4_CLASSES:
        return BuildingType.SFR_1_4
    if units >= 20:
        return BuildingType.LARGE_MF
    if units >= 5:
        return BuildingType.SMALL_MF
    if units >= 1 and use in {1, 2, 3}:
        if units <= 4:
            return BuildingType.SFR_1_4
        return BuildingType.SMALL_MF
    return BuildingType.OTHER_RES
