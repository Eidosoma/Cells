"""Static native-policy/caller/clock audit; execute only stdlib AST builders."""

import ast
import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

ROOT = Path("/home/robert/Cells")
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
PIN = Path("/mnt/workspaces/Cells/betse-v1.5.0")
FIELD = Path("/mnt/workspaces/Cells/betse-normal-ecm-field-join-prepared-20261031-01")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def functions(tree):
    return {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}


def digest(node):
    return hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest()


class Numeric(ast.NodeTransformer):
    def visit_Expr(self, node):
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            return None
        if isinstance(node.value, ast.Call) and ast.unparse(node.value.func) == "observe":
            return None
        return self.generic_visit(node)


def audit():
    original_field = json.loads((FIELD / "inputs.json").read_text())
    for p, h in original_field["owned_sha256"].items():
        assert sha(ROOT / p) == h, p
    proof = json.loads((WORK / "betse_normal_ecm_field_join_AST_witness_01.json").read_text())
    assert (
        proof["inherited_network_literal_scientific_bodies"] == 47
        and proof["complete_native_field_function_count"] == 10
    )
    # Reuse the complete original field builder; no native scientific module is imported.
    native = functions(
        ast.parse((ROOT / "validation/betse/betse_normal_ecm_calcium_join_native.py").read_text())
    )
    ftree = functions(
        ast.parse((ROOT / "validation/betse/betse_environment_field_native.py").read_text())
    )
    ns = dict(ast=ast, copy=copy, hashlib=hashlib)
    exec(
        compile(
            ast.Module(body=[ftree["wrapper"]], type_ignores=[]), "<stdlib AST wrapper>", "exec"
        ),
        ns,
    )
    ns["field_native"] = SimpleNamespace(wrapper=ns["wrapper"])
    exec(
        compile(
            ast.Module(body=[native["calcium_nodes"]], type_ignores=[]),
            "<stdlib CaATP AST builder>",
            "exec",
        ),
        ns,
    )
    nodes, sites = ns["calcium_nodes"](PIN)
    compile(
        ast.fix_missing_locations(ast.Module(body=copy.deepcopy(nodes), type_ignores=[])),
        "<native CaATP compile only>",
        "exec",
    )
    captured = functions(ast.Module(body=nodes, type_ignores=[]))
    sim = ast.parse((PIN / "betse/science/sim.py").read_text())
    methods = functions(
        next(n for n in sim.body if isinstance(n, ast.ClassDef) and n.name == "Simulator")
    )
    tb = functions(ast.parse((PIN / "betse/science/sim_toolbox.py").read_text()))
    for name, original in (
        ("ca_handler", methods["ca_handler"]),
        ("pumpCaATP", tb["pumpCaATP"]),
        ("no_negs", tb["no_negs"]),
    ):
        assert digest(captured[name]) == digest(original), name
    assert len(captured["calcium_cold"].body) == 3 and len(captured["calcium_cold_after"].body) == 1
    cold = captured["calcium_cold"].body
    assert ast.unparse(cold[0]) == "self.met_concs = None"
    assert ast.unparse(cold[1]) == "self.CaATP_block = np.ones(self.mdl)"
    assert ast.unparse(cold[2].test) == "p.ions_dict['Ca'] == 1 and p.Ca_dyn"
    assert ast.unparse(captured["calcium_cold_after"].body[0]) == "self.rho_pump = 1"
    defaults = {ast.unparse(n.targets[0]): n.value for n in captured["calcium_defaults"].body}
    assert ast.literal_eval(defaults["self.Ca_dyn"]) is False
    own = functions(
        ast.parse((ROOT / "src/cells/processes/betse_normal_ecm_calcium_join.py").read_text())
    )
    p = next(n.value for n in ast.walk(own["parameters"]) if isinstance(n, ast.Return))
    port_values = {k.arg: k.value for k in p.keywords}
    for key in ("cATP", "cADP", "cPi", "KmCa_Ca", "KmCa_ATP", "deltaGATP", "F", "R"):
        assert ast.literal_eval(port_values[key]) == ast.literal_eval(defaults["self." + key]), key
    helper = functions(
        ast.parse((ROOT / "src/cells/processes/betse_calcium_atp_source.py").read_text())
    )
    eq = copy.deepcopy(helper["_equations"])
    eq.name = "pumpCaATP"
    eq.args.kwonlyargs = []
    eq.args.kw_defaults = []
    for n in ast.walk(eq):
        if isinstance(n, ast.Name) and n.id == "_no_negs":
            n.id = "no_negs"
    assert digest(Numeric().visit(eq)) == digest(Numeric().visit(copy.deepcopy(tb["pumpCaATP"])))
    clip = copy.deepcopy(helper["_no_negs"])
    clip.name = "no_negs"
    assert digest(Numeric().visit(clip)) == digest(Numeric().visit(copy.deepcopy(tb["no_negs"])))
    previous = functions(
        ast.parse((ROOT / "src/cells/processes/betse_ecm_grn_join.py").read_text())
    )
    inverse = copy.deepcopy(own["_material_step"])
    inverse.name = "material_step"
    inverse.args = copy.deepcopy(previous["material_step"].args)

    class RemoveCalcium(ast.NodeTransformer):
        def visit_Expr(self, node):
            if isinstance(node.value, ast.Call) and (
                ast.unparse(node.value.func) in ("on_calcium", "calcium_equations")
                or ast.unparse(node) == "observe('calcium_handler')"
            ):
                return None
            return self.generic_visit(node)

    inverse = RemoveCalcium().visit(inverse)
    assert digest(inverse) == digest(previous["material_step"])
    chronology = ast.unparse(own["_material_step"])
    assert (
        chronology.index("on_calcium(")
        < chronology.index("fm += forcing.supplied_late_membrane_flux_mol_m2_s")
        < chronology.index("on_network(")
    )
    ref = functions(
        ast.parse(
            (ROOT / "validation/betse/betse_normal_ecm_calcium_join_reference.py").read_text()
        )
    )
    oldref = functions(
        ast.parse((ROOT / "validation/betse/betse_ecm_transport_reference.py").read_text())
    )
    inverse = RemoveCalcium().visit(copy.deepcopy(ref["material_model"]))
    inverse.name = "evaluate"
    assert digest(inverse) == digest(oldref["evaluate"])
    evaluate = ast.unparse(native["evaluate"])
    assert (
        evaluate.index("ca_api['calcium_cold'](sim, cells, parameters)")
        < evaluate.index("cold_cache = network.cold(ctx)")
        < evaluate.index("ca_api['calcium_cold_after'](sim, cells, parameters)")
    )
    loop = next(
        n
        for n in ast.walk(native["evaluate"])
        if isinstance(n, ast.For) and ast.unparse(n.target) == "(index, call)"
    )
    order = [ast.unparse(n) for n in loop.body]
    moving = next(i for i, s in enumerate(order) if s.startswith("source['ordered']("))
    ca = order.index("calcium_result = calcium_call(index)")
    late = next(
        i for i, s in enumerate(order) if s.startswith("sim.fluxes_mem +=") and "supplied_late" in s
    )
    grn = next(i for i, s in enumerate(order) if s.startswith("run_dispatch("))
    commit = order.index("sim.update_all_concs(cells, parameters)")
    fields = order.index("field_result = field_call('field')")
    assert moving < ca < late < grn < commit < fields
    for name in ("run_dispatch",):
        assert "source_time_s" in ast.unparse(own[name]) and "source_time_s" in ast.unparse(
            native[name]
        )
        assert ast.dump(own[name].args, include_attributes=False) == ast.dump(
            native[name].args, include_attributes=False
        )
    clock = ast.unparse(captured["source_clock"])
    assert "phase_time_step_count = phase.p.sim_tsteps" in clock
    assert "np.linspace(0, phase_time_len, phase_time_step_count)" in clock
    assert "float(source_times[index])" in ast.unparse(loop)
    port = ast.unparse(own["calcium"])
    assert "env[i][mapping]" in port and "env[i] =" not in port
    assert "membrane[i] = core.membrane_after_mM" in port
    assert "RateCache(True, ions.freeze(masked))" in port
    assert "RateCache(False, None)" in ast.unparse(own["initialize"])
    assert "after_cold(" in ast.unparse(own["initialize"]) and "calcium_failure" in ast.unparse(
        own["advance"]
    )
    witness = json.loads((WORK / "betse_normal_ecm_calcium_join_reachability_01.json").read_text())
    assert (
        witness["Python_files"] == 332
        and witness["sole_Ca_dyn_value"] is False
        and len(witness["missing_ER_parameter_producers"]) == 8
    )
    return dict(
        kind="cells.normal_ecm_CaATP_field_source_audit@1",
        inherited_network_bodies=47,
        inherited_complete_field_functions=10,
        new_complete_native_CaATP_functions=3,
        native_CaATP_source_blocks=sites,
        original_CaATP_helper_and_negative_clip_AST_equal=True,
        native_parameters_and_default_policy_derived=True,
        native_cold_owner_relative_order_preserved=True,
        material_inverse_AST_equal_except_actual_CaATP_callback=True,
        material_reference_inverse_AST_equal_except_CaATP=True,
        native_ion_CaATP_GeRN_commit_fields_order=True,
        actual_normal_SIM_source_clock=True,
        actual_clock_dispatch_argument_signature_equal=True,
        ECM_fancy_copy_not_written_back=True,
        source_rate_absence_then_actual_cache_carry=True,
        full_field_packet_byte_exact=True,
        prior_field_inputs_sha256=sha(FIELD / "inputs.json"),
        source_ER_disabled_without_forced_flags=True,
        legacy_ER_parameters_not_injected=True,
        scientific_imports=0,
        scientific_AST_executions=0,
        pytest_collection_runs=0,
        numerical_runs=0,
    )


if __name__ == "__main__":
    result = audit()
    path = WORK / "betse_normal_ecm_calcium_join_AST_witness_02.json"
    with path.open("x") as f:
        json.dump(result, f, indent=2, sort_keys=True)
        f.write("\n")
    print(
        json.dumps(
            dict(
                status="static_AST_passed",
                witness=str(path),
                sha256=sha(path),
                scientific_imports=0,
                scientific_AST_executions=0,
            )
        )
    )
