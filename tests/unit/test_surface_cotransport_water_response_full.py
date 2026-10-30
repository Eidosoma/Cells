"""Longer physical response checks; launched explicitly in guarded CPU groups.

The full half-second trajectories keep every accepted state and compare an
independent adaptive solver. Manufactured controls are paired numerical cases,
not independent biological observations. GPU qualification is separate.
"""

import hashlib
import json
import os
from pathlib import Path
from time import perf_counter
from types import SimpleNamespace

import jax
import numpy as np
import pytest

from cells.core import runner
from cells.core.grid import EventGrid
from cells.core.runner import run
from cells.core.schedule import control_values
from cells.core.specs import parse_spec
from cells.core.windows import WindowPolicy, iter_windows, merge_diagnostics
from cells.io import load_snapshot, write_snapshot
from cells.models import surface_cotransport_water as model
from cells.numerics.fixed_step import rk4_checked_step
from validation.tissue import cotransport_material_coordinates as material
from validation.tissue import surface_cotransport_water_reference as reference
from validation.tissue import surface_cotransport_water_response as panel


def root():
    path = os.environ.get("CELLS_COMPONENT_EVIDENCE")
    if not path:
        raise RuntimeError("Run this panel through a guarded worker with persistent evidence")
    target = Path(path) / "cpu"
    target.mkdir(parents=True, exist_ok=True)
    return target


def write(name, value, arrays=None):
    target = root() / name
    target.with_suffix(".json").write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    if arrays is not None:
        with target.with_suffix(".npz").open("xb") as stream:
            np.savez_compressed(stream, **arrays)


def saved(name):
    report = json.loads((root() / (name + ".json")).read_text())
    with np.load(root() / (name + ".npz"), allow_pickle=False) as values:
        arrays = {k: v.copy() for k, v in values.items()}
    return report, arrays


def worker_identity():
    fields = Path("/proc/self/stat").read_text().rsplit(")", 1)[1].split()
    return dict(pid=os.getpid(), process_start_ticks=int(fields[19]))


def run_captured(spec, name, monkeypatch, *, checkpoint=None, window_steps=None):
    """Save the complete proposed history before the unchanged acceptance checks.

    The ordinary runner remains authoritative. This test-local observation hook
    never returns a rejected trajectory or converts a failure into acceptance.
    Domain rejection before history analysis retains its original exception.
    """
    original = runner._analyse_segment
    window_index = 0

    def capture(spec, parent, times, arrays, final_state, layout, requested):
        nonlocal window_index
        label = name if window_steps is None else f"{name}-window-{window_index:06d}"
        window_index += 1
        write(
            label + "-proposed-history",
            dict(
                status="proposed_not_yet_accepted",
                inputs=spec.to_dict(),
                parent_clock=dict(
                    time=parent.time,
                    step_index=parent.step_index,
                    event_index=parent.event_index,
                ),
                complete_fields=list(model.STATE_TYPE._fields),
                acceptance_checks_unchanged=True,
            ),
            dict(
                proposed_times=times,
                **dict(zip(model.STATE_TYPE._fields, arrays, strict=True)),
                **{"layout__" + k: np.asarray(v) for k, v in layout._asdict().items()},
            ),
        )
        try:
            value = original(spec, parent, times, arrays, final_state, layout, requested)
        except Exception as error:
            write(
                label + "-rejection",
                dict(
                    status="rejected",
                    error_type=type(error).__name__,
                    error=str(error),
                    proposed_history=label + "-proposed-history.npz",
                    accepted_result_returned=False,
                    automatic_retry=False,
                ),
            )
            raise
        if window_steps is not None:
            write(
                label + "-acceptance",
                dict(
                    status="accepted_by_original_checks",
                    start_time_s=float(times[0]),
                    end_time_s=float(times[-1]),
                    diagnostics=value[-1],
                    proposed_history=label + "-proposed-history.npz",
                ),
            )
        return value

    with monkeypatch.context() as patch:
        patch.setattr(runner, "_analyse_segment", capture)
        if window_steps is None:
            return run(spec, checkpoint=checkpoint)
        # Bound the extra host history/assembly separately from the ordinary
        # window working storage. The process guard still covers total memory.
        state, _ = model.initial_values(spec)
        rows = len(EventGrid(spec))
        host_estimate = 3 * rows * (8 + sum(np.asarray(v).nbytes for v in state))
        if host_estimate > spec.execution.max_trace_bytes:
            raise ValueError("Complete host history exceeds the response capture budget")
        parts = list(iter_windows(spec, WindowPolicy(window_steps, "full"), checkpoint))
    merge_started = perf_counter()
    times = np.concatenate([p.times[int(i > 0) :] for i, p in enumerate(parts)])
    history = model.STATE_TYPE(
        *(
            np.concatenate([getattr(p.history, field)[int(i > 0) :] for i, p in enumerate(parts)])
            for field in model.STATE_TYPE._fields
        )
    )
    observations = SimpleNamespace(
        **{
            field: np.concatenate([getattr(p.observations, field) for p in parts])
            for field in vars(parts[0].observations)
        }
    )
    requested = np.asarray(spec.experiment.observation_times)
    np.testing.assert_array_equal(observations.times, requested[requested >= times[0]])
    diagnostics, timings = {}, {}
    for part in parts:
        merge_diagnostics(diagnostics, part.diagnostics)
        for key, value in part.timings.items():
            timings[key] = timings.get(key, 0.0) + value
    # This also covers monotonic ledgers across all concatenated windows.
    merge_diagnostics(diagnostics, model.check_values(history, spec))
    timings["capture_merge_and_full_check_seconds"] = perf_counter() - merge_started
    for value in (times, *history, *vars(observations).values()):
        value.setflags(write=False)
    return runner.RunResult(
        spec,
        parts[-1].final,
        parts[0].start_step,
        times,
        history,
        observations,
        timings,
        diagnostics,
    )


def field_errors(c, actual, expected):
    return {
        name: float(np.max(np.abs(value), initial=0))
        for name, value in reference.unpack(c, actual - expected).items()
    }


def state_comparison(c, actual, expected, *, times=None, atol=2e-11, charge_atol=3e-25, rtol=3e-9):
    """Describe every field before enforcing the original fixed error budgets.

    A completed comparison can still fail qualification. Empty physical fields
    are recorded explicitly; mismatched shapes never receive broadcasting credit.
    """
    actual, expected = np.asarray(actual), np.asarray(expected)
    width = sum(int(np.prod(shape)) for shape in c["shapes"].values())
    if actual.shape != expected.shape or actual.ndim not in (1, 2) or actual.shape[-1] != width:
        raise ValueError("Require matching complete flat states or observation histories")
    if times is not None:
        times = np.asarray(times)
        if actual.ndim != 2 or times.shape != actual.shape[:1] or not np.isfinite(times).all():
            raise ValueError("Comparison times must match the complete observation axis")
    if not (
        np.isfinite([atol, charge_atol, rtol]).all() and min(atol, charge_atol) > 0 and rtol >= 0
    ):
        raise ValueError("Require finite positive absolute budgets and nonnegative relative budget")
    absolute = reference.flatten(
        c,
        {
            k: np.full(shape, charge_atol if k.endswith("_C") else atol)
            for k, shape in c["shapes"].items()
        },
    )
    with np.errstate(over="ignore", invalid="ignore"):
        errors = np.abs(actual - expected)
        budgets = absolute + rtol * np.abs(expected)
        ratios = errors / budgets
    fields = {}
    arrays = [reference.unpack(c, value) for value in (actual, expected, errors, budgets, ratios)]
    for name in c["shapes"]:
        a, e, error, budget, ratio = (value[name] for value in arrays)
        finite = bool(all(np.isfinite(value).all() for value in (a, e, error, budget, ratio)))
        field = dict(
            shape=list(a.shape),
            compared_values=int(a.size),
            finite=finite,
            max_error_over_budget=float(np.max(ratio, initial=0)) if finite else None,
            violating_values=int(np.count_nonzero((ratio > 1) | ~np.isfinite(ratio))),
            worst=None,
        )
        if a.size and finite:
            index = tuple(int(i) for i in np.unravel_index(np.argmax(ratio), ratio.shape))
            field["worst"] = dict(
                index=list(index),
                time_s=None if times is None else float(times[index[0]]),
                actual=float(a[index]),
                expected=float(e[index]),
                absolute_error=float(error[index]),
                budget=float(budget[index]),
                error_over_budget=float(ratio[index]),
            )
        fields[name] = field
    finite = all(field["finite"] for field in fields.values())
    maximum = float(np.max(ratios, initial=0)) if finite else None
    failed = [
        name for name, field in fields.items() if not field["finite"] or field["violating_values"]
    ]
    return dict(
        status="passed" if not failed else "failed",
        finite=finite,
        max_error_over_budget=maximum,
        failed_fields=failed,
        budgets=dict(atol=atol, charge_atol=charge_atol, rtol=rtol),
        fields=fields,
        scope="Fixed-budget state comparison only; no complete trajectory qualification",
    )


def score(
    c, actual, expected, *, times=None, evidence_name=None, atol=2e-11, charge_atol=3e-25, rtol=3e-9
):
    comparison = state_comparison(
        c, actual, expected, times=times, atol=atol, charge_atol=charge_atol, rtol=rtol
    )
    if evidence_name is not None:
        write(evidence_name, comparison)
    assert comparison["finite"], comparison["failed_fields"]
    result = comparison["max_error_over_budget"]
    assert result <= 1, result
    return result


def independent(arm, raw, *, refinement=1):
    name = f"response-reference-{arm}-r{refinement}"
    write(name, dict(status="running", inputs=raw, refinement=refinement))
    try:
        result = reference.integrate(raw, refinement=refinement, max_step_s=1e-3)
    except BaseException as error:
        detail = getattr(error, "diagnostics", None)
        write(
            name,
            dict(
                status="failed",
                inputs=raw,
                refinement=refinement,
                error_type=type(error).__name__,
                error=str(error),
                details=detail,
            ),
        )
        raise
    write(
        name,
        {k: v for k, v in result.items() if not isinstance(v, np.ndarray)}
        | dict(status="passed", inputs=raw),
        {k: v for k, v in result.items() if isinstance(v, np.ndarray)},
    )
    return result


def test_compiled_empty_channel_step_and_strict_rejection():
    raw = panel.definition()
    spec = parse_spec(raw)
    state, layout = model.initial_values(spec)
    table = control_values(spec, [0.0])
    held = type(table)(*(v[0] for v in table))
    dt = panel.DT
    slopes = []
    for scale in (0, 0.5, 0.5, 1.0):
        trial = (
            state
            if not slopes
            else model.STATE_TYPE(
                *(a + dt * scale * b for a, b in zip(state, slopes[-1], strict=True))
            )
        )
        slopes.append(model.rhs(trial, held, layout, layout.active, xp=np))
    expected = model.STATE_TYPE(
        *(
            a + dt * (b + 2 * c + 2 * d + e) / 6
            for a, b, c, d, e in zip(state, *slopes, strict=True)
        )
    )
    step = jax.jit(
        lambda y, h, u, p: rk4_checked_step(model.rhs, model.domain_valid, y, h, u, p, p.active)
    )
    actual, valid = step(state, dt, held, layout)
    assert bool(valid)
    c = reference.bind(raw)
    error = score(
        c,
        reference.flatten(c, actual._asdict()),
        reference.flatten(c, expected._asdict()),
        atol=3e-12,
        charge_atol=3e-23,
        rtol=3e-10,
    )
    diagnostics = model.check_values(model.STATE_TYPE(*(np.asarray(v) for v in actual)), spec)
    broken = state.energy_amount_increment_fmol.copy()
    broken[0, 0] = -layout.energy_initial_amount_fmol[0, 0]
    bad = state._replace(energy_amount_increment_fmol=broken)
    stopped, accepted = step(bad, dt, held, layout)
    assert not bool(accepted)
    for a, b in zip(stopped, bad, strict=True):
        np.testing.assert_array_equal(a, b)
    write(
        "response-compiled-step",
        dict(
            status="passed",
            inputs=raw,
            max_error_over_budget=error,
            diagnostics=diagnostics,
            state_fields=31,
            rejected_exhausted_pool=True,
            scope="One ordinary RK4 step and strict invalid-state rejection; no settling claim",
        ),
        dict(
            **{"actual_" + k: v for k, v in actual._asdict().items()},
            **{"expected_" + k: v for k, v in expected._asdict().items()},
        ),
    )


def qualify_complete_response(
    arm,
    raw,
    monkeypatch,
    *,
    window_steps=None,
    expected=None,
    reference_coordinates="global",
    reference_material_coordinates="full",
    local_stop_time_s=None,
):
    assert jax.default_backend() == "cpu" and jax.config.x64_enabled
    assert reference_coordinates == "global" or expected is not None
    assert reference_material_coordinates in ("full", "transport_ledgers")
    assert reference_material_coordinates == "full" or expected is not None
    write(
        "response-trajectory-" + arm,
        dict(status="running", inputs=raw, duration=panel.duration_inputs(raw)),
    )
    value = run_captured(
        parse_spec(raw), "response-trajectory-" + arm, monkeypatch, window_steps=window_steps
    )
    observations = vars(value.observations)
    c = reference.bind(raw)
    actual = reference.flatten(c, observations)
    phi = np.c_[observations["cell_potential_V"], observations["extracellular_potential_V"]]
    report = dict(
        status="captured",
        inputs=raw,
        duration=panel.duration_inputs(raw),
        diagnostics=value.diagnostics,
        timings=value.timings,
        complete_fields=list(model.STATE_TYPE._fields),
        accepted_steps=len(value.times) - 1,
        worker=worker_identity(),
        window_steps=window_steps,
        reference_coordinates=reference_coordinates,
        reference_material_coordinates=reference_material_coordinates,
        local_refinement_stop_time_s=local_stop_time_s,
        scope="Closed manufactured response; no source trajectory or biological fit",
    )
    write(
        "response-trajectory-" + arm,
        report,
        dict(
            state=actual, potential_V=phi, **{"observed_" + k: v for k, v in observations.items()}
        ),
    )
    write(
        "response-history-" + arm,
        dict(status="captured", complete_fields=31),
        dict(accepted_times=value.times, **value.history._asdict()),
    )
    write_snapshot(root() / ("response-final-" + arm), value.spec, value.final)
    if arm == "supply_recovery":
        checkpoint = value.checkpoint_at(panel.INTERVENTION_TIME)
        write_snapshot(root() / "response-restart", value.spec, checkpoint)
    if expected is None:
        expected = independent(arm, raw)
    try:
        report["state_comparison"] = "response-state-comparison-" + arm + ".json"
        report["max_error_over_budget"] = score(
            c,
            actual,
            expected["state"],
            times=observations["times"],
            evidence_name="response-state-comparison-" + arm,
        )
        np.testing.assert_allclose(phi, expected["potential_V"], atol=2e-8, rtol=3e-9)
        assert value.diagnostics["max_energy_balance_error_pJ"] <= 2e-8
        assert value.diagnostics["max_pool_internal_transfer_error_pJ"] <= 2e-8
        assert value.diagnostics["max_global_water_balance_error_pL"] <= 2e-12
        # Report late physical rates; no 'steady state' label follows from time alone.
        controls = control_values(value.spec, [panel.END_TIME])
        held = type(controls)(*(v[0] for v in controls))
        late = model.readouts(value.final.state, held, value.final.layout, xp=np)
        report["late_rates"] = dict(
            atp_fmol_s=float(late.derivative.energy_amount_increment_fmol[0, 0]),
            cell_volume_pL_s=float(late.derivative.volume_increment_pL[0]),
            cotransport_cycles_fmol_s=late.derivative.cotransport_cycles_fmol.tolist(),
        )
    except BaseException as error:
        write("response-trajectory-" + arm, report | dict(status="failed", error=str(error)))
        raise
    write("response-trajectory-" + arm, report | dict(status="passed"))


@pytest.mark.parametrize("arm", panel.ARMS)
def test_complete_response_against_independent_reference(arm, monkeypatch):
    qualify_complete_response(arm, panel.definition(arm), monkeypatch)


def qualify_recovery_refinement(monkeypatch, *, tighter=None, local_stop_time_s=None):
    arm = "supply_recovery"
    first, arrays = saved("response-trajectory-" + arm)
    assert first["status"] == "passed"
    raw, coarse = first["inputs"], arrays["state"]
    stored_stop = first.get("local_refinement_stop_time_s")
    if stored_stop is not None:
        assert local_stop_time_s is None or local_stop_time_s == stored_stop
        local_stop_time_s = stored_stop
    c = reference.bind(raw)
    _, reference1 = saved("response-reference-" + arm + "-r1")
    if tighter is None:
        assert first.get("reference_coordinates", "global") == "global"
        tighter = independent(arm, raw, refinement=2)
    stability = score(
        c,
        reference1["state"],
        tighter["state"],
        times=raw["experiment"]["observation_times"],
        evidence_name="response-reference-stability",
        atol=3e-14,
        charge_atol=3e-28,
        rtol=3e-11,
    )
    errors = [field_errors(c, coarse, tighter["state"])]
    scores = [score(c, coarse, tighter["state"])]
    for factor in (2, 4):
        local = raw["execution"].get("refinement_times", [])
        stop = 20001 * panel.DT if local_stop_time_s is None else local_stop_time_s
        refined_raw = (
            panel.refined_recovery_definition(
                [panel.INTERVENTION_TIME, *local, stop], factor=factor, stop_time_s=stop
            )
            if local
            else panel.definition(arm, dt=panel.DT / factor)
        )
        value = run_captured(
            parse_spec(refined_raw),
            f"response-refined-r{factor}",
            monkeypatch,
            window_steps=first.get("window_steps"),
        )
        actual = reference.flatten(c, vars(value.observations))
        phi = np.c_[
            value.observations.cell_potential_V, value.observations.extracellular_potential_V
        ]
        write(
            f"response-refined-r{factor}",
            dict(
                status="captured",
                inputs=refined_raw,
                diagnostics=value.diagnostics,
                timings=value.timings,
            ),
            dict(state=actual, potential_V=phi, signed_error=actual - tighter["state"]),
        )
        write(
            f"response-refined-history-r{factor}",
            dict(status="captured", complete_fields=31, inputs=refined_raw),
            dict(accepted_times=value.times, **value.history._asdict()),
        )
        errors.append(field_errors(c, actual, tighter["state"]))
        scores.append(
            score(
                c,
                actual,
                tighter["state"],
                times=value.observations.times,
                evidence_name=f"response-refined-r{factor}-state-comparison",
            )
        )
        np.testing.assert_allclose(phi, tighter["potential_V"], atol=2e-8, rtol=3e-9)
    report = dict(
        status="captured",
        steps_s=[panel.DT / f for f in (1, 2, 4)],
        reference_stability_over_budget=stability,
        state_errors_by_field=errors,
        error_over_budget=scores,
        convergence_observables={
            "amount_increment": dict(unit="fmol", roundoff_floor=3e-13),
            "energy_amount_increment_fmol": dict(unit="fmol", roundoff_floor=3e-13),
            "volume_increment_pL": dict(unit="pL", roundoff_floor=3e-13),
        },
        all_31_fields_pass_accuracy_budget=True,
    )
    write("response-refinement", report)
    for name, settings in report["convergence_observables"].items():
        assert errors[-1][name] <= max(settings["roundoff_floor"], 0.2 * errors[0][name]), (
            name,
            errors,
        )
    write("response-refinement", report | dict(status="passed"))


def test_recovery_refinement_and_reference_stability(monkeypatch):
    qualify_recovery_refinement(monkeypatch)


def admit_reference_material_coordinates(context, report, arrays, declared):
    """Check saved coordinate identity without altering or accepting a trajectory.

    Legacy full-coordinate receipts remain readable. A reduced reference must
    explicitly declare its solver dimension and charge source and retain its
    original start. All complete states must exactly decode from their saved
    ledgers. Accuracy, physical domain and refinement gates remain separate.
    """
    if declared not in ("full", "transport_ledgers"):
        raise ValueError("Unknown declared reference material coordinates")
    if report.get("material_coordinates", "full") != declared:
        raise ValueError("Saved reference material coordinates differ from the declaration")
    initial = reference.initial(context)
    codec = material.bind(context) if declared == "transport_ledgers" else None
    expected = dict(
        integrated_scalar_count=initial.size if codec is None else codec.size,
        complete_scalar_count=initial.size,
        derived_fields=[] if codec is None else list(material.BULK_FIELDS),
        field_charge_source="bulk_increments"
        if codec is None
        else "electrogenic_transport_ledgers",
    )
    for name, value in expected.items():
        if (codec is not None or name in report) and report.get(name) != value:
            raise ValueError("Invalid reference material metadata: " + name)
    if codec is not None:
        if report.get("fresh_original_start") is not True:
            raise ValueError("Transport-ledger references require a fresh original start")
        np.testing.assert_array_equal(arrays["initial_state"], initial)
        np.testing.assert_array_equal(arrays["state"][0], initial)
        np.testing.assert_array_equal(arrays["final_state"], arrays["state"][-1])
        for state in (arrays["initial_state"], arrays["final_state"], *arrays["state"]):
            codec.pack(state)  # Refuse an inconsistent state; never repair it.


def declared_recovery_reference(refinement):
    declaration = json.loads(Path(os.environ["CELLS_RECOVERY_GRID_INPUTS"]).read_text())
    raw = panel.refined_recovery_definition(
        declaration["local_times_s"], stop_time_s=declaration.get("local_stop_time_s")
    )
    report, arrays = saved(f"response-reference-supply_recovery-r{refinement}")
    assert report["status"] == "passed" and report["inputs"] == raw
    assert report["segment_coordinates"] == "local_delta"
    assert report["production_imports_denied"] is True
    assert report["refinement"] == refinement
    scale = declaration.get("reference_tolerance_scale", 1.0)
    assert report.get("tolerance_scale", 1.0) == scale
    assert report["rtol"] == (2e-11 / refinement) * scale
    assert report["amount_volume_energy_atol"] == (2e-14 / refinement) * scale
    assert report["electrode_charge_atol_C"] == (1e-29 / refinement) * scale
    np.testing.assert_array_equal(report["times"], raw["experiment"]["observation_times"])
    count = len(raw["experiment"]["observation_times"])
    context = reference.bind(raw)
    assert arrays["state"].shape == (count, reference.initial(context).size)
    assert arrays["potential_V"].shape == (count, len(context["vi"]) + len(context["vo"]))
    assert np.isfinite(arrays["state"]).all() and np.isfinite(arrays["potential_V"]).all()
    admit_reference_material_coordinates(
        context, report, arrays, declaration.get("reference_material_coordinates", "full")
    )
    return raw, arrays


def test_full_recovery_with_declared_local_resolution(monkeypatch):
    """A fresh full trajectory; the local diagnostic parent is never loaded."""
    raw, expected = declared_recovery_reference(1)
    tighter_raw, tighter = declared_recovery_reference(2)
    assert raw == tighter_raw
    # Reference completion alone does not establish accuracy. Check the same
    # strict stability budget before spending time on a production trajectory.
    score(
        reference.bind(raw),
        expected["state"],
        tighter["state"],
        times=raw["experiment"]["observation_times"],
        evidence_name="response-reference-stability-before-trajectory",
        atol=3e-14,
        charge_atol=3e-28,
        rtol=3e-11,
    )
    declaration = json.loads(Path(os.environ["CELLS_RECOVERY_GRID_INPUTS"]).read_text())
    qualify_complete_response(
        "supply_recovery",
        raw,
        monkeypatch,
        window_steps=256,
        expected=expected,
        reference_coordinates="local_delta",
        reference_material_coordinates=declaration.get("reference_material_coordinates", "full"),
        local_stop_time_s=declaration.get("local_stop_time_s"),
    )


def test_declared_recovery_refinement_against_fresh_references(monkeypatch):
    raw, _ = declared_recovery_reference(1)
    refined_raw, tighter = declared_recovery_reference(2)
    baseline, _ = saved("response-trajectory-supply_recovery")
    assert raw == refined_raw == baseline["inputs"]
    assert baseline["reference_coordinates"] == "local_delta" and baseline["window_steps"] == 256
    declaration = json.loads(Path(os.environ["CELLS_RECOVERY_GRID_INPUTS"]).read_text())
    assert baseline.get("reference_material_coordinates", "full") == declaration.get(
        "reference_material_coordinates", "full"
    )
    qualify_recovery_refinement(
        monkeypatch, tighter=tighter, local_stop_time_s=declaration.get("local_stop_time_s")
    )


def test_paired_response_controls_and_physical_effects():
    samples = {}
    for arm in panel.ARMS:
        receipt, data = saved("response-trajectory-" + arm)
        assert receipt["status"] == "passed"
        samples[arm] = data
    times = samples["supply_on"]["observed_times"]
    cut = int(np.flatnonzero(times == panel.INTERVENTION_TIME)[0])
    # Same pre-intervention states, despite different future control schedules.
    np.testing.assert_array_equal(
        samples["supply_off"]["state"][: cut + 1], samples["supply_recovery"]["state"][: cut + 1]
    )
    np.testing.assert_array_equal(
        samples["cotransport_blocked"]["state"][: cut + 1],
        samples["cotransport_release"]["state"][: cut + 1],
    )
    atp = {a: v["observed_energy_amount_fmol"][:, 0, 0] for a, v in samples.items()}
    assert atp["supply_off"][cut] < 0.9 * atp["supply_off"][0]
    assert atp["supply_recovery"][-1] > 1.1 * atp["supply_recovery"][cut]
    assert atp["supply_recovery"][-1] > atp["supply_off"][-1]
    for arm in ("cotransport_blocked", "cotransport_release"):
        endpoint = None if arm == "cotransport_blocked" else cut + 1
        for field in (
            "cotransport_cycles_fmol",
            "cotransport_transferred_fmol",
            "cotransport_dissipated_energy_pJ",
        ):
            assert not np.any(samples[arm]["observed_" + field][:endpoint])
    for field in (
        "volume_increment_pL",
        "extracellular_volume_increment_pL",
        "water_transferred_pL",
        "water_dissipated_energy_pJ",
        "pool_volume_work_pJ",
    ):
        assert not np.any(samples["water_blocked"]["observed_" + field])
    volume_effect = float(
        samples["supply_on"]["observed_volume_increment_pL"][-1, 0]
        - samples["cotransport_blocked"]["observed_volume_increment_pL"][-1, 0]
    )
    assert abs(volume_effect) > 1e-6
    write(
        "response-controls",
        dict(
            status="passed",
            cases=list(panel.ARMS),
            interpretation="Matched manufactured controls, not independent biological cases",
            atp_at_cut_fmol={a: float(v[cut]) for a, v in atp.items()},
            final_atp_fmol={a: float(v[-1]) for a, v in atp.items()},
            cotransport_volume_effect_pL=volume_effect,
        ),
    )


def test_complete_disk_restart_in_fresh_worker(monkeypatch):
    producer, _ = saved("response-trajectory-supply_recovery")
    consumer = worker_identity()
    assert producer["worker"] != consumer
    loaded = load_snapshot(root() / "response-restart")
    value = run_captured(
        loaded.spec,
        "response-restart",
        monkeypatch,
        checkpoint=loaded.checkpoint,
        window_steps=producer.get("window_steps"),
    )
    expected = load_snapshot(root() / "response-final-supply_recovery")
    write(
        "response-restart-result",
        dict(status="captured", diagnostics=value.diagnostics, timings=value.timings),
        dict(
            **{"state_" + k: v for k, v in value.final.state._asdict().items()},
            **{"layout_" + k: v for k, v in value.final.layout._asdict().items()},
        ),
    )
    for a, b in zip(
        (*value.final.state, *value.final.layout),
        (*expected.checkpoint.state, *expected.checkpoint.layout),
        strict=True,
    ):
        np.testing.assert_array_equal(a, b)
        assert np.asarray(a).dtype == np.asarray(b).dtype
        assert np.asarray(a).tobytes() == np.asarray(b).tobytes()
    _, full = saved("response-history-supply_recovery")
    index = int(np.flatnonzero(full["accepted_times"] == panel.INTERVENTION_TIME)[0])
    np.testing.assert_array_equal(full["accepted_times"][index:], value.times)
    for name, field in value.history._asdict().items():
        np.testing.assert_array_equal(full[name][index:], field)
    _, full_observations = saved("response-trajectory-supply_recovery")
    keep = full_observations["observed_times"] >= loaded.checkpoint.time
    for name, field in vars(value.observations).items():
        np.testing.assert_array_equal(full_observations["observed_" + name][keep], field)
    clock = (value.final.time, value.final.step_index, value.final.event_index)
    assert clock == (
        expected.checkpoint.time,
        expected.checkpoint.step_index,
        expected.checkpoint.event_index,
    )
    write(
        "response-restart-result",
        dict(
            status="passed",
            full_state_fields=31,
            complete_history=True,
            fresh_worker=True,
            producer_worker=producer["worker"],
            restart_worker=consumer,
            final_clock=dict(time=clock[0], step_index=clock[1], event_index=clock[2]),
            comparison="bitwise",
            final_snapshot_manifest_sha256=hashlib.sha256(
                (root() / "response-final-supply_recovery" / "manifest.json").read_bytes()
            ).hexdigest(),
        ),
    )
