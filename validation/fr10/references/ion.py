"""R-ion: a passive cell whose held bath is stepped (Appendix A.3, item B2).

**The law (A.3).** The constant-field (Goldman-Hodgkin-Katz) flux of species s across the cell's
wall, outward positive, is

    J_s = 1e15 P_s A u (c_i - c_o e^{-u}) / (1 - e^{-u})  fmol/s,   u = z_s F V_m / RT,

with c in mM (= mol/m^3), P_s in m/s, A in m^2 and V_m the cell's potential less the bath's
(Hille 2001, ch. 14). Written with the Bernoulli function B(x) = x/(e^x - 1), B(0) = 1, it is
J_s = 1e15 P_s A [c_i B(-u) - c_o B(u)], which is regular at u = 0 (z = 0 gives Fick's law).
The capacitor gives C dV_m/dt = -1e-15 F sum_s z_s J_s, and the cell's amounts change by
dn_s/dt = -J_s. The bath is held: its composition is piecewise constant and right-continuous; V_m
and the amounts are continuous at an event.

**The start.** V_m(0) = Q_0/C, the inputs' initial charge over the wall's capacitance, and the
amounts are the inputs' amounts.

**One permeant ionic species (the registered W2).** Charge conservation makes
C (V_m - V_m(0)) = 1e-15 F z_p (n_p - n_p(0)) an exact invariant, so the state reduces to the
scalar V_m with n_p(V_m) on that line. The primary solution integrates that scalar equation epoch
by epoch (SciPy DOP853, rtol 3e-14, on V_m - V_m(t_e)). The second solution integrates the full
state (V_m and every permeant amount) with SciPy Radau, a different family. A third check is
exact for a scalar autonomous equation: the time to reach V is T(V) = int_{V_e}^{V} dV'/f(V'),
evaluated by QUADPACK at relative 1e-13, and |f(V(t)) (T(V(t)) - (t - t_e))| bounds the
primary's error at each record. The floor is the larger of the two differences, plus half an ulp.
With several permeant species the primary integrates the full state with DOP853 and Radau is the
second.

**The zero-current potential.** After each event, at the cytosol's composition at t_e and the
bath's new composition, V_rev solves sum_s z_s J_s(V) = 0. With one permeant species it is the
Nernst potential (RT/(z F)) ln(c_o/c_i), evaluated in 50-digit decimals; with monovalent species
only it is the GHK voltage equation; otherwise a root. Since the current that charges the wall
also moves the cytosol's amounts, the epoch's own limit differs slightly: ``limit_V`` is the fixed
point of the scalar equation on the invariant line (one permeant species only), by a decimal fixed
point iteration and by a float64 root, whose difference is its floor. Both are returned, labelled.

**The supply.** The cell is the tissue the bath supplies, so S_s(t) = -(n_s(t) - n_s(0)) (fmol,
positive out of the bath), the input A.5's K needs.
"""

from __future__ import annotations

import math
import warnings
from dataclasses import dataclass
from decimal import localcontext
from fractions import Fraction

import numpy as np
from scipy.integrate import quad, solve_ivp
from scipy.optimize import brentq

from .common import DIGITS, Constants, constants_from_block, dec, exact
from .records import bath_epochs, valences

RTOL_PRIMARY = 3e-14
RTOL_SECOND = 1e-12
QUAD_EPSREL = 1e-12


@dataclass
class IonWorld:
    """A parsed R_ion block, exact inputs kept."""

    temperature_K: Fraction
    z: dict
    volume_pL: Fraction
    amounts0: dict          # Fraction fmol
    charge0_C: Fraction
    area_m2: Fraction
    capacitance_F: Fraction
    permeability: dict      # Fraction m/s
    epochs: list            # [(t_start, {species: c_o (Fraction, mM)})]
    times: np.ndarray
    constants: Constants

    @property
    def species(self) -> list:
        return sorted(self.amounts0)

    @property
    def permeant(self) -> list:
        return [s for s in self.species if self.permeability.get(s, 0) > 0]

    def V0(self) -> float:
        return float(self.charge0_C / self.capacitance_F)


def parse(block: dict, constants=None) -> IonWorld:
    """Parse an R_ion block (the inputs file's layout)."""
    const = constants if isinstance(constants, Constants) else constants_from_block(constants)
    z = valences(block)
    cell, wall = block["cell"], block["wall"]
    amounts = {s: exact(v) for s, v in cell["amounts_fmol"].items()}
    perm = {s: exact(v) for s, v in wall["permeability_m_per_s"].items()}
    if set(perm) - set(amounts) or set(amounts) - set(z):
        raise ValueError("permeabilities, amounts and valences must name the same species")
    if any(v < 0 for v in perm.values()) or any(v <= 0 for v in amounts.values()):
        raise ValueError("permeabilities must be >= 0 and amounts > 0")
    epochs = bath_epochs(block["bath"])
    if set(epochs[0][1]) != set(amounts):
        raise ValueError("the bath and the cell must declare the same species")
    world = IonWorld(exact(block["temperature_K"]), z, exact(cell["volume_pL"]), amounts,
                     exact(cell["initial_charge_C"]), exact(wall["area_m2"]),
                     exact(wall["capacitance_F"]), perm, epochs,
                     np.asarray(block["record_times_s"], dtype=np.float64), const)
    if world.capacitance_F <= 0 or world.area_m2 <= 0 or world.volume_pL <= 0:
        raise ValueError("capacitance, area and volume must be positive")
    return world


def bernoulli(x: np.ndarray) -> np.ndarray:
    """B(x) = x/(e^x - 1), with B(0) = 1 and a series near 0."""
    x = np.asarray(x, dtype=np.float64)
    small = np.abs(x) < 1e-5
    safe = np.where(small, 1.0, x)
    out = np.where(small, 1.0 - x / 2.0 + x * x / 12.0, safe / np.expm1(safe))
    return out


class Fluxes:
    """Float64 constant-field fluxes for one epoch's bath."""

    def __init__(self, world: IonWorld, bath: dict, species: list):
        c = world.constants
        self.species = list(species)
        self.z = np.array([world.z[s] for s in species], dtype=np.float64)
        self.g = np.array([1e15 * float(world.permeability.get(s, 0) * world.area_m2)
                           for s in species])
        self.co = np.array([float(bath[s]) for s in species])
        self.Vc = float(world.volume_pL)
        self.inv_VT = float(c.faraday / c.RT(world.temperature_K))
        self.q = float(c.faraday / (10 ** 15 * world.capacitance_F))   # V per fmol of charge

        self._zl = [float(x) for x in self.z]
        self._gl = [float(x) for x in self.g]
        self._col = [float(x) for x in self.co]

    def J(self, V: float, n) -> np.ndarray:
        """Each species' outward flux (fmol/s) at V_m = V and cytosol amounts n."""
        return np.array(self.J_list(float(V), [float(x) for x in np.atleast_1d(n)]))

    def J_list(self, V: float, n: list) -> list:
        out = []
        for z, g, co, ni in zip(self._zl, self._gl, self._col, n, strict=True):
            u = z * V * self.inv_VT
            out.append(g * (ni / self.Vc * _bern(-u) - co * _bern(u)))
        return out


def _bern(x: float) -> float:
    """B(x) = x/(e^x - 1): a series near 0, and x e^{-x} beyond e^x's range."""
    if abs(x) < 1e-5:
        return 1.0 - x / 2.0 + x * x / 12.0
    if x > 700.0:
        return x * math.exp(-x)
    return x / math.expm1(x)


def _epoch_records(times, epochs) -> list:
    """For each epoch, the indices of the record times in [t_e, t_{e+1})."""
    texact = [exact(t) for t in times]
    out = []
    for e, (t0, _) in enumerate(epochs):
        t1 = epochs[e + 1][0] if e + 1 < len(epochs) else None
        out.append([k for k, t in enumerate(texact) if t >= t0 and (t1 is None or t < t1)])
    return out


def _solve(world: IonWorld, epochs, method: str, rtol: float, scalar: bool) -> dict:
    """Integrate epoch by epoch; returns V [T] and amounts {s: [T]} at the record times."""
    times = world.times
    sp = world.species
    perm = world.permeant
    n0 = np.array([float(world.amounts0[s]) for s in perm])
    V0 = world.V0()
    rec = _epoch_records(times, epochs)
    V_out = np.full(times.size, np.nan)
    dn_out = np.zeros((times.size, len(perm)))
    V_start, dn_start = V0, np.zeros(len(perm))
    starts = []
    t_end = max(float(times.max()), float(epochs[-1][0]))
    for e, (t_e, bath) in enumerate(epochs):
        fl = Fluxes(world, bath, perm)
        t_next = float(epochs[e + 1][0]) if e + 1 < len(epochs) else t_end
        span = float(exact(t_next) - t_e)
        taus = [float(exact(times[k]) - t_e) for k in rec[e]]
        if scalar:
            zp = fl.z[0]
            per_charge = 1.0 / (fl.q * zp)          # fmol of p per volt

            def rhs(_t, x, fl=fl, Vs=V_start, d0=dn_start[0], per=per_charge, n00=n0[0],
                    zp=zp):
                V = Vs + x[0]
                return [-fl.q * zp * fl.J_list(V, [n00 + d0 + per * x[0]])[0]]
            y0 = np.zeros(1)
            atol = 1e-18
        else:
            def rhs(_t, y, fl=fl, Vs=V_start, n0l=tuple(float(x) for x in n0)):
                J = fl.J_list(Vs + y[0], [a + b for a, b in zip(n0l, y[1:], strict=True)])
                return [-fl.q * sum(z * j for z, j in zip(fl._zl, J, strict=True))] + \
                    [-j for j in J]
            y0 = np.concatenate(([0.0], dn_start))
            atol = np.concatenate(([1e-18], np.full(len(perm), 1e-16)))
        if span > 0:
            sol = solve_ivp(rhs, (0.0, span), y0, method=method, rtol=rtol, atol=atol,
                            t_eval=sorted(set(taus + [span])), dense_output=False)
            if not sol.success:
                raise RuntimeError(f"{method} failed in epoch {e}: {sol.message}")
            at = {float(t): sol.y[:, i] for i, t in enumerate(sol.t)}
        else:
            at = {0.0: y0}
        starts.append((V_start, dn_start.copy()))
        for k, tau in zip(rec[e], taus, strict=True):
            y = at[tau]
            V_out[k] = V_start + y[0]
            dn_out[k] = (dn_start[0] + per_charge * y[0]) if scalar else y[1:]
        y_end = at[span] if span > 0 else y0
        if scalar:
            dn_start = np.array([dn_start[0] + per_charge * y_end[0]])
        else:
            dn_start = y_end[1:].copy()
        V_start = V_start + y_end[0]
    amounts = {}
    for s in sp:
        if s in perm:
            amounts[s] = n0[perm.index(s)] + dn_out[:, perm.index(s)]
        else:
            amounts[s] = np.full(times.size, float(world.amounts0[s]))
    start_amounts = [{s: (n0[perm.index(s)] + d[perm.index(s)]) if s in perm
                      else float(world.amounts0[s]) for s in sp} for _, d in starts]
    return {"V": V_out, "amounts": amounts, "dn": dn_out,
            "V_start": [v for v, _ in starts], "start_amounts": start_amounts}


def _quad_floor(world: IonWorld, epochs, V: np.ndarray, V_start: list) -> np.ndarray:
    """|f(V) (T(V) - (t - t_e))| at each record: the time-residual bound (one permeant only)."""
    p = world.permeant[0]
    rec = _epoch_records(world.times, epochs)
    out = np.zeros(world.times.size)
    V0 = world.V0()
    n_p0 = float(world.amounts0[p])
    for e, (t_e, bath) in enumerate(epochs):
        fl = Fluxes(world, bath, [p])
        zp = fl.z[0]
        per = 1.0 / (fl.q * zp)

        def f(Vx, fl=fl, per=per, zp=zp):
            return -fl.q * zp * fl.J_list(Vx, [n_p0 + per * (Vx - V0)])[0]
        Ve = V_start[e]
        for k in rec[e]:
            dV = V[k] - Ve
            tau = float(exact(world.times[k]) - t_e)
            if abs(dV) < 1e-15:
                out[k] = abs(dV)
                continue
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                val, err = quad(lambda x: 1.0 / f(x), Ve, V[k], epsabs=0.0,
                                epsrel=QUAD_EPSREL, limit=500)
            # QUADPACK may flag roundoff near the limit; its estimate is then taken tenfold.
            err = err * (10.0 if caught else 1.0)
            out[k] = abs(f(V[k]) * (val - tau)) + abs(f(V[k]) * err)
    return out


def zero_current(world: IonWorld, amounts_at: dict, bath: dict) -> tuple:
    """(V_rev, floor): the zero-current potential at a cytosol composition and a bath composition.

    One permeant species: the Nernst potential in decimals, against a float64 root. Monovalent
    species only: the GHK voltage equation in decimals, against the root. Otherwise the root.
    """
    c = world.constants
    perm = [s for s in world.permeant if world.z[s] != 0]
    if not perm:
        raise ValueError("no permeant ion: no zero-current potential")
    fl = Fluxes(world, bath, perm)
    n = np.array([float(amounts_at[s]) for s in perm])

    def current(V):
        return float(np.sum(fl.z * fl.J(V, n)))
    lo, hi = -1.0, 1.0
    root = brentq(current, lo, hi, xtol=1e-18, rtol=4 * np.finfo(float).eps, maxiter=500)
    with localcontext() as ctx:
        ctx.prec = DIGITS
        VT = dec(c.thermal_voltage(world.temperature_K))
        if len(perm) == 1:
            s = perm[0]
            ci = dec(exact(amounts_at[s]) / world.volume_pL)
            primary = float(VT * (dec(bath[s]) / ci).ln() / world.z[s])
        elif all(abs(world.z[s]) == 1 for s in perm):
            num = den = 0
            for s in perm:
                P = dec(world.permeability[s])
                ci = dec(exact(amounts_at[s]) / world.volume_pL)
                co = dec(bath[s])
                num += P * (co if world.z[s] > 0 else ci)
                den += P * (ci if world.z[s] > 0 else co)
            primary = float(VT * (num / den).ln())
        else:
            return root, 4 * float(np.spacing(abs(root)))
    return primary, abs(primary - root) + 0.5 * float(np.spacing(abs(primary)))


def epoch_limit(world: IonWorld, bath: dict) -> tuple:
    """(V_inf, floor): the fixed point of the scalar equation on the invariant line (one ion)."""
    perm = [s for s in world.permeant if world.z[s] != 0]
    if len(perm) != 1:
        return None, None
    p = perm[0]
    c = world.constants
    zp = world.z[p]
    with localcontext() as ctx:
        ctx.prec = DIGITS
        VT = dec(c.thermal_voltage(world.temperature_K))
        V0 = dec(world.charge0_C / world.capacitance_F)
        per = dec(10 ** 15 * world.capacitance_F / (c.faraday * zp))   # fmol per volt
        n0 = dec(world.amounts0[p])
        Vc = dec(world.volume_pL)
        co = dec(bath[p])
        V = VT * (co / (n0 / Vc)).ln() / zp
        for _ in range(60):
            ci = (n0 + per * (V - V0)) / Vc
            V_new = VT * (co / ci).ln() / zp
            if abs(V_new - V) < dec(Fraction(1, 10 ** 45)):
                V = V_new
                break
            V = V_new
        primary = float(V)
    fl = Fluxes(world, bath, [p])
    V0f = world.V0()
    perf = float(per)

    def f(Vx):
        return float(fl.J(Vx, np.array([float(world.amounts0[p]) + perf * (Vx - V0f)]))[0])
    root = brentq(f, primary - 1e-3, primary + 1e-3, xtol=1e-18, rtol=4 * np.finfo(float).eps)
    return primary, abs(primary - root) + 0.5 * float(np.spacing(abs(primary)))


def solve(world: IonWorld, epochs=None) -> dict:
    """The reference at the record times, both methods, the floors and the zero-current values.

    ``epochs`` overrides the bath's [(t_start, {species: c})] (the planted controls use it).
    """
    epochs = world.epochs if epochs is None else epochs
    ions = [s for s in world.permeant if world.z[s] != 0]
    scalar = len(world.permeant) == 1 and len(ions) == 1
    prim = _solve(world, epochs, "DOP853", RTOL_PRIMARY, scalar)
    second = _solve(world, epochs, "Radau", RTOL_SECOND, False)
    V = prim["V"]
    fV = np.abs(V - second["V"])
    if scalar:
        fV = np.maximum(fV, _quad_floor(world, epochs, V, prim["V_start"]))
    floor_V = fV + 0.5 * np.spacing(np.abs(V))
    floor_n = {}
    for s in world.species:
        a = prim["amounts"][s]
        floor_n[s] = np.abs(a - second["amounts"][s]) + 0.5 * np.spacing(np.abs(a))
        if scalar and s == world.permeant[0]:
            per = float(10 ** 15 * world.capacitance_F /
                        (world.constants.faraday * world.z[s]))
            floor_n[s] = np.maximum(floor_n[s], abs(per) * floor_V)
    supply = {s: -(prim["amounts"][s] - float(world.amounts0[s])) for s in world.species}
    zc, zc_floor, lim, lim_floor, at_event = [], [], [], [], []
    for e in range(1, len(epochs)):
        t_e, bath = epochs[e]
        v, fv = zero_current(world, prim["start_amounts"][e], bath)
        zc.append(v)
        zc_floor.append(fv)
        lv, lf = epoch_limit(world, bath)
        lim.append(lv)
        lim_floor.append(lf)
        at_event.append(float(t_e))
    rest_v, rest_f = zero_current(world, world.amounts0, epochs[0][1])
    return {
        "times_s": world.times,
        "V_m_V": V,
        "amount_fmol": prim["amounts"],
        "floor": {"V_m_V": floor_V, "amount_fmol": floor_n},
        "V_m_radau_V": second["V"],
        "supply_fmol": supply,
        "event_times_s": at_event,
        "zero_current_V": zc,
        "zero_current_floor_V": zc_floor,
        "limit_V": lim,
        "limit_floor_V": lim_floor,
        "V0_V": world.V0(),
        "rest_V_declared": rest_v,
        "rest_floor_V": rest_f,
        "scalar_reduction": scalar,
    }


def reference(block: dict, constants=None) -> dict:
    """R-ion on an inputs block: ``solve(parse(block, constants))``."""
    return solve(parse(block, constants))
