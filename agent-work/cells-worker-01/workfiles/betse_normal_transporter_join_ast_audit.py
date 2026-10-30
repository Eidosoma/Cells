"""Original-AST audits, executing only stdlib transformation code."""

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
            "self._observe_transporter",
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


def literal_capture_nodes():
    # Only stdlib AST builders are compiled below. No returned scientific AST
    # body is compiled, imported or executed by this audit.
    feedback = ast.parse(
        (ROOT / "validation/betse/betse_normal_network_join_native_network.py").read_text()
    )
    methods = next(
        ast.literal_eval(node.value)
        for node in feedback.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "METHODS" for target in node.targets)
    )
    namespace = dict(ast=ast, copy=copy, METHODS=methods)
    exec(
        compile(
            ast.Module(body=[functions(feedback)["literal_nodes"]], type_ignores=[]),
            "<stdlib feedback AST builder>",
            "exec",
        ),
        namespace,
    )
    for prefix in ("molecule", "transporter"):
        tree = ast.parse(
            (ROOT / f"validation/betse/betse_normal_{prefix}_join_native_network.py").read_text()
        )
        definitions = {**functions(tree), **classes(tree)}
        builder = copy.deepcopy(definitions["literal_nodes"])
        builder.body = [node for node in builder.body if not isinstance(node, ast.ImportFrom)]
        previous = SimpleNamespace(literal_nodes=namespace["literal_nodes"])
        namespace = dict(ast=ast, copy=copy, previous=previous, molecule_native=previous)
        selected = [definitions["Clean"], definitions["statement"], builder]
        exec(
            compile(
                ast.Module(body=selected, type_ignores=[]),
                "<stdlib " + prefix + " AST builder>",
                "exec",
            ),
            namespace,
        )
    return namespace["literal_nodes"](UPSTREAM)


def audit():
    captured = ast.Module(body=literal_capture_nodes(), type_ignores=[])
    captured_classes = classes(captured)
    parent_tree = ast.parse(
        (ROOT / "src/cells/processes/betse_normal_network_join_source.py").read_text()
    )
    molecule_tree = ast.parse(
        (ROOT / "src/cells/processes/betse_normal_molecule_source.py").read_text()
    )
    tree = ast.parse((ROOT / "src/cells/processes/betse_normal_transporter_source.py").read_text())
    parents, molecules, own = classes(parent_tree), classes(molecule_tree), classes(tree)
    implementations = {
        "_LiteralNetwork": (
            "MasterOfNetworks",
            functions(parents["_LiteralNetwork"])
            | functions(molecules["_Network"])
            | functions(own["_Network"]),
        ),
        "Reaction": ("Reaction", functions(parents["Reaction"])),
        "Modulator": ("Modulator", functions(parents["Modulator"])),
        "Molecule": ("Molecule", functions(molecules["_Molecule"])),
        "Transporter": ("Transporter", functions(own["Transporter"])),
    }
    original = classes(ast.parse((UPSTREAM / "science/chemistry/networks.py").read_text()))
    proof = {}
    for key, (name, implementation) in implementations.items():
        for method, native in functions(captured_classes[key]).items():
            assert digest(implementation[method]) == digest(native), (name, method, "observational")
            cleaned = Numeric().visit(copy.deepcopy(native))
            literal = Numeric().visit(copy.deepcopy(functions(original[name])[method]))
            assert digest(cleaned) == digest(literal), (name, method, "literal source")
            proof[name + "." + method] = dict(
                observational_AST_equal=True,
                numeric_AST_sha256=digest(cleaned),
                source_path="betse/science/chemistry/networks.py",
                first_line=functions(original[name])[method].lineno,
                last_line=functions(original[name])[method].end_lineno,
            )
    native_functions, molecule_functions = functions(captured), functions(molecule_tree)
    toolbox = functions(ast.parse((UPSTREAM / "science/sim_toolbox.py").read_text()))
    for name in ("electroflux", "update_Co", "molecule_mover", "no_negs"):
        assert digest(molecule_functions[name]) == digest(native_functions[name]), name
        cleaned = Numeric().visit(copy.deepcopy(native_functions[name]))
        assert digest(cleaned) == digest(Numeric().visit(copy.deepcopy(toolbox[name]))), name
        proof[name] = dict(
            observational_AST_equal=True,
            numeric_AST_sha256=digest(cleaned),
            source_path="betse/science/sim_toolbox.py",
            first_line=toolbox[name].lineno,
            last_line=toolbox[name].end_lineno,
        )
    assert len(proof) == 27
    outer, predecessor = (
        functions(
            ast.parse(
                (ROOT / ("src/cells/processes/betse_normal_" + prefix + "_join.py")).read_text()
            )
        )
        for prefix in ("transporter", "molecule")
    )
    helpers = {}
    for name in (
        "_pump_material_step",
        "_pumped_material_step",
        "_active_material_step",
        "vector_state",
        "_initialize_gate",
    ):
        assert digest(outer[name]) == digest(predecessor[name]), name
        helpers[name] = dict(AST_sha256=digest(outer[name]), unchanged_from_frozen_molecule=True)
    exceptions = {}
    for name in ("BetseException", "BetseSimException", "BetseSimUnstableException"):
        assert digest(molecules[name]) == digest(captured_classes[name]), name
        exceptions[name] = dict(AST_sha256=digest(molecules[name]), unchanged=True)
    sim = ast.parse((UPSTREAM / "science/sim.py").read_text())
    order = sorted(
        (node.lineno, ast.unparse(node.func))
        for node in ast.walk(sim)
        if isinstance(node, ast.Call)
        and 1280 <= node.lineno <= 1304
        and any(
            ast.unparse(node.func).endswith("." + method)
            for method in (
                "clear_run_loop",
                "run_loop_transporters",
                "run_loop_channels",
                "run_loop_modulators",
                "run_loop",
            )
        )
    )
    assert [name.rsplit(".", 1)[-1] for _, name in order] == [
        "clear_run_loop",
        "run_loop_transporters",
        "run_loop_channels",
        "run_loop_modulators",
        "run_loop",
    ]
    return dict(
        literal_numeric_bodies=proof,
        exception_classes=exceptions,
        outer_helpers=helpers,
        normal_molecules_call_order=order,
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
                unchanged_outer_helpers=len(result["outer_helpers"]),
                scientific_AST_executions=0,
            )
        )
    )
