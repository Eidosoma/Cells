"""Prepare prospective checks without importing science, fixtures or tests."""
# ruff: noqa: E501 -- Literal prospective checks.

import ast
from pathlib import Path

ROOT = Path("/home/robert/Cells")
PARENT = Path(
    "/mnt/workspaces/Cells/betse-normal-ecm-molecule-dispatch-prepared-20261031-01/source"
)
OLD = "betse_normal_ecm_molecule_dispatch"
NEW = "betse_normal_ecm_molecule_transport"

EXTRA = """
from tests.unit.test_betse_normal_ion_join import FLOORS
TRANSPORT_TOLERANCES=json.loads((Path(__file__).resolve().parents[2]/'validation/transport/betse_network_transport_protocol.json').read_text())['tolerances']

def transporter_rows(feedback,lower,target):
    rows,add=chemistry.comparisons()
    before=feedback['before_transporters']
    actual=[r for r in feedback.get('transporter_frames',[]) if r['stage'] not in ('before','flux')]
    assert len(actual)==len(target['frames'])==len(lower['frames'])
    geometry=before['geometry']
    n,m=len(geometry['cell_volume_m3']),len(geometry['owner'])
    e=len(before['concentrations_before']['env_concs'][before['ion_ids'][0]])
    species=list(before['concentrations_before']['cell_concs'])
    factor=128*np.finfo(float).eps*(len(species)+n+m+e+64)
    floors=dict(cell_concs=FLOORS['cell_mol_m3'],
                mem_concs=FLOORS['membrane_mol_m3'],
                env_concs=FLOORS['bath_mol_m3'])
    for i,(source,high,low) in enumerate(zip(actual,target['frames'],lower['frames'],strict=True)):
        assert (source['stage'],source['name'],source['term'])==(high['stage'],high['name'],high['term'])
        key=str(i)+'/'+source['name']+'/'+source['stage']
        add(key+'/flux',source['fluxes'][source['name']],high['flux'],low['flux'],
            TRANSPORT_TOLERANCES['density_atol_mol_m2_s']+TRANSPORT_TOLERANCES['relative']*np.abs(high['flux']), 'mol/(m2*s)')
        add(key+'/current',source['extra_current_A_m2'],high['extra_current_A_m2'],low['extra_current_A_m2'],
            TRANSPORT_TOLERANCES['current_atol_A_m2']+factor*np.asarray(high['current_gross']),'A/m2')
        for zone in floors:
            for name in species:
                add(key+'/'+zone+'/'+name,source['concentrations'][zone][name],high['concentrations'][zone][name],
                    low['concentrations'][zone][name],floors[zone]+factor*np.asarray(high['gross'][zone][name]),'mM')
        if source['delta'] is not None:
            add(key+'/delta',source['delta'],high['delta'],low['delta'],
                floors['cell_concs']+factor*np.asarray(high['delta_gross']),'mM/s')
    # Empty-but-enabled transporters still have a complete, unchanged input/output seam.
    for zone in floors:
        for name in species:
            wanted=target['concentrations_after'][zone][name]
            found=(actual[-1]['concentrations'][zone][name] if actual else before['concentrations_before'][zone][name])
            add('final/'+zone+'/'+name,found,wanted,lower['concentrations_after'][zone][name],
                floors[zone]+factor*np.asarray(target['gross'][zone][name]),'mM')
    area=np.asarray(geometry['membrane_area_m2'])
    volume=np.asarray(geometry['cell_volume_m3'])
    wedge=np.asarray(geometry['membrane_volume_m3'])
    site_volume=target['site_volume_m3']
    dt=before['dt_s']
    configurations={r['name']:r for r in before['definition']['transporters'] or []}
    valence=dict(zip(before['ion_ids'],before['valence'],strict=True))
    scales={s:1.0 for s in species}
    for config in before['definition']['biomolecules']:
        valence[config['name']]=config['z']
        scales[config['name']]=config.get('scale factor',1.0)
    books=[]
    frames=feedback.get('transporter_frames',[])
    for index,(high,low) in enumerate(zip(target['ledgers'],lower['ledgers'],strict=True)):
        name=high['name']
        initial=next(r for r in frames if r['name']==name and r['stage']=='before')['concentrations']
        final=next(r for r in frames if r['name']==name and r['stage']=='after')['concentrations']
        charge_bulk=charge_environment=0.0
        charge_budget=0.0
        for species_name in species:
            old_cell,new_cell=(np.asarray(state['cell_concs'][species_name]) for state in (initial,final))
            old_env,new_env=(np.asarray(state['env_concs'][species_name]) for state in (initial,final))
            old_mem,new_mem=(np.asarray(state['mem_concs'][species_name]) for state in (initial,final))
            bulk=np.dot(new_cell-old_cell,volume)
            environment=np.sum(new_env-old_env)*site_volume
            p,q=high['predicted'][species_name],low['predicted'][species_name]
            gross_amount=np.dot(np.abs(old_cell)+np.abs(new_cell),volume)+np.sum(np.abs(old_env)+np.abs(new_env))*site_volume
            budget=factor*gross_amount+floors['cell_concs']*(sum(volume)+e*site_volume)
            key='book/'+str(index)+'/'+species_name
            for label,value,expected,less in (
                ('bulk',bulk,p['bulk'],q['bulk']),
                ('environment',environment,p['environment'],q['environment']),
                ('physical_residual',bulk+environment,p['bulk']+p['environment'],q['bulk']+q['environment']),
                ('collocated_defect',environment-p['requested_environment'],p['environment']-p['requested_environment'],q['environment']-q['requested_environment']),
            ):
                add(key+'/'+label,value,expected,less,budget,'mol')
            ideal=np.zeros(m)
            for sign,role,coefficients,transferred in (
                (-1,'reactants','reactant multipliers','transfered into cell'),
                (1,'products','product multipliers','transfered out of cell'),
            ):
                config=configurations[name]
                moved=config[transferred]
                moved=[] if moved in (None,'None') else moved
                for s,nu in zip(config[role],config[coefficients],strict=True):
                    if s==species_name and s not in moved:
                        ideal+=sign*nu*np.asarray(high['flux'])*area/wedge*dt
            discrepancy=new_mem-old_mem-ideal
            add(key+'/buffer_discrepancy',discrepancy,p['buffer'],q['buffer'],
                floors['mem_concs']+factor*(np.abs(old_mem)+np.abs(new_mem)+np.abs(ideal)),'mM')
            zscale=valence[species_name]*scales[species_name]*before['F']
            charge_bulk+=zscale*bulk
            charge_environment+=zscale*environment
            charge_budget+=abs(zscale)*budget
            books.append(dict(name=name,species=species_name,bulk_change_mol=bulk,environment_change_mol=environment,
                physical_residual_mol=bulk+environment,predicted=p,source_effective_requested_environment_mol=p['requested_environment'],
                collocated_defect_mol=environment-p['requested_environment'],buffer_discrepancy_mM=discrepancy,
                amount_budget_mol=budget,physical_global_conservation_credit=False))
        for label,actual_charge in (('charge_bulk_change_C',charge_bulk),('charge_environment_change_C',charge_environment)):
            add('charge/'+name+'/'+label,actual_charge,high[label],low[label],
                TRANSPORT_TOLERANCES['charge_atol_C']+charge_budget,'C')
    return rows,books

@pytest.mark.parametrize('case',fixtures.RAW_SETUP_CASES)
def test_original_transporter_setup_failure(tmp_path,case):
    raw=fixtures.fixture(case)
    binding=dispatch.bind(raw)
    captured=[]
    def observe(role,stage,value):
        archive(tmp_path,case+'-'+role+'-'+stage,value)
        if role=='all':
            captured.append(isolated(root(tmp_path)/(case+'-native-setup'),value))
    with pytest.raises(dispatch.DispatchRejected) as caught:
        dispatch.initialize(binding,observer=observe)
    archive(tmp_path,case+'-original-setup-partial',dict(inputs=raw,partial=caught.value.partial,native=captured))
    assert caught.value.partial['root_cause']['type']=='KeyError'
    assert 'max rate' in caught.value.partial['root_cause']['message']
    assert captured and captured[0]['status']=='source_refused' and captured[0]['failure_capture']
    assert captured[0]['failure']['type']=='KeyError'
    actual=ions.data(caught.value.partial['available']['owners']['handlers']['molecules']['cache'])
    exact(actual,captured[0]['returned']['handlers']['molecules'])
    fields=actual['wire']['transporter_fields']
    assert len(fields)==int(case[-1])+1
    assert all(f['flux'] is None for f in fields.values())
    assert caught.value.__cause__ is not None

@pytest.mark.parametrize('case',fixtures.TRANSPORT_DEPENDENCIES)
def test_transporter_dependency(tmp_path,case):
    raw=fixtures.fixture(case)
    if case in ('missing_membrane_volume','foreign_membrane_volume','unmarked_missing_rate',
                'foreign_native_transporters','unsupported_profile','unsupported_GRN_transporters'):
        if case=='missing_membrane_volume': raw['transport'].pop('membrane_volume_m3')
        elif case=='foreign_membrane_volume': raw['transport']['membrane_volume_m3'][0]*=2
        elif case=='unmarked_missing_rate':
            raw['handlers']['molecules']['network']['configuration']['transporters'][0].pop('max rate')
            raw['configuration']['general network']['transporters'][0].pop('max rate')
        elif case=='foreign_native_transporters': raw['configuration']['general network']['transporters'][0]['max rate']*=2
        elif case=='unsupported_profile':
            raw['handlers']['molecules']['network']['configuration']['transporters'][0]['apply to']=['absent']
            raw['configuration']['general network']['transporters'][0]['apply to']=['absent']
        else:
            rows=copy.deepcopy(raw['handlers']['molecules']['network']['configuration']['transporters'])
            raw['handlers']['grn']['network']['configuration']['transporters']=rows
            raw['field']['network']['configuration']['transporters']=copy.deepcopy(rows)
        archive(tmp_path,case+'-input',raw)
        with pytest.raises(ValueError): dispatch.bind(raw)
        return
    binding=dispatch.bind(raw)
    parent=dispatch.initialize(binding)
    owners=ions.data(parent.owners)
    cache=owners['handlers']['molecules']['cache']
    name=next(iter(cache['wire']['transporter_fields']))
    if case=='missing_transporter_cache': cache['wire']['transporter_fields'].pop(name)
    elif case=='changed_transporter_equation': cache['wire']['transporter_fields'][name]['transporter_eval_string']='0'
    elif case=='changed_transporter_flux_epoch': cache['wire']['transporter_fields'][name]['flux']=np.zeros_like(parent.material.values.voltage_V)
    elif case=='arbitrary_pump_weight': owners['shared']['rho_pump']=2
    changed=dispatch.state(binding,parent.material,parent.field,owners,parent.controls,parent.rate_cache,parent.clock)
    archive(tmp_path,case+'-state',changed)
    with pytest.raises(ValueError): dispatch.verify(binding,changed)
"""


def main():
    text = (PARENT / "tests/unit" / ("test_" + OLD + ".py")).read_text().replace(OLD, NEW)
    text = text.replace(
        "CELLS_ECM_MOLECULE_DISPATCH_RELEASED", "CELLS_ECM_MOLECULE_TRANSPORT_RELEASED"
    )
    text = text.replace("normal-ecm-molecule-dispatch", "normal-ecm-molecule-transport")
    text = text.replace("fixtures.DEPENDENCIES", "fixtures.prior.DEPENDENCIES")
    text = text.replace(
        'elif stage in ("channels", "network"):',
        'elif stage in ("channels", "network", "transporters"):',
    )
    tree = ast.parse(text)
    history = next(
        n
        for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name == "test_two_owner_history"
    )

    class AddChecks(ast.NodeTransformer):
        def visit_Assign(self, node):
            node = self.generic_visit(node)
            if ast.unparse(node.targets[0]) == "feedback":
                return [
                    node,
                    *ast.parse("""
if role=='molecules' and raw['handlers'][role]['network']['configuration'].get('transporters') is not None:
    key=role+'-transporters'
    comparison,books=transporter_rows(feedback,*answers[key])
    archive(tmp_path,case+'-transporter-books-'+str(index),books)
    check(tmp_path,case+'-transporter-errors-'+str(index),point/key,comparison)
""").body,
                ]
            return node

        def visit_AugAssign(self, node):
            node = self.generic_visit(node)
            if ast.unparse(node.target) == "forms_count" and ast.unparse(node.value).startswith(
                "8 +"
            ):
                return [
                    node,
                    *ast.parse("""
if enabled['molecules'] and raw['handlers']['molecules']['network']['configuration'].get('transporters') is not None:
    forms_count+=2
""").body,
                ]
            return node

    # There are exactly two forms per enabled transporter call, not per other component.
    AddChecks().visit(history)
    extra = ast.parse(EXTRA).body
    tree.body[1:1] = [n for n in extra if isinstance(n, (ast.Import, ast.ImportFrom))]
    tree.body += [n for n in extra if not isinstance(n, (ast.Import, ast.ImportFrom))]
    path = ROOT / "tests/unit" / ("test_" + NEW + ".py")
    path.parent.mkdir(parents=True, exist_ok=True)
    result = "# ruff: noqa: E501\n" + ast.unparse(ast.fix_missing_locations(tree)) + "\n"
    compile(result, str(path), "exec")
    with path.open("x") as stream:
        stream.write(result)
    print(str(path))


if __name__ == "__main__":
    main()
