"""Tests for the public synthetic financial-underwriting demonstration."""

import unittest


from property_underwriting.financial.engine import calculate
from property_underwriting.financial.inputs import observation


class FinancialEngineTests(unittest.TestCase):

    def scenario_input(self, name, value, *, coverage="COMPLETE"):
        return observation(
            name,
            value,
            evidence_class="SCENARIO_ONLY",
            source={"kind": "SYNTHETIC_TEST"},
            effective_date=None,
            accepted=True,
            coverage=coverage,
        )

    def test_unknown_values_do_not_become_zero(self):
        result = calculate(
            {},
            mode="EVIDENCE_MODE",
            property_id="TEST_PROPERTY",
        )

        self.assertIsNone(
            result["metrics"]["NET_OPERATING_INCOME"]["value"]
        )

        self.assertEqual(
            result["metrics"]["NET_OPERATING_INCOME"]["status"],
            "NOT_READY",
        )

    def test_hcv_payment_standard_is_not_treated_as_rent(self):
        inputs = {
            "payment_standard_reference": observation(
                "payment_standard_reference",
                1500,
                evidence_class="REFERENCE_ONLY",
                source={"kind": "PAYMENT_STANDARD"},
                accepted=True,
            )
        }

        result = calculate(
            inputs,
            mode="EVIDENCE_MODE",
            property_id="TEST_PROPERTY",
        )

        self.assertIsNone(result["selected_revenue_source"])
        self.assertIsNone(
            result["metrics"]["GROSS_POTENTIAL_RENT"]["value"]
        )

    def test_partial_rehab_cannot_be_used_as_total_rehab(self):
        inputs = {
            "initial_rehab": observation(
                "initial_rehab",
                10000,
                evidence_class="ESTIMATED",
                source={"kind": "PARTIAL_VISIBLE_SCOPE_ONLY"},
                accepted=True,
                coverage="PARTIAL",
            )
        }

        result = calculate(
            inputs,
            mode="EVIDENCE_MODE",
            property_id="TEST_PROPERTY",
        )

        self.assertIsNone(
            result["metrics"]["TOTAL_PROJECT_COST"]["value"]
        )


if __name__ == "__main__":
    unittest.main()