"""Read-only imported-module/resource inventory for four explicit frozen successors."""

import argparse
import ast
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path("/home/robert/Cells")
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
BASE = Path("/mnt/workspaces/Cells")
PACKETS = {
    "catalog05": (
        "betse-normal-ecm-catalog-join-prepared-20261031-04",
        "betse_normal_ecm_catalog_join",
    ),
    "event04": ("betse-normal-ecm-event-join-prepared-20261031-03", "betse_normal_ecm_event_join"),
    "event_mechanics03": (
        "betse-normal-ecm-event-mechanics-prepared-20261031-02",
        "betse_normal_ecm_event_mechanics",
    ),
    "lifecycle02": (
        "betse-normal-ecm-run-lifecycle-prepared-20261031-01",
        "betse_normal_ecm_run_lifecycle",
    ),
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def module_path(root, name):
    for prefix in ("", "src/"):
        for suffix in (".py", "/__init__.py"):
            candidate = prefix + name.replace(".", "/") + suffix
            if (root / candidate).is_file():
                return candidate
    return None


def closure(root, starts, *, reference=False):
    pending, closed = list(starts), {}
    while pending:
        relative = pending.pop()
        if relative in closed:
            continue
        path = root / relative
        tree = ast.parse(path.read_text())
        compile(tree, relative, "exec")
        closed[relative] = sha(path)
        parent = Path(relative).parent
        while str(parent) not in (".", "src"):
            candidate = str(parent / "__init__.py")
            if (root / candidate).is_file():
                pending.append(candidate)
            parent = parent.parent
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [n.name for n in node.names]
            elif isinstance(node, ast.ImportFrom):
                assert not node.level, (relative, "relative import needs review")
                names = [node.module] + [node.module + "." + n.name for n in node.names]
            else:
                continue
            for name in names:
                head = name.split(".")[0]
                if reference:
                    assert head in sys.stdlib_module_names | {"validation"}, (relative, name)
                if head in {"cells", "tests", "validation"}:
                    resolved = module_path(root, name)
                    if resolved:
                        pending.append(resolved)
    return closed


def audit(root, prefix):
    utility = ROOT / "validation/frozen_resource_dependencies.py"
    spec = importlib.util.spec_from_file_location("frozen_resource_source_audit_only", utility)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    runtime = closure(root, ["tests/unit/test_" + prefix + ".py"])
    references = closure(root, ["validation/betse/" + prefix + "_reference.py"], reference=True)
    sources = runtime | references
    found = module.audit_literal_sibling_reads(root, sources)
    for row in found["unresolved_reads"]:
        tree = ast.parse((root / row["module"]).read_text())
        containers = [
            n
            for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            and n.lineno <= row["line"] <= n.end_lineno
        ]
        row["containing_function"] = (
            min(containers, key=lambda n: n.end_lineno - n.lineno).name
            if containers
            else "<module>"
        )
    return dict(
        kind="cells.reviewed_ECM_successor_resource_inventory@1",
        root=str(root),
        prefix=prefix,
        utility=dict(path=str(utility), sha256=sha(utility)),
        scientific_import_closure=runtime,
        reference_closure=references,
        literal_resource_audit=found,
        manual_unresolved_review_pending=True,
        scientific_imports=0,
        scientific_AST_executions=0,
        numerical_runs=0,
    )


def manual_review(result):
    """Resolve constant aliases and classify every remaining read by reviewed callers.

    Dynamic native paths remain constrained by the literal protocol/inventory
    source pin tables. Generated inputs/results and runtime identities are
    explicitly distinct from resources that must exist in the frozen tree.
    """
    root = Path(result["root"])
    trees, globals_ = {}, {}

    def parsed(relative):
        if relative not in trees:
            trees[relative] = ast.parse((root / relative).read_text())
        return trees[relative]

    def definitions(relative):
        if relative not in globals_:
            values = {}
            for node in parsed(relative).body:
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            values[target.id] = node.value
                elif isinstance(node, ast.ImportFrom) and node.module:
                    for item in node.names:
                        path = module_path(root, node.module + "." + item.name)
                        values[item.asname or item.name] = (
                            ("module", path)
                            if path
                            else ("member", module_path(root, node.module), item.name)
                        )
            globals_[relative] = values
        return globals_[relative]

    def resolve(node, relative, stack=()):
        key = (relative, ast.unparse(node))
        if key in stack:
            return None
        stack = (*stack, key)
        if isinstance(node, ast.Constant) and type(node.value) in (str, int):
            return node.value
        if isinstance(node, ast.Name):
            if node.id == "__file__":
                return root / relative
            value = definitions(relative).get(node.id)
            if isinstance(value, tuple):
                if value[0] == "member" and value[1]:
                    return resolve(ast.Name(id=value[2]), value[1], stack)
                return value
            return resolve(value, relative, stack) if isinstance(value, ast.AST) else None
        if isinstance(node, ast.Attribute):
            value = resolve(node.value, relative, stack)
            if isinstance(value, Path) and node.attr in ("parent", "parents"):
                return value.parent if node.attr == "parent" else list(value.parents)
            if isinstance(value, tuple) and value[0] == "module" and value[1]:
                return resolve(ast.Name(id=node.attr), value[1], stack)
        if isinstance(node, ast.Subscript):
            value, index = (
                resolve(node.value, relative, stack),
                resolve(node.slice, relative, stack),
            )
            if isinstance(value, list) and type(index) is int and 0 <= index < len(value):
                return value[index]
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            value, part = resolve(node.left, relative, stack), resolve(node.right, relative, stack)
            if isinstance(value, Path) and isinstance(part, str):
                return value / part
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id == "Path" and len(node.args) == 1:
                value = resolve(node.args[0], relative, stack)
                return Path(value) if isinstance(value, (str, Path)) else None
            if isinstance(node.func, ast.Attribute):
                value = resolve(node.func.value, relative, stack)
                if isinstance(value, Path):
                    if node.func.attr in ("resolve", "absolute") and not node.args:
                        return value.absolute()
                    if node.func.attr == "with_name" and len(node.args) == 1:
                        name = resolve(node.args[0], relative, stack)
                        return value.with_name(name) if isinstance(name, str) else None
        return None

    resources = {
        row["resource"]: row["sha256"]
        for row in result["literal_resource_audit"]["required_resources"]
        if row["present"]
    }
    reviewed, pending = [], []
    for source in result["literal_resource_audit"]["unresolved_reads"]:
        row = dict(source)
        expression, module, function = row["expression"], row["module"], row["containing_function"]
        call = ast.parse(expression, mode="eval").body
        receiver = call.func.value if isinstance(call.func, ast.Attribute) else None
        path = resolve(receiver, module) if receiver is not None else None
        if isinstance(path, Path) and path.is_relative_to(root):
            relative = str(path.relative_to(root))
            assert path.is_file(), relative
            resources[relative] = sha(path)
            row.update(
                classification="frozen_constant_path_or_imported_alias",
                resource=relative,
                sha256=sha(path),
            )
        elif (
            module.endswith("test_betse_normal_channel_join.py")
            and expression == "(SOURCE_ROOT / path).read_text()"
        ):
            declared = [
                "validation/channels/sodium_catalog_protocol.json",
                "validation/channels/potassium_catalog_protocol.json",
                "validation/channels/leak_channels_protocol.json",
                "validation/tissue/surface_channel_protocol.json",
            ]
            assigned = next(
                n
                for n in parsed(module).body
                if isinstance(n, ast.Assign)
                and isinstance(n.targets[0], ast.Name)
                and n.targets[0].id == "CHANNEL_PROTOCOLS"
            )
            assert {
                n.value
                for n in ast.walk(assigned)
                if isinstance(n, ast.Constant)
                and isinstance(n.value, str)
                and n.value.endswith(".json")
            } == set(declared)
            for name in declared:
                assert (root / name).is_file(), name
                resources[name] = sha(root / name)
            row.update(classification="frozen_literal_channel_protocol_table", resources=declared)
        elif expression == "args.inputs.read_text()" and function == "main":
            row.update(
                classification="future_explicit_CLI_input",
                rationale=(
                    "The selected test writes inputs.json then supplies its path to this "
                    "subprocess; no hidden packaged data read"
                ),
            )
        elif (
            module.startswith("tests/")
            and function in ("references", "independent")
            and expression == "path.read_text()"
        ):
            row.update(
                classification="future_fresh_reference_output",
                rationale=(
                    "Read the JSON path just supplied to a checked fresh reference subprocess"
                ),
            )
        elif function in ("archive_read", "read_raw_capture_inputs") and expression in (
            "(path / 'data.json').read_text()",
            "(path / 'manifest.json').read_text()",
            "(path / name).read_bytes()",
        ):
            row.update(
                classification="future_hash_bound_typed_evidence",
                rationale=(
                    "Read the requested generated evidence directory, verify exact manifest "
                    "payload hashes, preserve typed buffers"
                ),
            )
        elif function == "write_archive" and expression == "(path / name).read_bytes()":
            row.update(
                classification="hash_newly_written_archive_payload",
                rationale="Hash only the payload pair written by this writer",
            )
        elif function == "write_archive" and expression == "os.open(directory, os.O_RDONLY)":
            row.update(
                classification="output_directory_fsync_descriptor",
                rationale="Directory descriptor used by fsync, no data resource opened",
            )
        elif module.endswith("betse_normal_channel_join_runtime.py") and function == "inventory":
            assert expression in ("path.read_bytes()", "executable.read_bytes()")
            row.update(
                classification="future_loaded_module_and_interpreter_identity",
                rationale=(
                    "Actual loaded module __file__ paths and sys.executable are hashed by "
                    "runtime inventory; not static packaged data"
                ),
            )
        elif (
            module.endswith("betse_normal_calcium_join_native.py")
            and function == "helper_probe"
            and expression == "path.read_text()"
        ):
            row.update(
                classification="future_native_helper_probe_output",
                rationale="Read fresh subprocess probe JSON at its explicit output path",
            )
        elif (
            module.startswith("validation/betse/")
            and function
            in (
                "authenticated",
                "authenticated_gate",
                "capture",
                "science",
                "setup",
                "literal_nodes",
                "original_nodes",
                "extra_nodes",
                "field_nodes",
                "calcium_nodes",
                "pump_material_source",
                "parsed",
                "main",
            )
            and call.func.attr in ("read_text", "read_bytes")
        ):
            row.update(
                classification="pinned_native_source_consumer",
                rationale=(
                    "Reviewed caller passes checkout/installed BETSE paths from authenticated "
                    "protocol/inventory source tables; these tables and their complete union "
                    "are verified separately"
                ),
            )
        else:
            row.update(classification="manual_resolution_pending")
            pending.append(row)
        reviewed.append(row)
    native = {}

    def collect(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key in ("source_sha256", "native_source_sha256") and isinstance(child, dict):
                    for name, pin in child.items():
                        if name.startswith("betse/") and isinstance(pin, str) and len(pin) == 64:
                            assert name not in native or native[name] == pin, name
                            native[name] = pin
                collect(child)
        elif isinstance(value, list):
            for child in value:
                collect(child)

    for name in resources:
        if name.endswith(".json"):
            collect(json.loads((root / name).read_text()))
    for name, pin in native.items():
        assert (
            sha(BASE / "betse-v1.5.0" / name)
            == sha(BASE / "venv-betse/lib/python3.13/site-packages" / name)
            == pin
        ), name
    return dict(
        kind="cells.manual_frozen_resource_review@1",
        resource_sha256=resources,
        all_resources_present=True,
        native_source_union_sha256=native,
        native_checkout_and_installed_pins_verified=True,
        reviewed_unresolved_reads=reviewed,
        pending_manual_reads=pending,
        complete_general_dependency_resolver_claim=False,
        scientific_imports=0,
        scientific_AST_executions=0,
        numerical_runs=0,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = {
        key: audit(BASE / parent / "source", prefix) for key, (parent, prefix) in PACKETS.items()
    }
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(
        json.dumps(
            {
                k: dict(
                    runtime=len(v["scientific_import_closure"]),
                    references=len(v["reference_closure"]),
                    literal_reads=len(v["literal_resource_audit"]["required_resources"]),
                    missing=v["literal_resource_audit"]["missing_resources"],
                    unresolved=len(v["literal_resource_audit"]["unresolved_reads"]),
                )
                for k, v in result.items()
            }
        )
    )


if __name__ == "__main__":
    main()
