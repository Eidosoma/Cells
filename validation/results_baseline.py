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
  save DIR [--sets ...] [--worlds ...] [--max-steps N] [--from BASELINE]
      run every world, writing DIR/SET/WORLD.npz (times, history, observations, diagnostics and
      the final checkpoint's state, time and step) and DIR/SET/WORLD.json (the definition run,
      the steps, seconds, a refusal); DIR/manifest.json records the source and environment.
      --from BASELINE runs the definitions saved there (so a later source's world builders
      cannot change what is compared)
  compare BASELINE OTHER [--tolerance FILE] [--output FILE]
      every array of every world: bitwise (default), or within a declared tolerance
      ({"KEY_PATTERN": {"relative": r, "absolute": a}}, fnmatch patterns over SET/WORLD:KEY,
      first match wins; |x - y| <= a + r max|x| per array); refusals must match exactly
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
    from validation.tissue import composite_l4_agreement as agreement

    predictions = agreement.registered("g2")[0]
    out = {name: copy.deepcopy(e["definition"]) for name, e in predictions["cases"].items()}
    out["W37"] = judge.w37_raw()
    out["Q7_tissue"] = judge.q7_raw(judge.REGISTERED["q7_channel_scale"])
    return out


def _s3():
    from validation.division import cleft_egg_engine as egg

    return {"cleft_egg": egg.definition(end=0.05)}


def _d150():
    from validation.tissue import secreted_species_qualification as d150

    return {name: d150.arm_world(name, end=0.05) for name in d150.ARMS}


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


def run_world(raw, max_steps):
    """(arrays, steps) of the world's first scalar window of at most max_steps steps."""
    from cells.core.specs import parse_spec
    from cells.core.windows import WindowPolicy, iter_windows

    spec = parse_spec(raw)
    result = next(iter(iter_windows(spec, WindowPolicy(max_steps, "checkpoints"))))
    return result_arrays(result), len(result.times) - 1


def run_paths(raw):
    """{path: arrays} of one world through every run path (the batched ones over two copies)."""
    from cells.core.batch import BatchSpec, WorldSpec, run_batch
    from cells.core.batch_windows import run_batch_windowed
    from cells.core.runner import run
    from cells.core.specs import parse_spec
    from cells.core.vector_windows import run_vector_windowed
    from cells.core.windows import WindowPolicy, run_windowed

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
    git = ["git", "-C", str(root)]
    run = lambda *a: subprocess.run([*git, *a], capture_output=True, text=True).stdout.strip()  # noqa: E731
    return dict(
        root=str(root),
        snapshot=False,
        git_revision=run("rev-parse", "HEAD"),
        dirty=run("status", "--porcelain", "--untracked-files=no"),
    )


def save(directory, sets, worlds, max_steps, origin):
    import jax

    jax.config.update("jax_enable_x64", True)
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
        ),
        max_steps=max_steps,
        definitions_from=str(origin) if origin else "built by this source's validation builders",
        worlds={},
    )
    for set_name in sets:
        if origin:
            records = [
                json.loads(p.read_text()) for p in sorted((origin / set_name).glob("*.json"))
            ]
            built = {r["name"]: r["definition"] for r in records}
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
                    arrays = {
                        f"{path}:{k}": v for path, a in run_paths(raw).items() for k, v in a.items()
                    }
                else:
                    arrays, record["steps"] = run_world(raw, max_steps)
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


def tolerance_for(key, tolerances):
    for pattern, tol in tolerances.items():
        if fnmatch.fnmatch(key, pattern):
            return tol
    return None


def compare(base, other, tolerances):
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
            same = bool(ra and rb and ra["type"] == rb["type"] and ra["message"] == rb["message"])
            rows.append(dict(world=world, refusal=True, equal=same))
            continue
        x, y = (
            np.load(base / set_name / f"{stem(name)}.npz"),
            np.load(other / set_name / f"{stem(name)}.npz"),
        )
        keys = sorted(set(x.files) | set(y.files))
        worst, failing = 0.0, []
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
    three = sub.add_parser("compare")
    three.add_argument("base", type=Path)
    three.add_argument("other", type=Path)
    three.add_argument("--tolerance", type=Path)
    three.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.action == "list":
        for set_name in args.sets:
            try:
                print(set_name, sorted(SETS[set_name]()))
            except Exception as error:
                print(set_name, "builder error:", repr(error)[:300])
    elif args.action == "save":
        manifest = save(args.directory, args.sets, set(args.worlds), args.max_steps, args.origin)
        refused = [k for k, v in manifest["worlds"].items() if v.get("refusal")]
        errors = [k for k, v in manifest["worlds"].items() if "builder_error" in v]
        print(
            f"saved {len(manifest['worlds'])} entries; refusals {refused}; builder errors {errors}"
        )
    else:
        tolerances = json.loads(args.tolerance.read_text()) if args.tolerance else {}
        report = compare(args.base, args.other, tolerances)
        if args.output:
            args.output.write_text(json.dumps(report, indent=1) + "\n")
        print(
            f"{report['verdict']}: {report['equal']} of {report['worlds']} worlds equal; "
            f"problems {len(report['problems'])}"
        )
        return 0 if report["verdict"] != "differs" else 1


if __name__ == "__main__":
    sys.exit(main())
