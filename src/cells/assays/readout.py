"""Restricted voltage observations and a calibration-only binary reader.

These are external analysis instruments, not energetic or causal consumers in
the tissue. Neither routine receives task labels or controls while observing.
"""

from dataclasses import dataclass

import numpy as np


def _matrix(value):
    value = np.asarray(value, dtype=np.float64)
    if value.ndim != 2 or not all(value.shape) or not np.isfinite(value).all():
        raise ValueError("Expected a nonempty finite feature matrix")
    return value


@dataclass(frozen=True)
class VoltageReadout:
    """Area-weighted membrane voltage at named cells and accepted times.

    Only the explicitly supplied membrane voltage is visible. Bookkeeping,
    intervention schedules, labels, world IDs and archived traces are excluded.
    The returned feature order is time first, then the declared cell IDs.
    """

    cell_ids: tuple[int, ...]
    times_s: tuple[float, ...]

    def __post_init__(self):
        if (
            not self.cell_ids
            or any(type(v) is not int or v < 1 for v in self.cell_ids)
            or len(set(self.cell_ids)) != len(self.cell_ids)
            or not self.times_s
            or any(type(t) not in (int, float) for t in self.times_s)
            or not np.isfinite(self.times_s).all()
            or self.times_s[0] < 0
            or np.any(np.diff(self.times_s) <= 0)
        ):
            raise ValueError("Readout needs distinct positive cell IDs and increasing times")

    def observe(self, times, membrane_voltage_V, *, cell_ids, cell_owner, membrane_area):
        times = np.asarray(times)
        voltage = _matrix(membrane_voltage_V)
        ids, owner, area = map(np.asarray, (cell_ids, cell_owner, membrane_area))
        if (
            times.ndim != 1
            or len(times) != len(voltage)
            or not np.isfinite(times).all()
            or np.any(np.diff(times) <= 0)
            or ids.ndim != 1
            or ids.dtype.kind not in "iu"
            or len(set(ids.tolist())) != len(ids)
            or np.any(ids < 1)
            or owner.shape != (voltage.shape[1],)
            or owner.dtype.kind not in "iu"
            or np.any((owner < 0) | (owner >= len(ids)))
            or area.shape != owner.shape
            or not np.isfinite(area).all()
            or np.any(area <= 0)
        ):
            raise ValueError("Invalid voltage sampling or membrane ownership")
        indices = np.searchsorted(times, self.times_s)
        if np.any(indices >= len(times)) or not np.array_equal(times[indices], self.times_s):
            raise ValueError("Readout requires exact accepted samples; no interpolation")
        columns = []
        for identity in self.cell_ids:
            slots = np.flatnonzero(ids == identity)
            if len(slots) != 1 or not np.any(owner == slots[0]):
                raise ValueError("Readout cell is absent or has no membrane")
            mask = owner == slots[0]
            weights = area[mask] / area[mask].sum()
            columns.append(voltage[indices][:, mask] @ weights)
        result = np.stack(columns, axis=1).reshape(-1)
        result.setflags(write=False)
        return result


@dataclass(frozen=True)
class CentroidReader:
    """Two class means, with no feature selection or fitted hyperparameters.

    Scores are signed distances to the class-mean bisector in input units.
    The declared margin marks unresolved decisions; forced predictions are
    retained separately so abstentions cannot inflate reported accuracy.
    """

    centers: np.ndarray
    minimum_margin: float

    def __post_init__(self):
        centers = _matrix(self.centers).copy()
        if (
            centers.shape[0] != 2
            or not np.isfinite(self.minimum_margin)
            or self.minimum_margin <= 0
        ):
            raise ValueError("Binary centers and a positive finite margin required")
        centers.setflags(write=False)
        object.__setattr__(self, "centers", centers)

    @classmethod
    def fit(cls, features, labels, *, minimum_margin):
        features = _matrix(features)
        labels = np.asarray(labels)
        if (
            labels.shape != (len(features),)
            or labels.dtype.kind not in "iu"
            or set(labels) != {0, 1}
        ):
            raise ValueError("Calibration requires both binary classes")
        return cls(np.stack([features[labels == k].mean(axis=0) for k in (0, 1)]), minimum_margin)

    def read(self, features):
        features = _matrix(features)
        if features.shape[1] != self.centers.shape[1]:
            raise ValueError("Reader feature support changed after calibration")
        direction = self.centers[1] - self.centers[0]
        separation = float(np.linalg.norm(direction))
        score = (
            (features - self.centers.mean(axis=0)) @ (direction / separation)
            if separation > 0
            else np.zeros(len(features))
        )
        prediction = (score > 0).astype(np.int64)
        resolved = (abs(score) > self.minimum_margin) & (separation > 2 * self.minimum_margin)
        return dict(score=score, prediction=prediction, resolved=resolved, separation=separation)

    def to_dict(self):
        return dict(centers=self.centers.tolist(), minimum_margin=self.minimum_margin)


def score_predictions(labels, predictions, resolved):
    """Report every held-out case, including ties and unresolved decisions."""
    labels, predictions, resolved = map(np.asarray, (labels, predictions, resolved))
    if (
        labels.ndim != 1
        or not len(labels)
        or predictions.shape != labels.shape
        or resolved.shape != labels.shape
        or not np.isin(labels, (0, 1)).all()
        or not np.isin(predictions, (0, 1)).all()
        or resolved.dtype != np.bool_
    ):
        raise ValueError("Invalid binary predictions")
    correct = predictions == labels
    confusion = np.zeros((2, 2), dtype=np.int64)
    np.add.at(confusion, (labels, predictions), 1)
    return dict(
        cases=len(labels),
        forced_accuracy=float(correct.mean()),
        resolved_fraction=float(resolved.mean()),
        resolved_correct_fraction_of_all_cases=float((correct & resolved).mean()),
        accuracy_on_resolved=float(correct[resolved].mean()) if resolved.any() else None,
        confusion_true_by_predicted=confusion.tolist(),
    )
