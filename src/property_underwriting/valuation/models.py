from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
import math


@dataclass(frozen=True)
class Tier:
    name: str
    distance_miles: float
    recency_days: int
    sqft_tolerance: float
    bed_difference: float
    bath_difference: float
    year_built_tolerance: int


@dataclass(frozen=True)
class ValuationConfig:
    tiers: tuple[Tier, ...] = (Tier("A", .75, 180, .25, 1, .5, 40),
                              Tier("B", 1.5, 365, .40, 1, 1, 60),
                              Tier("C", 3, 540, .50, 2, 1, 80))
    weights: dict[str, float] = field(default_factory=lambda: dict(
        distance=.15, recency=.15, sqft=.20, beds=.10, baths=.10,
        year_built=.05, lot_size=.05, condition=.10, renovation=.10))
    min_comps: int = 3
    min_compatible_comps: int = 2
    max_comps: int = 8
    min_compatible_weight_share: float = .60
    avm_disagreement_fraction: float = .20
    outlier_mad_multiple: float = 3.5
    outlier_zero_mad_ratio: float = 1.6
    outlier_weight_multiplier: float = .25

    def __post_init__(self):
        required = {"distance", "recency", "sqft", "beds", "baths", "year_built", "lot_size", "condition", "renovation"}
        if set(self.weights) != required or any(not math.isfinite(v) or v < 0 for v in self.weights.values()) or not math.isclose(sum(self.weights.values()), 1):
            raise ValueError("Use documented nonnegative similarity weights summing to one")
        if not 2 <= self.min_comps <= self.max_comps or not 1 <= self.min_compatible_comps <= self.min_comps:
            raise ValueError("Invalid sufficiency counts")
        if not 0 < self.min_compatible_weight_share <= 1 or not 0 < self.outlier_weight_multiplier <= 1:
            raise ValueError("Invalid weight limits")
        if not self.tiers or len({t.name for t in self.tiers}) != len(self.tiers):
            raise ValueError("Unique ordered tiers required")
        previous = None
        for t in self.tiers:
            values = [v for k, v in asdict(t).items() if k != "name"]
            if any(isinstance(v, bool) or not math.isfinite(v) or v <= 0 for v in values):
                raise ValueError("Tier limits must be positive finite values")
            if previous and any(a > b for a, b in zip(previous, values)):
                raise ValueError("Tiers may expand, not narrow")
            previous = values


def number(value):
    if isinstance(value, bool) or value is None or value == "":
        return None
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (ValueError, TypeError):
        return None


def day(value):
    try:
        return date.fromisoformat(str(value)[:10]) if value else None
    except ValueError:
        return None
