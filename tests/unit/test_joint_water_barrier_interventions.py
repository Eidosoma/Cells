"""Independent complete stages and software contracts; no full-history claim."""

import ast
import json
import os
from copy import deepcopy
from dataclasses import replace
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from cells.core.errors import NumericalError
from cells.core.grid import EventGrid
from cells.core.schedule import control_values
from cells.core.specs import ConfigError
from cells.models import surface_calcium_energy as fuel
from cells.models import surface_calcium_energy_water_hcn_extra as water_parent
from cells.models import surface_calcium_energy_water_repair_hcn_extra as repair_parent
from tests.joint_water_barrier_fixtures import components, definition
from tests.owned_joint_water_hcn_helpers import changed
from validation.transport import joint_water_barrier_interventions_fixtures as fixtures
from validation.transport import joint_water_barrier_interventions_reference as reference

PARENTS = {"water": water_parent, "repair": repair_parent}
CLOCKS = (0.0, 10e-6, 20e-6, 30e-6, 50e-6)


def evidence(name, report, arrays=None):
    if folder := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        root = Path(folder) / "joint-water-barrier-interventions"
        root.mkdir(parents=True, exist_ok=True)
        if arrays is not None:
            np.savez_compressed(root / (name + ".npz"), **arrays)
        (root / (name + ".json")).write_text(
            json.dumps(
                dict(status="passed", **report),
                indent=2,
                allow_nan=False,
                default=lambda value: np.asarray(value).tolist(),
            )
            + "\n"
        )


@lru_cache
def initialized(family="water", case="partial", permuted=False, padded=True):
    raw = definition(family, case, permuted=permuted, padded=padded)
    schema, model = components(family)
    spec = schema.parse(raw)
    state, layout = model.initial_values(spec)
    return schema.to_dict(spec), spec, state, layout


def control(spec, time):
    table = control_values(spec, [time])
    return type(table)(*(v[0] for v in table))


def rate_budget(context, target):
    process = context["process"]
    floors = {
        key: np.full(shape, 3e-23 if key.endswith("_C") else 3e-12)
        for key, shape in context["parent"]["shapes"].items()
    }
    return np.r_[process.flatten(context["parent"], floors), 3e-12] + 3e-10 * np.abs(target)


def stage(raw, spec, state, layout, family, time):
    _, model = components(family)
    context = reference.bind(raw)
    state = state._replace(phase_clock_s=np.asarray([time]))
    before = [v.tobytes() for v in state]
    flat = reference.flatten(context, state._asdict())
    target, phi, proof = reference.evaluate(context, flat, time)
    value = model.readouts(state, control(spec, time), layout, xp=np)
    actual = reference.flatten(context, value.derivative._asdict())
    budget = rate_budget(context, target)
    ratio = float(np.max(np.abs(actual - target) / budget, initial=0))
    assert ratio <= 1, ratio
    n = layout.active.size
    observed_phi = np.r_[
        value.field.potential_V[:n][layout.active],
        value.field.potential_V[n:][layout.outside_active],
    ]
    np.testing.assert_allclose(observed_phi, phi, rtol=3e-10, atol=3e-13)
    assert value.valid and abs(value.field.energy_balance_pJ_s) < 1e-10
    assert proof["max_charge_residual_C"] <= 3e-25
    assert proof["max_component_current_residual_A"] <= 1e-23
    assert abs(proof["physical_energy_balance_pJ_s"]) < 1e-10
    assert before == [v.tobytes() for v in state]
    np.testing.assert_array_equal(value.derivative.phase_clock_s, [1.0])
    return dict(
        time_s=time,
        error_over_budget=ratio,
        independent=proof,
        production_energy_residual_pJ_s=float(value.field.energy_balance_pJ_s),
    ), dict(
        actual=actual,
        reference=target,
        budget=budget,
        potential=observed_phi,
        reference_potential=phi,
        state=flat,
    )


@pytest.mark.parametrize("family", fixtures.FAMILIES)
@pytest.mark.parametrize("case", fixtures.CASES)
def test_complete_owners_initial_and_live_manufactured_event_stages(family, case):
    permuted = case in ("duplicate", "asymmetric_modulators")
    raw, spec, initial, p = initialized(family, case, permuted)
    schema, model = components(family)
    parent = PARENTS[family]
    ordinary = schema.owner_spec(spec)
    original, q = parent.initial_values(ordinary)
    assert len(initial) == (44 if family == "water" else 49)
    assert type(model.parent_layout(p)) is parent.LAYOUT_TYPE
    assert len(spec.model.channels) == 63
    assert set(p.channel_laws[p.channel_active]) == set(range(56))
    for a, b in zip(model.parent_state(initial), original, strict=True):
        assert a.dtype == b.dtype and a.shape == b.shape and a.tobytes() == b.tobytes()
    for a, b in zip(model.parent_layout(p), q, strict=True):
        np.testing.assert_array_equal(a, b)
    records, arrays = [], {}
    for label, y in (("initial", initial), ("manufactured", changed(spec, initial, p))):
        for index, time in enumerate(CLOCKS):
            proof, values = stage(raw, spec, y, p, family, time)
            records.append(dict(label=label, **proof))
            arrays.update({f"{label}_{index}__" + k: v for k, v in values.items()})
    evidence(
        "stages-" + family + "-" + case,
        dict(
            inputs=raw,
            complete_physical_fields=len(initial) - 1,
            complete_state_fields=len(initial),
            comparisons=records,
            manufactured_not_evolved=True,
            padded=True,
            permuted=permuted,
            original_owners_and_parameters_exact=True,
            independent_biological_cases=0,
        ),
        arrays,
    )


@pytest.mark.parametrize("family", fixtures.FAMILIES)
@pytest.mark.parametrize("case", ("INIT", "none", "zeroamp"))
def test_disabled_events_are_bitwise_complete_parent(family, case):
    _, spec, initial, p = initialized(family, case)
    _, model = components(family)
    y = changed(spec, initial, p)._replace(phase_clock_s=np.asarray([20e-6]))
    u = control(spec, 20e-6)
    actual = model.rhs(y, u, p, p.active, xp=np)
    expected = PARENTS[family].rhs(
        model.parent_state(y), u, model.parent_layout(p), p.active, xp=np
    )
    for a, b in zip(model.parent_state(actual), expected, strict=True):
        np.testing.assert_array_equal(a, b)
    np.testing.assert_array_equal(actual.phase_clock_s, [1.0])
    evidence("inactive-" + family + "-" + case, dict(parent_all_rates_bitwise=True))


@pytest.mark.parametrize("family", fixtures.FAMILIES)
def test_duplicate_and_permuted_occurrences_preserve_same_coefficients(family):
    raw, spec, state, p = initialized(family, "partial")
    other_raw, other_spec, _, q = initialized(family, "duplicate", True)
    _, model = components(family)
    species = [other_spec.model.species_ids.index(s) for s in spec.model.species_ids]
    grids = [
        value["model"]["barrier_preparation"]["provenance"]["request"]["grid"]
        for value in (raw, other_raw)
    ]
    sites = [grids[1]["site_ids"].index(s) for s in grids[0]["site_ids"]]
    face_ids = [row.id for row in other_spec.model.faces]
    faces = [face_ids.index(row.id) for row in spec.model.faces]
    for time in CLOCKS:
        y = state._replace(phase_clock_s=np.asarray([time]))
        a, b = model.signal_values(y, p, xp=np), model.signal_values(y, q, xp=np)
        np.testing.assert_array_equal(
            a.site_diffusivity, b.site_diffusivity[np.ix_(species, sites)]
        )
        for key in ("face_diffusivity", "face_factor"):
            np.testing.assert_array_equal(
                getattr(a, key)[:, : len(faces)], getattr(b, key)[np.ix_(species, faces)]
            )
            assert not np.any(getattr(a, key)[:, len(faces) :])
            assert not np.any(getattr(b, key)[:, len(faces) :])
        np.testing.assert_array_equal(a.sodium_weight, b.sodium_weight[sites])
        np.testing.assert_array_equal(a.pulse, b.pulse)
        np.testing.assert_array_equal(a.valid, b.valid)
    evidence(
        "duplicate-" + family,
        dict(
            duplicate_assignment_not_additive=True,
            permuted_owner_and_target_axes=True,
            padded_targets=True,
        ),
    )


@pytest.mark.parametrize("family", fixtures.FAMILIES)
def test_live_volume_feeds_all_pumps_fuel_osmolytes_and_fixed_er_once(family):
    raw, spec, state, p = initialized(family)
    _, model = components(family)
    y = changed(spec, state, p)._replace(phase_clock_s=np.asarray([20e-6]))
    signal = model.signal_values(y, p, xp=np)
    current = model.parent_layout(p)._replace(face_factor=signal.face_factor)
    complete_water = model.water_layout(current)
    physical = water_parent.effective_layout(y, complete_water)
    stage_layout = fuel.stage_layout(water_parent.prior_state(y), physical, xp=np)
    amount = fuel.energy_amounts(y, p)
    concentration = amount / stage_layout.volume
    for prefix, owners in (
        ("pump_", p.membrane_cell),
        ("pmca_", p.membrane_cell),
        ("er_pump_", np.arange(p.er_pump_present.size)),
    ):
        present = getattr(p, prefix + "present")
        for i, name in enumerate(("atp", "adp", "pi")):
            key = prefix + name + ("_mM" if prefix == "pump_" else "")
            np.testing.assert_array_equal(
                getattr(stage_layout, key)[present], concentration[i, owners[present]]
            )
    particles = water_parent.osmolyte_amounts(y, complete_water)
    np.testing.assert_array_equal(particles[-3:, : p.active.size], amount)
    assert not np.any(particles[-3:, p.active.size :])
    mask = p.cytosol_selector.astype(bool)
    np.testing.assert_array_equal(stage_layout.er_volume[~mask], p.er_volume[~mask])
    np.testing.assert_array_equal(
        stage_layout.er_volume[mask],
        np.broadcast_to(stage_layout.volume[: mask.shape[0], None], mask.shape)[mask],
    )
    proof, _ = stage(raw, spec, y, p, family, 20e-6)
    evidence(
        "live-owners-" + family,
        dict(
            current_volume_all_three_pumps=True,
            no_duplicate_fuel_particles=True,
            fixed_er=True,
            proof=proof,
        ),
    )


@pytest.mark.parametrize("family", fixtures.FAMILIES)
def test_closed_na_faces_retain_actual_histories_and_observer_accounting(family):
    raw, spec, state, p = initialized(family, "close-reopen")
    _, model = components(family)
    time = spec.experiment.end_time
    y = type(state)(*(np.array(v, copy=True) for v in state))
    y = y._replace(phase_clock_s=np.asarray([time]))
    signal = model.signal_values(y, p, xp=np)
    accounting = model.accounting_layout(p, xp=np)
    na = spec.model.species_ids.index("Na")
    closed = (signal.face_factor[na] == 0) & (accounting.face_factor[na] > 0)
    assert np.any(closed)
    i = int(np.flatnonzero(closed)[0])
    moved = 1e-14
    y.face_transferred[na, i] = moved
    y.extracellular_amount_increment[na, p.face_sender[i]] -= moved
    y.extracellular_amount_increment[na, p.face_receiver[i]] += moved
    y.face_dissipated_energy_pJ[i] = 1e-14
    before = [v.tobytes() for v in y]
    assert model.domain_valid(y, p, p.active, xp=np)
    proof, _ = stage(raw, spec, y, p, family, time)
    history = type(y)(*(v[None] for v in y))
    obs = model.observe_history(np.asarray([time]), history, p, np.asarray([time]), spec)
    for key in y._fields:
        np.testing.assert_array_equal(getattr(obs, key)[0], getattr(y, key))
    balance = PARENTS[family].balances(model.parent_state(y), accounting)
    np.testing.assert_array_equal(obs.energy_balance_pJ[0], np.atleast_1d(balance["energy"]))
    np.testing.assert_array_equal(obs.pool_internal_transfer_balance_pJ[0], balance["pool_energy"])
    assert before == [v.tobytes() for v in y]
    # Other charged species retain actual field-return conductance.
    others = np.arange(len(spec.model.species_ids)) != na
    assert np.all(np.sum(signal.face_factor[others, : len(spec.model.faces)], axis=0) > 0)
    evidence(
        "closed-history-" + family,
        dict(
            inputs=raw,
            manufactured_history_not_trajectory=True,
            closed_na_face_id=spec.model.faces[i].id,
            retained_transfer_fmol=moved,
            all_state_observables_exact=True,
            actual_energy_work_accounting=True,
            proof=proof,
        ),
        {"state__" + k: v for k, v in y._asdict().items()}
        | {"observation__" + k: np.asarray(v) for k, v in vars(obs).items()},
    )


@pytest.mark.parametrize("family", fixtures.FAMILIES)
@pytest.mark.parametrize(
    "fault",
    (
        "water",
        "fuel",
        "store",
        "phase-policy",
        "wrong-parent",
        "negative-amplitude",
        "overshoot-amplitude",
        "target-capacity",
    ),
)
def test_definition_cannot_change_physical_owner_or_native_contract(family, fault):
    raw, _, _, _ = initialized(family)
    schema, _ = components(family)
    value = deepcopy(raw)
    m = value["model"]
    if fault == "water":
        m["water_compartments"][0]["reference_volume_pL"] *= 0.9
    elif fault == "fuel":
        m["energy_pools"][0]["initial_amount_fmol"]["ATP"] *= 0.9
    elif fault == "store":
        m["stores"][0]["model"]["compartments"][0]["volume_pL"] *= 0.9
    elif fault == "phase-policy":
        m["timing_policy"] = "external_clock"
    elif fault == "wrong-parent":
        m["barrier_preparation"]["definition"]["model"]["id"] = "resolved_calcium_energy_water@1"
    elif fault == "target-capacity":
        value["execution"]["barrier_target_capacity"] = 1
    else:
        m["intervention"]["amplitude"] = -0.1 if fault == "negative-amplitude" else 1.1
    with pytest.raises((ValueError, KeyError)):
        reference.bind(value)
    with pytest.raises(ConfigError):
        schema.parse(value)
    evidence("definition-refusal-" + family + "-" + fault, dict(fault=fault, refused_by_both=True))


@pytest.mark.parametrize("family", fixtures.FAMILIES)
@pytest.mark.parametrize(
    "fault",
    ("negative-clock", "clock-nan", "clock-end", "volume", "fuel", "padding", "negative-face-heat"),
)
def test_invalid_actual_states_cannot_be_hidden_by_barrier_phase(family, fault):
    _, spec, state, p = initialized(family, "INIT")
    _, model = components(family)
    y = type(state)(*(np.array(v, copy=True) for v in state))
    if fault in ("negative-clock", "clock-nan", "clock-end"):
        y.phase_clock_s[0] = {"negative-clock": -1e-9, "clock-nan": np.nan, "clock-end": 1e-3}[
            fault
        ]
    elif fault == "volume":
        y.volume_increment_pL[0] = -p.volume[0]
    elif fault == "fuel":
        y.energy_amount_increment_fmol[0, 0] = -p.energy_initial_amount_fmol[0, 0]
    elif fault == "padding":
        y.volume_increment_pL[-1] = 1e-3
    else:
        y.face_dissipated_energy_pJ[0] = -0.1
    before = [v.tobytes() for v in y]
    with np.errstate(all="ignore"):
        assert not model.control_domain_valid(y, control(spec, 0), p, p.active, xp=np)
        with pytest.raises(NumericalError):
            model.check_values(y, spec)
    assert before == [v.tobytes() for v in y]
    evidence("state-refusal-" + family + "-" + fault, dict(fault=fault, refused=True))


@pytest.mark.parametrize("family", fixtures.FAMILIES)
def test_phase_clock_and_native_ramp_admission_remain_explicit(family):
    raw, spec, state, p = initialized(family)
    _, model = components(family)
    model.check_checkpoint(spec, SimpleNamespace(state=state, time=0.0))
    with pytest.raises(ConfigError):
        model.check_checkpoint(spec, SimpleNamespace(state=state, time=10e-6))
    context = reference.bind(raw)
    with pytest.raises(ValueError, match="clock"):
        reference.evaluate(context, reference.initial(context), 10e-6)
    times = np.asarray(list(EventGrid(spec)))
    model.check_steps(spec, np.diff(times), control_values(spec, times[:-1]))
    unresolved = replace(spec, execution=replace(spec.execution, dt=0.6e-6))
    with pytest.raises(ConfigError):
        model.check_steps(unresolved, np.asarray([0.6e-6]), control_values(unresolved, [0.0]))
    altered = deepcopy(raw)
    altered["execution"]["dt"] = 0.6e-6
    with pytest.raises(ValueError, match="transition"):
        reference.bind(altered)
    evidence(
        "clock-ramp-" + family,
        dict(
            clock_mismatch_refused=True,
            ramp_underresolution_refused=True,
            parent_admissions_preserved=True,
        ),
    )


@pytest.mark.parametrize("family", fixtures.FAMILIES)
def test_phase_clock_tolerance_uses_physical_horizon_without_one_second_floor(family):
    raw, spec, state, p = initialized(family)
    _, model = components(family)
    context = reference.bind(raw)
    bound = 64 * np.finfo(float).eps * max(spec.experiment.end_time, spec.execution.dt)
    assert context["phase_clock_atol_s"] == bound == p.phase_clock_atol_s
    clock = 20e-6
    y = state._replace(phase_clock_s=np.asarray([clock]))
    flat = reference.flatten(context, y._asdict())
    within, outside = clock + 0.5 * bound, clock + 8 * bound
    assert 0 < within - clock <= bound < outside - clock < 64 * np.finfo(float).eps
    reference.current_definition(context, flat, within)
    model.check_checkpoint(spec, SimpleNamespace(state=y, time=within))
    with pytest.raises(ValueError, match="clock"):
        reference.current_definition(context, flat, outside)
    with pytest.raises(ConfigError):
        model.check_checkpoint(spec, SimpleNamespace(state=y, time=outside))
    evidence(
        "clock-scale-" + family,
        dict(
            phase_clock_atol_s=bound,
            accepted_difference_s=within - clock,
            refused_difference_s=outside - clock,
            former_one_second_floor_s=64 * np.finfo(float).eps,
            refusal_by_reference_and_production=True,
            manufactured_clock_software_scope=True,
        ),
    )


def test_new_independent_oracle_has_no_production_imports():
    tree = ast.parse(Path(reference.__file__).read_text())
    for node in ast.walk(tree):
        names = (
            [row.name for row in node.names]
            if isinstance(node, ast.Import)
            else [node.module or ""]
            if isinstance(node, ast.ImportFrom)
            else []
        )
        assert not any(name.split(".")[0] in ("cells", "jax") for name in names)
    evidence(
        "oracle-source",
        dict(
            no_production_or_accelerator_imports=True,
            equations="Frozen full56 water/repair and Decimal ECM coefficients",
        ),
    )
