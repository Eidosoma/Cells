# Copyright 2014-2025 Alexis Pietak & Cecil Curry; see licenses/BETSE.txt.
"""Selected native non-SVG multi-cell caller and fresh parameter source.

Only phase.p is normalized to an explicitly owned p argument. Original Cells
constructor/lattice/image and numerical clip/lifecycle methods are reused.
The unselected SVG branch is refused before any parameter/source work.
"""
# ruff: noqa: E501,F821

from cells.processes.betse_native_single_cell_caller_lattice_source import CellLatticeType

NATIVE_PINS = {'parameters.py': 'f36ec747918aa285ca043fe51086bcff4e4e2198cd4f30a138f1e58a51ecf85e', 'cells.py': 'be38678a4f0bd084044fe7d952d74a4550003ce9701f5d073d1f124ba6daeaf2', 'math/mesh.py': 'fd0dc21e1f82aa71e19a487f3b91c4b5258f02aec4c69f22c2bf3c419e425c38'}
STORE_LINES = [521, 533, 534, 535, 536, 544, 546, 558, 560, 575, 578, 582, 1118, 1119, 1122, 1127, 1128, 1129, 1130, 1131]
STORES_AST_SHA256 = '0eec6750684ca2a4b6b142af828c7774a81389a68f71bc5e7df457ea71003422'
CALLER_LINES = (888, 930, 947, 954, 958, 959, 961)
CALLER_AST_SHA256 = '98da72e4e3543dffcdbe7c0477581973037f0cefaadf50dcfa6d43e55d9ea0d9'

# fmt: off
class ParameterStores:
    def initialize_source_stores(self):
        self.plot_grid_size = 50
        self.wsx = self.world_len
        self.wsy = self.world_len
        self.cell_height = float(self._conf['world options']['cell height'])
        self.cell_space = float(self._conf['world options']['cell spacing'])
        mesh_refine = self._conf['world options'].get('mesh refinement', None)
        if mesh_refine is not None:
            self.refine_mesh = mesh_refine['refine mesh']
            self.maximum_voronoi_steps = int(mesh_refine['maximum steps'])
            self.voronoi_convergence = float(mesh_refine['convergence threshold'])
        else:
            self.refine_mesh = False
            self.maximum_voronoi_steps = 10
            self.voronoi_convergence = 2.5
        svg_import = self._conf['world options'].get('import from svg', None)
        if svg_import is not None:
            self.svg_size = svg_import['svg size']
            self.svg_override = svg_import['svg override']
            svg_cells_fname_o = svg_import['cells from svg']
            self.svg_cells_fname = pathnames.join(self.conf_dirname, svg_cells_fname_o)
        else:
            self.svg_override = False
            self.svg_cells_fname = None
            self.svg_size = None
        self.single_cell = self._conf['world options'].get('simulate single cell', False)
        self.alpha_shape = self._conf['world options'].get('alpha shape', 0.05)
        self.use_centroids = self._conf['world options'].get('use centers', False)
        self.ac = 1e-06
        self.scale_cell = 0.99
        self.tm = 7.5e-09
        self.d_cell = self.cell_radius * 2
        self.nx = int(self.wsx / self.d_cell)
        self.ny = int(self.wsy / self.d_cell)
        self.wsx = self.wsx + 5 * self.cell_lattice_disorder * self.d_cell
        self.wsy = self.wsy + 5 * self.cell_lattice_disorder * self.d_cell

class CellsMulti:
    def make_voronoi_non_svg(self, p, image_mask):
        lattice_to_mesh_type = {CellLatticeType.HEX: 'tri', CellLatticeType.SQUARE: 'rect'}
        self.mesh = DECMesh(cell_radius=p.cell_radius, seed_points=self.clust_xy, alpha_shape=p.alpha_shape, use_centroids=p.use_centroids, use_alpha_shape=True, single_cell_noise=0.5, single_cell_sides=6, image_mask=None, allow_merging=True, merge_thresh=0.1, close_thresh=0.1, make_all_operators=False, mesh_type=lattice_to_mesh_type[p.cell_lattice_type])
        self.mesh.clip_and_refine(image_mask, smoothing=None, refinement=p.refine_mesh, max_steps=p.maximum_voronoi_steps, convergence=p.voronoi_convergence, fix_bounds=True)
        self.ecm_verts = self.mesh.vcell_verts
        self.cluster_mask = image_mask.clipping_matrix
        self.msize = image_mask.msize
        self.ecm_verts_unique = self.mesh.vor_verts

    def cell_index(self, p) -> None:
        '''
        (Re)define the array of all cell centres (i.e., :attr:`cell_centres`)
        from every corresponding Voronoi polygon.

        This method is typically called *after* creating, closing, and clipping
        the Voronoi diagram for this cell cluster. Doing so creates an ordering
        of cells consistent with all Voronoi polygons, membrane domains, and
        extracellular matrix (ECM)-driven polygons and segments.
        '''

        self.cell_centres = self.mesh.vor_cents

        self.cell_vol = self.mesh.vor_sa*p.cell_height

class MeshPipeline:
    def clip_and_refine(self, imagemask, smoothing=None, refinement=True, max_steps=25, convergence=7.5, fix_bounds=True):
        self.pre_mesh()
        self.clip_to_curve(imagemask)
        if smoothing is not None:
            self.init_mesh()
            self.laplacian_smoothing(stepsize=smoothing)
            self.pre_mesh()
        if refinement:
            self.refine_mesh(max_steps=max_steps, convergence=convergence, fix_bounds=fix_bounds)
            self.pre_mesh()
        self.create_core_operators()
        if self.make_all_operators:
            self.create_aux_operators()
        logs.log_info('Mesh creation complete!')
# fmt: on
