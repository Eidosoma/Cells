# Copyright 2014-2025 Alexis Pietak & Cecil Curry; see licenses/BETSE.txt.
# ruff: noqa: F821, E501
"""Whole original clear_storage body; no import-time source execution."""

SIM_SHA256 = "02a9a049b5daa5cf6bc543332aa89437f58a4700ed31310abc3ee13697f22d43"


class InitStorage:
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
            self.grn.core.clear_cache()
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
