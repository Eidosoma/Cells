"""Public interfaces keep complete calcium/fuel owners and explicit phase history.

Independent field equations and adequately refined trajectories belong to the
component qualification. The two-step checks here exercise execution/restart.
"""

import importlib
import json
import subprocess
import sys
from copy import deepcopy
from dataclasses import replace
from functools import lru_cache
from pathlib import Path

import numpy as np
import pytest

from cells.core import active_membrane_profile_phase_handoff as active_handoff
from cells.core import membrane_profile_phase_handoff as passive_handoff
from cells.core import surface_calcium_energy_profile_interventions_spec as fuel_schema
from cells.core import surface_calcium_profile_interventions_spec as calcium_schema
from cells.core.batch import BatchSpec, WorldSpec, parse_batch
from cells.core.errors import NumericalError
from cells.core.excision import excise
from cells.core.grid import EventGrid
from cells.core.runner import branch_checkpoint, run, validate_checkpoint
from cells.core.schedule import control_values, event_index
from cells.core.specs import ConfigError, digest, parse_spec
from cells.core.state import initialise
from cells.core.windows import WindowPolicy, plan_windows
from cells.ensemble.ionic import parse_spec as parse_ensemble
from cells.io import load_snapshot, write_run, write_snapshot
from cells.models import surface_calcium_energy_profile_interventions as fuel
from cells.models import surface_calcium_profile_interventions as calcium
from cells.models.registry import get_model
from cells.numerics.fixed_step import rk4_step
from cells.tissue_profiles import REQUEST_KIND, prepare_request
from tests.integration.test_cli import cli
from tests.unit.test_surface_catalog import evidence
from validation.topology import owned_calcium_profile_interventions_fixtures as fixtures

OWNERS = {"calcium6": (calcium_schema, calcium), "fuel5": (fuel_schema, fuel)}


def definition(family, case="SIM", *, short=False):
    # Public dispatch needs a complete owner and a real control change, while
    # the component separately qualifies longer schedules and refinement.
    raw = deepcopy(fixtures.public_inputs(family))
    raw["phase"] = "INIT" if case == "INIT" else "SIM"
    if case == "ion-flags":
        raw["ion_enabled"] = [False] * 6
    if not short:
        for name, rows in raw["definition"]["experiment"].items():
            if name.endswith("_controls"):
                for row in rows:
                    key = "controls" if "controls" in row else "schedule"
                    changed = fixtures._scaled(row[key][0], 0.7)
                    changed["time"] = 1e-9
                    row[key].append(changed)
    options = {
        key: raw.pop(key)
        for key in (
            "interventions",
            "phase",
            "intervention_capacity",
            "intervention_target_capacity",
        )
    }
    prepared = prepare_request(dict(schema_version=1, kind=REQUEST_KIND, **raw))
    schema, _ = OWNERS[family]
    result = deepcopy(prepared.definition)
    result["model"].update(
        id=schema.MODEL_ID,
        profile_preparation=dict(definition=prepared.definition, provenance=prepared.provenance),
        interventions=options["interventions"],
        phase=options["phase"],
        timing_policy=schema.TIMING_POLICY,
        reset_policy=schema.RESET_POLICY,
    )
    result["execution"].update(
        jit=not short,
        max_trace_bytes=2**32,
        intervention_capacity=options["intervention_capacity"],
        intervention_target_capacity=options["intervention_target_capacity"],
    )
    return result


def exact(left, right):
    assert type(left) is type(right)
    assert left._fields == right._fields
    for a, b in zip(left, right, strict=True):
        assert np.asarray(a).dtype == np.asarray(b).dtype
        np.testing.assert_array_equal(a, b)


@pytest.mark.parametrize("family", fixtures.FAMILIES)
@pytest.mark.parametrize("case", ["SIM", "INIT", "ion-flags"])
def test_public_owned_profiles_keep_complete_state_controls_and_checkpoint(family, case, tmp_path):
    schema, model = OWNERS[family]
    raw = definition(family, case)
    spec = parse_spec(raw)
    assert get_model(spec.model) is model
    assert spec == schema.parse(raw) == parse_spec(spec.to_dict())
    assert digest(raw["model"]) == digest(spec.to_dict()["model"])
    owner = schema.owner_spec(spec)
    assert owner.to_dict()["model"]["id"] == schema.PARENT_MODEL_ID
    assert spec.to_dict()["model"]["ionic"] == owner.to_dict()["model"]["ionic"]
    times = sorted({0.0, spec.experiment.end_time, *(c.time for c in spec.experiment.changes)})
    controls = control_values(spec, times)
    exact(controls, control_values(owner, times))
    point, original = initialise(spec), initialise(owner)
    exact(model.parent_state(point.state), original.state)
    exact(model.parent_layout(point.layout), original.layout)
    assert point.state._fields == (*original.state._fields, "phase_clock_s")
    np.testing.assert_array_equal(point.state.phase_clock_s, [0.0])
    write_snapshot(tmp_path / "checkpoint", spec, point)
    restored = load_snapshot(tmp_path / "checkpoint")
    assert restored.spec == spec
    exact(restored.checkpoint.state, point.state)
    exact(restored.checkpoint.layout, point.layout)
    batch = BatchSpec((WorldSpec(29, spec), WorldSpec(83, spec)), 2, 10000, 2**32)
    assert parse_batch(batch.to_dict()) == batch
    assert (
        parse_ensemble(
            dict(model="ionic_worlds@1", simulation=raw, worlds=2, window_steps=2)
        ).simulation
        == spec
    )
    assert plan_windows(spec, WindowPolicy(2)).start_step == 0
    evidence(
        "public-owned-profiles-" + family + "-" + case,
        dict(
            definition=spec.to_dict(),
            state_fields=list(point.state._fields),
            control_fields=list(controls._fields),
            all_parent_arrays_and_layout_exact=True,
            scope="Public identity, snapshot and offline admission; no compiled execution",
        ),
    )


@lru_cache
def evolved_checkpoint(family, phase="SIM"):
    _, model = OWNERS[family]
    spec = parse_spec(definition(family, phase))
    point = initialise(spec)
    state = model.STATE_TYPE(*(np.asarray(v) for v in point.state))
    layout = model.LAYOUT_TYPE(*(np.asarray(v) for v in point.layout))
    table = control_values(spec, [0.0])
    control = type(table)(*(np.asarray(v[0]) for v in table))

    def checked_rhs(trial, u, p, active):
        assert model.control_domain_valid(trial, u, p, active, xp=np)
        return model.rhs(trial, u, p, active, xp=np)

    time = spec.execution.dt
    evolved = rk4_step(checked_rhs, state, time, control, layout, layout.active)
    result = replace(
        point,
        state=evolved,
        time=time,
        step_index=EventGrid(spec).exact_index(time),
        event_index=event_index(spec, time),
    )
    validate_checkpoint(spec, result)
    assert np.any(evolved.channel_transferred != 0)
    assert np.any(evolved.pump_cycles != 0)
    assert any(np.any(a != b) for a, b in zip(evolved[:-1], state[:-1], strict=True))
    return spec, result


@pytest.mark.parametrize("family", fixtures.FAMILIES)
@pytest.mark.parametrize("phase", ["SIM", "INIT"])
def test_evolved_owned_profiles_restore_all_fields_in_fresh_process(family, phase, tmp_path):
    schema, _ = OWNERS[family]
    spec, point = evolved_checkpoint(family, phase)
    folder = write_snapshot(tmp_path / "checkpoint", spec, point)
    restored = load_snapshot(folder)
    exact(restored.checkpoint.state, point.state)
    exact(restored.checkpoint.layout, point.layout)
    code = """
import json,sys,numpy as np
from cells.io import load_snapshot
from cells.core.specs import digest
x=load_snapshot(sys.argv[1])
print(json.dumps(dict(model=x.spec.to_dict()['model']['id'], phase=x.spec.model.phase,
 time=x.checkpoint.time, state_fields=list(x.checkpoint.state._fields),
 state=digest({k:np.asarray(v).tolist() for k,v in x.checkpoint.state._asdict().items()}),
 layout=digest({k:np.asarray(v).tolist() for k,v in x.checkpoint.layout._asdict().items()}))))
"""
    fresh = subprocess.run(
        [sys.executable, "-B", "-c", code, str(folder)],
        check=True,
        capture_output=True,
        text=True,
        timeout=90,
    )
    assert json.loads(fresh.stdout) == dict(
        model=schema.MODEL_ID,
        phase=phase,
        time=point.time,
        state_fields=list(point.state._fields),
        state=digest({k: np.asarray(v).tolist() for k, v in point.state._asdict().items()}),
        layout=digest({k: np.asarray(v).tolist() for k, v in point.layout._asdict().items()}),
    )
    changed = spec.to_dict()
    changed["model"]["phase"] = "INIT" if phase == "SIM" else "SIM"
    with pytest.raises(ConfigError, match="branch may not change model"):
        branch_checkpoint(spec, point, parse_spec(changed))
    for handoff in (passive_handoff, active_handoff):
        with pytest.raises(ConfigError):
            handoff.capture_source(spec, point)
    evidence(
        "public-owned-profiles-evolved-" + family + "-" + phase,
        dict(
            definition=spec.to_dict(),
            state_fields=list(point.state._fields),
            accepted_time=point.time,
            all_state_and_layout_restored_exactly=True,
            scope="One host RK4 step tests checkpoint interfaces, not a refined trajectory",
        ),
        arrays={k: np.asarray(v) for k, v in point.state._asdict().items()},
    )


@pytest.mark.parametrize("family", fixtures.FAMILIES)
@pytest.mark.parametrize("clock", [0.0, -1e-9, float("nan")])
def test_public_owned_profiles_refuse_implicit_clock_reset(family, clock):
    spec, point = evolved_checkpoint(family)
    damaged = replace(point, state=point.state._replace(phase_clock_s=np.asarray([clock])))
    with pytest.raises((ConfigError, NumericalError), match="clock"):
        validate_checkpoint(spec, damaged)


@pytest.mark.parametrize("family", fixtures.FAMILIES)
def test_owned_profiles_do_not_fall_through_to_parent_cuts_or_cohorts(family):
    schema, _ = OWNERS[family]
    spec = parse_spec(definition(family))
    owner = schema.owner_spec(spec)
    point = initialise(spec)
    with pytest.raises(ConfigError):
        validate_checkpoint(spec, initialise(owner))
    with pytest.raises(ConfigError):
        validate_checkpoint(owner, point)
    with pytest.raises(ConfigError, match="Cuts support"):
        excise(spec, point, [spec.model.cells[0].id])
    mixed = BatchSpec((WorldSpec(29, spec), WorldSpec(83, owner)), 2, 10000, 2**32)
    with pytest.raises(ConfigError, match="one model family"):
        parse_batch(mixed.to_dict())
    raw = spec.to_dict()
    raw["execution"]["jit"] = False
    with pytest.raises(ValueError, match="JIT"):
        parse_ensemble(dict(model="ionic_worlds@1", simulation=raw, worlds=1))


@pytest.mark.parametrize("family", fixtures.FAMILIES)
def test_public_owned_profiles_artifact_replay_and_cli(family, tmp_path):
    schema, model = OWNERS[family]
    spec = parse_spec(definition(family))
    record = schema.artifact(spec)
    replayed = schema.replay(record)
    assert replayed == spec and get_model(replayed.model) is model
    path = tmp_path / "profiles.json"
    path.write_text(json.dumps(spec.to_dict()))
    result = cli("validate", path)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["status"] == "valid"
    assert json.loads(path.read_text()) == spec.to_dict()


@pytest.mark.parametrize(
    "filename,module",
    [
        ("resolved_calcium_cav_tissue.json", "surface_calcium_cav"),
        ("resolved_hcn_extra_energy.json", "surface_calcium_energy_hcn_extra"),
        ("resolved_calcium_energy_water.json", "surface_calcium_energy_water"),
        ("resolved_calcium_energy_mitochondria.json", "surface_calcium_energy_mitochondria"),
    ],
)
def test_owned_profile_registration_preserves_existing_family_routes(filename, module):
    root = Path(__file__).resolve().parents[2]
    raw = json.loads((root / "configs" / filename).read_text())
    spec = parse_spec(raw)
    assert get_model(spec.model) is importlib.import_module("cells.models." + module)
    assert parse_spec(spec.to_dict()) == spec
    assert spec.to_dict()["model"]["id"] == raw["model"]["id"]


@pytest.mark.parametrize("family", fixtures.FAMILIES)
def test_public_eager_owned_profile_execution_and_real_restart(family, tmp_path):
    _, model = OWNERS[family]
    spec = parse_spec(definition(family, short=True))
    initial = initialise(spec)
    result = run(spec)
    write_run(tmp_path / "run", result)
    assert result.final.step_index == 2
    for k, values in result.history._asdict().items():
        np.testing.assert_array_equal(values[0], getattr(initial.state, k))
    np.testing.assert_allclose(
        result.observations.phase_clock_s[:, 0], result.times, atol=1e-23, rtol=0
    )
    middle = result.checkpoint_at(spec.execution.dt)
    folder = write_snapshot(tmp_path / "middle", spec, middle)
    restored = load_snapshot(folder)
    resumed = run(restored.spec, restored.checkpoint)
    exact(resumed.final.state, result.final.state)
    exact(resumed.final.layout, result.final.layout)
    for key, values in vars(result.observations).items():
        np.testing.assert_array_equal(getattr(resumed.observations, key), values[1:])
    evidence(
        "public-owned-profiles-eager-" + family,
        dict(
            definition=spec.to_dict(),
            state_fields=list(model.STATE_TYPE._fields),
            observation_fields=list(vars(result.observations)),
            real_steps=result.final.step_index,
            complete_restart_state_layout_observations_exact=True,
            diagnostics=result.diagnostics,
            scope="Two eager CPU steps and real intermediate restart; no compiled qualification",
        ),
    )
