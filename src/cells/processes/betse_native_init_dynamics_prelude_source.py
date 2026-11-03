# Copyright 2014-2025 Alexis Pietak & Cecil Curry; see licenses/BETSE.txt.
# ruff: noqa: F821, E501
"""Original INIT dynamics prefix and complete reached helpers; definitions only.

Stops before native tissue-profile remapping at sim.py809. No method is called
at import; native annotations/decorators are authenticated by the driver.
"""

class InitDynamicsPrelude:

    def init_dynamics(self, phase):
        """
        Prepare tissue-centric data structures required by the passed phase in
        a general-purpose manner applicable to *all* possible phases.

        This method initializes core computational matrices -- including those
        concerning tissue, cut, and boundary profiles, dynamic activities, and
        optional simulation features safely modifiable between the
        initialization and simulation phases (e.g., electroosmotic fluid flow).

        Parameters
        --------
        phase : SimPhase
            Current simulation phase.
        """
        logs.log_info('Initializing tissue and boundary profiles...')
        cells = phase.cells
        p = phase.p
        nfrac = p.smooth_cells
        self.smooth_weight_mem = (nfrac * cells.num_mems[cells.mem_to_cells] - 1) / (nfrac * cells.num_mems[cells.mem_to_cells])
        self.smooth_weight_o = 1 / (nfrac * cells.num_mems[cells.mem_to_cells])
        if p.v_sensitive_gj:
            self.gj_funk = Gap_Junction(self, cells, p)
        self.initDenv(cells, p)
        for key, val in p.ions_dict.items():
            if val == 1:
                ion_i = self.get_ion(key)
                if p.cbnd is not None:
                    self.c_env_bound[ion_i] = p.cbnd[key]

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
        self.TJ_targets = np.hstack((cells.all_bound_mem_inds, cells.interior_bound_mem_inds, cells.ecm_inds_bound_cell))
        self.Chi = np.ones(len(cells.xypts)) * p.er
        self.Chi = gaussian_filter(self.Chi.reshape(cells.X.shape), 2)

    def get_ion(self, ion_name):
        """
        0-based index assigned to the ion with the passed name (e.g., ``Na``)
        if this ion is enabled by this simulation *or* the empty list
        otherwise.

        This index is guaranteed to uniquely (but arbitrarily) identify this
        ion with respect to this simulation.
        """
        if ion_name == 'Na':
            ion = self.iNa
        elif ion_name == 'K':
            ion = self.iK
        elif ion_name == 'Ca':
            ion = self.iCa
        elif ion_name == 'Cl':
            ion = self.iCl
        elif ion_name == 'M':
            ion = self.iM
        elif ion_name == 'H':
            ion = self.iH
        elif ion_name == 'P':
            ion = self.iP
        else:
            logs.warning('Oops! Molecule gated ion "%s" channel target not found!', ion_name)
            ion = []
        return ion

class GapJunctionConstruction:

    def __init__(self, sim, cells, p):
        self.init(sim, cells, p)

    def init(self, sim, cells, p):
        """
        Initialize the gap junction object to its initial conditions

        """
        self.lamb = 0.0013
        self.A1 = 0.077
        self.A2 = 0.14
        self.Ao = 0.217
        V1 = 1000.0 * np.abs(sim.vgj)
        self.alpha = self.lamb * np.exp(-self.A1 * (V1 - p.gj_vthresh))
        beta = self.lamb * np.exp(self.A2 * (V1 - p.gj_vthresh))
        self.beta = beta / (1 + 50 * beta)
        self.gjopen = sim.gj_block * (self.alpha / (self.alpha + self.beta) + p.gj_min)
