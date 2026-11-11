"""Independent reduced reference for resolved_pump_water@1 (numpy/scipy; no Cells code).

It reads a plain resolved_pump_water@1 definition (the JSON dict) and writes the
declared laws as one smooth ODE system, integrated with scipy's Radau or DOP853 at
tight tolerances. Nothing in src/cells is imported. The channel, junction-gate and
constant-field laws are transcribed from the laws resolved_pump_tissue@3 declares
(processes/sodium_channels.py, potassium_channels.py, junction_gate.py,
coupling/selective.py). The pump is mg0b_theory's transcription of
kinetic_pump.LAW_ID, already judged against the engine. The water law is written
from docs/WATER_VOLUME_REFERENCE.md and docs/PUMP_WATER_MODEL.md:

    Pi = R T (sum N + I) / V,  P = K (V/Vref - 1) + P0,  psi = P - Pi
    Q = 1e15 A Lp a (psi_cell - psi_outside)   [pL/s, cell to outside]

Scope (refused otherwise): every membrane faces a held bath or the declared
gauge node, so each cell's potential is its charge over its capacitance and the
outside potential is 0. Channels: NaV1.2 (m^3 h), Kir2.1 (m h^2), K and Na
leaks. Junctions: constant field with the voltage-relaxation gate. Controls are
piecewise constant; integration restarts at every change.

State: amount increments of cells and finite outside nodes (fmol), volume
increments (pL), channel gates and junction gates. Concentrations are amount
over current volume everywhere.
"""

import math
from dataclasses import dataclass
from types import SimpleNamespace

import numpy as np
from scipy import integrate, optimize

from validation.morphogenesis import mg0b_theory as theory

F, R = theory.F, theory.R
MOL_PER_FMOL = 1e-15
GATED = {"nav1p2_m3h_regularized@1": "nav", "kir2p1_mh2@1": "kir"}
LEAKS = {"kleak_always_open@1", "naleak_always_open@1"}


def bernoulli(x):
    return theory.bernoulli(x)


def logistic(x):
    e = np.exp(-np.abs(x))
    return np.where(x >= 0, 1 / (1 + e), e / (1 + e))


def nav_kinetics(v):
    """NaV1.2 (m, h) targets and time constants (s); processes/sodium_channels.py."""
    shifted = (v + 0.025) / 0.009
    a = 0.182 * 9 * bernoulli(-shifted)
    b = 0.124 * 9 * bernoulli(shifted)
    recovery = 0.024 * 5 * bernoulli(-(v + 0.040) / 0.005)
    inactivation = 0.0091 * 5 * bernoulli((v + 0.065000123) / 0.005)
    target = np.array([a / (a + b), 1 / (1 + np.exp((v + 0.055) / 0.0062))])
    tau = np.array([0.001 / (a + b), 0.001 / (recovery + inactivation)])
    return target, tau


def kir_kinetics(v):
    """Kir2.1 (m, h) targets and time constants (s); processes/potassium_channels.py."""
    target = np.array([logistic(-(v + 0.09648) / 0.02326), logistic((v + 0.16828) / 0.04413)])
    tau = np.array(
        [
            0.0037 - 0.00337 * logistic(-(v + 0.0329) / 0.02793),
            0.00085 + 0.3063 * logistic((v + 0.11829) / 0.02723),
        ]
    )
    return target, tau


def junction_rates(vj, threshold, minimum):
    """alpha, beta (1/s) of junction_voltage_relaxation@1 (processes/junction_gate.py)."""
    shift = np.abs(vj) - threshold
    alpha = 1.3 * np.exp(-77.0 * shift)
    beta = 20.0 / (1.0 + np.exp(-(math.log(0.065) + 140.0 * shift)))
    return alpha, beta


def ghk_outward(c_from, c_to, dv, z, temperature, area_permeability):
    """Constant-field flux from `from` to `to` (fmol/s), coupling/selective.py's form."""
    x = z * F * dv / (R * temperature)
    return area_permeability / MOL_PER_FMOL * (c_from * bernoulli(-x) - c_to * bernoulli(x))


def schedule_value(schedule, t):
    value = schedule[0]["availability"]
    for change in schedule:
        if change["time"] <= t:
            value = change["availability"]
    return value


def kcc_cycles(k_in, m_in, k_out, m_out, volume, kcc):
    """Outward cycles (fmol/s): k a exp[(V - V_set)/(s V_set)] (K_i M_i - K_o M_o)."""
    factor = np.exp((volume - kcc["set_volume_pL"]) / (kcc["steepness"] * kcc["set_volume_pL"]))
    return kcc["capacity_fmol_s_mM2"] * kcc["availability"] * factor * (k_in * m_in - k_out * m_out)


@dataclass
class World:
    raw: dict
    species: list
    z: np.ndarray
    temperature: float
    cells: list
    outside: list
    membranes: list
    channels: list
    junctions: list
    water: dict
    times: list  # every control change time


def load(raw):
    m, e = raw["model"], raw["experiment"]
    if m["id"] != "resolved_pump_water@1":
        raise ValueError("The reference reads resolved_pump_water@1 definitions")
    species = [s["id"] for s in m["species"]]
    gauge = m["closure"]["gauge_reference"]
    outside = m["extracellular"]
    held = {o["id"] for o in outside if o.get("reservoir", False) or o["id"] == gauge}
    for p in m["membranes"]:
        if p["outside"] not in held:
            raise ValueError("The reference needs every membrane to face a held bath or the gauge")
        if p.get("calcium_pump") is not None:
            raise ValueError("The reference has no calcium pump")
    for c in m["channels"]:
        if c["kinetic_law"] not in GATED and c["kinetic_law"] not in LEAKS:
            raise ValueError("Unsupported channel law " + c["kinetic_law"])
    times = sorted(
        {
            0.0,
            *(
                c["time"]
                for key in (
                    "membrane_controls",
                    "junction_controls",
                    "pump_controls",
                    "channel_controls",
                    "water_controls",
                )
                for g in e.get(key, [])
                for c in g["schedule"]
            ),
        }
    )
    return World(
        raw,
        species,
        np.array([s["valence"] for s in m["species"]], dtype=float),
        float(m["temperature_K"]),
        m["cells"],
        outside,
        m["membranes"],
        m["channels"],
        m["junctions"],
        m["water"],
        times,
    )


class Reference:
    """The ODE system of one world: pack/unpack, right-hand side, integration."""

    def __init__(self, raw, kcc=None):
        """kcc: optional KCC-type route on every membrane, a dict with
        capacity_fmol_s_mM2, set_volume_pL, steepness and availability (W2;
        k_anion_symport_mass_action@1 transcribed from its docstring)."""
        self.kcc = kcc
        w = self.w = load(raw)
        self.s = len(w.species)
        self.z = w.z
        self.n = len(w.cells)
        cid = {c["id"]: i for i, c in enumerate(w.cells)}
        oid = {c["id"]: i for i, c in enumerate(w.outside)}
        self.finite = [
            i for i, o in enumerate(w.outside) if not o.get("reservoir", False)
        ]  # Finite outside nodes (the gauge included).
        self.of = len(self.finite)
        self.amount0 = np.array(
            [[c["initial_amount_fmol"][s] for s in w.species] for c in w.cells]
        ).T
        self.volume0 = np.array([c["volume_pL"] for c in w.cells])
        self.charge0 = np.array([c["initial_charge_C"] for c in w.cells])
        self.out_amount0 = np.array(
            [[o["initial_amount_fmol"][s] for s in w.species] for o in w.outside]
        ).T
        self.out_volume0 = np.array([o["volume_pL"] for o in w.outside])
        self.mem_cell = np.array([cid[p["inside"]] for p in w.membranes])
        self.mem_out = np.array([oid[p["outside"]] for p in w.membranes])
        self.area = np.array([p["area_m2"] for p in w.membranes])
        self.cap = np.array([p["capacitance_F"] for p in w.membranes])
        self.perm = np.array(
            [[p["permeability_m_per_s"][s] for s in w.species] for p in w.membranes]
        ).T
        self.cell_cap = np.bincount(self.mem_cell, weights=self.cap, minlength=self.n)
        mids = {p["id"]: i for i, p in enumerate(w.membranes)}
        self.ch_mem = np.array([mids[c["membrane_id"]] for c in w.channels], dtype=int)
        self.ch_kind = [GATED.get(c["kinetic_law"], "leak") for c in w.channels]
        self.ch_species = np.array(
            [w.species.index(c["permeant_ions"][0]["species_id"]) for c in w.channels], dtype=int
        )
        self.ch_perm = np.array(
            [c["max_permeability_m_per_s"] * c["abundance"] for c in w.channels]
        )
        self.gated = [i for i, k in enumerate(self.ch_kind) if k != "leak"]
        self.gate0 = np.array([g for i in self.gated for g in w.channels[i]["initial_gate"]])
        self.j_send = np.array([cid[j["sender"]] for j in w.junctions], dtype=int)
        self.j_recv = np.array([cid[j["receiver"]] for j in w.junctions], dtype=int)
        self.j_ap = np.array(
            [[j["area_m2"] * j["permeability_m_per_s"][s] for s in w.species] for j in w.junctions]
        ).T.reshape(self.s, len(w.junctions))
        self.j_thr = np.array([j["gate"]["threshold_voltage_V"] for j in w.junctions])
        self.j_min = np.array([j["gate"]["minimum_open_fraction"] for j in w.junctions])
        self.j_gate0 = np.array([j["gate"]["initial_gate"] for j in w.junctions])
        # Water: node parameters for cells and finite outside nodes, baths' potentials.
        rows = {c["compartment_id"]: c for c in w.water["compartments"]}
        nodes = [c["id"] for c in w.cells] + [w.outside[i]["id"] for i in self.finite]
        self.vref = np.array([rows[k]["reference_volume_pL"] for k in nodes])
        self.vmin = np.array([rows[k]["minimum_volume_pL"] for k in nodes])
        self.vmax = np.array([rows[k]["maximum_volume_pL"] for k in nodes])
        self.impermeant = np.array([rows[k]["impermeant_amount_fmol"] for k in nodes])
        self.modulus = np.array([rows[k]["bulk_modulus_Pa"] for k in nodes])
        self.offset = np.array([rows[k]["pressure_offset_Pa"] for k in nodes])
        baths = {b["compartment_id"]: b["hydrostatic_pressure_Pa"] for b in w.water["baths"]}
        lp = {
            r["membrane_id"]: r["hydraulic_permeability_m_per_Pa_s"] for r in w.water["membranes"]
        }
        self.conductance = np.array([1e15 * p["area_m2"] * lp[p["id"]] for p in w.membranes])
        rt = R * w.temperature
        self.bath_psi = np.zeros(len(w.outside))
        for i, o in enumerate(w.outside):
            if o["id"] in baths:
                self.bath_psi[i] = (
                    baths[o["id"]] - rt * np.sum(self.out_amount0[:, i]) / o["volume_pL"]
                )
        self.pump = [p.get("pump") for p in w.membranes]
        self.sizes = (
            self.s * self.n,
            self.s * self.of,
            self.n,
            self.of,
            len(self.gate0),
            len(w.junctions),
        )

    # ------------------------------------------------------------ state

    def initial(self):
        return np.concatenate(
            (np.zeros(self.sizes[0] + self.sizes[1] + self.n + self.of), self.gate0, self.j_gate0)
        )

    def unpack(self, y):
        parts, start = [], 0
        for size in self.sizes:
            parts.append(y[start : start + size])
            start += size
        dn, dno, dv, dvo, gates, jg = parts
        return (
            dn.reshape(self.s, self.n),
            dno.reshape(self.s, self.of),
            dv,
            dvo,
            gates.reshape(-1, 2) if len(gates) else gates.reshape(0, 2),
            jg,
        )

    def controls(self, t):
        e = self.w.raw["experiment"]

        def by(key, idkey, ids):
            groups = {g[idkey]: g["schedule"] for g in e.get(key, [])}
            return np.array([schedule_value(groups[i], t) for i in ids]) if ids else np.zeros(0)

        mids = [p["id"] for p in self.w.membranes]
        return SimpleNamespace(
            membrane=by("membrane_controls", "membrane_id", mids),
            junction=by("junction_controls", "junction_id", [j["id"] for j in self.w.junctions]),
            pump=by(
                "pump_controls",
                "pump_id",
                [p["pump"]["id"] for p in self.w.membranes if p.get("pump")],
            ),
            channel=by("channel_controls", "channel_id", [c["id"] for c in self.w.channels]),
            water=by("water_controls", "membrane_id", mids),
        )

    def physical(self, y):
        dn, dno, dv, dvo, gates, jg = self.unpack(y)
        amount = self.amount0 + dn
        volume = self.volume0 + dv
        out_amount = self.out_amount0.copy()
        out_volume = self.out_volume0.copy()
        out_amount[:, self.finite] += dno
        out_volume[self.finite] += dvo
        charge = self.charge0 + F * MOL_PER_FMOL * np.sum(self.z[:, None] * dn, axis=0)
        vm = charge / self.cell_cap
        return amount, volume, out_amount, out_volume, vm, gates, jg

    # ------------------------------------------------------------ laws

    def rhs(self, t, y, control=None):
        c = self.controls(t) if control is None else control
        amount, volume, out_amount, out_volume, vm, gates, jg = self.physical(y)
        temperature, z = self.w.temperature, self.z
        ci, co = amount / volume, out_amount / out_volume
        cell_rate = np.zeros_like(amount)
        out_rate = np.zeros_like(out_amount)
        v_mem = vm[self.mem_cell]
        # Passive membrane routes (outward positive).
        flux = (
            ghk_outward(
                ci[:, self.mem_cell],
                co[:, self.mem_out],
                v_mem,
                z[:, None],
                temperature,
                self.area * self.perm,
            )
            * c.membrane
        )
        # Channels.
        gate_rate = np.zeros_like(gates)
        k = 0
        for i, kind in enumerate(self.ch_kind):
            mem, sp = self.ch_mem[i], self.ch_species[i]
            if kind == "leak":
                opening = 1.0
            else:
                g = gates[k]
                target, tau = (nav_kinetics if kind == "nav" else kir_kinetics)(v_mem[mem])
                gate_rate[k] = (target - g) / tau
                opening = g[0] ** 3 * g[1] if kind == "nav" else g[0] * g[1] ** 2
                k += 1
            flux[sp, mem] += (
                ghk_outward(
                    ci[sp, self.mem_cell[mem]],
                    co[sp, self.mem_out[mem]],
                    v_mem[mem],
                    z[sp],
                    temperature,
                    self.area[mem] * self.ch_perm[i],
                )
                * opening
                * c.channel[i]
            )
        # Na/K pumps (mg0b_theory's transcription of the declared law).
        q = 0
        for mem, pump in enumerate(self.pump):
            if pump is None:
                continue
            na, kk = (
                self.w.species.index(pump["roles"]["sodium"]),
                self.w.species.index(pump["roles"]["potassium"]),
            )
            m = pump["metabolism"]
            p = SimpleNamespace(
                temperature_K=temperature,
                pump=dict(
                    km_na_mM=pump["km_na_mM"],
                    km_k_mM=pump["km_k_mM"],
                    km_atp_mM=pump["km_atp_mM"],
                    atp_mM=m["atp_mM"],
                    adp_mM=m["adp_mM"],
                    pi_mM=m["pi_mM"],
                    delta_g0_J_per_mol=m["delta_g0_J_per_mol"],
                ),
                bath_mM=dict(Na=co[na, self.mem_out[mem]], K=co[kk, self.mem_out[mem]]),
                pump_capacity_mol_s=pump["capacity_fmol_per_s"] * c.pump[q],
            )
            cycles = float(
                theory.pump_cycles_mol_s(
                    p, dict(Na=ci[na, self.mem_cell[mem]], K=ci[kk, self.mem_cell[mem]]), v_mem[mem]
                )
            )
            flux[na, mem] += 3 * cycles
            flux[kk, mem] -= 2 * cycles
            q += 1
        if self.kcc is not None:  # KCC-type route: outward K and M, 1:1.
            k_idx, m_idx = self.w.species.index("K"), self.w.species.index("M")
            cycles = kcc_cycles(
                ci[k_idx, self.mem_cell],
                ci[m_idx, self.mem_cell],
                co[k_idx, self.mem_out],
                co[m_idx, self.mem_out],
                volume[self.mem_cell],
                self.kcc,
            )
            flux[k_idx] += cycles
            flux[m_idx] += cycles
        np.subtract.at(cell_rate, (slice(None), self.mem_cell), flux)
        np.add.at(out_rate, (slice(None), self.mem_out), flux)
        # Junctions and their gates.
        jrate = np.zeros_like(jg)
        if len(jg):
            vj = vm[self.j_send] - vm[self.j_recv]
            jflux = ghk_outward(
                ci[:, self.j_send], ci[:, self.j_recv], vj, z[:, None], temperature, self.j_ap
            ) * (jg * c.junction)
            np.subtract.at(cell_rate, (slice(None), self.j_send), jflux)
            np.add.at(cell_rate, (slice(None), self.j_recv), jflux)
            alpha, beta = junction_rates(vj, self.j_thr, self.j_min)
            jrate = alpha * (1 - jg) - beta * (jg - self.j_min)
        # Water at current amounts and volumes.
        rt = R * temperature
        nodes_amount = np.concatenate((amount, out_amount[:, self.finite]), axis=1)
        nodes_volume = np.concatenate((volume, out_volume[self.finite]))
        psi_nodes = (
            self.modulus * (nodes_volume / self.vref - 1)
            + self.offset
            - rt * (np.sum(nodes_amount, axis=0) + self.impermeant) / nodes_volume
        )
        psi_out = self.bath_psi.copy()
        psi_out[self.finite] = psi_nodes[self.n :]
        qflow = self.conductance * c.water * (psi_nodes[self.mem_cell] - psi_out[self.mem_out])
        dv = -np.bincount(self.mem_cell, weights=qflow, minlength=self.n)
        dvo_all = np.bincount(self.mem_out, weights=qflow, minlength=len(self.w.outside))
        return np.concatenate(
            (
                cell_rate.ravel(),
                out_rate[:, self.finite].ravel(),
                dv,
                dvo_all[self.finite],
                gate_rate.ravel(),
                jrate,
            )
        )

    def integrate(self, end, t_eval, *, method="Radau", rtol=1e-11, atol=None, y0=None):
        """Piecewise-constant controls: one solve per interval between control changes."""
        y = self.initial() if y0 is None else np.asarray(y0, dtype=float)
        atol = 1e-15 if atol is None else atol
        points = [t for t in self.w.times if 0 < t < end] + [end]
        start, out = 0.0, {}
        t_eval = sorted(set(float(t) for t in t_eval))
        if 0.0 in t_eval:
            out[0.0] = y.copy()
        for stop in points:
            control = self.controls(start)
            inside = [t for t in t_eval if start < t <= stop]
            solution = integrate.solve_ivp(
                lambda t, v, control=control: self.rhs(t, v, control),
                (start, stop),
                y,
                method=method,
                t_eval=inside or None,
                rtol=rtol,
                atol=atol,
                dense_output=False,
            )
            if not solution.success:
                raise RuntimeError(solution.message)
            for t, column in zip(solution.t, solution.y.T, strict=True):
                out[float(t)] = column.copy()
            y = solution.y[:, -1].copy()
            start = stop
        return {t: out[t] for t in t_eval}

    def observe(self, y):
        amount, volume, out_amount, out_volume, vm, gates, jg = self.physical(y)
        return dict(
            cell_volume_pL=volume.tolist(),
            membrane_voltage_V=vm[self.mem_cell].tolist(),
            cell_concentration_mM=(amount / volume).T.tolist(),
            cell_osmolarity_mM=(
                (np.sum(amount, axis=0) + self.impermeant[: self.n]) / volume
            ).tolist(),
            extracellular_volume_pL=out_volume[self.finite].tolist(),
        )


# ------------------------------------------------------------ stationary states


def cell_stationary_states(raw, *, grid=None):
    """Stationary states of one heredity cell facing a held bath, with water.

    For a given Vm the Na and K balances (pump, leaks, channels at their voltage
    steady state) fix the Na and K concentrations; M is at its Nernst
    distribution (passive routes only); the volume follows from osmotic balance
    sum(c) + (N_fixed + I)/V = c_bath + P(V)/RT; the residual is the charge,
    C Vm - F (sum z N + X). Roots in Vm on the grid are refined by brentq.
    Returns [(Vm, {Na, K, M}, V, osmolarity)] sorted by Vm.
    """
    w = Reference(raw)
    if w.n != 1 or len(w.w.membranes) != 1 or w.of:
        raise ValueError("One cell, one membrane, a held bath")
    cell = w.w.cells[0]
    species = w.w.species
    idx = {s: species.index(s) for s in species}
    rt = R * w.w.temperature
    bath = w.out_amount0[:, 0] / w.out_volume0[0]
    c_bath = float(np.sum(bath))
    fixed = {s: w.amount0[idx[s], 0] for s in species if s not in ("Na", "K", "M")}
    control = w.controls(0.0)

    def openings(v):
        out = []
        for kind in w.ch_kind:
            if kind == "leak":
                out.append(1.0)
            elif kind == "nav":
                target, _ = nav_kinetics(v)
                out.append(target[0] ** 3 * target[1])
            else:
                target, _ = kir_kinetics(v)
                out.append(target[0] * target[1] ** 2)
        return out

    def inward(v, conc):
        """Inward fluxes (fmol/s) of Na and K at v with steady gates."""
        opening = openings(v)
        out = {}
        for s in ("Na", "K"):
            k = idx[s]
            perm = w.perm[k, 0] * control.membrane[0]
            for i, o in enumerate(opening):
                if w.ch_species[i] == k:
                    perm += w.ch_perm[i] * o * control.channel[i]
            out[s] = -float(
                ghk_outward(conc[s], bath[k], v, w.z[k], w.w.temperature, w.area[0] * perm)
            )
        pump = w.pump[0]
        if pump is not None:
            m = pump["metabolism"]
            q = SimpleNamespace(
                temperature_K=w.w.temperature,
                pump=dict(
                    km_na_mM=pump["km_na_mM"],
                    km_k_mM=pump["km_k_mM"],
                    km_atp_mM=pump["km_atp_mM"],
                    atp_mM=m["atp_mM"],
                    adp_mM=m["adp_mM"],
                    pi_mM=m["pi_mM"],
                    delta_g0_J_per_mol=m["delta_g0_J_per_mol"],
                ),
                bath_mM=dict(Na=bath[idx["Na"]], K=bath[idx["K"]]),
                pump_capacity_mol_s=pump["capacity_fmol_per_s"] * control.pump[0],
            )
            cycles = float(theory.pump_cycles_mol_s(q, dict(Na=conc["Na"], K=conc["K"]), v))
            out["Na"] -= 3 * cycles
            out["K"] += 2 * cycles
        return out

    def composition(v):
        conc = dict(Na=12.0, K=140.0, M=bath[idx["M"]] * math.exp(F * v / rt))
        for _ in range(80):
            na = optimize.brentq(
                lambda x, c=conc: inward(v, dict(c, Na=x))["Na"], 1e-6, 5e3, xtol=1e-14, rtol=1e-15
            )
            kk = optimize.brentq(
                lambda x, na=na, c=conc: inward(v, dict(c, Na=na, K=x))["K"],
                1e-6,
                5e4,
                xtol=1e-14,
                rtol=1e-15,
            )
            done = abs(na - conc["Na"]) <= 1e-14 * na and abs(kk - conc["K"]) <= 1e-14 * kk
            conc = dict(conc, Na=na, K=kk)
            if done:
                break
        return conc

    def volume_of(conc):
        mobile = conc["Na"] + conc["K"] + conc["M"]
        particles = sum(fixed.values()) + w.impermeant[0]

        def residual(volume):
            pressure = w.modulus[0] * (volume / w.vref[0] - 1) + w.offset[0]
            return mobile + particles / volume - c_bath - pressure / rt

        low, high = 1e-3 * w.volume0[0], 1e3 * w.volume0[0]
        if residual(high) > 0:
            return math.nan  # Mobile ions alone exceed the bath: no finite volume.
        return optimize.brentq(residual, low, high, xtol=1e-17, rtol=1e-15)

    def charge_residual(v):
        conc = composition(v)
        volume = volume_of(conc)
        if not math.isfinite(volume):
            return math.nan
        ionic = sum(w.z[idx[s]] * conc[s] * volume for s in ("Na", "K", "M"))
        ionic += sum(w.z[idx[s]] * n for s, n in fixed.items())
        return w.cell_cap[0] * v - F * MOL_PER_FMOL * (ionic + cell["fixed_charge_equivalent_fmol"])

    grid = np.linspace(-0.110, 0.0, 221) if grid is None else grid
    values = np.array([charge_residual(v) for v in grid])
    states = []
    finite = np.isfinite(values)
    for i in np.flatnonzero(
        finite[:-1] & finite[1:] & (np.sign(values[:-1]) * np.sign(values[1:]) < 0)
    ):
        v = optimize.brentq(charge_residual, grid[i], grid[i + 1], xtol=1e-16, rtol=1e-15)
        conc = composition(v)
        volume = volume_of(conc)
        particles = sum(fixed.values()) + w.impermeant[0]
        osmolarity = conc["Na"] + conc["K"] + conc["M"] + particles / volume
        states.append((v, conc, volume, osmolarity))
    return states


def regulated_stationary_states(raw, kcc, *, grid=None):
    """Stationary states of one held-bath heredity cell with water and a KCC-type route.

    With the route, M is no longer at its Nernst distribution, so for each Vm the
    four balances (Na, K and M fluxes, and osmotic balance) are solved together
    for (Na, K, M, V); the residual is again the charge C Vm - F (sum z N + X).
    kcc=None reproduces cell_stationary_states. Returns
    [(Vm, {Na, K, M}, V, osmolarity, kcc_cycles_fmol_s)] sorted by Vm.
    """
    w = Reference(raw, kcc)
    if w.n != 1 or len(w.w.membranes) != 1 or w.of:
        raise ValueError("One cell, one membrane, a held bath")
    cell = w.w.cells[0]
    species = w.w.species
    idx = {s: species.index(s) for s in species}
    rt = R * w.w.temperature
    bath = w.out_amount0[:, 0] / w.out_volume0[0]
    c_bath = float(np.sum(bath))
    fixed = {s: w.amount0[idx[s], 0] for s in species if s not in ("Na", "K", "M")}
    particles = sum(fixed.values()) + w.impermeant[0]
    control = w.controls(0.0)

    def opening(i, v):
        kind = w.ch_kind[i]
        if kind == "leak":
            return 1.0
        target, _ = (nav_kinetics if kind == "nav" else kir_kinetics)(v)
        return target[0] ** 3 * target[1] if kind == "nav" else target[0] * target[1] ** 2

    def inward(v, conc, volume):
        out = {}
        for s in ("Na", "K", "M"):
            k = idx[s]
            perm = w.perm[k, 0] * control.membrane[0]
            for i in range(len(w.ch_kind)):
                if w.ch_species[i] == k:
                    perm += w.ch_perm[i] * opening(i, v) * control.channel[i]
            out[s] = -float(
                ghk_outward(conc[s], bath[k], v, w.z[k], w.w.temperature, w.area[0] * perm)
            )
        pump = w.pump[0]
        if pump is not None:
            m = pump["metabolism"]
            q = SimpleNamespace(
                temperature_K=w.w.temperature,
                pump=dict(
                    km_na_mM=pump["km_na_mM"],
                    km_k_mM=pump["km_k_mM"],
                    km_atp_mM=pump["km_atp_mM"],
                    atp_mM=m["atp_mM"],
                    adp_mM=m["adp_mM"],
                    pi_mM=m["pi_mM"],
                    delta_g0_J_per_mol=m["delta_g0_J_per_mol"],
                ),
                bath_mM=dict(Na=bath[idx["Na"]], K=bath[idx["K"]]),
                pump_capacity_mol_s=pump["capacity_fmol_per_s"] * control.pump[0],
            )
            cycles = float(theory.pump_cycles_mol_s(q, dict(Na=conc["Na"], K=conc["K"]), v))
            out["Na"] -= 3 * cycles
            out["K"] += 2 * cycles
        regulated = 0.0
        if kcc is not None:
            regulated = float(
                kcc_cycles(conc["K"], conc["M"], bath[idx["K"]], bath[idx["M"]], volume, kcc)
            )
            out["K"] -= regulated
            out["M"] -= regulated
        return out, regulated

    def pressure(volume):
        return w.modulus[0] * (volume / w.vref[0] - 1) + w.offset[0]

    def equations(x, v):
        na, k, m, volume = np.exp(x)
        conc = dict(Na=na, K=k, M=m)
        flux, _ = inward(v, conc, volume)
        return np.array(
            [
                1e3 * flux["Na"],
                1e3 * flux["K"],
                1e3 * flux["M"],
                (na + k + m + particles / volume - c_bath - pressure(volume) / rt) / c_bath,
            ]
        )

    cache = {}

    def nested(v):
        """Robust fallback: Gauss-Seidel brentq on Na, K, M at each V, brentq on V."""

        def composition(volume, start):
            conc = dict(start)
            for _ in range(200):
                old = dict(conc)
                for s, high in (("Na", 5e3), ("K", 5e4), ("M", 5e4)):
                    conc[s] = optimize.brentq(
                        lambda x, s=s: inward(v, dict(conc, **{s: x}), volume)[0][s],
                        1e-9,
                        high,
                        xtol=1e-15,
                        rtol=1e-15,
                    )
                if all(abs(conc[s] - old[s]) <= 1e-14 * conc[s] for s in conc):
                    break
            return conc

        start = dict(Na=10.0, K=140.0, M=bath[idx["M"]] * math.exp(F * v / rt))

        def residual(volume):
            c = composition(volume, start)
            return c["Na"] + c["K"] + c["M"] + particles / volume - c_bath - pressure(volume) / rt

        # The validity range of the water law (0.5-2 V0) with a margin; beyond it
        # the exponential volume factor overflows for steep routes.
        low, high = 0.3 * w.volume0[0], 3.0 * w.volume0[0]
        if not residual(low) > 0 > residual(high):
            return None
        volume = optimize.brentq(residual, low, high, xtol=1e-17, rtol=1e-15)
        c = composition(volume, start)
        x = np.log([c["Na"], c["K"], c["M"], volume])
        return x, float(np.max(np.abs(equations(x, v))))

    def solve(v):
        if v in cache:
            return cache[v]
        m0 = bath[idx["M"]] * math.exp(F * v / rt)
        guesses = [np.log([10.0, 140.0, m0, w.volume0[0]])]
        if cache:
            nearest = min(
                (t for t in cache if cache[t] is not None), key=lambda t: abs(t - v), default=None
            )
            if nearest is not None:
                guesses.insert(0, cache[nearest][0])
        result = None
        for guess in guesses:
            sol = optimize.root(equations, guess, args=(v,), method="hybr", tol=1e-14)
            if sol.success and np.max(np.abs(equations(sol.x, v))) < 1e-9:
                result = (sol.x, float(np.max(np.abs(equations(sol.x, v)))))
                break
        if result is None:
            result = nested(v)
        cache[v] = result
        return result

    def charge_residual(v):
        solved = solve(v)
        if solved is None:
            return math.nan
        na, k, m, volume = np.exp(solved[0])
        ionic = (w.z[idx["Na"]] * na + w.z[idx["K"]] * k + w.z[idx["M"]] * m) * volume
        ionic += sum(w.z[idx[s]] * n for s, n in fixed.items())
        return w.cell_cap[0] * v - F * MOL_PER_FMOL * (ionic + cell["fixed_charge_equivalent_fmol"])

    grid = np.linspace(-0.110, 0.0, 221) if grid is None else grid
    values = np.array([charge_residual(v) for v in grid])
    finite = np.isfinite(values)
    states = []
    for i in np.flatnonzero(
        finite[:-1] & finite[1:] & (np.sign(values[:-1]) * np.sign(values[1:]) < 0)
    ):
        v = optimize.brentq(charge_residual, grid[i], grid[i + 1], xtol=1e-16, rtol=1e-15)
        na, k, m, volume = np.exp(solve(v)[0])
        conc = dict(Na=float(na), K=float(k), M=float(m))
        _, regulated = inward(v, conc, volume)
        osmolarity = na + k + m + particles / volume
        states.append((v, conc, float(volume), float(osmolarity), regulated))
    return states


def stationary_spectrum(raw, kcc, state, *, step=1e-7):
    """Leading eigenvalues (1/s) of the reference Jacobian at a stationary state.

    The state is (Vm, {Na, K, M}, V, ...) from a stationary solver; gates sit at
    their steady state. Central differences of Reference.rhs in relative steps,
    on every coordinate except the closed impermeant amounts (zero rows).
    """
    r = Reference(raw, kcc)
    vm, conc, volume = state[0], state[1], state[2]
    y = r.initial()
    dn, _, dv, _, gates, _ = r.unpack(y)
    for s, c in conc.items():
        k = r.w.species.index(s)
        dn[k, 0] = c * volume - r.amount0[k, 0]
    dv[0] = volume - r.volume0[0]
    k = 0
    for kind in r.ch_kind:
        if kind != "leak":
            gates[k] = (nav_kinetics if kind == "nav" else kir_kinetics)(vm)[0]
            k += 1
    closed = [r.w.species.index(s) for s in r.w.species if s not in conc]
    free = [i for i in range(len(y)) if not (i < r.s * r.n and i // r.n in closed)]
    base = r.rhs(0.0, y)
    scale = np.abs(np.concatenate((r.amount0.ravel(), np.zeros(len(y) - r.s * r.n))))
    jac = np.zeros((len(free), len(free)))
    for col, i in enumerate(free):
        h = step * max(1.0, abs(y[i]) + scale[i])
        plus, minus = y.copy(), y.copy()
        plus[i] += h
        minus[i] -= h
        jac[:, col] = (r.rhs(0.0, plus)[free] - r.rhs(0.0, minus)[free]) / (2 * h)
    values = np.linalg.eigvals(jac)
    order = np.argsort(-values.real)
    return dict(
        leading_growth_rate_per_s=float(values.real[order[0]]),
        eigenvalues_per_s=[[float(v.real), float(v.imag)] for v in values[order][:6]],
        residual_inf=float(np.max(np.abs(base[free]))),
    )


def continued_stationary_states(raw, kcc, *, steps=40):
    """Stationary states with a KCC-type route by continuation in its capacity.

    Starts from the route-free states (cell_stationary_states) and raises the
    capacity from 0 to kcc's in `steps` equal increments, solving the five
    stationary equations (Na, K and M balances, osmotic balance, charge) with
    scipy's hybr from the previous point. A branch that stops converging is
    reported as lost at that capacity (for example at a fold).
    Returns [dict(branch, converged, state or lost_at_fraction)].
    """
    w = Reference(raw, kcc)
    if w.n != 1 or len(w.w.membranes) != 1 or w.of:
        raise ValueError("One cell, one membrane, a held bath")
    cell = w.w.cells[0]
    species = w.w.species
    idx = {s: species.index(s) for s in species}
    rt = R * w.w.temperature
    bath = w.out_amount0[:, 0] / w.out_volume0[0]
    c_bath = float(np.sum(bath))
    fixed = {s: w.amount0[idx[s], 0] for s in species if s not in ("Na", "K", "M")}
    particles = sum(fixed.values()) + w.impermeant[0]
    charged = sum(w.z[idx[s]] * n for s, n in fixed.items()) + cell["fixed_charge_equivalent_fmol"]
    control = w.controls(0.0)

    def opening(i, v):
        kind = w.ch_kind[i]
        if kind == "leak":
            return 1.0
        target, _ = (nav_kinetics if kind == "nav" else kir_kinetics)(v)
        return target[0] ** 3 * target[1] if kind == "nav" else target[0] * target[1] ** 2

    def inward(v, conc, volume, route):
        out = {}
        for s in ("Na", "K", "M"):
            k = idx[s]
            perm = w.perm[k, 0] * control.membrane[0]
            for i in range(len(w.ch_kind)):
                if w.ch_species[i] == k:
                    perm += w.ch_perm[i] * opening(i, v) * control.channel[i]
            out[s] = -float(
                ghk_outward(conc[s], bath[k], v, w.z[k], w.w.temperature, w.area[0] * perm)
            )
        pump = w.pump[0]
        if pump is not None:
            m = pump["metabolism"]
            q = SimpleNamespace(
                temperature_K=w.w.temperature,
                pump=dict(
                    km_na_mM=pump["km_na_mM"],
                    km_k_mM=pump["km_k_mM"],
                    km_atp_mM=pump["km_atp_mM"],
                    atp_mM=m["atp_mM"],
                    adp_mM=m["adp_mM"],
                    pi_mM=m["pi_mM"],
                    delta_g0_J_per_mol=m["delta_g0_J_per_mol"],
                ),
                bath_mM=dict(Na=bath[idx["Na"]], K=bath[idx["K"]]),
                pump_capacity_mol_s=pump["capacity_fmol_per_s"] * control.pump[0],
            )
            cycles = float(theory.pump_cycles_mol_s(q, dict(Na=conc["Na"], K=conc["K"]), v))
            out["Na"] -= 3 * cycles
            out["K"] += 2 * cycles
        regulated = float(
            kcc_cycles(conc["K"], conc["M"], bath[idx["K"]], bath[idx["M"]], volume, route)
        )
        out["K"] -= regulated
        out["M"] -= regulated
        return out, regulated

    def equations(x, route):
        na, k, m, volume = np.exp(x[:4])
        v = x[4]
        conc = dict(Na=na, K=k, M=m)
        flux, _ = inward(v, conc, volume, route)
        pressure = w.modulus[0] * (volume / w.vref[0] - 1) + w.offset[0]
        ionic = (w.z[idx["Na"]] * na + w.z[idx["K"]] * k + w.z[idx["M"]] * m) * volume
        return np.array(
            [
                1e3 * flux["Na"],
                1e3 * flux["K"],
                1e3 * flux["M"],
                (na + k + m + particles / volume - c_bath - pressure / rt) / c_bath,
                (w.cell_cap[0] * v / (F * MOL_PER_FMOL) - ionic - charged) / 100.0,
            ]
        )

    out = []
    for branch, start in enumerate(cell_stationary_states(raw)):
        vm, conc, volume, _ = start
        x = np.array([*np.log([conc["Na"], conc["K"], conc["M"], volume]), vm])
        record = dict(branch=branch, converged=True)
        for t in np.linspace(0.0, 1.0, steps + 1)[1:]:
            route = dict(kcc, capacity_fmol_s_mM2=t * kcc["capacity_fmol_s_mM2"])
            sol = optimize.root(equations, x, args=(route,), method="hybr", tol=1e-15)
            residual = float(np.max(np.abs(equations(sol.x, route))))
            if not sol.success and residual > 1e-10:
                record.update(converged=False, lost_at_fraction=float(t), residual=residual)
                break
            x = sol.x
        if record["converged"]:
            na, k, m, volume = (float(v) for v in np.exp(x[:4]))
            conc = dict(Na=na, K=k, M=m)
            _, regulated = inward(x[4], conc, volume, kcc)
            record.update(
                state=(float(x[4]), conc, volume, na + k + m + particles / volume, regulated),
                residual=float(np.max(np.abs(equations(x, kcc)))),
            )
        out.append(record)
    return out
