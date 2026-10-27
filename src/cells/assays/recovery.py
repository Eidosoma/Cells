"""Sampled return to a matched trajectory; an observer, never a repair mechanism."""

import numpy as np


def _outcome(times, inside, outside, intervention_s, release_s, hold_s):
    eligible = times >= intervention_s
    departures = np.flatnonzero(outside & eligible)
    ambiguous = ~inside & ~outside
    start, duration = None, 0.0
    if not len(departures):
        label = "unresolved_departure" if np.any(ambiguous & eligible) else "no_resolved_departure"
    elif outside[-1]:
        label = "outside_at_end"
    elif not inside[-1]:
        label = "unresolved_boundary"
    else:
        # Count only the uninterrupted final sequence of accepted observations.
        last_not_inside = np.flatnonzero(~inside)[-1]
        # An off-grid release cannot earn unobserved time toward the hold.
        release_sample = float(times[np.searchsorted(times, release_s)])
        start = max(float(times[last_not_inside + 1]), release_sample)
        duration = float(times[-1] - start)
        slack = 8 * np.finfo(float).eps * max(abs(times[-1]), hold_s)
        label = "returned_with_hold" if duration + slack >= hold_s else "insufficient_hold"
    return dict(
        classification=label,
        returned_with_hold=label == "returned_with_hold",
        first_resolved_departure_s=float(times[departures[0]]) if len(departures) else None,
        last_resolved_departure_s=float(times[departures[-1]]) if len(departures) else None,
        final_sample_inside=bool(inside[-1]),
        final_sample_outside=bool(outside[-1]),
        final_hold_start_s=start,
        sampled_hold_s=duration,
        ambiguous_samples=int(np.sum(ambiguous & eligible)),
    )


def sampled_recovery(
    times,
    actual,
    reference,
    *,
    bands,
    uncertainty,
    intervention_s,
    release_s,
    hold_s,
    max_gap_s,
):
    """Classify simultaneous return of all supplied measurements, without interpolation.

    Values are time-first arrays. Each named measurement has an absolute band
    and a strictly smaller numerical uncertainty in its own physical units.
    A return requires a resolved departure, followed by a final sampled hold
    after release. Off-grid events start eligibility at the first subsequent
    observation; no unobserved release interval earns hold time.
    Near-boundary samples cannot establish the hold. Agreement
    between observations, physiological health and biological repair are not
    inferred. Reference validity must be established by the calling experiment.
    """
    times = np.asarray(times, dtype=float)
    settings = (intervention_s, release_s, hold_s, max_gap_s)
    if (
        times.ndim != 1
        or len(times) < 2
        or not np.isfinite(times).all()
        or times[0] < 0
        or np.any(np.diff(times) <= 0)
        or any(type(v) not in (int, float) or not np.isfinite(v) for v in settings)
        or not times[0] <= intervention_s <= release_s <= times[-1]
        or hold_s <= 0
        or max_gap_s <= 0
    ):
        raise ValueError("Recovery needs finite increasing samples bracketing intervention/release")
    if np.max(np.diff(times)) > max_gap_s + 8 * np.finfo(float).eps * times[-1]:
        raise ValueError("Recovery observation gap exceeds its declared bound")
    if not actual or not set(actual) == set(reference) == set(bands) == set(uncertainty):
        raise ValueError("Recovery measurements, bands and uncertainty must have identical keys")
    all_inside, any_outside = np.ones(len(times), dtype=bool), np.zeros(len(times), dtype=bool)
    metrics = {}
    for name in actual:
        a, b = np.asarray(actual[name], dtype=float), np.asarray(reference[name], dtype=float)
        band, margin = bands[name], uncertainty[name]
        if (
            a.ndim < 1
            or a.shape != b.shape
            or a.shape[0] != len(times)
            or not a.size
            or not np.isfinite(a).all()
            or not np.isfinite(b).all()
            or type(band) not in (int, float)
            or type(margin) not in (int, float)
            or not np.isfinite((band, margin)).all()
            or not 0 <= margin < band
        ):
            raise ValueError("Recovery needs matching finite arrays and 0 <= uncertainty < band")
        error = np.max(np.abs(a - b).reshape(len(times), -1), axis=1)
        inside, outside = error + margin <= band, error - margin > band
        all_inside &= inside
        any_outside |= outside
        metrics[name] = dict(
            band=band,
            numerical_uncertainty=margin,
            peak_abs_difference=float(np.max(error[times >= intervention_s])),
            final_abs_difference=float(error[-1]),
            reference_drift_from_initial=float(np.max(np.abs(b - b[0]))),
            **_outcome(times, inside, outside, intervention_s, release_s, hold_s),
        )
    return dict(
        scope="Sampled return to matched reference; no continuous-time or physiological claim",
        samples=len(times),
        intervention_s=intervention_s,
        release_s=release_s,
        first_sample_at_or_after_intervention_s=float(
            times[np.searchsorted(times, intervention_s)]
        ),
        first_sample_at_or_after_release_s=float(times[np.searchsorted(times, release_s)]),
        required_hold_s=hold_s,
        maximum_allowed_gap_s=max_gap_s,
        maximum_observed_gap_s=float(np.max(np.diff(times))),
        metrics=metrics,
        **_outcome(times, all_inside, any_outside, intervention_s, release_s, hold_s),
    )
