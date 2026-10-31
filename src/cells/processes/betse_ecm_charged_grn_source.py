# ruff: noqa: B007, B905, E501, E402
"""Genuine configured MasterOfGenes initialization and normal GRN dispatch.

Scientific bodies are literal; bounded all-target ECM transport is explicit.
Hot state hydration preserves every public owner/core/molecule field.
"""

from collections import OrderedDict
from collections.abc import Mapping, MutableMapping
from types import SimpleNamespace

import numpy as np

from cells.processes import betse_normal_molecule_source as molecule_source
from cells.processes import betse_normal_network_join_source as feedback_source

logs = SimpleNamespace(log_info=lambda *_: None, log_warning=lambda *_: None)
tex_val = str
types = SimpleNamespace(trim=repr)
MappingMutableType = MutableMapping
BetseMethodUnimplementedException = NotImplementedError
BetseSimException = molecule_source.BetseSimException


class BetseSimConfException(BetseSimException):
    pass


controls = molecule_source.controls
stb = molecule_source.stb


def _outside_scope(*args, **kwargs):
    raise ValueError("Separate mitochondria, asymmetry, optimizer or profile state is required")


Mito = _outside_scope
mods = SimpleNamespace()


class Molecule(molecule_source._Molecule):
    def transport(self, sim, cells, p):
        self.c_env, self.c_cells, self.cc_at_mem, self.f_mem, self.f_gj, self.fenvx, self.fenvy = (
            stb.molecule_mover(
                sim,
                self.c_env,
                self.c_cells,
                cells,
                p,
                z=self.z,
                Dm=self.Dm,
                Do=self.Do,
                Dgj=self.Dgj,
                c_bound=self.c_bound,
                ignoreECM=self.ignore_ECM_pump,
                smoothECM=False,
                ignoreTJ=self.ignoreTJ,
                ignoreGJ=self.ignoreGJ,
                Ftj=self.TJ_factor,
                rho=sim.rho_channel,
                cmems=self.cc_at_mem,
                time_dilation_factor=self.modify_time_factor,
                update_intra=self.update_intra_conc,
                name=self.name,
                transmem=self.transmem,
                mu_mem=self.Mu_mem,
                umt=self.u_mt,
            )
        )


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
        observe_balance(self, "before", Q, sim, tag, p)
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

        observe_balance(self, "after", Q, sim, tag, p)


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


def electroflux(cA, cB, Dc, d, zc, vBA, T, p, rho=1):
    FLOAT_NONCE = 1e-25
    vBA += FLOAT_NONCE
    zc += FLOAT_NONCE
    alpha = zc * vBA * p.F / (p.R * T)
    exp_alpha = np.exp(-alpha)
    deno = -np.expm1(-alpha)
    flux = -(Dc * alpha / d) * ((cB - cA * exp_alpha) / deno) * rho
    return flux


def molecule_mover(
    sim,
    cX_env_o,
    cX_cells,
    cells,
    p,
    z=0,
    Dm=1e-18,
    Do=1e-09,
    Dgj=1e-12,
    Ftj=1.0,
    c_bound=0.0,
    ignoreECM=True,
    smoothECM=False,
    ignoreTJ=False,
    ignoreGJ=False,
    rho=1,
    cmems=None,
    time_dilation_factor=1.0,
    update_intra=False,
    name="Unknown",
    transmem=False,
    mu_mem=0.0,
    umt=0.0,
):
    if p.is_ecm is True:
        cX_env = cX_env_o[cells.map_mem2ecm]
    else:
        cX_env = cX_env_o[:]
    if cmems is None:
        cX_mems = cX_cells[cells.mem_to_cells]
    elif len(cmems) == sim.mdl:
        cX_mems = cmems
    Dm_vect = np.ones(len(cX_mems)) * Dm
    if Dm != 0.0:
        IdM = np.ones(sim.mdl)
        f_X_ED = electroflux(
            cX_env, cX_mems, Dm_vect, p.tm * IdM, z * IdM, sim.vm, sim.T, p, rho=rho
        )
        if p.cluster_open is False:
            f_X_ED[cells.bflags_mems] = 0
    else:
        f_X_ED = np.zeros(sim.mdl)
    cX_cells, cX_mems, cX_env_o = update_Co(
        sim,
        cX_cells,
        cX_mems,
        cX_env_o,
        f_X_ED,
        cells,
        p,
        ignoreECM=ignoreECM,
        update_at_mems=update_intra,
    )
    p._mover_observe("membrane_commit", name, locals(), sim)
    if ignoreGJ is False:
        fgj_X = electroflux(
            cX_mems[cells.mem_i],
            cX_mems[cells.nn_i],
            Dgj * sim.gj_block * sim.gjopen,
            cells.gj_len * np.ones(sim.mdl),
            z * np.ones(sim.mdl),
            sim.vgj,
            p.T,
            p,
            rho=1,
        )
        fgj_X[cells.bflags_mems] = 0.0
        delta_cco = np.dot(cells.M_sum_mems, -fgj_X * cells.mem_sa) / cells.cell_vol
        if update_intra is False:
            cX_cells = cX_cells + p.dt * delta_cco * time_dilation_factor
            cX_mems = cX_cells[cells.mem_to_cells]
        else:
            cX_cells = cX_cells + p.dt * delta_cco * time_dilation_factor
            cX_mems += (
                -fgj_X * (cells.mem_sa / (3 / 4 * cells.mem_vol)) * time_dilation_factor * p.dt
            )
    else:
        fgj_X = np.zeros(sim.mdl)
    p._mover_observe("junction_commit", name, locals(), sim)
    if update_intra is False and ignoreGJ and (transmem is True):
        nx = cells.mem_vects_flat[:, 2]
        ny = cells.mem_vects_flat[:, 3]
        gcc, gccmx, gccmy = cells.gradient(cX_cells)
        mcc = (cX_mems[cells.nn_i] + cX_mems[cells.mem_i]) / 2
        umtx = 0.0
        umty = 0.0
        emtx = (
            sim.E_cell_x[cells.mem_to_cells][cells.nn_i]
            + sim.E_cell_x[cells.mem_to_cells][cells.nn_i]
        ) / 2
        emty = (
            sim.E_cell_y[cells.mem_to_cells][cells.nn_i]
            + sim.E_cell_y[cells.mem_to_cells][cells.nn_i]
        ) / 2
        alpha = Do * p.q * z / (p.kb * sim.T)
        flux_mtx = -Do * gccmx + umtx * mcc * umt + (mu_mem + alpha) * emtx * mcc
        flux_mty = -Do * gccmy + umty * mcc * umt + (mu_mem + alpha) * emty * mcc
        flux_mtn = flux_mtx * nx + flux_mty * ny
        flux_mtn[cells.bflags_mems] = 0.0
        div_ccmt = -np.dot(cells.M_sum_mems, flux_mtn * cells.mem_sa) / cells.cell_vol
        cX_cells += div_ccmt * p.dt * time_dilation_factor
        cX_mems = cX_cells[cells.mem_to_cells] * 1
    if p.is_ecm is True:
        env_check = len((cX_env_o != 0.0).nonzero()[0])
        if env_check != 0.0 or c_bound > 1e-15:
            cenv = cX_env_o
            cenv = cenv.reshape(cells.X.shape)
            cenv[:, 0] = c_bound
            cenv[:, -1] = c_bound
            cenv[0, :] = c_bound
            cenv[-1, :] = c_bound
            p._mover_observe("ecm_clamp", name, locals(), sim)
            denv_multiplier = np.ones(len(cells.xypts))
            if ignoreTJ is False:
                denv_multiplier = denv_multiplier.reshape(cells.X.shape) * sim.D_env_weight
                denv_multiplier.ravel()[sim.TJ_targets] = (
                    denv_multiplier.ravel()[sim.TJ_targets] * Ftj
                )
            else:
                denv_multiplier = denv_multiplier.reshape(cells.X.shape)
            gcx, gcy = fd.gradient(cenv, cells.delta)
            p._mover_observe("ecm_gradient", name, locals(), sim)
            if p.fluid_flow is True:
                ux = sim.u_env_x.reshape(cells.X.shape)
                uy = sim.u_env_y.reshape(cells.X.shape)
            else:
                ux = 0.0
                uy = 0.0
            fx, fy = nernst_planck_flux(
                cenv,
                gcx,
                gcy,
                -sim.E_env_x,
                -sim.E_env_y,
                ux,
                uy,
                denv_multiplier * Do,
                z,
                sim.T,
                p,
                mu=mu_mem,
            )
            p._mover_observe("ecm_flux", name, locals(), sim)
            div_fa = fd.divergence(-fx, -fy, cells.delta, cells.delta)
            fenvx = fx
            fenvy = fy
            cenv = cenv + div_fa * p.dt * time_dilation_factor
            p._mover_observe("ecm_euler", name, locals(), sim)
            if p.sharpness < 1.0:
                cenv = fd.integrator(cenv, sharp=p.sharpness)
            cX_env_o = cenv.ravel()
        else:
            fenvx = np.zeros(sim.edl)
            fenvy = np.zeros(sim.edl)
    else:
        cX_env_temp = cX_env_o.mean()
        cX_env_o = np.zeros(sim.mdl)
        cX_env_o[:] = cX_env_temp
        fenvx = 0
        fenvy = 0
    p._mover_observe("environment_mix", name, locals(), sim)
    indsZm = (cX_mems < 0.0).nonzero()[0]
    indsZc = (cX_cells < 0.0).nonzero()[0]
    if len(indsZc) > 0:
        raise BetseSimUnstableException(
            "Network concentration of "
            + name
            + " in cells below zero! Your simulation has become unstable."
        )
    if len(indsZm) > 0:
        raise BetseSimUnstableException(
            "Network concentration of "
            + name
            + " on membrane below zero! Your simulation has become unstable."
        )
    indsZe = (cX_env_o < 0.0).nonzero()[0]
    if len(indsZe) > 0:
        print(name, c_bound)
        raise BetseSimUnstableException(
            "Network concentration of "
            + name
            + " in environment below zero! Your simulation has become unstable."
        )
    p._mover_observe("return", name, locals(), sim)
    return (cX_env_o, cX_cells, cX_mems, f_X_ED, fgj_X, fenvx, fenvy)


def update_Co(sim, cX_cell, cX_mem, cX_env, flux, cells, p, ignoreECM=True, update_at_mems=False):
    delta_cells = np.dot(cells.M_sum_mems, flux * cells.mem_sa) / cells.cell_vol
    if update_at_mems is False:
        cX_cell = cX_cell + delta_cells * p.dt
        cX_mem = cX_cell[cells.mem_to_cells]
    else:
        cX_mem += flux * (cells.mem_sa / (3 / 4 * cells.mem_vol)) * p.dt
        cX_cell = cX_cell + delta_cells * p.dt
    if p.is_ecm is True:
        delta_env = div_env(-flux, cells, p)
        cX_env = cX_env + delta_env * p.dt
    else:
        delta_env = -flux * (cells.mem_sa / p.vol_env)
        cX_env_o = cX_env + delta_env * p.dt
        cX_env = cX_env_o.mean()
    return (cX_cell, cX_mem, cX_env)


def nernst_planck_flux(c, gcx, gcy, gvx, gvy, ux, uy, D, z, T, p, mu=0.0):
    """
     Calculate the flux component of the Nernst-Planck equation

     Parameters
     ------------

    c:     concentration
    gcx:   concentration gradient, x component
    gcy:   concentration gradient, y component
    gvx:   voltage gradient, x component
    gvy:   voltage gradient, y component
    ux:    fluid velocity, x component
    uy:    fluid velocity, y component
    D:     diffusion constant, D
    z:     ion charge
    T:     temperature
    p:     parameters object

    Returns
    --------
    fx, fx        mass flux in x and y directions
    """
    alpha = D * z * p.q / (p.kb * T)
    fx = -D * gcx - alpha * gvx * c + ux * c - mu * c * gvx
    fy = -D * gcy - alpha * gvy * c + uy * c - mu * c * gvy
    return (fx, fy)


def div_env(flux, cells, p):
    """
    Calculates the divergence of the normal net flux component defined on a set of cell membranes
    with respect to the environmental grid spaces.

    :param flux:
    :param cells:
    :return:
    """
    if p.fast_update_ecm:
        flux_env = np.zeros(len(cells.xypts))
        flux_env[cells.map_mem2ecm] = flux
        delta_env = flux_env * cells.memSa_per_envSquare / cells.ecm_vol
    else:
        delta_env = np.dot(cells.M_divmap_mem2ecm, flux) / (p.cell_height * cells.delta**2)
    return delta_env


def gradient(F, delx, dely=None):
    if dely is None:
        dely = delx
    dF_interior_y = -(F[:-2, :] - F[2:, :]) / (2 * dely)
    dF_interior_x = -(F[:, :-2] - F[:, 2:]) / (2 * delx)
    dF_B = (F[1, :] - F[0, :]) / dely
    dF_T = (F[-1, :] - F[-2, :]) / dely
    dF_L = (F[:, 1] - F[:, 0]) / delx
    dF_R = (F[:, -1] - F[:, -2]) / delx
    dFx = np.zeros(F.shape)
    dFy = np.zeros(F.shape)
    dFx[:, 1:-1] = dF_interior_x
    dFy[1:-1, :] = dF_interior_y
    dFx[:, 0] = dF_L
    dFx[:, -1] = dF_R
    dFy[0, :] = dF_B
    dFy[-1, :] = dF_T
    return (dFx, dFy)


def diff(F, delx, axis=0):
    if axis == 1:
        dF_interior = -(F[:-2, :] - F[2:, :]) / (2 * delx)
        dF_B = -(F[1, :] - F[0, :]) / delx
        dF_T = -(F[-1, :] - F[-2, :]) / delx
        dF = np.zeros(F.shape)
        dF[1:-1, :] = dF_interior
        dF[0, :] = dF_B
        dF[-1, :] = dF_T
    elif axis == 0:
        dF_interior = -(F[:, :-2] - F[:, 2:]) / (2 * delx)
        dF_L = (F[:, 0] - F[:, 1]) / delx
        dF_R = (F[:, -2] - F[:, -1]) / delx
        dF = np.zeros(F.shape)
        dF[:, 1:-1] = dF_interior
        dF[:, 0] = dF_L
        dF[:, -1] = dF_R
    return dF


def divergence(Fx, Fy, delx, dely):
    gx = diff(Fx, delx, axis=0)
    gy = diff(Fy, dely, axis=1)
    div = gx + gy
    return div


def integrator(P, sharp=0.5):
    """
    Averages nearest neighbours of the environmental array with a weighting
    given by the "sharp" option.

    P: some 2D matrix
    sharp: weighting of the neigbouring averages; 0.5 is standard finite volume smoothing; 1.0 is no smoothing

    Thanks Sess!

    """
    F = np.zeros(P.shape)
    eP = P[:, 1:]
    wP = P[:, 0:-1]
    nP = P[1:, :]
    sP = P[0:-1, :]
    sides = (1 - sharp) / 4
    F[:, :] = sharp * P
    F[0:-1, :] += sides * nP
    F[1:, :] += sides * sP
    F[:, 0:-1] += sides * eP
    F[:, 1:] += sides * wP
    F[:, 0] = P[:, 0]
    F[:, -1] = P[:, -1]
    F[0, :] = P[0, :]
    F[-1, :] = P[-1, :]
    return F


from cells.processes import betse_normal_grn_source as qualified

clone, public = qualified.clone, qualified.public
ALIASES, OBJECTS = qualified.ALIASES, qualified.OBJECTS


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
        ionic_state=ionic_state(sim),
        balance_events=[] if core is None else clone(getattr(core, "_balance_events", [])),
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


def ionic_state(sim):
    return dict(
        cc_cells=sim.cc_cells.copy(), cc_at_mem=sim.cc_at_mem.copy(), cc_env=sim.cc_env.copy()
    )


def observe_balance(net, stage, Q, sim, tag, p):
    if not hasattr(net, "_balance_events"):
        net._balance_events = []
    net._balance_events.append(
        dict(
            stage=stage,
            tag=tag,
            Q=clone(Q),
            ionic_state=ionic_state(sim),
            boundary_state=sim.c_env_bound.copy(),
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
            charge_has_been_balanced=net.charge_has_been_balanced,
            substances_affect_charge=p.substances_affect_charge,
        )
    )


BetseSimUnstableException = molecule_source.BetseSimUnstableException
fd = SimpleNamespace(gradient=gradient, divergence=divergence, integrator=integrator)
stb = SimpleNamespace(molecule_mover=molecule_mover, no_negs=molecule_source.no_negs)


def science():
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
        derive_context=derive_context,
    )


def derive_radial(self):
    self.rads = self.mem_mids_flat - self.cell_centres[self.mem_to_cells]
    self.R_rads = np.sqrt(self.rads[:, 0] ** 2 + self.rads[:, 1] ** 2)


def derive_context(self, cells):
    D_env_weight = self.D_env[self.iNa] / self.D_env[self.iNa].max()
    self.D_env_weight = D_env_weight.reshape(cells.X.shape)
    self.D_env_weight_base = np.copy(self.D_env_weight)
    self.TJ_targets = np.hstack(
        (cells.all_bound_mem_inds, cells.interior_bound_mem_inds, cells.ecm_inds_bound_cell)
    )
    derive_radial(cells)


MATERIAL_PAIRS = (
    ("cell_mol_m3", "cc_cells"),
    ("membrane_mol_m3", "cc_at_mem"),
    ("environment_mol_m3", "cc_env"),
    ("voltage_V", "vm"),
    ("membrane_flux_mol_m2_s", "fluxes_mem"),
    ("junction_flux_mol_m2_s", "fluxes_gj"),
    ("environment_flux_x_mol_m2_s", "fluxes_env_x"),
    ("environment_flux_y_mol_m2_s", "fluxes_env_y"),
    ("junction_voltage_V", "vgj"),
    ("junction_field_source", "Egj"),
    ("gap_open", "gjopen"),
)
PARAMETERS = (
    "z",
    "Dm",
    "Do",
    "Dgj",
    "c_bound",
    "TJ_factor",
    "ignoreTJ",
    "ignoreGJ",
    "ignore_ECM_pump",
    "update_intra_conc",
    "transmem",
    "modify_time_factor",
    "Mu_mem",
    "u_mt",
    "scale_factor",
    "active_pumping",
    "ion_channel_gating",
    "change_bounds",
    "cell_clamp",
)


def material_values(sim):
    return {key: clone(getattr(sim, attr)) for key, attr in MATERIAL_PAIRS} | dict(
        junction_field_xy_source=np.column_stack((sim.E_gj_x, sim.E_gj_y))
    )


def augment(sim, cells, p, definition, ion_ids):
    p.ions_dict = {name: 1 for name in ion_ids}
    p.ions_dict.setdefault("Ca", 0)
    p.grn = SimpleNamespace(conf=clone(definition["configuration"]))
    p.grn_enabled, p.molecules_enabled, p.plot_network = True, False, False
    sim.get_ion = lambda name: ion_ids.index(name)
    sim.iNa, sim.iK, sim.iM = (sim.get_ion(name) for name in ("Na", "K", "M"))
    sim.cdl = len(cells.cell_i)
    p.fluid_flow = False
    for key in ("all_bound_mem_inds", "interior_bound_mem_inds", "ecm_inds_bound_cell"):
        setattr(cells, key, np.asarray(definition["grid_index_groups"][key], np.int64).copy())
    science()["derive_context"](sim, cells)
    return SimpleNamespace(
        sim=sim,
        cells=cells,
        p=p,
        definition=definition,
        ion_ids=ion_ids,
        phase=SimpleNamespace(sim=sim, cells=cells, p=p, kind="SIM", dyna=SimpleNamespace()),
        trace=new_trace(),
    )


def cache(ctx):
    return dict(
        kind="cells.ecm_charged_grn_owner_cache@1",
        wire=wire(ctx.sim.grn, ctx.sim),
        coefficient_fields={
            name: clone(getattr(ctx.sim, name))
            for name in ("D_env_weight", "D_env_weight_base", "TJ_targets")
        },
    )


def cold(ctx):
    ctx.sim.grn = None
    ctx.phase.kind = "INIT"
    ctx.p.substances_affect_charge = ctx.definition["cold_publish"]
    science()["initialize_owner"](ctx.sim, 0.0, ctx.phase, ctx.cells, ctx.p)
    return cache(ctx)


def restore(ctx, incoming):
    if incoming is None or incoming.get("kind") != "cells.ecm_charged_grn_owner_cache@1":
        raise ValueError("Require complete ECM GRN owner cache")
    raw = incoming["wire"]
    if "ionic_state" not in raw:
        raise ValueError("Require complete ECM charged ionic snapshot")
    if "balance_events" not in raw:
        raise ValueError("Require ECM charged compensation observations")
    if set(raw) != {
        "owner_fields",
        "core_fields",
        "molecule_fields",
        "reaction_fields",
        "modulator_fields",
        "ion_boundary_state",
        "simulator_fields",
        "ionic_state",
        "balance_events",
    }:
        raise ValueError("Require every ECM owner/cache field")
    if set(raw["molecule_fields"]) != {"X", "Y"}:
        raise ValueError("Require both configured ECM gene products")
    for values in raw["molecule_fields"].values():
        if (
            not set(PARAMETERS) | {"c_cells", "cc_at_mem", "c_env", "flux_intra", "gad_eval_string"}
            <= values.keys()
        ):
            raise ValueError("Missing source-initialized ECM gene fields")
        if values["ignore_ECM_pump"] is not True:
            raise ValueError("Preserve actual source ignore_ECM_pump default")
    api = science()
    owner = object.__new__(api["MasterOfGenes"])
    vars(owner).update(clone(raw["owner_fields"]))
    net = object.__new__(api["MasterOfNetworks"])
    vars(net).update(clone(raw["core_fields"]))
    owner.core, ctx.sim.grn = net, owner
    for attr, key, cls in (
        ("molecules", "molecule_fields", "Molecule"),
        ("reactions", "reaction_fields", "Reaction"),
        ("modulators", "modulator_fields", "Modulator"),
    ):
        objects = OrderedDict()
        for name, fields in raw[key].items():
            obj = object.__new__(api[cls])
            vars(obj).update(clone(fields))
            objects[name] = obj
        setattr(net, attr, objects)
    net.reactions_env, net.reactions_mit, net.channels, net.mit = (
        OrderedDict(),
        OrderedDict(),
        OrderedDict(),
        None,
    )
    validate_ionic_cache(ctx, raw)
    net._balance_events = clone(raw["balance_events"])
    # The current packet's ionic boundary vector remains authoritative. Gene
    # boundary scalars already travel with their complete molecule fields.
    for key, value in raw["simulator_fields"].items():
        setattr(ctx.sim, key, clone(value))
    if set(incoming["coefficient_fields"]) != {"D_env_weight", "D_env_weight_base", "TJ_targets"}:
        raise ValueError("Require owned ECM molecular grid coefficients")
    for key, value in incoming["coefficient_fields"].items():
        setattr(ctx.sim, key, clone(value))
    for attr, ionic, molecular in (
        ("cell_concs", "cc_cells", "c_cells"),
        ("mem_concs", "cc_at_mem", "cc_at_mem"),
        ("env_concs", "cc_env", "c_env"),
        ("bound_concs", "c_env_bound", "c_bound"),
    ):
        mapping = OrderedDict()
        for name, enabled in ctx.p.ions_dict.items():
            if enabled != 1:
                continue
            i = ctx.sim.get_ion(name)
            mapping[name] = api["DynamicValue"](
                lambda i=i, a=ionic: getattr(ctx.sim, a)[i],
                lambda value, i=i, a=ionic: getattr(ctx.sim, a).__setitem__(i, value),
            )
        for name in net.molecules:
            mapping[name] = api["DynamicValue"](
                lambda name=name, a=molecular: getattr(net.molecules[name], a),
                lambda value, name=name, a=molecular: setattr(net.molecules[name], a, value),
            )
        setattr(net, attr, api["DynamicValueDict"](mapping))
    net.mit_concs = None
    return net


def owner_evidence(ctx):
    return dict(
        owner_class=type(ctx.sim.grn).__name__,
        core_class=type(ctx.sim.grn.core).__name__,
        actual_core_identity=ctx.sim.grn.core is ctx.net,
        grn_enabled=ctx.p.grn_enabled,
        molecules_enabled=ctx.p.molecules_enabled,
        standalone_sim_grn=False,
    )


def before(ctx, material_declaration):
    sim, p, cells, net = ctx.sim, ctx.p, ctx.cells, ctx.net
    configured = []
    for name, obj in net.molecules.items():
        g = dict(
            enabled=obj.simple_growth,
            production_rate_mM_s=0.0 if obj.r_production is None else obj.r_production,
            decay_rate_per_s=0.0 if obj.r_decay is None else obj.r_decay,
            decay_max_per_s=0.0 if not obj.simple_growth else obj.decay_max,
            scale_factor=obj.gad_scale_factor,
        )
        configured.append(
            dict(
                name=name,
                parameters={key: clone(getattr(obj, key)) for key in PARAMETERS},
                growth=g,
            )
        )
    return dict(
        conditioned_before_model_network=True,
        ecm_normal_grn=True,
        material_declaration=clone(material_declaration),
        definition=dict(
            molecules=configured,
            grn_configuration=clone(p.grn.conf),
            reactions=clone(p.grn.conf["reactions"]),
            modulators=clone(p.grn.conf.get("modulators") or []),
        ),
        values_before=material_values(sim),
        molecule_states_before={
            name: {
                key: clone(getattr(obj, key))
                for key in ("c_cells", "cc_at_mem", "c_env", "flux_intra")
            }
            for name, obj in net.molecules.items()
        },
        cache_before=cache(ctx),
        controls_before=dict(gj_block=clone(sim.gj_block), NaKATP_block=clone(sim.NaKATP_block)),
        molecular_geometry=dict(
            owner=clone(cells.mem_to_cells),
            partner=clone(cells.nn_i),
            boundary=clone(cells.bflags_mems),
            membrane_area_m2=clone(cells.mem_sa),
            cell_volume_m3=clone(cells.cell_vol),
            gap_length_m=clone(cells.gj_len),
        ),
        dt_s=p.dt,
        F=p.F,
        R=p.R,
        q_C=p.q,
        kb_J_K=p.kb,
        membrane_thickness_m=p.tm,
        runtime_temperature_K=sim.T,
        configured_temperature_K=p.T,
        gap_open=clone(sim.gjopen),
        rho_channel=clone(sim.rho_channel),
        ion_ids=list(ctx.ion_ids),
        valence=clone(sim.zs),
        electric_x_source=clone(sim.E_env_x),
        electric_y_source=clone(sim.E_env_y),
        D_env=clone(sim.D_env),
        grid_index_groups=clone(ctx.definition["grid_index_groups"]),
        substances_affect_charge=p.substances_affect_charge,
        sharpness=p.sharpness,
        cluster_open=p.cluster_open,
        incoming_channel_current_A_m2=clone(net.extra_J_mem),
        simulator_fields_before=wire(sim.grn, sim)["simulator_fields"],
        owner=owner_evidence(ctx),
    )


def attach(ctx, material_declaration, observer=None):
    sim, p, net = ctx.sim, ctx.p, ctx.net

    def chemistry(stage, species, actual):
        ctx.trace["molecule_frames"].append(
            dict(stage=stage, species=species, values=material_values(sim), cache=cache(ctx))
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
            "cenv",
            "gcx",
            "gcy",
            "fx",
            "fy",
            "div_fa",
            "denv_multiplier",
        )
        ctx.trace["mover_frames"].append(
            dict(
                stage=stage,
                species=name,
                fields={key: clone(local.get(key)) for key in fields},
                vm=clone(actual.vm),
                vgj=clone(actual.vgj),
            )
        )

    def rhs(growth, reaction, all_rates):
        ctx.trace["rhs"] = dict(
            growth_rates=clone(growth), reaction_rates=clone(reaction), all_rates=clone(all_rates)
        )

    def control(name, value, actual):
        ctx.trace["control_writes"].append(
            dict(
                rule_id=name,
                target=net.modulators[name].target_label,
                value=clone(value),
                gj_block=clone(actual.gj_block),
                NaKATP_block=clone(actual.NaKATP_block),
            )
        )

    def dispatched(stage, actual, phase):
        ctx.trace["dispatch_stages"].append(stage)
        if stage == "clear_run_loop":
            ctx.trace["before"] = before(ctx, material_declaration)
            if observer is not None:
                observer(clone(ctx.trace["before"]))

    (
        net._observe_chem,
        net._observe_rhs,
        net._observe_control,
        net._observe_dispatch,
        p._mover_observe,
    ) = chemistry, rhs, control, dispatched, mover


def run_dispatch(ctx, material_declaration, publication, observer=None):
    ctx.p.substances_affect_charge = publication
    ctx.phase.kind = "SIM"
    ctx.net = ctx.sim.grn.core
    attach(ctx, material_declaration, observer)
    try:
        science()["dispatch"](ctx.sim, 0.0, ctx.phase, ctx.cells, ctx.p)
        ctx.trace["source_completed"] = True
    finally:
        ctx.trace.update(
            cache_after=cache(ctx),
            values_after=material_values(ctx.sim),
            controls_after=dict(
                gj_block=clone(ctx.sim.gj_block), NaKATP_block=clone(ctx.sim.NaKATP_block)
            ),
            owner_after=owner_evidence(ctx),
            completed_transports=sum(
                row["stage"] == "transport_after" for row in ctx.trace["molecule_frames"]
            ),
        )
    return ctx.trace


def _number(value, positive=False):
    return (
        type(value) in (int, float)
        and np.isfinite(value)
        and (value > 0 if positive else value >= 0)
    )


def validate_definition(definition, ids, n, m, e):
    required = {
        "owner",
        "configuration",
        "cold_publish",
        "grid_index_groups",
        "initial_controls",
        "initial_ion_boundary",
        "raw_initialization_fault",
        "scope",
    }
    if set(definition) != required or definition["owner"] != "grn":
        raise ValueError("Require a complete genuine ECM GRN declaration")
    if definition["scope"] != {
        "mitochondria": False,
        "fluid": False,
        "cuts": False,
        "standalone": False,
    }:
        raise ValueError("ECM GRN mitochondria/fluid/cuts/standalone require separate state")
    if not {"Na", "K", "M"} <= set(ids):
        raise ValueError("Require actual Na/K/M rows for ECM charged compensation")
    cfg = definition["configuration"]
    if set(cfg) - {"biomolecules", "reactions", "modulators", "time dilation factor"}:
        raise ValueError("Other ECM GRN lifecycle branches require separate state")
    if not _number(cfg.get("time dilation factor", 1.0), True):
        raise ValueError("Require positive source time dilation")
    if type(definition["cold_publish"]) is not bool:
        raise ValueError("Require an explicit ECM cold publication flag")
    rows = cfg["biomolecules"]
    if len(rows) != 2 or [row["name"] for row in rows] != ["X", "Y"]:
        raise ValueError("Require actual configured X/Y gene products")
    fault = definition["raw_initialization_fault"]
    if fault not in (
        None,
        "cell_positive_excess",
        "cell_negative_excess",
        "env_positive_excess",
        "env_negative_excess",
    ):
        raise ValueError("Undeclared ECM cold source failure")
    for row in rows:
        needed = {
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
            "growth and decay",
            "plotting",
        }
        if needed - set(row) != set() or set(row) - needed - {
            "Dgj",
            "scale factor",
            "use time dilation",
        }:
            raise ValueError("Require complete bounded ECM gene configuration")
        if row["z"] not in (-1.0, 0.0, 1.0) or row["update intracellular"] is not False:
            raise ValueError("Require bounded monovalent instant-mixing ECM products")
        if (
            any(type(row[key]) is not bool for key in ("TJ permeable", "GJ impermeable"))
            or type(row.get("use time dilation", False)) is not bool
        ):
            raise ValueError("Require explicit source transport flags")
        if not all(
            _number(row.get(key, default))
            for key, default in (
                ("cell conc", 0.0),
                ("env conc", 0.0),
                ("Dm", 0.0),
                ("Do", 0.0),
                ("Dgj", 1e-16),
                ("TJ factor", 1.0),
            )
        ) or not _number(row.get("scale factor", 1.0), True):
            raise ValueError("Require finite source concentrations and coefficients")
        if row["plotting"] != {
            "plot 2D": False,
            "animate": False,
            "autoscale colorbar": True,
            "max val": 1.0,
            "min val": 0.0,
        }:
            raise ValueError("ECM network plotting is outside this boundary")
        gad = row["growth and decay"]
        if gad is not None:
            allowed = {
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
            }
            if (
                set(gad) - allowed
                or gad["apply to"] != "all"
                or not _number(gad["production rate"])
                or not _number(gad["decay rate"])
                or not _number(gad.get("decay max", 0.0))
                or not _number(gad.get("scale factor", 1.0), True)
            ):
                raise ValueError("Require ordinary all-cell ECM gene regulation")
            for prefix in ("", "decay "):
                for sign in ("activators", "inhibitors"):
                    names = gad.get(prefix + sign)
                    if names is None:
                        continue
                    for name, km, exponent in zip(
                        names, gad["Km " + prefix + sign], gad["n " + prefix + sign], strict=True
                    ):
                        if (
                            name not in (*ids, "X", "Y")
                            or not _number(km, True)
                            or not _number(exponent, True)
                        ):
                            raise ValueError("Invalid ECM gene Hill regulator")
    if rows[0]["z"] != rows[1]["z"] or rows[0].get("scale factor", 1.0) != rows[1].get(
        "scale factor", 1.0
    ):
        raise ValueError("Preserve X-to-Y formal charge weighting")
    reactions = cfg["reactions"]
    if len(reactions) != 1:
        raise ValueError("Require one configured source X-to-Y reaction")
    reaction = reactions[0]
    if (
        reaction["name"] != "X_to_Y"
        or reaction["reaction zone"] != "cell"
        or reaction["reactants"] != ["X"]
        or reaction["products"] != ["Y"]
        or reaction["reactant multipliers"] != [1.0]
        or reaction["product multipliers"] != [1.0]
        or reaction["standard free energy"] != "None"
    ):
        raise ValueError("Require the irreversible cell-zone conversion")
    for key in ("Km reactants", "Km products"):
        if len(reaction[key]) != 1 or not _number(reaction[key][0], True):
            raise ValueError("Require positive source reaction constants")
    if not _number(reaction["max rate"]):
        raise ValueError("Require a finite source reaction rate")
    for mod in cfg.get("modulators") or []:
        allowed = {
            "name",
            "target",
            "max effect",
            "activators",
            "activator Km",
            "activator n",
            "activator zone",
            "inhibitors",
            "inhibitor Km",
            "inhibitor n",
            "inhibitor zone",
        }
        if (
            set(mod) - allowed
            or mod["target"] not in ("GJ", "Na/K-ATPase")
            or not _number(mod["max effect"])
        ):
            raise ValueError("Require bounded ion-driven ECM modulators")
        for sign in ("activator", "inhibitor"):
            names = mod.get(sign + "s")
            if names is None:
                continue
            zone = mod.get(sign + " zone", ["cell"] * len(names))
            for name, km, exponent, where in zip(
                names, mod[sign + " Km"], mod[sign + " n"], zone, strict=True
            ):
                if (
                    name not in ids
                    or not _number(km, True)
                    or not _number(exponent, True)
                    or where not in ("cell", "env")
                ):
                    raise ValueError("Invalid ECM modulator input")
    if set(definition["grid_index_groups"]) != {
        "all_bound_mem_inds",
        "interior_bound_mem_inds",
        "ecm_inds_bound_cell",
    }:
        raise ValueError("Require the three original TJ index groups")
    for group in definition["grid_index_groups"].values():
        if any(type(index) is not int or not 0 <= index < e for index in group):
            raise ValueError("Require owned in-grid TJ indices")
    if set(definition["initial_controls"]) != {"gj_block", "NaKATP_block"} or any(
        len(row) != m or not all(_number(value) for value in row)
        for row in definition["initial_controls"].values()
    ):
        raise ValueError("Require complete ECM network controls")
    if len(definition["initial_ion_boundary"]) != len(ids) or not all(
        _number(v) for v in definition["initial_ion_boundary"]
    ):
        raise ValueError("Require every original ionic boundary scalar")


def validate(definition, binding):
    if binding.kernel.fluid_flow:
        raise ValueError("ECM network fluid coupling requires separate state")
    if (
        np.max(
            binding.kernel.environment_diffusion_m2_s[
                binding.geometry_binding.current_binding.ion_ids.index("Na")
            ]
        )
        <= 0
    ):
        raise ValueError("Na ECM diffusion normalization needs a positive maximum")
    g = binding.geometry_binding.geometry
    cb = binding.geometry_binding.current_binding
    for name, charge in (("Na", 1), ("K", 1), ("M", -1)):
        if name not in cb.ion_ids or cb.kernel.valence[cb.ion_ids.index(name)] != charge:
            raise ValueError("Require actual Na(+1), K(+1), M(-1) counterion rows")
    if cb.ion_ids.index("M") in binding.kernel.moving:
        raise ValueError("Declare the compensation M row stationary")
    validate_definition(
        definition, list(cb.ion_ids), len(cb.cell_ids), len(cb.membrane_ids), int(np.prod(g.shape))
    )


def new_trace():
    return dict(
        molecule_frames=[],
        mover_frames=[],
        rhs={},
        control_writes=[],
        dispatch_stages=[],
        source_completed=False,
    )


def validate_ionic_cache(ctx, raw):
    if not isinstance(raw.get("ionic_state"), Mapping) or set(raw["ionic_state"]) != {
        "cc_cells",
        "cc_at_mem",
        "cc_env",
    }:
        raise ValueError("Require complete ECM charged ionic snapshot")
    for key, value in raw["ionic_state"].items():
        array = np.asarray(value)
        if (
            array.shape != getattr(ctx.sim, key).shape
            or array.dtype.kind not in "fiu"
            or not np.isfinite(array).all()
        ):
            raise ValueError("Require original E-grid and M-membrane ionic cache shapes")
    if not isinstance(raw.get("balance_events"), (list, tuple)):
        raise ValueError("Require ECM charged compensation observations")
