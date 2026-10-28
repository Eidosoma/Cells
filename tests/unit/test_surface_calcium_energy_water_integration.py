"""Owned calcium/water full-state compilation and assembly/placement contracts."""

from copy import deepcopy

import jax
import numpy as np
import pytest

from cells.assembly_cell.io import load_checkpoint, write_checkpoint
from cells.assembly_cluster import engine as assembly
from cells.assembly_cluster.spec import parse_spec as parse_assembly
from cells.core.runner import run
from cells.core.schedule import control_values
from cells.core.specs import parse_spec
from cells.ensemble.cluster import aggregate
from cells.io import load_snapshot, write_run
from cells.models import surface_calcium_energy_water as model
from cells.processes import morris_lecar_catalog as catalog
from tests.unit.test_surface_calcium_energy_water import changed
from tests.unit.test_surface_catalog import evidence
from tests.unit.test_surface_kinetic import assert_states, exact
from validation.tissue import calcium_energy_water_fixtures as fixtures
from validation.tissue import calcium_energy_water_reference as reference


def test_assembly_summary_and_checkpoint_preserve_water_owners(tmp_path):
    spec = parse_assembly(fixtures.assembly_definition())
    state = assembly.initial_state(spec)
    report = assembly.summary(spec, state) | dict(
        arm="water", wall_start=0.0, wall_end=1.0, execute_seconds=0.0
    )
    assert report["physical_model"] == fixtures.MODEL_ID
    value = report["water"]
    assert value["chemical_osmotic_coupling"] == "ideal_all_cytosol_species_fixed_er@1"
    assert value["er_water_coupling"] == "fixed ER volume; no ER water port"
    assert value["energy_osmotic_coupling"] == "neutral_ideal_atp_adp_pi@1"
    target = aggregate([report, report])["water"]
    np.testing.assert_array_equal(
        target["finite_energy"]["amount_fmol_sum_over_worlds"],
        2 * np.sum(report["finite_energy"]["amount_fmol"], axis=0),
    )
    assert target["worlds"] == 2 * spec.pool.worlds
    for key in (
        "cell_volume_pL",
        "outside_volume_pL",
        "er_volume_pL",
        "cytosol_free_concentration_mM",
        "cytosol_osmolytes_fmol",
        "pool_osmolytes_fmol",
        "energy_concentration_mM",
        "pool_volume_work_pJ",
    ):
        np.testing.assert_array_equal(
            target["water"][key + "_sum_over_worlds"], 2 * np.sum(value[key], axis=0)
        )
    for key in ("water", "ip3", "calcium", "finite_energy", "channel_transfer_axes"):
        wrong = deepcopy(report)
        wrong.pop(key)
        with pytest.raises(ValueError):
            aggregate([report, wrong])
    for key, invalid in (
        ("chemical_osmotic_coupling", "duplicate_ions"),
        ("energy_osmotic_coupling", "duplicate_fuel"),
        ("pool_volume_work_pJ", [[float("nan")]]),
        ("er_water_coupling", "variable ER"),
        ("species_ids", list(reversed(value["species_ids"]))),
        ("cell_volume_pL", [[0.0]]),
        ("outside_volume_pL", [[float("nan")]]),
    ):
        wrong = deepcopy(report)
        wrong["water"][key] = invalid
        with pytest.raises(ValueError):
            aggregate([wrong])
    write_checkpoint(tmp_path / "assembly", spec, state, backend="cpu")
    restored, newer, _ = load_checkpoint(tmp_path / "assembly", backend="cpu")
    assert restored == spec
    exact(jax.tree.leaves(newer), jax.tree.leaves(state))
    evidence(
        "calcium-energy-water-assembly-owners",
        dict(
            status="passed",
            report=report,
            scope="Initial complete summary/checkpoint; no stochastic history",
        ),
    )


def test_offline_assembly_worlds_keep_owner_streams_in_gpu_plans():
    from tests.unit.test_assembly_cluster import ensemble_definition
    from tests.unit.test_morris_lecar_catalog_planning import verify

    raw = ensemble_definition()
    arm = deepcopy(raw["arms"][0])
    arm.update(
        id="water",
        worlds=16,
        batch_worlds=1,
        seconds_per_world=None,
        definition=fixtures.assembly_definition(),
    )
    for binding in arm["definition"]["pools"]:
        for key in ("worlds", "world_id_start", "seed"):
            binding["pool"].pop(key)
    raw["arms"] = [arm]
    plans = verify(raw)
    ids = []
    for task in plans["local"]["tasks"]:
        spec = parse_assembly(task["definition"])
        assert spec.ionic.to_dict()["model"]["id"] == fixtures.MODEL_ID
        assert [binding.pool.seed for binding in spec.pools] == [2**32 - 1, 0]
        ids.extend(range(spec.pool.world_id_start, spec.pool.world_id_start + spec.pool.worlds))
    assert sorted(ids) == list(range(16))
    evidence(
        "calcium-energy-water-assembly-planning",
        dict(
            status="passed",
            inputs=raw,
            plans=plans,
            world_ids=sorted(ids),
            scope=(
                "Offline 1/4/16-GPU placement; runtime balance and stochastic history unqualified"
            ),
        ),
    )


def test_compiled_two_world_calcium_energy_water_rates_and_isolated_failure():
    raw = fixtures.definition()
    spec = parse_spec(raw)
    state, p = model.initial_values(spec)
    table = control_values(spec, [0.0])
    u = type(table)(*(v[0] for v in table))
    modified = changed(spec, state, p)
    states = model.STATE_TYPE(*(np.stack((a, b)) for a, b in zip(state, modified, strict=True)))
    controls = type(u)(*(np.stack((v, v)) for v in u))
    evaluate = jax.jit(
        jax.vmap(
            lambda y, ctl, q: (
                model.rhs(y, ctl, q, q.active),
                model.control_domain_valid(y, ctl, q, q.active),
            ),
            in_axes=(0, 0, None),
        )
    )
    rates, valid = evaluate(states, controls, p)
    assert np.all(valid)
    c, checked = reference.bind(raw), []
    for i in (0, 1):
        y = model.STATE_TYPE(*(v[i] for v in states))
        derivative = model.STATE_TYPE(*(v[i] for v in rates))
        target, _, proof = reference.evaluate(c, reference.flatten(c, y._asdict()), 0.0)
        ratio = assert_states(
            c,
            reference.flatten(c, derivative._asdict()),
            target,
            atol=3e-12,
            charge_atol=3e-23,
            rtol=3e-10,
        )
        assert abs(proof["physical_energy_balance_pJ_s"]) < 1e-9
        checked.append(dict(max_error_over_budget=ratio, independent_stage=proof))
    failures = []
    for fault in ("absent_gate", "exhausted_fuel", "negative_regeneration_heat"):
        bad = model.STATE_TYPE(*(v.copy() for v in states))
        if fault == "absent_gate":
            bad.channel_gate[1, 0, np.flatnonzero(p.channel_laws == 46)[0]] = 0.25
        elif fault == "exhausted_fuel":
            bad.energy_amount_increment_fmol[1, 0, 0] = -p.energy_initial_amount_fmol[0, 0]
        else:
            bad.regeneration_dissipated_energy_pJ[1, 0] = -0.1
        failed, valid = evaluate(bad, controls, p)
        assert np.array_equal(np.asarray(valid), [True, False])
        assert all(np.isnan(v[1]).all() for v in failed)
        exact((v[0] for v in failed), (v[0] for v in rates))
        failures.append(fault)
    evidence(
        "calcium-energy-water-compiled-stage",
        dict(
            status="passed",
            inputs=raw,
            world_checks=checked,
            invalid_world_isolated=True,
            rejected_states=failures,
            scope="Two manufactured stages with changed free calcium, fuel, volumes and m gate",
        ),
    )


def test_compiled_calcium_energy_water_trajectory_and_complete_final_snapshot(tmp_path):
    raw = fixtures.compact_probe()
    result = run(parse_spec(raw))
    c = reference.bind(raw)
    expected = reference.integrate(raw)
    actual = reference.flatten(c, vars(result.observations))
    target = np.asarray(expected["state"])
    report = dict(
        status="captured",
        inputs=raw,
        diagnostics=result.diagnostics,
        scope=(
            "50-us full43 early coupling; live ATP, chemical cytosol and fixed ER; "
            "channel/water/supply controls"
        ),
        independent_reference={
            k: v.tolist() if isinstance(v, np.ndarray) else v for k, v in expected.items()
        },
    )
    evidence(
        "calcium-energy-water-trajectory",
        report,
        dict(observed=actual, reference=target, signed_error=actual - target),
    )
    ratio = assert_states(c, actual, target)
    assert np.max(np.abs(result.observations.volume_increment_pL)) > 1e-4
    initial_er = result.observations.er_volume_pL[0]
    assert np.all(result.observations.er_volume_pL == initial_er)
    p = result.final.layout
    absent = ~(catalog.gate_active(p.channel_laws, xp=np) & p.channel_active)
    assert np.all(result.observations.channel_gate[:, absent] == 0)
    write_run(tmp_path / "coupled", result)
    saved = load_snapshot(tmp_path / "coupled/checkpoint_final")
    assert saved.spec == result.spec and type(saved.checkpoint.layout) is model.LAYOUT_TYPE
    exact(saved.checkpoint.state, result.final.state)
    exact(saved.checkpoint.layout, result.final.layout)
    evidence(
        "calcium-energy-water-trajectory",
        report
        | dict(
            status="passed",
            max_error_over_budget=ratio,
            complete_final_snapshot=True,
            absent_gate_slots_exact_zero=True,
            er_volume_fixed=True,
        ),
    )
