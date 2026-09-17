from opaque_housing.adapters.soda import _page_frame


def test_page_frame_coerces_mixed_json_types() -> None:
    frame = _page_frame(
        [
            {"document_id": 2003010100000001, "document_amt": 0},
            {"document_id": "2002122700120001", "document_amt": "500000.0"},
        ]
    )
    assert frame["document_id"].dtype == frame["document_amt"].dtype
    assert set(frame["document_id"].to_list()) == {"2003010100000001", "2002122700120001"}
