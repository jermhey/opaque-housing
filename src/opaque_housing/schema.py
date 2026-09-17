"""Canonical tables. Adapters emit these; everything downstream is metro-agnostic."""

from datetime import date
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class MetroId(StrEnum):
    NYC = "nyc"
    PHL = "phl"


class BuildingType(StrEnum):
    SFR_1_4 = "sfr_1_4"
    CONDO_UNIT = "condo_unit"
    SMALL_MF = "small_mf"
    LARGE_MF = "large_mf"
    MIXED_USE_RES = "mixed_use_res"
    COOP_BUILDING = "coop_building"
    OTHER_RES = "other_res"


class OwnerClass(StrEnum):
    INDIVIDUAL = "individual"
    TRUST = "trust"
    ESTATE = "estate"
    LLC = "llc"
    CORP = "corp"
    PARTNERSHIP = "partnership"
    COOP_CORP = "coop_corp"
    HDFC = "hdfc"
    PUBLIC = "public"
    NONPROFIT_RELIGIOUS = "nonprofit_religious"
    LENDER_REO = "lender_reo"
    UNKNOWN = "unknown"


class ClassSource(StrEnum):
    RULE = "rule"
    LLM = "llm"
    MANUAL = "manual"


class DocTypeCanonical(StrEnum):
    SALE_DEED = "sale_deed"
    NONSALE_DEED = "nonsale_deed"
    OTHER = "other"


class PartyRole(StrEnum):
    GRANTOR = "grantor"
    GRANTEE = "grantee"


class OpacityTier(StrEnum):
    O1 = "O1"
    O2 = "O2"
    O3 = "O3"
    O4 = "O4"


class ParcelSnapshot(BaseModel):
    metro_id: str
    parcel_id: str
    snapshot_date: date
    geo_tract: str | None = None
    geo_neighborhood: str | None = None
    geo_borough: str | None = None
    building_type: BuildingType
    res_units: int
    owner_name_raw: str | None = None
    owner_mailing_address_raw: str | None = None
    source_dataset: str
    source_version: str


class Transfer(BaseModel):
    metro_id: str
    doc_id: str
    recorded_date: date | None = None
    doc_date: date | None = None
    doc_type_raw: str
    doc_type_canonical: DocTypeCanonical
    consideration: float | None = None
    parcel_ids: list[str] = Field(default_factory=list)
    source_dataset: str
    source_version: str


class TransferParty(BaseModel):
    metro_id: str
    doc_id: str
    role: PartyRole
    name_raw: str | None = None
    address_raw: str | None = None


class Owner(BaseModel):
    owner_key: str
    name_normalized: str
    owner_class: OwnerClass
    class_source: ClassSource
    rule_id: str | None = None
    model_id: str | None = None
    prompt_version: str | None = None
    confidence: float | None = None


class EntityRecord(BaseModel):
    entity_id: str
    name_normalized: str
    formation_date: date | None = None
    jurisdiction: str | None = None
    entity_type: str | None = None
    process_address_normalized: str | None = None


class OwnerLink(BaseModel):
    owner_key_a: str
    owner_key_b: str
    link_type: str
    evidence_ref: str


class OwnerCluster(BaseModel):
    cluster_id: str
    owner_key: str


class Opacity(BaseModel):
    owner_key: str
    tier: OpacityTier
    evidence: dict[str, Any]
    rules_version: str


ENTITY_OWNED_CLASSES: frozenset[OwnerClass] = frozenset(
    {OwnerClass.LLC, OwnerClass.CORP, OwnerClass.PARTNERSHIP}
)

PRIVATE_DENOMINATOR_EXCLUSIONS: frozenset[OwnerClass] = frozenset(
    {OwnerClass.PUBLIC, OwnerClass.NONPROFIT_RELIGIOUS}
)
