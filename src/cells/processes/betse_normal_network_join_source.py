# ruff: noqa: B007, B905, E501
"""Literal late network feedback and explicitly empty chemistry.

Native modulator expressions execute here. Existing standalone components validate
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
from cells.processes import betse_normal_ion_join as ions

logs = SimpleNamespace(log_info=lambda *_: None, log_warning=lambda *_: None)
tex_val = str
BetseSimConfException = ValueError
stb = SimpleNamespace(no_negs=calcium_source._no_negs)


class _LiteralNetwork:
    def read_reactions(self, config_reactions, sim, cells, p):
        logs.log_info("Reading reaction input data...")
        self.reactions = OrderedDict({})
        self.reactions_env = OrderedDict({})
        if self.mit_enabled is True:
            self.reactions_mit = OrderedDict({})
        for q, react_dic in enumerate(config_reactions):
            name = str(react_dic["name"])
            zone = react_dic["reaction zone"]
            if zone == "cell":
                self.reactions[name] = Reaction(sim, cells, p)
                obj = self.reactions[name]
            elif zone == "mit" and self.mit_enabled is True:
                self.reactions_mit[name] = Reaction(sim, cells, p)
                obj = self.reactions_mit[name]
            elif zone == "env":
                self.reactions_env[name] = Reaction(sim, cells, p)
                obj = self.reactions_env[name]
            else:
                logs.log_warning("---------------------------------------------------------------")
                logs.log_warning(
                    "Reaction {} defined on inappropriate zone (or mit not enabled)".format(name)
                )
                logs.log_warning("Reverting this reaction to the 'cell' zone!")
                logs.log_warning("---------------------------------------------------------------")
                self.reactions[name] = Reaction(sim, cells, p)
                obj = self.reactions[name]
            obj.name = name
            obj.reaction_zone = react_dic["reaction zone"]
            obj.reactants_list = react_dic["reactants"]
            obj.reactants_coeff = react_dic["reactant multipliers"]
            obj.products_list = react_dic["products"]
            obj.products_coeff = react_dic["product multipliers"]
            obj.Km_reactants_list = react_dic["Km reactants"]
            obj.Km_products_list = react_dic["Km products"]
            obj.vmax = float(react_dic["max rate"])
            obj.delta_Go = react_dic["standard free energy"]
            if obj.delta_Go == "None":
                obj.delta_Go = None
            else:
                obj.delta_Go = float(obj.delta_Go)
            obj.reaction_activators_list = react_dic.get("reaction activators", None)
            obj.reaction_activators_Km = react_dic.get("activator Km", None)
            obj.reaction_activators_n = react_dic.get("activator n", None)
            obj.reaction_activators_zone = react_dic.get("activator zone", None)
            obj.reaction_inhibitors_list = react_dic.get("reaction inhibitors", None)
            obj.reaction_inhibitors_Km = react_dic.get("inhibitor Km", None)
            obj.reaction_inhibitors_n = react_dic.get("inhibitor n", None)
            obj.reaction_inhibitors_zone = react_dic.get("inhibitor zone", None)
            obj.reaction_activators_zone, obj.reaction_inhibitors_zone = self.default_zones(
                obj.reaction_activators_zone,
                obj.reaction_inhibitors_zone,
                obj.reaction_activators_list,
                obj.reaction_inhibitors_list,
            )
            if self.mit_enabled:
                obj.mit_enabled = True
            else:
                obj.mit_enabled = False
        for name in self.reactions:
            msg = "Including the cell-zone reaction: {}".format(name)
            logs.log_info(msg)
        if self.mit_enabled is True:
            for name in self.reactions_mit:
                msg = "Including the mit-zone reaction: {}".format(name)
                logs.log_info(msg)

    def read_modulators(self, config_modulators, sim, cells, p):
        logs.log_info("Reading modulator input data...")
        self.modulators = OrderedDict({})
        for q, mod_dic in enumerate(config_modulators):
            name = str(mod_dic["name"])
            self.modulators[name] = Modulator()
            obj = self.modulators[name]
            obj.target_label = str(mod_dic["target"])
            obj.target_ion = mod_dic.get("target ion", None)
            obj.max_val = float(mod_dic["max effect"])
            obj.modulator_activators_list = mod_dic.get("activators", None)
            obj.modulator_activators_Km = mod_dic.get("activator Km", None)
            obj.modulator_activators_n = mod_dic.get("activator n", None)
            obj.modulator_activators_zone = mod_dic.get("activator zone", None)
            obj.modulator_inhibitors_list = mod_dic.get("inhibitors", None)
            obj.modulator_inhibitors_Km = mod_dic.get("inhibitor Km", None)
            obj.modulator_inhibitors_n = mod_dic.get("inhibitor n", None)
            obj.modulator_inhibitors_zone = mod_dic.get("inhibitor zone", None)
            obj.modulator_activators_zone, obj.modulator_inhibitors_zone = self.default_zones(
                obj.modulator_activators_zone,
                obj.modulator_inhibitors_zone,
                obj.modulator_activators_list,
                obj.modulator_inhibitors_list,
            )
            obj.init_modulator(sim, cells, p)
            a_list = obj.modulator_activators_list
            Km_a_list = obj.modulator_activators_Km
            n_a_list = obj.modulator_activators_n
            zone_a = obj.modulator_activators_zone
            i_list = obj.modulator_inhibitors_list
            Km_i_list = obj.modulator_inhibitors_Km
            n_i_list = obj.modulator_inhibitors_n
            zone_i = obj.modulator_inhibitors_zone
            tex_vars = []
            if obj.target_label == "TJ":
                r_zone = "env"
            else:
                r_zone = "mem"
            all_alpha, alpha_tex, tex_vars = self.get_influencers(
                a_list,
                Km_a_list,
                n_a_list,
                i_list,
                Km_i_list,
                n_i_list,
                tex_list=tex_vars,
                reaction_zone=r_zone,
                zone_tags_a=zone_a,
                zone_tags_i=zone_i,
                in_mem_tag=False,
            )
            obj.alpha_eval_string = "(" + all_alpha + ")"
        for name in self.modulators:
            msg = "Including the modulation: {}".format(name)
            logs.log_info(msg)

    def write_growth_and_decay(self):
        logs.log_info("Writing substance growth/decay equations...")
        for mol_name in self.molecules:
            if self.molecules[mol_name].simple_growth is True:
                gad_tex_var_list = []
                cc = "(self.molecules['{}'].c_cells/self.molecules['{}'].gad_scale_factor)".format(
                    mol_name, mol_name
                )
                cc_tex = "[%s]" % mol_name
                a_list = self.molecules[mol_name].growth_activators_list
                Km_a_list = self.molecules[mol_name].growth_activators_Km
                n_a_list = self.molecules[mol_name].growth_activators_n
                zone_a = self.molecules[mol_name].growth_activators_zone
                i_list = self.molecules[mol_name].growth_inhibitors_list
                Km_i_list = self.molecules[mol_name].growth_inhibitors_Km
                n_i_list = self.molecules[mol_name].growth_inhibitors_n
                zone_i = self.molecules[mol_name].growth_inhibitors_zone
                all_alpha, alpha_tex, gad_tex_var_list = self.get_influencers(
                    a_list,
                    Km_a_list,
                    n_a_list,
                    i_list,
                    Km_i_list,
                    n_i_list,
                    tex_list=gad_tex_var_list,
                    reaction_zone="cell",
                    zone_tags_a=zone_a,
                    zone_tags_i=zone_i,
                    in_mem_tag=False,
                )
                dec_gad_tex_var_list = []
                dec_a_list = self.molecules[mol_name].decay_activators_list
                dec_Km_a_list = self.molecules[mol_name].decay_activators_Km
                dec_n_a_list = self.molecules[mol_name].decay_activators_n
                dec_zone_a = self.molecules[mol_name].decay_activators_zone
                dec_i_list = self.molecules[mol_name].decay_inhibitors_list
                dec_Km_i_list = self.molecules[mol_name].decay_inhibitors_Km
                dec_n_i_list = self.molecules[mol_name].decay_inhibitors_n
                dec_zone_i = self.molecules[mol_name].decay_inhibitors_zone
                dec_all_alpha, dec_alpha_tex, dec_gad_tex_var_list = self.get_influencers(
                    dec_a_list,
                    dec_Km_a_list,
                    dec_n_a_list,
                    dec_i_list,
                    dec_Km_i_list,
                    dec_n_i_list,
                    tex_list=dec_gad_tex_var_list,
                    reaction_zone="cell",
                    zone_tags_a=dec_zone_a,
                    zone_tags_i=dec_zone_i,
                    in_mem_tag=False,
                )
                mod_funk = "(self.molecules['{}'].growth_mod_function_cells)".format(mol_name)
                r_prod = "(self.molecules['{}'].r_production*(self.molecules['{}'].modify_time_factor))".format(
                    mol_name, mol_name
                )
                r_decay = "(self.molecules['{}'].r_decay*(self.molecules['{}'].modify_time_factor))".format(
                    mol_name, mol_name
                )
                dec_max = "(self.molecules['{}'].decay_max*(self.molecules['{}'].modify_time_factor))".format(
                    mol_name, mol_name
                )
                gad_eval_string = (
                    mod_funk
                    + "*"
                    + r_prod
                    + "*"
                    + all_alpha
                    + "-"
                    + r_decay
                    + "*"
                    + cc
                    + "-"
                    + dec_max
                    + "*"
                    + dec_all_alpha
                    + "*"
                    + cc
                )
                r_prod_tex = "r_{%s}^{max}\\," % mol_name
                r_dec_tex = " - \\delta_{%s}\\," % mol_name
                gad_tex_initial = "r_{%s}=" % mol_name
                gad_tex_string = gad_tex_initial + r_prod_tex + alpha_tex + r_dec_tex + cc_tex
                rpval = tex_val(self.molecules[mol_name].r_production)
                r_p_tex = "r_{%s}^{max} & =" % mol_name
                r_p_tex += rpval
                rdval = tex_val(self.molecules[mol_name].r_decay)
                r_d_tex = "\\delta_{%s} & =" % mol_name
                r_d_tex += rdval
                gad_tex_var_list.append(r_p_tex)
                gad_tex_var_list.append(r_d_tex)
                gad_eval_string_growth = all_alpha
                gad_eval_string_decay = r_decay + "*" + cc
                self.molecules[mol_name].gad_eval_string = gad_eval_string
                self.molecules[mol_name].gad_eval_string_growth = gad_eval_string_growth
                self.molecules[mol_name].gad_eval_string_decay = gad_eval_string_decay
                self.molecules[mol_name].gad_tex_string = gad_tex_string
                tex_params = "\\begin{aligned}"
                for i, tex_str in enumerate(gad_tex_var_list):
                    tex_params += tex_str
                    if i < len(gad_tex_var_list) - 1:
                        tex_params += "\\\\"
                    else:
                        tex_params += "\\end{aligned}"
                self.molecules[mol_name].gad_tex_vars = tex_params
            else:
                self.molecules[mol_name].gad_eval_string = "np.zeros(sim.cdl)"
                self.molecules[mol_name].gad_eval_string_growth = "np.zeros(sim.cdl)"
                self.molecules[mol_name].gad_eval_string_decay = "np.zeros(sim.cdl)"
                self.molecules[mol_name].gad_tex_string = ""
                self.molecules[mol_name].gad_tex_vars = ""

    def write_reactions(self):
        logs.log_info("Writing reaction equations for cell zone...")
        for reaction_name in self.reactions:
            rea_tex_var_list = []
            reactant_names = self.reactions[reaction_name].reactants_list
            reactant_coeff = self.reactions[reaction_name].reactants_coeff
            reactant_Km = self.reactions[reaction_name].Km_reactants_list
            product_names = self.reactions[reaction_name].products_list
            product_coeff = self.reactions[reaction_name].products_coeff
            product_Km = self.reactions[reaction_name].Km_products_list
            a_list = self.reactions[reaction_name].reaction_activators_list
            Km_a_list = self.reactions[reaction_name].reaction_activators_Km
            n_a_list = self.reactions[reaction_name].reaction_activators_n
            zone_a = self.reactions[reaction_name].reaction_activators_zone
            i_list = self.reactions[reaction_name].reaction_inhibitors_list
            Km_i_list = self.reactions[reaction_name].reaction_inhibitors_Km
            n_i_list = self.reactions[reaction_name].reaction_inhibitors_n
            zone_i = self.reactions[reaction_name].reaction_inhibitors_zone
            r_zone = self.reactions[reaction_name].reaction_zone
            numo_string_Q = "("
            denomo_string_Q = "("
            numo_tex_Q = ""
            deno_tex_Q = ""
            for i, (name, coeff) in enumerate(zip(reactant_names, reactant_coeff)):
                tex_name = name
                denomo_string_Q += "(1.0e-3*self.cell_concs['{}']".format(name)
                denomo_string_Q += "**{})".format(coeff)
                deno_tex_Q += "[%s]^{%.1f}" % (tex_name, coeff)
                if i < len(reactant_names) - 1:
                    denomo_string_Q += "*"
                    deno_tex_Q += "\\,"
                else:
                    denomo_string_Q += ")"
            for i, (name, coeff) in enumerate(zip(product_names, product_coeff)):
                tex_name = name
                numo_string_Q += "(1.0e-3*self.cell_concs['{}']".format(name)
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
                numo_string_r = "((self.cell_concs['{}']/{})**{})".format(name, Km, n)
                denomo_string_r = "(1 + (self.cell_concs['{}']/{})**{})".format(name, Km, n)
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
                numo_string_p = "((self.cell_concs['{}']/{})**{})".format(name, Km, n)
                denomo_string_p = "(1 + (self.cell_concs['{}']/{})**{})".format(name, Km, n)
                term = "(" + numo_string_p + "/" + denomo_string_p + ")"
                cc_tex = "\\left(\\frac{[%s]}{K_{%s_r}^{%s}}\\right)" % (
                    tex_name,
                    reaction_name,
                    tex_name,
                )
                tex_term = "\\left(\\frac{%s}{1 + %s}\\right)" % (cc_tex, cc_tex)
                backward_coeff += term
                bwd_coeff_tex += tex_term
                if self.reactions[reaction_name].delta_Go is not None:
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
            if self.reactions[reaction_name].delta_Go is not None:
                Keqm = "(np.exp(-self.reactions['{}'].delta_Go / (p.R * sim.T)))".format(
                    reaction_name
                )
                Keqm_tex = "exp\\left(-\\frac{deltaG_{%s}^{o}}{R\\,T}\\right)" % reaction_name
                gval = tex_val(self.reactions[reaction_name].delta_Go)
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
            vmax = "self.reactions['{}'].vmax".format(reaction_name)
            if self.reactions[reaction_name].delta_Go is not None:
                reaction_eval_string = (
                    vmax
                    + "*"
                    + all_alpha
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
            if self.reactions[reaction_name].delta_Go is not None:
                reaction_tex_string = (
                    r_main
                    + r_tex
                    + "\\,"
                    + alpha_tex
                    + "\\,\\left("
                    + "1.0"
                    + "-"
                    + reversed_term_tex
                    + "\\,"
                    + "\\right)"
                )
            else:
                reaction_tex_string = r_main + r_tex + "\\," + alpha_tex + "\\," + fwd_coeff_tex
            rval = tex_val(self.reactions[reaction_name].vmax)
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
            self.reactions[reaction_name].reaction_tex_vars = tex_params
            self.reactions[reaction_name].reaction_eval_string = reaction_eval_string
            self.reactions[reaction_name].reaction_tex_string = reaction_tex_string

    def create_reaction_matrix(self):
        logs.log_info("Writing reaction network matrix for cell zone...")
        n_reacts = len(self.molecules) + len(self.reactions)
        n_mols = len(self.cell_concs)
        n_subs = len(self.molecules)
        self.reaction_matrix = np.zeros((n_mols, n_reacts))
        molecule_keys = list(self.cell_concs.keys())
        for i, name in enumerate(self.molecules):
            jj = molecule_keys.index(name)
            self.reaction_matrix[jj, i] += 1
        for jo, reaction_name in enumerate(self.reactions):
            j = jo + n_subs
            for react_name, coeff in zip(
                self.reactions[reaction_name].reactants_list,
                self.reactions[reaction_name].reactants_coeff,
            ):
                i = molecule_keys.index(react_name)
                self.reaction_matrix[i, j] += -coeff
            for prod_name, coeff in zip(
                self.reactions[reaction_name].products_list,
                self.reactions[reaction_name].products_coeff,
            ):
                i = molecule_keys.index(prod_name)
                self.reaction_matrix[i, j] += coeff

    def clear_run_loop(self, sim):
        self.extra_rho_cells = np.zeros(sim.cdl)
        self.extra_rho_env = np.zeros(sim.edl)
        self.extra_rho_mit = np.zeros(sim.cdl)
        self.extra_J_mem = np.zeros(sim.mdl)
        self.extra_Jenv_x = np.zeros(sim.edl)
        self.extra_Jenv_y = np.zeros(sim.edl)

    def run_loop(self, phase, t):
        cells = phase.cells
        p = phase.p
        sim = phase.sim
        gad_rates_o = []
        gad_targs = []
        init_rates = []
        gad_rates = []
        globalo = globals()
        localo = locals()
        for mol in self.molecules:
            obj = self.molecules[mol]
            obj.update_intra(sim, cells, p)
            gad_rates_o.append(eval(self.molecules[mol].gad_eval_string, globalo, localo))
            gad_targs.append(self.molecules[mol].growth_targets_cell)
            init_rates.append(np.zeros(sim.cdl))
        for mat, trgs, rts in zip(init_rates, gad_targs, gad_rates_o):
            mat[trgs] = rts[trgs]
            gad_rates.append(mat)
        gad_rates = np.asarray(gad_rates)
        self.reaction_rates = np.asarray(
            [
                eval(self.reactions[rn].reaction_eval_string, globalo, localo)
                for rn in self.reactions
            ]
        )
        if len(self.reaction_rates) > 0:
            all_rates = np.vstack((gad_rates, self.reaction_rates))
        else:
            all_rates = gad_rates
        self.delta_conc = np.dot(self.reaction_matrix, all_rates)
        if self.mit_enabled and len(self.reactions_mit) > 0:
            self.reaction_rates_mit = np.asarray(
                [
                    eval(self.reactions_mit[rn].reaction_eval_string, globalo, localo)
                    for rn in self.reactions_mit
                ]
            )
            self.delta_conc_mit = np.dot(self.reaction_matrix_mit, self.reaction_rates_mit)
        if len(self.reactions_env) > 0:
            self.reaction_rates_env = np.asarray(
                [
                    eval(self.reactions_env[rn].reaction_eval_string, globalo, localo)
                    for rn in self.reactions_env
                ]
            )
            self.delta_conc_env = np.dot(self.reaction_matrix_env, self.reaction_rates_env)
        else:
            self.delta_conc_env = None
        if self.delta_conc_env is not None:
            for name_env, deltae in zip(self.env_concs, self.delta_conc_env):
                conce = self.env_concs[name_env]
                self.env_concs[name_env] = conce + deltae * p.dt
        for ii, (name, deltac) in enumerate(zip(self.cell_concs, self.delta_conc)):
            conco = self.cell_concs[name]
            if name not in p.ions_dict:
                obj = self.molecules[name]
            else:
                obj = None
            self.cell_concs[name] = conco + deltac * p.dt
            if obj is not None:
                if obj.active_pumping:
                    obj.pump(sim, cells, p)
                if obj.ion_channel_gating:
                    obj.gating_mod = eval(obj.gating_mod_eval_string, globalo, localo)
                    obj.gating(sim, cells, p)
                if obj.change_bounds and phase.kind:
                    obj.update_boundary(t, p)
                if obj.cell_clamp:
                    obj.cell_clamp_method(t, p, cells)
                obj.transport(sim, cells, p)
                stb.no_negs(obj.c_cells)
                stb.no_negs(obj.c_env)
                if p.substances_affect_charge:
                    self.extra_rho_cells[:] += p.F * obj.c_cells * obj.z * obj.scale_factor
                    self.extra_J_mem[:] += (
                        -obj.z * obj.f_mem * p.F * obj.scale_factor
                        + obj.z * obj.f_gj * p.F * obj.scale_factor
                    )
                    if p.is_ecm:
                        self.extra_rho_env[:] += p.F * obj.c_env * obj.z * obj.scale_factor
                        self.extra_Jenv_x += obj.fenvx.ravel() * obj.z * p.F * obj.scale_factor
                        self.extra_Jenv_y += obj.fenvy.ravel() * obj.z * p.F * obj.scale_factor
            if self.mit_enabled and len(self.reactions_mit) > 0:
                concm = self.mit_concs[name]
                self.mit_concs[name] = concm + self.delta_conc_mit[ii] * p.dt
                stb.no_negs(self.mit_concs[name])
            if self.mit_enabled and obj is not None:
                self.extra_rho_mit[:] += p.F * obj.c_mit * obj.z
        self.energy_charge(sim)
        if p.substances_affect_charge:
            sim.extra_rho_cells = self.extra_rho_cells
            sim.extra_rho_env = self.extra_rho_env
            sim.extra_J_mem = self.extra_J_mem
            sim.extra_Jenv_x = self.extra_Jenv_x
            sim.extra_Jenv_y = self.extra_Jenv_y
        if self.mit_enabled:
            self.mit.extra_rho = self.extra_rho_mit[:]
            self.mit.update(sim, cells, p)

    def run_loop_modulators(self, sim, cells, p):
        globalo = globals()
        localo = locals()
        for i, name in enumerate(self.modulators):
            obj = self.modulators[name]
            modulator = obj.max_val * eval(obj.alpha_eval_string, globalo, localo)
            if obj.target_label == "GJ":
                sim.gj_block = modulator
            elif obj.target_label == "Na/K-ATPase":
                sim.NaKATP_block = modulator
            elif obj.target_label == "TJ":
                if obj.ion_i is None:
                    sim.TJ_modulator[:, sim.TJ_targets] = modulator[sim.TJ_targets]
                else:
                    sim.TJ_modulator[obj.ion_i][sim.TJ_targets] = modulator[sim.TJ_targets]
            else:
                raise BetseSimConfException(
                    "You have requested a sim modulator that is not available. Available choices are: 'gj', 'Na/K-ATPase', 'H/K-ATPase', and 'V-ATPase', 'Ca-ATPase', and 'Na/Ca-Exch' "
                )
            self._observe_control(name, modulator, sim)

    def energy_charge(self, sim):
        if "AMP" in self.molecules:
            numo = self.cell_concs["ATP"] + 0.5 * self.cell_concs["ADP"]
            denomo = self.cell_concs["ATP"] + self.cell_concs["ADP"] + self.cell_concs["AMP"]
            self.chi = numo / denomo
        else:
            self.chi = np.zeros(sim.cdl)

    def default_zones(self, zone_tags_a, zone_tags_i, a_list, i_list):
        if zone_tags_a is None or zone_tags_a == "None" or len(zone_tags_a) == 0:
            if a_list is not None and a_list != "None" and (len(a_list) > 0):
                zone_tags_a = ["cell" for x in a_list]
        if zone_tags_i is None or zone_tags_i == "None" or len(zone_tags_i) == 0:
            if i_list is not None and i_list != "None" and (len(i_list) > 0):
                zone_tags_i = ["cell" for x in i_list]
        return (zone_tags_a, zone_tags_i)

    def get_influencers(
        self,
        a_list,
        Km_a_list,
        n_a_list,
        i_list,
        Km_i_list,
        n_i_list,
        tex_list=None,
        reaction_zone="cell",
        zone_tags_a=None,
        zone_tags_i=None,
        in_mem_tag=False,
        max_activators=None,
        max_inhibitors=None,
    ):
        if tex_list is None:
            tex_list = []
        zone_tags_a, zone_tags_i = self.default_zones(zone_tags_a, zone_tags_i, a_list, i_list)
        activator_alpha = "("
        inhibitor_alpha = "("
        activator_alpha_tex = ""
        inhibitor_alpha_tex = ""
        direct_terms_list = []
        direct_terms_tex = []
        direct_term_alpha = "("
        direct_term_alpha_tex = ""
        if reaction_zone == "cell":
            dl = "np.ones(sim.cdl))"
        elif reaction_zone == "mem":
            dl = "np.ones(sim.mdl))"
        elif reaction_zone == "mit":
            dl = "np.ones(sim.cdl))"
        elif reaction_zone == "env":
            dl = "np.ones(sim.edl))"
        else:
            raise BetseSimConfException("Reaction zone requested not an existing option!")
        if max_activators is None and a_list != "None" and (a_list is not None):
            max_activators = np.zeros(len(a_list))
        if max_inhibitors is None and i_list != "None" and (i_list is not None):
            max_inhibitors = np.zeros(len(i_list))
        if a_list is not None and a_list != "None" and (len(a_list) > 0):
            independent_terms = []
            independent_terms_tex = []
            for i, (name, Kmo, n, zone_tag) in enumerate(
                zip(a_list, Km_a_list, n_a_list, zone_tags_a)
            ):
                if name.endswith("*"):
                    name = name[:-1]
                    vs_request = True
                else:
                    vs_request = False
                independence_tag = False
                direct_tag = False
                if name.endswith("!"):
                    name = name[:-1]
                    independence_tag = True
                elif name.endswith("&"):
                    name = name[:-1]
                    direct_tag = True
                if in_mem_tag is True and vs_request is True:
                    za = self.zmol[name]
                    if za != 0.0:
                        msg = "Vmem-sensitive gating used for activator: " + name
                        logs.log_info(msg)
                        Kmc = "({}*np.exp(-(sim.vm*{}*p.F)/(p.R*p.T)))".format(Kmo, za)
                        Kme = "({}*np.exp((sim.vm*{}*p.F)/(p.R*p.T)))".format(Kmo, za)
                    else:
                        Kmc = "{}".format(Kmo)
                        Kme = "{}".format(Kmo)
                else:
                    Kmc = "{}".format(Kmo)
                    Kme = "{}".format(Kmo)
                numo_string_a = ""
                denomo_string_a = ""
                direct_string_a = ""
                if reaction_zone == "cell":
                    if zone_tag == "cell":
                        numo_string_a += "((self.cell_concs['{}']/{})**{})".format(name, Kmc, n)
                        denomo_string_a += "(1 + (self.cell_concs['{}']/{})**{})".format(
                            name, Kmc, n
                        )
                        direct_string_a += "self.cell_concs['{}']".format(name)
                        tex_name = name
                    elif zone_tag == "env":
                        tex_name = name + "_{env}"
                        numo_string_a += (
                            "((self.env_concs['{}'][cells.map_cell2ecm]/{})**{})".format(
                                name, Kme, n
                            )
                        )
                        denomo_string_a += (
                            "(1 + (self.env_concs['{}'][cells.map_cell2ecm]/{})**{})".format(
                                name, Kme, n
                            )
                        )
                        direct_string_a += "self.env_concs['{}'][cells.map_cell2ecm]".format(name)
                elif reaction_zone == "mem":
                    if zone_tag == "cell":
                        numo_string_a += "((self.mem_concs['{}']/{})**{})".format(name, Kmc, n)
                        denomo_string_a += "(1 + (self.mem_concs['{}']/{})**{})".format(
                            name, Kmc, n
                        )
                        direct_string_a += "self.mem_concs['{}']".format(name)
                        tex_name = name
                    elif zone_tag == "env":
                        tex_name = name + "_{env}"
                        numo_string_a += (
                            "((self.env_concs['{}'][cells.map_mem2ecm]/{})**{})".format(
                                name, Kme, n
                            )
                        )
                        denomo_string_a += (
                            "(1 + (self.env_concs['{}'][cells.map_mem2ecm]/{})**{})".format(
                                name, Kme, n
                            )
                        )
                        direct_string_a += "self.env_concs['{}'][cells.map_mem2ecm]".format(name)
                elif reaction_zone == "mit":
                    tex_name = name + "_{mit}"
                    numo_string_a += "((self.mit_concs['{}']/{})**{})".format(name, Kmo, n)
                    denomo_string_a += "(1 + (self.mit_concs['{}']/{})**{})".format(name, Kmo, n)
                    direct_string_a += "self.mit_concs['{}']".format(name)
                elif reaction_zone == "env":
                    if zone_tag == "cell":
                        tex_name = name
                        numo_string_a += "1"
                        denomo_string_a += "1"
                        direct_string_a += "1"
                    elif zone_tag == "env":
                        tex_name = name + "_{env}"
                        numo_string_a += "((self.env_concs['{}']/{})**{})".format(name, Kme, n)
                        denomo_string_a += "(1 + (self.env_concs['{}']/{})**{})".format(
                            name, Kme, n
                        )
                        direct_string_a += "self.env_concs['{}']".format(name)
                else:
                    raise BetseSimConfException(
                        "You've asked for a reaction zonethat doesn't exist. Enable mitochondria or ensure all reaction and transporter zones are 'cell' or 'env'."
                    )
                numo_tex_a = "\\left(\\frac{[%s]}{K_{%s}^{a}}\\right)^{n_{%s}^{a}}" % (
                    tex_name,
                    tex_name,
                    tex_name,
                )
                denomo_tex_a = "1+\\left(\\frac{[%s]}{K_{%s}^{a}}\\right)^{n_{%s}^{a}}" % (
                    tex_name,
                    tex_name,
                    tex_name,
                )
                direct_tex_a = "\\[%s]" % tex_name
                term = "(" + numo_string_a + "/" + denomo_string_a + ")"
                tex_term = "\\left(\\frac{%s}{%s}\\right)" % (numo_tex_a, denomo_tex_a)
                kval = tex_val(Kmo)
                Ka_tex = "Ko_{%s}^{a} & =" % tex_name
                Ka_tex += kval
                nval = tex_val(n)
                n_a_tex = "n_{%s}^{a} & =" % tex_name
                n_a_tex += nval
                tex_list.append(Ka_tex)
                tex_list.append(n_a_tex)
                if independence_tag is False and direct_tag is False:
                    activator_alpha += term
                    activator_alpha_tex += tex_term
                elif independence_tag is True:
                    independent_terms.append(term)
                    independent_terms_tex.append(tex_term)
                elif direct_tag is True:
                    direct_terms_list.append(direct_string_a)
                    direct_terms_tex.append(direct_tex_a)
                if i < len(a_list) - 1 and direct_tag is False and (independence_tag is False):
                    activator_alpha += "*"
                    activator_alpha_tex += "\\,"
                elif i >= len(a_list) - 1:
                    for indt, indtex in zip(independent_terms, independent_terms_tex):
                        if activator_alpha == "(":
                            activator_alpha = "(1"
                            activator_alpha_tex = "1"
                        elif activator_alpha.endswith("*"):
                            activator_alpha = activator_alpha[:-1]
                        activator_alpha += "+" + indt
                        activator_alpha_tex += "+" + indtex
                    if activator_alpha.endswith("*"):
                        activator_alpha = activator_alpha[:-1]
                    activator_alpha += ")"
                    activator_alpha_tex += "\\,"
        else:
            activator_alpha += dl
        if i_list is not None and i_list != "None" and (len(i_list) > 0):
            for i, (name, Kmo, n, zone_tag, max_i) in enumerate(
                zip(i_list, Km_i_list, n_i_list, zone_tags_i, max_inhibitors)
            ):
                if max_i != 0.0 and max_i is not None:
                    maxI = str(max_i)
                else:
                    maxI = "0.0"
                if name.endswith("*"):
                    name = name[:-1]
                    vs_request = True
                else:
                    vs_request = False
                direct_tag = False
                if name.endswith("!"):
                    name = name[:-1]
                elif name.endswith("&"):
                    name = name[:-1]
                    direct_tag = True
                if in_mem_tag is True and vs_request is True:
                    zi = self.zmol[name]
                    msg = "Vmem-sensitive gating used for inhibitor: " + name
                    logs.log_info(msg)
                    Kmc = "({}*np.exp(-(sim.vm*{}*p.F)/(p.R*p.T)))".format(Kmo, zi)
                    Kme = "({}*np.exp((sim.vm*{}*p.F)/(p.R*p.T)))".format(Kmo, zi)
                else:
                    Kmc = "{}".format(Kmo)
                    Kme = "{}".format(Kmo)
                numo_string_i = ""
                denomo_string_i = ""
                direct_string_i = ""
                if maxI == "0.0":
                    numo_string_i = "1"
                else:
                    numo_string_i += "(1" + "-" + maxI + ")"
                if reaction_zone == "cell":
                    if zone_tag == "cell":
                        tex_name = name
                        denomo_string_i += "(1 + (self.cell_concs['{}']/{})**{})".format(
                            name, Kmc, n
                        )
                        direct_string_i += "-self.cell_concs['{}']".format(name)
                    elif zone_tag == "env":
                        tex_name = name + "_{env}"
                        denomo_string_i += (
                            "(1 + (self.env_concs['{}'][cells.map_cell2ecm]/{})**{})".format(
                                name, Kme, n
                            )
                        )
                        direct_string_i += "-self.env_concs['{}'][cells.map_cell2ecm]".format(name)
                elif reaction_zone == "mem":
                    if zone_tag == "cell":
                        tex_name = name
                        denomo_string_i += "(1 + (self.mem_concs['{}']/{})**{})".format(
                            name, Kmc, n
                        )
                        direct_string_i += "-self.mem_concs['{}']".format(name)
                    elif zone_tag == "env":
                        tex_name = name + "_{env}"
                        denomo_string_i += (
                            "(1 + (self.env_concs['{}'][cells.map_mem2ecm]/{})**{})".format(
                                name, Kme, n
                            )
                        )
                        direct_string_i += "-self.env_concs['{}'][cells.map_mem2ecm]".format(name)
                elif reaction_zone == "mit":
                    tex_name = name + "_{mit}"
                    denomo_string_i += "(1 + (self.mit_concs['{}']/{})**{})".format(name, Kmo, n)
                    direct_string_i += "-self.mit_concs['{}']".format(name)
                elif reaction_zone == "env":
                    if zone_tag == "cell":
                        tex_name = name
                        denomo_string_i += "1"
                        direct_string_i += "1"
                    elif zone_tag == "env":
                        tex_name = name + "_{env}"
                        denomo_string_i += "(1 + (self.env_concs['{}']/{})**{})".format(
                            name, Kme, n
                        )
                        direct_string_i += "-self.env_concs['{}']".format(name)
                if maxI == "0.0":
                    numo_tex_i = "1"
                else:
                    numo_tex_i = "(1" + "-" + maxI + ")"
                denomo_tex_i = "1+\\left(\\frac{[%s]}{K_{%s}^{i}}\\right)^{n_{%s}^{i}}" % (
                    tex_name,
                    tex_name,
                    tex_name,
                )
                direct_tex_i = "[%s]" % tex_name
                if maxI == "0.0":
                    term = "(" + numo_string_i + "/" + denomo_string_i + ")"
                else:
                    term = "(" + numo_string_i + "/" + denomo_string_i + ")" + "+" + maxI
                if maxI == "0.0":
                    tex_term = "\\left(\\frac{%s}{%s}\\right)" % (numo_tex_i, denomo_tex_i)
                else:
                    tex_term = "\\left(\\frac{%s}{%s}\\right) + {%s}" % (
                        numo_tex_i,
                        denomo_tex_i,
                        maxI,
                    )
                kval = tex_val(Kmo)
                Ki_tex = "Ko_{%s}^{i} & =" % tex_name
                Ki_tex += kval
                nval = tex_val(n)
                n_i_tex = "n_{%s}^{i} & =" % tex_name
                n_i_tex += nval
                tex_list.append(Ki_tex)
                tex_list.append(n_i_tex)
                if direct_tag is False:
                    inhibitor_alpha += term
                    inhibitor_alpha_tex += tex_term
                elif direct_tag is True:
                    direct_terms_list.append(direct_string_i)
                    direct_terms_tex.append(direct_tex_i)
                if i < len(i_list) - 1:
                    inhibitor_alpha += "*"
                    inhibitor_alpha_tex += "\\,"
                elif i >= len(i_list) - 1:
                    if inhibitor_alpha.endswith("*"):
                        inhibitor_alpha = inhibitor_alpha[:-1]
                    inhibitor_alpha += ")"
                    inhibitor_alpha_tex += "\\,"
        else:
            inhibitor_alpha += dl
        if inhibitor_alpha == "()":
            inhibitor_alpha = ""
            alpha = activator_alpha
        elif activator_alpha == "()":
            activator_alpha = ""
            alpha = inhibitor_alpha
        else:
            alpha = activator_alpha + "*" + inhibitor_alpha
        alpha_tex = activator_alpha_tex + "\\," + inhibitor_alpha_tex
        if len(direct_terms_list) > 0:
            for q, (dit, ditex) in enumerate(zip(direct_terms_list, direct_terms_tex)):
                direct_term_alpha += dit
                direct_term_alpha_tex += ditex
                if q < len(direct_terms_list) - 1:
                    direct_term_alpha += "+"
                    direct_term_alpha_tex += "+"
                else:
                    direct_term_alpha += ")"
                    direct_term_alpha_tex += "\\,"
            alpha = alpha + "*" + direct_term_alpha
            alpha_tex = alpha_tex + "\\," + direct_term_alpha_tex
        return (alpha, alpha_tex, tex_list)


class Reaction:
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
        self.reaction_activators_list = None
        self.reaction_activators_Km = None
        self.reaction_activators_n = None
        self.reaction_inhibitors_list = None
        self.reaction_inhibitors_Km = None
        self.reaction_inhibitors_n = None


class Modulator:
    def __init__(self):
        self.target_label = None
        self.max_val = None
        self.target_ion = None
        self.modulator_activators_list = None
        self.modulator_activators_Km = None
        self.modulator_activators_n = None
        self.modulator_inhibitors_list = None
        self.modulator_inhibitors_Km = None
        self.modulator_inhibitors_n = None

    def init_modulator(self, sim, cells, p):
        if self.target_label == "GJ":
            sim.gj_block_o = np.ones(sim.mdl)
        elif self.target_label == "Na/K-ATPase":
            sim.NaKATP_block_o = np.ones(sim.mdl)
        elif self.target_label == "TJ":
            if self.target_ion is None or self.target_ion == "None":
                self.ion_i = None
            else:
                self.ion_i = sim.get_ion(self.target_ion)
        else:
            raise BetseSimConfException(
                "You have requested a sim modulator that is not available. Available choices are: 'GJ', 'Na/K-ATPase' and 'MT' "
            )


class RowAliases(MutableMapping):
    """Explicit current-row ownership, independently captured against DynamicValueDict."""

    def __init__(self, sim, attribute, names):
        self.sim, self.attribute, self.names = sim, attribute, tuple(names)

    def __getitem__(self, key):
        return getattr(self.sim, self.attribute)[self.names.index(key)]

    def __setitem__(self, key, value):
        getattr(self.sim, self.attribute)[self.names.index(key)] = value

    def __delitem__(self, key):
        raise ValueError("Native ion row ownership cannot be deleted")

    def __iter__(self):
        return iter(self.names)

    def __len__(self):
        return len(self.names)


def validate(definition, ion_binding, current_binding, configured_temperature_K):
    required = {
        "owner",
        "reactions",
        "modulators",
        "initial_controls",
        "membrane_to_environment",
        "provenance",
    }
    if (
        not isinstance(definition, dict)
        or set(definition) != required
        or definition["owner"] not in ("molecules", "grn")
        or not isinstance(definition["provenance"], str)
        or not definition["provenance"].strip()
    ):
        raise ValueError(
            "Require one explicitly enabled native network owner and complete declaration"
        )
    if definition["reactions"] != []:
        raise ValueError(
            "Complete owned molecule transport/chemistry is a separate dependency; empty chemistry required"
        )
    mods = definition["modulators"]
    if not isinstance(mods, list) or len(mods) > 8:
        raise ValueError("Require bounded ordered native network modulators")
    for row in mods:
        if (
            row.get("target") not in ("GJ", "Na/K-ATPase")
            or not row.get("name", "").isidentifier()
            or type(row.get("max effect")) not in (int, float)
            or row["max effect"] < 0
        ):
            raise ValueError("First seam supports nonnegative GJ/NaK source modulators")
        for key in ("activators", "inhibitors"):
            labels = row.get(key)
            if labels not in (None, "None", []) and any(not name.isidentifier() for name in labels):
                raise ValueError("First seam uses ordinary nonnegative ion Hill regulators")
    m = len(ion_binding.membrane_ids)
    names, valence = ion_binding.ion_ids, ion_binding.kernel.valence
    if any(not name.isidentifier() for name in names):
        raise ValueError("Require native ion identifiers")
    modulation.bind(
        mods,
        [],
        names,
        valence,
        definition["membrane_to_environment"],
        m,
        names,
        tj_targets=[False] * m,
        faraday_C_mol=ion_binding.kernel.F_C_mol,
        gas_constant_J_mol_K=ion_binding.kernel.R_J_mol_K,
        temperature_K=configured_temperature_K,
    )
    controls(definition["initial_controls"], m)
    if current_binding.ion_ids != ion_binding.ion_ids or not np.array_equal(
        current_binding.kernel.valence, valence
    ):
        raise ValueError("Current and chemical ion valences must share an axis")


def controls(raw, m):
    if not isinstance(raw, dict) or set(raw) != {"gj_block", "NaKATP_block"}:
        raise ValueError("Require both owned native control vectors")
    result = {}
    for name, value in raw.items():
        array = np.asarray(value, np.float64)
        if array.shape != (m,) or not np.isfinite(array).all() or np.any(array < 0):
            raise ValueError("Require finite nonnegative native control: " + name)
        result[name] = ions.freeze(array)
    return ions.freeze(result)


def prepare(
    arrays, *, ion_ids, parameters, definition, incoming_controls, incoming_cache, phase_kind
):
    cell, membrane, bath, vm, *_ = arrays
    n, m = cell.shape[1], len(vm)
    owned = controls(ions.data(incoming_controls), m)
    sim = SimpleNamespace(
        cc_cells=cell,
        cc_at_mem=membrane,
        cc_env=bath,
        vm=vm,
        T=parameters["runtime_temperature_K"],
        cdl=n,
        mdl=m,
        edl=m,
        gj_block=np.array(owned["gj_block"], copy=True),
        NaKATP_block=np.array(owned["NaKATP_block"], copy=True),
        extra_rho_cells=np.array(parameters["incoming_extra_charge"], copy=True),
        extra_J_mem=np.array(parameters["incoming_extra_current"], copy=True),
    )
    sim.get_ion = lambda name: ion_ids.index(name)
    p = SimpleNamespace(
        R=parameters["R"],
        F=parameters["F"],
        dt=parameters["dt_s"],
        is_ecm=False,
        ions_dict={name: 1 for name in ion_ids},
        substances_affect_charge=parameters["substances_affect_charge"],
    )
    cells = SimpleNamespace(
        cell_i=np.arange(n),
        mem_i=np.arange(m),
        map_mem2ecm=np.asarray(definition["membrane_to_environment"], np.int64),
    )
    net = _LiteralNetwork()
    net.molecules = OrderedDict()
    net.mit_enabled = False
    net.reactions_mit = OrderedDict()
    net.reactions_env = OrderedDict()
    net.cell_concs = RowAliases(sim, "cc_cells", ion_ids)
    net.mem_concs = RowAliases(sim, "cc_at_mem", ion_ids)
    net.env_concs = RowAliases(sim, "cc_env", ion_ids)
    net.zmol = {name: parameters["valence"][i] for i, name in enumerate(ion_ids)}
    net.reaction_rates = None
    if incoming_cache is not None:
        for key in ("reaction_rates", "delta_conc", "delta_conc_env", "chi"):
            if key in incoming_cache:
                setattr(net, key, copy_value(incoming_cache[key]))
    net.read_reactions(ions.data(definition["reactions"]), sim, cells, p)
    net.write_reactions()
    net.write_growth_and_decay()
    net.create_reaction_matrix()
    net.read_modulators(ions.data(definition["modulators"]), sim, cells, p)
    net.clear_run_loop(sim)
    return net, sim, cells, p, SimpleNamespace(sim=sim, cells=cells, p=p, kind=phase_kind)


def copy_value(value):
    return np.array(value, copy=True) if isinstance(value, np.ndarray) else value


def cache(net):
    fields = ("reaction_rates", "delta_conc", "delta_conc_env", "chi")
    return ions.freeze(
        dict(
            present_fields=tuple(name for name in fields if hasattr(net, name)),
            reaction_rates=copy_value(getattr(net, "reaction_rates", None)),
            delta_conc=copy_value(getattr(net, "delta_conc", None)),
            delta_conc_env=copy_value(getattr(net, "delta_conc_env", None)),
            chi=copy_value(getattr(net, "chi", None)),
            reaction_matrix=net.reaction_matrix.copy(),
            reaction_expressions={
                name: row.reaction_eval_string for name, row in net.reactions.items()
            },
            modulator_expressions={
                name: row.alpha_eval_string for name, row in net.modulators.items()
            },
            extra_rho_env=net.extra_rho_env.copy(),
            extra_rho_mit=net.extra_rho_mit.copy(),
            extra_Jenv_x=net.extra_Jenv_x.copy(),
            extra_Jenv_y=net.extra_Jenv_y.copy(),
            extra_rho_cells=net.extra_rho_cells.copy(),
            extra_J_mem=net.extra_J_mem.copy(),
        )
    )
