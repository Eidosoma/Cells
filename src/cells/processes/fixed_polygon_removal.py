"""Supplied fixed-polygon cell removal; geometry and owner lineage only.

Remove whole physical cell groups. Coordinates and extracellular volumes remain
parent-owned. Newly exposed half-membranes require explicit existing-bath IDs.
No material state, native DEC epoch, or ordinary checkpoint is admitted here.
"""

import hashlib
import json
import struct
from dataclasses import dataclass, fields
from pathlib import Path

from cells.processes import conservative_polygon_geometry as geometry

LAW_ID = "cells_fixed_polygon_removal_rebuild@1"
REQUEST_KIND = "cells.fixed_polygon_removal_request@1"
RESULT_KIND = "cells.fixed_polygon_removal_binding@1"
GEOMETRY_SHA256 = "5d267b20cdb3a05f4f036bbc3fa6978b40780ca4394f67ac6c33a8b605af4b0d"
ARITHMETIC_SHA256 = "c9fab4f34aa9166711431844f2af72eb6b8fe4873154bfe01dfce3f656326958"
NATIVE_INVALIDATED_OWNERS = (
    "DEC_mesh_and_operators",
    "cell_membrane_geometry_and_measures",
    "environment_maps_volumes_and_operators",
    "cell_graph_and_gap_junctions",
    "source_diffusion_and_wound_TJ",
    "tissue_profile_and_callback_epochs",
    "RNG_and_schedule_epochs",
    "molecule_transporter_channel_reinitialization",
    "current_voltage_and_initializer_caches",
    "material_and_voltage_component_bindings",
    "complete_post_cut_checkpoint",
)
AXES = {
    "source_cell": "source_cells",
    "cell": "cells",
    "vertex": "vertices",
    "edge": "edges",
    "membrane": "membranes",
    "contact": "contacts",
    "bath": "baths",
}


class RemovalRejected(ValueError):
    def __init__(self, code, *, stage, detail=None, trial=None):
        super().__init__(code + " at " + stage)
        self.code, self.stage, self.detail, self.trial = code, stage, detail, trial


@dataclass(frozen=True, slots=True)
class Request:
    parent_request: geometry.Request
    parent_binding: geometry.Binding
    declaration_json: str
    identity: str

    @property
    def declaration(self):
        return json.loads(self.declaration_json)


@dataclass(frozen=True, slots=True)
class Binding:
    request_identity: str
    report_json: str
    child_request: geometry.Request | None
    child_binding: geometry.Binding | None
    identity: str

    @property
    def report(self):
        return json.loads(self.report_json)


def _json(value):
    text = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    if len(text.encode()) > 64 * 2**20:
        raise RemovalRejected("metadata_size", stage="representation")
    return text


def _digest(value):
    return hashlib.sha256(_json(value).encode()).hexdigest()


def capture(value, _active=None):
    """Full typed evidence for the bounded JSON/record input contract.

    Store binary64 bits even for invalid nonfinite inputs. Non-contract objects
    are identified by type/repr and are never interpreted as geometry owners.
    """
    active = set() if _active is None else _active
    kind = type(value)
    if kind in (str, int, bool) or value is None:
        return value
    if kind is float:
        return dict(kind="binary64", bits_be=struct.pack(">d", value).hex())
    if kind is bytes:
        return dict(kind="bytes", hex=value.hex())
    if id(value) in active:
        return dict(kind="cycle", type=kind.__module__ + "." + kind.__qualname__)
    active.add(id(value))
    try:
        if kind in (tuple, list):
            return dict(kind=kind.__name__, values=[capture(v, active) for v in value])
        if kind is dict:
            return dict(
                kind="dict",
                items=[[capture(k, active), capture(v, active)] for k, v in value.items()],
            )
        if kind in (geometry.Request, geometry.Binding, Request, Binding):
            return dict(
                kind=kind.__module__ + "." + kind.__qualname__,
                fields={f.name: capture(getattr(value, f.name), active) for f in fields(value)},
            )
        return dict(
            kind="unsupported_object",
            type=kind.__module__ + "." + kind.__qualname__,
            representation=repr(value),
        )
    finally:
        active.remove(id(value))


def _retained(error, trial, stage):
    trial["failure"] = dict(
        type=type(error).__module__ + "." + type(error).__qualname__,
        message=str(error),
        code=getattr(error, "code", None),
        stage=getattr(error, "stage", stage),
        dependency_trial=capture(getattr(error, "trial", None)),
    )
    if isinstance(error, RemovalRejected):
        error.trial = trial
        return error
    return RemovalRejected(
        "dependency_or_representation_refusal", stage=stage, detail=trial["failure"], trial=trial
    )


def _dependencies():
    for module, expected in ((geometry, GEOMETRY_SHA256), (geometry.arithmetic, ARITHMETIC_SHA256)):
        if hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest() != expected:
            raise RemovalRejected(
                "changed_qualified_dependency", stage="provenance", detail=module.__name__
            )


def _id(value):
    if (
        type(value) is not str
        or not 1 <= len(value) <= 128
        or any(ord(c) < 33 or ord(c) > 126 for c in value)
    ):
        raise RemovalRejected("stable_id", stage="input")
    return value


def _normalise(raw):
    if type(raw) is not dict or set(raw) != {"removed_cell_ids", "exposed_baths"}:
        raise RemovalRejected("declaration_fields", stage="input")
    selected, exposed = raw["removed_cell_ids"], raw["exposed_baths"]
    if (
        type(selected) is not list
        or len(selected) > geometry.MAX_SOURCE_CELLS
        or type(exposed) is not list
        or len(exposed) > geometry.MAX_HALF_EDGES
    ):
        raise RemovalRejected("declaration_axes", stage="input")
    for name in selected:
        _id(name)
    if len(set(selected)) != len(selected):
        raise RemovalRejected("duplicate_selected_cell", stage="input")
    seen = set()
    for row in exposed:
        if type(row) is not dict or set(row) != {"membrane_id", "bath_id"}:
            raise RemovalRejected("exposed_bath_fields", stage="input")
        _id(row["membrane_id"])
        _id(row["bath_id"])
        if row["membrane_id"] in seen:
            raise RemovalRejected("duplicate_exposed_membrane", stage="input")
        seen.add(row["membrane_id"])
    return json.loads(_json(raw))


def _parent_record(request, binding):
    return dict(
        request_identity=request.identity,
        declaration_json=request.declaration_json,
        binding_identity=binding.identity,
        binding_request_identity=binding.request_identity,
        geometry_json=binding.geometry_json,
    )


def _request_payload(parent_request, parent_binding, declaration):
    return dict(
        kind=REQUEST_KIND,
        law=LAW_ID,
        parent=_parent_record(parent_request, parent_binding),
        declaration=declaration,
    )


def from_parent(parent_request, parent_binding, raw, *, law_id):
    trial = dict(
        stage="request",
        parent_request=capture(parent_request),
        parent_binding=capture(parent_binding),
        supplied_removal=capture(raw),
        opted_in_law=capture(law_id),
    )
    try:
        if type(law_id) is not str or law_id != LAW_ID:
            raise RemovalRejected("explicit_opt_in", stage="input")
        _dependencies()
        if (
            type(parent_request) is not geometry.Request
            or type(parent_binding) is not geometry.Binding
        ):
            raise RemovalRejected("parent_owner_types", stage="provenance")
        if parent_request.upstream or parent_request.declaration["source"]["kind"] != (
            "declared_polygon_complex@1"
        ):
            raise RemovalRejected("supplied_declared_parent_required", stage="provenance")
        geometry.validate_binding(parent_request, parent_binding)
        declaration = _normalise(raw)
        identity = _digest(_request_payload(parent_request, parent_binding, declaration))
        return Request(parent_request, parent_binding, _json(declaration), identity)
    except Exception as error:
        retained = _retained(error, trial, "request")
        if retained is error:
            raise
        raise retained from error


def request_record(request):
    return _request_payload(request.parent_request, request.parent_binding, request.declaration)


def validate_request(request):
    trial = dict(stage="request_identity", supplied_request=capture(request))
    try:
        if type(request) is not Request or type(request.declaration_json) is not str:
            raise RemovalRejected("request_ownership", stage="identity")
        expected = from_parent(
            request.parent_request, request.parent_binding, request.declaration, law_id=LAW_ID
        )
        if (
            expected.identity != request.identity
            or expected.declaration_json != request.declaration_json
        ):
            raise RemovalRejected("changed_request", stage="identity")
        return request
    except Exception as error:
        retained = _retained(error, trial, "request_identity")
        if retained is error:
            raise
        raise retained from error


def _selection(before, declaration):
    selected = set(declaration["removed_cell_ids"])
    ids = {row["id"] for row in before["cells"]}
    if not selected <= ids:
        raise RemovalRejected(
            "unknown_selected_cell", stage="selection", detail=sorted(selected - ids)
        )
    membranes = {row["id"]: row for row in before["membranes"]}
    exposed = []
    for contact in before["contacts"]:
        removed = [name for name in (contact["sender"], contact["receiver"]) if name in selected]
        if len(removed) == 1:
            kept = [
                membranes[name]
                for name in contact["membrane_ids"]
                if membranes[name]["cell_id"] not in selected
            ]
            if len(kept) != 1:
                raise RemovalRejected("parent_contact_ownership", stage="selection")
            membrane = kept[0]
            exposed.append(
                dict(
                    membrane_id=membrane["id"],
                    edge_id=membrane["edge_id"],
                    previous_contact_id=contact["id"],
                    removed_cell_id=removed[0],
                    surviving_cell_id=membrane["cell_id"],
                    previous_bath_id=membrane["bath_id"],
                )
            )
    supplied = {row["membrane_id"]: row["bath_id"] for row in declaration["exposed_baths"]}
    if set(supplied) != {row["membrane_id"] for row in exposed}:
        raise RemovalRejected(
            "exact_exposed_bath_ownership_required",
            stage="selection",
            detail=dict(expected=[r["membrane_id"] for r in exposed], supplied=list(supplied)),
        )
    bath_ids = {row["id"] for row in before["baths"]}
    for row in exposed:
        row["bath_id"] = supplied[row["membrane_id"]]
        if row["bath_id"] not in bath_ids:
            raise RemovalRejected("unknown_exposed_bath", stage="selection", detail=row)
    return selected, exposed


def _child_declaration(request, before, selected, exposed):
    raw = request.parent_request.declaration
    groups = [row for row in raw["cell_groups"] if row["id"] not in selected]
    source_ids = {name for row in groups for name in row["source_cell_ids"]}
    source_cells = [row for row in raw["source_cells"] if row["id"] in source_ids]
    vertex_ids = {name for row in source_cells for name in row["vertex_ids"]}
    exposed_by_edge = {row["edge_id"]: row["bath_id"] for row in exposed}
    assignments = [
        dict(vertex_ids=row["vertex_ids"], bath_id=exposed_by_edge.get(row["id"], row["bath_id"]))
        for row in before["edges"]
        if any(c not in selected for c in row["cell_ids"])
    ]
    return dict(
        source=dict(
            kind="declared_polygon_complex@1",
            generator="cells.fixed_polygon_removal@1",
            recipe=dict(
                parent_request_identity=request.parent_request.identity,
                parent_geometry_identity=request.parent_binding.identity,
                removal_request_identity=request.identity,
                coordinate_authority="unchanged_survivor_source_polygons@1",
            ),
            generation_coverage=False,
        ),
        vertices=[row for row in raw["vertices"] if row["id"] in vertex_ids],
        source_cells=source_cells,
        cell_groups=groups,
        baths=raw["baths"],
        bath_assignment=dict(kind="explicit_edge_baths@1", rows=assignments),
        height_m=raw["height_m"],
        thickness_m=raw["thickness_m"],
        axial_caps=raw["axial_caps"],
        units=raw["units"],
    )


def _lineage(before, after):
    result = {}
    for domain, key in AXES.items():
        old = before[key]
        new = after[key] if after is not None else before[key] if domain == "bath" else []
        old_axis, new_axis = [r["id"] for r in old], [r["id"] for r in new]
        old_index, new_index = (
            {name: i for i, name in enumerate(axis)} for axis in (old_axis, new_axis)
        )
        if not set(new_axis) <= set(old_axis):
            raise RemovalRejected("new_owner_in_fixed_removal", stage="lineage", detail=domain)
        result[domain] = dict(
            before_ids=old_axis,
            after_ids=new_axis,
            old_to_new=[new_index.get(name, -1) for name in old_axis],
            new_to_old=[old_index[name] for name in new_axis],
            removed_records=[r for r in old if r["id"] not in new_index],
            changed_records=[
                dict(before=old[old_index[r["id"]]], after=r)
                for r in new
                if old[old_index[r["id"]]] != r
            ],
        )
    return result


def _unchanged_survivors(before, after, axes):
    if after is None:
        return
    permitted = {
        "membrane": {"bath_id", "partner_id"},
        "edge": {"cell_ids", "membrane_ids", "bath_id"},
    }
    for domain, axis in axes.items():
        skip = permitted.get(domain, set())
        for row in axis["changed_records"]:
            old, new = row["before"], row["after"]
            if {k: v for k, v in old.items() if k not in skip} != {
                k: v for k, v in new.items() if k not in skip
            }:
                raise RemovalRejected(
                    "survivor_geometry_or_identity_changed",
                    stage="lineage",
                    detail=dict(domain=domain, before=old, after=new),
                )
    for key in ("height_m", "thickness_m", "units", "axial_caps", "baths"):
        if before[key] != after[key]:
            raise RemovalRejected("parent_measure_policy_changed", stage="lineage", detail=key)


def _binding_record(binding):
    return dict(
        request_identity=binding.request_identity,
        report_json=binding.report_json,
        child=None
        if binding.child_request is None
        else dict(
            request=geometry.request_record(binding.child_request),
            request_identity=binding.child_request.identity,
            geometry=binding.child_binding.geometry,
            binding_identity=binding.child_binding.identity,
            binding_request_identity=binding.child_binding.request_identity,
        ),
    )


def prepare(request):
    trial = dict(
        stage="rebuild",
        supplied_request=capture(request),
        child_declaration=None,
        returned_child_request=None,
        returned_child_binding=None,
    )
    try:
        validate_request(request)
        before = request.parent_binding.geometry
        declaration = request.declaration
        selected, exposed = _selection(before, declaration)
        trial["exposed_faces"] = exposed
        child_request = child_binding = None
        if not selected:
            child_request, child_binding = request.parent_request, request.parent_binding
            status = "empty_selection_identical_parent"
        elif len(selected) == len(before["cells"]):
            status = "all_cells_removed_no_child_geometry"
        else:
            raw = _child_declaration(request, before, selected, exposed)
            trial["child_declaration"] = capture(raw)
            child_request = geometry.from_polygons(raw, law_id=geometry.LAW_ID)
            trial["returned_child_request"] = capture(child_request)
            child_binding = geometry.prepare(child_request)
            trial["returned_child_binding"] = capture(child_binding)
            status = "survivor_geometry_rebuilt_unqualified"
        after = None if child_binding is None else child_binding.geometry
        axes = _lineage(before, after)
        trial["lineage"] = axes
        _unchanged_survivors(before, after, axes)
        groups = request.parent_request.declaration["cell_groups"]
        report = dict(
            kind=RESULT_KIND,
            law=LAW_ID,
            request_identity=request.identity,
            status=status,
            parent=_parent_record(request.parent_request, request.parent_binding),
            declaration=declaration,
            axes=axes,
            exposed_faces=exposed,
            geometry_material_owner_associations=[
                dict(
                    cell_id=r["id"],
                    source_cell_ids=r["source_cell_ids"],
                    disposition="removed" if r["id"] in selected else "surviving",
                )
                for r in groups
            ],
            child_geometry_identity=None if child_binding is None else child_binding.identity,
            native_invalidated_owners=list(NATIVE_INVALIDATED_OWNERS),
            invalidated_cells_owners=[]
            if not selected
            else [
                "material_and_voltage_component_bindings",
                "field_operators",
                "compiled_layout",
                "physical_model_preparation",
                "complete_checkpoint",
            ],
            coordinate_policy="unchanged_supplied_survivor_source_polygons@1",
            bath_policy="existing_owner_ids_and_parent_volumes_explicit_exposed_faces@1",
            material_state_policy="not_supplied_not_remapped_no_removed_material_release@1",
            physical_model_prepared=False,
            ordinary_continuation_admitted=False,
            native_equivalence=False,
            scientific_qualification_inherited=False,
            numerical_trajectory_claim=False,
        )
        binding = Binding(request.identity, _json(report), child_request, child_binding, "")
        return Binding(
            binding.request_identity,
            binding.report_json,
            child_request,
            child_binding,
            _digest(_binding_record(binding)),
        )
    except Exception as error:
        retained = _retained(error, trial, "rebuild")
        if retained is error:
            raise
        raise retained from error


def validate_binding(request, binding):
    trial = dict(
        stage="binding", supplied_request=capture(request), supplied_binding=capture(binding)
    )
    try:
        if (
            type(binding) is not Binding
            or binding.request_identity != request.identity
            or type(binding.report_json) is not str
        ):
            raise RemovalRejected("binding_ownership", stage="identity")
        if (binding.child_request is None) != (binding.child_binding is None):
            raise RemovalRejected("child_owner_pair", stage="identity")
        if binding.child_request is not None:
            geometry.validate_binding(binding.child_request, binding.child_binding)
        expected = prepare(request)
        if binding.identity != expected.identity or _binding_record(binding) != _binding_record(
            expected
        ):
            raise RemovalRejected("changed_binding", stage="identity")
        return binding
    except Exception as error:
        retained = _retained(error, trial, "binding")
        if retained is error:
            raise
        raise retained from error


def require_ordinary_resume(request, binding):
    raise RemovalRejected(
        "ordinary_checkpoint_owner_unavailable",
        stage="continuation",
        trial=dict(
            request=capture(request),
            binding=capture(binding),
            native_invalidated_owners=list(NATIVE_INVALIDATED_OWNERS),
        ),
    )
