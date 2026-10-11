"""D038 instantaneous and short-fixture tests, never a long candidate study."""

import copy
import json
import subprocess
from time import perf_counter

import numpy as np
import pytest

from scripts import audit_graph_diagnostics as audit
from scripts import profile_graph_diagnostics as profile
from tests import reference_graph_diagnostics as diagnostics
from tests import source_graph_fixtures as fixtures

ref, prep, candidate = profile.ref, profile.prep, profile.candidate


def increments(model, count):
    values = np.zeros((count, model.coordinates.size))
    values[:, : 6 * model.n] = np.arange(count)[:, None] * 0.0001
    values[:, model.n : 2 * model.n] = 0  # Equal Na/Cl perturbations preserve charge.
    return values


@pytest.mark.parametrize("case", fixtures.cases(), ids=lambda case: case["id"])
@pytest.mark.parametrize("width", [1, 17])
def test_existing_graph_fixture_full_readouts_match_scalar(case, width):
    model = prep.graph.Model(case)
    cache = diagnostics.BatchedReadouts(model)
    values = increments(model, width)
    before = values.copy()
    expected = prep.observed(model, values)
    actual = cache.observed(values)
    scores = diagnostics.readout_scores(
        actual, expected, fixtures.definition()["instantaneous_tolerances"]
    )
    assert max(scores.values()) <= 1
    np.testing.assert_array_equal(values, before)
    primary = values[:, : 6 * model.n].reshape(-1, 6, model.n) + model.anchor
    complete = cache.evaluate(primary)
    scalar = [model.evaluate(value) for value in primary]
    assert set(complete) == set(scalar[0])
    for name, value in complete.items():
        np.testing.assert_allclose(
            value,
            np.array([r[name] for r in scalar]),
            rtol=2e-12,
            atol=5e-21 if "flux" in name else 5e-12,
        )
    np.testing.assert_array_equal(actual["packet"][:, prep.graph.eq.PRIMARY_INDEX], primary)
    np.testing.assert_array_equal(
        actual["packet"][:, prep.graph.eq.CONTEXT_INDEX],
        np.broadcast_to(model.context, (width, 3, model.n)),
    )


@pytest.fixture
def model():
    return prep.graph.Model(next(case for case in fixtures.cases() if case["id"] == "G07"))


@pytest.mark.parametrize("width", [1, 2, 3, 16, 31, 256])
def test_batch_width_stride_and_chunking_do_not_mutate_inputs(model, width):
    cache = diagnostics.BatchedReadouts(model)
    backing = np.zeros((width * 2, model.coordinates.size * 2))
    values = backing[::2, ::2]
    values[:] = increments(model, width)
    expected = prep.observed(model, values)
    actual = cache.observed(values)
    assert (
        max(
            diagnostics.readout_scores(
                actual, expected, fixtures.definition()["instantaneous_tolerances"]
            ).values()
        )
        <= 1
    )
    separately = {
        key: np.concatenate([cache.observed(values[i : i + 1])[key] for i in range(width)])
        for key in actual
    }
    assert (
        max(
            diagnostics.readout_scores(
                actual, separately, fixtures.definition()["instantaneous_tolerances"]
            ).values()
        )
        <= 1
    )
    assert not np.any(backing[1::2]) and not np.any(backing[:, 1::2])


def test_cache_is_an_immutable_snapshot_and_outputs_do_not_alias_it(model):
    cache = diagnostics.BatchedReadouts(model)
    values = increments(model, 3)
    expected = cache.observed(values)
    identity = cache.cache_identity
    model.case["controls"]["pump"][0] = 0
    model.panel["bath_ions"][0] *= 2
    model.case["context"][1][0] = 10
    for name, value in cache.observed(values).items():
        np.testing.assert_array_equal(value, expected[name])
    assert cache.cache_identity == identity
    with pytest.raises(ValueError):
        cache.anchor[0, 0] = 1
    with pytest.raises(ValueError):
        cache.controls["leak"][0, 0] = 0
    with pytest.raises(TypeError):
        cache.p["F"] = 1
    expected["packet"][:] = 0
    assert np.any(cache.observed(values)["packet"])


@pytest.mark.parametrize("width", [0, 257, True, 2.0])
def test_invalid_batch_capacity_refused(model, width):
    with pytest.raises(ValueError, match="capacity"):
        diagnostics.BatchedReadouts(model, max_samples=width)


def test_array_budget_is_checked_before_model_copy(model, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Model copied before array preflight")

    monkeypatch.setattr(prep.graph.Model, "__init__", forbidden)
    with pytest.raises(ref.BudgetExceeded, match="array estimate"):
        diagnostics.BatchedReadouts(model, array_budget_bytes=1)


@pytest.mark.parametrize(
    "kind",
    ["empty", "too_wide", "float32", "wrong_size", "wrong_axis", "nan", "inf", "object", "list"],
)
def test_invalid_complete_readout_batches_refused(model, kind):
    cache = diagnostics.BatchedReadouts(model, max_samples=3)
    values = increments(model, 2)
    if kind == "empty":
        values = values[:0]
    elif kind == "too_wide":
        values = increments(model, 4)
    elif kind == "float32":
        values = values.astype(np.float32)
    elif kind == "wrong_size":
        values = values[:, :-1]
    elif kind == "wrong_axis":
        values = values.T
    elif kind in ("nan", "inf"):
        values[1, -1] = np.nan if kind == "nan" else np.inf
    elif kind == "object":
        values = values.astype(object)
    else:
        values = values.tolist()
    with pytest.raises(ValueError):
        cache.observed(values)


@pytest.mark.parametrize("coordinate,value", [(0, 0), (0, 1001), (3, -1), (3, 1001), (0, 10.1)])
def test_primary_and_voltage_domains_match_scalar(coordinate, value):
    model = prep.graph.Model(prep.preparations()["E"])
    cache = diagnostics.BatchedReadouts(model)
    primary = model.anchor.copy()
    primary[coordinate, 0] = value
    with pytest.raises(ValueError):
        model.evaluate(primary)
    with pytest.raises(ValueError):
        cache.evaluate(primary[None])


def test_electrical_exponent_guard_matches_scalar():
    panel = prep.graph.eq.load_panel()
    panel["parameters"]["F"] = 1e8
    model = prep.graph.Model(prep.preparations()["E"], panel)
    primary = model.anchor.copy()
    primary[0, 0] += 0.05 / (
        panel["parameters"]["F"] * model.volume / (model.area * panel["parameters"]["cm"])
    )
    with pytest.raises(ValueError, match="exponent"):
        model.evaluate(primary)
    with pytest.raises(ValueError, match="exponent"):
        diagnostics.BatchedReadouts(model).evaluate(primary[None])


def test_readout_field_shape_and_value_identity_is_explicit(model):
    value = diagnostics.BatchedReadouts(model).observed(increments(model, 2))
    tolerances = fixtures.definition()["instantaneous_tolerances"]
    altered = {k: v.copy() for k, v in value.items()}
    original = diagnostics.fingerprint(value)
    altered["voltage"][0, 0] += 1e-6
    assert diagnostics.fingerprint(altered) != original
    assert diagnostics.readout_scores(altered, value, tolerances)["voltage"] > 1
    altered["voltage"][0, 0] = np.nan
    with pytest.raises(ValueError, match="shape/precision/values"):
        diagnostics.readout_scores(altered, value, tolerances)
    with pytest.raises(ValueError, match="inventory"):
        diagnostics.readout_scores({}, value, tolerances)


@pytest.fixture(scope="module")
def short_references(tmp_path_factory):
    root = tmp_path_factory.mktemp("diagnostic-references")
    protocol = profile.campaign.frozen.load_protocol()
    case = prep.preparations()["E"]
    selected = {
        "case": case,
        "duration": 0.08,
        "methods": {k: list(v) for k, v in profile.campaign.METHODS.items()},
        "numerics": protocol["numerics"],
    }
    directories = {}
    for key, (method, refinement) in selected["methods"].items():
        directories[key] = root / key
        candidate.paths.integrate(
            prep.graph.Model(case),
            root / key,
            method=method,
            refinement=refinement,
            duration=selected["duration"],
            numerics=selected["numerics"],
            resources=protocol["resources"] | {"window_steps": 2},
            artifact_root=root,
        )
    return directories, selected, protocol


def short_run(tmp_path, short_references, policy, *, comparison_class=diagnostics.Comparison):
    directories, selected, protocol = short_references
    resources = protocol["resources"] | {"window_steps": 2}
    output = tmp_path / policy
    consumer = comparison_class(
        directories,
        selected,
        output,
        tmp_path,
        resources,
        [0, 0.013, 0.031, 0.037],
        **({} if policy == "original" else {"policy": policy}),
    )
    result = candidate.integrate(
        prep.graph.Model(selected["case"]),
        output,
        step=0.01,
        end=0.037,
        numerics=selected["numerics"],
        resources=resources,
        identity={"short_diagnostic_fixture": True},
        artifact_root=tmp_path,
        comparison=consumer,
    )
    return output, result, consumer, resources


def test_both_policies_preserve_frozen_comparison_and_independent_audits(
    tmp_path, short_references
):
    directories, selected, _ = short_references
    records = {}
    original, reference_result, _, _ = short_run(
        tmp_path, short_references, "original", comparison_class=diagnostics.original.Comparison
    )
    for policy in diagnostics.POLICIES:
        folder, result, consumer, resources = short_run(tmp_path, short_references, policy)
        assert result["comparison"]["scores"] == reference_result["comparison"]["scores"]
        for (a, arrays), (b, expected) in zip(
            diagnostics.original.chunks(folder, comparison=True),
            diagnostics.original.chunks(original, comparison=True),
            strict=True,
        ):
            assert a["samples"] == b["samples"]
            assert set(a["readout_hashes"]) == {"candidate", *directories}
            for name, values in arrays.items():
                np.testing.assert_array_equal(values, expected[name])
        records[policy] = audit.old.audit_samples(
            folder, directories, selected, [0, 0.013, 0.031, 0.037], resources, perf_counter() + 60
        )
        checked = audit.audit_readouts(
            folder,
            selected,
            policy,
            fixtures.definition()["instantaneous_tolerances"],
            resources,
            perf_counter() + 60,
        )
        assert checked["maximum_scalar_difference_score"] <= 1
        assert checked["all_eight_candidate_scores_recomputed"]
        assert all(reader._iterator.gi_frame is None for reader in consumer.readers.values())
    assert (
        records["scalar_frozen"]["ordered_sample_arrays_sha256"]
        == records["batched_cached"]["ordered_sample_arrays_sha256"]
    )


def test_readout_fingerprint_tamper_is_detected_independently(tmp_path, short_references):
    _, selected, _ = short_references
    folder, _, _, resources = short_run(tmp_path, short_references, "batched_cached")
    path = folder / "comparison/chunks.jsonl"
    entries = [json.loads(line) for line in path.read_text().splitlines()]
    entries[0]["readout_hashes"]["candidate"] = "0" * 64
    path.write_text("".join(json.dumps(entry) + "\n" for entry in entries))
    with pytest.raises(ValueError, match="fingerprint differs"):
        audit.audit_readouts(
            folder,
            selected,
            "batched_cached",
            fixtures.definition()["instantaneous_tolerances"],
            resources,
            perf_counter() + 60,
        )


def test_batched_readout_failure_is_retained_without_scalar_fallback(
    tmp_path, short_references, monkeypatch
):
    directories, selected, protocol = short_references
    calls = []

    def broken(self, values):
        calls.append(len(values))
        raise ValueError("fixture readout refusal")

    monkeypatch.setattr(diagnostics.BatchedReadouts, "observed", broken)
    resources = protocol["resources"] | {"window_steps": 2}
    output = tmp_path / "failed"
    consumer = diagnostics.Comparison(
        directories, selected, output, tmp_path, resources, [0, 0.037], policy="batched_cached"
    )
    with pytest.raises(ValueError, match="fixture readout refusal"):
        candidate.integrate(
            prep.graph.Model(selected["case"]),
            output,
            step=0.01,
            end=0.037,
            numerics=selected["numerics"],
            resources=resources,
            identity={"fixture": True},
            artifact_root=tmp_path,
            comparison=consumer,
        )
    failed = ref.read_json(output / "failure.json")
    assert calls == [2] and failed["steps"] == 2 and failed["completed_chunks"] == 1
    assert not (output / "trajectory.json").exists()
    assert all(reader._iterator.gi_frame is None for reader in consumer.readers.values())


def test_real_profile_scope_capsule_and_shared_quota():
    r = profile.specification(profile.OUTPUT_PARENT / "diagnostics-01")
    assert len(r["planned_attempts"]) == 12 and len(profile.SOURCES) == 55
    assert r["plan"]["window_steps"] == 256 and r["plan"]["duration"] == 5.12
    assert r["plan"]["policies"] == ["scalar_frozen", "batched_cached"]
    assert r["storage_budget"]["prior_bytes"] == 783644175
    assert r["storage_budget"]["new_root_limit_bytes"] == 290097649
    assert not r["plan"]["compact_evidence_used"] and not r["plan"]["long_study_run"]
    assert r["readout_tolerances"] == fixtures.definition()["instantaneous_tolerances"]
    assert len(r["production_source_hashes"]) == 39 and len(r["parent_results"]) == 12


@pytest.fixture
def registration_fixture(tmp_path, monkeypatch):
    source = tmp_path / "fixture.txt"
    source.write_text("fixture source\n")
    protocol = profile.campaign.frozen.load_protocol()
    spec = {
        "resources": protocol["resources"],
        "runtime": prep.runtime(),
        "planned_attempts": ["first/scalar_frozen", "first/batched_cached"],
    }
    monkeypatch.setattr(profile, "ROOT", tmp_path)
    monkeypatch.setattr(profile, "SOURCES", ["fixture.txt"])
    monkeypatch.setattr(profile, "specification", lambda output: copy.deepcopy(spec))
    for key, value in profile.campaign.THREADS.items():
        monkeypatch.setenv(key, value)
    return tmp_path / "new", source


def test_registration_roundtrip_source_identity_and_exclusivity(registration_fixture):
    output, source = registration_fixture
    registered = profile.register(output)
    assert profile.check_registration(output) == registered
    with pytest.raises(FileExistsError):
        profile.register(output)
    source.write_text("modified fixture source\n")
    with pytest.raises(ValueError, match="source identity"):
        profile.check_registration(output)


@pytest.mark.parametrize("timeout", [False, True])
def test_one_worker_stops_on_failure_or_timeout_without_retry(
    registration_fixture, monkeypatch, timeout
):
    output, _ = registration_fixture
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        if timeout:
            raise subprocess.TimeoutExpired(command, kwargs["timeout"])
        return subprocess.CompletedProcess(command, 1)

    monkeypatch.setattr(profile.subprocess, "run", run)
    with pytest.raises((ValueError, subprocess.TimeoutExpired)):
        profile.run(output)
    failed = ref.read_json(output / "failure.json")
    assert len(calls) == 1 and failed["no_automatic_retry"]
    assert failed["not_started"] == ["first/batched_cached"]
    with pytest.raises(ValueError, match="Closed diagnostic session"):
        profile.worker(output, "first/batched_cached")
