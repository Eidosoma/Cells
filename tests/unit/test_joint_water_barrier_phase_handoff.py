"""Full-state instantaneous physics and explicit ECM epoch refusal contracts."""

from copy import deepcopy
from dataclasses import replace

import numpy as np
import pytest

from cells.core import joint_water_barrier_phase_handoff as bridge
from cells.core.errors import NumericalError
from cells.core.schedule import control_values
from cells.core.specs import ConfigError, parse_spec
from tests.joint_water_barrier_phase_fixtures import (
    DT,
    OWNERS,
    components,
    prepared,
    request,
    source_checkpoint,
)
from tests.unit.test_joint_water_barrier_interventions import rate_budget
from tests.unit.test_surface_catalog import evidence
from validation.transport import joint_water_barrier_phase_reference as reference


@pytest.mark.parametrize("family", OWNERS)
@pytest.mark.parametrize("case", ("changed", "empty"))
def test_carried_barrier_epoch_complete_independent_stages(family, case):
    raw = request(family, case)
    result = prepared(family, case)
    spec = parse_spec(result.definition)
    _, model = components(family)
    state, layout = model.initial_values(spec)
    context, initial = reference.initial(raw)
    np.testing.assert_array_equal(reference.scheduled.flatten(context, state._asdict()), initial)
    rows, arrays = [], {}
    for i, time in enumerate((0.0, DT, 2 * DT)):
        trial = state._replace(phase_clock_s=np.asarray([time]))
        table = control_values(spec, [time])
        control = type(table)(*(v[0] for v in table))
        flat = reference.scheduled.flatten(context, trial._asdict())
        expected, phi, proof = reference.scheduled.evaluate(context, flat, time)
        actual = model.readouts(trial, control, layout, xp=np)
        slope = reference.scheduled.flatten(context, actual.derivative._asdict())
        budget = rate_budget(context, expected)
        ratio = float(np.max(np.abs(slope - expected) / budget, initial=0))
        assert ratio <= 1
        n = layout.active.size
        potentials = np.r_[
            actual.field.potential_V[:n][layout.active],
            actual.field.potential_V[n:][layout.outside_active],
        ]
        np.testing.assert_allclose(potentials, phi, rtol=3e-10, atol=3e-13)
        assert actual.valid and abs(actual.field.energy_balance_pJ_s) < 1e-10
        assert abs(proof["physical_energy_balance_pJ_s"]) < 1e-10
        assert proof["max_charge_residual_C"] <= 3e-25
        assert proof["max_component_current_residual_A"] <= 1e-23
        assert type(model.rhs(trial, control, layout, layout.active, xp=np)) is model.STATE_TYPE
        rows.append(dict(time_s=time, error_over_budget=ratio, independent=proof))
        arrays.update(
            {
                f"{i}_{k}": v
                for k, v in dict(
                    state=flat,
                    actual=slope,
                    reference=expected,
                    budget=budget,
                    potential=potentials,
                    reference_potential=phi,
                ).items()
            }
        )
    evidence(
        "barrier-epoch-stages-" + family + "-" + case,
        dict(
            request=raw,
            fields=list(state._fields),
            stages=rows,
            full_trajectory_credit=False,
            independent_biological_cases=0,
        ),
        arrays,
    )


@pytest.mark.parametrize("family", OWNERS)
def test_carried_barrier_fuel_turnover_uses_actual_pools_and_volumes(family):
    raw = request(family)
    spec = parse_spec(prepared(family).definition)
    _, initial = reference.initial(raw)
    expected, rows = reference.carried_fuel_turnover(raw["simulation"], initial)
    _, model = components(family)
    actual = model.check_carried_pool_turnover(spec, spec.execution.dt)
    np.testing.assert_allclose(actual, expected, rtol=3e-11, atol=3e-15)
    assert expected > 0
    with pytest.raises(ConfigError, match="turnover"):
        model.check_carried_pool_turnover(spec, 0.05 / expected * 1.01)
    evidence(
        "barrier-epoch-turnover-" + family,
        dict(
            independent=rows,
            maximum_fractional_rate_s=actual,
            actual_carried_pools=True,
            gross_turnover_limit=0.05,
            excessive_step_refused=True,
        ),
    )


@pytest.mark.parametrize("family", OWNERS)
@pytest.mark.parametrize("fault", ("clock", "precision", "water", "pool", "history", "layout"))
def test_source_refuses_corrupt_owned_arrays_and_clock(family, fault):
    source, point = source_checkpoint(family)
    if fault == "clock":
        point = replace(point, state=point.state._replace(phase_clock_s=np.zeros(1)))
    elif fault == "precision":
        point = replace(
            point,
            state=point.state._replace(channel_gate=point.state.channel_gate.astype(np.float32)),
        )
    elif fault == "layout":
        point = replace(point, layout=point.layout._replace(volume=point.layout.volume * 2))
    else:
        key = dict(
            water="volume_increment_pL",
            pool="energy_amount_increment_fmol",
            history="face_transferred",
        )[fault]
        values = np.array(getattr(point.state, key))
        values.flat[0] += 1e-3
        point = replace(point, state=point.state._replace(**{key: values}))
    with pytest.raises((ConfigError, NumericalError, ValueError)):
        bridge.capture_source(source, point)


@pytest.mark.parametrize("family", OWNERS)
@pytest.mark.parametrize("fault", ("capacity", "static", "phase", "policy", "seal", "coefficient"))
def test_phase_refuses_owner_rebase_and_false_reset_recipe(family, fault):
    raw = request(family)
    if fault == "capacity":
        raw["simulation"]["execution"]["capacity"] += 1
    elif fault == "static":
        raw["simulation"]["model"]["water_compartments"][0]["reference_volume_pL"] *= 1.01
    elif fault == "phase":
        raw["simulation"]["model"]["phase"] = "INIT"
    elif fault == "policy":
        raw["policies"]["coefficient_policy"] = "reset_all_history"
    elif fault == "seal":
        raw["source"]["identity"] = "bad"
    else:
        definition = deepcopy(prepared(family).definition)
        record = definition["model"]["handoff"]["coefficient_reset"]
        record["stateful_coefficient_buffer"] = True
        with pytest.raises(ConfigError):
            parse_spec(definition)
        return
    with pytest.raises((ConfigError, NumericalError, ValueError)):
        bridge.prepare(raw)


@pytest.mark.parametrize("family", OWNERS)
def test_phase_refuses_water_repair_owner_exchange(family):
    raw = request(family)
    other = "repair" if family == "water" else "water"
    raw["simulation"] = request(other)["simulation"]
    with pytest.raises(ConfigError):
        bridge.prepare(raw)
