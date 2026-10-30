# ruff: noqa: E501
"""Static source extraction for a new owned EndoRetic prefix; no model import."""

import ast
import copy
from pathlib import Path

ROOT = Path("/home/robert/Cells")
ORIGINAL = Path("/mnt/workspaces/Cells/betse-v1.5.0/betse/science")


def call(expression):
    return ast.parse(expression).body[0]


def literal_nodes():
    toolbox = ast.parse((ORIGINAL / "sim_toolbox.py").read_text())
    pump = copy.deepcopy(
        next(n for n in toolbox.body if isinstance(n, ast.FunctionDef) and n.name == "pumpCaER")
    )
    pump.name = "_pumpCaER"
    labels = {
        "Qnumo": "quotient_numerator",
        "Qdenomo": "quotient_denominator_raw",
        "Q": "quotient",
        "Keq": "equilibrium",
        "frwd": "forward",
        "bkwrd": "backward_unused",
        "f_Ca": "serca_flux_mol_m2_s",
    }
    body = []
    for node in pump.body:
        if (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            continue
        body.append(node)
        if (
            isinstance(node, ast.Assign)
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id in labels
        ):
            name = node.targets[0].id
            body.append(call("p._observe(" + repr(labels[name]) + "," + name + ")"))
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Subscript):
            body.append(call("p._observe('quotient_denominator_used',Qdenomo)"))
    pump.body = body
    flux = copy.deepcopy(
        next(n for n in toolbox.body if isinstance(n, ast.FunctionDef) and n.name == "electroflux")
    )
    flux.name = "_electroflux"
    flux.body = [
        n
        for n in flux.body
        if not (
            isinstance(n, ast.Expr)
            and isinstance(n.value, ast.Constant)
            and isinstance(n.value.value, str)
        )
    ]
    original = ast.parse((ORIGINAL / "organelles/endo_retic.py").read_text())
    er = copy.deepcopy(
        next(n for n in original.body if isinstance(n, ast.ClassDef) and n.name == "EndoRetic")
    )
    er.name = "_LiteralEndoRetic"
    er.body = [
        n
        for n in er.body
        if isinstance(n, ast.FunctionDef) and n.name in ("__init__", "get_v", "channels", "update")
    ]
    for method in er.body:
        method.body = [
            n
            for n in method.body
            if not (
                isinstance(n, ast.Expr)
                and isinstance(n.value, ast.Constant)
                and isinstance(n.value.value, str)
            )
        ]
        if method.name == "update":
            body = []
            for node in method.body:
                body.append(node)
                if (
                    isinstance(node, ast.Expr)
                    and isinstance(node.value, ast.Call)
                    and ast.unparse(node.value.func) == "self.channels"
                ):
                    body.append(call("self._observe('channels',sim,None,None)"))
                if (
                    isinstance(node, ast.Assign)
                    and ast.unparse(node.targets[0]) == "sim.cc_er[sim.iCa]"
                ):
                    body.append(call("self._observe('serca_commit',sim,sim.iCa,f_CaATP)"))
                if isinstance(node, ast.For):
                    node.body.append(call("self._observe('er_electroflux_commit',sim,i,f_ED)"))
                if (
                    isinstance(node, ast.Expr)
                    and isinstance(node.value, ast.Call)
                    and ast.unparse(node.value.func) == "self.get_v"
                ):
                    body.append(call("self._observe('charge_voltage',sim,None,None)"))
            method.body = body
    return [pump, flux, er]


HEADER = '''"""Literal EndoRetic state and update with explicitly owned all-ion arrays.

Static preparation only. Raw source negatives and nonfinite returns remain
observable; finite publication is checked separately. No explicit buffer or
finite-fuel chemistry is introduced.
"""
import copy
from dataclasses import dataclass, replace
from types import SimpleNamespace

import numpy as np

from cells.processes import betse_normal_ion_join as ions

FIELDS = ('cc_er','er_vol','er_sa','Ver','Q','cm_er','Dm_er','Dm_er_base','Dm_channels','zer')
PARAMETERS = ('serca_max','max_er','act_Km_Ca','act_n_Ca','inh_Km_Ca','inh_n_Ca','act_Km_IP3','act_n_IP3')

'''

FOOTER = """
stb = SimpleNamespace(pumpCaER=_pumpCaER, electroflux=_electroflux)


@dataclass(frozen=True, slots=True)
class OwnedState:
    binding_identity: str
    ion_ids: tuple
    cell_ids: tuple
    fields: object
    identity: str


@dataclass(frozen=True, slots=True)
class Trial:
    parent: OwnedState
    cytosol_before_mM: object
    cytosol_after_mM: object
    frames: tuple
    arithmetic: object
    raw_candidate: object
    candidate: object
    source_completed: bool
    finite: bool
    failure: object
    amount_change_mol: object
    amount_gross_mol: object


def state(binding_identity, ion_ids, cell_ids, fields):
    fields = ions.data(fields)
    count, n = len(ion_ids), len(cell_ids)
    if set(fields) != set(FIELDS):
        raise ValueError('Require every owned native ER field')
    values = {}
    for key in FIELDS:
        value = np.asarray(fields[key], np.float64)
        shape = () if key == 'cm_er' else (count,n) if key in ('cc_er','Dm_er','Dm_er_base','Dm_channels','zer') else (n,)
        if value.shape != shape or not np.isfinite(value).all():
            raise ValueError('Require finite explicitly shaped ER state: ' + key)
        if key in ('er_vol','er_sa','cm_er') and np.any(value <= 0):
            raise ValueError('Require positive ER geometry/capacitance')
        values[key] = float(value) if key == 'cm_er' else ions.freeze(value)
    result = OwnedState(binding_identity,tuple(ion_ids),tuple(cell_ids),ions.freeze(values),'')
    return replace(result,identity=ions.digest(result))


def initialize(binding_identity, ion_ids, cell_ids, cell_mol_m3, cell_volume_m3, cell_area_m2, valence, capacitance_F_m2):
    sim = SimpleNamespace(cc_cells=np.array(cell_mol_m3,copy=True), cdl=len(cell_ids),
                          iCa=ion_ids.index('Ca'),zs=np.array(valence,copy=True))
    cells = SimpleNamespace(cell_vol=np.array(cell_volume_m3,copy=True),cell_sa=np.array(cell_area_m2,copy=True))
    er = _LiteralEndoRetic(sim,cells,SimpleNamespace(cm=capacitance_F_m2))
    fields = {key:copy.deepcopy(getattr(er,key)) for key in FIELDS if key != 'cc_er'}
    fields['cc_er'] = sim.cc_er.copy()
    return state(binding_identity,ion_ids,cell_ids,fields)


def context(raw, n):
    if not isinstance(raw,dict) or set(raw) != {'molecules','metabo','grn'}:
        raise ValueError('Require explicit presence and IP3 membership for all three source owners')
    result = {}
    for name,row in raw.items():
        if not isinstance(row,dict) or set(row) != {'present','contains_IP3','IP3_mM'} or type(row['present']) is not bool or type(row['contains_IP3']) is not bool:
            raise ValueError('Require explicit native owner lookup context')
        if not row['present'] and row['contains_IP3']:
            raise ValueError('Absent owner cannot contain an IP3 entry')
        values = None
        if row['contains_IP3']:
            values = np.asarray(row['IP3_mM'],np.float64)
            if values.shape != (n,) or not np.isfinite(values).all():
                raise ValueError('Require explicit finite IP3 cell vector')
            values = ions.freeze(values)
        elif row['IP3_mM'] is not None:
            raise ValueError('Absent IP3 must be declared None')
        result[name] = dict(present=row['present'],contains_IP3=row['contains_IP3'],IP3_mM=values)
    return ions.freeze(result)


def _owners(raw):
    result = {}
    for name,row in raw.items():
        if not row['present']:
            result[name] = None
            continue
        concentrations = {'IP3':np.array(row['IP3_mM'],copy=True)} if row['contains_IP3'] else {}
        result[name] = SimpleNamespace(molecules={'IP3':True} if row['contains_IP3'] else {},cell_concs=concentrations) if name == 'molecules' else SimpleNamespace(core=SimpleNamespace(cell_concs=concentrations))
    return result


def step(parent, *, binding_identity, cytosol_mM, cell_volume_m3, moving_indices, valence, runtime_temperature_K, parameters, owner_context):
    checked = state(parent.binding_identity,parent.ion_ids,parent.cell_ids,parent.fields)
    if parent.binding_identity != binding_identity or checked.identity != parent.identity:
        raise ValueError('Changed ER state/binding association')
    if any(isinstance(v,np.ndarray) and v.flags.writeable for v in parent.fields.values()):
        raise ValueError('Require immutable owned ER buffers')
    live_context = context(ions.data(owner_context),len(parent.cell_ids))
    sim = SimpleNamespace(cc_cells=np.array(cytosol_mM,copy=True), cc_er=np.array(parent.fields['cc_er'],copy=True),
                          cdl=len(parent.cell_ids),iCa=parent.ion_ids.index('Ca'),
                          zs=np.array(valence,copy=True),movingIons=tuple(moving_indices),T=runtime_temperature_K,
                          **_owners(live_context))
    cells = SimpleNamespace(cell_vol=np.array(cell_volume_m3,copy=True))
    er = object.__new__(_LiteralEndoRetic)
    for key in FIELDS:
        if key != 'cc_er':setattr(er,key,copy.deepcopy(parent.fields[key]))
    frames, arithmetic = [],{}
    def raw_fields():
        return {key:copy.deepcopy(sim.cc_er if key == 'cc_er' else getattr(er,key)) for key in FIELDS}
    def observe(stage,actual,index,flux):
        frames.append(ions.freeze(dict(stage=stage,ion_id=None if index is None else parent.ion_ids[index],
                                      cytosol_mM=actual.cc_cells.copy(),fields=raw_fields(),
                                      flux_mol_m2_s=None if flux is None else flux.copy())))
    er._observe = observe
    p = SimpleNamespace(**parameters,_observe=lambda name,value:arithmetic.__setitem__(name,ions.freeze(np.array(value,copy=True))))
    observe('initial',sim,None,None)
    completed,failure = True,None
    with np.errstate(all='ignore'):
        try:er.update(sim,cells,p)
        except Exception as error:
            import traceback
            completed = False
            failure = dict(type=type(error).__name__,message=str(error),traceback=traceback.format_exc())
    raw = raw_fields()
    finite = all(np.isfinite(np.asarray(value)).all() for value in raw.values()) and np.isfinite(sim.cc_cells).all() and all(np.isfinite(np.asarray(value)).all() for value in arithmetic.values())
    candidate = state(binding_identity,parent.ion_ids,parent.cell_ids,raw) if completed and finite else None
    before_cytosol = np.array(cytosol_mM,copy=True)
    vol = np.asarray(cell_volume_m3)
    before_amount = before_cytosol*vol + parent.fields['cc_er']*parent.fields['er_vol']
    after_amount = sim.cc_cells*vol + sim.cc_er*er.er_vol
    return Trial(parent,ions.freeze(before_cytosol),ions.freeze(sim.cc_cells),tuple(frames),ions.freeze(arithmetic),ions.freeze(raw),candidate,completed,bool(finite),ions.freeze(failure),ions.freeze(after_amount-before_amount),ions.freeze(abs(before_cytosol*vol)+abs(parent.fields['cc_er']*parent.fields['er_vol'])+abs(sim.cc_cells*vol)+abs(sim.cc_er*er.er_vol)))
"""


def main():
    nodes = literal_nodes()
    output = (
        HEADER
        + "\n\n".join(ast.unparse(ast.fix_missing_locations(n)) for n in nodes)
        + "\n"
        + FOOTER
    )
    path = ROOT / "src/cells/processes/betse_endoretic_source.py"
    with path.open("x") as stream:
        stream.write(output)


if __name__ == "__main__":
    main()
