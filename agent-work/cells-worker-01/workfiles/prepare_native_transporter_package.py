# ruff: noqa: E501 -- literal source templates are formatted in their outputs.
"""Create the separate configured-transporter package without scientific imports."""

import ast
import copy
from pathlib import Path

ROOT = Path("/home/robert/Cells")
PIN = Path("/mnt/workspaces/Cells/betse-v1.5.0/betse/science/chemistry/networks.py")
OLD = "betse_normal_molecule"
NEW = "betse_normal_transporter"


def write(name, text):
    with (ROOT / name).open("x") as stream:
        stream.write(text)


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


class Observe(ast.NodeTransformer):
    def visit_For(self, node):
        node = self.generic_visit(node)
        if ast.unparse(node.target) == "name":
            node.body.insert(0, statement("self._observe_transporter('before',name,None,None,sim)"))
            node.body.append(statement("self._observe_transporter('after',name,None,None,sim)"))
        if ast.unparse(node.target) == "(i, (delc, coeff))":
            is_product = "delta_prod_eval_strings" in ast.unparse(node.iter)
            stage, value = (
                ("product_commit", "delta_prod")
                if is_product
                else ("reactant_commit", "delta_react")
            )
            node.body.append(statement(f"self._observe_transporter('{stage}',name,i,{value},sim)"))
        return node

    def visit_Assign(self, node):
        node = self.generic_visit(node)
        if ast.unparse(node.targets[0]) == "self.transporters[name].flux":
            return [node, statement("self._observe_transporter('flux',name,None,None,sim)")]
        return node

    def visit_AugAssign(self, node):
        node = self.generic_visit(node)
        if ast.unparse(node.target) == "self.extra_J_mem":
            return [node, statement("self._observe_transporter('current',name,None,None,sim)")]
        return node


parsed = ast.parse(PIN.read_text())
network = next(
    node
    for node in parsed.body
    if isinstance(node, ast.ClassDef) and node.name == "MasterOfNetworks"
)
methods = [
    Clean().visit(copy.deepcopy(node))
    for node in network.body
    if isinstance(node, ast.FunctionDef)
    and node.name in ("read_transporters", "write_transporters", "run_loop_transporters")
]
assert len(methods) == 3
loop = next(node for node in methods if node.name == "run_loop_transporters")
methods[methods.index(loop)] = Observe().visit(loop)
transporter = Clean().visit(
    copy.deepcopy(
        next(
            node
            for node in parsed.body
            if isinstance(node, ast.ClassDef) and node.name == "Transporter"
        )
    )
)
transporter.body = [
    node
    for node in transporter.body
    if isinstance(node, ast.FunctionDef) and node.name in ("__init__", "init_reaction")
]
assert len(transporter.body) == 2
literal = ast.ClassDef(
    name="_Network",
    bases=[ast.parse("molecule_source._Network", mode="eval").body],
    keywords=[],
    body=methods,
    decorator_list=[],
)
header = '''# ruff: noqa: B007, B905, E501
"""Actual configured transporter builder and ordered source execution.

The no-ECM cell-volume bath update and coefficient-free membrane-buffer
updates are preserved. This consumes supplied geometry and configured state.
"""

import copy
from collections import OrderedDict
from collections.abc import Mapping
from types import SimpleNamespace

import numpy as np

from cells.processes import betse_network_transport as component
from cells.processes import betse_normal_ion_join as ions
from cells.processes import betse_normal_molecule_source as molecule_source

logs = SimpleNamespace(log_info=lambda *_: None, log_warning=lambda *_: None)
tex_val = str
BetseSimConfException = ValueError
controls = molecule_source.controls
EXTRA = {"transporters", "membrane_volume_m3", "transporter_profiles"}

'''
write(
    "src/cells/processes/" + NEW + "_source.py",
    header
    + ast.unparse(
        ast.fix_missing_locations(ast.Module(body=[transporter, literal], type_ignores=[]))
    )
    + "\n",
)

# Preserve the complete outer implementation and its five arithmetic helpers.
joined = (ROOT / ("src/cells/processes/" + OLD + "_join.py")).read_text()
joined = joined.replace(OLD, NEW).replace(
    "betse_normal_native_molecule_chemistry_transport_v1_5_0@1",
    "betse_normal_configured_transporter_execution_v1_5_0@1",
)
joined = joined.replace(
    "    before_network=None,\n", "    before_network=None,\n    before_transporters=None,\n"
)
joined = joined.replace(
    "            before_network=before_network,\n",
    "            before_network=before_network,\n            before_transporters=before_transporters,\n",
)
needle = (
    "                    cluster_open=ib.kernel.cluster_open,\n                    geometry=dict("
)
assert joined.count(needle) == 1
joined = joined.replace(
    needle,
    "                    cluster_open=ib.kernel.cluster_open,\n                    rho_pump=live_pump.rho_pump,\n                    geometry=dict(",
    1,
)
needle = """            observe("network_clear")
            with np.errstate(all="ignore"):
"""
assert joined.count(needle) == 1
joined = joined.replace(
    needle,
    """            observe("network_clear")
            transporter_execution = network_source.execution_inputs(
                core, sim, geometry, p, binding.definition["network"], ib.ion_ids
            )
            feedback["transporter_execution"] = transporter_execution
            if before_transporters is not None:
                before_transporters(ions.freeze(transporter_execution))
            try:
                with np.errstate(all="ignore"):
                    core.run_loop_transporters(0.0, sim, geometry, p)
                transporter_execution["source_completed"] = True
                observe("network_transporters")
            finally:
                transporter_execution.update(
                    values_after=ions.data(_values(arrays)),
                    concentrations_after=network_source.concentrations(core),
                    fluxes_after=network_source.fluxes(core),
                    extra_current_after_A_m2=core.extra_J_mem.copy(),
                    frames=tuple(core.transporter_frames),
                )
            with np.errstate(all="ignore"):
""",
    1,
)
write("src/cells/processes/" + NEW + "_join.py", joined)

# Independent capture: original AST comes from the authenticated checkout.
native_network = (ROOT / ("validation/betse/" + OLD + "_join_native_network.py")).read_text()
native_network = native_network.replace(OLD, NEW)
start = native_network.index("def literal_nodes(root):")
end = native_network.index("\n\ndef authenticated():", start)
builder = """def literal_nodes(root):
    from validation.betse import betse_normal_molecule_join_native_network as molecule_native

    nodes = molecule_native.literal_nodes(root)
    parsed = ast.parse((root / "science/chemistry/networks.py").read_text())
    original = next(node for node in parsed.body if isinstance(node, ast.ClassDef) and node.name == "MasterOfNetworks")
    network = next(node for node in nodes if getattr(node, "name", None) == "_LiteralNetwork")
    methods = [Clean().visit(copy.deepcopy(node)) for node in original.body if isinstance(node, ast.FunctionDef) and node.name in ("read_transporters", "write_transporters", "run_loop_transporters")]

    class Observe(ast.NodeTransformer):
        def visit_For(self, node):
            node = self.generic_visit(node)
            if ast.unparse(node.target) == "name":
                node.body.insert(0, statement("self._observe_transporter('before',name,None,None,sim)"))
                node.body.append(statement("self._observe_transporter('after',name,None,None,sim)"))
            if ast.unparse(node.target) == "(i, (delc, coeff))":
                product = "delta_prod_eval_strings" in ast.unparse(node.iter)
                stage, value = ("product_commit", "delta_prod") if product else ("reactant_commit", "delta_react")
                node.body.append(statement(f"self._observe_transporter('{stage}',name,i,{value},sim)"))
            return node

        def visit_Assign(self, node):
            node = self.generic_visit(node)
            if ast.unparse(node.targets[0]) == "self.transporters[name].flux":
                return [node, statement("self._observe_transporter('flux',name,None,None,sim)")]
            return node

        def visit_AugAssign(self, node):
            node = self.generic_visit(node)
            if ast.unparse(node.target) == "self.extra_J_mem":
                return [node, statement("self._observe_transporter('current',name,None,None,sim)")]
            return node

    network.body.extend(Observe().visit(node) if node.name == "run_loop_transporters" else node for node in methods)
    transporter = Clean().visit(copy.deepcopy(next(node for node in parsed.body if isinstance(node, ast.ClassDef) and node.name == "Transporter")))
    transporter.body = [node for node in transporter.body if isinstance(node, ast.FunctionDef) and node.name in ("__init__", "init_reaction")]
    return nodes + [transporter]
"""
native_network = native_network[:start] + builder + native_network[end:]
native_network = native_network.replace(
    "for name in previous.METHODS:",
    "for name in (*previous.METHODS, 'read_transporters', 'write_transporters', 'run_loop_transporters'):",
)
native_network = native_network.replace(
    "return dict(present_fields=(), molecule_states=molecules)",
    "return dict(present_fields=(), molecule_states=molecules, transporter_fluxes={row['name']: None for row in definition['transporters']})",
)
native_network = native_network.replace(
    "    return values\n\n\ndef attach(",
    "    values['transporter_fluxes'] = fluxes(net)\n    return values\n\n\ndef attach(",
)
needle = '    net.read_reactions(definition["reactions"], sim, cells, p)'
assert native_network.count(needle) == 1
native_network = native_network.replace(
    needle,
    """    cells.mem_vol = np.asarray(definition["membrane_volume_m3"], np.float64).copy()
    profiles = definition["transporter_profiles"]
    dyna = SimpleNamespace(
        cell_target_inds={name: row["cells"] for name, row in profiles.items()},
        tissue_target_inds={name: row["membranes"] for name, row in profiles.items()},
        env_target_inds={name: row["environment"] for name, row in profiles.items()},
    )
    net.read_transporters(definition["transporters"], SimpleNamespace(sim=sim,cells=cells,p=p,dyna=dyna))
    net.write_transporters(sim, cells, p)
    for name, obj in net.transporters.items():
        value = incoming_cache["transporter_fluxes"][name]
        obj.flux = None if value is None else np.asarray(value, np.float64).copy()
"""
    + needle,
    1,
)
native_network = native_network.replace(
    "        mover_frames=[],\n", "        mover_frames=[],\n        transporter_frames=[],\n"
)
needle = "    return trace\n"
assert native_network.count(needle) == 1
native_network = native_network.replace(
    needle,
    """    def transporter(stage, name, term, delta, actual):
        trace["transporter_frames"].append(dict(
            stage=stage, name=name, term=term, delta=copy.deepcopy(delta),
            concentrations=concentrations(net), fluxes=fluxes(net),
            extra_current_A_m2=net.extra_J_mem.copy(),
            vm=actual.vm.copy(), vgj=actual.vgj.copy(),
        ))
    net._observe_transporter = transporter
    return trace
""",
)
write("validation/betse/" + NEW + "_join_native_network.py", native_network)
for suffix in ("native.py", "native_helpers.py"):
    text = (ROOT / ("validation/betse/" + OLD + "_join_" + suffix)).read_text().replace(OLD, NEW)
    write("validation/betse/" + NEW + "_join_" + suffix, text)

print(
    "Created separate transporter source, join and three native capture files; no scientific execution"
)
