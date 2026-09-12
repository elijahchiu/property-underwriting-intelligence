"""Offline reference arithmetic; no jurisdiction resolution or schedule scraping."""
from datetime import date, datetime, timezone

def local_day(value):
    if not value: return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc).date() if parsed.tzinfo else parsed.date()
    except ValueError: return None


def reference_economics(payment, utility, market_base=None):
    amount=payment.get("payment_standard_amount") if payment.get("status")=="AVAILABLE" else None
    allowance=utility.get("tenant_paid_utility_allowance") if utility.get("status")=="SELECTED_REFERENCE_NOT_PHA_APPROVED" else None
    return dict(status="PARTIAL_REFERENCE",label="PAYMENT_STANDARD_DERIVED_REFERENCE",payment_standard=amount,
        market_rent_base=market_base,tenant_paid_utility_allowance=allowance,
        payment_standard_minus_known_tenant_utilities_reference=round(amount-allowance,2) if amount is not None and allowance is not None else None,
        difference_market_vs_payment_standard=round(market_base-amount,2) if market_base is not None and amount is not None else None,
        contract_rent=None,gross_rent=None,gross_rent_definition="contract_rent + tenant_paid_utility_allowance = gross_rent",
        approved_hcv_contract_rent=None,approved_contract_rent_status="NOT_APPROVED",
        warning="PAYMENT STANDARD IS NOT GUARANTEED CONTRACT RENT; reference is not owner revenue, HAP or approval")

