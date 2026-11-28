"""FR-49's driver for C4, the four-way form (fr49-compartment-compositions-v1, amendment 2): one run
of one job, in a fresh process of its own, written as one record of the engine's own values and its
definition as built. Nothing in a record is formed from a reference; the judge
(validation/fr49/judge_c4.py, which the lead runs) reads the records and the tagged references. The
tagged B/C files are imported here and never edited.

**The jobs** (JOBS, A2.3 and A2.6): eight, each at dt 0.5 s, observed every 60 s, to world L's
horizon but plant (e), which runs to its own 1800 s (amendment 3, A3.2): C4; its twin, the wash
declared with no event; its unlabelled twin; its unbound twin; plants (c), (d), (c1) and (e). Plant
(a) is the judge's own substitution. `jobs OUT_DIR` builds every
job's definition, runs amendment 2's two gates on each (worlds_c4.gates_refusal: the values gate
against cases.json and the decoupling gate), and writes the job files and their SHA256SUMS only if
every definition passes.

**The first-run rule** (A2.7; it binds every agent, the builder, the reviewer and the lead alike):
no one runs C4's world, a twin of it or a plant of it to the horizon before the judged runs. Here
(first_run_refusal):
- a job whose ID does not begin `dev-` must be exactly one of JOBS's rows, and runs only with
  `--judged`;
- a `dev-` job is C4's world, at a horizon strictly short of its registered run's (world L's, or
  plant (e)'s own 1800 s: amendment 3, A3.7), with a registered plant or none.

**A run** (`run JOB RECORD_DIR`) gets a fresh process of its own (A2.7): `run` checks the job, the
first-run rule and both gates, then starts a new interpreter for it (`run-here`). That process
refuses unless `run` started it for this job and this driver file, it has run no job before, and
no JAX or engine module is loaded (fresh_process_refusal, with its own mark CHILD). It enters the
job's engine plant, if any, before the world is parsed, so the patch is in place for the parse,
the binding and the compile. The runner's host checks run on every accepted row.

**A record** is RECORD_DIR/<id>.json, <id>.npz and <id>.definition.json (the definition as built,
which the judge's gates read before any value):
- the outcome, the identity (driver_bc.identity: the revision, and the engine's tree, the driver's
  own), the process (driver_bc.process_identity) and C4's entity slots (worlds_c4.c4_entity_slots,
  refused unless they are world_c4()'s);
- the quantities at every saved row, the dt grid, as exact hexadecimal floats: S at O, C and W
  (n_O, n_C, n_W), label x's share at each and the base's at W (labelled runs), G at C (n_G), and
  the population's B and R;
- the npz, compressed: C4-1's arrays (`O.`, `C.` and `P.<field>`, by C4's entity rule,
  worlds_c4.c4_part), every label share at every cell and outside node, the wash's applied counts
  at W and at C, the label owner's closure diagnostic (labelled runs), and for C4 and its
  unlabelled twin every history field (`H.<field>`) and observation (`OBS.<name>`), with the run's
  diagnostics in the record (C4-4).
A refusal by a named check is recorded with its class and message; any other fault is recorded,
then raised.

Usage (from a snapshot's root, PYTHONPATH=src, JAX_ENABLE_X64=1, JAX_PLATFORMS=cpu):
  python -B -m validation.fr49.driver_c4 jobs OUT_DIR
  python -B -m validation.fr49.driver_c4 run JOB_JSON RECORD_DIR [--judged]
(`run-here` is the fresh process that `run` starts; called directly, it refuses.)
"""

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

from validation.fr49 import driver_bc

KIND = "fr49 C4 engine record, version 1"
JOB_KIND = "fr49 C4 job, version 1"
PROTOCOL = "fr49-compartment-compositions-v1"
HORIZON = (
    3600.0  # s: world L's horizon_s (the values gate checks each job's definition against it).
)
E_HORIZON = 1800.0  # s: plant (e)'s own horizon (amendment 3, A3.2; the values gate's row for it).
# (id, world, dt s, horizon s, observed every s, the wash's event, labelled, bound, plant): A2.3's
# runs and A2.6's plants, plant (e) at its own horizon (amendment 3). The judge holds its own copy
# (judge_c4.RUNS).
JOBS = (
    ("C4-dt0.5", "C4", 0.5, HORIZON, 60.0, True, True, True, None),
    ("C4-twin-dt0.5", "C4", 0.5, HORIZON, 60.0, False, True, True, None),
    ("C4-unlabelled-dt0.5", "C4", 0.5, HORIZON, 60.0, True, False, True, None),
    ("C4-unbound-dt0.5", "C4", 0.5, HORIZON, 60.0, True, True, False, None),
    ("C4-plant-c-dt0.5", "C4", 0.5, HORIZON, 60.0, True, True, True, "c"),
    ("C4-plant-d-dt0.5", "C4", 0.5, HORIZON, 60.0, True, True, True, "d"),
    ("C4-plant-c1-dt0.5", "C4", 0.5, HORIZON, 60.0, True, True, True, "c1"),
    ("C4-plant-e-dt0.5", "C4", 0.5, E_HORIZON, 60.0, True, True, True, "e"),
)
FIELDS = ("id", "world", "dt", "horizon_s", "every_s", "event", "labelled", "bound", "plant")
PLANTS = (None, "c", "d", "c1", "e")
CHILD = "FR49_C4_DRIVER_RUN"  # Set by `run` for the process it starts: [this driver file, the job].
ENGINE_MODULES = ("jax", "jaxlib", "cells")  # None is loaded in a fresh process before its job.
_RAN = []  # The job this process has run: one at most.


def full(entry):
    """Whether a run's record holds every history field and observation (C4-4): C4's world and its
    unlabelled twin, the wash's event and the binding on, no plant."""
    return entry["event"] and entry["bound"] and entry["plant"] is None


def job(row):
    return dict(kind=JOB_KIND, protocol=PROTOCOL, **dict(zip(FIELDS, row, strict=True)))


def change(entry):
    """The registered change by which a job's definition departs from C4's (worlds_c4.CHANGES), or
    ValueError for a job with more than one."""
    found = [
        name
        for name, departs in (
            ("twin", not entry["event"]),
            ("unlabelled", not entry["labelled"]),
            ("unbound", not entry["bound"]),
            ("plant c", entry["plant"] == "c"),
            ("plant e", entry["plant"] == "e"),  # Its own horizon (amendment 3, A3.2).
        )
        if departs
    ]
    if len(found) > 1:
        raise ValueError(f"{entry['id']} departs from C4 by more than one change: {found}")
    return found[0] if found else None


def raw_world(entry):
    """The job's definition, its definition plant applied (worlds_c4; plants_c4.definition)."""
    from validation.fr49 import plants_c4
    from validation.fr49 import worlds_c4 as w4

    if entry["world"] != "C4":
        raise ValueError(f"no C4 world {entry['world']!r}")
    raw = w4.world_c4(
        dt=entry["dt"],
        end=entry["horizon_s"],
        every=entry["every_s"],
        event=entry["event"],
        labelled=entry["labelled"],
        bound=entry["bound"],
    )
    return plants_c4.definition(raw, entry["plant"])


def gates_refusal(entry, raw):
    """Why the job's definition fails amendment 2's values gate or decoupling gate, or None."""
    from validation.fr49 import worlds_c4 as w4

    return w4.gates_refusal(raw, change(entry), development=entry["id"].startswith("dev-"))


def write_jobs(out_dir):
    """One job file per registered run, and SHA256SUMS of them, once every job's definition passes
    both gates; otherwise nothing is written (SystemExit)."""
    entries = [job(row) for row in JOBS]
    refused = {e["id"]: gates_refusal(e, raw_world(e)) for e in entries}
    refused = {k: v for k, v in refused.items() if v}
    if refused:
        raise SystemExit(
            f"the gates refuse these jobs' definitions, so no job is written: {refused}"
        )
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    sums = []
    for entry in entries:
        path = out / f"{entry['id']}.json"
        path.write_text(json.dumps(entry, indent=1) + "\n", encoding="utf-8")
        sums.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}")
    (out / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")
    return [e["id"] for e in entries]


def load_job(job_path):
    entry = json.loads(Path(job_path).read_text(encoding="utf-8"))
    if entry.get("kind") != JOB_KIND or entry.get("protocol") != PROTOCOL:
        raise SystemExit(f"{job_path}: not an FR-49 C4 job")
    return entry


def first_run_refusal(entry, judged):
    """Why the first-run rule (A2.7, A3.7) refuses a job, or None: a plant not registered; a job
    without `dev-` that is not exactly a row of JOBS, or not run with `--judged`; a `dev-` job that
    is not C4's world, or whose horizon is not strictly short of its registered run's (NaN among
    them): world L's, or plant (e)'s own."""
    name, plant = entry.get("id"), entry.get("plant")
    if plant not in PLANTS:
        return f"{name}: plant {plant!r} is not a registered plant {PLANTS}"
    if not str(name).startswith("dev-"):
        if tuple(entry.get(k) for k in FIELDS) not in JOBS:
            return f"{name} is not a registered run: a job without dev- is exactly a row of JOBS"
        return None if judged else f"{name} is a registered run: it runs only with --judged"
    if entry.get("world") != "C4":
        return f"{name}: world {entry.get('world')!r} is not C4's"
    limit = E_HORIZON if plant == "e" else HORIZON
    if not float(entry["horizon_s"]) < limit:  # NaN is not short of it either.
        return (
            f"{name} is a development job whose horizon ({entry['horizon_s']!r} s) is not strictly "
            f"short of its registered run's ({limit:g} s): no one runs C4's world, a twin or a "
            "plant to its horizon before the judged runs (A2.7, A3.7)"
        )
    return None


def mark(job_path):
    """CHILD's value for a job: this driver file and the job file, resolved."""
    return json.dumps([str(Path(__file__).resolve()), str(Path(job_path).resolve())])


def fresh_process_refusal(job_path, environ=None, modules=None, ran=None):
    """Why this process is not a fresh one of its own for the job, or None: `run` started it for
    this job and this driver file (CHILD), it has run no job before (_RAN), and no JAX or engine
    module is loaded (ENGINE_MODULES). The defaults are this process's own."""
    environ = os.environ if environ is None else environ
    modules = sys.modules if modules is None else modules
    ran = _RAN if ran is None else ran
    if environ.get(CHILD) != mark(job_path):
        return "a run's process is the one `run` starts for that job and driver (a fresh process)"
    if ran:
        return f"this process ran {ran[0]} already: one job per fresh process"
    loaded = sorted(m for m in modules if m.split(".")[0] in ENGINE_MODULES)
    if loaded:
        return f"this process loaded {loaded[0]} and {len(loaded) - 1} more before its job"
    return None


def hexes(values):
    return [float(v).hex() for v in np.asarray(values, dtype=float).ravel()]


def record_values(spec, result, p, raw, entry, slots):
    """(quantities, arrays, extra) of a completed run (the module docstring)."""
    from cells.registry.models import get_model
    from validation.fr49 import worlds
    from validation.fr49 import worlds_bc as wb
    from validation.fr49 import worlds_c4 as w4
    from validation.fr49.judge_l import LABELS_ONLY

    h = result.history
    ids = list(spec.model.species_ids)
    s, g = ids.index(worlds.S), ids.index(w4.G)
    nodes = [c.id for c in spec.model.extracellular]
    owner = [c.id for c in spec.model.cells].index(worlds.CELL)
    node, well = nodes.index(worlds.NODE), nodes.index(wb.W)
    cell_ref = np.asarray(p.amount_reference)
    node_ref = np.asarray(p.extracellular_amount_reference)
    n_o = cell_ref[s, owner] + np.asarray(h.amount_increment)[:, s, owner]
    n_c = node_ref[s, node] + np.asarray(h.extracellular_amount_increment)[:, s, node]
    n_w = node_ref[s, well] + np.asarray(h.extracellular_amount_increment)[:, s, well]
    n_g = node_ref[g, node] + np.asarray(h.extracellular_amount_increment)[:, g, node]
    bound = np.asarray(p.site_bound_anchor_fmol)[0] + np.asarray(h.site_bound_increment_fmol)[:, 0]
    free = np.asarray(p.site_free_anchor_fmol)[0] + np.asarray(h.site_free_increment_fmol)[:, 0]
    quantities = dict(n_O=hexes(n_o), n_C=hexes(n_c), n_W=hexes(n_w), n_G=hexes(n_g),
                      B=hexes(bound), R=hexes(free))  # fmt: skip
    applied = np.asarray(h.wash_applied)
    arrays = dict(wash_applied_W=applied[:, well], wash_applied_C=applied[:, node])
    fields = set(type(h)._fields)
    if "label_share" in fields:
        share = np.asarray(h.label_share)  # [row, labelled species, label, cell]
        outside = np.asarray(h.label_outside_share)  # [row, labelled species, label, node]
        quantities.update(
            share_x_O=hexes(share[:, 0, 1, owner]),
            share_x_C=hexes(outside[:, 0, 1, node]),
            share_x_W=hexes(outside[:, 0, 1, well]),
            share_base_W=hexes(outside[:, 0, 0, well]),
        )
        arrays.update(label_share=share, label_outside_share=outside,
                      label_closure_relative=np.asarray(h.label_closure_relative))  # fmt: skip
    axes = get_model(spec.model).STATE_AXES
    for field in type(h)._fields:
        if field in LABELS_ONLY:
            continue
        part = w4.c4_part(tuple(axes.get(field, ())), getattr(h, field), slots)
        if part is not None:
            arrays[f"{part[0]}.{field}"] = np.asarray(part[1])
    extra = {}
    if full(entry):
        for field in type(h)._fields:
            arrays[f"H.{field}"] = np.asarray(getattr(h, field))
        for name, value in vars(result.observations).items():
            arrays[f"OBS.{name}"] = np.asarray(value)
        extra["diagnostics"] = {k: float(v) for k, v in result.diagnostics.items()}
    if "label_closure_relative" in arrays:
        extra["label_closure_relative_max"] = float(np.max(arrays["label_closure_relative"]))
    return quantities, arrays, extra


def run(job_path, record_dir, *, judged=False):
    """Run one job in a fresh process of its own (run_here) and return its outcome; the job, the
    first-run rule and both gates are checked here first."""
    entry = load_job(job_path)
    refusal = first_run_refusal(entry, judged) or gates_refusal(entry, raw_world(entry))
    if refusal:
        raise SystemExit(refusal)
    command = [sys.executable, "-B", "-m", "validation.fr49.driver_c4", "run-here", str(job_path),
               str(record_dir), *(["--judged"] if judged else [])]  # fmt: skip
    done = subprocess.run(command, env=dict(os.environ, **{CHILD: mark(job_path)}), check=False)
    if done.returncode:
        raise SystemExit(f"{entry['id']}: its process ended with status {done.returncode}")
    record = json.loads((Path(record_dir) / f"{entry['id']}.json").read_text(encoding="utf-8"))
    return record["outcome"]


def run_here(job_path, record_dir, *, judged=False):
    """Run one job in this process, which must be the fresh one `run` started for it, and write its
    record (the module docstring)."""
    entry = load_job(job_path)
    refusal = first_run_refusal(entry, judged) or fresh_process_refusal(job_path)
    if refusal:
        raise SystemExit(refusal)
    _RAN.append(entry["id"])
    raw = raw_world(entry)
    refusal = gates_refusal(entry, raw)
    if refusal:
        raise SystemExit(f"{entry['id']}: the gates refuse its definition: {refusal}")
    import jax

    jax.config.update("jax_enable_x64", True)
    from cells.definitions.specs import ConfigError, parse_spec
    from cells.execution.errors import NumericalError
    from cells.execution.runner import run as run_spec
    from cells.registry.models import get_model
    from validation.fr49 import plants_c4
    from validation.fr49 import worlds_c4 as w4

    slots = w4.c4_entity_slots(raw)
    if slots != w4.c4_entity_slots(w4.world_c4()):
        raise SystemExit(f"{entry['id']}: its entity slots are not world_c4()'s: {slots}")
    out = Path(record_dir)
    out.mkdir(parents=True, exist_ok=True)
    definition = out / f"{entry['id']}.definition.json"
    definition.write_text(json.dumps(raw, indent=1) + "\n", encoding="utf-8")
    digest = hashlib.sha256(definition.read_bytes()).hexdigest()
    record = dict(kind=KIND, protocol=PROTOCOL, job=entry, identity=driver_bc.identity(),
                  python=sys.version.split()[0], platform=platform.platform(),
                  process=driver_bc.process_identity(), c4_entity_slots=slots,
                  definition_sha256=digest)  # fmt: skip
    started = time.perf_counter()
    record["plant_kind"] = (
        "engine"
        if entry["plant"] in plants_c4.ENGINE
        else ("definition" if entry["plant"] else None)
    )
    try:
        with plants_c4.engine(entry["plant"]):
            spec = parse_spec(raw)
            result = run_spec(spec)  # Its host checks run on every accepted row.
            _, p = get_model(spec.model).initial_values(spec)
            quantities, arrays, extra = record_values(spec, result, p, raw, entry, slots)
        record.update(outcome="completed", times=hexes(result.times), quantities=quantities,
                      **extra)  # fmt: skip
        np.savez_compressed(out / f"{entry['id']}.npz", **arrays)
    except (ConfigError, NumericalError) as error:  # A refusal by a named check: a record.
        record.update(outcome="refused", refusal=dict(cls=type(error).__name__,
                                                      message=str(error)[:4000]))  # fmt: skip
    except Exception as error:  # Anything else is the harness's fault: recorded, then raised.
        record.update(outcome="error", error=f"{type(error).__name__}: {error}"[:4000],
                      seconds=round(time.perf_counter() - started, 2))  # fmt: skip
        (out / f"{entry['id']}.json").write_text(json.dumps(record, indent=1) + "\n")
        raise
    record["seconds"] = round(time.perf_counter() - started, 2)
    (out / f"{entry['id']}.json").write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8")
    return record["outcome"]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    jobs = sub.add_parser("jobs", help="check every job's definition, then write the job files")
    jobs.add_argument("out_dir")
    one = sub.add_parser("run", help="run one job in a fresh process and write its record")
    here = sub.add_parser("run-here", help="the fresh process `run` starts (not for direct use)")
    for command in (one, here):
        command.add_argument("job")
        command.add_argument("record_dir")
        command.add_argument("--judged", action="store_true", help="the call runs a registered job")
    args = parser.parse_args(argv)
    if args.command == "jobs":
        print("\n".join(write_jobs(args.out_dir)))
    elif args.command == "run":
        print(run(args.job, args.record_dir, judged=args.judged))
    else:
        run_here(args.job, args.record_dir, judged=args.judged)


if __name__ == "__main__":
    main()
