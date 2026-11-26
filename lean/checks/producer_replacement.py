"""Check the FR-38 producer balances in the owner's replacement/restart record and checkpoint."""

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from cells.definitions.specs import parse_spec
from cells.operators import species_labels
from validation import id_table
from validation.gene_regulation.sheet_check import COPY_FMOL


def balance(steps, *terms):
    """Check the signed fmol terms against cumulative binary64 rounding over these steps."""
    assert all(math.isfinite(x) for x in terms)
    gap = math.fsum(terms)
    bound = 64 * math.ulp(1.0) * steps * math.fsum(abs(x) for x in terms)
    assert abs(gap) <= bound, (terms, gap, bound)
    return gap


def label_agreement(old, recorded):
    assert np.isfinite(old).all() and np.isfinite(recorded).all()
    np.testing.assert_allclose(recorded, old, rtol=16 * math.ulp(1.0), atol=0, equal_nan=False)


def check_export(report, state, spec, gene, export, rows, resumed, labels, founder, cohort, fresh):
    """Cross-check the physical node, its individual labels, returned founder RNA and both routes."""
    model = spec["model"]
    (cell,) = model["cells"]
    (patch,) = [m for m in model["membranes"] if m["id"] == export["patch"]]
    assert patch["inside"] == cell["id"]
    (loss,) = gene["outside_degradations"]
    nodes = [n["id"] for n in model["extracellular"]]
    slot = nodes.index(patch["outside"])
    node = model["extracellular"][slot]
    fate = export["row"]
    assert not node["reservoir"] and (loss["node"], loss["polymer"]) == (node["id"], fate)
    j = [d["polymer"] for d in gene["degradations"]].index(fate)
    species = [s["id"] for s in model["species"]]
    i = species.index(fate)
    at_start = node["initial_amount_fmol"][fate]
    amount = float(state["extracellular_amount_reference"][i, slot]
                   + state["extracellular_amount_increment"][i, slot])
    fwd, back = (float(state[f"poly_export_{k}_fmol"][0]) for k in ("forward", "backward"))
    lost = float(state["poly_outside_degraded_fmol"][0])
    steps = report["checkpoint"]["step_index"]
    outside_gap = balance(steps, at_start, fwd, -back, -lost, -amount)
    moved = state["poly_rep_export_birth_fmol"][0]
    returned = back - moved[1]
    amounts = amount * state["label_outside_share"][j, :, slot]
    label_agreement(amounts, [resumed["R_at_node"][label] for label in labels])
    label_agreement([amount], [math.fsum(amounts)])
    old_ids = (labels.index(founder), cohort)
    cell_amounts = state["amount_reference"][:, 0] + state["amount_increment"][:, 0]
    old_inside = math.fsum(
        float(cell_amounts[species.index(d["polymer"])])
        * float(state["label_share"][k, idx, 0])
        for k, d in enumerate(gene["degradations"]) for idx in old_ids
    )
    label_agreement([old_inside], [resumed["g0_in_cell_fmol"]])
    assert 0 <= old_inside <= returned * (1 + 64 * math.ulp(1.0))
    combined_gap = balance(
        steps, cell["initial_amount_fmol"][fate], at_start,
        state["poly_hold_released_fmol"][0, 0, j], state["replacement_supplied_fmol"][i, 0],
        -state["replacement_removed_fmol"][i, 0], -cell_amounts[i], -amount,
        -state["poly_degraded_fmol"][j], -lost,
    )
    replacement = spec["experiment"]["replacement_events"][0]["time"]
    assert any(0 < t < replacement for t in spec["experiment"]["observation_times"]), (
        "insufficient resolution within the founder's export interval"
    )
    retention = {float(t): v for t, v in report["retention"].items()}
    assert set(retention) == {t for t in rows if t > replacement} and retention
    for t, v in retention.items():
        row = rows[t]
        labelled = [row["R_at_node"][label] for label in labels]
        label_agreement([math.fsum(labelled)], [row["R_at_node_fmol"]])
        old = math.fsum(labelled[idx] for idx in old_ids)
        label_agreement([old, labelled[fresh]], [row["g0_at_node_fmol"], row["g1_at_node_fmol"]])
        label_agreement([old / float(COPY_FMOL)], [v["route1_copies"]])
        one, two, limit = (v[k] for k in ("route1_copies", "route2_copies", "bound_copies"))
        assert all(x is not None and math.isfinite(x) and x >= 0 for x in (one, two, limit))
        # Older finite native receipts predate the explicit three-way status.
        assert v.get("status", "agree") == "agree" and v["agree"] is True and abs(one - two) <= limit
    shifted = amounts.copy()
    shifted[[cohort, fresh]] = amounts[[fresh, cohort]]
    assert math.fsum(amounts) == math.fsum(shifted) and shifted[fresh] != amounts[fresh]
    try:
        label_agreement(amounts, shifted)
    except AssertionError:
        misplaced = abs(float(shifted[fresh] - amounts[fresh]))
    else:
        raise AssertionError("extracellular producer swap passed")
    return dict(outside_residual_fmol=outside_gap, combined_residual_fmol=combined_gap,
                returned_since_replacement_fmol=returned, old_inside_fmol=old_inside,
                swapped_node_label_fmol=misplaced, retention=retention)


def compare(path):
    report = json.loads(path.read_text())
    assert report["kind"] == "cells.gene_regulation.replace_restart@1"
    verdicts = report["verdicts"]
    assert report["passed"] is True and verdicts and all(v is True for v in verdicts.values()), (
        verdicts
    )
    folder = path.parent / "checkpoint"
    manifest = json.loads((folder / "manifest.json").read_text())
    spec, clock = id_table.translate(manifest["spec"]), manifest["clock"]
    model = spec["model"]
    (cell,) = model["cells"]
    gene = next(
        op for op in model["operators"] if op["law"] == "cells.operator.templated_polymerisation@1"
    )
    labels_op = next(
        op for op in model["operators"] if op["law"] == "cells.operator.neutral_arrival_labels@1"
    )
    (chain,) = gene["chains"]
    release = chain["release"]
    (pair,) = release["fates"]
    fates = [pair["durable"], pair["short_lived"]]
    assert [d["polymer"] for d in gene["degradations"]] == fates
    exports = gene.get("exports", [])
    assert not gene["transfers"] and len(exports) <= 1
    assert release["label"] is None  # Marking is at detachment. The attached hold has base share.
    (event,) = spec["experiment"]["replacement_events"]
    rows = {float(t): row for t, row in report["readouts"].items()}
    before, resumed = rows[event["time"]], rows[clock["time"]]
    assert event["slot"] == cell["id"] and event["time"] < clock["time"]
    assert clock["time"] == report["checkpoint"]["time"] == min(report["resumed_outputs_s"])
    assert not report["physical_fields_differing"] and not report["resumed_fields_differing"]
    labels = report["world"]["labels"]
    assert [s["id"] for s in labels_op["species"]] == fates
    founder = f"{cell['id']}-g0-{chain['id']}"
    newcomer = f"{cell['id']}-g1-{chain['id']}"
    if labels_op["species"][0].get("producers"):
        parsed = parse_spec(spec)
        owner = next(o for o in parsed.model.operators if o.law == labels_op["law"])
        derived, _ = species_labels.derived(parsed, owner)
        assert all(list(s.labels) == labels for s in derived.species)
        (producer,) = labels_op["species"][0]["producers"]
        (window,) = producer["windows"]
        assert producer["source"] == chain["id"]
        marked = species_labels.producer_label(cell["id"], 0, chain["id"], window["label"])
    else:
        assert all(s["labels"] == labels for s in labels_op["species"])
        marked = f"{founder}-cohort"
    cohort = labels.index(marked)
    fresh = labels.index(newcomer)
    steps = clock["step_index"]
    birth_hold = math.fsum(release["initial_copies"]) * float(COPY_FMOL)
    gaps = {"founder": {}, "newcomer": {}}
    with np.load(folder / "state.npz", allow_pickle=False) as state:
        assert state["generation"].tolist() == [1] and state["poly_rep_applied"].tolist() == [1]
        # The founder started at zero. Every departed total must be the newcomer's birth offset.
        counters = 0
        groups = ["chain", "release", "degradation"]
        if exports:
            groups.append("export")
        for group in groups:
            offset = state[f"poly_rep_{group}_birth_fmol"]
            assert np.isfinite(offset).all()
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
            old_net = young_net = 0.0
            if exports and exports[0]["row"] == fate:
                forward, backward = state["poly_rep_export_birth_fmol"][0]
                old_net = forward - backward
                young_net = ((state["poly_export_forward_fmol"][0] - forward)
                             - (state["poly_export_backward_fmol"][0] - backward))
            gaps["founder"][fate] = balance(
                steps, cell["initial_amount_fmol"][fate], born_q[j], -former, -born_d[j], -old_net
            )
            gaps["newcomer"][fate] = balance(
                steps, supplied, total_q[j], -born_q[j], -current, born_d[j], -total_d[j], -young_net
            )
        outside = (check_export(report, state, spec, gene, exports[0], rows, resumed,
                                labels, founder, cohort, fresh) if exports else None)

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
        native_verdicts=len(verdicts),
        birth_offsets_checked=counters,
        departing_label_amounts_checked=old.size + len(labels),
        max_fate_label_error_fmol=float(np.max(np.abs(old - recorded))),
        founder_hold_removed_fmol=hold,
        balance_residuals_fmol=gaps,
        swapped_durable_cohort_fmol=misplaced,
        cohort_survival=report["survival"],
        extracellular=outside,
    )


def resolution_control():
    """Vary sampling before and after the export interval independently in the native reader."""
    from validation.gene_regulation import replace_restart as rr

    @dataclass
    class Counters:
        poly_export_forward_fmol: np.ndarray
        poly_export_backward_fmol: np.ndarray

    cases = []
    for times in ([0, 3000, 4800], [0, 1500, 3000, 4800], [0, 3000, 3300, 3600, 4800]):
        raw = rr.chase_world()
        raw["experiment"]["observation_times"] = times
        spec = parse_spec(raw)
        forward = (2 * rr.COPY_FMOL * np.minimum(np.asarray(times) / rr.T_E, 1))[:, None]
        counters = Counters(forward, np.zeros_like(forward))
        rows = {t: {"g0_at_node_fmol": 100 * rr.COPY_FMOL} for t in times if t > rr.T_E}
        wrong = rr.retention(spec, counters, rows)[rr.END]
        rows[rr.END]["g0_at_node_fmol"] = wrong["route2_copies"] * rr.COPY_FMOL
        equal = rr.retention(spec, counters, rows)[rr.END]
        resolved = any(0 < t < rr.T_E for t in times)
        expected = ("disagree", "agree") if resolved else ("insufficient resolution",) * 2
        observed = (wrong["status"], equal["status"])
        cases.append(dict(times_s=times, unequal=wrong, equal=equal, expected=expected,
                          passed=observed == expected))
    return dict(passed=all(c["passed"] for c in cases), cases=cases)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", type=Path, help="Cells replace_restart.json beside checkpoint/")
    parser.add_argument("--resolution", action="store_true", help="Check the native reader on three output grids")
    args = parser.parse_args()
    if args.resolution == (args.path is not None):
        parser.error("choose a report path or --resolution")
    result = resolution_control() if args.resolution else compare(args.path)
    print(json.dumps(result, indent=2, allow_nan=False))
    raise SystemExit(0 if result.get("passed", True) else 1)
