"""AST/source-only audit of the unfrozen initial-physiology bridge draft."""

import ast
import copy
import hashlib
import json
from pathlib import Path

CORE = "src/cells/processes/stable_seed_partition_physiology_bridge.py"
FINITE = Path("/mnt/workspaces/Cells/finite-ecm-polygon-prepared-20261031-01")
FINITE_SHA256 = "232f5762460fd03d8990a65648e7f264dccb4b8f6ee5e2514f431d127041bc9f"
ECM = Path("/mnt/workspaces/Cells/stable-seed-explicit-ecm-partition-prepared-20261031-02")
ECM_SHA256 = "5b6257f7a8f0f8a51b6903fb55aba11fe34c0934f2e10351e377a42eee81b406"
SOURCES = "src/cells/core/finite_ecm_polygon_sources.json"
SOURCES_SHA256 = "4d6196c9332ab0353d0eb513fbae2c00c5232ac4ce6a19f2bd5ad6a7da5c86f2"
DENIED = {"cells", "betse", "numpy", "scipy", "jax", "jaxlib", "PIL", "torch"}
PREFIX = "validation/geometry/stable_seed_partition_physiology_bridge_"
REFERENCE = PREFIX + "reference.py"
ENGINE = PREFIX + "initial_reference.py"
SCALAR = PREFIX + "scalar_reference.py"
FIELD = PREFIX + "field_reference.py"
DECLARATIONS = PREFIX + "declarations.py"
CALLERS = PREFIX + "callers.json"
CONTROLS = PREFIX + "controls.json"
UPSTREAM_REVIEW = Path(
    "/mnt/workspaces/Cells/stable-seed-explicit-ecm-partition-preflight-20261031-02/REVIEW.json"
)
UPSTREAM_REVIEW_SHA256 = "a8c09e4245079f55784e62d79e62d05e616dc5a665de5fb62b5235365b6078c7"
UPSTREAM_VERDICT = "clear_for_prospective_guarded_qualification_preparation"
UPSTREAM_REFERENCE_SHA256 = "5b2240bf02166ae4bc73e03a669611d3328448fe1dd5824919ccbf59dc8f702c"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def assignment(tree, name):
    return next(
        node.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == name for t in node.targets)
    )


def literal(tree, name):
    return ast.literal_eval(assignment(tree, name))


def function(tree, name):
    return next(
        node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == name
    )


def calls(node):
    return [ast.unparse(n.func) for n in ast.walk(node) if isinstance(n, ast.Call)]


def fields(tree, name):
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == name)
    return [n.target.id for n in cls.body if isinstance(n, ast.AnnAssign)]


def site(path, node):
    return dict(
        source=path,
        first_line=node.lineno,
        last_line=node.end_lineno,
        ast_sha256=hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest(),
    )


def call_line(node, name):
    return next(
        n.lineno for n in ast.walk(node) if isinstance(n, ast.Call) and ast.unparse(n.func) == name
    )


def observer_line(node, stage):
    return next(
        n.lineno
        for n in ast.walk(node)
        if isinstance(n, ast.Call)
        and ast.unparse(n.func) == "observer"
        and isinstance(n.args[0], ast.Constant)
        and n.args[0].value == stage
    )


def accepted_review_scope(project):
    """Only review binding/capture metadata changed after the held draft02."""
    project = Path(project)
    prior = Path("/mnt/workspaces/Cells/stable-seed-partition-physiology-bridge-draft-20261031-02")
    receipt_sha = "65d07354254eef6521b796749214b3aa6ec6190173b40cb5552a216c916eeda6"
    assert sha(prior / "receipt.json") == receipt_sha
    receipt = json.loads((prior / "receipt.json").read_text())
    for rel, expected in receipt["source_sha256"].items():
        assert sha(prior / "original-source-capture" / rel) == expected
    before = ast.parse((prior / "original-source-capture" / CORE).read_bytes())
    after = ast.parse((project / CORE).read_bytes())
    normalized = copy.deepcopy(after)
    normalized.body[0] = before.body[0]
    permitted = {
        "UPSTREAM_SOURCE_REVIEW_SHA256",
        "UPSTREAM_PREPARED_MANIFEST_SHA256",
        "UPSTREAM_REFERENCE_SHA256",
        "UPSTREAM_SOURCE_REVIEW_STATUS",
        "DRAFT_ONLY",
    }
    for i, node in enumerate(normalized.body):
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
        ):
            name = node.targets[0].id
            if name in permitted:
                normalized.body[i] = next(
                    n
                    for n in before.body
                    if isinstance(n, ast.Assign)
                    and any(isinstance(t, ast.Name) and t.id == name for t in n.targets)
                )
        elif isinstance(node, ast.FunctionDef) and node.name == "_source_review":
            normalized.body[i] = function(before, "_source_review")
    assert ast.dump(normalized, include_attributes=False) == ast.dump(
        before, include_attributes=False
    )
    unchanged = {}
    for rel in (ENGINE, SCALAR, FIELD, DECLARATIONS, CONTROLS):
        assert sha(project / rel) == receipt["source_sha256"][rel]
        unchanged[rel] = sha(project / rel)
    old_caller = json.loads((prior / "original-source-capture" / CALLERS).read_text())
    new_caller = json.loads((project / CALLERS).read_text())
    new_caller["geometry"] = old_caller["geometry"]
    assert new_caller == old_caller
    return dict(
        original_draft02_receipt_sha256=receipt_sha,
        original_source_files_preserved=12,
        production_numeric_AST_unchanged_outside_exact_review_gate=True,
        numerical_helpers_declarations_controls_unchanged=unchanged,
        physical_caller_parameters_unchanged=True,
        science_or_tests_executed=False,
    )


def independent_source(project, inventory):
    project = Path(project)
    reference, engine, scalar, field, declarations = (
        ast.parse((project / rel).read_bytes())
        for rel in (REFERENCE, ENGINE, SCALAR, FIELD, DECLARATIONS)
    )
    for name, expected in (
        ("UPSTREAM_SOURCE_REVIEW_SHA256", UPSTREAM_REVIEW_SHA256),
        ("UPSTREAM_SOURCE_REVIEW_STATUS", UPSTREAM_VERDICT),
        ("UPSTREAM_PREPARED_MANIFEST_SHA256", ECM_SHA256),
        ("UPSTREAM_GEOMETRY_REFERENCE_SHA256", UPSTREAM_REFERENCE_SHA256),
    ):
        assert literal(reference, name) == expected
    assert literal(reference, "DRAFT_ONLY") is False
    assert literal(reference, "BRIDGE_CORE_SHA256") == sha(project / CORE)
    assert call_line(function(reference, "authenticate"), "gate") < next(
        n.lineno
        for n in ast.walk(function(reference, "authenticate"))
        if isinstance(n, ast.ImportFrom)
    )
    assert call_line(function(reference, "evaluate"), "authenticate") < next(
        n.lineno for n in ast.walk(function(reference, "evaluate")) if isinstance(n, ast.ImportFrom)
    )
    paths = {}
    for key, value in zip(
        assignment(reference, "HELPER_PINS").keys,
        assignment(reference, "HELPER_PINS").values,
        strict=True,
    ):
        if isinstance(key, ast.Constant):
            rel = ast.literal_eval(key)
        else:
            assert isinstance(key, ast.BinOp) and isinstance(key.op, ast.Add)
            assert ast.unparse(key.left) == "PREFIX"
            rel = literal(reference, "PREFIX") + ast.literal_eval(key.right)
        paths[rel] = ast.literal_eval(value)
    for rel, pin in paths.items():
        assert sha(project / rel) == pin, rel
    for name, rel in (("CALLERS_SHA256", CALLERS), ("CONTROLS_SHA256", CONTROLS)):
        assert literal(reference, name) == sha(project / rel)
    closure, pending = {}, [REFERENCE]
    denied = {"cells", "betse", "jax", "jaxlib", "PIL", "torch"}
    while pending:
        rel = pending.pop()
        if rel in closure:
            continue
        tree = ast.parse((project / rel).read_bytes())
        imports, local = [], set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = [n.name for n in node.names]
            elif isinstance(node, ast.ImportFrom):
                assert node.level == 0
                modules = [node.module + "." + n.name for n in node.names]
            else:
                continue
            for module in modules:
                assert module.split(".")[0] not in denied
                assert "integrat" not in module
                imports.append(module)
                parts = module.split(".")
                for end in range(len(parts), 0, -1):
                    candidate = "/".join(parts[:end]) + ".py"
                    if (project / candidate).is_file():
                        local.add(candidate)
                        pending.append(candidate)
                        break
        closure[rel] = dict(
            sha256=sha(project / rel),
            imports=sorted(imports),
            local_dependencies=sorted(local),
            imported_or_executed=False,
        )
    assert len(closure) == 8
    sources = {
        "validation/betse/junction_transport/check.py": ("decimal_flux",),
        "validation/tissue/reference.py": ("bernoulli",),
        "validation/tissue/surface_reference.py": ("logarithmic_mean", "transport", "accounting"),
        "validation/tissue/surface_field_reference.py": ("topology", "currents", "check"),
    }
    unchanged = []
    old_field = None
    for rel, names in sources.items():
        original = ast.parse((FINITE / "source" / rel).read_bytes())
        new = field if "surface_field" in rel else scalar
        if new is field:
            old_field = original
        for name in names:
            assert ast.dump(function(original, name), include_attributes=False) == ast.dump(
                function(new, name), include_attributes=False
            )
            unchanged.append(
                dict(source=rel, function=name, source_sha256=sha(FINITE / "source" / rel))
            )
    old, new = function(old_field, "solve"), copy.deepcopy(function(field, "solve"))
    assert [n.arg for n in new.args.args] == ["raw", "partial"]
    new.args.args.pop()
    extra = [
        n
        for n in new.body
        if isinstance(n, ast.Assign)
        and isinstance(n.targets[0], ast.Subscript)
        and ast.unparse(n.targets[0].value) == "partial"
    ]
    assert len(extra) == 7
    new.body = [n for n in new.body if n not in extra]
    assert ast.dump(old, include_attributes=False) == ast.dump(new, include_attributes=False)
    solve = function(field, "solve")
    index = next(
        i
        for i, n in enumerate(solve.body)
        if isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) == "answer"
    )
    assert ast.unparse(solve.body[index + 1].targets[0]) == "partial['root_return']"
    original_caller = copy.deepcopy(
        function(
            ast.parse(
                (
                    ECM
                    / "source/validation/geometry/stable_seed_explicit_ecm_partition_fixtures.py"
                ).read_bytes()
            ),
            "declaration",
        )
    )
    reconstructed_caller = copy.deepcopy(function(declarations, "geometry_declaration"))
    reconstructed_caller.name = "declaration"
    reconstructed_caller.body.pop(0)
    upstream = ast.parse(
        (project / "src/cells/processes/stable_seed_explicit_ecm_partition.py").read_bytes()
    )

    class CallerMetadataConstants(ast.NodeTransformer):
        def visit_Attribute(self, node):
            if isinstance(node.value, ast.Name) and node.value.id == "constructor":
                assert node.attr in {"INPUT_KIND", "LAW_ID"}
                return ast.Constant(value=literal(upstream, node.attr))
            return self.generic_visit(node)

    original_caller = CallerMetadataConstants().visit(original_caller)
    assert ast.dump(original_caller, include_attributes=False) == ast.dump(
        reconstructed_caller, include_attributes=False
    )
    assert tuple(inventory["state"]) == literal(engine, "STATE_FIELDS")
    field_values = next(
        n.value
        for n in ast.walk(function(engine, "solve_initial"))
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "values" for t in n.targets)
    )
    assert {n.arg for n in field_values.keywords} == set(inventory["field"])
    assert {"quantity.number", "quantity.multiply", "quantity.divide", "quantity.subtract"} <= set(
        calls(function(engine, "materialize"))
    )
    assert not {"Fraction", "quantity.evaluate", "geometry.evaluate", "schema.parse"} & set(
        calls(engine)
    )
    verify = function(reference, "verify")
    assert len(verify.body[1].handlers) == 1
    assert ast.unparse(verify.body[1].handlers[0].type) == "engine.SnapshotRejected"
    assert "engine.derive" in calls(function(reference, "evaluate"))
    assert calls(function(reference, "evaluate")).count("engine.derive") == 1
    caller = json.loads((project / CALLERS).read_text())
    controls = json.loads((project / CONTROLS).read_text())
    ids = [row["id"] for row in caller["cases"]]
    assert ids == [
        "uniform-two-species",
        "unequal-clefts-readback-defects",
        "two-cell-four-species",
        "four-cell-reordered-gradient",
    ]
    assert (
        caller["qualification"]["materialized_cases"]
        == caller["qualification"]["evaluated_cases"]
        == 0
    )
    assert caller["geometry"]["manifest_sha256"] == ECM_SHA256
    assert caller["geometry"]["caller_document_sha256"] == sha(
        project / "validation/geometry/stable_seed_explicit_ecm_partition_callers.json"
    )
    for row in caller["cases"]:
        names = {r["id"] for r in row["species"]}
        for key in (
            "cell_concentration_mM",
            "membrane_permeability_m_per_s",
            "membrane_diffusivity_m2_per_s",
            "face_diffusivity_m2_per_s",
        ):
            assert set(row[key]) == names
        assert all(set(r) == names for r in row["bath_concentration_by_slot_y_mM"])

    def branch_names(node):
        result = set()
        for comparison in ast.walk(node):
            if not isinstance(comparison, ast.Compare) or ast.unparse(comparison.left) != "name":
                continue
            target = comparison.comparators[0]
            if isinstance(target, ast.Constant):
                result.add(ast.literal_eval(target))
            elif isinstance(target, ast.Set):
                result.update(ast.literal_eval(target))
        return result

    output_ids = [row["id"] for row in controls["output_controls"]]
    input_ids = [row["id"] for row in controls["input_controls"]]
    assert branch_names(function(declarations, "changed_preparation")) == set(output_ids)
    assert branch_names(function(declarations, "changed_declaration")) == set(input_ids)
    assert len(output_ids) == 26 and len(input_ids) == 16
    assert len(set(output_ids)) == 26 and len(set(input_ids)) == 16
    assert all(
        row["expected_exception_type"] and row["expected_reason"]
        for row in controls["input_controls"]
    )
    return dict(
        source_only=True,
        worker_source=REFERENCE,
        helper_closure=closure,
        unchanged_frozen_function_ASTs=unchanged,
        helper_functions_unchanged=8,
        full_node_solve_inverse_AST_equal_after_removing_partial_assignments=True,
        full_node_solve_inserted_partial_assignments=[ast.unparse(n) for n in extra],
        root_return_saved_immediately_before_gates=True,
        original_geometry_caller_body_AST_equal_after_metadata_constant_substitution=True,
        physical_case_declaration_ids=ids,
        literal_case_declarations=4,
        materialized_physical_cases=0,
        evaluated_physical_cases=0,
        physical_input_control_ids=input_ids,
        physical_output_control_ids=output_ids,
        metadata_control_ids=[row["id"] for row in controls["metadata_controls"]],
        controls_count_as_cases=False,
        all_controls_unmaterialized_unrun=True,
        complete_named_field_counts={k: len(v) for k, v in inventory.items()},
        normalized_residuals_bound_and_readback_checked=True,
        production_iteration_counter_domain_checked_independent_count_not_claimed=True,
        caller_parameters_inferred=False,
        parameter_values_numerically_evaluated=False,
        upstream_source_review_bound=True,
        final_source_only_freeze_permitted=True,
        numerical_launch_authorized=False,
        accepted_review_binding_scope=accepted_review_scope(project),
    )


def audit(project):
    project = Path(project)
    assert sha(FINITE / "manifest.json") == FINITE_SHA256
    assert sha(ECM / "manifest.json") == ECM_SHA256
    assert sha(UPSTREAM_REVIEW) == UPSTREAM_REVIEW_SHA256
    reviewed = json.loads(UPSTREAM_REVIEW.read_text())
    assert reviewed["verdict"] == UPSTREAM_VERDICT and reviewed["blockers"] == []
    assert reviewed["packet"]["manifest_sha256"] == ECM_SHA256
    manifests = {
        "finite_ECM01": json.loads((FINITE / "manifest.json").read_text())["file_sha256"],
        "explicit_ECM02": json.loads((ECM / "manifest.json").read_text())["file_sha256"],
    }
    tree = ast.parse((project / CORE).read_bytes())
    for name, expected in (
        ("UPSTREAM_SOURCE_REVIEW_SHA256", UPSTREAM_REVIEW_SHA256),
        ("UPSTREAM_PREPARED_MANIFEST_SHA256", ECM_SHA256),
        ("UPSTREAM_REFERENCE_SHA256", UPSTREAM_REFERENCE_SHA256),
        ("UPSTREAM_SOURCE_REVIEW_STATUS", UPSTREAM_VERDICT),
    ):
        assert literal(tree, name) == expected
    assert literal(tree, "DRAFT_ONLY") is False
    review = function(tree, "_source_review")
    assert isinstance(review.body[0], ast.If)
    assert isinstance(review.body[0].body[0], ast.Raise)
    assert calls(function(tree, "_accepted_geometry"))[0] == "_source_review"
    assert calls(function(tree, "bind"))[0] == "_accepted_geometry"
    assert isinstance(function(tree, "require_advancement").body[0], ast.Raise)
    pins = literal(tree, "SOURCE_PINS")
    origins = {}
    for rel, expected in pins.items():
        parent = (
            "explicit_ECM02"
            if rel.endswith("stable_seed_explicit_ecm_partition.py")
            else "finite_ECM01"
        )
        frozen = ECM if parent == "explicit_ECM02" else FINITE
        assert manifests[parent]["source/" + rel] == expected
        assert sha(frozen / "source" / rel) == expected == sha(project / rel), rel
        origins[rel] = dict(bundle=str(frozen), sha256=expected)
    assert len(origins) == 10 and sha(project / SOURCES) == SOURCES_SHA256
    assert manifests["finite_ECM01"]["source/" + SOURCES] == SOURCES_SHA256
    source_pins = json.loads((project / SOURCES).read_text())["source_sha256"]
    closure_rows = []
    for rel, expected in source_pins.items():
        assert manifests["finite_ECM01"]["source/" + rel] == expected
        assert sha(FINITE / "source" / rel) == expected
        closure_rows.append(dict(source=rel, sha256=expected))
    model_path = "src/cells/models/surface_tissue.py"
    field_path = "src/cells/numerics/surface_field.py"
    surface_path = "src/cells/numerics/surface_transport.py"
    schedule_path = "src/cells/core/schedule.py"
    model, field, surface, schedule = (
        ast.parse((project / rel).read_bytes())
        for rel in (model_path, field_path, surface_path, schedule_path)
    )
    state_fields = list(literal(model, "STATE_AXES"))
    layout = assignment(model, "LAYOUT_TYPE").args[1].generators[0].iter
    assert (
        isinstance(layout, ast.Tuple) and sum(isinstance(n, ast.Starred) for n in layout.elts) == 2
    )
    tail = [ast.literal_eval(n) for n in layout.elts if not isinstance(n, ast.Starred)]
    layout_fields = (
        fields(surface, "Layout")
        + ["field_" + name for name in fields(field, "Layout") if name != "surface"]
        + tail
    )
    inventory = dict(
        state=state_fields,
        rhs=list(state_fields),
        layout=layout_fields,
        control=fields(schedule, "SurfaceControl"),
        field=fields(field, "Values"),
        rates=fields(surface, "Rates"),
    )
    assert (
        len(state_fields) == 12 and len(inventory["field"]) == 21 and len(inventory["rates"]) == 19
    )
    assert len(layout_fields) == len(set(layout_fields)) == 40
    snapshot = function(tree, "_initial_snapshot")
    expected_calls = {
        "schema.parse",
        "model.initial_values",
        "control_values",
        "model.field_values",
        "model.derivative_from_field",
        "model.check_values",
        "model.domain_valid",
        "_initial_accounting",
    }
    assert expected_calls <= set(calls(snapshot))
    assert calls(snapshot).count("model.field_values") == 1
    assert observer_line(snapshot, "initial_state_layout_control") < call_line(
        snapshot, "model.field_values"
    )
    assert observer_line(snapshot, "initial_field_return") < call_line(
        snapshot, "model.derivative_from_field"
    )
    assert observer_line(snapshot, "initial_RHS_return") < call_line(
        snapshot, "_initial_accounting"
    )
    assert observer_line(snapshot, "initial_accounting_return") < call_line(
        snapshot, "model.check_values"
    )
    assert observer_line(snapshot, "initial_state_diagnostics_return") < call_line(
        snapshot, "model.domain_valid"
    )
    arrays = function(snapshot, "arrays")
    assert {"value._asdict", "np.asarray", "array.tobytes"} <= set(calls(arrays))
    source = ast.unparse(arrays)
    assert "typed_C_order_array_bytes@1" in source and "dtype=array.dtype.str" in source
    assert (
        "shape=list(array.shape)" in source and "data_hex=array.tobytes(order='C').hex()" in source
    )
    conversion = function(tree, "_materialize")
    projection = function(conversion, "project")
    assert call_line(projection, "observer") < call_line(projection, "exact._rounded")
    observer_sites = sorted(
        n.lineno
        for n in ast.walk(projection)
        if isinstance(n, ast.Call) and ast.unparse(n.func) == "observer"
    )
    assert len(observer_sites) == 2 and observer_sites[1] > call_line(projection, "exact._rounded")
    conversion_source = ast.unparse(conversion)
    assert "Fraction.from_float(concentration) * Fraction.from_float(volume)" in conversion_source
    assert "Fraction.from_float(amount) / Fraction.from_float(volume)" in conversion_source
    assert "Fraction.from_float(diffusion) / thickness" in conversion_source
    assert "projected.hex() != row['permeability_m_per_s'][ion].hex()" in conversion_source
    assert "fixed_charge_equivalent_fmol" not in conversion_source
    assert "plain(anchors[family][name])" in conversion_source
    declaration = function(tree, "_declaration")
    declaration_source = ast.unparse(declaration)
    assert "provided_prior_state_or_operators" in declaration_source
    assert "[0.0]" in declaration_source and "gauge_reference" in declaration_source
    protocol = json.loads((project / "validation/tissue/surface_field_protocol.json").read_text())
    tolerance = protocol["tolerances"]
    for key, target in (
        ("MATERIAL_RATE_ATOL_FMOL_S", tolerance["material_rate_atol_fmol_s"]),
        ("ENERGY_BALANCE_ATOL_PJ_S", tolerance["energy_balance_atol_pJ_s"]),
        ("POWER_COMPARISON_ATOL_PJ_S", tolerance["power_atol_pJ_s"]),
        ("ACCOUNTING_RTOL", tolerance["charge_rtol"]),
    ):
        assert literal(tree, key) == target
    assert literal(field, "CHARGE_ATOL_C") == tolerance["charge_atol_C"]
    assert literal(field, "CHARGE_RTOL") == tolerance["charge_rtol"]
    assert literal(field, "CURRENT_ATOL_A") == tolerance["current_constraint_atol_A"]
    assert literal(field, "CURRENT_RTOL") == tolerance["current_constraint_rtol"]
    forbidden = {"solve_ivp", "rollout", "step", "rk4", "checkpoint", "run"}
    assert all(name.split(".")[-1] not in forbidden for name in calls(tree))
    assert not any(
        isinstance(n, (ast.Import, ast.ImportFrom))
        and (
            isinstance(n, ast.ImportFrom)
            and "integrat" in (n.module or "")
            or isinstance(n, ast.Import)
            and any("integrat" in a.name for a in n.names)
        )
        for n in ast.walk(tree)
    )
    schema = ast.parse((project / "src/cells/core/surface_tissue_spec.py").read_bytes())
    admission = ast.parse(
        (project / "src/cells/core/finite_ecm_polygon_preparation.py").read_bytes()
    )
    assert "check_definition" in calls(function(schema, "parse"))
    assert "schema.parse" in calls(function(admission, "prepare"))
    assert "control_domain_valid" in calls(function(model, "check_definition"))
    reference_paths = [
        "validation/tissue/surface_field_reference.py",
        "validation/tissue/surface_reference.py",
        "validation/tissue/reference.py",
        "validation/betse/junction_transport/check.py",
    ]
    references = {}
    for rel in reference_paths:
        expected = manifests["finite_ECM01"]["source/" + rel]
        assert sha(FINITE / "source" / rel) == expected == sha(project / rel)
        references[rel] = dict(sha256=expected, source_only_inspected=True)
    scalar = ast.parse((project / reference_paths[-1]).read_bytes())
    assert not any(
        isinstance(n, (ast.Import, ast.ImportFrom))
        for n in ast.walk(function(scalar, "decimal_flux"))
    )
    assert any(
        isinstance(n, ast.ImportFrom) and n.module == "cells.coupling.selective"
        for n in ast.walk(scalar)
    )
    return dict(
        kind="cells.partition_initial_physiology_source_review_bound_static_audit@1",
        status="source_prepared_upstream_review_bound_physiology_unqualified",
        core_sha256=sha(project / CORE),
        source_pins=origins,
        finite_admission_source_manifest=dict(
            source=SOURCES,
            sha256=SOURCES_SHA256,
            immutable_frozen_closure_count=len(closure_rows),
            sources=closure_rows,
        ),
        explicit_ECM02_manifest_sha256=ECM_SHA256,
        upstream_accepted_review=dict(
            path=str(UPSTREAM_REVIEW),
            sha256=UPSTREAM_REVIEW_SHA256,
            verdict=UPSTREAM_VERDICT,
            blockers=[],
            manifest_sha256=ECM_SHA256,
        ),
        DRAFT_ONLY=False,
        source_only_freeze_permitted=True,
        numerical_launch_authorized=False,
        complete_named_array_inventory=inventory,
        source_sites={
            name: site(CORE, function(tree, name))
            for name in (
                "_source_review",
                "_accepted_geometry",
                "_declaration",
                "_materialize",
                "_initial_accounting",
                "_initial_snapshot",
                "prepare",
                "require_advancement",
            )
        },
        initial_path=dict(
            snapshot_field_solve_reused_for_complete_RHS=True,
            existing_parser_performs_initial_field_validation=True,
            typed_spec_reparse_repeats_initial_validation=True,
            total_field_solver_calls_claimed_single=False,
            time_advanced=False,
            scientific_accounting_executed=False,
        ),
        independent_physical_lane=dict(
            references=references,
            implementation_prepared=True,
            implementation_source_only_unrun=True,
            executed=False,
            full_node_scalar_laws_required=True,
            production_model_calls_permitted=False,
            geometry_worker_must_remain_separate_stdlib_only=True,
            existing_scalar_helper_module_contains_unused_nested_Cells_import=True,
            pinned_decimal_flux_function_AST_extraction_completed=True,
            future_helper_requires_pinned_decimal_flux_function_AST_extraction=False,
            integration_permitted=False,
            source_implementation=independent_source(project, inventory),
        ),
        activity=dict(
            production_imports=0,
            scientific_imports=0,
            model_or_reference_evaluations=0,
            tests=0,
            collection=0,
            fixtures=0,
            numerical_jobs=0,
            polls=0,
            shared_status_edited=False,
            frozen_evidence_edited=False,
        ),
        qualification=dict(
            literal_case_declarations=4,
            new_physical_cases_materialized=0,
            independent_cases_evaluated=0,
            input_control_declarations=16,
            output_control_declarations=26,
            checks_executed=0,
            native_equivalence=False,
        ),
    )
