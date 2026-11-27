"""FR-45's dress rehearsal (the build plan's question 17; the lead's ruling of 27 November 2026): a builder-side NumPy
and SciPy reference for invented worlds, written in the references' format (the format note,
validation/fr45/spec/rulings/REFERENCE-FORMAT-NOTE-2026-11-27.txt), so that the engine's runs of the same worlds
(driver, exporter) drive the judge's whole scoring path end to end. It is never in the judged run: the judged run
reads the references' own files and their own G. Nothing here reads them but their invented format sample, under
`--invented-reference` below.

The worlds are the format sample's invented worlds with the engine's constants, re-timed so that each relaxes
within its horizon (the wash worlds again after the wash, at the post-wash rate) at a step with dt max L about 0.06,
in at most 6000 steps (W3 does not relax in that, so it keeps no C2a); W1eq and W7 start at the root of their own
totals; W1p takes its first six times, and W3p is W3's inputs at W3's first five times, reading W3's file. The reference: the binding network's ODE (DOP853 at rtol 1e-12 and 1e-13, the gap between
them the convergence record), the wash's map at its time, the equilibrium's root, and SPEC §1.3's free energy G as
a stand-in (`stand_in_G`, ruling 6: in self-tests and this rehearsal only). Its pairs follow CRITERIA's tests; the
plants' entries follow its table, each judged over its run.

`--invented-reference` instead judges the references' own invented file (`format_sample_INVENTED.json`,
which ruling 5a lets the builder read), its world run at each of its dt; no other file of the references is read.

Usage (PYTHONPATH at a snapshot, JAX_ENABLE_X64=1, JAX_PLATFORMS=cpu):
  python -B -m validation.fr45.rehearsal SAMPLE_DIR OUT --cpus 6,7
"""

import argparse
import copy
import json
import math
import sys
from pathlib import Path

import numpy as np

EPS = 2.0**-52
TARGET_DTL = 0.06  # dt max L at the start (h max L 0.03).
RELAX = 30.0  # The horizon in the slowest time constants.
STEP_CAP = 6000  # At most the registered worlds' steps.
N_A, K_B = 6.02214076e23, 1.380649e-23


class Model:
    """The invented world's binding network, as SPEC §1 states it, from an object of the `inputs` shape."""

    def __init__(self, inputs):
        self.inputs = inputs
        constants = inputs["constants"]
        self.RT, self.NF = constants["RT_pJ_per_fmol"], constants["sites_per_fmol"]
        self.V = {n["id"]: n["volume_pL"] for n in inputs["nodes"]}
        self.sets = [s["id"] for s in inputs["sets"]]
        self.faces = {s["id"]: s["faces"] for s in inputs["sets"]}
        self.S = {s["id"]: s["accessible_fraction"] * s["sites_per_copy"] * s["copies"] / self.NF
                  for s in inputs["sets"]}  # fmt: skip
        self.pops = inputs["populations"]
        self.pools = sorted({(p["ligand"], self.faces[p["set"]]) for p in self.pops})
        self.pool_of = np.array(
            [self.pools.index((p["ligand"], self.faces[p["set"]])) for p in self.pops]
        )
        self.set_of = np.array([self.sets.index(p["set"]) for p in self.pops])
        self.kon = np.array([p["k_on"] for p in self.pops])
        self.koff = np.array([p["k_off"] for p in self.pops])
        self.vol = np.array([self.V[node] for _, node in self.pools])
        self.np_, self.nb, self.ns = len(self.pools), len(self.pops), len(self.sets)

    def observables(self):
        return ([f"n:{lig}@{node}" for lig, node in self.pools] + [f"B:{p['id']}" for p in self.pops]
                + [f"R:{s}" for s in self.sets])  # fmt: skip

    def start(self):
        n0 = {(a["ligand"], a["node"]): a["n_fmol"] for a in self.inputs["free_amounts"]}
        B0 = np.array([p["initial_occupancy"] * self.S[p["set"]] for p in self.pops])
        R0 = np.array(
            [self.S[s] - math.fsum(B0[self.set_of == k]) for k, s in enumerate(self.sets)]
        )
        return np.concatenate([[n0[pool] for pool in self.pools], B0, R0])

    def split(self, y):
        return y[: self.np_], y[self.np_ : self.np_ + self.nb], y[self.np_ + self.nb :]

    def rhs(self, _t, y):
        n, B, R = self.split(y)
        J = self.kon * (n[self.pool_of] / self.vol[self.pool_of]) * R[self.set_of] - self.koff * B
        dn = -np.bincount(self.pool_of, J, self.np_)
        dR = -np.bincount(self.set_of, J, self.ns)
        return np.concatenate([dn, J, dR])

    def loads(self, y):
        """The stage condition's unidirectional loads at a state (SPEC §1.2): pools, sets summed, populations."""
        n, B, R = self.split(y)
        c = n[self.pool_of] / self.vol[self.pool_of]
        load_n = np.bincount(self.pool_of, self.kon * R[self.set_of], self.np_) / self.vol
        load_r = np.bincount(self.set_of, self.kon * c, self.ns)
        return load_n, load_r, self.koff.copy()

    def wash(self, y):
        """The wash's map (SPEC's §2): every ligand at the washed node to (1 - f) n + f V c_buf; B and R kept."""
        w = self.inputs["wash"]
        y = y.copy()
        removed, supplied = {}, {}
        for k, (lig, node) in enumerate(self.pools):
            if node != w["node"]:
                continue
            f, add = w["fraction"], w["fraction"] * self.V[node] * w["buffer_mM"][lig]
            removed[lig], supplied[lig] = f * y[k], add
            y[k] = (1.0 - f) * y[k] + add
        return y, removed, supplied

    def solve(self, times, rtol, start=None):
        """{time: state} at `times` (and the wash's before and after), integrating across the wash."""
        from scipy.integrate import solve_ivp

        y = self.start() if start is None else start
        out, t0 = {0.0: y.copy()}, 0.0
        w = self.inputs.get("wash")
        stops = sorted({*times, *([w["time_s"]] if w else [])})
        for t in stops:
            if t > t0:
                sol = solve_ivp(
                    self.rhs, (t0, t), y, method="DOP853", rtol=rtol, atol=1e-30 + 1e-16 * np.abs(y)
                )
                y, t0 = sol.y[:, -1], t
            out[t] = y.copy()
            if w and t == w["time_s"]:
                out["before_wash"] = y.copy()
                y, _, _ = self.wash(y)
                out["after_wash"] = y.copy()
        return out

    def equilibrium(self, y):
        """The root of the closed network at the totals of y (R-eq), refined by Newton in binary64."""
        from scipy.optimize import root

        n, B, R = self.split(y)
        totals = n + np.bincount(self.pool_of, B, self.np_)
        S = np.array([self.S[s] for s in self.sets])

        def F(x):
            nn, BB, RR = self.split(x)
            bind = (
                self.kon * (nn[self.pool_of] / self.vol[self.pool_of]) * RR[self.set_of]
                - self.koff * BB
            )
            sites = RR + np.bincount(self.set_of, BB, self.ns) - S
            pools = nn + np.bincount(self.pool_of, BB, self.np_) - totals
            return np.concatenate([bind / self.koff, pools, sites])

        sol = root(F, y, method="hybr", tol=1e-15)
        return sol.x

    def G(self, node, y):
        """SPEC §1.3's free energy of one node's pools and the sets facing it (pJ)."""
        n, B, R = self.split(y)
        amounts = {**{f"n:{lig}@{nd}": n[k] for k, (lig, nd) in enumerate(self.pools)},
                   **{f"B:{p['id']}": B[k] for k, p in enumerate(self.pops)},
                   **{f"R:{s}": R[k] for k, s in enumerate(self.sets)}}  # fmt: skip
        return stand_in_G(echo(self.inputs, self), node, amounts)


def _xlnx(x, s):
    return 0.0 if x == 0 else x * math.log(x / s)


def stand_in_G(world, node, amounts):
    """A stand-in for the references' G (ruling 6; self-tests and the rehearsal only): SPEC §1.3's free energy at
    one node, RT n (ln(n/V) - 1) of each pool there, B (RT ln K_b) + RT B ln(B/S_s) of each population facing it,
    and RT R ln(R/S_s) of each set facing it."""
    RT = world["constants"]["RT_pJ_per_fmol"]
    V = {x["id"]: x["V"] for x in world["nodes"]}
    S = {s["id"]: s["S"] for s in world["sets"]}
    faces = {s["id"]: s["faces"] for s in world["sets"]}
    pops = {p["id"]: p for p in world["populations"]}
    total = 0.0
    for key, x in amounts.items():
        kind, name = key.split(":", 1)
        if kind == "n":
            lig, where = name.split("@")
            if where == node and x > 0:
                total += RT * x * (math.log(x / V[where]) - 1.0)
        elif kind == "B" and faces[pops[name]["set"]] == node:
            p = pops[name]
            total += x * RT * math.log(p["k_off"] / p["k_on"]) + RT * _xlnx(x, S[p["set"]])
        elif kind == "R" and faces[name] == node:
            total += RT * _xlnx(x, S[name])
    return total


def echo(inputs, model):
    """The references' world echo (the format note): the inputs as the references hold them."""
    return dict(
        id=inputs["world"],
        constants=dict(
            N_f_sites_per_fmol=inputs["constants"]["sites_per_fmol"],
            N_A_per_mol=N_A,
            k_B_J_per_K=K_B,
            T_K=inputs["constants"]["temperature_K"],
            RT_pJ_per_fmol=inputs["constants"]["RT_pJ_per_fmol"],
        ),
        nodes=[dict(id=n["id"], kind=n["kind"], V=n["volume_pL"]) for n in inputs["nodes"]],
        patches=[dict(p) for p in inputs["patches"]],
        ligands=list(inputs["ligands"]),
        free_amounts=[
            dict(ligand=a["ligand"], node=a["node"], n=a["n_fmol"], declared=a["declared"])
            for a in inputs["free_amounts"]
        ],  # fmt: skip
        sets=[
            dict(
                id=s["id"],
                owner=s["owner"],
                faces=s["faces"],
                copies=s["copies"],
                sites_per_copy=s["sites_per_copy"],
                accessible_fraction=s["accessible_fraction"],
                S=model.S[s["id"]],
            )
            for s in inputs["sets"]
        ],  # fmt: skip
        populations=[dict(p, faces=model.faces[p["set"]]) for p in inputs["populations"]],
        start=[
            dict(observable=o, value=float(v))
            for o, v in zip(model.observables(), model.start(), strict=True)
        ],
        dt=inputs["dt_s"],
        observation_times=list(inputs["observation_times_s"]),
        horizon=inputs["horizon_s"],
        wash=None
        if not inputs.get("wash")
        else dict(
            t=inputs["wash"]["time_s"],
            node=inputs["wash"]["node"],
            f=inputs["wash"]["fraction"],
            buffer=dict(inputs["wash"]["buffer_mM"]),
        ),  # fmt: skip
    )


# ------------------------------------------------------------------ the rehearsal's worlds


def _grid(t, dt):
    return round(t / dt) * dt


def _slowest_rate(model, y):
    """The slowest relaxation rate at the root: the smallest |Re| of the Jacobian's nonzero eigenvalues."""
    eq = model.equilibrium(y)
    step = 1e-9 * np.maximum(np.abs(eq), 1e-30)
    J = np.column_stack([(model.rhs(0, eq + step[k] * np.eye(len(eq))[k]) - model.rhs(0, eq)) / step[k]
                         for k in range(len(eq))])  # fmt: skip
    rates = np.abs(np.linalg.eigvals(J).real)
    rates = rates[rates > 1e-9 * rates.max()]
    return float(rates.min())


def _at_root(inputs, model):
    """The inputs started at the root of their own totals, rounded once (W1eq's and W7's start)."""
    eq = model.equilibrium(model.start())
    n, B, _ = model.split(eq)
    out = copy.deepcopy(inputs)
    pools = {pool: float(n[k]) for k, pool in enumerate(model.pools)}
    for a in out["free_amounts"]:
        if (a["ligand"], a["node"]) in pools:
            a["n_fmol"] = pools[(a["ligand"], a["node"])]
    for k, p in enumerate(out["populations"]):
        p["initial_occupancy"] = float(B[k] / model.S[p["set"]])
    return out


def _constants(inputs):
    """The engine's own constants (SPEC §0): N_f = N_A 1e-15 and RT = N_A k_B T 1e-3 pJ per fmol; the format
    sample's invented N_f is not the engine's."""
    c = inputs["constants"]
    c["sites_per_fmol"] = 602214076.0
    c["RT_pJ_per_fmol"] = N_A * K_B * c["temperature_K"] * 1e-3


def design(sample_runs):
    """({world: inputs}, {world: notes}) of the rehearsal: the sample's invented worlds with the engine's constants,
    re-timed (module docstring). W1p's times are its first six; W3p is W3's inputs at W3's first five times, as
    the registration has them (SPEC:182). A world that does not relax within STEP_CAP steps keeps no C2a pair."""
    out, notes = {}, {}
    base = {r["world"].removeprefix("INVENTED-"): r["inputs"] for r in sample_runs.values()
            if r["inputs"] is not None and r["plant"] is None}  # fmt: skip
    for world, inputs in sorted(base.items()):
        if world == "W3p":
            continue
        inputs = copy.deepcopy(inputs)
        _constants(inputs)
        if world == "W5":  # As the sample has it: refused at its first step by the stage condition.
            out[world], notes[world] = inputs, dict(relaxed=False)
            continue
        if world in ("W1eq", "W7"):
            inputs = _at_root(inputs, Model(inputs))
        model = Model(inputs)
        y0 = model.start()
        lmax = max(float(np.max(x)) for x in model.loads(y0))
        if inputs.get("wash"):
            after, _, _ = model.wash(model.equilibrium(y0))
            lmax = max(lmax, *(float(np.max(x)) for x in model.loads(after)))
        dt = 2.0 ** math.floor(math.log2(TARGET_DTL / lmax))
        rate = _slowest_rate(model, y0)
        relaxed = True
        if world == "W4":  # Three steps, the coarsest at dt max L about 0.2, over four short times.
            dt = 2.0 ** math.floor(math.log2(0.2 / lmax))
            times = [_grid(k * 5 * dt, dt) for k in (1, 2, 3, 4)]
            horizon, relaxed = times[-1], False
        elif inputs.get(
            "wash"
        ):  # Relaxed before the wash, and again after it at the post-wash rate.
            t_w = _grid(RELAX / rate, dt)
            washed, _, _ = model.wash(model.equilibrium(y0))
            horizon = _grid(t_w + RELAX / _slowest_rate(model, washed), dt)
            times = sorted({_grid(t_w / 2, dt), t_w, _grid(t_w + dt, dt), _grid(t_w + (horizon - t_w) / 2, dt),
                            horizon})  # fmt: skip
            inputs["wash"]["time_s"] = t_w
        else:
            horizon = _grid(RELAX / rate, dt)
            if horizon / dt > STEP_CAP:
                horizon, relaxed = STEP_CAP * dt, False
            times = sorted({_grid(horizon * 2.0**-j, dt) for j in range(7, -1, -1)} - {0.0})
            if world == "W1p":
                times = times[:6]
                horizon = times[-1]
        inputs["dt_s"], inputs["observation_times_s"], inputs["horizon_s"] = dt, times, horizon
        out[world], notes[world] = inputs, dict(relaxed=relaxed, steps=round(horizon / dt))
    w3p = copy.deepcopy(out["W3"])
    w3p["world"] = "INVENTED-W3p"
    w3p["observation_times_s"] = out["W3"]["observation_times_s"][:5]
    w3p["horizon_s"] = w3p["observation_times_s"][-1]
    out["W3p"], notes["W3p"] = (
        w3p,
        dict(relaxed=False, steps=round(w3p["horizon_s"] / w3p["dt_s"]), of="W3"),
    )
    return out, notes


def registration(worlds):
    """The rehearsal's registration, in the judge's shape (judge.Registration): the runs and their dt (TABLE §3),
    each world's saved steps (§5.1), the wash's step, the event map's steps (§6), the facing nodes (§5.2), the
    operators (§9), and which reference file each world reads (W3p reads W3's)."""
    runs, rows, wash, maps = {}, {}, {}, {}
    for world, inputs in worlds.items():
        dts = [inputs["dt_s"] / d for d in W4_DIVISORS] if world == "W4" else [inputs["dt_s"]]
        for dt in dts:
            runs[f"{world}-dt{dt!r}" if world == "W4" else world] = dict(
                world=world, plant=None, dt_s=dt
            )
        times = [0.0, *inputs["observation_times_s"]] + (
            [inputs["horizon_s"]] if world == "W5" else []
        )
        rows[world] = {repr(dt): [[t, round(t / dt)] for t in times] for dt in dts}
        if inputs.get("wash"):
            wash[world] = dict(time_s=inputs["wash"]["time_s"])
            maps[world] = (
                [inputs["wash"]["time_s"]] if world == "W2" else [0.0, inputs["wash"]["time_s"]]
            )
    for world, plant, _ in PLANTS:
        runs[f"{world}-{plant}"] = dict(world=world, plant=plant, dt_s=worlds[world]["dt_s"])
    base = ["cells.model.resolved_pump_composite@1", "cells.model.resolved_pump_tissue@3",
            "cells.operator.site_occupancy@1"]  # fmt: skip
    return dict(
        runs=runs, rows=rows, wash=wash, maps=maps,
        files={w: ("W3" if w == "W3p" else w) for w in worlds},
        heat_nodes={w: sorted({s["faces"] for s in i["sets"]}) for w, i in worlds.items()},
        operators={w: base + (["cells.operator.scheduled_compartment_wash@1"] if i.get("wash") else [])
                   for w, i in worlds.items()},
        plants=[[p, c, w, t] for w, i in worlds.items() for ww, p, c, t in PLANT_ENTRIES((i.get("wash") or {}).get(
            "time_s")) if ww == w and (p, c) not in (("P3", "C3a"), ("P6", "C3a"))],
    )  # fmt: skip


PLANTS = [("W1p", "P1", "p1"), ("W1p", "P2", "p2"), ("W1p", "P3", "p3"), ("W1p", "P6", "p6"), ("W1p", "P8", "p8"),
          ("W1p", "P9", "p9"), ("W5", "P4", "p4"), ("W2", "P5", "p5"), ("W7", "P5", "p5"), ("W3p", "P7", "p7")]  # fmt: skip
W4_DIVISORS = (1, 2, 4)


def jobs(worlds, start_file=None):
    """[(run, job)] of the rehearsal's honest and plant runs; W1eq reads its start from its reference file, as the
    registered W1eq does (TABLE §3)."""
    out = []

    def job(name, inputs, plant=None, start=None):
        out.append(
            (name, dict(run=name, inputs=inputs, plant=plant, start=start, time_limit_step=None))
        )

    for world, inputs in worlds.items():
        if world == "W4":
            for d in W4_DIVISORS:
                w4 = copy.deepcopy(inputs)
                w4["dt_s"] = inputs["dt_s"] / d
                job(f"INVENTED-W4-dt{w4['dt_s']!r}", w4)
            continue
        job(
            f"INVENTED-{world}",
            inputs,
            start=str(start_file) if world == "W1eq" and start_file else None,
        )
    for world, plant, module in PLANTS:
        job(f"INVENTED-{world}-{plant}", worlds[world], plant=module)
    return out


# ------------------------------------------------------------------ the rehearsal's reference files

# The registered files' pairs by world (the census): W1p holds C1, C3b, C5, C9 and C10; W3p has no file of its own.
C1_WORLDS = ("W1", "W2", "W3", "W6", "W7", "W7s", "W1p")
C2A_WORLDS = ("W1", "W2", "W3", "W6", "W7", "W7s")
C3_WORLDS = ("W1", "W2", "W3", "W6", "W7", "W7s", "W1p")
C3AC_WORLDS = ("W1", "W2", "W3", "W6", "W7", "W7s")
C9_WORLDS = ("W1", "W3", "W6", "W7", "W7s", "W1p")


def _node_of(model, obs):
    kind, name = obs.split(":", 1)
    if kind == "n":
        return name.split("@")[1]
    if kind == "R":
        return model.faces[name]
    return model.faces[next(p["set"] for p in model.pops if p["id"] == name)]


def _g_terms(model, node, y):
    """The magnitudes of G's terms at a node (CRITERIA's E for a heat)."""
    n, B, R = model.split(y)
    total = 0.0
    for k, (_, where) in enumerate(model.pools):
        if where == node and n[k] > 0:
            total += abs(model.RT * n[k] * (math.log(n[k] / model.V[where]) - 1.0))
    for k, p in enumerate(model.pops):
        if model.faces[p["set"]] == node:
            total += abs(B[k] * model.RT * math.log(p["k_off"] / p["k_on"])) + abs(
                model.RT * _xlnx(B[k], model.S[p["set"]])
            )
    for k, s in enumerate(model.sets):
        if model.faces[s] == node:
            total += abs(model.RT * _xlnx(R[k], model.S[s]))
    return total


def reference(world, inputs, dts=None, relaxed=True):
    """The rehearsal's reference file for one world, in the references' format (the format note); C2a only where
    the world relaxes within its horizon."""
    model = Model(inputs)
    obs_times = list(inputs["observation_times_s"])
    saved = [0.0, *obs_times]
    names = model.observables()
    echo_ = echo(inputs, model)
    if dts:
        echo_["dt"] = list(dts)
    # The registered files' top keys (the census): `wash` in W2 and W7, `closed_form` in W4, `stage` in W5.
    ref = dict(schema="fr45-reference/1", invented=True, world=echo_, units={}, equilibrium=None, trajectory=[],
               balances=dict(ligands=[], sets=[]), heats=dict(intervals=[], G=[]), pairs=[],
               spread="none", spread_note="rehearsal: nothing is drawn", distance_at_horizon=None,
               plants=[], provenance=dict(writer="validation/fr45/rehearsal.py"))  # fmt: skip
    if world == "W4":
        ref["closed_form"] = []
    pairs = ref["pairs"]
    dt = inputs["dt_s"]
    if world == "W5":
        load_n, load_r, load_b = model.loads(model.start())
        h = dt / 2
        ref["stage"] = dict(h_s=h, max_hL_summed=h * max(map(float, [*load_n, *load_r, *load_b])))
        pairs.append(dict(criterion="C7", observable="stage:first_step", time_s=0.0, **{"class": "constant"},
                          value="refused", tolerance=None, against="engine: its step report gives h max L above 1/2"))  # fmt: skip
        ref["plants"] = [
            _plant_entry(p, c, w, t) for w, p, c, t in PLANT_ENTRIES(None) if w == "W5"
        ]
        return ref
    hi, lo = model.solve(saved, 1e-13), model.solve(saved, 1e-12)
    state = {t: hi[t] for t in saved}
    start = model.start()
    s_node = {}
    for o_k, obs in enumerate(names):
        node = _node_of(model, obs)
        s_node[node] = max(s_node.get(node, 0.0), *(abs(float(state[t][o_k])) for t in saved))
    for t in obs_times:
        for o_k, obs in enumerate(names):
            ref["trajectory"].append(dict(observable=obs, time_s=t, value=float(hi[t][o_k]),
                                          tolerance_gap=float(abs(hi[t][o_k] - lo[t][o_k]))))  # fmt: skip
    horizon = inputs["horizon_s"]
    eq = model.equilibrium(state[horizon])
    ref["equilibrium"] = {o: float(v) for o, v in zip(names, eq, strict=True)}
    ref["distance_at_horizon"] = {
        o: float(abs(a - b)) for o, a, b in zip(names, state[horizon], eq, strict=True)
    }

    def pair(criterion, obs, t, cls, value, tol, **extra):
        pairs.append(dict(criterion=criterion, observable=obs, time_s=t, **{"class": cls}, value=value,
                          tolerance=tol, against=extra.pop("against", "reference"), **extra))  # fmt: skip

    if world in C1_WORLDS:
        for t in obs_times:
            for o_k, obs in enumerate(names):
                pair(
                    "C1", obs, t, "band", float(state[t][o_k]), 1e-6 * s_node[_node_of(model, obs)]
                )
    if world in C2A_WORLDS and relaxed:
        for o_k, obs in enumerate(names):
            pair("C2a", obs, horizon, "band", float(eq[o_k]), 1e-9 * s_node[_node_of(model, obs)])
    load_n, load_r, load_b = model.loads(start)
    L = max(map(float, [*load_n, *load_r, *load_b]))
    wash = inputs.get("wash")
    t_w = wash["time_s"] if wash else None
    if world in ("W1eq", "W7"):
        root = model.equilibrium(start)
        for t in [x for x in obs_times if t_w is None or x <= t_w]:
            k = round(t / dt)
            for o_k, obs in enumerate(names):
                tol = (2 + 3 * k * (dt / 2) * L) * 4 * EPS * max(abs(root[o_k]), abs(start[o_k]))
                pair("C2b", obs, t, "derived", float(root[o_k]), tol, dt_s=dt)
    if world in C3_WORLDS:
        nodes = sorted(set(model.faces.values()))
        for a, b in zip(saved, saved[1:], strict=False):
            spans = t_w is not None and a <= t_w < b
            for node in nodes:
                y0 = hi["after_wash"] if spans else state[a]
                E = _g_terms(model, node, y0) + _g_terms(model, node, state[b])
                k = round((b - a) / dt)
                if not spans and world not in C3AC_WORLDS:
                    pair("C3b", f"H:{node}", b, "derived", None, 16 * EPS * k * E, start_s=a, end_s=b, dt_s=dt,
                         against="engine: -dG of its own saved states, G the stand-in")  # fmt: skip
                    continue
                if not spans:
                    heat = model.G(node, state[a]) - model.G(node, state[b])
                    bh = 0.0
                    for o_k, obs in enumerate(names):
                        if _node_of(model, obs) == node:
                            delta, x = 1e-6 * s_node[node], abs(float(state[b][o_k]))
                            x0 = max(abs(float(start[o_k])), delta)
                            bh += model.RT * (abs(math.log(max(x, delta) / x0)) + 1.0) * delta
                    bound = 2 * bh + 16 * EPS * E
                    pair("C3a", f"H:{node}", b, "band", float(heat), bound, start_s=a, end_s=b)
                    pair("C3b", f"H:{node}", b, "derived", None, 16 * EPS * k * E, start_s=a, end_s=b, dt_s=dt,
                         against="engine: -dG of its own saved states, G the stand-in")  # fmt: skip
                pair("C3c", f"cumulative_site_heat:{node}", b, "derived", None, 16 * EPS * E, start_s=a, end_s=b,
                     against="engine: its own cumulative site heat may not fall",
                     **(dict(spans_wash=True) if spans else {}))  # fmt: skip
    if wash:
        node, f = wash["node"], wash["fraction"]
        ligands = [lig for lig, where in model.pools if where == node]
        declared = {(a["ligand"], a["node"]): a["n_fmol"] for a in inputs["free_amounts"]}
        _, removed, supplied = model.wash(hi["before_wash"])
        for t in saved:
            k = round(t / dt)
            for lig in ligands:
                pk = model.pools.index((lig, node))
                bound = [
                    b
                    for b, p in enumerate(model.pops)
                    if p["ligand"] == lig and model.faces[p["set"]] == node
                ]
                y = state[t]
                after = t > t_w
                free, b_sum = float(y[pk]), sum(float(y[model.np_ + b]) for b in bound)
                col = removed[lig] if after else 0.0
                sup = supplied[lig] if after else 0.0
                total = declared[(lig, node)] + sum(float(start[model.np_ + b]) for b in bound)
                pair("C4a", f"books:{lig}@{node}", t, "derived", total, 16 * EPS * (k + 1) * (free + b_sum + col + sup),
                     dt_s=dt)  # fmt: skip
        states = [t_w] if world == "W2" else [0.0, t_w]
        for t in states:
            y = start if t == 0.0 else hi["before_wash"]
            _, rem, sup = model.wash(y)
            for lig in ligands:
                volume = model.V[node]
                fvc = f * volume * wash["buffer_mM"][lig]
                pair("C4b", f"n:{lig}@{node}", t, "derived", None, None, tolerance_terms=dict(
                    eps_factor=4 * EPS, f_V_c_buf=fvc, formula="eps_factor * (|a_n| + |n| + f_V_c_buf)"),
                    tolerance_information="R-ode's state terms: information",
                    against="engine: (1 - f) n + f V c_buf of its own state at the event")  # fmt: skip
                pair("C4b", f"removed:{lig}@{node}", t, "derived", None, None,
                     tolerance_terms=dict(eps_factor=2 * EPS, f=f, formula="eps_factor * f * |n|"),
                     tolerance_information="R-ode's state terms: information",
                     against="engine: f n of its own state at the event")  # fmt: skip
                pair("C4b", f"supplied:{lig}@{node}", t, "derived", fvc, 2 * EPS * fvc)
            for obs in names:
                if obs.startswith(("R:", "B:")):
                    pair(
                        "C6",
                        obs,
                        t,
                        "constant",
                        "unchanged",
                        None,
                        against="engine: its own value before the map",
                    )
        for lig in ligands:
            ns = s_node[node]
            pair("C4c", f"removed:{lig}@{node}", t_w, "band", float(removed[lig]), f * 1e-6 * ns)
            pair(
                "C4c",
                f"supplied:{lig}@{node}",
                t_w,
                "band",
                float(supplied[lig]),
                2 * EPS * supplied[lig],
            )
        ref["wash"] = {
            lig: dict(removed=float(removed[lig]), supplied=float(supplied[lig])) for lig in ligands
        }
    for t in saved:
        for s in model.sets:
            for d in dts or [dt]:
                kk = round(t / d)
                pair(
                    "C5",
                    f"sites:{s}",
                    t,
                    "derived",
                    model.S[s],
                    16 * EPS * (kk + 1) * model.S[s],
                    dt_s=d,
                )
    if world in C9_WORLDS:
        for t in saved:
            for p in model.pops:
                pair("C9", f"theta:{p['id']}", t, "derived", None, None, tolerance_terms=dict(
                    eps_term=4 * EPS, formula="eps_term + |R_s + sum B - S_s| / S_s"),
                    tolerance_information="R-ode's moiety term: information",
                    against="engine: B_b / S_s of its own saved state")  # fmt: skip
    if world == "W4":
        finest = min(dts)
        for d in dts:
            for t in obs_times:
                for o_k, obs in enumerate(names):
                    if obs.startswith(("R:", "B:")):
                        s = (
                            obs[2:]
                            if obs.startswith("R:")
                            else next(p["set"] for p in model.pops if p["id"] == obs[2:])
                        )
                        scale = model.S[s]
                        pair("C8", obs, t, "band", float(state[t][o_k]), 1e-6 * scale if d == finest else None,
                             dt_s=d, scale=scale)  # fmt: skip
        coarse = sorted(dts, reverse=True)
        for a, b in zip(coarse, coarse[1:], strict=False):
            pair("C8", f"ratio:e({a!r})/e({b!r})", None, "band", None, None, minimum=6.0,
                 against="engine: e(dt) = max |y_e - y_ref| / S over R and the B_b at its times")  # fmt: skip
    for d in dts or [dt]:
        pair("C10", "run", horizon, "constant", "completes", None, dt_s=d,
             against="engine: the run completes and closes its ledgers on every row")  # fmt: skip
    ref["plants"] = [_plant_entry(p, c, w, t) for w, p, c, t in PLANT_ENTRIES(t_w)
                     if (w if w != "W3p" else "W3") == world]  # fmt: skip
    return ref


def _plant_entry(plant, criterion, world, time_s):
    """A plant entry in the registered files' keys (the census); the rehearsal sizes no plant, so its sizes are
    null."""
    return dict(plant=plant, criterion=criterion, world=world, time_s=time_s, compared={}, honest=None, planted=None,
                distance_in_bounds=None)  # fmt: skip


def PLANT_ENTRIES(t_w):  # noqa: N802 - a table, keyed by the wash's time
    """(world, plant, criterion, time_s) of the rehearsal's plant entries, after CRITERIA's table."""
    return [("W1p", "P1", "C1", None), ("W1p", "P2", "C1", None), ("W1p", "P3", "C3a", None),
            ("W1p", "P3", "C3b", None), ("W1p", "P6", "C3a", None), ("W1p", "P6", "C3b", None),
            ("W1p", "P8", "C10", None), ("W1p", "P9", "C9", None),
            ("W2", "P5", "C6", t_w), ("W2", "P5", "C4a", None), ("W7", "P5", "C6", 0.0), ("W7", "P5", "C6", t_w),
            ("W7", "P5", "C4a", None), ("W3p", "P7", "C5", None), ("W3p", "P7", "C1", None),
            ("W5", "P4", "C7", None)]  # fmt: skip


# ------------------------------------------------------------------ the rehearsal end to end


def run_jobs(todo, out, cpus):
    """Each job in its own process through the driver, on one CPU each; returns [(run, exit code)]."""
    import os
    import subprocess
    import time
    from concurrent.futures import ThreadPoolExecutor

    (out / "jobs").mkdir(parents=True, exist_ok=True)
    (out / "logs").mkdir(exist_ok=True)
    free = list(cpus)

    def one(item):
        name, job = item
        cpu = free.pop()
        try:
            path = out / "jobs" / f"{name}.json"
            path.write_text(json.dumps(job, indent=1) + "\n")
            started = time.time()
            done = subprocess.run(["taskset", "-c", str(cpu), sys.executable, "-B", "-m", "validation.fr45.driver",
                                   "run", str(path), str(out / "records" / f"{name}.json")],
                                  capture_output=True, text=True, env=os.environ)  # fmt: skip
            (out / "logs" / f"{name}.log").write_text(done.stdout + done.stderr)
            with (out / "runs.log").open("a") as f:
                f.write(
                    f"{name}: exit {done.returncode}, {time.time() - started:.1f} s, CPU {cpu}\n"
                )
            return name, done.returncode
        finally:
            free.append(cpu)

    with ThreadPoolExecutor(max_workers=len(cpus)) as pool:
        return list(pool.map(one, todo))


def expected_inputs(worlds, todo):
    """The rehearsal's expected-inputs file, in §12.2's shape: each honest run's designed inputs, W1eq's start and
    RT null (compared with the references' file, and recorded); the host volumes and host_values marked as the
    host-entity addendum's, and every ion's permeability 0.0 (§4.1); P2's crossed k_off for its declaration."""
    runs = {}
    for name, job in todo:
        if any(name.endswith(f"-{p}") for _, p, _ in PLANTS):
            continue
        inputs = copy.deepcopy(job["inputs"])
        inputs["constants"]["RT_pJ_per_fmol"] = None
        inputs["host_values"] = MARKERS["host_values"]
        for node in inputs["nodes"]:
            if not node["registered"]:
                node["volume_pL"] = MARKERS["volume"]
        inputs["ion_permeabilities"] = {
            patch: {"each_ion": 0.0} for patch in inputs["ion_permeabilities"]
        }
        if name == "INVENTED-W1eq":
            for p in inputs["populations"]:
                p["initial_occupancy"] = None
            for a in inputs["free_amounts"]:
                if a["declared"]:
                    a["n_fmol"] = None
        runs[name.removeprefix("INVENTED-")] = inputs
    w1p = worlds["W1p"]
    first = next(s["id"] for s in w1p["sets"] if s["shared"])
    a, b = [p for p in w1p["populations"] if p["set"] == first][:2]
    crossed = {
        f"populations[id={a['id']}].k_off": b["k_off"],
        f"populations[id={b['id']}].k_off": a["k_off"],
    }
    return dict(kind="fr45 expected inputs, version 1", protocol="fr45-site-competition-v1", invented=True,
                runs=runs, plant_inputs_changed={"W1p-P2": crossed}, host=dict(markers=dict(MARKERS)))  # fmt: skip


MARKERS = dict(volume="from the host-entity addendum",
               trace="from the host-entity addendum: the binary64 product 1e-12 \u00d7 this compartment's volume_pL "
                     "there", host_values="from the host-entity addendum")  # fmt: skip


def addendum(table):
    """An invented host-entity addendum, as the registered one is made (§4.1, §14.1 item 6): each honest run's host
    volumes and host_values copied by machine from the engine's own parse, here its run's echo."""
    out = {}
    for name, run in table["runs"].items():
        if run["plant"] is None and run["inputs"] is not None:
            out[name.removeprefix("INVENTED-")] = dict(
                nodes=[dict(id=n["id"], volume_pL=n["volume_pL"]) for n in run["inputs"]["nodes"] if not n["registered"]],
                host_values=run["inputs"]["host_values"])  # fmt: skip
    return dict(kind="INVENTED host-entity addendum (the rehearsal's)", runs=out)


def stand_in_module():
    """The source of a stand-in `fr45ref_free_energy` module (ruling 6), so that the judge loads G in the rehearsal
    exactly as it loads the references' at the judged run: by its folder on sys.path."""
    import inspect

    return ('"""INVENTED: the rehearsal\'s stand-in G (ruling 6), never the references\'."""\n\nimport math\n\n\n'
            + inspect.getsource(_xlnx) + "\n\n" + inspect.getsource(stand_in_G) + "\n\nG = stand_in_G\n")  # fmt: skip


def references(worlds, notes, folder):
    """Each world's reference file but W3p's, which reads W3's (TABLE §3), and the stand-in G module."""
    (folder / "outputs").mkdir(parents=True, exist_ok=True)
    (folder / "fr45ref_free_energy.py").write_text(stand_in_module())
    for world, inputs in worlds.items():
        if world == "W3p":
            continue
        dts = [inputs["dt_s"] / d for d in W4_DIVISORS] if world == "W4" else None
        ref = reference(world, inputs, dts, relaxed=notes[world]["relaxed"])
        (folder / "outputs" / f"reference_{world}.json").write_text(
            json.dumps(ref, indent=1) + "\n"
        )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("sample")
    parser.add_argument("out")
    parser.add_argument("--cpus", default="6,7")
    parser.add_argument("--stage", choices=("all", "runs", "judge"), default="all")
    parser.add_argument(
        "--invented-reference", help="judge against the references' own invented file instead"
    )
    args = parser.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    if args.invented_reference:
        return invented_check(args.invented_reference, out, [int(c) for c in args.cpus.split(",")])
    sample = json.loads((Path(args.sample) / "table" / "table.json").read_text())
    worlds, notes = design(sample["runs"])
    folder = out / "references"
    references(worlds, notes, folder)
    todo = jobs(worlds, start_file=folder / "outputs" / "reference_W1eq.json")
    for name, value in (("worlds", worlds), ("notes", notes), ("registration", registration(worlds)),
                        ("expected_inputs", expected_inputs(worlds, todo))):  # fmt: skip
        (out / f"{name}.json").write_text(json.dumps(value, indent=1) + "\n")
    if args.stage in ("all", "runs"):
        results = run_jobs(todo, out, [int(c) for c in args.cpus.split(",")])
        print("driver failures:", [n for n, rc in results if rc])
        if args.stage == "runs":
            return 0
    from validation.fr45 import exporter

    table = exporter.export(
        out / "records", out / "table", [n for n, _ in todo], invented="INVENTED: rehearsal"
    )
    (out / "addendum.json").write_text(json.dumps(addendum(table), indent=1) + "\n")
    root = Path(__file__).resolve().parents[2]
    import subprocess

    command = [sys.executable, "-B", str(root / "validation" / "fr45" / "judge.py"), "judge",
               "--table", str(out / "table"), "--references", str(folder), "--expected",
               str(out / "expected_inputs.json"), "--registration", str(out / "registration.json"),
               "--addendum", str(out / "addendum.json"), "--out", str(out / "judgement")]  # fmt: skip
    done = subprocess.run(command, capture_output=True, text=True)
    (out / "judge.log").write_text(done.stdout + done.stderr)
    print(done.stdout[-6000:], done.stderr[-3000:])
    return done.returncode


# ------------------------------------------------------------------ the references' own invented file (ruling 5a)


def invented_world(ref):
    """§4.1 inputs for the references' invented format-sample world (`format_sample_INVENTED.json`, which ruling 5a
    lets the builder read): its echo in W3's bath form (the registered cell walled on the bath), every amount it
    does not declare at its trace 1e-12 V, invented host values."""
    from collections import Counter

    echo = ref["world"]
    c = echo["constants"]
    cell = next(n["id"] for n in echo["nodes"] if n["kind"] == "cell")
    node = next(n["id"] for n in echo["nodes"] if n["kind"] == "node")
    nodes = [
        dict(id=n["id"], kind=n["kind"], volume_pL=n["V"], registered=True) for n in echo["nodes"]
    ]
    nodes.append(dict(id="bath", kind="node", volume_pL=140.0, registered=False))
    patches = [dict(p) for p in echo["patches"]] + [
        dict(id="host_wall", inside=cell, outside="bath")
    ]
    declared = {(a["ligand"], a["node"]): a["n"] for a in echo["free_amounts"]}
    free = [dict(ligand=g, node=n["id"], n_fmol=declared.get((g, n["id"]), 1e-12 * n["volume_pL"]),
                 declared=(g, n["id"]) in declared) for g in echo["ligands"] for n in nodes]  # fmt: skip
    members = Counter(p["set"] for p in echo["populations"])
    sets = []
    for s in echo["sets"]:
        kind, _, rest = s["owner"].partition(" ")
        owner, face = (
            (rest, None)
            if kind == "node"
            else (rest.split(",")[0], "inside" if "inside" in rest else "outside")
        )
        sets.append(dict(id=s["id"], shared=members[s["id"]] > 1, owner=owner, face=face, faces=s["faces"],
                         copies=s["copies"], sites_per_copy=s["sites_per_copy"],
                         accessible_fraction=s["accessible_fraction"]))  # fmt: skip
    pops = [
        {k: p[k] for k in ("id", "set", "ligand", "k_on", "k_off", "initial_occupancy")}
        for p in echo["populations"]
    ]
    ids = [p["id"] for p in patches]
    w = echo["wash"]
    return dict(
        world="INVENTED-X",
        constants=dict(sites_per_fmol=float(c["N_f_sites_per_fmol"]), temperature_K=c["T_K"],
                       RT_pJ_per_fmol=c["RT_pJ_per_fmol"]),
        nodes=nodes, patches=patches, ligands=list(echo["ligands"]), free_amounts=free, sets=sets, populations=pops,
        wash=dict(time_s=w["t"], node=w["node"], fraction=w["f"], buffer_mM=dict(w["buffer"])),
        permeabilities=[dict(patch=p, ligand=g, value=0.0) for p in ids for g in echo["ligands"]],
        ion_permeabilities={p: {"IA": 0.0, "IB": 0.0} for p in ids},
        multipliers=[dict(of=p["id"], name="site_binding_multiplier", value=1.0) for p in pops],
        charges={g: 0 for g in echo["ligands"]},
        capacitor_components=[dict(members=["bath", cell, node], held_by="bath")],
        host_values=dict(areas={p: 20.0 for p in ids}, capacitances={p: 0.2 for p in ids},
                         ion_amounts={n["id"]: dict(IA=0.03, IB=0.003) for n in nodes}),
        dt_s=echo["dt"][0], observation_times_s=list(echo["observation_times"]), horizon_s=echo["horizon"],
    )  # fmt: skip


def invented_check(path, out, cpus):
    """The judge's criteria against the references' own invented file (the lead's instruction of 27 November 2026,
    ruling 6's stand-in G): its world through the driver at each of its dt, the table judged against the file as
    written. Some of its pairs are there for their format only (the file says which: C2b against its own root, C7,
    C8), so those criteria are information here."""
    ref = json.loads(Path(path).read_text())
    inputs = invented_world(ref)
    dts = list(ref["world"]["dt"])
    todo = []
    for dt in dts:
        one = copy.deepcopy(inputs)
        one["dt_s"] = dt
        name = f"INVENTED-X-dt{dt!r}"
        todo.append(
            (
                name,
                dict(
                    run=name,
                    inputs=one,
                    plant=None,
                    start=None,
                    time_limit_step=None,
                    map_at_start=True,
                ),
            )
        )
    results = run_jobs(todo, out, cpus)
    print("driver failures:", [n for n, rc in results if rc])
    from validation.fr45 import exporter

    table = exporter.export(
        out / "records",
        out / "table",
        [n for n, _ in todo],
        invented="INVENTED: the references' file",
    )
    folder = out / "references"
    (folder / "outputs").mkdir(parents=True, exist_ok=True)
    (folder / "fr45ref_free_energy.py").write_text(stand_in_module())
    (folder / "outputs" / "reference_X.json").write_text(Path(path).read_text())
    times = [0.0, *inputs["observation_times_s"]]
    base = ["cells.model.resolved_pump_composite@1", "cells.model.resolved_pump_tissue@3",
            "cells.operator.site_occupancy@1", "cells.operator.scheduled_compartment_wash@1"]  # fmt: skip
    reg = dict(runs={f"X-dt{dt!r}": dict(world="X", plant=None, dt_s=dt) for dt in dts},
               rows={"X": {repr(dt): [[t, round(t / dt)] for t in times] for dt in dts}},
               wash={"X": dict(time_s=inputs["wash"]["time_s"])}, maps={"X": [0.0, inputs["wash"]["time_s"]]},
               files={"X": "X"}, heat_nodes={"X": sorted({s["faces"] for s in inputs["sets"]})},
               operators={"X": base}, plants=[], default_dt={"X": dts[0]})  # fmt: skip
    expected = {}
    for name, job in todo:
        want = copy.deepcopy(job["inputs"])
        want["constants"]["RT_pJ_per_fmol"] = None
        want["host_values"] = MARKERS["host_values"]
        for n in want["nodes"]:
            n["volume_pL"] = n["volume_pL"] if n["registered"] else MARKERS["volume"]
        want["ion_permeabilities"] = {p: {"each_ion": 0.0} for p in want["ion_permeabilities"]}
        expected[name.removeprefix("INVENTED-")] = want
    for label, value in (("registration", reg), ("addendum", addendum(table)),
                         ("expected_inputs", dict(runs=expected, plant_inputs_changed={},
                                                  host=dict(markers=dict(MARKERS))))):  # fmt: skip
        (out / f"{label}.json").write_text(json.dumps(value, indent=1) + "\n")
    root = Path(__file__).resolve().parents[2]
    import subprocess

    command = [sys.executable, "-B", str(root / "validation" / "fr45" / "judge.py"), "judge", "--table",
               str(out / "table"), "--references", str(folder), "--expected", str(out / "expected_inputs.json"),
               "--registration", str(out / "registration.json"), "--addendum", str(out / "addendum.json"),
               "--out", str(out / "judgement")]  # fmt: skip
    done = subprocess.run(command, capture_output=True, text=True)
    (out / "judge.log").write_text(done.stdout + done.stderr)
    print(done.stdout[-6000:], done.stderr[-3000:])
    return 0


if __name__ == "__main__":
    sys.exit(main())
