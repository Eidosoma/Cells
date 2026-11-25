"""Dynamic junctions with spatial pumps and channels: protocol, clock, domains and one compiled run.

The 18 rows on the native captures left on 25 November 2026. They could not start: the predecessor
check refuses since the src files it binds changed (11 October 2026). Their driver,
validation/betse/spatial_active/junction_native.py, is kept at the tag pre-cleanup-2026-11-25, which
does not run it either.
"""

import copy
import json

import jax
import numpy as np
import pytest

from cells.laws.junctions import junction_gate
from tests.unit import test_betse_spatial_active as previous
from validation.betse.emulator import active as active
from validation.betse.emulator import junction as model
from validation.betse.emulator.spatial_spec import CONFIGS, definition_arrays, parse
from validation.betse.junction_gate.reference import rates as decimal_rates
from validation.betse.spatial_active import junctions

common = previous.short
BACKEND = common.BACKEND
PROTOCOL, TOL = junctions.protocol(), previous.TOL
CASES = [(c["id"], i) for c in PROTOCOL["cases"] for i in (0, 1)]
RUN = jax.jit(model.trajectory)


@pytest.fixture(scope="module")
def device():
    jax.config.update("jax_enable_x64", True)
    return jax.devices(BACKEND)[0]


@pytest.fixture(scope="module")
def example():
    data = json.loads((CONFIGS / "betse_spatial_active.json").read_text())
    initial, p = definition_arrays(parse(data).model)
    ones = np.ones_like(p.pump_available)
    layout = model.validate_layout(
        model.Layout(
            p,
            junction_gate.Parameters(
                ones * PROTOCOL["junction"]["threshold_voltage_V"],
                ones * PROTOCOL["junction"]["minimum_open_fraction"],
            ),
            p.tissue.junction_open.copy(),
            np.flatnonzero(p.tissue.moving),
        )
    )
    return model.initial_state(initial, layout, ones * PROTOCOL["junction"]["initial_open"]), layout


def test_host_junction_protocol_and_resources(example):
    assert PROTOCOL["tolerances"] == previous.PROTOCOL["tolerances"]
    assert PROTOCOL["native_update_tolerances"] == previous.PROTOCOL["native_update_tolerances"]
    assert PROTOCOL["duration_s"] == 64e-6 and PROTOCOL["native_steps_s"] == [1e-6, 0.5e-6]
    assert not PROTOCOL["automatic_followup"] and len(CASES) == 12
    initial, layout = example
    patches = layout.junction_block.size
    control = model.Control(*(np.ones(patches) for _ in range(3)))
    _, rates, valid = model.step(initial, layout, 1e-6, control, xp=np)
    assert valid
    fields = common.model.field(initial.active.tissue, layout.active.tissue, xp=np)
    retained_per_step = sum(v.nbytes for v in jax.tree.leaves((initial, rates, fields)))
    plans = []
    for case in PROTOCOL["cases"]:
        for dt in PROTOCOL["native_steps_s"]:
            steps = round(PROTOCOL["duration_s"] / dt)
            controls = junctions.controls(case, dt, steps, patches)
            assert all(v.shape == (steps, patches) for v in controls)
            # States, rates, field readouts and controls, with three host/device copies.
            estimate = 3 * ((steps + 1) * retained_per_step + sum(v.nbytes for v in controls))
            plans.append(
                dict(case=case["id"], dt_s=dt, steps=steps, estimated_array_bytes=estimate)
            )
    total = sum(p["estimated_array_bytes"] for p in plans)
    assert total < PROTOCOL["resources"]["max_retained_array_estimate_bytes"]
    common.evidence(
        "junction-resources",
        dict(
            status="passed",
            plans=plans,
            total_array_estimate_bytes=total,
            scope="Retained-array estimate; compiler/process memory is bounded separately",
        ),
    )


@pytest.mark.parametrize("block", [0.0, 0.5, 1.0])
def test_host_junction_decimal_clock_and_block(block):
    voltage = np.array([-0.12, -0.04, 0.0, 0.04, 0.12])
    parameters = junction_gate.Parameters(np.full(5, 0.015), np.full(5, 0.1))
    a, b = decimal_rates(voltage, 0.015)
    expected = np.full(5, 0.35)
    actual = expected.copy()
    dt = 1e-6
    first = None
    for _ in range(3):
        expected = block * ((expected + dt * (a + 0.1 * b)) / (1 + dt * (a + b)))
        actual = model.gate_step(actual, voltage, block, dt, parameters, xp=np)
        np.testing.assert_allclose(actual, expected, atol=TOL["gate_atol"], rtol=TOL["gate_rtol"])
        if first is None:
            first = actual.copy()
    if block:
        assert np.max(abs(actual - first)) > 1e-7
    else:
        np.testing.assert_array_equal(actual, 0)


@pytest.mark.parametrize(
    "fault",
    [
        "duplicate",
        "missing",
        "float_order",
        "threshold",
        "minimum",
        "block",
        "asymmetric",
        "fractional_mask",
    ],
)
def test_host_junction_bad_layout(example, fault):
    _, layout = copy.deepcopy(example)
    if fault == "duplicate":
        layout.moving_order[1] = layout.moving_order[0]
    elif fault == "missing":
        layout = layout._replace(moving_order=layout.moving_order[:-1])
    elif fault == "float_order":
        layout = layout._replace(moving_order=layout.moving_order.astype(float))
    elif fault in ("threshold", "minimum"):
        layout.junction[0 if fault == "threshold" else 1][0] = -0.1
    elif fault == "block":
        layout.junction_block[0] = np.nan
    elif fault == "asymmetric":
        i = np.flatnonzero(layout.active.tissue.partner != np.arange(layout.junction_block.size))[0]
        layout.junction_block[i] = 0.25
    else:
        layout.active.tissue.junction_open[:] = 0.5
    with pytest.raises(ValueError):
        model.validate_layout(layout)


@pytest.mark.parametrize(
    "fault",
    [
        "negative_gate",
        "nan_gate",
        "above_one",
        "asymmetric_gate",
        "bad_control",
        "asymmetric_control",
        "negative_dt",
        "voltage",
    ],
)
def test_host_junction_invalid_trial_retains_state(example, fault):
    state, p = copy.deepcopy(example)
    control = model.Control(*(np.ones(p.junction_block.size) for _ in range(3)))
    dt = 1e-6
    if fault in ("negative_gate", "nan_gate", "above_one"):
        state.junction_open[0] = {"negative_gate": -0.1, "nan_gate": np.nan, "above_one": 1.1}[
            fault
        ]
    elif fault in ("asymmetric_gate", "asymmetric_control"):
        i = np.flatnonzero(p.active.tissue.partner != np.arange(p.junction_block.size))[0]
        (state.junction_open if fault == "asymmetric_gate" else control.junction)[i] = 0.25
    elif fault == "bad_control":
        control.junction[:] = -0.5
    elif fault == "negative_dt":
        dt = -dt
    else:
        # Opposing large surface potentials exceed the declared transjunction domain.
        p.active.tissue.boundary_values[:, 0] = -1
        p.active.tissue.boundary_values[:, -1] = 1
    result, _, valid = model.step(state, p, dt, control, xp=np)
    assert not valid
    common.bits(result, state)


def test_compiled_junction_smoke_and_static_transport_limit(example, device):
    state, p = example
    case = PROTOCOL["cases"][0]
    controls = junctions.controls(case, 1e-6, 4, p.junction_block.size)
    expected = state
    for i in range(4):
        expected, _, valid = model.step(
            expected, p, 1e-6, jax.tree.map(lambda v, i=i: v[i], controls), xp=np
        )
        assert valid
    final, (_, _, accepted), valid = common.selected(
        RUN, (state, p, np.asarray(1e-6), controls), device
    )
    assert valid and accepted.all()
    for a, b in zip(jax.tree.leaves(final), jax.tree.leaves(expected), strict=True):
        np.testing.assert_allclose(a, b, atol=2e-12, rtol=2e-12)
    blocked = p.active._replace(
        tissue=p.active.tissue._replace(
            junction_permeability=np.zeros_like(p.active.tissue.junction_permeability)
        )
    )
    controls = model.Control(*(np.ones(p.junction_block.size) for _ in range(3)))
    previous_state, _, good = active.step(state.active, blocked, 1e-6, xp=np)
    actual, _, valid = model.step(state, p._replace(active=blocked), 1e-6, controls, xp=np)
    assert valid and good
    common.bits(actual.active, previous_state)
