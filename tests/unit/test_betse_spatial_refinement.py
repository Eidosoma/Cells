"""Extended native trajectories, resolved temporal refinement and complete replay."""

import json
import os
import subprocess
from pathlib import Path

import jax
import numpy as np
import pytest

from tests.unit import test_betse_spatial_trajectory as short
from tests.unit.test_betse_tissue_contact import load_capture
from validation.betse.spatial_trajectory import fixtures, reference, refinement
from validation.betse.tissue_contact import reference as native_reference

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_PATH = ROOT / "validation/betse/spatial_trajectory/refinement_protocol.json"
PROTOCOL = json.loads(PROTOCOL_PATH.read_text())
TOL = PROTOCOL["tolerances"]
CASES = [(case["id"], index) for case in PROTOCOL["cases"] for index in range(3)]
model = short.model


@pytest.fixture(scope="module")
def device():
    jax.config.update("jax_enable_x64", True)
    return jax.devices(short.BACKEND)[0]


@pytest.fixture(scope="module")
def captured(tmp_path_factory):
    binding = PROTOCOL["prior_binding"]
    prior = Path(binding["root"])
    assert fixtures.digest(prior / "completion.json") == binding["completion_sha256"]
    completion = json.loads((prior / "completion.json").read_text())
    assert completion["status"] == "completed"
    assert fixtures.digest(prior / "result.json") == completion["result_sha256"]
    if short.BACKEND == "gpu":
        assert short.EVIDENCE
        path = Path(short.EVIDENCE) / "cpu/extended-native"
    else:
        root = (
            Path(short.EVIDENCE) / "cpu"
            if short.EVIDENCE
            else tmp_path_factory.mktemp("extended-native")
        )
        root.mkdir(parents=True, exist_ok=True)
        path = root / "extended-native"
        with (
            (root / "extended-native.stdout.log").open("x") as out,
            (root / "extended-native.stderr.log").open("x") as err,
        ):
            subprocess.run(
                [
                    "/mnt/workspaces/Cells/venv-betse/bin/python",
                    "-B",
                    str(ROOT / "validation/betse/tissue_contact/native.py"),
                    "--output",
                    str(path),
                    "--protocol",
                    str(PROTOCOL_PATH),
                ],
                check=True,
                timeout=PROTOCOL["resources"]["native_timeout_seconds"],
                stdout=out,
                stderr=err,
                env=dict(
                    os.environ, MPLBACKEND="Agg", MPLCONFIGDIR=str(root / "matplotlib-extended")
                ),
            )
    rows = load_capture(path, PROTOCOL)
    for case, index in CASES:
        row, trace = rows[f"{case}/step-{index}/observed"]
        other, _ = rows[f"{case}/step-{index}/bare"]
        for key in (
            "case",
            "dt_s",
            "steps",
            "fixture",
            "geometry",
            "parameters",
            "arrays",
            "species",
            "final",
        ):
            assert row[key] == other[key], key
        assert row["steps"] == round(PROTOCOL["duration_s"] / row["dt_s"])
        assert trace is not None
    return rows


@pytest.fixture(scope="module")
def computed(captured, device):
    values = {}
    for case, index in CASES:
        row, trace = captured[f"{case}/step-{index}/observed"]
        initial, layout = fixtures.prepare(row, trace, PROTOCOL)
        final, (states, rates, accepted), valid = short.selected(
            short.RUN, (initial, layout, np.asarray(row["dt_s"])), device, row["steps"]
        )
        assert valid and accepted.all()
        fields = short.selected(short.FIELDS, (states, layout), device)
        observed = short.observed_history(states, rates, fields, layout)
        values[(case, index)] = dict(
            row=row,
            trace=trace,
            initial=initial,
            layout=layout,
            final=final,
            states=states,
            rates=rates,
            observed=observed,
        )
    return values


def test_extended_protocol_retains_physical_tolerances():
    assert PROTOCOL["duration_s"] == 256e-6
    assert PROTOCOL["native_steps_s"] == [1e-6, 5e-7, 2.5e-7]
    assert len(CASES) == 12 and PROTOCOL["expected_cpu_skips"] == 2
    assert PROTOCOL["automatic_followup"] is False
    for key, value in short.TOL.items():
        assert TOL[key] == value, key
    assert TOL["material_roundoff_ops_per_step"] == 32
    longest = round(PROTOCOL["duration_s"] / min(PROTOCOL["native_steps_s"]))
    clock_bound = np.finfo(float).eps * longest * PROTOCOL["duration_s"]
    assert clock_bound <= TOL["clock_atol_s"] < 2 * clock_bound


@pytest.mark.parametrize("case,index", CASES)
def test_extended_native_trajectory(case, index, computed):
    value = computed[(case, index)]
    native = native_reference.check(
        value["row"],
        value["trace"],
        PROTOCOL | {"tolerances": PROTOCOL["native_update_tolerances"]},
    )
    report = reference.compare(
        value["row"], value["trace"], TOL, value["states"]._asdict(), value["observed"]
    )
    report.update(
        backend=short.BACKEND,
        observer_neutrality="bitwise",
        native_update_max_errors=native["max_errors"],
    )
    short.evidence(
        f"extended-native-trajectory-{case}-{index}",
        report,
        short.saved_arrays(value["states"], value["observed"]),
    )


def test_original_native_prefix_is_unchanged(captured):
    original, _ = fixtures.capture()
    count = 0
    for case in (c["id"] for c in PROTOCOL["cases"]):
        for index in (0, 1):
            _, old = original[f"{case}/step-{index}/observed"]
            _, new = captured[f"{case}/step-{index}/observed"]
            assert set(old) == set(new)
            for key, value in old.items():
                if key == "raw_label_s":
                    # Linspace labels depend on duration, unlike completed-step time.
                    continue
                actual = new[key] if key.startswith("initial_") else new[key][: len(value)]
                short.bits(actual, value)
                count += value.size
    short.evidence(
        "extended-native-prefix",
        dict(
            status="passed", compared_scalars=count, comparison="bitwise", completed_duration_s=8e-6
        ),
    )


@pytest.mark.parametrize("case", [case["id"] for case in PROTOCOL["cases"]])
def test_native_and_cells_temporal_refinement(case, computed):
    values = [computed[(case, index)] for index in range(3)]
    for value in values[1:]:
        short.bits(value["initial"], values[0]["initial"])
        short.bits(value["layout"], values[0]["layout"])
    if case == "uniform":
        for value in values:
            for key in ("cell_concentration", "membrane_concentration", "outside_concentration"):
                short.bits(getattr(value["final"], key), getattr(value["initial"], key))
    series = [dict(states=v["states"]._asdict(), observed=v["observed"]) for v in values]
    native = [refinement.native_series(v["row"], v["trace"]) for v in values]
    area = values[0]["layout"].membrane_area
    report = refinement.check(case, series, area, PROTOCOL)
    report["native"] = refinement.check(case, native, area, PROTOCOL)
    report["backend"] = short.BACKEND
    short.evidence("extended-native-refinement-" + case, report)


def test_extended_disk_windows_and_world_partitions(computed, device, tmp_path):
    value = computed[("combined", 2)]
    state, layout, dt = value["initial"], value["layout"], np.asarray(value["row"]["dt_s"])
    assert value["row"]["steps"] == 1024
    for index, steps in enumerate((257, 389, 378)):
        state, _, valid = short.selected(short.RUN, (state, layout, dt), device, steps)
        assert valid
        path = tmp_path / f"restart-{index}.npz"
        np.savez_compressed(path, **state._asdict())
        with np.load(path, allow_pickle=False) as saved:
            state = model.State(*(saved[k] for k in model.State._fields))
    short.bits(state, value["final"])
    values = [computed[(case, 0)] for case in ("combined", "diffusion", "junction")]
    states = jax.tree.map(lambda *v: np.stack(v), *(v["initial"] for v in values))
    layouts = jax.tree.map(lambda *v: np.stack(v), *(v["layout"] for v in values))
    dt = np.asarray(values[0]["row"]["dt_s"])
    together, _, valid = short.selected(short.MAPPED, (states, layouts, dt), device, 256)
    assert valid.all()
    for index, value in enumerate(values):
        short.bits(jax.tree.map(lambda x, i=index: x[i], together), value["final"])
    order = np.array([2, 0, 1])
    reordered, _, valid = short.selected(
        short.MAPPED, (*jax.tree.map(lambda x: x[order], (states, layouts)), dt), device, 256
    )
    assert valid.all()
    short.bits(reordered, jax.tree.map(lambda x: x[order], together))
    for index in range(3):
        alone, _, valid = short.selected(
            short.MAPPED,
            (*jax.tree.map(lambda x, i=index: x[i : i + 1], (states, layouts)), dt),
            device,
            256,
        )
        assert valid.all()
        short.bits(alone, jax.tree.map(lambda x, i=index: x[i : i + 1], together))
    short.evidence(
        "extended-native-replay",
        dict(
            status="passed",
            comparison="bitwise",
            state_fields=list(model.State._fields),
            disk=True,
            windows=[257, 389, 378],
            mapped_worlds=3,
            reordered=True,
            partitions=True,
            completed_duration_s=256e-6,
        ),
    )


def test_roundoff_allowance_does_not_hide_missing_material(computed):
    value = computed[("combined", 2)]
    reports = {}
    for name in ("reservoir_reset_fmol", "stencil_exchange_fmol"):
        states = dict(value["states"]._asdict())
        changed = states[name].copy()
        changed[-1, 0, 0] += 1e-6
        states[name] = changed
        with pytest.raises(AssertionError):
            reference.compare(value["row"], value["trace"], TOL, states, value["observed"])
        reports[name] = "rejected"
    short.evidence(
        "extended-native-roundoff-controls",
        dict(status="passed", corrupted_fmol=1e-6, controls=reports),
    )


def test_refinement_accepts_resolved_first_order_and_marks_unresolved():
    rule = PROTOCOL["refinement"]
    result = refinement.differences(
        np.array([1.04, 2.04]), np.array([1.02, 2.02]), np.array([1.01, 2.01]), 1e-6, 0, rule
    )
    assert result["first_order_resolved"]
    assert result["ratio"] == pytest.approx(2)
    result = refinement.differences(
        np.array([1.0]), np.array([1.0]), np.array([1.0]), 1e-6, 0, rule
    )
    assert not result["first_order_resolved"] and result["ratio"] is None


@pytest.mark.parametrize("fault", ["worse", "wrong_order", "nonfinite", "shape"])
def test_refinement_rejects_false_claims(fault):
    values = [np.array([1.04]), np.array([1.02]), np.array([1.01])]
    if fault == "worse":
        values[2] = np.array([1.1])
    elif fault == "wrong_order":
        values[2] = np.array([1.005])
    elif fault == "nonfinite":
        values[2] = np.array([np.nan])
    else:
        values[2] = np.array([[1.01]])
    with pytest.raises(AssertionError):
        refinement.differences(*values, 1e-6, 0, PROTOCOL["refinement"])


def test_extended_cpu_gpu(computed):
    if short.BACKEND == "cpu":
        pytest.skip("Requires following L4 phase and saved extended CPU trajectories")
    assert short.EVIDENCE
    count = 0
    for (case, index), value in computed.items():
        path = Path(short.EVIDENCE) / "cpu" / f"extended-native-trajectory-{case}-{index}.npz"
        with np.load(path, allow_pickle=False) as saved:
            count += short.compare_cpu_gpu_arrays(
                short.saved_arrays(value["states"], value["observed"]),
                saved,
                value["layout"].membrane_area,
                TOL,
            )
    short.evidence("extended-native-cpu-gpu", dict(status="passed", compared_scalars=count))
