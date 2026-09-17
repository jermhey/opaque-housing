"""Ordered owner-class rules. Each rule has a rule_id and unit tests."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from opaque_housing.schema import BuildingType, OwnerClass

RULES_VERSION = "2026-09-16.1"

_TokenPred = Callable[[str], bool]


def _has(pattern: re.Pattern[str]) -> _TokenPred:
    return lambda name: pattern.search(name) is not None


def _eq(value: str) -> _TokenPred:
    return lambda name: name == value


_HDFC = re.compile(r"\bHDFC\b|HOUSING DEVELOPMENT FUND")
_ESTATE = re.compile(r"^ESTATE\b|\bESTATE OF\b|\bEST OF\b")
_TRUST = re.compile(r"\bTRUSTEE\b|\bTRUST\b|\b TR$")
_LLC = re.compile(r"\bLLC\b")
_PARTNERSHIP = re.compile(
    r"\bLLLP\b|\bLLP\b|\bLP\b|\bLIMITED PARTNERSHIP\b|\bGENERAL PARTNERSHIP\b|\bL P\b"
)
_CORP = re.compile(r"\bCORP\b|\bINC\b|\bLTD\b|\bPC\b|\bCOMPANY\b|\bCO\b|\bPLC\b")
_COOP_NAME = re.compile(r"\bCO-?OP\b|\bCOOPERATIVE\b|\bTENANTS CORP\b|\bOWNERS CORP\b")
_INDIVIDUAL_MARK = re.compile(r"\bET AL\b|\bJTWROS\b|\bJT TEN\b|\bH/W\b|\bHUS\b|\bWIFE\b")
_PERSON_LIKE = re.compile(r"^[A-Z]+(?:[ &]+[A-Z]+){1,4}$")
_HAS_DIGIT = re.compile(r"\d")
_NOT_PERSON = re.compile(
    r"\b(REALTY|PROPERTIES|HOLDINGS|MANAGEMENT|ASSOCIATES|GROUP|VENTURES|"
    r"PARTNERS|ENTERPRISES|INVESTMENTS|DEVELOPMENT|CAPITAL|HOMES|HOUSING|"
    r"EQUITIES|FUND|ASSOC)\b"
)

_PUBLIC = re.compile(
    r"\bCITY OF NEW YORK\b|\bNEW YORK CITY\b|\bNYCHA\b|\bHOUSING AUTHORITY\b"
    r"|\bUNITED STATES\b|\bU S A\b|\bUS GOVERNMENT\b|\bUSA\b"
    r"|\bSTATE OF NEW YORK\b|\bNYS \b|\bNEW YORK STATE\b"
    r"|\bPORT AUTHORITY\b|\bMTA\b|\bMETROPOLITAN TRANSPORTATION\b"
    r"|\bDEPARTMENT OF\b|\bNYC DEPARTMENT\b|\bDCAS\b"
    r"|\bPARKS AND RECREATION\b|\bNYC PARKS\b"
    r"|\bFEDERAL\b|\bHUD\b"
)
_LENDER = re.compile(
    r"\bFANNIE MAE\b|\bFREDDIE MAC\b|\bFNMA\b|\bFHLMC\b|\bGINNIE MAE\b|\bGNMA\b"
    r"|\bBANK OF\b|\b N A\b|\b NA\b|\bREO\b|\bMORTGAGE\b|\bSERVICING\b"
    r"|\bWELLS FARGO\b|\bCITIMORTGAGE\b|\bCHASE\b"
    r"|\bSECRETARY OF HOUSING\b"
)
_NONPROFIT = re.compile(
    r"\bCHURCH\b|\bSYNAGOGUE\b|\bTEMPLE\b|\bMOSQUE\b|\bPARISH\b|\bDIOCESE\b"
    r"|\bUNIVERSITY\b|\bCOLLEGE\b"
    r"|\bFOUNDATION\b|\bYMCA\b|\bYWCA\b"
    r"|\bHOSPITAL\b|\bCONVENT\b|\bRECTORY\b"
)


def _is_public(name: str) -> bool:
    return _PUBLIC.search(name) is not None


def _is_lender(name: str) -> bool:
    if _LLC.search(name):
        return False
    return _LENDER.search(name) is not None


def _is_nonprofit(name: str) -> bool:
    if "COLLEGE POINT" in name:
        return False
    return _NONPROFIT.search(name) is not None


def _is_coop_building(_name: str, building_type: BuildingType | None) -> bool:
    return building_type is BuildingType.COOP_BUILDING


def _is_individual(name: str) -> bool:
    if _INDIVIDUAL_MARK.search(name):
        return True
    if _HAS_DIGIT.search(name) or _NOT_PERSON.search(name):
        return False
    if _LLC.search(name) or _CORP.search(name) or _PARTNERSHIP.search(name):
        return False
    return _PERSON_LIKE.search(name) is not None


@dataclass(frozen=True)
class Rule:
    rule_id: str
    owner_class: OwnerClass
    matches_name: Callable[[str], bool]
    matches: Callable[[str, BuildingType | None], bool] | None = None

    def applies(self, name: str, building_type: BuildingType | None) -> bool:
        if self.matches is not None:
            return self.matches(name, building_type)
        return self.matches_name(name)


# First match wins. More specific legal forms beat generic CORP/INC.
RULES: tuple[Rule, ...] = (
    Rule("R001_blank", OwnerClass.UNKNOWN, _eq("")),
    Rule("R010_hdfc", OwnerClass.HDFC, _has(_HDFC)),
    Rule("R020_public", OwnerClass.PUBLIC, _is_public),
    Rule("R030_lender", OwnerClass.LENDER_REO, _is_lender),
    Rule("R040_nonprofit", OwnerClass.NONPROFIT_RELIGIOUS, _is_nonprofit),
    Rule("R050_estate", OwnerClass.ESTATE, _has(_ESTATE)),
    Rule("R060_trust", OwnerClass.TRUST, _has(_TRUST)),
    Rule(
        "R070_coop_building",
        OwnerClass.COOP_CORP,
        lambda _n: False,
        matches=_is_coop_building,
    ),
    Rule("R071_coop_name", OwnerClass.COOP_CORP, _has(_COOP_NAME)),
    Rule("R080_llc", OwnerClass.LLC, _has(_LLC)),
    Rule("R090_partnership", OwnerClass.PARTNERSHIP, _has(_PARTNERSHIP)),
    Rule("R100_corp", OwnerClass.CORP, _has(_CORP)),
    Rule("R110_individual", OwnerClass.INDIVIDUAL, _is_individual),
    Rule("R999_unknown", OwnerClass.UNKNOWN, lambda _n: True),
)


def apply_rules(name_normalized: str, building_type: BuildingType | None = None) -> Rule:
    for rule in RULES:
        if rule.applies(name_normalized, building_type):
            return rule
    return RULES[-1]
