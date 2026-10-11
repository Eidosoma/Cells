"""Read-only D035 audit: identities, new dense path, union grid and retained states.

Primary/history scores are independently normalized. Flux/cache/gate scores are
online results, not independently re-evaluated RHSs. No original-case promotion.
"""

import argparse
import heapq
import itertools
import json
import sys
import zipfile
from contextlib import ExitStack
from pathlib import Path
from time import perf_counter

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import audit_source_graph_paths as old_audit  # noqa: E402
from scripts import refine_graph_reference as trial  # noqa: E402


def check_integrity(output):
    registration = trial.check_registration(output)
    name = "verification.json" if (output / "verification.json").exists() else "failure.json"
    receipt = trial.ref.read_json(output / name)
    names = {str(p.relative_to(output)) for p in output.rglob("*") if p.is_file()}
    if names != set(receipt["payload_hashes"]) | {name} or receipt[
        "registration_sha256"
    ] != trial.ref.sha(output / "registration.json"):
        raise ValueError("Refinement payload inventory/registration differs")
    for path, digest in receipt["payload_hashes"].items():
        target = output / path
        if not target.resolve().is_relative_to(output) or trial.ref.sha(target) != digest:
            raise ValueError("Refinement payload differs")
    session = trial.ref.read_json(output / "session.json")
    (attempt,) = receipt["attempts"]
    if (
        attempt["key"] != "bdf_tight"
        or attempt["initial_time"] != 0
        or attempt["attempt_id"] != f"{registration['output_directory']}/bdf_tight"
        or session["attempt_id"] != attempt["attempt_id"]
        or session["registration_sha256"] != receipt["registration_sha256"]
        or session["wall_budget_seconds"]
        != registration["resources"]["session_wall_budget_seconds"]
        or trial.ref.sha(output / "bdf-tight.log") != attempt["log_sha256"]
        or receipt["case_qualification_changed"]
    ):
        raise ValueError("Refinement session/attempt identity differs")
    if name == "verification.json":
        if (
            receipt["status"] != "pass"
            or attempt["status"] != "complete_not_yet_cross_qualified"
            or attempt["returncode"] != 0
            or receipt["seconds"] > registration["resources"]["session_wall_budget_seconds"]
            or receipt["NUM005c1_complete"]
            or receipt["candidate_selected"]
        ):
            raise ValueError("Refinement completion claim differs")
    elif receipt["status"] not in ("incomplete", "unqualified") or receipt["automatic_retry"]:
        raise ValueError("Refinement failure claim differs")
    return registration, receipt, name


def accepted_grid(directory):
    yield 0.0
    with (directory / "chunks.jsonl").open() as handle:
        for line in handle:
            with np.load(directory / json.loads(line)["path"], allow_pickle=False) as data:
                times = data["times"]
            for a, b in zip(times[:-1], times[1:], strict=True):
                yield float(a + (b - a) / 2)
                yield float(b)


def audit_comparison(output, registration, deadline):
    folder = output / "comparison"
    summary = trial.ref.read_json(folder / "comparison.json")
    if (
        trial.ref.sha(folder / "chunks.jsonl") != summary["index_sha256"]
        or summary["required_pairs"] != registration["required_pairs"]
        or summary["original_BDF_failure_reclassified"]
    ):
        raise ValueError("Refinement comparison index/selection differs")
    directories = trial.directories(registration)
    n, e = len(registration["case"]["cell_ids"]), len(registration["case"]["edges"])
    size, anchor = 13 * n + 4 * e, np.asarray(registration["case"]["primary"]).ravel()
    slices = {
        "ionic_state": (slice(0, 3 * n), "ionic_state_and_ledger"),
        "regulatory_state": (slice(3 * n, 6 * n), "regulatory_state_and_ledger"),
        "ionic_history": (slice(6 * n, 10 * n + 3 * e), "ionic_state_and_ledger"),
        "regulatory_history": (slice(10 * n + 3 * e, size), "regulatory_state_and_ledger"),
    }
    scores = {
        f"{a}_vs_{b}": dict.fromkeys(slices, 0.0) for a, b in itertools.combinations(directories, 2)
    }
    samples = chunks = 0
    with trial.comparison.open_readers(directories, registration) as readers, ExitStack() as stack:
        grids = [accepted_grid(d) for d in directories.values()]
        for grid in grids:
            stack.callback(grid.close)
        expected = (
            key
            for key, _ in itertools.groupby(heapq.merge(*grids, registration["observation_times"]))
        )
        with (folder / "chunks.jsonl").open() as handle:
            for line in handle:
                if perf_counter() > deadline:
                    raise TimeoutError("Read-only refinement comparison budget exhausted")
                entry = json.loads(line)
                path = folder / entry["path"]
                if (
                    entry["path"] != f"chunk-{chunks:06d}.npz"
                    or trial.ref.sha(path) != entry["sha256"]
                ):
                    raise ValueError("Refinement comparison chunk differs")
                with np.load(path, allow_pickle=False) as data:
                    times = data["times"]
                    states = {key: data[key].copy() for key in directories}
                if (
                    times.shape != (entry["samples"],)
                    or not 1 <= len(times) <= registration["resources"]["window_steps"]
                    or entry["start"] != times[0]
                    or entry["end"] != times[-1]
                ):
                    raise ValueError("Refinement sample metadata differs")
                np.testing.assert_array_equal(times, list(itertools.islice(expected, len(times))))
                for key, state in states.items():
                    if state.shape != (len(times), size) or not np.isfinite(state).all():
                        raise ValueError("Refinement sample shape/values differ")
                    np.testing.assert_array_equal(state, readers[key].sample(times))
                    state[:, : 6 * n] += anchor
                for a, b in itertools.combinations(directories, 2):
                    for quantity, (selected, target) in slices.items():
                        tol = registration["numerics"]["targets"][target]
                        value = float(
                            np.max(
                                abs(states[a][:, selected] - states[b][:, selected])
                                / (tol["atol"] + tol["rtol"] * abs(states[b][:, selected])),
                                initial=0,
                            )
                        )
                        scores[f"{a}_vs_{b}"][quantity] = max(
                            scores[f"{a}_vs_{b}"][quantity], value
                        )
                samples, chunks = samples + len(times), chunks + 1
        if (
            next(expected, None) is not None
            or samples != summary["samples"]
            or chunks != summary["chunks"]
        ):
            raise ValueError("Incomplete refinement union grid")
    for pair, quantities in scores.items():
        for quantity, value in quantities.items():
            if value != summary["scores"][pair][quantity]:
                raise ValueError("Independent refinement score differs")
    required = max(v for k in registration["required_pairs"] for v in summary["scores"][k].values())
    all_maximum = max(v for quantities in summary["scores"].values() for v in quantities.values())
    agree = (
        required <= registration["numerics"]["reference_agreement_fraction"]
        and summary["maximum_accounting_residual"] <= registration["numerics"]["accounting_atol"]
    )
    if (
        not np.isfinite(all_maximum)
        or required != summary["maximum_required_score"]
        or all_maximum != summary["maximum_all_pairs_score"]
        or summary["status"] != ("agreement_met" if agree else "agreement_not_met")
        or summary["estimated_working_array_bytes"]
        > registration["resources"]["estimated_array_budget_bytes"]
    ):
        raise ValueError("Refinement comparison decision differs")
    return {
        "samples": samples,
        "chunks": chunks,
        "independently_recomputed_primary_history_scores": scores,
        "sampled_state_identity": "all_four_inputs_exact",
        "derived_scores": "online_recorded_not_independently_recomputed",
        "agreement": summary["status"],
    }


def verify(output):
    begun = perf_counter()
    registration, receipt, name = check_integrity(output)
    deadline = begun + registration["resources"]["session_wall_budget_seconds"]
    path_audit = grid_audit = None
    if (output / "bdf_tight/trajectory.json").exists():
        with zipfile.ZipFile(output / "reference_sources.zip") as archive:
            panel = json.loads(archive.read("configs/reference/source_emt_pair_panel_v1.json"))
        path_audit = old_audit.audit_trajectory(
            output / "bdf_tight", registration["case"], registration, panel, deadline
        )
    if (output / "comparison/comparison.json").exists():
        grid_audit = audit_comparison(output, registration, deadline)
    if name == "verification.json" and (
        path_audit is None
        or grid_audit is None
        or grid_audit["agreement"] != "agreement_met"
        or receipt["comparison"] != trial.ref.read_json(output / "comparison/comparison.json")
    ):
        raise ValueError("Missing refinement agreement evidence")
    check_integrity(output)
    if perf_counter() > deadline:
        raise TimeoutError("Read-only refinement audit session exhausted")
    return {
        "status": "pass",
        "trial_status": receipt["status"],
        "scope": "refinement_integrity_new_dense_path_union_grid_and_primary_history_score_audit",
        "trajectory": path_audit,
        "comparison": grid_audit,
        "receipt_sha256": trial.ref.sha(output / name),
        "registration_sha256": trial.ref.sha(output / "registration.json"),
        "prior_audit_sha256": registration["prior_audit_sha256"],
        "payloads": len(receipt["payload_hashes"]),
        "source_capsule_files": len(registration["source_hashes"]),
        "aggregate_artifact_bytes": registration["storage_budget"]["prior_bytes"]
        + trial.previous.tree_bytes(output),
        "seconds": perf_counter() - begun,
        "audit_wall_budget_seconds": registration["resources"]["session_wall_budget_seconds"],
        "case_qualification_changed": False,
        "original_qualified_conditions": 10,
        "NUM005c1_complete": False,
        "production_changed": False,
        "candidate_selected": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.directory.absolute()), indent=2))


if __name__ == "__main__":
    main()
