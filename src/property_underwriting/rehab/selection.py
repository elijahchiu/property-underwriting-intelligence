from copy import deepcopy
from .common import cost_range

def select_evidence(historical: dict | None, current: dict | None = None, manual: dict | None = None) -> dict:
    result = dict(historical_prior=deepcopy(historical), current_provider_evidence=deepcopy(current),
                  manual_contractor_evidence=deepcopy(manual), selected_method="NOT_PRICED",
                  selected_range_cents=None, selection_reason="No compatible evidence")
    if manual:
        valid = (manual.get("verified") is True and manual.get("source_ids")
                 and manual.get("source_type") in {"CONTRACTOR_ESTIMATE", "INVOICE"}
                 and manual.get("coverage_review_status") == "REVIEWED"
                 and manual.get("scope_compatible") is True)
        if valid:
            span = cost_range(**manual["range_cents"])
            result.update(selected_method="VERIFIED_CONTRACTOR_EVIDENCE", selected_range_cents=span,
                          selection_reason="Verified scoped contractor evidence; other evidence retained separately")
            return result
    if current and current.get("status") == "COMPATIBLE":
        result.update(selected_method="UNIT_COST", selected_range_cents=cost_range(**current["range_cents"]),
                      selection_reason="Compatible reviewed current local rate; historical prior retained, not averaged")
    elif historical and (historical["method"] != "UNIT_COST" or historical.get("resolved_quantity")):
        result.update(selected_method=historical["method"], selected_range_cents=historical["historical_range_cents"],
                      selection_reason="Historical estimated budget prior only; no current or verified contractor evidence")
    return result

