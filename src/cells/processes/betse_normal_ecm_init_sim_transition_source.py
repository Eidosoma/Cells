# ruff: noqa: E731, F841, B905
"""Pinned native SIM reinitialization bodies on explicitly supplied owners.

No cold constructor, seed loader, pickle, profile selector or full solver runs.
The retained GRN executes its real reinitialize body; channels are reconstructed
by that body, never inferred from a fresh cold snapshot.
"""

from types import SimpleNamespace

import numpy as np

from cells.processes import betse_environment_field as environment

gaussian_filter = environment.gaussian_filter
logs = SimpleNamespace(log_info=lambda *args: None, log_debug=lambda *args: None)
EndoRetic = None  # unreachable under the explicit ordinary Ca_dyn=False flag


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
    logs.log_debug("Mapping tissue, surgery, and boundary profiles...")
    cells = phase.cells
    p = phase.p
    sim = phase.sim
    self.cell_target_inds = {}
    self.env_target_inds = {}
    self.tissue_target_inds = {}
    for tissue_name, tissue_profile in self.tissue_name_to_profile.items():
        tissue_cells_index, tissue_mems_index = tissue_profile.picker.pick_cells_and_mems(
            cells=cells, p=p
        )
        self.cell_target_inds[tissue_name] = tissue_cells_index
        self.tissue_target_inds[tissue_name] = tissue_mems_index
        if len(self.cell_target_inds[tissue_name]):
            if p.is_ecm:
                ecm_targs_mem = list(cells.map_mem2ecm[tissue_mems_index])
                self.env_target_inds[tissue_name] = ecm_targs_mem
            if p.ions_dict["Na"] == 1:
                sim.Dm_cells[sim.iNa][tissue_mems_index] = tissue_profile.Dm_Na
            if p.ions_dict["K"] == 1:
                sim.Dm_cells[sim.iK][tissue_mems_index] = tissue_profile.Dm_K
            if p.ions_dict["Cl"] == 1:
                sim.Dm_cells[sim.iCl][tissue_mems_index] = tissue_profile.Dm_Cl
            if p.ions_dict["Ca"] == 1:
                sim.Dm_cells[sim.iCa][tissue_mems_index] = tissue_profile.Dm_Ca
            if p.ions_dict["M"] == 1:
                sim.Dm_cells[sim.iM][tissue_mems_index] = tissue_profile.Dm_M
            if p.ions_dict["P"] == 1:
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
    self.TJ_targets = np.hstack(
        (cells.all_bound_mem_inds, cells.interior_bound_mem_inds, cells.ecm_inds_bound_cell)
    )
    self.Chi = np.ones(len(cells.xypts)) * p.er
    self.Chi = gaussian_filter(self.Chi.reshape(cells.X.shape), 2)


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
    if p.global_options["K_env"] != 0:
        self.t_on_Kenv = p.global_options["K_env"][0]
        self.t_off_Kenv = p.global_options["K_env"][1]
        self.t_change_Kenv = p.global_options["K_env"][2]
        self.mem_mult_Kenv = p.global_options["K_env"][3]
    if p.global_options["Cl_env"] != 0:
        self.t_on_Clenv = p.global_options["Cl_env"][0]
        self.t_off_Clenv = p.global_options["Cl_env"][1]
        self.t_change_Clenv = p.global_options["Cl_env"][2]
        self.mem_mult_Clenv = p.global_options["Cl_env"][3]
    if p.global_options["Na_env"] != 0:
        self.t_on_Naenv = p.global_options["Na_env"][0]
        self.t_off_Naenv = p.global_options["Na_env"][1]
        self.t_change_Naenv = p.global_options["Na_env"][2]
        self.mem_mult_Naenv = p.global_options["Na_env"][3]
    if p.global_options["T_change"] != 0:
        self.tonT = p.global_options["T_change"][0]
        self.toffT = p.global_options["T_change"][1]
        self.trampT = p.global_options["T_change"][2]
        self.multT = p.global_options["T_change"][3]
    if p.global_options["gj_block"] != 0:
        self.tonGJ = p.global_options["gj_block"][0]
        self.toffGJ = p.global_options["gj_block"][1]
        self.trampGJ = p.global_options["gj_block"][2]
        numo = int(p.global_options["gj_block"][3])
        if numo > 100:
            numo = 100
        elif numo < 1:
            numo = 1
        data_length = len(cells.mem_i)
        data_fraction = int(numo / 100 * data_length)
        mem_i_copy = np.copy(cells.mem_i[:])
        shuffle(mem_i_copy)
        self.targets_gj_block = [cells.mem_i[x] for x in range(0, data_fraction)]
    if p.global_options["NaKATP_block"] != 0:
        self.tonNK = p.global_options["NaKATP_block"][0]
        self.toffNK = p.global_options["NaKATP_block"][1]
        self.trampNK = p.global_options["NaKATP_block"][2]


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
    if p.scheduled_options["Na_mem"] != 0:
        self.t_on_Namem = p.scheduled_options["Na_mem"][0]
        self.t_off_Namem = p.scheduled_options["Na_mem"][1]
        self.t_change_Namem = p.scheduled_options["Na_mem"][2]
        self.mem_mult_Namem = p.scheduled_options["Na_mem"][3]
        self.apply_Namem = p.scheduled_options["Na_mem"][4]
        self.function_Namem = p.scheduled_options["Na_mem"][5]
        self.targets_Namem = []
        for profile in self.apply_Namem:
            targets = self.tissue_target_inds[profile]
            self.targets_Namem.append(targets)
        self.targets_Namem = [item for sublist in self.targets_Namem for item in sublist]
        self.scalar_Namem = 1
        self.dyna_Namem = lambda t: 1
        if self.function_Namem != "None":
            self.scalar_Namem, self.dyna_Namem = getattr(mod, self.function_Namem)(
                self.targets_Namem, cells, p
            )
    if p.scheduled_options["K_mem"] != 0:
        self.t_on_Kmem = p.scheduled_options["K_mem"][0]
        self.t_off_Kmem = p.scheduled_options["K_mem"][1]
        self.t_change_Kmem = p.scheduled_options["K_mem"][2]
        self.mem_mult_Kmem = p.scheduled_options["K_mem"][3]
        self.apply_Kmem = p.scheduled_options["K_mem"][4]
        self.function_Kmem = p.scheduled_options["K_mem"][5]
        self.targets_Kmem = []
        for profile in self.apply_Kmem:
            targets = self.tissue_target_inds[profile]
            self.targets_Kmem.append(targets)
        self.targets_Kmem = [item for sublist in self.targets_Kmem for item in sublist]
        self.scalar_Kmem = 1
        self.dyna_Kmem = lambda t: 1
        if self.function_Kmem != "None":
            self.scalar_Kmem, self.dyna_Kmem = getattr(mod, self.function_Kmem)(
                self.targets_Kmem, cells, p
            )
    if p.scheduled_options["Cl_mem"] != 0:
        self.t_on_Clmem = p.scheduled_options["Cl_mem"][0]
        self.t_off_Clmem = p.scheduled_options["Cl_mem"][1]
        self.t_change_Clmem = p.scheduled_options["Cl_mem"][2]
        self.mem_mult_Clmem = p.scheduled_options["Cl_mem"][3]
        self.apply_Clmem = p.scheduled_options["Cl_mem"][4]
        self.function_Clmem = p.scheduled_options["Cl_mem"][5]
        self.targets_Clmem = []
        for profile in self.apply_Clmem:
            targets = self.tissue_target_inds[profile]
            self.targets_Clmem.append(targets)
        self.targets_Clmem = [item for sublist in self.targets_Clmem for item in sublist]
        self.scalar_Clmem = 1
        self.dyna_Clmem = lambda t: 1
        if self.function_Clmem != "None":
            self.scalar_Clmem, self.dyna_Clmem = getattr(mod, self.function_Clmem)(
                self.targets_Clmem, cells, p
            )
    if p.scheduled_options["Ca_mem"] != 0:
        self.t_on_Camem = p.scheduled_options["Ca_mem"][0]
        self.t_off_Camem = p.scheduled_options["Ca_mem"][1]
        self.t_change_Camem = p.scheduled_options["Ca_mem"][2]
        self.mem_mult_Camem = p.scheduled_options["Ca_mem"][3]
        self.apply_Camem = p.scheduled_options["Ca_mem"][4]
        self.function_Camem = p.scheduled_options["Ca_mem"][5]
        self.targets_Camem = []
        for profile in self.apply_Camem:
            targets = self.tissue_target_inds[profile]
            self.targets_Camem.append(targets)
        self.targets_Camem = [item for sublist in self.targets_Camem for item in sublist]
        self.scalar_Camem = 1
        self.dyna_Camem = lambda t: 1
        if self.function_Camem != "None":
            self.scalar_Camem, self.dyna_Camem = getattr(mod, self.function_Camem)(
                self.targets_Camem, cells, p
            )
    if p.scheduled_options["pressure"] != 0:
        self.t_onP = p.scheduled_options["pressure"][0]
        self.t_offP = p.scheduled_options["pressure"][1]
        self.t_changeP = p.scheduled_options["pressure"][2]
        self.rate_P = p.scheduled_options["pressure"][3]
        self.apply_P = p.scheduled_options["pressure"][4]
        self.function_P = p.scheduled_options["pressure"][5]
        self.targets_P = []
        for profile in self.apply_P:
            targets = self.cell_target_inds[profile]
            self.targets_P.append(targets)
        self.targets_P = [item for sublist in self.targets_P for item in sublist]
        self.scalar_P = 1
        self.dyna_P = lambda t: 1
        if self.function_P != "None":
            self.scalar_P, self.dyna_P = getattr(mod, self.function_P)(self.targets_P, cells, p)
    if p.scheduled_options["ecmJ"] != 0 and p.is_ecm:
        self.t_on_ecmJ = p.scheduled_options["ecmJ"][0]
        self.t_off_ecmJ = p.scheduled_options["ecmJ"][1]
        self.t_change_ecmJ = p.scheduled_options["ecmJ"][2]
        self.apply_ecmJ = p.scheduled_options["ecmJ"][3]
        self.mult_ecmJ = p.scheduled_options["ecmJ"][4]
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
    if p.f_scan_properties["f slope"] is None and p._run_sim:
        p.f_scan_properties["f slope"] = (
            p.f_scan_properties["f stop"] - p.f_scan_properties["f start"]
        ) / p.sim_time_total
    f_slope = p.f_scan_properties["f slope"]
    y = lambda t: np.sin(np.pi * (f_slope * t + p.f_scan_properties["f start"]) * t) ** 2
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
    self.Dm_cells[self.iK] = (
        p.channel_noise_level * self.channel_noise_factor + 1
    ) * self.Dm_cells[self.iK]
    if p.global_options["gj_block"] != 0:
        self.gj_block = np.ones(len(cells.mem_i))
    else:
        self.gj_block = 1
    if p.global_options["NaKATP_block"] != 0:
        self.NaKATP_block = np.ones(self.mdl)
    else:
        self.NaKATP_block = 1
    self.CaATP_block = np.ones(self.mdl)
    if p.ions_dict["Ca"] == 1 and p.Ca_dyn:
        self.endo_retic = EndoRetic(self, cells, p)
    else:
        self.endo_retic = None


def screening_conductivity(self, cells, p):
    self.ko_env = np.sqrt(
        np.dot(p.NAv * p.q**2 * self.zs**2 / (p.er * p.eo * p.kb * p.T), self.cc_env)
    ).mean()
    self.ko_cell = np.sqrt(
        np.dot(p.NAv * p.q**2 * self.zs**2 / (p.er * p.eo * p.kb * p.T), self.cc_cells)
    ).mean()
    self.cedl_env = p.er * p.eo * self.ko_env
    self.cedl_cell = p.er * p.eo * self.ko_cell
    self.cedl = p.er * p.eo * self.ko_env
    self.sigma = (
        np.asarray(
            [
                z**2 * p.q * p.F * cc * D / (p.kb * p.T)
                for z, cc, D in zip(self.zs, self.cc_cells, self.D_free)
            ]
        )
        .sum(axis=0)
        .mean()
    )
    self.sigma_cell = np.asarray(
        [
            z**2 * p.q * p.F * cc * D * 0.1 / (p.kb * p.T)
            for z, cc, D in zip(self.zs, self.cc_cells, self.D_free)
        ]
    ).sum(axis=0)
    self.sigma_env = np.asarray(
        [
            z**2 * p.q * p.F * cc * D / (p.kb * p.T)
            for z, cc, D in zip(self.zs, self.cc_env, self.D_env)
        ]
    ).sum(axis=0)
    if p.is_ecm:
        self.sigma_env = gaussian_filter(self.sigma_env.reshape(cells.X.shape), 1).ravel()
    self.rho_factor = cells.mem_sa / cells.R_rads
    self.cgj = 1 / (2 / p.cm)


mod = SimpleNamespace(f_sweep=f_sweep)
