import unittest

from portfolio_demo.data_pipeline import prepare_dataset
from portfolio_demo.engine import ANALYTIC_DATA, DATA, analyze_property, bootstrap, evaluate_synthetic_scope_holdouts, market_similarity


class PortfolioDemoTests(unittest.TestCase):
    def request(self, **kwargs):
        payload = {"property_id": "demo-101", **kwargs}
        return analyze_property(payload)

    def test_public_fixtures_are_explicitly_fictional(self):
        self.assertIn("fictional", DATA["data_notice"].lower())
        self.assertTrue(all(item["parcel"].startswith("DEMO-") for item in DATA["properties"]))
        self.assertTrue(all(item["id"].startswith("SIM-SCOPE-") for item in DATA["synthetic_scope_projects"]))

    def test_preparation_cleans_and_integrates_fictional_records(self):
        source = {**DATA, "properties": [dict(DATA["properties"][0], market_id=" NORTHLINE ")]}
        prepared = prepare_dataset(source)
        self.assertEqual(prepared["properties"][0]["market_id"], "northline")
        self.assertEqual(prepared["properties"][0]["market_name"], "Northline")
        self.assertEqual(prepared["properties"][0]["sales_count"], 3)
        self.assertEqual(prepared["quality"]["scope_project_rows"], 6)
        self.assertEqual(ANALYTIC_DATA["quality"]["property_rows"], 5)

    def test_preparation_rejects_unknown_market_and_conflicting_duplicate(self):
        bad_market = {**DATA, "properties": [dict(DATA["properties"][0], market_id="missing")]}
        with self.assertRaisesRegex(ValueError, "unknown market"):
            prepare_dataset(bad_market)
        conflict = {**DATA, "properties": [DATA["properties"][0], dict(DATA["properties"][0], sqft=1)]}
        with self.assertRaisesRegex(ValueError, "Conflicting duplicate"):
            prepare_dataset(conflict)
        market_conflict = {**DATA, "markets": [*DATA["markets"], dict(DATA["markets"][0], id=" NORTHLINE ", name="A conflicting market name")]}
        with self.assertRaisesRegex(ValueError, "Conflicting duplicate market"):
            prepare_dataset(market_conflict)

    def test_bootstrap_reports_fixture_counts(self):
        result = bootstrap()
        self.assertEqual(len(result["markets"]), 3)
        self.assertEqual(len(result["properties"]), 5)
        self.assertEqual(result["project_count"], 6)
        self.assertEqual(sum(m["property_count"] for m in result["markets"]), 5)

    def test_similarity_weights_are_interpretable_and_add_to_one(self):
        subject = DATA["properties"][0]
        project = DATA["synthetic_scope_projects"][0]
        score, features = market_similarity(subject, project)
        self.assertAlmostEqual(score, 97.6, places=1)
        self.assertEqual(sum((0.30, 0.15, 0.15, 0.25, 0.15)), 1.0)
        self.assertEqual(features["market"], 100.0)

    def test_scope_is_itemized_and_scenario_only(self):
        result = self.request()
        scope = result["scope"]
        self.assertGreater(len(scope["lines"]), 3)
        self.assertEqual(scope["total"], sum(row["base"] for row in scope["lines"]))
        self.assertTrue(all(row["evidence_class"] == "SYNTHETIC_SCENARIO_ONLY" for row in scope["lines"]))
        self.assertEqual(scope["analog_count"], 5)

    def test_basement_strategy_does_not_force_basement_on_property_without_one(self):
        result = analyze_property({"property_id": "demo-201", "strategy": "finished_basement"})
        self.assertNotIn("basement_finish", {line["category"] for line in result["scope"]["lines"]})

    def test_editable_scope_override_flows_into_project_uses(self):
        baseline = self.request()
        changed = self.request(scope_overrides={"kitchen": 5000})
        self.assertEqual(next(x for x in changed["scope"]["lines"] if x["category"] == "kitchen")["base"], 5000)
        self.assertNotEqual(baseline["scope"]["total"], changed["scope"]["total"])
        self.assertNotEqual(baseline["finance"]["metrics"]["project_uses"], changed["finance"]["metrics"]["project_uses"])

    def test_financial_metrics_recompute_from_explicit_scenario_inputs(self):
        self.assertEqual(self.request()["finance"]["inputs"]["vacancy_rate"], 0.081)
        base = self.request()["finance"]["metrics"]
        changed = self.request(financial_inputs={"monthly_rent": 1700})["finance"]["metrics"]
        self.assertGreater(changed["estimated_noi"], base["estimated_noi"])
        self.assertGreater(changed["monthly_cash_flow"], base["monthly_cash_flow"])
        self.assertGreater(changed["dscr"], base["dscr"])

    def test_project_uses_reconcile_into_named_components(self):
        result = self.request()
        metrics = result["finance"]["metrics"]
        components = metrics["project_uses_components"]
        self.assertEqual(sum(components.values()), metrics["project_uses"])
        self.assertEqual(components["purchase_price"], result["finance"]["inputs"]["purchase_price"])
        self.assertEqual(components["rehab_budget"], result["scope"]["total"])
        self.assertEqual(components["closing_costs"], metrics["closing_costs"])

    def test_synthetic_leave_one_out_evaluation_holds_out_whole_project(self):
        evaluation = evaluate_synthetic_scope_holdouts()
        self.assertIn("SYNTHETIC DEMONSTRATION ONLY", evaluation["label"])
        self.assertEqual(evaluation["project_count"], 6)
        self.assertEqual(len(evaluation["properties"]), 6)
        self.assertTrue(all(row["training_projects"] == 5 for row in evaluation["properties"]))
        self.assertIn("basement_finish", evaluation["excluded_categories"])
        self.assertEqual(len({row["held_out_project"] for row in evaluation["properties"]}), 6)
        self.assertIsNotNone(evaluation["aggregate"]["tracked_component_sum_mae"])

    def test_longer_construction_reduces_year_one_cash_flow_and_adds_carry_uses(self):
        cases = self.request()["timing"]
        self.assertEqual(len(cases), 2)
        self.assertLess(cases[1]["first_year_operating_cash_flow"], cases[0]["first_year_operating_cash_flow"])
        self.assertGreater(cases[1]["additional_uses"], cases[0]["additional_uses"])
        self.assertEqual(cases[0]["repair_months"], 1)
        self.assertEqual(cases[1]["repair_months"], 2)

    def test_bad_identifier_and_unsafe_inputs_fail_closed(self):
        with self.assertRaises(ValueError):
            analyze_property({"property_id": "a-real-address"})
        with self.assertRaises(ValueError):
            self.request(financial_inputs={"monthly_rent": -1})
        with self.assertRaises(ValueError):
            self.request(scope_overrides={"kitchen": -20})


if __name__ == "__main__":
    unittest.main()
