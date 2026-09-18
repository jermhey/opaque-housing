"""View-models for CSS bars and SVG sparklines. Pure; no I/O."""

from __future__ import annotations

from typing import Any

TYPE_LABELS: dict[str, str] = {
    "sfr_1_4": "1–4 family (harmonized)",
    "condo_unit": "Condo unit",
    "small_mf": "Small multifamily",
    "large_mf": "Large multifamily",
    "mixed_use_res": "Mixed-use residential",
    "coop_building": "Co-op building",
    "other_res": "Other residential",
}


def type_label(code: str) -> str:
    return TYPE_LABELS.get(code, code.replace("_", " "))


def _as_float(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _suppressed(row: dict[str, Any]) -> bool:
    flag = row.get("suppressed")
    return flag in {True, "true", "True", "TRUE"}


def mix_weight_bars(types: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Paired mix-weight bars for types that exist in either metro."""
    rows: list[dict[str, Any]] = []
    for item in types:
        reference = _as_float(item.get("reference_weight")) or 0.0
        other = _as_float(item.get("other_weight")) or 0.0
        if reference <= 0 and other <= 0:
            continue
        rows.append(
            {
                "building_type": str(item.get("building_type") or ""),
                "label": type_label(str(item.get("building_type") or "")),
                "reference": reference,
                "other": other,
                "reference_width": reference * 100,
                "other_width": other * 100,
            }
        )
    return rows


def ranked_share_bars(
    rows: list[dict[str, Any]],
    *,
    label_keys: tuple[str, ...] = ("nta_name", "nta", "geo_neighborhood"),
    value_key: str = "entity_parcel_share",
    limit: int = 12,
) -> list[dict[str, Any]]:
    ranked: list[tuple[str, float]] = []
    for row in rows:
        if _suppressed(row):
            continue
        value = _as_float(row.get(value_key))
        if value is None:
            continue
        label = ""
        for key in label_keys:
            raw = row.get(key)
            if raw:
                label = str(raw)
                break
        if not label:
            continue
        ranked.append((label, value))
    ranked.sort(key=lambda item: item[1], reverse=True)
    top = ranked[:limit]
    scale = top[0][1] if top and top[0][1] > 0 else 1.0
    return [
        {
            "label": label,
            "value": value,
            "width": (value / scale) * 100,
        }
        for label, value in top
    ]


def year_sparkline(
    rows: list[dict[str, Any]],
    *,
    x_key: str = "year",
    y_key: str = "sale_share",
    width: int = 480,
    height: int = 120,
) -> dict[str, Any] | None:
    points: list[tuple[float, float]] = []
    for row in rows:
        year = _as_float(row.get(x_key))
        share = _as_float(row.get(y_key))
        if year is None or share is None:
            continue
        points.append((year, share))
    if len(points) < 2:
        return None
    xs = [item[0] for item in points]
    ys = [item[1] for item in points]
    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(ys), max(ys)
    if ymax <= ymin:
        ymax = ymin + 1e-9
    pad_x, pad_y = 8.0, 12.0
    inner_w = width - pad_x * 2
    inner_h = height - pad_y * 2
    span_x = xmax - xmin or 1.0
    span_y = ymax - ymin

    def sx(year: float) -> float:
        return pad_x + ((year - xmin) / span_x) * inner_w

    def sy(share: float) -> float:
        return pad_y + (1.0 - (share - ymin) / span_y) * inner_h

    coords = [(sx(year), sy(share)) for year, share in points]
    path = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in coords)
    return {
        "width": width,
        "height": height,
        "path": path,
        "first_year": int(xs[0]),
        "last_year": int(xs[-1]),
        "start": ys[0],
        "end": ys[-1],
        "min": ymin,
        "max": ymax,
    }
