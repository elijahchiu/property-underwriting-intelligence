"""Offline synthetic integration of the seven engines.

This entry point deliberately cannot certify a real property. Source authority and
review labels describe fictional roles inside the fixture, never real verification.
"""
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json

from .property import FactObservation, reconcile
from .condition.models import ComponentEvidence, ConditionConfig
from .condition.taxonomy import taxonomy
from .condition.aggregate import prepare_evidence, aggregate_components
from .rehab.scope import build_scope, admit
from .rehab.selection import select_evidence
from .rehab.pricing import commit_price, totals
from .rehab.common import dollars
from .valuation.engine import value_property
from .rental.market import market_rent
from .rental.official import reference_economics
from .financial.engine import calculate
from .financial.inputs import observation, scenario_inputs
from .decision.engine import orchestrate


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def property_stage(case):
    pid = case['property_id']
    observations = [FactObservation.model_validate(row) for row in case['observations']]
    if any(o.property_id != pid for o in observations):
        raise ValueError('Observation belongs to a different property')
    if len({o.observation_id for o in observations}) != len(observations):
        raise ValueError('Duplicate observation identifiers')
    as_of = datetime.fromisoformat(case['as_of']).date()
    admitted, excluded = [], []
    for row in observations:
        try:
            effective = datetime.fromisoformat(row.effective_date).date()
            retrieved = datetime.fromisoformat(row.retrieved_at.replace('Z', '+00:00')).date()
            valid = effective <= as_of and retrieved <= as_of
        except (TypeError, ValueError):
            valid = False
        if row.status == 'AVAILABLE' and row.source_scope == 'CURRENT' and valid:
            admitted.append(row)
        else:
            excluded.append(row.model_dump(mode='json'))
    selected, conflicts = reconcile(admitted)
    required = {'living_area_sqft', 'bedrooms', 'bathrooms', 'year_built', 'property_type'}
    missing = sorted(required - selected.keys())
    blocked = any(c['severity'] == 'STOP' for c in conflicts)
    identity = case['identity_status'] == 'RESOLVED' and not blocked
    facts = {k: v.model_dump(mode='json') for k, v in selected.items()}
    domains = {
        'IDENTITY_SUFFICIENCY': {'status': 'PASS' if identity else 'BLOCKED'},
        'PROPERTY_FACTS_SUFFICIENCY': {'status': 'INSUFFICIENT' if missing else 'PASS_WITH_WARNINGS' if conflicts else 'PASS'},
        'REGULATORY_SUFFICIENCY': {'status': case['regulatory_status']},
        'HAZARD_SUFFICIENCY': {'status': case['hazard_status']},
    }
    return dict(engine_version='engine1-official-0.2.0', identity=dict(property_id=pid, status='RESOLVED' if identity else 'UNRESOLVED'),
                parcel_resolution=dict(status='RESOLVED' if identity else 'UNRESOLVED'), canonical_facts=facts,
                observations=[o.model_dump(mode='json') for o in observations], excluded_observations=excluded,
                conflicts=conflicts, missing_required_facts=missing, domain_sufficiency=domains,
                source='SYNTHETIC_FIXTURE', live_calls=0)


def condition_stage(case, property_result, as_of):
    config = ConditionConfig()
    components = taxonomy()
    evidence = [ComponentEvidence.model_validate(e) for e in case['condition_evidence']]
    if any(e.property_id != case['property_id'] for e in evidence):
        raise ValueError('Condition evidence belongs to a different property')
    if len({e.evidence_id for e in evidence}) != len(evidence):
        raise ValueError('Duplicate condition evidence identifiers')
    prepared = prepare_evidence(evidence, [], components, config, as_of)
    aggregated = aggregate_components(prepared, components, config)
    reviewed = []
    for c in aggregated:
        row = deepcopy(c)
        row.update(component_instance_id=c['component_id'] + ':synthetic-instance', room_instance_id='synthetic-room',
                   media_ids=c['supporting_media_ids'], review_origin='SYNTHETIC_REVIEW',
                   inspection_items=[c['component_id']] if c['inspection_required'] else [],
                   conflicts=c['contradictory_evidence_ids'], visible_coverage=c['observable_coverage'],
                   disposition='INSPECTION_BEFORE_SCOPE' if c['inspection_required'] else 'REVIEWED',
                   evidence_ids=c['evidence_ids'] or ['synthetic:missing-evidence:' + c['component_id']])
        reviewed.append(row)
    return dict(contract_version='engine2-reviewed-development-handoff-0.3.0', property_id=case['property_id'],
                acceptance_status='READY', engine3_development='READY', unresolved_development_blockers=[],
                components=reviewed, prepared_evidence=prepared, review_origin='SYNTHETIC_REVIEW',
                hidden_systems_requiring_inspection=[c['component_id'] for c in reviewed if c['inspection_required']],
                visible_severity={'status': 'PARTIAL_COMPONENT_REVIEW', 'whole_property_rating': None},
                special_review_flags=['SYNTHETIC_NOT_REAL_INSPECTION'], media_coverage={'photos': 0, 'status': 'NO_MEDIA'},
                unknown_capture_dates=True, automated_vision_validation='NOT_ESTABLISHED', production_handoff_accepted=False,
                source_engine1_context={'research_projection': {'physical_facts': property_result['canonical_facts']},
                                        'source_sha256': digest(property_result)})


def rehab_stage(case, condition):
    groups = build_scope(admit(condition))
    chosen = []
    for quote in case['quotes']:
        covered = [g['scope_group_id'] for g in groups if g['operation'] == quote['operation']]
        if not covered:
            raise ValueError('Quote does not match any supported scope')
        selection = select_evidence(None, manual=quote['evidence'])
        commit_price(groups, chosen, covered, selection, operation=quote['operation'],
                     boundary=quote['boundary'], coverage_reviewed=True)
    ledger = totals(groups, chosen)
    span = ledger['preliminary_rehab_range']
    major = [g for g in groups if g['bucket'] == 'UNRESOLVED_MAJOR_EXPOSURE']
    return dict(contract_version='engine3-preliminary-rehab-0.2.0', property_id=case['property_id'],
                status={'PHYSICAL_INSPECTION_REQUIRED': any(g['inspection_required'] for g in groups),
                        'VISIBLE_SCOPE_PRICING': 'PARTIAL' if chosen else 'INSUFFICIENT'},
                VISIBLE_REHAB_LOW=dollars(span['low']) if span else None,
                VISIBLE_REHAB_BASE=dollars(span['base']) if span else None,
                VISIBLE_REHAB_HIGH=dollars(span['high']) if span else None,
                unresolved_major_exposure_count=len(major), unresolved_major_exposure=major,
                confidence='LOW' if chosen else 'INSUFFICIENT',
                estimate_label='PARTIAL_SCOPE_ONLY_EXCLUDES_UNPRICED_AND_HIDDEN_WORK',
                scope_groups=groups, cost_lines=chosen, totals=ledger, source_handoff_semantic_sha256=digest(condition))


def run_pipeline(case, financial_scenario=None):
    case = deepcopy(case)
    if case.get('synthetic') is not True:
        raise ValueError('This public integration accepts synthetic demonstrations only')
    as_of = datetime.fromisoformat(case['as_of']).replace(tzinfo=timezone.utc)
    e1 = property_stage(case)
    e2 = condition_stage(case, e1, as_of)
    e3 = rehab_stage(case, e2)
    subject = deepcopy(case['subject'])
    if subject['property_id'] != case['property_id']:
        raise ValueError('Subject identity mismatch')
    fields = {'living_sqft': 'living_area_sqft', 'beds': 'bedrooms', 'baths': 'bathrooms',
              'year_built': 'year_built', 'property_type': 'property_type'}
    for target, source in fields.items():
        fact = e1['canonical_facts'].get(source)
        subject[target] = fact['normalized_value'] if fact else None
    usable_subject = (e1['identity']['status'] == 'RESOLVED' and not e1['missing_required_facts'])
    if usable_subject:
        e4 = value_property(subject, case['sale_comps'], valuation_date=case['as_of'])
        market = market_rent(subject, case['rental_comps'], as_of.date())
    else:
        e4 = dict(contract_version='engine4-sale-valuation-0.1.0', subject=subject,
                  ARV_BASE=None, ARV_CONFIDENCE='INSUFFICIENT', accepted_comp_count=0,
                  status={'COMP_SET_STATUS': 'BLOCKED'}, reason='Identity or required facts unresolved')
        market = dict(status='INSUFFICIENT', MARKET_RENT_BASE=None, accepted_comp_count=0,
                      reason='Identity or required facts unresolved')
    payment = dict(status='AVAILABLE' if case['payment_standard'] is not None else 'UNAVAILABLE',
                   payment_standard_amount=case['payment_standard'], source='SYNTHETIC_REFERENCE')
    utility = dict(status='NOT_SELECTED', utility_responsibility_status='UNKNOWN', tenant_paid_utility_allowance=None)
    e5 = dict(contract_version='engine5-rent-hcv-0.1.0', subject=subject, market_rent=market,
              pha={'status': 'NOT_RESOLVED', 'reason': 'No real jurisdiction in synthetic demo'},
              hcv_payment_standard=payment, utility_allowance=utility, APPROVED_HCV_CONTRACT_RENT=None,
              rent_reasonableness={'status': 'NOT_APPROVED'}, inspection_status={'status': 'NOT_APPROVED'},
              reference_economics=reference_economics(payment, utility, market['MARKET_RENT_BASE']))
    # Synthetic calculations remain reference-only in the evidence financial path.
    inputs = {}
    for name, value, engine, pointer in (
        ('ARV', e4['ARV_BASE'], 'ENGINE4', '/ARV_BASE'),
        ('monthly_market_rent', market['MARKET_RENT_BASE'], 'ENGINE5', '/market_rent/MARKET_RENT_BASE'),
        ('partial_visible_rehab_reference', e3['VISIBLE_REHAB_BASE'], 'ENGINE3', '/VISIBLE_REHAB_BASE'),
        ('payment_standard_reference', case['payment_standard'], 'ENGINE5', '/hcv_payment_standard/payment_standard_amount')):
        inputs[name] = observation(name, value, evidence_class='REFERENCE_ONLY',
                                   source={'engine': engine, 'json_pointer': pointer, 'kind': 'SYNTHETIC_REFERENCE'},
                                   effective_date=case['as_of'], accepted=True, coverage='PARTIAL')
    e6 = calculate(inputs, property_id=case['property_id'])
    e6['subject'] = deepcopy(subject)
    scenario = None
    if financial_scenario is not None:
        assumptions = scenario_inputs(financial_scenario, case['property_id'])
        for name, value, source_engine in [('monthly_scenario_rent', market['MARKET_RENT_BASE'], 'ENGINE5'),
                                           ('ARV', e4['ARV_BASE'], 'ENGINE4')]:
            # No fallback rent when the synthetic comp set is insufficient.
            assumptions[name] = observation(name, value, evidence_class='SCENARIO_ONLY',
                source={'kind': 'SYNTHETIC_COMPUTED_ASSUMPTION', 'engine': source_engine}, accepted=True,
                effective_date=case['as_of'], coverage='COMPLETE')
        scenario = calculate(assumptions, mode='SCENARIO_MODE', property_id=case['property_id'])
        scenario.update(subject=deepcopy(subject), baseline_evidence_inputs=deepcopy(e6['inputs']),
                        source_handoffs=None, operator_confirmed=True, scenario_name=financial_scenario['scenario_name'])
    records = dict(ENGINE1=e1, ENGINE2=e2, ENGINE3=e3, ENGINE4=e4, ENGINE5=e5, ENGINE6=e6)
    for record in records.values():
        record['synthetic'] = True
    sources = {engine: {'path': None, 'sha256': digest(record)} for engine, record in records.items()}
    e7 = orchestrate(records, sources=sources, scenario=scenario)
    return dict(schema_version='public-demo-1', synthetic=True, live_calls=0, as_of=case['as_of'],
                warning='All facts, reviews, quotes and comparables are fictional. No real property is verified.',
                fixture_sha256=digest(case), engines=records, scenario=scenario, decision=e7)
