"""Explicit operator scenarios and deterministic one-at-a-time variations."""
from copy import deepcopy
from .inputs import scenario_inputs, normalize
from .engine import calculate

IMPACTS=('NET_OPERATING_INCOME','DSCR','ANNUAL_CASH_FLOW','CASH_ON_CASH_RETURN')


def build_scenario(evidence,payload):
    overrides=scenario_inputs(payload,evidence['property_id'])
    inputs=deepcopy(evidence['inputs']);inputs.update(overrides)
    result=calculate(inputs,mode='SCENARIO_MODE',property_id=evidence['property_id'])
    result.update(scenario_name=payload['scenario_name'],operator_confirmed=True,scenario_overrides=deepcopy(overrides),
        baseline_evidence_inputs=deepcopy(evidence['inputs']),subject=deepcopy(evidence.get('subject')),
        source_handoffs=deepcopy(evidence.get('source_handoffs',[])),as_of=evidence.get('as_of'),
        upstream_context=deepcopy(evidence.get('upstream_context',{})),
        real_evidence_profile_status=evidence['FINANCIAL_PROFILE_STATUS'],live_calls=0)
    result['sensitivities']=sensitivities(result)
    result['stress_scenario']=stress(result,payload.get('stress_overrides'))
    return result


def sensitivities(base):
    required=('NET_OPERATING_INCOME','ANNUAL_CASH_FLOW','TOTAL_PROJECT_COST','TOTAL_CASH_INVESTED','DEBT_SERVICE')
    ready=base['mode']=='SCENARIO_MODE' and base['selected_revenue_source']=='monthly_scenario_rent' and all(base['metrics'][k]['status']=='READY' for k in required)
    if not ready:
        return dict(status='NOT_READY',evidence_class='SCENARIO_ONLY',cases=[],reason='Complete funded operator-rent scenario with applicable debt/return metrics required')
    varied_fields=['initial_rehab','vacancy_rate','equity_contribution']
    if base['inputs']['loan_amount']['value']!=0: varied_fields.append('interest_rate')
    if any(base['inputs'][k]['evidence_class']!='SCENARIO_ONLY' for k in varied_fields):
        return dict(status='NOT_READY',evidence_class='SCENARIO_ONLY',cases=[],reason='Varied rehab, vacancy, senior rate and equity inputs must be deliberate scenario assumptions')
    cases=[]
    # Explicit method, not an invented loan draw: hold funded debt constant and
    # change aggregate scenario equity by exactly the change in project uses.
    for label,field,factor,increment in (
        ('BASE',None,1,0),('RENT_MINUS_10_PERCENT','monthly_scenario_rent',.9,0),('RENT_PLUS_10_PERCENT','monthly_scenario_rent',1.1,0),
        ('REHAB_PLUS_10_PERCENT','initial_rehab',1.1,0),('REHAB_PLUS_20_PERCENT','initial_rehab',1.2,0),
        ('VACANCY_PLUS_5_PERCENTAGE_POINTS','vacancy_rate',1,.05),('SENIOR_RATE_PLUS_100_BPS','interest_rate',1,.01)):
        inputs=deepcopy(base['inputs']);changes={}
        if field=='interest_rate' and inputs['loan_amount']['value']==0:
            cases.append(dict(case=label,status='NOT_APPLICABLE',evidence_class='SCENARIO_ONLY',changes={},metrics={},reason='No senior loan; no rate assumption invented'))
            continue
        if field:
            old=inputs[field]['value'];new=old*factor+increment
            inputs[field].update(value=new,source=dict(kind='SCENARIO_SENSITIVITY',base_source=inputs[field]['source'],case=label),evidence_class='SCENARIO_ONLY')
            changes[field]=dict(before=old,after=new)
            if field=='initial_rehab':
                old_equity=inputs['equity_contribution']['value']
                inputs['equity_contribution'].update(value=old_equity+new-old,
                    source=dict(kind='SCENARIO_SENSITIVITY',case=label,policy='Incremental project uses funded entirely by incremental aggregate equity'),evidence_class='SCENARIO_ONLY')
                changes['equity_contribution']=dict(before=old_equity,after=old_equity+new-old)
        try:
            varied=calculate(inputs,mode='SCENARIO_MODE',property_id=base['property_id'])
            cases.append(dict(case=label,evidence_class='SCENARIO_ONLY',changes=changes,metrics={k:varied['metrics'][k] for k in IMPACTS},sources_and_uses=varied['sources_and_uses']))
        except ValueError as exc:
            cases.append(dict(case=label,status='NOT_READY',evidence_class='SCENARIO_ONLY',changes=changes,reason=str(exc),metrics={}))
    return dict(status='READY',evidence_class='SCENARIO_ONLY',method='One-at-a-time deterministic variations, not probabilities',
        funding_policy='Debt proceeds, seller financing and other capital held constant; rehab delta funded by equal incremental scenario equity. Financing fees and other uses held fixed.',cases=cases)


def stress(base,overrides):
    if overrides is None: return dict(status='NOT_REQUESTED',evidence_class='SCENARIO_ONLY',scenario=None)
    if base['mode']!='SCENARIO_MODE' or not isinstance(overrides,dict) or not overrides: raise ValueError('Explicit nonempty scenario stress overrides required')
    normalize(overrides)
    if any(item.get('evidence_class')!='SCENARIO_ONLY' or item.get('accepted') is not True or not item.get('source') for item in overrides.values()):
        raise ValueError('Stress assumptions require SCENARIO_ONLY, acceptance and operator source')
    inputs=deepcopy(base['inputs']);inputs.update(deepcopy(overrides))
    result=calculate(inputs,mode='SCENARIO_MODE',property_id=base['property_id'])
    return dict(status='STRESS_SCENARIO',evidence_class='SCENARIO_ONLY',operator_overrides=deepcopy(overrides),scenario=result,
        warning='Operator-defined stress, not downside probability; funding mismatch is retained, not automatically repaired')
