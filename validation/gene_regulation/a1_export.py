"""The engine's development export of the sheet's A1 (gene regulation's option A, G4): its own
trajectory, for the reviewer. Development, not judged.

It runs validation/gene_regulation/worlds.a1 and writes, into a fresh directory:
- a1_export.csv: at every output time, in the units its header names:
  - t (s);
  - the protein P and the mRNA R, in fmol and copies;
  - the cumulative releases ∫Q of translation (tl) and transcription (tx);
  - the cumulative degradations ∫D of P and R;
- run_record.json: what it is (development, not judged), the sheet's tag, the definition, dt,
  horizon, steps and wall time, the engine revision (git HEAD) and whether the checkout was dirty,
  each column's unit, and the run's own end state of every operator ledger;
- checkout.patch: the dirty diff against HEAD, written only when the checkout is dirty.

Run: PYTHONPATH=src:. JAX_ENABLE_X64=1 python -m validation.gene_regulation.a1_export [--dt S]
[--end S] [--every S] [--out DIR].
"""

import argparse
import csv
import json
import platform
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from cells.definitions.specs import parse_spec
from cells.execution.windows import WindowPolicy, iter_windows
from cells.operators.templated_polymerisation import COPY_FMOL
from cells.registry.models import get_model
from validation.gene_regulation import worlds

ROOT = Path(__file__).resolve().parents[2]
SHEET_TAG = "gr1-sheet-2026-11-20b"
POLICY = WindowPolicy(window_steps=10000, recording="observations")
COLUMNS = (
    ("t_s", "s"),
    ("protein_P_fmol", "fmol"),
    ("protein_P_copies", "copies"),
    ("mRNA_R_fmol", "fmol"),
    ("mRNA_R_copies", "copies"),
    ("released_tl_fmol", "fmol, cumulative from t = 0"),
    ("released_tl_copies", "copies, cumulative from t = 0"),
    ("released_tx_fmol", "fmol, cumulative from t = 0"),
    ("released_tx_copies", "copies, cumulative from t = 0"),
    ("degraded_P_fmol", "fmol, cumulative from t = 0"),
    ("degraded_P_copies", "copies, cumulative from t = 0"),
    ("degraded_R_fmol", "fmol, cumulative from t = 0"),
    ("degraded_R_copies", "copies, cumulative from t = 0"),
)


def git(*args):
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout


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


def rows(spec, states):
    """[(column values), ...] at every output time."""
    model = get_model(spec.model)
    _, p = model.initial_values(spec)
    species = list(spec.model.species_ids)
    reference = np.asarray(p.amount_reference)
    dt = spec.execution.dt
    (block,) = [d for d in spec.model.operators if d.law == worlds.POLYMERISATION]
    chains = [c.id for c in block.chains]
    degradations = [d.id for d in block.degradations]
    out = []
    for t in spec.experiment.observation_times:
        s = states[int(round(float(t) / dt))]

        def amount(name, s=s):
            r = species.index(name)
            return float(reference[r, 0] + np.asarray(s.amount_increment)[r, 0])

        released = np.asarray(s.poly_released_fmol)
        degraded = np.asarray(s.poly_degraded_fmol)
        values = [
            amount("P"),
            amount("R"),
            float(released[chains.index("tl")]),
            float(released[chains.index("tx")]),
            float(degraded[degradations.index("deg_P")]),
            float(degraded[degradations.index("deg_R")]),
        ]
        p_f, r_f, tl, tx, dp, dr = values
        out.append(
            (float(t), p_f, p_f / COPY_FMOL, r_f, r_f / COPY_FMOL, tl, tl / COPY_FMOL, tx,
             tx / COPY_FMOL, dp, dp / COPY_FMOL, dr, dr / COPY_FMOL)
        )  # fmt: skip
    return out


def ledgers(spec, state):
    """The operator's own ledgers at the end state, and their bounds' magnitudes."""
    from cells.operators import OPERATORS

    op = OPERATORS[worlds.POLYMERISATION]
    model = get_model(spec.model)
    _, p = model.initial_values(spec)
    own = op.own_ledgers(state, p, xp=np)
    return {k: [float(x) for x in np.atleast_1d(v)] for k, v in own.items()}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dt", type=float, default=0.5)
    parser.add_argument("--end", type=float)
    parser.add_argument("--every", type=float, default=60.0)
    parser.add_argument("--out")
    args = parser.parse_args(argv)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out = Path(args.out or f"/mnt/workspaces/Cells/gene-regulation-20261120/a1-dev-export-{stamp}")
    out.mkdir(parents=True, exist_ok=False)
    revision = git("rev-parse", "HEAD").strip()
    status = git("status", "--porcelain")
    dirty = bool(status.strip())
    if dirty:
        (out / "checkout.patch").write_text(git("diff", "HEAD"))
    raw = worlds.a1(dt=args.dt, end=args.end, every=args.every)
    spec = parse_spec(raw)
    started = time.perf_counter()
    states = collect(spec)
    wall = time.perf_counter() - started
    table = rows(spec, states)
    with (out / "a1_export.csv").open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow([name for name, _ in COLUMNS])
        writer.writerows([[repr(v) for v in row] for row in table])
    end_state = states[max(states)]
    record = dict(
        what="The engine's development export of the sheet's A1 (G4). Development, not judged.",
        sheet_tag=SHEET_TAG,
        potentials="the sheet's numeric test instance (§3.3); the registration names its source",
        world="validation/gene_regulation/worlds.a1",
        dt_s=args.dt,
        end_s=float(spec.experiment.end_time),
        steps=int(round(float(spec.experiment.end_time) / args.dt)),
        outputs=len(table),
        wall_s=wall,
        engine_revision=revision,
        checkout_dirty=dirty,
        checkout_status=status.splitlines(),
        dirty_diff="checkout.patch" if dirty else None,
        python=platform.python_version(),
        units=dict(COLUMNS),
        copies_per_fmol=1.0 / COPY_FMOL,
        operator_ledgers_at_end=ledgers(spec, end_state),
        created_utc=stamp,
        definition=raw,
    )
    (out / "run_record.json").write_text(json.dumps(record, indent=1, default=float) + "\n")
    print(json.dumps({k: record[k] for k in ("engine_revision", "checkout_dirty", "steps",
                                             "wall_s")}, default=float))  # fmt: skip
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
