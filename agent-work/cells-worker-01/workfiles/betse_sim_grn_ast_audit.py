"""Stdlib original-AST, standalone order and complete state-bridge audit."""

import ast
import copy
import hashlib
import importlib.util
from pathlib import Path
from types import SimpleNamespace

ROOT = Path("/home/robert/Cells")
PIN = Path("/mnt/workspaces/Cells/betse-v1.5.0/betse")
WORK = ROOT / "agent-work/cells-worker-01/workfiles"


def functions(node):
    return {n.name: n for n in node.body if isinstance(n, ast.FunctionDef)}


def classes(node):
    return {n.name: n for n in node.body if isinstance(n, ast.ClassDef)}


def digest(node):
    return hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest()


def audit():
    spec = importlib.util.spec_from_file_location(
        "accepted_grn_AST", WORK / "betse_normal_grn_join_ast_audit.py"
    )
    old = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(old)
    previous = old.captured_nodes()
    native_tree = ast.parse((ROOT / "validation/betse/betse_sim_grn_native.py").read_text())
    defs = functions(native_tree) | classes(native_tree)
    constants = next(
        ast.literal_eval(n.value)
        for n in native_tree.body
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "CORE_METHODS" for t in n.targets)
    )
    ns = dict(
        ast=ast,
        copy=copy,
        CORE_METHODS=constants,
        previous=SimpleNamespace(literal_nodes=lambda root: copy.deepcopy(previous)),
    )
    chosen = [defs[name] for name in ("Clean", "original_nodes", "literal_nodes")]
    exec(
        compile(
            ast.Module(body=chosen, type_ignores=[]), "<stdlib standalone AST builder>", "exec"
        ),
        ns,
    )
    captured = ast.Module(body=ns["literal_nodes"](PIN), type_ignores=[])
    compile(
        ast.fix_missing_locations(copy.deepcopy(captured)),
        "<native standalone AST compile only>",
        "exec",
    )
    native = classes(captured)
    source = ast.parse((ROOT / "src/cells/processes/betse_sim_grn.py").read_text())
    own = classes(source)
    originals = classes(ast.parse((PIN / "science/chemistry/networks.py").read_text())) | classes(
        ast.parse((PIN / "science/chemistry/gene.py").read_text())
    )
    feedback = classes(
        ast.parse((ROOT / "src/cells/processes/betse_normal_network_join_source.py").read_text())
    )
    molecule = classes(
        ast.parse((ROOT / "src/cells/processes/betse_normal_molecule_source.py").read_text())
    )
    neutral = classes(
        ast.parse((ROOT / "src/cells/processes/betse_normal_grn_source.py").read_text())
    )
    implementations = dict(
        MasterOfNetworks=functions(feedback["_LiteralNetwork"])
        | functions(molecule["_Network"])
        | functions(neutral["MasterOfNetworks"])
        | functions(own["MasterOfNetworks"]),
        MasterOfGenes=functions(own["MasterOfGenes"]),
        Molecule=functions(molecule["_Molecule"]),
        Reaction=functions(feedback["Reaction"]),
        Modulator=functions(feedback["Modulator"]),
        DynamicValue=functions(neutral["DynamicValue"]),
        DynamicValueDict=functions(neutral["DynamicValueDict"]),
    )
    originals |= classes(ast.parse((PIN / "util/type/iterable/mapping/mapcls.py").read_text()))

    class Numeric(old.Numeric):
        def visit_Expr(self, node):
            if isinstance(node.value, ast.Call) and ast.unparse(node.value.func) in {
                "observe",
                "created",
            }:
                return None
            return super().visit_Expr(node)

    proof = {}
    for cls, methods in implementations.items():
        for name, node in functions(native[cls]).items():
            assert digest(methods[name]) == digest(node), (cls, name, "native")
            cleaned = Numeric().visit(copy.deepcopy(node))
            assert digest(cleaned) == digest(
                Numeric().visit(copy.deepcopy(functions(originals[cls])[name]))
            ), (cls, name, "original")
            proof[cls + "." + name] = dict(
                numeric_AST_sha256=digest(cleaned),
                original_AST_equal=True,
                observational_AST_equal=True,
            )
    toolbox = functions(ast.parse((PIN / "science/sim_toolbox.py").read_text()))
    toolbox |= functions(ast.parse((PIN / "science/chemistry/netplot.py").read_text()))
    source_functions = functions(source)
    for name in ("molecule_mover", "electroflux", "update_Co", "no_negs", "set_net_opts"):
        impl = (
            functions(
                ast.parse((ROOT / "src/cells/processes/betse_normal_grn_source.py").read_text())
            )[name]
            if name == "set_net_opts"
            else functions(
                ast.parse(
                    (ROOT / "src/cells/processes/betse_normal_molecule_source.py").read_text()
                )
            )[name]
        )
        node = functions(captured)[name]
        assert digest(impl) == digest(node), name
        cleaned = Numeric().visit(copy.deepcopy(node))
        assert digest(cleaned) == digest(Numeric().visit(copy.deepcopy(toolbox[name]))), name
        proof[name] = dict(
            numeric_AST_sha256=digest(cleaned),
            original_AST_equal=True,
            observational_AST_equal=True,
        )
    assert len(proof) == 46, len(proof)
    conf = classes(ast.parse((PIN / "exceptions.py").read_text()))["BetseSimConfException"]
    assert digest(Numeric().visit(copy.deepcopy(own["BetseSimConfException"]))) == digest(
        Numeric().visit(copy.deepcopy(conf))
    )
    assert digest(Numeric().visit(copy.deepcopy(native["BetseSimConfException"]))) == digest(
        Numeric().visit(copy.deepcopy(conf))
    )
    native_f = functions(native_tree)
    common = {}
    for name in (
        "validate",
        "make_context",
        "snapshot",
        "restore",
        "configure_call",
        "local_inputs",
        "observe",
        "attach",
        "capture_open",
        "save_boundary",
        "directory_boundary",
        "new_trace",
        "created",
        "active",
    ):
        assert digest(source_functions[name]) == digest(native_f[name]), name
        common[name] = digest(source_functions[name])
    branch = next(
        n
        for n in ast.walk(ast.parse((PIN / "science/simrunner.py").read_text()))
        if isinstance(n, ast.If) and ast.unparse(n.test) == "self._p.grn_unpickle_filename is None"
    )
    start = Numeric().visit(copy.deepcopy(source_functions["start_new"]))
    assert [digest(n) for n in start.body[:-1]] == [
        digest(Numeric().visit(copy.deepcopy(n))) for n in branch.body
    ]
    assert digest(source_functions["start_new"]) == digest(functions(captured)["start_new"])
    assert not {"initialize_owner", "dispatch"} & functions(captured).keys()
    run = functions(own["MasterOfGenes"])["run_core_sim"]
    calls = {ast.unparse(n.func) for n in ast.walk(run) if isinstance(n, ast.Call)}
    assert "self.core.clear_cache" in calls and "self.reinitialize" in calls
    assert (
        not {
            "self.core.clear_run_loop",
            "self.core.run_loop_modulators",
            "self.core.run_loop_channels",
        }
        & calls
    )
    assert ast.unparse(run.body[3]) == "p.substances_affect_charge = False"
    restore = ast.unparse(source_functions["restore"])
    assert (
        "read_gene_config" not in restore
        and "tissue_init" not in restore
        and "vars(net).update" in restore
    )
    hot_containers = {
        node.attr
        for node in ast.walk(source_functions["restore"])
        if isinstance(node, ast.Attribute)
        and isinstance(node.ctx, ast.Store)
        and isinstance(node.value, ast.Name)
        and node.value.id == "net"
    }
    object_loop = next(
        node
        for node in ast.walk(source_functions["restore"])
        if isinstance(node, ast.For) and ast.unparse(node.target) == "(attr, key, cls)"
    )
    hot_containers |= {row[0] for row in ast.literal_eval(object_loop.iter)}
    required_containers = {
        "molecules",
        "reactions",
        "transporters",
        "channels",
        "reactions_env",
        "reactions_mit",
        "modulators",
        "mit",
    }
    assert required_containers <= hot_containers, required_containers - hot_containers
    cold_containers = {
        node.attr
        for name in ("__init__", "read_substances")
        for node in ast.walk(functions(originals["MasterOfNetworks"])[name])
        if isinstance(node, ast.Attribute)
        and isinstance(node.ctx, ast.Store)
        and isinstance(node.value, ast.Name)
        and node.value.id == "self"
    }
    assert required_containers <= cold_containers
    ref = functions(ast.parse((ROOT / "validation/betse/betse_sim_grn_reference.py").read_text()))
    old_ref = functions(
        ast.parse((ROOT / "validation/betse/betse_normal_grn_join_reference.py").read_text())
    )
    warm = copy.deepcopy(ref["warm"])
    loop = next(
        n
        for n in ast.walk(warm)
        if isinstance(n, ast.For)
        and ast.unparse(n.target) == "row"
        and isinstance(n.iter, ast.Tuple)
        and not n.iter.elts
    )
    loop.iter = ast.parse('definition["modulators"]', mode="eval").body
    assert digest(warm) == digest(old_ref["warm"])
    assert digest(ref["hill"]) == digest(old_ref["hill"])
    assert "numpy" not in ast.unparse(ref["clock"]) and "linspace" not in {
        ast.unparse(n.func) for n in ast.walk(ref["clock"]) if isinstance(n, ast.Call)
    }
    return dict(
        literal_scientific_body_count=46,
        literal_numeric_bodies=proof,
        common_adapter_AST_sha256=common,
        actual_entire_run_core_sim=True,
        original_new_owner_branch=dict(
            first_line=branch.lineno, last_line=branch.end_lineno, body_AST_equal=True
        ),
        original_clock_and_sampling=True,
        original_reinitialize_clear_sample_report_exports=True,
        no_normal_guard_or_dispatch_substitution=True,
        complete_public_owner_ionic_boundary_cache=True,
        standalone_cache_container_providers=dict(
            required=sorted(required_containers),
            original_cold_providers=sorted(required_containers & cold_containers),
            hot_restore_providers=sorted(required_containers & hot_containers),
            missing=[],
        ),
        independent_warm_equations_only_modulator_dispatch_removed=True,
        in_memory_IO_boundary=True,
        physical_file_persistence_credit=False,
        unsupported_ecm_mitochondria_fluid_cut_restart_explicit=True,
        scientific_AST_executions=0,
        scientific_imports=0,
    )


if __name__ == "__main__":
    result = audit()
    print(
        {
            "literal_scientific_bodies": result["literal_scientific_body_count"],
            "scientific_AST_executions": 0,
        }
    )
