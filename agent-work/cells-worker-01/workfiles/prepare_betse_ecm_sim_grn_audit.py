# ruff: noqa: E501
"""Emit the independent stdlib AST audit for the combined standalone ECM scope."""

from pathlib import Path

ROOT = Path("/home/robert/Cells")
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
text = (
    (WORK / "betse_sim_grn_ast_audit.py").read_text().replace("betse_sim_grn", "betse_ecm_sim_grn")
)
text = text.replace(
    "    previous = old.captured_nodes()",
    """    neutral_nodes=old.captured_nodes()
    ecm_path=ROOT/"validation/betse/betse_ecm_grn_native_network.py"
    ecm_tree=ast.parse(ecm_path.read_text())
    ecm_defs=functions(ecm_tree)|classes(ecm_tree)
    namespace=dict(ast=ast,copy=copy,Path=Path,__file__=str(ecm_path),
        previous=SimpleNamespace(literal_nodes=lambda root:copy.deepcopy(neutral_nodes)))
    selected=[ecm_defs[name] for name in ("ObserveEnvironment","extra_nodes","literal_nodes")]
    exec(compile(ast.Module(body=selected,type_ignores=[]),"<stdlib ECM AST assembly>","exec"),namespace)
    previous=namespace["literal_nodes"](PIN)""",
    1,
)
text = text.replace(
    "src/cells/processes/betse_normal_grn_source.py", "src/cells/processes/betse_ecm_grn_source.py"
)
text = text.replace(
    'Molecule=functions(molecule["_Molecule"]),',
    'Molecule=functions(molecule["_Molecule"])|functions(neutral["Molecule"]),',
    1,
)
text = text.replace(
    '    toolbox |= functions(ast.parse((PIN / "science/chemistry/netplot.py").read_text()))',
    '    toolbox |= functions(ast.parse((PIN / "science/chemistry/netplot.py").read_text()))\n'
    '    toolbox |= functions(ast.parse((PIN / "science/math/finitediff.py").read_text()))',
    1,
)
start = text.index(
    '    for name in ("molecule_mover", "electroflux", "update_Co", "no_negs", "set_net_opts"):'
)
end = text.index("        node = functions(captured)[name]", start)
text = (
    text[:start]
    + """    for name in ("molecule_mover","electroflux","update_Co","no_negs","set_net_opts",
                 "nernst_planck_flux","div_env","gradient","diff","divergence","integrator"):
        local=functions(ast.parse((ROOT/"src/cells/processes/betse_ecm_grn_source.py").read_text()))
        primitive=functions(ast.parse((ROOT/"src/cells/processes/betse_normal_molecule_source.py").read_text()))
        impl=local[name] if name in local else primitive[name]
"""
    + text[end:]
)
text = text.replace(
    "    assert len(proof) == 46, len(proof)", "    assert len(proof) == 52, len(proof)", 1
)
text = text.replace('        "validate",\n', "", 1)
text = text.replace(
    '    old_ref = functions(\n        ast.parse((ROOT / "validation/betse/betse_normal_grn_join_reference.py").read_text())\n    )',
    '    old_ref = functions(ast.parse((ROOT/"validation/betse/betse_ecm_grn_reference.py").read_text()))',
    1,
)
point = text.index('    assert "numpy" not in ast.unparse(ref["clock"])')
text = (
    text[:point]
    + """    scalar_ref=functions(ast.parse((ROOT/"validation/betse/betse_sim_grn_reference.py").read_text()))
    original_clock=copy.deepcopy(scalar_ref["clock"])
    class Precision(ast.NodeTransformer):
        def visit_Constant(self,node):
            if isinstance(node.value,int) and node.value in (90,140):
                node.value={90:100,140:160}[node.value]
            return node
    assert digest(Numeric().visit(copy.deepcopy(ref["clock"])))==digest(Numeric().visit(Precision().visit(original_clock)))
    assert "is_ecm=True" in ast.unparse(source_functions["make_context"])
    assert "science()['derive_context'](sim, cells)" in ast.unparse(source_functions["make_context"])
    assert "code['grid'](cells, p)" in ast.unparse(native_f["build_grid"])
    assert "code['environment'](cells, p)" in ast.unparse(native_f["build_grid"])
    assert "read_gene_config" not in ast.unparse(source_functions["restore"])
    assert "if enabled != 1" in ast.unparse(source_functions["restore"])
    assert "grid_fields" in ast.unparse(source_functions["snapshot"])
    original_ecm_spec=importlib.util.spec_from_file_location("original_ECM_context_statements",WORK/"betse_ecm_grn_ast_audit.py")
    original_ecm=importlib.util.module_from_spec(original_ecm_spec)
    original_ecm_spec.loader.exec_module(original_ecm)
    ecm_proof=original_ecm.audit()
    assert ecm_proof["original_radial_weight_and_TJ_context_statements"]
"""
    + text[point:]
)
text = text.replace("literal_scientific_body_count=46", "literal_scientific_body_count=52")
text = text.replace(
    "        unsupported_ecm_mitochondria_fluid_cut_restart_explicit=True,",
    """        actual_ECM_grid_molecular_mover_and_FD_bodies=True,
        original_radial_weight_and_TJ_context_statements=True,
        E_grid_and_M_membrane_buffers_distinct=True,
        scalar_clock_reference_only_precision_changed=True,
        full_five_publication_fields_persist_without_creation_of_core_rho=True,
        unsupported_mitochondria_fluid_cut_restart_explicit=True,""",
)
with (WORK / "betse_ecm_sim_grn_ast_audit.py").open("x") as stream:
    stream.write(text)
print("ECM standalone52-body AST audit emitted; scientific AST is never executed")
