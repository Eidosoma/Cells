"""proton_atp_mass_action_positive@1: an ATP-driven proton pump on a patch (FR-4).

docs/COMPARTMENT_PH_TRANSFER_DESIGN.md §6, against the inner-model note's §7.4 (g) 2 (the
transporter kind). Per cycle it hydrolyses one ATP at the patch's inside node and moves n H+ from
the inside to the outside, n a declared integer from 1 to 4. The form is the Na/K law's
(processes/kinetic_pump.py), thermodynamically consistent:

    dG_cyc = chemical drive + n (RT ln(h_out/h_in) - F V),     V = phi_in - phi_out,
    chemical drive = dG'° + RT ln(c_ADP c_Pi / (c_ATP c0)),    c0 = 1000 mM,
    cycles = capacity x availability x S x (1 - exp(dG_cyc/RT)),
    S = [1 + (K_H/h_in)^n]^-1 [1 + K_ATP/c_ATP]^-1.

h_in and h_out are free protons, read through each node's closure (rapid_proton_buffer@1).
dG'° comes from the registry's transformed potentials (B3), never from the pump. Fuel is held
(maintained_held_rows@1): the rows are read, not moved. Heat is -cycles x dG_cyc, and work is
-cycles x the chemical drive (pJ/s with cycles in fmol/s and energies in J/mol, times 1e-3).

Pure functions in the xp style of processes/. The composing model supplies valid, positive inputs
and refuses a trial whose domain fails; nothing here floors or clips.
"""

from typing import Any, NamedTuple

import jax.numpy as jnp

from cells.processes.electrochemistry import CHARGE_PER_FMOL, F, R

LAW_ID = "proton_atp_mass_action_positive@1"
STANDARD_STATE_mM = 1000.0
MAX_ABS_AFFINITY_OVER_RT = 80.0
PROTONS_PER_CYCLE_RANGE = (1, 4)
TEMPERATURE_DOMAIN_K = (200.0, 400.0)


class Parameters(NamedTuple):
    """Numeric pytree, every leaf broadcastable over [..., transporter_slot]."""

    capacity_fmol_s: Any  # fmol cycles/s: N x the per-member value for a lumped node
    protons_per_cycle: Any  # n, an integer from 1 to 4, carried as a float
    km_proton_mM: Any
    km_atp_mM: Any
    delta_g0_prime_J_mol: Any  # from the registry's transformed potentials


class Inputs(NamedTuple):
    h_in_mM: Any  # free, through the inside node's closure
    h_out_mM: Any  # free, through the outside node's closure
    voltage_V: Any  # the patch voltage, inside minus outside
    atp_mM: Any
    adp_mM: Any
    pi_mM: Any
    temperature_K: Any


class Rates(NamedTuple):
    cycles_fmol_s: Any
    cycle_free_energy_J_mol: Any
    chemical_drive_J_mol: Any


def chemical_drive(inputs, parameters, *, xp=jnp):
    """Transformed hydrolysis free energy at the held fuel (J/mol)."""
    i = inputs
    return parameters.delta_g0_prime_J_mol + R * i.temperature_K * (
        xp.log(i.adp_mM) + xp.log(i.pi_mM) - xp.log(i.atp_mM) - xp.log(STANDARD_STATE_mM)
    )


def cycle_free_energy(inputs, parameters, *, xp=jnp):
    """dG_cyc (J/mol cycles): hydrolysis plus moving n H+ from inside to outside."""
    i, n = inputs, parameters.protons_per_cycle
    transport = R * i.temperature_K * (xp.log(i.h_out_mM) - xp.log(i.h_in_mM)) - F * i.voltage_V
    return chemical_drive(i, parameters, xp=xp) + n * transport


def _log_magnitude(inputs, parameters, availability, *, xp):
    i, p = inputs, parameters
    log_saturation = -xp.logaddexp(
        0.0, p.protons_per_cycle * (xp.log(p.km_proton_mM) - xp.log(i.h_in_mM))
    ) - xp.logaddexp(0.0, xp.log(p.km_atp_mM) - xp.log(i.atp_mM))
    enabled = (p.capacity_fmol_s > 0) & (availability > 0)
    safe_capacity = xp.where(enabled, p.capacity_fmol_s, 1.0)
    safe_availability = xp.where(enabled, availability, 1.0)
    return xp.log(safe_capacity) + xp.log(safe_availability) + log_saturation, enabled


def kinetics(inputs, parameters, availability, *, xp=jnp):
    """Signed cycles (fmol/s), positive forward, with the cycle's and the drive's free energies."""
    energy = cycle_free_energy(inputs, parameters, xp=xp)
    a = energy / (R * inputs.temperature_K)
    log_magnitude, enabled = _log_magnitude(inputs, parameters, availability, xp=xp)
    # As kinetic_pump: combine exponents before exp; exp(max(a,0)) * departure is 1 - exp(a).
    magnitude = xp.exp(log_magnitude + xp.maximum(a, 0.0))
    departure = xp.where(a >= 0, xp.expm1(-a), -xp.expm1(a))
    cycles = xp.where(enabled, magnitude * departure, 0.0)
    return Rates(cycles, energy, chemical_drive(inputs, parameters, xp=xp))


def heat_pJ_s(rates):
    """Dissipation (pJ/s): -cycles x dG_cyc, nonnegative by the form."""
    return -1e-3 * rates.cycles_fmol_s * rates.cycle_free_energy_J_mol


def work_pJ_s(rates):
    """Work supplied by the held fuel's maintenance (pJ/s): -cycles x the chemical drive."""
    return -1e-3 * rates.cycles_fmol_s * rates.chemical_drive_J_mol


def proton_transfer_fmol_s(rates, parameters):
    """H+ moved from the inside node to the outside node (fmol/s); H_eq at buffered nodes."""
    return parameters.protons_per_cycle * rates.cycles_fmol_s


def electrogenic_conductance_S(inputs, parameters, availability, *, xp=jnp):
    """|d(current)/dV| (S), for the stage rule: n F |d cycles/dV| with |dcycles/da| = M exp(a)."""
    energy = cycle_free_energy(inputs, parameters, xp=xp)
    a = energy / (R * inputs.temperature_K)
    log_magnitude, enabled = _log_magnitude(inputs, parameters, availability, xp=xp)
    n = parameters.protons_per_cycle
    slope = xp.exp(log_magnitude + a) * n * F / (R * inputs.temperature_K)  # fmol/s per V
    return xp.where(enabled, n * CHARGE_PER_FMOL * slope, 0.0)


def loop_rate_per_s(inputs, parameters, availability, outside_free_per_total, outside_volume_pL,
                    *, xp=jnp):
    """The loop term (1/s): |d(n cycles)/dH_eq,out| through dh_out/dH_out, at the outside node.

    outside_free_per_total is the closure's dh/dH there (rapid_proton_buffer.free_per_total).
    """
    energy = cycle_free_energy(inputs, parameters, xp=xp)
    a = energy / (R * inputs.temperature_K)
    log_magnitude, enabled = _log_magnitude(inputs, parameters, availability, xp=xp)
    n = parameters.protons_per_cycle
    d_cycles_d_h = xp.exp(log_magnitude + a) * n / inputs.h_out_mM  # fmol/s per mM
    return xp.where(enabled, n * d_cycles_d_h * outside_free_per_total / outside_volume_pL, 0.0)


def domain_valid(inputs, parameters, availability, *, xp=jnp):
    """Per-slot validity: positive finite concentrations and constants, an integer n in 1..4,
    |dG_cyc/RT| <= 80, availability in [0, 1], capacity >= 0 and temperature in its domain."""
    i, p = inputs, parameters

    def positive(value):
        return xp.isfinite(value) & (value > 0)

    valid = positive(i.h_in_mM) & positive(i.h_out_mM) & positive(i.atp_mM)
    valid = valid & positive(i.adp_mM) & positive(i.pi_mM) & xp.isfinite(i.voltage_V)
    valid = valid & positive(p.km_proton_mM) & positive(p.km_atp_mM)
    valid = valid & xp.isfinite(p.delta_g0_prime_J_mol)
    valid = valid & xp.isfinite(p.capacity_fmol_s) & (p.capacity_fmol_s >= 0)
    n = p.protons_per_cycle
    valid = valid & (n == xp.round(n)) & (n >= PROTONS_PER_CYCLE_RANGE[0])
    valid = valid & (n <= PROTONS_PER_CYCLE_RANGE[1])
    valid = valid & xp.isfinite(availability) & (availability >= 0) & (availability <= 1)
    t = i.temperature_K
    valid = valid & (t >= TEMPERATURE_DOMAIN_K[0]) & (t <= TEMPERATURE_DOMAIN_K[1])
    safe = Inputs(
        *(xp.where(valid, v, 1.0) for v in i[:2]),
        xp.where(valid, i.voltage_V, 0.0),
        *(xp.where(valid, v, 1.0) for v in i[3:6]),
        xp.where(valid, t, 300.0),
    )
    safe_p = Parameters(
        p.capacity_fmol_s,
        xp.where(valid, n, 1.0),
        xp.where(valid, p.km_proton_mM, 1.0),
        xp.where(valid, p.km_atp_mM, 1.0),
        xp.where(valid, p.delta_g0_prime_J_mol, 0.0),
    )
    a = cycle_free_energy(safe, safe_p, xp=xp) / (R * safe.temperature_K)
    return valid & (xp.abs(a) <= MAX_ABS_AFFINITY_OVER_RT)
