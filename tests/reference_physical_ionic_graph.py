"""SPEC-007 immutable scalar composition; no Cells/JAX imports or ODE solver.

Reference tuples are cell-/edge-major. Proposed production species-major axes
are documented separately. Local equations remain the frozen SPEC-005/006 ones.
"""

import math
from dataclasses import dataclass

from tests import reference_multispecies as ionic
from tests import reference_voltage_gated_channel as channel

SCHEMA = "cells.physical_ionic_graph_reference@1"
GATE_LAW = "symmetric_opposing_relaxation@1"


def immutable_vector(value, length, name, **domain):
    if type(value) is not tuple:
        raise ValueError(f"{name} must be an immutable tuple")
    return ionic.vector(value, length, name, **domain)


def matrix(value, rows, columns, name, **domain):
    if type(value) is not tuple or len(value) != rows:
        raise ValueError(f"{name} requires {rows} immutable rows")
    return tuple(immutable_vector(row, columns, name, **domain) for row in value)


@dataclass(frozen=True)
class Junction:
    id: str
    from_cell: str
    to_cell: str
    area_m2: float
    permeability_m_per_s: tuple[float, ...]
    residual_fraction: tuple[float, ...]
    law: str
    sensitivity_per_V: float
    half_voltage_V: float
    tau_s: float
    initial_gate: float

    def __post_init__(self):
        for value in (self.id, self.from_cell, self.to_cell):
            ionic.identifier(value)
        if self.from_cell == self.to_cell:
            raise ValueError("A junction must have distinct endpoints")
        if self.law != GATE_LAW:
            raise ValueError("Unsupported junction gate law")
        for name in ("area_m2", "sensitivity_per_V", "tau_s"):
            ionic.number(getattr(self, name), name, positive=True)
        ionic.number(self.half_voltage_V, "half voltage", nonnegative=True)
        channel.fraction(self.initial_gate, "junction gate")
        if type(self.permeability_m_per_s) is not tuple or not self.permeability_m_per_s:
            raise ValueError("Junction permeability must be a nonempty immutable tuple")
        size = len(self.permeability_m_per_s)
        immutable_vector(self.permeability_m_per_s, size, "permeability", nonnegative=True)
        immutable_vector(self.residual_fraction, size, "residual fraction", nonnegative=True)
        for permeability, residual in zip(
            self.permeability_m_per_s, self.residual_fraction, strict=True
        ):
            channel.fraction(residual, "residual fraction")
            ionic.number(
                self.area_m2 * permeability / ionic.MOL_PER_FMOL,
                "junction flux coefficient",
                nonnegative=True,
            )

    def target(self, delta_v):
        ionic.number(delta_v, "junction voltage")
        a = ionic.number(self.sensitivity_per_V * (-delta_v - self.half_voltage_V), "gate exponent")
        b = ionic.number(self.sensitivity_per_V * (delta_v - self.half_voltage_V), "gate exponent")
        shift = max(0.0, a, b)
        small = math.exp(-shift)
        return small / math.fsum((small, math.exp(a - shift), math.exp(b - shift)))

    def gate_rate(self, delta_v, gate):
        channel.fraction(gate, "junction gate")
        return ionic.number((self.target(delta_v) - gate) / self.tau_s, "junction gate rate")


@dataclass(frozen=True)
class Graph:
    cells: tuple[ionic.Resolved, ...]
    channels: tuple[channel.Resolved, ...]
    junctions: tuple[Junction, ...]

    def __post_init__(self):
        for name in ("cells", "channels", "junctions"):
            if type(getattr(self, name)) is not tuple:
                raise ValueError("Resolved graph collections must be immutable tuples")
        if not self.cells or any(type(p) is not ionic.Resolved for p in self.cells):
            raise ValueError("Require at least one resolved physical cell")
        base = self.cells[0]
        owners = [base.bath_id]
        for p in self.cells:
            for name in (
                "species_ids",
                "valence",
                "bath_id",
                "bath_mM",
                "temperature_K",
                "bath_background_charge_mM",
            ):
                if getattr(p, name) != getattr(base, name):
                    raise ValueError("Graph requires a common species table and maintained bath")
            owners.extend((p.cell_id, p.membrane_id))
            if p.pump_id is not None:
                owners.append(p.pump_id)
        bound_membranes = set()
        for c in self.channels:
            if type(c) is not channel.Resolved or c.assembly not in self.cells:
                raise ValueError("Channel must bind exactly one declared local assembly")
            if c.assembly.membrane_id in bound_membranes:
                raise ValueError("First graph reference permits at most one channel per membrane")
            bound_membranes.add(c.assembly.membrane_id)
            owners.append(c.channel.id)
        pairs = set()
        for e in self.junctions:
            if type(e) is not Junction:
                raise ValueError("Require a resolved junction")
            if e.from_cell not in self.cell_ids or e.to_cell not in self.cell_ids:
                raise ValueError("Junction endpoint is not a declared cell")
            pair = frozenset((e.from_cell, e.to_cell))
            if pair in pairs:
                raise ValueError("Duplicate physical edge, including a reversed duplicate")
            pairs.add(pair)
            if len(e.permeability_m_per_s) != len(base.species_ids):
                raise ValueError("Every junction must bind the complete declared species table")
            a, b = self.cell_ids.index(e.from_cell), self.cell_ids.index(e.to_cell)
            dv = self.cells[a].initial_voltage_V - self.cells[b].initial_voltage_V
            for z in self.valence:
                ionic.dimensionless_voltage(z, dv, base.temperature_K)
            e.gate_rate(dv, e.initial_gate)
            owners.append(e.id)
        if len(set(owners)) != len(owners):
            raise ValueError("Physical entity IDs must be globally unique")

    @property
    def cell_ids(self):
        return tuple(p.cell_id for p in self.cells)

    @property
    def species_ids(self):
        return self.cells[0].species_ids

    @property
    def valence(self):
        return self.cells[0].valence

    @property
    def channel_cells(self):
        return tuple(self.cell_ids.index(c.assembly.cell_id) for c in self.channels)

    @property
    def endpoints(self):
        return tuple(
            (self.cell_ids.index(e.from_cell), self.cell_ids.index(e.to_cell))
            for e in self.junctions
        )


def resolve(raw):
    ionic.fields(raw, {"schema", "species", "bath", "cells", "junctions"}, "physical ionic graph")
    if raw["schema"] != SCHEMA:
        raise ValueError("Unsupported graph reference schema")
    if type(raw["cells"]) is not list or not raw["cells"] or type(raw["junctions"]) is not list:
        raise ValueError("Require a nonempty cell list and an explicit junction list")
    cells, channels, edges = [], [], []
    for item in raw["cells"]:
        ionic.fields(item, {"cell", "membrane", "channel"}, "local cell")
        definition = {
            "schema": ionic.SCHEMA,
            "species": raw["species"],
            "bath": raw["bath"],
            "cell": item["cell"],
            "membrane": item["membrane"],
        }
        if item["channel"] is None:
            cells.append(ionic.resolve(definition))
        else:
            resolved = channel.resolve(
                {"schema": channel.SCHEMA, "assembly": definition, "channel": item["channel"]}
            )
            cells.append(resolved.assembly)
            channels.append(resolved)
    species = cells[0].species_ids
    for item in raw["junctions"]:
        ionic.fields(
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
        gate = ionic.fields(
            item["gate"],
            {"law", "sensitivity_per_V", "half_voltage_V", "tau_s", "initial_gate"},
            "junction gate",
        )
        for name in ("permeability_m_per_s", "residual_fraction"):
            ionic.fields(item[name], species, name)
        edges.append(
            Junction(
                item["id"],
                item["from_cell"],
                item["to_cell"],
                item["area_m2"],
                tuple(item["permeability_m_per_s"][s] for s in species),
                tuple(item["residual_fraction"][s] for s in species),
                **gate,
            )
        )
    return Graph(tuple(cells), tuple(channels), tuple(edges))


@dataclass(frozen=True)
class State:
    """Shared coordinate carrier for physical states and derivatives.

    Physical domain checking is explicit in validate_state, not in construction:
    derivative gate entries are rates and need not lie in [0,1].
    """

    amount: tuple[tuple[float, ...], ...]
    leak_transferred: tuple[tuple[float, ...], ...]
    pump_cycles: tuple[float, ...]
    membrane_dissipated_energy_pJ: tuple[float, ...]
    membrane_gate: tuple[tuple[float, float], ...]
    channel_transferred: tuple[float, ...]
    junction_gate: tuple[float, ...]
    junction_transferred: tuple[tuple[float, ...], ...]
    junction_dissipated_energy_pJ: tuple[float, ...]


@dataclass(frozen=True)
class Control:
    leak: tuple[tuple[float, ...], ...]
    pump: tuple[float, ...]
    channel: tuple[float, ...]
    junction: tuple[float, ...]


def initial_state(graph):
    n, s, k, e = len(graph.cells), len(graph.species_ids), len(graph.channels), len(graph.junctions)
    return State(
        tuple(p.initial_amount_fmol for p in graph.cells),
        ((0.0,) * s,) * n,
        (0.0,) * n,
        (0.0,) * n,
        tuple((c.channel.initial_gate.m, c.channel.initial_gate.h) for c in graph.channels),
        (0.0,) * k,
        tuple(j.initial_gate for j in graph.junctions),
        ((0.0,) * s,) * e,
        (0.0,) * e,
    )


def enabled(graph):
    n, s = len(graph.cells), len(graph.species_ids)
    return Control(
        ((1.0,) * s,) * n, (1.0,) * n, (1.0,) * len(graph.channels), (1.0,) * len(graph.junctions)
    )


def validate_state(graph, state):
    if type(graph) is not Graph or type(state) is not State:
        raise ValueError("Require a resolved graph and complete typed state")
    n, s, k, e = len(graph.cells), len(graph.species_ids), len(graph.channels), len(graph.junctions)
    matrix(state.amount, n, s, "amounts", positive=True)
    matrix(state.leak_transferred, n, s, "leak ledgers")
    immutable_vector(state.pump_cycles, n, "pump ledgers")
    immutable_vector(state.membrane_dissipated_energy_pJ, n, "membrane dissipation")
    gates = matrix(state.membrane_gate, k, 2, "membrane gates")
    immutable_vector(state.channel_transferred, k, "channel ledgers")
    edge_gates = immutable_vector(state.junction_gate, e, "junction gates")
    matrix(state.junction_transferred, e, s, "junction ledgers")
    immutable_vector(state.junction_dissipated_energy_pJ, e, "junction dissipation")
    for gate in gates:
        channel.Gate(*gate)
    for gate in edge_gates:
        channel.fraction(gate, "junction gate")
    voltages = tuple(p.voltage(amount) for p, amount in zip(graph.cells, state.amount, strict=True))
    for i, p in enumerate(graph.cells):
        if p.pump_id is None and state.pump_cycles[i] != 0:
            raise ValueError("Absent pump cannot own a cycle ledger")
        for z in graph.valence:
            ionic.dimensionless_voltage(z, voltages[i], p.temperature_K)
    for i in graph.channel_cells:
        channel.voltage(voltages[i])
    for edge, (a, b) in zip(graph.junctions, graph.endpoints, strict=True):
        for z in graph.valence:
            ionic.dimensionless_voltage(z, voltages[a] - voltages[b], graph.cells[0].temperature_K)
        edge.target(voltages[a] - voltages[b])
    return voltages


def validate_control(graph, control):
    if type(control) is not Control:
        raise ValueError("Require complete independent typed controls")
    n, s = len(graph.cells), len(graph.species_ids)
    leak = matrix(control.leak, n, s, "leak controls")
    groups = (
        *(row for row in leak),
        immutable_vector(control.pump, n, "pump controls"),
        immutable_vector(control.channel, len(graph.channels), "channel controls"),
        immutable_vector(control.junction, len(graph.junctions), "junction controls"),
    )
    for group in groups:
        for value in group:
            channel.fraction(value, "control")


def transfer(z, ca, cb, delta_v, temperature, area, permeability, gate, residual, control):
    """Oriented A->B flux via the same physical law, B treated as 'inside'."""
    for value, name in (
        (gate, "junction gate"),
        (residual, "residual fraction"),
        (control, "junction control"),
    ):
        channel.fraction(value, name)
    ionic.number(permeability, "junction permeability", nonnegative=True)
    effective = ionic.number(
        permeability * (residual + (1 - residual) * gate),
        "effective junction permeability",
        nonnegative=True,
    )
    return ionic.passive_flux(z, cb, ca, -delta_v, temperature, area, effective, control)


@dataclass(frozen=True)
class Instantaneous:
    rate: State
    voltage_V: tuple[float, ...]
    voltage_rate_V_per_s: tuple[float, ...]
    local: tuple[ionic.Instantaneous, ...]
    channels: tuple[channel.Instantaneous, ...]
    junction_potential_J_per_mol: tuple[tuple[float, ...], ...]
    junction_current_A: tuple[float, ...]
    junction_target: tuple[float, ...]
    membrane_dissipation_W: tuple[float, ...]
    junction_dissipation_W: tuple[float, ...]
    bath_rate_fmol_per_s: tuple[tuple[float, ...], ...]
    supplied_power_W: float
    stored_energy_rate_W: float


def evaluate(graph, state=None, control=None):
    if type(graph) is not Graph:
        raise ValueError("Require a resolved physical ionic graph")
    state = initial_state(graph) if state is None else state
    control = enabled(graph) if control is None else control
    volts = validate_state(graph, state)
    validate_control(graph, control)
    channel_by_cell = {
        i: (k, c) for k, (i, c) in enumerate(zip(graph.channel_cells, graph.channels, strict=True))
    }
    locals_, channel_results = [], [None] * len(graph.channels)
    local_rates, dissipation = [], []
    for i, p in enumerate(graph.cells):
        if i in channel_by_cell:
            k, c = channel_by_cell[i]
            result = channel.evaluate(
                c,
                state.amount[i],
                channel.Gate(*state.membrane_gate[k]),
                leak_control=control.leak[i],
                pump_control=control.pump[i],
                availability=control.channel[k],
            )
            channel_results[k] = result
            local_rates.append(result.amount_rate_fmol_per_s)
            dissipation.append(result.ionic_dissipation_rate_pJ_per_s * 1e-12)
            locals_.append(result.baseline)
        else:
            result = ionic.evaluate(
                p, state.amount[i], leak_control=control.leak[i], pump_control=control.pump[i]
            )
            local_rates.append(result.amount_rate_fmol_per_s)
            dissipation.append(
                ionic.finite_sum(
                    (*result.passive_dissipation_W, result.pump_dissipation_W), "local dissipation"
                )
            )
            locals_.append(result)
    # A local membrane is evaluated once; only edge contributions are scattered.
    terms = [[[value] for value in row] for row in local_rates]
    transfers, edge_mu, edge_dissipation, edge_current, targets, gate_rates = [], [], [], [], [], []
    temperature = graph.cells[0].temperature_K
    for edge, (a, b), gate, u in zip(
        graph.junctions, graph.endpoints, state.junction_gate, control.junction, strict=True
    ):
        dv = volts[a] - volts[b]
        flow, potential = [], []
        for j, (z, permeability, residual) in enumerate(
            zip(graph.valence, edge.permeability_m_per_s, edge.residual_fraction, strict=True)
        ):
            ca, cb = (
                state.amount[a][j] / graph.cells[a].volume_pL,
                state.amount[b][j] / graph.cells[b].volume_pL,
            )
            value = transfer(
                z, ca, cb, dv, temperature, edge.area_m2, permeability, gate, residual, u
            )
            flow.append(value)
            potential.append(ionic.potential(z, cb, ca, -dv, temperature))
            terms[a][j].append(-value)
            terms[b][j].append(value)
        transfers.append(tuple(flow))
        edge_mu.append(tuple(potential))
        edge_dissipation.append(
            ionic.number(
                -ionic.MOL_PER_FMOL
                * ionic.finite_sum(
                    (j * mu for j, mu in zip(flow, potential, strict=True)), "edge passive products"
                ),
                "edge dissipation",
            )
        )
        edge_current.append(
            ionic.number(
                ionic.CHARGE_PER_FMOL
                * ionic.finite_sum(
                    (z * j for z, j in zip(graph.valence, flow, strict=True)), "edge charge rate"
                ),
                "edge current",
            )
        )
        targets.append(edge.target(dv))
        gate_rates.append(edge.gate_rate(dv, gate))
    amount_rates = tuple(
        tuple(ionic.finite_sum(values, "complete cell species rate") for values in row)
        for row in terms
    )
    voltage_rates = tuple(
        ionic.number(
            ionic.CHARGE_PER_FMOL
            / p.capacitance_F
            * ionic.finite_sum(
                (z * j for z, j in zip(graph.valence, row, strict=True)), "cell charge rate"
            ),
            "cell voltage rate",
        )
        for p, row in zip(graph.cells, amount_rates, strict=True)
    )
    energy_terms = []
    for i, p in enumerate(graph.cells):
        chemical = (
            ionic.MOL_PER_FMOL
            * ionic.R
            * temperature
            * ionic.finite_sum(
                (
                    (math.log(n / p.volume_pL) - math.log(co)) * j
                    for n, co, j in zip(state.amount[i], p.bath_mM, amount_rates[i], strict=True)
                ),
                "cell chemical energy rate",
            )
        )
        energy_terms.append(
            ionic.number(
                chemical + p.capacitance_F * volts[i] * voltage_rates[i], "cell stored energy rate"
            )
        )
    rates = State(
        amount_rates,
        tuple(r.passive_fmol_per_s for r in locals_),
        tuple(r.pump_cycles_fmol_per_s for r in locals_),
        tuple(ionic.number(d * 1e12, "membrane dissipation pJ/s") for d in dissipation),
        tuple(r.gate_rate_per_s for r in channel_results),
        tuple(r.channel_flux_fmol_per_s for r in channel_results),
        tuple(gate_rates),
        tuple(transfers),
        tuple(ionic.number(d * 1e12, "junction dissipation pJ/s") for d in edge_dissipation),
    )
    return Instantaneous(
        rates,
        volts,
        voltage_rates,
        tuple(locals_),
        tuple(channel_results),
        tuple(edge_mu),
        tuple(edge_current),
        tuple(targets),
        tuple(dissipation),
        tuple(edge_dissipation),
        tuple(tuple(-j for j in row) for row in local_rates),
        ionic.finite_sum((r.chemical_power_W for r in locals_), "supplied power"),
        ionic.finite_sum(energy_terms, "graph stored energy rate"),
    )


def ledger_residuals(graph, state):
    """Pure algebra on supplied complete histories; never construct a trajectory."""
    volts = validate_state(graph, state)
    local = [
        [
            state.leak_transferred[i][s] + p.stoichiometry[s] * state.pump_cycles[i]
            for s in range(len(graph.species_ids))
        ]
        for i, p in enumerate(graph.cells)
    ]
    for k, (i, c) in enumerate(zip(graph.channel_cells, graph.channels, strict=True)):
        local[i][c.species_index] += state.channel_transferred[k]
    internal = [[[0.0] for _ in graph.species_ids] for _ in graph.cells]
    for (a, b), transfer_row in zip(graph.endpoints, state.junction_transferred, strict=True):
        for s, value in enumerate(transfer_row):
            internal[a][s].append(-value)
            internal[b][s].append(value)
    internal = tuple(
        tuple(ionic.finite_sum(terms, "internal transfer") for terms in row) for row in internal
    )
    total = tuple(
        tuple(ionic.number(a + b, "net transfer") for a, b in zip(local_row, edge_row, strict=True))
        for local_row, edge_row in zip(local, internal, strict=True)
    )
    material = tuple(
        tuple(
            ionic.number(n - anchor - transfer, "material residual")
            for n, anchor, transfer in zip(
                state.amount[i], p.initial_amount_fmol, total[i], strict=True
            )
        )
        for i, p in enumerate(graph.cells)
    )
    charge = tuple(
        ionic.number(
            volts[i]
            - p.initial_voltage_V
            - ionic.CHARGE_PER_FMOL
            / p.capacitance_F
            * ionic.finite_sum(
                (z * t for z, t in zip(graph.valence, total[i], strict=True)), "ledger charge"
            ),
            "charge residual",
        )
        for i, p in enumerate(graph.cells)
    )
    return {
        "material_fmol": material,
        "charge_V": charge,
        "bath_exchange_fmol": tuple(tuple(-v for v in row) for row in local),
        "internal_transfer_fmol": internal,
        "global_material_fmol": tuple(
            ionic.finite_sum(
                (
                    state.amount[i][s] - p.initial_amount_fmol[s] - local[i][s]
                    for i, p in enumerate(graph.cells)
                ),
                "global material residual",
            )
            for s in range(len(graph.species_ids))
        ),
    }
