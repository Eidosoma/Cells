"""Explicit six-column owner bridge into the held component bootstrap.

The original boundary and six-column layout remain attached to every request
and result. A named midpoint/normal projection enters an unchanged supplied
owner handoff. Physical geometry and native initialization history stay open.
"""

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass, fields, is_dataclass, replace
from pathlib import Path

import numpy as np

from cells.processes import betse_native_membrane_layout as layout
from cells.processes import betse_normal_ecm_initialization as initial
from cells.processes import betse_normal_ion_join as ions

LAW_ID = "betse_native_membrane_explicit_component_initialization_v1_5_0@1"
DECLARATION_KIND = "cells.betse_native_membrane_initialization_declaration@1"
DEPENDENCY_PINS = (
    (
        "betse_native_membrane_layout",
        "e93597511e882b5c4dd046fec40e4df32d0eda438fb7cb21531e020b445bd6f1",
    ),
    (
        "betse_normal_ecm_initialization",
        "780ffb431383b1ba5b8f2e05d98d1159755cd5b5b6c2504aaf0f205838e896af",
    ),
    ("betse_normal_ion_join", "f41a79fd30efdf777cc12af9808427b26d30af4d902ad99fe9c48fb55d7ed56d"),
    (
        "betse_normal_ecm_field_join",
        "fa50436c824362e34422d7bdf233f7676a364256011476d34333982bfcd2ddad",
    ),
    (
        "betse_normal_ecm_calcium_join",
        "80ccf03ce5b758274930e94c89f3411531aed5eeef924f6b2334b3ab8e6ea184",
    ),
    ("betse_ecm_grn_source", "638e4e7130c5301c7c7f8ea5afda0a2f2b38f492ab05b79b5467eeb19d049c25"),
    ("betse_ecm_grn_join", "f73b54e367613b1cf6473c14fd0d1b9967e5d9a328aa2c2299e319850454b274"),
    ("betse_ecm_transport", "05c909a59a760c763a05e30e36dd2630ce5959262519b58fde9e19f121500541"),
)
GATE_NAMES = (
    "physical_geometry_admitted",
    "tangent_geometry_qualified",
    "native_seed_init_chain_established",
    "native_layout_qualification_inherited",
    "ordinary_ECM_loop_ready",
    "mechanics_admitted",
)


@dataclass(frozen=True)
class CapturedPair:
    boundary: initial.Boundary
    native_layout: layout.Snapshot
    observation: str
    identity: str


@dataclass(frozen=True)
class PreparedEntry:
    binding: object
    original: CapturedPair
    declaration: object
    six_column_layout: layout.Layout
    explicit_view: layout.ConsumerView
    projected_boundary: initial.Boundary
    readiness: object
    gates: object
    identity: str


@dataclass(frozen=True)
class ComponentEntry:
    request: PreparedEntry
    component_handoff: initial.Handoff
    provenance: object
    gates: object
    identity: str


class EntryRejected(ValueError):
    def __init__(self, reason, *, stage, original=None, partial=None):
        super().__init__("Native membrane initialization refused at " + stage + ": " + str(reason))
        self.stage, self.original, self.partial = stage, original, partial


def record(value):
    if isinstance(value, np.generic):
        return dict(numpy_scalar_dtype=value.dtype.str, raw_bytes_hex=value.tobytes().hex())
    if is_dataclass(value):
        return {field.name: record(getattr(value, field.name)) for field in fields(value)}
    if hasattr(value, "_asdict"):
        return {key: record(child) for key, child in value._asdict().items()}
    if isinstance(value, Mapping):
        return {key: record(child) for key, child in value.items()}
    if isinstance(value, (tuple, list)):
        return [record(child) for child in value]
    if type(value) is bytes:
        return dict(bytes_hex=value.hex())
    return value


def digest(value):
    return ions.digest(record(value))


def _verify_sources():
    modules = (
        layout,
        initial,
        ions,
        initial.field,
        initial.calcium,
        initial.source,
        initial.network,
        initial.material,
    )
    for (name, expected), module in zip(DEPENDENCY_PINS, modules, strict=True):
        if (
            module.__name__.rsplit(".", 1)[-1] != name
            or hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest() != expected
        ):
            raise ValueError("Changed frozen membrane-entry dependency: " + name)


def pair_record(value):
    return (LAW_ID, value.boundary, value.native_layout, value.observation)


def _notify(observer, name, value):
    if observer is not None:
        observer(name, value)


def capture_supplied(
    owners, network_cache, excluded, boundary_declaration, layout_declaration, *, observer=None
):
    partial = dict(boundary=None, native_layout=None)
    try:
        _verify_sources()
        _notify(
            observer,
            "capture-input",
            dict(
                owners=owners,
                network_cache=network_cache,
                excluded=excluded,
                boundary_declaration=boundary_declaration,
                layout_declaration=layout_declaration,
            ),
        )
        partial["boundary"] = initial.capture_supplied(
            owners, network_cache, excluded, boundary_declaration
        )
        _notify(observer, "captured-original-boundary", partial["boundary"])
        partial["native_layout"] = layout.capture_supplied(owners["cells"], layout_declaration)
        _notify(observer, "captured-original-layout", partial["native_layout"])
        result = CapturedPair(partial["boundary"], partial["native_layout"], "paired_supplied", "")
        return replace(result, identity=digest(pair_record(result)))
    except Exception as error:
        raise EntryRejected(
            error,
            stage="supplied_capture",
            original=partial.get("boundary"),
            partial=dict(partial, source=getattr(error, "partial", None)),
        ) from error


def capture_native(phase, boundary_declaration, layout_declaration, *, observer=None):
    partial = dict(boundary=None, native_layout=None)
    try:
        _verify_sources()
        _notify(
            observer,
            "native-capture-request",
            dict(
                boundary_declaration=boundary_declaration,
                layout_declaration=layout_declaration,
                construction_history_claimed=False,
            ),
        )
        partial["boundary"] = initial.capture_native(phase, boundary_declaration)
        _notify(observer, "captured-original-boundary", partial["boundary"])
        partial["native_layout"] = layout.capture_native(phase.cells, layout_declaration)
        _notify(observer, "captured-original-layout", partial["native_layout"])
        result = CapturedPair(
            partial["boundary"], partial["native_layout"], "paired_pinned_native", ""
        )
        return replace(result, identity=digest(pair_record(result)))
    except Exception as error:
        raise EntryRejected(
            error,
            stage="native_capture",
            original=partial.get("boundary"),
            partial=dict(partial, source=getattr(error, "partial", None)),
        ) from error


def _declaration(raw):
    if (
        not isinstance(raw, Mapping)
        or set(raw)
        != {
            "kind",
            "opted_in_law",
            "conversion_law",
            "component_policy",
            "geometry_policy",
            "stage",
        }
        or raw["kind"] != DECLARATION_KIND
        or raw["opted_in_law"] != LAW_ID
        or raw["conversion_law"] != layout.MIDPOINT_NORMAL_LAW
        or raw["component_policy"] != "held_single_component_bootstrap_no_ordinary_loop"
        or raw["geometry_policy"] != "retain_unqualified_six_column_parent"
        or raw["stage"] != initial.STAGE
    ):
        raise ValueError(
            "Declare the exact midpoint-normal bridge and unqualified component-only seam"
        )
    return ions.freeze(raw)


def _shared_stores(pair, bound):
    initial.validate_boundary(pair.boundary)
    if pair.identity != digest(pair_record(pair)):
        raise ValueError("Changed original paired boundary/layout capture")
    kinds = {
        "paired_supplied": ("supplied_owner_boundary", "supplied_owner_stores"),
        "paired_pinned_native": (
            "pinned_native_objects_at_declared_boundary",
            "pinned_native_Cells_stores",
        ),
    }
    if pair.observation not in kinds or kinds[pair.observation] != (
        pair.boundary.observation_kind,
        pair.native_layout.observation,
    ):
        raise ValueError("Mixed or changed native/supplied capture origins")
    for key in ("cell_i", "mem_i", "mem_to_cells", "mem_mids_flat", "mem_vects_flat"):
        value = initial._required(pair.boundary, "cells", key)
        retained = bound.snapshot.entries[key]["value"]
        if key in ("cell_i", "mem_i") and retained["kind"] != "array_indices":
            indices = layout._index_values(retained)
            actual = np.asarray(value)
            if (
                actual.dtype.kind not in "iu"
                or actual.shape != (len(indices),)
                or tuple(actual) != indices
            ):
                raise ValueError("Shared original index sequence differs: " + key)
            continue
        buffer = retained["buffer"] if key in ("cell_i", "mem_i") else retained
        actual = np.asarray(value)
        if (actual.dtype.str, actual.shape, actual.tobytes(order="C")) != (
            buffer.dtype,
            buffer.shape,
            buffer.raw,
        ):
            raise ValueError("Paired original owner stores differ in dtype/shape/bits: " + key)


def _project(pair, declaration):
    if type(pair) is not CapturedPair:
        raise ValueError("Require the complete paired original native stores")
    bound = layout.bind_layout(pair.native_layout)
    _shared_stores(pair, bound)
    view = layout.midpoint_normal_view(bound, opted_in_conversion=declaration["conversion_law"])
    layout.validate_view(view)
    buffer = view.values
    array = np.frombuffer(buffer.raw, dtype=np.dtype(buffer.dtype)).reshape(buffer.shape)
    owners = dict(pair.boundary.owners)
    cells = dict(owners["cells"])
    cells["mem_vects_flat"] = ions.freeze(dict(present=True, captured=True, value=array))
    owners["cells"] = ions.freeze(cells)
    boundary_declaration = dict(
        pair.boundary.declaration, geometry_classification="unqualified_native_layout"
    )
    source_objects = ions.freeze(
        dict(
            law=LAW_ID,
            original_observation=pair.boundary.observation_kind,
            original_source_objects=pair.boundary.source_objects,
            original_boundary_identity=pair.boundary.identity,
            original_pair_identity=pair.identity,
            native_layout_identity=pair.native_layout.identity,
            conversion_law=view.conversion_law,
            explicit_view_identity=view.identity,
            replaced_store="cells.mem_vects_flat",
            projected_capture_is_native=False,
        )
    )
    projected = replace(
        pair.boundary,
        declaration=ions.freeze(boundary_declaration),
        observation_kind="supplied_owner_boundary",
        owners=ions.freeze(owners),
        source_objects=source_objects,
        identity="",
    )
    projected = replace(projected, identity=ions.digest(initial.boundary_record(projected)))
    initial.validate_boundary(projected)
    return bound, view, projected


def request_record(value):
    return (
        LAW_ID,
        value.binding,
        value.original,
        value.declaration,
        value.six_column_layout,
        value.explicit_view,
        value.projected_boundary,
        value.readiness,
        value.gates,
    )


def prepare(binding, pair, declaration, *, observer=None):
    stage, partial = "declaration", {}
    try:
        _verify_sources()
        declared = _declaration(declaration)
        _notify(
            observer, "entry-request", dict(binding=binding, original=pair, declaration=declared)
        )
        stage = "explicit_projection"
        bound, view, projected = _project(pair, declared)
        partial.update(six_column_layout=bound, explicit_view=view, projected_boundary=projected)
        _notify(observer, "explicit-projection", partial.copy())
        stage = "common_owner_and_hot_cache_readiness"
        missing = initial.missing_stores(projected)
        partial["presence_inventory"] = missing
        _notify(observer, "owner-presence-inventory", missing)
        state, controls, cached = initial._check_owners(binding, projected)
        partial.update(common_state=state, controls=controls, hot_cache=cached)
        _notify(observer, "common-owner-readiness-return", partial.copy())
        readiness = ions.freeze(
            dict(
                common_owner_checks_complete=True,
                common_state_identity=state.identity,
                controls_digest=ions.digest(controls),
                hot_cache_digest=ions.digest(cached),
                presence_inventory=missing,
                native_cache_defaults_filled=False,
                optional_calcium_admission_pending=type(binding) is initial.calcium.Binding,
                serializer_roundtrip_pending=True,
                component_bootstrap_performed=False,
                tangent_columns_consumed=False,
            )
        )
        result = PreparedEntry(
            binding,
            pair,
            declared,
            bound,
            view,
            projected,
            readiness,
            ions.freeze(dict.fromkeys(GATE_NAMES, False)),
            "",
        )
        return replace(result, identity=digest(request_record(result)))
    except Exception as error:
        raise EntryRejected(
            error,
            stage=stage,
            original=dict(binding=binding, pair=pair, declaration=declaration),
            partial=dict(partial, source=getattr(error, "partial", None)),
        ) from error


def _validate_request(request):
    _verify_sources()
    if type(request) is not PreparedEntry or request.identity != digest(request_record(request)):
        raise ValueError("Changed or unsealed component entry request")
    rebuilt = prepare(request.binding, request.original, request.declaration)
    if digest(request_record(rebuilt)) != digest(request_record(request)):
        raise ValueError("Resealed request changes original projection, readiness or closed gates")


def entry_record(value):
    return (LAW_ID, value.request, value.component_handoff, value.provenance, value.gates)


def bootstrap_component(request, *, observer=None, before_field=None):
    partial = dict(component_handoff=None, field_requests=[])
    stage = "request_authentication"
    try:
        _validate_request(request)
        _notify(observer, "before-held-component-handoff", request)

        def field_observer(raw):
            partial["field_requests"].append(raw)
            _notify(observer, "before-component-field", raw)
            if before_field is not None:
                before_field(raw)

        stage = "held_component_handoff"
        result = initial.handoff(
            request.binding, request.projected_boundary, before_field=field_observer
        )
        partial["component_handoff"] = result
        _notify(observer, "held-component-handoff-return", result)
        stage = "component_receipt"
        if (
            len(partial["field_requests"]) != 1
            or result.boundary_identity != request.projected_boundary.identity
            or result.binding_identity != request.binding.identity
            or result.provenance["bootstrap_calls"] != 1
            or result.provenance["cold_owner_calls"] != 0
            or result.provenance["native_init_dynamics_calls"] != 0
            or result.provenance["native_seed_init_load_chain_established"] is not False
            or result.provenance["geometry_classification"] != "unqualified_native_layout"
        ):
            raise ValueError("The existing component bootstrap crossed its declared scope")
        cache = result.parent.network.network_cache
        if ions.digest(cache) != ions.digest(request.original.boundary.network_cache["value"]):
            raise ValueError("Component bootstrap changed the retained hot GRN cache")
        provenance = ions.freeze(
            dict(
                law=LAW_ID,
                original_boundary_identity=request.original.boundary.identity,
                original_native_layout_identity=request.original.native_layout.identity,
                original_pair_identity=request.original.identity,
                conversion_law=request.explicit_view.conversion_law,
                explicit_view_identity=request.explicit_view.identity,
                projected_boundary_identity=request.projected_boundary.identity,
                component_handoff_identity=result.identity,
                component_bootstrap_calls=1,
                original_hot_cache_digest=ions.digest(cache),
                native_bootstrap_executed=False,
                native_seed_init_chain_established=False,
                full_six_column_parent_retained=True,
                tangent_columns_geometry_qualified=False,
            )
        )
        entry = ComponentEntry(
            request, result, provenance, ions.freeze(dict.fromkeys(GATE_NAMES, False)), ""
        )
        return replace(entry, identity=digest(entry_record(entry)))
    except Exception as error:
        raise EntryRejected(
            error,
            stage=stage,
            original=request,
            partial=dict(
                partial,
                source=getattr(error, "partial", None),
                rejected_boundary=getattr(error, "boundary", None),
            ),
        ) from error


def require_ordinary_loop(entry):
    raise EntryRejected(
        "The explicit component bridge does not establish physical geometry, "
        "tangent qualification or the native seed/init/load chain",
        stage="ordinary_loop_admission",
        original=entry,
    )
