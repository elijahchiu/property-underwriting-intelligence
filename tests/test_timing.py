import unittest
from pathlib import Path
import json

from property_underwriting.financial.engine import calculate
from property_underwriting.financial.inputs import scenario_inputs
from property_underwriting.financial.timing import construction_timing_case, repair_months_from_weeks


ROOT = Path(__file__).resolve().parents[1]
PROPERTY_ID = "DEMO_PROPERTY_001"


def base_result():
    payload = json.loads((ROOT / "examples/demo_financial_scenario.json").read_text(encoding="utf-8"))
    return calculate(scenario_inputs(payload, PROPERTY_ID), mode="SCENARIO_MODE", property_id=PROPERTY_ID)


class TimingSensitivityTests(unittest.TestCase):
    def test_six_weeks_rounds_up_to_two_repair_months(self):
        self.assertEqual(repair_months_from_weeks(4), 1)
        self.assertEqual(repair_months_from_weeks(6), 2)

    def test_longer_repair_leaves_stabilized_cash_flow_unchanged_but_reduces_first_year(self):
        base = base_result()
        short = construction_timing_case(base, construction_weeks=4, lease_up_months=1, monthly_carry_cost=350)
        long = construction_timing_case(base, construction_weeks=6, lease_up_months=1, monthly_carry_cost=350)
        self.assertEqual(short["stabilized_annual_cash_flow"], long["stabilized_annual_cash_flow"])
        self.assertLess(long["first_year_operating_cash_flow"], short["first_year_operating_cash_flow"])
        self.assertLess(long["annualized_stabilized_cash_on_cash"], short["annualized_stabilized_cash_on_cash"])
        self.assertEqual(long["total_project_uses"] - short["total_project_uses"], 350)
        self.assertEqual(long["evidence_class"], "SCENARIO_ONLY")

    def test_bad_duration_or_cost_is_rejected(self):
        with self.assertRaises(ValueError):
            repair_months_from_weeks(-1)
        with self.assertRaises(ValueError):
            construction_timing_case(base_result(), construction_weeks=6, lease_up_months=1, monthly_carry_cost=-1)

    def test_non_scenario_result_is_rejected(self):
        with self.assertRaises(ValueError):
            construction_timing_case({}, construction_weeks=6, lease_up_months=1, monthly_carry_cost=350)


if __name__ == "__main__":
    unittest.main()
