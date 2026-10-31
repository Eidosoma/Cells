# ruff: noqa: E501
"""Copied phase reset arithmetic; current owner existence is explicit metadata."""
import copy
from decimal import Decimal
from validation.betse import betse_normal_ecm_catalog_join_reference as catalog
from validation.betse import betse_normal_ecm_init_phase_reference as ordinary
d, numbers, serial = (catalog.d, catalog.numbers, catalog.serial)

def phase_rules(inputs):
    old = inputs['incoming']
    cfg = inputs['setup']
    names = inputs['ion_ids']
    before = numbers(old['membrane_diffusion_m2_s'])
    profile = copy.deepcopy(before)
    for row in cfg['tissue_profiles']:
        if not row['cell_indices']:
            continue
        for role in ('Na', 'K', 'Cl', 'Ca', 'M', 'P'):
            if role in names:
                for j in row['membrane_indices']:
                    profile[names.index(role)][j] = d(row['diffusion_m2_s']['Dm_' + role])
    current = copy.deepcopy(profile)
    level = d(cfg['static_noise_level'])
    current[names.index('K')] = [(1 + level * d(u)) * v for u, v in zip(inputs['actual_static_uniforms'], profile[names.index('K')], strict=True)]
    denv = []
    environment = cfg['environment_diffusion']
    for i, free in enumerate(old['D_free']):
        values = [d(free)] * inputs['environment_sites']
        for j in environment['environment_in_cluster_indices']:
            values[j] = d(free) * d(environment['adherens_multiplier'])
        for key in ('all_bound_mem_inds', 'interior_bound_mem_inds', 'ecm_inds_bound_cell'):
            for j in inputs['grid_index_groups'][key]:
                values[j] = d(free) * d(environment['tight_junction_multiplier']) * d(environment['tight_junction_relative'][i])
        denv.append(values)
    mechanical = numbers(old['mechanics'])
    mechanical['div_u_osmo'] = [Decimal(0)] * inputs['cells']
    if inputs['mechanics_policy']['deformation']:
        mechanical['d_cells_x'] = [Decimal(0)] * inputs['cells']
        mechanical['d_cells_y'] = [Decimal(0)] * inputs['cells']
    sweep = cfg['frequency_sweep']
    slope = d(sweep['f slope']) if sweep['f slope'] is not None else (d(sweep['f stop']) - d(sweep['f start'])) / d(inputs['SIM_total_s']) if inputs['source_f_sweep_configured'] else None
    clock, sample_indices = ordinary.phase_clock(dict(init_total_s=inputs['time_profile']['sim_total_s'], init_dt_s=inputs['time_profile']['sim_dt_s'], init_sampling_s=inputs['time_profile']['sim_sampling_s']))
    return dict(clock=clock, sample_indices=sample_indices, Dm_base=profile, Dm_scheduled=[[Decimal(0) for _ in row] for row in profile], Dm_cells=current, D_env=denv, P_base=numbers(old['P_cells']), P_mod=numbers(old['P_cells']), mechanics=mechanical, rate_CaATP=copy.deepcopy(old['rate_CaATP']), rate_NaKATP=copy.deepcopy(old['rate_NaKATP']), rho_pump=1, rho_channel=1, source_phase='SIM', legacy_run_sim=True, new_call_index=0, new_material_dt_sum_s=0.0, retained_INIT_call_count=inputs['INIT_call_count'], f_sweep_slope=slope, grn_owner_reused=inputs['enabled']['grn'], grn_core_reused=inputs['enabled']['grn'], molecular_current_concentrations_retained=any(inputs['enabled'].values()), source_cold_recapture=False, native_pickle_or_load_attested=False)
