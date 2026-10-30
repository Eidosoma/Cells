# ruff: noqa: B007, B905, E501, F841, E402
"""Literal standalone run_core_sim at an explicit prepared-phase boundary.

Filesystem persistence is captured in memory; full SimRunner loading is outside
this boundary. Original clocks, reinitialization and sampled state execute.
"""

import csv
import io
import os
from collections import OrderedDict
from collections.abc import Mapping
from dataclasses import dataclass
from types import SimpleNamespace

import numpy as np

from cells.processes import betse_normal_current as current
from cells.processes import betse_normal_grn_source as base
from cells.processes import betse_normal_ion_join as ions

clone, public, wire = base.clone, base.public, base.wire
set_net_opts = base.set_net_opts
BetseSimException = base.molecule_source.BetseSimException


class BetseSimConfException(BetseSimException):
    pass


logs = SimpleNamespace(log_info=lambda *_: None, log_warning=lambda *_: None)
fh = SimpleNamespace(saveSim=lambda filename, data: save_boundary(filename, data))
pathnames = SimpleNamespace(join=os.path.join)
dirs = SimpleNamespace(make_unless_dir=lambda path: directory_boundary(path))
plt = viz = None
_ACTIVE = None


class MasterOfNetworks(base.MasterOfNetworks):
    def init_saving(self, cells, p, plot_type="init", nested_folder_name="Molecules"):
        if plot_type == "sim":
            self.resultsPath = pathnames.join(p.sim_export_dirname, nested_folder_name)
        elif plot_type == "init":
            self.resultsPath = pathnames.join(p.init_export_dirname, nested_folder_name)
        elif plot_type == "grn":
            self.resultsPath = pathnames.join(p.grn_pickle_dirname, nested_folder_name)
        dirs.make_unless_dir(self.resultsPath)
        self.imagePath = pathnames.join(self.resultsPath, "fig_")
        if p.visual.single_cell_index not in cells.cell_i:
            raise BetseSimConfException(
                'The "plot cell" defined in the "results" section of your configuration file does not exist in your cluster. Choose a plot cell number smaller than the maximum cell number.'
            )

    def clear_cache(self):
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

    def write_data(self, sim, cells, p):
        for name in self.molecules:
            obj = self.molecules[name]
            obj.c_mems_time.append(obj.cc_at_mem * 1)
            obj.c_cells_time.append(obj.c_cells * 1)
            cc_env = np.copy(obj.c_env * 1)
            obj.c_env_time.append(cc_env * 1)
            if self.mit_enabled:
                obj.c_mit_time.append(obj.c_mit * 1)
        for name in self.transporters:
            obj = self.transporters[name]
            if obj.flux is not None:
                obj.flux_time.append(obj.flux * 1)
        for name in self.channels:
            obj = self.channels[name]
            if obj.channel_core.DChan is not None:
                obj.D_time.append(obj.channel_core.DChan * 1)
            if obj.channel_core.chan_flux is not None:
                obj.flux_time.append(obj.channel_core.chan_flux * 1)
        for i, name in enumerate(self.reactions):
            obj = self.reactions[name]
            if self.reaction_rates is not None:
                obj.rate_time.append(self.reaction_rates[i])
        if self.mit_enabled:
            self.vmit_time.append(self.mit.Vmit[:])
        self.chi_time.append(self.chi)

    def report(self, sim, p):
        logs.log_info(
            "time: "
            + str(np.round(sim.time[-1], 2))
            + " s of "
            + str(np.round(p.total_time, 2))
            + " s"
        )
        for name in self.molecules:
            obj = self.molecules[name]
            if self.mit_enabled:
                logs.log_info(
                    "Average "
                    + str(name)
                    + " in the mitochondria: "
                    + str(np.round(obj.c_mit.mean(), 4))
                    + " mmol/L"
                )
            logs.log_info(
                "Average "
                + str(name)
                + " in the cell: "
                + str(np.round(obj.c_cells.mean(), 4))
                + " mmol/L"
            )
        if self.mit_enabled:
            logs.log_info(
                "Average Vmit: " + str(np.round(1000.0 * self.mit.Vmit.mean(), 4)) + " mV"
            )
        if self.chi.mean() != 0.0:
            logs.log_info("Energy charge: " + str(np.round(self.chi.mean(), 3)))
        if "H+" in self.molecules:
            obj = self.molecules["H+"]
            ph = -np.log10(1e-06 * obj.c_cells.mean())
            phe = -np.log10(1e-06 * obj.c_env.mean())
            logs.log_info("Average pH in the cell: " + str(np.round(ph, 2)))
        logs.log_info(
            "Average Na "
            + " in the cell: "
            + str(np.round(sim.cc_cells[sim.iNa].mean(), 4))
            + " mmol/L"
        )
        logs.log_info(
            "Average K "
            + " in the cell: "
            + str(np.round(sim.cc_cells[sim.iK].mean(), 4))
            + " mmol/L"
        )
        if p.ions_dict["Cl"] == 1:
            logs.log_info(
                "Average Cl "
                + " in the cell: "
                + str(np.round(sim.cc_cells[sim.iCl].mean(), 4))
                + " mmol/L"
            )
        if p.ions_dict["Ca"] == 1:
            logs.log_info(
                "Average Ca "
                + " in the cell: "
                + str(np.round(1000000.0 * sim.cc_cells[sim.iCa].mean(), 4))
                + " nmol/L"
            )
        logs.log_info("-------------------------------------------------------------------")

    def export_equations(self, p):
        saveData = pathnames.join(self.resultsPath, "NetworkModelLatexEquations.csv")
        with open(saveData, "w", newline="") as csvfile:
            eqwriter = csv.writer(csvfile, delimiter="\t", quotechar="|", quoting=csv.QUOTE_NONE)
            for mol in self.molecules:
                if self.molecules[mol].simple_growth is True:
                    text_var = self.molecules[mol].gad_tex_vars
                    eq_var = self.molecules[mol].gad_tex_string
                    eqwriter.writerow([mol, eq_var, text_var])
            for rea in self.reactions:
                text_var = self.reactions[rea].reaction_tex_vars
                eq_var = self.reactions[rea].reaction_tex_string
                eqwriter.writerow([rea, eq_var, text_var])
            for rea in self.reactions_mit:
                text_var = self.reactions_mit[rea].reaction_tex_vars
                eq_var = self.reactions_mit[rea].reaction_tex_string
                eqwriter.writerow([rea, eq_var, text_var])
            for trans in self.transporters:
                text_var = self.transporters[trans].transporter_tex_vars
                eq_var = self.transporters[trans].transporter_tex_string
                eqwriter.writerow([trans, eq_var, text_var])

    def export_eval_strings(self, p):
        saveData = pathnames.join(self.resultsPath, "NetworkModelEvalStrings.csv")
        with open(saveData, "w", newline="") as csvfile:
            eqwriter = csv.writer(csvfile, delimiter="\t", quotechar="|", quoting=csv.QUOTE_NONE)
            for mol in self.molecules:
                if self.molecules[mol].simple_growth is True:
                    eq_var = self.molecules[mol].gad_eval_string
                    eqwriter.writerow([mol, eq_var])
            for rea in self.reactions:
                eq_var = self.reactions[rea].reaction_eval_string
                eqwriter.writerow([rea, eq_var])
            for rea in self.reactions_mit:
                eq_var = self.reactions_mit[rea].reaction_eval_string
                eqwriter.writerow([rea, eq_var])
            for trans in self.transporters:
                eq_var = self.transporters[trans].transporter_eval_string
                eqwriter.writerow([trans, eq_var])


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

    def run_core_sim(self, phase):
        cells = phase.cells
        p = phase.p
        sim = phase.sim
        p.substances_affect_charge = False
        p.dt = p.grn_dt
        p.init_time_total = p.grn_total_time
        p.init_time_sampling = p.grn_tsample
        p.init_tsteps = int(p.init_time_total / p.dt)
        p.resample = p.init_time_sampling
        p.total_time = p.init_time_total
        p.t_resample = p.resample / p.dt
        loop_time_step_max = p.init_tsteps
        loop_seconds_max = loop_time_step_max * p.dt
        tt = np.linspace(0, loop_seconds_max, loop_time_step_max)
        tsamples = set()
        i = 0
        while i < len(tt) - p.t_resample:
            i = int(i + p.t_resample)
            tsamples.add(tt[i])
        observe("before_reinitialize", self, phase, locals())
        self.reinitialize(phase)
        observe("after_reinitialize", self, phase, locals())
        observe("before_clear_cache", self, phase, locals())
        self.core.clear_cache()
        observe("after_clear_cache", self, phase, locals())
        self.time = []
        self.mod_after_cut = False
        if self.recalc_fluid:
            logs.log_info("Calculating fluid in terms of endogenous currents...")
            p.fluid_flow = True
            cc = sim.cc_env.mean(axis=0).reshape(cells.X.shape)
            zz = sim.zs.mean()
            sim.u_env_x = -sim.J_env_x / (p.F * cc * zz)
            sim.u_env_y = -sim.J_env_y / (p.F * cc * zz)
        for t in tt:
            if self.transporters:
                self.core.run_loop_transporters(t, sim, cells, p)
            observe("before_run_loop", self, phase, locals())
            self.core.run_loop(phase=phase, t=t)
            observe("after_run_loop", self, phase, locals())
            if p.grn_runmodesim and (not self.mod_after_cut) and (t >= p.event_cut_time):
                phase.dyna.fire_events(phase=phase, t=t)
                if phase.dyna.event_cut.is_fired and (not self.mod_after_cut):
                    self.core.mod_after_cut_event(
                        phase, sim.target_inds_cell_o, sim.target_inds_mem_o
                    )
                    self.core.redefine_dynamic_dics(sim, cells, p)
                    logs.log_info("Reinitializing the gene regulatory network for simulation...")
                    observe("before_reinitialize", self, phase, locals())
                    self.reinitialize(phase)
                    observe("after_reinitialize", self, phase, locals())
                    self.mod_after_cut = True
            if t in tsamples:
                sim.time.append(t)
                logs.log_info(
                    "------------------" + str(np.round(t, 3)) + " s --------------------"
                )
                self.time.append(t)
                observe("before_write_data", self, phase, locals())
                self.core.write_data(sim, cells, p)
                observe("after_write_data", self, phase, locals())
                self.core.report(sim, p)
        logs.log_info("Saving simulation...")
        datadump = [self, cells, p]
        fh.saveSim(p.grn_pickle_filename, datadump)
        self.core.init_saving(cells, p, plot_type="grn", nested_folder_name="RESULTS")
        if self.recalc_fluid:
            logs.log_info("Plotting fluid flow used in GRN simulation")
            plt.figure()
            ax = plt.subplot(111)
            viz.plotStreamField(
                1000000000.0 * sim.u_env_x,
                1000000000.0 * sim.u_env_y,
                cells,
                p,
                plot_ecm=True,
                title="Final Fluid Velocity in Environment",
                cb_title="Velocity [nm/s]",
            )
            if p.autosave is True:
                savename = self.core.imagePath + "Fluid_ECM" + ".png"
                plt.savefig(savename, format="png", transparent=True)
            if p.turn_all_plots_off is False:
                plt.show(block=False)
        self.core.export_eval_strings(p)
        self.core.export_equations(p)
        message = "Gene regulatory network simulation saved to" + " " + p.grn_pickle_filename
        logs.log_info(message)
        logs.log_info("-------------------Simulation Complete!-----------------------")


def start_new(self, phase):
    logs.log_info("Initializing the gene regulatory network...")
    MoG = MasterOfGenes(self._p)
    created(MoG, phase)
    MoG.read_gene_config(phase)
    return MoG


import math
from contextlib import contextmanager


def outside(*args, **kwargs):
    raise ValueError(
        "Standalone boundary excludes ECM, mitochondria, fluid, cuts and file restarts"
    )


def validate(inputs):
    if inputs.get("kind") != "cells.betse_sim_grn_inputs@1":
        raise ValueError("Require explicit standalone GRN phase inputs")
    scope = inputs["scope"]
    if inputs["ion_definition"]["parameters"]["is_ecm"] is not False:
        raise ValueError("Standalone ECM requires a separate spatial phase")
    if scope["mitochondria"] is not False:
        raise ValueError("Standalone mitochondria require separate organelle state")
    if scope["fluid"] is not False or scope["cuts"] is not False:
        raise ValueError("Standalone fluid and cuts require separate phase dynamics")
    if scope["grn_unpickle_filename"] is not None:
        raise ValueError("File restart requires a separate persistence boundary")
    if not 1 <= len(inputs["calls"]) <= 3:
        raise ValueError("Require one to three bounded standalone invocations")
    for call in inputs["calls"]:
        values = [call[k] for k in ("dt_s", "total_s", "sample_s")]
        if any(type(v) not in (int, float) or not math.isfinite(v) or v <= 0 for v in values):
            raise ValueError("Require finite positive standalone clocks")
        if call["sample_s"] < call["dt_s"]:
            raise ValueError("Sampling below dt stalls the source sampling-index loop")
        if not 1 <= int(call["total_s"] / call["dt_s"]) <= 8:
            raise ValueError("Require one to eight source clock points")
        if call["raw_fault"] not in (None, "missing_Y_Dm"):
            raise ValueError("Undeclared standalone partial failure")
        if type(call["plot_cell"]) is not int:
            raise ValueError("Require an explicit integer plot-cell index")
    g = inputs["ion_definition"]["geometry"]
    if (
        not 1 <= len(g["cell_ids"]) <= 16
        or not 1 <= len(g["owner"]) <= 128
        or not 1 <= len(inputs["ion_definition"]["ions"]["ids"]) <= 32
    ):
        raise ValueError("Refuse an unbounded standalone phase")
    initial = inputs["initial"]
    n, m, s = len(g["cell_ids"]), len(g["owner"]), len(inputs["ion_definition"]["ions"]["ids"])
    for key, shape in (
        ("cell_mol_m3", (s, n)),
        ("membrane_mol_m3", (s, m)),
        ("bath_mol_m3", (s, m)),
        ("voltage_V", (m,)),
        ("junction_voltage_V", (m,)),
        ("gap_open", (m,)),
    ):
        value = np.asarray(initial[key], np.float64)
        if value.shape != shape or not np.isfinite(value).all():
            raise ValueError("Require complete finite standalone phase buffers")
        if "mol_m3" in key and np.any(value < 0):
            raise ValueError("Require nonnegative standalone concentrations")
    if not {"Na", "K", "Cl", "Ca"} <= set(inputs["ion_definition"]["ions"]["ids"]):
        raise ValueError("Standalone reports require actual Na/K/Cl/Ca rows")
    net = inputs["network"]
    if set(net["grn_configuration"]) - {
        "biomolecules",
        "reactions",
        "modulators",
        "time dilation factor",
    }:
        raise ValueError("Standalone configured optional branches need a separate contract")
    if type(net["grn_initialization_publish"]) is not bool:
        raise ValueError("Require explicit cold charge publication")
    if any(row["z"] != 0.0 for row in net["grn_configuration"]["biomolecules"]):
        raise ValueError("Standalone charged cold initialization is separately scoped")


def new_trace():
    return dict(events=[], steps=[], molecule_frames=[], mover_frames=[], io_events=[])


def make_context(inputs):
    definition, initial = inputs["ion_definition"], inputs["initial"]
    g, ion, rawp = definition["geometry"], definition["ions"], definition["parameters"]
    n, m = len(g["cell_ids"]), len(g["owner"])
    sim = SimpleNamespace(
        cdl=n,
        mdl=m,
        edl=m,
        cc_cells=np.asarray(initial["cell_mol_m3"], np.float64).copy(),
        cc_at_mem=np.asarray(initial["membrane_mol_m3"], np.float64).copy(),
        cc_env=np.asarray(initial["bath_mol_m3"], np.float64).copy(),
        vm=np.asarray(initial["voltage_V"], np.float64).copy(),
        vgj=np.asarray(initial["junction_voltage_V"], np.float64).copy(),
        gjopen=np.asarray(initial["gap_open"], np.float64).copy(),
        zs=np.asarray(ion["valence"], np.float64),
        Dm_cells=np.asarray(ion["membrane_diffusion_m2_s"], np.float64),
        T=inputs["runtime_temperature_K"],
        rho_channel=np.ones(m),
        gj_block=np.asarray(inputs["network"]["initial_controls"]["gj_block"], np.float64).copy(),
        NaKATP_block=np.asarray(
            inputs["network"]["initial_controls"]["NaKATP_block"], np.float64
        ).copy(),
        extra_rho_cells=np.asarray(inputs["incoming_charge_C_m3"], np.float64).copy(),
        extra_J_mem=np.asarray(inputs["incoming_current_A_m2"], np.float64).copy(),
        c_env_bound=np.asarray(inputs["network"]["ion_boundary_mM"], np.float64).copy(),
        time=clone(inputs["simulator_time_before"]),
    )
    sim.get_ion = lambda name: ion["ids"].index(name)
    for name in ("Na", "K", "Cl", "Ca"):
        setattr(sim, "i" + name, sim.get_ion(name))
    cells = SimpleNamespace(
        cell_i=np.arange(n),
        mem_i=np.arange(m),
        mem_to_cells=np.asarray(g["owner"], np.int64),
        nn_i=np.asarray(g["partner"], np.int64),
        bflags_mems=np.asarray(g["boundary"], bool),
        mem_sa=np.asarray(g["membrane_area_m2"], np.float64),
        cell_vol=np.asarray(g["cell_volume_m3"], np.float64),
        M_sum_mems=np.asarray([[int(i == o) for o in g["owner"]] for i in range(n)], np.float64),
        gj_len=np.asarray(g["gap_length_m"], np.float64),
        map_mem2ecm=np.asarray(inputs["network"]["membrane_to_environment"], np.int64),
        R_rads=np.asarray(inputs["network"]["radius_m"], np.float64),
    )
    p = SimpleNamespace(
        F=rawp["F_C_mol"],
        R=rawp["R_J_mol_K"],
        T=rawp["configured_temperature_K"],
        dt=inputs["initial_dt_s"],
        tm=rawp["membrane_thickness_m"],
        vol_env=rawp["bath_volume_m3"],
        cluster_open=rawp["cluster_open"],
        is_ecm=False,
        ions_dict={name: 1 for name in ion["ids"]},
        substances_affect_charge=inputs["network"]["grn_initialization_publish"],
        plot_network=False,
        grn=SimpleNamespace(conf=clone(inputs["network"]["grn_configuration"])),
        visual=SimpleNamespace(single_cell_index=0),
        grn_runmodesim=False,
        grn_unpickle_filename=None,
        grn_pickle_filename="/captured/grn/network.pickle",
        grn_pickle_dirname="/captured/grn",
    )
    phase = SimpleNamespace(sim=sim, cells=cells, p=p, kind="INIT", dyna=SimpleNamespace())
    return SimpleNamespace(
        inputs=inputs,
        sim=sim,
        cells=cells,
        p=p,
        phase=phase,
        owner=None,
        trace=new_trace(),
        files={},
        directories=[],
        before_step=None,
    )


@contextmanager
def active(ctx):
    global _ACTIVE
    previous = _ACTIVE
    _ACTIVE = ctx
    try:
        yield
    finally:
        _ACTIVE = previous


def created(owner, phase):
    assert phase is _ACTIVE.phase
    _ACTIVE.owner = owner


def snapshot(ctx):
    return dict(
        wire=wire(ctx.owner, ctx.sim),
        simulator=public(ctx.sim),
        parameters=public(ctx.p, {"grn", "visual"}),
        configuration=clone(ctx.p.grn.conf),
        visual=public(ctx.p.visual),
        captured_files=clone(ctx.files),
        directories=clone(ctx.directories),
    )


def configure_call(ctx, call):
    ctx.p.grn_dt, ctx.p.grn_total_time, ctx.p.grn_tsample = (
        call["dt_s"],
        call["total_s"],
        call["sample_s"],
    )
    ctx.p.visual.single_cell_index = call["plot_cell"]
    if call["raw_fault"] == "missing_Y_Dm":
        del ctx.p.grn.conf["biomolecules"][1]["Dm"]


def restore(ctx, incoming):
    if "wire" not in incoming or "owner_fields" not in incoming["wire"]:
        raise ValueError("Require complete standalone owner state")
    raw = incoming["wire"]
    if "ion_boundary_state" not in raw:
        raise ValueError("Require standalone boundary state")
    if set(raw) != {
        "owner_fields",
        "core_fields",
        "molecule_fields",
        "reaction_fields",
        "modulator_fields",
        "ion_boundary_state",
        "simulator_fields",
    }:
        raise ValueError("Require all standalone public cache fields")
    api = science()
    owner = object.__new__(api["MasterOfGenes"])
    vars(owner).update(clone(raw["owner_fields"]))
    net = object.__new__(api["MasterOfNetworks"])
    vars(net).update(clone(raw["core_fields"]))
    owner.core, ctx.owner = net, owner
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
    net.reactions_env, net.reactions_mit, net.transporters, net.channels, net.mit = (
        OrderedDict(),
        OrderedDict(),
        OrderedDict(),
        OrderedDict(),
        None,
    )
    vars(ctx.sim).update(clone(incoming["simulator"]))
    ctx.sim.c_env_bound = clone(raw["ion_boundary_state"])
    vars(ctx.p).update(clone(incoming["parameters"]))
    ctx.p.grn = SimpleNamespace(conf=clone(incoming["configuration"]))
    ctx.p.visual = SimpleNamespace(**clone(incoming["visual"]))
    ctx.files, ctx.directories = clone(incoming["captured_files"]), clone(incoming["directories"])
    for attr, ionic, molecular in (
        ("cell_concs", "cc_cells", "c_cells"),
        ("mem_concs", "cc_at_mem", "cc_at_mem"),
        ("env_concs", "cc_env", "c_env"),
        ("bound_concs", "c_env_bound", "c_bound"),
    ):
        mapping = OrderedDict()
        for name in ctx.p.ions_dict:
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
    attach(ctx)


def attach(ctx):
    net = ctx.owner.core

    def chemistry(stage, species, actual):
        ctx.trace["molecule_frames"].append(dict(stage=stage, species=species, state=snapshot(ctx)))

    def rhs(growth, reaction, combined):
        ctx.trace["current_rhs"] = dict(
            growth_rates=clone(growth), reaction_rates=clone(reaction), all_rates=clone(combined)
        )

    def mover(stage, name, local, actual):
        ctx.trace["mover_frames"].append(
            dict(
                stage=stage,
                species=name,
                fields={
                    k: clone(local.get(k))
                    for k in ("f_X_ED", "fgj_X", "cX_cells", "cX_env_o", "cX_mems")
                },
                vm=actual.vm.copy(),
                vgj=actual.vgj.copy(),
            )
        )

    net._observe_chem, net._observe_rhs, ctx.p._mover_observe = chemistry, rhs, mover


def local_inputs(ctx, t):
    sim, p, cells = ctx.sim, ctx.p, ctx.cells
    return dict(
        conditioned_before_model_network=True,
        definition=clone(ctx.inputs["network"]),
        molecule_states_before={
            name: {
                key: clone(getattr(obj, key))
                for key in ("c_cells", "cc_at_mem", "c_env", "flux_intra")
            }
            for name, obj in ctx.owner.core.molecules.items()
        },
        molecular_geometry=dict(
            owner=cells.mem_to_cells.copy(),
            partner=cells.nn_i.copy(),
            boundary=cells.bflags_mems.copy(),
            membrane_area_m2=cells.mem_sa.copy(),
            cell_volume_m3=cells.cell_vol.copy(),
            gap_length_m=cells.gj_len.copy(),
        ),
        dt_s=p.dt,
        F=p.F,
        R=p.R,
        runtime_temperature_K=sim.T,
        configured_temperature_K=p.T,
        membrane_thickness_m=p.tm,
        bath_volume_m3=p.vol_env,
        cluster_open=p.cluster_open,
        gap_open=sim.gjopen.copy(),
        ion_ids=list(p.ions_dict),
        valence=sim.zs.copy(),
        controls_before=dict(gj_block=sim.gj_block.copy(), NaKATP_block=sim.NaKATP_block.copy()),
        values_before=dict(
            voltage_V=sim.vm.copy(),
            junction_voltage_V=sim.vgj.copy(),
            cell_mol_m3=sim.cc_cells.copy(),
            membrane_mol_m3=sim.cc_at_mem.copy(),
            bath_mol_m3=sim.cc_env.copy(),
        ),
        incoming_channel_current_A_m2=sim.extra_J_mem.copy(),
        substances_affect_charge=p.substances_affect_charge,
        source_time_s=t,
        standalone_dispatch=True,
    )


def observe(stage, owner, phase, local):
    ctx = _ACTIVE
    assert ctx.owner is owner and phase is ctx.phase
    t = local.get("t")
    event = dict(stage=stage, t=clone(t), state=snapshot(ctx))
    if stage == "before_reinitialize":
        event["clock"] = dict(
            tt=local["tt"].copy(),
            tsamples=sorted(local["tsamples"]),
            loop_time_step_max=local["loop_time_step_max"],
            loop_seconds_max=local["loop_seconds_max"],
        )
    if stage == "before_run_loop":
        before = local_inputs(ctx, t)
        ctx.trace["steps"].append(dict(before=before, after=None, rhs=None))
        if ctx.before_step is not None:
            ctx.before_step(clone(before))
    if stage == "after_run_loop":
        ctx.trace["steps"][-1].update(after=snapshot(ctx), rhs=clone(ctx.trace["current_rhs"]))
    ctx.trace["events"].append(event)


def save_boundary(filename, data):
    ctx = _ACTIVE
    assert data[0] is ctx.owner and data[1] is ctx.cells and data[2] is ctx.p
    ctx.trace["io_events"].append(
        dict(
            operation="saveSim",
            filename=filename,
            scientific_snapshot=snapshot(ctx),
            persistence_executed=False,
        )
    )


def directory_boundary(path):
    ctx = _ACTIVE
    ctx.directories.append(path)
    ctx.trace["io_events"].append(
        dict(operation="make_unless_dir", path=path, persistence_executed=False)
    )


def capture_open(path, mode="r", newline=None):
    if mode != "w" or newline != "":
        raise ValueError("Only standalone CSV output capture is admitted")
    ctx = _ACTIVE

    class CapturedFile(io.StringIO):
        def close(self):
            if not self.closed:
                text = self.getvalue()
                ctx.files[path] = text
                ctx.trace["io_events"].append(
                    dict(operation="CSV", path=path, text=text, persistence_executed=False)
                )
            super().close()

    return CapturedFile(newline=newline)


open = capture_open


def science():
    return dict(
        MasterOfGenes=MasterOfGenes,
        MasterOfNetworks=MasterOfNetworks,
        Molecule=base.Molecule,
        Reaction=base.feedback_source.Reaction,
        Modulator=base.feedback_source.Modulator,
        DynamicValue=base.DynamicValue,
        DynamicValueDict=base.DynamicValueDict,
    )


@dataclass(frozen=True)
class Binding:
    identity: str
    inputs: Mapping


@dataclass(frozen=True)
class State:
    binding_identity: str
    invocation: int
    snapshot: Mapping
    identity: str


class StandaloneRejected(RuntimeError):
    def __init__(self, error, partial):
        super().__init__(str(error))
        self.partial = ions.freeze(partial)


def bind(inputs):
    inputs = ions.data(inputs)
    validate(inputs)
    ib = ions.bind(inputs["ion_definition"])
    cb = current.bind(inputs["current_definition"])
    checked = clone(inputs["network"])
    checked["grn_initialization_publish"] = True
    base.validate(checked, ib, cb, ib.kernel.configured_temperature_K)
    return Binding(ions.digest(inputs), ions.freeze(inputs))


def state(binding, snapshot, invocation):
    snapshot = ions.freeze(snapshot)
    return State(
        binding.identity,
        invocation,
        snapshot,
        ions.digest((binding.identity, invocation, snapshot)),
    )


def initialize(binding):
    ctx = make_context(ions.data(binding.inputs))
    try:
        with active(ctx):
            ctx.owner = start_new(SimpleNamespace(_p=ctx.p), ctx.phase)
    except Exception as error:
        raise StandaloneRejected(
            error, dict(stage="cold", snapshot=snapshot(ctx), trace=ctx.trace)
        ) from error
    return state(binding, snapshot(ctx), 0)


def advance(binding, parent, *, before_step=None):
    if parent.binding_identity != binding.identity or parent.identity != ions.digest(
        (binding.identity, parent.invocation, parent.snapshot)
    ):
        raise ValueError("Changed standalone GRN parent")
    if parent.invocation >= len(binding.inputs["calls"]):
        raise ValueError("No remaining standalone invocation")
    ctx = make_context(ions.data(binding.inputs))
    restore(ctx, ions.data(parent.snapshot))
    ctx.before_step = before_step
    configure_call(ctx, ions.data(binding.inputs["calls"][parent.invocation]))
    try:
        with active(ctx):
            ctx.owner.run_core_sim(ctx.phase)
    except Exception as error:
        raise StandaloneRejected(
            error,
            dict(
                stage="run_core_sim",
                snapshot=snapshot(ctx),
                trace=ctx.trace,
                invocation=parent.invocation,
            ),
        ) from error
    return state(binding, snapshot(ctx), parent.invocation + 1), ions.freeze(ctx.trace)
