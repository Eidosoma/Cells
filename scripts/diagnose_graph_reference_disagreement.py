"""Post-hoc read-only localization of retained regulatory reference disagreement.

No RHS evaluation, integration, label qualification, tolerance change or retry.
This diagnostic is not part of the prospectively registered scientific run.
"""

import argparse
import hashlib
import itertools
import json
from pathlib import Path
from time import perf_counter

import numpy as np

REGULATION = ("miR200_total", "Zeb_mRNA_total", "ZEB_prot")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def worst_sample(times, actual, expected, tolerance):
    """Exact online normalization, preserving the first tied maximum in a batch."""
    scores = abs(actual - expected) / (tolerance["atol"] + tolerance["rtol"] * abs(expected))
    if scores.ndim != 2 or len(times) != scores.shape[0] or not np.isfinite(scores).all():
        raise ValueError("Invalid diagnostic sample shape/values")
    row, column = np.unravel_index(np.argmax(scores), scores.shape)
    denominator = tolerance["atol"] + tolerance["rtol"] * abs(expected[row, column])
    return {
        "score": float(scores[row, column]),
        "time": float(times[row]),
        "column": int(column),
        "actual": float(actual[row, column]),
        "expected": float(expected[row, column]),
        "absolute_difference": float(abs(actual[row, column] - expected[row, column])),
        "candidate_budget_at_expected": float(denominator),
    }


def coordinate(case, quantity, column):
    n = len(case["cell_ids"])
    if quantity == "regulatory_state" or column < 3 * n:
        species, cell = divmod(column, n)
        return {
            "coordinate": REGULATION[species],
            "kind": "primary" if quantity == "regulatory_state" else "local_regulatory_history",
            "cell_id": case["cell_ids"][cell],
        }
    edge = column - 3 * n
    return {
        "coordinate": "miRNA_exchange_history",
        "kind": "oriented_edge_history",
        "edge_id": case["edge_ids"][edge],
    }


def analyse(directory, case_key, *, wall_budget_seconds=60):
    begun = perf_counter()
    directory = Path(directory).resolve()
    receipt_path = directory / "failure.json"
    receipt = json.loads(receipt_path.read_text())
    registration_path = directory / "registration.json"
    if sha(registration_path) != receipt["registration_sha256"]:
        raise ValueError("Diagnostic registration identity differs")
    registration = json.loads(registration_path.read_text())
    case = registration["cases"][case_key]
    comparison_path = directory / case_key / "comparison/comparison.json"
    if (
        sha(comparison_path)
        != receipt["payload_hashes"][str(comparison_path.relative_to(directory))]
    ):
        raise ValueError("Diagnostic comparison receipt differs")
    comparison = json.loads(comparison_path.read_text())
    index = comparison_path.parent / "chunks.jsonl"
    if sha(index) != comparison["index_sha256"]:
        raise ValueError("Diagnostic comparison index differs")
    n, e = len(case["cell_ids"]), len(case["edges"])
    size = 13 * n + 4 * e
    anchor = np.asarray(case["primary"]).reshape(-1)
    tolerance = registration["numerics"]["targets"]["regulatory_state_and_ledger"]
    fraction = registration["numerics"]["reference_agreement_fraction"]
    slices = {
        "regulatory_state": slice(3 * n, 6 * n),
        "regulatory_history": slice(10 * n + 3 * e, size),
    }
    maxima, samples, chunks, previous_time = {}, 0, 0, -np.inf
    with index.open() as handle:
        for line in handle:
            if perf_counter() - begun > wall_budget_seconds:
                raise TimeoutError("Read-only discrepancy diagnostic budget exhausted")
            entry = json.loads(line)
            path = index.parent / entry["path"]
            if entry["path"] != f"chunk-{chunks:06d}.npz" or sha(path) != entry["sha256"]:
                raise ValueError("Diagnostic comparison chunk differs")
            with np.load(path, allow_pickle=False) as data:
                times = data["times"]
                states = {variant: data[variant].copy() for variant in ("radau", "bdf", "refined")}
            if (
                times.shape != (entry["samples"],)
                or not 1 <= len(times) <= registration["resources"]["window_steps"]
                or not np.isfinite(times).all()
                or times[0] <= previous_time
                or np.any(np.diff(times) <= 0)
            ):
                raise ValueError("Diagnostic comparison sample order differs")
            for state in states.values():
                if state.shape != (len(times), size) or not np.isfinite(state).all():
                    raise ValueError("Diagnostic state shape/values differ")
                state[:, : 6 * n] += anchor
            for a, b in itertools.combinations(states, 2):
                pair = f"{a}_vs_{b}"
                maxima.setdefault(pair, {})
                for quantity, selected in slices.items():
                    result = worst_sample(
                        times, states[a][:, selected], states[b][:, selected], tolerance
                    )
                    if (
                        quantity not in maxima[pair]
                        or result["score"] > maxima[pair][quantity]["score"]
                    ):
                        maxima[pair][quantity] = (
                            result
                            | coordinate(case, quantity, result["column"])
                            | {
                                "comparison_chunk": entry["path"],
                                "reference_allowance_at_expected": fraction
                                * result["candidate_budget_at_expected"],
                            }
                        )
            samples, chunks, previous_time = samples + len(times), chunks + 1, float(times[-1])
    if samples != comparison["samples"] or chunks != comparison["chunks"]:
        raise ValueError("Diagnostic comparison coverage differs")
    for pair, quantities in maxima.items():
        for quantity, witness in quantities.items():
            if witness["score"] != comparison["scores"][pair][quantity]:
                raise ValueError("Independently normalized maximum differs from online receipt")
    return {
        "status": "pass",
        "scope": "post_hoc_retained_regulatory_disagreement_localization_only",
        "case": case_key,
        "campaign_status": receipt["status"],
        "receipt_sha256": sha(receipt_path),
        "registration_sha256": sha(registration_path),
        "comparison_sha256": sha(comparison_path),
        "diagnostic_source_sha256": sha(__file__),
        "samples": samples,
        "chunks": chunks,
        "maxima": maxima,
        "reference_agreement_fraction": fraction,
        "seconds": perf_counter() - begun,
        "wall_budget_seconds": wall_budget_seconds,
        "new_integration": False,
        "scientific_gate_changed": False,
        "method_at_fault_established": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("case")
    args = parser.parse_args()
    print(json.dumps(analyse(args.directory, args.case), indent=2))


if __name__ == "__main__":
    main()
