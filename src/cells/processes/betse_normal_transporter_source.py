# ruff: noqa: B007, B905, E501
"""Actual configured transporter builder and ordered source execution.

The no-ECM cell-volume bath update and coefficient-free membrane-buffer
updates are preserved. This consumes supplied geometry and configured state.
"""

import copy
from collections import OrderedDict
from collections.abc import Mapping
from types import SimpleNamespace

import numpy as np

from cells.processes import betse_network_transport as component
from cells.processes import betse_normal_ion_join as ions
from cells.processes import betse_normal_molecule_source as molecule_source

logs = SimpleNamespace(log_info=lambda *_: None, log_warning=lambda *_: None)
tex_val = str
BetseSimConfException = ValueError
controls = molecule_source.controls
EXTRA = {"transporters", "membrane_volume_m3", "transporter_profiles"}


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
        if (
            self.transporter_profiles_list is not None
            and self.transporter_profiles_list != "all"
            and (self.transporter_profiles_list != "express")
        ):
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
        elif self.transporter_profiles_list == "express":
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


class _Network(molecule_source._Network):
    def read_transporters(self, config_transporters, phase):
        sim = phase.sim
        cells = phase.cells
        p = phase.p
        logs.log_info("Reading transporter input data...")
        self.transporters = OrderedDict({})
        for q, trans_dic in enumerate(config_transporters):
            name = str(trans_dic["name"])
            self.transporters[name] = Transporter(sim, cells, p)
            obj = self.transporters[name]
            obj.name = name
            obj.reaction_zone = trans_dic["reaction zone"]
            obj.reactants_list = trans_dic["reactants"]
            obj.reactants_coeff = trans_dic["reactant multipliers"]
            obj.products_list = trans_dic["products"]
            obj.products_coeff = trans_dic["product multipliers"]
            obj.Km_reactants_list = trans_dic["Km reactants"]
            obj.Km_products_list = trans_dic["Km products"]
            obj.transport_out_list = trans_dic["transfered out of cell"]
            obj.transport_in_list = trans_dic["transfered into cell"]
            obj.vmax = float(trans_dic["max rate"])
            obj.delta_Go = trans_dic["standard free energy"]
            obj.ignore_ECM_transporter = trans_dic["ignore ECM"]
            obj.transporter_profiles_list = trans_dic["apply to"]
            obj.init_reaction(phase)
            if obj.delta_Go == "None":
                obj.delta_Go = None
            else:
                obj.delta_Go = float(obj.delta_Go)
            obj.transporter_activators_list = trans_dic.get("transporter activators", None)
            obj.transporter_activators_Km = trans_dic.get("activator Km", None)
            obj.transporter_activators_n = trans_dic.get("activator n", None)
            obj.transporter_activators_zone = trans_dic.get("activator zone", None)
            obj.transporter_inhibitors_list = trans_dic.get("transporter inhibitors", None)
            obj.transporter_inhibitors_Km = trans_dic.get("inhibitor Km", None)
            obj.transporter_inhibitors_n = trans_dic.get("inhibitor n", None)
            obj.transporter_inhibitors_zone = trans_dic.get("inhibitor zone", None)
            obj.transporter_activators_zone, obj.transporter_inhibitors_zone = self.default_zones(
                obj.transporter_activators_zone,
                obj.transporter_inhibitors_zone,
                obj.transporter_activators_list,
                obj.transporter_inhibitors_list,
            )
            if self.mit_enabled:
                obj.mit_enabled = True
            else:
                obj.mit_enabled = False
        for name in self.transporters:
            msg = "Including the network transporter: {}".format(name)
            logs.log_info(msg)

    def write_transporters(self, sim, cells, p):
        logs.log_info("Writing transporter equations...")
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
            react_transfer_tag = ["mem_concs" for x in reactant_names]
            prod_transfer_tag = ["mem_concs" for x in product_names]
            echem_terms_list = []
            echem_terms_list_tex = []
            if reaction_zone == "cell":
                type_out = "env_concs"
                vmem = "sim.vm"
                vmem_tex = "V_{mem}"
                in_delta_term_react = "(np.dot(cells.M_sum_mems, -self.transporters['{}'].flux*cells.mem_sa)/cells.cell_vol)".format(
                    transp_name
                )
                in_delta_term_prod = "(np.dot(cells.M_sum_mems, self.transporters['{}'].flux*cells.mem_sa)/cells.cell_vol)".format(
                    transp_name
                )
                if p.is_ecm is True:
                    out_delta_term_react = (
                        "stb.div_env(-self.transporters['{}'].flux, cells, p)".format(transp_name)
                    )
                    out_delta_term_prod = (
                        "stb.div_env(self.transporters['{}'].flux, cells, p)".format(transp_name)
                    )
                else:
                    out_delta_term_react = "(np.dot(cells.M_sum_mems, -self.transporters['{}'].flux*cells.mem_sa)/cells.cell_vol)".format(
                        transp_name
                    )
                    out_delta_term_prod = "(np.dot(cells.M_sum_mems, self.transporters['{}'].flux*cells.mem_sa)/cells.cell_vol)".format(
                        transp_name
                    )
                all_alpha, alpha_tex, trans_tex_var_list = self.get_influencers(
                    a_list,
                    Km_a_list,
                    n_a_list,
                    i_list,
                    Km_i_list,
                    n_i_list,
                    tex_list=trans_tex_var_list,
                    reaction_zone="mem",
                    in_mem_tag=False,
                )
            elif reaction_zone == "mit" and self.mit_enabled is True:
                vmem_tex = "V_{mit}"
                react_transfer_tag = ["mit_concs" for x in reactant_names]
                prod_transfer_tag = ["mit_concs" for x in product_names]
                type_out = "cell_concs"
                vmem = "self.mit.Vmit"
                in_delta_term_react = (
                    "-self.transporters['{}'].flux*(self.mit.mit_sa/self.mit.mit_vol)".format(
                        transp_name
                    )
                )
                in_delta_term_prod = (
                    "self.transporters['{}'].flux*(self.mit.mit_sa/self.mit.mit_vol)".format(
                        transp_name
                    )
                )
                out_delta_term_react = (
                    "-self.transporters['{}'].flux*(self.mit.mit_sa/cells.cell_vol)".format(
                        transp_name
                    )
                )
                out_delta_term_prod = (
                    "self.transporters['{}'].flux*(self.mit.mit_sa/cells.cell_vol)".format(
                        transp_name
                    )
                )
                all_alpha, alpha_tex, trans_tex_var_list = self.get_influencers(
                    a_list,
                    Km_a_list,
                    n_a_list,
                    i_list,
                    Km_i_list,
                    n_i_list,
                    reaction_zone="mit",
                    tex_list=trans_tex_var_list,
                    in_mem_tag=False,
                )
            delta_strings_reactants = [in_delta_term_react for x in reactant_names]
            delta_strings_products = [in_delta_term_prod for x in product_names]
            if transport_out_list != "None":
                for out_name in transport_out_list:
                    if out_name in p.ions_dict:
                        if p.ions_dict[out_name] == 1:
                            ion_ind = sim.get_ion(out_name)
                            prod_i = product_names.index(out_name)
                            prod_transfer_tag[prod_i] = type_out
                            coeff = product_coeff[prod_i]
                            eterm = "-{}*sim.zs[{}]*p.F*{}".format(coeff, ion_ind, vmem)
                            self.transporters[transp_name].net_z += coeff * sim.zs[ion_ind]
                            eterm_tex = "-%s\\,[%s]\\,z_{%s}\\,F\\,%s" % (
                                coeff,
                                out_name,
                                out_name,
                                vmem_tex,
                            )
                            zval = tex_val(sim.zs[ion_ind])
                            z_tex = "z_{%s} & =" % out_name
                            z_tex += zval
                    else:
                        prod_i = product_names.index(out_name)
                        prod_transfer_tag[prod_i] = type_out
                        coeff = product_coeff[prod_i]
                        eterm = "-{}*self.molecules['{}'].z*p.F*{}".format(coeff, out_name, vmem)
                        self.transporters[transp_name].net_z += coeff * self.molecules[out_name].z
                        eterm_tex = "-%s\\,[%s]\\,z_{%s}\\,F\\,%s" % (
                            coeff,
                            out_name,
                            out_name,
                            vmem_tex,
                        )
                        zval = tex_val(self.molecules[out_name].z)
                        z_tex = "z_{%s} & =" % out_name
                        z_tex += zval
                    trans_tex_var_list.append(z_tex)
                    echem_terms_list.append(eterm)
                    echem_terms_list_tex.append(eterm_tex)
                    delta_strings_products[prod_i] = out_delta_term_prod
            if transport_in_list != "None":
                for in_name in transport_in_list:
                    if in_name in p.ions_dict:
                        if p.ions_dict[in_name] == 1:
                            ion_ind = sim.get_ion(in_name)
                            react_i = reactant_names.index(in_name)
                            react_transfer_tag[react_i] = type_out
                            coeff = reactant_coeff[react_i]
                            eterm = "{}*sim.zs[{}]*p.F*{}".format(coeff, ion_ind, vmem)
                            self.transporters[transp_name].net_z += -coeff * sim.zs[ion_ind]
                            eterm_tex = "%s\\,[%s]\\,z_{%s}\\,F\\,%s" % (
                                coeff,
                                in_name,
                                in_name,
                                vmem_tex,
                            )
                            zval = tex_val(sim.zs[ion_ind])
                            z_tex = "z_{%s} & =" % in_name
                            z_tex += zval
                    else:
                        react_i = reactant_names.index(in_name)
                        react_transfer_tag[react_i] = type_out
                        coeff = reactant_coeff[react_i]
                        eterm = "{}*self.molecules['{}'].z*p.F*{}".format(coeff, in_name, vmem)
                        self.transporters[transp_name].net_z += -coeff * self.molecules[in_name].z
                        eterm_tex = "%s\\,[%s]\\,z_{%s}\\,F\\,%s" % (
                            coeff,
                            in_name,
                            in_name,
                            vmem_tex,
                        )
                        zval = tex_val(self.molecules[in_name].z)
                        z_tex = "z_{%s} & =" % in_name
                        z_tex += zval
                    trans_tex_var_list.append(z_tex)
                    echem_terms_list.append(eterm)
                    echem_terms_list_tex.append(eterm_tex)
                    delta_strings_reactants[react_i] = out_delta_term_react
            echem_string = "("
            echem_tex_string = ""
            for i, (et, etx) in enumerate(zip(echem_terms_list, echem_terms_list_tex)):
                echem_string += et
                echem_tex_string += etx
                if i < len(echem_terms_list) - 1:
                    echem_string += "+"
                    echem_tex_string += "+"
                else:
                    echem_string += ")"
            numo_string_Q = "("
            denomo_string_Q = "("
            numo_tex = ""
            deno_tex = ""
            for i, (name, coeff, tag) in enumerate(
                zip(reactant_names, reactant_coeff, react_transfer_tag)
            ):
                if tag == "mem_concs":
                    denomo_string_Q += "(1.0e-3*self.{}['{}']".format(tag, name)
                    tex_name = name
                elif tag == "mit_concs":
                    denomo_string_Q += "(1.0e-3*self.{}['{}']".format(tag, name)
                    tex_name = name + "_{mit}"
                elif tag == "cell_concs":
                    denomo_string_Q += "(1.0e-3*self.{}['{}']".format(tag, name)
                    tex_name = name
                elif tag == "env_concs":
                    if p.is_ecm is True:
                        denomo_string_Q += "(1.0e-3*self.{}['{}'][cells.map_mem2ecm]".format(
                            tag, name
                        )
                    else:
                        denomo_string_Q += "(1.0e-3*self.{}['{}']".format(tag, name)
                    tex_name = name + "_{env}"
                else:
                    raise BetseSimConfException("Transporter tag not properly defined!")
                denomo_string_Q += "**{})".format(coeff)
                deno_tex += "[%s]^{%s}" % (tex_name, coeff)
                if i < len(reactant_names) - 1:
                    denomo_string_Q += "*"
                    deno_tex += "\\,"
                else:
                    denomo_string_Q += ")"
            for i, (name, coeff, tag) in enumerate(
                zip(product_names, product_coeff, prod_transfer_tag)
            ):
                if tag == "mem_concs":
                    numo_string_Q += "(1.0e-3*self.{}['{}']".format(tag, name)
                    tex_name = name
                elif tag == "mit_concs":
                    numo_string_Q += "(1.0e-3*self.{}['{}']".format(tag, name)
                    tex_name = name + "_{mit}"
                elif tag == "cell_concs":
                    numo_string_Q += "(1.0e-3*self.{}['{}']".format(tag, name)
                    tex_name = name
                elif tag == "env_concs":
                    if p.is_ecm is True:
                        numo_string_Q += "(1.0e-3*self.{}['{}'][cells.map_mem2ecm]".format(
                            tag, name
                        )
                    else:
                        numo_string_Q += "(1.0e-3*self.{}['{}']".format(tag, name)
                    tex_name = name + "_{env}"
                else:
                    raise BetseSimConfException("Transporter tag not properly defined!")
                numo_string_Q += "**{})".format(coeff)
                numo_tex += "[%s]^{%s}" % (tex_name, coeff)
                if i < len(product_names) - 1:
                    numo_string_Q += "*"
                    numo_tex += "\\,"
                else:
                    numo_string_Q += ")"
            Q = "(" + numo_string_Q + "/" + denomo_string_Q + ")"
            Q_tex = "\\frac{%s}{%s}" % (numo_tex, deno_tex)
            forward_coeff = "("
            backward_coeff = "("
            fwd_tex_coeff = ""
            bwd_tex_coeff = ""
            for i, (name, n, Km, tag) in enumerate(
                zip(reactant_names, reactant_coeff, reactant_Km, react_transfer_tag)
            ):
                if tag == "mem_concs":
                    numo_string_r = "((self.{}['{}']/{})**{})".format(tag, name, Km, n)
                    denomo_string_r = "(1 + (self.{}['{}']/{})**{})".format(tag, name, Km, n)
                    tex_name = name
                elif tag == "mit_concs":
                    numo_string_r = "((self.{}['{}']/{})**{})".format(tag, name, Km, n)
                    denomo_string_r = "(1 + (self.{}['{}']/{})**{})".format(tag, name, Km, n)
                    tex_name = name + "_{mit}"
                elif tag == "cell_concs":
                    numo_string_r = "((self.{}['{}']/{})**{})".format(tag, name, Km, n)
                    denomo_string_r = "(1 + (self.{}['{}']/{})**{})".format(tag, name, Km, n)
                    tex_name = name
                elif tag == "env_concs":
                    if p.is_ecm is True:
                        numo_string_r = "((self.{}['{}'][cells.map_mem2ecm]/{})**{})".format(
                            tag, name, Km, n
                        )
                        denomo_string_r = "(1 + (self.{}['{}'][cells.map_mem2ecm]/{})**{})".format(
                            tag, name, Km, n
                        )
                    else:
                        numo_string_r = "((self.{}['{}']/{})**{})".format(tag, name, Km, n)
                        denomo_string_r = "(1 + (self.{}['{}']/{})**{})".format(tag, name, Km, n)
                    tex_name = name + "_{env}"
                else:
                    raise BetseSimConfException("Transporter tag not properly defined!")
                term = "(" + numo_string_r + "/" + denomo_string_r + ")"
                forward_coeff += term
                cc_tex = "\\left(\\frac{[%s]}{K_{%s_f}^{%s}}\\right)^{n_{%s_f}^{%s}}" % (
                    tex_name,
                    transp_name,
                    tex_name,
                    transp_name,
                    tex_name,
                )
                fwd_tex_coeff += "\\left(\\frac{%s}{1+%s}\\right)" % (cc_tex, cc_tex)
                if i < len(reactant_names) - 1:
                    forward_coeff += "*"
                    fwd_tex_coeff += "\\,"
                else:
                    forward_coeff += ")"
                kval = tex_val(Km)
                k_tex = "K_{%s}^{%s} & =" % (transp_name, tex_name)
                k_tex += kval
                trans_tex_var_list.append(k_tex)
                nval = tex_val(n)
                n_tex = "n_{%s}^{%s} & =" % (transp_name, tex_name)
                n_tex += nval
                trans_tex_var_list.append(n_tex)
            for i, (name, n, Km, tag) in enumerate(
                zip(product_names, product_coeff, product_Km, prod_transfer_tag)
            ):
                if tag == "mem_concs":
                    numo_string_p = "((self.{}['{}']/{})**{})".format(tag, name, Km, n)
                    denomo_string_p = "(1 + (self.{}['{}']/{})**{})".format(tag, name, Km, n)
                    tex_name = name
                elif tag == "mit_concs":
                    numo_string_p = "((self.{}['{}']/{})**{})".format(tag, name, Km, n)
                    denomo_string_p = "(1 + (self.{}['{}']/{})**{})".format(tag, name, Km, n)
                    tex_name = name + "_{mit}"
                elif tag == "cell_concs":
                    numo_string_p = "((self.{}['{}']/{})**{})".format(tag, name, Km, n)
                    denomo_string_p = "(1 + (self.{}['{}']/{})**{})".format(tag, name, Km, n)
                    tex_name = name
                elif tag == "env_concs":
                    if p.is_ecm is True:
                        numo_string_p = "((self.{}['{}'][cells.map_mem2ecm]/{})**{})".format(
                            tag, name, Km, n
                        )
                        denomo_string_p = "(1 + (self.{}['{}'][cells.map_mem2ecm]/{})**{})".format(
                            tag, name, Km, n
                        )
                    else:
                        numo_string_p = "((self.{}['{}']/{})**{})".format(tag, name, Km, n)
                        denomo_string_p = "(1 + (self.{}['{}']/{})**{})".format(tag, name, Km, n)
                    tex_name = name + "_{env}"
                else:
                    raise BetseSimConfException("Transporter tag not properly defined!")
                term = "(" + numo_string_p + "/" + denomo_string_p + ")"
                backward_coeff += term
                cc_tex = "\\left(\\frac{[%s]}{K_{%s_r}^{%s}}\\right)^{n_{%s_r}^{%s}}" % (
                    tex_name,
                    transp_name,
                    tex_name,
                    transp_name,
                    tex_name,
                )
                bwd_tex_coeff += "\\left(\\frac{%s}{1+%s}\\right)" % (cc_tex, cc_tex)
                if i < len(product_names) - 1:
                    backward_coeff += "*"
                    bwd_tex_coeff += "\\,"
                else:
                    backward_coeff += ")"
                if self.transporters[transp_name].delta_Go is not None:
                    kval = tex_val(Km)
                    k_tex = "K_{%s}^{%s} & =" % (transp_name, tex_name)
                    k_tex += kval
                    trans_tex_var_list.append(k_tex)
                    nval = tex_val(n)
                    n_tex = "n_{%s}^{%s} & =" % (transp_name, tex_name)
                    n_tex += nval
                    trans_tex_var_list.append(n_tex)
            if self.transporters[transp_name].delta_Go is not None:
                Keqm = "(np.exp(-(self.transporters['{}'].delta_Go + {})/ (p.R * sim.T)))".format(
                    transp_name, echem_string
                )
                Keqm_tex = "\\frac{exp(-deltaG_{%s}^{o} + %s)}{R\\,T}" % (
                    transp_name,
                    echem_tex_string,
                )
                gval = tex_val(self.transporters[transp_name].delta_Go)
                g_tex = "deltaG_{%s}^{o} & =" % transp_name
                g_tex += gval
                trans_tex_var_list.append(g_tex)
            else:
                Q = "0"
                backward_coeff = "0"
                Keqm = "1"
                Keqm_tex = ""
            reversed_term = "(" + Q + "/" + Keqm + ")"
            rev_term_tex = "\\left(\\frac{%s}{%s}\\right)" % (Q_tex, Keqm_tex)
            vmax = "self.transporters['{}'].vmax".format(transp_name)
            v_texo = "r_{%s}^{max}" % transp_name
            vm_tex = "r_{%s}" % transp_name
            vval = tex_val(self.transporters[transp_name].vmax)
            v_tex = "v_{%s}^{max} & =" % transp_name
            v_tex += vval
            trans_tex_var_list.append(v_tex)
            if self.transporters[transp_name].delta_Go is not None:
                transporter_tex_string = (
                    vm_tex
                    + " = "
                    + v_texo
                    + "\\,"
                    + alpha_tex
                    + "\\,\\left("
                    + "1.0"
                    + "-"
                    + rev_term_tex
                    + "\\,"
                    + bwd_tex_coeff
                    + "\\right)"
                )
                transporter_eval_string = (
                    vmax
                    + "*"
                    + all_alpha
                    + "*"
                    + forward_coeff
                    + "*"
                    + "("
                    + "1.0"
                    + "-"
                    + reversed_term
                    + ")"
                )
            else:
                transporter_tex_string = (
                    vm_tex + " = " + v_tex + "\\," + alpha_tex + "\\," + fwd_tex_coeff
                )
                transporter_eval_string = vmax + "*" + all_alpha + "*" + forward_coeff
            tex_params = "\\begin{aligned}"
            for i, tex_str in enumerate(trans_tex_var_list):
                tex_params += tex_str
                if i < len(trans_tex_var_list) - 1:
                    tex_params += "\\\\"
                elif i == len(trans_tex_var_list) - 1:
                    tex_params += "\\end{aligned}"
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
            self._observe_transporter("before", name, None, None, sim)
            targ_mem = self.transporters[name].transporter_targets_mem
            targ_cell = self.transporters[name].transporter_targets_cell
            targ_env = self.transporters[name].transporter_targets_env
            self.transporters[name].flux = sim.rho_pump * eval(
                self.transporters[name].transporter_eval_string, globalo, localo
            )
            self._observe_transporter("flux", name, None, None, sim)
            self.extra_J_mem += self.transporters[name].net_z * self.transporters[name].flux * p.F
            self._observe_transporter("current", name, None, None, sim)
            for i, (delc, coeff) in enumerate(
                zip(
                    self.transporters[name].delta_react_eval_strings,
                    self.transporters[name].reactants_coeff,
                )
            ):
                delta_react = coeff * eval(delc, globalo, localo)
                if self.transporters[name].react_transport_tag[i] == "mem_concs":
                    self.cell_concs[self.transporters[name].reactants_list[i]][targ_cell] = (
                        self.cell_concs[self.transporters[name].reactants_list[i]][targ_cell]
                        + delta_react[targ_cell] * p.dt
                    )
                    self.mem_concs[self.transporters[name].reactants_list[i]][targ_mem] = (
                        self.mem_concs[self.transporters[name].reactants_list[i]][targ_mem]
                        - self.transporters[name].flux[targ_mem]
                        * (cells.mem_sa[targ_mem] / cells.mem_vol[targ_mem])
                        * p.dt
                    )
                elif self.transporters[name].react_transport_tag[i] == "env_concs":
                    if p.is_ecm is True:
                        self.env_concs[self.transporters[name].reactants_list[i]][targ_env] = (
                            self.env_concs[self.transporters[name].reactants_list[i]][targ_env]
                            + delta_react[targ_env] * p.dt
                        )
                    else:
                        self.env_concs[self.transporters[name].reactants_list[i]][targ_mem] = (
                            self.env_concs[self.transporters[name].reactants_list[i]][targ_mem]
                            + delta_react[targ_cell][cells.mem_to_cells] * p.dt
                        )
                elif self.transporters[name].react_transport_tag[i] == "cell_concs":
                    self.cell_concs[self.transporters[name].reactants_list[i]][targ_cell] = (
                        self.cell_concs[self.transporters[name].reactants_list[i]][targ_cell]
                        + delta_react[targ_cell] * p.dt
                    )
                elif self.transporters[name].react_transport_tag[i] == "mit_concs":
                    self.mit_concs[self.transporters[name].reactants_list[i]][targ_cell] = (
                        self.mit_concs[self.transporters[name].reactants_list[i]][targ_cell]
                        + delta_react[targ_cell] * p.dt
                    )
                else:
                    raise BetseSimConfException(
                        "Internal error: transporter zone not specified correctly!"
                    )
                self._observe_transporter("reactant_commit", name, i, delta_react, sim)
            for i, (delc, coeff) in enumerate(
                zip(
                    self.transporters[name].delta_prod_eval_strings,
                    self.transporters[name].products_coeff,
                )
            ):
                delta_prod = coeff * eval(delc, globalo, localo)
                if self.transporters[name].prod_transport_tag[i] == "mem_concs":
                    self.cell_concs[self.transporters[name].products_list[i]][targ_cell] = (
                        self.cell_concs[self.transporters[name].products_list[i]][targ_cell]
                        + delta_prod[targ_cell] * p.dt
                    )
                    self.mem_concs[self.transporters[name].products_list[i]][targ_mem] = (
                        self.mem_concs[self.transporters[name].products_list[i]][targ_mem]
                        + self.transporters[name].flux[targ_mem]
                        * (cells.mem_sa[targ_mem] / cells.mem_vol[targ_mem])
                        * p.dt
                    )
                elif self.transporters[name].prod_transport_tag[i] == "env_concs":
                    if p.is_ecm is True:
                        self.env_concs[self.transporters[name].products_list[i]][targ_env] = (
                            self.env_concs[self.transporters[name].products_list[i]][targ_env]
                            + delta_prod[targ_env] * p.dt
                        )
                    else:
                        self.env_concs[self.transporters[name].products_list[i]][targ_mem] = (
                            self.env_concs[self.transporters[name].products_list[i]][targ_mem]
                            + delta_prod[targ_cell][cells.mem_to_cells] * p.dt
                        )
                elif self.transporters[name].prod_transport_tag[i] == "cell_concs":
                    self.cell_concs[self.transporters[name].products_list[i]][targ_cell] = (
                        self.cell_concs[self.transporters[name].products_list[i]][targ_cell]
                        + delta_prod[targ_cell] * p.dt
                    )
                elif self.transporters[name].prod_transport_tag[i] == "mit_concs":
                    self.mit_concs[self.transporters[name].products_list[i]][targ_cell] = (
                        self.mit_concs[self.transporters[name].products_list[i]][targ_cell]
                        + delta_prod[targ_cell] * p.dt
                    )
                else:
                    raise BetseSimConfException(
                        "Internal error: transporter zone not specified correctly!"
                    )
                self._observe_transporter("product_commit", name, i, delta_prod, sim)
            self._observe_transporter("after", name, None, None, sim)


def base_definition(definition):
    return {key: value for key, value in definition.items() if key not in EXTRA}


def integer_valences(values):
    """Lossless component-axis representation; native scientific buffers stay float64."""
    raw = np.asarray(values)
    if (
        raw.ndim != 1
        or not raw.size
        or raw.dtype.kind not in "fiu"
        or not np.isfinite(raw).all()
        or np.any(raw < -8)
        or np.any(raw > 8)
        or not np.array_equal(raw, np.trunc(raw))
    ):
        raise ValueError("Require finite integral valences in [-8,8] for the component axis")
    integers = raw.astype(np.int64)
    if not np.array_equal(raw, integers):
        raise ValueError("Component valence conversion must be lossless")
    return integers


def validate(definition, ion_binding, current_binding, configured_temperature_K):
    if not isinstance(definition, dict) or not EXTRA <= definition.keys():
        raise ValueError("Require configured transporters, membrane volumes and profile ownership")
    molecule_source.validate(
        base_definition(definition), ion_binding, current_binding, configured_temperature_K
    )
    n, m = len(ion_binding.cell_ids), len(ion_binding.membrane_ids)
    volume = np.asarray(definition["membrane_volume_m3"], np.float64)
    expected = 0.5 * np.asarray(definition["radius_m"], np.float64) * ion_binding.kernel.area_m2
    if (
        volume.shape != (m,)
        or not np.isfinite(volume).all()
        or np.any(volume <= 0)
        or not np.array_equal(volume, expected)
    ):
        raise ValueError("Require the explicit source membrane wedge volumes 0.5*radius*area")
    profiles = definition["transporter_profiles"]
    if not isinstance(profiles, dict):
        raise ValueError("Require explicit supplied profile targets")
    for name, row in profiles.items():
        if (
            not isinstance(name, str)
            or not name
            or set(row) != {"cells", "membranes", "environment"}
        ):
            raise ValueError("Incomplete supplied transporter profile")
        for key, bound in (("cells", n), ("membranes", m), ("environment", m)):
            values = row[key]
            if (
                not isinstance(values, list)
                or not values
                or len(set(values)) != len(values)
                or any(type(value) is not int or not 0 <= value < bound for value in values)
            ):
                raise ValueError("Require unique in-range supplied profile targets")
    rows = definition["transporters"]
    if not isinstance(rows, list) or not rows or len(rows) > 3:
        raise ValueError("Require one to three genuine configured transporters")
    for row in rows:
        if row.get("standard free energy") != "None" and not molecule_source._number(
            row.get("standard free energy")
        ):
            raise ValueError("Require a finite standard energy or the native literal 'None'")
        if not {"ignore ECM", "apply to"} <= row.keys() or row["ignore ECM"] is not False:
            raise ValueError("Explicit no-ECM transporter ownership is required")
        targets = row["apply to"]
        if targets != "all" and (
            not isinstance(targets, list)
            or not targets
            or any(name not in profiles for name in targets)
            or len(set(targets)) != len(targets)
        ):
            raise ValueError("Require all targets or completely supplied named profiles")
    species = tuple(ion_binding.ion_ids) + tuple(row["name"] for row in definition["molecules"])
    valence = tuple(ion_binding.kernel.valence) + tuple(
        row["parameters"]["z"] for row in definition["molecules"]
    )
    component.bind(
        rows,
        species,
        integer_valences(valence),
        [0] * len(rows),
        [1] * len(rows),
        [True, True],
        area_m2=[1.0] * len(rows),
        temperature_K=configured_temperature_K,
    )


def initial_cache(definition):
    values = ions.data(molecule_source.initial_cache(base_definition(definition)))
    values["transporter_fluxes"] = {row["name"]: None for row in definition["transporters"]}
    return ions.freeze(values)


snapshot = molecule_source.snapshot


def fluxes(net):
    return {name: copy.deepcopy(obj.flux) for name, obj in net.transporters.items()}


def concentrations(net):
    return {
        zone: {name: np.array(value, copy=True) for name, value in getattr(net, zone).items()}
        for zone in ("cell_concs", "mem_concs", "env_concs")
    }


def cache(net):
    values = ions.data(molecule_source.cache(net))
    values["transporter_fluxes"] = fluxes(net)
    return ions.freeze(values)


def _flux_state(raw, definition):
    names = [row["name"] for row in definition["transporters"]]
    if not isinstance(raw, Mapping) or set(raw) != set(names):
        raise ValueError("Require every owned transporter flux cache; no silent reset")
    m = len(definition["radius_m"])
    for name in names:
        value = raw[name]
        if value is not None and (
            not isinstance(value, np.ndarray)
            or value.dtype != np.float64
            or value.shape != (m,)
            or value.flags.writeable
            or not np.isfinite(value).all()
        ):
            raise ValueError(
                "Require an immutable finite transporter flux vector or literal cold None"
            )


def checked_cache(raw, definition):
    molecule_source.checked_cache(raw, base_definition(definition))
    _flux_state(raw["transporter_fluxes"], definition)
    return ions.freeze(raw)


def prepare(
    arrays, *, ion_ids, parameters, definition, incoming_controls, incoming_cache, phase_kind
):
    _flux_state(incoming_cache.get("transporter_fluxes"), definition)
    net, sim, cells, p, phase = molecule_source.prepare(
        arrays,
        ion_ids=ion_ids,
        parameters=parameters,
        definition=base_definition(definition),
        incoming_controls=incoming_controls,
        incoming_cache=incoming_cache,
        phase_kind=phase_kind,
    )
    net.__class__ = _Network
    sim.zs = np.asarray(parameters["valence"], np.float64)
    sim.rho_pump = np.asarray(parameters["rho_pump"], np.float64).copy()
    cells.mem_vol = np.asarray(definition["membrane_volume_m3"], np.float64).copy()
    profiles = definition["transporter_profiles"]
    phase.dyna = SimpleNamespace(
        cell_target_inds={name: row["cells"] for name, row in profiles.items()},
        tissue_target_inds={name: row["membranes"] for name, row in profiles.items()},
        env_target_inds={name: row["environment"] for name, row in profiles.items()},
    )
    net.read_transporters(ions.data(definition["transporters"]), phase)
    net.write_transporters(sim, cells, p)
    for name, obj in net.transporters.items():
        value = incoming_cache["transporter_fluxes"][name]
        obj.flux = None if value is None else np.array(value, copy=True)
    net.transporter_frames = []

    def observe(stage, name, term, delta, actual):
        net.transporter_frames.append(
            ions.freeze(
                dict(
                    stage=stage,
                    name=name,
                    term=term,
                    delta=copy.deepcopy(delta),
                    concentrations=concentrations(net),
                    fluxes=fluxes(net),
                    extra_current_A_m2=net.extra_J_mem.copy(),
                    vm=actual.vm.copy(),
                    vgj=actual.vgj.copy(),
                )
            )
        )

    chemistry = net._observe_chem

    def observe_chem(stage, species, actual):
        chemistry(stage, species, actual)
        frame = ions.data(net.molecule_frames[-1])
        frame["cache"]["transporter_fluxes"] = fluxes(net)
        net.molecule_frames[-1] = ions.freeze(frame)

    net._observe_transporter, net._observe_chem = observe, observe_chem
    return net, sim, cells, p, phase


def execution_inputs(net, sim, cells, p, definition, ion_ids, values):
    return dict(
        conditioned_before_model_transporters=True,
        source_completed=False,
        definition=definition,
        ion_ids=ion_ids,
        valence=sim.zs.copy(),
        values_before=values,
        concentrations_before=concentrations(net),
        fluxes_before=fluxes(net),
        metadata={name: copy.deepcopy(vars(obj)) for name, obj in net.transporters.items()},
        geometry=dict(
            owner=cells.mem_to_cells.copy(),
            membrane_area_m2=cells.mem_sa.copy(),
            cell_volume_m3=cells.cell_vol.copy(),
            membrane_volume_m3=cells.mem_vol.copy(),
        ),
        rho_pump=sim.rho_pump.copy(),
        runtime_temperature_K=sim.T,
        F=p.F,
        R=p.R,
        dt_s=p.dt,
        bath_volume_m3=p.vol_env,
        extra_current_before_A_m2=net.extra_J_mem.copy(),
    )
