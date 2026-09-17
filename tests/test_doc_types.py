from opaque_housing.adapters.nyc.doc_types import (
    SALE_DEED_CODES,
    assert_sale_codes_are_official,
    canonical_doc_type,
    conveyance_codes,
)
from opaque_housing.schema import DocTypeCanonical


def test_sale_codes_are_in_official_conveyance_class() -> None:
    assert_sale_codes_are_official()
    official = conveyance_codes()
    assert SALE_DEED_CODES <= official


def test_each_sale_code_maps_to_sale_deed() -> None:
    for code in SALE_DEED_CODES:
        assert canonical_doc_type(code) is DocTypeCanonical.SALE_DEED


def test_correction_and_confirmatory_are_nonsale() -> None:
    for code in ("CORRD", "CONDEED", "DEED COR", "TODD", "IDED", "DEED, LE", "DEED, TS"):
        assert canonical_doc_type(code) is DocTypeCanonical.NONSALE_DEED, code


def test_contract_lease_easement_declaration_are_nonsale() -> None:
    for code in ("CNTR", "EASE", "LEAS", "CDEC", "AIRRIGHT", "DEVR"):
        assert canonical_doc_type(code) is DocTypeCanonical.NONSALE_DEED, code


def test_mortgage_and_unknown_are_other() -> None:
    assert canonical_doc_type("MTGE") is DocTypeCanonical.OTHER
    assert canonical_doc_type("NOT_A_REAL_CODE") is DocTypeCanonical.OTHER
    assert canonical_doc_type("") is DocTypeCanonical.OTHER
    assert canonical_doc_type(None) is DocTypeCanonical.OTHER
