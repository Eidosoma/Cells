"""The continuity probe: does a resume under another source run the same programs on the same
inputs? (docs/CHECKPOINT_CONTINUITY_DESIGN.md, sections 3.1 and 4.2.)

First landing: the vector-windows path, cohort snapshots of CPU definitions with jit: true.
Anything else answers cannot_decide, and the resume is refused.

- **One process per source tree**, out of process, as
  ``PYTHONPATH=<tree>/src:<tool root> python -m validation.continuity.probe run ...``.
  validation/continuity/admit.py runs it under the checkpoint's tree S0 and the resuming tree
  S1, and compares the outputs.
- **It uses only APIs that S0 already has.** The first real checkpoints predate this work, so
  it never imports cells.continuity. A tree that lacks one of its entry points answers
  cannot_decide.
- **It reads the checkpoint without the two identity comparisons**, keeping every other check
  of batch_io.load_batch_snapshot, and it never continues a run. It is exempt from the bypass
  guard for that reason (tests/unit/test_continuity_bypass.py). It records this tree's
  source_hashes(); under S0 they must reproduce the manifest's map.

The parts, each a digest record in OUT/summary.json (texts under OUT/texts, rounds in
OUT/rounds.jsonl):
  P0  entry capture. iter_vector_windows runs from the checkpoint, with its jitted window
      replaced, where the path looks it up (core/vector_windows._compiled_vector_window), by a
      recorder. At .lower() the recorder keeps the arguments, the static functions, the jaxpr
      with every closed-over constant and the StableHLO; at .compile() it keeps the compile
      arguments and stops. No model program compiles or executes.
  P   that program, and the step-level texts (checked step, device checks) of each distinct
      definition, at the checkpoint's own state and clock.
  B   every array the path binds over the remaining horizon: the resident inputs; each round
      from the path's own round builder, iterated as its driving loop does; and per
      definition the remaining grid, integration steps and controls (digested in chunks),
      the observation times, and the initial state and layout. P0's arguments must equal B's
      first round.
  H   check_values (with step counts), observe_history, the windowed observation-continuity
      check and summarize, replayed on every saved state given (the checkpoint's by default).
  O   the overlap. The path itself runs from the checkpoint on CPU for N rounds. Each
      executable call's bound arguments are recorded where launch looks the executable up
      (core/vector_windows.compile_window), and each round's endpoint states, observations,
      device-check diagnostics, clock and event index are digested. The arguments are
      compared with B's rounds. N is at least two rounds, past the next event and the next
      observation time after the checkpoint, or the whole remaining horizon if shorter.

Usage:
  probe.py run --checkpoint SNAP --out OUT --window-steps N --recording R
               [--parts P,B,H,O] [--overlap-rounds N] [--saved-state SNAP ...]
Exit status: 0 probed, 3 cannot_decide, 4 refused by a loader check under this tree.
"""

import argparse
import hashlib
import importlib
import json
import resource
import sys
import time
from bisect import bisect_left
from pathlib import Path
from types import SimpleNamespace

import numpy as np

KIND = "cells.continuity_probe@1"
PATH = "vector_windows"
COHORT = "cells_independent_world_checkpoint"
CHUNK = 65536  # Steps per chunk of the remaining-horizon digests: bounded host memory.
PARTS = ("P", "B", "H", "O")
# Every entry point the probe drives; a tree without one cannot be decided (section 4.2).
ENTRY_POINTS = {
    "cells.core.vector_windows": (
        "plan_vector_windows",
        "iter_vector_windows",
        "_compiled_vector_window",
        "_vector_window",
        "compile_window",
        "resident_inputs",
        "_initial_checkpoints",
        "_Round",
        "require_device_checks",
    ),
    "cells.core.runner": ("integration_steps", "validate_checkpoint", "check_steps"),
    "cells.core.schedule": ("control_values",),
    "cells.core.windows": ("WindowPolicy", "_observation_tail"),
    "cells.core.grid": ("EventGrid",),
    "cells.core.state": ("Checkpoint", "initialise"),
    "cells.core.batch": ("parse_batch", "checkpoint_batch_limits"),
    "cells.core.devices": ("execution_device",),
    "cells.core.specs": ("ConfigError", "digest", "parse_spec", "read_json", "_fields"),
    "cells.io": ("source_hashes", "runtime_identity"),
    "cells.models.registry": ("get_model",),
}
MODEL_PROTOCOL = ("STATE_TYPE", "parameters", "check_values", "observe_history", "summarize")
T0 = time.perf_counter()


class CannotDecide(Exception):
    """Outside what this probe decides: the resume is refused (section 4.2)."""


class Refused(Exception):
    """The checkpoint fails a loader check under this tree."""


# ---------------------------------------------------------------- digests (exact, host only)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def arr(value):
    a = np.ascontiguousarray(np.asarray(value))
    return dict(dtype=str(a.dtype), shape=list(a.shape), sha256=sha(a.tobytes()))


def tree(value):
    import jax

    leaves, structure = jax.tree.flatten(value)
    return dict(structure=str(structure), leaves=[arr(v) for v in leaves])


def exact(value):
    """A JSON form that keeps every bit: floats as float.hex, arrays as digests."""
    if isinstance(value, dict):
        return {str(k): exact(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [exact(v) for v in value]
    if isinstance(value, (bool, type(None), str, int)):
        return value
    if isinstance(value, float):
        return {"float": value.hex()}
    if isinstance(value, np.generic) and np.ndim(value) == 0:
        return exact(value.item())
    if isinstance(value, np.ndarray) or hasattr(value, "shape"):
        return arr(value)
    return {"repr": repr(value)}


def canonical(value):
    return json.dumps(exact(value), sort_keys=True, separators=(",", ":"))


def error(exc):
    return f"{type(exc).__name__}: {exc}"[:1000]


def peak_mb():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


def write_json(path, value):
    with Path(path).open("x") as handle:
        json.dump(value, handle, indent=1, sort_keys=True, allow_nan=False)
        handle.write("\n")


def all_consts(closed):
    """Every constant of a closed jaxpr and of the closed jaxprs inside its equations."""
    # A JAX 0.11 closed jaxpr's .jaxpr may be itself, so a visited object still has its
    # equations walked; constants are deduplicated by id.
    found, seen, taken = [], set(), set()

    def visit(value):
        if isinstance(value, (tuple, list)):
            for item in value:
                visit(item)
            return
        if not (hasattr(value, "eqns") or hasattr(value, "jaxpr")) or id(value) in seen:
            return
        seen.add(id(value))
        for const in getattr(value, "consts", None) or ():
            if id(const) not in taken:
                taken.add(id(const))
                found.append(const)
        inner = getattr(value, "jaxpr", None)
        if inner is not None and inner is not value:
            visit(inner)
        for eqn in getattr(value, "eqns", None) or ():
            for param in eqn.params.values():
                visit(param)

    visit(closed)
    return found


def program(name, closed, hlo, out):
    """One traced program: its texts saved, their digests and every constant's digest."""
    text = str(closed)
    (out / "texts").mkdir(parents=True, exist_ok=True)
    (out / "texts" / f"{name}.jaxpr.txt").write_text(text)
    if hlo is not None:
        (out / "texts" / f"{name}.stablehlo.txt").write_text(hlo)
    return dict(
        jaxpr_sha256=sha(text.encode()),
        jaxpr_chars=len(text),
        consts=[arr(c) for c in all_consts(closed)],
        stablehlo_sha256=None if hlo is None else sha(hlo.encode()),
        stablehlo_chars=None if hlo is None else len(hlo),
    )


def static_name(value):
    module = getattr(value, "__module__", None) or type(value).__module__
    name = getattr(value, "__qualname__", None) or type(value).__qualname__
    return f"{module}.{name}"


def arguments(args, kwargs):
    """Digests of a call's arguments: arrays by bytes, static functions by name."""
    import jax

    def one(value):
        if callable(value) and not hasattr(value, "shape"):
            return dict(static=static_name(value))
        if value is None or isinstance(value, (bool, int, float, str)):
            return dict(static=repr(value))
        return tree(jax.device_get(value))

    return dict(args=[one(a) for a in args], kwargs={k: one(v) for k, v in sorted(kwargs.items())})


# ---------------------------------------------------------------- the tree and the checkpoint


def require_entry_points():
    missing = []
    for name, attributes in ENTRY_POINTS.items():
        try:
            module = importlib.import_module(name)
        except ImportError as exc:
            missing.append(f"{name} ({error(exc)})")
            continue
        missing += [f"{name}.{a}" for a in attributes if not hasattr(module, a)]
    if missing:
        raise CannotDecide("the tree lacks the probe's entry points: " + ", ".join(missing))


def read_scalar(path):
    """io.load_snapshot without its two identity comparisons; every other check is kept."""
    import jax

    from cells.core.devices import execution_device
    from cells.core.runner import validate_checkpoint
    from cells.core.specs import ConfigError, digest, parse_spec, read_json
    from cells.core.state import Checkpoint, initialise
    from cells.models.registry import get_model

    path = Path(path)
    manifest = read_json(path / "manifest.json")
    fields = {
        "schema_version",
        "kind",
        "spec",
        "spec_sha256",
        "clock",
        "random_state",
        "runtime",
        "source_hashes",
        "state_sha256",
        "manifest_sha256",
    }
    if not isinstance(manifest, dict) or set(manifest) != fields:
        raise ConfigError("Invalid checkpoint manifest fields")
    fingerprint = manifest.pop("manifest_sha256")
    if digest(manifest) != fingerprint:
        raise ConfigError("Checkpoint manifest checksum mismatch")
    if type(manifest["schema_version"]) is not int or manifest["schema_version"] != 1:
        raise ConfigError("Unsupported checkpoint schema")
    if manifest["kind"] != "cells_complete_numerical_checkpoint":
        raise ConfigError("Not a complete Cells numerical checkpoint")
    if manifest["random_state"] is not None:
        raise ConfigError("These deterministic models have no random state")
    spec = parse_spec(manifest["spec"])
    model = get_model(spec.model)
    if spec.fingerprint != manifest["spec_sha256"]:
        raise ConfigError("Checkpoint specification checksum mismatch")
    if sha((path / "state.npz").read_bytes()) != manifest["state_sha256"]:
        raise ConfigError("Checkpoint state checksum mismatch")
    clock = manifest["clock"]
    if not isinstance(clock, dict) or set(clock) != {"time", "step_index", "event_index"}:
        raise ConfigError("Invalid checkpoint clock fields")
    if isinstance(clock["time"], bool) or not isinstance(clock["time"], (int, float)):
        raise ConfigError("Invalid checkpoint time")
    initial = initialise(spec)
    kind = type(initial.layout)
    with np.load(path / "state.npz", allow_pickle=False) as archive:
        if set(archive.files) != set(model.STATE_TYPE._fields + kind._fields):
            raise ConfigError("Invalid checkpoint state fields")
        state = model.STATE_TYPE(*(archive[name] for name in model.STATE_TYPE._fields))
        layout = kind(*(archive[name] for name in kind._fields))
    checkpoint = Checkpoint(state, layout, **clock)
    validate_checkpoint(spec, checkpoint, initial=initial)
    device = execution_device(spec.execution.backend)
    checkpoint = Checkpoint(jax.device_put(state, device), jax.device_put(layout, device), **clock)
    return spec, checkpoint, {**manifest, "manifest_sha256": fingerprint}


def require_scope(spec):
    """The first landing's definitions: CPU, jit: true, no projective block (section 3.1)."""
    for world in spec.worlds:
        s = world.simulation
        if s.execution.backend != "cpu":
            raise CannotDecide(
                f"world {world.world_id} is a {s.execution.backend} definition; the first "
                "landing probes CPU definitions"
            )
        if s.execution.jit is not True:
            raise CannotDecide(f"world {world.world_id} is a jit: false definition")
        if getattr(s, "projective", None) is not None:
            raise CannotDecide(f"world {world.world_id} is a projective definition")


def read_cohort(path):
    """batch_io.load_batch_snapshot without its two identity comparisons.

    Returns (spec, checkpoints, manifest, children): the parsed cohort, its checkpoints by
    world ID, the cohort manifest and each child's manifest.
    """
    from cells.core.batch import checkpoint_batch_limits, parse_batch
    from cells.core.specs import ConfigError, _fields, digest, read_json

    path = Path(path).resolve()
    raw = read_json(path / "manifest.json")
    if isinstance(raw, dict) and raw.get("kind") != COHORT:
        raise CannotDecide(
            f"a {raw.get('kind')} names no cohort; the first landing probes cohort snapshots "
            "on the vector-windows path"
        )
    manifest = _fields(
        raw,
        {
            "schema_version",
            "kind",
            "spec",
            "spec_sha256",
            "runtime",
            "source_hashes",
            "worlds",
            "manifest_sha256",
        },
        "batch checkpoint manifest",
    )
    fingerprint = manifest.pop("manifest_sha256")
    if digest(manifest) != fingerprint:
        raise ConfigError("Batch checkpoint manifest checksum mismatch")
    if type(manifest["schema_version"]) is not int or manifest["schema_version"] != 1:
        raise ConfigError("Unsupported batch checkpoint schema")
    spec, _ = checkpoint_batch_limits(parse_batch(manifest["spec"]))
    require_scope(spec)
    if manifest["spec_sha256"] != spec.fingerprint:
        raise ConfigError("Batch checkpoint specification checksum mismatch")
    records = manifest["worlds"]
    if not isinstance(records, list) or len(records) != len(spec.worlds):
        raise ConfigError("Batch checkpoint world inventory differs")
    checkpoints, children = {}, {}
    for world, record in zip(spec.worlds, records, strict=True):
        _fields(record, {"world_id", "path", "snapshot_sha256"}, "checkpoint world")
        if type(record["world_id"]) is not int or record["world_id"] != world.world_id:
            raise ConfigError("Batch checkpoint world identity/order differs")
        if record["path"] != f"world-{world.world_id}":
            raise ConfigError("Invalid batch checkpoint child path")
        child = (path / record["path"]).resolve()
        if not child.is_relative_to(path):
            raise ConfigError("Batch checkpoint child escapes its directory")
        simulation, checkpoint, saved = read_scalar(child)
        if simulation != world.simulation or saved["manifest_sha256"] != record["snapshot_sha256"]:
            raise ConfigError("Batch checkpoint child specification/identity differs")
        checkpoints[world.world_id], children[world.world_id] = checkpoint, saved
    return spec, checkpoints, {**manifest, "manifest_sha256": fingerprint}, children


# ---------------------------------------------------------------- P0 and P


class _Stop(Exception):
    """Raised at .compile(): the path's program is captured; nothing runs."""


class _Recorder:
    """The jitted window, where the path looks it up: records its lowering, then stops."""

    def __init__(self, real, record, out):
        self.real, self.record, self.out = real, record, out

    def lower(self, *args, **kwargs):
        traced = self.real.trace(*args, **kwargs)
        hlo = traced.lower().as_text()
        self.record.update(
            arguments=arguments(args, kwargs),
            program=program("vector_window", traced.jaxpr, hlo, self.out),
        )
        return _Lowered(self.record)


class _Lowered:
    def __init__(self, record):
        self.record = record

    def compile(self, *args, **kwargs):
        self.record["compile_arguments"] = repr((args, sorted(kwargs.items())))
        raise _Stop


def capture_entry(vw, spec, policy, checkpoints, out):
    """P0: the program the vector-windows path compiles, from its own entry point."""
    record, real = {}, vw._compiled_vector_window
    vw._compiled_vector_window = _Recorder(real, record, out)
    try:
        windows = vw.iter_vector_windows(spec, policy, checkpoints)
        try:
            next(windows)
        except _Stop:
            pass
        except StopIteration as exc:
            raise CannotDecide("no round remains after the checkpoint") from exc
        else:
            raise CannotDecide("the vector-windows path ran a round without lowering its program")
    finally:
        vw._compiled_vector_window = real
    if "compile_arguments" not in record:
        raise CannotDecide("the vector-windows path did not reach .compile()")
    return record


def step_texts(spec, checkpoints, out):
    """P: crossrev's step-level texts of each distinct definition, at its checkpoint."""
    import jax
    import jax.numpy as jnp

    from cells.core.schedule import control_values
    from cells.models.registry import get_model

    texts = {}
    for world in spec.worlds:
        s = world.simulation
        if s.fingerprint in texts:
            continue
        model, checkpoint = get_model(s.model), checkpoints[world.world_id]
        layout = type(checkpoint.layout)(*(np.asarray(v) for v in checkpoint.layout))
        table = control_values(s, np.array([float(checkpoint.time)]))
        control = type(table)(*(np.asarray(v[0]) for v in table))
        # Crossrev's arguments (composite_crossrev): every leaf an array; parameters from the
        # host layout, as resident_inputs builds them.
        state, control, params, active = jax.tree.map(
            jnp.asarray, (checkpoint.state, control, model.parameters(s, layout), layout.active)
        )
        dt = jnp.asarray(s.execution.dt)
        constants = model.device_check_constants(s)
        stepped = jax.make_jaxpr(model.checked_step)(state, dt, control, params, active)

        def checks(y, q, model=model, constants=constants, step=checkpoint.step_index):
            return model.device_checks(y, y, q, constants, step)  # Constants closed over.

        checked = jax.make_jaxpr(checks)(state, params)
        label = f"world{world.world_id}"
        texts[s.fingerprint] = dict(
            checked_step=program(f"{label}.checked_step", stepped, None, out),
            device_checks=program(f"{label}.device_checks", checked, None, out),
        )
    return texts


# ---------------------------------------------------------------- B


def iterate_rounds(vw, plan, starts, ids):
    """Each round's host inputs from the path's own builder, as its driving loop builds them.

    The loop builds a round with the clocks of the round before it, and only then advances
    them (a finished world's start lags a round: core/vector_windows._Round), so this does too.
    """
    grids = [
        plan.worlds[g[0]].grid.windows(plan.worlds[g[0]].start_step, plan.policy.window_steps)
        for g in plan.groups
    ]
    index = [
        bisect_left(p.spec.experiment.observation_times, starts[i].time)
        for i, p in zip(ids, plan.worlds, strict=True)
    ]
    clocks = {i: SimpleNamespace(time=starts[i].time) for i in ids}
    current = vw._Round(plan, grids, dict(clocks), ids, index, True)
    if not any(current.live):
        return
    while current is not None:
        yield current
        following = vw._Round(plan, grids, dict(clocks), ids, current.stops, False)
        for i, identity in enumerate(ids):
            if current.live[i]:
                clocks[identity] = SimpleNamespace(time=float(current.times[i][-1]))
        current = following if any(following.live) else None


def round_record(index, current):
    return dict(
        round=index,
        arrays=[tree(a) for a in current.arrays],
        times=[arr(t) for t in current.times],
        clocks=[
            dict(start=float(t[0]), end=float(t[-1]), steps=len(t) - 1, live=bool(live))
            for t, live in zip(current.times, current.live, strict=True)
        ],
        observed=[exact(list(map(float, c))) for c in current.chosen],
        rows=[list(map(int, r)) for r in current.rows],
        stops=list(map(int, current.stops)),
    )


def horizon_bindings(s, checkpoint):
    """Per definition: the remaining grid, its integration steps and controls, in chunks."""
    import jax

    from cells.core.grid import EventGrid
    from cells.core.runner import integration_steps
    from cells.core.schedule import control_values
    from cells.core.state import initialise

    grid = EventGrid(s)
    start, last = checkpoint.step_index, len(grid) - 1
    hashes = {"times": hashlib.sha256(), "steps": hashlib.sha256()}
    controls, structure = None, None
    for first in range(start, last, CHUNK):
        stop = min(first + CHUNK, last)
        times = np.fromiter((grid[i] for i in range(first, stop + 1)), dtype=np.float64)
        hashes["times"].update(np.ascontiguousarray(times[:-1]).tobytes())
        hashes["steps"].update(np.ascontiguousarray(integration_steps(s, times)).tobytes())
        leaves, treedef = jax.tree.flatten(control_values(s, times[:-1]))
        if controls is None:
            controls, structure = [hashlib.sha256() for _ in leaves], str(treedef)
        for digest, leaf in zip(controls, leaves, strict=True):
            digest.update(np.ascontiguousarray(np.asarray(leaf)).tobytes())
    hashes["times"].update(np.float64(grid[last]).tobytes())
    initial = initialise(s)
    return dict(
        remaining_steps=last - start,
        times_sha256=hashes["times"].hexdigest(),
        integration_steps_sha256=hashes["steps"].hexdigest(),
        controls=dict(structure=structure, leaves_sha256=[d.hexdigest() for d in controls or ()]),
        observation_times=exact(list(s.experiment.observation_times)),
        initial_state=tree(initial.state),
        initial_layout=tree(initial.layout),
    )


def bindings(vw, spec, policy, checkpoints, out):
    """B: everything the path binds over the remaining horizon, from its own builders."""
    import jax

    from cells.core.devices import execution_device
    from cells.models.registry import get_model

    model = get_model(spec.worlds[0].simulation.model)
    device = execution_device(spec.worlds[0].simulation.execution.backend)
    plan = vw.plan_vector_windows(spec, policy, checkpoints)
    starts = vw._initial_checkpoints(plan, checkpoints)
    ids = [w.world_id for w in spec.worlds]
    state, params, active, constants, _ = vw.resident_inputs(plan, starts, model, device)
    rounds, first = [], None
    with (out / "rounds.jsonl").open("x") as stream:
        for index, current in enumerate(iterate_rounds(vw, plan, starts, ids)):
            record = round_record(index, current)
            rounds.append(record)
            stream.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
            if index == 0:
                args = (state, *jax.device_put(current.arrays, device), params, active, constants)
                statics = dict(
                    step=model.checked_step, checks=model.device_checks, rows=plan.observation_rows
                )
                first = arguments(args, statics)
    definitions = {}
    for world in spec.worlds:
        s = world.simulation
        key = f"{s.fingerprint}@{checkpoints[world.world_id].step_index}"
        if key not in definitions:
            definitions[key] = horizon_bindings(s, checkpoints[world.world_id])
    record = dict(
        plan=dict(
            width=plan.width,
            control_rows=plan.control_rows,
            observation_rows=plan.observation_rows,
            groups=[list(g) for g in plan.groups],
        ),
        resident=dict(
            state=tree(state), params=tree(params), active=tree(active), constants=tree(constants)
        ),
        definitions=definitions,
        rounds=len(rounds),
        rounds_sha256=sha((out / "rounds.jsonl").read_bytes()),
        minimum_overlap=minimum_overlap(spec, checkpoints, rounds),
    )
    return record, rounds, first


def minimum_overlap(spec, checkpoints, rounds):
    """The fewest rounds (at least two) past each world's next event and next observation.

    A round passes an event when it ends after the event time (the step from the event time
    takes the new schedule), and an observation when it ends at or after it. The whole
    remaining horizon if shorter.
    """
    needed = min(2, len(rounds))
    for i, world in enumerate(spec.worlds):
        s, start = world.simulation, float(checkpoints[world.world_id].time)
        targets = [
            (min((c.time for c in s.experiment.changes if c.time > start), default=None), False),
            (min((t for t in s.experiment.observation_times if t > start), default=None), True),
        ]
        for target, inclusive in targets:
            if target is None:
                continue
            reach = [
                k
                for k, r in enumerate(rounds)
                if r["clocks"][i]["live"]
                and (
                    r["clocks"][i]["end"] >= target if inclusive else r["clocks"][i]["end"] > target
                )
            ]
            needed = max(needed, (reach[0] + 1) if reach else len(rounds))
    return min(needed, len(rounds))


# ---------------------------------------------------------------- H


def host_replay(states):
    """H: the host's acceptance and observation code on every saved state, under this tree.

    states is [(label, world ID, definition, checkpoint)]. Per world, in time order, the
    windowed observation-continuity check joins each state's observation to the previous one.
    A part that raises is recorded as {"raised": message}: it repeats or not under the other
    tree, but it compares nothing, so admit.py cannot decide on it (host_replay_errors).
    """
    from cells.core.grid import EventGrid
    from cells.core.runner import check_steps
    from cells.core.windows import _observation_tail
    from cells.models.registry import get_model

    rows, previous = [], {}
    unique = {(w, c.step_index): (label, w, s, c) for label, w, s, c in states}
    for label, world_id, s, checkpoint in sorted(
        unique.values(), key=lambda r: (r[1], r[3].step_index)
    ):
        model = get_model(s.model)
        history = model.STATE_TYPE(*(np.asarray(v)[None] for v in checkpoint.state))
        layout = type(checkpoint.layout)(*(np.asarray(v) for v in checkpoint.layout))
        row = dict(state=label, world=world_id, step_index=checkpoint.step_index)
        diagnostics = {}
        try:
            diagnostics = model.check_values(
                history, s, **check_steps(model, checkpoint.step_index, 1)
            )
            row["check_values"] = exact(diagnostics)
        except Exception as exc:  # noqa: BLE001  (recorded; admit.py cannot decide on it)
            row["check_values"] = dict(raised=error(exc))
        t, observed = float(checkpoint.time), None
        try:
            observed = model.observe_history(np.array([t]), history, layout, [t], s)
            row["observe_history"] = {k: arr(v) for k, v in sorted(vars(observed).items())}
        except Exception as exc:  # noqa: BLE001
            row["observe_history"] = dict(raised=error(exc))
        if observed is not None:
            try:
                tail = _observation_tail(model, s, observed, previous.get(world_id), EventGrid(s))
                previous[world_id] = tail
                row["observation_tail"] = exact(tail)
            except Exception as exc:  # noqa: BLE001
                row["observation_tail"] = dict(raised=error(exc))
        try:
            row["summarize"] = sha(
                json.dumps(
                    model.summarize(history, diagnostics, s), sort_keys=True, default=repr
                ).encode()
            )
        except Exception as exc:  # noqa: BLE001
            row["summarize"] = dict(raised=error(exc))
        rows.append(row)
    return rows


# ---------------------------------------------------------------- O


class _Recorded:
    """The vector window's executable, recording each call's bound arguments.

    args = (state, steps, counts, table, index, slots, origin, params, active, constants): the
    carried state, the six round arrays the host built and the three resident trees.
    """

    def __init__(self, executable, calls):
        self.executable, self.calls = executable, calls

    def __call__(self, *args):
        import jax

        self.calls.append(
            dict(
                state=tree(jax.device_get(args[0])),
                arrays=[tree(jax.device_get(a)) for a in args[1:7]],
                resident=tree(jax.device_get(args[7:])),
            )
        )
        return self.executable(*args)

    def __getattr__(self, name):
        return getattr(self.executable, name)


def window_record(window):
    worlds = {}
    for identity, checkpoint in sorted(window.checkpoints.items()):
        found = window.observations.get(identity)
        worlds[str(identity)] = dict(
            time=float(checkpoint.time).hex(),
            step_index=checkpoint.step_index,
            event_index=checkpoint.event_index,
            state=tree(checkpoint.state),
            observations=None
            if found is None
            else {k: arr(v) for k, v in sorted(vars(found).items())},
            diagnostics=exact(window.diagnostics.get(identity)),
        )
    return dict(round=window.index, worlds=worlds)


def overlap(vw, spec, policy, checkpoints, wanted, own):
    """O: the path itself for the first ``wanted`` rounds of the resume, bitwise."""
    calls, outputs, real = [], [], vw.compile_window

    def recording(model, args, rows):  # Where launch() looks it up: the module attribute.
        compiled, seconds, memory = real(model, args, rows)
        return _Recorded(compiled, calls), seconds, memory

    vw.compile_window = recording
    failure = None
    try:
        windows = vw.iter_vector_windows(spec, policy, checkpoints)
        for window in windows:
            outputs.append(window_record(window))
            if len(outputs) >= wanted:
                break
        windows.close()
    except Exception as exc:  # noqa: BLE001  (a refused resume is a result)
        failure = dict(error=error(exc), checks=list(getattr(exc, "checks", ()) or ()) or None)
    finally:
        vw.compile_window = real
    rows = [
        dict(call=k, equal=call["arrays"] == own[k]["arrays"])
        for k, call in enumerate(calls)
        if k < len(own)
    ]
    return dict(
        rounds=wanted,
        completed=len(outputs),
        calls=calls,
        outputs=outputs,
        failure=failure,
        arguments_equal_own_rounds=bool(rows)
        and len(calls) <= len(own)
        and all(r["equal"] for r in rows),
        own_round_rows=rows,
    )


# ---------------------------------------------------------------- the probe


def _probe(args, out, summary, parts):
    import cells
    from cells import io
    from cells.core import vector_windows as vw
    from cells.core.specs import digest
    from cells.core.windows import WindowPolicy
    from cells.models.registry import get_model

    sources = io.source_hashes()
    summary.update(
        tree=str(Path(cells.__file__).parent),
        source_hashes=sources,
        source_hashes_sha256=digest(sources),
        runtime=io.runtime_identity("cpu"),
    )
    tick = time.perf_counter()
    spec, checkpoints, manifest, children = read_cohort(args.checkpoint)
    saved = []
    for extra in args.saved_state:
        more, states, _, _ = read_cohort(extra)
        saved += [(str(extra), w.world_id, w.simulation, states[w.world_id]) for w in more.worlds]
    summary["timings"]["read_seconds"] = time.perf_counter() - tick
    summary["checkpoint"] = dict(
        path=str(Path(args.checkpoint).resolve()),
        format=manifest["kind"],
        manifest_sha256=manifest["manifest_sha256"],
        definitions={str(w.world_id): w.simulation.fingerprint for w in spec.worlds},
        clocks={str(i): children[i]["clock"] for i in sorted(children)},
        source_hashes_sha256=digest(manifest["source_hashes"]),
        children_share_cohort_identity=all(
            c["source_hashes"] == manifest["source_hashes"] and c["runtime"] == manifest["runtime"]
            for c in children.values()
        ),
    )
    summary["reproduces_manifest"] = sources == manifest["source_hashes"]
    model = get_model(spec.worlds[0].simulation.model)
    missing = [name for name in MODEL_PROTOCOL if not hasattr(model, name)]
    if missing:
        raise CannotDecide(f"the model lacks {missing}")
    try:
        vw.require_device_checks(model)
    except ValueError as exc:  # ConfigError: the model has no device checks.
        raise CannotDecide(error(exc)) from exc
    policy = WindowPolicy(args.window_steps, args.recording)
    if "P" in parts:
        tick = time.perf_counter()
        summary["P0"] = capture_entry(vw, spec, policy, checkpoints, out)
        summary["P"] = step_texts(spec, checkpoints, out)
        summary["timings"]["P_seconds"] = time.perf_counter() - tick
    tick = time.perf_counter()
    record, rounds, first = bindings(vw, spec, policy, checkpoints, out)
    summary["timings"]["B_seconds"] = time.perf_counter() - tick
    summary["horizon_rounds"] = len(rounds)
    summary["minimum_overlap"] = record["minimum_overlap"]
    if "B" in parts:
        summary["B"] = record
        if "P0" in summary:
            summary["B"]["first_round_equals_P0"] = summary["P0"]["arguments"] == first
    if "H" in parts:
        tick = time.perf_counter()
        states = [
            ("checkpoint", w.world_id, w.simulation, checkpoints[w.world_id]) for w in spec.worlds
        ]
        summary["H"] = dict(  # Saved cohort states: the checkpoint and each --saved-state.
            rows=host_replay(states + saved), saved_states=1 + len(args.saved_state)
        )
        summary["timings"]["H_seconds"] = time.perf_counter() - tick
    if "O" in parts:
        wanted = min(max(record["minimum_overlap"], args.overlap_rounds or 0), len(rounds))
        tick = time.perf_counter()
        summary["O"] = overlap(vw, spec, policy, checkpoints, wanted, rounds)
        summary["timings"]["O_seconds"] = time.perf_counter() - tick


def probe(args):
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    tool = Path(__file__).resolve()
    summary = dict(
        kind=KIND,
        status="probing",
        tool=dict(path=str(tool), sha256=sha(tool.read_bytes())),
        argv=sys.argv,
        path=PATH,
        policy=dict(window_steps=args.window_steps, recording=args.recording),
        parts=sorted(set(args.parts.split(","))),
        timings={},
    )
    parts = set(summary["parts"])
    if not parts <= set(PARTS):
        raise SystemExit(f"--parts takes {PARTS}")
    code = 0
    try:
        import jax

        jax.config.update("jax_enable_x64", True)
        require_entry_points()
        from cells.core.specs import ConfigError

        try:
            _probe(args, out, summary, parts)
        except ConfigError as exc:  # A loader or plan check refused it under this tree.
            raise Refused(error(exc)) from exc
        summary["status"] = "probed"
    except CannotDecide as exc:
        summary.update(status="cannot_decide", reason=str(exc))
        code = 3
    except Refused as exc:
        summary.update(status="refused", reason=str(exc))
        code = 4
    summary["timings"]["total_seconds"] = time.perf_counter() - T0
    summary["peak_rss_mb"] = peak_mb()
    write_json(out / "summary.json", summary)
    print(KIND, out, summary["status"], summary.get("reason") or "", flush=True)
    return code


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="probe one tree (the one on PYTHONPATH)")
    run.add_argument("--checkpoint", required=True, help="the cohort snapshot to resume")
    run.add_argument("--out", required=True, help="a new output directory")
    run.add_argument("--window-steps", type=int, required=True)
    run.add_argument("--recording", required=True, choices=("full", "observations", "checkpoints"))
    run.add_argument("--parts", default="P,B,H,O", help="any of P,B,H,O (default all)")
    run.add_argument("--overlap-rounds", type=int, default=0, help="at least the minimum N")
    run.add_argument(
        "--saved-state", action="append", default=[], help="another saved cohort state for H"
    )
    args = parser.parse_args(argv)
    return probe(args)


if __name__ == "__main__":
    sys.exit(main())
