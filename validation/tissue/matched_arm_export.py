"""Matched-arm export of the coupling operator's A5 world: four arms, four steps, typed streams.

docs/INVENTORY_COUPLING_DESIGN.md §4.4 (A5, Track R) and validation/tissue/
regulated_availability_references.py. One cell on a held bath with a K-leak population and a
neutral regulator X (D150's turnover), read at once on the population by
cells.operator.species_regulated_availability@1, as cells.model.resolved_pump_composite@1 over cells.model.resolved_pump_tissue@3. The
four arms hold the population's availability at 1 and differ only in the regulator's production
pulse over [0.2, 0.5) s (pulse_factor 10 or 1) and the coupling switch (1 or 0):

    regulated_pulse, regulated_no_pulse, disabled_pulse, disabled_no_pulse

each at dt 1, 0.5, 0.25 and 0.125 ms to 1 s, observed every 0.05 s: 16 definitions. This module is
a driver of the established runners (rr.engine_definition, cells.execution.windows.iter_windows,
cells.records.io snapshots, validation/coupling's R-cell reference); it adds no physics and no verdict.

Record times are the engine's own grid values, (k * stride) * dt (the dt study's grid_records):
a resolved-pump definition is refused at window planning if an observation time is not an
accepted integration boundary, and a decimal 0.35 is not one (0.35 is not 350 * 0.001 in float64).
The rows keep the engine's time values; the references are evaluated at the decimal times.

Evidence written under OUT (all paths in the records are relative to OUT):
* definitions/<arm>-<dt>.json and definitions.json: the exact raw definitions that are parsed,
  planned and executed (the run reads these files back);
* traces/engine-<arm>-<dt>.json (16), traces/reference-<arm>[-refined].json (8, from R-cell's
  `floor`: Radau at rtol 1e-10 and at rtol 1e-12 with atol / 1000), reference_provenance.json,
  reference_sources/;
* inventory.json (every compiled state field and observation column, from the regulated_pulse
  definition at the finest step) and the checks that the 16 compiled cases share it;
* restarts/ (six written checkpoints of regulated_pulse at the finest step, each continued in a
  fresh process) and windows/ (4- and 7-step windows), as raw typed streams with byte comparisons;
* duration/<S>s.json (separate probes), admission.json, execution_record.json, export_index.json.

Usage (python -m validation.tissue.matched_arm_export COMMAND OUT [options]):
  all OUT [--contract-sha256 H]     every stage below in order, each stage in its own process
  definitions | references | engine | compare | index OUT
  continue OUT --step K | windows OUT --steps N   (one fresh process each)
  duration OUT --seconds S          (separate from `all`)
A stage that fails writes OUT/failures/<stage>.failure.json and the next stages still run.
"""  # noqa: E501

import argparse
import ast
import hashlib
import json
import math
import os
import platform
import resource
import subprocess
import sys
import time
import traceback
from pathlib import Path

import numpy as np

from cells.definitions.specs import parse_spec
from cells.execution.grid import EventGrid
from cells.execution.windows import WindowPolicy, iter_windows, plan_windows, run_windowed
from cells.records.io import load_snapshot, write_snapshot
from cells.registry.models import get_model
from validation.coupling import cells_reference as rc
from validation.tissue import regulated_availability_dt_study as study
from validation.tissue import regulated_availability_references as rr

ROOT = Path(__file__).resolve().parents[2]
ARMS = {  # arm: (pulse_factor, coupling enabled)
    "regulated_pulse": (10.0, 1),
    "regulated_no_pulse": (1.0, 1),
    "disabled_pulse": (10.0, 0),
    "disabled_no_pulse": (1.0, 0),
}
DTS = study.DTS  # 1, 0.5, 0.25, 0.125 ms
FINEST = DTS[-1]
END, EVERY = 1.0, 0.05
WORLD = dict(  # The declared parameters (regulated_availability_references.cell_world's values).
    regulator_mM=1e-3,
    clearance=5.0,
    pulse=(0.2, 0.5),
    half_saturation=3e-3,
    coefficient=2.0,
    basal=0.1,
    population_P=2e-9,
    population_schedule=((0.0, 1.0),),
)
RESTART_STEPS = (1599, 1600, 1601, 3999, 4000, 4001)  # Before, at and after each production event.
WINDOW_STEPS = (4, 7)
WINDOW = 1000  # The uninterrupted run's window.
DURATION_SECONDS = (1.0, 10.0, 60.0)
UNITS = dict(
    time_s="s",
    voltage_V="V",
    ion_amounts_fmol="fmol",
    X_fmol="fmol",
    X_produced_fmol="fmol",
    X_cleared_fmol="fmol",
    availability="dimensionless",
)
REFERENCE_SOURCES = (
    "validation/coupling/cells_reference.py",
    "validation/coupling/state_reference.py",
    "validation/coupling/factor_reference.py",
    "validation/coupling/piecewise_ode.py",
    "validation/division/cleft_egg_reference.py",
)
EMPTY_PATCH_SHA256 = hashlib.sha256(b"").hexdigest()


# ------------------------------------------------------------------ files and identity


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def dt_label(dt):
    return f"{dt:g}"


def stem(arm, dt):
    return f"{arm}-{dt_label(dt)}"


def json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


def put(out, relative, data):
    """Write bytes (or a JSON value) under out; return the artifact record."""
    if not isinstance(data, bytes):
        data = json_bytes(data)
    path = Path(out) / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return dict(path=str(relative), sha256=sha256_bytes(data), bytes=len(data))


def artifact(out, relative):
    data = (Path(out) / relative).read_bytes()
    return dict(path=str(relative), sha256=sha256_bytes(data), bytes=len(data))


def load(out, relative):
    return json.loads((Path(out) / relative).read_text())


def source_identity():
    """The run's source: the snapshot's record, or the checkout's head (a development run)."""
    found = study.snapshot_identity(ROOT)
    if found["kind"] == "snapshot":
        clean = found["status"] == "complete" and found["patch_sha256"] == EMPTY_PATCH_SHA256
        return dict(
            kind="snapshot",
            source_revision=found["git_revision"],
            source_dirty=not clean,
            patch_sha256=found["patch_sha256"],
        )
    return dict(
        kind="checkout",
        source_revision=found["git_revision"],
        source_dirty=bool(found["dirty"]),
        patch_sha256=None,
    )


def versions():
    import jax
    import scipy

    return dict(
        python=platform.python_version(),
        numpy=np.__version__,
        scipy=scipy.__version__,
        jax=jax.__version__,
    )


def hardware():
    model = "unknown"
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                model = line.split(":", 1)[1].strip()
                break
    except OSError:
        pass
    import jax

    return dict(
        platform=platform.platform(),
        cpu_model=model,
        cpus_allowed=sorted(os.sched_getaffinity(0)),
        jax_backend=jax.default_backend(),
        jax_devices=[str(d) for d in jax.devices()],
    )


def guarded(out, name, function, *args):
    """Run a stage; a failure is written to OUT/failures/<name>.failure.json and returned."""
    try:
        return function(*args), None
    except BaseException as error:  # noqa: BLE001 (every failure is evidence)
        record = dict(
            stage=name,
            error_type=type(error).__name__,
            message=str(error),
            traceback=traceback.format_exc(),
            completed=False,
        )
        put(out, f"failures/{name}.failure.json", record)
        print("FAILED", name, type(error).__name__, str(error)[:300], flush=True)
        return None, record


# ------------------------------------------------------------------ the 16 definitions


def arm_world(arm):
    pulse_factor, enabled = ARMS[arm]
    return rr.cell_world(pulse_factor=pulse_factor, enabled=enabled, **WORLD)


def record_times(dt, end=END, every=EVERY):
    """Observation times on the engine's grid: 0 and every `every`, as (k * stride) * dt."""
    return [0.0, *study.grid_records(end, every, dt)]


def reference_start(arm):
    """The reference's own start (V, background), which the engine's definition also starts from."""
    run = rc.simulate(arm_world(arm), END, record=(END,))
    c0 = run.initial["c0"]
    return {"c0": (c0["V"], c0["background_fmol"])}


def raw_definition(arm, dt, initial):
    times = record_times(dt)
    return rr.engine_definition(arm_world(arm), dt=dt, end=END, times=times, initial=initial)


def build_definitions():
    """{(arm, dt): raw definition bytes} for the 16 definitions (the starts are the reference's)."""
    starts = {enabled: reference_start(arm) for arm, (_, enabled) in ARMS.items()}
    out = {}
    for arm, (_, enabled) in ARMS.items():
        for dt in DTS:
            out[arm, dt] = json_bytes(raw_definition(arm, dt, starts[enabled]))
    return out


def write_definitions(out):
    records, built = [], build_definitions()
    for (arm, dt), data in built.items():
        started = time.perf_counter()
        spec = parse_spec(json.loads(data))
        plan = plan_windows(spec, WindowPolicy(WINDOW, "full"))
        grid = EventGrid(spec)
        steps = round(END / dt)
        if len(grid) != steps + 1 or grid.extras:
            raise RuntimeError(f"{arm} {dt}: the clock is not the nominal grid of {steps} steps")
        record = put(out, f"definitions/{stem(arm, dt)}.json", data)
        records.append(
            dict(
                arm=arm,
                dt_s=dt,
                artifact=record,
                definition_sha256=record["sha256"],
                spec_fingerprint=spec.fingerprint,
                steps=steps,
                windows_planned=plan.window_count,
                parse_and_plan_seconds=time.perf_counter() - started,
            )
        )
    put(out, "definitions.json", dict(definitions=records, initial_voltage_V=initial_report()))
    return records


def initial_report():
    return {
        arm: dict(zip(("V", "background_fmol"), reference_start(arm)["c0"], strict=True))
        for arm in ARMS
    }


def definitions_index(out):
    return {(d["arm"], d["dt_s"]): d for d in load(out, "definitions.json")["definitions"]}


def spec_from_file(out, arm, dt):
    """The definition as written (the bytes that are executed)."""
    return parse_spec(load(out, f"definitions/{stem(arm, dt)}.json"))


# ------------------------------------------------------------------ the engine's streams


class Stream:
    """A windowed run's complete rows: state rows by step, observation columns by record."""

    def __init__(self, first_step):
        self.first_step = first_step
        self.state = {}
        self.obs = {}
        self.windows = 0
        self.final = None


def collect(spec, window_steps, checkpoint=None, on_window=None):
    """Run through iter_windows (A8's pattern): state rows keyed by step (adjacent windows share
    an endpoint row, which must agree bit for bit), observations concatenated."""
    rows, observed, final, windows, first = {}, {}, None, 0, None
    fields = None
    for window in iter_windows(spec, WindowPolicy(window_steps, "full"), checkpoint):
        fields = fields or type(window.history)._fields
        arrays = [np.asarray(v) for v in window.history]
        for i in range(len(window.times)):
            step = window.start_step + i
            row = tuple(a[i] for a in arrays)
            if step in rows:
                if any(a.tobytes() != b.tobytes() for a, b in zip(rows[step], row, strict=True)):
                    raise RuntimeError(f"windows disagree at their shared step {step}")
            else:
                rows[step] = row
        first = window.start_step if first is None else first
        for name, value in vars(window.observations).items():
            observed.setdefault(name, []).append(np.asarray(value))
        if on_window is not None:
            on_window(window)
        final, windows = window.final, windows + 1
    steps = sorted(rows)
    if steps != list(range(steps[0], steps[-1] + 1)):
        raise RuntimeError("the state rows are not consecutive steps")
    stream = Stream(steps[0])
    for k, name in enumerate(fields):
        stream.state[name] = np.stack([rows[s][k] for s in steps])
    stream.obs = {name: np.concatenate(parts) for name, parts in observed.items()}
    stream.windows, stream.final = windows, final
    times = stream.obs["times"]
    if not np.all(np.diff(times) > 0):
        raise RuntimeError("observation times are not strictly increasing")
    return stream


def engine_rows(spec, stream):
    """Trace rows at the registered records, from the typed columns (contract's row shape)."""
    m = spec.model
    species = list(m.species_ids)
    ions = [species.index(s) for s in rr.SPECIES]
    x = species.index("X")
    anchor = np.asarray([m.cells[0].initial_amount_fmol[i] for i in range(len(species))])
    rows, worst = [], 0.0
    for j, t in enumerate(stream.obs["times"]):
        step = int(stream.obs["coupling_step_count"][j, 0])
        increment = stream.state["amount_increment"][step - stream.first_step][:, 0]
        total = anchor + increment
        worst = max(worst, float(np.max(np.abs(total - stream.obs["amount"][j][:, 0]))))
        rows.append(
            dict(
                time_s=float(t),
                step=step,
                voltage_V=float(stream.obs["cell_potential_V"][j, 0]),
                ion_amounts_fmol={
                    s: float(total[i]) for s, i in zip(rr.SPECIES, ions, strict=True)
                },
                X_fmol=float(total[x]),
                X_produced_fmol=float(stream.obs["turnover_produced_fmol"][j, x, 0]),
                X_cleared_fmol=float(stream.obs["turnover_cleared_fmol"][j, x, 0]),
                availability=float(stream.obs["channel_availability"][j, 0]),
            )
        )
    return rows, worst


def shapes(stream):
    """{field name: [dtype, per-row shape]} of the state rows and the observation columns."""
    out = {f"state.{k}": [v.dtype.str, list(v.shape[1:])] for k, v in stream.state.items()}
    out |= {f"observations.{k}": [v.dtype.str, list(v.shape[1:])] for k, v in stream.obs.items()}
    return out


def inventory_record(spec, stream, identity, definition_sha256):
    declared = list(get_model(spec.model).STATE_TYPE._fields)
    fields = {k: dict(dtype=d, shape=s) for k, (d, s) in shapes(stream).items()}
    return dict(
        source_revision=identity["source_revision"],
        definition_sha256=definition_sha256,
        scope="all_compiled_state_fields_and_observation_columns",
        species_index={s: i for i, s in enumerate(spec.model.species_ids)},
        cell_index={c.id: i for i, c in enumerate(spec.model.cells)},
        fields=fields,
        state_fields_equal_STATE_TYPE_fields=sorted(declared)
        == sorted(k[6:] for k in fields if k.startswith("state.")),
    )


def write_stream(
    out,
    directory,
    spec,
    stream,
    identity,
    definition_sha256,
    inventory_sha256,
    dt,
    first,
    observation_from=None,
):
    """A stream JSON and its raw C-order field files, from step `first` and (for restarts) the
    observations at or after `observation_from`."""
    keep = np.flatnonzero(
        stream.obs["times"] >= (-math.inf if observation_from is None else observation_from)
    )
    fields = {}
    for kind, columns in (("state", stream.state), ("observations", stream.obs)):
        for name, values in columns.items():
            part = values[first - stream.first_step :] if kind == "state" else values[keep]
            part = np.ascontiguousarray(part)
            record = put(out, f"{directory}/{kind}.{name}.bin", part.tobytes())
            fields[f"{kind}.{name}"] = dict(
                dtype=part.dtype.str, shape=list(part.shape), artifact=record
            )
    last = stream.first_step + len(next(iter(stream.state.values()))) - 1
    value = dict(
        source_revision=identity["source_revision"],
        definition_sha256=definition_sha256,
        inventory_sha256=inventory_sha256,
        dt_s=dt,
        start_step=first,
        end_step=last,
        state_step_stride=1,
        observation_times_s=[float(t) for t in stream.obs["times"][keep]],
        fields=fields,
    )
    return put(out, f"{directory}/stream.json", value)


def compare_streams(out, a, b):
    """Exact bytes, dtype and shape of every field of two stream JSONs (NaN payloads included)."""
    sa, sb = load(out, a["path"]), load(out, b["path"])
    problems = []
    for key in (
        "source_revision",
        "definition_sha256",
        "inventory_sha256",
        "dt_s",
        "start_step",
        "end_step",
        "state_step_stride",
        "observation_times_s",
    ):
        if sa[key] != sb[key]:
            problems.append(f"{key} differs")
    if sa["fields"].keys() != sb["fields"].keys():
        problems.append("field sets differ")
    for name in sorted(sa["fields"].keys() & sb["fields"].keys()):
        fa, fb = sa["fields"][name], sb["fields"][name]
        if fa["dtype"] != fb["dtype"] or fa["shape"] != fb["shape"]:
            problems.append(f"{name}: dtype or shape differs")
        elif (Path(out) / fa["artifact"]["path"]).read_bytes() != (
            Path(out) / fb["artifact"]["path"]
        ).read_bytes():
            problems.append(f"{name}: bytes differ")
    return dict(identical=not problems, fields=len(sa["fields"]), problems=problems)


# ------------------------------------------------------------------ the 16 engine runs


def trace_record(arm, role, identity, definition_sha256, rows, dt=None):
    value = dict(
        arm=arm,
        role=role,
        source_revision=identity["source_revision"],
        definition_sha256=definition_sha256,
        units=UNITS,
        rows=rows,
    )
    return value | (dict(dt_s=dt) if role == "engine" else {})


def collect_with_checkpoints(out, spec, written):
    """The uninterrupted run, writing a complete checkpoint at each restart step (written[step] =
    its time) as its window passes."""
    pending = list(RESTART_STEPS)

    def write(window):
        for step in list(pending):
            offset = step - window.start_step
            if 0 <= offset < len(window.times):
                t = float(window.times[offset])
                path = Path(out) / "checkpoints" / f"step-{step}"
                write_snapshot(path, spec, window.checkpoint_at(t))
                written[step] = t
                pending.remove(step)

    stream = collect(spec, WINDOW, None, write)
    if pending:
        raise RuntimeError(f"checkpoints not reached: {pending}")
    return stream


def run_engine(out):
    identity = source_identity()
    index = definitions_index(out)
    runs, shared = [], {}
    order = [(a, d) for d in DTS for a in ARMS]
    finest_pulse = ("regulated_pulse", FINEST)
    for arm, dt in order:
        name = stem(arm, dt)
        record = index[arm, dt]
        spec = spec_from_file(out, arm, dt)
        started = time.perf_counter()
        last_checkpoint = {}
        if (arm, dt) == finest_pulse:
            stream, failure = guarded(
                out, name, collect_with_checkpoints, out, spec, last_checkpoint
            )
        else:
            stream, failure = guarded(out, name, collect, spec, WINDOW)
        if failure is not None:
            runs.append(dict(arm=arm, dt_s=dt, completed=False))
            continue
        wall = time.perf_counter() - started
        rows, amount_gap = engine_rows(spec, stream)
        steps_ok = all(r["step"] == round(r["time_s"] / dt) for r in rows)
        trace = put(
            out,
            f"traces/engine-{name}.json",
            trace_record(arm, "engine", identity, record["definition_sha256"], rows, dt),
        )
        runs.append(
            dict(
                arm=arm,
                dt_s=dt,
                completed=True,
                wall_s=wall,
                windows=stream.windows,
                steps=stream.final.step_index,
                final_time_s=stream.final.time,
                trace=trace,
                shapes=shapes(stream),
                amount_obs_vs_reference_plus_increment_max_abs_fmol=amount_gap,
                step_column_equals_round_time_over_dt=steps_ok,
            )
        )
        print("engine", name, f"{wall:.1f} s", flush=True)
        if (arm, dt) == finest_pulse:
            shared = dict(stream=stream, spec=spec, record=record, checkpoints=last_checkpoint)
    reference_shapes = runs[0]["shapes"] if runs and runs[0].get("completed") else None
    same = all(r.get("shapes") == reference_shapes for r in runs if r["completed"])
    put(out, "engine_runs.json", dict(runs=runs, all_16_share_the_inventory=same))
    if shared:
        write_restart_inputs(out, identity, **shared)
    if not all(r["completed"] for r in runs):
        raise RuntimeError("some of the 16 runs failed; see failures/")


def write_restart_inputs(out, identity, stream, spec, record, checkpoints):
    """The inventory, the uninterrupted stream and its six restart slices (regulated_pulse)."""
    sha = record["definition_sha256"]
    inventory = put(out, "inventory.json", inventory_record(spec, stream, identity, sha))
    full = write_stream(
        out,
        "streams/uninterrupted",
        spec,
        stream,
        identity,
        sha,
        inventory["sha256"],
        FINEST,
        stream.first_step,
    )
    slices = {}
    for step, t in checkpoints.items():
        slices[step] = write_stream(
            out,
            f"restarts/step-{step}/uninterrupted",
            spec,
            stream,
            identity,
            sha,
            inventory["sha256"],
            FINEST,
            step,
            observation_from=t,
        )
    put(
        out,
        "restart_inputs.json",
        dict(inventory=inventory, uninterrupted=full, slices=slices, checkpoint_times=checkpoints),
    )


# ------------------------------------------------------------------ restarts and windows


def run_continue(out, step):
    """One fresh process: load the written checkpoint, run to the end, write the stream."""
    identity = source_identity()
    sha = definitions_index(out)["regulated_pulse", FINEST]["definition_sha256"]
    inputs = load(out, "restart_inputs.json")
    started = time.perf_counter()
    snapshot = load_snapshot(Path(out) / "checkpoints" / f"step-{step}")
    stream = collect(snapshot.spec, WINDOW, snapshot.checkpoint)
    if stream.first_step != step or stream.final.step_index != round(END / FINEST):
        raise RuntimeError("the continued run did not start at the checkpoint or reach the end")
    written = write_stream(
        out,
        f"restarts/step-{step}/continued",
        snapshot.spec,
        stream,
        identity,
        sha,
        inputs["inventory"]["sha256"],
        FINEST,
        step,
        observation_from=snapshot.checkpoint.time,
    )
    put(
        out,
        f"restarts/step-{step}/continued.json",
        dict(
            run_id=f"continued-step-{step}",
            pid=os.getpid(),
            fresh_process=True,
            checkpoint_step=step,
            checkpoint_time_s=snapshot.checkpoint.time,
            snapshot_spec_fingerprint=snapshot.spec.fingerprint,
            definition_spec_fingerprint=spec_from_file(out, "regulated_pulse", FINEST).fingerprint,
            wall_s=time.perf_counter() - started,
            stream=written,
        ),
    )


def run_windows(out, window_steps):
    identity = source_identity()
    sha = definitions_index(out)["regulated_pulse", FINEST]["definition_sha256"]
    inputs = load(out, "restart_inputs.json")
    spec = spec_from_file(out, "regulated_pulse", FINEST)
    started = time.perf_counter()
    stream = collect(spec, window_steps)
    wall = time.perf_counter() - started
    written = write_stream(
        out,
        f"windows/steps-{window_steps}/stream",
        spec,
        stream,
        identity,
        sha,
        inputs["inventory"]["sha256"],
        FINEST,
        0,
    )
    put(
        out,
        f"windows/steps-{window_steps}/run.json",
        dict(
            run_id=f"windows-{window_steps}",
            pid=os.getpid(),
            window_steps=window_steps,
            windows=stream.windows,
            wall_s=wall,
            stream=written,
        ),
    )


def run_compare(out):
    inputs = load(out, "restart_inputs.json")
    restarts = []
    for step in RESTART_STEPS:
        run = load(out, f"restarts/step-{step}/continued.json")
        result = compare_streams(out, inputs["slices"][str(step)], run["stream"])
        restarts.append(
            dict(
                checkpoint_step=step,
                checkpoint_time_s=run["checkpoint_time_s"],
                fresh_process=run["fresh_process"],
                uninterrupted_run_id="uninterrupted-engine-run",
                continued_run_id=run["run_id"],
                checkpoint=artifact(out, f"checkpoints/step-{step}/manifest.json"),
                checkpoint_files=[
                    artifact(out, f.relative_to(out))
                    for f in sorted((Path(out) / "checkpoints" / f"step-{step}").iterdir())
                ],
                uninterrupted=inputs["slices"][str(step)],
                continued=run["stream"],
                comparison=result,
            )
        )
    windows = []
    for n in WINDOW_STEPS:
        run = load(out, f"windows/steps-{n}/run.json")
        windows.append(
            dict(
                window_steps=n,
                uninterrupted=inputs["uninterrupted"],
                windowed=run["stream"],
                comparison=compare_streams(out, inputs["uninterrupted"], run["stream"]),
                windows=run["windows"],
                wall_s=run["wall_s"],
            )
        )
    put(out, "restarts.json", dict(restarts=restarts))
    put(out, "windows.json", dict(windows=windows))
    bad = [r["checkpoint_step"] for r in restarts if not r["comparison"]["identical"]]
    bad += [w["window_steps"] for w in windows if not w["comparison"]["identical"]]
    if bad:
        raise RuntimeError(f"byte comparisons differ: {bad}")


# ------------------------------------------------------------------ the independent references


def imports_engine(sources):
    """Whether any reference source imports cells (a static scan of the files' imports)."""
    for path in sources:
        for node in ast.walk(ast.parse((ROOT / path).read_text())):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else []
            if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names.append(node.module)
            if any(n == "cells" or n.startswith("cells.") for n in names):
                return True
    return False


def reference_rows(world, run):
    """Trace rows at the decimal record times. X and its ledgers are the turnover's closed form
    (R-state's Turnover), not an integration: the regulator is neutral and impermeant, so the
    electrical solve does not depend on it."""
    turnover = world.regulators["X"].amounts["c0"]
    segments = list(turnover.segments)
    ends = [s[0] for s in segments[1:]] + [math.inf]
    rows = []
    for t in sorted(run.at):
        row = run.at[t]
        produced = math.fsum(
            p * max(0.0, min(t, end) - start)
            for (start, p, _), end in zip(segments, ends, strict=True)
        )
        amount = float(turnover.amount(t))
        rows.append(
            dict(
                time_s=t,
                voltage_V=float(row["V"]["c0"]),
                ion_amounts_fmol=dict(
                    zip(rr.SPECIES, (float(a) for a in row["amounts_fmol"]["c0"]), strict=True)
                ),
                X_fmol=amount,
                X_produced_fmol=produced,
                X_cleared_fmol=float(turnover.n0_fmol) + produced - amount,
                availability=float(row["elements"]["kleak"]["a_eff"]),
            )
        )
    return rows


def run_references(out, contract_sha256=None):
    identity = source_identity()
    index = definitions_index(out)
    record = [round(EVERY * k, 10) for k in range(round(END / EVERY) + 1)]
    started, written = time.perf_counter(), []
    for arm in ARMS:
        world = arm_world(arm)
        normal, refined, differences = rc.floor(world, END, record)
        sha = index[arm, FINEST]["definition_sha256"]
        for role, run, suffix in (
            ("reference", normal, ""),
            ("reference_refined", refined, "-refined"),
        ):
            written.append(
                put(
                    out,
                    f"traces/reference-{arm}{suffix}.json",
                    trace_record(arm, role, identity, sha, reference_rows(world, run)),
                )
            )
        print("reference", arm, f"{differences['V']:.2e} V", flush=True)
    sources = [
        dict(
            source_name=name,
            artifact=put(out, f"reference_sources/{name}", (ROOT / name).read_bytes()),
        )
        for name in REFERENCE_SOURCES
    ]
    put(
        out,
        "reference_provenance.json",
        dict(
            source_revision=identity["source_revision"],
            contract_sha256=contract_sha256,
            imports_engine=imports_engine(REFERENCE_SOURCES),
            imports_engine_note=(
                "static scan of the five source files' imports for cells; the world declaration "
                "comes from regulated_availability_references.cell_world, whose engine translation "
                "half imports cells but is not used by the solve"
            ),
            normal=dict(method="Radau", rtol=1e-10, atol_scale=1.0),
            refined=dict(method="Radau", rtol=1e-12, atol_scale=0.001),
            settings_source="cells_reference.floor(world, t_end, record) defaults: rtol 1e-10 and "
            "rtol/100 with atol/1000 (cells_reference.ATOL)",
            atol=rc.ATOL,
            record_times_s=record,
            x_ledger_mapping=(
                "X_fmol, X_produced_fmol and X_cleared_fmol are R-state's analytic Turnover "
                "(amount; cumulative production as the sum of production x overlap per segment; "
                "cleared = n0 + produced - amount); voltage, ions and availability (a_eff, the "
                "as-built convention) are the integrated electrical solve"
            ),
            dependency_versions=versions(),
            reference_time_seconds=time.perf_counter() - started,
            source_artifacts=sources,
            traces=written,
        ),
    )


# ------------------------------------------------------------------ duration probes


def run_duration(out, seconds):
    """A separate probe: regulated_pulse at the finest step to `seconds` (only the horizon, the
    observation times and max_steps differ from the short case's definition)."""
    identity = source_identity()
    parent = definitions_index(out)["regulated_pulse", FINEST]
    raw = load(out, parent["artifact"]["path"])
    dt = raw["execution"]["dt"]
    raw["experiment"]["end_time"] = seconds
    raw["experiment"]["observation_times"] = record_times(dt, seconds, seconds / 20)
    raw["execution"]["max_steps"] = int(math.ceil(seconds / dt)) + 8
    name = f"duration/{dt_label(seconds)}s"
    definition = put(out, f"{name}-definition.json", json_bytes(raw))
    value = dict(
        source_revision=identity["source_revision"],
        status="refused",
        arm="regulated_pulse",
        dt_s=dt,
        parent_definition_sha256=parent["definition_sha256"],
        definition=definition,
        requested_seconds=seconds,
        completed_seconds=0.0,
        completed_steps=0,
        cold_compile_seconds=None,
        warm_execution_seconds=None,
        total_wall_seconds=None,
        peak_memory_bytes=None,
        hardware=hardware(),
        refusal=None,
    )
    started = time.perf_counter()
    try:
        spec = parse_spec(json.loads(json.dumps(raw)))
        result = run_windowed(spec, WindowPolicy(WINDOW, "observations"))
        timings = result.timings
        value.update(
            status="completed",
            completed_seconds=float(result.final.time),
            completed_steps=int(result.final.step_index),
            cold_compile_seconds=timings["window_compile_or_cache_seconds"],
            warm_execution_seconds=timings["window_execute_seconds"],
            window_timings=timings,
            windows=result.resources["windows"],
        )
    except BaseException as error:  # noqa: BLE001 (a guard failure is the record)
        value["refusal"] = dict(
            error_type=type(error).__name__, message=str(error), traceback=traceback.format_exc()
        )
    value["total_wall_seconds"] = time.perf_counter() - started
    value["peak_memory_bytes"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    value["peak_memory_note"] = "this process's peak resident set (ru_maxrss)"
    put(out, f"{name}.json", value)
    print("duration", seconds, value["status"], f"{value['total_wall_seconds']:.1f} s", flush=True)


# ------------------------------------------------------------------ the index and the receipt


def run_index(out, contract_sha256=None):
    out = Path(out)
    identity = source_identity()
    index = definitions_index(out)
    engine = load(out, "engine_runs.json")
    failures = sorted(p.name for p in (out / "failures").glob("*.failure.json"))
    executed = all(r["completed"] for r in engine["runs"]) and len(engine["runs"]) == 16
    if (ROOT / "SNAPSHOT.json").exists():
        put(out, "SNAPSHOT.json", (ROOT / "SNAPSHOT.json").read_bytes())
    record = put(
        out,
        "execution_record.json",
        dict(
            source=identity,
            command=" ".join(sys.argv),
            versions=versions(),
            hardware=hardware(),
            runs=engine["runs"],
            all_16_share_the_inventory=engine["all_16_share_the_inventory"],
            definitions=[
                dict(
                    arm=a,
                    dt_s=dt,
                    spec_fingerprint=d["spec_fingerprint"],
                    parse_and_plan_seconds=d["parse_and_plan_seconds"],
                    windows_planned=d["windows_planned"],
                )
                for (a, dt), d in index.items()
            ],
            failures=failures,
        ),
    )
    admission = put(
        out,
        "admission.json",
        dict(
            source_revision=identity["source_revision"],
            source_dirty=identity["source_dirty"],
            status="admitted_and_executed" if executed and not failures else "incomplete",
            contract_sha256=contract_sha256,
            definitions=[
                dict(arm=a, dt_s=dt, definition_sha256=d["definition_sha256"])
                for (a, dt), d in index.items()
            ],
            execution_record=record,
        ),
    )
    restarts = artifact(out, "restarts.json") if (out / "restarts.json").exists() else None
    windows = artifact(out, "windows.json") if (out / "windows.json").exists() else None
    provenance = (
        artifact(out, "reference_provenance.json")
        if (out / "reference_provenance.json").exists()
        else None
    )
    durations = (
        sorted(str(p.relative_to(out)) for p in (out / "duration").glob("*s.json"))
        if (out / "duration").exists()
        else []
    )
    put(
        out,
        "export_index.json",
        dict(
            source=identity,
            evidence_kind="engine_export",
            definitions=[
                dict(arm=a, dt_s=dt, artifact=d["artifact"]) for (a, dt), d in index.items()
            ],
            admission=admission,
            reference_provenance=provenance,
            references=[
                dict(artifact=artifact(out, f"traces/reference-{a}{s}.json"))
                for a in ARMS
                for s in ("", "-refined")
                if (out / f"traces/reference-{a}{s}.json").exists()
            ],
            engine_traces=[
                dict(artifact=artifact(out, f"traces/engine-{stem(a, dt)}.json"))
                for (a, dt) in index
                if (out / f"traces/engine-{stem(a, dt)}.json").exists()
            ],
            stream_inventory=artifact(out, "inventory.json")
            if (out / "inventory.json").exists()
            else None,
            restarts=restarts,
            windows=windows,
            duration_observations=durations,
            failures=failures,
        ),
    )


# ------------------------------------------------------------------ the entry


def stage(out, *arguments):
    """One stage in its own fresh process."""
    command = [sys.executable, "-B", "-u", "-m", "validation.tissue.matched_arm_export", *arguments]
    return subprocess.run(command, cwd=ROOT, check=False).returncode


def run_all(out, contract_sha256):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    extra = ["--contract-sha256", contract_sha256] if contract_sha256 else []
    codes = {}
    codes["definitions"] = stage(out, "definitions", str(out))
    if codes["definitions"] == 0:
        codes["references"] = stage(out, "references", str(out), *extra)
        codes["engine"] = stage(out, "engine", str(out))
        if codes["engine"] == 0:
            for step in RESTART_STEPS:
                codes[f"continue-{step}"] = stage(out, "continue", str(out), "--step", str(step))
            for n in WINDOW_STEPS:
                codes[f"windows-{n}"] = stage(out, "windows", str(out), "--steps", str(n))
            codes["compare"] = stage(out, "compare", str(out))
        codes["index"] = stage(out, "index", str(out), *extra)
    put(out, "stages.json", dict(exit_codes=codes))
    return 0 if all(c == 0 for c in codes.values()) else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "command",
        choices=(
            "all",
            "definitions",
            "references",
            "engine",
            "continue",
            "windows",
            "compare",
            "duration",
            "index",
        ),
    )
    parser.add_argument("out")
    parser.add_argument("--step", type=int)
    parser.add_argument("--steps", type=int)
    parser.add_argument("--seconds", type=float)
    parser.add_argument("--contract-sha256")
    args = parser.parse_args(argv)
    out = Path(args.out)
    if args.command == "all":
        return run_all(out, args.contract_sha256)
    runners = dict(
        definitions=lambda: write_definitions(out),
        references=lambda: run_references(out, args.contract_sha256),
        engine=lambda: run_engine(out),
        compare=lambda: run_compare(out),
        index=lambda: run_index(out, args.contract_sha256),
    )
    if args.command == "continue":
        runners["continue"] = lambda: run_continue(out, args.step)
    if args.command == "windows":
        runners["windows"] = lambda: run_windows(out, args.steps)
    if args.command == "duration":
        runners["duration"] = lambda: run_duration(out, args.seconds)
    name = (
        args.command
        + (f"-{args.step}" if args.step else "")
        + (f"-{args.steps}" if args.steps else "")
    )
    if args.command == "duration":
        name += f"-{args.seconds:g}"
    _, failure = guarded(out, name, runners[args.command])
    return 0 if failure is None else 1


if __name__ == "__main__":
    sys.exit(main())
