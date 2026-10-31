"""Two exact source control branches at the supplied SIM event entry."""

import numpy as np


def entry_controls(self, cells, p):
    if p.global_options["gj_block"] != 0:
        self.gj_block = np.ones(len(cells.mem_i))
    else:
        self.gj_block = 1
    if p.global_options["NaKATP_block"] != 0:
        self.NaKATP_block = np.ones(self.mdl)
    else:
        self.NaKATP_block = 1
