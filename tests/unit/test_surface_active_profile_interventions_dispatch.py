"""Public active-profile identity, complete history and guarded family boundaries.

These check the shared interface. Independent pulse/field equations, closure
trajectories and refinement remain in the component qualification.
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

from cells.core import membrane_profile_phase_handoff as handoff
from cells.core import surface_active_profile_interventions_spec as schema
from cells.core.batch import BatchSpec, WorldSpec, parse_batch
from cells.core.errors import NumericalError
from cells.core.excision import excise
from cells.core.grid import EventGrid
from cells.core.runner import branch_checkpoint, validate_checkpoint
from cells.core.schedule import control_values, event_index
from cells.core.specs import ConfigError, digest, parse_spec
from cells.core.state import initialise
from cells.core.windows import WindowPolicy, plan_windows
from cells.ensemble.ionic import parse_spec as parse_ensemble
from cells.io import load_snapshot, write_snapshot
from cells.models import surface_active_profile_interventions as model
from cells.models.registry import get_model
from cells.numerics.fixed_step import rk4_step
from cells.tissue_profiles import REQUEST_KIND, prepare_request
from tests.integration.test_cli import cli
from tests.unit.test_surface_catalog import evidence
from validation.topology import surface_active_profile_interventions_fixtures as fixtures


def definition(case="SIM"):
    raw = deepcopy(fixtures.inputs(case))
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
        jit=True,
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


@pytest.mark.parametrize("case", ["SIM", "INIT", "ion-flags"])
def test_public_active_profiles_keep_all_owners_controls_and_checkpoint(case, tmp_path):
    raw = definition(case)
    spec = parse_spec(raw)
    assert type(spec.model) is schema.SurfaceActiveProfileInterventionModel
    assert get_model(spec.model) is model
    assert spec == schema.parse(raw) == parse_spec(spec.to_dict())
    assert digest(spec.to_dict()["model"]) == digest(raw["model"])
    times = sorted({0.0, spec.experiment.end_time, *(c.time for c in spec.experiment.changes)})
    controls = control_values(spec, times)
    parent = schema.active_spec(spec)
    exact(controls, control_values(parent, times))
    assert len(controls._fields) == 4
    point, ordinary = initialise(spec), initialise(parent)
    assert len(point.state) == 20
    assert len(spec.model.channels) == 56
    exact(model.parent_state(point.state), ordinary.state)
    exact(model.parent_layout(point.layout), ordinary.layout)
    np.testing.assert_array_equal(point.state.phase_clock_s, [0.0])
    laws = np.asarray(point.layout.channel_laws)[np.asarray(point.layout.channel_active)]
    assert set(laws.tolist()) == set(range(56))
    write_snapshot(tmp_path / "checkpoint", spec, point)
    restored = load_snapshot(tmp_path / "checkpoint")
    assert restored.spec == spec
    exact(restored.checkpoint.state, point.state)
    exact(restored.checkpoint.layout, point.layout)
    batch = BatchSpec((WorldSpec(23, spec), WorldSpec(71, spec)), 2, 10000, 2**32)
    assert parse_batch(batch.to_dict()) == batch
    ensemble = parse_ensemble(
        dict(model="ionic_worlds@1", simulation=spec.to_dict(), worlds=2, window_steps=16)
    )
    assert ensemble.simulation == spec
    assert plan_windows(spec, WindowPolicy(16)).start_step == 0
    evidence(
        "registered-active-profiles-" + case,
        dict(
            definition=spec.to_dict(),
            state_fields=list(point.state._fields),
            control_fields=list(controls._fields),
            control_times=times,
            checkpoint_and_layout_exact=True,
            scope="Public identity, full initial state and offline admission; no compiled run",
        ),
    )


@lru_cache
def evolved_checkpoint(phase="SIM"):
    spec = parse_spec(definition(phase))
    point = initialise(spec)
    state = model.STATE_TYPE(*(np.asarray(value) for value in point.state))
    layout = model.LAYOUT_TYPE(*(np.asarray(value) for value in point.layout))
    table = control_values(spec, [0.0])
    control = type(table)(*(np.asarray(value[0]) for value in table))

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
    assert np.any(evolved.channel_gate != state.channel_gate)
    assert np.any(evolved.channel_transferred != 0)
    assert np.any(evolved.pump_cycles != 0)
    return spec, result


@pytest.mark.parametrize("phase", ["SIM", "INIT"])
def test_evolved_active_profile_snapshot_keeps_gates_work_and_phase_in_fresh_process(
    phase, tmp_path
):
    spec, point = evolved_checkpoint(phase)
    folder = write_snapshot(tmp_path / "checkpoint", spec, point)
    restored = load_snapshot(folder)
    exact(restored.checkpoint.state, point.state)
    exact(restored.checkpoint.layout, point.layout)
    code = """
import json,sys,numpy as np
from cells.io import load_snapshot
from cells.core.specs import digest
x=load_snapshot(sys.argv[1])
values={k:np.asarray(v).tolist() for k,v in x.checkpoint.state._asdict().items()}
print(json.dumps(dict(model=x.spec.to_dict()['model']['id'], phase=x.spec.model.phase,
    time=x.checkpoint.time, clock=float(x.checkpoint.state.phase_clock_s[0]),
    fields=list(x.checkpoint.state._fields),
    state_digest=digest(values))))
"""
    result = subprocess.run(
        [sys.executable, "-B", "-c", code, str(folder)],
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    assert json.loads(result.stdout) == dict(
        model=schema.MODEL_ID,
        phase=phase,
        time=point.time,
        clock=float(point.state.phase_clock_s[0]),
        fields=list(point.state._fields),
        state_digest=digest({k: np.asarray(v).tolist() for k, v in point.state._asdict().items()}),
    )
    changed = spec.to_dict()
    changed["model"]["phase"] = "INIT" if phase == "SIM" else "SIM"
    with pytest.raises(ConfigError, match="branch may not change model"):
        branch_checkpoint(spec, point, parse_spec(changed))
    with pytest.raises(ConfigError):
        handoff.capture_source(spec, point)
    evidence(
        "registered-active-evolved-" + phase,
        dict(
            definition=spec.to_dict(),
            state_fields=list(point.state._fields),
            time=point.time,
            clock=float(point.state.phase_clock_s[0]),
            fresh_process_restored=True,
            implicit_phase_change_refused=True,
            scope="One host RK4 step checks checkpoint interfaces; no trajectory qualification",
        ),
        arrays={k: np.asarray(v) for k, v in point.state._asdict().items()},
    )


@pytest.mark.parametrize("clock", [0.0, -1e-9, float("nan")])
def test_public_active_checkpoint_refuses_evolved_phase_clock_reset(clock):
    spec, point = evolved_checkpoint()
    damaged = replace(point, state=point.state._replace(phase_clock_s=np.asarray([clock])))
    with pytest.raises((ConfigError, NumericalError), match="clock"):
        validate_checkpoint(spec, damaged)
    assert float(point.state.phase_clock_s[0]) > 0


def test_active_profiles_refuse_parent_checkpoint_cut_cohort_and_eager_ensemble():
    spec = parse_spec(definition())
    parent = schema.active_spec(spec)
    point = initialise(spec)
    with pytest.raises(ConfigError):
        validate_checkpoint(spec, initialise(parent))
    with pytest.raises(ConfigError, match="Cuts support"):
        excise(spec, point, [spec.model.cells[0].id])
    batch = BatchSpec((WorldSpec(23, spec), WorldSpec(71, parent)), 2, 10000, 2**32)
    with pytest.raises(ConfigError, match="one model family"):
        parse_batch(batch.to_dict())
    raw = spec.to_dict()
    raw["execution"]["jit"] = False
    with pytest.raises(ValueError, match="JIT"):
        parse_ensemble(dict(model="ionic_worlds@1", simulation=raw, worlds=1))


def test_public_cli_validates_complete_active_profile_definition(tmp_path):
    path = tmp_path / "active-profiles.json"
    path.write_text(json.dumps(definition()))
    saved = path.read_bytes()
    result = cli("validate", path)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["status"] == "valid"
    assert path.read_bytes() == saved


def test_portable_active_profile_example_replays_through_public_parser():
    folder = Path(__file__).resolve().parents[2] / "examples/scheduled_active_membrane_profiles"
    raw = json.loads((folder / "definition.json").read_text())
    record = json.loads((folder / "artifact.json").read_text())
    replayed = schema.replay(record)
    public = parse_spec(raw)
    assert replayed == public
    assert digest(public.to_dict()) == digest(raw)
    assert get_model(public.model) is model
    assert len(public.model.channels) == 56
    before = initialise(public)
    after = initialise(replayed)
    exact(after.state, before.state)
    exact(after.layout, before.layout)


@pytest.mark.parametrize(
    "filename,module",
    [
        ("resolved_hcn_extra_ionic.json", "surface_hcn_extra"),
        ("resolved_hcn_extra_energy.json", "surface_calcium_energy_hcn_extra"),
        ("resolved_calcium_energy_network_transport.json", "surface_calcium_energy_transport"),
        ("resolved_calcium_energy_mitochondria.json", "surface_calcium_energy_mitochondria"),
        ("resolved_calcium_energy_water.json", "surface_calcium_energy_water"),
    ],
)
def test_active_profile_registration_preserves_parent_and_composed_dispatch(filename, module):
    raw = json.loads((Path(__file__).resolve().parents[2] / "configs" / filename).read_text())
    spec = parse_spec(raw)
    assert get_model(spec.model) is importlib.import_module("cells.models." + module)
    assert parse_spec(spec.to_dict()) == spec
    assert spec.to_dict()["model"]["id"] == raw["model"]["id"]
