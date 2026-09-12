"""Versioned parent/child component IDs and configurable remote observability."""
from dataclasses import asdict, dataclass

GROUPS = {
    'structure': 'foundation framing_walls floor_structure roof_structure roof_decking concealed_framing',
    'exterior': 'roof_covering gutters siding exterior_paint masonry windows exterior_doors porch_deck driveway_walkways grading_drainage landscaping',
    'interior': 'walls ceilings paint flooring trim_baseboards doors stairs_railings',
    'kitchen': 'cabinets countertops sink_faucet appliances flooring walls_ceiling lighting',
    'bathroom': 'tub_shower toilet vanity sink_faucet tile_surround ventilation flooring walls',
    'systems': 'electrical_service visible_electrical plumbing_supply plumbing_waste water_heater furnace air_conditioning ductwork concealed_wiring concealed_plumbing sewer_lateral hvac_internal',
    'basement': 'structure moisture walls floor ceiling finish_status egress visible_utilities',
    'safety': 'exposed_wiring missing_fixtures water_intrusion broken_missing_windows missing_exterior_doors unsafe_stairs_railings fire_smoke major_debris sanitation_habitability',
    'environmental': 'asbestos lead concealed_mold concealed_termite_damage',
}
HIDDEN = {'structure.roof_decking','structure.concealed_framing','systems.concealed_wiring','systems.concealed_plumbing',
          'systems.sewer_lateral','systems.hvac_internal', *('environmental.'+s for s in GROUPS['environmental'].split())}
PARTIAL = {'structure.foundation','structure.framing_walls','structure.floor_structure','structure.roof_structure',
    'exterior.roof_covering','exterior.grading_drainage','basement.structure','basement.moisture','basement.egress',
    'safety.water_intrusion', *('systems.'+s for s in GROUPS['systems'].split())} - HIDDEN


@dataclass(frozen=True)
class Component:
    component_id: str
    parent_id: str | None
    label: str
    observability: str


def taxonomy(extensions=()):
    rows = [Component(g,None,g.replace('_',' ').title(),'GROUP') for g in GROUPS]
    rows += [Component(g+'.'+s,g,s.replace('_',' ').title(),
                      'NOT_REMOTELY_VERIFIABLE' if g+'.'+s in HIDDEN else 'PARTIAL' if g+'.'+s in PARTIAL else 'OFTEN_OBSERVABLE')
             for g,children in GROUPS.items() for s in children.split()]
    rows += list(extensions)
    ids = [r.component_id for r in rows]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate component IDs')
    for row in rows:
        if row.parent_id and row.parent_id not in ids:
            raise ValueError('Unknown parent component')
        if row.observability not in {'GROUP','OFTEN_OBSERVABLE','PARTIAL','NOT_REMOTELY_VERIFIABLE'}:
            raise ValueError('Unknown observability')
        visited = {row.component_id}
        parent = row.parent_id
        while parent:
            if parent in visited:
                raise ValueError('Cyclic component taxonomy')
            visited.add(parent)
            parent = next(r.parent_id for r in rows if r.component_id == parent)
    return {r.component_id:r for r in rows}


def export_taxonomy():
    return dict(version='0.1.0',components=[asdict(c) for c in taxonomy().values()])


def leaf_ids(components):
    parents={c.parent_id for c in components.values() if c.parent_id}
    return [cid for cid,c in components.items() if cid not in parents and c.observability!='GROUP']
