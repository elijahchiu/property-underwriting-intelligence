from copy import deepcopy
from hashlib import sha256
import json

VERSIONS = {
    'ENGINE1': ('engine_version', 'engine1-official-0.2.0'),
    'ENGINE2': ('contract_version', 'engine2-reviewed-development-handoff-0.3.0'),
    'ENGINE3': ('contract_version', 'engine3-preliminary-rehab-0.2.0'),
    'ENGINE4': ('contract_version', 'engine4-sale-valuation-0.1.0'),
    'ENGINE5': ('contract_version', 'engine5-rent-hcv-0.1.0'),
    'ENGINE6': ('contract_version', 'engine6-financial-0.1.0'),
}
DOMAINS = ('PROPERTY_DATA','CONDITION','REHAB','VALUATION','RENT_HCV','FINANCIALS')
STATES = ('BLOCKED_PROPERTY_IDENTITY','DUE_DILIGENCE_REQUIRED','CONDITION_REVIEW_REQUIRED',
          'UNDERWRITING_DATA_INCOMPLETE','READY_FOR_FINANCIAL_REVIEW','READY_FOR_DECISION','SCENARIO_ONLY_REVIEW')
# Only recognized upstream statuses may be mapped. Unknown states fail closed.
MAPPING = {'PASS':'READY','READY':'READY','COMPLETE_EVIDENCE':'READY',
           'PASS_WITH_WARNINGS':'PARTIAL','REVIEW_REQUIRED':'PARTIAL','PARTIAL':'PARTIAL','PARTIAL_EVIDENCE':'PARTIAL',
           'INSUFFICIENT':'INSUFFICIENT','NOT_READY':'INSUFFICIENT','BLOCKED':'BLOCKED'}
REQUIRED = {
    'ENGINE1': ['/identity/status','/identity/property_id','/parcel_resolution/status','/domain_sufficiency',
        '/domain_sufficiency/IDENTITY_SUFFICIENCY/status','/domain_sufficiency/PROPERTY_FACTS_SUFFICIENCY/status',
        '/domain_sufficiency/REGULATORY_SUFFICIENCY/status','/domain_sufficiency/HAZARD_SUFFICIENCY/status'],
    'ENGINE2': ['/property_id','/acceptance_status','/components','/hidden_systems_requiring_inspection','/visible_severity',
        '/special_review_flags','/media_coverage','/review_origin','/unknown_capture_dates','/automated_vision_validation','/production_handoff_accepted'],
    'ENGINE3': ['/property_id','/status/PHYSICAL_INSPECTION_REQUIRED','/status/VISIBLE_SCOPE_PRICING','/unresolved_major_exposure_count',
        '/unresolved_major_exposure','/VISIBLE_REHAB_BASE','/VISIBLE_REHAB_LOW','/VISIBLE_REHAB_HIGH','/confidence','/estimate_label'],
    'ENGINE4': ['/subject/property_id','/status/COMP_SET_STATUS','/ARV_BASE','/ARV_CONFIDENCE','/accepted_comp_count'],
    'ENGINE5': ['/subject/property_id','/market_rent/status','/market_rent/MARKET_RENT_BASE','/pha','/hcv_payment_standard/payment_standard_amount',
        '/APPROVED_HCV_CONTRACT_RENT','/utility_allowance/status','/utility_allowance/utility_responsibility_status','/rent_reasonableness/status','/inspection_status/status'],
    'ENGINE6': ['/property_id','/subject','/mode','/gates','/metrics','/inputs/purchase_price','/inputs/initial_rehab',
        '/FINANCIAL_PROFILE_STATUS','/KEY_FINANCIAL_RISKS','/selected_revenue_source','/sources_and_uses','/status/SCENARIO_ENGINE'],
}


def pointer(document,path):
    value=document
    try:
        for key in path.lstrip('/').split('/'):
            key=key.replace('~1','/').replace('~0','~')
            value=value[int(key)] if isinstance(value,list) else value[key]
    except (KeyError,IndexError,TypeError,ValueError) as exc:
        raise ValueError('Missing/invalid upstream field '+path) from exc
    return value


def admit(records):
    if set(records)!=set(VERSIONS): raise ValueError('Exactly Engines 1–6 required')
    for engine,(field,version) in VERSIONS.items():
        if records[engine].get(field)!=version: raise ValueError('Unsupported '+engine+' contract')
        for path in REQUIRED[engine]: pointer(records[engine],path)
    e1,e2,e3,e4,e5,e6=(records[k] for k in VERSIONS)
    ids=[e2['property_id'],e3['property_id'],e4['subject']['property_id'],e5['subject']['property_id'],e6['property_id'],e6['subject']['property_id']]
    if e1['identity']['property_id'] is not None: ids.append(e1['identity']['property_id'])
    if not ids[0] or len(set(ids))!=1: raise ValueError('Cross-engine property identity mismatch')
    if e4['subject']!=e5['subject'] or e5['subject']!=e6['subject']: raise ValueError('Cross-engine subject context drift')
    if e6['mode']!='EVIDENCE_MODE': raise ValueError('Real Engine 6 evidence required separately from any scenario')
    for name in ('REVENUE','REHAB_COST','OPERATING_EXPENSE','DEBT','VALUE'):
        pointer(e6,'/gates/'+name+'_SUFFICIENCY/status')
    for name in ('NET_OPERATING_INCOME','TOTAL_PROJECT_COST','TOTAL_CASH_INVESTED','DEBT_SERVICE','DSCR','CASH_ON_CASH_RETURN'):
        pointer(e6,'/metrics/'+name)
    for metric in e6['metrics'].values():
        if not {'value','status','evidence_class','source_inputs','formula','warnings'}<=set(metric): raise ValueError('Incomplete financial metric provenance')
        if metric['evidence_class']=='SCENARIO_ONLY': raise ValueError('Scenario metric cannot masquerade as real evidence')
    if not isinstance(e2['components'],list) or not e2['components']: raise ValueError('Condition components required')
    for component in e2['components']:
        if not {'component_id','inspection_required','condition','hidden_risk','evidence_ids','media_ids'}<=set(component): raise ValueError('Incomplete component contract')
        if not isinstance(component['inspection_required'],bool): raise ValueError('Explicit component inspection flag required')
    if not isinstance(e3['status']['PHYSICAL_INSPECTION_REQUIRED'],bool): raise ValueError('Explicit physical inspection flag required')
    if not isinstance(e3['unresolved_major_exposure'],list) or e3['unresolved_major_exposure_count']!=len(e3['unresolved_major_exposure']):
        raise ValueError('Inconsistent upstream exposure count; do not reconcile silently')
    return ids[0]


def orchestrate(records,*,sources=None,scenario=None,scenario_source=None):
    property_id=admit(records)
    a,b,c,d,e,f=(records[k] for k in VERSIONS)
    semantic_hashes={engine:sha256(json.dumps(record,sort_keys=True).encode()).hexdigest() for engine,record in records.items()}
    def ref(engine,path):
        return dict(engine=engine,json_pointer=path,value=deepcopy(pointer(records[engine],path)),
            **((sources or {}).get(engine) or dict(path=None,sha256=None)),
            semantic_sha256=semantic_hashes[engine])
    def refs(engine,*paths): return [ref(engine,p) for p in paths]
    blockers=[];limitations=[];domains={}
    def block(code,domain,message,evidence):
        blockers.append(dict(code=code,domain=domain,classification='HARD_BLOCKER',message=message,evidence=evidence))
    def info(code,message,evidence):
        limitations.append(dict(code=code,classification='INFORMATIONAL_LIMITATION',message=message,evidence=evidence))
    def domain(name,status,rule,evidence):
        domains[name]=dict(status=status,rule=rule,upstream_evidence=evidence)

    identity=(a['identity']['status']=='RESOLVED' and a['parcel_resolution']['status']=='RESOLVED'
        and a['domain_sufficiency']['IDENTITY_SUFFICIENCY']['status']=='PASS')
    pstatus=[MAPPING.get(v['status'],'BLOCKED') for v in a['domain_sufficiency'].values()]
    property_status='BLOCKED' if not identity or 'BLOCKED' in pstatus else 'INSUFFICIENT' if 'INSUFFICIENT' in pstatus else 'PARTIAL' if 'PARTIAL' in pstatus else 'READY'
    domain('PROPERTY_DATA',property_status,'Identity must resolve; retain the weakest mapped Engine 1 subdomain.',refs('ENGINE1','/identity/status','/parcel_resolution/status','/domain_sufficiency'))
    if not identity: block('IDENTITY_UNRESOLVED','PROPERTY_DATA','Resolve address/parcel identity before property-specific work.',domains['PROPERTY_DATA']['upstream_evidence'])
    if a['domain_sufficiency']['REGULATORY_SUFFICIENCY']['status']!='PASS':
        block('REGULATORY_REVIEW_REQUIRED','PROPERTY_DATA','Verify current zoning/legal use and current city case coverage; published history is not clearance.',refs('ENGINE1','/domain_sufficiency/REGULATORY_SUFFICIENCY'))
    if a['domain_sufficiency']['HAZARD_SUFFICIENCY']['status']!='PASS':
        block('HAZARD_REVIEW_REQUIRED','PROPERTY_DATA','Resolve the upstream hazard-screening gap.',refs('ENGINE1','/domain_sufficiency/HAZARD_SUFFICIENCY'))
    if a['domain_sufficiency']['PROPERTY_FACTS_SUFFICIENCY']['status'] not in {'PASS','PASS_WITH_WARNINGS'}:
        block('PROPERTY_FACTS_INCOMPLETE','PROPERTY_DATA','Resolve required official property facts.',refs('ENGINE1','/domain_sufficiency/PROPERTY_FACTS_SUFFICIENCY'))
    review=b['acceptance_status']=='READY'
    inspection=c['status']['PHYSICAL_INSPECTION_REQUIRED'] or any(x['inspection_required'] for x in b['components'])
    hidden=bool(b['hidden_systems_requiring_inspection'] or c['unresolved_major_exposure_count'])
    unresolved_components=any(x['condition']=='UNKNOWN' or x['hidden_risk']=='UNKNOWN' for x in b['components'])
    condition_ready=review and not inspection and not hidden and not unresolved_components and b['production_handoff_accepted'] is True
    domain('CONDITION','READY' if condition_ready else 'PARTIAL' if review else 'BLOCKED',
        'Accepted visible review is PARTIAL while inspection/hidden conditions or production acceptance are unresolved.',
        refs('ENGINE2','/acceptance_status','/visible_severity','/production_handoff_accepted','/hidden_systems_requiring_inspection')+refs('ENGINE3','/status/PHYSICAL_INSPECTION_REQUIRED')
        +[ref('ENGINE2',f'/components/{i}/{field}') for i,x in enumerate(b['components']) for field in ('condition','hidden_risk') if x[field]=='UNKNOWN'])
    if not review or (not condition_ready and not inspection and not hidden):
        block('CONDITION_REVIEW_REQUIRED','CONDITION','Obtain accepted condition evidence sufficient for the decision scope.',domains['CONDITION']['upstream_evidence'])
    if inspection:
        block('PHYSICAL_INSPECTION_REQUIRED','CONDITION','Inspect unresolved components and current habitability; photos are not system tests.',
            refs('ENGINE3','/status/PHYSICAL_INSPECTION_REQUIRED')+[ref('ENGINE2',f'/components/{i}/inspection_required') for i,x in enumerate(b['components']) if x['inspection_required']])
    if hidden: block('MAJOR_HIDDEN_EXPOSURE','REHAB','Resolve hidden-condition exposure before final rehabilitation underwriting.',refs('ENGINE3','/unresolved_major_exposure_count','/unresolved_major_exposure')+refs('ENGINE2','/hidden_systems_requiring_inspection'))
    rehab_gate=f['gates']['REHAB_COST_SUFFICIENCY']['status']
    rehab_input=f['inputs']['initial_rehab']
    rehab_ready=(rehab_gate=='READY' and rehab_input.get('coverage')=='COMPLETE' and rehab_input.get('accepted') is True
        and rehab_input.get('value') is not None and rehab_input.get('evidence_class') not in {'UNKNOWN','REFERENCE_ONLY','SCENARIO_ONLY'}
        and bool(rehab_input.get('source'))
        and not hidden and not inspection)
    domain('REHAB','READY' if rehab_ready else 'PARTIAL' if c['VISIBLE_REHAB_BASE'] is not None else 'INSUFFICIENT',
        'Partial visible pricing is context; comprehensive readiness requires the real Engine 6 rehab gate and resolved inspection exposure.',
        refs('ENGINE3','/status','/estimate_label','/confidence','/VISIBLE_REHAB_BASE')+refs('ENGINE6','/gates/REHAB_COST_SUFFICIENCY','/inputs/initial_rehab'))
    if not rehab_ready: block('COMPREHENSIVE_REHAB_UNAVAILABLE','REHAB','Obtain an inspected comprehensive scope and non-overlapping cost/allowance coverage; visible subtotal is not total rehab.',domains['REHAB']['upstream_evidence'])
    arv_ready=d['ARV_BASE'] is not None and d['status']['COMP_SET_STATUS']=='READY' and d['ARV_CONFIDENCE'] not in {'UNKNOWN','INSUFFICIENT'}
    domain('VALUATION','READY' if arv_ready else MAPPING.get(d['status']['COMP_SET_STATUS'],'BLOCKED') if d['status']['COMP_SET_STATUS']!='READY' else 'PARTIAL',
        'A comp-set readiness label alone cannot replace an available supported ARV.',refs('ENGINE4','/status/COMP_SET_STATUS','/ARV_BASE','/ARV_CONFIDENCE','/accepted_comp_count'))
    if not arv_ready: block('ARV_UNAVAILABLE','VALUATION','Obtain current acceptable sale comps and an accepted ARV; no strategy exemption in v0.1.',domains['VALUATION']['upstream_evidence'])
    revenue_ready=f['gates']['REVENUE_SUFFICIENCY']['status']=='READY' and f['selected_revenue_source'] in {'approved_hcv_contract_rent','verified_market_contract_rent','monthly_market_rent'}
    utilities=e['utility_allowance']['utility_responsibility_status']=='KNOWN_REVIEWED' and e['utility_allowance']['status']=='SELECTED_REFERENCE_NOT_PHA_APPROVED'
    hcv=e['APPROVED_HCV_CONTRACT_RENT'] is not None and f['selected_revenue_source']=='approved_hcv_contract_rent'
    rr=e['rent_reasonableness']['status']=='APPROVED';hcv_inspection=e['inspection_status']['status']=='PASSED'
    rent_ready=revenue_ready and utilities and hcv and rr and hcv_inspection
    domain('RENT_HCV','READY' if rent_ready else 'PARTIAL' if e['hcv_payment_standard']['payment_standard_amount'] is not None or e['market_rent']['MARKET_RENT_BASE'] is not None else 'INSUFFICIENT',
        'Reference availability is PARTIAL, not rent approval; v0.1 retains the combined rental/HCV evidence requirements.',
        refs('ENGINE5','/market_rent/status','/hcv_payment_standard','/APPROVED_HCV_CONTRACT_RENT','/utility_allowance/status','/utility_allowance/utility_responsibility_status','/rent_reasonableness/status','/inspection_status/status')+refs('ENGINE6','/gates/REVENUE_SUFFICIENCY','/selected_revenue_source'))
    if not revenue_ready: block('ELIGIBLE_RENT_UNAVAILABLE','RENT_HCV','Obtain supported achieved/market rent and applicable collection assumptions; payment standard is not revenue.',refs('ENGINE5','/market_rent/status','/market_rent/MARKET_RENT_BASE','/APPROVED_HCV_CONTRACT_RENT')+refs('ENGINE6','/gates/REVENUE_SUFFICIENCY'))
    if not utilities: block('UTILITIES_UNRESOLVED','RENT_HCV','Establish utility responsibility, fuels and applicable allowance, then owner expenses.',refs('ENGINE5','/utility_allowance/status','/utility_allowance/utility_responsibility_status'))
    if not hcv: block('HCV_APPROVAL_ABSENT','RENT_HCV','For the retained HCV path obtain actual PHA contract-rent approval; reference standard is insufficient.',refs('ENGINE5','/APPROVED_HCV_CONTRACT_RENT')+refs('ENGINE6','/selected_revenue_source'))
    if not rr: block('HCV_REASONABLENESS_UNRESOLVED','RENT_HCV','PHA rent-reasonableness remains separate from an estimated market rent.',refs('ENGINE5','/rent_reasonableness/status'))
    if not hcv_inspection: block('HCV_INSPECTION_UNRESOLVED','RENT_HCV','Obtain actual PHA inspection approval at the appropriate rental-ready stage; do not schedule prematurely.',refs('ENGINE5','/inspection_status/status'))
    for code,gate,message in (
        ('OPERATING_EXPENSES_INCOMPLETE','OPERATING_EXPENSE_SUFFICIENCY','Obtain supported annual operating expenses and explicit utility treatment.'),
        ('FINANCING_ABSENT_OR_INCOMPLETE','DEBT_SUFFICIENCY','Obtain financing terms or explicit supported all-cash/no-seller-debt inputs.')):
        if f['gates'][gate]['status']!='READY': block(code,'FINANCIALS',message,refs('ENGINE6','/gates/'+gate))
    purchase=f['inputs']['purchase_price']
    if purchase['value'] is None or purchase.get('accepted') is not True or purchase['evidence_class'] in {'UNKNOWN','REFERENCE_ONLY','SCENARIO_ONLY'} or not purchase['source']:
        block('ACQUISITION_TERMS_UNAVAILABLE','FINANCIALS','Obtain accepted purchase and complete closing/funding terms.',refs('ENGINE6','/inputs/purchase_price','/metrics/TOTAL_PROJECT_COST'))
    financial_ready=f['FINANCIAL_PROFILE_STATUS']=='COMPLETE_EVIDENCE' and all(f['metrics'][m]['status']=='READY' and f['metrics'][m]['value'] is not None for m in ('NET_OPERATING_INCOME','TOTAL_PROJECT_COST','TOTAL_CASH_INVESTED','DEBT_SERVICE','CASH_ON_CASH_RETURN')) and f['sources_and_uses']['status']=='BALANCED'
    domain('FINANCIALS','READY' if financial_ready else MAPPING.get(f['FINANCIAL_PROFILE_STATUS'],'BLOCKED') if f['FINANCIAL_PROFILE_STATUS']!='COMPLETE_EVIDENCE' else 'PARTIAL',
        'Real evidence profile plus material metric availability and funding reconciliation; scenario success never qualifies.',refs('ENGINE6','/FINANCIAL_PROFILE_STATUS','/gates','/sources_and_uses'))
    if not financial_ready: block('FINANCIAL_EVIDENCE_INCOMPLETE','FINANCIALS','Refresh Engine 6 after its missing material inputs are accepted.',refs('ENGINE6','/FINANCIAL_PROFILE_STATUS','/KEY_FINANCIAL_RISKS','/metrics/NET_OPERATING_INCOME','/metrics/TOTAL_PROJECT_COST','/sources_and_uses'))
    for name,domain_result in domains.items():
        if domain_result['status']=='BLOCKED' and not any(x['domain']==name for x in blockers): block('UNRECOGNIZED_'+name+'_STATUS',name,'Unrecognized upstream status requires contract review.',domain_result['upstream_evidence'])
    info('VISION_VALIDATION_NOT_INFERRED','Provider-assisted review is not independent automated vision ground truth.',refs('ENGINE2','/review_origin','/automated_vision_validation'))
    info('PHOTO_DATES_AND_COVERAGE','Preserve capture-date uncertainty and limited media coverage; no new photo inference.',refs('ENGINE2','/unknown_capture_dates','/media_coverage'))
    info('PROPERTY_SOURCE_LIMITATIONS','Official facts and hazard screening retain their original scope and warnings.',refs('ENGINE1','/domain_sufficiency'))
    info('NO_AUTONOMOUS_DECISION','Acquisition recommendation policy is intentionally disabled in v0.1, even for complete inputs.',refs('ENGINE6','/status'))
    codes={x['code'] for x in blockers}
    state=('BLOCKED_PROPERTY_IDENTITY' if not identity else 'CONDITION_REVIEW_REQUIRED' if 'CONDITION_REVIEW_REQUIRED' in codes else
        'DUE_DILIGENCE_REQUIRED' if codes & {'PHYSICAL_INSPECTION_REQUIRED','MAJOR_HIDDEN_EXPOSURE','REGULATORY_REVIEW_REQUIRED','HAZARD_REVIEW_REQUIRED'} else
        'UNDERWRITING_DATA_INCOMPLETE' if blockers else 'READY_FOR_FINANCIAL_REVIEW')
    real_state=state
    scenario_status=dict(status='NOT_SUPPLIED',engine6_capability=f['status']['SCENARIO_ENGINE'],financial_profile=None,metrics=None)
    if scenario is not None:
        if scenario.get('contract_version')!=VERSIONS['ENGINE6'][1] or scenario.get('mode')!='SCENARIO_MODE' or scenario.get('property_id')!=property_id or scenario.get('FINANCIAL_PROFILE_STATUS')!='SCENARIO_ONLY' or scenario.get('operator_confirmed') is not True:
            raise ValueError('Matching operator-confirmed Engine 6 scenario required')
        if scenario.get('baseline_evidence_inputs')!=f['inputs'] or scenario.get('subject')!=f['subject'] or scenario.get('source_handoffs')!=f.get('source_handoffs'):
            raise ValueError('Scenario baseline differs from accepted real evidence')
        if not scenario.get('metrics') or any(m.get('evidence_class')!='SCENARIO_ONLY' for m in scenario['metrics'].values()): raise ValueError('Scenario output labels required')
        scenario_status=dict(status='SCENARIO_ONLY_REVIEW',engine6_capability=f['status']['SCENARIO_ENGINE'],financial_profile='SCENARIO_ONLY',
            scenario_name=scenario.get('scenario_name'),metrics=deepcopy(scenario['metrics']),source=scenario_source,
            semantic_sha256=sha256(json.dumps(scenario,sort_keys=True).encode()).hexdigest(),warning='Scenario results do not clear any real evidence blocker')
        if identity: state='SCENARIO_ONLY_REVIEW'
    actions=next_actions(blockers,identity)
    return dict(contract_version='engine7-decision-readiness-0.1.0',property_id=property_id,decision_state=state,real_evidence_decision_state=real_state,
        decision_provenance=dict(rule='Identity first, accepted condition review, physical/regulatory due diligence, incomplete underwriting, then human financial review; scenario is a separate overlay.',
            blocker_codes=[x['code'] for x in blockers],evidence=refs('ENGINE1','/identity/status')+refs('ENGINE2','/acceptance_status')+refs('ENGINE6','/mode','/FINANCIAL_PROFILE_STATUS')),
        acquisition_decision='NOT_READY',acquisition_policy=dict(enabled=False,evidence_gate_satisfied=not blockers and all(x['status']=='READY' for x in domains.values()),
            reason='No BUY/NEGOTIATE/PASS policy in this edition; READY_FOR_DECISION reserved for a later authorized human-review policy.'),
        domain_readiness=domains,hard_blockers=blockers,informational_limitations=limitations,next_required_actions=actions,
        upstream_engine_versions={k:v[field] for k,v in records.items() for field,_ in [VERSIONS[k]]},
        financial_profile=dict(status=f['FINANCIAL_PROFILE_STATUS'],gates=deepcopy(f['gates']),metrics=deepcopy(f['metrics']),risks=deepcopy(f['KEY_FINANCIAL_RISKS']),evidence=refs('ENGINE6','/FINANCIAL_PROFILE_STATUS','/metrics')),
        scenario_status=scenario_status,evidence_summary=dict(subject=deepcopy(f['subject']),property_subdomains=deepcopy(a['domain_sufficiency']),
            condition={k:deepcopy(b[k]) for k in ('visible_severity','review_origin','media_coverage','components','special_review_flags','hidden_systems_requiring_inspection','unknown_capture_dates','automated_vision_validation')},
            rehab={k:deepcopy(c[k]) for k in ('VISIBLE_REHAB_LOW','VISIBLE_REHAB_BASE','VISIBLE_REHAB_HIGH','estimate_label','confidence','unresolved_major_exposure_count','unresolved_major_exposure')},
            valuation={k:deepcopy(d[k]) for k in ('ARV_BASE','ARV_CONFIDENCE','accepted_comp_count','status')},
            rent_hcv={k:deepcopy(e[k]) for k in ('market_rent','pha','hcv_payment_standard','utility_allowance','rent_reasonableness','inspection_status','APPROVED_HCV_CONTRACT_RENT')}),
        source_handoffs=deepcopy(sources or {}),warnings=['Readiness is not investment merit; no arbitrary score or numerical confidence added.',
            'UNKNOWN remains unresolved work, not zero work. Inspection requirements are not KEEP_NO_WORK.',
            'Combined rental/HCV and ARV gates retained; strategy-specific exemptions are not implemented.',
            'MVP completion refers to software scope, not complete real-property underwriting.'],
        status=dict(ENGINE7_ARCHITECTURE='READY',ENGINE7_MVP='PUBLIC_DEMONSTRATION',PUBLIC_PIPELINE='DEMONSTRATION',FULL_UNDERWRITING_INTEGRATION='NOT_READY'))


def next_actions(blockers,identity):
    actions=[]
    def add(code,title,causes,depends=(),stage=None):
        matches=[b for b in blockers if b['code'] in causes]
        if not matches: return
        dependencies=[d for d in depends if any(a['action_id']==d for a in actions)]
        actions.append(dict(action_id=code,priority=len(actions)+1,title=title,addresses_blockers=[b['code'] for b in matches],
            depends_on=dependencies,status='WAITING_ON_DEPENDENCIES' if dependencies else 'ACTIONABLE',
            stage_requirement=stage,evidence=[r for b in matches for r in b['evidence']]))
    add('resolve_identity','Resolve property identity and re-admit upstream evidence.',{'IDENTITY_UNRESOLVED'})
    if not identity: return actions
    add('review_condition','Complete the accepted component/property condition review.',{'CONDITION_REVIEW_REQUIRED'})
    add('inspect_property','Complete physical inspection of unresolved systems, components and habitability.',{'PHYSICAL_INSPECTION_REQUIRED','MAJOR_HIDDEN_EXPOSURE'},('review_condition',))
    add('verify_official_data','Verify current legal use, city case coverage and any missing official facts/hazard evidence.',{'REGULATORY_REVIEW_REQUIRED','HAZARD_REVIEW_REQUIRED','PROPERTY_FACTS_INCOMPLETE'})
    add('complete_rehab','Obtain comprehensive contractor scope, costs and inspection allowances; refresh Engine 3.',{'COMPREHENSIVE_REHAB_UNAVAILABLE'},('inspect_property','review_condition','verify_official_data'))
    add('obtain_acquisition','Obtain purchase, closing and funding terms.',{'ACQUISITION_TERMS_UNAVAILABLE'})
    add('obtain_arv','Obtain current sale comps and accepted ARV for the supported post-rehab target; refresh Engine 4.',{'ARV_UNAVAILABLE'},('complete_rehab',))
    add('obtain_rent','Obtain current eligible rental evidence and initiate the applicable HCV evidence path; refresh Engine 5.',{'ELIGIBLE_RENT_UNAVAILABLE'},('complete_rehab',))
    add('resolve_utilities_opex','Resolve utilities/allowance applicability and obtain supported annual operating expenses.',{'UTILITIES_UNRESOLVED','OPERATING_EXPENSES_INCOMPLETE'})
    add('complete_hcv_approvals','Obtain PHA reasonableness, inspection and actual contract-rent approval at the appropriate program stage.',{'HCV_APPROVAL_ABSENT','HCV_REASONABLENESS_UNRESOLVED','HCV_INSPECTION_UNRESOLVED'},('obtain_rent','resolve_utilities_opex','complete_rehab'),stage='Actual property rental readiness and PHA process required; a completed budget is not completed rehab.')
    add('obtain_financing','Obtain applicable debt terms/proceeds or documented all-cash funding; reconcile sources and uses.',{'FINANCING_ABSENT_OR_INCOMPLETE'},('complete_rehab','obtain_acquisition','obtain_arv','obtain_rent','resolve_utilities_opex'))
    if blockers:
        prior=[a['action_id'] for a in actions]
        add('refresh_engine6','Refresh real-evidence Engine 6 after accepting the required evidence; do not substitute scenario economics.',{b['code'] for b in blockers},prior)
        add('refresh_engine7','Re-run Engine 7 with the new consistent accepted handoffs.',{b['code'] for b in blockers},('refresh_engine6',))
    else:
        actions.append(dict(action_id='human_financial_review',priority=1,title='Submit the complete evidence packet for human financial review; acquisition policy remains disabled.',addresses_blockers=[],depends_on=[],status='ACTIONABLE',stage_requirement='No autonomous recommendation',evidence=[]))
    return actions
