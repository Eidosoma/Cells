"""Read-only NUM-004 payload/accounting audit; imports no simulator or reference RHS."""

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def initial(panel, case):
    if case["initial"] != "prepared":
        entry = panel["constructed_initials"][case["initial"]]
        return np.array(entry["primary"]), np.array(entry["context"])
    packets = [entry["raw_packet"] | {"ST": 0.0} for entry in panel["preparation"]["cells"]]
    return tuple(
        np.array([[packet[row] for packet in packets] for row in panel[key]])
        for key in ("primary_rows", "context_rows")
    )


def check_state(values, panel, case, *, increments=False):
    """Independently reconstruct each coordinate from its typed exchange history."""
    if values.ndim != 2 or values.shape[1] != 30 or not len(values):
        raise ValueError("Invalid complete state shape")
    if not np.isfinite(values).all():
        raise ValueError("Nonfinite complete state")
    anchor, context = initial(panel, case)
    delta = values[:, :12].reshape(-1, 6, 2).copy()
    absolute = delta + anchor if increments else delta.copy()
    if not increments:
        delta -= anchor
    predicted = np.zeros_like(delta)
    sender, receiver = case.get("edge", [0, 1])
    for cell in range(2):
        pump = values[:, 18 + cell]
        for species, stoichiometry in enumerate((-3.0, 2.0, 0.0)):
            predicted[:, species, cell] = values[:, 12 + 2 * species + cell] + stoichiometry * pump
        for species in range(3):
            predicted[:, species + 3, cell] = values[:, 23 + 2 * species + cell]
    for species in range(3):
        transfer = values[:, 20 + species]
        predicted[:, species, sender] -= transfer
        predicted[:, species, receiver] += transfer
    predicted[:, 3, sender] -= values[:, 29]
    predicted[:, 3, receiver] += values[:, 29]
    errors = np.max(abs(delta - predicted), axis=(0, 2))
    if np.max(errors) > 2e-9:
        raise ValueError("Typed exchange accounting failed")
    if (
        np.any(absolute[:, :3] < 1e-6)
        or np.any(absolute[:, :3] > 1000)
        or np.any(absolute[:, 3:] < 0)
        or np.any(absolute[:, 3:] > 1000)
    ):
        raise ValueError("Primary domain failed")
    p = panel["parameters"]
    voltage = (
        p["F"]
        * p["cell_r"]
        / (3 * p["cm"])
        * (absolute[:, 0] + absolute[:, 1] - absolute[:, 2] - context[0])
    )
    vmax = float(max(np.max(abs(voltage)), np.max(abs(voltage[:, 0] - voltage[:, 1]))))
    if vmax > 0.2:
        raise ValueError("Electrical domain failed")
    return {
        "states": len(values),
        "max_accounting_error": float(np.max(errors)),
        "max_voltage": vmax,
    }


def audit_directory(directory, panel):
    receipt = json.loads((directory / "verification.json").read_text())
    if receipt["status"] != "pass":
        raise ValueError("Independent qualification/study did not pass")
    actual = {
        str(p.relative_to(directory)): sha(p)
        for p in directory.rglob("*")
        if p.is_file() and p != directory / "verification.json"
    }
    if actual != receipt["payload_hashes"]:
        raise ValueError("Payload inventory/hash mismatch")
    with zipfile.ZipFile(directory / "reference_sources.zip") as capsule:
        if set(capsule.namelist()) != set(receipt["source_hashes"]):
            raise ValueError("Source capsule inventory mismatch")
        for name, digest in receipt["source_hashes"].items():
            if (
                hashlib.sha256(capsule.read(name)).hexdigest() != digest
                or sha(ROOT / name) != digest
            ):
                raise ValueError("Archived/live source hash mismatch")
    counts = {
        "implicit_states": 0,
        "implicit_segments": 0,
        "exact_event_carries": 0,
        "rk_states": 0,
        "comparison_states": 0,
        "payload_hashes": len(actual),
    }
    maximum_error = 0.0
    for case in panel["cases"]:
        folder = directory / case["id"]
        if not folder.exists():
            continue
        if json.loads((folder / "case.json").read_text()) != case:
            raise ValueError("Resolved case differs from frozen panel")
        edges = [0.0] + [e["time"] for e in case.get("events", [])] + [case["end_time"]]
        for method in ("radau", "bdf", "refined"):
            with np.load(folder / f"{method}-accepted.npz", allow_pickle=False) as data:
                previous = None
                for index, (start, end) in enumerate(zip(edges[:-1], edges[1:], strict=True)):
                    times = data[f"segment_{index}_times"]
                    states = data[f"segment_{index}_increment_state"]
                    if (
                        times.shape != (len(states),)
                        or times[0] != start
                        or times[-1] != end
                        or np.any(np.diff(times) <= 0)
                    ):
                        raise ValueError("Implicit accepted clock mismatch")
                    if previous is not None:
                        np.testing.assert_array_equal(states[0], previous)
                        counts["exact_event_carries"] += 1
                    else:
                        np.testing.assert_array_equal(states[0], np.zeros(30))
                    previous = states[-1]
                    checked = check_state(states, panel, case, increments=True)
                    maximum_error = max(maximum_error, checked["max_accounting_error"])
                    counts["implicit_states"] += len(states)
                    counts["implicit_segments"] += 1
        for trajectory in sorted(folder.glob("rk4-*/trajectory.npz")):
            with np.load(trajectory, allow_pickle=False) as data:
                times = data["accepted_times"]
                if times[0] != 0 or times[-1] != case["end_time"] or np.any(np.diff(times) <= 0):
                    raise ValueError("RK accepted clock mismatch")
                if not all(event in times for event in edges):
                    raise ValueError("Missing exact event endpoint")
                anchor, _ = initial(panel, case)
                np.testing.assert_array_equal(
                    data["accepted_state"][0], np.r_[anchor.ravel(), np.zeros(18)]
                )
                for name in ("accepted_state", "observed", "radau", "bdf", "refined"):
                    checked = check_state(data[name], panel, case)
                    maximum_error = max(maximum_error, checked["max_accounting_error"])
                    counts["rk_states" if name == "accepted_state" else "comparison_states"] += len(
                        data[name]
                    )
    return counts | {
        "max_accounting_error": maximum_error,
        "receipt_sha256": sha(directory / "verification.json"),
    }


def orientation(qualified):
    arrays = {}
    dt = json.loads((qualified / "verification.json").read_text())["selected_dt"]
    for case in ("S05", "S06", "S07"):
        with np.load(
            qualified / case / f"rk4-{dt:g}" / "trajectory.npz", allow_pickle=False
        ) as data:
            arrays[case] = data["accepted_state"]
    reversed_state = arrays["S07"].copy()
    reversed_state[:, 20:23] *= -1
    reversed_state[:, 29] *= -1
    np.testing.assert_allclose(reversed_state, arrays["S05"], atol=2e-9, rtol=0)
    negative = float(np.max(abs(arrays["S06"][:, :12] - arrays["S05"][:, :12])))
    if negative <= 1e-6:
        raise ValueError("Keeping asymmetric hemichannels did not change the trajectory")
    return {
        "reoriented_complete_state_error": float(np.max(abs(reversed_state - arrays["S05"]))),
        "unswapped_primary_difference": negative,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", type=Path, required=True)
    parser.add_argument("--qualified", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output must be new")
    panel_path = ROOT / "configs/reference/source_emt_pair_panel_v1.json"
    panel = json.loads(panel_path.read_text())
    report = {
        "status": "pass",
        "study": audit_directory(args.study, panel),
        "qualification": audit_directory(args.qualified, panel),
        "orientation": orientation(args.qualified),
        "panel_sha256": sha(panel_path),
        "auditor_sha256": sha(Path(__file__)),
    }
    production = {
        str(p.relative_to(ROOT / "src/cells")): sha(p) for p in (ROOT / "src/cells").rglob("*.py")
    }
    accepted = json.loads(
        (ROOT / "runs/model-004-2026-09-08/acceptance/verification.json").read_text()
    )
    if production != accepted["source_hashes"]:
        raise ValueError("Accepted production identity changed")
    report["unchanged_production_files"] = len(production)
    with args.output.open("x") as handle:
        json.dump(report, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
