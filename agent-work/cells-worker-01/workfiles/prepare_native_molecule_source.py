"""Extract literal molecule/mover bodies with observational statements only."""

import ast
import copy
from pathlib import Path

BASE = Path("/mnt/workspaces/Cells/betse-v1.5.0/betse")


class Clean(ast.NodeTransformer):
    def visit_Expr(self, node):
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            return None
        return self.generic_visit(node)

    def visit_FunctionDef(self, node):
        node.decorator_list = []
        node.returns = None
        for arg in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs):
            arg.annotation = None
        return self.generic_visit(node)


def statement(text):
    return ast.parse(text).body[0]


tree = ast.parse((BASE / "science/chemistry/networks.py").read_text())
classes = {node.name: node for node in tree.body if isinstance(node, ast.ClassDef)}
molecule = Clean().visit(copy.deepcopy(classes["Molecule"]))
molecule.name = "_Molecule"
molecule.bases = []
molecule.body = [
    node
    for node in molecule.body
    if isinstance(node, ast.FunctionDef)
    and node.name in ("__init__", "transport", "update_intra", "init_growth")
]
assert len(molecule.body) == 4
loop = Clean().visit(
    copy.deepcopy(
        next(
            node
            for node in classes["MasterOfNetworks"].body
            if isinstance(node, ast.FunctionDef) and node.name == "run_loop"
        )
    )
)


class NetworkObserve(ast.NodeTransformer):
    def visit_Expr(self, node):
        if isinstance(node.value, ast.Call) and ast.unparse(node.value.func) == "obj.update_intra":
            return [node, statement("self._observe_chem('molecule_intra',mol,sim)")]
        if isinstance(node.value, ast.Call) and ast.unparse(node.value.func) == "obj.transport":
            return [
                statement("self._observe_chem('transport_before',name,sim)"),
                node,
                statement("self._observe_chem('transport_after',name,sim)"),
            ]
        return self.generic_visit(node)

    def visit_Assign(self, node):
        result = self.generic_visit(node)
        target = ast.unparse(node.targets[0])
        if target == "self.delta_conc":
            return [result, statement("self._observe_chem('rhs_ready',None,sim)")]
        if target == "self.cell_concs[name]":
            return [result, statement("self._observe_chem('chemical_commit',name,sim)")]
        return result


loop = NetworkObserve().visit(loop)
network = ast.ClassDef(
    name="_Network",
    bases=[ast.parse("feedback_source._LiteralNetwork").body[0].value],
    keywords=[],
    body=[loop],
    decorator_list=[],
)
toolbox = ast.parse((BASE / "science/sim_toolbox.py").read_text())
helpers = [
    Clean().visit(copy.deepcopy(node))
    for node in toolbox.body
    if isinstance(node, ast.FunctionDef)
    and node.name in ("electroflux", "update_Co", "molecule_mover", "no_negs")
]
assert len(helpers) == 4
mover = next(node for node in helpers if node.name == "molecule_mover")
body = []
for node in mover.body:
    body.append(node)
    stage = None
    if (
        isinstance(node, ast.Assign)
        and isinstance(node.value, ast.Call)
        and ast.unparse(node.value.func) == "update_Co"
    ):
        stage = "membrane_commit"
    if isinstance(node, ast.If) and ast.unparse(node.test) == "ignoreGJ is False":
        stage = "junction_commit"
    if (
        isinstance(node, ast.If)
        and ast.unparse(node.test) == "p.is_ecm is True"
        and any(
            isinstance(child, ast.Assign) and ast.unparse(child.targets[0]) == "cX_env_temp"
            for child in node.orelse
        )
    ):
        stage = "environment_mix"
    if stage:
        body.append(statement("p._mover_observe(" + repr(stage) + ",name,locals(),sim)"))
    if isinstance(node, ast.Return):
        body.insert(len(body) - 1, statement("p._mover_observe('return',name,locals(),sim)"))
mover.body = body
exceptions = ast.parse((BASE / "exceptions.py").read_text())
exception_nodes = [
    Clean().visit(copy.deepcopy(node))
    for node in exceptions.body
    if isinstance(node, ast.ClassDef)
    and node.name in ("BetseException", "BetseSimException", "BetseSimUnstableException")
]
assert len(exception_nodes) == 3
head = '''# ruff: noqa: B007, B905, E501
"""Literal nonempty molecule chemistry and real no-ECM transport.

This is a conditional configured-state seam, not full native initialization.
Static preparation only; no numeric qualification has run.
"""

import copy
from abc import ABCMeta
from collections import OrderedDict
from collections.abc import MutableMapping
from types import SimpleNamespace

import numpy as np

from cells.processes import betse_normal_network_join_source as feedback_source
from cells.processes import betse_normal_ion_join as ions


def _outside_scope(*args, **kwargs):
    raise ValueError("Requires separately owned ECM/intracellular-field/motor state")


fd = SimpleNamespace(gradient=_outside_scope, divergence=_outside_scope, integrator=_outside_scope)
div_env = _outside_scope
nernst_planck_flux = _outside_scope

'''
output = Path("src/cells/processes/betse_normal_molecule_source.py")
with output.open("x") as stream:
    stream.write(
        head
        + ast.unparse(
            ast.fix_missing_locations(
                ast.Module(body=exception_nodes + helpers + [molecule, network], type_ignores=[])
            )
        )
        + "\n"
    )
print("Generated9 literal numeric bodies and3 exception classes; no scientific AST executed")
