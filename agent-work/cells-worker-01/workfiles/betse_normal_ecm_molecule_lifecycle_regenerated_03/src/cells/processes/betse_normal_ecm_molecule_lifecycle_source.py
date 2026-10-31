# ruff: noqa: E501, E731, F841, B007, B905
"""Private native general owner and explicit FULL general-then-GRN source slices.

No shared scientific module is patched. Qualified molecule/ECM kernels are
reused; helper role lowering changes owner access and evidence wiring only.
"""
from cells.processes import betse_environment_field as environment
import posixpath as pathnames
from collections import OrderedDict
from types import SimpleNamespace
import numpy as np
from cells.processes import betse_normal_ecm_catalog_join_source as qualified
MasterOfGenes = qualified.MasterOfGenes
set_net_opts = qualified.base.set_net_opts
logs = qualified.logs
clone = qualified.clone
PARAMETERS = qualified.PARAMETERS
validate_cached_channels = qualified.validate_cached_channels
channel_fields = qualified.channel_fields
material_values = qualified.material_values

def science_general():
    return dict(qualified.science(), MasterOfGenes=MasterOfMolecules, MasterOfNetworks=MasterOfNetworks, Transporter=Transporter)

class MasterOfMolecules:

    def __init__(self, p):
        self.savedMoM = pathnames.join(p.init_pickle_dirname, 'GeneralNetwork.betse')

    def read_mol_config(self, phase):
        cells = phase.cells
        p = phase.p
        sim = phase.sim
        config_dic = p.network_config
        substances_config = config_dic['biomolecules']
        reactions_config = config_dic.get('reactions', None)
        transporters_config = config_dic.get('transporters', None)
        channels_config = config_dic.get('channels', None)
        modulators_config = config_dic.get('modulators', None)
        self.core = MasterOfNetworks(sim, cells, substances_config, p)
        self.core.time_dila = float(config_dic.get('time dilation factor', 1.0))
        self.core.read_substances(sim, cells, substances_config, p)
        self.core.tissue_init(phase, substances_config)
        if reactions_config is not None:
            self.core.read_reactions(reactions_config, sim, cells, p)
            self.core.write_reactions()
            self.core.create_reaction_matrix()
            self.core.write_reactions_env()
            self.core.create_reaction_matrix_env()
            self.reactions = True
        else:
            self.core.create_reaction_matrix()
            self.core.create_reaction_matrix_env()
            self.reactions = False
        if transporters_config is not None:
            self.core.read_transporters(transporters_config, phase)
            self.core.write_transporters(sim, cells, p)
            self.transporters = True
        else:
            self.transporters = False
        if channels_config is not None:
            self.core.read_channels(channels_config, phase)
            self.channels = True
        else:
            self.channels = False
        if modulators_config is not None:
            self.core.read_modulators(modulators_config, sim, cells, p)
            self.modulators = True
        else:
            self.modulators = False
        self.core.net_plot_opts = config_dic.get('network plotting', None)
        set_net_opts(self.core, self.core.net_plot_opts, p)
        optim_exists = config_dic.get('optimization', None)
        if optim_exists is not None:
            opti = config_dic['optimization']['optimize network']
            self.core.opti_N = config_dic['optimization']['optimization steps']
            self.core.opti_method = config_dic['optimization']['optimization method']
            self.core.target_vmem = float(config_dic['optimization']['target Vmem'])
            self.core.opti_T = float(config_dic['optimization']['optimization T'])
            self.core.opti_step = float(config_dic['optimization']['optimization step'])
            if opti:
                logs.log_info('Analyzing the general network for optimal rates...')
                self.core.optimizer(sim, cells, p)
                self.reinitialize(phase)

    def reinitialize(self, phase):
        cells = phase.cells
        p = phase.p
        sim = phase.sim
        config_dic = p.network_config
        self.core.time_dila = float(config_dic.get('time dilation factor', 1.0))
        substances_config = config_dic['biomolecules']
        reactions_config = config_dic.get('reactions', None)
        transporters_config = config_dic.get('transporters', None)
        channels_config = config_dic.get('channels', None)
        modulators_config = config_dic.get('modulators', None)
        self.core.tissue_init(phase, substances_config)
        if reactions_config is not None:
            self.core.read_reactions(reactions_config, sim, cells, p)
            self.core.write_reactions()
            self.core.create_reaction_matrix()
            self.core.write_reactions_env()
            self.core.create_reaction_matrix_env()
            self.reactions = True
        else:
            self.core.create_reaction_matrix()
            self.core.create_reaction_matrix_env()
            self.reactions = False
        if transporters_config is not None:
            self.core.read_transporters(transporters_config, phase)
            self.core.write_transporters(sim, cells, p)
            self.transporters = True
        else:
            self.transporters = False
        if channels_config is not None:
            self.core.read_channels(channels_config, phase)
            self.channels = True
        else:
            self.channels = False
        if modulators_config is not None:
            self.core.read_modulators(modulators_config, sim, cells, p)
            self.modulators = True
        else:
            self.modulators = False

def initialize_both(self, t, phase, cells, p, *, hook):
    if p.molecules_enabled:
        hook('molecules', 'before_setup', self, phase)
        if self.molecules is None:
            logs.log_info('Initializing general network...')
            self.molecules = MasterOfMolecules(p)
            self.molecules.read_mol_config(phase)
        else:
            logs.log_info('Reinitializing the general regulatory network for simulation...')
            self.molecules.reinitialize(phase)
        hook('molecules', 'after_setup', self, phase)
    if p.grn_enabled:
        hook('grn', 'before_setup', self, phase)
        if self.grn is None:
            logs.log_info('Initializing gene regulatory network...')
            self.grn = MasterOfGenes(p)
            self.grn.read_gene_config(phase)
        else:
            logs.log_info('Reinitializing the gene regulatory network for simulation...')
            self.grn.reinitialize(phase)
        hook('grn', 'after_setup', self, phase)

def dispatch_both(self, t, phase, cells, p, *, hook):
    if p.molecules_enabled:
        hook('molecules', 'before_dispatch', self, phase)
        self.molecules.core.clear_run_loop(self)
        hook('molecules', 'clear_run_loop', self, phase)
        if self.molecules.transporters:
            self.molecules.core.run_loop_transporters(t, self, cells, p)
            hook('molecules', 'run_loop_transporters', self, phase)
        if self.molecules.channels:
            self.molecules.core.run_loop_channels(phase)
            hook('molecules', 'run_loop_channels', self, phase)
        if self.molecules.modulators:
            self.molecules.core.run_loop_modulators(self, cells, p)
            hook('molecules', 'run_loop_modulators', self, phase)
        self.molecules.core.run_loop(phase=phase, t=t)
        hook('molecules', 'run_loop', self, phase)
    if p.grn_enabled:
        hook('grn', 'before_dispatch', self, phase)
        self.grn.core.clear_run_loop(self)
        hook('grn', 'clear_run_loop', self, phase)
        if self.grn.transporters:
            self.grn.core.run_loop_transporters(t, self, cells, p)
            hook('grn', 'run_loop_transporters', self, phase)
        if self.grn.channels:
            self.grn.core.run_loop_channels(phase)
            hook('grn', 'run_loop_channels', self, phase)
        if self.grn.modulators:
            self.grn.core.run_loop_modulators(self, cells, p)
            hook('grn', 'run_loop_modulators', self, phase)
        self.grn.core.run_loop(phase=phase, t=t)
        hook('grn', 'run_loop', self, phase)

def cache_general(ctx):
    return dict(kind='cells.ecm_catalog_grn_owner_cache@1', wire=wire(getattr(ctx.sim, 'molecules', None), ctx.sim), coefficient_fields={name: clone(getattr(ctx.sim, name)) for name in ('D_env_weight', 'D_env_weight_base', 'TJ_targets') if hasattr(ctx.sim, name)}, initial_channel_fields=clone(ctx.initial_channel_fields), channel_calls=clone(ctx.channel_calls), initial_transporter_fields=clone(ctx.initial_transporter_fields))

def restore_general(ctx, incoming):
    if incoming is None or incoming.get('kind') != 'cells.ecm_catalog_grn_owner_cache@1':
        raise ValueError('Require complete ECM catalog GRN owner cache')
    raw = incoming['wire']
    if set(raw) != {'owner_fields', 'core_fields', 'molecule_fields', 'reaction_fields', 'modulator_fields', 'ion_boundary_state', 'simulator_fields', 'channel_fields', 'transporter_fields'}:
        raise ValueError('Require every ECM owner/cache field')
    if set(raw['molecule_fields']) != {'X', 'Y'}:
        raise ValueError('Require both configured ECM gene products')
    for values in raw['molecule_fields'].values():
        if not set(PARAMETERS) | {'c_cells', 'cc_at_mem', 'c_env', 'flux_intra', 'gad_eval_string'} <= values.keys():
            raise ValueError('Missing source-initialized ECM gene fields')
        if values['ignore_ECM_pump'] is not True:
            raise ValueError('Preserve actual source ignore_ECM_pump default')
    validate_cached_transporters(ctx, incoming)
    ctx.initial_transporter_fields = clone(incoming['initial_transporter_fields'])
    validate_cached_channels(ctx, incoming)
    ctx.initial_channel_fields = clone(incoming['initial_channel_fields'])
    ctx.channel_calls = clone(incoming['channel_calls'])
    api = science_general()
    owner = object.__new__(api['MasterOfGenes'])
    vars(owner).update(clone(raw['owner_fields']))
    net = object.__new__(api['MasterOfNetworks'])
    vars(net).update(clone(raw['core_fields']))
    owner.core, ctx.sim.molecules = (net, owner)
    for attr, key, cls in (('molecules', 'molecule_fields', 'Molecule'), ('reactions', 'reaction_fields', 'Reaction'), ('modulators', 'modulator_fields', 'Modulator')):
        objects = OrderedDict()
        for name, fields in raw[key].items():
            obj = object.__new__(api[cls])
            vars(obj).update(clone(fields))
            objects[name] = obj
        setattr(net, attr, objects)
    net.reactions_env, net.reactions_mit, net.channels, net.mit = (OrderedDict(), OrderedDict(), OrderedDict(), None)
    for name, saved in raw['channel_fields'].items():
        obj = object.__new__(api['Channel'])
        vars(obj).update(clone(saved['fields']))
        core = object.__new__(api['class_for'](saved['core_class']))
        vars(core).update(clone(saved['core_fields']))
        obj.channel_core = core
        net.channels[name] = obj
    for key, value in raw['simulator_fields'].items():
        setattr(ctx.sim, key, clone(value))
    if set(incoming['coefficient_fields']) != {'D_env_weight', 'D_env_weight_base', 'TJ_targets'}:
        raise ValueError('Require owned ECM molecular grid coefficients')
    for key, value in incoming['coefficient_fields'].items():
        setattr(ctx.sim, key, clone(value))
    for attr, ionic, molecular in (('cell_concs', 'cc_cells', 'c_cells'), ('mem_concs', 'cc_at_mem', 'cc_at_mem'), ('env_concs', 'cc_env', 'c_env'), ('bound_concs', 'c_env_bound', 'c_bound')):
        mapping = OrderedDict()
        for name, enabled in ctx.p.ions_dict.items():
            if enabled != 1:
                continue
            i = ctx.sim.get_ion(name)
            mapping[name] = api['DynamicValue'](lambda i=i, a=ionic: getattr(ctx.sim, a)[i], lambda value, i=i, a=ionic: getattr(ctx.sim, a).__setitem__(i, value))
        for name in net.molecules:
            mapping[name] = api['DynamicValue'](lambda name=name, a=molecular: getattr(net.molecules[name], a), lambda value, name=name, a=molecular: setattr(net.molecules[name], a, value))
        setattr(net, attr, api['DynamicValueDict'](mapping))
    net.mit_concs = None
    net.transporters = OrderedDict()
    for name, fields in raw['transporter_fields'].items():
        obj = object.__new__(api['Transporter'])
        vars(obj).update(clone(fields))
        net.transporters[name] = obj
    return net

def before_general(ctx, material_declaration):
    sim, p, cells, net = (ctx.sim, ctx.p, ctx.cells, ctx.net)
    configured = []
    for name, obj in net.molecules.items():
        g = dict(enabled=obj.simple_growth, production_rate_mM_s=0.0 if obj.r_production is None else obj.r_production, decay_rate_per_s=0.0 if obj.r_decay is None else obj.r_decay, decay_max_per_s=0.0 if not obj.simple_growth else obj.decay_max, scale_factor=obj.gad_scale_factor)
        configured.append(dict(name=name, parameters={key: clone(getattr(obj, key)) for key in PARAMETERS}, growth=g))
    return dict(conditioned_before_model_network=True, ecm_normal_grn=True, material_declaration=clone(material_declaration), definition=dict(molecules=configured, grn_configuration=clone(p.network_config), reactions=clone(p.network_config['reactions']), modulators=clone(p.network_config.get('modulators') or [])), values_before=material_values(sim), molecule_states_before={name: {key: clone(getattr(obj, key)) for key in ('c_cells', 'cc_at_mem', 'c_env', 'flux_intra')} for name, obj in net.molecules.items()}, cache_before=cache_general(ctx), controls_before=dict(gj_block=clone(sim.gj_block), NaKATP_block=clone(sim.NaKATP_block)), molecular_geometry=dict(owner=clone(cells.mem_to_cells), partner=clone(cells.nn_i), boundary=clone(cells.bflags_mems), membrane_area_m2=clone(cells.mem_sa), cell_volume_m3=clone(cells.cell_vol), gap_length_m=clone(cells.gj_len)), dt_s=p.dt, F=p.F, R=p.R, q_C=p.q, kb_J_K=p.kb, membrane_thickness_m=p.tm, runtime_temperature_K=sim.T, configured_temperature_K=p.T, gap_open=clone(sim.gjopen), rho_channel=clone(sim.rho_channel), ion_ids=list(ctx.ion_ids), valence=clone(sim.zs), electric_x_source=clone(sim.E_env_x), electric_y_source=clone(sim.E_env_y), D_env=clone(sim.D_env), grid_index_groups=clone(ctx.definition['grid_index_groups']), substances_affect_charge=p.substances_affect_charge, sharpness=p.sharpness, cluster_open=p.cluster_open, incoming_channel_current_A_m2=clone(net.extra_J_mem), simulator_fields_before=wire(sim.molecules, sim)['simulator_fields'], owner=owner_evidence_general(ctx))

def attach_general(ctx, material_declaration, observer=None, channel_observer=None, transporter_observer=None):
    sim, p, net = (ctx.sim, ctx.p, ctx.net)
    attach_transporters(ctx)

    def chemistry(stage, species, actual):
        ctx.trace['molecule_frames'].append(dict(stage=stage, species=species, values=material_values(sim), cache=cache_general(ctx)))

    def mover(stage, name, local, actual):
        fields = ('cX_env_o', 'cX_cells', 'cX_mems', 'f_X_ED', 'fgj_X', 'fenvx', 'fenvy', 'cenv', 'gcx', 'gcy', 'fx', 'fy', 'div_fa', 'denv_multiplier')
        ctx.trace['mover_frames'].append(dict(stage=stage, species=name, fields={key: clone(local.get(key)) for key in fields}, vm=clone(actual.vm), vgj=clone(actual.vgj)))

    def rhs(growth, reaction, all_rates):
        ctx.trace['rhs'] = dict(growth_rates=clone(growth), reaction_rates=clone(reaction), all_rates=clone(all_rates))

    def control(name, value, actual):
        ctx.trace['control_writes'].append(dict(rule_id=name, target=net.modulators[name].target_label, value=clone(value), gj_block=clone(actual.gj_block), NaKATP_block=clone(actual.NaKATP_block)))

    def dispatched(stage, actual, phase):
        ctx.trace['dispatch_stages'].append(stage)
        if stage == 'clear_run_loop' and ctx.sim.molecules.transporters:
            ctx.trace['before_transporters'] = transporter_before(ctx, material_declaration)
            if transporter_observer is not None:
                transporter_observer(clone(ctx.trace['before_transporters']))
        ready = stage == 'run_loop_transporters' or (stage == 'clear_run_loop' and (not ctx.sim.molecules.transporters))
        if ready:
            ctx.trace['before_channels'] = before_general(ctx, material_declaration)
            ctx.trace['before_channels'].update(mode='channels', catalog=clone(ctx.catalog))
            if channel_observer is not None:
                channel_observer(clone(ctx.trace['before_channels']))
        if stage == 'run_loop_channels' or (ready and (not ctx.sim.molecules.channels)):
            ctx.trace['before'] = before_general(ctx, material_declaration)
            if observer is not None:
                observer(clone(ctx.trace['before']))
    net._observe_chem, net._observe_rhs, net._observe_control, net._observe_dispatch, p._mover_observe = (chemistry, rhs, control, dispatched, mover)

def install_channel_observer_general(ctx):

    def observe(stage, name, local):
        obj = local.get('chan', local.get('obj'))
        values = dict(stage=stage, name=name, values=material_values(ctx.sim), cache=cache_general(ctx), fields={key: clone(local[key]) for key in ('ion', 'rel_perm', 'zzz', 'ioni', 'DChan', 'cenv', 'ccell', 'cmem', 'f_ED', 'moddy') if key in local}, population=None if obj is None else dict(fields={k: clone(v) for k, v in vars(obj).items() if k != 'channel_core'}, core_fields=None if not hasattr(obj, 'channel_core') else clone(vars(obj.channel_core))), incoming_current=clone(ctx.sim.molecules.core.extra_J_mem))
        if stage.startswith('initialize') or stage == 'configuration_after':
            ctx.trace['channel_initializations'].append(values)
        else:
            if stage == 'population_after':
                ctx.channel_calls[name] += 1
                values['cache'] = cache_general(ctx)
            ctx.trace['channel_events'].append(values)
    ctx.p._catalog_observe = observe

def owner_evidence_general(ctx):
    return dict(owner_class=type(ctx.sim.molecules).__name__, core_class=type(ctx.sim.molecules.core).__name__, actual_core_identity=ctx.sim.molecules.core is ctx.net, grn_enabled=ctx.p.grn_enabled, molecules_enabled=ctx.p.molecules_enabled, standalone_sim_grn=False)
tex_val = str
BetseSimConfException = ValueError
stb = SimpleNamespace(div_env=qualified.base.div_env)

class Transporter(object):

    def __init__(self, sim, cells, p):
        self.name = None
        self.reactants_list = None
        self.reactants_coeff = None
        self.products_list = None
        self.products_coeff = None
        self.Km_reactants_list = None
        self.Km_products_list = None
        self.vmax = None
        self.delta_Go = None
        self.reaction_zone = None
        self.c_reactants = []
        self.z_reactants = []
        self.inds_react = []
        self.c_products = []
        self.z_products = []
        self.inds_prod = []
        self.product_source_object = []
        self.product_source_type = []
        self.reactant_source_object = []
        self.reactant_source_type = []
        self.transporter_activators_list = None
        self.transporter_activators_Km = None
        self.transporter_activators_n = None
        self.transporter_inhibitors_list = None
        self.transporter_inhibitors_Km = None
        self.transporter_inhibitors_n = None
        self.transport_out_list = None
        self.transport_in_list = None
        self.flux = None

    def init_reaction(self, phase):
        sim = phase.sim
        cells = phase.cells
        p = phase.p
        if self.transporter_profiles_list is not None and self.transporter_profiles_list != 'all' and (self.transporter_profiles_list != 'express'):
            self.transporter_targets_mem = []
            self.transporter_targets_cell = []
            self.transporter_targets_env = []
            for profile in self.transporter_profiles_list:
                targets_cell = phase.dyna.cell_target_inds[profile]
                self.transporter_targets_cell.extend(targets_cell)
                targets_mem = phase.dyna.tissue_target_inds[profile]
                self.transporter_targets_mem.extend(targets_mem)
                targets_env = phase.dyna.env_target_inds[profile]
                self.transporter_targets_env.extend(targets_env)
        elif self.transporter_profiles_list == 'express':
            self.transporter_targets_mem = cells.mem_i
            self.transporter_targets_cell = cells.cell_i
            self.transporter_targets_env = cells.map_mem2ecm
            self.expr_map_cell = np.zeros(sim.cdl)
            self.expr_map_mem = np.zeros(sim.mdl)
            for region, val in p.expression_data[self.name].items():
                tinds_mem = phase.dyna.tissue_target_inds[region]
                tinds_cell = phase.dyna.cell_target_inds[region]
                self.expr_map_mem[tinds_mem] = val
                self.expr_map_cell[tinds_cell] = val
            self.vmax = self.vmax * self.expr_map_mem
        else:
            self.transporter_targets_mem = cells.mem_i
            self.transporter_targets_cell = cells.cell_i
            self.transporter_targets_env = cells.map_mem2ecm

class MasterOfNetworks(qualified.MasterOfNetworks):

    def read_transporters(self, config_transporters, phase):
        sim = phase.sim
        cells = phase.cells
        p = phase.p
        logs.log_info('Reading transporter input data...')
        self.transporters = OrderedDict({})
        for q, trans_dic in enumerate(config_transporters):
            name = str(trans_dic['name'])
            self.transporters[name] = Transporter(sim, cells, p)
            obj = self.transporters[name]
            obj.name = name
            obj.reaction_zone = trans_dic['reaction zone']
            obj.reactants_list = trans_dic['reactants']
            obj.reactants_coeff = trans_dic['reactant multipliers']
            obj.products_list = trans_dic['products']
            obj.products_coeff = trans_dic['product multipliers']
            obj.Km_reactants_list = trans_dic['Km reactants']
            obj.Km_products_list = trans_dic['Km products']
            obj.transport_out_list = trans_dic['transfered out of cell']
            obj.transport_in_list = trans_dic['transfered into cell']
            obj.vmax = float(trans_dic['max rate'])
            obj.delta_Go = trans_dic['standard free energy']
            obj.ignore_ECM_transporter = trans_dic['ignore ECM']
            obj.transporter_profiles_list = trans_dic['apply to']
            obj.init_reaction(phase)
            if obj.delta_Go == 'None':
                obj.delta_Go = None
            else:
                obj.delta_Go = float(obj.delta_Go)
            obj.transporter_activators_list = trans_dic.get('transporter activators', None)
            obj.transporter_activators_Km = trans_dic.get('activator Km', None)
            obj.transporter_activators_n = trans_dic.get('activator n', None)
            obj.transporter_activators_zone = trans_dic.get('activator zone', None)
            obj.transporter_inhibitors_list = trans_dic.get('transporter inhibitors', None)
            obj.transporter_inhibitors_Km = trans_dic.get('inhibitor Km', None)
            obj.transporter_inhibitors_n = trans_dic.get('inhibitor n', None)
            obj.transporter_inhibitors_zone = trans_dic.get('inhibitor zone', None)
            obj.transporter_activators_zone, obj.transporter_inhibitors_zone = self.default_zones(obj.transporter_activators_zone, obj.transporter_inhibitors_zone, obj.transporter_activators_list, obj.transporter_inhibitors_list)
            if self.mit_enabled:
                obj.mit_enabled = True
            else:
                obj.mit_enabled = False
        for name in self.transporters:
            msg = 'Including the network transporter: {}'.format(name)
            logs.log_info(msg)

    def write_transporters(self, sim, cells, p):
        logs.log_info('Writing transporter equations...')
        for transp_name in self.transporters:
            trans_tex_var_list = []
            self.transporters[transp_name].net_z = 0
            reactant_names = self.transporters[transp_name].reactants_list
            reactant_coeff = self.transporters[transp_name].reactants_coeff
            reactant_Km = self.transporters[transp_name].Km_reactants_list
            product_names = self.transporters[transp_name].products_list
            product_coeff = self.transporters[transp_name].products_coeff
            product_Km = self.transporters[transp_name].Km_products_list
            a_list = self.transporters[transp_name].transporter_activators_list
            Km_a_list = self.transporters[transp_name].transporter_activators_Km
            n_a_list = self.transporters[transp_name].transporter_activators_n
            i_list = self.transporters[transp_name].transporter_inhibitors_list
            Km_i_list = self.transporters[transp_name].transporter_inhibitors_Km
            n_i_list = self.transporters[transp_name].transporter_inhibitors_n
            reaction_zone = self.transporters[transp_name].reaction_zone
            transport_out_list = self.transporters[transp_name].transport_out_list
            transport_in_list = self.transporters[transp_name].transport_in_list
            react_transfer_tag = ['mem_concs' for x in reactant_names]
            prod_transfer_tag = ['mem_concs' for x in product_names]
            echem_terms_list = []
            echem_terms_list_tex = []
            if reaction_zone == 'cell':
                type_out = 'env_concs'
                vmem = 'sim.vm'
                vmem_tex = 'V_{mem}'
                in_delta_term_react = "(np.dot(cells.M_sum_mems, -self.transporters['{}'].flux*cells.mem_sa)/cells.cell_vol)".format(transp_name)
                in_delta_term_prod = "(np.dot(cells.M_sum_mems, self.transporters['{}'].flux*cells.mem_sa)/cells.cell_vol)".format(transp_name)
                if p.is_ecm is True:
                    out_delta_term_react = "stb.div_env(-self.transporters['{}'].flux, cells, p)".format(transp_name)
                    out_delta_term_prod = "stb.div_env(self.transporters['{}'].flux, cells, p)".format(transp_name)
                else:
                    out_delta_term_react = "(np.dot(cells.M_sum_mems, -self.transporters['{}'].flux*cells.mem_sa)/cells.cell_vol)".format(transp_name)
                    out_delta_term_prod = "(np.dot(cells.M_sum_mems, self.transporters['{}'].flux*cells.mem_sa)/cells.cell_vol)".format(transp_name)
                all_alpha, alpha_tex, trans_tex_var_list = self.get_influencers(a_list, Km_a_list, n_a_list, i_list, Km_i_list, n_i_list, tex_list=trans_tex_var_list, reaction_zone='mem', in_mem_tag=False)
            elif reaction_zone == 'mit' and self.mit_enabled is True:
                vmem_tex = 'V_{mit}'
                react_transfer_tag = ['mit_concs' for x in reactant_names]
                prod_transfer_tag = ['mit_concs' for x in product_names]
                type_out = 'cell_concs'
                vmem = 'self.mit.Vmit'
                in_delta_term_react = "-self.transporters['{}'].flux*(self.mit.mit_sa/self.mit.mit_vol)".format(transp_name)
                in_delta_term_prod = "self.transporters['{}'].flux*(self.mit.mit_sa/self.mit.mit_vol)".format(transp_name)
                out_delta_term_react = "-self.transporters['{}'].flux*(self.mit.mit_sa/cells.cell_vol)".format(transp_name)
                out_delta_term_prod = "self.transporters['{}'].flux*(self.mit.mit_sa/cells.cell_vol)".format(transp_name)
                all_alpha, alpha_tex, trans_tex_var_list = self.get_influencers(a_list, Km_a_list, n_a_list, i_list, Km_i_list, n_i_list, reaction_zone='mit', tex_list=trans_tex_var_list, in_mem_tag=False)
            delta_strings_reactants = [in_delta_term_react for x in reactant_names]
            delta_strings_products = [in_delta_term_prod for x in product_names]
            if transport_out_list != 'None':
                for out_name in transport_out_list:
                    if out_name in p.ions_dict:
                        if p.ions_dict[out_name] == 1:
                            ion_ind = sim.get_ion(out_name)
                            prod_i = product_names.index(out_name)
                            prod_transfer_tag[prod_i] = type_out
                            coeff = product_coeff[prod_i]
                            eterm = '-{}*sim.zs[{}]*p.F*{}'.format(coeff, ion_ind, vmem)
                            self.transporters[transp_name].net_z += coeff * sim.zs[ion_ind]
                            eterm_tex = '-%s\\,[%s]\\,z_{%s}\\,F\\,%s' % (coeff, out_name, out_name, vmem_tex)
                            zval = tex_val(sim.zs[ion_ind])
                            z_tex = 'z_{%s} & =' % out_name
                            z_tex += zval
                    else:
                        prod_i = product_names.index(out_name)
                        prod_transfer_tag[prod_i] = type_out
                        coeff = product_coeff[prod_i]
                        eterm = "-{}*self.molecules['{}'].z*p.F*{}".format(coeff, out_name, vmem)
                        self.transporters[transp_name].net_z += coeff * self.molecules[out_name].z
                        eterm_tex = '-%s\\,[%s]\\,z_{%s}\\,F\\,%s' % (coeff, out_name, out_name, vmem_tex)
                        zval = tex_val(self.molecules[out_name].z)
                        z_tex = 'z_{%s} & =' % out_name
                        z_tex += zval
                    trans_tex_var_list.append(z_tex)
                    echem_terms_list.append(eterm)
                    echem_terms_list_tex.append(eterm_tex)
                    delta_strings_products[prod_i] = out_delta_term_prod
            if transport_in_list != 'None':
                for in_name in transport_in_list:
                    if in_name in p.ions_dict:
                        if p.ions_dict[in_name] == 1:
                            ion_ind = sim.get_ion(in_name)
                            react_i = reactant_names.index(in_name)
                            react_transfer_tag[react_i] = type_out
                            coeff = reactant_coeff[react_i]
                            eterm = '{}*sim.zs[{}]*p.F*{}'.format(coeff, ion_ind, vmem)
                            self.transporters[transp_name].net_z += -coeff * sim.zs[ion_ind]
                            eterm_tex = '%s\\,[%s]\\,z_{%s}\\,F\\,%s' % (coeff, in_name, in_name, vmem_tex)
                            zval = tex_val(sim.zs[ion_ind])
                            z_tex = 'z_{%s} & =' % in_name
                            z_tex += zval
                    else:
                        react_i = reactant_names.index(in_name)
                        react_transfer_tag[react_i] = type_out
                        coeff = reactant_coeff[react_i]
                        eterm = "{}*self.molecules['{}'].z*p.F*{}".format(coeff, in_name, vmem)
                        self.transporters[transp_name].net_z += -coeff * self.molecules[in_name].z
                        eterm_tex = '%s\\,[%s]\\,z_{%s}\\,F\\,%s' % (coeff, in_name, in_name, vmem_tex)
                        zval = tex_val(self.molecules[in_name].z)
                        z_tex = 'z_{%s} & =' % in_name
                        z_tex += zval
                    trans_tex_var_list.append(z_tex)
                    echem_terms_list.append(eterm)
                    echem_terms_list_tex.append(eterm_tex)
                    delta_strings_reactants[react_i] = out_delta_term_react
            echem_string = '('
            echem_tex_string = ''
            for i, (et, etx) in enumerate(zip(echem_terms_list, echem_terms_list_tex)):
                echem_string += et
                echem_tex_string += etx
                if i < len(echem_terms_list) - 1:
                    echem_string += '+'
                    echem_tex_string += '+'
                else:
                    echem_string += ')'
            numo_string_Q = '('
            denomo_string_Q = '('
            numo_tex = ''
            deno_tex = ''
            for i, (name, coeff, tag) in enumerate(zip(reactant_names, reactant_coeff, react_transfer_tag)):
                if tag == 'mem_concs':
                    denomo_string_Q += "(1.0e-3*self.{}['{}']".format(tag, name)
                    tex_name = name
                elif tag == 'mit_concs':
                    denomo_string_Q += "(1.0e-3*self.{}['{}']".format(tag, name)
                    tex_name = name + '_{mit}'
                elif tag == 'cell_concs':
                    denomo_string_Q += "(1.0e-3*self.{}['{}']".format(tag, name)
                    tex_name = name
                elif tag == 'env_concs':
                    if p.is_ecm is True:
                        denomo_string_Q += "(1.0e-3*self.{}['{}'][cells.map_mem2ecm]".format(tag, name)
                    else:
                        denomo_string_Q += "(1.0e-3*self.{}['{}']".format(tag, name)
                    tex_name = name + '_{env}'
                else:
                    raise BetseSimConfException('Transporter tag not properly defined!')
                denomo_string_Q += '**{})'.format(coeff)
                deno_tex += '[%s]^{%s}' % (tex_name, coeff)
                if i < len(reactant_names) - 1:
                    denomo_string_Q += '*'
                    deno_tex += '\\,'
                else:
                    denomo_string_Q += ')'
            for i, (name, coeff, tag) in enumerate(zip(product_names, product_coeff, prod_transfer_tag)):
                if tag == 'mem_concs':
                    numo_string_Q += "(1.0e-3*self.{}['{}']".format(tag, name)
                    tex_name = name
                elif tag == 'mit_concs':
                    numo_string_Q += "(1.0e-3*self.{}['{}']".format(tag, name)
                    tex_name = name + '_{mit}'
                elif tag == 'cell_concs':
                    numo_string_Q += "(1.0e-3*self.{}['{}']".format(tag, name)
                    tex_name = name
                elif tag == 'env_concs':
                    if p.is_ecm is True:
                        numo_string_Q += "(1.0e-3*self.{}['{}'][cells.map_mem2ecm]".format(tag, name)
                    else:
                        numo_string_Q += "(1.0e-3*self.{}['{}']".format(tag, name)
                    tex_name = name + '_{env}'
                else:
                    raise BetseSimConfException('Transporter tag not properly defined!')
                numo_string_Q += '**{})'.format(coeff)
                numo_tex += '[%s]^{%s}' % (tex_name, coeff)
                if i < len(product_names) - 1:
                    numo_string_Q += '*'
                    numo_tex += '\\,'
                else:
                    numo_string_Q += ')'
            Q = '(' + numo_string_Q + '/' + denomo_string_Q + ')'
            Q_tex = '\\frac{%s}{%s}' % (numo_tex, deno_tex)
            forward_coeff = '('
            backward_coeff = '('
            fwd_tex_coeff = ''
            bwd_tex_coeff = ''
            for i, (name, n, Km, tag) in enumerate(zip(reactant_names, reactant_coeff, reactant_Km, react_transfer_tag)):
                if tag == 'mem_concs':
                    numo_string_r = "((self.{}['{}']/{})**{})".format(tag, name, Km, n)
                    denomo_string_r = "(1 + (self.{}['{}']/{})**{})".format(tag, name, Km, n)
                    tex_name = name
                elif tag == 'mit_concs':
                    numo_string_r = "((self.{}['{}']/{})**{})".format(tag, name, Km, n)
                    denomo_string_r = "(1 + (self.{}['{}']/{})**{})".format(tag, name, Km, n)
                    tex_name = name + '_{mit}'
                elif tag == 'cell_concs':
                    numo_string_r = "((self.{}['{}']/{})**{})".format(tag, name, Km, n)
                    denomo_string_r = "(1 + (self.{}['{}']/{})**{})".format(tag, name, Km, n)
                    tex_name = name
                elif tag == 'env_concs':
                    if p.is_ecm is True:
                        numo_string_r = "((self.{}['{}'][cells.map_mem2ecm]/{})**{})".format(tag, name, Km, n)
                        denomo_string_r = "(1 + (self.{}['{}'][cells.map_mem2ecm]/{})**{})".format(tag, name, Km, n)
                    else:
                        numo_string_r = "((self.{}['{}']/{})**{})".format(tag, name, Km, n)
                        denomo_string_r = "(1 + (self.{}['{}']/{})**{})".format(tag, name, Km, n)
                    tex_name = name + '_{env}'
                else:
                    raise BetseSimConfException('Transporter tag not properly defined!')
                term = '(' + numo_string_r + '/' + denomo_string_r + ')'
                forward_coeff += term
                cc_tex = '\\left(\\frac{[%s]}{K_{%s_f}^{%s}}\\right)^{n_{%s_f}^{%s}}' % (tex_name, transp_name, tex_name, transp_name, tex_name)
                fwd_tex_coeff += '\\left(\\frac{%s}{1+%s}\\right)' % (cc_tex, cc_tex)
                if i < len(reactant_names) - 1:
                    forward_coeff += '*'
                    fwd_tex_coeff += '\\,'
                else:
                    forward_coeff += ')'
                kval = tex_val(Km)
                k_tex = 'K_{%s}^{%s} & =' % (transp_name, tex_name)
                k_tex += kval
                trans_tex_var_list.append(k_tex)
                nval = tex_val(n)
                n_tex = 'n_{%s}^{%s} & =' % (transp_name, tex_name)
                n_tex += nval
                trans_tex_var_list.append(n_tex)
            for i, (name, n, Km, tag) in enumerate(zip(product_names, product_coeff, product_Km, prod_transfer_tag)):
                if tag == 'mem_concs':
                    numo_string_p = "((self.{}['{}']/{})**{})".format(tag, name, Km, n)
                    denomo_string_p = "(1 + (self.{}['{}']/{})**{})".format(tag, name, Km, n)
                    tex_name = name
                elif tag == 'mit_concs':
                    numo_string_p = "((self.{}['{}']/{})**{})".format(tag, name, Km, n)
                    denomo_string_p = "(1 + (self.{}['{}']/{})**{})".format(tag, name, Km, n)
                    tex_name = name + '_{mit}'
                elif tag == 'cell_concs':
                    numo_string_p = "((self.{}['{}']/{})**{})".format(tag, name, Km, n)
                    denomo_string_p = "(1 + (self.{}['{}']/{})**{})".format(tag, name, Km, n)
                    tex_name = name
                elif tag == 'env_concs':
                    if p.is_ecm is True:
                        numo_string_p = "((self.{}['{}'][cells.map_mem2ecm]/{})**{})".format(tag, name, Km, n)
                        denomo_string_p = "(1 + (self.{}['{}'][cells.map_mem2ecm]/{})**{})".format(tag, name, Km, n)
                    else:
                        numo_string_p = "((self.{}['{}']/{})**{})".format(tag, name, Km, n)
                        denomo_string_p = "(1 + (self.{}['{}']/{})**{})".format(tag, name, Km, n)
                    tex_name = name + '_{env}'
                else:
                    raise BetseSimConfException('Transporter tag not properly defined!')
                term = '(' + numo_string_p + '/' + denomo_string_p + ')'
                backward_coeff += term
                cc_tex = '\\left(\\frac{[%s]}{K_{%s_r}^{%s}}\\right)^{n_{%s_r}^{%s}}' % (tex_name, transp_name, tex_name, transp_name, tex_name)
                bwd_tex_coeff += '\\left(\\frac{%s}{1+%s}\\right)' % (cc_tex, cc_tex)
                if i < len(product_names) - 1:
                    backward_coeff += '*'
                    bwd_tex_coeff += '\\,'
                else:
                    backward_coeff += ')'
                if self.transporters[transp_name].delta_Go is not None:
                    kval = tex_val(Km)
                    k_tex = 'K_{%s}^{%s} & =' % (transp_name, tex_name)
                    k_tex += kval
                    trans_tex_var_list.append(k_tex)
                    nval = tex_val(n)
                    n_tex = 'n_{%s}^{%s} & =' % (transp_name, tex_name)
                    n_tex += nval
                    trans_tex_var_list.append(n_tex)
            if self.transporters[transp_name].delta_Go is not None:
                Keqm = "(np.exp(-(self.transporters['{}'].delta_Go + {})/ (p.R * sim.T)))".format(transp_name, echem_string)
                Keqm_tex = '\\frac{exp(-deltaG_{%s}^{o} + %s)}{R\\,T}' % (transp_name, echem_tex_string)
                gval = tex_val(self.transporters[transp_name].delta_Go)
                g_tex = 'deltaG_{%s}^{o} & =' % transp_name
                g_tex += gval
                trans_tex_var_list.append(g_tex)
            else:
                Q = '0'
                backward_coeff = '0'
                Keqm = '1'
                Keqm_tex = ''
            reversed_term = '(' + Q + '/' + Keqm + ')'
            rev_term_tex = '\\left(\\frac{%s}{%s}\\right)' % (Q_tex, Keqm_tex)
            vmax = "self.transporters['{}'].vmax".format(transp_name)
            v_texo = 'r_{%s}^{max}' % transp_name
            vm_tex = 'r_{%s}' % transp_name
            vval = tex_val(self.transporters[transp_name].vmax)
            v_tex = 'v_{%s}^{max} & =' % transp_name
            v_tex += vval
            trans_tex_var_list.append(v_tex)
            if self.transporters[transp_name].delta_Go is not None:
                transporter_tex_string = vm_tex + ' = ' + v_texo + '\\,' + alpha_tex + '\\,\\left(' + '1.0' + '-' + rev_term_tex + '\\,' + bwd_tex_coeff + '\\right)'
                transporter_eval_string = vmax + '*' + all_alpha + '*' + forward_coeff + '*' + '(' + '1.0' + '-' + reversed_term + ')'
            else:
                transporter_tex_string = vm_tex + ' = ' + v_tex + '\\,' + alpha_tex + '\\,' + fwd_tex_coeff
                transporter_eval_string = vmax + '*' + all_alpha + '*' + forward_coeff
            tex_params = '\\begin{aligned}'
            for i, tex_str in enumerate(trans_tex_var_list):
                tex_params += tex_str
                if i < len(trans_tex_var_list) - 1:
                    tex_params += '\\\\'
                elif i == len(trans_tex_var_list) - 1:
                    tex_params += '\\end{aligned}'
            self.transporters[transp_name].transporter_eval_string = transporter_eval_string
            self.transporters[transp_name].transporter_tex_string = transporter_tex_string
            self.transporters[transp_name].transporter_tex_vars = tex_params
            self.transporters[transp_name].delta_react_eval_strings = delta_strings_reactants
            self.transporters[transp_name].delta_prod_eval_strings = delta_strings_products
            self.transporters[transp_name].react_transport_tag = react_transfer_tag
            self.transporters[transp_name].prod_transport_tag = prod_transfer_tag

    def run_loop_transporters(self, t, sim, cells, p):
        globalo = globals()
        localo = locals()
        for name in self.transporters:
            self._observe_transporter('before', name, None, None, sim)
            targ_mem = self.transporters[name].transporter_targets_mem
            targ_cell = self.transporters[name].transporter_targets_cell
            targ_env = self.transporters[name].transporter_targets_env
            self.transporters[name].flux = sim.rho_pump * eval(self.transporters[name].transporter_eval_string, globalo, localo)
            self._observe_transporter('flux', name, None, None, sim)
            self.extra_J_mem += self.transporters[name].net_z * self.transporters[name].flux * p.F
            self._observe_transporter('current', name, None, None, sim)
            for i, (delc, coeff) in enumerate(zip(self.transporters[name].delta_react_eval_strings, self.transporters[name].reactants_coeff)):
                delta_react = coeff * eval(delc, globalo, localo)
                if self.transporters[name].react_transport_tag[i] == 'mem_concs':
                    self.cell_concs[self.transporters[name].reactants_list[i]][targ_cell] = self.cell_concs[self.transporters[name].reactants_list[i]][targ_cell] + delta_react[targ_cell] * p.dt
                    self.mem_concs[self.transporters[name].reactants_list[i]][targ_mem] = self.mem_concs[self.transporters[name].reactants_list[i]][targ_mem] - self.transporters[name].flux[targ_mem] * (cells.mem_sa[targ_mem] / cells.mem_vol[targ_mem]) * p.dt
                elif self.transporters[name].react_transport_tag[i] == 'env_concs':
                    if p.is_ecm is True:
                        self.env_concs[self.transporters[name].reactants_list[i]][targ_env] = self.env_concs[self.transporters[name].reactants_list[i]][targ_env] + delta_react[targ_env] * p.dt
                    else:
                        self.env_concs[self.transporters[name].reactants_list[i]][targ_mem] = self.env_concs[self.transporters[name].reactants_list[i]][targ_mem] + delta_react[targ_cell][cells.mem_to_cells] * p.dt
                elif self.transporters[name].react_transport_tag[i] == 'cell_concs':
                    self.cell_concs[self.transporters[name].reactants_list[i]][targ_cell] = self.cell_concs[self.transporters[name].reactants_list[i]][targ_cell] + delta_react[targ_cell] * p.dt
                elif self.transporters[name].react_transport_tag[i] == 'mit_concs':
                    self.mit_concs[self.transporters[name].reactants_list[i]][targ_cell] = self.mit_concs[self.transporters[name].reactants_list[i]][targ_cell] + delta_react[targ_cell] * p.dt
                else:
                    raise BetseSimConfException('Internal error: transporter zone not specified correctly!')
                self._observe_transporter('reactant_commit', name, i, delta_react, sim)
            for i, (delc, coeff) in enumerate(zip(self.transporters[name].delta_prod_eval_strings, self.transporters[name].products_coeff)):
                delta_prod = coeff * eval(delc, globalo, localo)
                if self.transporters[name].prod_transport_tag[i] == 'mem_concs':
                    self.cell_concs[self.transporters[name].products_list[i]][targ_cell] = self.cell_concs[self.transporters[name].products_list[i]][targ_cell] + delta_prod[targ_cell] * p.dt
                    self.mem_concs[self.transporters[name].products_list[i]][targ_mem] = self.mem_concs[self.transporters[name].products_list[i]][targ_mem] + self.transporters[name].flux[targ_mem] * (cells.mem_sa[targ_mem] / cells.mem_vol[targ_mem]) * p.dt
                elif self.transporters[name].prod_transport_tag[i] == 'env_concs':
                    if p.is_ecm is True:
                        self.env_concs[self.transporters[name].products_list[i]][targ_env] = self.env_concs[self.transporters[name].products_list[i]][targ_env] + delta_prod[targ_env] * p.dt
                    else:
                        self.env_concs[self.transporters[name].products_list[i]][targ_mem] = self.env_concs[self.transporters[name].products_list[i]][targ_mem] + delta_prod[targ_cell][cells.mem_to_cells] * p.dt
                elif self.transporters[name].prod_transport_tag[i] == 'cell_concs':
                    self.cell_concs[self.transporters[name].products_list[i]][targ_cell] = self.cell_concs[self.transporters[name].products_list[i]][targ_cell] + delta_prod[targ_cell] * p.dt
                elif self.transporters[name].prod_transport_tag[i] == 'mit_concs':
                    self.mit_concs[self.transporters[name].products_list[i]][targ_cell] = self.mit_concs[self.transporters[name].products_list[i]][targ_cell] + delta_prod[targ_cell] * p.dt
                else:
                    raise BetseSimConfException('Internal error: transporter zone not specified correctly!')
                self._observe_transporter('product_commit', name, i, delta_prod, sim)
            self._observe_transporter('after', name, None, None, sim)

    def clear_cache(self):
        """
    Initializes or clears the time-storage vectors at the beginning of init and sim runs.

    """
        for name in self.molecules:
            obj = self.molecules[name]
            obj.c_mems_time = []
            obj.c_cells_time = []
            obj.c_env_time = []
            if self.mit_enabled:
                obj.c_mit_time = []
        for name in self.transporters:
            obj = self.transporters[name]
            obj.flux_time = []
        for name in self.channels:
            obj = self.channels[name]
            obj.D_time = []
            obj.flux_time = []
        for name in self.reactions:
            obj = self.reactions[name]
            obj.rate_time = []
        if self.mit_enabled:
            self.vmit_time = []
        self.chi_time = []

def transporter_fields(net):
    return {} if net is None else {name: qualified.public(obj) for name, obj in net.transporters.items()}

def wire(owner, sim):
    core = getattr(owner, 'core', None) if owner is not None else None
    aliases = {'cell_concs', 'mem_concs', 'env_concs', 'bound_concs', 'mit_concs'}
    objects = {'molecules', 'reactions', 'reactions_env', 'reactions_mit', 'modulators', 'channels', 'mit', 'molecule_frames', 'mover_frames', 'rhs', 'transporters', 'transporter_frames'}
    return dict(owner_fields={} if owner is None else qualified.public(owner, {'core'}), core_fields={} if core is None else qualified.public(core, aliases | objects), molecule_fields={} if core is None else {k: qualified.public(v) for k, v in core.molecules.items()}, reaction_fields={} if core is None else {k: qualified.public(v) for k, v in core.reactions.items()}, modulator_fields={} if core is None else {k: qualified.public(v) for k, v in core.modulators.items()}, channel_fields={} if core is None else channel_fields(core), transporter_fields=transporter_fields(core), ion_boundary_state=clone(sim.c_env_bound), simulator_fields={k: clone(getattr(sim, k)) for k in ('extra_rho_cells', 'extra_rho_env', 'extra_J_mem', 'extra_Jenv_x', 'extra_Jenv_y') if hasattr(sim, k)})

def validate_cached_transporters(ctx, incoming):
    config = ctx.definition['configuration'].get('transporters')
    expected = [r['name'] for r in config or []]
    fields = incoming['wire']['transporter_fields']
    initial = incoming['initial_transporter_fields']
    if list(fields) != expected or list(initial) != expected:
        raise ValueError('Require every ordered general-owner transporter and initial metadata')
    if incoming['wire']['owner_fields'].get('transporters') is not (config is not None):
        raise ValueError('Changed native general-owner transporter dispatch flag')
    for name in expected:
        current, origin = (fields[name], initial[name])
        if set(current) != set(origin) or 'flux' not in current or origin['flux'] is not None:
            raise ValueError('Require complete original transporter fields and literal cold flux None')
        for key in origin.keys() - {'flux'}:
            if not qualified.equal_tree(current[key], origin[key]):
                raise ValueError('Changed source-generated transporter equations or targeting metadata')
        flux = current['flux']
        if flux is not None:
            a = np.asarray(flux)
            if a.shape != (len(ctx.cells.mem_i),) or a.dtype != np.float64 or (not np.isfinite(a).all()):
                raise ValueError('Require a complete finite signed transporter flux cache')

def transporter_before(ctx, material_declaration):
    sim, cells, p, net = (ctx.sim, ctx.cells, ctx.p, ctx.net)
    return dict(mode='transporters', conditioned_before_model_transporters=True, definition=dict(transporters=clone(p.network_config.get('transporters')), biomolecules=clone(p.network_config['biomolecules'])), material_declaration=clone(material_declaration), ion_ids=list(ctx.ion_ids), valence=clone(sim.zs), values_before=material_values(sim), concentrations_before={zone: {name: clone(mapping[name]) for name in mapping} for zone, mapping in ((a, getattr(net, a)) for a in ('cell_concs', 'mem_concs', 'env_concs'))}, fluxes_before={name: clone(obj.flux) for name, obj in net.transporters.items()}, metadata={name: qualified.public(obj) for name, obj in net.transporters.items()}, geometry=dict(owner=clone(cells.mem_to_cells), membrane_area_m2=clone(cells.mem_sa), cell_volume_m3=clone(cells.cell_vol), membrane_volume_m3=clone(cells.mem_vol)), rho_pump=clone(np.broadcast_to(sim.rho_pump, (sim.mdl,))), runtime_temperature_K=sim.T, F=p.F, R=p.R, dt_s=p.dt, extra_current_before_A_m2=clone(net.extra_J_mem), cache_before=cache_general(ctx), source_completed=False, independently_carried_trajectory=False)

def attach_transporters(ctx):
    net = ctx.net

    def observe(stage, name, term, delta, actual):
        ctx.trace.setdefault('transporter_frames', []).append(dict(stage=stage, name=name, term=term, delta=clone(delta), concentrations={zone: {s: clone(values[s]) for s in values} for zone, values in ((a, getattr(net, a)) for a in ('cell_concs', 'mem_concs', 'env_concs'))}, fluxes={n: clone(o.flux) for n, o in net.transporters.items()}, extra_current_A_m2=clone(net.extra_J_mem), values=material_values(actual), cache=cache_general(ctx)))
    net._observe_transporter = observe

def clear_cache(self):
    """
    Initializes or clears the time-storage vectors at the beginning of init and sim runs.

    """
    for name in self.molecules:
        obj = self.molecules[name]
        obj.c_mems_time = []
        obj.c_cells_time = []
        obj.c_env_time = []
        if self.mit_enabled:
            obj.c_mit_time = []
    for name in self.transporters:
        obj = self.transporters[name]
        obj.flux_time = []
    for name in self.channels:
        obj = self.channels[name]
        obj.D_time = []
        obj.flux_time = []
    for name in self.reactions:
        obj = self.reactions[name]
        obj.rate_time = []
    if self.mit_enabled:
        self.vmit_time = []
    self.chi_time = []

def clear_storage(self, cells, p):
    """
    Re-initializes time storage vectors at the begining of a sim or init.
    """
    self.fluxes_mem = np.zeros(self.fluxes_mem.shape)
    self.fluxes_gj = np.zeros(self.fluxes_gj.shape)
    self.Ax_time = []
    self.Ay_time = []
    self.Bz_time = []
    self.cc_time = []
    self.cc_env_time = []
    self.dd_time = []
    self.vm_time = []
    self.vm_ave_time = []
    self.vm_GHK_time = []
    self.time = []
    self.gjopen_time = []
    self.osmo_P_delta_time = []
    self.I_mem_time = []
    self.I_cell_x_time = []
    self.I_cell_y_time = []
    self.I_tot_x_time = []
    self.I_tot_y_time = []
    self.efield_gj_x_time = []
    self.efield_gj_y_time = []
    self.P_cells_time = []
    self.u_cells_x_time = []
    self.u_cells_y_time = []
    self.rho_cells_time = []
    self.F_electro_x_time = []
    self.F_electro_y_time = []
    self.F_hydro_x_time = []
    self.F_hydro_y_time = []
    self.P_electro_time = []
    self.rate_NaKATP_time = []
    self.vm_ave_time = []
    self.venv_time = []
    if p.deformation:
        self.ecm_verts_unique_to = cells.ecm_verts_unique[:]
        self.cell_centres_time = []
        self.mem_mids_time = []
        self.maskM_time = []
        self.mem_edges_time = []
        self.cell_verts_time = []
        self.dx_cell_time = []
        self.dy_cell_time = []
        self.dx_time = []
        self.dy_time = []
        self.phi = np.zeros(self.mdl)
        self.phi_time = []
    if p.molecules_enabled:
        self.molecules.core.clear_cache()
    if p.grn_enabled:
        clear_cache(self.grn.core)
    if p.Ca_dyn:
        self.endo_retic.clear_cache()
    if p.is_ecm:
        self.charge_env_time = []
        self.efield_ecm_x_time = []
        self.efield_ecm_y_time = []
        self.u_env_x_time = []
        self.u_env_y_time = []
        self.rho_pump_time = []
        self.rho_channel_time = []
gaussian_filter = environment.gaussian_filter
EndoRetic = None

def init_profiles(self, phase):
    """
    Finalize the initialization of all events and tissue and cut profiles
    for the passed simulation phase.

    Specifically, this method:

    * Defines all dictionaries mapping from tissue profile names to
      one-dimensional arrays of the indices of various cellular objects
      (e.g., cells, cell membranes) in the cluster belonging to these
      tissues. This includes the :attr:`cell_target_inds`,
      :attr:`env_target_inds`, and :attr:`tissue_target_inds` dictionaries.

    Parameters
    ----------
    phase : SimPhase
        Current simulation phase.
    """
    logs.log_debug('Mapping tissue, surgery, and boundary profiles...')
    cells = phase.cells
    p = phase.p
    sim = phase.sim
    self.cell_target_inds = {}
    self.env_target_inds = {}
    self.tissue_target_inds = {}
    for tissue_name, tissue_profile in self.tissue_name_to_profile.items():
        tissue_cells_index, tissue_mems_index = tissue_profile.picker.pick_cells_and_mems(cells=cells, p=p)
        self.cell_target_inds[tissue_name] = tissue_cells_index
        self.tissue_target_inds[tissue_name] = tissue_mems_index
        if len(self.cell_target_inds[tissue_name]):
            if p.is_ecm:
                ecm_targs_mem = list(cells.map_mem2ecm[tissue_mems_index])
                self.env_target_inds[tissue_name] = ecm_targs_mem
            if p.ions_dict['Na'] == 1:
                sim.Dm_cells[sim.iNa][tissue_mems_index] = tissue_profile.Dm_Na
            if p.ions_dict['K'] == 1:
                sim.Dm_cells[sim.iK][tissue_mems_index] = tissue_profile.Dm_K
            if p.ions_dict['Cl'] == 1:
                sim.Dm_cells[sim.iCl][tissue_mems_index] = tissue_profile.Dm_Cl
            if p.ions_dict['Ca'] == 1:
                sim.Dm_cells[sim.iCa][tissue_mems_index] = tissue_profile.Dm_Ca
            if p.ions_dict['M'] == 1:
                sim.Dm_cells[sim.iM][tissue_mems_index] = tissue_profile.Dm_M
            if p.ions_dict['P'] == 1:
                sim.Dm_cells[sim.iP][tissue_mems_index] = tissue_profile.Dm_P

def initDenv(self, cells, p):
    """
    Initialize the environmental diffusion matrix and corresponding weight
    matrices, including tight and adherin junctions.
    """
    if p.is_ecm:
        for i, _ in enumerate(self.D_env):
            Denv_o = np.ones(self.edl) * self.D_free[i]
            Denv_o[cells.envInds_inClust] = self.D_free[i] * p.D_adh
            Denv_o[cells.all_bound_mem_inds] = self.D_free[i] * p.D_tj * self.Dtj_rel[i]
            Denv_o[cells.interior_bound_mem_inds] = self.D_free[i] * p.D_tj * self.Dtj_rel[i]
            Denv_o[cells.ecm_inds_bound_cell] = self.D_free[i] * p.D_tj * self.Dtj_rel[i]
            self.D_env[i] = Denv_o * 1.0
        D_env_weight = self.D_env[self.iNa] / self.D_env[self.iNa].max()
        self.D_env_weight = D_env_weight.reshape(cells.X.shape)
        self.D_env_weight_base = np.copy(self.D_env_weight)
        self.TJ_modulator = np.ones(self.D_env.shape)
    else:
        Denv_o = np.ones(len(cells.xypts))
        Denv_o[cells.all_bound_mem_inds] = p.D_tj
        Denv_o[cells.interior_bound_mem_inds] = p.D_tj
        Denv_o[cells.ecm_inds_bound_cell] = p.D_tj
        Denv_o = gaussian_filter(Denv_o.reshape(cells.X.shape), 1.0)
        self.D_env = np.copy(self.D_free)
        self.D_env_weight = Denv_o.reshape(cells.X.shape)
        self.D_env_weight_base = np.copy(self.D_env_weight)
    self.TJ_targets = np.hstack((cells.all_bound_mem_inds, cells.interior_bound_mem_inds, cells.ecm_inds_bound_cell))
    self.Chi = np.ones(len(cells.xypts)) * p.er
    self.Chi = gaussian_filter(self.Chi.reshape(cells.X.shape), 2)

def _finalize_events_global(self, phase, *, shuffle):
    """
    Initialize all **global scheduled interventions** (i.e., events
    globally applicable to all cells) for the passed simulation phase.

    Parameters
    ----------
    phase : SimPhase
        Current simulation phase.
    """
    cells = phase.cells
    p = phase.p
    if p.global_options['K_env'] != 0:
        self.t_on_Kenv = p.global_options['K_env'][0]
        self.t_off_Kenv = p.global_options['K_env'][1]
        self.t_change_Kenv = p.global_options['K_env'][2]
        self.mem_mult_Kenv = p.global_options['K_env'][3]
    if p.global_options['Cl_env'] != 0:
        self.t_on_Clenv = p.global_options['Cl_env'][0]
        self.t_off_Clenv = p.global_options['Cl_env'][1]
        self.t_change_Clenv = p.global_options['Cl_env'][2]
        self.mem_mult_Clenv = p.global_options['Cl_env'][3]
    if p.global_options['Na_env'] != 0:
        self.t_on_Naenv = p.global_options['Na_env'][0]
        self.t_off_Naenv = p.global_options['Na_env'][1]
        self.t_change_Naenv = p.global_options['Na_env'][2]
        self.mem_mult_Naenv = p.global_options['Na_env'][3]
    if p.global_options['T_change'] != 0:
        self.tonT = p.global_options['T_change'][0]
        self.toffT = p.global_options['T_change'][1]
        self.trampT = p.global_options['T_change'][2]
        self.multT = p.global_options['T_change'][3]
    if p.global_options['gj_block'] != 0:
        self.tonGJ = p.global_options['gj_block'][0]
        self.toffGJ = p.global_options['gj_block'][1]
        self.trampGJ = p.global_options['gj_block'][2]
        numo = int(p.global_options['gj_block'][3])
        if numo > 100:
            numo = 100
        elif numo < 1:
            numo = 1
        data_length = len(cells.mem_i)
        data_fraction = int(numo / 100 * data_length)
        mem_i_copy = np.copy(cells.mem_i[:])
        shuffle(mem_i_copy)
        self.targets_gj_block = [cells.mem_i[x] for x in range(0, data_fraction)]
    if p.global_options['NaKATP_block'] != 0:
        self.tonNK = p.global_options['NaKATP_block'][0]
        self.toffNK = p.global_options['NaKATP_block'][1]
        self.trampNK = p.global_options['NaKATP_block'][2]

def _finalize_events_tissue(self, phase):
    """
    Initialize all **targeted scheduled interventions** (i.e., events only
    applicable to specific tissue profiles) for the passed simulation
    phase.

    Parameters
    ----------
    phase : SimPhase
        Current simulation phase.
    """
    cells = phase.cells
    p = phase.p
    if p.scheduled_options['Na_mem'] != 0:
        self.t_on_Namem = p.scheduled_options['Na_mem'][0]
        self.t_off_Namem = p.scheduled_options['Na_mem'][1]
        self.t_change_Namem = p.scheduled_options['Na_mem'][2]
        self.mem_mult_Namem = p.scheduled_options['Na_mem'][3]
        self.apply_Namem = p.scheduled_options['Na_mem'][4]
        self.function_Namem = p.scheduled_options['Na_mem'][5]
        self.targets_Namem = []
        for profile in self.apply_Namem:
            targets = self.tissue_target_inds[profile]
            self.targets_Namem.append(targets)
        self.targets_Namem = [item for sublist in self.targets_Namem for item in sublist]
        self.scalar_Namem = 1
        self.dyna_Namem = lambda t: 1
        if self.function_Namem != 'None':
            self.scalar_Namem, self.dyna_Namem = getattr(mod, self.function_Namem)(self.targets_Namem, cells, p)
    if p.scheduled_options['K_mem'] != 0:
        self.t_on_Kmem = p.scheduled_options['K_mem'][0]
        self.t_off_Kmem = p.scheduled_options['K_mem'][1]
        self.t_change_Kmem = p.scheduled_options['K_mem'][2]
        self.mem_mult_Kmem = p.scheduled_options['K_mem'][3]
        self.apply_Kmem = p.scheduled_options['K_mem'][4]
        self.function_Kmem = p.scheduled_options['K_mem'][5]
        self.targets_Kmem = []
        for profile in self.apply_Kmem:
            targets = self.tissue_target_inds[profile]
            self.targets_Kmem.append(targets)
        self.targets_Kmem = [item for sublist in self.targets_Kmem for item in sublist]
        self.scalar_Kmem = 1
        self.dyna_Kmem = lambda t: 1
        if self.function_Kmem != 'None':
            self.scalar_Kmem, self.dyna_Kmem = getattr(mod, self.function_Kmem)(self.targets_Kmem, cells, p)
    if p.scheduled_options['Cl_mem'] != 0:
        self.t_on_Clmem = p.scheduled_options['Cl_mem'][0]
        self.t_off_Clmem = p.scheduled_options['Cl_mem'][1]
        self.t_change_Clmem = p.scheduled_options['Cl_mem'][2]
        self.mem_mult_Clmem = p.scheduled_options['Cl_mem'][3]
        self.apply_Clmem = p.scheduled_options['Cl_mem'][4]
        self.function_Clmem = p.scheduled_options['Cl_mem'][5]
        self.targets_Clmem = []
        for profile in self.apply_Clmem:
            targets = self.tissue_target_inds[profile]
            self.targets_Clmem.append(targets)
        self.targets_Clmem = [item for sublist in self.targets_Clmem for item in sublist]
        self.scalar_Clmem = 1
        self.dyna_Clmem = lambda t: 1
        if self.function_Clmem != 'None':
            self.scalar_Clmem, self.dyna_Clmem = getattr(mod, self.function_Clmem)(self.targets_Clmem, cells, p)
    if p.scheduled_options['Ca_mem'] != 0:
        self.t_on_Camem = p.scheduled_options['Ca_mem'][0]
        self.t_off_Camem = p.scheduled_options['Ca_mem'][1]
        self.t_change_Camem = p.scheduled_options['Ca_mem'][2]
        self.mem_mult_Camem = p.scheduled_options['Ca_mem'][3]
        self.apply_Camem = p.scheduled_options['Ca_mem'][4]
        self.function_Camem = p.scheduled_options['Ca_mem'][5]
        self.targets_Camem = []
        for profile in self.apply_Camem:
            targets = self.tissue_target_inds[profile]
            self.targets_Camem.append(targets)
        self.targets_Camem = [item for sublist in self.targets_Camem for item in sublist]
        self.scalar_Camem = 1
        self.dyna_Camem = lambda t: 1
        if self.function_Camem != 'None':
            self.scalar_Camem, self.dyna_Camem = getattr(mod, self.function_Camem)(self.targets_Camem, cells, p)
    if p.scheduled_options['pressure'] != 0:
        self.t_onP = p.scheduled_options['pressure'][0]
        self.t_offP = p.scheduled_options['pressure'][1]
        self.t_changeP = p.scheduled_options['pressure'][2]
        self.rate_P = p.scheduled_options['pressure'][3]
        self.apply_P = p.scheduled_options['pressure'][4]
        self.function_P = p.scheduled_options['pressure'][5]
        self.targets_P = []
        for profile in self.apply_P:
            targets = self.cell_target_inds[profile]
            self.targets_P.append(targets)
        self.targets_P = [item for sublist in self.targets_P for item in sublist]
        self.scalar_P = 1
        self.dyna_P = lambda t: 1
        if self.function_P != 'None':
            self.scalar_P, self.dyna_P = getattr(mod, self.function_P)(self.targets_P, cells, p)
    if p.scheduled_options['ecmJ'] != 0 and p.is_ecm:
        self.t_on_ecmJ = p.scheduled_options['ecmJ'][0]
        self.t_off_ecmJ = p.scheduled_options['ecmJ'][1]
        self.t_change_ecmJ = p.scheduled_options['ecmJ'][2]
        self.apply_ecmJ = p.scheduled_options['ecmJ'][3]
        self.mult_ecmJ = p.scheduled_options['ecmJ'][4]
        self.targets_ecmJ = []
        for profile in self.apply_ecmJ:
            targets = self.env_target_inds[profile]
            self.targets_ecmJ.append(targets)
        self.targets_ecmJ = [item for sublist in self.targets_ecmJ for item in sublist]

def f_sweep(pc, cells, p):
    """
    Create and return a time-dependent sweep of a sinusoidal function through
    various frequencies.

    Parameters
    ----------
    pc                 Indices of cells (p.is_ecm == False) or membranes (p.is_ecm == True)
    cells              Instance of Cells module
    p                  Instance of parameters

    Returns
    ---------
    y              Data values from 0 to 1 defining a periodic signal.
    scalar         Null output corresponding to spatial variation.
    """
    scalar = 1
    if p.f_scan_properties['f slope'] is None and p._run_sim:
        p.f_scan_properties['f slope'] = (p.f_scan_properties['f stop'] - p.f_scan_properties['f start']) / p.sim_time_total
    f_slope = p.f_scan_properties['f slope']
    y = lambda t: np.sin(np.pi * (f_slope * t + p.f_scan_properties['f start']) * t) ** 2
    return (scalar, y)

def static_and_blocks(self, cells, p, rng):
    Dm_cellsA = np.asarray(self.Dm_cells)
    self.Dm_base = np.copy(Dm_cellsA)
    self.Dm_scheduled = np.copy(Dm_cellsA)
    self.Dm_scheduled[:] = 0
    self.P_mod = np.copy(self.P_cells[:])
    self.P_base = np.copy(self.P_cells[:])
    self.div_u_osmo = np.zeros(self.cdl)
    self.channel_noise_factor = rng.random(self.mdl)
    self.Dm_cells[self.iK] = (p.channel_noise_level * self.channel_noise_factor + 1) * self.Dm_cells[self.iK]
    if p.global_options['gj_block'] != 0:
        self.gj_block = np.ones(len(cells.mem_i))
    else:
        self.gj_block = 1
    if p.global_options['NaKATP_block'] != 0:
        self.NaKATP_block = np.ones(self.mdl)
    else:
        self.NaKATP_block = 1
    self.CaATP_block = np.ones(self.mdl)
    if p.ions_dict['Ca'] == 1 and p.Ca_dyn:
        self.endo_retic = EndoRetic(self, cells, p)
    else:
        self.endo_retic = None

def screening_conductivity(self, cells, p):
    self.ko_env = np.sqrt(np.dot(p.NAv * p.q ** 2 * self.zs ** 2 / (p.er * p.eo * p.kb * p.T), self.cc_env)).mean()
    self.ko_cell = np.sqrt(np.dot(p.NAv * p.q ** 2 * self.zs ** 2 / (p.er * p.eo * p.kb * p.T), self.cc_cells)).mean()
    self.cedl_env = p.er * p.eo * self.ko_env
    self.cedl_cell = p.er * p.eo * self.ko_cell
    self.cedl = p.er * p.eo * self.ko_env
    self.sigma = np.asarray([z ** 2 * p.q * p.F * cc * D / (p.kb * p.T) for z, cc, D in zip(self.zs, self.cc_cells, self.D_free)]).sum(axis=0).mean()
    self.sigma_cell = np.asarray([z ** 2 * p.q * p.F * cc * D * 0.1 / (p.kb * p.T) for z, cc, D in zip(self.zs, self.cc_cells, self.D_free)]).sum(axis=0)
    self.sigma_env = np.asarray([z ** 2 * p.q * p.F * cc * D / (p.kb * p.T) for z, cc, D in zip(self.zs, self.cc_env, self.D_env)]).sum(axis=0)
    if p.is_ecm:
        self.sigma_env = gaussian_filter(self.sigma_env.reshape(cells.X.shape), 1).ravel()
    self.rho_factor = cells.mem_sa / cells.R_rads
    self.cgj = 1 / (2 / p.cm)
mod = SimpleNamespace(f_sweep=f_sweep)
