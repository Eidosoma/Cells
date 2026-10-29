"""Actual carried fuel admission; manufactured histories earn no trajectory credit."""

from copy import deepcopy
from functools import lru_cache

import numpy as np
import pytest

from cells.core.specs import ConfigError, parse_spec
from cells.tissue_phase import prepare_request
from tests import owned_barrier_phase_fixtures as fixtures
from tests.unit.test_owned_barrier_phase_reference import evidence, setup
from validation.topology import owned_barrier_phase_handoff_reference as reference


@lru_cache
def bound(case):
    request, context, state, _, spec, actual, layout, _, model, _ = setup("energy", case)
    maximum, rows = reference.carried_fuel_turnover(request["simulation"], state)
    return request, context, state, spec, actual, layout, model, maximum, rows


@pytest.mark.parametrize("case", ["changed", "empty"])
def test_actual_carried_gross_turnover_and_both_sides_of_limit(case):
    request, _, _, spec, _, _, model, expected, rows = bound(case)
    assert expected > 0
    actual = model.check_carried_pool_turnover(spec, spec.execution.dt)
    np.testing.assert_allclose(actual, expected, rtol=3e-11, atol=3e-15)
    below, above = 0.99 * 0.05 / expected, 1.01 * 0.05 / expected
    np.testing.assert_allclose(
        model.check_carried_pool_turnover(spec, below), expected, rtol=3e-11, atol=3e-15
    )
    with pytest.raises(ConfigError, match="turnover"):
        model.check_carried_pool_turnover(spec, above)
    times = {row["time_s"] for row in rows}
    raw = request["simulation"]
    for name, groups in raw["experiment"].items():
        if name.endswith("_controls"):
            for group in groups:
                assert {v["time"] for v in group.get("controls", group.get("schedule"))} <= times
    for event in () if raw["model"]["intervention"] is None else (raw["model"]["intervention"],):
        assert {event["on_s"], (event["on_s"] + event["off_s"]) / 2, event["off_s"]} <= times
    if case == "empty":
        assert times == {0.0, fixtures.DT, 2 * fixtures.DT}
    evidence(
        "turnover-boundary-" + case,
        dict(
            independent=rows,
            actual_maximum_rate_s=actual,
            limit=0.05,
            below_step_s=below,
            rejected_above_step_s=above,
            scope="Stage admission at carried pools; no trajectory claim",
        ),
    )


@pytest.mark.parametrize("case", ["changed", "empty"])
def test_signed_opposing_routes_are_added_gross_before_pool_division(case):
    _, _, _, _, _, _, _, _, rows = bound(case)
    cancellation = []
    for row in rows:
        n = len(row["minimum_carried_amount_fmol"])
        hydrolysis, synthesis = np.zeros(n), np.zeros(n)
        for rates, owners, sign in (
            (row["signed_pump_cycles_fmol_s"], row["pump_owners"], 1.0),
            (row["signed_regeneration_cycles_fmol_s"], row["regeneration_owners"], -1.0),
        ):
            for value, owner in zip(rates, owners, strict=True):
                hydrolysis[owner] += max(sign * value, 0.0)
                synthesis[owner] += max(-sign * value, 0.0)
        gross = hydrolysis + synthesis
        net = np.abs(np.asarray(row["net_pool_amount_rate_fmol_s"])[0])
        np.testing.assert_allclose(
            hydrolysis, row["gross_hydrolysis_fmol_s"], rtol=3e-15, atol=1e-16
        )
        np.testing.assert_allclose(synthesis, row["gross_synthesis_fmol_s"], rtol=3e-15, atol=1e-16)
        np.testing.assert_allclose(
            gross / row["minimum_carried_amount_fmol"],
            row["fractional_rate_by_owner_s"],
            rtol=3e-15,
            atol=1e-15,
        )
        assert np.all(gross >= net - 1e-13)
        cancellation.extend((gross - net).tolist())
    assert max(cancellation) > 1e-8
    evidence(
        "turnover-gross-" + case,
        dict(gross_minus_absolute_net_fmol_s=cancellation, summed_route_directions=True),
    )


def test_ecm_admission_knots_are_not_lost_in_complete_control_union(monkeypatch):
    request, _, state, _, _, _, _, _, _ = bound("changed")
    raw = deepcopy(request["simulation"])
    event = raw["model"]["intervention"]
    event.update(on_s=0.4 * fixtures.DT, off_s=1.4 * fixtures.DT)
    expected = {event["on_s"], (event["on_s"] + event["off_s"]) / 2, event["off_s"]}
    existing = {0.0, raw["experiment"]["end_time"]}
    for name, groups in raw["experiment"].items():
        if name.endswith("_controls"):
            for group in groups:
                existing.update(v["time"] for v in group.get("controls", group.get("schedule")))
    assert expected.isdisjoint(existing)
    maximum, rows = reference.carried_fuel_turnover(raw, state)
    times = {row["time_s"] for row in rows}
    assert expected <= times
    modified = deepcopy(request)
    modified["simulation"] = raw
    spec = parse_spec(prepare_request(modified).definition)
    _, model, _ = fixtures.OWNERS["energy"]
    evaluated = []
    readouts = model.readouts

    def record_clock(actual_state, *args, **kwargs):
        evaluated.append(float(actual_state.phase_clock_s[0]))
        return readouts(actual_state, *args, **kwargs)

    monkeypatch.setattr(model, "readouts", record_clock)
    actual = model.check_carried_pool_turnover(spec, spec.execution.dt)
    np.testing.assert_allclose(actual, maximum, rtol=3e-11, atol=3e-15)
    assert set(evaluated) == times
    evidence(
        "turnover-exclusive-ecm-knots",
        dict(
            unique_barrier_clocks_s=sorted(expected),
            production_clocks_s=evaluated,
            independent_maximum_rate_s=maximum,
            production_maximum_rate_s=actual,
            independent=rows,
        ),
    )


def regeneration_history_probe(context, vector):
    """Material/energy-consistent counterfactual, not an integrated source epoch."""
    fields = {key: value.copy() for key, value in reference.unpack(context, vector).items()}
    parent = context["parent"]
    raw = context["parent_definition"]["model"]
    pools = {row["id"]: row for row in raw["energy_pools"]}
    changed, report = set(), []
    for j, port in enumerate(raw["regeneration_ports"]):
        owner = parent["cell_ids"].index(pools[port["pool_id"]]["cell_id"])
        if owner in changed:
            continue
        before = (
            parent["energy_initial"][:, owner] + fields["energy_amount_increment_fmol"][:, owner]
        )
        cycles = 0.9 * min(before[1:])
        after = before + np.asarray([cycles, -cycles, -cycles])
        free_energy_change = reference.energy_chemistry.free_energy_change(
            before,
            after,
            parent["vi"][owner],
            parent["vi"][owner],
            parent["temperature"],
            parent["energy_delta_g0"][owner],
        )
        supplied = 1e-3 * cycles * port["supplied_energy_J_per_mol"]
        heat = supplied - free_energy_change
        assert heat >= 0.0
        fields["energy_amount_increment_fmol"][:, owner] += np.asarray([cycles, -cycles, -cycles])
        fields["regeneration_cycles_fmol"][j] += cycles
        fields["regeneration_supplied_work_pJ"][j] += supplied
        fields["regeneration_dissipated_energy_pJ"][j] += heat
        changed.add(owner)
        report.append(
            dict(
                owner=owner,
                port_id=port["id"],
                synthesis_fmol=cycles,
                before_fmol=before,
                after_fmol=after,
                free_energy_change_pJ=free_energy_change,
                supplied_pJ=supplied,
                heat_pJ=heat,
            )
        )
    assert changed == set(range(len(parent["cell_ids"])))
    return reference.flatten(context, fields), report


def test_manufactured_conserved_carried_pools_require_a_different_bound(monkeypatch):
    request, context, vector, spec, state, layout, model, original_rate, _ = bound("changed")
    manufactured, synthesis = regeneration_history_probe(context, vector)
    before = reference.conservation(context, vector)
    after = reference.conservation(context, manufactured)
    for key in ("adenylate_fmol", "phosphorus_fmol", "pool_cycle_residual_fmol"):
        np.testing.assert_allclose(after[key], 0.0, rtol=0, atol=3e-14)
    np.testing.assert_allclose(after["pool_internal_transfer_residual_pJ"], 0.0, rtol=0, atol=1e-10)
    np.testing.assert_allclose(after["energy_pJ"], before["energy_pJ"], rtol=0, atol=1e-10)
    for key in (
        "chemical_amount_fmol",
        "free_cytosol_amount_fmol",
        "cell_charge_C",
        "outside_charge_C",
    ):
        np.testing.assert_array_equal(after[key], before[key])
    actual_rate, rows = reference.carried_fuel_turnover(request["simulation"], manufactured)
    original_minimum = np.min(context["parent"]["energy_initial"], axis=0)
    wrong_original_denominator = max(
        float(
            np.max(
                (np.asarray(row["gross_hydrolysis_fmol_s"]) + row["gross_synthesis_fmol_s"])
                / original_minimum
            )
        )
        for row in rows
    )
    assert actual_rate > 5 * wrong_original_denominator
    gap_step = 0.05 / np.sqrt(actual_rate * wrong_original_denominator)
    assert gap_step * wrong_original_denominator < 0.05 < gap_step * actual_rate
    # Lift only the declared actual compact fields into the original padded
    # complete state. All unused owners retain exact zeros.
    values = reference.unpack(context, manufactured)
    copied = {name: np.array(value, copy=True) for name, value in state._asdict().items()}
    for name, shape in context["shapes"].items():
        copied[name][tuple(slice(0, n) for n in shape)] = values[name]
    carried = type(state)(*(copied[name] for name in state._fields))
    model.check_values(carried, spec)
    monkeypatch.setattr(model, "initial_values", lambda _spec: (carried, layout))
    np.testing.assert_allclose(
        model.check_carried_pool_turnover(spec, 0.99 * 0.05 / actual_rate),
        actual_rate,
        rtol=3e-11,
        atol=3e-15,
    )
    with pytest.raises(ConfigError, match="turnover"):
        model.check_carried_pool_turnover(spec, gap_step)
    evidence(
        "turnover-manufactured-conserved-history",
        dict(
            original_carried_rate_s=original_rate,
            modified_carried_rate_s=actual_rate,
            incorrect_original_denominator_rate_s=wrong_original_denominator,
            separating_step_s=gap_step,
            synthesis_history=synthesis,
            original_conservation=before,
            manufactured_conservation=after,
            independent=rows,
            scope=(
                "Manufactured material/energy-consistent history; not claimed reachable in1ns "
                "or a qualified trajectory; no biological case"
            ),
        ),
        {"original_state": vector, "manufactured_state": manufactured},
    )


@pytest.mark.parametrize(
    "step", [-1.0, float("nan"), float("inf")], ids=["negative", "nan", "infinite"]
)
def test_invalid_turnover_step_is_refused(step):
    _, _, _, spec, _, _, model, _, _ = bound("changed")
    with pytest.raises(ConfigError):
        model.check_carried_pool_turnover(spec, step)


def test_definition_and_step_admission_both_invoke_actual_carried_guard(monkeypatch):
    _, _, _, spec, _, _, model, _, _ = bound("changed")
    calls = []

    def guard(_spec, step):
        calls.append(step)
        raise ConfigError("carried-turnover-sentinel")

    monkeypatch.setattr(model, "check_carried_pool_turnover", guard)
    with pytest.raises(ConfigError, match="carried-turnover-sentinel"):
        model.check_definition(spec)
    monkeypatch.setattr(model.scheduled, "check_steps", lambda *args: None)
    steps = np.asarray([0.25 * spec.execution.dt, 0.5 * spec.execution.dt])
    with pytest.raises(ConfigError, match="carried-turnover-sentinel"):
        model.check_steps(spec, steps, None)
    assert calls == [spec.execution.dt, float(np.max(steps))]
    evidence("turnover-admission-hooks", dict(called_steps_s=calls, scope="Software dispatch only"))
