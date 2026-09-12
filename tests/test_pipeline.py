"""Behavioral regression tests over fresh fictional inputs, not private fixtures."""
from copy import deepcopy
from datetime import datetime, timezone
import json
import subprocess
import sys
import unittest
from unittest.mock import patch

from property_underwriting.demo import load_fixture, load_scenario, render_report
from property_underwriting.pipeline import run_pipeline, property_stage, condition_stage, rehab_stage
from property_underwriting.property import FactObservation, reconcile
from property_underwriting.condition.models import ComponentEvidence, ConditionConfig
from property_underwriting.condition.aggregate import prepare_evidence, aggregate_components
from property_underwriting.condition.taxonomy import taxonomy
from property_underwriting.rehab.scope import admit, build_scope, resolve_quantity
from property_underwriting.rehab.pricing import commit_price
from property_underwriting.rehab.selection import select_evidence
from property_underwriting.valuation.engine import value_property
from property_underwriting.rental.market import market_rent
from property_underwriting.rental.official import reference_economics, local_day
from property_underwriting.decision.engine import orchestrate


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.case = load_fixture()

    def test_populated_flow_keeps_synthetic_values_out_of_evidence_financials(self):
        r = run_pipeline(self.case, load_scenario())
        self.assertEqual(len(r['engines']), 6)
        self.assertEqual(r['engines']['ENGINE4']['accepted_comp_count'], 3)
        self.assertAlmostEqual(r['engines']['ENGINE4']['ARV_BASE'], 160000, delta=200)
        self.assertEqual(r['engines']['ENGINE3']['VISIBLE_REHAB_BASE'], 2000)
        self.assertIsNone(r['engines']['ENGINE6']['metrics']['NET_OPERATING_INCOME']['value'])
        self.assertEqual(r['scenario']['sources_and_uses']['status'], 'BALANCED')
        self.assertGreater(r['scenario']['metrics']['NET_OPERATING_INCOME']['value'], 0)
        self.assertFalse(r['decision']['acquisition_policy']['enabled'])
        self.assertEqual(r['decision']['real_evidence_decision_state'], 'DUE_DILIGENCE_REQUIRED')
        self.assertTrue(all(m['evidence_class'] == 'SCENARIO_ONLY' for m in r['scenario']['metrics'].values()))

    def test_insufficient_flow_abstains_without_fallback_rent(self):
        r = run_pipeline(load_fixture('insufficient'), load_scenario())
        self.assertIsNone(r['engines']['ENGINE4']['ARV_BASE'])
        self.assertIsNone(r['engines']['ENGINE3']['VISIBLE_REHAB_BASE'])
        self.assertIsNone(r['engines']['ENGINE5']['market_rent']['MARKET_RENT_BASE'])
        self.assertIsNone(r['scenario']['metrics']['NET_OPERATING_INCOME']['value'])
        self.assertGreater(len(r['decision']['hard_blockers']), 0)

    def test_identity_conflict_blocks_downstream_estimates(self):
        r = run_pipeline(load_fixture('identity-conflict'), load_scenario())
        self.assertEqual(r['decision']['decision_state'], 'BLOCKED_PROPERTY_IDENTITY')
        self.assertIsNone(r['engines']['ENGINE4']['ARV_BASE'])
        self.assertEqual(r['decision']['next_required_actions'][0]['action_id'], 'resolve_identity')

    def test_scenario_does_not_remove_blockers(self):
        a = run_pipeline(self.case)
        b = run_pipeline(self.case, load_scenario())
        self.assertEqual(a['decision']['hard_blockers'], b['decision']['hard_blockers'])
        self.assertEqual(a['decision']['real_evidence_decision_state'], b['decision']['real_evidence_decision_state'])

    def test_input_is_not_mutated_and_output_is_deterministic(self):
        original = deepcopy(self.case)
        a = run_pipeline(self.case, load_scenario())
        self.assertEqual(self.case, original)
        self.assertEqual(a, run_pipeline(self.case, load_scenario()))
        json.dumps(a, allow_nan=False)

    def test_no_network_calls(self):
        with patch('socket.socket', side_effect=AssertionError('Network forbidden')):
            run_pipeline(self.case, load_scenario())

    def test_real_data_mode_rejected(self):
        self.case['synthetic'] = False
        with self.assertRaisesRegex(ValueError, 'synthetic'):
            run_pipeline(self.case)

    def test_property_mismatch_rejected(self):
        self.case['observations'][0]['property_id'] = 'DIFFERENT_SYNTHETIC_PROPERTY'
        with self.assertRaisesRegex(ValueError, 'different property'):
            run_pipeline(self.case)

    def test_condition_mismatch_rejected(self):
        self.case['condition_evidence'][0]['property_id'] = 'DIFFERENT_SYNTHETIC_PROPERTY'
        with self.assertRaisesRegex(ValueError, 'different property'):
            run_pipeline(self.case)

    def test_missing_area_abstains(self):
        self.case['observations'] = self.case['observations'][1:]
        r = run_pipeline(self.case)
        self.assertIsNone(r['engines']['ENGINE4']['ARV_BASE'])
        self.assertEqual(r['engines']['ENGINE1']['missing_required_facts'], ['living_area_sqft'])

    def test_future_observation_excluded(self):
        self.case['observations'][0]['effective_date'] = '2099-01-01'
        r = property_stage(self.case)
        self.assertNotIn('living_area_sqft', r['canonical_facts'])
        self.assertEqual(len(r['excluded_observations']), 1)

    def test_failed_source_value_not_selected(self):
        self.case['observations'][0]['status'] = 'SOURCE_UNAVAILABLE'
        self.assertNotIn('living_area_sqft', property_stage(self.case)['canonical_facts'])

    def test_duplicate_observation_id_rejected(self):
        self.case['observations'].append(deepcopy(self.case['observations'][0]))
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            run_pipeline(self.case)

    def test_readiness_rejects_cross_engine_identity_drift(self):
        r = run_pipeline(self.case)
        r['engines']['ENGINE3']['property_id'] = 'DIFFERENT_SYNTHETIC_PROPERTY'
        with self.assertRaisesRegex(ValueError, 'identity mismatch'):
            orchestrate(r['engines'])

    def test_readiness_rejects_scenario_as_evidence(self):
        r = run_pipeline(self.case, load_scenario())
        r['engines']['ENGINE6'] = r['scenario']
        with self.assertRaisesRegex(ValueError, 'evidence required'):
            orchestrate(r['engines'])

    def test_readiness_rejects_unknown_contract(self):
        r = run_pipeline(self.case)
        r['engines']['ENGINE4']['contract_version'] = 'unsupported'
        with self.assertRaisesRegex(ValueError, 'Unsupported'):
            orchestrate(r['engines'])

    def test_readiness_unknown_status_fails_closed(self):
        r = run_pipeline(self.case)
        r['engines']['ENGINE4']['status']['COMP_SET_STATUS'] = 'NEW_UNRECOGNIZED_STATUS'
        d = orchestrate(r['engines'])
        self.assertEqual(d['domain_readiness']['VALUATION']['status'], 'BLOCKED')

    def test_report_discloses_synthetic_and_exclusions(self):
        report = render_report(run_pipeline(self.case, load_scenario()))
        self.assertIn('fictional', report)
        self.assertIn('does not clear blockers', report)
        self.assertIn('DISABLED', report)
        self.assertIn('depends on:', report)

    def test_cli_json_is_parseable(self):
        result = subprocess.run([sys.executable, '-m', 'property_underwriting.demo', '--case', 'insufficient', '--json'],
                                check=True, capture_output=True, text=True)
        self.assertTrue(json.loads(result.stdout)['synthetic'])


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.case = load_fixture()
        self.as_of = datetime(2026, 1, 15, tzinfo=timezone.utc)

    def test_same_authority_conflict_does_not_select_arbitrary_value(self):
        original = self.case['observations'][0]
        other = dict(original, normalized_value=1800, observation_id='synthetic:conflict')
        selected, conflicts = reconcile([FactObservation(**original), FactObservation(**other)])
        self.assertNotIn('living_area_sqft', selected)
        self.assertEqual(conflicts[0]['severity'], 'STOP')

    def condition(self, rows):
        prepared = prepare_evidence([ComponentEvidence(**r) for r in rows], [], taxonomy(), ConditionConfig(), self.as_of)
        return {r['component_id']: r for r in aggregate_components(prepared, taxonomy(), ConditionConfig())}

    def test_hidden_systems_remain_unknown_without_inspection(self):
        rows = self.condition(self.case['condition_evidence'])
        self.assertEqual(rows['systems.concealed_wiring']['condition'], 'UNKNOWN')
        self.assertTrue(rows['systems.concealed_wiring']['inspection_required'])

    def test_stale_condition_evidence_does_not_clear_inspection(self):
        row = deepcopy(self.case['condition_evidence'][0]); row['observed_at'] = '2020-01-01T00:00:00Z'
        self.assertEqual(self.condition([row])['interior.paint']['condition'], 'UNKNOWN')

    def test_conflicting_condition_evidence_not_majority_vote(self):
        row = self.case['condition_evidence'][0]
        other = dict(row, evidence_id='synthetic:conflict', condition='GOOD', action='KEEP_NO_WORK')
        result = self.condition([row, other])['interior.paint']
        self.assertEqual(result['condition'], 'UNKNOWN')
        self.assertTrue(result['inspection_required'])

    def test_reported_text_is_context_not_inspection(self):
        row = dict(self.case['condition_evidence'][0], source_kind='STRUCTURED_REPORTED')
        self.assertEqual(self.condition([row])['interior.paint']['condition'], 'UNKNOWN')

    def test_duplicate_price_cannot_double_count_scope(self):
        e1 = property_stage(self.case); e2 = condition_stage(self.case, e1, self.as_of)
        groups = build_scope(admit(e2)); quote = self.case['quotes'][0]; chosen = []
        ids = [g['scope_group_id'] for g in groups if g['operation'] == quote['operation']]
        selection = select_evidence(None, manual=quote['evidence'])
        commit_price(groups, chosen, ids, selection, operation=quote['operation'], boundary=quote['boundary'], coverage_reviewed=True)
        with self.assertRaisesRegex(ValueError, 'overlap'):
            commit_price(groups, chosen, ids, selection, operation=quote['operation'], boundary=quote['boundary'], coverage_reviewed=True)

    def test_unknown_scope_cannot_be_priced(self):
        e1 = property_stage(self.case); e2 = condition_stage(self.case, e1, self.as_of)
        groups = build_scope(admit(e2)); quote = self.case['quotes'][0]
        ids = [next(g['scope_group_id'] for g in groups if g['bucket'] == 'UNRESOLVED_MAJOR_EXPOSURE')]
        with self.assertRaisesRegex(ValueError, 'Cannot price unknown'):
            commit_price(groups, [], ids, select_evidence(None, manual=quote['evidence']), operation='invalid', boundary='synthetic', coverage_reviewed=True)

    def test_assessor_area_not_component_geometry(self):
        candidate = dict(basis='AUTHORITATIVE_PROPERTY_PROXY', review_status='REVIEWED', evidence_level='A',
                         source_ids=['synthetic:area'], compatible_operations=['paint'], unit='sqft', value=1200)
        result = resolve_quantity([candidate], 'paint')
        self.assertIsNone(result['value'])
        self.assertEqual(result['rejected'][0]['reason'], 'ASSESSOR_AREA_IS_NOT_COMPONENT_GEOMETRY')

    def test_duplicate_sales_do_not_increase_count(self):
        sales = self.case['sale_comps']; duplicate = dict(sales[0], comp_id='synthetic:duplicate')
        r = value_property(self.case['subject'], sales + [duplicate], valuation_date=self.case['as_of'])
        self.assertEqual(r['accepted_comp_count'], 3)
        self.assertEqual(r['duplicate_occurrence_count'], 1)

    def test_future_sale_cannot_support_arv(self):
        self.case['sale_comps'][0]['sale_date'] = '2099-01-01'
        r = value_property(self.case['subject'], self.case['sale_comps'], valuation_date=self.case['as_of'])
        self.assertIsNone(r['ARV_BASE'])
        self.assertIn('FUTURE_SALE', r['rejected_comps'][0]['exclusions'])

    def test_conflicting_duplicate_sales_rejected(self):
        sales = self.case['sale_comps']; duplicate = dict(sales[0], comp_id='synthetic:duplicate', sale_price=999999)
        r = value_property(self.case['subject'], sales + [duplicate], valuation_date=self.case['as_of'])
        self.assertIsNone(r['ARV_BASE'])

    def test_asking_rent_stays_partial(self):
        r = market_rent(self.case['subject'], self.case['rental_comps'], self.as_of.date())
        self.assertEqual(r['status'], 'PARTIAL')
        self.assertEqual(r['range_basis'], 'ASKING')

    def test_duplicate_rentals_do_not_increase_count(self):
        rows = self.case['rental_comps']; duplicate = dict(rows[0], comp_id='synthetic:duplicate')
        r = market_rent(self.case['subject'], rows + [duplicate], self.as_of.date())
        self.assertEqual(r['accepted_comp_count'], 3)
        self.assertEqual(len(r['duplicate_occurrences']), 1)

    def test_unverified_achieved_rent_rejected(self):
        rows = [dict(r, rent_basis='CONTRACT_RENT', verified_rent=1250) for r in self.case['rental_comps']]
        r = market_rent(self.case['subject'], rows, self.as_of.date())
        self.assertIsNone(r['MARKET_RENT_BASE'])

    def test_hcv_arithmetic_does_not_approve_contract_rent(self):
        r = reference_economics({'status': 'AVAILABLE', 'payment_standard_amount': 1500},
            {'status': 'SELECTED_REFERENCE_NOT_PHA_APPROVED', 'tenant_paid_utility_allowance': 100})
        self.assertEqual(r['payment_standard_minus_known_tenant_utilities_reference'], 1400)
        self.assertIsNone(r['approved_hcv_contract_rent'])

    def test_utc_date_is_machine_timezone_independent(self):
        self.assertEqual(str(local_day('2026-01-15T23:30:00-08:00')), '2026-01-16')


if __name__ == '__main__':
    unittest.main()
