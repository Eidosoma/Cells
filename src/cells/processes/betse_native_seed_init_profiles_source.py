# Copyright 2014-2025 Alexis Pietak & Cecil Curry; see licenses/BETSE.txt.
# ruff: noqa: F821
"""Whole original init_profiles and its preceding SEED callback call site.

No source body runs at import. Picker and mapping helpers remain the genuine
retained native functions; this literal never creates a phase/profile owner.
Only method annotations/decorators are omitted in the source proof.
"""


class SeedProfiles:
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


class SeedProfilesCallSite:
    def continue_seed(self, phase):
        self._callbacks.progressed_next(status="Creating tissue, surgery, and boundary profiles...")
        phase.dyna.init_profiles(phase)
