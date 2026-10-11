"""Prescribed native interventions and ordinary CPU/L4 event/restart execution."""

import copy
import json
import os
import subprocess
from dataclasses import replace
from pathlib import Path

import jax
import numpy as np
import pytest

from cells.batch_io import load_batch_snapshot, write_batch_snapshot
from cells.core.batch import BatchSpec, WorldSpec, run_batch
from cells.core.batch_windows import iter_batch_windows
from cells.core.betse_spatial_spec import Control, definition_arrays
from cells.core.errors import NumericalError
from cells.core.runner import branch_checkpoint, run, timeline, validate_checkpoint
from cells.core.schedule import control_values, event_index
from cells.core.specs import ConfigError, parse_spec
from cells.core.windows import WindowPolicy, iter_windows
from cells.io import load_snapshot, write_snapshot
from cells.models import betse_spatial as model
from cells.numerics import betse_active as active
from cells.numerics import betse_spatial as passive
from tests.unit import test_betse_spatial_runtime as previous
from tests.unit.test_betse_tissue_contact import load_capture
from tests.unit.test_windows import assert_windows
from validation.betse.spatial_active import (
    fixtures,
    interventions,
    reference,
)
from validation.betse.spatial_active import (
    intervention_reference as independent,
)

common, short = previous.common, previous.short
BACKEND, EVIDENCE = common.BACKEND, common.EVIDENCE
PROTOCOL = interventions.protocol()
CASES = [(c["id"], i) for c in PROTOCOL["cases"] for i in range(2)]


@pytest.fixture(scope="module")
def baseline():
    return interventions.baseline()


def test_intervention_baseline(baseline):
    common.evidence("intervention-baseline", baseline)


def test_host_schedule_clock_and_roundtrip():
    raw = interventions.definition()
    spec = parse_spec(raw)
    assert parse_spec(spec.to_dict()) == spec
    times = timeline(spec)
    assert len(times) == 65
    controls = control_values(spec, times)
    assert isinstance(controls, Control)
    np.testing.assert_array_equal(controls.pump[:, 0], [1] * 16 + [0] * 24 + [1] * 25)
    np.testing.assert_array_equal(controls.channel, controls.pump)
    assert [event_index(spec, times[i]) for i in (15, 16, 39, 40)] == [0, 1, 1, 2]
    np.testing.assert_array_equal(model.integration_steps(spec, times), np.full(64, 1e-6))
    raw["experiment"]["changes"].append(dict(time=64e-6, pump=[0] * 30, channel=[0] * 30))
    end = parse_spec(raw)
    assert event_index(end, end.experiment.end_time) == 3


@pytest.mark.parametrize(
    "fault",
    (
        "empty",
        "missing_zero",
        "duplicate",
        "reversed",
        "off_grid",
        "past_end",
        "boolean_time",
        "negative",
        "above_one",
        "nan",
        "boolean",
        "short",
        "matrix",
        "missing_control",
        "extra",
    ),
)
def test_host_bad_schedule(fault):
    raw = interventions.definition()
    changes = raw["experiment"]["changes"]
    if fault == "empty":
        changes.clear()
    elif fault == "missing_zero":
        changes.pop(0)
    elif fault == "duplicate":
        changes[2]["time"] = changes[1]["time"]
    elif fault == "reversed":
        changes.reverse()
    elif fault == "off_grid":
        changes[1]["time"] += 0.4e-6
    elif fault == "past_end":
        changes[-1]["time"] = 65e-6
    elif fault == "boolean_time":
        changes[0]["time"] = False
    elif fault in ("negative", "above_one", "nan", "boolean"):
        changes[1]["pump"][0] = {
            "negative": -0.1,
            "above_one": 1.1,
            "nan": float("nan"),
            "boolean": True,
        }[fault]
    elif fault == "short":
        changes[1]["channel"].pop()
    elif fault == "matrix":
        changes[1]["channel"] = [changes[1]["channel"]]
    elif fault == "missing_control":
        del changes[1]["pump"]
    else:
        changes[1]["reset_gate"] = True
    with pytest.raises(ConfigError):
        parse_spec(raw)


def test_host_static_config_identity_and_mixed_controls():
    path = Path(PROTOCOL["prior_binding"]["root"]) / "source/configs/betse_spatial_active.json"
    raw = json.loads(path.read_text())
    spec = parse_spec(raw)
    assert spec.to_dict() == raw and not spec.experiment.changes
    values = control_values(spec, np.array([0.0, 1e-6]))
    assert isinstance(values, Control) and all(np.all(v == 1) for v in values)
    assert all(v.shape == (0, 30) for v in control_values(spec, np.array([])))
    with pytest.raises(ConfigError, match="controls"):
        model.check_steps(spec, np.array([spec.execution.dt]), np.array([0.0]))


def test_compiled_intervention_smoke():
    raw = interventions.definition(backend=BACKEND)
    raw["experiment"] = dict(
        end_time=6e-6,
        observation_times=[0, 2e-6, 4e-6, 6e-6],
        changes=[
            dict(c, time=t)
            for c, t in zip(raw["experiment"]["changes"], (0, 2e-6, 4e-6), strict=True)
        ],
    )
    spec = parse_spec(raw)
    result = run(spec)
    assert all(v.device.platform == BACKEND for v in result.final.state)
    current, p = definition_arrays(spec.model)
    for i in range(6):
        enabled = 0.0 if 2 <= i < 4 else 1.0
        current, _, ok = active.step(
            current,
            p._replace(
                pump_available=p.pump_available * enabled,
                channel_permeability=p.channel_permeability * enabled,
            ),
            spec.execution.dt,
            xp=np,
        )
        assert ok
    short.compare_cpu_gpu_arrays(
        previous.state_arrays(result.final.state),
        previous.state_arrays(model.flatten(current)),
        p.tissue.membrane_area,
    )
    snapshot = result.checkpoint_at(result.times[2])
    resumed = run(spec, snapshot)
    common.bits(resumed.final.state, result.final.state)


@pytest.fixture(scope="module")
def captured(baseline, tmp_path_factory):
    if BACKEND == "gpu":
        assert EVIDENCE
        path = Path(EVIDENCE) / "cpu/intervention-native"
    else:
        root = (
            Path(EVIDENCE) / "cpu" if EVIDENCE else tmp_path_factory.mktemp("intervention-native")
        )
        root.mkdir(parents=True, exist_ok=True)
        path = root / "intervention-native"
        with (
            (root / "intervention-native.stdout.log").open("x") as out,
            (root / "intervention-native.stderr.log").open("x") as err,
        ):
            subprocess.run(
                [
                    "/mnt/workspaces/Cells/venv-betse/bin/python",
                    "-B",
                    str(interventions.PROTOCOL_PATH.with_name("intervention_native.py")),
                    "--output",
                    str(path),
                    "--protocol",
                    str(interventions.PROTOCOL_PATH),
                ],
                check=True,
                timeout=PROTOCOL["resources"]["native_timeout_seconds"],
                stdout=out,
                stderr=err,
                env=dict(
                    os.environ,
                    MPLBACKEND="Agg",
                    MPLCONFIGDIR=str(root / "matplotlib-interventions"),
                ),
            )
    rows = load_capture(path, PROTOCOL)
    for case, index in CASES:
        row, trace = rows[f"{case}/step-{index}/observed"]
        bare, _ = rows[f"{case}/step-{index}/bare"]
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
            assert row[key] == bare[key], key
        assert trace is not None
        independent.step_rows(row)
    return rows


def _rate(state, control, parameters, dt):
    return active.step(
        model.unflatten(state), model.controlled_parameters(parameters, control), dt
    )[1]


RATES = jax.jit(jax.vmap(_rate, in_axes=(0, 0, None, None)))


def simulate(row, trace, spec, protocol=PROTOCOL):
    device = jax.devices(BACKEND)[0]
    initial, p = fixtures.prepare(row, trace, protocol)
    exported, layout = definition_arrays(spec.model)
    common.bits(exported, initial)
    common.bits(layout, p)
    result = run(spec)
    states = active.State(
        passive.State(
            *(
                getattr(result.history, k)[1:, 0]
                if k in ("step_count", "elapsed_s")
                else getattr(result.history, k)[1:]
                for k in passive.State._fields
            )
        ),
        *(getattr(result.history, k)[1:] for k in active.State._fields[1:]),
    )
    before = model.STATE_TYPE(*(v[:-1] for v in result.history))
    controls = control_values(spec, result.times[:-1])
    rates = common.selected(RATES, (before, controls, p, np.asarray(spec.execution.dt)), device)
    fields = common.selected(common.FIELDS, (states.tissue, p.tissue), device)
    observed = common.observed_history(states.tissue, rates.ordinary, fields, p.tissue)
    return dict(
        row=row,
        trace=trace,
        result=result,
        states=states,
        rates=rates,
        observed=observed,
        controls=controls,
        layout=p,
    )


@pytest.fixture(scope="module")
def computed(captured):
    results = {}
    for case, index in CASES:
        row, trace = captured[f"{case}/step-{index}/observed"]
        spec = parse_spec(interventions.definition(case, index, backend=BACKEND))
        results[(case, index)] = simulate(row, trace, spec)
    return results


def compare(value, states=None):
    states = value["states"] if states is None else states
    return reference.compare(
        value["row"],
        value["trace"],
        PROTOCOL["tolerances"],
        states.tissue._asdict(),
        {k: v for k, v in states._asdict().items() if k != "tissue"},
        {k: v for k, v in value["rates"]._asdict().items() if k != "ordinary"},
        value["observed"],
    )


@pytest.mark.parametrize("case,index", CASES)
def test_intervention_native_trajectory(case, index, computed):
    value = computed[(case, index)]
    native = independent.native_check(value["row"], value["trace"], PROTOCOL)
    report = compare(value)
    report.update(
        backend=BACKEND,
        observer_neutrality="bitwise",
        controlled_steps=value["row"]["steps"],
        native_max_errors=native["max_errors"],
        native_pump_error_fmol_s=native["max_pump_error_fmol_s"],
        diagnostics=value["result"].diagnostics,
    )
    common.evidence(
        f"intervention-native-{case}-{index}",
        report,
        fixtures.arrays(value["states"], value["rates"], value["observed"]),
    )


def test_intervention_static_compatibility(computed):
    for index in range(2):
        raw = interventions.definition("sham", index, backend=BACKEND)
        del raw["experiment"]["changes"]
        result = run(parse_spec(raw))
        common.bits(result.history, computed[("sham", index)]["result"].history)
    full = computed[("coupled_block", 0)]["result"]
    raw = full.spec.to_dict()
    raw["experiment"]["changes"].append(dict(time=full.times[-1], pump=[0] * 30, channel=[0] * 30))
    terminal_change = run(parse_spec(raw))
    common.bits(terminal_change.history, full.history)
    assert terminal_change.final.event_index == 3
    common.evidence(
        "intervention-static-compatibility",
        dict(
            status="passed",
            comparison="bitwise",
            neutral_schedules=2,
            terminal_event_no_extra_step=True,
        ),
    )


def test_intervention_effects(computed):
    effects = {}
    for (case, index), value in computed.items():
        controls, rates, result = value["controls"], value["rates"], value["result"]
        for key, rate in (
            ("pump", rates.pump_cycles_fmol_s),
            ("channel", rates.channel_inward_fmol_s),
        ):
            disabled = getattr(controls, key) == 0
            assert np.all(rate[disabled] == 0)
        if case == "sham":
            continue
        sham = computed[("sham", index)]["result"]
        cut = round(16e-6 / result.spec.execution.dt)
        common.bits(
            model.STATE_TYPE(*(v[: cut + 1] for v in result.history)),
            model.STATE_TYPE(*(v[: cut + 1] for v in sham.history)),
        )
        difference = float(
            np.max(
                abs(result.observations.membrane_voltage_V - sham.observations.membrane_voltage_V)
            )
        )
        assert difference > PROTOCOL["tolerances"]["voltage_atol_V"]
        released = result.times[:-1] >= result.spec.experiment.changes[-1].time
        assert np.any(abs(rates.pump_cycles_fmol_s[released]) > 0)
        assert np.any(abs(rates.channel_inward_fmol_s[released]) > 0)
        blocked = controls.channel == 0
        if blocked.any():
            assert np.any(np.diff(result.history.m_gate, axis=0)[blocked] != 0)
        effects[f"{case}-{index}"] = difference
    common.evidence(
        "intervention-effects",
        dict(
            status="passed",
            max_voltage_difference_V=effects,
            blocked_transport_zero=True,
            intrinsic_gates_continue=True,
            transport_restored=True,
            scope="Synthetic short input response, not biological recovery or return to baseline",
        ),
    )


def test_intervention_replay(computed, tmp_path):
    full = computed[("coupled_block", 0)]["result"]
    for cut in (15, 16, 17, 39, 40, 41):
        path = tmp_path / str(cut)
        write_snapshot(path, full.spec, full.checkpoint_at(full.times[cut]))
        saved = load_snapshot(path)
        suffix = run(saved.spec, saved.checkpoint)
        common.bits(suffix.history, model.STATE_TYPE(*(v[cut:] for v in full.history)))
    assert_windows(list(iter_windows(full.spec, WindowPolicy(17))), full)
    at_event = full.checkpoint_at(full.times[16])
    suffix = run(full.spec, at_event)
    assert_windows(list(iter_windows(full.spec, WindowPolicy(11), at_event)), suffix)
    terminal = run(full.spec, full.final)
    common.bits(terminal.final.state, full.final.state)
    common.evidence(
        "intervention-replay",
        dict(
            status="passed",
            state_arrays=13,
            comparison="bitwise",
            checkpoint_steps=[15, 16, 17, 39, 40, 41],
            window_steps=[17, 11],
            terminal=True,
        ),
    )


def test_intervention_branches(computed):
    full = computed[("coupled_block", 0)]["result"]
    checkpoint = full.checkpoint_at(full.times[16])
    raw = full.spec.to_dict()
    raw["experiment"]["changes"][1]["pump"] = [0.5] * 30
    changed = parse_spec(raw)
    selected = branch_checkpoint(full.spec, checkpoint, changed)
    suffix, whole = run(changed, selected), run(changed)
    common.bits(suffix.history, model.STATE_TYPE(*(v[16:] for v in whole.history)))
    common.bits(
        model.STATE_TYPE(*(v[:17] for v in full.history)),
        model.STATE_TYPE(*(v[:17] for v in whole.history)),
    )
    raw["experiment"]["changes"][0]["pump"][0] = 0.5
    with pytest.raises(ConfigError, match="rewrite"):
        branch_checkpoint(full.spec, checkpoint, parse_spec(raw))
    with pytest.raises(ConfigError, match="event position"):
        validate_checkpoint(full.spec, replace(checkpoint, event_index=0))
    common.evidence(
        "intervention-branches",
        dict(
            status="passed",
            future_change_exact=True,
            past_rewrite_rejected=True,
            wrong_event_cursor_rejected=True,
        ),
    )


def test_intervention_worlds(computed, tmp_path):
    specs = [
        computed[k]["result"].spec for k in (("coupled_block", 0), ("regional", 1), ("sham", 0))
    ]
    raw = specs[2].to_dict()
    del raw["experiment"]["changes"]
    raw["experiment"]["end_time"] = 32e-6
    raw["experiment"]["observation_times"] = [0, 16e-6, 32e-6]
    specs[2] = parse_spec(raw)
    batch = BatchSpec(tuple(WorldSpec(i + 10, s) for i, s in enumerate(specs)), 4, 4096, 1024**3)
    full = run_batch(batch)
    for world in batch.worlds:
        common.bits(full.worlds[world.world_id].history, run(world.simulation).history)
    reverse = run_batch(replace(batch, worlds=tuple(reversed(batch.worlds))))
    for key in full.worlds:
        common.bits(full.worlds[key].history, reverse.worlds[key].history)
    rounds = list(iter_batch_windows(batch, WindowPolicy(17)))
    for key in full.worlds:
        assert_windows([r.worlds[key] for r in rounds if key in r.worlds], full.worlds[key])
    # Decimal literals can differ from the accepted step * dt clock by one bit.
    checkpoint_steps = {10: 16, 11: 80, 12: 32}
    checkpoints = full.checkpoint_at(
        {key: full.worlds[key].times[step] for key, step in checkpoint_steps.items()}
    )
    write_batch_snapshot(tmp_path / "worlds", batch, checkpoints)
    saved = load_batch_snapshot(tmp_path / "worlds")
    resumed = run_batch(saved.spec, saved.checkpoints)
    for key, value in resumed.worlds.items():
        cut = checkpoints[key].step_index
        common.bits(value.history, model.STATE_TYPE(*(v[cut:] for v in full.worlds[key].history)))
    common.evidence(
        "intervention-worlds",
        dict(
            status="passed",
            worlds=3,
            comparison="bitwise",
            independent_clocks=True,
            mixed_static_scheduled=True,
            reordered=True,
            disk=True,
            completed_world=True,
        ),
    )


def test_intervention_negative_controls(computed):
    value = computed[("coupled_block", 0)]
    for key in ("event_index", "pump_available", "channel_permeability_m_s"):
        row = copy.deepcopy(value["row"])
        entry = row["fixture"]["interventions"]["steps"][16]
        if key == "event_index":
            entry[key] = 0
        else:
            entry[key][0] += 1
        with pytest.raises(AssertionError):
            independent.step_rows(row)
    states = value["states"]
    corrupt = states._replace(m_gate=states.m_gate.copy())
    corrupt.m_gate[16, 0] += 1e-4
    with pytest.raises(AssertionError):
        compare(value, corrupt)
    state = model.STATE_TYPE(*(np.asarray(v).copy() for v in value["result"].final.state))
    state.channel_inward_fmol[0] += 1e-6
    with pytest.raises(NumericalError, match="material"):
        model.check_values(state, value["result"].spec)
    common.evidence(
        "intervention-negative-controls",
        dict(
            status="passed",
            corrupted_native_controls=3,
            corrupted_gate_rejected=True,
            missing_channel_material_rejected=True,
        ),
    )


def test_intervention_cpu_gpu(computed):
    if BACKEND == "cpu":
        pytest.skip("Requires following L4 phase and saved scheduled CPU histories")
    count = 0
    for (case, index), value in computed.items():
        actual = fixtures.arrays(value["states"], value["rates"], value["observed"])
        with np.load(
            Path(EVIDENCE) / "cpu" / f"intervention-native-{case}-{index}.npz", allow_pickle=False
        ) as saved:
            count += short.compare_cpu_gpu_arrays(
                actual, dict(saved), value["layout"].tissue.membrane_area
            )
    common.evidence("intervention-cpu-gpu", dict(status="passed", compared_scalars=count))
