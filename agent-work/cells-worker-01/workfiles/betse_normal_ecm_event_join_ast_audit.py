"""Static literal event/noise/reset/material lowering audit, never science."""

import ast
import builtins
import copy
import hashlib
import json
import symtable
from pathlib import Path

ROOT = Path("/home/robert/Cells")
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
PIN = Path("/mnt/workspaces/Cells/betse-v1.5.0/betse")
PREFIX = "betse_normal_ecm_event_join"


def digest(node):
    return hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest()


def funcs(tree):
    return {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}


def classes(tree):
    return {n.name: n for n in tree.body if isinstance(n, ast.ClassDef)}


class Numeric(ast.NodeTransformer):
    def visit_Expr(self, node):
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            return None
        if isinstance(node.value, ast.Call) and ast.unparse(node.value.func) == "self._observe":
            return None
        return self.generic_visit(node)

    def visit_FunctionDef(self, node):
        node.decorator_list = []
        node.returns = None
        for arg in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs):
            arg.annotation = None
        return self.generic_visit(node)


def audit():
    st = ast.parse((ROOT / "src/cells/processes" / f"{PREFIX}_source.py").read_text())
    sf = funcs(st)
    sc = classes(st)
    handlers = classes(ast.parse((PIN / "science/tissue/tishandler.py").read_text()))
    volt = classes(ast.parse((PIN / "science/tissue/event/tisevevolt.py").read_text()))
    source_bodies = {}
    for cls, names in (
        (
            "TissueHandler",
            ("fire_events", "_fire_events_global", "_fire_events_tissue", "makeAllChanges"),
        ),
        ("SimEventPulseVoltage", ("fire",)),
    ):
        originals = handlers[cls] if cls == "TissueHandler" else volt[cls]
        for name in names:
            original = funcs(originals)[name]
            ported = funcs(sc[cls])[name]
            assert digest(Numeric().visit(copy.deepcopy(original))) == digest(
                Numeric().visit(copy.deepcopy(ported))
            ), (cls, name)
            source_bodies[cls + "." + name] = dict(
                original_AST_sha256=digest(original),
                port_AST_sha256=digest(ported),
                first_line=original.lineno,
                last_line=original.end_lineno,
            )
    tb = funcs(ast.parse((PIN / "science/math/toolbox.py").read_text()))
    assert digest(Numeric().visit(copy.deepcopy(tb["pulse"]))) == digest(sf["pulse"])
    simulator = classes(ast.parse((PIN / "science/sim.py").read_text()))["Simulator"]
    methods = funcs(simulator)
    loop = next(n for n in methods["_run_sim_core_loop"].body if isinstance(n, ast.For))
    guard = next(
        n for n in loop.body if isinstance(n, ast.If) and "phase.dyna.fire_events" in ast.unparse(n)
    )
    assert digest(sf["fire_events_guarded"].body[0]) == digest(guard)
    resets = [
        copy.deepcopy(n)
        for n in loop.body
        if isinstance(n, ast.Expr)
        and ast.unparse(n) in ("self.fluxes_mem.fill(0)", "self.fluxes_gj.fill(0)")
        or isinstance(n, ast.If)
        and ast.unparse(n.test) == "p.is_ecm"
        and "self.fluxes_env_x =" in ast.unparse(n)
    ]
    assert [digest(n) for n in resets] == [digest(n) for n in sf["reset_fluxes"].body]
    original_noise = next(
        n
        for n in loop.body
        if isinstance(n, ast.If) and "p.dynamic_noise == 1" in ast.unparse(n.test)
    )
    noise = copy.deepcopy(sf["protein_noise"].body[0])
    count = 0

    class UndoRandom(ast.NodeTransformer):
        def visit_Call(self, node):
            nonlocal count
            if ast.unparse(node.func) == "p._native_random":
                node.func = ast.parse("np.random.random", mode="eval").body
                count += 1
            return self.generic_visit(node)

    assert digest(UndoRandom().visit(noise)) == digest(original_noise) and count == 1
    old = funcs(
        ast.parse((ROOT / "src/cells/processes/betse_normal_ecm_calcium_join.py").read_text())
    )["_material_step"]
    material = funcs(
        ast.parse((ROOT / "src/cells/processes" / f"{PREFIX}_material.py").read_text())
    )["step_after_events"]
    initial_clear = []
    for n in ast.walk(old):
        if isinstance(n, ast.Expr) and ast.unparse(n) in ("fm.fill(0)", "fg.fill(0)"):
            initial_clear.append(copy.deepcopy(n))
        if isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) == "(fx_all, fy_all)":
            initial_clear.append(copy.deepcopy(n))
    initial_clear.sort(key=lambda n: n.lineno)
    assert len(initial_clear) == 3
    restored = copy.deepcopy(material)
    restored.name = old.name
    restored.args = copy.deepcopy(old.args)

    class InverseMaterial(ast.NodeTransformer):
        def visit_Expr(self, node):
            if isinstance(node.value, ast.Call) and ast.unparse(node.value.func) == "on_noise":
                return None
            if ast.unparse(node) == "observe('protein_noise')":
                return None
            if ast.unparse(node) == "observe('initial')":
                return [node, *copy.deepcopy(initial_clear)]
            return self.generic_visit(node)

    assert digest(InverseMaterial().visit(restored)) == digest(old)
    main = funcs(ast.parse((ROOT / "src/cells/processes" / f"{PREFIX}.py").read_text()))
    lowering = ast.unparse(main["runtime_material"])
    assert (
        lowering.count("definition['ions']") == 2
        and "lowered = material.bind(definition)" in lowering
    )
    assert (
        "lowered.geometry_binding.identity != binding.material_binding.geometry_binding.identity"
        in lowering
    )
    advance = ast.unparse(main["advance"])
    assert (
        advance.index("events.reset_fluxes(")
        < advance.index("event = events.fire(")
        < advance.index("runtime_material(binding, stores)")
        < advance.index("event_material.step_after_events(")
        < advance.index("full.reconstruct(")
    )
    on_network = next(
        n
        for n in ast.walk(main["advance"])
        if isinstance(n, ast.FunctionDef) and n.name == "on_network"
    )
    text = ast.unparse(on_network)
    assert (
        text.index("source.restore(")
        < text.index("events.install_owner(")
        < text.index("source.run_dispatch(")
    )
    assert (
        "prospective_draw_is_uncommitted" in advance and "Actual post-GRN draw differs" in advance
    )
    assert "if key != 'ctx'" in advance and "missing_event_stores" in advance
    # Validate helper keyword names statically, avoiding the earlier scaffold API guess.
    time = funcs(ast.parse((ROOT / "src/cells/processes/betse_time_modulation.py").read_text()))
    for call in ast.walk(sf["prepared_callback"]):
        if (
            isinstance(call, ast.Call)
            and isinstance(call.func, ast.Attribute)
            and isinstance(call.func.value, ast.Name)
            and call.func.value.id == "time_laws"
        ):
            signature = time[call.func.attr].args
            allowed = {a.arg for a in signature.args + signature.kwonlyargs}
            assert {k.arg for k in call.keywords} <= allowed, (call.func.attr, allowed)
    for p in sorted((ROOT / "src/cells/processes").glob(PREFIX + "*.py")):
        text = p.read_text()
        compile(text, str(p), "exec")
        table = symtable.symtable(text, str(p), "exec")
        known = set(table.get_identifiers()) | set(dir(builtins)) | {"__file__", "__name__"}

        def missing(scope, known=known):
            out = {
                s.get_name()
                for s in scope.get_symbols()
                if s.is_global() and s.is_referenced() and s.get_name() not in known
            }
            for child in scope.get_children():
                out |= missing(child)
            return out

        assert not missing(table), (p, missing(table))
    native_path = ROOT / "validation/betse" / f"{PREFIX}_native_events.py"
    native_tree = ast.parse(native_path.read_text())
    selected = [
        n
        for n in native_tree.body
        if isinstance(n, (ast.ClassDef, ast.FunctionDef)) and n.name in ("Clean", "literal_nodes")
    ]
    assert len(selected) == 2
    namespace = dict(ast=ast, copy=copy)
    # Execute only these stdlib AST builders; never execute returned scientific AST.
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(native_path), "exec"), namespace)
    native_nodes = namespace["literal_nodes"](PIN)
    native_functions, native_classes = (
        funcs(ast.Module(body=native_nodes)),
        classes(ast.Module(body=native_nodes)),
    )
    assert digest(native_functions["protein_noise"].body[0]) == digest(original_noise)
    assert "np.random.random" in ast.unparse(native_functions["protein_noise"])
    assert "p._native_random" not in ast.unparse(native_functions["protein_noise"])
    for cls, names in (
        (
            "TissueHandler",
            ("fire_events", "_fire_events_global", "_fire_events_tissue", "makeAllChanges"),
        ),
        ("SimEventPulseVoltage", ("fire",)),
    ):
        for name in names:
            assert digest(
                Numeric().visit(copy.deepcopy(funcs(native_classes[cls])[name]))
            ) == digest(Numeric().visit(copy.deepcopy(funcs(sc[cls])[name])))
    old_native = funcs(
        ast.parse((ROOT / "validation/betse/betse_normal_ecm_catalog_join_native.py").read_text())
    )
    new_native = funcs(ast.parse((ROOT / "validation/betse" / f"{PREFIX}_native.py").read_text()))
    for name in ("field_nodes", "calcium_nodes", "capture", "run_dispatch"):
        assert digest(old_native[name]) == digest(new_native[name]), name
    native_eval = ast.unparse(new_native["evaluate"])
    order = [
        "source['resets'](",
        "event_result = event_owner.fire(",
        "calcium_result = calcium_call(",
        "run_dispatch(",
        "noise_result = event_owner.noise(",
        "sim.update_all_concs(",
    ]
    positions = [native_eval.index(text) for text in order]
    assert positions == sorted(positions)
    reference = funcs(ast.parse((ROOT / "validation/betse" / f"{PREFIX}_reference.py").read_text()))
    old_reference = funcs(
        ast.parse(
            (ROOT / "validation/betse/betse_normal_ecm_catalog_join_reference.py").read_text()
        )
    )
    for name in set(old_reference) - {"evaluate", "material_model", "channel_sequence"}:
        assert digest(reference[name]) == digest(old_reference[name]), name

    class UndoRho(ast.NodeTransformer):
        def visit_Call(self, node):
            if ast.unparse(node.func) == "control_at":
                assert len(node.args) == 2
                return ast.Subscript(value=node.args[0], slice=node.args[1], ctx=ast.Load())
            return self.generic_visit(node)

    assert digest(UndoRho().visit(copy.deepcopy(reference["channel_sequence"]))) == digest(
        old_reference["channel_sequence"]
    )
    old_model = old_reference["material_model"]
    clear_loop = next(
        n
        for n in ast.walk(old_model)
        if isinstance(n, ast.For) and ast.unparse(n.target) == "(key, count)"
    )

    class UndoReferenceNoise(ast.NodeTransformer):
        def visit_Assign(self, node):
            if [ast.unparse(t) for t in node.targets] == ["noise_result"]:
                return None
            return self.generic_visit(node)

        def visit_Expr(self, node):
            if ast.unparse(node) == "observe('protein_noise')":
                return None
            if ast.unparse(node) == "observe('initial')":
                return [node, copy.deepcopy(clear_loop)]
            return self.generic_visit(node)

        def visit_Call(self, node):
            node.keywords = [k for k in node.keywords if k.arg != "noise_reference"]
            return self.generic_visit(node)

    assert digest(UndoReferenceNoise().visit(copy.deepcopy(reference["material_model"]))) == digest(
        old_model
    )
    return dict(
        kind="cells.normal_ecm_event_owned_adapter_AST_audit@1",
        source_bodies=source_bodies,
        literal_event_firer_and_voltage_bodies=5,
        original_pulse_equal=True,
        original_reset_and_SIM_guard_equal=True,
        original_noise_guard_body_equal_except_explicit_draw_interface=True,
        noise_draw_interface_replacements=1,
        material_inverse_exact=True,
        relocated_reset_statements=3,
        relocated_reset_buffer_effects=4,
        actual_reset_before_event_and_post_event_material=True,
        post_GRN_noise_hook_before_commit=True,
        legitimate_runtime_material_binding_lowering=True,
        fixed_geometry_identity_checked=True,
        prior_cache_restored_before_reapplying_earlier_event_writes=True,
        opaque_contexts_excluded_from_failure_serialization=True,
        uncommitted_noise_preview_separate_from_actual_draw=True,
        temporal_helper_keyword_interfaces_valid=True,
        compile_and_global_names_pass=True,
        independent_native_original_noise_AST_equal=True,
        independent_native_firer_AST_equal=True,
        native_field_CaATP_capture_and_dispatch_functions_unchanged=True,
        native_reset_event_CaATP_GRN_noise_commit_order=True,
        scalar_channel_reference_inverse_exact=True,
        reference_material_noise_insertion_inverse_exact=True,
        reference_CaATP_and_other_catalog_scalar_functions_unchanged=True,
        status="static_source_correspondence_passed_no_numerics",
        scientific_imports=0,
        scientific_AST_executions=0,
        fixture_evaluations=0,
        pytest_collection_runs=0,
        numerical_runs=0,
    )


if __name__ == "__main__":
    result = audit()
    with (WORK / f"{PREFIX}_AST_witness_02.json").open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({k: v for k, v in result.items() if k != "source_bodies"}, sort_keys=True))
