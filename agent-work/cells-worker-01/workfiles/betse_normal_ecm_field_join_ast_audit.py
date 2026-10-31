"""Literal source and composition audit; execute AST builders, never science."""

import ast
import copy
import hashlib
import json
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace

ROOT = Path("/home/robert/Cells")
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
PIN = Path("/mnt/workspaces/Cells/betse-v1.5.0")
ACCEPTED = Path("/mnt/workspaces/Cells/betse-ecm-grn-prepared-20261031-02")


def funcs(tree):
    return {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}


def digest(node):
    return hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit():
    accepted = json.loads((ACCEPTED / "inputs.json").read_text())
    # The shared material module now has a separately requested diagnostic.
    # Authenticate the inherited join against its actual accepted baseline;
    # never present the modified standalone material packet as rerun/accepted.
    baseline = "src/cells/processes/betse_ecm_transport.py"
    frozen = ACCEPTED / "source" / baseline
    assert sha(frozen) == accepted["source_hashes"][baseline]
    oldtree = ast.parse((WORK / "betse_ecm_grn_ast_audit.py").read_text())
    replacements = 0
    for node in ast.walk(oldtree):
        if isinstance(node, ast.Constant) and node.value == baseline:
            node.value = str(frozen)
            replacements += 1
    assert replacements == 1
    oldns = dict(__name__="inherited_ecm_static_only")
    exec(compile(ast.fix_missing_locations(oldtree), "<stdlib inherited ECM audit>", "exec"), oldns)
    inherited = oldns["audit"]()
    assert inherited["literal_scientific_body_count"] == 47
    reused = (
        "src/cells/processes/betse_ecm_grn_join.py",
        "src/cells/processes/betse_ecm_grn_source.py",
        "validation/betse/betse_ecm_grn_native.py",
        "validation/betse/betse_ecm_grn_native_network.py",
    )
    for relative in reused:
        assert sha(ROOT / relative) == accepted["source_hashes"][relative], relative

    fieldpath = ROOT / "validation/betse/betse_environment_field_native.py"
    ftree = ast.parse(fieldpath.read_text())
    definitions = funcs(ftree)
    # Stop before creation or execution of a NumPy scientific namespace.
    builder = copy.deepcopy(definitions["capture"])
    stop = next(
        i
        for i, n in enumerate(builder.body)
        if isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) == "namespace"
    )
    builder.body = builder.body[:stop] + ast.parse("return module, blocks, original_functions").body
    ns = dict(
        ast=ast,
        copy=copy,
        hashlib=hashlib,
        json=json,
        os=os,
        subprocess=subprocess,
        Path=Path,
        PROTOCOL=fieldpath.with_name("betse_environment_field_protocol.json"),
    )
    exec(
        compile(
            ast.fix_missing_locations(
                ast.Module(body=[definitions["wrapper"], builder], type_ignores=[])
            ),
            "<stdlib original geometry/field AST builder>",
            "exec",
        ),
        ns,
    )
    base, blocks, originals = ns["capture"]()
    compile(ast.fix_missing_locations(copy.deepcopy(base)), "<field AST compile only>", "exec")
    nativepath = ROOT / "validation/betse/betse_normal_ecm_field_join_native.py"
    native = funcs(ast.parse(nativepath.read_text()))
    ns2 = dict(
        ast=ast, copy=copy, hashlib=hashlib, field_native=SimpleNamespace(wrapper=ns["wrapper"])
    )
    exec(
        compile(
            ast.Module(body=[native["field_nodes"]], type_ignores=[]),
            "<stdlib full suffix AST builder>",
            "exec",
        ),
        ns2,
    )
    extra, sites = ns2["field_nodes"](PIN)
    compile(
        ast.fix_missing_locations(ast.Module(body=copy.deepcopy(extra), type_ignores=[])),
        "<suffix compile only>",
        "exec",
    )
    sim = ast.parse((PIN / "betse/science/sim.py").read_text())
    methods = funcs(
        next(n for n in sim.body if isinstance(n, ast.ClassDef) and n.name == "Simulator")
    )
    tb = funcs(ast.parse((PIN / "betse/science/sim_toolbox.py").read_text()))
    full = funcs(ast.Module(body=extra, type_ignores=[]))
    assert digest(full["update_V"]) == digest(methods["update_V"])
    assert digest(full["check_v"]) == digest(tb["check_v"])
    calls = [ast.unparse(n) for n in full["normal_field"].body]
    assert calls == ["self.update_V(cells, p)", "stb.check_v(self.vm)"]
    assert [ast.unparse(n) for n in full["bootstrap_field"].body] == [
        "self.update_V(phase.cells, phase.p)"
    ]
    assert ast.unparse(full["diviterm"].body[0]) == "self.diviterm = self.cell_vol / self.cell_sa"
    assert "np.isnan(vm)" in ast.unparse(full["check_v"]) and "isfinite" not in ast.unparse(
        full["check_v"]
    )
    original_proof = {n.name: digest(n) for n in originals}
    cls = next(n for n in base.body if isinstance(n, ast.ClassDef))
    original_proof.update({"FiniteDiffSolver." + k: digest(n) for k, n in funcs(cls).items()})
    original_proof.update({k: digest(full[k]) for k in ("update_V", "check_v")})
    assert len(original_proof) == 10
    capture = ast.unparse(native["capture"])
    assert "previous.capture()" in capture and "field_nodes(root)" in capture
    assert "geometry['get_current'] =" not in capture
    evaluate = ast.unparse(native["evaluate"])
    assert "geometry_code['caches'](sim, parameters)" in evaluate
    assert "live_cells, live_env = (sim.cc_cells, sim.cc_env)" in evaluate
    assert "post_material_cache = (values(), network.cache(ctx))" in evaluate
    loop = next(
        n
        for n in ast.walk(native["evaluate"])
        if isinstance(n, ast.For) and ast.unparse(n.target) == "(index, call)"
    )
    sequence = [ast.unparse(n) for n in loop.body]
    run = next(i for i, s in enumerate(sequence) if s.startswith("network.run_dispatch("))
    commit = sequence.index("sim.update_all_concs(cells, parameters)")
    field = next(i for i, s in enumerate(sequence) if "field_result = field_call('field')" in s)
    assert run < commit < field
    assert "('electric_x_source', 'E_env_x')" not in ast.unparse(loop)
    assert "sim.E_env_x.copy()" in ast.unparse(loop)

    own = funcs(
        ast.parse((ROOT / "src/cells/processes/betse_normal_ecm_field_join.py").read_text())
    )
    prior = funcs(ast.parse((ROOT / "src/cells/processes/betse_ecm_grn_join.py").read_text()))
    inverse = copy.deepcopy(own["advance_material"])
    inverse.name = "advance"
    inverse.args = copy.deepcopy(prior["advance"].args)
    changed = 0
    for node in ast.walk(inverse):
        if isinstance(node, ast.FunctionDef) and node.name == "failed":
            node.body = copy.deepcopy(
                next(
                    n
                    for n in ast.walk(prior["advance"])
                    if isinstance(n, ast.FunctionDef) and n.name == "failed"
                ).body
            )
            changed += 1
        if isinstance(node, ast.Call) and ast.unparse(node.func) == "material.drive":
            node.args[1].keywords = [
                k
                for k in node.args[1].keywords
                if k.arg not in ("electric_x_source", "electric_y_source")
            ]
            changed += 1
    assert changed == 2 and digest(inverse) == digest(prior["advance"])
    code = ast.unparse(own["advance"])
    assert (
        code.index("advance_material(")
        < code.index("after_material(candidate, trial, feedback)")
        < code.index("reconstruct(")
    )
    code = ast.unparse(own["initialize"])
    assert (
        code.index("source.cold(") < code.index("after_cold(initial)") < code.index("reconstruct(")
    )
    assert "raw['voltage_V'] = vm.values.voltage_V" in ast.unparse(own["reconstruct"])
    assert "junction_voltage_V" not in ast.unparse(own["reconstruct"])
    vf = ast.unparse(own["voltage_definition"])
    for needed in (
        "g.dirichlet_inverse_m2",
        "g.membrane_to_grid",
        "np.sqrt",
        "cell_volume_m3",
        "cell_area_m2",
    ):
        assert needed in vf
    before = ast.unparse(own["field_inputs"])
    for key in ("extra_rho_cells", "extra_rho_env", "extra_J_mem", "extra_Jenv_x", "extra_Jenv_y"):
        assert key in before
    assert "np.zeros" not in before
    ref = funcs(
        ast.parse((ROOT / "validation/betse/betse_normal_ecm_field_join_reference.py").read_text())
    )
    for name, oldfile, oldname in (
        ("current_equations", "betse_normal_current_reference.py", "evaluate"),
        ("voltage_equations", "betse_normal_voltage_reference.py", "voltage_equations"),
    ):
        expected = copy.deepcopy(
            funcs(ast.parse((ROOT / "validation/betse" / oldfile).read_text()))[oldname]
        )
        expected.name = name
        for n in ast.walk(expected):
            if isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) == "ctx.prec":
                n.value = ast.parse("100 if refinement == 1 else 160", mode="eval").body
            if (
                isinstance(n, ast.Return)
                and isinstance(n.value, ast.Call)
                and ast.unparse(n.value.func) in ("serial", "tree")
            ):
                n.value = n.value.args[0]
        assert digest(expected) == digest(ref[name]), name
    return dict(
        kind="cells.normal_ecm_full_field_source_audit@1",
        inherited_network_literal_scientific_bodies=47,
        inherited_network_proof=inherited,
        complete_native_field_function_count=10,
        complete_native_field_functions=original_proof,
        source_suffix_blocks=sites,
        geometry_cache_source_blocks={k: len(v) for k, v in blocks.items()},
        source_get_current_never_substituted=True,
        source_bootstrap_without_check_v=True,
        normal_check_v_only_NaN_vm=True,
        source_GRN_before_commit_before_fields=True,
        prior_field_exclusively_supplies_next_E=True,
        voltage_operator_geometry_derived=True,
        initializer_cache_fixed_from_declared_pre_state=True,
        post_material_cache_captured_separately=True,
        stale_gap_caches_preserved_after_voltage=True,
        copied_dispatch_inverse_AST_equal_except_E_and_capture=True,
        full_raw_material_locals_preserved=True,
        independent_current_voltage_equations_no_intermediate_float=True,
        accepted_inherited_material_baseline_sha256=sha(frozen),
        retained_material_accuracy_accepted=False,
        retained_material_panel=[39, 40],
        scientific_imports=0,
        scientific_AST_executions=0,
    )


if __name__ == "__main__":
    result = audit()
    path = WORK / "betse_normal_ecm_field_join_AST_witness_01.json"
    with path.open("x") as handle:
        json.dump(result, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(
        json.dumps(
            dict(
                status="static_AST_passed",
                network_bodies=47,
                field_functions=10,
                scientific_imports=0,
                scientific_AST_executions=0,
                witness=str(path),
                sha256=sha(path),
            )
        )
    )
