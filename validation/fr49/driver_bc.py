"""FR-49's driver for World B, C1 and C2 (fr49-compartment-compositions-v1,
validation/fr49/REGISTRATION.md §4 and §5): one run of one job, in its own process, written as one
record of the engine's own values. Nothing in a record is formed from a reference; the judge
(validation/fr49/judge_bc.py, which the lead runs) reads the records and the code-blind references.

**The jobs** (JOBS, the registered runs, twelve):
- World B: dt 0.1 s and 0.05 s to 600 s, observed every 5 s; its twin, the wash declared with no
  event, at 0.1 s (the literal reading, D424); plants (b), (c) and (d) at 0.1 s. Plant (a) is the
  judge's own substitution, with no run, and B6 is the judge's host row.
- C1: dt 2 s to 3600 s, observed every 60 s; its twin; its plant.
- C2: dt 0.1 s and 0.05 s to 2000 s, observed every 20 s; its plant at 0.1 s.
`jobs OUT_DIR` writes one job file per run and an index of their SHA-256 sums, for the lead to check
and hash before any run (D424). The worlds are validation/fr49/worlds_bc.py's, the plants
validation/fr49/plants_bc.py's.

**A run** (`run JOB RECORD_DIR`) enters the job's engine plant, if any, before the world is built,
so its patch is in place for the parse, the binding and the compile; a definition plant changes the
built definition instead (plants_bc.definition). The definition is parsed and run by the runner,
whose host checks run on every accepted row. It writes RECORD_DIR/<id>.json, the outcome, the
identity and the quantities at every observed row as exact hexadecimal floats, and
RECORD_DIR/<id>.npz, the arrays that the bitwise criteria compare (B5, C1-1). A refusal is recorded
with its class and message, not raised.

**What each world's record holds:**
- World B: S at lys (n_L), and the population's B and R, at every row; in the npz, lys's every
  species row and the site increments, and the wash's applied counts.
- C1: S at the owner O, the compartment C and the well W, and label x's share at each, at every row;
  in the npz, O's and C's every species row and their label shares; the label owner's closure
  diagnostic, largest over the run.
- C2: L1 and L2 at lys, each member's B, and the set's free sites R, at every row.

The first-run rule: a job whose ID does not begin `dev-` runs only with `--judged`, so that no
registered run is made by accident before the launch note.

Usage (PYTHONPATH at a snapshot, JAX_ENABLE_X64=1, JAX_PLATFORMS=cpu):
  python -B -m validation.fr49.driver_bc jobs OUT_DIR
  python -B -m validation.fr49.driver_bc run JOB_JSON RECORD_DIR [--judged]
"""

import argparse
import hashlib
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

KIND = "fr49 Parts B and C engine record, version 1"
JOB_KIND = "fr49 Parts B and C job, version 1"
PROTOCOL = "fr49-compartment-compositions-v1"
# (id, world, dt s, horizon s, observed every s, the wash's event declared, plant): REGISTRATION.md
# §4.1's and §5's runs. The judge holds its own copy of this table (judge_bc.RUNS), checked against
# the job files by the lead before any run.
JOBS = (
    ("B-dt0.1", "B", 0.1, 600.0, 5.0, True, None),
    ("B-dt0.05", "B", 0.05, 600.0, 5.0, True, None),
    ("B-twin-dt0.1", "B", 0.1, 600.0, 5.0, False, None),
    ("B-plant-b-dt0.1", "B", 0.1, 600.0, 5.0, True, "b"),
    ("B-plant-c-dt0.1", "B", 0.1, 600.0, 5.0, True, "c"),
    ("B-plant-d-dt0.1", "B", 0.1, 600.0, 5.0, True, "d"),
    ("C1-dt2", "C1", 2.0, 3600.0, 60.0, True, None),
    ("C1-twin-dt2", "C1", 2.0, 3600.0, 60.0, False, None),
    ("C1-plant-dt2", "C1", 2.0, 3600.0, 60.0, True, "c1"),
    ("C2-dt0.1", "C2", 0.1, 2000.0, 20.0, None, None),
    ("C2-dt0.05", "C2", 0.05, 2000.0, 20.0, None, None),
    ("C2-plant-dt0.1", "C2", 0.1, 2000.0, 20.0, None, "c2"),
)
FIELDS = ("id", "world", "dt", "horizon_s", "every_s", "event", "plant")
LABEL_X = 1  # World L's labels: ["base", "x"].


def job(row):
    return dict(kind=JOB_KIND, protocol=PROTOCOL, **dict(zip(FIELDS, row, strict=True)))


def write_jobs(out_dir):
    """One job file per registered run, and SHA256SUMS of them."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    sums = []
    for row in JOBS:
        entry = job(row)
        path = out / f"{entry['id']}.json"
        path.write_text(json.dumps(entry, indent=1) + "\n", encoding="utf-8")
        sums.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}")
    (out / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")
    return [r[0] for r in JOBS]


def raw_world(entry):
    """The job's definition, its definition plant applied (worlds_bc; plants_bc.definition)."""
    from validation.fr49 import plants_bc
    from validation.fr49 import worlds_bc as wb

    world, dt, end, every = entry["world"], entry["dt"], entry["horizon_s"], entry["every_s"]
    if world == "B":
        raw = wb.world_b(dt=dt, end=end, every=every, event=entry["event"])
    elif world == "C1":
        raw = wb.world_c1(dt=dt, end=end, every=every, event=entry["event"])
    elif world == "C2":
        raw = wb.world_c2(dt=dt, end=end, every=every)
    else:
        raise ValueError(f"no world {world!r}")
    return plants_bc.definition(raw, entry["plant"])


def hexes(values):
    return [float(v).hex() for v in np.asarray(values, dtype=float).ravel()]


def node_index(spec, name):
    return [c.id for c in spec.model.extracellular].index(name)


def b_record(spec, result, p):
    from validation.fr49 import worlds_bc as wb

    h = result.history
    s = list(spec.model.species_ids).index(wb.LIGAND)
    lys, well = node_index(spec, wb.LYS), node_index(spec, wb.WELL)
    n_l = (
        np.asarray(p.extracellular_amount_reference)[s, lys]
        + np.asarray(h.extracellular_amount_increment)[:, s, lys]
    )
    bound = np.asarray(p.site_bound_anchor_fmol)[0] + np.asarray(h.site_bound_increment_fmol)[:, 0]
    free = np.asarray(p.site_free_anchor_fmol)[0] + np.asarray(h.site_free_increment_fmol)[:, 0]
    quantities = dict(n_L=hexes(n_l), B=hexes(bound), R=hexes(free))
    arrays = dict(
        lys_rows=np.asarray(h.extracellular_amount_increment)[:, :, lys],
        site_free_increment_fmol=np.asarray(h.site_free_increment_fmol),
        site_bound_increment_fmol=np.asarray(h.site_bound_increment_fmol),
        wash_applied_well=np.asarray(h.wash_applied)[:, well],
        wash_applied_lys=np.asarray(h.wash_applied)[:, lys],
    )
    return quantities, arrays, {}


def c1_record(spec, result, p):
    from validation.fr49 import worlds
    from validation.fr49 import worlds_bc as wb

    h = result.history
    s = list(spec.model.species_ids).index(worlds.S)
    owner = [c.id for c in spec.model.cells].index(worlds.CELL)
    node, well = node_index(spec, worlds.NODE), node_index(spec, wb.W)
    cell_ref = np.asarray(p.amount_reference)
    node_ref = np.asarray(p.extracellular_amount_reference)
    n_o = cell_ref[s, owner] + np.asarray(h.amount_increment)[:, s, owner]
    n_c = node_ref[s, node] + np.asarray(h.extracellular_amount_increment)[:, s, node]
    n_w = node_ref[s, well] + np.asarray(h.extracellular_amount_increment)[:, s, well]
    share = np.asarray(h.label_share)  # [row, labelled species, label, cell]
    outside = np.asarray(h.label_outside_share)  # [row, labelled species, label, outside node]
    quantities = dict(
        n_O=hexes(n_o),
        n_C=hexes(n_c),
        n_W=hexes(n_w),
        share_x_O=hexes(share[:, 0, LABEL_X, owner]),
        share_x_C=hexes(outside[:, 0, LABEL_X, node]),
        share_x_W=hexes(outside[:, 0, LABEL_X, well]),
        share_base_W=hexes(outside[:, 0, 0, well]),
    )
    arrays = dict(
        O_rows=np.asarray(h.amount_increment)[:, :, owner],
        C_rows=np.asarray(h.extracellular_amount_increment)[:, :, node],
        O_shares=share[:, :, :, owner],
        C_shares=outside[:, :, :, node],
    )
    closure = float(np.max(np.asarray(h.label_closure_relative), initial=0.0))
    return quantities, arrays, dict(label_closure_relative_max=closure)


def c2_record(spec, result, p):
    from validation.fr49 import worlds
    from validation.fr49 import worlds_bc as wb

    h = result.history
    ids = list(spec.model.species_ids)
    lys = node_index(spec, wb.LYS)
    quantities, arrays = {}, {}
    ligands = worlds.declared("C2")["ligands"]
    bound = np.asarray(p.site_bound_anchor_fmol)[None, :] + np.asarray(h.site_bound_increment_fmol)
    for k, g in enumerate(ligands):
        s = ids.index(g["id"])
        n = (
            np.asarray(p.extracellular_amount_reference)[s, lys]
            + np.asarray(h.extracellular_amount_increment)[:, s, lys]
        )
        quantities[f"n_{g['id']}"] = hexes(n)
        quantities[f"B{k + 1}"] = hexes(bound[:, k])  # The members in cases.json's order.
    free = np.asarray(p.site_free_anchor_fmol)[0] + np.asarray(h.site_free_increment_fmol)[:, 0]
    quantities["R"] = hexes(free)
    arrays["lys_rows"] = np.asarray(h.extracellular_amount_increment)[:, :, lys]
    return quantities, arrays, {}


RECORDS = {"B": b_record, "C1": c1_record, "C2": c2_record}


def identity():
    """The tree's revision and dirty files, or a frozen snapshot's (SNAPSHOT.json)."""
    here = Path(__file__).resolve().parents[2]
    manifest = here / "SNAPSHOT.json"
    if manifest.is_file():
        snapshot = json.loads(manifest.read_text(encoding="utf-8"))
        return dict(revision=snapshot["git_revision"], snapshot=str(here),
                    patch_sha256=snapshot["patch_sha256"])  # fmt: skip
    git = ["git", "-C", str(here)]
    revision = subprocess.run([*git, "rev-parse", "HEAD"], capture_output=True, text=True)
    dirty = subprocess.run([*git, "status", "--short"], capture_output=True, text=True)
    return dict(revision=revision.stdout.strip(), dirty=dirty.stdout.splitlines())


def run(job_path, record_dir, *, judged=False):
    """Run one job in this process and write its record (the module docstring)."""
    import jax

    jax.config.update("jax_enable_x64", True)
    from cells.definitions.specs import ConfigError, parse_spec
    from cells.execution.errors import NumericalError
    from cells.execution.runner import run as run_spec
    from cells.registry.models import get_model
    from validation.fr49 import plants_bc

    entry = json.loads(Path(job_path).read_text(encoding="utf-8"))
    if entry.get("kind") != JOB_KIND or entry.get("protocol") != PROTOCOL:
        raise SystemExit(f"{job_path}: not an FR-49 Parts B and C job")
    if not entry["id"].startswith("dev-") and not judged:
        raise SystemExit(f"{entry['id']} is a registered run: it runs only with --judged")
    out = Path(record_dir)
    out.mkdir(parents=True, exist_ok=True)
    record = dict(kind=KIND, protocol=PROTOCOL, job=entry, identity=identity(),
                  python=sys.version.split()[0], platform=platform.platform())  # fmt: skip
    started = time.perf_counter()
    engine_plant = entry["plant"] in plants_bc.ENGINE
    record["plant_kind"] = "engine" if engine_plant else ("definition" if entry["plant"] else None)
    try:
        with plants_bc.engine(entry["plant"]):
            spec = parse_spec(raw_world(entry))
            result = run_spec(spec)  # Its host checks run on every accepted row.
            _, p = get_model(spec.model).initial_values(spec)
            quantities, arrays, extra = RECORDS[entry["world"]](spec, result, p)
        record.update(outcome="completed", times=hexes(result.times), quantities=quantities,
                      **extra)  # fmt: skip
        np.savez(out / f"{entry['id']}.npz", **arrays)
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
    jobs = sub.add_parser("jobs", help="write the registered job files and their SHA256SUMS")
    jobs.add_argument("out_dir")
    one = sub.add_parser("run", help="run one job in this process and write its record")
    one.add_argument("job")
    one.add_argument("record_dir")
    one.add_argument("--judged", action="store_true", help="the call runs a registered job")
    args = parser.parse_args(argv)
    if args.command == "jobs":
        print("\n".join(write_jobs(args.out_dir)))
    else:
        print(run(args.job, args.record_dir, judged=args.judged))


if __name__ == "__main__":
    main()
