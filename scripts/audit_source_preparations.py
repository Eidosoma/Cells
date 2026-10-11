"""Read-only NUM-005b receipt/state audit, with no simulator or reference RHS.

Reconstructs state from typed ledgers and checks every dense polynomial, exact
chunk carries, fixed inputs, preparation anchors and archived source identities.
"""

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

import numpy as np
from numpy.polynomial import polynomial as poly

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def bounds(c):
    result = []
    for column in c.T:
        roots = poly.polyroots(poly.polyder(column))
        interior = [float(z.real) for z in roots if abs(z.imag) <= 1e-12 and 0 < z.real < 1]
        values = poly.polyval(np.array([0.0, 1.0, *interior]), column)
        result.append([float(values.min()), float(values.max())])
    return np.array(result).T


def check_coefficients(c, case, panel):
    # This gate accepts only its registered one-cell, zero-edge preparation inputs.
    if c.ndim != 2 or c.shape[1] != 13 or not np.isfinite(c).all():
        raise ValueError("Invalid isolated preparation coordinates")
    anchor, context = np.array(case["primary"])[:, 0], np.array(case["context"])[:, 0]
    prediction = c[:, :6].copy()
    prediction[:, :3] -= c[:, 6:9] + c[:, 9, None] * np.array([-3.0, 2.0, 0.0])
    prediction[:, 3:] -= c[:, 10:13]
    error = float(np.max(abs(bounds(prediction))))
    if error > 2e-9:
        raise ValueError("Independent typed accounting audit failed")
    primary = c[:, :6].copy()
    primary[0] += anchor
    charge = primary[:, 0] + primary[:, 1] - primary[:, 2]
    charge[0] -= context[0]
    p = panel["parameters"]
    voltage = charge * p["F"] * p["cell_r"] / (3 * p["cm"])
    low, high = bounds(np.c_[primary, voltage])
    if np.any(low < [1e-6] * 3 + [0] * 3 + [-0.2]) or np.any(high > [1000] * 6 + [0.2]):
        raise ValueError("Independent whole-curve domain audit failed")
    if max(abs(low[-1]), abs(high[-1])) * p["F"] / (p["R"] * p["T"]) > 50:
        raise ValueError("Independent electrical exponent audit failed")
    return error


def audit_trajectory(folder, expected_case, protocol, panel):
    receipt = read(folder / "trajectory.json")
    case = read(folder / "case.json")
    if case != expected_case or receipt["status"] != "complete_not_yet_cross_qualified":
        raise ValueError("Preparation trajectory identity differs")
    method, refinement = {"radau": ("Radau", 1), "bdf": ("BDF", 1), "refined": ("Radau", 0.1)}[
        folder.name
    ]
    if (
        receipt["method"] != method
        or receipt["refinement"] != refinement
        or receipt["rtol"] != protocol["numerics"]["rtol"] * refinement
        or receipt["atol"] != protocol["numerics"]["atol"] * refinement
        or receipt["max_step"] != protocol["numerics"]["reference_max_step"]
        or receipt["seconds"] > protocol["resources"]["worker_timeout_seconds"]
        or receipt["rhs_calls_including_solver_jacobian"]
        > protocol["resources"]["rhs_calls_per_reference_trajectory"]
    ):
        raise ValueError("Preparation numerical settings/resources differ")
    if (
        sha(folder / "case.json") != receipt["case_sha256"]
        or sha(folder / "chunks.jsonl") != receipt["index_sha256"]
    ):
        raise ValueError("Preparation trajectory index differs")
    previous, clock, chunks, steps, error = np.zeros(13), 0.0, 0, 0, 0.0
    with (folder / "chunks.jsonl").open() as index:
        for line in index:
            entry = json.loads(line)
            if entry["path"] != f"chunk-{chunks:06d}.npz":
                raise ValueError("Unexpected preparation chunk inventory")
            path = folder / entry["path"]
            if sha(path) != entry["sha256"]:
                raise ValueError("Preparation chunk hash differs")
            with np.load(path, allow_pickle=False) as data:
                t, v, c, degrees = (
                    data[key] for key in ("times", "increments", "coefficients", "degrees")
                )
                width = entry["steps"]
                if (
                    not 1 <= width <= 256
                    or t.shape != (width + 1,)
                    or v.shape != (width + 1, 13)
                    or c.shape != (width, 6, 13)
                    or degrees.shape != (width,)
                    or not all(np.isfinite(a).all() for a in (t, v, c))
                    or t[0] != clock
                    or t[0] != entry["start"]
                    or t[-1] != entry["end"]
                    or np.any(np.diff(t) <= 0)
                    or np.any(np.diff(t) > receipt["max_step"] + 1e-12)
                ):
                    raise ValueError("Invalid preparation chunk coordinates/clock")
                np.testing.assert_array_equal(v[0], previous)
                np.testing.assert_array_equal(data["anchor"], case["primary"])
                np.testing.assert_array_equal(data["context"], case["context"])
                for i, degree in enumerate(degrees):
                    if not 1 <= degree <= 5 or np.any(c[i, degree + 1 :] != 0):
                        raise ValueError("Invalid dense polynomial degree/padding")
                    left, right = c[i, 0], c[i].sum(axis=0)
                    np.testing.assert_allclose(left, v[i], atol=2e-11, rtol=2e-12)
                    np.testing.assert_allclose(right, v[i + 1], atol=2e-11, rtol=2e-12)
                    error = max(error, check_coefficients(c[i], case, panel))
                    error = max(error, check_coefficients(v[i + 1 : i + 2], case, panel))
                previous, clock = v[-1].copy(), float(t[-1])
            chunks, steps = chunks + 1, steps + width
    if (
        clock != protocol["preparation"]["duration"]
        or chunks != receipt["chunks"]
        or steps != receipt["accepted_steps"]
    ):
        raise ValueError("Incomplete preparation trajectory")
    if receipt["dense_adapter_maximum_score"] > 1 or any(
        c["maximum_score"] > 1 for c in receipt["jacobian_checks"]
    ):
        raise ValueError("Preparation instrumentation was not checked")
    return {"steps": steps, "chunks": chunks, "maximum_accounting_residual": error}, previous


def audit_observations(directory, label, protocol, packet, summary):
    with np.load(directory / label / "observations.npz", allow_pickle=False) as data:
        expected_times = sorted(
            set(range(501)) | {t for t in protocol["observer"]["irregular_times"] if t <= 500}
        )
        np.testing.assert_array_equal(data["times"], expected_times)
        values = data["refined"].copy()
        values[:, :6] += np.array(packet["initial_primary_anchor"])[:, 0]
        tol = protocol["numerics"]["targets"]["regulatory_state_and_ledger"]
        disagreement = np.maximum.reduce(
            [
                abs(data[key][:, 3:6] - data["refined"][:, 3:6])
                for key in ("radau", "bdf", "refined")
            ]
        )
        allowance = tol["atol"] + tol["rtol"] * abs(values[:, 3:6]) + disagreement
        np.testing.assert_array_equal(data["regulatory_allowance"], allowance)
        mask = (data["times"] >= 400) & (data["times"] == np.floor(data["times"]))
        sign = 1 if label == "E" else -1
        lower_margin = sign * (values[:, 3] - values[:, 4]) - allowance[:, 0] - allowance[:, 1]
        if mask.sum() != 101 or lower_margin[mask].min() < 10:
            raise ValueError("Prepared phenotype margin failed audit")
        if float(lower_margin[mask].min()) != summary["minimum_margin_after_numerical_allowance"]:
            raise ValueError("Reported preparation margin differs")
        np.testing.assert_array_equal(
            summary["end_minus_start"], values[mask][-1, :6] - values[mask][0, :6]
        )
        np.testing.assert_array_equal(summary["peak_to_peak"], np.ptp(values[mask, :6], axis=0))
        expected = np.zeros((len(values), 17, 1))
        expected[:, [0, 1, 2, 5, 6, 7], 0] = values[:, :6]
        expected[:, [3, 4, 16], 0] = [80.0, 72.0, 0.0]
        expected[:, 8, 0] = values[:, 3]
        ratio = values[:, 3] / 40
        for order in range(7):
            expected[:, 9 + order, 0] = values[:, 4] * ratio**order / (1 + ratio) ** 6
        np.testing.assert_allclose(data["packet"], expected, atol=2e-12, rtol=2e-12)
        np.testing.assert_array_equal(packet["derived_packet"], data["packet"][-1])
        np.testing.assert_array_equal(packet["endpoint_regulatory_allowance"], allowance[-1])
    return {"observations": len(expected_times), "margin_observations": 101}


def audit(directory, *, check_live_sources=True):
    directory = Path(directory)
    receipt = read(directory / "verification.json")
    registration = read(directory / "registration.json")
    protocol = read(ROOT / "configs/reference/e02_switching_protocol_v1.json")
    panel = read(ROOT / protocol["equations"]["panel"])
    if (
        receipt["status"] != "pass"
        or len(receipt["attempts"]) != 6
        or any(a["returncode"] != 0 for a in receipt["attempts"])
    ):
        raise ValueError("Preparation campaign is not complete")
    actual = {
        str(p.relative_to(directory)): sha(p)
        for p in directory.rglob("*")
        if p.is_file() and p != directory / "verification.json"
    }
    if actual != receipt["payload_hashes"]:
        raise ValueError("Preparation campaign payload inventory/hash differs")
    if (
        sha(ROOT / "configs/reference/e02_switching_protocol_v1.json")
        != registration["protocol_sha256"]
    ):
        raise ValueError("Preparation protocol changed")
    with zipfile.ZipFile(directory / "reference_sources.zip") as capsule:
        if set(capsule.namelist()) != set(registration["source_hashes"]):
            raise ValueError("Reference source capsule inventory differs")
        for name, digest in registration["source_hashes"].items():
            if hashlib.sha256(capsule.read(name)).hexdigest() != digest:
                raise ValueError("Archived reference source differs")
            if check_live_sources and sha(ROOT / name) != digest:
                raise ValueError("Live reference source differs")
    report, endpoints = {}, {}
    for label in ("E", "M"):
        for variant in ("radau", "bdf", "refined"):
            case = registration["preparation_cases"][label]
            if (
                case["cell_ids"] != [100]
                or case["edges"]
                or case["context"] != [[80.0], [72.0], [0.0]]
            ):
                raise ValueError("Preparation topology/context differs")
            expected = (
                protocol["preparation"]["initial_ions"]
                + protocol["preparation"]["initial_regulation"][label]
            )
            np.testing.assert_array_equal(np.array(case["primary"])[:, 0], expected)
            report[f"{label}/{variant}"], endpoints[f"{label}/{variant}"] = audit_trajectory(
                directory / label / variant, case, protocol, panel
            )
    qualified = read(directory / "qualification.json")
    if qualified["status"] != "pass" or qualified["criteria"]["status"] != "pass":
        raise ValueError("Preparation criteria not qualified")
    for metrics in qualified["comparisons"].values():
        if (
            metrics["status"] != "pass"
            or max(v for pair in metrics["scores"].values() for v in pair.values()) > 0.1
        ):
            raise ValueError("Independent references do not agree")
    packets = read(directory / "prepared-packets.json")
    if sha(directory / "prepared-packets.json") != receipt["prepared_packets_sha256"] or packets[
        "qualification_sha256"
    ] != sha(directory / "qualification.json"):
        raise ValueError("Prepared packet parent/hash mismatch")
    if set(packets["packets"]) != {"E", "M"}:
        raise ValueError("Missing preparation anchor")
    for label, packet in packets["packets"].items():
        v = endpoints[f"{label}/refined"]
        np.testing.assert_array_equal(packet["complete_increment_state"], v)
        v = v.copy()
        v[:6] += np.array(registration["preparation_cases"][label]["primary"])[:, 0]
        np.testing.assert_array_equal(packet["complete_absolute_state"], v)
        np.testing.assert_array_equal(np.array(packet["prepared_primary"])[:, 0], v[:6])
        np.testing.assert_array_equal(packet["context"], [[80.0], [72.0], [0.0]])
        if packet["phase_start"] != 0 or packet["phase_end"] != 500:
            raise ValueError("Prepared packet clock differs")
        audit_observations(
            directory, label, protocol, packet, qualified["criteria"]["preparations"][label]
        )
    separation = abs(
        np.array(packets["packets"]["E"]["prepared_primary"])[3:, 0]
        - np.array(packets["packets"]["M"]["prepared_primary"])[3:, 0]
    )
    lower_separation = (
        separation
        - np.array(packets["packets"]["E"]["endpoint_regulatory_allowance"])
        - np.array(packets["packets"]["M"]["endpoint_regulatory_allowance"])
    )
    if np.any(lower_separation < 1):
        raise ValueError("Prepared anchor separation failed audit")
    np.testing.assert_array_equal(
        qualified["criteria"]["anchor_separation_after_allowance"], lower_separation
    )
    baseline = read(ROOT / protocol["provenance"]["production_audit"])
    current = {
        str(p.relative_to(ROOT / "src/cells")): sha(p) for p in (ROOT / "src/cells").rglob("*.py")
    }
    if current != baseline["source_hashes"]:
        raise ValueError("Production source identity changed")
    return {
        "status": "pass",
        "trajectories": report,
        "payload_hashes": len(actual),
        "source_capsule_files": len(registration["source_hashes"]),
        "production_files_unchanged": len(current),
        "verification_sha256": sha(directory / "verification.json"),
        "prepared_packets_sha256": receipt["prepared_packets_sha256"],
        "scope": "preparation_artifact_accounting_domain_and_identity_not_switching",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit(args.directory)
    if args.output:
        with args.output.open("x") as handle:
            json.dump(result, handle, indent=2, sort_keys=True, allow_nan=False)
            handle.write("\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
