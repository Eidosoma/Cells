# ruff: noqa: E501 -- emitted source templates are formatted in their outputs.
"""Create a separate charged GRN prefix from frozen neutral02, stdlib only."""

import ast
from pathlib import Path

ROOT = Path("/home/robert/Cells")
PIN = Path("/mnt/workspaces/Cells/betse-v1.5.0/betse")
OLD, NEW = "betse_normal_grn", "betse_normal_charged_grn"


def write(relative, text):
    with (ROOT / relative).open("x") as stream:
        stream.write(text)


def read(relative):
    return (ROOT / relative).read_text()


for folder, suffix in (
    ("src/cells/processes/", "_source.py"),
    ("src/cells/processes/", "_join.py"),
    ("validation/betse/", "_join_native.py"),
    ("validation/betse/", "_join_native_helpers.py"),
    ("validation/betse/", "_join_native_network.py"),
):
    text = (
        read(folder + OLD + suffix)
        .replace(OLD, NEW)
        .replace("cells.genuine_grn_owner_cache@1", "cells.charged_grn_owner_cache@1")
    )
    if suffix == "_join.py":
        text = text.replace(
            "betse_normal_native_grn_owner_dispatch_v1_5_0@1",
            "betse_normal_native_charged_grn_initialization_v1_5_0@1",
        )
    write(folder + NEW + suffix, text)

source = ROOT / ("src/cells/processes/" + NEW + "_source.py")
text = source.read_text()
text = text.replace(
    "BetseSimConfException = ValueError",
    """BetseSimException = molecule_source.BetseSimException

class BetseSimConfException(BetseSimException):
    pass""",
    1,
)
tree = ast.parse(text)
core = next(
    node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "MasterOfNetworks"
)
bal = next(
    node for node in core.body if isinstance(node, ast.FunctionDef) and node.name == "bal_charge"
)
bal.body.insert(0, ast.parse("observe_balance(self,'before',Q,sim,tag,p)").body[0])
bal.body.append(ast.parse("observe_balance(self,'after',Q,sim,tag,p)").body[0])
text = ast.unparse(ast.fix_missing_locations(tree)) + "\n"
text = "# ruff: noqa: B007, B905, E501\n" + text
source.write_text(text)

native = ROOT / ("validation/betse/" + NEW + "_join_native_network.py")
text = native.read_text()
needle = "    net.body.extend(added.body)"
assert text.count(needle) == 1
text = text.replace(
    needle,
    """    bal=next(node for node in added.body if node.name=="bal_charge")
    bal.body.insert(0,statement("observe_balance(self,'before',Q,sim,tag,p)"))
    bal.body.append(statement("observe_balance(self,'after',Q,sim,tag,p)"))
    exceptions=ast.parse((root/"exceptions.py").read_text())
    conf=Clean().visit(copy.deepcopy(next(node for node in exceptions.body if isinstance(node,ast.ClassDef) and node.name=="BetseSimConfException")))
    base.append(conf)
"""
    + needle,
    1,
)
needle = "        nernst_planck_flux=_outside_scope,"
assert text.count(needle) == 1
text = text.replace(needle, needle + "\n        observe_balance=observe_balance,", 1)
native.write_text(text)

observe = """

def ionic_state(sim):
    return dict(cc_cells=sim.cc_cells.copy(),cc_at_mem=sim.cc_at_mem.copy(),cc_env=sim.cc_env.copy())


def observe_balance(net,stage,Q,sim,tag,p):
    if not hasattr(net,"_balance_events"):
        net._balance_events=[]
    net._balance_events.append(dict(stage=stage,tag=tag,Q=clone(Q),ionic_state=ionic_state(sim),boundary_state=sim.c_env_bound.copy(),simulator_fields={key:clone(getattr(sim,key)) for key in ("extra_rho_cells","extra_rho_env","extra_J_mem","extra_Jenv_x","extra_Jenv_y") if hasattr(sim,key)},charge_has_been_balanced=net.charge_has_been_balanced,substances_affect_charge=p.substances_affect_charge))
"""
for path in (source, native):
    text = path.read_text() + observe
    # Wire is complete for cold partial failures and subsequent source points.
    needle = "        ion_boundary_state=clone(sim.c_env_bound),"
    assert text.count(needle) == 1
    text = text.replace(
        needle,
        needle
        + """\n        ionic_state=ionic_state(sim),
        balance_events=[] if core is None else clone(getattr(core,"_balance_events",[])),""",
        1,
    )
    needle = '    sim.c_env_bound = np.asarray(definition["ion_boundary_mM"], np.float64).copy()'
    if needle not in text:
        # ast.unparse uses single quotes in the production literal module.
        needle = (
            "    sim.c_env_bound = np.asarray(definition['ion_boundary_mM'], np.float64).copy()"
        )
    assert text.count(needle) == 1
    text = text.replace(
        needle,
        needle + """\n    sim.iNa,sim.iK,sim.iM=(sim.get_ion(name) for name in ("Na","K","M"))""",
        1,
    )
    needle = "    net.reactions_env, net.reactions_mit, net.channels, net.mit = "
    start = text.index(needle)
    line_end = text.index("\n", start)
    text = (
        text[:line_end]
        + """\n    net._balance_events=clone(raw["balance_events"])"""
        + text[line_end:]
    )
    # Extend the exact wire schema, never silently supply a missing cold trace.
    needle = '"simulator_fields",'
    # Replace only the restore_owner set, not the wire field name.
    restore_start = text.index("def restore_owner(")
    restore_end = text.index("def attach_observers(", restore_start)
    block = text[restore_start:restore_end]
    if needle in block:
        block = block.replace(
            needle, needle + '\n        "ionic_state",\n        "balance_events",', 1
        )
    else:
        needle = "'simulator_fields'"
        assert needle in block
        block = block.replace(needle, needle + ", 'ionic_state', 'balance_events'", 1)
    text = text[:restore_start] + block + text[restore_end:]
    path.write_text(text)

# The source initializer returns actual compensated ionic values, and the
# outer owner adopts them before the first ordinary timestep; Vm/GJ and all
# other pre-existing fields remain actual source values, not rebalanced.
text = source.read_text()
needle = "    return cache(net)\n"
start = text.index("def initialize_cache(")
pos = text.index(needle, start)
text = (
    text[:pos]
    + """    return cache(net), ions.Values(*(np.array(value,copy=True) for value in arrays))
"""
    + text[pos + len(needle) :]
)
source.write_text(text)
outer = ROOT / ("src/cells/processes/" + NEW + "_join.py")
text = outer.read_text().replace(
    "        grn_cache = network_source.initialize_cache(",
    "        grn_cache, compensated_values = network_source.initialize_cache(",
    1,
)
needle = "    return _state(\n        binding,\n        parent,\n        caches,"
assert text.count(needle) == 1
text = text.replace(
    needle,
    """    ib=binding.pump_binding.gated_binding.material_binding
    material_parent=vector_state(ib,compensated_values._asdict(),step_index=parent.gated.material.step_index)
    gate_parent=gated._state(binding.pump_binding.gated_binding,material_parent,parent.gated.memory,parent.gated.initialization)
    parent=pump._state(binding.pump_binding,gate_parent,parent.rate_proxy_mol_m2_s)
"""
    + needle,
    1,
)
outer.write_text(text)
print(
    "Created charged-only source/native/outer skeletons and literal balance observations; no scientific execution"
)
