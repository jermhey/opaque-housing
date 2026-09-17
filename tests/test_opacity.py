from opaque_housing.opacity.tiers import OpacityInput, assign_tier, o1_rule
from opaque_housing.schema import OpacityTier


def _row(**kwargs: object) -> OpacityInput:
    payload = {
        "owner_key": "abc",
        "name_normalized": "EXAMPLE HOLDINGS LLC",
        "has_hpd_person": False,
    }
    payload.update(kwargs)
    return OpacityInput(**payload)  # type: ignore[arg-type]


def test_t010_hpd_person_positive_and_negative() -> None:
    pos = _row(has_hpd_person=True, hpd_person_roles=("HeadOfficer",))
    neg = _row(has_hpd_person=False)
    assert o1_rule(pos) == "T010_hpd_person"
    assert assign_tier(pos, False).tier is OpacityTier.O1
    assert o1_rule(neg) is None
    assert assign_tier(neg, False).tier is not OpacityTier.O1


def test_t020_dos_chairman_positive_and_negative() -> None:
    pos = _row(has_dos_chairman_person=True)
    neg = _row(has_dos_chairman_person=False)
    assert o1_rule(pos) == "T020_dos_chairman"
    assert assign_tier(pos, False).rule_id == "T020_dos_chairman"
    assert o1_rule(neg) is None


def test_t030_cluster_o1_positive_and_negative() -> None:
    row = _row()
    pos = assign_tier(row, True)
    neg = assign_tier(row, False)
    assert pos.tier is OpacityTier.O2
    assert pos.rule_id == "T030_cluster_o1"
    assert neg.tier is not OpacityTier.O2


def test_t040_entity_chain_positive_and_negative() -> None:
    pos = assign_tier(_row(has_entity_chain=True), False)
    neg = assign_tier(_row(has_entity_chain=False), False)
    assert pos.tier is OpacityTier.O4
    assert pos.rule_id == "T040_entity_chain"
    assert neg.tier is OpacityTier.O3


def test_t050_residual_o3() -> None:
    row = assign_tier(_row(agent_address_only=False, address_count=1), False)
    assert row.tier is OpacityTier.O3
    assert row.rule_id == "T050_no_person"
    assert row.evidence["agent_address_only"] is False


def test_o1_beats_cluster_and_chain() -> None:
    row = _row(has_hpd_person=True, has_entity_chain=True)
    result = assign_tier(row, True)
    assert result.tier is OpacityTier.O1
    assert result.rule_id == "T010_hpd_person"
