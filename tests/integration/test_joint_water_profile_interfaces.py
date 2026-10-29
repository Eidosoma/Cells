"""Complete scheduled water/repair owners through the public execution boundary.

Two nanoseconds exercises interfaces and actual restart, not physical recovery.
The component's independent multi-observation trajectories qualify the physics.
"""

import json
import subprocess
import sys
from copy import deepcopy
from dataclasses import replace

import numpy as np
import pytest

from cells.assembly_cluster.spec import AssemblyError
from cells.assembly_cluster.spec import parse_spec as parse_assembly
from cells.core import owned_calcium_profile_phase_handoff as phase_handoff
from cells.core.batch import BatchSpec, WorldSpec, parse_batch
from cells.core.errors import NumericalError
from cells.core.excision import excise
from cells.core.runner import branch_checkpoint, validate_checkpoint
from cells.core.schedule import control_values
from cells.core.specs import ConfigError, parse_spec
from cells.core.state import initialise
from cells.ensemble.ionic import parse_spec as parse_ensemble
from cells.io import load_snapshot, write_snapshot
from cells.models.registry import get_model
from tests.joint_water_hcn_fixtures import assembly_definition
from tests.joint_water_profile_fixtures import DT, FAMILIES, FIELDS, components, definition
from tests.unit.test_surface_catalog import evidence
from tests.unit.test_surface_kinetic import exact


@pytest.mark.parametrize("family", FAMILIES)
@pytest.mark.parametrize("backend", ("cpu", "gpu"))
def test_public_scheduled_water_routes_preserve_complete_owners(family, backend):
    schema, model = components(family)
    raw = definition(family, backend=backend, jit=True)
    spec = parse_spec(raw)
    assert spec == schema.parse(raw) == parse_spec(spec.to_dict())
    assert get_model(spec.model) is model
    assert schema.replay(schema.artifact(spec)) == spec
    owner = schema.owner_spec(spec)
    assert owner.to_dict()["model"]["id"] == schema.PARENT_MODEL_ID
    state, layout = model.initial_values(spec)
    parent_state, parent_layout = get_model(owner.model).initial_values(owner)
    exact(model.parent_state(state), parent_state)
    exact(model.parent_layout(layout), parent_layout)
    assert len(state) == FIELDS[family]
    assert state._fields == (*parent_state._fields, "phase_clock_s")
    assert set(layout.channel_laws[layout.channel_active]) == set(range(56))
    batch = BatchSpec((WorldSpec(3, spec), WorldSpec(79, spec)), 2, 100, 2**32)
    assert parse_batch(batch.to_dict()) == batch
    assert parse_ensemble(dict(model="ionic_worlds@1", simulation=raw, worlds=2)).simulation == spec
    evidence(
        "water-profiles-routing-" + family + "-" + backend,
        dict(
            definition=spec.to_dict(),
            state_fields=list(state._fields),
            layout_fields=list(layout._fields),
            complete_parent_arrays_exact=True,
            scope="Schema, portable replay and offline admission; no GPU execution",
        ),
    )


@pytest.mark.parametrize("family", FAMILIES)
def test_scheduled_water_controls_are_right_continuous(family):
    schema, _ = components(family)
    raw = definition(family)
    spec = parse_spec(raw)
    times = [0.0, np.nextafter(DT, 0.0), DT, 2 * DT]
    actual = control_values(spec, times)
    exact(actual, control_values(schema.owner_spec(spec), times))
    # Every held axis must retain its boundary, independently of the pulse clock.
    for field in actual:
        np.testing.assert_array_equal(field[0], field[1])
        np.testing.assert_array_equal(field[2], field[3])
    declarations = [
        ("water", "water_controls", "membrane_id", "availability", spec.model.membranes),
        ("channel", "channel_controls", "channel_id", "availability", spec.model.channels),
    ]
    if family == "repair":
        declarations.extend(
            (name, "injury_controls", "membrane_id", name, spec.model.membranes)
            for name in ("injury", "resealing")
        )
    for field, group, key, value, owners in declarations:
        rows = {row[key]: row["schedule"] for row in raw["experiment"][group]}
        expected = [[rows[owner.id][i][value] for owner in owners] for i in (0, 0, 1, 1)]
        np.testing.assert_array_equal(getattr(actual, field)[:, : len(owners)], expected)
        assert not np.any(getattr(actual, field)[:, len(owners) :])
    assert np.any(actual.regeneration[0] != actual.regeneration[2])
    evidence(
        "water-profiles-controls-" + family,
        dict(
            definition=raw,
            control_fields=list(actual._fields),
            right_continuous=True,
        ),
        arrays={name: np.asarray(v) for name, v in actual._asdict().items()},
    )


@pytest.mark.parametrize("family", FAMILIES)
@pytest.mark.parametrize("phase", ("INIT", "SIM"))
def test_scheduled_water_snapshot_preserves_typed_owner_and_phase(family, phase, tmp_path):
    schema, _ = components(family)
    spec = parse_spec(definition(family, phase))
    point = initialise(spec)
    saved = load_snapshot(write_snapshot(tmp_path / "saved", spec, point))
    assert saved.spec == spec
    exact(saved.checkpoint.state, point.state)
    exact(saved.checkpoint.layout, point.layout)
    other = spec.to_dict()
    other["model"]["phase"] = "INIT" if phase == "SIM" else "SIM"
    with pytest.raises(ConfigError, match="branch may not change model"):
        branch_checkpoint(spec, point, parse_spec(other))
    owner = schema.owner_spec(spec)
    with pytest.raises(ConfigError):
        validate_checkpoint(owner, point)
    with pytest.raises(ConfigError):
        validate_checkpoint(spec, initialise(owner))
    evidence(
        "water-profiles-snapshot-" + family + "-" + phase,
        dict(
            definition=spec.to_dict(),
            complete_fields=FIELDS[family],
            exact_initial_snapshot=True,
            implicit_phase_change_refused=True,
        ),
    )


@pytest.mark.parametrize("family", FAMILIES)
def test_scheduled_water_unsupported_compositions_cannot_use_parent_admission(family):
    schema, _ = components(family)
    spec = parse_spec(definition(family, "INIT", jit=True))
    point = initialise(spec)
    with pytest.raises(ConfigError, match="Cuts support"):
        excise(spec, point, [spec.model.cells[0].id])
    with pytest.raises(ConfigError, match="exactly"):
        phase_handoff.capture_source(spec, point)
    raw = assembly_definition(family)
    raw["ionic"] = spec.to_dict()
    with pytest.raises(AssemblyError, match="qualified spatial"):
        parse_assembly(raw)
    mixed = BatchSpec((WorldSpec(3, spec), WorldSpec(79, schema.owner_spec(spec))), 2, 100, 2**32)
    with pytest.raises(ConfigError, match="one model family"):
        parse_batch(mixed.to_dict())


def test_scheduled_water_offline_assignment_through_sixteen_gpus():
    from cells.ensemble.families import parse_definition, population
    from tests.unit.test_hcn_extra_catalog_planning import verify
    from tests.unit.test_integrated_ensemble import experiment

    raw = experiment("ionic", backend="gpu", worlds=8, width=1)
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
        "water-profiles-offline-placement",
        dict(
            inputs=raw,
            plans=plans,
            world_ids=sorted(ids),
            per_arm_worlds=counts,
            scope="Offline 1/4/16-GPU assignment; no execution or utilization qualification",
        ),
    )


@pytest.mark.parametrize("family", FAMILIES)
def test_scheduled_water_fresh_process_execution_and_complete_restart(family, tmp_path):
    _, model = components(family)
    spec = parse_spec(definition(family))
    config = tmp_path / "input.json"
    config.write_text(json.dumps(spec.to_dict()))
    original, resumed = tmp_path / "original", tmp_path / "resumed"

    def invoke(name, *arguments):
        result = subprocess.run(
            [sys.executable, "-B", "-m", "cells", *map(str, arguments)],
            capture_output=True,
            text=True,
            timeout=240,
        )
        (tmp_path / (name + ".stdout.log")).write_text(result.stdout)
        (tmp_path / (name + ".stderr.log")).write_text(result.stderr)
        assert result.returncode == 0, result.stderr

    invoke("run", "run", config, "--output", original, "--checkpoint-at", DT)
    manifest = json.loads((original / "manifest.json").read_text())
    midpoint = original / manifest["snapshots"][0]
    point = load_snapshot(midpoint).checkpoint
    assert point.time == DT and np.any(point.state.channel_transferred != 0)
    assert np.any(point.state.pump_cycles != 0)
    damaged = replace(point, state=point.state._replace(phase_clock_s=np.asarray([0.0])))
    with pytest.raises((ConfigError, NumericalError), match="clock"):
        validate_checkpoint(spec, damaged)
    invoke("resume", "resume", midpoint, "--output", resumed)
    before = load_snapshot(original / "checkpoint_final").checkpoint
    after = load_snapshot(resumed / "checkpoint_final").checkpoint
    assert type(after.state) is model.STATE_TYPE and len(after.state) == FIELDS[family]
    assert before.time == after.time == 2 * DT
    exact(after.state, before.state)
    exact(after.layout, before.layout)
    with (
        np.load(original / "trajectory.npz") as expected,
        np.load(resumed / "trajectory.npz") as actual,
    ):
        arrays = {"original_" + k: expected[k] for k in expected.files}
        arrays.update({"resumed_" + k: actual[k] for k in actual.files})
        np.testing.assert_array_equal(actual["accepted_times"], expected["accepted_times"][1:])
        for field in before.state._fields:
            np.testing.assert_array_equal(actual[field], expected[field][1:])
        selected = expected["observation_times"] >= DT
        observed = [k for k in expected.files if k.startswith("observed_")]
        for key in ["observation_times", *observed]:
            np.testing.assert_array_equal(actual[key], expected[key][selected])
        np.testing.assert_allclose(
            expected["phase_clock_s"][:, 0], expected["accepted_times"], atol=1e-23, rtol=0
        )
    summary = json.loads((resumed / "summary.json").read_text())
    assert summary["executed_steps"] == 1
    evidence(
        "water-profiles-fresh-restart-" + family,
        dict(
            definition=spec.to_dict(),
            complete_fields=FIELDS[family],
            layout_fields=len(after.layout),
            observation_fields=len(observed),
            restored_summary=summary,
            exact_complete_suffix=True,
            scope="Two eager CPU steps and a fresh-process restored step; interface evidence only",
        ),
        arrays=arrays,
    )
