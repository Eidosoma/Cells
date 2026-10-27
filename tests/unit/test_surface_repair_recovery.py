"""Longer injury qualification and sampled recovery outcomes, including non-recovery."""

import json
from pathlib import Path

import numpy as np
import pytest

from cells.core.batch import BatchSpec, WorldSpec, plan_batch, run_batch
from cells.core.resources import trace_bytes
from cells.core.runner import run, timeline
from cells.core.specs import ConfigError, parse_spec
from cells.core.windows import WindowPolicy, iter_windows
from cells.io import load_snapshot, write_run, write_snapshot
from cells.models import surface_repair as model
from tests.unit.test_surface_calcium import BACKEND, EVIDENCE, evidence
from tests.unit.test_surface_kinetic import assert_states, exact
from tests.unit.test_surface_repair_full import arrays, compare_backend, normalized
from validation.tissue import surface_repair_recovery as fixtures
from validation.tissue import surface_repair_reference as reference

PREFIX = "resolved-repair-recovery"
REFERENCE = dict(rtol=1e-13, atol=1e-16, charge_atol=5e-32)


def capture(name, value, *, status="captured", **details):
    evidence(
        PREFIX + "-" + name,
        dict(status=status, inputs=value.spec.to_dict(), diagnostics=value.diagnostics, **details),
        arrays(value),
    )


def independent(raw, arm):
    name = PREFIX + "-reference-" + arm
    directory = Path(EVIDENCE) / "cpu" if EVIDENCE else None
    if directory and (directory / (name + ".json")).exists():
        receipt = json.loads((directory / (name + ".json")).read_text())
        assert receipt["status"] == "passed"
        assert receipt["inputs"] == normalized(raw) and receipt["settings"] == REFERENCE
        with np.load(directory / (name + ".npz"), allow_pickle=False) as saved:
            data = {k: saved[k].copy() for k in saved.files}
        assert data["state"].shape[0] == len(raw["experiment"]["observation_times"])
        if BACKEND == "gpu":
            evidence(name, receipt | dict(reused_cpu_reference=True), data)
        return data
    assert BACKEND == "cpu", "GPU comparison needs completed independent CPU references"
    result = reference.integrate(raw, **REFERENCE)
    data = dict(state=result["state"], **reference.measurements(raw, result["state"]))
    evidence(
        name,
        dict(
            status="passed",
            inputs=normalized(raw),
            settings=REFERENCE,
            method=result["method"],
            evaluations=result["evaluations"],
        ),
        data,
    )
    return data


def test_registered_long_grids_and_gpu_example():
    grids = []
    for arm in fixtures.ARMS:
        for dt in fixtures.STEPS:
            spec = parse_spec(fixtures.definition(arm, backend=BACKEND, dt=dt))
            times = timeline(spec)
            assert np.isin(spec.experiment.observation_times, times).all()
            assert len(spec.experiment.observation_times) == 83
            assert 5.3e-6 in times and 15.3e-6 in times and 0.001 in times
            assert times[-1] == 0.002 and len(model.STATE_TYPE._fields) == 39
            grids.append(
                dict(
                    arm=arm,
                    dt_s=dt,
                    steps=len(times) - 1,
                    estimated_trace_bytes=trace_bytes(spec, len(times) - 1),
                )
            )
    worlds = tuple(
        WorldSpec(i, parse_spec(fixtures.definition(arm, backend=BACKEND)))
        for i, arm in ((7, "resealing"), (29, "held"))
    )
    planned = plan_batch(BatchSpec(worlds, 2, 8192, 2**33))
    # The earlier 4-GiB declaration cannot cover this longer finest grid or batch.
    old = fixtures.definition(dt=fixtures.STEPS[-1])
    old["execution"]["max_trace_bytes"] = 2**32
    with pytest.raises(ConfigError, match="trace working storage"):
        timeline(parse_spec(old))
    with pytest.raises(ConfigError, match="aggregate arrays"):
        plan_batch(BatchSpec(worlds, 2, 8192, 2**32))
    root = Path(__file__).resolve().parents[2]
    assert json.loads(
        (root / "configs/resolved_repair_recovery_tissue.json").read_text()
    ) == fixtures.definition(backend="gpu")
    evidence(
        PREFIX + "-grids",
        dict(
            status="passed",
            grids=grids,
            batch_estimated_working_bytes=planned.estimated_working_bytes,
            obsolete_budgets_rejected=True,
        ),
    )


def test_initial_free_ion_and_voltage_readouts_match_independent_owners():
    spec = parse_spec(fixtures.definition())
    raw = spec.to_dict()
    state, p = model.initial_values(spec)
    history = model.STATE_TYPE(*(v[None] for v in state))
    observed = model.observe_history(np.array([0.0]), history, p, [0.0], spec)
    actual = fixtures.measurements(raw, vars(observed))
    raw["experiment"]["observation_times"] = [0.0]
    c = reference.bind(raw)
    expected = reference.measurements(raw, reference.initial(c)[None])
    for name in fixtures.BANDS:
        np.testing.assert_allclose(actual[name], expected[name], rtol=3e-12, atol=3e-13)
    assert actual["cytosol_free_mM"].shape == (1, 4, 2)
    assert actual["exterior_free_mM"].shape == (1, 4, 5)
    evidence(PREFIX + "-owners", dict(status="passed", padding_excluded=True))


@pytest.fixture(scope="module")
def histories(tmp_path_factory):
    root, values = tmp_path_factory.mktemp("recovery-histories"), {}
    for arm in fixtures.ARMS:
        value = run(parse_spec(fixtures.definition(arm, backend=BACKEND)))
        write_run(root / arm, value)
        capture(arm, value)
        assert all(v.device.platform == BACKEND for v in value.final.state)
        values[arm] = value
    return values


@pytest.mark.parametrize("arm", ("held", "resealing"))
def test_long_reference_stability(arm):
    raw = parse_spec(fixtures.definition(arm, backend=BACKEND)).to_dict()
    name = PREFIX + "-reference-stability-" + arm
    tighter_settings = {k: v / 4 for k, v in REFERENCE.items()}
    if BACKEND == "gpu":
        saved = json.loads((Path(EVIDENCE) / "cpu" / (name + ".json")).read_text())
        assert saved["status"] == "passed" and saved["inputs"] == normalized(raw)
        assert saved["settings"] == REFERENCE and saved["tighter_settings"] == tighter_settings
        evidence(name, saved | dict(reused_cpu_reference=True))
        return
    c, ordinary = reference.bind(raw), independent(raw, arm)
    tighter = reference.integrate(raw, **tighter_settings)["state"]
    tighter_readouts = reference.measurements(raw, tighter)
    evidence(
        name + "-arrays",
        dict(inputs=raw, settings=REFERENCE, tighter_settings=tighter_settings),
        dict(
            reference=ordinary["state"],
            tighter=tighter,
            signed_error=ordinary["state"] - tighter,
            **{"tighter_" + k: v for k, v in tighter_readouts.items()},
        ),
    )
    for k, v in reference.unpack(c, ordinary["state"] - tighter).items():
        assert np.max(np.abs(v), initial=0) <= (3e-28 if k.endswith("_C") else 3e-14), k
    for k, v in tighter_readouts.items():
        assert np.max(np.abs(ordinary[k] - v)) <= fixtures.READOUT_ATOL[k] / 10, k
    evidence(
        name,
        dict(
            status="passed",
            inputs=normalized(raw),
            settings=REFERENCE,
            tighter_settings=tighter_settings,
            state_floor=3e-14,
            charge_floor_C=3e-28,
            readout_floors={k: v / 10 for k, v in fixtures.READOUT_ATOL.items()},
        ),
    )


@pytest.mark.parametrize("arm", fixtures.ARMS)
def test_long_trajectory_reference_conservation_and_damage(histories, arm):
    value = histories[arm]
    raw = value.spec.to_dict()
    expected, c = independent(raw, arm), reference.bind(raw)
    actual = reference.flatten(c, vars(value.observations))
    measured = fixtures.measurements(raw, vars(value.observations))
    evidence(
        PREFIX + "-errors-" + arm,
        dict(inputs=raw),
        dict(
            actual=actual,
            reference=expected["state"],
            signed_error=actual - expected["state"],
            **{"measured_" + k: v for k, v in measured.items()},
            **{"readout_error_" + k: v - expected[k] for k, v in measured.items()},
        ),
    )
    ratio = assert_states(c, actual, expected["state"])
    for k, v in measured.items():
        np.testing.assert_allclose(v, expected[k], rtol=0, atol=fixtures.READOUT_ATOL[k], err_msg=k)
    hazard = 20000.0 if arm in ("held", "resealing") else 0.0
    closure = 0.0 if arm == "held" else 4000.0
    damage = []
    for t in value.observations.times:
        peak = reference.analytic_damage(0.0, hazard, closure, min(max(t - 5.3e-6, 0.0), 10e-6))
        damage.append(reference.analytic_damage(peak, 0.0, closure, max(t - 15.3e-6, 0.0)))
    np.testing.assert_allclose(value.observations.damage[:, 0], damage, rtol=0, atol=2e-9)
    model.check_values(value.history, value.spec)
    capture(arm, value, status="passed", max_error_over_budget=ratio)


def test_sampled_functional_recovery_report_preserves_all_outcomes(histories):
    baseline = histories["uninjured"]
    expected_base = independent(baseline.spec.to_dict(), "uninjured")
    expected_base = {k: expected_base[k] for k in fixtures.BANDS}
    reports, references = {}, {}
    for arm, value in histories.items():
        before = value.times <= fixtures.SETTINGS["intervention_s"]
        exact(tuple(v[before] for v in value.history), tuple(v[before] for v in baseline.history))
        raw = value.spec.to_dict()
        measured = fixtures.measurements(raw, vars(value.observations))
        expected = independent(raw, arm)
        reports[arm] = fixtures.assess(value.observations.times, measured, expected_base)
        references[arm] = fixtures.assess(
            value.observations.times, {k: expected[k] for k in fixtures.BANDS}, expected_base
        )
    report = dict(
        status="captured",
        arms=reports,
        independent_reference_arms=references,
        bands=fixtures.BANDS,
        uncertainty=fixtures.UNCERTAINTY,
        settings=fixtures.SETTINGS,
        interpretation="Return to matched synthetic trajectory; no biological repair claim",
        closure_fraction_remaining=float(
            histories["resealing"].history.damage[-1, 0]
            / histories["resealing"].checkpoint_at(15.3e-6).state.damage[0]
        ),
    )
    evidence(PREFIX + "-functional", report)
    exact(histories["uninjured"].history, histories["sham"].history)
    for arm in fixtures.ARMS:
        assert reports[arm]["classification"] == references[arm]["classification"]
        for k in fixtures.BANDS:
            assert (
                reports[arm]["metrics"][k]["classification"]
                == references[arm]["metrics"][k]["classification"]
            )
        if arm in ("uninjured", "sham"):
            assert reports[arm]["classification"] == "no_resolved_departure"
        else:
            assert reports[arm]["first_resolved_departure_s"] is not None
    assert report["closure_fraction_remaining"] < 1e-3
    evidence(PREFIX + "-functional", report | dict(status="passed"))


@pytest.mark.parametrize("arm", ("held", "resealing"))
def test_long_coupled_timestep_refinement(arm):
    raw = parse_spec(fixtures.definition(arm, backend=BACKEND)).to_dict()
    expected, c = independent(raw, arm), reference.bind(raw)
    errors, charges, ratios = [], [], []
    for i, dt in enumerate(fixtures.STEPS):
        raw["execution"]["dt"] = dt
        value = run(parse_spec(raw))
        actual = reference.flatten(c, vars(value.observations))
        capture(f"refinement-{arm}-{i}", value)
        evidence(
            PREFIX + f"-refinement-errors-{arm}-{i}",
            dict(inputs=raw),
            dict(
                actual=actual, reference=expected["state"], signed_error=actual - expected["state"]
            ),
        )
        ratios.append(assert_states(c, actual, expected["state"]))
        diff = reference.unpack(c, actual - expected["state"])
        errors.append(
            max(float(np.max(np.abs(v))) for k, v in diff.items() if not k.endswith("_C"))
        )
        charges.append(max(float(np.max(np.abs(v))) for k, v in diff.items() if k.endswith("_C")))
    assert errors[-1] <= max(errors[0] * 0.2, 3e-13)
    assert charges[-1] <= max(charges[0] * 0.2, 3e-27)
    evidence(
        PREFIX + "-refinement-" + arm,
        dict(
            status="passed",
            steps_s=fixtures.STEPS,
            max_error_over_budget=ratios,
            noncharge_max_errors=errors,
            charge_max_errors_C=charges,
        ),
    )


def test_long_complete_checkpoint_and_window_replay(histories, tmp_path):
    value = histories["resealing"]
    checkpoint = value.checkpoint_at(0.001)
    write_snapshot(tmp_path / "checkpoint", value.spec, checkpoint)
    saved = load_snapshot(tmp_path / "checkpoint")
    exact(saved.checkpoint.state, checkpoint.state)
    resumed = run(saved.spec, saved.checkpoint)
    capture("resumed", resumed)
    exact(resumed.history, tuple(v[checkpoint.step_index :] for v in value.history))
    parts = list(iter_windows(saved.spec, WindowPolicy(257, "full"), saved.checkpoint))
    merged = tuple(
        np.concatenate([getattr(p.history, k)[0 if i == 0 else 1 :] for i, p in enumerate(parts)])
        for k in model.STATE_TYPE._fields
    )
    evidence(
        PREFIX + "-windows",
        dict(inputs=value.spec.to_dict()),
        dict(zip(model.STATE_TYPE._fields, merged, strict=True)),
    )
    exact(merged, resumed.history)
    evidence(
        PREFIX + "-replay",
        dict(status="passed", complete_history_bitwise=True, checkpoint_s=0.001, window_steps=257),
    )


def test_long_independent_worlds_and_reordering(histories):
    expected = {7: histories["resealing"], 29: histories["held"]}
    worlds = tuple(WorldSpec(i, v.spec) for i, v in expected.items())
    for label, rows in (("world", worlds), ("reordered-world", tuple(reversed(worlds)))):
        actual = run_batch(BatchSpec(rows, 2, 8192, 2**33))
        for identity, value in actual.worlds.items():
            capture(f"{label}-{identity}", value)
            exact(value.history, expected[identity].history)
    evidence(
        PREFIX + "-worlds",
        dict(
            status="passed", complete_history_bitwise=True, reordered=True, world_ids=list(expected)
        ),
    )


def test_long_cpu_gpu_complete_histories_and_observations(histories):
    if BACKEND == "cpu":
        pytest.skip("Requires following L4 phase and complete saved CPU histories")
    count = 0
    for arm, value in histories.items():
        path = Path(EVIDENCE) / "cpu" / (PREFIX + "-" + arm)
        receipt = json.loads(path.with_suffix(".json").read_text())
        assert receipt["status"] == "passed" and receipt["inputs"] == normalized(
            value.spec.to_dict()
        )
        with np.load(path.with_suffix(".npz"), allow_pickle=False) as saved:
            count += compare_backend(arrays(value), saved)
    cpu = json.loads((Path(EVIDENCE) / "cpu" / (PREFIX + "-functional.json")).read_text())
    gpu = json.loads((Path(EVIDENCE) / "gpu" / (PREFIX + "-functional.json")).read_text())
    assert cpu["status"] == gpu["status"] == "passed"
    for arm in fixtures.ARMS:
        assert cpu["arms"][arm]["classification"] == gpu["arms"][arm]["classification"]
    evidence(
        PREFIX + "-cpu-gpu",
        dict(
            status="passed",
            scalar_values=count,
            recovery_labels_identical=True,
            unit_specific_tolerances_unchanged=True,
        ),
    )
