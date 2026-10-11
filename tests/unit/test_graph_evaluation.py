"""D041 complete derivative, immutable-cache and checked short-trajectory tests."""

import copy
import subprocess
from contextlib import closing
from dataclasses import FrozenInstanceError
from time import perf_counter

import numpy as np
import pytest

from scripts import audit_graph_evaluation as audit
from scripts import profile_graph_evaluation as profile
from tests import reference_comparison_evidence as codec
from tests import reference_graph_evaluation as evaluation
from tests import reference_graph_evidence as evidence
from tests import reference_recorded_candidate as runner
from tests import source_graph_fixtures as fixtures
from tests.unit import test_comparison_evidence as prior
from tests.unit.test_graph_candidate import short_references as short_references
from tests.unit.test_graph_evidence import assert_bits, collect

ref, prep = profile.ref, profile.prep


@pytest.fixture
def model():
    return prep.graph.Model(next(case for case in fixtures.cases() if case["id"] == "G07"))


@pytest.fixture
def protocol():
    return profile.campaign.frozen.load_protocol()


@pytest.mark.parametrize("case", fixtures.cases(), ids=lambda case: case["id"])
@pytest.mark.parametrize("policy", evaluation.POLICIES)
@pytest.mark.parametrize("increments", [False, True])
def test_complete_rhs_and_all_fields_are_exact(case, policy, increments):
    original = prep.graph.Model(case)
    prepared = evaluation.PreparedModel(original, policy=policy)
    for index in range(8):
        value = profile.probe_values(original, index)
        primary = value[: 6 * original.n].reshape(6, original.n) + original.anchor
        assert_bits(prepared.evaluate(primary), original.evaluate(primary))
        if not increments:
            value[: 6 * original.n] += original.anchor.ravel()
        before = value.copy()
        want = original.derivative(value, increments=increments)
        got = prepared.derivative(value, increments=increments)
        assert got.tobytes() == want.tobytes()
        assert value.tobytes() == before.tobytes()
        assert got.shape == (13 * original.n + 4 * original.e,)
    assert prepared.receipt()["rhs_calls"] == 8


@pytest.mark.parametrize("policy", evaluation.POLICIES)
def test_snapshot_and_constants_are_immutable_and_detached(model, policy):
    prepared = evaluation.PreparedModel(model, policy=policy)
    values = np.zeros(model.coordinates.size)
    expected = prepared.derivative(values, increments=True)
    identity = prepared.identity
    model.panel["bath_ions"][0] *= 2
    model.case["context"][1][0] = 5
    model.case["controls"]["pump"][0] = 0
    prepared.case["controls"]["pump"][0] = 0
    identity["policy"] = "changed"
    assert prepared.derivative(values, increments=True).tobytes() == expected.tobytes()
    assert prepared.identity["policy"] == policy
    for array in (prepared.anchor, prepared.context, prepared.controls["pump"]):
        with pytest.raises(ValueError):
            array.setflags(write=True)
        with pytest.raises(ValueError):
            array.flat[0] = 0
    if policy == "scalar_cached":
        for name in ("_bath", "_snail_mir", "_ionic_over_len", "_pump_enabled"):
            with pytest.raises(ValueError):
                getattr(prepared, name).setflags(write=True)
    with pytest.raises(TypeError):
        prepared.panel["parameters"]["F"] = 1
    with pytest.raises(FrozenInstanceError):
        prepared.policy = "scalar_frozen"
    expected[:] = 0
    assert np.any(prepared.derivative(values, increments=True))


@pytest.mark.parametrize("policy", evaluation.POLICIES)
def test_strided_vectors_histories_and_coordinate_modes(model, policy):
    prepared = evaluation.PreparedModel(model, policy=policy)
    backing = np.zeros(2 * model.coordinates.size)
    values = backing[::2]
    expected = prepared.derivative(values, increments=True)
    values[6 * model.n :] = np.linspace(-100, 100, model.coordinates.size - 6 * model.n)
    assert prepared.derivative(values, increments=True).tobytes() == expected.tobytes()
    assert not np.any(backing[1::2])
    values[: 6 * model.n] += model.anchor.ravel()
    assert prepared.derivative(values).tobytes() == expected.tobytes()


@pytest.mark.parametrize("policy", evaluation.POLICIES)
@pytest.mark.parametrize(
    "kind", ["list", "float32", "object", "short", "batch", "nan", "inf", "mode"]
)
def test_malformed_complete_inputs_are_refused(model, policy, kind):
    prepared = evaluation.PreparedModel(model, policy=policy)
    value = np.zeros(model.coordinates.size)
    mode = True
    if kind == "list":
        value = value.tolist()
    elif kind in ("float32", "object"):
        value = value.astype(kind)
    elif kind == "short":
        value = value[:-1]
    elif kind == "batch":
        value = value[None]
    elif kind in ("nan", "inf"):
        value[-1] = np.nan if kind == "nan" else np.inf
    else:
        mode = 1
    with pytest.raises(ValueError, match="float64"):
        prepared.derivative(value, increments=mode)
    assert prepared.receipt()["rhs_calls"] == 0


@pytest.mark.parametrize("policy", evaluation.POLICIES)
@pytest.mark.parametrize("kind", ["ion_zero", "ion_upper", "reg_negative", "reg_upper", "voltage"])
def test_primary_domains_remain_frozen(model, policy, kind):
    prepared = evaluation.PreparedModel(model, policy=policy)
    primary = model.anchor.copy()
    if kind == "ion_zero":
        primary[0, 0] = 0
    elif kind == "ion_upper":
        primary[0, 0] = 1001
    elif kind == "reg_negative":
        primary[3, 0] = -1
    elif kind == "reg_upper":
        primary[3, 0] = 1001
    else:
        primary[0, 0] += 0.1
    with pytest.raises(ValueError):
        model.evaluate(primary)
    with pytest.raises(ValueError):
        prepared.evaluate(primary)


@pytest.mark.parametrize("policy", evaluation.POLICIES)
def test_exponent_guard_and_nominal_time_are_preserved(policy):
    panel = prep.graph.eq.load_panel()
    panel["parameters"]["F"] = 1e8
    original = prep.graph.Model(prep.preparations()["E"], panel)
    prepared = evaluation.PreparedModel(original, policy=policy)
    primary = original.anchor.copy()
    primary[0, 0] += 0.05 / (
        panel["parameters"]["F"] * original.volume / (original.area * panel["parameters"]["cm"])
    )
    for model in (original, prepared):
        with pytest.raises(ValueError, match="exponent"):
            model.evaluate(primary)
        for time in (-1, np.nan, np.inf):
            with pytest.raises(ValueError, match="time"):
                model.evaluate(model.anchor, time)


@pytest.mark.parametrize("policy", evaluation.POLICIES)
def test_control_changes_are_explicit_new_identity(model, policy):
    prepared = evaluation.PreparedModel(model, policy=policy)
    state = np.zeros(model.coordinates.size)
    with pytest.raises(ValueError, match="new prepared model"):
        prepared.derivative(state, increments=True, controls=model.case["controls"])
    with pytest.raises(ValueError, match="new prepared model"):
        prepared.evaluate(model.anchor, controls=model.case["controls"])
    changed = copy.deepcopy(model.case)
    changed["controls"]["leak"][0][0] = 0
    updated = evaluation.PreparedModel(prep.graph.Model(changed), policy=policy)
    assert updated.identity != prepared.identity
    assert (
        updated.derivative(state, increments=True).tobytes()
        != prepared.derivative(state, increments=True).tobytes()
    )


@pytest.mark.parametrize("budget", [0, -1, True, 1.0, 1])
def test_budget_preflight_precedes_snapshot(model, monkeypatch, budget):
    def forbidden(*args, **kwargs):
        raise AssertionError("snapshot allocation preceded preflight")

    monkeypatch.setattr(prep.graph.Model, "__init__", forbidden)
    with pytest.raises((ValueError, ref.BudgetExceeded)):
        evaluation.PreparedModel(model, policy="scalar_cached", array_budget_bytes=budget)


def test_unknown_policy_and_model_are_refused(model):
    with pytest.raises(ValueError, match="policy"):
        evaluation.PreparedModel(model, policy="automatic")
    with pytest.raises(ValueError, match="graph model"):
        evaluation.PreparedModel(None, policy="scalar_cached")


def execute(
    root,
    protocol,
    references,
    *,
    policy="scalar_cached",
    width=2,
    name="run",
    initial=None,
    storage_policy="trajectory_backed",
):
    directories, selected = references
    model = evaluation.PreparedModel(prep.graph.Model(selected["case"]), policy=policy)
    args, output = prior.arguments(root, protocol, width), root / name
    args["identity"] = {"fixture": "D041-short", "integration_evaluation": model.identity}
    consumer = codec.Comparison(
        directories,
        selected,
        output,
        root,
        args["resources"],
        [0, 0.013, 0.031, 0.037],
        policy="batched_cached",
        storage_policy=storage_policy,
    )
    result = evaluation.integrate(model, output, comparison=consumer, initial=initial, **args)
    return output, result, consumer, args, model


@pytest.mark.parametrize("policy", evaluation.POLICIES)
@pytest.mark.parametrize("width", [1, 2, 3, 16, 256])
def test_short_checked_profile_preserves_D040_arrays_and_independent_audit(
    tmp_path, protocol, short_references, policy, width
):
    baseline, _, _, _ = prior.execute(
        tmp_path, protocol, short_references, name="baseline", width=width
    )
    folder, report, consumer, args, model = execute(
        tmp_path, protocol, short_references, policy=policy, width=width
    )
    assert_bits(collect(folder), collect(baseline))
    for a, b in zip(prior.decoded(folder), prior.decoded(baseline), strict=True):
        assert_bits(a, b)
    original = prep.graph.Model(short_references[1]["case"])
    audit.audit_trajectory(
        folder, prior.expected(model, args), args["resources"], original.panel, perf_counter() + 60
    )
    checked = audit.audit_stage_rhs(folder, original.case, original.panel, perf_counter() + 60)
    assert (
        checked["complete_RHS_evaluations"]
        == report["rhs_calls"]
        == model.receipt()["rhs_calls"]
        == 20
    )
    sampled = audit.audit_samples(
        folder, *short_references, [0, 0.013, 0.031, 0.037], args["resources"], perf_counter() + 60
    )
    assert sampled["samples"] == report["comparison"]["samples"]
    assert all(reader._iterator.gi_frame is None for reader in consumer.readers.values())


@pytest.mark.parametrize("policy", evaluation.POLICIES)
@pytest.mark.parametrize("chunk", [0, 1, 2])
@pytest.mark.parametrize("storage_policy", codec.POLICIES)
def test_same_evaluator_complete_restart_can_change_recording_policy_and_width(
    tmp_path, protocol, short_references, policy, chunk, storage_policy
):
    folder, _, _, args, model = execute(
        tmp_path,
        protocol,
        short_references,
        policy=policy,
        width=1,
        storage_policy=storage_policy,
    )
    carry = codec.load_checkpoint(folder, chunk, prior.expected(model, args))
    resumed, _, _, _, _ = execute(
        tmp_path,
        protocol,
        short_references,
        policy=policy,
        width=3,
        name="resumed",
        initial=carry,
        storage_policy=next(p for p in codec.POLICIES if p != storage_policy),
    )
    original, continued = collect(folder), collect(resumed)
    for key in ("times", "increments", "coefficients", "slopes"):
        assert continued[key].tobytes() == original[key][carry["tick"] :].tobytes()


@pytest.mark.parametrize("source", evaluation.POLICIES)
def test_cross_evaluator_restart_refused_before_output(
    tmp_path, protocol, short_references, source
):
    folder, _, _, args, model = execute(
        tmp_path, protocol, short_references, policy=source, width=1
    )
    carry = codec.load_checkpoint(folder, 0, prior.expected(model, args))
    target = next(p for p in evaluation.POLICIES if p != source)
    with pytest.raises(ValueError, match="identity"):
        execute(tmp_path, protocol, short_references, policy=target, name="refused", initial=carry)
    assert not (tmp_path / "refused").exists()


@pytest.mark.parametrize("change", ["identity", "budget"])
def test_adapter_preflight_before_any_output(tmp_path, protocol, short_references, change):
    directories, selected = short_references
    model = evaluation.PreparedModel(prep.graph.Model(selected["case"]), policy="scalar_cached")
    args = prior.arguments(tmp_path, protocol)
    args["identity"]["integration_evaluation"] = model.identity
    if change == "identity":
        args["identity"]["integration_evaluation"]["policy"] = "scalar_frozen"
    else:
        args["resources"]["estimated_array_budget_bytes"] = codec.estimate_array_bytes(
            2, model.coordinates.size, model.n
        )
    consumer = codec.Comparison(
        directories,
        selected,
        tmp_path / "run",
        tmp_path,
        args["resources"],
        [0],
        policy="batched_cached",
        storage_policy="trajectory_backed",
    )
    with pytest.raises((ValueError, ref.BudgetExceeded)):
        evaluation.integrate(model, tmp_path / "run", comparison=consumer, **args)
    assert not (tmp_path / "run").exists()


def test_stage_accounting_and_interior_curve_guards_still_apply():
    original = prep.graph.Model(prep.preparations()["E"])
    for policy in evaluation.POLICIES:
        model = evaluation.PreparedModel(original, policy=policy)
        value = np.zeros(model.coordinates.size)
        value[model.coordinates.leak.start] = 1e-6
        with pytest.raises(ValueError, match="accounting"):
            runner.check_state(model, value, 2e-9)
        cubic = np.zeros((4, model.coordinates.size))
        cubic[1, 0] = cubic[1, model.coordinates.leak.start] = -80
        cubic[2, 0] = cubic[2, model.coordinates.leak.start] = 80
        runner.check_state(model, cubic[0], 2e-9)
        runner.check_state(model, cubic.sum(axis=0), 2e-9)
        with pytest.raises(ValueError, match="curve"):
            ref.check_curve(model, cubic)


def test_live_bad_rhs_cannot_publish_a_checkpoint(
    tmp_path, protocol, short_references, monkeypatch
):
    derivative = evaluation.PreparedModel.derivative

    def corrupt(self, values, **kwargs):
        result = derivative(self, values, **kwargs)
        result[self.coordinates.leak.start] += 1
        return result

    monkeypatch.setattr(evaluation.PreparedModel, "derivative", corrupt)
    with pytest.raises(ValueError, match="accounting"):
        execute(tmp_path, protocol, short_references)
    failed = ref.read_json(tmp_path / "run/failure.json")
    assert failed["committed_chunks"] == 0 and failed["no_automatic_retry"]


def test_independent_stage_audit_does_not_use_cache_or_writer_decoder(
    tmp_path, protocol, short_references, monkeypatch
):
    folder, _, _, _, _ = execute(tmp_path, protocol, short_references)
    original = prep.graph.Model(short_references[1]["case"])

    def forbidden(*args, **kwargs):
        raise AssertionError("cached RHS or writer decoder was called")

    monkeypatch.setattr(evaluation.PreparedModel, "derivative", forbidden)
    monkeypatch.setattr(evidence, "decode_window", forbidden)
    result = audit.audit_stage_rhs(folder, original.case, original.panel, perf_counter() + 60)
    assert result["complete_RHS_evaluations"] == 20


@pytest.mark.parametrize("stage", range(5))
def test_independent_stage_audit_refuses_a_changed_slope(
    tmp_path, protocol, short_references, monkeypatch, stage
):
    folder, _, _, _, _ = execute(tmp_path, protocol, short_references)
    with closing(evidence.chunks(folder)) as stream:
        windows = [(entry, {k: v.copy() for k, v in data.items()}) for entry, data in stream]
    windows[0][1]["slopes"][0, stage, -1] += 0.0001

    def forged(*args, **kwargs):
        yield from windows

    monkeypatch.setattr(evidence, "chunks", forged)
    original = prep.graph.Model(short_references[1]["case"])
    with pytest.raises(ValueError, match="stage RHS"):
        audit.audit_stage_rhs(folder, original.case, original.panel, perf_counter() + 60)


def test_registered_probes_are_deterministic_and_complete():
    a, b = profile.exact_probes(), profile.exact_probes()
    assert a == b
    assert len(a["cases"]) == 45
    assert a["prepared_RHS_evaluations"] == 1440
    assert a["decomposed_evaluations"] == 720


@pytest.mark.parametrize("calls", [0, 257, True, 1.0])
def test_microprofile_call_budget_is_explicit(model, calls):
    with pytest.raises(ValueError, match="cap"):
        profile.microprofile(model.case, "scalar_cached", calls)


def test_real_registration_keeps_prior_caps_and_separates_evaluator_identity():
    r = profile.specification(profile.OUTPUT_PARENT / "evaluation-01")
    r["source_hashes"] = {name: ref.sha(profile.ROOT / name) for name in profile.SOURCES}
    assert len(profile.SOURCES) == len(set(profile.SOURCES)) == 74
    assert r["storage_budget"]["prior_bytes"] == 831126114
    assert r["storage_budget"]["new_root_limit_bytes"] == 242615710
    assert len(r["planned_attempts"]) == 12
    for case in r["plan"]["cases"]:
        a, b = [profile.identity(r, case, p) for p in evaluation.POLICIES]
        assert (
            a["integration_evaluation"]["model_sha256"]
            == b["integration_evaluation"]["model_sha256"]
        )
        assert a != b


@pytest.fixture
def registration_fixture(tmp_path, monkeypatch, protocol):
    source = tmp_path / "fixture.txt"
    source.write_text("D041 fixture\n")
    spec = {
        "resources": protocol["resources"],
        "runtime": prep.runtime(),
        "storage_budget": {"new_root_limit_bytes": protocol["resources"]["artifact_budget_bytes"]},
        "planned_attempts": ["first/scalar_frozen", "first/scalar_cached"],
    }
    monkeypatch.setattr(profile, "ROOT", tmp_path)
    monkeypatch.setattr(profile, "SOURCES", ["fixture.txt"])
    monkeypatch.setattr(profile, "specification", lambda output: copy.deepcopy(spec))
    monkeypatch.setattr(profile, "exact_probes", lambda: {"status": "pass"})
    for key, value in profile.campaign.THREADS.items():
        monkeypatch.setenv(key, value)
    return tmp_path / "new", source


def test_registration_is_exclusive_and_source_pinned(registration_fixture):
    output, source = registration_fixture
    registered = profile.register(output)
    assert profile.check_registration(output) == registered
    with pytest.raises(FileExistsError):
        profile.register(output)
    source.write_text("changed\n")
    with pytest.raises(ValueError, match="source identity"):
        profile.check_registration(output)


@pytest.mark.parametrize("timeout", [False, True])
def test_profile_failure_stops_without_retry(registration_fixture, monkeypatch, timeout):
    output, _ = registration_fixture
    calls = []

    def stop(command, **kwargs):
        calls.append(command)
        if timeout:
            raise subprocess.TimeoutExpired(command, kwargs["timeout"])
        return subprocess.CompletedProcess(command, 1)

    monkeypatch.setattr(profile.subprocess, "run", stop)
    with pytest.raises((ValueError, subprocess.TimeoutExpired)):
        profile.run(output)
    failed = ref.read_json(output / "failure.json")
    assert len(calls) == 1 and failed["no_automatic_retry"]
    assert failed["not_started"] == ["first/scalar_cached"]
    with pytest.raises(ValueError, match="Closed evaluation session"):
        profile.worker(output, "first/scalar_cached")


@pytest.mark.parametrize("policy", evaluation.POLICIES)
@pytest.mark.parametrize(
    "change", ["none", "calls", "identity", "nan_time", "array_estimate", "micro_calls"]
)
def test_worker_and_evaluation_receipt_checks(
    tmp_path, protocol, short_references, monkeypatch, policy, change
):
    import json
    from datetime import datetime, timezone

    directories, selected = short_references
    key = f"fixture/{policy}"
    registered = {
        "cases": {
            "fixture": {
                "selected": selected,
                "trajectories": {name: str(path) for name, path in directories.items()},
            }
        },
        "plan": {
            "step": 0.01,
            "duration": 0.037,
            "window_steps": 2,
            "readout_policy": "batched_cached",
            "trajectory_policy": "rk4_basis",
            "comparison_policy": "trajectory_backed",
            "microprofile_calls": 1,
        },
        "resources": protocol["resources"],
        "numerics": protocol["numerics"],
        "storage_budget": {"new_root_limit_bytes": protocol["resources"]["artifact_budget_bytes"]},
        "planned_attempts": [key],
        "observation_times": [0, 0.013, 0.031, 0.037],
        "source_hashes": {"fixture": "D041"},
        "runtime": prep.runtime(),
    }
    ref.write_json(tmp_path / "registration.json", registered)
    ref.write_json(
        tmp_path / "session.json",
        {
            "registration_sha256": ref.sha(tmp_path / "registration.json"),
            "automatic_retry": False,
            "started_utc": datetime.now(timezone.utc).isoformat(),
        },
    )
    (tmp_path / "attempts.jsonl").write_text(json.dumps({"key": key}) + "\n")
    monkeypatch.setattr(profile, "check_registration", lambda output: registered)
    for name, value in profile.campaign.THREADS.items():
        monkeypatch.setenv(name, value)
    profile.worker(tmp_path, key)
    folder = tmp_path / key
    measured = ref.read_json(folder / "profile.json")
    trajectory = ref.read_json(folder / "trajectory.json")
    _, _, resources = profile.execution(registered, key)
    audit.check_evaluation(
        folder, measured, trajectory, selected["case"], policy, resources, registered["plan"]
    )
    if change == "none":
        checked = audit.audit_stage_rhs(
            folder, selected["case"], prep.graph.eq.load_panel(), perf_counter() + 60
        )
        assert checked["complete_RHS_evaluations"] == measured["evaluation"]["rhs_calls"] == 20
        return
    if change == "calls":
        measured["evaluation"]["rhs_calls"] -= 1
    elif change == "identity":
        measured["evaluation"]["model_sha256"] = "f" * 64
    elif change == "nan_time":
        measured["evaluation"]["rhs_seconds"] = np.nan
    elif change == "array_estimate":
        measured["aggregate_array_estimate_bytes"] -= 1
    else:
        micro = ref.read_json(folder / "rhs-profile.json")
        micro["calls"] = 2
        (folder / "rhs-profile.json").write_text(json.dumps(micro))
        measured["rhs_profile_sha256"] = ref.sha(folder / "rhs-profile.json")
    with pytest.raises(ValueError, match="Integration evaluator/profile"):
        audit.check_evaluation(
            folder, measured, trajectory, selected["case"], policy, resources, registered["plan"]
        )
