from __future__ import annotations

from copy import deepcopy

from .common import decimal, stable_id


CONTRACT = "engine2-reviewed-development-handoff-0.3.0"
REASONS = {"REQUIRED", "PROJECT_STANDARD", "DISCRETIONARY_VALUE_ADD", "UNKNOWN"}
QUANTITY_HIERARCHY = ("VERIFIED_MEASUREMENT", "ACCEPTED_FLOORPLAN_OR_DIMENSION",
                      "REVIEWED_DIRECT_COUNT", "AUTHORITATIVE_PROPERTY_PROXY",
                      "HISTORICAL_PACKAGE_PRIOR", "UNKNOWN")
WORK_ACTIONS = {"MINOR_MAINTENANCE", "REPAIR", "PARTIAL_REPLACEMENT", "FULL_REPLACEMENT"}
# Canonical operation stems, joined with the approved action; unknown keys fail closed.
COMPONENT_OPERATIONS = {
    "exterior.siding": "siding", "exterior.driveway_walkways": "walkway_surface",
    "exterior.exterior_paint": "exterior_paint", "interior.flooring": "floor_finish",
    "interior.walls": "wall_finish", "interior.ceilings": "ceiling_finish",
    "interior.paint": "interior_paint", "interior.doors": "door",
    "interior.trim_baseboards": "trim", "bathroom.flooring": "bathroom_floor_finish",
    "bathroom.walls": "bathroom_wall_finish", "bathroom.tub_shower": "tub_shower",
    "bathroom.toilet": "toilet", "bathroom.vanity": "vanity_assembly",
    "bathroom.sink_faucet": "sink_faucet_assembly", "kitchen.cabinets": "cabinet",
    "kitchen.countertops": "countertop", "kitchen.flooring": "kitchen_floor_finish",
    "kitchen.sink_faucet": "kitchen_sink_faucet", "kitchen.lighting": "lighting",
    "safety.missing_fixtures": "missing_fixture_review",
}


def admit(handoff: dict) -> dict:
    if handoff.get("contract_version") != CONTRACT:
        raise ValueError("Only accepted Engine 2 development contract 0.3.0 is supported")
    for field in ("acceptance_status", "engine3_development"):
        if handoff.get(field) != "READY":
            raise ValueError(field + " must be READY")
    if not handoff.get("property_id") or not handoff.get("components"):
        raise ValueError("Property and reviewed components are required")
    if handoff.get("unresolved_development_blockers"):
        raise ValueError("Engine 2 reports unresolved development blockers")
    seen = set()
    for row in handoff["components"]:
        required = ("component_id", "component_instance_id", "room_instance_id", "condition",
                    "recommended_action", "work_reason", "evidence_ids", "media_ids", "review_origin",
                    "inspection_required", "inspection_items", "hidden_risk", "conflicts",
                    "visible_coverage", "disposition", "quantity_hints")
        if any(key not in row for key in required):
            raise ValueError("Incomplete reviewed component")
        if row["component_instance_id"] in seen:
            raise ValueError("Duplicate component instance; reconcile in Engine 2")
        seen.add(row["component_instance_id"])
        if row["work_reason"] not in REASONS or not isinstance(row["inspection_required"], bool):
            raise ValueError("Invalid reason or inspection state")
        if row["recommended_action"] == "INSPECTION_REQUIRED" and not row["inspection_required"]:
            raise ValueError("Inspection-only action must preserve inspection required")
        if not row["evidence_ids"] or row["review_origin"] != handoff["review_origin"]:
            raise ValueError("Missing reviewed evidence or inconsistent origin")
        if row["condition"] == "UNKNOWN" and row["recommended_action"] == "KEEP_NO_WORK":
            raise ValueError("UNKNOWN cannot be converted into no work")
    return deepcopy(handoff)


def resolve_quantity(candidates: list[dict], operation: str) -> dict:
    accepted, rejected = [], []
    for candidate in candidates:
        candidate = deepcopy(candidate)
        basis = candidate.get("basis", "UNKNOWN")
        reason = None
        if basis not in QUANTITY_HIERARCHY[:-1]:
            reason = "UNKNOWN_BASIS"
        elif candidate.get("review_status") not in {"REVIEWED", "REVIEWED_PROVIDER_ASSISTED"} or candidate.get("evidence_level") == "D":
            reason = "UNREVIEWED_HINT_NOT_QUANTITY_AUTHORITY"
        elif basis == "VERIFIED_MEASUREMENT" and candidate.get("evidence_level") != "V":
            reason = "VERIFIED_MEASUREMENT_REQUIRES_VERIFIED_EVIDENCE"
        elif candidate.get("usage") == "HINT_ONLY_NOT_MEASURED_OR_SUMMED":
            reason = "HINT_NOT_MEASURED_OR_SUMMED"
        elif not candidate.get("source_ids") or operation not in candidate.get("compatible_operations", []):
            reason = "MISSING_SOURCE_OR_INCOMPATIBLE_SCOPE"
        elif not candidate.get("unit"):
            reason = "MISSING_UNIT"
        elif basis == "AUTHORITATIVE_PROPERTY_PROXY" and candidate["unit"] == "sqft" and operation != "whole_reported_living_area_reference":
            reason = "ASSESSOR_AREA_IS_NOT_COMPONENT_GEOMETRY"
        else:
            try:
                if decimal(candidate.get("value")) <= 0:
                    reason = "NONPOSITIVE_QUANTITY"
            except (ValueError, ArithmeticError):
                reason = "INVALID_QUANTITY"
        if reason:
            rejected.append(dict(candidate=candidate, reason=reason))
        else:
            accepted.append(candidate)
    if not accepted:
        return dict(value=None, unit=None, basis="UNKNOWN", rejected=rejected,
                    reason="No accepted quantity; no geometry manufactured from photographs or assessor area")
    accepted.sort(key=lambda c: QUANTITY_HIERARCHY.index(c["basis"]))
    top = [c for c in accepted if c["basis"] == accepted[0]["basis"]]
    if len({(decimal(c["value"]), c["unit"]) for c in top}) > 1:
        return dict(value=None, unit=None, basis="UNKNOWN", rejected=rejected,
                    conflicts=top, reason="Conflicting equal-authority quantities require review")
    return {**accepted[0], "rejected": accepted[0].get("rejected", []) + rejected, "alternatives": accepted[1:]}


def exposure_family(component_id: str) -> str | None:
    if component_id.startswith("environmental."):
        return "environmental_conditions"
    if component_id in {"exterior.roof_covering", "structure.roof_decking", "structure.roof_structure"}:
        return "roof_covering_structure_decking"
    if component_id == "structure.foundation":
        return "foundation"
    if component_id.startswith("structure.") or component_id == "basement.structure":
        return "concealed_framing_and_floor_structure"
    if component_id in {"systems.visible_electrical", "systems.concealed_wiring", "systems.electrical_service", "safety.exposed_wiring"}:
        return "electrical_visible_and_concealed"
    if component_id == "systems.sewer_lateral":
        return "sewer_lateral"
    if component_id in {"systems.concealed_plumbing", "systems.plumbing_supply", "systems.plumbing_waste"}:
        return "concealed_plumbing"
    if component_id in {"systems.furnace", "systems.air_conditioning", "systems.ductwork", "systems.hvac_internal"}:
        return "hvac_operation"
    if component_id == "systems.water_heater":
        return "water_heater_operation"
    if component_id in {"basement.moisture", "safety.water_intrusion", "exterior.grading_drainage"}:
        return "moisture_and_drainage"
    return None


def build_scope(handoff: dict) -> list[dict]:
    """Preserve reviewed labels whole; scope grouping never edits accepted evidence."""
    groups = {}
    physical_facts = handoff["source_engine1_context"]["research_projection"]["physical_facts"]
    components = handoff["components"] + handoff.get("unobserved_components", [])
    bath_rooms = {c.get("room_instance_id") for c in handoff["components"]
                  if c["component_id"] == "bathroom.vanity" and c["recommended_action"] == "FULL_REPLACEMENT"}
    for row in components:
        cid, action = row["component_id"], row["recommended_action"]
        room = row.get("room_instance_id", "property_unobserved")
        family = exposure_family(cid)
        major = family and (row["condition"] == "UNKNOWN" or action == "INSPECTION_REQUIRED")
        safety_overlap = cid == "safety.missing_fixtures" and room in bath_rooms
        if major:
            operation, key = "inspect_" + family, "exposure:" + family
            bucket, status = "UNRESOLVED_MAJOR_EXPOSURE", "UNRESOLVED_NOT_ZERO_WORK"
        elif action == "KEEP_NO_WORK":
            operation, key = "retain_" + cid, room + ":" + cid
            bucket = "INSPECTION_DEPENDENT_SCOPE" if row["inspection_required"] else "KNOWN_SUPPORTED_SCOPE"
            status = "PROVISIONAL_RETAIN" if row["inspection_required"] else "REVIEWED_RETAIN"
        elif action == "INSPECTION_REQUIRED" or row["condition"] == "UNKNOWN":
            operation, key = "inspect_" + cid, room + ":" + cid
            bucket, status = "INSPECTION_DEPENDENT_SCOPE", "NOT_PRICED"
        elif safety_overlap or (cid in {"bathroom.vanity", "bathroom.sink_faucet"} and room in bath_rooms):
            operation, key = "vanity_sink_assembly_replacement", room + ":vanity_sink_assembly"
            bucket, status = "INSPECTION_DEPENDENT_SCOPE", "NOT_PRICED"
        else:
            stem = COMPONENT_OPERATIONS.get(cid)
            operation = stem + "_" + action.lower() if stem and action in WORK_ACTIONS else "UNMAPPED_REVIEW_REQUIRED"
            key = room + ":" + cid
            # Accepted dispositions take precedence over superficially certain action labels.
            dependent = row["inspection_required"] or row.get("disposition") == "INSPECTION_BEFORE_SCOPE"
            bucket = "INSPECTION_DEPENDENT_SCOPE" if dependent else "KNOWN_SUPPORTED_SCOPE"
            status = "NOT_PRICED"
        if key not in groups:
            groups[key] = dict(scope_group_id=stable_id("scope-", [handoff["property_id"], key]),
                               operation=operation, bucket=bucket, pricing_status=status,
                               included_component_ids=[], included_component_instance_ids=[],
                               reviewed_components=[], room_instance_ids=[], evidence_ids=[], media_ids=[],
                               deduplication_reason="ONE_PHYSICAL_COMPONENT_INSTANCE",
                               inspection_required=False, inspection_items=[], hidden_risks=[], conflicts=[],
                               cost_coverage_ids=[], covered_scope_groups=[], overlap_check="NOT_PRICED")
        group = groups[key]
        group["reviewed_components"].append(deepcopy(row))
        for field, values in (("included_component_ids", [cid]),
                              ("included_component_instance_ids", [row.get("component_instance_id", "unobserved:" + cid)]),
                              ("room_instance_ids", [room]), ("evidence_ids", row["evidence_ids"]),
                              ("media_ids", row["media_ids"]), ("inspection_items", row.get("inspection_items", [])),
                              ("hidden_risks", [row["hidden_risk"]]), ("conflicts", row["conflicts"])):
            for value in values:
                if value not in group[field]:
                    group[field].append(value)
        group["inspection_required"] |= row["inspection_required"]
    for group in groups.values():
        rows = group["reviewed_components"]
        reasons = sorted({c["work_reason"] for c in rows})
        group["work_reasons"] = reasons
        group["work_reason"] = reasons[0] if len(reasons) == 1 else "UNKNOWN"
        group["reason_allocation"] = "DIRECT" if len(reasons) == 1 else "MIXED_UNALLOCATED_NOT_RECAST_REQUIRED"
        group["review_origin"] = handoff["review_origin"]
        group["media_coverage"] = {c.get("component_instance_id", c["component_id"]):
                                   c.get("visible_coverage", c.get("media_coverage", "UNKNOWN")) for c in rows}
        group["unknowns"] = [c["component_id"] for c in rows if c["condition"] == "UNKNOWN"]
        candidates = []
        if group["operation"] == "vanity_sink_assembly_replacement":
            group["deduplication_reason"] = "ONE_BATHROOM_VANITY_SINK_ASSEMBLY; SAFETY_MISSING_FIXTURE_IS_SAME_WORK_NOT_EXTRA"
            bathroom = physical_facts.get("bathrooms", {})
            if len(bath_rooms) == 1 and bathroom.get("normalized_value") == 1 and bathroom.get("evidence_level") == "A":
                candidates.append(dict(value=1, unit="assembly", basis="REVIEWED_DIRECT_COUNT",
                                       evidence_level="C", review_status="REVIEWED_PROVIDER_ASSISTED",
                                       source_ids=group["evidence_ids"] + [bathroom.get("observation_id", "engine1:physical_facts.bathrooms")],
                                       compatible_operations=[group["operation"]],
                                       reason="Single reviewed bathroom/vanity requirement plus official one-bath fact; not AI hints"))
        if group["bucket"] == "UNRESOLVED_MAJOR_EXPOSURE":
            group["deduplication_reason"] = "RELATED_UNKNOWN_COMPONENTS_ONE_INSPECTION_EXPOSURE; NOT_ADDITIONAL_REVIEW_LABELS"
        group["quantity_evidence"] = resolve_quantity(candidates, group["operation"])
        group["quantity_hints"] = [deepcopy(h) for c in rows for h in c.get("quantity_hints", [])]
        group["selected_range_cents"] = None
        group["known_priced_work_cents"] = 0 if group["pricing_status"] in {"PROVISIONAL_RETAIN", "REVIEWED_RETAIN"} else None
        group["uncertainty"] = dict(scope="HIGH" if group["inspection_required"] else "MEDIUM",
                                     quantity="HIGH" if candidates else "UNKNOWN", price="UNKNOWN", hidden_condition="UNKNOWN")
        group["not_priced_reason"] = "No compatible scope/quantity/cost evidence yet; unknown is not zero work"
    return list(groups.values())
