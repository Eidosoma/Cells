"""R-loop: FR-7's first closed loop (F4), an independent reference.

Written from D231, docs/EXCITABLE_TISSUE_EQUATIONS.md (sections 1 to 3 and 5: the cell, the
constant-field flux and the Na/K pump `nak_atp_mass_action_positive@1`),
docs/KINETIC_PUMP_PROCESS.md (the pump's interface: the chemical drive's 1 M standard state,
saturation, the signed rate near stall), the coupling note's Appendix A (the two-state regulator,
the state-complement factor) and R-chain (this package). The world's numbers are the FR-7 lane's
exported input values, relayed by the lead (loop_worlds.py). Its author never read the engine,
the FR-7 lane's files or any engine test. numpy and scipy only; nothing imports `cells`.

The loop: one cell facing a held bath at 0 V, with R-cell's capacitor, Q = F (sum z n + X) and
V = Q/C.
* **Ions.** Constant-field leaks per species; fixed gate-free populations (P N/rho_ref each); the
  Na/K pump (3 Na out and 2 K in per cycle, from the declared fuel pools and standard state); and
  the Na-leak units, N gate-free units carrying P_unit N/rho_ref of Na permeability.
* **The regulator:** ds/dt = k_on u (1 - s) - k_off s, u = c_Na^n/(K^n + c_Na^n) of cytosolic
  Na.
* **The precursor**, a supplied, fast-cleared species: dn_P/dt = S_P - k_P n_P - k_a F n_P.
* **The producer:** units at c_u k_a F n_P, with F = F_T(t) F_loop(t). F_T is the template's
  factor (R-chain's law). F_loop is the route's factor:
  - 1 - s (state complement, b = 0) in the closed arm;
  - in the clamped arm, 1 - s until t_d and F* after, with the coupling switched off.
* **The units:** m maturation stages (kappa) and removal k_r on all of N, as in R-chain.
* **The account:** W, the precursor consumed into units (fmol); R_removed, the units removed;
  C_P, the precursor cleared (fmol). The total n_P + (sum M + N + R_removed)/c_u + C_P - S_P t
  is conserved.

Plants and arms are `LoopVariant`s of the ODE.
"""

import copy
import math
from dataclasses import dataclass

import numpy as np
from scipy.optimize import fsolve

from validation.coupling import piecewise_ode
from validation.division.cleft_egg_reference import ghk_flux  # R-full's law (S3-qualified)
from validation.fr7.references.chain import FMOL, Template, hill_activation, units_per_fmol

# ---------------------------------------------------------------- the pump (section 5)


def pump(p, cNa_i, cNa_o, cK_i, cK_o, V, F, RT, standard_mM=None):
    """`nak_atp_mass_action_positive@1`: (cycles in mol/s, cycle free energy G and chemical drive
    in J/mol).
    - Inward potentials: mu_s = RT ln(c_i/c_o) + z F V, with z = +1 for Na and K.
    - drive = dG0 + RT ln(ADP Pi/(standard x ATP)).
    - G = drive - 3 mu_Na + 2 mu_K.
    - Saturation in log form, with orders 3 (Na inside), 2 (K outside) and 1 (ATP).
    - rate = capacity x availability x saturation x (1 - e^(G/RT)), as -expm1 near stall."""
    std = p["standard_state_mM"] if standard_mM is None else standard_mM
    mu_na = RT * math.log(cNa_i / cNa_o) + F * V
    mu_k = RT * math.log(cK_i / cK_o) + F * V
    drive = p["deltaG0_J_per_mol"] + RT * math.log(p["adp_mM"] * p["pi_mM"]
                                                   / (std * p["atp_mM"]))
    G = drive - 3.0 * mu_na + 2.0 * mu_k
    log_sat = (-math.log1p((p["km_na_mM"] / cNa_i) ** 3) - math.log1p((p["km_k_mM"] / cK_o) ** 2)
               - math.log1p(p["km_atp_mM"] / p["atp_mM"]))
    rate = p["capacity_mol_per_s"] * p["availability"] * math.exp(log_sat) * (-math.expm1(G / RT))
    return rate, G, drive


# ---------------------------------------------------------------- variants (plants and arms)


@dataclass(frozen=True)
class LoopVariant:
    """The closed arm (every default), the clamped arm, or one plant."""

    name: str = "closed"
    clamp_from_s: float = math.inf  # the loop factor held from this time on...
    clamp_value: float = math.nan  # ...at this value (F*; 1 for the cut-at-one plant)
    nu_delta: int = 0
    cu_per_mol: bool = False
    stages_delta: int = 0
    removal_on_increment: bool = False
    route_on_clearance: bool = False  # both factors move to the precursor's clearance
    factor_lag_s: float = 0.0  # both factors read dt/2 earlier (s by its first-order Taylor)
    factor_from_amount: bool = False  # the template's factor reads n_T as if it were mM
    route_state_fraction: bool = False  # F_loop = s instead of 1 - s
    regulator_reads_amount: bool = False  # u of the Na amount (fmol) as if it were mM
    regulator_quasi_steady: bool = False  # s replaced by s*(u) = k_on u/(k_on u + k_off)
    pump_standard_mM: float = math.nan  # the pump's standard state replaced (1 mM: no 1000)
    template_hold_from_s: float = math.inf  # the template replaced from this time on...
    template_hold_fmol: float = math.nan  # ...by this constant amount (the floor's sensitivity)


CLOSED = LoopVariant()


# ---------------------------------------------------------------- the world


class LoopWorld:
    """R-loop's world from the inputs' `loop` block, under a variant."""

    def __init__(self, inputs, variant=CLOSED):
        lp, c = inputs["loop"], inputs["constants"]
        self.lp, self.variant = lp, variant
        self.avogadro = c["avogadro_per_mol"]
        self.F = c["faraday_C_per_mol"]
        cell = lp["cell"]
        self.rt = c["gas_J_per_mol_K"] * cell["temperature_K"]
        self.species, self.z = tuple(cell["species"]), tuple(cell["valence"])
        self.bath = tuple(cell["bath_mM"])
        self.volume, self.area = cell["volume_pL"], cell["patch_area_m2"]
        self.cap = cell["capacitance_F"]
        self.leak = tuple(cell["leak_permeability_m_s"])
        self.fixed_pa = [0.0] * len(self.z)  # the fixed gate-free populations, summed per species
        for pop in cell["fixed_populations"]:
            for s, r in enumerate(pop["relative_permeability"]):
                self.fixed_pa[s] += pop["permeability_m_s"] * r * pop["units"] / pop[
                    "reference_density_per_m2"]
        self.iNa, self.iK = self.species.index("Na"), self.species.index("K")
        self.pump = dict(lp["pump"])
        u = lp["units"]
        self.P_unit, self.rel = u["permeability_m_s"], tuple(u["relative_permeability"])
        self.rho = u["reference_density_per_m2"]
        self.nu, self.ka = u["nu"], u["assembly_per_s"]
        self.kappa, self.kr = u["maturation_per_s"], u["removal_per_s"]
        self.m_declared = u["stages"]
        p = lp["precursor"]
        self.kP = p["clearance_per_s"]
        tp = lp["template"]
        self.template = Template(tp["n0_fmol"], tp["clearance_per_s"], tp["production"])
        f = tp["factor"]
        self.K, self.n, self.b = f["K_mM"], f["n"], f["basal"]
        reg = lp["regulator"]
        self.k_on, self.k_off = reg["k_on_per_s"], reg["k_off_per_s"]
        self.K_reg, self.n_reg = reg["K_mM"], reg["n"]
        self.start = lp["start"]
        self.S, self.nP0 = self.start["supply_fmol_per_s"], self.start["n_P_fmol"]
        self.horizon, self.rows = lp["horizon_s"], tuple(lp["rows_s"])
        v = variant
        nu = self.nu + v.nu_delta
        self.cu_declared = units_per_fmol(self.nu, self.avogadro)
        self.cu = self.avogadro / nu if v.cu_per_mol else units_per_fmol(nu, self.avogadro)
        self.m = self.m_declared + v.stages_delta
        if self.m < 0:
            raise ValueError(f"the variant {v.name} does not apply (m = 0)")
        M0 = list(self.start["M_units"])
        while len(M0) > self.m:
            last = M0.pop()
            if M0:
                M0[-1] += last
        self.M0 = tuple(M0)
        self.N0 = self.start["N_units"]

    def template_amount(self, t):
        v = self.variant
        if t >= v.template_hold_from_s:
            return v.template_hold_fmol
        return self.template.amount_scalar(t)

    def factor_T(self, t):
        """F_T at t (as the variant reads the template)."""
        nT = self.template_amount(t)
        c = nT if self.variant.factor_from_amount else nT / self.volume
        if c <= 0.0:
            return self.b
        try:
            h = 1.0 / (1.0 + (self.K / c) ** self.n)
        except OverflowError:
            h = 0.0
        return self.b + (1.0 - self.b) * h

    def regulator_input(self, n_na):
        c = n_na if self.variant.regulator_reads_amount else n_na / self.volume
        return float(hill_activation(c, self.K_reg, self.n_reg))


# ---------------------------------------------------------------- the model


class LoopModel:
    """State: the charge (fmol), every species' amount but the follower (the last charged one), s,
    n_P, M_1..M_m, N, W, R_removed and C_P."""

    def __init__(self, world):
        w = self.w = world
        self.ns = len(w.z)
        self.follower = max(i for i, x in enumerate(w.z) if x != 0)
        self.others = [i for i in range(self.ns) if i != self.follower]
        self.i_s = 1 + len(self.others)
        self.i_P = self.i_s + 1
        self.i_M = self.i_P + 1
        self.i_N = self.i_M + w.m
        self.i_W, self.i_R, self.i_C = self.i_N + 1, self.i_N + 2, self.i_N + 3
        self.size = self.i_C + 1
        self.route_pa = [w.leak[s] * w.area + w.fixed_pa[s] for s in range(self.ns)]
        self.unit_pa = [w.P_unit * w.rel[s] / w.rho for s in range(self.ns)]
        self.background = w.start["background_fmol"]

    def ions(self, y):
        """(amounts in fmol per species, V)."""
        w = self.w
        n = [0.0] * self.ns
        for j, s in enumerate(self.others):
            n[s] = float(y[1 + j])
        n[self.follower] = (float(y[0]) - self.background - math.fsum(
            w.z[s] * n[s] for s in self.others)) / w.z[self.follower]
        return n, float(y[0]) * FMOL * w.F / w.cap

    def s_value(self, y):
        w = self.w
        if w.variant.regulator_quasi_steady:
            n, _ = self.ions(y)
            u = w.regulator_input(n[w.iNa])
            return w.k_on * u / (w.k_on * u + w.k_off)
        return float(y[self.i_s])

    def ds_dt(self, y):
        w = self.w
        n, _ = self.ions(y)
        u = w.regulator_input(n[w.iNa])
        s = float(y[self.i_s])
        return w.k_on * u * (1.0 - s) - w.k_off * s

    def loop_factor(self, t, y):
        """F_loop(t): the route's factor on the producer's rate."""
        v = self.w.variant
        if t >= v.clamp_from_s:
            return v.clamp_value
        s = self.s_value(y)
        if v.factor_lag_s:
            s = s - v.factor_lag_s * self.ds_dt(y)
        return s if v.route_state_fraction else 1.0 - s

    def fluxes(self, y, N):
        """Outward mol/s per species: (routes, units, pump transfer), and the pump's
        (cycles, G, drive)."""
        w = self.w
        n, phi = self.ions(y)
        c = [x / w.volume for x in n]
        u = w.F * phi / w.rt
        routes = [ghk_flux(self.route_pa[s], w.z[s], u, c[s], w.bath[s]) for s in range(self.ns)]
        unit = [ghk_flux(self.unit_pa[s] * N, w.z[s], u, c[s], w.bath[s]) for s in range(self.ns)]
        std = w.variant.pump_standard_mM
        cycles, G, drive = pump(w.pump, c[w.iNa], w.bath[w.iNa], c[w.iK], w.bath[w.iK], phi,
                                w.F, w.rt, None if math.isnan(std) else std)
        transfer = [0.0] * self.ns
        transfer[w.iNa], transfer[w.iK] = 3.0 * cycles, -2.0 * cycles
        return routes, unit, transfer, (cycles, G, drive)

    def rhs(self, t, y):
        w, v = self.w, self.w.variant
        out = np.zeros(self.size)
        N = float(y[self.i_N])
        routes, unit, transfer, _ = self.fluxes(y, N)
        dn = [-(routes[s] + unit[s] + transfer[s]) / FMOL for s in range(self.ns)]
        out[0] = math.fsum(w.z[s] * dn[s] for s in range(self.ns))
        for j, s in enumerate(self.others):
            out[1 + j] = dn[s]
        if not v.regulator_quasi_steady:
            out[self.i_s] = self.ds_dt(y)
        F = w.factor_T(t - v.factor_lag_s) * self.loop_factor(t, y)
        nP = float(y[self.i_P])
        if v.route_on_clearance:
            cons, clr = w.ka * nP, w.kP * F * nP
        else:
            cons, clr = w.ka * F * nP, w.kP * nP
        out[self.i_P] = w.S - clr - cons
        q = w.cu * cons
        iM, m = self.i_M, w.m
        if m > 0:
            out[iM] = q - w.kappa * y[iM]
            for j in range(1, m):
                out[iM + j] = w.kappa * (y[iM + j - 1] - y[iM + j])
            inflow = w.kappa * y[iM + m - 1]
        else:
            inflow = q
        removal = w.kr * (N - w.N0) if v.removal_on_increment else w.kr * N
        out[self.i_N] = inflow - removal
        out[self.i_W], out[self.i_R], out[self.i_C] = cons, removal, clr
        return out

    def jac(self, t, y):
        """Central differences in every column (the system is small)."""
        J = np.empty((self.size, self.size))
        for col in range(self.size):
            h = 1e-7 * max(abs(float(y[col])), self.scale[col])
            yp, ym = y.copy(), y.copy()
            yp[col] += h
            ym[col] -= h
            J[:, col] = (self.rhs(t, yp) - self.rhs(t, ym)) / (2.0 * h)
        return J

    def initial(self):
        w, st = self.w, self.w.start
        y = np.zeros(self.size)
        n = list(st["amounts_fmol"])
        y[0] = math.fsum(w.z[s] * n[s] for s in range(self.ns)) + self.background
        for j, s in enumerate(self.others):
            y[1 + j] = n[s]
        y[self.i_s] = st["s"]
        y[self.i_P] = w.nP0
        y[self.i_M:self.i_M + w.m] = w.M0
        y[self.i_N] = w.N0
        self.scale = np.maximum(np.abs(y), 1e-6)
        self.scale[self.i_W] = self.scale[self.i_C] = max(w.nP0, 1e-30)
        self.scale[self.i_R] = 1.0
        return y

    def atol(self):
        w = self.w
        a = np.empty(self.size)
        a[0] = 1e-17
        a[1:self.i_s] = 1e-15
        a[self.i_s] = 1e-14
        a[self.i_P] = 1e-14 * max(w.nP0, 1e-30)
        a[self.i_M:self.i_N + 1] = 1e-10
        a[self.i_W] = a[self.i_C] = 1e-14 * max(w.nP0, 1e-30)
        a[self.i_R] = 1e-10
        return a

    def record(self, t, y):
        w = self.w
        n, phi = self.ions(y)
        N = float(y[self.i_N])
        M = [float(y[self.i_M + j]) for j in range(w.m)]
        nP, W = float(y[self.i_P]), float(y[self.i_W])
        Rr, C = float(y[self.i_R]), float(y[self.i_C])
        _, unit, _, (cycles, G, drive) = self.fluxes(y, N)
        return dict(
            t=t, V=phi, amounts=n, s=self.s_value(y), u=w.regulator_input(n[w.iNa]),
            F_loop=self.loop_factor(t, y), F_T=w.factor_T(t),
            n_T=float(w.template_amount(t)), n_P=nP, M=M, N=N, W=W, R=Rr, C_P=C,
            total=nP + (sum(M) + N + Rr) / w.cu_declared + C - w.S * t,
            PA_units=w.P_unit * w.rel[w.iNa] * N / w.rho, pump_cycles_fmol_s=cycles / FMOL,
            pump_G=G, pump_drive=drive,
            I_units=w.F * math.fsum(w.z[s] * unit[s] for s in range(self.ns)),
            I_pump=w.F * cycles)


def simulate(world, rows, *, rtol=1e-12, method="Radau", dense=False):
    """Integrate the loop from 0 to the horizon; records at the rows (integration end points).
    With dense, also the (min, max) of s over every accepted step."""
    model = LoopModel(world)
    y0 = model.initial()
    v = world.variant
    points = {0.0, float(world.horizon), *map(float, rows)}
    for b in world.template.breakpoints():
        points |= {b, b + v.factor_lag_s}
    if math.isfinite(v.clamp_from_s):
        points.add(float(v.clamp_from_s))
    if math.isfinite(v.template_hold_from_s):
        points.add(float(v.template_hold_from_s))
    points = sorted(p for p in points if 0.0 <= p <= world.horizon)

    def segment(t0, t1):
        return model.rhs, (model.jac if method in ("Radau", "BDF", "LSODA") else None)

    run = piecewise_ode.Run(segment, y0, points, rtol=rtol, atol=model.atol(), method=method)
    recs = [model.record(float(t), run.state(float(t))) for t in rows]
    if dense:
        s = np.concatenate([seg[5][:, model.i_s] for seg in run.segments])
        return recs, run.steps, (float(np.min(s)), float(np.max(s)))
    return recs, run.steps


# ---------------------------------------------------------------- the start


def steady_start(inputs, *, settle_s=3000.0):
    """The closed loop's own steady state with no template and N = N0.

    1. The ions and s settle with the units frozen at N0 and the producer off. The fixed charge X
       is declared; P, impermeant, keeps its declared amount.
    2. Newton polishes the result.
    3. s0 = s*(u0), F_loop0 = 1 - s0 and F0 = b_T F_loop0.
    4. n_P0 = k_r N0/(c_u k_a F0) makes production equal removal.
    5. S_P = n_P0 (k_P + k_a F0) holds n_P0.

    Returns (start dict, report dict)."""
    lp = inputs["loop"]
    cell = lp["cell"]
    frozen = copy.deepcopy(inputs)
    fl = frozen["loop"]
    fl["units"]["assembly_per_s"], fl["units"]["removal_per_s"] = 0.0, 0.0
    fl["template"] = dict(lp["template"], n0_fmol=0.0, production=[[0.0, 0.0]])
    amounts = list(cell["initial_amounts_fmol"])
    fl["start"] = dict(amounts_fmol=amounts, background_fmol=cell["fixed_charge_fmol"], s=0.0,
                       n_P_fmol=0.0, supply_fmol_per_s=0.0, M_units=[0.0] * lp["units"]["stages"],
                       N_units=lp["units"]["N0"])
    world = LoopWorld(frozen)
    model = LoopModel(world)
    y0 = model.initial()
    run = piecewise_ode.Run(lambda a, b: (model.rhs, model.jac), y0, [0.0, settle_s], rtol=1e-11,
                            atol=model.atol(), method="Radau")
    y = run.end_state()
    free = list(range(model.i_s + 1))

    def residual(x):
        yy = y.copy()
        yy[free] = x
        r = model.rhs(settle_s, yy)[free]
        return r / np.maximum(np.abs(x), 1e-6)

    x = fsolve(residual, y[free], xtol=1e-15)
    y[free] = x
    n, phi = model.ions(y)
    s0 = float(y[model.i_s])
    u0 = world.regulator_input(n[world.iNa])
    units = lp["units"]
    F_loop0 = 1.0 - s0
    F0 = lp["template"]["factor"]["basal"] * F_loop0
    cu = units_per_fmol(units["nu"], inputs["constants"]["avogadro_per_mol"])
    nP0 = units["removal_per_s"] * units["N0"] / (cu * units["assembly_per_s"] * F0)
    S = nP0 * (lp["precursor"]["clearance_per_s"] + units["assembly_per_s"] * F0)
    rhs = model.rhs(settle_s, y)
    start = dict(amounts_fmol=n, V=phi, background_fmol=cell["fixed_charge_fmol"], s=s0,
                 n_P_fmol=nP0, supply_fmol_per_s=S, M_units=[0.0] * units["stages"],
                 N_units=units["N0"])
    report = dict(u0=u0, s_star_check=world.k_on * u0 / (world.k_on * u0 + world.k_off),
                  F_loop0=F_loop0, F0=F0, production_units_per_s=cu * units["assembly_per_s"]
                  * F0 * nP0, removal_units_per_s=units["removal_per_s"] * units["N0"],
                  stationarity_residual_fmol_per_s=float(np.max(np.abs(rhs[1:model.i_s]))),
                  charge_rate_fmol_per_s=float(abs(rhs[0])),
                  s_rate_per_s=float(abs(rhs[model.i_s])), settle_s=settle_s,
                  mM=[x / world.volume for x in n])
    return start, report
