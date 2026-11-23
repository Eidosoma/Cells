"""XC0's engine readings: every value is the engine's own output at a world of xc0_worlds, with no
law of physics written here (no Nernst, Goldman-Hodgkin-Katz, Hill or cycle formula). This module
never reads the references' designs/ files: it builds the engine-only table that the comparison's
reader (xc0_compare.py) judges after the table's digest is recorded.

Three kinds of reading:

1. **At a state.** @3's readouts (`impl.readouts`, the observation path's own evaluation) at a
   world parsed by the engine, its cells at a voltage V set through the charge anchor alone (the
   fixed background, never a concentration; declared_inputs' charge_anchor_rule). For speed the
   anchor of an already parsed definition is replaced in place (`Engine.at`); a full re-parse at
   the same anchor is bitwise the same (checked on invented inputs, and again at every root this
   module returns: `reparsed_equal`). Read there:
   - dV/dt, the field's `membrane_voltage_rate_V_s` at the cell's m_main patch (every patch of a
     cell shares it);
   - an ion's outward flux through one patch, the patch total `membrane_flux_fmol_s[ion, patch]`
     (its constant-field leak, any channel population on it, the pump's and the kinds' patch flux);
     its outward current, z e x that flux (CHARGE_PER_FMOL z J, A);
   - the symporter's mode values from the transporter kind's own probe at the state's read and
     field potentials (x = dG_cyc/RT, S, J, J+, J-).
2. **Roots.** scipy's brentq of one such output over V (or over one concentration, re-parsed),
   in a bracket found by scanning: the engine's zero-current voltage (dV/dt = 0 with the amounts
   fixed, DESIGN C2's reading), an ion's zero (its flux through its single-ion conductor), the
   symporter's stall (J = 0), its equilibrium ratio (J = 0 over B_in), the Cl- threshold (the GlyR
   flux = 0 over Cl_i at the resting voltage). Each root is refined to ROOT_XTOL and re-parsed.
3. **Runs.** cells.execution.runner.run of a world with the X2 energy check at the cap the rule
   names, every accepted step observed (the observation path's readouts), from which a trajectory's
   values are read at the steps or by interpolation between two accepted steps (stated per reading).

The ion's single-ion conductor (DESIGN C1): K+ the m_kleak patch, Na+ the m_main patch's Na flux,
Cl- GlyR on m_glycine (P_REF, availability 1), and the Kir route its own K flux on m_kir.

Usage (cwd = a frozen snapshot root, PYTHONPATH=src:.):
    python -m validation.xenopus_bioelectric.xc0_engine table MANIFEST.json OUT_DIR [--x2-cap C]
writes OUT_DIR/engine_table.json, prints its sha256, and keeps OUT_DIR/run_record.json.
"""

import argparse
import copy
import dataclasses
import hashlib
import json
import math
import platform
import subprocess
import sys
import time
import traceback
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from cells.definitions.specs import ConfigError, parse_spec
from cells.definitions.surface_pump_v3_spec import control_values
from cells.kinds import transporter
from cells.laws.electrochemistry import CHARGE_PER_FMOL
from cells.registry.models import get_model
from validation.xenopus_bioelectric import xc0_worlds as W

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "xenopus_xc0_engine_table@1"
ROOT_XTOL = 1e-16  # V: brentq's absolute tolerance on a voltage root (rtol 4 eps).
SCAN = 24  # Bracket scan points across a root's domain.
V_DOMAIN = (-0.20, 0.15)  # V: the scan for a root with no channel population declared.
CHANNEL_DOMAIN = (-0.12, 0.06)  # V: @3's channel domain, wherever GlyR is declared.
SLOPE_STEP_V = 1e-5  # V: the central difference of dV/dt (or a current) for a slope.
NEWTON_STEPS = 12  # The two-cell steady state's polishing steps at most.
RUN_TAUS = 8.25  # C3's and C7's runs last this many tau_lin (k <= 33 at t = k tau_lin / 4).
P_REF = 1e-8  # m/s: GlyR's permeability where only its zero or a sign is read (any P gives both).
G_REF = 1.0  # S/m2: the route's g_ref where only its zero or a sign is read.
CONDUCTOR = {"K": ("m_kleak", None), "Na": ("m_main", None), "Cl": ("m_glycine", "glycine"),
             "Kir": ("m_kir", "kir")}  # fmt: skip
ION = {"K": "K", "Na": "Na", "Cl": "Cl", "Kir": "K"}


# The run's step factor (1 at the declared dt; the table's companion runs at 1/2, the retry's at 1/2
# and 1/4) and the bracket scan's points (doubled in the retry). Set by build_table only.
STEP = {"factor": 1.0}
SCAN_POINTS = {"n": SCAN}


class Refused(Exception):
    """A reading the engine cannot give at its world (its reason is recorded in the table)."""


# ------------------------------------------------------------------ the engine at a state


@dataclasses.dataclass
class Bound:
    spec: object
    impl: object
    state: object
    p: object
    control: object
    values: object


def bind(spec):
    impl = get_model(spec.model)
    state, p = impl.initial_values(spec)
    control = impl.Control(*(v[0] for v in control_values(spec, [0.0])))
    with np.errstate(all="ignore"):
        values = impl.readouts(state, control, p, xp=np)
    if not bool(values.valid):
        raise Refused("the engine's readouts are not valid at this state (a law's domain)")
    return Bound(spec, impl, state, p, control, values)


def anchored(spec, voltages, c_total):
    """spec with each cell's charge anchor at its voltage (V), its amounts unchanged; an outside
    node with no held bath in its component holds minus its cells' charge (xc0_worlds)."""
    model = spec.model
    z = model.valence
    cells = []
    total = 0.0
    for c in model.cells:
        q = c_total * voltages[c.id]
        total += q
        ionic = math.fsum(v * a for v, a in zip(z, c.initial_amount_fmol, strict=True))
        cells.append(dataclasses.replace(
            c, fixed_charge_equivalent_fmol=q / CHARGE_PER_FMOL - ionic, initial_charge_C=q))
    outside = []
    held = any(o.reservoir for o in model.extracellular)
    for o in model.extracellular:
        if not held and not o.reservoir:
            ionic = math.fsum(v * a for v, a in zip(z, o.initial_amount_fmol, strict=True))
            o = dataclasses.replace(o, fixed_charge_equivalent_fmol=-total / CHARGE_PER_FMOL - ionic,
                                    initial_charge_C=-total)  # fmt: skip
        outside.append(o)
    return dataclasses.replace(
        spec, model=dataclasses.replace(model, cells=tuple(cells), extracellular=tuple(outside)))


class World:
    """One parsed XC0 world (xc0_worlds.world's keywords), read at any cell voltages."""

    def __init__(self, d=None, **kw):
        self.d = W.inputs() if d is None else d
        self.kw = kw
        self.raw = W.world(d=self.d, **kw)
        self.spec = parse_spec(copy.deepcopy(self.raw))
        self.c_total = W.total_capacitance(self.d) * kw.get("scale_capacitance", 1.0)
        self.cells = [c.id for c in self.spec.model.cells]
        self.species = list(self.spec.model.species_ids)
        self.patches = [m.id for m in self.spec.model.membranes]
        self.domain = CHANNEL_DOMAIN if self.spec.model.channels else V_DOMAIN

    def at(self, voltages):
        """The engine at the cells' voltages ({cell: V}, or one V for every cell)."""
        if not isinstance(voltages, dict):
            voltages = {c: float(voltages) for c in self.cells}
        return bind(anchored(self.spec, voltages, self.c_total))

    def reparsed(self, voltages):
        """The same reading through a full parse of the definition at that anchor."""
        if not isinstance(voltages, dict):
            voltages = {c: float(voltages) for c in self.cells}
        return bind(parse_spec(W.world(d=self.d, **dict(self.kw, v0=voltages))))

    def patch(self, base, cell="cell_1"):
        return self.patches.index(f"{base}_{cell}")

    def dvdt(self, b, cell="cell_1"):
        return float(np.asarray(b.values.field.membrane_voltage_rate_V_s)[self.patch("m_main", cell)])

    def voltage(self, b, cell="cell_1"):
        return float(np.asarray(b.values.field.rates.membrane_voltage_V)[self.patch("m_main", cell)])

    def flux(self, b, ion, base, cell="cell_1"):
        flux = np.asarray(b.values.field.rates.membrane_flux_fmol_s)
        return float(flux[self.species.index(ion), self.patch(base, cell)])

    def current(self, b, ion, base, cell="cell_1"):
        z = dict(zip(self.species, self.spec.model.valence, strict=True))[ion]
        return CHARGE_PER_FMOL * z * self.flux(b, ion, base, cell)

    def cycle_modes(self, b):
        """The transporter kind's probe at the state's read and field potentials."""
        potentials = np.asarray(b.values.field.potential_V)
        return transporter.probe(b.state, potentials, b.control, b.p, xp=np).modes


# ------------------------------------------------------------------ roots


def bracket(f, lo, hi, n=None):
    """A sign change of f on a scan of [lo, hi]: (a, b, f(a), f(b)); refused if none, or if f
    changes sign more than once (no unique root)."""
    n = SCAN_POINTS["n"] if n is None else n
    xs = np.linspace(lo, hi, n)
    ys = []
    for x in xs:
        try:
            ys.append(f(float(x)))
        except (Refused, ConfigError):  # Outside a law's domain or the parse's: no point there.
            ys.append(np.nan)
    ys = np.asarray(ys)
    ok = np.isfinite(ys)
    signs = [(float(xs[i]), float(xs[i + 1]), float(ys[i]), float(ys[i + 1]))
             for i in range(n - 1) if ok[i] and ok[i + 1] and ys[i] * ys[i + 1] <= 0]  # fmt: skip
    exact = [s for s in signs if s[2] == 0.0 or s[3] == 0.0]
    if len(signs) == 0:
        raise Refused(f"no sign change on [{lo}, {hi}]")
    if len(signs) > 1 and not (len(exact) and len(signs) <= 2):
        raise Refused(f"{len(signs)} sign changes on [{lo}, {hi}]: no unique root")
    return signs[0]


def root(f, lo, hi, *, xtol=ROOT_XTOL):
    """brentq of f in the bracket that a scan of [lo, hi] finds."""
    from scipy.optimize import brentq

    a, b, fa, fb = bracket(f, lo, hi)
    if fa == 0.0:
        return a
    if fb == 0.0:
        return b
    return float(brentq(f, a, b, xtol=xtol, rtol=4 * np.finfo(float).eps, maxiter=500))


def log_root(f, lo, hi):
    """A root over a positive quantity, found in its logarithm."""
    return math.exp(root(lambda y: f(math.exp(y)), math.log(lo), math.log(hi), xtol=1e-14))


# ------------------------------------------------------------------ static readings


def leaks_world(state, d=None, **extra):
    """P1 (or P1L at the local exterior) at a registered state: the leaks open, the pump off, no
    symporter; extra adds glycine/kir/... in xc0_worlds' keywords."""
    ion_set, exterior, temperature = state
    return World(d, cells=(("cell_1", ion_set),), exterior_name=exterior,
                 temperature_K=temperature, **extra)  # fmt: skip


def v_zero(world, cell="cell_1"):
    """The engine's zero-current voltage: the root over V of dV/dt with the amounts fixed."""
    v = root(lambda x: world.dvdt(world.at(x), cell), *world.domain)
    return v, check_reparse(world, v, lambda b: world.dvdt(b, cell))


def ion_world(state, ion, d=None, g_ref=G_REF):
    if ion == "Cl":
        return leaks_world(state, d, glycine={"cell_1": (P_REF, 1.0)})
    if ion == "Kir":
        return leaks_world(state, d, kir={"cell_1": (g_ref, 1.0)})
    return leaks_world(state, d)


def e_zero(world, ion, cell="cell_1"):
    """An ion's zero: the root over V of its outward flux through its single-ion conductor."""
    base, _ = CONDUCTOR[ion]
    species = ION[ion]
    v = root(lambda x: world.flux(world.at(x), species, base, cell), *world.domain)
    return v, check_reparse(world, v, lambda b: world.flux(b, species, base, cell))


def check_reparse(world, v, read):
    """Whether a full re-parse at the root reads the same bits as the replaced anchor."""
    return bool(np.float64(read(world.at(v))) == np.float64(read(world.reparsed(v))))


def ion_current_at(world, ion, v, cell="cell_1"):
    base, _ = CONDUCTOR[ion]
    return world.current(world.at(v), ION[ion], base, cell)


def slope(f, x, h=SLOPE_STEP_V):
    """The central difference (f(x + h) - f(x - h)) / 2h of an engine output."""
    return (f(x + h) - f(x - h)) / (2 * h)


def tau_lin(world, v_inf, cell="cell_1"):
    """The engine's linear time constant at v_inf: -1 / (d(dV/dt)/dV), the central difference of the
    engine's dV/dt (C_total / g, g the engine's slope conductance)."""
    k = slope(lambda x: world.dvdt(world.at(x), cell), v_inf)
    if not k < 0:
        raise Refused("dV/dt does not fall with V at the zero")
    return -1.0 / k


# ------------------------------------------------------------------ the symporter (C6)


def symport_world(n, na_in, na_out, b_out, r_b, temperature, *, capacity=None, d=None,
                  version=1):  # fmt: skip
    """One cell (the primary set's other ions) facing a held bath (0.1x MMR's other ions), Na and
    B at the key's values; the symporter version 1 (n_Na = n) or version 2 on m_main."""
    d = W.inputs() if d is None else d
    base = d["symporter_v1"]["capacity_fmol_per_s"]["base"]
    k = base if capacity is None else capacity
    kw = dict(cells=(("cell_1", "primary"),), exterior_name="bath", temperature_K=temperature,
              cell_mm={"cell_1": {"Na": na_in, "B": r_b * b_out}},
              exterior_mm={"Na": na_out, "B": b_out})  # fmt: skip
    if version == 1:
        kw["symport"] = {"cell_1": (k, int(n))}
    else:
        kw["diagram"] = {"cell_1": k}
    return World(d, **kw)


def mode_value(world, v, field):
    modes = world.cycle_modes(world.at(v))
    return float(np.asarray(getattr(modes, field))[0, 0])


def stall(world):
    """The root over V of the population's net cycle rate J."""
    v = root(lambda x: mode_value(world, x, "j"), *world.domain)
    return v, check_reparse(world, v, lambda b: float(np.asarray(world.cycle_modes(b).j)[0, 0]))


def eq_ratio(n, na_in, na_out, b_out, temperature, v, *, d=None, version=1):
    """The root over B_in/B_out of J at a fixed V (each B_in a parsed world)."""

    def j(r):
        return mode_value(symport_world(n, na_in, na_out, b_out, r, temperature, d=d,
                                        version=version), v, "j")  # fmt: skip

    return log_root(j, 1e-6, 1e6)


# ------------------------------------------------------------------ runs


def trajectory(world_kw, end_time, *, d=None, x2_cap, dt=None):
    """A run of the world (xc0_worlds keywords), every accepted step observed, with X2 on."""
    from cells.execution.runner import run

    d = W.inputs() if d is None else d
    dt = float(d["execution"]["dt_s"]) * STEP["factor"] if dt is None else float(dt)
    steps = int(round(end_time / dt))
    times = [k * dt for k in range(steps + 1)]
    raw = W.world(d=d, dt=dt, end_time=steps * dt, observation_times=times,
                  energy_check_cap=x2_cap, **world_kw)  # fmt: skip
    started = time.perf_counter()
    result = run(parse_spec(raw))
    o = result.observations
    spec = result.spec
    membranes = [m.id for m in spec.model.membranes]
    cells = [c.id for c in spec.model.cells]
    voltage = np.asarray(o.membrane_voltage_V)
    out = dict(
        t=np.asarray(o.times, dtype=float),
        V={c: voltage[:, membranes.index(f"m_main_{c}")] for c in cells},
        amount=np.asarray(o.amount),  # [t, species, cell]
        outside=np.asarray(o.extracellular_amount),  # [t, species, outside node]
        species=list(spec.model.species_ids),
        cells=cells,
        outside_ids=[x.id for x in spec.model.extracellular],
        valence=np.asarray(spec.model.valence, dtype=float),
        fixed={c.id: c.fixed_charge_equivalent_fmol for c in spec.model.cells},
        c_total=W.total_capacitance(d) * world_kw.get("scale_capacitance", 1.0),
        diagnostics={k: float(v) for k, v in result.diagnostics.items()},
        seconds=time.perf_counter() - started,
        observations=o,
        spec=spec,
    )
    return out


def at_time(t, y, when):
    """y at time `when`: the accepted step's value if `when` is one, else the log-linear
    interpolation of y between the two accepted steps around it (y one-signed there)."""
    i = int(np.searchsorted(t, when))
    if i < len(t) and t[i] == when:
        return float(y[i])
    if i == 0 or i >= len(t):
        raise Refused(f"time {when} outside the run")
    a, b = y[i - 1], y[i]
    w = (when - t[i - 1]) / (t[i] - t[i - 1])
    if a * b > 0:
        return float(math.copysign(math.exp((1 - w) * math.log(abs(a)) + w * math.log(abs(b))), a))
    return float((1 - w) * a + w * b)


def cell_charge(traj, cell):
    """The cell's charge from its recorded amounts and fixed background (C)."""
    k = traj["cells"].index(cell)
    ionic = np.sum(traj["valence"][None, :] * traj["amount"][:, :, k], axis=1)
    return CHARGE_PER_FMOL * (traj["fixed"][cell] + ionic)


# ------------------------------------------------------------------ the measure catalogue


def state_of(params):
    return (params["ion_set"], params["exterior"], float(params["T"]))


def measure(name, params, *, d=None, x2_cap=None, cache=None):
    """The engine's value of one reading (MEASURES[name]) at its parameters: a float, a sign
    (-1, 0, 1), a flag (True/False) or a dict of named values."""
    cache = {} if cache is None else cache
    fn = MEASURES[name]
    return fn(params, d=d, x2_cap=x2_cap, cache=cache)


def cached(cache, key, make):
    if key not in cache:
        cache[key] = make()
    return cache[key]


def m_v_zero(params, *, d, cache, **_):
    """C0/C2 V_ghk_area, C4 V_zero_*: dV/dt's root at the state, the leaks open, with GlyR at
    (P, a) and/or the route at (g, a) where the params name them."""
    extra = {}
    if "P" in params:
        extra["glycine"] = {"cell_1": (float(params["P"]), float(params.get("a", 1.0)))}
    if "g" in params:
        extra["kir"] = {"cell_1": (float(params["g"]), float(params.get("a", 1.0)))}
    key = ("v_zero", state_of(params), json.dumps(extra, sort_keys=True))
    return cached(cache, key, lambda: v_zero(leaks_world(state_of(params), d, **extra)))[0]


def m_e_zero(params, *, d, cache, **_):
    """C0 E_<ion>, C1 zero_<ion>, the route's zero: the ion's zero through its conductor."""
    ion = params["ion"]
    key = ("e_zero", state_of(params), ion, params.get("g"))
    world = ion_world(state_of(params), ion, d, float(params.get("g", G_REF)))
    return cached(cache, key, lambda: e_zero(world, ion))[0]


def m_ion_current(params, *, d, cache, **_):
    """C1 sign_I: the ion's outward current through its conductor at its own zero + offset (A)."""
    ion, offset = params["ion"], float(params["offset"])
    e = m_e_zero(params, d=d, cache=cache)
    world = ion_world(state_of(params), ion, d, float(params.get("g", G_REF)))
    return ion_current_at(world, ion, e + offset)


def m_dvdt_offset(params, *, d, cache, **_):
    """C2's signs: the engine's dV/dt at the zero-current voltage + offset (V/s)."""
    v = m_v_zero(params, d=d, cache=cache)
    world = leaks_world(state_of(params), d)
    return world.dvdt(world.at(v + float(params["offset"])))


def m_effect_sign(params, *, d, cache, **_):
    """C0's effect signs (+1 depolarises): the sign of the voltage change the ion's single-ion
    conductor makes at the resting voltage, -sign(its outward current there)."""
    v = m_v_zero({k: params[k] for k in ("ion_set", "exterior", "T")}, d=d, cache=cache)
    i = ion_current_at(ion_world(state_of(params), params["ion"], d), params["ion"], v)
    return -float(np.sign(i))


def m_cl_bound(params, *, d, cache, **_):
    """C0's Cl- bound: |E_Cl - V_rest| from the engine's two roots."""
    rest = m_v_zero({k: params[k] for k in ("ion_set", "exterior", "T")}, d=d, cache=cache)
    e = m_e_zero(dict(params, ion="Cl"), d=d, cache=cache)
    return abs(e - rest)


def m_cl_threshold(params, *, d, cache, **_):
    """C0's Cl_i threshold (mM): the root over the cell's Cl- of GlyR's Cl flux at the resting
    voltage of the declared state (each Cl_i a parsed world, its charge anchor at that voltage)."""
    state = state_of(params)
    rest = m_v_zero({k: params[k] for k in ("ion_set", "exterior", "T")}, d=d, cache=cache)
    ion_set, exterior_name, temperature = state

    def flux(cl):
        world = World(d, cells=(("cell_1", ion_set),), exterior_name=exterior_name,
                      temperature_K=temperature, cell_mm={"cell_1": {"Cl": cl}},
                      glycine={"cell_1": (P_REF, 1.0)})  # fmt: skip
        return world.flux(world.at(rest), "Cl", "m_glycine")

    return log_root(flux, 1e-3, 1e4)


def m_shift(params, *, d, cache, **_):
    """C4's shifts: V_zero at availability a minus V_zero at availability 0 (the same world)."""
    at_a = m_v_zero(params, d=d, cache=cache)
    at_0 = m_v_zero(dict(params, a=0.0), d=d, cache=cache)
    return at_a - at_0


def m_monotone(params, *, d, cache, **_):
    """C4's monotone flags: V_zero over availability 0, 0.25, 0.5, 0.75, 1 moves toward the ion's
    zero at every step, or by less than the roots' resolution (ROOT_XTOL + 4 eps |V|)."""
    levels = (0.0, 0.25, 0.5, 0.75, 1.0)
    zs = [m_v_zero(dict(params, a=a), d=d, cache=cache) for a in levels]
    ion = "Cl" if "P" in params else "Kir"
    target = m_e_zero(dict(params, ion=ion), d=d, cache=cache)
    toward = np.sign(target - zs[0])
    for a, b in zip(zs, zs[1:], strict=False):
        step = b - a
        resolution = 2 * (ROOT_XTOL + 4 * np.finfo(float).eps * max(abs(a), abs(b)))
        if np.sign(step) not in (toward, 0.0) and abs(step) > resolution:
            return False
    return True


def m_exact_zero(params, *, d, cache, **_):
    """C4's exact zeros: the element's outward flux at availability 0, at the resting voltage."""
    rest = m_v_zero({k: params[k] for k in ("ion_set", "exterior", "T")}, d=d, cache=cache)
    if "P" in params:
        world = leaks_world(state_of(params), d, glycine={"cell_1": (float(params["P"]), 0.0)})
        return world.flux(world.at(rest), "Cl", "m_glycine")
    world = leaks_world(state_of(params), d, kir={"cell_1": (float(params["g"]), 0.0)})
    return world.flux(world.at(rest), "K", "m_kir")


def m_kir_current(params, *, d, cache, **_):
    """The route's outward current (A) at the route's zero + offset (V), g from the params."""
    world = ion_world(state_of(params), "Kir", d, float(params["g"]))
    e = m_e_zero(dict(params, ion="Kir"), d=d, cache=cache)
    return ion_current_at(world, "Kir", e + float(params["offset"]))


def m_kir_slope(params, *, d, cache, **_):
    """The route's slope dI/dV (S) at its zero + offset: the central difference of its current."""
    world = ion_world(state_of(params), "Kir", d, float(params["g"]))
    e = m_e_zero(dict(params, ion="Kir"), d=d, cache=cache)
    return slope(lambda x: ion_current_at(world, "Kir", x), e + float(params["offset"]))


def m_tau_lin(params, *, d, cache, **_):
    """C3's tau_lin at a scenario world: -1 / d(dV/dt)/dV at its zero-current voltage."""
    world = scenario_world(params, d)
    v = cached(cache, ("scenario_zero", scenario_key(params)), lambda: v_zero(world))[0]
    return tau_lin(world, v)


# ------------------------------------------------------------------ scenarios (runs)

# C3's scenarios that DESIGN §4 and the interface's documented names define. The rest of the
# references' S2-S8 are not documented outside their family notes: each joins this table by a
# dated erratum that states its world (the rule's readings_to_confirm), never by a guess.
SCENARIOS = {
    "S1_leaks_bath": dict(state=("primary", "bath", 291.15)),
    "S9_leaks_bath_T287": dict(state=("primary", "bath", 287.15)),
}


def scenario_key(params):
    return json.dumps({k: params[k] for k in sorted(params) if k not in ("k", "delta")},
                      sort_keys=True, default=str)  # fmt: skip


def scenario_world(params, d):
    s = SCENARIOS.get(params.get("scenario"))
    if s is None:
        raise Refused(f"scenario {params.get('scenario')!r} has no declared world")
    return leaks_world(s["state"], d, **s.get("extra", {}))


def relaxation(params, *, d, x2_cap, cache):
    """C3: the run from V_inf + delta (the engine's own zero-current voltage) to RUN_TAUS tau_lin, its
    observations at every accepted step, with the engine's tau_lin."""
    key = ("relax", scenario_key(params), float(params["delta"]), STEP["factor"])

    def make():
        world = scenario_world(params, d)
        v_inf = cached(cache, ("scenario_zero", scenario_key(params)), lambda: v_zero(world))[0]
        tau = tau_lin(world, v_inf)
        s = SCENARIOS[params["scenario"]]
        ion_set, exterior_name, temperature = s["state"]
        kw = dict(cells=(("cell_1", ion_set),), exterior_name=exterior_name,
                  temperature_K=temperature, v0=v_inf + float(params["delta"]),
                  **s.get("extra", {}))  # fmt: skip
        traj = trajectory(kw, RUN_TAUS * tau, d=d, x2_cap=x2_cap)
        return dict(v_inf=v_inf, tau_lin=tau, traj=traj)

    return cached(cache, key, make)


def m_tau_fit(params, *, d, x2_cap, cache, **_):
    """C3's tau_fit: t / ln(delta / (V(t) - V_inf)) at t = tau_lin (the engine's own), V(t) the
    run's, interpolated log-linearly between its two accepted steps."""
    r = relaxation(params, d=d, x2_cap=x2_cap, cache=cache)
    t = r["tau_lin"]
    dev = r["traj"]["V"]["cell_1"] - r["v_inf"]
    return t / math.log(float(params["delta"]) / at_time(r["traj"]["t"], dev, t))


def m_ratio_t(params, *, d, x2_cap, cache, **_):
    """C3's ratio_t: (V(t) - V_inf) / delta at t = k tau_lin / 4, as m_tau_fit reads V(t)."""
    r = relaxation(params, d=d, x2_cap=x2_cap, cache=cache)
    t = int(params["k"]) * r["tau_lin"] / 4.0
    dev = r["traj"]["V"]["cell_1"] - r["v_inf"]
    return at_time(r["traj"]["t"], dev, t) / float(params["delta"])


def m_charge_identity(params, *, d, x2_cap, cache, **_):
    """C3's Q - C V: the largest |Q(t) - C_total V(t)| over the run's accepted steps, Q from the
    recorded amounts and the cell's fixed background (C)."""
    r = relaxation(params, d=d, x2_cap=x2_cap, cache=cache)
    traj = r["traj"]
    q = cell_charge(traj, "cell_1")
    return float(np.max(np.abs(q - traj["c_total"] * traj["V"]["cell_1"])))


# ------------------------------------------------------------------ the symporter's readings (C6)


def sym_params(params):
    return (int(params["n"]), float(params["Nain"]), float(params["Naout"]), float(params["BP"]),
            float(params.get("rB", 1.0)), float(params.get("T", 291.15)))  # fmt: skip


def sym_world(params, d, *, capacity=None, version=1):
    n, na_in, na_out, b_out, r_b, temperature = sym_params(params)
    return symport_world(n, na_in, na_out, b_out, r_b, temperature, capacity=capacity, d=d,
                         version=version)  # fmt: skip


def rest_voltage(params, d, cache):
    """A key's Vrest_<exterior>: the engine's zero-current voltage of the primary set at that
    exterior and the key's temperature (the leaks open, the pump off)."""
    return m_v_zero(dict(ion_set="primary", exterior=params["Vrest"], T=float(params.get("T", 291.15))),
                    d=d, cache=cache)  # fmt: skip


def m_sym_stall(params, *, d, cache, **_):
    """C6 v1 stall: the root over V of the population's J at the key's state."""
    key = ("sym_stall", sym_params(params))
    return cached(cache, key, lambda: stall(sym_world(params, d)))[0]


def sym_voltage(params, d, cache):
    """The key's voltage: |V<V> absolute, |off<dV> from the engine's stall, |Vrest_<ext>."""
    if "V" in params:
        return float(params["V"])
    if "off" in params:
        return m_sym_stall(params, d=d, cache=cache) + float(params["off"])
    if "Vrest" in params:
        return rest_voltage(params, d, cache)
    raise Refused("the key names no voltage")


def m_sym_mode(field):
    def reading(params, *, d, cache, **_):
        world = sym_world(params, d)
        return mode_value(world, sym_voltage(params, d, cache), field)

    reading.__doc__ = (f"C6 v1: the transporter kind's probe's {field} at the key's state and "
                       "voltage (|V, |off from the engine's stall, or |Vrest_<exterior>).")  # fmt: skip
    return reading


def m_sym_eq_ratio(params, *, d, cache, **_):
    """C6 v1 equilibrium ratio: the root over B_in/B_out of J at the key's voltage."""
    n, na_in, na_out, b_out, _, temperature = sym_params(dict(params, rB=1.0))
    return eq_ratio(n, na_in, na_out, b_out, temperature, sym_voltage(params, d, cache), d=d)


def m_sym_capacity_ratio(params, *, d, cache, **_):
    """C6 v1 capacity: J at capacity f k over J at k (k the declared base), at the key's voltage."""
    base = (W.inputs() if d is None else d)["symporter_v1"]["capacity_fmol_per_s"]["base"]
    v = sym_voltage(params, d, cache)
    scaled = mode_value(sym_world(params, d, capacity=float(params["f"]) * base), v, "j")
    return scaled / mode_value(sym_world(params, d, capacity=base), v, "j")


def m_diag_ratio(params, *, d, cache, **_):
    """C6 v2 (thermodynamic): J-/J+ of the diagram population at the key's state and voltage."""
    world = sym_world(params, d, version=2)
    modes = world.cycle_modes(world.at(sym_voltage(params, d, cache)))
    return float(np.asarray(modes.j_minus)[0, 0] / np.asarray(modes.j_plus)[0, 0])


def m_diag_stall(params, *, d, cache, **_):
    """C6 v2 (thermodynamic): the root over V of the diagram population's J."""
    key = ("diag_stall", sym_params(params))
    return cached(cache, key, lambda: stall(sym_world(params, d, version=2)))[0]


# ------------------------------------------------------------------ two cells (C5)


def two_cell_world(params, d):
    """P2: two primary cells in the bath at 291.15 K, the junction at the key's multiple; cell_2
    carries the scenario's element (kir_g<g>: the route open; x_gly<P>: GlyR open; sym: none)."""
    extra = {}
    if "kir_g" in params:
        extra["kir"] = {"cell_2": (float(params["kir_g"]), 1.0)}
    if "x_gly" in params:
        extra["glycine"] = {"cell_2": (float(params["x_gly"]), 1.0)}
    return World(d, cells=(("cell_1", "primary"), ("cell_2", "primary")), exterior_name="bath",
                 temperature_K=291.15, junction=float(params.get("x", 1.0)), **extra)  # fmt: skip


def two_cell_steady(world):
    """The engine's steady voltages with the amounts fixed: the 2D root of (dV1/dt, dV2/dt),
    scipy's hybrid method from the isolated cells' zero, then refined until both rates sit at the
    float64 floor (each evaluation a replaced anchor)."""
    from scipy.optimize import root as solve

    def f(v):
        b = world.at({"cell_1": float(v[0]), "cell_2": float(v[1])})
        return [world.dvdt(b, "cell_1"), world.dvdt(b, "cell_2")]

    start = v_zero(World(world.d, **dict(world.kw, cells=(("cell_1", "primary"),), junction=None,
                                         kir=None, glycine=None)))[0]  # fmt: skip
    sol = solve(f, [start, start], method="hybr", options=dict(xtol=1e-12, maxfev=400))
    v = np.asarray(sol.x, dtype=float)
    # Newton's steps with the engine's central-difference Jacobian, until a step moves neither
    # voltage by more than the roots' resolution (NEWTON_STEPS at most).
    for _ in range(NEWTON_STEPS):
        step = np.linalg.solve(two_cell_jacobian(world, v[0], v[1]), -np.asarray(f(v)))
        v = v + step
        if np.max(np.abs(step)) <= ROOT_XTOL + 4 * np.finfo(float).eps * np.max(np.abs(v)):
            return float(v[0]), float(v[1])
    raise Refused(f"no steady state to the roots' resolution in {NEWTON_STEPS} Newton steps")


def two_cell_jacobian(world, v1, v2, h=SLOPE_STEP_V):
    def rates(a, b):
        x = world.at({"cell_1": a, "cell_2": b})
        return np.array([world.dvdt(x, "cell_1"), world.dvdt(x, "cell_2")])

    j = np.empty((2, 2))
    j[:, 0] = (rates(v1 + h, v2) - rates(v1 - h, v2)) / (2 * h)
    j[:, 1] = (rates(v1, v2 + h) - rates(v1, v2 - h)) / (2 * h)
    return j


def m_c5(field):
    def reading(params, *, d, cache, **_):
        """C5: the engine's two-cell steady voltages (v1, v2) and its relaxation modes: tau = -1 /
        eigenvalue of the central-difference Jacobian of (dV1/dt, dV2/dt) at the steady state, the
        common mode the eigenvector nearer (1, 1)."""
        key = ("c5", json.dumps(params, sort_keys=True, default=str))

        def make():
            world = two_cell_world(params, d)
            v1, v2 = two_cell_steady(world)
            values, vectors = np.linalg.eig(two_cell_jacobian(world, v1, v2))
            if np.any(np.abs(np.imag(values)) > 0) or np.any(np.real(values) >= 0):
                raise Refused("the Jacobian's modes are not two decaying real modes")
            values, vectors = np.real(values), np.real(vectors)
            common = int(np.argmax(np.abs(vectors[0] + vectors[1]) / np.linalg.norm(vectors, axis=0)))
            return dict(v1=v1, v2=v2, tau_common=-1.0 / values[common],
                        tau_diff=-1.0 / values[1 - common])  # fmt: skip

        return cached(cache, key, make)[field]

    return reading


# ------------------------------------------------------------------ the pump (C7)


def m_pump(field):
    def reading(params, *, d, cache, **_):
        """C7 pump, per cycle at the state's readouts (P1, primary, bath, 291.15 K, V0 = -0.04 V,
        the leaks closed so that m_main's flux is the pump's): its counts (the patch's outward
        flux of Na and K over the cycle rate), the cell's charge per fmol of cycles (C), the
        chemical drive (J/mol: -1e3 metabolic power / cycle rate) and the heat (J/mol: 1e3 pump
        dissipation / cycle rate), each the engine's readout over its cycle rate."""
        key = ("pump",)

        def make():
            world = World(d, cells=(("cell_1", "primary"),), exterior_name="bath",
                          temperature_K=291.15, pump={"cell_1": 1.0},
                          leaks={"cell_1": {"m_main": 0.0, "m_kleak": 0.0}})  # fmt: skip
            b = world.at(W.V0)
            der = b.values.derivative
            k = world.patch("m_main")
            cycles = float(np.asarray(der.pump_cycles)[k])
            flux = np.asarray(b.values.field.rates.membrane_flux_fmol_s)[:, k]
            z = np.asarray(world.spec.model.valence, dtype=float)
            return dict(
                counts_Na=-flux[world.species.index("Na")] / cycles,  # Inward per cycle.
                counts_K=-flux[world.species.index("K")] / cycles,
                cell_charge_per_fmol=-CHARGE_PER_FMOL * float(np.sum(z * flux)) / cycles,
                dG_atp=-1e3 * float(np.asarray(der.metabolic_work_pJ)[k]) / cycles,
                heat=1e3 * float(np.asarray(der.pump_dissipated_energy_pJ)[k]) / cycles,
            )

        values = cached(cache, key, make)
        if field == "heat_nonneg":
            return values["heat"] >= 0.0
        return values[field]

    return reading


# ------------------------------------------------------------------ local against bath (C8)


def m_c8a(quantity):
    def reading(params, *, d, cache, **_):
        """C8 (a): the engine's local-node value minus its bath value, the same ion set and T."""
        local = dict(params, exterior="local")
        bath = dict(params, exterior="bath")
        if quantity == "v_zero":
            return m_v_zero(local, d=d, cache=cache) - m_v_zero(bath, d=d, cache=cache)
        ion = quantity.split("_", 1)[1]
        return (m_e_zero(dict(local, ion=ion), d=d, cache=cache)
                - m_e_zero(dict(bath, ion=ion), d=d, cache=cache))  # fmt: skip

    return reading


# ------------------------------------------------------------------ C7's relaxation (runs)

C7_STATE = ("primary", "bath", 291.15)


def c7_relaxation(*, d, x2_cap, cache):
    """C7: P1 at the primary set in the bath at 291.15 K, the leaks open, the pump off, from the
    declared anchor V0 = -0.04 V, run to RUN_TAUS tau_lin of the engine at its zero-current voltage,
    every accepted step observed."""

    def make():
        world = leaks_world(C7_STATE, d)
        v_inf = v_zero(world)[0]
        tau = tau_lin(world, v_inf)
        kw = dict(cells=(("cell_1", "primary"),), exterior_name="bath", temperature_K=291.15,
                  v0=W.V0)  # fmt: skip
        return dict(v_inf=v_inf, tau_lin=tau, traj=trajectory(kw, RUN_TAUS * tau, d=d, x2_cap=x2_cap))

    return cached(cache, ("c7_relax", STEP["factor"]), make)


def m_c7_charge_identity(params, *, d, x2_cap, cache, **_):
    """C7: the largest |Q(t) - C_total V(t)| over the run's accepted steps (C)."""
    traj = c7_relaxation(d=d, x2_cap=x2_cap, cache=cache)["traj"]
    return float(np.max(np.abs(cell_charge(traj, "cell_1") - traj["c_total"] * traj["V"]["cell_1"])))


def m_c7_charge_balance(params, *, d, x2_cap, cache, **_):
    """C7: the largest |(Q(t) - Q(0)) + e sum_s z_s sum_m T_sm(t)| over the run's accepted steps,
    T the cumulative outward transfer through each patch (the engine's membrane_transferred): the
    cell's ionic charge change against the integrated membrane current (C)."""
    traj = c7_relaxation(d=d, x2_cap=x2_cap, cache=cache)["traj"]
    q = cell_charge(traj, "cell_1")
    moved = np.asarray(traj["observations"].membrane_transferred)  # [t, species, membrane]
    out = CHARGE_PER_FMOL * np.sum(traj["valence"][None, :, None] * moved, axis=(1, 2))
    return float(np.max(np.abs((q - q[0]) + out)))


def m_c7_dQ(params, *, d, x2_cap, cache, **_):
    """C7: the cell's charge change Q(t) - Q(0) from its recorded amounts (C), at t = k tau_lin / 4
    (params k) or t (params t, an accepted step), interpolated as at_time reads."""
    r = c7_relaxation(d=d, x2_cap=x2_cap, cache=cache)
    traj = r["traj"]
    q = cell_charge(traj, "cell_1")
    when = float(params["t"]) if "t" in params else int(params["k"]) * r["tau_lin"] / 4.0
    return at_time(traj["t"], q - q[0], when)


# ------------------------------------------------------------------ C8 (b): the local node (runs)

C8_END_S = 60.0  # s: the P1LB runs' horizon (about twelve 1/e times of the slowest species).
C8_EVERY = 100  # Accepted steps between observations in the P1LB runs (10 ms at the declared dt).


def c8b_run(reading, *, d, x2_cap, cache):
    """P1LB at the primary set, 291.15 K, from the declared anchor: `coupled`, the cell's leaks open
    (its passive membrane; the pump off, no route or GlyR); `bare`, every patch closed, so the node
    exchanges with the bath through the face alone. Observed every C8_EVERY steps to C8_END_S."""

    def make():
        from cells.execution.runner import run

        dd = W.inputs() if d is None else d
        dt = float(dd["execution"]["dt_s"]) * STEP["factor"]
        steps = int(round(C8_END_S / dt))
        every = int(round(C8_EVERY / STEP["factor"]))  # The same observation times at every step.
        times = [k * dt for k in range(0, steps + 1, every)]
        leaks = None if reading == "coupled" else {"cell_1": {"m_main": 0.0, "m_kleak": 0.0}}
        raw = W.world(d=dd, cells=(("cell_1", "primary"),), exterior_name="local", face=True,
                      leaks=leaks, dt=dt, end_time=steps * dt, observation_times=times,
                      energy_check_cap=x2_cap)  # fmt: skip
        result = run(parse_spec(raw))
        o = result.observations
        outside = [x.id for x in result.spec.model.extracellular]
        k = outside.index("outside_local")
        volume = result.spec.model.extracellular[k].volume_pL
        return dict(t=np.asarray(o.times, dtype=float),
                    c=np.asarray(o.extracellular_amount)[:, :, k] / volume,  # [t, species] mM
                    psi=np.asarray(o.extracellular_potential_V)[:, k],
                    species=list(result.spec.model.species_ids),
                    diagnostics={x: float(v) for x, v in result.diagnostics.items()})  # fmt: skip

    return cached(cache, ("c8b", reading, STEP["factor"]), make)


def m_c8b(field):
    def reading(params, *, d, x2_cap, cache, **_):
        """C8 (b) at the `reading` (coupled or bare): the local node's concentration of `species`
        (mM) or potential (V, the bath held at 0) at C8_END_S (`final`) or at t (`at`); or a
        species' 1/e time (`t_e`, s): the first time its distance from its C8_END_S value falls
        to 1/e of its initial distance, interpolated linearly between two observations."""
        r = c8b_run(params["reading"], d=d, x2_cap=x2_cap, cache=cache)
        if field == "psi_final":
            return float(r["psi"][-1])
        if field == "psi_at":
            return at_time(r["t"], r["psi"], float(params["t"]))
        y = r["c"][:, r["species"].index(params["species"])]
        if field == "final":
            return float(y[-1])
        if field == "at":
            return at_time(r["t"], y, float(params["t"]))
        dist = np.abs(y - y[-1])
        target = dist[0] / math.e
        i = int(np.argmax(dist <= target))
        if i == 0:
            raise Refused("the species does not relax within the run")
        w = (dist[i - 1] - target) / (dist[i - 1] - dist[i])
        return float(r["t"][i - 1] + w * (r["t"][i] - r["t"][i - 1]))

    return reading


# ------------------------------------------------------------------ T1 and T2 (published numbers)


def m_t2_shift(params, *, d, cache, **_):
    """T2's engine reading: the GlyR arm's voltage change, V_zero with GlyR at (P, 1) minus V_zero
    with it at (P, 0), at a state (negative: a hyperpolarisation). Scored against the published
    19.4 mV outside the reference verdict."""
    return m_shift(dict(params, a=1.0), d=d, cache=cache)


def m_t1_availability(params, *, d, cache, **_):
    """T1's engine reading: the m_kleak availability at which the zero-current voltage lies the
    published shift (params shift_V, +0.011 for a depolarisation of 11 mV) above its value at
    availability 1, at a state; refused where none in [0, 1] does."""
    state = state_of(params)
    rest = m_v_zero({k: params[k] for k in STATE_KEYS}, d=d, cache=cache)

    def gap(a):
        world = leaks_world(state, d, leaks={"cell_1": {"m_main": 1.0, "m_kleak": a}})
        return v_zero(world)[0] - rest - float(params["shift_V"])

    from scipy.optimize import brentq

    lo, hi = gap(0.0), gap(1.0)
    if lo * hi > 0:
        raise Refused("no m_kleak availability in [0, 1] gives the shift")
    return float(brentq(gap, 0.0, 1.0, xtol=1e-14))


STATE_KEYS = ("ion_set", "exterior", "T")


MEASURES = {
    "v_zero": m_v_zero,
    "e_zero": m_e_zero,
    "ion_current": m_ion_current,
    "dvdt_offset": m_dvdt_offset,
    "effect_sign": m_effect_sign,
    "cl_bound": m_cl_bound,
    "cl_threshold": m_cl_threshold,
    "shift": m_shift,
    "monotone": m_monotone,
    "exact_zero": m_exact_zero,
    "kir_current": m_kir_current,
    "kir_slope": m_kir_slope,
    "tau_lin": m_tau_lin,
    "tau_fit": m_tau_fit,
    "ratio_t": m_ratio_t,
    "charge_identity": m_charge_identity,
    "sym_stall": m_sym_stall,
    "sym_x": m_sym_mode("x"),
    "sym_s": m_sym_mode("s"),
    "sym_j": m_sym_mode("j"),
    "sym_eq_ratio": m_sym_eq_ratio,
    "sym_capacity_ratio": m_sym_capacity_ratio,
    "diag_ratio": m_diag_ratio,
    "diag_stall": m_diag_stall,
    "c5_v1": m_c5("v1"),
    "c5_v2": m_c5("v2"),
    "c5_tau_common": m_c5("tau_common"),
    "c5_tau_diff": m_c5("tau_diff"),
    "pump_counts_Na": m_pump("counts_Na"),
    "pump_counts_K": m_pump("counts_K"),
    "pump_cell_charge_per_fmol": m_pump("cell_charge_per_fmol"),
    "pump_dG_atp": m_pump("dG_atp"),
    "pump_heat": m_pump("heat"),
    "pump_heat_nonneg": m_pump("heat_nonneg"),
    "c8a_v_zero": m_c8a("v_zero"),
    "c8a_e_K": m_c8a("e_K"),
    "c8a_e_Cl": m_c8a("e_Cl"),
    "c8a_e_Na": m_c8a("e_Na"),
    "c7_charge_identity": m_c7_charge_identity,
    "c7_charge_balance": m_c7_charge_balance,
    "c7_dQ": m_c7_dQ,
    "c8b_final": m_c8b("final"),
    "c8b_at": m_c8b("at"),
    "c8b_t_e": m_c8b("t_e"),
    "c8b_psi_final": m_c8b("psi_final"),
    "c8b_psi_at": m_c8b("psi_at"),
    "t2_shift": m_t2_shift,
    "t1_kleak_availability": m_t1_availability,
}


# ------------------------------------------------------------------ the table


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                          check=True).stdout  # fmt: skip


def provenance():
    """The source's identity: a frozen snapshot's record (SNAPSHOT.json at ROOT), else the
    checkout's revision and whether it is dirty (a dirty checkout is recorded, never judged)."""
    snapshot = ROOT / "SNAPSHOT.json"
    if snapshot.exists():
        s = json.loads(snapshot.read_text())
        clean = s["patch_sha256"] == hashlib.sha256(b"").hexdigest()
        return dict(engine_revision=s["git_revision"], snapshot=str(ROOT),
                    snapshot_patch_sha256=s["patch_sha256"], checkout_dirty=not clean)  # fmt: skip
    status = git("status", "--porcelain", "--", "src", "validation")
    return dict(engine_revision=git("rev-parse", "HEAD").strip(), snapshot=None,
                checkout_dirty=bool(status.strip()), checkout_status=status.splitlines())  # fmt: skip


def encode(value):
    if isinstance(value, (bool, np.bool_)):
        return dict(type="flag", value="true" if bool(value) else "false")
    if isinstance(value, (int, float, np.floating, np.integer)):
        return dict(type="number", value=repr(float(value)))
    raise TypeError(f"no encoding for {type(value)}")


RUN_MEASURES = frozenset({
    "tau_fit", "ratio_t", "charge_identity", "c7_charge_identity", "c7_charge_balance", "c7_dQ",
    "c8b_final", "c8b_at", "c8b_t_e", "c8b_psi_final", "c8b_psi_at",
})  # fmt: skip


def evaluate(entry, *, d, x2_cap, cache, factor=1.0):
    STEP["factor"] = factor
    try:
        return encode(measure(entry["measure"], entry["params"], d=d, x2_cap=x2_cap, cache=cache))
    except Refused as exc:
        return dict(type="refused", reason=str(exc))
    except Exception as exc:  # A failure is recorded, never hidden (the rule's retry reads it).
        return dict(type="error", reason=f"{type(exc).__name__}: {exc}",
                    trace=traceback.format_exc(limit=4))  # fmt: skip
    finally:
        STEP["factor"] = 1.0


def step_check(value, half, tolerance):
    """A run row's step-halving check: |y(h) - y(h/2)| against the claim's DESIGN tolerance,
    abs + rel |y(h/2)| (the manifest's step_tolerance)."""
    if value["type"] != "number" or half["type"] != "number":
        return dict(converged=False, reason="a run was refused")
    a, b = float(value["value"]), float(half["value"])
    bound = float(tolerance.get("abs", 0.0)) + float(tolerance.get("rel", 0.0)) * abs(b)
    return dict(converged=bool(abs(a - b) <= bound), difference=repr(abs(a - b)), bound=repr(bound))


def build_table(manifest, *, x2_cap, d=None, log=print, retry=False):
    """Each manifest entry {family, key, measure, params[, step_tolerance]} with the engine's value,
    or its refusal. A run row is also run at half the step (the step check); in the retry (the
    rule's, once) a run row is judged at h/2 against h/4 and a static row's scan is doubled."""
    cache, rows = {}, []
    SCAN_POINTS["n"] = 2 * SCAN if retry else SCAN
    for i, entry in enumerate(manifest):
        started = time.perf_counter()
        row = dict(family=entry["family"], key=entry["key"], measure=entry["measure"],
                   params=entry["params"])  # fmt: skip
        if entry["measure"] in RUN_MEASURES:
            first, second = (0.5, 0.25) if retry else (1.0, 0.5)
            value = evaluate(entry, d=d, x2_cap=x2_cap, cache=cache, factor=first)
            half = evaluate(entry, d=d, x2_cap=x2_cap, cache=cache, factor=second)
            row |= value
            row["step_factor"] = first
            row["half_step"] = half
            row["step_check"] = step_check(value, half, entry.get("step_tolerance", {}))
        else:
            row |= evaluate(entry, d=d, x2_cap=x2_cap, cache=cache)
        row["seconds"] = round(time.perf_counter() - started, 3)
        rows.append(row)
        log(f"[{i + 1}/{len(manifest)}] {row['family']} {row['key']}: {row['type']} "
            f"({row['seconds']} s)")  # fmt: skip
    return rows


def main(argv=None):
    a = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = a.add_subparsers(dest="command", required=True)
    t = sub.add_parser("table")
    t.add_argument("manifest")
    t.add_argument("out")
    t.add_argument("--x2-cap", type=float, required=True)
    t.add_argument("--retry", action="store_true", help="the rule's retry (once)")
    args = a.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    manifest = json.loads(Path(args.manifest).read_text())
    started = datetime.now(UTC).isoformat()
    record = dict(schema=SCHEMA, started_utc=started, source=provenance(),
                  manifest=str(Path(args.manifest).resolve()),
                  manifest_sha256=hashlib.sha256(Path(args.manifest).read_bytes()).hexdigest(),
                  x2_cap=args.x2_cap, retry=args.retry, python=platform.python_version(),
                  argv=sys.argv)  # fmt: skip
    (out / "run_record.json").write_text(json.dumps(record, indent=1))
    rows = build_table(manifest["entries"], x2_cap=args.x2_cap, retry=args.retry)
    table = dict(schema=SCHEMA, record=record, finished_utc=datetime.now(UTC).isoformat(), rows=rows)
    data = json.dumps(table, indent=1, sort_keys=True).encode()
    (out / "engine_table.json").write_bytes(data)
    digest = hashlib.sha256(data).hexdigest()
    (out / "engine_table.sha256").write_text(digest + "  engine_table.json\n")
    print(digest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
