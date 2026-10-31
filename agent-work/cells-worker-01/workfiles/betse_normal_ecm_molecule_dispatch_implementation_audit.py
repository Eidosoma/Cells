"""Regeneration and native/qualified AST correspondence, without science imports."""

import argparse
import ast
import hashlib
import importlib.util
import json
import resource
import sys
import time
from pathlib import Path

import betse_normal_ecm_init_sim_transition_implementation_audit as checks

ROOT = Path("/home/robert/Cells")
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
PARENT = Path("/mnt/workspaces/Cells/betse-normal-ecm-init-phase-prepared-20261031-02/source")
NATIVE = Path("/mnt/workspaces/Cells/betse-v1.5.0/betse")
PREFIX = "betse_normal_ecm_molecule_dispatch"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--regenerate", type=Path, required=True)
    args = parser.parse_args()
    started = time.monotonic()
    resource.setrlimit(resource.RLIMIT_CPU, (90, 90))
    resource.setrlimit(resource.RLIMIT_AS, (512 * 2**20, 512 * 2**20))
    if args.output.exists() or args.regenerate.exists():
        raise ValueError("Preserve earlier static evidence")
    for name in ("src/cells/processes", "validation/betse"):
        (args.regenerate / name).mkdir(parents=True)
    proofs = {}
    for suffix in ("source", "native_source", "reference"):
        script = WORK / f"prepare_{PREFIX}_{suffix}.py"
        spec = importlib.util.spec_from_file_location(
            "stdlib_general_source_generator_" + suffix, script
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.ROOT = args.regenerate
        module.main()
    for path in args.regenerate.rglob("*.py"):
        relative = path.relative_to(args.regenerate)
        assert checks.normalized(ast.parse(path.read_text())) == checks.normalized(
            ast.parse((ROOT / relative).read_text())
        ), str(relative)
        proofs["regeneration/" + str(relative)] = True
    owned = ROOT / "src/cells/processes" / f"{PREFIX}_source.py"
    native = ROOT / "validation/betse" / f"{PREFIX}_native_source.py"
    for name in ("__init__", "read_mol_config", "reinitialize"):
        expected = checks.native_clean(
            checks.fn(NATIVE / "science/chemistry/molecules.py", name, "MasterOfMolecules")
        )
        for label, path in (("owned", owned), ("independent_native", native)):
            assert checks.normalized(
                checks.fn(path, name, "MasterOfMolecules")
            ) == checks.normalized(expected)
            proofs[label + "/literal_MasterOfMolecules_" + name] = True

    class RemoveHooks(ast.NodeTransformer):
        def visit_Expr(self, node):
            if isinstance(node.value, ast.Call) and ast.unparse(node.value.func) == "hook":
                return None
            return self.generic_visit(node)

    source_setup = checks.fn(NATIVE / "science/sim.py", "init_dynamics", "Simulator").body
    source_loop = next(
        n
        for n in checks.fn(NATIVE / "science/sim.py", "_run_sim_core_loop", "Simulator").body
        if isinstance(n, ast.For)
    ).body
    for name, source_body in (("initialize_both", source_setup), ("dispatch_both", source_loop)):
        expected = [
            n
            for n in source_body
            if isinstance(n, ast.If)
            and ast.unparse(n.test) in ("p.molecules_enabled", "p.grn_enabled")
        ]
        for label, path in (("owned", owned), ("independent_native", native)):
            actual = RemoveHooks().visit(checks.fn(path, name)).body
            assert [checks.normalized(n) for n in actual] == [
                checks.normalized(n) for n in expected
            ]
            proofs[label + "/" + name + "_complete_adjacent_native_guards_inverse"] = True
    rename = {
        name + "_general": name
        for name in (
            "cache",
            "restore",
            "before",
            "attach",
            "install_channel_observer",
            "owner_evidence",
        )
    }

    class RestoreRole(ast.NodeTransformer):
        def visit_Name(self, node):
            if node.id in rename:
                node.id = rename[node.id]
            elif node.id == "science_general":
                node.id = "science"
            return node

        def visit_Attribute(self, node):
            if ast.unparse(node) == "p.network_config":
                return ast.parse("p.grn.conf", mode="eval").body
            if node.attr == "molecules" and ast.unparse(node.value) in ("sim", "ctx.sim"):
                node.attr = "grn"
            return self.generic_visit(node)

        def visit_Call(self, node):
            if (
                isinstance(node.func, ast.Name)
                and node.func.id == "getattr"
                and len(node.args) >= 2
                and ast.unparse(node.args[0]) == "ctx.sim"
                and isinstance(node.args[1], ast.Constant)
                and node.args[1].value == "molecules"
            ):
                node.args[1] = ast.Constant("grn")
            return self.generic_visit(node)

    for name in rename.values():
        original = (
            PARENT
            / "src/cells/processes"
            / (
                "betse_ecm_grn_source.py"
                if name == "owner_evidence"
                else "betse_normal_ecm_catalog_join_source.py"
            )
        )
        function = checks.fn(owned, name + "_general")
        function.name = name
        assert checks.normalized(RestoreRole().visit(function)) == checks.normalized(
            checks.fn(original, name)
        ), name
        proofs["complete_qualified_helper_role_inverse/" + name] = True
    cache = checks.fn(owned, "cache_general")
    assert "getattr(ctx.sim, 'molecules', None)" in ast.unparse(cache)
    assert "getattr(ctx.sim, 'grn', None)" not in ast.unparse(cache)
    proofs["general_cache_getattr_literal_uses_distinct_owner"] = True
    # The first prefix is the complete independent ordinary material/CaATP body
    # through supplied late flux. Its tail is truncated before network dispatch.
    model = ROOT / "validation/betse" / f"{PREFIX}_reference_models.py"
    original = checks.fn(
        PARENT / "validation/betse/betse_normal_ecm_catalog_join_reference.py", "material_model"
    )
    original_with = next(n for n in original.body if isinstance(n, ast.With))
    original_loop = next(n for n in original_with.body if isinstance(n, ast.For))
    cut = next(
        i
        for i, n in enumerate(original_loop.body)
        if isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) == "channel_result"
    )
    prefix = checks.fn(model, "prefix_model")
    prefix_loop = next(
        n
        for n in next(n for n in prefix.body if isinstance(n, ast.With)).body
        if isinstance(n, ast.For)
    )
    assert [checks.normalized(n) for n in prefix_loop.body[:-1]] == [
        checks.normalized(n) for n in original_loop.body[:cut]
    ]
    proofs["independent_material_CaATP_prefix_entire_body_exact"] = True
    commit = checks.fn(model, "commit_model")
    actual_with = next(n for n in commit.body if isinstance(n, ast.With))
    actual_loop = next(
        n for n in actual_with.body if isinstance(n, ast.For) and ast.unparse(n.target) == "i"
    )
    assert checks.normalized(actual_loop) == checks.normalized(original_loop.body[cut + 1])
    proofs["independent_deferred_commit_entire_equation_loop_exact"] = True
    after = actual_with.body[actual_with.body.index(actual_loop) + 1 :]
    wanted = original_loop.body[cut + 2 : -1]
    assert [checks.normalized(n) for n in after[: len(wanted)]] == [
        checks.normalized(n) for n in wanted
    ]
    proofs["independent_entire_original_amount_diagnostics_exact"] = True
    controller = ROOT / "src/cells/processes" / f"{PREFIX}.py"
    advance = checks.fn(controller, "advance")
    calls = [ast.unparse(n.func) for n in ast.walk(advance) if isinstance(n, ast.Call)]
    assert calls.count("calcium._material_step") == 1 and calls.count("full.reconstruct") == 1
    assert "runtime.dispatch" in calls and "runtime.restore" in calls
    proofs["one_material_tick_and_one_field_suffix_with_complete_dual_dispatch"] = True
    runtime = ROOT / "src/cells/processes" / f"{PREFIX}_runtime.py"
    context = checks.fn(runtime, "make_context")
    body = ast.unparse(context)
    assert (
        body.index("network.make_context(")
        < body.index("ctx.p.grn_enabled =")
        < body.index("return ctx")
    )
    assert "initialize_both(" not in body and "dispatch_both(" not in body
    proofs["actual_independent_flags_set_before_any_handler_constructor_or_dispatch"] = True
    # No scientific function or AST is executed. Compile/name checks inspect
    # scopes and direct local-module exports, including newly generated files.
    files = []
    for directory in ("src/cells/processes", "validation/betse", "tests/unit"):
        files.extend((ROOT / directory).glob("*" + PREFIX + "*.py"))
    import builtins

    allowed = set(dir(builtins)) | {"__file__", "__name__", "__doc__", "__package__", "__spec__"}
    import symtable

    for path in files:
        text = path.read_text()
        tree = ast.parse(text)
        compile(tree, str(path), "exec")
        known = checks.bound_names(tree) | allowed

        def unresolved(scope, known=known):
            out = {
                s.get_name()
                for s in scope.get_symbols()
                if s.is_global() and s.is_referenced() and s.get_name() not in known
            }
            for child in scope.get_children():
                out |= unresolved(child)
            return out

        assert not unresolved(symtable.symtable(text, str(path), "exec")), (
            str(path),
            "undefined globals",
        )
        for statement in tree.body:
            if isinstance(statement, ast.ImportFrom):
                for alias in statement.names:
                    dependency = checks.module_path(statement.module + "." + alias.name)
                    if dependency is None:
                        continue
                    exported = checks.bound_names(ast.parse(dependency.read_text()))
                    name = alias.asname or alias.name
                    for node in ast.walk(tree):
                        if (
                            isinstance(node, ast.Attribute)
                            and isinstance(node.value, ast.Name)
                            and node.value.id == name
                        ):
                            assert node.attr in exported or node.attr.startswith("__"), (
                                str(path),
                                name,
                                node.attr,
                                str(dependency),
                            )
    proofs["all_new_files_compile_and_global_module_names_resolve"] = True
    result = dict(
        kind="cells.held_general_molecule_source_audit@1",
        status="passed",
        proofs=proofs,
        source_sha256={str(p.relative_to(ROOT)): sha(p) for p in sorted(files)},
        compiled_without_execution=len(files),
        max_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
        elapsed_s=time.monotonic() - started,
        scientific_imports=0,
        scientific_AST_executions=0,
        fixture_reference_model_evaluations=0,
        pytest_collections=0,
        numerical_runs=0,
        active_job_queries=0,
        inherited_scientific_passes=0,
    )
    assert not any(
        n.split(".")[0] in {"cells", "betse", "numpy", "scipy", "jax", "jaxlib", "pytest"}
        for n in sys.modules
    )
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(
        json.dumps(
            dict(
                status="passed",
                AST_proofs=len(proofs),
                compiled_files=len(files),
                elapsed_s=result["elapsed_s"],
            )
        )
    )


if __name__ == "__main__":
    main()
