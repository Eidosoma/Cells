"""SPEC-008 scalar reference. No Cells/JAX imports, maintained bath or integrator."""

import math
from dataclasses import dataclass

from tests import reference_multispecies as ion
from tests import reference_physical_ionic_graph as graph
from tests import reference_voltage_gated_channel as channel

SCHEMA = "cells.finite_extracellular_reference@1"
CHARGE_TOLERANCE_C = 1e-20


def total(values):
    return ion.finite_sum(values, "finite-compartment sum")


@dataclass(frozen=True)
class Compartment:
    id: str
    volume_pL: float
    initial_amount_fmol: tuple[float, ...]
    fixed_charge_equivalent_fmol: float

    def __post_init__(self):
        ion.identifier(self.id)
        ion.number(self.volume_pL, "compartment volume", positive=True)
        ion.number(1.0 / self.volume_pL, "amount-to-concentration coefficient", positive=True)
        graph.immutable_vector(
            self.initial_amount_fmol,
            len(self.initial_amount_fmol),
            "initial amounts",
            positive=True,
        )
        if not self.initial_amount_fmol:
            raise ValueError("Compartment requires species amounts")
        ion.number(self.fixed_charge_equivalent_fmol, "fixed charge")
        self.concentrations(self.initial_amount_fmol)

    def concentrations(self, amount):
        return tuple(ion.number(n / self.volume_pL, "concentration", positive=True) for n in amount)

    def charge(self, valence, amount):
        return ion.number(
            ion.CHARGE_PER_FMOL
            * total(
                (
                    self.fixed_charge_equivalent_fmol,
                    *(z * n for z, n in zip(valence, amount, strict=True)),
                )
            ),
            "compartment charge",
        )


@dataclass(frozen=True)
class Pump:
    id: str
    roles: tuple[str, str]
    stoichiometry: tuple[int, ...]
    capacity_fmol_per_s: float
    drive_J_per_mol: float

    def __post_init__(self):
        ion.identifier(self.id)
        if type(self.roles) is not tuple or len(self.roles) != 2:
            raise ValueError("Pump roles must be an immutable pair")
        for role in self.roles:
            ion.identifier(role)
        if type(self.stoichiometry) is not tuple or any(
            type(x) is not int for x in self.stoichiometry
        ):
            raise ValueError("Pump stoichiometry must be immutable integers")
        ion.number(self.capacity_fmol_per_s, "pump capacity", nonnegative=True)
        ion.number(self.drive_J_per_mol, "pump drive")


@dataclass(frozen=True)
class Membrane:
    id: str
    inside: str
    outside: str
    area_m2: float
    specific_capacitance_F_per_m2: float
    permeability_m_per_s: tuple[float, ...]
    initial_voltage_V: float
    pump: Pump | None

    def __post_init__(self):
        for x in (self.id, self.inside, self.outside):
            ion.identifier(x)
        for name in ("area_m2", "specific_capacitance_F_per_m2"):
            ion.number(getattr(self, name), name, positive=True)
        ion.number(self.capacitance_F, "capacitance", positive=True)
        ion.number(ion.CHARGE_PER_FMOL / self.capacitance_F, "charge conversion", positive=True)
        ion.number(self.initial_voltage_V, "initial voltage")
        graph.immutable_vector(
            self.permeability_m_per_s,
            len(self.permeability_m_per_s),
            "permeability",
            nonnegative=True,
        )
        for p in self.permeability_m_per_s:
            ion.number(
                self.area_m2 * p / ion.MOL_PER_FMOL, "membrane flux coefficient", nonnegative=True
            )
        if self.pump is not None and type(self.pump) is not Pump:
            raise ValueError("Membrane pump must be resolved or absent")

    @property
    def capacitance_F(self):
        return self.area_m2 * self.specific_capacitance_F_per_m2


@dataclass(frozen=True)
class World:
    species_ids: tuple[str, ...]
    valence: tuple[int, ...]
    temperature_K: float
    extracellular: Compartment
    cells: tuple[Compartment, ...]
    membranes: tuple[Membrane, ...]
    channels: tuple[channel.Channel, ...]
    junctions: tuple[graph.Junction, ...]

    def __post_init__(self):
        for name in ("species_ids", "valence", "cells", "membranes", "channels", "junctions"):
            if type(getattr(self, name)) is not tuple:
                raise ValueError("World collections must be immutable tuples")
        size = len(self.species_ids)
        if not size or len(set(self.species_ids)) != size:
            raise ValueError("Species IDs must be nonempty and unique")
        for s in self.species_ids:
            ion.identifier(s)
        if len(self.valence) != size or any(
            type(z) is not int or z not in ion.VALENCES for z in self.valence
        ):
            raise ValueError("Unsupported valence table")
        ion.number(self.temperature_K, "temperature", positive=True)
        ion.number(ion.R * self.temperature_K, "thermal energy", positive=True)
        ion.number(2 * ion.R * self.temperature_K, "pump thermal scale", positive=True)
        if not self.cells or len(self.cells) != len(self.membranes):
            raise ValueError("Require one membrane for each cell")
        compartments = (*self.cells, self.extracellular)
        if any(
            type(c) is not Compartment or len(c.initial_amount_fmol) != size for c in compartments
        ):
            raise ValueError("Every compartment must bind all species")
        owners = [c.id for c in compartments]
        for c, m in zip(self.cells, self.membranes, strict=True):
            if type(m) is not Membrane or m.inside != c.id or m.outside != self.extracellular.id:
                raise ValueError(
                    "Membrane must face its cell and the sole extracellular compartment"
                )
            if len(m.permeability_m_per_s) != size:
                raise ValueError("Membrane must bind all species")
            owners.append(m.id)
            if (
                abs(
                    c.charge(self.valence, c.initial_amount_fmol) / m.capacitance_F
                    - m.initial_voltage_V
                )
                > ion.ANCHOR_TOLERANCE_V
            ):
                raise ValueError("Cell charge and voltage anchor are inconsistent")
            for z in self.valence:
                ion.dimensionless_voltage(z, m.initial_voltage_V, self.temperature_K)
            p = m.pump
            if p is not None:
                if p.roles[0] == p.roles[1] or any(s not in self.species_ids for s in p.roles):
                    raise ValueError("Pump requires distinct existing roles")
                if any(self.valence[self.species_ids.index(s)] != 1 for s in p.roles):
                    raise ValueError("Pump roles must be monovalent positive species")
                expected = tuple(
                    -3 if s == p.roles[0] else 2 if s == p.roles[1] else 0 for s in self.species_ids
                )
                if p.stoichiometry != expected:
                    raise ValueError("Pump stoichiometry must be -3 sodium / +2 potassium")
                owners.append(p.id)
        bound = set()
        for c in self.channels:
            if (
                type(c) is not channel.Channel
                or c.membrane_id not in self.membrane_ids
                or c.membrane_id in bound
            ):
                raise ValueError("At most one resolved channel per declared membrane")
            if (
                c.species_id not in self.species_ids
                or self.valence[self.species_ids.index(c.species_id)] != 1
            ):
                raise ValueError("Channel must bind a monovalent positive species")
            if self.temperature_K != channel.TEMPERATURE_K:
                raise ValueError("Kv1p5 reference requires 298.15 K")
            m = self.membranes[self.membrane_ids.index(c.membrane_id)]
            channel.voltage(m.initial_voltage_V)
            ion.number(
                m.area_m2 * c.max_permeability_m_per_s * c.abundance / ion.MOL_PER_FMOL,
                "channel flux coefficient",
                nonnegative=True,
            )
            bound.add(c.membrane_id)
            owners.append(c.id)
        pairs = set()
        for e in self.junctions:
            if (
                type(e) is not graph.Junction
                or e.from_cell not in self.cell_ids
                or e.to_cell not in self.cell_ids
            ):
                raise ValueError("Junction must bind two intracellular endpoints")
            pair = frozenset((e.from_cell, e.to_cell))
            if pair in pairs:
                raise ValueError("Duplicate physical edge, including reversed duplicate")
            pairs.add(pair)
            if len(e.permeability_m_per_s) != size:
                raise ValueError("Junction must bind all species")
            dv = (
                self.membranes[self.cell_ids.index(e.from_cell)].initial_voltage_V
                - self.membranes[self.cell_ids.index(e.to_cell)].initial_voltage_V
            )
            for z in self.valence:
                ion.dimensionless_voltage(z, dv, self.temperature_K)
            e.gate_rate(dv, e.initial_gate)
            owners.append(e.id)
        if len(set(owners)) != len(owners):
            raise ValueError("Physical entity IDs must be globally unique")
        if abs(self.initial_countercharge_C) > CHARGE_TOLERANCE_C:
            raise ValueError("Extracellular charge must oppose the membrane capacitors")
        if (
            abs(total(c.charge(self.valence, c.initial_amount_fmol) for c in compartments))
            > CHARGE_TOLERANCE_C
        ):
            raise ValueError("Initial total charge must be zero")

    @property
    def cell_ids(self):
        return tuple(c.id for c in self.cells)

    @property
    def membrane_ids(self):
        return tuple(m.id for m in self.membranes)

    @property
    def channel_cells(self):
        return tuple(self.membrane_ids.index(c.membrane_id) for c in self.channels)

    @property
    def endpoints(self):
        return tuple(
            (self.cell_ids.index(e.from_cell), self.cell_ids.index(e.to_cell))
            for e in self.junctions
        )

    @property
    def initial_countercharge_C(self):
        return total(
            (
                self.extracellular.charge(self.valence, self.extracellular.initial_amount_fmol),
                *(m.capacitance_F * m.initial_voltage_V for m in self.membranes),
            )
        )


def resolve(raw):
    ion.fields(
        raw,
        {"schema", "species", "temperature_K", "extracellular", "cells", "junctions"},
        "finite extracellular world",
    )
    if raw["schema"] != SCHEMA:
        raise ValueError("Unsupported finite extracellular reference schema")
    if type(raw["species"]) is not list or not raw["species"]:
        raise ValueError("Require a species list")
    for s in raw["species"]:
        ion.fields(s, {"id", "valence"}, "species")
    ids = tuple(ion.identifier(s["id"]) for s in raw["species"])

    def aligned(mapping, name):
        ion.fields(mapping, ids, name)
        return tuple(mapping[s] for s in ids)

    def compartment(item):
        ion.fields(
            item,
            {"id", "volume_pL", "initial_amount_fmol", "fixed_charge_equivalent_fmol"},
            "compartment",
        )
        return Compartment(
            **(
                item
                | {"initial_amount_fmol": aligned(item["initial_amount_fmol"], "initial amounts")}
            )
        )

    outside = compartment(raw["extracellular"])
    if type(raw["cells"]) is not list or not raw["cells"] or type(raw["junctions"]) is not list:
        raise ValueError("Require nonempty cells and an explicit junction list")
    cells, membranes, channels, edges = [], [], [], []
    for item in raw["cells"]:
        ion.fields(item, {"cell", "membrane", "channel"}, "local cell")
        c = ion.fields(
            item["cell"],
            {
                "id",
                "volume_pL",
                "initial_amount_fmol",
                "fixed_charge_equivalent_fmol",
                "initial_voltage_V",
            },
            "cell",
        )
        cells.append(compartment({k: v for k, v in c.items() if k != "initial_voltage_V"}))
        m = ion.fields(
            item["membrane"],
            {
                "id",
                "inside",
                "outside",
                "area_m2",
                "specific_capacitance_F_per_m2",
                "passive",
                "pump",
            },
            "membrane",
        )
        passive = ion.fields(m["passive"], {"law", "permeability_m_per_s"}, "passive")
        if passive["law"] != "constant_field@1":
            raise ValueError("Unsupported passive law")
        pump = None
        if m["pump"] is not None:
            p = ion.fields(
                m["pump"],
                {"id", "law", "roles", "stoichiometry", "capacity_fmol_per_s", "drive_J_per_mol"},
                "pump",
            )
            if p["law"] != "nak_atp_affinity_tanh@1":
                raise ValueError("Unsupported pump law")
            roles = ion.fields(p["roles"], {"sodium", "potassium"}, "pump roles")
            role_ids = tuple(ion.identifier(roles[s]) for s in ("sodium", "potassium"))
            ion.fields(p["stoichiometry"], role_ids, "pump stoichiometry")
            pump = Pump(
                p["id"],
                role_ids,
                tuple(p["stoichiometry"].get(s, 0) for s in ids),
                p["capacity_fmol_per_s"],
                p["drive_J_per_mol"],
            )
        membranes.append(
            Membrane(
                m["id"],
                m["inside"],
                m["outside"],
                m["area_m2"],
                m["specific_capacitance_F_per_m2"],
                aligned(passive["permeability_m_per_s"], "permeability"),
                c["initial_voltage_V"],
                pump,
            )
        )
        if item["channel"] is not None:
            ch = ion.fields(
                item["channel"],
                {
                    "id",
                    "membrane_id",
                    "species_id",
                    "kinetic_law",
                    "max_permeability_m_per_s",
                    "abundance",
                    "initial_gate",
                },
                "channel",
            )
            g = ion.fields(ch["initial_gate"], {"m", "h"}, "initial gate")
            channels.append(channel.Channel(**(ch | {"initial_gate": channel.Gate(**g)})))
    for item in raw["junctions"]:
        ion.fields(
            item,
            {
                "id",
                "from_cell",
                "to_cell",
                "area_m2",
                "permeability_m_per_s",
                "residual_fraction",
                "gate",
            },
            "junction",
        )
        gate = ion.fields(
            item["gate"],
            {"law", "sensitivity_per_V", "half_voltage_V", "tau_s", "initial_gate"},
            "junction gate",
        )
        edges.append(
            graph.Junction(
                item["id"],
                item["from_cell"],
                item["to_cell"],
                item["area_m2"],
                aligned(item["permeability_m_per_s"], "edge permeability"),
                aligned(item["residual_fraction"], "residual fraction"),
                **gate,
            )
        )
    return World(
        ids,
        tuple(s["valence"] for s in raw["species"]),
        raw["temperature_K"],
        outside,
        tuple(cells),
        tuple(membranes),
        tuple(channels),
        tuple(edges),
    )


@dataclass(frozen=True)
class State(graph.State):
    extracellular_amount: tuple[float, ...]


def initial_state(world):
    if type(world) is not World:
        raise ValueError("Require a resolved finite world")
    n, s, k, e = len(world.cells), len(world.species_ids), len(world.channels), len(world.junctions)
    return State(
        tuple(c.initial_amount_fmol for c in world.cells),
        ((0.0,) * s,) * n,
        (0.0,) * n,
        (0.0,) * n,
        tuple((c.initial_gate.m, c.initial_gate.h) for c in world.channels),
        (0.0,) * k,
        tuple(e.initial_gate for e in world.junctions),
        ((0.0,) * s,) * e,
        (0.0,) * e,
        world.extracellular.initial_amount_fmol,
    )


def voltages(world, amount):
    return tuple(
        ion.number(
            m.initial_voltage_V
            + ion.CHARGE_PER_FMOL
            / m.capacitance_F
            * total(
                z * (n - a)
                for z, n, a in zip(world.valence, row, c.initial_amount_fmol, strict=True)
            ),
            "voltage",
        )
        for c, m, row in zip(world.cells, world.membranes, amount, strict=True)
    )


def countercharge_increment(world, state):
    outside = ion.CHARGE_PER_FMOL * total(
        z * (n - a)
        for z, n, a in zip(
            world.valence,
            state.extracellular_amount,
            world.extracellular.initial_amount_fmol,
            strict=True,
        )
    )
    return total(
        (
            outside,
            *(
                m.capacitance_F * (v - m.initial_voltage_V)
                for m, v in zip(world.membranes, voltages(world, state.amount), strict=True)
            ),
        )
    )


def validate_state(world, state):
    if type(world) is not World or type(state) is not State:
        raise ValueError("Require a resolved finite world and complete typed state")
    n, s, k, e = len(world.cells), len(world.species_ids), len(world.channels), len(world.junctions)
    graph.matrix(state.amount, n, s, "amounts", positive=True)
    graph.immutable_vector(state.extracellular_amount, s, "outside amounts", positive=True)
    graph.matrix(state.leak_transferred, n, s, "leak ledgers")
    graph.immutable_vector(state.pump_cycles, n, "pump ledgers")
    graph.immutable_vector(state.membrane_dissipated_energy_pJ, n, "membrane dissipation")
    graph.matrix(state.membrane_gate, k, 2, "membrane gates")
    graph.immutable_vector(state.channel_transferred, k, "channel ledgers")
    graph.immutable_vector(state.junction_gate, e, "junction gates")
    graph.matrix(state.junction_transferred, e, s, "junction ledgers")
    graph.immutable_vector(state.junction_dissipated_energy_pJ, e, "edge dissipation")
    for gate in state.membrane_gate:
        channel.Gate(*gate)
    for gate in state.junction_gate:
        channel.fraction(gate, "junction gate")
    vs = voltages(world, state.amount)
    for i, (c, m, row) in enumerate(zip(world.cells, world.membranes, state.amount, strict=True)):
        c.concentrations(row)
        if m.pump is None and state.pump_cycles[i] != 0:
            raise ValueError("Absent pump cannot own a cycle ledger")
        for z in world.valence:
            ion.dimensionless_voltage(z, vs[i], world.temperature_K)
    world.extracellular.concentrations(state.extracellular_amount)
    for i in world.channel_cells:
        channel.voltage(vs[i])
    for edge, (a, b) in zip(world.junctions, world.endpoints, strict=True):
        for z in world.valence:
            ion.dimensionless_voltage(z, vs[a] - vs[b], world.temperature_K)
        edge.target(vs[a] - vs[b])
    if abs(countercharge_increment(world, state)) > CHARGE_TOLERANCE_C:
        raise ValueError("Finite outside countercharge constraint violated")
    return vs


@dataclass(frozen=True)
class Instantaneous:
    rate: State
    voltage_V: tuple[float, ...]
    voltage_rate_V_per_s: tuple[float, ...]
    extracellular_concentration_mM: tuple[float, ...]
    membrane_rate_fmol_per_s: tuple[tuple[float, ...], ...]
    membrane_potential_J_per_mol: tuple[tuple[float, ...], ...]
    membrane_dissipation_W: tuple[float, ...]
    junction_dissipation_W: tuple[float, ...]
    supplied_power_W: float
    stored_energy_rate_W: float


def evaluate(world, state=None, control=None):
    if type(world) is not World:
        raise ValueError("Require a resolved finite world")
    state = initial_state(world) if state is None else state
    control = graph.enabled(world) if control is None else control
    vs = validate_state(world, state)
    graph.validate_control(world, control)
    co = world.extracellular.concentrations(state.extracellular_amount)
    ci = tuple(c.concentrations(row) for c, row in zip(world.cells, state.amount, strict=True))
    rt, a = ion.R * world.temperature_K, ion.MOL_PER_FMOL
    leaks, cycles, membrane, mus, dm, supplied = [], [], [], [], [], []
    hg, hf = [None] * len(world.channels), [0.0] * len(world.channels)
    by_cell = {i: k for k, i in enumerate(world.channel_cells)}
    for i, m in enumerate(world.membranes):
        mu = tuple(
            ion.potential(z, c, o, vs[i], world.temperature_K)
            for z, c, o in zip(world.valence, ci[i], co, strict=True)
        )
        leak = tuple(
            ion.passive_flux(z, c, o, vs[i], world.temperature_K, m.area_m2, p, u)
            for z, c, o, p, u in zip(
                world.valence, ci[i], co, m.permeability_m_per_s, control.leak[i], strict=True
            )
        )
        p = m.pump
        nu = (0,) * len(co) if p is None else p.stoichiometry
        affinity = (
            0.0
            if p is None
            else ion.number(
                p.drive_J_per_mol + total(x * y for x, y in zip(nu, mu, strict=True)),
                "cycle energy",
            )
        )
        r = (
            0.0
            if p is None
            else ion.number(
                p.capacity_fmol_per_s * control.pump[i] * math.tanh(-affinity / (2 * rt)),
                "cycle rate",
            )
        )
        row = [j + x * r for j, x in zip(leak, nu, strict=True)]
        channel_power = 0.0
        if i in by_cell:
            k = by_cell[i]
            ch, gate = world.channels[k], channel.Gate(*state.membrane_gate[k])
            hg[k] = channel.gate_rate(vs[i], gate)
            s = world.species_ids.index(ch.species_id)
            effective = ion.number(
                ch.max_permeability_m_per_s
                * ch.abundance
                * control.channel[k]
                * gate.open_probability,
                "channel permeability",
                nonnegative=True,
            )
            hf[k] = ion.passive_flux(
                world.valence[s], ci[i][s], co[s], vs[i], world.temperature_K, m.area_m2, effective
            )
            row[s] += hf[k]
            channel_power = -a * hf[k] * mu[s]
        leaks.append(leak)
        cycles.append(r)
        membrane.append(tuple(ion.number(x, "membrane species rate") for x in row))
        mus.append(mu)
        dm.append(
            total(
                (
                    -a * total(j * u for j, u in zip(leak, mu, strict=True)),
                    -a * r * affinity,
                    channel_power,
                )
            )
        )
        supplied.append(
            0.0 if p is None else ion.number(-a * p.drive_J_per_mol * r, "supplied power")
        )
    terms = [[[x] for x in row] for row in membrane]
    edge_flow, edge_gate, de = [], [], []
    for k, (edge, (src, dst)) in enumerate(zip(world.junctions, world.endpoints, strict=True)):
        dv = vs[src] - vs[dst]
        flow = tuple(
            graph.transfer(
                z,
                x,
                y,
                dv,
                world.temperature_K,
                edge.area_m2,
                p,
                state.junction_gate[k],
                r,
                control.junction[k],
            )
            for z, x, y, p, r in zip(
                world.valence,
                ci[src],
                ci[dst],
                edge.permeability_m_per_s,
                edge.residual_fraction,
                strict=True,
            )
        )
        mu = tuple(
            ion.potential(z, y, x, -dv, world.temperature_K)
            for z, x, y in zip(world.valence, ci[src], ci[dst], strict=True)
        )
        for s, j in enumerate(flow):
            terms[src][s].append(-j)
            terms[dst][s].append(j)
        edge_flow.append(flow)
        edge_gate.append(edge.gate_rate(dv, state.junction_gate[k]))
        de.append(
            ion.number(-a * total(j * u for j, u in zip(flow, mu, strict=True)), "edge dissipation")
        )
    dn = tuple(tuple(total(t) for t in row) for row in terms)
    dno = tuple(-total(row[s] for row in membrane) for s in range(len(co)))
    dv = tuple(
        ion.number(
            ion.CHARGE_PER_FMOL
            / m.capacitance_F
            * total(z * j for z, j in zip(world.valence, row, strict=True)),
            "voltage rate",
        )
        for m, row in zip(world.membranes, dn, strict=True)
    )
    chemical = (
        a
        * rt
        * total(
            math.log(c) * j
            for row, slope in zip((*ci, co), (*dn, dno), strict=True)
            for c, j in zip(row, slope, strict=True)
        )
    )
    electric = total(
        m.capacitance_F * v * slope for m, v, slope in zip(world.membranes, vs, dv, strict=True)
    )
    rate = State(
        dn,
        tuple(leaks),
        tuple(cycles),
        tuple(ion.number(x * 1e12, "membrane pJ/s") for x in dm),
        tuple(hg),
        tuple(hf),
        tuple(edge_gate),
        tuple(edge_flow),
        tuple(ion.number(x * 1e12, "edge pJ/s") for x in de),
        dno,
    )
    return Instantaneous(
        rate,
        vs,
        dv,
        co,
        tuple(membrane),
        tuple(mus),
        tuple(dm),
        tuple(de),
        total(supplied),
        total((chemical, electric)),
    )


def energy_change_J(world, state):
    vs = validate_state(world, state)
    terms = []
    for c, row in zip(
        (*world.cells, world.extracellular),
        (*state.amount, state.extracellular_amount),
        strict=True,
    ):
        for n, n0 in zip(row, c.initial_amount_fmol, strict=True):
            delta = n - n0
            log_ratio = (
                math.log1p(delta / n0) if abs(delta) < 0.5 * n0 else math.log(n) - math.log(n0)
            )
            terms.append(delta * (math.log(n0 / c.volume_pL) - 1) + n * log_ratio)
    chemical = ion.MOL_PER_FMOL * ion.R * world.temperature_K * total(terms)
    electric = total(
        0.5 * m.capacitance_F * (v - m.initial_voltage_V) * (v + m.initial_voltage_V)
        for m, v in zip(world.membranes, vs, strict=True)
    )
    return total((chemical, electric))


def ledger_residuals(world, state):
    vs = validate_state(world, state)
    local = [
        [
            state.leak_transferred[i][s]
            + (0 if m.pump is None else m.pump.stoichiometry[s] * state.pump_cycles[i])
            for s in range(len(world.species_ids))
        ]
        for i, m in enumerate(world.membranes)
    ]
    for k, i in enumerate(world.channel_cells):
        local[i][world.species_ids.index(world.channels[k].species_id)] += (
            state.channel_transferred[k]
        )
    internal = [[[0.0] for _ in world.species_ids] for _ in world.cells]
    for (src, dst), row in zip(world.endpoints, state.junction_transferred, strict=True):
        for s, x in enumerate(row):
            internal[src][s].append(-x)
            internal[dst][s].append(x)
    inside = tuple(
        tuple(
            n - n0 - total((local[i][s], *internal[i][s]))
            for s, (n, n0) in enumerate(zip(row, c.initial_amount_fmol, strict=True))
        )
        for i, (c, row) in enumerate(zip(world.cells, state.amount, strict=True))
    )
    outside_delta = tuple(
        n - n0
        for n, n0 in zip(
            state.extracellular_amount, world.extracellular.initial_amount_fmol, strict=True
        )
    )
    outside = tuple(
        total((delta, *(row[s] for row in local))) for s, delta in enumerate(outside_delta)
    )
    global_material = tuple(
        total(
            (
                delta,
                *(state.amount[i][s] - c.initial_amount_fmol[s] for i, c in enumerate(world.cells)),
            )
        )
        for s, delta in enumerate(outside_delta)
    )
    work = ion.MOL_PER_FMOL * total(
        m.pump.drive_J_per_mol * p
        for m, p in zip(world.membranes, state.pump_cycles, strict=True)
        if m.pump is not None
    )
    return {
        "inside_material_fmol": inside,
        "outside_material_fmol": outside,
        "global_material_fmol": global_material,
        "countercharge_increment_C": countercharge_increment(world, state),
        "absolute_countercharge_C": total(
            (
                world.extracellular.charge(world.valence, state.extracellular_amount),
                *(m.capacitance_F * v for m, v in zip(world.membranes, vs, strict=True)),
            )
        ),
        "energy_residual_J": total(
            (
                energy_change_J(world, state),
                total((*state.membrane_dissipated_energy_pJ, *state.junction_dissipated_energy_pJ))
                * 1e-12,
                work,
            )
        ),
    }
