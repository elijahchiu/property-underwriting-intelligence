"""Evidence-aware financial arithmetic, deliberately isolated from legacy offer logic."""
from copy import deepcopy
import math
from .inputs import normalize, usable, output_class, MODES
from .math import amortizing_loan, cash_flow_returns

OPEX = ('property_taxes','insurance','management_fee','maintenance','utilities_owner_paid','HOA','other_opex')
INITIAL = ('purchase_price','closing_costs','initial_rehab','contingency','inspection_dependent_allowance','initial_reserves','other_initial_costs')
RENTS = ('approved_hcv_contract_rent','verified_market_contract_rent','monthly_market_rent','monthly_scenario_rent')


class Ledger:
    def __init__(self, inputs, mode):
        self.inputs = normalize(inputs)
        self.mode = mode
        self.metrics = {}
        self.values = {}

    def eligible(self, name):
        item = self.inputs[name]
        source=item.get('source')
        if name=='initial_rehab' and isinstance(source,dict) and source.get('kind')=='PARTIAL_VISIBLE_SCOPE_ONLY': return False
        return usable(item,self.mode,complete=name in {'initial_rehab','cash_flows'})

    def add(self, name, fields, dependencies, formula, fn, *, unit='USD_YEAR', warnings=(), block=None):
        sources = {f:deepcopy(self.inputs[f]) for f in fields}
        for dep in dependencies:
            sources.update(deepcopy(self.metrics[dep]['source_inputs']))
        missing = [f for f in fields if not self.eligible(f)]
        missing += [d for d in dependencies if self.values[d] is None]
        notes = list(warnings)
        for dep in dependencies:
            notes.extend(self.metrics[dep]['warnings'])
        if missing: notes.append('Missing or ineligible: '+', '.join(missing))
        if block: notes.append(block)
        value = None
        if not missing and not block:
            try:
                value = fn({f:self.inputs[f]['value'] for f in fields},self.values)
                if not math.isfinite(value): raise ValueError('Nonfinite result')
            except (ValueError,ZeroDivisionError,OverflowError) as exc:
                notes.append(str(exc) or 'Zero denominator; metric undefined')
                value = None
        self.values[name] = value
        if value is not None and any(x.get('effective_date') is None for x in sources.values()): notes.append('One or more material input effective dates are UNKNOWN; freshness not certified')
        self.metrics[name] = dict(value=None if value is None else round(value,8 if unit in {'FRACTION','MULTIPLE'} else 2),
            unit=unit,status='READY' if value is not None else 'NOT_READY',
            evidence_class=('SCENARIO_ONLY' if self.mode=='SCENARIO_MODE' else 'INSUFFICIENT') if value is None else output_class(sources.values(),self.mode),
            source_inputs=sources,formula=formula,warnings=list(dict.fromkeys(notes)),dependencies=list(dependencies))


def eligible_rent(ledger):
    for name in RENTS:
        item=ledger.inputs[name]
        source=item.get('source'); kind=source.get('kind') if isinstance(source,dict) else None
        if not ledger.eligible(name): continue
        if name=='approved_hcv_contract_rent' and (item['evidence_class']!='APPROVED' or kind!='PHA_APPROVAL'): continue
        if name=='verified_market_contract_rent' and (item['evidence_class']!='VERIFIED' or kind not in {'LEASE','CONTRACT'}): continue
        if name=='monthly_market_rent' and item['evidence_class'] not in {'ESTIMATED','VERIFIED'}: continue
        if name=='monthly_scenario_rent' and (ledger.mode!='SCENARIO_MODE' or item['evidence_class']!='SCENARIO_ONLY'): continue
        # Reference source role cannot be laundered by changing its evidence label.
        if kind in {'PAYMENT_STANDARD','HCV_REFERENCE','UTILITY_ALLOWANCE','PROVIDER_BENCHMARK'} and name!='monthly_scenario_rent': continue
        return name
    return None


def calculate(inputs, *, mode='EVIDENCE_MODE', property_id=None, rounding_tolerance=.01):
    if mode not in MODES: raise ValueError('Explicit supported mode required')
    if isinstance(rounding_tolerance,bool) or not math.isfinite(rounding_tolerance) or rounding_tolerance<0:
        raise ValueError('Finite nonnegative reconciliation tolerance required')
    l=Ledger(inputs,mode); add=l.add; selected=eligible_rent(l)
    rent_fields=[selected] if selected else list(RENTS)
    rent_warnings=[]
    if selected=='monthly_scenario_rent':
        rent_warnings=['SCENARIO_RENT_ASSUMPTION','NOT_APPROVED_HCV_CONTRACT_RENT','NOT PHA-APPROVED CONTRACT RENT']
        if l.eligible('rent_assumption_basis'): rent_fields.append('rent_assumption_basis')
    add('GROSS_POTENTIAL_RENT',rent_fields,[],'eligible monthly rent * 12',lambda f,m:f[selected]*12,
        warnings=rent_warnings,block=None if selected else 'No eligible revenue; HCV payment standard is reference only')
    add('VACANCY_LOSS',['vacancy_rate'],['GROSS_POTENTIAL_RENT'],'GPR * vacancy_rate',lambda f,m:m['GROSS_POTENTIAL_RENT']*f['vacancy_rate'])
    add('CREDIT_LOSS',['credit_loss_rate'],['GROSS_POTENTIAL_RENT','VACANCY_LOSS'],'(GPR - vacancy loss) * credit_loss_rate',lambda f,m:(m['GROSS_POTENTIAL_RENT']-m['VACANCY_LOSS'])*f['credit_loss_rate'])
    add('EFFECTIVE_GROSS_INCOME',['other_income'],['GROSS_POTENTIAL_RENT','VACANCY_LOSS','CREDIT_LOSS'],'GPR - vacancy loss - credit loss + annual net other income',lambda f,m:m['GROSS_POTENTIAL_RENT']-m['VACANCY_LOSS']-m['CREDIT_LOSS']+f['other_income'])
    add('OPERATING_EXPENSES',OPEX,[],'sum of annual taxes, insurance, management, maintenance, owner utilities, HOA, other opex',lambda f,m:sum(f.values()))
    add('NET_OPERATING_INCOME',[],['EFFECTIVE_GROSS_INCOME','OPERATING_EXPENSES'],'EGI - OPEX; excludes debt, initial costs and capex reserves',lambda f,m:m['EFFECTIVE_GROSS_INCOME']-m['OPERATING_EXPENSES'])
    add('ADJUSTED_NOI',['capex_reserve'],['NET_OPERATING_INCOME'],'NOI - annual capex reserve (separate adjusted view)',lambda f,m:m['NET_OPERATING_INCOME']-f['capex_reserve'])
    add('FINANCING_FEES',['loan_amount','points','loan_fees'],[],'senior principal * points + all other upfront finance fees',lambda f,m:f['loan_amount']*f['points']+f['loan_fees'],unit='USD')
    add('TOTAL_PROJECT_COST',INITIAL,['FINANCING_FEES'],'purchase + closing + complete rehab + incremental contingency + incremental inspection allowance + initial reserves + other initial uses + financing fees',lambda f,m:sum(f.values())+m['FINANCING_FEES'],unit='USD')
    funding=['debt_proceeds','seller_financing','other_capital']
    add('TOTAL_INITIAL_CASH_REQUIRED',funding,['TOTAL_PROJECT_COST'],'total project uses - senior funded proceeds - seller financing - nonownership nonrepayable other capital',lambda f,m:m['TOTAL_PROJECT_COST']-sum(f.values()),unit='USD')
    add('TOTAL_SOURCES',funding+['equity_contribution'],[],'funded proceeds + seller financing + other capital + aggregate equity',lambda f,m:sum(f.values()),unit='USD')
    add('SOURCES_USES_DIFFERENCE',[],['TOTAL_SOURCES','TOTAL_PROJECT_COST'],'total sources - total project uses',lambda f,m:m['TOTAL_SOURCES']-m['TOTAL_PROJECT_COST'],unit='USD')
    difference=l.values['SOURCES_USES_DIFFERENCE']
    funding_flags=[]
    if difference is not None and abs(difference)>rounding_tolerance: funding_flags.append('SOURCES_USES_MISMATCH')
    if l.values['TOTAL_INITIAL_CASH_REQUIRED'] is not None and l.values['TOTAL_INITIAL_CASH_REQUIRED']<0: funding_flags.append('OVERFUNDED_USES_REVIEW_REQUIRED')
    if l.eligible('debt_proceeds') and l.eligible('loan_amount') and l.inputs['debt_proceeds']['value']>l.inputs['loan_amount']['value']+rounding_tolerance:
        funding_flags.append('FUNDED_PROCEEDS_EXCEED_PRINCIPAL')
    add('TOTAL_CASH_INVESTED',['equity_contribution'],['TOTAL_INITIAL_CASH_REQUIRED','SOURCES_USES_DIFFERENCE'],
        'aggregate equity contribution after sources/uses reconciliation',lambda f,m:f['equity_contribution'],unit='USD',block='; '.join(funding_flags) or None)

    # Seller debt is explicit, including a supported zero when absent.
    loan_details={};loan_required=[]
    for prefix,principal,rate,term,amort,io in (
        ('SENIOR','loan_amount','interest_rate','term_years','amortization_years','interest_only_months'),
        ('SELLER','seller_financing','seller_interest_rate','seller_term_years','seller_amortization_years','seller_interest_only_months')):
        names=[principal] if l.eligible(principal) and l.inputs[principal]['value']==0 else [principal,rate,term,amort,io]
        loan_required.extend(names)
        detail=None; error=None
        if all(l.eligible(f) for f in names):
            try:
                detail=dict(monthly_payment=0,annual_scheduled_debt_service=0,balloon_at_maturity=0) if len(names)==1 else amortizing_loan(*[l.inputs[f]['value'] for f in (principal,rate,amort,term,io)])
            except ValueError as exc: error=str(exc)
        loan_details[prefix]=dict(status='READY' if detail is not None else 'NOT_READY',
            evidence_class=output_class([l.inputs[f] for f in names],mode) if detail is not None else ('SCENARIO_ONLY' if mode=='SCENARIO_MODE' else 'INSUFFICIENT'),
            source_inputs={f:deepcopy(l.inputs[f]) for f in names},calculation=detail,
            formula='Fixed monthly amortization; see corresponding component metrics',warnings=[error] if error else [])
        for suffix,key,unit in [('MONTHLY_PAYMENT','monthly_payment','USD_MONTH'),('DEBT_SERVICE','annual_scheduled_debt_service','USD_YEAR'),('BALLOON_AT_MATURITY','balloon_at_maturity','USD')]:
            add(prefix+'_'+suffix,names,[],'fixed monthly amortization; annual debt service = 12 scheduled payments; maturity balloon separate',
                lambda f,m,k=key,d=detail:d[k],unit=unit,block=error,
                warnings=['Annualized scheduled P&I excludes escrow, fees and maturity balloon'] if len(names)>1 else [])
    add('DEBT_SERVICE',[],['SENIOR_DEBT_SERVICE','SELLER_DEBT_SERVICE'],'annual senior scheduled P&I + annual seller scheduled P&I',lambda f,m:m['SENIOR_DEBT_SERVICE']+m['SELLER_DEBT_SERVICE'])
    add('ANNUAL_CASH_FLOW',[],['NET_OPERATING_INCOME','DEBT_SERVICE'],'NOI - annual scheduled debt service; pre-tax, pre-capex, excludes balloon',lambda f,m:m['NET_OPERATING_INCOME']-m['DEBT_SERVICE'])
    add('MONTHLY_CASH_FLOW',[],['ANNUAL_CASH_FLOW'],'annual pre-tax cash flow / 12 (annualized average)',lambda f,m:m['ANNUAL_CASH_FLOW']/12,unit='USD_MONTH')
    add('CAPEX_ADJUSTED_CASH_FLOW',['capex_reserve'],['ANNUAL_CASH_FLOW'],'annual cash flow - annual capex reserve',lambda f,m:m['ANNUAL_CASH_FLOW']-f['capex_reserve'])
    add('DSCR',[],['NET_OPERATING_INCOME','DEBT_SERVICE'],'NOI / annual scheduled debt service; undefined for zero debt service',lambda f,m:m['NET_OPERATING_INCOME']/m['DEBT_SERVICE'],unit='MULTIPLE',warnings=['Not lender approval; annualized payments exclude any maturity balloon'])
    add('CAP_RATE_ON_PURCHASE_PRICE',['purchase_price'],['NET_OPERATING_INCOME'],'NOI / purchase price',lambda f,m:m['NET_OPERATING_INCOME']/f['purchase_price'],unit='FRACTION')
    add('CAP_RATE_ON_TOTAL_PROJECT_COST',[],['NET_OPERATING_INCOME','TOTAL_PROJECT_COST'],'NOI / complete project cost',lambda f,m:m['NET_OPERATING_INCOME']/m['TOTAL_PROJECT_COST'],unit='FRACTION')
    add('YIELD_ON_COST',['stabilized_operations'],['NET_OPERATING_INCOME','TOTAL_PROJECT_COST'],'explicitly stabilized NOI / complete project cost',lambda f,m:m['NET_OPERATING_INCOME']/m['TOTAL_PROJECT_COST'],unit='FRACTION',
        block=None if l.inputs['stabilized_operations']['value'] is True else 'Stabilized operations not confirmed')
    add('CASH_ON_CASH_RETURN',[],['ANNUAL_CASH_FLOW','TOTAL_CASH_INVESTED'],'annual pre-tax cash flow / reconciled complete initial cash invested',lambda f,m:m['ANNUAL_CASH_FLOW']/m['TOTAL_CASH_INVESTED'],unit='FRACTION')
    add('BREAKEVEN_OCCUPANCY',['other_income','credit_loss_rate'],['OPERATING_EXPENSES','DEBT_SERVICE','GROSS_POTENTIAL_RENT'],
        '(annual OPEX + annual debt service - net other income) / (GPR * (1 - credit_loss_rate))',
        lambda f,m:(m['OPERATING_EXPENSES']+m['DEBT_SERVICE']-f['other_income'])/(m['GROSS_POTENTIAL_RENT']*(1-f['credit_loss_rate'])),unit='FRACTION',warnings=['Fixed annual operating expenses; not a probabilistic forecast'])
    occupancy=l.values['BREAKEVEN_OCCUPANCY']
    if occupancy is not None and not 0<=occupancy<=1: l.metrics['BREAKEVEN_OCCUPANCY']['warnings'].append('OUTSIDE_FEASIBLE_OCCUPANCY_RANGE; not clamped')
    add('TOTAL_DEBT_PRINCIPAL',['loan_amount','seller_financing'],[],'senior principal + seller note principal',lambda f,m:sum(f.values()),unit='USD')
    add('DEBT_YIELD',[],['NET_OPERATING_INCOME','TOTAL_DEBT_PRINCIPAL'],'NOI / total debt principal',lambda f,m:m['NET_OPERATING_INCOME']/m['TOTAL_DEBT_PRINCIPAL'],unit='FRACTION')
    add('LOAN_TO_COST',[],['TOTAL_DEBT_PRINCIPAL','TOTAL_PROJECT_COST'],'total debt principal / complete project cost',lambda f,m:m['TOTAL_DEBT_PRINCIPAL']/m['TOTAL_PROJECT_COST'],unit='FRACTION')
    add('LOAN_TO_VALUE',['ARV'],['TOTAL_DEBT_PRINCIPAL'],'total debt principal / accepted ARV; no purchase-price fallback',lambda f,m:m['TOTAL_DEBT_PRINCIPAL']/f['ARV'],unit='FRACTION')
    refi_value='refinance_value' if l.eligible('refinance_value') else 'ARV'
    add('MAXIMUM_REFINANCE_LOAN',[refi_value,'refinance_LTV'],[],'accepted refinance value (else accepted ARV) * explicit refi LTV',lambda f,m:f[refi_value]*f['refinance_LTV'],unit='USD',warnings=['LTV-only reference sizing, not lender approval or a DSCR/credit-constrained loan commitment'])
    add('GROSS_REFINANCE_CASH_OUT',['refinance_existing_debt_payoff'],['MAXIMUM_REFINANCE_LOAN'],'new loan - all existing debt payoff at refinance',lambda f,m:m['MAXIMUM_REFINANCE_LOAN']-f['refinance_existing_debt_payoff'],unit='USD')
    add('NET_REFINANCE_CASH_OUT',['refinance_costs'],['GROSS_REFINANCE_CASH_OUT'],'gross cash out - complete refinance fees',lambda f,m:m['GROSS_REFINANCE_CASH_OUT']-f['refinance_costs'],unit='USD')
    add('CASH_LEFT_IN_DEAL',[],['TOTAL_CASH_INVESTED','NET_REFINANCE_CASH_OUT'],'initial cash invested - net cash returned at refi; excludes interim operating distributions',lambda f,m:m['TOTAL_CASH_INVESTED']-m['NET_REFINANCE_CASH_OUT'],unit='USD')
    if l.values['CASH_LEFT_IN_DEAL'] is not None and l.values['CASH_LEFT_IN_DEAL']<0:
        l.metrics['CASH_LEFT_IN_DEAL']['warnings'].append('Net cash returned exceeds initial equity; negative cash left is not clamped')
    add('POST_REFINANCE_DEBT_SERVICE',['refinance_rate','refinance_amortization_years','refinance_term_years'],['MAXIMUM_REFINANCE_LOAN'],
        '12 monthly fully amortizing new-note payments; no IO; all existing liens paid off',
        lambda f,m:amortizing_loan(m['MAXIMUM_REFINANCE_LOAN'],f['refinance_rate'],f['refinance_amortization_years'],f['refinance_term_years'])['annual_scheduled_debt_service'],warnings=['Annualized; maturity balloon excluded'])
    add('POST_REFINANCE_DSCR',[],['NET_OPERATING_INCOME','POST_REFINANCE_DEBT_SERVICE'],'NOI / new annual scheduled P&I',lambda f,m:m['NET_OPERATING_INCOME']/m['POST_REFINANCE_DEBT_SERVICE'],unit='MULTIPLE')
    add('NET_SALE_PROCEEDS',['sale_price','selling_cost_rate','other_exit_costs','sale_debt_payoff'],[],'sale price * (1 - selling cost rate) - fixed exit costs - all debt payoff at sale',lambda f,m:f['sale_price']*(1-f['selling_cost_rate'])-f['other_exit_costs']-f['sale_debt_payoff'],unit='USD')
    for metric,key,unit in [('EQUITY_MULTIPLE','equity_multiple','MULTIPLE'),('IRR','annualized_irr','FRACTION')]:
        add(metric,['cash_flows','cash_flow_period_months'],[],'complete equally spaced net equity cash flows; multiple = distributions / contributions; IRR solves NPV=0 then annualizes',
            lambda f,m,k=key:cash_flow_returns(f['cash_flows'],f['cash_flow_period_months'])[k],unit=unit,warnings=['Supplied complete cash-flow series only; no inferred rent/rehab/exit timeline'])

    def gate(fields,ready,extra=False):
        good=[f for f in fields if l.eligible(f)]
        return dict(status='READY' if ready else ('PARTIAL' if good or extra else 'INSUFFICIENT'),
            eligible_inputs=good,missing_or_ineligible_inputs=[f for f in fields if not l.eligible(f)])
    gates={
        'REVENUE_SUFFICIENCY':gate(((selected,) if selected else RENTS)+('vacancy_rate','credit_loss_rate','other_income'),l.values['EFFECTIVE_GROSS_INCOME'] is not None),
        'REHAB_COST_SUFFICIENCY':gate(('initial_rehab','contingency','inspection_dependent_allowance'),all(l.eligible(f) for f in ('initial_rehab','contingency','inspection_dependent_allowance')),l.inputs['partial_visible_rehab_reference']['value'] is not None),
        'OPERATING_EXPENSE_SUFFICIENCY':gate(OPEX,l.values['OPERATING_EXPENSES'] is not None),
        'DEBT_SUFFICIENCY':gate(tuple(loan_required),l.values['DEBT_SERVICE'] is not None),
        'VALUE_SUFFICIENCY':gate(('ARV','refinance_value'),l.eligible('ARV') or l.eligible('refinance_value')),
    }
    core=('NET_OPERATING_INCOME','TOTAL_PROJECT_COST','TOTAL_CASH_INVESTED','DEBT_SERVICE','CAP_RATE_ON_PURCHASE_PRICE','YIELD_ON_COST','LOAN_TO_VALUE')
    ready_count=sum(l.values[k] is not None for k in core)
    profile='SCENARIO_ONLY' if mode=='SCENARIO_MODE' else ('COMPLETE_EVIDENCE' if ready_count==len(core) else 'PARTIAL_EVIDENCE' if ready_count else 'INSUFFICIENT')
    risks=list(funding_flags)
    risk_fields={'initial_rehab':'COMPLETE_REHAB_UNAVAILABLE','ARV':'ARV_UNAVAILABLE','utilities_owner_paid':'OWNER_UTILITIES_UNKNOWN','loan_amount':'FINANCING_ABSENT'}
    risks += [risk for field,risk in risk_fields.items() if not l.eligible(field)]
    if selected is None: risks.append('ELIGIBLE_RENT_UNAVAILABLE')
    if selected!='approved_hcv_contract_rent': risks.append('HCV_CONTRACT_RENT_UNAPPROVED_OR_UNAVAILABLE')
    if l.values['OPERATING_EXPENSES'] is None: risks.append('OPERATING_EXPENSES_INCOMPLETE')
    return dict(contract_version='engine6-financial-0.1.0',property_id=property_id,mode=mode,
        evidence_class='SCENARIO_ONLY' if mode=='SCENARIO_MODE' else 'EVIDENCE_MODE',inputs=l.inputs,selected_revenue_source=selected,
        metrics=l.metrics,gates=gates,loan_details=loan_details,
        sources_and_uses=dict(status='NOT_READY' if difference is None else 'MISMATCH' if funding_flags else 'BALANCED',rounding_tolerance=rounding_tolerance,flags=funding_flags),
        FINANCIAL_PROFILE_STATUS=profile,KEY_FINANCIAL_RISKS=risks,
        status=dict(ENGINE6_ARCHITECTURE='READY',ENGINE6_MVP='READY TO FREEZE',SCENARIO_ENGINE='READY',ENGINE7_PROPERTY_DECISION_DEVELOPMENT='READY',FULL_UNDERWRITING_INTEGRATION='NOT_READY'),
        limitations=['Arithmetic and evidence sufficiency only; no investment recommendation',
            'Scenario readiness cannot clear real underwriting blockers','UNKNOWN is unresolved, not zero; partial scope is not total rehab',
            'Regular-payment metrics exclude maturity balloon; no lender approval, tax modeling or inferred multi-period forecast'])
