"""Bind static native barrier coefficients to finite resolved extracellular owners.

The native overwrite order supplies site diffusion coefficients. Explicit ionic
modulators and a declared harmonic face conversion feed Cells' existing logmean
transport, field and energy laws. This is initial preparation, not a live barrier
intervention, native collocated update, Bernoulli face solver or flow model.
"""

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass, fields
from pathlib import Path

import numpy as np

from cells.core.specs import ConfigError, digest, parse_spec
from cells.core.surface_tissue_spec import SurfaceTissueModel
from cells.models import surface_tissue
from cells.processes import betse_environment_transport as native

BRIDGE_ID = "resolved_static_environment_barriers@1"
REQUEST_KIND = "cells.environment_barrier_preparation_request@1"
KIND = "cells.environment_barrier_preparation@1"
CONVERSION = "harmonic_ionic_site_diffusion_to_logmean_faces@1"
REQUEST_FIELDS = {
    "schema_version",
    "kind",
    "definition",
    "grid",
    "regions",
    "free_diffusion_m2_s",
    "relative_TJ",
    "adherens_factor",
    "tight_factor",
    "ion_modulators",
    "perimeter_policy",
}
REGION_FIELDS = {
    "cluster_sites",
    "boundary_membrane_sites",
    "neighbor_membrane_sites",
    "boundary_cell_sites",
}
SOURCE_CORRESPONDENCE = {
    "native_version": "1.5.0",
    "native_revision": "5269a714aa2593ed2a6708c4516289977d8ae1a2",
    "coefficient_kernel_sha256": "7cf5b793964f9b34dccd85b04982a3c2f2e92f3b043b8e04a30a647409afe42c",
    "source_law": native.SOURCE_LAW_ID,
    "native_scope": "Static initDenv overwrite order and prescribed ionic TJ multiplication",
    "cells_face_law": "logmean_electrodiffusion@1",
    "excluded": (
        "Native collocated update/bath setters, Bernoulli face law, flow and moving geometry"
    ),
}
UNITS = {
    "diffusion": "m2/s",
    "coordinates_and_lengths": "m",
    "face_area": "m2",
    "grid_volume": "m3",
    "tissue_volume": "pL",
    "volume_conversion": "1 m3 = 1e15 pL",
    "barrier_factors_and_modulators": "dimensionless",
    "face_conversion": "2*D_left*D_right/(D_left+D_right), zero if either is zero",
}


@dataclass(frozen=True)
class Preparation:
    definition: dict
    provenance: dict


def _json(value):
    try:
        return json.loads(json.dumps(value, allow_nan=False))
    except (TypeError, ValueError, OverflowError, RecursionError) as error:
        raise ConfigError("Require complete finite JSON barrier declarations") from error


def _keys(value, names, label):
    if type(value) is not dict or set(value) != set(names):
        raise ConfigError("Require complete exact " + label + " fields")
    return value


def _number(value, label):
    if type(value) not in (int, float) or not np.isfinite(value) or value < 0:
        raise ConfigError("Require finite nonnegative " + label)
    return float(value)


def _species_vector(value, species, label):
    _keys(value, species, label)
    return np.asarray([_number(value[name], label) for name in species], dtype=float)


def _same_measure(actual, expected, label):
    if (
        not np.isfinite(expected)
        or expected <= 0
        or not np.isclose(actual, expected, rtol=64 * np.finfo(float).eps, atol=0)
    ):
        raise ConfigError("Physical " + label + " disagrees with the explicit grid measure")


def _bind_grid(raw, model):
    _keys(raw, {f.name for f in fields(native.GridSpec)}, "grid")
    for name, rows in (("valence", [raw["valence"]]), ("coordinates", raw["coordinates_m"])):
        if type(rows) is not list or any(
            type(row) is not list or any(type(v) not in (int, float) for v in row) for row in rows
        ):
            raise ConfigError("Require explicit numeric grid " + name + " axes")
    grid = native.bind_grid(native.GridSpec(**raw))
    if set(grid.site_ids) != {row.id for row in model.extracellular}:
        raise ConfigError("Grid sites must match all finite extracellular owner IDs")
    if set(grid.species_ids) != set(model.species_ids):
        raise ConfigError("Grid species must match the complete tissue species IDs")
    valence = dict(zip(model.species_ids, model.valence, strict=True))
    for name, value in zip(grid.species_ids, grid.kernel.valence, strict=True):
        if value != valence[name]:
            raise ConfigError("Grid species valence disagrees with the physical owner")
    if any(row.reservoir for row in model.extracellular):
        raise ConfigError("Static sealed barriers require finite extracellular owners")
    outside = {row.id: row for row in model.extracellular}
    for i, name in enumerate(grid.site_ids):
        _same_measure(outside[name].volume_pL, grid.kernel.volume_m3[i] * 1e15, "site volume")
    faces = {row.id: row for row in model.faces}
    if set(grid.internal_face_ids) != set(faces):
        raise ConfigError("Grid internal faces must match every physical tissue face ID")
    physical_ids = {
        row.id
        for rows in (
            model.cells,
            model.extracellular,
            model.membranes,
            model.junctions,
            model.faces,
        )
        for row in rows
    }
    if physical_ids.intersection(grid.boundary_face_ids):
        raise ConfigError("Sealed perimeter IDs must be distinct from physical owner/route IDs")
    for i, name in enumerate(grid.internal_face_ids):
        face = faces[name]
        a = grid.site_ids[int(grid.kernel.senders[i])]
        b = grid.site_ids[int(grid.kernel.receivers[i])]
        if {face.sender, face.receiver} != {a, b}:
            raise ConfigError("Grid face endpoints disagree with their physical owners")
        _same_measure(face.area_m2, grid.kernel.internal_area_m2[i], "face area")
        _same_measure(face.length_m, grid.kernel.internal_distance_m[i], "face length")
    return grid


def _coefficients(raw, grid):
    regions = _keys(raw["regions"], REGION_FIELDS, "barrier regions")
    for values in regions.values():
        if type(values) is not list or any(type(v) is not str for v in values):
            raise ConfigError("Barrier regions require ordered stable-ID occurrence lists")
    free = _species_vector(raw["free_diffusion_m2_s"], grid.species_ids, "free diffusivity")
    relative = _species_vector(
        raw["relative_TJ"], grid.species_ids, "relative tight-junction factor"
    )
    _keys(raw["ion_modulators"], grid.species_ids, "ionic modulator species")
    modifiers = []
    for species in grid.species_ids:
        row = _keys(raw["ion_modulators"][species], grid.site_ids, "ionic modulator sites")
        modifiers.append([_number(row[site], "ionic modulator") for site in grid.site_ids])
    modifiers = np.asarray(modifiers)
    # Keep source sodium normalization and overlap precedence, including refusal
    # of a zero sodium maximum; do not add a conductivity floor.
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        barriers = native.init_barriers(
            grid,
            native.Regions(**regions),
            free,
            relative,
            _number(raw["adherens_factor"], "adherens factor"),
            _number(raw["tight_factor"], "tight factor"),
        )
        effective = barriers.diffusion_m2_s * modifiers
    if not all(
        np.isfinite(v).all() for v in (barriers.diffusion_m2_s, barriers.sodium_weight, effective)
    ):
        raise ConfigError("Barrier coefficients exceed finite float64")
    left = effective[:, grid.kernel.senders]
    right = effective[:, grid.kernel.receivers]
    low, high = np.minimum(left, right), np.maximum(left, right)
    # Equivalent harmonic mean without overflowing the product or reciprocal
    # of finite endpoint diffusivities. Both-zero faces remain exactly zero.
    denominator = np.where(high > 0, high, 1.0)
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        harmonic = low / (0.5 + 0.5 * (low / denominator))
    if not np.isfinite(harmonic).all():
        raise ConfigError("Face diffusivity exceeds finite float64")
    return barriers, modifiers, effective, harmonic


def _map(values, species, owners):
    return {
        name: {owner: float(values[i, j]) for j, owner in enumerate(owners)}
        for i, name in enumerate(species)
    }


def _state_identity(state):
    return digest(
        {
            name: {
                "dtype": np.asarray(value).dtype.str,
                "shape": list(np.asarray(value).shape),
                "sha256": hashlib.sha256(np.asarray(value).tobytes(order="C")).hexdigest(),
            }
            for name, value in state._asdict().items()
        }
    )


def prepare(request):
    """Prepare initial coefficients; preserve every physical owner and inventory."""
    try:
        raw = _json(_keys(request, REQUEST_FIELDS, "barrier request"))
        if type(raw["schema_version"]) is not int or raw["schema_version"] != 1:
            raise ConfigError("Require barrier request schema_version 1")
        if raw["kind"] != REQUEST_KIND or raw["perimeter_policy"] != "sealed":
            raise ConfigError("Require the explicit static barrier request and sealed perimeter")
        if type(raw["definition"]) is not dict or type(raw["definition"].get("model")) is not dict:
            raise ConfigError("Require a complete ordinary passive tissue definition")
        if raw["definition"]["model"].get("id") != surface_tissue.MODEL_ID:
            raise ConfigError("Static environment preparation currently supports resolved_tissue@1")
        spec = parse_spec(raw["definition"])
        if type(spec.model) is not SurfaceTissueModel:
            raise ConfigError("Require the exact passive tissue owner type")
        source = spec.to_dict()
        grid = _bind_grid(raw["grid"], spec.model)
        barriers, modifiers, effective, harmonic = _coefficients(raw, grid)
        face_values = _map(harmonic, grid.species_ids, grid.internal_face_ids)
        result, changes = deepcopy(source), []
        for face in result["model"]["faces"]:
            for species in spec.model.species_ids:
                old = face["diffusivity_m2_per_s"][species]
                new = face_values[species][face["id"]]
                face["diffusivity_m2_per_s"][species] = new
                if old != new:
                    changes.append(
                        dict(
                            face_id=face["id"], species_id=species, before_m2_s=old, after_m2_s=new
                        )
                    )
        # Re-run the actual field/domain admission. A disconnected or singular
        # physical tissue must refuse; the bridge never repairs it with leakage.
        prepared = parse_spec(result)
        before, _ = surface_tissue.initial_values(spec)
        after, _ = surface_tissue.initial_values(prepared)
        if type(after) is not type(before) or _state_identity(after) != _state_identity(before):
            raise ConfigError("Barrier preparation must preserve the complete initial state")
        provenance = _json(
            dict(
                kind=KIND,
                bridge_id=BRIDGE_ID,
                request=raw,
                source_definition_sha256=digest(source),
                prepared_definition_sha256=digest(result),
                grid=native.grid_manifest(grid),
                barrier_identity=barriers.identity,
                conversion=CONVERSION,
                units=UNITS,
                source_correspondence=SOURCE_CORRESPONDENCE,
                coefficients=dict(
                    site_base_m2_s=_map(barriers.diffusion_m2_s, grid.species_ids, grid.site_ids),
                    site_effective_m2_s=_map(effective, grid.species_ids, grid.site_ids),
                    face_m2_s=face_values,
                ),
                sodium_weight={
                    name: float(barriers.sodium_weight[i]) for i, name in enumerate(grid.site_ids)
                },
                target_site_occurrences=list(barriers.target_site_ids),
                ionic_modulators=_map(modifiers, grid.species_ids, grid.site_ids),
                changes=changes,
                state_fields=list(before._fields),
                initial_state_sha256=_state_identity(before),
                scope=(
                    "Initial static ionic barriers on a finite sealed uniform grid. Existing Cells "
                    "Logmean transport, charge/current closure and material/energy ledgers remain. "
                    "No native stencil, bath event, dynamic barrier, moving geometry or flow claim."
                ),
            )
        )
        provenance["identity"] = digest(provenance)
        return Preparation(result, provenance)
    except (KeyError, TypeError, ValueError, ArithmeticError, AttributeError, IndexError) as error:
        raise ConfigError(
            "Invalid static environment barrier preparation: " + str(error)
        ) from error


def replay(provenance):
    """Recompute all coefficients and owner checks from the complete JSON recipe."""
    try:
        raw = _json(provenance)
        identity = raw.pop("identity")
        if raw["kind"] != KIND or identity != digest(raw):
            raise ConfigError("Stale barrier preparation identity")
        result = prepare(raw["request"])
        if digest(result.provenance) != digest(provenance):
            raise ConfigError("Barrier preparation recipe or derived fields changed")
        return result
    except (KeyError, TypeError, ValueError, ArithmeticError, AttributeError) as error:
        raise ConfigError("Invalid complete barrier preparation: " + str(error)) from error


def write_preparation(directory, prepared):
    expected = replay(prepared.provenance)
    if digest(expected.definition) != digest(prepared.definition):
        raise ConfigError("Prepared definition disagrees with the barrier recipe")
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=False)
    for name, value in (
        ("definition.json", expected.definition),
        ("provenance.json", expected.provenance),
    ):
        (root / name).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    return root
