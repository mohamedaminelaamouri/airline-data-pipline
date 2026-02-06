from __future__ import annotations

REQUIRED_RAW_COLUMNS: set[str] = {
    "year",
    "month",
    "carrier",
    "airport",
    "arr_flights",
    "arr_del15",
}


def validate_required_columns(columns: list[str]) -> None:
    missing = sorted(REQUIRED_RAW_COLUMNS.difference(set(columns)))
    if missing:
        raise ValueError("Missing required columns: " + ", ".join(missing))
