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
import shutil
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
from cells.laws.electrochemistry import CHARGE_PER_FMOL, R
from cells.registry.models import get_model
from validation.xenopus_bioelectric import xc0_worlds as W

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "xenopus_xc0_engine_table@1"
ROOT_XTOL = 1e-16  # V: brentq's absolute tolerance on a voltage root (rtol 4 eps).
SCAN = 24  # Bracket scan points across a root's domain.
V_DOMAIN = (-0.20, 0.15)  # V: the scan for a root with no channel population declared.
CHANNEL_DOMAIN = (-0.12, 0.06)  # V: @3's channel domain, wherever GlyR is declared.
# V: a symporter world's scan (erratum 1): no channel is declared there, and with the keys' B ratios
# (to 1e-5) a stall can lie far beyond V_DOMAIN; points outside the law's domain (|x| > 80) are skipped.
SYM_DOMAIN = (-1.0, 1.0)
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
REPARSED = []  # Each root's re-parse check, for the row that read it (build_table records them).
SCANS = []  # Erratum 2: each bracket scan's points and drops, for the row that read it.


class Refused(Exception):
    """A reading the engine cannot give at its world (its reason is recorded in the table); a scan's
    refusal carries the scan's counts (erratum 2)."""

    def __init__(self, reason, *, scan=None):
        super().__init__(reason)
        self.scan = scan


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
        return self.cycle_modes_full(b).modes

    def cycle_modes_full(self, b):
        """The whole probe (modes, rows, populations) at the state's read and field potentials."""
        potentials = np.asarray(b.values.field.potential_V)
        return transporter.probe(b.state, potentials, b.control, b.p, xp=np)


# ------------------------------------------------------------------ roots


def bracket(f, lo, hi, n=None):
    """A sign change of f on a scan of [lo, hi]: (a, b, f(a), f(b)); refused if none, or if f
    changes sign more than once (no unique root). Erratum 2: the scan counts the points it could not
    evaluate (the parse refused the world, the engine's readouts refused the state, or f was not
    finite) and a refusal states them, so that "no sign change" cannot hide a stretch never
    evaluated; which scans are accepted is unchanged."""
    n = SCAN_POINTS["n"] if n is None else n
    xs = np.linspace(lo, hi, n)
    ys = []
    scan = dict(points=n, parse=0, domain=0, nonfinite=0)
    for x in xs:
        try:
            ys.append(f(float(x)))
        except ConfigError:  # Outside the parse's: no point there.
            scan["parse"] += 1
            ys.append(np.nan)
        except Refused:  # Outside a law's domain: no point there.
            scan["domain"] += 1
            ys.append(np.nan)
    ys = np.asarray(ys, dtype=float)
    ok = np.isfinite(ys)
    scan["nonfinite"] = int(n - np.sum(ok) - scan["parse"] - scan["domain"])
    scan["evaluated"] = int(np.sum(ok))
    SCANS.append(scan)
    signs = [(float(xs[i]), float(xs[i + 1]), float(ys[i]), float(ys[i + 1]))
             for i in range(n - 1) if ok[i] and ok[i + 1] and ys[i] * ys[i + 1] <= 0]  # fmt: skip
    exact = [s for s in signs if s[2] == 0.0 or s[3] == 0.0]
    counted = (f"{scan['evaluated']} of {n} points evaluated; not evaluated: {scan['parse']} "
               f"refused at parse, {scan['domain']} outside a law's domain, "
               f"{scan['nonfinite']} not finite")
    if len(signs) == 0:
        raise Refused(f"no sign change on [{lo}, {hi}] ({counted})", scan=scan)
    if len(signs) > 1 and not (len(exact) and len(signs) <= 2):
        raise Refused(f"{len(signs)} sign changes on [{lo}, {hi}]: no unique root ({counted})",
                      scan=scan)  # fmt: skip
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


def recorded(pair):
    """A cached (root, reparsed_equal): the flag joins the current row's record."""
    REPARSED.append(bool(pair[1]))
    return pair[0]


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


def symport_kw(n, na_in, na_out, b_out, r_b, temperature, *, capacity=None, d=None, version=1):
    """xc0_worlds' keywords of symport_world's world."""
    base = d["symporter_v1"]["capacity_fmol_per_s"]["base"]
    k = base if capacity is None else capacity
    kw = dict(cells=(("cell_1", "primary"),), exterior_name="bath", temperature_K=temperature,
              cell_mm={"cell_1": {"Na": na_in, "B": r_b * b_out}},
              exterior_mm={"Na": na_out, "B": b_out})  # fmt: skip
    if version == 1:
        kw["symport"] = {"cell_1": (k, int(n))}
    else:
        kw["diagram"] = {"cell_1": k}
    return kw


def symport_world(n, na_in, na_out, b_out, r_b, temperature, *, capacity=None, d=None,
                  version=1):  # fmt: skip
    """One cell (the primary set's other ions) facing a held bath (0.1x MMR's other ions), Na and
    B at the key's values; the symporter version 1 (n_Na = n) or version 2 on m_main."""
    d = W.inputs() if d is None else d
    world = World(d, **symport_kw(n, na_in, na_out, b_out, r_b, temperature, capacity=capacity, d=d,
                                  version=version))  # fmt: skip
    world.domain = SYM_DOMAIN
    return world


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


def anchor_terms_fmol(raw):
    """The largest magnitude among the charge-anchor terms of a definition's nodes (fmol): each
    node's fixed background and its ionic sum, whose two roundings surface_tissue.check_definition's
    absolute 1e-20 C test meets (D332). Arithmetic on the definition's entries: nothing is
    parsed."""
    z = {s["id"]: s["valence"] for s in raw["model"]["species"]}
    largest = 0.0
    for node in (*raw["model"]["cells"], *raw["model"]["extracellular"]):
        ionic = math.fsum(z[s] * a for s, a in node["initial_amount_fmol"].items())
        largest = max(largest, abs(node["fixed_charge_equivalent_fmol"]), abs(ionic))
    return largest


def eq_anchor_terms(n, na_in, na_out, b_out, temperature, domain, *, d=None):
    """The largest charge-anchor term over an equilibrium-ratio scan's worlds (fmol). Each term is
    linear in B_in, so its magnitude is largest at an end of the domain: both ends are built."""
    d = W.inputs() if d is None else d
    return max(anchor_terms_fmol(W.world(d=d, **symport_kw(n, na_in, na_out, b_out, r, temperature,
                                                           d=d)))  # fmt: skip
               for r in domain)


def eq_ratio_e2(n, na_in, na_out, b_out, temperature, v, *, domain, bound, d=None):
    """Erratum 2 (D333): the root over B_in/B_out of J at a fixed V on `domain`, at the reader's
    B_out, each B_in a parsed world; refused before any world is parsed when a world of the scan
    would hold a charge-anchor term at or beyond `bound` fmol, where the parse's absolute 1e-20 C
    check can refuse a correctly built world (D332)."""
    terms = eq_anchor_terms(n, na_in, na_out, b_out, temperature, domain, d=d)
    if not terms < bound:
        raise Refused(f"the scan's worlds reach a charge-anchor term of {terms:.6g} fmol, not "
                      f"below {bound:g} fmol (erratum 2): B_out {b_out:g} mM on "
                      f"{list(domain)}")  # fmt: skip

    def j(r):
        return mode_value(symport_world(n, na_in, na_out, b_out, r, temperature, d=d), v, "j")

    return log_root(j, *domain)


# ------------------------------------------------------------------ runs


WINDOW_STEPS = 10000  # Accepted steps per window of the scalar window path.
KEEP = ("times", "membrane_voltage_V", "amount", "extracellular_amount", "membrane_transferred",
        "extracellular_potential_V", "channel_transferred", "passive_transferred",
        "pump_cycles")  # fmt: skip  # The last three where the world's model records them.


def windowed(spec, checkpoint=None, keep=KEEP):
    """A run of a parsed definition through the engine's scalar window path (cells.execution.
    windows.iter_windows, which runs X2 where the definition selects it), from its start or from a
    checkpoint, keeping the named observation fields; the windows' diagnostics are merged by their
    maxima; a field the model does not record is left out. Returns (fields, diagnostics, final
    checkpoint)."""
    from cells.execution.windows import WindowPolicy, iter_windows

    policy = WindowPolicy(window_steps=WINDOW_STEPS, recording="observations")
    parts, diagnostics, final = {f: [] for f in keep}, {}, None
    for window in iter_windows(spec, policy, checkpoint):
        for f in keep:
            if hasattr(window.observations, f):
                parts[f].append(np.asarray(getattr(window.observations, f)))
        for k, v in window.diagnostics.items():
            if isinstance(v, (int, float, np.floating, np.integer)) and np.isfinite(v):
                diagnostics[k] = max(diagnostics.get(k, -math.inf), float(v))
        final = window.final
    return {f: np.concatenate(v) for f, v in parts.items() if v}, diagnostics, final


def trajectory(world_kw, end_time, *, d=None, x2_cap, dt=None, every=1):
    """A run of the world (xc0_worlds keywords) at the step factor, observed every `every`
    accepted steps, with X2 at the cap."""
    d = W.inputs() if d is None else d
    dt = float(d["execution"]["dt_s"]) * STEP["factor"] if dt is None else float(dt)
    steps = int(round(end_time / dt))
    times = [k * dt for k in range(0, steps + 1, every)]
    if times[-1] != steps * dt:
        times.append(steps * dt)
    raw = W.world(d=d, dt=dt, end_time=steps * dt, observation_times=times,
                  energy_check_cap=x2_cap, **world_kw)  # fmt: skip
    started = time.perf_counter()
    spec = parse_spec(raw)
    o, diagnostics, _ = windowed(spec)
    membranes = [m.id for m in spec.model.membranes]
    cells = [c.id for c in spec.model.cells]
    voltage = o["membrane_voltage_V"]
    inside = {m.id: m.inside for m in spec.model.membranes}
    routes = dict(spec.model.kinds).get("cells.passive_routes@1", ())
    return dict(
        t=np.asarray(o["times"], dtype=float),
        V={c: voltage[:, membranes.index(f"m_main_{c}")] for c in cells},
        amount=o["amount"],  # [t, species, cell]
        outside=o["extracellular_amount"],  # [t, species, outside node]
        transferred=o["membrane_transferred"],  # [t, species, membrane], cumulative outward
        membranes=membranes,
        membrane_cell=[m.inside for m in spec.model.membranes],
        # A channel population's and a route's transfers are their own records, not the patch's:
        # [t, species, channel] cumulative outward; [t, species, route] cumulative inward.
        channel_transferred=o.get("channel_transferred"),
        channel_cell=[inside[c.membrane_id] for c in spec.model.channels],
        route_transferred=o.get("passive_transferred"),
        route_cell=[r.inside for r in routes],
        pump_cycles=o.get("pump_cycles"),
        species=list(spec.model.species_ids),
        cells=cells,
        outside_ids=[x.id for x in spec.model.extracellular],
        valence=np.asarray(spec.model.valence, dtype=float),
        fixed={c.id: c.fixed_charge_equivalent_fmol for c in spec.model.cells},
        c_total=W.total_capacitance(d) * world_kw.get("scale_capacitance", 1.0),
        diagnostics=diagnostics,
        seconds=time.perf_counter() - started,
    )


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


def linear_at(t, y, when):
    """y at time `when`, interpolated linearly between the two accepted steps around it (for a
    residual, which may change sign); the step's own value where `when` is one."""
    i = int(np.searchsorted(t, when))
    if i < len(t) and t[i] == when:
        return float(y[i])
    if i == 0 or i >= len(t):
        raise Refused(f"time {when} outside the run")
    w = (when - t[i - 1]) / (t[i] - t[i - 1])
    return float((1 - w) * y[i - 1] + w * y[i])


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
    return recorded(cached(cache, key, lambda: v_zero(leaks_world(state_of(params), d, **extra))))


def m_e_zero(params, *, d, cache, **_):
    """C0 E_<ion>, C1 zero_<ion>, the route's zero: the ion's zero through its conductor."""
    ion = params["ion"]
    key = ("e_zero", state_of(params), ion, params.get("g"))
    world = ion_world(state_of(params), ion, d, float(params.get("g", G_REF)))
    return recorded(cached(cache, key, lambda: e_zero(world, ion)))


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
    if "V" in params:  # Erratum 1: C0.cl_i_threshold_V<V> holds V fixed at the family's value.
        rest = float(params["V"])
    else:
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
    return scenario_zero(params, d, cache)[1]


def m_c3_v_inf(params, *, d, cache, **_):
    """C3's V_inf (erratum 1): the scenario world's zero-current voltage (dV/dt's root)."""
    return scenario_zero(params, d, cache)[0]


def m_c3_g(params, *, d, cache, **_):
    """C3's g (erratum 1): the membrane's slope conductance at V_inf, C_total / tau_lin, i.e.
    -C_total d(dV/dt)/dV, the engine's slope with the declared total capacitance (S)."""
    return W.total_capacitance(W.inputs() if d is None else d) / scenario_zero(params, d, cache)[1]


def m_c3_tau_doubling(params, *, d, cache, **_):
    """C3's tau_doubling (erratum 1): tau_lin of the scenario world with every patch's capacitance
    doubled over tau_lin with the declared ones, each at its own zero (the same voltage)."""
    v, tau = scenario_zero(params, d, cache)
    doubled = scenario_world(params, d, scale_capacitance=2.0)
    return tau_lin(doubled, v_zero(doubled)[0]) / tau


# ------------------------------------------------------------------ scenarios (runs)

# C3's scenarios that DESIGN §4 and the interface's documented names define. The rest of the
# references' S2-S8 are not documented outside their family notes: each joins this table by a
# dated erratum that states its world (the rule's readings_to_confirm), never by a guess.
SCENARIOS = {  # Erratum 1: the confirmer's SEMANTICS.md, section 3 (S2-S8 as stated there).
    "S1_leaks_bath": dict(state=("primary", "bath", 291.15)),
    "S2_glycine1e-8_bath": dict(state=("primary", "bath", 291.15),
                                extra=dict(glycine={"cell_1": (1e-8, 1.0)})),
    "S3_glycine3e-8_bath": dict(state=("primary", "bath", 291.15),
                                extra=dict(glycine={"cell_1": (3e-8, 1.0)})),
    "S4_glycine1e-8_bath70Na": dict(state=("primary", "bath70_Na", 291.15),
                                    extra=dict(glycine={"cell_1": (1e-8, 1.0)})),
    "S5_glycine1e-8_bath70inert": dict(state=("primary", "bath70_inert", 291.15),
                                       extra=dict(glycine={"cell_1": (1e-8, 1.0)})),
    "S6_kir3_bath": dict(state=("primary", "bath", 291.15), extra=dict(kir={"cell_1": (3.0, 1.0)})),
    "S7_leaks_bath_Clhigh": dict(state=("bracket_Cl_high", "bath", 291.15)),
    "S8_leaks_bath_secondhand": dict(state=("bracket_second_hand_table", "bath", 291.15)),
    "S9_leaks_bath_T287": dict(state=("primary", "bath", 287.15)),
}  # fmt: skip


def scenario_key(params):
    return json.dumps({k: params[k] for k in sorted(params) if k not in ("k", "delta")},
                      sort_keys=True, default=str)  # fmt: skip


def scenario_world(params, d, **more):
    s = SCENARIOS.get(params.get("scenario"))
    if s is None:
        raise Refused(f"scenario {params.get('scenario')!r} has no declared world")
    return leaks_world(s["state"], d, **s.get("extra", {}), **more)


def scenario_run_kw(name, v0):
    """A scenario's world as the run's keywords, its cell anchored at v0."""
    s = SCENARIOS[name]
    ion_set, exterior_name, temperature = s["state"]
    return dict(cells=(("cell_1", ion_set),), exterior_name=exterior_name,
                temperature_K=temperature, v0=v0, **s.get("extra", {}))  # fmt: skip


def scenario_zero(params, d, cache):
    """(V_inf, tau_lin) of a scenario's world: the engine's zero-current voltage and its linear
    time constant there."""

    def make():
        world = scenario_world(params, d)
        v = v_zero(world)
        return v[0], tau_lin(world, v[0]), v[1]

    v, tau, equal = cached(cache, ("scenario_zero", params["scenario"]), make)
    REPARSED.append(bool(equal))
    return v, tau


def relaxation(params, *, d, x2_cap, cache):
    """C3: the run from V_inf + delta (the engine's own zero-current voltage) to RUN_TAUS tau_lin, its
    observations at every accepted step, with the engine's tau_lin."""
    key = ("relax", scenario_key(params), float(params["delta"]), STEP["factor"])

    def make():
        v_inf, tau = scenario_zero(params, d, cache)
        kw = scenario_run_kw(params["scenario"], v_inf + float(params["delta"]))
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
    recorded amounts and the cell's fixed background (C). Superseded for the rows by
    m_c3_q_minus_cv (erratum 1)."""
    r = relaxation(params, d=d, x2_cap=x2_cap, cache=cache)
    traj = r["traj"]
    q = cell_charge(traj, "cell_1")
    return float(np.max(np.abs(q - traj["c_total"] * traj["V"]["cell_1"])))


def m_c3_q_minus_cv(params, *, d, x2_cap, cache, **_):
    """C3's Q_over_CV_error (erratum 1): Q(t_k) - C_total V(t_k) at t_k = k tau_lin / 4 of the
    run, Q the cell's charge from its recorded amounts and fixed background, the residual read
    linearly between the two accepted steps around t_k (C)."""
    r = relaxation(params, d=d, x2_cap=x2_cap, cache=cache)
    traj = r["traj"]
    residual = cell_charge(traj, "cell_1") - traj["c_total"] * traj["V"]["cell_1"]
    return linear_at(traj["t"], residual, int(params["k"]) * r["tau_lin"] / 4.0)


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
    return recorded(cached(cache, key, lambda: stall(sym_world(params, d))))


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
    return recorded(cached(cache, key, lambda: stall(sym_world(params, d, version=2))))


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

C8_END_S = 64.0  # s: the P1LB runs' horizon (erratum 1: the reference's runs end at 64 s).
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

# ================================================================== erratum 1 (23 November 2026)
# The readings the confirmer's SEMANTICS.md (sha256 56b5fd5c...) defines, each from the engine's own
# outputs; the reader's erratum mapping names which family reads which.


def m_feasible_19p4(params, *, d, cache, **_):
    """C0.feasible_19p4_area: V_rest - E_Cl >= 19.4 mV (T2's published magnitude), from the engine's
    zero-current voltage and its Cl- zero at the state."""
    rest = m_v_zero({k: params[k] for k in STATE_KEYS}, d=d, cache=cache)
    e_cl = m_e_zero(dict({k: params[k] for k in STATE_KEYS}, ion="Cl"), d=d, cache=cache)
    return bool(rest - e_cl >= 0.0194)


def route_at_ek(params, d, cache, offset):
    """The route's outward current (A) at the state's E_K + offset, g_ref 1 S/m2 and availability 1,
    E_K the engine's K+ zero through m_kleak (the constant-field K leak), not the route's own."""
    state = {k: params[k] for k in STATE_KEYS}
    e_k = m_e_zero(dict(state, ion="K"), d=d, cache=cache)
    world = ion_world(state_of(params), "Kir", d, G_REF)
    return world, e_k + offset


def m_kir_current_ek(params, *, d, cache, **_):
    """C1.kir_zero_at_EK (u 0) and C1.kir_I_u<u>: the route's current at E_K + u (A)."""
    world, v = route_at_ek(params, d, cache, float(params.get("u", 0.0)))
    return ion_current_at(world, "Kir", v)


def m_kir_slope_ek(params, *, d, cache, **_):
    """C1.kir_slope_u<u>: the route's slope dI/dV at E_K + u, the central difference of its
    current (S)."""
    world, v = route_at_ek(params, d, cache, float(params["u"]))
    return slope(lambda x: ion_current_at(world, "Kir", x), v)


def m_kir_sqrtko_ratio(params, *, d, cache, **_):
    """C1.kir_sqrtKo_ratio: the route's current at E_K + 0.02 V with the local exterior over the
    same with the bath, the ion set and T of the key, each at its own E_K."""
    out = []
    for exterior_name in ("local", "bath"):
        state = dict(ion_set=params["ion_set"], exterior=exterior_name, T=float(params["T"]))
        world, v = route_at_ek(state, d, cache, 0.02)
        out.append(ion_current_at(world, "Kir", v))
    return out[0] / out[1]


def m_c4_flux_at_a0(params, *, d, cache, **_):
    """C4.flux_at_a0: the route's current (declared at g_ref 3 S/m2) plus GlyR's Cl current
    (declared at P_GlyR 3e-8 m/s), both at availability 0, at the key's voltage (A)."""
    world = leaks_world(state_of(params), d, kir={"cell_1": (3.0, 0.0)},
                        glycine={"cell_1": (3e-8, 0.0)})  # fmt: skip
    b = world.at(float(params["V"]))
    return world.current(b, "K", "m_kir") + world.current(b, "Cl", "m_glycine")


LEVELS = (0.0, 0.25, 0.5, 0.75, 1.0)
P_GRID = (1e-9, 3e-9, 1e-8, 3e-8)
G_GRID = (0.1, 0.3, 1.0, 3.0)


def m_c4_monotone_kir(params, *, d, cache, **_):
    """C4.monotone_kir: for every g_ref of the grid, V_zero over the availabilities 0 to 1 falls
    at every step (strictly) and never lies below E_K (the engine's K+ zero): exact comparisons
    on the engine's roots, as the reference's."""
    state = {k: params[k] for k in STATE_KEYS}
    e_k = m_e_zero(dict(state, ion="K"), d=d, cache=cache)
    for g in G_GRID:
        zs = [m_v_zero(dict(state, g=g, a=a), d=d, cache=cache) for a in LEVELS]
        if any(b - a >= 0 for a, b in zip(zs, zs[1:], strict=False)) or any(z < e_k for z in zs):
            return False
    return True


def m_c4_monotone_glycine(params, *, d, cache, **_):
    """C4.monotone_glycine: for every P_GlyR of the grid, with sigma = sign(E_Cl - V_zero(0)),
    every step of V_zero over the availabilities 0 to 1 has the sign sigma and every level has
    (V_zero - E_Cl) sigma <= 0: exact comparisons on the engine's roots, as the reference's."""
    state = {k: params[k] for k in STATE_KEYS}
    e_cl = m_e_zero(dict(state, ion="Cl"), d=d, cache=cache)
    for p in P_GRID:
        zs = [m_v_zero(dict(state, P=p, a=a), d=d, cache=cache) for a in LEVELS]
        sigma = np.sign(e_cl - zs[0])
        if any(np.sign(b - a) != sigma for a, b in zip(zs, zs[1:], strict=False)):
            return False
        if any((z - e_cl) * sigma > 0 for z in zs):
            return False
    return True


def m_c5_v_limit(params, *, d, cache, **_):
    """C5.V_limit: the root over V of dV1/dt + dV2/dt with both cells at V (the junction then
    carries nothing), the scenario's two cells."""
    world = two_cell_world(dict(params, x=1.0), d)
    v = root(lambda x: world.dvdt(world.at(x), "cell_1") + world.dvdt(world.at(x), "cell_2"),
             *world.domain)  # fmt: skip
    return v


def junction_current(world, b):
    """The junction's current from its sender to its receiver (A): CHARGE_PER_FMOL sum z J, J the
    engine's junction flux readout."""
    flux = np.asarray(b.values.field.rates.junction_flux_fmol_s)[:, 0]
    return CHARGE_PER_FMOL * float(np.sum(np.asarray(world.spec.model.valence) * flux))


def m_c5_g_j(params, *, d, cache, **_):
    """C5.g_J: the declared junction's slope conductance at V1 = V2 (S): the central difference of
    its current over V1 - V2, both cells about the declared anchor V0, the junction at x1."""
    world = two_cell_world(dict(params, x=1.0), d)
    h = SLOPE_STEP_V

    def current(dv):
        return junction_current(world, world.at({"cell_1": W.V0 + dv / 2, "cell_2": W.V0 - dv / 2}))

    return (current(h) - current(-h)) / (2 * h)


def m_c5_g_m(params, *, d, cache, **_):
    """C5.g_m: a cell's membrane slope conductance at its own uncoupled zero-current voltage (S):
    cell1 the leaks alone, cell2 the leaks and the scenario's element; C_total / tau_lin."""
    extra = {}
    if params.get("cell") == "cell2":
        if "kir_g" in params:
            extra["kir"] = {"cell_1": (float(params["kir_g"]), 1.0)}
        if "x_gly" in params:
            extra["glycine"] = {"cell_1": (float(params["x_gly"]), 1.0)}
    world = leaks_world(("primary", "bath", 291.15), d, **extra)
    v = v_zero(world)[0]
    return W.total_capacitance(W.inputs() if d is None else d) / tau_lin(world, v)


def c5_modes(params, d, cache):
    """The scenario's steady voltages at x1 and its two modes: (V_ss, [(lambda, v) slow, fast])."""

    def make():
        world = two_cell_world(dict(params, x=1.0), d)
        v1, v2 = two_cell_steady(world)
        values, vectors = np.linalg.eig(two_cell_jacobian(world, v1, v2))
        values, vectors = np.real(values), np.real(vectors)
        order = np.argsort(-values)  # The slower mode (lambda nearer 0) first.
        modes = []
        for i in order:
            v = vectors[:, i] / np.linalg.norm(vectors[:, i])
            modes.append((float(values[i]), v if v[0] > 0 else -v))
        return np.array([v1, v2]), modes

    return cached(cache, ("c5_modes", json.dumps(params, sort_keys=True, default=str)), make)


def m_c5_tau_fit(mode):
    def reading(params, *, d, x2_cap, cache, **_):
        v_ss, modes = c5_modes(params, d, cache)
        lam, v = modes[0 if mode == "common" else 1]
        tau = -1.0 / lam
        start = v_ss + v * (0.002 / np.max(np.abs(v)))
        key = ("c5_fit", mode, json.dumps(params, sort_keys=True, default=str), STEP["factor"])

        def make():
            kw = dict(two_cell_world(dict(params, x=1.0), d).kw,
                      v0={"cell_1": float(start[0]), "cell_2": float(start[1])})  # fmt: skip
            return trajectory(kw, 1.25 * tau, d=d, x2_cap=x2_cap)

        traj = cached(cache, key, make)
        a = v[0] * (traj["V"]["cell_1"] - v_ss[0]) + v[1] * (traj["V"]["cell_2"] - v_ss[1])
        return -tau / math.log(at_time(traj["t"], a, tau) / a[0])

    reading.__doc__ = (f"C5.tau_fit_{mode} (erratum 1): from the engine's steady voltages at x1 plus "
                       "0.002 V along the mode's eigenvector of the engine's Jacobian (its largest "
                       "component), the run to tau_m = -1/lambda of that mode; a(t) = v . (V(t) - "
                       "V_ss); tau_fit = -tau_m / ln(a(tau_m) / a(0)), a(tau_m) read as at_time does.")
    return reading


def own_outward_charge(traj, cell):
    """The charge (C) that has left the cell through its own patches, channel populations and
    routes by each observation: e sum_s z_s of the engine's cumulative records (membrane_ and
    channel_transferred outward, passive_transferred inward). Refused where a pump has cycled,
    whose transfers these records do not carry."""
    if traj["pump_cycles"] is not None and np.any(np.asarray(traj["pump_cycles"]) != 0):
        raise Refused("a pump cycled: its transfers are not booked here")
    z = traj["valence"][None, :, None]
    moved = np.zeros(len(traj["t"]))
    for record, owners, sign in (("transferred", traj["membrane_cell"], 1.0),
                                 ("channel_transferred", traj["channel_cell"], 1.0),
                                 ("route_transferred", traj["route_cell"], -1.0)):  # fmt: skip
        own = [i for i, c in enumerate(owners) if c == cell]
        if own:
            moved += sign * np.sum(z * np.asarray(traj[record])[:, :, own], axis=(1, 2))
    return CHARGE_PER_FMOL * moved


def m_c5_junction_charge_sum(params, *, d, x2_cap, cache, **_):
    """C5.junction_charge_sum: the run of the scenario's two cells at x1 from the declared anchor
    V0 = -0.04 V (both) to 4 tau_common, every 10 accepted steps observed; at each observation,
    the junction's charge into each cell is its charge change from its recorded amounts plus the
    charge that has left through its own patches, channel populations and routes
    (own_outward_charge); the reading is the largest |sum over the two cells| (C), the junction's
    own conservation through the engine's records."""
    key = ("c5_charge", json.dumps(params, sort_keys=True, default=str), STEP["factor"])

    def make():
        _, modes = c5_modes(params, d, cache)
        kw = dict(two_cell_world(dict(params, x=1.0), d).kw, v0=W.V0)
        return trajectory(kw, 4 * (-1.0 / modes[0][0]), d=d, x2_cap=x2_cap, every=10)

    traj = cached(cache, key, make)
    total = np.zeros(len(traj["t"]))
    for cell in traj["cells"]:
        q = cell_charge(traj, cell)
        total += (q - q[0]) + own_outward_charge(traj, cell)
    return float(np.max(np.abs(total)))


def m_sym_dj_dv(params, *, d, cache, **_):
    """C6.v1_dJdV_at_stall: the transporter probe's dJ/dV (the engine's own derivative,
    fmol/s/V) at the key's voltage (the engine's stall with off 0)."""
    world = sym_world(params, d)
    return mode_value(world, sym_voltage(params, d, cache), "d_j_d_v")


def m_sym_ratio(params, *, d, cache, **_):
    """C6.v1_ratio_Jm_Jp: J-/J+ of the transporter probe at the key's voltage."""
    world = sym_world(params, d)
    v = sym_voltage(params, d, cache)
    return mode_value(world, v, "j_minus") / mode_value(world, v, "j_plus")


def m_sym_eq_x(params, *, d, cache, **_):
    """C6.v1_eq_x: x = dG_cyc/RT of the probe at B_in = the engine's equilibrium ratio times
    B_out, at the key's voltage."""
    n, na_in, na_out, b_out, _, temperature = sym_params(dict(params, rB=1.0))
    v = sym_voltage(params, d, cache)
    ratio = eq_ratio(n, na_in, na_out, b_out, temperature, v, d=d)
    return mode_value(symport_world(n, na_in, na_out, b_out, ratio, temperature, d=d), v, "x")


def eq_ratio_e2_of(params, d, cache):
    """Erratum 2's equilibrium ratio at a row's parameters (B_out, domain and anchor bound from the
    reader's settings, carried in the row's parameters), found afresh for each row as erratum 1's
    x row finds it: (ratio, V)."""
    n, na_in, na_out, b_out, _, temperature = sym_params(dict(params, rB=1.0))
    v = sym_voltage(params, d, cache)
    domain = (float(params["domain"][0]), float(params["domain"][1]))
    ratio = eq_ratio_e2(n, na_in, na_out, b_out, temperature, v, domain=domain, d=d,
                        bound=float(params["anchor_bound_fmol"]))  # fmt: skip
    return ratio, v


def m_sym_eq_ratio_e2(params, *, d, cache, **_):
    """C6.v1_eq_ratio (erratum 2): the root over B_in/B_out of J at the key's voltage, at the
    reader's B_out on the reader's domain, every world of the scan within the anchor bound."""
    return eq_ratio_e2_of(params, d, cache)[0]


def m_sym_eq_x_e2(params, *, d, cache, **_):
    """C6.v1_eq_x (erratum 2): x = dG_cyc/RT of the probe at B_in = erratum 2's equilibrium ratio
    times B_out, at the key's voltage."""
    ratio, v = eq_ratio_e2_of(params, d, cache)
    n, na_in, na_out, b_out, _, temperature = sym_params(dict(params, rB=1.0))
    return mode_value(symport_world(n, na_in, na_out, b_out, ratio, temperature, d=d), v, "x")


def m_sym_s_at(params, *, d, cache, **_):
    """C6.S_hill: the probe's saturation S at the P end's Na (NaP) and B (BP); the factored form's
    S reads the P end alone (the N end and V of the world: the primary set, -0.04 V)."""
    world = symport_world(2, 21.0, float(params["NaP"]), float(params["BP"]), 1.0, 291.15, d=d)
    return mode_value(world, W.V0, "s")


def pump_world(params, d):
    """P1 (bath) or P1L (local) at the primary set, 291.15 K, the pump at availability 1."""
    return World(d, cells=(("cell_1", "primary"),), exterior_name=params["exterior"],
                 temperature_K=float(params.get("T", 291.15)), pump={"cell_1": 1.0})  # fmt: skip


def pump_voltage(params, d, cache):
    if params.get("word") == "Vghk":
        return m_v_zero(dict(ion_set="primary", exterior=params["exterior"],
                             T=float(params.get("T", 291.15))), d=d, cache=cache)  # fmt: skip
    return float(params["V"])


def m_pump_at(field):
    def reading(params, *, d, cache, **_):
        world = pump_world(params, d)
        k = world.patch("m_main")

        def total(v):
            return float(np.asarray(world.at(v).values.pump_affinity_J_mol)[k])

        v = pump_voltage(params, d, cache)
        b = world.at(v)
        cycles = float(np.asarray(b.values.derivative.pump_cycles)[k])
        dg_atp = -1e3 * float(np.asarray(b.values.derivative.metabolic_work_pJ)[k]) / cycles
        if field == "dG_atp":
            return dg_atp
        at_v, at_0 = total(v), total(0.0)
        if field == "dG_chem":
            return at_0 - dg_atp
        if field == "dU_cap":
            return at_v - at_0
        if field == "heat":
            return -at_v
        return bool(-at_v >= 0.0)

    reading.__doc__ = (f"C7.pump_{field} (erratum 1), per cycle at the key's state and voltage "
                       "(-0.04 V or Vghk, the engine's zero-current voltage there): dG_atp = -1e3 "
                       "metabolic power / cycle rate; the cycle's free energy G(V) is the engine's "
                       "pump affinity; dG_chem = G(0) - dG_atp; dU_cap = G(V) - G(0); heat = -G(V); "
                       "heat_nonneg heat >= 0 (J/mol).")
    return reading


def m_pump_outward_charge(params, *, d, cache, **_):
    """C7.pump_cycle_counts outward_charge: the net charge leaving the cell per cycle (e), from
    the pump's patch flux over its cycle rate (the leaks closed)."""
    return -m_pump("cell_charge_per_fmol")(params, d=d, cache=cache) / CHARGE_PER_FMOL


def m_sym_partition(field):
    def reading(params, *, d, cache, **_):
        world = sym_world(params, d)
        v = sym_voltage(params, d, cache)
        rt = R * float(params.get("T", 291.15))
        x_v, x_0 = mode_value(world, v, "x"), mode_value(world, 0.0, "x")
        if field == "dG_chem":
            return rt * x_0
        if field == "dU_cap":
            return rt * (x_v - x_0)
        if field == "heat_per_cycle":
            return -rt * x_v
        heat = float(np.asarray(world.cycle_modes_full(world.at(v)).populations.heat_pJ_s)[0])
        return 1e3 * heat if field == "heat_power" else bool(heat >= 0.0)

    reading.__doc__ = (f"C7.sym_{field} (erratum 1) at the C6 offset key's state and voltage: "
                       "dG_chem = R T x(0) (the probe's x with the electrical term at V = 0); dU_cap "
                       "= R T (x(V) - x(0)); heat_per_cycle = -R T x(V) (J/mol); heat_power = the "
                       "kind's booked heat rate (heat_pJ_s, in fW); heat_nonneg: that rate >= 0.")
    return reading


SYM_COUNT_STATE = dict(Nain=21.0, Naout=9.9, BP=10.0, rB=1.0, T=291.15, V=-0.0899)


def m_sym_counts(params, *, d, cache, **_):
    """C7.sym_cycle_counts: per cycle, from the transporter probe's row rates over its J at one
    state (the primary cell's Na 21 mM, Na_P 9.9, B 10 mM both sides, -0.0899 V): the cell's Na
    and B gain (dNa_in, dB_in), the outside's (dNa_out, dB_out), and the charge carried inward
    (charge_inward, e)."""
    world = sym_world(dict(SYM_COUNT_STATE, n=int(params["n"])), d)
    probe = world.cycle_modes_full(world.at(SYM_COUNT_STATE["V"]))
    j = float(np.asarray(probe.modes.j)[0, 0])
    rows = probe.rows
    species = world.species
    out = {}
    for k in range(int(np.sum(np.asarray(rows.present)[:, 0]))):
        name = species[int(np.asarray(rows.species)[k, 0])]
        end = "in" if bool(np.asarray(rows.at_n)[k, 0]) else "out"
        out[f"d{name}_{end}"] = float(np.asarray(rows.rate)[k, 0]) / j
    out["charge_inward"] = out["dNa_in"] - out["dB_in"]  # Na+ at +1, B- at -1.
    return out[params["word"]]


# ------------------------------------------------------------------ C7's relaxations (erratum 1)


def c7_scenario_relaxation(name, *, d, x2_cap, cache):
    """C7 (erratum 1): the scenario's world (S1, S2 or S4) from the declared anchor V0 = -0.04 V,
    its amounts evolving, to RUN_TAUS tau_lin of that scenario (k <= 24 needs 6), every accepted
    step observed."""

    def make():
        _, tau = scenario_zero(dict(scenario=name), d, cache)
        traj = trajectory(scenario_run_kw(name, W.V0), RUN_TAUS * tau, d=d, x2_cap=x2_cap)
        return dict(tau_lin=tau, traj=traj)

    return cached(cache, ("c7_relax", name, STEP["factor"]), make)


def m_c7_relax(field):
    def reading(params, *, d, x2_cap, cache, **_):
        r = c7_scenario_relaxation(params["scenario"], d=d, x2_cap=x2_cap, cache=cache)
        traj = r["traj"]
        when = int(params["k"]) * r["tau_lin"] / 4.0
        dq_v = traj["c_total"] * (traj["V"]["cell_1"] - W.V0)
        if field == "dQ":
            return at_time(traj["t"], dq_v, when)
        species = traj["species"]
        k = traj["cells"].index("cell_1")
        ionic = CHARGE_PER_FMOL * sum(
            traj["valence"][species.index(s)] * (traj["amount"][:, species.index(s), k]
                                                 - traj["amount"][0, species.index(s), k])
            for s in ("Na", "K", "Cl"))  # fmt: skip
        return linear_at(traj["t"], dq_v - ionic, when)

    reading.__doc__ = (f"C7.relax_{'dQ' if field == 'dQ' else 'charge_identity'} (erratum 1), at "
                       "t_k = k tau_lin / 4 of the scenario's run: dQ = C_total (V(t_k) - V0); the "
                       "identity C_total (V(t_k) - V0) - CHARGE_PER_FMOL sum z dn(t_k) over Na, K "
                       "and Cl (C).")
    return reading


# ------------------------------------------------------------------ C8 (b): saved runs (erratum 1)

C8_RUNS = {"dir": None}  # The folder of the saved P1LB runs (xc0_engine c8b-run), set by `table`.


def c8b_horizon(reading):
    """Erratum 2: a P1LB reading's horizon (s), the reader's setting: the bare run's reaches the
    node's end state, the coupled run's stays erratum 1's 64 s."""
    from validation.xenopus_bioelectric.xc0_compare import SETTINGS

    return float(SETTINGS["c8b_horizon_s"][reading])


def c8b_definition(reading, factor, until, *, d, x2_cap, v0):
    """P1LB at the primary set, 291.15 K: `coupled`, the cell's leaks open (no pump, route or
    GlyR), starting at v0, the engine's zero-current voltage of the primary set against the local
    node (SEMANTICS.md); `bare`, every patch closed (v0 the same). Observed every C8_EVERY steps
    of the declared step (the same times at every step factor), to `until` (erratum 2: the grid is
    counted to `until`, which may pass erratum 1's 64 s; to 64 s it is erratum 1's grid)."""
    dd = W.inputs() if d is None else d
    dt = float(dd["execution"]["dt_s"]) * factor
    steps = int(round(max(until, C8_END_S) / dt))
    every = int(round(C8_EVERY / factor))
    times = [k * dt for k in range(0, steps + 1, every) if k * dt <= until + 1e-12]
    leaks = None if reading == "coupled" else {"cell_1": {"m_main": 0.0, "m_kleak": 0.0}}
    return W.world(d=dd, cells=(("cell_1", "primary"),), exterior_name="local", face=True,
                   leaks=leaks, v0=v0, dt=dt, end_time=times[-1], observation_times=times,
                   energy_check_cap=x2_cap)  # fmt: skip


def c8b_segment(reading, factor, until, out, *, x2_cap, resume=None, d=None):
    """One segment of a saved P1LB run, from its start or from the previous segment's snapshot
    (`resume`), to `until` (s): its observations (the local node's concentrations and potential),
    its snapshot for the next segment, and its record (the source, the cap, the diagnostics)."""
    from cells.records.io import load_snapshot, write_snapshot

    if until > c8b_horizon(reading) + 1e-9:
        raise SystemExit(f"refused: {reading}'s horizon is {c8b_horizon(reading)} s (erratum 2), "
                         f"not beyond it to {until} s")  # fmt: skip
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    v0 = m_v_zero(dict(ion_set="primary", exterior="local", T=291.15), d=d, cache={})
    if resume is not None:
        prior = json.loads((Path(resume) / "record.json").read_text())
        if prior["v0"] != v0 or prior["reading"] != reading or prior["factor"] != factor:
            raise SystemExit("refused: the segment does not continue its predecessor")
    started = time.perf_counter()
    spec = parse_spec(c8b_definition(reading, factor, until, d=d, x2_cap=x2_cap, v0=v0))
    checkpoint = None if resume is None else load_snapshot(Path(resume) / "snapshot").checkpoint
    fields, diagnostics, final = windowed(
        spec, checkpoint, keep=("times", "extracellular_amount", "extracellular_potential_V"))
    outside = [x.id for x in spec.model.extracellular]
    k = outside.index("outside_local")
    volume = spec.model.extracellular[k].volume_pL
    np.savez(out / "trajectory.npz", t=np.asarray(fields["times"], dtype=float),
             c=fields["extracellular_amount"][:, :, k] / volume,
             psi=fields["extracellular_potential_V"][:, k])  # fmt: skip
    write_snapshot(out / "snapshot", spec, final)
    record = dict(reading=reading, factor=factor, until=until, v0=v0, resume=resume,
                  species=list(spec.model.species_ids), source=provenance(), x2_cap=x2_cap,
                  diagnostics=diagnostics, seconds=round(time.perf_counter() - started, 1),
                  trajectory_sha256=hashlib.sha256((out / "trajectory.npz").read_bytes()).hexdigest())
    (out / "record.json").write_text(json.dumps(record, indent=1))
    return record


def c8b_loaded(reading, *, x2_cap, horizon=C8_END_S):
    """The saved run of a reading at the current step factor: its segments in order, checked
    against the table's source and cap, joined (a time shared by two segments read once), and
    refused unless it ends at `horizon` (erratum 1's 64 s; erratum 2's reading's horizon)."""
    folder = Path(C8_RUNS["dir"] or "") / f"{reading}-{STEP['factor']:g}"
    if C8_RUNS["dir"] is None or not folder.is_dir():
        raise Refused(f"no saved P1LB run {folder.name}")
    source = provenance()
    ts, cs, psis, species = [], [], [], None
    segments = sorted(folder.iterdir(), key=lambda f: json.loads((f / "record.json").read_text())["until"])
    for seg in segments:
        record = json.loads((seg / "record.json").read_text())
        data = (seg / "trajectory.npz").read_bytes()
        if hashlib.sha256(data).hexdigest() != record["trajectory_sha256"]:
            raise Refused(f"{seg.name}: its trajectory is not its record's")
        if record["source"].get("engine_revision") != source.get("engine_revision") or record[
                "source"].get("snapshot_patch_sha256") != source.get("snapshot_patch_sha256"):  # fmt: skip
            raise Refused(f"{seg.name}: run from another source than the table's")
        if record["x2_cap"] != x2_cap:
            raise Refused(f"{seg.name}: run at another X2 cap than the table's")
        z = np.load(seg / "trajectory.npz")
        keep = np.asarray(z["t"]) > (ts[-1][-1] if ts else -1.0)
        ts.append(np.asarray(z["t"])[keep])
        cs.append(np.asarray(z["c"])[keep])
        psis.append(np.asarray(z["psi"])[keep])
        species = record["species"]
    t = np.concatenate(ts)
    if abs(t[-1] - horizon) > 1e-9:
        raise Refused(f"{folder.name} ends at {t[-1]} s, not {horizon} s")
    return dict(t=t, c=np.concatenate(cs), psi=np.concatenate(psis), species=species)


def saved(cache, reading, horizon, x2_cap):
    """A saved run, loaded once per reading, step factor and horizon."""
    return cached(cache, ("c8b_saved", reading, STEP["factor"], float(horizon)),
                  lambda: c8b_loaded(reading, x2_cap=x2_cap, horizon=float(horizon)))  # fmt: skip


def one_over_e_time(t, y, c_f):
    """The first time (y - c_f)/(y(0) - c_f) falls to 1/e, linear between two observations."""
    frac = (y - c_f) / (y[0] - c_f)
    target = 1.0 / math.e
    i = int(np.argmax(frac <= target))
    if i == 0:
        raise Refused("the species does not reach 1/e within the run")
    w = (frac[i - 1] - target) / (frac[i - 1] - frac[i])
    return float(t[i - 1] + w * (t[i] - t[i - 1]))


def m_c8b_saved(field):
    def reading(params, *, d, x2_cap, cache, **_):
        if field in ("final", "psi_final"):
            r = saved(cache, "bare", C8_END_S, x2_cap)
            if field == "psi_final":
                return float(r["psi"][-1])
            return float(r["c"][-1, r["species"].index(params["species"])])
        r = saved(cache, "coupled", C8_END_S, x2_cap)
        if field == "psi_at":
            return at_time(r["t"], r["psi"], float(params["t"]))
        y = r["c"][:, r["species"].index(params["species"])]
        if field == "at":
            return at_time(r["t"], y, float(params["t"]))
        bare = saved(cache, "bare", C8_END_S, x2_cap)
        c_f = float(bare["c"][-1, bare["species"].index(params["species"])])
        return one_over_e_time(r["t"], y, c_f)

    reading.__doc__ = (f"C8 (b) (erratum 1), from the saved P1LB runs: final (the bare run's node "
                       "concentration at 64 s), psi_final (its node potential), at and psi_at (the "
                       "coupled run's at t), t_e (the coupled run's first time (c(t) - c_f)/(c(0) - "
                       "c_f) falls to 1/e, c_f the bare run's 64 s value, linear between two "
                       f"observations). This one: {field}.")
    return reading


def m_c8b_end(field):
    def reading(params, *, d, x2_cap, cache, **_):
        bare = saved(cache, "bare", params["horizon_s"], x2_cap)
        if field == "end_psi":
            return float(bare["psi"][-1])
        c_f = float(bare["c"][-1, bare["species"].index(params["species"])])
        if field == "end_c":
            return c_f
        r = saved(cache, "coupled", params["coupled_horizon_s"], x2_cap)
        return one_over_e_time(r["t"], r["c"][:, r["species"].index(params["species"])], c_f)

    reading.__doc__ = (f"C8 (b) (erratum 2): 'final' is the bare node's end state, read as the "
                       "saved bare P1LB run's last observation, at its horizon (the row's "
                       "horizon_s, the run refused unless it ends there): end_c its node "
                       "concentration, end_psi its node potential (the bath held at 0), t_e_end "
                       "the coupled run's first time (c(t) - c_f)/(c(0) - c_f) falls to 1/e with "
                       "c_f that end state (the coupled run refused unless it ends at the row's "
                       f"coupled_horizon_s), linear between two observations. This one: {field}.")
    return reading



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
    # Erratum 1 (the confirmer's SEMANTICS.md).
    "feasible_19p4": m_feasible_19p4,
    "kir_current_ek": m_kir_current_ek,
    "kir_slope_ek": m_kir_slope_ek,
    "kir_sqrtko_ratio": m_kir_sqrtko_ratio,
    "c3_v_inf": m_c3_v_inf,
    "c3_g": m_c3_g,
    "c3_tau_doubling": m_c3_tau_doubling,
    "c3_q_minus_cv": m_c3_q_minus_cv,
    "c4_flux_at_a0": m_c4_flux_at_a0,
    "c4_monotone_kir": m_c4_monotone_kir,
    "c4_monotone_glycine": m_c4_monotone_glycine,
    "c5_v_limit": m_c5_v_limit,
    "c5_g_j": m_c5_g_j,
    "c5_g_m": m_c5_g_m,
    "c5_tau_fit_common": m_c5_tau_fit("common"),
    "c5_tau_fit_diff": m_c5_tau_fit("diff"),
    "c5_junction_charge_sum": m_c5_junction_charge_sum,
    "sym_dj_dv": m_sym_dj_dv,
    "sym_ratio": m_sym_ratio,
    "sym_eq_x": m_sym_eq_x,
    "sym_s_at": m_sym_s_at,
    "pump_dG_atp_at": m_pump_at("dG_atp"),
    "pump_dG_chem_at": m_pump_at("dG_chem"),
    "pump_dU_cap_at": m_pump_at("dU_cap"),
    "pump_heat_at": m_pump_at("heat"),
    "pump_heat_nonneg_at": m_pump_at("heat_nonneg"),
    "pump_outward_charge": m_pump_outward_charge,
    "sym_dG_chem": m_sym_partition("dG_chem"),
    "sym_dU_cap": m_sym_partition("dU_cap"),
    "sym_heat_per_cycle": m_sym_partition("heat_per_cycle"),
    "sym_heat_power": m_sym_partition("heat_power"),
    "sym_heat_nonneg": m_sym_partition("heat_nonneg"),
    "sym_counts": m_sym_counts,
    "c7_relax_dQ": m_c7_relax("dQ"),
    "c7_relax_identity": m_c7_relax("identity"),
    "c8b_final_saved": m_c8b_saved("final"),
    "c8b_psi_final_saved": m_c8b_saved("psi_final"),
    "c8b_at_saved": m_c8b_saved("at"),
    "c8b_psi_at_saved": m_c8b_saved("psi_at"),
    "c8b_t_e_saved": m_c8b_saved("t_e"),
    # Erratum 2 (D333).
    "sym_eq_ratio_e2": m_sym_eq_ratio_e2,
    "sym_eq_x_e2": m_sym_eq_x_e2,
    "c8b_end_c": m_c8b_end("end_c"),
    "c8b_end_psi": m_c8b_end("end_psi"),
    "c8b_t_e_end": m_c8b_end("t_e_end"),
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
    # Erratum 1.
    "c3_q_minus_cv", "c5_tau_fit_common", "c5_tau_fit_diff", "c5_junction_charge_sum",
    "c7_relax_dQ", "c7_relax_identity", "c8b_final_saved", "c8b_psi_final_saved", "c8b_at_saved",
    "c8b_psi_at_saved", "c8b_t_e_saved",
    # Erratum 2.
    "c8b_end_c", "c8b_end_psi", "c8b_t_e_end",
})  # fmt: skip


def evaluate(entry, *, d, x2_cap, cache, factor=1.0):
    STEP["factor"] = factor
    REPARSED.clear()
    SCANS.clear()
    try:
        value = encode(measure(entry["measure"], entry["params"], d=d, x2_cap=x2_cap, cache=cache))
        if REPARSED:  # Every root the row read, re-parsed at its anchor: bitwise the same?
            value["reparsed_equal"] = all(REPARSED)
        if SCANS:  # Erratum 2: the row's bracket scans, with the points they did not evaluate.
            value["scans"] = scans_summary()
        return value
    except Refused as exc:
        row = dict(type="refused", reason=str(exc))
        if SCANS:
            row["scans"] = scans_summary()
        return row
    except Exception as exc:  # A failure is recorded, never hidden (the rule's retry reads it).
        return dict(type="error", reason=f"{type(exc).__name__}: {exc}",
                    trace=traceback.format_exc(limit=4))  # fmt: skip
    finally:
        STEP["factor"] = 1.0


def scans_summary():
    """A row's bracket scans (erratum 2): how many, their points, and the points not evaluated."""
    keys = ("points", "evaluated", "parse", "domain", "nonfinite")
    return dict(scans=len(SCANS), **{k: int(sum(s[k] for s in SCANS)) for k in keys})


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
        if entry.get("step_tolerance") is not None:
            row["step_tolerance"] = entry["step_tolerance"]
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


EQ_E2 = ("sym_eq_ratio_e2", "sym_eq_x_e2")


def anchor_bound(manifest, d=None):
    """Erratum 2: for every C6 equilibrium row of a manifest, the largest charge-anchor term of its
    scan's worlds (both ends of its domain at its B_out) against its anchor bound. Arithmetic on the
    worlds' entries at the declared inputs (or d): nothing is parsed and no engine value is read."""
    rows, largest, below = 0, 0.0, True
    for e in manifest["entries"]:
        if e["measure"] not in EQ_E2:
            continue
        p = e["params"]
        n, na_in, na_out, b_out, _, temperature = sym_params(dict(p, rB=1.0))
        terms = eq_anchor_terms(n, na_in, na_out, b_out, temperature, tuple(p["domain"]), d=d)
        rows, largest = rows + 1, max(largest, terms)
        below = below and terms < float(p["anchor_bound_fmol"])
    bounds = {float(e["params"]["anchor_bound_fmol"]) for e in manifest["entries"]
              if e["measure"] in EQ_E2}  # fmt: skip
    return dict(rows=rows, largest_term_fmol=largest, all_below=below, bound_fmol=sorted(bounds))


def invented_inputs():
    """An invented input set (not XC0's: other ion sets, baths, leaks, pump and symporter
    constants), so that an engine value at it reveals nothing about the references (erratum 1's
    development set). A symporter key sets n, the Na concentrations and V, which alone fix the
    equilibrium ratio, so the selfcheck also uses invented keys."""
    d = copy.deepcopy(W.inputs())
    d["ion_sets"]["primary"]["cytosol_mM"] = dict(Na=15.0, K=120.0, Cl=20.0, A=115.0)
    d["ion_sets"]["bracket_Cl_high"]["cytosol_mM"] = dict(Na=17.0, K=110.0, Cl=44.0, A=83.0)
    d["ion_sets"]["bracket_second_hand_table"]["cytosol_mM"] = dict(Na=30.0, K=70.0, Cl=25.0,
                                                                    A=75.0)  # fmt: skip
    v = d["nodes"]["bath"]["node"]["volume_pL"]
    d["nodes"]["bath"]["node"]["initial_amount_fmol"] = dict(Na=100.0 * v, K=3.0 * v, Cl=103.0 * v,
                                                             A=0.0, B=0.0)  # fmt: skip
    lv = d["nodes"]["local"]["node"]["volume_pL"]
    d["nodes"]["local"]["node"]["initial_amount_fmol"] = dict(Na=60.0 * lv, K=8.0 * lv,
                                                              Cl=40.0 * lv, A=28.0 * lv,
                                                              B=0.0)  # fmt: skip
    for m in d["membranes"]:
        if m["id"] == "m_main":
            m["permeability_m_per_s"] |= dict(Na=1.1e-9, Cl=4.0e-10)
        if m["id"] == "m_kleak":
            m["permeability_m_per_s"] |= dict(K=3.3e-9)
        if m.get("pump"):
            m["pump"]["metabolism"] |= dict(atp_mM=4.0, adp_mM=0.3, pi_mM=2.0,
                                            delta_g0_J_per_mol=-31000.0)  # fmt: skip
            m["pump"]["capacity_fmol_per_s"] = 0.02
    d["symporter_v1"]["parameters"] |= dict(K_Na_mM=12.0, K_B_mM=0.4)
    return d


def selfcheck(out):
    """Erratum 2's engine readings on invented inputs and invented keys (no registered state, no
    reference; no value printed): the scan's counts of the points it did not evaluate; the anchor
    bound refusing a B_out that the parse could refuse; the equilibrium ratio at B_out 1e-5 mM on
    [1e-6, 1e8], every scan point evaluated and x = 0 at the root, for a key whose root lies
    between 1e6 and 1e8 and one below; the same keys at erratum 1's settings; the C8 (b) readings
    on invented saved runs; a short split bare run; every P1LB definition the procedure's segments
    use, parsed at h, h/2 and h/4. Returns the failures."""
    from validation.xenopus_bioelectric.xc0_compare import SETTINGS

    failures = []

    def expect(name, condition):
        if not condition:
            failures.append(name)

    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()

    # 1. The scan's counts (an invented function: no engine).
    def made(root):
        def f(x):
            if x > 0.6:
                raise ConfigError("invented parse refusal")
            if x < -0.7:
                raise Refused("invented domain refusal")
            return root - x

        return f

    xs = np.linspace(-1.0, 1.0, SCAN)
    parse, domain = int(np.sum(xs > 0.6)), int(np.sum(xs < -0.7))
    SCANS.clear()
    expect("a bracket inside the evaluated stretch", bracket(made(0.3), -1.0, 1.0) is not None
           and SCANS[-1] == dict(points=SCAN, parse=parse, domain=domain, nonfinite=0,
                                 evaluated=SCAN - parse - domain))  # fmt: skip
    try:
        bracket(made(0.9), -1.0, 1.0)
        failures.append("a root in the unevaluated stretch: not refused")
    except Refused as exc:
        expect("the refusal counts the points refused at parse",
               exc.scan["parse"] == parse and f"{parse} refused at parse" in str(exc)
               and f"{domain} outside a law's domain" in str(exc))  # fmt: skip

    # 2. The anchor bound (arithmetic on invented worlds' entries).
    d = invented_inputs()
    s = SETTINGS["eq_ratio"]
    domain_e2, bound = tuple(s["domain"]), float(s["anchor_bound_fmol"])
    keys = {"A": (3, 17.0, 55.0, -0.06), "B": (4, 15.0, 100.0, -0.08)}  # B's root: 1e6 to 1e8.
    for name, (n, na_in, na_out, _) in keys.items():
        expect(f"key {name}: B_out 1e-5 mM keeps the scan below the bound",
               eq_anchor_terms(n, na_in, na_out, s["B_out_mM"], 291.15, domain_e2, d=d) < bound)
        expect(f"key {name}: B_out 10 mM on the domain reaches the bound",
               eq_anchor_terms(n, na_in, na_out, 10.0, 291.15, domain_e2, d=d) >= bound)
    try:
        eq_ratio_e2(3, 17.0, 55.0, 10.0, 291.15, -0.06, domain=domain_e2, bound=bound, d=d)
        failures.append("B_out 10 mM on erratum 2's domain: not refused")
    except Refused as exc:
        expect("the bound refuses before any world is parsed", "charge-anchor term" in str(exc))

    # 3. The equilibrium ratio at erratum 2's settings, and at erratum 1's (invented keys).
    ratios = {}
    for name, (n, na_in, na_out, v) in keys.items():
        SCANS.clear()
        ratio = ratios[name] = eq_ratio_e2(n, na_in, na_out, s["B_out_mM"], 291.15, v,
                                           domain=domain_e2, bound=bound, d=d)  # fmt: skip
        scans = scans_summary()
        x = mode_value(symport_world(n, na_in, na_out, s["B_out_mM"], ratio, 291.15, d=d), v, "x")
        expect(f"key {name}: a ratio inside the domain", domain_e2[0] < ratio < domain_e2[1])
        expect(f"key {name}: every scan point evaluated",
               scans["scans"] == 1 and scans["evaluated"] == SCAN and scans["parse"] == 0
               and scans["domain"] == 0 and scans["nonfinite"] == 0)  # fmt: skip
        expect(f"key {name}: x = 0 at the root (|x| < 1e-9)", abs(x) < 1e-9)
    expect("key B's root lies between 1e6 and 1e8", 1e6 < ratios["B"] < 1e8)
    SCANS.clear()
    try:
        eq_ratio(4, 15.0, 100.0, 10.0, 291.15, -0.08, d=d)
        failures.append("key B at erratum 1's settings: not refused")
    except Refused as exc:
        expect("key B at erratum 1's settings: refused, its unevaluated points counted",
               exc.scan is not None and exc.scan["parse"] > 0 and "refused at parse" in str(exc))
    SCANS.clear()
    try:  # Information only: erratum 1's settings at key A (a root inside 1e6, above the limit).
        eq_ratio(3, 17.0, 55.0, 10.0, 291.15, -0.06, d=d)
        a_outcome = "a number"
    except Refused:
        a_outcome = "refused by its scan"
    except ConfigError:
        a_outcome = "a parse refusal inside the scan's bracket (an error row in a table)"
    a_dropped = SCANS[-1]["parse"] if SCANS else None

    # 4. The C8 (b) readings on invented saved runs (no engine): end state, potential, t_e.
    runs = out / "c8b-runs"
    shutil.rmtree(runs, ignore_errors=True)
    source = provenance()
    tau_bare, tau_coupled, c0, cf = 5.0, 4.0, 4.0, 0.75

    def save(folder, t, c, psi, until):
        folder.mkdir(parents=True)
        np.savez(folder / "trajectory.npz", t=t, c=c, psi=psi)
        digest = hashlib.sha256((folder / "trajectory.npz").read_bytes()).hexdigest()
        (folder / "record.json").write_text(json.dumps(dict(
            until=until, source=source, x2_cap=0.002, trajectory_sha256=digest,
            species=["Na", "K", "Cl", "A", "B"])))  # fmt: skip

    def invented_run(reading, tau, bounds):
        for i, (lo, hi) in enumerate(zip(bounds[:-1], bounds[1:], strict=True)):
            t = np.round(np.arange(round(lo * 100), round(hi * 100) + 1) * 0.01, 10)
            k = cf + (c0 - cf) * np.exp(-t / tau)
            c = np.column_stack([10 * k, k, 3 * k, np.full_like(t, 36.0), np.full_like(t, 1e-9)])
            save(runs / f"{reading}-1" / f"seg{i + 1}", t, c, -0.03 * (1 - np.exp(-t / tau)), hi)

    horizon = SETTINGS["c8b_horizon_s"]
    invented_run("bare", tau_bare, [0.0, 64.0, 128.0, horizon["bare"]])
    invented_run("coupled", tau_coupled, [0.0, horizon["coupled"]])
    C8_RUNS["dir"] = str(runs)
    cache = {}
    end_k = measure("c8b_end_c", dict(species="K", horizon_s=horizon["bare"]), x2_cap=0.002,
                    cache=cache)  # fmt: skip
    expect("end_c: the bare run's last observation",
           abs(end_k - (cf + (c0 - cf) * math.exp(-horizon["bare"] / tau_bare))) < 1e-12)
    psi = measure("c8b_end_psi", dict(horizon_s=horizon["bare"]), x2_cap=0.002, cache=cache)
    expect("end_psi: the bare run's last potential", abs(psi + 0.03) < 1e-12)
    t_e = measure("c8b_t_e_end", dict(species="Cl", horizon_s=horizon["bare"],
                                      coupled_horizon_s=horizon["coupled"]),
                  x2_cap=0.002, cache=cache)  # fmt: skip
    expect("t_e_end: the coupled run's 1/e time from the bare end state",
           abs(t_e - tau_coupled) < 1e-3)
    for name, measure_name, params in (
            ("erratum 1's final on a 192 s bare run", "c8b_final_saved", dict(species="K")),
            ("an end state at another horizon", "c8b_end_c", dict(species="K", horizon_s=128.0)),
            ("a coupled run at another horizon", "c8b_t_e_end",
             dict(species="K", horizon_s=horizon["bare"], coupled_horizon_s=32.0))):  # fmt: skip
        try:
            measure(measure_name, params, x2_cap=0.002, cache={})
            failures.append(f"{name}: not refused")
        except Refused:
            pass
    C8_RUNS["dir"] = None

    # 5. A short split bare run on the invented inputs (the engine), and the horizon refusal.
    try:
        c8b_segment("coupled", 1.0, horizon["coupled"] + 1.0, out / "beyond", x2_cap=0.002, d=d)
        failures.append("a coupled segment beyond its horizon: not refused")
    except SystemExit:
        pass
    split = out / "c8b-split"
    shutil.rmtree(split, ignore_errors=True)
    whole = c8b_segment("bare", 1.0, 0.04, split / "whole" / "bare-1" / "seg", x2_cap=0.002, d=d)
    c8b_segment("bare", 1.0, 0.02, split / "parts" / "bare-1" / "a", x2_cap=0.002, d=d)
    c8b_segment("bare", 1.0, 0.04, split / "parts" / "bare-1" / "b", x2_cap=0.002, d=d,
                resume=str(split / "parts" / "bare-1" / "a"))  # fmt: skip
    C8_RUNS["dir"] = str(split / "parts")
    joined = c8b_loaded("bare", x2_cap=0.002, horizon=0.04)
    C8_RUNS["dir"] = None
    w = np.load(split / "whole" / "bare-1" / "seg" / "trajectory.npz")
    expect("a split bare run is bitwise its whole (t, c, psi)",
           np.array_equal(w["t"], joined["t"]) and np.array_equal(w["c"], joined["c"])
           and np.array_equal(w["psi"], joined["psi"]) and len(joined["t"]) == 5)  # fmt: skip

    # 6. Every P1LB definition the procedure's segments use parses (no run), at h, h/2 and h/4, its
    # observation grid ending at the segment's end, one observation per 0.01 s.
    v0 = m_v_zero(dict(ion_set="primary", exterior="local", T=291.15), d=d, cache={})
    ends = {"bare": (64.0, 128.0, horizon["bare"]), "coupled": (32.0, horizon["coupled"])}
    for reading, untils in ends.items():
        for factor in (1.0, 0.5, 0.25):
            for until in untils:
                raw = c8b_definition(reading, factor, until, d=d, x2_cap=0.002, v0=v0)
                times = raw["experiment"]["observation_times"]
                try:
                    parse_spec(copy.deepcopy(raw))
                    parsed = True
                except ConfigError:
                    parsed = False
                expect(f"the {reading} definition to {until:g} s at factor {factor:g} parses, its "
                       f"grid ending there", parsed and abs(times[-1] - until) < 1e-9
                       and len(times) == round(until / 0.01) + 1)  # fmt: skip
    print(json.dumps(dict(seconds=round(time.perf_counter() - started, 1),
                          key_A_at_erratum_1s_settings=a_outcome,
                          key_A_scan_points_refused_at_parse_at_erratum_1s_settings=a_dropped,
                          split_run_seconds=whole["seconds"])))  # fmt: skip
    return failures


def main(argv=None):
    a = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = a.add_subparsers(dest="command", required=True)
    t = sub.add_parser("table")
    t.add_argument("manifest")
    t.add_argument("out")
    t.add_argument("--x2-cap", type=float, required=True)
    t.add_argument("--retry", action="store_true", help="the rule's retry (once)")
    t.add_argument("--c8b", help="the folder of the saved P1LB runs (xc0_engine c8b-run)")
    c = sub.add_parser("c8b-run", help="one segment of a saved P1LB run (errata 1 and 2)")
    c.add_argument("reading", choices=("bare", "coupled"))
    c.add_argument("factor", type=float, help="the step factor: 1, 0.5 (the companion) or 0.25")
    c.add_argument("until", type=float,
                   help="the segment's end (s); the run's is the reading's horizon (erratum 2)")
    c.add_argument("out", help="the segment's folder: <runs>/<reading>-<factor>/<segment>")
    c.add_argument("--x2-cap", type=float, required=True)
    c.add_argument("--resume", help="the previous segment's folder")
    b = sub.add_parser("anchor-bound", help="erratum 2: the C6 rows' worlds against the bound")
    b.add_argument("manifest")
    s = sub.add_parser("selfcheck", help="erratum 2's engine readings on invented inputs and keys")
    s.add_argument("out")
    args = a.parse_args(argv)
    if args.command == "anchor-bound":
        result = anchor_bound(json.loads(Path(args.manifest).read_text()))
        print(json.dumps(result))
        return 0 if result["rows"] and result["all_below"] else 1
    if args.command == "selfcheck":
        failures = selfcheck(args.out)
        print("engine selfcheck: "
              + ("passed" if not failures else "FAILED: " + "; ".join(failures)))
        return 1 if failures else 0
    if args.command == "c8b-run":
        record = c8b_segment(args.reading, args.factor, args.until, args.out, x2_cap=args.x2_cap,
                             resume=args.resume)  # fmt: skip
        print(json.dumps({k: record[k] for k in ("reading", "factor", "until", "seconds",
                                                 "trajectory_sha256")}))  # fmt: skip
        return 0
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    manifest = json.loads(Path(args.manifest).read_text())
    started = datetime.now(UTC).isoformat()
    C8_RUNS["dir"] = args.c8b
    c8b_records = {}
    if args.c8b:  # Each saved segment's record, by its digest, in the table's record.
        for record in sorted(Path(args.c8b).glob("*/*/record.json")):
            c8b_records[str(record.relative_to(args.c8b))] = hashlib.sha256(
                record.read_bytes()).hexdigest()
    record = dict(schema=SCHEMA, started_utc=started, source=provenance(),
                  manifest=str(Path(args.manifest).resolve()),
                  manifest_sha256=hashlib.sha256(Path(args.manifest).read_bytes()).hexdigest(),
                  x2_cap=args.x2_cap, retry=args.retry, python=platform.python_version(),
                  argv=sys.argv, c8b_runs=args.c8b, c8b_records=c8b_records)  # fmt: skip
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
