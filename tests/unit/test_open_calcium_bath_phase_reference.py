"""Independent complete epoch stages and explicit original-anchor source budgets."""

import json
import os
from pathlib import Path

import numpy as np
import pytest

from cells.core.schedule import control_values
from cells.core.specs import ConfigError
from cells.numerics.fixed_step import rk4_step
from tests.unit.test_open_calcium_bath_phase_handoff import setup
from validation.topology import open_calcium_bath_phase_fixtures as fixtures
from validation.topology import open_calcium_bath_phase_handoff_reference as reference


def evidence(name, record, arrays=None):
    if directory := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        folder = Path(directory) / "open-calcium-bath-phase"
        folder.mkdir(parents=True, exist_ok=True)
        if arrays is not None:
            np.savez_compressed(folder / (name + ".npz"), **arrays)
        (folder / (name + ".json")).write_text(
            json.dumps(
                record, indent=2, allow_nan=False, default=lambda value: np.asarray(value).tolist()
            )
            + "\n"
        )


def control(schema, spec, time):
    ordinary = schema.scheduled_spec(spec)
    table = control_values(schema.scheduled.owner_spec(ordinary), [time])
    return type(table)(*(v[0] for v in table))


def assert_conservation(proof):
    for key in (
        "local_material_fmol",
        "outside_material_fmol",
        "chemical_ledger_fmol",
        "ionic_ownership_fmol",
        "nonionic_moiety_fmol",
        "ionic_global_fmol",
    ):
        np.testing.assert_allclose(proof[key], 0.0, rtol=0, atol=3e-14, err_msg=key)
    for key in ("capacitor_charge_C", "electrode_charge_C", "global_charge_C"):
        np.testing.assert_allclose(proof[key], 0.0, rtol=0, atol=3e-25, err_msg=key)
    for key in (
        "energy_residual_pJ",
        "reservoir_work_pJ",
        "electrode_work_pJ",
        "pool_energy_pJ",
        "program_energy_pJ",
    ):
        np.testing.assert_allclose(proof[key], 0.0, rtol=0, atol=1e-10, err_msg=key)
    for key in ("pool_material_fmol", "adenylate_fmol", "phosphorus_fmol"):
        np.testing.assert_allclose(proof[key], 0.0, rtol=0, atol=2e-12, err_msg=key)


@pytest.mark.parametrize("family", fixtures.FAMILIES)
@pytest.mark.parametrize("case", ("changed", "empty"))
def test_full_control_and_bath_clock_stages_from_exact_carried_state(family, case):
    _, schema, model, count, prepared, spec, state, p = setup(family, case)
    c, vector = reference.verify_epoch(prepared.definition)
    np.testing.assert_array_equal(reference.flatten(c, state._asdict()), vector)
    clocks = {0.0, spec.experiment.end_time, *(v.time for v in spec.experiment.changes)}
    for event in spec.model.bath_events:
        clocks.update((event.on_s, (event.on_s + event.off_s) / 2, event.off_s))
    arrays, records = {}, []
    for i, time in enumerate(sorted(clocks)):
        trial = state._replace(phase_clock_s=np.asarray([time]))
        independent = vector.copy()
        independent[-1] = time
        target, phi, proof = reference.evaluate(c, independent, held_time=time)
        u = control(schema, spec, time)
        result = model.rhs(trial, u, p, p.active, xp=np)
        actual = reference.flatten(c, result._asdict())
        budget = reference.flatten(
            c,
            {
                key: np.full(shape, 3e-23 if key.endswith("_C") else 3e-12)
                for key, shape in c["shapes"].items()
            },
        ) + 3e-10 * np.abs(target)
        ratio = float(np.max(np.abs(actual - target) / budget, initial=0))
        field = model.field_values(trial, u, p, xp=np)
        potential = np.r_[
            field.potential_V[: p.active.size][p.active],
            field.potential_V[p.active.size :][p.outside_active],
        ]
        records.append(
            dict(
                time_s=time,
                error_over_budget=ratio,
                independent=proof,
                transport_energy_residual_pJ_s=float(field.energy_balance_pJ_s),
            )
        )
        arrays.update(
            {
                str(i) + "-" + key: value
                for key, value in dict(
                    state=independent,
                    actual=actual,
                    reference=target,
                    budget=budget,
                    potential_V=potential,
                    independent_potential_V=phi,
                ).items()
            }
        )
        evidence(
            "stages-" + family + "-" + case,
            dict(
                definition=prepared.definition,
                complete_fields=count,
                stages=records,
                scope="one accepted INIT step carried to SIM; independent clock/control probes",
            ),
            arrays,
        )
        assert type(result) is model.STATE_TYPE
        assert ratio <= 1
        assert field.converged
        assert abs(field.energy_balance_pJ_s) <= 1e-10
        np.testing.assert_allclose(potential, phi, rtol=3e-10, atol=3e-13)
        for key in state._fields:
            np.testing.assert_array_equal(getattr(result, key)[~c["active_masks"][key]], 0)
        np.testing.assert_array_equal(result.phase_clock_s, [1.0])


@pytest.mark.parametrize("family", fixtures.FAMILIES)
@pytest.mark.parametrize("case", fixtures.CASES)
def test_all_original_histories_plus_only_declared_initial_dose_work_and_charge(family, case):
    _, _, model, _, prepared, spec, state, p = setup(family, case)
    request = fixtures.request(family, case)
    c, vector = reference.initial(request)
    before = reference.scheduled.conservation(
        c["source_context"], reference.flatten(c["source_context"], c["source_arrays"])
    )
    after = reference.conservation(c, vector)
    assert_conservation(before)
    assert_conservation(after)
    op = reference.operation(c)
    np.testing.assert_allclose(
        after["chemical_change_pJ"] - before["chemical_change_pJ"],
        op["chemical_work_pJ"].sum(),
        rtol=5e-13,
        atol=3e-12,
    )
    np.testing.assert_allclose(
        after["external_work_pJ"] - before["external_work_pJ"],
        op["chemical_work_pJ"].sum(),
        rtol=5e-13,
        atol=3e-12,
    )
    for key in (
        "plasma_capacitor_change_pJ",
        "er_capacitor_change_pJ",
        "pool_energy_pJ",
        "pool_material_fmol",
        "adenylate_fmol",
        "phosphorus_fmol",
    ):
        np.testing.assert_array_equal(after[key], before[key])
    np.testing.assert_array_equal(after["dissipated_energy_pJ"], before["dissipated_energy_pJ"])
    model.check_values(state, spec)
    assert prepared.provenance["clocks"]["init_checkpoint_time_s"] > 0
    assert prepared.provenance["clocks"]["sim_epoch_time_s"] == 0
    for key in state._fields:
        np.testing.assert_array_equal(getattr(state, key), c["carried_arrays"][key], err_msg=key)
    evidence(
        "accounting-" + family + "-" + case,
        dict(
            before=before,
            after=after,
            operation=op,
            provenance=prepared.provenance,
            scope=(
                "original anchors; carried work plus a separate reversible "
                "SIM composition operation"
            ),
        ),
        {key: value for key, value in c["carried_arrays"].items()},
    )
    # Frozen carried histories with later controller clocks are stage probes,
    # not a claim that the tissue followed a full bath trajectory.
    for time in (2.5e-6, spec.experiment.end_time):
        probe = state._replace(phase_clock_s=np.asarray([time]))
        model.check_values(probe, spec)
        assert_conservation(reference.conservation(c, reference.flatten(c, probe._asdict())))


@pytest.mark.parametrize("family", fixtures.FAMILIES)
@pytest.mark.parametrize("case", ("changed", "empty"))
def test_observer_archives_both_clocks_and_exposes_continuous_physical_histories(family, case):
    _, _, model, _, prepared, spec, state, p = setup(family, case)
    history = model.STATE_TYPE(*(v[None] for v in state))
    observed = model.observe_history(np.asarray([0.0]), history, p, [0.0], spec)
    clocks = prepared.provenance["clocks"]
    np.testing.assert_array_equal(observed.init_phase_clock_s, [[clocks["init_phase_clock_s"]]])
    np.testing.assert_array_equal(observed.elapsed_time_s, [[clocks["init_checkpoint_time_s"]]])
    np.testing.assert_array_equal(observed.phase_clock_s, [[0.0]])
    np.testing.assert_array_equal(
        observed.reservoir_chemical_work_pJ[0], state.reservoir_chemical_work_pJ
    )
    physical = model.physical_state(state, p, xp=np)
    for key in (
        "reservoir_supplied",
        "electrode_charge_transferred_C",
        "reservoir_work_pJ",
        "electrode_work_pJ",
    ):
        np.testing.assert_array_equal(
            getattr(observed, "physical_" + key)[0], getattr(physical, key)
        )
    model.check_checkpoint(spec, type("Point", (), dict(state=state, time=0.0))())
    with pytest.raises(ConfigError, match="checkpoint time"):
        model.check_checkpoint(
            spec, type("Point", (), dict(state=state, time=clocks["init_checkpoint_time_s"]))()
        )


@pytest.mark.parametrize("family", fixtures.FAMILIES)
def test_empty_controller_retains_all_parent_work_instead_of_starting_over(family):
    _, _, model, _, prepared, spec, state, p = setup(family, "empty")
    source, point = fixtures.source_checkpoint(family)
    assert source.model.phase == "INIT"
    before = model.scheduled.physical_state(point.state, point.layout, xp=np)
    after = model.physical_state(state, p, xp=np)
    for key in after._fields:
        np.testing.assert_array_equal(getattr(after, key), getattr(before, key), err_msg=key)
    assert np.any(state.reservoir_work_pJ != 0)
    assert np.any(state.reservoir_chemical_work_pJ != 0)
    summary = model.summarize(
        model.STATE_TYPE(*(v[None] for v in state)), model.check_values(state, spec), spec
    )
    assert summary["model"] == prepared.definition["model"]["id"]
    assert summary["initial_controller_operation"] == prepared.provenance["controller_operation"]


def test_independent_epoch_reference_closure_includes_actual_bath_and_56law_helpers():
    root = Path(os.environ.get("CELLS_COMPONENT_SOURCE_ROOT", Path(__file__).resolve().parents[2]))
    manifest = reference.dependency_manifest(root)
    assert {
        "validation/topology/open_calcium_bath_phase_handoff_reference.py",
        "validation/tissue/open_calcium_bath_reference.py",
        "validation/tissue/open_calcium_reference.py",
        "validation/chemistry/finite_energy_reference.py",
        "validation/transport/surface_bath_events_reference.py",
        "validation/tissue/surface_kinetic_reference.py",
        "validation/tissue/surface_dynamics_reference.py",
    } <= set(manifest)
    assert all(
        name.startswith("validation/")
        or name == "tests/__init__.py"
        or Path(name).parent == Path("tests")
        and Path(name).name.startswith("reference_")
        for name in manifest
    )
    evidence("dependency-closure", dict(sources=manifest, production_imports=False))


def test_actual_carried_pool_bound_all_controls_and_corners_and_isolated_step_boundary():
    """Guard-only boundary probe; the full8us recipes and every other guard stay fixed."""
    _, _, model, _, prepared, spec, state, p = setup("energy")
    context, vector = reference.verify_epoch(prepared.definition)
    actual = model.carried_pool_turnover_bound(spec)
    independent = reference.admission(context, vector, 0.0)
    current = (
        p.energy_initial_amount_fmol[:, p.active] + state.energy_amount_increment_fmol[:, p.active]
    )
    np.testing.assert_array_equal(actual["carried_amount_fmol"], current)
    np.testing.assert_allclose(
        actual["maximum_fraction_rate_s_inv"],
        independent["maximum_fraction_rate_s_inv"],
        rtol=3e-10,
        atol=3e-12,
    )
    assert actual["corners"] == 8 and actual["held_control_states"] == len(spec.experiment.changes)
    assert np.any(np.asarray(actual["carried_increment_fmol"]) != 0)
    boundary = 0.05 / actual["maximum_fraction_rate_s_inv"]
    model.check_carried_pool_turnover(spec, boundary * (1 - 1e-6))
    with pytest.raises(ConfigError, match="actual carried"):
        model.check_carried_pool_turnover(spec, boundary * (1 + 1e-6))
    reference.admission(context, vector, boundary * (1 - 1e-6))
    with pytest.raises(ValueError, match="actual carried"):
        reference.admission(context, vector, boundary * (1 + 1e-6))
    for step in (float("nan"), float("inf"), -1e-9):
        with pytest.raises(ConfigError):
            model.check_carried_pool_turnover(spec, step)
    evidence(
        "actual-carried-pool-envelope",
        dict(
            definition=prepared.definition,
            production=actual,
            independent=independent,
            isolated_guard_boundary_s=boundary,
            scope=(
                "actual full carried state and all corners/controls; isolated guard boundary only"
            ),
            production_guard_bypasses=[],
            full_recipe_duration_s=spec.experiment.end_time,
        ),
        {key: np.asarray(value) for key, value in state._asdict().items()},
    )


@pytest.mark.parametrize("family", fixtures.FAMILIES)
def test_real_sim_prefix_keeps_full_source_and_bath_energy_histories(family):
    _, schema, model, count, prepared, spec, state, p = setup(family)
    u = control(schema, spec, 0.0)
    evolved = rk4_step(lambda y, *args: model.rhs(y, *args, xp=np), state, 1e-9, u, p, p.active)
    assert len(evolved) == count
    model.check_values(evolved, spec)
    context, _ = reference.verify_epoch(prepared.definition)
    proof = reference.conservation(context, reference.flatten(context, evolved._asdict()))
    assert_conservation(proof)
    assert np.any(evolved.chemical_amount_increment != state.chemical_amount_increment)
    if family == "energy":
        assert np.any(evolved.energy_amount_increment_fmol != state.energy_amount_increment_fmol)
    history = model.STATE_TYPE(*(np.stack((a, b)) for a, b in zip(state, evolved, strict=True)))
    observed = model.observe_history(np.asarray([0.0, 1e-9]), history, p, [0.0, 1e-9], spec)
    for key in model.scheduled.STATE_TYPE._fields:
        np.testing.assert_array_equal(getattr(observed, key)[1], getattr(evolved, key))
    np.testing.assert_allclose(
        observed.elapsed_time_s[1],
        prepared.provenance["clocks"]["init_checkpoint_time_s"] + 1e-9,
        rtol=0,
        atol=1e-20,
    )
    evidence(
        "continuous-source-and-sim-prefix-" + family,
        dict(
            definition=prepared.definition,
            independent=proof,
            scope="one INIT step +actual1ns SIM prefix",
        ),
        {key: np.asarray(value) for key, value in evolved._asdict().items()},
    )


@pytest.mark.parametrize("family", fixtures.FAMILIES)
def test_carried_ionic_envelope_matches_independent_actual_full_state(family):
    from cells.models.open_calcium_bath_epoch import validate_carried_envelope

    _, _, model, _, prepared, spec, state, p = setup(family)
    context, vector = reference.verify_epoch(prepared.definition)
    actual = validate_carried_envelope(model.scheduled, state, p)
    independent = reference.admission(context, vector, 0.0)
    np.testing.assert_allclose(
        actual, independent["ionic_moiety_upper_fmol"], rtol=3e-13, atol=3e-12
    )
    k = spec.model.species_ids.index("K")
    dose = np.sum(np.maximum(p.bath_amount_coefficient_fmol, 0.0), axis=(0, 2))
    limits = p.open_ionic_moiety_ceiling_fmol.copy()
    limits[k] = actual[k] - 0.25 * dose[k]
    narrow = p._replace(open_ionic_moiety_ceiling_fmol=limits)
    assert model.domain_valid(state, narrow, p.active, xp=np)
    with pytest.raises(ConfigError, match="Actual carried ions"):
        validate_carried_envelope(model.scheduled, state, narrow)
    evidence(
        "actual-carried-ionic-envelope-" + family,
        dict(
            definition=prepared.definition,
            production=actual,
            independent=independent["ionic_moiety_upper_fmol"],
            scope="isolated hard-domain envelope probe; original full8us input/caps unchanged",
        ),
    )


@pytest.mark.parametrize("family", fixtures.FAMILIES)
def test_empty_sim_two_steps_reduce_exactly_to_static_owner_from_actual_carried_history(family):
    _, schema, model, _, prepared, spec, state, p = setup(family, "empty")
    base = model.scheduled.base
    target = schema.scheduled.owner_spec(schema.scheduled_spec(spec))
    original, layout = model.parent_state(state), model.parent_layout(p)
    u = control(schema, spec, 0.0)
    for step in range(2):
        actual = model.rhs(state, u, p, p.active, xp=np)
        expected = base.rhs(original, u, layout, layout.active, xp=np)
        evidence(
            "empty-static-reduction-" + family,
            dict(
                definition=prepared.definition,
                prefix_step=step,
                scope="two local SIM RK4 steps from actual full INIT history",
            ),
            {"actual-" + key: getattr(actual, key) for key in original._fields}
            | {"expected-" + key: getattr(expected, key) for key in original._fields},
        )
        for key in original._fields:
            np.testing.assert_array_equal(getattr(actual, key), getattr(expected, key), err_msg=key)
        state = rk4_step(lambda y, *args: model.rhs(y, *args, xp=np), state, 1e-9, u, p, p.active)
        original = rk4_step(
            lambda y, *args: base.rhs(y, *args, xp=np), original, 1e-9, u, layout, layout.active
        )
        for key in original._fields:
            np.testing.assert_array_equal(getattr(state, key), getattr(original, key), err_msg=key)
        model.check_values(state, spec)
        base.check_values(original, target)
