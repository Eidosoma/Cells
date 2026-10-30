"""Owned calcium/ER and expanded channels with one finite cellular fuel owner.

Existing metabolic_work_pJ is an internal pump/pool transfer diagnostic. The
combined transformed balance owns finite pool free energy and counts only the
declared regeneration supply as external energetic input. Geometry stays fixed.
"""

from dataclasses import make_dataclass, replace
from typing import NamedTuple

import jax
import jax.numpy as jnp
import numpy as np

from cells.core.errors import NumericalError
from cells.core.specs import ConfigError
from cells.core.surface_calcium_energy_spec import (
    SurfaceCalciumEnergyActivatedModel,
    SurfaceCalciumEnergyCatalogModel,
    SurfaceCalciumEnergyHCNExtraModel,
    SurfaceCalciumEnergyMorrisLecarModel,
    initial_prior_spec,
    model_id,
)
from cells.models import compartment_reactions as chemistry
from cells.models import kinetic_finite_extracellular as pump_layout
from cells.models import surface_calcium_catalog as prior
from cells.models import surface_tissue as passive
from cells.models.surface_calcium import (
    CALCIUM_ACTIVATED_LAYOUT_TYPE as CALCIUM_ACTIVATED_PRIOR_LAYOUT,
)
from cells.models.surface_calcium import EXTENDED_CATALOG_LAYOUT_TYPE as CALCIUM_CATALOG_LAYOUT_TYPE
from cells.models.surface_calcium import HCN_EXTRA_LAYOUT_TYPE as HCN_EXTRA_PRIOR_LAYOUT
from cells.models.surface_calcium import MORRIS_LECAR_LAYOUT_TYPE as MORRIS_LECAR_PRIOR_LAYOUT
from cells.numerics import surface_field as field
from cells.numerics.extracellular_field import ordered_scatter
from cells.processes import finite_calcium_pumps as calcium
from cells.processes import finite_energy as energy
from cells.processes import kinetic_pump as pump
from cells.processes.electrochemistry import R

OBSERVER_ID = "resolved_calcium_finite_energy_accepted_grid@1"
STAGE_DOMAIN_ID = "owned_calcium_and_finite_cellular_atp_actual_controls@1"
OBSERVATION_SAMPLING = prior.OBSERVATION_SAMPLING
BATCH_CAPACITIES = (*prior.BATCH_CAPACITIES, "regeneration_capacity")
POOL_MATERIAL_ATOL_FMOL = 2e-12
MAX_INITIAL_POOL_CHANGE_PER_STEP = 0.05
EXTRA_AXES = {
    "energy_amount_increment_fmol": ["energy_species", "cell_slot"],
    "regeneration_cycles_fmol": ["regeneration_slot"],
    "regeneration_dissipated_energy_pJ": ["regeneration_slot"],
    "regeneration_supplied_work_pJ": ["regeneration_slot"],
}
STATE_AXES = prior.STATE_AXES | EXTRA_AXES
STATE_TYPE = NamedTuple("SurfaceCalciumEnergyState", [(k, object) for k in STATE_AXES])
LAYOUT_TYPE = NamedTuple(
    "SurfaceCalciumEnergyLayout",
    [
        (k, object)
        for k in (
            *prior.LAYOUT_TYPE._fields,
            "energy_initial_amount_fmol",
            "energy_delta_g0_J_mol",
            "regeneration_active",
            "regeneration_owner",
            "regeneration_capacity_fmol_s",
            "regeneration_supplied_energy_J_mol",
        )
    ],
)
CATALOG_LAYOUT_TYPE = NamedTuple(
    "SurfaceCalciumEnergyCatalogLayout", [(k, object) for k in LAYOUT_TYPE._fields]
)
CALCIUM_ACTIVATED_LAYOUT_TYPE = NamedTuple(
    "SurfaceCalciumEnergyActivatedLayout",
    [(k, object) for k in (*LAYOUT_TYPE._fields, "channel_calcium_species")],
)
MORRIS_LECAR_LAYOUT_TYPE = NamedTuple(
    "SurfaceCalciumEnergyMorrisLecarLayout",
    [(k, object) for k in CALCIUM_ACTIVATED_LAYOUT_TYPE._fields],
)
HCN_EXTRA_LAYOUT_TYPE = NamedTuple(
    "SurfaceCalciumEnergyHCNExtraLayout", [(k, object) for k in MORRIS_LECAR_LAYOUT_TYPE._fields]
)

READOUTS = (
    "energy_amount_fmol",
    "energy_concentration_mM",
    "energy_chemical_potential_J_mol",
    "energy_hydrolysis_free_energy_J_mol",
    "energy_free_energy_change_pJ",
    "adenylate_fmol",
    "phosphorus_fmol",
    "regeneration_cycle_rate_fmol_s",
    "regeneration_affinity_J_mol",
    "regeneration_power_pJ_s",
    "regeneration_dissipation_pJ_s",
    "regeneration_availability",
    "energy_balance_pJ",
    "pool_internal_transfer_balance_pJ",
)
OBSERVATION_FIELDS = (*prior.OBSERVATION_FIELDS, *EXTRA_AXES, *READOUTS)
Observations = make_dataclass(
    "SurfaceCalciumEnergyObservations", [(k, np.ndarray) for k in OBSERVATION_FIELDS], frozen=True
)
parameters = prior.parameters
physical_amounts = prior.physical_amounts
cytosol_amount = prior.cytosol_amount
er = prior.er
store_layout = prior.store_layout
store_state = prior.store_state
ip3_readouts = prior.ip3_readouts
ENERGY_ATOL_PJ = prior.ENERGY_ATOL_PJ


class Values(NamedTuple):
    field: object
    derivative: object
    kinetic: object
    energy: object
    regeneration: object
    exchange: object
    valid: object


def prior_state(state):
    return prior.STATE_TYPE(*(getattr(state, k) for k in prior.STATE_TYPE._fields))


def prior_layout(layout):
    cls = (
        HCN_EXTRA_PRIOR_LAYOUT
        if isinstance(layout, HCN_EXTRA_LAYOUT_TYPE)
        else MORRIS_LECAR_PRIOR_LAYOUT
        if isinstance(layout, MORRIS_LECAR_LAYOUT_TYPE)
        else CALCIUM_ACTIVATED_PRIOR_LAYOUT
        if isinstance(layout, CALCIUM_ACTIVATED_LAYOUT_TYPE)
        else CALCIUM_CATALOG_LAYOUT_TYPE
        if isinstance(layout, CATALOG_LAYOUT_TYPE)
        else prior.LAYOUT_TYPE
    )
    return cls(*(getattr(layout, k) for k in cls._fields))


def prior_control(control):
    from cells.core.schedule import SurfaceCalciumControl

    return SurfaceCalciumControl(*(getattr(control, k) for k in SurfaceCalciumControl._fields))


def batch_signature(model):
    return (
        *prior.batch_signature(model),
        tuple((p.id, p.cell_id) for p in model.energy_pools),
        tuple((p.id, p.pool_id) for p in model.regeneration_ports),
    )


def working_size(spec):
    return prior.working_size(spec) + 256 * (
        spec.execution.capacity + spec.execution.regeneration_capacity
    )


def pool_parameters(p, *, xp=np):
    return energy.Parameters(
        xp.where(p.active, p.temperature, 298.15), p.energy_delta_g0_J_mol, p.active
    )


def pump_routes(p, *, xp=np):
    """Each computed signed cycle appears once, in NaK/PMCA/ER order."""
    return energy.Routes(
        xp.concatenate((p.membrane_cell, p.membrane_cell, xp.arange(p.er_pump_present.size))),
        xp.concatenate((p.pump_present, p.pmca_present, p.er_pump_present)),
    )


def pump_cycles(state, *, xp=np):
    return xp.concatenate(
        (state.pump_cycles, state.plasma_pump_cycles, state.er_pump_transferred[..., 0]), axis=-1
    )


def regeneration_routes(p):
    return energy.Routes(p.regeneration_owner, p.regeneration_active)


def regeneration_parameters(p):
    return energy.RegenerationParameters(
        p.regeneration_capacity_fmol_s, p.regeneration_supplied_energy_J_mol
    )


def energy_amounts(state, p):
    return p.energy_initial_amount_fmol + state.energy_amount_increment_fmol


def initial_values(spec):
    state, p = prior.initial_values(initial_prior_spec(spec))
    n, r = spec.execution.capacity, spec.execution.regeneration_capacity
    values = p._asdict() | dict(
        energy_initial_amount_fmol=np.zeros((3, n)),
        energy_delta_g0_J_mol=np.zeros(n),
        regeneration_active=np.arange(r) < len(spec.model.regeneration_ports),
        regeneration_owner=np.zeros(r, dtype=np.int64),
        regeneration_capacity_fmol_s=np.zeros(r),
        regeneration_supplied_energy_J_mol=np.zeros(r),
    )
    owners = {cell.id: i for i, cell in enumerate(spec.model.cells)}
    pools = {}
    for pool in spec.model.energy_pools:
        i = owners[pool.cell_id]
        pools[pool.id] = i
        values["energy_initial_amount_fmol"][:, i] = pool.initial_amount_fmol
        values["energy_delta_g0_J_mol"][i] = pool.delta_g0_J_per_mol
    for i, port in enumerate(spec.model.regeneration_ports):
        values["regeneration_owner"][i] = pools[port.pool_id]
        values["regeneration_capacity_fmol_s"][i] = port.capacity_fmol_per_s
        values["regeneration_supplied_energy_J_mol"][i] = port.supplied_energy_J_per_mol
    cls = (
        HCN_EXTRA_LAYOUT_TYPE
        if isinstance(spec.model, SurfaceCalciumEnergyHCNExtraModel)
        else MORRIS_LECAR_LAYOUT_TYPE
        if isinstance(spec.model, SurfaceCalciumEnergyMorrisLecarModel)
        else CALCIUM_ACTIVATED_LAYOUT_TYPE
        if isinstance(spec.model, SurfaceCalciumEnergyActivatedModel)
        else CATALOG_LAYOUT_TYPE
        if isinstance(spec.model, SurfaceCalciumEnergyCatalogModel)
        else LAYOUT_TYPE
    )
    layout = cls(**values)
    energy.validate_parameters(pool_parameters(layout))
    energy.validate_routes(pump_routes(layout), pool_parameters(layout))
    energy.validate_routes(regeneration_routes(layout), pool_parameters(layout))
    return STATE_TYPE(*state, np.zeros((3, n)), np.zeros(r), np.zeros(r), np.zeros(r)), layout


def stage_layout(state, p, *, xp=jnp):
    """All three pump families read the same live owner pool at every stage."""
    original = prior_layout(p)
    current = energy.pump_parameters(
        energy_amounts(state, p),
        p.volume,
        pool_parameters(p, xp=xp),
        energy.Routes(p.membrane_cell, p.pump_present),
        pump_layout.pump_parameters(original),
        xp=xp,
    )
    values = dict(
        pump_capacity=current.capacity_fmol_s,
        pump_drive=pump.chemical_drive(current, p.temperature, xp=xp),
        **{"pump_" + key: getattr(current, key) for key in pump.Parameters._fields[1:]},
    )
    for prefix, owner, present, names in (
        (
            "pmca_",
            p.membrane_cell,
            p.pmca_present,
            ("capacity", "km_ca", "km_atp", "atp", "adp", "pi", "dg"),
        ),
        (
            "er_pump_",
            xp.arange(p.er_pump_present.size),
            p.er_pump_present,
            ("capacity", "km_ca", "km_atp", "atp", "adp", "pi", "dg0"),
        ),
    ):
        current = calcium.pump_parameters(
            energy_amounts(state, p),
            p.volume,
            pool_parameters(p, xp=xp),
            energy.Routes(owner, present),
            calcium.PumpParameters(*(getattr(p, prefix + key) for key in names[:3])),
            xp=xp,
        )
        values.update(zip((prefix + key for key in names), current, strict=True))
    return original._replace(**values)


def readouts(state, control, p, *, xp=jnp):
    current = stage_layout(state, p, xp=xp)
    ionic = prior.readouts(prior_state(state), prior_control(control), current, xp=xp)
    return complete_calcium_stage(state, control, p, ionic, xp=xp)


def complete_calcium_stage(state, control, p, ionic, *, xp=jnp):
    """Finish the original finite-pool readout after its calcium/ER calculation.

    The caller retains the same full state, control and projected fuel layout.
    The calcium result must use that state's live pool-derived pump layout.
    This boundary neither advances time nor changes any material/energy owner.
    """
    params = pool_parameters(p, xp=xp)
    amount = energy_amounts(state, p)
    pools = energy.thermodynamics(amount, p.volume, params, xp=xp)
    regeneration = energy.regeneration_rates(
        amount,
        p.volume,
        params,
        regeneration_routes(p),
        regeneration_parameters(p),
        control.regeneration,
        xp=xp,
    )
    exchange = energy.exchange_rates(
        pump_cycles(ionic.derivative, xp=xp),
        pump_routes(p, xp=xp),
        regeneration.synthesis_fmol_s,
        regeneration_routes(p),
        params,
        xp=xp,
    )
    derivative = STATE_TYPE(
        *ionic.derivative,
        exchange.amount_fmol_s,
        regeneration.synthesis_fmol_s,
        regeneration.dissipated_power_pJ_s,
        regeneration.supplied_power_pJ_s,
    )
    chemical = xp.sum(energy.chemical_power_pJ_s(exchange.amount_fmol_s, pools, xp=xp))
    v = ionic.field
    dissipation = v.dissipation_pJ_s + xp.sum(regeneration.dissipated_power_pJ_s)
    balance = (
        v.chemical_energy_rate_pJ_s
        + v.capacitor_energy_rate_pJ_s
        + chemical
        + dissipation
        - v.reservoir_power_pJ_s
        - v.electrode_power_pJ_s
        - xp.sum(regeneration.supplied_power_pJ_s)
    )
    valid = ionic.valid & domain_valid(state, p, p.active, xp=xp)
    valid &= energy.regeneration_domain_valid(
        amount,
        p.volume,
        params,
        regeneration_routes(p),
        regeneration_parameters(p),
        control.regeneration,
        xp=xp,
    )
    valid &= energy.exchange_domain_valid(
        pump_cycles(ionic.derivative, xp=xp),
        pump_routes(p, xp=xp),
        regeneration.synthesis_fmol_s,
        regeneration_routes(p),
        params,
        xp=xp,
    )
    for value in (*derivative, chemical, dissipation, balance):
        valid &= xp.all(xp.isfinite(value))
    v = v._replace(
        dissipation_pJ_s=dissipation,
        energy_balance_pJ_s=balance,
        converged=valid,
        rates=v.rates._replace(valid=valid),
    )
    return Values(v, derivative, ionic, pools, regeneration, exchange, valid)


def rhs(state, control, p, active, *, xp=jnp):
    result = readouts(state, control, p, xp=xp)
    return STATE_TYPE(*(xp.where(result.valid, value, xp.nan) for value in result.derivative))


def field_values(state, control, p, *, xp=jnp):
    return readouts(state, control, p, xp=xp).field


def domain_valid(state, p, active, *, xp=jnp):
    valid = energy.domain_valid(
        energy_amounts(state, p), p.volume, pool_parameters(p, xp=xp), xp=xp
    )
    valid &= xp.all(xp.isfinite(state.energy_amount_increment_fmol))
    valid &= xp.all(xp.where(p.active, True, state.energy_amount_increment_fmol == 0))
    supported = p.regeneration_active & (p.regeneration_capacity_fmol_s > 0)
    for key in tuple(EXTRA_AXES)[1:]:
        value = getattr(state, key)
        valid &= xp.all(xp.isfinite(value)) & xp.all(xp.where(supported, True, value == 0))
    # ER affinity depends on current fuel even when its pump is blocked.
    # Check the strict pool interior before logs or any physical stage solve.
    if xp is np:
        return np.asarray(
            bool(valid)
            and prior.domain_valid(prior_state(state), stage_layout(state, p, xp=np), active, xp=np)
        )
    return jax.lax.cond(
        valid,
        lambda: prior.domain_valid(prior_state(state), stage_layout(state, p), active),
        lambda: jnp.asarray(False),
    )


def control_domain_valid(state, control, p, active, *, xp=jnp):
    valid = domain_valid(state, p, active, xp=xp)
    if xp is np:
        if not valid:
            return np.asarray(False)
        try:
            return readouts(state, control, p, xp=np).valid
        except np.linalg.LinAlgError:
            return np.asarray(False)
    return jax.lax.cond(
        valid, lambda: readouts(state, control, p).valid, lambda: jnp.asarray(False)
    )


domain_valid.with_control = control_domain_valid


def check_definition(spec):
    m = spec.model
    compact = replace(
        spec,
        execution=replace(
            spec.execution,
            capacity=len(m.cells),
            extracellular_capacity=len(m.extracellular),
            membrane_capacity=len(m.membranes),
            edge_capacity=len(m.junctions),
            face_capacity=len(m.faces),
            channel_capacity=len(m.channels),
            regeneration_capacity=len(m.regeneration_ports),
        ),
    )
    state, p = initial_values(compact)
    from cells.core.schedule import control_values

    table = control_values(compact, [c.time for c in compact.experiment.changes])
    with np.errstate(all="ignore"):
        for i in range(len(compact.experiment.changes)):
            if not control_domain_valid(
                state, type(table)(*(v[i] for v in table)), p, p.active, xp=np
            ):
                raise ConfigError(
                    "Initial finite-energy/ionic state or actual control outside domain"
                )


def bounded_prior_spec(spec):
    """Auxiliary loss-bound coefficients, NOT a realizable maintained state.

    Adenylate A=ATP+ADP and phosphorus P=3ATP+2ADP+Pi are conserved per owner.
    ATP,ADP <= A and Pi <= P. For each calcium pump the reverse saturation
    cancels ATP exactly: ADP*Pi/(KmATP+ATP). Choosing ATP=A and
    Pi=P*(KmATP+A)/KmATP majorizes both forward and reverse coefficients.
    The unchanged calcium loss-bound code then also retains all chemistry,
    NCX, passive transport, voltage-domain and free-calcium pool bounds.
    """
    projected = initial_prior_spec(spec)
    upper = {}
    for cell, pool in zip(spec.model.cells, spec.model.energy_pools, strict=True):
        a, d, pi = pool.initial_amount_fmol
        upper[cell.id] = ((a + d) / cell.volume_pL, (3 * a + 2 * d + pi) / cell.volume_pL)

    def bounded(pump, owner):
        if pump is None:
            return None
        a, phosphorus = upper[owner]
        return replace(
            pump, atp_mM=a, adp_mM=a, pi_mM=phosphorus * (pump.km_atp_mM + a) / pump.km_atp_mM
        )

    m = projected.model
    owners = {patch.id: patch.inside for patch in m.membranes}
    return replace(
        projected,
        experiment=spec.experiment,
        model=replace(
            m,
            stores=tuple(
                replace(s, membrane=replace(s.membrane, pump=bounded(s.membrane.pump, c.id)))
                for c, s in zip(m.cells, m.stores, strict=True)
            ),
            plasma_routes=tuple(
                replace(p, pump=bounded(p.pump, owners[p.membrane_id])) for p in m.plasma_routes
            ),
        ),
    )


def check_steps(spec, steps, controls):
    # Full merged clock, inherited gate ceilings, and a calcium loss bound that
    # remains conservative as finite fuel changes (not just at its initial value).
    prior.check_steps(bounded_prior_spec(spec), steps, controls)
    state, p = initial_values(spec)
    amount = np.where(p.active, energy_amounts(state, p), 1.0)
    from cells.core.schedule import control_values

    table = control_values(spec, [c.time for c in spec.experiment.changes])
    for i in range(len(spec.experiment.changes)):
        value = readouts(state, type(table)(*(v[i] for v in table)), p, xp=np)
        gross = value.exchange.gross_hydrolysis_fmol_s + value.exchange.gross_synthesis_fmol_s
        fractional = np.max(np.where(p.active, gross / np.min(amount, axis=0), 0.0), initial=0)
        if (
            not np.isfinite(fractional)
            or np.max(steps, initial=0) * fractional > MAX_INITIAL_POOL_CHANGE_PER_STEP
        ):
            raise ConfigError("Finite-energy initial gross turnover requires a smaller RK4 step")


def pool_free_energy_change_pJ(state, p):
    """Stable fixed-volume change, preserving small stored amount increments."""
    anchor = np.where(p.active, p.energy_initial_amount_fmol, 1.0)
    delta = np.asarray(state.energy_amount_increment_fmol)
    mixing = delta * (np.log(anchor / p.volume / energy.STANDARD_STATE_mM) - 1)
    mixing += (anchor + delta) * np.log1p(delta / anchor)
    return 1e-3 * (R * p.temperature * np.sum(mixing, axis=0) - p.energy_delta_g0_J_mol * delta[0])


def balances(state, p):
    qp = prior_layout(p)
    result = prior.balances(prior_state(state), qp)
    # Live chemical drive invalidates the old constant-drive*cycles identities.
    for key in ("metabolic_work", "plasma_metabolic_work", "er_metabolic_work"):
        result.pop(key)
    free = pool_free_energy_change_pJ(state, p)
    work = np.concatenate(
        (state.metabolic_work_pJ, state.plasma_metabolic_work_pJ, state.er_metabolic_work_pJ)
    )
    result["energy"] += (
        np.sum(work)
        + np.sum(free)
        + np.sum(state.regeneration_dissipated_energy_pJ)
        - np.sum(state.regeneration_supplied_work_pJ)
    )
    material = energy.material_balances(
        p.energy_initial_amount_fmol,
        energy_amounts(state, p),
        pump_cycles(state),
        pump_routes(p),
        state.regeneration_cycles_fmol,
        regeneration_routes(p),
        pool_parameters(p),
        xp=np,
    )
    result.update(
        pool_material=material.amount_residual_fmol,
        adenylate=material.adenylate_residual_fmol,
        phosphorus=material.phosphorus_residual_fmol,
    )
    transferred = ordered_scatter(work, np.zeros_like(p.volume), (pump_routes(p).owner,), xp=np)
    port = ordered_scatter(
        state.regeneration_dissipated_energy_pJ - state.regeneration_supplied_work_pJ,
        np.zeros_like(p.volume),
        (p.regeneration_owner,),
        xp=np,
    )
    result["pool_energy"] = free + transferred + port
    result["regeneration_work"] = (
        state.regeneration_supplied_work_pJ
        - 1e-3 * p.regeneration_supplied_energy_J_mol * state.regeneration_cycles_fmol
    )
    return result


def check_values(state, spec):
    _, p = initial_values(spec)
    rows = (
        [state]
        if state.amount_increment.ndim == 2
        else [
            STATE_TYPE(*(value[i] for value in state)) for i in range(len(state.amount_increment))
        ]
    )
    diagnostics = {}
    with np.errstate(all="ignore"):
        for row in rows:
            if not domain_valid(row, p, p.active, xp=np):
                raise NumericalError("Invalid finite-energy/calcium state, exhaustion or padding")
            current = balances(row, p)
            tolerance = np.asarray(spec.execution.material_balance_atol_fmol)
            charge = np.r_[p.initial_cell_charge_C, p.initial_outside_charge_C]
            charge += passive.charge_increment(row, p, xp=np)
            limits = dict(
                local=tolerance[:, None],
                outside=tolerance[:, None],
                total=tolerance,
                charge=field.CHARGE_ATOL_C + field.CHARGE_RTOL * np.abs(charge),
                electrode=field.CHARGE_ATOL_C,
                global_charge=3e-25,
                energy=ENERGY_ATOL_PJ,
                reservoir_work=3e-12,
                electrode_work=3e-12,
                chemical_ledger=chemistry.ROUND_ATOL,
                ownership=chemistry.ROUND_ATOL,
                pool_material=POOL_MATERIAL_ATOL_FMOL,
                adenylate=POOL_MATERIAL_ATOL_FMOL,
                phosphorus=POOL_MATERIAL_ATOL_FMOL,
                pool_energy=ENERGY_ATOL_PJ,
                regeneration_work=3e-12,
            )
            for key, value in current.items():
                if not np.isfinite(value).all() or np.any(np.abs(value) > limits[key]):
                    raise NumericalError("Finite-energy/calcium accounting failed: " + key)
                name = "max_" + key + "_error"
                diagnostics[name] = max(
                    diagnostics.get(name, 0.0), float(np.max(np.abs(value), initial=0))
                )
    for key in (name for name in STATE_AXES if name.endswith("_dissipated_energy_pJ")):
        value = getattr(state, key)
        if np.min(value, initial=0) < -1e-12 or (
            state.amount_increment.ndim == 3 and np.min(np.diff(value, axis=0), initial=0) < -1e-12
        ):
            raise NumericalError("Finite-energy dissipation cannot be negative or decrease")
    return diagnostics


def observe_history(times, history, layout, requested, spec):
    from cells.core.schedule import control_values

    p = type(layout)(*(np.asarray(v) for v in layout))
    requested = np.asarray(requested, dtype=float)
    if any(t not in times for t in requested):
        raise ConfigError("Finite-energy observations require accepted integration boundaries")
    controls = control_values(spec, requested)
    records = []
    for j, time in enumerate(requested):
        i = int(np.flatnonzero(times == time)[0])
        state = STATE_TYPE(*(v[i] for v in history))
        control = type(controls)(*(v[j] for v in controls))
        value = readouts(state, control, p, xp=np)
        if not value.valid:
            raise NumericalError("Invalid finite-energy observation state/control")
        observed = prior.observe_history(
            np.asarray([time]),
            prior.STATE_TYPE(*(np.asarray([v]) for v in prior_state(state))),
            stage_layout(state, p, xp=np),
            np.asarray([time]),
            initial_prior_spec(spec),
        )
        row = {key: v[0] for key, v in vars(observed).items()}
        row.update({key: getattr(state, key) for key in EXTRA_AXES})
        conserved = energy.invariants(energy_amounts(state, p), xp=np)
        balance = balances(state, p)
        row.update(
            energy_amount_fmol=energy_amounts(state, p),
            energy_concentration_mM=value.energy.concentration_mM,
            energy_chemical_potential_J_mol=value.energy.chemical_potential_J_mol,
            energy_hydrolysis_free_energy_J_mol=value.energy.hydrolysis_free_energy_J_mol,
            energy_free_energy_change_pJ=pool_free_energy_change_pJ(state, p),
            adenylate_fmol=conserved.adenylate_fmol,
            phosphorus_fmol=conserved.phosphorus_fmol,
            regeneration_cycle_rate_fmol_s=value.regeneration.synthesis_fmol_s,
            regeneration_affinity_J_mol=value.regeneration.reaction_free_energy_J_mol,
            regeneration_power_pJ_s=value.regeneration.supplied_power_pJ_s,
            regeneration_dissipation_pJ_s=value.regeneration.dissipated_power_pJ_s,
            regeneration_availability=control.regeneration,
            energy_balance_pJ=np.atleast_1d(balance["energy"]),
            pool_internal_transfer_balance_pJ=balance["pool_energy"],
            energy_balance_pJ_s=np.atleast_1d(value.field.energy_balance_pJ_s),
        )
        records.append(tuple(row[key] for key in OBSERVATION_FIELDS))
    if records:
        return Observations(*(np.stack(v) for v in zip(*records, strict=True)))
    sample = observe_history(times[:1], STATE_TYPE(*(v[:1] for v in history)), p, times[:1], spec)
    return Observations(
        *(np.empty((0, *v.shape[1:]), dtype=v.dtype) for v in vars(sample).values())
    )


def ensemble_voltage(state, layout, spec, time):
    from cells.core.schedule import control_values

    table = control_values(spec, [time])
    control = type(table)(*(v[0] for v in table))
    p = type(layout)(*(np.asarray(v) for v in layout))
    value = readouts(STATE_TYPE(*(np.asarray(v) for v in state)), control, p, xp=np)
    if not value.valid:
        raise NumericalError("Finite-energy ensemble endpoint outside domain")
    return value.field.rates.membrane_voltage_V[p.membrane_active]


def summarize(history, diagnostics, spec):
    return prior.summarize(prior_state(history), diagnostics, initial_prior_spec(spec)) | dict(
        model=model_id(spec.model),
        state_fields=list(STATE_TYPE._fields),
        energy_species=list(energy.SPECIES),
        energy_law=energy.LAW_ID,
        regeneration_law=energy.REGENERATION_LAW_ID,
        metabolic_work_role="Internal pump/pool transfer diagnostic, not external chemical supply",
        scope="Transformed finite energy with buffered pH/Mg/solvent; fixed geometry and volume",
    )
