"""Predeclared strength interpolation using external calibrated response curves.

The reader is an experimental analysis instrument, not new tissue physics.
Evaluation accepts observations only; its inferred segment position is never
supplied with the evaluation strength or selected using a held-out label.
"""

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from cells.assays.readout import CentroidReader, score_predictions
from cells.core.batch import BatchSpec, WorldSpec
from cells.core.specs import parse_spec
from validation.assays import two_task as assay
from validation.betse.spatial_active.refinement import digest

PROTOCOL_PATH = Path(__file__).with_name("template_readout_protocol.json")


def protocol():
    return json.loads(PROTOCOL_PATH.read_text())


def baseline(rule):
    report = assay.baseline(rule)
    assert digest(assay.ROOT / rule["source_protocol"]) == rule["source_protocol_sha256"]
    return report | dict(unchanged_physics_and_original_assay=True)


def physical_rule(rule):
    return assay.protocol() | {
        "preparations": rule["preparations"],
        "batch_worlds": rule["batch_worlds"],
        "resources": rule["resources"],
    }


def cases(rule):
    return [
        row | {"world_id": row["world_id"] + rule["world_id_offset"]}
        for row in assay.cases(physical_rule(rule))
    ]


def definition(base, row, backend, rule):
    if row not in cases(rule):
        raise ValueError("Unregistered template assay case")
    original_id = row["world_id"] - rule["world_id_offset"]
    raw = assay.definition(base, row | {"world_id": original_id}, backend, physical_rule(rule))
    raw["execution"]["dt"] = rule["dt_s"]
    return raw


def batch(base, rows, backend, rule):
    return BatchSpec(
        tuple(
            WorldSpec(row["world_id"], parse_spec(definition(base, row, backend, rule)))
            for row in rows
        ),
        max_worlds=rule["batch_worlds"],
        max_padded_steps=rule["batch_worlds"]
        * (round(rule["duration_s"] / rule["dt_s"]) + len(assay.protocol()["control_steps"])),
        max_working_bytes=rule["resources"]["max_batch_working_bytes"],
    )


def matrix(value):
    value = np.asarray(value, dtype=np.float64)
    if value.ndim != 2 or not all(value.shape) or not np.isfinite(value).all():
        raise ValueError("Expected a nonempty finite feature matrix")
    return value


@dataclass(frozen=True)
class TemplateReader:
    """Distances to fixed polylines, with a physical-unit abstention margin."""

    vertices: np.ndarray
    labels: np.ndarray
    minimum_margin: float

    def __post_init__(self):
        vertices = np.asarray(self.vertices, dtype=np.float64).copy()
        labels = np.asarray(self.labels).copy()
        if (
            vertices.ndim != 3
            or not all(vertices.shape)
            or vertices.shape[1] < 2
            or not np.isfinite(vertices).all()
            or labels.ndim != 2
            or labels.shape[0] != vertices.shape[0]
            or not labels.shape[1]
            or labels.dtype.kind not in "iu"
            or any(set(labels[:, i]) != {0, 1} for i in range(labels.shape[1]))
            or len(np.unique(labels, axis=0)) != len(labels)
            or not np.isfinite(self.minimum_margin)
            or self.minimum_margin <= 0
        ):
            raise ValueError("Finite curves, distinct binary labels and a positive margin required")
        vertices.setflags(write=False)
        labels.setflags(write=False)
        object.__setattr__(self, "vertices", vertices)
        object.__setattr__(self, "labels", labels)

    @classmethod
    def fit(cls, features, labels, strengths, *, minimum_margin):
        features = matrix(features)
        labels, strengths = np.asarray(labels), np.asarray(strengths, dtype=np.float64)
        if (
            labels.ndim != 2
            or labels.shape[0] != len(features)
            or labels.dtype.kind not in "iu"
            or strengths.shape != (len(features),)
            or not np.isfinite(strengths).all()
        ):
            raise ValueError("Invalid calibration grid")
        groups = np.unique(labels, axis=0)
        levels = np.unique(strengths)
        if len(levels) < 2:
            raise ValueError("Calibration needs at least two strengths")
        curves = []
        for group in groups:
            indices = np.flatnonzero(np.all(labels == group, axis=1))
            indices = indices[np.argsort(strengths[indices])]
            if not np.array_equal(strengths[indices], levels):
                raise ValueError("Calibration needs one sample per label and strength")
            curves.append(features[indices])
        return cls(np.stack(curves), groups, minimum_margin)

    def read(self, features):
        features = matrix(features)
        if features.shape[1] != self.vertices.shape[2]:
            raise ValueError("Reader feature support changed after calibration")
        start = self.vertices[:, :-1]
        direction = self.vertices[:, 1:] - start
        offset = features[:, None, None, :] - start
        denominator = np.sum(direction * direction, axis=-1)
        coordinate = np.divide(
            np.sum(offset * direction, axis=-1),
            denominator,
            out=np.zeros(offset.shape[:-1]),
            where=denominator > 0,
        ).clip(0, 1)
        residual = offset - coordinate[..., None] * direction
        segment_distance = np.linalg.norm(residual, axis=-1)
        segments = np.argmin(segment_distance, axis=-1)
        distances = np.take_along_axis(segment_distance, segments[..., None], axis=-1)[..., 0]
        positions = np.take_along_axis(coordinate, segments[..., None], axis=-1)[..., 0]
        score = np.stack(
            [
                (
                    distances[:, self.labels[:, task] == 0].min(axis=1)
                    - distances[:, self.labels[:, task] == 1].min(axis=1)
                )
                / 2
                for task in range(self.labels.shape[1])
            ],
            axis=1,
        )
        return dict(
            score=score,
            prediction=(score > 0).astype(np.int64),
            resolved=np.abs(score) > self.minimum_margin,
            curve_distances=distances,
            closest_segments=segments,
            segment_coordinates=positions,
        )

    def to_dict(self):
        return dict(
            vertices=self.vertices.tolist(),
            labels=self.labels.tolist(),
            minimum_margin=self.minimum_margin,
        )


def split(rows, arm):
    selected = [r for r in rows if r["arm"] == arm]
    tasks = ["location", "timing"]
    if arm in ("location_only", "timing_only"):
        task = arm.removesuffix("_only")
        ignored = "timing" if task == "location" else "location"
        selected = [r for r in selected if r[ignored] == 0]
        tasks = [task]
    training = [r for r in selected if r["split"] == "calibration"]
    testing = [r for r in selected if r["split"] == "heldout"]
    if (
        not training
        or not testing
        or not {r["amplitude"] for r in training}.isdisjoint(r["amplitude"] for r in testing)
    ):
        raise ValueError("Need disjoint calibration and evaluation strengths")
    return tasks, training, testing


def evaluate(rows, features, *, margin, centroid=False, shuffle_seed=None):
    """Fit calibration only; evaluation metadata is used solely for scoring."""
    if centroid and shuffle_seed is not None:
        raise ValueError("Curve-label shuffles are defined for template readers only")
    arms = {}
    rng = np.random.default_rng(shuffle_seed) if shuffle_seed is not None else None
    for arm in dict.fromkeys(r["arm"] for r in rows):
        tasks, training, testing = split(rows, arm)
        train_x = np.stack([features[r["world_id"]] for r in training])
        train_y = np.array([[r[t] for t in tasks] for r in training])
        test_x = np.stack([features[r["world_id"]] for r in testing])
        if centroid:
            readers = [
                CentroidReader.fit(train_x, train_y[:, i], minimum_margin=margin)
                for i in range(len(tasks))
            ]
            values = [reader.read(test_x) for reader in readers]
            decoded = {
                key: np.stack([value[key] for value in values], axis=1)
                for key in ("score", "prediction", "resolved")
            }
            fitted = dict(centroid_readers=[reader.to_dict() for reader in readers])
            projection = None
        else:
            reader = TemplateReader.fit(
                train_x,
                train_y,
                [r["amplitude"] for r in training],
                minimum_margin=margin,
            )
            if rng is not None:
                reader = TemplateReader(
                    reader.vertices, reader.labels[rng.permutation(len(reader.labels))], margin
                )
            decoded = reader.read(test_x)
            fitted = dict(template_reader=reader.to_dict())
            projection = [
                dict(
                    world_id=row["world_id"],
                    curve_distances=decoded["curve_distances"][i].tolist(),
                    closest_segments=decoded["closest_segments"][i].tolist(),
                    segment_coordinates=decoded["segment_coordinates"][i].tolist(),
                )
                for i, row in enumerate(testing)
            ]
        task_reports = {}
        for i, task in enumerate(tasks):
            predictions = [
                dict(
                    world_id=row["world_id"],
                    target=row[task],
                    prediction=int(decoded["prediction"][j, i]),
                    resolved=bool(decoded["resolved"][j, i]),
                    score=float(decoded["score"][j, i]),
                )
                for j, row in enumerate(testing)
            ]
            task_reports[task] = dict(
                predictions=predictions,
                metrics=score_predictions(
                    [r[task] for r in testing],
                    decoded["prediction"][:, i],
                    decoded["resolved"][:, i],
                ),
            )
        joint = None
        if len(tasks) == 2:
            target = np.array([[r[t] for t in tasks] for r in testing])
            correct = np.all(target == decoded["prediction"], axis=1)
            resolved = np.all(decoded["resolved"], axis=1)
            joint = dict(
                cases=len(testing),
                forced_accuracy=float(correct.mean()),
                resolved_fraction=float(resolved.mean()),
                resolved_correct_fraction_of_all_cases=float((correct & resolved).mean()),
                all_cases_correct_and_resolved=bool(np.all(correct & resolved)),
            )
        arms[arm] = dict(
            tasks=task_reports,
            joint=joint,
            calibration=dict(
                world_ids=[r["world_id"] for r in training],
                strengths=[r["amplitude"] for r in training],
                task_order=tasks,
                **fitted,
            ),
            projections=projection,
        )
    return dict(
        arms=arms,
        feature_count=len(next(iter(features.values()))),
        reader="balanced_centroid" if centroid else "calibrated_polyline",
        shuffle_seed=shuffle_seed,
        outcome_is_not_an_acceptance_gate=True,
    )
