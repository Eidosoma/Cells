# Copyright 2014-2025 Alexis Pietak & Cecil Curry; see licenses/BETSE.txt.
# ruff: noqa: F821, E501, B905
"""Literal native tail809–1012 with only original cells/p alias reads.

Definitions only. Original branch/body order, RNG and arithmetic remain; no
native callable is invoked at import. This alone supplies no parent authority.
"""

class InitDynamicsCompletion:

    def init_dynamics(self, phase):
        cells = phase.cells
        p = phase.p
        phase.dyna.init_profiles(phase)
        if p.is_ecm:
            self.D_env_base = copy.copy(self.D_env)
            self.J_env_x = np.zeros(len(cells.xypts))
            self.J_env_y = np.zeros(len(cells.xypts))
            self.fluxes_env_x = np.zeros((len(self.zs), self.edl))
            self.fluxes_env_y = np.zeros((len(self.zs), self.edl))
        Dm_cellsA = np.asarray(self.Dm_cells)
        self.Dm_base = np.copy(Dm_cellsA)
        self.Dm_scheduled = np.copy(Dm_cellsA)
        self.Dm_scheduled[:] = 0
        self.P_mod = np.copy(self.P_cells[:])
        self.P_base = np.copy(self.P_cells[:])
        self.div_u_osmo = np.zeros(self.cdl)
        self.channel_noise_factor = np.random.random(self.mdl)
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
        if p.molecules_enabled:
            if self.molecules is None:
                logs.log_info('Initializing general network...')
                self.molecules = MasterOfMolecules(p)
                self.molecules.read_mol_config(phase)
            else:
                logs.log_info('Reinitializing the general regulatory network for simulation...')
                self.molecules.reinitialize(phase)
        if p.grn_enabled:
            if self.grn is None:
                logs.log_info('Initializing gene regulatory network...')
                self.grn = MasterOfGenes(p)
                self.grn.read_gene_config(phase)
            else:
                logs.log_info('Reinitializing the gene regulatory network for simulation...')
                self.grn.reinitialize(phase)
        if p.deform_osmo is True:
            self.div_u_osmo = np.zeros(self.cdl)
            self.u_net = np.zeros(self.mdl)
        if p.fluid_flow is True:
            self.u_cells_x = np.zeros(self.cdl)
            self.u_cells_y = np.zeros(self.cdl)
            self.u_gj_x = np.zeros(self.mdl)
            self.u_gj_y = np.zeros(self.mdl)
            if p.is_ecm is True:
                self.u_env_x = np.zeros(cells.X.shape)
                self.u_env_y = np.zeros(cells.X.shape)
        if p.deformation:
            self.d_cells_x = np.zeros(self.cdl)
            self.d_cells_y = np.zeros(self.cdl)
            cells.deform_tools(p)
            self.cellso = copy.deepcopy(cells)
            if p.td_deform and cells.lapGJ is None:
                logs.log_info('Creating cell network Poisson solver...')
                cells.graphLaplacian(p)
        else:
            self.cellso = cells
        self.rho_pump = 1
        self.rho_channel = 1
        phase.dyna.init_events(phase)
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
        if p.solver_type is SolverType.FAST:
            self.fast_sim_init(cells, p)
