# Copyright 2014-2025 Alexis Pietak & Cecil Curry; see licenses/BETSE.txt.
"""Selected normalized parameter stores in original Parameters.load source order.

This is a bounded scalar-configuration projection, not Parameters/YAML/package
execution. The original cell-height lookup runs before the later lattice stores
on the same actual parameter instance subsequently passed to Cells.
"""

# Preserve literal source statements, including their original expression order.
# fmt: off
NATIVE_PARAMETERS_SHA256 = 'f36ec747918aa285ca043fe51086bcff4e4e2198cd4f30a138f1e58a51ecf85e'
STORE_LINES = [533, 534, 535, 1118, 1127, 1128, 1129, 1130, 1131]
STORES_AST_SHA256 = 'aa8598dcc6fdfe6005a55d917ad98e1a8b86bae3c2822ef844f7c85537428f1d'

class ParameterStores:
    def initialize_source_stores(self):
        self.wsx = self.world_len
        self.wsy = self.world_len
        self.cell_height = float(self._conf['world options']['cell height'])
        self.ac = 1.0e-6
        self.d_cell = self.cell_radius * 2
        self.nx = int(self.wsx / self.d_cell)
        self.ny = int(self.wsy / self.d_cell)
        self.wsx = self.wsx + 5 * self.cell_lattice_disorder * self.d_cell
        self.wsy = self.wsy + 5 * self.cell_lattice_disorder * self.d_cell
