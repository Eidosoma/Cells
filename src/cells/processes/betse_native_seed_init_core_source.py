# ruff: noqa: F821, E501
# Copyright 2014-2025 Alexis Pietak & Cecil Curry; see licenses/BETSE.txt.
"""Literal selected native SEED core and its entire conditional helper.

No body runs at import. Actual native wrapper/decorator provenance is authenticated by the driver.
The selected method bodies use exact-owner checks, not a replayed decorator.
Only annotations are omitted in this proof. SeedCoreCallSite projects the
selected two statements; it is not an independently issued SimRunner owner.
"""

SIM_SHA256 = "02a9a049b5daa5cf6bc543332aa89437f58a4700ed31310abc3ee13697f22d43"
RUNNER_SHA256 = "6a9389f106d717dc83ea1a594a64aa5bde278cef9a17b2a8ff01251b08d7be8a"


class SeedCore:
    def init_core(self, phase):
        """
        Create core data structures required by both the passed simulation
        phase *and* all subsequent phases.

        This method initializes core computational matrices -- including those
        concerning intracellular and environmental concentrations, voltages,
        specific diffusion constants, and types of ions included in the
        simulation. This method is performed only once per seed (i.e., cell
        cluster creation) and thus contains crucial parameters that *cannot* be
        safely modified after running an initialization.

        Parameters
        --------
        phase : SimPhase
            Current simulation phase.
        """

        # Log this attempt.
        logs.log_info("Creating core computational matrices...")

        # Localize frequently referenced phase variables for convenience.
        p = phase.p
        cells = phase.cells

        # Initialize all extra substances related objects to None, to be filled
        # in (if desired) later.
        self.molecules = None
        self.metabo = None
        self.met_concs = None
        self.grn = None

        self.mdl = len(cells.mem_i)  # mems-data-length
        self.cdl = len(cells.cell_i)  # cells-data-length

        if p.is_ecm:  # set environnment data length
            self.edl = len(cells.xypts)
        else:
            self.edl = self.mdl

        # Initialize extra arrays that allow additional substances (defined
        # outside of sim) to affect Vmem.
        self.extra_rho_cells = np.zeros(self.cdl)
        self.extra_rho_mems = np.zeros(self.mdl)
        self.extra_rho_env = np.zeros(self.edl)
        self.extra_J_mem = np.zeros(self.mdl)

        self.extra_Jenv_x = np.zeros(self.edl)
        self.extra_Jenv_y = np.zeros(self.edl)

        self.extra_rho_cells_o = np.zeros(self.cdl)

        self.vgj = np.zeros(self.mdl)

        self.gj_block = 1  # will update this according to user preferences in self.init_dynamics()

        # Identity matrix to easily make matrices out of scalars
        self.id_mems = np.ones(self.mdl)

        self.cc_cells = []  # cell concentrations at cell centres
        self.cc_er = []  # endoplasmic reticulum ion concentrations in each cell
        self.cc_env = []  # environmental concentrations initialized

        self.zs = []  # ion valence state initialized
        self.z_er = []  # ion valence states of er ions
        self.z_array_er = []
        self.z_array = []  # ion valence array matched to cell points

        self.Dm_cells = []  # membrane diffusion constants initialized
        self.Dm_er = []  # a list of endoplasmic reticulum membrane state
        self.D_free = []  # a list of single-valued free diffusion constants for each ion
        self.D_gj = []  # an array of diffusion constants for gap junctions
        self.movingIons = []  # moving ions indices
        self.ionlabel = {}  # dictionary to hold ion label names
        self.molar_mass = []

        self.T = p.T  # set the base temperature for the simulation

        self.Jn = np.zeros(self.mdl)  # net normal transmembrane current density at membranes
        self.Jmem = np.zeros(
            self.mdl
        )  # current across membrane from intra- to extra-cellular space
        self.Jgj = np.zeros(
            self.mdl
        )  # total normal current across GJ coupled membranes from intra- to intra- space
        self.Jc = np.zeros(self.mdl)  # current across membrane from intracellular conductivity
        self.Ec = np.zeros(self.mdl)  # intracellular electric field at membrane
        self.dvm = np.zeros(self.mdl)  # rate of change of Vmem
        self.drho = np.zeros(self.cdl)  # rate of change of charge in cell

        # Current averaged to cell centres:
        self.J_cell_x = np.zeros(self.cdl)
        self.J_cell_y = np.zeros(self.cdl)

        # Membrane current data structure initialization
        self.flx_mem_i = np.zeros(self.mdl)
        self.fluxes_mem = []
        self.I_mem = np.zeros(self.mdl)  # total current across membranes

        self.P_cells = np.zeros(self.cdl)  # initialize pressure in cells

        self.v_cell = np.zeros(self.cdl)  # initialize intracellular (long range) voltage
        self.vm = np.zeros(self.mdl)  # initialize Vmem at membranes
        self.vm_ave = np.zeros(self.cdl)  # initialize average Vmem at cell centres
        self.rho_cells = np.zeros(self.cdl)

        self.E_gj_x = np.zeros(
            self.mdl
        )  # electric field components across gap junctions (micro-field)
        self.E_gj_y = np.zeros(self.mdl)

        self.E_cell_x = np.zeros(self.mdl)  # intracellular electric field components (macro-field)
        self.E_cell_y = np.zeros(self.mdl)

        self.TJ_modulator = None  # register the tight junction modulator field to a 'None" object

        self.c_env_bound = []  # moving ion concentration at global boundary

        if p.is_ecm:  # special items specific to simulation of extracellular spaces only:
            # vectors storing separate cell and env voltages
            self.v_env = np.zeros(self.edl)  # voltage in the full environment
            self.rho_env = np.zeros(self.edl)  # charge in the full environment
            self.z_array_env = []  # ion valence array matched to env points
            self.D_env = []  # an array of diffusion constants for each ion defined on env grid
            self.Dtj_rel = []  # relative diffusion constants for ions across tight junctions

            self.E_env_x = np.zeros(cells.X.shape)  # electric field in environment, x component
            self.E_env_y = np.zeros(cells.X.shape)  # electric field in environment, y component

        else:  # items specific to simulation *without* extracellular spaces:
            # Initialize environmental volume:
            self.envV = np.zeros(self.mdl)
            self.envV[:] = p.vol_env
            self.v_env = np.zeros(len(cells.xypts))
            self.rho_env = np.zeros(len(cells.xypts))

        ion_names = list(p.ions_dict.keys())

        i = -1  # dynamic index

        # Go through ion list/dictionary and initialize all sim structures.
        for name in ion_names:
            # If this ion is enabled...
            if p.ions_dict[name] == 1:
                i = i + 1  # update the dynamic index

                str1 = "i" + name  # create the ion index

                # Dynamically add this field to the object.
                setattr(self, str1, i)

                self.ionlabel[vars(self)[str1]] = p.ion_long_name[name]

                # if name != 'P':
                self.movingIons.append(vars(self)[str1])

                # cell concentration for the ion
                str_cells = "c" + name + "cells"
                setattr(self, str_cells, np.zeros(self.cdl))
                vars(self)[str_cells][:] = p.cell_concs[name]

                # environmental concentration for the ion:
                str_env = "c" + name + "_env"

                setattr(self, str_env, np.zeros(self.edl))

                vars(self)[str_env][:] = p.env_concs[name]

                # base transmembrane diffusion for each ion
                str_Dm = "Dm" + name

                setattr(self, str_Dm, np.zeros(self.mdl))

                vars(self)[str_Dm][:] = p.mem_perms[name]

                # base gap junction (intercellular) diffusion for each ion
                str_Dgj = "Dgj" + name

                setattr(self, str_Dgj, np.zeros(len(cells.nn_i)))
                vars(self)[str_Dgj][:] = p.free_diff[name]

                # environmental diffusion for each ion:
                if p.is_ecm:
                    str_Denv = "D" + name

                    setattr(self, str_Denv, np.zeros(len(cells.xypts)))
                    vars(self)[str_Denv][:] = p.free_diff[name]

                # ion charge characteristic for intracellular:
                str_z = "z" + name

                setattr(self, str_z, np.zeros(self.cdl))
                vars(self)[str_z][:] = p.ion_charge[name]

                if p.is_ecm:  # ion charge characteristic for extracellular:
                    str_z2 = "z2" + name

                    setattr(self, str_z2, np.zeros(len(cells.xypts)))
                    vars(self)[str_z2][:] = p.ion_charge[name]

                self.cc_cells.append(vars(self)[str_cells])
                self.cc_env.append(vars(self)[str_env])

                self.zs.append(p.ion_charge[name])
                self.molar_mass.append(p.molar_mass[name])
                self.z_array.append(vars(self)[str_z])
                self.Dm_cells.append(vars(self)[str_Dm])
                self.D_gj.append(vars(self)[str_Dgj])
                self.D_free.append(p.free_diff[name])

                self.fluxes_mem.append(self.flx_mem_i)

                self.c_env_bound.append(p.env_concs[name])

                if p.is_ecm:
                    self.z_array_env.append(vars(self)[str_z2])
                    self.D_env.append(vars(self)[str_Denv])
                    self.Dtj_rel.append(p.Dtj_rel[name])

                if name == "Ca":
                    self.cCa_er = np.zeros(len(cells.cell_i))
                    self.cCa_er[:] = p.cCa_er

                    self.zCa_er = np.zeros(len(cells.cell_i))
                    self.zCa_er[:] = p.z_Ca

                    self.cc_er.append(self.cCa_er)
                    self.z_er.append(p.z_Ca)
                    self.z_array_er.append(self.zCa_er)

                if name == "M" and p.ions_dict["Ca"] == 1:
                    self.cM_er = np.zeros(len(cells.cell_i))
                    self.cM_er[:] = p.cCa_er

                    self.zM_er = np.zeros(len(cells.cell_i))
                    self.zM_er[:] = p.z_M

                    self.cc_er.append(self.cM_er)
                    self.z_er.append(p.z_M)
                    self.z_array_er.append(self.zM_er)

        # -------------------------------------------------------------------------------------------------------

        # convert all data structures to Numpy arrays:
        self.cc_cells = np.asarray(self.cc_cells)
        self.cc_env = np.asarray(self.cc_env)
        self.zs = np.asarray(self.zs)
        self.z_array = np.asarray(self.z_array)
        self.Dm_cells = np.asarray(self.Dm_cells)
        self.D_free = np.asarray(self.D_free)
        self.D_gj = np.asarray(self.D_gj)
        self.molar_mass = np.asarray(self.molar_mass)
        self.fluxes_mem = np.asarray(self.fluxes_mem)

        # boundary conditions for voltages:
        # voltage (scheduled dynamics might vary these values)
        self.bound_V = {}
        self.bound_V["T"] = 0
        self.bound_V["B"] = 0
        self.bound_V["L"] = 0
        self.bound_V["R"] = 0

        if p.is_ecm:  # items specific for extracellular spaces simulation:
            self.z_array_env = np.asarray(self.z_array_env)
            self.D_env = np.asarray(self.D_env)

            # redo environmental protein handling so that it's only present in the cell cluster:
            # self.c_env_bound[self.iM] += 1*self.c_env_bound[self.iP]
            # self.c_env_bound[self.iP] = 0.0
            #
            # new_P = np.zeros(self.edl)
            # new_P[cells.map_mem2ecm] = self.cc_env[self.iP][cells.map_mem2ecm]
            # new_P = fd.integrator(new_P.reshape(cells.X.shape), 0.5).ravel()
            #
            # change_M = np.ones(self.edl)*self.cc_env[self.iP]
            # change_M[cells.map_mem2ecm] = 0.0
            # change_M = fd.integrator(change_M.reshape(cells.X.shape), 0.5).ravel()
            #
            # self.cc_env[self.iP] = new_P
            # self.cc_env[self.iM] += change_M

            # initialize the environmental diffusion matrix:
            self.initDenv(cells, p)

        # gap junction specific arrays:
        self.id_gj = np.ones(len(cells.mem_i))  # identity array for gap junction indices...
        self.gjopen = (
            np.ones(len(cells.mem_i)) * cells.gj_default_weights
        )  # holds gap junction open fraction for each gj
        self.gjl = np.zeros(len(cells.mem_i))  # gj length for each gj
        self.gjl[:] = cells.gj_len

        # GJ fluxes storage vector:
        self.fluxes_gj = np.copy(self.fluxes_mem)

        self.gj_funk = None  # initialize this to None; set in init_dynamics

        # Initialize matrices to store concentration gradient information for each ion:
        self.fluxes_intra = np.zeros(self.fluxes_mem.shape)

        self.cc_at_mem = np.asarray([cc[cells.mem_to_cells] for cc in self.cc_cells])

        # # load in the microtubules object:
        # self.mtubes = Mtubes(self, cells, p)

        self.u_cells_x = 0.0
        self.u_cells_y = 0.0

        self.u_env_x = 0.0
        self.u_env_y = 0.0

    def initDenv(self, cells, p):
        """
        Initialize the environmental diffusion matrix and corresponding weight
        matrices, including tight and adherin junctions.
        """

        if p.is_ecm:
            for i, _ in enumerate(self.D_env):
                Denv_o = np.ones(self.edl) * self.D_free[i]

                # adherens junctions slow diffusion throughout the cell cluster:
                Denv_o[cells.envInds_inClust] = self.D_free[i] * p.D_adh

                # if p.env_type is True:
                Denv_o[cells.all_bound_mem_inds] = self.D_free[i] * p.D_tj * self.Dtj_rel[i]
                Denv_o[cells.interior_bound_mem_inds] = self.D_free[i] * p.D_tj * self.Dtj_rel[i]
                Denv_o[cells.ecm_inds_bound_cell] = self.D_free[i] * p.D_tj * self.Dtj_rel[i]

                # create an ecm diffusion grid filled with the environmental values
                self.D_env[i] = Denv_o * 1.0

            # create a matrix that weights the relative transport efficiency in the world space:
            D_env_weight = self.D_env[self.iNa] / self.D_env[self.iNa].max()
            self.D_env_weight = D_env_weight.reshape(cells.X.shape)
            self.D_env_weight_base = np.copy(self.D_env_weight)

            self.TJ_modulator = np.ones(self.D_env.shape)

        else:
            Denv_o = np.ones(len(cells.xypts))

            # if p.env_type is True:
            Denv_o[cells.all_bound_mem_inds] = p.D_tj
            Denv_o[cells.interior_bound_mem_inds] = p.D_tj
            Denv_o[cells.ecm_inds_bound_cell] = p.D_tj

            Denv_o = gaussian_filter(Denv_o.reshape(cells.X.shape), 1.0)

            self.D_env = np.copy(self.D_free)

            # create a matrix that weights the relative transport efficiency in the world space:
            self.D_env_weight = Denv_o.reshape(cells.X.shape)
            self.D_env_weight_base = np.copy(self.D_env_weight)

        self.TJ_targets = np.hstack(
            (cells.all_bound_mem_inds, cells.interior_bound_mem_inds, cells.ecm_inds_bound_cell)
        )

        self.Chi = np.ones(len(cells.xypts)) * p.er  # electrical susceptibility of pure water
        # self.Chi[cells.envInds_inClust] = 2.0e5  # electrical susceptibility of tissue

        self.Chi = gaussian_filter(self.Chi.reshape(cells.X.shape), 2)


class SeedCoreCallSite:
    def continue_seed(self, phase):
        self._callbacks.progressed_next(status="Creating core computational matrices...")
        phase.sim.init_core(phase)
