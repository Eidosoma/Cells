#!/usr/bin/env python3
# ....................{ LICENSE                            }....................
# Copyright 2014-2025 by Alexis Pietak & Cecil Curry.
# See "LICENSE" for further details.
# Cells retains that upstream license in licenses/BETSE.txt.

# ....................{ TODO                               }....................
# FIXME: Get face to edge mappings for tri and vor.
# FIXME: Make mids mappers.

# FIXME: Consider converting ragged arrays (i.e., arrays defined with
# "dtype=object") into their non-ragged equivalents. The latter are considerably
# faster and smaller than the former, but require special handling (e.g.,
# padding by nulls or zeroes) to account for ragged subarray sizes. See also the
# following canonical StackOverflow post on the subject:
#    https://stackoverflow.com/a/30960883/2809027

# ....................{ IMPORTS                            }....................
# ruff: noqa: B007,B905,E721,F841,F821,E501
"""Pinned native source boundary; appended locals return only; no native geometry admission."""

from __future__ import annotations

import copy
import math
from types import SimpleNamespace

import numpy as np
from numpy import array
from scipy.spatial import cKDTree


def flatten(ls_of_ls: SequenceTypes) -> tuple:
    """
    Flattens a doubly-nested sequences of sequences (e.g., list of lists,
    two-dimensional Numpy array).

    For convenience, this function silently flattens two-dimensional Numpy
    arrays to lists of lists. Notheless, for both sanity and clarity, callers
    are recommended to instead call the standard :meth:`numpy.ndarray.flatten`
    method when this sequence is known to be a Numpy array.

    Parameters
    ----------
    ls_of_ls : SequenceTypes
        Nested sequence of sequences (e.g., ``[[a,b,c],[d,e,f],[g,h,i]]``).

    Returns
    -------
    (list, list, list)
        3-tuple ``(ls_flat, ind_map, rind_map)``, where:
        * ``ls_flat`` is a flattened version of the input list (e.g.,
          ``[a,b,c,d,e,f,g,h,i]``).
        * ``ind_map`` is a list of forward indices mapping from all indices of
          the output ``ls_flat`` list to the corresponding indices of the input
          ``ls_of_ls`` list (e.g., ``ind_map[5] = [0,5]``, which would yield the
          same value for ``ls_flat[5]`` and ``ls_of_ls[0][5]``).
        * ``rind_map`` is a list of lists of reverse indices mapping from all
          indices of the input ``ls_of_ls`` list to the corresponding indices of
          the output ``ls_flat`` list.
    """
    ls_flat = []
    ind_map = []
    rind_map = copy.deepcopy(ls_of_ls)
    for i, sublist in enumerate(ls_of_ls):
        for j, val in enumerate(sublist):
            ls_flat.append(val)
            ind_map.append([i, j])
    for j, vals in enumerate(ind_map):
        rind_map[vals[0]][vals[1]] = j
    return (ls_flat, ind_map, rind_map)


tb = SimpleNamespace(flatten=flatten)
logs = SimpleNamespace(log_info=lambda *args: None)


class MeshKernel:
    def cut_mesh(self, tvert_targets: ndarray) -> Tuple[ndarray, ndarray]:
        """
        Delete tri-verts from the DEC mesh system and rebuild core operators.

        Parameters
        ----------
        tvert_targets : np.ndarray
            One-dimensional Numpy array of the indices of all tri-verts to be
            removed from this mesh.

        Returns
        -------
        tedge_targets: ?
            Indices to *restructure* (not delete) data on edges (used as
            ``foo2 = foo[tedge_targets]``).
        tcell_targets:
            Indices to *remove* from data structure defined on tri-cells (used
            as ``foo2 = np.delete(foo, tcell_targets)``).
        """
        self.tri_mids_o = self.tri_mids * 1
        self.tri_edge_i_o = self.tri_edge_i * 1
        tedge_verts = self.tri_verts[self.tri_edges]
        tcell_targets = []
        for sublist in self._tverts_to_tcell[tvert_targets]:
            tcell_targets.extend(sublist)
        tcell_targets = np.unique(tcell_targets)
        self.tri_verts = np.delete(self.tri_verts, tvert_targets, axis=0)
        self.tcell_verts = np.delete(self.tcell_verts, tcell_targets, axis=0)
        self.tri_ccents = np.delete(self.tri_ccents, tcell_targets, axis=0)
        self.tri_rcircs = np.delete(self.tri_rcircs, tcell_targets, axis=0)
        self.tri_cents = np.delete(self.tri_cents, tcell_targets, axis=0)
        self.tri_sa = np.delete(self.tri_sa, tcell_targets, axis=0)
        tri_vtree = cKDTree(self.tri_verts)
        self.tri_cells = []
        for tvrts in self.tcell_verts:
            self.tri_cells.append(tri_vtree.query(tvrts)[1])
        self.tri_cells = np.asarray(self.tri_cells, dtype=object)
        self.n_tverts = len(self.tri_verts)
        self.tri_vert_i = np.linspace(0, self.n_tverts - 1, self.n_tverts, dtype=int)
        self.n_tcell = len(self.tri_cells)
        self.tri_cell_i = np.asarray([i for i in range(self.n_tcell)])
        tedge_targs = []
        for sublist in self.tverts_to_tedges[tvert_targets]:
            tedge_targs.extend(sublist)
        tedge_targs = np.unique(tedge_targs)
        tedge_verts = np.delete(tedge_verts, tedge_targs, axis=0)
        tri_edges = []
        for everts in tedge_verts:
            edge_inds = tri_vtree.query(everts)[1]
            if len(edge_inds) == 2:
                tri_edges.append(edge_inds)
        self.tri_edges = np.asarray(tri_edges)
        self.n_tedges = len(self.tri_edges)
        self.tri_edge_i = np.linspace(0, self.n_tedges - 1, self.n_tedges, dtype=int)
        self.tri_mids = np.delete(self.tri_mids, tedge_targs, axis=0)
        self.tri_edge_len = np.delete(self.tri_edge_len, tedge_targs, axis=0)
        self.tri_tang = np.delete(self.tri_tang, tedge_targs, axis=0)
        self.vor_sa = np.delete(self.vor_sa, tvert_targets, axis=0)
        self.vor_edge_len = np.delete(self.vor_edge_len, tedge_targs, axis=0)
        self.create_tri_map()
        self.create_mappings(ignoreb=True)
        self.create_core_operators()
        logs.log_info("Mesh successfully cut!")
        return (tedge_targs, tcell_targets)

    def create_tri_map(self):
        """
        Create the basic mapping between triverts and simplices.
        """
        tverts_to_tcell = [[] for i in range(len(self.tri_verts))]
        self.free_to_merge = set()
        for ci, vertsi_o in enumerate(self.tri_cells):
            self.free_to_merge.add(ci)
            for vi in vertsi_o:
                tverts_to_tcell[vi].append(ci)
        self._tverts_to_tcell = array(tverts_to_tcell, dtype=object)

    def create_mappings(self, ignoreb=False):
        """
        Make various mappings for the tri-mesh.
        """
        face_to_edges = [[] for ii in range(self.n_tcell)]
        verts_to_edges = [[] for i in range(len(self.tri_verts))]
        edge_tree = cKDTree(self.tri_edges)
        for ci, vertsi_o in enumerate(self.tri_cells):
            vertsi_i = np.roll(vertsi_o, -1)
            for vi, vj in zip(vertsi_o, vertsi_i):
                dist_e, ea = edge_tree.query([vi, vj])
                if dist_e == 0.0:
                    face_to_edges[ci].append(ea)
                    verts_to_edges[vi].append(ea)
                    verts_to_edges[vj].append(ea)
        self.tcell_to_tedges = np.asarray(face_to_edges, dtype=object)
        self.tverts_to_tedges = np.asarray(verts_to_edges, dtype=object)
        tedges_to_tcell = [[] for xi in self.tri_edges]
        for tcell_i, edge_inds in enumerate(self.tcell_to_tedges):
            for ei in edge_inds:
                tedges_to_tcell[ei].append(tcell_i)
        self.tedges_to_tcell = np.asarray(tedges_to_tcell, dtype=object)
        if ignoreb is False:
            bcellso = self.tedges_to_tcell[self.bflags_tedges]
            self.bflags_tcells = np.asarray([b[0] for b in bcellso])

    def create_core_operators(self):
        """

        Creates the exterior derivative operators 'delta_0' and 'delta_1'.
        Note that the transpose of these matrices are equal to the
        boundary operators, where bount_1 = (delta_0).T and bound_2 = (delta_1).T.

        """
        logs.log_info("Creating core operators...")
        delta_tri_0 = np.zeros((self.n_tedges, self.n_tverts))
        for ei, (vi, vj) in enumerate(self.tri_edges):
            delta_tri_0[ei, vj] = 1.0
            delta_tri_0[ei, vi] = -1.0
        self.delta_tri_0 = np.asarray(delta_tri_0)
        self.delta_tri_0_inv = np.linalg.pinv(self.delta_tri_0)


class CellKernel:
    def cellVerts(self, p):
        """
        Calculate the true vertices of each individual cell from the extracellular matrix (ecm) vertices
        of the closed & clipped Voronoi diagram.

        The BETSE cell grid has each cell defined by unique vertices, which are scaled in from the ecm points.

        Creates
        -------
        self.cell_verts      A nested python list of the [x,y] point pairs defining vertices of each individual cell
                            polygon. The points of each polygon are arranged in a counterclockwise manner.
        self.mem_verts          Flat list of self.cell_verts
        self.cell_vol       Volume of each cell [m3]
        self.cell_sa        Whole cell surface area

        self.mem_edges_flat          membrane edge points [x,y] coordinates
        self.mem_length         membrane surface area values [m2]
        self.mem_mids_flat      unraveled list of membrane edge midpoints [x,y] arranged to self.mem_i
        self.mem_vects_flat     list of normal and tangent vectors (non nested) arranged to self.mem_i

        Notes
        -------
        The Voronoi diagram returns a connected graph. For this simulation, each cell needs unique vertices and edges.
        This method takes the vertices of the original diagram and scales them in to make unique cells.
        """
        self.gj_len = p.cell_space
        self.cell_verts = []
        for centre, poly in zip(self.cell_centres, self.ecm_verts):
            pt_scale = []
            for vert in poly:
                pt_zero = vert - centre
                pt_scale.append(p.scale_cell * pt_zero + centre)
            self.cell_verts.append(np.asarray(pt_scale))
        self.cell_verts = np.asarray(self.cell_verts, dtype=object)
        self.cell_sa = []
        self.cell_area = []
        mem_edges = []
        mem_length = []
        mem_mids = []
        cv_x = []
        cv_y = []
        cv_nx = []
        cv_ny = []
        cv_tx = []
        cv_ty = []
        for polyc in self.cell_verts:
            edge = []
            mps = []
            surfa = []
            for i in range(0, len(polyc)):
                pt1 = polyc[i - 1]
                pt2 = polyc[i]
                pt1 = np.asarray(pt1)
                pt2 = np.asarray(pt2)
                edge.append([pt1, pt2])
                mid = (pt1 + pt2) / 2
                mps.append(mid.tolist())
                lgth = np.sqrt((pt2[0] - pt1[0]) ** 2 + (pt2[1] - pt1[1]) ** 2)
                surfa.append(lgth)
                tang_a = pt2 - pt1
                tang = tang_a / np.linalg.norm(tang_a)
                normal = np.array([tang[1], -tang[0]])
                cv_x.append(mid[0])
                cv_y.append(mid[1])
                cv_nx.append(normal[0])
                cv_ny.append(normal[1])
                cv_tx.append(tang[0])
                cv_ty.append(tang[1])
            mem_edges.append(edge)
            mem_mids.append(mps)
            mem_length.append(surfa)
        self.mem_vects_flat = np.array([cv_x, cv_y, cv_nx, cv_ny, cv_tx, cv_ty]).T
        self.mem_mids = np.asarray(mem_mids, dtype=object)
        self.mem_mids_flat, indmap_mem, _ = tb.flatten(mem_mids)
        self.mem_mids_flat = np.asarray(self.mem_mids_flat)
        self.cell_i = [x for x in range(0, len(self.cell_centres))]
        self.mem_i = [x for x in range(0, len(self.mem_mids_flat))]
        mem_length, _, _ = tb.flatten(mem_length)
        mem_length = np.asarray(mem_length)
        self.mem_sa = mem_length * p.cell_height
        self.mem_edges_flat, _, _ = tb.flatten(mem_edges)
        self.mem_edges_flat = np.asarray(self.mem_edges_flat)
        self.mem_verts, _, _ = tb.flatten(self.cell_verts)
        self.mem_verts = np.asarray(self.mem_verts)
        self.plot_xy = np.vstack((self.mem_mids_flat, self.mem_verts))
        indmap_mem = np.asarray(indmap_mem)
        self.mem_to_cells = indmap_mem[:, 0]
        self.cell_to_mems = []
        for cell_index in self.cell_i:
            mems_index = (self.mem_to_cells == cell_index).nonzero()[0]
            self.cell_to_mems.append(mems_index)
        self.cell_to_mems = np.asarray(self.cell_to_mems, dtype=object)
        self.cell_sa = []
        for grp in self.cell_to_mems:
            cell_sa = sum(self.mem_sa[grp])
            self.cell_sa.append(cell_sa)
        self.cell_sa = np.asarray(self.cell_sa)
        cellVertTree = cKDTree(self.mem_verts)
        self.index_to_mem_verts = []
        for cell_nest in mem_edges:
            for mem_points in cell_nest:
                _, pt_ind1 = cellVertTree.query(mem_points[0])
                _, pt_ind2 = cellVertTree.query(mem_points[1])
                self.index_to_mem_verts.append([pt_ind1, pt_ind2])
        self.index_to_mem_verts = np.asarray(self.index_to_mem_verts)
        self.rads = self.mem_mids_flat - self.cell_centres[self.mem_to_cells]
        self.R_rads = np.sqrt(self.rads[:, 0] ** 2 + self.rads[:, 1] ** 2)
        self.nx_rads = self.rads[:, 0] / self.R_rads
        self.ny_rads = self.rads[:, 1] / self.R_rads

    def cellMatrices(self, p) -> None:
        """
        Create the main matrices used in routine calculations on the Cell Grid.
        """
        logs.log_info("Creating computational matrices for cell-cell transfers...")
        self.M_sum_mems = np.zeros((len(self.cell_i), len(self.mem_i)))
        self.num_mems = []
        for i, inds in enumerate(self.cell_to_mems):
            n = 0
            for j in inds:
                self.M_sum_mems[i, j] = 1
                n = n + 1
            self.num_mems.append(n)
        self.M_sum_mems_inv = np.linalg.pinv(self.M_sum_mems)
        self.num_mems = np.asarray(self.num_mems)
        self.mem_distance = p.cell_space + 2 * p.tm
        self.cell_number = self.cell_centres.shape[0]
        self.gradTheta = np.zeros((len(self.mem_i), len(self.mem_i)))
        self.radial_len = np.zeros(len(self.mem_i))
        for cell_i, mem_i in enumerate(self.cell_to_mems):
            mem_io = np.roll(mem_i, 1)
            li = self.mem_mids_flat[mem_i] - self.mem_mids_flat[mem_io]
            lm = np.sqrt(li[:, 0] ** 2 + li[:, 1] ** 2)
            self.radial_len[mem_i] = np.abs(lm)
            self.gradTheta[mem_i, mem_i] = 1 / lm
            self.gradTheta[mem_i, mem_io] = -1 / lm

    def intra_updater(self, p):
        """
        Calculate a matrix that takes values on membrane midpoints, interpolate
        them to cell vertices, and add them all together as half of a finite
        volume integration for the pie-box regions.

        The other half will come from the centroid region value.
        """
        self.M_int_mems = np.zeros((len(self.mem_i), len(self.mem_i)))
        for i, inds in enumerate(self.cell_to_mems):
            inds = np.asarray(inds)
            inds_p1 = np.roll(inds, 1)
            inds_o = np.roll(inds, 0)
            inds_n1 = np.roll(inds, -1)
            self.M_int_mems[inds_o, inds_o] = 1 / 3
            self.M_int_mems[inds_o, inds_p1] = 1 / 12
            self.M_int_mems[inds_o, inds_n1] = 1 / 12

    def cell_vols(self, p) -> None:
        """
        Divide each cell into a spider-web like volume with an outer "pie-box"
        region volume associated with each membrane, and a region around the
        central point (centroid region).

        This function calculates the volumes of cells, membrane "pie-boxes" and
        centroids, and associated parameters of **cell chords** (i.e., the
        distance between the cell center and each membrane midpoint).
        """
        self.mem_vol = 1 / 2 * self.R_rads * self.mem_sa
        self.cell_vol = np.dot(self.M_sum_mems, self.mem_vol)
        self.R = (3 / 4 * (self.cell_vol / math.pi)) ** (1 / 3)
        self.diviterm = self.cell_vol / self.cell_sa

    def mem_processing(self, p) -> None:
        """
        Calculate the membrane-specific nearest neighbour pairs, interaction
        with the extracellular data points of the Voronoi grid lattice, and
        membranes on the boundary.
        """
        logs.log_info("Creating gap junctions... ")
        sc = 3.0 * (1 - p.scale_cell) * p.cell_radius
        memTree = cKDTree(self.mem_mids_flat)
        mem_nn_o = memTree.query_ball_point(self.mem_mids_flat, sc)
        mem_nn = [[] for x in self.mem_i]
        mem_bound = []
        for i, ind_pair in enumerate(mem_nn_o):
            if len(ind_pair) == 1:
                mem_bound.append(i)
                mem_nn[i].append(i)
                mem_nn[i].append(i)
            elif len(ind_pair) == 2:
                mem_nn[i].append(ind_pair[0])
                mem_nn[i].append(ind_pair[1])
            elif len(ind_pair) > 2:
                i_n = [self.mem_vects_flat[i, 2], self.mem_vects_flat[i, 3]]
                for j in ind_pair:
                    a = [self.mem_vects_flat[j, 2], self.mem_vects_flat[j, 3]]
                    ia = round(np.dot(i_n, a), 1)
                    if ia == -1.0:
                        mem_nn[i] = []
                        mem_nn[i].append(i)
                        mem_nn[i].append(j)
                    else:
                        mem_nn[i] = []
                        mem_nn[i].append(i)
                        mem_nn[i].append(i)
        self.mem_nn = np.asarray(mem_nn)
        self.bflags_mems = np.asarray(mem_bound)
        self.bflags_cells = []
        for mem_i in self.bflags_mems:
            cell_i = self.mem_to_cells[mem_i]
            self.bflags_cells.append(cell_i)
        self.bflags_cells = np.asarray(self.bflags_cells)
        ecm_mids = set()
        for verts in self.ecm_verts:
            for i in range(0, len(verts)):
                pt1 = verts[i - 1]
                pt2 = verts[i]
                pt1 = np.asarray(pt1)
                pt2 = np.asarray(pt2)
                mid = (pt1 + pt2) / 2
                mx = mid[0]
                my = mid[1]
                ecm_mids.add((mx, my))
        ecm_mids = list(ecm_mids)
        self.ecm_mids = np.asarray(ecm_mids)

    def near_neigh(self, p):
        """
        Calculate the nearest neighbours for each cell centre in the cluster and return a numpy
        array of nn indices with an index consistent with all other data lists for the cluster.

        Creates
        -------
        self.cell_nn            Indices of all nearest neighbours to each cell (ordered to self.cell_i)
        self.num_nn             Number of nearest neighbours for each cell (ordered to self.cell_i)
        self.average_nn         Average number of nearest neighbours for entire cluster
        self.nn_i                           Non-unique list of index pairs to cells, each pair defining a cell-cell GJ
        self.gj_len                         Length of each GJ [m]
        self.nn_tx, self.nn_ty              Tangent vector coordinates to each gj

        Notes
        -------
        Uses numpy arrays
        Uses scipy spatial KDTree search algorithm
        """
        self.nn_i = []
        self.cell_nn_i = [[] for x in self.mem_i]
        for i, (mem_i, mem_j) in enumerate(self.mem_nn):
            if mem_i == mem_j:
                self.nn_i.append(i)
                cell_i = self.mem_to_cells[i]
                self.cell_nn_i[mem_i].append(cell_i)
                self.cell_nn_i[mem_i].append(cell_i)
            elif i == mem_i and i != mem_j:
                self.nn_i.append(mem_j)
                cell_i = self.mem_to_cells[mem_i]
                cell_j = self.mem_to_cells[mem_j]
                self.cell_nn_i[i].append(cell_i)
                self.cell_nn_i[i].append(cell_j)
            elif i == mem_j and i != mem_i:
                self.nn_i.append(mem_i)
                cell_i = self.mem_to_cells[mem_j]
                cell_j = self.mem_to_cells[mem_i]
                self.cell_nn_i[i].append(cell_i)
                self.cell_nn_i[i].append(cell_j)
            else:
                logs.log_info(
                    "WARNING: entry not placed in seed nearest neighbour construction. Results may not be accurate."
                )
        self.nn_i = np.asarray(self.nn_i)
        self.cell_nn_i = np.asarray(self.cell_nn_i)
        self.cell_nn = []
        for cell_i, mem_i_set in enumerate(self.cell_to_mems):
            cell_neigh_set = []
            for mem_i in mem_i_set:
                mem_j = self.nn_i[mem_i]
                if mem_j == mem_i:
                    pass
                else:
                    cell_j = self.mem_to_cells[mem_j]
                    if cell_i != cell_j:
                        cell_neigh_set.append(cell_j)
            self.cell_nn.append(cell_neigh_set)
        self.num_nn = []
        for indices in self.cell_nn:
            self.num_nn.append(len(indices))
        self.average_nn = sum(self.num_nn) / len(self.num_nn)
        self.num_nn = np.asarray(self.num_nn)
        self.cell_nn = np.asarray(self.cell_nn, dtype=object)
        nn_bound = self.cell_nn[self.bflags_cells]
        nn_bound, _, _ = tb.flatten(nn_bound)
        self.nn_bound = []
        for ind in nn_bound:
            if ind not in self.bflags_cells:
                self.nn_bound.append(ind)

    def calc_gj_vects(self, p):
        """
        Recalculate nearest neighbour (gap junction) vectors.

        Used in deformation sequence.
        """
        self.nn_mids = []
        self.nn_tx = []
        self.nn_ty = []
        self.nn_len = []
        self.nn_edges = [[] for x in self.mem_i]
        for mem_i, mem_j in enumerate(self.nn_i):
            cell_i, cell_j = self.cell_nn_i[mem_i]
            pt1_mem = self.mem_mids_flat[mem_i]
            pt2_mem = self.mem_mids_flat[mem_j]
            pt1_cell = self.cell_centres[cell_i]
            pt2_cell = self.cell_centres[cell_j]
            tang_o = pt2_mem - pt1_mem
            tang_x_o = tang_o[0]
            tang_y_o = tang_o[1]
            tang_mag = np.sqrt(tang_x_o**2 + tang_y_o**2)
            if tang_mag == 0.0:
                tang_x = 0
                tang_y = 0
            else:
                tang_x = tang_x_o / tang_mag
                tang_y = tang_y_o / tang_mag
            mid = (pt1_mem + pt2_mem) / 2
            self.nn_mids.append(mid)
            len_o = pt2_cell - pt1_cell
            len_xo = len_o[0]
            len_yo = len_o[1]
            len_mag = np.sqrt(len_xo**2 + len_yo**2)
            if len_mag == 0.0:
                self.nn_len.append(-1)
            else:
                self.nn_len.append(len_mag)
            self.nn_tx.append(tang_x)
            self.nn_ty.append(tang_y)
            self.nn_edges[mem_i].append(pt1_cell)
            self.nn_edges[mem_i].append(pt2_cell)
        self.nn_mids = np.asarray(self.nn_mids)
        self.nn_tx = np.asarray(self.nn_tx)
        self.nn_ty = np.asarray(self.nn_ty)
        self.nn_len = np.asarray(self.nn_len)
        self.nn_edges = np.asarray(self.nn_edges)
        self.cell_nn_tx = []
        self.cell_nn_ty = []
        for cell_i, cell_j in self.cell_nn_i:
            pt1 = self.cell_centres[cell_i]
            pt2 = self.cell_centres[cell_j]
            tang_o = pt2 - pt1
            norm_tang = np.sqrt(tang_o[0] ** 2 + tang_o[1] ** 2)
            if norm_tang != 0:
                tang = tang_o / norm_tang
            else:
                norm_tang = 1
                tang = tang_o / norm_tang
                tang[0] = 0
                tang[1] = 0
            self.cell_nn_tx.append(tang[0])
            self.cell_nn_ty.append(tang[1])
        self.cell_nn_tx = np.asarray(self.cell_nn_tx)
        self.cell_nn_ty = np.asarray(self.cell_nn_ty)
        self.cell_to_nn_full = [[] for x in range(len(self.cell_i))]
        for i, (cell_i, cell_j) in enumerate(self.cell_nn_i):
            if cell_i != cell_j:
                self.cell_to_nn_full[cell_i].append(i)
                self.cell_to_nn_full[cell_j].append(i)
        self.cell_to_nn_full = np.asarray(self.cell_to_nn_full, dtype=object)


def cut_through_contacts(self, phase: SimPhase, tissue_picker: TissuePickerABC) -> None:
    """
    Permanently remove all cells selected by the passed tissue picker from
    the cell cluster described by the passed simulation phase.

    Parameters
    ----------
    phase : SimPhase
        Current simulation phase.
    tissue_picker : TissuePickerABC
        Object matching all cells to be removed.
    """
    cells = phase.cells
    p = phase.p
    sim = phase.sim
    target_inds_cell, target_inds_mem = tissue_picker.pick_cells_and_mems(cells=cells, p=p)
    target_inds_gj, _, _ = tb.flatten(cells.cell_to_nn_full[target_inds_cell])
    if p.is_ecm:
        ecm_targs_cell = list(cells.map_cell2ecm[target_inds_cell])
        ecm_targs_mem = list(cells.map_mem2ecm[target_inds_mem])
        ecm_targs = []
        for v in ecm_targs_cell:
            ecm_targs.append(v)
        for v in ecm_targs_mem:
            ecm_targs.append(v)
    hurt_cells = np.zeros(len(cells.cell_i))
    target_inds_gj_unique = np.unique(target_inds_gj)
    for i, inds in enumerate(cells.cell_to_nn_full):
        inds_array = np.asarray(inds)
        inds_in_target = np.intersect1d(inds_array, target_inds_gj_unique)
        if len(inds_in_target):
            hurt_cells[i] = 1
    hurt_inds = (hurt_cells == 1).nonzero()
    sim.hurt_mask = np.zeros(sim.cdl)
    sim.hurt_mask[hurt_inds] = 1.0
    sim_names = list(sim.__dict__.keys())
    specials_list = [
        "cc_cells",
        "cc_mems",
        "cc_env",
        "cc_er",
        "z_array",
        "z_array_er",
        "fluxes_gj",
        "fluxes_mem",
        "Dm_base",
        "Dm_cells",
        "Dm_scheduled",
        "Dm_vg",
        "Dm_cag",
        "Dm_morpho",
        "Dm_er_base",
        "Dm_er_CICR",
        "Dm_stretch",
        "Dm_custom",
        "D_gj",
        "fluxes_intra",
        "cc_at_mem",
    ]
    if p.is_ecm:
        specials_list.remove("cc_env")
        extra = ["z_array_cells"]
        for ent in extra:
            specials_list.append(ent)
    special_names = set(specials_list)
    for name in sim_names:
        if name in special_names:
            super_data = getattr(sim, name)
            super_data2 = []
            for i, data in enumerate(super_data):
                if isinstance(data, np.ndarray):
                    if len(data) == len(cells.cell_i):
                        data2 = np.delete(data, target_inds_cell)
                    elif len(data) == len(cells.mem_i):
                        data2 = np.delete(data, target_inds_mem)
                elif isinstance(data, list):
                    data2 = []
                    if len(data) == len(cells.cell_i):
                        for index in sorted(target_inds_cell, reverse=True):
                            del data[index]
                        data2.append(data[index])
                    elif len(data) == len(cells.mem_i):
                        for index in sorted(target_inds_mem, reverse=True):
                            del data[index]
                        data2.append(data[index])
                super_data2.append(data2)
            if type(super_data) == np.ndarray:
                super_data2 = np.asarray(super_data2)
            setattr(sim, name, super_data2)
        else:
            data = getattr(sim, name)
            if isinstance(data, np.ndarray):
                if len(data) == len(cells.cell_i):
                    data2 = np.delete(data, target_inds_cell)
                    setattr(sim, name, data2)
                elif len(data) == len(cells.mem_i):
                    data2 = np.delete(data, target_inds_mem)
                    setattr(sim, name, data2)
            elif isinstance(data, list):
                index = None
                data2 = []
                if len(data) == len(cells.cell_i):
                    for index in sorted(target_inds_cell, reverse=True):
                        del data[index]
                    data2.append(data[index])
                    setattr(sim, name, data2)
                elif len(data) == len(cells.mem_i):
                    for index in sorted(target_inds_mem, reverse=True):
                        del data[index]
                    data2.append(data[index])
                    setattr(sim, name, data2)
    if p.Ca_dyn and sim.endo_retic is not None:
        sim.endo_retic.remove_ers(sim, target_inds_cell)
    new_cell_centres = []
    new_ecm_verts = []
    removal_flags = np.zeros(len(cells.cell_i))
    removal_flags[target_inds_cell] = 1
    for i, flag in enumerate(removal_flags):
        if flag == 0:
            new_cell_centres.append(cells.cell_centres[i])
            new_ecm_verts.append(cells.ecm_verts[i])
    cells.cell_centres = np.asarray(new_cell_centres)
    cells.ecm_verts = np.asarray(new_ecm_verts, dtype=object)
    ecm_verts_flat, _, _ = tb.flatten(cells.ecm_verts)
    ecm_verts_set = set()
    for vert in ecm_verts_flat:
        ptx = vert[0]
        pty = vert[1]
        ecm_verts_set.add((ptx, pty))
    cells.ecm_verts_unique = [list(verts) for verts in list(ecm_verts_set)]
    cells.ecm_verts_unique = np.asarray(cells.ecm_verts_unique)
    logs.log_info("Recalculating cluster variables for new configuration...")
    self.targets_dec_edges, self.targets_dec_tcells = cells.mesh.cut_mesh(target_inds_cell)
    self.targets_dec_tverts = target_inds_cell
    cells.cellVerts(p)
    cells.cellMatrices(p)
    cells.intra_updater(p)
    cells.cell_vols(p)
    cells.mem_processing(p)
    cells.near_neigh(p)
    cells.calc_gj_vects(p)
    return locals()
