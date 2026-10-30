# ruff: noqa: E501 -- source templates are formatted in their outputs.
"""Append complete state wiring and emit an independently original-AST native GRN."""

import ast
import copy
from pathlib import Path

ROOT = Path("/home/robert/Cells")
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
template = (WORK / "grn_owner_adapter_template.txt").read_text()
source_path = ROOT / "src/cells/processes/betse_normal_grn_source.py"
source_path.write_text(
    source_path.read_text().replace(
        "from collections.abc import MutableMapping",
        "from collections.abc import Mapping, MutableMapping",
    )
    + "\n"
    + template
    + """

def literals():
    return dict(MasterOfGenes=MasterOfGenes,MasterOfNetworks=MasterOfNetworks,Molecule=Molecule,Reaction=feedback_source.Reaction,Modulator=feedback_source.Modulator,DynamicValue=DynamicValue,DynamicValueDict=DynamicValueDict,initialize_owner=initialize_owner,dispatch=dispatch)
"""
)

# Copy only stdlib original-AST construction code. Native scientific bodies
# always come from the authenticated checkout; no production module import.
generator = ast.parse((WORK / "prepare_native_grn_package.py").read_text())
selected = [
    node
    for node in generator.body
    if isinstance(node, (ast.FunctionDef, ast.ClassDef))
    and node.name in {"statement", "Clean", "original_nodes"}
]
native = '''# ruff: noqa: B007, B905, E501
"""Independent original-AST GRN lifecycle, owner and dispatch capture."""
import ast
import copy
import hashlib
import json
from abc import ABCMeta
from collections import OrderedDict
from collections.abc import Mapping, MutableMapping
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from validation.betse import betse_normal_molecule_join_native_network as previous

PROTOCOL = Path(__file__).with_name("betse_normal_grn_join_protocol.json")
_LITERAL = None

def _outside_scope(*args,**kwargs):
    raise ValueError("Separate mitochondria, asymmetry, optimizer or profile state required")

'''
native += ast.unparse(
    ast.fix_missing_locations(ast.Module(body=copy.deepcopy(selected), type_ignores=[]))
)
native += """

def literal_nodes(root):
    base=previous.literal_nodes(root)
    net=next(node for node in base if getattr(node,"name",None)=="_LiteralNetwork")
    net.name="MasterOfNetworks"
    original=original_nodes(root)
    added=next(node for node in original if getattr(node,"name",None)=="MasterOfNetworks")
    net.body.extend(added.body)
    return [node for node in original if getattr(node,"name",None) not in {"MasterOfNetworks","MasterOfGenes","initialize_owner","dispatch"}]+base+[node for node in original if getattr(node,"name",None) in {"MasterOfGenes","initialize_owner","dispatch"}]

def authenticated():
    pins=json.loads(PROTOCOL.read_text())["native_source"]
    for name,digest in pins["source_sha256"].items():
        data=(Path(pins["checkout"])/name).read_bytes()
        assert hashlib.sha256(data).hexdigest()==digest
        assert data==(Path(pins["installed_package"]).parent/name).read_bytes()
    ns=dict(np=np,copy=copy,ABCMeta=ABCMeta,OrderedDict=OrderedDict,SimpleNamespace=SimpleNamespace,MappingMutableType=MutableMapping,types=SimpleNamespace(trim=repr),BetseMethodUnimplementedException=NotImplementedError,BetseSimConfException=ValueError,logs=SimpleNamespace(log_info=lambda *_:None,log_warning=lambda *_:None),tex_val=str,Mito=_outside_scope,mods=SimpleNamespace(),fd=SimpleNamespace(gradient=_outside_scope,divergence=_outside_scope,integrator=_outside_scope),div_env=_outside_scope,nernst_planck_flux=_outside_scope)
    nodes=literal_nodes(Path(pins["checkout"])/"betse")
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[])),"<original GRN owner lifecycle and normal dispatch>","exec"),ns)
    ns["stb"]=SimpleNamespace(molecule_mover=ns["molecule_mover"],no_negs=ns["no_negs"],map_to_cells=_outside_scope)
    return ns

def literals():
    global _LITERAL
    if _LITERAL is None:
        _LITERAL=authenticated()
    return _LITERAL

def initial_cache(definition):
    return None

def dispatch_owner(sim,t,phase,cells,p):
    return literals()["dispatch"](sim,t,phase,cells,p)
"""
native += (
    "\n"
    + template
    + """

def attach(net,sim,cells,p,definition,incoming_controls,incoming_cache,stb,*,ion_ids,dynamic_value,dynamic_dict):
    configure_owner_context(sim,cells,p,definition)
    sim.gj_block=np.asarray(incoming_controls["gj_block"],np.float64).copy()
    sim.NaKATP_block=np.asarray(incoming_controls["NaKATP_block"],np.float64).copy()
    if incoming_cache is None:
        net=cold_owner(sim,cells,p,definition)
        incoming_cache=cache(net)
        cold=True
    else:
        net=restore_owner(sim,cells,p,definition,incoming_cache)
        cold=False
    trace=attach_observers(net,sim,p,incoming_cache)
    trace["cold_initialization"]=cold
    return net,sim.grn,trace
"""
)
with (ROOT / "validation/betse/betse_normal_grn_join_native_network.py").open("x") as stream:
    stream.write(native)
helper = ROOT / "validation/betse/betse_normal_grn_join_native_helpers.py"
text = helper.read_text().replace(
    "    feedback = network_native.attach(",
    "    try:\n        net, owner, feedback = network_native.attach(",
)
start = text.index("    try:\n        net, owner, feedback = network_native.attach(")
stop = text.index("    phase = SimpleNamespace(", start)
block = text[start:stop]
lines = block.splitlines()
block = "\n".join(lines[:2] + ["    " + line for line in lines[2:]]) + "\n"
block += """    except network_native.GRNInitializationRefused as error:
        raise NativeChannelInitializationRefused(error,error.partial) from error
"""
text = text[:start] + block + text[stop:]
start = text.index('        ns["clear_run_loop"](net, actual)')
stop = text.index("        publication.update(", start)
text = (
    text[:start]
    + """        stages=[]
        def dispatched(stage,simulator,actual_phase):
            stages.append(stage)
            observe("grn_"+stage,None,simulator)
            if stage=="clear_run_loop":
                feedback.update(values_before=material_native.values(actual),molecule_states_before=network_native.snapshot(net.molecules),controls_before=dict(gj_block=actual.gj_block.copy(),NaKATP_block=actual.NaKATP_block.copy()),incoming_channel_current_A_m2=net.extra_J_mem.copy(),grn_owner=network_native.owner_evidence(actual))
        net._observe_dispatch=dispatched
        try:
            network_native.dispatch_owner(actual,t,phase,geometry,params)
            feedback.update(source_completed=True,configured_chemistry_run_loop_completed=True)
        finally:
            feedback.update(cache_after=network_native.cache(net),chemical_rhs_evaluated=any(row["stage"]=="rhs_ready" for row in feedback["molecule_frames"]),executed_chemistry=any(row["stage"]=="rhs_ready" for row in feedback["molecule_frames"]),molecular_transports_completed=sum(row["stage"]=="transport_after" for row in feedback["molecule_frames"]),molecule_states_after=network_native.snapshot(net.molecules),values_after=material_native.values(actual),controls_after=dict(gj_block=actual.gj_block.copy(),NaKATP_block=actual.NaKATP_block.copy()),grn_dispatch_stages=tuple(stages),grn_owner_after=network_native.owner_evidence(actual))
"""
    + text[stop:]
)
helper.write_text(text)
native_path = ROOT / "validation/betse/betse_normal_grn_join_native.py"
text = native_path.read_text().replace(
    'stage="channel_initialization"', 'stage="grn_initialization"'
)
native_path.write_text(text)
print("Emitted two independent complete owner-state bridges and genuine native dispatch wiring")
