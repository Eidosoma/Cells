"""FR-38's second registered comparison: the engine side's runs and their table (the builder's).

The protocol's §6, steps 7 and 8: fresh runs from a clean frozen snapshot, detached, one thread
each, cold, the plants in their own processes; then the table, built from the engine runs alone
and hashed before any reference value is read. Nothing here reads a reference.

**One run** (`run`, one process each): a world of worlds.py (a registered run, a support run or
a plant) at its step, run windowed (POLICY), its readouts exported by
validation/gene_regulation/engine_run.readouts under READOUTS.md §1's names, the C and D exports
included. Its record holds the definition, the source's identity (engine_run.provenance: the
revision, the dirty diff or the frozen snapshot), the readouts, engine_run's checks and the
operator's own ledgers at the end. A run the engine refuses writes its refusal instead.

**The restart** (`restart`, CRITERIA.md §1): AN's p_sched returned at h, run to 7200 s, its
checkpoint written and read back through the snapshot files (cells.records.io), and resumed to
14,400 s. Its record is the whole run's, from both parts, by the same export, so the judge can
hold it to the uninterrupted run bit for bit. Every run takes POLICY, whose windows end at the
join.

**The plants** (CRITERIA.md §6): the world-data plants are worlds.PLANTS, each its own run at h.
P9 runs D's p_sched returned with templated_polymerisation@1's half-step patched in this process
only to drop the reader view the composite passes, so the gene unit reads the declared volume V0
for every concentration and booking while water reads the current one (FR-43's V0 plant form,
validation/tissue/shared_inventory_references.planted_c28). Its definition is its honest run's, so
its record names the patch (`host_patch`, HOST_PATCHES; amendment 4, §8.4). The judge forms P1,
P1′, P1″ and P6 itself from the honest records (amendment 4, item 5), so the table carries none.

**The table** (`table`): one file per family, from the records alone:
- per rung, each run's series under READOUTS.md §1's names, its definition, checks, ledgers and
  step count;
- READOUTS.md §2's host-side quantities:
  - `released_present_gross_<fate>`, the sum of the three released classes;
  - route 2 at each sample time, cohort.known_rate on the run's release counter at the fate's
    declared k_f, with its grid error (cohort.known_rate_error, LAWS.md §6);
  - `excess_over_blank_<fate>`, the run's row minus its blank's at the same step (AF's blank of
    the same machine option; elsewhere the blank);
  - route 1's survival readout (cohort.label_survival on the `win` class), its ratio None at a
    zero count;
- the restart and the plants, each in a run entry's form, the restart's with its checkpoint and
  each plant's with `judged_as` and `host_patch`.

This is the engine export contract that amendment 4, §8 registers.

SHA256SUMS lists each table file's sha256, written with the tables.

Run with /mnt/workspaces/Cells/venv-cpu/bin/python, PYTHONPATH=src:. and JAX_ENABLE_X64=1:
- `python -m validation.gene_regulation.fr38_v2.campaign plan [--retry]` prints the runs;
- `... campaign run --family F --run NAME --dt S --out DIR` makes one run;
- `... campaign run --plant NAME --out DIR` makes one plant;
- `... campaign restart --out DIR` makes the restart;
- `... campaign launch --out DIR --cpus 6,7 [--retry] [--only F ...]` makes every planned run, one
  process each, one per CPU at a time;
- `... campaign table --out DIR` builds and hashes the tables.

The judged campaign waits for the lead's go: it is about 85 runs, 8 to 12 CPU-hours (the
protocol's §7), queued behind other registered runs.
"""

import argparse
import contextlib
import hashlib
import json
import os
import subprocess
import sys
import time
import traceback
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from cells.definitions.specs import parse_spec
from cells.execution.windows import WindowPolicy, iter_windows
from validation.gene_regulation import cohort, engine_run
from validation.gene_regulation.fr38_v2 import worlds

WINDOW_STEPS = 2400  # 1200 s at h: the restart's join, 7200 s, ends a window
POLICY = WindowPolicy(window_steps=WINDOW_STEPS, recording="observations")
RECORD = "cells.fr38_v2.engine_run@1"
TABLE = "cells.fr38_v2.engine_table@1"
FATES = {"durable": "R", "short_lived": "R_s"}
RELEASED = ("pre", "win", "post")
V0_PLANT = "P9"
# The host-side patch a plant runs under (CRITERIA.md §6). P9's definition is its honest run's, so
# its record names the patch (amendment 4, §8.4); a world-data plant's is null.
HOST_PATCHES = {
    V0_PLANT: dict(
        id="V0",
        operator="templated_polymerisation@1",
        change=("the gene unit's half-step drops the reader view the composite passes, so it reads "
                "the declared volume V0 = 1.0 pL for every concentration and booking, while water "
                "reads the current volume (FR-43's V0 plant form, keeping the half-step's labels)"),
        code="validation.gene_regulation.fr38_v2.campaign.v0_patch",
    ),
}  # fmt: skip


def plant_identity(name):
    """A plant's record identity: its family, honest run, judged_as and host_patch."""
    family, run, judged_as, _ = worlds.PLANTS[name]
    return dict(family=family, run=run, plant=name, judged_as=judged_as,
                host_patch=HOST_PATCHES.get(name))  # fmt: skip


def slug(text):
    return engine_run.slug(text)


# ------------------------------------------------------------------ one run


def collect(spec, policy=POLICY, checkpoint=None, stop=None):
    """({step: state} at each observed step, the last window's final checkpoint), stopping after
    the window that ends at `stop` (s)."""
    dt = spec.execution.dt
    wanted = {int(round(float(t) / dt)) for t in spec.experiment.observation_times}
    states, final = {}, None
    for window in iter_windows(spec, policy, checkpoint):
        for i, _ in enumerate(np.asarray(window.times)):
            k = window.start_step + i
            if k in wanted:
                states[k] = type(window.history)(*(np.asarray(v)[i] for v in window.history))
        final = window.final
        if stop is not None and float(final.time) >= stop - 1e-9:
            break
    return states, final


def _record(raw, spec, states, wall, **identity):
    times, values, checks = engine_run.readouts(spec, states)
    return dict(
        kind=RECORD,
        **identity,
        cell=checks["exported_cell"],
        dt_s=float(spec.execution.dt),
        steps=int(round(float(spec.experiment.end_time) / spec.execution.dt)),
        wall_s=wall,
        t=times,
        readouts=values,
        checks=checks,
        own_ledgers_at_end=engine_run.own_ledgers(spec, states[max(states)]),
        definition=raw,
    )


@contextlib.contextmanager
def v0_patch():
    """P9 (CRITERIA.md §6, FR-43's V0 plant form): the gene unit's half-step drops the reader view,
    so it reads the declared volume V0, in this process only; the compiled programs are cleared
    before and after. The patched half-step keeps its signature's `labels`, so the label owner
    still finds the gene unit a reporter (contract.takes_labels reads the signature): only the
    volume it reads changes."""
    import jax

    from cells.operators.templated_polymerisation import TemplatedPolymerisation as op

    original = op.half_step

    def planted(self, state, h, control, p, *, xp, labels=None, view=None):
        return original(self, state, h, control, p, xp=xp, labels=labels)

    jax.clear_caches()
    op.half_step = planted
    try:
        yield
    finally:
        op.half_step = original
        jax.clear_caches()


def one(raw, policy=POLICY, **identity):
    """The record of one run of `raw` in this process, or its refusal (the engine's message)."""
    from cells.execution.errors import NumericalError

    spec = parse_spec(raw)
    started = time.perf_counter()
    try:
        states, _ = collect(spec, policy)
    except NumericalError as refusal:
        return dict(kind=RECORD, **identity, dt_s=float(spec.execution.dt), refused=True,
                    refusal=str(refusal)[:2000], wall_s=time.perf_counter() - started,
                    definition=raw)  # fmt: skip
    record = _record(raw, spec, states, time.perf_counter() - started, **identity)
    return record | {"refused": False}


def restart_record(raw, join, folder, policy=POLICY, **identity):
    """The restart (module docstring): to `join`, through the snapshot files in `folder`, then
    resumed; one record of the whole run by the same export, with the checkpoint's identity."""
    from cells.records.io import load_snapshot, write_snapshot

    spec = parse_spec(raw)
    dt = spec.execution.dt
    steps = join / dt
    if abs(steps - round(steps)) > 1e-9 or round(steps) % policy.window_steps:
        raise ValueError("the join must end a window of the policy")
    started = time.perf_counter()
    first, checkpoint = collect(spec, policy, stop=join)
    write_snapshot(Path(folder) / "snapshot", spec, checkpoint)
    snapshot = load_snapshot(Path(folder) / "snapshot")
    second, _ = collect(snapshot.spec, policy, checkpoint=snapshot.checkpoint)
    states = {**first, **second}
    record = _record(raw, spec, states, time.perf_counter() - started, **identity)
    record["checkpoint"] = dict(time_s=float(checkpoint.time), step_index=checkpoint.step_index,
                                event_index=checkpoint.event_index,
                                through="cells.records.io snapshot files")  # fmt: skip
    return record | {"refused": False}


def _write(path, record, source):
    path.parent.mkdir(parents=True, exist_ok=True)
    record = dict(record, source=source, created_utc=datetime.now(UTC).isoformat())
    path.write_text(json.dumps(record, indent=1, default=float) + "\n")
    return path


def _source(folder):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    source, patch = engine_run.provenance(folder)
    if patch is not None:
        (folder / "checkout.patch").write_text(patch)
    return source


def record_path(out, *, family=None, run=None, dt=None, plant=None, restart=False):
    out = Path(out) / "records"
    if plant is not None:
        return out / "plants" / f"{slug(plant)}.json"
    if restart:
        return out / "restart" / f"{family}-{slug(run)}.json"
    return out / family / f"dt{dt:g}" / f"{slug(run)}.json"


# ------------------------------------------------------------------ the plan


def plan(retry=False, families=("AF", "AN", "B", "C", "D")):
    """[job, ...]: every run of CRITERIA.md §1 at its rungs (the retry's for --retry), then the
    restart and the plants at h. A job is {"family", "run", "dt"}, {"restart": true} or
    {"plant"}."""
    rungs = worlds.RETRY_RUNGS if retry else worlds.RUNGS
    jobs = [dict(family=f, run=r, dt=dt) for f in families for dt in rungs for r in worlds.runs(f)]
    if not retry:
        family, run, _ = worlds.RESTART
        if family in families:
            jobs.append(dict(family=family, run=run, dt=worlds.H, restart=True))
        jobs += [dict(plant=name) for name, p in worlds.PLANTS.items() if p[0] in families]
    return jobs


def job_args(job):
    if "plant" in job:
        return ["run", "--plant", job["plant"]]
    if job.get("restart"):
        return ["restart"]
    return ["run", "--family", job["family"], "--run", job["run"], "--dt", repr(job["dt"])]


def job_path(out, job):
    if "plant" in job:
        return record_path(out, plant=job["plant"])
    if job.get("restart"):
        return record_path(out, family=job["family"], run=job["run"], restart=True)
    return record_path(out, family=job["family"], run=job["run"], dt=job["dt"])


def launch(out, cpus, jobs, parse_only=False):
    """Each job in its own process (a fresh, cold compile), one per CPU at a time, pinned to it.
    A job's stdout and stderr go to logs/; progress.json is rewritten after each finish.
    parse_only: each job parses its world and writes that, compiling nothing (the command line's
    own check, before the registration's tag)."""
    out = Path(out)
    (out / "logs").mkdir(parents=True, exist_ok=True)
    pending = [j for j in jobs if not job_path(out, j).exists()]
    running, done = {}, []
    env = dict(os.environ, JAX_ENABLE_X64="1", JAX_ENABLE_COMPILATION_CACHE="false")
    env.pop("JAX_COMPILATION_CACHE_DIR", None)
    while pending or running:
        for cpu in cpus:
            if cpu in running or not pending:
                continue
            job = pending.pop(0)
            name = slug(" ".join(job_args(job)[1:]) or "restart")
            log = (out / "logs" / f"{name}.log").open("w")
            command = ["taskset", "-c", str(cpu), sys.executable, "-m",
                       "validation.gene_regulation.fr38_v2.campaign", *job_args(job),
                       "--out", str(out), *(["--parse-only"] if parse_only else [])]  # fmt: skip
            proc = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, env=env)
            running[cpu] = (proc, job, time.time(), log)
        time.sleep(2)
        for cpu, (proc, job, began, log) in list(running.items()):
            if proc.poll() is None:
                continue
            log.close()
            done.append(dict(job=job, cpu=cpu, exit=proc.returncode, wall_s=time.time() - began))
            del running[cpu]
            (out / "progress.json").write_text(json.dumps(
                dict(done=done, pending=len(pending), running=len(running)), indent=1))  # fmt: skip
    return done


# ------------------------------------------------------------------ the table


def _definition_rate(definition, route):
    """A route's scheduled value at t = 0 (constant in these worlds) from a run's definition."""
    for control in definition["experiment"]["polymerisation_controls"]:
        if control["route_id"] == route:
            schedule = control["schedule"]
            if len(schedule) != 1:
                raise ValueError(f"{route}'s rate is not constant")
            return float(schedule[0]["value"])
    raise ValueError(f"no schedule for {route}")


def host_side(record, window, samples, blank=None):
    """READOUTS.md §2's quantities of one record (module docstring), for the window [t1, t2) and
    the sample times (t2 first)."""
    t, x = record["t"], record["readouts"]
    t1, t2 = window
    out = {"series": {}, "route2": [], "survival": []}
    labelled = all(f"label_{row}_win" in x for row in FATES.values())
    if not labelled:  # survival is a labelled run's (amendment 4, §8.3)
        del out["survival"]
    for fate, row in FATES.items():
        if labelled:
            parts = [x[f"label_{row}_{c}"] for c in RELEASED]
            out["series"][f"released_present_gross_{fate}"] = [
                (a + b) + c for a, b, c in zip(*parts, strict=True)
            ]
        Q = x[f"int_Q_tx_release_{fate}"]
        k = _definition_rate(record["definition"], f"deg_{row}")
        for ts in samples:
            out["route2"].append(dict(
                fate=fate, ts_s=ts, k_per_s=k, value=cohort.known_rate(t, Q, k, t1, t2, ts),
                grid_error=cohort.known_rate_error(t, Q, k, t1, t2, ts)))  # fmt: skip
        if labelled:
            for ts in samples[1:]:
                read = cohort.label_survival(t, x[f"label_{row}_win"], t2, ts)
                out["survival"].append(dict(
                    fate=fate, t2_s=t2, ts_s=ts, alive_t2=read["alive_at_window_end"],
                    alive_ts=read["alive_at_sample"], ratio=read["ratio"]))  # fmt: skip
        if blank is not None:
            base = blank["readouts"][f"n_{row}"]
            out.setdefault("excess_over_blank", {})[fate] = [
                a - b for a, b in zip(x[f"n_{row}"], base, strict=True)
            ]
    return out


def _window(family):
    return worlds.ARM_B.window if family == "B" else worlds.HOLDS[family].window


def _samples(family):
    return worlds.ARM_B.samples if family == "B" else worlds.HOLDS[family].samples


def _blank_of(family, run):
    """A run's matched blank (module docstring); None in B and for a blank."""
    if family == "B" or run.startswith("blank"):
        return None
    machine = run.split(" ")[1]
    return f"blank {machine}" if f"blank {machine}" in worlds.BLANKS[family] else "blank returned"


def _entry(record, path):
    entry = {k: record[k] for k in ("t", "readouts", "checks", "own_ledgers_at_end", "steps",
                                    "definition", "dt_s", "source")}  # fmt: skip
    entry["record"] = str(path)
    entry["record_sha256"] = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    return entry


def _refusal(record, path):
    return dict(refused=True, refusal=record["refusal"], definition=record["definition"],
                record=str(path))  # fmt: skip


def _usable(record):
    return record if record is not None and not record.get("refused") else None


def _run_entry(record, path, family, blank_name, blank):
    """A run's entry (amendment 4, §8.3): its record's keys, READOUTS.md §2's host-side quantities
    and its matched blank's name; or its refusal."""
    if record.get("refused"):
        return _refusal(record, path)
    entry = _entry(record, path)
    extra = host_side(record, _window(family), _samples(family), _usable(blank))
    entry["readouts"] = {**entry["readouts"], **extra.pop("series")}
    return entry | extra | {"blank": blank_name}


def _load(path):
    return json.loads(Path(path).read_text()) if Path(path).exists() else None


def build_table(out, family, rungs=worlds.RUNGS):
    """The family's table (module docstring) from the records under `out`."""
    out = Path(out)
    table = dict(kind=TABLE, family=family, window_s=list(_window(family)),
                 samples_s=list(_samples(family)), rungs={}, missing=[])  # fmt: skip
    for dt in rungs:
        records = {}
        for run in worlds.runs(family):
            path = record_path(out, family=family, run=run, dt=dt)
            record = _load(path)
            if record is None:
                table["missing"].append(str(path))
                continue
            records[run] = (record, path)
        rung = dict(dt_s=dt, runs={})
        for run, (record, path) in records.items():
            blank_name = _blank_of(family, run)
            blank = records.get(blank_name, (None,))[0] if blank_name else None
            rung["runs"][run] = _run_entry(record, path, family, blank_name, blank)
        table["rungs"][repr(dt)] = rung
    family_r, run_r, _ = worlds.RESTART
    if family == family_r and rungs == worlds.RUNGS:  # The same form, with its checkpoint (§8.4).
        path = record_path(out, family=family, run=run_r, restart=True)
        record = _load(path)
        blank_name = _blank_of(family, run_r)
        blank = _load(record_path(out, family=family, run=blank_name, dt=worlds.H))
        if record is None:
            table["restart"] = None
        else:
            table["restart"] = _run_entry(record, path, family, blank_name, blank)
            if not record.get("refused"):
                table["restart"]["checkpoint"] = record.get("checkpoint")
    table["plants"] = plants_table(out, family) if rungs == worlds.RUNGS else {}
    return table


def plants_table(out, family):
    """The world-data plants of `family`, each in a run entry's form with `judged_as` and
    `host_patch` (amendment 4, §8.4); null where the record is missing. P8's excess is its own
    planted blank's (amendment 1, item 4)."""
    found = {}
    for name, (fam, _run, judged_as, _) in worlds.PLANTS.items():
        if fam != family:
            continue
        path = record_path(out, plant=name)
        record = _load(path)
        if record is None:
            found[name] = None
            continue
        blank_name = "P8 blank" if name == "P8" else None
        blank = _load(record_path(out, plant=blank_name)) if blank_name else None
        found[name] = _run_entry(record, path, family, blank_name, blank) | {
            "judged_as": judged_as, "host_patch": record.get("host_patch")}  # fmt: skip
    return found


def table(out, families=("AF", "AN", "B", "C", "D"), retry=False):
    """Every family's table under out/table (out/table-retry with --retry), and their SHA256SUMS."""
    out = Path(out)
    folder = out / ("table-retry" if retry else "table")
    folder.mkdir(parents=True, exist_ok=True)
    sums = []
    for family in families:
        built = build_table(out, family, worlds.RETRY_RUNGS if retry else worlds.RUNGS)
        path = folder / f"table_{family}.json"
        path.write_text(json.dumps(built, sort_keys=True, separators=(",", ":"), default=float))
        sums.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}")
    (folder / "SHA256SUMS").write_text("\n".join(sums) + "\n")
    return folder


def _fabricated(raw, **identity):
    """A record with made-up counters on `raw`'s output grid (no engine run): positive rows far
    above every cumulative counter, each counter non-decreasing, and the labels summing to their
    rows. For table_check only."""
    t = [float(x) for x in raw["experiment"]["observation_times"]]
    horizon = t[-1]

    def grow(scale):
        return [scale * x / horizon for x in t]

    x = {f"n_{row}": [1.0 + 0.1 * s / horizon for s in t]
         for row in ("N", "M", "Pi", "R", "R_s", "Mx")}  # fmt: skip
    labelled = any(o["law"] == worlds.LABELS for o in raw["model"]["operators"])
    for fate, row in FATES.items():
        x[f"int_Q_tx_release_{fate}"] = grow(1e-3)
        x[f"int_D_{row}"] = grow(2e-3)
        shares = {"resyn": 0.1, "pool0": 0.6, "pre": 0.1, "win": 0.1, "post": 0.1}
        for c, share in shares.items() if labelled else ():  # A twin's record has no labels.
            x[f"label_{row}_{c}"] = [share * n for n in x[f"n_{row}"]]
    x["H_tx_release"] = [1e-3] * len(t)
    x["G_minus_G0"] = grow(-1.0)
    checks = dict(G_identity_largest_pJ=0.0, energy_magnitude_at_end_pJ=1.0, exported_cell="cell_0")
    record = dict(kind=RECORD, **identity, cell="cell_0", dt_s=raw["execution"]["dt"],
                  steps=int(round(horizon / raw["execution"]["dt"])), wall_s=0.0, t=t,
                  readouts=x, checks=checks, own_ledgers_at_end={}, definition=raw,
                  refused=False)  # fmt: skip
    if identity.get("restart"):  # As restart_record's: the checkpoint's identity.
        record["checkpoint"] = dict(time_s=worlds.RESTART[2], step_index=None, event_index=None,
                                    through="fabricated")  # fmt: skip
    return record


def table_check(out):
    """The table's code on fabricated records (no engine run): every planned job's record made up
    on its own registered definition, then every family's table built and hashed. Returns
    {family: summary}; raises on any fault."""
    out = Path(out)
    for job in plan():
        if "plant" in job:
            raw, identity = worlds.plant(job["plant"]), plant_identity(job["plant"])
        else:
            raw = worlds.world(job["family"], job["run"], dt=job["dt"])
            identity = dict(family=job["family"], run=job["run"], restart=job.get("restart"))
        _write(job_path(out, job), _fabricated(raw, **identity), {"fabricated": True})
    folder = table(out)
    summary = {}
    for family in ("AF", "AN", "B", "C", "D"):
        built = json.loads((folder / f"table_{family}.json").read_text())
        rungs = built["rungs"]
        runs = {name for rung in rungs.values() for name in rung["runs"]}
        host = next(iter(rungs.values()))["runs"][worlds.LABELLED[family][0]]
        restart = built.get("restart")
        summary[family] = dict(
            rungs=sorted(rungs), runs=len(runs), missing=built["missing"],
            route2=len(host["route2"]), survival=len(host["survival"]),
            excess="excess_over_blank" in host, plants=sorted(built["plants"]),
            restart="restart" in built,
            restart_form=None if restart is None else sorted(
                k for k in ("route2", "survival", "excess_over_blank", "checkpoint", "blank")
                if k in restart),
            twin_has_survival=any("survival" in rung["runs"][n] for rung in rungs.values()
                                  for n in rung["runs"] if n.endswith(worlds.UNLABELLED)),
            host_patches={k: (v or {}).get("host_patch") and v["host_patch"]["id"]
                          for k, v in built["plants"].items()})  # fmt: skip
        if built["missing"] or len(runs) != len(worlds.runs(family)):
            raise ValueError(f"{family}'s table misses runs: {built['missing']}")
    return summary


# ------------------------------------------------------------------ the command line


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=("plan", "run", "restart", "launch", "table"))
    parser.add_argument("--family")
    parser.add_argument("--run")
    parser.add_argument("--dt", type=float)
    parser.add_argument("--plant")
    parser.add_argument("--out")
    parser.add_argument("--cpus", default="6,7")
    parser.add_argument("--retry", action="store_true")
    parser.add_argument("--only", nargs="+", default=["AF", "AN", "B", "C", "D"])
    parser.add_argument("--parse-only", action="store_true", help="parse; run nothing")
    args = parser.parse_args(argv)
    if args.command == "plan":
        print(json.dumps(plan(args.retry, tuple(args.only)), indent=1))
        return 0
    out = Path(args.out)
    if args.command == "launch":
        jobs = plan(args.retry, tuple(args.only))
        cpus = [int(c) for c in args.cpus.split(",")]
        (out / "campaign.json").parent.mkdir(parents=True, exist_ok=True)
        (out / "campaign.json").write_text(json.dumps(dict(jobs=jobs, cpus=cpus,
                                                           source=_source(out / "source")),
                                                      indent=1))  # fmt: skip
        done = launch(out, cpus, jobs, args.parse_only)
        return 0 if all(d["exit"] == 0 for d in done) else 1
    if args.command == "table":
        print(table(out, tuple(args.only), args.retry))
        return 0
    if args.command == "restart":
        family, run, join = worlds.RESTART
        path = record_path(out, family=family, run=run, restart=True)
    elif args.plant:
        path = record_path(out, plant=args.plant)
    else:
        path = record_path(out, family=args.family, run=args.run, dt=args.dt)
    folder = path.parent / f"{path.stem}.source"
    source = _source(folder)  # Before the run (engine_run.provenance); late sources after it.
    try:
        if args.parse_only:  # The command line's own check: the world parsed, nothing compiled.
            if args.command == "restart":
                raw = worlds.world(family, run, dt=worlds.H)
                identity = dict(family=family, run=run, restart=True)
            elif args.plant:
                raw, identity = worlds.plant(args.plant), plant_identity(args.plant)
            else:
                raw = worlds.world(args.family, args.run, dt=args.dt)
                identity = dict(family=args.family, run=args.run)
            worlds._parse(raw)
            record = dict(kind=RECORD, **identity, parsed_only=True, refused=False,
                          dt_s=raw["execution"]["dt"], definition=raw)  # fmt: skip
        elif args.command == "restart":
            raw = worlds.world(family, run, dt=worlds.H)
            record = restart_record(raw, join, path.parent / "snapshot-files", family=family,
                                    run=run, restart=True)  # fmt: skip
        elif args.plant:
            raw = worlds.plant(args.plant)
            with v0_patch() if args.plant == V0_PLANT else contextlib.nullcontext():
                record = one(raw, **plant_identity(args.plant))
        else:
            raw = worlds.world(args.family, args.run, dt=args.dt)
            record = one(raw, family=args.family, run=args.run)
    except Exception:  # A failure is recorded, never silent; the campaign goes on.
        traceback.print_exc()
        return 1
    _write(path, record, engine_run.late_sources(folder, source))
    print(json.dumps({"record": str(path), "refused": record.get("refused"),
                      "wall_s": record.get("wall_s")}))  # fmt: skip
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
