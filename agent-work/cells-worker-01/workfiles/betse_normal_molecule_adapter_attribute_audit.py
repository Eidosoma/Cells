"""Scope-aware attribute coverage from pinned AST and both configured factories.

Only Boolean/control metadata is interpreted. No scientific expression,
fixture, method, packet, array or reference is evaluated.
"""

import argparse
import ast
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path("/home/robert/Cells")
UPSTREAM = Path("/mnt/workspaces/Cells/betse-v1.5.0/betse")
UNKNOWN = object()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def functions(tree):
    return {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}


def constants(tree):
    return {
        target.id: ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
        and target.id in {"PARAMETERS", "DYNAMIC", "BASE_FIELDS"}
        and isinstance(node.value, (ast.Set, ast.Tuple, ast.List))
    }


def value(node, known):
    if ast.unparse(node) in known:
        return known[ast.unparse(node)]
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        result = value(node.operand, known)
        return UNKNOWN if result is UNKNOWN else not result
    if isinstance(node, ast.BoolOp):
        results = [value(child, known) for child in node.values]
        if isinstance(node.op, ast.And):
            return (
                False
                if any(item is False for item in results)
                else True
                if all(item is True for item in results)
                else UNKNOWN
            )
        return (
            True
            if any(item is True for item in results)
            else False
            if all(item is False for item in results)
            else UNKNOWN
        )
    if isinstance(node, ast.Compare) and len(node.ops) == 1:
        left, right = value(node.left, known), value(node.comparators[0], known)
        if left is UNKNOWN or right is UNKNOWN:
            return UNKNOWN
        if isinstance(node.ops[0], (ast.Is, ast.Eq)):
            return left == right
        if isinstance(node.ops[0], (ast.IsNot, ast.NotEq)):
            return left != right
    return UNKNOWN


class Reachable(ast.NodeTransformer):
    def __init__(self, known):
        self.known, self.excluded, self.tests = known, [], []

    def visit_If(self, node):
        self.tests.append(copy.deepcopy(node.test))
        decision = value(node.test, self.known)
        if decision is UNKNOWN:
            return self.generic_visit(node)
        excluded = node.orelse if decision else node.body
        self.excluded.append(
            dict(
                condition=ast.unparse(node.test),
                taken=decision,
                omitted_lines=[child.lineno for child in excluded],
            )
        )
        return [self.visit(child) for child in (node.body if decision else node.orelse)]


def attributes(node):
    result = {key: set() for key in ("self", "sim", "cells", "p", "phase")}
    for child in ast.walk(node):
        if (
            isinstance(child, ast.Attribute)
            and isinstance(child.ctx, ast.Load)
            and isinstance(child.value, ast.Name)
            and child.value.id in result
        ):
            result[child.value.id].add(child.attr)
    return result


def producers(paths):
    result = {key: {} for key in ("obj", "mol", "sim", "cells", "p", "parameters")}
    for relative in paths:
        tree = ast.parse((ROOT / relative).read_text())
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Attribute)
                and isinstance(node.ctx, ast.Store)
                and isinstance(node.value, ast.Name)
                and node.value.id in result
            ):
                result[node.value.id].setdefault(node.attr, []).append(
                    dict(path=relative, line=node.lineno, kind="attribute assignment")
                )
            if (
                isinstance(node, ast.Assign)
                and isinstance(node.value, ast.Call)
                and ast.unparse(node.value.func) == "SimpleNamespace"
            ):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id in result:
                        for item in node.value.keywords:
                            if item.arg:
                                result[target.id].setdefault(item.arg, []).append(
                                    dict(
                                        path=relative,
                                        line=node.lineno,
                                        kind="SimpleNamespace keyword",
                                    )
                                )
            if (
                isinstance(node, ast.For)
                and isinstance(node.target, ast.Tuple)
                and isinstance(node.iter, (ast.Tuple, ast.List))
            ):
                names = [
                    item.id if isinstance(item, ast.Name) else None for item in node.target.elts
                ]
                for call in ast.walk(node):
                    if (
                        not isinstance(call, ast.Call)
                        or ast.unparse(call.func) != "setattr"
                        or len(call.args) < 2
                        or not isinstance(call.args[0], ast.Name)
                        or call.args[0].id not in result
                        or not isinstance(call.args[1], ast.Name)
                        or call.args[1].id not in names
                    ):
                        continue
                    column = names.index(call.args[1].id)
                    for entry in node.iter.elts:
                        if (
                            isinstance(entry, ast.Tuple)
                            and len(entry.elts) > column
                            and isinstance(entry.elts[column], ast.Constant)
                            and isinstance(entry.elts[column].value, str)
                        ):
                            result[call.args[0].id].setdefault(entry.elts[column].value, []).append(
                                dict(path=relative, line=node.lineno, kind="literal setattr loop")
                            )
    return result


def audit():
    source_path = "src/cells/processes/betse_normal_molecule_source.py"
    native_path = "validation/betse/betse_normal_molecule_join_native_network.py"
    source = ast.parse((ROOT / source_path).read_text())
    metadata = constants(source)
    network = ast.parse((UPSTREAM / "science/chemistry/networks.py").read_text())
    molecule = next(
        node for node in network.body if isinstance(node, ast.ClassDef) and node.name == "Molecule"
    )
    methods = functions(molecule)
    toolbox = functions(ast.parse((UPSTREAM / "science/sim_toolbox.py").read_text()))
    known = {
        "p.is_ecm": False,
        "self.update_intra_conc": False,
        "update_intra": False,
        "update_at_mems": False,
        "self.transmem": False,
        "transmem": False,
        "cmems is None": False,
        "len(cmems) == sim.mdl": True,
    }
    required = {key: set() for key in ("self", "sim", "cells", "p", "phase")}
    reachability = {}
    for name, original in [
        ("Molecule.transport", methods["transport"]),
        ("Molecule.update_intra", methods["update_intra"]),
    ] + [
        (name, toolbox[name]) for name in ("molecule_mover", "update_Co", "electroflux", "no_negs")
    ]:
        pruning = Reachable(known)
        node = pruning.visit(copy.deepcopy(original))
        fields = attributes(node)
        for test in pruning.tests:
            for key, values in attributes(test).items():
                fields[key] |= values
        for key, values in fields.items():
            required[key] |= values
        reachability[name] = dict(
            source_lines=[original.lineno, original.end_lineno],
            reachable_attributes={key: sorted(values) for key, values in fields.items()},
            excluded_branches=pruning.excluded,
        )
    production_paths = [source_path, "src/cells/processes/betse_normal_network_join_source.py"]
    native_paths = [
        native_path,
        "validation/betse/betse_normal_molecule_join_native.py",
        "validation/betse/betse_normal_molecule_join_native_helpers.py",
    ]
    prod, native = producers(production_paths), producers(native_paths)
    constructor_fields = {
        node.attr
        for node in ast.walk(methods["__init__"])
        if isinstance(node, ast.Attribute)
        and isinstance(node.ctx, ast.Store)
        and isinstance(node.value, ast.Name)
        and node.value.id == "self"
    }
    shared = set(metadata["PARAMETERS"]) | set(metadata["DYNAMIC"][:4]) | constructor_fields
    inventories = {
        "production": dict(
            self=shared | set(prod["obj"]),
            sim=set(prod["sim"]),
            cells=set(prod["cells"]),
            p=set(prod["p"]),
        ),
        "native": dict(
            self=shared | set(native["mol"]),
            sim=set(native["sim"]),
            cells=set(native["cells"]) | {"M_sum_mems"},
            p=set(native["p"]) | set(native["parameters"]),
        ),
    }
    # Audit that both factories actually apply all validated parameter keys.
    factory_loops = {}
    for relative in (source_path, native_path):
        tree = ast.parse((ROOT / relative).read_text())
        loops = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.For)
            and ast.dump(ast.parse("row['parameters'].items()", mode="eval").body)
            == ast.dump(node.iter)
        ]
        assert len(loops) == 1 and any(
            isinstance(child, ast.Call) and ast.unparse(child.func) == "setattr"
            for child in ast.walk(loops[0])
        )
        factory_loops[relative] = loops[0].lineno
    # Literal owner-matrix extraction in the established native runner.
    capture = (ROOT / "validation/betse/betse_normal_ion_join_native.py").read_text()
    assert '== "self.M_sum_mems"' in capture and "owner = matrix.body[start : stop + 1]" in capture
    default = [
        node
        for node in ast.walk(network)
        if isinstance(node, ast.Assign)
        and any(ast.unparse(target) == "mol.ignore_ECM_pump" for target in node.targets)
    ]
    assert len(default) == 1 and ast.literal_eval(default[0].value) is True
    missing = {
        kind: {
            key: sorted(required[key] - values)
            for key, values in inventory.items()
            if required[key] - values
        }
        for kind, inventory in inventories.items()
    }
    return dict(
        kind="cells.native_molecule_adapter_attribute_coverage@1",
        scope=(
            "Complete reachable attributes for declared no-ECM, instant intra, transmem False, "
            "Dm0/nonzero and ignoreGJ True/False; no numerical/body execution"
        ),
        source_sha256={
            "betse/science/chemistry/networks.py": sha(UPSTREAM / "science/chemistry/networks.py"),
            "betse/science/sim_toolbox.py": sha(UPSTREAM / "science/sim_toolbox.py"),
        },
        adapter_sha256={
            relative: sha(ROOT / relative) for relative in production_paths + native_paths
        },
        known_control_metadata=known,
        factory_parameter_setattr_loops=factory_loops,
        literal_source_default=dict(
            path="betse/science/chemistry/networks.py",
            line=default[0].lineno,
            statement=ast.unparse(default[0]),
            value=True,
        ),
        reachability=reachability,
        inventories={
            kind: {key: sorted(values) for key, values in inventory.items()}
            for kind, inventory in inventories.items()
        },
        reachable_required={key: sorted(values) for key, values in required.items()},
        missing=missing,
        scientific_imports=0,
        scientific_AST_executions=0,
        numerical_runs=0,
        excluded_scope_requires_additional_state=True,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--expect-missing", action="store_true")
    args = parser.parse_args()
    result = audit()
    expected = {
        kind: {"self": ["ignore_ECM_pump"]} if args.expect_missing else {}
        for kind in ("production", "native")
    }
    assert result["missing"] == expected, result["missing"]
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(
        json.dumps(
            dict(
                output=str(args.output),
                missing=result["missing"],
                reachable_required=result["reachable_required"],
                scientific_imports=0,
                numerical_runs=0,
            )
        )
    )


if __name__ == "__main__":
    main()
