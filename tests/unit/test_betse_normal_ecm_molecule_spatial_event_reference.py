"""Source/metadata and synthetic comparison controls; actual spatial work held."""

import copy
import json
import sys
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from tests.unit.test_betse_normal_ecm_molecule_event_checkpoint import (
    no_actual_execution as no_actual_execution,
)
from validation.betse import betse_normal_ecm_molecule_spatial_event_reference as probe


@pytest.fixture(autouse=True)
def forbid_actual_spatial(no_actual_execution, monkeypatch, tmp_path):
    attempted = []
    codes = {
        probe.native.capture.__wrapped__.__code__,
        probe.native.evaluate.__code__,
        probe.independent.evaluate.__code__,
        probe.spatial.evaluate.__code__,
        probe._original_events.__code__,
        probe.literal.prepared_callback.__code__,
        probe.literal.TissueHandler._fire_events_tissue.__code__,
        probe.literal.TissueHandler.makeAllChanges.__code__,
    }
    previous = sys.getprofile()

    def guard(frame, event, arg):
        if previous is not None:
            previous(frame, event, arg)
        if event == "call" and frame.f_code in codes:
            attempted.append(frame.f_code.co_name)
            raise AssertionError("Actual spatial/native/reference execution forbidden")

    sys.setprofile(guard)
    try:
        yield attempted
    finally:
        sys.setprofile(previous)
        (tmp_path / "spatial-software-control.json").write_text(
            json.dumps(
                dict(
                    actual_spatial_native_reference_entries=attempted,
                    independent_biological_cases=0,
                    synthetic_only=True,
                    parent_admission=False,
                )
            )
        )
    assert attempted == []


def program(kind="gradient_x", targets=None):
    return probe.spatial.bind(
        kind=kind,
        target_domain="membranes",
        target_ids=["m" + str(i) for i in range(6)] if targets is None else targets,
        cell_ids=["c0", "c1", "c2"],
        membrane_ids=["m" + str(i) for i in range(6)],
        cell_centres_m=[[-2e-6, 1e-6], [1e-6, -1e-6], [4e-6, 3e-6]],
        membrane_midpoints_m=[
            [-3e-6, 0.0],
            [-1e-6, 2e-6],
            [0.0, -2e-6],
            [2e-6, 0.0],
            [3e-6, 2e-6],
            [5e-6, 4e-6],
        ],
        centre_m=[1e-6, 0.5e-6],
        x_offset=0.25e-6 if kind == "gradient_r" else 0.13,
        exponent=None if kind == "gradient_r" else 2.0,
        slope=0.7,
        z_offset=0.2,
        provenance="Synthetic declared source-probe geometry; not native owner authority",
    )


def inputs(programs=None):
    programs = {"Na": program()} if programs is None else programs
    return programs, dict(
        pulses={k: (0.125, 0.5, 0.0625, 0.25) for k in programs},
        defaults={k: float(i + 1) * 1e-18 for i, k in enumerate(probe.IONS)},
        present=probe.IONS,
        labels=(0.0, 0.125, 0.5),
        stores={
            k: np.full((4, 6) if k.startswith("Dm_") else (6,), float(i), dtype=np.float64)
            for i, k in enumerate(probe.STORES)
        },
        provenance="Synthetic software declaration only; no setup/finalizer/parent",
    )


def declared(programs=None):
    selected, kwargs = inputs(programs)
    return selected, probe.declaration(selected, **kwargs)


def test_source_plan_pins_factories_and_complete_event_bodies_without_execution(tmp_path):
    plan = probe.source_plan()
    assert plan["compiled_or_evaluated"] is False and plan["INIT_SIM_admission"] is False
    assert set(plan["factory_AST_sha256"]) == {"gradient_x", "gradient_y", "gradient_r"}
    assert all(plan["original_event_AST_equal"].values()) and plan["pulse_AST_equal"] is True
    assert probe.native.PINNED.items() <= probe.PINS.items()
    (tmp_path / "source-plan.json").write_text(json.dumps(plan))


@pytest.mark.parametrize("name", list(probe.PINS))
def test_source_pin_drift_refuses_before_compilation(tmp_path, name):
    root = tmp_path / "original"
    for relative in probe.PINS:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((probe.NATIVE_ROOT / relative).read_bytes())
    changed = root / name
    changed.write_bytes(changed.read_bytes() + b"\n# changed\n")
    with pytest.raises(ValueError, match="pin changed"):
        probe.source_plan(root)


@pytest.mark.parametrize("method", ["_fire_events_tissue", "makeAllChanges", "pulse"])
def test_event_body_drift_is_not_normalized(tmp_path, monkeypatch, method):
    source = Path(probe.literal.__file__).read_text()
    # Add an executable statement, preserving every original line and function.
    marker = "    def " + method if method != "pulse" else "def pulse"
    lines = source.splitlines(keepends=True)
    index = next(i for i, line in enumerate(lines) if line.startswith(marker))
    indentation = "        " if method != "pulse" else "    "
    lines.insert(index + 1, indentation + "source_probe_drift = 1\n")
    path = tmp_path / "changed.py"
    path.write_text("".join(lines))
    monkeypatch.setattr(probe, "literal", SimpleNamespace(__file__=str(path)))
    with pytest.raises(ValueError, match="source differs"):
        probe.source_plan()


@pytest.mark.parametrize(
    "kind,targets",
    [
        ("gradient_x", ["m0"] * 6),
        ("gradient_y", ["m5", "m2", "m2", "m0", "m4", "m1"]),
        ("gradient_r", ["m2", "m2", "m0"]),
        ("gradient_r", ["m1", "m4"]),
    ],
)
def test_declaration_preserves_full_geometry_target_occurrences_and_conditional_provenance(
    kind, targets
):
    programs, saved = declared({"Na": program(kind, targets)})
    assert saved["programs"]["Na"]["target_ids"] == targets
    assert saved["stores"]["Dm_scheduled"].shape == (4, 6)
    assert "not Parameters/YAML/finalized ownership" in saved["property_authority"]
    assert saved["INIT_SIM_admission"] is False and saved["independent_biological_cases"] == 0
    assert programs["Na"].target_ids == tuple(targets)


@pytest.mark.parametrize(
    "bad",
    [
        "empty",
        "unknown",
        "missing-pulse",
        "extra-pulse",
        "ramp",
        "missing-default",
        "integer-default",
        "presence",
        "labels",
        "label-bool",
        "store-dtype",
        "store-shape",
        "store-missing",
        "store-nonfinite",
        "provenance",
        "foreign-geometry",
        "stale-program",
    ],
)
def test_incomplete_or_foreign_probe_refuses_without_hydration(bad):
    programs, kwargs = inputs()
    if bad == "empty":
        programs = {}
    elif bad == "unknown":
        programs["pressure"] = programs.pop("Na")
    elif bad == "missing-pulse":
        kwargs["pulses"] = {}
    elif bad == "extra-pulse":
        kwargs["pulses"]["K"] = kwargs["pulses"]["Na"]
    elif bad == "ramp":
        kwargs["pulses"]["Na"] = (0.125, 0.5, 0.0, 0.25)
    elif bad == "missing-default":
        kwargs["defaults"].pop("Ca")
    elif bad == "integer-default":
        kwargs["defaults"]["Ca"] = 1
    elif bad == "presence":
        kwargs["present"] = ("K", "Na")
    elif bad == "labels":
        kwargs["labels"] = ()
    elif bad == "label-bool":
        kwargs["labels"] = (True,)
    elif bad == "store-dtype":
        kwargs["stores"]["Dm_base"] = kwargs["stores"]["Dm_base"].astype(np.float32)
    elif bad == "store-shape":
        kwargs["stores"]["Dm_base"] = np.zeros((4, 3), dtype=np.float64)
    elif bad == "store-missing":
        kwargs["stores"].pop("P_cells")
    elif bad == "store-nonfinite":
        kwargs["stores"]["Dm_base"][0, 0] = np.nan
    elif bad == "provenance":
        kwargs["provenance"] = ""
    elif bad == "foreign-geometry":
        data = asdict(programs["Na"])
        data.pop("identity")
        data["centre_m"] = (0.0, 0.0)
        programs["K"] = probe.spatial.bind(**data)
        kwargs["pulses"]["K"] = kwargs["pulses"]["Na"]
    else:
        object.__setattr__(programs["Na"], "identity", "foreign")
    with pytest.raises(ValueError):
        probe.declaration(programs, **kwargs)


@pytest.mark.parametrize("domain,targets", [("cells", ["c0"] * 3), ("membranes", ["m0", "m1"])])
def test_native_count_branch_is_not_repaired_or_relabelled(domain, targets):
    data = asdict(program())
    data.pop("identity")
    data.update(target_domain=domain, target_ids=targets)
    if domain == "membranes":
        with pytest.raises(ValueError, match="target-count"):
            probe.spatial.bind(**data)
    else:
        programs, kwargs = inputs({"Na": probe.spatial.bind(**data)})
        with pytest.raises(ValueError, match="membrane source branch"):
            probe.declaration(programs, **kwargs)


@pytest.mark.parametrize("released", [(False, False), (True, False), (False, True)])
def test_both_releases_precede_even_output_creation(tmp_path, monkeypatch, released):
    for name, enabled in zip(probe.RELEASES, released, strict=True):
        monkeypatch.setenv(name, "1" if enabled else "0")
    programs, kwargs = inputs()
    output = tmp_path / "unreleased"
    with pytest.raises(ValueError, match="remains held"):
        probe.paired_probe(output, programs, **kwargs)
    assert not output.exists()


def test_released_missing_declaration_refuses_before_native_or_output(tmp_path, monkeypatch):
    for name in probe.RELEASES:
        monkeypatch.setenv(name, "1")
    _, kwargs = inputs()
    output = tmp_path / "incomplete"
    with pytest.raises(ValueError, match="supported membrane ions"):
        probe.paired_probe(output, {}, **kwargs)
    assert not output.exists()


@pytest.mark.parametrize(
    "bad", ["value", "dtype", "shape", "nonfinite", "oracle-value", "oracle-shape", "budget"]
)
def test_factory_comparator_detects_complete_output_and_independent_budget_drift(bad):
    original = np.array([0.25, 0.5], dtype=np.float64)
    candidate = original.copy()
    oracle = dict(factor=[0.25, 0.5], factor_budget=1e-15)
    if bad == "value":
        candidate[0] = np.nextafter(candidate[0], 1.0)
    elif bad == "dtype":
        candidate = candidate.astype(np.float32)
    elif bad == "shape":
        candidate = candidate.reshape(1, 2)
    elif bad == "nonfinite":
        original[0] = candidate[0] = np.nan
    elif bad == "oracle-value":
        oracle["factor"][0] = 0.26
    elif bad == "oracle-shape":
        oracle["factor"] = [0.25]
    else:
        oracle["factor_budget"] = float("inf")
    with pytest.raises(ValueError):
        probe.compare_factory(original, candidate, oracle)


def synthetic_result(saved):
    stores = {k: v.copy() for k, v in saved["stores"].items()}
    frames = [
        dict(
            label=i,
            time=t,
            method=method,
            before=copy.deepcopy(stores),
            after=copy.deepcopy(stores),
        )
        for i, t in enumerate(saved["labels"])
        for method in ("_fire_events_tissue", "makeAllChanges")
    ]
    callbacks = [
        dict(ion=ion, time=t, status="returned", value=1)
        for t in saved["labels"]
        for ion in probe.IONS
        if ion in saved["programs"] and ion in saved["present"]
    ]
    return dict(
        status="source_completed", factories={}, frames=frames, callbacks=callbacks, stores=stores
    )


@pytest.mark.parametrize(
    "bad",
    [
        "store-value",
        "store-dtype",
        "store-shape",
        "stage-order",
        "clock",
        "callback-duplicate",
        "callback-omitted",
        "callback-value",
        "callback-ion",
        "completion",
    ],
)
def test_full_store_order_callback_and_completion_differences_reject(bad):
    _, saved = declared({"Na": program(), "K": program("gradient_y")})
    original = synthetic_result(saved)
    candidate = copy.deepcopy(original)
    if bad == "store-value":
        candidate["stores"]["Dm_scheduled"][1, 3] += 1.0
    elif bad == "store-dtype":
        candidate["stores"]["Dm_scheduled"] = candidate["stores"]["Dm_scheduled"].astype(np.float32)
    elif bad == "store-shape":
        candidate["stores"]["Dm_scheduled"] = candidate["stores"]["Dm_scheduled"][:, :3]
    elif bad == "stage-order":
        candidate["frames"][0], candidate["frames"][1] = (
            candidate["frames"][1],
            candidate["frames"][0],
        )
    elif bad == "clock":
        candidate["frames"][0]["time"] = 0.01
    elif bad == "callback-duplicate":
        candidate["callbacks"].insert(0, copy.deepcopy(candidate["callbacks"][0]))
    elif bad == "callback-omitted":
        candidate["callbacks"].pop()
    elif bad == "callback-value":
        candidate["callbacks"][0]["value"] = 2
    elif bad == "callback-ion":
        candidate["callbacks"][0]["ion"] = "Ca"
    else:
        candidate["status"] = "source_failed"
    with pytest.raises(ValueError):
        probe.compare_legs(original, candidate, saved)


def test_common_trace_corruption_cannot_validate_two_identical_results():
    _, saved = declared()
    result = synthetic_result(saved)
    result["frames"].pop()
    with pytest.raises(ValueError, match="missing event"):
        probe.compare_legs(result, copy.deepcopy(result), saved)


def test_exact_synthetic_success_is_source_scope_only():
    _, saved = declared()
    result = synthetic_result(saved)
    compared = probe.compare_legs(result, copy.deepcopy(result), saved)
    assert compared == dict(status="source_probe_match", successful_event_admission=False)


def test_synthetic_assignment_failure_retains_partial_writes_and_blocks_completion(
    tmp_path, monkeypatch
):
    programs, saved = declared(
        {"Na": program("gradient_r"), "K": program("gradient_r", ["m1", "m4"])}
    )

    class SoftwareEvents:
        def _fire_events_tissue(self, phase, t):
            for index, ion in enumerate(probe.IONS):
                if phase.p.scheduled_options[ion + "_mem"] != 0:
                    suffix = probe.SUFFIXES[index]
                    assert getattr(self, "dyna_" + suffix)(t) == 1
                    phase.sim.Dm_scheduled[index][getattr(self, "targets_" + suffix)] = getattr(
                        self, "scalar_" + suffix
                    )

        def makeAllChanges(self, sim):
            raise AssertionError("The failed synthetic prefix must not reach completion")

    def fake_factory(original, program, cells, p, captured):
        captured["synthetic_only"] = True
        return np.arange(6, dtype=np.float64) + 10.0, lambda t: 1

    monkeypatch.setattr(probe, "_factory", fake_factory)
    monkeypatch.setattr(probe, "literal", SimpleNamespace(TissueHandler=SoftwareEvents))
    attempts = []
    left = probe._leg(
        tmp_path / "left",
        saved,
        programs,
        original=True,
        attempts=attempts,
        original_events=SoftwareEvents,
    )
    right = probe._leg(
        tmp_path / "right",
        saved,
        programs,
        original=False,
        attempts=attempts,
        original_events=SoftwareEvents,
    )
    assert left["status"] == right["status"] == "source_failed"
    assert (
        left["stage"] == "label-0-_fire_events_tissue" and left["failure"]["type"] == "ValueError"
    )
    np.testing.assert_array_equal(left["stores"]["Dm_scheduled"][0], np.arange(6) + 10.0)
    np.testing.assert_array_equal(
        left["stores"]["Dm_scheduled"][1], saved["stores"]["Dm_scheduled"][1]
    )
    np.testing.assert_array_equal(left["stores"]["Dm_cells"], saved["stores"]["Dm_cells"])
    assert [row["ion"] for row in left["callbacks"]] == ["Na", "K"]
    assert probe.compare_legs(left, right, saved)["status"] == "matching_source_refusal_diagnostic"
    assert len(list(tmp_path.glob("*/label-0-*/manifest.json"))) == 2
    assert all(row.get("evidence_complete", True) for row in attempts)
    assert not any(row["operation"].endswith("makeAllChanges") for row in attempts)


@pytest.mark.parametrize("writer_fails", [False, True])
def test_primary_source_exception_cause_and_attempt_are_retained_with_recovery_failure(
    tmp_path, monkeypatch, writer_fails
):
    cause, primary = LookupError("original cause"), ValueError("primary synthetic source failure")
    payloads = []

    def fail():
        raise primary from cause

    def writer(directory, payload):
        payloads.append(payload)
        if writer_fails:
            raise OSError("secondary synthetic archive failure")

    monkeypatch.setattr(probe.archives, "write_archive", writer)
    attempts = []
    with pytest.raises(ValueError) as caught:
        probe._take(
            tmp_path,
            "synthetic-operation",
            fail,
            attempts=attempts,
            work="synthetic_only",
            readers={"available": lambda: np.array([1.0])},
        )
    assert caught.value is primary and primary.__cause__ is cause
    assert payloads[0]["failure"]["stage"] == "synthetic-operation"
    assert attempts[0]["failure_origin"] == "source"
    assert attempts[0]["evidence_complete"] is (not writer_fails)
    if writer_fails:
        assert attempts[0]["recovery_errors"][0]["type"] == "OSError"
        assert "secondary synthetic archive failure" in primary.__notes__[0]


def test_successful_operation_with_evidence_IO_failure_is_not_a_source_refusal(
    tmp_path, monkeypatch
):
    def fail_writer(directory, payload):
        raise OSError("synthetic evidence write failed")

    monkeypatch.setattr(probe.archives, "write_archive", fail_writer)
    attempts = []
    with pytest.raises(OSError) as caught:
        probe._take(
            tmp_path,
            "synthetic-return",
            lambda: 1,
            attempts=attempts,
            work="synthetic_only",
            readers={},
        )
    assert not hasattr(caught.value, "spatial_probe_source_operation")
    assert attempts[0]["failure_origin"] == "evidence" and attempts[0]["evidence_complete"] is False


@pytest.mark.parametrize("unwind", [False, True])
def test_exact_profiled_synthetic_factory_unwind_keeps_primary_and_restores_profiler(
    monkeypatch, unwind
):
    primary, cause = ValueError("synthetic factory error"), LookupError("synthetic cause")

    def synthetic(pc, cells, p):
        intermediate = np.array([2.0, 4.0], dtype=np.float64)
        if unwind:
            raise primary from cause
        return intermediate, lambda t: 1

    monkeypatch.setattr(probe.native, "capture", lambda: {"gradient_x": synthetic})
    captured = {}
    previous = sys.getprofile()
    if unwind:
        with pytest.raises(ValueError) as caught:
            probe._factory(True, program(), None, None, captured)
        assert caught.value is primary and primary.__cause__ is cause
        assert captured["return_or_unwind_type"] == "NoneType"
    else:
        scalar, dynamic = probe._factory(True, program(), None, None, captured)
        np.testing.assert_array_equal(scalar, [2.0, 4.0])
        assert callable(dynamic) and captured["return_or_unwind_type"] == "tuple"
    assert sys.getprofile() is previous
    np.testing.assert_array_equal(captured["intermediate"], [2.0, 4.0])
