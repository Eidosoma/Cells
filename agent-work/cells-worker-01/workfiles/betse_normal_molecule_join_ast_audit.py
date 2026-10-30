"""Stdlib AST transformation/auditing only; numeric AST is never executed."""

import ast
import copy
import hashlib
from pathlib import Path
from types import SimpleNamespace

ROOT = Path("/home/robert/Cells")
UPSTREAM = Path("/mnt/workspaces/Cells/betse-v1.5.0/betse")


def functions(tree):
    return {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}


def classes(tree):
    return {node.name: node for node in tree.body if isinstance(node, ast.ClassDef)}


def digest(node):
    return hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest()


class Numeric(ast.NodeTransformer):
    def visit_Expr(self, node):
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            return None
        if isinstance(node.value, ast.Call) and ast.unparse(node.value.func) in {
            "self._observe_chem",
            "self._observe_rhs",
            "self._observe_control",
            "p._mover_observe",
        }:
            return None
        return self.generic_visit(node)

    def visit_FunctionDef(self, node):
        node.decorator_list = []
        node.returns = None
        for arg in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs):
            arg.annotation = None
        return self.generic_visit(node)


def audit():
    # Execute only the independently written stdlib AST builders. The AST
    # returned for scientific methods is inspected, never compiled/executed.
    old_tree = ast.parse(
        (ROOT / "validation/betse/betse_normal_network_join_native_network.py").read_text()
    )
    method_names = next(
        ast.literal_eval(node.value)
        for node in old_tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "METHODS" for target in node.targets)
    )
    namespace = dict(ast=ast, copy=copy, METHODS=method_names)
    exec(
        compile(
            ast.Module(body=[functions(old_tree)["literal_nodes"]], type_ignores=[]),
            "<stdlib earlier AST builder>",
            "exec",
        ),
        namespace,
    )
    new_tree = ast.parse(
        (ROOT / "validation/betse/betse_normal_molecule_join_native_network.py").read_text()
    )
    helpers = {**functions(new_tree), **classes(new_tree)}
    selected = [helpers["Clean"], helpers["statement"], helpers["literal_nodes"]]
    native_namespace = dict(
        ast=ast, copy=copy, previous=SimpleNamespace(literal_nodes=namespace["literal_nodes"])
    )
    exec(
        compile(
            ast.Module(body=selected, type_ignores=[]), "<stdlib molecule AST builder>", "exec"
        ),
        native_namespace,
    )
    captured = ast.Module(body=native_namespace["literal_nodes"](UPSTREAM), type_ignores=[])
    captured_classes = classes(captured)
    source_tree = ast.parse(
        (ROOT / "src/cells/processes/betse_normal_molecule_source.py").read_text()
    )
    source_classes = classes(source_tree)
    parent_tree = ast.parse(
        (ROOT / "src/cells/processes/betse_normal_network_join_source.py").read_text()
    )
    parent_classes = classes(parent_tree)
    comparisons = {}
    for class_name, original_name, ported in (
        (
            "_LiteralNetwork",
            "MasterOfNetworks",
            {
                **functions(parent_classes["_LiteralNetwork"]),
                **functions(source_classes["_Network"]),
            },
        ),
        ("Reaction", "Reaction", functions(parent_classes["Reaction"])),
        ("Modulator", "Modulator", functions(parent_classes["Modulator"])),
        ("Molecule", "Molecule", functions(source_classes["_Molecule"])),
    ):
        for name, method in functions(captured_classes[class_name]).items():
            actual = ported[name]
            assert digest(actual) == digest(method), (
                class_name,
                name,
                "observational AST mismatch",
            )
            numeric = Numeric().visit(copy.deepcopy(method))
            comparisons[original_name + "." + name] = dict(
                observational_AST_equal=True, numeric_AST_sha256=digest(numeric)
            )
    captured_functions = functions(captured)
    source_functions = functions(source_tree)
    for name in ("electroflux", "update_Co", "molecule_mover", "no_negs"):
        assert digest(source_functions[name]) == digest(captured_functions[name]), name
        comparisons[name] = dict(
            observational_AST_equal=True,
            numeric_AST_sha256=digest(Numeric().visit(copy.deepcopy(captured_functions[name]))),
        )
    assert len(comparisons) == 22
    exception_audit = {}
    for name in ("BetseException", "BetseSimException", "BetseSimUnstableException"):
        assert digest(source_classes[name]) == digest(captured_classes[name]), name
        exception_audit[name] = dict(AST_sha256=digest(source_classes[name]), unchanged=True)
    new_outer = functions(
        ast.parse((ROOT / "src/cells/processes/betse_normal_molecule_join.py").read_text())
    )
    old_outer = functions(
        ast.parse((ROOT / "src/cells/processes/betse_normal_network_join.py").read_text())
    )
    outer = {}
    for name in (
        "_pump_material_step",
        "_pumped_material_step",
        "_active_material_step",
        "vector_state",
        "_initialize_gate",
    ):
        assert digest(new_outer[name]) == digest(old_outer[name]), name
        outer[name] = dict(
            AST_sha256=digest(new_outer[name]), unchanged_from_accepted_feedback=True
        )
    return dict(
        literal_numeric_bodies=comparisons,
        exception_classes=exception_audit,
        outer_helpers=outer,
        stdlib_AST_builder_execution_only=True,
        scientific_AST_executions=0,
    )


if __name__ == "__main__":
    import json

    result = audit()
    print(
        json.dumps(
            dict(
                literal_numeric_bodies=len(result["literal_numeric_bodies"]),
                exception_classes=len(result["exception_classes"]),
                outer_helpers=len(result["outer_helpers"]),
                scientific_AST_executions=0,
            )
        )
    )
