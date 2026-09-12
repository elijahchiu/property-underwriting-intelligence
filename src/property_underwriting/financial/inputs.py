from copy import deepcopy
from dataclasses import dataclass, asdict
import math


CLASSES={"VERIFIED","APPROVED","ESTIMATED","SCENARIO_ONLY","REFERENCE_ONLY","UNKNOWN"}
MODES={"EVIDENCE_MODE","SCENARIO_MODE"}

# Units are intentionally explicit; no automatic monthly/annual or percent conversion.
FIELDS={
    "purchase_price":("acquisition","USD","Accepted purchase price or explicit operator assumption"),
    "closing_costs":("acquisition","USD","Acquisition closing costs, excluding financing fees"),
    "initial_rehab":("rehab","USD","Complete rehab base, excluding separately listed contingency/inspection allowances; coverage must be COMPLETE"),
    "partial_visible_rehab_reference":("rehab","USD","Partial Engine 3 context only; never complete project rehab"),
    "contingency":("rehab","USD","Incremental contingency not already in rehab base; explicit zero if included"),
    "inspection_dependent_allowance":("rehab","USD","Additional non-overlapping inspection allowance; unknown is not zero"),
    "initial_reserves":("acquisition","USD","Initial cash reserve funding, separate from annual capex reserve"),
    "other_initial_costs":("acquisition","USD","Other non-overlapping initial uses, including any pre-stabilization carrying cost"),
    "approved_hcv_contract_rent":("revenue","USD_MONTH","Only accepted PHA-approved contract rent, never the payment standard"),
    "verified_market_contract_rent":("revenue","USD_MONTH","Verified private-market leased/contract rent"),
    "monthly_market_rent":("revenue","USD_MONTH","Accepted market-rent estimate, not a provider benchmark alone"),
    "monthly_scenario_rent":("revenue","USD_MONTH","Deliberate operator rental assumption; not PHA-approved"),
    "payment_standard_reference":("revenue","USD_MONTH","Reference only; ineligible for operating revenue"),
    "rent_assumption_basis":("revenue","TEXT","OPERATOR_ASSUMPTION or PHA_PAYMENT_STANDARD_REFERENCE; the latter needs deliberate rent input too"),
    "other_income":("revenue","USD_YEAR","Annual other income after its own collection assumptions"),
    "vacancy_rate":("revenue","FRACTION","Fraction of potential rent lost to vacancy, e.g. typed fraction, no default"),
    "credit_loss_rate":("revenue","FRACTION","Fraction of occupied potential rent lost to noncollection"),
    "stabilized_operations":("revenue","BOOLEAN","Explicit confirmation that rental/expense inputs describe stabilized operations"),
    "property_taxes":("operating_expenses","USD_YEAR","Authoritative actual/current annual property tax bill, not assessed value or tax district"),
    "insurance":("operating_expenses","USD_YEAR","Accepted insurance quote/history or explicit scenario"),
    "management_fee":("operating_expenses","USD_YEAR","Annual management expense, modeled fixed; no invented percentage"),
    "maintenance":("operating_expenses","USD_YEAR","Annual maintenance, excluding capex reserve and initial rehab"),
    "capex_reserve":("operating_expenses","USD_YEAR","Annual reserve outside standard NOI; separately adjusted NOI available"),
    "utilities_owner_paid":("operating_expenses","USD_YEAR","Owner-paid annual utility expense; unknown responsibilities cannot default to zero"),
    "HOA":("operating_expenses","USD_YEAR","Annual HOA expense; explicit zero only when supported"),
    "other_opex":("operating_expenses","USD_YEAR","Other non-overlapping annual operating expenses"),
    "loan_amount":("financing","USD","Senior principal committed/outstanding for the modeled funding event; explicit zero for all cash"),
    "debt_proceeds":("financing","USD","Total senior funding applied to project uses, INCLUDING lender-retained fees already listed as uses; not net bank deposit, and not automatically equal to committed principal"),
    "interest_rate":("financing","FRACTION","Annual fixed nominal rate; no invented current rate"),
    "term_years":("financing","YEARS","Contractual maturity; can be shorter than amortization, producing a disclosed balloon"),
    "amortization_years":("financing","YEARS","Principal amortization period, monthly payments"),
    "interest_only_months":("financing","MONTHS","v0.1 supports zero only; nonzero is explicitly unsupported"),
    "points":("financing","FRACTION","Senior origination points as fraction of principal, not percentage points"),
    "loan_fees":("financing","USD","All other upfront finance fees including seller-note fees, excluding points and acquisition closing costs"),
    "seller_financing":("financing","USD","Seller note principal applied to purchase uses; counted once as debt funding"),
    "seller_interest_rate":("financing","FRACTION","Annual fixed seller-note rate, when seller financing is positive"),
    "seller_term_years":("financing","YEARS","Seller note maturity"),
    "seller_amortization_years":("financing","YEARS","Seller note monthly amortization period"),
    "seller_interest_only_months":("financing","MONTHS","Zero supported; other structures explicitly unavailable"),
    "other_capital":("financing","USD","Nonrepayable nonownership capital, e.g. grant; additional investor equity belongs in equity_contribution"),
    "equity_contribution":("financing","USD","Total owner/investor equity supplied to reconcile sources and uses; returns are for aggregate equity"),
    "ARV":("refinance","USD","Accepted after-repair value or explicit scenario; unavailable Engine 4 ARV stays null"),
    "refinance_value":("refinance","USD","Accepted stabilized refinance valuation or explicit scenario"),
    "refinance_LTV":("refinance","FRACTION","Explicit target/reference LTV; not lender approval"),
    "refinance_rate":("refinance","FRACTION","Annual fixed new-note rate"),
    "refinance_term_years":("refinance","YEARS","New-note contractual term"),
    "refinance_amortization_years":("refinance","YEARS","New-note monthly amortization period"),
    "refinance_costs":("refinance","USD","Complete incremental refinance closing/finance fees"),
    "refinance_existing_debt_payoff":("refinance","USD","All existing liens/interest/payoff charges at refinance; not inferred from original principal"),
    "sale_price":("sale_exit","USD","Accepted sale evidence or explicit scenario exit price"),
    "selling_cost_rate":("sale_exit","FRACTION","Selling costs as fraction of sale price"),
    "other_exit_costs":("sale_exit","USD","Additional non-overlapping fixed exit costs"),
    "sale_debt_payoff":("sale_exit","USD","All loan payoff amounts at sale; no invented remaining balance"),
    "holding_period":("sale_exit","MONTHS","Explicit hold duration; no automatic cash-flow timeline is fabricated"),
    "cash_flows":("sale_exit","USD_SERIES","Complete net equity flows: initial negative contribution followed by equally spaced net flows; scenario or accepted actual series"),
    "cash_flow_period_months":("sale_exit","MONTHS","Spacing of supplied cash flows, needed for annualized IRR"),
}


@dataclass(frozen=True)
class FinancialInput:
    value: object
    unit: str
    evidence_class: str
    source: object
    effective_date: object
    notes: str
    accepted: bool = False
    coverage: str = "UNKNOWN"


def observation(name,value=None,*,evidence_class="UNKNOWN",source=None,effective_date=None,notes=None,accepted=False,coverage="UNKNOWN"):
    return asdict(FinancialInput(value,FIELDS[name][1],evidence_class,deepcopy(source),effective_date,notes or FIELDS[name][2],accepted,coverage))


def normalize(inputs):
    unknown=set(inputs)-set(FIELDS)
    if unknown: raise ValueError("Unknown financial fields: "+", ".join(sorted(unknown)))
    result={name:observation(name) for name in FIELDS}
    required={"value","unit","evidence_class","source","effective_date","notes"}
    for name,raw in inputs.items():
        if not isinstance(raw,dict) or not required<=set(raw): raise ValueError("Complete provenance wrapper required for "+name)
        if raw['unit']!=FIELDS[name][1] or raw['evidence_class'] not in CLASSES: raise ValueError("Invalid unit/evidence class: "+name)
        item=observation(name);item.update(deepcopy(raw));v=item['value']
        if v is not None:
            if item['unit'] not in {'TEXT','BOOLEAN','USD_SERIES'}:
                if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<0: raise ValueError("Finite nonnegative number required: "+name)
                if item['unit']=='FRACTION' and v>1: raise ValueError("Fraction must be between zero and one: "+name)
            elif item['unit']=='BOOLEAN' and not isinstance(v,bool): raise ValueError("Boolean required: "+name)
            elif item['unit']=='TEXT' and not isinstance(v,str): raise ValueError("Text required: "+name)
            elif item['unit']=='USD_SERIES' and (not isinstance(v,list) or any(isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) for x in v)):
                raise ValueError("Finite cash-flow series required")
        result[name]=item
    return result


def usable(item,mode,*,complete=False):
    return (item['value'] is not None and item.get('accepted') is True and bool(item['source'])
        and item['evidence_class'] not in {'UNKNOWN','REFERENCE_ONLY'}
        and (mode=='SCENARIO_MODE' or item['evidence_class']!='SCENARIO_ONLY')
        and (not complete or item.get('coverage')=='COMPLETE'))


def output_class(items,mode):
    classes={x['evidence_class'] for x in items}
    if mode=='SCENARIO_MODE' or 'SCENARIO_ONLY' in classes: return 'SCENARIO_ONLY'
    if 'ESTIMATED' in classes: return 'MIXED_ESTIMATED'
    if 'APPROVED' in classes: return 'APPROVED_INPUTS' if classes=={'APPROVED'} else 'MIXED_APPROVED_VERIFIED'
    return 'ALL_VERIFIED'


def scenario_template(property_id):
    groups={}
    for name,(category,unit,description) in FIELDS.items():
        if name in {'partial_visible_rehab_reference','payment_standard_reference','approved_hcv_contract_rent','verified_market_contract_rent','monthly_market_rent'}: continue
        groups.setdefault(category,{})[name]=observation(name,evidence_class='SCENARIO_ONLY',notes=description)
    return dict(contract_version='engine6-scenario-input-0.1.0',property_id=property_id,mode='SCENARIO_MODE',
        scenario_name=None,operator_confirmed=False,rent_assumption_warning='NOT PHA-APPROVED CONTRACT RENT',
        instructions='Populate only deliberate assumptions. Set accepted=true, a source identifying the operator assumption, and coverage=COMPLETE for complete rehab/cash-flow series. All amounts are null; no recommended values.',
        categories=groups,stress_overrides=None)


def scenario_inputs(payload,property_id):
    if payload.get('contract_version')!='engine6-scenario-input-0.1.0' or payload.get('property_id')!=property_id or payload.get('mode')!='SCENARIO_MODE':
        raise ValueError('Scenario contract/property mismatch')
    if payload.get('operator_confirmed') is not True or not payload.get('scenario_name'): raise ValueError('Named operator-confirmed scenario required')
    result={}
    for category,fields in payload.get('categories',{}).items():
        for name,item in fields.items():
            if name not in FIELDS or FIELDS[name][0]!=category or name in result: raise ValueError('Invalid/duplicate scenario category field')
            if item.get('value') is None: continue
            if item.get('evidence_class')!='SCENARIO_ONLY': raise ValueError('Operator assumptions must remain SCENARIO_ONLY')
            result[name]=deepcopy(item)
    normalize(result)
    return result
