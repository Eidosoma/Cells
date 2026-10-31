# Copyright 2014-2025 Alexis Pietak & Cecil Curry; see licenses/BETSE.txt.
"""Literal single-cell makeECM and MAC grid source; no environment/Poisson."""
# ruff: noqa: B007,E501,F821

import numpy as np
from scipy.spatial import cKDTree


# fmt: off
class CellsECM:
    def makeECM(self,p):

        """
        makeECM returns an regular scatter
        of points defined on the world space
        with dimensions wsx, wsy in [m].


        Creates
        -------
        self.delta          spacing between points of square environmental grid
        self.grid_obj       an instance of FiniteDiffSolver, with MACs grid defined within
        self.X, self.Y      major X and Y grid (cell centre points) of MACs grid
        self.map_ij2k       mapping between (i,j) indices of 2D grids and the k indice of the unravelled grid
                            (for grid-cell centres)
        self.index_k        unravelled grid k-index
        self.ecm_sa         surface area of the extracellular space grid-cell face
        self.ecm_vol        volume of the extracellular space grid-cell
        self.xypts          numpy array listing [x,y] of world seed points

        self.xmin, self.xmax      dimensions of world grid
        self.ymin, self.ymax

        self.centre     [x,y] coordinate of world centre

        Notes
        -------
        Uses Numpy arrays
        """

        # base parameter definitions
        self.delta = ((self.xmax-self.xmin)/p.grid_size) # spacing between grid points

        self.grid_obj = fd.FiniteDiffSolver()

        self.grid_obj.cell_grid(self.delta,self.xmin,self.xmax,self.ymin,self.ymax)

        self.X = self.grid_obj.cents_X
        self.Y = self.grid_obj.cents_Y

        self.xypts = self.grid_obj.xy_cents
        self.map_ij2k = self.grid_obj.map_ij2k_cents

        # linear k index:
        self.index_k = [x for x in range(0,len(self.xypts))]

        # FIXME temporary addition of block of sphaghetti code for later use/improvement:
        #--------------------------------------------------------------
        # Create singular ecm points and data-structures mapping from cell to ecm nn
        # where 'ecm' is different than the environmental grid points defined in self.xypts and corresponds
        # to the shared membrane midpoint between two cells (e.g. a true 'extracellular' matrix point).

        bflags_ecm_o = [] # flags for ecm points at boundaries
        ecm_points_o = [] # the points, prior to processing

        for i, (mem_i, mem_j) in enumerate(self.mem_nn): # for each membrane mid pair in mem near neighbours...

            xmem = self.mem_mids_flat[:, 0]
            ymem = self.mem_mids_flat[:, 1]

            xi = (xmem[mem_i] + xmem[mem_j])/2 # average the x and y points
            yi = (ymem[mem_i] + ymem[mem_j])/2

            ecm_points_o.append([xi, yi]) # append the pair to the points list

            if mem_i == mem_j:         # if membrane indices are equal, they must be a boundary:
                bflags_ecm_o.append([xi, yi])

        ecm_points_unique = np.unique(ecm_points_o, axis = 0)   # get only the unique points from the above
        bflags_ecm_unique = np.unique(bflags_ecm_o, axis = 0)

        ecm_list = ecm_points_unique.tolist()     # convert them back to a list
        bflags_list = bflags_ecm_unique.tolist()

        bflags_ecm = []

        for bf in bflags_list:

            bflags_ecm.append(ecm_list.index(bf))   # get the proper index for the boundary flag from points list

        self.ecm_points = np.asarray(ecm_points_unique)  # assign final data structures
        self.bflags_ecm = np.asarray(bflags_ecm)

        self.ecm_i = np.asarray([ii for ii in range(len(self.ecm_points))])

        xmem_mids = (self.mem_mids_flat[self.mem_nn[:,0]]
                     + self.mem_mids_flat[self.mem_nn[:,1]])/2

        points_tree_ecm = cKDTree(self.ecm_points)


        mem_to_ecm = []
        for xm in xmem_mids:

            _,ei = points_tree_ecm.query(xm)
            mem_to_ecm.append(ei)

        self.mem_to_ecm = np.asarray(mem_to_ecm)


        cell_to_ecm = []
        for ci, mem_is in enumerate(self.cell_to_mems):

            mem_pts = xmem_mids[mem_is] # get membrane mids surrounding this cell
            _, eci = points_tree_ecm.query(mem_pts)
            cell_to_ecm.append(eci.tolist())

        self.cell_to_ecm = np.asarray(cell_to_ecm, dtype=object)

        self.all_points = np.vstack((self.cell_centres, self.ecm_points))
        self.all_points_imap = np.hstack((self.cell_i, self.ecm_i))
        self.all_i = np.asarray([ii for ii in range(len(self.all_points))])
        self.all_points_ecm_i = len(self.cell_i) + self.ecm_i
        self.all_points_cell_i = self.cell_i
        self.adl = len(self.all_points)

        points_tree_mems = cKDTree(self.mem_mids_flat)
        ecm_to_mems_o = points_tree_mems.query_ball_point(
            self.ecm_points, r=10*p.cell_space)

        ecm_to_mems = []
        ecm_to_cells = []

        for i, ecm_is in enumerate(ecm_to_mems_o):
            ecm_to_mems.append(ecm_is)
            ecm_to_cells.append(self.mem_to_cells[ecm_is])

        self.ecm_to_mems = np.asarray(ecm_to_mems, dtype=object)
        self.ecm_to_cells = np.asarray(ecm_to_cells, dtype=object)

        # Surface area and volume of ecm spaces:
        self.ecm_vol = []
        self.ecm_sa = []

        for mis in self.ecm_to_mems:
            esa = self.mem_sa[mis[0]]
            self.ecm_vol.append(esa*p.cell_space)
            self.ecm_sa.append(esa*1)

        self.ecm_vol = np.asarray(self.ecm_vol)
        self.ecm_sa = np.asarray(self.ecm_sa)

        self.ecmdl = len(self.ecm_points)

CELLS_SHA256 = 'be38678a4f0bd084044fe7d952d74a4550003ce9701f5d073d1f124ba6daeaf2'
class FiniteDiffSolver:
    def __init__(self) -> None:
        pass

    def cell_grid(self,grid_delta, xmin, xmax, ymin, ymax) -> None:
        """
        Make a staggered n x n grid for use with finite volume or MACs method.

        One n x n grid contains the cell centres.
        One n+1 x n+1 grid contains the cell corners (vertices)
        One n+1 x n grid contains the u-coordinate points for velocity and x-coordinate for fluxes
        One n x n+1 grid contains the v-coordinate points for velocity and y-coordinate for fluxes
        """

        # max-min dimensions of the 2D world space:
        self.xmin = xmin
        self.xmax = xmax
        self.ymin = ymin
        self.ymax = ymax

        # spacing of the grid points (uniform in x and y dimensions):
        self.delta = grid_delta

        # number of points in the x and y directions
        self.grid_nx = int((self.xmax - self.xmin)/grid_delta)
        self.grid_ny = int((self.ymax - self.ymin)/grid_delta)

        # creation of the first mesh -- these are the corners of each MACs grid square:
        xv = np.linspace(xmin,xmax,self.grid_nx+1)
        yv = np.linspace(ymin,ymax,self.grid_ny+1)
        self.verts_X, self.verts_Y = np.meshgrid(xv,yv)

        x_verts = self.verts_X.ravel()
        y_verts = self.verts_Y.ravel()
        self.xy_verts = np.column_stack((x_verts,y_verts))
        self.verts_shape = self.verts_X.shape

        # grid and coordinate vectors defining the centre points of each cell:
        self.cents_X = (self.verts_X[0:-1,0:-1] + self.verts_X[0:-1,1:])/2
        self.cents_Y = (self.verts_Y[0:-1,0:-1] + self.verts_Y[1:,0:-1])/2

        x_cent = self.cents_X.ravel()
        y_cent = self.cents_Y.ravel()

        # unravelled x,y points for cell centres:
        self.xy_cents = np.column_stack((x_cent,y_cent))

        self.cents_shape = self.cents_X.shape

        # define a mapping between the (i,j) centers mesh and the linear unravelled k index:
        self.map_ij2k_cents = []

        for i, row in enumerate(self.cents_X):
            for j, val in enumerate(row):
                self.map_ij2k_cents.append([i,j])

        self.map_ij2k_cents = np.asarray(self.map_ij2k_cents)

        # Next define grids for the x and y cordinates as midpoints of each MACs cell:
        # cell side midpoints in the x (u) and x (v) directions:
        mx = self.cents_X[0,:]
        my = self.verts_Y[:,0]
        self.v_X, self.v_Y = np.meshgrid(mx,my)

        x_m = self.v_X.ravel()
        y_m = self.v_Y.ravel()

        # points on which y co-ordinate of velocity is defined:
        self.v_pts = np.column_stack((x_m,y_m))
        self.v_shape = self.v_X.shape

        self.map_ij2k_v = []

        for i, row in enumerate(self.v_X):
            for j, val in enumerate(row):
                self.map_ij2k_v.append([i,j])

        self.map_ij2k_v = np.asarray(self.map_ij2k_v)

        nx = self.verts_X[0,:]
        ny = self.cents_Y[:,0]
        self.u_X, self.u_Y = np.meshgrid(nx,ny)

        x_n = self.u_X.ravel()
        y_n = self.u_Y.ravel()

        # points on which x co-ordinate of velocity is defined:
        self.u_pts = np.column_stack((x_n,y_n))
        self.u_shape = self.u_X.shape

        self.map_ij2k_u = []

        for i, row in enumerate(self.u_X):
            for j, val in enumerate(row):
                self.map_ij2k_u.append([i,j])

        self.map_ij2k_u = np.asarray(self.map_ij2k_u)

GRID_SHA256 = '8186bc5c013db8aec224f6ed9b0892e944b2ddd4247f135ff19caf7419478350'
