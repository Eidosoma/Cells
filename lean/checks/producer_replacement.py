"""Check the FR-38 producer balances in the owner's replacement/restart record and checkpoint."""

import argparse
import json
import math
from pathlib import Path

import numpy as np

from validation.gene_regulation.sheet_check import COPY_FMOL


def run_owner(folder):
    """Run the Cells fixture once and retain its returned readouts alongside its checkpoint."""
    from validation.gene_regulation import engine_run, replace_restart

    folder.mkdir(parents=True, exist_ok=False)
    source, patch = engine_run.provenance(folder)
    if patch is not None:
        (folder / "checkout.patch").write_text(patch)
    report = replace_restart.check(folder)
    report.update(engine_run.late_sources(folder, source))
    # Four verdicts in the first development fixture are NumPy booleans.
    for name, value in report["verdicts"].items():
        if isinstance(value, np.bool_):
            report["verdicts"][name] = bool(value)
    path = folder / "owner-return.json"
    path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    return path


def balance(steps, *terms):
    """Check the signed fmol terms against cumulative binary64 rounding over these steps."""
    gap = math.fsum(terms)
    bound = 64 * math.ulp(1.0) * steps * math.fsum(abs(x) for x in terms)
    assert abs(gap) <= bound, (terms, gap, bound)
    return gap


def label_agreement(old, recorded):
    np.testing.assert_allclose(recorded, old, rtol=16 * math.ulp(1.0), atol=0, equal_nan=False)


def compare(path):
    report = json.loads(path.read_text())
    assert report["kind"] == "cells.gene_regulation.replace_restart@1"
    assert report["passed"] and all(report["verdicts"].values()), report["verdicts"]
    folder = path.parent / "checkpoint"
    manifest = json.loads((folder / "manifest.json").read_text())
    spec, clock = manifest["spec"], manifest["clock"]
    model = spec["model"]
    (cell,) = model["cells"]
    gene = next(op for op in model["operators"] if op["law"] == "templated_polymerisation@1")
    labels_op = next(op for op in model["operators"] if op["law"] == "neutral_arrival_labels@1")
    (chain,) = gene["chains"]
    release = chain["release"]
    (pair,) = release["fates"]
    fates = [pair["durable"], pair["short_lived"]]
    assert [d["polymer"] for d in gene["degradations"]] == fates
    assert not gene["transfers"] and not gene.get("exports")
    assert release["label"] is None  # Marking is at detachment. The attached hold has base share.
    (event,) = spec["experiment"]["replacement_events"]
    rows = {float(t): row for t, row in report["readouts"].items()}
    before, resumed = rows[event["time"]], rows[clock["time"]]
    assert event["slot"] == cell["id"] and event["time"] < clock["time"]
    assert clock["time"] == report["checkpoint"]["time"] == min(report["resumed_outputs_s"])
    assert not report["physical_fields_differing"] and not report["resumed_fields_differing"]
    labels = report["world"]["labels"]
    assert [s["id"] for s in labels_op["species"]] == fates
    assert all(s["labels"] == labels for s in labels_op["species"])
    founder = f"{cell['id']}-g0-{chain['id']}"
    newcomer = f"{cell['id']}-g1-{chain['id']}"
    cohort = labels.index(f"{founder}-cohort")
    fresh = labels.index(newcomer)
    steps = clock["step_index"]
    birth_hold = math.fsum(release["initial_copies"]) * float(COPY_FMOL)
    gaps = {"founder": {}, "newcomer": {}}
    with np.load(folder / "state.npz", allow_pickle=False) as state:
        assert state["generation"].tolist() == [1] and state["poly_rep_applied"].tolist() == [1]
        # The founder started at zero. Every departed total must be the newcomer's birth offset.
        counters = 0
        for group in ("chain", "release", "degradation"):
            offset = state[f"poly_rep_{group}_birth_fmol"]
            np.testing.assert_array_equal(offset, state[f"poly_rep_{group}_departed_fmol"])
            counters += offset.size
        born_a = float(state["poly_rep_chain_birth_fmol"][0, 2])
        born_q = state["poly_rep_release_birth_fmol"][0, 0]
        born_d = state["poly_rep_degradation_birth_fmol"]
        total_a = float(state["poly_released_fmol"][0])
        total_q = state["poly_hold_released_fmol"][0, 0]
        total_d = state["poly_degraded_fmol"]
        hold = float(state["poly_rep_hold_removed_fmol"][0, 0])
        gaps["founder"]["hold"] = balance(steps, birth_hold, born_a, -hold, *-born_q)
        gaps["newcomer"]["hold"] = balance(
            steps, total_a, -born_a, -float(state["poly_hold_fmol"].sum()), *born_q, *-total_q
        )
        hold_by_label = state["label_pool_removed_fmol"][0, :, 0]
        label_agreement([hold if label == "base" else 0.0 for label in labels], hold_by_label)
        label_agreement(hold_by_label, [resumed["hold_departed"][label] for label in labels])
        species = [s["id"] for s in model["species"]]
        old = np.array([[before[f]["in_cell"][label] for label in labels] for f in fates])
        assert np.all(old[:, fresh] == 0) and np.all(old[:, cohort] > 0)
        recorded = state["label_removed_fmol"][:, :, 0]
        label_agreement(old, recorded)
        for j, fate in enumerate(fates):
            i = species.index(fate)
            former = float(state["replacement_removed_fmol"][i, 0])
            supplied = float(state["replacement_supplied_fmol"][i, 0])
            current = math.fsum(resumed[fate]["in_cell"].values())
            label_agreement(recorded[j], [resumed[fate]["departed"][label] for label in labels])
            label_agreement([former], [math.fsum(recorded[j])])
            gaps["founder"][fate] = balance(
                steps, cell["initial_amount_fmol"][fate], born_q[j], -former, -born_d[j]
            )
            gaps["newcomer"][fate] = balance(
                steps, supplied, total_q[j], -born_q[j], -current, born_d[j], -total_d[j]
            )

        # Swap two IDs in one fate. Its physical total still closes, but the per-label test fails.
        swapped = recorded[0].copy()
        swapped[[cohort, fresh]] = swapped[[fresh, cohort]]
        assert math.fsum(swapped) == math.fsum(recorded[0])
        try:
            label_agreement(old[0], swapped)
        except AssertionError:
            misplaced = float(abs(swapped[fresh] - old[0, fresh]))
        else:
            raise AssertionError("the label comparison accepted a swapped producer")
    return dict(
        engine_revision=report["engine_revision"],
        replacement_s=event["time"],
        checkpoint_s=clock["time"],
        resumed_samples_s=report["resumed_outputs_s"],
        native_verdicts=len(report["verdicts"]),
        birth_offsets_checked=counters,
        departing_label_amounts_checked=old.size + len(labels),
        max_fate_label_error_fmol=float(np.max(np.abs(old - recorded))),
        founder_hold_removed_fmol=hold,
        balance_residuals_fmol=gaps,
        swapped_durable_cohort_fmol=misplaced,
        cohort_survival=report["survival"],
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="saved result JSON, or a fresh folder with --run")
    parser.add_argument("--run", action="store_true", help="run the owner's development fixture")
    args = parser.parse_args()
    record = run_owner(args.path) if args.run else args.path
    print(json.dumps(compare(record), indent=2, allow_nan=False))
