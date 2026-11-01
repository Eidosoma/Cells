# Copyright 2014-2025 Alexis Pietak & Cecil Curry; see licenses/BETSE.txt.
"""Six literal data stores after environmental Poisson in Cells.make_world.

These selected statement boundaries do not include phase callbacks, package
authority, a gap-junction Laplacian construction or physical admission.
"""

import numpy as np

CELLS_SHA256 = "be38678a4f0bd084044fe7d952d74a4550003ce9701f5d073d1f124ba6daeaf2"
STORE_LINES = (517, 518, 521, 522, 525, 526)
STORE_NAMES = ("lapGJinv", "lapGJ", "M_sum_mem_to_ecm", "gradMem", "cell_i", "gj_default_weights")


class CellsWorldTail:
    def clear_lapGJinv(self):
        self.lapGJinv = None

    def clear_lapGJ(self):
        self.lapGJ = None

    def clear_M_sum_mem_to_ecm(self):
        self.M_sum_mem_to_ecm = None

    def clear_gradMem(self):
        self.gradMem = None

    def coerce_cell_i(self):
        self.cell_i = np.asarray(self.cell_i)

    def default_gj_weights(self):
        self.gj_default_weights = np.ones(len(self.mem_i))
