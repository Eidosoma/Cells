"""Source/AST-only origin, geometry-lane extraction and constructor audit."""

import ast
import copy
import hashlib
import json
import sys
from pathlib import Path

CORE = "src/cells/processes/stable_seed_explicit_ecm_partition.py"
REFERENCE = "validation/geometry/stable_seed_explicit_ecm_partition_reference.py"
LANE = "validation/geometry/stable_seed_explicit_ecm_partition_geometry_reference.py"
FIXTURE = "validation/geometry/stable_seed_explicit_ecm_partition_fixtures.py"
CALLERS = "validation/geometry/stable_seed_explicit_ecm_partition_callers.json"
TEST = "tests/unit/test_stable_seed_explicit_ecm_partition.py"
FINITE = Path("/mnt/workspaces/Cells/finite-ecm-polygon-prepared-20261031-01")
FINITE_SHA256 = "232f5762460fd03d8990a65648e7f264dccb4b8f6ee5e2514f431d127041bc9f"
POLYGON = Path("/mnt/workspaces/Cells/conservative-polygon-geometry-prepared-20261030-02")
POLYGON_SHA256 = "2a1182f4091761f20c8048e0bd8cf8281ff67b808410be2820dddb4531f1d95b"
ORIGINAL_REFERENCE_SHA256 = "79aaf9acb8a9cfbc557b33fbc386fbf835fb6eef12f2395e97acb08d072fde71"
NATIVE_PINS = {
    "betse/science/cells.py": "be38678a4f0bd084044fe7d952d74a4550003ce9701f5d073d1f124ba6daeaf2",
    "betse/science/math/mesh.py": (
        "fd0dc21e1f82aa71e19a487f3b91c4b5258f02aec4c69f22c2bf3c419e425c38"
    ),
}
DENIED = {"cells", "betse", "numpy", "scipy", "jax", "jaxlib", "PIL", "torch"}
PREDECESSOR = Path("/mnt/workspaces/Cells/stable-seed-explicit-ecm-partition-prepared-20261031-01")
PREDECESSOR_SHA256 = "9247bd691887657a40137c11ce5bc53d81f022bcbb2d080a34c0f1babc5b71fb"
REVIEW = Path(
    "/mnt/workspaces/Cells/stable-seed-explicit-ecm-partition-preflight-20261031-01/REVIEW.json"
)
REVIEW_SHA256 = "e4ce212b2be31eae84076b9fd9b3880ffd1927c5b1ea14251f399bdb72f81ab3"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def literal(tree, name):
    return ast.literal_eval(
        next(
            node.value
            for node in tree.body
            if isinstance(node, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == name for t in node.targets)
        )
    )


def function(tree, name, cls=None):
    body = (
        next(node.body for node in tree.body if isinstance(node, ast.ClassDef) and node.name == cls)
        if cls
        else tree.body
    )
    return next(node for node in body if isinstance(node, ast.FunctionDef) and node.name == name)


def calls(node):
    return {ast.unparse(child.func) for child in ast.walk(node) if isinstance(child, ast.Call)}


def site(source, node):
    return dict(
        source=source,
        first_line=node.lineno,
        last_line=node.end_lineno,
        ast_sha256=hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest(),
    )


def dict_fields(node, name=None):
    value = (
        next(
            child.value
            for child in ast.walk(node)
            if isinstance(child, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == name for t in child.targets)
        )
        if name
        else next(child.value for child in node.body if isinstance(child, ast.Return))
    )
    assert isinstance(value, ast.Call) and ast.unparse(value.func) == "dict"
    return {item.arg for item in value.keywords}


def inventory(project):
    project = Path(project)
    fixtures, tests = (ast.parse((project / path).read_bytes()) for path in (FIXTURE, TEST))
    cases = literal(fixtures, "CASES")
    entry = "test_positive_explicit_cell_bath_construction_and_full_independent_geometry"
    functions = [
        node
        for node in tests.body
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
    ]
    checks = [TEST + "::" + entry + "[" + case + "]" for case in cases] + [
        TEST + "::" + node.name for node in functions if node.name != entry
    ]
    assert len(cases) == 5 and len(checks) == len(set(checks)) == 9
    assert all({"build", "independent"} <= calls(node) for node in functions)
    panels = {name: list(literal(tests, name)) for name in ("REFUSALS", "CORRUPTIONS")}
    assert [len(value) for value in panels.values()] == [23, 23]
    caller = json.loads((project / CALLERS).read_text())
    assert [row["id"] for row in caller["cases"]] == list(cases)
    assert caller["qualification"] == dict(
        executed=False,
        new_biological_cases=0,
        native_equivalence=False,
        physical_model_prepared=False,
    )
    return dict(
        check_ids=checks,
        manufactured_cases=list(cases),
        assertion_panels=panels,
        top_level_pytest_trees=9,
        potential_actual_nested_reference_children=9,
        Root_finalizer=1,
        scheduled_units=10,
        total_process_units=19,
        duplicate_child_replays=0,
        completed_checks=0,
        biological_cases=0,
        collection=False,
        all_checks_unrun=True,
    )


def reference_closure(project):
    project = Path(project)
    pending, seen, rows = [REFERENCE], set(), []
    while pending:
        rel = pending.pop()
        if rel in seen:
            continue
        seen.add(rel)
        imports, local = [], []
        for node in ast.walk(ast.parse((project / rel).read_bytes())):
            if isinstance(node, ast.Import):
                names = [item.name for item in node.names]
            elif isinstance(node, ast.ImportFrom):
                assert node.level == 0
                names = [node.module + "." + item.name for item in node.names]
            else:
                continue
            for name in names:
                parts = name.split(".")
                assert parts[0] not in DENIED, (rel, name)
                imports.append(name)
                match = None
                for end in range(len(parts), 0, -1):
                    candidate = "/".join(parts[:end]) + ".py"
                    if (project / candidate).is_file():
                        match = candidate
                        break
                if match:
                    pending.append(match)
                    local.append(match)
                else:
                    assert parts[0] in sys.stdlib_module_names, (rel, name)
        rows.append(
            dict(
                source=rel,
                sha256=sha(project / rel),
                imports=sorted(imports),
                local_dependencies=sorted(set(local)),
            )
        )
    assert seen == {
        REFERENCE,
        LANE,
        "validation/geometry/conservative_polygon_geometry_reference.py",
        "validation/geometry/stable_geometry_primitives_reference.py",
    }
    return dict(
        modules=rows,
        production_and_scientific_imports=[],
        executed=False,
        field_or_physical_lanes_imported=False,
    )


def successor_scope(project):
    """Compare source ASTs only; never import or execute the reference or tests."""
    project = Path(project)
    assert sha(PREDECESSOR / "manifest.json") == PREDECESSOR_SHA256
    old_files = json.loads((PREDECESSOR / "manifest.json").read_text())["file_sha256"]
    assert len(old_files) == 38
    for rel, expected in old_files.items():
        assert sha(PREDECESSOR / rel) == expected, rel
    assert sha(REVIEW) == REVIEW_SHA256
    review = json.loads(REVIEW.read_text())
    assert review["status"] == "held_for_narrow_evidence_contract_successor"
    assert {row["id"] for row in review["findings"]} == {
        "named_refusal_specificity",
        "completed_reference_retention",
    }
    unchanged = [CORE, LANE, FIXTURE, CALLERS]
    for rel in unchanged:
        assert sha(project / rel) == old_files["source/" + rel], rel
    old_reference = ast.parse((PREDECESSOR / "source" / REFERENCE).read_bytes())
    new_reference = ast.parse((project / REFERENCE).read_bytes())
    original = function(old_reference, "derive")
    updated = function(new_reference, "derive")
    allowed = {
        "grid_line_events",
        "stage",
        "x_axis",
        "y_axis",
        "primary",
        "refined",
        "owner_maps",
        "construction",
        "provenance",
    }
    retained, inserted, index = [], [], 0
    for statement in updated.body:
        dumped = ast.dump(statement, include_attributes=False)
        if index < len(original.body) and dumped == ast.dump(
            original.body[index], include_attributes=False
        ):
            retained.append(statement)
            index += 1
        else:
            assert isinstance(statement, ast.Assign) and len(statement.targets) == 1
            target = statement.targets[0]
            assert isinstance(target, ast.Subscript) and ast.unparse(target.value) == "partial"
            assert ast.literal_eval(target.slice) in allowed
            inserted.append(ast.unparse(statement))
    assert index == len(original.body) and len(inserted) == 14
    normalized = copy.deepcopy(new_reference)
    function(normalized, "derive").body = retained
    assert ast.dump(normalized, include_attributes=False) == ast.dump(
        old_reference, include_attributes=False
    )
    for name in ("primary", "refined"):
        assignment = next(
            i
            for i, n in enumerate(updated.body)
            if isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) == name
        )
        saved = updated.body[assignment + 1]
        assert ast.unparse(saved.targets[0]) == "partial[" + repr(name) + "]"
        assert ast.unparse(saved.value) == name
    old_tests = ast.parse((PREDECESSOR / "source" / TEST).read_bytes())
    new_tests = ast.parse((project / TEST).read_bytes())
    helpers = {
        "refusal_contract",
        "refusal_metadata_controls",
        "reference_retention_metadata_controls",
    }
    changed = {
        "test_complete_caller_width_domain_owner_and_cache_refusals",
        "test_failed_constructor_baseline_cannot_credit_output_controls",
    }
    normalized = copy.deepcopy(new_tests)
    normalized.body = [
        node
        for node in normalized.body
        if not (
            isinstance(node, ast.FunctionDef)
            and node.name in helpers
            or isinstance(node, ast.Assign)
            and any(
                isinstance(t, ast.Name) and t.id == "REFUSAL_EXPECTATIONS" for t in node.targets
            )
            or isinstance(node, ast.Import)
            and [n.name for n in node.names] == ["ast"]
            or isinstance(node, ast.ImportFrom)
            and node.module in {"pathlib", "types"}
        )
    ]
    for name in changed:
        old, new = function(old_tests, name), function(new_tests, name)
        if "refusals" in name:

            def mutations(node):
                loop = next(
                    n
                    for n in ast.walk(node)
                    if isinstance(n, ast.For) and ast.unparse(n.iter) == "REFUSALS"
                )
                return next(n for n in loop.body if isinstance(n, ast.If))

            assert ast.dump(mutations(old), include_attributes=False) == ast.dump(
                mutations(new), include_attributes=False
            )
        else:
            stripped = copy.deepcopy(new)
            stripped.body[0].body = [
                n
                for n in stripped.body[0].body
                if not (
                    isinstance(n, ast.Expr)
                    and isinstance(n.value, ast.Call)
                    and ast.unparse(n.value.func) == "reference_retention_metadata_controls"
                )
            ]
            assert ast.dump(stripped, include_attributes=False) == ast.dump(
                old, include_attributes=False
            )
        position = next(
            i
            for i, n in enumerate(normalized.body)
            if isinstance(n, ast.FunctionDef) and n.name == name
        )
        normalized.body[position] = old
    assert ast.dump(normalized, include_attributes=False) == ast.dump(
        old_tests, include_attributes=False
    )
    expectations = literal(new_tests, "REFUSAL_EXPECTATIONS")
    assert tuple(expectations) == literal(old_tests, "REFUSALS")
    assert sum(row["phase"] == "bind" for row in expectations.values()) == 19
    assert sum(row["phase"] == "prepare" for row in expectations.values()) == 4
    for row in expectations.values():
        assert set(row) == {
            "phase",
            "exception_type",
            "stage",
            "reason",
            "source_error",
            "cause_chain",
        }
        assert row["exception_type"] == (
            "ValueError" if row["phase"] == "bind" else "ConstructionRejected"
        )
        if row["phase"] == "bind":
            assert row["stage"] is None and row["source_error"] is None and row["cause_chain"] == []
        else:
            assert row["reason"] == (
                "Explicit cell/bath construction refused at "
                + row["stage"]
                + ": "
                + row["source_error"]["reason"]
            )
            assert row["cause_chain"][0]["exception_type"] == row["source_error"]["type"]
    return dict(
        predecessor=dict(
            bundle=str(PREDECESSOR), manifest_sha256=PREDECESSOR_SHA256, verified_original_files=38
        ),
        review=dict(path=str(REVIEW), sha256=REVIEW_SHA256, status=review["status"]),
        unchanged_source_sha256={rel: sha(project / rel) for rel in unchanged},
        reference_inverse_AST_equal_after_removing_partial_assignments=True,
        reference_inserted_partial_assignments=inserted,
        tests_unchanged_outside_named_contracts_and_metadata_helpers=True,
        original_input_mutations_unchanged=True,
        refusal_expectations=expectations,
        metadata_controls=dict(
            wrong_contract_fields=6,
            simulated_reference_failures=2,
            future_only_unrun=True,
            additional_children=0,
            physical_cases=0,
        ),
        test_helper_source={
            name: site(TEST, function(new_tests, name)) for name in sorted(helpers)
        },
        science_or_test_execution=False,
    )


def audit(project, native):
    project, native = Path(project), Path(native)
    assert (
        sha(FINITE / "manifest.json") == FINITE_SHA256
        and sha(POLYGON / "manifest.json") == POLYGON_SHA256
    )
    core, reference = (ast.parse((project / path).read_bytes()) for path in (CORE, REFERENCE))
    assert literal(core, "LAW_ID") == literal(reference, "LAW") and literal(
        core, "INPUT_KIND"
    ) == literal(reference, "INPUT_KIND")
    assert literal(core, "SOURCE_PINS") == literal(reference, "SOURCE_PINS")
    assert list(literal(core, "INVALIDATED")) == literal(reference, "INVALIDATED")
    assert sha(project / LANE) == literal(reference, "GEOMETRY_REFERENCE_SHA256")
    dependency_origins = {}
    for filename, pin in literal(core, "SOURCE_PINS").items():
        parent = FINITE if filename == "finite_ecm_polygon_geometry.py" else POLYGON
        rel = "src/cells/processes/" + filename
        manifest = json.loads((parent / "manifest.json").read_text())["file_sha256"]
        assert sha(project / rel) == pin == manifest["source/" + rel]
        dependency_origins[rel] = dict(bundle=str(parent), sha256=pin)
    original_path = FINITE / "source/validation/geometry/finite_ecm_polygon_reference.py"
    assert sha(original_path) == ORIGINAL_REFERENCE_SHA256
    original = ast.parse(original_path.read_bytes())
    lane = ast.parse((project / LANE).read_bytes())
    cutoff = function(original, "semantic").lineno
    a = {
        n.name: ast.dump(n, include_attributes=False)
        for n in original.body
        if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.lineno < cutoff
    }
    b = {
        n.name: ast.dump(n, include_attributes=False)
        for n in lane.body
        if isinstance(n, (ast.FunctionDef, ast.ClassDef))
    }
    assert a == b
    for rel, pin in NATIVE_PINS.items():
        assert sha(native / rel) == pin
    native_cells = ast.parse((native / "betse/science/cells.py").read_bytes())
    cellverts = function(native_cells, "cellVerts", "Cells")
    ecm = function(native_cells, "makeECM", "Cells")
    assert "p.scale_cell * pt_zero + centre" in ast.unparse(cellverts)
    assert "self.gj_len = p.cell_space" in ast.unparse(cellverts)
    assert {"points_tree_ecm.query", "points_tree_mems.query_ball_point"} <= calls(ecm)
    axis = function(core, "_axis")
    independent = function(reference, "cumulative_axis")
    assert "center - half" in ast.unparse(axis) and "geometry.add" in calls(independent)
    assert "_axis" not in calls(reference) and "Fraction" not in calls(reference)
    assert {
        "finite.from_partition",
        "finite.prepare",
        "_measure_targets",
        "_conservation",
    } <= calls(function(core, "prepare"))
    assert {"geometry.evaluate", "cumulative_axis", "partition", "conservation"} <= calls(
        function(reference, "derive")
    )
    assert isinstance(function(core, "require_physical_admission").body[0], ast.Raise)
    assert isinstance(function(core, "require_cached_operators").body[0], ast.Raise)
    grid = function(core, "grid", "_Work")
    append = next(
        n.lineno
        for n in ast.walk(grid)
        if isinstance(n, ast.Call) and ast.unparse(n.func) == "self.events.append"
    )
    rounding = next(
        n.lineno
        for n in ast.walk(grid)
        if isinstance(n, ast.Call) and ast.unparse(n.func) == "finite.exact.arithmetic._round"
    )
    assert append < rounding
    for field in ("construction", "provenance"):
        assert dict_fields(function(core, "prepare"), field) == dict_fields(
            function(reference, "derive"), field
        ), field
    assert dict_fields(function(core, "prepare"), "maps") == dict_fields(
        function(reference, "derive"), "maps"
    )
    assert dict_fields(function(core, "_conservation")) == dict_fields(
        function(reference, "conservation")
    )
    cls = next(n for n in core.body if isinstance(n, ast.ClassDef) and n.name == "Candidate")
    fields = {n.target.id for n in cls.body if isinstance(n, ast.AnnAssign)}
    required = next(
        n.args[1]
        for n in ast.walk(function(reference, "verify"))
        if isinstance(n, ast.Call)
        and ast.unparse(n.func) == "keys"
        and ast.unparse(n.args[0]) == "candidate"
    )
    assert fields == ast.literal_eval(required)
    return dict(
        kind="cells.explicit_cleft_width_cell_bath_constructor_static_correspondence@1",
        source_only=True,
        dependencies=dependency_origins,
        finite_ECM_manifest_sha256=FINITE_SHA256,
        conservative_polygon_manifest_sha256=POLYGON_SHA256,
        native_source_sha256=NATIVE_PINS,
        native_source_sites=dict(
            cellVerts=site("betse/science/cells.py", cellverts),
            makeECM=site("betse/science/cells.py", ecm),
        ),
        native_correspondence=(
            "Native homothetic cell scale and separate cell_space gap length plus "
            "nearest midpoint maps are inspected, not reproduced or adopted"
        ),
        new_law=(
            "Fresh manufactured tensor seeds, explicit half-widths/all clefts/domain/"
            "positive bath slots; exact representable shared coordinates"
        ),
        production_width_construction=site(CORE, axis),
        independent_width_construction=site(REFERENCE, independent),
        production_finite_geometry_admission=site(CORE, function(core, "prepare")),
        independent_full_geometry_and_certificate_inventory=site(
            REFERENCE, function(reference, "compare_geometry")
        ),
        exact_conservation=site(CORE, function(core, "_conservation")),
        independent_conservation=site(REFERENCE, function(reference, "conservation")),
        extraction=dict(
            original_reference_sha256=ORIGINAL_REFERENCE_SHA256,
            original_geometry_lane_end_exclusive=cutoff,
            unchanged_geometry_AST_members=sorted(a),
            new_geometry_only_reference_sha256=sha(project / LANE),
            field_conversion_and_solver_lanes_excluded=True,
        ),
        complete_constructor_and_conservation_dictionary_inventories_match=True,
        pending_grid_input_saved_before_rounding=True,
        evidence_contract_successor=successor_scope(project),
        inventory=inventory(project),
        reference_closure=reference_closure(project),
        activity=dict(
            production_imports=0,
            scientific_imports=0,
            geometry_evaluations=0,
            reference_evaluations=0,
            fixture_executions=0,
            tests=0,
            collection=0,
            numerical_jobs=0,
            GPU_jobs=0,
            polls=0,
            shared_status_edited=False,
            existing_core_or_frozen_files_edited=False,
        ),
    )
