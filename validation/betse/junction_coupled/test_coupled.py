"""Production composition, domains and compatibility; long panels run detached."""

import copy
import importlib.util
import json
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from cells.core.errors import NumericalError
from cells.core.runner import run, timeline, validate_checkpoint
from cells.core.schedule import PhysicalIonicGraphControl, control_values
from cells.core.specs import ConfigError, parse_spec
from cells.core.state import initialise
from cells.io import load_snapshot, write_snapshot
from cells.models import junction_finite_extracellular as model
from cells.models.registry import get_model
from cells.processes import junction_gate as gate
from cells.processes.electrochemistry import CHARGE_PER_FMOL

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def private(name, file):
    spec = importlib.util.spec_from_file_location(name, HERE / file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


data = private("coupled_test_fixtures", "fixtures.py")
ref = private("coupled_test_reference", "reference.py")
PROTOCOL = json.loads((HERE / "protocol.json").read_text())


def definition(**kwargs):
    return data.definition("network_mixed", PROTOCOL, end=0.001, **kwargs)


def initial(raw=None):
    spec = parse_spec(definition() if raw is None else raw)
    state, layout = model.initial_values(spec)
    control = PhysicalIonicGraphControl(*(v[0] for v in control_values(spec, [0.0])))
    return spec, state, layout, control


def test_roundtrip_numeric_layout_and_independent_coupled_rhs():
    raw = definition()
    spec, state, layout, control = initial(raw)
    assert get_model(spec.model) is model and parse_spec(spec.to_dict()) == spec
    assert not {"junction_sensitivity", "junction_tau", "junction_residual"} & set(layout._fields)
    assert model.domain_valid(state, layout, layout.active, xp=np)
    c = ref.bind(raw)
    expected = ref.rhs(
        c, np.ones(len(c["initial_gate"])), ref.physical(type(state)(*(v[None] for v in state)))[0]
    )
    rate = model.rhs(state, control, layout, layout.active, xp=np)
    actual = ref.physical(type(rate)(*(v[None] for v in rate)))[0]
    np.testing.assert_allclose(actual, expected, rtol=3e-13, atol=2e-13)
    np.testing.assert_allclose(np.sum(rate.amount_increment, axis=-1), 0, atol=3e-17)
    np.testing.assert_array_equal(rate.extracellular_amount_increment, 0)
    readout = model.junction_readouts(state, control.junction, layout, xp=np)
    assert readout.open_fraction.shape == layout.junction_permeability.shape
    np.testing.assert_array_equal(
        readout.open_fraction, np.broadcast_to(state.junction_gate, readout.open_fraction.shape)
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("law", "symmetric_opposing_relaxation@1"),
        ("law", "unknown"),
        ("threshold_voltage_V", -0.001),
        ("threshold_voltage_V", 0.121),
        ("threshold_voltage_V", True),
        ("threshold_voltage_V", np.nan),
        ("minimum_open_fraction", -0.1),
        ("minimum_open_fraction", 1.1),
        ("minimum_open_fraction", 0.9),
        ("initial_gate", 0.01),
        ("initial_gate", 1.001),
        ("initial_gate", np.inf),
        ("tau_s", 0.01),
    ],
)
def test_gate_schema_rejects_invalid_or_legacy_meaning(field, value):
    raw = definition()
    raw["model"]["junctions"][0]["gate"][field] = value
    with pytest.raises(ConfigError):
        parse_spec(raw)


def test_missing_fields_second_residual_and_old_model_identity_are_rejected():
    raw = definition()
    for field in tuple(raw["model"]["junctions"][0]["gate"]):
        changed = copy.deepcopy(raw)
        del changed["model"]["junctions"][0]["gate"][field]
        with pytest.raises(ConfigError):
            parse_spec(changed)
    raw["model"]["junctions"][0]["residual_fraction"] = {"Na": 0.1, "K": 0.1, "Cl": 0.1}
    with pytest.raises(ConfigError):
        parse_spec(raw)
    raw = definition()
    raw["model"]["id"] = "finite_extracellular@2"
    with pytest.raises(ConfigError):
        parse_spec(raw)


def test_blocking_preserves_gate_derivative_and_blocks_all_edge_transport():
    _, state, layout, control = initial()
    opened = model.rhs(state, control, layout, layout.active, xp=np)
    blocked = model.rhs(
        state,
        control._replace(junction=np.zeros_like(control.junction)),
        layout,
        layout.active,
        xp=np,
    )
    np.testing.assert_array_equal(opened.junction_gate, blocked.junction_gate)
    for name in (
        "amount_increment",
        "junction_transferred",
        "junction_dissipated_energy_pJ",
        "extracellular_amount_increment",
    ):
        np.testing.assert_array_equal(getattr(blocked, name), 0)
    assert np.max(np.abs(blocked.junction_gate)) > 0.1
    p = gate.Parameters(layout.junction_threshold_voltage, layout.junction_minimum)
    voltage = model.cell_voltage(state.amount_increment, layout, xp=np)
    expected = gate.rhs(
        state.junction_gate, voltage[layout.senders] - voltage[layout.receivers], p, xp=np
    )
    np.testing.assert_array_equal(blocked.junction_gate, expected)


def test_stage_gate_and_voltage_domains_hold_for_blocked_routes():
    _, state, layout, _ = initial()
    changed = state.junction_gate.copy()
    changed[0] = np.nextafter(layout.junction_minimum[0], -np.inf)
    assert not model.domain_valid(
        state._replace(junction_gate=changed), layout, layout.active, xp=np
    )
    delta = state.amount_increment.copy()
    sender = layout.senders[0]
    # Set a physical charge increment that changes the sender voltage by 0.2 V.
    delta[0, sender] = 0.2 * layout.capacitance[sender] / CHARGE_PER_FMOL
    delta[0, layout.receivers[0]] = -delta[0, sender]
    assert not model.domain_valid(
        state._replace(amount_increment=delta), layout, layout.active, xp=np
    )


def test_cubic_interior_minimum_is_checked():
    _, state, layout, _ = initial()
    values = state.junction_gate.copy()
    values[0] = layout.junction_minimum[0] + 0.001
    state = state._replace(junction_gate=values)
    history = type(state)(*(np.stack([v, v]) for v in state))
    zero = type(state)(*(np.zeros_like(v)[None] for v in state))
    slope = zero.junction_gate.copy()
    slope[0, 0] = -0.1
    with pytest.raises(NumericalError, match="minimum conductance"):
        model.check_interpolants(
            np.asarray([0.0, 0.1]),
            history,
            zero._replace(junction_gate=slope),
            zero._replace(junction_gate=-slope),
            layout,
        )


def test_cubic_interior_junction_voltage_is_checked():
    _, state, layout, _ = initial()
    history = type(state)(*(np.stack([v, v]) for v in state))
    zero = type(state)(*(np.zeros_like(v)[None] for v in state))
    a, b = layout.senders[0], layout.receivers[0]
    rate = 8.0 / (CHARGE_PER_FMOL * (1 / layout.capacitance[a] + 1 / layout.capacitance[b]))
    slope = zero.amount_increment.copy()
    slope[0, 0, a], slope[0, 0, b] = rate, -rate
    with pytest.raises(NumericalError, match="named junction voltage domain"):
        model.check_interpolants(
            np.asarray([0.0, 0.1]),
            history,
            zero._replace(amount_increment=slope),
            zero._replace(amount_increment=-slope),
            layout,
        )


@pytest.mark.parametrize("field", ["junction_threshold_voltage", "junction_minimum"])
def test_gate_parameters_are_checkpoint_owned(field):
    spec = parse_spec(definition())
    cp = initialise(spec)
    value = np.asarray(getattr(cp.layout, field)).copy()
    value[0] += 0.001
    with pytest.raises(ConfigError, match="layout"):
        validate_checkpoint(spec, replace(cp, layout=cp.layout._replace(**{field: value})))


def test_timestep_rate_bound_and_allocation_guard(monkeypatch):
    raw = definition()
    raw["model"]["junctions"][0]["gate"]["threshold_voltage_V"] = 0.12
    with pytest.raises(ConfigError, match="rate bound"):
        timeline(parse_spec(raw))
    spec = parse_spec(definition())

    def no_allocate(_):
        raise AssertionError("Resource check must precede capacity allocation")

    monkeypatch.setattr(model, "initial_values", no_allocate)
    with pytest.raises(ConfigError, match="storage"):
        timeline(replace(spec, execution=replace(spec.execution, capacity=10**8)))


def test_empty_and_padded_edges_have_finite_neutral_dynamics():
    raw = definition()
    raw["model"]["junctions"] = []
    raw["experiment"]["junction_controls"] = []
    _, state, layout, control = initial(raw)
    result = model.rhs(state, control, layout, layout.active, xp=np)
    assert model.domain_valid(state, layout, layout.active, xp=np)
    for value in result:
        np.testing.assert_array_equal(value, 0)


def test_short_production_run_disk_restart_and_composed_processes(tmp_path):
    backend = os.environ.get("CELLS_TEST_BACKEND", "cpu")
    raw = data.with_membrane_processes(definition(backend=backend))
    raw["experiment"]["observation_times"] = [0, 0.000137, 0.0005, 0.001]
    for group in raw["experiment"]["junction_controls"]:
        group["schedule"] += [
            {"time": 0.0003, "open_fraction": 0.0},
            {"time": 0.0007, "open_fraction": 1.0},
        ]
    result = run(parse_spec(raw))
    assert {d.platform for d in result.final.state.amount_increment.devices()} == {backend}
    cp = result.checkpoint_at(0.0005)
    write_snapshot(tmp_path / "restart", result.spec, cp)
    saved = load_snapshot(tmp_path / "restart")
    resumed = run(saved.spec, saved.checkpoint)
    for a, b in zip(result.history, resumed.history, strict=True):
        np.testing.assert_array_equal(a[cp.step_index :], b)
    assert result.history.pump_cycles[-1, 0] > 0
    assert np.any(result.history.channel_transferred[-1])
    assert np.any(result.history.junction_transferred[-1])
    assert result.diagnostics["max_global_balance_error_fmol"] < 2e-11
    np.savez_compressed(tmp_path / "composed-trajectory.npz", **result.history._asdict())
    (tmp_path / "diagnostics.json").write_text(json.dumps(result.diagnostics, indent=2))
    (tmp_path / "execution.json").write_text(
        json.dumps({"backend": backend, "timings": result.timings}, indent=2)
    )


def test_coupled_block_release_matches_independent_odes(tmp_path):
    protocol = copy.deepcopy(PROTOCOL)
    protocol["duration_s"] = 0.02
    protocol["availability"] = [[0.0, 1.0], [0.005, 0.5], [0.01, 0.0], [0.015, 1.0]]
    raw = data.definition(
        "network_mixed", protocol, backend=os.environ.get("CELLS_TEST_BACKEND", "cpu")
    )
    raw["experiment"]["observation_times"] = [0.0, 0.003713, 0.005, 0.01, 0.012345, 0.015, 0.02]
    result = run(parse_spec(raw))
    c = ref.bind(raw)
    actual = ref.physical(result.observations)
    reports = {}
    for method in ("DOP853", "Radau"):
        expected, _ = ref.integrate(c, protocol["reference"], result.observations.times, method)
        reports[method] = ref.difference(c, actual, expected)
    (tmp_path / "comparison.json").write_text(json.dumps(reports, indent=2))
    np.savez_compressed(
        tmp_path / "trajectory.npz", times_s=result.times, **result.history._asdict()
    )
    for errors in reports.values():
        for name, error in errors.items():
            assert error <= protocol["tolerances"][name]
    blocked = (result.times >= 0.01) & (result.times <= 0.015)
    transfer = result.history.junction_transferred[blocked]
    np.testing.assert_array_equal(transfer, np.broadcast_to(transfer[0], transfer.shape))
    assert np.max(np.abs(np.diff(result.history.junction_gate[blocked], axis=0))) > 1e-8


LEGACY_PROBE = """
import json, sys
import numpy as np
from cells.core.specs import parse_spec
from cells.core.schedule import PhysicalIonicGraphControl, control_values
from cells.models.registry import get_model
results=[]
for raw in json.load(sys.stdin):
    spec=parse_spec(raw)
    model=get_model(spec.model)
    state,layout=model.initial_values(spec)
    control=PhysicalIonicGraphControl(*(v[0] for v in control_values(spec,[0.])))
    rate=model.rhs(state,control,layout,layout.active,xp=np)
    results.append(dict(fingerprint=spec.fingerprint,resolved=spec.to_dict(),
        state=[v.tolist() for v in state],layout=[v.tolist() for v in layout],
        fields=layout._fields,rate=[v.tolist() for v in rate]))
print(json.dumps(results,sort_keys=True,allow_nan=False))
"""


def test_prior_families_match_frozen_preintegration_source(tmp_path):
    prior = data.WORKSPACE / "betse-junction-gate-20260920-02"
    receipt = data.read(prior / "completion.json")
    assert receipt["registration_sha256"] == data.sha(prior / "registration.json")
    registration = data.read(prior / "registration.json")
    for name, digest in registration["sources_sha256"].items():
        if name.startswith("src/cells/"):
            assert data.sha(prior / "source" / name) == digest
    raws = [
        data.read(ROOT / "configs" / (name + ".json"))
        for name in ("finite_extracellular_cell", "kinetic_finite_cell", "physical_ionic_star")
    ]
    raws.append(data.prior_definition("network_mixed"))
    outputs = []
    for i, source in enumerate((prior / "source/src", ROOT / "src")):
        result = subprocess.run(
            [sys.executable, "-B", "-c", LEGACY_PROBE],
            input=json.dumps(raws),
            text=True,
            capture_output=True,
            check=True,
            timeout=30,
            env=os.environ | {"PYTHONPATH": str(source)},
            cwd=tmp_path,
        )
        (tmp_path / f"legacy-{i}.json").write_text(result.stdout)
        (tmp_path / f"legacy-{i}.stderr.log").write_text(result.stderr)
        assert not result.stderr
        outputs.append(result.stdout)
    assert outputs[0] == outputs[1]
