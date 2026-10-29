"""Software-only campaign tests: synthetic workers provide no numerical evidence."""

import json
import os
import shutil
import sys
import time
from pathlib import Path

import pytest

from validation.tissue import open_calcium_bath_trajectory_campaign as campaign

artifact = campaign.artifact

# A frozen, standard-library-only role runner exercising the real subprocess
# interface. Every output declares itself synthetic; no Cells model is imported.
FAKE_RUNNER = """
import argparse
import os
import sys
import time
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('--bundle', type=Path, required=True)
p.add_argument('--execute', action='store_true')
p.add_argument('--job', required=True)
p.add_argument('--cpu', type=int, required=True)
p.add_argument('--output', type=Path, required=True)
p.add_argument('--dependency-runs', type=Path)
a = p.parse_args()
sys.path.insert(0, str(a.bundle / 'source'))
import synthetic_artifacts as artifact
job = artifact.read_json(a.bundle / 'plan.json')['jobs'][a.job]
protocol = artifact.read_json(a.bundle / 'protocol.json')
out = a.output
out.mkdir(parents=True)
(out / 'started').write_text('synthetic worker only')
def await_condition(condition):
    deadline = time.monotonic() + 5
    while not condition():
        if time.monotonic() > deadline:
            raise RuntimeError('Synthetic synchronization timed out')
        time.sleep(.01)
behavior = job.get('behavior', {})
if behavior.get('hold'):
    await_condition(lambda: (out.parent.parent / 'release').exists())
if behavior.get('fail_after_peer'):
    await_condition(lambda: (out.parent / behavior['fail_after_peer'] / 'started').exists())
    artifact.write_json(out / 'failure.json', dict(status='failed', synthetic=True))
    raise SystemExit(7)
if behavior.get('finish_after_stop'):
    await_condition(lambda: artifact.read_json(out.parent.parent / 'status.json')['status']
                    == 'stopping_after_failure')
dependencies = artifact.read_json(a.dependency_runs) if a.dependency_runs else None
assert set(dependencies or {}) == set(job['requires'])
for path in (dependencies or {}).values():
    artifact.verify_result(path)
os.sched_setaffinity(0, {a.cpu})
for folder in ('data', 'guard'):
    (out / folder).mkdir()
manifest_sha = artifact.sha(a.bundle / 'manifest.json')
identity = dict(job_id=a.job, role=job['role'], family=job['family'],
                dataset=job['dataset'], phase=job['phase'],
                bundle_manifest_sha256=manifest_sha)
(out / 'data/synthetic.txt').write_text('No numerical or biological evidence')
artifact.success(out / 'data', dict(**identity, synthetic=True,
    definition_sha256=job['definition_sha256'], physics_sha256=job['physics_sha256'],
    protocol_sha256=artifact.digest(protocol), duration_s=8e-6))
limits = dict(max_wall_seconds=480, max_process_tree_memory_bytes=2**30,
              max_process_tree_rss_bytes=2**30, max_individual_process_rss_bytes=2**30,
              min_available_host_memory_bytes=8*2**30, process_tree_memory_metric='rss')
resource = dict(status='completed', returncode=0, elapsed_seconds=.01,
    sampled_peak_process_tree_rss_bytes=1024, observed_process_high_water_bytes=1024,
    minimum_available_host_memory_bytes=16*2**30, samples=1,
    process_tree_memory_metric='rss', limits=limits, synthetic=True)
artifact.write_json(out / 'guard/process-inputs.json', dict(limits=limits))
artifact.write_json(out / 'guard/result.json', resource)
artifact.write_json(out / 'inputs.json', dict(job_id=a.job, job=job, cpu=a.cpu,
    cpu_affinity=sorted(os.sched_getaffinity(0)), bundle_manifest_sha256=manifest_sha,
    resources=protocol['resources'], dependency_runs=dependencies))
if dependencies:
    artifact.write_json(out / 'dependency-runs.json', dependencies)
artifact.success(out, dict(**identity, synthetic=True, source_and_input_hashes_unchanged=True,
    qualifier_result_sha256=artifact.sha(out / 'data/result.json'), resource_result=resource))
"""


def freeze(bundle):
    artifact.write_json(
        bundle / "manifest.json",
        dict(
            accepted_source=str(bundle / "source"),
            file_sha256={
                str(path.relative_to(bundle)): artifact.sha(path)
                for path in bundle.rglob("*")
                if path.is_file() and path.name != "manifest.json"
            },
        ),
    )


def synthetic_plan(tmp_path, graph):
    bundle = tmp_path / "bundle"
    (bundle / "source").mkdir(parents=True)
    shutil.copyfile(Path(artifact.__file__), bundle / "source/synthetic_artifacts.py")
    (bundle / "runner.py").write_text(FAKE_RUNNER)
    raw = dict(experiment=dict(end_time=8e-6), execution=dict(dt=6.25e-8, max_steps=512))
    physical = {**raw, "execution": {"max_steps": 512}}
    artifact.write_json(bundle / "definition.json", raw)
    jobs = {
        name: dict(
            role="production",
            family="calcium",
            dataset="synthetic",
            phase="SIM",
            requires=dependencies,
            definition="definition.json",
            definition_sha256=artifact.digest(raw),
            physics_sha256=artifact.digest(physical),
        )
        for name, dependencies in graph.items()
    }
    artifact.write_json(bundle / "plan.json", dict(jobs=jobs))
    artifact.write_json(
        bundle / "protocol.json",
        dict(duration_s=8e-6, planned_roles=len(jobs), resources=campaign.RESOURCES),
    )
    freeze(bundle)
    inputs = dict(
        kind=campaign.KIND,
        bundle=dict(path=str(bundle), manifest_sha256=artifact.sha(bundle / "manifest.json")),
        pending_jobs=list(graph),
        retained={},
        cpus=sorted(os.sched_getaffinity(0))[:2],
    )
    return inputs, bundle


def prepare(tmp_path, inputs, name="campaign"):
    input_path = tmp_path / (name + "-inputs.json")
    artifact.write_json(input_path, inputs)
    return campaign.prepare(input_path, tmp_path / name)


def execute_attached(output):
    """Exercise the controller synchronously; no long-running test jobs."""
    (output / "launched").mkdir()
    artifact.write_json(
        output / "launch-inputs.json", dict(seal=campaign.receipt(output / "seal.json"))
    )
    return campaign.execute(output)


def change_plan(inputs, bundle, change):
    plan = artifact.read_json(bundle / "plan.json")
    change(plan["jobs"])
    artifact.write_json(bundle / "plan.json", plan)
    freeze(bundle)
    inputs["bundle"]["manifest_sha256"] = artifact.sha(bundle / "manifest.json")


@pytest.mark.parametrize("defect", ["missing", "cycle", "duplicate", "unknown", "recipe", "cpu"])
def test_invalid_explicit_plan_refused_before_any_launch(tmp_path, defect):
    inputs, bundle = synthetic_plan(tmp_path, {"init": [], "sim": ["init"]})
    if defect == "missing":
        inputs["pending_jobs"] = ["sim"]
    elif defect == "cycle":
        change_plan(inputs, bundle, lambda jobs: jobs["init"].update(requires=["sim"]))
    elif defect == "duplicate":
        inputs["pending_jobs"].append("sim")
    elif defect == "unknown":
        inputs["pending_jobs"].append("absent")
    elif defect == "recipe":
        change_plan(inputs, bundle, lambda jobs: jobs["sim"].update(physics_sha256="0" * 64))
    else:
        inputs["cpus"] *= 3
    with pytest.raises(ValueError):
        prepare(tmp_path, inputs)
    assert not (tmp_path / "campaign").exists()


def test_preparation_is_read_only_and_controller_is_frozen(tmp_path):
    inputs, bundle = synthetic_plan(tmp_path, {"init": [], "sim": ["init"]})
    before = artifact.sha(bundle / "manifest.json")
    output = prepare(tmp_path, inputs)
    assert artifact.sha(bundle / "manifest.json") == before
    assert not (output / "roles").exists()
    assert not (output / "launched").exists()
    assert artifact.read_json(output / "seal.json")["executable"] == str(
        Path(sys.executable).absolute()
    )
    campaign.checked(output)
    with pytest.raises(ValueError, match="already exists"):
        prepare(tmp_path, inputs)
    with (output / "driver.py").open("a") as stream:
        stream.write("\n# changed\n")
    with pytest.raises(ValueError, match="Frozen controller changed"):
        campaign.checked(output)


def test_matching_dependencies_and_retained_parent_are_used_without_rerunning(tmp_path):
    inputs, _ = synthetic_plan(tmp_path, {"init": [], "sim": ["init"], "compare": ["init", "sim"]})
    inputs["pending_jobs"] = ["init"]
    initial = prepare(tmp_path, inputs, "initial")
    assert execute_attached(initial) == 0
    assert artifact.read_json(initial / "result.json")["all_plan_jobs_completed"] is False
    parent = initial / "roles/init"
    pinned = artifact.sha(parent / "result.json")
    inputs["retained"] = {"init": dict(path=str(parent), result_sha256=pinned)}
    inputs["pending_jobs"] = ["sim", "compare"]
    output = prepare(tmp_path, inputs, "continuation")
    assert execute_attached(output) == 0
    result = artifact.read_json(output / "result.json")
    assert (result["retained_roles"], result["newly_executed_roles"], result["distinct_roles"]) == (
        1,
        2,
        3,
    )
    assert result["all_plan_jobs_completed"] is True
    assert not (output / "roles/init").exists()
    assert artifact.sha(parent / "result.json") == pinned
    sim = artifact.read_json(output / "roles/sim/inputs.json")
    assert sim["dependency_runs"] == {"init": str(parent)}
    comparison = artifact.read_json(output / "roles/compare/inputs.json")
    assert comparison["dependency_runs"] == {"init": str(parent), "sim": str(output / "roles/sim")}


@pytest.mark.parametrize("defect", ["duration", "guard", "limits", "changed_after_prepare"])
def test_corrupted_retained_evidence_is_refused(tmp_path, defect):
    inputs, _ = synthetic_plan(tmp_path, {"init": [], "sim": ["init"]})
    inputs["pending_jobs"] = ["init"]
    initial = prepare(tmp_path, inputs, "initial")
    assert execute_attached(initial) == 0
    parent = initial / "roles/init"
    inputs["pending_jobs"] = ["sim"]
    inputs["retained"] = {
        "init": dict(path=str(parent), result_sha256=artifact.sha(parent / "result.json"))
    }
    if defect == "changed_after_prepare":
        output = prepare(tmp_path, inputs, "continuation")
        (parent / "data/synthetic.txt").write_text("altered after prepare")
        assert execute_attached(output) == 1
        assert not (output / "roles").exists()
        assert (output / "failure.json").exists()
        return
    outer = artifact.read_json(parent / "result.json")
    if defect == "duration":
        child = artifact.read_json(parent / "data/result.json")
        child["duration_s"] = 1e-9
        artifact.write_json(parent / "data/result.json", child)
        outer["qualifier_result_sha256"] = artifact.sha(parent / "data/result.json")
    else:
        resource = artifact.read_json(parent / "guard/result.json")
        if defect == "guard":
            resource["minimum_available_host_memory_bytes"] = 2**30
        else:
            resource["limits"]["max_wall_seconds"] = 960
        artifact.write_json(parent / "guard/result.json", resource)
        outer["resource_result"] = resource
    # Even a self-consistently rehashed receipt must still satisfy physical and resource contracts.
    outer.pop("status")
    outer.pop("artifacts")
    artifact.success(parent, outer)
    inputs["retained"]["init"]["result_sha256"] = artifact.sha(parent / "result.json")
    with pytest.raises(ValueError):
        prepare(tmp_path, inputs, "continuation")
    assert not (tmp_path / "continuation").exists()


def test_failure_stops_new_launches_and_allows_active_sibling_to_finish(tmp_path):
    if len(os.sched_getaffinity(0)) < 2:
        pytest.skip("Requires two available CPU slots")
    inputs, bundle = synthetic_plan(tmp_path, {"fail": [], "active": [], "unlaunched": []})

    def behaviors(jobs):
        jobs["fail"]["behavior"] = dict(fail_after_peer="active")
        jobs["active"]["behavior"] = dict(finish_after_stop=True)

    change_plan(inputs, bundle, behaviors)
    output = prepare(tmp_path, inputs)
    assert execute_attached(output) == 1
    failure = artifact.read_json(output / "failure.json")
    assert failure["unlaunched"] == ["unlaunched"]
    assert list(failure["completed"]) == ["active"]
    assert [value["job"] for value in failure["failures"]] == ["fail"]
    assert (output / "roles/fail/failure.json").exists()
    assert (output / "roles/active/result.json").exists()
    assert not (output / "roles/unlaunched").exists()
    assert not (output / "result.json").exists()
    assert artifact.read_json(output / "status.json")["status"] == "failed"


def test_explicit_launch_detaches_once_and_preserves_the_environment(tmp_path, monkeypatch):
    inputs, bundle = synthetic_plan(tmp_path, {"held": []})
    change_plan(inputs, bundle, lambda jobs: jobs["held"].update(behavior=dict(hold=True)))
    output = prepare(tmp_path, inputs)
    monkeypatch.setattr(campaign, "available_memory", lambda: 16 * 2**30)
    launch = campaign.launch(output)
    assert os.getsid(launch["pid"]) == launch["pid"]
    assert not (output / "result.json").exists()
    launch_bytes = (output / "launch.json").read_bytes()
    try:
        with pytest.raises(FileExistsError):
            campaign.launch(output)
        assert (output / "launch.json").read_bytes() == launch_bytes
    finally:
        (output / "release").touch()
        # Only this sub-second synthetic process is watched; no scientific job is launched.
        deadline = time.monotonic() + 10
        while not ((output / "result.json").exists() or (output / "failure.json").exists()):
            assert time.monotonic() < deadline, (output / "controller.log").read_text()
            time.sleep(0.02)
    assert not (output / "failure.json").exists(), (output / "controller.log").read_text()
    assert artifact.read_json(output / "result.json")["distinct_roles"] == 1
    assert artifact.read_json(output / "roles/held/result.json")["synthetic"] is True


def test_low_memory_launch_does_not_claim_or_start_campaign(tmp_path, monkeypatch):
    inputs, _ = synthetic_plan(tmp_path, {"init": []})
    output = prepare(tmp_path, inputs)
    monkeypatch.setattr(campaign, "available_memory", lambda: 4 * 2**30)
    with pytest.raises(ValueError, match="reserve unavailable"):
        campaign.launch(output)
    assert not (output / "launched").exists()
    assert not (output / "roles").exists()
    assert json.loads((output / "status.json").read_text())["status"] == "prepared"
