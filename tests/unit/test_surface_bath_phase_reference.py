"""Independent complete epoch stages and explicit original-anchor source budgets."""

import json
import os
from pathlib import Path

import numpy as np
import pytest

from cells.core.schedule import control_values
from cells.core.specs import ConfigError
from tests.unit.test_surface_bath_phase_handoff import setup
from validation.topology import surface_bath_phase_fixtures as fixtures
from validation.topology import surface_bath_phase_handoff_reference as reference


def evidence(name, record, arrays=None):
    if directory := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        folder = Path(directory) / "surface-bath-phase"
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
    for key in ("local_fmol", "outside_fmol", "global_fmol"):
        np.testing.assert_allclose(proof[key], 0.0, rtol=0, atol=3e-14, err_msg=key)
    for key in ("capacitor_charge_C", "electrode_charge_C", "global_charge_C"):
        np.testing.assert_allclose(proof[key], 0.0, rtol=0, atol=3e-25, err_msg=key)
    for key in ("energy_residual_pJ", "chemical_work_residual_pJ", "electrode_work_residual_pJ"):
        np.testing.assert_allclose(proof[key], 0.0, rtol=0, atol=1e-10, err_msg=key)


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
        after["work_pJ"] - before["work_pJ"], op["chemical_work_pJ"].sum(), rtol=5e-13, atol=3e-12
    )
    np.testing.assert_array_equal(after["capacitor_change_pJ"], before["capacitor_change_pJ"])
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
        "validation/topology/surface_bath_phase_handoff_reference.py",
        "validation/transport/surface_bath_events_reference.py",
        "validation/tissue/surface_kinetic_reference.py",
        "validation/tissue/surface_dynamics_reference.py",
    } <= set(manifest)
    assert all(
        name.startswith("validation/")
        or Path(name).parent == Path("tests")
        and Path(name).name.startswith("reference_")
        for name in manifest
    )
    evidence("dependency-closure", dict(sources=manifest, production_imports=False))
