"""Pure inert request encoding. No pipe or server import side effects."""
from __future__ import annotations
import math
import re
from decimal import Decimal, InvalidOperation
from typing import Any

LEGACY_SIDES = {-1: "ALL", 0: "NEUTRAL", 1: "EAST", 2: "WEST", 3: "GUER", 4: "CIV", 5: "AMBIENT"}
CONFIG_SIDES = {-1: "AMBIENT", 0: "EAST", 1: "WEST", 2: "GUER", 3: "CIV", 4: "NEUTRAL", 5: "ENEMY", 6: "FRIENDLY", 7: "LOGIC", 8: "EMPTY", 9: "AMBIENT"}
DECIMAL_NUMBER = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?\Z")


def normalize_number(value: Any, label: str, integer_only: bool = False,
                     minimum: int | float = -1e30, maximum: int | float = 1e30) -> int | float:
    """Validate expected numeric fields without coercing deliberate strings elsewhere.

    Decimal comparison precedes float conversion so fractional ID strings cannot
    round to a different integer. SQF uses single precision; integer IDs are
    deliberately bounded to 0..16777215 by the caller.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError(f"{label} must be a number or numeric string")
    if isinstance(value, str) and not DECIMAL_NUMBER.fullmatch(value):
        raise ValueError(f"{label} must be a complete decimal numeric value")
    try:
        exact = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f"{label} must be a complete decimal numeric value") from exc
    if not exact.is_finite():
        raise ValueError(f"{label} must be finite")
    if not Decimal(str(minimum)) <= exact <= Decimal(str(maximum)):
        raise ValueError(f"{label} must be in [{minimum},{maximum}]")
    if integer_only:
        if exact != exact.to_integral_value():
            raise ValueError(f"{label} must be an integer")
        return int(exact)
    return float(exact)

def normalize_catalog_side(value: str | int) -> str:
    """Names are preferred; integer aliases retain the documented legacy meanings."""
    if isinstance(value, bool):
        raise ValueError("filter_side must be a side name or legacy integer")
    if isinstance(value, int):
        if value not in LEGACY_SIDES:
            raise ValueError("filter_side legacy integer must be -1..5")
        return LEGACY_SIDES[value]
    if isinstance(value, str):
        name = value.upper()
        if name in set(CONFIG_SIDES.values()) | {"ALL", "UNKNOWN"}:
            return name
        # Older wire clients sent quoted integer aliases; never parse a prefix.
        if DECIMAL_NUMBER.fullmatch(value):
            legacy = normalize_number(value, "filter_side", True, -1, 5)
            return LEGACY_SIDES[legacy]
    raise ValueError("filter_side must be ALL, EAST, WEST, GUER, CIV, NEUTRAL, ENEMY, FRIENDLY, LOGIC, EMPTY, AMBIENT or UNKNOWN")

def sqf_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        if not -3.4028234663852886e38 <= value <= 3.4028234663852886e38:
            raise ValueError("wire numbers must be finite and within SQF scalar range")
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("wire numbers must be finite")
        return str(value)
    if isinstance(value, str):
        # Newline-delimited inert SQF has no lossless control-character escape.
        # Reject instead of silently changing text or accepting malformed numeric
        # strings (e.g. "1\n" becoming entity/attribute value 1).
        if any(ord(ch) < 0x20 and ch != "\t" for ch in value):
            raise ValueError("Request strings cannot contain CR/LF or other control characters; use single-line text")
        return '"' + value.replace('"', '""') + '"'
    if isinstance(value, list):
        return "[" + ",".join(sqf_value(item) for item in value) + "]"
    raise TypeError(f"Unsupported SQF wire value: {type(value).__name__}")

def build_sqf_payload(command: dict, request_id: str) -> bytes:
    parts = [sqf_value(request_id), sqf_value(command["cmd"])]
    for key, value in command.items():
        if key not in ("cmd", "id"):
            parts.extend([sqf_value(key), sqf_value(value)])
    return ("[" + ",".join(parts) + "]\n").encode("utf-8")
