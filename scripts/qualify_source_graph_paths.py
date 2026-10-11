"""NUM-005c1: frozen E02 long implicit references, not RK4 or production.

One sequential CPU session, exclusive output, no automatic retries or budget
extensions. Complete reference trios are cross-compared before the next case.
"""

import argparse
import itertools
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path
from time import perf_counter

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import check_e02_protocol as frozen  # noqa: E402
from scripts import qualify_source_preparations as prep  # noqa: E402
from tests import reference_graph_paths as paths  # noqa: E402
from tests import reference_source_graph as graph  # noqa: E402
from tests import reference_source_graph_numerics as ref  # noqa: E402

PARENT = ROOT / "runs/num-005b-2026-09-08/preparation-01"
PARENT_HASHES = {
    "prepared-packets.json": "a7eee3207205b799717523c14c0d4436d8935d4766f3b976474856ab90458e6b",
    "qualification.json": "f4fa3adc83ae550c21354c9de6da1e556c07076cc65921c54b805159a780b641",
    "verification.json": "cf2570b6a8720bdb864113a2075d748d883a78a7a69783acab91d060c2360d63",
}
PARENT_AUDIT_SHA = "799afa9652c99bc73dff72218971d4968519b521432c37f5846b2683ac0138df"
METHODS = prep.METHODS
SOURCES = prep.SOURCES + [
    "tests/reference_graph_paths.py",
    "scripts/qualify_source_graph_paths.py",
    "scripts/audit_source_graph_paths.py",
    "tests/unit/test_source_graph_paths.py",
    "docs/SOURCE_GRAPH_PATHS_REFERENCE.md",
]
THREADS = dict.fromkeys(
    ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"), "1"
)


def prepared(parent=PARENT, *, audit_payloads=False):
    parent = Path(parent)
    data = {
        name: frozen.pinned_json(parent / name, digest) for name, digest in PARENT_HASHES.items()
    }
    packet, verification = data["prepared-packets.json"], data["verification.json"]
    audit = frozen.pinned_json(ROOT / "reports/num-005b-audit.json", PARENT_AUDIT_SHA)
    if (
        packet["status"] != "independent_reference_preparations_qualified"
        or packet["protocol_sha256"] != frozen.PROTOCOL_SHA256
        or packet["qualification_sha256"] != PARENT_HASHES["qualification.json"]
        or verification["status"] != "pass"
        or data["qualification.json"]["status"] != "pass"
        or audit["status"] != "pass"
        or audit["verification_sha256"] != PARENT_HASHES["verification.json"]
    ):
        raise ValueError("Preparation parent gate is not qualified")
    if audit_payloads:
        for name, digest in verification["payload_hashes"].items():
            if not (parent / name).resolve().is_relative_to(parent.resolve()):
                raise ValueError("Invalid parent payload path")
            if ref.sha(parent / name) != digest:
                raise ValueError(f"Prepared parent payload changed: {name}")
        prep.check_registration(parent)
    return packet


def cases(packet=None):
    """Exact prepared primary/context import; all new assay ledgers start at zero."""
    packet = prepared() if packet is None else packet
    result = {}
    for item in frozen.case_inventory():
        labels = item["prepared_labels"]
        n, e = len(labels), len(item["edges"])
        case = {
            key: item[key]
            for key in (
                "id",
                "cell_ids",
                "edge_ids",
                "edges",
                "membrane_diffusion",
                "ionic_diffusion",
                "mirna_diffusion",
            )
        }
        case.update(
            {
                "origin": "E02_NUM005b_qualified_primary_context_import_new_zero_ledgers",
                "primary": np.column_stack(
                    [
                        np.asarray(packet["packets"][label]["prepared_primary"])[:, 0]
                        for label in labels
                    ]
                ).tolist(),
                "context": np.column_stack(
                    [np.asarray(packet["packets"][label]["context"])[:, 0] for label in labels]
                ).tolist(),
                "gates": [None] * e,
                "swap_hemichannels": [False] * e,
                "controls": {
                    "leak": [[1.0] * n for _ in range(3)],
                    "pump": [1.0] * n,
                    "ion_contact": item["ion_contact"],
                    "mirna_contact": item["mirna_contact"],
                },
            }
        )
        graph.Model(case)  # Refuse malformed import before registering or launching workers.
        result[item["id"]] = case
    return result


def specification():
    protocol = frozen.load_protocol()
    packet = prepared()
    return {
        "revision": "num005c1_long_implicit_reference@1",
        "scope": "independent_long_references_and_readouts_only",
        "protocol_sha256": frozen.PROTOCOL_SHA256,
        "parent_directory": str(PARENT.relative_to(ROOT)),
        "parent_hashes": PARENT_HASHES,
        "parent_audit_sha256": PARENT_AUDIT_SHA,
        "prepared_packets": packet,
        "cases": cases(packet),
        "inventory": frozen.case_inventory(),
        "planned_attempts": [f"{case}/{method}" for case in cases(packet) for method in METHODS],
        "methods": {key: list(value) for key, value in METHODS.items()},
        "runtime": prep.runtime(),
        "thread_environment": THREADS,
        "production_source_hashes": prep.production_identity(protocol),
        "resources": protocol["resources"],
        "numerics": protocol["numerics"],
        "duration": protocol["experiment"]["end_time"],
        "observation_times": frozen.observation_times(),
        "observer": protocol["observer"],
        "storage": "lossless_numpy_savez_compressed_no_dtype_change",
        "artifact_tail_reserve_bytes": paths.TAIL_RESERVE,
        "jacobian": {
            "second_order_step": 1e-5,
            "five_point_check_step": 1e-4,
            "atol": 2e-6,
            "rtol": 2e-5,
            "check_times": [0.0, 1000.0],
        },
        "dense_adapter": {
            "theta": [0, 0.113, 0.37, 0.5, 0.613, 0.91, 1],
            "atol": 2e-11,
            "rtol": 2e-12,
            "maximum_degree": 5,
        },
        "binding_diagnostic_budget": "same_as_regulatory_coordinates_additional_check",
        "label_allowance": "coordinate_budgets_plus_reference_disagreement_candidate_not_run",
        "candidate_selection": "not_in_this_slice",
        "candidate_owned_preparation_continuations": "not_in_this_slice",
        "biological_outcome_is_numerical_gate": False,
        "no_automatic_retry_or_session_extension": True,
    }


def register(output):
    frozen.verify()
    prepared(audit_payloads=True)
    spec = specification()
    if spec["runtime"]["cpu_affinity"] != spec["resources"]["cpu_affinity"]:
        raise ValueError("Run with CPU affinity 0-3")
    if any(os.environ.get(key) != value for key, value in THREADS.items()):
        raise ValueError("Run with the registered single-thread numerical environment")
    output.mkdir(parents=True, exist_ok=False)
    sources = {name: ref.sha(ROOT / name) for name in SOURCES}
    with zipfile.ZipFile(
        output / "reference_sources.zip", "x", compression=zipfile.ZIP_DEFLATED
    ) as z:
        for name in SOURCES:
            z.write(ROOT / name, name)
    receipt = spec | {
        "source_hashes": sources,
        "source_capsule_sha256": ref.sha(output / "reference_sources.zip"),
    }
    ref.write_json(output / "registration.json", receipt)
    return receipt


def check_registration(output):
    receipt = ref.read_json(output / "registration.json")
    spec = specification()
    if set(receipt) != set(spec) | {"source_hashes", "source_capsule_sha256"}:
        raise ValueError("Registered fields differ")
    if any(receipt[key] != value for key, value in spec.items()):
        raise ValueError("Registered inputs/settings/parent/runtime changed")
    if receipt["source_hashes"] != {name: ref.sha(ROOT / name) for name in SOURCES}:
        raise ValueError("Registered reference sources changed")
    if receipt["source_capsule_sha256"] != ref.sha(output / "reference_sources.zip"):
        raise ValueError("Registered source capsule changed")
    return receipt


def worker(output, key):
    receipt = check_registration(output)
    if key not in receipt["planned_attempts"]:
        raise ValueError("Unregistered path attempt")
    if any(os.environ.get(k) != v for k, v in THREADS.items()):
        raise ValueError("Reference numerical thread settings differ")
    case, variant = key.rsplit("/", 1)
    method, refinement = METHODS[variant]
    return paths.integrate(
        graph.Model(receipt["cases"][case]),
        output / key,
        method=method,
        refinement=refinement,
        duration=receipt["duration"],
        numerics=receipt["numerics"],
        resources=receipt["resources"],
        artifact_root=output,
    )


def guard(deadline):
    if perf_counter() > deadline:
        raise ref.BudgetExceeded("Long-reference session wall budget exhausted")


def trajectories(output, case, expected_case, duration):
    result = {key: ref.Trajectory(output / case / key) for key in METHODS}
    for key, trajectory in result.items():
        if (
            trajectory.model.case != expected_case
            or trajectory.report["end"] != duration
            or (trajectory.report["method"], trajectory.report["refinement"]) != METHODS[key]
        ):
            raise ValueError("Reference case/clock/method identity differs")
    return result


def compare(output, case, registration, deadline):
    ts = trajectories(output, case, registration["cases"][case], registration["duration"])
    model = ts["refined"].model
    folder = output / case / "comparison"
    folder.mkdir(exist_ok=False)
    pairs = list(itertools.combinations(METHODS, 2))
    maxima = {f"{a}_vs_{b}": {} for a, b in pairs}
    count = chunks = 0
    residual_max = 0.0
    resources, numerics = registration["resources"], registration["numerics"]
    estimate = 8 * resources["window_steps"] * (80 * model.coordinates.size + 256 * model.n)
    if estimate > resources["estimated_array_budget_bytes"]:
        raise ref.BudgetExceeded("Comparison working array estimate exceeds budget")
    streams = [t.grid() for t in ts.values()] + [iter(registration["observation_times"])]
    for times in prep.unique_batches(streams, resources["window_steps"]):
        guard(deadline)
        states = {key: t.sample(times) for key, t in ts.items()}
        reads = {key: prep.observed(model, state) for key, state in states.items()}
        for state in states.values():
            residual_max = max(residual_max, float(np.max(abs(ref.residual(model, state)))))
            if np.any(state[:, ref.blocked_coordinates(model)] != 0):
                raise ValueError("Blocked comparison history changed")
        for a, b in pairs:
            for name, score in prep.comparison_scores(
                model, states[a], states[b], reads[a], reads[b], numerics["targets"]
            ).items():
                maxima[f"{a}_vs_{b}"][name] = max(maxima[f"{a}_vs_{b}"].get(name, 0), score)
        path = folder / f"chunk-{chunks:06d}.npz"
        paths.save_arrays(
            path, {"times": times, **states}, output, resources["artifact_budget_bytes"]
        )
        with (folder / "chunks.jsonl").open("a") as handle:
            handle.write(
                json.dumps(
                    {
                        "path": path.name,
                        "sha256": ref.sha(path),
                        "samples": len(times),
                        "start": float(times[0]),
                        "end": float(times[-1]),
                    },
                    sort_keys=True,
                )
                + "\n"
            )
        count, chunks = count + len(times), chunks + 1
    guard(deadline)
    maximum = max(score for metrics in maxima.values() for score in metrics.values())
    summary = {
        "status": "pass"
        if maximum <= numerics["reference_agreement_fraction"]
        and residual_max <= numerics["accounting_atol"]
        else "unqualified",
        "scores": maxima,
        "maximum_score": maximum,
        "samples": count,
        "chunks": chunks,
        "maximum_accounting_residual": residual_max,
        "estimated_working_array_bytes": estimate,
        "index_sha256": ref.sha(folder / "chunks.jsonl"),
    }
    ref.write_json(folder / "comparison.json", summary)
    return summary


def labels_with_allowance(primary, disagreement, targets, threshold=2.0):
    """Codes E=1, M=-1, X=0, unresolved=2. No candidate error is claimed here."""
    regulation = primary[:, 3:]
    allowance = targets["atol"] + targets["rtol"] * abs(regulation) + disagreement
    difference = regulation[:, 0] - regulation[:, 1]
    radius = allowance[:, 0] + allowance[:, 1]
    raw = np.where(difference > threshold, 1, np.where(difference < -threshold, -1, 0))
    touches = (abs(difference - threshold) <= radius) | (abs(difference + threshold) <= radius)
    return raw.astype(np.int8), np.where(touches, 2, raw).astype(np.int8), allowance


def observe(output, case, registration, deadline):
    ts = trajectories(output, case, registration["cases"][case], registration["duration"])
    model = ts["refined"].model
    item = next(i for i in registration["inventory"] if i["id"] == case)
    target = 1 if item["target_label"] == "E" else -1
    packets = registration["prepared_packets"]["packets"]
    anchors = {k: np.asarray(packets[k]["prepared_primary"])[3:, 0] for k in ("E", "M")}
    scale = abs(anchors["E"] - anchors["M"])
    goal_rows = [
        graph.eq.PACKET.index(name) for name in registration["observer"]["native_style_goal_rows"]
    ]
    opposite = np.asarray(packets[item["target_label"]]["derived_packet"])[goal_rows]
    window = registration["observer"]["terminal_window"]
    folder = output / case / "observations"
    folder.mkdir(exist_ok=False)
    small_times, small_labels = [], []  # Fixed 1007*N observer metadata, not trajectory windows.
    first = last = low = high = max_rhs = None
    terminal_count = chunks = 0
    width = registration["resources"]["window_steps"]
    estimate = 8 * width * (80 * model.coordinates.size + 256 * model.n)
    estimate += 16 * len(registration["observation_times"]) * (model.n + 1)
    if estimate > registration["resources"]["estimated_array_budget_bytes"]:
        raise ref.BudgetExceeded("Observer working array estimate exceeds budget")
    for times in prep.unique_batches([iter(registration["observation_times"])], width):
        guard(deadline)
        states = {key: t.sample(times) for key, t in ts.items()}
        reads = prep.observed(model, states["refined"])
        primary = ref.absolute(model, states["refined"])[:, : 6 * model.n].reshape(-1, 6, model.n)
        disagreement = np.maximum.reduce(
            [
                abs(
                    state[:, 3 * model.n : 6 * model.n]
                    - states["refined"][:, 3 * model.n : 6 * model.n]
                ).reshape(-1, 3, model.n)
                for state in states.values()
            ]
        )
        raw, labels, allowance = labels_with_allowance(
            primary,
            disagreement,
            registration["numerics"]["targets"]["regulatory_state_and_ledger"],
        )
        for state in states.values():
            absolute = ref.absolute(model, state)[:, : 6 * model.n].reshape(-1, 6, model.n)
            difference = absolute[:, 3] - absolute[:, 4]
            other = np.where(difference > 2, 1, np.where(difference < -2, -1, 0))
            labels[other != raw] = 2
        full_rhs = np.array(
            [model.derivative(value, increments=True) for value in states["refined"]]
        )
        distance = {
            f"distance_to_{k}": abs(primary[:, 3:] - anchor[None, :, None]) / scale[None, :, None]
            for k, anchor in anchors.items()
        }
        goal = abs(reads["packet"][:, goal_rows] - opposite[None, :, :]).max(axis=(1, 2))
        path = folder / f"chunk-{chunks:06d}.npz"
        paths.save_arrays(
            path,
            {
                "times": times,
                **states,
                **reads,
                **distance,
                "full_rhs": full_rhs,
                "raw_labels": raw,
                "labels": labels,
                "regulatory_allowance": allowance,
                "native_style_goal_distance": goal,
            },
            output,
            registration["resources"]["artifact_budget_bytes"],
        )
        with (folder / "chunks.jsonl").open("a") as handle:
            handle.write(
                json.dumps(
                    {"path": path.name, "sha256": ref.sha(path), "samples": len(times)},
                    sort_keys=True,
                )
                + "\n"
            )
        chunks += 1
        small_times.extend(times.tolist())
        small_labels.extend(labels.tolist())
        mask = (times >= window[0]) & (times <= window[1])
        if np.any(mask):
            values = states["refined"][mask]
            if first is None:
                first, low, high = values[0].copy(), values.min(axis=0), values.max(axis=0)
                max_rhs = abs(full_rhs[mask]).max(axis=0)
            last = values[-1].copy()
            low, high = np.minimum(low, values.min(axis=0)), np.maximum(high, values.max(axis=0))
            max_rhs = np.maximum(max_rhs, abs(full_rhs[mask]).max(axis=0))
            terminal_count += int(mask.sum())
    times, labels = np.asarray(small_times), np.asarray(small_labels)
    terminal = (times >= window[0]) & (times <= window[1])
    cells = []
    for column, cell_id in enumerate(model.case["cell_ids"]):
        hits = np.flatnonzero(labels[:, column] == target)
        hit = None if not len(hits) else int(hits[0])
        returns = (
            np.flatnonzero((labels[:-1, column] == target) & (labels[1:, column] != target)) + 1
        )
        changes = np.flatnonzero(labels[1:, column] != labels[:-1, column]) + 1
        cells.append(
            {
                "cell_id": cell_id,
                "initial_prepared_label": item["prepared_labels"][column],
                "endpoint_label": int(labels[-1, column]),
                "terminal_labels": sorted(set(labels[terminal, column].tolist())),
                "target_at_all_terminal_observations": bool(
                    np.all(labels[terminal, column] == target)
                ),
                "unresolved_observations": int(np.sum(labels[:, column] == 2)),
                "first_sampled_target_time": None if hit is None else float(times[hit]),
                "already_target_at_start": hit == 0,
                "preceding_non_target_bracket": None
                if hit is None or hit == 0
                else [float(times[hit - 1]), float(times[hit])],
                "bracket_left_label": None
                if hit is None or hit == 0
                else int(labels[hit - 1, column]),
                "right_censored_no_sampled_target": hit is None,
                "late_return_times": times[returns].tolist(),
                "label_change_times": times[changes].tolist(),
            }
        )
    summary = {
        "scope": "reference_diagnostics_not_production_assay_or_biological_validation",
        "label_codes": {"E": 1, "M": -1, "X": 0, "unresolved": 2},
        "samples": len(times),
        "chunks": chunks,
        "terminal_observations": terminal_count,
        "estimated_working_array_bytes": estimate,
        "cells": cells,
        "recipient_terminal_target": cells[0]["target_at_all_terminal_observations"],
        "complete_state_terminal_end_minus_start": (last - first).tolist(),
        "complete_state_terminal_peak_to_peak": (high - low).tolist(),
        "complete_state_terminal_maximum_absolute_rhs": max_rhs.tolist(),
        "native_style_goal_distance_endpoint": float(goal[-1]),
        "native_style_goal_below_2_endpoint_diagnostic_only": bool(goal[-1] < 2),
        "candidate_error_included": False,
        "equilibrium_claimed": False,
        "index_sha256": ref.sha(folder / "chunks.jsonl"),
    }
    guard(deadline)
    ref.write_json(folder / "summary.json", summary)
    return summary


def run(output):
    registration = register(output)
    begun = perf_counter()
    deadline = begun + registration["resources"]["session_wall_budget_seconds"]
    attempts, completed = [], {}
    try:
        for case in registration["cases"]:
            for variant in METHODS:
                guard(deadline)
                key = f"{case}/{variant}"
                log = output / f"{key.replace('/', '-')}.log"
                print(f"Starting registered {key}", flush=True)
                attempt = {"key": key, "status": "started"}
                attempts.append(attempt)
                with log.open("x") as handle:
                    try:
                        result = subprocess.run(
                            [
                                sys.executable,
                                str(Path(__file__).resolve()),
                                "--output",
                                str(output),
                                "--worker",
                                key,
                            ],
                            env=os.environ | THREADS | {"PYTHONDONTWRITEBYTECODE": "1"},
                            stdout=handle,
                            stderr=subprocess.STDOUT,
                            check=False,
                            timeout=min(
                                deadline - perf_counter(),
                                registration["resources"]["worker_timeout_seconds"],
                            ),
                        )
                    except subprocess.TimeoutExpired:
                        attempt.update(status="incomplete_timeout", log_sha256=ref.sha(log))
                        raise
                attempt.update(returncode=result.returncode, log_sha256=ref.sha(log))
                if result.returncode:
                    failure = output / key / "failure.json"
                    incomplete = (
                        failure.exists() and ref.read_json(failure)["status"] == "incomplete"
                    )
                    attempt["status"] = "incomplete" if incomplete else "refused"
                    error = ref.BudgetExceeded if incomplete else ValueError
                    raise error(f"Registered worker {attempt['status']}: {key}; retained log")
                attempt["status"] = "complete_not_yet_cross_qualified"
                print(f"Completed {key}", flush=True)
            agreement = compare(output, case, registration, deadline)
            if agreement["status"] != "pass":
                raise ValueError(f"Reference disagreement in {case}; no automatic amendment")
            observations = observe(output, case, registration, deadline)
            completed[case] = {"comparison": agreement, "observations": observations}
            print(f"Cross-qualified {case}: score={agreement['maximum_score']:.9g}", flush=True)
        check_registration(output)
        prepared(audit_payloads=True)
        guard(deadline)
        payloads = {
            str(p.relative_to(output)): ref.sha(p) for p in output.rglob("*") if p.is_file()
        }
        guard(deadline)
        receipt = {
            "status": "pass",
            "scope": registration["scope"],
            "attempts": attempts,
            "cases": completed,
            "seconds": perf_counter() - begun,
            "payload_hashes": payloads,
            "registration_sha256": ref.sha(output / "registration.json"),
            "production_changed": False,
            "long_time_rk4_step": "not_selected",
            "candidate_owned_continuations": "not_run",
            "NUM005c_complete": False,
        }
        ref.write_json(output / "verification.json", receipt)
        print(
            json.dumps(
                receipt | {"payload_hashes": len(payloads), "cases": list(completed)}, indent=2
            ),
            flush=True,
        )
        return receipt
    except Exception as error:
        receipt = {
            "status": "incomplete"
            if isinstance(error, (ref.BudgetExceeded, subprocess.TimeoutExpired))
            else "unqualified",
            "exception": type(error).__name__,
            "message": str(error),
            "attempts": attempts,
            "cross_qualified_cases": list(completed),
            "not_started": [
                key
                for key in registration["planned_attempts"]
                if key not in {attempt["key"] for attempt in attempts}
            ],
            "seconds": perf_counter() - begun,
            "no_automatic_retry": True,
            "registration_sha256": ref.sha(output / "registration.json"),
            "payload_hashes": {
                str(p.relative_to(output)): ref.sha(p) for p in output.rglob("*") if p.is_file()
            },
        }
        ref.write_json(output / "failure.json", receipt)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--worker", help=argparse.SUPPRESS)
    args = parser.parse_args()
    output = args.output.resolve()
    if args.worker:
        worker(output, args.worker)
    else:
        run(output)


if __name__ == "__main__":
    main()
