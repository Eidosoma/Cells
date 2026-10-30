"""Owned native target selection with separate NumPy and Python RNG states.

PERCENT mutates a carried logical cell order using NumPy's legacy shuffle.
Global GJ setup shuffles a discarded membrane copy with Python's RNG, then
selects the original membrane prefix. Neither operation mutates geometry or a
process-global random stream. This prepares targets, not a tissue timestep.
"""

import json
import math
import platform
import random
from dataclasses import dataclass, replace
from types import MappingProxyType

import numpy as np

from cells.processes import betse_perturbations as perturb
from cells.processes import betse_tissue_profiles as profiles

KIND = "cells.native_target_selection_stream@1"
PYTHON_KIND = "cells.cpython_random_state@1"
RESULT_KIND = "cells.native_target_selection_result@1"
MAX_CALL = 2**64 - 1


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


@dataclass(frozen=True, slots=True)
class PythonStream:
    state_json: str
    python_version: str
    implementation: str
    identity: str


def python_stream(state, *, python_version, implementation):
    """Import complete version-3 Python state; never seed from an owner label."""
    if (
        implementation != "CPython"
        or platform.python_implementation() != implementation
        or python_version != platform.python_version()
    ):
        raise ValueError("Python selection replay requires the recorded CPython version")
    if not isinstance(state, (tuple, list)) or len(state) != 3:
        raise ValueError("Require complete Python random state")
    version, words, gaussian = state
    if (
        type(version) is not int
        or version != 3
        or not isinstance(words, (tuple, list))
        or len(words) != 625
        or any(type(value) is not int or not 0 <= value < 2**32 for value in words[:-1])
        or not any(words[:-1])
        or type(words[-1]) is not int
        or not 0 <= words[-1] <= 624
        or (gaussian is not None and (type(gaussian) is not float or not math.isfinite(gaussian)))
    ):
        raise ValueError("Invalid Python MT19937 words, position or Gaussian cache")
    saved = [3, list(words), gaussian]
    payload = dict(
        kind=PYTHON_KIND, state=saved, python_version=python_version, implementation=implementation
    )
    return PythonStream(_json(saved), python_version, implementation, profiles._hash(payload))


def seeded_python_stream(seed):
    if type(seed) is not int or seed < 0:
        raise ValueError("Declare an explicit nonnegative Python seed")
    return python_stream(
        random.Random(seed).getstate(),
        python_version=platform.python_version(),
        implementation=platform.python_implementation(),
    )


def python_record(stream):
    if type(stream) is not PythonStream:
        raise ValueError("Require a complete owned Python stream")
    expected = python_stream(
        json.loads(stream.state_json),
        python_version=stream.python_version,
        implementation=stream.implementation,
    )
    if expected != stream:
        raise ValueError("Python stream state association changed")
    return dict(
        kind=PYTHON_KIND,
        state=json.loads(stream.state_json),
        python_version=stream.python_version,
        implementation=stream.implementation,
        identity=stream.identity,
    )


def restore_python(saved):
    if type(saved) is not dict or set(saved) != {
        "kind",
        "state",
        "python_version",
        "implementation",
        "identity",
    }:
        raise ValueError("Require complete serialized Python stream")
    stream = python_stream(
        saved["state"],
        python_version=saved["python_version"],
        implementation=saved["implementation"],
    )
    if _json(python_record(stream)) != _json(saved):
        raise ValueError("Saved Python stream identity or canonical values changed")
    return stream


@dataclass(frozen=True, slots=True)
class SelectionStream:
    layout_identity: str
    stream_id: str
    world_id: int
    next_call: int
    numpy: perturb.NativeStream
    python: PythonStream
    cell_order: tuple
    identity: str


def stream_record(stream):
    if type(stream) is not SelectionStream:
        raise ValueError("Require a complete target-selection stream")
    payload = dict(
        kind=KIND,
        layout_identity=stream.layout_identity,
        stream_id=stream.stream_id,
        world_id=stream.world_id,
        next_call=stream.next_call,
        numpy=perturb.native_stream_manifest(stream.numpy),
        python=python_record(stream.python),
        cell_order=stream.cell_order,
    )
    return payload | dict(identity=profiles._hash(payload))


def _seal(stream):
    return replace(stream, identity=stream_record(stream)["identity"])


def validate_stream(stream, layout):
    if type(stream) is not SelectionStream:
        raise ValueError("Require the complete selection stream")
    if stream.identity != stream_record(stream)["identity"]:
        raise ValueError("Selection stream association changed")
    if stream.layout_identity != profiles.layout_identity(layout):
        raise ValueError("Selection stream belongs to another physical layout")
    if type(stream.stream_id) is not str or not stream.stream_id.strip():
        raise ValueError("Require an explicit nonempty stream ID")
    for value in (stream.world_id, stream.next_call):
        if type(value) is not int or not 0 <= value <= MAX_CALL:
            raise ValueError("Selection world and call counters require uint64 integers")
    if (
        type(stream.cell_order) is not tuple
        or len(stream.cell_order) != len(layout.cell_ids)
        or set(stream.cell_order) != set(layout.cell_ids)
    ):
        raise ValueError("Carried cell order must be a complete original-owner permutation")
    return stream


def new_stream(layout, numpy_stream, python_rng, *, stream_id, world_id, next_call=0):
    t = profiles.validate_layout(layout)
    stream = _seal(
        SelectionStream(
            profiles.layout_identity(t),
            stream_id,
            world_id,
            next_call,
            numpy_stream,
            python_rng,
            t.cell_ids,
            "",
        )
    )
    return validate_stream(stream, t)


def restore_stream(saved, layout, *, stream_id, world_id):
    """Restore caller-declared owners and both full tapes without drawing."""
    if type(saved) is not dict or saved.get("kind") != KIND:
        raise ValueError("Require a complete serialized selection stream")
    try:
        restored = SelectionStream(
            saved["layout_identity"],
            saved["stream_id"],
            saved["world_id"],
            saved["next_call"],
            perturb.native_stream_from_manifest(saved["numpy"]),
            restore_python(saved["python"]),
            tuple(saved["cell_order"]),
            saved["identity"],
        )
        validate_stream(restored, layout)
        if (
            type(stream_id) is not str
            or type(world_id) is not int
            or restored.stream_id != stream_id
            or restored.world_id != world_id
            or _json(stream_record(restored)) != _json(saved)
        ):
            raise ValueError(
                "Saved selection stream differs from requested owners or canonical values"
            )
    except (KeyError, TypeError) as error:
        raise ValueError("Incomplete selection stream record") from error
    return restored


@dataclass(frozen=True, slots=True)
class SelectionOperation:
    kind: str
    name: str
    requested_percent: float
    source: SelectionStream
    successor: SelectionStream
    permutation: tuple
    selected: tuple
    shuffled_copy_ignored: bool


@dataclass(frozen=True, slots=True)
class SelectionResult:
    source: SelectionStream
    stream: SelectionStream
    binding: profiles.Binding
    global_gj_targets: profiles.Target | None
    operations: tuple
    identity: str


class SelectionRejected(ValueError):
    def __init__(self, reason, *, source, trial_stream, operations, stage):
        super().__init__("Target selection refused at " + stage + ": " + str(reason))
        self.source, self.trial_stream = source, trial_stream
        self.operations, self.stage = tuple(operations), stage


def result_record(result):
    operations = [
        dict(
            kind=op.kind,
            name=op.name,
            requested_percent=op.requested_percent,
            source_identity=op.source.identity,
            successor_identity=op.successor.identity,
            permutation=op.permutation,
            selected=op.selected,
            shuffled_copy_ignored=op.shuffled_copy_ignored,
        )
        for op in result.operations
    ]
    payload = dict(
        kind=RESULT_KIND,
        source=stream_record(result.source),
        successor=stream_record(result.stream),
        binding=profiles.binding_manifest(result.binding),
        operations=operations,
        global_gj_targets=None
        if result.global_gj_targets is None
        else result.global_gj_targets.ids,
    )
    return payload | dict(identity=profiles._hash(payload))


def _numpy_rng(stream):
    state = perturb.native_stream_manifest(stream)["state"]
    rng = np.random.RandomState(0)
    rng.set_state((state[0], np.asarray(state[1], dtype=np.uint32), state[2], state[3], state[4]))
    return rng


def _python_rng(stream):
    state = python_record(stream)["state"]
    rng = random.Random(0)
    rng.setstate((state[0], tuple(state[1]), state[2]))
    return rng


def _binding(layout, default, definitions, start_order, **kwargs):
    """Reuse qualified maps, preserving ALL aliases across repeated preparations."""
    bound = profiles.compile_profiles(layout, default, definitions, **kwargs)
    order, all_picks = tuple(start_order), {}
    for index, row in enumerate([default, *definitions] if kwargs["enabled"] else []):
        kind = "all" if index == 0 else row.selector.kind
        if kind == "all":
            all_picks[row.name] = order
        elif kind == "percent":
            order = tuple(row.selector.permutation_cell_ids)
    targets = dict(bound.targets)
    final_cells = profiles._target(layout, "cell", order)
    for name, picked in all_picks.items():
        selected = profiles.targets_for_cell_ids(layout, picked, is_ecm=kwargs["is_ecm"])
        targets[name] = replace(selected, cells=final_cells)
    # ALL membership is unchanged, hence its existing numeric masks remain exact.
    return replace(bound, targets=MappingProxyType(targets), final_cell_order=order)


def resolve(
    layout,
    stream,
    default,
    definitions,
    *,
    ion_enabled=(True,) * 6,
    is_ecm=True,
    enabled=True,
    global_gj_percent=None,
):
    """Resolve profiles then optional global GJ setup as one atomic preparation.

    Geometry and random tapes are caller-owned. World IDs label native tapes;
    they never salt either seed. Logical call count increments for every active
    shuffle, including zero-target and empty-axis calls that consume no words.
    Disabled profiles consume no NumPy state; global GJ has its own enable flag
    (None disables it), independent of profiles, ions and simulation phase.
    """
    trial, completed, stage = stream, [], "source_admission"
    try:
        t = profiles.validate_layout(layout)
        validate_stream(stream, t)
        definitions = tuple(definitions)
        placeholders = []
        for row in definitions if enabled else ():
            if type(row) is not profiles.Profile or type(row.selector) is not profiles.Selector:
                raise ValueError("Require complete explicit profile/selector declarations")
            if row.selector.kind == "percent":
                if type(row.selector.value) not in (int, float):
                    raise ValueError(
                        "Owned percentage selection requires a Python numeric declaration"
                    )
                if row.selector.permutation_cell_ids is not None:
                    raise ValueError(
                        "Owned selection cannot consume a pre-resolved percentage permutation"
                    )
                row = replace(row, selector=replace(row.selector, permutation_cell_ids=t.cell_ids))
            placeholders.append(row)
        kwargs = dict(ion_enabled=ion_enabled, is_ecm=is_ecm, enabled=enabled)
        # Validate complete declarations before any random tape is consumed.
        profiles.compile_profiles(t, default, placeholders, **kwargs)
        global_target = (
            None
            if global_gj_percent is None
            else profiles.global_gj_prefix_targets(t, global_gj_percent)
        )
        resolved = []
        cell_indices = {name: i for i, name in enumerate(t.cell_ids)}
        stage = "percentage_selection"
        for row in definitions if enabled else ():
            if row.selector.kind == "percent":
                if trial.next_call == MAX_CALL:
                    raise ValueError("Selection call counter would overflow uint64")
                rng = _numpy_rng(trial.numpy)
                order = np.asarray(
                    [cell_indices[name] for name in trial.cell_order], dtype=np.int64
                )
                rng.shuffle(order)
                permutation = tuple(t.cell_ids[int(i)] for i in order)
                selected = permutation[: int((float(row.selector.value) / 100) * len(permutation))]
                successor = _seal(
                    replace(
                        trial,
                        numpy=perturb._native_stream(rng.get_state(), np.__version__),
                        next_call=trial.next_call + 1,
                        cell_order=permutation,
                    )
                )
                completed.append(
                    SelectionOperation(
                        "percent",
                        row.name,
                        float(row.selector.value),
                        trial,
                        successor,
                        permutation,
                        selected,
                        False,
                    )
                )
                trial = successor
                row = replace(row, selector=replace(row.selector, permutation_cell_ids=permutation))
            resolved.append(row)
        stage = "global_gj_selection"
        if global_target is not None:
            if trial.next_call == MAX_CALL:
                raise ValueError("Selection call counter would overflow uint64")
            rng = _python_rng(trial.python)
            ignored = np.arange(len(t.membrane_ids), dtype=np.int64)
            rng.shuffle(ignored)
            successor = _seal(
                replace(
                    trial,
                    python=python_stream(
                        rng.getstate(),
                        python_version=trial.python.python_version,
                        implementation=trial.python.implementation,
                    ),
                    next_call=trial.next_call + 1,
                )
            )
            completed.append(
                SelectionOperation(
                    "global_gj",
                    "global_gj",
                    float(global_gj_percent),
                    trial,
                    successor,
                    tuple(t.membrane_ids[int(i)] for i in ignored),
                    global_target.ids,
                    True,
                )
            )
            trial = successor
        stage = "profile_binding"
        binding = _binding(t, default, resolved, stream.cell_order, **kwargs)
        if trial.cell_order != binding.final_cell_order:
            raise ValueError("Selected targets differ from the carried cell order")
        validate_stream(trial, t)
        result = SelectionResult(stream, trial, binding, global_target, tuple(completed), "")
        return replace(result, identity=result_record(result)["identity"])
    except Exception as error:
        raise SelectionRejected(
            error, source=stream, trial_stream=trial, operations=completed, stage=stage
        ) from error
