"""Mixed potassium/calcium composition through the established calcium suite.

The scoped adapter changes the model, fixtures and evidence prefix only. Shared
trajectory, ownership, replay, assembly and CPU/L4 assertions keep their original
tolerances. Additional checks target the new law/chemical-ownership boundary.
"""

import copy
import json
from pathlib import Path

import jax
import numpy as np
import pytest

from cells.core.batch import BatchSpec, WorldSpec, run_batch
from cells.core.runner import branch_checkpoint, run, timeline
from cells.core.schedule import control_values
from cells.core.specs import ConfigError, parse_spec
from cells.io import load_snapshot, write_run
from cells.models import surface_calcium as legacy
from cells.models import surface_calcium_channels as model
from cells.models.registry import get_model
from cells.processes.potassium_channels import KIR_LAW_ID
from tests.unit import test_surface_calcium as shared
from tests.unit.test_surface_kinetic import assert_states, exact
from validation.tissue import surface_calcium_channel_fixtures as fixtures
from validation.tissue import surface_calcium_fixtures as old_fixtures
from validation.tissue import surface_calcium_reference as reference

PREFIX = "resolved-calcium-channels"
BACKEND, EVIDENCE = shared.BACKEND, shared.EVIDENCE


@pytest.fixture(scope="module", autouse=True)
def composition_context():
    # Restored before any separately collected legacy-model regression tests.
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(shared, "model", model)
        patch.setattr(shared, "fixtures", fixtures)
        patch.setattr(shared, "PREFIX", PREFIX)
        yield


def evidence(name, value):
    shared.evidence(PREFIX + "-" + name, value)


def initial(raw=None):
    spec = parse_spec(fixtures.definition() if raw is None else raw)
    state, layout = model.initial_values(spec)
    controls = control_values(spec, [0.0])
    return spec, state, layout, type(controls)(*(v[0] for v in controls))


@pytest.mark.parametrize("definitions", [old_fixtures, fixtures], ids=["legacy", "mixed"])
def test_initial_assembly_report_preserves_owned_readouts(definitions, monkeypatch):
    spec = shared.parse_assembly(definitions.assembly_definition(backend=BACKEND))
    state = shared.assembly.initial_state(spec)
    # The initial-state fixture has no integration time; summary() supplies
    # physical readouts, while run() normally adds timing for aggregation.
    report = shared.assembly.summary(spec, state) | {"execute_seconds": 0.0}
    # Exercise both model versions before compiling any long trajectories.
    with monkeypatch.context() as patch:
        patch.setattr(shared, "model", get_model(spec.ionic.model))
        shared.test_assembly_aggregation_retains_owned_ligand((spec, state, report))


def test_composition_identity_laws_and_rejections():
    spec, state, p, _ = initial()
    assert get_model(spec.model) is model
    assert type(p) is model.LAYOUT_TYPE
    assert spec.to_dict()["model"]["id"] == "resolved_calcium@2"
    assert spec.to_dict()["model"]["ionic"]["id"] == "resolved_tissue@3"
    np.testing.assert_array_equal(p.channel_laws, [0, 1, 0, 1, 1, 0])
    view = model.ionic_layout(state, p, xp=np)
    np.testing.assert_array_equal(view.channel_laws, p.channel_laws)
    assert len(model.STATE_TYPE._fields) == 34
    faults = (
        "old_outer",
        "old_inner",
        "legacy_kir",
        "law",
        "species",
        "temperature",
        "large_step",
        "capacity",
        "duplicate",
        "control",
    )
    for fault in faults:
        raw = fixtures.definition()
        outer, x = raw["model"], raw["execution"]
        ion, e = outer["ionic"], raw["experiment"]
        if fault == "old_outer":
            outer["id"] = "resolved_calcium@1"
        elif fault == "old_inner":
            ion["id"] = "resolved_tissue@2"
        elif fault == "legacy_kir":
            outer["id"], ion["id"] = "resolved_calcium@1", "resolved_tissue@2"
        elif fault == "law":
            ion["channels"][1]["kinetic_law"] = "unknown"
        elif fault == "species":
            ion["channels"][1]["species_id"] = "Na"
        elif fault == "temperature":
            ion["temperature_K"] = 310.0
        elif fault == "large_step":
            x["dt"] = 50e-6
        elif fault == "capacity":
            x["channel_capacity"] = 4
        elif fault == "duplicate":
            outer["calcium_channels"][0]["id"] = ion["channels"][4]["id"]
        else:
            e["channel_controls"][4]["schedule"][0]["availability"] = -0.1
        with pytest.raises(ConfigError):
            timeline(parse_spec(raw))
    bad_codes = p.channel_laws.copy()
    bad_codes[1] = 2
    assert not model.domain_valid(state, p._replace(channel_laws=bad_codes), p.active, xp=np)
    bad_codes = p.channel_laws.copy()
    bad_codes[-1] = 1
    assert not model.domain_valid(state, p._replace(channel_laws=bad_codes), p.active, xp=np)
    evidence("design", dict(status="passed", inputs=spec.to_dict(), rejected=list(faults)))


def test_legacy_calcium_kv_only_reduction():
    raw = old_fixtures.definition()
    old, state, p, c = initial(raw)
    assert get_model(old.model) is legacy and type(p) is legacy.LAYOUT_TYPE
    assert not hasattr(p, "channel_laws")
    raw["model"]["id"] = "resolved_calcium@2"
    raw["model"]["ionic"]["id"] = "resolved_tissue@3"
    new, newer, q, d = initial(raw)
    exact(newer, state)
    a, b = legacy.readouts(state, c, p, xp=np), model.readouts(newer, d, q, xp=np)
    exact(a.derivative, b.derivative)
    exact(jax.tree.leaves(a.field), jax.tree.leaves(b.field))
    assert parse_spec(old.to_dict()) == old and parse_spec(new.to_dict()) == new
    # Independent old-model stages remain a regression control, not new cases.
    for arm in old_fixtures.ARMS:
        old, y, p, c = initial(old_fixtures.definition(arm))
        context = reference.bind(old.to_dict())
        expected, _, _ = reference.evaluate(context, reference.initial(context), 0.0)
        assert_states(
            context,
            reference.flatten(context, legacy.rhs(y, c, p, p.active, xp=np)._asdict()),
            expected,
            atol=3e-12,
            charge_atol=3e-23,
            rtol=3e-10,
        )
    evidence("legacy", dict(status="passed", kv_only_stage="bitwise", old_layout_preserved=True))


def test_free_potassium_ownership_and_kir_controls():
    spec, state, p, control = initial()
    changed = model.STATE_TYPE(*(np.array(v) for v in state))
    names = [s.id for s in spec.model.stores[0].species]
    k = names.index("K")
    cy, er = int(p.er_cytosol[0]), int(p.er_er[0])
    changed.chemical_amount_increment[0, k, [cy, er]] += 1e-4 * np.array([-1, 1])
    assert model.domain_valid(changed, p, p.active, xp=np)
    exact(model.ensemble_voltage(state, p, spec, 0), model.ensemble_voltage(changed, p, spec, 0))
    before, after = (model.readouts(y, control, p, xp=np) for y in (state, changed))
    # Cell zero owns channels 0, 1 and 4; cell one's pools were not changed.
    for i in (0, 1, 4):
        assert after.derivative.channel_transferred[i] != before.derivative.channel_transferred[i]
    # Re-solving the shared floating field can change the last bits even when
    # the unchanged owner's physical concentration and patch voltage agree.
    np.testing.assert_array_equal(
        model.physical_amounts(changed, p)[0][:, 1],
        model.physical_amounts(state, p)[0][:, 1],
    )
    np.testing.assert_allclose(
        after.derivative.channel_transferred[[2, 3]],
        before.derivative.channel_transferred[[2, 3]],
        rtol=3e-10,
        atol=3e-12,
    )
    context = reference.bind(spec.to_dict())
    expected, _, proof = reference.evaluate(
        context, reference.flatten(context, changed._asdict()), 0.0
    )
    assert_states(
        context,
        reference.flatten(context, after.derivative._asdict()),
        expected,
        atol=3e-12,
        charge_atol=3e-23,
        rtol=3e-10,
    )
    assert abs(proof["physical_energy_balance_pJ_s"]) < 1e-10
    raw = spec.to_dict()
    kir = [i for i, ch in enumerate(spec.model.channels) if ch.kinetic_law == KIR_LAW_ID]
    for i in kir:
        raw["experiment"]["channel_controls"][i]["schedule"][0]["availability"] = 0.0
    blocked, y, q, d = initial(raw)
    held = model.readouts(y, d, q, xp=np)
    exact(held.derivative.channel_gate, before.derivative.channel_gate)
    assert not np.any(held.derivative.channel_transferred[kir])
    assert np.any(held.field.membrane_voltage_rate_V_s != before.field.membrane_voltage_rate_V_s)
    context = reference.bind(blocked.to_dict())
    expected, _, proof = reference.evaluate(context, reference.initial(context), 0.0)
    assert_states(
        context,
        reference.flatten(context, held.derivative._asdict()),
        expected,
        atol=3e-12,
        charge_atol=3e-23,
        rtol=3e-10,
    )
    assert abs(proof["physical_energy_balance_pJ_s"]) < 1e-10
    evidence(
        "ownership-controls",
        dict(
            status="passed",
            kir_indices=kir,
            internal_potassium_transfer_fmol=1e-4,
            plasma_voltage_unchanged_by_internal_transfer=True,
            intrinsic_gates_unchanged_by_block=True,
            independent_stage_comparisons=2,
            unchanged_owner_flux_max_difference_fmol_s=float(
                np.max(
                    np.abs(
                        after.derivative.channel_transferred[[2, 3]]
                        - before.derivative.channel_transferred[[2, 3]]
                    )
                )
            ),
        ),
    )


def test_compiled_smoke_and_layout_identity(tmp_path):
    raw = fixtures.definition(backend=BACKEND)
    raw["experiment"].update(end_time=50e-6, observation_times=[0.0, 25e-6, 50e-6])
    result = run(parse_spec(raw))
    assert all(v.device.platform == BACKEND for v in result.final.state)
    write_run(tmp_path / "smoke", result)
    loaded = load_snapshot(tmp_path / "smoke/checkpoint_final")
    assert loaded.spec == result.spec
    exact(loaded.checkpoint.state, result.final.state)
    report = model.summarize(result.history, result.diagnostics, result.spec)
    assert report["model"] == model.MODEL_ID
    assert report["channel_laws"] == {c.id: c.kinetic_law for c in result.spec.model.channels}
    evidence(
        "smoke", dict(status="passed", inputs=result.spec.to_dict(), diagnostics=result.diagnostics)
    )


# Reuse all established calcium checks with the scoped composition above.
trajectories = shared.trajectories
coupled = shared.coupled
test_registered_roundtrip_and_ensemble = shared.test_registered_roundtrip_and_ensemble
test_independent_stage_rates_and_accounting = shared.test_independent_stage_rates_and_accounting
test_internal_chemistry_uses_free_ions_without_charging_plasma = (
    shared.test_internal_chemistry_uses_free_ions_without_charging_plasma
)
test_corrupt_complete_ledgers_or_inventories_are_rejected = (
    shared.test_corrupt_complete_ledgers_or_inventories_are_rejected
)
test_inconsistent_definitions_reject = shared.test_inconsistent_definitions_reject
test_failed_field_and_actual_controls_reject = shared.test_failed_field_and_actual_controls_reject
test_chemical_event_is_an_accepted_observation_boundary = (
    shared.test_chemical_event_is_an_accepted_observation_boundary
)
test_existing_resolved_kinetics_preserve_rates_and_energy = (
    shared.test_existing_resolved_kinetics_preserve_rates_and_energy
)
test_evolved_stage_preserves_owned_charge_and_independent_rates = (
    shared.test_evolved_stage_preserves_owned_charge_and_independent_rates
)
test_new_model_rejects_held_bath_with_explicit_scope = (
    shared.test_new_model_rejects_held_bath_with_explicit_scope
)
test_absent_routes_and_zero_reaction_capacity_keep_zero_ledgers = (
    shared.test_absent_routes_and_zero_reaction_capacity_keep_zero_ledgers
)
test_independent_trajectories_and_complete_accounting = (
    shared.test_independent_trajectories_and_complete_accounting
)
test_timestep_refinement = shared.test_timestep_refinement
test_compiled_guard_rejects_actual_invalid_control_without_changing_state = (
    shared.test_compiled_guard_rejects_actual_invalid_control_without_changing_state
)
test_complete_disk_fresh_process_restart_branch_and_windows = (
    shared.test_complete_disk_fresh_process_restart_branch_and_windows
)
test_world_partition_reorder_and_independent_restart = (
    shared.test_world_partition_reorder_and_independent_restart
)
test_ensemble_endpoint_reports_real_patch_voltages_and_complete_state = (
    shared.test_ensemble_endpoint_reports_real_patch_voltages_and_complete_state
)
test_cpu_gpu_complete_saved_states_and_observations = (
    shared.test_cpu_gpu_complete_saved_states_and_observations
)
test_assembly_event_reference = shared.test_assembly_event_reference
test_assembly_restart_partition_and_ligand_response = (
    shared.test_assembly_restart_partition_and_ligand_response
)
test_sixteen_gpu_planning_keeps_worlds_and_model = (
    shared.test_sixteen_gpu_planning_keeps_worlds_and_model
)
test_assembly_aggregation_retains_owned_ligand = (
    shared.test_assembly_aggregation_retains_owned_ligand
)


@pytest.fixture(scope="module")
def references(composition_context):
    if BACKEND == "gpu" and EVIDENCE:
        result = {}
        for arm in fixtures.ARMS:
            saved = json.loads(
                (Path(EVIDENCE) / "cpu" / (PREFIX + "-trajectory-" + arm + ".json")).read_text()
            )
            assert saved["status"] == "passed"
            assert saved["inputs"] == parse_spec(fixtures.definition(arm)).to_dict()
            result[arm] = saved["independent_reference"]
        return result
    return {arm: reference.integrate(fixtures.definition(arm)) for arm in fixtures.ARMS}


def test_restart_rejects_changed_channel_law(trajectories):
    value = trajectories["baseline"]
    raw = copy.deepcopy(value.spec.to_dict())
    raw["model"]["ionic"]["channels"][1]["kinetic_law"] = "betse_kv1p5_mh@1"
    with pytest.raises((ConfigError, ValueError)):
        branch_checkpoint(value.spec, value.checkpoint_at(0.001), parse_spec(raw))
    evidence("law-identity", dict(status="passed", changed_law_branch_rejected=True))


def test_channel_laws_remain_owned_by_each_batched_world(trajectories):
    baseline = trajectories["baseline"]
    raw = baseline.spec.to_dict()
    for channel in raw["model"]["ionic"]["channels"]:
        channel["kinetic_law"] = "betse_kv1p5_mh@1"
    alternate = run(parse_spec(raw))
    assert np.any(alternate.history.channel_gate != baseline.history.channel_gate)
    spec = BatchSpec((WorldSpec(23, baseline.spec), WorldSpec(41, alternate.spec)), 2, 1000, 2**29)
    batch = run_batch(spec)
    exact(batch.worlds[23].history, baseline.history)
    exact(batch.worlds[41].history, alternate.history)
    evidence(
        "world-laws",
        dict(
            status="passed",
            comparison="bitwise against each standalone world",
            world_ids=[23, 41],
            law_lists=[
                [c.kinetic_law for c in value.spec.model.channels]
                for value in (baseline, alternate)
            ],
            scope="numerical law-routing control, not an independent biological case",
        ),
    )
