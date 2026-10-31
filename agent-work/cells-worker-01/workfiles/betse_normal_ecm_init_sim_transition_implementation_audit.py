"""Source regeneration, native correspondence and inverse AST proofs; stdlib only."""
# ruff: noqa: E501 -- exact AST comparison strings.

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
import time
from pathlib import Path

ROOT = Path("/home/robert/Cells")
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
PARENT = Path("/mnt/workspaces/Cells/betse-normal-ecm-init-phase-prepared-20261031-02/source")
NATIVE = Path("/mnt/workspaces/Cells/betse-v1.5.0/betse")
PREFIX = "betse_normal_ecm_init_sim_transition"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fn(path, name, owner=None):
    tree = ast.parse(path.read_text())
    if owner:
        tree = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == owner)
    return copy.deepcopy(
        next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    )


def normalized(node):
    node = copy.deepcopy(node)
    for item in ast.walk(node):
        if isinstance(item, (ast.Module, ast.FunctionDef, ast.ClassDef)) and item.body:
            if (
                isinstance(item.body[0], ast.Expr)
                and isinstance(item.body[0].value, ast.Constant)
                and isinstance(item.body[0].value.value, str)
            ):
                item.body.pop(0)
    if isinstance(node, ast.Module):
        imports = [n for n in node.body if isinstance(n, (ast.Import, ast.ImportFrom))]
        node.body = sorted(imports, key=lambda n: ast.dump(n, include_attributes=False)) + [
            n for n in node.body if not isinstance(n, (ast.Import, ast.ImportFrom))
        ]
    return ast.dump(node, include_attributes=False)


def native_clean(node):
    node.decorator_list = []
    node.returns = None
    for arg in node.args.args:
        arg.annotation = None
    return node


def module_path(name):
    for base in (ROOT, PARENT):
        for prefix in ("", "src/"):
            for suffix in (".py", "/__init__.py"):
                path = base / (prefix + name.replace(".", "/") + suffix)
                if path.is_file():
                    return path
    return None


def bound_names(tree):
    names = set()
    for node in tree.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name)
        elif isinstance(node, ast.Import):
            names.update(a.asname or a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.update(a.asname or a.name for a in node.names)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            names.update(
                n.id for target in targets for n in ast.walk(target) if isinstance(n, ast.Name)
            )
    return names


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--regenerate", type=Path, required=True)
    args = parser.parse_args()
    started = time.monotonic()
    resource.setrlimit(resource.RLIMIT_CPU, (90, 90))
    resource.setrlimit(resource.RLIMIT_AS, (512 * 2**20, 512 * 2**20))
    if args.output.exists() or args.regenerate.exists():
        raise ValueError("Preserve earlier static evidence; use exclusive outputs")
    args.regenerate.mkdir(parents=True)
    for relative in ("src/cells/processes", "validation/betse"):
        (args.regenerate / relative).mkdir(parents=True)
    proofs = {}
    # These four worker-owned generators parse/copy/write source and compile
    # without execution. No generated scientific module is ever imported.
    for suffix in ("source", "sim", "native", "native_sim"):
        path = WORK / ("prepare_" + PREFIX + "_" + suffix + ".py")
        spec = importlib.util.spec_from_file_location("stdlib_source_generator_" + suffix, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.ROOT = args.regenerate
        module.main()
    generated = list(args.regenerate.rglob("*.py"))
    for path in generated:
        relative = path.relative_to(args.regenerate)
        assert normalized(ast.parse(path.read_text())) == normalized(
            ast.parse((ROOT / relative).read_text())
        ), str(relative)
        proofs["source_regeneration/" + str(relative)] = True
    actual = ROOT / "src/cells/processes" / f"{PREFIX}_source.py"
    for relative, name, owner in (
        ("science/chemistry/gene.py", "reinitialize", "MasterOfGenes"),
        ("science/chemistry/networks.py", "clear_cache", "MasterOfNetworks"),
        ("science/tissue/tishandler.py", "init_profiles", "TissueHandler"),
        ("science/sim.py", "initDenv", "Simulator"),
        ("science/tissue/tishandler.py", "_finalize_events_tissue", "TissueHandler"),
        ("science/math/modulate.py", "f_sweep", None),
    ):
        assert normalized(fn(actual, name)) == normalized(
            native_clean(fn(NATIVE / relative, name, owner))
        ), name
        proofs["literal_native/" + name] = True
    clear = fn(actual, "clear_storage")

    class RestoreMethod(ast.NodeTransformer):
        def visit_Call(self, node):
            if ast.unparse(node.func) == "clear_cache":
                assert len(node.args) == 1 and ast.unparse(node.args[0]) == "self.grn.core"
                node.func = ast.parse("self.grn.core.clear_cache", mode="eval").body
                node.args = []
            return self.generic_visit(node)

    assert normalized(RestoreMethod().visit(clear)) == normalized(
        native_clean(fn(NATIVE / "science/sim.py", "clear_storage", "Simulator"))
    )
    proofs["literal_native/clear_storage_method_binding_inverse"] = True
    finalizer = fn(actual, "_finalize_events_global")
    assert [a.arg for a in finalizer.args.kwonlyargs] == ["shuffle"]
    finalizer.args.kwonlyargs = []
    finalizer.args.kw_defaults = []
    assert normalized(finalizer) == normalized(
        native_clean(
            fn(NATIVE / "science/tissue/tishandler.py", "_finalize_events_global", "TissueHandler")
        )
    )
    proofs["literal_native/global_finalizer_shuffle_injection_inverse"] = True
    assert normalized(fn(actual, "static_and_blocks")) == normalized(
        fn(
            PARENT / "validation/betse/betse_normal_ecm_init_phase_native_setup.py",
            "static_and_blocks",
        )
    )
    proofs["literal_native/static_setup_RNG_injection_body_exact"] = True
    assert normalized(
        fn(ROOT / "validation/betse" / f"{PREFIX}_native.py", "reinitialize")
    ) == normalized(
        native_clean(fn(NATIVE / "science/chemistry/gene.py", "reinitialize", "MasterOfGenes"))
    )
    proofs["independent_native_reinitialize_exact"] = True
    original = PARENT / "src/cells/processes/betse_normal_ecm_event_mechanics.py"
    private = ROOT / "src/cells/processes" / f"{PREFIX}_sim.py"
    assert normalized(fn(private, "advance")) == normalized(fn(original, "advance"))
    proofs["outer_SIM_mechanics_composition_body_exact"] = True
    adapted = fn(private, "_advance_events")
    assert [a.arg for a in adapted.args.kwonlyargs[-4:]] == [
        "entry_ca_rate_present",
        "nak_rate_before",
        "alpha_NaK",
        "before_nak",
    ]
    adapted.args.kwonlyargs = adapted.args.kwonlyargs[:-4]
    adapted.args.kw_defaults = adapted.args.kw_defaults[:-4]
    block = next(n for n in adapted.body if isinstance(n, ast.Try))

    def inserted(node):
        if isinstance(node, ast.Assign):
            return ast.unparse(node.targets[0]) in {
                "pump_binding",
                "pump_stores",
                "(nak_phase, nak_flux, nak_proxy)",
                "holder['nak']",
                "holder['nak_rate_after']",
            }
        return isinstance(node, ast.If) and ast.unparse(node.test) == "not pump.finite(nak_phase)"

    before = len(block.body)
    block.body = [n for n in block.body if not inserted(n)]
    assert before - len(block.body) == 6
    for target, keyword in (
        ("packet", "supplied_pump_membrane_flux_mol_m2_s"),
        ("material_input", "nak_before"),
    ):
        node = next(
            n
            for n in block.body
            if isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) == target
        )
        assert sum(k.arg == keyword for k in node.value.keywords) == 1
        node.value.keywords = [k for k in node.value.keywords if k.arg != keyword]
    on_network = next(
        n for n in block.body if isinstance(n, ast.FunctionDef) and n.name == "on_network"
    )
    on_network.body = [
        n for n in on_network.body if ast.unparse(n) != "current.sim.rate_NaKATP = nak_proxy.copy()"
    ]
    returned = next(n for n in block.body if isinstance(n, ast.Return))
    returned.value.elts[-1].args[0].keywords = [
        k
        for k in returned.value.elts[-1].args[0].keywords
        if k.arg not in {"nak", "nak_rate_after"}
    ]

    class RestoreGuard(ast.NodeTransformer):
        def visit_Compare(self, node):
            if (
                ast.unparse(node)
                == "rate.present is not (entry_ca_rate_present or (binding.calcium['alpha_Ca'] > 0 and index > 0))"
            ):
                return ast.parse(
                    "rate.present is not (binding.calcium['alpha_Ca'] > 0 and index > 0)",
                    mode="eval",
                ).body
            return self.generic_visit(node)

    assert normalized(RestoreGuard().visit(adapted)) == normalized(fn(original, "_advance_events"))
    proofs["SIM_event_material_calcium_GRN_noise_field_complete_NaK_cache_inverse"] = True
    previous = (PARENT / "src/cells/processes/betse_normal_ecm_init_phase_pump.py").read_text()
    newer = (
        (ROOT / "src/cells/processes" / f"{PREFIX}_pump.py")
        .read_text()
        .replace('source_phase="SIM"', 'source_phase="INIT"')
        .replace("legacy_run_sim=True", "legacy_run_sim=False")
    )
    assert normalized(ast.parse(previous)) == normalized(ast.parse(newer))
    proofs["maintained_NaK_entire_module_phase_metadata_inverse"] = True
    previous = (PARENT / "src/cells/processes/betse_normal_ecm_run_lifecycle.py").read_text()
    newer = (ROOT / "src/cells/processes" / f"{PREFIX}_lifecycle.py").read_text()
    for old, new in (
        ("betse_normal_ecm_event_mechanics as composition", PREFIX + "_sim as composition"),
        (
            "betse_normal_ecm_headless_supplied_SIM_run_v1_5_0@1",
            "betse_normal_ecm_reinitialized_SIM_run_v1_5_0@1",
        ),
        ("cells.normal_ecm_headless_run_inputs@1", "cells.normal_ecm_transitioned_run_inputs@1"),
        ("supplied_component_cold_bootstrap_subset", "supplied_reinitialized_INIT_to_SIM_subset"),
    ):
        newer = newer.replace(new, old)
    assert normalized(ast.parse(previous)) == normalized(ast.parse(newer))
    proofs["entire_existing_SIM_lifecycle_private_binding_and_entry_label_inverse"] = True
    native_sim = ROOT / "validation/betse" / f"{PREFIX}_native_sim.py"
    original_native = PARENT / "validation/betse/betse_normal_ecm_event_mechanics_native.py"
    for name in ("values", "observe", "trace", "field_call", "calcium_call", "rate_cache", "clock"):

        def nested(path, name=name):
            return next(
                n
                for n in ast.walk(fn(path, "evaluate"))
                if isinstance(n, ast.FunctionDef) and n.name == name
            )

        assert normalized(nested(native_sim)) == normalized(nested(original_native)), name
        proofs["native_SIM_literal_nested/" + name] = True
    assert "network.cold(" not in native_sim.read_text()
    proofs["native_SIM_no_cold_recapture"] = True
    files = []
    for directory in ("src/cells/processes", "validation/betse", "tests/unit"):
        files.extend((ROOT / directory).glob("*" + PREFIX + "*.py"))
    allowed = set(dir(builtins)) | {"__file__", "__name__", "__doc__", "__package__", "__spec__"}
    for path in files:
        code = path.read_text()
        tree = ast.parse(code)
        compile(tree, str(path), "exec")
        known = bound_names(tree) | allowed
        table = symtable.symtable(code, str(path), "exec")

        def unresolved(scope, known=known):
            missing = {
                s.get_name()
                for s in scope.get_symbols()
                if s.is_global() and s.is_referenced() and s.get_name() not in known
            }
            for child in scope.get_children():
                missing |= unresolved(child)
            return missing

        assert not unresolved(table), (str(path), unresolved(table))
        for statement in tree.body:
            if isinstance(statement, ast.ImportFrom):
                for alias in statement.names:
                    dependency = module_path(statement.module + "." + alias.name)
                    if dependency is None:
                        continue
                    exported = bound_names(ast.parse(dependency.read_text()))
                    imported = alias.asname or alias.name
                    for node in ast.walk(tree):
                        if (
                            isinstance(node, ast.Attribute)
                            and isinstance(node.value, ast.Name)
                            and node.value.id == imported
                        ):
                            assert node.attr in exported or node.attr.startswith("__"), (
                                str(path),
                                imported,
                                node.attr,
                                str(dependency),
                            )
    proofs["all_new_global_names_and_direct_local_module_attributes_resolve"] = True
    assert not any(
        name.split(".")[0] in {"cells", "betse", "numpy", "scipy", "jax", "jaxlib", "pytest"}
        for name in sys.modules
    )
    result = dict(
        kind="cells.held_INIT_SIM_transition_source_audit@1",
        status="passed",
        proofs=proofs,
        source_sha256={str(p.relative_to(ROOT)): sha(p) for p in sorted(files)},
        parent_manifest_sha256=sha(PARENT.parent / "MANIFEST.json"),
        generated_scientific_source_files=len(generated),
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
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(json.dumps(dict(status="passed", AST_proofs=len(proofs), elapsed_s=result["elapsed_s"])))


if __name__ == "__main__":
    main()
