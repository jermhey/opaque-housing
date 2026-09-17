"""Borough / block / lot → 10-digit BBL. Verified PLUTO/ACRIS/PAD fields only."""

from __future__ import annotations


def format_bbl_parts(borough: object, block: object, lot: object) -> str:
    """Join official 1-5-4 boro/block/lot parts into a 10-digit BBL string."""
    if borough is None or block is None or lot is None:
        return ""
    boro_text = str(borough).strip()
    block_text = str(block).strip()
    lot_text = str(lot).strip()
    if not boro_text or not block_text or not lot_text:
        return ""
    try:
        boro = int(float(boro_text))
        blk = int(float(block_text))
        lt = int(float(lot_text))
    except ValueError:
        return ""
    if boro <= 0 or blk < 0 or lt < 0:
        return ""
    return f"{boro}{blk:05d}{lt:04d}"
