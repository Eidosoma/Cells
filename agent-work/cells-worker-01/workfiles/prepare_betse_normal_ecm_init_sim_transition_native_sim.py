"""Write a private native SIM conditional evaluator; never execute source AST."""
# ruff: noqa: E501 -- embedded source templates.

import ast
import copy
from pathlib import Path

ROOT = Path("/home/robert/Cells")
PARENT = Path("/mnt/workspaces/Cells/betse-normal-ecm-init-phase-prepared-20261031-02/source")
PREFIX = "betse_normal_ecm_init_sim_transition"


def nodes(text):
    return ast.parse(text).body


def main():
    tree = ast.parse(
        (PARENT / "validation/betse/betse_normal_ecm_event_mechanics_native.py").read_text()
    )
    evaluation = next(
        n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "evaluate"
    )
    assert ast.unparse(evaluation.body[0]) == "composition = declared"
    evaluation.body[:1] = nodes("conditional = declared\ncomposition = conditional['composition']")
    for statement in list(evaluation.body):
        if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call):
            if ast.unparse(statement.value.func) in {
                "ca_api['calcium_cold']",
                "ca_api['calcium_cold_after']",
            }:
                evaluation.body.remove(statement)
    cold = next(n for n in evaluation.body if isinstance(n, ast.Try))
    assert ast.unparse(cold.body[0]) == "cold_cache = network.cold(ctx)"
    position = evaluation.body.index(cold)
    evaluation.body[position : position + 1] = nodes("""
for key, value in arrays(conditional['simulator_fields']).items():
    setattr(sim, key, value)
network.restore(ctx, arrays(conditional['entry_cache']))
cold_cache = network.cache(ctx)
nak_source.nak_defaults(parameters)
parameters.alpha_NaK = conditional['alpha_NaK']
parameters._run_sim = True
nak_owner = SimpleNamespace(ctx=ctx, declaration=dict(field=inputs), nak_history=[])
""")
    # Use the actual new SIM total. The original native clock body still builds
    # the three linspace source labels; no index or endpoint is rebased.
    position = next(
        i
        for i, n in enumerate(evaluation.body)
        if isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) == "parameters.sim_tsteps"
    )
    evaluation.body[position:position] = nodes(
        "parameters.sim_time_total = conditional['sim_total_s']"
    )
    loop = next(
        n
        for n in ast.walk(evaluation)
        if isinstance(n, ast.For) and ast.unparse(n.target) == "(index, call)"
    )
    packet = next(
        n for n in loop.body if isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) == "packet"
    )
    position = loop.body.index(packet)
    loop.body[position:position] = nodes("""
nak_owner.declaration = dict(field=dict(inputs, definition=runtime_definition))
nak_result = sim_pump(nak_owner, values)
""")
    packet.value.keywords.append(
        ast.keyword(
            arg="supplied_pump_membrane_flux_mol_m2_s",
            value=ast.parse("nak_result['applied_flux'].copy()", mode="eval").body,
        )
    )
    material_before = next(
        n
        for n in loop.body
        if isinstance(n, ast.Assign)
        and ast.unparse(n.targets[0]) == "material_before"
        and isinstance(n.value, ast.Call)
    )
    material_before.value.keywords.append(
        ast.keyword(
            arg="nak_before",
            value=ast.parse("network.clone(nak_result['before'])", mode="eval").body,
        )
    )
    next(k for k in material_before.value.keywords if k.arg == "initial").value = ast.parse(
        "network.clone(nak_result['before']['values_before'])", mode="eval"
    ).body
    for stage in ("initial", "reset_flux"):
        observed = next(
            n
            for n in loop.body
            if isinstance(n, ast.Expr)
            and isinstance(n.value, ast.Call)
            and ast.unparse(n.value.func) == "observe"
            and n.value.args[0].value == stage
        )
        loop.body[loop.body.index(observed)] = nodes(
            "frames.append(dict(stage="
            + repr(stage)
            + ",ion_id=None,values=network.clone(nak_result['before']['values_before'])))"
        )[0]
    applied = next(
        n
        for n in loop.body
        if isinstance(n, ast.AugAssign) and "supplied_pump_membrane_flux_mol_m2_s" in ast.unparse(n)
    )
    loop.body.remove(applied)  # Actual native nak_call already wrote this flux once.
    history = next(
        n
        for n in ast.walk(loop)
        if isinstance(n, ast.Call)
        and ast.unparse(n.func) == "dict"
        and any(k.arg == "source_completed" for k in n.keywords)
    )
    history.keywords.append(ast.keyword(arg="nak", value=ast.Name(id="nak_result", ctx=ast.Load())))
    history.keywords.append(
        ast.keyword(
            arg="nak_rate_after",
            value=ast.parse(
                "dict(present=hasattr(sim,'rate_NaKATP'),value=network.clone(getattr(sim,'rate_NaKATP',None)))",
                mode="eval",
            ).body,
        )
    )
    # Capture unexpected pre-loop and bootstrap failures through the reviewed
    # INIT02 helper, before any fragile old failure-summary reader is reached.
    inner = next(
        n
        for n in ast.walk(evaluation)
        if isinstance(n, ast.Try)
        and any(
            isinstance(s, ast.Expr)
            and isinstance(s.value, ast.Call)
            and ast.unparse(s.value.func) == "field_call"
            for s in n.body
        )
    )
    inner.handlers[0].body[:0] = nodes("if field_phase in ('bootstrap', 'events'):\n    raise")
    with_index = next(i for i, n in enumerate(evaluation.body) if isinstance(n, ast.With))
    evaluation.body[with_index:with_index] = nodes("field_phase = 'bootstrap'")
    returned = next(n for n in reversed(evaluation.body) if isinstance(n, ast.Return))
    next(k for k in returned.value.keywords if k.arg == "seams").value = ast.Constant(
        "Actual NaK before ion loop; supplied late flux absent; fixed-gap source branch; "
        "source reconstructed field feedback; explicit external flow/bath/boundary"
    )
    returned.value.keywords.extend(
        [
            ast.keyword(arg="source_cold_recapture", value=ast.Constant(False)),
            ast.keyword(arg="independent_INIT_trajectory", value=ast.Constant(False)),
            ast.keyword(arg="whole_native_phase_completed", value=ast.Constant(False)),
        ]
    )
    evaluation.args.kwonlyargs.append(ast.arg(arg="retain_failure"))
    evaluation.args.kw_defaults.append(ast.Constant(None))
    outer = nodes("""
try:
    pass
except Exception as error:
    readers = _failure_readers(locals(), error)
    readers['conditional_entry'] = lambda: conditional
    capture_evidence.record_failure(error, stage=field_phase or 'native_SIM_preparation', readers=readers, retain=retain_failure)
    raise
finally:
    sys.settrace(capture_previous_trace)
""")[0]
    outer.body = evaluation.body
    evaluation.body = nodes(
        "capture_previous_trace = sys.gettrace()\nfield_phase = 'native_SIM_preparation'\nconditional = declared"
    ) + [outer]
    init_tree = ast.parse(
        (PARENT / "validation/betse/betse_normal_ecm_init_phase_native.py").read_text()
    )
    main_function = next(
        n for n in init_tree.body if isinstance(n, ast.FunctionDef) and n.name == "main"
    )
    original_main = next(
        n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main"
    )
    tree.body[tree.body.index(original_main)] = copy.deepcopy(main_function)
    original_setup = ast.parse(
        (PARENT / "validation/betse/betse_normal_ecm_init_phase_native_setup.py").read_text()
    )
    owner = next(
        n for n in original_setup.body if isinstance(n, ast.ClassDef) and n.name == "Owner"
    )
    pump = copy.deepcopy(
        next(n for n in owner.body if isinstance(n, ast.FunctionDef) and n.name == "pump")
    )
    pump.name = "sim_pump"
    for node in ast.walk(pump):
        if isinstance(node, ast.keyword) and node.arg == "source_phase":
            assert node.value.value == "INIT"
            node.value = ast.Constant("SIM")
        if isinstance(node, ast.keyword) and node.arg == "legacy_run_sim":
            assert node.value.value is False
            node.value = ast.Constant(True)
    tree.body.insert(tree.body.index(evaluation), pump)

    class RenameEntry(ast.NodeTransformer):
        def visit_Name(self, node):
            if node.id.startswith("cold_"):
                node.id = "entry_" + node.id[5:]
            return node

        def visit_keyword(self, node):
            if node.arg and node.arg.startswith("cold_"):
                node.arg = "entry_" + node.arg[5:]
            return self.generic_visit(node)

    tree = RenameEntry().visit(tree)
    tree.body[0] = nodes(
        '"""Native SIM conditionals from actual post-reinitialize/clear entry; no cold recapture."""'
    )[0]
    insertion = next(i for i, n in enumerate(tree.body) if isinstance(n, ast.FunctionDef))
    tree.body[insertion:insertion] = nodes("""
from validation.betse import betse_normal_ecm_init_phase_capture as capture_evidence
from validation.betse import betse_normal_ecm_init_phase_native_setup as nak_source
from validation.betse.betse_normal_ecm_init_phase_native import _failure_readers
from validation.betse.betse_normal_ecm_init_sim_transition_native import arrays
pumpNaKATP = nak_source.pumpNaKATP
nak_call = nak_source.nak_call
""")
    output = ROOT / "validation/betse" / (PREFIX + "_native_sim.py")
    with output.open("x") as stream:
        stream.write("# ruff: noqa: F841\n" + ast.unparse(ast.fix_missing_locations(tree)) + "\n")
    compile(output.read_text(), str(output), "exec")
    print(str(output))


if __name__ == "__main__":
    main()
