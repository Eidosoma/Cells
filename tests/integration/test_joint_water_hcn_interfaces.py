"""Public 56-law water/repair interfaces; physical qualification stays separate."""

import json
import subprocess
import sys
from copy import deepcopy

import jax
import numpy as np
import pytest

from cells.assembly_cell.io import load_checkpoint, write_checkpoint
from cells.assembly_cluster import engine as assembly
from cells.assembly_cluster.spec import parse_spec as parse_assembly
from cells.core.batch import BatchSpec, WorldSpec, parse_batch
from cells.core.excision import excise
from cells.core.schedule import control_values
from cells.core.specs import ConfigError, parse_spec
from cells.core.state import initialise
from cells.ensemble.cluster import aggregate
from cells.ensemble.ionic import parse_spec as parse_ensemble
from cells.io import load_snapshot, write_snapshot
from cells.models import surface_calcium_energy as fuel
from cells.models.registry import get_model
from tests.integration.test_cli import cli
from tests.joint_water_hcn_fixtures import (
    DT,
    FAMILIES,
    FIELDS,
    assembly_definition,
    components,
    definition,
)
from tests.unit.test_surface_catalog import evidence
from tests.unit.test_surface_kinetic import exact


@pytest.mark.parametrize("family", FAMILIES)
@pytest.mark.parametrize("backend", ("cpu", "gpu"))
def test_public_routes_keep_full_catalog_and_typed_water_owners(family, backend):
    schema, model = components(family)
    raw = definition(family, backend=backend, jit=True)
    spec = parse_spec(raw)
    assert spec == schema.parse(raw) == parse_spec(spec.to_dict())
    assert spec.to_dict()["model"]["id"] == model.MODEL_ID
    assert get_model(spec.model) is model
    state, layout = model.initial_values(spec)
    assert type(state) is model.STATE_TYPE and type(layout) is model.LAYOUT_TYPE
    assert len(state) == FIELDS[family]
    assert set(layout.channel_laws[layout.channel_active]) == set(range(56))
    if family == "repair":
        water_schema, water_model = components("water")
        parent = schema.base_spec(spec)
        assert get_model(parent.model) is water_model
        assert parent.to_dict()["model"]["id"] == water_model.MODEL_ID
        energy_layout = water_model.prior_layout(model.base_layout(layout))
        energy = water_schema.energy_spec(parent)
    else:
        energy_layout = model.prior_layout(layout)
        energy = schema.energy_spec(spec)
    assert type(energy_layout) is fuel.HCN_EXTRA_LAYOUT_TYPE
    assert energy.to_dict()["model"]["id"] == "resolved_calcium_energy@5"
    assert energy.to_dict()["model"]["ionic"]["id"] == "resolved_tissue@12"
    assert parse_ensemble(dict(model="ionic_worlds@1", simulation=raw, worlds=2)).simulation == spec
    batch = BatchSpec((WorldSpec(3, spec), WorldSpec(79, spec)), 2, 100, 2**30)
    assert parse_batch(batch.to_dict()) == batch
    evidence(
        "joint-water-hcn-routing-" + family + "-" + backend,
        dict(
            definition=spec.to_dict(),
            state_fields=list(state._fields),
            layout_fields=list(layout._fields),
            catalog_laws=56,
            scope="Schema, control and execution admission only; no GPU execution",
        ),
    )


@pytest.mark.parametrize("family", FAMILIES)
def test_public_controls_are_right_continuous_and_keep_water_repair_axes(family):
    schema, _ = components(family)
    raw = definition(family)
    spec = parse_spec(raw)
    times = [0.0, np.nextafter(DT, 0.0), DT, 2 * DT]
    table = control_values(spec, times)
    assert type(table) is schema.Control
    declarations = [
        ("water", "water_controls", "membrane_id", "availability", spec.model.membranes)
    ]
    declarations.append(
        ("channel", "channel_controls", "channel_id", "availability", spec.model.channels)
    )
    if family == "repair":
        declarations.extend(
            (name, "injury_controls", "membrane_id", name, spec.model.membranes)
            for name in ("injury", "resealing")
        )
    for field, group, key, value, owners in declarations:
        rows = {row[key]: row["schedule"] for row in raw["experiment"][group]}
        expected = np.asarray(
            [[rows[owner.id][i][value] for owner in owners] for i in (0, 0, 1, 1)]
        )
        actual = getattr(table, field)
        np.testing.assert_array_equal(actual[:, : len(owners)], expected)
        assert not np.any(actual[:, len(owners) :])


@pytest.mark.parametrize("family", FAMILIES)
def test_public_snapshots_preserve_every_water_fuel_and_gate_array(family, tmp_path):
    _, model = components(family)
    spec = parse_spec(definition(family))
    point = initialise(spec)
    folder = write_snapshot(tmp_path / "complete", spec, point)
    saved = load_snapshot(folder)
    assert saved.spec == spec
    assert type(saved.checkpoint.state) is model.STATE_TYPE
    assert type(saved.checkpoint.layout) is model.LAYOUT_TYPE
    exact(saved.checkpoint.state, point.state)
    exact(saved.checkpoint.layout, point.layout)
    definition_path = tmp_path / "definition.json"
    definition_path.write_text(json.dumps(spec.to_dict()))
    assert cli("validate", definition_path).returncode == 0
    with pytest.raises(ConfigError, match="Cuts support"):
        excise(spec, point, [spec.model.cells[0].id])
    evidence(
        "joint-water-hcn-snapshot-" + family,
        dict(
            complete_fields=FIELDS[family],
            layout_fields=len(point.layout),
            exact_initial_snapshot=True,
            unsupported_cut_refused=True,
            scope="Initial persistence and public validation; no evolved-history claim",
        ),
    )


@pytest.mark.parametrize("family", FAMILIES)
@pytest.mark.parametrize("fault", ("old_outer_version", "old_inner_version"))
def test_public_version_mismatch_cannot_silently_drop_hcn_or_water(family, fault):
    raw = definition(family)
    if fault == "old_outer_version":
        raw["model"]["id"] = raw["model"]["id"].replace("@2", "@1")
    else:
        raw["model"]["ionic"]["id"] = "resolved_tissue@11"
    with pytest.raises(ConfigError):
        parse_spec(raw)


@pytest.mark.parametrize("family", FAMILIES)
def test_assembly_owner_reports_and_checkpoint_include_new_versions(family, tmp_path):
    spec = parse_assembly(assembly_definition(family))
    state = assembly.initial_state(spec)
    report = assembly.summary(spec, state) | dict(
        arm=family, wall_start=0.0, wall_end=1.0, execute_seconds=0.0
    )
    assert report["physical_model"] == components(family)[0].MODEL_ID
    target = aggregate([report, report])[family]
    assert target["worlds"] == 2 * spec.pool.worlds
    for name in ("water", "calcium", "finite_energy", "ip3") + (
        ("injury",) if family == "repair" else ()
    ):
        assert name in target
        wrong = deepcopy(report)
        wrong.pop(name)
        with pytest.raises(ValueError):
            aggregate([report, wrong])
    np.testing.assert_array_equal(
        target["water"]["cell_volume_pL_sum_over_worlds"],
        2 * np.sum(report["water"]["cell_volume_pL"], axis=0),
    )
    write_checkpoint(tmp_path / "assembly", spec, state, backend="cpu")
    restored, newer, _ = load_checkpoint(tmp_path / "assembly", backend="cpu")
    assert restored == spec
    exact(jax.tree.leaves(newer), jax.tree.leaves(state))
    evidence(
        "joint-water-hcn-assembly-" + family,
        dict(
            report=report,
            complete_initial_checkpoint=True,
            scope="Initial assembly owners, aggregation and snapshot; no stochastic trajectory",
        ),
    )


def test_offline_world_assignment_preserves_both_models_through_sixteen_gpus():
    from cells.ensemble.families import parse_definition, population
    from tests.unit.test_hcn_extra_catalog_planning import verify
    from tests.unit.test_integrated_ensemble import experiment

    raw = experiment("ionic", backend="gpu", worlds=8, width=1)
    # Sixteen tasks each reserve success and recovery checkpoints. Their
    # metadata alone exceeds the tiny example's 512 MiB output allowance.
    raw["execution"]["max_output_bytes"] = 1024**3
    template = deepcopy(raw["arms"][0])
    raw["arms"] = []
    for family in FAMILIES:
        arm = deepcopy(template)
        arm["id"] = family
        arm["definition"]["simulation"] = definition(family, backend="gpu", jit=True)
        raw["arms"].append(arm)
    plans = verify(raw)
    ids, counts = [], dict.fromkeys(FAMILIES, 0)
    for task in plans["local"]["tasks"]:
        spec = parse_definition(task["definition"])
        owners = population(spec)
        assert owners.seed == raw["seed"]
        assert spec.simulation.to_dict()["model"]["id"] == components(task["arm"])[0].MODEL_ID
        counts[task["arm"]] += owners.worlds
        ids.extend(range(owners.world_id_start, owners.world_id_start + owners.worlds))
    assert sorted(ids) == list(range(16)) and set(counts.values()) == {8}
    evidence(
        "joint-water-hcn-offline-placement",
        dict(
            inputs=raw,
            plans=plans,
            world_ids=sorted(ids),
            per_arm_worlds=counts,
            scope="Offline 1/4/16-GPU assignment only; no utilization or remote execution claim",
        ),
    )


@pytest.mark.parametrize("family", FAMILIES)
def test_short_eager_history_and_fresh_process_restart_preserve_complete_suffix(family, tmp_path):
    _, model = components(family)
    spec = parse_spec(definition(family))
    config = tmp_path / "input.json"
    config.write_text(json.dumps(spec.to_dict()))
    original = tmp_path / "original"

    def invoke(name, arguments):
        child = subprocess.run(
            [sys.executable, "-B", "-m", "cells", *map(str, arguments)],
            capture_output=True,
            text=True,
            timeout=240,
        )
        (tmp_path / (name + ".stdout.log")).write_text(child.stdout)
        (tmp_path / (name + ".stderr.log")).write_text(child.stderr)
        assert child.returncode == 0, child.stderr

    # Separate child processes keep primitive caches out of the host test worker
    # while exercising the actual public run and resume commands.
    invoke("run", ("run", config, "--output", original, "--checkpoint-at", DT))
    manifest = json.loads((original / "manifest.json").read_text())
    snapshot = original / manifest["snapshots"][0]
    destination = tmp_path / "restored"
    invoke("resume", ("resume", snapshot, "--output", destination))
    before = load_snapshot(original / "checkpoint_final")
    saved = load_snapshot(destination / "checkpoint_final")
    assert type(saved.checkpoint.state) is model.STATE_TYPE
    assert saved.checkpoint.time == before.checkpoint.time == 2 * DT
    assert len(before.checkpoint.state) == FIELDS[family]
    exact(saved.checkpoint.state, before.checkpoint.state)
    exact(saved.checkpoint.layout, before.checkpoint.layout)
    with (
        np.load(original / "trajectory.npz", allow_pickle=False) as expected,
        np.load(destination / "trajectory.npz", allow_pickle=False) as actual,
    ):
        arrays = {"original_" + k: expected[k] for k in expected.files}
        arrays.update({"restored_" + k: actual[k] for k in actual.files})
        assert len(expected["accepted_times"]) == 3
        np.testing.assert_array_equal(actual["accepted_times"], expected["accepted_times"][1:])
        for name in before.checkpoint.state._fields:
            np.testing.assert_array_equal(actual[name], expected[name][1:])
        selected = expected["observation_times"] >= DT
        for key in expected.files:
            if key == "observation_times" or key.startswith("observed_"):
                np.testing.assert_array_equal(actual[key], expected[key][selected])
    assert json.loads((destination / "summary.json").read_text())["executed_steps"] == 1
    evidence(
        "joint-water-hcn-eager-restart-" + family,
        dict(
            definition=spec.to_dict(),
            original_summary=json.loads((original / "summary.json").read_text()),
            complete_fields=FIELDS[family],
            executed_steps=2,
            restored_steps=1,
            fresh_process_exact_complete_suffix=True,
            scope=(
                "Two-step public execution/restart; "
                "independent physical convergence remains separate"
            ),
        ),
        arrays,
    )
