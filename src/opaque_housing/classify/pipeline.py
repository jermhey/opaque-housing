"""Rules-only classification. Pure: names in, Owner records out."""

from __future__ import annotations

from opaque_housing.classify.rules import RULES_VERSION, apply_rules
from opaque_housing.normalize.names import owner_key, primary_owner_name
from opaque_housing.schema import BuildingType, ClassSource, Owner, OwnerClass


def classify_owner(
    name_raw: str | None,
    building_type: BuildingType | None = None,
) -> Owner:
    name_normalized = primary_owner_name(name_raw)
    rule = apply_rules(name_normalized, building_type)
    return Owner(
        owner_key=owner_key(name_normalized),
        name_normalized=name_normalized,
        owner_class=rule.owner_class,
        class_source=ClassSource.RULE,
        rule_id=rule.rule_id,
        confidence=1.0 if rule.owner_class is not OwnerClass.UNKNOWN else 0.0,
    )


def classify_owner_with_version(
    name_raw: str | None,
    building_type: BuildingType | None = None,
) -> tuple[Owner, str]:
    return classify_owner(name_raw, building_type), RULES_VERSION
