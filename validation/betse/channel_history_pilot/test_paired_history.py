"""Bounded software/reference/interface checks; not the registered coupled panel."""

import copy
import importlib
import math
import sys
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
ctx = importlib.import_module("paired_context")
ref = importlib.import_module("paired_reference")
refcheck = importlib.import_module("paired_reference_check")
nativecheck = importlib.import_module("paired_native_check")
cellscheck = importlib.import_module("paired_cells_check")
compare = importlib.import_module("paired_compare")
job = importlib.import_module("paired_job")


@pytest.fixture(scope="module")
def protocol():
    return ctx.c.read(ctx.PROTOCOL)


@pytest.fixture(scope="module")
def views(protocol):
    return ctx.views(protocol)


def toy_parameters(active=True):
    return {
        "F": 96485.33212331001,
        "R": 8.31446261815324,
        "temperature_K": 298.15,
        "volume_pL": [0.5, 0.8],
        "area_m2": [3e-10, 4e-10],
        "cm_F_per_m2": 0.01,
        "initial_K_fmol": [70.0, 112.0],
        "outside_volume_pL": 5.0,
        "outside_K_fmol": 20.0,
        "initial_voltage_V": [-0.035, -0.05],
        "channel_enabled": [True, True],
        "Pmax_m_per_s": [1e-8 if active else 0.0] * 2,
    }


@pytest.fixture(scope="module")
def short_references(views):
    result = {}
    for name, original in views.items():
        view = copy.deepcopy(original)
        view["protocol"]["duration_s"] = 0.0001
        view["protocol"]["common_times_s"] = [0.0, 0.0001]
        view["protocol"]["reference"]["sample_dt_s"] = 0.00005
        view["reference_parameters"] = {
            v: toy_parameters(v == "active_channel") for v in view["protocol"]["variants"]
        }
        records = {}
        for variant in view["protocol"]["variants"]:
            for setting in view["protocol"]["reference"]["solves"]:
                records[variant + "/" + setting["id"]] = ref.integrate(
                    view["reference_parameters"][variant], setting, view["protocol"]
                )
        result[name] = view, records
    return result


@pytest.mark.parametrize("name", ["a", "b"])
def test_numeric_views_preserve_declared_gates_and_production_physics(protocol, views, name):
    view = views[name]
    assert view["protocol"]["initial_gate"] == protocol["histories"][name]
    assert (
        view["preparation_registration"]["protocol"]["initial_gate"] == protocol["histories"][name]
    )
    assert len(view["cells_definitions"]) == view["protocol"]["cells_trajectories"] == 8
    assert view["protocol"]["native_runs"] == 12
    for definition in view["cells_definitions"].values():
        for entry in definition["model"]["cells"]:
            assert [entry["channel"]["initial_gate"][g] for g in ("m", "h")] == protocol[
                "histories"
            ][name]
            assert entry["membrane"]["pump"] is None
    assert (
        view["protocol"]["trajectory_absolute"]
        == ctx.c.read(ctx.feedback.PROTOCOL)["trajectory_absolute"]
    )


@pytest.mark.parametrize(
    "field", ["production_changed", "automatic_polling", "automatic_retry", "automatic_followup"]
)
def test_unregistered_automatic_scope_is_rejected(protocol, field):
    p = copy.deepcopy(protocol)
    p[field] = True
    with pytest.raises(ValueError):
        ctx.validate_protocol(p)


@pytest.mark.parametrize("name", ["a", "b"])
@pytest.mark.parametrize("variant", ["active_channel", "blocked_channel"])
@pytest.mark.parametrize("method", ["dop853_base", "dop853_tight", "radau_check"])
def test_reference_initial_state_dense_samples_and_analytic_control(
    short_references, name, variant, method
):
    view, rows = short_references[name]
    row = rows[variant + "/" + method]
    p, plan = view["reference_parameters"][variant], view["protocol"]
    setting = next(s for s in plan["reference"]["solves"] if s["id"] == method)
    refcheck.validate_record(row, p, setting, plan)
    assert row["accepted_states"][0] == ref.initial_state(p, plan["initial_gate"])
    for t, expected in zip(row["sample_times_s"], row["sample_states"], strict=True):
        np.testing.assert_allclose(refcheck.sample_state(row, t), expected, atol=5e-13, rtol=2e-13)
    if variant == "blocked_channel":
        assert all(point["transfer_fmol"] == [0.0, 0.0] for point in row["readouts"])


@pytest.mark.parametrize("name", ["a", "b"])
def test_complete_short_reference_gate_uses_independent_readouts(short_references, tmp_path, name):
    view, rows = short_references[name]
    aggregate = {"records": {}, "reference_solves": len(rows)}
    for index, (key, row) in enumerate(rows.items()):
        path = f"reference-{index}.json.gz"
        ctx.io.write_compressed(tmp_path / path, row)
        aggregate["records"][key] = path
    result = refcheck.check(view, tmp_path, aggregate)
    assert result["status"] == "pass"
    assert result["reference_solves"] == 6
    assert not result["coupled_trajectory_qualified"]


@pytest.mark.parametrize("fault", ["gate", "initial", "axes", "clock", "dense", "setting"])
def test_reference_metadata_and_initial_state_corruption_is_rejected(short_references, fault):
    view, records = short_references["b"]
    row = copy.deepcopy(records["active_channel/dop853_tight"])
    if fault == "gate":
        row["initial_gate"] = [0.2, 0.6]
    elif fault == "initial":
        row["accepted_states"][0][2] = 0.2
    elif fault == "axes":
        row["state_axes"]["cell_count"] = 7
    elif fault == "clock":
        row["sample_times_s"][-1] = 0.003
    elif fault == "dense":
        row["dense_intervals"][0]["left_s"] = 0.01
    else:
        row["setting"]["rtol"] *= 2
    setting = next(s for s in view["protocol"]["reference"]["solves"] if s["id"] == "dop853_tight")
    with pytest.raises(ValueError):
        refcheck.validate_record(
            row, view["reference_parameters"]["active_channel"], setting, view["protocol"]
        )


def synthetic_signal(protocol):
    result = {}
    for name in ("a", "b"):
        variants = {}
        for variant in protocol["variants"]:
            first = {
                "gate": [[0.2], [0.6]] if name == "a" else [[0.6], [0.2]],
                "voltage_V": [0.0],
                "flux_fmol_per_s": [0.0],
            }
            last = {
                "gate": [[0.3], [0.6]] if name == "a" else [[0.6], [0.3]],
                "voltage_V": [-0.001 if name == "a" and variant == "active_channel" else 0.0],
                "flux_fmol_per_s": [0.0],
            }
            if name == "b":
                last["gate"] = [[0.6], [0.2]]
            variants[variant] = {
                "times_s": [0.0, protocol["candidate_duration_s"]],
                "readouts": [first, last],
            }
        result[name] = {
            "status": "pass",
            "reference_convergence_checked": True,
            "reference_solutions": variants,
        }
    return result


@pytest.mark.parametrize("fault", [None, "weak", "failed", "clock", "confound", "blocked"])
def test_reference_signal_gate_does_not_use_initial_derivative_as_horizon_proof(protocol, fault):
    references = synthetic_signal(protocol)
    if fault == "weak":
        references["a"]["reference_solutions"]["active_channel"]["readouts"][-1]["voltage_V"] = [
            0.0
        ]
    elif fault == "failed":
        references["b"]["status"] = "fail"
    elif fault == "clock":
        references["b"]["reference_solutions"]["active_channel"]["times_s"][-1] = 0.003
    elif fault == "confound":
        references["b"]["reference_solutions"]["active_channel"]["readouts"][0]["voltage_V"] = [
            0.001
        ]
    elif fault == "blocked":
        references["a"]["reference_solutions"]["blocked_channel"]["readouts"][-1]["voltage_V"] = [
            0.001
        ]
    if fault is None:
        assert compare.reference_signal(protocol, references)["active_channel"][
            "voltage_contrast_V"
        ] == [-0.001]
    else:
        with pytest.raises(ValueError):
            compare.reference_signal(protocol, references)


@pytest.mark.parametrize("failure", [None, "reference", "check", "release", "verify", "betse"])
def test_gated_sequence_never_runs_models_after_rejected_reference(failure):
    seen = []

    def action(name, value=None):
        seen.append(name)
        if name == failure:
            raise ValueError(name)
        return name if value is None else value

    def call():
        return job.gated_sequence(
            lambda name: action(name),
            lambda row: action("check"),
            lambda: action("release"),
            lambda: action("verify"),
        )

    if failure is None:
        assert call() == ("check", "betse", "cells")
        assert seen == ["reference", "check", "release", "verify", "betse", "verify", "cells"]
    else:
        with pytest.raises(ValueError):
            call()
        assert "cells" not in seen
        if failure != "betse":
            assert "betse" not in seen


def test_normative_native_fixture_view_changes_only_declared_gates(views):
    original = ctx.c.read(ctx.feedback.audit.preparation.audit.CAPTURE / "betse.json")
    before = copy.deepcopy(original)
    variant = next(
        v
        for v in views["b"]["preparation_registration"]["transport_protocol"]["variants"]
        if v["id"] == "active_channel"
    )
    expected = nativecheck.fixture_reference(original, variant, [0.6, 0.2])
    row = expected["rows"]["active_channel/prescribed_mh_a"]["channel_before"]
    assert row["m"] == [0.6] * 30 and row["h"] == [0.2] * 30
    assert row["derived_m_times_h"] == [0.12] * 30
    assert original == before


@pytest.mark.parametrize("name", ["a", "b"])
@pytest.mark.parametrize("backend", ["jax_eager", "jax_jit"])
def test_short_real_production_run_checks_full_state_and_checkpoint(views, tmp_path, name, backend):
    import feedback_cells

    from cells.core.runner import run
    from cells.core.specs import parse_spec
    from cells.io import load_snapshot, write_snapshot

    view = copy.deepcopy(views[name])
    dt = 0.00005
    key = ctx.feedback.key("active_channel", dt, backend)
    definition = view["cells_definitions"][key]
    definition["experiment"].update({"end_time": 2 * dt, "observation_times": [0.0, dt, 2 * dt]})
    view["protocol"].update({"duration_s": 2 * dt, "common_times_s": [0.0, dt, 2 * dt]})
    view["cells_definitions"] = {key: definition}
    result = run(parse_spec(definition))
    record = feedback_cells.record_result(result, key, definition)
    ledger = ctx.io.Ledger(cellscheck.cells_tolerances(view))
    points = cellscheck.cells_points_and_checks(view, record, ledger)
    assert ledger.failed == 0
    assert points[0]["gate"] == [[g] * 7 for g in view["protocol"]["initial_gate"]]
    directory = tmp_path / "cells" / key
    directory.mkdir(parents=True)
    ctx.io.write_compressed(directory / "result.json.gz", record)
    write_snapshot(directory / "final-checkpoint", result.spec, result.final)
    source_hashes = ctx.c.read(directory / "final-checkpoint/manifest.json")["source_hashes"]
    aggregate = {
        "records": {key: str((directory / "result.json.gz").relative_to(tmp_path))},
        "resumed": {},
    }
    assert compare.checkpoints(view, tmp_path, aggregate, source_hashes) == {
        "checkpoints": 1,
        "checkpoint_arrays": 54,
    }
    write_snapshot(directory / "test-midpoint", result.spec, result.checkpoint_at(dt))
    restored = load_snapshot(directory / "test-midpoint")
    resumed = run(restored.spec, restored.checkpoint)
    resumed_record = feedback_cells.record_result(resumed, key, definition)
    replay = cellscheck.compare_histories(
        key,
        record,
        resumed_record,
        view["protocol"]["restart_absolute"],
        2e-11,
        directory / "test-restart-failures.jsonl",
        1,
    )
    assert replay["failed_comparisons"] == 0
    if name == "b":
        altered = copy.deepcopy(record)
        gates = np.asarray(altered["history"]["gate"]["values"])
        gates[0, 0, :7], gates[0, 1, :7] = 0.2, 0.6
        altered["history"]["gate"] = ctx.feedback.audit.preparation.array_record(gates)
        with pytest.raises(ValueError, match="initial"):
            cellscheck.cells_points_and_checks(
                view, altered, ctx.io.Ledger(cellscheck.cells_tolerances(view))
            )


@pytest.mark.parametrize("left,right", [([1.0], [1.0, 2.0]), ([1.0], 0.0), ([math.nan], [0.0])])
def test_contrast_rejects_mismatched_axes_and_nonfinite_values(left, right):
    with pytest.raises(ValueError):
        compare.difference(left, right)


def test_contrast_preserves_sign_and_nested_gate_axes():
    assert compare.difference([[0.2, 0.4], [0.6, 0.3]], [[0.6, 0.4], [0.2, 0.3]]) == [
        [-0.39999999999999997, 0.0],
        [0.39999999999999997, 0.0],
    ]


def test_existing_directory_cannot_be_reused_for_capture(tmp_path):
    with pytest.raises(ValueError, match="fresh"):
        job.register(tmp_path, tmp_path / "unused.xml")


def test_every_paired_definition_differs_only_in_initial_gates(views):
    strip = ctx.review.assembly.without_gates
    assert set(views["a"]["cells_definitions"]) == set(views["b"]["cells_definitions"])
    for key, first in views["a"]["cells_definitions"].items():
        assert strip(first) == strip(views["b"]["cells_definitions"][key])


@pytest.mark.parametrize("fault", [None, "record", "missing", "decision", "registration"])
def test_reference_gate_binds_every_solve_before_simulators(protocol, views, tmp_path, fault):
    r = {"protocol": protocol, "views": views}
    ctx.io.write(tmp_path / "registration.json", {"software_fixture": True})
    ctx.io.write(tmp_path / "reference.json", {"software_fixture": True})
    gate = {
        "status": "pass",
        "simulators_allowed": True,
        "selected_duration_s": protocol["candidate_duration_s"],
        "reference_solves": 12,
    }
    ctx.io.write(tmp_path / "reference-gate.json", gate)
    for name, view in views.items():
        (tmp_path / name).mkdir()
        ctx.io.write_compressed(tmp_path / name / "reference-gate.json.gz", {"fixture": True})
        for variant in protocol["variants"]:
            for setting in view["protocol"]["reference"]["solves"]:
                path = tmp_path / name / "reference" / variant / setting["id"]
                path.mkdir(parents=True)
                ctx.io.write_compressed(path / "result.json.gz", {"fixture": True})
    job.allow_simulators(tmp_path, r)
    if fault == "record":
        path = tmp_path / "b/reference/active_channel/dop853_tight/result.json.gz"
        with path.open("ab") as stream:
            stream.write(b"changed")
    elif fault == "missing":
        (tmp_path / "b/reference/active_channel/dop853_tight/result.json.gz").unlink()
    elif fault == "decision":
        (tmp_path / "reference-gate.json").write_text('{"status":"fail"}')
    elif fault == "registration":
        (tmp_path / "registration.json").write_text('{"changed":true}')
    if fault is None:
        job.require_gate(tmp_path, r)
    else:
        with pytest.raises((ValueError, OSError)):
            job.require_gate(tmp_path, r)


@pytest.mark.parametrize("fault", ["readout", "polynomial"])
def test_numerical_reference_corruption_rejects_gate(short_references, tmp_path, fault):
    view, original = short_references["b"]
    records = copy.deepcopy(original)
    row = records["active_channel/dop853_tight"]
    if fault == "readout":
        row["readouts"][-1]["gate"][0][0] += 0.01
    else:
        row["dense_intervals"][0]["coefficients"][0][0] += 0.01
    aggregate = {"records": {}, "reference_solves": len(records)}
    for i, (key, record) in enumerate(records.items()):
        ctx.io.write_compressed(tmp_path / f"ref-{i}.gz", record)
        aggregate["records"][key] = f"ref-{i}.gz"
    result = refcheck.check(view, tmp_path, aggregate)
    assert result["status"] == "fail"
