# Copyright 2014-2025 Alexis Pietak & Cecil Curry; see licenses/BETSE.txt.
# ruff: noqa: F821, E501
"""Original INIT tissue-profile/event setup, with no import-time source calls.

The complete init_profiles body is reused from the existing frozen literal.
The three event methods retain all native branches and the ignored-shuffle
copy quirk. Event firing and later dynamics are outside this literal boundary.
"""

from cells.processes import betse_native_seed_init_profiles_source as profiles


class InitTissueDynamics:
    init_profiles = profiles.SeedProfiles.init_profiles

    def init_events(self, phase):
        """
        Initialize all scheduled interventions for the passed simulation phase.

        Parameters
        ----------
        phase : SimPhase
            Current simulation phase.
        """
        self._finalize_events_global(phase)
        self._finalize_events_tissue(phase)

    def _finalize_events_global(self, phase):
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
