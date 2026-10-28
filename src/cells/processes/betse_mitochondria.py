"""Versioned native BETSE 1.5.0 mitochondrial ion/voltage Euler component.

One cytosol/mitochondrion pair per cell. Concentrations are float64 mM, arrays
[..., species, cell]; geometry/cached Q/V are [..., cell]. The source keeps full
cytosolic volume and snapshots half-volume/half-area mitochondrial geometry.
Incoming cached voltage drives ordered ion fluxes, including the source nonce
mutation; charge/voltage refresh happens once after the complete ion loop.

No ATP synthesis, channels, solvent or heat ledger is added. Callers supply the
external charge density explicitly. Kernels are pure; invalid predicted trials
are rejected by domain_valid, without clamping or automatic timestep changes.
"""

from typing import NamedTuple

import jax.numpy as jnp
import numpy as np

from cells.processes.electrochemistry import MOL_PER_FMOL

LAW_ID = "betse_mitochondrial_ion_voltage_source_v1_5_0@1"
NATIVE_NONCE = 1e-25
NATIVE_DIFFUSIVITY_M2_S = 1e-19
NATIVE_FARADAY_C_MOL = 96485.0
NATIVE_GAS_CONSTANT_J_MOL_K = 8.314


class Topology(NamedTuple):
    species_valence: object  # [species], including fixed/nonmoving ions.
    moving_species: object  # Ordered unique indices; order affects native nonce.
    active: object  # [cell], zero padding is explicit.


class Parameters(NamedTuple):
    cytosol_volume_m3: object
    mitochondria_volume_m3: object
    mitochondria_area_m2: object
    capacitance_F: object
    membrane_thickness_m: object
    diffusivity_m2_s: object  # [..., species, cell], actual active Dm_mit.
    base_diffusivity_m2_s: object  # Native copy; no channel dynamics consume it.
    channel_diffusivity_m2_s: object  # Native copy; no channel dynamics consume it.
    temperature_K: object  # Scalar or [..., 1], one temperature per world.
    faraday_C_mol: object  # Explicit source p.F; pinned native value by default.
    gas_constant_J_mol_K: object  # Explicit source p.R, per-world singleton.


class State(NamedTuple):
    cytosol_mM: object
    mitochondria_mM: object
    charge_C: object  # Cached Q, intentionally zero at native construction.
    voltage_V: object  # Cached V, not implicitly refreshed before a step.


class Step(NamedTuple):
    state: State
    flux_density_mol_m2_s: object
    transferred_fmol: object  # Positive cytosol -> mitochondrion.
    voltage_used_V: object  # [..., moving_species, cell], after each nonce.
    physical_charge_before_C: object
    cache_charge_adjustment_C: object


class MaterialBalances(NamedTuple):
    cytosol_residual_fmol: object
    mitochondria_residual_fmol: object
    species_total_residual_fmol: object
    charge_residual_C: object


def _numeric(value):
    return value.dtype.kind in "fiu"


def _float64(value):
    return value.dtype.kind == "f" and value.dtype.itemsize == 8


def _topology_domain(topology, *, xp):
    z, moving, active = (xp.asarray(value) for value in topology)
    if (
        z.ndim != 1
        or not z.size
        or z.dtype.kind not in "iu"
        or moving.ndim != 1
        or moving.dtype.kind not in "iu"
        or active.ndim != 1
        or active.dtype.kind != "b"
    ):
        raise ValueError("Require integer species/moving axes and an explicit cell mask")
    valid = xp.all((z >= -8) & (z <= 8))
    valid &= xp.all((moving >= 0) & (moving < z.size))
    valid &= xp.all(xp.sum(moving[:, None] == moving[None, :], axis=0) == 1)
    return valid, Topology(z, xp.clip(moving, 0, z.size - 1), active)


def validate_topology(topology):
    valid, normalized = _topology_domain(topology, xp=np)
    if not valid:
        raise ValueError("Invalid native mitochondrial valences or ordered moving species")
    return normalized


def _parameters(parameters, topology, *, xp):
    p = Parameters(*(xp.asarray(value) for value in parameters))
    count, species = topology.active.size, topology.species_valence.size
    if not all(_numeric(value) for value in p):
        raise ValueError("Require real mitochondrial parameters without booleans")
    if any(value.ndim < 1 or value.shape[-1] != count for value in p[:5]):
        raise ValueError("Mitochondrial geometry requires explicit final cell axes")
    if any(value.ndim < 2 or value.shape[-2:] != (species, count) for value in p[5:8]):
        raise ValueError("Diffusivity requires [..., species, cell] arrays")
    tail = []
    for value in p[8:]:
        value = value.reshape((1,)) if not value.ndim else value
        if value.shape[-1] != 1:
            raise ValueError("Temperature and constants require singleton final axes")
        tail.append(value)
    return Parameters(*p[:8], *tail)


def validate_parameters(parameters, topology):
    t = validate_topology(topology)
    p = _parameters(parameters, t, xp=np)
    if (
        any(not np.isfinite(value).all() for value in p)
        or any(np.any(value <= 0) for value in p[8:])
        or any(np.any(np.where(t.active, value <= 0, value != 0)) for value in p[:5])
        or any(np.any(np.where(t.active, value < 0, value != 0)) for value in p[5:8])
    ):
        raise ValueError("Invalid mitochondrial geometry, temperature, diffusivity or padding")
    return p


def bind(
    species_valence,
    moving_species,
    cell_volume_m3,
    cell_area_m2,
    *,
    specific_capacitance_F_m2,
    temperature_K,
    membrane_thickness_m=7.5e-9,
    faraday_C_mol=NATIVE_FARADAY_C_MOL,
    gas_constant_J_mol_K=NATIVE_GAS_CONSTANT_J_MOL_K,
    active=None,
):
    """Host constructor geometry; snapshots mitochondrial halves and native D.

    Current full cytosolic volume is independently replaceable after binding;
    mitochondrial volume/area/capacitance retain their initialization values.
    """
    volume, area = np.asarray(cell_volume_m3), np.asarray(cell_area_m2)
    if not _numeric(volume) or not _numeric(area):
        raise ValueError("Require real cell geometry without booleans")
    volume, area = volume.astype(float), area.astype(float)
    if volume.ndim != 1 or area.shape != volume.shape:
        raise ValueError("Require matching one-dimensional cell volume/area arrays")
    active = np.ones(volume.shape, bool) if active is None else np.asarray(active)
    moving = np.asarray(moving_species)
    if moving.shape == (0,):
        moving = moving.astype(int)
    topology = validate_topology(Topology(np.asarray(species_valence), moving, active))
    if topology.active.shape != volume.shape:
        raise ValueError("Geometry and active cell axes must match")
    raw_cm, raw_thickness, raw_temperature, raw_faraday, raw_gas = (
        np.asarray(value)
        for value in (
            specific_capacitance_F_m2,
            membrane_thickness_m,
            temperature_K,
            faraday_C_mol,
            gas_constant_J_mol_K,
        )
    )
    if any(
        not _numeric(value) or not np.isfinite(value).all() or np.any(value <= 0)
        for value in (raw_cm, raw_thickness, raw_temperature, raw_faraday, raw_gas)
    ):
        raise ValueError("Require positive finite specific capacitance, thickness and temperature")
    cm, thickness = (np.broadcast_to(value, volume.shape) for value in (raw_cm, raw_thickness))
    mit_volume, mit_area = 0.5 * volume, 0.5 * area
    diffusion = np.where(active, NATIVE_DIFFUSIVITY_M2_S, 0.0)
    diffusion = np.broadcast_to(diffusion, (topology.species_valence.size, volume.size)).copy()
    p = Parameters(
        volume,
        mit_volume,
        mit_area,
        mit_area * cm,
        np.where(active, thickness, 0.0),
        diffusion,
        diffusion.copy(),
        diffusion.copy(),
        raw_temperature,
        raw_faraday,
        raw_gas,
    )
    return topology, validate_parameters(p, topology)


def initial_state(cytosol_mM, topology, *, xp=jnp):
    """Native construction copies ions and leaves both voltage/charge caches zero."""
    c = xp.asarray(cytosol_mM)
    if (
        c.ndim < 2
        or c.shape[-2:] != (topology.species_valence.size, topology.active.size)
        or not _float64(c)
    ):
        raise ValueError("Require float64 concentrations [..., species, cell]")
    zeros = xp.zeros(c.shape[:-2] + (topology.active.size,), dtype=c.dtype)
    return State(c.copy(), c.copy(), zeros, zeros.copy())


def _broadcast(state, topology, parameters, extra_charge_density_C_m3, dt_s, *, xp):
    t, p = topology, _parameters(parameters, topology, xp=xp)
    s = State(*(xp.asarray(value) for value in state))
    count, species = t.active.size, t.species_valence.size
    if (
        not all(_float64(value) for value in s)
        or any(value.ndim < 2 or value.shape[-2:] != (species, count) for value in s[:2])
        or any(value.ndim < 1 or value.shape[-1] != count for value in s[2:])
    ):
        raise ValueError("Require complete float64 paired concentration and cached Q/V state")
    extra, dt = xp.asarray(extra_charge_density_C_m3), xp.asarray(dt_s)
    if not _numeric(extra) or not _numeric(dt):
        raise ValueError("Explicit real extra charge density and time step are required")
    if not dt.ndim:
        dt = dt.reshape((1,))
    if dt.shape[-1] != 1:
        raise ValueError("Time step requires a singleton final world axis")
    shape = xp.broadcast_shapes(
        s.cytosol_mM.shape[:-2] + (count,),
        s.mitochondria_mM.shape[:-2] + (count,),
        s.charge_C.shape,
        s.voltage_V.shape,
        *(value.shape for value in p[:5]),
        *(value.shape[:-2] + (count,) for value in p[5:8]),
        *(value.shape for value in p[8:]),
        extra.shape,
        dt.shape,
    )
    if shape[-1] != count:
        raise ValueError("Mitochondrial state/parameter cell axis mismatch")
    fields = shape[:-1] + (species, count)
    s = State(*(xp.broadcast_to(value, fields if i < 2 else shape) for i, value in enumerate(s)))
    p = Parameters(
        *(xp.broadcast_to(value, shape) for value in p[:5]),
        *(xp.broadcast_to(value, fields) for value in p[5:8]),
        *p[8:],
    )
    return s, p, xp.broadcast_to(extra, shape), dt


def _charge(concentration, topology, parameters, extra, *, xp):
    p, t = parameters, topology
    charge = (
        xp.sum(
            (p.faraday_C_mol * p.mitochondria_volume_m3)[..., None, :]
            * concentration
            * t.species_valence[:, None],
            axis=-2,
        )
        + extra * p.mitochondria_volume_m3
    )
    return xp.where(t.active, charge, 0.0)


def refresh_voltage(state, topology, parameters, extra_charge_density_C_m3, *, xp=jnp):
    """Explicit native get_v phase; not called implicitly before ion fluxes."""
    s, p, extra, _ = _broadcast(state, topology, parameters, extra_charge_density_C_m3, 0.0, xp=xp)
    charge = _charge(s.mitochondria_mM, topology, p, extra, xp=xp)
    capacitance = xp.where(topology.active, p.capacitance_F, 1.0)
    return s._replace(
        charge_C=charge, voltage_V=xp.where(topology.active, (1 / capacitance) * charge, 0.0)
    )


def step(state, topology, parameters, extra_charge_density_C_m3, dt_s, *, xp=jnp):
    """Unchecked literal native update, with ordered nonce mutation and Euler steps."""
    s, p, extra, dt = _broadcast(
        state, topology, parameters, extra_charge_density_C_m3, dt_s, xp=xp
    )
    t = topology
    cytosol, mitochondria = s.cytosol_mM.copy(), s.mitochondria_mM.copy()
    voltage = s.voltage_V.copy()
    before = _charge(mitochondria, t, p, extra, xp=xp)
    fluxes, used = xp.zeros_like(cytosol), []
    area = xp.where(t.active, p.mitochondria_area_m2, 0.0)
    cy_volume = xp.where(t.active, p.cytosol_volume_m3, 1.0)
    mit_volume = xp.where(t.active, p.mitochondria_volume_m3, 1.0)
    thickness = xp.where(t.active, p.membrane_thickness_m, 1.0)
    moving, z = xp.asarray(t.moving_species), xp.asarray(t.species_valence)
    for position in range(moving.size):
        ion = moving[position]
        voltage = xp.where(t.active, voltage + NATIVE_NONCE, 0.0)
        used.append(voltage)
        flux_voltage = xp.where(t.active, voltage, 0.01)
        valence = xp.where(t.active, z[ion] + NATIVE_NONCE, 1.0)
        alpha = (
            valence * flux_voltage * p.faraday_C_mol / (p.gas_constant_J_mol_K * p.temperature_K)
        )
        ca, cb = (xp.where(t.active, value[..., ion, :], 1.0) for value in (cytosol, mitochondria))
        density = -(p.diffusivity_m2_s[..., ion, :] * alpha / thickness) * (
            (cb - ca * xp.exp(-alpha)) / -xp.expm1(-alpha)
        )
        density = xp.where(t.active, density, 0.0)
        new_cyto = cytosol[..., ion, :] - density * (area / cy_volume) * dt
        new_mito = mitochondria[..., ion, :] + density * (area / mit_volume) * dt
        if xp is np:
            cytosol[..., ion, :], mitochondria[..., ion, :], fluxes[..., ion, :] = (
                new_cyto,
                new_mito,
                density,
            )
        else:
            cytosol = cytosol.at[..., ion, :].set(new_cyto)
            mitochondria = mitochondria.at[..., ion, :].set(new_mito)
            fluxes = fluxes.at[..., ion, :].set(density)
    charge = _charge(mitochondria, t, p, extra, xp=xp)
    capacitance = xp.where(t.active, p.capacitance_F, 1.0)
    final = State(
        cytosol, mitochondria, charge, xp.where(t.active, (1 / capacitance) * charge, 0.0)
    )
    used = (
        xp.stack(used, axis=-2)
        if used
        else xp.zeros(s.voltage_V.shape[:-1] + (0, t.active.size), dtype=s.voltage_V.dtype)
    )
    return Step(
        final,
        fluxes,
        fluxes * area[..., None, :] * dt[..., None] / MOL_PER_FMOL,
        used,
        before,
        before - s.charge_C,
    )


def domain_valid(state, topology, parameters, extra_charge_density_C_m3, dt_s, *, xp=jnp):
    """Reject invalid inputs and the complete predicted native Euler candidate."""
    try:
        valid, t = _topology_domain(topology, xp=xp)
        raw = _parameters(parameters, t, xp=xp)
        s, p, extra, dt = _broadcast(state, t, raw, extra_charge_density_C_m3, dt_s, xp=xp)
    except (TypeError, ValueError, AttributeError, IndexError):
        return xp.asarray(False)
    for value in (*raw, xp.asarray(extra_charge_density_C_m3), xp.asarray(dt_s), *s):
        valid &= xp.all(xp.isfinite(value))
    for value in raw[8:]:
        valid &= xp.all(value > 0)
    valid &= xp.all(xp.asarray(dt_s) >= 0)
    for value in p[:5]:
        valid &= xp.all(xp.where(t.active, value > 0, value == 0))
    for value in p[5:8]:
        valid &= xp.all(xp.where(t.active, value >= 0, value == 0))
    for value in s[:2]:
        valid &= xp.all(xp.where(t.active, value >= 0, value == 0))
    for value in (*s[2:], extra):
        valid &= xp.all(xp.where(t.active, True, value == 0))
    safe_p = Parameters(
        *(xp.where(xp.isfinite(value) & (value > 0), value, 1.0) for value in p[:5]),
        *(xp.where(xp.isfinite(value) & (value >= 0), value, 0.0) for value in p[5:8]),
        *(
            xp.where(xp.isfinite(value) & (value > 0), value, fallback)
            for value, fallback in zip(
                raw[8:], (298.15, NATIVE_FARADAY_C_MOL, NATIVE_GAS_CONSTANT_J_MOL_K), strict=True
            )
        ),
    )
    safe_s = State(*(xp.where(xp.isfinite(value), value, 0.0) for value in s))
    predicted = step(
        safe_s,
        t,
        safe_p,
        xp.where(xp.isfinite(extra), extra, 0.0),
        xp.where(xp.isfinite(dt) & (dt >= 0), dt, 0.0),
        xp=xp,
    )
    for value in (*predicted.state, *predicted[1:]):
        valid &= xp.all(xp.isfinite(value))
    for value in predicted.state[:2]:
        valid &= xp.all(xp.where(t.active, value >= 0, value == 0))
    return valid


def material_balances(before, result, topology, parameters, *, xp=jnp):
    p, t = parameters, topology
    dc = (
        (result.state.cytosol_mM - before.cytosol_mM)
        * p.cytosol_volume_m3[..., None, :]
        / MOL_PER_FMOL
    )
    dm = (
        (result.state.mitochondria_mM - before.mitochondria_mM)
        * p.mitochondria_volume_m3[..., None, :]
        / MOL_PER_FMOL
    )
    charge_transfer = (
        p.faraday_C_mol
        * MOL_PER_FMOL
        * xp.sum(t.species_valence[:, None] * result.transferred_fmol, axis=-2)
    )
    return MaterialBalances(
        dc + result.transferred_fmol,
        dm - result.transferred_fmol,
        dc + dm,
        result.state.charge_C - result.physical_charge_before_C - charge_transfer,
    )
