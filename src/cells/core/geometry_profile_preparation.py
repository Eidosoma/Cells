"""Static profiles on a complete, replayable initial passive geometry artifact.

The frozen geometry and profile adapters retain their own complete recipes.
This adapter derives only their shared stable-owner view; colors, permutations,
physical inputs, geometry and intervention laws are never supplied implicitly.
"""

import json
from copy import deepcopy
from dataclasses import dataclass, fields
from pathlib import Path

import numpy as np

from cells.core import geometry_tissue_preparation as geometric
from cells.core import tissue_profile_preparation as profiles
from cells.core.specs import ConfigError, digest
from cells.processes import betse_tissue_profiles as native

BRIDGE_ID = "initial_geometry_static_profiles@1"
REQUEST_KIND = "cells.initial_geometry_profile_request@1"
KIND = "cells.initial_geometry_profile_preparation@1"


@dataclass(frozen=True)
class Preparation:
    definition: dict
    provenance: dict


def _keys(row, names, label):
    if type(row) is not dict or set(row) != set(names):
        raise ConfigError("Require exactly the declared " + label + " fields")


def _json(value):
    try:
        return json.loads(json.dumps(value, allow_nan=False))
    except (TypeError, ValueError, ArithmeticError) as error:
        raise ConfigError("Require complete finite JSON declarations") from error


def _derive(artifact, seed_fills):
    _keys(artifact, {"definition", "provenance"}, "geometry artifact")
    source = geometric.replay(artifact["provenance"])
    if digest(source.definition) != digest(artifact["definition"]) or digest(
        source.provenance
    ) != digest(artifact["provenance"]):
        raise ConfigError("Geometry artifact differs from its complete initial recipe")
    if source.definition["model"]["id"] != "resolved_tissue@1":
        raise ConfigError("Require an ordinary initial passive geometry preparation")
    recipe = source.provenance["request"]
    bound = geometric.bind_source(recipe["geometry_source"])
    cells, membranes, env = bound.mesh.cell_ids, bound.membrane_ids, bound.grid.environment_ids
    fills = None
    if seed_fills is not None:
        _keys(seed_fills, cells, "explicit stable-cell color tags")
        if any(type(value) is not str for value in seed_fills.values()):
            raise ConfigError("Require explicit string color tags; no palette is inferred")
        fills = tuple(seed_fills[name] for name in cells)
    k = bound.kernel
    layout = native.Layout(
        cell_ids=cells,
        membrane_ids=membranes,
        environment_ids=env,
        membrane_cell_ids=tuple(cells[i] for i in k.owner),
        membrane_environment_ids=tuple(env[i] for i in k.environment_owner),
        cell_membrane_ids=bound.cell_membrane_ids,
        cell_centres_m=np.asarray(bound.mesh.centres_m),
        bounds_m=bound.grid.bounds_m,
        seed_fills=fills,
    )
    physical = recipe["physics"]
    by_mid = {row["id"]: row for row in physical["membranes"]}
    neighbors = {name: [] for name in cells}
    for row in source.definition["model"]["junctions"]:
        a, b = row["sender"], row["receiver"]
        if b not in neighbors[a]:
            neighbors[a].append(b)
        if a not in neighbors[b]:
            neighbors[b].append(a)
    bridge = profiles.Geometry(
        layout=layout,
        thickness_m={name: by_mid[name]["thickness_m"] for name in membranes},
        partner_membrane_ids={name: membranes[k.partner[i]] for i, name in enumerate(membranes)},
        junction_membrane_ids={
            row["id"]: list(row["membrane_ids"]) for row in physical["junctions"]
        },
        cell_neighbor_ids=neighbors,
        provenance=dict(
            geometry_preparation_identity=source.provenance["identity"],
            geometry_binding_identity=bound.identity,
            generation_identity=digest(recipe["geometry_source"]["generation"]),
            centres="Bound polygon centroids; primal seed points are a separate field",
            thickness="Explicit physical per-membrane thickness; never generation tm",
            contacts="Bound reciprocal contacts plus declared physical junction IDs/orientation",
            colors="Caller-declared exact stable-cell tags or None; no inferred palette",
        ),
        length_unit="m",
        rho_channel=1.0,
    )
    return source, bridge


def derive_geometry(artifact, *, seed_fills=None):
    """Return the authoritative profile view, including its index-selector axis.

    Use native.layout_identity(view.layout) for an explicit positional selector.
    This function does not choose indices, percentage permutations or colors.
    """
    try:
        return _derive(_json(artifact), _json(seed_fills))[1]
    except (KeyError, TypeError, ValueError, ArithmeticError, AttributeError, IndexError) as error:
        raise ConfigError("Invalid initial geometry/profile binding: " + str(error)) from error


def _profile(row):
    _keys(row, {field.name for field in fields(native.Profile)}, "profile")
    _keys(row["selector"], {field.name for field in fields(native.Selector)}, "selector")
    if row["selector"]["kind"] == "image":
        _keys(row["selector"]["value"], {"grayscale_F"}, "decoded image")
    return profiles._decode_profile(row)


def prepare(request):
    """Prepare from a complete JSON recipe and retain both provenance chains."""
    try:
        request = _json(request)
        _keys(
            request,
            {
                "kind",
                "geometry_preparation",
                "seed_fills",
                "default",
                "profiles",
                "ion_enabled",
                "enabled",
                "is_ecm",
            },
            "geometry/profile request",
        )
        if request["kind"] != REQUEST_KIND:
            raise ConfigError("Require " + REQUEST_KIND)
        if type(request["profiles"]) is not list:
            raise ConfigError("Require an ordered explicit profile list")
        source, view = _derive(request["geometry_preparation"], request["seed_fills"])
        result = profiles.prepare(
            source.definition,
            view,
            _profile(request["default"]),
            [_profile(row) for row in request["profiles"]],
            ion_enabled=request["ion_enabled"],
            enabled=request["enabled"],
            is_ecm=request["is_ecm"],
        )
        p, g = result.provenance, source.provenance
        inventory = digest(
            {key: result.definition["model"][key] for key in ("species", "cells", "extracellular")}
        )
        if (
            p["initial_state_sha256"] != g["initial_state_sha256"]
            or p["state_fields"] != g["initial_state_fields"]
            or inventory != g["physical_inventory_sha256"]
            or digest(result.definition["experiment"]) != g["control_history_sha256"]
        ):
            raise ConfigError(
                "Static profiles changed initial physical state, inventory or controls"
            )
        restored = deepcopy(result.definition)
        for change in p["changes"]:
            row = next(
                row
                for row in restored["model"][change["domain"] + "s"]
                if row["id"] == change["id"]
            )
            row["permeability_m_per_s"][change["species_id"]] = change["before"]
        if digest(restored) != digest(source.definition):
            raise ConfigError("Profile integration changed a nonselected definition property")
        record = dict(
            kind=KIND,
            bridge_id=BRIDGE_ID,
            request=request,
            request_sha256=digest(request),
            geometry_preparation_identity=g["identity"],
            profile_preparation=p,
            profile_preparation_identity=p["identity"],
            derived_geometry_sha256=digest(p["geometry"]),
            derived_layout_identity=native.layout_identity(view.layout),
            prepared_definition_sha256=digest(result.definition),
            initial_state_sha256=p["initial_state_sha256"],
            initial_state_fields=p["state_fields"],
            physical_inventory_sha256=inventory,
            control_history_sha256=g["control_history_sha256"],
            changes=p["changes"],
            scope=(
                "Initial passive geometry plus static membrane/insular profiles; "
                "no new physics, remap, cuts or moving geometry"
            ),
        )
        record = _json(record)
        record["identity"] = digest(record)
        return Preparation(result.definition, record)
    except (KeyError, TypeError, ValueError, ArithmeticError, AttributeError, IndexError) as error:
        raise ConfigError("Invalid complete geometry/profile request: " + str(error)) from error


def replay(provenance):
    try:
        row = deepcopy(provenance)
        identity = row.pop("identity")
        if row["kind"] != KIND or identity != digest(row):
            raise ConfigError("Stale geometry/profile preparation identity")
        result = prepare(row["request"])
        if digest(result.provenance) != digest(provenance):
            raise ConfigError("Geometry/profile provenance chains or derived owners changed")
        return result
    except (KeyError, TypeError, ValueError, ArithmeticError) as error:
        raise ConfigError("Invalid complete geometry/profile preparation: " + str(error)) from error


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ConfigError("Duplicate JSON field: " + key)
        result[key] = value
    return result


def _nonfinite(value):
    raise ConfigError("Nonfinite JSON value: " + value)


def read_json(path):
    try:
        return _json(
            json.loads(
                Path(path).read_text(encoding="utf-8"),
                object_pairs_hook=_unique,
                parse_constant=_nonfinite,
            )
        )
    except (ValueError, TypeError, RecursionError) as error:
        raise ConfigError("Invalid finite geometry/profile JSON: " + str(error)) from error


def write_preparation(directory, prepared):
    expected = replay(prepared.provenance)
    if digest(expected.definition) != digest(prepared.definition):
        raise ConfigError("Prepared definition changed relative to both source recipes")
    path = Path(directory)
    path.mkdir(parents=True, exist_ok=False)
    for name, value in (
        ("definition.json", expected.definition),
        ("provenance.json", expected.provenance),
    ):
        (path / name).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    return path


def read_preparation(directory):
    path = Path(directory)
    result = replay(read_json(path / "provenance.json"))
    if digest(read_json(path / "definition.json")) != digest(result.definition):
        raise ConfigError("Prepared definition differs from complete geometry/profile replay")
    return result
