"""FR-38's step 5, the requester's acceptance (D284; the sheet's §9.16, amendment S, and §9.18,
erratum E): replace a producer midway through a chase, then restart. Development, not judged.

**The world** (chase_world). R1 at p = 0.75 (the requester's 80 attached chains, an exit half-life
of 1 h), with A1's transcription so that its producer keeps making RNA. FR-42's label owner labels
the fate rows R and R_s by shares, with producer x window labels on transcription's own label
schedule (a label source's, D296):
- releases in the window [0, W) take g0's cohort label;
- later releases take g0's label;
- from the replacement at T_E, g1's label. At T_E, replacement@1 replaces the producer's cell by a
  newcomer from template T, which has the founder's declared state and values (amendment S's
  occupant rule).

Each label names its producer (cell, generation, chain). The releases are marked at release (the
requester's answer to (e)), so each release takes its producer's label at its own step.

**What stays in the cell.** Until amendment T's export (§9.17) is built, only the newcomer's
material stays in the cell. replacement@1 removes the departing occupant's rows whole, and this
operator removes its chains in progress and its hold (§9.16). So:
- the departing generation g0's RNA is read from the label owner's removal record, never from a
  row: `label_removed_fmol` for its rows and `label_pool_removed_fmol` for its hold, by label;
- the newcomer g1's RNA is read from the rows, by share.

**The readouts** (readouts), at every output:
- each generation's RNA: in the cell, each fate row times its labels' shares; departed, the removal
  record by label;
- the window cohort: in the cell until T_E, then departed with g0. Its members alive at W, the same
  molecules alive at a later TS before T_E, and their ratio (the requester's survival readout,
  §9.8);
- the counters' generations (§9.16, item 3): g0's totals at its death, g1's from zero.

**The checks** (each a verdict in replace_restart.json; check):
1. labels change no physics: every physical observation of the labelled run equals the unlabelled
   run's, bit for bit;
2. the restart: checkpointed at T_C after the replacement, written to snapshot files and resumed,
   every recorded step equals the uninterrupted run's, bit for bit, labels and records included, so
   the resumed run's readouts, the cohort counts among them, are the uninterrupted run's;
3. the generations apart: no g1 share before T_E, and no g0 share in the cell after it;
4. the records agree: each fate row's removal record, summed over its labels, is replacement@1's
   removed amount, and the hold's is the operator's H_rem, within rounding;
5. the per-producer identities (§9.16, item 4): g0's over its life and g1's from its birth, within
   rounding.

Run: PYTHONPATH=src:. JAX_ENABLE_X64=1 python -m validation.gene_regulation.replace_restart
--out DIR
"""

import argparse
import json
from dataclasses import fields
from pathlib import Path

import numpy as np

from cells.definitions.specs import parse_spec
from cells.execution.runner import run
from cells.operators.templated_polymerisation import COPY_FMOL
from cells.records.io import load_snapshot, write_snapshot
from validation.gene_regulation import engine_run, kernel, worlds
from validation.tissue import secreted_species_fixtures as sfx

K_I = float(worlds.sheet.A1["k_I_tx"])
W, T_E, TS, T_C, END, EVERY = 1200.0, 3000.0, 2400.0, 3600.0, 4800.0, 600.0
CHAIN, ROWS = "tx", worlds.R1_LABELLED  # Transcription; its fate rows R and R_s.
G0, G1 = f"{worlds.CELL}-g0-{CHAIN}", f"{worlds.CELL}-g1-{CHAIN}"  # (cell, generation, chain).
COHORT = f"{G0}-cohort"  # g0's releases in [0, W): the window crossed with the producer.
LABELS = ("base", COHORT, G0, G1)  # The base first (the newcomer template's material).
EPS = float(np.finfo(float).eps)


def chase_world(*, labelled=True):
    """The module docstring's world, every output EVERY seconds to END."""
    raw = kernel.truncated(worlds.r1(0.75, initiation=K_I), END)
    raw["experiment"]["observation_times"] = [float(t) for t in np.arange(0.0, END + 1, EVERY)]
    template = sfx.template(raw, worlds.CELL, "T")
    raw = sfx.with_replacement(raw, [template], [(T_E, worlds.CELL, "T", f"{worlds.CELL}_g1")])
    rates = {
        c["route_id"]: c["schedule"][0]["value"]
        for c in raw["experiment"]["polymerisation_controls"]
    }
    kernel.block(raw)["templates"] = [dict(template_id="T", rates=rates)]  # The founder's values.
    if not labelled:
        return raw
    raw["model"]["operators"].append(
        dict(
            law=worlds.SHARE_LABELS,
            species=[dict(id=row, labels=list(LABELS), initial=[]) for row in ROWS],
        )
    )
    own = [(0.0, COHORT), (W, G0), (T_E, G1)]  # Transcription's source schedule (D296).
    raw["experiment"]["label_arrivals"] = [
        dict(species=row, schedule=[dict(time=0.0, label="base")]) for row in ROWS
    ] + [
        dict(
            species=ROWS[0],
            source=CHAIN,
            schedule=[dict(time=t, label=label) for t, label in own],
        )
    ]
    return raw


def _bits(a):
    a = np.ascontiguousarray(np.asarray(a))
    return a.dtype.str, a.shape, a.tobytes()


def _observed(obs):
    return {f.name: np.asarray(getattr(obs, f.name)) for f in fields(obs)}


def readouts(spec, obs, times):
    """{time: readouts} at each of `times`, the run's outputs (module docstring), in fmol and
    copies."""
    o = _observed(obs)
    species = list(spec.model.species_ids)
    out = {}
    for i, t in enumerate(times):
        row = {}
        for j, fate in enumerate(ROWS):
            n = float(o["amount"][i, species.index(fate), 0])
            share = o["label_share"][i, j, :, 0]
            removed = o["label_removed_fmol"][i, j, :, 0]
            row[fate] = dict(
                in_cell={label: n * float(s) for label, s in zip(LABELS, share, strict=True)},
                departed={label: float(r) for label, r in zip(LABELS, removed, strict=True)},
            )
        hold = o["label_pool_removed_fmol"][i, 0, :, 0]
        row["hold_departed"] = {label: float(h) for label, h in zip(LABELS, hold, strict=True)}
        cell = sum(row[f]["in_cell"][label] for f in ROWS for label in (COHORT, G0))
        row["g0_in_cell_fmol"] = cell
        row["g0_departed_fmol"] = sum(
            row[f]["departed"][label] for f in ROWS for label in (COHORT, G0)
        )
        row["g1_in_cell_fmol"] = sum(row[f]["in_cell"][G1] for f in ROWS)
        row["cohort_in_cell_fmol"] = sum(row[f]["in_cell"][COHORT] for f in ROWS)
        row["cohort_departed_fmol"] = sum(row[f]["departed"][COHORT] for f in ROWS)
        for key in [k for k in row if k.endswith("_fmol")]:
            row[key.replace("_fmol", "_copies")] = row[key] / COPY_FMOL
        out[float(t)] = row
    return out


def survival(rows):
    """The requester's survival readout (§9.8) of the window cohort: its members alive at W, the
    same molecules alive at TS, their ratio (undefined at a zero denominator), and what departed
    with g0 at T_E."""
    alive = {t: rows[t]["cohort_in_cell_fmol"] for t in (W, TS)}
    return dict(
        at_W_copies=alive[W] / COPY_FMOL,
        at_TS_copies=alive[TS] / COPY_FMOL,
        fraction=None if alive[W] == 0 else alive[TS] / alive[W],
        departed_at_T_E_copies=rows[END]["cohort_departed_copies"],
    )


def identities(spec, obs):
    """The per-producer identities (§9.16, item 4) at the last output: g0 over its life [0, T_E),
    g1 from its birth; each a residual with its rounding bound."""
    o = _observed(obs)
    species = list(spec.model.species_ids)
    last = -1
    rows = [species.index(f) for f in ROWS]
    n0 = [float(o["amount"][0, r, 0]) for r in rows]
    removed = [float(o["replacement_removed_fmol"][last, r, 0]) for r in rows]
    supplied = [float(o["replacement_supplied_fmol"][last, r, 0]) for r in rows]
    h0 = float(np.sum(o["poly_hold_fmol"][0]))
    h_rem = float(np.sum(o["poly_rep_hold_removed_fmol"][last]))
    a_g0 = float(o["poly_rep_chain_departed_fmol"][last, 0, 2])  # The released counter.
    d_g0 = [float(v) for v in o["poly_rep_degradation_departed_fmol"][last]]
    g0_terms = [h0, a_g0, h_rem, *removed, *n0, *d_g0]
    g0 = h0 + a_g0 - h_rem - sum(r - n + d for r, n, d in zip(removed, n0, d_g0, strict=True))
    birth_a = float(o["poly_rep_chain_birth_fmol"][last, 0, 2])
    birth_d = [float(v) for v in o["poly_rep_degradation_birth_fmol"][last]]
    a_g1 = float(o["poly_released_fmol"][last, 0]) - birth_a
    h_now = float(np.sum(o["poly_hold_fmol"][last]))
    n_now = [float(o["amount"][last, r, 0]) for r in rows]
    d_now = [float(v) for v in o["poly_degraded_fmol"][last]]
    g1 = (
        a_g1
        - h_now
        - sum((n - s) + (d - b) for n, s, d, b in zip(n_now, supplied, d_now, birth_d, strict=True))
    )
    g1_terms = [a_g1, birth_a, h_now, *n_now, *supplied, *d_now, *birth_d]

    steps = round(END / spec.execution.dt)

    def bound(terms):  # Rounding accumulated by the cumulative counters over the run's steps.
        return 64 * EPS * steps * max(abs(v) for v in terms) + 1e-30

    return dict(
        g0=dict(
            residual_fmol=g0,
            bound_fmol=bound(g0_terms),
            arrivals_fmol=a_g0,
            hold_removed_fmol=h_rem,
        ),
        g1=dict(residual_fmol=g1, bound_fmol=bound(g1_terms), arrivals_fmol=a_g1),
    )


def check(out):
    """The module docstring's checks on a fresh folder `out`; returns the record."""
    plain = run(parse_spec(chase_world(labelled=False)))
    spec = parse_spec(chase_world())
    full = run(spec)
    obs, base = _observed(full.observations), _observed(plain.observations)
    physical = sorted(k for k in base if _bits(base[k]) != _bits(obs.get(k, np.empty(0))))
    checkpoint = full.checkpoint_at(T_C)
    write_snapshot(out / "checkpoint", full.spec, checkpoint)
    loaded = load_snapshot(out / "checkpoint")
    resumed = run(loaded.spec, loaded.checkpoint)
    names = getattr(type(full.history), "_fields", None) or [f.name for f in fields(full.history)]
    steps = [
        k
        for k, (a, b) in enumerate(zip(resumed.history, full.history, strict=True))
        if _bits(a) != _bits(np.asarray(b)[checkpoint.step_index :])
    ]
    times = np.asarray(spec.experiment.observation_times)
    share = obs["label_share"]  # [time, m, label, cell]
    before, after = times < T_E, times > T_E
    g1 = LABELS.index(G1)
    g0 = [LABELS.index(COHORT), LABELS.index(G0)]
    rows_record = obs["label_removed_fmol"][:, :, :, 0].sum(axis=2)  # [time, m]
    species = list(spec.model.species_ids)
    swapped = obs["replacement_removed_fmol"][:, [species.index(f) for f in ROWS], 0]
    pool_record = obs["label_pool_removed_fmol"][:, 0, :, 0].sum(axis=1)
    h_rem = obs["poly_rep_hold_removed_fmol"].reshape(len(times), -1).sum(axis=1)
    record_gap = float(np.max(np.abs(rows_record - swapped)))
    pool_gap = float(np.max(np.abs(pool_record - h_rem)))
    whole = readouts(spec, full.observations, times)
    later = readouts(loaded.spec, resumed.observations, times[times >= checkpoint.time])
    same = all(whole[t] == later[t] for t in later)
    ids = identities(spec, full.observations)
    verdicts = {
        "1 labels change no physics": not physical,
        "2 the restart reproduces every step bit for bit": not steps,
        "2 the resumed readouts are the uninterrupted run's": same and bool(later),
        "3 no g1 share before T_E": bool(np.all(share[before][:, :, g1] == 0.0)),
        "3 no g0 share in the cell after T_E": bool(np.all(share[after][:, :, g0] == 0.0)),
        "4 the rows' record is replacement@1's removed amount": record_gap
        <= 64 * EPS * float(np.max(np.abs(swapped)) + 1e-300),
        "4 the hold's record is H_rem": pool_gap <= 64 * EPS * float(np.max(h_rem) + 1e-300),
        "5 g0's identity": abs(ids["g0"]["residual_fmol"]) <= ids["g0"]["bound_fmol"],
        "5 g1's identity": abs(ids["g1"]["residual_fmol"]) <= ids["g1"]["bound_fmol"],
    }
    verdicts = {name: bool(ok) for name, ok in verdicts.items()}
    return dict(
        kind="cells.gene_regulation.replace_restart@1",
        world=dict(
            r1_p=0.75,
            k_I=K_I,
            window_s=[0.0, W],
            replacement_s=T_E,
            survival_s=TS,
            checkpoint_s=T_C,
            end_s=END,
            labels=list(LABELS),
            dt_s=spec.execution.dt,
        ),  # fmt: skip
        limit=(
            "until amendment T's export is built only the newcomer's material stays in the cell; "
            "the departing g0 RNA is read from the removal record, never from a row"
        ),
        verdicts=verdicts,
        passed=all(verdicts.values()),
        physical_fields_differing=physical,
        resumed_fields_differing=[names[k] for k in steps],
        record_gap_fmol=record_gap,
        pool_record_gap_fmol=pool_gap,
        identities=ids,
        survival=survival(whole),
        resumed_outputs_s=sorted(later),
        readouts={str(t): v for t, v in whole.items()},
        checkpoint=dict(time=float(checkpoint.time), step_index=int(checkpoint.step_index)),
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    source, patch = engine_run.provenance(out)
    if patch is not None:
        (out / "checkout.patch").write_text(patch)
    record = check(out)
    record.update(engine_run.late_sources(out, source))
    (out / "replace_restart.json").write_text(json.dumps(record, indent=1) + "\n")
    print(json.dumps(record["verdicts"], indent=1))
    return 0 if record["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
