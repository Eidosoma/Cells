# ruff: noqa: E501
"""Held dual native-owner conditionals, source books and independent flag controls."""
from tests.unit.test_betse_normal_ion_join import FLOORS
import copy
import json
import os
import subprocess
import sys
import traceback
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pytest
from cells.processes import betse_normal_ecm_molecule_transport as dispatch
from cells.processes import betse_normal_ion_join as ions
from tests.unit import test_betse_ecm_grn_join as chemistry
from tests.unit import test_betse_normal_ecm_catalog_join as catalog
from tests.unit import test_betse_normal_ecm_field_join as field_checks
from tests.unit.test_betse_fast_solver import archive_read
from validation.betse import betse_ecm_transport_checks as material_checks
from validation.betse import betse_normal_ecm_molecule_transport_fixtures as fixtures
from validation.betse import betse_normal_grn_join_native as archives
exact = field_checks.exact

@pytest.fixture(autouse=True)
def explicit_release():
    if os.environ.get('CELLS_ECM_MOLECULE_TRANSPORT_RELEASED') != '1':
        pytest.skip('Held general-molecule source preparation; Chief must explicitly release')

def root(tmp_path):
    return Path(os.environ.get('CELLS_COMPONENT_EVIDENCE', str(tmp_path))) / 'normal-ecm-molecule-transport'

def archive(tmp_path, name, value):
    return archives.write_archive(root(tmp_path) / name, ions.data(value))

def references(folder, inputs):
    folder.mkdir(parents=True, exist_ok=False)
    from validation.betse.betse_normal_ecm_event_join_fixtures import plain as json_values
    (folder / 'inputs.json').write_text(json.dumps(json_values(ions.data(inputs)), indent=2, allow_nan=False) + '\n')
    results = []
    for level in (1, 2):
        output = folder / ('reference-' + str(level) + '.json')
        with (folder / ('reference-' + str(level) + '.stdout.log')).open('x') as stream:
            subprocess.run([sys.executable, '-B', '-m', 'validation.betse.betse_normal_ecm_molecule_transport_reference', '--inputs', str(folder / 'inputs.json'), '--output', str(output), '--refinement', str(level)], stdout=stream, stderr=subprocess.STDOUT, check=True, timeout=180)
        result = json.loads(output.read_text())
        assert result['production_imports_denied'] and (not result['loaded_production_modules'])
        assert result['carried_reference_forms'] == 0 and result['decimal_precision'] == (100 if level == 1 else 160)
        assert result['runtime']['measured_cpu_affinity'] == sorted(os.sched_getaffinity(0))
        results.append(result)
    return results

def isolated(folder, inputs):
    from validation.betse.betse_normal_ecm_event_join_fixtures import plain as json_values
    folder.mkdir(parents=True, exist_ok=False)
    (folder / 'inputs.json').write_text(json.dumps(json_values(ions.data(inputs)), indent=2, allow_nan=False) + '\n')
    with (folder / 'native.stdout.log').open('x') as stream:
        subprocess.run([sys.executable, '-B', '-m', 'validation.betse.betse_normal_ecm_molecule_transport_native', '--inputs', str(folder / 'inputs.json'), '--output', str(folder / 'native')], stdout=stream, stderr=subprocess.STDOUT, check=True, timeout=180)
    value = archive_read(folder / 'native')
    assert value['production_imports_denied'] and (not value['loaded_production_modules'])
    return value

def check(tmp_path, name, folder, rows):
    archive(tmp_path, name, dict(fields=rows, physical_global_conservation_credit=False))
    report = dict(fields={key: row['metric'] for key, row in rows.items()}, resolutions={key: row['resolution'] for key, row in rows.items()}, fresh_conditional_reference=True, carried_reference_forms=0, physical_global_conservation_credit=False)
    (folder / 'comparison.json').write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    assert rows and max((row['normalized_max_error'] for row in report['fields'].values())) <= 1
    assert max((row['normalized_max_error'] for row in report['resolutions'].values())) <= 0.1

def cold_input(raw, role):
    field = raw['field']
    names = field['definition']['environment_geometry_definition']['current_definition']['ions']['ids']
    return dict(mode='cold_initialization', owner_role=role, network=raw['handlers'][role]['network'], catalog=raw['handlers'][role]['catalog'], material_declaration=field['definition'], ion_ids=names, cells=len(field['initial']['cell_mol_m3'][0]), membranes=len(field['initial']['voltage_V']), environment_sites=len(field['initial']['environment_mol_m3'][0]), calcium_configuration=raw['calcium'], bootstrap_dt_s=field['bootstrap']['dt_s'])

def prefix_rows(trial, lower, target):
    rows, add = chemistry.comparisons()
    assert len(lower['frames']) == len(target['frames'])
    actual = trial.frames[:len(target['frames'])]
    for index, (frame, wanted) in enumerate(zip(actual, target['frames'], strict=True)):
        assert (frame.stage, frame.ion_id) == (wanted['stage'], wanted['ion_id'])
        for key, value in wanted['values'].items():
            add(f'frame_{index}.{key}', frame.values._asdict()[key], value, lower['frames'][index]['values'][key], material_checks.budget(key, np.asarray(value)), 'unchanged ECM material budget')
    for index, wanted in enumerate(target['environment_records']):
        actual = trial.environment_records[index]._asdict()
        for key, value in wanted.items():
            if key == 'ion_id':
                continue
            add(f'environment_{index}.{key}', actual[key], value, lower['environment_records'][index][key], material_checks.budget(key, np.asarray(value)), 'unchanged ECM material budget')
    return rows

def commit_rows(trial, lower, target):
    rows, add = chemistry.comparisons()
    actual_frames = trial.frames[-len(target['frames']):] if target['frames'] else ()
    assert len(actual_frames) == len(target['frames'])
    for index, (frame, wanted) in enumerate(zip(actual_frames, target['frames'], strict=True)):
        assert (frame.stage, frame.ion_id) == (wanted['stage'], wanted['ion_id'])
        for key, value in wanted['values'].items():
            add(f'commit_frame_{index}.{key}', frame.values._asdict()[key], value, lower['frames'][index]['values'][key], material_checks.budget(key, np.asarray(value)), 'unchanged ECM material budget')
    for key, value in target['candidate'].items():
        add('candidate.' + key, trial.candidate.values._asdict()[key], value, lower['candidate'][key], material_checks.budget(key, np.asarray(value)), 'unchanged ECM candidate budget')
    for key in material_checks.LEDGERS:
        value = target['ledgers'][key]
        add('ledger.' + key, trial.diagnostics[key], value, lower['ledgers'][key], material_checks.budget(key, np.asarray(value)), 'unchanged ECM source-effective ledger budget')
    return rows

@pytest.mark.parametrize('case', fixtures.CASES)
def test_two_owner_history(tmp_path, case):
    raw = fixtures.fixture(case)
    binding = dispatch.bind(raw)
    archive(tmp_path, case + '-inputs-before-setup', raw)
    folder = root(tmp_path) / case
    folder.mkdir(parents=True, exist_ok=False)
    enabled = dict(molecules=raw['configuration']['general network']['implement network'], grn=raw['configuration']['gene regulatory network settings']['gene regulatory network simulated'])
    captured = {}
    cold = {}
    boot = []
    forms_count = 0
    cold_material = copy.deepcopy(raw['field']['initial'])

    def setup_observer(role, stage, value):
        archive(tmp_path, case + '-' + role + '-' + stage, value)
        if stage == 'after_setup':
            cold_material.clear()
            cold_material.update(ions.data(value['material']))
        if role == 'all':
            captured['setup'] = isolated(folder / 'native-setup', value)
            for owner in dispatch.runtime.ROLES:
                if enabled[owner]:
                    cold[owner] = references(folder / ('cold-' + owner), cold_input(raw, owner))

    def before_boot(value):
        boot.extend(references(folder / 'bootstrap', value))
    try:
        parent = dispatch.initialize(binding, observer=setup_observer, before_field=before_boot)
    except Exception as error:
        archive(tmp_path, case + '-setup-failure', dict(partial=getattr(error, 'partial', None), traceback=traceback.format_exc()))
        raise
    archive(tmp_path, case + '-bootstrap-return', parent)
    native = captured['setup']
    assert native['status'] == 'source_completed'
    exact(native['returned']['material'], cold_material)
    for role in dispatch.runtime.ROLES:
        saved = parent.owners['handlers'][role]
        if enabled[role]:
            exact(ions.data(saved['cache']), native['returned']['handlers'][role])
            check(tmp_path, case + '-' + role + '-cold-errors', folder / ('cold-' + role), chemistry.compare_cold(binding.component, SimpleNamespace(network_cache=saved['cache']), *cold[role]))
        else:
            assert saved is native['returned']['handlers'][role] is None
    for key in dispatch.runtime.PUBLICATIONS:
        if not any(enabled.values()):
            exact(parent.owners['shared'][key], raw['shared_initial'][key])
    check(tmp_path, case + '-bootstrap-errors', folder / 'bootstrap', field_checks.compare_field(binding.component, parent.field, *boot))
    forms_count += 2 + 2 * sum(enabled.values())
    for index in range(3):
        point = folder / ('point-' + str(index))
        point.mkdir()
        answers = {}
        native_call = {}
        observed = {}
        previous = parent
        digest = ions.digest(previous)

        def before(mode, index=index, observed=observed, answers=answers, point=point):

            def callback(value):
                archive(tmp_path, case + '-' + mode + '-before-' + str(index), value)
                observed[mode] = ions.data(value)
                answers[mode] = references(point / mode, value)
            return callback

        def handler(role, stage, value, index=index, native_call=native_call, point=point, observed=observed, answers=answers):
            archive(tmp_path, case + '-' + role + '-' + stage + '-' + str(index), value)
            if role == 'all':
                native_call['result'] = isolated(point / 'native-dispatch', value)
            elif stage in ('channels', 'network', 'transporters'):
                key = role + '-' + stage
                observed[key] = ions.data(value)
                answers[key] = references(point / key, value)
        try:
            parent, details = dispatch.advance(binding, parent, before_material=before('material'), before_calcium=before('calcium'), handler_observer=handler, before_commit=before('commit'), before_field=before('field'))
            archive(tmp_path, case + '-accepted-' + str(index), dict(parent=parent, details=details))
        except Exception as error:
            archive(tmp_path, case + '-failure-' + str(index), dict(parent=previous, partial=getattr(error, 'partial', None), traceback=traceback.format_exc()))
            raise
        assert ions.digest(previous) == digest and parent.cursor == index + 1
        native = native_call['result']
        assert native['status'] == 'source_completed'
        exact(observed['commit']['values_before'], native['returned']['material'])
        exact(ions.data(details['dispatch']['shared_after']), native['returned']['shared'])
        expected_order = [role for role in dispatch.runtime.ROLES if enabled[role]]
        assert [row['role'] for row in details['dispatch']['order'] if row['stage'] == 'before_dispatch'] == expected_order
        for role in dispatch.runtime.ROLES:
            saved = parent.owners['handlers'][role]
            if enabled[role]:
                exact(ions.data(saved['cache']), native['returned']['handlers'][role])
                feedback = details['dispatch']['handlers'][role]
                if role == 'molecules' and raw['handlers'][role]['network']['configuration'].get('transporters') is not None:
                    key = role + '-transporters'
                    comparison, books = transporter_rows(feedback, *answers[key])
                    archive(tmp_path, case + '-transporter-books-' + str(index), books)
                    check(tmp_path, case + '-transporter-errors-' + str(index), point / key, comparison)
                check(tmp_path, case + '-' + role + '-channels-errors-' + str(index), point / (role + '-channels'), catalog.compare_channels(binding.component, feedback, *answers[role + '-channels']))
                check(tmp_path, case + '-' + role + '-network-errors-' + str(index), point / (role + '-network'), chemistry.compare_local(feedback, *answers[role + '-network']))
            else:
                assert saved is native['returned']['handlers'][role] is None
        if raw['field']['steps'][index]['publication'] and expected_order:
            assert parent.owners['publication_owner'] == expected_order[-1]
        else:
            assert parent.owners['publication_owner'] == previous.owners['publication_owner']
            exact(parent.owners['wire']['simulator_fields'], previous.owners['wire']['simulator_fields'])
        check(tmp_path, case + '-material-prefix-errors-' + str(index), point / 'material', prefix_rows(details['trial'], *answers['material']))
        check(tmp_path, case + '-calcium-errors-' + str(index), point / 'calcium', catalog.compare_calcium(details['calcium'], *answers['calcium']))
        check(tmp_path, case + '-commit-errors-' + str(index), point / 'commit', commit_rows(details['trial'], *answers['commit']))
        check(tmp_path, case + '-field-errors-' + str(index), point / 'field', field_checks.compare_field(binding.component, parent.field, *answers['field']))
        forms_count += 8 + 4 * sum(enabled.values())
        if enabled['molecules'] and raw['handlers']['molecules']['network']['configuration'].get('transporters') is not None:
            forms_count += 2
    archive(tmp_path, case + '-summary', dict(completed_calls=3, fresh_reference_forms=forms_count, native_conditional_captures=4, independently_carried_trajectory=False, no_ER_enablement=True, shared_publications_summed=False, global_conservation_credit=False))

@pytest.mark.parametrize('case', fixtures.RAW_CASES)
def test_original_molecule_failure(tmp_path, case):
    raw = fixtures.fixture(case)
    binding = dispatch.bind(raw)
    setup = []

    def setup_observer(role, stage, value):
        archive(tmp_path, case + '-setup-' + role + '-' + stage, value)
        if role == 'all':
            setup.append(isolated(root(tmp_path) / (case + '-native-setup'), value))
    parent = dispatch.initialize(binding, observer=setup_observer)
    assert len(setup) == 1 and setup[0]['status'] == 'source_completed'
    captured = []

    def observe(role, stage, value):
        archive(tmp_path, case + '-' + role + '-' + stage, value)
        if role == 'all':
            captured.append(isolated(root(tmp_path) / (case + '-native-dispatch'), value))
    with pytest.raises(dispatch.DispatchRejected) as caught:
        dispatch.advance(binding, parent, handler_observer=observe)
    archive(tmp_path, case + '-original-failure', dict(parent=parent, partial=caught.value.partial, native=captured))
    assert captured and captured[0]['status'] == 'source_refused'
    assert captured[0]['failure'] and captured[0]['failure_capture']
    assert caught.value.partial['available']['owners'] and caught.value.__cause__ is not None
    assert caught.value.partial['automatic_retry'] is False

@pytest.mark.parametrize('case', fixtures.prior.DEPENDENCIES)
def test_two_owner_dependency(tmp_path, case):
    raw = fixtures.fixture(case)
    conf = raw['configuration']
    flags = raw['flags']
    changes = {'absent_general_network': lambda: conf.update({'general network': None}), 'missing_implement_flag': lambda: conf['general network'].pop('implement network'), 'foreign_implement_flag': lambda: conf['general network'].update({'implement network': 1}), 'GRN_flag_missing': lambda: conf['gene regulatory network settings'].clear(), 'GRN_flag_not_bool': lambda: conf['gene regulatory network settings'].update({'gene regulatory network simulated': 1}), 'enabled_ER': lambda: flags.update(Ca_dyn=True), 'enabled_flow': lambda: flags.update(fluid_flow=True), 'FAST': lambda: flags.update(solver='FAST'), 'noise_requires_owner': lambda: flags.update(dynamic_noise=1), 'osmotic_requires_both_owners': lambda: flags.update(deform_osmo=True), 'foreign_general_config': lambda: conf['general network'].update({'time dilation factor': 99.0}), 'foreign_profile_owner': lambda: raw['handlers']['molecules']['catalog']['tissue_profiles'].update(foreign=[0]), 'missing_shared_charge': lambda: raw['shared_initial'].pop('extra_rho_cells')}
    if case in changes:
        changes[case]()
        archive(tmp_path, case + '-poisoned-input', raw)
        with pytest.raises(ValueError):
            dispatch.bind(raw)
        return
    if case == 'fabricated_disabled_owner':
        raw['configuration']['general network']['implement network'] = False
    binding = dispatch.bind(raw)
    parent = dispatch.initialize(binding)
    owners = ions.data(parent.owners)
    field = parent.field
    rate = parent.rate_cache
    if case == 'foreign_general_cache_role':
        owners['handlers']['molecules']['role'] = 'grn'
    elif case == 'swapped_handler_caches':
        owners['handlers']['molecules'], owners['handlers']['grn'] = (owners['handlers']['grn'], owners['handlers']['molecules'])
    elif case == 'missing_general_cache':
        owners['handlers']['molecules'] = None
    elif case == 'fabricated_disabled_owner':
        owners['handlers']['molecules'] = copy.deepcopy(owners['handlers']['grn'])
    elif case == 'changed_publication_projection':
        owners['wire']['simulator_fields']['extra_rho_cells'][0] += 1.0
    elif case == 'changed_shared_epoch':
        owners['wire']['simulator_fields']['extra_rho_cells'][0] += 1.0
        owners['shared']['extra_rho_cells'][0] += 1.0
    elif case == 'changed_field_owner':
        field = dispatch.full.FieldStage('foreign', field.before, field.current, field.environment, field.voltage, '')
        from dataclasses import replace
        field = replace(field, identity=ions.digest(dispatch.full.field_record(field)))
    elif case == 'changed_Ca_cache':
        rate = dispatch.calcium.RateCache(True, ions.freeze(np.zeros_like(parent.material.values.voltage_V)))
    changed = dispatch.state(binding, parent.material, field, owners, parent.controls, rate, parent.clock)
    archive(tmp_path, case + '-poisoned-state', changed)
    with pytest.raises(ValueError):
        dispatch.verify(binding, changed)
TRANSPORT_TOLERANCES = json.loads((Path(__file__).resolve().parents[2] / 'validation/transport/betse_network_transport_protocol.json').read_text())['tolerances']

def transporter_rows(feedback, lower, target):
    rows, add = chemistry.comparisons()
    before = feedback['before_transporters']
    actual = [r for r in feedback.get('transporter_frames', []) if r['stage'] not in ('before', 'flux')]
    assert len(actual) == len(target['frames']) == len(lower['frames'])
    geometry = before['geometry']
    n, m = (len(geometry['cell_volume_m3']), len(geometry['owner']))
    e = len(before['concentrations_before']['env_concs'][before['ion_ids'][0]])
    species = list(before['concentrations_before']['cell_concs'])
    factor = 128 * np.finfo(float).eps * (len(species) + n + m + e + 64)
    floors = dict(cell_concs=FLOORS['cell_mol_m3'], mem_concs=FLOORS['membrane_mol_m3'], env_concs=FLOORS['bath_mol_m3'])
    for i, (source, high, low) in enumerate(zip(actual, target['frames'], lower['frames'], strict=True)):
        assert (source['stage'], source['name'], source['term']) == (high['stage'], high['name'], high['term'])
        key = str(i) + '/' + source['name'] + '/' + source['stage']
        add(key + '/flux', source['fluxes'][source['name']], high['flux'], low['flux'], TRANSPORT_TOLERANCES['density_atol_mol_m2_s'] + TRANSPORT_TOLERANCES['relative'] * np.abs(high['flux']), 'mol/(m2*s)')
        add(key + '/current', source['extra_current_A_m2'], high['extra_current_A_m2'], low['extra_current_A_m2'], TRANSPORT_TOLERANCES['current_atol_A_m2'] + factor * np.asarray(high['current_gross']), 'A/m2')
        for zone in floors:
            for name in species:
                add(key + '/' + zone + '/' + name, source['concentrations'][zone][name], high['concentrations'][zone][name], low['concentrations'][zone][name], floors[zone] + factor * np.asarray(high['gross'][zone][name]), 'mM')
        if source['delta'] is not None:
            add(key + '/delta', source['delta'], high['delta'], low['delta'], floors['cell_concs'] + factor * np.asarray(high['delta_gross']), 'mM/s')
    for zone in floors:
        for name in species:
            wanted = target['concentrations_after'][zone][name]
            found = actual[-1]['concentrations'][zone][name] if actual else before['concentrations_before'][zone][name]
            add('final/' + zone + '/' + name, found, wanted, lower['concentrations_after'][zone][name], floors[zone] + factor * np.asarray(target['gross'][zone][name]), 'mM')
    area = np.asarray(geometry['membrane_area_m2'])
    volume = np.asarray(geometry['cell_volume_m3'])
    wedge = np.asarray(geometry['membrane_volume_m3'])
    site_volume = target['site_volume_m3']
    dt = before['dt_s']
    configurations = {r['name']: r for r in before['definition']['transporters'] or []}
    valence = dict(zip(before['ion_ids'], before['valence'], strict=True))
    scales = {s: 1.0 for s in species}
    for config in before['definition']['biomolecules']:
        valence[config['name']] = config['z']
        scales[config['name']] = config.get('scale factor', 1.0)
    books = []
    frames = feedback.get('transporter_frames', [])
    for index, (high, low) in enumerate(zip(target['ledgers'], lower['ledgers'], strict=True)):
        name = high['name']
        initial = next((r for r in frames if r['name'] == name and r['stage'] == 'before'))['concentrations']
        final = next((r for r in frames if r['name'] == name and r['stage'] == 'after'))['concentrations']
        charge_bulk = charge_environment = 0.0
        charge_budget = 0.0
        for species_name in species:
            old_cell, new_cell = (np.asarray(state['cell_concs'][species_name]) for state in (initial, final))
            old_env, new_env = (np.asarray(state['env_concs'][species_name]) for state in (initial, final))
            old_mem, new_mem = (np.asarray(state['mem_concs'][species_name]) for state in (initial, final))
            bulk = np.dot(new_cell - old_cell, volume)
            environment = np.sum(new_env - old_env) * site_volume
            p, q = (high['predicted'][species_name], low['predicted'][species_name])
            gross_amount = np.dot(np.abs(old_cell) + np.abs(new_cell), volume) + np.sum(np.abs(old_env) + np.abs(new_env)) * site_volume
            budget = factor * gross_amount + floors['cell_concs'] * (sum(volume) + e * site_volume)
            key = 'book/' + str(index) + '/' + species_name
            for label, value, expected, less in (('bulk', bulk, p['bulk'], q['bulk']), ('environment', environment, p['environment'], q['environment']), ('physical_residual', bulk + environment, p['bulk'] + p['environment'], q['bulk'] + q['environment']), ('collocated_defect', environment - p['requested_environment'], p['environment'] - p['requested_environment'], q['environment'] - q['requested_environment'])):
                add(key + '/' + label, value, expected, less, budget, 'mol')
            ideal = np.zeros(m)
            for sign, role, coefficients, transferred in ((-1, 'reactants', 'reactant multipliers', 'transfered into cell'), (1, 'products', 'product multipliers', 'transfered out of cell')):
                config = configurations[name]
                moved = config[transferred]
                moved = [] if moved in (None, 'None') else moved
                for s, nu in zip(config[role], config[coefficients], strict=True):
                    if s == species_name and s not in moved:
                        ideal += sign * nu * np.asarray(high['flux']) * area / wedge * dt
            discrepancy = new_mem - old_mem - ideal
            add(key + '/buffer_discrepancy', discrepancy, p['buffer'], q['buffer'], floors['mem_concs'] + factor * (np.abs(old_mem) + np.abs(new_mem) + np.abs(ideal)), 'mM')
            zscale = valence[species_name] * scales[species_name] * before['F']
            charge_bulk += zscale * bulk
            charge_environment += zscale * environment
            charge_budget += abs(zscale) * budget
            books.append(dict(name=name, species=species_name, bulk_change_mol=bulk, environment_change_mol=environment, physical_residual_mol=bulk + environment, predicted=p, source_effective_requested_environment_mol=p['requested_environment'], collocated_defect_mol=environment - p['requested_environment'], buffer_discrepancy_mM=discrepancy, amount_budget_mol=budget, physical_global_conservation_credit=False))
        for label, actual_charge in (('charge_bulk_change_C', charge_bulk), ('charge_environment_change_C', charge_environment)):
            add('charge/' + name + '/' + label, actual_charge, high[label], low[label], TRANSPORT_TOLERANCES['charge_atol_C'] + charge_budget, 'C')
    return (rows, books)

@pytest.mark.parametrize('case', fixtures.RAW_SETUP_CASES)
def test_original_transporter_setup_failure(tmp_path, case):
    raw = fixtures.fixture(case)
    binding = dispatch.bind(raw)
    captured = []

    def observe(role, stage, value):
        archive(tmp_path, case + '-' + role + '-' + stage, value)
        if role == 'all':
            captured.append(isolated(root(tmp_path) / (case + '-native-setup'), value))
    with pytest.raises(dispatch.DispatchRejected) as caught:
        dispatch.initialize(binding, observer=observe)
    archive(tmp_path, case + '-original-setup-partial', dict(inputs=raw, partial=caught.value.partial, native=captured))
    assert caught.value.partial['root_cause']['type'] == 'KeyError'
    assert 'max rate' in caught.value.partial['root_cause']['message']
    assert captured and captured[0]['status'] == 'source_refused' and captured[0]['failure_capture']
    assert captured[0]['failure']['type'] == 'KeyError'
    actual = ions.data(caught.value.partial['available']['owners']['handlers']['molecules']['cache'])
    exact(actual, captured[0]['returned']['handlers']['molecules'])
    fields = actual['wire']['transporter_fields']
    assert len(fields) == int(case[-1]) + 1
    assert all((f['flux'] is None for f in fields.values()))
    assert caught.value.__cause__ is not None

@pytest.mark.parametrize('case', fixtures.TRANSPORT_DEPENDENCIES)
def test_transporter_dependency(tmp_path, case):
    raw = fixtures.fixture(case)
    if case in ('missing_membrane_volume', 'foreign_membrane_volume', 'unmarked_missing_rate', 'foreign_native_transporters', 'unsupported_profile', 'unsupported_GRN_transporters'):
        if case == 'missing_membrane_volume':
            raw['transport'].pop('membrane_volume_m3')
        elif case == 'foreign_membrane_volume':
            raw['transport']['membrane_volume_m3'][0] *= 2
        elif case == 'unmarked_missing_rate':
            raw['handlers']['molecules']['network']['configuration']['transporters'][0].pop('max rate')
            raw['configuration']['general network']['transporters'][0].pop('max rate')
        elif case == 'foreign_native_transporters':
            raw['configuration']['general network']['transporters'][0]['max rate'] *= 2
        elif case == 'unsupported_profile':
            raw['handlers']['molecules']['network']['configuration']['transporters'][0]['apply to'] = ['absent']
            raw['configuration']['general network']['transporters'][0]['apply to'] = ['absent']
        else:
            rows = copy.deepcopy(raw['handlers']['molecules']['network']['configuration']['transporters'])
            raw['handlers']['grn']['network']['configuration']['transporters'] = rows
            raw['field']['network']['configuration']['transporters'] = copy.deepcopy(rows)
        archive(tmp_path, case + '-input', raw)
        with pytest.raises(ValueError):
            dispatch.bind(raw)
        return
    binding = dispatch.bind(raw)
    parent = dispatch.initialize(binding)
    owners = ions.data(parent.owners)
    cache = owners['handlers']['molecules']['cache']
    name = next(iter(cache['wire']['transporter_fields']))
    if case == 'missing_transporter_cache':
        cache['wire']['transporter_fields'].pop(name)
    elif case == 'changed_transporter_equation':
        cache['wire']['transporter_fields'][name]['transporter_eval_string'] = '0'
    elif case == 'changed_transporter_flux_epoch':
        cache['wire']['transporter_fields'][name]['flux'] = np.zeros_like(parent.material.values.voltage_V)
    elif case == 'arbitrary_pump_weight':
        owners['shared']['rho_pump'] = 2
    changed = dispatch.state(binding, parent.material, parent.field, owners, parent.controls, parent.rate_cache, parent.clock)
    archive(tmp_path, case + '-state', changed)
    with pytest.raises(ValueError):
        dispatch.verify(binding, changed)
