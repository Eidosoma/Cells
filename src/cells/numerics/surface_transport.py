"""Resolved membrane surfaces and explicit open-compartment transport.

This component consumes absolute cell/outside potentials; it does not choose a
field closure. Multiple physical patches may join the same pair of owners.
Positive route flux is sender -> receiver, including cell -> outside membranes.
Reservoir supply is positive into the finite system and is never discarded.
"""

from typing import NamedTuple

import jax.numpy as jnp
import numpy as np

from cells.coupling.selective import selective_flux
from cells.numerics.extracellular_field import logmean, scatter
from cells.processes.electrochemistry import CHARGE_PER_FMOL, MOL_PER_FMOL, F, R

LAW_ID = "resolved_surface_transport_explicit_reservoirs@1"
VOLTAGE_ID = "cell_charge_area_resolved_capacitors@1"
MAX_ABS_X = 50.0


class Layout(NamedTuple):
    temperature: object
    valence: object
    cell_active: object
    outside_active: object
    reservoir: object
    membrane_active: object
    membrane_cell: object
    membrane_outside: object
    membrane_area: object
    membrane_capacitance: object
    membrane_permeability: object
    face_active: object
    face_sender: object
    face_receiver: object
    face_factor: object
    junction_active: object
    junction_sender: object
    junction_receiver: object
    junction_area: object
    junction_permeability: object


class Voltage(NamedTuple):
    cell_potential_V: object
    membrane_voltage_V: object
    membrane_charge_C: object
    outside_capacitor_charge_C: object
    cell_charge_residual_C: object
    capacitor_energy_pJ: object
    valid: object


class Rates(NamedTuple):
    cell_rate_fmol_s: object
    outside_rate_fmol_s: object
    reservoir_supply_fmol_s: object
    membrane_voltage_V: object
    membrane_flux_fmol_s: object
    membrane_delta_mu_J_mol: object
    membrane_current_A: object
    membrane_dissipation_pJ_s: object
    junction_voltage_V: object
    junction_flux_fmol_s: object
    junction_delta_mu_J_mol: object
    junction_current_A: object
    junction_dissipation_pJ_s: object
    face_voltage_V: object
    face_flux_fmol_s: object
    face_delta_mu_J_mol: object
    face_current_A: object
    face_dissipation_pJ_s: object
    valid: object


class ReservoirReset(NamedTuple):
    amount_fmol: object
    supplied_fmol: object
    valid: object


def validate_layout(layout):
    """Validate immutable host ownership before JIT; no implicit geometry repair."""
    p = Layout(*(np.asarray(v) for v in layout))
    n, o, m, f, e = (
        len(getattr(p, k))
        for k in (
            "cell_active",
            "outside_active",
            "membrane_active",
            "face_active",
            "junction_active",
        )
    )
    s = len(p.valence)
    shapes = {
        "temperature": (),
        "valence": (s, 1),
        "cell_active": (n,),
        "outside_active": (o,),
        "reservoir": (o,),
        "membrane_active": (m,),
        "membrane_cell": (m,),
        "membrane_outside": (m,),
        "membrane_area": (m,),
        "membrane_capacitance": (m,),
        "membrane_permeability": (s, m),
        "face_active": (f,),
        "face_sender": (f,),
        "face_receiver": (f,),
        "face_factor": (s, f),
        "junction_active": (e,),
        "junction_sender": (e,),
        "junction_receiver": (e,),
        "junction_area": (e,),
        "junction_permeability": (s, e),
    }
    if min(n, o, m, s) < 1 or any(getattr(p, k).shape != v for k, v in shapes.items()):
        raise ValueError("Invalid resolved-surface shapes")
    masks = (
        "cell_active",
        "outside_active",
        "reservoir",
        "membrane_active",
        "face_active",
        "junction_active",
    )
    if any(getattr(p, k).dtype != np.bool_ for k in masks):
        raise ValueError("Surface masks must be boolean")
    if not all(np.isfinite(v).all() for v in p) or p.temperature <= 0:
        raise ValueError("Surface geometry must be finite with positive temperature")
    if not np.any(p.cell_active) or not np.any(p.outside_active):
        raise ValueError("Surface geometry requires active cell and outside owners")
    if np.any(p.reservoir & ~p.outside_active):
        raise ValueError("Reservoir must be an active outside owner")
    if np.any(p.valence != np.rint(p.valence)) or np.any(np.abs(p.valence) > 8):
        raise ValueError("Require integer valences in [-8,8]")
    for key, size in (
        ("membrane_cell", n),
        ("membrane_outside", o),
        ("face_sender", o),
        ("face_receiver", o),
        ("junction_sender", n),
        ("junction_receiver", n),
    ):
        v = getattr(p, key)
        if not np.issubdtype(v.dtype, np.integer) or np.any((v < 0) | (v >= size)):
            raise ValueError("Invalid resolved-surface owner: " + key)
    for prefix, src_active, dst_active, src, dst in (
        ("membrane", p.cell_active, p.outside_active, p.membrane_cell, p.membrane_outside),
        ("face", p.outside_active, p.outside_active, p.face_sender, p.face_receiver),
        ("junction", p.cell_active, p.cell_active, p.junction_sender, p.junction_receiver),
    ):
        active = getattr(p, prefix + "_active")
        if np.any(active & (~src_active[src] | ~dst_active[dst])):
            raise ValueError("Every route must join active owners")
        if prefix != "membrane":
            if np.any(active & (src == dst)):
                raise ValueError("Transport route cannot join an owner to itself")
            pairs = [
                tuple(sorted((int(a), int(b))))
                for a, b in zip(src[active], dst[active], strict=True)
            ]
            if len(pairs) != len(set(pairs)):
                raise ValueError("Extracellular/junction route must be owned once")
        for key in {
            "membrane": ("area", "capacitance", "permeability"),
            "face": ("factor",),
            "junction": ("area", "permeability"),
        }[prefix]:
            v = getattr(p, prefix + "_" + key)
            if np.any(v < 0) or np.any(v[..., ~active] != 0):
                raise ValueError("Negative route coefficient or nonzero padding")
            if key in ("area", "capacitance") and np.any(v[active] <= 0):
                raise ValueError("Active surface area and capacitance must be positive")
    count = np.bincount(p.membrane_cell[p.membrane_active], minlength=n)
    if np.any(p.cell_active & (count == 0)):
        raise ValueError("Every cell requires at least one membrane surface")
    return p


def _sum(values, owners, size, *, xp):
    return scatter(
        values, xp.zeros((*values.shape[:-1], size), dtype=values.dtype), (owners,), xp=xp
    )


def _domain_arrays(ci, co, cell_potential, outside_potential, p):
    s, n, o = p.valence.shape[0], p.cell_active.size, p.outside_active.size
    if (ci.shape, co.shape, cell_potential.shape, outside_potential.shape) != (
        (s, n),
        (s, o),
        (n,),
        (o,),
    ):
        raise ValueError("Surface state shape disagrees with geometry")


def from_cell_charge(charge_C, outside_potential_V, p, *, xp=jnp):
    """Resolve patch voltages from total cell capacitor charge and supplied field.

    psi_i = (Q_i + sum_m C_m phi_out(m)) / sum_m C_m.
    This preserves one equipotential cytosol and each individual patch voltage.
    Returned outside countercharge is a constraint for the eventual field model;
    it is not inferred to equal extracellular ionic charge by this function.
    """
    if charge_C.shape != p.cell_active.shape or outside_potential_V.shape != p.outside_active.shape:
        raise ValueError("Surface voltage inputs disagree with geometry")
    owner, outside = p.membrane_cell, p.membrane_outside
    cap = p.membrane_capacitance
    total = _sum(cap, owner, p.cell_active.size, xp=xp)
    weighted = _sum(cap * outside_potential_V[outside], owner, p.cell_active.size, xp=xp)
    psi = xp.where(p.cell_active, (charge_C + weighted) / xp.where(p.cell_active, total, 1.0), 0.0)
    vm = xp.where(p.membrane_active, psi[owner] - outside_potential_V[outside], 0.0)
    q = cap * vm
    residual = _sum(q, owner, p.cell_active.size, xp=xp) - charge_C
    values = (
        psi,
        vm,
        q,
        -_sum(q, outside, p.outside_active.size, xp=xp),
        residual,
        0.5e12 * cap * vm**2,
    )
    valid = (
        xp.all(xp.isfinite(charge_C))
        & xp.all(xp.isfinite(outside_potential_V))
        & xp.all(xp.where(p.cell_active, True, charge_C == 0))
        & xp.all(xp.abs(p.valence * F * vm / (R * p.temperature)) <= MAX_ABS_X)
        & xp.all(xp.isfinite(psi))
        & xp.all(xp.isfinite(q))
    )
    for value in values:
        valid = valid & xp.all(xp.isfinite(value))
    return Voltage(*(xp.where(valid, v, xp.nan) for v in values), valid)


def transport(
    ci, co, cell_potential_V, outside_potential_V, membrane_open, junction_open, p, *, xp=jnp
):
    """Float64 point laws and separate finite-owner/reservoir material rates.

    Potentials are absolute within one supplied gauge, concentrations in mM.
    Gates/availability are already-composed fractions; no channel kinetics or
    time integration is implicit. Reservoir concentrations must be supplied by
    the caller's declared boundary schedule, optionally via reset_reservoirs.
    """
    _domain_arrays(ci, co, cell_potential_V, outside_potential_V, p)
    if (
        membrane_open.shape != p.membrane_active.shape
        or junction_open.shape != p.junction_active.shape
    ):
        raise ValueError("Surface controls disagree with geometry")
    valid = (
        xp.all(xp.isfinite(ci) & (ci > 0))
        & xp.all(xp.isfinite(co) & (co > 0))
        & xp.all(xp.isfinite(cell_potential_V))
        & xp.all(xp.isfinite(outside_potential_V))
    )
    for control in (membrane_open, junction_open):
        valid = valid & xp.all(xp.isfinite(control) & (control >= 0) & (control <= 1))
    rt, z = R * p.temperature, p.valence
    route_values = []
    for prefix, left, right, dv, opening in (
        (
            "membrane",
            ci[:, p.membrane_cell],
            co[:, p.membrane_outside],
            cell_potential_V[p.membrane_cell] - outside_potential_V[p.membrane_outside],
            membrane_open,
        ),
        (
            "junction",
            ci[:, p.junction_sender],
            ci[:, p.junction_receiver],
            cell_potential_V[p.junction_sender] - cell_potential_V[p.junction_receiver],
            junction_open,
        ),
        (
            "face",
            co[:, p.face_sender],
            co[:, p.face_receiver],
            outside_potential_V[p.face_sender] - outside_potential_V[p.face_receiver],
            None,
        ),
    ):
        active = getattr(p, prefix + "_active")
        left, right = xp.where(active, left, 1.0), xp.where(active, right, 1.0)
        dv = xp.where(active, dv, 0.0)
        mu = rt * (xp.log(left) - xp.log(right)) + z * F * dv
        if prefix == "face":
            mean, _ = logmean(left, right, xp=xp)
            flux = p.face_factor * mean * mu / (rt * MOL_PER_FMOL)
        else:
            flux = selective_flux(
                left,
                right,
                dv,
                z,
                p.temperature,
                getattr(p, prefix + "_area"),
                getattr(p, prefix + "_permeability"),
                0.0,
                1.0,
                opening,
                xp=xp,
            )
        flux, mu = xp.where(active, flux, 0.0), xp.where(active, mu, 0.0)
        current = CHARGE_PER_FMOL * xp.sum(z * flux, axis=0)
        dissipation = 1e-3 * xp.sum(flux * mu, axis=0)
        route_values.append((dv, flux, mu, current, dissipation))
        valid = valid & xp.all(xp.abs(z * F * dv / rt) <= MAX_ABS_X)
        valid = valid & xp.all(xp.isfinite(flux)) & xp.all(xp.isfinite(dissipation))
    membrane, junction, face = [v[1] for v in route_values]
    cell = -_sum(membrane, p.membrane_cell, p.cell_active.size, xp=xp)
    cell += _sum(-junction, p.junction_sender, p.cell_active.size, xp=xp)
    cell += _sum(junction, p.junction_receiver, p.cell_active.size, xp=xp)
    outside = _sum(membrane, p.membrane_outside, p.outside_active.size, xp=xp)
    outside += _sum(-face, p.face_sender, p.outside_active.size, xp=xp)
    outside += _sum(face, p.face_receiver, p.outside_active.size, xp=xp)
    supply = xp.where(p.reservoir, -outside, 0.0)
    finite = xp.where(p.reservoir, 0.0, outside)
    values = (cell, finite, supply, *(v for route in route_values for v in route))
    for value in values:
        valid = valid & xp.all(xp.isfinite(value))
    return Rates(*(xp.where(valid, v, xp.nan) for v in values), valid)


def reset_reservoirs(amount_fmol, prescribed_mM, volume_pL, p, *, xp=jnp):
    """Explicit boundary reset and signed injection, in fmol; never a positivity repair."""
    shape = (p.valence.shape[0], p.outside_active.size)
    if (
        amount_fmol.shape != shape
        or prescribed_mM.shape != shape
        or volume_pL.shape != p.outside_active.shape
    ):
        raise ValueError("Reservoir state shape disagrees with geometry")
    valid = (
        xp.all(xp.isfinite(amount_fmol) & (amount_fmol > 0))
        & xp.all(xp.isfinite(prescribed_mM) & (prescribed_mM > 0))
        & xp.all(xp.isfinite(volume_pL) & (volume_pL > 0))
    )
    amount = xp.where(p.reservoir, prescribed_mM * volume_pL, amount_fmol)
    supply = xp.where(p.reservoir, amount - amount_fmol, 0.0)
    valid = valid & xp.all(xp.isfinite(amount))
    return ReservoirReset(xp.where(valid, amount, xp.nan), xp.where(valid, supply, xp.nan), valid)
