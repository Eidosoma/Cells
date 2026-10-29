"""Prescribed repair composes with all56 laws and actual moving-volume owners."""

import numpy as np
import pytest

from cells.core import surface_calcium_energy_water_repair_hcn_extra_spec as schema
from cells.core.errors import NumericalError
from cells.models import surface_calcium_energy_water_hcn_extra as parent
from cells.models import surface_calcium_energy_water_repair_hcn_extra as model
from tests.owned_joint_water_hcn_helpers import changed, evidence, initial, refinement, stage


@pytest.mark.parametrize(
    "arm",
    [
        "uninjured",
        "sham",
        "held",
        "resealing",
        "preinjured",
        "blocked",
        "reordered",
        "empty",
        "sealed",
        "supply_off",
        "leak_only",
        "camp_only",
    ],
)
def test_full48_repair_fields_at_initial_and_changed_live_owners(arm):
    raw, spec, state, p, _ = initial("repair", arm, time=7e-6)
    assert len(state) == 48 and schema.parse(schema.to_dict(spec)) == spec
    assert type(model.base_layout(p)) is parent.LAYOUT_TYPE
    if arm == "preinjured":
        assert len(spec.model.channels) == 63 and set(p.channel_laws[p.channel_active]) == set(
            range(56)
        )
    checks = []
    for y in (state, changed(spec, state, p, water_enabled=arm != "sealed")):
        before = [v.tobytes() for v in y]
        proof, value = stage("repair", raw, spec, y, p, 7e-6)
        assert before == [v.tobytes() for v in y]
        assert np.all(value.derivative.injury_dissipated_energy_pJ >= 0)
        checks.append(proof)
    evidence(
        "repair-stages-" + arm,
        dict(
            inputs=raw,
            stages=checks,
            manufactured_in_domain_state=True,
            complete_fields=48,
            live_volume_and_pools=True,
        ),
    )


def test_zero_damage_is_exact_parent_with_all56_laws():
    _, spec, state, p, u = initial("repair", "sham")
    y = changed(spec, state, p)
    y.damage[:] = 0
    y.damage_opened[:] = 0
    actual = model.readouts(y, u, p, xp=np)
    expected = parent.readouts(
        model.base_state(y), model.base_control(u), model.base_layout(p), xp=np
    )
    for a, b in zip(model.base_state(actual.derivative), expected.derivative, strict=True):
        np.testing.assert_array_equal(a, b)
    assert not np.any(actual.derivative.injury_transferred)
    evidence("repair-zero-exact", dict(full56_parent_rates_bitwise=True))


def test_injury_has_no_extra_fuel_debit_or_water_source():
    _, spec, state, p, u = initial("repair", "preinjured", time=7e-6)
    y = changed(spec, state, p)
    actual = model.readouts(y, u, p, xp=np)
    expected = parent.readouts(
        model.base_state(y), model.base_control(u), model.base_layout(p), xp=np
    )
    assert np.any(actual.derivative.injury_transferred)
    for key in ("energy_amount_increment_fmol", "volume_increment_pL", "pool_volume_work_pJ"):
        np.testing.assert_array_equal(
            getattr(actual.derivative, key), getattr(expected.derivative, key)
        )
    evidence(
        "repair-no-hidden-owners",
        dict(prescribed_damage=True, no_structural_ATP_or_volume_owner=True),
    )


@pytest.mark.parametrize("fault", ["damage", "ledger", "heat", "fuel", "water", "ca-route"])
def test_invalid_damage_and_parent_state_refuse_with_blocked_controls(fault):
    _, spec, state, p, u = initial("repair")
    y = type(state)(*(v.copy() for v in state))
    if fault == "damage":
        y.damage[0] = 1.1
    elif fault == "ledger":
        y.damage_opened[0] = 0.1
    elif fault == "heat":
        y.injury_dissipated_energy_pJ[0, 0] = -0.1
    elif fault == "fuel":
        y.energy_amount_increment_fmol[0, 0] = -p.energy_initial_amount_fmol[0, 0]
    elif fault == "water":
        y.volume_increment_pL[0] = -p.volume[0]
    else:
        y.injury_transferred[spec.model.species_ids.index("Ca"), 0] = 0.1
    blocked = type(u)(*(np.zeros_like(v) for v in u))
    with np.errstate(all="ignore"):
        assert not model.control_domain_valid(y, blocked, p, p.active, xp=np)
        with pytest.raises(NumericalError):
            model.check_values(y, spec)
    evidence("repair-refusal-" + fault, dict(fault=fault, refused=True))


def test_complete_repair_trajectory_at_every_observation_and_control_boundary():
    refinement("repair")


def test_legacy53_state_and_rates_match_the_unchanged_v1_repair():
    from cells.core import surface_calcium_energy_water_repair_spec as legacy_schema
    from cells.models import surface_calcium_energy_water_repair as legacy
    from tests.owned_joint_water_hcn_helpers import control
    from validation.tissue import calcium_energy_water_repair_fixtures as legacy_inputs

    _, spec, state, p, u = initial("repair", "legacy53")
    old = legacy_schema.parse(legacy_inputs.definition("preinjured"))
    old_state, q = legacy.initial_values(old)
    for a, b in zip(state, old_state, strict=True):
        np.testing.assert_array_equal(a, b)
    for a, b in zip(p, q, strict=True):
        np.testing.assert_array_equal(a, b)
    actual = model.rhs(state, u, p, p.active, xp=np)
    expected = legacy.rhs(old_state, control(old, 0.0), q, q.active, xp=np)
    for a, b in zip(actual, expected, strict=True):
        np.testing.assert_array_equal(a, b)
    evidence(
        "repair-legacy53-exact", dict(original_v1_unchanged=True, state_layout_rates_bitwise=True)
    )
