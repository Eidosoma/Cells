"""Bounded multi-root reference comparisons with explicit reader lifetimes.

Reuse immutable numerical readers and score definitions, not duplicated RHSs.
The mapping makes imported trajectories explicit; no copies or filesystem links.
"""

import itertools
import json
from contextlib import ExitStack, contextmanager

import numpy as np

from scripts import qualify_source_graph_paths as campaign

ref, paths, prep = campaign.ref, campaign.paths, campaign.prep


@contextmanager
def open_readers(directories, registration):
    """Close the pinned reader's sampling generator, including early refusals."""
    with ExitStack() as stack:
        readers = {}
        for variant, directory in directories.items():
            reader = ref.Trajectory(directory)
            stack.callback(reader._iterator.close)
            method, refinement = registration["methods"][variant]
            if (
                reader.model.case != registration["case"]
                or reader.report["start"] != 0
                or reader.report["end"] != registration["duration"]
                or reader.report["method"] != method
                or reader.report["refinement"] != refinement
                or reader.report["rtol"] != registration["numerics"]["rtol"] * refinement
                or reader.report["atol"] != registration["numerics"]["atol"] * refinement
                or reader.report["max_step"] != registration["numerics"]["reference_max_step"]
            ):
                raise ValueError("Imported comparison trajectory identity differs")
            readers[variant] = reader
        yield readers


def compare(directories, registration, output, deadline):
    """Retain all six comparisons; score the preregistered required pairs separately."""
    folder = output / "comparison"
    folder.mkdir(exist_ok=False)
    resources, numerics = registration["resources"], registration["numerics"]
    pairs = list(itertools.combinations(directories, 2))
    names = [f"{a}_vs_{b}" for a, b in pairs]
    if len(directories) != 4 or not set(registration["required_pairs"]) <= set(names):
        raise ValueError("Unregistered comparison inventory")
    maxima = {name: {} for name in names}
    samples = chunks = 0
    residual_max = 0.0
    with open_readers(directories, registration) as readers, ExitStack() as streams_stack:
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
    maximum = max(
        score for name in registration["required_pairs"] for score in maxima[name].values()
    )
    summary = {
        "status": "agreement_met"
        if maximum <= numerics["reference_agreement_fraction"]
        and residual_max <= numerics["accounting_atol"]
        else "agreement_not_met",
        "scope": "refinement_sensitivity_not_original_case_qualification",
        "scores": maxima,
        "required_pairs": registration["required_pairs"],
        "maximum_required_score": maximum,
        "maximum_all_pairs_score": max(
            score for scores in maxima.values() for score in scores.values()
        ),
        "maximum_accounting_residual": residual_max,
        "samples": samples,
        "chunks": chunks,
        "estimated_working_array_bytes": estimate,
        "index_sha256": ref.sha(folder / "chunks.jsonl"),
        "original_BDF_failure_reclassified": False,
    }
    ref.write_json(folder / "comparison.json", summary)
    return summary
