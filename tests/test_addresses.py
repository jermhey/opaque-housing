from opaque_housing.normalize.addresses import address_key, is_care_of, normalize_address


def test_normalize_drops_care_of_and_punct() -> None:
    assert normalize_address("c/o Corp. Service Co.", "251 Little Falls Dr.") == (
        "CORP SERVICE CO 251 LITTLE FALLS DR"
    )
    assert is_care_of("C/O CORPORATION SERVICE COMPANY")
    assert not is_care_of("10 SAMPLE ROAD")


def test_empty_address_has_no_key() -> None:
    assert normalize_address("", None) == ""
    assert address_key("") == ""
    assert address_key("10 SAMPLE ROAD BROOKLYN NY 11201")
