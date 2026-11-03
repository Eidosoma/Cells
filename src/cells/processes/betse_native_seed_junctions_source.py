# Copyright 2014-2025 Alexis Pietak & Cecil Curry; see licenses/BETSE.txt.
"""Whole original redo_gj and the four ordered SEED junction/network statements.

This is a literal source proof only. Native np, logs and owner objects are not
manufactured here. calc_gj_vects and graphLaplacian reuse existing exact source.
"""

from __future__ import annotations

# ruff: noqa: F821
CELLS_SHA256 = "be38678a4f0bd084044fe7d952d74a4550003ce9701f5d073d1f124ba6daeaf2"
RUNNER_SHA256 = "6a9389f106d717dc83ea1a594a64aa5bde278cef9a17b2a8ff01251b08d7be8a"
REUSED_SOURCE_PINS = {
    "src/cells/processes/betse_native_post_world_operators_source.py": (
        "f72d244066064b42427e89229742978b2330092c0b7663c8204ead2b68347c08"
    ),
    "src/cells/processes/betse_post_cut_mesh_contact_source.py": (
        "432e2453c4b5e0a4d46eb46c79bb1440093a042caa44ac2d00e09d20130de4b7"
    ),
}


class SeedJunctions:
    def redo_gj(self, phase):
        """
        (Re)create the gap junction connection network after assessing tissue
        profile requests for the passed simulation phase.

        Parameters
        ----------
        phase : SimPhase
            Current simulation phase.
        """
        dyna = phase.dyna
        p = phase.p
        flag_cell_nn = [[] for x in range(0, len(self.cell_i))]
        for tissue_name, tissue_profile in dyna.tissue_name_to_profile.items():
            if tissue_profile.is_gj_insular:
                cell_targets = dyna.cell_target_inds[tissue_name]
                for i, inds in enumerate(self.cell_nn):
                    check_a = int(i in cell_targets)
                    for ind_b in inds:
                        check_b = int(ind_b in cell_targets)
                        if check_a != check_b:
                            flag_cell_nn[i].append(ind_b)
        new_cell_nn = [[] for x in range(0, len(self.cell_i))]
        for i, flags in enumerate(flag_cell_nn):
            neighs = self.cell_nn[i]
            for cell in neighs:
                if cell not in flags:
                    new_cell_nn[i].append(cell)
        self.cell_nn_connected = np.asarray(new_cell_nn, dtype=object)
        self.num_nn = []
        for indices in self.cell_nn:
            self.num_nn.append(len(indices))
        self.average_nn = sum(self.num_nn) / len(self.num_nn)
        self.num_nn = np.asarray(self.num_nn)
        self.gj_default_weights = np.ones(len(self.mem_i))
        for cell_i, nn_cell_i_set in enumerate(self.cell_nn_connected):
            mem_i_set = self.cell_to_mems[cell_i]
            for mem_i in mem_i_set:
                mem_j = self.nn_i[mem_i]
                if mem_j != mem_i:
                    cell_j = self.mem_to_cells[mem_j]
                    if cell_j not in nn_cell_i_set:
                        self.gj_default_weights[mem_i] = 0.0
        self.calc_gj_vects(p)


class SeedJunctionsCallSite:
    def continue_seed(self, phase):
        self._callbacks.progressed_next(status="Creating gap junction connection network...")
        phase.cells.redo_gj(phase)
        self._callbacks.progressed_next(status="Creating cell network Poisson solver...")
        phase.cells.graphLaplacian(self._p)
