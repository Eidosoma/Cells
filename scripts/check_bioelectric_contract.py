"""Independent, instantaneous checks of the proposed one-cell physical contract.

This is not a Cells model, integrator, trajectory validation, or BETSE comparison.
It imports no Cells implementation. See docs/BIOELECTRIC_CELL_SPEC.md.
"""

import argparse
import hashlib
import json
import platform
from datetime import datetime, timezone
from decimal import Decimal, localcontext
from pathlib import Path

import numpy as np

AVOGADRO = 6.02214076e23
FARADAY = 1.602176634e-19 * AVOGADRO
GAS_CONSTANT = 1.380649e-23 * AVOGADRO
FMOL_TO_MOL = 1e-15
PL_TO_M3 = 1e-15
VALENCE = np.array([1.0, 1.0, -1.0])
PUMP_STOICHIOMETRY = np.array([-3.0, 2.0, 0.0])


def bernoulli(x):
    """x/(exp(x)-1), using a removable-singularity expansion near zero."""
    if abs(x) < 1e-4:
        return 1.0 - x / 2.0 + x**2 / 12.0 - x**4 / 720.0
    return x / np.expm1(x)


def passive_flux(ci, co, voltage, temperature, area, permeability):
    """Inward fmol/s; SI area and permeability, concentrations in mol/m3."""
    x = VALENCE * FARADAY * voltage / (GAS_CONSTANT * temperature)
    incoming = np.array([bernoulli(v) for v in x])
    outgoing = np.array([bernoulli(-v) for v in x])
    return area * permeability * (co * incoming - ci * outgoing) / FMOL_TO_MOL


def inward_potential(ci, co, voltage, temperature):
    """Electrochemical free-energy change for inward transport, J/mol."""
    return GAS_CONSTANT * temperature * np.log(ci / co) + VALENCE * FARADAY * voltage


def pump_rate(delta_mu, atp_free_energy, capacity, temperature):
    """Proposed affinity-limited phenomenological cycle law, not calibrated NaK kinetics."""
    cycle_free_energy = atp_free_energy + PUMP_STOICHIOMETRY @ delta_mu
    rate = capacity * np.tanh(-cycle_free_energy / (2.0 * GAS_CONSTANT * temperature))
    return rate, cycle_free_energy


def verify():
    checks = 0

    def require(condition, message):
        nonlocal checks
        if not condition:
            raise ValueError(message)
        checks += 1

    temperature, area, volume, capacitance = 298.15, 1e-9, 1.0, 1e-11
    ci, co = np.array([12.0, 140.0, 10.0]), np.array([145.0, 5.0, 150.0])
    permeability = np.array([1e-10, 1e-9, 1e-10])
    initial_voltage, atp_free_energy, capacity = -0.065, -50000.0, 0.02
    amounts = ci * volume * PL_TO_M3 / FMOL_TO_MOL
    charge_per_fmol = FARADAY * FMOL_TO_MOL
    fixed_charge = capacitance * initial_voltage - charge_per_fmol * (VALENCE @ amounts)
    fixed_anion_equivalent = -fixed_charge / charge_per_fmol
    require(FMOL_TO_MOL / PL_TO_M3 == 1.0, "fmol/pL must equal mol/m3 numerically")
    require(fixed_anion_equivalent > 0, "Fixture requires nonnegative fixed anion equivalent")
    require(VALENCE @ co == 0, "Declared bath must be electroneutral")

    xs = (-50.0, -1.0, -1e-4, -1e-8, 0.0, 1e-8, 1e-4, 1.0, 50.0)
    bernoulli_errors = []
    with localcontext() as context:
        context.prec = 70
        for x in xs:
            value = Decimal(str(x))
            expected = float(value / (value.exp() - 1)) if x else 1.0
            error = abs(bernoulli(x) - expected) / max(1.0, abs(expected))
            bernoulli_errors.append(error)
            require(error < 2e-15, f"Bernoulli high-precision mismatch at {x}")

    zero_voltage = passive_flux(ci, co, 0.0, temperature, area, permeability)
    require(
        np.allclose(
            zero_voltage,
            area * permeability * (co - ci) / FMOL_TO_MOL,
            rtol=2e-15,
            atol=1e-16,
        ),
        "Zero-voltage diffusion limit",
    )
    equilibria = GAS_CONSTANT * temperature / (VALENCE * FARADAY) * np.log(co / ci)
    equilibrium_errors = []
    for slot, voltage in enumerate(equilibria):
        flux = passive_flux(ci, co, voltage, temperature, area, permeability)[slot]
        equilibrium_errors.append(abs(flux))
        require(abs(flux) < 1e-12, f"Nernst zero-flux limit for slot {slot}")

    flux = passive_flux(ci, co, initial_voltage, temperature, area, permeability)
    require(
        np.array_equal(passive_flux(ci, co, initial_voltage, temperature, area, 0.0), [0, 0, 0]),
        "Disabled passive route must return zero",
    )
    require(
        np.allclose(
            passive_flux(co, ci, -initial_voltage, temperature, area, permeability),
            -flux,
            rtol=2e-15,
            atol=1e-16,
        ),
        "Exchanging compartments and voltage orientation must reverse flux",
    )
    require(
        np.array_equal(
            passive_flux(ci, co, initial_voltage, temperature, 2 * area, permeability), 2 * flux
        ),
        "Area scaling must be explicit",
    )

    mu = inward_potential(ci, co, initial_voltage, temperature)
    rate, delta_g = pump_rate(mu, atp_free_energy, capacity, temperature)
    require(VALENCE @ PUMP_STOICHIOMETRY == -1.0, "One net positive charge leaves per cycle")
    require(rate > 0 and delta_g < 0, "Fixture pump must run forward with supplied energy")
    require(pump_rate(mu, atp_free_energy, 0.0, temperature)[0] == 0, "Pump-off limit")
    stall_drive = -(PUMP_STOICHIOMETRY @ mu)
    require(pump_rate(mu, stall_drive, capacity, temperature)[0] == 0, "Pump stall limit")
    require(
        pump_rate(mu, stall_drive + 1000, capacity, temperature)[0] < 0,
        "Thermodynamically reversed pump must run backward",
    )
    # Check passive and coupled-pump dissipation across a declared, non-random panel.
    max_passive_product = max_pump_product = -np.inf
    for sodium in (1.0, 12.0, 120.0):
        varied_ci = np.array([sodium, ci[1], ci[2]])
        for voltage in (-0.1, -0.065, 0.0, 0.06):
            varied_mu = inward_potential(varied_ci, co, voltage, temperature)
            varied_flux = passive_flux(varied_ci, co, voltage, temperature, area, permeability)
            product = np.max(varied_flux * varied_mu)
            max_passive_product = max(max_passive_product, product)
            require(product <= 1e-12, "Passive transport must not climb electrochemical potential")
            for drive in (-50000.0, 0.0, 50000.0):
                varied_rate, varied_g = pump_rate(varied_mu, drive, capacity, temperature)
                product = varied_rate * varied_g
                max_pump_product = max(max_pump_product, product)
                require(product <= 1e-12, "Pump cycle must not create free energy")

    total_flux = flux + PUMP_STOICHIOMETRY * rate
    inward_current = charge_per_fmol * (VALENCE @ total_flux)
    # An algebraic ledger identity, not a time-integrated state or Euler trajectory.
    leak_ledger, cycles = np.array([0.02, -0.01, 0.005]), 0.003
    change = leak_ledger + PUMP_STOICHIOMETRY * cycles
    changed = amounts + change
    affine_voltage = initial_voltage + charge_per_fmol / capacitance * (VALENCE @ change)
    direct_voltage = (fixed_charge + charge_per_fmol * (VALENCE @ changed)) / capacitance
    require(abs(affine_voltage - direct_voltage) < 1e-11, "Charge/voltage identity")

    def current(voltage):
        passive = passive_flux(ci, co, voltage, temperature, area, permeability)
        chemical = inward_potential(ci, co, voltage, temperature)
        cycles_per_second = pump_rate(chemical, atp_free_energy, capacity, temperature)[0]
        return charge_per_fmol * (VALENCE @ (passive + PUMP_STOICHIOMETRY * cycles_per_second))

    epsilon = 1e-7
    slope = (current(initial_voltage + epsilon) - current(initial_voltage - epsilon)) / (
        2 * epsilon
    )
    require(slope < 0, "Fixture's frozen-concentration voltage feedback must be restoring")
    return {
        "status": "pass",
        "scope": "instantaneous design checks only; no Cells model or trajectory validation",
        "checks_passed": checks,
        "verified_utc": datetime.now(timezone.utc).isoformat(),
        "verifier_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "runtime": {"python": platform.python_version(), "numpy": np.__version__},
        "initial_amount_fmol": amounts.tolist(),
        "bath_mol_per_m3": co.tolist(),
        "fixed_anion_equivalent_fmol": fixed_anion_equivalent,
        "nernst_voltage_V": equilibria.tolist(),
        "max_bernoulli_scaled_error": max(bernoulli_errors),
        "max_nernst_flux_residual_fmol_per_s": max(equilibrium_errors),
        "passive_flux_inward_fmol_per_s": flux.tolist(),
        "pump_cycle_rate_fmol_per_s": rate,
        "pump_cycle_free_energy_J_per_mol": delta_g,
        "pump_chemical_power_W": -atp_free_energy * FMOL_TO_MOL * rate,
        "total_inward_current_A": inward_current,
        "initial_voltage_derivative_V_per_s": inward_current / capacitance,
        "frozen_concentration_relaxation_estimate_s": -capacitance / slope,
        "max_passive_flux_potential_product_fmol_J_per_mol_s": max_passive_product,
        "max_pump_rate_affinity_product_fmol_J_per_mol_s": max_pump_product,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Optional new JSON receipt file; no overwrite")
    args = parser.parse_args()
    if args.output is not None and args.output.exists():
        raise FileExistsError("Choose a new design-check receipt path")
    report = verify()
    payload = json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if args.output is not None:
        with args.output.open("x") as handle:
            handle.write(payload)
    print(payload, end="")


if __name__ == "__main__":
    main()
