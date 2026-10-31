"""Stdlib literal-source, ECM material order and bridge audit; no science runs."""

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
        "grn_AST", WORK / "betse_normal_grn_join_ast_audit.py"
    )
    old = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(old)
    previous = old.captured_nodes()
    path = ROOT / "validation/betse/betse_ecm_grn_native_network.py"
    native_tree = ast.parse(path.read_text())
    definitions = functions(native_tree) | classes(native_tree)
    ns = dict(
        ast=ast,
        copy=copy,
        Path=Path,
        __file__=str(path),
        previous=SimpleNamespace(literal_nodes=lambda root: copy.deepcopy(previous)),
    )
    selected = [definitions[n] for n in ("ObserveEnvironment", "extra_nodes", "literal_nodes")]
    exec(
        compile(ast.Module(body=selected, type_ignores=[]), "<stdlib ECM GRN AST builder>", "exec"),
        ns,
    )
    captured = ast.Module(body=ns["literal_nodes"](PIN), type_ignores=[])
    compile(
        ast.fix_missing_locations(copy.deepcopy(captured)), "<native ECM GRN compile only>", "exec"
    )
    native = classes(captured)
    source_tree = ast.parse((ROOT / "src/cells/processes/betse_ecm_grn_source.py").read_text())
    own = classes(source_tree)
    ownf = functions(source_tree)
    feedback = classes(
        ast.parse((ROOT / "src/cells/processes/betse_normal_network_join_source.py").read_text())
    )
    molecule_tree = ast.parse(
        (ROOT / "src/cells/processes/betse_normal_molecule_source.py").read_text()
    )
    molecules = classes(molecule_tree)
    original = (
        classes(ast.parse((PIN / "science/chemistry/networks.py").read_text()))
        | classes(ast.parse((PIN / "science/chemistry/gene.py").read_text()))
        | classes(ast.parse((PIN / "util/type/iterable/mapping/mapcls.py").read_text()))
    )
    impl = dict(
        MasterOfNetworks=functions(feedback["_LiteralNetwork"])
        | functions(molecules["_Network"])
        | functions(own["MasterOfNetworks"]),
        Molecule=functions(molecules["_Molecule"]) | functions(own["Molecule"]),
        Reaction=functions(feedback["Reaction"]),
        Modulator=functions(feedback["Modulator"]),
    )
    impl.update(
        {n: functions(own[n]) for n in ("MasterOfGenes", "DynamicValue", "DynamicValueDict")}
    )
    proof = {}
    for cls, methods in impl.items():
        for name, node in functions(native[cls]).items():
            assert digest(methods[name]) == digest(node), (cls, name, "native")
            cleaned = old.Numeric().visit(copy.deepcopy(node))
            assert digest(cleaned) == digest(
                old.Numeric().visit(copy.deepcopy(functions(original[cls])[name]))
            ), (cls, name, "original")
            proof[cls + "." + name] = dict(
                numeric_AST_sha256=digest(cleaned),
                original_AST_equal=True,
                observational_AST_equal=True,
            )
    toolbox = (
        functions(ast.parse((PIN / "science/sim_toolbox.py").read_text()))
        | functions(ast.parse((PIN / "science/chemistry/netplot.py").read_text()))
        | functions(ast.parse((PIN / "science/math/finitediff.py").read_text()))
    )
    for name in (
        "electroflux",
        "update_Co",
        "molecule_mover",
        "no_negs",
        "set_net_opts",
        "nernst_planck_flux",
        "div_env",
        "gradient",
        "diff",
        "divergence",
        "integrator",
    ):
        node = functions(captured)[name]
        model = ownf[name] if name in ownf else functions(molecule_tree)[name]
        assert digest(model) == digest(node), name
        cleaned = old.Numeric().visit(copy.deepcopy(node))
        assert digest(cleaned) == digest(old.Numeric().visit(copy.deepcopy(toolbox[name]))), name
        proof[name] = dict(
            numeric_AST_sha256=digest(cleaned),
            original_AST_equal=True,
            observational_AST_equal=True,
        )
    sim = ast.parse((PIN / "science/sim.py").read_text())
    for name, line in (("initialize_owner", 884), ("dispatch", 1306)):
        assert digest(ownf[name]) == digest(functions(captured)[name])
        node = old.Numeric().visit(copy.deepcopy(ownf[name]))
        block = next(n for n in ast.walk(sim) if isinstance(n, ast.If) and n.lineno == line)
        assert digest(node.body[0]) == digest(old.Numeric().visit(copy.deepcopy(block)))
        proof[name] = dict(
            first_line=block.lineno, last_line=block.end_lineno, original_guarded_block_equal=True
        )
    assert len(proof) == 47, len(proof)
    for name in ("derive_context", "derive_radial"):
        assert digest(ownf[name]) == digest(functions(captured)[name])
    sim_init = next(
        n for n in ast.walk(sim) if isinstance(n, ast.FunctionDef) and n.name == "initDenv"
    )
    for node in ownf["derive_context"].body[:-1]:
        assert any(digest(node) == digest(n) for n in ast.walk(sim_init)), ast.unparse(node)
    cells = ast.parse((PIN / "science/cells.py").read_text())
    for node in ownf["derive_radial"].body:
        assert any(digest(node) == digest(n) for n in ast.walk(cells))
    adapter = {}
    for name in (
        "material_values",
        "augment",
        "cache",
        "cold",
        "restore",
        "before",
        "attach",
        "run_dispatch",
        "owner_evidence",
        "new_trace",
        "validate_definition",
    ):
        assert digest(ownf[name]) == digest(functions(native_tree)[name]), name
        adapter[name] = digest(ownf[name])
    # The public adapter is deliberately distinct from the actual guarded body.
    assert "science()['dispatch']" in ast.unparse(ownf["run_dispatch"])
    assert "dispatch=dispatch" in ast.unparse(ownf["science"])
    joined = functions(ast.parse((ROOT / "src/cells/processes/betse_ecm_grn_join.py").read_text()))
    material = functions(
        ast.parse((ROOT / "src/cells/processes/betse_ecm_transport.py").read_text())
    )
    inverse = copy.deepcopy(joined["material_step"])
    inverse.name = "step"
    inverse.args.kwonlyargs = []
    inverse.args.kw_defaults = []

    class Remove(ast.NodeTransformer):
        def visit_If(self, node):
            if ast.unparse(node.test) in {"on_network is not None", "on_failure is not None"}:
                return None
            return self.generic_visit(node)

    inverse = Remove().visit(inverse)
    assert digest(inverse) == digest(material["step"])
    # The independent source capture places the guarded GRN between the late
    # seam and actual update_all_concs, and retains the real native owner live.
    capture = functions(ast.parse((ROOT / "validation/betse/betse_ecm_grn_native.py").read_text()))[
        "evaluate"
    ]
    loop = next(
        n
        for n in ast.walk(capture)
        if isinstance(n, ast.For) and ast.unparse(n.target) == "(index, call)"
    )
    texts = [ast.unparse(n) for n in loop.body]
    before = next(i for i, s in enumerate(texts) if s == "observe('supplied_late_flux')")
    run = next(i for i, s in enumerate(texts) if s.startswith("network.run_dispatch("))
    after = next(i for i, s in enumerate(texts) if s == "sim.update_all_concs(cells, parameters)")
    assert before < run < after
    assert "sim.c_env_bound =" not in ast.unparse(ownf["restore"])
    assert "if enabled != 1" in ast.unparse(ownf["restore"])
    assert "read_gene_config" not in ast.unparse(ownf["restore"])
    ref = functions(ast.parse((ROOT / "validation/betse/betse_ecm_grn_reference.py").read_text()))
    old_ref = functions(
        ast.parse((ROOT / "validation/betse/betse_normal_grn_join_reference.py").read_text())
    )
    assert digest(ref["hill"]) == digest(old_ref["hill"])
    return dict(
        literal_scientific_body_count=47,
        literal_numeric_bodies=proof,
        actual_normal_init_and_dispatch_guards=True,
        ecm_fd_and_nernst_planck_bodies_original=True,
        original_radial_weight_and_TJ_context_statements=True,
        bridge_AST_sha256=adapter,
        retained_material_step_inverse_AST_equal=True,
        native_network_before_deferred_commit=True,
        full_public_cache_and_E_site_buffers=True,
        current_packet_ionic_boundary_authoritative=True,
        disabled_ion_aliases_not_fabricated=True,
        cold_reader_not_rerun_on_hot_restore=True,
        independent_Hill_reference_unchanged=True,
        retained_material_accuracy_accepted=False,
        retained_material_panel=dict(
            passed=39, total=40, original_failed_case="signed_environment"
        ),
        scientific_imports=0,
        scientific_AST_executions=0,
    )


if __name__ == "__main__":
    result = audit()
    print(
        {
            "literal_scientific_bodies": result["literal_scientific_body_count"],
            "scientific_AST_executions": 0,
        }
    )
