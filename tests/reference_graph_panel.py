"""Bounded selected-reference panels, independent of trajectory storage ownership.

The observer arithmetic is extracted unchanged from the frozen long-reference
runner; only reader ownership is injected. Old source capsules remain immutable.
"""

import itertools
import json
from contextlib import ExitStack

import numpy as np

from scripts import qualify_source_graph_paths as campaign
from tests.reference_graph_comparison import open_readers

ref, paths, prep, graph = campaign.ref, campaign.paths, campaign.prep, campaign.graph
guard, labels_with_allowance = campaign.guard, campaign.labels_with_allowance


def compare(directories, output, case, registration, deadline):
    """Require every pair in an explicitly selected three-reference panel."""
    folder = output / case / "comparison"
    folder.mkdir(exist_ok=False)
    resources, numerics = registration["resources"], registration["numerics"]
    pairs = list(itertools.combinations(directories, 2))
    names = [f"{a}_vs_{b}" for a, b in pairs]
    if len(directories) != 3 or list(directories) != registration["reference_order"]:
        raise ValueError("Unregistered comparison inventory")
    maxima = {name: {} for name in names}
    samples = chunks = 0
    residual_max = 0.0
    selected = registration | {"case": registration["cases"][case]}
    with open_readers(directories, selected) as readers, ExitStack() as streams_stack:
        model = readers["refined"].model
        estimate = 8 * resources["window_steps"] * (112 * model.coordinates.size + 384 * model.n)
        if estimate > resources["estimated_array_budget_bytes"]:
            raise ref.BudgetExceeded("Multi-root comparison array estimate exceeds budget")
        streams = [r.grid() for r in readers.values()]
        for stream in streams:
            streams_stack.callback(stream.close)
        streams.append(iter(registration["observation_times"]))
        for times in prep.unique_batches(streams, resources["window_steps"]):
            campaign.guard(deadline)
            states = {key: reader.sample(times) for key, reader in readers.items()}
            readouts = {key: prep.observed(model, state) for key, state in states.items()}
            for state in states.values():
                residual_max = max(residual_max, float(np.max(abs(ref.residual(model, state)))))
                if np.any(state[:, ref.blocked_coordinates(model)] != 0):
                    raise ValueError("Blocked comparison history changed")
            for a, b in pairs:
                for quantity, score in prep.comparison_scores(
                    model, states[a], states[b], readouts[a], readouts[b], numerics["targets"]
                ).items():
                    if not np.isfinite(score):
                        raise ValueError("Nonfinite reference comparison")
                    maxima[f"{a}_vs_{b}"][quantity] = max(
                        maxima[f"{a}_vs_{b}"].get(quantity, 0), score
                    )
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
            samples, chunks = samples + len(times), chunks + 1
        campaign.guard(deadline)
    maximum = max(score for name in names for score in maxima[name].values())
    summary = {
        "status": "pass"
        if maximum <= numerics["reference_agreement_fraction"]
        and residual_max <= numerics["accounting_atol"]
        else "unqualified",
        "scope": "selected_reference_trio_all_pairs_unchanged_error_targets",
        "scores": maxima,
        "required_pairs": names,
        "maximum_score": maximum,
        "maximum_accounting_residual": residual_max,
        "samples": samples,
        "chunks": chunks,
        "estimated_working_array_bytes": estimate,
        "index_sha256": ref.sha(folder / "chunks.jsonl"),
    }
    ref.write_json(folder / "comparison.json", summary)
    return summary


def observe(directories, output, case, registration, deadline):
    """Read selected source paths without copying them or changing global methods."""
    if len(directories) != 3 or list(directories) != registration["reference_order"]:
        raise ValueError("Unregistered observer reference inventory")
    selected = registration | {"case": registration["cases"][case]}
    with open_readers(directories, selected) as readers:
        return _observe(readers, output, case, registration, deadline)


def _observe(ts, output, case, registration, deadline):
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
