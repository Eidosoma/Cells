"""Resolved plasma capacitors coupled to finite, cell-owned cytosol/ER chemistry.

External ionic exchange charges plasma capacitors. Free cytosolic ions alone
drive transport. Binding and ER exchange alter the chemical store, never a
second copy of the plasma inventory. Every process has a saved transfer and
dissipation ledger; maintained ATP reservoirs have separate work ledgers.
"""

from dataclasses import make_dataclass
from typing import NamedTuple

import jax
import jax.numpy as jnp
import numpy as np

from cells.core.errors import NumericalError
from cells.core.specs import ConfigError
from cells.core.surface_calcium_spec import (
    MODEL_ID,  # noqa: F401 - public model identity used by ordinary execution
    SurfaceCalciumCavModel,
    SurfaceCalciumChannelModel,
    SurfaceCalciumHCNModel,
    SurfaceCalciumKv1Model,
    SurfaceCalciumSodiumModel,
    ionic_spec,
    model_id,
    store_spec,
)
from cells.coupling.selective import selective_flux
from cells.models import compartment_reactions as chemistry
from cells.models import er_calcium as er
from cells.models import ip3_calcium as ip3
from cells.models import plasma_calcium as plasma
from cells.models import spatial_calcium as owned
from cells.models import surface_kinetic as kinetic
from cells.models import surface_tissue as base
from cells.numerics import surface_field as field
from cells.numerics.extracellular_field import scatter
from cells.processes import calcium_gates as gates
from cells.processes import plasma_calcium as process
from cells.processes.electrochemistry import CHARGE_PER_FMOL, F, R

STATE_AXES = (
    kinetic.STATE_AXES
    | {
        new: ["owned_cell", *er.STATE_AXES[old]]
        for new, old in zip(owned.ER_FIELDS, er.State._fields, strict=True)
    }
    | {
        "plasma_pump_cycles": ["membrane_slot"],
        "plasma_exchange_cycles": ["membrane_slot"],
        "plasma_dissipated_energy_pJ": ["plasma_route", "membrane_slot"],
        "calcium_gate": ["gate", "membrane_slot"],
        "calcium_channel_transferred": ["membrane_slot"],
        "calcium_channel_dissipated_energy_pJ": ["membrane_slot"],
        "plasma_metabolic_work_pJ": ["membrane_slot"],
        "er_metabolic_work_pJ": ["owned_cell"],
    }
)
STATE_TYPE = NamedTuple("SurfaceCalciumState", [(k, object) for k in STATE_AXES])
LAYOUT_TYPE = NamedTuple(
    "SurfaceCalciumLayout",
    [
        (k, object)
        for k in (
            *kinetic.LAYOUT_TYPE._fields,
            *("er_" + k for k in er.Layout._fields),
            "ionic_species",
            "ion_content",
            "cytosol_selector",
            "free_ion_selector",
            "nonionic_moieties",
            "chemical_fixed_charge_C",
            *plasma.LAYOUT_FIELDS,
            "cav_permeability",
            "cav_abundance",
            "ip3_weights",
            "ip3_activation",
            "ip3_power",
        )
    ],
)
IonicView = NamedTuple(
    "IonicView", [(k, object) for k in (*kinetic.LAYOUT_TYPE._fields, "cytosol_amount")]
)
CHANNEL_LAYOUT_TYPE = NamedTuple(
    "SurfaceCalciumChannelLayout", [(k, object) for k in (*LAYOUT_TYPE._fields, "channel_laws")]
)
SODIUM_LAYOUT_TYPE = NamedTuple(
    "SurfaceCalciumSodiumLayout", [(k, object) for k in CHANNEL_LAYOUT_TYPE._fields]
)
HCN_LAYOUT_TYPE = NamedTuple(
    "SurfaceCalciumHCNLayout",
    [
        (k, object)
        for k in (*SODIUM_LAYOUT_TYPE._fields, "channel_relative_permeability")
        if k != "channel_species"
    ],
)
KV1_LAYOUT_TYPE = NamedTuple(
    "SurfaceCalciumKv1Layout", [(k, object) for k in HCN_LAYOUT_TYPE._fields]
)
CAV_LAYOUT_TYPE = NamedTuple(
    "SurfaceCalciumCavLayout", [(k, object) for k in HCN_LAYOUT_TYPE._fields]
)
HCN_STATE_AXES = STATE_AXES | {
    "channel_transferred": ["species", "channel_slot"],
    "channel_dissipated_energy_pJ": ["species", "channel_slot"],
}
ChannelIonicView = NamedTuple(
    "ChannelIonicView", [(k, object) for k in (*IonicView._fields, "channel_laws")]
)
BATCH_CAPACITIES = (*kinetic.BATCH_CAPACITIES, "chemical_capacity", "reaction_capacity")
OBSERVER_ID = "resolved_owned_calcium_ip3_accepted_grid@1"
OBSERVATION_SAMPLING = base.OBSERVATION_SAMPLING
STAGE_DOMAIN_ID = "resolved_free_cytosol_er_ip3_actual_controls@1"
ENERGY_ATOL_PJ = 1e-9
parameters = kinetic.parameters
store_state, store_layout, store_control = (
    owned.store_state,
    owned.store_layout,
    owned.store_control,
)
cytosol_amount, ownership_residual, ip3_readouts = (
    owned.cytosol_amount,
    owned.ownership_residual,
    ip3.ip3_readouts,
)


def batch_signature(model):
    return (
        kinetic.batch_signature(model),
        tuple(chemistry.batch_signature(s) for s in model.stores),
        model.calcium_species,
        model.sodium_species,
    )


def working_size(spec):
    return (
        kinetic.working_size(ionic_spec(spec))
        + sum(er.working_size(store_spec(spec, i)) for i in range(len(spec.model.stores)))
        + 4096 * spec.execution.membrane_capacity
    )


def initial_values(spec):
    state, p = kinetic.initial_values(ionic_spec(spec))
    pairs = [er.initial_values(store_spec(spec, i)) for i in range(len(spec.model.stores))]
    states = [np.stack([s[j] for s, _ in pairs]) for j in range(len(er.State._fields))]
    v = p._asdict() | {
        "er_" + k: np.stack([getattr(q, k) for _, q in pairs]) for k in er.Layout._fields
    }
    m = spec.model
    chemical = m.stores[0]
    nm = spec.execution.membrane_capacity
    names = [s.id for s in chemical.species]
    indices = np.array([names.index(k) for k in m.species_ids])
    cy = np.zeros((len(pairs), spec.execution.chemical_capacity))
    for i, (_, q) in enumerate(pairs):
        cy[i, q.cytosol] = 1
    v.update(
        ionic_species=indices,
        ion_content=np.array(
            [
                [s.moieties[chemical.moieties.index(k)] for s in chemical.species]
                for k in m.species_ids
            ],
            dtype=float,
        ),
        cytosol_selector=cy,
        free_ion_selector=np.eye(len(names))[:, indices],
        nonionic_moieties=np.array([k not in m.species_ids for k in chemical.moieties]),
    )
    # ER backgrounds establish its own capacitor charge. The cytosol also owns
    # the declared whole-cell plasma charge; nonionic charged buffers must not
    # be silently counted again in the plasma charge anchor.
    v["chemical_fixed_charge_C"] = (
        v["er_fixed_charge_C"] + p.initial_cell_charge_C[: len(pairs), None] * cy
    )
    ca, na = m.species_ids.index(m.calcium_species), m.species_ids.index(m.sodium_species)
    v.update(
        plasma_ca=np.int32(ca),
        plasma_na=np.int32(na),
        plasma_ca_selector=np.eye(len(m.species_ids))[ca, :, None],
        plasma_na_selector=np.eye(len(m.species_ids))[na, :, None],
    )
    v.update({k: np.ones(nm) for k in plasma.LAYOUT_FIELDS[4:]})
    for k in ("pmca_present", "ncx_present"):
        v[k] = np.zeros(nm, dtype=bool)
    for k in ("pmca_capacity", "pmca_dg", "ncx_capacity"):
        v[k] = np.zeros(nm)
    for i, route in enumerate(m.plasma_routes):
        if route.pump is not None:
            v["pmca_present"][i] = True
            for k, f in (
                ("capacity", "capacity_fmol_per_s"),
                ("km_ca", "km_ca_mM"),
                ("km_atp", "km_atp_mM"),
                ("atp", "atp_mM"),
                ("adp", "adp_mM"),
                ("pi", "pi_mM"),
                ("dg", "delta_g0_J_per_mol"),
            ):
                v["pmca_" + k][i] = getattr(route.pump, f)
        if route.exchanger is not None:
            v["ncx_present"][i] = True
            for k, f in (
                ("capacity", "capacity_fmol_per_s"),
                ("km_ca", "km_ca_mM"),
                ("km_na", "km_na_mM"),
            ):
                v["ncx_" + k][i] = getattr(route.exchanger, f)
    gate = np.zeros((2, nm))
    v.update(cav_permeability=np.zeros(nm), cav_abundance=np.zeros(nm))
    for i, c in enumerate(m.calcium_channels):
        gate[:, i] = c.initial_gate
        v["cav_permeability"][i] = c.max_permeability_m_per_s
        v["cav_abundance"][i] = c.abundance
    weights = np.zeros_like(v["er_initial_amount"])
    for i, b in enumerate(m.ip3_release):
        q = pairs[i][1]
        weights[i, names.index(b.species_id), q.cytosol] = 1 / q.volume[q.cytosol]
    v.update(
        ip3_weights=weights,
        ip3_activation=np.array([b.activation_mM for b in m.ip3_release]),
        ip3_power=np.array([b.activation_n for b in m.ip3_release], dtype=float),
    )
    layout_type = (
        CAV_LAYOUT_TYPE
        if isinstance(m, SurfaceCalciumCavModel)
        else KV1_LAYOUT_TYPE
        if isinstance(m, SurfaceCalciumKv1Model)
        else HCN_LAYOUT_TYPE
        if isinstance(m, SurfaceCalciumHCNModel)
        else SODIUM_LAYOUT_TYPE
        if isinstance(m, SurfaceCalciumSodiumModel)
        else CHANNEL_LAYOUT_TYPE
        if isinstance(m, SurfaceCalciumChannelModel)
        else LAYOUT_TYPE
    )
    return STATE_TYPE(
        *state,
        *states,
        np.zeros(nm),
        np.zeros(nm),
        np.zeros((2, nm)),
        gate,
        np.zeros(nm),
        np.zeros(nm),
        np.zeros(nm),
        np.zeros(len(pairs)),
    ), layout_type(**v)


def ionic_state(state):
    return kinetic.STATE_TYPE(*(getattr(state, k) for k in kinetic.STATE_TYPE._fields))


def ionic_layout(state, p, *, xp=jnp):
    if isinstance(p, (HCN_LAYOUT_TYPE, KV1_LAYOUT_TYPE, CAV_LAYOUT_TYPE)):
        view = (
            kinetic.CAV_OWNED_VIEW_TYPE
            if isinstance(p, CAV_LAYOUT_TYPE)
            else kinetic.KV1_OWNED_VIEW_TYPE
            if isinstance(p, KV1_LAYOUT_TYPE)
            else kinetic.HCN_OWNED_VIEW_TYPE
        )
        return view(
            **{k: getattr(p, k) for k in kinetic.HCN_LAYOUT_TYPE._fields},
            cytosol_amount=cytosol_amount(state, p, xp=xp),
        )
    values = {k: getattr(p, k) for k in kinetic.LAYOUT_TYPE._fields}
    values["cytosol_amount"] = cytosol_amount(state, p, xp=xp)
    if isinstance(p, SODIUM_LAYOUT_TYPE):
        return kinetic.SODIUM_OWNED_VIEW_TYPE(**values, channel_laws=p.channel_laws)
    if hasattr(p, "channel_laws"):
        return ChannelIonicView(**values, channel_laws=p.channel_laws)
    return IonicView(**values)


def physical_amounts(state, p):
    return cytosol_amount(
        state, p, xp=np
    ), p.extracellular_amount_reference + state.extracellular_amount_increment


class Values(NamedTuple):
    field: object
    derivative: object
    ip3_cytosol_mM: object
    ip3_release_fraction: object
    er_voltage_V: object
    calcium_targets: object
    calcium_tau_s: object
    plasma_affinity_J_mol: object
    valid: object


def readouts(state, control, p, *, xp=jnp):
    from cells.core.schedule import SurfaceKineticControl

    view = ionic_layout(state, p, xp=xp)
    prior = kinetic.readouts(ionic_state(state), SurfaceKineticControl(*control[:4]), view, xp=xp)
    v, r = prior.field, prior.field.rates
    ci = xp.where(p.active, view.cytosol_amount / p.volume, 1.0)
    co = xp.where(
        p.outside_active,
        (p.extracellular_amount_reference + state.extracellular_amount_increment)
        / p.extracellular_volume,
        1.0,
    )
    a, b = p.membrane_cell, p.membrane_outside
    vm = r.membrane_voltage_V
    calcium_i, calcium_o = ci[p.plasma_ca, a], co[p.plasma_ca, b]
    pmca, gp, drive = process.pump_rates(
        calcium_i,
        calcium_o,
        vm,
        p.temperature,
        plasma.pump_parameters(p),
        control.plasma_pump,
        xp=xp,
    )
    ncx, gx = process.exchange_rates(
        ci[p.plasma_na, a],
        co[p.plasma_na, b],
        calcium_i,
        calcium_o,
        vm,
        p.temperature,
        process.ExchangerParameters(p.ncx_capacity, p.ncx_km_na, p.ncx_km_ca),
        control.plasma_exchange,
        xp=xp,
    )
    targets, tau = gates.kinetics(vm, xp=xp)
    gate_rate = xp.where(p.membrane_active, (targets - state.calcium_gate) / tau, 0.0)
    cav = selective_flux(
        calcium_i,
        calcium_o,
        vm,
        2,
        p.temperature,
        p.membrane_area,
        p.cav_permeability,
        0.0,
        p.cav_abundance,
        gates.open_probability(state.calcium_gate) * control.calcium_channel,
        xp=xp,
    )
    cav_d = 1e-3 * cav * r.membrane_delta_mu_J_mol[p.plasma_ca]
    plasma_d = -1e-3 * xp.stack((pmca * gp, ncx * gx))
    extra = p.plasma_ca_selector * (pmca + ncx + cav) - 3 * p.plasma_na_selector * ncx
    cell = r.cell_rate_fmol_s - scatter(extra, r.cell_rate_fmol_s, (a,), xp=xp)
    outside = r.outside_rate_fmol_s + scatter(extra, r.outside_rate_fmol_s, (b,), xp=xp)
    # This model admits finite exterior compartments only; there is no hidden
    # replenishment. Membrane transport is internal to each capacitor component.
    total_flux = r.membrane_flux_fmol_s + extra
    total_d = r.membrane_dissipation_pJ_s + xp.sum(plasma_d, axis=0) + cav_d
    n = p.active.size
    qdot = CHARGE_PER_FMOL * xp.sum(p.valence * xp.concatenate((cell, outside), axis=1), axis=0)
    dphi = field._capacitor_solve(qdot, xp.zeros_like(qdot), base.field_layout(p), xp=xp)
    dvm = xp.where(p.membrane_active, dphi[a] - dphi[n + b], 0.0)
    ip3_c, fraction = ip3_readouts(state, p, xp=xp)
    er_control = control._replace(er_release=control.er_release * fraction)
    stores, er_work, er_v = [], [], []
    chemical = 1e-3 * R * p.temperature * xp.sum(xp.log(co) * outside)
    er_electric = xp.asarray(0.0)
    for i in range(p.er_initial_amount.shape[0]):
        s, c = store_state(state, i), store_layout(p, i)
        dr = er.rhs(s, store_control(er_control, i), c, c.active, xp=xp)
        influx = p.free_ion_selector @ cell[:, i]
        dr = dr._replace(
            amount_increment=dr.amount_increment + influx[:, None] * p.cytosol_selector[i]
        )
        stores.append(dr)
        concentration = (c.initial_amount + s.amount_increment) / (
            c.volume * c.standard_concentration
        )
        chemical += (
            1e-3
            * R
            * c.temperature
            * xp.sum((c.standard_mu_RT[:, None] + xp.log(concentration)) * dr.amount_increment)
        )
        voltage = er.voltage(s, c, xp=xp)
        er_v.append(voltage)
        er_electric += (
            1e12 * voltage * CHARGE_PER_FMOL * xp.sum(c.valence * dr.amount_increment[:, c.er])
        )
        er_drive = er.processes.chemical_drive(er.pump_parameters(c), c.temperature, xp=xp)
        er_work.append(-1e-3 * er_drive * dr.pump_transferred[0])
    result = STATE_TYPE(
        *prior.derivative._replace(amount_increment=cell, extracellular_amount_increment=outside),
        *(xp.stack([s[j] for s in stores]) for j in range(len(er.State._fields))),
        pmca,
        ncx,
        plasma_d,
        gate_rate,
        cav,
        cav_d,
        -1e-3 * drive * pmca,
        xp.stack(er_work),
    )
    capacitor = 1e12 * xp.sum(p.membrane_capacitance * vm * dvm)
    dissipation = sum(
        xp.sum(getattr(result, k)) for k in STATE_AXES if k.endswith("_dissipated_energy_pJ")
    )
    work = (
        xp.sum(result.metabolic_work_pJ)
        + xp.sum(result.plasma_metabolic_work_pJ)
        + xp.sum(result.er_metabolic_work_pJ)
    )
    energy = chemical + capacitor + er_electric + dissipation - work
    valid = prior.valid & domain_valid(state, p, p.active, xp=xp)
    for value in control:
        valid &= xp.all(xp.isfinite(value) & (value >= 0) & (value <= 1))
    for aff, present in ((gp, p.pmca_present), (gx, p.ncx_present)):
        valid &= xp.all(
            xp.where(
                present,
                xp.isfinite(aff) & (xp.abs(aff / (R * p.temperature)) <= process.MAX_AFFINITY_RT),
                True,
            )
        )
    valid &= xp.all(
        xp.where(
            p.membrane_active,
            (vm >= gates.VOLTAGE_DOMAIN_V[0]) & (vm <= gates.VOLTAGE_DOMAIN_V[1]),
            True,
        )
    )
    for value in (*result, chemical, er_electric, energy):
        valid &= xp.all(xp.isfinite(value))
    r = r._replace(
        cell_rate_fmol_s=cell,
        outside_rate_fmol_s=outside,
        membrane_flux_fmol_s=total_flux,
        membrane_current_A=CHARGE_PER_FMOL * xp.sum(p.valence * total_flux, axis=0),
        membrane_dissipation_pJ_s=total_d,
        valid=valid,
    )
    v = v._replace(
        rates=r,
        membrane_voltage_rate_V_s=dvm,
        chemical_energy_rate_pJ_s=chemical,
        capacitor_energy_rate_pJ_s=capacitor + er_electric,
        dissipation_pJ_s=dissipation,
        energy_balance_pJ_s=energy,
        converged=valid,
    )
    return Values(
        v, result, ip3_c, fraction, xp.stack(er_v), targets, tau, xp.stack((gp, gx)), valid
    )


def field_values(state, control, p, *, xp=jnp):
    return readouts(state, control, p, xp=xp).field


def rhs(state, control, p, active, *, xp=jnp):
    w = readouts(state, control, p, xp=xp)
    return STATE_TYPE(*(xp.where(w.valid, v, xp.nan) for v in w.derivative))


def domain_valid(state, p, active, *, xp=jnp):
    valid = kinetic.domain_valid(ionic_state(state), ionic_layout(state, p, xp=xp), active, xp=xp)
    for i in range(p.er_initial_amount.shape[0]):
        s, c = store_state(state, i), store_layout(p, i)
        valid &= er.domain_valid(s, c, c.active, xp=xp)
        delta = xp.sum(s.amount_increment, axis=-1)
        moiety = c.moieties @ delta
        valid &= xp.all(xp.where(p.nonionic_moieties, xp.abs(moiety) <= chemistry.ROUND_ATOL, True))
        charge = CHARGE_PER_FMOL * (
            xp.sum(c.valence * delta) - xp.sum(p.valence[:, 0] * state.amount_increment[:, i])
        )
        valid &= xp.abs(charge) <= field.CHARGE_ATOL_C
    residue = ownership_residual(state, p, xp=xp)
    valid &= xp.all(xp.isfinite(residue) & (xp.abs(residue) <= chemistry.ROUND_ATOL))
    cav = p.membrane_active & (p.cav_permeability * p.cav_abundance > 0)
    masks = (
        p.pmca_present,
        p.ncx_present,
        xp.stack((p.pmca_present, p.ncx_present)),
        p.membrane_active,
        cav,
        cav,
        p.pmca_present,
        xp.ones_like(state.er_metabolic_work_pJ, dtype=bool),
    )
    for value, mask in zip(
        state[len(kinetic.STATE_TYPE._fields) + len(owned.ER_FIELDS) :], masks, strict=True
    ):
        valid &= xp.all(xp.isfinite(value)) & xp.all(xp.where(mask, True, value == 0))
    valid &= xp.all((state.calcium_gate >= 0) & (state.calcium_gate <= 1))
    valid &= xp.all(xp.where(p.pmca_capacity > 0, True, state.plasma_pump_cycles == 0))
    valid &= xp.all(xp.where(p.ncx_capacity > 0, True, state.plasma_exchange_cycles == 0))
    for k in STATE_AXES:
        if k.endswith("_dissipated_energy_pJ"):
            valid &= xp.all(getattr(state, k) >= -chemistry.ROUND_ATOL)
    return valid


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


def loss_bound(spec):
    # All chemical moiety bounds are conserved in this closed finite exterior.
    bound = chemical_loss_bound(spec)
    _, p = initial_values(spec)
    cy = np.zeros_like(p.amount_reference)
    out = np.zeros_like(p.extracellular_amount_reference)
    t = p.temperature
    vmax = process.MAX_VOLTAGE
    drive = process.chemical_drive(plasma.pump_parameters(p), t, xp=np)
    for i in np.flatnonzero(p.membrane_active):
        owner, other = p.membrane_cell[i], p.membrane_outside[i]
        pmca = (
            p.pmca_capacity[i]
            * p.pmca_atp[i]
            / (p.pmca_km_atp[i] + p.pmca_atp[i])
            / p.pmca_km_ca[i]
        )
        cy[p.plasma_ca, owner] += pmca / p.volume[owner]
        out[p.plasma_ca, other] += (
            pmca * np.exp((drive[i] + 2 * F * vmax) / (R * t)) / p.extracellular_volume[other]
        )
        ncx = p.ncx_capacity[i] * np.exp(F * vmax / (2 * R * t))
        cav = (
            p.membrane_area[i]
            * p.cav_permeability[i]
            * p.cav_abundance[i]
            / 1e-15
            * (1 + 2 * F * max(map(abs, gates.VOLTAGE_DOMAIN_V)) / (R * t))
        )
        for amounts, j, vol in (
            (cy, owner, p.volume[owner]),
            (out, other, p.extracellular_volume[other]),
        ):
            amounts[p.plasma_ca, j] += (ncx / p.ncx_km_ca[i] + cav) / vol
            amounts[p.plasma_na, j] += 3 * ncx / p.ncx_km_na[i] / vol
    return bound + max(float(np.max(cy)), float(np.max(out)))


def chemical_loss_bound(spec):
    _, p = initial_values(spec)
    global_ions = np.sum(p.extracellular_amount_reference, axis=-1)
    for i in range(len(spec.model.stores)):
        c = store_layout(p, i)
        global_ions += p.ion_content @ np.sum(c.initial_amount * c.active, axis=-1)
    losses = []
    for i, m in enumerate(spec.model.stores):
        c = store_layout(p, i)
        totals = c.moieties @ np.sum(c.initial_amount * c.active, axis=-1)
        for ion, value in zip(spec.model.species_ids, global_ions, strict=True):
            totals[m.moieties.index(ion)] = value
        losses.append(er.loss_bound(store_spec(spec, i), conserved_totals=totals))
    return max(losses)


def check_definition(spec):
    from cells.core.schedule import control_values

    state, p = initial_values(spec)
    controls = control_values(spec, [c.time for c in spec.experiment.changes])
    with np.errstate(all="ignore"):
        for i in range(len(controls.membrane)):
            if not control_domain_valid(
                state, type(controls)(*(v[i] for v in controls)), p, p.active, xp=np
            ):
                raise ConfigError("Initial resolved calcium inventory/gate/affinity domain invalid")
    if not np.isfinite(loss_bound(spec)):
        raise ConfigError("Resolved calcium conserved-pool loss bound is not finite")


def check_steps(spec, steps, controls):
    # Keep chemical-only event boundaries in the accepted observation grid.
    # ionic_spec() projects away store/plasma/calcium-channel schedules, so it
    # cannot be used to validate this composition's observation clock.
    kinetic.check_steps(spec, steps, controls)
    h = np.max(steps, initial=0)
    if isinstance(spec.model, SurfaceCalciumCavModel) and h > 1.25e-6 + 1e-16:
        raise ConfigError("Resolved owned calcium with shared CaV requires RK4 steps <= 1.25 us")
    if isinstance(spec.model, SurfaceCalciumSodiumModel) and h > 2.5e-6 + 1e-16:
        raise ConfigError("Resolved sodium/potassium/calcium requires RK4 steps <= 2.5 us")
    if isinstance(spec.model, SurfaceCalciumChannelModel) and h > 25e-6 + 1e-16:
        raise ConfigError("Resolved mixed potassium/calcium requires RK4 steps <= 25 us")
    if (
        h > er.MAX_STEP + 16 * np.finfo(float).eps
        or h * loss_bound(spec) > 0.25
        or h / gates.MIN_TAU_S > 0.25
    ):
        raise ConfigError(
            "Resolved calcium needs <=50 us and step * chemical/transport loss <=0.25"
        )


def balances(state, p, *, additional_transport=None):
    chemical, electric = 0.0, 0.0
    residuals = []
    er_work = []
    for i in range(p.er_initial_amount.shape[0]):
        s, c = store_state(state, i), store_layout(p, i)
        chemical += np.sum(chemistry.free_energy_change(s, c))
        dv = CHARGE_PER_FMOL / c.capacitance * np.sum(c.valence * s.amount_increment[:, c.er])
        electric += 0.5e12 * c.capacitance * dv * (2 * c.initial_voltage + dv)
        transfer = (
            s.passive_transferred
            + (s.pump_transferred + s.release_transferred) * c.calcium_selector
        )
        influx = p.free_ion_selector @ state.amount_increment[:, i]
        residuals.append(
            (
                s.amount_increment
                - chemistry.reaction_amount(s.reaction_extent, c)
                - transfer[:, None] * c.incidence
                - influx[:, None] * p.cytosol_selector[i]
            )
            / np.maximum(1, c.initial_amount)
        )
        drive = er.processes.chemical_drive(er.pump_parameters(c), c.temperature, xp=np)
        er_work.append(state.er_metabolic_work_pJ[i] + 1e-3 * drive * s.pump_transferred[0])
    total = (
        state.membrane_transferred
        + kinetic.channel_to_membrane(state.channel_transferred, p, xp=np)
        - p.stoichiometry * state.pump_cycles
        + p.plasma_ca_selector
        * (
            state.plasma_pump_cycles
            + state.plasma_exchange_cycles
            + state.calcium_channel_transferred
        )
        - 3 * p.plasma_na_selector * state.plasma_exchange_cycles
    )
    # An explicitly composed route supplies outward ion transfer, dissipation
    # and maintained-reservoir work separately. Never disguise pump work as
    # negative passive heat or alter the original fixed-pump ledgers.
    if additional_transport is not None:
        transfer, heat, work = additional_transport
        total = total + transfer
    b = base.balances(
        kinetic.passive_state(state)._replace(membrane_transferred=total),
        p,
        intracellular_energy_change_pJ=chemical,
    )
    extra_d = sum(
        np.sum(getattr(state, k))
        for k in STATE_AXES
        if k.endswith("_dissipated_energy_pJ") and k not in base.STATE_AXES
    )
    b["energy"] += (
        electric
        + extra_d
        - np.sum(state.metabolic_work_pJ)
        - np.sum(state.plasma_metabolic_work_pJ)
        - np.sum(state.er_metabolic_work_pJ)
    )
    if additional_transport is not None:
        b["energy"] += np.sum(heat) - np.sum(work)
    b["metabolic_work"] = state.metabolic_work_pJ + 1e-3 * p.pump_drive * state.pump_cycles
    b["plasma_metabolic_work"] = (
        state.plasma_metabolic_work_pJ
        + 1e-3
        * process.chemical_drive(plasma.pump_parameters(p), p.temperature, xp=np)
        * state.plasma_pump_cycles
    )
    b["er_metabolic_work"] = np.asarray(er_work)
    b["chemical_ledger"] = np.stack(residuals)
    b["ownership"] = ownership_residual(state, p)
    return b


def check_values(state, spec, *, additional_transport=None):
    _, p = initial_values(spec)
    rows = (
        [state]
        if state.amount_increment.ndim == 2
        else [STATE_TYPE(*(v[i] for v in state)) for i in range(len(state.amount_increment))]
    )
    diagnostics = {}
    for i, row in enumerate(rows):
        if not domain_valid(row, p, p.active, xp=np):
            raise NumericalError("Invalid resolved calcium inventory, ownership, gate or padding")
        extra = additional_transport
        if extra is not None and state.amount_increment.ndim > 2:
            extra = tuple(v[i] for v in extra)
        b = balances(row, p, additional_transport=extra)
        tol = np.asarray(spec.execution.material_balance_atol_fmol)
        q = np.r_[p.initial_cell_charge_C, p.initial_outside_charge_C] + base.charge_increment(
            row, p, xp=np
        )
        limits = dict(
            local=tol[:, None],
            outside=tol[:, None],
            total=tol,
            charge=field.CHARGE_ATOL_C + field.CHARGE_RTOL * np.abs(q),
            electrode=field.CHARGE_ATOL_C,
            global_charge=3e-25,
            energy=ENERGY_ATOL_PJ,
            reservoir_work=3e-12,
            electrode_work=3e-12,
            metabolic_work=3e-12,
            plasma_metabolic_work=3e-12,
            er_metabolic_work=3e-12,
            chemical_ledger=chemistry.ROUND_ATOL,
            ownership=chemistry.ROUND_ATOL,
        )
        for k, value in b.items():
            if not np.isfinite(value).all() or np.any(np.abs(value) > limits[k]):
                raise NumericalError("Resolved calcium accounting failed: " + k)
            diagnostics["max_" + k + "_error"] = max(
                diagnostics.get("max_" + k + "_error", 0), float(np.max(np.abs(value), initial=0))
            )
    state_axes = (
        HCN_STATE_AXES
        if isinstance(p, (HCN_LAYOUT_TYPE, KV1_LAYOUT_TYPE, CAV_LAYOUT_TYPE))
        else STATE_AXES
    )
    for k, axes in state_axes.items():
        if k.endswith("_dissipated_energy_pJ"):
            value = getattr(state, k)
            if (
                value.ndim > len(axes)
                and np.min(np.diff(value, axis=0), initial=0) < -chemistry.ROUND_ATOL
            ):
                raise NumericalError("Resolved calcium dissipation decreased: " + k)
    return diagnostics


OBSERVATION_FIELDS = (
    "times",
    *STATE_TYPE._fields,
    *(k for k in base.OBSERVATION_FIELDS if k not in ("times", *base.STATE_TYPE._fields)),
    "er_voltage_V",
    "ip3_cytosol_mM",
    "ip3_release_fraction",
    "calcium_targets",
    "calcium_tau_s",
    "plasma_affinity_J_mol",
    "channel_availability",
    "pump_availability",
    "calcium_channel_availability",
    "plasma_pump_availability",
    "plasma_exchange_availability",
)
Observations = make_dataclass(
    "SurfaceCalciumObservations", [(k, np.ndarray) for k in OBSERVATION_FIELDS], frozen=True
)


def observe_history(times, history, layout, requested, spec):
    from cells.core.schedule import control_values

    p = type(layout)(*(np.asarray(v) for v in layout))
    requested = np.asarray(requested, dtype=float)
    if any(t not in times for t in requested):
        raise ConfigError("Resolved calcium observations require accepted times")
    controls = control_values(spec, requested)
    records = []
    for j, t in enumerate(requested):
        i = int(np.flatnonzero(times == t)[0])
        state = STATE_TYPE(*(v[i] for v in history))
        control = type(controls)(*(v[j] for v in controls))
        w = readouts(state, control, p, xp=np)
        if not w.valid:
            raise NumericalError("Resolved calcium observation domain invalid")
        v, r, n = w.field, w.field.rates, p.active.size
        records.append(
            (
                np.asarray(t),
                *state,
                *physical_amounts(state, p),
                v.potential_V[:n],
                v.potential_V[n:],
                r.membrane_voltage_V,
                r.junction_voltage_V,
                r.membrane_flux_fmol_s,
                r.junction_flux_fmol_s,
                r.face_flux_fmol_s,
                r.reservoir_supply_fmol_s,
                v.electrode_charge_C,
                v.electrode_current_A,
                np.atleast_1d(v.reservoir_power_pJ_s),
                np.atleast_1d(v.electrode_power_pJ_s),
                v.charge_residual_C,
                v.component_current_residual_A,
                np.atleast_1d(v.energy_balance_pJ_s),
                control.membrane,
                control.junction,
                w.er_voltage_V,
                w.ip3_cytosol_mM,
                w.ip3_release_fraction,
                w.calcium_targets,
                w.calcium_tau_s,
                w.plasma_affinity_J_mol,
                control.channel,
                control.pump,
                control.calcium_channel,
                control.plasma_pump,
                control.plasma_exchange,
            )
        )
    if records:
        return Observations(*(np.stack(v) for v in zip(*records, strict=True)))
    sample = observe_history(times[:1], STATE_TYPE(*(v[:1] for v in history)), p, times[:1], spec)
    return Observations(
        *(np.empty((0, *v.shape[1:]), dtype=v.dtype) for v in vars(sample).values())
    )


def ensemble_voltage(state, layout, spec, time):
    # Patch voltage depends on conserved capacitor charge, not the floating
    # component gauge or instantaneous assembly-controlled conductance.
    p = type(layout)(*(np.asarray(v) for v in layout))
    state = STATE_TYPE(*(np.asarray(v) for v in state))
    _, _, dv = base.capacitor_change(state, p, xp=np)
    return (p.initial_membrane_voltage_V + dv)[p.membrane_active]


def summarize(history, diagnostics, spec):
    _, p = initial_values(spec)
    concentration, fraction = ip3_readouts(history, p, xp=np)
    return kinetic.summarize(history, diagnostics, ionic_spec(spec)) | dict(
        model=model_id(spec.model),
        state_fields=list(STATE_TYPE._fields),
        final_ip3_cytosol_mM=concentration[-1].tolist(),
        final_ip3_release_fraction=fraction[-1].tolist(),
        calcium_channel_transfer_direction="outward positive",
        capacitor_energy_rate_scope="plasma plus ER",
        claim_scope=(
            "Synthetic closed resolved electrical/chemical/assembly coupling; "
            "no whole-BETSE trajectory or biological calibration"
        ),
    )
