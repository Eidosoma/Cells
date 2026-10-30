"""Final stdlib source audits; no collection or scientific body execution."""

import ast
import builtins
import hashlib
import importlib.util
import json
import subprocess
import symtable
from pathlib import Path

ROOT = Path("/home/robert/Cells")
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
PREFIX = "betse_normal_transporter_join"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def reference_closure(start):
    pending, closed = [start], {}
    while pending:
        relative = pending.pop()
        if relative in closed:
            continue
        path = ROOT / relative
        tree = ast.parse(path.read_text())
        closed[relative] = sha(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [value.name for value in node.names]
            elif isinstance(node, ast.ImportFrom):
                assert not node.level
                names = [node.module] + [node.module + "." + value.name for value in node.names]
            else:
                continue
            for name in names:
                assert name.split(".")[0] not in {"cells", "betse", "numpy", "jax", "jaxlib"}
                candidate = name.replace(".", "/") + ".py"
                if name.startswith("validation.") and (ROOT / candidate).is_file():
                    pending.append(candidate)
    return closed


def audit():
    queue_path = WORK / (PREFIX + "_workqueue.json")
    queue = json.loads(queue_path.read_text())
    paths = [name for name in queue["owned"] + queue["workfiles"] if name.endswith(".py")]
    missing = {}
    for relative in paths:
        source = (ROOT / relative).read_text()
        compile(source, relative, "exec")
        table = symtable.symtable(source, relative, "exec")
        known = set(table.get_identifiers()) | set(dir(builtins)) | {"__name__", "__file__"}

        def unresolved(t, known=known):
            result = {
                symbol.get_name()
                for symbol in t.get_symbols()
                if symbol.is_global() and symbol.is_referenced() and symbol.get_name() not in known
            }
            for child in t.get_children():
                result |= unresolved(child)
            return result

        if names := unresolved(table):
            missing[relative] = sorted(names)
    assert not missing, missing
    spec = importlib.util.spec_from_file_location(
        "transporter_AST_audit", WORK / (PREFIX + "_ast_audit.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    proof = module.audit()
    adapter_spec = importlib.util.spec_from_file_location(
        "molecule_adapter_attribute_audit",
        WORK / "betse_normal_molecule_adapter_attribute_audit.py",
    )
    adapter_module = importlib.util.module_from_spec(adapter_spec)
    adapter_spec.loader.exec_module(adapter_module)
    adapter_proof = adapter_module.audit()
    assert adapter_proof["missing"] == {"production": {}, "native": {}}
    assert adapter_proof == json.loads(
        (WORK / "betse_normal_molecule_adapter_attributes_after_02.json").read_text()
    )
    # The new native bridge retains the exact common parameter hydration loop;
    # the explicit source True parameter reaches the actual Molecule object.
    hydration = []
    for prefix in ("molecule", "transporter"):
        t = ast.parse(
            (
                ROOT / ("validation/betse/betse_normal_" + prefix + "_join_native_network.py")
            ).read_text()
        )
        loop = next(
            node
            for node in ast.walk(t)
            if isinstance(node, ast.For)
            and ast.dump(node.iter)
            == ast.dump(ast.parse("row['parameters'].items()", mode="eval").body)
        )
        hydration.append(ast.dump(loop, include_attributes=False))
    assert hydration[0] == hydration[1]
    orders = {}
    for label, relative, function in (
        ("production", "src/cells/processes/betse_normal_transporter_join.py", "material_step"),
        ("native", "validation/betse/betse_normal_transporter_join_native_helpers.py", "setup"),
    ):
        t = ast.parse((ROOT / relative).read_text())
        f = next(
            node for node in t.body if isinstance(node, ast.FunctionDef) and node.name == function
        )
        calls = []
        for node in ast.walk(f):
            if not isinstance(node, ast.Call):
                continue
            name = ast.unparse(node.func).rsplit(".", 1)[-1]
            if (
                isinstance(node.func, ast.Subscript)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "ns"
            ):
                name = ast.literal_eval(node.func.slice)
            if name in {
                "run_loop_transporters",
                "_run_cache",
                "run_loop_channels",
                "run_loop_modulators",
                "run_loop",
            }:
                calls.append((node.lineno, name))
        orders[label] = [name for _, name in sorted(calls)]
    assert orders["production"] == [
        "run_loop_transporters",
        "_run_cache",
        "run_loop_modulators",
        "run_loop",
    ]
    assert orders["native"] == [
        "run_loop_transporters",
        "run_loop_channels",
        "run_loop_modulators",
        "run_loop",
    ]
    map_path = ROOT / ("validation/betse/" + PREFIX + "_source_map.json")
    mapping = json.loads(map_path.read_text())
    assert mapping["literal_numeric_bodies"] == proof["literal_numeric_bodies"]
    assert mapping["outer_helpers"] == proof["outer_helpers"]
    assert len(proof["literal_numeric_bodies"]) == 27
    assert len(queue["protected_sha256"]) == 225
    for relative, expected in queue["protected_sha256"].items():
        assert sha(ROOT / relative) == expected, relative
    for row in queue["binding_evidence"].values():
        assert sha(row["path"]) == row["sha256"], row["path"]
    protocol = json.loads((ROOT / ("validation/betse/" + PREFIX + "_protocol.json")).read_text())
    assert mapping["source_sha256"] == protocol["native_source"]["source_sha256"]
    assert len(mapping["source_sha256"]) == 21
    for relative, expected in protocol["acceptance"]["inherited_budget_source_sha256"].items():
        assert sha(ROOT / relative) == expected, relative
    assert (
        protocol["acceptance"]["transporter_rates"]
        == json.loads(
            (ROOT / "validation/transport/betse_network_transport_protocol.json").read_text()
        )["tolerances"]
    )
    for relative, expected in protocol["native_source"]["source_sha256"].items():
        assert sha(Path(protocol["native_source"]["checkout"]) / relative) == expected, relative
        assert (
            sha(Path(protocol["native_source"]["installed_package"]).parent / relative) == expected
        ), relative
    fixture = ast.parse((ROOT / ("validation/betse/" + PREFIX + "_fixtures.py")).read_text())
    constants = {
        target.id: ast.literal_eval(node.value)
        for node in fixture.body
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
        and target.id in {"CASES", "COMPONENT_CONTROLS", "RAW_CASES", "DEPENDENCIES"}
    }
    assert tuple(
        len(constants[name])
        for name in ("CASES", "COMPONENT_CONTROLS", "RAW_CASES", "DEPENDENCIES")
    ) == (18, 3, 2, 5)
    assert (
        protocol["planned"]["checks"] == 25
        and protocol["planned"]["fresh_Decimal_reference_forms"] == 216
    )
    test = ast.parse((ROOT / "tests/unit/test_betse_normal_transporter_join.py").read_text())
    test_functions = {node.name: node for node in test.body if isinstance(node, ast.FunctionDef)}
    assert {
        "test_native_configured_transporters_and_conditional_reference",
        "test_native_transporter_partial_failure",
        "test_complete_transporter_dependencies",
    } <= test_functions.keys()
    # Literal dictionary-key checks catch envelope/tolerance drift without
    # importing the scientific modules or evaluating a fixture/reference.
    tolerances = set(protocol["acceptance"]["transporter_rates"])
    for node in ast.walk(test):
        if (
            isinstance(node, ast.Subscript)
            and isinstance(node.value, ast.Name)
            and node.value.id == "TRANSPORT_TOLERANCES"
        ):
            keys = (
                (node.slice.body, node.slice.orelse)
                if isinstance(node.slice, ast.IfExp)
                else (node.slice,)
            )
            assert all(ast.literal_eval(key) in tolerances for key in keys)
    runner = ast.parse((ROOT / queue["runner"]).read_text())
    functions = {node.name: node for node in runner.body if isinstance(node, ast.FunctionDef)}
    previous = {
        node.name: node
        for node in ast.parse((WORK / "betse_normal_network_join_checks_02.py").read_text()).body
        if isinstance(node, ast.FunctionDef)
    }
    assert ast.dump(functions["verify_pytest_ids"], include_attributes=False) == ast.dump(
        previous["verify_pytest_ids"], include_attributes=False
    )
    run = functions["run"]
    start = next(
        index
        for index, node in enumerate(run.body)
        if isinstance(node, ast.Expr) and ast.unparse(node) == "target.mkdir(exist_ok=False)"
    )
    assert (
        isinstance(run.body[start + 1], ast.Assign)
        and isinstance(run.body[start + 2], ast.Try)
        and len(run.body) == start + 3
    )
    assert ast.unparse(run.body[-1].handlers[0].type) == "BaseException"
    for args in (["check"], ["format", "--check"]):
        result = subprocess.run(
            ["/mnt/workspaces/Cells/venv-cpu/bin/ruff", *args, *paths],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        assert result.returncode == 0, (args, result.stdout, result.stderr)
    closure = reference_closure("validation/betse/" + PREFIX + "_reference.py")
    queue.update(
        owned_sha256={relative: sha(ROOT / relative) for relative in queue["owned"]},
        reference_closure=closure,
        status="static_audits_passed_ready_to_freeze_no_transporter_numerics",
        static_checks=dict(
            compile_without_import="passed",
            global_name_resolution="passed",
            unresolved=missing,
            ruff_check="passed",
            ruff_format="passed",
            literal_numeric_AST_bodies=27,
            exception_class_ASTs=3,
            unchanged_outer_helper_ASTs=5,
            original_source_and_independent_native_observational_AST="passed",
            normal_source_call_order_AST="passed",
            production_and_native_phase_order_AST=orders,
            inherited_molecule_adapter_required_attributes=42,
            inherited_molecule_adapter_missing=adapter_proof["missing"],
            new_native_parameter_hydration_loop_unchanged=True,
            scientific_AST_executions=0,
            reference_closure_stdlib_only=True,
            exact_unique_pytest_ID_validator_AST_unchanged=True,
            post_output_terminal_failure_capture_AST="passed",
            unchanged_transporter_tolerances=True,
            native_checkout_installed_pins="all21 exact",
        ),
    )
    queue_path.write_text(json.dumps(queue, indent=2, sort_keys=True, allow_nan=False) + "\n")
    print(
        json.dumps(
            dict(
                status=queue["status"],
                Python_files=len(paths),
                owned=len(queue["owned"]),
                protected=len(queue["protected_sha256"]),
                reference_closure_files=len(closure),
                literal_numeric_bodies=27,
                scientific_imports=0,
                pytest_collection_runs=0,
                numerical_runs=0,
            )
        )
    )


if __name__ == "__main__":
    audit()
