"""Deterministic construction-timing sensitivity for explicit scenarios.

This is a scenario overlay, not an inferred project schedule or a prediction.
"""

import math


WEEKS_PER_MONTH = 4.345


def repair_months_from_weeks(construction_weeks):
    """Round construction weeks up to monthly repair-carry periods."""
    if (isinstance(construction_weeks, bool)
            or not isinstance(construction_weeks, (int, float))
            or not math.isfinite(construction_weeks)
            or construction_weeks < 0):
        raise ValueError("Construction weeks must be a finite nonnegative number")
    return math.ceil(construction_weeks / WEEKS_PER_MONTH)


def construction_timing_case(financial_result, *, construction_weeks,
                              lease_up_months, monthly_carry_cost):
    """Return timing-adjusted year-one cash flow and project-use sensitivity.

    The base result must be a complete, operator-supplied financial scenario.
    Stabilized operations continue to use Engine 6's annualized metrics. For
    year one, expected rent is withheld during repair and lease-up months and
    an explicit, non-overlapping monthly carry cost is added. That cost is
    assumed to be funded entirely by additional equity while debt is held
    constant. Fixed operating expenses already present in Engine 6 remain in
    the annual cash-flow baseline.
    """
    if not isinstance(financial_result, dict) or financial_result.get("mode") != "SCENARIO_MODE":
        raise ValueError("An explicit SCENARIO_MODE financial result is required")
    if financial_result.get("FINANCIAL_PROFILE_STATUS") != "SCENARIO_ONLY":
        raise ValueError("Timing sensitivity must remain scenario-only")

    inputs = financial_result.get("inputs", {})
    metrics = financial_result.get("metrics", {})

    def value(name):
        metric = metrics.get(name, {})
        if metric.get("status") != "READY" or metric.get("value") is None:
            raise ValueError(f"Required financial metric is unavailable: {name}")
        return float(metric["value"])

    def input_value(name):
        item = inputs.get(name, {})
        result = item.get("value")
        if result is None or item.get("accepted") is not True:
            raise ValueError(f"Required accepted scenario input is unavailable: {name}")
        return float(result)

    if financial_result.get("selected_revenue_source") != "monthly_scenario_rent":
        raise ValueError("A deliberate monthly scenario rent is required")
    repair_months = repair_months_from_weeks(construction_weeks)
    if isinstance(lease_up_months, bool) or not isinstance(lease_up_months, int) or lease_up_months < 0:
        raise ValueError("Lease-up months must be a nonnegative integer")
    if (isinstance(monthly_carry_cost, bool)
            or not isinstance(monthly_carry_cost, (int, float))
            or not math.isfinite(monthly_carry_cost)
            or monthly_carry_cost < 0):
        raise ValueError("Monthly carry cost must be a finite nonnegative number")

    pre_stabilization_months = repair_months + lease_up_months
    first_year_no_rent_months = min(12, pre_stabilization_months)
    monthly_rent = input_value("monthly_scenario_rent")
    vacancy = input_value("vacancy_rate")
    credit_loss = input_value("credit_loss_rate")
    if not 0 <= vacancy <= 1 or not 0 <= credit_loss <= 1:
        raise ValueError("Vacancy and credit-loss rates must be fractions from zero to one")

    stabilized_annual_cash_flow = value("ANNUAL_CASH_FLOW")
    base_project_uses = value("TOTAL_PROJECT_COST")
    base_cash_invested = value("TOTAL_CASH_INVESTED")
    if base_cash_invested <= 0:
        raise ValueError("Positive initial cash invested is required")
    effective_monthly_rent = monthly_rent * (1 - vacancy) * (1 - credit_loss)
    lost_rent = effective_monthly_rent * first_year_no_rent_months
    additional_carry = float(monthly_carry_cost) * pre_stabilization_months
    first_year_carry = float(monthly_carry_cost) * first_year_no_rent_months
    year_one_cash_flow = stabilized_annual_cash_flow - lost_rent - first_year_carry
    project_uses = base_project_uses + additional_carry
    cash_invested = base_cash_invested + additional_carry

    return {
        "evidence_class": "SCENARIO_ONLY",
        "construction_weeks": construction_weeks,
        "repair_months_rounded_up": repair_months,
        "lease_up_months": lease_up_months,
        "pre_stabilization_no_rent_months": pre_stabilization_months,
        "first_year_no_rent_months": first_year_no_rent_months,
        "stabilized_annual_cash_flow": round(stabilized_annual_cash_flow, 2),
        "annualized_stabilized_cash_on_cash": round(stabilized_annual_cash_flow / cash_invested, 8),
        "first_year_operating_cash_flow": round(year_one_cash_flow, 2),
        "additional_pre_stabilization_uses": round(additional_carry, 2),
        "total_project_uses": round(project_uses, 2),
        "total_cash_invested": round(cash_invested, 2),
        "method": {
            "repair_month_conversion": "ceil(construction weeks / 4.345)",
            "first_year_operating_cash_flow": "stabilized annual cash flow - effective rent lost during repair and lease-up within year one - explicit non-overlapping monthly carry cost for each pre-stabilization month within year one",
            "cash_on_cash": "stabilized annual cash flow / initial cash invested including timing carry; not first-year return",
            "funding_policy": "incremental carry is funded with equity; debt and stabilized operations are held constant",
        },
        "assumptions": {
            "monthly_effective_rent": round(effective_monthly_rent, 2),
            "monthly_nonoverlapping_carry_cost": round(float(monthly_carry_cost), 2),
            "year_one_cash_flow_basis": "pre-tax, pre-capex operating cash flow; excludes purchase, rehab, and other initial project uses",
        },
    }
