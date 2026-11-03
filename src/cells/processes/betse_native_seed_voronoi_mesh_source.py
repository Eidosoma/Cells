# Copyright 2014-2025 Alexis Pietak & Cecil Curry; see licenses/BETSE.txt.
"""Original branch selection and constructor assignments, before lifecycle.

The native constructor and its helper bodies are acquired from their original
module by the driver. They are not copied from a normalized mesh adapter.
The SVG constructor is retained for correspondence; a genuine non-SVG parent
cannot gain SVG authority through this selected method boundary.
"""

# ruff: noqa: F821
NATIVE_PINS = {
    "betse/science/cells.py": ("be38678a4f0bd084044fe7d952d74a4550003ce9701f5d073d1f124ba6daeaf2"),
    "betse/science/math/mesh.py": (
        "fd0dc21e1f82aa71e19a487f3b91c4b5258f02aec4c69f22c2bf3c419e425c38"
    ),
}


class VoronoiMeshPrefix:
    def make_voronoi(self, phase):
        lattice_to_mesh_type = {
            CellLatticeType.HEX: "tri",
            CellLatticeType.SQUARE: "rect",
        }
        if phase.p.single_cell:
            self.mesh = DECMesh(
                cell_radius=phase.p.cell_radius,
                seed_points=None,
                use_alpha_shape=False,
                allow_merging=False,
                single_cell_noise=0.1,
                single_cell_sides=6,
                image_mask=None,
                make_all_operators=False,
                mesh_type=lattice_to_mesh_type[phase.p.cell_lattice_type],
                center=self.centre,
            )
        else:
            if phase.p.svg_override:
                self.mesh = DECMesh(
                    cell_radius=None,
                    seed_points=self.clust_xy,
                    alpha_shape=phase.p.alpha_shape,
                    use_centroids=phase.p.use_centroids,
                    use_alpha_shape=True,
                    single_cell_noise=0.5,
                    single_cell_sides=6,
                    image_mask=None,
                    allow_merging=True,
                    merge_thresh=0.2,
                    make_all_operators=False,
                    mesh_type=lattice_to_mesh_type[phase.p.cell_lattice_type],
                )
            else:
                self.mesh = DECMesh(
                    cell_radius=phase.p.cell_radius,
                    seed_points=self.clust_xy,
                    alpha_shape=phase.p.alpha_shape,
                    use_centroids=phase.p.use_centroids,
                    use_alpha_shape=True,
                    single_cell_noise=0.5,
                    single_cell_sides=6,
                    image_mask=None,
                    allow_merging=True,
                    merge_thresh=0.1,
                    close_thresh=0.1,
                    make_all_operators=False,
                    mesh_type=lattice_to_mesh_type[phase.p.cell_lattice_type],
                )
