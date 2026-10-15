"""Compare two fully synthetic construction timelines with explicit assumptions."""

import json
from pathlib import Path

from property_underwriting.financial.engine import calculate
from property_underwriting.financial.inputs import scenario_inputs
from property_underwriting.financial.timing import construction_timing_case


HERE = Path(__file__).resolve().parent
PROPERTY_ID = "DEMO_PROPERTY_001"


def run():
    timing = json.loads((HERE / "timing_sensitivity.json").read_text(encoding="utf-8"))
    scenario = json.loads((HERE / timing["financial_scenario"]).read_text(encoding="utf-8"))
    result = calculate(
        scenario_inputs(scenario, PROPERTY_ID),
        mode="SCENARIO_MODE",
        property_id=PROPERTY_ID,
    )
    cases = [
        (case["label"], construction_timing_case(
            result,
            construction_weeks=case["construction_weeks"],
            lease_up_months=timing["lease_up_months"],
            monthly_carry_cost=timing["monthly_nonoverlapping_pre_stabilization_carry_cost"],
        ))
        for case in timing["timeline_cases"]
    ]

    print("PROPERTY UNDERWRITING INTELLIGENCE — SYNTHETIC TIMING SENSITIVITY")
    print("=" * 72)
    print("Fictional assumptions only. This is deterministic scenario arithmetic, not a forecast.\n")
    print("Measure                                      " + "  ".join(label for label, _ in cases))
    rows = (
        ("Repair months (rounded up)", "repair_months_rounded_up", "{:d}"),
        ("Lease-up months", "lease_up_months", "{:d}"),
        ("Pre-stabilization no-rent months", "pre_stabilization_no_rent_months", "{:d}"),
        ("Stabilized annual cash flow", "stabilized_annual_cash_flow", "${:,.2f}"),
        ("Annualized stabilized cash-on-cash", "annualized_stabilized_cash_on_cash", "{:.2%}"),
        ("First-year operating cash flow", "first_year_operating_cash_flow", "${:,.2f}"),
        ("Additional pre-stabilization uses", "additional_pre_stabilization_uses", "${:,.2f}"),
        ("Total project uses", "total_project_uses", "${:,.2f}"),
    )
    for label, key, fmt in rows:
        values = [fmt.format(case[key]) for _, case in cases]
        print(f"{label:<44}" + "  ".join(f"{value:>18}" for value in values))

    print("\nCash-on-cash is an annualized stabilized measure; it is not first-year cash return.")
    print("First-year operating cash flow subtracts lost effective rent during repair/lease-up and the explicit carry assumption.")
    print("Initial purchase and rehab uses are excluded from first-year operating cash flow and included in invested cash.")
    print("The saved-description conflict state is not part of this synthetic example.")
    return cases


if __name__ == "__main__":
    run()
