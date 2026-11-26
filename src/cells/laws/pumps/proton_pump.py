"""cells.cycle.proton_atp_mass_action_positive@1: an ATP-driven proton pump on a patch (FR-4).

docs/COMPARTMENT_PH_TRANSFER_DESIGN.md §6, against the inner-model note's §7.4 (g) 2 (the
transporter kind). Per cycle it hydrolyses one ATP at the patch's inside node and moves n H+ from
the inside to the outside, n a declared integer from 1 to 4. The form is the Na/K law's
(laws/pumps/kinetic_pump.py), thermodynamically consistent:

    dG_cyc = chemical drive + n (RT ln(h_out/h_in) - F V),     V = phi_in - phi_out,
    chemical drive = dG'° + RT ln(c_ADP c_Pi / (c_ATP c0)),    c0 = 1000 mM,
    cycles = capacity x availability x S x (1 - exp(dG_cyc/RT)),
    S = [1 + (K_H/h_in)^n]^-1 [1 + K_ATP/c_ATP]^-1.

h_in and h_out are free protons, read through each node's closure (cells.kind.rapid_proton_buffer@1).
dG'° comes from the registry's transformed potentials (B3), never from the pump. Fuel is held
(cells.fuel_kind.maintained_held_rows@1): the rows are read, not moved. Heat is -cycles x dG_cyc, and work is
-cycles x the chemical drive (pJ/s with cycles in fmol/s and energies in J/mol, times 1e-3).

Pure functions in the xp style of processes/. The composing model supplies valid, positive inputs
and refuses a trial whose domain fails; nothing here floors or clips.

cells.cycle.atp_driven_transporter_mass_action_positive@2 (laws/pumps/atp_transporter_v2.py) is this cycle for a
species of any valence, with no pH band. This law stays until the worlds that run it are judged
again, and then folds into that one (docs/CALCIUM_STORE_AND_CHANNELS_DESIGN.md §6.3).
"""

from typing import Any, NamedTuple

import jax.numpy as jnp

from cells.laws.cycles.forms import CycleForm, Parameter, PhBand, Saturation
from cells.laws.electrochemistry import CHARGE_PER_FMOL, F, R
from cells.modules import Citation, CycleLaw, qualified

LAW_ID = "cells.cycle.proton_atp_mass_action_positive@1"
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
    fuel_ph_ref: Any  # the fuel node's reference pH of its transformed potentials (§5.2)
    fuel_ph_band: Any  # delta: the domain refuses |pH_in - fuel_ph_ref| > delta


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


def kinetics(inputs, parameters, availability, reads=None, *, xp=jnp):
    """Signed cycles (fmol/s), positive forward, with the cycle's and the drive's free energies.

    §7.4 (g) 2's signature. The insertion point puts each read value into `inputs` (h_in and h_out
    from the closures), so `reads` is accepted and not consulted again.
    """
    del reads
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


def proton_inward_fmol_s(rates, parameters):
    """Inward-positive proton transfer across the patch (fmol/s), as `moves` and today's pumps
    count it: -n per forward cycle (H_eq at buffered nodes). The inside node gains this; the
    outside node gains its negative."""
    return -parameters.protons_per_cycle * rates.cycles_fmol_s


# §7.4 (g) 2: per-cycle stoichiometry by role, inward-positive. n is the population's declared
# integer; its role binds at binding to the H row at the patch's inside and outside nodes.
MOVES = (("proton", "-protons_per_cycle"),)
READS = ("cells.kind.rapid_proton_buffer@1",)  # free h at both nodes
DECLARATION = {
    "law_id": LAW_ID,
    "code": None,  # the core's registry assigns the next free code
    "kind": "transporter",
    "moves": MOVES,
    "reads": READS,
    "fuel": "cells.fuel_kind.maintained_held_rows@1",
    "stage_term": "electrogenic_conductance_S",
    "provenance": "cited",
    "b8": {},  # D175's four fields: reserved, empty
}


def electrogenic_conductance_S(inputs, parameters, availability, *, xp=jnp):
    """|d(current)/dV| (S), for the stage rule: n F |d cycles/dV| with |dcycles/da| = M exp(a)."""
    energy = cycle_free_energy(inputs, parameters, xp=xp)
    a = energy / (R * inputs.temperature_K)
    log_magnitude, enabled = _log_magnitude(inputs, parameters, availability, xp=xp)
    n = parameters.protons_per_cycle
    slope = xp.exp(log_magnitude + a) * n * F / (R * inputs.temperature_K)  # fmol/s per V
    return xp.where(enabled, n * CHARGE_PER_FMOL * slope, 0.0)


def loop_rates_per_s(inputs, parameters, availability, free_per_total_in, volume_in_pL,
                     free_per_total_out, volume_out_pL, *, xp=jnp):
    """The loop terms (1/s) at both nodes: |d(n cycles)/dH_eq| through each closure's dh/dH. The
    engine does not evaluate them.

    With cycles = M (1 - e^a): the outside proton enters through a only (da/dln h_out = n); the
    inside one through a (da/dln h_in = -n) and the saturation M
    (dln M/dln h_in = n s, s = (K_H/h_in)^n / (1 + (K_H/h_in)^n)). Returns (inside, outside).
    """
    energy = cycle_free_energy(inputs, parameters, xp=xp)
    a = energy / (R * inputs.temperature_K)
    log_magnitude, enabled = _log_magnitude(inputs, parameters, availability, xp=xp)
    n = parameters.protons_per_cycle
    m = xp.exp(log_magnitude)
    e_a = xp.exp(a)
    ratio = xp.exp(n * (xp.log(parameters.km_proton_mM) - xp.log(inputs.h_in_mM)))
    s = ratio / (1.0 + ratio)
    d_ln_out = -m * e_a * n  # d cycles / d ln h_out
    d_ln_in = m * n * s * (1.0 - e_a) + m * e_a * n  # d cycles / d ln h_in
    inside = xp.abs(n * d_ln_in / inputs.h_in_mM) * free_per_total_in / volume_in_pL
    outside = xp.abs(n * d_ln_out / inputs.h_out_mM) * free_per_total_out / volume_out_pL
    return xp.where(enabled, inside, 0.0), xp.where(enabled, outside, 0.0)


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
    # The fuel node's pH band (§5.2): transformed potentials hold only near their reference pH.
    ph_in = -xp.log10(xp.where(valid, i.h_in_mM, 1.0) / STANDARD_STATE_mM)
    valid = valid & xp.isfinite(p.fuel_ph_band) & (p.fuel_ph_band >= 0)
    valid = valid & (xp.abs(ph_in - p.fuel_ph_ref) <= p.fuel_ph_band)
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
        p.fuel_ph_ref,
        p.fuel_ph_band,
    )
    a = cycle_free_energy(safe, safe_p, xp=xp) / (R * safe.temperature_K)
    return valid & (xp.abs(a) <= MAX_ABS_AFFINITY_OVER_RT)


# The same law in seam A's general form (docs/CORE_SEAMS_DESIGN.md §3; laws/cycles/forms.py), for the
# cycle kind's population axis: data only, its free energy the kind's from the registry. Its rows,
# in the form's order: the proton at N and at P, then the fuel at N; N is the inside end, where the
# fuel is hydrolysed. Its S is version 1's, [1 + (K_H/h_N)^n]^-1 [1 + K_ATP/c_ATP]^-1, and its
# domain version 1's: n an integer in 1..4, the fuel's pH band at N, temperature in its domain.
CYCLE = CycleForm(
    kinetics="factored",
    roles=(("proton", 1), ("ATP", 0), ("ADP", 0), ("Pi", 0)),
    rows=(("proton", "N"), ("proton", "P"), ("ATP", "N"), ("ADP", "N"), ("Pi", "N")),
    modes=(("cycle", ("-stoichiometry", "stoichiometry", -1, 1, 1)),),
    parameters=(
        Parameter(
            "stoichiometry",
            "1",
            low=PROTONS_PER_CYCLE_RANGE[0],
            high=PROTONS_PER_CYCLE_RANGE[1],
            integer=True,
            positive=True,
        ),
        Parameter("km_role_mM", "mM", positive=True),
        Parameter("km_atp_mM", "mM", positive=True),
        Parameter("ph_ref", "pH", positive=True),
        Parameter("ph_band", "pH", low=0.0),
    ),
    fuel_roles=("ATP", "ADP", "Pi"),
    saturation=(
        (
            Saturation(("proton", "N"), "km_role_mM", "stoichiometry"),
            Saturation(("ATP", "N"), "km_atp_mM", 1),
        ),
    ),
    ph_bands=(PhBand(("proton", "N"), "ph_ref", "ph_band"),),
    temperature_K=TEMPERATURE_DOMAIN_K,
)


# Its declaration on the law template (registry/laws.py): inert, registered by the law registry's
# loader as one of the model table's law homes, hosted by the transporter kind.
DECLARED_ID = qualified(LAW_ID)  # As definitions write it; a module-level name, for the manifest.
LAW = CycleLaw(
    DECLARED_ID,
    MOVES,
    ("cells.fuel_kind.maintained_held_rows@1",),
    kinetics,
    domain_valid,
    reads=READS,
    stage_term=DECLARATION["stage_term"],
    cycle=CYCLE,
    host="cells.kind.transporter@1",
    provenance=DECLARATION["provenance"],
    source=Citation(
        "an ATP-driven proton pump, in the Na/K law's mass-action form "
        "(laws/pumps/kinetic_pump.py; docs/KINETIC_PUMP_PROCESS.md)",
        "docs/COMPARTMENT_PH_TRANSFER_DESIGN.md §6",
        "no numbers taken: the law is a form, its parameters a definition's values",
    ),
)
