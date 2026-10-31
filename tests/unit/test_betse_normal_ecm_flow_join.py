"""Unrun disabled ownership seam checks; active flow panel is already separate."""

import os
import subprocess
import sys
import traceback
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

from cells.processes import betse_normal_ecm_flow_join as joined
from cells.processes import betse_normal_ion_join as ions
from validation.betse import betse_mechanics_join_runtime as runtime
from validation.betse import betse_normal_ecm_flow_join_boundaries as boundary
from validation.betse import betse_normal_ecm_flow_join_fixtures as fixtures
from validation.betse.betse_normal_ecm_flow_join_replay import PREFIX, persist


def root(name):
    return Path(os.environ["CELLS_COMPONENT_EVIDENCE"]) / PREFIX / name


def child(source, mode):
    process = None
    with (source / (mode + ".stdout.log")).open("x") as stream:
        try:
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-B",
                    "-m",
                    "validation.betse.betse_normal_ecm_flow_join_replay",
                    "--mode",
                    mode,
                    "--source",
                    str(source),
                ],
                stdout=stream,
                stderr=subprocess.STDOUT,
            )
            runtime.write(
                source / (mode + "-child-started.json"),
                dict(pid=process.pid, parent_pid=os.getpid(), actual_nested_child=True),
            )
            process.wait(timeout=400)
        except BaseException as error:
            runtime.write(
                source / (mode + "-child-failure.json"),
                dict(
                    type=type(error).__name__, reason=str(error), traceback=traceback.format_exc()
                ),
            )
            if process is not None and process.poll() is None:
                process.kill()
                process.wait()
            raise
        finally:
            stream.flush()
            os.fsync(stream.fileno())
            if process is not None:
                runtime.write(
                    source / (mode + "-child-process.json"),
                    dict(pid=process.pid, returncode=process.returncode),
                )
    started = runtime.read(source / mode / "started.json")
    assert started["pid"] == process.pid and started["parent_pid"] == os.getpid()
    assert process.returncode == 0
    assert runtime.read(source / mode / "result.json")["status"] == "passed"
    origin = runtime.read(source / mode / "runtime.json")
    assert origin["file_errors"] == {} and origin["mapped_file_errors"] == []
    assert origin["production_modules_loaded"] == []
    if mode == "reference":
        assert origin["scientific_modules_loaded"] == []


@pytest.mark.parametrize("case", fixtures.CASES)
def test_disabled_flow_carries_complete_ordinary_source_owners(case):
    source = root(case)
    inputs = fixtures.fixture(case)
    runtime.write(source / "inputs.json", inputs)
    original = deepcopy(inputs)
    points = []

    def observer(name, value):
        persist(source, name, value)

    try:
        binding = joined.bind(inputs)
        persist(source, "binding", binding)
        parent = joined.initialize(binding, observer=observer)
        states = [parent]
        for index in range(3):
            before = ions.digest(parent)
            candidate, context = joined.advance(binding, parent, observer=observer)
            # Reuse the unchanged driver at the identical complete parent.
            baseline, _ = joined.ordinary.advance(binding.ordinary, parent)
            persist(source, "baseline-" + str(index), baseline)
            boundary.assert_identical(runtime.plain(candidate), runtime.plain(baseline))
            assert before == ions.digest(parent)
            point = context["disabled_flow_point"]
            joined.verify_point(binding, parent, point)
            with pytest.raises(ValueError, match="actual prior full parent"):
                joined.verify_point(binding, parent, replace(point, identity="f" * 64))
            points.append(runtime.plain(point.values))
            projected = boundary.disabled_reference(points[-1])
            runtime.write(source / ("disabled-conditional-" + str(index) + ".json"), projected)
            if index == 0:
                exported = joined.standalone_diagnostic_input(binding, parent, point)
                persist(source, "standalone-input-export-only", exported)
                assert exported["ordinary_activation"] is False
                assert exported["ordinary_feedback"] is False
                assert exported["numerical_flow_evaluations"] == 0
            states.append(candidate)
            parent = candidate
        runtime.write(source / "points.json", points)
        child(source, "native")
        child(source, "reference")
        assert inputs == original
    except BaseException as error:
        persist(
            source,
            "failure",
            dict(
                type=type(error).__name__,
                reason=str(error),
                partial=getattr(error, "partial", None),
                traceback=traceback.format_exc(),
            ),
        )
        raise
    finally:
        runtime.write(source / "completed-points.json", points)


@pytest.mark.parametrize("defect", fixtures.REFUSALS)
def test_unsupported_activation_or_flow_feedback_is_refused(defect):
    source = root(defect)
    inputs = fixtures.fixture()
    ordinary = inputs["ordinary_inputs"]
    if defect == "enabled-flow":
        ordinary["mechanics_definition"]["policy"]["fluid_flow"] = True
        expected = "Pinned ordinary loader disables flow"
    else:
        ordinary["field_inputs"]["steps"][0]["material"]["velocity_x_m_s"][1][1] = 1e-9
        expected = "Ordinary disabled-flow composition requires shared held-zero velocity stores"
    runtime.write(source / "inputs.json", inputs)
    with pytest.raises(ValueError, match=expected) as caught:
        joined.bind(inputs)
    runtime.write(
        source / "refusal.json", dict(type=type(caught.value).__name__, reason=str(caught.value))
    )


def test_precommit_observer_failure_retains_the_complete_disabled_flow_seam():
    source = root("precommit-observer-failure")
    inputs = fixtures.fixture()
    runtime.write(source / "inputs.json", inputs)
    binding = joined.bind(inputs)
    parent = joined.initialize(binding)
    before = ions.digest(parent)

    def fail(name, value):
        persist(source, name, value)
        if name == "step-0-flow-point":
            raise RuntimeError("retained disabled-flow precommit observer failure")

    with pytest.raises(joined.FlowJoinRejected) as caught:
        joined.advance(binding, parent, observer=fail)
    persist(source, "failure", caught.value.partial)
    assert ions.digest(parent) == before
    partial = caught.value.partial
    assert partial["accepted_candidate"] is False and partial["ordinary_getFlow_executed"] is False
    point = partial["completed_flow_point"]
    assert point["parent_identity"] == parent.identity and point["source_step"] == 0
    records = partial["completed_records"]
    assert "step-0-mechanics-output-before-material" in records
    assert "step-0-flow-point" in records
    assert "step-0-material-output-before-field" not in records
    error = caught.value
    causes = []
    while error is not None:
        causes.append((type(error).__name__, str(error)))
        error = error.__cause__
    assert ("RuntimeError", "retained disabled-flow precommit observer failure") in causes
