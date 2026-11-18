"""atp_driven_transporter_mass_action_positive@1: an ATP-driven transporter's kernel (B5).

The transporter kind's law kernel (fr45/transporter/PLAN.md; the inner-model note §7.4 (g) 2).
Per cycle it hydrolyses one ATP to ADP + Pi at its fuel node and moves n of its role from the
patch's inside to its outside. The role is neutral in version 1 (the proton pump is the first
charged consumer, later). The form is the Na/K and proton pumps':

    dG_cyc = dG'° + RT ln(c_ADP c_Pi / (c_ATP c0)) + n RT ln(c_out / c_in),
    cycles = k a S (1 - exp(dG_cyc / RT)),   S = [1 + (K/c_in)^n]^-1 [1 + K_ATP/c_ATP]^-1.

dG'° comes from the registry's potentials (mu°'(ADP) + mu°'(Pi) - mu°'(ATP), at the declared c0),
passed in at binding, never a law parameter. Near zero ATP the same law is evaluated in R-fuel's
identical rational form,

    cycles = k a [c_in^n c_ATP - c_ADP c_Pi e^(dG'°/RT) c_out^n / c0]
             / [(K^n + c_in^n)(K_ATP + c_ATP)],

which equals the exponential form for every positive state and stays finite at trial states.
Fuel is finite by default (ATP, ADP and Pi are rows the cycle moves) or held (read, never moved).
Pure functions in the xp style of processes/.
"""

from typing import Any, NamedTuple

import jax.numpy as jnp

from cells.laws.electrochemistry import R

LAW_ID = "atp_driven_transporter_mass_action_positive@1"
MAX_ABS_AFFINITY_OVER_RT = 80.0
STOICHIOMETRY_RANGE = (1, 4)
# Per cycle, inward-positive like today's pumps: the role leaves the inside (-n); the fuel node
# loses one ATP and gains one ADP and one Pi.
FUEL_STOICHIOMETRY = {"ATP": -1, "ADP": 1, "Pi": 1}


class Parameters(NamedTuple):
    capacity_fmol_s: Any  # k: fmol cycles/s
    stoichiometry: Any  # n, an integer 1..4, carried as a float
    km_role_mM: Any  # K
    km_atp_mM: Any  # K_ATP


class Inputs(NamedTuple):
    c_in_mM: Any  # the role at the patch's inside
    c_out_mM: Any  # the role at the patch's outside
    atp_mM: Any
    adp_mM: Any
    pi_mM: Any
    delta_g0_prime_J_mol: Any  # from the registry, at binding
    c0_mM: Any  # the registry's standard_concentration_mM
    temperature_K: Any


class Rates(NamedTuple):
    cycles_fmol_s: Any
    cycle_free_energy_J_mol: Any
    chemical_drive_J_mol: Any


def chemical_drive(i, *, xp=jnp):
    return i.delta_g0_prime_J_mol + R * i.temperature_K * (
        xp.log(i.adp_mM) + xp.log(i.pi_mM) - xp.log(i.atp_mM) - xp.log(i.c0_mM))


def cycle_free_energy(i, p, *, xp=jnp):
    transport = p.stoichiometry * R * i.temperature_K * (xp.log(i.c_out_mM) - xp.log(i.c_in_mM))
    return chemical_drive(i, xp=xp) + transport


def kinetics(i, p, availability, reads=None, *, xp=jnp):
    """Signed cycles (fmol/s) in the exponential form (positive states)."""
    del reads
    energy = cycle_free_energy(i, p, xp=xp)
    a = energy / (R * i.temperature_K)
    n = p.stoichiometry
    log_s = -xp.logaddexp(0.0, n * (xp.log(p.km_role_mM) - xp.log(i.c_in_mM))) - xp.logaddexp(
        0.0, xp.log(p.km_atp_mM) - xp.log(i.atp_mM))
    enabled = (p.capacity_fmol_s > 0) & (availability > 0)
    cap = xp.where(enabled, p.capacity_fmol_s, 1.0)
    avail = xp.where(enabled, availability, 1.0)
    magnitude = xp.exp(xp.log(cap) + xp.log(avail) + log_s + xp.maximum(a, 0.0))
    departure = xp.where(a >= 0, xp.expm1(-a), -xp.expm1(a))
    return Rates(xp.where(enabled, magnitude * departure, 0.0), energy, chemical_drive(i, xp=xp))


def cycles_rational(i, p, availability, *, xp=jnp):
    """R-fuel's identical rational form: finite at zero ATP and at trial states."""
    n = p.stoichiometry
    e0 = xp.exp(i.delta_g0_prime_J_mol / (R * i.temperature_K))
    num = i.c_in_mM**n * i.atp_mM - i.adp_mM * i.pi_mM * e0 * i.c_out_mM**n / i.c0_mM
    den = (p.km_role_mM**n + i.c_in_mM**n) * (p.km_atp_mM + i.atp_mM)
    return p.capacity_fmol_s * availability * num / den


def heat_pJ_s(rates):
    return -1e-3 * rates.cycles_fmol_s * rates.cycle_free_energy_J_mol


def held_work_pJ_s(rates):
    """Held fuel only: the maintenance's supplied work, -cycles x the chemical drive."""
    return -1e-3 * rates.cycles_fmol_s * rates.chemical_drive_J_mol


def role_inward_fmol_s(rates, p):
    return -p.stoichiometry * rates.cycles_fmol_s


def domain_valid(i, p, availability, *, xp=jnp):
    def pos(v):
        return xp.isfinite(v) & (v > 0)

    ok = pos(i.c_in_mM) & pos(i.c_out_mM) & pos(i.atp_mM) & pos(i.adp_mM) & pos(i.pi_mM)
    ok = ok & pos(p.km_role_mM) & pos(p.km_atp_mM) & pos(i.c0_mM)
    ok = ok & xp.isfinite(i.delta_g0_prime_J_mol)
    ok = ok & xp.isfinite(p.capacity_fmol_s) & (p.capacity_fmol_s >= 0)
    n = p.stoichiometry
    ok = ok & (n == xp.round(n)) & (n >= STOICHIOMETRY_RANGE[0]) & (n <= STOICHIOMETRY_RANGE[1])
    ok = ok & xp.isfinite(availability) & (availability >= 0) & (availability <= 1)
    safe = i._replace(**{f: xp.where(ok, getattr(i, f), 1.0) for f in
                         ("c_in_mM", "c_out_mM", "atp_mM", "adp_mM", "pi_mM", "c0_mM")})
    safe = safe._replace(delta_g0_prime_J_mol=xp.where(ok, i.delta_g0_prime_J_mol, 0.0))
    a = cycle_free_energy(safe, p._replace(stoichiometry=xp.where(ok, n, 1.0)), xp=xp) / (
        R * i.temperature_K)
    return ok & (xp.abs(a) <= MAX_ABS_AFFINITY_OVER_RT)
