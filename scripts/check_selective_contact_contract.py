"""Independent instantaneous SPEC-002 checks; not a Cells model or integrator.

Native BITSEY fixtures and new physical equations are checked separately. Their
intentional differences are tests, not fitted-away errors. NumPy only; no Cells
or upstream imports. See docs/SELECTIVE_CONTACT_SPEC.md.
"""

import argparse
import hashlib
import json
import platform
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

F = 1.602176634e-19 * 6.02214076e23
R = 1.380649e-23 * 6.02214076e23
AMOUNT_SCALE = 1e-15
Z = np.array([1.0, 1.0, -1.0])
NU = np.array([-3.0, 2.0, 0.0])
FIXTURE = Path(__file__).resolve().parents[1] / "tests/fixtures/contact_source_probes.json"


def bernoulli(x):
    if abs(x) < 1e-4:
        return 1 - x / 2 + x**2 / 12 - x**4 / 720
    return x / np.expm1(x)


def gate_target(delta_v, sensitivity=100.0, half_voltage=0.04):
    """Symmetric synthetic steady target; relaxation kinetics are our addition."""
    if not np.isfinite([delta_v, sensitivity, half_voltage]).all():
        raise ValueError("Gate parameters must be finite")
    if sensitivity <= 0 or half_voltage < 0:
        raise ValueError("Invalid sensitivity or half-voltage")
    return np.exp(
        -np.logaddexp.reduce(
            [0.0, sensitivity * (-delta_v - half_voltage), sensitivity * (delta_v - half_voltage)]
        )
    )


def gate_slope(gate, delta_v, tau=0.2):
    if not np.isfinite([gate, tau]).all() or not 0 <= gate <= 1 or tau <= 0:
        raise ValueError("Gate must be a probability and tau finite/positive")
    return (gate_target(delta_v) - gate) / tau


def edge_flux(ca, cb, delta_v, valence, permeability, area, gate, residual, control, temperature):
    """A -> B, fmol/s; concentrations mM, SI geometry/permeability/voltage."""
    ca, cb, valence, permeability, residual = map(
        np.asarray, (ca, cb, valence, permeability, residual)
    )
    if not np.isfinite([delta_v, area, gate, control, temperature]).all():
        raise ValueError("Nonfinite scalar")
    if area <= 0 or temperature <= 0 or not 0 <= gate <= 1 or not 0 <= control <= 1:
        raise ValueError("Invalid geometry, gate or control")
    if not all(np.isfinite(v).all() for v in (ca, cb, valence, permeability, residual)):
        raise ValueError("Nonfinite species data")
    if np.any(ca <= 0) or np.any(cb <= 0) or np.any(permeability < 0):
        raise ValueError("Positive concentrations and nonnegative permeability required")
    if np.any(residual < 0) or np.any(residual > 1):
        raise ValueError("Residual fraction must be in [0,1]")
    x = valence * F * delta_v / (R * temperature)
    if np.any(np.abs(x) > 50):
        raise ValueError("Outside the proposed dimensionless-voltage domain")
    forward = np.array([bernoulli(-v) for v in x])
    backward = np.array([bernoulli(v) for v in x])
    amplitude = area * permeability * control * (residual + (1 - residual) * gate)
    return amplitude / AMOUNT_SCALE * (ca * forward - cb * backward)


def source_flux(ca, cb, delta_v, valence, diffusion, constants):
    """Independent expression of the pinned source's upwind drift approximation."""
    x = np.asarray(valence) * constants["q"] * delta_v / (constants["kb"] * constants["T"])
    donor = np.where(x >= 0, ca, cb)
    return np.asarray(diffusion) / constants["GJ_len"] * (ca - cb + x * donor)


def verify(reference=FIXTURE):
    capture = json.loads(reference.read_text())
    checks = 0

    def require(condition, message):
        nonlocal checks
        if not condition:
            raise ValueError(message)
        checks += 1

    def close(actual, expected, message, *, atol=1e-20, rtol=3e-14):
        require(np.allclose(actual, expected, atol=atol, rtol=rtol), message)

    require(capture["schema_version"] == 1, "Reference schema")
    require(capture["revision"] == "b2cb370aaecbc8299f259bc4251d5396c81f19a6", "Source pin")
    p = capture["probes"]["constants"]
    require(p["q"] == 1.602e-19 and p["kb"] == 1.3806e-23, "Source drift constants")
    source = capture["probes"]
    inputs = source["transport_inputs"]
    ca, cb = np.asarray(inputs["concentrations"]).T
    for row in source["transport"]:
        expected = source_flux(ca, cb, row["delta_v"], inputs["valences"], inputs["diffusion"], p)
        close(row["flux"], expected, "Native drift/diffusion formula")
        close(row["reverse"], -expected, "Native reversed endpoints")

    full = source["full_rhs"]
    ca, cb = np.asarray(full["concentrations"]).T
    expected_vm = (
        np.asarray(full["valences"])
        @ np.asarray(full["concentrations"])
        * p["F"]
        * p["cell_vol"]
        / (p["cell_sa"] * p["cm"])
    )
    close(full["vm"], expected_vm, "Native charge closure", atol=1e-13)
    delta = full["vm"][0] - full["vm"][1]
    flux = source_flux(ca, cb, delta, full["valences"], full["diffusion"], p)
    expected = np.stack([-flux, flux], axis=1) * p["cell_sa"] / p["cell_vol"]
    close(full["slopes"], expected, "Executable from-minus-to orientation and scatter", atol=1e-15)

    for kind in source["gates"]:
        a1, v1, a2, v2, gmin, gmax = kind["parameters"]
        for row in kind["records"]:
            delta = row["delta_v"]
            opened = 1 / (1 + np.exp(a1 * (-delta - v1)) + np.exp(a2 * (delta - v2)))
            close(row["on_fraction"], opened, "Native steady opposing-gate factor")
            close(row["ordinary"], gmin + (gmax - gmin) * opened, "Native residual conductance")
            close(row["closed_blocked"], gmax * opened, "Native closed-state selectivity")
            require(
                row["fully_blocked"] == 0 and row["time_independent"], "Native block/statelessness"
            )
    require(source["gates"][0]["parameters"][-1] > 1, "Conductance amplitude is not probability")
    require(source["gates"][1]["records"][2]["ordinary"] > 1, "Do not clip native scale to one")
    require(
        source["gates"][1]["records"][1]["ordinary"]
        != source["gates"][1]["records"][-2]["ordinary"],
        "Heterotypic orientation is not symmetric",
    )
    mir = source["mirna"]
    require(mir["effective_transport_valence"] == -1, "Executable miRNA valence, not stale comment")
    close(mir["free_concentrations"], mir["total_concentrations"], "Simple free-miRNA proxy")
    for key in (
        "output_is_total",
        "charge_excluded",
        "temporary_valence_reset",
        "temporary_diffusion_reset",
        "primary_and_derived_unchanged_by_transport",
    ):
        require(mir[key] is True, key)
    for row in mir["records"]:
        expected = source_flux(*mir["free_concentrations"], row["delta_v"], -1, mir["diffusion"], p)
        close(row["flux"], expected, "Native miRNA flux into primary total")
    for name in (
        "snail",
        "ZEB_prot",
        "Zeb_mRNA_total",
        "miR200_free",
        *(f"bound{i}" for i in range(7)),
    ):
        require(mir["scale_at_40mv"][name] == 0, "No duplicate proxy/protein/mRNA routes")
    close(
        mir["scale_at_40mv"]["miR200_total"],
        source["gates"][0]["records"][3]["closed_blocked"],
        "Medium-sized primary route uses zero residual",
    )

    limiting = []
    for row in source["limiting"]:
        x = row["x"]
        close(row["normalized_flux"], x - 1, "Source drift counterexample", atol=1e-15)
        physical = bernoulli(-x) - 2 * bernoulli(x)
        limiting.append({**row, "constant_field_normalized_flux": physical})
    require(abs(limiting[0]["constant_field_normalized_flux"]) < 1e-14, "Physical Nernst limit")
    require(abs(limiting[0]["normalized_flux"]) > 0.3, "Do not equate the two transport laws")
    mu = np.log(2) - limiting[1]["x"]
    require(limiting[1]["normalized_flux"] * mu > 0, "Source approximation mismatch is retained")
    require(limiting[1]["constant_field_normalized_flux"] * mu < 0, "Physical passive direction")
    source_checks = checks

    temperature, area = 298.15, 1e-11
    permeability, residual = np.array([1e-8, 5e-9, 2e-9]), np.array([0.1, 0.1, 0.0])
    ca, cb = np.array([12.0, 140.0, 10.0]), np.array([18.0, 130.0, 15.0])
    initial_flux = edge_flux(ca, cb, -0.02, Z, permeability, area, 0.25, residual, 1, temperature)
    maximum_passive_product = -np.inf
    for ratio in (0.05, 0.5, 1.0, 2.0, 20.0):
        for voltage in (-0.1, -0.02, 0.0, 0.02, 0.1):
            for gate in (0.0, 0.25, 1.0):
                for control in (0.0, 0.3, 1.0):
                    other = ca * ratio
                    flux = edge_flux(
                        ca,
                        other,
                        voltage,
                        Z,
                        permeability,
                        area,
                        gate,
                        residual,
                        control,
                        temperature,
                    )
                    reverse = edge_flux(
                        other,
                        ca,
                        -voltage,
                        Z,
                        permeability,
                        area,
                        gate,
                        residual,
                        control,
                        temperature,
                    )
                    close(flux, -reverse, "Physical reciprocal transfer", atol=1e-14)
                    delta_mu = R * temperature * np.log(other / ca) - Z * F * voltage
                    product = np.max(flux * delta_mu)
                    maximum_passive_product = max(maximum_passive_product, float(product))
                    require(product <= 1e-12, "Physical passive dissipation")
                    if control == 0:
                        require(np.array_equal(flux, np.zeros(3)), "Independent contact blocker")
    zero = edge_flux(ca, cb, 0, Z, permeability, area, 1, residual, 1, temperature)
    close(zero, area * permeability / AMOUNT_SCALE * (ca - cb), "Zero-voltage Fick limit")
    closed = edge_flux(ca, cb, 0, Z, permeability, area, 0, residual, 1, temperature)
    close(closed, residual * zero, "Species-specific closed-gate residual")
    blocked = edge_flux(
        ca, cb, -0.02, Z, permeability * [1, 0, 1], area, 1, residual, 1, temperature
    )
    require(blocked[1] == 0, "Fully impermeant species")
    neutral = edge_flux(ca, cb, 0.1, np.zeros(3), permeability, area, 1, residual, 1, temperature)
    close(neutral, zero, "Neutral diffusion limit of the reusable law; not a new model species")
    for slot in range(3):
        voltage = R * temperature / (Z[slot] * F) * np.log(cb[slot] / ca[slot])
        flux = edge_flux(ca, cb, voltage, Z, permeability, area, 1, residual, 1, temperature)
        require(abs(flux[slot]) < 1e-13, "Per-species Nernst equilibrium")

    for voltage in (-10.0, -0.08, -0.02, 0.0, 0.02, 0.08, 10.0):
        target = gate_target(voltage)
        require(0 <= target <= 1, "Stable gate target domain")
        close(target, gate_target(-voltage), "Synthetic gate symmetry")
        require(
            gate_slope(0, voltage) >= 0 and gate_slope(1, voltage) <= 0,
            "Inward gate boundary slopes",
        )
        for initial in (0.0, 0.25, 1.0):
            time, tau = 0.3, 0.2
            exact = target + (initial - target) * np.exp(-time / tau)
            require(0 <= exact <= 1, "Frozen-voltage analytic gate trajectory domain")
            derivative = -(initial - target) / tau * np.exp(-time / tau)
            close(gate_slope(exact, voltage, tau), derivative, "Analytic gate derivative")
    require(gate_slope(0.25, -0.02) != 0, "A blocked contact must not freeze gate kinetics")

    # Ledger algebra with deliberately unequal volumes and capacitances.
    volumes, capacitance = np.array([1.0, 1.7]), np.array([1e-11, 1.6e-11])
    concentrations = np.stack([ca, cb], axis=1)
    initial_amount = concentrations * volumes
    initial_v = np.array([-0.065, -0.045])
    leak = np.array([[0.02, -0.01], [-0.01, 0.04], [0.005, 0.002]])
    cycles, transfer = np.array([0.003, 0.001]), np.array([0.02, -0.007, 0.003])
    external = leak + NU[:, None] * cycles
    change = external + np.stack([-transfer, transfer], axis=1)
    amount = initial_amount + change
    charge_per_fmol = F * AMOUNT_SCALE
    fixed_charge = capacitance * initial_v - charge_per_fmol * (Z @ initial_amount)
    voltage = initial_v + charge_per_fmol / capacitance * (Z @ (amount - initial_amount))
    direct_v = (fixed_charge + charge_per_fmol * (Z @ amount)) / capacitance
    close(voltage, direct_v, "Two-cell charge closure", atol=5e-13)
    close(
        change.sum(axis=1),
        external.sum(axis=1),
        "Each species cancels internal transfer",
        atol=1e-15,
    )
    # Adding/subtracting a small ledger to/from a large amount loses low bits.
    # Bound that arithmetic by operand scale, not a fitted biological tolerance.
    charge_roundoff_bound = (
        8 * np.finfo(float).eps * charge_per_fmol * np.sum(np.abs(initial_amount))
    )
    external_charge_residual = capacitance @ (voltage - initial_v) - charge_per_fmol * np.sum(
        Z @ external
    )
    close(
        capacitance @ (voltage - initial_v),
        charge_per_fmol * np.sum(Z @ external),
        "External charge ledger",
        atol=charge_roundoff_bound,
    )
    dv = charge_per_fmol / capacitance * (Z @ np.stack([-initial_flux, initial_flux], axis=1))
    close(capacitance @ dv, 0, "Isolated capacitive charge conservation", atol=1e-24)
    require(abs(np.sum(dv)) > 1e-6, "Unweighted voltage sum is not conserved for unequal C")

    bath, atp = np.array([145.0, 5.0, 150.0]), -50000.0
    mu_in = R * temperature * np.log(concentrations / bath[:, None]) + Z[:, None] * F * initial_v
    leaks = np.stack(
        [
            edge_flux(
                bath,
                concentrations[:, i],
                -initial_v[i],
                Z,
                [1e-10, 1e-9, 1e-10],
                1e-9,
                1,
                [0, 0, 0],
                1,
                temperature,
            )
            for i in range(2)
        ],
        axis=1,
    )
    cycle_g = atp + NU @ mu_in
    rates = 0.02 * np.tanh(-cycle_g / (2 * R * temperature))
    rate_amount = leaks + NU[:, None] * rates + np.stack([-initial_flux, initial_flux], axis=1)
    omega_dot = AMOUNT_SCALE * np.sum(mu_in * rate_amount)
    dissipation = -AMOUNT_SCALE * (
        np.sum(leaks * mu_in) + np.sum(rates * cycle_g) + initial_flux @ (mu_in[:, 1] - mu_in[:, 0])
    )
    supplied = -AMOUNT_SCALE * atp * np.sum(rates)
    require(dissipation >= 0, "Resolved transport/pump dissipation; gate energetics excluded")
    close(omega_dot, supplied - dissipation, "Resolved bath-relative energy balance", atol=1e-24)
    return {
        "status": "pass",
        "scope": "SPEC-002 instantaneous checks only; no coupled integration or JAX model",
        "checks_passed": checks,
        "source_checks": source_checks,
        "physical_checks": checks - source_checks,
        "verified_utc": datetime.now(timezone.utc).isoformat(),
        "verifier_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "reference_sha256": hashlib.sha256(reference.read_bytes()).hexdigest(),
        "runtime": {"python": platform.python_version(), "numpy": np.__version__},
        "initial_transfer_fmol_per_s": initial_flux.tolist(),
        "initial_gate_target": float(gate_target(-0.02)),
        "initial_gate_slope_per_s": float(gate_slope(0.25, -0.02)),
        "maximum_passive_flux_potential_product": maximum_passive_product,
        "charge_roundoff_residual_C": float(external_charge_residual),
        "charge_roundoff_bound_C": float(charge_roundoff_bound),
        "resolved_energy_residual_J_per_s": float(omega_dot - supplied + dissipation),
        "source_law_counterexamples": limiting,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-reference", type=Path, default=FIXTURE)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = verify(args.source_reference)
    encoded = json.dumps(result, indent=2, allow_nan=False) + "\n"
    if args.output is not None:
        with args.output.open("x") as handle:
            handle.write(encoded)
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
