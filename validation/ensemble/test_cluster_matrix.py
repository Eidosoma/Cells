"""Qualified IP3 profiles preserve physics, world identities and resource reserves."""

import json
from dataclasses import replace

import pytest

from validation.ensemble import cluster_matrix as matrix


@pytest.fixture(params=("gated", "ip3"))
def qualified(tmp_path, monkeypatch, request):
    family = request.param
    name = f"configs/assembly_regulated_{family}_calcium_cluster.json"
    root = tmp_path / "qualified"
    config = root / "source" / name
    config.parent.mkdir(parents=True)
    config.write_bytes((matrix.Path(__file__).resolve().parents[2] / name).read_bytes())
    spec = matrix.parse_spec(matrix.read(config))
    code = root / "source/src/cells/fixture.py"
    code.parent.mkdir(parents=True)
    code.write_text("# frozen production fixture\n")
    production = {"fixture.py": matrix.sha(code)}
    monkeypatch.setattr(matrix, "sources", lambda: production.copy())
    protocol = {"duration_s": spec.pool.end_time_s, "steps_s": [0.000025, 0.0000125, 0.00000625]}
    matrix.write(root / "chemistry-protocol.json", protocol)
    group = "cav" if family == "gated" else "ip3"
    rows = {
        "assembly-baseline": {
            "status": "passed",
            "backend": "gpu",
            "physical_model": spec.ionic.to_dict()["model"]["id"],
            "through_time_s": spec.pool.end_time_s,
            "tick": spec.ticks,
            "worlds": spec.pool.worlds,
            "world_id_start": spec.pool.world_id_start,
            "assembly_cells": {
                b.cell_id: {"seed": b.pool.seed, "stream_id": b.stream_id} for b in spec.pools
            },
        },
        **{
            key: {"status": "passed"}
            for key in ("assembly-reference", "assembly-replay", "cpu-gpu")
        },
    }
    artifacts = ["chemistry-protocol.json"]
    for key, value in rows.items():
        path = root / f"{group}-evidence/gpu/{key}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        matrix.write(path, value)
        artifacts.append(str(path.relative_to(root)))
    matrix.write(
        root / "registration.json",
        {
            "sources_sha256": {name: matrix.sha(config), "src/cells/fixture.py": matrix.sha(code)},
            "chemistry_protocol": protocol,
        },
    )
    matrix.write(
        root / "result.json",
        {
            "status": f"{family}_calcium_assembly_cpu_gpu_qualification_pass",
            "chemistry_protocol_sha256": matrix.sha(root / "chemistry-protocol.json"),
            "peak_child_rss_bytes": 14 * 1024**3,
        },
    )
    matrix.write(
        root / "completion.json",
        {
            "status": "completed",
            "result_sha256": matrix.sha(root / "result.json"),
            "files_sha256": {p: matrix.sha(root / p) for p in artifacts},
        },
    )
    monkeypatch.setenv("CELLS_OUTPUT_ROOT", str(tmp_path))
    monkeypatch.setattr(matrix, "available_host_memory", lambda: 40 * 1024**3)
    return root, family, spec


@pytest.mark.parametrize("workers", [1, 2])
def test_profiles_keep_physics_and_world_identity(qualified, tmp_path, workers):
    parent, family, original = qualified
    output = tmp_path / "prepared"
    matrix.prepare(parent, output, family=family, workers_per_gpu=workers)
    data, planned, receipt = (
        matrix.read(output / name) for name in ("definition.json", "plan.json", "preparation.json")
    )
    assert planned["worlds"] == 128 and len(planned["tasks"]) == 6
    assert planned["worker_processes"] == workers
    assert data["execution"]["worker_threads"] * workers == 2
    assert data["execution"]["max_wall_seconds"] == (3600 if workers == 1 else 1800)
    assert {a["batch_worlds"] for a in data["arms"]} == {16, 32}
    assert all(a["worlds"] == 64 for a in data["arms"])
    ids = []
    for task in planned["tasks"]:
        spec = matrix.parse_spec(task["definition"])
        assert spec.ionic.model == original.ionic.model
        assert spec.ionic.experiment == original.ionic.experiment
        assert spec.ionic.execution == replace(original.ionic.execution, backend="gpu")
        assert spec.window_ticks == original.window_ticks
        for b, old in zip(spec.pools, original.pools, strict=True):
            assert b.stream_id == old.stream_id and b.pool.seed == old.pool.seed
        ids.extend(range(spec.pool.world_id_start, spec.pool.world_id_start + spec.pool.worlds))
    assert sorted(ids) == list(range(128))
    allowance = (16 if family == "ip3" else 10) * 1024**3
    assert receipt["host_memory_allowance_per_worker_bytes"] == allowance
    assert receipt["required_available_memory_bytes"] == workers * allowance + 4 * 1024**3
    assert not receipt["automatic_launch"] and not receipt["automatic_followup"]


def test_memory_reserve_rejects_two_workers_and_keeps_single_worker(
    qualified, tmp_path, monkeypatch
):
    parent, family, _ = qualified
    monkeypatch.setattr(matrix, "available_host_memory", lambda: 22 * 1024**3)
    output = tmp_path / "must-not-prepare"
    with pytest.raises(ValueError, match="per-worker host allowance"):
        matrix.prepare(parent, output, family=family, workers_per_gpu=2)
    assert not output.exists()
    matrix.prepare(parent, tmp_path / "single", family=family, workers_per_gpu=1)


@pytest.mark.parametrize("change", ["source", "artifact", "production", "failed", "unbound"])
def test_rejects_changed_or_incomplete_qualification(qualified, monkeypatch, change):
    parent, family, _ = qualified
    group = "cav" if family == "gated" else "ip3"
    artifact = f"{group}-evidence/gpu/assembly-reference.json"
    if change == "source":
        (parent / "source/src/cells/fixture.py").write_text("changed production\n")
    elif change == "artifact":
        (parent / artifact).write_text(json.dumps({"status": "failed"}))
    elif change == "production":
        monkeypatch.setattr(matrix, "sources", lambda: {"fixture.py": "changed"})
    elif change == "failed":
        matrix.write(parent / "failure.json", {"status": "failed"})
    else:
        done = matrix.read(parent / "completion.json")
        done["files_sha256"].pop(artifact)
        (parent / "completion.json").write_text(json.dumps(done))
    with pytest.raises(ValueError):
        matrix.qualified_definitions(parent, family=family)


def test_rejects_wrong_qualified_family(qualified):
    parent, family, _ = qualified
    with pytest.raises(ValueError, match="completed assembly-cluster"):
        matrix.qualified_definitions(parent, family="gated" if family == "ip3" else "ip3")


@pytest.mark.parametrize("workers", [0, 3, True])
def test_invalid_worker_count_cannot_prepare(qualified, tmp_path, workers):
    parent, family, _ = qualified
    with pytest.raises(ValueError, match="one or two"):
        matrix.prepare(parent, tmp_path / "invalid", family=family, workers_per_gpu=workers)


@pytest.fixture
def observed_memory(qualified, tmp_path):
    parent, family, _ = qualified
    prepared = tmp_path / "observed-preparation"
    matrix.prepare(parent, prepared, family=family, workers_per_gpu=1)
    definition = matrix.read(prepared / "definition.json")
    root = tmp_path / "memory-profile"
    source = root / "source/cells/fixture.py"
    source.parent.mkdir(parents=True)
    source.write_bytes((parent / "source/src/cells/fixture.py").read_bytes())
    driver = root / "source/profile_cluster.py"
    driver.write_text("# frozen observer fixture\n")
    (root / "campaign").mkdir()
    matrix.write(root / "campaign/registration.json", {"definition": definition})
    matrix.write(
        root / "campaign/result.json",
        {
            "status": "completed",
            "registration_sha256": matrix.sha(root / "campaign/registration.json"),
        },
    )
    matrix.write(
        root / "profile-registration.json",
        {
            "sources_sha256": matrix.sources(),
            "driver_sha256": matrix.sha(driver),
        },
    )
    matrix.write(root / "resource-observations.json", {"fixture_peak_bytes": 6 * 1024**3})
    result = {
        "status": "completed",
        "all_checkpoint_fields_bitwise_equal_to_parent": True,
        "profile_registration_sha256": matrix.sha(root / "profile-registration.json"),
        "campaign_result_sha256": matrix.sha(root / "campaign/result.json"),
        "evidence_sha256": {
            "resource-observations.json": matrix.sha(root / "resource-observations.json")
        },
        "resource_samples": 100,
        "maximum_resource_sample_gap_seconds": 1.1,
        "worker_resources": {"worker-0-profile": {"peak_rss_bytes": 6 * 1024**3}},
        "sampled_peak_process_tree_rss_bytes": 6 * 1024**3,
    }
    matrix.write(root / "result.json", result)
    matrix.write(
        root / "completion.json",
        {"status": "completed", "result_sha256": matrix.sha(root / "result.json")},
    )
    return root, definition


def test_completed_memory_profile_preserves_work_and_reserve(
    qualified, observed_memory, tmp_path, monkeypatch
):
    parent, family, _ = qualified
    root, old = observed_memory
    monkeypatch.setattr(matrix, "available_host_memory", lambda: 20 * 1024**3)
    out = tmp_path / "measured-profile"
    matrix.prepare(parent, out, family=family, workers_per_gpu=2, memory_profile=root)
    new, receipt = matrix.read(out / "definition.json"), matrix.read(out / "preparation.json")
    assert new["arms"] == old["arms"] and new["seed"] == old["seed"]
    assert receipt["host_memory_allowance_per_worker_bytes"] == 8 * 1024**3
    assert receipt["required_available_memory_bytes"] == 20 * 1024**3
    assert receipt["measured_memory_basis"]["result_sha256"] == matrix.sha(root / "result.json")
    assert matrix.plan(new, 1)["tasks"] == matrix.plan(old, 1)["tasks"]
    monkeypatch.setattr(matrix, "available_host_memory", lambda: 20 * 1024**3 - 1)
    with pytest.raises(ValueError, match="memory reserve"):
        matrix.prepare(
            parent, tmp_path / "insufficient", family=family, workers_per_gpu=2, memory_profile=root
        )


@pytest.mark.parametrize(
    "change", ["artifact", "source", "workload", "failed", "replay", "gap", "peak"]
)
def test_changed_or_unsuitable_memory_profile_is_rejected(observed_memory, change):
    root, definition = observed_memory
    if change == "artifact":
        (root / "resource-observations.json").write_text("{}")
    elif change == "source":
        (root / "source/cells/fixture.py").write_text("changed")
    elif change == "workload":
        definition["arms"][0]["worlds"] += 1
    elif change == "failed":
        matrix.write(root / "failure.json", {"status": "failed"})
    else:
        result = matrix.read(root / "result.json")
        if change == "replay":
            result["all_checkpoint_fields_bitwise_equal_to_parent"] = False
        elif change == "gap":
            result["maximum_resource_sample_gap_seconds"] = 10.0
        elif change == "peak":
            result["worker_resources"]["worker-0-profile"]["peak_rss_bytes"] = 0
        (root / "result.json").write_text(json.dumps(result))
        (root / "completion.json").write_text(
            json.dumps(
                {
                    "status": "completed",
                    "result_sha256": matrix.sha(root / "result.json"),
                }
            )
        )
    with pytest.raises(ValueError):
        matrix.measured_memory_allowance(root, definition, matrix.sources())
