from opaque_housing.adapters.arcgis import next_page_size


def test_full_requested_page_continues() -> None:
    assert next_page_size(2000, 2000, None, first_page=True) == 2000
    assert next_page_size(2000, 2000, True, first_page=False) == 2000


def test_server_cap_on_first_page_is_not_eof() -> None:
    assert next_page_size(1000, 2000, None, first_page=True) == 1000


def test_short_later_page_is_eof() -> None:
    assert next_page_size(689, 1000, None, first_page=False) is None


def test_explicit_false_flag_stops_on_short_page() -> None:
    assert next_page_size(500, 2000, False, first_page=True) == 500
    assert next_page_size(500, 2000, False, first_page=False) is None


def test_empty_page_stops() -> None:
    assert next_page_size(0, 2000, None, first_page=True) is None
