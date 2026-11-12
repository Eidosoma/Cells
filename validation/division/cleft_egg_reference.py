"""R-full: an independent reference of the one-cell Xenopus egg with a restricted cleft (S0b).

Written from docs/CELL_DIVISION_DESIGN.md (sections 5.1, 7 and 8.4) and the physics, not from
engine code; numpy/scipy only. Every input comes from the registered
validation/division/j1_declared_inputs.json, which this module reads directly.

The model (SI units; the solver carries amounts in fmol and node charges as fmol equivalents):
* nodes: the cytosol and the cleft lumen are free; the bath is held at 0 V. The lumen exists
  from insertion onset, when its patch switches on with a small declared area;
* capacitor graph: the old membrane C_old joins cytosol and bath, the new membrane
  C_new(t) = c_new A_new(t) joins cytosol and lumen, so q_i + q_c = C_old phi_i and
  q_c = C_new (phi_c - phi_i). Node charges are explicit states (q = F (sum z n + X));
* membranes: constant-field (Goldman-Hodgkin-Katz) fluxes;
* access face, lumen to bath: two-point Nernst-Planck with k_s = (A/L) D_s, either the
  constant-field form or the log-mean form (Fickian at zero field, exact for linear profiles);
* insertion: dA/dt = r(t) at fixed free-node charges (section 5.1). The capacitor free energy
  then falls at the rate (1/2) V_new^2 dC_new/dt, booked as insertion heat H >= 0. The lumen
  volume is w A_new / 2 and fills with bath fluid as it grows;
* current injection: the dLB74 pulse train into the cytosol, carried by K+ in and Cl- out.

Parts (python -m validation.division.cleft_egg_reference PART[,PART...] --output DIR):
  record    calibrate the old membrane and A/L under the defaults; Em at J1 (the prediction of
            record) and its reference term
"""

import argparse
import hashlib
import json
import math
import platform
import subprocess
import sys
import time
import traceback
from dataclasses import dataclass, field, replace
from pathlib import Path

import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import brentq

ROOT = Path(__file__).resolve().parents[2]
DECLARED = Path(__file__).with_name("j1_declared_inputs.json")

F = 6.02214076e23 * 1.602176634e-19  # C/mol (exact SI product N_A e)
R = 6.02214076e23 * 1.380649e-23  # J/(mol K) (exact SI product N_A k_B)
FMOL = 1e-15  # mol
SPECIES = ("Na", "K", "Cl")
Z = (1, 1, -1)
# State layout: cytosol charge, Na, K; lumen charge, Na, K; insertion heat (pJ).
QI, NAI, KI, QC, NAC, KC, HEAT = range(7)
NSTATE = 7


# ---------------------------------------------------------------- transport laws


def ghk_factor(x):
    """x / (1 - exp(-x)), stable at small |x| and free of overflow at large |x|."""
    if abs(x) < 1e-6:
        return 1.0 + x / 2.0 + x * x / 12.0
    if x > 0.0:
        return x / -math.expm1(-x)
    return x * math.exp(x) / math.expm1(x)


def ghk_flux(pa, z, u, c_in, c_out):
    """Outward constant-field flux (mol/s) for permeability x area pa (m3/s), u = F V / RT.

    pa (A(x) c_in - A(-x) c_out) with A(x) = x / (1 - exp(-x)) and x = z u, since
    A(x) exp(-x) = A(-x).
    """
    if pa == 0.0:
        return 0.0
    x = z * u
    return pa * (ghk_factor(x) * c_in - ghk_factor(-x) * c_out)


def log_mean(a, b):
    """(a - b) / (ln a - ln b), with L(c, c) = c."""
    d = (a - b) / b
    if abs(d) < 1e-8:
        return b * (1.0 + d / 2.0 - d * d / 12.0)
    return (a - b) / math.log1p(d)


def access_flux(law, k, z, u, c_lumen, c_bath):
    """Flux (mol/s) from the lumen to the bath through the access, k = (A/L) D (m3/s)."""
    if k == 0.0:
        return 0.0
    if law == "constant_field":
        return ghk_flux(k, z, u, c_lumen, c_bath)
    if law == "logmean":
        return k * log_mean(c_lumen, c_bath) * (math.log(c_lumen / c_bath) + z * u)
    raise ValueError(law)


def ghk_current(v, pa, c_in, c_out, temperature):
    """Outward current (A) of a constant-field membrane at voltage v."""
    u = F * v / (R * temperature)
    return F * math.fsum(
        z * ghk_flux(p, z, u, ci, co) for z, p, ci, co in zip(Z, pa, c_in, c_out, strict=True)
    )


def zero_current_potential(pa, c_in, c_out, temperature, bracket=(-0.2, 0.2)):
    return brentq(
        lambda v: ghk_current(v, pa, c_in, c_out, temperature),
        *bracket,
        xtol=1e-15,
        rtol=4 * np.finfo(float).eps,
    )


def slope_conductance(v, pa, c_in, c_out, temperature, h=1e-6):
    return (
        ghk_current(v + h, pa, c_in, c_out, temperature)
        - ghk_current(v - h, pa, c_in, c_out, temperature)
    ) / (2 * h)


# ---------------------------------------------------------------- definition


@dataclass(frozen=True)
class Pulses:
    amplitude_A: float = 3.0e-8
    duration_s: float = 1.2
    period_s: float = 10.0
    first_onset_s: float = 0.0
    first_sign: int = 1
    sample_s: float = 1.0
    carrier_K: float = 0.4912
    carrier_Cl: float = 0.5088
    enabled: bool = True

    def sign(self, k):
        return self.first_sign * (-1) ** k

    def onset(self, k):
        return self.first_onset_s + k * self.period_s


@dataclass(frozen=True)
class Egg:
    """One complete definition of the cleft egg (SI units)."""

    temperature_K: float
    cytosol_volume_m3: float
    cytosol_mM: tuple  # initial Na, K, Cl (mol/m3)
    bath_mM: tuple
    old_area_m2: float
    old_capacitance_F: float
    old_relative: tuple  # relative permeabilities, scaled by p_old
    p_old: float  # m/s (calibrated)
    new_permeability: tuple  # m/s per species (per unit area of new membrane)
    new_specific_capacitance_F_m2: float
    onset_s: float
    activation_area_m2: float
    schedule: tuple  # ((t_start, rate_m2_s), ...) from onset; the last rate continues
    gap_width_m: float
    access_law: str
    access_D: tuple  # m2/s per species
    a_over_l_m: float  # calibrated
    new_faces: str = "lumen"  # "lumen" or "bath" (exposed arms)
    pulses: Pulses = field(default_factory=Pulses)
    old_capacitance_rate_F_s: float = 0.0  # tests only: one-patch insertion
    initial_V: float = math.nan  # tests only: start here instead of the zero-current potential

    @property
    def rt(self):
        return R * self.temperature_K

    def area(self, t):
        """New-membrane area (both faces) at t >= onset."""
        a = self.activation_area_m2
        pieces = self.schedule
        for i, (start, rate) in enumerate(pieces):
            stop = pieces[i + 1][0] if i + 1 < len(pieces) else math.inf
            if t <= stop:
                return a + rate * (t - start)
            a += rate * (stop - start)
        raise AssertionError

    def rate(self, t0, t1):
        """The constant insertion rate on [t0, t1] (segments never straddle a breakpoint)."""
        mid = 0.5 * (t0 + t1)
        for i, (start, rate) in enumerate(self.schedule):
            stop = self.schedule[i + 1][0] if i + 1 < len(self.schedule) else math.inf
            if start <= mid < stop:
                return rate
        raise AssertionError((t0, t1))


def uniform_schedule(onset_s, area_at_j1_m2, activation_m2, j1_s):
    return ((onset_s, (area_at_j1_m2 - activation_m2) / (j1_s - onset_s)),)


def back_loaded_schedule(onset_s, area_at_j1_m2, activation_m2, j1_s, rate, duration):
    first = activation_m2 + rate * duration
    return (
        (onset_s, rate),
        (onset_s + duration, (area_at_j1_m2 - first) / (j1_s - onset_s - duration)),
    )


# ---------------------------------------------------------------- declared inputs


def load_declared(path=DECLARED):
    return json.loads(Path(path).read_text())


BAND_INPUTS = (
    ("temperature_K", "inputs"),
    ("cytosol_Na_mM", "inputs"),
    ("cytosol_K_mM", "inputs"),
    ("new_membrane_specific_resistance_ohm_m2", "inputs"),
    ("new_membrane_PNa_over_PK", "inputs"),
    ("new_membrane_specific_capacitance_F_m2", "inputs"),
    ("insertion_onset_s", "inputs"),
    ("new_membrane_area_at_j1_m2", "inputs"),
    ("gap_width_m", "inputs"),
    ("rm1_target_ohm", "calibration_targets"),
    ("rm2_target_ohm", "calibration_targets"),
)


def scalar_values(d, overrides=None):
    """Default values of every scalar input, then overrides {name: value}."""
    values = {}
    for name, group in BAND_INPUTS:
        values[name] = float(d[group][name]["default"])
    values["schedule"] = "uniform"
    values["access_law"] = d["inputs"]["access"]["law_default"]
    values["access_selectivity"] = "free_solution"
    for name, value in (overrides or {}).items():
        if name not in values:
            raise KeyError(name)
        values[name] = value
    return values


def band_members(d):
    """[(label, overrides)] for the one-at-a-time band; the schedule member is one-sided."""
    members = []
    for name, group in BAND_INPUTS:
        entry = d[group][name]
        assert entry["in_band"] is True, name
        members.append((name + ":low", {name: float(entry["low"])}))
        members.append((name + ":high", {name: float(entry["high"])}))
    assert d["inputs"]["insertion_schedule"]["band_member_back_loaded"]["in_band"] is True
    members.append(("insertion_schedule:back_loaded", {"schedule": "back_loaded"}))
    return members


def new_permeability(d, values, cytosol, bath):
    """P_K,new from r_new by the declared slope rule; P_Na = rho P_K; P_Cl = 0."""
    entry = d["inputs"]["new_membrane_specific_resistance_ohm_m2"]
    assert "-60 mV" in entry["conversion_rule"]
    v = -0.060
    rho = values["new_membrane_PNa_over_PK"]
    unit = (rho, 1.0, float(d["inputs"]["new_membrane_PCl"]["default"]))
    g = slope_conductance(v, unit, cytosol, bath, values["temperature_K"])  # S/m2 per (m/s)
    pk = 1.0 / (values["new_membrane_specific_resistance_ohm_m2"] * g)
    return tuple(pk * w for w in unit)


def build(d, values, *, p_old=None, a_over_l=None):
    """An Egg from declared inputs and scalar values (calibrated factors may be None)."""
    inputs = d["inputs"]
    cytosol = (
        values["cytosol_Na_mM"],
        values["cytosol_K_mM"],
        float(inputs["cytosol_Cl_mM"]["default"]),
    )
    bath = tuple(float(inputs["bath"]["activity_mM"][s]) for s in SPECIES)
    old = inputs["old_membrane"]
    j1 = float(d["time"]["j1_s"])
    activation = float(inputs["insertion_activation_area_m2"]["default"])
    onset = values["insertion_onset_s"]
    total = values["new_membrane_area_at_j1_m2"]
    if values["schedule"] == "uniform":
        schedule = uniform_schedule(onset, total, activation, j1)
    elif values["schedule"] == "back_loaded":
        b = inputs["insertion_schedule"]["band_member_back_loaded"]
        schedule = back_loaded_schedule(
            onset,
            total,
            activation,
            j1,
            float(b["initial_rate_m2_per_s"]),
            float(b["initial_duration_s"]),
        )
    else:
        raise ValueError(values["schedule"])
    access = inputs["access"]
    D = tuple(float(access["diffusivity_m2_per_s"][s]) for s in SPECIES)
    if values["access_selectivity"] == "cation_selective":
        D = (D[0], D[1], 0.0)
    elif values["access_selectivity"] != "free_solution":
        raise ValueError(values["access_selectivity"])
    rm = d["rm_definition"]
    pulses = Pulses(
        amplitude_A=float(rm["pulse_amplitude_A"]),
        duration_s=float(rm["pulse_duration_s"]),
        period_s=float(rm["pulse_period_s"]),
        first_onset_s=float(rm["first_pulse_onset_s"]),
        first_sign=int(rm["first_pulse_sign"]),
        carrier_K=float(rm["injected_carrier_fractions"]["K"]),
        carrier_Cl=float(rm["injected_carrier_fractions"]["Cl"]),
    )
    return Egg(
        temperature_K=values["temperature_K"],
        cytosol_volume_m3=float(inputs["cytosol_volume_m3"]["default"]),
        cytosol_mM=cytosol,
        bath_mM=bath,
        old_area_m2=float(old["area_m2"]),
        old_capacitance_F=float(old["capacitance_F"]),
        old_relative=tuple(float(old["relative_permeability"][s]) for s in SPECIES),
        p_old=math.nan if p_old is None else p_old,
        new_permeability=new_permeability(d, values, cytosol, bath),
        new_specific_capacitance_F_m2=values["new_membrane_specific_capacitance_F_m2"],
        onset_s=onset,
        activation_area_m2=activation,
        schedule=schedule,
        gap_width_m=values["gap_width_m"],
        access_law=values["access_law"],
        access_D=D,
        a_over_l_m=math.nan if a_over_l is None else a_over_l,
        pulses=pulses,
    )


# ---------------------------------------------------------------- the ODE


@dataclass
class Segment:
    """Constants of one integration interval."""

    lumen: bool
    current_A: float
    area_t0: float
    area_a0: float
    rate: float


def initial_state(egg):
    """Cytosol at the old membrane's zero-current potential; lumen inactive."""
    if math.isfinite(egg.initial_V):
        v0 = egg.initial_V
    else:
        # The zero-current potential depends only on the relative permeabilities.
        pa = tuple(w * egg.old_area_m2 for w in egg.old_relative)
        v0 = zero_current_potential(pa, egg.cytosol_mM, egg.bath_mM, egg.temperature_K)
    n = [c * egg.cytosol_volume_m3 / FMOL for c in egg.cytosol_mM]
    q0 = egg.old_capacitance_F * v0 / (F * FMOL)
    background = q0 - math.fsum(z * x for z, x in zip(Z, n, strict=True))
    y = np.zeros(NSTATE)
    y[QI], y[NAI], y[KI] = q0, n[0], n[1]
    return y, background, v0


class Model:
    """The cleft egg's right-hand side and its derived quantities."""

    def __init__(self, egg, background_fmol):
        self.egg = egg
        self.x_i = background_fmol
        self.pa_old = tuple(egg.p_old * w * egg.old_area_m2 for w in egg.old_relative)
        self.k_acc = tuple(egg.a_over_l_m * D for D in egg.access_D)
        self.supply_charge = math.fsum(z * c for z, c in zip(Z, egg.bath_mM, strict=True))

    def c_old(self, t):
        return self.egg.old_capacitance_F + self.egg.old_capacitance_rate_F_s * t

    def derived(self, t, y, seg):
        """Potentials, concentrations and capacitances at (t, y)."""
        egg = self.egg
        vi = egg.cytosol_volume_m3
        n_cl_i = y[NAI] + y[KI] + self.x_i - y[QI]
        ci = (y[NAI] * FMOL / vi, y[KI] * FMOL / vi, n_cl_i * FMOL / vi)
        qi = y[QI] * FMOL * F
        out = dict(ci=ci)
        if not seg.lumen:
            area = 0.0
            if egg.new_faces == "bath" and t >= egg.onset_s:
                area = seg.area_a0 + seg.rate * (t - seg.area_t0)
            c_new = egg.new_specific_capacitance_F_m2 * area
            phi_i = qi / (self.c_old(t) + (c_new if egg.new_faces == "bath" else 0.0))
            out.update(phi_i=phi_i, phi_c=0.0, v_new=phi_i, area=area, c_new=c_new)
            return out
        area = seg.area_a0 + seg.rate * (t - seg.area_t0)
        c_new = egg.new_specific_capacitance_F_m2 * area
        vc = egg.gap_width_m * area / 2.0
        n_cl_c = y[NAC] + y[KC] - y[QC]
        cc = (y[NAC] * FMOL / vc, y[KC] * FMOL / vc, n_cl_c * FMOL / vc)
        qc = y[QC] * FMOL * F
        phi_i = (qi + qc) / self.c_old(t)
        v_new = -qc / c_new
        out.update(
            phi_i=phi_i, phi_c=phi_i - v_new, v_new=v_new, area=area, c_new=c_new, cc=cc, vc=vc
        )
        return out

    def rhs(self, t, y, seg):
        egg = self.egg
        s = self.derived(t, y, seg)
        rt = egg.rt
        u_old = F * s["phi_i"] / rt
        ci = s["ci"]
        j_old = [
            ghk_flux(p, z, u_old, a, b)
            for p, z, a, b in zip(self.pa_old, Z, ci, egg.bath_mM, strict=True)
        ]
        dy = np.zeros(NSTATE)
        inj_k = egg.pulses.carrier_K * seg.current_A / F
        inj_cl = -egg.pulses.carrier_Cl * seg.current_A / F
        if seg.lumen:
            area, cc = s["area"], s["cc"]
            u_new = F * s["v_new"] / rt
            j_new = [
                ghk_flux(p * area, z, u_new, a, b)
                for p, z, a, b in zip(egg.new_permeability, Z, ci, cc, strict=True)
            ]
            u_c = F * s["phi_c"] / rt
            j_acc = [
                access_flux(egg.access_law, k, z, u_c, a, b)
                for k, z, a, b in zip(self.k_acc, Z, cc, egg.bath_mM, strict=True)
            ]
            dvc = egg.gap_width_m * seg.rate / 2.0
            supply = [c * dvc for c in egg.bath_mM]
            dy[NAC] = (j_new[0] - j_acc[0] + supply[0]) / FMOL
            dy[KC] = (j_new[1] - j_acc[1] + supply[1]) / FMOL
            dy[QC] = (
                math.fsum(z * (a - b) for z, a, b in zip(Z, j_new, j_acc, strict=True))
                + self.supply_charge * dvc
            ) / FMOL
            dy[HEAT] = 0.5 * s["v_new"] ** 2 * egg.new_specific_capacitance_F_m2 * seg.rate * 1e12
        else:
            j_new = [0.0, 0.0, 0.0]
            if egg.new_faces == "bath" and s["area"] > 0.0:
                j_new = [
                    ghk_flux(p * s["area"], z, u_old, a, b)
                    for p, z, a, b in zip(egg.new_permeability, Z, ci, egg.bath_mM, strict=True)
                ]
                dy[HEAT] = (
                    0.5 * s["phi_i"] ** 2 * egg.new_specific_capacitance_F_m2 * seg.rate * 1e12
                )
        dy[HEAT] += 0.5 * s["phi_i"] ** 2 * egg.old_capacitance_rate_F_s * 1e12
        dy[NAI] = (-j_old[0] - j_new[0]) / FMOL
        dy[KI] = (-j_old[1] - j_new[1] + inj_k) / FMOL
        dy[QI] = (
            -math.fsum(z * (a + b) for z, a, b in zip(Z, j_old, j_new, strict=True))
            + seg.current_A / F
        ) / FMOL
        # Cl- of the cytosol follows from its charge; its own rate is -J_old,Cl - J_new,Cl + inj_cl.
        _ = inj_cl
        return dy

    def capacitor_energy_J(self, t, y, seg):
        s = self.derived(t, y, seg)
        e = 0.5 * self.c_old(t) * s["phi_i"] ** 2
        if seg.lumen or self.egg.new_faces == "bath":
            e += (
                0.5 * s["c_new"] * s["v_new"] ** 2
                if seg.lumen
                else 0.5 * s["c_new"] * s["phi_i"] ** 2
            )
        return e


# ---------------------------------------------------------------- integration


@dataclass
class Run:
    """Records of one simulation: pulse samples and the requested times."""

    egg: Egg
    background_fmol: float
    v0: float
    onset_V: dict  # pulse k -> V at its front edge
    sample_V: dict  # pulse k -> V one sample time after the front edge
    at: dict  # time -> dict of derived quantities and the state
    steps: int
    wall_s: float

    def rm(self, k):
        p = self.egg.pulses
        dv_prev = self.sample_V[k - 1] - self.onset_V[k - 1]
        dv = self.sample_V[k] - self.onset_V[k]
        return (abs(dv_prev) + abs(dv)) / (2.0 * p.amplitude_A), dv_prev, dv


def breakpoints(egg, t_end, extra=()):
    points = {0.0, t_end, *(t for t in extra if 0.0 <= t <= t_end)}
    if egg.onset_s < t_end:
        points.add(egg.onset_s)
        points |= {start for start, _ in egg.schedule if start < t_end}
    p = egg.pulses
    if p.enabled:
        k = 0
        while p.onset(k) < t_end:
            t = p.onset(k)
            points |= {t, *(x for x in (t + p.sample_s, t + p.duration_s) if x <= t_end)}
            k += 1
    return sorted(points)


def current_at(egg, t0):
    p = egg.pulses
    if not p.enabled or t0 < p.first_onset_s:
        return 0.0
    k = int(math.floor((t0 - p.first_onset_s) / p.period_s + 1e-12))
    start = p.onset(k)
    if start - 1e-12 <= t0 < start + p.duration_s - 1e-9:
        return p.sign(k) * p.amplitude_A
    return 0.0


def atol_vector():
    a = np.empty(NSTATE)
    a[QI], a[NAI], a[KI] = 1e-9, 1e-6, 1e-6
    a[QC], a[NAC], a[KC] = 1e-9, 1e-9, 1e-9
    a[HEAT] = 1e-12
    return a


def simulate(egg, t_end, *, record=(), rtol=1e-10, method="Radau", lumen_state=None, initial=None):
    """Integrate from t = 0 to t_end; returns a Run.

    lumen_state (tests only): a callable(egg, y) -> y applied at activation instead of the
    default (bath composition, zero charge). initial (static comparisons only): (y, background)
    to start from, with the lumen already active (requires onset 0 and a lumen-facing patch).
    """
    started = time.perf_counter()
    if initial is None:
        y, background, v0 = initial_state(egg)
    else:
        assert egg.onset_s == 0.0 and egg.new_faces == "lumen"
        y, background = np.asarray(initial[0], dtype=float).copy(), float(initial[1])
        v0 = math.nan
    model = Model(egg, background)
    points = breakpoints(egg, t_end, record)
    p = egg.pulses
    onset_V, sample_V, at = {}, {}, {}
    pulse_of_onset = {}
    pulse_of_sample = {}
    if p.enabled:
        k = 0
        while p.onset(k) <= t_end:
            pulse_of_onset[p.onset(k)] = k
            pulse_of_sample[p.onset(k) + p.sample_s] = k
            k += 1
    lumen = initial is not None  # a given start already has its lumen
    atol = atol_vector()
    steps = 0
    record = set(record)

    def snapshot(t, y, seg):
        s = model.derived(t, y, seg)
        return dict(
            V=s["phi_i"],
            phi_lumen=s["phi_c"],
            v_new=s["v_new"],
            area=s["area"],
            c_new=s["c_new"],
            cytosol_mM=list(s["ci"]),
            lumen_mM=list(s["cc"]) if "cc" in s else None,
            heat_pJ=float(y[HEAT]),
            capacitor_energy_J=model.capacitor_energy_J(t, y, seg),
            state=y.tolist(),
        )

    def segment_for(t0, t1):
        rate = egg.rate(t0, t1) if t0 >= egg.onset_s else 0.0
        a0 = egg.area(t0) if t0 >= egg.onset_s else 0.0
        return Segment(lumen, current_at(egg, t0), t0, a0, rate)

    seg = segment_for(0.0, points[1])
    exposed = False
    for t0, t1 in zip(points, points[1:], strict=False):
        if egg.new_faces == "bath" and not exposed and t0 >= egg.onset_s:
            # A bath-facing patch switches on in parallel at fixed charge: book the jump's heat.
            exposed = True
            qi = y[QI] * FMOL * F
            c = model.c_old(t0)
            c_new = egg.new_specific_capacitance_F_m2 * egg.area(t0)
            y = y.copy()
            y[HEAT] += 0.5 * qi * qi * (1.0 / c - 1.0 / (c + c_new)) * 1e12
        if egg.new_faces == "lumen" and not lumen and t0 >= egg.onset_s:
            lumen = True
            area0 = egg.area(t0)
            vc = egg.gap_width_m * area0 / 2.0
            y = y.copy()
            y[QC] = 0.0
            y[NAC] = egg.bath_mM[0] * vc / FMOL
            y[KC] = egg.bath_mM[1] * vc / FMOL
            if lumen_state is not None:
                y = lumen_state(egg, y)
        seg = segment_for(t0, t1)
        if t0 in pulse_of_onset:
            onset_V[pulse_of_onset[t0]] = model.derived(t0, y, seg)["phi_i"]
        if t0 in record:
            at[t0] = snapshot(t0, y, seg)
        sol = solve_ivp(model.rhs, (t0, t1), y, method=method, rtol=rtol, atol=atol, args=(seg,))
        if not sol.success:
            raise RuntimeError(f"integration failed on [{t0}, {t1}]: {sol.message}")
        steps += sol.t.size - 1
        y = sol.y[:, -1].copy()
        if t1 in pulse_of_sample:
            sample_V[pulse_of_sample[t1]] = model.derived(t1, y, seg)["phi_i"]
    if t_end in record:
        at[t_end] = snapshot(t_end, y, seg)
    if t_end in pulse_of_onset:
        onset_V[pulse_of_onset[t_end]] = model.derived(t_end, y, seg)["phi_i"]
    return Run(egg, background, v0, onset_V, sample_V, at, steps, time.perf_counter() - started)


# ---------------------------------------------------------------- calibration


def rm_at(egg, pair, *, rtol=1e-10, method="Radau"):
    """Pulse-protocol Rm (ohm) from the declared pulse pair, and its run."""
    k_prev, k = pair
    p = egg.pulses
    t_end = p.onset(k) + p.sample_s
    run = simulate(egg, t_end, rtol=rtol, method=method)
    return run.rm(k)[0], run


def solve_decreasing(miss, x0, *, step, xtol, ftol=1e-10, max_secant=10):
    """Root of a smooth decreasing miss(x): secant from x0, then bracketing brentq if needed.

    Returns (x, evaluations as [(x, f)]).
    """
    log = []

    def f(x):
        value = miss(x)
        log.append((x, value))
        return value

    x_a, f_a = x0, f(x0)
    if abs(f_a) < ftol:
        return x_a, log
    x_b = x0 + (step if f_a > 0 else -step)
    f_b = f(x_b)
    for _ in range(max_secant):
        if abs(f_b) < ftol:
            return x_b, log
        if f_b == f_a or (f_b - f_a) / (x_b - x_a) >= 0:
            break  # not decreasing here: fall back
        x_c = x_b - f_b * (x_b - x_a) / (f_b - f_a)
        x_c = min(max(x_c, x_b - 1.0), x_b + 1.0)  # at most one decade per secant step
        x_a, f_a = x_b, f_b
        x_b, f_b = x_c, f(x_c)
        if abs(x_b - x_a) < xtol and abs(f_b) < 1e3 * ftol:
            return x_b, log
    # Bracket from the evaluations, widening if needed, then brentq.
    pos = max((x for x, v in log if v > 0), default=None)
    neg = min((x for x, v in log if v < 0), default=None)
    while pos is None:
        x = min(x for x, _ in log) - 0.5
        if f(x) > 0:
            pos = x
    while neg is None:
        x = max(x for x, _ in log) + 0.5
        if f(x) < 0:
            neg = x
    return brentq(f, pos, neg, xtol=xtol, rtol=1e-15), log


def calibrate_old(egg, target_ohm, pair, *, rtol=1e-10, method="Radau"):
    """P_old (m/s) with the uncleaved egg's pulse Rm equal to target (insertion after the pair).

    The search starts from the closed-form slope estimate at rest.
    """
    p = egg.pulses
    assert egg.onset_s > p.onset(pair[1]) + p.sample_s
    _, _, v0 = initial_state(egg)
    unit = tuple(w * egg.old_area_m2 for w in egg.old_relative)
    g = slope_conductance(v0, unit, egg.cytosol_mM, egg.bath_mM, egg.temperature_K)
    estimate = 1.0 / (target_ohm * g)

    def miss(log_p):
        rm = rm_at(replace(egg, p_old=10.0**log_p), pair, rtol=rtol, method=method)[0]
        return math.log(rm / target_ohm)

    x, _ = solve_decreasing(miss, math.log10(estimate), step=0.01, xtol=1e-11)
    return 10.0**x


def calibrate_access(
    egg,
    target_ohm,
    pair,
    *,
    rtol=1e-10,
    guess=1.6e-6,
    xtol=1e-9,
    step=0.05,
    method="Radau",
    ftol=1e-10,
):
    """A/L (m) with the pulse Rm at J1 equal to target; returns (A/L, [(A/L, Rm)])."""

    evaluations = []

    def miss(log_al):
        rm, run = rm_at(replace(egg, a_over_l_m=10.0**log_al), pair, rtol=rtol, method=method)
        evaluations.append(
            dict(
                a_over_l_m=10.0**log_al,
                rm_ohm=rm,
                em_at_pulse_V=run.onset_V[pair[1]],
                wall_s=run.wall_s,
            )
        )
        return math.log(rm / target_ohm)

    x, _ = solve_decreasing(miss, math.log10(guess), step=step, xtol=xtol, ftol=ftol)
    return 10.0**x, evaluations


# ---------------------------------------------------------------- provenance and parts


def provenance():
    git = ["git", "-C", str(ROOT)]

    def out(*args):
        return subprocess.run([*git, *args], capture_output=True, text=True).stdout

    import scipy

    return dict(
        argv=sys.argv,
        host=platform.node(),
        revision=out("rev-parse", "HEAD").strip(),
        dirty=out("status", "--porcelain", "--untracked-files=no"),
        diff=out("diff", "HEAD"),
        numpy=np.__version__,
        scipy=scipy.__version__,
        python=sys.version,
        declared_sha256=hashlib.sha256(DECLARED.read_bytes()).hexdigest(),
    )


def egg_definition_record(egg):
    out = {k: v for k, v in egg.__dict__.items() if k != "pulses"}
    out["pulses"] = dict(egg.pulses.__dict__)
    return json.loads(json.dumps(out, default=float))


def calibrated(d, values, *, rtol=1e-10, method="Radau", guess=1.6e-6, step=0.05):
    """The definition with P_old and A/L calibrated on the declared pulse pairs."""
    rm = d["rm_definition"]
    egg = build(d, values)
    p_old = calibrate_old(
        egg, values["rm1_target_ohm"], tuple(rm["rm1_pulse_pair"]), rtol=rtol, method=method
    )
    egg = replace(egg, p_old=p_old)
    al, log = calibrate_access(
        egg,
        values["rm2_target_ohm"],
        tuple(rm["j1_pulse_pair"]),
        rtol=rtol,
        method=method,
        guess=guess,
        step=step,
    )
    return replace(egg, a_over_l_m=al), log


def j1_readout(d, egg, *, rtol=1e-10, method="Radau", t_end=None, record=()):
    rm = d["rm_definition"]
    k_prev, k = rm["j1_pulse_pair"]
    p = egg.pulses
    j1 = float(d["time"]["j1_s"])
    t_end = p.onset(k) + p.sample_s if t_end is None else t_end
    run = simulate(egg, t_end, rtol=rtol, method=method, record=(j1, *record))
    rm2, dv_prev, dv = run.rm(k)
    em = run.onset_V[rm["j1_em_pulse"]]
    return dict(
        em_V=em,
        rm_ohm=rm2,
        chords_ohm=[dv_prev / (p.sign(k_prev) * p.amplitude_A), dv / (p.sign(k) * p.amplitude_A)],
        at_j1=run.at[j1],
        steps=run.steps,
        wall_s=run.wall_s,
    ), run


def log_line(*parts):
    print(time.strftime("%H:%M:%S"), *parts, flush=True)


def part_record(args):
    """The prediction of record under the defaults, then its reference term.

    P_old is calibrated with Radau (rtol 1e-10). The A/L root is searched with LSODA (rtol
    1e-10), logging A/L, Rm and Em at the J1 pulse for every evaluation; one Radau run at that
    root, the registered integrator, gives the prediction of record (polished with Radau only if
    its Rm misses the target by more than 1e-8). It is written to prediction_of_record.json
    before any other run; the LSODA search's last Em is recorded beside it.
    """
    d = load_declared()
    values = scalar_values(d)
    rm = d["rm_definition"]
    pair = tuple(rm["j1_pulse_pair"])
    target = values["rm2_target_ohm"]
    started = time.perf_counter()
    egg = build(d, values)
    p_old = calibrate_old(egg, values["rm1_target_ohm"], tuple(rm["rm1_pulse_pair"]))
    egg = replace(egg, p_old=p_old)
    rm1, _ = rm_at(egg, tuple(rm["rm1_pulse_pair"]))
    log_line("P_old", p_old, "Rm1", rm1)
    al, search_log = calibrate_access(egg, target, pair, method="LSODA")
    log_line("A/L search (LSODA)", al, "evaluations", len(search_log))
    polish_log = []
    j1, _ = j1_readout(d, replace(egg, a_over_l_m=al))
    if abs(math.log(j1["rm_ohm"] / target)) > 1e-8:
        al, polish_log = calibrate_access(
            egg, target, pair, method="Radau", guess=al, step=1e-7, xtol=1e-11, ftol=1e-9
        )
        log_line("A/L polish (Radau)", al, "evaluations", len(polish_log))
        j1, _ = j1_readout(d, replace(egg, a_over_l_m=al))
    egg = replace(egg, a_over_l_m=al)
    last = search_log[-1]
    record = dict(
        observable="J1",
        prediction_of_record_V=j1["em_V"],
        rm_at_j1_ohm=j1["rm_ohm"],
        rm_relative_miss=j1["rm_ohm"] / target - 1.0,
        rm1_ohm=rm1,
        p_old_m_s=p_old,
        a_over_l_m=al,
        new_permeability_m_s=list(egg.new_permeability),
        integrator=dict(method="Radau", rtol=1e-10),
        lsoda_search_last=dict(last, d_em_from_record_V=last["em_at_pulse_V"] - j1["em_V"]),
        declared_sha256=hashlib.sha256(DECLARED.read_bytes()).hexdigest(),
        provenance=provenance(),
    )
    (Path(args.output) / "prediction_of_record.json").write_text(
        json.dumps(record, indent=1, default=float) + "\n"
    )
    log_line("PREDICTION OF RECORD Em", j1["em_V"], "V; Rm", j1["rm_ohm"])
    out = dict(
        record,
        values=values,
        search_log=search_log,
        polish_log=polish_log,
        j1=j1,
        definition=egg_definition_record(egg),
        calibration_and_record_wall_s=time.perf_counter() - started,
    )
    terms = {}
    j1_s = float(d["time"]["j1_s"])
    small = replace(egg, activation_area_m2=1e-10)
    small = replace(
        small,
        schedule=uniform_schedule(egg.onset_s, values["new_membrane_area_at_j1_m2"], 1e-10, j1_s),
    )
    for label, e, kwargs in (
        ("radau_rtol_1e-8", egg, dict(rtol=1e-8)),
        ("bdf_rtol_1e-10", egg, dict(method="BDF")),
        ("lsoda_rtol_1e-10", egg, dict(method="LSODA")),
        ("activation_1e-10_m2", small, {}),
    ):
        r = j1_readout(d, e, **kwargs)[0]
        terms[label] = dict(
            em_V=r["em_V"], rm_ohm=r["rm_ohm"], d_em_V=r["em_V"] - j1["em_V"], wall_s=r["wall_s"]
        )
        log_line("reference term", label, terms[label]["d_em_V"])
    out["reference_term"] = terms
    out["reference_term_V"] = max(abs(t["d_em_V"]) for t in terms.values())
    return out


BAND_METHOD = "LSODA"  # band and arms; agrees with Radau on the default (record reference term)


def record_file(args):
    path = Path(args.record) if args.record else Path(args.output) / "prediction_of_record.json"
    return json.loads(path.read_text())


def member(d, values, record, *, method=BAND_METHOD):
    """Calibrate P_old and A/L for one set of values; Em at J1 from the calibrated run."""
    started = time.perf_counter()
    egg, log = calibrated(d, values, method=method, guess=record["a_over_l_m"], step=0.02)
    hit = [e for e in log if e["a_over_l_m"] == egg.a_over_l_m]
    if hit:
        em, rm = hit[-1]["em_at_pulse_V"], hit[-1]["rm_ohm"]
    else:
        j1, _ = j1_readout(d, egg, method=method)
        em, rm = j1["em_V"], j1["rm_ohm"]
    return dict(
        em_V=em,
        rm_ohm=rm,
        p_old_m_s=egg.p_old,
        a_over_l_m=egg.a_over_l_m,
        new_permeability_m_s=list(egg.new_permeability),
        evaluations=len(log),
        wall_s=time.perf_counter() - started,
    )


def band_combination(record, base_em, results, d):
    """Worst-case sum of one-at-a-time shifts (registered band rule)."""
    shifts = {}
    for label, r in results.items():
        name, end = label.split(":")
        shifts.setdefault(name, {})[end] = r["em_V"] - base_em
    lo = hi = 0.0
    per_input = {}
    for name, ends in shifts.items():
        values = list(ends.values())
        down, up = min(0.0, *values), max(0.0, *values)
        lo += down
        hi += up
        per_input[name] = dict(ends, largest_abs_V=max(abs(v) for v in values))
    e0 = record["prediction_of_record_V"]
    return dict(lo_V=e0 + lo, hi_V=e0 + hi, width_V=hi - lo, per_input=per_input)


def part_band(args):
    """One-at-a-time band members, the worst-case band, then the corner check of the top three."""
    d = load_declared()
    record = record_file(args)
    out_path = Path(args.output)
    base_values = scalar_values(d)
    base = member(d, base_values, record)
    log_line("band default", base["em_V"], "evaluations", base["evaluations"])
    results = {}
    for label, override in band_members(d):
        results[label] = dict(member(d, scalar_values(d, override), record), override=override)
        log_line("band", label, results[label]["em_V"], results[label]["evaluations"])
        (out_path / "band_partial.json").write_text(
            json.dumps(dict(default=base, members=results), indent=1, default=float) + "\n"
        )
    band = band_combination(record, base["em_V"], results, d)
    top = sorted(band["per_input"], key=lambda k: -band["per_input"][k]["largest_abs_V"])[:3]
    corners = {}
    for signs in [(a, b, c) for a in (0, 1) for b in (0, 1) for c in (0, 1)]:
        override = {}
        for name, s in zip(top, signs, strict=True):
            if name == "insertion_schedule":
                if s:
                    override["schedule"] = "back_loaded"
                continue
            group = "calibration_targets" if name.startswith("rm") else "inputs"
            override[name] = float(d[group][name]["high" if s else "low"])
        label = ",".join(f"{n}:{'high' if s else 'low'}" for n, s in zip(top, signs, strict=True))
        corners[label] = dict(member(d, scalar_values(d, override), record), override=override)
        log_line("corner", label, corners[label]["em_V"])
        (out_path / "band_partial.json").write_text(
            json.dumps(
                dict(default=base, members=results, corners=corners), indent=1, default=float
            )
            + "\n"
        )
    shift = record["prediction_of_record_V"] - base["em_V"]
    corner_em = [c["em_V"] + shift for c in corners.values()]
    lo = min(band["lo_V"], *corner_em)
    hi = max(band["hi_V"], *corner_em)
    return dict(
        method=BAND_METHOD,
        rtol=1e-10,
        prediction_of_record_V=record["prediction_of_record_V"],
        default_band_method_V=base["em_V"],
        default=base,
        members=results,
        additive=band,
        top_three=top,
        corners=corners,
        corners_outside_additive=[
            k for k, c in corners.items() if not band["lo_V"] <= c["em_V"] + shift <= band["hi_V"]
        ],
        band_lo_V=lo,
        band_hi_V=hi,
        band_width_V=hi - lo,
    )


def part_arms(args):
    """The registered arms (reported only), the J1 limits and the exposed-arm checks."""
    d = load_declared()
    record = record_file(args)
    out = {}
    for label, override in (
        ("access_law_constant_field", {"access_law": "constant_field"}),
        ("cation_selective_seal", {"access_selectivity": "cation_selective"}),
        ("narrow_gap_0.5um", {"gap_width_m": 0.5e-6}),
    ):
        out[label] = dict(member(d, scalar_values(d, override), record), override=override)
        log_line("arm", label, out[label]["em_V"])
    values = scalar_values(d)
    egg = replace(build(d, values), p_old=record["p_old_m_s"], a_over_l_m=record["a_over_l_m"])
    limits = {}
    for label, al in (("bath_equivalent_A_over_L_1e-2_m", 1e-2), ("sealed_A_over_L_0", 0.0)):
        j1, _ = j1_readout(d, replace(egg, a_over_l_m=al), method=BAND_METHOD)
        limits[label] = dict(em_V=j1["em_V"], rm_ohm=j1["rm_ohm"])
        log_line("limit", label, j1["em_V"], j1["rm_ohm"])
    out["limits_at_default_calibration"] = limits
    # Exposed arms: the new membrane faces the bath (dLB74 -VM and +VM +CCB; areas BdL73
    # Table II; 0.04 mm2/min from onset until the arm's total; old membrane on the arm's Rm1).
    j1_s = float(d["time"]["j1_s"])
    exposed = {}
    for label, rm1, total, em_measured, rm_measured in (
        ("-VM", 901e3, 0.33e-6, -0.0600, 336e3),
        ("+VM+CCB", 779e3, 0.65e-6, -0.0609, 165e3),
    ):
        rate = 0.04e-6 / 60.0
        duration = (total - egg.activation_area_m2) / rate
        arm = replace(
            build(d, values),
            new_faces="bath",
            schedule=((egg.onset_s, rate), (egg.onset_s + duration, 0.0)),
        )
        pair = tuple(d["rm_definition"]["rm1_pulse_pair"])
        arm = replace(arm, p_old=calibrate_old(arm, rm1, pair, method=BAND_METHOD))
        j1, _ = j1_readout(d, arm, method=BAND_METHOD)
        exposed[label] = dict(
            em_V=j1["em_V"],
            rm_ohm=j1["rm_ohm"],
            measured_em_V=em_measured,
            measured_rm_ohm=rm_measured,
            area_at_j1_m2=arm.area(j1_s),
            p_old_m_s=arm.p_old,
        )
        log_line("exposed", label, j1["em_V"], j1["rm_ohm"])
    out["exposed_arms"] = exposed
    return out


def part_timecourse(args):
    """The default definition (record's calibration) to the 35-min horizon, with and without
    the pulse train: Em and Rm at every pulse pair, and the J1 readouts."""
    d = load_declared()
    record = record_file(args)
    egg = replace(
        build(d, scalar_values(d)), p_old=record["p_old_m_s"], a_over_l_m=record["a_over_l_m"]
    )
    horizon = float(d["time"]["horizon_s"])
    j1_s = float(d["time"]["j1_s"])
    run = simulate(egg, horizon, method=BAND_METHOD, record=(j1_s,))
    ks = sorted(k for k in run.onset_V if k in run.sample_V and k - 1 in run.sample_V)
    p = egg.pulses
    quiet = simulate(
        replace(egg, pulses=replace(p, enabled=False)), j1_s, method=BAND_METHOD, record=(j1_s,)
    )
    return dict(
        method=BAND_METHOD,
        times_s=[p.onset(k) for k in ks],
        em_V=[run.onset_V[k] for k in ks],
        rm_ohm=[run.rm(k)[0] for k in ks],
        at_j1=run.at[j1_s],
        unpulsed_at_j1=quiet.at[j1_s],
        unpulsed_minus_pulsed_em_at_j1_V=quiet.at[j1_s]["V"] - run.at[j1_s]["V"],
        steps=run.steps,
        wall_s=run.wall_s,
    )


PARTS = dict(record=part_record, band=part_band, arms=part_arms, timecourse=part_timecourse)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("parts")
    parser.add_argument("--output", required=True)
    parser.add_argument("--record", default=None, help="prediction_of_record.json (band, arms)")
    args = parser.parse_args(argv)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    for name in args.parts.split(","):
        started = time.perf_counter()
        try:
            result = PARTS[name](args)
            result["verdict"] = "done"
        except Exception as error:  # Kept as the part's result.
            result = dict(part=name, verdict="error", error=repr(error), tb=traceback.format_exc())
        result["part"] = name
        result["provenance"] = provenance()
        result["part_wall_s"] = time.perf_counter() - started
        (output / f"{name}.json").write_text(json.dumps(result, indent=1, default=float) + "\n")
        print(name, result.get("verdict"), f"{result['part_wall_s']:.1f} s", flush=True)


if __name__ == "__main__":
    main()
