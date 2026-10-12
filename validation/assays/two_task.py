"""Bounded location/timing assay on the unchanged BETSE runtime.

Task metadata stays outside SimulationSpec. Calibration and complete joint-input
holdouts are fixed before simulation. A failed task is a scientific outcome, not
a reason to relax the reader or to fail an otherwise valid numerical execution.
"""

import copy
import json
from pathlib import Path

import numpy as np

from cells.assays.readout import CentroidReader, VoltageReadout, score_predictions
from cells.core.batch import BatchSpec, WorldSpec
from cells.core.runner import control_values
from cells.core.specs import parse_spec
from validation.betse.spatial_active.refinement import completed_prior, digest

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_PATH = Path(__file__).with_name("two_task_protocol.json")


def protocol():
    return json.loads(PROTOCOL_PATH.read_text())


def baseline(rule):
    report = completed_prior(rule["prior_binding"], current_root=ROOT)
    assert report["completion_sha256"] == rule["prior_binding"]["completion_sha256"]
    prior = json.loads((Path(rule["prior_binding"]["root"]) / "registration.json").read_text())
    for name, expected in prior["sources_sha256"].items():
        assert digest(ROOT / name) == expected, name
    assert digest(ROOT / rule["template"]) == rule["template_sha256"]
    return report | dict(all_prior_sources_unchanged=len(prior["sources_sha256"]))


def cases(rule):
    return [
        dict(
            world_id=10000 + arm_index * 1000 + prep_index * 10 + 2 * location + timing,
            arm=arm,
            preparation=prep["id"],
            split=prep["split"],
            amplitude=prep["amplitude"],
            location=location,
            timing=timing,
        )
        for arm_index, arm in enumerate(rule["arms"])
        for prep_index, prep in enumerate(rule["preparations"])
        for location in (0, 1)
        for timing in (0, 1)
    ]


def definition(base, case, backend, rule):
    data = copy.deepcopy(base)
    if data["model"]["id"] != "betse_spatial_nak_kv1p5_dynamic_gj@1":
        raise ValueError("This assay requires the qualified dynamic-junction fixture")
    dt = data["execution"]["dt"]
    if dt != rule["dt_s"] or data["experiment"]["end_time"] != rule["steps"] * dt:
        raise ValueError("Assay clock differs from its frozen template")
    if case not in cases(rule):
        raise ValueError("Unregistered assay case")
    tissue = data["model"]["tissue"]
    owner, area = map(np.asarray, (tissue["cell_owner"], tissue["membrane_area"]))
    masks = [owner == identity - 1 for identity in rule["source_cell_ids"]]
    sizes = [area[mask].sum() for mask in masks]
    reference_area = min(sizes)
    block = np.zeros(len(owner))
    if case["arm"] != "no_cue":
        weights = (
            [0.5, 0.5]
            if case["arm"] == "timing_only"
            else [float(case["location"] == index) for index in (0, 1)]
        )
        for weight, mask, size in zip(weights, masks, sizes, strict=True):
            block[mask] = case["amplitude"] * weight * reference_area / size
    pulse = (
        rule["location_only_pulse_steps"]
        if case["arm"] == "location_only"
        else rule["timing_pulses_steps"][case["timing"]]
    )
    ones = np.ones(len(owner))
    junction = np.zeros(len(owner)) if case["arm"] == "disconnected" else ones
    changes = [
        dict(
            time=step * dt,
            pump=ones.tolist(),
            channel=(ones - block if pulse[0] <= step < pulse[1] else ones).tolist(),
            junction=junction.tolist(),
        )
        for step in rule["control_steps"]
    ]
    data["execution"]["backend"] = backend
    data["experiment"]["changes"] = changes
    data["experiment"]["observation_times"] = [step * dt for step in rule["readout_steps"]]
    return data


def batch(base, rows, backend, rule):
    return BatchSpec(
        tuple(
            WorldSpec(row["world_id"], parse_spec(definition(base, row, backend, rule)))
            for row in rows
        ),
        max_worlds=rule["batch_worlds"],
        max_padded_steps=rule["batch_worlds"] * (rule["steps"] + len(rule["control_steps"])),
        max_working_bytes=rule["resources"]["max_batch_working_bytes"],
    )


def voltage_features(result, rule):
    layout = result.final.layout
    reader = VoltageReadout(
        tuple(rule["readout_cell_ids"]),
        tuple(step * rule["dt_s"] for step in rule["readout_steps"]),
    )
    return reader.observe(
        result.observations.times,
        result.observations.membrane_voltage_V,
        cell_ids=np.asarray(layout.ids),
        cell_owner=np.asarray(layout.tissue_cell_owner),
        membrane_area=np.asarray(layout.tissue_membrane_area),
    )


def input_features(spec, steps, rule):
    """Declared baseline only: channel-availability samples, not tissue data."""
    control = control_values(spec, np.asarray(steps) * rule["dt_s"]).channel
    tissue = spec.to_dict()["model"]["tissue"]
    owner, area = map(np.asarray, (tissue["cell_owner"], tissue["membrane_area"]))
    return np.stack(
        [
            control[:, owner == identity - 1]
            @ (area[owner == identity - 1] / area[owner == identity - 1].sum())
            for identity in rule["readout_cell_ids"]
        ],
        axis=1,
    ).reshape(-1)


def folds(rows, arm):
    """Whole-input holdout plus disjoint cue strengths, never split windows."""
    if arm in ("location_only", "timing_only"):
        ignored = "timing" if arm == "location_only" else "location"
        unique = [r for r in rows if r[ignored] == 0]
        return [
            (
                "single_task",
                [r for r in unique if r["split"] == "calibration"],
                [r for r in unique if r["split"] == "heldout"],
            )
        ]
    return [
        (
            f"holdout_{location}_{timing}",
            [
                r
                for r in rows
                if r["split"] == "calibration"
                and (r["location"], r["timing"]) != (location, timing)
            ],
            [
                r
                for r in rows
                if r["split"] == "heldout" and (r["location"], r["timing"]) == (location, timing)
            ],
        )
        for location in (0, 1)
        for timing in (0, 1)
    ]


def evaluate(rows, features, *, margin, shuffle_seed=None):
    """Fit each frozen split independently; never inspect held-out targets to fit."""
    arms = {}
    rng = np.random.default_rng(shuffle_seed) if shuffle_seed is not None else None
    for arm in dict.fromkeys(r["arm"] for r in rows):
        selected = [r for r in rows if r["arm"] == arm]
        tasks = (
            ["location"]
            if arm == "location_only"
            else ["timing"]
            if arm == "timing_only"
            else ["location", "timing"]
        )
        tasks_report = {}
        for task in tasks:
            predictions, readers = [], []
            for name, training, testing in folds(selected, arm):
                train_x = np.stack([features[r["world_id"]] for r in training])
                train_y = np.asarray([r[task] for r in training])
                if rng is not None:
                    train_y = rng.permutation(train_y)
                reader = CentroidReader.fit(train_x, train_y, minimum_margin=margin)
                decoded = reader.read(np.stack([features[r["world_id"]] for r in testing]))
                readers.append(
                    dict(
                        fold=name,
                        calibration_world_ids=[r["world_id"] for r in training],
                        heldout_world_ids=[r["world_id"] for r in testing],
                        calibration_labels=train_y.tolist(),
                        reader=reader.to_dict(),
                        centroid_separation=decoded["separation"],
                    )
                )
                predictions.extend(
                    dict(
                        world_id=r["world_id"],
                        fold=name,
                        target=r[task],
                        prediction=int(decoded["prediction"][i]),
                        score=float(decoded["score"][i]),
                        resolved=bool(decoded["resolved"][i]),
                    )
                    for i, r in enumerate(testing)
                )
            metrics = score_predictions(
                [r["target"] for r in predictions],
                [r["prediction"] for r in predictions],
                [r["resolved"] for r in predictions],
            )
            tasks_report[task] = dict(metrics=metrics, predictions=predictions, calibration=readers)
        joint = None
        if len(tasks) == 2:
            a, b = (tasks_report[t]["predictions"] for t in tasks)
            assert [r["world_id"] for r in a] == [r["world_id"] for r in b]
            correct = [
                x["target"] == x["prediction"] and y["target"] == y["prediction"]
                for x, y in zip(a, b, strict=True)
            ]
            resolved = [x["resolved"] and y["resolved"] for x, y in zip(a, b, strict=True)]
            joint = dict(
                cases=len(a),
                forced_accuracy=float(np.mean(correct)),
                resolved_fraction=float(np.mean(resolved)),
                resolved_correct_fraction_of_all_cases=float(np.mean(np.array(correct) & resolved)),
            )
        arms[arm] = dict(tasks=tasks_report, joint=joint)
    return dict(
        arms=arms,
        feature_count=len(next(iter(features.values()))),
        shuffle_seed=shuffle_seed,
        outcome_is_not_an_acceptance_gate=True,
    )
