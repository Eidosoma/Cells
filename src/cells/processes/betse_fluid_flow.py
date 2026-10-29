"""Standalone literal BETSE 1.5.0 flow with explicit, caller-owned operators.

Cell output is m/s. The ECM source applies an inverse Laplacian to a slip
velocity and consequently returns m3/s; it must not silently feed an m/s
advection port. HH potentials are numeric auxiliaries, never pressure in Pa.
No pressure, volume, geometry, time history or energy state is advanced here.
"""

import hashlib
import json
from dataclasses import dataclass
from typing import NamedTuple

import jax.numpy as jnp
import numpy as np

from cells.processes import betse_deformation as mechanics
from cells.processes.betse_environment_transport import source_gradient
from cells.processes.betse_geometry import GridBinding

LAW_ID = "betse_fluid_flow_source_v1_5_0@1"


class CellForcing(NamedTuple):
    electric_field_V_m: object  # [...,2,cell]
    charge_density_C_m3: object  # [...,cell], signed


class CellParameters(NamedTuple):
    viscosity_Pa_s: object  # scalar or [...,1]
    gap_junction_fraction: object  # dimensionless, scalar or [...,1]


class CellResult(NamedTuple):
    divided_body_force_per_m_s: object
    unprojected_velocity_m_s: object
    stream_potential_m2_s: object
    velocity_m_s: object
    divergence_numeric_per_s: object


class EnvironmentForcing(NamedTuple):
    electric_field_V_m: object  # [...,2,ny,nx]
    potential_V: object  # [...,ny,nx], literal absolute v_env, not inferred zeta
    diffusion_weight: object  # [...,ny,nx], supplied, no barrier reconstruction


class EnvironmentParameters(NamedTuple):
    viscosity_Pa_s: object
    vacuum_permittivity_F_m: object
    relative_permittivity: object


class EnvironmentOperators(NamedTuple):
    laplacian_inverse_m2: object
    delta_m: object


class EnvironmentResult(NamedTuple):
    slip_velocity_m_s: object
    unprojected_native_m3_s: object
    stream_potential_native_m4_s: object
    output_native_m3_s: object
    discarded_scalar_native_m4_s: object
    discarded_gradient_native_m3_s: object
    divergence_numeric_m2_s: object


@dataclass(frozen=True)
class CellBinding:
    owner_ids: tuple
    operators: mechanics.Operators
    provenance_json: str
    identity: str


@dataclass(frozen=True)
class EnvironmentBinding:
    owner_ids: tuple
    shape: tuple
    operators: EnvironmentOperators
    geometry_identity: str
    identity: str


class FlowResult(NamedTuple):
    cells: CellResult
    environment: EnvironmentResult | None


def _identity(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def bind_cells(owner_ids, operators, provenance):
    """Bind an already qualified mechanics operator; never build/reorder geometry."""
    ids = tuple(owner_ids)
    if (
        not ids
        or any(not isinstance(v, str) or not v for v in ids)
        or len(set(ids)) != len(ids)
        or not isinstance(provenance, dict)
        or not provenance
    ):
        raise ValueError("Require explicit unique cell owner IDs and nonempty provenance")
    op = mechanics.validate_operators(operators)
    if len(ids) != op.active.size or not op.active.all():
        raise ValueError("Bind exactly the supplied active cell axis; no implicit padding/remap")
    frozen = []
    for value in op:
        a = np.array(value, copy=True)
        a.flags.writeable = False
        frozen.append(a)
    op = mechanics.Operators(*frozen)
    provenance_json = json.dumps(provenance, sort_keys=True, allow_nan=False)
    identity = _identity(dict(ids=ids, operators=[v.tolist() for v in op], provenance=provenance))
    return CellBinding(ids, op, provenance_json, identity)


def bind_environment(grid):
    """Reuse source voltage-grid inverse, including its boundary and SVD semantics."""
    if not isinstance(grid, GridBinding) or any(v != "value" for v in grid.boundaries.values()):
        raise ValueError("getFlow uses the explicit all-value voltage grid inverse")
    op = EnvironmentOperators(grid.kernel.pseudoinverse, grid.delta_m)
    return EnvironmentBinding(
        grid.environment_ids,
        grid.shape,
        op,
        grid.identity,
        _identity(dict(law=LAW_ID, geometry=grid.identity, convention="native-voltage-inverse")),
    )


def _field(value, trailing, *, xp):
    v = xp.asarray(value)
    if v.dtype.kind not in "fiu" or v.ndim < len(trailing) or v.shape[-len(trailing) :] != trailing:
        raise ValueError("Require real fields on the explicit trailing owner/vector/grid axes")
    return v


def _parameters(parameters, *, xp):
    result = []
    for value in parameters:
        v = xp.asarray(value)
        if v.dtype.kind not in "fiu":
            raise ValueError("Require real parameters")
        if not v.ndim:
            v = v.reshape((1,))
        if v.shape[-1] != 1:
            raise ValueError("Parameters require scalar or singleton final world axes")
        result.append(v)
    return result


def _mat(matrix, value, *, xp):
    return xp.einsum("ij,...j->...i", xp.asarray(matrix), value)


def cell_flow(forcing, operators, parameters, *, xp=jnp):
    """Literal divided Coulomb force -> inverse -> actual cell curl/inverse/curl."""
    n = operators.active.size
    e = _field(forcing.electric_field_V_m, (2, n), xp=xp)
    rho = _field(forcing.charge_density_C_m3, (n,), xp=xp)
    mu, fraction = _parameters(parameters, xp=xp)
    body = e * rho[..., None, :] * (fraction / mu)[..., None, :]
    raw = _mat(operators.laplacian_inverse, -body, xp=xp)
    potential, velocity = mechanics.rotation_only(raw, operators, xp=xp)
    return CellResult(
        body, raw, potential, velocity, mechanics.divergence_numeric(velocity, operators, xp=xp)
    )


def cell_valid(forcing, operators, parameters, *, xp=jnp):
    n = operators.active.size
    e = _field(forcing.electric_field_V_m, (2, n), xp=xp)
    rho = _field(forcing.charge_density_C_m3, (n,), xp=xp)
    mu, fraction = _parameters(parameters, xp=xp)
    return (
        xp.all(xp.isfinite(e), axis=(-2, -1))
        & xp.all(xp.isfinite(rho), axis=-1)
        & xp.all(xp.isfinite(mu) & (mu > 0), axis=-1)
        & xp.all(xp.isfinite(fraction) & (fraction >= 0) & (fraction <= 1), axis=-1)
    )


def _environment(forcing, operators, *, xp):
    e = xp.asarray(forcing.electric_field_V_m)
    if e.ndim < 3 or e.shape[-3] != 2 or min(e.shape[-2:]) < 2:
        raise ValueError("Environment electric field requires [...,2,ny>=2,nx>=2]")
    shape = e.shape[-2:]
    e = _field(e, (2, *shape), xp=xp)
    phi = _field(forcing.potential_V, shape, xp=xp)
    weight = _field(forcing.diffusion_weight, shape, xp=xp)
    inv = xp.asarray(operators.laplacian_inverse_m2)
    if inv.dtype.kind not in "fiu" or inv.shape != (shape[0] * shape[1],) * 2:
        raise ValueError("Require the explicit environment inverse on the same owner axis")
    delta = xp.asarray(operators.delta_m)
    if delta.ndim or delta.dtype.kind not in "fiu":
        raise ValueError("Require a scalar, geometry-owned spacing")
    return e, phi, weight, inv, delta


def environment_flow(forcing, operators, parameters, *, xp=jnp):
    """Literal getFlow ECM law; output units deliberately retain the source defect."""
    e, phi, weight, inv, h = _environment(forcing, operators, xp=xp)
    mu, epsilon, er = _parameters(parameters, xp=xp)
    slip = (
        -(epsilon * er / mu)[..., None, None] * e * phi[..., None, :, :] * weight[..., None, :, :]
    )
    shape = slip.shape[-2:]

    def solve(value):
        flat = value.reshape(value.shape[:-2] + (-1,))
        return _mat(inv, flat, xp=xp).reshape(value.shape)

    raw = solve(-slip)
    # Source divergence reverses its one-sided boundary derivative signs.
    dx, _ = source_gradient(-raw[..., 1, :, :], h, negative_boundary=True, xp=xp)
    _, dy = source_gradient(raw[..., 0, :, :], h, negative_boundary=True, xp=xp)
    interior = xp.asarray(
        [
            [0 < i < shape[0] - 1 and 0 < j < shape[1] - 1 for j in range(shape[1])]
            for i in range(shape[0])
        ]
    )
    stream = solve(xp.where(interior, -dx - dy, 0.0))
    gx, gy = source_gradient(stream, h, xp=xp)
    output = xp.stack((-gy, gx), axis=-3)
    dx, _ = source_gradient(raw[..., 0, :, :], h, negative_boundary=True, xp=xp)
    _, dy = source_gradient(raw[..., 1, :, :], h, negative_boundary=True, xp=xp)
    scalar = solve(xp.where(interior, dx + dy, 0.0))
    scalar_gradient = xp.stack(source_gradient(scalar, h, xp=xp), axis=-3)
    dx, _ = source_gradient(output[..., 0, :, :], h, negative_boundary=True, xp=xp)
    _, dy = source_gradient(output[..., 1, :, :], h, negative_boundary=True, xp=xp)
    return EnvironmentResult(slip, raw, stream, output, scalar, scalar_gradient, dx + dy)


def environment_valid(forcing, operators, parameters, *, xp=jnp):
    e, phi, weight, inv, h = _environment(forcing, operators, xp=xp)
    p = _parameters(parameters, xp=xp)
    valid = (
        xp.all(xp.isfinite(e), axis=(-3, -2, -1))
        & xp.all(xp.isfinite(phi), axis=(-2, -1))
        & xp.all(xp.isfinite(weight) & (weight >= 0), axis=(-2, -1))
        & xp.all(xp.isfinite(inv))
        & xp.isfinite(h)
        & (h > 0)
    )
    for value in p:
        valid &= xp.all(xp.isfinite(value) & (value > 0), axis=-1)
    return valid


def flow(forcing, binding, parameters, *, fluid_flow=False, environment=None):
    """Host gate defaults to the disabled loader policy and makes no state writes.

    environment is an explicit (forcing, binding, parameters) triple, or None.
    Bare kernels are for qualified/JIT numeric diagnostics; this host gate
    checks domains and ownership. Enabling it does not enable BETSE itself.
    """
    if type(fluid_flow) is not bool:
        raise ValueError("Require an explicit boolean flow policy")
    if not fluid_flow:
        return None
    if not isinstance(binding, CellBinding) or not np.all(
        cell_valid(forcing, binding.operators, parameters, xp=np)
    ):
        raise ValueError("Invalid cell flow domain/binding")
    env_result = None
    if environment is not None:
        ef, eb, ep = environment
        if (
            not isinstance(eb, EnvironmentBinding)
            or np.shape(ef.electric_field_V_m)[-2:] != eb.shape
            or not np.all(environment_valid(ef, eb.operators, ep, xp=np))
        ):
            raise ValueError("Invalid native ECM domain/binding")
        env_result = environment_flow(ef, eb.operators, ep, xp=np)
    return FlowResult(cell_flow(forcing, binding.operators, parameters, xp=np), env_result)


def grn_current_flow(current_A_m2, concentration_mol_m3, valence, faraday_C_mol, *, xp=jnp):
    """Separate native GRN recalculation formula; no HH, voltage or cell flow."""
    current = xp.asarray(current_A_m2)
    if current.ndim < 3 or current.shape[-3] != 2:
        raise ValueError("Require a [...,2,ny,nx] current field")
    current = _field(current, current.shape[-3:], xp=xp)
    c = xp.asarray(concentration_mol_m3)
    z = xp.asarray(valence)
    if c.ndim < 3 or z.ndim != 1 or c.shape[-3] != z.size or not z.size:
        raise ValueError("Require explicit species concentration and shared valence axes")
    c = _field(c, (z.size, *current.shape[-2:]), xp=xp)
    if z.dtype.kind not in "fiu":
        raise ValueError("Require real valences")
    faraday = _parameters((faraday_C_mol,), xp=xp)[0]
    return -current / (faraday[..., None, None] * xp.mean(c, axis=-3)[..., None, :, :] * xp.mean(z))


def grn_valid(current_A_m2, concentration_mol_m3, valence, faraday_C_mol, *, xp=jnp):
    # Shape validation stays shared with the literal kernel; no denominator floor.
    value = grn_current_flow(current_A_m2, concentration_mol_m3, valence, faraday_C_mol, xp=xp)
    c, z, f = (xp.asarray(v) for v in (concentration_mol_m3, valence, faraday_C_mol))
    valid = (
        xp.all(xp.isfinite(value), axis=(-3, -2, -1))
        & xp.all(xp.isfinite(c) & (c >= 0), axis=(-3, -2, -1))
        & xp.all(xp.mean(c, axis=-3) > 0, axis=(-2, -1))
        & xp.all(xp.isfinite(z))
        & (xp.mean(z) != 0)
        & xp.all(xp.isfinite(f) & (f > 0), axis=-1 if f.ndim else None)
    )
    return valid
