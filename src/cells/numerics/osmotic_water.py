"""Conservative neutral-water exchange between finite compliant compartments.

Amounts are fmol, volumes pL, pressure Pa and energy pJ. Interfaces and their
areas stay fixed. The water potential is P - Pi; it is a derivative of the
declared mixing plus elastic free energy, not an imposed concentration reset.
"""

from typing import NamedTuple

import numpy as np

from cells.numerics.extracellular_field import ordered_scatter
from cells.processes.electrochemistry import R

LAW_ID = "ideal_osmosis_linear_compliance_water@1"


class Parameters(NamedTuple):
    temperature_K: object
    active: object
    reference_volume_pL: object
    minimum_volume_pL: object
    maximum_volume_pL: object
    impermeant_amount_fmol: object
    bulk_modulus_Pa: object
    pressure_offset_Pa: object
    edge_active: object
    sender: object
    receiver: object
    conductance_pL_per_Pa_s: object


class Values(NamedTuple):
    volume_rate_pL_s: object
    edge_flow_pL_s: object
    osmotic_pressure_Pa: object
    hydrostatic_pressure_Pa: object
    water_potential_Pa: object
    mixing_energy_pJ: object
    elastic_energy_pJ: object
    free_energy_pJ: object
    edge_dissipation_pJ_s: object
    dissipation_pJ_s: object
    mixing_energy_rate_pJ_s: object
    elastic_energy_rate_pJ_s: object
    energy_balance_pJ_s: object


def validate_parameters(p):
    """Host-side shape, owner, unit-domain and inactive-padding contract."""
    active, edges = np.asarray(p.active), np.asarray(p.edge_active)
    if (
        active.ndim != 1
        or active.dtype != np.bool_
        or not np.any(active)
        or edges.ndim != 1
        or edges.dtype != np.bool_
    ):
        raise ValueError("Water nodes/edges require explicit one-dimensional boolean masks")
    n, e = active.size, edges.size
    values = dict(active=active, edge_active=edges)
    for name in Parameters._fields:
        if name in values:
            continue
        value = np.asarray(getattr(p, name))
        if name in ("sender", "receiver"):
            if value.shape != (e,) or value.dtype.kind not in "iu":
                raise ValueError("Water edge owners require integer vectors")
            if np.any((value < 0) | (value >= n)):
                raise ValueError("Water edge owner outside padded node range")
            values[name] = value.astype(np.int64)
            continue
        shape = () if name == "temperature_K" else (e,) if name.startswith("conductance") else (n,)
        if value.shape != shape or value.dtype.kind not in "fiu" or not np.isfinite(value).all():
            raise ValueError("Invalid water parameter shape/domain: " + name)
        values[name] = value.astype(float)
    q = Parameters(**values)
    if (
        q.temperature_K <= 0
        or np.any(q.minimum_volume_pL <= 0)
        or np.any(q.reference_volume_pL <= q.minimum_volume_pL)
        or np.any(q.reference_volume_pL >= q.maximum_volume_pL)
        or np.any(q.impermeant_amount_fmol < 0)
        or np.any(q.bulk_modulus_Pa < 0)
        or np.any(q.conductance_pL_per_Pa_s < 0)
        or np.any(q.conductance_pL_per_Pa_s[~edges] != 0)
        or np.any(q.impermeant_amount_fmol[~active] != 0)
        or np.any(q.bulk_modulus_Pa[~active] != 0)
        or np.any(q.pressure_offset_Pa[~active] != 0)
        or np.any(edges & ((q.sender == q.receiver) | ~active[q.sender] | ~active[q.receiver]))
    ):
        raise ValueError("Invalid water volume bounds, material, mobility or active owners")
    return q


def domain_valid(volume_pL, amount_fmol, p, *, xp=np):
    """No clipping: trial volumes must stay inside the declared validity range."""
    volume, amount = xp.asarray(volume_pL), xp.asarray(amount_fmol)
    if volume.shape != p.active.shape or amount.ndim != 2 or amount.shape[-1] != volume.size:
        return xp.asarray(False)
    return (
        xp.all(xp.isfinite(volume))
        & xp.all(xp.isfinite(amount))
        & xp.all(amount >= 0)
        & xp.all(xp.where(p.active, volume > p.minimum_volume_pL, volume == 1.0))
        & xp.all(xp.where(p.active, volume < p.maximum_volume_pL, True))
        & xp.all(xp.where(p.active[None, :], True, amount == 0))
    )


def _scatter(values, indices, size, *, xp):
    return ordered_scatter(values, xp.zeros(size, dtype=values.dtype), (indices,), xp=xp)


def _mixing_terms(amount, volume, *, xp):
    # Exact continuous zero-amount limit. Invalid negative amounts remain invalid;
    # no logarithm floor or nonnegative projection changes a physical state.
    ratio = xp.where(amount == 0, 1.0, amount / volume)
    return amount * (xp.log(ratio) - 1.0)


def evaluate(volume_pL, amount_fmol, availability, p, *, xp=np):
    """Stage values; neutral solvent transfer never changes any solute amount.

    Positive edge flow is sender-to-receiver. Interface availability changes
    mobility only, so it adds no pressure source or hidden work term.
    """
    volume = xp.where(p.active, volume_pL, 1.0)
    amount = xp.asarray(amount_fmol)
    rt = R * p.temperature_K
    osmolytes = xp.sum(amount, axis=0) + p.impermeant_amount_fmol
    osmotic = xp.where(p.active, rt * osmolytes / volume, 0.0)
    extension = volume - p.reference_volume_pL
    hydrostatic = xp.where(
        p.active,
        p.bulk_modulus_Pa * extension / p.reference_volume_pL + p.pressure_offset_Pa,
        0.0,
    )
    potential = hydrostatic - osmotic
    drive = potential[p.sender] - potential[p.receiver]
    flow = xp.where(p.edge_active, p.conductance_pL_per_Pa_s * availability * drive, 0.0)
    rate = _scatter(flow, p.receiver, volume.size, xp=xp) - _scatter(
        flow, p.sender, volume.size, xp=xp
    )
    mixing = xp.where(
        p.active,
        1e-3
        * rt
        * (
            xp.sum(_mixing_terms(amount, volume[None, :], xp=xp), axis=0)
            + _mixing_terms(p.impermeant_amount_fmol, volume, xp=xp)
        ),
        0.0,
    )
    elastic = xp.where(
        p.active,
        1e-3
        * (
            0.5 * p.bulk_modulus_Pa * extension**2 / p.reference_volume_pL
            + p.pressure_offset_Pa * extension
        ),
        0.0,
    )
    heat = 1e-3 * flow * drive
    mixing_rate = -1e-3 * xp.sum(osmotic * rate)
    elastic_rate = 1e-3 * xp.sum(hydrostatic * rate)
    dissipated = xp.sum(heat)
    return Values(
        rate,
        flow,
        osmotic,
        hydrostatic,
        potential,
        mixing,
        elastic,
        xp.sum(mixing + elastic),
        heat,
        dissipated,
        mixing_rate,
        elastic_rate,
        mixing_rate + elastic_rate + dissipated,
    )


def relaxation_rate_bound(maximum_osmolyte_amount_fmol, p, *, xp=np):
    """Water-volume Jacobian row bound with the current solute amounts held fixed.

    The material upper bound covers the declared closed-volume regime and
    availability is at most one. This does not bound the full coupled ion/water
    Jacobian or establish accuracy. Coupled steppers must still reject every
    invalid intermediate/final trial and undergo independent refinement checks.
    """
    slope = xp.where(
        p.active,
        p.bulk_modulus_Pa / p.reference_volume_pL
        + R * p.temperature_K * maximum_osmolyte_amount_fmol / p.minimum_volume_pL**2,
        0.0,
    )
    edge = xp.where(
        p.edge_active,
        p.conductance_pL_per_Pa_s * (slope[p.sender] + slope[p.receiver]),
        0.0,
    )
    rate = _scatter(edge, p.sender, p.active.size, xp=xp) + _scatter(
        edge, p.receiver, p.active.size, xp=xp
    )
    return xp.max(rate, initial=0.0)
