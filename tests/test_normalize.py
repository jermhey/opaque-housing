from opaque_housing.normalize.names import (
    normalize_name,
    owner_key,
    primary_owner_name,
    split_owner_names,
)


def test_llc_spellings_collapse() -> None:
    assert normalize_name("123 Main St L.L.C.") == "123 MAIN ST LLC"
    assert normalize_name("123 MAIN ST L L C") == "123 MAIN ST LLC"
    assert normalize_name("123 MAIN LIMITED LIABILITY CO") == "123 MAIN LLC"


def test_trust_tokens() -> None:
    assert "TRUSTEE" in normalize_name("JOHN SMITH TTEE")
    assert normalize_name("SMITH FAMILY TRST") == "SMITH FAMILY TRUST"


def test_owner_key_stable() -> None:
    assert owner_key("ACME LLC") == owner_key("ACME LLC")
    assert owner_key("ACME LLC") != owner_key("ACME INC")


def test_split_on_slash_not_ampersand() -> None:
    assert split_owner_names("SMITH JOHN & MARY") == ["SMITH JOHN & MARY"]
    assert split_owner_names("ACME LLC / JONES JOHN") == ["ACME LLC", "JONES JOHN"]
    assert primary_owner_name("Acme LLC / Jones John") == "ACME LLC"


def test_later_slash_parts_estate_tokens() -> None:
    from opaque_housing.normalize.names import later_parts_estate_evidence, normalize_name

    parts = split_owner_names(normalize_name("BUZ, FREDERICK H/LWT/DEF"))
    assert later_parts_estate_evidence(parts)
    deft = split_owner_names(normalize_name("SECURE REAL ESTATE CORP/DEFT"))
    assert not later_parts_estate_evidence(deft)
