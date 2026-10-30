# ruff: noqa: E501
"""Prepare an independent pinned-source feedback capture; execute no science."""

import ast
from pathlib import Path

ROOT = Path("/home/robert/Cells")


def main():
    tree = ast.parse(
        (ROOT / "agent-work/cells-worker-01/workfiles/prepare_native_network_source.py").read_text()
    )
    methods = next(
        n
        for n in tree.body
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "METHODS" for t in n.targets)
    )
    builder = next(
        n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "literal_nodes"
    )
    header = '''# ruff: noqa: B007, B905, E501
"""Native network builders and control writes from authenticated original AST."""
import ast
import copy
import hashlib
import json
from collections import OrderedDict
from pathlib import Path
from types import MethodType, SimpleNamespace

import numpy as np

PROTOCOL=Path(__file__).with_name('betse_normal_network_join_protocol.json')
'''
    footer = """
def authenticated(stb):
    pins=json.loads(PROTOCOL.read_text())['native_source']
    name='betse/science/chemistry/networks.py';path=Path(pins['checkout'])/name
    data=path.read_bytes()
    assert hashlib.sha256(data).hexdigest()==pins['source_sha256'][name]
    assert data==(Path(pins['installed_package']).parent/name).read_bytes()
    nodes=literal_nodes(path)
    cls=next(n for n in nodes if n.name=='_LiteralNetwork')
    method=next(n for n in cls.body if n.name=='run_loop_modulators')
    loop=next(n for n in method.body if isinstance(n,ast.For))
    loop.body.append(ast.parse('self._observe_control(name,modulator,sim)').body[0])
    ns=dict(np=np,OrderedDict=OrderedDict,SimpleNamespace=SimpleNamespace,stb=stb,
            logs=SimpleNamespace(log_info=lambda *_:None,log_warning=lambda *_:None),
            tex_val=str,BetseSimConfException=ValueError)
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[])),str(path),'exec'),ns)
    return ns['_LiteralNetwork']


def cache(net):
    fields=('reaction_rates','delta_conc','delta_conc_env','chi')
    return dict(present_fields=tuple(name for name in fields if hasattr(net,name)),
        reaction_rates=copy.deepcopy(getattr(net,'reaction_rates',None)),
        delta_conc=copy.deepcopy(getattr(net,'delta_conc',None)),
        delta_conc_env=copy.deepcopy(getattr(net,'delta_conc_env',None)),
        chi=copy.deepcopy(getattr(net,'chi',None)),reaction_matrix=net.reaction_matrix.copy(),
        reaction_expressions={name:row.reaction_eval_string for name,row in net.reactions.items()},
        modulator_expressions={name:row.alpha_eval_string for name,row in net.modulators.items()},
        extra_rho_cells=net.extra_rho_cells.copy(),extra_J_mem=net.extra_J_mem.copy())


def attach(net,sim,cells,p,definition,incoming_controls,incoming_cache,stb):
    cls=authenticated(stb)
    for name in METHODS:setattr(net,name,MethodType(getattr(cls,name),net))
    sim.gj_block=np.asarray(incoming_controls['gj_block'],np.float64).copy()
    sim.NaKATP_block=np.asarray(incoming_controls['NaKATP_block'],np.float64).copy()
    cells.map_mem2ecm=np.asarray(definition['membrane_to_environment'],np.int64)
    net.reaction_rates=None
    if incoming_cache is not None:
        for name in incoming_cache['present_fields']:setattr(net,name,copy.deepcopy(incoming_cache[name]))
    net.read_reactions(definition['reactions'],sim,cells,p)
    net.write_reactions();net.write_growth_and_decay();net.create_reaction_matrix()
    net.read_modulators(definition['modulators'],sim,cells,p)
    trace=dict(cache_before=copy.deepcopy(incoming_cache),control_writes=[],source_completed=False,executed_chemistry=False)
    def observe(name,value,actual):
        trace['control_writes'].append(dict(rule_id=name,target=net.modulators[name].target_label,
            value=np.array(value,copy=True),gj_block=np.array(actual.gj_block,copy=True),
            NaKATP_block=np.array(actual.NaKATP_block,copy=True)))
    net._observe_control=observe
    return trace
"""
    with (ROOT / "validation/betse/betse_normal_network_join_native_network.py").open("x") as f:
        f.write(header + ast.unparse(methods) + "\n" + ast.unparse(builder) + "\n" + footer)
    source = (
        (ROOT / "validation/betse/betse_normal_calcium_join_native_helpers.py")
        .read_text()
        .replace(
            "betse_normal_calcium_join_protocol.json", "betse_normal_network_join_protocol.json"
        )
    )
    source = source.replace(
        "from validation.betse import betse_normal_ion_join_native as material_native",
        "from validation.betse import betse_normal_ion_join_native as material_native\nfrom validation.betse import betse_normal_network_join_native_network as network_native",
    )
    source = source.replace(
        "*, calcium_live):", "*, calcium_live, incoming_network_controls, incoming_network_cache):"
    )
    marker = '    net.energy_charge = MethodType(ns["energy_charge"], net)'
    assert source.count(marker) == 1
    source = source.replace(
        marker,
        marker
        + """
    feedback=network_native.attach(net,sim,cells,p,definition['network'],incoming_network_controls,incoming_network_cache,source['stb'])""",
    )
    marker = '        ns["run_loop"](net, phase, t)'
    assert source.count(marker) == 1
    source = source.replace(
        marker,
        """
        feedback.update(values_before=material_native.values(actual),
            controls_before=dict(gj_block=np.array(actual.gj_block,copy=True),NaKATP_block=np.array(actual.NaKATP_block,copy=True)),
            incoming_channel_current_A_m2=net.extra_J_mem.copy())
        try:
            net.run_loop_modulators(actual,geometry,params)
            observe('network_modulators',None,actual)
            net.run_loop(phase,t)
            observe('network_chemistry_empty',None,actual)
            feedback.update(source_completed=True,empty_chemistry_run_loop_executed=True)
        finally:
            feedback.update(cache_after=network_native.cache(net),values_after=material_native.values(actual),
                controls_after=dict(gj_block=np.array(actual.gj_block,copy=True),NaKATP_block=np.array(actual.NaKATP_block,copy=True)))""",
    )
    source = source.replace(
        "        initializations=initializations,",
        "        network_feedback=feedback,\n        initializations=initializations,",
    )
    with (ROOT / "validation/betse/betse_normal_network_join_native_helpers.py").open("x") as f:
        f.write(source)
    source = (
        (ROOT / "validation/betse/betse_normal_calcium_join_native.py")
        .read_text()
        .replace(
            "betse_normal_calcium_join_native_helpers", "betse_normal_network_join_native_helpers"
        )
        .replace(
            "betse_normal_calcium_join_protocol.json", "betse_normal_network_join_protocol.json"
        )
        .replace(
            "cells.native_normal_calcium_join_capture@1",
            "cells.native_normal_network_join_capture@1",
        )
    )
    source = source.replace(
        "    calcium_live=None,",
        "    calcium_live=None,\n    incoming_network_controls=None,\n    incoming_network_cache=None,",
    )
    source = source.replace(
        "        calcium_live=calcium_live,",
        "        calcium_live=calcium_live,\n        incoming_network_controls=incoming_network_controls,\n        incoming_network_cache=incoming_network_cache,",
    )
    source = source.replace(
        "    channel_initialization_failure = None",
        '    network_controls=copy.deepcopy(inputs["channel_definition"]["network"]["initial_controls"])\n    network_cache=None\n    channel_initialization_failure = None',
    )
    marker = '    for index, forcing in enumerate(inputs["drives"]):'
    assert source.count(marker) == 1
    source = source.replace(
        marker,
        marker
        + """
        forcing=copy.deepcopy(forcing)
        if forcing.get('scheduled_controls') is not None:network_controls=copy.deepcopy(forcing['scheduled_controls'])
        forcing['material']['junction_block']=copy.deepcopy(network_controls['gj_block'])
        forcing['pump']['block']=copy.deepcopy(network_controls['NaKATP_block'])""",
    )
    source = source.replace(
        '                forcing["calcium"],',
        '                forcing["calcium"],\n                network_controls,\n                network_cache,',
    )
    marker = '        pump_rate_cache = material["rate_proxy_after"]'
    source = source.replace(
        marker,
        """        network_controls=copy.deepcopy(material['channel_capture']['network_feedback']['controls_after'])
        network_cache=copy.deepcopy(material['channel_capture']['network_feedback']['cache_after'])
"""
        + marker,
    )
    a = source.index("\ndef helper_probe(")
    b = source.index("\ndef read_raw_capture_inputs(", a)
    source = source[:a] + "\n" + source[b:]
    source = source.replace(
        'result = helper_probe(payload) if payload.get("helper_probe") else evaluate(payload)',
        "result = evaluate(payload)",
    )
    with (ROOT / "validation/betse/betse_normal_network_join_native.py").open("x") as f:
        f.write(source)


if __name__ == "__main__":
    main()
