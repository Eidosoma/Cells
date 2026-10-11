"""Independent scalar finite-bath equations; adaptive float64 DOP853/Radau solves."""

import importlib
import sys
import time

import pilot_context as ctx
from pilot_math import Ledger

sys.path.insert(0, str(ctx.HERE.parent / "pump_coupled"))
equations = importlib.import_module("coupled_reference")
c = ctx.c


def integrate(case, setting, plan):
    import numpy as np
    from scipy.integrate import solve_ivp

    start = time.monotonic()
    calls = 0

    def rhs(_time, state):
        nonlocal calls
        calls += 1
        c.require(calls <= plan["reference"]["max_rhs_calls_per_solve"], "Reference RHS budget")
        return equations.rhs(case, state, (1.0, 1.0))

    duration = plan["duration_s"]
    h = plan["reference"]["sample_dt_s"]
    times = np.asarray([i * h for i in range(round(duration / h))] + [duration], dtype=np.float64)
    result = solve_ivp(
        rhs,
        (0.0, duration),
        np.zeros(equations.size(case)),
        method=setting["method"],
        rtol=setting["rtol"],
        atol=setting["atol"],
        max_step=setting["max_step_s"],
        dense_output=True,
    )
    c.require(
        result.success and result.status == 0 and result.t[-1] == duration,
        "Reference solver failed",
    )
    c.require(
        len(result.t) - 1 <= plan["reference"]["max_accepted_steps_per_solve"],
        "Reference step budget",
    )
    states = result.sol(times).T
    c.require(np.isfinite(states).all(), "Nonfinite reference")
    accounting = [equations.accounting(case, state) for state in result.y.T]
    c.require(
        all(
            v["material_residual_fmol"] <= 2e-11
            and v["charge_residual_C"] <= 1e-20
            and v["energy_residual_pJ"] <= 2e-8
            for v in accounting
        ),
        "Reference accounting",
    )
    return dict(
        setting=setting,
        times_s=times.tolist(),
        states=states.tolist(),
        voltage_V=[equations.read_state(case, y)[2] for y in states],
        accepted_times_s=result.t.tolist(),
        accepted_states=result.y.T.tolist(),
        accounting=accounting,
        stats=dict(
            rhs_calls=calls,
            nfev=result.nfev,
            njev=result.njev,
            nlu=result.nlu,
            elapsed_seconds=time.monotonic() - start,
        ),
    )


def gate(plan, records):
    ledger = Ledger()
    for variant in plan["variants"]:
        primary = records[variant + "/" + plan["reference"]["primary"]]
        for setting in plan["reference"]["solves"]:
            row = records[variant + "/" + setting["id"]]
            c.require(row["times_s"] == primary["times_s"], "Reference sample grid")
            ledger.compare(
                "reference_amount_fmol",
                [s[:52] for s in row["states"]],
                [s[:52] for s in primary["states"]],
                plan["reference"]["agreement_amount_fmol"],
            )
            ledger.compare(
                "reference_energy_pJ",
                [s[52:] for s in row["states"]],
                [s[52:] for s in primary["states"]],
                plan["reference"]["agreement_energy_pJ"],
            )
            ledger.compare(
                "reference_voltage_V",
                row["voltage_V"],
                primary["voltage_V"],
                plan["reference"]["agreement_voltage_V"],
            )
    return dict(
        status="independent_reference_gate_pass",
        comparisons=ledger.comparisons,
        maxima=ledger.maxima,
    )


def worker(r, output):
    records = {}
    for case in r["cases"].values():
        for setting in r["protocol"]["reference"]["solves"]:
            record = integrate(case, setting, r["protocol"])
            directory = output / "reference" / case["id"] / setting["id"]
            directory.mkdir(parents=True, exist_ok=False)
            c.write(directory / "result.json", record)
            records[case["id"] + "/" + setting["id"]] = record
    c.require(
        not any(n.split(".")[0] in ("cells", "betse", "jax", "jaxlib") for n in sys.modules),
        "Reference imported a simulator",
    )
    result = gate(r["protocol"], records)
    return dict(
        engine="independent_scalar_equations_scipy_adaptive",
        precision="float64",
        records=records,
        gate=result,
        reference_solves=len(records),
    )
