"""SPEC-006 scalar gate/permeation reference; no Cells/JAX or coupled integrator.

Equations and provenance: docs/VOLTAGE_GATED_CHANNEL_SPEC.md. Prescribed-voltage
gate responses are analytic, not whole-cell voltage clamps or native BETSE runs.
"""

import bisect
import math
from dataclasses import dataclass

from tests import reference_multispecies as ionic

SCHEMA = "cells.voltage_gated_membrane_reference@1"
PROTOCOL_SCHEMA = "cells.kv1p5_gate_protocol@1"
LAW = "betse_kv1p5_mh@1"
VOLTAGE_DOMAIN_V = (-0.120, 0.060)
TEMPERATURE_K = 298.15


def fraction(value, name):
    value = ionic.number(value, name, nonnegative=True)
    if value > 1:
        raise ValueError(f"{name} must lie in [0, 1]")
    return value


def voltage(value):
    value = ionic.number(value, "gate voltage")
    if not VOLTAGE_DOMAIN_V[0] <= value <= VOLTAGE_DOMAIN_V[1]:
        raise ValueError("Gate voltage outside the declared [-0.120, 0.060] V domain")
    return value


@dataclass(frozen=True)
class Gate:
    m: float
    h: float

    def __post_init__(self):
        fraction(self.m, "activation gate")
        fraction(self.h, "inactivation gate")

    @property
    def open_probability(self):
        return self.m * self.h


@dataclass(frozen=True)
class Kinetics:
    m_inf: float
    h_inf: float
    tau_m_s: float
    tau_h_s: float


def kinetics(voltage_V):
    v = voltage(voltage_V)

    def sigmoid(x):
        if x >= 0:
            return 1 / (1 + math.exp(-x))
        y = math.exp(x)
        return y / (1 + y)

    return Kinetics(
        sigmoid((v + 0.0060) / 0.0064),
        sigmoid(-(v + 0.0253) / 0.0035),
        ionic.number(0.008330 - 0.1163 * v, "activation time constant", positive=True),
        ionic.number(1.620000 - 15.500 * v, "inactivation time constant", positive=True),
    )


def gate_rate(voltage_V, gate):
    if type(gate) is not Gate:
        raise ValueError("Gate state must retain separate immutable m and h")
    k = kinetics(voltage_V)
    return (k.m_inf - gate.m) / k.tau_m_s, (k.h_inf - gate.h) / k.tau_h_s


def equilibrium_gate(voltage_V):
    """Explicit preparation helper; never called implicitly by resolve or replay."""
    k = kinetics(voltage_V)
    return Gate(k.m_inf, k.h_inf)


def relax_gate(voltage_V, gate, elapsed_s):
    """Exact continuous solution only while the supplied voltage is held fixed."""
    if type(gate) is not Gate:
        raise ValueError("Gate state must retain separate immutable m and h")
    k = kinetics(voltage_V)
    elapsed = ionic.number(elapsed_s, "gate elapsed time", nonnegative=True)
    if elapsed == 0:
        return gate
    result = []
    for q, target, tau in ((gate.m, k.m_inf, k.tau_m_s), (gate.h, k.h_inf, k.tau_h_s)):
        scaled = ionic.number(elapsed / tau, "scaled gate elapsed time", nonnegative=True)
        weight = -math.expm1(-scaled)
        result.append(q + (target - q) * weight)
    return Gate(*result)


@dataclass(frozen=True)
class Channel:
    id: str
    membrane_id: str
    species_id: str
    kinetic_law: str
    max_permeability_m_per_s: float
    abundance: float
    initial_gate: Gate

    def __post_init__(self):
        for value in (self.id, self.membrane_id, self.species_id):
            ionic.identifier(value)
        if self.kinetic_law != LAW:
            raise ValueError("Only the named Kv1p5 continuous gate law is specified")
        ionic.number(self.max_permeability_m_per_s, "channel permeability", nonnegative=True)
        ionic.number(self.abundance, "channel abundance", nonnegative=True)
        ionic.number(
            self.max_permeability_m_per_s * self.abundance,
            "scaled channel permeability",
            nonnegative=True,
        )
        if type(self.initial_gate) is not Gate:
            raise ValueError("Initial gate must explicitly retain m and h")


@dataclass(frozen=True)
class Resolved:
    assembly: ionic.Resolved
    channel: Channel

    def __post_init__(self):
        if type(self.assembly) is not ionic.Resolved or type(self.channel) is not Channel:
            raise ValueError("Require immutable resolved ionic assembly and channel")
        p, c = self.assembly, self.channel
        if c.id in (p.cell_id, p.membrane_id, p.bath_id, p.pump_id):
            raise ValueError("Channel ID must be distinct from physical owner IDs")
        if c.membrane_id != p.membrane_id:
            raise ValueError("Channel must identify the declared membrane")
        if c.species_id not in p.species_ids or p.valence[p.species_ids.index(c.species_id)] != 1:
            raise ValueError("Potassium role must bind a declared monovalent positive species")
        if p.temperature_K != TEMPERATURE_K:
            raise ValueError("This gate assembly specifies only the 298.15 K engineering fixture")
        voltage(p.initial_voltage_V)
        ionic.number(
            p.area_m2 * c.max_permeability_m_per_s * c.abundance / ionic.MOL_PER_FMOL,
            "channel flux coefficient",
            nonnegative=True,
        )

    @property
    def species_index(self):
        return self.assembly.species_ids.index(self.channel.species_id)


def resolve(definition):
    ionic.fields(definition, {"schema", "assembly", "channel"}, "gated membrane reference")
    if definition["schema"] != SCHEMA:
        raise ValueError("Unsupported gated membrane reference schema")
    c = ionic.fields(
        definition["channel"],
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
    g = ionic.fields(c["initial_gate"], {"m", "h"}, "initial gate")
    return Resolved(
        ionic.resolve(definition["assembly"]),
        Channel(**(c | {"initial_gate": Gate(g["m"], g["h"])})),
    )


@dataclass(frozen=True)
class Instantaneous:
    baseline: ionic.Instantaneous
    gate_rate_per_s: tuple[float, float]
    open_probability: float
    channel_availability: float
    effective_permeability_m_per_s: float
    channel_flux_fmol_per_s: float
    channel_species_rate_fmol_per_s: tuple[float, ...]
    amount_rate_fmol_per_s: tuple[float, ...]
    bath_rate_fmol_per_s: tuple[float, ...]
    inward_current_A: float
    voltage_rate_V_per_s: float
    channel_dissipation_W: float
    ionic_dissipation_rate_pJ_per_s: float
    stored_ionic_capacitor_energy_rate_W: float


def evaluate(
    resolved, amount=None, gate=None, *, leak_control=None, pump_control=1.0, availability=1.0
):
    if type(resolved) is not Resolved:
        raise ValueError("Require a resolved gated membrane reference")
    p, c = resolved.assembly, resolved.channel
    g = c.initial_gate if gate is None else gate
    if type(g) is not Gate:
        raise ValueError("Gate state must retain m and h")
    u = fraction(availability, "channel availability")
    old = ionic.evaluate(p, amount, leak_control=leak_control, pump_control=pump_control)
    rates = gate_rate(old.voltage_V, g)  # Domain still checked for a disabled channel.
    index = resolved.species_index
    effective = ionic.number(
        c.max_permeability_m_per_s * c.abundance * u * g.open_probability,
        "effective permeability",
        nonnegative=True,
    )
    flow = ionic.passive_flux(
        p.valence[index],
        old.concentration_mM[index],
        p.bath_mM[index],
        old.voltage_V,
        p.temperature_K,
        p.area_m2,
        effective,
    )
    channel_rates = tuple(flow if i == index else 0.0 for i in range(len(p.species_ids)))
    total = tuple(
        ionic.number(a + b, "total ionic rate")
        for a, b in zip(old.amount_rate_fmol_per_s, channel_rates, strict=True)
    )
    current = ionic.number(
        ionic.CHARGE_PER_FMOL
        * ionic.finite_sum(
            (z * j for z, j in zip(p.valence, total, strict=True)), "total charge rate"
        ),
        "current",
    )
    dv = ionic.number(current / p.capacitance_F, "voltage rate")
    channel_dissipation = ionic.number(
        -ionic.MOL_PER_FMOL * flow * old.potential_J_per_mol[index], "channel dissipation"
    )
    dissipated = ionic.finite_sum(
        (*old.passive_dissipation_W, old.pump_dissipation_W, channel_dissipation),
        "ionic dissipation",
    )
    chemical = ionic.number(
        ionic.MOL_PER_FMOL
        * ionic.R
        * p.temperature_K
        * ionic.finite_sum(
            (
                (math.log(ci) - math.log(co)) * j
                for ci, co, j in zip(old.concentration_mM, p.bath_mM, total, strict=True)
            ),
            "chemical energy rate",
        ),
        "chemical power",
    )
    stored = ionic.number(
        chemical + p.capacitance_F * old.voltage_V * dv, "stored ionic energy rate"
    )
    return Instantaneous(
        old,
        rates,
        g.open_probability,
        u,
        effective,
        flow,
        channel_rates,
        total,
        tuple(-j for j in total),
        current,
        dv,
        channel_dissipation,
        ionic.number(1e12 * dissipated, "dissipation in pJ/s"),
        stored,
    )


@dataclass(frozen=True)
class GateProgram:
    initial_gate: Gate
    end_time_s: float
    voltage_steps: tuple[tuple[float, float], ...]
    availability_steps: tuple[tuple[float, float], ...]
    sample_times_s: tuple[float, ...]

    def __post_init__(self):
        if type(self.initial_gate) is not Gate:
            raise ValueError("Require an explicit initial gate")
        end = ionic.number(self.end_time_s, "protocol end time", positive=True)
        for group, check in (
            (self.voltage_steps, voltage),
            (self.availability_steps, lambda v: fraction(v, "channel availability")),
        ):
            if type(group) is not tuple or not group:
                raise ValueError("Step groups must be nonempty immutable tuples")
            last = -1.0
            for i, pair in enumerate(group):
                if type(pair) is not tuple or len(pair) != 2:
                    raise ValueError("Each immutable step must contain time and value")
                t = ionic.number(pair[0], "step time", nonnegative=True)
                if t > end or t <= last or (i == 0 and t != 0):
                    raise ValueError("Step groups start at zero and increase within the horizon")
                check(pair[1])
                last = t
        if type(self.sample_times_s) is not tuple or not self.sample_times_s:
            raise ValueError("Samples must be a nonempty immutable tuple")
        last = -1.0
        for value in self.sample_times_s:
            t = ionic.number(value, "sample time", nonnegative=True)
            if t > end or t <= last:
                raise ValueError("Sample times must increase within the horizon")
            last = t


def resolve_program(raw):
    ionic.fields(
        raw,
        {
            "schema",
            "initial_gate",
            "end_time_s",
            "voltage_steps",
            "availability_steps",
            "sample_times_s",
        },
        "gate protocol",
    )
    if raw["schema"] != PROTOCOL_SCHEMA:
        raise ValueError("Unsupported gate protocol schema")
    gate = ionic.fields(raw["initial_gate"], {"m", "h"}, "initial gate")
    groups = []
    for field, value in (("voltage_steps", "voltage_V"), ("availability_steps", "multiplier")):
        if not isinstance(raw[field], list):
            raise ValueError("Protocol step groups must be lists")
        groups.append(
            tuple(
                (p["time_s"], p[value])
                for p in (ionic.fields(p, {"time_s", value}, field) for p in raw[field])
            )
        )
    if not isinstance(raw["sample_times_s"], list):
        raise ValueError("Sample times must be a list")
    return GateProgram(Gate(**gate), raw["end_time_s"], *groups, tuple(raw["sample_times_s"]))


@dataclass(frozen=True)
class GateSample:
    time_s: float
    voltage_V: float
    m: float
    h: float
    dm_per_s: float
    dh_per_s: float
    open_probability: float
    availability: float
    available_open_fraction: float


def sample_program(program):
    if type(program) is not GateProgram:
        raise ValueError("Require a resolved immutable gate protocol")
    steps, controls = program.voltage_steps, program.availability_steps
    anchors = [program.initial_gate]
    for (start, v), (end, _) in zip(steps, steps[1:], strict=False):
        anchors.append(relax_gate(v, anchors[-1], end - start))
    times = [p[0] for p in steps]
    control_times = [p[0] for p in controls]
    result = []
    for t in program.sample_times_s:
        i = bisect.bisect_right(times, t) - 1
        start, v = steps[i]
        gate = relax_gate(v, anchors[i], t - start)
        dm, dh = gate_rate(v, gate)
        u = controls[bisect.bisect_right(control_times, t) - 1][1]
        result.append(
            GateSample(
                t, v, gate.m, gate.h, dm, dh, gate.open_probability, u, u * gate.open_probability
            )
        )
    return tuple(result)
