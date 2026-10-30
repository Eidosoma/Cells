"""Pair a Cells checkpoint with its physiological RNG and optional material state.

The ordinary numeric snapshot retains its existing validation and source/runtime
pins. This outer bundle saves the logical draw counter independently of physical
time and commits their association last. It neither injects noise into a model
nor infers how a perturbation layout maps onto physical state. Consumers must
define that coupling and the points at which draws occur.

The complete component form additionally binds all protein/permeability buffers,
controls, explicit-loop count and accumulated component time. The component and
numeric clocks are independent; a caller must define their physical coupling.
Only the paired loader restores these objects. Loading its inner deterministic
snapshot alone does not restore the component or advance the random stream.

An optional tissue binding also preserves the declared physical owners, geometry
and unit conversion. It is replayed against the numeric snapshot's exact model
definition. Saving that binding does not apply the component to the solver.
The explicit advance_tissue_checkpoint operation restores a bound pair, holds
its physiological permeability through one original tissue interval, and saves
the accepted numeric endpoint with the unchanged component and random stream.
"""

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

from cells.core import physiology_random_streams as streams
from cells.core.specs import ConfigError, digest, read_json
from cells.io import Snapshot, load_snapshot, source_hashes, write_snapshot

KIND = "cells.physiology_random_checkpoint@1"
COMPLETE_KIND = "cells.physiology_perturbation_checkpoint@2"
BOUND_KIND = "cells.physiology_tissue_checkpoint@3"
LOOP_KIND = "cells.physiology_tissue_loop_checkpoint@4"
COMPONENT_KIND = "cells.physiology_perturbation_state@1"
CLOCK_POLICY = "accumulated_explicit_loop_dt_independent_of_numeric_snapshot_clock@1"
FILES = frozenset(("snapshot/manifest.json", "snapshot/state.npz", "stream.json"))
COMPLETE_FILES = FILES | {"component.json"}
BOUND_FILES = COMPLETE_FILES | {"binding.json"}
LOOP_FILES = BOUND_FILES | {"loop.json"}
FIELDS = frozenset(
    (
        "kind",
        "complete",
        "snapshot_identity",
        "spec_sha256",
        "clock",
        "stream_identity",
        "stream_id",
        "world_id",
        "layout_identity",
        "next_tick",
        "files",
        "identity",
    )
)
COMPLETE_FIELDS = FIELDS | {"component_identity", "component_clock"}
BOUND_FIELDS = COMPLETE_FIELDS | {"tissue_binding_identity"}
LOOP_FIELDS = BOUND_FIELDS | {"loop_cursor_identity"}
FORMATS = {
    KIND: (FIELDS, FILES),
    COMPLETE_KIND: (COMPLETE_FIELDS, COMPLETE_FILES),
    BOUND_KIND: (BOUND_FIELDS, BOUND_FILES),
    LOOP_KIND: (LOOP_FIELDS, LOOP_FILES),
}
COMPONENT_FIELDS = frozenset(
    ("kind", "clock_policy", "loop_calls", "stream_identity", "replay", "identity")
)


@dataclass(frozen=True)
class PhysiologyCheckpoint:
    snapshot: Snapshot
    stream: streams.PhysiologyRandomStream
    identity: str
    component_state: object | None = None
    tissue_binding: object | None = None
    loop_cursor: object | None = None


def _sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _write_json(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def _sync_directory(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _clock(point):
    return dict(time=point.time, step_index=point.step_index, event_index=point.event_index)


def _stream_identity(stream, record):
    return dict(
        stream_identity=record["identity"],
        stream_id=stream.stream_id,
        world_id=stream.world_id,
        layout_identity=stream.layout_identity,
        next_tick=stream.next_tick,
    )


def _component_clock(state):
    return dict(elapsed_time_s=state.time_s, loop_calls=state.loop_calls, policy=CLOCK_POLICY)


def _component_record(state, binding, stream):
    from cells.core import physiology_perturbation_step as step
    from cells.processes import betse_perturbations as perturb

    step.validate_state(state, binding)
    stream_record = streams.stream_record(stream)
    if streams.stream_record(state.stream) != stream_record:
        raise ConfigError("Complete perturbation state belongs to another stream checkpoint")
    replay = perturb.Replay(
        state.protein, state.diffusion, stream.rng, stream.next_tick, state.time_s
    )
    payload = dict(
        kind=COMPONENT_KIND,
        clock_policy=CLOCK_POLICY,
        loop_calls=state.loop_calls,
        stream_identity=stream_record["identity"],
        replay=perturb.replay_record(binding, state.controls, replay),
    )
    return payload | dict(identity=digest(payload))


def _restore_component(record, binding, stream):
    from cells.core import physiology_perturbation_step as step
    from cells.processes import betse_perturbations as perturb

    if not isinstance(record, dict) or set(record) != COMPONENT_FIELDS:
        raise ConfigError("Incomplete perturbation component record")
    if (
        record["kind"] != COMPONENT_KIND
        or record["clock_policy"] != CLOCK_POLICY
        or type(record["loop_calls"]) is not int
        or not 0 <= record["loop_calls"] < 2**64
        or digest({key: value for key, value in record.items() if key != "identity"})
        != record["identity"]
        or record["stream_identity"] != streams.stream_record(stream)["identity"]
    ):
        raise ConfigError("Perturbation component identity, stream or clock policy changed")
    try:
        controls = perturb.Controls(**record["replay"]["controls"])
    except (TypeError, KeyError) as error:
        raise ConfigError("Incomplete perturbation controls") from error
    try:
        restored = perturb.restore_replay(record["replay"], binding, controls)
    except (KeyError, TypeError, ValueError) as error:
        raise ConfigError("Invalid or incomplete perturbation material/RNG replay") from error
    if restored.rng != stream.rng or restored.tick != stream.next_tick:
        raise ConfigError("Perturbation material and random state are from different checkpoints")
    state = step.PhysiologyPerturbationState(
        protein=restored.protein,
        diffusion=restored.diffusion,
        stream=stream,
        controls=controls,
        time_s=restored.time_s,
        loop_calls=record["loop_calls"],
    )
    step.validate_state(state, binding)
    if _component_record(state, binding, stream) != record:
        raise ConfigError("Noncanonical or incomplete perturbation state")
    return state


def _restore_tissue_binding(record, spec, binding, component):
    from cells.core import physiology_tissue_binding as tissue

    try:
        restored = tissue.restore_binding(record, spec)
        if streams._binding_identity(binding) != restored.component.identity:
            raise ValueError("Tissue and physiological component owners disagree")
        # Check representability of all six saved buffers in the actual owner
        # binding. This neither finalizes scheduled diffusion nor consumes RNG.
        tissue.component_permeability(component, restored)
    except (KeyError, TypeError, ValueError) as error:
        raise ConfigError(
            "Invalid physiological tissue binding or component association"
        ) from error
    return restored


def _restore_loop_cursor(record, spec, checkpoint, binding, component):
    from cells.core import physiology_tissue_loop as loop

    try:
        restored = loop.restore_cursor(record, spec, checkpoint, binding, component)
        if loop.cursor_record(restored) != record:
            raise ValueError("Noncanonical physiological loop cursor")
    except (KeyError, TypeError, ValueError) as error:
        raise ConfigError("Invalid physiological loop cursor or state association") from error
    return restored


def write_physiology_checkpoint(
    directory,
    spec,
    checkpoint,
    stream,
    binding,
    *,
    component_state=None,
    tissue_binding=None,
    loop_cursor=None,
    expected_source_hashes=None,
):
    """Save associated states in a new directory; a failed publication cannot load.

    The caller supplies the exact stream associated with this accepted numeric
    endpoint. Logical next_tick need not equal step_index or any floating clock.
    A retained stream object deliberately permits explicit replay/branching;
    this writer does not allocate a new random world or silently reseed it.
    Supplying component_state selects the complete material-state format and
    requires its stream to match exactly; no buffers are inferred or rebuilt.
    A tissue_binding additionally saves explicit physical ownership and units,
    requires complete component_state, and must match the exact numeric spec.
    loop_cursor requires both and selects the complete nominal-loop format;
    its numeric/component association must describe this exact accepted pair.
    expected_source_hashes can pin the installation used by an earlier numeric
    operation; a changed installation refuses before the outer manifest commits.
    """
    expected_sources = None if expected_source_hashes is None else dict(expected_source_hashes)
    if expected_sources is not None and expected_sources != source_hashes():
        raise ConfigError("Checkpoint source differs from the accepted tissue operation")
    record = streams.stream_record(stream)
    streams.restore_stream(record, binding)
    component = (
        _component_record(component_state, binding, stream) if component_state is not None else None
    )
    tissue_record = None
    if tissue_binding is not None:
        from cells.core import physiology_tissue_binding as tissue

        if component is None:
            raise ConfigError("Tissue binding requires complete perturbation material state")
        tissue_record = tissue.binding_record(tissue_binding)
        _restore_tissue_binding(tissue_record, spec, binding, component_state)
    loop_record = None
    if loop_cursor is not None:
        from cells.core import physiology_tissue_loop as loop

        if tissue_record is None:
            raise ConfigError("Loop cursor requires a complete tissue-bound checkpoint")
        loop_record = loop.cursor_record(loop_cursor)
        _restore_loop_cursor(loop_record, spec, checkpoint, tissue_binding, component_state)
    kind = (
        LOOP_KIND
        if loop_record is not None
        else BOUND_KIND
        if tissue_record is not None
        else COMPLETE_KIND
        if component is not None
        else KIND
    )
    _, files = FORMATS[kind]
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=False)
    try:
        write_snapshot(root / "snapshot", spec, checkpoint)
        _write_json(root / "stream.json", record)
        if component is not None:
            _write_json(root / "component.json", component)
        if tissue_record is not None:
            _write_json(root / "binding.json", tissue_record)
        if loop_record is not None:
            _write_json(root / "loop.json", loop_record)
        numeric = read_json(root / "snapshot/manifest.json")
        if numeric["source_hashes"] != source_hashes() or (
            expected_sources is not None and numeric["source_hashes"] != expected_sources
        ):
            raise ConfigError("Checkpoint source changed during paired publication")
        manifest = dict(
            kind=kind,
            complete=True,
            snapshot_identity=numeric["manifest_sha256"],
            spec_sha256=numeric["spec_sha256"],
            clock=numeric["clock"],
            **_stream_identity(stream, record),
            files={name: _sha(root / name) for name in sorted(files)},
        )
        if component is not None:
            manifest.update(
                component_identity=component["identity"],
                component_clock=_component_clock(component_state),
            )
        if tissue_record is not None:
            manifest["tissue_binding_identity"] = tissue_record["identity"]
        if loop_record is not None:
            manifest["loop_cursor_identity"] = loop_record["identity"]
        # The ordinary writer closes its files. Sync them before committing the
        # association so a durable outer manifest never precedes its payloads.
        for name in files:
            with (root / name).open("rb") as payload:
                os.fsync(payload.fileno())
        _sync_directory(root / "snapshot")
        _write_json(root / "manifest.json", manifest | dict(identity=digest(manifest)))
        _sync_directory(root)
        _sync_directory(root.parent)
    except Exception as error:
        _write_json(root / "failure.json", dict(type=type(error).__name__, message=str(error)))
        raise
    return root


def load_physiology_checkpoint(
    directory,
    binding,
    *,
    expected_stream_id=None,
    expected_world_id=None,
    require_component=False,
    tissue_binding=None,
    require_tissue_binding=False,
    loop_cursor=None,
    require_loop_cursor=False,
):
    """Restore associated states together, refusing partial or mixed evidence.

    Binding is explicit and must match the saved perturbation layout exactly.
    Optional expected identifiers guard a caller's intended stream/world; they
    do not reinterpret native RNG as a world-keyed sampling law.
    require_component refuses the older RNG-only format. It never reconstructs
    missing material state by consuming a new initialization draw.
    Bound artifacts restore their tissue binding against the saved numeric spec.
    tissue_binding supplies an optional exact caller expectation; either that
    expectation or require_tissue_binding refuses older unbound formats.
    A saved loop cursor is always restored and checked against the complete
    numeric/component pair. require_loop_cursor or an expected loop_cursor
    refuses older formats without constructing a schedule from their clocks.
    """
    root = Path(directory).resolve()
    if any(
        type(value) is not bool
        for value in (require_component, require_tissue_binding, require_loop_cursor)
    ):
        raise ConfigError("Component/binding/cursor requirements must be explicit booleans")
    if (root / "failure.json").exists():
        raise ConfigError("Failed physiological checkpoint publication")
    manifest = read_json(root / "manifest.json")
    if not isinstance(manifest, dict):
        raise ConfigError("Invalid physiological checkpoint manifest fields")
    kind = manifest.get("kind")
    if type(kind) is not str or kind not in FORMATS:
        raise ConfigError("Invalid physiological checkpoint kind")
    managed = kind == LOOP_KIND
    bound = kind in (BOUND_KIND, LOOP_KIND)
    complete = kind != KIND
    fields, files = FORMATS[kind]
    if set(manifest) != fields:
        raise ConfigError("Invalid physiological checkpoint manifest fields")
    if (
        manifest["complete"] is not True
        or digest({key: value for key, value in manifest.items() if key != "identity"})
        != manifest["identity"]
    ):
        raise ConfigError("Invalid physiological checkpoint identity or completion marker")
    if require_component and not complete:
        raise ConfigError("Complete perturbation state is required; RNG-only checkpoint refused")
    if (require_tissue_binding or tissue_binding is not None) and not bound:
        raise ConfigError("Explicit tissue binding is required; unbound checkpoint refused")
    if (require_loop_cursor or loop_cursor is not None) and not managed:
        raise ConfigError("Explicit loop cursor is required; unmanaged checkpoint refused")
    if not isinstance(manifest["files"], dict) or set(manifest["files"]) != files:
        raise ConfigError("Invalid physiological checkpoint file inventory")
    present = {str(path.relative_to(root)) for path in root.rglob("*") if path.is_file()}
    if present != files | {"manifest.json"}:
        raise ConfigError("Physiological checkpoint has missing or extra artifacts")
    for name, expected in manifest["files"].items():
        path = root / name
        if not path.resolve().is_relative_to(root) or _sha(path) != expected:
            raise ConfigError("Physiological checkpoint payload changed: " + name)
    for field in ("world_id", "next_tick"):
        if type(manifest[field]) is not int or not 0 <= manifest[field] < 2**64:
            raise ConfigError("Invalid physiological checkpoint " + field)
    if expected_stream_id is not None and (
        not isinstance(expected_stream_id, str)
        or not expected_stream_id
        or manifest["stream_id"] != expected_stream_id
    ):
        raise ConfigError("Physiological checkpoint belongs to another stream")
    if expected_world_id is not None and (
        type(expected_world_id) is not int or manifest["world_id"] != expected_world_id
    ):
        raise ConfigError("Physiological checkpoint belongs to another world")
    record = read_json(root / "stream.json")
    stream = streams.restore_stream(record, binding)
    if any(manifest[key] != value for key, value in _stream_identity(stream, record).items()):
        raise ConfigError("Physiological checkpoint stream/clock association disagrees")
    component = None
    if complete:
        component_record = read_json(root / "component.json")
        component = _restore_component(component_record, binding, stream)
        if manifest["component_identity"] != component_record["identity"] or digest(
            manifest["component_clock"]
        ) != digest(_component_clock(component)):
            raise ConfigError("Complete perturbation state/clock association disagrees")
    snapshot = load_snapshot(root / "snapshot")
    if (
        manifest["snapshot_identity"] != snapshot.fingerprint
        or manifest["spec_sha256"] != snapshot.spec.fingerprint
        or digest(manifest["clock"]) != digest(_clock(snapshot.checkpoint))
    ):
        raise ConfigError("Physiological checkpoint numeric/clock association disagrees")
    restored_binding = None
    if bound:
        from cells.core import physiology_tissue_binding as tissue

        binding_record = read_json(root / "binding.json")
        restored_binding = _restore_tissue_binding(
            binding_record, snapshot.spec, binding, component
        )
        if manifest["tissue_binding_identity"] != restored_binding.identity:
            raise ConfigError("Physiological tissue binding association disagrees")
        if tissue_binding is not None:
            expected = tissue.binding_record(tissue_binding)
            _restore_tissue_binding(expected, snapshot.spec, binding, component)
            if expected != binding_record:
                raise ConfigError("Physiological checkpoint belongs to another tissue binding")
    restored_cursor = None
    if managed:
        from cells.core import physiology_tissue_loop as loop

        loop_record = read_json(root / "loop.json")
        restored_cursor = _restore_loop_cursor(
            loop_record, snapshot.spec, snapshot.checkpoint, restored_binding, component
        )
        if manifest["loop_cursor_identity"] != loop_record["identity"]:
            raise ConfigError("Physiological loop cursor association disagrees")
        if loop_cursor is not None:
            expected = loop.cursor_record(loop_cursor)
            _restore_loop_cursor(
                expected, snapshot.spec, snapshot.checkpoint, restored_binding, component
            )
            if expected != loop_record:
                raise ConfigError("Physiological checkpoint belongs to another loop cursor")
    return PhysiologyCheckpoint(
        snapshot, stream, manifest["identity"], component, restored_binding, restored_cursor
    )


def _operation_source(source_directory, directory, binding, **requirements):
    target = Path(directory)
    if target.exists() or target.is_symlink():
        raise FileExistsError("Physiological checkpoint destination already exists: " + str(target))
    original_sources = source_hashes()
    source = load_physiology_checkpoint(
        source_directory,
        binding,
        require_component=True,
        require_tissue_binding=True,
        **requirements,
    )
    if source_hashes() != original_sources:
        raise ConfigError("Checkpoint source changed while restoring the tissue operation")
    return source, original_sources


def advance_tissue_checkpoint(
    source_directory,
    directory,
    binding,
    *,
    expected_stream_id=None,
    expected_world_id=None,
    tissue_binding=None,
    end_time_s=None,
):
    """Restore, attempt one tissue interval, then publish a new bound pair.

    Requires the complete tissue-bound format and its ordinary source/runtime
    checks. The component's current passive permeability is held throughout
    exactly the next original EventGrid interval. Its six buffers, clock,
    controls, random state and draw count remain unchanged. No component loop
    or scheduled-buffer finalization is inferred from the numeric clock.

    Return the TissueStepResult after successful publication. Numerical refusal
    propagates TissueStepRejected with its raw trial and leaves no destination;
    publication errors retain the existing writer's failure artifacts. Source
    files are never changed. An existing destination refuses before stepping.
    """
    from cells.core import physiology_tissue_step as tissue

    source, original_sources = _operation_source(
        source_directory,
        directory,
        binding,
        expected_stream_id=expected_stream_id,
        expected_world_id=expected_world_id,
        tissue_binding=tissue_binding,
    )
    if source.loop_cursor is not None:
        raise ConfigError("Loop-managed checkpoint requires the complete-loop operation")
    result = tissue.advance(
        source.snapshot.spec,
        source.snapshot.checkpoint,
        source.tissue_binding,
        source.component_state,
        end_time_s=end_time_s,
    )
    write_physiology_checkpoint(
        directory,
        source.snapshot.spec,
        result.checkpoint,
        source.stream,
        result.binding.component,
        component_state=result.component,
        tissue_binding=result.binding,
        expected_source_hashes=original_sources,
    )
    return result


def initialise_loop_checkpoint(
    source_directory,
    directory,
    binding,
    *,
    loop_index=0,
    expected_stream_id=None,
    expected_world_id=None,
    tissue_binding=None,
):
    """Explicitly associate an existing bound pair with a nominal-loop cursor.

    This performs no component call, numeric step, draw or schedule finalization.
    Existing loop-managed checkpoints refuse reinitialization. Return the new
    cursor after publication; no partial-loop cursor is inferred from clocks.
    """
    from cells.core import physiology_tissue_loop as loop

    source, original_sources = _operation_source(
        source_directory,
        directory,
        binding,
        expected_stream_id=expected_stream_id,
        expected_world_id=expected_world_id,
        tissue_binding=tissue_binding,
    )
    if source.loop_cursor is not None:
        raise ConfigError("Physiological checkpoint already has a loop cursor")
    cursor = loop.initialise(
        source.snapshot.spec,
        source.snapshot.checkpoint,
        source.tissue_binding,
        source.component_state,
        loop_index=loop_index,
    )
    write_physiology_checkpoint(
        directory,
        source.snapshot.spec,
        source.snapshot.checkpoint,
        source.stream,
        source.tissue_binding.component,
        component_state=source.component_state,
        tissue_binding=source.tissue_binding,
        loop_cursor=cursor,
        expected_source_hashes=original_sources,
    )
    return cursor


def advance_loop_checkpoint(
    source_directory,
    directory,
    binding,
    *,
    expected_stream_id=None,
    expected_world_id=None,
    tissue_binding=None,
    loop_cursor=None,
):
    """Restore one managed pair and publish only a complete nominal-loop result.

    The core bridge stages one component call and all original tissue/control
    substeps. A rejection retains the proposed component/RNG and numerical
    trials and creates no destination. Successful publication commits the
    numeric endpoint, component and cursor together. Return its LoopResult.
    """
    from cells.core import physiology_tissue_loop as loop

    source, original_sources = _operation_source(
        source_directory,
        directory,
        binding,
        expected_stream_id=expected_stream_id,
        expected_world_id=expected_world_id,
        tissue_binding=tissue_binding,
        loop_cursor=loop_cursor,
        require_loop_cursor=True,
    )
    result = loop.advance(
        source.snapshot.spec,
        source.snapshot.checkpoint,
        source.tissue_binding,
        source.component_state,
        source.loop_cursor,
    )
    write_physiology_checkpoint(
        directory,
        source.snapshot.spec,
        result.checkpoint,
        result.component.stream,
        result.binding.component,
        component_state=result.component,
        tissue_binding=result.binding,
        loop_cursor=result.cursor,
        expected_source_hashes=original_sources,
    )
    return result
