"""Read-only long-reference artifact audit; no simulation or reference RHS.

Independently reconstruct graph state from typed ledgers and inspect all dense
polynomial extrema. Incomplete campaigns get integrity audits, never promotion.
"""

import argparse
import hashlib
import heapq
import itertools
import json
import sys
import zipfile
from pathlib import Path
from time import perf_counter

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.audit_source_preparations import bounds  # noqa: E402


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_coefficients(c, case, panel):
    n, e = len(case["cell_ids"]), len(case["edges"])
    if c.ndim != 2 or c.shape[1] != 13 * n + 4 * e or not np.isfinite(c).all():
        raise ValueError("Invalid graph reference coordinates")
    primary = c[:, : 6 * n].reshape(-1, 6, n).copy()
    leak = c[:, 6 * n : 9 * n].reshape(-1, 3, n)
    pump = c[:, 9 * n : 10 * n]
    ionic = c[:, 10 * n : 10 * n + 3 * e].reshape(len(c), 3, e)
    local = c[:, 10 * n + 3 * e : 13 * n + 3 * e].reshape(-1, 3, n)
    mirna = c[:, 13 * n + 3 * e :]
    error = primary.copy()
    error[:, :3] -= leak + np.array([-3.0, 2.0, 0.0])[None, :, None] * pump[:, None, :]
    error[:, 3:] -= local
    positions = {cell: i for i, cell in enumerate(case["cell_ids"])}
    for edge, (a, b) in enumerate(case["edges"]):
        left, right = positions[a], positions[b]
        error[:, :3, left] += ionic[:, :, edge]
        error[:, :3, right] -= ionic[:, :, edge]
        error[:, 3, left] += mirna[:, edge]
        error[:, 3, right] -= mirna[:, edge]
    maximum = float(np.max(abs(bounds(error.reshape(len(c), 6 * n)))))
    if maximum > 2e-9:
        raise ValueError("Independent graph typed accounting audit failed")
    controls = case["controls"]
    blocked_leak = np.asarray(case["membrane_diffusion"]) * controls["leak"] == 0
    blocked_pump = (np.asarray(controls["pump"]) == 0) | np.all(
        np.asarray(case["membrane_diffusion"]) == 0, axis=0
    )
    blocked_ion = np.asarray(case["ionic_diffusion"]) * controls["ion_contact"] == 0
    blocked_mirna = np.asarray(case["mirna_diffusion"]) * controls["mirna_contact"] == 0
    if any(
        np.any(values[:, mask] != 0)
        for values, mask in (
            (leak, blocked_leak),
            (pump, blocked_pump),
            (ionic, blocked_ion),
            (mirna, blocked_mirna),
        )
    ):
        raise ValueError("Independent blocked-history audit failed")
    primary[0] += np.asarray(case["primary"])
    charge = primary[:, 0] + primary[:, 1] - primary[:, 2]
    charge[0] -= np.asarray(case["context"])[0]
    p = panel["parameters"]
    voltage = charge * p["F"] * p["cell_r"] / (3 * p["cm"])
    delta = (
        np.array([voltage[:, positions[a]] - voltage[:, positions[b]] for a, b in case["edges"]])
        .reshape(e, len(c))
        .T
    )
    low, high = bounds(np.c_[primary.reshape(len(c), 6 * n), voltage, delta])
    if np.any(low < [1e-6] * (3 * n) + [0] * (3 * n) + [-0.2] * (n + e)) or np.any(
        high > [1000] * (6 * n) + [0.2] * (n + e)
    ):
        raise ValueError("Independent graph whole-curve domain audit failed")
    volts = np.maximum(abs(low[6 * n :]), abs(high[6 * n :]))
    if (
        max(
            volts[:n].max() * p["F"] / (p["R"] * p["T"]),
            volts[n:].max(initial=0) * p["q"] / (p["kb"] * p["T"]),
        )
        > 50
    ):
        raise ValueError("Independent graph electrical exponent audit failed")
    return maximum


def audit_trajectory(folder, case, registration, panel, deadline):
    report = read(folder / "trajectory.json")
    method, refinement = registration["methods"][folder.name]
    numerics, resources = registration["numerics"], registration["resources"]
    if (
        read(folder / "case.json") != case
        or sha(folder / "case.json") != report["case_sha256"]
        or sha(folder / "chunks.jsonl") != report["index_sha256"]
        or report["status"] != "complete_not_yet_cross_qualified"
        or report["method"] != method
        or report["refinement"] != refinement
        or report["rtol"] != numerics["rtol"] * refinement
        or report["atol"] != numerics["atol"] * refinement
        or report["max_step"] != numerics["reference_max_step"]
        or report["seconds"] > resources["worker_timeout_seconds"]
        or report["accepted_steps"] > resources["max_steps_per_trajectory"]
        or report["rhs_calls_including_solver_jacobian"]
        > resources["rhs_calls_per_reference_trajectory"]
        or report["estimated_working_array_bytes"] > resources["estimated_array_budget_bytes"]
        or report["dense_adapter_maximum_score"] > 1
        or len(report["jacobian_checks"]) != 2
        or any(
            c["maximum_score"] > 1 or not c["passive_columns_exact"]
            for c in report["jacobian_checks"]
        )
    ):
        raise ValueError("Long reference identity/settings/resources differ")
    n, e = len(case["cell_ids"]), len(case["edges"])
    size = 13 * n + 4 * e
    previous, clock, chunks, steps, maximum = np.zeros(size), 0.0, 0, 0, 0.0
    with (folder / "chunks.jsonl").open() as handle:
        for line in handle:
            if perf_counter() > deadline:
                raise TimeoutError("Read-only artifact audit session exhausted")
            entry = json.loads(line)
            path = folder / entry["path"]
            if (
                path.name != f"chunk-{chunks:06d}.npz"
                or path.parent != folder
                or sha(path) != entry["sha256"]
            ):
                raise ValueError("Long reference chunk inventory/hash differs")
            with np.load(path, allow_pickle=False) as data:
                t, v, c, degrees = [
                    data[k] for k in ("times", "increments", "coefficients", "degrees")
                ]
                width = entry["steps"]
                if (
                    not 1 <= width <= resources["window_steps"]
                    or t.shape != (width + 1,)
                    or v.shape != (width + 1, size)
                    or c.shape != (width, 6, size)
                    or degrees.shape != (width,)
                    or degrees.dtype.kind not in "iu"
                    or not all(np.isfinite(a).all() for a in (t, v, c))
                    or t[0] != clock
                    or t[0] != entry["start"]
                    or t[-1] != entry["end"]
                    or np.any(np.diff(t) <= 0)
                    or np.any(np.diff(t) > report["max_step"] + 1e-12)
                ):
                    raise ValueError("Long reference chunk shape/clock differs")
                np.testing.assert_array_equal(v[0], previous)
                np.testing.assert_array_equal(data["anchor"], case["primary"])
                np.testing.assert_array_equal(data["context"], case["context"])
                for i, degree in enumerate(degrees):
                    if not 1 <= degree <= 5 or np.any(c[i, degree + 1 :] != 0):
                        raise ValueError("Dense degree/padding differs")
                    np.testing.assert_allclose(c[i, 0], v[i], atol=2e-11, rtol=2e-12)
                    np.testing.assert_allclose(c[i].sum(axis=0), v[i + 1], atol=2e-11, rtol=2e-12)
                    maximum = max(
                        maximum,
                        check_coefficients(c[i], case, panel),
                        check_coefficients(v[i + 1 : i + 2], case, panel),
                    )
                previous, clock = v[-1].copy(), float(t[-1])
            chunks, steps = chunks + 1, steps + width
    if (
        clock != registration["duration"]
        or report["end"] != clock
        or report["start"] != 0
        or chunks != report["chunks"]
        or steps != report["accepted_steps"]
    ):
        raise ValueError("Incomplete long reference inventory")
    return {"steps": steps, "chunks": chunks, "maximum_accounting_residual": maximum}


def audit_observations(folder, case, registration, deadline=np.inf):
    summary = read(folder / "observations/summary.json")
    index_path = folder / "observations/chunks.jsonl"
    if sha(index_path) != summary["index_sha256"]:
        raise ValueError("Observer index hash differs")
    n, e = len(case["cell_ids"]), len(case["edges"])
    size = 13 * n + 4 * e
    expected_times = registration["observation_times"]
    tol = registration["numerics"]["targets"]["regulatory_state_and_ledger"]
    packets = registration["prepared_packets"]["packets"]
    scale = abs(
        np.asarray(packets["E"]["prepared_primary"])[3:, 0]
        - np.asarray(packets["M"]["prepared_primary"])[3:, 0]
    )
    window = registration["observer"]["terminal_window"]
    offset = chunks = terminal_count = 0
    first = last = low = high = rhs = None
    all_labels = []  # Only the fixed-size observer label table, never all solver chunks.
    with index_path.open() as handle:
        for line in handle:
            if perf_counter() > deadline:
                raise TimeoutError("Read-only observer audit session exhausted")
            entry = json.loads(line)
            path = index_path.parent / entry["path"]
            if entry["path"] != f"chunk-{chunks:06d}.npz" or sha(path) != entry["sha256"]:
                raise ValueError("Observer chunk inventory/hash differs")
            with np.load(path, allow_pickle=False) as data:
                t, v = data["times"], data["refined"]
                width = entry["samples"]
                if not 1 <= width <= registration["resources"]["window_steps"]:
                    raise ValueError("Observer batch size differs")
                np.testing.assert_array_equal(t, expected_times[offset : offset + width])
                if v.shape != (width, size) or data["full_rhs"].shape != v.shape:
                    raise ValueError("Observer complete-state shape differs")
                if any(not np.isfinite(data[k]).all() for k in data.files):
                    raise ValueError("Nonfinite observer payload")
                primary = v[:, : 6 * n].reshape(width, 6, n) + np.asarray(case["primary"])
                others = [
                    data[k][:, : 6 * n].reshape(width, 6, n) + np.asarray(case["primary"])
                    for k in registration["methods"]
                ]
                disagreement = np.maximum.reduce(
                    [
                        abs(data[k][:, 3 * n : 6 * n] - v[:, 3 * n : 6 * n]).reshape(width, 3, n)
                        for k in registration["methods"]
                    ]
                )
                allowance = tol["atol"] + tol["rtol"] * abs(primary[:, 3:]) + disagreement
                np.testing.assert_array_equal(data["regulatory_allowance"], allowance)
                difference = primary[:, 3] - primary[:, 4]
                radius = allowance[:, 0] + allowance[:, 1]
                raw = np.where(difference > 2, 1, np.where(difference < -2, -1, 0))
                labels = np.where(
                    (abs(difference - 2) <= radius) | (abs(difference + 2) <= radius), 2, raw
                )
                for other in others:
                    margin = other[:, 3] - other[:, 4]
                    codes = np.where(margin > 2, 1, np.where(margin < -2, -1, 0))
                    labels[codes != raw] = 2
                np.testing.assert_array_equal(data["raw_labels"], raw)
                np.testing.assert_array_equal(data["labels"], labels)
                packet = np.zeros((width, 17, n))
                packet[:, [0, 1, 2, 5, 6, 7]] = primary
                packet[:, [3, 4, 16]] = np.asarray(case["context"])
                packet[:, 8] = primary[:, 3]
                ratio = primary[:, 3] / 40
                for order in range(7):
                    packet[:, 9 + order] = primary[:, 4] * ratio**order / (1 + ratio) ** 6
                np.testing.assert_allclose(data["packet"], packet, atol=2e-12, rtol=2e-12)
                np.testing.assert_array_equal(data["binding_cache"], data["packet"][:, 8:16])
                for label in ("E", "M"):
                    distance = abs(
                        primary[:, 3:] - np.asarray(packets[label]["prepared_primary"])[None, 3:, :]
                    )
                    np.testing.assert_array_equal(
                        data[f"distance_to_{label}"], distance / scale[None, :, None]
                    )
                mask = (t >= window[0]) & (t <= window[1])
                if np.any(mask):
                    values = v[mask]
                    if first is None:
                        first, low, high = values[0].copy(), values.min(axis=0), values.max(axis=0)
                        rhs = abs(data["full_rhs"][mask]).max(axis=0)
                    last = values[-1].copy()
                    low, high = (
                        np.minimum(low, values.min(axis=0)),
                        np.maximum(high, values.max(axis=0)),
                    )
                    rhs = np.maximum(rhs, abs(data["full_rhs"][mask]).max(axis=0))
                    terminal_count += int(mask.sum())
                all_labels.extend(labels.tolist())
            offset, chunks = offset + width, chunks + 1
    if (
        offset != len(expected_times)
        or summary["samples"] != offset
        or summary["chunks"] != chunks
        or summary["terminal_observations"] != terminal_count
    ):
        raise ValueError("Observer coverage differs")
    np.testing.assert_array_equal(summary["complete_state_terminal_end_minus_start"], last - first)
    np.testing.assert_array_equal(summary["complete_state_terminal_peak_to_peak"], high - low)
    np.testing.assert_array_equal(summary["complete_state_terminal_maximum_absolute_rhs"], rhs)
    labels, t = np.asarray(all_labels), np.asarray(expected_times)
    terminal = (t >= window[0]) & (t <= window[1])
    target = -1 if case["id"].startswith("E_to_M/") else 1
    for i, cell in enumerate(summary["cells"]):
        if (
            cell["cell_id"] != case["cell_ids"][i]
            or cell["endpoint_label"] != int(labels[-1, i])
            or cell["terminal_labels"] != sorted(set(labels[terminal, i].tolist()))
            or cell["target_at_all_terminal_observations"]
            != bool(np.all(labels[terminal, i] == target))
        ):
            raise ValueError("Observer terminal summary differs")
    return {"observations": offset, "terminal_observations": terminal_count}


def audit_comparison_grid(folder, registration, deadline=np.inf):
    def grid(variant):
        yield 0.0
        with (folder / variant / "chunks.jsonl").open() as handle:
            for line in handle:
                with np.load(
                    folder / variant / json.loads(line)["path"], allow_pickle=False
                ) as data:
                    times = data["times"]
                for a, b in zip(times[:-1], times[1:], strict=True):
                    yield float(a + (b - a) / 2)
                    yield float(b)

    streams = [grid(key) for key in registration["methods"]] + [
        iter(registration["observation_times"])
    ]
    expected = (key for key, _ in itertools.groupby(heapq.merge(*streams)))
    comparison = read(folder / "comparison/comparison.json")
    index = folder / "comparison/chunks.jsonl"
    if sha(index) != comparison["index_sha256"]:
        raise ValueError("Comparison index differs")
    samples = chunks = 0
    with index.open() as handle:
        for line in handle:
            if perf_counter() > deadline:
                raise TimeoutError("Read-only comparison audit session exhausted")
            entry = json.loads(line)
            path = index.parent / entry["path"]
            if entry["path"] != f"chunk-{chunks:06d}.npz" or sha(path) != entry["sha256"]:
                raise ValueError("Comparison chunk inventory/hash differs")
            with np.load(path, allow_pickle=False) as data:
                count = entry["samples"]
                if not 1 <= count <= registration["resources"]["window_steps"]:
                    raise ValueError("Comparison batch size differs")
                np.testing.assert_array_equal(
                    data["times"], list(itertools.islice(expected, count))
                )
            samples, chunks = samples + count, chunks + 1
    if (
        next(expected, None) is not None
        or samples != comparison["samples"]
        or chunks != comparison["chunks"]
    ):
        raise ValueError("Incomplete union comparison grid")
    return {"samples": samples, "chunks": chunks}


def audit(directory, *, check_live_sources=True):
    directory = Path(directory).resolve()
    receipt_path = directory / "verification.json"
    complete = receipt_path.exists()
    if not complete:
        receipt_path = directory / "failure.json"
    receipt, registration = read(receipt_path), read(directory / "registration.json")
    if sha(directory / "registration.json") != receipt["registration_sha256"]:
        raise ValueError("Campaign registration hash differs")
    names = {str(p.relative_to(directory)) for p in directory.rglob("*") if p.is_file()}
    if names != set(receipt["payload_hashes"]) | {receipt_path.name}:
        raise ValueError("Campaign payload inventory differs")
    for name, digest in receipt["payload_hashes"].items():
        path = directory / name
        if not path.resolve().is_relative_to(directory) or sha(path) != digest:
            raise ValueError(f"Campaign payload differs: {name}")
    if sha(directory / "reference_sources.zip") != registration["source_capsule_sha256"]:
        raise ValueError("Campaign source capsule differs")
    with zipfile.ZipFile(directory / "reference_sources.zip") as z:
        if sorted(z.namelist()) != sorted(registration["source_hashes"]):
            raise ValueError("Campaign source inventory differs")
        for name, digest in registration["source_hashes"].items():
            if hashlib.sha256(z.read(name)).hexdigest() != digest:
                raise ValueError(f"Archived reference source differs: {name}")
            if check_live_sources and sha(ROOT / name) != digest:
                raise ValueError(f"Live reference source differs: {name}")
        panel = json.loads(z.read("configs/reference/source_emt_pair_panel_v1.json"))
        protocol = json.loads(z.read("configs/reference/e02_switching_protocol_v1.json"))
        if (
            hashlib.sha256(z.read("configs/reference/e02_switching_protocol_v1.json")).hexdigest()
            != registration["protocol_sha256"]
        ):
            raise ValueError("Archived protocol differs")
    if (
        registration["resources"] != protocol["resources"]
        or registration["numerics"] != protocol["numerics"]
    ):
        raise ValueError("Frozen budgets/settings differ")
    if check_live_sources:
        current = {
            str(p.relative_to(ROOT / "src/cells")): sha(p)
            for p in (ROOT / "src/cells").rglob("*.py")
        }
        if current != registration["production_source_hashes"]:
            raise ValueError("Production identity differs")
    total_bytes = sum(p.stat().st_size for p in directory.rglob("*") if p.is_file())
    if total_bytes > registration["resources"]["artifact_budget_bytes"]:
        raise ValueError("Artifact budget exceeded")
    attempted = [a["key"] for a in receipt["attempts"]]
    if attempted != registration["planned_attempts"][: len(attempted)]:
        raise ValueError("Attempt order/inventory differs")
    trajectories, observations_audit, grids = {}, {}, {}
    if complete:
        if (
            receipt["status"] != "pass"
            or attempted != registration["planned_attempts"]
            or set(receipt["cases"]) != set(registration["cases"])
            or receipt["seconds"] > registration["resources"]["session_wall_budget_seconds"]
        ):
            raise ValueError("Incomplete campaign cannot pass")
        deadline = perf_counter() + registration["resources"]["session_wall_budget_seconds"]
        for key in attempted:
            case, _ = key.rsplit("/", 1)
            trajectories[key] = audit_trajectory(
                directory / key, registration["cases"][case], registration, panel, deadline
            )
        for case, result in receipt["cases"].items():
            comparison = read(directory / case / "comparison/comparison.json")
            observations = read(directory / case / "observations/summary.json")
            if (
                result != {"comparison": comparison, "observations": observations}
                or comparison["status"] != "pass"
                or comparison["maximum_score"]
                > registration["numerics"]["reference_agreement_fraction"]
                or comparison["maximum_accounting_residual"]
                > registration["numerics"]["accounting_atol"]
                or observations["samples"] != len(registration["observation_times"])
            ):
                raise ValueError("Long-path comparison/observation receipt differs")
            observations_audit[case] = audit_observations(
                directory / case, registration["cases"][case], registration, deadline
            )
            grids[case] = audit_comparison_grid(directory / case, registration, deadline)
        if perf_counter() > deadline:
            raise TimeoutError("Read-only artifact audit session exhausted")
    elif receipt["status"] not in ("unqualified", "incomplete"):
        raise ValueError("Failure receipt cannot claim pass")
    return {
        "status": "pass",
        "campaign_status": receipt["status"],
        "scope": "complete_path_identity_domain_accounting_audit"
        if complete
        else "failed_or_incomplete_campaign_integrity_only_no_numerical_promotion",
        "receipt_sha256": sha(receipt_path),
        "payloads": len(receipt["payload_hashes"]),
        "source_capsule_files": len(registration["source_hashes"]),
        "artifact_bytes": total_bytes,
        "trajectories": trajectories,
        "observations": observations_audit,
        "comparison_grids": grids,
        "production_changed": False if check_live_sources else None,
        "comparison_flux_scores": "online_recorded_not_independently_recomputed_by_this_audit",
        "candidate_selected": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--archive-only", action="store_true")
    args = parser.parse_args()
    print(json.dumps(audit(args.directory, check_live_sources=not args.archive_only), indent=2))


if __name__ == "__main__":
    main()
