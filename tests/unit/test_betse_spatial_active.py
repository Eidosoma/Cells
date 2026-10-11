"""Native active tissue agreement, independent accounting and CPU/L4 replay."""

import copy
import json
import os
import subprocess
from pathlib import Path

import jax
import numpy as np
import pytest

from cells.numerics import betse_active as model
from cells.processes import kinetic_pump
from tests.unit import test_betse_spatial_trajectory as short
from tests.unit.test_betse_tissue_contact import load_capture
from validation.betse.spatial_active import fixtures, reference

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_PATH = ROOT / "validation/betse/spatial_active/protocol.json"
PROTOCOL = json.loads(PROTOCOL_PATH.read_text())
TOL = PROTOCOL["tolerances"]
CASES = [(case["id"], index) for case in PROTOCOL["cases"] for index in (0, 1)]
RUN = jax.jit(model.trajectory, static_argnums=(3,))
MAPPED = jax.jit(model.trajectories, static_argnums=(3,))


@pytest.fixture(scope="module")
def device():
    jax.config.update("jax_enable_x64", True)
    return jax.devices(short.BACKEND)[0]


@pytest.fixture(scope="module")
def captured(tmp_path_factory):
    binding = PROTOCOL["prior_binding"]
    prior = Path(binding["root"])
    assert short.fixtures.digest(prior / "completion.json") == binding["completion_sha256"]
    done = json.loads((prior / "completion.json").read_text())
    assert done["status"] == "completed"
    assert short.fixtures.digest(prior / "result.json") == done["result_sha256"]
    if short.BACKEND == "gpu":
        assert short.EVIDENCE
        path = Path(short.EVIDENCE) / "cpu/active-native"
    else:
        root = (
            Path(short.EVIDENCE) / "cpu"
            if short.EVIDENCE
            else tmp_path_factory.mktemp("active-native")
        )
        root.mkdir(parents=True, exist_ok=True)
        path = root / "active-native"
        with (
            (root / "active-native.stdout.log").open("x") as out,
            (root / "active-native.stderr.log").open("x") as err,
        ):
            subprocess.run(
                [
                    "/mnt/workspaces/Cells/venv-betse/bin/python",
                    "-B",
                    str(ROOT / "validation/betse/spatial_active/native.py"),
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
                    os.environ, MPLBACKEND="Agg", MPLCONFIGDIR=str(root / "matplotlib-active")
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
        assert trace is not None
        assert row["steps"] == round(PROTOCOL["duration_s"] / row["dt_s"])
    return rows


@pytest.fixture(scope="module")
def computed(captured, device):
    results = {}
    for case, index in CASES:
        row, trace = captured[f"{case}/step-{index}/observed"]
        state, layout = fixtures.prepare(row, trace, PROTOCOL)
        final, (states, rates, accepted), valid = short.selected(
            RUN, (state, layout, np.asarray(row["dt_s"])), device, row["steps"]
        )
        assert valid and accepted.all()
        fields = short.selected(short.FIELDS, (states.tissue, layout.tissue), device)
        observed = short.observed_history(states.tissue, rates.ordinary, fields, layout.tissue)
        results[(case, index)] = dict(
            row=row,
            trace=trace,
            initial=state,
            layout=layout,
            final=final,
            states=states,
            rates=rates,
            observed=observed,
        )
    return results


def compare(value):
    return reference.compare(
        value["row"],
        value["trace"],
        TOL,
        value["states"].tissue._asdict(),
        {k: v for k, v in value["states"]._asdict().items() if k != "tissue"},
        {k: v for k, v in value["rates"]._asdict().items() if k != "ordinary"},
        value["observed"],
    )


def test_protocol_retains_physical_tolerances_and_scope():
    assert model.MODEL_ID == "betse_spatial_nak_kv1p5@1"
    assert PROTOCOL["automatic_followup"] is False and len(CASES) == 12
    assert PROTOCOL["duration_s"] == 64e-6 and PROTOCOL["native_steps_s"] == [1e-6, 5e-7]
    for key, value in short.TOL.items():
        assert TOL[key] == value
    assert PROTOCOL["expected_cpu_skips"] == 2
    assert PROTOCOL["initial_gate"] == [0.2, 0.6]


@pytest.mark.parametrize("case,index", CASES)
def test_complete_active_native_trajectory(case, index, computed):
    value = computed[(case, index)]
    native = reference.native_check(value["row"], value["trace"], PROTOCOL)
    report = compare(value)
    report.update(
        backend=short.BACKEND,
        observer_neutrality="bitwise",
        native_update_max_errors=native["max_errors"],
        independent_native_pump_error_fmol_s=native["max_pump_error_fmol_s"],
    )
    short.evidence(
        f"active-native-trajectory-{case}-{index}",
        report,
        fixtures.arrays(value["states"], value["rates"], value["observed"]),
    )


@pytest.fixture(scope="module")
def example():
    rows, protocol = short.fixtures.capture()
    row, trace = rows["combined/step-0/observed"]
    tissue, layout = short.fixtures.prepare(row, trace, protocol)
    pump = PROTOCOL["pump_parameters"]
    ones = np.ones_like(layout.membrane_area)
    active_layout = model.validate_layout(
        model.Layout(
            layout,
            kinetic_pump.Parameters(
                layout.membrane_area * 1e8,
                *(
                    ones * pump[key]
                    for key in ("cATP", "cADP", "cPi", "KmNK_Na", "KmNK_K", "KmNK_ATP", "deltaGATP")
                ),
            ),
            np.asarray(row["species"]["Na"]),
            np.asarray(row["species"]["K"]),
            ones,
            ones * 2e-8,
        )
    )
    return model.initial_state(tissue, active_layout, ones * 0.2, ones * 0.6), active_layout


@pytest.mark.parametrize(
    "fault",
    ["same_role", "immobile_role", "availability", "pool", "permeability", "shape", "temperature"],
)
def test_invalid_active_layouts(example, fault):
    _, p = example
    if fault == "same_role":
        p = p._replace(sodium_index=p.potassium_index)
    elif fault == "immobile_role":
        p = p._replace(potassium_index=np.asarray(np.flatnonzero(~p.tissue.moving)[0]))
    elif fault == "availability":
        p = p._replace(pump_available=p.pump_available * 1.1)
    elif fault == "pool":
        p = p._replace(pump=p.pump._replace(atp_mM=p.pump.atp_mM * 0))
    elif fault == "permeability":
        p = p._replace(channel_permeability=-p.channel_permeability)
    elif fault == "shape":
        p = p._replace(channel_permeability=p.channel_permeability[:1])
    else:
        p = p._replace(tissue=p.tissue._replace(temperature=np.asarray(310.15)))
    with pytest.raises(ValueError):
        model.validate_layout(p)


@pytest.mark.parametrize(
    "fault", ["gate", "nan_gate", "cell", "outside", "zero_dt", "negative_dt", "large_dt"]
)
def test_invalid_active_trials_retain_full_state(example, fault):
    state, p = example
    dt = 1e-6
    if fault == "gate":
        state = state._replace(m_gate=np.full_like(state.m_gate, 1.1))
    elif fault == "nan_gate":
        state = state._replace(h_gate=np.full_like(state.h_gate, np.nan))
    elif fault == "cell":
        state = state._replace(
            tissue=state.tissue._replace(cell_concentration=-state.tissue.cell_concentration)
        )
    elif fault == "outside":
        state = state._replace(
            tissue=state.tissue._replace(
                outside_concentration=state.tissue.outside_concentration * 0
            )
        )
    elif fault == "zero_dt":
        dt = 0.0
    elif fault == "negative_dt":
        dt = -1e-6
    else:
        dt = 1e4
    with np.errstate(all="ignore"):
        result, _, valid = model.step(state, p, dt, xp=np)
    assert not valid
    short.bits(result, state)


def test_active_controls_and_passive_reduction(computed, device):
    changes = {}
    for index in (0, 1):
        off, blocked = computed[("off", index)], computed[("blocked", index)]
        short.bits(off["final"], blocked["final"])
        p, dt = off["layout"].tissue, np.asarray(off["row"]["dt_s"])
        reference_state, _, valid = short.selected(
            short.RUN, (off["initial"].tissue, p, dt), device, off["row"]["steps"]
        )
        assert valid
        short.bits(off["final"].tissue, reference_state)
        for name in ("pump", "channel", "coupled", "partial"):
            value = computed[(name, index)]
            delta = float(np.max(abs(value["observed"]["vm"] - off["observed"]["vm"])))
            assert delta > 100 * TOL["voltage_atol_V"]
            changes[f"{name}-{index}"] = delta
        value = computed[("coupled", index)]
        assert np.max(abs(value["final"].m_gate - value["initial"].m_gate)) > 1e-4
        assert np.max(abs(value["final"].h_gate - value["initial"].h_gate)) > 1e-6
        assert np.max(abs(value["final"].pump_cycles_fmol)) > 100 * TOL["material_atol_fmol"]
        assert np.max(abs(value["final"].channel_inward_fmol)) > 100 * TOL["material_atol_fmol"]
        partial = computed[("partial", index)]
        blocked_patches = partial["layout"].pump_available == 0
        assert np.all(partial["states"].pump_cycles_fmol[:, blocked_patches] == 0)
    short.evidence(
        "active-native-controls",
        dict(
            status="passed",
            disabled_reduces_to_passive="bitwise",
            blocked_matches_off="bitwise",
            nontrivial_gate_evolution=True,
            max_voltage_change_from_off_V=changes,
        ),
    )


def test_active_disk_windows_world_partitions(computed, device, tmp_path):
    value = computed[("coupled", 1)]
    state, p, dt = value["initial"], value["layout"], np.asarray(value["row"]["dt_s"])
    assert value["row"]["steps"] == 128
    for i, length in enumerate((31, 53, 44)):
        state, (_, rates, _), valid = short.selected(RUN, (state, p, dt), device, length)
        assert valid
        path = tmp_path / f"active-restart-{i}.npz"
        np.savez_compressed(path, **fixtures.arrays(state, rates, {}))
        with np.load(path, allow_pickle=False) as saved:
            state = fixtures.restore(saved)
    short.bits(state, value["final"])
    values = [computed[(case, 0)] for case in ("coupled", "pump", "channel")]
    states = jax.tree.map(lambda *x: np.stack(x), *(v["initial"] for v in values))
    layouts = jax.tree.map(lambda *x: np.stack(x), *(v["layout"] for v in values))
    dt = np.asarray(values[0]["row"]["dt_s"])
    together, _, valid = short.selected(MAPPED, (states, layouts, dt), device, 64)
    assert valid.all()
    for i, value in enumerate(values):
        short.bits(jax.tree.map(lambda x, i=i: x[i], together), value["final"])
    order = np.asarray([2, 0, 1])
    reordered, _, valid = short.selected(
        MAPPED, (*jax.tree.map(lambda x: x[order], (states, layouts)), dt), device, 64
    )
    assert valid.all()
    short.bits(reordered, jax.tree.map(lambda x: x[order], together))
    for i in range(3):
        alone, _, valid = short.selected(
            MAPPED, (*jax.tree.map(lambda x, i=i: x[i : i + 1], (states, layouts)), dt), device, 64
        )
        assert valid.all()
        short.bits(alone, jax.tree.map(lambda x, i=i: x[i : i + 1], together))
    bad = value["initial"]._replace(m_gate=np.full_like(value["initial"].m_gate, 1.1))
    final, (history, _, accepted), valid = short.selected(
        RUN, (bad, value["layout"], dt), device, 3
    )
    assert not valid and not accepted.any()
    short.bits(final, bad)
    short.bits(history, jax.tree.map(lambda x: np.stack([x] * 3), bad))
    short.evidence(
        "active-native-replay",
        dict(
            status="passed",
            comparison="bitwise",
            state_arrays=len(jax.tree.leaves(state)),
            disk=True,
            windows=[31, 53, 44],
            mapped_worlds=3,
            reordered=True,
            partitions=True,
            failure_latched=True,
        ),
    )


@pytest.mark.parametrize(
    "fault",
    [
        "gate",
        "pump_rate",
        "channel_rate",
        "pump_ledger",
        "channel_ledger",
        "ordinary_ledger",
        "missing_channel",
        "double_channel",
    ],
)
def test_corrupted_active_evidence_is_rejected(computed, fault):
    value = copy.deepcopy(computed[("coupled", 0)])
    if fault == "gate":
        value["states"].m_gate[-1, 0] += 1e-4
    elif fault == "pump_rate":
        value["rates"].pump_cycles_fmol_s[-1, 0] += 1e-5
    elif fault == "channel_rate":
        value["rates"].channel_inward_fmol_s[-1, 0] += 1e-5
    elif fault == "pump_ledger":
        value["states"].pump_cycles_fmol[-1, 0] += 1e-6
    elif fault == "channel_ledger":
        value["states"].channel_inward_fmol[-1, 0] += 1e-6
    elif fault == "ordinary_ledger":
        value["states"].tissue.membrane_inward_fmol[-1, 0, 0] += 1e-6
    else:
        value["states"].channel_inward_fmol[:] *= 0 if fault == "missing_channel" else 2
    with pytest.raises(AssertionError):
        compare(value)


def test_native_wrong_channel_sampling_and_damaged_gates_rejected(computed):
    value = computed[("coupled", 0)]
    row, trace = value["row"], value["trace"]
    (index,) = np.flatnonzero((trace["method"] == 4) & ~trace["after"] & (trace["step"] == 0))
    names = (
        "cc_cells",
        "cc_at_mem",
        "cc_env",
        "vm",
        "fluxes_mem",
        "m_gate",
        "h_gate",
        "channel_flux",
    )
    before, after = ({name: trace[name][i].copy() for name in names} for i in (index, index + 1))

    def near(name, a, b, atol, rtol=0):
        np.testing.assert_allclose(a, b, atol=atol, rtol=rtol, err_msg=name)

    reference.channel_update(row, before, after, near)
    wrong = copy.deepcopy(before)
    wrong["cc_env"] = trace["initial_cc_env"].copy()
    with pytest.raises(AssertionError):
        reference.channel_update(row, wrong, after, near)
    after["h_gate"][0] += 1e-4
    with pytest.raises(AssertionError):
        reference.channel_update(row, before, after, near)
    short.evidence(
        "active-native-negative-controls",
        dict(
            status="passed",
            wrong_pre_diffusion_channel_input="rejected",
            damaged_native_gate="rejected",
            saved_corruption_tests=8,
        ),
    )


def compare_cpu_gpu_arrays(actual, saved, area, tol=TOL):
    ordinary = {k: v for k, v in actual.items() if not k.startswith("active__")}
    count = short.compare_cpu_gpu_arrays(ordinary, {k: saved[k] for k in ordinary}, area, tol)
    assert set(actual) == set(saved)
    for name, values in actual.items():
        if not name.startswith("active__"):
            continue
        expected = saved[name]
        assert values.shape == expected.shape and values.dtype == expected.dtype
        assert np.isfinite(values).all() and np.isfinite(expected).all()
        atol = (
            tol["gate_atol"]
            if name.endswith("gate")
            else tol["flux_atol_fmol_s"]
            if name.endswith("fmol_s")
            else tol["material_atol_fmol"]
        )
        rtol = tol["gate_rtol"] if name.endswith("gate") else tol["cpu_gpu_rtol"]
        np.testing.assert_allclose(values, expected, atol=atol, rtol=rtol, err_msg=name)
        count += values.size
    return count


def test_active_cpu_gpu(computed):
    if short.BACKEND == "cpu":
        pytest.skip("Requires following L4 phase and saved CPU trajectories")
    assert short.EVIDENCE
    count = 0
    for (case, index), value in computed.items():
        actual = fixtures.arrays(value["states"], value["rates"], value["observed"])
        path = Path(short.EVIDENCE) / "cpu" / f"active-native-trajectory-{case}-{index}.npz"
        with np.load(path, allow_pickle=False) as saved:
            count += compare_cpu_gpu_arrays(actual, saved, value["layout"].tissue.membrane_area)
    short.evidence("active-native-cpu-gpu", dict(status="passed", compared_scalars=count))
