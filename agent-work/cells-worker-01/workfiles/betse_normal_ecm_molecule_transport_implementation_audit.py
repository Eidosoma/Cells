"""Regenerate, parse, compare and compile source without scientific execution."""

import argparse
import ast
import builtins
import copy
import hashlib
import importlib.util
import json
import resource
import symtable
import sys
from pathlib import Path

import betse_normal_ecm_init_sim_transition_implementation_audit as common

ROOT = Path("/home/robert/Cells")
WORK = Path(__file__).parent
BASE = Path("/mnt/workspaces/Cells")
PARENT = BASE / "betse-normal-ecm-molecule-dispatch-prepared-20261031-01/source"
TRANSPORTER = BASE / "betse-normal-transporter-prepared-20261030-03/source"
NATIVE = BASE / "betse-v1.5.0/betse"
PREFIX = "betse_normal_ecm_molecule_transport"
OLD = "betse_normal_ecm_molecule_dispatch"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def resolve(name):
    own = PREFIX in name
    for base in (ROOT,) if own else (PARENT, TRANSPORTER):
        for prefix in ("", "src/"):
            for suffix in (".py", "/__init__.py"):
                path = base / (prefix + name.replace(".", "/") + suffix)
                if path.is_file():
                    return path
    return None


class RemoveObservations(ast.NodeTransformer):
    def visit_Expr(self, node):
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            return None
        if isinstance(node.value, ast.Call) and ast.unparse(node.value.func) in {
            "self._observe_transporter",
            "hook",
        }:
            return None
        return self.generic_visit(node)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--regenerate", type=Path, required=True)
    args = parser.parse_args()
    resource.setrlimit(resource.RLIMIT_CPU, (90, 90))
    resource.setrlimit(resource.RLIMIT_AS, (512 * 2**20, 512 * 2**20))
    if args.output.exists() or args.regenerate.exists():
        raise ValueError("Preserve prior static evidence; choose exclusive output paths")
    args.regenerate.mkdir(parents=True)
    proofs = {}

    def same(label, a, b):
        assert common.normalized(a) == common.normalized(b), label
        proofs[label] = True

    for suffix in ("implementation", "native", "reference", "checks"):
        path = WORK / ("prepare_" + PREFIX + "_" + suffix + ".py")
        spec = importlib.util.spec_from_file_location(
            "stdlib_transporter_generator_" + suffix, path
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.ROOT = args.regenerate
        module.main()
    for path in sorted(args.regenerate.rglob("*.py")):
        relative = path.relative_to(args.regenerate)
        same(
            "regeneration/" + str(relative),
            ast.parse(path.read_text()),
            ast.parse((ROOT / relative).read_text()),
        )
    product = ROOT / "src/cells/processes" / (PREFIX + "_source.py")
    independent = ROOT / "validation/betse" / (PREFIX + "_native_source.py")
    original = NATIVE / "science/chemistry/networks.py"
    for cls, names in (
        ("MasterOfNetworks", ("read_transporters", "write_transporters", "run_loop_transporters")),
        ("Transporter", ("__init__", "init_reaction")),
    ):
        for name in names:
            actual = RemoveObservations().visit(common.fn(product, name, cls))
            wanted = RemoveObservations().visit(common.native_clean(common.fn(original, name, cls)))
            same("literal_native/" + cls + "." + name, actual, wanted)
    for name in ("__init__", "read_mol_config", "reinitialize"):
        for label, path in (("product", product), ("independent", independent)):
            same(
                label + "/literal_general_" + name,
                common.fn(path, name, "MasterOfMolecules"),
                common.native_clean(
                    common.fn(NATIVE / "science/chemistry/molecules.py", name, "MasterOfMolecules")
                ),
            )
    protected = (
        "initialize_both",
        "dispatch_both",
        "before_general",
        "install_channel_observer_general",
        "owner_evidence_general",
    )
    for name in protected:
        same(
            "frozen_complete_general_helper/" + name,
            common.fn(product, name),
            common.fn(PARENT / "src/cells/processes" / (OLD + "_source.py"), name),
        )
    tree = ast.parse(product.read_text())
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name not in {
            "Transporter",
            "MasterOfNetworks",
        }:
            other_tree = ast.parse(independent.read_text())
            other = next(
                n for n in other_tree.body if isinstance(n, type(node)) and n.name == node.name
            )
            same("independent_observation_plumbing/" + node.name, node, other)
    ctl = ROOT / "src/cells/processes" / (PREFIX + ".py")
    for name in ("binding_record", "state_record", "state", "initialize", "advance"):
        same(
            "complete_frozen_primary_CaATP_field_composition/" + name,
            common.fn(ctl, name),
            common.fn(PARENT / "src/cells/processes" / (OLD + ".py"), name),
        )
    verifier = common.fn(ctl, "verify")
    assert ast.unparse(verifier.body.pop()) == "runtime.validate_transport_cache(binding, parent)"
    same(
        "original_complete_state_verifier_plus_new_transport_cache",
        verifier,
        common.fn(PARENT / "src/cells/processes" / (OLD + ".py"), "verify"),
    )
    runtime = ROOT / "src/cells/processes" / (PREFIX + "_runtime.py")
    for name in (
        "owner_identity",
        "owner_cache",
        "cache",
        "available",
        "restore",
        "conditional_input",
    ):
        same(
            "retained_full_runtime_books/" + name,
            common.fn(runtime, name),
            common.fn(PARENT / "src/cells/processes" / (OLD + "_runtime.py"), name),
        )
    old_reference = TRANSPORTER / "validation/betse/betse_normal_transporter_join_reference.py"
    equations = ROOT / "validation/betse" / (PREFIX + "_equations.py")
    same(
        "unchanged_independent_regulation",
        common.fn(equations, "regulation"),
        common.fn(old_reference, "regulation"),
    )

    def rate_prefix(path, function):
        body = next(n for n in common.fn(path, function).body if isinstance(n, ast.With)).body
        return next(n for n in body if isinstance(n, ast.For) and ast.unparse(n.target) == "config")

    old_rate = rate_prefix(old_reference, "transporters")
    new_rate = rate_prefix(equations, "evaluate")

    class UnmapECMSample(ast.NodeTransformer):
        def visit_Subscript(self, node):
            if ast.unparse(node) == "state[zone][species][mapping[j] if external else j]":
                return ast.parse("state[zone][species][j]", mode="eval").body
            return self.generic_visit(node)

    same(
        "unchanged_independent_rate_entire_prefix_with_only_ECM_sample_mapping",
        ast.Module(
            body=[UnmapECMSample().visit(copy.deepcopy(n)) for n in new_rate.body[:11]],
            type_ignores=[],
        ),
        ast.Module(body=old_rate.body[:11], type_ignores=[]),
    )
    helpers = ROOT / "validation/betse" / (PREFIX + "_native_network.py")
    old_helpers = TRANSPORTER / "validation/betse/betse_normal_transporter_join_native_network.py"
    literal = common.fn(helpers, "literal_nodes")

    class RestoreNativeRoot(ast.NodeTransformer):
        def visit_Attribute(self, node):
            if ast.unparse(node) == "qualified.literal_nodes":
                return ast.parse("molecule_native.literal_nodes", mode="eval").body
            return self.generic_visit(node)

    literal = RestoreNativeRoot().visit(literal)
    selected_class = next(
        n
        for n in literal.body
        if isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) == "network"
    )
    for n in ast.walk(selected_class):
        if isinstance(n, ast.Constant) and n.value == "MasterOfNetworks":
            n.value = "_LiteralNetwork"
    literal.body[0:0] = ast.parse(
        "from validation.betse import betse_normal_molecule_join_native_network as molecule_native"
    ).body
    same(
        "independent_native_literal_method_and_observer_loader_only_ECM_parent_changed",
        literal,
        common.fn(old_helpers, "literal_nodes"),
    )
    files = []
    for directory in ("src/cells/processes", "validation/betse", "tests/unit"):
        files.extend((ROOT / directory).glob("*" + PREFIX + "*.py"))
    allowed = set(dir(builtins)) | {"__file__", "__name__", "__doc__", "__package__", "__spec__"}
    exports = {}
    for path in sorted(files):
        source = path.read_text()
        tree = ast.parse(source)
        compile(tree, str(path), "exec")
        known = common.bound_names(tree) | allowed

        def unresolved(scope, known=known):
            names = {
                s.get_name()
                for s in scope.get_symbols()
                if s.is_global() and s.is_referenced() and s.get_name() not in known
            }
            for child in scope.get_children():
                names |= unresolved(child)
            return names

        assert not unresolved(symtable.symtable(source, str(path), "exec")), str(path)
        for statement in tree.body:
            if not isinstance(statement, ast.ImportFrom):
                continue
            for alias in statement.names:
                dep = resolve(statement.module + "." + alias.name)
                if dep is None:
                    continue
                bound = exports.setdefault(str(dep), common.bound_names(ast.parse(dep.read_text())))
                name = alias.asname or alias.name
                used = {
                    n.attr
                    for n in ast.walk(tree)
                    if isinstance(n, ast.Attribute)
                    and isinstance(n.value, ast.Name)
                    and n.value.id == name
                }
                assert used <= bound, (str(path), str(dep), sorted(used - bound))
    assert len(files) == 10
    assert not any(
        n.split(".")[0] in {"cells", "betse", "numpy", "scipy", "jax", "jaxlib", "pytest"}
        for n in sys.modules
    )
    result = dict(
        kind="cells.held_general_ECM_transporter_implementation_audit@1",
        status="source_static_complete_unrun",
        proofs=proofs,
        compile_and_global_names=True,
        direct_module_attributes=True,
        source_sha256={str(p.relative_to(ROOT)): sha(p) for p in sorted(files)},
        scientific_imports=0,
        scientific_AST_executions=0,
        fixture_model_reference_evaluations=0,
        pytest_collections=0,
        numerical_runs=0,
        regenerated_files=len(list(args.regenerate.rglob("*.py"))),
    )
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(
        json.dumps(
            dict(
                output=str(args.output),
                sha256=sha(args.output),
                proofs=len(proofs),
                compiled_files=len(files),
                scientific_evaluations=0,
            )
        )
    )


if __name__ == "__main__":
    main()
