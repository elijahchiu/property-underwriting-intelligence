from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import math
import re

from .models import day, number


CONDITIONS = {"RENOVATED_COMP", "AVERAGE_MARKET_COMP", "DISTRESSED_COMP", "UNKNOWN_CONDITION"}


def address_key(address, state):
    text = re.sub(r"[^A-Z0-9 ]", " ", (address or "").upper())
    aliases = {"AVENUE": "AVE", "STREET": "ST", "ROAD": "RD", "BOULEVARD": "BLVD", "DRIVE": "DR", "LANE": "LN"}
    return " ".join(aliases.get(x, x) for x in text.split()) + "|" + (state or "").upper()


def distance_miles(lat1, lon1, lat2, lon2):
    vals = [number(v) for v in (lat1, lon1, lat2, lon2)]
    if any(v is None for v in vals) or not all(-90 <= v <= 90 for v in (vals[0], vals[2])) or not all(-180 <= v <= 180 for v in (vals[1], vals[3])):
        return None
    a, b, c, d = map(math.radians, vals)
    h = math.sin((c-a)/2)**2 + math.cos(a)*math.cos(c)*math.sin((d-b)/2)**2
    return 3958.7613 * 2 * math.asin(min(1, math.sqrt(h)))


def condition_evidence(raw, as_of):
    evidence = deepcopy(raw.get("condition_evidence") or {})
    classification = evidence.get("classification", "UNKNOWN_CONDITION")
    valid = (classification in CONDITIONS and evidence.get("review_status") == "REVIEWED"
             and evidence.get("source_reference") and evidence.get("evidence_text")
             and evidence.get("basis") in {"MANUAL_REVIEW", "REVIEWED_LISTING_REMARKS", "VERIFIED_PHOTO_REVIEW", "STRUCTURED_PROFESSIONAL_REVIEW"}
             and day(evidence.get("available_at")) is not None and day(evidence["available_at"]) <= as_of
             and day(evidence.get("effective_date")) is not None and day(raw.get("sale_date")) is not None
             and day(evidence["effective_date"]) <= day(raw["sale_date"]))
    if not valid:
        classification = "UNKNOWN_CONDITION"
    quality = evidence.get("renovation_quality") if valid else None
    compatible = classification == "RENOVATED_COMP" and quality in {"STANDARD", "FUNCTIONALLY_RENOVATED", "RENTAL_READY"}
    return dict(classification=classification, target_compatible=compatible, renovation_quality=quality,
                raw_evidence=evidence, evidence_confidence=evidence.get("confidence", "UNKNOWN") if valid else "UNKNOWN",
                basis="EXPLICIT_SOURCE_REVIEW" if valid else "NO_ADMITTED_CONDITION_EVIDENCE",
                not_inferred_from_price=True)


def normalize_comp(raw: dict, subject: dict, as_of) -> dict:
    source = deepcopy(raw.get("source") or {})
    record = deepcopy(raw)
    comp_id = str(raw.get("comp_id") or "comp-" + sha256(json.dumps(raw, sort_keys=True).encode()).hexdigest()[:16])
    price, sqft = number(raw.get("sale_price")), number(raw.get("living_sqft"))
    classification = condition_evidence(raw, as_of)
    return dict(comp_id=comp_id, address=raw.get("address"), state=raw.get("state"), county_fips=raw.get("county_fips"),
                property_key=address_key(raw.get("address"), raw.get("state")),
                latitude=number(raw.get("latitude")), longitude=number(raw.get("longitude")),
                distance_miles=distance_miles(subject.get("latitude"), subject.get("longitude"), raw.get("latitude"), raw.get("longitude")),
                provider_reported_distance=raw.get("distance_miles"),
                sale_price=price, sale_date=day(raw.get("sale_date")).isoformat() if day(raw.get("sale_date")) else None, living_sqft=sqft,
                beds=number(raw.get("beds")), baths=number(raw.get("baths")), year_built=number(raw.get("year_built")),
                property_type=raw.get("property_type"), lot_size_sqft=number(raw.get("lot_size_sqft")),
                price_per_sqft=price/sqft if price is not None and price > 0 and sqft is not None and sqft > 0 else None,
                retrieved_date=source.get("retrieved_at"), available_at=source.get("available_at"),
                source=source, condition=classification, renovation_evidence=classification["raw_evidence"],
                listing_sale_metadata=deepcopy(raw.get("listing_sale_metadata", {})), raw_record=record,
                source_occurrences=[dict(comp_id=comp_id, source=source, raw_record=record)],
                exclusions=[], warnings=[], adjusted_value=None, dollar_adjustments=[])


def basic_exclusions(comp, subject, as_of):
    reasons = []
    raw = comp["raw_record"]
    if not comp["address"] or not comp["source"].get("source_id"):
        reasons.append("MISSING_PROPERTY_IDENTITY_OR_SOURCE")
    if comp["property_key"] == address_key(subject["address"], subject["state"]):
        reasons.append("SUBJECT_IS_NOT_A_COMPARABLE")
    if comp["state"] != subject["state"]:
        reasons.append("STATE_MISMATCH")
    if comp["county_fips"] != subject["county_fips"]:
        reasons.append("COUNTY_UNCONFIRMED_OR_DIFFERENT_SUBMARKET")
    if comp["distance_miles"] is None:
        reasons.append("MISSING_VALID_SUBJECT_RELATIVE_GEOGRAPHY")
    if comp["property_type"] != subject["property_type"]:
        reasons.append("PROPERTY_TYPE_MISMATCH")
    if raw.get("status") != "SOLD" or raw.get("sale_price_basis") not in {"CLOSED_SALE", "RECORDED_SALE", "MLS_SOLD_PRICE"}:
        reasons.append("NOT_CONFIRMED_CLOSED_SALE_PRICE")
    if comp["sale_price"] is None or comp["sale_price"] <= 0:
        reasons.append("MISSING_OR_INVALID_SALE_PRICE")
    sale = day(comp["sale_date"])
    if sale is None:
        reasons.append("MISSING_OR_INVALID_SALE_DATE")
    elif sale > as_of:
        reasons.append("FUTURE_SALE")
    available, retrieved = day(comp["available_at"]), day(comp["retrieved_date"])
    if available is None or retrieved is None:
        reasons.append("MISSING_KNOWLEDGE_DATES")
    elif available > as_of or retrieved > as_of:
        reasons.append("EVIDENCE_NOT_AVAILABLE_AS_OF_VALUATION")
    elif sale and available < sale:
        reasons.append("EVIDENCE_PREDATES_CLOSED_SALE")
    if comp["living_sqft"] is None or comp["living_sqft"] <= 0:
        reasons.append("MISSING_OR_INVALID_LIVING_AREA")
    for key in ("beds", "baths"):
        if comp[key] is None or comp[key] < 0:
            reasons.append("MISSING_OR_INVALID_" + key.upper())
    if raw.get("arms_length") is False:
        reasons.append("NON_ARMS_LENGTH")
    if raw.get("arms_length") is None:
        comp["warnings"].append("ARMS_LENGTH_UNKNOWN")
    for flag in ("teardown", "land_sale", "redevelopment", "luxury"):
        if raw.get(flag) is True:
            reasons.append(flag.upper() + "_NOT_TARGET_SCENARIO")
    if comp["condition"]["renovation_quality"] == "LUXURY":
        reasons.append("LUXURY_NOT_TARGET_SCENARIO")
    if comp["condition"]["classification"] == "DISTRESSED_COMP":
        reasons.append("DISTRESSED_AS_IS_CONTEXT_NOT_ARV")
    if raw.get("cross_submarket") is True and not raw.get("geography_review_reference"):
        reasons.append("CROSS_SUBMARKET_REVIEW_REQUIRED")
    if raw.get("evidence_role") == "HISTORICAL_COMP_CONTEXT":
        reasons.append("HISTORICAL_CONTEXT_NOT_CURRENT_COMP_ADMISSION")
    return reasons


def deduplicate(comps):
    groups = {}
    for comp in comps:
        groups.setdefault((comp["property_key"], comp["sale_date"]), []).append(comp)
    canonical, duplicate_rows = [], []
    for key, rows in sorted(groups.items()):
        rows.sort(key=lambda r: r["comp_id"])
        first = deepcopy(rows[0])
        first["source_occurrences"] = [s for r in rows for s in r["source_occurrences"]]
        conflicts = [field for field in ("sale_price", "living_sqft", "beds", "baths") if len({r[field] for r in rows}) > 1]
        if len({r["condition"]["classification"] for r in rows}) > 1:
            conflicts.append("condition")
        first["duplicate_conflicts"] = conflicts
        if conflicts:
            first["exclusions"].append("CONFLICTING_DUPLICATE_OBSERVATIONS")
        canonical.append(first)
        duplicate_rows += [dict(comp_id=r["comp_id"], duplicate_of=first["comp_id"], source=r["source"], reason="SAME_PROPERTY_SALE_EVENT_ONE_WEIGHT") for r in rows[1:]]
    # One physical property contributes only its latest admitted sale event.
    latest = {}
    for r in canonical:
        if not r["exclusions"]:
            latest[r["property_key"]] = max(latest.get(r["property_key"], ""), r["sale_date"])
    for r in canonical:
        if not r["exclusions"] and r["sale_date"] != latest[r["property_key"]]:
            r["exclusions"].append("OLDER_SALE_SAME_PROPERTY_NO_EXTRA_WEIGHT")
    return canonical, duplicate_rows
