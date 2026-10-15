"""Small, reproducible preparation and integration step for fictional fixtures."""

from __future__ import annotations

from copy import deepcopy
import math


def _clean_id(value):
    return " ".join(str(value).strip().lower().split())


def _unique(rows, label, id_transform=lambda value: str(value).strip()):
    result = {}
    for source in rows:
        row = deepcopy(source)
        row["id"] = id_transform(row.get("id", ""))
        if not row["id"]:
            raise ValueError(f"{label} record is missing an id")
        prior = result.get(row["id"])
        if prior is not None and prior != row:
            raise ValueError(f"Conflicting duplicate {label} id: {row['id']}")
        result[row["id"]] = row
    return list(result.values())


def _number(value, field):
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field} must be numeric") from None
    if not math.isfinite(number):
        raise ValueError(f"{field} must be finite")
    return number


def prepare_dataset(raw):
    """Clean fixture keys, reject conflicting IDs, validate, and join datasets.

    The output is a derived view; the bundled source fixture is never rewritten.
    All records processed here are fictional examples.
    """
    markets = _unique(raw.get("markets", []), "market", _clean_id)
    properties = _unique(raw.get("properties", []), "property")
    projects = _unique(raw.get("synthetic_scope_projects", []), "scope project")
    market_index = {}
    for market in markets:
        market_index[market["id"]] = market
    integrated_properties = []
    for prop in properties:
        prop["market_id"] = _clean_id(prop.get("market_id", ""))
        market = market_index.get(prop["market_id"])
        if market is None:
            raise ValueError(f"Property {prop['id']} references an unknown market")
        prop["sqft"] = _number(prop.get("sqft"), "property sqft")
        prop["asking_price"] = _number(prop.get("asking_price"), "asking price")
        prop["market_name"] = market["name"].strip()
        prop["sales_count"] = len(_unique(prop.get("comps", {}).get("sales", []), "sale comp"))
        prop["rental_count"] = len(_unique(prop.get("comps", {}).get("rentals", []), "rental comp"))
        integrated_properties.append(prop)
    integrated_projects = []
    for project in projects:
        project["market_id"] = _clean_id(project.get("market_id", ""))
        if project["market_id"] not in market_index:
            raise ValueError(f"Scope project {project['id']} references an unknown market")
        project["property_type"] = " ".join(str(project.get("property_type", "")).split())
        project["year_built"] = int(_number(project.get("year_built"), "project year built"))
        project["sqft"] = _number(project.get("sqft"), "project sqft")
        project["baths"] = _number(project.get("baths", 1), "project baths")
        project["costs"] = {key: _number(value, f"costs.{key}") for key, value in project.get("costs", {}).items()}
        integrated_projects.append(project)
    return {
        "properties": integrated_properties,
        "markets": markets,
        "scope_projects": integrated_projects,
        "quality": {
            "fictional": True,
            "property_rows": len(integrated_properties),
            "market_rows": len(markets),
            "scope_project_rows": len(integrated_projects),
            "property_duplicate_ids_removed": len(raw.get("properties", [])) - len(properties),
            "scope_duplicate_ids_removed": len(raw.get("synthetic_scope_projects", [])) - len(projects),
        },
    }
