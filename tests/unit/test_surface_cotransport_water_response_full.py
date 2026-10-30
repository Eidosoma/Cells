"""Longer physical response checks; launched explicitly in guarded CPU groups.

The full half-second trajectories keep every accepted state and compare an
independent adaptive solver. Manufactured controls are paired numerical cases,
not independent biological observations. GPU qualification is separate.
"""

import hashlib
import json
import os
from pathlib import Path

import jax
import numpy as np
import pytest

from cells.core import runner
from cells.core.runner import run
from cells.core.schedule import control_values
from cells.core.specs import parse_spec
from cells.io import load_snapshot, write_snapshot
from cells.models import surface_cotransport_water as model
from cells.numerics.fixed_step import rk4_checked_step
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


def run_captured(spec, name, monkeypatch, *, checkpoint=None):
    """Save the complete proposed history before the unchanged acceptance checks.

    The ordinary runner remains authoritative. This test-local observation hook
    never returns a rejected trajectory or converts a failure into acceptance.
    Domain rejection before history analysis retains its original exception.
    """
    original = runner._analyse_segment

    def capture(spec, parent, times, arrays, final_state, layout, requested):
        write(
            name + "-proposed-history",
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
            return original(spec, parent, times, arrays, final_state, layout, requested)
        except Exception as error:
            write(
                name + "-rejection",
                dict(
                    status="rejected",
                    error_type=type(error).__name__,
                    error=str(error),
                    proposed_history=name + "-proposed-history.npz",
                    accepted_result_returned=False,
                    automatic_retry=False,
                ),
            )
            raise

    with monkeypatch.context() as patch:
        patch.setattr(runner, "_analyse_segment", capture)
        return run(spec, checkpoint=checkpoint)


def field_errors(c, actual, expected):
    return {
        name: float(np.max(np.abs(value), initial=0))
        for name, value in reference.unpack(c, actual - expected).items()
    }


def score(c, actual, expected, *, atol=2e-11, charge_atol=3e-25, rtol=3e-9):
    absolute = reference.flatten(
        c,
        {
            k: np.full(shape, charge_atol if k.endswith("_C") else atol)
            for k, shape in c["shapes"].items()
        },
    )
    ratios = np.abs(actual - expected) / (absolute + rtol * np.abs(expected))
    assert np.isfinite(ratios).all()
    result = float(np.max(ratios, initial=0))
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


@pytest.mark.parametrize("arm", panel.ARMS)
def test_complete_response_against_independent_reference(arm, monkeypatch):
    assert jax.default_backend() == "cpu" and jax.config.x64_enabled
    raw = panel.definition(arm)
    write(
        "response-trajectory-" + arm,
        dict(status="running", inputs=raw, duration=panel.duration_inputs(raw)),
    )
    value = run_captured(parse_spec(raw), "response-trajectory-" + arm, monkeypatch)
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
    expected = independent(arm, raw)
    try:
        report["max_error_over_budget"] = score(c, actual, expected["state"])
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


def test_recovery_refinement_and_reference_stability(monkeypatch):
    arm = "supply_recovery"
    first, arrays = saved("response-trajectory-" + arm)
    assert first["status"] == "passed"
    raw, coarse = first["inputs"], arrays["state"]
    c = reference.bind(raw)
    _, reference1 = saved("response-reference-" + arm + "-r1")
    tighter = independent(arm, raw, refinement=2)
    stability = score(
        c, reference1["state"], tighter["state"], atol=3e-14, charge_atol=3e-28, rtol=3e-11
    )
    errors = [field_errors(c, coarse, tighter["state"])]
    scores = [score(c, coarse, tighter["state"])]
    for factor in (2, 4):
        refined_raw = panel.definition(arm, dt=panel.DT / factor)
        value = run_captured(parse_spec(refined_raw), f"response-refined-r{factor}", monkeypatch)
        actual = reference.flatten(c, vars(value.observations))
        write(
            f"response-refined-r{factor}",
            dict(
                status="captured",
                inputs=refined_raw,
                diagnostics=value.diagnostics,
                timings=value.timings,
            ),
            dict(state=actual, signed_error=actual - tighter["state"]),
        )
        errors.append(field_errors(c, actual, tighter["state"]))
        scores.append(score(c, actual, tighter["state"]))
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
    value = run_captured(loaded.spec, "response-restart", monkeypatch, checkpoint=loaded.checkpoint)
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
