from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class Condition(StrEnum):
    GOOD='GOOD'; FAIR='FAIR'; POOR='POOR'; FAILED='FAILED'; UNKNOWN='UNKNOWN'


class Action(StrEnum):
    KEEP_NO_WORK='KEEP_NO_WORK'; MINOR_MAINTENANCE='MINOR_MAINTENANCE'; REPAIR='REPAIR'
    PARTIAL_REPLACEMENT='PARTIAL_REPLACEMENT'; FULL_REPLACEMENT='FULL_REPLACEMENT'; UPGRADE='UPGRADE'
    NEW_CONSTRUCTION='NEW_CONSTRUCTION'; FINISH_CONVERT='FINISH_CONVERT'; INSPECTION_REQUIRED='INSPECTION_REQUIRED'; UNKNOWN='UNKNOWN'


class WorkReason(StrEnum):
    REQUIRED='REQUIRED'; PROJECT_STANDARD='PROJECT_STANDARD'; DISCRETIONARY_VALUE_ADD='DISCRETIONARY_VALUE_ADD'; UNKNOWN='UNKNOWN'


PhotoCategory = Literal['exterior','roof','kitchen','bathroom','bedroom','living_room','dining_room','basement',
                        'mechanical','electrical','garage','hallway/stairs','yard','floor_plan','other','unknown']
Defect = Literal['missing','broken','cracked','water_staining','fire_damage','smoke_damage','exposed_framing',
    'exposed_wiring','missing_fixture','severe_wear','debris','unfinished','peeling','rotted','damaged_surface','apparent_moisture','other']


class MediaInput(StrictModel):
    media_id: str = Field(min_length=1,max_length=100)
    property_id: str
    source: Literal['LOCAL_UPLOAD','PROJECT_UPLOAD','AUTHORIZED_LISTING_PROVIDER','MLS_PROVIDER','OTHER_AUTHORIZED_PROVIDER']
    local_path: str | None = None
    source_reference: str
    source_url: str | None = None
    retrieved_uploaded_at: datetime
    captured_at: datetime | None = None
    capture_date_status: Literal['KNOWN','UNKNOWN'] = 'UNKNOWN'
    temporal_scope: Literal['CURRENT_REPORTED','HISTORICAL','UNKNOWN'] = 'UNKNOWN'
    rights_basis: str = Field(min_length=1)
    analysis_permitted: StrictBool = False
    external_share_permitted: StrictBool = False
    retention_mode: Literal['STABLE_REFERENCE','ORIGINAL_COPY_ALLOWED'] = 'STABLE_REFERENCE'
    categories: list[PhotoCategory] = Field(default_factory=lambda:['unknown'])
    category_source: Literal['USER','PROVIDER','UNKNOWN'] = 'UNKNOWN'
    room_instance_id: str | None = None
    kind: Literal['PHOTO','FLOOR_PLAN','DOCUMENT_PAGE','RENDERING'] = 'PHOTO'
    usability_override: Literal['LIMITED','UNUSABLE'] | None = None

    @model_validator(mode='after')
    def capture_date(self):
        if self.capture_date_status == 'KNOWN' and self.captured_at is None:
            raise ValueError('Known capture date requires a date')
        if self.captured_at is not None and self.capture_date_status != 'KNOWN':
            raise ValueError('Supplied capture date requires explicit KNOWN status')
        return self


class QuantityHint(StrictModel):
    value: float = Field(gt=0)
    unit: Literal['count','sqft','linear_ft']
    basis: Literal['VISIBLE_COUNT','STATED_MEASUREMENT']
    observed_object_ids: list[str] = Field(default_factory=list)
    whole_property_total: StrictBool = False


class ComponentEvidence(StrictModel):
    evidence_id: str
    property_id: str
    component_id: str
    source_kind: Literal['PHOTO_MANUAL','PHOTO_VISION','INSPECTION','FLOOR_PLAN','STRUCTURED_REPORTED']
    source_reference: str
    media_ids: list[str] = Field(default_factory=list)
    observed_at: datetime | None = None
    temporal_scope: Literal['CURRENT_REPORTED','HISTORICAL','UNKNOWN'] = 'UNKNOWN'
    condition: Condition = Condition.UNKNOWN
    action: Action = Action.UNKNOWN
    work_reason: WorkReason = WorkReason.UNKNOWN
    reason_reference: str | None = None
    defect_tags: list[Defect] = Field(default_factory=list)
    observation: str = Field(max_length=1000)
    confidence: float = Field(default=0,ge=0,le=1)
    visible_coverage: Literal['NONE','LIMITED','ADEQUATE'] = 'NONE'
    room_instance_id: str | None = None
    component_instance_id: str | None = None
    quantity_hint: QuantityHint | None = None
    review_status: Literal['UNREVIEWED','REVIEWED','REJECTED'] = 'UNREVIEWED'
    reviewer: str | None = None
    inspection_scope: str | None = None
    evidence_level: Literal['V','A','B','C','D','U'] = 'U'


class ListingText(StrictModel):
    text_id: str
    property_id: str
    text: str = Field(max_length=20000)
    source_reference: str
    observed_at: datetime | None = None
    temporal_scope: Literal['CURRENT_REPORTED','HISTORICAL','UNKNOWN'] = 'UNKNOWN'
    analysis_permitted: StrictBool = False
    quote_retention_permitted: StrictBool = False
    max_quote_characters: int = Field(default=120,ge=0,le=200)


class Engine1Context(StrictModel):
    contract_version: Literal['engine1-freeze-0.3.0']
    source_run_id: str
    source_reference: str
    source_sha256: str
    allowed_next_steps: dict[str,StrictBool]
    research_projection: dict
    administrative_events: list[dict] = Field(default_factory=list)


class ConditionInput(StrictModel):
    schema_version: Literal['0.1.0'] = '0.1.0'
    property_id: str
    engine1: Engine1Context
    media: list[MediaInput] = Field(default_factory=list,max_length=100)
    listing_texts: list[ListingText] = Field(default_factory=list,max_length=20)
    component_evidence: list[ComponentEvidence] = Field(default_factory=list,max_length=1000)

    @model_validator(mode='after')
    def associations(self):
        if self.engine1.research_projection.get('identity',{}).get('property_id') != self.property_id:
            raise ValueError('Engine 1 projection property mismatch')
        for items, key in [(self.media,'media_id'),(self.listing_texts,'text_id'),(self.component_evidence,'evidence_id')]:
            ids = [getattr(x,key) for x in items]
            if len(ids) != len(set(ids)):
                raise ValueError('Duplicate input identifiers')
            if any(x.property_id != self.property_id for x in items):
                raise ValueError('Evidence belongs to a different property')
        return self


class ConditionConfig(StrictModel):
    evidence_min_confidence: float = Field(default=.65,ge=0,le=1)
    min_unique_photos: int = Field(default=4,ge=1)
    min_room_categories: int = Field(default=3,ge=1)
    partial_component_coverage: float = Field(default=.20,gt=0,le=1)
    complete_component_coverage: float = Field(default=.80,gt=0,le=1)
    max_media_age_days: int = Field(default=365,gt=0)
    near_duplicate_hamming: int = Field(default=4,ge=0,le=16)
    observability_overrides: dict[str,Literal['OFTEN_OBSERVABLE','PARTIAL','NOT_REMOTELY_VERIFIABLE']] = Field(default_factory=dict)

    @model_validator(mode='after')
    def coverage_order(self):
        if self.partial_component_coverage > self.complete_component_coverage:
            raise ValueError('Partial coverage threshold exceeds complete coverage threshold')
        return self


class BenchmarkLabel(StrictModel):
    label_id: str
    property_id: str
    media_id: str | None
    categories: list[PhotoCategory]
    component_id: str | None
    condition_label: Condition | None
    action_label: Action | None
    defect_tags: list[Defect]
    severity_label: Literal['C0','C1','C2','C3','C4','C5','CX'] | None
    labeler: str
    review_status: Literal['DRAFT','REVIEWED','ADJUDICATED','REJECTED']
    notes: str
    provenance_reference: str
    split: Literal['TRAIN','VALIDATION','TEST','UNASSIGNED']
    evidence_date: datetime | None
    is_synthetic: StrictBool = False
    label_origin: Literal['HUMAN','SYNTHETIC'] = 'HUMAN'
