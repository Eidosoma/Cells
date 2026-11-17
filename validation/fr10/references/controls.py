"""Planted controls: wrong operators the comparison must catch, and their deviations (power).

Every check here is deterministic, so a control's power is its margin: its largest deviation from
the reference over the record times, divided by the tolerance. A control has power at a
tolerance when that margin is at least ``MIN_MARGIN`` (10). The design records each control's
deviation before any engine output, so a tolerance pinned later can be held below the smallest.

**Timing and view controls** (R-faces and R-ion), each the exact solution of a mis-scheduled
bath:
- ``null``: the bath's step never reaches transport (the view absent);
- ``late``: each event takes effect one step late, at t_e + dt (a left-continuous event map);
- ``early``: one step early, at t_e - dt;
- ``half``: half a step late, at t_e + dt/2 (the bath switched between a step's stages);
- ``accumulate``: offsets added to the previous epoch's composition instead of the declared one,
  c'_k = c'_{k-1} + (c_k - c_0). With a single event it equals the honest bath (no power).

**The scheme control.** ``implicit_euler``, a first-order engine; with the honest second-order
stand-ins (``schemes``) it shows the order a dt study can separate.

**Records controls** (R-records), each a wrong booking of an event: dG_b's sign, dG_b at the
content after the event, the linearised mu(a) dn, a dropped "-1", a 1 M standard state, log10,
Appendix A's rounded RT, a dose under accumulated offsets, a dose in mM (missing V_b), and a step
whose counter-ion is dropped (a net charge).

**K controls** (A.5), given a supply series: K dropped; K's sign; the supply re-priced at the
current potential without the accumulator B (``K_without_B``); and each epoch's supply booked at
the previous epoch's potential (``K_previous_epoch``).
"""

from __future__ import annotations

from decimal import localcontext
from fractions import Fraction

import numpy as np

from . import faces as faces_mod
from . import ion as ion_mod
from .common import DIGITS, MIN_MARGIN, Constants, dec, exact
from .records import bath_epochs, delta_G_exact, valences

TIMING = ("null", "late", "early", "half", "accumulate")


def shifted_epochs(epochs, control: str, dt=None):
    """The bath's epochs as a planted control sees them."""
    if control == "null":
        return epochs[:1]
    if control == "accumulate":
        c0 = epochs[0][1]
        out = [epochs[0]]
        for t, comp in epochs[1:]:
            prev = out[-1][1]
            if isinstance(comp, dict):
                new = {s: prev[s] + (comp[s] - c0[s]) for s in comp}
            else:
                new = prev + (comp - c0)
            out.append((t, new))
        return out
    shift = {"late": Fraction(1), "early": Fraction(-1), "half": Fraction(1, 2)}[control]
    d = exact(dt) * shift
    return [epochs[0]] + [(t + d, comp) for t, comp in epochs[1:]]


def faces_controls(world, dt_ladder, reference=None) -> dict:
    """Largest |amount - reference| (fmol) of each timing control, per dt where it depends on dt."""
    ref = faces_mod.solve(world) if reference is None else reference
    out = {}
    for control in TIMING:
        dts = dt_ladder if control in ("late", "early", "half") else [None]
        for dt in dts:
            amt = faces_mod.solve(world, epochs=shifted_epochs(world.epochs, control, dt))
            dev = float(np.max(np.abs(amt["amount_fmol"] - ref["amount_fmol"])))
            dev_s = float(np.max(np.abs(amt["supply_fmol"] - ref["supply_fmol"])))
            out[control if dt is None else f"{control}@{dt:g}"] = {
                "amount_fmol": dev, "supply_fmol": dev_s}
    return out


def ion_controls(world, dt_ladder, reference=None) -> dict:
    """Largest |V_m - reference| (V) and |n_K - reference| (fmol) of each timing control."""
    ref = ion_mod.solve(world) if reference is None else reference
    p = world.permeant[0]
    out = {}
    for control in TIMING:
        dts = dt_ladder if control in ("late", "early", "half") else [None]
        for dt in dts:
            sol = ion_mod._solve(world, shifted_epochs(world.epochs, control, dt), "DOP853",
                                 ion_mod.RTOL_PRIMARY, True)
            out[control if dt is None else f"{control}@{dt:g}"] = {
                "V_m_V": float(np.max(np.abs(sol["V"] - ref["V_m_V"]))),
                "amount_fmol": float(np.max(np.abs(sol["amounts"][p] -
                                                   ref["amount_fmol"][p])))}
    return out


class RoundedConstants(Constants):
    """Appendix A's printed values: RT = 2.577 pJ/fmol (2577 J/mol) at 310 K, F = 96485.33."""

    @property
    def faraday(self) -> Fraction:
        return Fraction("96485.33")

    def RT(self, temperature_K) -> Fraction:
        return Fraction(2577) * exact(temperature_K) / 310

    def thermal_voltage(self, temperature_K) -> Fraction:
        return self.RT(temperature_K) / self.faraday


def ion_rounded_constants(block: dict, reference) -> dict:
    """The deviation of an engine on Appendix A's rounded RT and F (not the operator's error)."""
    w = ion_mod.parse(block, RoundedConstants())
    sol = ion_mod._solve(w, w.epochs, "DOP853", ion_mod.RTOL_PRIMARY, True)
    p = w.permeant[0]
    return {"V_m_V": float(np.max(np.abs(sol["V"] - reference["V_m_V"]))),
            "amount_fmol": float(np.max(np.abs(sol["amounts"][p] -
                                               reference["amount_fmol"][p])))}


def _records_variants(world: dict, const: Constants) -> list:
    """Per event: the honest dG_b and dose, and every records control's value."""
    RT = const.RT(world["temperature_K"])
    z = valences(world)
    out = []
    baths = world.get("baths", {"bath": world.get("bath")})
    for name, bath in baths.items():
        V_b = exact(bath["volume_pL"])
        epochs = bath_epochs(bath)
        acc = shifted_epochs(epochs, "accumulate")
        for k in range(1, len(epochs)):
            before, after = epochs[k - 1][1], epochs[k][1]
            honest = delta_G_exact(before, after, V_b, RT)
            dose = {s: V_b * (after[s] - before[s]) for s in before}
            sum_dn = sum(dose.values())
            with localcontext() as ctx:
                ctx.prec = DIGITS
                lin = sum((dec(dose[s]) * dec(before[s]).ln() for s in before if dose[s] != 0),
                          start=dec(0)) * dec(RT) / 1000
                log10 = sum((dec(dose[s]) * (dec(before[s]).log10() - 1) +
                             dec(V_b * after[s]) * dec(after[s] / before[s]).log10()
                             for s in before if dose[s] != 0), start=dec(0)) * dec(RT) / 1000
                minus_one = honest + dec(RT) * dec(sum_dn) / 1000
                one_molar = honest - dec(RT) * dec(sum_dn) * dec(1000).ln() / 1000
            after_state = delta_G_exact(after, {s: 2 * after[s] - before[s] for s in after},
                                        V_b, RT) if all(2 * after[s] - before[s] > 0
                                                         for s in after) else None
            rounded = delta_G_exact(before, after, V_b, Fraction(2577) *
                                    exact(world["temperature_K"]) / 310)
            acc_dose = {s: V_b * (acc[k][1][s] - acc[k - 1][1][s]) for s in before}
            # A dropped counter-ion: the event's largest decrease is not applied.
            dec_species = [s for s in before if dose[s] < 0]
            if dec_species:
                drop = min(dec_species, key=lambda s: dose[s])
                q_drop = const.faraday * sum(z[s] * dose[s] for s in dose if s != drop) / 10**15
            else:
                q_drop = Fraction(0)
            out.append({
                "bath": name, "time_s": float(epochs[k][0]), "dG_b_pJ": float(honest),
                "dose_fmol": {s: float(v) for s, v in dose.items()},
                "sum_dose_fmol": float(sum_dn),
                "controls": {
                    "dG_sign": float(-honest),
                    "dG_after_state": None if after_state is None else float(after_state),
                    "dG_linearised": float(lin),
                    "dG_no_minus_one": float(minus_one),
                    "dG_one_molar": float(one_molar),
                    "dG_log10": float(log10),
                    "dG_rounded_RT": float(rounded),
                    "dose_accumulate": {s: float(v) for s, v in acc_dose.items()},
                    "dose_in_mM": {s: float(dose[s] / V_b) for s in dose},
                    "charge_dropped_counterion_C": float(q_drop),
                },
            })
    return out


def records_controls(world: dict, const: Constants) -> list:
    """Per event: each records control's relative deviation from the honest value."""
    rows = []
    for ev in _records_variants(world, const):
        dG = ev["dG_b_pJ"]
        rel = {}
        for key, val in ev["controls"].items():
            if key.startswith("dG_"):
                rel[key] = None if val is None else abs(val - dG) / abs(dG)
            elif key.startswith("dose_"):
                rel[key] = max(abs(val[s] - ev["dose_fmol"][s]) for s in val)
            else:
                rel[key] = abs(val)
        rows.append({"bath": ev["bath"], "time_s": ev["time_s"], "dG_b_pJ": dG,
                     "sum_dose_fmol": ev["sum_dose_fmol"], "deviation": rel})
    return rows


def K_controls(K_out: dict, supply: dict, world: dict, const: Constants) -> dict:
    """Largest |K_control - K| (pJ) of each K control, over the record times."""
    K = K_out["K_pJ"]
    dmu = K_out["delta_mu_J_per_mol"]
    rows = K_out["event_rows"]
    T = K.size
    species = list(supply)
    S = {s: np.asarray(supply[s], dtype=np.float64) for s in species}
    without_B = np.empty(T)
    prev = np.zeros(T)
    for k in range(T):
        e = sum(1 for r in rows if r <= k)
        without_B[k] = 1e-3 * sum(dmu[e][s] * S[s][k] for s in species)
        tot = 0.0
        for j in range(1, e + 1):
            start = rows[j - 1]
            end = k if j == e else rows[j]
            tot += 1e-3 * sum(dmu[j - 1][s] * (S[s][end] - S[s][start]) for s in species)
        prev[k] = tot
    return {
        "K_max_abs_pJ": float(np.max(np.abs(K))),
        "K_dropped": float(np.max(np.abs(K))),
        "K_sign": float(np.max(np.abs(2 * K))),
        "K_without_B": float(np.max(np.abs(without_B - K))),
        "K_previous_epoch": float(np.max(np.abs(prev - K))),
    }


def margin(deviation, tolerance) -> float:
    """A control's margin over a tolerance; power needs at least MIN_MARGIN."""
    return float("inf") if tolerance == 0 else float(deviation) / float(tolerance)


__all__ = ["MIN_MARGIN", "TIMING", "shifted_epochs", "faces_controls", "ion_controls",
           "ion_rounded_constants", "records_controls", "K_controls", "margin"]
