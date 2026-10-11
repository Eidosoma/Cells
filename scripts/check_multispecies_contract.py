"""Recompute the frozen SPEC-005 instantaneous panel; no simulator or trajectory run."""

import argparse
import copy
import hashlib
import itertools
import json
import math
import platform
import sys
from dataclasses import asdict, replace
from datetime import datetime, timezone
from decimal import Decimal, localcontext
from importlib.metadata import version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests import reference_bioelectric as legacy  # noqa: E402
from tests import reference_multispecies as ref  # noqa: E402

PROTOCOL = ROOT / "configs/reference/multispecies_membrane_v1.json"
FROZEN_PROTOCOL_SHA256 = "a5b267af9f88f218673e585ba1e3e575a9a85cb567ae24d3542721e13cfe6f34"


class Checks:
    def __init__(self, rtol):
        self.rtol = rtol
        self.groups = {}
        self.failures = []

    def require(self, group, label, passed, **details):
        item = self.groups.setdefault(group, {"checks": 0, "failed": 0})
        item["checks"] += 1
        if not passed:
            item["failed"] += 1
            self.failures.append({"group": group, "label": label, **details})

    def close(self, group, label, actual, expected, atol):
        limit = atol + self.rtol * abs(expected)
        error = abs(actual - expected)
        self.require(group, label, error <= limit, actual=actual, expected=expected, limit=limit)
        item = self.groups[group]
        item["max_normalized_error"] = max(item.get("max_normalized_error", 0.0), error / limit)


def decimal_passive(z, ci, co, voltage, temperature, area, permeability, precision):
    """Direct GHK exponential numerator, not the reference's two Bernoulli factors."""
    with localcontext() as context:
        context.prec = precision
        avogadro = Decimal("6.02214076e23")
        faraday = avogadro * Decimal("1.602176634e-19")
        gas = avogadro * Decimal("1.380649e-23")
        inside, outside, v, t, a, p = (
            Decimal(str(value)) for value in (ci, co, voltage, temperature, area, permeability)
        )
        x = z * faraday * v / (gas * t)
        diff = outside - inside if x == 0 else x * (outside - inside * x.exp()) / (x.exp() - 1)
        flux = a * p / Decimal("1e-15") * diff
        mu = gas * t * (inside.ln() - outside.ln()) + z * faraday * v
        return float(flux), float(mu)


def passive_panel(protocol, checks):
    grid, tol = protocol["passive_probe"], protocol["tolerances"]
    t, area, permeability = (grid[k] for k in ("temperature_K", "area_m2", "permeability_m_per_s"))
    for z, x, (ci, co) in itertools.product(
        grid["valences"], grid["dimensionless_voltages"], grid["concentration_pairs_mM"]
    ):
        label = f"z={z},x={x},ci={ci},co={co}"
        voltage = x * ref.R * t / (z * ref.F)
        args = (z, ci, co, voltage, t, area, permeability)
        flux = ref.passive_flux(*args)
        mu = ref.potential(z, ci, co, voltage, t)
        oracle_flux, oracle_mu = decimal_passive(*args, grid["decimal_precision"])
        checks.close("decimal_flux", label, flux, oracle_flux, tol["flux_fmol_per_s"])
        checks.close("decimal_potential", label, mu, oracle_mu, tol["potential_J_per_mol"])
        dissipation = -ref.MOL_PER_FMOL * flux * mu
        checks.require(
            "passive_dissipation",
            label,
            dissipation >= -tol["negative_dissipation_W"],
            dissipation_W=dissipation,
        )
        swapped = ref.passive_flux(z, co, ci, -voltage, t, area, permeability)
        checks.close("orientation", label, swapped, -flux, tol["flux_fmol_per_s"])
        doubled = ref.passive_flux(z, ci, co, voltage, t, 2 * area, permeability)
        checks.close("passive_area", label, doubled, 2 * flux, tol["flux_fmol_per_s"])
        checks.require(
            "passive_off",
            label,
            ref.passive_flux(*args, control=0.0) == 0.0
            and ref.passive_flux(z, ci, co, voltage, t, area, 0.0) == 0.0,
        )
        if x == 0:
            checks.close(
                "zero_voltage",
                label,
                flux,
                area * permeability / ref.MOL_PER_FMOL * (co - ci),
                tol["flux_fmol_per_s"],
            )
    for z, (ci, co) in itertools.product(grid["valences"], grid["concentration_pairs_mM"]):
        equilibrium = ref.R * t / (z * ref.F) * math.log(co / ci)
        flux = ref.passive_flux(z, ci, co, equilibrium, t, area, permeability)
        checks.close("nernst", f"z={z},ci={ci},co={co}", flux, 0.0, tol["nernst_flux_fmol_per_s"])


def legacy_reduction(protocol, checks):
    p = ref.resolve(protocol["cases"][0]["assembly"])
    old, control = legacy.Parameters(), legacy.Control()
    tol = protocol["tolerances"]
    checks.require(
        "legacy_definition",
        "species/boundary/geometry/drive",
        p.species_ids == ("Na", "K", "Cl")
        and p.valence == (1, 1, -1)
        and p.stoichiometry == (-3, 2, 0)
        and p.initial_amount_fmol == tuple(old.initial_amount)
        and p.bath_mM == old.bath_mM
        and p.permeability_m_per_s == old.permeability_m_per_s
        and p.volume_pL == old.volume_pL
        and p.area_m2 == old.area_m2
        and p.capacitance_F == old.capacitance
        and p.temperature_K == old.temperature_K
        and p.initial_voltage_V == old.initial_voltage_V
        and p.capacity_fmol_per_s == old.pump_capacity_fmol_per_s
        and p.drive_J_per_mol == old.atp_free_energy_J_per_mol
        and p.bath_background_charge_mM == 0.0,
    )
    checks.close(
        "legacy_fixed_charge",
        "anchor",
        -p.fixed_charge_equivalent_fmol,
        old.fixed_anion_equivalent,
        tol["amount_fmol"],
    )
    for voltage in protocol["reduction_voltages_V"]:
        old_flux, old_rate, old_mu, old_energy = legacy.fluxes(
            old, old.initial_amount, voltage, control
        )
        mu = []
        for i, (z, n, co, permeability) in enumerate(
            zip(p.valence, p.initial_amount_fmol, p.bath_mM, p.permeability_m_per_s, strict=True)
        ):
            label = f"V={voltage},species={p.species_ids[i]}"
            flux = ref.passive_flux(
                z, n / p.volume_pL, co, voltage, p.temperature_K, p.area_m2, permeability
            )
            mu.append(ref.potential(z, n / p.volume_pL, co, voltage, p.temperature_K))
            checks.close("legacy_flux", label, flux, float(old_flux[i]), tol["flux_fmol_per_s"])
            checks.close(
                "legacy_potential", label, mu[-1], float(old_mu[i]), tol["potential_J_per_mol"]
            )
        rate, energy = ref.pump_cycle(p, mu)
        checks.close("legacy_pump_rate", str(voltage), rate, old_rate, tol["flux_fmol_per_s"])
        checks.close(
            "legacy_pump_energy", str(voltage), energy, old_energy, tol["cycle_energy_J_per_mol"]
        )


def assembly_panel(case, protocol, checks):
    name, tol = case["id"], protocol["tolerances"]
    p = ref.resolve(case["assembly"])
    result = ref.evaluate(p)
    checks.close("initial_charge", name, p.anchor_residual_V, 0.0, tol["voltage_V"])
    checks.close("bath_charge", name, p.bath_charge_residual_mM, 0.0, tol["bath_charge_mM"])
    checks.require(
        "stoichiometry",
        name,
        sum(z * nu for z, nu in zip(p.valence, p.stoichiometry, strict=True)) == -1,
    )
    for s, n, concentration in zip(
        p.species_ids, p.initial_amount_fmol, result.concentration_mM, strict=True
    ):
        checks.close(
            "units",
            f"{name}/{s}",
            concentration,
            n * ref.MOL_PER_FMOL / (p.volume_pL * ref.M3_PER_PL),
            tol["amount_fmol"],
        )
    for drive in protocol["pump_drive_probes_J_per_mol"]:
        varied = replace(p, drive_J_per_mol=drive)
        driven = ref.evaluate(varied)
        checks.require(
            "pump_dissipation",
            f"{name}/{drive}",
            driven.pump_dissipation_W >= -tol["negative_dissipation_W"],
        )
        check_rates_and_energy(varied, driven, checks, tol, f"{name}/drive={drive}")
    transport_energy = math.fsum(
        nu * mu for nu, mu in zip(p.stoichiometry, result.potential_J_per_mol, strict=True)
    )
    for offset in protocol["stall_offsets_J_per_mol"]:
        rate, energy = ref.pump_cycle(
            replace(p, drive_J_per_mol=-transport_energy + offset), result.potential_J_per_mol
        )
        checks.close(
            "pump_stall_energy", f"{name}/{offset}", energy, offset, tol["cycle_energy_J_per_mol"]
        )
        checks.require(
            "pump_direction",
            f"{name}/{offset}",
            rate > 0 if offset < 0 else rate == 0 if offset == 0 else rate < 0,
        )
    off = ref.evaluate(p, leak_control=[0.0] * len(p.species_ids), pump_control=0.0)
    checks.require(
        "assembly_off",
        name,
        all(j == 0.0 for j in off.amount_rate_fmol_per_s)
        and off.inward_current_A == 0.0
        and off.voltage_rate_V_per_s == 0.0
        and off.voltage_V == result.voltage_V,
    )
    no_pump = replace(
        p,
        pump_id=None,
        pump_roles=None,
        stoichiometry=(0,) * len(p.species_ids),
        capacity_fmol_per_s=0.0,
        drive_J_per_mol=0.0,
    )
    passive_only = ref.evaluate(no_pump)
    checks.require(
        "absent_pump",
        name,
        passive_only.cycle_energy_J_per_mol is None
        and passive_only.amount_rate_fmol_per_s == result.passive_fmol_per_s
        and passive_only.pump_cycles_fmol_per_s == 0.0,
    )
    # Independent area/capacitance parameters: keep C and the charge anchor fixed.
    area_only = replace(
        p, area_m2=2 * p.area_m2, specific_capacitance_F_per_m2=p.specific_capacitance_F_per_m2 / 2
    )
    enlarged = ref.evaluate(area_only)
    checks.require(
        "capacity_not_area_density",
        name,
        enlarged.pump_cycles_fmol_per_s == result.pump_cycles_fmol_per_s
        and enlarged.passive_fmol_per_s == tuple(2 * j for j in result.passive_fmol_per_s),
    )
    leak = tuple(case["ledger_probe"]["passive_fmol"][s] for s in p.species_ids)
    cycles = case["ledger_probe"]["pump_cycles_fmol"]
    amount = tuple(
        n + transfer + nu * cycles
        for n, transfer, nu in zip(p.initial_amount_fmol, leak, p.stoichiometry, strict=True)
    )
    ledger = ref.ledger_residuals(p, amount, leak, cycles)
    for i, s in enumerate(p.species_ids):
        checks.close(
            "material_ledger",
            f"{name}/{s}",
            ledger["material_residual_fmol"][i],
            0.0,
            tol["amount_fmol"],
        )
        checks.close(
            "bath_ledger",
            f"{name}/{s}",
            amount[i] - p.initial_amount_fmol[i] + ledger["bath_exchange_fmol"][i],
            0.0,
            tol["amount_fmol"],
        )
    checks.close("charge_ledger", name, ledger["charge_residual_V"], 0.0, tol["voltage_V"])
    checks.close(
        "direct_charge", name, p.direct_voltage(amount), p.voltage(amount), tol["voltage_V"]
    )
    check_rates_and_energy(
        p, ref.evaluate(p, amount), checks, tol, f"{name}/algebraic_ledger_state"
    )
    permutation_checks(case, p, result, checks, tol)
    if 2 in p.valence:
        slot = p.valence.index(2)
        controls = tuple(0.0 if i == slot else 1.0 for i in range(len(p.species_ids)))
        blocked_p = replace(
            p,
            permeability_m_per_s=tuple(
                0.0 if i == slot else value for i, value in enumerate(p.permeability_m_per_s)
            ),
        )
        disabled = ref.evaluate(blocked_p)
        checks.require(
            "inactive_species",
            name,
            disabled == ref.evaluate(p, leak_control=controls)
            and disabled.passive_fmol_per_s[slot] == 0.0
            and disabled.voltage_V == result.voltage_V,
        )
        perturbed = list(p.initial_amount_fmol)
        perturbed[slot] += leak[slot]
        charged = ref.evaluate(blocked_p, perturbed)
        checks.close(
            "inactive_charge",
            name,
            charged.voltage_V - disabled.voltage_V,
            p.valence[slot] * ref.CHARGE_PER_FMOL * leak[slot] / p.capacitance_F,
            tol["voltage_V"],
        )
    return {
        "id": name,
        "species_ids": p.species_ids,
        "resolved": asdict(p),
        "initial": asdict(result),
        "anchor_residual_V": p.anchor_residual_V,
        "bath_charge_residual_mM": p.bath_charge_residual_mM,
        "algebraic_ledger_probe": {"amount_fmol": amount, **ledger},
    }


def check_rates_and_energy(p, result, checks, tol, label):
    # Compute expected species rates using chemical roles, not the resolved nu vector.
    sodium, potassium = p.pump_roles
    expected_rates = tuple(
        j + (-3 if s == sodium else 2 if s == potassium else 0) * result.pump_cycles_fmol_per_s
        for s, j in zip(p.species_ids, result.passive_fmol_per_s, strict=True)
    )
    for s, actual, expected, bath in zip(
        p.species_ids,
        result.amount_rate_fmol_per_s,
        expected_rates,
        result.bath_rate_fmol_per_s,
        strict=True,
    ):
        checks.close("material_rate", f"{label}/{s}", actual, expected, tol["flux_fmol_per_s"])
        checks.close("bath_rate", f"{label}/{s}", actual + bath, 0.0, tol["flux_fmol_per_s"])
    expected_current = ref.CHARGE_PER_FMOL * math.fsum(
        z * j for z, j in zip(p.valence, expected_rates, strict=True)
    )
    checks.close("current", label, result.inward_current_A, expected_current, tol["current_A"])
    checks.close(
        "capacitor_rate",
        label,
        p.capacitance_F * result.voltage_rate_V_per_s,
        expected_current,
        tol["current_A"],
    )
    checks.close(
        "energy_identity",
        label,
        result.stored_energy_rate_W,
        result.chemical_power_W
        - math.fsum(result.passive_dissipation_W)
        - result.pump_dissipation_W,
        tol["power_W"],
    )


def permutation_checks(case, p, result, checks, tol):
    vector_fields = (
        "concentration_mM",
        "potential_J_per_mol",
        "passive_fmol_per_s",
        "pump_species_fmol_per_s",
        "amount_rate_fmol_per_s",
        "bath_rate_fmol_per_s",
        "passive_dissipation_W",
    )
    for ordering in itertools.permutations(case["assembly"]["species"]):
        definition = copy.deepcopy(case["assembly"])
        definition["species"] = list(ordering)
        permuted = ref.resolve(definition)
        actual = ref.evaluate(permuted)
        indices = [permuted.species_ids.index(s) for s in p.species_ids]
        restored = replace(
            actual,
            **{key: tuple(getattr(actual, key)[i] for i in indices) for key in vector_fields},
        )
        # fsum makes these tiny tuple reductions storage-order independent on this CPU.
        checks.require(
            "species_permutation", f"{case['id']}/{permuted.species_ids}", restored == result
        )


def verify():
    if hashlib.sha256(PROTOCOL.read_bytes()).hexdigest() != FROZEN_PROTOCOL_SHA256:
        raise ValueError("Frozen panel changed: retain prior evidence and version any new protocol")
    protocol = ref.load_json(PROTOCOL)
    checks = Checks(protocol["tolerances"]["rtol"])
    checks.require("units", "fmol/pL equals mol/m3", ref.MOL_PER_FMOL / ref.M3_PER_PL == 1.0)
    passive_panel(protocol, checks)
    legacy_reduction(protocol, checks)
    cases = [assembly_panel(case, protocol, checks) for case in protocol["cases"]]
    sources = (
        "configs/reference/multispecies_membrane_v1.json",
        "docs/MULTISPECIES_MEMBRANE_SPEC.md",
        "tests/reference_multispecies.py",
        "tests/reference_bioelectric.py",
        "scripts/check_multispecies_contract.py",
        "tests/unit/test_multispecies_reference.py",
        "pyproject.toml",
        "requirements-lock.txt",
        "requirements-reference.txt",
    )
    return {
        "status": "fail" if checks.failures else "pass",
        "scope": protocol["scope"],
        "protocol_schema": protocol["schema"],
        "verified_utc": datetime.now(timezone.utc).isoformat(),
        "runtime": {
            "python": platform.python_version(),
            "numpy": legacy.np.__version__,
            "scipy": version("scipy"),
        },
        "protocol_sha256": FROZEN_PROTOCOL_SHA256,
        "source_sha256": {s: hashlib.sha256((ROOT / s).read_bytes()).hexdigest() for s in sources},
        "checks": sum(g["checks"] for g in checks.groups.values()),
        "checks_failed": len(checks.failures),
        "groups": checks.groups,
        "failures": checks.failures,
        "tolerances": protocol["tolerances"],
        "cases": cases,
        "trajectory_qualification": "not_performed",
        "production_change": False,
        "biological_acceptance": "not_assessable",
        "gpu_qualification": "not_performed",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Optional new JSON receipt; never overwrite")
    args = parser.parse_args()
    if args.output is not None and args.output.exists():
        raise FileExistsError("Choose a new receipt path; prior evidence is immutable")
    report = verify()
    payload = json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if args.output is not None:
        with args.output.open("x") as handle:
            handle.write(payload)
    print(payload, end="")
    return 1 if report["status"] != "pass" else 0


if __name__ == "__main__":
    raise SystemExit(main())
