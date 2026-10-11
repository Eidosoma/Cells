"""Read-only payload/capsule and native-accepted-state audit for NUM-003.

Uses NumPy and literal contract identities, not Cells or either reference RHS.
Optional JSON output must be new. Does not rerun any simulation.
"""

import argparse
import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

F = 6.02214076e23 * 1.602176634e-19
R = 6.02214076e23 * 1.380649e-23
Z = np.array([1.0, 1.0, -1.0])
NU = np.array([-3.0, 2.0, 0.0])


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def native_balances(case, values):
    if values.ndim != 2 or values.shape[1] != 21 or not np.isfinite(values).all():
        raise ValueError("Invalid native accepted array")
    cells = case["parameters"]["cells"]
    edge = case["parameters"]["junction"]
    volumes = np.array([p["volume_pL"] for p in cells])
    initial = np.array([p["initial_mM"] for p in cells]).T * volumes
    capacitance = np.array([p["area_m2"] * p["specific_capacitance_F_per_m2"] for p in cells])
    v0 = np.array([p["initial_voltage_V"] for p in cells])
    temperature = cells[0]["temperature_K"]
    delta = values[:, :6].reshape(-1, 3, 2)
    amount = initial + delta
    voltage = v0 + F * 1e-15 / capacitance * np.einsum("s,tsc->tc", Z, delta)
    all_voltage = np.column_stack([voltage, voltage[:, 0] - voltage[:, 1]])
    if np.any(amount <= 0) or np.any(values[:, 17] < 0) or np.any(values[:, 17] > 1):
        raise ValueError("Native accepted amounts/gates outside the contract domain")
    if np.max(np.abs(all_voltage)) * F / (R * temperature) > 50:
        raise ValueError("Native accepted voltage outside the contract domain")
    expected = values[:, 6:12].reshape(-1, 3, 2) + NU[None, :, None] * values[:, None, 12:14]
    expected[:, :, edge["endpoints"][0]] -= values[:, 14:17]
    expected[:, :, edge["endpoints"][1]] += values[:, 14:17]
    material = delta - expected
    charge = F * 1e-15 / capacitance * np.einsum("s,tsc->tc", Z, material)
    bath = np.asarray(cells[0]["bath_mM"])[:, None]
    # Independently evaluate the potential *change*, without subtracting two
    # large absolute potentials. This also returns exactly zero for a gate-only
    # change, despite different scalar/batched summation orders in a direct form.
    chemical_change = (
        1e-3
        * R
        * temperature
        * np.sum(
            delta * (np.log(initial / volumes / bath) - 1) + amount * np.log1p(delta / initial),
            axis=(1, 2),
        )
    )
    voltage_change = F * 1e-15 / capacitance * np.einsum("s,tsc->tc", Z, delta)
    electric = 0.5e12 * np.sum(capacitance * voltage_change * (2 * v0 + voltage_change), axis=1)
    supplied = -1e-3 * cells[0]["atp_free_energy_J_per_mol"] * values[:, 12:14].sum(axis=1)
    energy = chemical_change + electric + values[:, 18:21].sum(axis=1) - supplied
    if np.min(np.diff(values[:, 18:21], axis=0), initial=0) < -1e-10:
        raise ValueError("Native accepted dissipation decreases beyond the diagnostic tolerance")
    return {
        "amount_fmol": float(np.max(np.abs(material))),
        "charge_as_voltage_V": float(np.max(np.abs(charge))),
        "energy_pJ": float(np.max(np.abs(energy))),
    }


def audit(path):
    receipt = json.loads((path / "verification.json").read_text())
    if receipt["status"] not in ("pass", "study_complete"):
        raise ValueError("Receipt does not identify a completed qualification or study")
    for name, digest in receipt["files_sha256"].items():
        if sha(path / name) != digest:
            raise ValueError(f"Payload hash mismatch: {name}")
    with zipfile.ZipFile(path / "reference_sources.zip") as archive:
        if set(archive.namelist()) != set(receipt["reference_source_hashes"]):
            raise ValueError("Reference capsule members differ")
        for name, digest in receipt["reference_source_hashes"].items():
            if hashlib.sha256(archive.read(name)).hexdigest() != digest:
                raise ValueError(f"Capsule source mismatch: {name}")
    frozen = json.loads((path / "frozen-panel.json").read_text())
    definitions = {case["id"]: case for case in frozen["resolved_cases"]}
    source_hash = receipt["reference_source_hashes"][
        "configs/reference/bioelectric_pair_panel_v1.json"
    ]
    if frozen["source_sha256"] != source_hash:
        raise ValueError("Frozen panel identity mismatch")
    limits = receipt["balance_targets"]
    worst = dict.fromkeys(limits, 0.0)
    states = segments = files = continuations = 0
    for name in receipt["cases"]:
        case = definitions[name]
        stored = json.loads((path / name / "case.json").read_text())
        if stored != case:
            raise ValueError("Resolved case differs from frozen panel")
        for method in ("radau", "bdf", "refined"):
            prior = None
            with np.load(path / name / f"{method}-accepted.npz", allow_pickle=False) as data:
                count = len(data.files) // 2
                if set(data.files) != {
                    f"segment_{i}_{suffix}"
                    for i in range(count)
                    for suffix in ("times_s", "increment_state")
                }:
                    raise ValueError("Unexpected native trajectory layout")
                for i in range(count):
                    time, value = data[f"segment_{i}_times_s"], data[f"segment_{i}_increment_state"]
                    start = case["controls"][i]["time"]
                    end = (
                        case["controls"][i + 1]["time"]
                        if i + 1 < len(case["controls"])
                        else case["horizon"]
                    )
                    if (
                        time.shape != (len(value),)
                        or not np.isfinite(time).all()
                        or np.any(np.diff(time) <= 0)
                    ):
                        raise ValueError("Invalid native clock")
                    if time[0] != start or time[-1] != end:
                        raise ValueError("Native event/horizon endpoint mismatch")
                    if prior is not None:
                        np.testing.assert_array_equal(prior, value[0])
                        continuations += 1
                    prior = value[-1]
                    error = native_balances(case, value)
                    for key, magnitude in error.items():
                        if magnitude > limits[key]:
                            raise ValueError(f"Native accepted accounting: {name}/{method}/{key}")
                        worst[key] = max(worst[key], magnitude)
                    states += len(value)
                    segments += 1
            files += 1
    return {
        "status": "pass",
        "path": str(path.resolve()),
        "receipt_sha256": sha(path / "verification.json"),
        "payload_hashes": len(receipt["files_sha256"]),
        "capsule_source_hashes": len(receipt["reference_source_hashes"]),
        "native_trajectory_files": files,
        "native_segments": segments,
        "native_accepted_states_including_event_duplicates": states,
        "exact_event_continuations": continuations,
        "native_accepted_maximum_balance_residual": worst,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runs", type=Path, nargs="+")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.output is not None and args.output.exists():
        parser.error("Audit output must be a new file")
    report = {
        "status": "pass",
        "audited_utc": datetime.now(timezone.utc).isoformat(),
        "auditor_sha256": sha(Path(__file__)),
        "runs": [audit(path) for path in args.runs],
        "scope": (
            "payload/capsule integrity and native accepted-state accounting; not a new simulation"
        ),
    }
    encoded = json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if args.output is not None:
        with args.output.open("x") as handle:
            handle.write(encoded)
    print(encoded, end="")


if __name__ == "__main__":
    main()
