"""FR-7 F3's comparison: the engine's R-chain worlds against the registered references.

R-chain and R-clear (validation/fr7/references/, registered code-blind and tagged
fr7-references-registered-2026-11-19) are read through their interface only
(interface/REFERENCES_USAGE.md, "How a comparison reads them"):
1. each world is built from interface/inputs.json by chain_mapper and run at the declared
   step, observed at its rows;
2. every row whose status is "compared" passes when |engine - value| <= band (interface/rows.json).
   The material total is formed from the engine's rows with the declared c_u:
   total = n_P + (sum M_j + N + R) / c_u + C_P - S_P t;
3. the clearance row: D from the engine's template rows by the references' registered
   clearance.hill_drive(n_T / V, K, n), then clearance.t_clear(rows_s, D, epsilon), equal to the
   registered row. Those two functions are imported from validation.fr7.references.clearance
   (their code is not read here); before the references are on main the clearance row is
   reported as pending;
4. the registered power, as context: zero_power.json's compared core rows without any plant
   (empty in every registered world), and per quantity the plants with power
   (zero_power.json, plants.json), so a pass is read against what the comparison can see.

The engine's quantities at a row:
* n_T, n_P, Na, K and Cl: the cell's amounts;
* F_T: the coupling's observed factor at the row's own state (coupling_factor);
* N: membrane state's units (declared plus increment);
* M_j: the producer's stages;
* W: the producer's consumed precursor;
* R: its removed units;
* C_P: turnover's cleared precursor;
* PA: the population's permeability-area product, P a A, from the view's current abundance;
* V: the membrane voltage.

Usage: chain_comparison.py OUT_JSON [--interface DIR] [--world NAME ...] [--end S]
(--end runs a world's first S seconds and compares the rows up to it: a smoke check.)
Development, not judged.
"""

import argparse
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

from cells.definitions.specs import parse_spec
from cells.execution.windows import WindowPolicy, iter_windows
from cells.registry.models import get_model
from validation.fr7 import chain_mapper as cm

POLICY = WindowPolicy(window_steps=10000, recording="observations")  # Bounded memory.
OBSERVED = ("coupling_factor", "membrane_voltage_V")
QUANTITIES = (
    "n_T_fmol",
    "F_T",
    "n_P_fmol",
    "N_units",
    "W_fmol",
    "R_units",
    "C_P_fmol",
    "total_fmol",
    "M1_units",
    "M2_units",
    "M3_units",
    "PA_m3_s",
    "V_V",
    "Na_fmol",
    "K_fmol",
    "Cl_fmol",
)


def collect(spec):
    """A windowed run of `spec` (every row checked), keeping only its observed rows: (the state
    at each observed step, {field: [value at each observation]} of OBSERVED)."""
    dt = spec.execution.dt
    wanted = {int(round(float(t) / dt)) for t in spec.experiment.observation_times}
    states, observed = {}, {name: [] for name in (*OBSERVED, "times")}
    for window in iter_windows(spec, POLICY):
        for i, _ in enumerate(np.asarray(window.times)):
            k = window.start_step + i
            if k in wanted:
                states[k] = type(window.history)(*(np.asarray(v)[i] for v in window.history))
        obs = window.observations
        for name in observed:
            observed[name].extend(np.asarray(getattr(obs, name)))
    return states, observed


def engine_rows(spec, collected, inp, name):
    """{quantity: [value at each observed row]} from a windowed run of world `name`."""
    w = inp["worlds"][name]
    model = get_model(spec.model)
    _, p = model.initial_values(spec)
    species = list(spec.model.species_ids)
    dt = spec.execution.dt
    states, observed = collected
    times = [float(t) for t in spec.experiment.observation_times]
    index = [int(round(t / dt)) for t in times]
    if [float(t) for t in observed["times"]] != times or sorted(states) != index:
        raise ValueError(f"{name}: the windowed run did not return every observed row")
    rows = [states[k] for k in index]
    h = type(rows[0])(*(np.stack(v) for v in zip(*rows, strict=True)))
    index = list(range(len(times)))  # Positions in the stacked rows.
    reference = np.asarray(p.amount_reference)
    increment = np.asarray(h.amount_increment)

    def amount(sid):
        r = species.index(sid)
        return [float(reference[r, 0] + increment[k, r, 0]) for k in index]

    cell, pop = inp["cell"], inp["cell"]["population"]
    area, rho = cell["patch_area_m2"], pop["reference_density_per_m2"]
    channel = spec.model.channels[0]
    declared = channel.abundance * area * rho
    units = [declared + float(np.asarray(h.population_abundance_increment)[k, 0]) for k in index]
    pools = np.asarray(h.unit_pool_units)
    m = w["units"]["stages"]
    out = {
        "n_T_fmol": amount(cm.TEMPLATE),
        "n_P_fmol": amount(cm.PRECURSOR),
        "Na_fmol": amount("Na"),
        "K_fmol": amount("K"),
        "Cl_fmol": amount("Cl"),
        "N_units": units,
        "W_fmol": [float(np.asarray(h.unit_consumed_fmol)[k, 0]) for k in index],
        "R_units": [float(np.asarray(h.unit_removed_units)[k, 0]) for k in index],
    }
    for j in range(3):
        out[f"M{j + 1}_units"] = [float(pools[k, 0, j]) if j < m else 0.0 for k in index]
    row = species.index(cm.PRECURSOR)
    cleared = np.asarray(h.turnover_cleared_fmol)
    out["C_P_fmol"] = [float(cleared[k, row, 0]) for k in index]
    c_u = w["units"]["units_per_fmol"]
    supply = w["precursor"]["supply_fmol_per_s"]
    out["total_fmol"] = [
        math.fsum((n_p, (sum(out[f"M{j + 1}_units"][i] for j in range(3)) + n + r) / c_u, c_p))
        - supply * t
        for i, (t, n_p, n, r, c_p) in enumerate(
            zip(times, out["n_P_fmol"], units, out["R_units"], out["C_P_fmol"], strict=True)
        )
    ]
    out["F_T"] = [float(np.asarray(v)[0]) for v in observed["coupling_factor"]]
    out["V_V"] = [float(np.asarray(v)[0]) for v in observed["membrane_voltage_V"]]
    state_type = type(h)
    pa = []
    for k in index:
        state = state_type(*(np.asarray(v)[k] for v in h))
        view = model.view(p, state, xp=np)
        pa.append(float(np.asarray(view.channel_abundance)[0]) * area * pop["permeability_m_s"])
    out["PA_m3_s"] = pa
    return times, out


def judge(reference, times, engine):
    """Per quantity: the compared rows, the failures and the worst |engine - value| / band."""
    out = {}
    registered = reference["rows_s"]
    for q in QUANTITIES:
        rq = reference["quantities"].get(q)
        if rq is None or rq["cls"] != "compared":
            continue
        rows = []
        for i, t in enumerate(times):
            if t not in registered:
                continue
            j = registered.index(t)
            if rq["status"][j] != "compared":
                continue
            margin = abs(engine[q][i] - rq["value"][j]) / rq["band"][j]
            rows.append((t, margin))
        failures = [(t, m) for t, m in rows if m > 1.0]
        worst = max(rows, key=lambda r: r[1], default=(None, 0.0))
        out[q] = dict(
            compared=len(rows),
            failed=len(failures),
            worst_margin=worst[1],
            worst_row_s=worst[0],
            failures=failures[:5],
        )
    return out


def clearance_row(inp, name, times, engine, reference):
    """The engine's clearance row by the references' registered functions, or pending."""
    try:
        from validation.fr7.references import clearance  # noqa: PLC0415 (lands with them)
    except ImportError:
        return dict(status="pending: the references are not on this tree's path yet")
    w = inp["worlds"][name]
    f = w["factor"]
    volume = inp["cell"]["volume_pL"]
    drive = clearance.hill_drive(np.asarray(engine["n_T_fmol"]) / volume, f["K_mM"], f["n"])
    got = clearance.t_clear(times, drive, inp["clearance"]["epsilon"])
    want = reference["clearance"]["t_clear_s"]
    return dict(status="equal" if got == want else "differs", engine=got, registered=want)


def power_context(zero_power, name):
    z = zero_power["worlds"][name] if "worlds" in zero_power else zero_power[name]
    return dict(core_rows_without_any_plant=z.get("core_rows_without_any_plant"))


def compare_world(inp, refs, name, *, end=None):
    raw = cm.definition(inp, name, end=end)
    spec = parse_spec(raw)
    started = time.perf_counter()
    collected = collect(spec)
    wall = time.perf_counter() - started
    times, engine = engine_rows(spec, collected, inp, name)
    reference = refs["rows"]["worlds"][name]
    verdict = judge(reference, times, engine)
    out = dict(
        world=name,
        end_s=times[-1],
        steps=int(round(times[-1] / spec.execution.dt)),
        wall_s=wall,
        quantities=verdict,
        passed=all(v["failed"] == 0 for v in verdict.values()),
        clearance=clearance_row(inp, name, times, engine, reference)
        if end is None
        else dict(status="not judged: a partial run"),
        power=power_context(refs["zero_power"], name),
        engine_rows=dict(times=times, **engine),
    )
    return out


def load(interface):
    interface = Path(interface)
    return dict(
        inputs=cm.inputs(interface / "inputs.json"),
        rows=json.loads((interface / "rows.json").read_text()),
        zero_power=json.loads((interface / "zero_power.json").read_text()),
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("out")
    parser.add_argument("--interface", default=str(cm.INTERFACE))
    parser.add_argument("--world", nargs="*")
    parser.add_argument("--end", type=float)
    args = parser.parse_args(argv)
    refs = load(args.interface)
    inp = refs["inputs"]
    names = args.world or list(inp["worlds"])
    report = dict(interface=args.interface, worlds={})
    for name in names:
        report["worlds"][name] = compare_world(inp, refs, name, end=args.end)
        r = report["worlds"][name]
        print(
            name,
            "passed" if r["passed"] else "FAILED",
            f"{r['wall_s']:.0f} s",
            {q: (v["failed"], round(v["worst_margin"], 4)) for q, v in r["quantities"].items()},
            r["clearance"]["status"],
            flush=True,
        )
        Path(args.out).write_text(json.dumps(report, indent=1, default=float))
    return 0 if all(r["passed"] for r in report["worlds"].values()) else 1


if __name__ == "__main__":
    sys.exit(main())
