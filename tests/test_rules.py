from opaque_housing.classify.pipeline import classify_owner
from opaque_housing.classify.rules import RULES, apply_rules
from opaque_housing.normalize.names import primary_owner_name
from opaque_housing.schema import BuildingType, OwnerClass

# rule_id, raw name, building_type, expected class, positive?
CASES: list[tuple[str, str, BuildingType | None, OwnerClass]] = [
    ("R001_blank", "", None, OwnerClass.UNKNOWN),
    ("R010_hdfc", "EAST SIDE HDFC", None, OwnerClass.HDFC),
    ("R010_hdfc", "HOUSING DEVELOPMENT FUND CORP", None, OwnerClass.HDFC),
    ("R020_public", "CITY OF NEW YORK", None, OwnerClass.PUBLIC),
    ("R020_public", "NYCHA", None, OwnerClass.PUBLIC),
    ("R030_lender", "FANNIE MAE", None, OwnerClass.LENDER_REO),
    ("R030_lender", "WELLS FARGO BANK NA", None, OwnerClass.LENDER_REO),
    ("R040_nonprofit", "ST MARYS CHURCH", None, OwnerClass.NONPROFIT_RELIGIOUS),
    ("R040_nonprofit", "COLUMBIA UNIVERSITY", None, OwnerClass.NONPROFIT_RELIGIOUS),
    ("R050_estate", "ESTATE OF JOHN SMITH", None, OwnerClass.ESTATE),
    ("R051_estate_suffix", "BUZ, FREDERICK H/LWT/DEF", None, OwnerClass.ESTATE),
    ("R051_estate_suffix", "LEE, HYMAN/LWT", None, OwnerClass.ESTATE),
    ("R060_trust", "SMITH FAMILY TRUST", None, OwnerClass.TRUST),
    ("R060_trust", "JOHN SMITH TRUSTEE OF SMITH TRUST", None, OwnerClass.TRUST),
    ("R060_trust", "JOHN SMITH TR", None, OwnerClass.TRUST),
    (
        "R070_coop_building",
        "EXAMPLE TENANTS CORP",
        BuildingType.COOP_BUILDING,
        OwnerClass.COOP_CORP,
    ),
    ("R070_coop_building", "123 MAIN ST LLC", BuildingType.COOP_BUILDING, OwnerClass.COOP_CORP),
    ("R071_coop_name", "PARK TENANTS CORP", BuildingType.SFR_1_4, OwnerClass.COOP_CORP),
    ("R080_llc", "123 MAIN ST LLC", BuildingType.SFR_1_4, OwnerClass.LLC),
    ("R090_partnership", "ABC ASSOCIATES LP", None, OwnerClass.PARTNERSHIP),
    ("R090_partnership", "SMITH JONES LLP", None, OwnerClass.PARTNERSHIP),
    ("R100_corp", "ABC REALTY CORP", None, OwnerClass.CORP),
    ("R100_corp", "ABC REALTY INC", None, OwnerClass.CORP),
    ("R110_individual", "JOHN SMITH", None, OwnerClass.INDIVIDUAL),
    ("R110_individual", "SMITH JOHN & MARY", None, OwnerClass.INDIVIDUAL),
    ("R110_individual", "JOHN SMITH ET AL", None, OwnerClass.INDIVIDUAL),
    ("R110_individual", "SMITH JOHN JTWROS", None, OwnerClass.INDIVIDUAL),
    ("R110_individual", "JO-ANN V TOBIN", None, OwnerClass.INDIVIDUAL),
    ("R110_individual", "FILS-AIME, KRISTY", None, OwnerClass.INDIVIDUAL),
    ("R999_unknown", "ACME REALTY", None, OwnerClass.UNKNOWN),
]


NEGATIVES: list[tuple[str, str, BuildingType | None]] = [
    ("R010_hdfc", "ABC REALTY CORP", None),
    ("R020_public", "CITYWIDE LLC", BuildingType.SFR_1_4),
    ("R020_public", "ADAR HOLDINGS USA LLC", BuildingType.SFR_1_4),
    ("R030_lender", "BANK STREET LLC", BuildingType.SFR_1_4),
    ("R030_lender", "PAN, FU NA", BuildingType.SFR_1_4),
    ("R040_nonprofit", "COLLEGE POINT LLC", BuildingType.SFR_1_4),
    ("R040_nonprofit", "1106 COLLEGE AVE HOU", BuildingType.SFR_1_4),
    ("R040_nonprofit", "52 CONVENT LLC", BuildingType.SFR_1_4),
    ("R050_estate", "REAL ESTATE VENTURES LLC", BuildingType.SFR_1_4),
    ("R050_estate", "ESTATE TRADER INC.", BuildingType.SFR_1_4),
    ("R060_trust", "JOHN SMITH", None),
    ("R070_coop_building", "EXAMPLE TENANTS CORP", BuildingType.SFR_1_4),
    ("R071_coop_name", "ABC REALTY CORP", BuildingType.SFR_1_4),
    ("R071_coop_name", "755 COOP CITY, LLC", BuildingType.CONDO_UNIT),
    ("R080_llc", "ABC REALTY INC", None),
    ("R090_partnership", "ABC REALTY INC", None),
    ("R100_corp", "123 MAIN ST LLC", BuildingType.SFR_1_4),
    ("R110_individual", "123 MAIN ST LLC", BuildingType.SFR_1_4),
]


def test_every_rule_has_a_positive_case() -> None:
    covered = {rule_id for rule_id, *_ in CASES}
    for rule in RULES:
        assert rule.rule_id in covered, f"missing positive case for {rule.rule_id}"


def test_positive_cases() -> None:
    for rule_id, raw, building_type, expected in CASES:
        owner = classify_owner(raw, building_type)
        assert owner.owner_class == expected, (rule_id, raw, owner)
        if raw != "" or expected is OwnerClass.UNKNOWN:
            assert owner.rule_id == rule_id, (raw, owner.rule_id, rule_id)


def test_negative_cases_do_not_fire_that_rule() -> None:
    for rule_id, raw, building_type in NEGATIVES:
        name = primary_owner_name(raw)
        rule = apply_rules(name, building_type)
        assert rule.rule_id != rule_id, (rule_id, raw, rule.rule_id)


def test_hdfc_beats_corp() -> None:
    assert classify_owner("HOUSING DEVELOPMENT FUND CORP").owner_class == OwnerClass.HDFC


def test_trust_beats_individual() -> None:
    owner = classify_owner("JOHN SMITH TRUSTEE OF SMITH TRUST")
    assert owner.owner_class == OwnerClass.TRUST
    assert owner.rule_id == "R060_trust"


def test_coop_building_not_counted_as_entity() -> None:
    owner = classify_owner("123 MAIN ST LLC", BuildingType.COOP_BUILDING)
    assert owner.owner_class == OwnerClass.COOP_CORP


def test_estate_suffix_does_not_treat_deft_as_estate() -> None:
    owner = classify_owner("SECURE REAL ESTATE CORP/DEFT")
    assert owner.rule_id != "R051_estate_suffix"
    assert owner.owner_class == OwnerClass.CORP


def test_usa_llc_is_not_public() -> None:
    assert classify_owner("ADAR HOLDINGS USA LLC").owner_class == OwnerClass.LLC


def test_fannie_mae_long_name_is_lender() -> None:
    owner = classify_owner("FEDERAL NATIONAL MORTGAGE ASSOCIATION")
    assert owner.owner_class == OwnerClass.LENDER_REO


def test_wrapped_trust_and_hdfc() -> None:
    assert classify_owner("VINCENT AND ROSALIE FRISONE REVOCABLE TR UST").owner_class == (
        OwnerClass.TRUST
    )
    assert (
        classify_owner("2080 BOSTON ROAD HOUSING DEVELOPMENT FUN D CORP").owner_class
        == OwnerClass.HDFC
    )


def test_condominium_is_not_an_individual() -> None:
    assert classify_owner("ELMWOOD PARK CONDOMINIUM").owner_class == OwnerClass.UNKNOWN


def test_limited_without_partnership_is_corp() -> None:
    assert classify_owner("JP REAL ESTATE GROUP LIMITED").owner_class == OwnerClass.CORP


def test_glued_corp_suffix() -> None:
    assert classify_owner("2426 GRAND OPERATINGCORP").owner_class == OwnerClass.CORP
