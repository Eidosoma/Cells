"""Bounded composition software checks, not full-panel numerical acceptance."""

import copy
import importlib
import math
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
p = importlib.import_module("coupled_plan")
r = importlib.import_module("coupled_reference")
a = importlib.import_module("coupled_candidate")
job = importlib.import_module("coupled_job")
check = importlib.import_module("coupled_compare")


@pytest.mark.parametrize("case", p.cases(), ids=lambda case: case["id"])
def test_complete_rhs_and_same_stage_conservation(case):
    state = np.zeros(r.size(case))
    parameters = a.parameters(case, np)
    for _ in range(2):
        control = [case["controls"][0]["pump"], case["controls"][0]["leak"]]
        expected = np.asarray(r.rhs(case, state, control))
        actual = a.rhs(state, control, parameters, xp=np)
        assert a.valid(state, parameters, xp=np)
        np.testing.assert_allclose(actual, expected, atol=2e-13, rtol=2e-12)
        n = len(case["volume_pL"])
        np.testing.assert_allclose(
            actual[: 3 * n].reshape(n, 3).sum(axis=0) + actual[3 * n : 3 * n + 3], 0, atol=1e-15
        )
        assert min(actual[7 * n + 3 :]) >= -1e-13
        state += 1e-6 * actual


@pytest.mark.parametrize("case", p.cases(), ids=lambda case: case["id"])
def test_explicit_initial_charge_closure(case):
    charges = []
    for i, row in enumerate(case["initial_inside_mM"]):
        charge = (
            p.F
            * 1e-15
            * (
                case["fixed_inside_charge_fmol"][i]
                + case["volume_pL"][i]
                * math.fsum(z * v for z, v in zip(case["valence"], row, strict=True))
            )
        )
        assert charge / (
            case["area_m2"][i] * case["specific_capacitance_F_m2"][i]
        ) == pytest.approx(case["initial_voltage_V"][i], abs=1e-10)
        charges.append(charge)
    outside = (
        p.F
        * 1e-15
        * (
            case["fixed_outside_charge_fmol"]
            + case["outside_volume_pL"]
            * math.fsum(
                z * v for z, v in zip(case["valence"], case["initial_outside_mM"], strict=True)
            )
        )
    )
    assert abs(math.fsum([*charges, outside])) < 1e-20


@pytest.mark.parametrize(
    "index,value", [(0, -13.0), (0, math.nan), (0, math.inf), (3, -141.0), (2, 140.0)]
)
def test_domain_refuses_bad_trial_without_repair(index, value):
    case = p.cases()[0]
    state = np.zeros(r.size(case))
    state[index] = value
    before = state.copy()
    assert not a.valid(state, a.parameters(case, np), xp=np)
    with pytest.raises(ValueError, match="trial"):
        a.numpy_rollout(case, 0.0001, [[1, 1]], initial=state)
    assert np.array_equal(before, state, equal_nan=True)


def test_synthetic_pump_is_not_called_or_subtracted(monkeypatch):
    from cells.processes import electrochemistry

    def forbidden(*_args, **_kwargs):
        raise AssertionError("Synthetic pump cannot stand in for kinetic pump")

    monkeypatch.setattr(electrochemistry, "reversible_pump", forbidden)
    case = p.cases()[0]
    assert np.isfinite(a.rhs(np.zeros(r.size(case)), [1, 1], a.parameters(case, np), xp=np)).all()


def test_species_roles_follow_explicit_mapping():
    case = copy.deepcopy(p.cases()[-1])
    order = [2, 0, 1]
    for key in ("species", "valence", "pump_stoichiometry", "initial_outside_mM"):
        case[key] = [case[key][i] for i in order]
    for key in ("initial_inside_mM", "permeability_m_s"):
        case[key] = [[row[i] for i in order] for row in case[key]]
    case["sodium_index"], case["potassium_index"] = 1, 2
    state = np.zeros(r.size(case))
    np.testing.assert_allclose(
        a.rhs(state, [1, 1], a.parameters(case, np), xp=np),
        r.rhs(case, state, [1, 1]),
        atol=2e-13,
        rtol=2e-12,
    )


def test_held_inputs_have_exact_grid_boundaries():
    case = next(c for c in p.cases() if c["id"] == "pump_block_release")
    inputs = p.controls(case, 0.0001)
    assert inputs[39] == [1, 1] and inputs[40] == [0, 1]
    assert inputs[59] == [0, 1] and inputs[60] == [1, 1]
    with pytest.raises(ValueError, match="grid"):
        p.controls(case, 0.00013)


def test_short_numpy_and_independent_adaptive_reference(tmp_path):
    case, protocol = copy.deepcopy(p.cases()[0]), p.protocol()
    case["end_time_s"] = 0.0004
    protocol["sample_dt_s"] = 0.0001
    fixture, result_path = tmp_path / "reference-input.json", tmp_path / "reference-output.json"
    p.c.write(fixture, {"case": case, "plan": protocol})
    result = subprocess.run(
        [
            str(p.c.REFERENCE_PYTHON),
            "-B",
            "-c",
            "import sys; import coupled_plan as p; import coupled_reference as r; "
            "v=p.c.read(sys.argv[1]); "
            "p.c.write(sys.argv[2], r.integrate(v['case'],v['plan'],'Radau'))",
            str(fixture),
            str(result_path),
        ],
        cwd=Path(__file__).resolve().parent,
        env=job.environment(tmp_path),
        capture_output=True,
        text=True,
        check=True,
        timeout=20,
    )
    assert not result.stderr
    reference = p.c.read(result_path)
    states = a.numpy_rollout(case, 0.0001, p.controls(case, 0.0001))
    np.testing.assert_allclose(states, reference["state"], atol=1e-10, rtol=2e-9)
    for state in states:
        evidence = r.accounting(case, state)
        assert evidence["material_residual_fmol"] <= 2e-14
        assert evidence["energy_residual_pJ"] <= 2e-8


def test_four_step_compiled_shared_rk4_and_restart():
    import jax
    import jax.numpy as jnp

    case = p.cases()[0]
    state = np.zeros(r.size(case))
    parameters = a.parameters(case, jnp)
    actual = a.rhs(jnp.asarray(state), jnp.asarray([1, 1]), parameters, xp=jnp)
    compiled = jax.jit(lambda y: a.rhs(y, jnp.asarray([1, 1]), parameters, xp=jnp))(
        jnp.asarray(state)
    )
    np.testing.assert_allclose(actual, r.rhs(case, state, [1, 1]), atol=2e-13, rtol=2e-12)
    np.testing.assert_allclose(compiled, actual, atol=2e-13, rtol=2e-12)
    inputs = [[1, 1]] * 4
    states = a.jax_rollout(case, 0.0001, inputs)
    numpy_states = a.numpy_rollout(case, 0.0001, inputs)
    np.testing.assert_allclose(states, numpy_states, atol=1e-13, rtol=1e-12)
    resumed = a.jax_rollout(case, 0.0001, inputs[2:], initial=states[2].tolist())
    assert np.array_equal(resumed, states[2:])


def test_blocked_pump_retains_history_and_leak():
    case = p.cases()[0]
    state = a.numpy_rollout(case, 0.0001, [[1, 1]])[-1]
    blocked = a.numpy_rollout(case, 0.0001, [[0, 1]] * 3, initial=state)
    assert np.all(blocked[:, 9] == state[9])
    assert np.any(blocked[-1, :3] != state[:3])


def test_all_blocked_exactly_preserves_complete_state():
    case = p.cases()[0]
    state = a.numpy_rollout(case, 0.0001, [[1, 1]])[-1]
    blocked = a.numpy_rollout(case, 0.0001, [[0, 0]] * 3, initial=state)
    assert np.array_equal(blocked, np.broadcast_to(state, blocked.shape))


def test_controller_failure_is_durable(tmp_path, monkeypatch):
    def reject(_output):
        raise ValueError("Fixture registration rejection")

    monkeypatch.setattr(job, "authenticate", reject)
    with pytest.raises(ValueError, match="Fixture"):
        job.execute(tmp_path)
    assert job.c.read(tmp_path / "failure.json")["status"] == "failed_not_qualified"
    assert not (tmp_path / "completion.json").exists()


def test_detached_launch_never_waits_or_polls(tmp_path, monkeypatch):
    monkeypatch.setattr(job, "register", lambda *_: {"protocol": p.protocol()})
    monkeypatch.setattr(job.c, "sha", lambda _: "fixture")
    calls = []

    def popen(*args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(pid=123)

    monkeypatch.setattr(job.subprocess, "Popen", popen)
    assert job.launch(tmp_path, tmp_path / "fixture.xml")["automatic_polling"] is False
    assert calls[0][1]["start_new_session"] is True


def test_closed_source_contact_is_required():
    assert p.predecessor()["completion_sha256"] == p.AUDIT_SHA


def test_existing_registration_directory_is_refused(tmp_path):
    with pytest.raises(ValueError, match="fresh"):
        job.register(tmp_path, tmp_path / "fixture.xml")


def synthetic_packets():
    protocol = p.protocol()
    references, candidates = {}, {}
    for case in protocol["cases"]:
        width = r.size(case)
        sample = {
            "times_s": [k * protocol["sample_dt_s"] for k in range(11)],
            "state": [[0.0] * width for _ in range(11)],
        }
        references[case["id"]] = {
            method: copy.deepcopy(sample) for method in protocol["reference_methods"]
        }
        trajectories, checkpoints = {}, {}
        for engine in ("numpy", "jax_jit"):
            for dt in protocol["rk4_steps_s"]:
                full = [[0.0] * width for _ in range(round(case["end_time_s"] / dt) + 1)]
                trajectories[f"{engine}/{dt}"] = {
                    **copy.deepcopy(sample),
                    "step_s": dt,
                    "full_state": full,
                }
                if dt == protocol["rk4_steps_s"][-1]:
                    index = round(0.006 / dt)
                    checkpoints[engine] = {
                        "time_s": 0.006,
                        "complete_state": full[index],
                        "suffix_state": full[index:],
                        "exact": True,
                    }
        candidates[case["id"]] = {
            "trajectories": trajectories,
            "checkpoints": checkpoints,
            "restart_exact": True,
        }
    return protocol, references, candidates


def test_synthetic_comparator_complete_not_executed_physics():
    result = check.compare(*synthetic_packets())
    assert result["status"] == "pass" and result["state_comparisons"] == 4070
    assert len(result["groups"]) == 30 and len(result["refinement"]) == 12
    assert not result["production_model_accepted"]


@pytest.mark.parametrize(
    "change", ["missing_case", "missing_engine", "full", "sample", "restart", "time", "energy"]
)
def test_corrupted_saved_coupling_is_rejected(change):
    protocol, reference, candidates = synthetic_packets()
    case = candidates["pump_leak"]
    trial = case["trajectories"]["numpy/0.0001"]
    if change == "missing_case":
        candidates.pop("leak_only")
    elif change == "missing_engine":
        case["trajectories"].pop("jax_jit/0.0001")
    elif change == "full":
        trial["full_state"].pop()
    elif change == "sample":
        trial["state"][1][0] = 1e-5
    elif change == "restart":
        case["checkpoints"]["numpy"]["suffix_state"] = []
    elif change == "time":
        trial["times_s"][2] += 0.0001
    else:
        # Coherently alter a nonsampled dissipation record: full-state checks
        # must reject it even when all sampled values still agree perfectly.
        trial["full_state"][1][-1] += 0.001
        assert check.compare(protocol, reference, candidates)["status"] == "failed"
        return
    with pytest.raises(ValueError):
        check.compare(protocol, reference, candidates)


def test_attempted_execution_is_not_modified(tmp_path):
    p.c.write(tmp_path / "started.json", {"fixture": True})
    before = (tmp_path / "started.json").read_bytes()
    with pytest.raises(ValueError, match="already attempted"):
        job.execute(tmp_path)
    assert (tmp_path / "started.json").read_bytes() == before
    assert not (tmp_path / "failure.json").exists()
