"""Full56 joint owner: moving concentrations, actual pools and complete state."""

import ast
from pathlib import Path

import numpy as np
import pytest

from cells.core import surface_calcium_energy_water_hcn_extra_spec as schema
from cells.core.errors import NumericalError
from cells.core.specs import ConfigError
from cells.models import surface_calcium_energy as energy
from cells.models import surface_calcium_energy_water_hcn_extra as model
from cells.processes import hcn_extra_catalog as catalog
from tests.owned_joint_water_hcn_helpers import changed, evidence, initial, refinement, stage


@pytest.mark.parametrize(
    "arm",
    [
        "open",
        "blocked",
        "reordered",
        "empty",
        "instant_only",
        "dynamic_only",
        "sealed",
        "supply_off",
        "reverse",
        "absent",
        "leak_only",
        "camp_only",
    ],
)
def test_full_catalog_joint43_at_live_free_calcium_fuel_and_volume(arm):
    raw, spec, state, p, _ = initial("water", arm)
    assert len(state) == 43 and type(model.prior_layout(p)) is energy.HCN_EXTRA_LAYOUT_TYPE
    assert schema.energy_spec(spec).model.__class__.__name__ == "SurfaceCalciumEnergyHCNExtraModel"
    assert schema.parse(schema.to_dict(spec)) == spec
    records = []
    for y in (state, changed(spec, state, p, water_enabled=arm != "sealed")):
        before = [v.tobytes() for v in y]
        proof, value = stage("water", raw, spec, y, p, 0.0)
        assert before == [v.tobytes() for v in y]
        records.append(proof)
        arity = catalog.gate_active(p.channel_laws, xp=np) & p.channel_active
        assert np.all(value.derivative.channel_gate[~arity] == 0)
    if arm == "open":
        assert len(spec.model.channels) == 63 and set(p.channel_laws[p.channel_active]) == set(
            range(56)
        )
    evidence(
        "water-stages-" + arm,
        dict(
            inputs=raw,
            stages=records,
            manufactured_in_domain_state=True,
            complete_fields=43,
            live_volume_and_pools=True,
        ),
    )


def test_actual_fuel_and_volume_feed_every_pump_and_particle_count_once():
    _, spec, state, p, _ = initial("water")
    y = changed(spec, state, p)
    current = model.effective_layout(y, p)
    assert type(current) is energy.HCN_EXTRA_LAYOUT_TYPE
    actual = energy.stage_layout(model.prior_state(y), current, xp=np)
    amount = energy.energy_amounts(y, p)
    concentration = amount / current.volume
    for prefix, owners in (
        ("pump_", p.membrane_cell),
        ("pmca_", p.membrane_cell),
        ("er_pump_", np.arange(p.er_pump_present.size)),
    ):
        present = getattr(p, prefix + "present")
        for i, name in enumerate(("atp", "adp", "pi")):
            key = prefix + name + ("_mM" if prefix == "pump_" else "")
            np.testing.assert_array_equal(
                getattr(actual, key)[present], concentration[i, owners[present]]
            )
    particles = model.osmolyte_amounts(y, p)
    np.testing.assert_array_equal(particles[-3:, : p.active.size], amount)
    assert np.all(particles[-3:, p.active.size :] == 0)
    mask = p.cytosol_selector.astype(bool)
    np.testing.assert_array_equal(current.er_volume[~mask], p.er_volume[~mask])
    np.testing.assert_array_equal(current.er_volume[mask], current.volume[: len(p.er_volume)])
    evidence(
        "water-live-pools",
        dict(
            all_pump_families_actual_ATP_ADP_Pi=True,
            current_cytosol_volume=True,
            fixed_er_volume=True,
            neutral_fuel_particles_once=True,
        ),
    )


def test_sealed_water_is_exact_full56_finite_fuel_parent():
    _, spec, state, p, u = initial("water", "sealed")
    before, q = energy.initial_values(schema.energy_spec(spec))
    for a, b in zip(model.prior_state(state), before, strict=True):
        np.testing.assert_array_equal(a, b)
    for a, b in zip(model.prior_layout(p), q, strict=True):
        np.testing.assert_array_equal(a, b)
    actual = model.readouts(state, u, p, xp=np)
    expected = energy.readouts(before, model.base_control(u), q, xp=np)
    for a, b in zip(model.prior_state(actual.derivative), expected.derivative, strict=True):
        np.testing.assert_array_equal(a, b)
    for key in model.EXTRA_AXES:
        assert not np.any(getattr(actual.derivative, key))
    evidence(
        "water-sealed-exact", dict(full56_parent_rates_bitwise=True, no_volume_or_pool_work=True)
    )


@pytest.mark.parametrize("fault", ["fuel", "water", "instant-gate", "work", "chemical", "heat"])
def test_invalid_complete_owner_state_refuses_without_repair(fault):
    _, spec, state, p, u = initial("water")
    y = type(state)(*(v.copy() for v in state))
    if fault == "fuel":
        y.energy_amount_increment_fmol[0, 0] = -p.energy_initial_amount_fmol[0, 0]
    elif fault == "water":
        y.volume_increment_pL[0] = -p.volume[0]
    elif fault == "instant-gate":
        index = next(
            i for i, c in enumerate(spec.model.channels) if c.kinetic_law == "betse_hcn_leak_open@1"
        )
        y.channel_gate[0, index] = 0.1
    elif fault == "work":
        y.pool_volume_work_pJ[-1] = 1.0
    elif fault == "chemical":
        y.chemical_amount_increment[0, 0, int(p.er_er[0])] = (
            -2 * p.er_initial_amount[0, 0, int(p.er_er[0])] - 1
        )
    else:
        y.water_dissipated_energy_pJ[0] = -0.1
    blocked = type(u)(*(np.zeros_like(v) for v in u))
    with np.errstate(all="ignore"):
        assert not model.control_domain_valid(y, blocked, p, p.active, xp=np)
        with pytest.raises(NumericalError):
            model.check_values(y, spec)
    evidence("water-refusal-" + fault, dict(fault=fault, refused=True))


def test_complete_water_trajectory_at_all_observations_and_control_boundaries():
    refinement("water")


def test_new_reference_does_not_import_production_or_jax():
    from validation.tissue import calcium_energy_water_hcn_extra_reference as reference

    for node in ast.walk(ast.parse(Path(reference.__file__).read_text())):
        if isinstance(node, ast.ImportFrom):
            assert not (node.module or "").startswith(("cells", "jax"))
    evidence("water-reference-purity", dict(independent_complete_parent=True))


def test_legacy53_state_and_rates_match_the_unchanged_v1_family():
    from cells.core import surface_calcium_energy_water_spec as legacy_schema
    from cells.models import surface_calcium_energy_water as legacy
    from validation.tissue import calcium_energy_water_fixtures as legacy_inputs

    _, spec, state, p, u = initial("water", "legacy53")
    old = legacy_schema.parse(legacy_inputs.definition())
    old_state, q = legacy.initial_values(old)
    for a, b in zip(state, old_state, strict=True):
        np.testing.assert_array_equal(a, b)
    for a, b in zip(p, q, strict=True):
        np.testing.assert_array_equal(a, b)
    actual = model.rhs(state, u, p, p.active, xp=np)
    from tests.owned_joint_water_hcn_helpers import control

    expected = legacy.rhs(old_state, control(old, 0.0), q, q.active, xp=np)
    for a, b in zip(actual, expected, strict=True):
        np.testing.assert_array_equal(a, b)
    evidence(
        "water-legacy53-exact", dict(original_v1_unchanged=True, state_layout_rates_bitwise=True)
    )


def test_v1_does_not_silently_admit_the_new_hcn_laws():
    from cells.core import surface_calcium_energy_water_spec as legacy
    from validation.tissue import calcium_energy_water_hcn_extra_fixtures as inputs

    raw = inputs.definition()
    raw["model"]["id"] = "resolved_calcium_energy_water@1"
    raw["model"]["ionic"]["id"] = "resolved_tissue@11"
    with pytest.raises(ConfigError):
        legacy.parse(raw)
    evidence("water-v1-refusal", dict(complete_hcn_requires_explicit_v2=True))
