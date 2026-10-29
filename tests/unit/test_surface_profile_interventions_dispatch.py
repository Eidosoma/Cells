"""Public model admission must retain the complete phase and profile contracts.

These are dispatch, checkpoint and planning checks. The component's independent
equations and pulse histories supply separate physical evidence.
"""

import importlib
import json
import subprocess
import sys
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from cells.core import surface_profile_interventions_spec as schema
from cells.core.batch import BatchSpec, WorldSpec, parse_batch
from cells.core.errors import NumericalError
from cells.core.excision import excise
from cells.core.grid import EventGrid
from cells.core.runner import branch_checkpoint, validate_checkpoint
from cells.core.schedule import control_values, event_index
from cells.core.specs import ConfigError, digest, parse_spec
from cells.core.state import initialise
from cells.ensemble.ionic import parse_spec as parse_ensemble
from cells.io import load_snapshot, write_snapshot
from cells.models import surface_profile_interventions as model
from cells.models.registry import get_model
from cells.numerics.fixed_step import rk4_step
from cells.tissue_profiles import REQUEST_KIND, prepare_request
from tests.integration.test_cli import cli
from tests.unit.test_surface_catalog import evidence
from validation.topology import surface_profile_interventions_fixtures as fixtures


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


@pytest.mark.parametrize("phase", ["SIM", "INIT", "guards"])
def test_public_profile_dispatch_keeps_phase_rules_owners_controls_and_checkpoint(phase, tmp_path):
    raw = definition(phase)
    spec = parse_spec(raw)
    assert type(spec.model) is schema.SurfaceProfileInterventionModel
    assert get_model(spec.model) is model
    assert spec == schema.parse(raw) == parse_spec(spec.to_dict())
    for key in ("profile_preparation", "interventions", "phase", "timing_policy", "reset_policy"):
        assert digest(spec.to_dict()["model"][key]) == digest(raw["model"][key])
    times = sorted({0.0, spec.experiment.end_time, *(c.time for c in spec.experiment.changes)})
    exact(control_values(spec, times), control_values(schema.base_spec(spec), times))
    point = initialise(spec)
    assert point.state.phase_clock_s.shape == (1,)
    np.testing.assert_array_equal(point.state.phase_clock_s, [0.0])
    write_snapshot(tmp_path / "checkpoint", spec, point)
    restored = load_snapshot(tmp_path / "checkpoint")
    assert restored.spec == spec
    exact(restored.checkpoint.state, point.state)
    exact(restored.checkpoint.layout, point.layout)
    assert restored.checkpoint.time == point.time
    assert restored.checkpoint.step_index == point.step_index
    assert restored.checkpoint.event_index == point.event_index
    batch = BatchSpec((WorldSpec(23, spec), WorldSpec(71, spec)), 2, 10000, 2**32)
    assert parse_batch(batch.to_dict()) == batch
    ensemble = parse_ensemble(
        dict(model="ionic_worlds@1", simulation=spec.to_dict(), worlds=1, window_steps=1)
    )
    assert ensemble.simulation == spec
    evidence(
        "registered-membrane-profiles-" + phase,
        dict(
            definition=spec.to_dict(),
            state_fields=list(point.state._fields),
            control_fields=list(control_values(spec, times)._fields),
            control_times=times,
            checkpoint_and_layout_exact=True,
            scope="Public dispatch, complete initial checkpoint and offline admission only",
        ),
    )


@pytest.mark.parametrize("clock", [1e-6, -1e-6, float("nan")])
def test_registered_checkpoint_rejects_changed_phase_clock(clock):
    spec = parse_spec(definition())
    point = initialise(spec)
    validate_checkpoint(spec, point)
    damaged = replace(point, state=point.state._replace(phase_clock_s=np.asarray([clock])))
    with pytest.raises((ConfigError, NumericalError), match="clock"):
        validate_checkpoint(spec, damaged)
    np.testing.assert_array_equal(point.state.phase_clock_s, [0.0])


@pytest.mark.parametrize("phase", ["SIM", "INIT"])
def test_public_evolved_checkpoint_preserves_phase_clock_and_refuses_implicit_reset(
    phase, tmp_path
):
    raw = definition(phase)
    spec = parse_spec(raw)
    initial = initialise(spec)
    state = model.STATE_TYPE(*(np.asarray(v) for v in initial.state))
    layout = model.LAYOUT_TYPE(*(np.asarray(v) for v in initial.layout))
    table = control_values(spec, [0.0])
    control = type(table)(*(np.asarray(v[0]) for v in table))

    def checked_rhs(trial, u, p, active):
        assert model.control_domain_valid(trial, u, p, active, xp=np)
        return model.rhs(trial, u, p, active, xp=np)

    time = spec.execution.dt
    evolved = rk4_step(checked_rhs, state, time, control, layout, layout.active)
    point = replace(
        initial,
        state=evolved,
        time=time,
        step_index=EventGrid(spec).exact_index(time),
        event_index=event_index(spec, time),
    )
    validate_checkpoint(spec, point)
    assert float(point.state.phase_clock_s[0]) > 0
    folder = tmp_path / "checkpoint"
    write_snapshot(folder, spec, point)
    restored = load_snapshot(folder)
    exact(restored.checkpoint.state, point.state)
    exact(restored.checkpoint.layout, point.layout)
    assert restored.checkpoint.time == time
    process = subprocess.run(
        [
            sys.executable,
            "-B",
            "-c",
            "import json,sys; from cells.io import load_snapshot; "
            "x=load_snapshot(sys.argv[1]); "
            "print(json.dumps(dict(phase=x.spec.model.phase, time=x.checkpoint.time, "
            "phase_clock=float(x.checkpoint.state.phase_clock_s[0]))))",
            str(folder),
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout) == dict(
        phase=phase, time=time, phase_clock=float(point.state.phase_clock_s[0])
    )
    reset = replace(point, state=point.state._replace(phase_clock_s=np.zeros(1)))
    refused = tmp_path / "reset-refused"
    with pytest.raises(ConfigError, match="clock"):
        write_snapshot(refused, spec, reset)
    assert not refused.exists()
    changed = deepcopy(raw)
    changed["model"]["phase"] = "INIT" if phase == "SIM" else "SIM"
    with pytest.raises(ConfigError, match="branch may not change model"):
        branch_checkpoint(spec, point, parse_spec(changed))
    evidence(
        "registered-membrane-evolved-checkpoint-" + phase,
        dict(
            definition=spec.to_dict(),
            physical_steps=1,
            state_fields=list(point.state._fields),
            phase=phase,
            saved_time=time,
            phase_clock=float(point.state.phase_clock_s[0]),
            fresh_process_restored=True,
            reset_and_phase_change_refused=True,
            scope="One host RK4 step for checkpoint interfaces, not trajectory qualification",
        ),
    )


def test_scheduled_profiles_cannot_fall_through_to_passive_cuts_or_cohorts():
    spec = parse_spec(definition())
    point = initialise(spec)
    with pytest.raises(ConfigError, match="Cuts support"):
        excise(spec, point, [spec.model.cells[0].id])
    batch = BatchSpec((WorldSpec(23, spec), WorldSpec(71, schema.base_spec(spec))), 2, 10000, 2**32)
    with pytest.raises(ConfigError, match="one model family"):
        parse_batch(batch.to_dict())


def test_public_cli_validates_the_complete_scheduled_profile_model(tmp_path):
    raw = definition()
    path = tmp_path / "scheduled.json"
    path.write_text(json.dumps(raw))
    saved = path.read_bytes()
    result = cli("validate", path)
    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)
    assert summary["status"] == "valid"
    assert path.read_bytes() == saved


@pytest.mark.parametrize(
    "filename,module",
    [
        ("resolved_hcn_extra_energy.json", "surface_calcium_energy_hcn_extra"),
        ("resolved_calcium_energy_network_transport.json", "surface_calcium_energy_transport"),
        ("resolved_calcium_energy_mitochondria.json", "surface_calcium_energy_mitochondria"),
        ("resolved_calcium_energy_water.json", "surface_calcium_energy_water"),
    ],
)
def test_profile_registration_preserves_existing_physical_families(filename, module):
    raw = json.loads((Path(__file__).resolve().parents[2] / "configs" / filename).read_text())
    spec = parse_spec(raw)
    assert get_model(spec.model) is importlib.import_module("cells.models." + module)
    assert parse_spec(spec.to_dict()) == spec
    assert spec.to_dict()["model"]["id"] == raw["model"]["id"]
