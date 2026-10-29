"""Durable full-field ECM trajectory units, uncertainty and timestep comparisons."""

import argparse
import json
import time
import traceback
from pathlib import Path

import numpy as np

from validation.transport import owned_barrier_transient_fixtures as fixtures
from validation.transport import owned_barrier_transient_reference as reference


def sha(path):
    import hashlib

    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, allow_nan=False, default=lambda v: np.asarray(v).tolist())
        + "\n"
    )


def location(output, dataset, role, factor, chunk, *, pilot=False):
    prefix = "pilot-" if pilot else ""
    return output / "evidence" / dataset / f"{prefix}{role}-{factor}-chunk{chunk}"


def save(stem, record, arrays):
    stem.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(stem.with_suffix(".npz"), **arrays)
    write(stem.with_suffix(".json"), record | dict(arrays_sha256=sha(stem.with_suffix(".npz"))))


def load(stem):
    meta = read(stem.with_suffix(".json"))
    assert meta["status"] == "completed"
    assert sha(stem.with_suffix(".npz")) == meta["arrays_sha256"]
    with np.load(stem.with_suffix(".npz"), allow_pickle=False) as handle:
        arrays = {k: handle[k].copy() for k in handle.files}
    return meta, arrays


def input_raw(bundle, dataset):
    manifest = read(bundle / "manifest.json")
    path = bundle / "inputs" / (dataset + ".json")
    assert sha(path) == manifest["file_sha256"][str(path.relative_to(bundle))]
    return read(path)


def run_reference(bundle, output, dataset, factor, chunk, *, pilot=False):
    raw = input_raw(bundle, dataset)
    left, right, times = fixtures.window(raw, chunk, pilot=pilot)
    original_left = left
    prefix = None
    initial, dependency = None, None
    if chunk:
        previous = location(output, dataset, "reference", factor, chunk - 1)
        _, data = load(previous)
        initial = data["state_flat"][-1].copy()
        dependency = dict(
            path=str(previous.with_suffix(".json")), sha256=sha(previous.with_suffix(".json"))
        )
    elif not pilot:
        previous = location(output, dataset, "reference", factor, 0, pilot=True)
        if previous.with_suffix(".json").exists():
            meta, prefix = load(previous)
            assert meta["inputs"] == raw and meta["pilot_only"] is True
            initial = prefix["state_flat"][-1].copy()
            left = float(prefix["times_s"][-1])
            times = sorted({left, *(t for t in times if t >= left)})
            dependency = dict(
                kind="retained_pilot_prefix",
                path=str(previous.with_suffix(".json")),
                sha256=sha(previous.with_suffix(".json")),
            )
    began = time.monotonic()
    actual_times, states, proof = reference.integrate(
        raw, left, right, times, initial, factor=factor
    )
    if prefix is not None:
        np.testing.assert_array_equal(states[0], prefix["state_flat"][-1])
        actual_times = np.r_[prefix["times_s"][:-1], actual_times]
        states = np.concatenate((prefix["state_flat"][:-1], states))
    context = reference.scheduled.bind(raw)
    ledgers = [reference.conservation(context, vector) for vector in states]
    try:
        maxima = reference.assert_conservation(ledgers)
    except Exception as error:
        save(
            location(output, dataset, "reference-accounting-failure", factor, chunk, pilot=pilot),
            dict(status="failed", error=str(error), inputs=raw, conservation=ledgers),
            dict(times_s=actual_times, state_flat=states),
        )
        raise
    save(
        location(output, dataset, "reference", factor, chunk, pilot=pilot),
        dict(
            status="completed",
            inputs=raw,
            role="reference",
            factor=factor,
            chunk=chunk,
            original_full_horizon_s=raw["experiment"]["end_time"],
            window_s=[original_left, right],
            newly_integrated_window_s=[left, right],
            elapsed_seconds=time.monotonic() - began,
            proof=proof,
            conservation=ledgers,
            maximum_conservation_errors=maxima,
            continuation=dependency,
            pilot_only=pilot,
        ),
        dict(
            times_s=actual_times,
            state_flat=states,
            initial_flat=states[0],
            reference_shapes_json=np.asarray(json.dumps(context["shapes"])),
        ),
    )


def run_production(bundle, output, dataset, factor, chunk, *, pilot=False):
    from cells.core.grid import EventGrid
    from cells.core.schedule import control_values
    from cells.core.specs import parse_spec
    from cells.models.registry import get_model
    from cells.numerics.fixed_step import rk4_step

    raw = input_raw(bundle, dataset)
    raw["execution"]["dt"] /= factor
    spec = parse_spec(raw)
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    assert len(state) == dict(ionic=20, calcium=35, energy=39)[dataset.split("-")[0]]
    assert set(p.channel_laws[p.channel_active]) == set(range(56))
    left, right, requested = fixtures.window(raw, chunk, pilot=pilot)
    original_left = left
    prefix = None
    requested = np.asarray(requested)
    dependency = None
    if chunk:
        previous = location(output, dataset, "production", factor, chunk - 1)
        _, data = load(previous)
        state = model.STATE_TYPE(
            *(data["grid__" + key][-1].copy() for key in model.STATE_TYPE._fields)
        )
        for key in p._fields:
            np.testing.assert_array_equal(getattr(p, key), data["layout__" + key])
        dependency = dict(
            path=str(previous.with_suffix(".json")), sha256=sha(previous.with_suffix(".json"))
        )
    elif not pilot:
        previous = location(output, dataset, "production", factor, 0, pilot=True)
        if previous.with_suffix(".json").exists():
            meta, prefix = load(previous)
            assert meta["inputs"] == raw and meta["pilot_only"] is True
            state = model.STATE_TYPE(*(prefix["grid__" + key][-1].copy() for key in state._fields))
            for key in p._fields:
                np.testing.assert_array_equal(getattr(p, key), prefix["layout__" + key])
            left = float(prefix["integration_times_s"][-1])
            requested = np.unique(np.r_[requested, prefix["times_s"]])
            dependency = dict(
                kind="retained_pilot_prefix",
                path=str(previous.with_suffix(".json")),
                sha256=sha(previous.with_suffix(".json")),
            )
    assert abs(state.phase_clock_s[0] - left) <= p.phase_clock_atol_s
    grid = EventGrid(spec)
    full_times = np.asarray(list(grid))
    first, last = grid.exact_index(left), grid.exact_index(right)
    times = full_times[first : last + 1]
    table = control_values(spec, times[:-1])
    model.check_steps(spec, np.diff(times), table)
    values = [state]
    began = time.monotonic()
    try:
        for i, step in enumerate(np.diff(times)):
            u = type(table)(*(v[i] for v in table))

            def derivative(trial, u=u):
                slope = model.rhs(trial, u, p, p.active, xp=np)
                if not all(np.isfinite(v).all() for v in slope):
                    raise ValueError("Invalid complete parent RK stage; no step accepted")
                return slope

            state = rk4_step(derivative, state, step)
            values.append(state)
        history = model.STATE_TYPE(*(np.stack(v) for v in zip(*values, strict=True)))
        if prefix is not None:
            history = model.STATE_TYPE(
                *(
                    np.concatenate((prefix["grid__" + k][:-1], v))
                    for k, v in zip(history._fields, history, strict=True)
                )
            )
            times = np.r_[prefix["integration_times_s"][:-1], times]
        diagnostics = model.check_values(history, spec)
        np.testing.assert_allclose(
            history.phase_clock_s[:, 0], times, rtol=0, atol=p.phase_clock_atol_s
        )
    except Exception as error:
        save(
            location(output, dataset, "production-failure", factor, chunk, pilot=pilot),
            dict(status="failed", error=str(error), inputs=raw, window_s=[left, right]),
            dict(
                times_s=times[: len(values)],
                **{k: np.stack([getattr(v, k) for v in values]) for k in state._fields},
            ),
        )
        raise
    observed = model.observe_history(times, history, p, requested, spec)
    indexes = [int(np.flatnonzero(times == t)[0]) for t in requested]
    context = reference.scheduled.bind(raw)
    flat = np.stack(
        [
            reference.scheduled.flatten(
                context, model.STATE_TYPE(*(v[i] for v in history))._asdict()
            )
            for i in indexes
        ]
    )
    arrays = dict(
        times_s=requested,
        integration_times_s=times,
        state_flat=flat,
        initial_flat=flat[0],
        state_fields=np.asarray(state._fields),
    )
    for key in state._fields:
        np.testing.assert_array_equal(getattr(observed, key), getattr(history, key)[indexes])
        arrays[key] = getattr(history, key)[indexes]
        arrays["grid__" + key] = getattr(history, key)
    arrays.update({"obs__" + k: np.asarray(v) for k, v in vars(observed).items()})
    arrays.update({"layout__" + k: np.asarray(v) for k, v in zip(p._fields, p, strict=True)})
    closed = []
    if dataset.endswith("reseal"):
        for i, t in enumerate(requested):
            sample = model.STATE_TYPE(*(getattr(history, k)[indexes[i]] for k in state._fields))
            signal = model.signal_values(sample, p, xp=np)
            sodium = spec.model.species_ids.index("Na")
            mask = (signal.face_factor[sodium] == 0) & (p.barrier_union_factor[sodium] > 0)
            if np.any(mask & (sample.face_transferred[sodium] != 0)):
                closed.append(float(t))
    save(
        location(output, dataset, "production", factor, chunk, pilot=pilot),
        dict(
            status="completed",
            inputs=raw,
            role="production",
            factor=factor,
            chunk=chunk,
            original_full_horizon_s=raw["experiment"]["end_time"],
            window_s=[original_left, right],
            newly_integrated_window_s=[left, right],
            dt_s=spec.execution.dt,
            diagnostics=diagnostics,
            continuation=dependency,
            elapsed_seconds=time.monotonic() - began,
            pilot_only=pilot,
            closed_faces_with_preserved_history_s=closed,
        ),
        arrays,
    )


def stitched(output, dataset, role, factor, *, pilot=False):
    metas, arrays = [], []
    for chunk in [0] if pilot else range(4):
        meta, row = load(location(output, dataset, role, factor, chunk, pilot=pilot))
        if arrays:
            np.testing.assert_array_equal(row["state_flat"][0], arrays[-1]["state_flat"][-1])
            assert row["times_s"][0] == arrays[-1]["times_s"][-1]
        metas.append(meta)
        arrays.append(row)
    data = {
        k: np.concatenate([row[k] if i == 0 else row[k][1:] for i, row in enumerate(arrays)])
        for k in ["times_s", "state_flat"]
    }
    data["initial_flat"] = arrays[0]["initial_flat"]
    return metas, data


def comparison(bundle, output, dataset, *, pilot=False):
    raw = input_raw(bundle, dataset)
    context = reference.scheduled.bind(raw)
    _, coarse_ref = stitched(output, dataset, "reference", 1, pilot=pilot)
    ref_metas, exact = stitched(output, dataset, "reference", 2, pilot=pilot)
    expected = exact["state_flat"]
    floors = {
        k: np.full(s, 3e-25 if k.endswith("_C") else 1e-17 if k == "phase_clock_s" else 2e-11)
        for k, s in context["shapes"].items()
    }
    budget = reference.scheduled.flatten(context, floors) + 3e-9 * np.abs(expected)
    np.testing.assert_array_equal(coarse_ref["times_s"], exact["times_s"])
    delta = np.abs(coarse_ref["state_flat"] - expected)
    uncertainty = float(np.max(delta / budget, initial=0))
    assert uncertainty <= 0.1, ("reference uncertainty", uncertainty)
    selectors = {
        k: np.ones(s) if k == "face_transferred" else np.zeros(s)
        for k, s in context["shapes"].items()
    }
    face_mask = reference.scheduled.flatten(context, selectors).astype(bool)
    reference_face_uncertainty = float(np.max(delta[:, face_mask], initial=0))
    rows = []
    arrays = dict(
        times_s=exact["times_s"],
        reference_flat=expected,
        coarse_reference_flat=coarse_ref["state_flat"],
        budget=budget,
    )
    for factor in (1, 2):
        metas, actual = stitched(output, dataset, "production", factor, pilot=pilot)
        np.testing.assert_array_equal(actual["times_s"], exact["times_s"])
        np.testing.assert_array_equal(actual["initial_flat"], exact["initial_flat"])
        error = actual["state_flat"] - expected
        ratio = float(np.max(np.abs(error) / budget, initial=0))
        ledgers = [reference.conservation(context, v) for v in actual["state_flat"]]
        maximum = reference.assert_conservation(ledgers)
        face_error = float(np.max(np.abs(error[:, face_mask]), initial=0))
        rows.append(
            dict(
                factor=factor,
                dt_s=metas[0]["dt_s"],
                error_over_budget=ratio,
                max_absolute_error=float(np.max(np.abs(error), initial=0)),
                max_face_history_error_fmol=face_error,
                independent_conservation=maximum,
                closed_history_times_s=sorted(
                    {t for m in metas for t in m["closed_faces_with_preserved_history_s"]}
                ),
            )
        )
        arrays["production_flat_" + str(factor)] = actual["state_flat"]
        save(
            output
            / "evidence"
            / dataset
            / ("pilot-comparison-progress" if pilot else "comparison-progress"),
            dict(
                status="incomplete", refinements=rows, reference_uncertainty_over_budget=uncertainty
            ),
            arrays,
        )
        assert ratio <= 1, (dataset, factor, ratio)
        if dataset.endswith("reseal") and not pilot:
            assert rows[-1]["closed_history_times_s"], (
                "Closure never exercised actual nonzero face history"
            )
    high, low = [row["max_absolute_error"] for row in rows]
    assert low <= max(0.35 * high, 3e-13), (high, low)
    coarse, fine = [row["max_face_history_error_fmol"] for row in rows]
    floor = max(1e-20, 8 * reference_face_uncertainty)
    resolved = coarse > floor
    if resolved:
        assert fine <= 0.35 * coarse + 2 * reference_face_uncertainty + 1e-22, (
            coarse,
            fine,
            reference_face_uncertainty,
        )
    else:
        assert fine <= floor, (fine, floor)
    save(
        output / "evidence" / dataset / ("pilot-comparison" if pilot else "comparison"),
        dict(
            status="completed",
            pilot_only=pilot,
            original_full_horizon_s=raw["experiment"]["end_time"],
            compared_horizon_s=float(exact["times_s"][-1]),
            refinements=rows,
            reference_uncertainty_over_budget=uncertainty,
            reference_face_uncertainty_fmol=reference_face_uncertainty,
            reference_proofs=[m["proof"] for m in ref_metas],
            face_refinement_mode="resolved_reduction" if resolved else "precision_limited",
            all_observations_and_control_boundaries=not pilot,
            continuous_full_parent_clock=True,
            complete_state_fields=len(context["shapes"]),
            convergence_order_claim=False,
            native_solver_loop_parity=False,
            independent_biological_cases=0,
        ),
        arrays,
    )


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--bundle", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--dataset", choices=fixtures.DATASETS, required=True)
    p.add_argument("--role", choices=("reference", "production", "comparison"), required=True)
    p.add_argument("--factor", type=int, choices=(1, 2), default=1)
    p.add_argument("--chunk", type=int, choices=range(4), default=0)
    p.add_argument("--pilot", action="store_true")
    a = p.parse_args()
    try:
        if a.role == "reference":
            run_reference(a.bundle, a.output, a.dataset, a.factor, a.chunk, pilot=a.pilot)
        elif a.role == "production":
            run_production(a.bundle, a.output, a.dataset, a.factor, a.chunk, pilot=a.pilot)
        else:
            comparison(a.bundle, a.output, a.dataset, pilot=a.pilot)
    except Exception as error:
        stem = location(a.output, a.dataset, a.role + "-failure", a.factor, a.chunk, pilot=a.pilot)
        record = dict(status="failed", error=str(error), traceback=traceback.format_exc())
        if isinstance(error, reference.IntegrationFailure):
            save(stem, record, error.arrays)
        else:
            write(stem.with_suffix(".json"), record)
        raise


if __name__ == "__main__":
    main()
