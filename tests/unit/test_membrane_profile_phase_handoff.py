"""Evolved INIT to explicit SIM: exact owners/history, independent physics, replay."""

import ast
import hashlib
import json
import os
import subprocess
import sys
from copy import deepcopy
from dataclasses import replace
from functools import lru_cache
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.core import membrane_profile_phase_handoff as adapter
from cells.core import surface_profile_epoch_spec as definition
from cells.core import surface_profile_interventions_spec as scheduled_spec
from cells.core import tissue_profile_preparation as static
from cells.core.errors import NumericalError
from cells.core.grid import EventGrid
from cells.core.runner import branch_checkpoint, run, validate_checkpoint
from cells.core.schedule import control_values, event_index
from cells.core.specs import ConfigError, digest, parse_spec
from cells.core.state import Checkpoint
from cells.io import load_snapshot, write_snapshot
from cells.models import surface_profile_epoch as model
from cells.models import surface_profile_interventions as scheduled
from cells.models.registry import get_model
from cells.numerics.fixed_step import rk4_step
from cells.processes import betse_tissue_profiles as native
from validation.topology import membrane_profile_phase_handoff_fixtures as fixtures
from validation.topology import membrane_profile_phase_handoff_reference as reference

ROOT = Path(os.environ.get("CELLS_COMPONENT_SOURCE_ROOT", Path(__file__).resolve().parents[2]))
PROTOCOL = ROOT / "validation/topology/membrane_profile_phase_handoff_protocol.json"


def evidence(name, value):
    if directory := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        path = Path(directory)
        path.mkdir(parents=True, exist_ok=True)
        (path / ("phase-handoff-" + name + ".json")).write_text(
            json.dumps(
                dict(value, status="passed"),
                indent=2,
                allow_nan=False,
                default=lambda v: v.tolist(),
            )
            + "\n"
        )


def example(name="direct-four-ion"):
    if directory := os.environ.get("CELLS_EPOCH_QUALIFIED_SOURCE"):
        path = Path(directory) / name / "definition.json"
    else:
        path = Path(json.loads(PROTOCOL.read_text())["qualified_examples"][name]["path"])
    return json.loads(path.read_text())


def control(spec, time):
    table = control_values(spec, [time])
    return type(table)(*(v[0] for v in table))


@lru_cache
def source_checkpoint(name="direct-four-ion", time=10e-6, public=False):
    source, _ = (
        fixtures.public_definitions(example(name))
        if public
        else fixtures.definitions(example(name))
    )
    spec = scheduled_spec.parse(source)
    state, layout = scheduled.initial_values(spec)
    grid = EventGrid(spec)
    index = grid.exact_index(time)
    for i in range(index):
        state = rk4_step(
            lambda y, *args: scheduled.rhs(y, *args, xp=np),
            state,
            grid[i + 1] - grid[i],
            control(spec, grid[i]),
            layout,
            layout.active,
        )
    cp = Checkpoint(state, layout, time, index, event_index(spec, time))
    return spec, cp


@lru_cache
def prepared(case="continued-controls", name="direct-four-ion", time=10e-6):
    source, cp = source_checkpoint(name, time)
    _, target = fixtures.definitions(example(name), case)
    request = dict(
        kind=adapter.REQUEST_KIND,
        policies=deepcopy(definition.POLICIES),
        source=adapter.capture_source(source, cp),
        simulation=target,
    )
    result = adapter.prepare(request)
    return request, result, parse_spec(result.definition), source, cp


def score(context, observed, expected, *, rtol=3e-10, atol=3e-12, charge_atol=3e-23):
    p = reference.scheduled.passive
    actual = reference.scheduled.flatten(context, observed._asdict())
    budget = np.r_[
        p.flatten(
            context["parent"],
            {
                key: np.full(shape, charge_atol if key.endswith("_C") else atol)
                for key, shape in context["parent"]["shapes"].items()
            },
        ),
        atol,
    ] + rtol * np.abs(expected)
    ratio = float(np.max(np.abs(actual - expected) / budget, initial=0))
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


@pytest.mark.parametrize("time", [5e-6, 10e-6])
def test_evolved_INIT_checkpoint_matches_independent_segmented_solution(time):
    source, cp = source_checkpoint(time=time)
    raw = scheduled_spec.to_dict(source)
    expected, proof = reference.integrate(raw, end_time=time)
    context = reference.scheduled.bind(raw)
    ratio = score(context, cp.state, expected, rtol=3e-8, atol=2e-11, charge_atol=3e-25)
    assert np.any(cp.state.amount_increment != 0)
    assert np.any(cp.state.membrane_transferred != 0)
    assert np.any(cp.state.electrode_charge_transferred_C != 0)
    assert np.sum(cp.state.membrane_dissipated_energy_pJ) > 0
    assert np.any(cp.state.reservoir_work_pJ != 0)
    flat = reference.scheduled.flatten(context, cp.state._asdict())
    conservation = reference.conservation(raw, flat)
    assert_conservation(conservation)
    evidence(
        "INIT-reference-" + str(time),
        dict(
            time_s=time,
            error_over_budget=ratio,
            independent=proof,
            conservation=conservation,
            diagnostics=scheduled.check_values(cp.state, source),
        ),
    )


@pytest.mark.parametrize("case", fixtures.CASES)
def test_handoff_preserves_all_parent_arrays_owners_and_original_accounting(case):
    request, result, spec, source, cp = prepared(case)
    state, layout = model.initial_values(spec)
    assert type(state) is model.STATE_TYPE and type(layout) is model.LAYOUT_TYPE
    assert type(state) is not scheduled.STATE_TYPE and type(layout) is not scheduled.LAYOUT_TYPE
    for a, b in zip(scheduled.base_state(cp.state), scheduled.base_state(state), strict=True):
        assert a.dtype == b.dtype and a.shape == b.shape and a.tobytes() == b.tobytes()
    for a, b in zip(scheduled.base_layout(cp.layout), scheduled.base_layout(layout), strict=True):
        assert a.dtype == b.dtype and a.tobytes() == b.tobytes()
    np.testing.assert_array_equal(state.phase_clock_s, [0.0])
    clocks = result.provenance["clocks"]
    assert clocks["init_checkpoint_time_s"] == cp.time
    assert clocks["init_phase_clock_s"] == float(cp.state.phase_clock_s[0])
    assert clocks["sim_epoch_time_s"] == clocks["sim_phase_clock_s"] == 0.0
    buffers = scheduled.native_state(layout, xp=np)
    reset = result.provenance["buffer_reset"]
    np.testing.assert_array_equal(buffers.membrane_base_m2_s, reset["baseline_diffusion_m2_s"])
    np.testing.assert_array_equal(buffers.membrane_scheduled_m2_s, reset["scheduled_buffer_m2_s"])
    context, flat = reference.initial(request)
    actual = reference.scheduled.flatten(context, state._asdict())
    np.testing.assert_array_equal(actual, flat)
    before = reference.conservation(
        scheduled_spec.to_dict(source), reference.scheduled.flatten(context, cp.state._asdict())
    )
    after = reference.conservation(request["simulation"], flat)
    for key in before:
        np.testing.assert_array_equal(before[key], after[key])
    assert_conservation(after)
    diagnostics = model.check_values(state, spec)
    assert diagnostics == scheduled.check_values(cp.state, source) | {"phase_clock_final_s": 0.0}
    evidence(
        "preserved-" + case,
        dict(
            request=request,
            definition=result.definition,
            provenance=result.provenance,
            physical_and_history_exact=True,
            conservation=after,
            diagnostics=diagnostics,
            original_origin_retained=True,
        ),
    )


@pytest.mark.parametrize("case", fixtures.CASES)
def test_complete_SIM_fields_rhs_pulses_and_ledgers_from_evolved_INIT(case):
    request, _, spec, _, _ = prepared(case)
    state, layout = model.initial_values(spec)
    context = reference.scheduled.bind(request["simulation"])
    stages = []
    for time in (0.0, 1e-6, 2e-6, 4e-6, 5e-6, 6e-6, 8e-6, 10e-6):
        trial = state._replace(phase_clock_s=np.asarray([time]))
        actual = model.readouts(trial, control(spec, time), layout, xp=np)
        expected, phi, proof = reference.scheduled.evaluate(
            context, reference.scheduled.flatten(context, trial._asdict())
        )
        ratio = score(context, actual.derivative, expected)
        n = layout.active.size
        observed_phi = np.r_[
            actual.field.potential_V[:n][layout.active],
            actual.field.potential_V[n:][layout.outside_active],
        ]
        np.testing.assert_allclose(observed_phi, phi, rtol=3e-10, atol=3e-13)
        assert bool(actual.valid) and abs(actual.field.energy_balance_pJ_s) < 1e-10
        rhs = model.rhs(trial, control(spec, time), layout, layout.active, xp=np)
        assert type(rhs) is model.STATE_TYPE
        stages.append(
            dict(
                time_s=time,
                max_error_over_budget=ratio,
                independent=proof,
                energy_balance_pJ_s=float(actual.field.energy_balance_pJ_s),
            )
        )
    evidence("SIM-fields-" + case, dict(stages=stages, full_parent_RHS_and_ledgers=True))


def test_joined_geometry_profile_chain_and_intermediate_INIT_checkpoint():
    request, result, spec, _, cp = prepared(name="geometry-profiles", time=5e-6)
    state, layout = model.initial_values(spec)
    artifact = request["source"]["definition"]["model"]["profile_preparation"]
    assert artifact["provenance"]["kind"] == "cells.initial_geometry_profile_preparation@1"
    assert definition.scheduled_spec(spec).model.profile_preparation == artifact
    assert cp.time < source_checkpoint("geometry-profiles")[0].experiment.end_time
    context, flat = reference.initial(request)
    expected, phi, proof = reference.scheduled.evaluate(context, flat)
    actual = model.readouts(state, control(spec, 0.0), layout, xp=np)
    ratio = score(context, actual.derivative, expected)
    assert actual.valid and adapter.replay(result.provenance).definition == result.definition
    evidence(
        "joined-chain",
        dict(
            request=request,
            definition=result.definition,
            provenance=result.provenance,
            complete_geometry_profile_chain_retained=True,
            accepted_interior_INIT_checkpoint=True,
            independent_error_over_budget=ratio,
            independent=proof,
        ),
    )


def test_SIM_continuation_against_independent_adaptive_solution_with_global_history():
    request, _, spec, _, cp = prepared()
    context, initial = reference.initial(request)
    expected, proof = reference.integrate(request["simulation"], initial_state=initial)
    outcomes = []
    for dt in (0.125e-6, 0.0625e-6):
        state, layout = model.initial_values(spec)
        for start, stop in ((0.0, 5e-6), (5e-6, 10e-6)):
            count = round((stop - start) / dt)
            h = (stop - start) / count
            u = control(spec, start)
            for _ in range(count):
                state = rk4_step(
                    lambda y, *args: model.rhs(y, *args, xp=np), state, h, u, layout, layout.active
                )
        ratio = score(context, state, expected, rtol=3e-8, atol=2e-11, charge_atol=3e-25)
        diagnostics = model.check_values(state, spec)
        flat = reference.scheduled.flatten(context, state._asdict())
        conservation = reference.conservation(request["simulation"], flat)
        assert_conservation(conservation)
        outcomes.append(
            dict(
                dt_s=dt,
                error_over_budget=ratio,
                max_error=float(np.max(np.abs(flat - expected))),
                diagnostics=diagnostics,
                independent_conservation=conservation,
            )
        )
    assert outcomes[-1]["max_error"] <= max(outcomes[0]["max_error"] * 0.2, 3e-13)
    assert np.sum(state.membrane_dissipated_energy_pJ) > np.sum(
        cp.state.membrane_dissipated_energy_pJ
    )
    evidence(
        "continued-trajectory",
        dict(
            INIT_duration_s=cp.time,
            SIM_duration_s=spec.experiment.end_time,
            independent=proof,
            refinements=outcomes,
            INIT_ledgers_retained_in_SIM=True,
        ),
    )


def test_full_recipe_registry_typed_serialization_and_portable_preparation(tmp_path):
    request, result, spec, _, _ = prepared()
    original = digest(request)
    checked = adapter.prepare(deepcopy(request))
    assert digest(request) == original and checked == result
    assert get_model(spec.model) is model
    assert parse_spec(spec.to_dict()) == spec
    assert spec.fingerprint == digest(spec.to_dict())
    assert adapter.replay(json.loads(json.dumps(result.provenance))) == result
    path = adapter.write_preparation(tmp_path / "handoff", result)
    assert adapter.read_preparation(path) == result
    with pytest.raises(ConfigError):
        adapter.write_preparation(path, result)
    raw = json.loads((path / "definition.json").read_text())
    raw["model"]["handoff"]["clocks"]["sim_epoch_time_s"] = 1.0
    (path / "definition.json").write_text(json.dumps(raw))
    with pytest.raises(ConfigError):
        adapter.read_preparation(path)
    evidence(
        "recipe",
        dict(
            request=request,
            definition=result.definition,
            provenance=result.provenance,
            full_roundtrip=True,
            input_purity=True,
            typed_arrays_retained=True,
            nonoverwriting_output=True,
        ),
    )


def test_fresh_process_replay_needs_no_original_checkpoint_or_example(tmp_path):
    _, result, _, _, _ = prepared()
    directory = adapter.write_preparation(tmp_path / "portable", result)
    script = """
import builtins,io,json,sys
from pathlib import Path
from cells.core import membrane_profile_phase_handoff as a
from cells.core import surface_profile_epoch_spec as s
from cells.models import surface_profile_epoch as m
original=builtins.open
def guarded(file,*args,**kwargs):
    text=str(file)
    if "scheduled-membrane-profiles-handoff-" in text or "qualified-source" in text:
        raise RuntimeError("original source read forbidden")
    return original(file,*args,**kwargs)
builtins.open=guarded
io.open=guarded
value=a.read_preparation(Path(sys.argv[1]))
spec=s.parse(value.definition)
state,layout=m.initial_values(spec)
assert state.phase_clock_s[0]==0 and state.membrane_transferred.any()
print(json.dumps({"identity":value.provenance["identity"],"external_source_reads_blocked":True}))
"""
    completed = subprocess.run(
        [sys.executable, "-B", "-c", script, str(directory)],
        capture_output=True,
        text=True,
        check=True,
        timeout=90,
    )
    proof = json.loads(completed.stdout)
    assert proof["identity"] == result.provenance["identity"]
    evidence("portable-replay", proof)


@pytest.mark.parametrize(
    "fault",
    [
        "SIM-source",
        "wrong-owner",
        "wrong-layout",
        "erased-history",
        "negative-dissipation",
        "electrode-work",
        "clock-mismatch",
        "step-index",
        "event-index",
        "precision",
        "padding",
    ],
)
def test_invalid_source_owner_clock_or_history_refused(fault):
    spec, cp = source_checkpoint()
    if fault == "SIM-source":
        spec = replace(spec, model=replace(spec.model, phase="SIM"))
    if fault == "wrong-owner":
        value = np.array(cp.state.amount_increment)
        value[0, 0], value[0, 1] = value[0, 1], value[0, 0]
        cp = replace(cp, state=cp.state._replace(amount_increment=value))
    if fault == "wrong-layout":
        value = np.array(cp.layout.membrane_cell)
        value[0] = 1 - value[0]
        cp = replace(cp, layout=cp.layout._replace(membrane_cell=value))
    if fault == "erased-history":
        cp = replace(
            cp,
            state=cp.state._replace(
                membrane_transferred=np.zeros_like(cp.state.membrane_transferred)
            ),
        )
    if fault == "negative-dissipation":
        cp = replace(
            cp,
            state=cp.state._replace(
                membrane_dissipated_energy_pJ=-np.ones_like(cp.state.membrane_dissipated_energy_pJ)
            ),
        )
    if fault == "electrode-work":
        value = np.array(cp.state.electrode_work_pJ)
        value[0] += 1e-4
        cp = replace(cp, state=cp.state._replace(electrode_work_pJ=value))
    if fault == "clock-mismatch":
        cp = replace(cp, state=cp.state._replace(phase_clock_s=np.asarray([0.0])))
    if fault == "step-index":
        cp = replace(cp, step_index=cp.step_index - 1)
    if fault == "event-index":
        cp = replace(cp, event_index=cp.event_index - 1)
    if fault == "precision":
        cp = replace(
            cp,
            state=cp.state._replace(amount_increment=cp.state.amount_increment.astype(np.float32)),
        )
    if fault == "padding":
        value = np.array(cp.state.amount_increment)
        assert value.shape[1] > len(spec.model.cells)
        value[0, -1] = 1e-6
        cp = replace(cp, state=cp.state._replace(amount_increment=value))
    with pytest.raises((ConfigError, NumericalError)):
        adapter.capture_source(spec, cp)
    evidence("refused-source-" + fault, dict(fault=fault, refused=True))


@pytest.mark.parametrize(
    "fault",
    [
        "source-seal",
        "missing-ledger",
        "typed-bool",
        "typed-overflow",
        "shape-bool",
        "target-INIT",
        "changed-volume",
        "changed-capacity",
        "changed-defaults",
        "reset-policy",
        "new-clock",
        "source-clock",
        "buffer-values",
        "history-rewrite",
        "provenance-proof",
    ],
)
def test_invalid_request_epoch_reset_and_artifact_refused(fault):
    request, result, _, _, _ = prepared()
    request = deepcopy(request)
    if fault in ("new-clock", "source-clock", "buffer-values", "history-rewrite"):
        raw = deepcopy(result.definition)
        record = raw["model"]["handoff"]
        if fault == "new-clock":
            record["clocks"]["sim_phase_clock_s"] = 10e-6
        if fault == "source-clock":
            record["clocks"]["init_checkpoint_time_s"] = 0.0
        if fault == "buffer-values":
            record["buffer_reset"]["scheduled_buffer_m2_s"][0][0] = 1e-20
        if fault == "history-rewrite":
            record["source"]["checkpoint"]["state"]["membrane_transferred"]["values"][0][0] += 1e-3
            record["source"].pop("identity")
            record["source"]["identity"] = digest(record["source"])
        with pytest.raises((ConfigError, NumericalError)):
            parse_spec(raw)
    elif fault == "provenance-proof":
        p = deepcopy(result.provenance)
        p["preservation"]["cell_amount_fmol"][0][0] += 1
        p.pop("identity")
        p["identity"] = digest(p)
        with pytest.raises(ConfigError):
            adapter.replay(p)
    else:
        source = request["source"]
        cp = source["checkpoint"]
        if fault == "source-seal":
            source["identity"] = "0" * 64
        if fault == "missing-ledger":
            cp["state"].pop("face_transferred")
        if fault == "typed-bool":
            cp["state"]["amount_increment"]["values"][0][0] = True
        if fault == "typed-overflow":
            cp["layout"]["intervention_kind"]["values"][0] += 2**64
        if fault == "shape-bool":
            cp["state"]["phase_clock_s"]["shape"] = [True]
        if fault == "target-INIT":
            request["simulation"]["model"]["phase"] = "INIT"
        if fault == "changed-volume":
            request["simulation"]["model"]["cells"][0]["volume_pL"] *= 2
        if fault == "changed-capacity":
            request["simulation"]["execution"]["capacity"] += 1
        if fault == "changed-defaults":
            old = request["simulation"]["model"]["profile_preparation"]
            p = deepcopy(old["provenance"])
            geometry = p["geometry"]
            layout = geometry.pop("layout")
            rows = p["profile_declarations"]
            rows["default"]["diffusivity_m2_s"][0] *= 1.25
            rebuilt = static.prepare(
                p["source_definition"],
                static.Geometry(native.Layout(**layout), **geometry),
                static._decode_profile(rows["default"]),
                [static._decode_profile(row) for row in rows["profiles"]],
                ion_enabled=rows["ion_enabled"],
                enabled=rows["enabled"],
                is_ecm=rows["is_ecm"],
            )
            assert digest(rebuilt.definition["model"]) == digest(old["definition"]["model"])
            request["simulation"]["model"]["profile_preparation"] = dict(
                definition=rebuilt.definition, provenance=rebuilt.provenance
            )
            scheduled_spec.parse(request["simulation"])
        if fault == "reset-policy":
            request["policies"]["state_policy"] = "reset_all_ledgers"
        if fault in ("missing-ledger", "typed-bool", "typed-overflow", "shape-bool"):
            source.pop("identity")
            source["identity"] = digest(source)
        with pytest.raises((ConfigError, NumericalError, ValueError, OverflowError)):
            adapter.prepare(request)
    evidence("refused-artifact-" + fault, dict(fault=fault, refused=True))


def test_handoff_cannot_be_ordinary_resume_or_branch_and_history_cannot_reset():
    _, _, spec, source, cp = prepared()
    with pytest.raises(ConfigError):
        branch_checkpoint(source, cp, spec)
    with pytest.raises(ConfigError):
        validate_checkpoint(spec, cp)
    state, layout = model.initial_values(spec)
    start = Checkpoint(state, layout, 0.0, 0, event_index(spec, 0.0))
    validate_checkpoint(spec, start)
    zero, _ = scheduled.initial_values(definition.scheduled_spec(spec))
    erased = replace(start, state=model.STATE_TYPE(*zero))
    with pytest.raises(ConfigError, match="initial state"):
        validate_checkpoint(spec, erased)
    stale = replace(start, state=state._replace(phase_clock_s=np.array(cp.state.phase_clock_s)))
    with pytest.raises(ConfigError):
        validate_checkpoint(spec, stale)
    evidence(
        "operation-boundary",
        dict(
            resume_cannot_transition=True,
            branch_cannot_transition=True,
            initial_history_reset_refused=True,
            old_clock_reset_on_resume_refused=True,
        ),
    )


@pytest.mark.skipif(
    os.environ.get("CELLS_COMPONENT_PHASE") != "jax", reason="separate CPU JAX process"
)
def test_cpu_jax_complete_epoch_rhs_and_invalid_world_isolation():
    request, _, spec, _, _ = prepared()
    state, layout = model.initial_values(spec)
    y, p = jax.tree.map(jnp.asarray, state), jax.tree.map(jnp.asarray, layout)
    u = jax.tree.map(jnp.asarray, control(spec, 4e-6))
    function = jax.jit(lambda t: model.rhs(y._replace(phase_clock_s=t[None]), u, p, p.active))
    actual = function(jnp.asarray(4e-6))
    expected = model.rhs(
        state._replace(phase_clock_s=np.asarray([4e-6])),
        control(spec, 4e-6),
        layout,
        layout.active,
        xp=np,
    )
    context = reference.scheduled.bind(request["simulation"])
    score(context, actual, reference.scheduled.flatten(context, expected._asdict()))
    batch = jax.jit(jax.vmap(function))(jnp.asarray([1e-6, -1e-6, 4e-6]))
    for value in batch:
        assert np.isnan(np.asarray(value)[1]).all() and np.isfinite(np.asarray(value)[[0, 2]]).all()
    evidence(
        "cpu-jax",
        dict(full_rhs_parity=True, invalid_world_isolated=True, carried_history_preserved=True),
    )


@pytest.mark.skipif(
    os.environ.get("CELLS_COMPONENT_PHASE") != "public", reason="separate public CPU process"
)
def test_public_SIM_epoch_execution_snapshot_resume_and_observed_clocks(tmp_path):
    source, cp = source_checkpoint(time=0.25e-6, public=True)
    _, target = fixtures.public_definitions(example())
    request = dict(
        kind=adapter.REQUEST_KIND,
        policies=deepcopy(definition.POLICIES),
        source=adapter.capture_source(source, cp),
        simulation=target,
    )
    prepared = adapter.prepare(request)
    spec = parse_spec(prepared.definition)
    complete = run(spec)
    snapshot = write_snapshot(tmp_path / "SIM-snapshot", spec, complete.checkpoint_at(1e-9))
    loaded = load_snapshot(snapshot)
    resumed = run(loaded.spec, loaded.checkpoint)
    for a, b in zip(complete.final.state, resumed.final.state, strict=True):
        np.testing.assert_array_equal(a, b)
    np.testing.assert_allclose(
        complete.history.phase_clock_s[:, 0], complete.times, rtol=0, atol=1e-23
    )
    np.testing.assert_array_equal(
        complete.observations.init_phase_clock_s, float(cp.state.phase_clock_s[0])
    )
    np.testing.assert_allclose(
        complete.observations.elapsed_time_s[:, 0],
        cp.time + complete.observations.times,
        rtol=0,
        atol=1e-23,
    )
    for a, b in zip(
        scheduled.base_state(complete.history)._asdict().values(),
        scheduled.base_state(cp.state),
        strict=True,
    ):
        np.testing.assert_array_equal(a[0], b)
    evidence(
        "public-replay",
        dict(
            request=request,
            definition=prepared.definition,
            provenance=prepared.provenance,
            INIT_time_s=cp.time,
            SIM_time_s=2e-9,
            steps=2,
            snapshot_resume_exact=True,
            original_INIT_history_at_SIM_zero=True,
            both_phase_clocks_observed=True,
            compiled_trajectory=False,
            diagnostics=complete.diagnostics,
        ),
    )


def test_pinned_native_phase_calls_and_reference_independence():
    protocol = json.loads(PROTOCOL.read_text())
    for name, expected in protocol["readonly_source_sha256"].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected, name
    for row in protocol["native_phase_scope"]:
        path = Path(row["path"])
        content = path.read_bytes()
        assert hashlib.sha256(content).hexdigest() == row["sha256"]
        tree = ast.parse(content)
        for name, expected in row["body_ast_sha256"].items():
            node = next(
                n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name
            )
            assert (
                hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest()
                == expected
            )
    for module in (reference, fixtures):
        for node in ast.walk(ast.parse(Path(module.__file__).read_text())):
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith(("cells", "jax"))
    evidence(
        "source-contract",
        dict(
            native_phase_scope=protocol["native_phase_scope"],
            independent_reference=True,
            original_scheduled_model_unchanged=True,
        ),
    )
