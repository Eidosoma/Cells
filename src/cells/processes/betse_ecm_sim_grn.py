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

from cells.processes import betse_ecm_grn_source as base
from cells.processes import betse_ecm_transport as material
from cells.processes import betse_environment_field as field
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
    if inputs.get("kind") != "cells.betse_ecm_sim_grn_inputs@1":
        raise ValueError("Require explicit standalone GRN phase inputs")
    scope = inputs["scope"]
    if inputs.get("is_ecm") is not True:
        raise ValueError("Require explicit ECM-enabled standalone phase")
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
    binding = material.bind(inputs["material_definition"])
    material.state(binding, inputs["initial"])
    base_validate(inputs["network"], binding)
    cb = binding.geometry_binding.current_binding
    if not {"Na", "K", "Cl"} <= set(cb.ion_ids):
        raise ValueError("Standalone ECM reports require actual Na/K/Cl rows")
    if set(inputs["incoming_publication_fields"]) != {
        "extra_rho_cells",
        "extra_rho_env",
        "extra_J_mem",
        "extra_Jenv_x",
        "extra_Jenv_y",
    }:
        raise ValueError("Require all five incoming ECM publications")
    n, m, e = (
        len(cb.cell_ids),
        len(cb.membrane_ids),
        int(np.prod(binding.geometry_binding.geometry.shape)),
    )
    for key in ("initial_dt_s", "runtime_temperature_K"):
        if (
            type(inputs[key]) not in (int, float)
            or not math.isfinite(inputs[key])
            or inputs[key] <= 0
        ):
            raise ValueError("Require positive finite standalone phase scalars")
    if (
        np.asarray(inputs["rho_channel"]).shape != (m,)
        or not np.isfinite(inputs["rho_channel"]).all()
    ):
        raise ValueError("Require original membrane channel multipliers")
    for key in ("electric_x_source", "electric_y_source"):
        if (
            np.asarray(inputs[key]).shape != binding.geometry_binding.geometry.shape
            or not np.isfinite(inputs[key]).all()
        ):
            raise ValueError("Require complete held ECM field arrays")
    for key, size in (
        ("extra_rho_cells", n),
        ("extra_rho_env", e),
        ("extra_J_mem", m),
        ("extra_Jenv_x", e),
        ("extra_Jenv_y", e),
    ):
        array = np.asarray(inputs["incoming_publication_fields"][key], np.float64)
        if array.shape != (size,) or not np.isfinite(array).all():
            raise ValueError("Require original cell/E-grid/M-membrane publication shapes")
    if inputs["material_definition"]["parameters"]["fluid_flow"] is not False:
        raise ValueError("Standalone fluid and cuts require separate phase dynamics")


def new_trace():
    return dict(events=[], steps=[], molecule_frames=[], mover_frames=[], io_events=[])


def make_context(inputs):
    definition, initial = inputs["material_definition"], inputs["initial"]
    external = definition["environment_geometry_definition"]
    current = external["current_definition"]
    g, ion = current["geometry"], current["ions"]
    n, m = len(g["cell_ids"]), len(g["owner"])
    rawp, transport = external["parameters"], definition["parameters"]
    sim = SimpleNamespace(
        cdl=n,
        mdl=m,
        edl=len(initial["environment_mol_m3"][0]),
        cc_cells=np.asarray(initial["cell_mol_m3"], np.float64).copy(),
        cc_at_mem=np.asarray(initial["membrane_mol_m3"], np.float64).copy(),
        cc_env=np.asarray(initial["environment_mol_m3"], np.float64).copy(),
        vm=np.asarray(initial["voltage_V"], np.float64).copy(),
        vgj=np.asarray(initial["junction_voltage_V"], np.float64).copy(),
        gjopen=np.asarray(initial["gap_open"], np.float64).copy(),
        zs=np.asarray(ion["valence"], np.float64),
        Dm_cells=np.asarray(definition["ions"]["membrane_diffusion_m2_s"], np.float64),
        D_env=np.asarray(definition["ions"]["environment_diffusion_m2_s"], np.float64),
        T=inputs["runtime_temperature_K"],
        rho_channel=np.asarray(inputs["rho_channel"], np.float64).copy(),
        gj_block=np.asarray(inputs["network"]["initial_controls"]["gj_block"], np.float64).copy(),
        NaKATP_block=np.asarray(
            inputs["network"]["initial_controls"]["NaKATP_block"], np.float64
        ).copy(),
        c_env_bound=np.asarray(inputs["network"]["initial_ion_boundary"], np.float64).copy(),
        time=clone(inputs["simulator_time_before"]),
        E_env_x=np.asarray(inputs["electric_x_source"], np.float64).copy(),
        E_env_y=np.asarray(inputs["electric_y_source"], np.float64).copy(),
    )
    for key, value in inputs["incoming_publication_fields"].items():
        setattr(sim, key, np.asarray(value, np.float64).copy())
    for key, attr in (
        ("membrane_flux_mol_m2_s", "fluxes_mem"),
        ("junction_flux_mol_m2_s", "fluxes_gj"),
        ("environment_flux_x_mol_m2_s", "fluxes_env_x"),
        ("environment_flux_y_mol_m2_s", "fluxes_env_y"),
        ("junction_field_source", "Egj"),
    ):
        setattr(sim, attr, np.asarray(initial[key], np.float64).copy())
    sim.E_gj_x, sim.E_gj_y = np.asarray(initial["junction_field_xy_source"], np.float64).T.copy()
    sim.get_ion = lambda name: ion["ids"].index(name)
    for name in ("Na", "K", "Cl"):
        setattr(sim, "i" + name, sim.get_ion(name))
    cells = SimpleNamespace(
        cell_i=np.arange(n),
        mem_i=np.arange(m),
        mem_to_cells=np.asarray(g["owner"], np.int64),
        cell_to_mems=[np.flatnonzero(np.asarray(g["owner"]) == i).tolist() for i in range(n)],
        nn_i=np.asarray(definition["junction_geometry"]["partner"], np.int64),
        bflags_mems=np.asarray(definition["junction_geometry"]["boundary"], bool),
        mem_sa=np.asarray(g["membrane_area_m2"], np.float64),
        cell_sa=np.asarray(g["cell_area_m2"], np.float64),
        cell_vol=np.asarray(external["geometry"]["cell_volume_m3"], np.float64),
        cell_centres=np.asarray(external["geometry"]["cell_centres_m"], np.float64),
        mem_mids_flat=np.asarray(external["geometry"]["membrane_midpoints_m"], np.float64),
        mem_vects_flat=np.column_stack((np.zeros((m, 2)), g["normal_xy"])),
        M_sum_mems=np.asarray([[int(i == o) for o in g["owner"]] for i in range(n)], np.float64),
        gj_len=np.asarray(definition["junction_geometry"]["gap_length_m"], np.float64),
        **{key: external["world"][key + "_m"] for key in ("xmin", "xmax", "ymin", "ymax")},
    )
    p = SimpleNamespace(
        F=current["parameters"]["F_C_mol"],
        R=transport["R_J_mol_K"],
        T=rawp["configured_temperature_K"],
        q=rawp["q_C"],
        kb=rawp["kb_J_K"],
        dt=inputs["initial_dt_s"],
        tm=transport["membrane_thickness_m"],
        cluster_open=transport["cluster_open"],
        fast_update_ecm=transport["fast_update_ecm"],
        sharpness=transport["sharpness"],
        is_ecm=True,
        fluid_flow=False,
        grid_size=external["world"]["grid_size"],
        cell_height=rawp["cell_height_m"],
        cell_space=rawp["cell_space_m"],
        ions_dict={name: 1 for name in ion["ids"]},
        substances_affect_charge=inputs["network"]["cold_publish"],
        plot_network=False,
        grn=SimpleNamespace(conf=clone(inputs["network"]["configuration"])),
        visual=SimpleNamespace(single_cell_index=0),
        grn_runmodesim=False,
        grn_unpickle_filename=None,
        grn_pickle_filename="/captured/grn/network.pickle",
        grn_pickle_dirname="/captured/grn",
    )
    p.ions_dict.setdefault("Ca", 0)
    build_grid(cells, p, inputs)
    cells.ecm_vol = p.cell_height * cells.delta**2
    for key, value in inputs["network"]["grid_index_groups"].items():
        setattr(cells, key, np.asarray(value, np.int64).copy())
    science()["derive_context"](sim, cells)
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
        grid_fields={name: clone(getattr(ctx.cells, name)) for name in GRID_FIELDS},
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
    if "grid_fields" not in incoming or set(incoming["grid_fields"]) != set(GRID_FIELDS):
        raise ValueError("Require complete generated standalone ECM grid state")
    if not {"D_env_weight", "D_env_weight_base", "TJ_targets"} <= incoming["simulator"].keys():
        raise ValueError("Require standalone ECM coefficient state")
    vars(ctx.cells).update(clone(incoming["grid_fields"]))
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
                    for k in (
                        "f_X_ED",
                        "fgj_X",
                        "cX_cells",
                        "cX_env_o",
                        "cX_mems",
                        "fenvx",
                        "fenvy",
                        "cenv",
                        "gcx",
                        "gcy",
                        "fx",
                        "fy",
                        "div_fa",
                    )
                },
                vm=actual.vm.copy(),
                vgj=actual.vgj.copy(),
            )
        )

    net._observe_chem, net._observe_rhs, ctx.p._mover_observe = chemistry, rhs, mover


def local_inputs(ctx, t):
    sim, p, cells, net = ctx.sim, ctx.p, ctx.cells, ctx.owner.core
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
        material_declaration=clone(ctx.inputs["material_definition"]),
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
        core_publication_fields_before={
            key: clone(getattr(net, key)) for key in PUBLICATIONS if hasattr(net, key)
        },
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
        ion_ids=[name for name, enabled in p.ions_dict.items() if enabled == 1],
        valence=clone(sim.zs),
        electric_x_source=clone(sim.E_env_x),
        electric_y_source=clone(sim.E_env_y),
        D_env=clone(sim.D_env),
        grid_index_groups=clone(ctx.inputs["network"]["grid_index_groups"]),
        substances_affect_charge=p.substances_affect_charge,
        sharpness=p.sharpness,
        cluster_open=p.cluster_open,
        incoming_channel_current_A_m2=clone(net.extra_J_mem),
        simulator_fields_before=wire(ctx.owner, sim)["simulator_fields"],
        standalone_dispatch=True,
        source_time_s=t,
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
        derive_context=base.derive_context,
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


PARAMETERS = base.PARAMETERS

PUBLICATIONS = ("extra_rho_cells", "extra_rho_env", "extra_J_mem", "extra_Jenv_x", "extra_Jenv_y")
GRID_FIELDS = (
    "X",
    "Y",
    "xypts",
    "delta",
    "map_cell2ecm",
    "map_mem2ecm",
    "M_sum_mems",
    "num_mems",
    "memSa_per_envSquare",
    "M_divmap_mem2ecm",
    "true_ecm_vol",
    "ecm_vol",
    "rads",
    "R_rads",
    "all_bound_mem_inds",
    "interior_bound_mem_inds",
    "ecm_inds_bound_cell",
)
material_values = base.material_values
base_validate = base.validate


def build_grid(cells, p, inputs):
    binding = field.bind(inputs["material_definition"]["environment_geometry_definition"])
    g = binding.geometry
    for target, attr in (
        ("X", "X_m"),
        ("Y", "Y_m"),
        ("xypts", "grid_points_m"),
        ("delta", "delta_m"),
        ("map_cell2ecm", "cell_to_grid"),
        ("map_mem2ecm", "membrane_to_grid"),
        ("memSa_per_envSquare", "membrane_area_per_site_m2"),
        ("M_divmap_mem2ecm", "membrane_divergence_map_m2"),
        ("true_ecm_vol", "true_environment_volume_m3"),
    ):
        setattr(cells, target, clone(getattr(g, attr)))

    cells.num_mems = np.asarray([len(group) for group in cells.cell_to_mems])
