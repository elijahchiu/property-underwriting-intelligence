"""Independent, synthetic-data portfolio analysis for the interactive demo.

All fixture records are fictional. The weighted-analog calculation is a
teaching demonstration and is not fitted to Roof4All company records.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from .data_pipeline import prepare_dataset


DATA_PATH = Path(__file__).with_name("data.json")
DATA = json.loads(DATA_PATH.read_text(encoding="utf-8"))
ANALYTIC_DATA = prepare_dataset(DATA)

BASE_SCOPE = ("kitchen", "bath", "flooring", "paint", "hvac_service", "exterior")
EXTRA_SCOPE = {
    "interior_refresh": (),
    "finished_basement": ("basement_finish",),
    "systems_refresh": ("roof", "electrical"),
}


def _find(rows, key, value):
    return next((row for row in rows if row.get(key) == value), None)


def _property(property_id):
    result = _find(DATA["properties"], "id", property_id)
    if result is None:
        raise ValueError("Select one of the fictional demo properties")
    return result


def _market(market_id):
    return _find(DATA["markets"], "id", market_id)


def market_similarity(subject, candidate):
    """Readable weighted similarity score for the fictional scope corpus."""
    weights = {"market": 0.30, "property_type": 0.15, "era": 0.15, "area": 0.25, "basement": 0.15}
    features = {
        "market": (subject["market_id"] == candidate["market_id"], weights["market"]),
        "property_type": (subject["property_type"] == candidate["property_type"], weights["property_type"]),
        "era": (max(0.0, 1 - abs(subject["year_built"] - candidate["year_built"]) / 60), weights["era"]),
        "area": (max(0.0, 1 - abs(subject["sqft"] - candidate["sqft"]) / max(subject["sqft"], candidate["sqft"])), weights["area"]),
        "basement": (subject["basement"] == candidate["basement"], weights["basement"]),
    }
    score = sum((float(value) if isinstance(value, bool) else value) * weight for value, weight in features.values())
    return round(score * 100, 1), {name: round((float(value) if isinstance(value, bool) else value) * 100, 1) for name, (value, _) in features.items()}


def _project_cost(project, category, subject):
    costs = project["costs"]
    if category == "flooring":
        return costs.get("flooring_per_sqft", 0) * subject["sqft"]
    if category == "paint":
        return costs.get("paint_per_sqft", 0) * subject["sqft"]
    if category == "bath":
        return costs.get("bath", 0) * max(1, subject["baths"]) / max(1, project["baths"])
    if category == "basement_finish":
        return costs.get("basement_finish_per_sqft", 0) * subject["basement_sqft"]
    return costs.get(category, 0)


def _scope_for(subject, strategy, overrides):
    if strategy not in EXTRA_SCOPE:
        raise ValueError("Unknown scope strategy")
    ranked = []
    for project in ANALYTIC_DATA["scope_projects"]:
        score, feature_scores = market_similarity(subject, project)
        ranked.append((project, score, feature_scores))
    ranked.sort(key=lambda row: (-row[1], row[0]["id"]))
    analogs = ranked[:5]
    categories = list(BASE_SCOPE + EXTRA_SCOPE[strategy])
    if strategy == "finished_basement" and not subject["basement"]:
        categories.remove("basement_finish")

    labels = {
        "kitchen": ("Kitchen refresh", "Package estimate from similar fictional projects"),
        "bath": ("Existing bathroom refresh", "Per-bath package scaled to subject bath count"),
        "flooring": ("Flooring", "Synthetic area rate × subject living area"),
        "paint": ("Paint and finish", "Synthetic area rate × subject living area"),
        "hvac_service": ("HVAC service allowance", "Package estimate from similar fictional projects"),
        "exterior": ("Exterior repairs", "Package estimate from similar fictional projects"),
        "basement_finish": ("Basement finish", "Synthetic area rate × stated basement area"),
        "roof": ("Roof replacement allowance", "Package estimate from similar fictional projects"),
        "electrical": ("Electrical update allowance", "Package estimate from similar fictional projects"),
    }
    lines = []
    for category in categories:
        observations = []
        for project, score, _ in analogs:
            amount = _project_cost(project, category, subject)
            if amount > 0:
                observations.append((amount, max(score, 1)))
        if not observations:
            continue
        weight_total = sum(weight for _, weight in observations)
        base = sum(amount * weight for amount, weight in observations) / weight_total
        low = min(amount for amount, _ in observations)
        high = max(amount for amount, _ in observations)
        override = overrides.get(category)
        if override is not None:
            try:
                base = float(override)
            except (ValueError, TypeError):
                raise ValueError(f"Enter a valid nonnegative estimate for {labels[category][0]}")
            if not math.isfinite(base) or base < 0 or base > 10_000_000:
                raise ValueError("Scope overrides must be between $0 and $10,000,000")
        lines.append({
            "category": category,
            "label": labels[category][0],
            "method": labels[category][1],
            "low": round(low),
            "base": round(base),
            "high": round(high),
            "supporting_projects": len(observations),
            "total_analogs": len(analogs),
            "evidence_class": "SYNTHETIC_SCENARIO_ONLY",
        })
    return {
        "strategy": strategy,
        "lines": lines,
        "total": sum(line["base"] for line in lines),
        "analog_count": len(analogs),
        "method": "Similarity-weighted mean of the five closest fictional project records; per-area rates are scaled by the stated subject area. Low/high show the observed range in those fictional analogs.",
        "weights": {"market": 0.30, "property_type": 0.15, "era": 0.15, "area": 0.25, "basement": 0.15},
        "analogs": [{"id": project["id"], "score": score, "feature_scores": features} for project, score, features in analogs],
        "status": "PRELIMINARY_SYNTHETIC_ESTIMATE",
    }


def _number(inputs, key, default, minimum=0, maximum=10_000_000):
    value = inputs.get(key, default)
    if isinstance(value, bool):
        raise ValueError(f"{key} must be a number")
    try:
        value = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{key} must be a number")
    if not math.isfinite(value) or value < minimum or value > maximum:
        raise ValueError(f"{key} must be between {minimum} and {maximum}")
    return value


def _finance(subject, rehab_total, inputs):
    defaults = {
        "purchase_price": subject["asking_price"],
        "monthly_rent": subject["monthly_rent"],
        "vacancy_rate": _market(subject["market_id"])["vacancy_rate"],
        "annual_tax": subject["annual_tax"],
        "annual_insurance": subject["annual_insurance"],
        "maintenance_rate": 0.06,
        "management_rate": 0.08,
        "other_monthly_expenses": 0,
        "ltv": 0.75,
        "interest_rate": 0.075,
        "loan_term_years": 30,
        "closing_rate": 0.03,
        "initial_reserves": 1000,
    }
    values = {key: _number(inputs, key, default, 1 if key == "loan_term_years" else 0, 100 if key == "loan_term_years" else 1 if key.endswith("_rate") or key == "ltv" else 10_000_000) for key, default in defaults.items()}
    price = values["purchase_price"]
    rent = values["monthly_rent"]
    ltv = values["ltv"]
    monthly_rate = values["interest_rate"] / 12
    loan = price * ltv
    months = int(values["loan_term_years"] * 12)
    debt_payment = loan * monthly_rate / (1 - (1 + monthly_rate) ** -months) if loan and monthly_rate else loan / months if loan else 0
    gross = rent * 12
    effective_gross = gross * (1 - values["vacancy_rate"])
    annual_expenses = (values["annual_tax"] + values["annual_insurance"] + price * values["maintenance_rate"] + gross * values["management_rate"] + values["other_monthly_expenses"] * 12)
    noi = effective_gross - annual_expenses
    annual_debt = debt_payment * 12
    annual_cash_flow = noi - annual_debt
    closing = price * values["closing_rate"]
    purchase_and_rehab = price + rehab_total
    invested = price * (1 - ltv) + rehab_total + closing + values["initial_reserves"]
    return {
        "inputs": {**values, "rehab_budget": round(rehab_total)},
        "metrics": {
            "estimated_gross_rent": round(gross),
            "estimated_noi": round(noi),
            "annual_debt_service": round(annual_debt),
            "monthly_debt_payment": round(debt_payment),
            "monthly_cash_flow": round(annual_cash_flow / 12),
            "dscr": round(noi / annual_debt, 2) if annual_debt else None,
            "cash_on_cash": round(annual_cash_flow / invested, 4) if invested > 0 else None,
            "project_uses": round(price + rehab_total + closing + values["initial_reserves"]),
            "purchase_and_rehab": round(purchase_and_rehab),
            "cash_invested": round(invested),
            "closing_costs": round(closing),
            "initial_reserves": round(values["initial_reserves"]),
            "project_uses_components": {
                "purchase_price": round(price),
                "rehab_budget": round(rehab_total),
                "closing_costs": round(closing),
                "initial_reserves": round(values["initial_reserves"]),
            },
        },
        "evidence_class": "SYNTHETIC_SCENARIO_ONLY",
    }


def evaluate_synthetic_scope_holdouts():
    """Leave one fictional project out at a time and report descriptive errors.

    Every project is held out as a whole. Predictions use only the other
    fictional projects, the same transparent similarity weights, and the
    same category cost-scaling helpers used by the interactive demo.
    """
    projects = ANALYTIC_DATA["scope_projects"]
    categories = sorted({key for project in projects for key in project["costs"]})
    rows = []
    component_errors = []
    total_errors = []
    total_ape = []
    for heldout in projects:
        subject = {
            **heldout,
            "baths": heldout.get("baths", 1),
            "basement_sqft": 0,
        }
        pool = [project for project in projects if project["id"] != heldout["id"]]
        ranked = sorted(
            ((project, market_similarity(subject, project)[0]) for project in pool),
            key=lambda row: (-row[1], row[0]["id"]),
        )[:5]
        actual_total = 0.0
        predicted_total = 0.0
        component_count = 0
        for category in categories:
            if category not in heldout["costs"]:
                continue
            actual = _project_cost(heldout, category, subject)
            observations = [
                (_project_cost(project, category, subject), max(score, 1))
                for project, score in ranked
                if _project_cost(project, category, subject) > 0
            ]
            if not observations:
                continue
            estimate = sum(value * weight for value, weight in observations) / sum(weight for _, weight in observations)
            component_errors.append(abs(estimate - actual))
            component_count += 1
            actual_total += actual
            predicted_total += estimate
        actual_total = round(actual_total)
        predicted_total = round(predicted_total)
        error = abs(predicted_total - actual_total)
        total_errors.append(error)
        if actual_total:
            total_ape.append(error / actual_total)
        rows.append({
            "held_out_project": heldout["id"],
            "training_projects": len(pool),
            "components_compared": component_count,
            "actual_tracked_component_sum": round(actual_total),
            "predicted_tracked_component_sum": round(predicted_total),
            "absolute_component_sum_error": round(error),
            "component_sum_absolute_percentage_error": round(error / actual_total, 4) if actual_total else None,
        })
    mean = lambda values: round(sum(values) / len(values), 2) if values else None
    ordered = sorted(total_errors)
    median = round((ordered[(len(ordered)-1)//2] + ordered[len(ordered)//2]) / 2, 2) if ordered else None
    return {
        "label": "SYNTHETIC DEMONSTRATION ONLY — not Roof4All validation or real project performance",
        "method": "Leave one fictional scope project out; estimate its recorded categories from all other projects with the demo similarity-weighted mean. Area-priced categories are scaled to the held-out project's own area. Basement-finish costs are excluded because the source fixtures provide no basement-area quantities.",
        "excluded_categories": {"basement_finish": "No basement-area quantity is present in these synthetic scope records."},
        "project_count": len(projects),
        "aggregate": {
            "component_observations": len(component_errors),
            "component_cost_mae": mean(component_errors),
            "tracked_component_sum_mae": mean(total_errors),
            "tracked_component_sum_median_absolute_error": median,
            "tracked_component_sum_mape": mean(total_ape),
        },
        "properties": rows,
    }


def _timing(finance, lease_up_months, monthly_carry_cost):
    metrics = finance["metrics"]
    inputs = finance["inputs"]
    cases = []
    for weeks in (4, 6):
        repair_months = math.ceil(weeks / 4.345)
        no_rent_months = repair_months + lease_up_months
        year_one_months = min(12, no_rent_months)
        effective_rent = inputs["monthly_rent"] * (1 - inputs["vacancy_rate"])
        additional_uses = monthly_carry_cost * no_rent_months
        first_year_cf = metrics["monthly_cash_flow"] * 12 - effective_rent * year_one_months - monthly_carry_cost * year_one_months
        adjusted_cash_invested = metrics["cash_invested"] + additional_uses
        cases.append({
            "construction_weeks": weeks,
            "repair_months": repair_months,
            "lease_up_months": lease_up_months,
            "no_rent_months": no_rent_months,
            "annualized_stabilized_cash_on_cash": round(metrics["monthly_cash_flow"] * 12 / adjusted_cash_invested, 4) if adjusted_cash_invested else None,
            "first_year_operating_cash_flow": round(first_year_cf),
            "additional_uses": round(additional_uses),
            "project_uses_including_timing": round(metrics["project_uses"] + additional_uses),
        })
    return cases


def analyze_property(payload):
    """Return a full fictional workspace packet from a small explicit fixture."""
    if not isinstance(payload, dict):
        raise ValueError("Analysis request must be an object")
    subject = _property(payload.get("property_id"))
    market = _market(subject["market_id"])
    strategy = payload.get("strategy", "interior_refresh")
    overrides = payload.get("scope_overrides", {})
    if not isinstance(overrides, dict):
        raise ValueError("Scope overrides must be an object")
    scope = _scope_for(subject, strategy, overrides)
    inputs = payload.get("financial_inputs", {})
    if not isinstance(inputs, dict):
        raise ValueError("Financial inputs must be an object")
    finance = _finance(subject, scope["total"], inputs)
    timing_inputs = payload.get("timing_inputs", {})
    lease_up = int(_number(timing_inputs, "lease_up_months", 1, 0, 24))
    carry = _number(timing_inputs, "monthly_carry_cost", 350, 0, 1_000_000)
    sale_values = sorted(comp["sale_price"] for comp in subject["comps"]["sales"])
    rental_values = sorted(comp["monthly_rent"] for comp in subject["comps"]["rentals"])
    return {
        "data_notice": DATA["data_notice"],
        "property": subject,
        "market": market,
        "scope": scope,
        "sales": subject["comps"]["sales"],
        "rentals": subject["comps"]["rentals"],
        "value_reference": {
            "median_comparable_sale": sale_values[len(sale_values) // 2],
            "sale_count": len(sale_values),
            "evidence_class": "SIMULATED_CLOSED_SALE_FIXTURE",
        },
        "rent_reference": {
            "median_comparable_asking_rent": rental_values[len(rental_values) // 2],
            "rent_count": len(rental_values),
            "evidence_class": "SIMULATED_ASKING_RENT_FIXTURE",
        },
        "finance": finance,
        "timing": _timing(finance, lease_up, carry),
        "audit": {
            "model_version": "synthetic-analog-demo-v1",
            "corpus_version": "fictional-fixtures-2026-10",
            "review_required": ["Confirm identity and property facts", "Inspect concealed systems", "Obtain a complete contractor scope", "Verify achieved rent and financing terms"],
            "limits": ["Fictional records only", "No real property facts or prices", "Analog ranges are not confidence intervals", "No investment or lending decision is provided"],
        },
    }


def bootstrap():
    """Return synthetic public UI data and derived market counts."""
    markets = []
    for row in DATA["markets"]:
        members = [prop for prop in DATA["properties"] if prop["market_id"] == row["id"]]
        markets.append({**row, "property_count": len(members), "average_simulated_asking": round(sum(p["asking_price"] for p in members) / len(members)) if members else None})
    return {"edition": DATA["edition"], "data_notice": DATA["data_notice"], "markets": markets, "properties": DATA["properties"], "project_count": len(DATA["synthetic_scope_projects"])}
