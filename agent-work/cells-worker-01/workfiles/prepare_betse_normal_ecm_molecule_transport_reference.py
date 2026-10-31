"""Write fresh Decimal ECM transporter equations; parse/copy only, never evaluate."""
# ruff: noqa: E501 -- Generated independent equations and metadata strings.

import ast
import copy
from pathlib import Path

ROOT = Path("/home/robert/Cells")
BASE = Path("/mnt/workspaces/Cells")
PARENT = BASE / "betse-normal-ecm-molecule-dispatch-prepared-20261031-01/source"
TRANSPORTER = BASE / "betse-normal-transporter-prepared-20261030-03/source"
PREFIX = "betse_normal_ecm_molecule_transport"

TOP = """
context.prec=100 if refinement==1 else 160
definition,geometry=inputs['definition'],inputs['geometry']
rows=definition['transporters'] or []
if any(row['apply to']!='all' or row['reaction zone']!='cell' for row in rows):
    raise ValueError('Positive conditional reference covers all-target ECM cell transporters')
owner=geometry['owner']
area,volume,membrane_volume=([d(value) for value in geometry[key]]
    for key in ('membrane_area_m2','cell_volume_m3','membrane_volume_m3'))
n,m=len(volume),len(owner)
raw=inputs['material_declaration']
external=raw['environment_geometry_definition']
grid=derive_geometry(external,precision=context.prec)
mapping=grid['membrane_to_grid']
sites=len(grid['grid_points_m'])
site_volume=d(external['parameters']['cell_height_m'])*grid['delta_m']**2
fast=raw['parameters']['fast_update_ecm']
dt,F,R,temperature=(d(inputs[key]) for key in ('dt_s','F','R','runtime_temperature_K'))
voltage=[d(value) for value in inputs['values_before']['voltage_V']]
density=[d(value) for value in inputs['rho_pump']]
valence={name:d(value) for name,value in zip(inputs['ion_ids'],inputs['valence'],strict=True)}
valence.update({row['name']:d(row['z']) for row in definition['biomolecules']})
charge_scale={name:d(1) for name in inputs['ion_ids']}
charge_scale.update({row['name']:d(row.get('scale factor',1.0)) for row in definition['biomolecules']})
state={zone:{name:[d(v) for v in values] for name,values in substances.items()}
       for zone,substances in inputs['concentrations_before'].items()}
gross={zone:{name:list(map(abs,values)) for name,values in substances.items()}
       for zone,substances in state.items()}
current=[d(value) for value in inputs['extra_current_before_A_m2']]
current_gross=list(map(abs,current))
frames,ledgers=[],[]

def project(values):
    if fast:
        last=[d(0)]*sites
        for j,site in enumerate(mapping):
            last[site]=values[j]
        return [last[k]*grid['membrane_area_per_site_m2'][k]/site_volume for k in range(sites)]
    return [sum((values[j]*area[j] for j in range(m) if mapping[j]==k),d(0))/site_volume
            for k in range(sites)]
"""

COMMITS = """
predicted={species:dict(bulk=d(0),environment=d(0),requested_environment=d(0),
    buffer=[d(0)]*m) for species in state['cell_concs']}
counters={-1:0,1:0}
for sign,species,external,nu in terms:
    if external:
        delta=[sign*nu*value for value in project(flux)]
        delta_gross=[nu*value for value in project(flux_gross)]
        # Native repeated-index assignment writes one grid delta per target site.
        for k in dict.fromkeys(mapping):
            state['env_concs'][species][k]+=delta[k]*dt
            gross['env_concs'][species][k]+=delta_gross[k]*dt
        predicted[species]['environment']+=dt*site_volume*sum(delta,d(0))
        predicted[species]['requested_environment']+=sign*nu*dt*sum(
            (flux[j]*area[j] for j in range(m)),d(0))
    else:
        delta=[sign*nu*value for value in divergence]
        delta_gross=[nu*value for value in divergence_gross]
        for i in range(n):
            state['cell_concs'][species][i]+=delta[i]*dt
            gross['cell_concs'][species][i]+=delta_gross[i]*dt
        for j in range(m):
            # Preserve the original omission of nu in the sampled membrane buffer.
            state['mem_concs'][species][j]+=sign*flux[j]*area[j]/membrane_volume[j]*dt
            gross['mem_concs'][species][j]+=flux_gross[j]*area[j]/membrane_volume[j]*dt
            predicted[species]['buffer'][j]+=sign*(1-nu)*flux[j]*area[j]/membrane_volume[j]*dt
        predicted[species]['bulk']+=sign*nu*dt*sum((flux[j]*area[j] for j in range(m)),d(0))
    frame('reactant_commit' if sign<0 else 'product_commit',name,counters[sign],delta[:],flux,flux_gross,delta_gross[:])
    counters[sign]+=1
charge_bulk=F*sum((valence[s]*charge_scale[s]*p['bulk'] for s,p in predicted.items()),d(0))
charge_environment=F*sum((valence[s]*charge_scale[s]*p['environment'] for s,p in predicted.items()),d(0))
ledgers.append(dict(name=name,initial=initial,final=copy.deepcopy(state),predicted=predicted,
    flux=flux,net_z=net_z,forward=forward,regulation=alpha,source_energy_J_mol=energy,
    quotient=quotient,electrical_J_mol=electrical,
    charge_bulk_change_C=charge_bulk,charge_environment_change_C=charge_environment,
    source_current_transfer_C=dt*F*net_z*sum((flux[j]*area[j] for j in range(m)),d(0)),
    physical_global_conservation_credit=False))
frame('after',name,None,None,flux,flux_gross)
"""

RETURN = """
result=dict(concentrations_after=state,gross=gross,extra_current_after_A_m2=current,
    current_gross=current_gross,frames=frames,ledgers=ledgers,
    independent_grid=grid,site_volume_m3=site_volume,decimal_precision=context.prec,
    fresh_conditional_reference=True,carried_reference_forms=0,
    physical_global_conservation_credit=False)
if retain_decimal is not None:
    retain_decimal(copy.deepcopy(result))
return plain(result)
"""


def write(name, tree):
    path = ROOT / "validation/betse" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "# ruff: noqa: E501\n" + ast.unparse(ast.fix_missing_locations(tree)) + "\n"
    compile(text, str(path), "exec")
    with path.open("x") as stream:
        stream.write(text)
    print(str(path))


def main():
    old = ast.parse(
        (TRANSPORTER / "validation/betse/betse_normal_transporter_join_reference.py").read_text()
    )
    regulation = copy.deepcopy(
        next(n for n in old.body if isinstance(n, ast.FunctionDef) and n.name == "regulation")
    )
    original = next(
        n for n in old.body if isinstance(n, ast.FunctionDef) and n.name == "transporters"
    )
    body = next(n for n in original.body if isinstance(n, ast.With)).body
    config = next(n for n in body if isinstance(n, ast.For) and ast.unparse(n.target) == "config")
    rate = copy.deepcopy(config.body[:11])

    class Samples(ast.NodeTransformer):
        def visit_Subscript(self, node):
            if ast.unparse(node) == "state[zone][species][j]":
                return ast.parse(
                    "state[zone][species][mapping[j] if external else j]", mode="eval"
                ).body
            return self.generic_visit(node)

    rate = [Samples().visit(n) for n in rate]
    config = copy.deepcopy(config)
    config.body = rate + ast.parse(COMMITS).body
    model = ast.parse("""
def evaluate(inputs,*,refinement=1,retain_decimal=None):
    if refinement not in (1,2) or not inputs['conditioned_before_model_transporters']:
        raise ValueError('Require complete actual pre-transporter inputs')
    with localcontext() as context:
        pass
""").body[0]
    frame = copy.deepcopy(
        next(n for n in body if isinstance(n, ast.FunctionDef) and n.name == "frame")
    )
    model.body[-1].body = ast.parse(TOP).body + [frame, config] + ast.parse(RETURN).body
    equations = ast.parse('''
"""Independent Decimal ECM rate, ordered commit and explicit native-defect books."""
import copy
from decimal import localcontext
from validation.betse.betse_normal_molecule_join_reference import plain
from validation.betse.betse_normal_network_join_reference import d
from validation.betse.betse_environment_field_reference import geometry as derive_geometry
''')
    equations.body.extend([regulation, model])
    write(PREFIX + "_equations.py", equations)

    outer = ast.parse(
        (PARENT / "validation/betse/betse_normal_ecm_molecule_dispatch_reference.py").read_text()
    )
    outer.body[1:1] = ast.parse("""
from validation.betse import betse_normal_ecm_molecule_dispatch_reference as prior
from validation.betse import betse_normal_ecm_molecule_transport_equations as equations
""").body
    new = ast.parse("""
def evaluate(inputs,*,refinement,retain):
    if refinement not in (1,2):
        raise ValueError('Require the two independent Decimal precision forms')
    if inputs.get('mode')=='transporters':
        precision=100 if refinement==1 else 160
        result=equations.evaluate(inputs,refinement=refinement,
            retain_decimal=lambda value:raw_evidence.retain_raw(retain,'ECM-transporters',value,precision))
        result.update(mode='transporters',carried_reference_forms=0,
            independently_carried_trajectory=False,physical_global_conservation_credit=False)
        return result
    result=prior.evaluate(inputs,refinement=refinement,retain=retain)
    if inputs.get('mode')=='cold_initialization' and inputs['owner_role']=='molecules':
        result['owner_fields']['transporters']=inputs['network']['configuration'].get('transporters') is not None
    return result
""").body[0]
    outer.body = [
        new if isinstance(n, ast.FunctionDef) and n.name == "evaluate" else n for n in outer.body
    ]
    # Prefix/material/commit equations remain explicit frozen-parent dependencies.
    outer.body = [
        n for n in outer.body if not (isinstance(n, ast.FunctionDef) and n.name == "calcium_index")
    ]
    outer.body = [
        n
        for n in outer.body
        if not (isinstance(n, ast.Import) and any(a.name == "copy" for a in n.names))
    ]
    outer.body = [
        n
        for n in outer.body
        if not (
            isinstance(n, ast.ImportFrom)
            and (
                n.module == "decimal"
                or any(
                    a.name
                    in {
                        "betse_normal_ecm_catalog_join_reference",
                        "betse_normal_ecm_molecule_dispatch_reference_models",
                    }
                    for a in n.names
                )
            )
        )
    ]
    write(PREFIX + "_reference.py", outer)


if __name__ == "__main__":
    main()
