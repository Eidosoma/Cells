"""Native deletion-prefix evidence and explicit cut epoch invalidation.

The source prefix ends before DEC cutting. Native arrays and an explicitly
owned conservative removal ledger are separate outputs. No geometry factory,
full native cut, physical mesh, ordinary checkpoint or resumed loop is supplied.
"""

import copy
import hashlib
import json
import traceback
from collections.abc import Mapping
from dataclasses import dataclass, fields, is_dataclass
from types import SimpleNamespace

import numpy as np

from cells.processes import betse_native_cut_lifecycle_source as source
from cells.processes import betse_tissue_cut as ownership

LAW_ID = "betse_native_cut_deletion_prefix_and_owner_epoch@1"


class _DataOwner:
    """Explicit data carrier whose dictionary preserves supplied graph aliases."""


def _namespace(mapping):
    result = _DataOwner()
    result.__dict__ = mapping
    return result


BOUNDARY = "before_TissueHandler._cut_cells:cells.mesh.cut_mesh"
REQUIRED_OWNERS = (
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


def _hash(value):
    return hashlib.sha256(value.encode()).hexdigest()


def _identity(value):
    return (
        isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)
    )


def snapshot(value):
    """Encode data types, dictionary order and shared mutable references exactly.

    Object arrays encode children rather than object-pointer bytes. Shared object
    identity is retained; distinct ndarray views do not encode shared buffer
    ownership. The literal prefix never mutates existing numeric buffers. This record
    is evidence only; it does not constitute a simulator checkpoint migration.
    """
    nodes, seen = [], {}

    def encode(item, depth=0):
        if depth > 48 or len(nodes) > 32768:
            raise ValueError("Refuse unbounded cut evidence graph")
        if item is None or type(item) in (str, bool, int):
            return item
        if type(item) is float:
            return dict(float64=item.hex())
        if isinstance(item, np.generic):
            return dict(numpy_scalar=item.dtype.str, data=item.tobytes().hex())
        if not isinstance(
            item, (np.ndarray, Mapping, list, tuple, set, SimpleNamespace, _DataOwner)
        ) and not is_dataclass(item):
            raise ValueError("Require explicit cut data without executable or opaque owners")
        at = seen.get(id(item))
        if at is not None:
            return dict(ref=at)
        at = len(nodes)
        seen[id(item)] = at
        nodes.append(None)
        if isinstance(item, np.ndarray):
            if item.nbytes > 16 * 2**20:
                raise ValueError("Refuse an unbounded cut array")
            node = dict(kind="ndarray", dtype=item.dtype.str, shape=list(item.shape))
            if item.dtype.hasobject:
                node["items"] = [encode(v, depth + 1) for v in item.flat]
            else:
                node["data"] = item.tobytes(order="C").hex()
        elif isinstance(item, Mapping):
            if any(type(key) is not str for key in item):
                raise ValueError("Require named cut data fields")
            node = dict(kind="dict", items=[[key, encode(v, depth + 1)] for key, v in item.items()])
        elif isinstance(item, (SimpleNamespace, _DataOwner)):
            node = dict(
                kind="namespace",
                items=[[key, encode(v, depth + 1)] for key, v in vars(item).items()],
            )
        elif is_dataclass(item):
            node = dict(
                kind="dataclass",
                type=type(item).__name__,
                items=[[f.name, encode(getattr(item, f.name), depth + 1)] for f in fields(item)],
            )
        else:
            kind = "set" if isinstance(item, set) else "list" if isinstance(item, list) else "tuple"
            values = sorted(item, key=repr) if isinstance(item, set) else item
            node = dict(kind=kind, items=[encode(v, depth + 1) for v in values])
        nodes[at] = node
        return dict(ref=at)

    root = encode(value)
    return json.dumps(
        dict(kind="cells.cut_typed_alias_graph@1", root=root, nodes=nodes),
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


@dataclass(frozen=True)
class PrefixTrial:
    law_id: str
    boundary: str
    before_json: str
    after_json: str
    source_prefix_completed: bool
    failure_json: str | None
    identity: str

    @property
    def complete_native_cut(self):
        return False


def _trial_record(trial):
    return (
        trial.law_id,
        trial.boundary,
        trial.before_json,
        trial.after_json,
        trial.source_prefix_completed,
        trial.failure_json,
    )


def validate_trial(trial):
    if type(trial) is not PrefixTrial or trial.law_id != LAW_ID or trial.boundary != BOUNDARY:
        raise ValueError("Require the owned literal native deletion-prefix trial")
    expected = _hash(json.dumps(_trial_record(trial), separators=(",", ":")))
    if trial.identity != expected:
        raise ValueError("Changed native prefix evidence")
    for packet in (trial.before_json, trial.after_json):
        if json.loads(packet)["kind"] != "cells.cut_typed_alias_graph@1":
            raise ValueError("Require complete typed cut snapshots")
    if trial.source_prefix_completed is not (trial.failure_json is None):
        raise ValueError("Source prefix completion and failure evidence disagree")


def capture_prefix(simulator_fields, cell_fields, selection, parameters, *, handler_fields=None):
    """Run only the literal pre-mesh fragment on cloned explicitly supplied data.

    Selection is the supplied picker return, not an executed profile selector.
    Exceptions become retained failed trials; no data2/list/axis defect is fixed.
    """
    if not all(
        isinstance(value, dict) for value in (simulator_fields, cell_fields, selection, parameters)
    ):
        raise ValueError("Require explicit simulator/cell/selection/parameter records")
    if (
        set(selection) != {"cells", "membranes", "provenance"}
        or not isinstance(selection["provenance"], str)
        or not selection["provenance"].strip()
    ):
        raise ValueError("Require the supplied source picker-return epoch and both target arrays")
    if parameters.get("is_ecm") is not True or parameters.get("Ca_dyn") is not False:
        raise ValueError("This ordinary ECM prefix requires actual is_ecm True/Ca_dyn False owners")
    if handler_fields is None:
        handler_fields = {}
    if not isinstance(handler_fields, dict):
        raise ValueError("Require explicit handler fields")
    supplied = dict(
        sim=simulator_fields,
        cells=cell_fields,
        selection=selection,
        p=parameters,
        handler=handler_fields,
    )
    before = snapshot(supplied)
    # One deepcopy retains aliases across all supplied data while isolating caller state.
    work = copy.deepcopy(supplied)
    phase = SimpleNamespace(
        sim=_namespace(work["sim"]),
        cells=_namespace(work["cells"]),
        p=_namespace(work["p"]),
    )
    handler = _namespace(work["handler"])
    targets = work["selection"]
    picker = SimpleNamespace(
        pick_cells_and_mems=lambda cells, p: (targets["cells"], targets["membranes"])
    )
    failure = None
    local_values = {}
    source_frames = []
    excluded = {"self", "phase", "cells", "p", "sim", "tissue_picker"}
    try:
        local_values = source.deletion_prefix(handler, phase, picker)
    except Exception as error:
        frame = error.__traceback__
        while frame is not None:
            name = frame.tb_frame.f_code.co_name
            if name in ("deletion_prefix", "flatten"):
                available = {
                    key: value
                    for key, value in frame.tb_frame.f_locals.items()
                    if key not in excluded
                }
                source_frames.append(dict(function=name, available=available))
                if name == "deletion_prefix":
                    local_values = dict(frame.tb_frame.f_locals)
            frame = frame.tb_next
        failure = json.dumps(
            dict(type=type(error).__name__, message=str(error), traceback=traceback.format_exc()),
            sort_keys=True,
        )
    after = snapshot(
        dict(
            sim=vars(phase.sim),
            cells=vars(phase.cells),
            selection=targets,
            p=vars(phase.p),
            handler=vars(handler),
            available_source_locals={
                key: value for key, value in local_values.items() if key not in excluded
            },
            available_source_frames=source_frames,
        )
    )
    if snapshot(supplied) != before:
        raise RuntimeError("Native prefix mutated its actual supplied parent")
    values = (LAW_ID, BOUNDARY, before, after, failure is None, failure)
    return PrefixTrial(*values, _hash(json.dumps(values, separators=(",", ":"))))


class CutPrefixRejected(RuntimeError):
    def __init__(self, trial):
        validate_trial(trial)
        super().__init__("Original native deletion prefix refused; full partial evidence retained")
        self.trial = trial


@dataclass(frozen=True)
class CutEpoch:
    parent_epoch_identity: str
    trial: PrefixTrial
    stable_removal: object
    source_topology_identity: str
    conservative_target_identity: str
    invalidated: tuple
    rebind_json: str
    identity: str


def _epoch_record(epoch):
    return dict(
        parent=epoch.parent_epoch_identity,
        trial=epoch.trial.identity,
        stable_removal=snapshot(epoch.stable_removal),
        source_topology=epoch.source_topology_identity,
        conservative_target=epoch.conservative_target_identity,
        invalidated=epoch.invalidated,
        rebind_json=epoch.rebind_json,
    )


def _seal(epoch):
    payload = json.dumps(_epoch_record(epoch), sort_keys=True, separators=(",", ":"))
    return CutEpoch(
        epoch.parent_epoch_identity,
        epoch.trial,
        epoch.stable_removal,
        epoch.source_topology_identity,
        epoch.conservative_target_identity,
        epoch.invalidated,
        epoch.rebind_json,
        _hash(payload),
    )


def validate_epoch(epoch):
    if type(epoch) is not CutEpoch or not _identity(epoch.parent_epoch_identity):
        raise ValueError("Require the explicit unchanged parent cut epoch")
    validate_trial(epoch.trial)
    if not epoch.trial.source_prefix_completed or _seal(epoch).identity != epoch.identity:
        raise ValueError("Require unchanged complete prefix and separate stable-owner evidence")
    if epoch.invalidated != REQUIRED_OWNERS:
        raise ValueError("Every actual native cut invalidates the full continuation owners")
    if (
        ownership.layout_identity(epoch.stable_removal.plan.before)
        != epoch.source_topology_identity
    ):
        raise ValueError("Changed pre-cut topology ownership")
    if (
        ownership.layout_identity(epoch.stable_removal.plan.after)
        != epoch.conservative_target_identity
    ):
        raise ValueError("Changed conservative removal target; no native geometry is inferred")


def begin(
    parent_epoch_identity,
    topology,
    removed_cell_ids,
    owned_fields,
    simulator_fields,
    cell_fields,
    selection,
    parameters,
    *,
    handler_fields=None,
):
    """Capture the source prefix and prepare the separate explicit owner sink ledger."""
    if not _identity(parent_epoch_identity):
        raise ValueError("Require the actual supplied parent epoch identity")
    plan = ownership.plan_cut(topology, removed_cell_ids)
    for key, wanted in (("cells", plan.removed["cell"]), ("membranes", plan.removed["membrane"])):
        actual = np.asarray(selection[key])
        if (
            actual.dtype.kind not in "iu"
            or actual.ndim != 1
            or not np.array_equal(np.sort(actual), wanted)
        ):
            raise ValueError(
                "Primary prefix picker targets must match explicit stable owner removal"
            )
    if len(cell_fields["cell_i"]) != len(plan.before.cell_ids) or len(cell_fields["mem_i"]) != len(
        plan.before.membrane_ids
    ):
        raise ValueError("Supplied native source axes disagree with explicit old owner domains")
    if "cell_to_mems" not in cell_fields or len(cell_fields["cell_to_mems"]) != len(
        plan.before.cell_ids
    ):
        raise ValueError("Require the supplied original cell-to-membrane occurrence map")
    for cell, indices in enumerate(cell_fields["cell_to_mems"]):
        expected = np.flatnonzero(plan.before.membrane_cell == cell)
        actual = np.asarray(indices)
        if (
            actual.dtype.kind not in "iu"
            or actual.ndim != 1
            or not np.array_equal(np.sort(actual), expected)
        ):
            raise ValueError("Original cell membrane occurrences disagree with declared owners")
    picked = [int(j) for cell in selection["cells"] for j in cell_fields["cell_to_mems"][cell]]
    if not np.array_equal(selection["membranes"], np.asarray(picked, np.int64)):
        raise ValueError("Preserve the supplied picker cell-to-membrane occurrence order")
    trial = capture_prefix(
        simulator_fields, cell_fields, selection, parameters, handler_fields=handler_fields
    )
    if not trial.source_prefix_completed:
        raise CutPrefixRejected(trial)
    try:
        removed = ownership.apply_cut(topology, removed_cell_ids, owned_fields)
    except Exception as error:
        rejected = CutPrefixRejected(trial)
        rejected.args = (
            "Explicit owner ledger refused after source prefix; returned prefix retained",
        )
        raise rejected from error
    # Even an empty native selection reaches rebuild/reset logic after this boundary.
    return _seal(
        CutEpoch(
            parent_epoch_identity,
            trial,
            removed,
            plan.before_identity,
            plan.after_identity,
            REQUIRED_OWNERS,
            "[]",
            "",
        )
    )


def record_rebind(epoch, *, owner, input_identity, output_identity, artifact_sha256, provenance):
    """Record supplied owner evidence in order without constructing a native world.

    These are declarations to review, not assertions of physical qualification.
    The final ordinary checkpoint still needs actual typed component binders.
    """
    validate_epoch(epoch)
    history = json.loads(epoch.rebind_json)
    if len(history) >= len(REQUIRED_OWNERS) or owner != REQUIRED_OWNERS[len(history)]:
        raise ValueError(
            "Cut rebind evidence is missing, repeated or outside declared dependency order"
        )
    expected = epoch.trial.identity if not history else history[-1]["output_identity"]
    if input_identity != expected or not all(
        _identity(v) for v in (output_identity, artifact_sha256)
    ):
        raise ValueError(
            "Cut owner evidence must bind its actual predecessor and complete artifact"
        )
    if not isinstance(provenance, str) or not provenance.strip():
        raise ValueError("Require explicit supplied post-cut owner provenance")
    history.append(
        dict(
            owner=owner,
            input_identity=input_identity,
            output_identity=output_identity,
            artifact_sha256=artifact_sha256,
            provenance=provenance,
        )
    )
    return _seal(
        CutEpoch(
            epoch.parent_epoch_identity,
            epoch.trial,
            epoch.stable_removal,
            epoch.source_topology_identity,
            epoch.conservative_target_identity,
            epoch.invalidated,
            json.dumps(history, sort_keys=True, separators=(",", ":")),
            "",
        )
    )


def capabilities(epoch):
    validate_epoch(epoch)
    history = json.loads(epoch.rebind_json)
    return dict(
        prefix_complete=True,
        complete_native_cut=False,
        source_prefix_identity=epoch.trial.identity,
        supplied_owner_records=history,
        missing_owners=list(REQUIRED_OWNERS[len(history) :]),
        conservative_target_is_native_geometry=False,
        physical_mesh_qualified=False,
        ordinary_checkpoint_ready=False,
        old_field_or_cache_reuse_allowed=False,
        original_clock_RNG_preservation_not_inferred=True,
        scope="Literal source prefix plus separate stable removal; supplied owner metadata only",
    )


class CutContinuationRejected(RuntimeError):
    def __init__(self, epoch):
        super().__init__(
            (
                "Cut continuation requires qualified changing geometry and an actual "
                "typed post-cut checkpoint"
            )
        )
        self.epoch = epoch
        self.partial = capabilities(epoch)


def require_ordinary_continuation(epoch):
    """Refuse rebasing a frozen ordinary parent onto an unqualified cut geometry."""
    validate_epoch(epoch)
    raise CutContinuationRejected(epoch)
