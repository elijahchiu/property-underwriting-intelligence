from __future__ import annotations

import hashlib
import json
from decimal import Decimal, ROUND_HALF_UP


def stable_id(prefix: str, value: object) -> str:
    return prefix + hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()[:16]


def decimal(value: object) -> Decimal:
    if isinstance(value, bool):
        raise ValueError("Boolean is not a quantity or money")
    result = Decimal(str(value))
    if not result.is_finite():
        raise ValueError("Nonfinite quantity or money")
    return result


def cents(value: object) -> int:
    value = decimal(value)
    if value < 0:
        raise ValueError("Negative cost")
    return int((value * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def dollars(value: int | None) -> float | None:
    return None if value is None else float(Decimal(value) / 100)


def median(values: list[int]) -> int:
    values = sorted(values)
    n = len(values)
    if not n:
        raise ValueError("No observations")
    return int((Decimal(values[(n - 1) // 2]) + values[n // 2]).__truediv__(2)
               .quantize(Decimal(1), rounding=ROUND_HALF_UP))


def cost_range(low: int, base: int, high: int) -> dict:
    if any(isinstance(v, bool) or not isinstance(v, int) for v in (low, base, high)):
        raise ValueError("Monetary ranges require integer USD cents")
    if not 0 <= low <= base <= high:
        raise ValueError("Invalid cost range")
    return {"low": low, "base": base, "high": high}


def add_ranges(ranges: list[dict]) -> dict:
    return {key: sum(r[key] for r in ranges) for key in ("low", "base", "high")}
