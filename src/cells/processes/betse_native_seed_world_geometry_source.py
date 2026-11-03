# Copyright 2014-2025 Alexis Pietak & Cecil Curry; see licenses/BETSE.txt.
"""Original post-lifecycle aliases and ordinary make_world body through mask.

This is a selected method boundary on the actual retained SEED objects. It is
not Python-frame restoration or complete make_world/phase/package admission.
Numerical methods and the grid constructor come from original native CodeTypes.
"""

CELLS_SHA256 = "be38678a4f0bd084044fe7d952d74a4550003ce9701f5d073d1f124ba6daeaf2"
GRID_SHA256 = "8186bc5c013db8aec224f6ed9b0892e944b2ddd4247f135ff19caf7419478350"


class SeedWorldGeometry:
    def finish_voronoi(self, image_mask):
        self.ecm_verts = self.mesh.vcell_verts
        self.cluster_mask = image_mask.clipping_matrix
        self.msize = image_mask.msize
        self.ecm_verts_unique = self.mesh.vor_verts

    def continue_world(self, phase):
        self.cell_index(phase.p)
        phase.callbacks.progressed_next(status="Calculating geometric cell properties...")
        self.cellVerts(phase.p)
        self.cellMatrices(phase.p)
        phase.callbacks.progressed_next(status="Calculating geometric cell volumes...")
        self.cell_vols(phase.p)
        self.mem_processing(phase.p)
        self.near_neigh(phase.p)
        phase.callbacks.progressed_next(status="Creating extracellular matrix (ECM) grid...")
        self.makeECM(phase.p)
        self.environment(phase.p)
        self.grid_len = len(self.xypts)
        self.make_maskM(phase.p)
