"""Explicit calcium @6 and finite-fuel @5 owners with regional plasma pulses."""

import ast
import hashlib
import json
import os
from copy import deepcopy
from dataclasses import replace
from functools import lru_cache
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.core import surface_calcium_energy_profile_interventions_spec as fuel_spec
from cells.core import surface_calcium_profile_interventions_spec as calcium_spec
from cells.core import tissue_profile_composition_preparation as composed
from cells.core import tissue_profile_preparation as direct
from cells.core.errors import NumericalError
from cells.core.grid import EventGrid
from cells.core.runner import run
from cells.core.schedule import control_values
from cells.core.specs import ConfigError, parse_spec
from cells.io import load_snapshot, write_snapshot
from cells.models import surface_calcium_cav as calcium_parent
from cells.models import surface_calcium_energy_hcn_extra as fuel_parent
from cells.models import surface_calcium_energy_profile_interventions as fuel
from cells.models import surface_calcium_profile_interventions as calcium
from cells.numerics.fixed_step import rk4_step
from cells.processes import betse_tissue_profiles as native
from validation.topology import owned_calcium_profile_interventions_fixtures as fixtures
from validation.topology import owned_calcium_profile_interventions_reference as reference

ROOT = Path(os.environ.get("CELLS_COMPONENT_SOURCE_ROOT", Path(__file__).resolve().parents[2]))
OWNERS = {
    "calcium6": (calcium_spec, calcium, calcium_parent),
    "fuel5": (fuel_spec, fuel, fuel_parent),
}


def evidence(name, value):
    if directory := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        p = Path(directory)
        p.mkdir(parents=True, exist_ok=True)
        (p / ("owned-calcium-profiles-" + name + ".json")).write_text(
            json.dumps(
                dict(value, status="passed"),
                indent=2,
                allow_nan=False,
                default=lambda v: v.tolist(),
            )
            + "\n"
        )


def build(raw, family):
    raw = deepcopy(raw)
    geometry = raw["geometry"]
    layout = geometry.pop("layout")
    prepared = composed.prepare(
        raw["definition"],
        composed.Geometry(native.Layout(**layout), **geometry),
        direct._decode_profile(raw["default"]),
        [direct._decode_profile(p) for p in raw["profiles"]],
        ion_enabled=raw["ion_enabled"],
        enabled=raw["enabled"],
        is_ecm=raw["is_ecm"],
    )
    definition = OWNERS[family][0]
    result = deepcopy(prepared.definition)
    result["model"].update(
        id=definition.MODEL_ID,
        profile_preparation=dict(definition=prepared.definition, provenance=prepared.provenance),
        interventions=raw["interventions"],
        phase=raw["phase"],
        timing_policy=definition.TIMING_POLICY,
        reset_policy=definition.RESET_POLICY,
    )
    result["execution"].update(
        intervention_capacity=raw["intervention_capacity"],
        intervention_target_capacity=raw["intervention_target_capacity"],
    )
    return result


@lru_cache
def initialized(family="calcium6", case="SIM"):
    raw = build(fixtures.inputs(family, case), family)
    definition, model, parent = OWNERS[family]
    spec = definition.parse(raw)
    state, p = model.initial_values(spec)
    return raw, spec, state, p


def control(spec, time):
    table = control_values(spec, [time])
    return type(table)(*(v[0] for v in table))


def score(context, actual, expected, *, rtol=3e-10, atol=3e-12, charge_atol=3e-23):
    observed = reference.flatten(context, actual._asdict())
    process = context["process"]
    budget = np.r_[
        process.flatten(
            context["parent"],
            {
                key: np.full(shape, charge_atol if key.endswith("_C") else atol)
                for key, shape in context["parent"]["shapes"].items()
            },
        ),
        atol,
    ] + rtol * np.abs(expected)
    ratio = float(np.max(np.abs(observed - expected) / budget, initial=0))
    assert ratio <= 1, ratio
    return ratio


def stage(raw, spec, state, p, family, time):
    model = OWNERS[family][1]
    context = reference.bind(raw)
    y = state._replace(phase_clock_s=np.asarray([time]))
    u = control(spec, time)
    actual = model.readouts(y, u, p, xp=np)
    expected, phi, proof = reference.evaluate(context, reference.flatten(context, y._asdict()))
    ratio = score(context, actual.derivative, expected)
    n = p.active.size
    observed = np.r_[
        actual.field.potential_V[:n][p.active], actual.field.potential_V[n:][p.outside_active]
    ]
    np.testing.assert_allclose(observed, phi, rtol=3e-10, atol=3e-12)
    assert bool(actual.valid) and abs(actual.field.energy_balance_pJ_s) < 1e-9
    return dict(
        time_s=time,
        error_over_budget=ratio,
        independent=proof,
        full_state_fields=list(model.STATE_TYPE._fields),
        energy_rate_residual_pJ_s=float(actual.field.energy_balance_pJ_s),
    )


@pytest.mark.parametrize("family", fixtures.FAMILIES)
@pytest.mark.parametrize("case", fixtures.CASES)
def test_full_stage_original_stores_gates_and_pool_owner_preserved(family, case):
    raw, spec, state, p = initialized(family, case)
    definition, model, parent = OWNERS[family]
    original, layout = parent.initial_values(definition.owner_spec(spec))
    assert type(model.parent_layout(p)) is parent.LAYOUT_TYPE
    for a, b in zip(model.parent_state(state), original, strict=True):
        assert a.shape == b.shape and a.dtype == b.dtype and a.tobytes() == b.tobytes()
    for a, b in zip(model.parent_layout(p), layout, strict=True):
        np.testing.assert_array_equal(a, b)
    stages = [stage(raw, spec, state, p, family, t) for t in (0.0, 1e-6, 2e-6, 3e-6, 4e-6)]
    diagnostics = model.check_values(state, spec)
    assert not any(v > 1e-9 for k, v in diagnostics.items() if "energy" in k)
    evidence(
        "stages-" + family + "-" + case,
        dict(
            inputs=raw,
            stages=stages,
            exact_initial_parent_state=True,
            exact_parent_layout=True,
            all_chemical_and_fuel_fields=True,
            diagnostics=diagnostics,
        ),
    )


@pytest.mark.parametrize("family", fixtures.FAMILIES)
@pytest.mark.parametrize("case", ["INIT", "empty-events"])
def test_inactive_schedule_is_exact_complete_parent_rhs(family, case):
    _, spec, state, p = initialized(family, case)
    _, model, parent = OWNERS[family]
    u = control(spec, 2e-6)
    y = state._replace(phase_clock_s=np.asarray([2e-6]))
    actual = model.rhs(y, u, p, p.active, xp=np)
    expected = parent.rhs(model.parent_state(y), u, model.parent_layout(p), p.active, xp=np)
    for a, b in zip(model.parent_state(actual), expected, strict=True):
        np.testing.assert_array_equal(a, b)
    np.testing.assert_array_equal(actual.phase_clock_s, [1.0])
    evidence(
        "inactive-" + family + "-" + case,
        dict(all_parent_fields_bitwise=True, actual_owner_evolves=True),
    )


@lru_cache
def trajectory(family, case, refinement):
    raw, original, _, _ = initialized(family, case)
    model = OWNERS[family][1]
    spec = replace(
        original, execution=replace(original.execution, dt=original.execution.dt / refinement)
    )
    state, p = model.initial_values(spec)
    times = np.asarray(list(EventGrid(spec)))
    table = control_values(spec, times[:-1])
    model.check_steps(spec, np.diff(times), table)
    values = [state]
    for i, h in enumerate(np.diff(times)):
        u = type(table)(*(v[i] for v in table))
        state = rk4_step(lambda y, *args: model.rhs(y, *args, xp=np), state, h, u, p, p.active)
        values.append(state)
    history = model.STATE_TYPE(*(np.stack(v) for v in zip(*values, strict=True)))
    return spec, p, times, history, model.check_values(history, spec)


@pytest.mark.parametrize("family", fixtures.FAMILIES)
@pytest.mark.parametrize("case", ["SIM", "close-reopen"])
def test_short_complete_coupled_trajectory_refinement(family, case):
    raw, _, _, _ = initialized(family, case)
    _, model, _ = OWNERS[family]
    context = reference.bind(raw)
    expected, proof = reference.integrate(raw)
    outcomes = []
    for refinement in (1, 2):
        spec, _, _, history, diagnostics = trajectory(family, case, refinement)
        final = model.STATE_TYPE(*(v[-1] for v in history))
        ratio = score(context, final, expected, rtol=3e-9, atol=2e-11, charge_atol=3e-25)
        error = float(np.max(np.abs(reference.flatten(context, final._asdict()) - expected)))
        outcomes.append(
            dict(
                dt_s=spec.execution.dt,
                error_over_budget=ratio,
                max_error=error,
                diagnostics=diagnostics,
            )
        )
    assert outcomes[-1]["max_error"] <= max(outcomes[0]["max_error"] * 0.3, 3e-12)
    evidence(
        "trajectory-" + family + "-" + case,
        dict(
            duration_s=4e-6,
            independent=proof,
            refinements=outcomes,
            refinement_mode=(
                "within_precision_floor"
                if max(v["max_error"] for v in outcomes) <= 3e-12
                else "decreasing_error"
            ),
            convergence_order_claim=False,
            complete_chemical_gate_fuel_history_compared=True,
        ),
    )


@pytest.mark.parametrize("family", fixtures.FAMILIES)
def test_closure_physics_and_actual_global_diagnostics(family):
    raw, _, _, _ = initialized(family, "close-reopen")
    _, model, parent = OWNERS[family]
    spec, p, times, history, diagnostics = trajectory(family, "close-reopen", 1)
    before = [v.tobytes() for v in history]
    comparisons = []
    count = 0
    for time in (1e-6, 2e-6, 3e-6, 4e-6):
        i = int(np.flatnonzero(times == time)[0])
        state = model.STATE_TYPE(*(v[i] for v in history))
        signal = model.signal_values(state, p, xp=np)
        current = model.parent_layout(p)._replace(membrane_permeability=signal.permeability)
        untouched = parent.readouts(model.parent_state(state), control(spec, time), current, xp=np)
        projected = parent.readouts(
            model.readout_state(state, signal.permeability, xp=np),
            control(spec, time),
            current,
            xp=np,
        )
        for a, b in zip(jax.tree.leaves(untouched), jax.tree.leaves(projected), strict=True):
            if np.asarray(a).dtype.kind != "b":
                np.testing.assert_array_equal(a, b)
                count += 1
        comparisons.append(stage(raw, spec, state, p, family, time))
        if time == 2e-6:
            na = spec.model.species_ids.index("Na")
            closed = signal.permeability[na] == 0
            assert np.any(closed) and np.any(state.membrane_transferred[na, closed] != 0)
            assert not untouched.valid and projected.valid
    observed = model.observe_history(times, history, p, [1e-6, 2e-6, 3e-6, 4e-6], spec)
    indices = [int(np.flatnonzero(times == time)[0]) for time in (1e-6, 2e-6, 3e-6, 4e-6)]
    for name in parent.STATE_TYPE._fields:
        np.testing.assert_array_equal(getattr(observed, name), getattr(history, name)[indices])
    if family == "fuel5":
        for j, index in enumerate(indices):
            state = model.STATE_TYPE(*(v[index] for v in history))
            balance = parent.balances(model.parent_state(state), model.accounting_layout(p, xp=np))
            np.testing.assert_array_equal(
                observed.energy_balance_pJ[j], np.atleast_1d(balance["energy"])
            )
            np.testing.assert_array_equal(
                observed.pool_internal_transfer_balance_pJ[j], balance["pool_energy"]
            )
    assert before == [v.tobytes() for v in history]
    bad = np.array(history.membrane_transferred)
    bad[indices[1], 0, 0] += 1e-3
    corrupt = history._replace(membrane_transferred=bad)
    with pytest.raises(NumericalError):
        model.check_values(corrupt, spec)
    with pytest.raises(NumericalError):
        model.observe_history(times, corrupt, p, [2e-6], spec)
    evidence(
        "closure-" + family,
        dict(
            comparisons=comparisons,
            numeric_parent_leaf_comparisons=count,
            full_physics_projection_bitwise=True,
            all_actual_observed_fields_exact=True,
            actual_global_conservation_used=True,
            corrupt_closed_history_refused=True,
            diagnostics=diagnostics,
        ),
    )


def test_finite_fuel_all_three_pump_families_use_actual_stage_pool():
    _, spec, state, p = initialized("fuel5")
    _, model, parent = OWNERS["fuel5"]
    spec, p, times, history, _ = trajectory("fuel5", "SIM", 1)
    actual = model.STATE_TYPE(*(v[-1] for v in history))
    physical = model.parent_state(actual)
    current = parent.stage_layout(physical, model.parent_layout(p), xp=np)
    amount = parent.energy_amounts(physical, model.parent_layout(p))
    concentration = amount / p.volume
    for prefix, owners, present in (
        ("pump_", p.membrane_cell, p.pump_present),
        ("pmca_", p.membrane_cell, p.pmca_present),
        ("er_pump_", np.arange(p.er_pump_present.size), p.er_pump_present),
    ):
        for i, species in enumerate(("atp", "adp", "pi")):
            key = prefix + species + ("_mM" if prefix == "pump_" else "")
            np.testing.assert_allclose(
                getattr(current, key)[present],
                concentration[i, owners[present]],
                rtol=3e-14,
                atol=0,
            )
    assert np.any(actual.energy_amount_increment_fmol != 0)
    exhausted = state._replace(energy_amount_increment_fmol=-np.array(p.energy_initial_amount_fmol))
    assert not model.domain_valid(exhausted, p, p.active, xp=np)
    with pytest.raises(NumericalError):
        model.check_values(exhausted, spec)
    unpaid = np.array(actual.energy_amount_increment_fmol)
    unpaid[0, 0] += 1e-3
    with pytest.raises(NumericalError):
        model.check_values(actual._replace(energy_amount_increment_fmol=unpaid), spec)
    evidence(
        "live-fuel",
        dict(
            all_three_pumps_actual_stage_ATP_ADP_Pi=True,
            finite_pool_changes=True,
            exhaustion_refused=True,
            unrecorded_pool_change_refused=True,
        ),
    )


@pytest.mark.parametrize("family", fixtures.FAMILIES)
def test_upper_permeability_used_for_chemical_loss_bound_and_full_recipe(family):
    raw, spec, _, _ = initialized(family)
    definition, model, parent = OWNERS[family]
    record = definition.artifact(spec)
    assert definition.replay(json.loads(json.dumps(record))) == spec
    assert definition.parse(definition.to_dict(spec)) == spec
    times = np.asarray(list(EventGrid(spec)))
    controls = control_values(spec, times[:-1])
    model.check_steps(spec, np.diff(times), controls)
    exaggerated = replace(
        spec,
        model=replace(
            spec.model,
            interventions=tuple(replace(e, amplitude=1e12) for e in spec.model.interventions),
        ),
    )
    with pytest.raises(ConfigError):
        model.check_steps(exaggerated, np.asarray([spec.execution.dt]), control_values(spec, [0.0]))
    evidence(
        "recipe-" + family,
        dict(
            inputs=raw,
            artifact=record,
            full_recipe_roundtrip=True,
            conservative_scheduled_chemical_bound=True,
        ),
    )


@pytest.mark.parametrize("family", fixtures.FAMILIES)
@pytest.mark.parametrize(
    "fault", ["owner", "store", "fuel", "pressure", "negative-P", "phase", "history-reset"]
)
def test_wrong_owner_store_fuel_and_reset_contract_refused(family, fault):
    raw = deepcopy(initialized(family)[0])
    definition = OWNERS[family][0]
    m = raw["model"]
    if fault == "owner":
        m["ionic"]["channels"][0]["membrane_id"] = "missing"
    if fault == "store":
        m["stores"][0]["cell_id"] = "missing"
    if fault == "fuel":
        if family == "fuel5":
            m["energy_pools"][0]["initial_amount_fmol"]["ATP"] *= 2
        else:
            m["plasma_transport"]["membranes"][0]["pump"]["atp_mM"] *= 2
    if fault == "pressure":
        m["interventions"][0]["kind"] = "pressure"
    if fault == "negative-P":
        m["interventions"][0]["amplitude"] = -1e12
    if fault == "phase":
        m["phase"] = "automatic"
    if fault == "history-reset":
        m["reset_policy"] = "reset_all_stores_and_pools"
    with pytest.raises((ConfigError, ValueError, TypeError)):
        definition.parse(raw)
    evidence("refused-" + family + "-" + fault, dict(fault=fault, refused=True))


@pytest.mark.parametrize("family", fixtures.FAMILIES)
def test_actual_chemical_owner_and_phase_clock_cannot_be_repaired(family):
    from types import SimpleNamespace

    _, spec, state, p = initialized(family)
    _, model, _ = OWNERS[family]
    cp = SimpleNamespace(state=state, time=0.0)
    model.check_checkpoint(spec, cp)
    with pytest.raises(ConfigError):
        model.check_checkpoint(
            spec, SimpleNamespace(state=state._replace(phase_clock_s=np.asarray([1e-7])), time=0.0)
        )
    with pytest.raises(ConfigError):
        model.check_steps(spec, np.asarray([1e-6]), control_values(spec, [0.0]))
    bad = np.array(state.chemical_amount_increment)
    bad.flat[0] += 1e-3
    corrupt = state._replace(chemical_amount_increment=bad)
    assert not model.domain_valid(corrupt, p, p.active, xp=np)
    with pytest.raises(NumericalError):
        model.check_values(corrupt, spec)
    for clock in (-1e-9, spec.experiment.end_time + 1e-9):
        assert not model.domain_valid(
            state._replace(phase_clock_s=np.asarray([clock])), p, p.active, xp=np
        )
    evidence(
        "physical-refusals-" + family,
        dict(
            chemical_ownership_corruption_refused=True,
            checkpoint_clock_mismatch_refused=True,
            coarse_ramp_refused=True,
            out_of_phase_clock_refused=True,
            no_physical_repair=True,
        ),
    )


@pytest.mark.parametrize("family", fixtures.FAMILIES)
@pytest.mark.skipif(
    os.environ.get("CELLS_COMPONENT_PHASE") != "jax", reason="separate bounded CPU JAX process"
)
def test_cpu_jax_eager_complete_owner_rhs_and_abstract_trace(family):
    _, spec, state, p = initialized(family)
    _, model, _ = OWNERS[family]
    trial = state._replace(phase_clock_s=np.asarray([2e-6]))
    u = control(spec, 2e-6)
    y, q, v = (jax.tree.map(jnp.asarray, a) for a in (trial, p, u))
    actual = model.rhs(y, v, q, q.active)
    expected = model.rhs(trial, u, p, p.active, xp=np)
    for name, a, b in zip(model.STATE_TYPE._fields, actual, expected, strict=True):
        np.testing.assert_allclose(a, b, rtol=3e-10, atol=3e-23 if name.endswith("_C") else 3e-12)
    shaped = jax.eval_shape(lambda s: model.rhs(s, v, q, q.active), y)
    assert type(shaped) is model.STATE_TYPE
    assert [a.shape for a in shaped] == [a.shape for a in y]
    slope = jax.grad(
        lambda t: model.signal_values(y._replace(phase_clock_s=t[None]), q).scheduled[0, 0]
    )(jnp.asarray(1e-6))
    assert np.isfinite(slope) and slope != 0
    evidence(
        "cpu-jax-eager-" + family,
        dict(
            full_rhs_parity=True,
            actual_store_and_fuel_owner=True,
            abstract_trace_preserves_full_state=True,
            channel_populations=len(spec.model.channels),
            fields=list(model.STATE_TYPE._fields),
            pulse_time_derivative=float(slope),
            compiled_trajectory=False,
        ),
    )


@pytest.mark.parametrize("family", fixtures.FAMILIES)
@pytest.mark.skipif(
    os.environ.get("CELLS_COMPONENT_PHASE") != "public", reason="separate bounded public process"
)
def test_public_short_complete_owner_snapshot_and_exact_resume(family, tmp_path):
    from cells.core.runner import branch_checkpoint

    definition, model, _ = OWNERS[family]
    raw = build(fixtures.public_inputs(family), family)
    spec = parse_spec(raw)
    assert spec.to_dict() == definition.to_dict(spec)
    complete = run(spec)
    cp = complete.checkpoint_at(1e-9)
    loaded = load_snapshot(write_snapshot(tmp_path / "snapshot", spec, cp))
    resumed = run(loaded.spec, loaded.checkpoint)
    for a, b in zip(complete.final.state, resumed.final.state, strict=True):
        np.testing.assert_array_equal(a, b)
    for name in model.STATE_TYPE._fields:
        np.testing.assert_array_equal(
            getattr(complete.observations, name), getattr(complete.history, name)
        )
    assert np.any(complete.final.state.chemical_amount_increment != 0)
    assert np.any(complete.final.state.channel_gate != complete.history.channel_gate[0])
    if family == "fuel5":
        assert np.any(complete.final.state.energy_amount_increment_fmol != 0)
    changed = deepcopy(raw)
    changed["model"]["phase"] = "INIT"
    with pytest.raises(ConfigError):
        branch_checkpoint(spec, cp, parse_spec(changed))
    with pytest.raises(ConfigError):
        run(spec, replace(cp, state=cp.state._replace(phase_clock_s=np.zeros(1))))
    evidence(
        "public-replay-" + family,
        dict(
            inputs=raw,
            artifact=definition.artifact(spec),
            steps=2,
            snapshot_resume_exact=True,
            all_actual_states_observed=True,
            actual_chemical_and_fuel_owner_evolves=True,
            phase_branch_refused=True,
            checkpoint_clock_reset_refused=True,
            compiled_trajectory=False,
            diagnostics=complete.diagnostics,
        ),
    )


def test_critical_dependencies_and_owner_call_graph_are_pinned():
    protocol = json.loads(
        (ROOT / "validation/topology/owned_calcium_profile_interventions_protocol.json").read_text()
    )
    assert "validation/betse/contact.py" in protocol["readonly_source_sha256"]
    for name, expected in protocol["readonly_source_sha256"].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected, name
    functions = {}
    for row in protocol["owner_call_graph"]:
        content = (ROOT / row["path"]).read_bytes()
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
            functions[row["path"] + ":" + name] = node
            parents = {c: owner for owner in ast.walk(node) for c in ast.iter_child_nodes(owner)}
            attributes, calls, other = set(), set(), set()
            for value in ast.walk(node):
                if (
                    isinstance(value, ast.Name)
                    and value.id == "state"
                    and isinstance(value.ctx, ast.Load)
                ):
                    owner = parents[value]
                    if isinstance(owner, ast.Attribute):
                        attributes.add(owner.attr)
                    elif isinstance(owner, ast.Call):
                        calls.add(ast.unparse(owner.func))
                    else:
                        other.add(type(owner).__name__)
            assert (
                dict(attributes=sorted(attributes), calls=sorted(calls), other=sorted(other))
                == row["state_flow"][name]
            )

    def flow(module, name):
        row = next(
            r
            for r in protocol["owner_call_graph"]
            if r["path"] == "src/cells/models/" + module + ".py"
        )
        return row["state_flow"][name]

    # The physical subgraph has exactly these state edges. The sole full-history
    # passthrough is to copied parent state and boolean validity; no transfer
    # ledger enters free calcium, field, channel gating, or live pump parameters.
    assert flow("surface_kinetic", "readouts") == dict(
        attributes=["channel_gate", "junction_gate"],
        calls=["base.field_values", "domain_valid", "physical_amounts"],
        other=[],
    )
    assert flow("surface_tissue", "field_values") == dict(
        attributes=[], calls=["charge_increment", "physical_amounts"], other=[]
    )
    for name in ("physical_amounts", "charge_increment"):
        assert flow("surface_tissue", name) == dict(
            attributes=["amount_increment", "extracellular_amount_increment"], calls=[], other=[]
        )
    assert flow("surface_calcium", "readouts") == dict(
        attributes=["calcium_gate", "extracellular_amount_increment"],
        calls=["domain_valid", "ionic_layout", "ionic_state", "ip3_readouts", "store_state"],
        other=[],
    )
    assert flow("surface_calcium", "ionic_layout") == dict(
        attributes=[], calls=["cytosol_amount"], other=[]
    )
    assert flow("spatial_calcium", "cytosol_amount") == dict(
        attributes=[], calls=["store_state"], other=[]
    )
    assert flow("ip3_calcium", "ip3_readouts") == dict(
        attributes=["chemical_amount_increment"], calls=[], other=[]
    )
    assert flow("surface_calcium_energy", "readouts") == dict(
        attributes=[],
        calls=["domain_valid", "energy_amounts", "prior_state", "stage_layout"],
        other=[],
    )
    assert flow("surface_calcium_energy", "stage_layout") == dict(
        attributes=[], calls=["energy_amounts"], other=[]
    )
    assert flow("surface_calcium_energy", "energy_amounts") == dict(
        attributes=["energy_amount_increment_fmol"], calls=[], other=[]
    )
    for module, name in (
        ("surface_calcium", "ionic_state"),
        ("surface_calcium_energy", "prior_state"),
        ("spatial_calcium", "store_state"),
    ):
        assert flow(module, name) == dict(attributes=[], calls=["getattr"], other=[])
    from cells.models import spatial_calcium

    assert "membrane_transferred" not in spatial_calcium.ER_FIELDS
    for module in (reference, fixtures):
        for node in ast.walk(ast.parse(Path(module.__file__).read_text())):
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith(("cells", "jax"))
    evidence(
        "call-graph",
        dict(
            owner_call_graph=protocol["owner_call_graph"],
            contact_require_pinned=True,
            explicit_physical_owners=True,
            independent_full_owner_references=True,
        ),
    )
