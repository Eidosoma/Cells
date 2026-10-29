"""An evolved active INIT hands every owner, gate and ledger to an explicit SIM."""

import ast
import json
import os
import subprocess
import sys
from copy import deepcopy
from dataclasses import replace
from functools import lru_cache
from pathlib import Path

import numpy as np
import pytest

from cells.core import active_membrane_profile_phase_handoff as adapter
from cells.core import surface_active_profile_epoch_spec as definition
from cells.core import surface_active_profile_interventions_spec as scheduled_spec
from cells.core import tissue_profile_preparation as static
from cells.core.errors import NumericalError
from cells.core.grid import EventGrid
from cells.core.runner import branch_checkpoint, validate_checkpoint
from cells.core.schedule import control_values, event_index
from cells.core.specs import ConfigError, digest, parse_spec
from cells.core.state import Checkpoint
from cells.models import surface_active_profile_epoch as model
from cells.models import surface_active_profile_interventions as scheduled
from cells.models.registry import get_model
from cells.numerics.fixed_step import rk4_step
from cells.processes import betse_tissue_profiles as native
from validation.topology import active_membrane_profile_phase_handoff_fixtures as fixtures
from validation.topology import active_membrane_profile_phase_handoff_reference as reference

ROOT = Path(os.environ.get("CELLS_COMPONENT_SOURCE_ROOT", Path(__file__).resolve().parents[2]))


def evidence(name, value, arrays=None):
    if directory := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        path = Path(directory)
        path.mkdir(parents=True, exist_ok=True)
        stem = "active-phase-" + name
        (path / (stem + ".json")).write_text(
            json.dumps(
                dict(value, status="passed"),
                indent=2,
                allow_nan=False,
                default=lambda v: v.tolist(),
            )
            + "\n"
        )
        if arrays is not None:
            np.savez(path / (stem + ".npz"), **arrays)


@lru_cache
def prepared_definition():
    raw = fixtures.inputs()
    geometry = raw["geometry"]
    layout = geometry.pop("layout")
    value = static.prepare(
        raw["definition"],
        static.Geometry(native.Layout(**layout), **geometry),
        static._decode_profile(raw["default"]),
        [static._decode_profile(row) for row in raw["profiles"]],
        ion_enabled=raw["ion_enabled"],
        enabled=raw["enabled"],
        is_ecm=raw["is_ecm"],
    )
    result = deepcopy(value.definition)
    result["model"].update(
        id=scheduled_spec.MODEL_ID,
        profile_preparation=dict(definition=value.definition, provenance=value.provenance),
        interventions=raw["interventions"],
        phase="INIT",
        timing_policy=scheduled_spec.TIMING_POLICY,
        reset_policy=scheduled_spec.RESET_POLICY,
    )
    result["execution"].update(
        intervention_capacity=raw["intervention_capacity"],
        intervention_target_capacity=raw["intervention_target_capacity"],
    )
    return result


def control(spec, time):
    table = control_values(spec, [time])
    return type(table)(*(v[0] for v in table))


def integrate_host(spec, impl):
    state, layout = impl.initial_values(spec)
    times = np.asarray(list(EventGrid(spec)))
    table = control_values(spec, times[:-1])
    impl.check_steps(spec, np.diff(times), table)
    states = [state]

    def rhs(y, *args):
        result = impl.rhs(y, *args, xp=np)
        assert all(np.isfinite(v).all() for v in result)
        return result

    for index, step in enumerate(np.diff(times)):
        u = type(table)(*(v[index] for v in table))
        state = rk4_step(rhs, state, step, u, layout, layout.active)
        states.append(state)
    history = impl.STATE_TYPE(*(np.stack(v) for v in zip(*states, strict=True)))
    diagnostics = impl.check_values(history, spec)
    return times, states, layout, diagnostics


@lru_cache
def source_run(refinement=1):
    raw, _ = fixtures.definitions(prepared_definition())
    raw["execution"]["dt"] /= refinement
    spec = scheduled_spec.parse(raw)
    return spec, integrate_host(spec, scheduled)


def source_checkpoint(time=fixtures.INIT_END):
    spec, (times, states, layout, _) = source_run()
    index = EventGrid(spec).exact_index(time)
    assert times[index] == time
    return spec, Checkpoint(states[index], layout, time, index, event_index(spec, time))


@lru_cache
def prepared(case="changed-controls", time=fixtures.INIT_END):
    source, checkpoint = source_checkpoint(time)
    _, target = fixtures.definitions(prepared_definition(), case)
    request = dict(
        kind=adapter.REQUEST_KIND,
        policies=deepcopy(definition.POLICIES),
        source=adapter.capture_source(source, checkpoint),
        simulation=target,
    )
    result = adapter.prepare(request)
    return request, result, parse_spec(result.definition), source, checkpoint


def score(context, actual, expected, *, rtol=3e-10, atol=3e-12, charge_atol=3e-23):
    observed = (
        reference.scheduled.flatten(context, actual._asdict())
        if hasattr(actual, "_asdict")
        else np.asarray(actual)
    )
    budget = np.r_[
        reference.scheduled.active.flatten(
            context["parent"],
            {
                name: np.full(shape, charge_atol if name.endswith("_C") else atol)
                for name, shape in context["parent"]["shapes"].items()
            },
        ),
        atol,
    ] + rtol * np.abs(expected)
    ratio = float(np.max(np.abs(observed - expected) / budget, initial=0))
    assert ratio <= 1, ratio
    return ratio


def assert_conservation(proof):
    for name in ("local_residual_fmol", "outside_residual_fmol", "global_residual_fmol"):
        np.testing.assert_allclose(proof[name], 0, rtol=0, atol=3e-14)
    for name in (
        "capacitor_charge_residual_C",
        "electrode_charge_residual_C",
        "global_charge_residual_C",
    ):
        np.testing.assert_allclose(proof[name], 0, rtol=0, atol=3e-25)
    assert abs(proof["energy_residual_pJ"]) < 1e-10


def compare_stage(raw, spec, state, layout, time):
    c = reference.scheduled.bind(raw)
    trial = state._replace(phase_clock_s=np.asarray([time]))
    actual = model.readouts(trial, control(spec, time), layout, xp=np)
    flat = reference.scheduled.flatten(c, trial._asdict())
    slope, phi, proof = reference.scheduled.evaluate(c, flat)
    ratio = score(c, actual.derivative, slope)
    rhs = model.rhs(trial, control(spec, time), layout, layout.active, xp=np)
    assert type(rhs) is model.STATE_TYPE
    for a, b in zip(rhs, actual.derivative, strict=True):
        np.testing.assert_array_equal(a, b)
    n = layout.active.size
    observed_phi = np.r_[
        actual.field.potential_V[:n][layout.active],
        actual.field.potential_V[n:][layout.outside_active],
    ]
    np.testing.assert_allclose(observed_phi, phi, rtol=3e-10, atol=3e-13)
    expected = reference.scheduled.field_observables(c, flat, slope, phi)
    observed = {
        k: getattr(actual.field, k)
        for k in (
            "membrane_voltage_rate_V_s",
            "electrode_current_A",
            "chemical_energy_rate_pJ_s",
            "capacitor_energy_rate_pJ_s",
            "dissipation_pJ_s",
            "reservoir_power_pJ_s",
            "electrode_power_pJ_s",
            "energy_balance_pJ_s",
        )
    }
    for key in (
        "membrane_flux_fmol_s",
        "membrane_current_A",
        "membrane_voltage_V",
        "junction_voltage_V",
        "membrane_dissipation_pJ_s",
        "junction_dissipation_pJ_s",
        "face_dissipation_pJ_s",
    ):
        value = getattr(actual.field.rates, key)
        observed[key] = value[..., : np.asarray(expected[key]).shape[-1]]
    observed.update(
        channel_flux_fmol_s=actual.parent.channel_flux_fmol_s[:, : len(spec.model.channels)],
        pump_cycles=actual.derivative.pump_cycles[: len(spec.model.membranes)],
        metabolic_power_pJ_s=float(np.sum(actual.derivative.metabolic_work_pJ)),
    )
    observed["membrane_voltage_rate_V_s"] = observed["membrane_voltage_rate_V_s"][
        : len(spec.model.membranes)
    ]
    observed["electrode_current_A"] = observed["electrode_current_A"][
        : len(spec.model.extracellular)
    ]
    assert set(observed) == set(expected)
    for key, value in observed.items():
        atol = (
            3e-23
            if key.endswith("_A")
            else 3e-13
            if key.endswith("_V")
            else 3e-8
            if key.endswith("_V_s")
            else 3e-10
        )
        np.testing.assert_allclose(value, expected[key], rtol=3e-10, atol=atol, err_msg=key)
    assert actual.valid and abs(actual.field.energy_balance_pJ_s) < 1e-10
    return dict(time_s=time, error_over_budget=ratio, independent=proof, field_keys=list(expected))


def test_evolved_full_catalog_INIT_refines_at_all_saved_times_against_independent_solution():
    source, _ = source_run()
    raw = source.to_dict()
    context = reference.scheduled.bind(raw)
    expected, proof = reference.integrate(raw)
    assert len(context["parent"]["shapes"]) == 19
    assert len({c["kinetic_law"] for c in raw["model"]["channels"]}) == 56
    outcomes, arrays = [], dict(reference=proof["observations"])
    for refinement in (1, 2):
        spec, (times, states, _, diagnostics) = source_run(refinement)
        actual = np.stack(
            [
                reference.scheduled.flatten(
                    context, states[EventGrid(spec).exact_index(t)]._asdict()
                )
                for t in proof["observation_times_s"]
            ]
        )
        ratio = score(
            context, actual, proof["observations"], rtol=3e-9, atol=2e-11, charge_atol=3e-25
        )
        conservation = reference.scheduled.conservation(context, actual[-1])
        assert_conservation(conservation)
        arrays[str(refinement)] = actual
        outcomes.append(
            dict(
                refinement=refinement,
                dt_s=spec.execution.dt,
                error_over_budget=ratio,
                max_error=float(np.max(np.abs(actual - proof["observations"]))),
                diagnostics=diagnostics,
                conservation=conservation,
            )
        )
    state = states[-1]
    initial, _ = scheduled.initial_values(spec)
    for key in (
        "amount_increment",
        "membrane_transferred",
        "channel_transferred",
        "pump_cycles",
        "metabolic_work_pJ",
    ):
        assert np.any(getattr(state, key) != 0), key
    assert np.any(state.channel_gate != initial.channel_gate)
    assert np.any(state.junction_gate != initial.junction_gate)
    assert outcomes[-1]["max_error"] <= max(0.2 * outcomes[0]["max_error"], 3e-13)
    evidence(
        "INIT-refinement",
        dict(
            source=raw,
            independent={k: v for k, v in proof.items() if k != "observations"},
            refinements=outcomes,
            full_state_fields=20,
            all_channel_laws=56,
        ),
        arrays,
    )


@pytest.mark.parametrize("case", fixtures.CASES)
def test_all_19_parent_fields_gates_owners_and_original_accounting_survive_handoff(case):
    request, result, spec, source, checkpoint = prepared(case)
    state, layout = model.initial_values(spec)
    assert type(state) is model.STATE_TYPE and type(layout) is model.LAYOUT_TYPE
    assert type(state) is not scheduled.STATE_TYPE and type(layout) is not scheduled.LAYOUT_TYPE
    assert len(state) == 20 and len(scheduled.parent_state(state)) == 19
    for a, b in zip(
        scheduled.parent_state(checkpoint.state), scheduled.parent_state(state), strict=True
    ):
        assert a.dtype == b.dtype and a.shape == b.shape and a.tobytes() == b.tobytes()
    for a, b in zip(
        scheduled.parent_layout(checkpoint.layout), scheduled.parent_layout(layout), strict=True
    ):
        assert a.dtype == b.dtype and a.shape == b.shape and a.tobytes() == b.tobytes()
    np.testing.assert_array_equal(state.phase_clock_s, [0.0])
    assert result.provenance["clocks"] == dict(
        init_checkpoint_time_s=checkpoint.time,
        init_phase_clock_s=float(checkpoint.state.phase_clock_s[0]),
        sim_epoch_time_s=0.0,
        sim_phase_clock_s=0.0,
    )
    context, flat = reference.initial(request)
    np.testing.assert_array_equal(reference.scheduled.flatten(context, state._asdict()), flat)
    before = reference.scheduled.conservation(
        reference.scheduled.bind(source.to_dict()),
        reference.scheduled.flatten(context, checkpoint.state._asdict()),
    )
    after = reference.scheduled.conservation(context, flat)
    for key in before:
        np.testing.assert_array_equal(before[key], after[key])
    assert_conservation(after)
    assert model.check_values(state, spec) == scheduled.check_values(checkpoint.state, source) | {
        "phase_clock_final_s": 0.0
    }
    assert (
        definition.scheduled_spec(spec).model.profile_preparation
        == source.model.profile_preparation
    )
    evidence(
        "preservation-" + case,
        dict(
            request=request,
            definition=result.definition,
            provenance=result.provenance,
            carried_fields=list(scheduled.parent_state(state)._fields),
            conservation=after,
        ),
    )


@pytest.mark.parametrize("case", fixtures.CASES)
def test_complete_SIM_fields_all_56_laws_and_full_rhs_from_evolved_INIT(case):
    request, _, spec, _, _ = prepared(case)
    state, layout = model.initial_values(spec)
    stages = [
        compare_stage(request["simulation"], spec, state, layout, time)
        for time in (0.0, 1e-6, 2.5e-6, 3e-6, 4e-6, 5e-6, 7e-6, 8e-6)
    ]
    evidence("SIM-stages-" + case, dict(stages=stages, full_state_fields=20, all_channel_laws=56))


@pytest.mark.parametrize("case", ["changed-controls", "close-reopen"])
def test_carried_SIM_trajectory_refines_with_every_gate_and_global_ledger(case):
    request, _, original, _, checkpoint = prepared(case)
    context, initial = reference.initial(request)
    _, proof = reference.integrate(request["simulation"], initial_state=initial)
    np.testing.assert_array_equal(initial, reference.initial(request)[1])
    outcomes, arrays = [], dict(reference=proof["observations"], times=proof["observation_times_s"])
    for refinement in (1, 2):
        spec = replace(
            original, execution=replace(original.execution, dt=original.execution.dt / refinement)
        )
        times, states, layout, diagnostics = integrate_host(spec, model)
        grid = EventGrid(spec)
        actual = np.stack(
            [
                reference.scheduled.flatten(context, states[grid.exact_index(t)]._asdict())
                for t in proof["observation_times_s"]
            ]
        )
        ratio = score(
            context, actual, proof["observations"], rtol=3e-9, atol=2e-11, charge_atol=3e-25
        )
        conservation = reference.scheduled.conservation(context, actual[-1])
        assert_conservation(conservation)
        arrays[str(refinement)] = actual
        outcomes.append(
            dict(
                refinement=refinement,
                dt_s=spec.execution.dt,
                error_over_budget=ratio,
                max_error=float(np.max(np.abs(actual - proof["observations"]))),
                diagnostics=diagnostics,
                conservation=conservation,
            )
        )
    assert outcomes[-1]["max_error"] <= max(0.2 * outcomes[0]["max_error"], 3e-13)
    assert np.sum(states[-1].metabolic_work_pJ) > np.sum(checkpoint.state.metabolic_work_pJ)
    assert np.sum(states[-1].channel_dissipated_energy_pJ) > np.sum(
        checkpoint.state.channel_dissipated_energy_pJ
    )
    if case == "close-reopen":
        proofs, permeability = [], []
        sodium = spec.model.species_ids.index("Na")
        for time in (0.0, 4e-6, 8e-6):
            current = states[grid.exact_index(time)]
            value = model.readouts(current, control(spec, time), layout, xp=np)
            proofs.append(compare_stage(request["simulation"], spec, current, layout, time))
            assert np.any(current.membrane_transferred != 0)
            permeability.append(np.asarray(value.signal.permeability[sodium]))
        closed = (
            (permeability[1] == 0)
            & layout.membrane_active
            & (layout.membrane_permeability[sodium] > 0)
        )
        assert np.any(closed)
        assert np.all(permeability[0][closed] > 0) and np.all(permeability[2][closed] > 0)
        assert np.any(checkpoint.state.membrane_transferred[sodium][closed] != 0)
        evidence(
            "evolved-closure-fields", dict(stages=proofs, full_history_conservation_checked=True)
        )
    evidence(
        "SIM-refinement-" + case,
        dict(
            INIT_duration_s=checkpoint.time,
            SIM_duration_s=spec.experiment.end_time,
            request_sha256=digest(request),
            source_identity=request["source"]["identity"],
            independent={k: v for k, v in proof.items() if k != "observations"},
            refinements=outcomes,
            original_accounting_origin_retained=True,
        ),
        arrays,
    )


def test_interior_INIT_checkpoint_portable_recipe_and_exact_typed_replay(tmp_path):
    request, result, spec, source, checkpoint = prepared(time=4e-6)
    assert checkpoint.time < source.experiment.end_time
    assert get_model(spec.model) is model
    assert parse_spec(spec.to_dict()) == spec
    identity = digest(request)
    assert adapter.prepare(deepcopy(request)) == result and digest(request) == identity
    assert adapter.replay(json.loads(json.dumps(result.provenance))) == result
    path = adapter.write_preparation(tmp_path / "handoff", result)
    assert adapter.read_preparation(path) == result
    with pytest.raises(ConfigError):
        adapter.write_preparation(path, result)
    decoded, point = adapter.decode_source(request["source"])
    assert decoded == source
    for a, b in zip(point.state, checkpoint.state, strict=True):
        np.testing.assert_array_equal(a, b)
    evidence(
        "portable-interior",
        dict(
            definition=result.definition,
            provenance=result.provenance,
            interior_INIT_checkpoint=True,
            exact_typed_replay=True,
        ),
    )


@pytest.mark.parametrize(
    "fault",
    [
        "SIM-source",
        "channel-owner",
        "channel-gate",
        "junction-gate",
        "channel-history",
        "pump-history",
        "channel-energy",
        "metabolic-work",
        "clock",
        "step",
        "precision",
        "padding",
    ],
)
def test_source_owner_gate_history_clock_and_precision_refusals(fault):
    source, checkpoint = source_checkpoint()
    if fault == "SIM-source":
        source = replace(source, model=replace(source.model, phase="SIM"))
    elif fault == "channel-owner":
        value = np.array(checkpoint.layout.channel_membranes)
        value[0] = 1 - value[0]
        checkpoint = replace(checkpoint, layout=checkpoint.layout._replace(channel_membranes=value))
    elif fault == "step":
        checkpoint = replace(checkpoint, step_index=checkpoint.step_index - 1)
    else:
        key = {
            "channel-gate": "channel_gate",
            "junction-gate": "junction_gate",
            "channel-history": "channel_transferred",
            "pump-history": "pump_cycles",
            "channel-energy": "channel_dissipated_energy_pJ",
            "metabolic-work": "metabolic_work_pJ",
            "clock": "phase_clock_s",
            "precision": "amount_increment",
            "padding": "amount_increment",
        }[fault]
        value = np.array(getattr(checkpoint.state, key))
        if fault in ("channel-gate", "junction-gate"):
            value.flat[0] = 1.1
        elif fault in ("channel-history", "pump-history", "clock"):
            value[:] = 0.0
        elif fault == "precision":
            value = value.astype(np.float32)
        elif fault == "padding":
            assert value.shape[1] > len(source.model.cells)
            value[0, -1] = 1e-4
        else:
            value.flat[0] += 1e-4
        checkpoint = replace(checkpoint, state=checkpoint.state._replace(**{key: value}))
    with pytest.raises((ConfigError, NumericalError)):
        adapter.capture_source(source, checkpoint)


@pytest.mark.parametrize(
    "fault",
    [
        "source-seal",
        "missing-gate",
        "typed-bool",
        "typed-owner-overflow",
        "shape-bool",
        "target-INIT",
        "changed-volume",
        "changed-channel",
        "changed-channel-capacity",
        "reset-policy",
    ],
)
def test_request_cannot_rewrite_typed_owners_static_parent_or_reset_policy(fault):
    original, _, _, _, _ = prepared()
    request = deepcopy(original)
    source = request["source"]
    if fault == "source-seal":
        source["identity"] = "0" * 64
    elif fault == "missing-gate":
        source["checkpoint"]["state"].pop("channel_gate")
    elif fault == "typed-bool":
        source["checkpoint"]["state"]["channel_gate"]["values"][0][0] = True
    elif fault == "typed-owner-overflow":
        source["checkpoint"]["layout"]["channel_membranes"]["values"][0] += 2**64
    elif fault == "shape-bool":
        source["checkpoint"]["state"]["phase_clock_s"]["shape"] = [True]
    elif fault == "target-INIT":
        request["simulation"]["model"]["phase"] = "INIT"
    elif fault == "changed-volume":
        request["simulation"]["model"]["cells"][0]["volume_pL"] *= 2
    elif fault == "changed-channel":
        channel = request["simulation"]["model"]["channels"][0]
        channel["membrane_id"] = next(
            row["id"]
            for row in request["simulation"]["model"]["membranes"]
            if row["id"] != channel["membrane_id"]
        )
    elif fault == "changed-channel-capacity":
        request["simulation"]["execution"]["channel_capacity"] += 1
    else:
        request["policies"]["state_policy"] = "erase_all_work_and_gates"
    if fault in ("missing-gate", "typed-bool", "typed-owner-overflow", "shape-bool"):
        source.pop("identity")
        source["identity"] = digest(source)
    with pytest.raises((ConfigError, NumericalError)):
        adapter.prepare(request)


def test_epoch_seals_clocks_and_ordinary_resume_cannot_create_transition():
    _, result, spec, source, checkpoint = prepared()
    for name in (
        "init_checkpoint_time_s",
        "init_phase_clock_s",
        "sim_epoch_time_s",
        "sim_phase_clock_s",
    ):
        raw = deepcopy(result.definition)
        raw["model"]["handoff"]["clocks"][name] += 1e-6
        with pytest.raises(ConfigError):
            parse_spec(raw)
    provenance = deepcopy(result.provenance)
    provenance["preservation"]["cell_amount_fmol"][0][0] += 1.0
    provenance.pop("identity")
    provenance["identity"] = digest(provenance)
    with pytest.raises(ConfigError):
        adapter.replay(provenance)
    with pytest.raises(ConfigError):
        branch_checkpoint(source, checkpoint, spec)
    with pytest.raises(ConfigError):
        validate_checkpoint(spec, checkpoint)
    state, layout = model.initial_values(spec)
    start = Checkpoint(state, layout, 0.0, 0, event_index(spec, 0.0))
    validate_checkpoint(spec, start)
    zero, _ = scheduled.initial_values(definition.scheduled_spec(spec))
    with pytest.raises(ConfigError, match="initial state"):
        validate_checkpoint(spec, replace(start, state=model.STATE_TYPE(*zero)))
    with pytest.raises(ConfigError):
        validate_checkpoint(
            spec, replace(start, state=state._replace(phase_clock_s=checkpoint.state.phase_clock_s))
        )


def test_independent_complete_dependency_manifest_includes_assertion_helpers(tmp_path):
    request, _, _, _, _ = prepared()
    for module in (reference, fixtures):
        for node in ast.walk(ast.parse(Path(module.__file__).read_text())):
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith(("cells", "jax"))
    manifest = reference.dependency_manifest(ROOT)
    assert "validation/betse/contact.py" in manifest
    assert "validation/topology/surface_active_profile_interventions_reference.py" in manifest
    path = tmp_path / "simulation.json"
    path.write_text(json.dumps(request["simulation"]))
    script = """
import builtins,json,sys
from pathlib import Path
original=builtins.__import__
def guarded(name,*args,**kwargs):
    if name.split('.')[0] in ('cells','jax'):
        raise RuntimeError('Production/accelerator oracle import forbidden: '+name)
    return original(name,*args,**kwargs)
builtins.__import__=guarded
from validation.topology import active_membrane_profile_phase_handoff_reference as r
raw=json.loads(Path(sys.argv[1]).read_text())
c=r.scheduled.bind(raw)
y=r.scheduled.initial(c)
d,p,proof=r.scheduled.evaluate(c,y)
assert len(c['parent']['shapes'])==19 and len(d)==len(y)
assert not any(n.split('.')[0] in ('cells','jax') for n in sys.modules)
print(json.dumps(r.dependency_manifest(Path(sys.argv[2]))))
"""
    completed = subprocess.run(
        [sys.executable, "-B", "-c", script, str(path), str(ROOT)],
        capture_output=True,
        text=True,
        check=True,
        timeout=90,
    )
    assert json.loads(completed.stdout) == manifest
    evidence(
        "reference-dependencies",
        dict(
            source_sha256=manifest,
            production_imports_forbidden=True,
            complete_stage_executed_without_cells_or_jax=True,
        ),
    )
