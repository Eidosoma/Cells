"""Source/AST-only first-interval semantics audit; never import model or tests."""

import ast
import hashlib
import json
from pathlib import Path

CORE = "src/cells/processes/stable_seed_partition_advance.py"
TEST = "tests/unit/test_stable_seed_partition_advance.py"
INITIAL = Path("/mnt/workspaces/Cells/stable-seed-partition-physiology-bridge-prepared-20261031-01")
INITIAL_SHA256 = "92caecd20cba1973336f14a005492a144393740fae3d6cd3be32a2636a8fcf26"
FINITE = Path("/mnt/workspaces/Cells/finite-ecm-polygon-prepared-20261031-01")
FINITE_SHA256 = "232f5762460fd03d8990a65648e7f264dccb4b8f6ee5e2514f431d127041bc9f"
DYNAMICS_PROTOCOL = "validation/tissue/surface_dynamics_protocol.json"
DYNAMICS_REFERENCE = "validation/tissue/surface_dynamics_reference.py"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def literal(tree, name):
    return ast.literal_eval(
        next(
            n.value
            for n in tree.body
            if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == name for t in n.targets)
        )
    )


def function(tree, name):
    return next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name)


def calls(node, name):
    return [n for n in ast.walk(node) if isinstance(n, ast.Call) and ast.unparse(n.func) == name]


def call_line(node, name):
    return min(n.lineno for n in calls(node, name))


def retained(node, name):
    return next(
        n.lineno
        for n in calls(node, "retain")
        if isinstance(n.args[0], ast.Constant) and n.args[0].value == name
    )


def site(rel, node):
    return dict(
        source=rel,
        first_line=node.lineno,
        last_line=node.end_lineno,
        ast_sha256=hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest(),
    )


def audit(project):
    project = Path(project)
    assert sha(INITIAL / "manifest.json") == INITIAL_SHA256
    assert sha(FINITE / "manifest.json") == FINITE_SHA256
    initial_files = json.loads((INITIAL / "manifest.json").read_text())["file_sha256"]
    finite_files = json.loads((FINITE / "manifest.json").read_text())["file_sha256"]
    assert len(initial_files) == 503
    for rel, pin in initial_files.items():
        assert sha(INITIAL / rel) == pin, rel
    old_plan = json.loads(
        (
            INITIAL
            / "source/agent-work/cells-specialist/stable_seed_partition_physiology_bridge_plan.json"
        ).read_text()
    )
    original_live = old_plan["owned_source_sha256"]
    for rel, pin in original_live.items():
        assert sha(project / rel) == pin, rel
    assert len(original_live) == 12
    core, tests = (ast.parse((project / rel).read_bytes()) for rel in (CORE, TEST))
    assert literal(core, "DRAFT_ONLY") is True
    assert literal(core, "INITIAL_SOURCE_REVIEW_SHA256") is None
    assert literal(core, "INITIAL_NUMERICAL_QUALIFICATION_SHA256") is None
    assert literal(core, "INITIAL_MANIFEST_SHA256") == INITIAL_SHA256
    assert isinstance(function(core, "_qualification_gate").body[0], ast.If)
    assert isinstance(function(core, "_qualification_gate").body[0].body[0], ast.Raise)
    origins = {}
    for rel, pin in literal(core, "SOURCE_PINS").items():
        parent, records = (
            (INITIAL, initial_files) if "source/" + rel in initial_files else (FINITE, finite_files)
        )
        assert records["source/" + rel] == pin == sha(parent / "source" / rel) == sha(project / rel)
        origins[rel] = dict(bundle=str(parent), sha256=pin)
    assert len(origins) == 13
    fixed_path = "src/cells/numerics/fixed_step.py"
    model_path = "src/cells/models/surface_tissue.py"
    runner_path = "src/cells/core/runner.py"
    grid_path = "src/cells/core/grid.py"
    schedule_path = "src/cells/core/schedule.py"
    fixed, model, runner, grid, schedule = (
        ast.parse((project / rel).read_bytes())
        for rel in (fixed_path, model_path, runner_path, grid_path, schedule_path)
    )
    operation = function(core, "_cells_trial")
    checked = calls(operation, "rk4_checked_step")
    assert len(checked) == 1
    assert [ast.unparse(n) for n in checked[0].args] == [
        "rhs",
        "guard",
        "state",
        "step",
        "held",
        "layout",
        "layout.active",
    ]
    assert len(calls(operation, "jax.disable_jit")) == 1
    assert not calls(operation, "jax.tree.map")
    assert len(calls(function(operation, "contextual"), "model.control_domain_valid")) == 1
    assert any(
        isinstance(n, ast.Assign)
        and ast.unparse(n.targets[0]) == "guard.with_control"
        and ast.unparse(n.value) == "contextual"
        for n in operation.body
    )
    rhs = function(operation, "rhs")
    assert call_line(rhs, "model.field_values") < call_line(rhs, "model.derivative_from_field")
    composition = function(model, "rhs")
    assert [ast.unparse(n.func) for n in ast.walk(composition) if isinstance(n, ast.Call)] == [
        "field_values",
        "derivative_from_field",
    ]
    assert ast.unparse(composition.args.kw_defaults[0]) == "jnp"
    assert not calls(rhs, "model.rhs")
    assert retained(operation, "cells_checked_kernel_return") < next(
        n.lineno
        for n in calls(operation, "_require")
        if any(
            isinstance(arg, ast.Constant)
            and arg.value == "existing_cells_rk4_trial_or_endpoint_domain_failed"
            for arg in n.args
        )
    )
    run = function(core, "advance")
    assert call_line(run, "_qualification_gate") < min(
        n.lineno for n in ast.walk(run) if isinstance(n, (ast.Import, ast.ImportFrom))
    )
    assert call_line(run, "model.balances") < call_line(run, "model.check_values")
    assert retained(run, "raw_existing_endpoint_balances") < call_line(run, "model.check_values")
    assert call_line(run, "model.field_values") < call_line(run, "model.derivative_from_field")
    assert len(calls(run, "_cells_trial")) == 1
    assert len(calls(run, "validate_checkpoint")) == 2
    assert not calls(core, "initial._initial_accounting")
    assert not calls(core, "initial._initial_snapshot")
    assert not calls(core, "initial.prepare")
    assert not calls(core, "rk4_step") and not calls(core, "array_rk4_step")
    assert isinstance(function(core, "require_continuation").body[0], ast.Raise)
    names = {ast.unparse(n.func) for n in ast.walk(core) if isinstance(n, ast.Call)}
    assert not names & {"solve_ivp", "run", "retry", "refine", "subdivide"}
    initial_map = json.loads(
        (
            INITIAL
            / "source/validation/geometry/stable_seed_partition_physiology_bridge_source_map.json"
        ).read_text()
    )
    inventory = initial_map["complete_named_array_inventory"]
    state_units = {
        name: ("C" if name.endswith("_C") else "pJ" if name.endswith("_pJ") else "fmol")
        for name in inventory["state"]
    }
    layout_units = {name: "1" for name in inventory["layout"]}
    layout_units.update(
        temperature="K",
        membrane_area="m2",
        junction_area="m2",
        membrane_capacitance="F",
        membrane_permeability="m/s",
        junction_permeability="m/s",
        face_factor="m3/s",
        field_capacitor_matrix="F",
        field_capacitor_scale="F",
        volume="pL",
        extracellular_volume="pL",
        amount_reference="fmol",
        extracellular_amount_reference="fmol",
        initial_cell_charge_C="C",
        initial_outside_charge_C="C",
        boundary_V="V",
        initial_membrane_voltage_V="V",
    )
    assert set(layout_units) == set(inventory["layout"]) and len(layout_units) == 40
    assert len(state_units) == 12
    for rel in (DYNAMICS_PROTOCOL, DYNAMICS_REFERENCE):
        assert sha(FINITE / "source" / rel) == finite_files["source/" + rel] == sha(project / rel)
    dynamics = json.loads((project / DYNAMICS_PROTOCOL).read_text())
    caller = json.loads(
        (
            INITIAL
            / "source/validation/geometry/stable_seed_partition_physiology_bridge_callers.json"
        ).read_text()
    )
    assert caller["shared"]["execution"]["dt"] == caller["shared"]["experiment"]["end_time"] == 1e-6
    case_ids = literal(tests, "CASES")
    assert list(case_ids) == [r["id"] for r in caller["cases"]]
    test_functions = [
        n for n in tests.body if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")
    ]
    assert len(test_functions) == 7
    positive = "test_first_interval_preserves_units_layout_and_matches_existing_cells_driver"
    ids = [TEST + "::" + positive + "[" + case + "]" for case in case_ids] + [
        TEST + "::" + n.name for n in test_functions if n.name != positive
    ]
    assert len(ids) == len(set(ids)) == 10
    helper = function(tests, "approved_input")
    assert call_line(helper, "advance._qualification_gate") < min(
        n.lineno for n in ast.walk(helper) if isinstance(n, ast.ImportFrom)
    )
    assert not any(
        isinstance(n, ast.Call)
        and (
            ast.unparse(n.func).endswith("fixtures.declaration")
            or ast.unparse(n.func).endswith("fixtures.definition")
        )
        for n in ast.walk(tests)
    )
    field_sites = dict(
        existing_Cells_checked_RK4=site(fixed_path, function(fixed, "rk4_checked_step")),
        existing_Cells_eager_driver=site(runner_path, function(runner, "_checked_eager_rollout")),
        exact_original_clock=site(grid_path, function(grid, "__init__")),
        right_continuous_controls=site(schedule_path, function(schedule, "control_values")),
        field_and_RHS=site(model_path, function(model, "rhs")),
        actual_control_domain=site(model_path, function(model, "control_domain_valid")),
        integrated_balances=site(model_path, function(model, "balances")),
        existing_acceptance=site(model_path, function(model, "check_values")),
        existing_step_limits=site(model_path, function(model, "check_steps")),
    )
    return dict(
        kind="cells.partition_first_interval_unfrozen_source_audit@1",
        status="source_candidate_existing_Cells_stepping_initial_qualification_pending",
        source_only=True,
        core_sha256=sha(project / CORE),
        source_pins=origins,
        initial_packet=dict(
            path=str(INITIAL),
            manifest_sha256=INITIAL_SHA256,
            verified_files=503,
            original_live_owned_files_unchanged=12,
        ),
        source_sites=field_sites,
        units=dict(
            state=state_units,
            layout=layout_units,
            step="s",
            RHS_amount="fmol/s",
            RHS_charge="C/s",
            RHS_energy="pJ/s",
            physical_values_and_typed_layout_carried_bitwise=True,
        ),
        field_order=dict(
            existing_Cells_control_aware_guard_then_RHS=True,
            guard_recomputes_own_field=True,
            RHS_recomputes_own_field=True,
            no_field_cache_adopted=True,
            held_control_at_all_RK_stages=True,
            unmasked_endpoint_captured_before_kernel_old_state_fallback=True,
            right_continuous_endpoint_readout_after_existing_integrated_checks=True,
            production_RHS_composition_preserved=True,
            time_zero_only_accounting_helper_reused_after_advancement=False,
        ),
        acceptance=dict(
            existing_Cells_model_check_values_on_two_boundary_history=True,
            every_state_ledger_carried=True,
            local_and_global_material=True,
            charge_increment_from_actual_state=True,
            finite_node_capacitor_constraints=True,
            reservoir_electrode_work_ledgers_carried=True,
            existing_energy_budget_pJ=dynamics["tolerances"]["energy_atol_pJ"],
            existing_dissipation_monotonicity_pJ=dynamics["tolerances"][
                "dissipation_monotonicity_atol_pJ"
            ],
            new_physical_law=False,
            clipping_or_repair=False,
        ),
        prospective_tests=dict(
            exact_ids=ids,
            pytest_trees=10,
            functions=7,
            metadata_trees=4,
            same_existing_initial_case_driver_comparisons=4,
            failure_capture_controls=2,
            independent_reference_children_prepared=0,
            new_scientific_cases=0,
            collected=False,
            executed=0,
            requires_existing_qualified_input_index=True,
        ),
        refinement=dict(
            status="blocked_at_explicit_initial_caller_scope",
            original_dt_s=1e-6,
            original_endpoint_s=1e-6,
            separate_caller_definitions_required=True,
            common_endpoint_required=True,
            silent_subdivision_or_retry_permitted=False,
            initial_worker_currently_binds_four_fixed_dt_declarations=True,
            unresolved_choice=(
                "Reviewed initial caller/worker successor or explicitly reviewed "
                "clock-metadata equivalence"
            ),
            no_qualification_inherited_across_clock_change=True,
            existing_family_reference_protocol=dict(
                source=DYNAMICS_PROTOCOL,
                sha256=sha(project / DYNAMICS_PROTOCOL),
                tolerances=dynamics["tolerances"],
            ),
            existing_independent_dynamics_source=dict(
                source=DYNAMICS_REFERENCE,
                sha256=sha(project / DYNAMICS_REFERENCE),
                imported_or_executed=False,
            ),
        ),
        gate=dict(
            DRAFT_ONLY=True,
            initial_source_review=None,
            initial_numerical_qualification=None,
            numerical_execution_permitted=False,
            final_source_freeze=False,
        ),
        limits=dict(
            first_original_interval_only=True,
            continuation=False,
            native_BETSE_equivalence=False,
            moving_geometry=False,
            inferred_parameters=False,
            GPU=False,
        ),
        activity=dict(
            scientific_imports=0,
            model_or_reference_evaluations=0,
            fixtures=0,
            tests=0,
            collection=0,
            jobs=0,
            polls=0,
            PROGRESS_edited=False,
            initial_packet_or_sources_edited=False,
        ),
    )
