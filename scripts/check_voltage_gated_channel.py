"""Check SPEC-006 gate arithmetic, analytic gate protocols and instantaneous coupling.

Offline, bounded equation checks. No production, native BETSE, implicit solver,
coupled-cell trajectory, numerical-method selection or biological fit is run.
"""

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
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests import reference_multispecies as ionic  # noqa: E402
from tests import reference_voltage_gated_channel as ref  # noqa: E402

PROTOCOL = ROOT / "configs/reference/voltage_gated_channel_v1.json"
FROZEN_PROTOCOL_SHA256 = "16b6e245ba2cef921fc48e1a4c7f8ebd03481724e7de5d1062fcf0d8fdeed09c"
RELEASE = ROOT / "runs/core-006-2026-09-09/release-audit.json"
RELEASE_SHA256 = "ec084d0f626fbb3793714bbb7ea346688d1f1244078869507396a57aec1f5005"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Checks:
    def __init__(self, tolerances):
        self.tolerances = tolerances
        self.groups = {}
        self.failures = []

    def require(self, group, label, passed, **details):
        entry = self.groups.setdefault(group, {"checks": 0, "failed": 0})
        entry["checks"] += 1
        if not passed:
            entry["failed"] += 1
            self.failures.append({"group": group, "label": label, **details})

    def close(self, group, label, actual, expected, tolerance):
        limit = self.tolerances[tolerance] + self.tolerances["rtol"] * abs(expected)
        error = abs(actual - expected)
        self.require(group, label, error <= limit, actual=actual, expected=expected, limit=limit)
        entry = self.groups[group]
        entry["max_normalized_error"] = max(entry.get("max_normalized_error", 0.0), error / limit)


def decimal_kinetics(voltage_V):
    """Literal source-unit expressions: mV and ms, unlike the SI scalar reference."""
    v = Decimal(str(voltage_V)) * 1000
    m = 1 / (1 + ((v + 6) / Decimal("-6.4")).exp())
    h = 1 / (1 + ((v + Decimal("25.3")) / Decimal("3.5")).exp())
    tm = (Decimal("8.33") - Decimal("0.1163") * v) / 1000
    th = (Decimal(1620) - Decimal("15.5") * v) / 1000
    return m, h, tm, th


def decimal_relax(voltage_V, gate, elapsed_s):
    k = decimal_kinetics(voltage_V)
    dt = Decimal(str(elapsed_s))
    return tuple(
        target + (Decimal(str(q)) - target) * (-dt / tau).exp()
        for q, target, tau in zip(gate, k[:2], k[2:], strict=True)
    )


def decimal_program(program):
    """Replay each requested prefix independently, keeping Decimal event history."""
    result = []
    for t in program.sample_times_s:
        gate = tuple(Decimal(str(v)) for v in (program.initial_gate.m, program.initial_gate.h))
        last = Decimal(0)
        current_v = program.voltage_steps[0][1]
        for time, v in program.voltage_steps[1:]:
            if time > t:
                break
            stamp = Decimal(str(time))
            gate = decimal_relax(current_v, gate, stamp - last)
            last, current_v = stamp, v
        gate = decimal_relax(current_v, gate, Decimal(str(t)) - last)
        result.append(gate)
    return result


def decimal_flux(p, channel, gate, availability, voltage_V, ci):
    """Direct GHK numerator, not the reference's separate Bernoulli factors."""

    def d(x):
        return Decimal(str(x))

    f = Decimal("6.02214076e23") * Decimal("1.602176634e-19")
    r = Decimal("6.02214076e23") * Decimal("1.380649e-23")
    index = p.species_ids.index(channel.species_id)
    x = p.valence[index] * f * d(voltage_V) / (r * d(p.temperature_K))
    co = d(p.bath_mM[index])
    inside = d(ci)
    drive = co - inside if x == 0 else x * (co - inside * x.exp()) / (x.exp() - 1)
    permeability = d(channel.max_permeability_m_per_s) * d(channel.abundance)
    permeability *= d(availability) * d(gate.m) * d(gate.h)
    return d(p.area_m2) * permeability * drive / Decimal("1e-15")


def gate_grid(panel, checks):
    probes = panel["gate_probes"]
    for v in probes["voltages_V"]:
        k = ref.kinetics(v)
        oracle = decimal_kinetics(v)
        for field, expected in zip(asdict(k), oracle, strict=True):
            checks.close(
                "source_unit_rates",
                f"{v}/{field}",
                getattr(k, field),
                float(expected),
                "time_constant_s" if field.startswith("tau") else "gate",
            )
        equilibrium = ref.equilibrium_gate(v)
        checks.require("equilibrium", str(v), ref.gate_rate(v, equilibrium) == (0.0, 0.0))
        for state in probes["states"]:
            gate = ref.Gate(*state)
            rates = ref.gate_rate(v, gate)
            for name, q, target, tau, rate in zip(
                ("m", "h"), state, oracle[:2], oracle[2:], rates, strict=True
            ):
                checks.close(
                    "gate_derivatives",
                    f"{v}/{state}/{name}",
                    rate,
                    float((target - Decimal(str(q))) / tau),
                    "rate_per_s",
                )
                checks.require(
                    "inward_gate_domain",
                    f"{v}/{state}/{name}",
                    (q != 0 or rate >= 0) and (q != 1 or rate <= 0),
                )
            for time_scale, factor in itertools.product(
                (k.tau_m_s, k.tau_h_s), probes["elapsed_tau_factors"]
            ):
                elapsed = time_scale * factor
                result = ref.relax_gate(v, gate, elapsed)
                expected = decimal_relax(v, state, elapsed)
                for name, q, actual, target, wanted in zip(
                    ("m", "h"), state, (result.m, result.h), oracle[:2], expected, strict=True
                ):
                    label = f"{v}/{state}/{name}/{elapsed}"
                    checks.close("decimal_relaxation", label, actual, float(wanted), "gate")
                    checks.require(
                        "monotone_relaxation",
                        label,
                        min(q, float(target)) - 2e-15 <= actual <= max(q, float(target)) + 2e-15,
                    )
                if elapsed == 0:
                    checks.require("zero_elapsed", f"{v}/{state}", result is gate)
            split = ref.relax_gate(v, ref.relax_gate(v, gate, k.tau_m_s * 0.37), k.tau_m_s * 1.31)
            whole = ref.relax_gate(v, gate, k.tau_m_s * (0.37 + 1.31))
            for name in ("m", "h"):
                checks.close(
                    "held_voltage_semigroup",
                    f"{v}/{state}/{name}",
                    getattr(split, name),
                    getattr(whole, name),
                    "gate",
                )


def protocol_checks(panel, checks):
    protocols = {}
    for item in panel["protocols"]:
        name, program = item["id"], ref.resolve_program(item["protocol"])
        rows = ref.sample_program(program)
        expected = decimal_program(program)
        enabled = ref.sample_program(replace(program, availability_steps=((0.0, 1.0),)))
        sparse = ref.sample_program(replace(program, sample_times_s=program.sample_times_s[::2]))
        checks.require("sampling_independence", name, sparse == rows[::2])
        for row, wanted, on in zip(rows, expected, enabled, strict=True):
            label = f"{name}/{row.time_s}"
            for field, value in zip(("m", "h"), wanted, strict=True):
                checks.close(
                    "decimal_protocol",
                    f"{label}/{field}",
                    getattr(row, field),
                    float(value),
                    "gate",
                )
            controls = [u for t, u in program.availability_steps if t <= row.time_s]
            volts = [v for t, v in program.voltage_steps if t <= row.time_s]
            checks.require(
                "right_continuous_readout",
                label,
                row.availability == controls[-1] and row.voltage_V == volts[-1],
            )
            checks.close(
                "open_fraction", label, row.open_probability, float(wanted[0] * wanted[1]), "gate"
            )
            checks.require(
                "availability_separation",
                label,
                (row.m, row.h, row.dm_per_s, row.dh_per_s) == (on.m, on.h, on.dm_per_s, on.dh_per_s)
                and row.available_open_fraction == row.availability * row.open_probability,
            )
        if program.voltage_steps[-1][0] == program.end_time_s:
            prior = ref.sample_program(replace(program, voltage_steps=program.voltage_steps[:-1]))[
                -1
            ]
            final = rows[-1]
            checks.require(
                "final_event_no_duration",
                name,
                (prior.m, prior.h) == (final.m, final.h) and prior.voltage_V != final.voltage_V,
            )
        protocols[name] = [asdict(row) for row in rows]
    a, b = protocols["equal_open_a"], protocols["equal_open_b"]
    checks.require(
        "hidden_gate_history",
        "same present open fraction",
        a[0]["open_probability"] == b[0]["open_probability"],
    )
    checks.require(
        "hidden_gate_history",
        "different future under common voltage",
        abs(a[1]["open_probability"] - b[1]["open_probability"]) > checks.tolerances["gate"],
    )
    return protocols


def with_voltage(resolved, target):
    """Explicit hypothetical charge-consistent probe, never a definition repair."""
    p = resolved.assembly
    fixed = p.capacitance_F * target / ionic.CHARGE_PER_FMOL - math.fsum(
        z * n for z, n in zip(p.valence, p.initial_amount_fmol, strict=True)
    )
    return replace(
        resolved, assembly=replace(p, fixed_charge_equivalent_fmol=fixed, initial_voltage_V=target)
    )


def assembly_checks(panel, checks):
    results = []
    for case in panel["cases"]:
        name, p = case["id"], ref.resolve(case["definition"])
        base = p.assembly
        initial = base.initial_amount_fmol
        offset = tuple(n + (i + 1) * 1e-6 for i, n in enumerate(initial))
        for amount, state, u in itertools.product(
            (initial, offset), panel["gate_probes"]["states"], (0.0, 0.37, 1.0)
        ):
            gate = ref.Gate(*state)
            controls = tuple((i + 1) / (len(initial) + 1) for i in range(len(initial)))
            result = ref.evaluate(
                p, amount, gate, leak_control=controls, pump_control=0.73, availability=u
            )
            label = f"{name}/{amount}/{state}/{u}"
            oracle = decimal_flux(
                base,
                p.channel,
                gate,
                u,
                result.baseline.voltage_V,
                result.baseline.concentration_mM[p.species_index],
            )
            checks.close(
                "decimal_channel_flux",
                label,
                result.channel_flux_fmol_per_s,
                float(oracle),
                "flux_fmol_per_s",
            )
            checks.require(
                "channel_dissipation",
                label,
                result.channel_dissipation_W >= -checks.tolerances["negative_dissipation_W"],
            )
            for i, (a, b, extra, outside) in enumerate(
                zip(
                    result.amount_rate_fmol_per_s,
                    result.baseline.amount_rate_fmol_per_s,
                    result.channel_species_rate_fmol_per_s,
                    result.bath_rate_fmol_per_s,
                    strict=True,
                )
            ):
                checks.close("material_rate", f"{label}/{i}", a, b + extra, "flux_fmol_per_s")
                checks.require("bath_rate", f"{label}/{i}", outside == -a)
                checks.require(
                    "bound_species_only", f"{label}/{i}", i == p.species_index or extra == 0
                )
            checks.close(
                "charge_rate",
                label,
                result.voltage_rate_V_per_s,
                ionic.CHARGE_PER_FMOL
                / base.capacitance_F
                * math.fsum(
                    z * j for z, j in zip(base.valence, result.amount_rate_fmol_per_s, strict=True)
                ),
                "voltage_rate_V_per_s",
            )
            checks.close(
                "ionic_energy_rate",
                label,
                result.stored_ionic_capacitor_energy_rate_W,
                result.baseline.chemical_power_W - 1e-12 * result.ionic_dissipation_rate_pJ_per_s,
                "power_W",
            )
            if u == 0 or gate.open_probability == 0:
                checks.require(
                    "off_reduction",
                    label,
                    result.channel_flux_fmol_per_s == 0
                    and result.amount_rate_fmol_per_s == result.baseline.amount_rate_fmol_per_s,
                )
        g = ref.Gate(0.4, 0.6)
        nominal = ref.evaluate(p, gate=g)
        for field in ("abundance", "max_permeability_m_per_s"):
            off = ref.evaluate(replace(p, channel=replace(p.channel, **{field: 0.0})), gate=g)
            checks.require(
                "zero_parameter_keeps_gates",
                f"{name}/{field}",
                off.channel_flux_fmol_per_s == 0 and off.gate_rate_per_s == nominal.gate_rate_per_s,
            )
            doubled = ref.evaluate(
                replace(p, channel=replace(p.channel, **{field: 2 * getattr(p.channel, field)})),
                gate=g,
            )
            checks.close(
                "independent_abundance_permeability",
                f"{name}/{field}",
                doubled.channel_flux_fmol_per_s,
                2 * nominal.channel_flux_fmol_per_s,
                "flux_fmol_per_s",
            )
        larger = replace(
            base,
            area_m2=2 * base.area_m2,
            specific_capacitance_F_per_m2=base.specific_capacitance_F_per_m2 / 2,
        )
        enlarged = ref.evaluate(replace(p, assembly=larger), gate=g)
        checks.close(
            "area_not_gate_kinetics",
            name,
            enlarged.channel_flux_fmol_per_s,
            2 * nominal.channel_flux_fmol_per_s,
            "flux_fmol_per_s",
        )
        checks.require(
            "area_not_gate_kinetics", name, enlarged.gate_rate_per_s == nominal.gate_rate_per_s
        )
        ci = initial[p.species_index] / base.volume_pL
        reversal = (
            ionic.R * base.temperature_K / ionic.F * math.log(base.bath_mM[p.species_index] / ci)
        )
        checks.close(
            "nernst_channel",
            name,
            ref.evaluate(with_voltage(p, reversal), gate=g).channel_flux_fmol_per_s,
            0.0,
            "flux_fmol_per_s",
        )
        zero = ref.evaluate(with_voltage(p, 0.0), gate=g)
        checks.close(
            "zero_voltage_diffusion",
            name,
            zero.channel_flux_fmol_per_s,
            base.area_m2
            * zero.effective_permeability_m_per_s
            / ionic.MOL_PER_FMOL
            * (base.bath_mM[p.species_index] - ci),
            "flux_fmol_per_s",
        )
        for order in itertools.permutations(case["definition"]["assembly"]["species"]):
            definition = copy.deepcopy(case["definition"])
            definition["assembly"]["species"] = list(order)
            permuted = ref.resolve(definition)
            actual = ref.evaluate(permuted, gate=g)
            expected_map = dict(zip(base.species_ids, nominal.amount_rate_fmol_per_s, strict=True))
            actual_map = dict(
                zip(permuted.assembly.species_ids, actual.amount_rate_fmol_per_s, strict=True)
            )
            checks.require(
                "species_permutation",
                f"{name}/{permuted.assembly.species_ids}",
                actual_map == expected_map
                and actual.gate_rate_per_s == nominal.gate_rate_per_s
                and actual.channel_flux_fmol_per_s == nominal.channel_flux_fmol_per_s,
            )
        results.append({"id": name, "resolved": asdict(p), "open_probe": asdict(nominal)})
    return results


def verify():
    if sha(PROTOCOL) != FROZEN_PROTOCOL_SHA256:
        raise ValueError("Frozen SPEC-006 panel changed; retain evidence and version a revision")
    if sha(RELEASE) != RELEASE_SHA256:
        raise ValueError("Accepted production release identity changed")
    panel = ionic.load_json(PROTOCOL)
    base_path = ROOT / panel["base_panel"]["path"]
    if sha(base_path) != panel["base_panel"]["sha256"]:
        raise ValueError("Frozen SPEC-005 base panel changed")
    bases = ionic.load_json(base_path)["cases"]
    assert [c["definition"]["assembly"] for c in panel["cases"]] == [c["assembly"] for c in bases]
    production = {
        str(p.relative_to(ROOT / "src/cells")): sha(p)
        for p in sorted((ROOT / "src/cells").rglob("*.py"))
    }
    assert production == json.loads(RELEASE.read_text())["source_hashes"]
    checks = Checks(panel["tolerances"])
    with localcontext() as context:
        context.prec = panel["gate_probes"]["decimal_precision"]
        gate_grid(panel, checks)
        protocols = protocol_checks(panel, checks)
        assemblies = assembly_checks(panel, checks)
    smallest = min(ref.kinetics(v).tau_m_s for v in ref.VOLTAGE_DOMAIN_V)
    ratio = 0.01 / smallest
    amplification = 1 - ratio + ratio**2 / 2 - ratio**3 / 6 + ratio**4 / 24
    checks.require(
        "old_step_not_inherited", "linear held-gate RK4 amplification", abs(amplification) > 1
    )
    sources = (
        "configs/reference/voltage_gated_channel_v1.json",
        "docs/VOLTAGE_GATED_CHANNEL_SPEC.md",
        "tests/reference_voltage_gated_channel.py",
        "scripts/check_voltage_gated_channel.py",
        "tests/unit/test_voltage_gated_channel_reference.py",
        "tests/reference_multispecies.py",
        "configs/reference/multispecies_membrane_v1.json",
        "pyproject.toml",
        "requirements-lock.txt",
        "requirements-reference.txt",
    )
    return {
        "status": "fail" if checks.failures else "pass",
        "scope": panel["scope"],
        "verified_utc": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(),
        "protocol_sha256": FROZEN_PROTOCOL_SHA256,
        "production_release_sha256": RELEASE_SHA256,
        "source_sha256": {s: sha(ROOT / s) for s in sources},
        "production_source_sha256": production,
        "checks": sum(g["checks"] for g in checks.groups.values()),
        "checks_failed": len(checks.failures),
        "groups": checks.groups,
        "failures": checks.failures,
        "tolerances": panel["tolerances"],
        "gate_protocols": protocols,
        "assemblies": assemblies,
        "diagnostic_10ms_RK4_fast_gate_amplification": amplification,
        "gate_reference": "analytic prescribed-voltage responses",
        "coupled_trajectory_qualification": "not_performed",
        "method_selection": "not_performed",
        "native_betse_execution": False,
        "production_change": False,
        "gpu_qualification": "not_performed",
        "biological_acceptance": "not_assessable",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Optional new receipt, never overwrite")
    args = parser.parse_args()
    if args.output is not None and args.output.exists():
        raise FileExistsError("Choose a new receipt path; earlier evidence is immutable")
    result = verify()
    payload = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if args.output is not None:
        with args.output.open("x") as handle:
            handle.write(payload)
    print(payload, end="")
    return int(result["status"] != "pass")


if __name__ == "__main__":
    raise SystemExit(main())
