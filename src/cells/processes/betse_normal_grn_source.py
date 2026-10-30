# ruff: noqa: B007, B905, E501
"""Genuine configured MasterOfGenes initialization and normal GRN dispatch.

Scientific bodies are literal; neutral all-target no-ECM scope is explicit.
Hot state hydration preserves every public owner/core/molecule field.
"""

import copy
from collections import OrderedDict
from collections.abc import Mapping, MutableMapping
from types import SimpleNamespace

import numpy as np

from cells.processes import betse_normal_ion_join as ions
from cells.processes import betse_normal_molecule_source as molecule_source
from cells.processes import betse_normal_network_join_source as feedback_source

logs = SimpleNamespace(log_info=lambda *_: None, log_warning=lambda *_: None)
tex_val = str
types = SimpleNamespace(trim=repr)
MappingMutableType = MutableMapping
BetseMethodUnimplementedException = NotImplementedError
BetseSimConfException = ValueError
controls = molecule_source.controls
stb = molecule_source.stb


def _outside_scope(*args, **kwargs):
    raise ValueError("Separate mitochondria, asymmetry, optimizer or profile state is required")


Mito = _outside_scope
mods = SimpleNamespace()


class Molecule(molecule_source._Molecule):
    pass


class DynamicValue(object):
    __slots__ = ("get_value", "set_value")

    def __init__(self, get_value, set_value):
        self.get_value = get_value
        self.set_value = set_value


class DynamicValueDict(MappingMutableType):
    def __init__(self, key_to_dynamic_value):
        if __debug__:
            for dynamic_value in key_to_dynamic_value.values():
                assert isinstance(dynamic_value, DynamicValue), '"{}" not a dynamic value.'.format(
                    types.trim(dynamic_value)
                )
        self._key_to_dynamic_value = key_to_dynamic_value

    def __getitem__(self, key):
        return self._key_to_dynamic_value[key].get_value()

    def __setitem__(self, key, value):
        self._key_to_dynamic_value[key].set_value(value)

    def __delitem__(self, key):
        raise BetseMethodUnimplementedException()

    def __len__(self):
        return len(self._key_to_dynamic_value)

    def __iter__(self):
        return iter(self._key_to_dynamic_value)


def set_net_opts(self, net_plot_opts, p):
    if net_plot_opts is not None:
        self.plot_net = net_plot_opts["plot network"]
        self.net_font_name = net_plot_opts["font name"]
        self.node_font_size = net_plot_opts["node font size"]
        self.tit_font_size = net_plot_opts["sub-net font size"]
        self.net_layout = net_plot_opts["layout"]
        self.edge_width = net_plot_opts["edge linewidth"]
        self.conc_node_font_color = net_plot_opts["substances"]["font color"]
        self.conc_node_color = net_plot_opts["substances"]["node color"]
        self.conc_shape = net_plot_opts["substances"]["node shape"]
        self.react_node_font_color = net_plot_opts["reactions"]["font color"]
        self.react_node_color = net_plot_opts["reactions"]["node color"]
        self.reaction_shape = net_plot_opts["reactions"]["node shape"]
        self.transp_node_font_color = net_plot_opts["transporters"]["font color"]
        self.transp_node_color = net_plot_opts["transporters"]["node color"]
        self.transporter_shape = net_plot_opts["transporters"]["node shape"]
        self.chan_node_font_color = net_plot_opts["channels"]["font color"]
        self.chan_node_color = net_plot_opts["channels"]["node color"]
        self.channel_shape = net_plot_opts["channels"]["node shape"]
        self.ed_node_font_color = net_plot_opts["electrodiffusion"]["font color"]
        self.ed_node_color = net_plot_opts["electrodiffusion"]["node color"]
        self.ed_shape = net_plot_opts["electrodiffusion"]["node shape"]
        self.vmem_node_font_color = net_plot_opts["Vmem"]["font color"]
        self.vmem_node_color = net_plot_opts["Vmem"]["node color"]
        self.vmem_shape = net_plot_opts["Vmem"]["node shape"]
        self.subnets_dicts = net_plot_opts["sub-nets"]
        self.additional_edges = net_plot_opts.get("additional relationships", None)
    else:
        self.plot_net = p.plot_network
        self.net_font_name = "DejaVu Sans"
        self.node_font_size = 16
        self.tit_font_size = 24
        self.net_layout = "TB"
        self.edge_width = 2.0
        self.conc_node_font_color = "Black"
        self.conc_node_color = "LightCyan"
        self.conc_shape = "ellipse"
        self.react_node_font_color = "White"
        self.react_node_color = "DarkSeaGreen"
        self.reaction_shape = "rect"
        self.transp_node_font_color = "White"
        self.transp_node_color = "DarkSeaGreen"
        self.transporter_shape = "diamond"
        self.chan_node_font_color = "White"
        self.chan_node_color = "DarkSeaGreen"
        self.channel_shape = "pentagon"
        self.ed_node_font_color = "White"
        self.ed_node_color = "DarkSeaGreen"
        self.ed_shape = "hexagon"
        self.vmem_node_font_color = "White"
        self.vmem_node_color = "maroon"
        self.vmem_shape = "oval"
        self.subnets_dicts = None
        self.additional_edges = None


class MasterOfNetworks(molecule_source._Network):
    def __init__(self, sim, cells, config_substances, p, mit_enabled=False):
        self.molecules = OrderedDict({})
        self.reactions = OrderedDict({})
        self.reactions_env = OrderedDict({})
        self.transporters = OrderedDict({})
        self.channels = OrderedDict({})
        self.modulators = OrderedDict({})
        self.reactions_mit = OrderedDict({})
        self.reaction_rates = None
        self.charge_has_been_balanced = False
        self.mit_enabled = mit_enabled
        self.ave_cell_vol = cells.cell_vol.mean()
        self.plot_cmap = "viridis"
        self.reaction_shape = "rect"
        self.transporter_shape = "diamond"
        self.channel_shape = "pentagon"
        self.vmem_shape = "ellipse"
        self.ed_shape = "hexagon"
        self.conc_shape = "oval"
        self.extra_J_mem = np.zeros(sim.mdl)
        self.extra_Jenv_x = np.zeros(sim.edl)
        self.extra_Jenv_y = np.zeros(sim.edl)

    def read_substances(self, sim, cells, config_substances, p):
        logs.log_info("Reading additional substance data...")
        cell_concs_mapping = OrderedDict({})
        mem_concs_mapping = OrderedDict({})
        env_concs_mapping = OrderedDict({})
        bound_concs_mapping = OrderedDict({})
        self.zmol = OrderedDict({})
        self.Dmem = OrderedDict({})
        self.ED_eval_strings = OrderedDict({})
        if self.mit_enabled:
            self.mit = Mito(sim, cells, p)
            mit_concs_mapping = {}
        else:
            self.mit = None
            mit_concs_mapping = None
        for k, val in p.ions_dict.items():
            if val == 1:
                ion_index = sim.get_ion(k)
                cell_concs_mapping[k] = DynamicValue(
                    lambda ion_index=ion_index: sim.cc_cells[ion_index],
                    lambda value, ion_index=ion_index: sim.cc_cells.__setitem__(ion_index, value),
                )
                mem_concs_mapping[k] = DynamicValue(
                    lambda ion_index=ion_index: sim.cc_at_mem[ion_index],
                    lambda value, ion_index=ion_index: sim.cc_at_mem.__setitem__(ion_index, value),
                )
                env_concs_mapping[k] = DynamicValue(
                    lambda ion_index=ion_index: sim.cc_env[ion_index],
                    lambda value, ion_index=ion_index: sim.cc_env.__setitem__(ion_index, value),
                )
                bound_concs_mapping[k] = DynamicValue(
                    lambda ion_index=ion_index: sim.c_env_bound[ion_index],
                    lambda value, ion_index=ion_index: sim.c_env_bound.__setitem__(
                        ion_index, value
                    ),
                )
                self.zmol[k] = sim.zs[ion_index]
                self.Dmem[k] = sim.Dm_cells[ion_index].mean()
                if self.mit_enabled:
                    mit_concs_mapping[k] = DynamicValue(
                        lambda ion_index=ion_index: sim.cc_mit[ion_index],
                        lambda value, ion_index=ion_index: sim.cc_mit.__setitem__(ion_index, value),
                    )
        if config_substances is not None:
            for q, mol_dic in enumerate(config_substances):
                name = str(mol_dic["name"])
                self.molecules[name] = Molecule(sim, cells, p)
                mol = self.molecules[name]
                mol.name = name
                mol.c_envo = mol_dic["env conc"]
                mol.c_cello = mol_dic["cell conc"]
                mol.c_mito = mol_dic.get("mit conc", None)
                mol.use_time_dilation = mol_dic.get("use time dilation", False)
                if mol.use_time_dilation:
                    mol.modify_time_factor = self.time_dila
                else:
                    mol.modify_time_factor = 1.0
                init_asym = mol_dic.get("initial asymmetry", None)
                if init_asym != "None" and init_asym is not None:
                    mol.init_asym, _ = getattr(mods, init_asym)(cells.cell_i, cells, p)
                else:
                    mol.init_asym = np.ones(sim.cdl)
                mol.c_cells = np.ones(sim.cdl) * mol.c_cello * mol.init_asym
                cell_concs_mapping[name] = DynamicValue(
                    lambda name=name: self.molecules[name].c_cells,
                    lambda value, name=name: setattr(self.molecules[name], "c_cells", value),
                )
                mol.cc_at_mem = mol.c_cells[cells.mem_to_cells]
                mem_concs_mapping[name] = DynamicValue(
                    lambda name=name: self.molecules[name].cc_at_mem,
                    lambda value, name=name: setattr(self.molecules[name], "cc_at_mem", value),
                )
                mol.flux_intra = np.zeros(sim.mdl)
                if self.mit_enabled:
                    if mol.c_mito is not None:
                        mol.c_mit = np.ones(sim.cdl) * mol.c_mito
                    elif mol.c_mito is None:
                        mol.c_mit = np.zeros(sim.cdl)
                    mit_concs_mapping[name] = DynamicValue(
                        lambda name=name: self.molecules[name].c_mit,
                        lambda value, name=name: setattr(self.molecules[name], "c_mit", value),
                    )
                if p.is_ecm is False:
                    mol.c_env = np.ones(sim.mdl) * mol.c_envo
                else:
                    mol.c_env = np.ones(sim.edl) * mol.c_envo
                env_concs_mapping[name] = DynamicValue(
                    lambda name=name: self.molecules[name].c_env,
                    lambda value, name=name: setattr(self.molecules[name], "c_env", value),
                )
                mol.c_bound = mol.c_envo
                bound_concs_mapping[name] = DynamicValue(
                    lambda name=name: self.molecules[name].c_bound,
                    lambda value, name=name: setattr(self.molecules[name], "c_bound", value),
                )
                if self.mit_enabled:
                    mol.mit_enabled = True
                else:
                    mol.mit_enabled = False
                mol.c_bound_mem = np.zeros(len(cells.bflags_mems))
        self.cell_concs = DynamicValueDict(cell_concs_mapping)
        self.mem_concs = DynamicValueDict(mem_concs_mapping)
        self.env_concs = DynamicValueDict(env_concs_mapping)
        self.bound_concs = DynamicValueDict(bound_concs_mapping)
        if self.mit_enabled:
            self.mit_concs = DynamicValueDict(mit_concs_mapping)
        else:
            self.mit_concs = None

    def tissue_init(self, phase, config_substances):
        logs.log_info("Initializing substances/reaction network...")
        cells = phase.cells
        p = phase.p
        sim = phase.sim
        if config_substances is not None:
            for q, mol_dic in enumerate(config_substances):
                name = str(mol_dic["name"])
                if name not in self.molecules:
                    logs.log_warning(
                        "WARNING: You've added a new substance, which was not in your initialization.It will be ignored. Please re-run an init to see all your substances in action."
                    )
                    continue
                mol = self.molecules[name]
                mol.name = name
                mol.Dm = float(mol_dic["Dm"])
                mol.Do = float(mol_dic["Do"])
                mol.Dgj = float(mol_dic.get("Dgj", 1e-16))
                mol.z = float(mol_dic["z"])
                mol.update_intra_conc = mol_dic.get("update intracellular", True)
                mol.u_mt = float(mol_dic.get("u_mtube", 0.0))
                mol.Mu_mem = float(mol_dic.get("Mu_mem", 0.0))
                mol.transmem = mol_dic.get("transmem", False)
                self.zmol[name] = mol.z
                self.Dmem[name] = mol.Dm
                mol.scale_factor = float(mol_dic.get("scale factor", 1.0))
                mol.ignore_ECM_pump = True
                mol.ignoreTJ = mol_dic["TJ permeable"]
                mol.ignoreGJ = mol_dic["GJ impermeable"]
                mol.TJ_factor = float(mol_dic["TJ factor"])
                gad = mol_dic.get("growth and decay", None)
                if gad != "None" and gad is not None:
                    mol.simple_growth = True
                    mol.r_production = gad["production rate"]
                    mol.r_decay = gad["decay rate"]
                    mol.gad_scale_factor = float(gad.get("scale factor", 1.0))
                    mol.growth_profiles_list = gad["apply to"]
                    modulator_function_name = gad.get("modulator function", None)
                    mol.growth_activators_list = gad.get("activators", None)
                    mol.growth_activators_zone = gad.get("zone activators", None)
                    mol.growth_activators_Km = gad.get("Km activators", None)
                    mol.growth_activators_n = gad.get("n activators", None)
                    mol.growth_inhibitors_list = gad.get("inhibitors", None)
                    mol.growth_inhibitors_zone = gad.get("zone inhibitors", None)
                    mol.growth_inhibitors_Km = gad.get("Km inhibitors", None)
                    mol.growth_inhibitors_n = gad.get("n inhibitors", None)
                    mol.growth_activators_zone, mol.growth_inhibitors_zone = self.default_zones(
                        mol.growth_activators_zone,
                        mol.growth_inhibitors_zone,
                        mol.growth_activators_list,
                        mol.growth_inhibitors_list,
                    )
                    mol.decay_max = gad.get("decay max", 0.0)
                    mol.decay_activators_list = gad.get("decay activators", None)
                    mol.decay_activators_zone = gad.get("zone decay activators", None)
                    mol.decay_activators_Km = gad.get("Km decay activators", None)
                    mol.decay_activators_n = gad.get("n decay activators", None)
                    mol.decay_inhibitors_list = gad.get("decay inhibitors", None)
                    mol.decay_inhibitors_zone = gad.get("zone decay inhibitors", None)
                    mol.decay_inhibitors_Km = gad.get("Km decay inhibitors", None)
                    mol.decay_inhibitors_n = gad.get("n decay inhibitors", None)
                    mol.decay_activators_zone, mol.decay_inhibitors_zone = self.default_zones(
                        mol.decay_activators_zone,
                        mol.decay_inhibitors_zone,
                        mol.decay_activators_list,
                        mol.decay_inhibitors_list,
                    )
                    mol.init_growth(phase)
                    if modulator_function_name != "None" and modulator_function_name is not None:
                        mol.growth_mod_function_cells, _ = getattr(mods, modulator_function_name)(
                            cells.cell_i, cells, p
                        )
                    else:
                        mol.growth_mod_function_cells = np.ones(sim.cdl)
                else:
                    mol.simple_growth = False
                    mol.growth_profiles_list = None
                    mol.gad_scale_factor = 1.0
                icg = mol_dic.get("ion channel gating", None)
                if icg is not None:
                    mol.ion_channel_gating = True
                    mol.gating_channel_name = icg.get("channel name", "Gated channel")
                    mol.gating_ion_name = icg["ion channel target"]
                    if mol.gating_ion_name != "None":
                        mol.use_gating_ligand = True
                        mol.gating_ion = []
                        for ion_o in mol.gating_ion_name:
                            mol.gating_ion.append(sim.get_ion(ion_o))
                    else:
                        mol.use_gating_ligand = False
                        mol.gating_ion = []
                    mol.gating_Hill_K = float(icg["target Hill coefficient"])
                    mol.gating_Hill_n = float(icg["target Hill exponent"])
                    mol.gating_max_val = float(icg["peak channel opening"])
                    mol.gating_extracell = icg["acts extracellularly"]
                    mol.ion_activators_list = icg.get("activators", None)
                    mol.ion_activators_Km = icg.get("Km activators", None)
                    mol.ion_activators_n = icg.get("n activators", None)
                    mol.ion_activators_zone = icg.get("zone activators", None)
                    mol.ion_inhibitors_list = icg.get("inhibitors", None)
                    mol.ion_inhibitors_Km = icg.get("Km inhibitors", None)
                    mol.ion_inhibitors_n = icg.get("n inhibitors", None)
                    mol.ion_inhibitors_zone = icg.get("zone inhibitors", None)
                    mol.ion_activators_zone, mol.ion_inhibitors_zone = self.default_zones(
                        mol.ion_activators_zone,
                        mol.ion_inhibitors_zone,
                        mol.ion_activators_list,
                        mol.ion_inhibitors_list,
                    )
                    tex_vars = []
                    alpha_ion, alpha_tex, tex_vars = self.get_influencers(
                        mol.ion_activators_list,
                        mol.ion_activators_Km,
                        mol.ion_activators_n,
                        mol.ion_inhibitors_list,
                        mol.ion_inhibitors_Km,
                        mol.ion_inhibitors_n,
                        reaction_zone="mem",
                        tex_list=tex_vars,
                        zone_tags_a=mol.ion_activators_zone,
                        zone_tags_i=mol.ion_inhibitors_zone,
                        in_mem_tag=True,
                    )
                    mol.gating_mod_eval_string = "(" + alpha_ion + ")"
                else:
                    mol.ion_channel_gating = False
                ap = mol_dic.get("active pumping", None)
                if ap is not None:
                    mol.active_pumping = True
                    mol.use_pumping = ap["turn on"]
                    mol.pump_to_cell = ap["pump to cell"]
                    mol.pump_max_val = ap["maximum rate"]
                    mol.pump_Km = ap["pump Km"]
                    mol.pumps_use_ATP = ap["uses ATP"]
                else:
                    mol.active_pumping = False
                cell_clamp = mol_dic.get("clamp cell conc", None)
                if cell_clamp is not None:
                    mol.cell_clamp = True
                    mol.cell_clamp_event = bool(cell_clamp["event happens"])
                    mol.cell_clamp_start = float(cell_clamp["change start"])
                    mol.cell_clamp_end = float(cell_clamp["change finish"])
                    mol.cell_clamp_rate = float(cell_clamp["change rate"])
                    mol.cell_clamp_target = float(cell_clamp["concentration"])
                else:
                    mol.cell_clamp = False
                    mol.cell_clamp_event = False
                    mol.cell_clamp_start = 99999
                    mol.cell_clamp_end = 9999999
                cab = mol_dic.get("change at bounds", None)
                if cab is not None:
                    mol.change_bounds = True
                    mol.change_at_bounds = cab["event happens"]
                    mol.change_bounds_start = cab["change start"]
                    mol.change_bounds_end = cab["change finish"]
                    mol.change_bounds_rate = cab["change rate"]
                    mol.change_bounds_target = cab["concentration"]
                else:
                    mol.change_bounds = False
                pd = mol_dic["plotting"]
                mol.make_plots = pd["plot 2D"]
                mol.make_ani = pd["animate"]
                mol.plot_autoscale = pd["autoscale colorbar"]
                mol.plot_max = pd["max val"]
                mol.plot_min = pd["min val"]
        if p.substances_affect_charge and self.charge_has_been_balanced is False:
            Qcells = 0
            Qenv = 0
            Qmit = 0
            for name in self.molecules:
                mol = self.molecules[name]
                Qcells += mol.c_cello * mol.z * mol.scale_factor
                Qenv += mol.c_envo * mol.z * mol.scale_factor
                if self.mit_enabled:
                    Qmit += mol.c_mito * mol.z * mol.scale_factor
            self.bal_charge(Qcells, sim, "cell", p)
            self.bal_charge(Qenv, sim, "env", p)
            if self.mit_enabled:
                self.bal_charge(Qmit, sim, "mit", p)
            self.charge_has_been_balanced = True
        self.write_growth_and_decay()
        logs.log_info("Writing passive electrodiffusion equations...")
        for k, v in self.cell_concs.items():
            name = "'{}'".format(k)
            if self.zmol[k] != 0.0 and self.Dmem[k] != 0.0:
                if p.is_ecm is True:
                    self.ED_eval_strings[k] = (
                        "(self.Dmem[{}]/p.tm)*((p.F*sim.vm)/(p.R*sim.T))*self.zmol[{}]*((self.mem_concs[{}] - self.env_concs[{}][cells.map_mem2ecm]*np.exp(-(self.zmol[{}]*p.F*sim.vm)/(p.R*sim.T)))/(1-np.exp(-(self.zmol[{}]*p.F*sim.vm)/(p.R*sim.T))))".format(
                            name, name, name, name, name, name
                        )
                    )
                else:
                    self.ED_eval_strings[k] = (
                        "(self.Dmem[{}]/p.tm)*((p.F*sim.vm)/(p.R*sim.T))*self.zmol[{}]*((self.mem_concs[{}] - self.env_concs[{}][cells.mem_to_cells]*np.exp(-(self.zmol[{}]*p.F*sim.vm)/(p.R*sim.T)))/(1-np.exp(-(self.zmol[{}]*p.F*sim.vm)/(p.R*sim.T))))".format(
                            name, name, name, name, name, name
                        )
                    )
            elif self.zmol[k] == 0.0 and self.Dmem[k] != 0.0:
                if p.is_ecm is True:
                    self.ED_eval_strings[k] = (
                        "(self.Dmem[{}]/p.tm)*(self.mem_concs[{}] - self.env_concs[{}][cells.map_mem2ecm])".format(
                            name, name, name
                        )
                    )
                else:
                    self.ED_eval_strings[k] = (
                        "(self.Dmem[{}]/p.tm)*(self.mem_concs[{}] - self.env_concs[{}][cells.mem_to_cells])".format(
                            name, name, name
                        )
                    )
            elif self.Dmem[k] == 0.0:
                self.ED_eval_strings[k] = "np.zeros(sim.mdl)"

    def write_reactions_env(self):
        logs.log_info("Writing reaction equations for env zone...")
        for reaction_name in self.reactions_env:
            rea_tex_var_list = []
            reactant_names = self.reactions_env[reaction_name].reactants_list
            reactant_coeff = self.reactions_env[reaction_name].reactants_coeff
            reactant_Km = self.reactions_env[reaction_name].Km_reactants_list
            product_names = self.reactions_env[reaction_name].products_list
            product_coeff = self.reactions_env[reaction_name].products_coeff
            product_Km = self.reactions_env[reaction_name].Km_products_list
            a_list = self.reactions_env[reaction_name].reaction_activators_list
            Km_a_list = self.reactions_env[reaction_name].reaction_activators_Km
            n_a_list = self.reactions_env[reaction_name].reaction_activators_n
            zone_a = self.reactions_env[reaction_name].reaction_activators_zone
            i_list = self.reactions_env[reaction_name].reaction_inhibitors_list
            Km_i_list = self.reactions_env[reaction_name].reaction_inhibitors_Km
            n_i_list = self.reactions_env[reaction_name].reaction_inhibitors_n
            zone_i = self.reactions_env[reaction_name].reaction_inhibitors_zone
            r_zone = self.reactions_env[reaction_name].reaction_zone
            numo_string_Q = "("
            denomo_string_Q = "("
            numo_tex_Q = ""
            deno_tex_Q = ""
            for i, (name, coeff) in enumerate(zip(reactant_names, reactant_coeff)):
                tex_name = name
                denomo_string_Q += "(1.0e-3*self.env_concs['{}']".format(name)
                denomo_string_Q += "**{})".format(coeff)
                deno_tex_Q += "[%s]^{%.1f}" % (tex_name, coeff)
                if i < len(reactant_names) - 1:
                    denomo_string_Q += "*"
                    deno_tex_Q += "\\,"
                else:
                    denomo_string_Q += ")"
            for i, (name, coeff) in enumerate(zip(product_names, product_coeff)):
                tex_name = name
                numo_string_Q += "(1.0e-3*self.env_concs['{}']".format(name)
                numo_string_Q += "**{})".format(coeff)
                numo_tex_Q += "[%s]^{%.1f}" % (tex_name, coeff)
                if i < len(product_names) - 1:
                    numo_string_Q += "*"
                    numo_tex_Q += "\\,"
                else:
                    numo_string_Q += ")"
            Q = "(" + numo_string_Q + "/" + denomo_string_Q + ")"
            Q_tex = "\\frac{%s}{%s}" % (numo_tex_Q, deno_tex_Q)
            forward_coeff = "("
            backward_coeff = "("
            fwd_coeff_tex = ""
            bwd_coeff_tex = ""
            for i, (name, n, Km) in enumerate(zip(reactant_names, reactant_coeff, reactant_Km)):
                tex_name = name
                numo_string_r = "((self.env_concs['{}']/{})**{})".format(name, Km, n)
                denomo_string_r = "(1 + (self.env_concs['{}']/{})**{})".format(name, Km, n)
                cc_tex = "\\left(\\frac{[%s]}{K_{%s_f}^{%s}}\\right)" % (
                    tex_name,
                    reaction_name,
                    tex_name,
                )
                tex_term = "\\left(\\frac{%s}{1 + %s}\\right)" % (cc_tex, cc_tex)
                term = "(" + numo_string_r + "/" + denomo_string_r + ")"
                forward_coeff += term
                fwd_coeff_tex += tex_term
                kmval = tex_val(Km)
                km_tex = "K_{%s_f}^{%s} & =" % (reaction_name, name)
                km_tex += kmval
                nval = tex_val(n)
                n_tex = "n_{%s_f}^{%s} & =" % (reaction_name, name)
                n_tex += nval
                rea_tex_var_list.append(km_tex)
                rea_tex_var_list.append(n_tex)
                if i < len(reactant_names) - 1:
                    forward_coeff += "*"
                    fwd_coeff_tex += "\\,"
                else:
                    forward_coeff += ")"
            for i, (name, n, Km) in enumerate(zip(product_names, product_coeff, product_Km)):
                tex_name = name
                numo_string_p = "((self.env_concs['{}']/{})**{})".format(name, Km, n)
                denomo_string_p = "(1 + (self.env_concs['{}']/{})**{})".format(name, Km, n)
                term = "(" + numo_string_p + "/" + denomo_string_p + ")"
                cc_tex = "\\left(\\frac{[%s]}{K_{%s_r}^{%s}}\\right)" % (
                    tex_name,
                    reaction_name,
                    tex_name,
                )
                tex_term = "\\left(\\frac{%s}{1 + %s}\\right)" % (cc_tex, cc_tex)
                backward_coeff += term
                bwd_coeff_tex += tex_term
                if self.reactions_env[reaction_name].delta_Go is not None:
                    kmval = tex_val(Km)
                    km_tex = "K_{%s_r}^{%s} & =" % (reaction_name, name)
                    km_tex += kmval
                    nval = tex_val(n)
                    n_tex = "n_{%s_r}^{%s} & =" % (reaction_name, name)
                    n_tex += nval
                    rea_tex_var_list.append(km_tex)
                    rea_tex_var_list.append(n_tex)
                if i < len(product_names) - 1:
                    backward_coeff += "*"
                    bwd_coeff_tex += "\\,"
                else:
                    backward_coeff += ")"
            if self.reactions_env[reaction_name].delta_Go is not None:
                Keqm = "(np.exp(-self.reactions_env['{}'].delta_Go / (p.R * sim.T)))".format(
                    reaction_name
                )
                Keqm_tex = "exp\\left(-\\frac{deltaG_{%s}^{o}}{R\\,T}\\right)" % reaction_name
                gval = tex_val(self.reactions_env[reaction_name].delta_Go)
                g_tex = "deltaG_{%s}^{o} & =" % reaction_name
                g_tex += gval
                rea_tex_var_list.append(g_tex)
            else:
                Q = "0"
                backward_coeff = "0"
                Keqm = "1"
                Q_tex = ""
                Keqm_tex = ""
                bwd_coeff_tex = ""
            reversed_term = "(" + Q + "/" + Keqm + ")"
            reversed_term_tex = "\\frac{%s}{%s}" % (Q_tex, Keqm_tex)
            all_alpha, alpha_tex, rea_tex_var_list = self.get_influencers(
                a_list,
                Km_a_list,
                n_a_list,
                i_list,
                Km_i_list,
                n_i_list,
                tex_list=rea_tex_var_list,
                reaction_zone=r_zone,
                zone_tags_a=zone_a,
                zone_tags_i=zone_i,
                in_mem_tag=False,
            )
            vmax = "self.reactions_env['{}'].vmax".format(reaction_name)
            if self.reactions_env[reaction_name].delta_Go is not None:
                reaction_eval_string = (
                    vmax
                    + "*"
                    + all_alpha
                    + "*"
                    + forward_coeff
                    + "*"
                    + "("
                    + "1.0"
                    + "-"
                    + "("
                    + reversed_term
                    + ")"
                    + ")"
                )
            else:
                reaction_eval_string = (
                    vmax
                    + "*"
                    + all_alpha
                    + "*"
                    + "("
                    + forward_coeff
                    + "-"
                    + "("
                    + reversed_term
                    + "*"
                    + backward_coeff
                    + ")"
                    + ")"
                )
            r_tex = "r_{%s}^{max}" % reaction_name
            r_main = "r_{%s} = " % reaction_name
            if self.reactions_env[reaction_name].delta_Go is not None:
                reaction_tex_string = (
                    r_main
                    + r_tex
                    + "\\,"
                    + alpha_tex
                    + "\\,\\left("
                    + fwd_coeff_tex
                    + "-"
                    + reversed_term_tex
                    + "\\,"
                    + bwd_coeff_tex
                    + "\\right)"
                )
            else:
                reaction_tex_string = r_main + r_tex + "\\," + alpha_tex + "\\," + fwd_coeff_tex
            rval = tex_val(self.reactions_env[reaction_name].vmax)
            r_tex = "r_{%s}^{max} & =" % reaction_name
            r_tex += rval
            rea_tex_var_list.append(r_tex)
            tex_params = "\\begin{aligned}"
            for i, tex_str in enumerate(rea_tex_var_list):
                tex_params += tex_str
                if i < len(rea_tex_var_list) - 1:
                    tex_params += "\\\\"
                else:
                    tex_params += "\\end{aligned}"
            self.reactions_env[reaction_name].reaction_tex_vars = tex_params
            self.reactions_env[reaction_name].reaction_eval_string = reaction_eval_string
            self.reactions_env[reaction_name].reaction_tex_string = reaction_tex_string

    def create_reaction_matrix_env(self):
        logs.log_info("Writing reaction network matrix for env zone...")
        n_reacts = len(self.reactions_env)
        n_mols = len(self.env_concs)
        self.reaction_matrix_env = np.zeros((n_mols, n_reacts))
        molecule_keys = list(self.env_concs.keys())
        for j, reaction_name in enumerate(self.reactions_env):
            for react_name, coeff in zip(
                self.reactions_env[reaction_name].reactants_list,
                self.reactions_env[reaction_name].reactants_coeff,
            ):
                i = molecule_keys.index(react_name)
                self.reaction_matrix_env[i, j] += -coeff
            for prod_name, coeff in zip(
                self.reactions_env[reaction_name].products_list,
                self.reactions_env[reaction_name].products_coeff,
            ):
                i = molecule_keys.index(prod_name)
                self.reaction_matrix_env[i, j] += coeff

    def bal_charge(self, Q, sim, tag, p):
        if tag == "cell":
            if Q < 0 and np.abs(Q) <= sim.cc_cells[sim.iM].mean():
                self.cell_concs["M"] = sim.cc_cells[sim.iM] - np.abs(Q)
            elif Q > 0 and np.abs(Q) <= sim.cc_cells[sim.iK].mean():
                self.cell_concs["K"] = sim.cc_cells[sim.iK] - np.abs(Q)
            elif Q < 0 and np.abs(Q) > sim.cc_at_mem[sim.iM].mean():
                raise BetseSimConfException(
                    'You have defined more anionic charge in the extra substances (cell region) than can be compensated for. Either disable "substances affect Vmem" or try again.'
                )
            elif Q > 0 and np.abs(Q) > sim.cc_cells[sim.iK].mean():
                raise BetseSimConfException(
                    'You have defined more cationic charge in the extra substances (cell region) than can be compensated for. Either disable "substances affect Vmem" or try again.'
                )
            sim.extra_rho_cells = p.F * Q * np.ones(sim.cdl)
        elif tag == "env":
            if Q < 0 and np.abs(Q) <= sim.cc_env[sim.iM].mean():
                self.env_concs["M"] = sim.cc_env[sim.iM] - np.abs(Q)
                self.bound_concs["M"] = sim.c_env_bound[sim.iM] - np.abs(Q)
            elif Q > 0 and np.abs(Q) <= sim.cc_env[sim.iNa].mean():
                self.env_concs["Na"] = sim.cc_env[sim.iNa] - np.abs(Q)
                self.bound_concs["Na"] = sim.c_env_bound[sim.iNa] - np.abs(Q)
            elif Q < 0 and np.abs(Q) > sim.cc_env[sim.iM].mean():
                raise BetseSimConfException(
                    "You've defined way more anionic charge in the extra substances (env region) than we can compensate for. Either turn 'substances affect Vmem' off, or try again."
                )
            elif Q > 0 and np.abs(Q) > sim.cc_env[sim.iNa].mean():
                raise BetseSimConfException(
                    "You've defined way more cationic charge in the extra substances (env region) than we can compensate for. Either turn 'substances affect Vmem' off, or try again."
                )
            sim.extra_rho_env = p.F * Q * np.ones(sim.edl)
        elif tag == "mit":
            if Q < 0 and np.abs(Q) <= sim.cc_mit[sim.iP].mean():
                self.mit_concs["P"] = sim.cc_mit[sim.iP] - np.abs(Q)
            elif Q > 0 and np.abs(Q) <= sim.cc_mit[sim.iK].mean():
                self.mit_concs["K"] = sim.cc_mit[sim.iK] - np.abs(Q)
            elif Q < 0 and np.abs(Q) > sim.cc_mit[sim.iP].mean():
                raise BetseSimConfException(
                    "You've defined way more anionic charge inthe extra substances than we can compensate for. Either turn 'substances affect Vmem' off, or try again."
                )
            elif Q > 0 and np.abs(Q) > sim.cc_mit[sim.iK].mean():
                raise BetseSimConfException(
                    "You've defined way more cationic charge inthe extra substances than we can compensate for. Either turn 'substances affect Vmem' off, or try again."
                )
            self.mit.extra_rho = p.F * Q * np.ones(sim.cdl)


class MasterOfGenes(object):
    def __init__(self, p):
        pass

    def reinitialize(self, phase):
        cells = phase.cells
        p = phase.p
        sim = phase.sim
        config_dic = p.grn.conf
        self.core.time_dila = float(config_dic.get("time dilation factor", 1.0))
        self.reset_MT = config_dic.get("reset microtubules", False)
        self.recalc_fluid = config_dic.get("recalculate fluid flow", False)
        substances_config = config_dic["biomolecules"]
        reactions_config = config_dic.get("reactions", None)
        transporters_config = config_dic.get("transporters", None)
        channels_config = config_dic.get("channels", None)
        modulators_config = config_dic.get("modulators", None)
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

    def read_gene_config(self, phase):
        cells = phase.cells
        p = phase.p
        sim = phase.sim
        config_dic = p.grn.conf
        substances_config = config_dic["biomolecules"]
        reactions_config = config_dic.get("reactions", None)
        transporters_config = config_dic.get("transporters", None)
        channels_config = config_dic.get("channels", None)
        modulators_config = config_dic.get("modulators", None)
        self.core = MasterOfNetworks(sim, cells, substances_config, p)
        self.core.time_dila = float(config_dic.get("time dilation factor", 1.0))
        self.reset_MT = config_dic.get("reset microtubules", False)
        self.recalc_fluid = config_dic.get("recalculate fluid", False)
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
        self.core.net_plot_opts = config_dic.get("network plotting", None)
        set_net_opts(self.core, self.core.net_plot_opts, p)
        optim_exists = config_dic.get("optimization", None)
        if optim_exists is not None:
            opti = config_dic["optimization"]["optimize network"]
            self.core.opti_N = config_dic["optimization"]["optimization steps"]
            self.core.opti_method = config_dic["optimization"]["optimization method"]
            self.core.target_vmem = float(config_dic["optimization"]["target Vmem"])
            self.core.opti_T = float(config_dic["optimization"]["optimization T"])
            self.core.opti_step = float(config_dic["optimization"]["optimization step"])
            if opti:
                logs.log_info("Analyzing gene network for optimal rates...")
                self.core.optimizer(sim, cells, p)
                self.reinitialize(phase)


def initialize_owner(self, t, phase, cells, p):
    if p.grn_enabled:
        if self.grn is None:
            logs.log_info("Initializing gene regulatory network...")
            self.grn = MasterOfGenes(p)
            self.grn.read_gene_config(phase)
        else:
            logs.log_info("Reinitializing the gene regulatory network for simulation...")
            self.grn.reinitialize(phase)


def dispatch(self, t, phase, cells, p):
    if p.grn_enabled:
        self.grn.core.clear_run_loop(self)
        self.grn.core._observe_dispatch("clear_run_loop", self, phase)
        if self.grn.transporters:
            self.grn.core.run_loop_transporters(t, self, cells, p)
            self.grn.core._observe_dispatch("run_loop_transporters", self, phase)
        if self.grn.channels:
            self.grn.core.run_loop_channels(phase)
            self.grn.core._observe_dispatch("run_loop_channels", self, phase)
        if self.grn.modulators:
            self.grn.core.run_loop_modulators(self, cells, p)
            self.grn.core._observe_dispatch("run_loop_modulators", self, phase)
        self.grn.core.run_loop(phase=phase, t=t)
        self.grn.core._observe_dispatch("run_loop", self, phase)


"""Pure state-adapter template emitted into two independent capture modules.

This file is not imported as a scientific implementation. The emitting tool
reads its text; lifecycle/math bodies are separately original-AST authenticated.
"""

ALIASES = {"cell_concs", "mem_concs", "env_concs", "bound_concs", "mit_concs"}
OBJECTS = {
    "molecules",
    "reactions",
    "reactions_env",
    "reactions_mit",
    "modulators",
    "channels",
    "mit",
    "molecule_frames",
    "mover_frames",
    "rhs",
}
DYNAMIC = ("c_cells", "cc_at_mem", "c_env", "flux_intra", "f_mem", "f_gj", "fenvx", "fenvy")
REQUIRED_MOLECULE = {
    "Dgj",
    "Dm",
    "Do",
    "Mu_mem",
    "TJ_factor",
    "c_bound",
    "c_cells",
    "c_env",
    "cc_at_mem",
    "ignoreGJ",
    "ignoreTJ",
    "ignore_ECM_pump",
    "modify_time_factor",
    "name",
    "transmem",
    "u_mt",
    "update_intra_conc",
    "z",
    "active_pumping",
    "ion_channel_gating",
    "change_bounds",
    "cell_clamp",
    "simple_growth",
    "gad_eval_string",
    "scale_factor",
}


class GRNInitializationRefused(ValueError):
    def __init__(self, reason, partial):
        super().__init__(str(reason))
        self.partial = partial


def clone(value):
    if isinstance(value, np.ndarray):
        return value.copy()
    if isinstance(value, Mapping):
        return {key: clone(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [clone(item) for item in value]
    return copy.deepcopy(value)


def public(obj, excluded=()):
    return {
        key: clone(value)
        for key, value in vars(obj).items()
        if not key.startswith("_") and key not in excluded and not callable(value)
    }


def wire(owner, sim):
    core = getattr(owner, "core", None) if owner is not None else None
    return dict(
        owner_fields={} if owner is None else public(owner, {"core"}),
        core_fields={} if core is None else public(core, ALIASES | OBJECTS),
        molecule_fields={}
        if core is None
        else {name: public(obj) for name, obj in core.molecules.items()},
        reaction_fields={}
        if core is None
        else {name: public(obj) for name, obj in core.reactions.items()},
        modulator_fields={}
        if core is None
        else {name: public(obj) for name, obj in core.modulators.items()},
        ion_boundary_state=clone(sim.c_env_bound),
        simulator_fields={
            key: clone(getattr(sim, key))
            for key in (
                "extra_rho_cells",
                "extra_rho_env",
                "extra_J_mem",
                "extra_Jenv_x",
                "extra_Jenv_y",
            )
            if hasattr(sim, key)
        },
    )


def snapshot(molecules):
    return {
        name: dict(
            {key: clone(getattr(obj, key, None)) for key in DYNAMIC},
            present_fields=tuple(key for key in DYNAMIC if hasattr(obj, key)),
        )
        for name, obj in molecules.items()
    }


def cache(net):
    raw = wire(net._sim.grn, net._sim)
    dynamic = ("reaction_rates", "delta_conc", "delta_conc_env", "chi")
    result = dict(
        kind="cells.genuine_grn_owner_cache@1",
        wire=raw,
        present_fields=tuple(key for key in dynamic if hasattr(net, key)),
        molecule_states=snapshot(net.molecules),
        growth_expressions={name: obj.gad_eval_string for name, obj in net.molecules.items()},
    )
    for key in (
        *dynamic,
        "reaction_matrix",
        "extra_rho_env",
        "extra_rho_mit",
        "extra_Jenv_x",
        "extra_Jenv_y",
        "extra_rho_cells",
        "extra_J_mem",
    ):
        result[key] = clone(getattr(net, key, None))
    result["reaction_expressions"] = {
        name: obj.reaction_eval_string for name, obj in net.reactions.items()
    }
    result["modulator_expressions"] = {
        name: obj.alpha_eval_string for name, obj in net.modulators.items()
    }
    return result


def owner_evidence(sim, expected_core):
    owner = sim.grn
    return dict(
        owner_class=type(owner).__name__,
        core_class=type(owner.core).__name__,
        grn_enabled=sim._grn_parameters.grn_enabled,
        molecules_enabled=sim._grn_parameters.molecules_enabled,
        actual_core_identity=owner.core is expected_core,
        flags=public(owner, {"core"}),
        charge_has_been_balanced=owner.core.charge_has_been_balanced,
        time_dilation=owner.core.time_dila,
    )


def configure_owner_context(sim, cells, p, definition):
    p.grn = SimpleNamespace(conf=clone(definition["grn_configuration"]))
    sim._grn_parameters = p
    p.grn_enabled, p.molecules_enabled, p.plot_network = True, False, False
    sim.c_env_bound = np.asarray(definition["ion_boundary_mM"], np.float64).copy()
    cells.R_rads = np.asarray(definition["radius_m"], np.float64).copy()


def cold_owner(sim, cells, p, definition):
    configure_owner_context(sim, cells, p, definition)
    sim.grn = None
    old_publication = p.substances_affect_charge
    p.substances_affect_charge = definition["grn_initialization_publish"]
    phase = SimpleNamespace(sim=sim, cells=cells, p=p, kind="INIT", dyna=SimpleNamespace())
    try:
        literals()["initialize_owner"](sim, 0.0, phase, cells, p)
    except Exception as error:
        partial = dict(
            source_exception=type(error).__name__,
            source_message=str(error),
            stage="grn_initialization",
            owner_snapshot=wire(sim.grn, sim),
            actual_grn_enabled=p.grn_enabled,
            actual_molecules_enabled=p.molecules_enabled,
            initialization_publication=p.substances_affect_charge,
        )
        raise GRNInitializationRefused(error, partial) from error
    finally:
        p.substances_affect_charge = old_publication
    sim.grn.core._sim = sim
    return sim.grn.core


def restore_owner(sim, cells, p, definition, incoming):
    configure_owner_context(sim, cells, p, definition)
    if incoming is None or incoming.get("kind") != "cells.genuine_grn_owner_cache@1":
        raise ValueError("Require a complete genuine GRN owner cache")
    raw = incoming["wire"]
    if not isinstance(raw, Mapping) or set(raw) != {
        "owner_fields",
        "core_fields",
        "molecule_fields",
        "reaction_fields",
        "modulator_fields",
        "ion_boundary_state",
        "simulator_fields",
    }:
        raise ValueError("Require all GRN owner/cache fields")
    expected_flags = dict(
        reset_MT=False,
        recalc_fluid=False,
        reactions=True,
        transporters=False,
        channels=False,
        modulators=definition["grn_configuration"].get("modulators") is not None,
    )
    if dict(raw["owner_fields"]) != expected_flags or set(raw["molecule_fields"]) != {"X", "Y"}:
        raise ValueError("Changed GRN owner or configured dispatch flags")
    for values in raw["molecule_fields"].values():
        if not REQUIRED_MOLECULE <= values.keys() or values["ignore_ECM_pump"] is not True:
            raise ValueError("Missing source-initialized GRN molecule fields")
    ns = literals()
    owner = object.__new__(ns["MasterOfGenes"])
    vars(owner).update(clone(raw["owner_fields"]))
    net = object.__new__(ns["MasterOfNetworks"])
    vars(net).update(clone(raw["core_fields"]))
    owner.core, sim.grn, net._sim = net, owner, sim
    for attr, key, cls in (
        ("molecules", "molecule_fields", "Molecule"),
        ("reactions", "reaction_fields", "Reaction"),
        ("modulators", "modulator_fields", "Modulator"),
    ):
        objects = OrderedDict()
        for name, values in raw[key].items():
            obj = object.__new__(ns[cls])
            vars(obj).update(clone(values))
            objects[name] = obj
        setattr(net, attr, objects)
    net.reactions_env, net.reactions_mit, net.channels, net.mit = (
        OrderedDict(),
        OrderedDict(),
        OrderedDict(),
        None,
    )
    sim.c_env_bound = np.asarray(raw["ion_boundary_state"], np.float64).copy()
    for key, value in raw["simulator_fields"].items():
        if key not in {"extra_rho_cells", "extra_J_mem"}:
            setattr(sim, key, clone(value))
    for attr, ionic, molecular in (
        ("cell_concs", "cc_cells", "c_cells"),
        ("mem_concs", "cc_at_mem", "cc_at_mem"),
        ("env_concs", "cc_env", "c_env"),
        ("bound_concs", "c_env_bound", "c_bound"),
    ):
        mapping = OrderedDict()
        for name in p.ions_dict:
            i = sim.get_ion(name)
            mapping[name] = ns["DynamicValue"](
                lambda i=i, a=ionic: getattr(sim, a)[i],
                lambda value, i=i, a=ionic: getattr(sim, a).__setitem__(i, value),
            )
        for name in net.molecules:
            mapping[name] = ns["DynamicValue"](
                lambda name=name, a=molecular: getattr(net.molecules[name], a),
                lambda value, name=name, a=molecular: setattr(net.molecules[name], a, value),
            )
        setattr(net, attr, ns["DynamicValueDict"](mapping))
    net.mit_concs = None
    return net


def attach_observers(net, sim, p, incoming):
    trace = dict(
        cache_before=clone(incoming),
        control_writes=[],
        molecule_frames=[],
        mover_frames=[],
        rhs={},
        source_completed=False,
        executed_chemistry=False,
    )
    net.molecule_frames, net.mover_frames, net.rhs = (
        trace["molecule_frames"],
        trace["mover_frames"],
        trace["rhs"],
    )

    def chemistry(stage, species, actual):
        trace["molecule_frames"].append(
            dict(
                stage=stage,
                species=species,
                molecule_states=snapshot(net.molecules),
                cell_concs=actual.cc_cells.copy(),
                mem_concs=actual.cc_at_mem.copy(),
                vm=actual.vm.copy(),
                vgj=actual.vgj.copy(),
                cache=cache(net),
            )
        )

    def mover(stage, name, local, actual):
        fields = (
            "cX_env_o",
            "cX_cells",
            "cX_mems",
            "f_X_ED",
            "fgj_X",
            "fenvx",
            "fenvy",
            "delta_cco",
            "Dm_vect",
        )
        trace["mover_frames"].append(
            dict(
                stage=stage,
                species=name,
                fields={key: clone(local.get(key)) for key in fields},
                vm=actual.vm.copy(),
                vgj=actual.vgj.copy(),
            )
        )

    def control(name, value, actual):
        trace["control_writes"].append(
            dict(
                rule_id=name,
                target=net.modulators[name].target_label,
                value=np.array(value, copy=True),
                gj_block=np.array(actual.gj_block, copy=True),
                NaKATP_block=np.array(actual.NaKATP_block, copy=True),
            )
        )

    net._observe_control, net._observe_chem, p._mover_observe = control, chemistry, mover
    net._observe_rhs = lambda growth, reaction, combined: trace["rhs"].update(
        growth_rates=np.array(growth, copy=True),
        reaction_rates=np.array(reaction, copy=True),
        all_rates=np.array(combined, copy=True),
    )
    return trace


def literals():
    return dict(
        MasterOfGenes=MasterOfGenes,
        MasterOfNetworks=MasterOfNetworks,
        Molecule=Molecule,
        Reaction=feedback_source.Reaction,
        Modulator=feedback_source.Modulator,
        DynamicValue=DynamicValue,
        DynamicValueDict=DynamicValueDict,
        initialize_owner=initialize_owner,
        dispatch=dispatch,
    )


EXTRA = {
    "grn_configuration",
    "ion_boundary_mM",
    "grn_initialization_publish",
    "raw_initialization_fault",
}


def validate(definition, ion_binding, current_binding, configured_temperature_K):
    if (
        not isinstance(definition, dict)
        or definition.get("owner") != "grn"
        or not EXTRA <= definition.keys()
    ):
        raise ValueError(
            "Require an actual configured GRN owner and complete initialization context"
        )
    base = {key: value for key, value in definition.items() if key not in EXTRA}
    base["owner"] = "molecules"
    molecule_source.validate(base, ion_binding, current_binding, configured_temperature_K)
    cfg = definition["grn_configuration"]
    if len(definition["reactions"]) != 1 or not molecule_source._number(
        cfg.get("time dilation factor", 1.0), positive=True
    ):
        raise ValueError(
            "First genuine GRN scope requires one X-to-Y reaction and positive time dilation"
        )
    if (
        set(cfg) - {"biomolecules", "reactions", "modulators", "time dilation factor"}
        or cfg.get("reactions") != definition["reactions"]
        or cfg.get("modulators") != (definition["modulators"] or None)
    ):
        raise ValueError(
            "Require normal configured GRN reactions/modulators; other lifecycle branches are separate"
        )
    if definition["grn_initialization_publish"] is not True:
        raise ValueError("This neutral GRN scope executes original zero-charge initialization")
    boundary = np.asarray(definition["ion_boundary_mM"], np.float64)
    if (
        boundary.shape != (len(ion_binding.ion_ids),)
        or not np.isfinite(boundary).all()
        or np.any(boundary < 0)
    ):
        raise ValueError("Require every owned ionic boundary value")
    rows = cfg.get("biomolecules")
    if (
        not isinstance(rows, list)
        or len(rows) != 2
        or [row.get("name") for row in rows] != [row["name"] for row in definition["molecules"]]
    ):
        raise ValueError("Require genuine configured X/Y GRN products in declared order")
    fault = definition["raw_initialization_fault"]
    if fault not in (None, "X", "Y"):
        raise ValueError("Only the explicit malformed-Dm source retention controls are supported")
    for row, projection in zip(rows, definition["molecules"], strict=True):
        required = {
            "name",
            "cell conc",
            "env conc",
            "Dm",
            "Do",
            "z",
            "update intracellular",
            "TJ permeable",
            "GJ impermeable",
            "TJ factor",
            "plotting",
            "growth and decay",
        }
        allowed = required | {"Dgj", "use time dilation"}
        missing = required - set(row)
        if (
            missing != ({"Dm"} if fault == row["name"] else set())
            or set(row) - allowed
            or row["z"] != 0
            or row["update intracellular"] is not False
        ):
            raise ValueError("Require the bounded neutral, instant-mixing native GRN configuration")
        params = projection["parameters"]
        if row["plotting"] != {
            "plot 2D": False,
            "animate": False,
            "autoscale colorbar": True,
            "max val": 1.0,
            "min val": 0.0,
        }:
            raise ValueError(
                "This normal GRN scope uses the explicit disabled plotting configuration"
            )
        expected = dict(
            z=row["z"],
            Dm=row.get("Dm", params["Dm"]),
            Do=row["Do"],
            Dgj=row.get("Dgj", 1e-16),
            c_bound=row["env conc"],
            TJ_factor=row["TJ factor"],
            ignoreTJ=row["TJ permeable"],
            ignoreGJ=row["GJ impermeable"],
            ignore_ECM_pump=True,
            update_intra_conc=False,
            transmem=False,
            modify_time_factor=float(cfg.get("time dilation factor", 1.0))
            if row.get("use time dilation", False)
            else 1.0,
            Mu_mem=0.0,
            u_mt=0.0,
            scale_factor=1.0,
            active_pumping=False,
            ion_channel_gating=False,
            change_bounds=False,
            cell_clamp=False,
        )
        if params != expected:
            raise ValueError(
                "Declared parameter projection must match actual source defaults/configuration"
            )
        initial = projection["initial"]
        if (
            any(
                value != row["cell conc"]
                for key in ("c_cells", "cc_at_mem")
                for value in initial[key]
            )
            or any(value != row["env conc"] for value in initial["c_env"])
            or any(initial["flux_intra"])
        ):
            raise ValueError(
                "Cold GRN arrays must come from native scalar concentrations and zero flux"
            )
        gad = row["growth and decay"]
        growth = projection["growth"]
        wanted = dict(
            enabled=gad is not None,
            production_rate_mM_s=0.0 if gad is None else gad["production rate"],
            decay_rate_per_s=0.0 if gad is None else gad["decay rate"],
            decay_max_per_s=0.0 if gad is None else gad.get("decay max", 0.0),
            scale_factor=1.0 if gad is None else gad.get("scale factor", 1.0),
        )
        if growth != wanted:
            raise ValueError("Growth projection must equal the actual GRN configuration")
        if gad is not None:
            if gad["apply to"] != "all" or set(gad) - {
                "production rate",
                "decay rate",
                "decay max",
                "scale factor",
                "apply to",
                "activators",
                "Km activators",
                "n activators",
                "inhibitors",
                "Km inhibitors",
                "n inhibitors",
                "decay activators",
                "Km decay activators",
                "n decay activators",
                "decay inhibitors",
                "Km decay inhibitors",
                "n decay inhibitors",
            }:
                raise ValueError("First configured GRN uses all-cell ordinary Hill regulation")
            for prefix in ("", "decay "):
                for sign in ("activators", "inhibitors"):
                    names = gad.get(prefix + sign)
                    if names is None:
                        continue
                    if not isinstance(names, list) or len(names) > len(ion_binding.ion_ids) + 2:
                        raise ValueError("Require bounded ordinary GRN regulator lists")
                    for name, km, exponent in zip(
                        names, gad["Km " + prefix + sign], gad["n " + prefix + sign], strict=True
                    ):
                        if (
                            name not in (*ion_binding.ion_ids, "X", "Y")
                            or not molecule_source._number(km, positive=True)
                            or not molecule_source._number(exponent, positive=True)
                        ):
                            raise ValueError("Invalid ordinary GRN Hill regulator")


def context(arrays, ion_ids, parameters, definition, incoming_controls):
    cell, mem, bath, vm, *_ = arrays
    n, m = cell.shape[1], len(vm)
    sim = SimpleNamespace(
        cc_cells=cell,
        cc_at_mem=mem,
        cc_env=bath,
        vm=vm,
        vgj=arrays[6],
        gjopen=arrays[9],
        T=parameters["runtime_temperature_K"],
        cdl=n,
        mdl=m,
        edl=m,
        zs=np.asarray(parameters["valence"], np.float64),
        Dm_cells=np.asarray(parameters["ion_Dm"], np.float64),
        rho_channel=np.asarray(definition["rho_channel"], np.float64).copy(),
        gj_block=np.array(incoming_controls["gj_block"], copy=True),
        NaKATP_block=np.array(incoming_controls["NaKATP_block"], copy=True),
        extra_rho_cells=np.array(parameters["incoming_extra_charge"], copy=True),
        extra_J_mem=np.array(parameters["incoming_extra_current"], copy=True),
    )
    sim.get_ion = lambda name: ion_ids.index(name)
    g = parameters["geometry"]
    cells = SimpleNamespace(
        cell_i=np.arange(n),
        mem_i=np.arange(m),
        mem_to_cells=np.asarray(g["owner"], np.int64),
        nn_i=np.asarray(g["partner"], np.int64),
        bflags_mems=np.asarray(g["boundary"], bool),
        mem_sa=np.asarray(g["membrane_area_m2"], np.float64),
        cell_vol=np.asarray(g["cell_volume_m3"], np.float64),
        M_sum_mems=np.asarray(g["owner_sum"], np.float64),
        gj_len=np.asarray(g["gap_length_m"], np.float64),
        map_mem2ecm=np.asarray(definition["membrane_to_environment"], np.int64),
        R_rads=np.asarray(definition["radius_m"], np.float64),
    )
    p = SimpleNamespace(
        R=parameters["R"],
        F=parameters["F"],
        dt=parameters["dt_s"],
        T=parameters["configured_temperature_K"],
        tm=parameters["membrane_thickness_m"],
        vol_env=parameters["bath_volume_m3"],
        cluster_open=parameters["cluster_open"],
        is_ecm=False,
        ions_dict={name: 1 for name in ion_ids},
        substances_affect_charge=parameters["substances_affect_charge"],
    )
    return sim, cells, p


def initialize_cache(definition, ib, values):
    k = ib.kernel
    arrays = [np.array(value, copy=True) for value in values]
    parameters = dict(
        runtime_temperature_K=k.configured_temperature_K,
        configured_temperature_K=k.configured_temperature_K,
        R=k.R_J_mol_K,
        F=k.F_C_mol,
        dt_s=0.0,
        ion_Dm=k.membrane_diffusion_m2_s,
        valence=k.valence,
        incoming_extra_charge=np.zeros(len(ib.cell_ids)),
        incoming_extra_current=np.zeros(len(ib.membrane_ids)),
        membrane_thickness_m=k.membrane_thickness_m,
        bath_volume_m3=k.bath_volume_m3,
        cluster_open=k.cluster_open,
        substances_affect_charge=True,
        geometry=dict(
            owner=k.owner,
            partner=k.partner,
            boundary=k.boundary,
            membrane_area_m2=k.area_m2,
            cell_volume_m3=k.cell_volume_m3,
            owner_sum=k.owner_sum,
            gap_length_m=k.gap_length_m,
        ),
    )
    sim, cells, p = context(
        arrays, ib.ion_ids, parameters, definition, definition["initial_controls"]
    )
    net = cold_owner(sim, cells, p, definition)
    return cache(net)


def checked_cache(raw, definition):
    n = len(definition["molecules"][0]["initial"]["c_cells"])
    m = len(definition["radius_m"])
    for value in raw["molecule_states"].values():
        molecule_source._dynamic(ions.data(value), n, m)
    return raw


def prepare(
    arrays, *, ion_ids, parameters, definition, incoming_controls, incoming_cache, phase_kind
):
    molecule_source._require_immutable(incoming_cache)
    sim, cells, p = context(arrays, ion_ids, parameters, definition, incoming_controls)
    net = restore_owner(sim, cells, p, definition, incoming_cache)
    attach_observers(net, sim, p, incoming_cache)
    phase = SimpleNamespace(sim=sim, cells=cells, p=p, kind=phase_kind)
    return net, sim, cells, p, phase
