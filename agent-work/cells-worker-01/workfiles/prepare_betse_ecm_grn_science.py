# ruff: noqa: E501 -- emitted scientific bodies/templates are formatted separately.
"""Emit separate ECM GRN scientific source and independent AST builder."""

import ast
import copy
from pathlib import Path

ROOT = Path("/home/robert/Cells")
PIN = Path("/mnt/workspaces/Cells/betse-v1.5.0/betse")


class ObserveEnvironment(ast.NodeTransformer):
    def visit_Assign(self, node):
        target = ast.unparse(node.targets[0])
        label = {
            "cenv[-1, :]": "ecm_clamp",
            "(gcx, gcy)": "ecm_gradient",
            "(fx, fy)": "ecm_flux",
        }.get(target)
        if target == "cenv" and "div_fa" in ast.unparse(node.value):
            label = "ecm_euler"
        return (
            [node, *ast.parse("p._mover_observe(" + repr(label) + ",name,locals(),sim)").body]
            if label
            else node
        )


def extra_nodes(root):
    tb = ast.parse((root / "science/sim_toolbox.py").read_text())
    fd = ast.parse((root / "science/math/finitediff.py").read_text())
    return [
        copy.deepcopy(n)
        for tree, names in (
            (tb, {"nernst_planck_flux", "div_env"}),
            (fd, {"gradient", "diff", "divergence", "integrator"}),
        )
        for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name in names
    ]


old = (ROOT / "src/cells/processes/betse_normal_grn_source.py").read_text()
prefix = old[: old.index('"""Pure state-adapter template')]
tree = ast.parse(prefix)
mol = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Molecule")
molecule_tree = ast.parse(
    (ROOT / "src/cells/processes/betse_normal_molecule_source.py").read_text()
)
original = next(
    n for n in molecule_tree.body if isinstance(n, ast.ClassDef) and n.name == "_Molecule"
)
mol.body = [
    copy.deepcopy(n)
    for n in original.body
    if isinstance(n, ast.FunctionDef) and n.name == "transport"
]
physics = [
    copy.deepcopy(n)
    for n in molecule_tree.body
    if isinstance(n, ast.FunctionDef) and n.name in {"electroflux", "update_Co", "molecule_mover"}
]
for n in physics:
    if n.name == "molecule_mover":
        ObserveEnvironment().visit(n)
tree.body += physics + extra_nodes(PIN)
source = (
    ast.unparse(ast.fix_missing_locations(tree))
    + """

from cells.processes import betse_normal_grn_source as qualified
clone,public,wire=qualified.clone,qualified.public,qualified.wire
BetseSimUnstableException=molecule_source.BetseSimUnstableException
fd=SimpleNamespace(gradient=gradient,divergence=divergence,integrator=integrator)
stb=SimpleNamespace(molecule_mover=molecule_mover,no_negs=molecule_source.no_negs)


def science():
    return dict(MasterOfGenes=MasterOfGenes,MasterOfNetworks=MasterOfNetworks,Molecule=Molecule,
        Reaction=feedback_source.Reaction,Modulator=feedback_source.Modulator,
        DynamicValue=DynamicValue,DynamicValueDict=DynamicValueDict,
        initialize_owner=initialize_owner,dispatch=dispatch)
"""
)
with (ROOT / "src/cells/processes/betse_ecm_grn_source.py").open("x") as f:
    f.write("# ruff: noqa: B007, B905, E501, E402\n" + source)

own = ast.parse(Path(__file__).read_text())
builders = [
    n
    for n in own.body
    if isinstance(n, (ast.FunctionDef, ast.ClassDef))
    and n.name in {"ObserveEnvironment", "extra_nodes"}
]
native = (
    '''# ruff: noqa: E501, E402
"""Independent authenticated original-AST ECM GRN scientific namespace."""
import ast
import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import numpy as np
from validation.betse import betse_normal_grn_join_native_network as previous
clone,public,wire=previous.clone,previous.public,previous.wire
PROTOCOL=Path(__file__).with_name("betse_ecm_grn_protocol.json")
_SCIENCE=None
'''
    + ast.unparse(ast.fix_missing_locations(ast.Module(body=builders, type_ignores=[])))
    + """


def literal_nodes(root):
    nodes=previous.literal_nodes(root)
    for node in nodes:
        if isinstance(node,ast.FunctionDef) and node.name=="molecule_mover":
            ObserveEnvironment().visit(node)
    return nodes+extra_nodes(root)


def science():
    global _SCIENCE
    if _SCIENCE is None:
        pins=json.loads(PROTOCOL.read_text())["native_source"]
        for name,digest in pins["source_sha256"].items():
            data=(Path(pins["checkout"])/name).read_bytes()
            assert hashlib.sha256(data).hexdigest()==digest
            assert data==(Path(pins["installed_package"]).parent/name).read_bytes()
        ns=previous.authenticated()
        exec(compile(ast.fix_missing_locations(ast.Module(body=literal_nodes(Path(pins["checkout"])/"betse"),type_ignores=[])),"<original ECM GRN scientific bodies>","exec"),ns)
        ns["fd"]=SimpleNamespace(**{name:ns[name] for name in ("gradient","divergence","integrator")})
        ns["stb"]=SimpleNamespace(molecule_mover=ns["molecule_mover"],no_negs=ns["no_negs"])
        _SCIENCE=ns
    return _SCIENCE
"""
)
with (ROOT / "validation/betse/betse_ecm_grn_native_network.py").open("x") as f:
    f.write(native)
print({"scientific_source_files_emitted_without_execution": 2})
