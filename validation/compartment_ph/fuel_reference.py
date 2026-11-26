"""Item 4's reference: finite fuel shared by a regeneration reaction and an ATP-driven pump
(R-fuel), an independent reference, with held fuel as its comparison.

Written from the specification in this folder's REFERENCES_USAGE.md ("Finite fuel"), itself from
ARCHITECTURE.md's "Material identity and fuel" (F2, the first case), D176 (decisions 1 and 2),
D152's §2.2 (`cells.species_reaction.ideal_detailed_balance_mass_action@1`) and COMPARTMENT_PH_TRANSFER_DESIGN.md's §5
and §6 (the pump's form), without reading the engine. numpy, scipy and the standard library.

Units: fmol, pL, mM (= fmol/pL), s, m, m/s; potentials in J/mol; energies in pJ (1e-3 x fmol x
J/mol). The standard state is c0 (mM; 1000 by default), and every activity is a = c/c0.

* **The world:** a closed cell c (the fuel node, V_c) and a store s (V_s) across one patch (A).
  Rows: ATP, ADP, Pi, a donor D and its product P at c; a neutral solute Y at c and s. Each row's
  transformed standard potential mu0'/RT comes from one registry, and every Delta G0 below is
  formed from it (F2's one authority).
* **Regeneration** at c, D + ADP + Pi <-> P + ATP, by D152's passive law:
  v = m(t) V_c c0 k_f [a_D a_ADP a_Pi - exp(dG0_reg/RT) a_P a_ATP] (fmol/s), with
  dG0_reg = mu0'(P) + mu0'(ATP) - mu0'(D) - mu0'(ADP) - mu0'(Pi), and m(t) in [0, 1] a schedule.
* **The pump,** §6's form with Y for H+ and no voltage term: per cycle one ATP -> ADP + Pi at c
  and n Y from c to s. dG_cyc = dG_ATP + n RT ln(c_Ys/c_Yc), dG_ATP = dG0_hyd
  + RT ln(c_ADP c_Pi/(c_ATP c0)), dG0_hyd = mu0'(ADP) + mu0'(Pi) - mu0'(ATP);
  J_cyc = k a S (1 - exp(dG_cyc/RT)), S = [1 + (K_Y/c_Yc)^n]^-1 [1 + K_ATP/c_ATP]^-1. It is
  evaluated as the identical rational form k a [c_Yc^n c_ATP - c_ADP c_Pi e^(dG0_hyd/RT)
  c_Ys^n/c0] / [(K_Y^n + c_Yc^n)(K_ATP + c_ATP)], finite at the integrator's trial states.
* **The leak of Y:** J_Y = 1e15 P_Y A (c_Ys - c_Yc), from s to c (Fick's law at z = 0).
* **Held fuel** (§5.1): ATP, ADP and Pi are held, the regeneration is off, and the maintenance
  supplies W = int (-dG_ATP) J_cyc dt.
* **Energy:** dG_stored + Q = W, with G_stored = sum over rows of n (mu0' + RT (ln(c/c0) - 1)),
  Q = int [-dG_cyc J_cyc + J_Y RT ln(c_Ys/c_Yc) - dG_reg v] dt, and W = 0 with finite fuel.
  Each heat is kept apart.

Sources: Rao R, Esposito M. Phys Rev X 2016;6:041064 (detailed-balanced mass action and its
thermodynamics); Hill TL. Free Energy Transduction in Biology. Academic Press; 1977 (a pump's cycle
free energy); Hairer E, Wanner G. Solving ODEs II. Springer; 1996 (Radau IIA).
"""

import math
from dataclasses import dataclass

import numpy as np

from validation.coupling import piecewise_ode

ROWS = ("ATP", "ADP", "Pi", "D", "P")  # at the cell
FMOL_PER_MOL = 1e15


@dataclass(frozen=True)
class FuelWorld:
    """Every quantity in the units of the module docstring. ``mu0_RT``: mu0'/RT of ATP, ADP, Pi,
    D, P and Y (the registry's, at temperature_K). ``off_windows``: [start, end) windows where the
    regeneration's m = 0 (m = 1 elsewhere). ``held``: ATP, ADP and Pi held, regeneration off."""

    gas_J_per_mol_K: float
    temperature_K: float
    mu0_RT: dict
    cell_volume_pL: float
    store_volume_pL: float
    patch_area_m2: float
    start_mM: dict  # ATP, ADP, Pi, D, P at c; Y_c, Y_s
    pump_capacity_fmol_per_s: float
    pump_n: int
    K_Y_mM: float
    K_ATP_mM: float
    leak_m_s: float
    k_f_per_s: float
    off_windows: tuple = ()
    availability: float = 1.0
    held: bool = False
    standard_mM: float = 1000.0

    @property
    def rt(self):
        return self.gas_J_per_mol_K * self.temperature_K

    def dG0_hyd(self):
        m = self.mu0_RT
        return self.rt * (m["ADP"] + m["Pi"] - m["ATP"])

    def dG0_reg(self):
        m = self.mu0_RT
        return self.rt * (m["P"] + m["ATP"] - m["D"] - m["ADP"] - m["Pi"])

    def check(self):
        if set(self.mu0_RT) != {*ROWS, "Y"} or not all(map(math.isfinite, self.mu0_RT.values())):
            raise ValueError("finite mu0'/RT for ATP, ADP, Pi, D, P and Y")
        if set(self.start_mM) != {*ROWS, "Y_c", "Y_s"} or not all(
                x > 0 for x in self.start_mM.values()):
            raise ValueError("every row starts > 0 (a trace is a start, never a zero)")
        if not all(x > 0 for x in (self.cell_volume_pL, self.store_volume_pL, self.patch_area_m2,
                                   self.K_Y_mM, self.K_ATP_mM, self.standard_mM, self.rt)):
            raise ValueError("volumes, area, K_Y, K_ATP, c0 and RT are > 0")
        if not (isinstance(self.pump_n, int) and 1 <= self.pump_n <= 4):
            raise ValueError("the pump's n is an integer in 1..4 (§6)")
        if not (self.pump_capacity_fmol_per_s >= 0 and self.leak_m_s >= 0 and self.k_f_per_s >= 0
                and 0 <= self.availability <= 1):
            raise ValueError("k, P_Y and k_f >= 0; availability in [0, 1]")
        for a, b in self.off_windows:
            if not 0 <= a < b:
                raise ValueError("windows are [start, end) with 0 <= start < end")

    def m(self, t):
        return 0.0 if any(a <= t < b for a, b in self.off_windows) else 1.0


class _FuelModel:
    # State: the cell's rows (fmol), Y_c, Y_s (fmol), then the accumulators.
    NAMES = (*ROWS, "Y_c", "Y_s", "Q_pump", "Q_leak", "Q_reg", "W", "cycles", "regenerated")

    def __init__(self, world):
        world.check()
        self.w = w = world
        self.V = (w.cell_volume_pL, w.store_volume_pL)
        self.i = {name: k for k, name in enumerate(self.NAMES)}
        s = w.start_mM
        y0 = np.zeros(len(self.NAMES))
        for r in ROWS:
            y0[self.i[r]] = s[r] * self.V[0]
        y0[self.i["Y_c"]], y0[self.i["Y_s"]] = s["Y_c"] * self.V[0], s["Y_s"] * self.V[1]
        self.y0 = y0
        amounts = float(np.max(y0[:7]))
        G = abs(1e-3 * w.rt * amounts)
        self.scale = np.array([*np.abs(y0[:7]), G, G, G, G, amounts, amounts])
        self.e_hyd = math.exp(w.dG0_hyd() / w.rt)
        self.e_reg = math.exp(w.dG0_reg() / w.rt)
        self.breaks = sorted({x for win in w.off_windows for x in win if math.isfinite(x)})

    def conc(self, y):
        c = {r: y[self.i[r]] / self.V[0] for r in ROWS}
        if self.w.held:
            c.update(ATP=self.w.start_mM["ATP"], ADP=self.w.start_mM["ADP"],
                     Pi=self.w.start_mM["Pi"])
        c["Y_c"], c["Y_s"] = y[self.i["Y_c"]] / self.V[0], y[self.i["Y_s"]] / self.V[1]
        return c

    def rates(self, t, y, m=None):
        """(c, J_cyc, J_Y, v, m). ``m`` is the segment's schedule value; by default m(t)."""
        w, c, c0 = self.w, self.conc(y), self.w.standard_mM
        n = w.pump_n
        num =c["Y_c"] ** n * c["ATP"] - c["ADP"] * c["Pi"] * self.e_hyd * c["Y_s"] ** n / c0
        den = (w.K_Y_mM ** n + c["Y_c"] ** n) * (w.K_ATP_mM + c["ATP"])
        J = w.pump_capacity_fmol_per_s * w.availability * num / den
        JY = FMOL_PER_MOL * w.leak_m_s * w.patch_area_m2 * (c["Y_s"] - c["Y_c"])
        if m is None:
            m = w.m(t)
        m = 0.0 if w.held else m
        v = m * self.V[0] * c0 * w.k_f_per_s * (
            (c["D"] / c0) * (c["ADP"] / c0) * (c["Pi"] / c0)
            - self.e_reg * (c["P"] / c0) * (c["ATP"] / c0))
        return c, J, JY, v, m

    def free_energies(self, c):
        """(dG_ATP, dG_cyc, dG_reg) in J/mol. Concentrations are floored at 1e-300 mM, which
        changes nothing at a physical state and keeps the integrator's trial states finite."""
        w, rt, c0 = self.w, self.w.rt, self.w.standard_mM
        c = {k: max(x, 1e-300) for k, x in c.items()}
        dG_atp = w.dG0_hyd() + rt * math.log(c["ADP"] * c["Pi"] / (c["ATP"] * c0))
        dG_cyc = dG_atp + w.pump_n * rt * math.log(c["Y_s"] / c["Y_c"])
        dG_reg = w.dG0_reg() + rt * math.log(c["P"] * c["ATP"] * c0
                                             / (c["D"] * c["ADP"] * c["Pi"]))
        return dG_atp, dG_cyc, dG_reg

    def rhs(self, t, y, m=None):
        c, J, JY, v, _ = self.rates(t, y, m)
        out = np.zeros(len(self.NAMES))
        i = self.i
        if not self.w.held:
            out[i["ATP"]], out[i["ADP"]], out[i["Pi"]] = v - J, J - v, J - v
        out[i["D"]], out[i["P"]] = -v, v
        n = self.w.pump_n
        out[i["Y_c"]], out[i["Y_s"]] = -n * J + JY, n * J - JY
        dG_atp, dG_cyc, dG_reg = self.free_energies(c)
        out[i["Q_pump"]] = 1e-3 * (-dG_cyc) * J
        out[i["Q_leak"]] = 1e-3 * JY * self.w.rt * math.log(max(c["Y_s"], 1e-300)
                                                            / max(c["Y_c"], 1e-300))
        out[i["Q_reg"]] = 1e-3 * (-dG_reg) * v
        out[i["W"]] = 1e-3 * (-dG_atp) * J if self.w.held else 0.0
        out[i["cycles"]], out[i["regenerated"]] = J, v
        return out

    def stored_free_energy(self, y):
        w, rt, c0 = self.w, self.w.rt, self.w.standard_mM
        c = self.conc(y)
        g = 0.0
        for r in ROWS:
            n = c[r] * self.V[0]
            g += n * rt * (w.mu0_RT[r] + math.log(c[r] / c0) - 1.0)
        for key, V in (("Y_c", self.V[0]), ("Y_s", self.V[1])):
            g += c[key] * V * rt * (w.mu0_RT["Y"] + math.log(c[key] / c0) - 1.0)
        return 1e-3 * g


class FuelRun:
    """One run. ``at[t]``: dict(c {ATP, ADP, Pi, D, P, Y_c, Y_s} (mM), J_cyc (fmol/s), J_Y (s to c),
    v (fmol/s), m, dG_ATP, dG_cyc, dG_reg (J/mol), cycles, regenerated (fmol), heat_pJ
    {pump, leak, reg}, Q, W, stored_change, energy_residual (dG_stored + Q - W) (pJ), moieties
    {adenine, phosphate, donor, Y} (fmol))."""

    def __init__(self, model, run, record):
        self.model, self.run = model, run
        self.steps = run.steps
        self.G0 = model.stored_free_energy(model.y0)
        self.at = {t: self.observe(t) for t in record}

    def observe(self, t):
        m = self.model
        y = self.run.state(t)
        i = m.i
        c, J, JY, v, mult = m.rates(t, y)
        dG_atp, dG_cyc, dG_reg = m.free_energies(c)
        heat = {"pump": float(y[i["Q_pump"]]), "leak": float(y[i["Q_leak"]]),
                "reg": float(y[i["Q_reg"]])}
        Q, W = sum(heat.values()), float(y[i["W"]])
        dG = m.stored_free_energy(y) - self.G0
        n = {key: c[key] * m.V[0] for key in ROWS}
        return dict(
            t=t, c=c, J_cyc=J, J_Y=JY, v=v, m=mult, dG_ATP=dG_atp, dG_cyc=dG_cyc, dG_reg=dG_reg,
            cycles=float(y[i["cycles"]]), regenerated=float(y[i["regenerated"]]), heat_pJ=heat,
            Q_pJ=Q, W_pJ=W, stored_change_pJ=dG, energy_residual_pJ=dG + Q - W,
            moieties=dict(adenine=n["ATP"] + n["ADP"], phosphate=n["ATP"] + n["Pi"],
                          donor=n["D"] + n["P"],
                          Y=float(y[i["Y_c"]]) + float(y[i["Y_s"]])))


def integrate(world, t_end, *, record=(), rtol=1e-11, method="Radau", atol_fraction=1e-6):
    """R-fuel from the start to t_end; Radau at rtol 1e-11. The schedule's breakpoints are
    segment ends, and m is held at its value inside each segment, so the right-hand side is
    smooth on every closed segment."""
    model = _FuelModel(world)
    record = tuple(sorted({float(t) for t in record}))
    points = sorted({0.0, float(t_end), *record, *(b for b in model.breaks if 0 < b < t_end)})
    def segment(t0, t1):  # m is constant on each segment, including at its ends
        m = world.m(0.5 * (t0 + t1))
        return (lambda t, y: model.rhs(t, y, m)), None

    run = piecewise_ode.Run(segment, model.y0, points, rtol=rtol,
                            atol=rtol * atol_fraction * model.scale, method=method)
    return FuelRun(model, run, record)


def registry_potentials(rt):
    """The proposal's potentials (mu0'/RT at the given RT): dG0_hyd = -30.5 kJ/mol and
    mu0'(D) - mu0'(P) = 60 kJ/mol, so dG0_reg = -29.5 kJ/mol; Y's cancels."""
    return {"ATP": 30.5e3 / rt, "ADP": 0.0, "Pi": 0.0, "D": 60.0e3 / rt, "P": 0.0, "Y": 0.0}


def acceptance_world(*, held=False, off_windows=((100.0, 300.0),)):
    """The calibrated first case: regeneration off on [100, 300) s; ``held=True`` is held fuel;
    ``off_windows=()`` is the negative control (m = 1)."""
    R, T = 8.314462618, 310.0
    return FuelWorld(
        gas_J_per_mol_K=R, temperature_K=T, mu0_RT=registry_potentials(R * T),
        cell_volume_pL=4.18879, store_volume_pL=6.54498e-2, patch_area_m2=7.85398e-10,
        start_mM={"ATP": 3.0, "ADP": 0.3, "Pi": 3.0, "D": 30.0, "P": 3.0, "Y_c": 10.0,
                  "Y_s": 10.0},
        pump_capacity_fmol_per_s=0.1, pump_n=1, K_Y_mM=1.0, K_ATP_mM=0.1, leak_m_s=1e-9,
        k_f_per_s=1e4, off_windows=tuple(off_windows), held=held)
