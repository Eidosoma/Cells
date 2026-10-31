"""Later SIM event-owner publication from retained typed source authorities.

The early event_finalized observation keeps its original epoch and payload.
Missing configuration/default/boundary authority requires explicit typed input;
no physical IDs, reservoirs, profile choices or callback outputs are invented.
Publication is source transport, not setup admission or native persistence.
Supplied seams remain conditional inputs. Frozen typed records establish neither
original native derivation nor biological qualification.
"""

import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass, fields, replace
from types import MappingProxyType

import numpy as np

from cells.processes import betse_mechanics_join as mechanics
from cells.processes import betse_normal_ion_join as ions

KIND = "cells.actual_SIM_event_owner_publication@1"
EPOCH = "after_source_setup_before_SIM_phase_binding"
OWNER_KIND = "cells.supplied_finalized_native_tissue_event_owner@1"
OWNER_KEYS = {
    "kind",
    "provenance",
    "geometry_declaration_sha256",
    "owners",
    "handler_fields",
    "tissue_default",
    "tissue_target_inds",
    "cell_target_inds",
    "env_target_inds",
    "global_options",
    "scheduled_options",
    "configured_environment",
    "callbacks",
    "voltage",
    "event_cut",
}
ROLES = ("Na", "K", "Cl", "Ca", "M", "P")
SUPPLIED_AUTHORITY = (
    "conditional/supplied seam; native derivation and biological qualification "
    "unestablished by typed record"
)


@dataclass(frozen=True)
class Inputs:
    """Caller-supplied conditional data; construction performs no admission."""

    source_INIT_binding_identity: str
    source_geometry_binding_identity: str
    default_tissue_profile: str
    configured_environment: object
    boundary_cell_occurrences: tuple
    voltage: object
    event_cut: object
    provenance: str


@dataclass(frozen=True)
class Publication:
    """Immutable publication data; decoding performs no source/validation replay."""

    inputs: Inputs
    source_binding_identity: str
    source_INIT_binding_identity: str
    source_INIT_parent_identity: str
    source_complete_INIT_identity: str
    source_SIM_declaration_identity: str
    phase_inputs_identity: str
    event_finalized: object
    event_finalized_identity: str
    owner: object
    field_sources: object
    epoch: str
    identity: str


def require(condition, message):
    if not condition:
        raise ValueError(message)


def same(left, right):
    """Typed data correspondence; occurrence/array order remains significant."""
    if isinstance(left, Mapping) or isinstance(right, Mapping):
        return (
            isinstance(left, Mapping)
            and isinstance(right, Mapping)
            and set(left) == set(right)
            and all(same(left[k], right[k]) for k in left)
        )
    if isinstance(left, (np.ndarray, np.generic)) or isinstance(right, (np.ndarray, np.generic)):
        return (
            type(left) is type(right)
            and left.dtype == right.dtype
            and left.shape == right.shape
            and np.array_equal(left, right)
        )
    if isinstance(left, (list, tuple)) or isinstance(right, (list, tuple)):
        return (
            isinstance(left, (list, tuple))
            and isinstance(right, (list, tuple))
            and len(left) == len(right)
            and all(same(a, b) for a, b in zip(left, right, strict=True))
        )
    return type(left) is type(right) and left == right


def document_hash(value):
    return hashlib.sha256(
        json.dumps(
            ions.data(value), sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def check_inputs(value, *, expected_INIT=None):
    require(
        type(value) is Inputs, "Require explicit typed SIM event-owner inputs; no fixture hydration"
    )
    for name in (
        "source_INIT_binding_identity",
        "source_geometry_binding_identity",
        "default_tissue_profile",
        "provenance",
    ):
        require(
            type(getattr(value, name)) is str and bool(getattr(value, name).strip()),
            "Missing explicit event-owner authority: " + name,
        )
    require(
        expected_INIT is None or value.source_INIT_binding_identity == expected_INIT,
        "Foreign event-owner source INIT binding",
    )
    require(
        type(value.configured_environment) is MappingProxyType and value.configured_environment,
        "Require immutable explicitly configured reservoirs, never warm boundary inference",
    )
    for key, number in value.configured_environment.items():
        require(
            type(key) is str
            and bool(key)
            and not isinstance(number, (bool, np.bool_))
            and isinstance(number, (int, float, np.integer, np.floating))
            and math.isfinite(number),
            "Require finite scalar configured reservoirs without axis repair",
        )
    require(
        type(value.boundary_cell_occurrences) is tuple
        and all(type(key) is str and bool(key) for key in value.boundary_cell_occurrences),
        "Require explicit ordered boundary cell occurrences",
    )
    require(
        value.voltage is None and value.event_cut is None,
        "Voltage/cutting remain outside the deterministic event-owner bridge",
    )
    return value


def record(value):
    return (
        KIND,
        *(getattr(value, field.name) for field in fields(Publication) if field.name != "identity"),
    )


def field_sources(early):
    result = {key: "unchanged actual event_finalized.owner." + key for key in early["owner"]}
    result.update(
        kind="closed Cells event-owner schema",
        provenance=SUPPLIED_AUTHORITY + "; typed Inputs.provenance",
        geometry_declaration_sha256="actual post-setup phase field/geometry declaration",
        owners="retained typed current/ECM/mechanics axes; boundary occurrences: "
        + SUPPLIED_AUTHORITY,
        tissue_default="actual finalized profile fields; explicit default-profile role: "
        + SUPPLIED_AUTHORITY,
        configured_environment=SUPPLIED_AUTHORITY
        + "; typed configured reservoirs; no warm-state inference",
        voltage=SUPPLIED_AUTHORITY + "; typed Inputs.voltage verifies disabled scope only",
        event_cut=SUPPLIED_AUTHORITY + "; typed Inputs.event_cut verifies disabled scope only",
    )
    return result


def _axes(completed, mechanical):
    from cells.processes import betse_normal_ecm_molecule_lifecycle_phase as phase

    require(
        type(completed.binding) is phase.Binding and type(mechanical) is mechanics.Binding,
        "Require actual retained typed phase/mechanics authorities",
    )
    gb = completed.binding.material_binding.geometry_binding
    cb, grid = gb.current_binding, gb.geometry
    geometry = mechanical.definition["geometry"]
    cells, membranes, environment = (
        tuple(cb.cell_ids),
        tuple(cb.membrane_ids),
        tuple(geometry["environment_ids"]),
    )
    require(
        same(cells, geometry["cell_ids"]) and same(membranes, geometry["layout"]["membrane_ids"]),
        "Foreign typed mechanics cell/membrane axes",
    )
    require(
        len(environment) == len(grid.grid_points_m)
        and len(set(environment)) == len(environment)
        and all(type(key) is str and bool(key) for key in environment),
        "Missing complete typed mechanics/grid owner IDs; no generated IDs",
    )

    def indices_equal(left, right):
        left, right = np.asarray(left), np.asarray(right)
        return (
            left.ndim == right.ndim == 1
            and left.dtype.kind in "iu"
            and right.dtype.kind in "iu"
            and left.shape == right.shape
            and np.array_equal(left, right)
        )

    require(
        indices_equal(geometry["cell_to_environment"], grid.cell_to_grid)
        and indices_equal(geometry["membrane_to_environment"], grid.membrane_to_grid),
        "Foreign typed mechanics/environment mapping",
    )

    def gather(ids, indices):
        require(len(indices) == len(membranes), "Incomplete membrane ownership mapping")
        require(
            all(
                not isinstance(i, (bool, np.bool_))
                and isinstance(i, (int, np.integer))
                and 0 <= i < len(ids)
                for i in indices
            ),
            "Foreign membrane ownership index",
        )
        return [ids[i] for i in indices]

    return gb, dict(
        cell_ids=list(cells),
        membrane_ids=list(membranes),
        environment_ids=list(environment),
        membrane_cell_ids=gather(cells, cb.kernel.owner),
        membrane_environment_ids=gather(environment, grid.membrane_to_grid),
    )


def publish(
    source_binding, completed, event_finalized, final_phase_inputs, mechanical, actual_profiles
):
    """Called only after actual source setup; this routine executes no finalizer."""
    from cells.processes import betse_normal_ecm_molecule_lifecycle as lifecycle

    require(
        type(source_binding) is lifecycle.Binding and type(completed) is lifecycle.CompleteInit,
        "Require exact retained lifecycle/complete-INIT owners",
    )
    supplied = check_inputs(
        source_binding.event_owner_inputs, expected_INIT=source_binding.expected_init_identity
    )
    require(
        completed.binding.identity == supplied.source_INIT_binding_identity,
        "Foreign complete INIT source for event-owner publication",
    )
    gb, axes = _axes(completed, mechanical)
    require(
        gb.identity == supplied.source_geometry_binding_identity,
        "Foreign retained geometry authority",
    )
    require(
        set(supplied.configured_environment) == set(gb.current_binding.ion_ids),
        "Configured reservoirs must name every actual ion",
    )
    require(
        all(key in axes["cell_ids"] for key in supplied.boundary_cell_occurrences),
        "Boundary occurrences name foreign cell owners",
    )
    axes["boundary_cell_occurrences"] = list(supplied.boundary_cell_occurrences)
    require(
        event_finalized["source_phase"] == "SIM"
        and event_finalized["legacy_run_sim"] is True
        and type(event_finalized["event_fire_calls"]) is int
        and event_finalized["event_fire_calls"] == 0,
        "Require the unchanged actual zero-fire SIM finalization epoch",
    )
    cfg = source_binding.inputs["source_setup"]
    profiles = actual_profiles.tissue_name_to_profile
    require(
        list(profiles) == [row["name"] for row in cfg["tissue_profiles"]],
        "Changed actual source profile order",
    )
    require(
        supplied.default_tissue_profile in profiles,
        "Missing explicitly selected actual default profile; no default generation",
    )
    row = next(
        row for row in cfg["tissue_profiles"] if row["name"] == supplied.default_tissue_profile
    )
    profile = profiles[supplied.default_tissue_profile]
    defaults = {"Dm_" + role: getattr(profile, "Dm_" + role) for role in ROLES}
    require(
        same(defaults, row["diffusion_m2_s"]),
        "Actual default profile differs from retained configuration",
    )
    owner = ions.data(event_finalized["owner"])
    maps = ("tissue_target_inds", "cell_target_inds", "env_target_inds")
    require(
        set(owner[maps[0]]) == set(owner[maps[1]]) == set(owner[maps[2]]),
        "Missing actual finalized profile map; no profile hydration",
    )
    original_setup = source_binding.inputs["sim_phase"]["setup"]
    for key in ("global_options", "scheduled_options"):
        require(
            same(owner[key], original_setup[key]),
            "Changed actual finalizer/config association: " + key,
        )
    external = final_phase_inputs["field"]["definition"]["environment_geometry_definition"]
    original_external = source_binding.inputs["sim_phase"]["field"]["definition"][
        "environment_geometry_definition"
    ]
    for before, after in (
        (original_external["geometry"], external["geometry"]),
        (original_external["world"], external["world"]),
        (
            original_external["current_definition"]["geometry"],
            external["current_definition"]["geometry"],
        ),
        (original_external["current_definition"]["ions"], external["current_definition"]["ions"]),
    ):
        require(
            same(before, after), "Publication may not replace retained geometry/world/ion owners"
        )
    owner.update(
        kind=OWNER_KIND,
        provenance=supplied.provenance,
        geometry_declaration_sha256=document_hash(external),
        owners=axes,
        tissue_default=defaults,
        configured_environment=ions.data(supplied.configured_environment),
        voltage=supplied.voltage,
        event_cut=supplied.event_cut,
    )
    require(set(owner) == OWNER_KEYS, "Incomplete actual event-owner publication")
    value = Publication(
        supplied,
        source_binding.identity,
        completed.binding.identity,
        completed.parent.identity,
        completed.identity,
        source_binding.declaration.identity,
        ions.digest(final_phase_inputs),
        event_finalized,
        ions.digest(event_finalized),
        ions.freeze(owner),
        ions.freeze(field_sources(event_finalized)),
        EPOCH,
        "",
    )
    return replace(value, identity=ions.digest(record(value)))


def _same_publication_data(left, right):
    """Compare record/container/scalar types as well as complete retained data."""
    kind = type(left)
    if kind is not type(right):
        return False
    if left is right:
        return True
    if kind in (Publication, Inputs):
        return all(
            _same_publication_data(getattr(left, field.name), getattr(right, field.name))
            for field in fields(kind)
        )
    if isinstance(left, Mapping):
        return set(left) == set(right) and all(
            _same_publication_data(left[key], right[key]) for key in left
        )
    if kind in (tuple, list):
        return len(left) == len(right) and all(
            _same_publication_data(a, b) for a, b in zip(left, right, strict=True)
        )
    return same(left, right)


def resolve(source_binding, source_entry):
    """Check exact setup/config/callback/phase association without setup replay."""
    from cells.processes import betse_normal_ecm_molecule_lifecycle as lifecycle
    from cells.processes import betse_normal_ecm_molecule_lifecycle_phase as phase

    require(
        type(source_binding) is lifecycle.Binding
        and type(source_entry) is lifecycle.SimPhase
        and type(source_entry.phase_binding) is phase.Binding,
        "Require typed lifecycle/SIM owners for event publication",
    )
    binding, completed = source_entry.phase_binding, source_entry.source_init
    supplied = check_inputs(
        source_binding.event_owner_inputs, expected_INIT=source_binding.expected_init_identity
    )
    require(
        type(completed) is lifecycle.CompleteInit
        and source_entry.binding_identity == source_binding.identity,
        "Foreign actual INIT/SIM association for event publication",
    )
    receipt = binding.setup_receipt
    finalization = receipt["event_finalization"]
    published = finalization.get("owner_publication")
    require(
        type(published) is Publication,
        "Missing actual later event-owner publication; legacy receipts cannot supply it",
    )
    require(
        published.identity == ions.digest(record(published)) and published.epoch == EPOCH,
        "Changed later event-owner publication identity/epoch",
    )
    require(
        type(published.inputs) is Inputs and same(ions.data(published.inputs), ions.data(supplied)),
        "Foreign typed event-owner inputs",
    )
    require(
        published.source_binding_identity == source_binding.identity
        and completed.binding.identity == supplied.source_INIT_binding_identity
        and published.source_INIT_binding_identity == completed.binding.identity
        and published.source_INIT_parent_identity == completed.parent.identity
        and published.source_complete_INIT_identity == completed.identity
        and published.source_SIM_declaration_identity == source_binding.declaration.identity
        and receipt["source_init_identity"] == completed.identity
        and published.phase_inputs_identity == ions.digest(binding.inputs_raw)
        and binding.calendar.phase == "SIM"
        and receipt["source_phase"] == "SIM"
        and receipt["legacy_run_sim"] is True,
        "Foreign setup/config/INIT/SIM parent in event-owner publication",
    )
    early = finalization["source_fields"]
    require(
        early["source_phase"] == "SIM"
        and early["legacy_run_sim"] is True
        and type(early["event_fire_calls"]) is int
        and early["event_fire_calls"] == 0,
        "Changed original zero-fire SIM finalization epoch/phase",
    )
    original_setup = source_binding.inputs["sim_phase"]["setup"]
    for key in ("global_options", "scheduled_options"):
        require(
            same(early["owner"][key], original_setup[key]),
            "Changed early finalizer/source configuration association: " + key,
        )
    require(
        published.event_finalized_identity == ions.digest(early)
        and same(published.event_finalized, early)
        and same(receipt["source_setup"]["event_finalized"], early),
        "Early event_finalized observation/epoch was replaced",
    )
    secondary = receipt["source_setup"].get("event_owner_published")
    require(
        type(secondary) is Publication
        and secondary.identity == ions.digest(record(secondary))
        and secondary.epoch == EPOCH
        and secondary.identity == published.identity
        and _same_publication_data(secondary, published),
        "Missing or foreign later source publication observation",
    )
    owner = published.owner
    require(
        set(owner) == OWNER_KEYS and same(published.field_sources, field_sources(early)),
        "Incomplete later owner or field-source correspondence",
    )
    for key, value in early["owner"].items():
        require(same(owner[key], value), "Changed early finalizer field in later owner: " + key)
    require(
        owner["kind"] == OWNER_KIND
        and owner["provenance"] == supplied.provenance
        and owner["voltage"] is None
        and owner["event_cut"] is None
        and same(owner["configured_environment"], supplied.configured_environment)
        and same(owner["owners"]["boundary_cell_occurrences"], supplied.boundary_cell_occurrences)
        and owner["geometry_declaration_sha256"]
        == document_hash(binding.inputs["definition"]["environment_geometry_definition"]),
        "Changed configured/default/geometry owner publication",
    )
    gb, axes = _axes(completed, binding.mechanics)
    require(
        gb.identity == supplied.source_geometry_binding_identity
        and set(supplied.configured_environment) == set(gb.current_binding.ion_ids),
        "Foreign retained geometry/reservoir axis in publication",
    )
    axes["boundary_cell_occurrences"] = list(supplied.boundary_cell_occurrences)
    require(same(owner["owners"], axes), "Changed actual cell/membrane/grid owner correspondence")
    profiles = source_binding.inputs["source_setup"]["tissue_profiles"]
    selected = [row for row in profiles if row["name"] == supplied.default_tissue_profile]
    require(
        len(selected) == 1 and same(owner["tissue_default"], selected[0]["diffusion_m2_s"]),
        "Changed explicit default-profile correspondence",
    )
    for row in profiles:
        name = row["name"]
        require(
            same(owner["tissue_target_inds"].get(name), row["membrane_indices"])
            and same(owner["cell_target_inds"].get(name), row["cell_indices"]),
            "Changed actual finalized profile targets: " + name,
        )
        expected = [gb.geometry.membrane_to_grid[i] for i in row["membrane_indices"]]
        actual = owner["env_target_inds"].get(name)
        require(
            actual is not None
            and len(actual) == len(expected)
            and all(
                isinstance(i, (int, np.integer)) and not isinstance(i, (bool, np.bool_)) and i == j
                for i, j in zip(actual, expected, strict=True)
            ),
            "Changed actual finalized profile/grid correspondence: " + name,
        )
    return published
