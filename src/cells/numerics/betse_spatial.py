"""Pinned BETSE 1.5 passive spatial compatibility, separate from Cells' field law.

Native forward-Euler order, membrane concentration lag, screened charge field,
and signed boundary derivatives are intentional here. No BETSE dependency,
captured voltage operator, fitted forcing, concentration repair or state reset.
Material from reservoir resets and the nonconservative native stencil has
separate per-species/per-grid-site ledgers. This is not an energy-conserving
replacement for the resolved capacitor/return-current models.
"""

from typing import NamedTuple

import jax
import jax.numpy as jnp
import numpy as np

from cells.coupling.selective import selective_flux
from cells.processes.electrochemistry import F, ghk_leak

MODEL_ID = "betse_spatial_passive@1"


class Layout(NamedTuple):
    cell_volume: object
    membrane_area: object
    cell_owner: object
    outside_owner: object
    partner: object
    moving: object
    valence: object
    membrane_permeability: object
    junction_permeability: object
    membrane_open: object
    junction_open: object
    diffusivity: object
    boundary_concentration: object
    boundary_values: object
    extra_cell_charge_density: object
    extra_outside_charge_density: object
    spacing: object
    height: object
    temperature: object
    capacitance_density: object
    screening_wavenumber: object
    permittivity: object
    cell_size_ratio: object
    native_q_over_kb: object


class State(NamedTuple):
    cell_concentration: object
    membrane_concentration: object
    outside_concentration: object
    membrane_inward_fmol: object
    junction_outward_fmol: object
    reservoir_reset_fmol: object
    stencil_exchange_fmol: object
    step_count: object
    elapsed_s: object


class Field(NamedTuple):
    membrane_voltage_V: object
    cell_mean_voltage_V: object
    cell_charge_density: object
    boundary_potential_V: object
    outside_potential_V: object
    outside_field_x_V_m: object
    outside_field_y_V_m: object


class Rates(NamedTuple):
    membrane_inward_fmol_s: object
    junction_outward_fmol_s: object
    outside_flux_x_mol_m2_s: object
    outside_flux_y_mol_m2_s: object


def boundary_mask(shape, *, xp=jnp):
    rows, cols = shape
    y, x = xp.arange(rows)[:, None], xp.arange(cols)[None, :]
    return (y == 0) | (x == 0) | (y == rows - 1) | (x == cols - 1)


def dirichlet_operator(shape):
    """Dimensionless five-point operator, built from topology, not native inverse."""
    rows, cols = shape
    if min(shape) < 3 or rows * cols > 256:
        raise ValueError("Compatibility grid requires 3+ sites per axis and at most 256 sites")
    matrix = np.eye(rows * cols)
    for y in range(1, rows - 1):
        for x in range(1, cols - 1):
            i = y * cols + x
            matrix[i, i] = -4
            matrix[i, [i - cols, i + cols, i - 1, i + 1]] = 1
    return matrix


def boundary_field(values, *, xp=jnp):
    matrix = xp.asarray(dirichlet_operator(values.shape))
    rhs = xp.where(boundary_mask(values.shape, xp=xp), values, 0).ravel()
    return xp.linalg.solve(matrix, rhs).reshape(values.shape)


def gradient(values, spacing, *, xp=jnp, native_edges=False):
    """Centred interior and one-sided edges; native divergence reverses edges."""
    sign = -1 if native_edges else 1
    dx = (
        xp.concatenate(
            (
                sign * (values[..., :, 1:2] - values[..., :, :1]),
                0.5 * (values[..., :, 2:] - values[..., :, :-2]),
                sign * (values[..., :, -1:] - values[..., :, -2:-1]),
            ),
            axis=-1,
        )
        / spacing
    )
    dy = (
        xp.concatenate(
            (
                sign * (values[..., 1:2, :] - values[..., :1, :]),
                0.5 * (values[..., 2:, :] - values[..., :-2, :]),
                sign * (values[..., -1:, :] - values[..., -2:-1, :]),
            ),
            axis=-2,
        )
        / spacing
    )
    return dx, dy


def smooth(values, *, xp=jnp):
    """Sigma=1/radius=4 Gaussian, separable and zero-padded like the pinned law."""
    kernel = xp.exp(-0.5 * xp.arange(-4, 5, dtype=values.dtype) ** 2)
    kernel /= xp.sum(kernel)
    rows, cols = values.shape
    padded = xp.pad(values, ((4, 4), (0, 0)))
    vertical = sum(kernel[k] * padded[k : k + rows, :] for k in range(9))
    padded = xp.pad(vertical, ((0, 0), (4, 4)))
    return sum(kernel[k] * padded[:, k : k + cols] for k in range(9))


def ownership(p, *, xp=jnp):
    cells = (xp.arange(p.cell_volume.size)[:, None] == p.cell_owner).astype(p.cell_volume.dtype)
    outside = (xp.arange(p.boundary_values.size)[:, None] == p.outside_owner).astype(
        p.cell_volume.dtype
    )
    return cells, outside


def charge_density(concentration, valence, extra, *, xp=jnp):
    """Sum ionic charge before scaling by F, retaining cancellation residuals.

    Nearly neutral mixtures subtract large positive and negative contributions.
    Scaling every ion by F before a dot product magnifies backend rounding into
    the voltage driving the gates. Neumaier summation preserves the same charge
    equation; barriers keep compiled reassociation from discarding its residuals.
    """

    def retain(value):
        return jax.lax.optimization_barrier(value) if xp is jnp else value

    total = xp.zeros_like(concentration[0])
    correction = xp.zeros_like(total)
    for i in range(valence.size):
        term = retain(valence[i] * concentration[i])
        updated = retain(total + term)
        residual = xp.where(
            xp.abs(total) >= xp.abs(term),
            retain(total - updated) + term,
            retain(term - updated) + total,
        )
        correction = retain(correction + residual)
        total = updated
    return retain((total + correction) * F) + extra


def field(state, p, *, xp=jnp):
    cells, outside = ownership(p, xp=xp)
    phi = boundary_field(p.boundary_values, xp=xp)
    rho = charge_density(state.cell_concentration, p.valence, p.extra_cell_charge_density, xp=xp)
    cell_area = cells @ p.membrane_area
    cell_v = rho * (p.cell_volume / cell_area) / p.capacitance_density
    vm = cell_v[p.cell_owner] - phi.ravel()[p.outside_owner]
    rho_out = charge_density(
        state.outside_concentration, p.valence, p.extra_outside_charge_density, xp=xp
    )
    grid_area = outside @ p.membrane_area
    mean_area = xp.mean(grid_area[p.outside_owner])
    voxel = p.height * p.spacing**2
    surface = xp.where(grid_area > 0, rho_out * voxel / mean_area, 0)
    screened = surface.reshape(phi.shape) / (p.screening_wavenumber * p.permittivity)
    potential = smooth(screened, xp=xp) + phi
    scale = 2 / (p.screening_wavenumber * p.spacing) * p.cell_size_ratio
    gx, gy = gradient(scale * potential, p.spacing, xp=xp)
    return Field(vm, (cells @ vm) / xp.sum(cells, axis=1), rho, phi, potential, -gx, -gy)


def validate_layout(layout):
    p = Layout(*(np.asarray(v) for v in layout))
    n, m, s = p.cell_volume.size, p.membrane_area.size, p.valence.size
    shape, o = p.boundary_values.shape, p.boundary_values.size
    dirichlet_operator(shape)
    for key, expected in {
        "cell_volume": (n,),
        "membrane_area": (m,),
        "cell_owner": (m,),
        "outside_owner": (m,),
        "partner": (m,),
        "moving": (s,),
        "valence": (s,),
        "membrane_permeability": (s, m),
        "junction_permeability": (s, m),
        "membrane_open": (m,),
        "junction_open": (m,),
        "diffusivity": (s, *shape),
        "boundary_concentration": (s,),
        "extra_cell_charge_density": (n,),
        "extra_outside_charge_density": (o,),
        **{key: () for key in Layout._fields[16:]},
    }.items():
        if getattr(p, key).shape != expected:
            raise ValueError("Compatibility layout shape: " + key)
    if min(n, m, s) < 1 or p.moving.dtype != np.bool_ or not p.moving.any():
        raise ValueError("Require real cells, patches and moving species")
    for key, limit in (("cell_owner", n), ("outside_owner", o), ("partner", m)):
        v = getattr(p, key)
        if v.dtype.kind not in "iu" or np.any((v < 0) | (v >= limit)):
            raise ValueError("Compatibility ownership: " + key)
    if not np.array_equal(p.partner[p.partner], np.arange(m)):
        raise ValueError("Junction partners must be reciprocal")
    if not np.array_equal(p.membrane_area, p.membrane_area[p.partner]):
        # Native geometry can differ by last-bit polygon area roundoff.
        if not np.allclose(p.membrane_area, p.membrane_area[p.partner], rtol=5e-14, atol=0):
            raise ValueError("Junction areas must match")
    if not np.allclose(p.junction_open, p.junction_open[p.partner], rtol=0, atol=0):
        raise ValueError("Junction controls must be symmetric")
    if not np.allclose(
        p.junction_permeability, p.junction_permeability[:, p.partner], rtol=5e-14, atol=0
    ):
        raise ValueError("Junction permeability must be symmetric")
    if set(p.cell_owner) != set(range(n)):
        raise ValueError("Each cell needs a membrane")
    for key, value in p._asdict().items():
        if not np.isfinite(value).all():
            raise ValueError("Nonfinite compatibility layout: " + key)
    for key in ("cell_volume", "membrane_area", "boundary_concentration", *Layout._fields[16:]):
        if np.any(getattr(p, key) <= 0):
            raise ValueError("Positive compatibility parameter required: " + key)
    for key in ("membrane_permeability", "junction_permeability", "diffusivity"):
        if np.any(getattr(p, key) < 0):
            raise ValueError("Nonnegative transport required")
    for key in ("membrane_open", "junction_open"):
        if np.any((getattr(p, key) < 0) | (getattr(p, key) > 1)):
            raise ValueError("Availability must be in [0, 1]")
    return p


def initial_state(cell, membrane, outside, p):
    cell, membrane, outside = (np.asarray(v, dtype=np.float64) for v in (cell, membrane, outside))
    if (
        cell.shape != (p.valence.size, p.cell_volume.size)
        or membrane.shape != p.membrane_permeability.shape
    ):
        raise ValueError("Initial cell/membrane shape")
    if outside.shape != (p.valence.size, p.boundary_values.size):
        raise ValueError("Initial outside shape")
    if not all(np.isfinite(v).all() and (v > 0).all() for v in (cell, membrane, outside)):
        raise ValueError("Initial concentrations must be finite and positive")
    return State(
        cell.copy(),
        membrane.copy(),
        outside.copy(),
        np.zeros_like(membrane),
        np.zeros_like(membrane),
        np.zeros_like(outside),
        np.zeros_like(outside),
        np.asarray(0, dtype=np.int64),
        np.asarray(0.0),
    )


def domain_valid(state, *, xp=jnp):
    return (
        xp.all(xp.stack([xp.all(xp.isfinite(v)) for v in state]))
        & xp.all(state.cell_concentration > 0)
        & xp.all(state.membrane_concentration > 0)
        & xp.all(state.outside_concentration > 0)
        & (state.step_count >= 0)
        & (state.elapsed_s >= 0)
    )


def transport(state, p, dt, *, xp=jnp):
    """Old-state passive rates and exterior update, before membrane transfer."""
    f = field(state, p, xp=xp)
    z = p.valence[:, None]
    membrane = ghk_leak(
        state.membrane_concentration,
        state.outside_concentration[:, p.outside_owner],
        f.membrane_voltage_V,
        z,
        p.temperature,
        p.membrane_area,
        p.membrane_permeability,
        p.membrane_open,
        xp=xp,
    )
    junction = selective_flux(
        state.membrane_concentration,
        state.membrane_concentration[:, p.partner],
        f.membrane_voltage_V - f.membrane_voltage_V[p.partner],
        z,
        p.temperature,
        p.membrane_area,
        p.junction_permeability,
        0.0,
        1.0,
        p.junction_open,
        xp=xp,
    )
    membrane = xp.where(p.moving[:, None], membrane, 0)
    junction = xp.where(p.moving[:, None], junction, 0)
    co = state.outside_concentration.reshape(p.diffusivity.shape)
    reset = xp.where(
        p.moving[:, None, None] & boundary_mask(p.boundary_values.shape, xp=xp),
        p.boundary_concentration[:, None, None],
        co,
    )
    gx, gy = gradient(reset, p.spacing, xp=xp)
    mobility = p.diffusivity * p.valence[:, None, None] * p.native_q_over_kb / p.temperature
    fx = -p.diffusivity * gx + mobility * f.outside_field_x_V_m * reset
    fy = -p.diffusivity * gy + mobility * f.outside_field_y_V_m * reset
    fx, fy = (xp.where(p.moving[:, None, None], v, 0) for v in (fx, fy))
    delta = dt * (
        gradient(-fx, p.spacing, xp=xp, native_edges=True)[0]
        + gradient(-fy, p.spacing, xp=xp, native_edges=True)[1]
    )
    return Rates(membrane, junction, fx, fy), reset, delta, f


def step(state, p, dt, *, xp=jnp):
    """One native-order trial; return unchanged state on an invalid trial."""
    cells, outside = ownership(p, xp=xp)
    rates, reset, delta, f = transport(state, p, dt, xp=xp)
    membrane, junction, _, _ = rates
    co = state.outside_concentration.reshape(p.diffusivity.shape)
    voxel_fmol = p.height * p.spacing**2 * 1e15
    cell_after_mem = state.cell_concentration + dt * (membrane @ cells.T) / (p.cell_volume * 1e15)
    candidate = State(
        cell_after_mem - dt * (junction @ cells.T) / (p.cell_volume * 1e15),
        xp.where(p.moving[:, None], cell_after_mem[:, p.cell_owner], state.membrane_concentration),
        (reset + delta).reshape(state.outside_concentration.shape)
        - dt * (membrane @ outside.T) / voxel_fmol,
        state.membrane_inward_fmol + dt * membrane,
        state.junction_outward_fmol + dt * junction,
        state.reservoir_reset_fmol
        + ((reset - co) * voxel_fmol).reshape(state.outside_concentration.shape),
        state.stencil_exchange_fmol
        + (delta * voxel_fmol).reshape(state.outside_concentration.shape),
        state.step_count + 1,
        state.elapsed_s + dt,
    )
    valid = domain_valid(state, xp=xp) & domain_valid(candidate, xp=xp) & xp.isfinite(dt) & (dt > 0)
    valid &= xp.all(xp.stack([xp.all(xp.isfinite(v)) for v in (*f, *rates)]))
    accepted = State(
        *(xp.where(valid, new, old) for new, old in zip(candidate, state, strict=True))
    )
    return accepted, rates, valid


def trajectory(state, p, dt, steps):
    """JAX scan with latched failure; all state remains fixed after rejection."""

    def one(carry, _):
        old, ok = carry
        trial, rates, valid = step(old, p, dt)
        ok &= valid
        new = jax.tree.map(lambda x, y: jnp.where(ok, x, y), trial, old)
        return (new, ok), (new, rates, ok)

    (final, valid), history = jax.lax.scan(one, (state, jnp.asarray(True)), None, length=steps)
    return final, history, valid


def trajectories(states, layouts, dt, steps):
    """Independent worlds with the same runtime timestep and full scan outputs."""
    return jax.lax.map(lambda args: trajectory(args[0], args[1], dt, steps), (states, layouts))


def accounting(initial, state, p):
    """Independent inventory reconstruction from complete transfer ledgers."""
    cells, outside = ownership(p, xp=np)
    dc = (state.cell_concentration - initial.cell_concentration) * p.cell_volume * 1e15
    de = (
        (state.outside_concentration - initial.outside_concentration)
        * p.height
        * p.spacing**2
        * 1e15
    )
    mem = state.membrane_inward_fmol - initial.membrane_inward_fmol
    gap = state.junction_outward_fmol - initial.junction_outward_fmol
    supply = state.reservoir_reset_fmol - initial.reservoir_reset_fmol
    stencil = state.stencil_exchange_fmol - initial.stencil_exchange_fmol
    return dict(
        cell_residual_fmol=dc - (mem - gap) @ cells.T,
        outside_residual_fmol=de + mem @ outside.T - supply - stencil,
        global_residual_fmol=dc.sum(axis=1)
        + de.sum(axis=1)
        - supply.sum(axis=1)
        - stencil.sum(axis=1),
    )
