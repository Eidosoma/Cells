"""Bounded reference infrastructure checks; no 500-unit trajectory in pytest."""

import copy
import inspect
import json
from time import perf_counter

import numpy as np
import pytest

from scripts import audit_source_preparations as audit
from scripts import check_e02_protocol as frozen
from scripts import qualify_source_preparations as campaign
from tests import reference_source_graph as graph
from tests import reference_source_graph_numerics as ref
from tests import source_graph_fixtures as fixtures


@pytest.fixture
def protocol():
    return frozen.load_protocol()


@pytest.fixture
def model():
    return graph.Model(campaign.preparations()["E"])


@pytest.mark.parametrize("label", ["E", "M"])
def test_exact_preparation_seed(protocol, label):
    case = campaign.preparations()[label]
    m = graph.Model(case)
    old = next(c for c in fixtures.cases() if c["id"] == f"prepare_seed/{label}")
    for key in set(old) - {"id", "origin"}:
        assert case[key] == old[key]
    assert m.coordinates.size == 13 and m.n == 1 and m.e == 0
    np.testing.assert_array_equal(
        m.anchor[:, 0],
        protocol["preparation"]["initial_ions"]
        + protocol["preparation"]["initial_regulation"][label],
    )
    assert len(campaign.preparation_times(protocol)) == 505


@pytest.mark.parametrize("label", ["E", "M"])
def test_bounded_jacobian_initial_boundary(label):
    m = graph.Model(campaign.preparations()[label])
    y = np.zeros(13)
    checked = ref.check_jacobian(m, y)
    assert checked["maximum_score"] <= 1
    assert any("one_sided" in s for s in checked["primary_column_schemes"])
    j = ref.jacobian(m, y, lambda v: m.derivative(v, increments=True))
    np.testing.assert_array_equal(j[:, 6:], np.zeros((13, 7)))


@pytest.mark.parametrize("name", ["G00", "G01", "G02", "G06", "G07", "G10", "G11"])
def test_graph_curve_accounting_and_passive_columns(name):
    case = next(c for c in fixtures.cases() if c["id"] == name)
    m = graph.Model(case)
    slope = m.derivative(np.zeros(m.coordinates.size), increments=True)
    c = np.array([np.zeros(m.coordinates.size), 1e-8 * slope])
    assert ref.check_curve(m, c)["maximum_accounting_residual"] < 1e-12
    np.testing.assert_allclose(ref.residual(m, c), 0, atol=1e-18)


def test_interior_negative_refused_despite_valid_endpoints(model):
    c = np.zeros((3, 13))
    c[1, 4] = c[1, 11] = -1
    c[2, 4] = c[2, 11] = 1
    for theta in (0, 1):
        model.validate_primary(ref.absolute(model, ref.evaluate_polynomial(c, theta))[:6, None])
    with pytest.raises(ValueError, match="Whole dense curve"):
        ref.check_curve(model, c)
    with pytest.raises(ValueError, match="whole-curve"):
        audit.check_coefficients(c, model.case, model.panel)


def test_interior_accounting_error_refused(model):
    c = np.zeros((3, 13))
    c[1, 6], c[2, 6] = 1e-6, -1e-6
    with pytest.raises(ValueError, match="accounting"):
        ref.check_curve(model, c)


def test_affine_voltage_interior_refused(model):
    c = np.zeros((3, 13))
    c[1, 0] = c[1, 6] = 4
    c[2, 0] = c[2, 6] = -4
    with pytest.raises(ValueError, match="electrical domain"):
        ref.check_curve(model, c)


@pytest.mark.parametrize("method,refinement", [("Radau", 1.0), ("BDF", 1.0), ("Radau", 0.1)])
def test_streamed_dense_identity_and_audit(tmp_path, model, protocol, method, refinement):
    resources = protocol["resources"] | {"window_steps": 2}
    folder = tmp_path / "trajectory"
    report = ref.integrate(
        model,
        folder,
        method=method,
        refinement=refinement,
        duration=0.03,
        numerics=protocol["numerics"],
        resources=resources,
        artifact_root=tmp_path,
    )
    assert report["end"] == 0.03 and report["chunks"] > 1
    t = ref.Trajectory(folder)
    items = list(t.chunks())  # Tiny test only; the runner never accumulates trajectory chunks.
    assert max(len(i["degrees"]) for i in items) == 2
    samples = np.array([0, 0.00113, 0.02, 0.03])
    values = t.sample(samples)
    assert np.max(abs(ref.residual(model, values))) < 2e-9
    raw = np.zeros(13)
    for item in items:
        np.testing.assert_array_equal(item["increments"][0], raw)
        raw = item["increments"][-1]
        for c in item["coefficients"]:
            audit.check_coefficients(c, model.case, model.panel)
    np.testing.assert_array_equal(values[-1], raw)
    with pytest.raises(ValueError, match="monotone"):
        t.sample([0.02])
    with pytest.raises(ValueError, match="in range"):
        ref.Trajectory(folder).sample([0.031])
    # Changing a payload cannot be hidden behind a valid original index.
    with (folder / "chunk-000000.npz").open("ab") as handle:
        handle.write(b"corrupt")
    with pytest.raises(ValueError, match="chunk hash"):
        next(ref.Trajectory(folder).chunks())


@pytest.mark.parametrize(
    "resource,value,match",
    [
        ("rhs_calls_per_reference_trajectory", 1, "RHS-call"),
        ("max_steps_per_trajectory", 0, "accepted-step"),
        ("worker_timeout_seconds", 0, "wall budget"),
    ],
)
def test_incomplete_is_not_pass(tmp_path, model, protocol, resource, value, match):
    folder = tmp_path / "limited"
    with pytest.raises(ref.BudgetExceeded, match=match):
        ref.integrate(
            model,
            folder,
            method="Radau",
            refinement=1.0,
            duration=0.03,
            numerics=protocol["numerics"],
            resources=protocol["resources"] | {resource: value},
            artifact_root=tmp_path,
        )
    assert not (folder / "trajectory.json").exists()
    assert ref.read_json(folder / "failure.json")["status"] == "incomplete"


def test_artifact_refusal_before_write(tmp_path):
    path = tmp_path / "not-written.npz"
    with pytest.raises(ref.BudgetExceeded, match="before writing"):
        ref.save_arrays(path, {"data": np.zeros(10)}, tmp_path, 10)
    assert not path.exists()


def test_exact_new_output_only(tmp_path, model, protocol):
    with pytest.raises(FileExistsError):
        ref.integrate(
            model,
            tmp_path,
            method="Radau",
            refinement=1.0,
            duration=0.1,
            numerics=protocol["numerics"],
            resources=protocol["resources"],
            artifact_root=tmp_path,
        )


@pytest.mark.parametrize(
    "method,refinement,duration", [("RK45", 1, 1), ("Radau", 0.01, 1), ("Radau", 1, 0)]
)
def test_unregistered_method_refused(tmp_path, model, protocol, method, refinement, duration):
    with pytest.raises(ValueError):
        ref.integrate(
            model,
            tmp_path / "invalid",
            method=method,
            refinement=refinement,
            duration=duration,
            numerics=protocol["numerics"],
            resources=protocol["resources"],
            artifact_root=tmp_path,
        )


def test_merge_preserves_all_endpoints_midpoints_observers():
    batches = list(campaign.unique_batches([iter([0, 0.1, 1]), iter([0, 0.05, 0.1, 0.113, 1])], 2))
    assert max(map(len, batches)) == 2
    np.testing.assert_array_equal(np.concatenate(batches), [0, 0.05, 0.1, 0.113, 1])


def test_diagnostics_include_binding_and_ledgers(model, protocol):
    expected = np.zeros((1, 13))
    actual = expected.copy()
    actual[0, 11] = 1e-3
    read = campaign.observed(model, expected)
    scores = campaign.comparison_scores(
        model, actual, expected, read, read, protocol["numerics"]["targets"]
    )
    assert scores["regulatory_history"] > 1 and scores["regulatory_state"] == 0
    altered = copy.deepcopy(read)
    altered["binding_cache"] += 1e-3
    scores = campaign.comparison_scores(
        model, expected, expected, altered, read, protocol["numerics"]["targets"]
    )
    assert scores["binding_cache"] > 1


def test_no_production_or_native_imports():
    for module in (ref, campaign, audit):
        source = inspect.getsource(module)
        assert "import cells" not in source and "from cells" not in source
        assert "import bitsey" not in source and "import zombie" not in source


def test_json_nonfinite_and_overwrite_refused(tmp_path):
    path = tmp_path / "receipt.json"
    with pytest.raises(ValueError):
        ref.write_json(path, {"value": float("nan")})
    assert not path.exists()
    ref.write_json(path, {"value": 1})
    with pytest.raises(FileExistsError):
        ref.write_json(path, {"value": 2})
    assert json.loads(path.read_text()) == {"value": 1}


@pytest.mark.parametrize("width", [0, 257, -1, True, 2.5])
def test_comparison_batch_bound_refused(width):
    with pytest.raises(ValueError, match="batch width"):
        list(campaign.unique_batches([iter([0, 1])], width))


def test_small_full_reference_comparison_and_criteria(tmp_path, protocol):
    # Engineering smoke case, explicitly not a shortened scientific preparation.
    short = copy.deepcopy(protocol)
    short["preparation"]["duration"] = 1.0
    short["preparation"]["qualification_window"] = [0.0, 1.0]
    short["resources"]["window_steps"] = 16
    for label, case in campaign.preparations(short).items():
        for variant, (method, refinement) in campaign.METHODS.items():
            ref.integrate(
                graph.Model(case),
                tmp_path / label / variant,
                method=method,
                refinement=refinement,
                duration=1.0,
                numerics=short["numerics"],
                resources=short["resources"],
                artifact_root=tmp_path,
            )
        result = campaign.compare_label(tmp_path, label, short, perf_counter() + 60)
        assert result["status"] == "pass" and result["samples"] > 10
        assert result["maximum_score"] <= 0.1
    criteria, packets = campaign.preparation_criteria(tmp_path, short)
    assert criteria["status"] == "pass" and set(packets) == {"E", "M"}
    assert packets["E"]["phase_end"] == 1.0
    assert not (tmp_path / "prepared-packets.json").exists()


def test_unqualified_criteria_do_not_publish_packets(tmp_path, monkeypatch):
    monkeypatch.setattr(campaign, "check_registration", lambda path: {})
    monkeypatch.setattr(campaign, "compare_label", lambda *args: {"status": "pass"})
    monkeypatch.setattr(
        campaign, "preparation_criteria", lambda *args: ({"status": "unqualified"}, {})
    )
    ref.write_json(tmp_path / "registration.json", {})
    with pytest.raises(ValueError, match="no prepared packets"):
        campaign.qualify(tmp_path, perf_counter() + 10)
    assert ref.read_json(tmp_path / "qualification.json")["status"] == "unqualified"
    assert not (tmp_path / "prepared-packets.json").exists()


def test_reference_disagreement_does_not_publish_packets(tmp_path, monkeypatch):
    monkeypatch.setattr(campaign, "check_registration", lambda path: {})
    monkeypatch.setattr(campaign, "compare_label", lambda *args: {"status": "unqualified"})
    monkeypatch.setattr(campaign, "preparation_criteria", lambda *args: ({"status": "pass"}, {}))
    ref.write_json(tmp_path / "registration.json", {})
    with pytest.raises(ValueError, match="no prepared packets"):
        campaign.qualify(tmp_path, perf_counter() + 10)
    assert not (tmp_path / "prepared-packets.json").exists()


def test_missing_index_tail_refused_before_endpoint_sampling(tmp_path, model, protocol):
    folder = tmp_path / "trajectory"
    ref.integrate(
        model,
        folder,
        method="Radau",
        refinement=1.0,
        duration=0.03,
        numerics=protocol["numerics"],
        resources=protocol["resources"] | {"window_steps": 2},
        artifact_root=tmp_path,
    )
    original = ref.read_json(folder / "trajectory.json")
    with pytest.raises(ValueError, match="Incomplete reference index"):
        ref.validate_chunk_index(folder, original | {"chunks": original["chunks"] + 1})


def test_registered_settings_are_checked(tmp_path):
    campaign.register(tmp_path / "registration")
    report = campaign.check_registration(tmp_path / "registration")
    assert len(report["planned_attempts"]) == 6
    assert len(report["production_source_hashes"]) == 39
