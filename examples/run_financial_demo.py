"""Run the fully synthetic public financial-underwriting demonstration."""

import json
from pathlib import Path


from property_underwriting.financial.engine import calculate
from property_underwriting.financial.inputs import scenario_inputs


PROPERTY_ID = "DEMO_PROPERTY_001"
SCENARIO_PATH = Path(__file__).with_name("demo_financial_scenario.json")


def main():
    with SCENARIO_PATH.open("r", encoding="utf-8") as file:
        payload = json.load(file)

    inputs = scenario_inputs(payload, PROPERTY_ID)

    result = calculate(
        inputs,
        mode="SCENARIO_MODE",
        property_id=PROPERTY_ID,
    )

    metrics = result["metrics"]

    print("\nPROPERTY UNDERWRITING INTELLIGENCE — SYNTHETIC DEMO")
    print("=" * 58)
    print("Synthetic demonstration only — not an actual property analysis.\n")

    print(
        f"Total Project Cost:  "
        f"${metrics['TOTAL_PROJECT_COST']['value']:,.2f}"
    )
    print(
        f"NOI:                 "
        f"${metrics['NET_OPERATING_INCOME']['value']:,.2f} / year"
    )
    print(
        f"Yield on Cost:       "
        f"{metrics['YIELD_ON_COST']['value'] * 100:.2f}%"
    )
    print(
        f"DSCR:                "
        f"{metrics['DSCR']['value']:.2f}x"
    )
    print(
        f"Cash-on-Cash Return: "
        f"{metrics['CASH_ON_CASH_RETURN']['value'] * 100:.2f}%"
    )
    print(
        f"Monthly Cash Flow:   "
        f"${metrics['MONTHLY_CASH_FLOW']['value']:,.2f}"
    )
    print(
        f"Debt Yield:          "
        f"{metrics['DEBT_YIELD']['value'] * 100:.2f}%"
    )
    print(
        f"Loan-to-Cost:        "
        f"{metrics['LOAN_TO_COST']['value'] * 100:.2f}%"
    )

    print("\nFinancial Profile:", result["FINANCIAL_PROFILE_STATUS"])
    print("Sources & Uses:", result["sources_and_uses"]["status"])


if __name__ == "__main__":
    main()