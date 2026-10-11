"""Finite inventories, kinetic ATPase and physical-time junction conductance.

All dynamics share RK4 stages. Junction availability multiplies flux while the
intrinsic conductance continues evolving. One edge owns each transfer; voltage
comes from ion inventory. No native species-loop clock or stored-state blocker
is applied, and no temperature scaling or biological parameter fit is implied.
"""

import jax.numpy as jnp
import numpy as np

from cells.core.errors import NumericalError
from cells.core.schedule import PhysicalIonicGraphControl, control_values
from cells.core.specs import JUNCTION_FINITE_EXTRACELLULAR_ID, ConfigError
from cells.core.state import JunctionFiniteExtracellularLayout
from cells.models import finite_extracellular as finite
from cells.models import kinetic_finite_extracellular as kinetic
from cells.observers import hermite_bounds
from cells.processes import junction_gate as gate
from cells.processes.electrochemistry import CHARGE_PER_FMOL

STATE_TYPE = finite.STATE_TYPE
LAYOUT_TYPE = JunctionFiniteExtracellularLayout
STATE_AXES = finite.STATE_AXES
BATCH_CAPACITIES = finite.BATCH_CAPACITIES
OBSERVER_ID = "junction_finite_extracellular_physical_readouts@1"
OBSERVATION_SAMPLING = "read_only_interval_control_cubic_hermite_junction_enclosed@1"
STAGE_DOMAIN_ID = "finite_kinetic_pump_intrinsic_junction_conductance_voltage_domain@1"
MAX_STEP = kinetic.MAX_STEP
batch_signature = finite.batch_signature
parameters = finite.parameters
balances = finite.balances
cell_voltage = finite.cell_voltage
readouts = kinetic.readouts
channel_readouts = finite.channel_readouts


def working_size(spec):
    return kinetic.working_size(spec) + 64 * spec.execution.edge_capacity


def check_junction_definition(edge, voltage):
    p = gate.Parameters(edge.threshold_voltage_V, edge.minimum_open_fraction)
    if not gate.domain_valid(edge.initial_gate, voltage, p, 1.0, xp=np):
        raise ConfigError("Initial junction conductance or voltage leaves the named gate domain")


def check_definition(model):
    kinetic.check_definition(model, junction_check=check_junction_definition)


def bind_junction(spec, values):
    n = spec.execution.edge_capacity
    values["junction_threshold_voltage"] = np.zeros(n)
    values["junction_minimum"] = np.zeros(n)
    for i, edge in enumerate(spec.model.junctions):
        values["junction_threshold_voltage"][i] = edge.threshold_voltage_V
        values["junction_minimum"][i] = edge.minimum_open_fraction


def initial_values(spec):
    state, values = finite.bind_geometry(spec, bind_junction=bind_junction)
    kinetic.bind_pumps(spec, values)
    return state, LAYOUT_TYPE(**values)


def gate_parameters(layout):
    return gate.Parameters(layout.junction_threshold_voltage, layout.junction_minimum)


def junction_kinetics(state, voltage, layout, *, xp):
    p = gate_parameters(layout)
    rates = gate.kinetics(voltage, p, xp=xp)
    derivative = rates.alpha_per_s * (1 - state) - rates.beta_per_s * (
        state - p.minimum_open_fraction
    )
    # State already contains minimum conductance. There is no second bypass.
    return rates.target, derivative, xp.zeros_like(layout.junction_permeability)


def junction_readouts(state, availability, layout, *, xp=jnp):
    return finite.junction_readouts(
        state, availability, layout, xp=xp, gate_kinetics=junction_kinetics
    )


def rhs(state, control, layout, active, *, xp=jnp):
    _, leak, cycles, mu, affinity = readouts(state, control.membrane, layout, xp=xp)
    return finite.assemble_rhs(
        state,
        layout,
        active,
        leak,
        cycles,
        mu,
        affinity,
        channel_readouts(state, control.channel, layout, xp=xp),
        junction_readouts(state, control.junction, layout, xp=xp),
        xp=xp,
    )


def domain_valid(state, layout, active, *, xp=jnp):
    voltage = cell_voltage(state.amount_increment, layout, xp=xp)
    delta = voltage[..., layout.senders] - voltage[..., layout.receivers]
    valid = gate.domain_valid(state.junction_gate, delta, gate_parameters(layout), 1.0, xp=xp)
    return kinetic.domain_valid(state, layout, active, xp=xp) & xp.all(
        xp.where(layout.junction_active, valid, True)
    )


def check_steps(spec, steps, controls):
    maximum_step = np.max(steps, initial=0)
    if maximum_step > MAX_STEP + 16 * np.finfo(float).eps:
        raise ConfigError("Junction finite model requires actual RK4 steps <= 0.0001 s")
    # Voltage can change during a step; bound rates over the whole declared
    # domain, including fully blocked routes. Alpha peaks at zero voltage and
    # beta is bounded by 20 /s. This is a resolution guard, not an error estimate.
    for edge in spec.model.junctions:
        rate_bound = 1.3 * np.exp(77 * edge.threshold_voltage_V) + 20.0
        if maximum_step * rate_bound > 0.125:
            raise ConfigError("RK4 step does not resolve the declared junction rate bound")
    state, layout = initial_values(spec)
    held = control_values(spec, [p.time for p in spec.experiment.changes])
    with np.errstate(over="ignore", invalid="ignore", divide="ignore", under="ignore"):
        for i in range(len(held.membrane)):
            control = PhysicalIonicGraphControl(*(v[i] for v in held))
            values = (
                *rhs(state, control, layout, layout.active, xp=np),
                *readouts(state, control.membrane, layout, xp=np),
                *channel_readouts(state, control.channel, layout, xp=np),
                *junction_readouts(state, control.junction, layout, xp=np),
            )
            if not domain_valid(state, layout, layout.active, xp=np) or not all(
                np.isfinite(v).all() for v in values
            ):
                raise ConfigError("Initial coupled junction state/rates violate physical domains")


def check_values(state, spec):
    _, layout = initial_values(spec)
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        valid = domain_valid(state, layout, layout.active, xp=np)
    if not valid:
        raise NumericalError("Invalid coupled junction state/domain; no clipping")
    return finite.check_accounting(state, spec, layout, valid)


def check_interpolants(times, history, f0, f1, layout):
    kinetic.check_interpolants(times, history, f0, f1, layout)
    if len(times) < 2:
        return
    mask = layout.junction_active
    lo, hi = hermite_bounds(times, history.junction_gate, f0.junction_gate, f1.junction_gate)
    if np.any(lo[..., mask] < layout.junction_minimum[mask]):
        raise NumericalError("Cubic interior violates intrinsic junction minimum conductance")
    voltage = cell_voltage(history.amount_increment, layout, xp=np)
    scale = CHARGE_PER_FMOL / layout.capacitance[layout.cell_membranes]
    slopes = [scale * np.sum(layout.valence * f.amount_increment, axis=-2) for f in (f0, f1)]
    lo, hi = hermite_bounds(
        times,
        voltage[..., layout.senders] - voltage[..., layout.receivers],
        *(v[..., layout.senders] - v[..., layout.receivers] for v in slopes),
    )
    if np.any(np.maximum(np.abs(lo[..., mask]), np.abs(hi[..., mask])) > gate.MAX_ABS_VOLTAGE_V):
        raise NumericalError("Cubic interior violates named junction voltage domain")


def observe_history(times, history, layout, requested, spec):
    return finite.observe_composed_history(
        times,
        history,
        LAYOUT_TYPE(*(np.asarray(v) for v in layout)),
        requested,
        spec,
        rhs=rhs,
        readouts=readouts,
        check_values=check_values,
        check_interpolants=check_interpolants,
        junction_readouts=junction_readouts,
    )


def summarize(history, diagnostics, spec):
    _, layout = initial_values(spec)
    return finite.summarize_geometry(
        history, diagnostics, spec, layout, JUNCTION_FINITE_EXTRACELLULAR_ID
    ) | {
        "pump_law": kinetic.pump.LAW_ID,
        "junction_law": gate.LAW_ID,
        "junction_state": "intrinsic conductance in [minimum,1]; availability scales flux only",
        "external_support": [
            "temperature",
            "fixed volumes/geometries",
            "maintained ATP/ADP/Pi reservoirs",
        ],
        "energy_scope": (
            "finite ideal chemical inventories, capacitors, dissipation and maintained "
            "hydrolysis work; no dynamic metabolism or gating energy"
        ),
    }
