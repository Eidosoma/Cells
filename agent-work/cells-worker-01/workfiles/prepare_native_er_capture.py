# ruff: noqa: E501
"""Prepare original-source ER capture without importing scientific modules."""

import ast
from pathlib import Path

ROOT = Path("/home/robert/Cells")


def main():
    # Copy the stdlib AST observation transform, not generated production code.
    generator = ast.parse(
        (ROOT / "agent-work/cells-worker-01/workfiles/prepare_native_endoretic.py").read_text()
    )
    functions = [
        n
        for n in generator.body
        if isinstance(n, ast.FunctionDef) and n.name in ("call", "literal_nodes")
    ]
    transform = "\n\n".join(ast.unparse(n) for n in functions)
    transform = transform.replace("def literal_nodes():", "def literal_nodes(original):").replace(
        "ORIGINAL /", "original /"
    )
    header = '''"""Authenticated original EndoRetic methods with observational hooks only."""
import ast
import copy
import hashlib
import json
from pathlib import Path
from types import MethodType, SimpleNamespace

import numpy as np

PROTOCOL = Path(__file__).with_name('betse_normal_er_join_protocol.json')
FIELDS = ('cc_er','er_vol','er_sa','Ver','Q','cm_er','Dm_er','Dm_er_base','Dm_channels','zer')

'''
    footer = """
def authenticated():
    pins = json.loads(PROTOCOL.read_text())['native_source']
    for name in ('betse/science/organelles/endo_retic.py','betse/science/sim_toolbox.py'):
        data = (Path(pins['checkout'])/name).read_bytes()
        if hashlib.sha256(data).hexdigest() != pins['source_sha256'][name] or data != (Path(pins['installed_package']).parent/name).read_bytes():
            raise ValueError('Original ER source changed: '+name)
    nodes = literal_nodes(Path(pins['checkout'])/'betse/science')
    ns = dict(np=np,copy=copy,SimpleNamespace=SimpleNamespace)
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[])),'<authenticated original ER>','exec'),ns)
    ns['stb'] = SimpleNamespace(pumpCaER=ns['_pumpCaER'],electroflux=ns['_electroflux'])
    return ns


def setup(sim,cells,p,policy,owner_context,incoming_state):
    ns = authenticated()
    for name,value in policy['endoretic'].items():setattr(p,name,value)
    for name,row in owner_context.items():
        concentrations = {'IP3':np.asarray(row['IP3_mM'],np.float64).copy()} if row['contains_IP3'] else {}
        owner = None if not row['present'] else SimpleNamespace(molecules={'IP3':True} if row['contains_IP3'] else {},cell_concs=concentrations) if name=='molecules' else SimpleNamespace(core=SimpleNamespace(cell_concs=concentrations))
        setattr(sim,name,owner)
    cls = ns['_LiteralEndoRetic']
    if incoming_state is None:
        er = cls(sim,cells,p)
    else:
        er = object.__new__(cls)
        for name in FIELDS:
            if name == 'cc_er':sim.cc_er=np.array(incoming_state[name],copy=True)
            else:setattr(er,name,copy.deepcopy(incoming_state[name]))
    def fields():return {name:copy.deepcopy(sim.cc_er if name=='cc_er' else getattr(er,name)) for name in FIELDS}
    trace = dict(initial_state=fields(),frames=[],arithmetic={},owner_context=copy.deepcopy(owner_context),after=None)
    def observe(stage,actual,index,flux):
        trace['frames'].append(dict(stage=stage,ion_id=None if index is None else next(name for name in p.ions_dict if sim.get_ion(name)==index),cytosol_mM=actual.cc_cells.copy(),fields=fields(),flux_mol_m2_s=None if flux is None else flux.copy()))
    er._observe = observe
    original_update=cls.update
    def update(actual,live_sim,geometry,params):
        trace['frames'].clear();trace['arithmetic'].clear()
        observe('initial',live_sim,None,None)
        params._observe=lambda name,value:trace['arithmetic'].__setitem__(name,np.array(value,copy=True))
        try:return original_update(actual,live_sim,geometry,params)
        finally:
            trace['after']=fields()
            del params._observe
    er.update=MethodType(update,er)
    sim.endo_retic=er
    return trace
"""
    with (ROOT / "validation/betse/betse_normal_er_join_native_er.py").open("x") as stream:
        stream.write(header + transform + "\n" + footer)
    source = (ROOT / "validation/betse/betse_normal_calcium_join_native_helpers.py").read_text()
    source = source.replace(
        "betse_normal_calcium_join_protocol.json", "betse_normal_er_join_protocol.json"
    )
    source = source.replace(
        "from validation.betse import betse_normal_ion_join_native as material_native",
        "from validation.betse import betse_normal_ion_join_native as material_native\nfrom validation.betse import betse_normal_er_join_native_er as er_native",
    )
    source = source.replace("*, calcium_live):", "*, calcium_live, er_context, incoming_er_state):")
    source = source.replace('policy["Ca_dyn"] != 0', 'policy["Ca_dyn"] != 1').replace(
        "p.Ca_dyn = 0\n", "p.Ca_dyn = 1\n"
    )
    source = source.replace(
        "Active CaATP requires explicit Ca_dyn0; ER/buffers separate",
        "New ER capture requires explicit Ca_dyn1",
    )
    source = source.replace(
        '(policy["maintained"] | policy["kinetics"]).items()',
        '(policy["maintained"] | policy["kinetics"]).items()',
    )
    needle = "    calcium_observations = {}"
    assert source.count(needle) == 1
    source = source.replace(
        needle,
        "    er_trace = er_native.setup(sim,cells,p,policy,er_context,incoming_er_state)\n"
        + needle,
    )
    source = source.replace("Ca_dyn=0,", "Ca_dyn=1,")
    source = source.replace(
        'key not in {"gj_funk", "dyna"}',
        'key not in {"gj_funk", "dyna", "endo_retic", "molecules", "metabo", "grn"}',
    )
    source = source.replace(
        "        initializations=initializations,",
        "        endoretic=er_trace,\n        initializations=initializations,",
    )
    with (ROOT / "validation/betse/betse_normal_er_join_native_helpers.py").open("x") as stream:
        stream.write(source)
    source = (ROOT / "validation/betse/betse_normal_calcium_join_native.py").read_text()
    source = (
        source.replace(
            "betse_normal_calcium_join_native_helpers", "betse_normal_er_join_native_helpers"
        )
        .replace("betse_normal_calcium_join_protocol.json", "betse_normal_er_join_protocol.json")
        .replace(
            "cells.native_normal_calcium_join_capture@1", "cells.native_normal_er_join_capture@1"
        )
    )
    source = source.replace(
        "    calcium_live=None,\n",
        "    calcium_live=None,\n    er_context=None,\n    incoming_er_state=None,\n",
    )
    needle = '    source["_late"], channel_capture = channel_helpers.setup('
    assert source.count(needle) == 1
    source = source.replace(
        needle,
        '    cells.cell_sa=np.asarray(inputs["er_cell_area_m2"],np.float64)\n    parameters.cm=inputs["er_capacitance_F_m2"]\n'
        + needle,
    )
    source = source.replace(
        "        calcium_live=calcium_live,",
        "        calcium_live=calcium_live,\n        er_context=er_context,\n        incoming_er_state=incoming_er_state,",
    )
    source = source.replace(
        'key not in {"gj_funk", "dyna"}',
        'key not in {"gj_funk", "dyna", "endo_retic", "molecules", "metabo", "grn"}',
    )
    source = source.replace(
        "    channel_initialization_failure = None",
        "    er_state_cache = None\n    channel_initialization_failure = None",
    )
    needle = '                    definition=inputs["ion_definition"], initial=state, steps=[forcing["material"]]'
    assert source.count(needle) == 1
    source = source.replace(
        needle,
        needle
        + ',\n                    er_cell_area_m2=inputs["current_definition"]["geometry"]["cell_area_m2"],\n                    er_capacitance_F_m2=inputs["voltage_definition"]["parameters"]["capacitance_F_m2"]',
    )
    source = source.replace(
        '                forcing["calcium"],',
        '                forcing["calcium"],\n                forcing["er_context"],\n                er_state_cache,',
    )
    source = source.replace(
        '        pump_rate_cache = material["rate_proxy_after"]',
        '        er_state_cache=copy.deepcopy(material["channel_capture"]["endoretic"]["after"])\n        pump_rate_cache = material["rate_proxy_after"]',
    )
    with (ROOT / "validation/betse/betse_normal_er_join_native.py").open("x") as stream:
        stream.write(source)


if __name__ == "__main__":
    main()
