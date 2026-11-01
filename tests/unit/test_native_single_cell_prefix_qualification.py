"""Stdlib runner controls. No Cells, native, NumPy, Pillow or scientific entry."""

import importlib.abc
import io
import json
import struct
import subprocess
import sys
from types import SimpleNamespace

import pytest

from validation.betse import native_single_cell_prefix_qualification as runner


@pytest.fixture(autouse=True)
def no_science():
    attempted = []

    class Block(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split(".")[0] in {
                "cells",
                "betse",
                "numpy",
                "scipy",
                "PIL",
                "jax",
                "jaxlib",
            }:
                attempted.append(fullname)
                raise AssertionError("Scientific import forbidden: " + fullname)

    blocker = Block()
    sys.meta_path.insert(0, blocker)
    try:
        yield
    finally:
        sys.meta_path.remove(blocker)
    assert not attempted


@pytest.fixture
def packet(tmp_path, monkeypatch):
    repository, base = tmp_path / "repo", tmp_path / "outputs"
    repository.mkdir()
    base.mkdir()
    native = base / "native"
    native.mkdir()
    defaults = native / "defaults.yaml"
    defaults.write_text("cell height: 1e-5\ncell spacing: 2.6e-8\n")
    original = native / "original.py"
    original.write_text("# retained synthetic source authority\n")
    grid = native / "betse/science/math/finitediff.py"
    grid.parent.mkdir(parents=True)
    grid.write_text("# synthetic grid authority; never imported\n")
    bootstrap = native / "betse/__init__.py"
    bootstrap.write_text("# synthetic package bootstrap; never imported\n")
    site = base / "site-packages"
    package = site / "beartype"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text(
        "raise AssertionError('must not import during preparation')\n"
    )
    (package / "claw.py").write_text("# metadata-only synthetic dependency\n")
    files = {runner.OWN: "# synthetic runner bytes\n", runner.TEST: "# controls\n"}
    for suffix in ("caller_lattice", "image_mask"):
        name = f"src/cells/processes/betse_native_single_cell_{suffix}_source.py"
        files[name] = "NATIVE_PINS = " + repr({"original.py": runner.pin(original)["sha256"]})
    files["src/cells/processes/betse_native_single_cell_grid_alias.py"] = "NATIVE_PINS = " + repr(
        {"original.py": runner.pin(original)["sha256"]}
    )
    files["src/cells/processes/betse_native_single_cell_ecm_source.py"] = "GRID_SHA256 = " + repr(
        runner.pin(grid)["sha256"]
    )
    names = [*files, runner.CLOSURE]
    files[runner.CLOSURE] = (
        "def closure(root, starts):\n    return {name: '' for name in " + repr(names) + "}\n"
    )
    for name, text in files.items():
        path = repository / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    subprocess.run(["git", "init", "-q", str(repository)], check=True)
    subprocess.run(["git", "-C", str(repository), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(repository),
            "-c",
            "user.name=Control",
            "-c",
            "user.email=control@invalid",
            "commit",
            "-qm",
            "synthetic source",
        ],
        check=True,
    )
    monkeypatch.setattr(runner, "BASE", base)
    monkeypatch.setattr(runner, "NATIVE", native)
    monkeypatch.setattr(runner, "DEFAULTS", defaults)
    monkeypatch.setattr(runner, "DEFAULTS_SHA256", runner.pin(defaults)["sha256"])
    monkeypatch.setattr(runner, "GRID_PACKAGE_SHA256", runner.pin(bootstrap)["sha256"])
    monkeypatch.setattr(
        runner.sysconfig, "get_paths", lambda: dict(purelib=str(site), platlib=str(site))
    )
    cpu = next(iter(runner.os.sched_getaffinity(0)))
    monkeypatch.setattr(runner.os, "sched_getaffinity", lambda pid: {cpu})
    prepared = base / "prepared"
    plan = runner.prepare(prepared, repository=repository, cpu=cpu)
    sha = runner.pin(prepared / "plan.json")["sha256"]
    review = base / "review.json"
    runner.write(review, dict(scope="synthetic orchestration control, not source admission"))
    release = base / "release.json"
    runner.write(
        release,
        dict(
            kind=runner.KINDS[1],
            plan_sha256=sha,
            snapshot_sha256=plan["snapshot_sha256"],
            case=runner.CASES[0],
            allow_actual_source_diagnostic=True,
            scientific_qualification=False,
            source_review=runner.pin(review),
        ),
    )
    return SimpleNamespace(
        root=base,
        repository=repository,
        prepared=prepared,
        plan=plan,
        sha=sha,
        release=release,
        review=review,
        native=original,
        cpu=cpu,
        site=site,
    )


def test_prepare_freezes_git_and_native_inputs_without_model_imports(packet):
    plan = runner.verify_plan(packet.prepared, packet.sha)
    assert plan["cases"] == list(runner.CASES)
    assert plan["configuration"] == runner.CONFIGURATION
    assert plan["git_revision"]
    assert len(plan["external_inputs"]) == 2
    assert not plan["scientific_qualification"]
    assert not (packet.prepared / "release.json").exists()
    assert not (packet.prepared / "source" / runner.OWN).stat().st_mode & 0o222


@pytest.mark.parametrize("endpoint", ["makeECM", "make_maskM", "lapENV_P_inv"])
@pytest.mark.parametrize("changed_path", ["betse/science/math/finitediff.py", "betse/__init__.py"])
def test_extended_preparation_binds_fresh_configuration_native_grid_and_endpoint(
    packet, endpoint, changed_path
):
    prepared = packet.root / endpoint
    plan = runner.prepare(
        prepared, repository=packet.repository, cpu=packet.cpu, stop_after=endpoint
    )
    digest = runner.pin(prepared / "plan.json")["sha256"]
    assert runner.verify_plan(prepared, digest) == plan
    assert plan["configuration"] == {
        **runner.CONFIGURATION,
        "general options": {"comp grid size": 25},
    }
    assert plan["execution_stages"] == list(runner.stage_names(endpoint))
    assert plan["scalar_provenance"]["lines"] == [106, 160, 164]
    assert runner.pin(runner.NATIVE / "betse/science/math/finitediff.py") in plan["external_inputs"]
    assert not (prepared / "release.json").exists()
    grant = runner.read(packet.release)
    grant.update(plan_sha256=digest, snapshot_sha256=plan["snapshot_sha256"])
    release = packet.root / (endpoint + "-release.json")
    runner.write(release, grant)
    with pytest.raises(ValueError, match="release"):
        runner.verify_release(prepared, digest, release, runner.CASES[0])
    grant["stop_after"] = endpoint
    release.write_text(json.dumps(grant))
    assert runner.verify_release(prepared, digest, release, runner.CASES[0]) == plan
    path = runner.NATIVE / changed_path
    path.write_text("changed original source")
    with pytest.raises(ValueError, match="external"):
        runner.verify_plan(prepared, digest)


def test_missing_descriptor_runtime_refuses_before_source_work(packet):
    (packet.site / "beartype").rename(packet.site / "not-beartype")
    prepared = packet.root / "missing-runtime"
    with pytest.raises(ValueError, match="beartype"):
        runner.prepare(prepared, repository=packet.repository, cpu=packet.cpu, stop_after="makeECM")
    assert (prepared / "preparation-failure.json").is_file()
    assert not (prepared / "plan.json").exists()


def test_added_descriptor_runtime_file_refuses_without_importing_package(packet):
    prepared = packet.root / "runtime-drift"
    runner.prepare(prepared, repository=packet.repository, cpu=packet.cpu, stop_after="makeECM")
    (packet.site / "beartype/added.py").write_text("# new unpinned import target\n")
    with pytest.raises(ValueError, match="runtime origin"):
        runner.verify_plan(prepared, runner.pin(prepared / "plan.json")["sha256"])


def test_legacy_near_neigh_plan_without_stage_field_still_verifies(packet):
    plan = runner.read(packet.prepared / "plan.json")
    plan.pop("execution_stages")
    path = packet.prepared / "plan.json"
    path.chmod(0o644)
    path.write_text(json.dumps(plan))
    assert runner.verify_plan(packet.prepared, runner.pin(path)["sha256"]) == plan


@pytest.mark.parametrize("change", ["endpoint", "configuration", "stages"])
def test_extended_plan_rejects_widened_or_incomplete_scope(packet, change):
    prepared = packet.root / "extended"
    plan = runner.prepare(
        prepared, repository=packet.repository, cpu=packet.cpu, stop_after="make_maskM"
    )
    if change == "endpoint":
        plan["stop_after"] = "makeLaplacian"
    elif change == "configuration":
        plan["configuration"]["general options"]["comp grid size"] = 26
    else:
        plan.pop("execution_stages")
    path = prepared / "plan.json"
    path.chmod(0o644)
    path.write_text(json.dumps(plan))
    with pytest.raises(ValueError, match="endpoint|Incomplete"):
        runner.verify_plan(prepared, runner.pin(path)["sha256"])


def pipeline_control(output, endpoint):
    """Synthetic distinct owners; public APIs are stubs, not native fixtures."""
    calls, values = [], {}

    class Owner:
        def __init__(self, stage):
            self.trial = {"stage": stage, "synthetic": True}

    def mark(stage, result):
        calls.append(stage)
        return result

    initial_request = {"synthetic_image_request": True}
    initial_state = {"synthetic_pre_mesh": True}
    core_request = {"synthetic_core_request": True}

    def fixture(case, path):
        assert case == runner.CASES[0] and path is output
        return mark("fixture", (initial_request, {"synthetic_native_inputs": True}))

    def initial_prepare(request):
        assert request is initial_request
        return mark("pre_mesh", initial_state)

    def core_from_initial(request, state, *, law_id):
        assert request is initial_request and state is initial_state and law_id == "core"
        return mark("core_request", core_request)

    def prefix(mode):
        def from_core(request, configuration, *, law_id):
            assert request is core_request and law_id == mode
            assert configuration == runner.configuration_for(endpoint)
            geo = {"fresh_projection": mode}
            values["geometry_request"] = geo
            mark("projection:" + mode, None)
            if mode == "geometry":
                return geo
            req = SimpleNamespace(geometry_request=geo)
            return SimpleNamespace(ecm_request=req) if mode == "environment" else req

        return from_core

    def geometry_prepare(request):
        assert request is values["geometry_request"]
        owner = values["geometry_owner"] = Owner("geometry")
        return mark("geometry", owner)

    def transition(stage, parent_stage):
        def request(owner, *, law_id):
            assert owner is values[parent_stage + "_owner"] and law_id == stage
            live = values[stage + "_request"] = SimpleNamespace(owner=owner)
            return mark(stage + "_request", live)

        def record(live):
            assert live is values[stage + "_request"]
            assert live.owner is values[parent_stage + "_owner"]
            return mark(stage + "_record", {"parent_stage": parent_stage})

        def execute(live):
            assert live is values[stage + "_request"]
            owner = values[stage + "_owner"] = Owner(stage)
            return mark(stage, owner)

        return request, record, execute

    er, em, ep = transition("ecm", "geometry")
    vr, vm, vp = transition("environment", "ecm")
    pr, pm, pp = transition("poisson", "environment")
    steps = runner._pipeline(
        runner.CASES[0],
        output,
        runner.configuration_for(endpoint),
        endpoint,
        fixtures=SimpleNamespace(caller=fixture),
        initial=SimpleNamespace(prepare=initial_prepare),
        core=SimpleNamespace(LAW_ID="core", from_initial=core_from_initial),
        geometry=SimpleNamespace(
            LAW_ID="geometry", from_core=prefix("geometry"), prepare=geometry_prepare
        ),
        ecm=SimpleNamespace(
            LAW_ID="ecm",
            from_core=prefix("ecm"),
            from_geometry=er,
            request_record=em,
            prepare_continuation=ep,
        ),
        environment_source=SimpleNamespace(
            LAW_ID="environment",
            from_core=prefix("environment"),
            from_ecm=vr,
            request_record=vm,
            prepare_continuation=vp,
        ),
        poisson=SimpleNamespace(
            LAW_ID="poisson", from_environment=pr, request_record=pm, prepare_continuation=pp
        ),
    )
    return steps, calls, values


@pytest.mark.parametrize("endpoint", runner.ENDPOINTS)
def test_pipeline_captures_distinct_trials_on_same_owners_without_rehydration(tmp_path, endpoint):
    steps, calls, values = pipeline_control(tmp_path, endpoint)
    assert not calls  # Merely building the plan performs no source work.
    result = runner.run_stages(steps, runner.Evidence(tmp_path), SimpleNamespace(count=0, phase=""))
    assert result["status"] == "source_completed_unqualified"
    assert result["completed_stages"] == list(runner.stage_names(endpoint))
    mode = dict(
        near_neigh="geometry", makeECM="ecm", make_maskM="environment", lapENV_P_inv="environment"
    )[endpoint]
    expected = ["fixture", "pre_mesh", "core_request", "projection:" + mode, "geometry"]
    if endpoint != "near_neigh":
        expected += ["ecm_request", "ecm_record", "ecm"]
    if endpoint in ("make_maskM", "lapENV_P_inv"):
        expected += ["environment_request", "environment_record", "environment"]
    if endpoint == "lapENV_P_inv":
        expected += ["poisson_request", "poisson_record", "poisson"]
    assert calls == expected
    captured = {r["label"]: runner.read(tmp_path / r["path"]) for r in result["captures"]}
    assert captured["geometry"] == values["geometry_owner"].trial
    if endpoint != "near_neigh":
        assert captured["makeECM"] == values["ecm_owner"].trial
        assert captured["ecm_request"] == {"parent_stage": "geometry"}
    if endpoint in ("make_maskM", "lapENV_P_inv"):
        assert captured["make_maskM"] == values["environment_owner"].trial
        assert captured["environment_request"] == {"parent_stage": "ecm"}
    if endpoint == "lapENV_P_inv":
        assert captured["lapENV_P_inv"] == values["poisson_owner"].trial
        assert captured["poisson_request"] == {"parent_stage": "environment"}
    assert result["accepted_cases"] == 0


def test_poisson_requires_explicit_bounded_capture_transport(packet):
    prepared = packet.root / "poisson"
    plan = runner.prepare(
        prepared, repository=packet.repository, cpu=packet.cpu, stop_after="lapENV_P_inv"
    )
    assert plan["capture_transport"] == runner.payload.KIND
    assert plan["configuration"]["general options"]["comp grid size"] == 25
    assert plan["limits"] == runner.LIMITS
    plan.pop("capture_transport")
    path = prepared / "plan.json"
    path.chmod(0o644)
    path.write_text(json.dumps(plan))
    with pytest.raises(ValueError, match="Incomplete"):
        runner.verify_plan(prepared, runner.pin(path)["sha256"])


def test_poisson_predecessor_capture_failure_prevents_operator_entry(tmp_path):
    steps, calls, _ = pipeline_control(tmp_path, "lapENV_P_inv")

    class CaptureFailure(runner.Evidence):
        def save(self, label, value):
            return super().save(label, object() if label == "make_maskM" else value)

    result = runner.run_stages(steps, CaptureFailure(tmp_path), SimpleNamespace(count=0, phase=""))
    assert result["failed_stage"] == "make_maskM:capture"
    assert "poisson_request" not in calls and "poisson" not in calls
    assert result["accepted_cases"] == 0


def test_sidecar_capture_preserves_failed_partial_matrix_bytes(tmp_path):
    raw = bytes.fromhex("030000000000f87f") * (runner.payload.THRESHOLD // 8)
    error = RuntimeError("original operator failed")
    error.partial = {"raw_result": {"raw_bytes_hex": raw.hex()}, "live_grid": object()}
    evidence = runner.Evidence(tmp_path, sidecars=True)
    evidence.failure(error)
    assert [row["status"] for row in evidence.rows] == ["saved", "capture_failed"]
    assert runner.payload.read(tmp_path / evidence.rows[0]["path"]) == {"raw_bytes_hex": raw.hex()}
    assert len(runner.payload.files(tmp_path / evidence.rows[0]["path"])) == 2


@pytest.mark.parametrize("stop", ["geometry", "makeECM", "make_maskM"])
def test_extended_pipeline_capture_failure_stops_before_next_owner_use(tmp_path, stop):
    steps, calls, _ = pipeline_control(tmp_path, "make_maskM")

    class CaptureFailure(runner.Evidence):
        def save(self, label, value):
            return super().save(label, object() if label == stop else value)

    result = runner.run_stages(steps, CaptureFailure(tmp_path), SimpleNamespace(count=0, phase=""))
    assert result["failed_stage"] == stop + ":capture" and result["source_error"] is None
    assert len(result["captures"]) == runner.stage_names("make_maskM").index(stop) + 1
    assert (
        calls[-1] == {"geometry": "geometry", "makeECM": "ecm", "make_maskM": "environment"}[stop]
    )
    if stop == "geometry":
        assert "ecm_request" not in calls
    if stop == "makeECM":
        assert "environment_request" not in calls


def test_execution_verification_uses_frozen_source_after_checkout_moves(packet):
    (packet.repository / runner.OWN).write_text("# subsequent checkout development\n")
    assert (
        runner.verify_release(packet.prepared, packet.sha, packet.release, runner.CASES[0])
        == packet.plan
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("plan_sha256", "0" * 64),
        ("snapshot_sha256", "0" * 64),
        ("allow_actual_source_diagnostic", False),
        ("allow_actual_source_diagnostic", 1),
        ("scientific_qualification", True),
        ("case", runner.CASES[1]),
        ("source_review", None),
    ],
)
def test_release_mismatches_refuse_before_any_launch(packet, field, value):
    release = runner.read(packet.release)
    release[field] = value
    packet.release.write_text(json.dumps(release))
    with pytest.raises(ValueError, match="release"):
        runner.verify_release(packet.prepared, packet.sha, packet.release, runner.CASES[0])


def test_release_review_and_native_source_drift_refuse(packet):
    packet.review.write_text("changed review")
    with pytest.raises(ValueError, match="external"):
        runner.verify_release(packet.prepared, packet.sha, packet.release, runner.CASES[0])
    packet.native.write_text("changed native source")
    with pytest.raises(ValueError, match="external"):
        runner.verify_plan(packet.prepared, packet.sha)


def test_missing_release_never_starts_child(packet, monkeypatch):
    monkeypatch.setattr(
        runner.guard, "run_bounded", lambda *a, **k: pytest.fail("unexpected launch")
    )
    output = packet.root / "not-started"
    with pytest.raises(FileNotFoundError):
        runner.launch(packet.prepared, packet.sha, packet.root / "absent", runner.CASES[0], output)
    assert not output.exists()


def test_snapshot_change_and_incomplete_preparation_refuse(packet):
    file = packet.prepared / "source" / runner.OWN
    file.chmod(0o644)
    file.write_text("changed frozen source")
    with pytest.raises(ValueError, match="Changed snapshot"):
        runner.verify_plan(packet.prepared, packet.sha)
    runner.write(packet.prepared / "preparation-failure.json", {"failed": True})
    with pytest.raises(ValueError, match="Incomplete"):
        runner.verify_plan(packet.prepared, packet.sha)


def test_failed_preparation_retains_error_and_never_publishes_plan(packet):
    packet.native.write_text("drift before preparation")
    target = packet.root / "failed-preparation"
    with pytest.raises(ValueError, match="external"):
        runner.prepare(target, repository=packet.repository, cpu=packet.cpu)
    assert (target / "preparation-failure.json").is_file()
    assert not (target / "plan.json").exists()


def test_overlay_pins_include_versioned_shared_libraries(packet):
    overlay = packet.root / "overlay"
    overlay.mkdir()
    library = overlay / "libnative.so.6.0.0"
    library.write_bytes(b"synthetic library bytes, never loaded")
    prepared = packet.root / "with-overlay"
    plan = runner.prepare(
        prepared, repository=packet.repository, cpu=packet.cpu, runtime_paths=[overlay]
    )
    assert runner.pin(library) in plan["external_inputs"]
    library.write_bytes(b"changed library")
    with pytest.raises(ValueError, match="external"):
        runner.verify_plan(prepared, runner.pin(prepared / "plan.json")["sha256"])


def test_output_escape_link_and_reuse_refused(packet):
    with pytest.raises(ValueError):
        runner.output_path(packet.root.parent / "outside")
    link = packet.root / "linked"
    link.symlink_to(packet.root / "prepared", target_is_directory=True)
    with pytest.raises(ValueError, match="Linked"):
        runner.output_path(link / "child")
    with pytest.raises(FileExistsError):
        runner.prepare(packet.prepared, repository=packet.repository, cpu=packet.cpu)


def test_wrong_cpu_refuses(packet, monkeypatch):
    monkeypatch.setattr(runner.os, "sched_getaffinity", lambda pid: {packet.cpu, packet.cpu + 1})
    with pytest.raises(ValueError, match="single CPU"):
        runner.verify_release(packet.prepared, packet.sha, packet.release, runner.CASES[0])


@pytest.mark.parametrize("target", ["prepared", "source", "native"])
def test_output_cannot_modify_prepared_or_native_inputs(packet, target):
    roots = {
        "prepared": packet.prepared,
        "source": packet.prepared / "source",
        "native": runner.NATIVE,
    }
    output = roots[target] / "new-run"
    with pytest.raises(ValueError, match="overlaps"):
        runner.launch(packet.prepared, packet.sha, packet.release, runner.CASES[0], output)
    assert not output.exists()


def test_environment_discards_inherited_source_and_gpu_settings(packet, monkeypatch):
    monkeypatch.setenv("PYTHONPATH", str(packet.repository) + ":/unknown")
    monkeypatch.setenv("CELLS_BETSE_SOURCE", "/unknown/native")
    monkeypatch.setenv("PYTHONHOME", "/unknown/python")
    env = runner.environment(packet.prepared / "source", packet.plan)
    assert env["PYTHONPATH"].split(":") == [
        str(packet.prepared / "source"),
        str(packet.prepared / "source/src"),
    ]
    assert env["CUDA_VISIBLE_DEVICES"] == ""
    assert env["OPENBLAS_NUM_THREADS"] == "1"
    assert "PYTHONHOME" not in env and "CELLS_BETSE_SOURCE" not in env


def test_source_failure_retains_parent_trial_cause_and_unrun_stages(tmp_path):
    evidence = runner.Evidence(tmp_path)
    work = SimpleNamespace(phase="", count=7)
    later = []
    parent = {"cache": [1, 2], "rng": {"position": 624, "cached": -0.25}}

    def fail():
        try:
            raise ZeroDivisionError("original native defect")
        except ZeroDivisionError as original:
            error = ValueError("owned trial refused")
            error.trial, error.parent_state = {"partial": [3]}, parent
            raise error from original

    result = runner.run_stages(
        [("parent", lambda: parent), ("pre_mesh", fail), ("later", lambda: later.append(1))],
        evidence,
        work,
    )
    assert result["status"] == "diagnostic_failed" and result["failed_stage"] == "pre_mesh"
    assert result["completed_stages"] == ["parent"] and not later
    assert result["source_error"]["nodes"][1]["type"].endswith("ZeroDivisionError")
    assert all(row["status"] == "saved" for row in result["captures"])
    assert len(result["captures"]) == 3
    assert runner.read(tmp_path / result["captures"][2]["path"]) == {
        "cache": [1, 2],
        "rng": {"position": 624, "cached": {"float64_bits": "000000000000d0bf"}},
    }
    assert result["accepted_cases"] == 0


def test_capture_failure_is_separate_and_stops_continuation(tmp_path):
    evidence = runner.Evidence(tmp_path)
    later = []
    result = runner.run_stages(
        [("parent", lambda: object()), ("later", lambda: later.append(1))],
        evidence,
        SimpleNamespace(phase="", count=0),
    )
    assert result["failed_stage"] == "parent:capture"
    assert result["source_error"] is None and not later
    assert result["captures"][0]["status"] == "capture_failed"


def test_failed_live_partial_capture_does_not_hide_primary_error(tmp_path):
    error = RuntimeError("primary source failure")
    error.partial = {"live_owner": object(), "saved_cache": {"value": 3}}
    evidence = runner.Evidence(tmp_path)
    evidence.failure(error)
    assert [r["status"] for r in evidence.rows] == ["capture_failed", "saved"]
    assert runner.read(tmp_path / evidence.rows[1]["path"]) == {"value": 3}
    assert runner.exception_record(error)["nodes"][0]["message"] == "primary source failure"


def test_exception_graph_retains_separate_capture_error_and_cycles():
    primary, capture = ValueError("source"), RuntimeError("capture")
    wrapper = RuntimeError("sealing")
    wrapper.source_error, wrapper.capture_error = primary, capture
    wrapper.__cause__ = primary
    primary.__cause__ = wrapper
    record = runner.exception_record(wrapper)
    assert len(record["nodes"]) == 3
    assert record["nodes"][0]["cause"] == record["nodes"][0]["source_error"]
    assert record["nodes"][1]["cause"] == record["root"]


def test_capture_preserves_noncanonical_nan_bits(tmp_path):
    bits = "030000000000f87f"
    value = struct.unpack("<d", bytes.fromhex(bits))[0]
    evidence = runner.Evidence(tmp_path)
    assert evidence.save("failed-cache", {"nan": value})
    saved = runner.read(tmp_path / evidence.rows[0]["path"])
    assert saved["nan"] == {"float64_bits": bits}


def test_completed_diagnostic_never_implies_parity(tmp_path):
    work = SimpleNamespace(phase="", count=19)
    result = runner.run_stages(
        [(name, lambda: {"synthetic": True}) for name in runner.STAGES],
        runner.Evidence(tmp_path),
        work,
    )
    assert result["status"] == "source_completed_unqualified"
    assert result["completed_stages"] == list(runner.STAGES)
    assert result["observed_source_entry_attempts"] == 19
    assert result["independent_cases"] == 1 and result["accepted_cases"] == 0
    assert all(result[key] == value for key, value in runner.NO_CREDIT.items())


def test_worklog_chains_restores_and_records_failed_attempt(tmp_path):
    source = tmp_path / "frozen"
    namespace = {}
    exec(
        compile(
            "def action():\n    raise ValueError('synthetic')\n",
            str(source / "src/cells/probe.py"),
            "exec",
        ),
        namespace,
    )
    previous = sys.getprofile()
    called = []

    def outer(frame, event, arg):
        if frame.f_code is namespace["action"].__code__ and event == "call":
            called.append(True)

    work = runner.WorkLog(tmp_path, source, phases=("authentication",))
    sys.setprofile(outer)
    try:
        with pytest.raises(ValueError, match="synthetic"), work.active():
            work.phase = "authentication"
            namespace["action"]()
        assert sys.getprofile() is outer
    finally:
        sys.setprofile(previous)
    rows = [json.loads(line) for line in work.path.read_text().splitlines()]
    assert called == [True] and len(rows) == 1
    assert rows[0]["phase"] == "authentication" and rows[0]["event"] == "call"
    assert rows[0]["entry_is_success_or_independent_case"] is False


def test_observer_budget_failure_is_not_a_native_failure(tmp_path):
    source = tmp_path / "source"
    namespace = {}
    exec(
        compile("def action():\n    return 1\n", str(source / "src/cells/probe.py"), "exec"),
        namespace,
    )
    work = runner.WorkLog(tmp_path, source, phases=("native",))
    work.trace_count = 100000
    with work.active():
        result = runner.run_stages(
            [("native", namespace["action"])], runner.Evidence(tmp_path), work
        )
    assert result["status"] == "diagnostic_failed"
    assert result["observer_error"] and result["interrupted_exception_graph"]
    assert result["source_error"] is None
    assert not result["completed_stages"] and result["accepted_cases"] == 0


def test_swallowed_profiler_error_still_stops_diagnostic(tmp_path):
    source = tmp_path / "source"
    namespace = {}
    exec(
        compile("def inner():\n    return 1\n", str(source / "src/cells/probe.py"), "exec"),
        namespace,
    )
    work = runner.WorkLog(tmp_path, source, phases=("native", "later"))
    work.trace_count = 100000
    later = []

    def catching_action():
        try:
            namespace["inner"]()
        except RuntimeError:
            return {"partial": "returned after profile failure"}

    with work.active():
        result = runner.run_stages(
            [("native", catching_action), ("later", lambda: later.append(True))],
            runner.Evidence(tmp_path),
            work,
        )
    assert result["status"] == "diagnostic_failed" and result["failed_stage"] == "native:observer"
    assert result["observer_error"] and result["source_error"] is None
    assert not later and not result["completed_stages"]
    assert result["captures"][0]["label"] == "native:interrupted-return"


def test_recursive_helper_work_is_counted_without_per_element_logging(tmp_path):
    source = tmp_path / "source"
    namespace = {}
    exec(
        compile(
            "def encode(n):\n    return encode(n-1) if n else 0\n",
            str(source / "src/cells/codec.py"),
            "exec",
        ),
        namespace,
    )
    work = runner.WorkLog(tmp_path, source, phases=("upstream", "authentication"))
    with work.active():
        work.phase = "upstream"
        namespace["encode"](200)
        work.phase = "authentication"
        namespace["encode"](300)
    summary = runner.read(tmp_path / "work-counts.json")
    assert summary["observed_entry_attempts"] == 502
    assert summary["ordered_trace_entries"] == 2
    assert [(row["phase"], row["attempts"]) for row in summary["call_sites"]] == [
        ("upstream", 201),
        ("authentication", 301),
    ]
    assert summary["independent_case_credit"] == 0
    assert len(work.path.read_text().splitlines()) == 2


def test_literal_kernel_entries_remain_in_exact_order(tmp_path):
    source = tmp_path / "source"
    namespace = {}
    exec(
        compile(
            "def native_body():\n    return 1\n", str(source / "src/cells/native_kernel.py"), "exec"
        ),
        namespace,
    )
    work = runner.WorkLog(
        tmp_path, source, phases=("constructor", "authentication", "continuation")
    )
    with work.active():
        for phase in ("constructor", "authentication", "authentication", "continuation"):
            work.phase = phase
            namespace["native_body"]()
    rows = [json.loads(line) for line in work.path.read_text().splitlines()]
    assert [row["phase"] for row in rows] == [
        "constructor",
        "authentication",
        "authentication",
        "continuation",
    ]
    assert [row["sequence"] for row in rows] == list(range(4))
    summary = runner.read(tmp_path / "work-counts.json")
    assert summary["observed_entry_attempts"] == summary["ordered_trace_entries"] == 4


def _work_row(work, index):
    return dict(
        sequence=work.count,
        phase=work.phase,
        event="call",
        source="src/cells/codec.py",
        function=f"metadata_{index}",
        line=index + 1,
        c_callable=None,
        entry_is_success_or_independent_case=False,
    )


def test_worklog_phase_reuse_does_not_spend_distinct_site_budget(tmp_path):
    work = runner.WorkLog(tmp_path, tmp_path / "source", phases=runner.stage_names("lapENV_P_inv"))
    stream = io.StringIO()
    for phase in work.phases:
        work.phase = phase
        for index in range(400):
            work.record(stream, _work_row(work, index))
            work.record(stream, _work_row(work, index))
    summary = work.summary()
    rows = [json.loads(line) for line in stream.getvalue().splitlines()]
    assert summary["distinct_call_sites"] == 400
    assert summary["site_phase_counters"] == len(rows) == 4800
    assert summary["observed_entry_attempts"] == 9600
    assert all(row["attempts"] == 2 for row in summary["call_sites"])
    assert [row["sequence"] for row in rows] == list(range(0, 9600, 2))
    assert [row["phase"] for row in rows] == [phase for phase in work.phases for _ in range(400)]


def test_worklog_true_site_limit_remains_4096(tmp_path):
    work = runner.WorkLog(tmp_path, tmp_path / "source", phases=("native",))
    stream = io.StringIO()
    for index in range(4096):
        work.record(stream, _work_row(work, index))
    before = work.summary()
    with pytest.raises(RuntimeError, match="distinct-call-site"):
        work.record(stream, _work_row(work, 4096))
    assert work.summary() == before
    work.phase = "native"
    work.record(stream, _work_row(work, 0))
    assert len(work.sites) == 4096 and len(work.counts) == work.count == 4097


def test_worklog_undeclared_phase_refuses_before_recording(tmp_path):
    work = runner.WorkLog(tmp_path, tmp_path / "source", phases=("native",))
    stream = io.StringIO()
    before = work.summary()
    work.phase = "unbounded-label"
    with pytest.raises(RuntimeError, match="Undeclared"):
        work.record(stream, _work_row(work, 0))
    assert work.summary() == before and not stream.getvalue()


def _worklog_frame(source, filename="codec.py"):
    namespace = {}
    exec(
        compile("def probe():\n    return 1\n", str(source / "src/cells" / filename), "exec"),
        namespace,
    )
    return SimpleNamespace(f_code=namespace["probe"].__code__)


def test_worklog_group_selection_ignores_parent_directory_and_parameter_keywords():
    from validation.betse import native_multi_cell_environment_qualification as environment

    wanted = SimpleNamespace(originalname="test_worklog_cached", name="test_worklog_cached[x]")
    incidental = SimpleNamespace(
        originalname="test_unrelated",
        name="test_unrelated[worklog]",
        nodeid="/worklog-output/test_module.py::test_unrelated[worklog]",
    )
    fallback = SimpleNamespace(originalname=None, name="test_stage_timing_capture[value]")
    items = [wanted, incidental, fallback]
    selected, deselected = environment._software_selection("worklog", items)
    assert selected == [wanted, fallback] and deselected == [incidental]
    assert items == [wanted, incidental, fallback]
    assert environment._software_selection("all", items) == (items, [])


def test_worklog_fast_repetitions_match_direct_record_and_literal_order(tmp_path):
    source = tmp_path / "source"
    work = runner.WorkLog(tmp_path, source, phases=("first", "second"))
    reference = runner.WorkLog(tmp_path, source, phases=("first", "second"))
    expected = io.StringIO()
    metadata = _worklog_frame(source)
    literal = _worklog_frame(source, "probe_kernel.py")
    events = [
        ("first", metadata, "call", None),
        ("first", metadata, "c_call", len),
        ("first", literal, "call", None),
    ] * 100 + [
        ("second", metadata, "call", None),
        ("second", literal, "c_call", list.append),
    ] * 50
    with work.active():
        for phase, frame, event, arg in events:
            work.phase = reference.phase = phase
            reference.record(
                expected,
                dict(
                    sequence=reference.count,
                    phase=phase,
                    event=event,
                    source="src/cells/" + frame.f_code.co_filename.rsplit("/", 1)[-1],
                    function=frame.f_code.co_qualname,
                    line=frame.f_code.co_firstlineno,
                    c_callable=getattr(arg, "__qualname__", None) if event == "c_call" else None,
                    entry_is_success_or_independent_case=False,
                ),
            )
            work._active_profile(frame, event, arg)
    assert work.summary() == reference.summary()
    assert work.path.read_text() == expected.getvalue()
    runner.write(tmp_path / "counter-comparison.json", work.summary())


def test_worklog_cached_event_still_obeys_previous_hook_phase_source_and_retention(tmp_path):
    source = tmp_path / "source"
    work = runner.WorkLog(tmp_path, source, phases=("first", "second"))
    frame = _worklog_frame(source)
    before = sys.getprofile()
    seen = []
    change = []

    def outer(current, event, arg):
        if current is frame:
            seen.append(event)
            if change:
                change.pop(0)()

    sys.setprofile(outer)
    try:
        with work.active():
            profile = work._active_profile
            work.phase = "first"
            profile(frame, "call", None)
            change.append(lambda: setattr(work, "phase", "second"))
            profile(frame, "return", None)
            profile(frame, "call", None)
            change.append(lambda: setattr(work, "_retaining_failure", 1))
            profile(frame, "call", None)
            change.append(lambda: setattr(work, "_retaining_failure", 0))
            profile(frame, "exception", None)
            old_source = work.source
            change.append(lambda: setattr(work, "source", str(tmp_path / "other") + "/"))
            profile(frame, "call", None)
            change.append(lambda: setattr(work, "source", old_source))
            profile(frame, "call", None)
        assert sys.getprofile() is outer
    finally:
        sys.setprofile(before)
    assert seen == ["call", "return", "call", "call", "exception", "call", "call"]
    assert work.count == 3 and work.failure_retention_entries == 1
    assert [(row["phase"], row["attempts"]) for row in work.counts.values()] == [
        ("first", 1),
        ("second", 2),
    ]


def test_worklog_location_cache_is_bounded_without_dropping_counts(tmp_path):
    source = tmp_path / "source"
    frame = _worklog_frame(source)
    work = runner.WorkLog(tmp_path, source, phases=("native",))
    codes = []
    with work.active():
        work.phase = "native"
        for _ in range(4100):
            code = frame.f_code.replace()
            codes.append(code)
            work._active_profile(SimpleNamespace(f_code=code), "call", None)
        closure = dict(
            zip(
                work._active_profile.__code__.co_freevars,
                [cell.cell_contents for cell in work._active_profile.__closure__],
                strict=True,
            )
        )
        assert 0 < len(closure["locations"]) <= 4096
    assert work.count == 4100 and work.trace_count == len(work.counts) == len(work.sites) == 1


@pytest.mark.parametrize("replacement", ["instance", "class", "code"])
def test_worklog_fast_path_never_bypasses_replaced_record(tmp_path, monkeypatch, replacement):
    source = tmp_path / "source"
    work = runner.WorkLog(tmp_path, source, phases=("native",))
    frame = _worklog_frame(source)

    def rejected(self, stream, row):
        raise ValueError("replacement recorder rejection")

    with work.active():
        work.phase = "native"
        work._active_profile(frame, "call", None)
        if replacement == "instance":
            monkeypatch.setattr(work, "record", lambda stream, row: rejected(work, stream, row))
        elif replacement == "class":
            monkeypatch.setattr(runner.WorkLog, "record", rejected)
        else:
            monkeypatch.setattr(runner.WorkLog.record, "__code__", rejected.__code__)
        with pytest.raises(ValueError, match="replacement recorder rejection"):
            work._active_profile(frame, "call", None)
    assert work.count == 1 and work.failure is not None


def test_worklog_fast_repetition_keeps_phase_and_trace_budget_failure_order(tmp_path):
    source = tmp_path / "source"
    work = runner.WorkLog(tmp_path, source, phases=("native",))
    metadata, literal = _worklog_frame(source), _worklog_frame(source, "probe_source.py")
    with work.active():
        work.phase = "native"
        work._active_profile(metadata, "call", None)
        work.trace_count = 100000
        work._active_profile(metadata, "call", None)
        assert work.count == 2
        work.phase = "undeclared"
        with pytest.raises(RuntimeError, match="Undeclared"):
            work._active_profile(metadata, "call", None)
        assert work.count == 2
        work.phase = "native"
        with pytest.raises(RuntimeError, match="diagnostic allowance"):
            work._active_profile(literal, "call", None)
        assert work.count == 3 and work.trace_count == 100000
        assert list(work.counts.values())[-1]["attempts"] == 1
    assert work.failure is not None


def test_worklog_bound_recorder_replacement_keeps_the_actual_receiver(tmp_path):
    source = tmp_path / "source"
    work = runner.WorkLog(tmp_path, source, phases=("native",))
    other = runner.WorkLog(tmp_path / "other", source, phases=("native",))
    frame = _worklog_frame(source)
    with work.active():
        work.phase = "native"
        work._active_profile(frame, "call", None)
        work.record = other.record
        work._active_profile(frame, "call", None)
        assert work.count == other.count == 1
        other.phases = ("imports", "different")
        with pytest.raises(RuntimeError, match="Undeclared diagnostic work phase"):
            work._active_profile(frame, "call", None)
        assert work.count == other.count == 1
    assert work.failure is not None
    runner.write(
        tmp_path / "receiver-counters.json", dict(work=work.summary(), other=other.summary())
    )


@pytest.mark.parametrize("failed_operation", ["write", "flush"])
def test_worklog_writer_failure_after_fast_repetitions_preserves_primary(
    tmp_path, monkeypatch, failed_operation
):
    source = tmp_path / "source"
    work = runner.WorkLog(tmp_path, source, phases=("native",))
    metadata, literal = _worklog_frame(source), _worklog_frame(source, "probe_kernel.py")
    original_open = type(work.path).open
    fail = []
    primary = ValueError("original source failure")

    class Wrapped:
        def __init__(self, raw):
            self.raw = raw

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.raw.close()

        def write(self, text):
            if fail and failed_operation == "write":
                raise OSError("record write failure")
            return self.raw.write(text)

        def flush(self):
            if fail and failed_operation == "flush":
                raise OSError("record flush failure")
            return self.raw.flush()

        def fileno(self):
            return self.raw.fileno()

    def open_path(path, *args, **kwargs):
        raw = original_open(path, *args, **kwargs)
        return Wrapped(raw) if path == work.path else raw

    monkeypatch.setattr(type(work.path), "open", open_path)
    with pytest.raises(ValueError) as saved, work.active():
        work.phase = "native"
        work._active_profile(metadata, "call", None)
        work._active_profile(metadata, "call", None)
        fail.append(True)
        with pytest.raises(OSError, match="record " + failed_operation + " failure"):
            work._active_profile(literal, "call", None)
        assert work.count == 3 and work.trace_count == 1
        raise primary
    assert saved.value is primary and work.failure is not None


@pytest.mark.parametrize(
    "phases", [(), ("same", "same"), ("imports",), tuple(map(str, range(12))), (1,), ("x" * 65,)]
)
def test_worklog_requires_bounded_phase_declaration(tmp_path, phases):
    with pytest.raises(ValueError, match="bounded, unique"):
        runner.WorkLog(tmp_path, tmp_path / "source", phases=phases)


@pytest.mark.parametrize("reject_capture", [False, True])
@pytest.mark.parametrize("restore_root", [False, True])
def test_exhausted_recorder_preserves_failure_capture_and_prior_guard(
    tmp_path, monkeypatch, reject_capture, restore_root
):
    source = tmp_path / "source"
    entered, captured, later = [], [], []
    namespace = {"entered": entered}
    exec(
        compile(
            "def action():\n    entered.append(True)\n",
            str(source / "src/cells/probe.py"),
            "exec",
        ),
        namespace,
    )
    capture_namespace = {"original": runner.archive.snapshot}
    exec(
        compile(
            "def capture(value):\n    return original(value)\n",
            str(source / "validation/betse/retention.py"),
            "exec",
        ),
        capture_namespace,
    )
    monkeypatch.setattr(runner.archive, "snapshot", capture_namespace["capture"])
    work = runner.WorkLog(tmp_path, source, phases=("native", "later"))
    work.trace_count = 100000
    evidence = runner.Evidence(tmp_path)
    previous = sys.getprofile()

    def outer(frame, event, arg):
        if frame.f_code is capture_namespace["capture"].__code__ and event == "call":
            captured.append(True)
            if reject_capture:
                raise ValueError("outer capture guard")

    def nested_observer_action():
        active = sys.getprofile()
        try:
            namespace["action"]()
        except RuntimeError as error:
            error.partial = {"values": [1, -0.0]}
            raise
        finally:
            # Native observers can restore the Root profiler after CPython
            # disabled it on an exception; reproduce that exact condition.
            if restore_root:
                sys.setprofile(active)

    sys.setprofile(outer)
    try:
        with work.active():
            result = runner.run_stages(
                [("native", nested_observer_action), ("later", lambda: later.append(True))],
                evidence,
                work,
            )
        assert sys.getprofile() is outer
    finally:
        sys.setprofile(previous)
    runner.write(
        tmp_path / "retention-control.json",
        dict(
            result=result, entered=entered, later=later, guard_entries=captured, work=work.summary()
        ),
    )
    # The original serializer recursively visits the list and both scalars;
    # a rejecting outer guard stops at the list's first entry.
    assert not entered and not later and captured == [True] * (1 if reject_capture else 3)
    assert result["source_error"] is None and result["observer_error"] == work.failure
    assert (
        work.failure["nodes"][0]["message"] == "Source entry log exceeded its diagnostic allowance"
    )
    assert result["accepted_cases"] == 0 and not result["completed_stages"]
    assert work._retaining_failure == 0
    assert len(evidence.rows) == 1
    row = evidence.rows[0]
    if reject_capture:
        assert row["status"] == "capture_failed"
        assert row["error"]["nodes"][0]["message"] == "outer capture guard"
    else:
        assert row["status"] == "saved" and work.failure_retention_entries > 0
        assert runner.read(tmp_path / row["path"]) == [1, {"float64_bits": "0000000000000080"}]


@pytest.mark.parametrize("mode", ["source_failure", "guard_stop", "success"])
def test_launch_retains_terminal_artifacts_without_retry(packet, monkeypatch, mode):
    monkeypatch.setattr(runner.guard, "memory_available", lambda: 13 * 2**30)
    attempts = []

    def bounded(command, *, directory, cwd, env, **limits):
        attempts.append(command)
        assert limits == runner.LIMITS
        assert cwd == packet.prepared / "source"
        assert env["PYTHONPATH"].startswith(str(cwd))
        if mode == "success":
            runner.write(
                directory.parent / "diagnostic.json",
                dict(
                    status="source_completed_unqualified",
                    stop_after="near_neigh",
                    completed_stages=list(runner.STAGES),
                ),
            )
            result = dict(status="completed", returncode=0)
            runner.write(directory / "result.json", result)
            return result
        if mode == "source_failure":
            runner.write(
                directory.parent / "diagnostic.json",
                dict(status="diagnostic_failed", source_error="retained"),
            )
        else:
            runner.write(directory / "resource-stop.json", dict(reason="synthetic wall guard"))
        runner.write(directory / "failure.json", dict(status="failed", returncode=1))
        raise subprocess.CalledProcessError(1, command)

    monkeypatch.setattr(runner.guard, "run_bounded", bounded)
    output = packet.root / mode
    result = runner.launch(packet.prepared, packet.sha, packet.release, runner.CASES[0], output)
    assert len(attempts) == 1 and result["automatic_retry"] is False
    assert result["status"] == ("completed_unqualified" if mode == "success" else "failed")
    assert result["process_receipts"] and result["accepted_cases"] == 0
    assert (output / ("result.json" if mode == "success" else "failure.json")).is_file()


def test_low_memory_leaves_terminal_failure_without_launch(packet, monkeypatch):
    monkeypatch.setattr(runner.guard, "memory_available", lambda: 11 * 2**30)
    monkeypatch.setattr(
        runner.guard, "run_bounded", lambda *a, **k: pytest.fail("unexpected launch")
    )
    output = packet.root / "low-memory"
    result = runner.launch(packet.prepared, packet.sha, packet.release, runner.CASES[0], output)
    assert result["status"] == "failed" and result["diagnostic"] is None
    assert not result["process_receipts"]
    assert (output / "failure.json").is_file()


@pytest.mark.parametrize("operation", ["mkdir", "inputs_write"])
def test_owned_startup_failure_has_terminal_receipt(packet, monkeypatch, operation):
    output = packet.root / "startup-failure"
    if operation == "mkdir":
        original = type(output).mkdir

        def mkdir(path, *args, **kwargs):
            if path == output / "process":
                raise OSError("synthetic process-directory failure")
            return original(path, *args, **kwargs)

        monkeypatch.setattr(type(output), "mkdir", mkdir)
    else:
        original = runner.write

        def write(path, value):
            if path == output / "inputs.json":
                raise OSError("synthetic inputs-write failure")
            return original(path, value)

        monkeypatch.setattr(runner, "write", write)
    monkeypatch.setattr(
        runner.guard, "run_bounded", lambda *a, **k: pytest.fail("unexpected launch")
    )
    result = runner.launch(packet.prepared, packet.sha, packet.release, runner.CASES[0], output)
    assert result["status"] == "failed" and result["process"] is None
    assert (output / "failure.json").is_file()
