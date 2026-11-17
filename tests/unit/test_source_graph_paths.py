"""Short engineering tests only: none execute a 1000-unit scientific path."""

import inspect
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


def test_deadline_refuses_comparison_without_claiming_pass():
    with pytest.raises(ref.BudgetExceeded, match="session wall"):
        campaign.guard(perf_counter() - 1)


def test_new_work_is_outside_production_and_native():
    for module in (paths, campaign, audit):
        source = inspect.getsource(module)
        assert "import cells" not in source and "from cells" not in source
        assert "import bitsey" not in source and "import zombie" not in source
    assert "model.derivative" not in inspect.getsource(audit)
