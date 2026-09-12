from copy import deepcopy
from .common import add_ranges, stable_id

def commit_price(groups: list[dict], chosen: list[dict], covered_ids: list[str], selection: dict,
                 *, operation: str, boundary: str, coverage_reviewed: bool) -> dict:
    """Single overlap ledger for unit, narrow or broad package evidence."""
    if not coverage_reviewed or not boundary.strip():
        raise ValueError("Ambiguous package coverage must be rejected")
    if not covered_ids or len(set(covered_ids)) != len(covered_ids):
        raise ValueError("Empty or duplicate scope coverage")
    index = {g["scope_group_id"]: g for g in groups}
    if any(gid not in index for gid in covered_ids):
        raise ValueError("Unknown scope coverage")
    covered = [index[gid] for gid in covered_ids]
    if any(g["bucket"] == "UNRESOLVED_MAJOR_EXPOSURE" or g["pricing_status"] in {"PROVISIONAL_RETAIN", "REVIEWED_RETAIN"}
           or any(r["condition"] == "UNKNOWN" or r["recommended_action"] == "INSPECTION_REQUIRED" for r in g["reviewed_components"])
           for g in covered):
        raise ValueError("Cannot price unknown, inspection-only, or retain work through a package")
    used = {gid for price in chosen for gid in price["covered_scope_groups"]}
    if used.intersection(covered_ids):
        raise ValueError("Package/component overlap: scope already included in selected price")
    if selection.get("selected_range_cents") is None:
        raise ValueError("Cannot commit an unpriced selection")
    instances = sorted({cid for g in covered for cid in g["included_component_instance_ids"]})
    used_instances = {cid for price in chosen for cid in price["cost_coverage_ids"]}
    if used_instances.intersection(instances):
        raise ValueError("Physical component overlap despite different scope groups")
    reasons = sorted({reason for g in covered for reason in g["work_reasons"]})
    bucket = "INSPECTION_DEPENDENT_SCOPE" if any(g["inspection_required"] for g in covered) else "KNOWN_SUPPORTED_SCOPE"
    prior = selection.get("historical_prior")
    line = dict(cost_line_id=stable_id("cost-", [operation, sorted(covered_ids)]), operation=operation,
                bucket=bucket, covered_scope_groups=covered_ids, cost_coverage_ids=instances,
                overlap_check="PASS_NO_OVERLAP", cost_coverage_boundary=boundary,
                coverage_status="PRELIMINARY_TARGET_BOUNDARY_NOT_VERIFIED_SOURCE_BILL_OF_QUANTITIES",
                work_reasons=reasons, work_reason=reasons[0] if len(reasons) == 1 else "UNKNOWN",
                reason_allocation="DIRECT" if len(reasons) == 1 else "MIXED_UNALLOCATED_NOT_RECAST_REQUIRED",
                evidence_ids=sorted({v for g in covered for v in g["evidence_ids"]}),
                media_ids=sorted({v for g in covered for v in g["media_ids"]}),
                inspection_required=any(g["inspection_required"] for g in covered),
                uncertainty=dict(scope="HIGH", quantity="HIGH", price="HIGH", hidden_condition="UNKNOWN"),
                quantity_evidence=dict(value=1, unit="property_scope_package", basis="HISTORICAL_PACKAGE_PRIOR",
                                       source_ids=[r["cost_library_id"] for r in prior["source_rows"]] if prior else [],
                                       reason="One consolidated allowance, not one measured room or inferred area") if selection["selected_method"] == "PACKAGE_COST" else None,
                **deepcopy(selection))
    for group in covered:
        group.update(pricing_status="INCLUDED_IN_PACKAGE" if selection["selected_method"] == "PACKAGE_COST" else "PRICED",
                     cost_line_id=line["cost_line_id"], cost_coverage_ids=instances,
                     covered_scope_groups=covered_ids, overlap_check="PASS_NO_OVERLAP",
                     not_priced_reason=None)
        # No allocation to children: null is intentional; only the parent enters totals.
        group["allocation_note"] = "Cost carried once at parent; child amount unallocated, not zero"
        group["uncertainty"]["price"] = "HIGH"
    chosen.append(line)
    return line


def totals(groups: list[dict], chosen: list[dict]) -> dict:
    def total(bucket, reason=None):
        return add_ranges([p["selected_range_cents"] for p in chosen if p["bucket"] == bucket
                           and (reason is None or p["work_reason"] == reason)])
    known, inspection = "KNOWN_SUPPORTED_SCOPE", "INSPECTION_DEPENDENT_SCOPE"
    result = {"known_supported_required": total(known, "REQUIRED"),
              "known_project_standard": total(known, "PROJECT_STANDARD"),
              "known_discretionary": total(known, "DISCRETIONARY_VALUE_ADD"),
              "known_unknown_reason": total(known, "UNKNOWN"),
              "known_scope_total": total(known), "inspection_dependent": total(inspection)}
    result["inspection_reason_breakdown"] = {r: total(inspection, r) for r in ("REQUIRED", "PROJECT_STANDARD", "DISCRETIONARY_VALUE_ADD", "UNKNOWN")}
    result["preliminary_rehab_range"] = add_ranges([result["known_scope_total"], result["inspection_dependent"]]) if chosen else None
    result["known_scope_subtotal"] = result["known_scope_total"]
    result["inspection_dependent_allowance"] = result["inspection_dependent"]
    result["policy_contingency_applied"] = None
    result["unresolved_exposure"] = None
    result["zero_subtotal_meaning"] = "Sum of priced entries only, never the cost of completing unpriced work"
    result["exclusions"] = [g["scope_group_id"] for g in groups if g["pricing_status"] not in {"INCLUDED_IN_PACKAGE", "PRICED", "REVIEWED_RETAIN"}]
    result["unresolved_major_systems_excluded"] = True
    result["high_is_all_in"] = False
    return result

