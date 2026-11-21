"""Generate the references of sheet §6 and their interface files.

    python -m validation.gene_regulation.references.run --out DIR [--stage S ...] [--workers N]
           [--sets all|edge|test] [--potentials G_ATP E_pd E_pep E_rc_RT]

Stages (each writes under DIR and resumes from what is there; `assemble` writes DIR/interface):
  refs      every world at every potential set: DOP853 at rtol 2.5e-12 (the judge, on which the
            identities are judged), again at 2.5e-14 (the sheet's 100× check), and Radau at
            1e-11 at the 18 edge sets (a second, stiff method)
  closed    §5.1's and §5.2's closed forms at every set, at 50 digits and again at 70
  plants    every plant at the 18 edge sets (model.SHEET_EDITS, model.OWN_EDITS)
  noise     R-noise at the test instance (the first set)
  assemble  the interface JSON files

`--potentials` runs everything at one named set of the four symbols (the registration's): ΔG′°_ATP,
E_pd and E_pep in kJ/mol, then E_rc/RT. It must lie inside §3.3's ranges.
"""

from __future__ import annotations

import argparse
import json
import os
import pickle
import platform
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import numpy as np
import scipy

# Engine-free provenance helper (validation/executed_sources.py): records or refuses the executed
# sources Git does not track. It is the one validation/ module the references import.
from validation import executed_sources
from . import closed_forms, model, noise, plants, sheet

# The judge and the sheet's 100× tighter check. 2.5e-14 sits just above scipy's floor of
# 100 × machine epsilon; at 1e-11/1e-13 a corner reached 8.3e-10 of the 1e-9 allowed.
PRIMARY = ("DOP853", 2.5e-12)
CHECK = ("DOP853", 2.5e-14)
CROSS = ("Radau", 1e-11)
COARSE_RTOL = 1e-8
RADAU_NEWTON_TOL = max(10 * np.finfo(float).eps / CROSS[1], min(0.03, CROSS[1] ** 0.5))
HERE = Path(__file__).resolve().parent
STRIDE = {"A1": 10, "pol": 10, "two-gene": 10, "rib": 10}  # edge sets: every 10th output
EDGE_READOUT_PREFIXES = ("n_", "F_", "E_", "W_", "int_", "G_minus_G0", "H_", "J_bar_")


def world_names() -> list[str]:
    return [w.name for w in model.all_worlds()]


def world_by_name(name: str) -> model.World:
    for w in model.all_worlds():
        if w.name == name:
            return w
    raise KeyError(name)


def slug(name: str) -> str:
    return name.replace(" ", "_").replace("=", "")


def kind_of(name: str) -> tuple[str, int | None]:
    if name == "A1":
        return "A1", None
    if name == "two-gene":
        return "two-gene", None
    if name.startswith("pol T="):
        return "pol", int(name.split("=")[1])
    return "rib", int(name.split("=")[1])


def potential_sets(which: str, potentials: list[str] | None) -> list[sheet.Potentials]:
    if potentials:
        g, pd, pep, rc = potentials
        for (name, lo, hi), v in zip(sheet.RANGES, (g, pd, pep, rc), strict=True):
            if not lo <= float(v) <= hi:
                raise SystemExit(f"{name} = {v} lies outside §3.3's range [{lo}, {hi}]")
        return [sheet.Potentials("registered", g, pd, pep, rc)]
    return {"all": sheet.potential_sets(), "edge": sheet.edge_sets(),
            "test": [sheet.TEST_INSTANCE]}[which]


def n_edge(sets: list) -> int:
    return min(len(sets), 18)


def convergence(a: dict, b: dict) -> dict:
    """max |a − b| over the horizon, over the readout's scale (its largest magnitude in a)."""
    out = {}
    for k, x in a.items():
        if k in ("t",) or k.startswith("rate_"):
            continue
        x, y = np.asarray(x, float), np.asarray(b[k], float)
        s = float(np.max(np.abs(x)))
        out[k] = float(np.max(np.abs(x - y)) / s) if s > 0 else float(np.max(np.abs(x - y)))
    return out


def _dump(path: Path, obj) -> None:
    tmp = path.with_suffix(".tmp")
    with tmp.open("wb") as f:
        pickle.dump(obj, f)
    tmp.replace(path)


def _load(path: Path):
    with path.open("rb") as f:
        return pickle.load(f)


# ---- stage items (module-level so that worker processes can run them) ---------------------------
def ref_item(task):
    out, i, pot, wname, radau = task
    path = Path(out) / "refs" / f"{i:02d}_{slug(wname)}.pkl"
    if path.exists():
        return str(path)
    t0 = time.time()
    sysm = model.System(world_by_name(wname), pot)
    scales = model.state_scales(sysm, COARSE_RTOL)
    prim = model.integrate(sysm, *PRIMARY, scales)
    ro = model.readouts(sysm, prim)
    ids = model.identities(sysm, ro)
    t1 = time.time()
    tight = model.integrate(sysm, *CHECK, scales, track_steps=False)
    ro_t = model.readouts(sysm, tight)
    rec = {"set": i, "pot": pot.as_dict(), "world": wname, "readouts": ro,
           "identity_levels": plants.identity_levels(ids),
           "identity_scales": {k: float(s) for k, (r, s) in ids.items()},
           "convergence": convergence(ro, ro_t),
           "domain_steps": prim["domain_steps"], "heat_min_increment": prim["heat_min_increment"],
           "steps": prim["steps"], "nfev": prim["nfev"], "steps_tight": tight["steps"],
           "seconds_primary": t1 - t0, "seconds_total": None}
    if radau:
        rad = model.integrate(sysm, *CROSS, scales, track_steps=False)
        ro_r = model.readouts(sysm, rad)
        rec["radau"] = {"vs_tight": convergence(ro_t, ro_r),
                        "identity_levels": plants.identity_levels(model.identities(sysm, ro_r)),
                        "newton_tol": RADAU_NEWTON_TOL, "steps": rad["steps"]}
    rec["seconds_total"] = time.time() - t0
    _dump(path, rec)
    return str(path)


def closed_item(task):
    out, i, pot = task
    path = Path(out) / "closed" / f"{i:02d}.pkl"
    if path.exists():
        return str(path)
    a = sheet.A1
    times = list(range(0, a["t_off"], a["dt_out"]))
    lim = closed_forms.a1_limit(pot, times, 50)
    lim70 = closed_forms.a1_limit(pot, times, 70)

    def rel(x, y):
        x, y = Decimal(x), Decimal(y)
        return float(abs(x - y) / abs(y)) if y != 0 else float(abs(x - y))

    prec_rel = max(rel(x, y) for k in lim["series"]
                   for x, y in zip(lim["series"][k], lim70["series"][k], strict=True))
    route_rel = max(rel(x, y) for k, ks in (("n_R", "n_R_scalar"), ("E_tx", "E_tx_scalar"))
                    for x, y in zip(lim70["series"][k], lim70["series"][ks], strict=True))
    machine, machine_rel = {}, 0.0
    for w in world_names():
        kind, size = kind_of(w)
        if kind == "A1":
            continue
        c50 = closed_forms.a1m_closed(pot, kind, size, 50)
        c70 = closed_forms.a1m_closed(pot, kind, size, 70)
        machine[w] = c50
        machine_rel = max([machine_rel] + [rel(c50[k], c70[k]) for k in c50 if k != "prec"])
    rec = {"set": i, "a1": lim, "machine": machine,
           "precision": {"a1_50_vs_70": prec_rel, "a1_matrix_vs_scalar": route_rel,
                         "machine_50_vs_70": machine_rel}}
    _dump(path, rec)
    return str(path)


def plant_item(task):
    out, j, plant, i, pot, wname = task
    tag = f"{plant['id']}_{'+'.join(plant['edits'])}_{i:02d}_{slug(wname)}"
    path = Path(out) / "plants" / f"{tag}.pkl"
    if path.exists():
        return str(path)
    world = world_by_name(wname)
    sysm = model.System(world, pot, frozenset(plant["edits"]))
    sol = model.integrate(sysm, *PRIMARY, model.state_scales(sysm, COARSE_RTOL))
    ro = model.readouts(sysm, sol)
    il = plants.identity_levels(model.identities(sysm, ro))
    ref = _load(Path(out) / "refs" / f"{i:02d}_{slug(wname)}.pkl")
    closed = _load(Path(out) / "closed" / f"{i:02d}.pkl")
    ch, missing = plants.changes(ref["readouts"], ro)
    if wname == "A1":
        gaps = plants.a1_gaps(ro, closed["a1"])
    else:
        routes = [r.name for r in world.routes]
        gaps = plants.machine_gaps(ro, closed["machine"][wname], routes, next(iter(world.pools)))
    f_min = {q: float(np.min(ro[f"F_{q}"])) for q in world.pools}
    rec = {"plant": plant, "set": i, "world": wname, "changes": ch, "missing": missing,
           "identity_levels": il, "gaps": gaps,
           "verdicts": plants.verdicts(plant, ch, il, gaps, wname), "F_min": f_min,
           "domain_steps": sol["domain_steps"]}
    _dump(path, rec)
    return str(path)


def noise_item(out, pot, replicates: int = sheet.NOISE_REPLICATES) -> None:
    path = Path(out) / "noise" / "report.pkl"
    if path.exists():
        return
    rec = {}
    for w in ("T10", "A1"):
        p = noise.params(pot, w)
        seeds = noise.replicate_seeds(w)[:replicates]
        t0 = time.time()
        counts = noise.simulate(p, seeds)
        secs = time.time() - t0
        det = noise.deterministic_mean(p)
        det_chk = noise.deterministic_mean(p, rtol=1e-11, prec=70)
        scale = np.max(np.abs(det), axis=0)
        det_conv = float(np.max(np.abs(det - det_chk) / scale))
        scalar_same = [bool(np.array_equal(noise.simulate_scalar(p, seeds[k]), counts[k]))
                       for k in range(3)]
        np.savez_compressed(Path(out) / "noise" / f"{w}_counts.npz", counts=counts)
        rep = noise.band_report(counts, det)
        rec[w] = {"params": p, "report": rep, "seconds": secs, "det_convergence": det_conv,
                  "scalar_equals_batch_first_3": scalar_same}
    _dump(path, rec)


# ---- driver ------------------------------------------------------------------------------------
def snapshot_manifest() -> tuple[Path, dict] | None:
    """The source snapshot this code runs from (validation/source_snapshot.py), if any."""
    for parent in HERE.parents:
        if (parent / "SNAPSHOT.json").exists():
            return parent, json.loads((parent / "SNAPSHOT.json").read_text())
    return None


def git(*args) -> str:
    snap = snapshot_manifest()
    where = snap[1]["repository"] if snap else str(HERE)
    try:
        return subprocess.run(["git", "-C", where, *args], capture_output=True, text=True,
                              check=True).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def provenance() -> dict:
    snap = snapshot_manifest()
    if snap:
        path, man = snap
        # The checkout's own location is not recorded: the revision, the selected files'
        # status and the patch identify the source.
        source = {"snapshot": str(path), "git_revision": man["git_revision"],
                  "selected_status": man["selected_status_porcelain_v1_z"] or None,
                  "patch_sha256": man["patch_sha256"]}
    else:
        # A checkout: `git diff HEAD` and the status miss a file Git does not track, so the receipt
        # also holds the full status (every untracked file, `!!` for loaded ignored sources), the
        # diff from HEAD joined to each untracked executed source's full content, and their paths.
        record = executed_sources.checkout(HERE)
        source = {"snapshot": None, "git_revision": git("rev-parse", "HEAD") or None,
                  "selected_status": git("status", "--porcelain", "--", str(HERE)) or None,
                  "status": record["status"] or None, "diff": record["diff"] or None,
                  "untracked_executed": record["untracked_executed"]}
    return {"source": source, "python": platform.python_version(), "numpy": np.__version__,
            "scipy": scipy.__version__, "generated_utc": datetime.now(timezone.utc).isoformat(),
            "cpu_affinity": sorted(os.sched_getaffinity(0))}


def run_stage(stage: str, out: Path, sets: list, workers: int,
              replicates: int = sheet.NOISE_REPLICATES) -> None:
    (out / stage).mkdir(parents=True, exist_ok=True)
    ne = n_edge(sets)
    if stage == "refs":
        tasks = [(str(out), i, pot, w, i < ne) for i, pot in enumerate(sets) for w in world_names()]
        tasks.sort(key=lambda t: (t[3] != "A1", t[1]))  # the long A1 solves first
        fn = ref_item
    elif stage == "closed":
        tasks = [(str(out), i, pot) for i, pot in enumerate(sets)]
        fn = closed_item
    elif stage == "plants":
        allp = plants.PLANTS + plants.EXTRA
        tasks = [(str(out), j, p, i, pot, w) for j, p in enumerate(allp)
                 for i, pot in enumerate(sets[:ne]) for w in p["worlds"]]
        tasks.sort(key=lambda t: (t[5] != "A1", t[3]))
        fn = plant_item
    elif stage == "noise":
        noise_item(out, sets[0], replicates)
        return
    else:
        raise ValueError(stage)
    t0 = time.time()
    done = 0
    if workers > 1:
        with ProcessPoolExecutor(max_workers=workers) as ex:
            for _ in ex.map(fn, tasks, chunksize=1):
                done += 1
                if done % 25 == 0:
                    print(f"{stage}: {done}/{len(tasks)} after {time.time() - t0:.0f} s",
                          flush=True)
    else:
        for t in tasks:
            fn(t)
            done += 1
            if done % 25 == 0:
                print(f"{stage}: {done}/{len(tasks)} after {time.time() - t0:.0f} s", flush=True)
    print(f"{stage}: {done} items in {time.time() - t0:.0f} s", flush=True)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--stage", nargs="+", default=["refs", "closed", "plants", "noise", "assemble"])
    ap.add_argument("--sets", choices=("all", "edge", "test"), default="all")
    ap.add_argument("--potentials", nargs=4, metavar=("G_ATP", "E_pd", "E_pep", "E_rc_RT"))
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--noise-replicates", type=int, default=sheet.NOISE_REPLICATES,
                    help="development only: the sheet's count is 1000")
    args = ap.parse_args(argv)
    sets = potential_sets(args.sets, args.potentials)
    args.out.mkdir(parents=True, exist_ok=True)
    # Every invocation keeps its own record, so a stage re-run later cannot hide which source
    # produced the earlier stages; assemble carries all of them into inputs.json.
    record = {"argv": sys.argv[1:], "stages": args.stage, "sets": [p.as_dict() for p in sets],
              "provenance": provenance()}
    inv = args.out / "invocations"
    inv.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    (inv / f"{stamp}.json").write_text(json.dumps(record, indent=1))
    for stage in args.stage:
        if stage == "assemble":
            from . import assemble
            assemble.write_interface(args.out, sets, provenance())
        else:
            run_stage(stage, args.out, sets, args.workers, args.noise_replicates)


if __name__ == "__main__":
    main()
