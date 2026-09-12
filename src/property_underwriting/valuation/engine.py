from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from datetime import date
from hashlib import sha256
import json
import math
from statistics import median

from .evidence import basic_exclusions, deduplicate, normalize_comp
from .models import ValuationConfig, day, number


def weighted_quantile(values, weights, fraction):
    if not values or len(values) != len(weights) or not 0 <= fraction <= 1:
        raise ValueError("Invalid weighted sample")
    pairs = sorted(zip(values, weights))
    if any(not math.isfinite(v) or not math.isfinite(w) or w <= 0 for v, w in pairs):
        raise ValueError("Finite values and positive weights required")
    total = sum(w for v, w in pairs)
    points, cumulative = [], 0
    for value, weight in pairs:
        points.append(((cumulative + weight/2) / total, value))
        cumulative += weight
    if fraction <= points[0][0]:
        return points[0][1]
    for (a, x), (b, y) in zip(points, points[1:]):
        if fraction <= b:
            return x + (y-x) * (fraction-a)/(b-a)
    return points[-1][1]


def comp_tier(comp, subject, as_of, config):
    age = (as_of - day(comp["sale_date"])).days
    ratio = abs(comp["living_sqft"] / subject["living_sqft"] - 1)
    comp["differences"] = dict(recency_days=age, sqft_fraction=ratio,
                               beds=abs(comp["beds"]-subject["beds"]), baths=abs(comp["baths"]-subject["baths"]),
                               year_built=abs(comp["year_built"]-subject["year_built"]) if comp["year_built"] is not None else None)
    for index, tier in enumerate(config.tiers):
        delta = comp["differences"]
        if comp["raw_record"].get("cross_submarket") is True and index != len(config.tiers)-1:
            continue
        if (comp["distance_miles"] <= tier.distance_miles and age <= tier.recency_days and ratio <= tier.sqft_tolerance
                and delta["beds"] <= tier.bed_difference and delta["baths"] <= tier.bath_difference
                and (delta["year_built"] is None or delta["year_built"] <= tier.year_built_tolerance)):
            return index, tier.name
    last = config.tiers[-1]
    reasons = []
    for key, limit in (("recency_days", last.recency_days), ("sqft_fraction", last.sqft_tolerance),
                       ("beds", last.bed_difference), ("baths", last.bath_difference), ("year_built", last.year_built_tolerance)):
        if comp["differences"][key] is not None and comp["differences"][key] > limit:
            reasons.append(key.upper() + "_OUTSIDE_MAX_TIER")
    if comp["distance_miles"] > last.distance_miles:
        reasons.append("DISTANCE_OUTSIDE_MAX_TIER")
    comp["exclusions"] += reasons or ["NO_COMPATIBLE_TIER"]
    return None, None


def similarity(comp, subject, config):
    limits = config.tiers[-1]
    delta = comp["differences"]
    taper = lambda value, maximum: max(0, 1-value/maximum) if value is not None else None
    classification = comp["condition"]["classification"]
    condition = {"RENOVATED_COMP": 1, "AVERAGE_MARKET_COMP": .55, "UNKNOWN_CONDITION": .20}.get(classification, 0)
    renovation = 1 if comp["condition"]["target_compatible"] else .35 if classification == "RENOVATED_COMP" else .15
    lot = None
    if comp["lot_size_sqft"] and comp["lot_size_sqft"] > 0 and subject.get("lot_size_sqft"):
        lot = min(comp["lot_size_sqft"], subject["lot_size_sqft"]) / max(comp["lot_size_sqft"], subject["lot_size_sqft"])
    scores = dict(distance=taper(comp["distance_miles"], limits.distance_miles), recency=taper(delta["recency_days"], limits.recency_days),
                  sqft=taper(delta["sqft_fraction"], limits.sqft_tolerance), beds=taper(delta["beds"], limits.bed_difference+1),
                  baths=taper(delta["baths"], limits.bath_difference+1), year_built=taper(delta["year_built"], limits.year_built_tolerance),
                  lot_size=lot, condition=condition, renovation=renovation)
    contributions = {k: config.weights[k] * (v if v is not None else 0) for k, v in scores.items()}
    # Global compatibility multipliers keep numerous unknown-condition records from
    # overwhelming the renovated condition evidence through other good attributes.
    compatibility = 1 if comp["condition"]["target_compatible"] else .50 if classification == "AVERAGE_MARKET_COMP" else .25
    geography = .5 if comp["raw_record"].get("cross_submarket") is True else 1
    comp.update(similarity_subscores=scores, similarity_contributions=contributions,
                similarity_score=sum(contributions.values()), condition_weight_multiplier=compatibility,
                geography_weight_multiplier=geography,
                similarity_weight=max(.001, sum(contributions.values()) * compatibility * geography),
                missing_attributes=[k for k, v in scores.items() if v is None])


def value_property(subject, comp_records, *, valuation_date, config=None, avm=None, provider_status=None):
    config = config or ValuationConfig()
    as_of = day(valuation_date)
    if as_of is None:
        raise ValueError("Explicit valuation date required")
    if not subject.get("living_sqft") or subject["living_sqft"] <= 0:
        raise ValueError("Authoritative subject area required")
    normalized = [normalize_comp(r, subject, as_of) for r in comp_records]
    id_properties = {}
    for comp in normalized:
        id_properties.setdefault(comp["comp_id"], set()).add(comp["property_key"])
    rejected, viable = [], []
    for comp in normalized:
        comp["exclusions"] = basic_exclusions(comp, subject, as_of)
        if len(id_properties[comp["comp_id"]]) > 1:
            comp["exclusions"].append("AMBIGUOUS_COMP_ID_ACROSS_PROPERTIES")
        (rejected if comp["exclusions"] else viable).append(comp)
    canonical, duplicates = deduplicate(viable)
    candidates = []
    for comp in canonical:
        if comp["exclusions"]:
            rejected.append(comp)
            continue
        index, tier = comp_tier(comp, subject, as_of, config)
        if index is None:
            rejected.append(comp)
            continue
        comp["tier_index"], comp["selection_tier"] = index, tier
        similarity(comp, subject, config)
        candidates.append(comp)
    selected, tier_history = [], []
    for index, tier in enumerate(config.tiers):
        pool = [c for c in candidates if c["tier_index"] <= index]
        pool.sort(key=lambda c: (not c["condition"]["target_compatible"], -c["similarity_weight"], c["comp_id"]))
        selected = pool[:config.max_comps]
        compatible_count = sum(c["condition"]["target_compatible"] for c in selected)
        tier_history.append(dict(tier=tier.name, eligible_count=len(pool), compatible_count=compatible_count,
                                 reason="Expand only if minimum sale/condition support not met"))
        if len(selected) >= config.min_comps and compatible_count >= config.min_compatible_comps:
            break
    selected_ids = {c["comp_id"] for c in selected}
    for c in candidates:
        if c["comp_id"] not in selected_ids:
            c["exclusions"].append("NARROWER_SUFFICIENT_SET_OR_CONFIGURED_LIMIT")
            rejected.append(c)
    logs = [math.log(c["price_per_sqft"]) for c in selected]
    center = median(logs) if logs else 0
    mad = median([abs(v-center) for v in logs]) if logs else 0
    for c, value in zip(selected, logs):
        extreme = (abs(value-center) > config.outlier_mad_multiple * 1.4826 * mad if mad > 1e-9
                   else abs(value-center) > math.log(config.outlier_zero_mad_ratio))
        flagged = len(selected) >= 3 and extreme
        c["outlier"] = dict(flagged=flagged, method="LOG_PPSF_MAD_OR_ZERO_MAD_RATIO", log_median=center, log_mad=mad,
                             effect="DOWNWEIGHT_NOT_DELETE" if flagged else "NONE")
        c["final_weight"] = c["similarity_weight"] * (config.outlier_weight_multiplier if flagged else 1)
        c["selection_reason"] = "Accepted closed sale in tier " + c["selection_tier"] + "; explicit property/geography/time/condition subscores retained"
    compatible = [c for c in selected if c["condition"]["target_compatible"]]
    total_weight = sum(c["final_weight"] for c in selected)
    compatible_share = sum(c["final_weight"] for c in compatible)/total_weight if total_weight else 0
    sufficient = len(selected) >= config.min_comps and len(compatible) >= config.min_compatible_comps and compatible_share >= config.min_compatible_weight_share
    ppsf, primary = None, None
    if selected:
        values, weights = [c["price_per_sqft"] for c in selected], [c["final_weight"] for c in selected]
        ppsf = dict(method="ROBUST_PPSF_CROSS_CHECK_NOT_PRIMARY", comp_ids=[c["comp_id"] for c in selected],
                    median=median(values), weighted_median=weighted_quantile(values, weights, .5),
                    low=weighted_quantile(values, weights, .25), high=weighted_quantile(values, weights, .75),
                    subject_area_reference=subject["living_sqft"], subject_equivalent_base=weighted_quantile(values, weights, .5)*subject["living_sqft"],
                    area_basis_warning="Assessor reported grade unspecified; comp area definitions may differ. No basement allocation inferred.")
    if sufficient:
        values, weights = [c["sale_price"] for c in selected], [c["final_weight"] for c in selected]
        base = weighted_quantile(values, weights, .5)
        low = min(base, weighted_quantile(values, weights, .25))
        high = max(base, weighted_quantile([c["sale_price"] for c in compatible], [c["final_weight"] for c in compatible], .75))
        primary = dict(method="SIMILARITY_WEIGHTED_COMP_VALUE", statistic="Weighted midpoint-interpolated sale-price quantiles",
                       conservative=round(low), base=round(base), upside=round(high), comp_ids=[c["comp_id"] for c in selected],
                       upside_condition_comp_ids=[c["comp_id"] for c in compatible], unsupported_dollar_adjustments=[],
                       scenario_not_confidence_interval=True, value_basis="UNADJUSTED_CLOSE_COMPARABLE_SALE_PRICES")
    conflicts = []
    benchmark = deepcopy(avm) if avm else dict(status="NOT_AVAILABLE", estimate=None)
    benchmark["role"] = "EXTERNAL_AVM_BENCHMARK"
    avm_number = number(benchmark.get("estimate"))
    avm_date = day(benchmark.get("retrieved_at"))
    if avm and (not benchmark.get("source_id") or not benchmark.get("provider") or avm_date is None or avm_date > as_of or avm_number is None or avm_number <= 0):
        benchmark["status"] = "REJECTED_INVALID_OR_FUTURE_BENCHMARK"
    elif avm:
        benchmark["status"] = "AVAILABLE"
    if primary and benchmark["status"] == "AVAILABLE":
        fraction = abs(avm_number-primary["base"])/primary["base"]
        benchmark["disagreement_fraction"] = fraction
        if fraction > config.avm_disagreement_fraction:
            conflicts.append("AVM_DISAGREEMENT_NOT_AVERAGED_AWAY")
    if primary and abs(ppsf["subject_equivalent_base"]-primary["base"])/primary["base"] > .20:
        conflicts.append("PPSF_CROSS_CHECK_DISAGREEMENT")
    dispersion = (ppsf["high"]-ppsf["low"])/ppsf["weighted_median"] if ppsf else None
    confidence = "INSUFFICIENT" if not primary else "LOW"
    if primary and len(selected) >= 5 and len(compatible) >= 3 and compatible_share >= .8 and dispersion <= .25 and not conflicts and all(c["selection_tier"] == "A" and not c["missing_attributes"] and not c["warnings"] and c["source"].get("evidence_level") in {"A", "B", "C"} for c in selected):
        confidence = "MEDIUM"
    return dict(contract_version="engine4-sale-valuation-0.1.0", subject=deepcopy(subject), valuation_date=as_of.isoformat(),
                valuation_purpose="AFTER_REPAIR_VALUE", current_subject_condition=subject.get("current_condition"),
                after_repair_target_condition=subject.get("after_repair_target_condition"),
                config=asdict(config), config_calibration="EXPLICIT_MVP_POLICY_NOT_STATISTICALLY_CALIBRATED",
                provider_status=provider_status or {"status": "NOT_CONFIGURED", "live_calls": 0},
                candidate_comp_count=len(normalized), accepted_comp_count=len(selected), rejected_comp_count=len(rejected),
                duplicate_occurrence_count=len(duplicates), condition_compatible_comp_count=len(compatible),
                accepted_comps=selected, rejected_comps=rejected, duplicate_occurrences=duplicates,
                selection_tier_history=tier_history, primary_valuation=primary, ppsf_cross_check=ppsf,
                external_avm_benchmark=benchmark, valuation_conflicts=conflicts,
                ARV_CONSERVATIVE=primary["conservative"] if primary else None,
                ARV_BASE=primary["base"] if primary else None, ARV_UPSIDE=primary["upside"] if primary else None,
                ARV_CONFIDENCE=confidence, confidence_factors=dict(accepted_count=len(selected), condition_compatible_count=len(compatible),
                    compatible_weight_share=compatible_share, ppsf_dispersion=dispersion, avm_disagreement=bool(conflicts),
                    missing_attribute_count=sum(len(c["missing_attributes"]) for c in selected),
                    explanation="Minimum 3 sales, 2 target-compatible and 60% compatible weight for any range. Small/broad/uncertain sets LOW; tightly supported sets may be MEDIUM; no calibrated HIGH claim."),
                status=dict(COMP_SET_STATUS="READY" if sufficient else "PARTIAL" if selected else "INSUFFICIENT",
                            ENGINE4_ARCHITECTURE="READY", ENGINE4_MVP="READY TO FREEZE", ENGINE5_RENT_HCV_DEVELOPMENT="READY",
                            FULL_UNDERWRITING_INTEGRATION="NOT_READY"),
                limitations=["ARV assumes ordinary rental-ready/functionally renovated visible condition, not an assessment of current condition",
                             "No addition, finished basement, luxury upgrade or structural redevelopment assumed",
                             "Engine 3 partial allowance is never an ARV input and does not certify full rehab pricing",
                             "Hidden systems unknown; hypothetical target is not a current habitability or repair-cost certification",
                             "Insufficient sales/condition evidence yields no ARV; synthetic tests are not market observations",
                             "This valuation module does not make an acquisition recommendation"])
