"""Independent references for resolved_pump_replacement@1 (protocol G2-Q1); no Cells code.

numpy/scipy only. Nothing in src/cells is imported. Each reference reads a plain
resolved_pump_replacement@1 definition (the JSON dict) and transcribes the declared
operation and laws from their documentation (docs/CELL_REPLACEMENT.md, the
docstrings of cell_replacement_spec and processes/junction_formation):

* R-ops (events): the event operator from first principles, on the reduced
  reference's physical state. The departing amounts are removed and the template's
  (or the donor's, before any event at that time) supplied. Gates come from the
  template or the donor, by channel law. Incident junction gates are set by the
  junction law at Vj = 0 (law_open) or at the post-event Vj (law_steady), and their
  formation restarts. The bookings are removed, supplied, z F (supplied - removed),
  the held baths' image charge (held-bath cells: Vm = q / C_cell, plate charge
  -dq C_m / C_cell), and the free-energy change: the ideal-solution
  RT n (ln(n/V) - 1) and the capacitor q^2 / 2C, absolute forms, minus the electrode
  work.
* R-full (ReplacementReference): validation/tissue/pump_water_reference.Reference
  (@3's laws on held-bath worlds, Radau) with every water route closed (Lp 0),
  restarted at every event. R-ops is applied there, and the formation law
  A = 1 - (1 - A0) exp(-max(0, t - t_e - lag) / tau) multiplies each incident
  junction's availability, with a breakpoint at t_e + lag.
* R-fast (ReducedChain): the reduced bistable chain of
  validation/morphogenesis/mg0b_theory. Composition is fixed per cell (each cell's
  own, swapped at an event) and gates sit at their voltage steady states. Each
  junction conductance is the constant-field slope at the mean of its two cells'
  compositions, times A(t), for ungated junctions. An event resets the slot's
  voltage and composition to the template's (or the donor's).

Scope (refused otherwise): held-bath worlds; templates without route values.
"""

import copy
from types import SimpleNamespace

import numpy as np
from scipy import integrate

from validation.morphogenesis import mg0b_theory as theory
from validation.tissue import pump_water_reference as water

F, R = theory.F, theory.R
MOL_PER_FMOL = 1e-15
GATED = water.GATED


def closed_water(raw):
    """A resolved_pump_water@1 copy of the inner definition with every water route closed."""
    raw = copy.deepcopy(raw)
    m = raw["model"]
    m.pop("replacement", None)
    raw["experiment"].pop("replacement_events", None)
    m["id"] = "resolved_pump_water@1"
    finite = [c for c in m["extracellular"] if not c.get("reservoir", False)]
    m["water"] = dict(
        law="ideal_osmosis_linear_compliance_water@1",
        compartments=[
            dict(
                compartment_id=c["id"],
                reference_volume_pL=c["volume_pL"],
                minimum_volume_pL=0.5 * c["volume_pL"],
                maximum_volume_pL=2.0 * c["volume_pL"],
                impermeant_amount_fmol=0.0,
                bulk_modulus_Pa=0.0,
                pressure_offset_Pa=0.0,
            )
            for c in (*m["cells"], *finite)
        ],
        baths=[
            dict(compartment_id=c["id"], hydrostatic_pressure_Pa=0.0)
            for c in m["extracellular"]
            if c.get("reservoir", False)
        ],
        membranes=[
            dict(membrane_id=p["id"], hydraulic_permeability_m_per_Pa_s=0.0) for p in m["membranes"]
        ],
    )
    raw["experiment"]["water_controls"] = [
        dict(membrane_id=p["id"], schedule=[dict(time=0.0, availability=0.0)])
        for p in m["membranes"]
    ]
    return raw


def junction_target(vj, threshold, minimum):
    alpha, beta = water.junction_rates(vj, threshold, minimum)
    return (alpha + beta * minimum) / (alpha + beta)


def abundance(t, start, formation):
    """The formation law at time t for junctions whose formation started at start (nan: formed)."""
    a0, lag, tau = (
        formation["initial_abundance"],
        formation["lag_s"],
        formation["time_constant_s"],
    )
    out = np.ones_like(start)
    forming = ~np.isnan(start)
    age = t - start[forming]
    out[forming] = 1.0 - (1.0 - a0) * np.exp(-np.maximum(age - lag, 0.0) / tau)
    return out


class ReplacementReference:
    """R-full with R-ops: the reduced reference restarted at each replacement event."""

    def __init__(self, raw):
        rep = raw["model"]["replacement"]
        if any(
            t["route_values"][k]
            for t in rep["templates"]
            for k in (
                "channel_permeability_m_per_s",
                "channel_abundance",
                "membrane_permeability_m_per_s",
            )
        ) or any(
            t["route_values"][k] is not None
            for t in rep["templates"]
            for k in ("pump_capacity_fmol_per_s_m2", "calcium_pump_capacity_fmol_per_s_m2")
        ):
            raise ValueError("The reference covers templates without route values")
        self.raw = raw
        self.ref = water.Reference(closed_water(raw))
        self.formation = rep["junction_formation"]
        self.templates = {t["id"]: t for t in rep["templates"]}
        cells = [c["id"] for c in raw["model"]["cells"]]
        self.cell_index = {c: i for i, c in enumerate(cells)}
        self.events = sorted(
            raw["experiment"]["replacement_events"],
            key=lambda e: (e["time"], self.cell_index[e["slot"]]),
        )
        self.start = np.full(len(self.ref.w.junctions), np.nan)
        r = self.ref
        # Gated channels: (gate row in y, membrane, law) in the reference's order.
        self.gated = []
        row = 0
        for i, kind in enumerate(r.ch_kind):
            if kind != "leak":
                law = r.w.channels[i]["kinetic_law"]
                self.gated.append((row, r.ch_mem[i], law))
                row += 1
        self.bookings = []

    # ------------------------------------------------------------ R-ops

    def apply(self, t, y, events):
        """The state after the events at time t, and their bookings (R-ops)."""
        r = self.ref
        dn, dno, dv, dvo, gates, jg = (np.array(a, copy=True) for a in r.unpack(y))
        amount_before = r.amount0 + dn
        gates_before = gates.copy()
        charge_before = r.charge0 + F * MOL_PER_FMOL * np.sum(r.z[:, None] * dn, axis=0)
        species = r.w.species
        replaced = []
        for e in events:
            i = self.cell_index[e["slot"]]
            replaced.append(i)
            if e["newcomer"] == "donor_copy":
                j = self.cell_index[e["donor"]]
                source = amount_before[:, j]
            else:
                tmpl = self.templates[e["template"]]
                source = np.array([tmpl["amounts_fmol"][s] for s in species])
            dn[:, i] = source - r.amount0[:, i]
            for row, mem, law in self.gated:
                if r.mem_cell[mem] != i:
                    continue
                if e["newcomer"] == "donor_copy":
                    j = self.cell_index[e["donor"]]
                    rows = [rw for rw, m2, l2 in self.gated if r.mem_cell[m2] == j and l2 == law]
                    gates[row] = gates_before[rows[0]]
                else:
                    gates[row] = self.templates[e["template"]]["channel_gates"][law]
            incident = (r.j_send == i) | (r.j_recv == i)
            self.start[incident] = t
        charge_after = r.charge0 + F * MOL_PER_FMOL * np.sum(r.z[:, None] * dn, axis=0)
        incident = np.isin(r.j_send, replaced) | np.isin(r.j_recv, replaced)
        if self.formation["gate_at_arrival"] == "law_open":
            target = junction_target(np.zeros(incident.sum()), r.j_thr[incident], r.j_min[incident])
        else:
            vm = charge_after / r.cell_cap
            vj = (vm[r.j_send] - vm[r.j_recv])[incident]
            target = junction_target(vj, r.j_thr[incident], r.j_min[incident])
        jg[incident] = target
        y_new = np.concatenate((dn.ravel(), dno.ravel(), dv, dvo, gates.ravel(), jg))
        # Bookings.
        volume = r.volume0
        amount_after = r.amount0 + dn

        def chemical(n):
            return 1e-3 * R * r.w.temperature * np.sum(n * (np.log(n / volume) - 1.0), axis=0)

        def capacitor(q):
            return 0.5e12 * q**2 / r.cell_cap

        dq = charge_after - charge_before
        image = np.zeros(len(r.w.outside))
        np.add.at(image, r.mem_out, -dq[r.mem_cell] * r.cap / r.cell_cap[r.mem_cell])
        boundary = np.array([o.get("boundary_potential_V", 0.0) for o in r.w.outside])
        work = 1e12 * np.sum(boundary * image)
        d_chem = chemical(amount_after) - chemical(amount_before)
        d_cap = capacitor(charge_after) - capacitor(charge_before)
        booking = dict(
            time_s=t,
            slots=[int(i) for i in replaced],
            removed_fmol={int(i): amount_before[:, i].tolist() for i in replaced},
            supplied_fmol={int(i): amount_after[:, i].tolist() for i in replaced},
            charge_C={int(i): float(dq[i]) for i in replaced},
            image_charge_C=image.tolist(),
            free_energy_pJ=float(np.sum(d_chem[replaced]) + np.sum(d_cap) - work),
        )
        self.bookings.append(booking)
        return y_new, booking

    # ------------------------------------------------------------ R-full

    def integrate(self, end, t_eval, *, rtol=1e-11, atol=1e-15):
        r = self.ref
        y = r.initial()
        lag = self.formation["lag_s"]
        events_at = {}
        for e in self.events:
            if e["time"] < end:
                events_at.setdefault(e["time"], []).append(e)
        points = sorted(
            {
                *(t for t in r.w.times if 0 < t < end),
                *events_at,
                *(t + lag for t in events_at if 0 < t + lag < end),
                end,
            }
        )
        out, start = {}, 0.0
        t_eval = sorted(set(float(t) for t in t_eval))
        if 0.0 in t_eval:
            out[0.0] = y.copy()
        for stop in points:
            if start in events_at:
                y, _ = self.apply(start, y, events_at[start])
            base = r.controls(start)

            def rhs(t, v, base=base):
                c = SimpleNamespace(**vars(base))
                c.junction = base.junction * abundance(t, self.start, self.formation)
                return r.rhs(t, v, c)

            inside = [t for t in t_eval if start < t <= stop]
            solution = integrate.solve_ivp(
                rhs, (start, stop), y, method="Radau", t_eval=inside or None, rtol=rtol, atol=atol
            )
            if not solution.success:
                raise RuntimeError(solution.message)
            for t, column in zip(solution.t, solution.y.T, strict=True):
                out[float(t)] = column.copy()
            y = solution.y[:, -1].copy()
            start = stop
        return {t: out[t] for t in t_eval}

    def observe(self, y):
        amount, volume, _, _, vm, gates, jg = self.ref.physical(y)
        return dict(
            membrane_voltage_V=vm[self.ref.mem_cell].tolist(),
            cell_amount_fmol=amount.T.tolist(),
            channel_gate=gates.tolist(),
            junction_gate=jg.tolist(),
        )


# ---------------------------------------------------------------- R-fast


def cell_parameters(raw, cell_index=0):
    """mg0b_theory.CellParameters of one heredity cell, read from the definition."""
    m = raw["model"]
    cell = m["cells"][cell_index]
    membrane = next(p for p in m["membranes"] if p["inside"] == cell["id"])
    bath = next(o for o in m["extracellular"] if o["id"] == membrane["outside"])
    chans = {c["kinetic_law"]: c for c in m["channels"] if c["membrane_id"] == membrane["id"]}
    pump = membrane["pump"]
    meta = pump["metabolism"]
    volume = cell["volume_pL"]
    return theory.CellParameters(
        temperature_K=float(m["temperature_K"]),
        area_m2=membrane["area_m2"],
        capacitance_F=membrane["capacitance_F"],
        volume_m3=volume * 1e-15,
        permeability_m_s={k: membrane["permeability_m_per_s"][k] for k in theory.MOBILE},
        bath_mM={k: bath["initial_amount_fmol"][k] / bath["volume_pL"] for k in theory.MOBILE},
        fixed_anion_mM=cell["initial_amount_fmol"]["P"] / volume,
        kir_m_s=chans["kir2p1_mh2@1"]["max_permeability_m_per_s"]
        * chans["kir2p1_mh2@1"]["abundance"],
        nav_m_s=chans["nav1p2_m3h_regularized@1"]["max_permeability_m_per_s"]
        * chans["nav1p2_m3h_regularized@1"]["abundance"],
        nav_availability=1.0,
        control_m_s=0.0,
        pump_capacity_mol_s=pump["capacity_fmol_per_s"] * MOL_PER_FMOL,
        pump=dict(
            km_na_mM=pump["km_na_mM"],
            km_k_mM=pump["km_k_mM"],
            km_atp_mM=pump["km_atp_mM"],
            atp_mM=meta["atp_mM"],
            adp_mM=meta["adp_mM"],
            pi_mM=meta["pi_mM"],
            delta_g0_J_per_mol=meta["delta_g0_J_per_mol"],
        ),
    )


class ReducedChain:
    """R-fast: the reduced chain with per-cell composition, events and the formation law."""

    def __init__(self, raw):
        m = raw["model"]
        self.raw = raw
        self.cells = [c["id"] for c in m["cells"]]
        self.index = {c: i for i, c in enumerate(self.cells)}
        self.p = cell_parameters(raw)
        self.composition = [
            {k: c["initial_amount_fmol"][k] / c["volume_pL"] for k in theory.MOBILE}
            for c in m["cells"]
        ]
        self.v = np.array([c["initial_charge_C"] for c in m["cells"]]) / self.p.capacitance_F
        self.edges = [(self.index[j["sender"]], self.index[j["receiver"]]) for j in m["junctions"]]
        self.junctions = m["junctions"]
        if any(j["gate"]["minimum_open_fraction"] != 1.0 for j in self.junctions):
            raise ValueError("R-fast covers ungated junctions (open fraction held at 1)")
        rep = m["replacement"]
        self.formation = rep["junction_formation"]
        self.templates = {t["id"]: t for t in rep["templates"]}
        self.events = sorted(
            raw["experiment"]["replacement_events"],
            key=lambda e: (e["time"], self.index[e["slot"]]),
        )
        self.start = np.full(len(self.edges), np.nan)

    def conductance(self):
        out = []
        for (a, b), j in zip(self.edges, self.junctions, strict=True):
            mean = {
                k: 0.5 * (self.composition[a][k] + self.composition[b][k]) for k in theory.MOBILE
            }
            perm = {k: j["permeability_m_per_s"][k] for k in theory.MOBILE}
            out.append(theory.junction_conductance_S(self.p, mean, j["area_m2"], perm))
        return np.asarray(out)

    def rhs(self, t, v, g0):
        g = g0 * abundance(t, self.start, self.formation)
        current = np.array(
            [
                theory.current_A(self.p, c, np.asarray(x), 0.0)
                for c, x in zip(self.composition, v, strict=True)
            ]
        ).reshape(-1)
        lap = np.zeros_like(v)
        for (a, b), gk in zip(self.edges, g, strict=True):
            flow = gk * (v[b] - v[a])
            lap[a] += flow
            lap[b] -= flow
        return (-current + lap) / self.p.capacitance_F

    def apply(self, t, events):
        before_v, before_c = self.v.copy(), [dict(c) for c in self.composition]
        for e in events:
            i = self.index[e["slot"]]
            if e["newcomer"] == "donor_copy":
                j = self.index[e["donor"]]
                self.v[i], self.composition[i] = before_v[j], dict(before_c[j])
            else:
                tmpl = self.templates[e["template"]]
                volume = tmpl["volume_pL"]
                self.composition[i] = {k: tmpl["amounts_fmol"][k] / volume for k in theory.MOBILE}
                q = (
                    F
                    * MOL_PER_FMOL
                    * sum(
                        v * tmpl["amounts_fmol"][s]
                        for s, v in (("Na", 1), ("K", 1), ("M", -1), ("P", -1))
                    )
                )
                self.v[i] = (
                    q + F * MOL_PER_FMOL * tmpl["fixed_charge_equivalent_fmol"]
                ) / self.p.capacitance_F
            for k, (a, b) in enumerate(self.edges):
                if i in (a, b):
                    self.start[k] = t

    def integrate(self, end, t_eval, *, rtol=1e-10, atol=1e-13):
        lag = self.formation["lag_s"]
        events_at = {}
        for e in self.events:
            if e["time"] < end:
                events_at.setdefault(e["time"], []).append(e)
        points = sorted({*events_at, *(t + lag for t in events_at if 0 < t + lag < end), end})
        t_eval = sorted(set(float(t) for t in t_eval))
        out, start = {}, 0.0
        if 0.0 in t_eval:
            out[0.0] = self.v.copy()
        for stop in points:
            if start in events_at:
                self.apply(start, events_at[start])
            g0 = self.conductance()
            inside = [t for t in t_eval if start < t <= stop]
            solution = integrate.solve_ivp(
                lambda t, v, g0=g0: self.rhs(t, v, g0),
                (start, stop),
                self.v,
                method="BDF",
                t_eval=inside or None,
                rtol=rtol,
                atol=atol,
                max_step=0.05,
            )
            if not solution.success:
                raise RuntimeError(solution.message)
            for t, column in zip(solution.t, solution.y.T, strict=True):
                out[float(t)] = column.copy()
            self.v = solution.y[:, -1].copy()
            start = stop
        return {t: out[t] for t in t_eval}
