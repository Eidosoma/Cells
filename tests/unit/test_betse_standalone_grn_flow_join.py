"""Unrun source activation, molecular advection and full partial-write checks."""

import hashlib
import os
import subprocess
import sys
import traceback
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest

from cells.processes import betse_standalone_grn_flow_join as model
from tests.unit import test_betse_ecm_sim_grn as legacy
from validation.betse import betse_mechanics_join_runtime as runtime
from validation.betse import betse_standalone_grn_flow_join_checks as checks
from validation.betse import betse_standalone_grn_flow_join_fixtures as fixtures
from validation.betse.betse_normal_ecm_mechanics_join_boundaries import assert_identical
from validation.betse.betse_standalone_grn_flow_join_replay import PREFIX, persist


def root(case):
    return Path(os.environ["CELLS_COMPONENT_EVIDENCE"]) / PREFIX / case


def child(source, mode):
    process = None
    with (source / (mode + ".stdout.log")).open("x") as stream:
        try:
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-B",
                    "-m",
                    "validation.betse.betse_standalone_grn_flow_join_replay",
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
            process.wait(timeout=480)
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
    assert (
        process.returncode == 0
        and started["pid"] == process.pid
        and started["parent_pid"] == os.getpid()
    )
    assert (
        started["input_sha256"] == hashlib.sha256((source / "inputs.json").read_bytes()).hexdigest()
    )
    origin = runtime.read(source / mode / "runtime.json")
    assert origin["production_modules_loaded"] == []
    assert origin["file_errors"] == {} and origin["mapped_file_errors"] == []
    if mode == "reference":
        assert origin["scientific_modules_loaded"] == []


def references(source, name):
    return [
        runtime.read(source / "reference" / name / ("projected-reference-" + str(p) + ".json"))
        for p in (100, 160)
    ]


def save_rows(source, name, rows):
    persist(source, name, rows)
    errors = [row["metric"]["normalized_max_error"] for row in rows.values()]
    resolution = [row["resolution"]["normalized_max_error"] for row in rows.values()]
    assert rows and max(errors) <= 1 and max(resolution) <= 0.1


def run(inputs, source):
    runtime.write(source / "inputs.json", inputs)
    points = []
    binding = model.bind(inputs)
    persist(source, "binding", binding)
    runtime.write(
        source / "production-parent-runtime-provenance.json", model.api().__source_provenance__
    )
    parent = model.initialize(binding)
    persist(source, "cold", parent.snapshot)
    cold = parent.snapshot
    history = []
    runtime.write(source / "cold-point.json", legacy.cold_inputs(inputs))
    points.append(dict(name="cold-point"))
    for invocation, call in enumerate(inputs["calls"]):
        step_index = []

        def before_step(payload, invocation=invocation, step_index=step_index):
            name = "call-" + str(invocation) + "-step-" + str(len(step_index))
            persist(source, name, payload)
            points.append(dict(name=name))
            step_index.append(name)

        original = model.api().ions.digest(parent)
        try:
            candidate, trace = model.advance(binding, parent, before_step=before_step)
        except BaseException as error:
            persist(
                source,
                "source-failure-" + str(invocation),
                dict(
                    type=type(error).__name__,
                    reason=str(error),
                    code=getattr(error, "code", None),
                    stage=getattr(error, "stage", None),
                    partial=getattr(error, "partial", None),
                    traceback=traceback.format_exc(),
                ),
            )
            runtime.write(source / "points-index.json", points)
            raise
        persist(
            source, "invocation-" + str(invocation), dict(snapshot=candidate.snapshot, trace=trace)
        )
        assert model.api().ions.digest(parent) == original
        history.append(dict(snapshot=candidate.snapshot, trace=trace))
        runtime.write(
            source / ("clock-" + str(invocation) + ".json"),
            dict(mode="standalone_clock", call=call),
        )
        points.append(dict(name="clock-" + str(invocation)))
        persist(
            source,
            "activation-" + str(invocation),
            dict(mode="flow_activation", activation=trace["flow_activations"][0]),
        )
        points.append(dict(name="activation-" + str(invocation)))
        parent = candidate
    runtime.write(source / "points-index.json", points)
    return binding, cold, history


@pytest.mark.parametrize("case", fixtures.CASES)
def test_standalone_source_flow_and_held_molecular_advection(case):
    source = root(case)
    inputs = fixtures.fixture(case)
    original = deepcopy(inputs)
    try:
        _, cold, history = run(inputs, source)
        child(source, "native")
        child(source, "reference")
        for point in runtime.read(source / "reference/index.json"):
            assert (
                point["input_sha256"]
                == hashlib.sha256((source / (point["name"] + ".json")).read_bytes()).hexdigest()
            )
        metadata = runtime.read(source / "native/metadata.json")
        assert metadata["status"] == "source_completed" and metadata["failure"] is None
        assert metadata["RNG_unchanged"] and metadata["warnings"] == []
        assert metadata["nonfinite_source_arrays"] == []
        native_cold = runtime.read(source / "native/cold.json")
        assert_identical(runtime.plain(cold), native_cold)
        lower, target = references(source, "cold-point")
        save_rows(source, "cold-errors", legacy.compare_cold(cold, lower, target))
        proof = checks.held_source_owners(runtime.plain(cold), runtime.plain(history))
        runtime.write(source / "held-source-owners.json", proof)
        for invocation, row in enumerate(history):
            native = runtime.read(source / "native" / ("invocation-" + str(invocation) + ".json"))
            assert_identical(runtime.plain(row), native)
            trace = row["trace"]
            assert trace["warnings"] == []
            lower, target = references(source, "clock-" + str(invocation))
            actual = trace["events"][0]["clock"]
            np.testing.assert_array_equal(actual["tt"], target["tt"])
            np.testing.assert_array_equal(actual["tsamples"], target["sample_times"])
            assert len(trace["steps"]) == target["steps"]
            lower, target = references(source, "activation-" + str(invocation))
            activation = trace["flow_activations"][0]
            rows = {}
            for axis in ("x", "y"):
                wanted = np.asarray(target["velocity_" + axis + "_m_s"])
                actual = activation["after"]["simulator"]["u_env_" + axis]
                rows[axis] = legacy.report(
                    axis,
                    actual,
                    wanted,
                    lower["velocity_" + axis + "_m_s"],
                    2e-11 + 8e-12 * abs(wanted),
                    "m/s; inherited standalone GRN flow budget",
                )
            save_rows(source, "flow-errors-" + str(invocation), rows)
            if activation["recalculate_fluid"]:
                component = model.component_flow_readout(activation)
                persist(source, "existing-flow-component-" + str(invocation), component)
                np.testing.assert_array_equal(
                    component,
                    np.stack(
                        [
                            activation["after"]["simulator"]["u_env_x"],
                            activation["after"]["simulator"]["u_env_y"],
                        ]
                    ),
                )
            for step_index, step in enumerate(trace["steps"]):
                name = "call-" + str(invocation) + "-step-" + str(step_index)
                lower, target = references(source, name)
                save_rows(source, name + "-errors", legacy.compare_local(step, lower, target))
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


@pytest.mark.parametrize("case", fixtures.RAW_CASES)
def test_source_flow_defects_keep_partial_writes_and_earn_no_accuracy_credit(case):
    source = root(case)
    inputs = fixtures.raw_fixture(case)
    with pytest.raises(model.FlowJoinRejected) as caught:
        run(inputs, source)
    partial = caught.value.partial
    persist(source, "raw-source-partial", partial)
    assert partial["numerical_candidate_accepted"] is False
    child(source, "native")
    native = runtime.restore(runtime.read(source / "native/invocation-0.json"))
    metadata = runtime.restore(runtime.read(source / "native/metadata.json"))
    assert metadata["numerical_candidate_accepted"] is False
    before = partial["trace"]["flow_before_activation"]["simulator"]
    after = partial["snapshot"]["simulator"]
    if case == "missing-current-y-after-first-flow-write":
        assert metadata["failure"]["type"] == "AttributeError"
        assert partial["original_type"] == "AttributeError"
        assert "J_env_y" not in after and partial["snapshot"]["parameters"]["fluid_flow"] is True
        assert not np.array_equal(after["u_env_x"], before["u_env_x"])
        np.testing.assert_array_equal(after["u_env_y"], before["u_env_y"])
        assert partial["trace"]["flow_activations"] == ()
        failed_frames = [
            row for row in partial["trace"]["flow_source_frames"] if row["event"] == "exception"
        ]
        assert failed_frames and failed_frames[0]["actual_mean_concentration"] is not None
        assert failed_frames[0]["actual_mean_valence"] is not None
        assert failed_frames[0]["current_y_present"] is False
        assert_identical(runtime.plain(after), runtime.plain(native["snapshot"]["simulator"]))
    else:
        activation = partial["trace"]["flow_activations"][0]
        velocity = np.stack(
            (
                activation["after"]["simulator"]["u_env_x"],
                activation["after"]["simulator"]["u_env_y"],
            )
        )
        assert not np.isfinite(velocity).all()
        assert np.all(np.asarray(activation["source_returned_mean_concentration"]) == 0)
        assert float(activation["source_returned_mean_valence"]) != 0
        assert np.isinf(velocity).all()
        assert metadata["nonfinite_source_arrays"]
        native_velocity = np.stack(
            (
                native["trace"]["flow_activations"][0]["after"]["simulator"]["u_env_x"],
                native["trace"]["flow_activations"][0]["after"]["simulator"]["u_env_y"],
            )
        )
        np.testing.assert_array_equal(velocity, native_velocity)


@pytest.mark.parametrize("defect", fixtures.DEPENDENCIES)
def test_flow_requires_its_explicit_standalone_owner_state(defect):
    source = root(defect)
    inputs = fixtures.fixture()
    if defect == "missing-flow-owner":
        del inputs["flow_state"]["initial_simulator_fields"]["J_env_y"]
        expected = "Require all current, electric, pressure and initial velocity stores"
    elif defect == "foreign-cell-owners":
        inputs["flow_state"]["cell_ids"] = list(reversed(inputs["flow_state"]["cell_ids"]))
        expected = "Bind actual declared cell and membrane owners without reordering"
    elif defect == "wrong-grid-shape":
        inputs["flow_state"]["shape"] = [4, 3]
        expected = "Declare every C-order ECM owner exactly once"
    else:
        inputs["scope"]["fluid"] = False
        expected = "Only the explicit standalone ECM flow capability is extended"
    runtime.write(source / "inputs.json", inputs)
    with pytest.raises(ValueError, match=expected) as caught:
        model.bind(inputs)
    runtime.write(
        source / "refusal.json", dict(type=type(caught.value).__name__, reason=str(caught.value))
    )
