"""Finite owned inventories composed with the named mass-action ATPase.

Host roles become numeric indices; the RK4 engine has no pump-law selector.
Geometry, channel/junction physics and conservative ledgers are shared with v1.
"""

import jax.numpy as jnp
import numpy as np

from cells.core.errors import NumericalError
from cells.core.schedule import PhysicalIonicGraphControl, control_values
from cells.core.specs import KINETIC_FINITE_EXTRACELLULAR_ID, ConfigError
from cells.core.state import KineticFiniteExtracellularLayout
from cells.models import finite_extracellular as finite
from cells.models.kinetic_finite_bounds import check_pump_interpolants
from cells.processes import kinetic_pump as pump
from cells.processes.electrochemistry import electrochemical_potential

STATE_TYPE = finite.STATE_TYPE
LAYOUT_TYPE = KineticFiniteExtracellularLayout
STATE_AXES = finite.STATE_AXES
BATCH_CAPACITIES = finite.BATCH_CAPACITIES
OBSERVER_ID = "kinetic_finite_extracellular_physical_readouts@1"
OBSERVATION_SAMPLING = "read_only_interval_control_cubic_hermite_kinetic_enclosed@1"
STAGE_DOMAIN_ID = "finite_compartments_mass_action_positive_pump_domain@1"
MAX_STEP = 0.0001
batch_signature = finite.batch_signature
parameters = finite.parameters
balances = finite.balances
cell_voltage = finite.cell_voltage
channel_readouts = finite.channel_readouts
junction_readouts = finite.junction_readouts


def working_size(spec):
    # Ten extra layout leaves, process temporaries and host interval enclosures;
    # conservative float64-equivalent buffers, not compiler/OS memory.
    return finite.working_size(spec) + 192 * spec.execution.membrane_capacity


def declared_parameters(p):
    m = p.metabolism
    return pump.Parameters(
        p.capacity_fmol_per_s,
        m.atp_mM,
        m.adp_mM,
        m.pi_mM,
        p.km_na_mM,
        p.km_k_mM,
        p.km_atp_mM,
        m.delta_g0_J_per_mol,
    )


def check_definition(model, *, junction_check=None, outside_compartments=None):
    finite.check_definition(
        model, junction_check=junction_check, outside_compartments=outside_compartments
    )
    # Small active-spec vectors only: reject derived coefficients before the
    # runner allocates any capacity-sized array.
    with np.errstate(over="ignore", invalid="ignore", divide="ignore", under="ignore"):
        outsides = (model.extracellular,) if outside_compartments is None else outside_compartments
        concentrations = {c.id: np.asarray(c.initial_amount_fmol) / c.volume_pL for c in outsides}
        for cell, membrane in zip(model.cells, model.membranes, strict=True):
            p = membrane.pump
            if p is None:
                continue
            outside = concentrations[membrane.outside]
            inside = np.asarray(cell.initial_amount_fmol) / cell.volume_pL
            mu = electrochemical_potential(
                inside,
                outside,
                membrane.initial_voltage_V,
                np.asarray(model.valence),
                model.temperature_K,
                xp=np,
            )
            na, k = (model.species_ids.index(s) for s in p.roles)
            args = (
                inside[na],
                outside[k],
                mu[na],
                mu[k],
                model.temperature_K,
                declared_parameters(p),
                1.0,
            )
            if (
                not pump.domain_valid(*args, xp=np)
                or not np.isfinite(pump.kinetics(*args, xp=np)).all()
            ):
                raise ConfigError("Initial kinetic pump domain or derived rate is invalid")


def initial_values(spec):
    state, values = finite.bind_geometry(spec)
    bind_pumps(spec, values)
    return state, LAYOUT_TYPE(**values)


def bind_pumps(spec, values):
    """Bind numeric pump roles/parameters into the composing geometry layout."""
    nm = spec.execution.membrane_capacity
    values.update(
        pump_present=np.zeros(nm, dtype=bool),
        pump_sodium_species=np.zeros(nm, dtype=np.int64),
        pump_potassium_species=np.zeros(nm, dtype=np.int64),
    )
    for name in ("atp_mM", "adp_mM", "pi_mM", "km_na_mM", "km_k_mM", "km_atp_mM", "delta_g0_J_mol"):
        neutral = 0.0 if name == "delta_g0_J_mol" else 1000.0 if name == "pi_mM" else 1.0
        values["pump_" + name] = np.full(nm, neutral)
    for i, membrane in enumerate(spec.model.membranes):
        p = membrane.pump
        if p is None:
            continue
        params = declared_parameters(p)
        values["pump_present"][i] = True
        values["pump_sodium_species"][i], values["pump_potassium_species"][i] = (
            spec.model.species_ids.index(s) for s in p.roles
        )
        values["stoichiometry"][:, i] = p.stoichiometry
        values["pump_capacity"][i] = p.capacity_fmol_per_s
        values["pump_drive"][i] = pump.chemical_drive(params, spec.model.temperature_K, xp=np)
        for name, value in zip(params._fields[1:], params[1:], strict=True):
            values["pump_" + name][i] = value


def pump_parameters(layout):
    return pump.Parameters(
        layout.pump_capacity,
        *(getattr(layout, "pump_" + name) for name in pump.Parameters._fields[1:]),
    )


def role_inputs(ci, co, mu, temperature, layout, *, xp):
    # Safe integer gathers precede masking. Only absent routes receive neutral
    # arguments; blocked but physically present pumps retain their real domain.
    slots = xp.arange(layout.pump_capacity.shape[-1])
    present = layout.pump_present
    return (
        xp.where(present, ci[..., layout.pump_sodium_species, slots], 1.0),
        xp.where(present, co[..., layout.pump_potassium_species, slots], 1.0),
        xp.where(present, mu[..., layout.pump_sodium_species, slots], 0.0),
        xp.where(present, mu[..., layout.pump_potassium_species, slots], 0.0),
        xp.where(present, temperature, 298.15),
    )


def readouts(state, control, layout, *, xp=jnp):
    ci, co, voltage, temp, leak, mu = finite.passive_readouts(state, control, layout, xp=xp)
    rate = pump.kinetics(
        *role_inputs(ci, co, mu, temp, layout, xp=xp),
        pump_parameters(layout),
        control[..., -1, :],
        xp=xp,
    )
    return tuple(
        xp.where(layout.membrane_active, v, 0.0)
        for v in (
            voltage,
            leak,
            rate.cycles_fmol_s,
            mu,
            xp.where(layout.pump_present, rate.cycle_free_energy_J_mol, 0.0),
        )
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
    ci, co, voltage, temp = finite.membrane_inputs(state, layout, xp=xp)
    # Predicate-only neutral logarithms avoid invalid host/device arithmetic.
    # The original inventory still determines acceptance in finite.domain_valid;
    # neither RHS inputs nor the state are floored or repaired here.
    safe_ci = xp.where(xp.isfinite(ci) & (ci > 0), ci, 1.0)
    safe_co = xp.where(xp.isfinite(co) & (co > 0), co, 1.0)
    mu = electrochemical_potential(
        safe_ci, safe_co, voltage[..., None, :], layout.valence, temp, xp=xp
    )
    valid = pump.domain_valid(
        *role_inputs(ci, co, mu, temp, layout, xp=xp),
        pump_parameters(layout),
        1.0,
        xp=xp,
    )
    return finite.domain_valid(state, layout, active, xp=xp) & xp.all(valid)


def check_steps(spec, steps, controls):
    if np.max(steps, initial=0) > MAX_STEP + 16 * np.finfo(float).eps:
        raise ConfigError(
            "Kinetic finite bath requires actual RK4 steps <= 0.0001 s; "
            "new regimes need qualification"
        )
    state, layout = initial_values(spec)
    held = control_values(spec, [p.time for p in spec.experiment.changes])
    with np.errstate(over="ignore", invalid="ignore", divide="ignore", under="ignore"):
        for i in range(len(held.membrane)):
            c = PhysicalIonicGraphControl(*(v[i] for v in held))
            values = (
                *rhs(state, c, layout, layout.active, xp=np),
                *readouts(state, c.membrane, layout, xp=np),
                *channel_readouts(state, c.channel, layout, xp=np),
                *junction_readouts(state, c.junction, layout, xp=np),
            )
            if not domain_valid(state, layout, layout.active, xp=np) or not all(
                np.isfinite(v).all() for v in values
            ):
                raise ConfigError(
                    "Initial kinetic finite-compartment state/rates violate physical domains"
                )


def check_values(state, spec):
    _, layout = initial_values(spec)
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        valid = domain_valid(state, layout, layout.active, xp=np)
    if not valid:
        raise NumericalError("Invalid kinetic finite-compartment state/domain; no clipping")
    return finite.check_accounting(state, spec, layout, valid)


def check_interpolants(times, history, f0, f1, layout):
    finite.check_interpolants(times, history, f0, f1, layout)
    check_pump_interpolants(times, history, f0, f1, layout)


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
    )


def summarize(history, diagnostics, spec):
    _, layout = initial_values(spec)
    return finite.summarize_geometry(
        history, diagnostics, spec, layout, KINETIC_FINITE_EXTRACELLULAR_ID
    ) | {
        "pump_law": pump.LAW_ID,
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
