"""The results baseline at a tag, and the comparison integration commits are checked against.

D176 (commit order): declarations, dispatch, operator adaptation and door S are checked bitwise
against outputs saved at the tag (d172-base-2026-11-15); the summation change lands last, alone, at
a declared tolerance. This tool saves those outputs and compares them. It runs the engine of
whatever source is on PYTHONPATH (a frozen snapshot), on the CPU.

The worlds (`list` prints them):
- crossrev-*: the eight crossrev sets' worlds (composite base, qualification, injection and volume;
  division; secreted species; reactions; coupling), each to its own short end time;
- protocol-*: registered protocols' development worlds at short horizons: W1's definitions, W2's
  arms, G2-Q1's cases with W37 and Q7's 825-node tissue, S3's cleft egg, D150's arms, E07-v1's first
  arm and MG0c's chain;
- run-paths: two worlds (the 127-cell sheet and E07's 825-node tissue) through every run path
  (runner.run, run_windowed, run_batch, run_batch_windowed, run_vector_windowed).
Every world but the run paths runs its first scalar window of at most --max-steps steps
(core.windows.iter_windows): a world shorter than that runs to its end. A refusal is an output too
(its type and message).

Actions:
  list [--sets ...]
  save DIR [--sets ...] [--worlds ...] [--max-steps N] [--from BASELINE [--map TABLE]]
      run every world, writing DIR/SET/WORLD.npz (times, history, observations, diagnostics and
      the final checkpoint's state, time and step) and DIR/SET/WORLD.json (the definition run,
      the steps, seconds, a refusal); DIR/manifest.json records the source and environment.
      --from BASELINE runs the definitions saved there (so a later source's world builders
      cannot change what is compared). --map TABLE translates their renamed IDs first
      (validation/id_table.py; TABLE is the engine's renamed_ids.py or a JSON {old: new})
  compare BASELINE OTHER [--tolerance FILE] [--padding k1] [--map TABLE] [--output FILE]
      every array of every world: bitwise (default), or within a declared tolerance
      ({"KEY_PATTERN": {"relative": r, "absolute": a}}, fnmatch patterns over SET/WORLD:KEY,
      first match wins; |x - y| <= a + r max|x| per array); refusals must match exactly,
      BASELINE's read through TABLE where one is given.
      --padding k1 (off by default) lets channel_targets and channel_tau_s differ at channel
      slots inactive for the whole run (check K1), for uses such as packed bucketing. It is
      NOT used by D172's dispatch gate (the lead's ruling, 15 November: the host observer keeps
      today's padding values, so every observation column must match bitwise, division worlds
      with closed slots included); the planted active-slot failure is that gate's self-test.
Usage (from a frozen snapshot, CPU):
  JAX_PLATFORMS=cpu PYTHONPATH=SNAPSHOT/src:SNAPSHOT python results_baseline.py save OUT
"""

import argparse
import copy
import dataclasses
import fnmatch
import hashlib
import json
import os
import platform
import subprocess
import sys
import traceback
from pathlib import Path
from time import perf_counter

import numpy as np

MAX_STEPS = 200


# ------------------------------------------------------------------ worlds


def _crossrev(module, function, *args):
    def build():
        import importlib

        return getattr(importlib.import_module(module), function)(*args)

    return build


def _w1():
    from validation.tissue import composite_l4_agreement as agreement
    from validation.tissue import pump_water_qualification as w1q

    predictions = agreement.registered("w1")[0]
    out = {
        f"{name}": copy.deepcopy(w1q.item(predictions, path)["definition"])
        for name, path in w1q.TRAJECTORIES.items()
    }
    out["P2_stationary"] = copy.deepcopy(predictions["P2"]["definition"])
    return out


def _w2():
    from validation.tissue import composite_l4_agreement as agreement
    from validation.tissue import pump_water_kcc_qualification as w2q

    predictions = agreement.registered("w2")[0]
    return {arm: w2q.definition(predictions, arm) for arm in predictions["arms"]}


def _g2():
    from validation.tissue import cell_replacement_judge as judge
    from validation.tissue import cell_replacement_qualification as qual
    from validation.tissue import composite_l4_agreement as agreement

    predictions = agreement.registered("g2")[0]
    # At the judge's step (judge.engine runs qual.at_dt(raw, 1e-3)): the predictions' own
    # step does not land on their observation times.
    out = {name: qual.at_dt(e["definition"], 1e-3) for name, e in predictions["cases"].items()}
    out["W37"] = judge.w37_raw()
    out["Q7_tissue"] = judge.q7_raw(judge.REGISTERED["q7_channel_scale"])
    return out


def _operators():
    """Operator worlds that run at the tag: a law-steady replacement (gate_at_arrival law_steady,
    as tests/unit/test_cell_replacement.py's compiled run; crossrev's replacement_steady is
    refused at the tag, so it gives no output to compare) with an inner schedule change."""
    from cells.definitions.cell_replacement_spec import exact_event_times
    from validation.tissue import cell_replacement_fixtures as rfx

    dt = 1e-3
    t1, t2, t3 = exact_event_times((10, 20, 30), dt)
    raw = rfx.heredity_sheet(1, 0, dt=dt, end_time=50 * dt)
    raw["experiment"]["observation_times"] = list(exact_event_times((0, 10, 11, 30, 31, 50), dt))
    for control in raw["experiment"]["channel_controls"]:
        if control["channel_id"].startswith("nav_"):
            control["schedule"] = [
                dict(time=0.0, availability=control["schedule"][0]["availability"]),
                dict(time=t2, availability=0.5),
            ]
    templates = [
        rfx.template_from_cell(raw, "cell_1", "h"),
        rfx.template_from_cell(raw, "cell_3", "d"),
    ]
    steady = dict(rfx.FORMATION, initial_abundance=1.0, lag_s=0.0, gate_at_arrival="law_steady")
    events = ((t1, "cell_0", "h", "n1"), (t3, "cell_3", "h", "n2"))
    return {
        "replacement_law_steady": rfx.with_replacement(raw, templates, events, formation=steady)
    }


def _s3():
    from validation.division import cleft_egg_engine as egg

    return {"cleft_egg": egg.definition()}  # Its own end; the first window keeps it short.


def _d150():
    from validation.tissue import secreted_species_qualification as d150

    return {name: d150.arm_world(name) for name in d150.ARMS}  # Own ends; first window only.


def _e07():
    from validation.tissue import e07_v1_run as run

    protocol = json.loads((Path(run.__file__).parent / "e07_v1_protocol.json").read_text())
    arm = protocol["arms"][0]
    record = run.schedule(arm, 0, dt=protocol["numerics"].get("dt", 1e-3), end_s=0.2)
    raw, _ = run.build(record)
    return {arm["id"]: raw}


def _mg0c():
    from validation.morphogenesis import mg0c_turing as mg

    profile = mg.mode_profile(16, 2)
    return {"chain16_mode2": mg.chain_world(profile, end=1.0, observation_times=[0.0, 1.0])}


def _run_path_worlds():
    from validation.tissue import cell_replacement_fixtures as rfx
    from validation.tissue import surface_pump_v3_study as study

    return {
        "sheet254": rfx.heredity_sheet(6, 3, scale=0.3, dt=1e-3, end_time=0.01),
        "tissue825": study.tissue_definition(dt=1e-3, end_time=0.02, observation_times=[0.0, 0.02]),
    }


SETS = {
    "crossrev-base": _crossrev("validation.tissue.composite_crossrev", "worlds"),
    "crossrev-qualification": _crossrev(
        "validation.tissue.composite_crossrev", "qualification_worlds"
    ),
    "crossrev-injection": _crossrev("validation.tissue.composite_crossrev", "injection_worlds"),
    "crossrev-volume": _crossrev("validation.tissue.composite_crossrev", "volume_worlds"),
    "crossrev-division": _crossrev("validation.division.division_crossrev", "division_worlds"),
    "crossrev-species": _crossrev("validation.tissue.secreted_species_crossrev", "species_worlds"),
    "crossrev-reactions": _crossrev(
        "validation.tissue.species_reactions_crossrev", "reaction_worlds"
    ),
    "crossrev-coupling": _crossrev(
        "validation.tissue.regulated_availability_crossrev", "coupling_worlds"
    ),
    "operators": _operators,
    "protocol-w1": _w1,
    "protocol-w2": _w2,
    "protocol-g2": _g2,
    "protocol-s3": _s3,
    "protocol-d150": _d150,
    "protocol-e07": _e07,
    "protocol-mg0c": _mg0c,
    "run-paths": _run_path_worlds,
}
PATHS = ("run", "run_windowed", "run_batch", "run_batch_windowed", "run_vector_windowed")


# ------------------------------------------------------------------ outputs


def flatten(value, prefix=""):
    """{dotted key: array} of a result tree (namedtuples, dataclasses, dicts, arrays, scalars)."""
    out = {}
    if value is None:
        return out
    if hasattr(value, "_asdict"):
        items = value._asdict().items()
    elif dataclasses.is_dataclass(value) and not isinstance(value, type):
        items = ((f.name, getattr(value, f.name)) for f in dataclasses.fields(value))
    elif isinstance(value, dict):
        items = value.items()
    elif hasattr(value, "__dict__") and not isinstance(value, np.ndarray | np.generic):
        items = vars(value).items()
    else:
        array = np.asarray(value)
        if array.dtype != object:
            out[prefix] = array
        return out
    for key, item in items:
        out.update(flatten(item, f"{prefix}.{key}" if prefix else str(key)))
    return out


def result_arrays(result):
    arrays = {"times": np.asarray(result.times)}
    arrays |= flatten(result.history, "history")
    arrays |= flatten(result.observations, "observations")
    arrays |= flatten({k: v for k, v in result.diagnostics.items()}, "diagnostics")
    final = result.final
    arrays |= flatten(final.state, "final.state")
    arrays["final.time"] = np.asarray(final.time)
    arrays["final.step_index"] = np.asarray(final.step_index)
    return arrays


def checkpoint_arrays(checkpoint, prefix):
    out = flatten(checkpoint.state, f"{prefix}.state")
    out[f"{prefix}.time"] = np.asarray(checkpoint.time)
    out[f"{prefix}.step_index"] = np.asarray(checkpoint.step_index)
    return out


def _channel_active(layout):
    found = [v for k, v in flatten(layout).items() if k.split(".")[-1] == "channel_active"]
    return np.asarray(found[0]).astype(bool).tolist() if found else None


def channel_activity(spec, final=None):
    """The channel slots' activity, for the comparator's padding rule (check K1): static when no
    operator provides channel_active through the view or closes masks (then the layout's mask is
    the run's), with the layout's mask at the start and at the end of the run."""
    from cells.execution.state import initialise
    from cells.registry.models import get_model

    model = get_model(spec.model)
    providers = getattr(model, "providers", ()) or ()
    static = not getattr(model, "closers", ()) and not any(
        "channel_active" in getattr(op, "VIEW_FIELDS", ()) for op in providers
    )
    return dict(
        static=bool(static),
        initial=_channel_active(initialise(spec).layout),
        final=None if final is None else _channel_active(final.layout),
    )


def run_world(raw, max_steps):
    """(arrays, steps, channel activity) of the world's first scalar window of at most
    max_steps steps."""
    from cells.definitions.specs import parse_spec
    from cells.execution.windows import WindowPolicy, iter_windows

    spec = parse_spec(raw)
    result = next(iter(iter_windows(spec, WindowPolicy(max_steps, "checkpoints"))))
    return result_arrays(result), len(result.times) - 1, channel_activity(spec, result.final)


def run_paths(raw):
    """{path: arrays} of one world through every run path (the batched ones over two copies)."""
    from cells.definitions.specs import parse_spec
    from cells.execution.batch import BatchSpec, WorldSpec, run_batch
    from cells.execution.batch_windows import run_batch_windowed
    from cells.execution.runner import run
    from cells.execution.vector_windows import run_vector_windowed
    from cells.execution.windows import WindowPolicy, run_windowed

    spec = parse_spec(raw)
    policy = WindowPolicy(MAX_STEPS, "checkpoints")
    batch = BatchSpec((WorldSpec(1, spec), WorldSpec(2, spec)), 2, 2**53 - 1, 2**53 - 1)
    out = {}
    out["run"] = result_arrays(run(spec))
    out["run_windowed"] = checkpoint_arrays(run_windowed(spec, policy).final, "final")
    batched = run_batch(batch)
    out["run_batch"] = {
        k: v
        for w in (1, 2)
        for k, v in result_arrays(batched.worlds[w]).items()
        for k in [f"world{w}.{k}"]
    }
    for name, function in (
        ("run_batch_windowed", run_batch_windowed),
        ("run_vector_windowed", run_vector_windowed),
    ):
        result = function(batch, policy)
        out[name] = {}
        for w in (1, 2):
            out[name] |= checkpoint_arrays(result.worlds[w].final, f"world{w}.final")
    return out


def stem(name):
    """A world's file name: its name with path separators replaced (G2's cases are C9/donor/...)."""
    return name.replace("/", "__")


def digest(array):
    a = np.ascontiguousarray(array)
    return hashlib.sha256(f"{a.dtype}{a.shape}".encode() + a.tobytes()).hexdigest()


def source():
    """The source on PYTHONPATH: a snapshot's SNAPSHOT.json revision, or a checkout's git state."""
    import cells

    root = Path(cells.__file__).resolve().parents[2]
    snapshot = root / "SNAPSHOT.json"
    if snapshot.exists():
        data = json.loads(snapshot.read_text())
        return dict(
            root=str(root),
            snapshot=True,
            git_revision=data.get("git_revision"),
            dirty=bool(data.get("selected_status_porcelain_v1_z")),
        )
    from validation import executed_sources  # noqa: PLC0415
    executed_sources.refuse_untracked(root, "results_baseline's source record")  # D259

    git = ["git", "-C", str(root)]
    run = lambda *a: subprocess.run([*git, *a], capture_output=True, text=True).stdout.strip()  # noqa: E731
    return dict(
        root=str(root),
        snapshot=False,
        git_revision=run("rev-parse", "HEAD"),
        dirty=run("status", "--porcelain", "--untracked-files=no"),
    )


def id_map_table(path):
    """The table file of --map, read; {} without one."""
    if path is None:
        return {}
    from validation import id_table

    return id_table.read_table(path)


def through(value, table):
    """`value` with its renamed IDs translated (validation/id_table.py)."""
    if not table:
        return value
    from validation import id_table

    return id_table.translate(value, table)


def save(directory, sets, worlds, max_steps, origin, append=False, id_map=None):
    """Run and save every world; with append, add sets (none already there) to an existing
    baseline from the same source, recording the addition in its manifest. With id_map (a table
    file), the origin's definitions are translated through it first."""
    import jax

    from cells.execution import blas_threads

    jax.config.update("jax_enable_x64", True)
    table = id_map_table(id_map)
    if append:
        manifest = json.loads((directory / "manifest.json").read_text())
        if manifest["source"] != source() or manifest["max_steps"] != max_steps:
            raise SystemExit("append: the baseline's source or max_steps differs from this run's")
        clash = [s for s in sets if (directory / s).exists()]
        if clash:
            raise SystemExit(f"append: the baseline already holds {clash}")
        manifest.setdefault("appended", []).append(
            dict(sets=list(sets), tool=str(Path(__file__).resolve()), at=time_now())
        )
        return _save_sets(directory, manifest, sets, worlds, max_steps, origin, table)
    directory.mkdir(parents=True, exist_ok=False)
    manifest = dict(
        kind="cells.results_baseline@1",
        source=source(),
        tool=str(Path(__file__).resolve()),
        environment=dict(
            jax=jax.__version__,
            devices=[str(d) for d in jax.devices()],
            python=platform.python_version(),
            machine=platform.machine(),
            XLA_FLAGS=os.environ.get("XLA_FLAGS"),
            JAX_PLATFORMS=os.environ.get("JAX_PLATFORMS"),
            JAX_DISABLE_JIT=os.environ.get("JAX_DISABLE_JIT"),
            cpu_affinity=sorted(os.sched_getaffinity(0)),
            blas=blas_threads.record(),  # D190: each BLAS library's version, kernels, threads.
        ),
        max_steps=max_steps,
        definitions_from=str(origin) if origin else "built by this source's validation builders",
        worlds={},
    )
    if id_map:
        manifest["definitions_through"] = dict(table=str(id_map), renamed_ids=len(table))
    return _save_sets(directory, manifest, sets, worlds, max_steps, origin, table)


def time_now():
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _save_sets(directory, manifest, sets, worlds, max_steps, origin, table):
    import jax

    for set_name in sets:
        if origin:
            records = [
                json.loads(p.read_text()) for p in sorted((origin / set_name).glob("*.json"))
            ]
            built = {r["name"]: through(r["definition"], table) for r in records}
        else:
            try:
                built = SETS[set_name]()
            except Exception as error:  # A builder that fails is recorded, not fatal.
                manifest["worlds"][set_name] = dict(builder_error=repr(error)[:2000])
                continue
        (directory / set_name).mkdir()
        for name, raw in built.items():
            if worlds and name not in worlds:
                continue
            key = f"{set_name}/{name}"
            started, record = perf_counter(), dict(name=name, definition=raw)
            try:
                if set_name == "run-paths":
                    from cells.definitions.specs import parse_spec

                    arrays = {
                        f"{path}:{k}": v for path, a in run_paths(raw).items() for k, v in a.items()
                    }
                    # The run paths' final layouts are not kept: activity at the start only.
                    activity = channel_activity(parse_spec(raw))
                    record["channel_activity"] = activity | dict(final=activity["initial"])
                else:
                    arrays, record["steps"], record["channel_activity"] = run_world(raw, max_steps)
            except Exception as error:  # A refusal is an output: its type and message.
                arrays = {}
                record["refusal"] = dict(
                    type=type(error).__name__,
                    message=str(error)[:4000],
                    traceback=traceback.format_exc()[-4000:],
                )
            record["seconds"] = perf_counter() - started
            jax.clear_caches()  # Each world's executables are released: memory stays per world.
            np.savez_compressed(directory / set_name / f"{stem(name)}.npz", **arrays)
            (directory / set_name / f"{stem(name)}.json").write_text(
                json.dumps(record, default=str) + "\n"
            )
            manifest["worlds"][key] = dict(
                steps=record.get("steps"),
                seconds=record["seconds"],
                refusal=record.get("refusal", {}).get("type"),
                arrays=len(arrays),
                digests={k: digest(v) for k, v in sorted(arrays.items())},
            )
            print(
                f"{key}: {'refused ' + record['refusal']['type'] if 'refusal' in record else 'ok'}"
                f" {record['seconds']:.1f} s",
                flush=True,
            )
            (directory / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")
    return manifest


# ------------------------------------------------------------------ compare


# Check K1 (core/padding-check/k1.json): per-law dispatch changes only these two readouts, and only
# at inactive channel slots; there they hold padding, not physics.
PADDING_COLUMNS = ("channel_targets", "channel_tau_s")


def inactive_slots(base, other, set_name, name):
    """Channel slots inactive for the whole run in both records (a boolean list), or None: the
    activity must be static (no operator provides channel_active or closes masks) and the slot
    inactive in the layout at the start and at the end of both runs."""
    records = [json.loads((d / set_name / f"{stem(name)}.json").read_text()) for d in (base, other)]
    activity = [r.get("channel_activity") for r in records]
    if not all(a and a["static"] and a["initial"] is not None for a in activity):
        return None
    masks = [a["initial"] for a in activity] + [a["final"] or a["initial"] for a in activity]
    if len({len(m) for m in masks}) != 1:
        return None
    return [not any(m[k] for m in masks) for k in range(len(masks[0]))]


def padding_only(p, q, inactive):
    """Whether p and q differ only in last-axis columns of slots inactive for the whole run."""
    if inactive is None or p.ndim == 0 or p.shape[-1] != len(inactive):
        return False
    differs = ~((p == q) | (np.isnan(p) & np.isnan(q))) if p.dtype.kind in "fc" else p != q
    columns = np.any(differs.reshape(-1, p.shape[-1]), axis=0)
    return bool(np.all(~columns | np.asarray(inactive)))


def tolerance_for(key, tolerances):
    for pattern, tol in tolerances.items():
        if fnmatch.fnmatch(key, pattern):
            return tol
    return None


def compare(base, other, tolerances, padding=False, table=()):
    a_manifest = json.loads((base / "manifest.json").read_text())
    b_manifest = json.loads((other / "manifest.json").read_text())
    rows, problems = [], []
    for world in sorted(set(a_manifest["worlds"]) | set(b_manifest["worlds"])):
        a, b = a_manifest["worlds"].get(world), b_manifest["worlds"].get(world)
        if a is None or b is None or "builder_error" in (a or {}) or "builder_error" in (b or {}):
            problems.append(dict(world=world, problem="missing or builder error", base=a, other=b))
            continue
        set_name, name = world.split("/", 1)
        ra = json.loads((base / set_name / f"{stem(name)}.json").read_text()).get("refusal")
        rb = json.loads((other / set_name / f"{stem(name)}.json").read_text()).get("refusal")
        if ra or rb:
            same = bool(
                ra
                and rb
                and ra["type"] == rb["type"]
                and through(ra["message"], table) == rb["message"]
            )
            rows.append(dict(world=world, refusal=True, equal=same))
            continue
        x, y = (
            np.load(base / set_name / f"{stem(name)}.npz"),
            np.load(other / set_name / f"{stem(name)}.npz"),
        )
        keys = sorted(set(x.files) | set(y.files))
        inactive = inactive_slots(base, other, set_name, name)
        worst, failing, padded = 0.0, [], []
        for key in keys:
            if key not in x.files or key not in y.files:
                failing.append(dict(key=key, problem="missing"))
                continue
            p, q = x[key], y[key]
            if p.dtype != q.dtype or p.shape != q.shape:
                failing.append(
                    dict(key=key, problem=f"{p.dtype}{p.shape} against {q.dtype}{q.shape}")
                )
                continue
            if np.array_equal(p, q, equal_nan=p.dtype.kind in "fc") and p.tobytes() == q.tobytes():
                continue
            if padding and key.split(".")[-1] in PADDING_COLUMNS and padding_only(p, q, inactive):
                padded.append(key)  # Check K1: per-law dispatch's padding at inactive slots.
                continue
            tol = tolerance_for(f"{world}:{key}", tolerances)
            if p.dtype.kind not in "fc" or tol is None:
                failing.append(
                    dict(key=key, problem="not bitwise" + ("" if tol is None else " (non-float)"))
                )
                continue
            d = float(np.max(np.abs(p.astype(float) - q.astype(float)), initial=0.0))
            scale = float(np.max(np.abs(p), initial=0.0))
            bound = tol.get("absolute", 0.0) + tol.get("relative", 0.0) * scale
            worst = max(worst, d / scale if scale else d)
            if not d <= bound:
                failing.append(dict(key=key, problem="beyond tolerance", difference=d, bound=bound))
        rows.append(
            dict(
                world=world,
                arrays=len(keys),
                equal=not failing,
                failing=failing[:20],
                failing_count=len(failing),
                padding_only=padded,
                largest_relative_within_tolerance=worst,
            )
        )
    verdict = "identical" if not tolerances else "within tolerance"
    ok = not problems and all(r["equal"] for r in rows)
    return dict(
        base=str(base),
        other=str(other),
        base_source=a_manifest["source"],
        other_source=b_manifest["source"],
        tolerances=tolerances or "bitwise",
        verdict=verdict if ok else "differs",
        worlds=len(rows),
        equal=sum(r["equal"] for r in rows),
        problems=problems,
        rows=rows,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="action", required=True)
    one = sub.add_parser("list")
    one.add_argument("--sets", nargs="*", default=list(SETS))
    two = sub.add_parser("save")
    two.add_argument("directory", type=Path)
    two.add_argument("--sets", nargs="*", default=list(SETS))
    two.add_argument("--worlds", nargs="*", default=[])
    two.add_argument("--max-steps", type=int, default=MAX_STEPS)
    two.add_argument("--from", dest="origin", type=Path)
    two.add_argument("--map", dest="id_map", type=Path, help="with --from: renamed IDs' table")
    two.add_argument("--append", action="store_true", help="add sets to an existing baseline")
    three = sub.add_parser("compare")
    three.add_argument("base", type=Path)
    three.add_argument("other", type=Path)
    three.add_argument("--tolerance", type=Path)
    three.add_argument(
        "--padding", choices=("k1",), help="check K1 padding rule (off for D172 gates)"
    )
    three.add_argument("--map", dest="id_map", type=Path, help="renamed IDs' table")
    three.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.action == "save" and args.id_map and not args.origin:
        parser.error("--map translates the definitions of --from")
    if args.action == "list":
        for set_name in args.sets:
            try:
                print(set_name, sorted(SETS[set_name]()))
            except Exception as error:
                print(set_name, "builder error:", repr(error)[:300])
    elif args.action == "save":
        manifest = save(
            args.directory,
            args.sets,
            set(args.worlds),
            args.max_steps,
            args.origin,
            args.append,
            args.id_map,
        )
        refused = [k for k, v in manifest["worlds"].items() if v.get("refusal")]
        errors = [k for k, v in manifest["worlds"].items() if "builder_error" in v]
        print(
            f"saved {len(manifest['worlds'])} entries; refusals {refused}; builder errors {errors}"
        )
    else:
        tolerances = json.loads(args.tolerance.read_text()) if args.tolerance else {}
        report = compare(
            args.base,
            args.other,
            tolerances,
            padding=args.padding == "k1",
            table=id_map_table(args.id_map),
        )
        if args.output:
            args.output.write_text(json.dumps(report, indent=1) + "\n")
        print(
            f"{report['verdict']}: {report['equal']} of {report['worlds']} worlds equal; "
            f"problems {len(report['problems'])}"
        )
        return 0 if report["verdict"] != "differs" else 1


if __name__ == "__main__":
    sys.exit(main())
