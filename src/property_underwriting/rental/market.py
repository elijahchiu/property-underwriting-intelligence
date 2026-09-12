"""Rental comparables: asking evidence never becomes achieved rent."""
from copy import deepcopy
from dataclasses import asdict, dataclass
from statistics import median
import math
from property_underwriting.valuation.engine import weighted_quantile
from property_underwriting.valuation.evidence import address_key, distance_miles
from property_underwriting.valuation.models import number
from .official import local_day


@dataclass(frozen=True)
class RentConfig:
    # radius, evidence age days, area fraction, bed difference, bath difference
    tiers: tuple = ((.75,90,.25,0,.5),(1.5,180,.4,1,1),(3,365,.5,1,1))
    weights: tuple = (.25,.15,.25,.15,.10,.10)
    min_comps: int = 3
    min_compatible: int = 2
    max_comps: int = 8
    avm_disagreement: float = .20

    def __post_init__(self):
        if len(self.weights)!=6 or any(not math.isfinite(w) or w<0 for w in self.weights) or not math.isclose(sum(self.weights),1):
            raise ValueError("Six finite nonnegative weights summing to one required")
        if not 3<=self.min_comps<=self.max_comps or not 2<=self.min_compatible<=self.min_comps: raise ValueError("Invalid count limits")
        if not self.tiers or any(len(t)!=5 or any(not math.isfinite(x) or x<0 for x in t) or min(t[:3])<=0 for t in self.tiers):
            raise ValueError("Invalid tiers")
        if any(any(a>b for a,b in zip(x,y)) for x,y in zip(self.tiers,self.tiers[1:])): raise ValueError("Tiers must expand")
        if not math.isfinite(self.avm_disagreement) or self.avm_disagreement<=0: raise ValueError("Invalid disagreement threshold")


def classify(record, as_of):
    ev=deepcopy(record.get("condition_evidence") or {})
    effective,available=local_day(ev.get("effective_date")),local_day(ev.get("available_at"))
    observed=local_day(record.get("effective_date"))
    valid=bool(ev.get("review_status")=="REVIEWED" and ev.get("source_reference") and ev.get("evidence_text")
               and effective and available and observed and effective<=observed<=as_of and available<=as_of)
    category=ev.get("classification") if valid else "UNKNOWN_CONDITION"
    if category not in {"RENOVATED_COMP","AVERAGE_MARKET_COMP","DISTRESSED_COMP","UNKNOWN_CONDITION"}: category="UNKNOWN_CONDITION"
    compatible=category=="RENOVATED_COMP" and ev.get("renovation_quality") in {"STANDARD","RENTAL_READY","FUNCTIONALLY_RENOVATED"}
    return dict(classification=category,target_compatible=compatible,raw_evidence=ev)


def market_rent(subject, records, as_of, *, config=None, avm=None):
    config=config or RentConfig(); accepted=[]; rejected=[]; candidates=[]
    for index,raw in enumerate(records):
        r=deepcopy(raw); source=deepcopy(raw.get("source") or {}); reasons=[]
        basis=r.get("rent_basis"); amount=number(r.get("asking_rent") if basis=="ASKING_RENT" else r.get("verified_rent"))
        r.update(comp_id=str(r.get("comp_id") or f"rental-{index}"),source=source,raw_record=deepcopy(raw),
            amount=amount,condition=classify(r,as_of),exclusions=reasons,dollar_adjustments=[],warnings=[])
        r["property_key"]=address_key(r.get("address"),r.get("state"))
        r["distance_miles"]=distance_miles(subject.get("latitude"),subject.get("longitude"),r.get("latitude"),r.get("longitude"))
        for key in ("living_sqft","beds","baths","year_built"): r[key]=number(r.get(key))
        effective,retrieved,available=map(local_day,(r.get("effective_date"),source.get("retrieved_at"),source.get("available_at")))
        if not r.get("address") or not source.get("source_id") or not source.get("provider"): reasons.append("MISSING_IDENTITY_OR_SOURCE")
        if r["property_key"]==address_key(subject["address"],subject["state"]): reasons.append("SUBJECT_NOT_COMP")
        if r.get("state")!=subject["state"] or r.get("county_fips")!=subject["county_fips"]: reasons.append("GEOGRAPHY_MISMATCH_OR_UNKNOWN")
        if r["distance_miles"] is None: reasons.append("VALID_COORDINATES_REQUIRED")
        if r.get("property_type")!=subject["property_type"]: reasons.append("PROPERTY_TYPE_MISMATCH")
        if basis not in {"ASKING_RENT","LEASED_RENT","CONTRACT_RENT"}: reasons.append("MODELED_OR_UNKNOWN_RENT_NOT_COMP")
        if basis in {"LEASED_RENT","CONTRACT_RENT"} and not r.get("verification_reference"): reasons.append("ACHIEVED_RENT_VERIFICATION_REQUIRED")
        if r.get("assisted") is True or (basis=="CONTRACT_RENT" and r.get("assisted") is not False): reasons.append("NOT_CONFIRMED_PRIVATE_MARKET_RENT")
        if r.get("rental_term")!="LONG_TERM": reasons.append("LONG_TERM_RENT_REQUIRED")
        if r.get("rent_period")!="MONTH": reasons.append("MONTHLY_BASIS_REQUIRED")
        if amount is None or amount<=0: reasons.append("MISSING_VALID_RENT")
        if any(x is None for x in (effective,retrieved,available)) or any(x>as_of for x in (effective,retrieved,available) if x): reasons.append("MISSING_OR_FUTURE_DATES")
        elif available<effective: reasons.append("EVIDENCE_PREDATES_RENT")
        if not r["living_sqft"] or r["living_sqft"]<=0 or any(r[k] is None or r[k]<0 for k in ("beds","baths")): reasons.append("MISSING_VALID_CONFIGURATION")
        if r["condition"]["classification"]=="DISTRESSED_COMP": reasons.append("DISTRESSED_NOT_RENOVATED_TARGET")
        if r["condition"]["raw_evidence"].get("renovation_quality")=="LUXURY" or r.get("luxury"): reasons.append("LUXURY_NOT_TARGET")
        if r.get("cross_submarket"): reasons.append("CROSS_SUBMARKET_REVIEW_REQUIRED")
        if reasons: rejected.append(r); continue
        diffs=(r["distance_miles"],(as_of-effective).days,abs(r["living_sqft"]/subject["living_sqft"]-1),abs(r["beds"]-subject["beds"]),abs(r["baths"]-subject["baths"]))
        tier=next((i for i,t in enumerate(config.tiers) if all(x<=y for x,y in zip(diffs,t))),None)
        if tier is None: reasons.append("OUTSIDE_DISTANCE_RECENCY_SIZE_CONFIGURATION_TIERS"); rejected.append(r); continue
        condition_score=1 if r["condition"]["target_compatible"] else .55 if r["condition"]["classification"]=="AVERAGE_MARKET_COMP" else .2
        scores=[max(0,1-x/(limit if i<3 else limit+1)) for i,(x,limit) in enumerate(zip(diffs,config.tiers[-1]))]+[condition_score]
        keys=("distance","recency","sqft","beds","baths","condition")
        r.update(tier=tier,similarity_subscores=dict(zip(keys,scores)),similarity_contributions=dict(zip(keys,[x*w for x,w in zip(scores,config.weights)])),
            similarity_weight=max(.001,sum(x*w for x,w in zip(scores,config.weights))*(1 if r["condition"]["target_compatible"] else .3)),
            rent_per_sqft=amount/r["living_sqft"],evidence_confidence=source.get("evidence_level","U"),source_occurrences=[deepcopy(raw)])
        candidates.append(r)
    # One weight per physical address and basis cohort, independent of repeat dates or documents.
    groups={}
    for r in candidates: groups.setdefault((r["property_key"],"ASKING" if r["rent_basis"]=="ASKING_RENT" else "ACHIEVED"),[]).append(r)
    unique=[]; duplicates=[]
    for key,rows in groups.items():
        rows.sort(key=lambda r:(r["effective_date"],r["comp_id"]),reverse=True)
        first=rows[0]; first["source_occurrences"]=[x["raw_record"] for x in rows]
        same=[r for r in rows if r["effective_date"]==first["effective_date"]]
        if any(len({json_value(r[k]) for r in same})>1 for k in ("amount","living_sqft","beds","baths","condition")):
            first["exclusions"].append("CONFLICTING_DUPLICATE_EVIDENCE"); rejected.append(first)
        else: unique.append(first)
        duplicates += [dict(comp_id=r["comp_id"],duplicate_of=first["comp_id"],reason="ONE_PROPERTY_COHORT_ONE_WEIGHT") for r in rows[1:]]
    cohorts={}
    for cohort in ("ACHIEVED","ASKING"):
        pool=[r for r in unique if (r["rent_basis"]=="ASKING_RENT")== (cohort=="ASKING")]
        selected=[]; history=[]
        for i in range(len(config.tiers)):
            selected=sorted((r for r in pool if r["tier"]<=i),key=lambda r:(not r["condition"]["target_compatible"],-r["similarity_weight"],r["comp_id"]))[:config.max_comps]
            history.append(dict(tier=i,selected=len(selected)))
            if len(selected)>=config.min_comps and sum(r["condition"]["target_compatible"] for r in selected)>=config.min_compatible: break
        logs=[math.log(r["rent_per_sqft"]) for r in selected]; center=median(logs) if logs else 0; mad=median([abs(x-center) for x in logs]) if logs else 0
        for r,x in zip(selected,logs):
            flag=len(logs)>=3 and abs(x-center)>(3.5*1.4826*mad if mad>1e-9 else math.log(1.6))
            r.update(outlier_flag=flag,final_weight=r["similarity_weight"]*(.25 if flag else 1),selection_reason=f"{cohort} cohort; tier {r['tier']}; no fabricated dollar adjustments")
        compat=[r for r in selected if r["condition"]["target_compatible"]]
        total=sum(r["final_weight"] for r in selected)
        share=sum(r["final_weight"] for r in compat)/total if total else 0
        enough=len(selected)>=config.min_comps and len(compat)>=config.min_compatible and share>=.6
        quant=lambda field,q,rows=selected: weighted_quantile([r[field] for r in rows],[r["final_weight"] for r in rows],q)
        scenario=dict(conservative=round(quant("amount",.25)),base=round(quant("amount",.5)),upside=round(max(quant("amount",.5),quant("amount",.75,compat)))) if enough else None
        cohorts[cohort]=dict(status="READY" if enough else "INSUFFICIENT",selected_comps=selected,range=scenario,tier_history=history,
            compatible_weight_share=share,rent_per_sqft_cross_check=dict(median=median(r["rent_per_sqft"] for r in selected),weighted_median=quant("rent_per_sqft",.5),low=quant("rent_per_sqft",.25),high=quant("rent_per_sqft",.75),comp_ids=[r["comp_id"] for r in selected]) if selected else None)
    chosen="ACHIEVED" if cohorts["ACHIEVED"]["range"] else "ASKING" if cohorts["ASKING"]["range"] else None
    selected=cohorts[chosen]["selected_comps"] if chosen else []
    result_range=cohorts[chosen]["range"] if chosen else None
    selected_keys={(r["property_key"],r["rent_basis"]) for r in selected}
    for r in unique:
        if (r["property_key"],r["rent_basis"]) not in selected_keys:
            r=deepcopy(r); r["exclusions"].append("NOT_PRIMARY_COHORT_OR_INSUFFICIENT_SUPPORT"); rejected.append(r)
    benchmark=deepcopy(avm) if avm else dict(estimate=None,status="NOT_AVAILABLE")
    benchmark["role"]="EXTERNAL_RENT_AVM_BENCHMARK"; conflicts=[]
    if avm:
        valid=number(avm.get("estimate")); retrieved=local_day(avm.get("retrieved_at"))
        benchmark["status"]="AVAILABLE" if valid and valid>0 and retrieved and 0<=(as_of-retrieved).days<=30 and avm.get("source_id") and avm.get("provider") else "REJECTED_INVALID_STALE_OR_FUTURE"
        if result_range and benchmark["status"]=="AVAILABLE" and abs(valid-result_range["base"])/result_range["base"]>config.avm_disagreement:
            conflicts.append("RENT_AVM_DISAGREEMENT_NOT_AVERAGED")
    return dict(status="READY" if chosen=="ACHIEVED" else "PARTIAL" if chosen else "INSUFFICIENT",
        MARKET_RENT_CONSERVATIVE=result_range["conservative"] if result_range else None,MARKET_RENT_BASE=result_range["base"] if result_range else None,
        MARKET_RENT_UPSIDE=result_range["upside"] if result_range else None,range_basis=chosen,scenario_not_confidence_interval=True,
        method="WEIGHTED_UNADJUSTED_RENT_QUANTILES_SEPARATE_BASIS_COHORTS",accepted_comps=selected,rejected_comps=rejected,
        candidate_count=len(records),accepted_comp_count=len(selected),rejected_comp_count=len(rejected),duplicate_occurrences=duplicates,
        cohorts=cohorts,external_rent_avm_benchmark=benchmark,conflicts=conflicts,config=asdict(config),confidence="LOW" if chosen else "INSUFFICIENT",
        limitations=["Asking cohort is asking-market evidence, never achieved or approved rent","Unknown utility inclusions and concessions require review; no hidden adjustment","No HCV parameters determine private market rent"])


def json_value(value):
    import json
    return json.dumps(value,sort_keys=True)
