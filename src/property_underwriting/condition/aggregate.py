"""Explainable component aggregation. Confidence is evidence support, not measured accuracy."""
from collections import defaultdict
from datetime import datetime, timezone

from .models import ConditionConfig
from .taxonomy import leaf_ids

ORDER={'UNKNOWN':-1,'GOOD':0,'FAIR':1,'POOR':2,'FAILED':3}
ACTION_ORDER={'UNKNOWN':0,'KEEP_NO_WORK':1,'MINOR_MAINTENANCE':2,'UPGRADE':3,'REPAIR':4,
              'PARTIAL_REPLACEMENT':5,'FULL_REPLACEMENT':6,'NEW_CONSTRUCTION':7,'FINISH_CONVERT':8,'INSPECTION_REQUIRED':9}


def date_scope(scope, date, as_of, max_age):
    if scope!='CURRENT_REPORTED': return scope
    if date is None: return 'UNKNOWN'
    dt=datetime.fromisoformat(date.replace('Z','+00:00')) if isinstance(date,str) else date
    if dt.tzinfo is None: dt=dt.replace(tzinfo=timezone.utc)
    age=(as_of-dt).total_seconds()/86400
    return 'HISTORICAL' if age>max_age else 'UNKNOWN' if age<0 else scope


def prepare_evidence(evidence, media, components, config:ConditionConfig, as_of):
    by_id={m['media_id']:m for m in media}
    leaves=set(leaf_ids(components))
    prepared=[]
    for original in evidence:
        if original.component_id not in leaves:
            raise ValueError('Unknown/non-leaf component ID')
        if any(mid not in by_id for mid in original.media_ids):
            raise ValueError('Evidence references unknown media')
        row=original.model_dump(mode='json')
        row.update(eligible=False,exclusion_reasons=[],effective_condition=row['condition'],effective_action=row['action'],
                   effective_work_reason=row['work_reason'],policy_notes=[])
        row['effective_temporal_scope']=date_scope(original.temporal_scope,original.observed_at,as_of,config.max_media_age_days)
        inspection=(original.source_kind=='INSPECTION' and original.review_status=='REVIEWED'
                    and bool(original.reviewer) and bool(original.inspection_scope) and original.evidence_level=='V')
        photo=original.source_kind in {'PHOTO_MANUAL','PHOTO_VISION'}
        if photo:
            if not original.media_ids: row['exclusion_reasons'].append('PHOTO_ID_REQUIRED')
            for mid in original.media_ids:
                m=by_id[mid]
                if not m['condition_photo_eligible']: row['exclusion_reasons'].append('MEDIA_NOT_USABLE_CONDITION_PHOTO')
                if date_scope(m['temporal_scope'],m['captured_at'],as_of,config.max_media_age_days)!='CURRENT_REPORTED':
                    row['exclusion_reasons'].append('MEDIA_DATE_UNKNOWN_OR_HISTORICAL')
        elif not inspection:
            row['exclusion_reasons'].append('REPORTED_OR_PLAN_EVIDENCE_CONTEXT_ONLY')
        if original.review_status=='REJECTED': row['exclusion_reasons'].append('REJECTED_EVIDENCE')
        if row['effective_temporal_scope']!='CURRENT_REPORTED': row['exclusion_reasons'].append('NOT_CURRENT_DATED_EVIDENCE')
        if original.confidence<config.evidence_min_confidence: row['exclusion_reasons'].append('LOW_SUPPORT')
        profile=config.observability_overrides.get(original.component_id,components[original.component_id].observability)
        # Never make a concealed/environmental component visible by configuration alone.
        if components[original.component_id].observability=='NOT_REMOTELY_VERIFIABLE': profile='NOT_REMOTELY_VERIFIABLE'
        row['observability']=profile
        if not inspection and (profile=='NOT_REMOTELY_VERIFIABLE' or original.visible_coverage=='NONE' or
            (original.condition=='GOOD' and (profile=='PARTIAL' or original.visible_coverage!='ADEQUATE'))):
            row['effective_condition']='UNKNOWN'
            row['effective_action']='INSPECTION_REQUIRED'
            row['policy_notes'].append('REMOTE_OBSERVABILITY_LIMIT; absence of visible defects does not verify concealed condition.')
        if photo and (original.component_id.startswith('structure.') or original.component_id.startswith('environmental.')):
            if original.condition=='FAILED': row['effective_condition']='POOR' if profile!='NOT_REMOTELY_VERIFIABLE' else 'UNKNOWN'
            if original.action in {'FULL_REPLACEMENT','NEW_CONSTRUCTION','FINISH_CONVERT'}:
                row['effective_action']='INSPECTION_REQUIRED'
            row['policy_notes'].append('Visible signs only; no structural failure, mold, asbestos or material diagnosis from appearance.')
        if original.work_reason!='UNKNOWN' and not original.reason_reference:
            row['effective_work_reason']='UNKNOWN'
            row['policy_notes'].append('Work-reason classification requires a cited requirement, project standard or discretionary rationale.')
        if original.quantity_hint and photo and (original.quantity_hint.basis!='VISIBLE_COUNT' or original.quantity_hint.unit!='count' or original.quantity_hint.whole_property_total):
            row['policy_notes'].append('Unsupported photo dimension/whole-property quantity excluded; no geometric scale inferred.')
            row['quantity_hint']=None
        row['eligible']=not row['exclusion_reasons']
        row['verified_inspection']=bool(inspection)
        row['evidence_level']='D' if original.source_kind=='PHOTO_VISION' else row['evidence_level']
        prepared.append(row)
    return prepared


def aggregate_components(evidence, components, config):
    by_component=defaultdict(list)
    for row in evidence: by_component[row['component_id']].append(row)
    results=[]
    leaves=set(leaf_ids(components))
    for cid,component in components.items():
        if cid not in leaves: continue
        rows=by_component[cid]
        active=[r for r in rows if r['eligible']]
        instances=defaultdict(list)
        for row in active:
            instances[row['component_instance_id'] or row['room_instance_id'] or 'UNRESOLVED_INSTANCE'].append(row)
        conflicting=[]
        instance_conditions={}
        for instance,items in instances.items():
            states={r['effective_condition'] for r in items}-{ 'UNKNOWN' }
            actions={r['effective_action'] for r in items}-{ 'UNKNOWN','INSPECTION_REQUIRED' }
            if ('GOOD' in states and bool(states & {'POOR','FAILED'})) or ('KEEP_NO_WORK' in actions and bool(actions & {'REPAIR','PARTIAL_REPLACEMENT','FULL_REPLACEMENT','NEW_CONSTRUCTION'})):
                conflicting.extend(r['evidence_id'] for r in items)
            instance_conditions[instance]=max(states,key=ORDER.get) if states else 'UNKNOWN'
        known=[r for r in active if r['effective_condition']!='UNKNOWN']
        condition='UNKNOWN' if conflicting or not known else max((r['effective_condition'] for r in known),key=ORDER.get)
        action='INSPECTION_REQUIRED' if conflicting else max((r['effective_action'] for r in active),key=ACTION_ORDER.get,default='UNKNOWN')
        if condition=='UNKNOWN' and action in {'KEEP_NO_WORK','MINOR_MAINTENANCE'}: action='INSPECTION_REQUIRED'
        reasons={r['effective_work_reason'] for r in active}-{'UNKNOWN'}
        work_reason=next(iter(reasons)) if len(reasons)==1 else 'UNKNOWN'
        profile=config.observability_overrides.get(cid,component.observability)
        if component.observability=='NOT_REMOTELY_VERIFIABLE': profile=component.observability
        full_inspection=bool(active) and any(r['verified_inspection'] for r in active)
        inspection_required=bool(conflicting) or condition=='UNKNOWN' or action=='INSPECTION_REQUIRED' or profile!='OFTEN_OBSERVABLE' and not full_inspection
        notes=[n for r in rows for n in r['policy_notes']]
        if profile!='OFTEN_OBSERVABLE' and not full_inspection: notes.append('Inspection required for hidden/partially observable condition.')
        if not active: notes.append('No usable current dated component evidence; history/text/plans do not fill this gap.')
        if conflicting: notes.append('CONFLICTING_EVIDENCE: no silent majority vote or latest-photo selection.')
        hints=[dict(evidence_id=r['evidence_id'],component_instance_id=r['component_instance_id'],media_ids=r['media_ids'],**r['quantity_hint'])
               for r in active if r['quantity_hint']]
        results.append(dict(component_id=cid,parent_id=component.parent_id,condition=condition,recommended_action=action,
            work_reason=work_reason,confidence=max((r['confidence'] for r in known),default=0) if not conflicting else 0,
            confidence_meaning='MAX_SUPPORT_NOT_CALIBRATED_PROBABILITY; duplicates never increase it',
            evidence_ids=[r['evidence_id'] for r in rows],active_evidence_ids=[r['evidence_id'] for r in active],
            supporting_media_ids=sorted({mid for r in rows for mid in r['media_ids']}),contradictory_evidence_ids=conflicting,
            evidence_status='CONFLICTING_EVIDENCE' if conflicting else 'SUPPORTED' if known else 'UNKNOWN',
            inspection_required=inspection_required,observable_coverage='ADEQUATE' if known and any(r['visible_coverage']=='ADEQUATE' for r in known) else 'LIMITED' if active else 'NONE',
            observability=profile,hidden_risk='LOW' if full_inspection and condition=='GOOD' else 'UNKNOWN',
            instance_conditions=instance_conditions,known_component_instance_ids=sorted(i for i in instances if i!='UNRESOLVED_INSTANCE'),
            quantity_hints=hints,quantity_total=None,quantity_notes='Hints are not summed across photos. Missing object/instance identity remains unresolved.',
            notes=notes))
    return results
