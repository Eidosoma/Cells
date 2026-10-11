"""Read-only A2 audit: composite identities, new curves, selected samples and observers."""

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
from scripts import audit_source_graph_paths as old  # noqa: E402
from scripts import complete_graph_reference_panel as panel  # noqa: E402

ref = panel.ref


def check_integrity(output):
    registration = panel.check_registration(output)
    passed = (output / "verification.json").exists()
    name = "verification.json" if passed else "failure.json"
    if passed and (output / "failure.json").exists():
        raise ValueError("Both panel pass and failure receipts exist")
    receipt = ref.read_json(output / name)
    names = {str(p.relative_to(output)) for p in output.rglob("*") if p.is_file()}
    if names != set(receipt["payload_hashes"]) | {name} or receipt[
        "registration_sha256"
    ] != ref.sha(output / "registration.json"):
        raise ValueError("Panel payload inventory/registration differs")
    for path, digest in receipt["payload_hashes"].items():
        target = output / path
        if not target.resolve().is_relative_to(output) or ref.sha(target) != digest:
            raise ValueError("Panel payload differs")
    attempts = receipt["attempts"]
    attempted = [a["key"] for a in attempts]
    if attempted != registration["planned_attempts"][: len(attempted)] or any(
        a["initial_time"] != 0
        or a["attempt_id"] != f"{registration['output_directory']}/{a['key']}"
        for a in attempts
    ):
        raise ValueError("Panel attempt order/identity differs")
    starts = (
        [json.loads(line) for line in (output / "attempts.jsonl").read_text().splitlines()]
        if attempts
        else []
    )
    if starts != [
        {key: a[key] for key in ("key", "attempt_id", "initial_time")} | {"status": "started"}
        for a in attempts
    ]:
        raise ValueError("Panel start ledger differs")
    for attempt in attempts:
        if ref.sha(output / f"{attempt['key'].replace('/', '-')}.log") != attempt["log_sha256"]:
            raise ValueError("Panel worker log differs")
    session = ref.read_json(output / "session.json")
    if (
        session["registration_sha256"] != receipt["registration_sha256"]
        or session["wall_budget_seconds"]
        != registration["resources"]["session_wall_budget_seconds"]
        or session["automatic_retry"]
        or receipt["original_campaign_reclassified"]
    ):
        raise ValueError("Panel session/preservation policy differs")
    new_cases = [registration["adopted_case"], *registration["new_cases"]]
    completed = receipt["new_observer_qualified_cases"]
    if completed != new_cases[: len(completed)]:
        raise ValueError("Panel qualified-case order differs")
    for case in completed:
        comparison = panel.case_result(registration, case)["comparison"]
        adopted = case == registration["adopted_case"]
        if (
            comparison["status"] != ("agreement_met" if adopted else "pass")
            or comparison["maximum_required_score" if adopted else "maximum_score"]
            > registration["numerics"]["reference_agreement_fraction"]
        ):
            raise ValueError("Unqualified comparison cannot be accepted")
    if passed:
        if (
            receipt["status"] != "pass"
            or attempted != registration["planned_attempts"]
            or any(
                a["status"] != "complete_not_yet_cross_qualified" or a["returncode"] != 0
                for a in attempts
            )
            or receipt["seconds"] > registration["resources"]["session_wall_budget_seconds"]
            or completed != new_cases
            or not receipt["amended_panel_cross_qualified"]
            or receipt["qualified_conditions"] != 14
            or receipt["original_qualified_conditions"] != 10
            or receipt["references"] != registration["references"]
            or receipt["production_changed"]
            or receipt["candidate_selected"]
            or receipt["NUM005c_complete"]
            or receipt["cases"]
            != {case: panel.case_result(registration, case) for case in registration["cases"]}
        ):
            raise ValueError("Incomplete or changed panel cannot pass")
    elif (
        receipt["status"] not in ("incomplete", "unqualified")
        or not receipt["no_automatic_retry"]
        or receipt["not_started"] != registration["planned_attempts"][len(attempted) :]
        or receipt["original_qualified_cases"] != registration["original_qualified_cases"]
    ):
        raise ValueError("Invalid panel stopping receipt")
    return registration, receipt, name


def sampled_identity(folder, directories, selected, deadline, *, comparison):
    """Independent grid and four primary/history score formulas, no RHS evaluation."""
    n, e = len(selected["case"]["cell_ids"]), len(selected["case"]["edges"])
    size, anchor = 13 * n + 4 * e, np.asarray(selected["case"]["primary"]).ravel()
    summary = ref.read_json(folder / ("comparison.json" if comparison else "summary.json"))
    if summary["index_sha256"] != ref.sha(folder / "chunks.jsonl"):
        raise ValueError("Selected-sample index differs")
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
    with panel.panel.open_readers(directories, selected) as readers, ExitStack() as stack:
        grids = (
            [panel.a1_audit.accepted_grid(d) for d in directories.values()] if comparison else []
        )
        for grid in grids:
            stack.callback(grid.close)
        expected = (
            key for key, _ in itertools.groupby(heapq.merge(*grids, selected["observation_times"]))
        )
        with (folder / "chunks.jsonl").open() as handle:
            for line in handle:
                if perf_counter() > deadline:
                    raise TimeoutError("Read-only panel sample budget exhausted")
                entry = json.loads(line)
                path = folder / entry["path"]
                if entry["path"] != f"chunk-{chunks:06d}.npz" or ref.sha(path) != entry["sha256"]:
                    raise ValueError("Selected-sample chunk differs")
                with np.load(path, allow_pickle=False) as data:
                    times = data["times"]
                    states = {key: data[key].copy() for key in directories}
                    if comparison and set(data.files) != {"times", *directories}:
                        raise ValueError("Comparison state inventory differs")
                if (
                    times.shape != (entry["samples"],)
                    or not 1 <= len(times) <= selected["resources"]["window_steps"]
                ):
                    raise ValueError("Selected-sample shape/window differs")
                if comparison and (entry["start"] != times[0] or entry["end"] != times[-1]):
                    raise ValueError("Comparison start/end metadata differs")
                np.testing.assert_array_equal(times, list(itertools.islice(expected, len(times))))
                for key, state in states.items():
                    if state.shape != (len(times), size) or not np.isfinite(state).all():
                        raise ValueError("Selected-sample state shape/values differ")
                    np.testing.assert_array_equal(state, readers[key].sample(times))
                    state[:, : 6 * n] += anchor
                if comparison:
                    for a, b in itertools.combinations(directories, 2):
                        for quantity, (chosen, target) in slices.items():
                            tol = selected["numerics"]["targets"][target]
                            score = float(
                                np.max(
                                    abs(states[a][:, chosen] - states[b][:, chosen])
                                    / (tol["atol"] + tol["rtol"] * abs(states[b][:, chosen])),
                                    initial=0,
                                )
                            )
                            scores[f"{a}_vs_{b}"][quantity] = max(
                                scores[f"{a}_vs_{b}"][quantity], score
                            )
                samples, chunks = samples + len(times), chunks + 1
        if (
            next(expected, None) is not None
            or samples != summary["samples"]
            or chunks != summary["chunks"]
        ):
            raise ValueError("Selected-sample grid coverage differs")
    result = {
        "samples": samples,
        "chunks": chunks,
        "sampled_state_identity": "all_selected_inputs_exact",
    }
    if comparison:
        if list(summary["required_pairs"]) != list(scores) or set(summary["scores"]) != set(scores):
            raise ValueError("Selected comparison pair inventory differs")
        for pair, quantities in scores.items():
            if set(summary["scores"][pair]) != {
                *slices,
                "voltage",
                "gate_scale",
                "membrane_and_junction_flux",
                "binding_cache",
            }:
                raise ValueError("Selected comparison quantity inventory differs")
            for key, value in quantities.items():
                if value != summary["scores"][pair][key]:
                    raise ValueError("Independent panel score differs")
        maximum = max(v for quantities in summary["scores"].values() for v in quantities.values())
        passing = (
            maximum <= selected["numerics"]["reference_agreement_fraction"]
            and summary["maximum_accounting_residual"] <= selected["numerics"]["accounting_atol"]
        )
        if (
            any(not np.isfinite(v) or v < 0 for q in summary["scores"].values() for v in q.values())
            or not np.isfinite(summary["maximum_accounting_residual"])
            or maximum != summary["maximum_score"]
            or summary["status"] != ("pass" if passing else "unqualified")
            or summary["estimated_working_array_bytes"]
            > selected["resources"]["estimated_array_budget_bytes"]
        ):
            raise ValueError("Selected comparison decision differs")
        result.update(
            independently_recomputed_primary_history_scores=scores,
            agreement=summary["status"],
            derived_scores="online_recorded_not_independently_recomputed",
        )
    return result


def observer_events(folder, case, registration, deadline):
    """Independently reproduce every sampled event/label summary, not phenotype acceptance."""
    summary = ref.read_json(folder / "summary.json")
    times, labels, goal = [], [], None
    with (folder / "chunks.jsonl").open() as handle:
        for line in handle:
            if perf_counter() > deadline:
                raise TimeoutError("Read-only panel observer budget exhausted")
            with np.load(folder / json.loads(line)["path"], allow_pickle=False) as data:
                times.extend(data["times"].tolist())
                labels.extend(data["labels"].tolist())
                goal = float(data["native_style_goal_distance"][-1])
    labels, times = np.asarray(labels), np.asarray(times)
    item = next(i for i in registration["inventory"] if i["id"] == case)
    target = 1 if item["target_label"] == "E" else -1
    low, high = registration["observer"]["terminal_window"]
    terminal = (times >= low) & (times <= high)
    expected = []
    for i, cell_id in enumerate(registration["cases"][case]["cell_ids"]):
        hits = [j for j, row in enumerate(labels) if row[i] == target]
        hit = hits[0] if hits else None
        expected.append(
            {
                "cell_id": cell_id,
                "initial_prepared_label": item["prepared_labels"][i],
                "endpoint_label": int(labels[-1, i]),
                "terminal_labels": sorted(set(labels[terminal, i].tolist())),
                "target_at_all_terminal_observations": bool(all(labels[terminal, i] == target)),
                "unresolved_observations": int(sum(labels[:, i] == 2)),
                "first_sampled_target_time": None if hit is None else float(times[hit]),
                "already_target_at_start": hit == 0,
                "preceding_non_target_bracket": None
                if hit in (None, 0)
                else [float(times[hit - 1]), float(times[hit])],
                "bracket_left_label": None if hit in (None, 0) else int(labels[hit - 1, i]),
                "right_censored_no_sampled_target": hit is None,
                "late_return_times": [
                    float(times[j])
                    for j in range(1, len(times))
                    if labels[j - 1, i] == target and labels[j, i] != target
                ],
                "label_change_times": [
                    float(times[j])
                    for j in range(1, len(times))
                    if labels[j - 1, i] != labels[j, i]
                ],
            }
        )
    if (
        summary["cells"] != expected
        or summary["recipient_terminal_target"]
        != expected[0]["target_at_all_terminal_observations"]
        or summary["native_style_goal_distance_endpoint"] != goal
        or summary["native_style_goal_below_2_endpoint_diagnostic_only"] != (goal < 2)
        or summary["candidate_error_included"]
        or summary["equilibrium_claimed"]
    ):
        raise ValueError("Independent observer event summary differs")
    return {"cells": len(expected), "event_summary": "independently_recomputed"}


def verify(output):
    begun = perf_counter()
    registration, receipt, name = check_integrity(output)
    deadline = begun + registration["resources"]["session_wall_budget_seconds"]
    with zipfile.ZipFile(output / "reference_sources.zip") as archive:
        source_panel = json.loads(archive.read("configs/reference/source_emt_pair_panel_v1.json"))
    curves, comparisons, observations = {}, {}, {}
    for attempt in receipt["attempts"]:
        if attempt["status"] == "complete_not_yet_cross_qualified":
            key = attempt["key"]
            case, _ = key.rsplit("/", 1)
            curves[key] = old.audit_trajectory(
                output / key, registration["cases"][case], registration, source_panel, deadline
            )
    for case in [registration["adopted_case"], *registration["new_cases"]]:
        selected = registration | {"case": registration["cases"][case]}
        directories = panel.directories(registration, case)
        if (output / case / "comparison/comparison.json").exists():
            comparisons[case] = sampled_identity(
                output / case / "comparison", directories, selected, deadline, comparison=True
            )
        if (output / case / "observations/summary.json").exists():
            observations[case] = {
                "source_samples": sampled_identity(
                    output / case / "observations",
                    directories,
                    selected,
                    deadline,
                    comparison=False,
                ),
                "labels_cache_and_drift": old.audit_observations(
                    output / case, registration["cases"][case], registration, deadline
                ),
                "events": observer_events(
                    output / case / "observations", case, registration, deadline
                ),
            }
    if name == "verification.json" and (
        set(curves) != set(registration["planned_attempts"])
        or set(comparisons) != set(registration["new_cases"])
        or any(c["agreement"] != "pass" for c in comparisons.values())
        or set(observations) != {registration["adopted_case"], *registration["new_cases"]}
    ):
        raise ValueError("Missing complete amended-panel evidence")
    check_integrity(output)
    if perf_counter() > deadline:
        raise TimeoutError("Read-only panel audit session exhausted")
    return {
        "status": "pass",
        "campaign_status": receipt["status"],
        "scope": "pinned_old_audits_plus_new_dense_curves_grid_state_identity_scores_and_observers",
        "receipt_sha256": ref.sha(output / name),
        "registration_sha256": ref.sha(output / "registration.json"),
        "prior_audit_sha256": registration["prior_audit_sha256"],
        "new_trajectory_audits": curves,
        "new_comparison_audits": comparisons,
        "new_observer_audits": observations,
        "new_payloads": len(receipt["payload_hashes"]),
        "source_capsule_files": len(registration["source_hashes"]),
        "aggregate_artifact_bytes": registration["storage_budget"]["prior_bytes"]
        + panel.previous.tree_bytes(output),
        "seconds": perf_counter() - begun,
        "audit_wall_budget_seconds": registration["resources"]["session_wall_budget_seconds"],
        "original_qualified_conditions": 10,
        "amended_qualified_conditions": 10 + len(receipt["new_observer_qualified_cases"]),
        "NUM005c1_complete_under_A2": receipt["status"] == "pass",
        "NUM005c_complete": False,
        "original_campaign_reclassified": False,
        "incomplete_attempts_not_numerically_promoted": True,
        "derived_scores_and_RHS": "online_recorded_not_independently_recomputed",
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
