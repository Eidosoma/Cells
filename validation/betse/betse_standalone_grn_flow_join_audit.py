"""AST/hash-only audit of reachable standalone GRN flow and held advection."""

import ast
import copy
import hashlib
import json
from pathlib import Path

PREFIX = "validation/betse/betse_standalone_grn_flow_join_"
CORE = "src/cells/processes/betse_standalone_grn_flow_join.py"
TEST = "tests/unit/test_betse_standalone_grn_flow_join.py"
ENGINE, REFERENCE = PREFIX + "engine.py", PREFIX + "reference.py"
WORK = Path("/mnt/workspaces/Cells")
FLOW_RECEIPT = WORK / "betse-fluid-flow-development-20261029-07/result.json"
FLOW_RECEIPT_SHA256 = "96c8ef38e86096f3713a5c97b2a7697bf2c945e9695bb4bf4f5f408b4d9a34bd"
DEPENDENCIES = (
    "src/cells/processes/betse_ecm_sim_grn.py",
    "src/cells/processes/betse_ecm_grn_source.py",
    "src/cells/processes/betse_ecm_transport.py",
    "src/cells/processes/betse_environment_field.py",
    "src/cells/processes/betse_normal_ion_join.py",
    "src/cells/processes/betse_fluid_flow.py",
    "validation/betse/betse_ecm_sim_grn_native.py",
    "validation/betse/betse_ecm_sim_grn_reference.py",
    "validation/betse/betse_ecm_sim_grn_fixtures.py",
    "validation/betse/betse_ecm_sim_grn_protocol.json",
    "validation/betse/betse_ecm_grn_native_network.py",
    "validation/betse/betse_mechanics_join_runtime.py",
    "validation/betse/betse_normal_ecm_mechanics_join_boundaries.py",
    "validation/geometry/stable_geometry_primitives_runtime.py",
    "validation/flow/betse_fluid_flow_protocol.json",
    "tests/unit/test_betse_ecm_sim_grn.py",
    "tests/unit/test_betse_fluid_flow.py",
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def tree(path):
    return ast.parse(Path(path).read_bytes())


def dump(node):
    return ast.dump(node, include_attributes=False)


def function(module, name):
    return next(n for n in ast.walk(module) if isinstance(n, ast.FunctionDef) and n.name == name)


def literal(module, name):
    return ast.literal_eval(
        next(
            n.value
            for n in module.body
            if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == name for t in n.targets)
        )
    )


def calls(node, name):
    return [n for n in ast.walk(node) if isinstance(n, ast.Call) and ast.unparse(n.func) == name]


def site(relative, node):
    return dict(
        source=relative,
        first_line=node.lineno,
        last_line=node.end_lineno,
        ast_sha256=hashlib.sha256(dump(node).encode()).hexdigest(),
    )


class Clean(ast.NodeTransformer):
    def visit_Expr(self, node):
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            return None
        if isinstance(node.value, ast.Call) and ast.unparse(node.value.func) == "observe":
            return None
        return self.generic_visit(node)

    def visit_FunctionDef(self, node):
        node.decorator_list = []
        node.returns = None
        for arg in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs):
            arg.annotation = None
        return self.generic_visit(node)


def source_order(project):
    protocol = read(project / "validation/flow/betse_fluid_flow_protocol.json")["native_source"]
    root = Path(protocol["checkout"])
    paths = {
        rel: pin
        for rel, pin in protocol["source_sha256"].items()
        if rel
        in {
            "betse/science/chemistry/gene.py",
            "betse/science/chemistry/networks.py",
            "betse/science/physics/flow.py",
            "betse/science/sim.py",
        }
    }
    for rel, pin in paths.items():
        assert sha(root / rel) == pin, rel
    inherited = read(project / "validation/betse/betse_ecm_sim_grn_protocol.json")["native_source"]
    runtime_pins = inherited["source_sha256"]
    for rel, pin in runtime_pins.items():
        assert sha(Path(inherited["checkout"]) / rel) == pin, rel
        assert sha(Path(inherited["installed_package"]).parent / rel) == pin, rel
    gene = tree(root / "betse/science/chemistry/gene.py")
    original = function(gene, "run_core_sim")
    parent = tree(project / "src/cells/processes/betse_ecm_sim_grn.py")
    reproduced = function(parent, "run_core_sim")
    normalized = [Clean().visit(copy.deepcopy(n)) for n in (original, reproduced)]
    assert dump(normalized[0]) == dump(normalized[1]), (
        "Parent runner equations differ from pinned source"
    )
    activation = next(
        n
        for n in ast.walk(original)
        if isinstance(n, ast.If)
        and ast.unparse(n.test) == "self.recalc_fluid"
        and "p.fluid_flow = True" in ast.unparse(n)
    )
    clear = calls(original, "self.core.clear_cache")[0]
    reinit = calls(original, "self.reinitialize")[0]
    loop = next(n for n in original.body if isinstance(n, ast.For) and ast.unparse(n.iter) == "tt")
    assert reinit.lineno < clear.lineno < activation.lineno < loop.lineno
    assert not calls(loop, "getFlow") and not calls(original, "getFlow")
    forbidden = {
        "osmotic_P",
        "self.update_V",
        "self.update_all_concs",
        "timeDeform",
        "getDeformation",
    }
    assert not forbidden & {
        ast.unparse(n.func) for n in ast.walk(original) if isinstance(n, ast.Call)
    }
    source = tree(project / "src/cells/processes/betse_ecm_grn_source.py")
    mover = function(source, "molecule_mover")
    flow = next(
        n
        for n in ast.walk(mover)
        if isinstance(n, ast.If) and ast.unparse(n.test) == "p.fluid_flow is True"
    )
    flux = function(source, "nernst_planck_flux")
    assert "ux * c" in ast.unparse(flux) and "uy * c" in ast.unparse(flux)
    return dict(
        pinned_native_sources=paths,
        complete_inherited_native_runtime_pins=runtime_pins,
        complete_parent_runner_normalized_AST_matches_native=True,
        once_per_invocation_after_reinitialize_and_clear_cache=True,
        activation=site("betse/science/chemistry/gene.py", activation),
        exact_activation_source=ast.unparse(activation),
        source_loop=site("betse/science/chemistry/gene.py", loop),
        molecular_velocity_consumer=site("src/cells/processes/betse_ecm_grn_source.py", flow),
        advection_expression=site("src/cells/processes/betse_ecm_grn_source.py", flux),
        pressure_electric_ionic_or_geometry_updates=False,
        ordinary_getFlow_called=False,
        no_flow_inverse_or_Poisson_solve_in_this_source_branch=True,
        standalone_velocity_units="m/s",
        ECM_getFlow_output_imported_or_converted=False,
    )


def runtime_scope(project):
    engine = tree(project / ENGINE)
    pins = literal(engine, "PARENTS")
    for relative, pin in pins.values():
        assert sha(project / relative) == pin, relative
    load = function(engine, "load_parent")
    assert len(calls(load, "exec")) == 1 and len(calls(load, "compile")) == 1
    compiled = calls(load, "compile")[0]
    assert ast.unparse(compiled.args[0]) == "source"
    assert calls(load, "hashlib.sha256")[0].lineno < calls(load, "exec")[0].lineno
    assert "sys.modules[name] = module" in ast.unparse(load)
    assert not calls(load, "ast.parse") and not calls(load, "ast.unparse")
    install = function(engine, "install")
    replacements = [
        ast.unparse(t)
        for n in ast.walk(install)
        if isinstance(n, ast.Assign)
        for t in n.targets
        if isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name) and t.value.id == "parent"
    ]
    assert set(replacements) == {
        "parent.validate",
        "parent.make_context",
        "parent.new_trace",
        "parent.observe",
        "parent.local_inputs",
        "parent.attach",
        "parent.configure_call",
        "parent.plt",
        "parent.viz",
    }
    core = tree(project / CORE)
    advance = function(core, "advance")
    assert len(calls(advance, "ctx.owner.run_core_sim")) == 1
    assert len(calls(function(core, "component_flow_readout"), "flow.grn_current_flow")) == 1
    assert not calls(advance, "flow.grn_current_flow")
    assert "complete_source_return" in ast.unparse(advance)
    assert (
        calls(advance, "runtime.snapshot")[0].lineno
        < calls(advance, "engine.nonfinite_arrays")[0].lineno
    )
    assert "original_partial" in ast.unparse(advance) and "traceback.format_exc()" in ast.unparse(
        advance
    )
    assert len(calls(advance, "engine.observe_flow_execution")) == 1
    observed = function(engine, "observe_flow_execution")
    assert "frame.f_locals.get('cc')" in ast.unparse(observed)
    assert "frame.f_locals.get('zz')" in ast.unparse(observed)
    return dict(
        authenticated_parent_sha256=pins,
        parent_code_compiled_verbatim=True,
        existing_module_globals_edited=False,
        private_namespace_registered_for_complete_runtime_inventory=True,
        private_replacements=replacements,
        admission_projection=site(ENGINE, function(engine, "parent_view")),
        actual_activation_is_unchanged_parent_code=True,
        complete_current_pressure_electric_and_velocity_fields=literal(engine, "EXTRA_FIELDS"),
        actual_source_mean_and_partial_velocity_locals_retained_read_only=True,
        original_source_faults_not_repaired=True,
        nonfinite_source_return_retained_before_candidate_gate=True,
        plotting_inputs_captured_without_rendering_or_physics=True,
        source_sites={
            name: site(ENGINE, function(engine, name))
            for name in ("load_parent", "install", "parent_view", "nonfinite_arrays")
        },
    )


def independent_extension(project):
    before = tree(project / "validation/betse/betse_ecm_sim_grn_reference.py")
    after = tree(project / REFERENCE)
    old = function(before, "ecm_environment")
    new = function(after, "ecm_environment")
    old_assignments = {
        ast.unparse(n.targets[0]): n for n in ast.walk(old) if isinstance(n, ast.Assign)
    }
    normalized = copy.deepcopy(new)
    additions = {}
    for node in ast.walk(normalized):
        if not isinstance(node, ast.Assign):
            continue
        name = ast.unparse(node.targets[0])
        if name not in {"fx[i][j]", "fy[i][j]", "fxg[i][j]", "fyg[i][j]"}:
            continue
        assert isinstance(node.value, ast.BinOp) and isinstance(node.value.op, ast.Add)
        assert dump(node.value.left) == dump(old_assignments[name].value)
        axis = "x" if name.startswith("fx") else "y"
        velocity = (
            "(d(inputs['velocity_" + axis + "_m_s'][i][j]) if inputs['fluid_flow'] else zero)"
        )
        expected = (
            "abs(" + velocity + ") * ig[i][j]" if "g[" in name else velocity + " * image[i][j]"
        )
        assert dump(node.value.right) == dump(ast.parse(expected, mode="eval").body)
        additions[name] = ast.unparse(node.value.right)
        node.value = old_assignments[name].value
    assert len(additions) == 4 and dump(normalized) == dump(old)
    reference_imports = []
    for module in (after, tree(project / ENGINE)):
        for node in module.body:
            if isinstance(node, ast.Import):
                reference_imports.extend(n.name for n in node.names)
            if isinstance(node, ast.ImportFrom):
                reference_imports.append(node.module)
    assert not {name.split(".")[0] for name in reference_imports} & {
        "numpy",
        "scipy",
        "jax",
        "cells",
        "betse",
    }
    assert "100 if refinement == 1 else 160" in ast.unparse(function(after, "flow_activation"))
    return dict(
        parent_reference_sha256=sha(project / "validation/betse/betse_ecm_sim_grn_reference.py"),
        complete_environment_function_AST_unchanged_except=additions,
        remaining_chemistry_clocks_stencils_and_books_inherited_verbatim=True,
        gross_advection_uses_only_actual_incoming_velocity_and_independent_concentration=True,
        separate_Decimal_current_flow_readout=True,
        precisions=[100, 160],
        complete_raw_preprojection_and_partial_reference_retention=True,
        independent_trajectory=False,
        carried_reference_forms=0,
        old_budget_factors_floors_and_self_resolution_limits_unchanged=True,
    )


def audit(project):
    project = Path(project)
    assert sha(FLOW_RECEIPT) == FLOW_RECEIPT_SHA256
    legacy = read(FLOW_RECEIPT)
    flow_source = "src/cells/processes/betse_fluid_flow.py"
    assert sha(project / flow_source) == legacy["source_sha256"][flow_source]
    fixtures = tree(project / (PREFIX + "fixtures.py"))
    groups = {name: literal(fixtures, name) for name in ("CASES", "RAW_CASES", "DEPENDENCIES")}
    assert tuple(map(len, groups.values())) == (4, 2, 4)
    tests = tree(project / TEST)
    names = [
        n.name for n in tests.body if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")
    ]
    assert len(names) == 3
    roster = [
        TEST + "::" + name + "[" + case + "]"
        for name, key in zip(names, groups, strict=True)
        for case in groups[key]
    ]
    assert len(roster) == len(set(roster)) == 10
    assert len(calls(function(tests, "child"), "subprocess.Popen")) == 1
    return dict(
        kind="cells.betse_standalone_GRN_flow_advection_source_audit@1",
        source_only=True,
        source_order=source_order(project),
        runtime=runtime_scope(project),
        independent_reference=independent_extension(project),
        existing_flow_component_receipt_sha256=FLOW_RECEIPT_SHA256,
        existing_flow_component_used_at_actual_activation_inputs=True,
        prior_qualification_does_not_qualify_new_composition=True,
        unchanged_dependency_sha256={rel: sha(project / rel) for rel in DEPENDENCIES},
        prospective=dict(
            exact_source_predicted_test_ids=roster,
            pytest_trees=10,
            functions=3,
            positive_contexts=4,
            new_active_contexts=2,
            component_controls=2,
            raw_defect_controls=2,
            dependency_controls=4,
            invocations_per_positive_context=2,
            warm_points_per_positive_context=7,
            cold_points=4,
            clock_points=8,
            flow_decision_points=8,
            actual_recalculation_points=6,
            warm_points=28,
            total_conditional_points=48,
            fresh_reference_precision_forms=96,
            nested_native_children=6,
            nested_reference_children=4,
            fixture_materializations=0,
            tests_executed=0,
            collected=False,
        ),
        source_review_pending=True,
        numerical_launch_authorized=False,
        scientific_imports=0,
        model_or_reference_evaluations=0,
        fixtures=0,
        tests=0,
        collection=0,
        jobs=0,
        GPU=0,
        PROGRESS_edited=False,
    )
