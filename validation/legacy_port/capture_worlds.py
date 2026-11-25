"""The captures that a re-expression of the used legacy worlds is judged against (section 8 of the
legacy port plan): the definitions, the jobs and one shard of their run.

It runs from a checkout against a frozen snapshot (PYTHONPATH=SNAPSHOT/src:SNAPSHOT) and records
both revisions. capture.sh drives it. It reads no reference and no result: it writes definitions,
runs the snapshot's own run paths in one process per job, and records hashes, sizes, exit codes and
timings. Nothing is tuned: a definition differs from its source only in `execution.dt` (h, h/2, h/4)
and, for the assembly worlds, in the pools' seeds. A refusal is recorded, never worked around.

The science set (`science`), each world at h, h/2 and h/4, where h is its source's own step:
- the four calcium clusters' ionic children (spatial_calcium@1 to @4);
- the JUPITER readiness check's world (spatial_extracellular@2), with both arms of the check
  (validation/ensemble/jupiter_check.py): the configuration as it is, and its pump release;
- the four assembly-regulated calcium clusters, the cluster's base and the cell family, four seeds
  each, on the assembly command lines with the CPU backend.

The check (`check`): the first steps of each captured world at h, one seed. They are taken with the
captures, and again at a later snapshot from the same definitions, and compared bit for bit
(`compare`). It shows, instead of assuming, that the commits landed between the two snapshots do
not reach the captured worlds.

The bitwise windows (`windows`): the first window, at most 200 steps, of every world on a kept ID.
They prove a move or a prune, not a re-expression, and depend on the route.

What "every recorded array" is:
- an ionic job saves, for each window of at most WINDOW_STEPS steps, the accepted times, the
  complete state at every accepted step, every observation field, the diagnostics and the final
  state (results_baseline.result_arrays). One window of the whole run is refused at h/2 and h/4 of
  the calcium worlds by their own execution.max_trace_bytes, so a run is saved window by window;
- an assembly job saves what its command line records: the final checkpoint and, for a cluster, a
  JSON summary at each observation time.

Actions:
  write SNAPSHOT ORIGIN      the definitions, jobs-{science,check,windows}.json and manifest.json
                             (with the admission of each definition, checked by parsing it)
  ionic DEFINITION OUT       one ionic job, in this process [--window-steps N] [--max-windows N]
  shard SNAPSHOT ORIGIN OUT SET   claim and run jobs until none is left (one per CPU; capture.sh)
  finish SNAPSHOT ORIGIN OUT SET  MANIFEST.json (every file's sha256) and EXIT
  compare BASE OTHER [--science OUT] [--output FILE]   two outputs of the same set, bit for bit;
                             --science also ties BASE's check to the science runs at h from the same
                             snapshot (the ionic rows, the clusters' summaries at the same ticks)
"""

import argparse
import contextlib
import copy
import hashlib
import io
import json
import os
import platform
import shutil
import signal
import subprocess
import sys
import time
import traceback
from datetime import UTC, datetime
from pathlib import Path

CHECKOUT = Path(__file__).resolve().parents[2]
KIND = "cells.legacy_captures@1"
REDUCTIONS = {"h": 1, "h2": 2, "h4": 4}
WINDOW_STEPS = 256  # The engine's own default window (WindowPolicy).
BITWISE_STEPS = 200  # results_baseline's own first window.
CHECK_STEPS = 64  # Past the off-grid observation and, in the pump release, the first pump change.
SEEDS, SEED_STRIDE = 4, 1000  # Cell streams add 0 and 1 to a seed, so the bases stand apart.
DISK_RESERVE = 50 * 1024**3  # No job starts with less than this free on the output's filesystem.

IONIC = {
    "spatial_calcium": "spatial_calcium_cluster",
    "plasma_calcium": "plasma_calcium_cluster",
    "gated_calcium": "gated_calcium_cluster",
    "ip3_calcium": "ip3_calcium_cluster",
    "jupiter_baseline": "spatial_kinetic_cluster",
    "jupiter_pump_release": "spatial_kinetic_cluster",
}
CLUSTER = "assembly-cluster"
ORDER = {"assembly-cell": 10**6, CLUSTER: 10**5}  # The slowest first (the pilot's compile times).
ASSEMBLY = {
    "cluster_ip3_calcium": (CLUSTER, "assembly_regulated_ip3_calcium_cluster"),
    "cluster_gated_calcium": (CLUSTER, "assembly_regulated_gated_calcium_cluster"),
    "cluster_plasma_calcium": (CLUSTER, "assembly_regulated_plasma_calcium_cluster"),
    "cluster_spatial_calcium": (CLUSTER, "assembly_regulated_calcium_cluster"),
    "cluster_base": (CLUSTER, "assembly_regulated_cluster"),
    "cell": ("assembly-cell", "assembly_regulated_cell"),
}
# The bitwise windows: every configuration on an ID that the plan's kept core holds, and on the
# three resolved_tissue versions whose dispatch moves to the live registry.
WINDOW_IONIC = (
    "spatial_calcium_cluster",  # spatial_calcium@1
    "plasma_calcium_cluster",  # spatial_calcium@2
    "gated_calcium_cluster",  # spatial_calcium@3
    "ip3_calcium_cluster",  # spatial_calcium@4
    "er_calcium_buffered",  # er_calcium@1
    "calcium_buffer_compartments",  # compartment_reactions@1
    "spatial_kinetic_cluster",  # spatial_extracellular@2
    "kinetic_finite_cell",  # finite_extracellular@2
    "junction_finite_cluster",  # finite_extracellular@3
    "resolved_tissue",  # resolved_tissue@1
    "resolved_tissue_excision_source",  # resolved_tissue@1
    "resolved_kinetic_tissue",  # resolved_tissue@2
    "resolved_catalog_tissue",  # resolved_tissue@8
)


# ---------------------------------------------------------------------------------- utilities


def utc():
    return datetime.now(UTC).isoformat(timespec="seconds")


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=1, allow_nan=False) + "\n")


def read_json(path):
    return json.loads(Path(path).read_text())


def tree_bytes(top):
    total = 0
    for folder, _, names in os.walk(top):
        for name in names:
            with contextlib.suppress(FileNotFoundError):
                total += os.lstat(os.path.join(folder, name)).st_size
    return total


def snapshot_record(snapshot):
    manifest = snapshot / "SNAPSHOT.json"
    value = read_json(manifest)
    return dict(
        path=str(snapshot),
        git_revision=value["git_revision"],
        clean=value["selected_status_porcelain_v1_z"] == "",
        patch_sha256=value["patch_sha256"],
        manifest_sha256=sha256(manifest),
    )


def tool_record():
    """This checkout's revision, whether the tool's folder differs from it, and its file hashes."""
    here = Path(__file__).resolve().parent
    git = ["git", "--no-optional-locks", "-C", str(CHECKOUT)]

    def run(*args):
        return subprocess.run([*git, *args], capture_output=True, text=True).stdout.strip()

    return dict(
        revision=run("rev-parse", "HEAD"),
        dirty=run("status", "--porcelain", "--", str(here)),
        files={p.name: sha256(p) for p in sorted(here.glob("capture*"))},
    )


# ---------------------------------------------------------------------------------- definitions


def config(snapshot, name):
    return read_json(snapshot / f"configs/{name}.json")


def at_step(definition, reduction, ionic=None):
    """The definition with its ionic step divided by `reduction` (exact: a power of two)."""
    out = copy.deepcopy(definition)
    (out if ionic is None else out[ionic])["execution"]["dt"] /= reduction
    return out


def pump_release(definition):
    """The JUPITER readiness check's second arm (jupiter_check.spatial_definitions), on the CPU."""
    out = copy.deepcopy(definition)
    for control in out["experiment"]["membrane_controls"]:
        control["pump"] = [
            {"multiplier": 1.0, "time": 0.0},
            {"multiplier": 0.0, "time": 0.005},
            {"multiplier": 1.0, "time": 0.01},
        ]
    return out


def at_seed(definition, index, default_seed):
    """The definition's `index`th seed: each pool's own seed plus a multiple of SEED_STRIDE, so a
    cluster's cells keep seed = ensemble seed + stream."""
    out = copy.deepcopy(definition)
    for pool in [out["pool"]] if "pool" in out else [p["pool"] for p in out["pools"]]:
        pool["seed"] = (pool.get("seed", default_seed) + index * SEED_STRIDE) % 2**32
    return out


def differences(a, b, path=""):
    """[(path, a's value or length, b's)] where two JSON values differ."""
    if type(a) is not type(b):
        return [(path, str(a)[:80], str(b)[:80])]
    if isinstance(a, dict):
        out = []
        for key in sorted(set(a) | set(b)):
            if key not in a or key not in b:
                out.append((f"{path}/{key}", key in a, key in b))
            else:
                out += differences(a[key], b[key], f"{path}/{key}")
        return out
    if isinstance(a, list) and len(a) == len(b):
        return [
            d
            for i, (x, y) in enumerate(zip(a, b, strict=True))
            for d in differences(x, y, f"{path}/{i}")
        ]
    return [] if a == b else [(path, str(a)[:80], str(b)[:80])]


def admit_ionic(definition):
    """Steps, and whether the window planner admits one window of the whole run and WINDOW_STEPS."""
    from cells.definitions.specs import parse_spec
    from cells.execution.grid import EventGrid
    from cells.execution.windows import WindowPolicy, plan_windows

    try:
        spec = parse_spec(definition)
        steps = len(EventGrid(spec)) - 1
    except Exception as error:  # A refusal is a finding, recorded.
        return dict(refused=f"{type(error).__name__}: {error}"[:400])
    out = dict(steps=steps, end_time=spec.experiment.end_time)
    for name, width in (("whole", steps), ("windowed", min(WINDOW_STEPS, steps))):
        try:
            plan = plan_windows(spec, WindowPolicy(width, "checkpoints"))
            out[name] = dict(admitted=True, window_steps=width, bytes=plan.estimated_working_bytes)
        except Exception as error:
            out[name] = dict(admitted=False, window_steps=width, refusal=str(error)[:200])
    return out


def admit_assembly(command, path):
    """The command line's own `validate` of a definition (its ticks and worlds), in this process."""
    from cells.__main__ import main

    text, errors = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(text), contextlib.redirect_stderr(errors):
        code = main([command, "validate", str(path)])
    if code != 0:
        return dict(refused=errors.getvalue()[:400])
    value = json.loads(text.getvalue())
    return {k: value[k] for k in ("ticks", "worlds", "working_bytes", "definition_sha256")}


def write(snapshot, origin):
    """Every definition, the two job lists and the manifest, in a new folder."""
    from cells.assembly_pool.spec import PoolSpec

    origin.mkdir(parents=True, exist_ok=False)
    default_seed = PoolSpec().seed
    jobs, worlds = [], {}
    for world, source in IONIC.items():
        raw = config(snapshot, source)
        if world == "jupiter_pump_release":
            raw = pump_release(raw)
        row = worlds[world] = dict(config=f"configs/{source}.json", kind="ionic", steps={})
        for step, reduction in REDUCTIONS.items():
            definition = at_step(raw, reduction)
            path = f"science/ionic/{world}/{step}.json"
            write_json(origin / path, dict(name=step, definition=definition))
            admission = admit_ionic(definition)
            row["steps"][step] = dict(dt=definition["execution"]["dt"], **admission)
            jobs.append(
                dict(
                    job=f"{world}-{step}",
                    kind="ionic",
                    definition=path,
                    world=world,
                    step=step,
                    order=admission.get("steps", 0),
                )
            )
    for world, (command, source) in ASSEMBLY.items():
        raw = config(snapshot, source)
        row = worlds[world] = dict(config=f"configs/{source}.json", kind=command, steps={})
        for step, reduction in REDUCTIONS.items():
            for index in range(SEEDS):
                definition = at_seed(at_step(raw, reduction, "ionic"), index, default_seed)
                path = f"science/assembly/{world}/{step}-s{index}.json"
                write_json(origin / path, definition)
                if index == 0:
                    admission = admit_assembly(command, origin / path)
                    row["steps"][step] = dict(
                        dt=definition["ionic"]["execution"]["dt"], **admission
                    )
                jobs.append(
                    dict(
                        job=f"{world}-{step}-s{index}",
                        kind="assembly",
                        command=command,
                        definition=path,
                        world=world,
                        step=step,
                        seed_index=index,
                        ticks=admission.get("ticks"),
                        order=ORDER[command] + (admission.get("ticks") or 0),
                    )
                )
        row["seeds"] = [
            [p["seed"] for p in ([d["pool"]] if "pool" in d else [x["pool"] for x in d["pools"]])]
            for d in (at_seed(raw, i, default_seed) for i in range(SEEDS))
        ]
    write_json(origin / "jobs-science.json", sorted(jobs, key=lambda j: -j["order"]))

    checks = [
        dict(
            job=f"check-{world}",
            kind="ionic",
            definition=f"science/ionic/{world}/h.json",
            world=world,
            first_steps=CHECK_STEPS,
        )
        for world in IONIC
    ]
    for world, (command, source) in ASSEMBLY.items():
        ion = config(snapshot, source)["ionic"]
        until = min(t for t in ion["experiment"]["observation_times"] if t > 0)
        checks.append(
            dict(
                job=f"check-{world}",
                kind="assembly",
                command=command,
                definition=f"science/assembly/{world}/h-s0.json",
                world=world,
                until=until,
                ticks=round(until / ion["execution"]["dt"]),
            )
        )
    write_json(origin / "jobs-check.json", checks[::-1])  # The cell family, the slowest, first.

    window_jobs = []
    for source in WINDOW_IONIC:
        path = f"windows/ionic/{source}/h.json"
        write_json(origin / path, dict(name="h", definition=config(snapshot, source)))
        window_jobs.append(dict(job=f"window-{source}", kind="window", definition=path, set=source))
    for world, (command, source) in ASSEMBLY.items():
        raw = config(snapshot, source)
        path = f"windows/assembly/{world}.json"
        write_json(origin / path, raw)
        until = min(
            BITWISE_STEPS * raw["ionic"]["execution"]["dt"],
            raw["ionic"]["experiment"]["end_time"],
        )
        window_jobs.append(
            dict(
                job=f"window-{world}",
                kind="assembly",
                command=command,
                definition=path,
                until=until,
                ticks=round(until / raw["ionic"]["execution"]["dt"]),
            )
        )
    write_json(origin / "jobs-windows.json", window_jobs)

    nested = {}
    for source, assembly in (
        ("spatial_calcium_cluster", "assembly_regulated_calcium_cluster"),
        ("plasma_calcium_cluster", "assembly_regulated_plasma_calcium_cluster"),
        ("gated_calcium_cluster", "assembly_regulated_gated_calcium_cluster"),
        ("ip3_calcium_cluster", "assembly_regulated_ip3_calcium_cluster"),
        ("spatial_kinetic_cluster", "assembly_regulated_cluster"),
    ):
        nested[f"{source} against {assembly}.ionic"] = differences(
            config(snapshot, source), config(snapshot, assembly)["ionic"]
        )
    write_json(
        origin / "manifest.json",
        dict(
            kind=KIND,
            utc=utc(),
            snapshot=snapshot_record(snapshot),
            tool=tool_record(),
            changed_only=["execution.dt", "pool seeds (assembly worlds)"],
            worlds=worlds,
            nested_ionic_differences=nested,
            configs_sha256={
                f"configs/{n}.json": sha256(snapshot / f"configs/{n}.json")
                for n in sorted(
                    {*IONIC.values(), *(s for _, s in ASSEMBLY.values()), *WINDOW_IONIC}
                )
            },
            files_sha256={
                str(p.relative_to(origin)): sha256(p)
                for p in sorted(origin.rglob("*.json"))
                if p.name != "manifest.json"
            },
        ),
    )
    print(f"{len(jobs)} science jobs and {len(window_jobs)} bitwise windows in {origin}")


# ---------------------------------------------------------------------------------- one ionic job


def ionic(definition, out, window_steps, max_windows=None):
    """Run one ionic world window by window, saving every array of each window."""
    import jax
    import numpy as np

    jax.config.update("jax_enable_x64", True)
    from cells.definitions.specs import parse_spec
    from cells.execution.windows import WindowPolicy, iter_windows
    from validation.results_baseline import result_arrays

    out.mkdir(parents=True, exist_ok=False)
    record = dict(
        kind=KIND,
        definition=str(definition),
        definition_sha256=sha256(definition),
        window_steps=window_steps,
        started=utc(),
        windows=[],
    )
    try:
        spec = parse_spec(read_json(definition)["definition"])
        record["fingerprint"] = spec.fingerprint
        began = time.perf_counter()
        policy = WindowPolicy(window_steps, "checkpoints")
        for index, window in enumerate(iter_windows(spec, policy)):
            computed = time.perf_counter()
            arrays = result_arrays(window)
            path = out / f"window-{index:04d}.npz"
            np.savez_compressed(path, **arrays)
            record["windows"].append(
                dict(
                    steps=len(window.times) - 1,
                    arrays=len(arrays),
                    raw_bytes=int(sum(a.nbytes for a in arrays.values())),
                    saved_bytes=path.stat().st_size,
                    run_seconds=computed - began,
                    save_seconds=time.perf_counter() - computed,
                    timings={k: float(v) for k, v in window.timings.items()},
                )
            )
            record["final_time"] = float(window.final.time)
            record["final_step"] = int(window.final.step_index)
            if max_windows and index + 1 >= max_windows:
                break
            began = time.perf_counter()
        record["end_time"] = float(spec.experiment.end_time)
        record["complete"] = record["final_time"] == record["end_time"]
    except Exception as error:  # A refusal is an output: its type and message.
        record["refusal"] = dict(
            type=type(error).__name__,
            message=str(error)[:4000],
            traceback=traceback.format_exc()[-4000:],
        )
    record.update(
        finished=utc(),
        environment=dict(
            jax=jax.__version__,
            devices=[str(d) for d in jax.devices()],
            python=platform.python_version(),
            cpu_affinity=sorted(os.sched_getaffinity(0)),
        ),
    )
    write_json(out / "run.json", record)
    return 0 if record.get("complete") or (max_windows and "refusal" not in record) else 1


# ---------------------------------------------------------------------------------- shards


def command_line(snapshot, origin, out, job):
    """A job's output folder and its command."""
    python = [sys.executable, "-B"]
    definition = origin / job["definition"]
    target = out / "runs" / job["job"]
    if job["kind"] == "ionic":
        argv = [
            *python,
            str(Path(__file__).resolve()),
            "ionic",
            str(definition),
            str(target),
        ]
        if "first_steps" in job:
            argv += ["--window-steps", str(job["first_steps"]), "--max-windows", "1"]
        return target, argv
    if job["kind"] == "window":
        # results_baseline reads every definition in ORIGIN/SET and saves the first window.
        return target, [
            *python,
            str(snapshot / "validation/results_baseline.py"),
            "save",
            str(target),
            "--sets",
            job["set"],
            "--from",
            str(origin / "windows/ionic"),
            "--max-steps",
            str(BITWISE_STEPS),
        ]
    argv = [
        *python,
        "-m",
        "cells",
        job["command"],
        "run",
        str(definition),
        "--output",
        str(target),
        "--backend",
        "cpu",
    ]
    return target, argv + (["--until", repr(job["until"])] if "until" in job else [])


def drop_source_copy(snapshot, target):
    """The assembly command line copies the whole package into its output. Drop the copy when it is
    the snapshot's package, file by file (its files are read-only, as the snapshot's are); keep it,
    and say so, when it is not."""
    copied = target / "source" / "cells"
    if not copied.is_dir():
        return dict(present=False)
    files = [
        {
            str(p.relative_to(top)): sha256(p)
            for p in sorted(top.rglob("*"))
            if p.is_file() and "__pycache__" not in p.parts
        }
        for top in (copied, snapshot / "src" / "cells")
    ]
    mine, theirs = files
    if mine != theirs:
        return dict(present=True, equal=False, files=len(mine), kept=True)
    for path in (target / "source").rglob("*"):
        path.chmod(0o755 if path.is_dir() else 0o644)
    shutil.rmtree(target / "source")
    return dict(present=True, equal=True, files=len(mine), kept=False)


def outcome(job, target, code, timed_out):
    """(status, timings) of a finished job. Only clocks, counts and refusals are read."""
    if timed_out:
        return "failed: the job's time limit", {}
    try:
        if job["kind"] == "ionic":
            run = read_json(target / "run.json")
            timings = dict(
                steps=run.get("final_step"),
                windows=len(run["windows"]),
                run_seconds=sum(w["run_seconds"] for w in run["windows"]),
                save_seconds=sum(w["save_seconds"] for w in run["windows"]),
                compile_seconds=sum(
                    w["timings"].get("compile_or_cache_seconds", 0.0) for w in run["windows"]
                ),
            )
            if "refusal" in run:
                return (
                    f"refused: {run['refusal']['type']}: {run['refusal']['message'][:200]}",
                    {},
                )
            done = (
                run["final_step"] == job["first_steps"] if "first_steps" in job else run["complete"]
            )
            return ("ok" if done and code == 0 else "failed: incomplete"), timings
        if job["kind"] == "window":
            (row,) = read_json(target / "manifest.json")["worlds"].values()
            if row.get("refusal") or "builder_error" in row:
                return (
                    f"refused: {row.get('refusal') or row['builder_error'][:200]}",
                    {},
                )
            timings = dict(steps=row["steps"], seconds=row["seconds"])
            return ("ok" if code == 0 else "failed"), timings
        if (target / "failure.json").exists():
            return f"refused: {read_json(target / 'failure.json')['error'][:200]}", {}
        result = read_json(target / "result.json")
        timings = dict(result["phase_timings"], windows=result["windows"], tick=result["tick"])
        if code or not (target / "completion.json").exists() or result["tick"] != job["ticks"]:
            return "failed: incomplete", timings
        return "ok", timings
    except Exception as error:
        return f"failed: {type(error).__name__}: {error}"[:300], {}


def run_job(snapshot, origin, out, job, seconds):
    """One job in its own process group, with durable logs, a time limit and its record."""
    target, argv = command_line(snapshot, origin, out, job)
    logs = out / "logs"
    logs.mkdir(exist_ok=True)
    meter = logs / f"{job['job']}.time"
    full = ["/usr/bin/time", "-o", str(meter), "-f", "%e %U %S %M", *argv]
    started, began, timed_out = utc(), time.monotonic(), False
    with (
        (logs / f"{job['job']}.out").open("xb") as stdout,
        (logs / f"{job['job']}.err").open("xb") as stderr,
    ):
        child = subprocess.Popen(
            full,
            cwd=out,
            stdin=subprocess.DEVNULL,
            stdout=stdout,
            stderr=stderr,
            start_new_session=True,
        )
        try:
            code = child.wait(timeout=seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(child.pid, signal.SIGKILL)
            code = child.wait()
    status, timings = outcome(job, target, code, timed_out)
    record = dict(
        job,
        status=status,
        exit=code,
        command=argv,
        started=started,
        finished=utc(),
        wall_seconds=time.monotonic() - began,
        timings=timings,
        cpu=sorted(os.sched_getaffinity(0)),
        definition_sha256=sha256(origin / job["definition"]),
    )
    with contextlib.suppress(Exception):
        elapsed, user, system, peak = meter.read_text().split("\n")[-2].split()
        record["process"] = dict(
            elapsed_s=float(elapsed),
            user_s=float(user),
            system_s=float(system),
            peak_rss_kb=int(peak),
        )
    if job["kind"] == "assembly":
        try:
            record["source_copy"] = drop_source_copy(snapshot, target)
        except Exception as error:  # The run's record stands whatever happens to the copy.
            record["source_copy"] = dict(error=f"{type(error).__name__}: {error}"[:300])
    record["bytes"] = tree_bytes(target) if target.exists() else 0
    write_json(out / "jobs" / f"{job['job']}.json", record)
    print(
        f"{utc()} {job['job']}: {status} ({record['wall_seconds']:.0f} s, {record['bytes']} bytes)",
        flush=True,
    )


def shard(snapshot, origin, out, name, cap_bytes, seconds):
    """Claim jobs in order, the largest first, until none is left. One job's failure or refusal
    stops no other; a job is not started once the set has reached its byte cap."""
    claims = out / "claims"
    claims.mkdir(exist_ok=True)
    for job in read_json(origin / f"jobs-{name}.json"):
        try:
            (claims / job["job"]).mkdir()
        except FileExistsError:
            continue
        used, free = tree_bytes(out), shutil.disk_usage(out).free
        if used >= cap_bytes or free < DISK_RESERVE:
            why = f"{used} bytes against the cap of {cap_bytes}, {free} free"
            write_json(out / "jobs" / f"{job['job']}.json", dict(job, status=f"not run: {why}"))
            continue
        try:
            run_job(snapshot, origin, out, job, seconds)
        except Exception as error:  # The driver's own fault, on this job only.
            write_json(
                out / "jobs" / f"{job['job']}.json",
                dict(job, status=f"failed: the driver: {type(error).__name__}: {error}"),
            )


def finish(snapshot, origin, out, name):
    """MANIFEST.json, and EXIT: 0 when every job is ok, 1 otherwise."""
    jobs = []
    for job in read_json(origin / f"jobs-{name}.json"):
        path = out / "jobs" / f"{job['job']}.json"
        jobs.append(read_json(path) if path.exists() else dict(job, status="not run: no record"))
    counts = {}
    for job in jobs:
        key = job["status"].split(":")[0]
        counts[key] = counts.get(key, 0) + 1
    code = 0 if counts.get("ok") == len(jobs) else 1
    steps = str(snapshot / "scripts/gates/gate_steps.py")
    entries = subprocess.run(
        [sys.executable, "-B", steps, "jax-entries", str(out)],
        capture_output=True,
        text=True,
    )
    entries = json.loads(entries.stdout) if entries.stdout else entries.stderr[:400]
    files = {}
    for path in sorted(out.rglob("*")):
        if path.is_file() and path.name not in ("MANIFEST.json", "EXIT"):
            files[str(path.relative_to(out))] = dict(bytes=path.stat().st_size, sha256=sha256(path))
    write_json(
        out / "MANIFEST.json",
        dict(
            kind=KIND,
            set=name,
            utc=utc(),
            snapshot=snapshot_record(snapshot),
            tool=tool_record(),
            origin=dict(
                path=str(origin),
                manifest_sha256=sha256(origin / "manifest.json"),
                snapshot=read_json(origin / "manifest.json")["snapshot"],
            ),
            run=read_json(out / "started.json"),
            counts=counts,
            jobs=jobs,
            jax_cache_entries=entries,
            bytes=sum(f["bytes"] for f in files.values()),
            files=files,
        ),
    )
    (out / "EXIT").write_text(f"{code} {utc()} {json.dumps(counts, sort_keys=True)}\n")
    print(f"EXIT {code}: {counts}")
    return code


# ---------------------------------------------------------------------------------- compare


def saved_arrays(folder):
    """{"FILE:KEY": array} of every array file under a run's folder."""
    import numpy as np

    out = {}
    for path in sorted(folder.rglob("*.npz")):
        with np.load(path, allow_pickle=False) as arrays:
            for key in arrays.files:
                out[f"{path.relative_to(folder)}:{key}"] = arrays[key]
    return out


def saved_summaries(folder):
    """The observation summaries a cluster run records, as JSON values."""
    return {p.name: read_json(p) for p in sorted((folder / "observations").glob("*.json"))}


def same_bits(a, b):
    return a.dtype == b.dtype and a.shape == b.shape and a.tobytes() == b.tobytes()


def compare_job(base, other):
    """The differing array keys and observation summaries of two runs' folders."""
    x, y = saved_arrays(base), saved_arrays(other)
    differing = [
        k
        for k in sorted(x.keys() | y.keys())
        if k not in x or k not in y or not same_bits(x[k], y[k])
    ]
    p, q = saved_summaries(base), saved_summaries(other)
    differing += [f"observations/{k}" for k in sorted(p.keys() | q.keys()) if p.get(k) != q.get(k)]
    return dict(arrays=len(x), summaries=len(p), differing=differing[:20], count=len(differing))


def compare(base, other, science=None):
    """Two outputs of one set, job by job, bit for bit: the same jobs, all ok in both, from the same
    definitions, with every array and every observation summary equal."""
    a, b = read_json(base / "MANIFEST.json"), read_json(other / "MANIFEST.json")
    rows, mine = [], {j["job"]: j for j in a["jobs"]}
    theirs = {j["job"]: j for j in b["jobs"]}
    for name in sorted(mine.keys() | theirs.keys()):
        x, y = mine.get(name, {}), theirs.get(name, {})
        row = dict(job=name)
        if x.get("status") != "ok" or y.get("status") != "ok":
            row["problem"] = f"not ok in both: {x.get('status')!r}, {y.get('status')!r}"
        elif x["definition_sha256"] != y["definition_sha256"]:
            row["problem"] = "the definitions differ"
        else:
            row |= compare_job(base / "runs" / name, other / "runs" / name)
            if not row["arrays"]:
                row["problem"] = "no arrays"
        row["identical"] = "problem" not in row and row["count"] == 0
        rows.append(row)
    report = dict(
        kind=KIND,
        utc=utc(),
        set=[a["set"], b["set"]],
        base=dict(path=str(base), snapshot=a["snapshot"]),
        other=dict(path=str(other), snapshot=b["snapshot"]),
        jobs=rows,
        identical=bool(rows) and a["set"] == b["set"] and all(r["identical"] for r in rows),
    )
    if science is not None:
        report["science_rows"] = science_rows(base, science, a)
        report["identical"] &= all(r["identical"] for r in report["science_rows"])
    return report


def science_rows(base, science, manifest):
    """Each check job against the science run at h that it is the start of: an ionic job's accepted
    rows against the first rows of the first window, and a cluster job's observation summaries
    against those at the same ticks (seed 0). The cell family records no summary, so its check is
    tied to the science run by the snapshot and the definition alone (`linked` is false)."""
    rows = []
    for job in manifest["jobs"]:
        mine = base / "runs" / job["job"]
        row = dict(job=job["job"], compared=0, differing=[], linked=True)
        if job["kind"] == "ionic":
            theirs = science / "runs" / f"{job['world']}-h"
            x, y = saved_arrays(mine), saved_arrays(theirs)
            keys = [k for k in x if k.split(":")[1].split(".")[0] in ("times", "history")]
            n = job["first_steps"] + 1
            row["differing"] = [k for k in keys if k not in y or not same_bits(x[k], y[k][:n])]
        else:
            x = saved_summaries(mine)
            y = saved_summaries(science / "runs" / f"{job['world']}-h-s0")
            keys = sorted(x)
            row["differing"] = [k for k in keys if x[k] != y.get(k)]
            row["linked"] = bool(keys)
        row.update(compared=len(keys), differing=row["differing"][:20])
        row["identical"] = not row["differing"] and (bool(keys) or not row["linked"])
        rows.append(row)
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="action", required=True)
    one = sub.add_parser("write")
    two = sub.add_parser("ionic")
    two.add_argument("definition", type=Path)
    two.add_argument("out", type=Path)
    two.add_argument("--window-steps", type=int, default=WINDOW_STEPS)
    two.add_argument("--max-windows", type=int, help="stop early (a pilot)")
    three, four = sub.add_parser("shard"), sub.add_parser("finish")
    for p in (one, three, four):
        p.add_argument("snapshot", type=Path)
        p.add_argument("origin", type=Path)
    for p in (three, four):
        p.add_argument("out", type=Path)
        p.add_argument("set", choices=("science", "check", "windows"))
    three.add_argument("--cap-bytes", type=int, required=True)
    three.add_argument("--job-seconds", type=int, required=True)
    five = sub.add_parser("compare")
    five.add_argument("base", type=Path)
    five.add_argument("other", type=Path)
    five.add_argument("--science", type=Path)
    five.add_argument("--output", type=Path)
    a = parser.parse_args(argv)
    if a.action == "compare":
        science = a.science.resolve() if a.science else None
        report = compare(a.base.resolve(), a.other.resolve(), science)
        if a.output:
            write_json(a.output, report)
        bad = [r["job"] for r in report["jobs"] if not r["identical"]]
        print(f"identical {report['identical']}: {len(report['jobs'])} jobs, differing {bad}")
        return 0 if report["identical"] else 1
    if a.action == "write":
        write(a.snapshot.resolve(), a.origin.resolve())
        return 0
    if a.action == "ionic":
        return ionic(a.definition.resolve(), a.out.resolve(), a.window_steps, a.max_windows)
    places = [p.resolve() for p in (a.snapshot, a.origin, a.out)]
    if a.action == "shard":
        shard(*places, a.set, a.cap_bytes, a.job_seconds)
        return 0
    return finish(*places, a.set)


if __name__ == "__main__":
    sys.exit(main())
