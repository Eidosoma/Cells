"""A5'': the reference, its floor, the planted controls and an honest second-order stand-in.

**The reference** is R-cell (``validation.coupling.cells_reference.simulate``, Radau at rtol 1e-10,
its defaults) on the registered world. The regulatory state is integrated together with the ions,
as R-feedback does, and R-state's turnover gives X(t) in closed form. Its floor is
``cells_reference.floor``: the run against rtol 1e-12 with atol / 1000.

**The controls** each change one thing the operator must get right, and are integrated by the
same reference:
- ``s0_swapped``: the two cells' priors exchanged;
- ``s0_shared_a``, ``s0_shared_b`` and ``s0_shared_mean``: one prior for both cells;
- ``s0_ignored``: both states started at 0;
- ``state_bypassed``: A5's instantaneous form, F = b + (1 - b) X^n/(K^n + X^n), with no state;
- ``k_on_1pct``, ``k_off_1pct``, and ``basal_1e-3``, the basal level scaled by 1 + 1e-3.

**The stand-in** steps R-cell's own right-hand side with the explicit half of ARS(2,2,2), a
second-order method, at each dt of the ladder (every segment start lies on the grid). Its
distance from the reference shows where an honest second-order engine lies.
"""

from __future__ import annotations

import math

import numpy as np

from validation.coupling import cells_reference as rc

from . import worlds

GAMMA = 1.0 - 1.0 / math.sqrt(2.0)
DELTA = 1.0 - 1.0 / (2.0 * GAMMA)


def observables(run, record) -> dict:
    """V [T, cell], amounts [T, cell, species], s [T, cell] and a_eff [T, cell] from a run."""
    cells = list(run.at[record[0]]["V"])
    V = np.array([[run.at[t]["V"][c] for c in cells] for t in record])
    n = np.array([[run.at[t]["amounts_fmol"][c] for c in cells] for t in record])
    s = np.array([[run.at[t]["s"][("s1", c)] for c in cells] for t in record])
    a = np.array([[run.at[t]["elements"][f"kleak_{c}"]["a_eff"] for c in cells] for t in record])
    return {"cells": cells, "V_V": V, "amounts_fmol": n, "s": s, "a_eff": a}


def reference(block: dict, constants=None, **overrides) -> dict:
    w = worlds.to_world(block, constants, **overrides)
    rec = tuple(block["record_times_s"])
    run = rc.simulate(w, block["end_s"], record=rec)
    out = observables(run, rec)
    out["times_s"] = np.array(rec)
    out["V0_V"] = {c: run.initial[c]["V"] for c in run.initial}
    out["background_fmol"] = {c: run.initial[c]["background_fmol"] for c in run.initial}
    return out


def floor(block: dict, constants=None) -> dict:
    w = worlds.to_world(block, constants)
    rec = tuple(block["record_times_s"])
    _, _, f = rc.floor(w, block["end_s"], rec)
    return f


def _dev(a: dict, b: dict) -> dict:
    return {"V_V": float(np.max(np.abs(a["V_V"] - b["V_V"]))),
            "amounts_fmol": float(np.max(np.abs(a["amounts_fmol"] - b["amounts_fmol"]))),
            "s": float(np.max(np.abs(a["s"] - b["s"])))}


def controls(block: dict, constants=None, ref=None) -> dict:
    ref = reference(block, constants) if ref is None else ref
    s0 = {c: cb["state_s1_initial"] for c, cb in block["cells"].items()}
    a, b = s0["a"], s0["b"]
    st = block["state_s1"]
    inp = st["input"]
    plan = {
        "s0_swapped": dict(s0_override={"a": b, "b": a}),
        "s0_shared_a": dict(s0_override={"a": a, "b": a}),
        "s0_shared_b": dict(s0_override={"a": b, "b": b}),
        "s0_shared_mean": dict(s0_override={"a": (a + b) / 2, "b": (a + b) / 2}),
        "s0_ignored": dict(s0_override={"a": 0.0, "b": 0.0}),
        "k_on_1pct": dict(state_override={"k_on_per_s": st["k_on_per_s"] * 1.01}),
        "k_off_1pct": dict(state_override={"k_off_per_s": st["k_off_per_s"] * 1.01}),
        "state_bypassed": dict(couplings_override={
            cp["id"]: rc.Coupling(f"kleak_{cp['target'].split()[-1]}", inp["law"], inp["source"],
                                  basal=cp["basal"], K_mM=inp["K_mM"], n=inp["n"])
            for cp in block["couplings"]}),
        "basal_1e-3": dict(couplings_override={
            cp["id"]: rc.Coupling(f"kleak_{cp['target'].split()[-1]}", cp["law"], cp["source"],
                                  basal=cp["basal"] * (1 + 1e-3))
            for cp in block["couplings"]}),
    }
    return {name: _dev(reference(block, constants, **kw), ref) for name, kw in plan.items()}


def stand_in(block: dict, dt: float, constants=None) -> dict:
    """The explicit half of ARS(2,2,2) on R-cell's right-hand side, at fixed dt."""
    w = worlds.to_world(block, constants)
    rec = np.asarray(block["record_times_s"], dtype=np.float64)
    model = rc._Model(w, dict(rc.ATOL))
    points = rc.breakpoints(w, block["end_s"], tuple(rec))
    y, _ = model.start((points[0], points[1]))
    steps = np.rint(rec / dt).astype(int)
    if np.any(np.abs(steps * dt - rec) > 1e-9 * dt):
        raise ValueError("record times must lie on the dt grid")
    seg_starts = [p for p in points]
    out_V, out_n, out_s = [], [], []
    k = 0

    def f(t, y, ctl):
        return model.rhs(t, y, *ctl)
    for target in steps:
        while k < target:
            t = k * dt
            j = max(i for i, p in enumerate(seg_starts[:-1]) if p <= t + 1e-12)
            ctl = model.controls(seg_starts[j], seg_starts[j + 1])
            k1 = f(t, y, ctl)
            y2 = y + GAMMA * dt * k1
            k2 = f(t + GAMMA * dt, y2, ctl)
            y = y + dt * (DELTA * k1 + (1 - DELTA) * k2)
            k += 1
        ctl = model.controls(seg_starts[0], seg_starts[1])
        ev = model.evaluate(k * dt, y, *ctl)
        out_V.append(list(ev["phi"]))
        out_n.append([list(x) for x in ev["amounts"]])
        out_s.append([ev["s"][("s1", c)] for c in model.cells])
    return {"V_V": np.array(out_V), "amounts_fmol": np.array(out_n), "s": np.array(out_s)}
