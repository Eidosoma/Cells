"""Bounded software controls, real four-step interfaces, and saved-reference columns."""

import ast
import copy
import importlib
import math
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
ctx = importlib.import_module("timed_context")
review = importlib.import_module("timed_reference_review")
job = importlib.import_module("timed_job")
nativecheck = importlib.import_module("timed_native_check")
cellscheck = importlib.import_module("timed_cells_check")
compare = importlib.import_module("timed_compare")


def mini():
    plan = copy.deepcopy(ctx.c.read(ctx.PLAN))
    views = ctx.views(plan)
    plan.update(
        histories=["a"],
        duration_s=0.0001,
        block_time_s=0.000025,
        release_time_s=0.00005,
        common_times_s=[0.0, 0.000025, 0.00005, 0.0001],
        native_steps_s=[0.000025],
        cells_steps_s=[0.000025],
    )
    view = views["a"]
    view["protocol"].update(
        duration_s=plan["duration_s"],
        common_times_s=plan["common_times_s"],
        native_steps_s=plan["native_steps_s"],
        cells_steps_s=plan["cells_steps_s"],
        cells_eager_step_s=0.000025,
        restart_time_s=0.00005,
        restart_step_s=0.000025,
    )
    for schedule in view["schedules"].values():
        for row in schedule:
            row["time"] = {0.0: 0.0, 0.0005: 0.000025, 0.001: 0.00005}[row["time"]]
    definitions = {}
    for condition in plan["conditions"]:
        for backend in ("jax_jit", "jax_eager"):
            definition = copy.deepcopy(
                view["cells_definitions"][ctx.key(condition, 0.000025, "jax_jit")]
            )
            definition["execution"].update(dt=0.000025, jit=backend == "jax_jit")
            definition["experiment"].update(
                end_time=0.0001, observation_times=plan["common_times_s"]
            )
            for control in definition["experiment"]["channel_controls"]:
                control["schedule"] = copy.deepcopy(view["schedules"][condition])
            definitions[ctx.key(condition, 0.000025, backend)] = definition
    view["cells_definitions"] = definitions
    return {"plan": plan, "views": {"a": view}}


@pytest.fixture(scope="module")
def native(tmp_path_factory):
    output = tmp_path_factory.mktemp("timed-native-smoke")
    r = mini()
    ctx.io.write(output / "fixture.json", r)
    code = """
import sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
import timed_context as ctx
import timed_native
output=Path(sys.argv[2])
r=ctx.c.read(output/'fixture.json')
selected=[('a',v,0.000025) for v in r['plan']['conditions']]
result=timed_native.worker(r,output,selections=selected)
ctx.io.write(output/'betse.json',result)
"""
    env = ctx.feedback.audit.preparation.old.ctx.worker_environment(
        r["views"]["a"]["preparation_registration"], output
    )
    subprocess.run(
        [
            "taskset",
            "-c",
            "0-3",
            str(ctx.c.REFERENCE_PYTHON),
            "-B",
            "-c",
            code,
            str(HERE),
            str(output),
        ],
        env=env,
        check=True,
        capture_output=True,
        text=True,
        timeout=25,
    )
    return r, output, ctx.c.read(output / "betse.json")


@pytest.fixture(scope="module")
def cells(tmp_path_factory):
    output = tmp_path_factory.mktemp("timed-cells-smoke")
    r = mini()
    r["plan"]["conditions"] = ["suppression_release"]
    view = r["views"]["a"]
    view["protocol"]["variants"] = r["plan"]["conditions"]
    view["cells_definitions"] = {
        key: value
        for key, value in view["cells_definitions"].items()
        if key.startswith("suppression_release/")
    }
    ctx.io.write(output / "fixture.json", r)
    code = """
import sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
import timed_context as ctx
import timed_cells
output=Path(sys.argv[2])
ctx.io.write(output/'cells.json',timed_cells.worker(ctx.c.read(output/'fixture.json'),output))
"""
    env = ctx.feedback.audit.preparation.old.ctx.worker_environment(
        r["views"]["a"]["preparation_registration"], output
    )
    subprocess.run(
        ["taskset", "-c", "0-3", str(ctx.c.CELLS_PYTHON), "-B", "-c", code, str(HERE), str(output)],
        env=env,
        check=True,
        capture_output=True,
        text=True,
        timeout=35,
    )
    return r, output, ctx.c.read(output / "cells.json")


@pytest.fixture(scope="module")
def saved_reference():
    r = ctx.c.read(ctx.CAPTURE / "registration.json")
    aggregate = ctx.c.read(ctx.CAPTURE / "reference.json")
    records = {k: ctx.io.read_compressed(ctx.CAPTURE / p) for k, p in aggregate["records"].items()}
    return review.Reference(r, records)


def test_scope_and_unchanged_physics():
    p = ctx.c.read(ctx.PLAN)
    ctx.validate_plan(p)
    views = ctx.views(p)
    assert p["native_runs"] == 2 * 2 * 4 * 3 and p["native_updates"] == 2 * 2 * 4 * sum(
        round(0.002 / s) for s in p["native_steps_s"]
    )
    for history, view in views.items():
        original = ctx.design.view(history)
        assert (
            view["protocol"]["trajectory_absolute"] == original["protocol"]["trajectory_absolute"]
        )
        assert view["protocol"]["refinement"] == original["protocol"]["refinement"]
        assert len(view["cells_definitions"]) == 16
        for definition in view["cells_definitions"].values():
            assert (
                definition["model"] == next(iter(original["cells_definitions"].values()))["model"]
            )
            assert definition["experiment"]["observation_times"] == p["common_times_s"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("automatic_polling", True),
        ("automatic_retry", True),
        ("automatic_followup", True),
        ("production_changed", True),
        ("reference_review_before_simulators", False),
        ("duration_s", 0.004),
        ("block_time_s", 0.0004),
        ("native_runs", 24),
        ("reference_integration_rerun", True),
        ("extra", 0),
    ],
)
def test_scope_expansion_rejected(field, value):
    plan = copy.deepcopy(ctx.c.read(ctx.PLAN))
    plan[field] = value
    with pytest.raises(ValueError):
        ctx.validate_plan(plan)


@pytest.mark.parametrize(
    "condition", ["baseline", "no_op", "static_blocked", "suppression_release"]
)
@pytest.mark.parametrize("step", [25e-6, 12.5e-6, 6.25e-6])
def test_elapsed_grids_and_sides(condition, step):
    view = ctx.views(ctx.c.read(ctx.PLAN))["a"]
    table = ctx.intervals(view["schedules"][condition], 0.002, step)
    assert table[-1]["end_s"] == 0.002
    assert table[round(0.0005 / step)]["start_s"] == 0.0005
    if condition == "suppression_release":
        assert ctx.availability(view["schedules"][condition], 0.0005, "left") == 1
        assert ctx.availability(view["schedules"][condition], 0.0005) == 0
        assert ctx.availability(view["schedules"][condition], 0.001, "left") == 0
        assert ctx.availability(view["schedules"][condition], 0.001) == 1
    assert table[1]["start_s"] != 0.002 / (len(table) - 1)


def test_no_off_grid_switch():
    with pytest.raises(ValueError):
        ctx.intervals(
            [{"time": 0.0, "availability": 1}, {"time": 0.00051, "availability": 0}], 0.002, 25e-6
        )


def test_reference_sources_and_capture_authenticate_without_models():
    with ctx.model_fence():
        result = ctx.prerequisite()
    assert len(result["files_sha256"]) == 34


@pytest.mark.parametrize(
    "suffix,dense",
    [
        ("sample/80/gate/0/0", False),
        ("sample/80/voltage_V/0", False),
        ("sample/80/bath_K_fmol", False),
        ("sample/80/0", True),
        ("sample/80/thermodynamics", False),
        ("sample/100/analytic_gate/1/0", False),
        ("segment/1/accepted/1/analytic_gate/0/0", False),
        ("segment/1/dense/0/0.5/analytic_gate/1/0", False),
        ("segment/0/endpoint/0/0", True),
        ("switch/0/left/flux_fmol_per_s/0", False),
        ("switch/0/right/rhs/gate_rate_per_s/0", False),
        ("switch/1/right/rhs/power_pJ_per_s/0", False),
        ("switch_agreement/0/right/gate/0/0", False),
        ("agreement/100/gate/1/0", False),
        ("interval/101/0", False),
        ("control/1/voltage_V/0", False),
    ],
)
@pytest.mark.parametrize("method", ["dop853_tight", "radau_check"])
def test_saved_reference_column_resolver(saved_reference, suffix, dense, method):
    key = "a/suppression_release/" + method
    a, b, unit = saved_reference.resolve(key + "/" + suffix, dense)
    assert math.isfinite(a) and math.isfinite(b)
    absolute = (
        5e-13
        if dense
        else saved_reference.r["inputs"]["reference"]["comparison_absolute"].get(unit, 2e-7)
    )
    assert abs(a - b) <= absolute + 2e-11 * abs(b)


def test_reference_crosscheck_rejects_corrupted_original_column(saved_reference):
    name = "a/suppression_release/dop853_tight/sample/80/voltage_V/0"
    a, b, unit = saved_reference.resolve(name)
    crossed = review.am.Crosscheck()
    crossed.add(name, a + 0.01, b, a, b, unit, 1e-8, 2e-11)
    assert crossed.failed == 1


def test_real_full_native_timed_loop_and_accounting(native):
    r, output, aggregate = native
    assert aggregate["native_runs"] == 8 and aggregate["native_updates"] == 32
    result = nativecheck.check(r, output, aggregate)
    assert result["status"] == "pass" and result["failed_comparisons"] == 0
    row = ctx.io.read_compressed(
        output / aggregate["records"]["a/suppression_release/dt_2.5e-05"]["observed"]
    )
    assert row["timed_input"]["applications"][1]["completed_updates"] == 1
    assert row["trace"]["steps"][1]["raw_label_s"] != 0.000025
    assert row["timed_input"]["intervals"][1]["availability"] == 0
    assert row["timed_input"]["intervals"][2]["availability"] == 1
    blocked = ctx.io.read_compressed(
        output / aggregate["records"]["a/static_blocked/dt_2.5e-05"]["observed"]
    )
    previous = blocked["trace"]["initial"]["physical"]["voltage_V"]
    for step in blocked["trace"]["steps"]:
        assert step["before"]["physical"]["voltage_V"] == nativecheck.pre_channel_voltage(previous)
        assert step["after_voltage"]["physical"]["voltage_V"] == previous


@pytest.mark.parametrize(
    "corruption",
    [
        "wrong_step",
        "wrong_raw_clock",
        "cumulative_input",
        "state_reset",
        "missing_application",
        "wrong_side",
    ],
)
def test_native_input_corruptions(native, corruption):
    r, output, aggregate = native
    row = ctx.io.read_compressed(
        output / aggregate["records"]["a/suppression_release/dt_2.5e-05"]["observed"]
    )
    entry = row["timed_input"]
    if corruption == "wrong_step":
        entry["applications"][1]["completed_updates"] += 1
    elif corruption == "wrong_raw_clock":
        entry["intervals"][1]["raw_label_s"] = entry["intervals"][1]["start_s"]
    elif corruption == "cumulative_input":
        entry["applications"][2]["applied_maxDm_m2_per_s"] = 0
    elif corruption == "state_reset":
        entry["applications"][1]["after"]["channel"]["m"][0] = 0
    elif corruption == "missing_application":
        entry["applications"].pop()
    elif corruption == "wrong_side":
        entry["intervals"][1]["availability"] = 1
    with pytest.raises(ValueError):
        nativecheck.input_checks(r["views"]["a"], row)


def test_real_cells_carry_restart_backend_and_side_rhs(cells):
    r, output, aggregate = cells
    view = r["views"]["a"]
    local = output / "a"
    rows = aggregate["by_history"]["a"]
    result = cellscheck.cells_checks(view, local, rows)
    sides = compare.check_side_probes(view, local, rows)
    assert result["status"] == sides["status"] == "pass"
    assert len(result["restarts"]) == 1 and len(result["backends"]) == 1
    assert rows["cells_trajectories"] == 2 and rows["resumed_segments"] == 1
    sources = ctx.c.read(
        ctx.design.audit.CAPTURE
        / "a/cells/active_channel/jax_jit/dt_5e-05/final-checkpoint/manifest.json"
    )["source_hashes"]
    saved = cellscheck.checkpoints(view, local, rows, sources)
    assert saved == {"checkpoints": 4, "checkpoint_arrays": 216}


@pytest.mark.parametrize(
    "condition", ["baseline", "no_op", "static_blocked", "suppression_release"]
)
@pytest.mark.parametrize("time_s", [0.0, 0.0005, 0.001, 0.002])
def test_checkpoint_event_clock_is_right_continuous(condition, time_s):
    view = ctx.views(ctx.c.read(ctx.PLAN))["a"]
    definition = view["cells_definitions"][ctx.key(condition, 0.000025, "jax_jit")]
    expected = (
        0 if condition in ("baseline", "static_blocked") else (time_s >= 0.0005) + (time_s >= 0.001)
    )
    assert cellscheck.checkpoint_event_index(definition, time_s) == expected


@pytest.mark.parametrize("field", ["time", "step_index", "event_index"])
def test_cells_checkpoint_rejects_changed_clock_even_with_rehashed_manifest(cells, field):
    _r, output, aggregate = cells
    key = "suppression_release/jax_jit/dt_2.5e-05"
    record = ctx.io.read_compressed(output / "a" / aggregate["by_history"]["a"]["records"][key])
    directory = output / "a/cells" / key / "final-checkpoint"
    manifest = ctx.c.read(directory / "manifest.json")
    manifest["clock"][field] = 0
    manifest["manifest_sha256"] = cellscheck.digest(
        {k: v for k, v in manifest.items() if k != "manifest_sha256"}
    )
    with pytest.raises(ValueError, match="Checkpoint complete clock"):
        cellscheck.checkpoint(
            directory, record, 4, manifest["source_hashes"], lambda _: manifest, ctx.c.sha
        )


@pytest.mark.parametrize(
    "corruption", ["gate", "bath", "channel_ledger", "padding", "blocked_energy", "right_readout"]
)
def test_cells_state_corruptions(cells, corruption):
    r, output, aggregate = cells
    view = r["views"]["a"]
    key = "suppression_release/jax_jit/dt_2.5e-05"
    record = ctx.io.read_compressed(output / "a" / aggregate["by_history"]["a"]["records"][key])
    fields = {
        "gate": ("gate", [2, 0, 0]),
        "bath": ("extracellular_amount_increment", [2, 1, 0]),
        "channel_ledger": ("channel_transferred", [2, 0]),
        "padding": ("channel_transferred", [2, 9]),
        "blocked_energy": ("dissipated_energy_pJ", [2, 0]),
    }
    if corruption == "right_readout":
        record["observations"]["channel_flux_fmol_per_s"]["values"][1][0] = 0.01
    else:
        field, indices = fields[corruption]
        array = record["history"][field]["values"]
        for i in indices[:-1]:
            array = array[i]
        array[indices[-1]] += 1e-3
    ledger = ctx.io.Ledger(cellscheck.cells_tolerances(view))
    try:
        cellscheck.cells_points_and_checks(view, record, ledger)
    except ValueError:
        return
    assert ledger.failed > 0


@pytest.mark.parametrize(
    "failure", ["review", "release", "verify", "betse", "cells", "compare", None]
)
def test_gated_sequence_never_runs_a_later_stage_after_failure(failure):
    steps = []

    def stage(name):
        steps.append(name)
        if name == failure:
            raise ValueError(name)
        return name

    def call():
        return job.gated_sequence(
            lambda: stage("review"),
            lambda: stage("release"),
            lambda: stage("verify"),
            stage,
            lambda *_: stage("compare"),
        )

    if failure:
        with pytest.raises(ValueError):
            call()
        assert steps[-1] == failure
        if failure in ("review", "release", "verify"):
            assert "betse" not in steps
    else:
        assert call() == ("review", "compare")
        assert steps == ["review", "release", "verify", "betse", "verify", "cells", "compare"]


def test_missing_reference_gate_blocks_worker_before_launch(tmp_path):
    with pytest.raises(FileNotFoundError):
        job.require_gate(tmp_path, {})


def test_changed_gate_digest_rejected(tmp_path):
    ctx.io.write(tmp_path / "registration.json", {})
    ctx.io.write(
        tmp_path / "reference-review.json",
        {
            "status": "piecewise_reference_review_closed",
            "independent": {
                "identities": 1485380,
                "column_mismatches": 0,
                "independent_numerical_rejections": 0,
            },
            "reference_completion_sha256": ctx.REFERENCE_SHA,
        },
    )
    r = {"plan": ctx.c.read(ctx.PLAN)}
    job.allow_simulators(tmp_path, r)
    job.require_gate(tmp_path, r)
    (tmp_path / "reference-review.json").write_text('{"status":"changed"}')
    with pytest.raises(ValueError):
        job.require_gate(tmp_path, r)


def test_detached_launch_never_waits_or_polls(tmp_path, monkeypatch):
    monkeypatch.setattr(job, "register", lambda *_: {"plan": ctx.c.read(ctx.PLAN)})
    monkeypatch.setattr(ctx.c, "sha", lambda _: "frozen")

    class Process:
        pid = 12345

        def __init__(self, command, **kwargs):
            assert kwargs["start_new_session"] is True

        def poll(self):
            pytest.fail("No polling")

        def wait(self):
            pytest.fail("No waiting")

    monkeypatch.setattr(job.subprocess, "Popen", Process)
    assert job.launch(tmp_path, tmp_path / "tests.xml")["automatic_polling"] is False


def test_capture_authentication_failure_has_durable_receipt(tmp_path, monkeypatch):
    def failure(_):
        raise ValueError("test rejection")

    monkeypatch.setattr(ctx, "authenticate", failure)
    monkeypatch.setattr(job.resource, "setrlimit", lambda *_: None)
    with pytest.raises(ValueError, match="test rejection"):
        job.execute(tmp_path)
    assert ctx.c.read(tmp_path / "failure.json")["stage"] == "authentication"
    assert not (tmp_path / "completion.json").exists()


def test_existing_directory_refused_before_authentication(tmp_path, monkeypatch):
    monkeypatch.setattr(ctx, "prerequisite", lambda: pytest.fail("Should not authenticate"))
    with pytest.raises(ValueError):
        job.register(tmp_path, tmp_path / "tests.xml")


def test_no_numerical_library_or_integrator_in_reference_review():
    tree = ast.parse((HERE / "timed_reference_review.py").read_text())
    names = {
        alias.name.split(".")[0]
        for n in ast.walk(tree)
        if isinstance(n, ast.Import)
        for alias in n.names
    }
    names |= {
        n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module
    }
    assert not names & {"cells", "betse", "numpy", "scipy", "jax", "jaxlib"}
    assert "solve_ivp" not in (HERE / "timed_reference_review.py").read_text()


@pytest.mark.parametrize("changed", [False, True])
def test_signed_history_comparison_uses_all_registered_conditions(tmp_path, changed):
    plan = ctx.c.read(ctx.PLAN)
    r = {"plan": plan, "views": ctx.views(plan)}
    protocol = ctx.c.read(compare.paired_compare.ctx.PROTOCOL) | {
        "variants": plan["conditions"],
        "common_times_s": plan["common_times_s"],
    }
    reference = {h: compare.reference_view(r, h) for h in plan["histories"]}
    results = {}
    for h in plan["histories"]:
        results[h] = {"native": {"points": {}}, "cells": {"points": {}}}
        for condition in plan["conditions"]:
            record = reference[h]["reference_solutions"][condition]
            points = [
                copy.deepcopy(record["readouts"][record["times_s"].index(t)])
                for t in plan["common_times_s"]
            ]
            for engine, backend, step in (
                ("native", None, plan["native_steps_s"][-1]),
                ("cells", "jax_jit", plan["cells_steps_s"][-1]),
            ):
                values = copy.deepcopy(points)
                if engine == "native":
                    for point in values:
                        point.pop("energy_pJ")
                if (
                    changed
                    and h == "b"
                    and condition == "suppression_release"
                    and engine == "cells"
                ):
                    values[-1]["voltage_V"][0] += 0.01
                results[h][engine]["points"][ctx.key(condition, step, backend)] = values
    result = compare.paired_compare.histories(
        r | {"protocol": protocol}, tmp_path, reference, results
    )
    assert len(result["comparisons"]) == 12
    assert (result["failed_comparisons"] > 0) is changed


@pytest.mark.parametrize("bad_grid", [None, "coarse", "finest"])
def test_comparison_assembly_retains_coarse_misses_and_rejects_finest(
    tmp_path, monkeypatch, bad_grid
):
    plan = ctx.c.read(ctx.PLAN)
    r = {"plan": plan, "views": ctx.views(plan)}
    refs = {h: compare.reference_view(r, h) for h in plan["histories"]}
    native = {"comparisons": 0, "failed_comparisons": 0, "observer_pairs": 24, "by_history": {}}
    actual_cells, side_cells, aggregate = {}, {}, {"by_history": {}}
    for h, view in r["views"].items():
        (tmp_path / h).mkdir()
        native["by_history"][h] = {"points": {}, "sides": {}}
        actual_cells[h] = {
            "points": {},
            "failed_comparisons": 0,
            "restarts": dict.fromkeys(plan["conditions"]),
            "backends": dict.fromkeys(plan["conditions"]),
        }
        side_cells[h] = {"points": {}, "checks": {"failed_comparisons": 0}}
        aggregate["by_history"][h] = {
            "records": dict.fromkeys(view["cells_definitions"], "fake.gz")
        }
        for condition in plan["conditions"]:
            row = refs[h]["reference_solutions"][condition]
            points = [row["readouts"][row["times_s"].index(t)] for t in plan["common_times_s"]]
            sides = compare.reference_sides(view, condition, refs[h])
            for step in plan["native_steps_s"]:
                key = ctx.key(condition, step)
                values = copy.deepcopy(points)
                for point in values:
                    point.pop("energy_pJ")
                if (
                    h == "a"
                    and condition == "suppression_release"
                    and bad_grid
                    and step == plan["native_steps_s"][0 if bad_grid == "coarse" else -1]
                ):
                    values[-1]["voltage_V"][0] += 0.01
                native["by_history"][h]["points"][key] = values
                native["by_history"][h]["sides"][key] = copy.deepcopy(sides)
            for key in view["cells_definitions"]:
                if key.startswith(condition + "/"):
                    actual_cells[h]["points"][key] = copy.deepcopy(points)
                    side_cells[h]["points"][key] = copy.deepcopy(sides)
    monkeypatch.setattr(nativecheck, "check", lambda *_: native)
    monkeypatch.setattr(compare, "reference_view", lambda _r, h: refs[h])
    monkeypatch.setattr(cellscheck, "cells_checks", lambda _v, path, _a: actual_cells[path.name])
    monkeypatch.setattr(compare, "check_side_probes", lambda _v, path, _a: side_cells[path.name])
    monkeypatch.setattr(
        cellscheck,
        "checkpoints",
        lambda *_: {"checkpoints": 24, "checkpoint_arrays": 1296},
    )
    monkeypatch.setattr(ctx.io, "read_compressed", lambda _: {"history": {}, "observations": {}})
    result = compare.check(r, tmp_path, {}, aggregate)
    assert result["checkpoints"] == 48 and result["checkpoint_arrays"] == 2592
    assert (result["status"] == "timed_release_capture_pass_pending_audit") is (
        bad_grid != "finest"
    )
    assert (result["coarse_diagnostic_failures"] > 0) is (bad_grid == "coarse")


@pytest.mark.parametrize(
    "stage", ["review", "betse", "cells", "comparison", "betse_timeout", "cells_timeout", None]
)
def test_controller_durable_success_and_stage_failures(tmp_path, monkeypatch, stage):
    r = mini() | {"tests": {"tests": 1}}
    seen = []
    monkeypatch.setattr(ctx, "authenticate", lambda _: r)
    monkeypatch.setattr(job.resource, "setrlimit", lambda *_: None)
    monkeypatch.setattr(job.os, "sched_getaffinity", lambda _: {0, 1, 2, 3})
    monkeypatch.setattr(job, "allow_simulators", lambda *_: None)
    monkeypatch.setattr(job, "require_gate", lambda *_: None)
    monkeypatch.setattr(job, "validate_worker", lambda _r, _p, kind: kind)
    ctx.io.write(tmp_path / "registration.json", {})

    def review_stage(_):
        seen.append("review")
        if stage == "review":
            raise ValueError("reference rejected")
        return {"independent": {"identities": 1}}

    def child(command, **_):
        kind = command[4]
        seen.append(kind)
        if stage == kind:
            raise subprocess.CalledProcessError(1, command)
        if stage == kind + "_timeout":
            raise subprocess.TimeoutExpired(command, 1)

    def comparison(*_):
        seen.append("comparison")
        if stage == "comparison":
            raise ValueError("comparison rejected")
        return {"status": "timed_release_capture_pass_pending_audit"}

    monkeypatch.setattr(review, "review", review_stage)
    monkeypatch.setattr(job.subprocess, "run", child)
    monkeypatch.setattr(compare, "check", comparison)
    if stage:
        with pytest.raises((ValueError, subprocess.SubprocessError)):
            job.execute(tmp_path)
        assert (tmp_path / "failure.json").exists()
        assert not (tmp_path / "completion.json").exists()
        assert seen[-1] == stage.removesuffix("_timeout")
    else:
        job.execute(tmp_path)
        assert seen == ["review", "betse", "cells", "comparison"]
        assert ctx.c.read(tmp_path / "completion.json")["automatic_followup"] is False


@pytest.mark.parametrize("corruption", [None, "duplicate", "missing_cells", "failure", "skip"])
def test_split_software_receipts_require_both_engines(tmp_path, monkeypatch, corruption):
    from xml.etree import ElementTree as ET

    monkeypatch.setattr(ctx, "ROOT", tmp_path)
    directory = tmp_path / "reports"
    directory.mkdir()
    names = [
        "test_real_full_native_timed_loop_and_accounting",
        "test_real_cells_carry_restart_backend_and_side_rhs",
        "test_reference_sources_and_capture_authenticate_without_models",
        "test_detached_launch_never_waits_or_polls",
        "test_reference_crosscheck_rejects_corrupted_original_column",
        "test_missing_reference_gate_blocks_worker_before_launch",
    ] + [f"test_synthetic_{i}" for i in range(50)]
    if corruption == "missing_cells":
        names[1] = "test_synthetic_missing"
    if corruption == "duplicate":
        names[-1] = names[0]
    paths = []
    for i, group in enumerate((names[:28], names[28:])):
        suite = ET.Element(
            "testsuite", tests=str(len(group)), failures="0", errors="0", skipped="0"
        )
        for name in group:
            row = ET.SubElement(
                suite,
                "testcase",
                classname="validation.betse.channel_release_pilot.test_timed_release",
                name=name,
            )
        if corruption in ("failure", "skip") and i == 1:
            ET.SubElement(row, "failure" if corruption == "failure" else "skipped")
        path = directory / f"part-{i}.xml"
        ET.ElementTree(suite).write(path)
        paths.append(path)
    if corruption:
        with pytest.raises(ValueError):
            ctx.test_receipt(paths)
    else:
        result = ctx.test_receipt(paths)
        assert result["tests"] == 56 and len(result["receipts"]) == 2
