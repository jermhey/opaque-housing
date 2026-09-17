"""Ordered owner-class rules. Each rule has a rule_id and unit tests."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from opaque_housing.schema import BuildingType, OwnerClass

RULES_VERSION = "2026-09-17.3"

_TokenPred = Callable[[str], bool]


def _has(pattern: re.Pattern[str]) -> _TokenPred:
    return lambda name: pattern.search(name) is not None


def _eq(value: str) -> _TokenPred:
    return lambda name: name == value


_HDFC = re.compile(r"\bHDFC\b|HOUSING DEVELOPMENT FU")
_ESTATE = re.compile(r"^ESTATE\b|\bESTATE OF\b|\bEST OF\b")
_TRUST = re.compile(r"\bTRUSTEE\b|\bTRUST\b|\b TR$")
_LLC = re.compile(r"\bLLC\b")
_PARTNERSHIP = re.compile(
    r"\bLLLP\b|\bLLP\b|\bLP\b|\bLIMITED PARTNERSHIP\b|\bGENERAL PARTNERSHIP\b|\bL P\b"
)
_CORP = re.compile(
    r"\bCORP\b|\bINC\b|\bLTD\b|\bPC\b|\bCOMPANY\b|\bCO\b|\bPLC\b|\bLIMITED\b|(?<=[A-Z])CORP\b"
)
_COOP_NAME = re.compile(r"\bCO-?OP\b|\bCOOPERATIVE\b|\bTENANTS CORP\b|\bOWNERS CORP\b")
_INDIVIDUAL_MARK = re.compile(r"\bET AL\b|\bETAL\b|\bJTWROS\b|\bJT TEN\b|\bH/W\b|\bHUS\b|\bWIFE\b")
_PERSON_TOKEN = r"[A-Z]+(?:-[A-Z]+)*"
_PERSON_LIKE = re.compile(rf"^{_PERSON_TOKEN}(?:[ &]+{_PERSON_TOKEN}){{1,4}}$")
_HAS_DIGIT = re.compile(r"\d")
_NOT_PERSON = re.compile(
    r"\b(REALTY|PROPERTIES|HOLDINGS|HOLDING|MANAGEMENT|ASSOCIATES|GROUP|VENTURES|"
    r"PARTNERS|ENTERPRISES|INVESTMENTS|DEVELOPMENT|CAPITAL|HOMES|HOUSING|"
    r"EQUITIES|FUND|ASSOC|CONDOMINIUM|CONDOMINUM)\b"
)

# Agency phrases only. Bare USA / NYS / FEDERAL over-fired on private firms (dev gold).
_PUBLIC = re.compile(
    r"\bCITY OF NEW YORK\b|\bNEW YORK CITY\b|\bNYCHA\b|\bHOUSING AUTH"
    r"|\bCITY OF PHILADELPHIA\b"
    r"|\bUNITED STATES\b|\bUS GOVERNMENT\b"
    r"|\bSTATE OF NEW YORK\b|\bNEW YORK STATE\b"
    r"|\bPORT AUTHORITY\b|\bMTA\b|\bMETROPOLITAN TRANSPORTATION\b"
    r"|\bDEPARTMENT OF\b|\bNYC DEPARTMENT\b|\bDCAS\b"
    r"|\bPARKS AND RECREATION\b|\bNYC PARKS\b"
    r"|\bHUD\b|\bNYS OFFICE\b|\bNYS DEPARTMENT\b"
    r"|\bCITY COLLEGE\b|\bGRAND-?DUCHY\b"
)
_LENDER = re.compile(
    r"\bFANNIE MAE\b|\bFREDDIE MAC\b|\bFNMA\b|\bFHLMC\b|\bGINNIE MAE\b|\bGNMA\b"
    r"|\bFEDERAL NATIONAL MORTGAGE\b"
    r"|\bBANK OF\b|\bREO\b|\bMORTGAGE\b|\bSERVICING\b"
    r"|\bWELLS FARGO\b|\bCITIMORTGAGE\b|\bJPMORGAN CHASE\b|\bJ P MORGAN CHASE\b"
    r"|\bCHASE BANK\b|\bSECRETARY OF HOUSING\b"
    r"|\b BANK\b"
)
_NONPROFIT = re.compile(
    r"\bCHURCH\b|\bSYNAGOGUE\b|\bTEMPLE\b|\bMOSQUE\b|\bPARISH\b|\bDIOCESE\b"
    r"|\bUNIVERSITY\b|\bCOLLEGE\b"
    r"|\bFOUNDATION\b|\bYMCA\b|\bYWCA\b"
    r"|\bHOSPITAL\b|\bCONVENT\b|\bRECTORY\b"
    r"|\bMINISTRY\b|\bAMBULANCE\b|\bDEVELOPMENTAL DISABILITIES\b"
)
_STREET_COLLEGE = re.compile(r"\bCOLLEGE (POINT|AVE|AVENUE|ST|STREET|RD|ROAD)\b")
_CHURCH_AS_STREET = re.compile(r"\b(CHURCH|CONVENT|TEMPLE)\b.*\b(RLTY|REALTY)\b")
_WS = re.compile(r"\s+")


def _has_legal_form(name: str) -> bool:
    return (
        _LLC.search(name) is not None
        or _CORP.search(name) is not None
        or _PARTNERSHIP.search(name) is not None
    )


def _is_public(name: str) -> bool:
    if _LLC.search(name):
        return False
    if "CITY COLLEGE" in name:
        return True
    if _PUBLIC.search(name) is None:
        return False
    if re.search(r"\b(UNIVERSITY|CHURCH|HOSPITAL|SYNAGOGUE)\b", name):
        return False
    if re.search(r"\b(MORTGAGE|FANNIE|FREDDIE)\b", name) or re.search(r"\b BANK\b", name):
        return False
    return True


def _is_lender(name: str) -> bool:
    if _LLC.search(name):
        return False
    return _LENDER.search(name) is not None


def _is_nonprofit(name: str) -> bool:
    if _LLC.search(name):
        return False
    if _STREET_COLLEGE.search(name) or _CHURCH_AS_STREET.search(name):
        return False
    return _NONPROFIT.search(name) is not None


def _is_estate(name: str) -> bool:
    if _has_legal_form(name):
        return False
    return _ESTATE.search(name) is not None


def _is_coop_building(_name: str, building_type: BuildingType | None) -> bool:
    return building_type is BuildingType.COOP_BUILDING


def _is_coop_name(name: str) -> bool:
    if _LLC.search(name):
        return False
    return _COOP_NAME.search(name) is not None


def _is_individual(name: str) -> bool:
    if _INDIVIDUAL_MARK.search(name):
        stem = _WS.sub(" ", _INDIVIDUAL_MARK.sub(" ", name)).strip()
        return bool(stem) and _PERSON_LIKE.search(stem) is not None
    if _HAS_DIGIT.search(name) or _NOT_PERSON.search(name):
        return False
    if _has_legal_form(name):
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
    Rule("R050_estate", OwnerClass.ESTATE, _is_estate),
    Rule("R051_estate_suffix", OwnerClass.ESTATE, lambda _n: False),
    Rule("R060_trust", OwnerClass.TRUST, _has(_TRUST)),
    Rule(
        "R070_coop_building",
        OwnerClass.COOP_CORP,
        lambda _n: False,
        matches=_is_coop_building,
    ),
    Rule("R071_coop_name", OwnerClass.COOP_CORP, _is_coop_name),
    Rule("R080_llc", OwnerClass.LLC, _has(_LLC)),
    Rule("R090_partnership", OwnerClass.PARTNERSHIP, _has(_PARTNERSHIP)),
    Rule("R100_corp", OwnerClass.CORP, _has(_CORP)),
    Rule("R110_individual", OwnerClass.INDIVIDUAL, _is_individual),
    Rule("R999_unknown", OwnerClass.UNKNOWN, lambda _n: True),
)

_RULE_BY_ID = {rule.rule_id: rule for rule in RULES}


def rule_by_id(rule_id: str) -> Rule:
    return _RULE_BY_ID[rule_id]


def apply_rules(name_normalized: str, building_type: BuildingType | None = None) -> Rule:
    for rule in RULES:
        if rule.applies(name_normalized, building_type):
            return rule
    return RULES[-1]
