"""Replay FR-38 machine and residue inventories, or read both lossless fates from public exports."""

import argparse
import json
import math
from pathlib import Path
from tempfile import TemporaryDirectory

import jax
import numpy as np

from cells.definitions.specs import parse_spec
from cells.operators.templated_polymerisation import FATES
from cells.registry.models import get_model
from validation.gene_regulation import cohort, engine_run, kernel, sheet_check, worlds

EPS = np.finfo(float).eps
COPY = float(sheet_check.COPY_FMOL)


def observed(raw, end):
    raw = kernel.truncated(raw, end)
    raw["experiment"]["observation_times"] = list(range(0, end + 1, 2))
    return raw


def collect(raw):
    spec = parse_spec(raw)
    states = engine_run.collect(spec)
    times, values, checks = engine_run.readouts(spec, states)
    assert list(spec.experiment.observation_times) == times
    assert [step * spec.execution.dt for step in sorted(states)] == times
    return spec, [states[step] for step in sorted(states)], times, values, checks["exported_cell"]


def residual(*terms, ledger=None):
    """Bound cancellation in the original fmol terms, including any initial stock."""
    error = math.fsum(terms)
    scale = math.fsum(abs(x) for x in terms)
    assert abs(error) <= 128 * EPS * scale, (error, scale)
    if ledger is not None:
        assert abs(error - ledger) <= 128 * EPS * scale, (error, ledger, scale)
    return abs(error)


def inventories(policy):
    raw = observed(worlds.r1s(policy), 60)
    for arrivals in raw["experiment"]["label_arrivals"]:
        arrivals["schedule"][1]["time"] = 20.0
    fraction = next(
        c for c in raw["experiment"]["polymerisation_controls"] if c["route_id"] == worlds.RELEASE
    )
    fraction["schedule"][1]["time"] = 40.0
    spec, states, t, x, _ = collect(raw)
    block = next(b for b in spec.model.operators if b.law == worlds.POLYMERISATION)
    (chain,) = block.chains
    (pool,) = block.pools
    model = get_model(spec.model)
    _, layout = model.initial_values(spec)
    op = next(op for op in model.operators if op.LAW_ID == block.law)
    total = pool.machines * COPY
    initial = math.fsum(chain.release.initial_copies) * COPY
    length, m = chain.residues, chain.stages
    r = length // m
    (fates,) = chain.release.fates
    labelled_totals = {row: f"n_{row}" for row in fates}
    hold_key = f"H_{worlds.RELEASE}"
    labelled_totals[hold_key] = hold_key
    maxima = dict.fromkeys(("machines", "hold", "residues", "fate_amount", "label_sum"), 0.0)
    for k, s in enumerate(states):
        cs = s.poly_complexes_fmol[0, :m]
        free = float(s.poly_free_machines_fmol[0])
        held = math.fsum(s.poly_hold_fmol[0])
        engaged_hold = held if policy == "held" else 0.0
        detached = math.fsum(s.poly_hold_released_fmol[0].flat)
        completed = float(s.poly_released_fmol[0])
        exits = float(s.poly_stage_exits_fmol[0])
        transit = math.fsum(j * r * float(v) for j, v in enumerate(cs))
        assert free == x["F_pol"][k] and completed == x["int_Q_tx"][k]
        residual(*cs, engaged_hold, -x["E_tx"][k])
        residual(held, -x[f"H_{worlds.RELEASE}"][k])
        residual(transit, -x["W_tx"][k])
        internal = op.own_ledgers(s, layout, xp=np)
        machine_error = residual(
            free, *cs, engaged_hold, -total, ledger=internal["poly_machines"][0]
        )
        stage_ledger, hold_ledger = internal["poly_residues"]
        hold_error = residual(initial, completed, -held, -detached, ledger=hold_ledger / length)
        residue_error = residual(
            r * exits,
            length * initial,
            -transit,
            -length * held,
            -length * detached,
            ledger=stage_ledger + hold_ledger,
        )
        maxima["machines"] = max(maxima["machines"], machine_error)
        maxima["hold"] = max(maxima["hold"], hold_error)
        maxima["residues"] = max(maxima["residues"], residue_error)
        for f, row in enumerate(fates):
            q = float(s.poly_hold_released_fmol[0, 0, f])
            assert q == x[f"int_Q_{worlds.RELEASE}_{FATES[f]}"][k]
            err = residual(x[f"n_{row}"][k], -x[f"n_{row}"][0], -q, x[f"int_D_{row}"][k])
            maxima["fate_amount"] = max(maxima["fate_amount"], err)
        for row, key in labelled_totals.items():
            err = residual(
                *(x[f"label_{row}_{label}"][k] for label in worlds.R1_LABELS), -x[key][k]
            )
            maxima["label_sum"] = max(maxima["label_sum"], err)
    wrong_at_start = abs(
        math.fsum(
            (
                x["F_pol"][0],
                *states[0].poly_complexes_fmol[0],
                initial if policy == "returned" else 0.0,
                -total,
            )
        )
    )
    assert math.isclose(wrong_at_start, initial, rel_tol=2e-13) and initial > 0
    assert x["int_Q_tx"][-1] > 0 and min(states[-1].poly_hold_released_fmol[0].flat) > 0
    # Completed RNA enters the marked part of the hold until the window closes, then drains.
    marked_hold = x[f"label_H_{worlds.RELEASE}_cohort"]
    assert marked_hold[0] == 0 < marked_hold[-1] < marked_hold[t.index(20.0)]
    for row in fates:
        assert x[f"label_{row}_cohort"][-1] > 0
    # Check each step's gross split on both sides of the change in durable fraction.
    for left, right, p in ((0.0, 40.0, 0.75), (40.0, 60.0, 0.25)):
        steps = np.asarray(
            [s.poly_hold_released_fmol[0, 0] for s in states[t.index(left) : t.index(right) + 1]]
        )
        for durable, short in np.diff(steps, axis=0):
            assert durable > 0 and short > 0
            assert math.isclose(durable / (durable + short), p, rel_tol=2e-12)
    return dict(
        saved_rows=len(t),
        end_s=t[-1],
        initial_hold_copies=initial / COPY,
        wrong_policy_error_at_start_fmol=wrong_at_start,
        final_completions_fmol=completed,
        final_detachments_fmol=detached,
        marked_hold_at_close_fmol=marked_hold[t.index(20.0)],
        marked_hold_at_end_fmol=marked_hold[-1],
        max_abs_error_fmol=maxima,
    )


def lossless(omitted):
    raw = worlds.with_share_labels(observed(worlds.r1(0.5), 10), window=(2.0, 8.0))
    block = kernel.block(raw)
    block["degradations"] = [d for d in block["degradations"] if d["polymer"] != omitted]
    experiment = raw["experiment"]
    controls = [
        c for c in experiment["polymerisation_controls"] if c["route_id"] != f"deg_{omitted}"
    ]
    experiment["polymerisation_controls"] = controls
    for ctl in controls:
        if ctl["route_id"].startswith("deg_"):
            ctl["schedule"][0]["value"] = 0.0
    spec, states, t, x, cell = collect(raw)
    assert max(x["int_Q_tx"]) == 0 and all(np.all(s.poly_degraded_fmol == 0) for s in states)
    result = {}
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "export.json"
        path.write_text(json.dumps(dict(definition=spec.to_dict(), cell=cell, t=t, readouts=x)))
        for f, row in enumerate(("R", "R_s")):
            released = x[f"int_Q_{worlds.RELEASE}_{FATES[f]}"]
            amount = x[f"n_{row}"]
            assert released[-1] > 0
            np.testing.assert_array_equal(
                released, [s.poly_hold_released_fmol[0, 0, f] for s in states]
            )
            # With no loss, actual cohort increments equal gross detachment at each marked step.
            marked = x[f"label_{row}_cohort"]
            for i, when in enumerate(t):
                stop = t.index(min(max(when, 2.0), 8.0))
                residual(marked[i], -(released[stop] - released[t.index(2.0)]))
            max_error = max(
                residual(n, -amount[0], -q) for n, q in zip(amount, released, strict=True)
            )
            rec = dict(
                final_released_fmol=released[-1],
                final_gain_fmol=amount[-1] - amount[0],
                max_balance_error_fmol=max_error,
                loss_series_exported=f"int_D_{row}" in x,
                marked_received_fmol=marked[-1],
            )
            try:
                series = cohort.read(path, product=row)
                assert series[1] == amount and series[2] == released and series[3] == [0.0] * len(t)
                made, alive, gain = cohort.survivors(*series, t[0], t[-1])
                residual(made, -alive)
                residual(amount[-1], -amount[0], -made)
                assert gain == amount[-1] - amount[0]
                rec.update(readable=True, surviving_fmol=alive)
            except ValueError as error:
                rec.update(readable=False, refusal=str(error))
            result[row] = rec
    assert result["R"]["final_released_fmol"] == result["R_s"]["final_released_fmol"]
    return dict(omitted_loss_route=f"deg_{omitted}", saved_rows=len(t), cell=cell, fates=result)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--lossless", action="store_true", help="read the two lossless fates with each omission"
    )
    args = parser.parse_args()
    jax.config.update("jax_enable_x64", True)
    if args.lossless:
        report = [lossless(row) for row in ("R", "R_s")]
        passed = all(fate["readable"] for case in report for fate in case["fates"].values())
    else:
        report = {policy: inventories(policy) for policy in ("returned", "held")}
        passed = True
    print(json.dumps(dict(passed=passed, cases=report), indent=2, allow_nan=False))
    raise SystemExit(0 if passed else 1)
