"""The engine's development runs of gene regulation's option A (G4): worlds of worlds.py at
potential sets and a step, each with every readout of the sheet's §6 under G2's interface names.
Development, not judged.

Per run (world, potential set, dt) it writes `<set>/<world>.json` into a fresh directory:
- the output times and, at each, the readouts: every row's amount n_*, each pool's free machines
  F_*, every stage's complexes C_*_j, E_* and the residues in transit W_* = r sum_j (j - 1) C_j, the
  cumulative extents int_J_I_*, int_S_*, int_Q_*, int_D_<polymer> and int_J_C (signed), and the
  five heat classes H_tx, H_tl, H_deg_R, H_deg_P and H_rc, each the sum of its routes' heats;
- J_bar_* over the final window in A1-M's worlds;
- G_minus_G0, G(t) - G(0) from the state alone (§3.4): every row's n [mu° + RT (ln a - 1)] and each
  route's mu°_res W, in 60-digit decimal arithmetic, never from extents or bookings;
- the engine's own: H_total, the booked heat, and each route's heat, H_route_*;
- the checks the bookings cannot certify themselves: G's identity, G(t) - G(0) + H_total, and the
  routes' sum against H_total, each with the largest over the outputs.
`run_record.json` holds the revision, whether the checkout was dirty (its diff in checkout.patch),
the potential sets, the step and every run's wall time and end-state own ledgers.

**Keyed by ID, never by position** (D264, findings 3 and 4).
- **The exported cell** is found by its ID: the one cell holding every route of the operator (its
  pools, degradations and transfers), or the cell named. A world whose routes span several cells
  must name it, and only that cell's routes are exported. The record names the cell. Reordering
  the declared cells changes nothing exported.
- **Each loss counter is summed once** per product, cell and output: int_D_<polymer> is the sum of
  the native counters of every degradation route of that polymer at the cell. Each route's own
  counter is int_D_route_<route>.
- **Every exported series has exactly one value per output,** or the export is refused.

The heat classes are assigned by route: a chain templated by a gene's copies is transcription
(tx), one templated by a species row is translation (tl); a degradation is deg_R or deg_P as its
polymer is made by transcription or translation; a transfer is recharging (rc).

Run: PYTHONPATH=src:. JAX_ENABLE_X64=1 python -m validation.gene_regulation.engine_run
[--worlds NAME ...] [--sets LABEL ...] [--dt S] [--end S] --out DIR
"""

import argparse
import hashlib
import json
import math
import platform
import re
import subprocess
import time
from datetime import UTC, datetime
from decimal import Decimal, localcontext
from pathlib import Path

import numpy as np

from cells.definitions.specs import parse_spec
from cells.execution.windows import WindowPolicy, iter_windows
from cells.operators import OPERATORS
from cells.registry.models import get_model
from validation.gene_regulation import sheet_check as sheet
from validation.gene_regulation import worlds

ROOT = Path(__file__).resolve().parents[2]
SHEET_TAG = "gr1-sheet-2026-11-20b"
POLICY = WindowPolicy(window_steps=10000, recording="observations")
DIGITS = 60


def git(*args):
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout


SOURCE_SCOPE = ("src", "validation")  # What a run imports or reads from the checkout.


def provenance(out=None):
    """(The source's identity, the dirty diff or None), for a run's record.
    - From a frozen snapshot (validation/source_snapshot.py): its record.
    - From the checkout (the review's finding 8 and its class, D259: a receipt named a revision
      without the script that ran):
      - validation/executed_sources.checkout: the status with every untracked file, and the dirty
        diff, `git diff --binary HEAD` joined to the full content of every executed source Git
        does not track, wherever it lives (the root, scripts/, tests/ fixtures). The record lists
        those sources as untracked_executed;
      - beside it, every untracked, nonignored file under SOURCE_SCOPE, executed or not yet, is
        frozen into OUT/untracked-sources by validation/source_snapshot.freeze, and the record
        names the folder, the files and the manifest's digest.

      Without an OUT, a checkout with either kind is refused. A source loaded later in the run is
      added at its end (late_sources)."""
    snapshot = ROOT / "SNAPSHOT.json"
    if snapshot.exists():
        d = json.loads(snapshot.read_text())
        clean = d["patch_sha256"] == hashlib.sha256(b"").hexdigest()
        return dict(
            engine_revision=d["git_revision"],
            checkout_dirty=not clean,
            snapshot=str(ROOT),
            snapshot_patch_sha256=d["patch_sha256"],
        ), None
    from validation import executed_sources

    found = executed_sources.checkout(ROOT)
    listed = git("ls-files", "--others", "--exclude-standard", "-z", "--", *SOURCE_SCOPE)
    untracked = sorted(name for name in listed.split("\0") if name)
    if out is None:
        executed_sources.refuse_untracked(ROOT, "this run, with no output folder for its record,")
        if untracked:
            raise RuntimeError(
                f"untracked source {untracked[:3]} would not be recorded: commit it, run from a "
                "frozen snapshot, or give the run an output folder to freeze it into"
            )
    dirty = bool(found["status"].strip())
    record = dict(
        engine_revision=git("rev-parse", "HEAD").strip(),
        checkout_dirty=dirty,
        checkout_status=found["status"].splitlines(),
        dirty_diff="checkout.patch" if found["diff"] else None,
        untracked_executed=found["untracked_executed"],
    )
    if untracked:
        from validation import source_snapshot

        folder = Path(out) / "untracked-sources"
        source_snapshot.freeze(ROOT, folder, {name: name for name in untracked})
        manifest = (folder / "SNAPSHOT.json").read_bytes()
        record["untracked_sources"] = dict(
            folder="untracked-sources",
            files=untracked,
            manifest_sha256=hashlib.sha256(manifest).hexdigest(),
        )
    return record, found["diff"] or None


def late_sources(out, source):
    """source, with any executed source Git does not track that the run loaded after provenance()
    took its record: each one's full content appended to OUT/checkout.patch, its path to
    untracked_executed (validation/executed_sources.untracked)."""
    if "snapshot" in source:
        return source
    from validation import executed_sources

    known = set(source.get("untracked_executed", ()))
    new = [p for p in executed_sources.untracked(ROOT) if p not in known]
    if not new:
        return source
    with (Path(out) / "checkout.patch").open("a") as stream:
        stream.write(executed_sources.untracked_diff(ROOT, new))
    return dict(
        source,
        checkout_dirty=True,
        dirty_diff="checkout.patch",
        untracked_executed=sorted(known | set(new)),
        untracked_executed_after_start=sorted(
            {*source.get("untracked_executed_after_start", ()), *new}
        ),  # fmt: skip
    )


def slug(text):
    return re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-")


def collect(spec):
    """The state at each observed step of a windowed run of `spec`: {step: state}."""
    dt = spec.execution.dt
    wanted = {int(round(float(t) / dt)) for t in spec.experiment.observation_times}
    states = {}
    for window in iter_windows(spec, POLICY):
        for i, _ in enumerate(np.asarray(window.times)):
            k = window.start_step + i
            if k in wanted:
                states[k] = type(window.history)(*(np.asarray(v)[i] for v in window.history))
    return states


def classes(block):
    """{class: [(kind, route index), ...]}: the sheet's five heat classes (module docstring)."""
    gene_made = {c.product for c in block.chains if c.template_copies is not None}
    out = {"H_tx": [], "H_tl": [], "H_deg_R": [], "H_deg_P": [], "H_rc": []}
    for i, c in enumerate(block.chains):
        out["H_tx" if c.template_copies is not None else "H_tl"].append(("chain", i))
    for i, d in enumerate(block.degradations):
        out["H_deg_R" if d.polymer in gene_made else "H_deg_P"].append(("degradation", i))
    for i, _ in enumerate(block.transfers):
        out["H_rc"].append(("transfer", i))
    return {k: v for k, v in out.items() if v}


def free_energy(amounts, transit, mu, residue_mu, volume, c0):
    """G of a state (§3.4) in pJ, as a Decimal: sum over rows n RT (mu°/RT + ln(n/(V c0)) - 1)
    plus sum over chains RT mu°_res/RT W. amounts and mu are {row: value}; transit and
    residue_mu {chain: value}."""
    with localcontext() as ctx:
        ctx.prec = DIGITS
        rt = sheet.R_GAS * sheet.T_K / 1000  # kJ/mol, so fmol times kJ/mol is pJ.
        v, c = Decimal(repr(volume)), Decimal(repr(c0))
        total = Decimal(0)
        for row, n in amounts.items():
            n = Decimal(repr(n))
            total += n * rt * (Decimal(repr(mu[row])) + (n / (v * c)).ln() - 1)
        for chain, w in transit.items():
            total += rt * Decimal(repr(residue_mu[chain])) * Decimal(repr(w))
        return total


def exported_cell(spec, block, cell=None):
    """The cell the export reads, by its ID (module docstring): the one cell holding every route,
    or the named one. Refused where the routes span several cells and none is named."""
    cells = [c.id for c in spec.model.cells]
    hosts = sorted({p.cell for p in block.pools} | {d.cell for d in block.degradations}
                   | {t.cell for t in block.transfers})  # fmt: skip
    if cell is None:
        if len(hosts) != 1:
            raise ValueError(f"the routes are in cells {hosts}: name the cell to export")
        return hosts[0]
    if cell not in cells:
        raise ValueError(f"no cell {cell!r}: the cells are {cells}")
    return cell


def readouts(spec, states, cell=None):
    """(times, {readout: [value per output]}, checks) of one run, at the exported cell
    (exported_cell), which checks names as exported_cell."""
    model = get_model(spec.model)
    _, p = model.initial_values(spec)
    species = list(spec.model.species_ids)
    reference = np.asarray(p.amount_reference)
    dt = spec.execution.dt
    (block,) = [d for d in spec.model.operators if d.law == worlds.POLYMERISATION]
    cell = exported_cell(spec, block, cell)
    at = [c.id for c in spec.model.cells].index(cell)
    rows = [s.id for s in block.species] + (["X"] if "X" in species else [])
    mu = dict(zip([s.id for s in block.species], block.mu_RT, strict=True))
    volume = float(next(c.volume_pL for c in spec.model.cells if c.id == cell))
    residue_mu = {
        c.id: (mu[c.product] - float(np.log(block.c0_mM / sheet_c0()))) / c.residues
        for c in block.chains
    }
    here = dict(
        chain=[i for i, c in enumerate(block.chains) if c.cell == cell],
        pool=[i for i, q in enumerate(block.pools) if q.cell == cell],
        degradation=[i for i, d in enumerate(block.degradations) if d.cell == cell],
        transfer=[i for i, x in enumerate(block.transfers) if x.cell == cell],
    )
    membership = {
        name: [(kind, i) for kind, i in members if i in here[kind]]
        for name, members in classes(block).items()
    }
    membership = {name: members for name, members in membership.items() if members}
    times = [float(t) for t in spec.experiment.observation_times]
    out = {}

    def put(name, value):
        out.setdefault(name, []).append(float(value))

    g0 = None
    for t in times:
        s = states[int(round(t / dt))]
        increment = np.asarray(s.amount_increment)
        amounts = {
            row: float(reference[species.index(row), at] + increment[species.index(row), at])
            for row in rows
        }
        for row in rows:
            put(f"n_{row}", amounts[row])
        free = np.asarray(s.poly_free_machines_fmol)
        for i in here["pool"]:
            put(f"F_{block.pools[i].id}", free[i])
        complexes = np.asarray(s.poly_complexes_fmol)
        transit = {}
        for i in here["chain"]:
            c = block.chains[i]
            r = c.residues // c.stages
            for j in range(c.stages):
                put(f"C_{c.id}_{j + 1}", complexes[i, j])
            put(f"E_{c.id}", float(np.sum(complexes[i, : c.stages])))
            transit[c.id] = float(r * sum(j * complexes[i, j] for j in range(c.stages)))
            put(f"W_{c.id}", transit[c.id])
            put(f"int_J_I_{c.id}", np.asarray(s.poly_initiated_fmol)[i])
            put(f"int_S_{c.id}", np.asarray(s.poly_stage_exits_fmol)[i])
            put(f"int_Q_{c.id}", np.asarray(s.poly_released_fmol)[i])
        degraded = np.asarray(s.poly_degraded_fmol)
        for polymer in sorted({block.degradations[i].polymer for i in here["degradation"]}):
            mine = [i for i in here["degradation"] if block.degradations[i].polymer == polymer]
            put(f"int_D_{polymer}", math.fsum(float(degraded[i]) for i in mine))
        for i in here["degradation"]:
            put(f"int_D_route_{block.degradations[i].id}", degraded[i])
        for i in here["transfer"]:
            x = block.transfers[i]
            name = "int_J_C" if len(here["transfer"]) == 1 else f"int_J_C_{x.id}"
            put(name, np.asarray(s.poly_transferred_fmol)[i])
        heats = {
            "chain": np.asarray(s.poly_chain_heat_pJ),
            "degradation": np.asarray(s.poly_degradation_heat_pJ),
            "transfer": np.asarray(s.poly_transfer_heat_pJ),
        }
        routes = {
            "chain": block.chains,
            "degradation": block.degradations,
            "transfer": block.transfers,
        }
        for kind, items in routes.items():
            for i in here[kind]:
                put(f"H_route_{items[i].id}", heats[kind][i])
        for name, members in membership.items():
            put(name, sum(float(heats[kind][i]) for kind, i in members))
        put("H_total", float(np.asarray(s.poly_dissipated_energy_pJ)[at]))
        put("H_routes_sum", sum(float(heats[kind][i]) for kind in heats for i in here[kind]))
        g = free_energy(
            {row: amounts[row] for row in mu}, transit, mu, residue_mu, volume, block.c0_mM
        )
        g0 = g if g0 is None else g0
        put("G_minus_G0", g - g0)
    ribosome = any(c.template_species for c in block.chains)
    window = float(sheet.A1M["window_rib" if ribosome else "window_pol"])
    full = float(sheet.A1M["t_end_rib" if ribosome else "t_end_pol"])
    if "X" not in rows and times[-1] == full:  # A1-M's release rate over its final window (§5.2).
        k_end, k_start = len(times) - 1, times.index(times[-1] - window)
        for i in here["chain"]:
            q = out[f"int_Q_{block.chains[i].id}"]
            out[f"J_bar_{block.chains[i].id}"] = [(q[k_end] - q[k_start]) / window]
    uneven = sorted(k for k, v in out.items() if not k.startswith("J_bar") and len(v) != len(times))
    if uneven:
        raise ValueError(f"the export holds {uneven[:3]} with other than one value per output")
    scale = max(abs(v) for v in out["H_total"]) or 1.0
    identity = [g + h for g, h in zip(out["G_minus_G0"], out["H_total"], strict=True)]
    split = [a - b for a, b in zip(out["H_routes_sum"], out["H_total"], strict=True)]
    magnitude = float(np.asarray(states[max(states)].poly_energy_magnitude_pJ)[at])
    checks = dict(
        G_identity_largest_pJ=max(abs(x) for x in identity),
        G_identity_over_sum_H_at_end=max(abs(x) for x in identity) / scale,
        routes_minus_total_largest_pJ=max(abs(x) for x in split),
        routes_minus_total_over_magnitude=max(abs(x) for x in split) / (magnitude or 1.0),
        H_total_at_end_pJ=out["H_total"][-1],
        energy_magnitude_at_end_pJ=magnitude,
        smallest_class_increment={
            name: min(b - a for a, b in zip(out[name], out[name][1:], strict=False))
            for name in membership
        },
        exported_cell=cell,
    )
    return times, out, checks


def sheet_c0():
    return worlds.C0_MM


def own_ledgers(spec, state):
    op = OPERATORS[worlds.POLYMERISATION]
    _, p = get_model(spec.model).initial_values(spec)
    own = op.own_ledgers(state, p, xp=np)
    return {k: [float(x) for x in np.atleast_1d(v)] for k, v in own.items()}


def run(name, label, symbols, dt, end, out):
    raw = worlds.world(name, dt=dt, symbols=symbols, end=end if name == "A1" else None)
    spec = parse_spec(raw)
    started = time.perf_counter()
    states = collect(spec)
    wall = time.perf_counter() - started
    times, values, checks = readouts(spec, states)
    path = out / slug(label) / f"{slug(name)}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    record = dict(
        kind="cells.gene_regulation.engine_run@1",
        world=name,
        cell=checks["exported_cell"],
        set=label,
        symbols_RT={k: str(v) for k, v in symbols.items()},
        dt_s=dt,
        end_s=float(spec.experiment.end_time),
        steps=int(round(float(spec.experiment.end_time) / dt)),
        wall_s=wall,
        t=times,
        readouts=values,
        checks=checks,
        own_ledgers_at_end=own_ledgers(spec, states[max(states)]),
        definition=raw,
    )
    path.write_text(json.dumps(record, indent=1, default=float) + "\n")
    return dict(world=name, set=label, wall_s=wall, file=str(path.relative_to(out)), **checks)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--worlds", nargs="+", default=["all"])
    parser.add_argument("--sets", nargs="+", default=["test instance", "Spirin's E_pep"])
    parser.add_argument("--dt", type=float, default=0.5)
    parser.add_argument("--end", type=float, help="A1 only: another horizon")
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    source, patch = provenance(out)
    if patch is not None:
        (out / "checkout.patch").write_text(patch)
    everything = sheet.potential_sets(interior=any(s.startswith("interior") for s in args.sets))
    sets = {label: everything[label] for label in args.sets}
    names = worlds.names() if args.worlds == ["all"] else args.worlds
    record = dict(
        what="The engine's development runs of option A (G4). Development, not judged.",
        sheet_tag=SHEET_TAG,
        **source,
        python=platform.python_version(),
        dt_s=args.dt,
        sets={label: {k: str(v) for k, v in s.items()} for label, s in sets.items()},
        worlds=names,
        created_utc=stamp,
        runs=[],
    )
    for label, symbols in sets.items():
        for name in names:
            record["runs"].append(run(name, label, symbols, args.dt, args.end, out))
            record.update(late_sources(out, record))
            (out / "run_record.json").write_text(json.dumps(record, indent=1) + "\n")
            print(json.dumps(record["runs"][-1]), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
