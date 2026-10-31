# Copyright 2014-2025 Alexis Pietak & Cecil Curry; see licenses/BETSE.txt.
"""Selected initial-geometry parameter stores in original load order.

Normalized scalar configuration only; no full Parameters/YAML/package claim.
All stores execute on the same fresh instance before actual caller creation.
"""

# fmt: off
NATIVE_PARAMETERS_SHA256 = 'f36ec747918aa285ca043fe51086bcff4e4e2198cd4f30a138f1e58a51ecf85e'
STORE_LINES = [533, 534, 535, 536, 1118, 1119, 1122, 1127, 1128, 1129, 1130, 1131]
STORES_AST_SHA256 = 'fa39c973498134d283a3930f50ee4e22e314fdcce68e4d9b7baa16178458ce5e'

class ParameterStores:
    def initialize_source_stores(self):
        self.wsx = self.world_len
        self.wsy = self.world_len
        self.cell_height = float(self._conf['world options']['cell height'])
        self.cell_space = float(self._conf['world options']['cell spacing'])
        self.ac = 1.0e-6
        self.scale_cell = 0.99
        self.tm = 7.5e-9
        self.d_cell = self.cell_radius * 2
        self.nx = int(self.wsx / self.d_cell)
        self.ny = int(self.wsy / self.d_cell)
        self.wsx = self.wsx + 5 * self.cell_lattice_disorder * self.d_cell
        self.wsy = self.wsy + 5 * self.cell_lattice_disorder * self.d_cell
