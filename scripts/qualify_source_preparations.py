"""NUM-005b: register, bound, record and independently qualify E02 preparations.

No production/native integration, candidate selection or connected trajectories.
Use a NEW output directory. Failures remain; no automatic numerical amendment.
"""

import argparse
import heapq
import importlib.metadata
import inspect
import itertools
import json
import os
import platform
import subprocess
import sys
import zipfile
from pathlib import Path
from time import perf_counter

import numpy as np
import scipy
from scipy.integrate._ivp import base, bdf, common, radau

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import check_e02_protocol as frozen  # noqa: E402
from tests import reference_source_graph as graph  # noqa: E402
from tests import reference_source_graph_numerics as ref  # noqa: E402

METHODS = {"radau": ("Radau", 1.0), "bdf": ("BDF", 1.0), "refined": ("Radau", 0.1)}
SOURCES = [
    "tests/reference_emt.py",
    "tests/reference_source_pair.py",
    "tests/reference_source_pair_numerics.py",
    "tests/reference_source_graph.py",
    "tests/reference_source_graph_numerics.py",
    "tests/source_graph_fixtures.py",
    "scripts/check_e02_protocol.py",
    "scripts/check_source_graph_reference.py",
    "scripts/qualify_source_preparations.py",
    "scripts/audit_source_preparations.py",
    "tests/unit/test_source_preparations.py",
    "configs/reference/e02_switching_protocol_v1.json",
    "configs/reference/source_emt_pair_panel_v1.json",
    "configs/reference/source_emt_pair_numerics_v1.json",
    "configs/reference/source_emt_graph_probes_v1.json",
    "tests/fixtures/source_graph_probes.json",
    "tests/fixtures/source_pair_probes.json",
    "requirements-lock.txt",
    "requirements-reference.txt",
    "pyproject.toml",
]


def preparations(protocol=None):
    protocol = frozen.load_protocol() if protocol is None else protocol
    p, equations = protocol["preparation"], protocol["equations"]
    return {
        label: {
            "id": f"prepare/{label}",
            "origin": "E02_fresh_isolated_500_unit_preparation",
            "cell_ids": [protocol["experiment"]["recipient_id"]],
            "edge_ids": [],
            "edges": [],
            "primary": [[x] for x in p["initial_ions"] + seed],
            "context": [[p["context"][k]] for k in graph.eq.CONTEXT],
            "membrane_diffusion": [[x] for x in equations["membrane_diffusion_per_cell"]],
            "ionic_diffusion": [[], [], []],
            "mirna_diffusion": [],
            "gates": [],
            "swap_hemichannels": [],
            "controls": {
                "leak": [[p["leak_control"]]] * 3,
                "pump": [p["pump_control"]],
                "ion_contact": [],
                "mirna_contact": [],
            },
        }
        for label, seed in p["initial_regulation"].items()
    }


def runtime():
    return {
        "python": platform.python_version(),
        "numpy": np.__version__,
        "scipy": scipy.__version__,
        "packages": {k: importlib.metadata.version(k) for k in ("numpy", "scipy")},
        "scipy_implementation_hashes": {
            module.__name__: ref.sha(inspect.getfile(module))
            for module in (base, common, radau, bdf)
        },
        "cpu_affinity": sorted(os.sched_getaffinity(0)),
        "precision": "float64",
        "platform": platform.platform(),
    }


def production_identity(protocol):
    provenance = protocol["provenance"]
    baseline = frozen.pinned_json(
        ROOT / provenance["production_audit"], provenance["production_audit_sha256"]
    )
    current = {
        str(p.relative_to(ROOT / "src/cells")): ref.sha(p)
        for p in (ROOT / "src/cells").rglob("*.py")
    }
    if current != baseline["source_hashes"]:
        raise ValueError("Production changed from the accepted 0.10.0 identity")
    return current


def register(output):
    protocol = frozen.load_protocol()
    frozen.verify()  # inputs/source identities; do not touch the continuing exploration
    native_gate = frozen.pinned_json(
        ROOT / "runs/num-005a-2026-09-08/acceptance-01/verification.json",
        "ec33714cdd560b8d95d6703c8021cc464bae1a36a71db831e21e6a55e19855e9",
    )
    if native_gate["status"] != "pass":
        raise ValueError("Instantaneous graph gate is not complete")
    if runtime()["cpu_affinity"] != protocol["resources"]["cpu_affinity"]:
        raise ValueError("Run with CPU affinity 0-3")
    production = production_identity(protocol)
    output.mkdir(parents=True, exist_ok=False)
    sources = {name: ref.sha(ROOT / name) for name in SOURCES}
    with zipfile.ZipFile(
        output / "reference_sources.zip", "x", compression=zipfile.ZIP_DEFLATED
    ) as z:
        for name in SOURCES:
            z.write(ROOT / name, name)
    receipt = {
        "revision": "num005b_preparation_reference@1",
        "protocol_sha256": frozen.PROTOCOL_SHA256,
        "source_hashes": sources,
        "source_capsule_sha256": ref.sha(output / "reference_sources.zip"),
        "instantaneous_gate_sha256": ref.sha(
            ROOT / "runs/num-005a-2026-09-08/acceptance-01/verification.json"
        ),
        "runtime": runtime(),
        "production_source_hashes": production,
        "preparation_cases": preparations(protocol),
        "planned_attempts": [f"{label}/{method}" for label in ("E", "M") for method in METHODS],
        "methods": {k: list(v) for k, v in METHODS.items()},
        "resources": protocol["resources"],
        "numerics": protocol["numerics"],
        "duration": protocol["preparation"]["duration"],
        "jacobian": {
            "second_order_step": 1e-5,
            "five_point_check_step": 1e-4,
            "check_atol": 2e-6,
            "check_rtol": 2e-5,
            "check_times": [0, 500],
        },
        "dense_adapter": {
            "check_theta": [0, 0.113, 0.37, 0.5, 0.613, 0.91, 1],
            "atol": 2e-11,
            "rtol": 2e-12,
            "maximum_degree": 5,
        },
        "binding_diagnostic_budget": "same_as_regulatory_coordinates_additional_check",
        "label_allowance": "full_coordinate_budgets_plus_measured_reference_disagreement",
        "candidate_selection": "not_in_this_slice",
        "connected_runs": "not_in_this_slice",
        "thread_environment": {
            key: "1"
            for key in (
                "OMP_NUM_THREADS",
                "OPENBLAS_NUM_THREADS",
                "MKL_NUM_THREADS",
                "NUMEXPR_NUM_THREADS",
            )
        },
    }
    ref.write_json(output / "registration.json", receipt)
    return receipt


def check_registration(output):
    registration = ref.read_json(output / "registration.json")
    if (
        registration["protocol_sha256"] != frozen.PROTOCOL_SHA256
        or registration["runtime"] != runtime()
    ):
        raise ValueError("Reference protocol/runtime identity changed")
    if registration["preparation_cases"] != preparations():
        raise ValueError("Registered preparation input changed")
    protocol = frozen.load_protocol()
    if (
        registration["resources"] != protocol["resources"]
        or registration["numerics"] != protocol["numerics"]
        or registration["methods"] != {k: list(v) for k, v in METHODS.items()}
        or registration["duration"] != protocol["preparation"]["duration"]
        or registration["planned_attempts"]
        != [f"{label}/{method}" for label in ("E", "M") for method in METHODS]
        or registration["production_source_hashes"] != production_identity(protocol)
    ):
        raise ValueError("Registered settings/inventory/production identity changed")
    for name, digest in registration["source_hashes"].items():
        if ref.sha(ROOT / name) != digest:
            raise ValueError(f"Registered source changed: {name}")
    if ref.sha(output / "reference_sources.zip") != registration["source_capsule_sha256"]:
        raise ValueError("Source capsule changed")
    return registration


def worker(output, key):
    registration = check_registration(output)
    if key not in registration["planned_attempts"]:
        raise ValueError("Unregistered reference attempt")
    for name, value in registration["thread_environment"].items():
        if os.environ.get(name) != value:
            raise ValueError("Reference numerical thread settings differ")
    label, variant = key.split("/")
    method, refinement = registration["methods"][variant]
    return ref.integrate(
        graph.Model(registration["preparation_cases"][label]),
        output / key,
        method=method,
        refinement=refinement,
        duration=registration["duration"],
        numerics=registration["numerics"],
        resources=registration["resources"],
        artifact_root=output,
    )


def observed(model, increments):
    values = ref.absolute(model, increments)
    readouts = [model.evaluate(v[: 6 * model.n].reshape(6, model.n)) for v in values]
    return {
        "voltage": np.array([r["voltage"] for r in readouts]),
        "gate_scale": np.array([r["gate_scales"] for r in readouts]),
        "membrane_and_junction_flux": np.array(
            [
                np.r_[r["leak_flux"].ravel(), r["pump_flux"].ravel(), r["junction_flux"].ravel()]
                for r in readouts
            ]
        ),
        "binding_cache": np.array([r["packet"][graph.eq.DERIVED_INDEX] for r in readouts]),
        "packet": np.array([r["packet"] for r in readouts]),
        "primary_rhs": np.array([r["primary_rate"] for r in readouts]),
    }


def comparison_scores(model, actual, expected, read_a, read_b, targets):
    def score(a, b, key):
        tolerance = targets[key]
        return float(
            np.max(abs(a - b) / (tolerance["atol"] + tolerance["rtol"] * abs(b)), initial=0)
        )

    a, b = ref.absolute(model, actual), ref.absolute(model, expected)
    n, s = model.n, model.coordinates
    result = {
        "ionic_state": score(a[:, : 3 * n], b[:, : 3 * n], "ionic_state_and_ledger"),
        "regulatory_state": score(
            a[:, 3 * n : 6 * n], b[:, 3 * n : 6 * n], "regulatory_state_and_ledger"
        ),
        "ionic_history": score(
            a[:, s.leak.start : s.local.start],
            b[:, s.leak.start : s.local.start],
            "ionic_state_and_ledger",
        ),
        "regulatory_history": score(
            a[:, s.local.start :], b[:, s.local.start :], "regulatory_state_and_ledger"
        ),
    }
    for name in ("voltage", "gate_scale", "membrane_and_junction_flux", "binding_cache"):
        key = "regulatory_state_and_ledger" if name == "binding_cache" else name
        result[name] = score(read_a[name], read_b[name], key)
    return result


def unique_batches(iterables, width):
    if type(width) is not int or not 1 <= width <= 256:
        raise ValueError("Invalid comparison batch width")
    previous, batch = None, []
    for time in heapq.merge(*iterables):
        if time == previous:
            continue
        if previous is not None and time < previous:
            raise ValueError("Nonmonotone comparison grid")
        batch.append(time)
        previous = time
        if len(batch) == width:
            yield np.array(batch)
            batch.clear()
    if batch:
        yield np.array(batch)


def preparation_times(protocol):
    duration = protocol["preparation"]["duration"]
    return np.array([t for t in frozen.observation_times() if t <= duration])


def compare_label(output, label, protocol, deadline):
    trajectories = {key: ref.Trajectory(output / label / key) for key in METHODS}
    model = trajectories["refined"].model
    expected_case = preparations(protocol)[label]
    for trajectory in trajectories.values():
        if (
            trajectory.model.case != expected_case
            or trajectory.report["end"] != protocol["preparation"]["duration"]
        ):
            raise ValueError("Reference cases/clocks do not agree")
    folder = output / label / "comparison"
    folder.mkdir(exist_ok=False)
    pairs = list(itertools.combinations(METHODS, 2))
    maxima = {f"{a}_vs_{b}": {} for a, b in pairs}
    count = chunks = 0
    residual_max = 0.0
    streams = [t.grid() for t in trajectories.values()] + [iter(preparation_times(protocol))]
    for times in unique_batches(streams, protocol["resources"]["window_steps"]):
        if perf_counter() > deadline:
            raise ref.BudgetExceeded("Preparation session wall budget exhausted during comparison")
        states = {k: t.sample(times) for k, t in trajectories.items()}
        readouts = {k: observed(model, state) for k, state in states.items()}
        for state in states.values():
            residual_max = max(residual_max, float(np.max(abs(ref.residual(model, state)))))
            if np.any(state[:, ref.blocked_coordinates(model)] != 0):
                raise ValueError("Blocked comparison history changed")
        for a, b in pairs:
            scores = comparison_scores(
                model,
                states[a],
                states[b],
                readouts[a],
                readouts[b],
                protocol["numerics"]["targets"],
            )
            for key, value in scores.items():
                maxima[f"{a}_vs_{b}"][key] = max(maxima[f"{a}_vs_{b}"].get(key, 0), value)
        path = folder / f"chunk-{chunks:06d}.npz"
        ref.save_arrays(
            path, {"times": times, **states}, output, protocol["resources"]["artifact_budget_bytes"]
        )
        with (folder / "chunks.jsonl").open("a") as handle:
            handle.write(
                json.dumps(
                    {"path": path.name, "sha256": ref.sha(path), "samples": len(times)},
                    sort_keys=True,
                )
                + "\n"
            )
        count, chunks = count + len(times), chunks + 1
    agreement = max(value for metrics in maxima.values() for value in metrics.values())
    summary = {
        "scores": maxima,
        "maximum_score": agreement,
        "samples": count,
        "chunks": chunks,
        "maximum_accounting_residual": residual_max,
        "index_sha256": ref.sha(folder / "chunks.jsonl"),
        "status": "pass"
        if agreement <= protocol["numerics"]["reference_agreement_fraction"]
        and residual_max <= protocol["numerics"]["accounting_atol"]
        else "unqualified",
    }
    ref.write_json(folder / "comparison.json", summary)
    return summary


def preparation_criteria(output, protocol):
    times = preparation_times(protocol)
    start, end = protocol["preparation"]["qualification_window"]
    mask = (times >= start) & (times <= end) & (times == np.floor(times))
    summaries, packets, envelopes = {}, {}, {}
    for label in ("E", "M"):
        trajectories = {k: ref.Trajectory(output / label / k) for k in METHODS}
        model = trajectories["refined"].model
        states = {k: t.sample(times) for k, t in trajectories.items()}
        values = ref.absolute(model, states["refined"])
        reads = observed(model, states["refined"])
        primary = values[:, :6]
        target = protocol["numerics"]["targets"]["regulatory_state_and_ledger"]
        disagreement = np.maximum.reduce(
            [abs(states[k][:, 3:6] - states["refined"][:, 3:6]) for k in METHODS]
        )
        allowance = target["atol"] + target["rtol"] * abs(primary[:, 3:6]) + disagreement
        sign = 1 if label == "E" else -1
        raw_margin = sign * (primary[:, 3] - primary[:, 4])
        conservative_margin = raw_margin - allowance[:, 0] - allowance[:, 1]
        signed_pass = bool(
            np.all(
                conservative_margin[mask]
                >= protocol["preparation"]["minimum_signed_u_minus_m_margin"]
            )
        )
        y, dy, vm = primary[mask], reads["primary_rhs"][mask, :, 0], reads["voltage"][mask, 0]
        p = model.panel["parameters"]
        dv = (dy[:, 0] + dy[:, 1] - dy[:, 2]) * p["F"] * model.volume / (model.area * p["cm"])
        summaries[label] = {
            "status": "pass" if signed_pass else "unqualified",
            "qualification_observations": int(mask.sum()),
            "minimum_signed_margin": float(raw_margin[mask].min()),
            "minimum_margin_after_numerical_allowance": float(conservative_margin[mask].min()),
            "primary_rows": list(graph.eq.PRIMARY),
            "end_minus_start": (y[-1] - y[0]).tolist(),
            "peak_to_peak": np.ptp(y, axis=0).tolist(),
            "maximum_absolute_rhs": abs(dy).max(axis=0).tolist(),
            "endpoint_rhs": dy[-1].tolist(),
            "voltage": {
                "end_minus_start": float(vm[-1] - vm[0]),
                "peak_to_peak": float(np.ptp(vm)),
                "maximum_absolute_rhs": float(abs(dv).max()),
                "endpoint": float(vm[-1]),
            },
            "equilibrium_required": False,
            "equilibrium_claimed": False,
        }
        envelopes[label] = allowance[-1]
        packets[label] = {
            "initial_primary_anchor": model.anchor.tolist(),
            "prepared_primary": primary[-1, :, None].tolist(),
            "context": model.context.tolist(),
            "complete_increment_state": states["refined"][-1].tolist(),
            "complete_absolute_state": values[-1].tolist(),
            "derived_packet": reads["packet"][-1].tolist(),
            "phase_start": 0.0,
            "phase_end": float(times[-1]),
            "reference_trajectory_sha256": ref.sha(output / label / "refined" / "trajectory.json"),
            "endpoint_regulatory_allowance": allowance[-1].tolist(),
            "transfer": "copy_prepared_primary_and_context_into_new_world_with_zero_ledgers",
        }
        ref.save_arrays(
            output / label / "observations.npz",
            {"times": times, **states, **reads, "regulatory_allowance": allowance},
            output,
            protocol["resources"]["artifact_budget_bytes"],
        )
    separation = abs(
        np.array(packets["E"]["prepared_primary"])[3:, 0]
        - np.array(packets["M"]["prepared_primary"])[3:, 0]
    )
    conservative_separation = separation - envelopes["E"] - envelopes["M"]
    separation_pass = bool(
        np.all(
            conservative_separation
            >= protocol["preparation"]["minimum_per_coordinate_anchor_separation"]
        )
    )
    return {
        "status": "pass"
        if separation_pass and all(s["status"] == "pass" for s in summaries.values())
        else "unqualified",
        "preparations": summaries,
        "regulatory_anchor_separation": separation.tolist(),
        "anchor_separation_after_allowance": conservative_separation.tolist(),
        "separation_status": "pass" if separation_pass else "unqualified",
    }, packets


def qualify(output, deadline):
    check_registration(output)
    protocol = frozen.load_protocol()
    comparisons = {label: compare_label(output, label, protocol, deadline) for label in ("E", "M")}
    criteria, packets = preparation_criteria(output, protocol)
    passed = (
        all(r["status"] == "pass" for r in comparisons.values()) and criteria["status"] == "pass"
    )
    receipt = {
        "status": "pass" if passed else "unqualified",
        "comparisons": comparisons,
        "criteria": criteria,
        "scope": "independent_preparations_only",
        "registration_sha256": ref.sha(output / "registration.json"),
    }
    ref.write_json(output / "qualification.json", receipt)
    if not passed:
        raise ValueError("Preparation qualification failed; no prepared packets published")
    ref.write_json(
        output / "prepared-packets.json",
        {
            "schema_version": 1,
            "status": "independent_reference_preparations_qualified",
            "protocol_id": protocol["protocol_id"],
            "protocol_sha256": frozen.PROTOCOL_SHA256,
            "qualification_sha256": ref.sha(output / "qualification.json"),
            "reference": "Radau_refined",
            "clock": protocol["clock"],
            "packets": packets,
            "candidate_qualification": "not_run",
            "connected_trajectories": "not_run",
        },
    )
    return receipt


def run(output):
    registration = register(output)
    begun = perf_counter()
    deadline = begun + registration["resources"]["session_wall_budget_seconds"]
    attempts = []
    try:
        for key in registration["planned_attempts"]:
            remaining = deadline - perf_counter()
            if remaining <= 0:
                raise ref.BudgetExceeded("Preparation session wall budget exhausted")
            print(f"Starting registered {key}", flush=True)
            log = output / f"{key.replace('/', '-')}.log"
            with log.open("x") as handle:
                result = subprocess.run(
                    [
                        sys.executable,
                        str(Path(__file__).resolve()),
                        "--output",
                        str(output),
                        "--worker",
                        key,
                    ],
                    env=os.environ
                    | registration["thread_environment"]
                    | {"PYTHONDONTWRITEBYTECODE": "1"},
                    stdout=handle,
                    stderr=subprocess.STDOUT,
                    timeout=min(remaining, registration["resources"]["worker_timeout_seconds"]),
                    check=False,
                )
            attempts.append(
                {"key": key, "returncode": result.returncode, "log_sha256": ref.sha(log)}
            )
            if result.returncode != 0:
                failure = output / key / "failure.json"
                if failure.exists() and ref.read_json(failure)["status"] == "incomplete":
                    raise ref.BudgetExceeded(f"Incomplete registered worker: {key}")
                raise ValueError(f"Registered worker refused: {key}; inspect retained log")
            print(f"Completed {key}", flush=True)
        qualification = qualify(output, deadline)
        check_registration(output)
        if perf_counter() > deadline:
            raise ref.BudgetExceeded("Preparation session wall budget exhausted")
        payloads = {
            str(p.relative_to(output)): ref.sha(p) for p in output.rglob("*") if p.is_file()
        }
        receipt = {
            "status": "pass",
            "scope": qualification["scope"],
            "attempts": attempts,
            "seconds": perf_counter() - begun,
            "payload_hashes": payloads,
            "prepared_packets_sha256": ref.sha(output / "prepared-packets.json"),
            "production_changed": False,
            "long_time_rk4_step": "not_selected",
        }
        ref.write_json(output / "verification.json", receipt)
        print(json.dumps(receipt | {"payload_hashes": len(payloads)}, indent=2), flush=True)
    except Exception as error:
        ref.write_json(
            output / "failure.json",
            {
                "status": "incomplete"
                if isinstance(error, (ref.BudgetExceeded, subprocess.TimeoutExpired))
                else "unqualified",
                "exception": type(error).__name__,
                "message": str(error),
                "completed_attempts": attempts,
                "seconds": perf_counter() - begun,
                "no_automatic_retry": True,
            },
        )
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--worker", help=argparse.SUPPRESS)
    args = parser.parse_args()
    output = args.output.resolve()
    if args.worker:
        worker(output, args.worker)
    else:
        run(output)


if __name__ == "__main__":
    main()
