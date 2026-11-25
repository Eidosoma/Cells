"""The long junction panel's protocol, its self-refinement rule and one compiled quarter step.

The 31 rows on the long native captures left on 25 November 2026. They could not start: the
predecessor check refuses since the src files it binds changed (11 October 2026). Their driver,
validation/betse/spatial_active/junction_native.py, is kept at the tag pre-cleanup-2026-11-25, which
does not run it either.
"""

import jax
import numpy as np
import pytest

from cells.laws.junctions import junction_gate
from tests.unit import test_betse_spatial_active_refinement as temporal
from tests.unit import test_betse_spatial_junction as short
from validation.betse.emulator import junction as model
from validation.betse.junction_gate.reference import rates as decimal_rates
from validation.betse.spatial_active import junction_refinement as long
from validation.betse.spatial_active import junctions

common, TOL = short.common, short.TOL
PROTOCOL = long.protocol()
CASES = [(c["id"], i) for c in PROTOCOL["cases"] for i in range(3)]
RUN = short.RUN
device, example = short.device, short.example


def test_host_long_junction_protocol_and_resources(example):
    for name in (
        "cases",
        "junction",
        "tolerances",
        "native_update_tolerances",
        "species",
        "initial_gate",
        "pump_parameters",
        "temperature_K",
        "gj_surface_fraction",
        "initial_voltage_extent_V",
        "base_concentration_mM",
        "outside_mM",
        "concentration_gradient_mM",
    ):
        assert PROTOCOL[name] == short.PROTOCOL[name], name
    assert PROTOCOL["duration_s"] == 4 * short.PROTOCOL["duration_s"] == 256e-6
    assert PROTOCOL["native_steps_s"] == [1e-6, 0.5e-6, 0.25e-6]
    for name in ("resolved_error_multiple", "ratio_min", "ratio_max"):
        assert PROTOCOL["refinement"][name] == temporal.PROTOCOL["refinement"][name]
    eligible = [c["id"] for c in PROTOCOL["cases"] if c["id"] != "half_block"]
    assert PROTOCOL["refinement"]["cases"] == eligible
    assert PROTOCOL["refinement"]["required_resolved_final_fields"] == {
        c: ["vm", "m_gate"] for c in eligible
    }
    assert PROTOCOL["refinement"]["required_resolved_junction_cases"] == [
        c for c in eligible if c != "disconnected"
    ]
    assert PROTOCOL["step_sensitivity"]["cases"] == ["half_block"]
    assert PROTOCOL["step_sensitivity"]["updates_per_outer_step"] == 3
    assert not PROTOCOL["allowed_prior_source_changes"]
    assert PROTOCOL["automatic_followup"] is False and len(CASES) == 18
    initial, layout = example
    patches = layout.junction_block.size
    control = model.Control(*(np.ones(patches) for _ in range(3)))
    _, rates, valid = model.step(initial, layout, 0.25e-6, control, xp=np)
    assert valid
    fields = common.model.field(initial.active.tissue, layout.active.tissue, xp=np)
    retained_per_step = sum(v.nbytes for v in jax.tree.leaves((initial, rates, fields)))
    plans = []
    for case in PROTOCOL["cases"]:
        for dt in PROTOCOL["native_steps_s"]:
            steps = round(PROTOCOL["duration_s"] / dt)
            controls = junctions.controls(case, dt, steps, patches)
            assert all(v.shape == (steps, patches) for v in controls)
            estimate = 3 * ((steps + 1) * retained_per_step + sum(v.nbytes for v in controls))
            plans.append(
                dict(case=case["id"], dt_s=dt, steps=steps, estimated_array_bytes=estimate)
            )
    total = sum(p["estimated_array_bytes"] for p in plans)
    limit = PROTOCOL["resources"]["max_retained_array_estimate_bytes"]
    assert total < limit <= PROTOCOL["resources"]["max_worker_rss_bytes"] // 2
    common.evidence(
        "long-junction-resources",
        dict(
            status="passed",
            plans=plans,
            total_array_estimate_bytes=total,
            scope="Retained-array estimate; compiler/process memory is bounded separately",
        ),
    )


def test_host_fractional_block_clock_has_dt_dependent_physical_rate():
    rule, parameters = PROTOCOL["step_sensitivity"], PROTOCOL["junction"]
    voltage = np.asarray([rule["fixed_voltage_V"]])
    alpha, beta = decimal_rates(voltage, parameters["threshold_voltage_V"])
    minimum = parameters["minimum_open_fraction"]
    layout = junction_gate.Parameters(
        np.asarray([parameters["threshold_voltage_V"]]), np.asarray([minimum])
    )
    records = []
    for block in (0.0, rule["block_fraction"], 1.0):
        for dt in PROTOCOL["native_steps_s"]:
            count = rule["updates_per_outer_step"] * round(rule["duration_s"] / dt)
            multiplier = block / (1 + dt * (alpha + beta))
            fixed_point = (
                block * dt * (alpha + minimum * beta) / ((1 - block) + dt * (alpha + beta))
            )
            closed_form = (
                fixed_point + (parameters["initial_open"] - fixed_point) * multiplier**count
            )
            actual = np.asarray([parameters["initial_open"]])
            for _ in range(count):
                actual = model.gate_step(actual, voltage, block, dt, layout, xp=np)
            np.testing.assert_allclose(
                actual, closed_form, atol=TOL["gate_atol"], rtol=TOL["gate_rtol"]
            )
            records.append(dict(block=block, dt_s=dt, updates=count, final_open=float(actual[0])))
    partial = [r["final_open"] for r in records if r["block"] == rule["block_fraction"]]
    assert partial[0] > partial[1] > partial[2] > 0
    assert rule["block_fraction"] == 0.5
    common.evidence(
        "long-junction-fixed-voltage-block-clock",
        dict(
            status="passed",
            records=records,
            recurrence=(
                "g_next = block * (g + dt * (alpha + minimum * beta)) / (1 + dt * (alpha + beta))"
            ),
            pure_block_decay_rate_per_s=[3 * np.log(2) / dt for dt in PROTOCOL["native_steps_s"]],
            scope="Constant-voltage closed-form recurrence; partial block is prescribed per update",
        ),
    )


def synthetic_series():
    rule, values = temporal.synthetic_series()
    rule["refinement"].update(cases=["coupled"], required_resolved_junction_cases=["coupled"])
    for dt, value in zip(rule["native_steps_s"], values, strict=True):
        value["junction_open"] = np.full((round(rule["duration_s"] / dt), 2), 0.2 + 0.01 * dt)
    return rule, values


def test_host_junction_refinement_resolves_shared_state():
    rule, values = synthetic_series()
    report = long.check("coupled", values, np.ones(2), rule)
    for checkpoint in report["checkpoints"]:
        assert all(
            v["first_order_resolved"] and v["ratio"] == pytest.approx(2)
            for v in checkpoint["fields"].values()
        )


@pytest.mark.parametrize(
    "fault",
    [
        "fractional_block",
        "unresolved",
        "nonfinite",
        "wrong_order",
        "worse",
        "truncated",
        "shape",
        "domain",
    ],
)
def test_host_junction_refinement_rejects_false_claims(fault):
    rule, values = synthetic_series()
    case = "coupled"
    if fault == "fractional_block":
        case = "half_block"
    elif fault == "unresolved":
        for value in values:
            value["junction_open"][:] = 0.2
    elif fault == "nonfinite":
        values[2]["junction_open"][-1, 0] = np.nan
    elif fault == "wrong_order":
        values[2]["junction_open"][:] = 0.201
    elif fault == "worse":
        values[2]["junction_open"][:] = 0.5
    elif fault == "truncated":
        values[2]["junction_open"] = values[2]["junction_open"][:-1]
    elif fault == "shape":
        values[2]["junction_open"] = values[2]["junction_open"][:, :1]
    else:
        values[2]["junction_open"][0, 0] = -0.1
    with pytest.raises(AssertionError):
        long.check(case, values, np.ones(2), rule)


def test_compiled_quarter_step_junction_smoke(example, device):
    state, layout = example
    case = dict(
        PROTOCOL["cases"][0],
        junction_changes=[
            dict(time_s=0.0, fraction=1.0),
            dict(time_s=2e-6, fraction=0.0),
            dict(time_s=4e-6, fraction=1.0),
        ],
    )
    dt = 0.25e-6
    controls = junctions.controls(case, dt, 24, layout.junction_block.size)
    expected = state
    for i in range(24):
        expected, _, valid = model.step(
            expected, layout, dt, jax.tree.map(lambda a, i=i: a[i], controls), xp=np
        )
        assert valid
    final, (states, rates, accepted), valid = common.selected(
        RUN, (state, layout, np.asarray(dt), controls), device
    )
    assert valid and accepted.all()
    for a, b in zip(jax.tree.leaves(final), jax.tree.leaves(expected), strict=True):
        np.testing.assert_allclose(a, b, atol=2e-12, rtol=2e-12)
    np.testing.assert_array_equal(states.junction_open[8:16], 0)
    np.testing.assert_array_equal(rates.active.ordinary.junction_outward_fmol_s[8:16], 0)
    assert np.any(states.junction_open[16] > 0)
