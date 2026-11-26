"""MG0c: Turing patterning at the predicted wavelength, cells.operator.local_species_reactions@1's first acceptance
(D152 version 1; docs/SHARED_INVENTORY_REACTIONS_DESIGN.md §6.4, with §11 and §11.2).

Engine models run, unmodified (IMEX ARS(2,2,2), CPU, float64):
  cells.model.resolved_pump_composite@1 (src/cells/models/pump_composite.py) over cells.model.resolved_pump_tissue@3
  (src/cells/definitions/surface_pump_v3_spec.py, src/cells/models/surface_pump_v3.py) with
  cells.operator.local_species_reactions@1 (src/cells/operators/species_reactions.py): driven mass action
  for Schnakenberg, and cells.species_reaction.ideal_detailed_balance_mass_action@1 in a linear world. The network's
  species are declared by cells.registry.inventory_species (D150).

The world (§6.4): a closed chain of N finite outside nodes of one volume V = 0.5 pL at spacing
h = l/2 = 5 um, joined by faces of area V/h = 1e-10 m^2 and length h (the references' chain
convention, REFERENCES_USAGE.md); quiescent ions (every ion diffusivity zero, every membrane
impermeant); one quiescent cell with a capacitive patch on every node and one on a held bath, so
every node shares a capacitor component with a held node; no face to the bath, so the chain's ends
are zero-flux. U and V are neutral, membrane-impermeant inventory species with D_U = 1e-11 and
D_V = d D_U m^2/s on every face, at the trace 1e-9 mM in the cell and the bath. Schnakenberg (1979)
is four generic mass-action reactions at every finite node: 0 -> U (a k c*), U -> 0 (k),
0 -> V (b k c*), 2U + V -> 3U (k / c*^2); U and V share one moiety. Synthetic, compressed
parameters, labelled so: a = 0.1, b = 0.9, d = 10, k = 0.1 /s, c* = 1 uM, l = sqrt(D_U / k) = 10 um.

Every prediction comes at run time from the independent references (validation/reactions, used
only through REFERENCES_USAGE.md), fed the raw declaration: turing_reference (tu: the dispersion
relation, d_c, the band, the domain modes discrete at h, the staircase), chain_reference (cr: the
zero-flux chain's modes, the exact mode propagator, the engine order's linear step map
strang_mode_map, a DOP853 integration of the semi-discrete system), network_reference (nr).

Deviations are measured without the representation's rounding: @3 stores an outside amount as its
anchor plus an increment, so a deviation is (anchor - reference) + increment, where the first
difference, of two nearby floats, is exact. Mode coefficients are cr.mode_coefficients of it.

Parts (development runs take no --protocol):
  d147    D147's solver check: every world's free field offsets and its declared field solver
  timing  compile and cost per step per chain size, and the window's working estimate
  theory  the analysis, the domains' discrete modes, the staircase, the subcritical control and the
          engine order's discrete-time rates; the declaration against tu's own network
  linear  §3.4 guard 2's reaction-transport check: linear networks on the chain (passive A <-> B
          with D_A != D_B; open 0 -> A -> 0, A -> B -> 0) against strang_mode_map iterated (the
          engine order's own map: rounding) and propagate_modes (exact: second order in dt),
          with the residual over the shared energy bound per dt
  floor   Schnakenberg's linearised map (strang_mode_map with K = k J) on one mode, against the
          start's amplitude: the floor of Q1's linearised comparison
  q1      single-mode starts on L/l = 6, 11, 16 for n <= 6 against the linearised map and the
          exact mode propagator, dt 0.05, 0.025 and 0.0125 s
  q2      L/l = 8 from seeded noise: no admissible unstable mode, the deviation decays
  q3      L/l = 6, 11, 16 from seeded noise: the dominant mode and its growth rate
  q4      the staircase over L/l in [4, 30] from single-mode starts, against the discrete argmax
  q5      the subcritical control (d = 8): every mode decays, at its predicted rate
  q6      the nonlinear pattern on L/l = 11 against cr.integrate_chain, dt 0.05, 0.025, 0.0125 s
  q7      accounting: the face-free world at rounding, restart through a written snapshot read in
          a fresh process (bitwise), a vector batch over seeds on one domain
  sites   reactions at several sites with different multipliers (one site at zero) on the chain,
          against cr.integrate_chain with the same [R, N] multipliers: second order in dt

Usage:
  python -m validation.morphogenesis.mg0c_turing PART [PART ...] --output DIR [--quick]
  ... --protocol FILE: a judged run, refused unless the protocol is registered, the source is a
      clean execution snapshot (validation/source_snapshot.py) and DIR is new (injection_rm1.py's
      and D150's rules)
  python -m validation.morphogenesis.mg0c_turing judge --output DIR --protocol FILE --results R...
      the parts' verdict over the judged runs' results.json (one snapshot, every part once,
      every run complete; no runs)
  python -m validation.morphogenesis.mg0c_turing judge-guards --output DIR --protocol FILE
      the guards' verdict: pytest on the protocol's guards of record, uncapped per file
  python -m validation.morphogenesis.mg0c_turing combine --output DIR --protocol FILE
      --results PARTS_DIR GUARDS_DIR: the one qualification verdict
"""

import argparse
import copy
import hashlib
import json
import math
import os
import re
import resource
import subprocess
import sys
import time
import traceback
from pathlib import Path

import numpy as np

from validation.morphogenesis.mg0a_gradient import evaluate
from validation.tissue import species_reactions_fixtures as rfx

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "validation/morphogenesis/protocols/mg0c_turing_v1.json"
OUTPUT = None  # The run's output directory (set by main), for parts that write as they go.
STATUS = "Development run of MG0c (D152 v1, milestone 3); not judged."

# ------------------------------------------------------------------ the world (§6.4)

SPACING_M = 5e-6  # h = l/2.
AREA_M2 = 1e-10  # V / h.
VOLUME_PL = AREA_M2 * SPACING_M * 1e15  # 0.5 pL.
D_U = 1e-11  # m^2/s.
RATE_K = 0.1  # 1/s.
C_STAR_MM = 1e-3  # 1 uM.
A, B, D_RATIO = 0.1, 0.9, 10.0
SUBCRITICAL = 8.0
TRACE_MM = 1e-9
FLOOR_FMOL = 1e-20
AMPLITUDE = 1e-7  # Q1's single-mode starts, of c*.
NOISE = 1e-3  # Q2, Q3 and Q6's seeded noise, of c*.
ION_SPECIES = (("Na", 1), ("K", 1), ("Cl", -1))
BATH_MM = dict(Na=145.0, K=5.0, Cl=150.0)
IMEX = "cells.solver.imex_ars222_face_electromigration@1"
DOMAINS = {6: 12, 8: 16, 11: 22, 16: 32}  # L/l: nodes at h = l/2.
DTS = (0.05, 0.025, 0.0125)
STAIRCASE = tuple(4.0 + 0.5 * i for i in range(53))  # 4 to 30 (amended at milestone 1, §11).
WINDOW_STEPS = 1000
SEEDS = dict(
    q2=152, q3={6: 13, 11: 18, 16: 23}, q6=11, q7_face_free=5, q7_restart=3, q7_batch=(3, 4, 5)
)


def length_scale_m():
    return math.sqrt(D_U / RATE_K)


def key(prefix, value):
    """A metric-path-safe key (mg0a_gradient's metric paths split on '.')."""
    return f"{prefix}{value:g}".replace(".", "p")


def dt_key(dt):
    return key("dt", 1e3 * dt) + "ms"


def _node(name, volume, *, outside=True, reservoir=False):
    amounts = {s: BATH_MM[s] * volume for s, _ in ION_SPECIES}
    charge = math.fsum(z * amounts[s] for s, z in ION_SPECIES)
    node = dict(
        id=name,
        volume_pL=volume,
        initial_amount_fmol=amounts,
        fixed_charge_equivalent_fmol=-charge,
        initial_charge_C=0.0,
    )
    return node | (dict(reservoir=reservoir, boundary_potential_V=0.0) if outside else {})


def _patch(name, inside, outside, area, capacitance):
    return dict(
        id=name,
        inside=inside,
        outside=outside,
        area_m2=area,
        capacitance_F=capacitance,
        permeability_m_per_s={s: 0.0 for s, _ in ION_SPECIES},
        law="cells.route.constant_field@1",
        pump=None,
        calcium_pump=None,
    )


def _controls(reactions, site_multipliers=None):
    """Every reaction at multiplier 1 from time 0, and per-site schedules {(reaction, node): m}."""
    controls = rfx.always([r["id"] for r in reactions])
    for (reaction, node), value in (site_multipliers or {}).items():
        controls.append((reaction, node, [(0.0, value)]))
    return controls


def schnakenberg(a=A, b=B, k=RATE_K, c_star=C_STAR_MM):
    """(species, reactions, controls): the four generic mass-action declarations (§6.4)."""
    sites = {"outside": "all"}
    species = [rfx.species("U", moieties={"M": 1}), rfx.species("V", moieties={"M": 1})]
    reactions = [
        rfx.mass_action("production_U", sites, {}, {"U": 1}, a * k * c_star),
        rfx.mass_action("decay_U", sites, {"U": 1}, {}, k),
        rfx.mass_action("production_V", sites, {}, {"V": 1}, b * k * c_star),
        rfx.mass_action("autocatalysis", sites, {"U": 2, "V": 1}, {"U": 3}, k / c_star**2),
    ]
    return species, reactions, _controls(reactions)


def passive_pair():
    """§6.2 world 1: passive A <-> B (K = 10 at c0 = 1 mM, k_f 0.2 /s), D_A = 1e-11, D_B = 1e-10."""
    species = [
        rfx.species("A", moieties={"M": 1}),
        rfx.species("B", moieties={"M": 1}, mu=-math.log(10.0)),
    ]
    reactions = [rfx.passive("swap", {"outside": "all"}, {"A": 1}, {"B": 1}, 0.2)]
    return dict(
        network=(species, reactions, _controls(reactions)),
        diffusivities=dict(A=1e-11, B=1e-10),
        base_mM=dict(A=1e-3, B=1e-3),
    )


def open_pair(site_multipliers=None):
    """Open linear kinetics on the chain: 0 -> A (2e-5 mM/s), A -> 0 (0.05 /s), A -> B (0.03 /s),
    B -> 0 (0.02 /s); D_A = 1e-11, D_B = 1e-10 m^2/s."""
    sites = {"outside": "all"}
    species = [rfx.species("A", moieties={"M": 1}), rfx.species("B", moieties={"M": 1})]
    reactions = [
        rfx.mass_action("make", sites, {}, {"A": 1}, 2e-5),
        rfx.mass_action("clear", sites, {"A": 1}, {}, 0.05),
        rfx.mass_action("convert", sites, {"A": 1}, {"B": 1}, 0.03),
        rfx.mass_action("drain", sites, {"B": 1}, {}, 0.02),
    ]
    return dict(
        network=(species, reactions, _controls(reactions, site_multipliers)),
        diffusivities=dict(A=1e-11, B=1e-10),
        base_mM=dict(A=4e-4, B=1e-3),
    )


def grid_times(dt, times_s, end_s, base=DTS[0]):
    """Observation times on the run's grid (k dt for integer k), the same physical times at every
    dt of the study: `times_s` and the end are rounded to multiples of `base` (the coarsest dt),
    then placed on this dt's grid, the end as k_end dt so the last step is a whole one; returns
    (times, end)."""

    def place(t):
        return round(round(t / base) * base / dt) * dt

    end = place(end_s)
    out = {0.0, end}
    out.update(place(t) for t in times_s if 0.0 < place(t) < end)
    return sorted(out), end


def chain_world(
    profile_mM,
    *,
    n_nodes=None,
    network=None,
    diffusivities=None,
    d=D_RATIO,
    dt=0.05,
    end=100.0,
    observation_times=None,
    faces=True,
    solver=IMEX,
):
    """The closed chain (module docstring) as a composite definition with a reaction network.

    profile_mM: {species: [N] mM} on the chain's nodes, for every species the network names (it
    sets the chain's size N); an empty profile gives the ions-only chain of n_nodes nodes, with no
    inventory species and no network; network: (species, reactions, controls), default Schnakenberg;
    diffusivities: {species: m^2/s}, default U at D_U and V at d D_U; faces=False isolates every
    node (the face-free world, where the network is the only energy flow)."""
    from cells.definitions import pump_composite_spec as cs
    from cells.registry.inventory_species import add_inventory_species

    names = list(profile_mM)
    n_nodes = len(next(iter(profile_mM.values()))) if names else n_nodes
    diffusivities = diffusivities or dict(U=D_U, V=d * D_U)
    nodes = [f"node_{i}" for i in range(n_nodes)]
    outside = [_node("bath", 1.0, reservoir=True)] + [_node(n, VOLUME_PL) for n in nodes]
    membranes = [_patch("wall", "cell", "bath", 1e-10, 1e-12)]
    membranes += [_patch(f"contact_{i}", "cell", n, 1e-11, 1e-13) for i, n in enumerate(nodes)]
    face_list = [
        dict(
            id=f"face_{i}",
            sender=nodes[i],
            receiver=nodes[i + 1],
            area_m2=AREA_M2,
            length_m=SPACING_M,
            diffusivity_m2_per_s={s: 0.0 for s, _ in ION_SPECIES},
            law="cells.route.logmean_electrodiffusion@1",
        )
        for i in range(n_nodes - 1 if faces else 0)
    ]
    always = [dict(time=0.0, availability=1.0)]
    raw = dict(
        schema_version=1,
        model=dict(
            id="cells.model.resolved_pump_tissue@3",
            temperature_K=310.0,
            species=[dict(id=s, valence=z) for s, z in ION_SPECIES],
            cells=[_node("cell", 1.0, outside=False)],
            extracellular=outside,
            membranes=membranes,
            junctions=[],
            faces=face_list,
            closure=dict(
                law="cells.field_closure.resolved_capacitor_components_current_continuity@1",
                gauge_reference=None,
            ),
            channels=[],
        ),
        experiment=dict(
            end_time=end,
            observation_times=list(observation_times or [0.0, end]),
            membrane_controls=[
                dict(membrane_id=p["id"], schedule=copy.deepcopy(always)) for p in membranes
            ],
            junction_controls=[],
            pump_controls=[],
            calcium_pump_controls=[],
            channel_controls=[],
        ),
        execution=dict(
            dt=dt,
            capacity=1,
            extracellular_capacity=len(outside),
            membrane_capacity=len(membranes),
            edge_capacity=0,
            face_capacity=max(1, len(face_list)),
            channel_capacity=0,
            backend="cpu",
            jit=True,
            precision="float64",
            solver=solver,
            field_solver="cells.solver.capacitive_reduction_gauged_damped_newton@2",
            max_steps=int(math.ceil(end / dt)) + 8,
            max_trace_bytes=2**31,
            material_balance_atol_fmol={s: 1e-10 for s, _ in ION_SPECIES},
        ),
    )
    raw = cs.frozen_definition(raw)
    if not names:
        return raw
    for name in names:
        values = np.asarray(profile_mM[name], dtype=float)
        raw = add_inventory_species(
            raw,
            name,
            trace_mM=TRACE_MM,
            diffusivity_m2_per_s=diffusivities[name],
            floor_fmol=FLOOR_FMOL,
            concentrations_mM={n: float(c) for n, c in zip(nodes, values, strict=True)},
        )
    species, reactions, controls = network or schnakenberg()
    return rfx.with_reactions(raw, species, reactions, controls)


def uniform_mM(a=A, b=B):
    """{U, V}: the uniform steady state (mM), from the reference."""
    from validation.reactions import turing_reference as tu

    u0, v0 = tu.schnakenberg_uniform_state(a, b)
    return dict(U=C_STAR_MM * u0, V=C_STAR_MM * v0)


def mode_profile(n_nodes, mode, amplitude=AMPLITUDE):
    """The uniform state plus mode `mode` at `amplitude` of c* in U and V."""
    from validation.reactions import chain_reference as cr

    shape = np.asarray(cr.mode_basis(n_nodes))[mode]
    return {s: c + amplitude * C_STAR_MM * shape for s, c in uniform_mM().items()}


def noise_profile(n_nodes, seed, amplitude=NOISE):
    """The uniform state plus seeded uniform noise in [-amplitude, amplitude] c* at every node."""
    rng = np.random.default_rng(seed)
    return {
        s: c + amplitude * C_STAR_MM * (2.0 * rng.uniform(size=n_nodes) - 1.0)
        for s, c in uniform_mM().items()
    }


# ------------------------------------------------------------------ the engine, windowed


def run_chain(raw, base_mM, *, every_row=False, window_steps=WINDOW_STEPS):
    """Run through run_windowed (every host check on every window; a failure raises) and keep, at
    the observation times, the network's deviations from base_mM on the chain [T, S, N] (fmol,
    without the representation's rounding) and its amounts [T, S, N] (fmol).

    At every observed row and every window's last row (every row with every_row) it measures the
    energy residual over the composite's own energy bound (its ledger_limits: 2e-8 pJ, rtol times
    the flows, and the rounding allowance), the network rows' material residuals over theirs
    (local, outside, total), the energy residual over the rounding allowance alone (2.5 eps x
    steps x the energy magnitude, the face-free guard of record, §3.4 guard 1) and the smallest
    network amount."""
    from cells.definitions.specs import parse_spec
    from cells.execution.windows import WindowPolicy, run_windowed
    from cells.models.surface_pump import ENERGY_RTOL, LEDGER_STEP_ROUNDING
    from cells.registry.models import get_model

    spec = parse_spec(raw)
    model = get_model(spec.model)
    _, p = model.initial_values(spec)
    block = next(b for b in raw["model"]["operators"] if b["law"] == rfx.REACTIONS)
    names = [s["id"] for s in block["species"]]
    species = list(spec.model.species_ids)
    rows = [species.index(n) for n in names]
    outside = [c.id for c in spec.model.extracellular]
    columns = [outside.index(c) for c in outside if c.startswith("node_")]
    volume = np.asarray(p.extracellular_volume)[columns]
    anchor = np.asarray(p.extracellular_amount_reference)[np.ix_(rows, columns)]
    reference = np.asarray([base_mM[n] * VOLUME_PL for n in names])[:, None]
    initial = anchor - reference  # Exact: nearby floats.
    tol = np.asarray(spec.execution.material_balance_atol_fmol)
    rtol = ENERGY_RTOL[spec.execution.solver]
    eps = np.finfo(float).eps
    dt = spec.execution.dt
    wanted = {float(t) for t in spec.experiment.observation_times}
    out = dict(times=[], deviation=[], amount=[])
    worst = dict(
        energy_over_bound=0.0,
        energy_over_rounding=0.0,
        material_over_bound=0.0,
        min_amount_fmol=math.inf,
        rows_checked=0,
    )
    diagnostics, windows = {}, [0]

    def check(row, t):
        b = model.balances(row, p)
        ledgers = list(b)
        mags = model.magnitudes(row, p)
        steps = int(round(t / dt))
        _, limits = model.ledger_limits(row, p, tol, rtol, steps=steps, magnitudes=mags)
        e = ledgers.index("energy")
        residual = abs(float(b["energy"]))
        worst["energy_over_bound"] = max(worst["energy_over_bound"], residual / float(limits[e]))
        allowance = LEDGER_STEP_ROUNDING * eps * max(steps, 1) * float(mags[e])
        ratio = 0.0 if residual == 0.0 else residual / allowance if allowance > 0 else math.inf
        worst["energy_over_rounding"] = max(worst["energy_over_rounding"], ratio)
        for name in ("local", "outside", "total"):
            value = np.abs(np.asarray(b[name]))
            bound = np.broadcast_to(np.asarray(limits[ledgers.index(name)]), value.shape)
            worst["material_over_bound"] = max(
                worst["material_over_bound"], float(np.max(value[rows] / bound[rows]))
            )
        amount = anchor + np.asarray(row.extracellular_amount_increment)[np.ix_(rows, columns)]
        worst["min_amount_fmol"] = min(worst["min_amount_fmol"], float(np.min(amount)))
        worst["rows_checked"] += 1

    def sink(window):
        times = np.asarray(window.times)
        h = type(window.history)(*(np.asarray(v) for v in window.history))
        last = out["times"][-1] if out["times"] else -1.0
        for i, t in enumerate(times):
            t = float(t)
            observed = t in wanted and t > last
            if observed or every_row or i == len(times) - 1:
                check(type(h)(*(v[i] for v in h)), t)
            if observed:
                increment = h.extracellular_amount_increment[i][np.ix_(rows, columns)]
                out["times"].append(t)
                out["deviation"].append(initial + increment)
                out["amount"].append(anchor + increment)
        for k, v in window.diagnostics.items():
            if np.isscalar(v):
                diagnostics[k] = max(diagnostics.get(k, -math.inf), float(v))
        windows[0] += 1

    started = time.perf_counter()
    result = run_windowed(spec, WindowPolicy(window_steps, "observations"), sink=sink)
    return dict(
        times=np.asarray(out["times"]),
        deviation=np.asarray(out["deviation"]),
        amount=np.asarray(out["amount"]),
        volume=volume,
        names=names,
        wall_s=time.perf_counter() - started,
        windows=windows[0],
        steps=int(result.final.step_index),
        resources={k: v for k, v in result.resources.items() if np.isscalar(v)},
        diagnostics=diagnostics,
        checks=worst,
        final=result.final,
        spec=spec,
    )


def accounting(run):
    """A run's accounting record."""
    keep = ("max_energy_balance_relative", "max_energy_balance_error_pJ", "max_balance_error_fmol")
    return dict(
        **run["checks"],
        **{k: run["diagnostics"].get(k) for k in keep},
        steps=run["steps"],
        wall_s=run["wall_s"],
        ms_per_step=1e3 * run["wall_s"] / max(run["steps"], 1),
    )


def coefficients(run, modes=None):
    """[T, S, N] the deviations' mode coefficients (concentration units, mM)."""
    from validation.reactions import chain_reference as cr

    a = np.asarray(cr.mode_coefficients(run["deviation"] / run["volume"]))
    return a if modes is None else a[..., modes]


def schnakenberg_rates(d=D_RATIO, a=A, b=B):
    """(K = k J in 1/s on concentration deviations, D [S] in m^2/s)."""
    from validation.reactions import turing_reference as tu

    return RATE_K * np.asarray(tu.schnakenberg_jacobian(a, b)), np.asarray([D_U, d * D_U])


def _lam(n_nodes, mode):
    from validation.reactions import chain_reference as cr

    return float(np.asarray(cr.chain_eigenvalues(n_nodes, SPACING_M))[mode])


def discrete_rate(K, D, n_nodes, mode, dt):
    """The growth rate (1/s) of `mode` under the engine order's linear step map (one step)."""
    from validation.reactions import chain_reference as cr

    M, _ = cr.strang_mode_map(K, D, _lam(n_nodes, mode), dt)
    return math.log(float(np.max(np.abs(np.linalg.eigvals(np.asarray(M)))))) / dt


def continuous_rate(K, D, n_nodes, mode):
    """sigma_n of the semi-discrete system: max Re eig(K - lambda_n D) (1/s)."""
    return float(np.max(np.linalg.eigvals(K - _lam(n_nodes, mode) * np.diag(D)).real))


def record_time(K, D, n_nodes, mode, cap=600.0):
    """3 / |Re lambda| of the mode's slowest eigenvalue (the usage note's record), capped."""
    return min(cap, 3.0 / max(abs(continuous_rate(K, D, n_nodes, mode)), 1e-12))


def _fit(times, values, start, stop):
    from validation.reactions import chain_reference as cr

    pick = (times >= start) & (times <= stop) & (np.abs(values) > 0)
    if np.count_nonzero(pick) < 3:
        return None, None
    slope, rms = cr.fit_growth_rate(times[pick], np.abs(values[pick]))
    return float(slope), float(rms)


def _rate_difference(fitted, predicted):
    """|fitted - predicted| / |predicted|, or None without a fit."""
    return None if fitted is None else abs(fitted - predicted) / abs(predicted)


def accounting_summary(results):
    """The worst of every run's accounting record in the results (every part, every run)."""
    worst = dict(
        runs=0, max_energy_over_bound=0.0, max_material_over_bound=0.0, min_amount_fmol=None
    )

    def walk(value):
        if isinstance(value, dict):
            if "energy_over_bound" in value and "material_over_bound" in value:
                worst["runs"] += 1
                worst["max_energy_over_bound"] = max(
                    worst["max_energy_over_bound"], value["energy_over_bound"]
                )
                worst["max_material_over_bound"] = max(
                    worst["max_material_over_bound"], value["material_over_bound"]
                )
                low = value.get("min_amount_fmol")
                if isinstance(low, float):
                    worst["min_amount_fmol"] = (
                        low
                        if worst["min_amount_fmol"] is None
                        else min(worst["min_amount_fmol"], low)
                    )
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(results["parts"])
    return worst


def _relative(a, b):
    return float(np.max(np.abs(np.asarray(a) - np.asarray(b))) / np.max(np.abs(np.asarray(b))))


# ------------------------------------------------------------------ the rules (D150's forms)

EPS = float(np.finfo(float).eps)
REFERENCE_EPS = 64  # An exact reference's term: 64 eps x the scale (S5's and D150's floor).
FACTOR = 3.0  # S5's dt-study rule: 3 x (the step term + the reference term).
USAGE_NOTE_PER_STEP = 1e-14  # The usage note's accumulation against strang_mode_map: 1e-10 at 1e4.
Q6_GRID = tuple(d for d in (m * 10.0**e for e in range(-9, 0) for m in (1, 2, 5)) if d <= 0.1)
Q6_GRID_QUICK = (1e-8, 1e-6, 1e-4, 1e-2)
DELTAS = (*(m * 10.0**e for e in range(-14, 0) for m in (1, 2, 5)), 0.5)  # A 1-2-5 grid.


def dt_rule(values, truth, scale, reference=None):
    """S5's dt-study rule (D150's protocol), per element and record. values [dt, record, ...]: the
    engine at the same records for each dt of DTS (each the next's double); truth [record, ...];
    reference: the reference's own term per element (default 64 eps x scale, an exact reference).
    For each dt with a half: the step term |q(dt) - q(dt/2)|, the tolerance 3 x (step term +
    reference term) and the error |q(dt) - truth|; where the worst ratio lies ([record, ...]) and
    how many elements exceed. Returns (summary, tolerances {dt index: array}).
    The summary also has the observed orders per record (log2 of successive max-norm differences,
    where both lie above the floor 64 eps x scale) and the stop rule (every measurable difference
    decreases)."""
    values, truth = np.asarray(values, dtype=float), np.asarray(truth, dtype=float)
    floor = REFERENCE_EPS * EPS * scale
    ref = floor if reference is None else np.asarray(reference, dtype=float) + floor
    summary, tolerances = {}, {}
    for i in range(len(values) - 1):
        step = np.abs(values[i] - values[i + 1])
        tolerance = FACTOR * (step + ref)
        error = np.abs(values[i] - truth)
        tolerances[i] = tolerance
        ratio = error / tolerance
        summary[dt_key(DTS[i])] = dict(
            max_error=float(np.max(error)),
            max_error_of_scale=float(np.max(error)) / scale,
            max_step_term=float(np.max(step)),
            max_ratio=float(np.max(ratio)),
            max_ratio_at=[int(j) for j in np.unravel_index(np.argmax(ratio), ratio.shape)],
            elements=int(ratio.size),
            exceeding=int(np.count_nonzero(ratio > 1.0)),
            passes=bool(np.max(ratio) <= 1.0),
            within_fraction=float(np.mean(error <= tolerance)),
            error_le_step_fraction=float(np.mean(error <= step)),
        )
    if len(values) >= 3:
        axes = tuple(range(1, values.ndim - 1))
        first = np.max(np.abs(values[0] - values[1]), axis=axes)
        second = np.max(np.abs(values[1] - values[2]), axis=axes)
        measurable = (first > floor) & (second > floor)
        summary["orders"] = [
            float(np.log2(a / b)) if m else None
            for a, b, m in zip(first, second, measurable, strict=True)
        ]
        summary["stop_rule_differences_decrease"] = bool(
            np.all(first[measurable] > second[measurable])
        )
        summary["measurable_records"] = int(np.count_nonzero(measurable))
    summary["scale"] = scale
    return summary, tolerances


PARAMETERS = ("k", "a", "b", "D_U", "D_V")  # Each must be caught by a judged control (the lead).


def smallest_caught_bisected(value, tolerance, perturbed, deltas=DELTAS):
    """smallest_caught for a costly perturbation (each one a reference integration): bisection on
    the grid, assuming that a larger delta is caught whenever a smaller one is (true where the
    error is about linear in delta); about log2 of the grid's length evaluations. None if the
    largest is not caught."""

    def caught(i):
        return bool(np.any(np.abs(value - perturbed(deltas[i])) > tolerance))

    low, high = 0, len(deltas) - 1
    if not caught(high):
        return None
    if caught(low):
        return deltas[low]
    while high - low > 1:
        middle = (low + high) // 2
        if caught(middle):
            high = middle
        else:
            low = middle
    return deltas[high]


def smallest_caught(value, tolerance, perturbed, deltas=DELTAS):
    """The smallest delta on the grid at which the rule catches the reference perturbed by it (its
    error exceeds the tolerance somewhere), or None. perturbed: delta -> the perturbed truth."""
    for d in deltas:
        if np.any(np.abs(value - perturbed(d)) > tolerance):
            return d
    return None


# A judged run's registered control deltas, {"q1.L6.n1.dt50ms.k": delta, ...}, from the protocol.
REGISTERED_DELTAS = {}


def controls(path, value, tolerance, perturbed, passes, deltas=DELTAS, *, bisect=False):
    """The controls of one rule at one judged dt: per kind, the smallest caught delta on the grid
    (development; bisected for a costly reference) and, in a judged run, whether the registered
    delta is caught. A control means nothing where the unperturbed rule already fails (passes
    False): it is then recorded so, and the protocol's draft refuses it."""
    scan = smallest_caught_bisected if bisect else smallest_caught
    out = {}
    for kind, function in perturbed.items():
        entry = dict(
            rule_passes_unperturbed=bool(passes),
            smallest_caught=scan(value, tolerance, function, deltas) if passes else None,
        )
        registered = REGISTERED_DELTAS.get(f"{path}.{kind}")
        if registered is not None:
            entry["registered_delta"] = registered
            entry["caught_at_registered"] = bool(
                np.any(np.abs(value - function(registered)) > tolerance)
            )
        out[kind] = entry
    return out


# ------------------------------------------------------------------ parts


def part_timing(quick):
    """Per chain size: a first run (compile), a second world with another start (does the compile
    carry over?), the second world again, and the window's working estimate."""
    from cells.definitions.specs import parse_spec
    from cells.execution.windows import WindowPolicy, plan_windows

    out = {}
    for n_nodes in (12, 22) if quick else (12, 16, 22, 32, 60):
        entry = {}
        for label, mode in (("first", 1), ("second", 2), ("repeat", 2)):
            raw = chain_world(mode_profile(n_nodes, mode), dt=0.05, end=200 * 0.05)
            run = run_chain(raw, uniform_mM())
            entry[label] = dict(wall_s=run["wall_s"], steps=run["steps"])
        plan = plan_windows(parse_spec(raw), WindowPolicy(WINDOW_STEPS, "observations"))
        entry["estimated_window_bytes"] = int(plan.estimated_working_bytes)
        entry["ms_per_step_repeat"] = 1e3 * entry["repeat"]["wall_s"] / entry["repeat"]["steps"]
        out[f"N{n_nodes}"] = entry
    raw = chain_world(mode_profile(22, 2), dt=0.0125, end=200 * 0.0125)
    run = run_chain(raw, uniform_mM())
    out["N22_dt12p5ms"] = dict(wall_s=run["wall_s"], steps=run["steps"])
    out["peak_rss_mb"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    return out


def part_theory(quick):
    from validation.reactions import turing_reference as tu

    J = np.asarray(tu.schnakenberg_jacobian(A, B))
    spacing = SPACING_M / length_scale_m()
    analysis = tu.turing_analysis(J, 1.0, D_RATIO)
    K, D = schnakenberg_rates()
    domains = {}
    for L, n_nodes in DOMAINS.items():
        modes = tu.domain_modes(J, 1.0, D_RATIO, L, spacing=spacing)
        unstable = tu.admissible_unstable_modes(J, 1.0, D_RATIO, L, spacing=spacing)
        rows = {}
        for n in range(1, 7):
            rows[f"n{n}"] = dict(
                sigma_continuum=float(np.asarray(modes["sigma_continuum"])[n - 1]),
                sigma_discrete=float(np.asarray(modes["sigma_discrete"])[n - 1]),
                k2_continuum=float(np.asarray(modes["k2_continuum"])[n - 1]),
                k2_discrete=float(np.asarray(modes["k2_discrete"])[n - 1]),
                semi_discrete_rate_per_s=continuous_rate(K, D, n_nodes, n),
                **{
                    "discrete_time_rate_" + dt_key(dt): discrete_rate(K, D, n_nodes, n, dt)
                    for dt in DTS
                },
                record_s=record_time(K, D, n_nodes, n),
            )
        domains[key("L", L)] = dict(
            nodes=n_nodes,
            unstable=_modes(unstable),
            fastest=tu.fastest_admissible_mode(J, 1.0, D_RATIO, L, spacing=spacing),
            modes=rows,
        )
    discrete = tu.staircase(J, 1.0, D_RATIO, list(STAIRCASE), spacing=spacing)
    continuum = tu.staircase(J, 1.0, D_RATIO, list(STAIRCASE), spacing=None)
    Ks, Ds = schnakenberg_rates(SUBCRITICAL)
    subcritical = {}
    for L, n_nodes in DOMAINS.items():
        sigma = tu.domain_modes(J, 1.0, SUBCRITICAL, L, spacing=spacing)["sigma_discrete"]
        subcritical[key("L", L)] = dict(
            max_sigma_discrete=float(np.max(np.asarray(sigma))),
            discrete_time_rates_per_s=[
                discrete_rate(Ks, Ds, n_nodes, n, 0.05) for n in range(1, 7)
            ],
        )
    # The declaration against the references' own Schnakenberg network.
    mine = rfx.reference_network(chain_world(mode_profile(12, 1)))
    theirs = tu.schnakenberg_network(A, B, RATE_K, C_STAR_MM)

    def summary(net):
        return [
            (r.name, r.law, dict(r.reactants), dict(r.products), float(r.rate_constant))
            for r in net.reactions
        ]

    agree = len(mine.reactions) == len(theirs.reactions) and all(
        x[:4] == y[:4] and abs(x[4] - y[4]) <= 1e-15 * abs(y[4])
        for x, y in zip(summary(mine), summary(theirs), strict=False)
    )
    return dict(
        analysis=analysis,
        critical_ratio_subcritical_margin=float(analysis["critical_ratio"]) - SUBCRITICAL,
        rate_constants=tu.schnakenberg_rate_constants(A, B, RATE_K, C_STAR_MM),
        declaration_matches_reference_network=bool(agree),
        declaration=summary(mine),
        length_scale_m=length_scale_m(),
        wavelength_m=float(analysis["wavelength"]) * length_scale_m(),
        e_fold_s=1.0 / (float(analysis["sigma_max"]) * RATE_K),
        explicit_rate_bound_per_s=4.0 * D_RATIO * D_U / SPACING_M**2,
        domains=domains,
        staircase=[
            dict(L=L, discrete=nd, continuum=nc)
            for (L, nd), (_, nc) in zip(discrete, continuum, strict=True)
        ],
        subcritical=subcritical,
    )


def _modes(value):
    return [] if value is None else sorted(int(n) for n in np.atleast_1d(value))


def _iterate_maps(K, D, n_nodes, dt, steps, a0, source, dtype=np.float64):
    """Coefficients after `steps` engine-order steps, mode by mode (strang_mode_map iterated), in
    `dtype` (np.longdouble isolates the engine's own rounding from the iteration's)."""
    from validation.reactions import chain_reference as cr

    out = np.zeros(a0.shape, dtype=dtype)
    for n in range(n_nodes):
        M, q = cr.strang_mode_map(K, D, _lam(n_nodes, n), dt, source=source if n == 0 else None)
        M = np.asarray(M, dtype=np.float64).astype(dtype)
        q = np.zeros(a0.shape[0], dtype=dtype) if q is None else np.asarray(q).astype(dtype)
        a = np.asarray(a0[:, n], dtype=np.float64).astype(dtype)
        for _ in range(steps):
            a = M @ a + q
        out[:, n] = a
    return out


def part_linear(quick):
    """§3.4 guard 2: linear networks on the chain (module docstring). The implementation rule, a
    priori: |engine - strang_mode_map iterated| <= 1e-14 x steps x the scale (REFERENCES_USAGE.md's
    accumulation, 1e-10 at 1e4 steps), with D150's tighter steps x eps x the scale reported. The
    accuracy: the dt-study rule against propagate_modes (exact), with the observed orders."""
    from validation.reactions import chain_reference as cr

    n_nodes = 12
    end = 20.0 if quick else 100.0
    shape = np.asarray(cr.mode_basis(n_nodes))
    dts = DTS[:2] if quick else DTS
    out = {}
    for label, world in (("passive", passive_pair()), ("open", open_pair())):
        base = world["base_mM"]
        profile = {s: c * (1.0 + 0.05 * shape[2] + 0.02 * shape[5]) for s, c in base.items()}
        names = list(profile)
        D = np.asarray([world["diffusivities"][s] for s in names])
        entry, values, truth = {}, [], None
        for dt in dts:
            times, stop = grid_times(dt, [end / 4, end / 2, 3 * end / 4], end)
            raw = chain_world(
                profile,
                network=world["network"],
                diffusivities=world["diffusivities"],
                dt=dt,
                end=stop,
                observation_times=times,
            )
            run = run_chain(raw, base)
            K, source = cr.linear_rates(rfx.reference_network(raw))
            K, source = np.asarray(K), np.asarray(source)
            a = coefficients(run)  # [T, S, N] of the deviation.
            a[:, :, 0] += np.asarray([base[s] * VOLUME_PL for s in names]) / run["volume"][0]
            start, scale = a[0], float(np.max(np.abs(a[0])))
            worst_map = worst_rule = worst_note = 0.0
            exact, per_record = [], []
            for t, value in zip(run["times"][1:], a[1:], strict=True):
                steps = int(round(t / dt))
                mapped = _iterate_maps(K, D, n_nodes, dt, steps, start, source)
                long = _iterate_maps(K, D, n_nodes, dt, steps, start, source, np.longdouble)
                difference = float(np.max(np.abs(value - mapped)))
                worst_map = max(worst_map, difference / scale)
                worst_rule = max(worst_rule, difference / (steps * EPS * scale))
                worst_note = max(worst_note, difference / (USAGE_NOTE_PER_STEP * steps * scale))
                per_record.append(
                    dict(
                        time_s=t,
                        steps=steps,
                        engine_vs_map_over_steps_eps=difference / (steps * EPS * scale),
                        engine_vs_long_map_over_steps_eps=float(
                            np.max(np.abs(value - long.astype(np.float64)))
                        )
                        / (steps * EPS * scale),
                        map_vs_long_map_over_steps_eps=float(
                            np.max(np.abs((mapped - long).astype(np.float64)))
                        )
                        / (steps * EPS * scale),
                    )
                )
                exact.append(
                    np.asarray(
                        cr.propagate_modes(K, D, n_nodes, SPACING_M, start, t, source=source)
                    )
                )
            values.append(a[1:])
            truth = np.asarray(exact) if truth is None else truth
            entry[dt_key(dt)] = dict(
                against_engine_order_map=worst_map,
                map_over_rounding_rule=worst_rule,
                map_over_usage_note_rule=worst_note,
                by_record=per_record,
                against_exact=float(np.max(np.abs(a[1:] - np.asarray(exact)))) / scale,
                steps_at_end=int(round(stop / dt)),
                accounting=accounting(run),
            )
        rule, _ = dt_rule(values, truth, float(np.max(np.abs(values[0]))))
        entry["dt_rule"] = rule
        errors = [entry[dt_key(dt)]["against_exact"] for dt in dts]
        entry["exact_ratios"] = [errors[i] / errors[i + 1] for i in range(len(errors) - 1)]
        out[label] = entry
    return out


def _single_mode(
    n_nodes, mode, dt, record, *, amplitude=AMPLITUDE, d=D_RATIO, fractions=(1 / 3, 2 / 3)
):
    """A single-mode start run to `record`: the mode's coefficient vector [T, 2], and the run."""
    times, stop = grid_times(dt, [f * record for f in fractions], record)
    raw = chain_world(
        mode_profile(n_nodes, mode, amplitude), d=d, dt=dt, end=stop, observation_times=times
    )
    run = run_chain(raw, uniform_mM())
    return coefficients(run, mode), run


def _linear_references(a, times, K, D, n_nodes, mode, dt):
    """At each record after the start: the linearised engine-order map's coefficients (with K = k J,
    strang_mode_map iterated) and the exact propagator's."""
    from validation.reactions import chain_reference as cr

    lam = _lam(n_nodes, mode)
    M = np.asarray(cr.strang_mode_map(K, D, lam, dt)[0])
    mapped = [np.linalg.matrix_power(M, int(round(t / dt))) @ a[0] for t in times[1:]]
    exact = [np.asarray(cr.mode_propagator(K, D, lam, t)) @ a[0] for t in times[1:]]
    return np.asarray(mapped), np.asarray(exact)


def _relative_rows(value, truth):
    """The largest |value - truth| over each record's largest |truth| (the vector's scale)."""
    scale = np.max(np.abs(truth), axis=-1)
    return float(np.max(np.max(np.abs(value - truth), axis=-1) / scale))


def part_floor(quick):
    """The engine against Schnakenberg's linearised map on one mode against the start's amplitude:
    the floor (the representation's rounding, falling as the amplitude rises) and the nonlinear
    terms (rising with it)."""
    K, D = schnakenberg_rates()
    out = {}
    amplitudes = (1e-8, 1e-7, 1e-5) if quick else (1e-9, 1e-8, 1e-7, 1e-6, 1e-5, 1e-4)
    for L, mode in ((11, 2),) if quick else ((11, 2), (11, 5)):
        n_nodes = DOMAINS[L]
        record = min(record_time(K, D, n_nodes, mode), 200.0)
        entry = {}
        for amplitude in amplitudes:
            a, run = _single_mode(n_nodes, mode, 0.05, record, amplitude=amplitude)
            mapped, exact = _linear_references(a, run["times"], K, D, n_nodes, mode, 0.05)
            entry[key("a", amplitude)] = dict(
                amplitude=amplitude,
                against_linearised_map=_relative_rows(a[1:], mapped),
                against_exact=_relative_rows(a[1:], exact),
                accounting=accounting(run),
            )
        out[f"L{L}_n{mode}"] = dict(record_s=record, dt_s=0.05, by_amplitude=entry)
    return out


def _mode_study(
    K, D, n_nodes, mode, record, dts, *, d=D_RATIO, path=None, fractions=(1 / 3, 2 / 3)
):
    """One single-mode start at every dt: the linearised map's agreement, the dt-study rule
    against the exact propagator with its orders, and, with a path (the item's metric path), the
    controls of all five parameters (k, a, b, D_U, D_V) at each judged dt, the item's engine
    values, reference and tolerances (so a later control needs no engine run) and the mode's
    structure (mode_structure). Returns (entry, the first dt's coefficients and run)."""
    from validation.reactions import chain_reference as cr

    entry, values, accounts = dict(record_s=record), [], {}
    for dt in dts:
        a, run = _single_mode(n_nodes, mode, dt, record, d=d, fractions=fractions)
        mapped, exact = _linear_references(a, run["times"], K, D, n_nodes, mode, dt)
        values.append(a[1:])
        accounts[dt] = (a, run, exact)
        entry[dt_key(dt)] = dict(
            against_linearised_map=_relative_rows(a[1:], mapped),
            against_exact=_relative_rows(a[1:], exact),
            accounting=accounting(run),
        )
    a0, times = accounts[dts[0]][0][0], accounts[dts[0]][1]["times"]
    truth = accounts[dts[0]][2]
    scale = float(np.max(np.abs(truth)))
    rule, tolerances = dt_rule(values, truth, scale)
    entry["dt_rule"] = rule
    if path is not None:
        lam = _lam(n_nodes, mode)

        def exact_with(Kx, Dx):
            return np.asarray(
                [np.asarray(cr.mode_propagator(Kx, Dx, lam, t)) @ a0 for t in times[1:]]
            )

        perturbed = dict(
            k=lambda x: exact_with(K * (1 + x), D),
            a=lambda x: exact_with(schnakenberg_rates(d, A * (1 + x), B)[0], D),
            b=lambda x: exact_with(schnakenberg_rates(d, A, B * (1 + x))[0], D),
            D_U=lambda x: exact_with(K, D * np.asarray([1 + x, 1.0])),
            D_V=lambda x: exact_with(K, D * np.asarray([1.0, 1 + x])),
        )
        for i, tolerance in tolerances.items():
            entry["dt_rule"][dt_key(dts[i])]["controls"] = controls(
                f"{path}.{dt_key(dts[i])}",
                values[i],
                tolerance,
                perturbed,
                rule[dt_key(dts[i])]["passes"],
            )
        entry["arrays"] = dict(
            records_s=[float(x) for x in times[1:]],
            start=np.asarray(a0).tolist(),
            truth=np.asarray(truth).tolist(),
            engine={dt_key(dt): np.asarray(v).tolist() for dt, v in zip(dts, values, strict=True)},
            tolerances={dt_key(dts[i]): np.asarray(v).tolist() for i, v in tolerances.items()},
        )
        entry["mode_structure"] = mode_structure(K, D, n_nodes, mode, a0, times[1:], d=d)
    errors = [entry[dt_key(dt)]["against_exact"] for dt in dts]
    entry["exact_ratios"] = [errors[i] / errors[i + 1] for i in range(len(errors) - 1)]
    return entry, accounts[dts[0]][:2]


def mode_structure(K, D, n_nodes, mode, a0, records, *, d=D_RATIO):
    """The mode's 2 x 2 system K - lambda_n D: its eigenvalues, the fast (more negative)
    component's weight against the slow one in the start and at the first record (in the
    eigenbasis), and each parameter's log-sensitivity of the slow eigenvalue times the last
    record (|d lambda_slow / d ln p| t), which sets the size of a control's effect."""
    lam = _lam(n_nodes, mode)

    def eigen(Kx, Dx):
        values, vectors = np.linalg.eig(Kx - lam * np.diag(Dx))
        order = np.argsort(values.real)  # [fast, slow]
        return values[order], vectors[:, order]

    values, vectors = eigen(K, D)
    complex_pair = bool(np.any(np.abs(values.imag) > 0))
    weights = np.linalg.solve(vectors, np.asarray(a0, dtype=complex))
    out = dict(
        eigenvalues_per_s=[[float(v.real), float(v.imag)] for v in values],
        complex_pair=complex_pair,
    )
    if not complex_pair:
        ratio = abs(weights[0]) / max(abs(weights[1]), 1e-300)
        out["fast_over_slow_at_start"] = float(ratio)
        out["fast_over_slow_at_first_record"] = float(
            ratio * np.exp((values[0].real - values[1].real) * records[0])
        )
    step = 1e-6
    perturbed = dict(
        k=(K * (1 + step), D),
        a=(schnakenberg_rates(d, A * (1 + step), B)[0], D),
        b=(schnakenberg_rates(d, A, B * (1 + step))[0], D),
        D_U=(K, D * np.asarray([1 + step, 1.0])),
        D_V=(K, D * np.asarray([1.0, 1 + step])),
    )
    out["slow_log_sensitivity_times_record"] = {
        name: float(abs(eigen(*pair)[0][1].real - values[1].real) / step * records[-1])
        for name, pair in perturbed.items()
    }
    return out


def part_q1(quick):
    """Single-mode starts against the linearised engine-order map and the exact mode propagator
    (the dt-study rule, its orders, and the five parameters' controls)."""
    K, D = schnakenberg_rates()
    dts = DTS[:2] if quick else DTS
    out = {}
    for L in (11,) if quick else (6, 11, 16):
        n_nodes = DOMAINS[L]
        out[key("L", L)] = {
            f"n{n}": _mode_study(
                K,
                D,
                n_nodes,
                n,
                record_time(K, D, n_nodes, n, cap=100.0 if quick else 600.0),
                dts,
                path=f"q1.{key('L', L)}.n{n}",
            )[0]
            for n in ((1, 2, 3) if quick else (1, 2, 3, 4, 5, 6))
        }
    return out


def _noise_run(L, seed, end, dt, *, every=50.0):
    times, stop = grid_times(dt, [every * i for i in range(1, int(end / every) + 1)], end)
    raw = chain_world(noise_profile(DOMAINS[L], seed), dt=dt, end=stop, observation_times=times)
    return run_chain(raw, uniform_mM())


def part_q2(quick):
    """L/l = 8: no admissible unstable mode; the deviation from uniform decays, its slowest mode at
    the slowest admissible rate."""
    from validation.reactions import chain_reference as cr

    end = 600.0 if quick else 1500.0
    run = _noise_run(8, SEEDS["q2"], end, 0.05)
    K, D = schnakenberg_rates()
    n_nodes = DOMAINS[8]
    rates = {n: discrete_rate(K, D, n_nodes, n, 0.05) for n in range(1, n_nodes)}
    slowest = max(rates, key=rates.get)
    a = coefficients(run)
    norm = np.max(np.abs(run["deviation"] / run["volume"]), axis=(1, 2)) / C_STAR_MM
    mode_rate, mode_rms = _fit(run["times"], a[:, 0, slowest], end / 2, end)
    norm_rate, norm_rms = _fit(run["times"], norm, end / 2, end)
    return dict(
        slowest_mode=int(slowest),
        slowest_discrete_time_rate_per_s=rates[slowest],
        slowest_semi_discrete_rate_per_s=continuous_rate(K, D, n_nodes, slowest),
        fitted_rate_of_slowest_mode_per_s=mode_rate,
        rate_relative_difference=_rate_difference(mode_rate, rates[slowest]),
        fit_rms=mode_rms,
        fitted_rate_of_max_deviation_per_s=norm_rate,
        max_deviation_start_of_c_star=float(norm[0]),
        max_deviation_end_of_c_star=float(norm[-1]),
        max_deviation_never_above_start=bool(np.all(norm <= norm[0])),
        dominant_mode_at_end=int(cr.dominant_mode(run["deviation"][-1] / run["volume"])),
        accounting=accounting(run),
    )


def part_q3(quick):
    """L/l = 6, 11, 16 from seeded noise: the only admissible unstable mode dominates; its growth
    rate in the linear phase (from 100 s until it reaches 1e-2 c*)."""
    from validation.reactions import turing_reference as tu

    J = np.asarray(tu.schnakenberg_jacobian(A, B))
    spacing = SPACING_M / length_scale_m()
    K, D = schnakenberg_rates()
    end = 1500.0 if quick else 3000.0
    out = {}
    for L in (6, 11) if quick else (6, 11, 16):
        run = _noise_run(L, SEEDS["q3"][L], end, 0.05)
        n_nodes = DOMAINS[L]
        expected = tu.fastest_admissible_mode(J, 1.0, D_RATIO, L, spacing=spacing)
        u = np.abs(coefficients(run)[:, 0, :])
        dominant = [int(np.argmax(row[1:]) + 1) for row in u]
        times = run["times"]
        linear = times[u[:, expected] <= 1e-2 * C_STAR_MM]
        stop = float(linear[-1]) if len(linear) else 0.0
        rate, rms = _fit(times, u[:, expected], 100.0, stop)
        other = [t for t, m in zip(times, dominant, strict=True) if m != expected]
        out[key("L", L)] = dict(
            expected_mode=int(expected),
            dominant_by_record=dominant,
            record_times_s=times.tolist(),
            dominant_from_s=float(max(other) + 50.0) if other else 0.0,
            dominant_at_end=dominant[-1],
            fit_window_s=[100.0, stop],
            fitted_rate_per_s=rate,
            fit_rms=rms,
            semi_discrete_rate_per_s=continuous_rate(K, D, n_nodes, expected),
            discrete_time_rate_per_s=discrete_rate(K, D, n_nodes, expected, 0.05),
            rate_relative_difference=_rate_difference(
                rate, discrete_rate(K, D, n_nodes, expected, 0.05)
            ),
            saturated_amplitude_of_c_star=float(
                np.max(np.abs(run["deviation"][-1, 0] / run["volume"])) / C_STAR_MM
            ),
            accounting=accounting(run),
        )
    return out


Q4_FIT_TOLERANCE = 1e-2  # Q3's relative fit tolerance (the lead's ruling 5: the simplest one).


def q4_near_ties(predicted, tolerance=Q4_FIT_TOLERANCE):
    """The near-tie rule (the lead's ruling 5), from the references' discrete-time rates alone:
    {mode: rate}. The fastest two candidates are a near tie when their gap is below
    2 x tolerance x the larger |rate| (each fitted rate may be off by tolerance relative). Returns
    (near_tie, gap, the gap over that allowance, the smallest |rate| over tolerance x the largest
    |rate|: the sign margin, reported)."""
    rates = sorted(predicted.values(), reverse=True)
    top = max(abs(r) for r in rates)
    gap = rates[0] - rates[1] if len(rates) > 1 else None
    allowance = 2 * tolerance * max(abs(rates[0]), abs(rates[1])) if gap is not None else None
    sign = min(abs(r) for r in rates) / (tolerance * top)
    return (
        bool(gap is not None and gap < allowance),
        gap,
        None if gap is None else gap / allowance,
        sign,
    )


def q4_verdict(points, tolerance=Q4_FIT_TOLERANCE):
    """Q4's verdict over its points: every length agrees, near ties excluded up front (each
    point's predicted_discrete_time_rates_per_s, from the references)."""
    excluded, summary = [], dict(smallest_gap_over_allowance=None, smallest_sign_margin=None)
    agree = True
    for point in points:
        predicted = {int(n): r for n, r in point["predicted_discrete_time_rates_per_s"].items()}
        tie, gap, over, sign = q4_near_ties(predicted, tolerance)
        if tie:
            excluded.append(point["L"])
        elif not point["agrees"]:
            agree = False
        if over is not None and (
            summary["smallest_gap_over_allowance"] is None
            or over < summary["smallest_gap_over_allowance"]
        ):
            summary.update(smallest_gap_over_allowance=over, smallest_gap_L=point["L"], gap=gap)
        if summary["smallest_sign_margin"] is None or sign < summary["smallest_sign_margin"]:
            summary.update(smallest_sign_margin=sign, smallest_sign_margin_L=point["L"])
    return dict(all_agree_outside_near_ties=bool(agree), near_ties_excluded=excluded, **summary)


def part_q4(quick):
    """The staircase: single-mode starts on L/l in [4, 30] (step 0.5) for every mode whose discrete
    k^2 lies in [0.1, 0.7] l^-2 (real eigenvalues; at least two modes); the fastest-growing on the
    engine against the discrete argmax of sigma_n, the growing set against the admissible one."""
    from validation.reactions import turing_reference as tu

    J = np.asarray(tu.schnakenberg_jacobian(A, B))
    spacing = SPACING_M / length_scale_m()
    end, dt = 100.0, 0.05
    out = []
    for L in (4.0, 6.0, 8.0, 11.0) if quick else STAIRCASE:
        n_nodes = int(round(L / spacing))
        k2 = {n: _lam(n_nodes, n) * length_scale_m() ** 2 for n in range(1, n_nodes)}
        candidates = sorted(n for n, v in k2.items() if 0.1 <= v <= 0.7)
        while len(candidates) < 2:
            candidates = sorted(set(candidates) | {max(candidates or [0]) + 1})
        expected = tu.fastest_admissible_mode(J, 1.0, D_RATIO, L, spacing=spacing)
        admissible = _modes(tu.admissible_unstable_modes(J, 1.0, D_RATIO, L, spacing=spacing))
        rates, cost = {}, 0.0
        for n in candidates:
            times, stop = grid_times(dt, [10.0 * i for i in range(1, 10)], end)
            raw = chain_world(mode_profile(n_nodes, n), dt=dt, end=stop, observation_times=times)
            run = run_chain(raw, uniform_mM())
            norm = np.max(np.abs(coefficients(run, n)), axis=1)
            rates[n] = _fit(run["times"], norm, 50.0, end)[0]
            cost += run["wall_s"]
        growing = sorted(n for n, r in rates.items() if r > 0)
        fastest = max(growing, key=rates.get) if growing else None
        K, D = schnakenberg_rates()
        predicted = {n: discrete_rate(K, D, n_nodes, n, dt) for n in candidates}
        order = sorted(predicted.values(), reverse=True)
        point = dict(
            L=L,
            nodes=n_nodes,
            candidates=candidates,
            rates_per_s={str(n): r for n, r in rates.items()},
            predicted_discrete_time_rates_per_s={str(n): r for n, r in predicted.items()},
            smallest_predicted_abs_rate_per_s=min(abs(r) for r in predicted.values()),
            predicted_top_two_gap_per_s=order[0] - order[1] if len(order) > 1 else None,
            engine_fastest=fastest,
            discrete_argmax=expected,
            engine_growing=growing,
            admissible_unstable=admissible,
            agrees=bool(fastest == expected and growing == admissible),
            wall_s=cost,
        )
        out.append(point)
        if OUTPUT:  # Each point as it finishes (a long part).
            with (Path(OUTPUT) / "q4_points.jsonl").open("a") as sink:
                sink.write(json.dumps(plain(point)) + "\n")
        import jax

        jax.clear_caches()  # Each chain size compiles its own programs; keep memory bounded.
    return dict(
        points=out,
        all_agree=bool(all(p["agrees"] for p in out)),
        disagreements=[p["L"] for p in out if not p["agrees"]],
        fit_tolerance=Q4_FIT_TOLERANCE,
        **q4_verdict(out),
    )


def part_q5(quick):
    """The subcritical control: d = 8 < d_c. Single-mode starts decay, at their predicted rates:
    the dt-study rule against the exact propagator at d = 8 (dt 0.05 and 0.025), and the fitted
    rate beside the engine order's discrete-time rate."""
    K, D = schnakenberg_rates(SUBCRITICAL)
    out = {}
    for L in (11,) if quick else (6, 8, 11, 16):
        n_nodes = DOMAINS[L]
        per = {}
        for n in (1, 2, 3) if quick else (1, 2, 3, 4, 5, 6):
            record = record_time(K, D, n_nodes, n, cap=300.0 if quick else 600.0)
            entry, (a, run) = _mode_study(
                K,
                D,
                n_nodes,
                n,
                record,
                DTS[:2],
                d=SUBCRITICAL,
                fractions=(0.4, 0.5, 0.6, 0.7, 0.8, 0.9),  # The fit's records, past the transient.
            )
            norm = np.max(np.abs(a), axis=1)
            rate, rms = _fit(run["times"], norm, 0.35 * record, 1.01 * record)
            entry.update(
                predicted_rate_per_s=discrete_rate(K, D, n_nodes, n, 0.05),
                fitted_rate_per_s=rate,
                rate_relative_difference=_rate_difference(
                    rate, discrete_rate(K, D, n_nodes, n, 0.05)
                ),
                fit_rms=rms,
                decays=bool(norm[-1] < norm[0]),
            )
            per[f"n{n}"] = entry
        out[key("L", L)] = per
    return out


def _schnakenberg_network(k=RATE_K, a=A, b=B):
    from validation.reactions import turing_reference as tu

    return tu.schnakenberg_network(a, b, k, C_STAR_MM)


def part_q6(quick):
    """The nonlinear pattern on L/l = 11 against cr.integrate_chain (DOP853 at rtol 1e-13; its own
    term |rtol 1e-12 - rtol 1e-13|): the dt-study rule per node, species and record, its orders,
    and the five parameters' controls (the reference re-integrated with each perturbed, the
    smallest caught delta bisected on the 1-2-5 grid from 1e-9 to 1e-1); the engine values,
    reference and tolerances stored."""
    from validation.reactions import chain_reference as cr

    n_nodes = DOMAINS[11]
    end = 1000.0 if quick else 3000.0
    every = 250.0
    dts = DTS[:2] if quick else DTS
    profile = noise_profile(n_nodes, SEEDS["q6"])
    records, _ = grid_times(0.05, [every * i for i in range(1, int(end / every) + 1)], end)
    raw = chain_world(profile, end=end, observation_times=records)
    net = rfx.reference_network(raw)
    amounts, _ = rfx.reference_amounts(raw)
    nodes = [n["id"] for n in rfx.reference_nodes(raw)]
    chain = [nodes.index(f"node_{i}") for i in range(n_nodes)]
    D = np.asarray([D_U, D_RATIO * D_U])
    started = time.perf_counter()

    def integrate(network, diffusivities, rtol):
        traj = cr.integrate_chain(
            network, amounts[:, chain], VOLUME_PL, SPACING_M, diffusivities, records, rtol=rtol
        )
        return np.asarray(traj.amounts)[1:] / VOLUME_PL  # [record, S, N] mM, after the start.

    coarse, ref = integrate(net, D, 1e-12), integrate(net, D, 1e-13)
    out = dict(
        reference_rtol_difference_of_c_star=float(np.max(np.abs(coarse - ref))) / C_STAR_MM,
        reference_s=time.perf_counter() - started,
        record_times_s=list(records),
        amplitude_end_of_c_star=float(np.max(np.abs(ref[-1, 0] - np.mean(ref[-1, 0])))) / C_STAR_MM,
    )
    values = []
    for dt in dts:
        times, stop = grid_times(dt, records[1:-1], end)
        run = run_chain(
            chain_world(profile, dt=dt, end=stop, observation_times=times), uniform_mM()
        )
        engine = run["amount"][1:] / VOLUME_PL
        values.append(engine)
        error = np.max(np.abs(engine - ref), axis=(1, 2)) / C_STAR_MM
        out[dt_key(dt)] = dict(
            max_error_of_c_star=float(np.max(error)),
            error_by_record_of_c_star=error.tolist(),
            dominant_mode_at_end=int(np.argmax(np.abs(coefficients(run)[-1, 0, 1:])) + 1),
            accounting=accounting(run),
        )
    rule, tolerances = dt_rule(values, ref, float(np.max(np.abs(ref))), np.abs(coarse - ref))
    out["dt_rule"] = rule
    grid = Q6_GRID_QUICK if quick else Q6_GRID
    started, cache = time.perf_counter(), {}

    def perturbed(kind, x):  # Each perturbed reference integrated once, for every judged dt.
        if (kind, x) not in cache:
            network = {
                "k": lambda: _schnakenberg_network(k=RATE_K * (1 + x)),
                "a": lambda: _schnakenberg_network(a=A * (1 + x)),
                "b": lambda: _schnakenberg_network(b=B * (1 + x)),
            }.get(kind, lambda: net)()
            scale = {"D_U": [1 + x, 1.0], "D_V": [1.0, 1 + x]}.get(kind, [1.0, 1.0])
            cache[kind, x] = integrate(network, D * np.asarray(scale), 1e-12)
        return cache[kind, x]

    for i, tolerance in tolerances.items():
        rule[dt_key(dts[i])]["controls"] = controls(
            f"q6.{dt_key(dts[i])}",
            values[i],
            tolerance,
            {kind: (lambda x, kind=kind: perturbed(kind, x)) for kind in PARAMETERS},
            rule[dt_key(dts[i])]["passes"],
            grid,
            bisect=True,
        )
    out["controls_s"] = time.perf_counter() - started
    out["controls_grid"] = list(grid)
    out["controls_integrations"] = len(cache)
    out["arrays"] = dict(
        records_s=[float(x) for x in records[1:]],
        truth=np.asarray(ref).tolist(),
        reference_term=np.abs(coarse - ref).tolist(),
        engine={dt_key(dt): np.asarray(v).tolist() for dt, v in zip(dts, values, strict=True)},
        tolerances={dt_key(dts[i]): np.asarray(v).tolist() for i, v in tolerances.items()},
    )
    errors = [out[dt_key(dt)]["max_error_of_c_star"] for dt in dts]
    out["ratios"] = [errors[i] / errors[i + 1] for i in range(len(errors) - 1)]
    return out


FRESH = """
import json, sys
import jax
jax.config.update("jax_enable_x64", True)
import numpy as np
from cells.execution.runner import run
from cells.records.io import load_snapshot
loaded = load_snapshot(sys.argv[1])
result = run(loaded.spec, loaded.checkpoint)
np.savez(sys.argv[2], **{k: np.asarray(v) for k, v in result.history._asdict().items()})
print(json.dumps(dict(start=int(loaded.checkpoint.step_index))))
"""


def part_q7(quick, output):
    """Accounting: the face-free world at rounding; restart through a written snapshot read in a
    fresh process, bitwise; a vector batch over seeds on one domain (each world within 1e-12 of
    its scalar run; bitwise against the reversed batch). Every other part's ledgers are in its own
    accounting records."""
    from cells.definitions.specs import parse_spec
    from cells.execution.batch import BatchSpec, WorldSpec
    from cells.execution.runner import run
    from cells.execution.vector_windows import run_vector_windowed
    from cells.execution.windows import WindowPolicy
    from cells.records.io import write_snapshot

    n_nodes = DOMAINS[6]
    out = {}
    # The face-free world (§3.4 guard 1, for MG0c's network): every node isolated.
    end = 20.0 if quick else 200.0
    times, stop = grid_times(0.05, [end / 2], end)
    raw = chain_world(
        noise_profile(n_nodes, SEEDS["q7_face_free"]),
        dt=0.05,
        end=stop,
        observation_times=times,
        faces=False,
    )
    out["face_free"] = accounting(run_chain(raw, uniform_mM(), every_row=True))
    # Restart through a written snapshot, read back in a fresh process.
    end = 10.0 if quick else 50.0
    times, stop = grid_times(0.05, [end / 2], end)
    spec = parse_spec(
        chain_world(
            noise_profile(n_nodes, SEEDS["q7_restart"]), dt=0.05, end=stop, observation_times=times
        )
    )
    full = run(spec)
    checkpoint = full.checkpoint_at(times[1])
    folder = Path(output) / "q7_snapshot"
    folder.mkdir(parents=True, exist_ok=True)
    write_snapshot(folder / "checkpoint", full.spec, checkpoint)
    env = dict(
        os.environ,
        PYTHONPATH=os.pathsep.join([str(ROOT / "src"), str(ROOT)]),
        JAX_ENABLE_X64="1",
        JAX_PLATFORMS="cpu",
    )
    done = subprocess.run(
        [sys.executable, "-B", "-c", FRESH, str(folder / "checkpoint"), str(folder / "h.npz")],
        capture_output=True,
        text=True,
        env=env,
        timeout=3600,
        check=False,
    )
    if done.returncode != 0:
        raise RuntimeError(done.stderr[-2000:])
    fresh = np.load(folder / "h.npz")
    start = json.loads(done.stdout.strip().splitlines()[-1])["start"]
    history = full.history._asdict()
    out["restart_step"] = int(start)
    out["restart_bitwise"] = bool(
        start == checkpoint.step_index
        and all(fresh[k].tobytes() == np.asarray(v)[start:].tobytes() for k, v in history.items())
    )
    # A vector batch over seeds on one domain: domains differ in their routes, which are part of
    # the batch signature, so they cannot share a batch (§6.4's Q7 reads "a vmap batch of the
    # domains"; a question for the lead).
    end = 10.0 if quick else 100.0
    specs = [
        parse_spec(chain_world(noise_profile(n_nodes, s), end=end, observation_times=[0.0, end]))
        for s in SEEDS["q7_batch"]
    ]

    def batch(order):
        worlds = tuple(WorldSpec(i + 1, specs[j]) for i, j in enumerate(order))
        return run_vector_windowed(
            BatchSpec(worlds, len(worlds), 10**7, 2**32), WindowPolicy(500, "checkpoints")
        )

    forward, backward = batch([0, 1, 2]), batch([2, 1, 0])
    bitwise, worst, zero_scale = True, 0.0, 0.0
    for k, s in enumerate(specs):
        final = forward.worlds[k + 1].final.state
        bitwise &= all(
            np.asarray(a).tobytes() == np.asarray(b).tobytes()
            for a, b in zip(final, backward.worlds[3 - k].final.state, strict=True)
        )
        single = run(s).history
        for name in type(final)._fields:
            a, b = np.asarray(getattr(final, name)), np.asarray(getattr(single, name))[-1]
            if a.dtype.kind != "f":
                bitwise &= a.tobytes() == b.tobytes()
                continue
            scale = float(np.max(np.abs(b), initial=0.0))
            if scale > 0:
                worst = max(worst, float(np.max(np.abs(a - b))) / scale)
            else:
                zero_scale = max(zero_scale, float(np.max(np.abs(a), initial=0.0)))
    out["batch_bitwise_against_reverse"] = bool(bitwise)
    out["batch_against_scalar_relative"] = worst
    out["batch_zero_fields_max_abs"] = zero_scale
    out["batch_worlds"] = len(specs)
    return out


def part_sites(quick):
    """Reactions at several sites with different multipliers on the chain (per-site schedules; one
    site at zero; node_0 on its reaction's schedule) against cr.integrate_chain with the same
    [R, N] multipliers (rtol 1e-13; its own term from 1e-12): the dt-study rule and its orders."""
    from validation.reactions import chain_reference as cr

    n_nodes = 12
    shape = np.asarray(cr.mode_basis(n_nodes))
    sited = {("make", f"node_{i}"): float(1.0 + 0.5 * shape[1][i]) for i in range(1, n_nodes)}
    sited[("make", "node_3")] = 0.0
    sited[("clear", "node_7")] = 2.0
    world = open_pair(sited)
    base = world["base_mM"]
    profile = {s: c * (1.0 + 0.05 * shape[2]) for s, c in base.items()}
    end = 20.0 if quick else 100.0
    records, _ = grid_times(0.05, [end / 4, end / 2, 3 * end / 4], end)
    raw = chain_world(
        profile, network=world["network"], diffusivities=world["diffusivities"], end=end
    )
    net = rfx.reference_network(raw)
    reactions = [r.name for r in net.reactions]
    multipliers = np.ones((len(reactions), n_nodes))
    for (reaction, node), value in sited.items():
        multipliers[reactions.index(reaction), int(node.split("_")[1])] = value
    amounts, _ = rfx.reference_amounts(raw)
    nodes = [n["id"] for n in rfx.reference_nodes(raw)]
    chain = [nodes.index(f"node_{i}") for i in range(n_nodes)]
    D = np.asarray([world["diffusivities"][s] for s in ("A", "B")])

    def integrate(rtol):
        traj = cr.integrate_chain(
            net,
            amounts[:, chain],
            VOLUME_PL,
            SPACING_M,
            D,
            records,
            multipliers=multipliers,
            rtol=rtol,
        )
        return np.asarray(traj.amounts)[1:]

    coarse, ref = integrate(1e-12), integrate(1e-13)
    out = dict(multipliers=multipliers.tolist())
    dts = DTS[:2] if quick else DTS
    values = []
    for dt in dts:
        times, stop = grid_times(dt, records[1:-1], end)
        raw = chain_world(
            profile,
            network=world["network"],
            diffusivities=world["diffusivities"],
            dt=dt,
            end=stop,
            observation_times=times,
        )
        run = run_chain(raw, base)
        values.append(run["amount"][1:])
        out[dt_key(dt)] = dict(
            max_error_relative=float(np.max(np.abs(run["amount"][1:] - ref)) / np.max(np.abs(ref))),
            accounting=accounting(run),
        )
    out["dt_rule"], _ = dt_rule(values, ref, float(np.max(np.abs(ref))), np.abs(coarse - ref))
    errors = [out[dt_key(dt)]["max_error_relative"] for dt in dts]
    out["ratios"] = [errors[i] / errors[i + 1] for i in range(len(errors) - 1)]
    return out


def part_d147(quick):
    """D147's solver check (the coordinator's milestone-3 addition, before the protocol's draft):
    validation/tissue/field_solver_choice.free_field_offsets(raw), the declared field solver and
    solver_for(raw)'s automatic choice for every MG0c world definition. Since D156 a composite
    follows its inner model (@3, in D147's family), so the automatic choice applies to these
    worlds: @3 with a free offset, the declared solver without one. A floating capacitor component
    (one with no held bath) is a free offset; every chain node shares the cell's capacitor
    component with the held bath."""
    from validation.tissue import field_solver_choice as fsc

    spacing = SPACING_M / length_scale_m()
    sizes = sorted({*DOMAINS.values(), *(int(round(L / spacing)) for L in STAIRCASE)})
    worlds = [(f"schnakenberg_chain_N{n}", chain_world(mode_profile(n, 1))) for n in sizes]
    worlds.append(("subcritical_chain_N22", chain_world(mode_profile(22, 1), d=SUBCRITICAL)))
    worlds.append(("face_free_N12", chain_world(noise_profile(12, 5), faces=False)))
    sited = {("make", "node_3"): 0.0, ("clear", "node_7"): 2.0}
    for label, world in (
        ("passive_pair", passive_pair()),
        ("open_pair", open_pair()),
        ("sites_open_pair", open_pair(sited)),
    ):
        profile = {s: [c] * 12 for s, c in world["base_mM"].items()}
        raw = chain_world(profile, network=world["network"], diffusivities=world["diffusivities"])
        worlds.append((f"{label}_N12", raw))
    worlds.append(("ions_only_chain_N12", chain_world({}, n_nodes=12)))
    worlds.append(("several_sites_face_free", rfx.several_sites()))
    records = [
        dict(
            world=label,
            model=raw["model"]["id"],
            free_field_offsets=fsc.free_field_offsets(raw),
            declared_field_solver=raw["execution"]["field_solver"],
            solver_for_auto=fsc.solver_for(raw),
        )
        for label, raw in worlds
    ]
    return dict(
        worlds=records,
        count=len(records),
        max_free_field_offsets=max(r["free_field_offsets"] for r in records),
        declared_field_solvers=sorted({r["declared_field_solver"] for r in records}),
    )


PARTS = dict(
    d147=part_d147,
    timing=part_timing,
    theory=part_theory,
    linear=part_linear,
    floor=part_floor,
    q1=part_q1,
    q2=part_q2,
    q3=part_q3,
    q4=part_q4,
    q5=part_q5,
    q6=part_q6,
    q7=part_q7,
    sites=part_sites,
)


def plain(value):
    """JSON-ready values: arrays, NumPy scalars and booleans, tuples."""
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    if isinstance(value, np.ndarray):
        return plain(value.tolist())
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    return value


def snapshot_identity(root=ROOT):
    """The execution snapshot's identity at root (D150's shape): every judged run and verdict
    carries it, so the judge and combine compare like with like."""
    snapshot = json.loads((Path(root) / "SNAPSHOT.json").read_text())
    return dict(
        kind="snapshot",
        git_revision=snapshot.get("git_revision"),
        patch_sha256=snapshot.get("patch_sha256"),
        status=snapshot.get("status"),
    )


def source_identity(root=ROOT):
    """The run's source: a frozen snapshot's identity (snapshot_identity), or the checkout's
    revision and status."""
    if (Path(root) / "SNAPSHOT.json").exists():
        return snapshot_identity(root)

    from validation import executed_sources  # noqa: PLC0415
    executed_sources.refuse_untracked(root, "mg0c_turing's source record")  # D259

    def git(*args):
        done = subprocess.run(
            ["git", "-C", str(root), *args], capture_output=True, text=True, check=False
        )
        return done.stdout.strip()

    return dict(
        kind="checkout",
        root=str(root),
        git_revision=git("rev-parse", "HEAD"),
        dirty=git("status", "--porcelain"),
    )


def judged_run_refusal(protocol, root=ROOT):
    """Why a judged entry may not start (None: it may): an unregistered protocol (its status, and a
    registration record matching it), or a source that is not a clean execution snapshot (D150's
    and Rm1's guard)."""
    status = protocol.get("status")
    if not (isinstance(status, str) and status.lower().startswith("registered")):
        return "the MG0c protocol is not registered (its status does not begin 'registered')"
    record = protocol.get("registration")
    if not (isinstance(record, dict) and record.get("status") == status):
        return "the MG0c protocol's registration record is missing or does not match its status"
    manifest = Path(root) / "SNAPSHOT.json"
    if not manifest.exists():
        return "a judged run comes from a clean execution snapshot of main, not a checkout"
    snapshot = json.loads(manifest.read_text())
    clean = snapshot.get("patch_sha256") == hashlib.sha256(b"").hexdigest()
    if snapshot.get("status") != "complete" or not clean:
        return "the execution snapshot is incomplete or carries uncommitted changes"
    return None


def registered(protocol_path, output, root=ROOT):
    """The protocol, or SystemExit("Refused: ...") before anything is computed or written: unless
    it is registered, the source is a clean execution snapshot and the output directory is new (each
    attempt writes its own; D150's attempt rule). Every judged entry calls it first."""
    protocol = json.loads(Path(protocol_path).read_text())
    refusal = judged_run_refusal(protocol, root)
    if refusal is None and Path(output).exists():
        refusal = "the output directory exists (each attempt writes its own)"
    if refusal:
        raise SystemExit("Refused: " + refusal)
    return protocol


def judge(protocol_path, output, results_paths, root=ROOT):
    """The parts' verdict (no runs here): the judged runs' results.json merged and evaluated by
    mg0a_gradient.evaluate into OUTPUT/verdict.json (MG0b's judge form). Refused before anything is
    written, by the guard, and unless every results file is a judged run of this protocol from the
    snapshot at root, complete (every requested part has run: an incomplete run is an
    infrastructure ending, its unit rerun once from the same snapshot), with every part of the
    protocol in exactly one run."""
    protocol = registered(protocol_path, output, root)
    source = snapshot_identity(root)
    parts, runs = {}, []
    for path in results_paths:
        data = json.loads(Path(path).read_text())
        if data.get("status") != "Judged run of " + protocol["id"] or data.get("quick"):
            raise SystemExit(f"Refused: {path} is not a judged run of {protocol['id']}")
        if data.get("source") != source:
            raise SystemExit(
                f"Refused: {path} comes from another source than the snapshot at {root}"
            )
        requested = data.get("requested_parts") or []
        if not data.get("complete") or sorted(data["parts"]) != sorted(requested):
            raise SystemExit(
                f"Refused: {path} is incomplete, an infrastructure ending (rerun its unit once "
                "from the same snapshot into a new directory); no verdict is written"
            )
        for name, value in data["parts"].items():
            if name in parts:
                raise SystemExit(f"Refused: part {name} is in more than one judged run")
            parts[name] = value
        runs.append(dict(path=str(path), parts=sorted(data["parts"])))
    missing = sorted(set(protocol["judged_parts"]) - set(parts))
    if missing:
        raise SystemExit(f"Refused: the judged runs lack parts {missing}; no verdict is written")
    results = dict(parts=parts)
    results["accounting_summary"] = accounting_summary(results)
    from validation.tissue import judge_harness  # The empty-metric guard (the review's finding 4).

    judge_harness.refuse(judge_harness.metrics(protocol["criteria"], results))
    verdict = evaluate(protocol, results)
    record = dict(
        item="parts",
        protocol_id=protocol["id"],
        protocol_status=protocol["status"],
        source=source,
        runs=runs,
        criteria=verdict["criteria"],
        passed=verdict["passed"],
    )
    Path(output).mkdir(parents=True)
    (Path(output) / "verdict.json").write_text(json.dumps(plain(record), indent=1) + "\n")
    return record


COUNTS = re.compile(r"(\d+) (passed|failed|errors?|skipped|xfailed|xpassed|deselected)")  # Tiers'.


def _pytest_file(test, root, out):
    """One guard file from root, in the tier runner's environment but with no cap: its exit code
    (negative: ended by a signal), duration and counts (D150's judge-q5)."""
    slug = test.replace("/", "__")
    outputs, evidence = out / "outputs" / slug, out / "evidence" / slug
    outputs.mkdir(parents=True)
    evidence.mkdir(parents=True)
    env = dict(
        os.environ,
        PYTHONPATH=str(root / "src"),
        CUDA_VISIBLE_DEVICES="",
        JAX_ENABLE_X64="1",
        CELLS_OUTPUT_ROOT=str(outputs),
        CELLS_COMPONENT_EVIDENCE=str(evidence),
    )
    log = out / f"{slug}.log"
    command = [sys.executable, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider"]
    command += ["--continue-on-collection-errors", test]
    started = time.monotonic()
    with log.open("w") as handle:
        code = subprocess.run(
            command, cwd=root, env=env, stdout=handle, stderr=subprocess.STDOUT, check=False
        ).returncode
    seconds = round(time.monotonic() - started, 2)
    tail = log.read_text(errors="replace")[-2000:]
    last = [line for line in tail.splitlines() if " in " in line and COUNTS.search(line)]
    counts = {}
    for number, kind in COUNTS.findall(last[-1] if last else ""):
        counts[kind.rstrip("s") if kind.startswith("error") else kind] = int(number)
    return dict(file=test, exit_code=code, seconds=seconds, counts=counts, log=str(log))


def judge_guards(protocol_path, output, root=ROOT):
    """The guards' verdict (rules.judge_entries.guards; D150's judge-q5): the guard first, then
    pytest on the protocol's guards_of_record from the snapshot at root, one file at a time with no
    per-file cap, into OUTPUT/verdict.json (each file's counts, exit code and duration; passed when
    every file exits 0; a test failure or error in a completed file is a verdict). A file whose
    process ends by a signal ends the attempt without a verdict: OUTPUT/infrastructure.json."""
    protocol = registered(protocol_path, output, root)
    out = Path(output).resolve()  # Absolute: each file's process runs from root.
    out.mkdir(parents=True)
    root = Path(root).resolve()
    files = []
    for test in protocol["guards_of_record"]["tests"]:
        files.append(_pytest_file(test, root, out))
        if files[-1]["exit_code"] < 0:
            ending = dict(item="guards", source=snapshot_identity(root), files=files)
            (out / "infrastructure.json").write_text(json.dumps(ending, indent=1) + "\n")
            raise SystemExit(
                f"Infrastructure ending: {test} ended by signal {-files[-1]['exit_code']}; no "
                "verdict is written (the attempt rule: rerun once from the same snapshot)"
            )
    verdict = dict(
        item="guards",
        protocol_id=protocol["id"],
        protocol_status=protocol["status"],
        source=snapshot_identity(root),
        files=files,
        passed=bool(files) and all(f["exit_code"] == 0 for f in files),
    )
    (out / "verdict.json").write_text(json.dumps(verdict, indent=1) + "\n")
    return verdict


def combine(protocol_path, output, parts_output, guards_output, root=ROOT):
    """The one qualification verdict (rules.judge_entries.combined; D150's combine): the guard
    first; then the parts' verdict and the guards' verdict, refused unless both name this protocol
    and the snapshot at root. OUTPUT/verdict.json carries every criterion, the guards' files, the
    scope line and the snapshot's revision; it passes when both passed."""
    protocol = registered(protocol_path, output, root)
    source = snapshot_identity(root)
    verdicts = {}
    for name, where in (("parts", parts_output), ("guards", guards_output)):
        path = Path(where) / "verdict.json"
        if not path.exists():
            raise SystemExit(f"Refused: no {name} verdict at {path}")
        part = json.loads(path.read_text())
        if (part.get("protocol_id"), part.get("protocol_status")) != (
            protocol["id"],
            protocol["status"],
        ):
            raise SystemExit(f"Refused: the {name} verdict is not this protocol's")
        if part.get("source") != source:
            raise SystemExit(f"Refused: the {name} verdict comes from another source than {root}")
        verdicts[name] = (part, str(path))
    (a, a_path), (b, b_path) = verdicts["parts"], verdicts["guards"]
    keep = ("file", "exit_code", "seconds", "counts")
    verdict = dict(
        kind="cells.mg0c_qualification_verdict@1",
        protocol_id=protocol["id"],
        protocol_status=protocol["status"],
        scope=protocol["scope"],
        source=source,
        snapshot_revision=source["git_revision"],
        criteria=a["criteria"],
        guards=dict(passed=b["passed"], files=[{k: f[k] for k in keep} for f in b["files"]]),
        passed=bool(a["passed"] and b["passed"]),
        not_judged=protocol["reported_not_judged"],
        verdicts=dict(parts=a_path, guards=b_path),
    )
    Path(output).mkdir(parents=True)
    (Path(output) / "verdict.json").write_text(json.dumps(plain(verdict), indent=1) + "\n")
    return verdict


def main(argv=None):
    import jax

    jax.config.update("jax_enable_x64", True)
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("parts", nargs="+")
    parser.add_argument("--output", required=True)
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--protocol")
    parser.add_argument("--results", nargs="*", default=[])
    args = parser.parse_args(argv)
    entries = {"judge", "judge-guards", "combine"}
    if args.parts and args.parts[0] in entries:
        if len(args.parts) != 1 or not args.protocol:
            raise SystemExit(f"{args.parts[0]} takes --protocol and --output alone")
        if args.parts == ["judge"]:
            if not args.results:
                raise SystemExit("judge takes --results (the judged runs' results.json)")
            verdict = judge(args.protocol, args.output, args.results)
        elif args.parts == ["judge-guards"]:
            verdict = judge_guards(args.protocol, args.output)
        else:
            if len(args.results) != 2:
                raise SystemExit("combine takes --results PARTS_OUTPUT GUARDS_OUTPUT")
            verdict = combine(args.protocol, args.output, *args.results)
        print(args.parts[0], "pass" if verdict["passed"] else "fail", flush=True)
        return 0 if verdict["passed"] else 1
    protocol = None
    if args.protocol:
        protocol = registered(args.protocol, args.output)
        REGISTERED_DELTAS.update(protocol.get("registered_control_deltas", {}))
    parts = list(PARTS) if args.parts == ["all"] else args.parts
    unknown = sorted(set(parts) - set(PARTS))
    if unknown:
        raise SystemExit(f"Unknown parts: {unknown}")
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    global OUTPUT
    OUTPUT = output
    results = dict(
        driver="validation/morphogenesis/mg0c_turing.py",
        status=STATUS if protocol is None else "Judged run of " + protocol["id"],
        quick=args.quick,
        source=source_identity(),
        started_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        requested_parts=list(parts),
        complete=False,  # True once every requested part has run (ok or not).
        parts={},
    )
    path = output / "results.json"
    for name in parts:
        started = time.perf_counter()
        try:
            value = part_q7(args.quick, output) if name == "q7" else PARTS[name](args.quick)
            entry = dict(ok=True, **plain(value))
        except Exception as error:  # Recorded and kept, never repaired: the part fails.
            entry = dict(ok=False, error=repr(error), traceback=traceback.format_exc())
        entry["seconds"] = time.perf_counter() - started
        results["parts"][name] = entry
        results["peak_rss_mb"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
        results["accounting_summary"] = accounting_summary(results)
        path.write_text(json.dumps(results, indent=1, sort_keys=True) + "\n")
        print(name, entry["ok"], round(entry["seconds"], 1), flush=True)
    results["complete"] = True
    path.write_text(json.dumps(results, indent=1, sort_keys=True) + "\n")
    if protocol is not None:  # The verdict is the judge entry's, over every judged run.
        results["verdict"] = "the judge entry's over the merged judged runs, then combine's"
        path.write_text(json.dumps(results, indent=1, sort_keys=True) + "\n")
    return 0 if all(p["ok"] for p in results["parts"].values()) else 1


if __name__ == "__main__":
    sys.exit(main())
