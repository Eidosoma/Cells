# Copyright 2014-2025 Alexis Pietak & Cecil Curry; see licenses/BETSE.txt.
"""Literal selected environment stores/methods; stops before Poisson."""
# ruff: noqa: B007,E501

import numpy as np
from scipy import interpolate as interp
from scipy.ndimage import gaussian_filter
from scipy.spatial import cKDTree

from cells.processes.betse_post_cut_mesh_contact_source import tb

# fmt: off
NATIVE_CELLS_SHA256 = 'be38678a4f0bd084044fe7d952d74a4550003ce9701f5d073d1f124ba6daeaf2'
NATIVE_PARAMETERS_SHA256 = 'f36ec747918aa285ca043fe51086bcff4e4e2198cd4f30a138f1e58a51ecf85e'
STORE_LINES = [521, 533, 534, 535, 536, 1118, 1119, 1122, 1127, 1128, 1129, 1130, 1131]
STORES_AST_SHA256 = 'fcdca2bb801ccfb3164118d0ddf9269a17c773ede5460a3cbd9345e823caaeef'

class ParameterStores:
    def initialize_source_stores(self):
        self.plot_grid_size = 50
        self.wsx = self.world_len
        self.wsy = self.world_len
        self.cell_height = float(self._conf['world options']['cell height'])
        self.cell_space = float(self._conf['world options']['cell spacing'])
        self.ac = 1e-06
        self.scale_cell = 0.99
        self.tm = 7.5e-09
        self.d_cell = self.cell_radius * 2
        self.nx = int(self.wsx / self.d_cell)
        self.ny = int(self.wsy / self.d_cell)
        self.wsx = self.wsx + 5 * self.cell_lattice_disorder * self.d_cell
        self.wsy = self.wsy + 5 * self.cell_lattice_disorder * self.d_cell

class CellsEnvironment:
    def environment(self,p):

        """
        Defines conditions for points in contact with the global environment at the outer boundary
        of the square world.

        Notes
        -------

        This is how to access all elements in a main-grid format from the k-vector:
        Z[cells.map_ij2k[:,0],cells.map_ij2k[:,1]]

        or access elements in a main-grid format to a subset of the k-vector:

        accessing bottom boundary:
        Z[cells.map_ij2k[bBot_k][:,0],cells.map_ij2k[bBot_k][:,1]]

        accessing all cells:
        Z[cells.map_ij2k[map_cell2ecm][:,0],cells.map_ij2k[map_cell2ecm][:,1]] = 10.0

        """


        # global properties of ecm spaces:
        self.ecm_sa = 4*self.delta*p.cell_height # surface area of ecm space in direction of cell flux
        # self.ecm_vol = (p.cell_height*self.delta**2)*np.ones(len(self.xypts))  # volume of ecm space
        self.ecm_vol = (p.cell_height*self.delta**2)  # volume of ecm space

        # ratio of mean cell volume to ecm square volume (gives approx num cells per ecm square)
        self.ratio_cell2ecm = self.ecm_vol/self.cell_vol.mean()

        #-------------------------

        # first obtain a structure to map to total xypts vector index:
        self.points_tree = cKDTree(self.xypts)

        # define a mapping between a cell and its ecm space in the full list of xy points for the world:
        _, self.map_cell2ecm = self.points_tree.query(self.cell_centres)
        _, self.map_mem2ecm  = self.points_tree.query(self.mem_mids_flat, k=1)

        # get a list of all membranes for boundary cells:
        all_bound_mem_inds = self.cell_to_mems[self.bflags_cells]
        all_bound_mem_inds, _ ,_ = tb.flatten(all_bound_mem_inds)

        # need these to obtain cluster membrane values from the ECM perspective, or it won't write to the array!
        self.ecm_bound_k = self.map_mem2ecm[self.bflags_mems]  # k indices to xypts for ecms on cluster boundary

        self.ecm_allbound_k = self.map_mem2ecm[all_bound_mem_inds]

        # self.all_clust_pts = np.vstack((self.cell_centres,self.mem_mids_flat))

        # get a list of k indices to the four exterior (global) boundaries of the rectangular world:
        bBot_x = self.X[0,:]
        bTop_x = self.X[-1,:]
        bL_x = self.X[:,0]
        bR_x = self.X[:,-1]

        bBot_y = self.Y[0,:]
        bTop_y = self.Y[-1,:]
        bL_y = self.Y[:,0]
        bR_y = self.Y[:,-1]

        bBot_pts = np.column_stack((bBot_x, bBot_y))
        bTop_pts = np.column_stack((bTop_x, bTop_y))
        bL_pts = np.column_stack((bL_x, bL_y))
        bR_pts = np.column_stack((bR_x, bR_y))

        _, self.bBot_k = self.points_tree.query(bBot_pts)
        _, self.bTop_k = self.points_tree.query(bTop_pts)
        _, self.bL_k = self.points_tree.query(bL_pts)
        _, self.bR_k = self.points_tree.query(bR_pts)

        # get a mapping specifying which mem mids an ecm space interacts with:
        self.map_ecm2mem = [[] for ind in self.xypts]

        for ind_mem, ind_ecm in enumerate(self.map_mem2ecm):
            self.map_ecm2mem[ind_ecm].append(ind_mem)

        # next, find out the total set of ecm spaces that interact with membranes
        # and develop the "weight-paint" functions:
        self.envInds_inClust = []
        self.memSa_per_envSquare = np.zeros(len(self.xypts))
        self.mems_per_envSquare = np.zeros(len(self.xypts))

        # create an array to hold the "true" extracellullar volume,
        # and populate it initially with the environmental square volume:
        self.true_ecm_vol = np.ones(len(self.xypts))*self.ecm_vol

        for ind_ecm, lst in enumerate(self.map_ecm2mem):

            if len(lst) > 0:
                self.envInds_inClust.append(ind_ecm)
                sas = np.sum(self.mem_sa[lst])
                self.memSa_per_envSquare[ind_ecm] = sas
                self.mems_per_envSquare[ind_ecm] = len(lst)

                self.true_ecm_vol[ind_ecm] = sas*p.cell_space*(1/2)

        self.envInds_inClust = np.asarray(self.envInds_inClust)

        # correction coefficient for converting from cell to env divergences:
        self.cell2env_corrF = (self.cell_vol / self.true_ecm_vol[self.map_cell2ecm]) * (self.ecm_sa / self.cell_sa)

        # calculate indices to tag TJ at boundary
        neigh_to_bcells, _, _ = tb.flatten(self.cell_nn[self.bflags_cells])
        all_bound_mem_inds_o = self.cell_to_mems[self.bflags_cells]
        interior_bound_mem_inds_o = self.cell_to_mems[neigh_to_bcells]
        interior_bound_mem_inds_o, _, _ = tb.flatten(interior_bound_mem_inds_o)
        all_bound_mem_inds_o, _, _ = tb.flatten(all_bound_mem_inds_o)

        self.all_bound_mem_inds = self.map_mem2ecm[all_bound_mem_inds_o]
        self.interior_bound_mem_inds = self.map_mem2ecm[interior_bound_mem_inds_o]
        self.inds_outmem = self.map_mem2ecm[self.bflags_mems]
        self.ecm_inds_bound_cell = self.map_cell2ecm[self.bflags_cells]

        # create the matrix that allows individual membrane normal fluxes to be mapped to each ecm square:
        # If Fmem is the normal component of a vector field wrt individual membranes,
        # the result of M_divmap_mem2ecm *dot* Fmem  is the divergence of the flux wrt the environment.
        self.M_divmap_mem2ecm = np.zeros((len(self.xypts), len(self.mem_i)))

        for mem_i, ecm_i in enumerate(self.map_mem2ecm):
            mem_sa = self.mem_sa[mem_i]
            self.M_divmap_mem2ecm[ecm_i, mem_i] += (mem_sa)

    def make_maskM(self,p):
        '''
        Create structures for plotting interpolated data on cell centres and
        differentiating between the cell cluster and environment.
        '''

        voronoiTree = cKDTree(self.xypts)
        _, self.map_voronoi2ecm = voronoiTree.query(self.ecm_verts_unique)

        self.voronoi_mask = np.zeros(len(self.xypts))
        self.voronoi_mask[self.map_voronoi2ecm]=1

        xv = np.linspace(self.xmin,self.xmax,p.plot_grid_size)
        yv = np.linspace(self.xmin,self.xmax,p.plot_grid_size)

        X,Y = np.meshgrid(xv,yv)

        self.Xgrid = X
        self.Ygrid = Y

        self.maskM = interp.griddata(
            (self.xypts[:,0],self.xypts[:,1]),
            self.voronoi_mask,(self.Xgrid,self.Ygrid),
            method='linear',fill_value=0)

        self.maskM = gaussian_filter(self.maskM, 1, mode='nearest')
        self.maskM = np.round(self.maskM,0)

        self.maskECM = interp.griddata(
            (X.ravel(),Y.ravel()),self.maskM.ravel(),
            (self.X, self.Y),
            method='linear',fill_value=0)
        self.maskECM = gaussian_filter(self.maskECM, 1, mode='nearest')
        self.maskECM = np.round(self.maskECM,0)

        self.inds_env = list(*(self.maskECM.ravel() == 0).nonzero())
        self.inds_clust = list(*(self.maskECM.ravel() == 1).nonzero())

        self.voronoi_centres = self.xypts

        vertTree = cKDTree(self.voronoi_centres)
        _, self.cell_to_grid = vertTree.query(self.cell_centres)

    def assign_grid_len(self):
        self.grid_len = len(self.xypts)
