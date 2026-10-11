"""Spatial calcium with explicit PMCA and NCX material/work/dissipation ledgers."""

from dataclasses import make_dataclass
from typing import NamedTuple

import jax.numpy as jnp
import numpy as np

from cells.core.errors import NumericalError
from cells.core.plasma_calcium_spec import MODEL_ID, base_spec
from cells.core.schedule import CalciumControl, control_values
from cells.core.specs import ConfigError
from cells.models import spatial_calcium as base
from cells.observers import hermite_bounds, sample_hermite_history
from cells.processes import plasma_calcium as process
from cells.processes.electrochemistry import CHARGE_PER_FMOL, F, R

EXTRA_FIELDS = ("plasma_pump_cycles", "plasma_exchange_cycles", "plasma_dissipated_energy_pJ")
State = NamedTuple("State", [(k, object) for k in (*base.State._fields, *EXTRA_FIELDS)])
LAYOUT_FIELDS = (
    "plasma_ca",
    "plasma_na",
    "plasma_ca_selector",
    "plasma_na_selector",
    "pmca_present",
    "pmca_capacity",
    "pmca_km_ca",
    "pmca_km_atp",
    "pmca_atp",
    "pmca_adp",
    "pmca_pi",
    "pmca_dg",
    "ncx_present",
    "ncx_capacity",
    "ncx_km_na",
    "ncx_km_ca",
)
Layout = NamedTuple("Layout", [(k, object) for k in (*base.Layout._fields, *LAYOUT_FIELDS)])
STATE_TYPE, LAYOUT_TYPE = State, Layout
STATE_AXES = base.STATE_AXES | {
    "plasma_pump_cycles": ["membrane_slot"],
    "plasma_exchange_cycles": ["membrane_slot"],
    "plasma_dissipated_energy_pJ": ["plasma_route", "membrane_slot"],
}
OBSERVER_ID = "spatial_calcium_plasma_transport_readouts@1"
OBSERVATION_SAMPLING = "read_only_control_local_hermite_plasma_calcium_enclosed@1"
STAGE_DOMAIN_ID = "positive_spatial_calcium_pmca_ncx_affinity@1"
BATCH_CAPACITIES = base.BATCH_CAPACITIES
ENERGY_ATOL_PJ = base.ENERGY_ATOL_PJ
parameters, cell_voltage = base.parameters, base.cell_voltage
cytosol_amount, store_state, store_layout, er = (
    base.cytosol_amount,
    base.store_state,
    base.store_layout,
    base.er,
)


def batch_signature(model):
    return base.batch_signature(model), model.calcium_species, model.sodium_species


def working_size(spec):
    return base.working_size(base_spec(spec)) + 64 * (
        24 * spec.execution.membrane_capacity + 2 * len(spec.model.species_ids) + 8
    )


def initial_values(spec):
    state, p = base.initial_values(base_spec(spec))
    nm = spec.execution.membrane_capacity
    ca = spec.model.species_ids.index(spec.model.calcium_species)
    na = spec.model.species_ids.index(spec.model.sodium_species)
    extra = {k: np.ones(nm) for k in LAYOUT_FIELDS[4:]}
    for key in ("pmca_present", "ncx_present"):
        extra[key] = np.zeros(nm, dtype=bool)
    for key in ("pmca_capacity", "pmca_dg", "ncx_capacity"):
        extra[key] = np.zeros(nm)
    for i, route in enumerate(spec.model.plasma_routes):
        if route.pump is not None:
            q = route.pump
            extra["pmca_present"][i] = True
            for name, field in (
                ("capacity", "capacity_fmol_per_s"),
                ("km_ca", "km_ca_mM"),
                ("km_atp", "km_atp_mM"),
                ("atp", "atp_mM"),
                ("adp", "adp_mM"),
                ("pi", "pi_mM"),
                ("dg", "delta_g0_J_per_mol"),
            ):
                extra["pmca_" + name][i] = getattr(q, field)
        if route.exchanger is not None:
            q = route.exchanger
            extra["ncx_present"][i] = True
            for name, field in (
                ("capacity", "capacity_fmol_per_s"),
                ("km_ca", "km_ca_mM"),
                ("km_na", "km_na_mM"),
            ):
                extra["ncx_" + name][i] = getattr(q, field)
    return State(*state, np.zeros(nm), np.zeros(nm), np.zeros((2, nm))), Layout(
        *p,
        np.int32(ca),
        np.int32(na),
        np.eye(len(spec.model.species_ids))[ca, :, None],
        np.eye(len(spec.model.species_ids))[na, :, None],
        *(extra[k] for k in LAYOUT_FIELDS[4:]),
    )


def pump_parameters(p):
    return process.PumpParameters(
        p.pmca_capacity,
        p.pmca_km_ca,
        p.pmca_km_atp,
        p.pmca_atp,
        p.pmca_adp,
        p.pmca_pi,
        p.pmca_dg,
    )


def readouts(state, p, pump=1.0, exchange=1.0, *, xp=jnp):
    ci, co, v, t = base.finite.membrane_inputs(state, base.ionic_layout(state, p, xp=xp), xp=xp)
    pmca, gp, drive = process.pump_rates(
        ci[..., p.plasma_ca, :],
        co[..., p.plasma_ca, :],
        v,
        t,
        pump_parameters(p),
        pump,
        xp=xp,
    )
    ncx, gx = process.exchange_rates(
        ci[..., p.plasma_na, :],
        co[..., p.plasma_na, :],
        ci[..., p.plasma_ca, :],
        co[..., p.plasma_ca, :],
        v,
        t,
        process.ExchangerParameters(p.ncx_capacity, p.ncx_km_na, p.ncx_km_ca),
        exchange,
        xp=xp,
    )
    return pmca, ncx, gp, gx, drive


def membrane_exchange(pmca, ncx, p):
    return -(pmca + ncx)[..., None, :] * p.plasma_ca_selector + (
        3 * ncx[..., None, :] * p.plasma_na_selector
    )


def rhs(state, control, p, active, *, xp=jnp, ionic=base.spatial):
    rates = base.rhs(state, CalciumControl(*control[:7]), p, active, xp=xp, ionic=ionic)
    pmca, ncx, gp, gx, _ = readouts(state, p, control.plasma_pump, control.plasma_exchange, xp=xp)
    flux = membrane_exchange(pmca, ncx, p)
    inside = base.finite.gated.scatter(flux, rates.amount_increment, (p.owners,), xp=xp)
    outside = base.finite.gated.scatter(
        -flux, rates.extracellular_amount_increment, (p.outside_owners,), xp=xp
    )
    chemical = xp.stack(
        [
            xp.einsum("si,...i->...s", p.free_ion_selector, inside[..., :, i])[..., :, None]
            * p.cytosol_selector[i]
            for i in range(p.er_initial_amount.shape[0])
        ],
        axis=-3,
    )
    rates = rates._replace(
        amount_increment=rates.amount_increment + inside,
        extracellular_amount_increment=rates.extracellular_amount_increment + outside,
        chemical_amount_increment=rates.chemical_amount_increment + chemical,
    )
    return State(*rates, pmca, ncx, -1e-3 * xp.stack((pmca * gp, ncx * gx), axis=-2))


def domain_valid(state, p, active, *, xp=jnp, ionic=base.spatial):
    valid = base.domain_valid(state, p, active, xp=xp, ionic=ionic)
    _, _, gp, gx, _ = readouts(state, p, xp=xp)
    rt = R * p.temperature[p.outside_owners]
    v = base.finite.membrane_voltage(state.amount_increment, p, xp=xp)
    valid &= xp.all(xp.abs(v) <= process.MAX_VOLTAGE)
    for a, enabled in ((gp / rt, p.pmca_present), (gx / rt, p.ncx_present)):
        valid &= xp.all(
            xp.where(enabled, xp.isfinite(a) & (xp.abs(a) <= process.MAX_AFFINITY_RT), True)
        )
    for name, mask in (
        ("plasma_pump_cycles", p.pmca_capacity > 0),
        ("plasma_exchange_cycles", p.ncx_capacity > 0),
        ("plasma_dissipated_energy_pJ", xp.stack((p.pmca_capacity > 0, p.ncx_capacity > 0))),
    ):
        value = getattr(state, name)
        valid &= xp.all(xp.isfinite(value)) & xp.all(xp.where(mask, True, value == 0))
    return valid & xp.all(state.plasma_dissipated_energy_pJ >= 0)


def plasma_loss_bound(spec):
    """Conservative concentration-independent substrate loss coefficients."""
    _, p = initial_values(spec)
    t = p.temperature[p.outside_owners]
    vmax = process.MAX_VOLTAGE
    saturation = p.pmca_atp / (p.pmca_km_atp + p.pmca_atp)
    drive = process.chemical_drive(pump_parameters(p), t, xp=np)
    cy = np.zeros_like(p.amount_reference)
    out = np.zeros_like(p.extracellular_amount_reference)
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        for i in np.flatnonzero(p.membrane_active):
            owner, outside = p.owners[i], p.outside_owners[i]
            pmca = p.pmca_capacity[i] * saturation[i] / p.pmca_km_ca[i]
            cy[p.plasma_ca, owner] += pmca / p.volume[owner]
            out[p.plasma_ca, outside] += (
                pmca
                * np.exp((drive[i] + 2 * F * vmax) / (R * t[i]))
                / p.extracellular_volume[outside]
            )
            ncx = p.ncx_capacity[i] * np.exp(F * vmax / (2 * R * t[i]))
            for amounts, cell, volume in (
                (cy, owner, p.volume[owner]),
                (out, outside, p.extracellular_volume[outside]),
            ):
                amounts[p.plasma_ca, cell] += ncx / (p.ncx_km_ca[i] * volume)
                amounts[p.plasma_na, cell] += 3 * ncx / (p.ncx_km_na[i] * volume)
    bound = max(float(np.max(cy)), float(np.max(out)))
    if not np.isfinite(bound):
        raise ConfigError("Plasma transport loss bound is not finite")
    return bound


def check_definition(spec):
    state, p = initial_values(spec)
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        if not domain_valid(state, p, p.active, xp=np, ionic=base.ionic_model(spec)):
            raise ConfigError("Initial plasma calcium voltage/affinity/ownership domain failed")
    plasma_loss_bound(spec)


def check_steps(spec, steps, controls):
    original = base_spec(spec)
    base.check_steps(original, steps, control_values(original, [0.0]))
    if np.max(steps, initial=0) * (base.loss_bound(original) + plasma_loss_bound(spec)) > 0.25:
        raise ConfigError("Step times combined chemical/plasma loss bound exceeds 0.25")


def extra_energy(state, p):
    drive = process.chemical_drive(pump_parameters(p), p.temperature[p.outside_owners], xp=np)
    return np.sum(state.plasma_dissipated_energy_pJ, axis=(-2, -1)) + 1e-3 * np.sum(
        drive * state.plasma_pump_cycles, axis=-1
    )


def energy_balance(state, p):
    return base.energy_balance(state, p) + extra_energy(state, p)


def check_values(state, spec, *, additional_exchange=None, additional_energy=0.0):
    _, p = initial_values(spec)
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        if not domain_valid(state, p, p.active, xp=np, ionic=base.ionic_model(spec)):
            raise NumericalError(
                "Plasma calcium inventory, affinity or transport ledger domain failed"
            )
    d = state.plasma_dissipated_energy_pJ
    if d.ndim > 2 and np.min(np.diff(d, axis=0), initial=0) < -base.chemistry.ROUND_ATOL:
        raise NumericalError("Plasma transport dissipation decreased")
    exchange = membrane_exchange(state.plasma_pump_cycles, state.plasma_exchange_cycles, p)
    if additional_exchange is not None:
        exchange = exchange + additional_exchange
    return base.check_values(
        state,
        base_spec(spec),
        extra_exchange=exchange,
        extra_energy=extra_energy(state, p) + additional_energy,
    )


def check_interpolants(times, history, left, right, p):
    base.check_interpolants(times, history, left, right, p)
    if len(times) < 2:
        return
    inside = base.bounds.cubic_hull(
        times,
        cytosol_amount(history, p, xp=np),
        *(cytosol_amount(s, p, xp=np, derivative=True) for s in (left, right)),
    )
    outside = tuple(
        v + p.extracellular_amount_reference
        for v in base.bounds.cubic_hull(
            times,
            history.extracellular_amount_increment,
            left.extracellular_amount_increment,
            right.extracellular_amount_increment,
        )
    )
    ci, co = [
        tuple(np.where(p.membrane_active, v[..., :, owners] / volume[owners], 1.0) for v in pair)
        for pair, owners, volume in (
            (inside, p.owners, p.volume),
            (outside, p.outside_owners, p.extracellular_volume),
        )
    ]
    vl, vh = base.bounds.cubic_hull(
        times,
        base.finite.membrane_voltage(history.amount_increment, p, xp=np),
        *(
            CHARGE_PER_FMOL
            / p.capacitance
            * np.sum(p.valence * s.amount_increment[..., :, p.owners], axis=-2)
            for s in (left, right)
        ),
    )
    if np.any(np.maximum(np.abs(vl), np.abs(vh))[..., p.membrane_active] > process.MAX_VOLTAGE):
        raise NumericalError("Plasma calcium cubic voltage outside domain")
    cil, cih = (v[..., p.plasma_ca, :] for v in ci)
    col, coh = (v[..., p.plasma_ca, :] for v in co)
    nil, nih = (v[..., p.plasma_na, :] for v in ci)
    nol, noh = (v[..., p.plasma_na, :] for v in co)
    rt = R * p.temperature[p.outside_owners]
    drive = process.chemical_drive(pump_parameters(p), p.temperature[p.outside_owners], xp=np) / rt
    for low, high, mask in (
        (
            drive + np.log(col) - np.log(cih) - 2 * F * vh / rt,
            drive + np.log(coh) - np.log(cil) - 2 * F * vl / rt,
            p.pmca_present,
        ),
        (
            3 * (np.log(nil) - np.log(noh)) + np.log(col) - np.log(cih) + F * vl / rt,
            3 * (np.log(nih) - np.log(nol)) + np.log(coh) - np.log(cil) + F * vh / rt,
            p.ncx_present,
        ),
    ):
        if (
            np.any(~np.isfinite(low[..., mask]))
            or np.any(~np.isfinite(high[..., mask]))
            or np.any(
                np.maximum(np.abs(low[..., mask]), np.abs(high[..., mask]))
                > process.MAX_AFFINITY_RT
            )
        ):
            raise NumericalError("Plasma calcium cubic affinity outside domain")
    d = history.plasma_dissipated_energy_pJ
    lo, hi = hermite_bounds(
        times, d, left.plasma_dissipated_energy_pJ, right.plasma_dissipated_energy_pJ
    )
    if np.any(lo < d[:-1] - base.chemistry.ROUND_ATOL) or np.any(
        hi > d[1:] + base.chemistry.ROUND_ATOL
    ):
        raise NumericalError("Plasma calcium cubic dissipation left its ledger interval")


Observations = make_dataclass(
    "Observations",
    [(k, np.ndarray) for k in ("times", *State._fields, *base.DERIVED_FIELDS)],
    frozen=True,
)


def observe_history(times, history, layout, requested, spec):
    p = Layout(*(np.asarray(v) for v in layout))
    requested = np.asarray(requested, dtype=np.float64)
    controls = control_values(spec, times[:-1])
    left, right = (
        rhs(State(*(v[part] for v in history)), controls, p, p.active, xp=np)
        for part in (slice(None, -1), slice(1, None))
    )
    check_interpolants(times, history, left, right, p)
    sampled = State(
        *(
            sample_hermite_history(times, v, requested, a, b)
            for v, a, b in zip(history, left, right, strict=True)
        )
    )
    check_values(sampled, spec)
    return Observations(
        requested,
        *sampled,
        cytosol_amount(sampled, p, xp=np),
        p.extracellular_amount_reference + sampled.extracellular_amount_increment,
        cell_voltage(sampled.amount_increment, p, xp=np),
        np.stack(
            [
                er.voltage(store_state(sampled, i), store_layout(p, i), xp=np)
                for i in range(p.er_initial_amount.shape[0])
            ],
            axis=-1,
        ),
        base.spatial.field_values(sampled, p, xp=np).potential_V,
    )


def summarize(history, diagnostics, spec):
    return base.summarize(history, diagnostics, base_spec(spec)) | {
        "model": MODEL_ID,
        "state_axes": STATE_AXES,
        "plasma_pump_law": process.PUMP_LAW,
        "plasma_exchanger_law": process.EXCHANGER_LAW,
        "final_plasma_pump_cycles_fmol": history.plasma_pump_cycles[-1].tolist(),
        "final_plasma_exchange_cycles_fmol": history.plasma_exchange_cycles[-1].tolist(),
        "claim_scope": (
            "Synthetic plasma/ER/spatial/assembly coupling; native PMCA function correspondence, "
            "synthetic reversible NCX; no biological or full BETSE trajectory calibration"
        ),
    }
