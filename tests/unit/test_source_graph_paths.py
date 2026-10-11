"""Short engineering tests only: none execute a 1000-unit scientific path."""

import copy
import inspect
import json
import subprocess
from time import perf_counter

import numpy as np
import pytest

from scripts import audit_source_graph_paths as audit
from scripts import check_e02_protocol as frozen
from scripts import qualify_source_graph_paths as campaign
from scripts import qualify_source_preparations as prep
from tests import reference_graph_paths as paths
from tests import reference_source_graph as graph
from tests import reference_source_graph_numerics as ref


@pytest.fixture
def protocol():
    return frozen.load_protocol()


@pytest.mark.parametrize("item", frozen.case_inventory(), ids=lambda item: item["id"])
def test_exact_packet_transfer_and_generic_control_inventory(item):
    packet = campaign.prepared()
    case = campaign.cases(packet)[item["id"]]
    model = graph.Model(case)
    for i, label in enumerate(item["prepared_labels"]):
        expected = packet["packets"][label]
        np.testing.assert_array_equal(
            model.anchor[:, i], np.asarray(expected["prepared_primary"])[:, 0]
        )
        np.testing.assert_array_equal(model.context[:, i], np.asarray(expected["context"])[:, 0])
        assert np.any(np.asarray(expected["complete_increment_state"])[6:] != 0)
    assert case["cell_ids"] == item["cell_ids"] and case["edges"] == item["edges"]
    assert model.coordinates.size == item["reference_coordinate_count"]
    assert case["controls"]["ion_contact"] == item["ion_contact"]
    assert case["controls"]["mirna_contact"] == item["mirna_contact"]
    np.testing.assert_array_equal(model.initial()[6 * model.n :], 0)
    assert ref.check_jacobian(model, np.zeros(model.coordinates.size))["maximum_score"] <= 1


def test_missing_or_tampered_parent_refused(tmp_path):
    with pytest.raises(FileNotFoundError):
        campaign.prepared(tmp_path)
    ref.write_json(tmp_path / "prepared-packets.json", {"status": "qualified"})
    with pytest.raises(ValueError, match="Frozen input changed"):
        campaign.prepared(tmp_path)


def test_lossless_bits_and_compression(tmp_path):
    data = np.tile(np.array([0.0, -0.0, 1.0, np.nextafter(1.0, 2.0), np.nextafter(0.0, 1.0)]), 500)
    path = tmp_path / "bits.npz"
    paths.save_arrays(path, {"data": data}, tmp_path, 10_000_000)
    with np.load(path, allow_pickle=False) as result:
        assert result["data"].dtype == data.dtype
        np.testing.assert_array_equal(result["data"].view(np.uint64), data.view(np.uint64))
    assert path.stat().st_size < data.nbytes / 4
    digest = ref.sha(path)
    with pytest.raises(FileExistsError):
        paths.save_arrays(path, {"data": data}, tmp_path, 10_000_000)
    assert ref.sha(path) == digest


def test_quota_is_conservative_before_compression(tmp_path):
    path = tmp_path / "not-written.npz"
    with pytest.raises(ref.BudgetExceeded, match="before writing compressed"):
        paths.save_arrays(path, {"data": np.zeros(1000)}, tmp_path, paths.TAIL_RESERVE + 8000)
    assert not path.exists()


def test_writer_rejects_outside_budget_and_objects(tmp_path):
    with pytest.raises(ValueError, match="budget root"):
        paths.save_arrays(tmp_path.parent / "outside.npz", {"x": [1]}, tmp_path, 10_000_000)
    with pytest.raises(ValueError, match="Object arrays"):
        paths.save_arrays(tmp_path / "object.npz", {"x": np.array([{}])}, tmp_path, 10_000_000)


@pytest.mark.parametrize("method,refinement", campaign.METHODS.values())
def test_old_and_compressed_runner_bit_exact(tmp_path, protocol, method, refinement):
    model = graph.Model(prep.preparations()["E"])
    arguments = dict(
        method=method,
        refinement=refinement,
        duration=0.03,
        numerics=protocol["numerics"],
        resources=protocol["resources"] | {"window_steps": 2},
        artifact_root=tmp_path,
    )
    old = ref.integrate(model, tmp_path / "old", **arguments)
    new = paths.integrate(model, tmp_path / "new", **arguments)
    for key in (
        "end",
        "accepted_steps",
        "rhs_calls_including_solver_jacobian",
        "nfev",
        "njev",
        "nlu",
        "whole_curve",
        "dense_adapter_maximum_score",
        "jacobian_checks",
        "chunks",
    ):
        assert new[key] == old[key]
    assert new["chunks"] > 1
    for a, b in zip(
        ref.Trajectory(tmp_path / "old").chunks(),
        ref.Trajectory(tmp_path / "new").chunks(),
        strict=True,
    ):
        for name in a:
            np.testing.assert_array_equal(a[name], b[name])


@pytest.mark.parametrize("key", ["E_to_M/active", "M_to_E/one_neighbor", "E_to_M/isolated"])
@pytest.mark.parametrize("variant", list(campaign.METHODS))
def test_short_graph_dense_checks_and_separate_audit(tmp_path, protocol, key, variant):
    case = campaign.cases()[key]
    model = graph.Model(case)
    method, refinement = campaign.METHODS[variant]
    registration = {
        "methods": {k: list(v) for k, v in campaign.METHODS.items()},
        "numerics": protocol["numerics"],
        "resources": protocol["resources"] | {"window_steps": 2},
        "duration": 0.03,
    }
    paths.integrate(
        model,
        tmp_path / variant,
        method=method,
        refinement=refinement,
        duration=0.03,
        numerics=registration["numerics"],
        resources=registration["resources"],
        artifact_root=tmp_path,
    )
    checked = audit.audit_trajectory(
        tmp_path / variant, case, registration, model.panel, perf_counter() + 30
    )
    assert checked["maximum_accounting_residual"] <= 2e-9
    values = ref.Trajectory(tmp_path / variant).sample([0, 0.00113, 0.02, 0.03])
    assert np.max(abs(ref.residual(model, values))) <= 2e-9
    np.testing.assert_array_equal(values[:, ref.blocked_coordinates(model)], 0)


@pytest.mark.parametrize(
    "resource,value,match",
    [
        ("estimated_array_budget_bytes", 1, "working array"),
        ("rhs_calls_per_reference_trajectory", 1, "RHS-call"),
        ("max_steps_per_trajectory", 0, "accepted-step"),
        ("worker_timeout_seconds", 0, "wall budget"),
        ("artifact_budget_bytes", 1, "Artifact budget"),
    ],
)
def test_all_resource_refusals_retain_incomplete_receipt(
    tmp_path, protocol, resource, value, match
):
    folder = tmp_path / "limited"
    with pytest.raises(ref.BudgetExceeded, match=match):
        paths.integrate(
            graph.Model(campaign.cases()["E_to_M/active"]),
            folder,
            method="Radau",
            refinement=1,
            duration=0.03,
            numerics=protocol["numerics"],
            resources=protocol["resources"] | {resource: value},
            artifact_root=tmp_path,
        )
    assert ref.read_json(folder / "failure.json")["status"] == "incomplete"
    assert not (folder / "trajectory.json").exists()


def test_label_uncertainty_including_exact_boundary(protocol):
    primary = np.zeros((5, 6, 1))
    primary[:, 3, 0] = [4, 2, 0, 0, 2.000001]
    primary[:, 4, 0] = [0, 0, 4, 0, 0]
    targets = protocol["numerics"]["targets"]["regulatory_state_and_ledger"]
    raw, labels, allowance = campaign.labels_with_allowance(primary, np.zeros((5, 3, 1)), targets)
    np.testing.assert_array_equal(raw[:, 0], [1, 0, -1, 0, 1])
    np.testing.assert_array_equal(labels[:, 0], [1, 2, -1, 0, 2])
    assert np.all(allowance > 0)
    disagreement = np.zeros((5, 3, 1))
    disagreement[0, 0, 0] = 3
    assert campaign.labels_with_allowance(primary, disagreement, targets)[1][0, 0] == 2


def test_independent_graph_ledger_sign_and_blocked_history_audit():
    for key in ("E_to_M/active", "E_to_M/blocked"):
        model = graph.Model(campaign.cases()[key])
        slope = model.derivative(np.zeros(model.coordinates.size), increments=True)
        c = np.array([np.zeros(model.coordinates.size), 1e-6 * slope])
        assert audit.check_coefficients(c, model.case, model.panel) <= 2e-9
        c[1, model.coordinates.mirna.start] += 1e-4
        with pytest.raises(ValueError, match="accounting"):
            audit.check_coefficients(c, model.case, model.panel)


def test_interior_domain_excursion_independently_refused():
    model = graph.Model(campaign.cases()["E_to_M/active"])
    c = np.zeros((3, model.coordinates.size))
    c[1, 0] = c[1, model.coordinates.leak.start] = -40
    c[2] = -c[1]
    with pytest.raises(ValueError, match="whole-curve domain"):
        audit.check_coefficients(c, model.case, model.panel)
    with pytest.raises(ValueError, match="Whole dense curve"):
        ref.check_curve(model, c)


def test_short_trio_comparison_observations_and_no_switch_requirement(tmp_path, protocol):
    key = "E_to_M/active"
    spec = campaign.specification()
    spec["duration"], spec["observation_times"] = 0.03, [0, 0.0113, 0.02, 0.03]
    spec["observer"] = copy.deepcopy(spec["observer"])
    spec["observer"]["terminal_window"] = [0.02, 0.03]
    spec["resources"] = spec["resources"] | {"window_steps": 2}
    for variant, (method, refinement) in campaign.METHODS.items():
        paths.integrate(
            graph.Model(spec["cases"][key]),
            tmp_path / key / variant,
            method=method,
            refinement=refinement,
            duration=spec["duration"],
            numerics=spec["numerics"],
            resources=spec["resources"],
            artifact_root=tmp_path,
        )
    comparison = campaign.compare(tmp_path, key, spec, perf_counter() + 60)
    observations = campaign.observe(tmp_path, key, spec, perf_counter() + 60)
    assert audit.audit_comparison_grid(tmp_path / key, spec)["samples"] == comparison["samples"]
    assert comparison["status"] == "pass" and comparison["samples"] > len(spec["observation_times"])
    assert observations["samples"] == 4 and observations["terminal_observations"] == 2
    assert not observations["recipient_terminal_target"]  # A nonswitch is not a numerical failure.
    assert observations["cells"][0]["right_censored_no_sampled_target"]
    assert observations["cells"][1]["first_sampled_target_time"] == 0
    with np.load(tmp_path / key / "observations/chunk-000000.npz", allow_pickle=False) as data:
        assert data["full_rhs"].shape == (2, 47)
        assert data["packet"].shape == (2, 17, 3)
        np.testing.assert_array_equal(data["refined"][0], 0)
    checked = audit.audit_observations(tmp_path / key, spec["cases"][key], spec)
    assert checked["observations"] == 4 and checked["terminal_observations"] == 2
    with (tmp_path / key / "observations/chunk-000000.npz").open("ab") as handle:
        handle.write(b"corrupt")
    with pytest.raises(ValueError, match="Observer chunk"):
        audit.audit_observations(tmp_path / key, spec["cases"][key], spec)


def test_registration_input_and_source_tampering_refused(tmp_path, monkeypatch):
    for key, value in campaign.THREADS.items():
        monkeypatch.setenv(key, value)
    output = tmp_path / "registered"
    receipt = campaign.register(output)
    assert len(receipt["planned_attempts"]) == 42 and len(receipt["cases"]) == 14
    assert campaign.check_registration(output) == receipt
    with pytest.raises(ValueError, match="Unregistered path"):
        campaign.worker(output, "E_to_M/active/unregistered")
    changed = copy.deepcopy(receipt)
    changed["duration"] = 0.03
    path = output / "registration.json"
    # Deliberate tampering of this test's own temporary evidence only.
    with path.open("w") as handle:
        json.dump(changed, handle)
    with pytest.raises(ValueError, match="Registered inputs"):
        campaign.check_registration(output)


def test_deadline_refuses_comparison_without_claiming_pass():
    with pytest.raises(ref.BudgetExceeded, match="session wall"):
        campaign.guard(perf_counter() - 1)


@pytest.mark.parametrize("timeout", [False, True])
def test_stopped_campaign_retains_attempt_and_never_retries(tmp_path, monkeypatch, timeout):
    for key, value in campaign.THREADS.items():
        monkeypatch.setenv(key, value)
    calls = []

    def fail(command, **kwargs):
        calls.append(command)
        kwargs["stdout"].write("deliberate engineering test worker failure\n")
        kwargs["stdout"].flush()
        if timeout:
            raise subprocess.TimeoutExpired(command, kwargs["timeout"])
        return subprocess.CompletedProcess(command, 1)

    monkeypatch.setattr(campaign.subprocess, "run", fail)
    output = tmp_path / "stopped"
    with pytest.raises(subprocess.TimeoutExpired if timeout else ValueError):
        campaign.run(output)
    assert len(calls) == 1 and not (output / "verification.json").exists()
    receipt = ref.read_json(output / "failure.json")
    assert receipt["status"] == ("incomplete" if timeout else "unqualified")
    assert len(receipt["not_started"]) == 41 and len(receipt["attempts"]) == 1
    checked = audit.audit(output)
    assert checked["status"] == "pass" and checked["campaign_status"] == receipt["status"]
    assert "integrity_only" in checked["scope"] and not checked["candidate_selected"]
    with (output / "extra.log").open("x") as handle:
        handle.write("extra evidence must not go unnoticed")
    with pytest.raises(ValueError, match="payload inventory"):
        audit.audit(output)


def test_new_work_is_outside_production_and_native():
    for module in (paths, campaign, audit):
        source = inspect.getsource(module)
        assert "import cells" not in source and "from cells" not in source
        assert "import bitsey" not in source and "import zombie" not in source
    assert "model.derivative" not in inspect.getsource(audit)
