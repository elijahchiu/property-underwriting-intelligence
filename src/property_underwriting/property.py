"""Offline source reconciliation extracted from the property data engine."""
import json
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

def utc_now():
    return datetime.now(timezone.utc).isoformat()

class FactObservation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)
    observation_id: str = Field(default_factory=lambda: str(uuid4()))
    property_id: str
    field_name: str
    raw_value: Any
    normalized_value: Any
    unit: str | None = None
    source: str
    source_record_id: str
    source_field_path: str
    source_url: str | None = None
    raw_hash: str | None = None
    retrieved_at: str = Field(default_factory=utc_now)
    effective_date: str | None = None
    source_run_id: str | None = None
    source_endpoint: str | None = None
    status: str = "AVAILABLE"
    source_scope: str = "CURRENT"
    lifecycle_state: Literal["existing", "proposed", "historical", "modeled"] = "existing"
    evidence_level: Literal["V", "A", "B", "C", "D", "U"] = "U"
    area_basis: str | None = None
    notes: str = ""

    @field_validator("raw_value", "normalized_value")
    @classmethod
    def json_value(cls, value: Any) -> Any:
        json.dumps(value, allow_nan=False)
        return value


class Engine1Config(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    living_area_warning_fraction: float = Field(default=.05,ge=0)
    living_area_stop_fraction: float = Field(default=.25,gt=0)
    source_stale_days: int = Field(default=45,gt=0)
    small_multibed_area_review_sqft: float = Field(default=300,gt=0)

    @model_validator(mode='after')
    def thresholds(self):
        if self.living_area_stop_fraction <= self.living_area_warning_fraction:
            raise ValueError('Stop threshold must exceed warning threshold')
        return self


REQUIRED_FACTS=('living_area_sqft','bedrooms','bathrooms','year_built','property_type')

def reconcile(observations, config=None, *, source_priority=None):
    config=config or Engine1Config()
    groups=defaultdict(list)
    for obs in observations:
        # Spatial one-to-many results are retained in result.flood, not flattened into a scalar fact.
        if obs.field_name.startswith('flood.'):
            continue
        if obs.normalized_value is not None and obs.lifecycle_state=='existing':
            groups[obs.field_name].append(obs)
    selected, conflicts={},[]
    priority=source_priority or {'assessor':0,'parcel_gis':1,'municipality':2,'hazard_agency':3,'geocoder':4}
    for field,group in groups.items():
        official=sorted([o for o in group if o.source in priority and o.evidence_level=='A'],key=lambda o:priority[o.source])
        if not official:
            continue
        base=official[0]
        selected[field]=base
        for other in group:
            if other.observation_id==base.observation_id:
                continue
            a,b=base.normalized_value,other.normalized_value
            if field=='county_name' and isinstance(a,str) and isinstance(b,str):
                if a.strip().lower().removesuffix(' county')==b.strip().lower().removesuffix(' county'):
                    continue
            if a==b and base.unit==other.unit and base.area_basis==other.area_basis:
                continue
            severity='WARNING'
            reason='Sources disagree; authoritative observation retained, other observation preserved.'
            fraction=None
            if field=='living_area_sqft' and all(isinstance(v,(int,float)) and not isinstance(v,bool) and v>0 for v in (a,b)):
                fraction=abs(a-b)/a
                # Basis mismatches are never treated as proof of a numerical discrepancy having been explained.
                if fraction > config.living_area_stop_fraction:
                    severity='STOP'
                elif fraction <= config.living_area_warning_fraction:
                    severity='INFO'
                reason='Living area comparison against official value; confirm grade definition and effective dates.'
                if base.area_basis != other.area_basis:
                    severity='STOP' if severity=='STOP' else 'REVIEW_REQUIRED'
                    reason+=' Area bases differ; not interchangeable.'
            elif field in ('situs_address','parcel_id','county_fips','county_name','property_type'):
                severity='STOP'
            elif field in ('longitude','latitude'):
                severity='INFO'
                reason='Coordinates from address-range interpolation and property providers may describe different point locations; not a canonical parcel replacement.'
            elif field in ('bedrooms','bathrooms','full_bathrooms','half_bathrooms','stories','postal_code'):
                severity='WARNING'
            if other.source in priority and priority[other.source]==priority[base.source]:
                # Same-priority official conflicts cannot be resolved by arrival order.
                selected.pop(field,None)
                severity='STOP' if field in ('living_area_sqft','parcel_id','property_type') else 'REVIEW_REQUIRED'
            conflicts.append(dict(field_name=field,severity=severity,official_observation_id=base.observation_id,
                                  other_observation_id=other.observation_id,official_value=a,other_value=b,
                                  fractional_difference=fraction,reason=reason))
    return selected,conflicts


def summarize_domain(searches):
    if not searches:
        return dict(status='NOT_QUERIED',record_count=0,coverage='NONE')
    has_records=any(x.get('records') for x in searches)
    failed=any(x['status']=='SOURCE_UNAVAILABLE' for x in searches)
    return dict(status='AVAILABLE' if has_records else 'SOURCE_UNAVAILABLE' if failed else 'MISSING',
                record_count=sum(len(x.get('records',[])) for x in searches),
                coverage='PARTIAL_SOURCE_FAILURE' if failed else 'QUERIED_PUBLISHED_DATASETS',
                source_failures=sum(x['status']=='SOURCE_UNAVAILABLE' for x in searches),
                current_case_completeness='NOT_ESTABLISHED')


def sufficiency(parcel_status,selected,conflicts,domains,warnings):
    missing=[x for x in REQUIRED_FACTS if x not in selected]
    stops=[c['reason'] for c in conflicts if c['severity']=='STOP']
    if parcel_status=='UNSUPPORTED_JURISDICTION':
        verdict='UNSUPPORTED'
    elif parcel_status!='RESOLVED' or stops:
        verdict='STOP_IDENTITY'
    elif missing or any(c['severity']=='REVIEW_REQUIRED' for c in conflicts):
        verdict='REVIEW_REQUIRED'
    elif any(d['status'] in ('SOURCE_UNAVAILABLE','NOT_QUERIED','CONFLICTING') for d in domains.values()):
        verdict='REVIEW_REQUIRED'
    elif domains.get('zoning_land_use',{}).get('current_zoning_status')=='SOURCE_UNAVAILABLE':
        verdict='REVIEW_REQUIRED'
    elif warnings or conflicts:
        verdict='PASS_WITH_WARNINGS'
    else:
        verdict='PASS'
    return dict(verdict=verdict,missing_required_facts=missing,stop_reasons=stops,
                can_continue_automatically=verdict in ('PASS','PASS_WITH_WARNINGS'),
                final_investment_decision_enabled=False,
                meaning='Engine 1 data sufficiency only; never a BUY/PASS investment recommendation.')

