"""AST/hash-only disabled ordinary flow reachability and ownership audit."""

import ast
import copy
import hashlib
import json
from pathlib import Path

PREFIX = "validation/betse/betse_normal_ecm_flow_join_"
CORE = "src/cells/processes/betse_normal_ecm_flow_join.py"
TEST = "tests/unit/test_betse_normal_ecm_flow_join.py"
LEGACY = Path("/mnt/workspaces/Cells/betse-fluid-flow-development-20261029-07")
LEGACY_SHA256 = "96c8ef38e86096f3713a5c97b2a7697bf2c945e9695bb4bf4f5f408b4d9a34bd"
FLOW_PROTOCOL = "validation/flow/betse_fluid_flow_protocol.json"
DEPENDENCIES = (
    "src/cells/processes/betse_normal_ecm_mechanics_join.py",
    "src/cells/processes/betse_mechanics_join.py",
    "src/cells/processes/betse_normal_ecm_field_join.py",
    "src/cells/processes/betse_ecm_grn_join.py",
    "src/cells/processes/betse_ecm_grn_source.py",
    "src/cells/processes/betse_ecm_transport.py",
    "src/cells/processes/betse_environment_field.py",
    "src/cells/processes/betse_normal_ion_join.py",
    "src/cells/processes/betse_fluid_flow.py",
    "src/cells/processes/betse_deformation.py",
    "src/cells/processes/betse_environment_transport.py",
    "src/cells/processes/betse_geometry.py",
    "validation/betse/betse_normal_ecm_mechanics_join_native.py",
    "validation/betse/betse_normal_ecm_mechanics_join_boundaries.py",
    "validation/betse/betse_normal_ecm_mechanics_join_fixtures.py",
    "validation/betse/betse_normal_ecm_field_join_native.py",
    "validation/betse/betse_mechanics_join_native.py",
    "validation/betse/betse_mechanics_join_runtime.py",
    "validation/geometry/stable_geometry_primitives_runtime.py",
    "validation/flow/betse_fluid_flow_native.py",
    "validation/flow/betse_fluid_flow_reference.py",
    "validation/flow/betse_fluid_flow_fixtures.py",
    FLOW_PROTOCOL,
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


def calls(node, name):
    return [n for n in ast.walk(node) if isinstance(n, ast.Call) and ast.unparse(n.func) == name]


def site(rel, node):
    return dict(
        source=rel,
        first_line=node.lineno,
        last_line=node.end_lineno,
        ast_sha256=hashlib.sha256(dump(node).encode()).hexdigest(),
    )


def reachability(project):
    protocol = read(project / FLOW_PROTOCOL)
    root = Path(protocol["native_source"]["checkout"])
    installed = Path(protocol["native_source"]["installed_package"]).parent
    pins = protocol["native_source"]["source_sha256"]
    for rel, pin in pins.items():
        assert sha(root / rel) == pin == sha(installed / rel), rel
    trees = {rel: tree(root / rel) for rel in pins if rel.endswith(".py")}
    parameters, sim, gene = (
        trees["betse/science/" + name + ".py"] for name in ("parameters", "sim", "chemistry/gene")
    )
    loader = {}
    for name in ("fluid_flow", "mu_water", "td_deform"):
        nodes = [
            n
            for n in ast.walk(parameters)
            if isinstance(n, ast.Assign)
            and any(ast.unparse(t) == "self." + name for t in n.targets)
        ]
        assert len(nodes) == 1
        loader[name] = dict(
            value=ast.literal_eval(nodes[0].value), **site("betse/science/parameters.py", nodes[0])
        )
    assert {k: v["value"] for k, v in loader.items()} == dict(
        fluid_flow=False, mu_water=0.01, td_deform=False
    )
    normal = function(sim, "_run_sim_core_loop")
    order = [
        (name, calls(normal, name)[0])
        for name in (
            "self.update_ecm",
            "self.grn.core.run_loop",
            "osmotic_P",
            "getFlow",
            "getDeformation",
            "self.update_all_concs",
            "self.update_V",
        )
    ]
    assert all(a[1].lineno < b[1].lineno for a, b in zip(order, order[1:], strict=False))
    conditional = [
        n
        for n in ast.walk(normal)
        if isinstance(n, ast.If) and ast.unparse(n.test) == "p.fluid_flow"
    ]
    assert len(conditional) == 1 and len(calls(conditional[0], "getFlow")) == 1
    assert not calls(function(sim, "_run_fast_sim_core_loop"), "getFlow")
    assert not [
        n
        for n in ast.walk(normal)
        if isinstance(n, ast.Assign) and any(ast.unparse(t) == "p.fluid_flow" for t in n.targets)
    ]
    consumer = function(sim, "update_ecm")
    consumer_gate = next(
        n
        for n in ast.walk(consumer)
        if isinstance(n, ast.If) and ast.unparse(n.test) == "p.fluid_flow is True"
    )
    assert ast.unparse(consumer_gate.orelse[0]) == "ux = np.zeros(cells.X.shape)"
    assert ast.unparse(consumer_gate.orelse[1]) == "uy = np.zeros(cells.X.shape)"
    get_flow = function(trees["betse/science/physics/flow.py"], "getFlow")
    flow_reads = sorted(
        {
            n.attr
            for n in ast.walk(get_flow)
            if isinstance(n, ast.Attribute)
            and isinstance(n.value, ast.Name)
            and n.value.id == "sim"
            and isinstance(n.ctx, ast.Load)
        }
    )
    assert not {"P_cells", "PP", "osmo_P_cell", "osmo_P_env", "d_cells_x", "d_cells_y"} & set(
        flow_reads
    )
    activation = next(
        n
        for n in ast.walk(gene)
        if isinstance(n, ast.If)
        and ast.unparse(n.test) == "self.recalc_fluid"
        and "p.fluid_flow = True" in ast.unparse(n)
    )
    owner = next(
        n
        for n in ast.walk(gene)
        if isinstance(n, ast.FunctionDef) and activation in list(ast.walk(n))
    )
    assert owner.name == "run_core_sim"
    flags = []
    for method in [n for n in ast.walk(gene) if isinstance(n, ast.FunctionDef)]:
        for n in method.body:
            if isinstance(n, ast.Assign) and any(
                ast.unparse(t) == "self.recalc_fluid" for t in n.targets
            ):
                flags.append(
                    dict(
                        method=method.name,
                        source_expression=ast.unparse(n),
                        **site("betse/science/chemistry/gene.py", n),
                    )
                )
    assert len(flags) == 2
    future = dict(
        kind="standalone_GRN_flow_activation_future_composition@1",
        source_method="MasterOfGenes.run_core_sim",
        ordinary_dispatch_reachable=False,
        source_site=site("betse/science/chemistry/gene.py", activation),
        exact_source_fragment=ast.unparse(activation),
        configuration_readers=flags,
        prerequisites=[
            "Standalone GRN reinitialize phase before its loop",
            "Actual environment current J_env_x/y on complete grid owners",
            "All current cc_env species and zs valences plus F and cells.X.shape",
            "Source flag self.recalc_fluid; no substituted ordinary YAML switch",
        ],
        effects=["p.fluid_flow=True", "u_env_x/y=-J_env_x/y/(F*mean(cc_env)*mean(zs))"],
        getFlow_called=False,
        cell_flow_written=False,
        denominator_floor=False,
        zero_mean_concentration_or_valence_may_be_nonfinite=True,
        source_executed=False,
        future_composition_implemented=False,
    )
    return dict(
        source_sha256=pins,
        loader=loader,
        ordinary_order={name: site("betse/science/sim.py", node) for name, node in order},
        conditional_gate=site("betse/science/sim.py", conditional[0]),
        consumer=site("betse/science/sim.py", consumer_gate),
        preceding_transport_reads_previous_flow_store_only_if_enabled=True,
        ordinary_flow_enabled=False,
        fast_getFlow_calls=0,
        getFlow_sim_read_set=flow_reads,
        pressure_and_displacement_not_flow_inputs=True,
        standalone_GRN_activation=future,
    )


def reuse_standalone(project):
    assert sha(LEGACY / "result.json") == LEGACY_SHA256
    result = read(LEGACY / "result.json")
    assert result["status"] == "passed" and result["tests"] == dict(
        tests=64, errors=0, failures=0, skipped=0
    )
    paths = [rel for rel in result["source_sha256"] if "betse_fluid_flow" in rel]
    assert len(paths) == 7
    preserved = {}
    for rel in paths:
        pin = result["source_sha256"][rel]
        assert sha(project / rel) == pin == sha(LEGACY / "sources" / rel), rel
        preserved[rel] = pin
    rel = "src/cells/processes/betse_deformation.py"
    before, after = tree(LEGACY / "sources" / rel), tree(project / rel)
    normalized = copy.deepcopy(after)
    previous = function(before, "quartic_display_interpolator")
    for index, node in enumerate(normalized.body):
        if isinstance(node, ast.FunctionDef) and node.name == "quartic_display_interpolator":
            normalized.body[index] = previous
    assert dump(before) == dump(normalized)
    flow = tree(project / "src/cells/processes/betse_fluid_flow.py")
    called = {ast.unparse(n.func) for n in ast.walk(flow) if isinstance(n, ast.Call)}
    assert not any("quartic_display" in name for name in called)
    for name in ("validate_operators", "rotation_only", "divergence_numeric"):
        assert dump(function(before, name)) == dump(function(after, name)), name
    return dict(
        receipt=str(LEGACY / "result.json"),
        receipt_sha256=LEGACY_SHA256,
        qualified_tests=64,
        preserved_seven_component_sources=preserved,
        relevant_deformation_dependency_AST_unchanged=True,
        sole_unrelated_dependency_AST_change="quartic_display_interpolator",
        display_admitted_by_new_composition=False,
        prior_receipt_edited=False,
        new_equation_panel=False,
        new_owner_qualification_inherited=False,
    )


def new_scope(project):
    core = tree(project / CORE)
    branch = function(core, "advance")
    assert len(calls(branch, "ordinary.advance")) == 1
    assert len(calls(function(core, "initialize"), "ordinary.initialize")) == 1
    assert len(calls(function(core, "bind"), "ordinary.bind")) == 1
    forbidden = {
        "getFlow",
        "flow.flow",
        "flow.cell_flow",
        "flow.environment_flow",
        "flow.grn_current_flow",
        "ordinary.field.material_step",
        "solve_ivp",
        "rk4_step",
        "graphLaplacian",
    }
    assert not forbidden & {ast.unparse(n.func) for n in ast.walk(core) if isinstance(n, ast.Call)}
    assignments = [
        ast.unparse(t) for n in ast.walk(core) if isinstance(n, ast.Assign) for t in n.targets
    ]
    assert not any(
        t.startswith(("ctx.sim.", "parent.", "binding.ordinary.", "p.fluid_flow"))
        for t in assignments
    )
    point = function(core, "_point")
    assert len(calls(point, "_same_arrays")) == 2
    assert "complete_cache_before_flow" in ast.unparse(
        point
    ) and "complete_cache_after_flow" in ast.unparse(point)
    assert "traceback.format_exc()" in ast.unparse(branch)
    assert "original_partial" in ast.unparse(branch) and "completed_flow_point" in ast.unparse(
        branch
    )
    mechanics = tree(project / "src/cells/processes/betse_mechanics_join.py")
    existing = function(mechanics, "step")
    disabled = calls(existing, "flow.flow")
    assert len(disabled) == 1 and any(
        k.arg == "fluid_flow" and isinstance(k.value, ast.Constant) and k.value.value is False
        for k in disabled[0].keywords
    )
    return dict(
        new_core_sha256=sha(project / CORE),
        existing_disabled_component_gate=site(
            "src/cells/processes/betse_mechanics_join.py", disabled[0]
        ),
        source_sites={
            name: site(CORE, function(core, name))
            for name in ("bind", "initialize", "_point", "advance", "standalone_diagnostic_input")
        },
        ordinary_equations_and_order_delegated_unchanged=True,
        complete_field_current_material_pressure_and_cache_owners_retained=True,
        exact_typed_flow_carry_and_noop_cache_required=True,
        diagnostic_export_only_no_new_flow_or_unit_conversion=True,
        complete_original_failure_and_precommit_point_retained=True,
        physical_conservation_or_moving_geometry_claim=False,
    )


def audit(project):
    project = Path(project)
    sources = {rel: sha(project / rel) for rel in DEPENDENCIES}
    source = reachability(project)
    fixtures = tree(project / (PREFIX + "fixtures.py"))
    literals = {
        t.id: ast.literal_eval(n.value)
        for n in fixtures.body
        if isinstance(n, ast.Assign)
        for t in n.targets
        if isinstance(t, ast.Name)
    }
    assert len(literals["CASES"]) == len(literals["REFUSALS"]) == 2
    tests = tree(project / TEST)
    functions = [
        n for n in tests.body if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")
    ]
    assert len(functions) == 3
    ids = [
        TEST + "::test_disabled_flow_carries_complete_ordinary_source_owners[" + case + "]"
        for case in literals["CASES"]
    ]
    ids += [
        TEST + "::test_unsupported_activation_or_flow_feedback_is_refused[" + case + "]"
        for case in literals["REFUSALS"]
    ]
    ids += [TEST + "::test_precommit_observer_failure_retains_the_complete_disabled_flow_seam"]
    assert len(ids) == len(set(ids)) == 5
    assert len(calls(function(tests, "child"), "subprocess.Popen")) == 1
    return dict(
        kind="cells.betse_ordinary_disabled_flow_ownership_source_audit@1",
        source_only=True,
        source_correspondence=source,
        standalone_qualification=reuse_standalone(project),
        new_scope=new_scope(project),
        unchanged_dependency_sha256=sources,
        prospective=dict(
            exact_source_predicted_test_ids=ids,
            pytest_trees=5,
            functions=3,
            existing_ordinary_specimen_ids=list(literals["CASES"]),
            new_scientific_cases=0,
            disabled_boundary_points=6,
            nested_native_children=2,
            nested_stdlib_conditional_children=2,
            new_active_flow_equation_cases=0,
            fixture_materializations=0,
            tests_executed=0,
            collected=False,
        ),
        resources=dict(new_launcher_or_finalizer_prepared=False, measured_sufficiency=False),
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
