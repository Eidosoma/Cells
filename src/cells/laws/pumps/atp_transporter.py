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

On held fuel it is superseded by atp_driven_transporter_mass_action_positive@2
(laws/pumps/atp_transporter_v2.py), whose role has any valence and which is this law at valence 0: a
new definition on held fuel takes that one. This one stays until the worlds that run it move
(docs/CALCIUM_STORE_AND_CHANNELS_DESIGN.md §6.3).
"""

from typing import Any, NamedTuple

import jax.numpy as jnp

from cells.laws.cycles.forms import CycleForm, Parameter, Saturation
from cells.laws.electrochemistry import R
from cells.modules import Citation, CycleLaw, qualified

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


# The same law in seam A's general form (docs/CORE_SEAMS_DESIGN.md §3; laws/cycles/forms.py), for the
# cycle kind's population axis: data only, its free energy the kind's from the registry. Its rows,
# in the form's order: the role at N and at P, then the fuel at N, where it is hydrolysed (held or
# moved: finite fuel runs here). S and the domain are version 1's: S = [1 + (K/c_N)^n]^-1
# [1 + K_ATP/c_ATP]^-1, n an integer in 1..4, the role neutral.
CYCLE = CycleForm(
    kinetics="factored",
    roles=(("role", 0), ("ATP", 0), ("ADP", 0), ("Pi", 0)),
    rows=(("role", "N"), ("role", "P"), ("ATP", "N"), ("ADP", "N"), ("Pi", "N")),
    modes=(("cycle", ("-stoichiometry", "stoichiometry", -1, 1, 1)),),
    parameters=(
        Parameter(
            "stoichiometry",
            "1",
            low=STOICHIOMETRY_RANGE[0],
            high=STOICHIOMETRY_RANGE[1],
            integer=True,
            positive=True,
        ),
        Parameter("km_role_mM", "mM", positive=True),
        Parameter("km_atp_mM", "mM", positive=True),
    ),
    fuel_roles=("ATP", "ADP", "Pi"),
    saturation=(
        (
            Saturation(("role", "N"), "km_role_mM", "stoichiometry"),
            Saturation(("ATP", "N"), "km_atp_mM", 1),
        ),
    ),
)


# Its declaration on the law template (registry/laws.py): inert, registered by the law registry's
# loader as one of the model table's law homes, hosted by the transporter kind.
DECLARED_ID = qualified(LAW_ID)  # As definitions write it; a module-level name, for the manifest.
LAW = CycleLaw(
    DECLARED_ID,
    (("role", "-stoichiometry"),),  # The role leaves the inside: -n per cycle, inward-positive.
    ("maintained_held_rows@1", "finite_fuel_rows@1"),
    kinetics,
    domain_valid,
    cycle=CYCLE,
    host="cells.transporter@1",
    provenance="cited",
    source=Citation(
        "an ATP-driven transporter of a neutral role, in the Na/K law's mass-action form "
        "(laws/pumps/kinetic_pump.py; docs/KINETIC_PUMP_PROCESS.md)",
        "docs/INNER_MODEL_V4_DESIGN.md §7.4 (g) 2",
        "no numbers taken: the law is a form, its parameters a definition's values",
    ),
)
