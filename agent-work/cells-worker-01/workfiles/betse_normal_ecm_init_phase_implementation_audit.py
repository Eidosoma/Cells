"""Source-only correspondence and closure checks. No scientific AST is executed."""

import argparse
import ast
import builtins
import copy
import hashlib
import json
import symtable
import sys
from pathlib import Path

ROOT = Path("/home/robert/Cells")
PARENT = Path("/mnt/workspaces/Cells/betse-normal-ecm-run-lifecycle-prepared-20261031-02/source")
NATIVE = Path("/mnt/workspaces/Cells/betse-v1.5.0/betse")
PREFIX = "betse_normal_ecm_init_phase"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fn(path, name, owner=None):
    tree = ast.parse(path.read_text())
    if owner:
        tree = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == owner)
    return copy.deepcopy(
        next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    )


def signature(value):
    value = copy.deepcopy(value)
    # Formatting dedents copied method docstrings when promoted to module scope.
    # Exclude only leading documentation expressions, never runtime statements.
    for node in ast.walk(value):
        if (
            isinstance(node, (ast.FunctionDef, ast.ClassDef))
            and node.body
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)
        ):
            node.body.pop(0)
    return ast.dump(value, include_attributes=False)


def clean_native(node, shuffle=False):
    node = copy.deepcopy(node)
    node.decorator_list = []
    node.returns = None
    for arg in node.args.args:
        arg.annotation = None
    if shuffle:
        node.args.kwonlyargs.append(ast.arg(arg="shuffle"))
        node.args.kw_defaults.append(None)
    return node


def globals_check(path):
    text = path.read_text()
    compile(text, str(path), "exec")
    tree = ast.parse(text)
    module_names = set(dir(builtins)) | {"__file__", "__name__", "__package__", "__spec__"}
    for node in tree.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
            module_names.add(node.name)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            module_names.update(a.asname or a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.Assign):
            module_names.update(
                n.id
                for target in node.targets
                for n in ast.walk(target)
                if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)
            )
    unresolved = set()

    def walk(scope):
        for symbol in scope.get_symbols():
            if (
                symbol.is_global()
                and symbol.is_referenced()
                and symbol.get_name() not in module_names
            ):
                unresolved.add(symbol.get_name())
        for child in scope.get_children():
            walk(child)

    walk(symtable.symtable(text, str(path), "exec"))
    assert not unresolved, (path, sorted(unresolved))
    return dict(
        path=str(path.relative_to(ROOT)), sha256=sha(path), compile=True, unresolved_global_names=[]
    )


def audit():
    proofs = {}
    original = fn(PARENT / "src/cells/processes/betse_normal_ecm_calcium_join.py", "_material_step")
    material = fn(ROOT / "src/cells/processes/betse_normal_ecm_init_phase_material.py", "step_init")
    material.name = original.name
    material.args.kwonlyargs.pop()
    material.args.kw_defaults.pop()
    block = next(
        n
        for n in ast.walk(material)
        if isinstance(n, ast.With)
        and any(
            isinstance(s, ast.If) and ast.unparse(s.test) == "on_network is not None"
            for s in n.body
        )
    )
    i = next(
        i
        for i, n in enumerate(block.body)
        if isinstance(n, ast.Expr) and ast.unparse(n.value).startswith("on_post_network(")
    )
    assert ast.unparse(block.body[i + 1]) == "observe('INIT_post_network')"
    del block.body[i : i + 2]
    assert signature(material) == signature(original)
    proofs["material_exact_inverse"] = (
        "Only post-network callback/receipt and its keyword/name added; all physics/guards exact"
    )
    for newpath, oldpath, qualifier in (
        (
            "src/cells/processes/betse_normal_ecm_init_phase_source.py",
            "src/cells/processes/betse_normal_ecm_catalog_join_source.py",
            "owned",
        ),
        (
            "validation/betse/betse_normal_ecm_init_phase_native.py",
            "validation/betse/betse_normal_ecm_event_join_native.py",
            "independent_native",
        ),
    ):
        original = fn(PARENT / oldpath, "run_dispatch")
        actual = fn(ROOT / newpath, "run_dispatch")
        assert ast.unparse(actual.body[1]) == "ctx.phase.kind = 'INIT'"
        assert ast.unparse(actual.body[2]) == "ctx.p._run_sim = False"
        actual.body.pop(2)
        actual.body[1].value.value = "SIM"
        assert signature(actual) == signature(original)
        proofs[qualifier + "_dispatch_exact_inverse"] = True
    for name in ("_finalize_events_global", "_finalize_events_tissue"):
        original = clean_native(
            fn(NATIVE / "science/tissue/tishandler.py", name, "TissueHandler"),
            shuffle=name == "_finalize_events_global",
        )
        for path in (
            "src/cells/processes/betse_normal_ecm_init_phase_source.py",
            "validation/betse/betse_normal_ecm_init_phase_native_setup.py",
        ):
            assert signature(fn(ROOT / path, name)) == signature(original), (path, name)
    proofs["complete_both_event_finalizers_exact_bodies"] = True
    for path in (
        "src/cells/processes/betse_normal_ecm_init_phase_source.py",
        "validation/betse/betse_normal_ecm_init_phase_native_setup.py",
    ):
        assert signature(fn(ROOT / path, "f_sweep")) == signature(
            clean_native(fn(NATIVE / "science/math/modulate.py", "f_sweep"))
        )
    proofs["complete_source_f_sweep_legacy_guard_retained"] = True
    path = ROOT / "validation/betse/betse_normal_ecm_init_phase_reference_models.py"
    original = fn(
        PARENT / "validation/betse/betse_normal_ecm_event_join_reference.py", "channel_sequence"
    )
    actual = fn(path, "channel_sequence")
    loop = next(
        n
        for n in ast.walk(actual)
        if isinstance(n, ast.For)
        and ast.unparse(n.target) == "row"
        and "inputs['catalog']['populations']" in ast.unparse(n.iter)
    )
    assert ast.unparse(loop.body[0]) == "if row.get('init active', True) is False:\n    continue"
    loop.body.pop(0)
    assert signature(actual) == signature(original)
    assert signature(fn(path, "material_model")) == signature(
        fn(PARENT / "validation/betse/betse_normal_ecm_catalog_join_reference.py", "material_model")
    )
    proofs["channel_reference_active_guard_only_exact_inverse"] = True
    proofs["material_reference_function_exact_AST"] = True
    native_setup = ROOT / "validation/betse/betse_normal_ecm_init_phase_native_setup.py"
    assert signature(fn(native_setup, "pumpNaKATP")) == signature(
        fn(NATIVE / "science/sim_toolbox.py", "pumpNaKATP")
    )
    proofs["native_full_NaK_helper_exact_AST"] = True
    loop = next(
        n
        for n in fn(NATIVE / "science/sim.py", "_run_sim_core_loop", "Simulator").body
        if isinstance(n, ast.For)
    )
    first = next(
        i
        for i, n in enumerate(loop.body)
        if isinstance(n, ast.If) and ast.unparse(n.test) == "p.alpha_NaK == 0.0"
    )
    assert [signature(n) for n in fn(native_setup, "nak_call").body] == [
        signature(n) for n in loop.body[first : first + 2]
    ]
    proofs["native_NaK_call_and_masks_exact_slices"] = True
    init = fn(NATIVE / "science/sim.py", "init_dynamics", "Simulator")
    start = next(
        i
        for i, n in enumerate(init.body)
        if isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) == "Dm_cellsA"
    )
    end = next(
        i
        for i, n in enumerate(init.body)
        if isinstance(n, ast.If) and ast.unparse(n.test) == "p.ions_dict['Ca'] == 1 and p.Ca_dyn"
    )
    static = fn(native_setup, "static_and_blocks")

    class Inverse(ast.NodeTransformer):
        def visit_Attribute(self, node):
            if ast.unparse(node) == "rng.random":
                return ast.parse("np.random.random", mode="eval").body
            return self.generic_visit(node)

    static = Inverse().visit(static)
    assert [signature(n) for n in static.body] == [signature(n) for n in init.body[start : end + 1]]
    proofs["native_static_setup_and_blocks_exact_inverse"] = "Only local RNG injection"
    for name in ("values", "observe", "trace", "field_call", "calcium_call", "rate_cache", "clock"):

        def nested(file, name=name):
            return next(
                n
                for n in ast.walk(fn(file, "evaluate"))
                if isinstance(n, ast.FunctionDef) and n.name == name
            )

        assert signature(
            nested(ROOT / "validation/betse/betse_normal_ecm_init_phase_native.py")
        ) == signature(
            nested(PARENT / "validation/betse/betse_normal_ecm_event_mechanics_native.py")
        ), name
    proofs["native_full_material_CaATP_field_trace_functions_exact_AST"] = True
    product = fn(ROOT / "src/cells/processes/betse_normal_ecm_init_phase.py", "advance")
    text = ast.unparse(product)
    assert "event_owner" not in text and "protein_noise(" not in text and "fire_events(" not in text
    assert (
        text.index("pump.produce(")
        < text.index("material_init.step_init(")
        < text.index("full.reconstruct(")
    )
    assert "on_post_network=on_post_network" in text
    proofs["separate_INIT_no_SIM_event_or_noise_execution"] = True
    tree = ast.parse(
        (ROOT / "validation/betse/betse_normal_ecm_init_phase_fixtures.py").read_text()
    )
    constants = {
        n.targets[0].id: ast.literal_eval(n.value)
        for n in tree.body
        if isinstance(n, ast.Assign)
        and isinstance(n.targets[0], ast.Name)
        and n.targets[0].id in {"CASES", "RAW_CASES", "DEPENDENCIES", "OBSERVER_CASES"}
    }
    for name, values in constants.items():
        assert len(set(values)) == len(values), name
    calls = sum(0 if c == "zero_calls" else 1 if c == "one_call" else 3 for c in constants["CASES"])
    files = []
    for directory in (
        ROOT / "src/cells/processes",
        ROOT / "validation/betse",
        ROOT / "tests/unit",
        ROOT / "agent-work/cells-worker-01/workfiles",
    ):
        for path in sorted(directory.glob("*" + PREFIX + "*.py")):
            # The old design-only audit is frozen evidence, not implementation.
            if path.name == PREFIX + "_audit.py":
                continue
            files.append(globals_check(path))
    assert not any(
        name.split(".")[0] in {"cells", "betse", "numpy", "scipy", "jax", "jaxlib"}
        for name in sys.modules
    )
    return dict(
        kind="cells.INIT_implementation_static_audit@1",
        status="passed",
        proofs=proofs,
        files=files,
        AST_normalization=(
            "Ignore source locations and leading documentation strings only; "
            "copied method docstrings were dedented by Ruff"
        ),
        prospective=dict(
            positive_cases=len(constants["CASES"]),
            raw_cases=len(constants["RAW_CASES"]),
            dependency_cases=len(constants["DEPENDENCIES"]),
            observer_cases=len(constants["OBSERVER_CASES"]),
            accepted_calls=calls,
            fresh_reference_forms=6 * len(constants["CASES"]) + 14 * calls,
            native_captures=len(constants["CASES"])
            + len(constants["RAW_CASES"])
            + len(constants["OBSERVER_CASES"]),
            total_tests=sum(len(v) for v in constants.values()),
        ),
        scientific_imports=0,
        scientific_AST_executions=0,
        model_fixture_reference_evaluations=0,
        pytest_collections=0,
        numerical_runs=0,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit()
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(
        json.dumps(
            dict(
                status=result["status"],
                proofs=len(result["proofs"]),
                files=len(result["files"]),
                prospective=result["prospective"],
            )
        )
    )


if __name__ == "__main__":
    main()
