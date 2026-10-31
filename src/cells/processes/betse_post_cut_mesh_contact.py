"""Bounded supplied-state native DEC cutting and membrane-contact reconstruction.

This component stops before cells.environment. Exact source return/failure is
separate from stable owner lineage and does not admit a physical mesh or a
runnable post-cut checkpoint.
"""

import copy
import hashlib
import json
import sys
import traceback
import warnings
from dataclasses import dataclass
from types import SimpleNamespace

LAW_ID = "betse_post_cut_DEC_and_contact_source_boundary@1"
BOUNDARY = "before_TissueHandler._cut_cells:cells.environment"
MAX_CELLS, MAX_MEMBRANES, MAX_EDGES, MAX_FACES = 16, 96, 128, 64
MAX_EVENTS = 256
MAX_EVIDENCE_BYTES = 128 * 2**20
HELD_SOURCE_COMPONENT = True
INVALIDATED_OWNERS = (
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


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


@dataclass(frozen=True)
class Trial:
    law_id: str
    mode: str
    before_json: str
    after_json: str
    events_json: str
    failure_json: object
    source_completed: bool
    first_failure_stage: object
    source_pin: str
    identity: str


class BoundaryRejected(RuntimeError):
    def __init__(self, reason, *, trial=None, partial=None):
        super().__init__(reason)
        self.trial, self.partial = trial, partial


def trial_record(value):
    return {
        key: getattr(value, key)
        for key in (
            "law_id",
            "mode",
            "before_json",
            "after_json",
            "events_json",
            "failure_json",
            "source_completed",
            "first_failure_stage",
            "source_pin",
        )
    }


def modules():
    import numpy as np
    from scipy.spatial import cKDTree

    from cells.processes import betse_post_cut_mesh_contact_records as wire
    from cells.processes import betse_post_cut_mesh_contact_source as source

    return np, cKDTree, wire, source


def _validate_request(raw, np):
    expected = {
        "kind",
        "mode",
        "classification",
        "provenance",
        "sim",
        "cells",
        "mesh",
        "selection",
        "parameters",
        "handler",
        "owners",
    }
    if (
        type(raw) is not dict
        or set(raw) != expected
        or raw["kind"] != "cells.supplied_post_cut_source_request@1"
    ):
        raise ValueError("Complete explicit supplied native state required")
    if raw["mode"] not in ("cut_through_contacts", "mesh_only", "contact_only"):
        raise ValueError("Unknown separately named source component boundary")
    if (
        raw["classification"] != "manufactured_supplied_source_state"
        or type(raw["provenance"]) is not str
        or not raw["provenance"]
    ):
        raise ValueError("Caller-supplied state is not cold native geometry provenance")
    if not all(
        type(raw[key]) is dict
        for key in ("sim", "cells", "mesh", "selection", "parameters", "handler", "owners")
    ):
        raise ValueError("Explicit source owner dictionaries required")
    p = raw["parameters"]
    if p.get("is_ecm") is not True or p.get("Ca_dyn") is not False:
        raise ValueError("Actual ordinary ECM/Ca_dynFalse source conditions required")
    owners = raw["owners"]
    if set(owners) != {
        "cell_ids",
        "membrane_ids",
        "mesh_edge_ids",
        "mesh_face_ids",
        "cell_membrane_ids",
    }:
        raise ValueError("Original named owner axes required")
    for key in ("cell_ids", "membrane_ids", "mesh_edge_ids", "mesh_face_ids"):
        values = owners[key]
        if (
            type(values) is not list
            or any(type(value) is not str or not 0 < len(value) <= 96 for value in values)
            or len(set(values)) != len(values)
        ):
            raise ValueError("Unique ordered stable names required: " + key)
    n = len(owners["cell_ids"])
    m = len(owners["membrane_ids"])
    if (
        not 1 <= n <= MAX_CELLS
        or not 1 <= m <= MAX_MEMBRANES
        or len(owners["mesh_edge_ids"]) > MAX_EDGES
        or len(owners["mesh_face_ids"]) > MAX_FACES
    ):
        raise ValueError("Source state exceeds the bounded owner/working-array panel")
    groups = owners["cell_membrane_ids"]
    if len(groups) != n or [value for row in groups for value in row] != owners["membrane_ids"]:
        raise ValueError("Cell membrane occurrences must partition the original ordered axis")
    selected = raw["selection"]
    if set(selected) != {"cells", "membranes", "provenance"} or not selected["provenance"]:
        raise ValueError("Actual supplied picker result includes both typed occurrence axes")
    for key, limit in (("cells", n), ("membranes", m)):
        values = np.asarray(selected[key])
        if (
            values.ndim != 1
            or values.dtype.kind not in "iu"
            or np.any(values < 0)
            or np.any(values >= limit)
        ):
            raise ValueError("Explicit in-range integer picker occurrence array required")
    expected_membranes = [
        owners["membrane_ids"].index(value)
        for index in selected["cells"]
        for value in groups[int(index)]
    ]
    if np.asarray(selected["membranes"]).tolist() != expected_membranes:
        raise ValueError("Picker membrane occurrences differ from selected original owners")
    # Scientific/source-domain defects (including nonfinite and duplicates) are
    # retained by the original source; this admission bounds axes and ownership.
    if raw["mode"] != "contact_only":
        mesh = raw["mesh"]
        if np.shape(mesh.get("tri_verts")) != (n, 2) or np.shape(mesh.get("tri_edges")) != (
            len(owners["mesh_edge_ids"]),
            2,
        ):
            raise ValueError("Supplied DEC vertex/edge axes differ from original cell owners")
        if len(mesh.get("tri_cells", ())) != len(owners["mesh_face_ids"]):
            raise ValueError("Supplied DEC face owner axis differs")
    return raw


def _available(value, np, tree_type, seen=None):
    if isinstance(value, tree_type):
        return dict(kind="native_KDTree_input_token", data=np.asarray(value.data))
    if isinstance(value, (np.ndarray, np.generic, str, bool, int, float, type(None))):
        return value
    if isinstance(value, (list, tuple, set, dict, SimpleNamespace)):
        # Source frames contain only typed data except local KDTree instances.
        # Their containers are passed directly so the established codec retains
        # shared identities. Trees occur as named locals in these methods.
        return value
    return dict(
        kind="unserializable_source_local_token",
        python_type=type(value).__module__ + "." + type(value).__qualname__,
    )


def _execute(raw, *, native=None, observer=None):
    np, tree_type, wire, default_source = modules()
    source = default_source if native is None else native
    before = wire.snapshot(raw)
    _validate_request(raw, np)
    work = copy.deepcopy(raw)

    class Mesh(source.MeshKernel, SimpleNamespace):
        pass

    class Cells(source.CellKernel, SimpleNamespace):
        pass

    mesh = Mesh()
    mesh.__dict__ = work["mesh"]
    cells = Cells()
    cells.__dict__ = work["cells"]
    cells.mesh = mesh
    p = SimpleNamespace()
    p.__dict__ = work["parameters"]
    sim = SimpleNamespace()
    sim.__dict__ = work["sim"]
    handler = SimpleNamespace()
    handler.__dict__ = work["handler"]
    phase = SimpleNamespace(cells=cells, p=p, sim=sim)

    class Picker:
        def pick_cells_and_mems(self, *, cells, p):
            return work["selection"]["cells"], work["selection"]["membranes"]

    picker = Picker()
    events = []
    event_bytes = 0
    stack = []
    first_failure = None

    def world():
        return dict(
            sim=sim,
            cells=cells,
            parameters=p,
            handler=handler,
            selection=work["selection"],
            owners=work["owners"],
        )

    codes = {
        source.cut_through_contacts.__code__: "cut_through_contacts",
        source.flatten.__code__: "flatten",
    }
    for cls in (source.MeshKernel, source.CellKernel):
        for name, value in vars(cls).items():
            if callable(value) and hasattr(value, "__code__"):
                codes[value.__code__] = name

    def add(kind, name, payload):
        nonlocal event_bytes
        encoded = wire.snapshot(payload)
        row = dict(sequence=len(events), kind=kind, method=name, depth=len(stack), payload=encoded)
        # Make actual available data observable before an evidence-budget gate.
        if observer is not None:
            observer(row)
        event_bytes += len(encoded.encode())
        events.append(row)
        if len(events) > MAX_EVENTS or event_bytes > MAX_EVIDENCE_BYTES:
            raise BoundaryRejected(
                "Declared complete source evidence budget exhausted", partial=dict(last_event=row)
            )

    excluded = {"self", "phase", "cells", "p", "sim", "tissue_picker"}

    def trace(frame, event, arg):
        nonlocal first_failure
        name = codes.get(frame.f_code)
        if name is None:
            return trace
        if event == "call":
            stack.append(name)
            add(
                "enter",
                name,
                dict(
                    world=world(),
                    arguments={
                        key: _available(value, np, tree_type)
                        for key, value in frame.f_locals.items()
                        if key not in excluded
                    },
                ),
            )
        elif event in ("return", "exception"):
            available = {
                key: _available(value, np, tree_type)
                for key, value in frame.f_locals.items()
                if key not in excluded
            }
            payload = dict(world=world(), available_source_locals=available)
            if event == "exception":
                first_failure = first_failure or name
                payload["exception"] = dict(type=arg[0].__name__, message=str(arg[1]))
            add(event, name, payload)
            if event == "return" and stack:
                stack.pop()
        return trace

    failure = None
    returned = None
    previous = sys.gettrace()
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            sys.settrace(trace)
            try:
                if raw["mode"] == "cut_through_contacts":
                    returned = source.cut_through_contacts(handler, phase, picker)
                elif raw["mode"] == "mesh_only":
                    returned = mesh.cut_mesh(work["selection"]["cells"])
                else:
                    cells.mem_processing(p)
                    cells.near_neigh(p)
                    cells.calc_gj_vects(p)
            finally:
                sys.settrace(previous)
        warning_records = [
            dict(
                type=type(item.message).__name__,
                message=str(item.message),
                filename=item.filename,
                lineno=item.lineno,
            )
            for item in caught
        ]
    except Exception as error:
        sys.settrace(previous)
        failure = dict(
            type=type(error).__name__,
            message=str(error),
            traceback=traceback.format_exc(),
            available_partial=getattr(error, "partial", None),
        )
        warning_records = (
            [
                dict(
                    type=type(item.message).__name__,
                    message=str(item.message),
                    filename=item.filename,
                    lineno=item.lineno,
                )
                for item in caught
            ]
            if "caught" in locals()
            else []
        )
    returned_locals = None
    if isinstance(returned, dict):
        returned_locals = {
            key: _available(value, np, tree_type)
            for key, value in returned.items()
            if key not in excluded
        }
    else:
        returned_locals = returned
    after = wire.snapshot(
        dict(world=world(), return_value=returned_locals, warnings=warning_records)
    )
    if wire.snapshot(raw) != before:
        raise BoundaryRejected(
            "Source capture mutated its actual supplied parent",
            partial=dict(before=before, after=after, events=events),
        )
    from pathlib import Path

    source_path = Path(default_source.__file__)
    pin = hashlib.sha256(source_path.read_bytes()).hexdigest()
    record = dict(
        law_id=LAW_ID,
        mode=raw["mode"],
        before_json=before,
        after_json=after,
        events_json=json.dumps(events, sort_keys=True, separators=(",", ":")),
        failure_json=None if failure is None else json.dumps(failure, sort_keys=True),
        source_completed=failure is None,
        first_failure_stage=first_failure,
        source_pin=pin,
    )
    return Trial(**record, identity=digest(record))


def capture(raw, *, observer=None):
    """Original source only on a cloned supplied state; failures stay as trials."""
    available_input = None
    try:
        _, _, wire, _ = modules()
        available_input = wire.snapshot(raw)
        return _execute(raw, observer=observer)
    except Exception as error:
        raise BoundaryRejected(
            "Cut/contact request or capture failed before a complete trial",
            partial=dict(
                available_input_json=available_input,
                original_type=type(error).__name__,
                original_reason=str(error),
                original_partial=getattr(error, "partial", None),
            ),
        ) from error


def validate_trial(trial):
    if (
        type(trial) is not Trial
        or trial.law_id != LAW_ID
        or digest(trial_record(trial)) != trial.identity
    ):
        raise ValueError("Complete unchanged cut/contact source trial required")
    if trial.source_completed is not (trial.failure_json is None):
        raise ValueError("Source completion/failure declaration differs")
    return trial


def owner_projection(trial):
    """Requested selection and proven source lineage; never a physical commit."""
    validate_trial(trial)
    np, _, wire, _ = modules()
    raw = wire.restore(trial.before_json)
    owners = raw["owners"]
    selected = set(map(int, raw["selection"]["cells"]))
    requested_kept = [i for i in range(len(owners["cell_ids"])) if i not in selected]
    requested_removed = [name for i, name in enumerate(owners["cell_ids"]) if i in selected]
    result = dict(
        kind="cells.post_cut_stable_owner_projection@1",
        source_trial_identity=trial.identity,
        cell_ids_before=owners["cell_ids"],
        requested_survivor_cell_ids=[owners["cell_ids"][i] for i in requested_kept],
        requested_removed_cell_ids=requested_removed,
        selection_applied_by_this_mode=trial.mode != "contact_only",
        cell_ids_after=None,
        removed_cell_ids=None,
        observed_lineage_status="unavailable_failed_source",
        original_partial_state=dict(
            source_trial_identity=trial.identity,
            before_json_sha256=hashlib.sha256(trial.before_json.encode()).hexdigest(),
            after_json_sha256=hashlib.sha256(trial.after_json.encode()).hexdigest(),
            events_json_sha256=hashlib.sha256(trial.events_json.encode()).hexdigest(),
            first_failure_stage=trial.first_failure_stage,
            original_trial_and_partial_arrays_preserved=True,
        ),
        source_completed=trial.source_completed,
        physical_mesh_admitted=False,
        executable_DEC_parent_admitted=False,
        ordinary_checkpoint_ready=False,
        invalidated_owners=list(INVALIDATED_OWNERS),
        required_next_capability="environment_grid_maps_then_Poisson_and_complete_state_cache_rebind",
        native_mesh_edge_return_policy="removed_edge_indices_despite_restructure_docstring",
        contact_pairs=None,
        mesh_survivor_edge_ids=None,
        mesh_removed_edge_ids=None,
        native_edge_endpoint_owner_pairs=None,
        survivor_edge_endpoints_preserved=None,
        hanging_cell_ids=None,
        auxiliary_geometry_and_operators_rebuilt=False,
        contact_validation=None,
    )
    # A failed source can leave differently shortened buffers. Keep its complete
    # partial graph in the original trial; requested deletion is no proof that
    # any common cell/edge/material owner axis completed.
    if not trial.source_completed:
        return result
    after = wire.restore(trial.after_json)["world"]
    cells, mesh = after["cells"], after["cells"].mesh
    kept = requested_kept
    if trial.mode == "contact_only":
        kept = list(range(len(owners["cell_ids"])))
        result["observed_lineage_status"] = "observed_completed_contact_helper_no_cell_deletion"
        result["removed_cell_ids"] = []
    else:
        expected_vertices = np.asarray(raw["mesh"]["tri_verts"])[kept]
        actual_vertices = np.asarray(mesh.tri_verts)
        vertex_axis_exact = (
            actual_vertices.shape == expected_vertices.shape
            and actual_vertices.dtype == expected_vertices.dtype
            and actual_vertices.tobytes(order="C") == expected_vertices.tobytes(order="C")
        )
        result["vertex_axis_matches_literal_deletion"] = vertex_axis_exact
        if not vertex_axis_exact:
            result["observed_lineage_status"] = "unavailable_completed_source_vertex_axis_mismatch"
            return result
        result["observed_lineage_status"] = "observed_completed_mesh_vertices"
        result["removed_cell_ids"] = requested_removed
    result["cell_ids_after"] = [owners["cell_ids"][i] for i in kept]
    if trial.mode != "contact_only":
        old = raw["mesh"]
        removed = set()
        for index in selected:
            removed.update(map(int, old["tverts_to_tedges"][index]))
        surviving = [index for index in range(len(owners["mesh_edge_ids"])) if index not in removed]
        if len(surviving) != len(mesh.tri_edges):
            raise BoundaryRejected(
                "Native edge count cannot be associated with original edge owners", trial=trial
            )
        result["mesh_survivor_edge_ids"] = [owners["mesh_edge_ids"][index] for index in surviving]
        result["mesh_removed_edge_ids"] = [
            owners["mesh_edge_ids"][index] for index in sorted(removed)
        ]
        original_pairs = [
            [owners["cell_ids"][int(vertex)] for vertex in old["tri_edges"][index]]
            for index in surviving
        ]
        rebuilt_pairs = [
            [result["cell_ids_after"][int(vertex)] for vertex in row] for row in mesh.tri_edges
        ]
        result["native_edge_endpoint_owner_pairs"] = rebuilt_pairs
        result["survivor_edge_endpoints_preserved"] = original_pairs == rebuilt_pairs
        faces = [set(map(int, row)) for row in mesh.tri_cells]
        result["hanging_cell_ids"] = [
            name
            for index, name in enumerate(result["cell_ids_after"])
            if not any(index in face for face in faces)
        ]
        result["auxiliary_geometry_and_operators_rebuilt"] = False
    if trial.mode == "mesh_only":
        return result
    membranes = [name for index in kept for name in owners["cell_membrane_ids"][index]]
    partner = np.asarray(cells.nn_i)
    if (
        partner.shape != (len(membranes),)
        or partner.dtype.kind not in "iu"
        or np.any(partner < 0)
        or np.any(partner >= len(membranes))
    ):
        result["contact_validation"] = dict(status="raw_invalid_partner_axes")
        return result
    owner = np.asarray(cells.mem_to_cells)
    geometry_domain = bool(
        owner.shape == (len(membranes),)
        and owner.dtype.kind in "iu"
        and np.all(owner >= 0)
        and np.all(owner < len(kept))
        and np.asarray(cells.mem_sa).shape == (len(membranes),)
        and np.isfinite(cells.mem_sa).all()
        and np.all(cells.mem_sa > 0)
        and np.asarray(cells.mem_vects_flat).shape == (len(membranes), 6)
        and np.isfinite(cells.mem_vects_flat).all()
    )
    reciprocal = bool(np.array_equal(partner[partner], np.arange(len(partner))))
    pairs = [(i, int(j)) for i, j in enumerate(partner) if i < int(j)]
    different = all(owner[i] != owner[j] for i, j in pairs)
    area = all(np.isclose(cells.mem_sa[i], cells.mem_sa[j], rtol=2e-12, atol=0) for i, j in pairs)
    normals = all(
        np.allclose(cells.mem_vects_flat[i, 2:4], -cells.mem_vects_flat[j, 2:4], rtol=0, atol=2e-12)
        for i, j in pairs
    )
    boundary = bool(
        np.all(
            partner[np.asarray(cells.bflags_mems, dtype=int)]
            == np.asarray(cells.bflags_mems, dtype=int)
        )
    )
    result["membrane_ids_after"] = membranes
    result["contact_pairs"] = [[membranes[i], membranes[j]] for i, j in pairs]
    result["contact_validation"] = dict(
        finite_positive_patch_geometry=geometry_domain,
        reciprocal=reciprocal,
        different_cell_owners=different,
        equal_paired_areas=area,
        opposed_paired_normals=normals,
        boundary_self_pairs=boundary,
        source_boundary_length_sentinel_minus_one=bool(np.any(cells.nn_len == -1)),
        conservative_contact_candidate=geometry_domain
        and reciprocal
        and different
        and area
        and normals
        and boundary,
    )
    return result


def request_ordinary_continuation(trial, *, declarations=None):
    validate_trial(trial)
    raise BoundaryRejected(
        (
            "Ordinary continuation requires an admitted executable DEC parent, "
            "qualified environment/grid/Poisson, cache epochs and a complete post-cut checkpoint"
        ),
        trial=trial,
        partial=dict(
            boundary=BOUNDARY,
            supplied_declarations=declarations,
            metadata_cannot_unlock_checkpoint=True,
            requires_admitted_executable_DEC_parent=True,
            executable_DEC_parent_admitted=False,
            invalidated_owners=list(INVALIDATED_OWNERS),
        ),
    )
