"""Pure deterministic math; callers enforce source eligibility."""
import math


def amortizing_loan(principal,rate,amortization_years,term_years,interest_only_months=0):
    if principal<0 or rate<0 or not all(math.isfinite(x) for x in (principal,rate,amortization_years,term_years)):
        raise ValueError('Invalid loan values')
    months=amortization_years*12;term=term_years*12
    if months<=0 or term<=0 or term>months or months>1200 or abs(months-round(months))>1e-8 or abs(term-round(term))>1e-8:
        raise ValueError('Positive whole-month term no longer than amortization required; maximum supported amortization 100 years')
    if interest_only_months!=0: raise ValueError('Interest-only structures unsupported in v0.1; never silently amortized')
    monthly_rate=rate/12
    payment=principal/months if rate==0 else principal*monthly_rate/(-math.expm1(-months*math.log1p(monthly_rate)))
    balance=principal
    for _ in range(int(round(term))): balance=max(0,balance*(1+monthly_rate)-payment)
    return dict(monthly_payment=payment,annual_scheduled_debt_service=payment*12,balloon_at_maturity=balance,
        term_months=int(round(term)),amortization_months=int(round(months)),annualized_payment_warning='Annual scheduled P&I excludes balloon, escrow and fees; short maturity requires separate liquidity planning')


def cash_flow_returns(flows,period_months):
    if len(flows)<3 or flows[0]>=0 or not any(x>0 for x in flows) or not 0<period_months<=120:
        raise ValueError('Initial investment, at least two later periods, distributions and positive period spacing required')
    signs=[1 if x>0 else -1 for x in flows if x!=0]
    if sum(a!=b for a,b in zip(signs,signs[1:]))!=1:
        raise ValueError('Nonconventional cash flows can have ambiguous IRR; unsupported')
    def npv(rate):
        return sum(x*math.exp(-i*math.log1p(rate)) for i,x in enumerate(flows))
    low=-.999;high=1.
    try:
        while npv(high)>0 and high<1e6: high=high*2+1
        if npv(low)*npv(high)>0: raise ValueError('IRR not bracketed')
        for _ in range(160):
            mid=(low+high)/2
            if npv(mid)>0: low=mid
            else: high=mid
        periodic=(low+high)/2;annual=math.expm1(math.log1p(periodic)*12/period_months)
    except (OverflowError,ZeroDivisionError): raise ValueError('Cash flow horizon/rate outside safe numerical range')
    if not math.isfinite(annual): raise ValueError('Nonfinite IRR')
    return dict(equity_multiple=sum(x for x in flows if x>0)/-sum(x for x in flows if x<0),periodic_irr=periodic,annualized_irr=annual)
