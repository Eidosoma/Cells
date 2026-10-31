# ruff: noqa: E501, E402, B007, B905
"""Owned literal modern-channel reader, factory, dispatch and complete caches.

Normal ECM SIM only. Numeric class methods and lower ECM math stay unchanged.
Gate-private fields are retained, and cold initializer failures remain raw.
"""

import math
from collections import OrderedDict
from collections.abc import Mapping
from types import SimpleNamespace

import numpy as np

from cells.processes import betse_channel_catalog_source as catalog
from cells.processes import betse_ecm_grn_source as base

clone, public = base.clone, base.public
MATERIAL_PAIRS, PARAMETERS = base.MATERIAL_PAIRS, base.PARAMETERS
logs, set_net_opts = base.logs, base.set_net_opts
BetseSimConfException = ValueError
SimPhaseKind = SimpleNamespace(INIT="INIT", SIM="SIM")
stb = SimpleNamespace(
    molecule_mover=base.molecule_mover,
    no_negs=base.molecule_source.no_negs,
    electroflux=base.electroflux,
    update_Co=base.update_Co,
)
material_values, owner_evidence = base.material_values, base.owner_evidence
new_trace = base.new_trace
FAMILIES = {
    "CaLeak": "Ca",
    "Ca_L2": "Ca",
    "Ca_L3": "Ca",
    "CatLeak": "Cat",
    "CatLeak2": "Cat",
    "Cav1p2": "Ca",
    "Cav1p3": "Ca",
    "Cav2p1": "Ca",
    "Cav2p2": "Ca",
    "Cav2p3": "Ca",
    "Cav3p1": "Ca",
    "Cav3p3": "Ca",
    "Cav_G": "Ca",
    "Cav_L_ML": "ML",
    "Cav_L_ML2": "ML",
    "Cav_N_ML": "ML",
    "Cav_T_ML": "ML",
    "ClLeak": "Cl",
    "HCN1": "Fun",
    "HCN2": "Fun",
    "HCN2_ML": "ML",
    "HCN2_cAMP": "Fun",
    "HCN4": "Fun",
    "HCN4_ML": "ML",
    "HCN4_cAMP": "Fun",
    "HCNLeak": "Fun",
    "KLeak": "K",
    "K_Fast": "K",
    "Kir2p1": "K",
    "Kir_ML": "ML",
    "Kv1p1": "K",
    "Kv1p2": "K",
    "Kv1p3": "K",
    "Kv1p3_ML": "ML",
    "Kv1p4": "K",
    "Kv1p5": "K",
    "Kv1p5S_ML": "ML",
    "Kv1p5_ML": "ML",
    "Kv1p6": "K",
    "Kv2p1": "K",
    "Kv2p1_ML": "ML",
    "Kv2p2": "K",
    "Kv3p1": "K",
    "Kv3p2": "K",
    "Kv3p3": "K",
    "Kv3p4": "K",
    "Kv_ML1": "ML",
    "NaLeak": "Na",
    "Nav1p2": "Na",
    "Nav1p3": "Na",
    "Nav1p6": "Na",
    "NavRat1": "Na",
    "NavRat2": "Na",
    "NavRat3": "Na",
    "Nav_ML": "ML",
}
ROUTES = {
    "CaLeak": [["Ca", 1.0]],
    "Ca_L2": [["Ca", 1.0]],
    "Ca_L3": [["Ca", 1.0]],
    "CatLeak": [["Na", 1.0], ["K", 1.0], ["Ca", 0.0]],
    "CatLeak2": [["Na", 1.0], ["K", 1.0], ["Ca", 1.0]],
    "Cav1p2": [["Ca", 1.0]],
    "Cav1p3": [["Ca", 1.0]],
    "Cav2p1": [["Ca", 1.0]],
    "Cav2p2": [["Ca", 1.0]],
    "Cav2p3": [["Ca", 1.0]],
    "Cav3p1": [["Ca", 1.0]],
    "Cav3p3": [["Ca", 1.0]],
    "Cav_G": [["Ca", 1.0]],
    "Cav_L_ML": [["Ca", 1.0]],
    "Cav_L_ML2": [["Ca", 1.0]],
    "Cav_N_ML": [["Ca", 1.0]],
    "Cav_T_ML": [["Ca", 1.0]],
    "ClLeak": [["Cl", 1.0]],
    "HCN1": [["Na", 0.2], ["K", 1.0], ["Ca", 0.05]],
    "HCN2": [["Na", 0.2], ["K", 1.0], ["Ca", 0.05]],
    "HCN2_ML": [["K", 1.0], ["Na", 0.2]],
    "HCN2_cAMP": [["Na", 0.2], ["K", 1.0], ["Ca", 0.05]],
    "HCN4": [["Na", 0.2], ["K", 1.0], ["Ca", 0.05]],
    "HCN4_ML": [["K", 1.0], ["Na", 0.2]],
    "HCN4_cAMP": [["Na", 0.2], ["K", 1.0], ["Ca", 0.05]],
    "HCNLeak": [["Na", 0.33], ["K", 1.0], ["Ca", 0.05]],
    "KLeak": [["K", 1.0]],
    "K_Fast": [["K", 1.0]],
    "Kir2p1": [["K", 1.0]],
    "Kir_ML": [["K", 1.0]],
    "Kv1p1": [["K", 1.0]],
    "Kv1p2": [["K", 1.0]],
    "Kv1p3": [["K", 1.0]],
    "Kv1p3_ML": [["K", 1.0]],
    "Kv1p4": [["K", 1.0]],
    "Kv1p5": [["K", 1.0]],
    "Kv1p5S_ML": [["K", 1.0]],
    "Kv1p5_ML": [["K", 1.0]],
    "Kv1p6": [["K", 1.0]],
    "Kv2p1": [["K", 1.0]],
    "Kv2p1_ML": [["K", 1.0]],
    "Kv2p2": [["K", 1.0]],
    "Kv3p1": [["K", 1.0]],
    "Kv3p2": [["K", 1.0]],
    "Kv3p3": [["K", 1.0]],
    "Kv3p4": [["K", 1.0]],
    "Kv_ML1": [["K", 1.0]],
    "NaLeak": [["Na", 1.0]],
    "Nav1p2": [["Na", 1.0]],
    "Nav1p3": [["Na", 1.0]],
    "Nav1p6": [["Na", 1.0]],
    "NavRat1": [["Na", 1.0]],
    "NavRat2": [["Na", 1.0]],
    "NavRat3": [["Na", 1.0]],
    "Nav_ML": [["Na", 1.0]],
}
vgna = SimpleNamespace(
    **{name: catalog.CLASSES[name] for name, family in FAMILIES.items() if family == "Na"}
)
vgk = SimpleNamespace(
    **{name: catalog.CLASSES[name] for name, family in FAMILIES.items() if family == "K"}
)
vgcl = SimpleNamespace(
    **{name: catalog.CLASSES[name] for name, family in FAMILIES.items() if family == "Cl"}
)
vgca = SimpleNamespace(
    **{name: catalog.CLASSES[name] for name, family in FAMILIES.items() if family == "Ca"}
)
vgfun = SimpleNamespace(
    **{name: catalog.CLASSES[name] for name, family in FAMILIES.items() if family == "Fun"}
)
vgcat = SimpleNamespace(
    **{name: catalog.CLASSES[name] for name, family in FAMILIES.items() if family == "Cat"}
)
vgml = SimpleNamespace(
    **{name: catalog.CLASSES[name] for name, family in FAMILIES.items() if family == "ML"}
)


class MasterOfNetworks(base.MasterOfNetworks):
    def read_channels(self, config_channels, phase):
        sim = phase.sim
        cells = phase.cells
        p = phase.p
        logs.log_info("Reading channel input data...")
        self.channels = OrderedDict({})
        for q, chan_dic in enumerate(config_channels):
            name = str(chan_dic["name"])
            self.channels[name] = Channel(sim, cells, p)
            obj = self.channels[name]
            obj.name = name
            obj.reaction_zone = "cell"
            obj.channel_class = chan_dic["channel class"]
            obj.channel_type = chan_dic["channel type"]
            chan_Dmem = chan_dic.get("max conductivity", None)
            if chan_Dmem is not None:
                obj.channelMax = chan_dic["max conductivity"]
            else:
                obj.channelMax = chan_dic["max Dm"]
            obj.channel_profiles_list = chan_dic["apply to"]
            obj.init_active = chan_dic.get("init active", True)
            obj.channel_activators_list = chan_dic.get("channel activators", None)
            obj.channel_activators_Km = chan_dic.get("activator Km", None)
            obj.channel_activators_n = chan_dic.get("activator n", None)
            obj.channel_activators_zone = chan_dic.get("activator zone", None)
            obj.channel_activators_max = chan_dic.get("activator max", None)
            obj.channel_inhibitors_list = chan_dic.get("channel inhibitors", None)
            obj.channel_inhibitors_Km = chan_dic.get("inhibitor Km", None)
            obj.channel_inhibitors_n = chan_dic.get("inhibitor n", None)
            obj.channel_inhibitors_zone = chan_dic.get("inhibitor zone", None)
            obj.channel_inhibitors_max = chan_dic.get("inhibitor max", None)
            p._catalog_observe("initialize_before", name, locals())
            obj.init_channel(obj.channel_class, obj.channel_type, obj.channelMax, phase)
            p._catalog_observe("initialize_after", name, locals())
            obj.channel_activators_zone, obj.channel_inhibitors_zone = self.default_zones(
                obj.channel_activators_zone,
                obj.channel_inhibitors_zone,
                obj.channel_activators_list,
                obj.channel_inhibitors_list,
            )
            a_list = obj.channel_activators_list
            Km_a_list = obj.channel_activators_Km
            n_a_list = obj.channel_activators_n
            zone_a = obj.channel_activators_zone
            max_a = obj.channel_activators_max
            i_list = obj.channel_inhibitors_list
            Km_i_list = obj.channel_inhibitors_Km
            n_i_list = obj.channel_inhibitors_n
            zone_i = obj.channel_inhibitors_zone
            max_i = obj.channel_inhibitors_max
            if max_a is None and a_list is not None:
                max_a = np.ones(len(a_list))
            if max_i is None and i_list is not None:
                max_i = np.zeros(len(i_list))
            tex_vars = []
            all_alpha, alpha_tex, tex_vars = self.get_influencers(
                a_list,
                Km_a_list,
                n_a_list,
                i_list,
                Km_i_list,
                n_i_list,
                tex_list=tex_vars,
                reaction_zone="mem",
                zone_tags_a=zone_a,
                zone_tags_i=zone_i,
                in_mem_tag=True,
                max_activators=max_a,
                max_inhibitors=max_i,
            )
            obj.alpha_eval_string = "(" + all_alpha + ")"
            p._catalog_observe("configuration_after", name, locals())

    def run_loop_channels(self, phase):
        sim = phase.sim
        cells = phase.cells
        p = phase.p
        globalo = globals()
        localo = locals()
        for i, name in enumerate(self.channels):
            chan = self.channels[name]
            p._catalog_observe("population_before", name, locals())
            pass_chan = False
            if phase.kind is SimPhaseKind.INIT and chan.init_active is False:
                pass_chan = True
            if pass_chan is False:
                moddy = eval(chan.alpha_eval_string, globalo, localo)
                p._catalog_observe("modulator", name, locals())
                chan.channel_core.modulator = moddy
                chan.channel_core.run(sim.vm, p)
                p._catalog_observe("gate_after", name, locals())
                for ion, rel_perm in zip(chan.channel_core.ions, chan.channel_core.rel_perm):
                    zzz = self.zmol[ion]
                    ioni = sim.get_ion(ion)
                    p._catalog_observe("route_before", name, locals())
                    DChan = chan.channel_core.P * rel_perm * chan.maxDm * moddy
                    if ion in self.env_concs:
                        cenv = self.env_concs[ion]
                    if ion in self.cell_concs:
                        ccell = self.cell_concs[ion]
                        cmem = self.cell_concs[ion][cells.mem_to_cells]
                    IdM = np.ones(sim.mdl)
                    if p.is_ecm:
                        f_ED = stb.electroflux(
                            cenv[cells.map_mem2ecm],
                            cmem,
                            DChan,
                            IdM * p.tm,
                            zzz * IdM,
                            sim.vm,
                            sim.T,
                            p,
                            rho=sim.rho_channel,
                        )
                        p._catalog_observe("flux_after", name, locals())
                    else:
                        f_ED = stb.electroflux(
                            cenv,
                            cmem,
                            DChan,
                            IdM * p.tm,
                            zzz * IdM,
                            sim.vm,
                            sim.T,
                            p,
                            rho=sim.rho_channel,
                        )
                        p._catalog_observe("flux_after", name, locals())
                    self.cell_concs[ion], self.mem_concs[ion], self.env_concs[ion] = stb.update_Co(
                        sim, ccell, cmem, cenv, f_ED, cells, p, ignoreECM=True
                    )
                    self.extra_J_mem += -f_ED * p.F * zzz
                    chan.channel_core.chan_flux = f_ED
                    chan.channel_core.DChan = DChan
                    p._catalog_observe("route_after", name, locals())
                p._catalog_observe("population_after", name, locals())


class Channel(object):
    def __init__(self, sim, cells, p):
        self.flux_time = []

    def init_channel(self, ion_string, type_string, max_val, phase):
        sim = phase.sim
        cells = phase.cells
        p = phase.p
        self.maxDm = max_val
        if (
            self.channel_profiles_list is not None
            and self.channel_profiles_list != "all"
            and (self.channel_profiles_list != "express")
        ):
            targets = []
            for profile in self.channel_profiles_list:
                targets_mem = sim.dyna.tissue_target_inds[profile]
                targets.extend(targets_mem)
            targets = np.asarray(targets)
        elif self.channel_profiles_list is None or self.channel_profiles_list == "all":
            targets = np.asarray(cells.mem_i)
        elif self.channel_profiles_list == "express":
            targets = np.asarray(cells.mem_i)
            self.expr_map_mem = np.zeros(sim.mdl)
            for region, val in p.expression_data[self.name].items():
                tinds_mem = phase.dyna.tissue_target_inds[region]
                self.expr_map_mem[tinds_mem] = val
            self.channelMax = self.channelMax * self.expr_map_mem
        if ion_string == "Na":
            class_string = vgna
        elif ion_string == "K":
            class_string = vgk
        elif ion_string == "Cl":
            class_string = vgcl
        elif ion_string == "Ca":
            class_string = vgca
        elif ion_string == "Fun":
            class_string = vgfun
        elif ion_string == "Cat":
            class_string = vgcat
        elif ion_string == "ML":
            class_string = vgml
        else:
            raise BetseSimConfException(
                "Substance-modulated ion type not available. Valid choices: Na, K, Ca, NaP, Kir, and Fun"
            )
        self.channel_core = getattr(class_string, type_string)()
        self.channel_core.init(sim.vm, cells, p, targets=targets)
        self.channel_core.chan_flux = np.zeros(sim.mdl)
        self.channel_core.DChan = None


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


def science():
    return base.science() | dict(
        MasterOfGenes=MasterOfGenes,
        MasterOfNetworks=MasterOfNetworks,
        Channel=Channel,
        initialize_owner=initialize_owner,
        dispatch=dispatch,
        class_for=class_for,
    )


def class_for(name):
    return catalog.CLASSES[name]


def validate_catalog(declaration, ids, m):
    if (
        set(declaration) != {"kind", "populations", "tissue_profiles", "phase", "provenance"}
        or declaration["kind"] != "cells.native_ECM_modern_channel_configuration@1"
        or declaration["phase"] != "SIM"
    ):
        raise ValueError("Require separately declared normal SIM channel configuration")
    if not isinstance(declaration["provenance"], str) or not declaration["provenance"].strip():
        raise ValueError("Require channel configuration provenance")
    profiles = declaration["tissue_profiles"]
    if not isinstance(profiles, dict) or any(
        not isinstance(k, str)
        or not k
        or not isinstance(v, list)
        or any(type(i) is not int or not 0 <= i < m for i in v)
        for k, v in profiles.items()
    ):
        raise ValueError("Require explicit prepared tissue membrane index maps")
    rows = declaration["populations"]
    if rows is None:
        return
    if not isinstance(rows, list) or len(rows) > 16:
        raise ValueError("Require bounded ordered native channel populations")
    names = []
    for row in rows:
        required = {"name", "channel class", "channel type", "apply to"}
        allowed = (
            required
            | {"max Dm", "max conductivity", "init active"}
            | {
                k
                for role in ("activator", "inhibitor")
                for k in ("channel " + role + "s", role + " Km", role + " n", role + " zone")
            }
        )
        if not isinstance(row, dict) or not required <= row.keys() or set(row) - allowed:
            raise ValueError("Unsupported modern channel configuration branch")
        name, cls, family = row["name"], row["channel type"], row["channel class"]
        if not isinstance(name, str) or not name or name in names:
            raise ValueError("Require unique native channel names")
        names.append(name)
        if cls not in FAMILIES or FAMILIES[cls] != family:
            raise ValueError("Require a reachable modern catalog factory class")
        if any(ion not in ids for ion, _ in ROUTES[cls]):
            raise ValueError("Require every original channel route ion role")
        conductance = row.get("max conductivity", None)
        maximum = conductance if conductance is not None else row.get("max Dm", None)
        if type(maximum) not in (float, int) or not math.isfinite(maximum) or maximum < 0:
            raise ValueError("Require finite nonnegative native channel maximum")
        if type(row.get("init active", True)) is not bool:
            raise ValueError("Require the original Boolean init active flag")
        targets = row["apply to"]
        if targets == "express":
            raise ValueError("Expression profiles require separately owned expression/tissue state")
        if targets not in (None, "all"):
            if not isinstance(targets, list) or any(k not in profiles for k in targets):
                raise ValueError("Require explicit prepared tissue membrane index maps")
        for role in ("activator", "inhibitor"):
            species = row.get("channel " + role + "s")
            if species is None:
                if any(row.get(role + " " + key) is not None for key in ("Km", "n", "zone")):
                    raise ValueError("Require complete native channel modifier lists")
                continue
            if not isinstance(species, list) or not 1 <= len(species) <= 4:
                raise ValueError("Require complete native channel modifier lists")
            for key in ("Km", "n"):
                values = row.get(role + " " + key)
                if (
                    not isinstance(values, list)
                    or len(values) != len(species)
                    or any(
                        type(v) not in (float, int) or not math.isfinite(v) or v <= 0
                        for v in values
                    )
                ):
                    raise ValueError("Require complete native channel modifier lists")
            zones = row.get(role + " zone")
            if zones is not None and (
                not isinstance(zones, list)
                or len(zones) != len(species)
                or any(z not in ("cell", "env") for z in zones)
            ):
                raise ValueError("Require explicit membrane/environment channel modifier zones")
            if any(value not in set(ids) | {"X", "Y"} for value in species):
                raise ValueError(
                    "Channel expression labels require separately qualified regulation"
                )


def configure(ctx, declaration):
    validate_catalog(declaration, ctx.ion_ids, len(ctx.cells.mem_i))
    ctx.catalog = clone(declaration)
    ctx.definition = clone(ctx.definition)
    ctx.definition["configuration"]["channels"] = clone(declaration["populations"])
    ctx.p.grn = SimpleNamespace(conf=clone(ctx.definition["configuration"]))
    prepared = {
        key: np.asarray(value, np.int64).copy()
        for key, value in declaration["tissue_profiles"].items()
    }
    ctx.sim.dyna = SimpleNamespace(tissue_target_inds=prepared)
    ctx.phase.dyna = ctx.sim.dyna
    ctx.initial_channel_fields = {}
    ctx.channel_calls = {row["name"]: 0 for row in declaration["populations"] or []}
    ctx.trace.update(channel_events=[], channel_initializations=[])
    install_channel_observer(ctx)
    return ctx


def channel_fields(net):
    return {
        name: dict(
            fields={k: clone(v) for k, v in vars(obj).items() if k != "channel_core"},
            core_class=getattr(obj, "channel_type", None),
            core_fields=None if not hasattr(obj, "channel_core") else clone(vars(obj.channel_core)),
        )
        for name, obj in getattr(net, "channels", {}).items()
    }


def wire(owner, sim):
    result = base.wire(owner, sim)
    net = getattr(owner, "core", None) if owner is not None else None
    result["channel_fields"] = {} if net is None else channel_fields(net)
    return result


def cache(ctx):
    return dict(
        kind="cells.ecm_catalog_grn_owner_cache@1",
        wire=wire(getattr(ctx.sim, "grn", None), ctx.sim),
        coefficient_fields={
            name: clone(getattr(ctx.sim, name))
            for name in ("D_env_weight", "D_env_weight_base", "TJ_targets")
            if hasattr(ctx.sim, name)
        },
        initial_channel_fields=clone(ctx.initial_channel_fields),
        channel_calls=clone(ctx.channel_calls),
    )


def cold(ctx):
    ctx.sim.grn = None
    ctx.phase.kind = "INIT"
    ctx.p.substances_affect_charge = ctx.definition["cold_publish"]
    science()["initialize_owner"](ctx.sim, 0.0, ctx.phase, ctx.cells, ctx.p)
    ctx.initial_channel_fields = channel_fields(ctx.sim.grn.core)
    return cache(ctx)


def install_channel_observer(ctx):
    def observe(stage, name, local):
        obj = local.get("chan", local.get("obj"))
        # Constructor hooks have obj; warm hooks have chan. Preserve raw absent fields.
        values = dict(
            stage=stage,
            name=name,
            values=material_values(ctx.sim),
            cache=cache(ctx),
            fields={
                key: clone(local[key])
                for key in (
                    "ion",
                    "rel_perm",
                    "zzz",
                    "ioni",
                    "DChan",
                    "cenv",
                    "ccell",
                    "cmem",
                    "f_ED",
                    "moddy",
                )
                if key in local
            },
            population=None
            if obj is None
            else dict(
                fields={k: clone(v) for k, v in vars(obj).items() if k != "channel_core"},
                core_fields=None
                if not hasattr(obj, "channel_core")
                else clone(vars(obj.channel_core)),
            ),
            incoming_current=clone(ctx.sim.grn.core.extra_J_mem),
        )
        if stage.startswith("initialize") or stage == "configuration_after":
            ctx.trace["channel_initializations"].append(values)
        else:
            if stage == "population_after":
                ctx.channel_calls[name] += 1
                values["cache"] = cache(ctx)
            ctx.trace["channel_events"].append(values)

    ctx.p._catalog_observe = observe


def validate_cached_channels(ctx, incoming):
    rows = ctx.catalog["populations"] or []
    fields = incoming["wire"]["channel_fields"]
    initial = incoming["initial_channel_fields"]
    calls = incoming["channel_calls"]
    expected = [row["name"] for row in rows]
    if list(fields) != expected or list(initial) != expected or list(calls) != expected:
        raise ValueError("Require every configured channel and complete constructor/cache metadata")
    for row in rows:
        name, cls = row["name"], row["channel type"]
        current, origin = fields[name], initial[name]
        if (
            set(current) != {"fields", "core_class", "core_fields"}
            or set(origin) != set(current)
            or current["core_class"] != cls
            or origin["core_class"] != cls
            or current["core_fields"] is None
            or origin["core_fields"] is None
            or type(calls[name]) is not int
            or not 0 <= calls[name] <= 3
            or set(current["fields"]) != set(origin["fields"])
        ):
            raise ValueError(
                "Require every configured channel and complete constructor/cache metadata"
            )
        a, b = current["core_fields"], origin["core_fields"]
        # Use the literal class write inventory, as the ordinary catalog does.
        # Funny-current classes first create vrev during _calculate_state().
        warm = set(catalog.CALCULATED_FIELDS[cls]) | {"P"} if calls[name] else set()
        if set(a) != set(b) | warm:
            raise ValueError("Require all source-private initialized and hot gate fields")
        if not equal_tree(current["fields"], origin["fields"]):
            raise ValueError("Changed native channel routing or constructor metadata")
        dynamic = {
            "m",
            "h",
            "P",
            "modulator",
            "chan_flux",
            "DChan",
            *catalog.CALCULATED_FIELDS[cls],
        }
        for key in set(b) - dynamic:
            if not equal_tree(a.get(key), b[key]):
                raise ValueError("Changed native channel routing or constructor metadata")
        for key in ("targets", "data_length", "mdl", "ions", "rel_perm", "time_unit"):
            if key in b and not np.array_equal(a.get(key), b[key]):
                raise ValueError("Changed native channel routing or constructor metadata")
        targets = []
        if row["apply to"] in (None, "all"):
            targets = list(ctx.cells.mem_i)
        else:
            for key in row["apply to"]:
                targets.extend(ctx.catalog["tissue_profiles"][key])
        if not np.array_equal(b.get("targets"), targets):
            raise ValueError("Changed native channel routing or constructor metadata")
        if current["fields"]["name"] != name or current["fields"]["channel_type"] != cls:
            raise ValueError("Changed native channel routing or constructor metadata")
        for state in (a, b):
            if not finite_tree(state):
                raise ValueError(
                    "Port requires finite complete channel caches; native return retained"
                )
    actual_flag = ctx.catalog["populations"] is not None
    if incoming["wire"]["owner_fields"].get("channels") is not actual_flag:
        raise ValueError("Require the actual cold-configured channel owner flag")


def equal_tree(a, b):
    if isinstance(a, Mapping) or isinstance(b, Mapping):
        return (
            isinstance(a, Mapping)
            and isinstance(b, Mapping)
            and list(a) == list(b)
            and all(equal_tree(a[k], b[k]) for k in a)
        )
    if isinstance(a, (list, tuple)) or isinstance(b, (list, tuple)):
        return (
            isinstance(a, (list, tuple))
            and isinstance(b, (list, tuple))
            and len(a) == len(b)
            and all(equal_tree(x, y) for x, y in zip(a, b, strict=True))
        )
    if isinstance(a, np.ndarray) or isinstance(b, np.ndarray):
        return (
            isinstance(a, np.ndarray)
            and isinstance(b, np.ndarray)
            and a.dtype == b.dtype
            and np.array_equal(a, b)
        )
    return a == b


def finite_tree(value):
    if isinstance(value, Mapping):
        return all(finite_tree(v) for v in value.values())
    if isinstance(value, (tuple, list)):
        return all(finite_tree(v) for v in value)
    if isinstance(value, (np.ndarray, np.generic, float)):
        return bool(np.isfinite(value).all())
    return True


def restore(ctx, incoming):
    if incoming is None or incoming.get("kind") != "cells.ecm_catalog_grn_owner_cache@1":
        raise ValueError("Require complete ECM catalog GRN owner cache")
    raw = incoming["wire"]
    if set(raw) != {
        "owner_fields",
        "core_fields",
        "molecule_fields",
        "reaction_fields",
        "modulator_fields",
        "ion_boundary_state",
        "simulator_fields",
        "channel_fields",
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
    validate_cached_channels(ctx, incoming)
    ctx.initial_channel_fields = clone(incoming["initial_channel_fields"])
    ctx.channel_calls = clone(incoming["channel_calls"])
    api = science()
    owner = object.__new__(api["MasterOfGenes"])
    vars(owner).update(clone(raw["owner_fields"]))
    net = object.__new__(api["MasterOfNetworks"])
    vars(net).update(clone(raw["core_fields"]))
    owner.core, ctx.sim.grn = (net, owner)
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
    for name, saved in raw["channel_fields"].items():
        obj = object.__new__(api["Channel"])
        vars(obj).update(clone(saved["fields"]))
        core = object.__new__(api["class_for"](saved["core_class"]))
        vars(core).update(clone(saved["core_fields"]))
        obj.channel_core = core
        net.channels[name] = obj
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


def before(ctx, material_declaration):
    sim, p, cells, net = (ctx.sim, ctx.p, ctx.cells, ctx.net)
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


def attach(ctx, material_declaration, observer=None, channel_observer=None):
    sim, p, net = (ctx.sim, ctx.p, ctx.net)

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
            ctx.trace["before_channels"] = before(ctx, material_declaration)
            ctx.trace["before_channels"].update(mode="channels", catalog=clone(ctx.catalog))
            if channel_observer is not None:
                channel_observer(clone(ctx.trace["before_channels"]))
        if stage == "run_loop_channels" or (stage == "clear_run_loop" and not ctx.sim.grn.channels):
            ctx.trace["before"] = before(ctx, material_declaration)
            if observer is not None:
                observer(clone(ctx.trace["before"]))

    (
        net._observe_chem,
        net._observe_rhs,
        net._observe_control,
        net._observe_dispatch,
        p._mover_observe,
    ) = (chemistry, rhs, control, dispatched, mover)


def run_dispatch(
    ctx, material_declaration, publication, source_time_s, observer=None, channel_observer=None
):
    ctx.p.substances_affect_charge = publication
    ctx.phase.kind = "SIM"
    ctx.net = ctx.sim.grn.core
    attach(ctx, material_declaration, observer, channel_observer)
    try:
        science()["dispatch"](ctx.sim, source_time_s, ctx.phase, ctx.cells, ctx.p)
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
                (row["stage"] == "transport_after" for row in ctx.trace["molecule_frames"])
            ),
        )
    return ctx.trace
