"""FR-7 item 3's comparison: the C-worlds' clearance against R-clear's RC2 and RC5.

The worlds are compartment_mapper's, the readings compartment_registration.json's, registered
before any engine output of either world. R-clear (validation/fr7/references/, registered
code-blind) is read through its interface only (interface/REFERENCES_USAGE.md, "R-clear: the
clearance clauses"):
* inputs.json's clearance_cases: each case's inputs and rows;
* clearance.json's synthetic_cases: each case's t_clear, bracket, D and c* rows, and every plant's
  outcome;
* clearance.hill_drive(c, K, n) and clearance.t_clear(rows_s, D, epsilon), whose call forms the
  usage note gives; their code is not read here. c* and the inclusion rule are this module's own,
  from the note's clauses 2 and 4.

c* at a row t (clause 2) is (the cell's n_T + the compartment's n_T, where it counts)/V, with V the
cell's declared volume. The compartment counts at t (clause 4) when its declared release rate is
positive on some interval starting at or after t: the release's schedule is read from the world's
definition (its exchange_controls), the rate in force at t being the last change at or before t.

The judged readings (the registration's J1 and J2):
* J1: t_clear from the engine's c* rows by R-clear's rule equals the case's registered t_clear;
* J2: the compartment plant with power in the world's case, applied to the engine's rows, gives its
  registered outcome: compartment_left_out (c* from the cell alone) in C2, and
  sealed_compartment_counted (the compartment counted at every row, whatever its release) in C5.
Everything else is information: the other compartment plant's outcome, c* and D against the case's
exact rows, the bracket, the chain's rows (chain_comparison.engine_rows on W2's quantities: no
registered reference covers a chain fed by a compartment), the template's account over the two
nodes, and the run's cost.

The stop rule: a refused step (the runner's NumericalError) or any other exception, during the run
or in reading its rows, is the world's recorded outcome, with the last checked time; its readings
are not met. Each world's report is written as soon as it ends.

Usage: compartment_comparison.py OUT_JSON [--interface DIR] [--world C2 C5] [--end S]
(--end runs a world's first S seconds: a smoke check, never judged.)
"""

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

from cells.definitions.specs import parse_spec
from cells.execution.windows import iter_windows
from cells.registry.models import get_model
from validation.fr7 import chain_comparison as cc
from validation.fr7 import chain_mapper as cm
from validation.fr7 import compartment_mapper as km

PLANTS = ("compartment_left_out", "sealed_compartment_counted")
JUDGED_PLANT = {"C2": "compartment_left_out", "C5": "sealed_compartment_counted"}


def load(interface):
    interface = Path(interface)
    return dict(
        inputs=cm.inputs(interface / "inputs.json"),
        clearance=json.loads((interface / "clearance.json").read_text()),
    )


def release_schedule(raw):
    """[(time, rate), ...] of the world's one release route, from its definition."""
    controls = raw["experiment"]["exchange_controls"]
    if len(controls) != 1 or controls[0]["route_id"] != km.RELEASE:
        raise ValueError("a C-world declares one release route")
    return [(float(c["time"]), float(c["rate"])) for c in controls[0]["schedule"]]


def counts(schedule, t):
    """Clause 4: whether the release rate is positive on some interval starting at or after t, the
    rate in force at t being the last change at or before t, and each later change's rate holding
    from its time on."""
    in_force = [rate for start, rate in schedule if start <= t]
    later = [rate for start, rate in schedule if start > t]
    return bool((in_force and in_force[-1] > 0.0) or any(rate > 0.0 for rate in later))


def c_star(n_cell, n_node, included, volume):
    """Clause 2: (the cell's n_T + the compartment's where it counts) / V, per row (mM)."""
    n_cell, n_node = np.asarray(n_cell, dtype=float), np.asarray(n_node, dtype=float)
    return (n_cell + np.where(np.asarray(included, dtype=bool), n_node, 0.0)) / volume


def template_rows(spec, collected):
    """{the cell's n_T, the node's n_T, turnover's cleared n_T and the release's moved amount}
    at each observed row (fmol; moved is export positive, so a release is negative)."""
    model = get_model(spec.model)
    _, p = model.initial_values(spec)
    dt = spec.execution.dt
    states, _ = collected
    index = [int(round(float(t) / dt)) for t in spec.experiment.observation_times]
    species = list(spec.model.species_ids).index(cm.TEMPLATE)
    node = [o.id for o in spec.model.extracellular].index(km.NODE)
    cell = [c.id for c in spec.model.cells].index(cm.CELL)
    ref_cell = float(np.asarray(p.amount_reference)[species, cell])
    ref_node = float(np.asarray(p.extracellular_amount_reference)[species, node])
    out = {"n_T_cell_fmol": [], "n_T_node_fmol": [], "cleared_fmol": [], "moved_fmol": []}
    for k in index:
        s = states[k]
        out["n_T_cell_fmol"].append(ref_cell + float(np.asarray(s.amount_increment)[species, cell]))
        out["n_T_node_fmol"].append(
            ref_node + float(np.asarray(s.extracellular_amount_increment)[species, node])
        )
        out["cleared_fmol"].append(float(np.asarray(s.turnover_cleared_fmol)[species, cell]))
        out["moved_fmol"].append(float(np.asarray(s.exchange_moved_fmol)[0]))
    return out


def t_clear_of(clearance, times, c, inp):
    """R-clear's rule on c* rows: (t_clear, D)."""
    cases = inp["clearance_cases"]
    drive = clearance.hill_drive(np.asarray(c, dtype=float), cases["K_mM"], cases["n"])
    return clearance.t_clear(list(times), drive, inp["clearance"]["epsilon"]), np.asarray(drive)


def deviation(engine, registered):
    """The largest |engine - registered| / |registered| over rows with a nonzero registered value,
    and its row's position."""
    engine, registered = np.asarray(engine, dtype=float), np.asarray(registered, dtype=float)
    nonzero = registered != 0.0
    rel = np.where(
        nonzero, np.abs(engine - registered) / np.where(nonzero, np.abs(registered), 1.0), 0.0
    )
    k = int(np.argmax(rel))
    return dict(largest=float(rel[k]), row=k)


def readings(inp, registered, world, times, template, schedule, *, partial):
    """The judged readings and their information for one world's rows."""
    from validation.fr7.references import clearance  # noqa: PLC0415 (the registered functions)

    volume = inp["clearance_cases"]["volume_pL"]
    epsilon = inp["clearance"]["epsilon"]
    included = [counts(schedule, t) for t in times]
    cell, node = template["n_T_cell_fmol"], template["n_T_node_fmol"]
    c = c_star(cell, node, included, volume)
    got, drive = t_clear_of(clearance, times, c, inp)
    plants = {
        "compartment_left_out": t_clear_of(
            clearance, times, c_star(cell, node, [False] * len(times), volume), inp
        )[0],
        "sealed_compartment_counted": t_clear_of(
            clearance, times, c_star(cell, node, [True] * len(times), volume), inp
        )[0],
    }
    case = registered["synthetic_cases"][km.CASES[world]]
    grid = inp["clearance_cases"]["rows_s"]
    rows = [grid.index(t) for t in times]
    out = dict(
        rows_s=list(times),
        included=included,
        c_star_mM=c.tolist(),
        D=drive.tolist(),
        information=dict(
            c_star_against_registered=deviation(c, [case["c_star_mM"][j] for j in rows]),
            D_against_registered=deviation(drive, [case["D"][j] for j in rows]),
        ),
    )
    if partial:
        out["status"] = "not judged: a partial run"
        return out
    at = times.index(got) if got is not None else None
    out["information"]["bracket"] = dict(
        engine=None
        if at is None or at == 0
        else dict(at=float(drive[at] / epsilon), before=float(drive[at - 1] / epsilon)),
        registered=case["bracket"],
    )
    out["J1_t_clear"] = dict(
        engine=got, registered=case["t_clear_s"], equal=got == case["t_clear_s"]
    )
    outcome = {
        name: dict(
            plant=name,
            engine=plants[name],
            registered=case["plants"][name]["t_clear_s"],
            equal=plants[name] == case["plants"][name]["t_clear_s"],
            power_engine=plants[name] != got,
            power_registered=case["plants"][name]["power"],
        )
        for name in PLANTS
    }
    out["J2_plant"] = outcome[JUDGED_PLANT[world]]
    out["information"]["other_plant"] = next(
        v for k, v in outcome.items() if k != JUDGED_PLANT[world]
    )
    out["passed"] = out["J1_t_clear"]["equal"] and out["J2_plant"]["equal"]
    return out


def account(template):
    """The template's account over the two nodes, from time 0 (fmol): the cell gains what the
    release moves in and loses what turnover clears; the node loses what the release moves out."""
    n_c, n_o = np.asarray(template["n_T_cell_fmol"]), np.asarray(template["n_T_node_fmol"])
    cleared, moved = np.asarray(template["cleared_fmol"]), np.asarray(template["moved_fmol"])
    cell = (n_c - n_c[0]) + (moved - moved[0]) + (cleared - cleared[0])
    node = (n_o - n_o[0]) - (moved - moved[0])
    return dict(
        cell_residual_fmol=float(np.max(np.abs(cell))),
        node_residual_fmol=float(np.max(np.abs(node))),
        total_residual_fmol=float(np.max(np.abs(cell + node))),
    )


def collect(spec, window_seconds):
    """chain_comparison.collect's rows, kept through a refusal (the stop rule): (collected, the
    last checked time, the refusal's text or None, the seconds of each of the first two windows)."""
    dt = spec.execution.dt
    wanted = {int(round(float(t) / dt)) for t in spec.experiment.observation_times}
    states, observed = {}, {name: [] for name in (*cc.OBSERVED, "times")}
    last, refusal, started = 0.0, None, time.perf_counter()
    try:
        for window in iter_windows(spec, cc.POLICY):
            for i, _ in enumerate(np.asarray(window.times)):
                k = window.start_step + i
                if k in wanted:
                    states[k] = type(window.history)(*(np.asarray(v)[i] for v in window.history))
            obs = window.observations
            for name in observed:
                observed[name].extend(np.asarray(getattr(obs, name)))
            last = float(np.asarray(window.times)[-1])
            if len(window_seconds) < 2:
                window_seconds.append(time.perf_counter() - started)
                started = time.perf_counter()
    except Exception as e:  # noqa: BLE001 (the stop rule: a refusal is a recorded outcome)
        refusal = f"{type(e).__name__}: {e}"
    return (states, observed), last, refusal


def compare_world(inp, registered, world, *, end=None):
    raw = km.definition(inp, world, end=end)
    spec = parse_spec(raw)
    started = time.perf_counter()
    windows = []
    collected, last, refusal = collect(spec, windows)
    out = dict(
        world=world,
        case=km.CASES[world],
        wall_s=time.perf_counter() - started,
        first_windows_s=windows,
        last_checked_time_s=last,
        passed=False,
    )
    if refusal is not None:
        out["refused"] = refusal
        return out
    try:
        times, chain = cc.engine_rows(spec, collected, inp, km.BASE)
        template = template_rows(spec, collected)
        partial = end is not None and end < inp["clearance_cases"]["rows_s"][-1]
        out.update(
            end_s=times[-1],
            steps=int(round(times[-1] / spec.execution.dt)),
            clearance=readings(
                inp, registered, world, times, template, release_schedule(raw), partial=partial
            ),
            template_account=account(template),
            engine_rows=dict(times=times, **template, **chain),
        )
    except Exception as e:  # noqa: BLE001 (the stop rule: reading the rows failed)
        out["refused"] = f"reading the rows: {type(e).__name__}: {e}"
        return out
    out["passed"] = bool(out["clearance"].get("passed", False))
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("out")
    parser.add_argument("--interface", default=str(cm.INTERFACE))
    parser.add_argument("--world", nargs="*", choices=sorted(km.CASES))
    parser.add_argument("--end", type=float)
    args = parser.parse_args(argv)
    refs = load(args.interface)
    inp = refs["inputs"]
    report = dict(interface=args.interface, worlds={})
    for world in args.world or sorted(km.CASES):
        r = compare_world(inp, refs["clearance"], world, end=args.end)
        report["worlds"][world] = r
        c = r.get("clearance", {})
        j2 = c.get("J2_plant")
        print(
            world,
            r.get("refused") or ("passed" if r["passed"] else c.get("status", "FAILED")),
            f"{r['wall_s']:.0f} s, first windows {[round(s, 1) for s in r['first_windows_s']]} s",
            c.get("J1_t_clear"),
            j2 and (j2["plant"], j2["engine"], j2["registered"]),
            flush=True,
        )
        Path(args.out).write_text(json.dumps(report, indent=1, default=float))
    return 0 if all(r["passed"] for r in report["worlds"].values()) else 1


if __name__ == "__main__":
    sys.exit(main())
