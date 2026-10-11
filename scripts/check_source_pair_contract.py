"""SPEC-003 instantaneous independent/native correspondence and structural checks.

Needs only the retained numeric fixture, not the upstream checkout. A passing
receipt establishes neither coupled trajectory accuracy nor a production model.
"""

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests import reference_source_pair as ref  # noqa: E402

FIXTURE = ROOT / "tests/fixtures/source_pair_probes.json"
SOURCE_FILES = (
    "scripts/capture_source_pair_reference.py",
    "scripts/capture_contact_reference.py",
    "scripts/capture_emt_reference.py",
    "scripts/check_source_pair_contract.py",
    "tests/reference_source_pair.py",
    "tests/reference_emt.py",
    "tests/unit/test_source_pair_contract.py",
    "configs/reference/source_emt_pair_panel_v1.json",
    "tests/fixtures/source_pair_probes.json",
    "requirements-reference.txt",
    "requirements-lock.txt",
    "docs/SOURCE_EMT_PAIR_SPEC.md",
)
AUDITS = {
    "primary_unchanged",
    "context_unchanged",
    "repeat_rhs_exact",
    "readouts_do_not_change_refreshed_packet",
    "nonprimary_native_slopes_zero",
    "regulatory_charge_excluded",
    "temporary_parameters_restored",
    "finite",
}
# Instantaneous arithmetic tolerances, not candidate trajectory-error targets.
TOLERANCES = {
    "voltage": (2e-13, 2e-12),
    "delta_v": (2e-13, 2e-12),
    "gate_scales": (2e-12, 2e-12),
    "leak_flux": (5e-21, 2e-12),
    "pump_flux": (5e-21, 2e-12),
    "junction_flux": (5e-21, 2e-12),
    "local_rate": (5e-12, 2e-12),
    "primary_rate": (5e-12, 2e-12),
    "packet": (5e-12, 2e-12),
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(fixture=FIXTURE, panel_path=ref.PANEL):
    panel = ref.load_panel(panel_path)
    native = json.loads(Path(fixture).read_text())
    count = 0
    maximum_errors = dict.fromkeys(TOLERANCES, 0.0)

    def require(condition, label):
        nonlocal count
        if not condition:
            raise ValueError(label)
        count += 1

    def close(actual, expected, label, atol=5e-12, rtol=2e-12):
        nonlocal count
        a, b = np.asarray(actual), np.asarray(expected)
        if a.shape != b.shape or not np.isfinite(a).all() or not np.isfinite(b).all():
            raise ValueError(f"Invalid shape/nonfinite {label}")
        if not np.allclose(a, b, atol=atol, rtol=rtol):
            raise ValueError(f"Mismatch {label}: max absolute error {np.max(np.abs(a - b))}")
        count += a.size

    require(native["schema_version"] == 1, "Native schema")
    require(native["revision"] == panel["source_revision"], "Native revision")
    require(native["panel_sha256"] == sha(Path(panel_path)), "Panel hash differs from capture")
    require(
        native["preparation_audit"]
        == {
            "capture_sha256": panel["preparation"]["capture_sha256"],
            "complete_packets_exact": True,
        },
        "Prepared full-state identity",
    )
    contact = json.loads((ROOT / "tests/fixtures/contact_source_probes.json").read_text())
    require(native["source_hashes"] == contact["source_hashes"], "Previously pinned source changed")
    probes = native["probes"]
    require(tuple(probes["row_names"]) == ref.PACKET, "Native packet ordering")
    require(
        probes["profile"]
        == {
            "iterate_binding": False,
            "mirna_target": -1,
            "mirna_drift_valence": -1,
            "mirna_in_voltage": False,
            "mirna_medium_size": True,
        },
        "Source approximation profile changed",
    )
    area, volume = ref.geometry(panel)
    close(probes["geometry"]["area"], area, "area", 0, 2e-15)
    close(probes["geometry"]["volume"], volume, "volume", 0, 2e-15)
    p = panel["parameters"]
    close(
        probes["geometry"]["ghk_voltage_factor"],
        p["F"] / (p["R"] * p["T"]),
        "GHK voltage factor",
        0,
        2e-15,
    )
    cases = {case["id"]: case for case in panel["cases"]}
    require(len(cases) == 14, "Incomplete/duplicate case panel")
    expected_keys = [
        (case["id"], time)
        for case in panel["cases"]
        for time in [0.0] + [event["time"] for event in case.get("events", [])]
    ]
    require(
        [(r["case_id"], r["control_time"]) for r in probes["records"]] == expected_keys,
        "Missing, duplicated, or reordered native control probes",
    )
    evaluations = {}
    native_slopes = {}
    for record in probes["records"]:
        case = cases[record["case_id"]]
        key = (case["id"], record["control_time"])
        primary, context = ref.initial_state(panel, case)
        primary_before, context_before = primary.copy(), context.copy()
        result = ref.evaluate(primary, context, panel, case, record["control_time"])
        evaluations[key] = result
        native_slopes[key] = np.asarray(record["primary_rate"])
        for name, (atol, rtol) in TOLERANCES.items():
            close(result[name], record[name], f"{key}/{name}", atol, rtol)
            maximum_errors[name] = max(
                maximum_errors[name], float(np.max(np.abs(result[name] - record[name])))
            )
        require(set(record["audits"]) == AUDITS, f"{key} incomplete native audits")
        for name in AUDITS:
            require(record["audits"][name] is True, f"{key}/{name}")
        before = np.asarray(record["input_packet"])
        close(before[ref.PRIMARY_INDEX], primary, f"{key} source input primary", 0, 0)
        close(before[ref.CONTEXT_INDEX], context, f"{key} source input context", 0, 0)
        require(
            not np.array_equal(before[ref.DERIVED_INDEX], result["packet"][ref.DERIVED_INDEX]),
            f"{key} caches were not stale in this probe",
        )
        close(primary, primary_before, f"{key} pure reference primary", 0, 0)
        close(context, context_before, f"{key} pure reference context", 0, 0)
        padded_rate = np.zeros((17, 2))
        padded_rate[ref.PRIMARY_INDEX] = result["primary_rate"]
        close(padded_rate, record["native_packet_rate"], f"{key} full native packet RHS")
        close(result["contact_rate"].sum(axis=1), np.zeros(6), f"{key} reciprocal exchange", 0, 0)
        close(
            np.array([1, 6, 15, 20, 15, 6, 1]) @ result["packet"][9:16],
            primary[4],
            f"{key} mRNA binding configurations",
        )
        # Assemble native readouts independently of either complete RHS.
        assembled = np.asarray(record["local_rate"]).copy()
        assembled[:3] += (np.asarray(record["leak_flux"]) + record["pump_flux"]) * area / volume
        edge = case.get("edge", [0, 1])
        incidence = np.zeros(2)
        incidence[edge] = [-1, 1]
        assembled[:4] += np.asarray(record["junction_flux"])[:, None] * incidence * area / volume
        close(assembled, record["primary_rate"], f"{key} separate native contribution assembly")

    def result(case):
        return evaluations[(case, 0)]

    close(result("S00")["junction_flux"], np.zeros(4), "blocked routes exact", 0, 0)
    require(abs(result("S01")["junction_flux"][3]) > 1e-8, "Active miRNA positive control")
    close(
        result("S02")["primary_rate"][3:],
        result("S00")["primary_rate"][3:],
        "ion-only does not instantly change regulatory slopes",
        0,
        0,
    )
    close(
        result("S03")["primary_rate"][:3],
        result("S00")["primary_rate"][:3],
        "miRNA-only does not change ionic slopes/charge",
        0,
        0,
    )
    close(
        result("S01")["primary_rate"],
        result("S02")["primary_rate"]
        + result("S03")["primary_rate"]
        - result("S00")["primary_rate"],
        "route decomposition",
    )
    close(
        result("S05")["primary_rate"],
        result("S07")["primary_rate"],
        "orientation with swapped hemichannels",
    )
    close(
        result("S05")["junction_flux"],
        -result("S07")["junction_flux"],
        "oriented ledger reverses",
        5e-21,
    )
    require(
        not np.allclose(result("S05")["gate_scales"], result("S06")["gate_scales"]),
        "Reversing heterotypic endpoints alone must change this model",
    )
    require(
        not np.allclose(native_slopes[("S05", 0)], native_slopes[("S06", 0)]),
        "Native heterotypic negative control has no effect",
    )
    for case in ("S08", "S09"):
        close(result(case)["leak_flux"], np.zeros((3, 2)), f"{case} zero leaks", 0, 0)
    close(result("S08")["pump_flux"], np.zeros((3, 2)), "No base permeability disables pump", 0, 0)
    require(
        np.max(np.abs(result("S09")["pump_flux"])) > 1e-8,
        "IC inhibition must not implicitly disable pump",
    )
    close(result("S10")["voltage"], np.zeros(2), "Zero voltage boundary", 0, 0)
    seed, _ = ref.initial_state(panel, cases["S10"])
    close(
        result("S10")["leak_flux"],
        np.asarray(panel["membrane_diffusion"])
        / p["tm"]
        * (np.asarray(panel["bath_ions"])[:, None] - seed[:3]),
        "GHK zero-voltage limit",
        5e-21,
    )
    close(
        evaluations[("S12", 0.137)]["primary_rate"],
        result("S01")["primary_rate"],
        "release changes control at unchanged state",
        0,
        0,
    )
    close(evaluations[("S13", 0.137)]["junction_flux"][3], 0, "miRNA pulse exact block", 0, 0)
    close(
        evaluations[("S13", 0.137)]["junction_flux"][:3],
        result("S13")["junction_flux"][:3],
        "miRNA pulse keeps ionic route",
        0,
        0,
    )
    close(
        evaluations[("S13", 0.274)]["primary_rate"],
        result("S13")["primary_rate"],
        "controls restored without fabricated gate history",
        0,
        0,
    )
    packet = result("S01")["packet"]
    binding_excess = np.array([0, 6, 30, 60, 60, 30, 6]) @ packet[9:16]
    require(np.all(binding_excess > 0), "Free proxy is not exact miRNA binding conservation")
    return {
        "status": "pass",
        "scope": "SPEC-003 instantaneous source-compatible pair only",
        "checks_passed": count,
        "cases": len(cases),
        "native_control_probes": len(expected_keys),
        "panel_sha256": sha(Path(panel_path)),
        "native_fixture_sha256": sha(Path(fixture)),
        "maximum_absolute_native_errors": maximum_errors,
        "instantaneous_tolerances_atol_rtol": TOLERANCES,
        "source_binding_excess_not_physical_mirna_inventory": binding_excess.tolist(),
        "trajectory_qualification": "not run",
        "production_implementation": "not implemented",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-reference", type=Path, default=FIXTURE)
    parser.add_argument("--output", type=Path, help="new evidence directory")
    args = parser.parse_args()
    if args.output is not None and args.output.exists():
        parser.error("Output must name a new directory")
    result = verify(args.source_reference)
    if args.output is not None:
        production = json.loads(
            (ROOT / "runs/model-004-2026-09-08/acceptance/verification.json").read_text()
        )
        live = {
            str(path.relative_to(ROOT / "src/cells")): sha(path)
            for path in sorted((ROOT / "src/cells").rglob("*.py"))
        }
        if live != production["source_hashes"]:
            raise ValueError("Production differs from accepted 0.6.0")
        args.output.mkdir(parents=True, exist_ok=False)
        identities = {name: sha(ROOT / name) for name in SOURCE_FILES}
        capsule = args.output / "reference_sources.zip"
        with zipfile.ZipFile(capsule, "x", compression=zipfile.ZIP_DEFLATED) as archive:
            for name in SOURCE_FILES:
                archive.write(ROOT / name, name)
        with zipfile.ZipFile(capsule) as archive:
            if any(
                hashlib.sha256(archive.read(name)).hexdigest() != digest
                for name, digest in identities.items()
            ):
                raise ValueError("Source capsule differs from evaluated files")
        result.update(
            {
                "source_hashes": identities,
                "source_capsule_sha256": sha(capsule),
                "production_source_hashes_unchanged": live,
            }
        )
        with (args.output / "verification.json").open("x") as handle:
            json.dump(result, handle, indent=2, sort_keys=True, allow_nan=False)
            handle.write("\n")
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
