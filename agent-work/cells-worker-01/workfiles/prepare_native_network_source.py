# ruff: noqa: E501
"""Prepare literal network builders/run_loop as source text; execute no chemistry."""

import ast
import copy
from pathlib import Path

ROOT = Path("/home/robert/Cells")
SOURCE = Path("/mnt/workspaces/Cells/betse-v1.5.0/betse/science/chemistry/networks.py")
METHODS = (
    "read_reactions",
    "default_zones",
    "get_influencers",
    "write_reactions",
    "write_growth_and_decay",
    "create_reaction_matrix",
    "read_modulators",
    "clear_run_loop",
    "run_loop_modulators",
    "run_loop",
    "energy_charge",
)


def literal_nodes(path):
    tree = ast.parse(path.read_text())
    classes = {n.name: n for n in tree.body if isinstance(n, ast.ClassDef)}

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

    result = []
    for name, selected in [
        ("MasterOfNetworks", METHODS),
        ("Reaction", ("__init__",)),
        ("Modulator", ("__init__", "init_modulator")),
    ]:
        nodes = [
            Clean().visit(copy.deepcopy(n))
            for n in classes[name].body
            if isinstance(n, ast.FunctionDef) and n.name in selected
        ]
        assert {n.name for n in nodes} == set(selected)
        result.append(
            ast.ClassDef(
                name="_LiteralNetwork" if name == "MasterOfNetworks" else name,
                bases=[],
                keywords=[],
                body=nodes,
                decorator_list=[],
            )
        )
    return result


HEADER = '''"""Literal ion-only late network chemistry and control writes.

Native source expressions execute here. Existing standalone components validate
the supported configuration/domain and provide separate comparison targets.
No molecule transport, supplied chemistry outputs or GRN owner dynamics are
invented. Static preparation only; numerical qualification has not run.
"""
from collections import OrderedDict
from collections.abc import MutableMapping
from types import SimpleNamespace

import numpy as np

from cells.processes import betse_calcium_atp_source as calcium_source
from cells.processes import betse_network_modulation as modulation
from cells.processes import betse_network_reactions as reactions
from cells.processes import betse_normal_ion_join as ions

logs=SimpleNamespace(log_info=lambda *_:None,log_warning=lambda *_:None)
tex_val=str
BetseSimConfException=ValueError
stb=SimpleNamespace(no_negs=calcium_source._no_negs)

'''

FOOTER = '''

class RowAliases(MutableMapping):
    """Explicit current-row ownership, independently captured against DynamicValueDict."""
    def __init__(self,sim,attribute,names):
        self.sim,self.attribute,self.names=sim,attribute,tuple(names)
    def __getitem__(self,key):return getattr(self.sim,self.attribute)[self.names.index(key)]
    def __setitem__(self,key,value):getattr(self.sim,self.attribute)[self.names.index(key)]=value
    def __delitem__(self,key):raise ValueError('Native ion row ownership cannot be deleted')
    def __iter__(self):return iter(self.names)
    def __len__(self):return len(self.names)


def validate(definition, ion_binding, current_binding, configured_temperature_K):
    if not isinstance(definition,dict) or set(definition)!={'owner','reactions','modulators','initial_controls','provenance'} or definition['owner'] not in ('molecules','grn') or not isinstance(definition['provenance'],str) or not definition['provenance'].strip():
        raise ValueError('Require one explicitly enabled native network owner and complete declaration')
    rows,mods=definition['reactions'],definition['modulators']
    if not isinstance(rows,list) or not 1<=len(rows)<=8 or not isinstance(mods,list) or len(mods)>8:
        raise ValueError('Require bounded nonempty ionic cell chemistry and ordered modulators')
    for row in rows:
        if row.get('reaction zone')!='cell' or not row.get('name','').isidentifier():
            raise ValueError('First seam supports cell-zone ionic reactions only')
        for key in ('activator zone','inhibitor zone'):
            if row.get(key) not in (None,'None',[]) and any(z!='cell' for z in row[key]):
                raise ValueError('Ionic cell reaction regulators must have cell owners')
    for row in mods:
        if row.get('target') not in ('GJ','Na/K-ATPase') or not row.get('name','').isidentifier() or type(row.get('max effect')) not in (int,float) or row['max effect']<0:
            raise ValueError('First seam supports nonnegative GJ/NaK source modulators')
        for key in ('activators','inhibitors'):
            labels=row.get(key)
            if labels not in (None,'None',[]) and any(not name.isidentifier() for name in labels):
                raise ValueError('First seam uses ordinary nonnegative ion Hill regulators')
    m,n=len(ion_binding.membrane_ids),len(ion_binding.cell_ids)
    names,valence=ion_binding.ion_ids,ion_binding.kernel.valence
    if any(not name.isidentifier() for name in names):raise ValueError('Require native ion identifiers')
    # Reuse frozen standalone readers/domain validation; literal stepping below
    # deliberately retains the source arithmetic grouping and raw quotients.
    reactions.bind(rows,[],names,valence,['cell']*n,temperature_K=configured_temperature_K,
                   gas_constant_J_mol_K=ion_binding.kernel.R_J_mol_K)
    modulation.bind(mods,[],names,valence,list(range(m)),m,names,tj_targets=[False]*m,
                    faraday_C_mol=ion_binding.kernel.F_C_mol,gas_constant_J_mol_K=ion_binding.kernel.R_J_mol_K,
                    temperature_K=configured_temperature_K)
    controls(definition['initial_controls'],m)
    if not np.array_equal(current_binding.kernel.valence,valence):
        raise ValueError('Current and chemical ion valences must share an axis')


def controls(raw,m):
    if not isinstance(raw,dict) or set(raw)!={'gj_block','NaKATP_block'}:
        raise ValueError('Require both owned native control vectors')
    result={}
    for name,value in raw.items():
        array=np.asarray(value,np.float64)
        if array.shape!=(m,) or not np.isfinite(array).all() or np.any(array<0):
            raise ValueError('Require finite nonnegative native control: '+name)
        result[name]=ions.freeze(array)
    return ions.freeze(result)


def prepare(arrays, *, ion_ids, parameters, definition, incoming_controls, incoming_cache, phase_kind):
    cell,membrane,bath,vm,*_=arrays
    n,m=cell.shape[1],len(vm)
    owned=controls(ions.data(incoming_controls),m)
    sim=SimpleNamespace(cc_cells=cell,cc_at_mem=membrane,cc_env=bath,vm=vm,
                        T=parameters['runtime_temperature_K'],cdl=n,mdl=m,edl=m,
                        gj_block=np.array(owned['gj_block'],copy=True),NaKATP_block=np.array(owned['NaKATP_block'],copy=True))
    sim.get_ion=lambda name:ion_ids.index(name)
    p=SimpleNamespace(R=parameters['R'],F=parameters['F'],dt=parameters['dt_s'],
                      is_ecm=False,ions_dict={name:1 for name in ion_ids},
                      substances_affect_charge=parameters['substances_affect_charge'])
    cells=SimpleNamespace(cell_i=np.arange(n),mem_i=np.arange(m))
    net=_LiteralNetwork()
    net.molecules=OrderedDict();net.mit_enabled=False;net.reactions_mit=OrderedDict();net.reactions_env=OrderedDict()
    net.cell_concs=RowAliases(sim,'cc_cells',ion_ids)
    net.mem_concs=RowAliases(sim,'cc_at_mem',ion_ids)
    net.env_concs=RowAliases(sim,'cc_env',ion_ids)
    net.zmol={name:parameters['valence'][i] for i,name in enumerate(ion_ids)}
    net.reaction_rates=None
    if incoming_cache is not None:
        for key in ('reaction_rates','delta_conc','delta_conc_env','chi'):
            if key in incoming_cache:setattr(net,key,copy_value(incoming_cache[key]))
    net.read_reactions(ions.data(definition['reactions']),sim,cells,p)
    net.write_reactions();net.write_growth_and_decay();net.create_reaction_matrix()
    net.read_modulators(ions.data(definition['modulators']),sim,cells,p)
    net.clear_run_loop(sim)
    return net,sim,cells,p,SimpleNamespace(sim=sim,cells=cells,p=p,kind=phase_kind)


def copy_value(value):
    return np.array(value,copy=True) if isinstance(value,np.ndarray) else value


def cache(net):
    return ions.freeze(dict(
        reaction_rates=copy_value(net.reaction_rates),delta_conc=copy_value(net.delta_conc),
        delta_conc_env=copy_value(net.delta_conc_env),chi=copy_value(net.chi),
        reaction_matrix=net.reaction_matrix.copy(),
        reaction_expressions={name:row.reaction_eval_string for name,row in net.reactions.items()},
        modulator_expressions={name:row.alpha_eval_string for name,row in net.modulators.items()},
        extra_rho_cells=net.extra_rho_cells.copy(),extra_J_mem=net.extra_J_mem.copy()))
'''


def main():
    nodes = literal_nodes(SOURCE)
    with (ROOT / "src/cells/processes/betse_normal_network_join_source.py").open("x") as stream:
        stream.write(
            HEADER
            + "\n\n".join(ast.unparse(ast.fix_missing_locations(n)) for n in nodes)
            + "\n"
            + FOOTER
        )


if __name__ == "__main__":
    main()
