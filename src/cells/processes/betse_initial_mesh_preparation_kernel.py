# Copyright 2014-2025 by Alexis Pietak & Cecil Curry.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""Static source transcription of the bounded BETSE constructor/pre_mesh closure.

Owned RNG, row deletion, nearest/Delaunay evidence and logs are injected by the
public preparation driver. No native package is imported. See the source map.
"""
# Keep original unused source stores for exact trace comparison.
# ruff: noqa: F841, B007

import math
from types import SimpleNamespace

import numpy as np
from numpy import array

PI = math.pi
TWO_PI = 2 * PI


def die_unless_polygon(polygon):
    points = np.asarray(polygon)
    if points.ndim != 2 or points.shape[1] != 2 or len(points) < 3 or not np.isfinite(points).all():
        raise ValueError("Require the closed finite polygon helper boundary")


def _scalar_to_python(scalar):
    return scalar.item()


nparray = SimpleNamespace(from_iterable=np.asarray)
npscalar = SimpleNamespace(to_python=_scalar_to_python)


def is_convex(polygon):
    """
    ``True`` only if the passed polygon is **strictly convex** (i.e., is
    non-self-intersecting such that all interior angles are strictly
    between zero and a straight angle).

    Parameters
    ----------
    polygon : SequenceTypes
        Two-dimensional sequence of all points defining the polygon to be
        tested such that:

        * The first dimension indexes each such point (in arbitrary order).
        * The second dimension indexes each coordinate of this point such that:

          * The first item is the X coordinate of this point.
          * The second item is the Y coordinate of this point.

    Returns
    ----------
    bool
        ``True`` only if this polygon is strictly convex.

    Raises
    ----------
    BetseMathPointException
        If this sequence is *not* a two-dimensional polygon.

    See Also
    ----------
    https://stackoverflow.com/a/45372025/2809027
        StackOverflow answer strongly inspiring this implementation. The credit
        entirely goes to Rory Daulton for mastering this non-trivial problem.
    """
    pass
    die_unless_polygon(polygon)
    try:
        old_x, old_y = polygon[-2]
        new_x, new_y = polygon[-1]
        new_direction = math.atan2(new_y - old_y, new_x - old_x)
        angle_sum = 0.0
        for ndx, newpoint in enumerate(polygon):
            old_x, old_y, old_direction = (new_x, new_y, new_direction)
            new_x, new_y = newpoint
            new_direction = math.atan2(new_y - old_y, new_x - old_x)
            if old_x == new_x and old_y == new_y:
                return False
            angle = new_direction - old_direction
            if angle <= -PI:
                angle += TWO_PI
            elif angle > PI:
                angle -= TWO_PI
            if ndx == 0:
                if angle == 0.0:
                    return False
                orientation = 1.0 if angle > 0.0 else -1.0
            elif orientation * angle <= 0.0:
                return False
            angle_sum += angle
        return abs(round(angle_sum / TWO_PI)) == 1
    except (ArithmeticError, TypeError, ValueError):
        return False


def is_cyclic_quad(A, B, C, D):
    """
    ``True`` only if the quadrilateral represented by the passed four vertices
    is **cyclic** (i.e., counterclockwise-oriented).

    Parameters
    ----------
    A, B, C, D : SequenceTypes
        Four vertices of the quadrilateral to be tested, assumed to be oriented
        counterclockwise.

    Returns
    ----------
    bool
        ``True`` only if this quadrilateral is cyclic.
    """
    pass
    A = nparray.from_iterable(A)
    B = nparray.from_iterable(B)
    C = nparray.from_iterable(C)
    D = nparray.from_iterable(D)
    a = np.linalg.norm(B - A)
    b = np.linalg.norm(C - B)
    c = np.linalg.norm(D - C)
    d = np.linalg.norm(A - D)
    e = np.sqrt((a * c + b * d) * (a * d + b * c) / (a * b + c * d))
    f = np.sqrt((a * c + b * d) * (a * b + c * d) / (a * d + b * c))
    lhs = np.round(e * f, 15)
    rhs = np.round(a * c + b * d, 15)
    test_bool = lhs == rhs
    return npscalar.to_python(test_bool)


def det1d(arr1, arr2):
    """
    Scalar determinant of two one-dimensional input **2-arrays** (i.e., arrays
    containing exactly two numbers each).

    This function literally computes the following one-liner:

    .. code-block:: pycon

       >>> import numpy as np
       >>> arr1 = np.asarray([1, 2])
       >>> arr2 = np.asarray([4, 5])
       >>> det1d = arr1[0] * arr2[1] - arr1[1] * arr2[0]
       >>> det1d
       -3

    Caveats
    -------
    This function is often (but *not* always) called in lieu of the official
    :func:`numpy.linalg.det` function, which requires that both of the passed
    2-arrays be congealed into a single two-dimensional input array. Weird!

    Parameters
    ----------
    arr1: NDArrayNdim2
        First 1-dimensional input 2-array to take the determinant of.
    arr2: NDArrayNdim2
        Second 1-dimensional input 2-array to take the determinant of.

    Returns
    -------
    Number
        Scalar determinant of these one-dimensional input 2-arrays.
    """
    return arr1[0] * arr2[1] - arr1[1] * arr2[0]


class Kernel:
    def __init__(
        self,
        cell_radius=None,
        mesh_type="tri",
        seed_points=None,
        use_centroids=True,
        use_alpha_shape=True,
        alpha_shape=0.4,
        single_cell_sides=6,
        single_cell_noise=0.5,
        image_mask=None,
        make_all_operators=True,
        allow_merging=True,
        merge_thresh=0.2,
        close_thresh=0.25,
        center=None,
    ):
        self.single_cell_noise = single_cell_noise
        self.single_cell_sides = single_cell_sides
        self.alpha_shape = alpha_shape
        self.use_alpha_shape = use_alpha_shape
        self.image_mask = image_mask
        self.make_all_operators = make_all_operators
        self.mesh_type = mesh_type
        self.merge_thresh = merge_thresh
        self.allow_merging = allow_merging
        self.use_centroids = use_centroids
        self.close_thresh = close_thresh
        self.single_cell = False
        if center is not None:
            self.centx = center[0]
            self.centy = center[1]
        else:
            self.centx = 0.0
            self.centy = 0.0
        self.removed_bad_verts = False
        if cell_radius is None and seed_points is not None:
            point_tree = self._cells_tree(seed_points)
            nd, _ = point_tree.query(seed_points, k=2)
            self.cell_radius = np.mean(nd[:, 1]) / 2
        elif cell_radius is None and seed_points is None:
            self.cell_radius = 5e-06
        else:
            self.cell_radius = cell_radius
        if seed_points is None:
            self.make_single_cell_points()
            self.single_cell = True
        else:
            self.tri_verts = seed_points

    def pre_mesh(self):
        """
        Create only the tri and vor meshes without creating operators.

        """
        self.create_tri_mesh()
        self.create_mappings()
        self.define_vorverts()
        self.process_voredges()

    def make_single_cell_points(self):
        """
        Creates seed points (tri_mesh verts) for a single closed voronoi cell and
        its boundary.

        """
        self._cells_log("log_info", "Creating single cell points")
        angles = [2 * n * np.pi / self.single_cell_sides for n in range(self.single_cell_sides)]
        xenv = 2 * self.cell_radius * np.cos(angles)
        yenv = 2 * self.cell_radius * np.sin(angles)
        noisex = self._cells_rng.random(self.single_cell_sides + 1)
        noisey = self._cells_rng.random(self.single_cell_sides + 1)
        xenv = (
            np.hstack((xenv, 0.0)) + noisex * self.cell_radius * self.single_cell_noise + self.centx
        )
        yenv = (
            np.hstack((yenv, 0.0)) + noisey * self.cell_radius * self.single_cell_noise + self.centy
        )
        self.tri_verts = np.column_stack((xenv, yenv))

    def create_tri_mesh(self):
        """
        Calculate the Delaunay triangulation and non-convex hull using alpha
        shapes.
        """
        self._cells_log("log_info", "Creating triangular mesh...")
        self.trimesh_core_calcs()
        if self.single_cell is False:
            self.sanity_check()
        tri_tree = self._cells_tree(self.tri_ccents)
        di, ni = tri_tree.query(self.tri_ccents, k=2)
        mark_for_merge = []
        for si, ccenti in enumerate(self.tri_ccents):
            disti = di[si, 1]
            indi = ni[si, 1]
            if self.mesh_type == "quad":
                mark_for_merge.append([indi])
            elif disti < self.cell_radius * self.merge_thresh:
                mark_for_merge.append([indi])
            else:
                mark_for_merge.append([])
        if self.allow_merging or self.mesh_type == "quad":
            self.merge_tri_mesh(mark_for_merge)
            self.create_tri_map()
        self.process_primary_edges()

    def trimesh_core_calcs(self):
        """
        Figure out if there are super close points in the tri_verts set.

        Next check for triverts with really close circumcenters and, if
        necessary, merge to quads, or if requested, try merging as much of
        the mesh to quads as possible. Find ccents that are close to one
        another and mark cells for quad-merge.
        """
        tri_tree = self._cells_tree(self.tri_verts)
        di, ni = tri_tree.query(self.tri_verts, k=2)
        mark_for_merge = set()
        not_merged = set()
        for vi, tvertpts in enumerate(self.tri_verts):
            disti = di[vi, 1]
            indi = ni[vi, 1]
            near_point_check = disti / self.cell_radius
            if near_point_check < self.close_thresh:
                if vi not in not_merged:
                    mark_for_merge.add(vi)
                not_merged.add(indi)
        mark_for_merge = np.asarray(list(mark_for_merge), dtype=int)
        self.tri_verts = self._cells_delete_seed_rows(
            mark_for_merge, axis=0, cause="trimesh_core_calcs"
        )
        trimesh = self._cells_delaunay(self.tri_verts)
        self.n_tverts = len(self.tri_verts)
        self.tri_vert_i = np.linspace(0, self.n_tverts - 1, self.n_tverts, dtype=int)
        tri_ccents = []
        tri_cents = []
        tri_rcircs = []
        tri_sa = []
        tcell_verts = []
        tri_cells = []
        for si, vert_inds in enumerate(trimesh.simplices):
            abc = trimesh.points[vert_inds]
            vx, vy, r_circ, r_in = self.circumc(abc[0], abc[1], abc[2])
            cx, cy = self.poly_centroid(abc)
            sa = self.area(abc)
            if self.use_alpha_shape:
                if r_circ < self.cell_radius / self.alpha_shape:
                    if self.image_mask is not None:
                        flagc = self.image_mask.clipping_function(vx, vy)
                    else:
                        flagc = 1.0
                    if flagc != 0.0:
                        tri_ccents.append([vx, vy])
                        tri_cents.append([cx, cy])
                        tri_rcircs.append(r_circ)
                        tri_cells.append(vert_inds)
                        tri_sa.append(sa)
                        tcell_verts.append(abc)
            else:
                tri_ccents.append([vx, vy])
                tri_cents.append([cx, cy])
                tri_rcircs.append(r_circ)
                tri_sa.append(sa)
                tri_cells.append(vert_inds)
                tcell_verts.append(abc)
        self.tri_cells = np.asarray(tri_cells)
        self.n_tcell = len(tri_cells)
        self.tri_cell_i = np.asarray([i for i in range(self.n_tcell)])
        self.tri_ccents = np.asarray(tri_ccents)
        self.tri_cents = np.asarray(tri_cents)
        self.tri_rcircs = np.asarray(tri_rcircs)
        self.tri_sa = np.asarray(tri_sa)
        self.tcell_verts = np.asarray(tcell_verts)
        self.create_tri_map()

    def merge_tri_mesh(self, merge_list):
        """
        Merge cells of the tri_mesh into a (potentially) mixed quad-tri mesh.

        Parameters
        -----------
        merge_list : List[List[int]]
        """
        self._cells_log("log_info", "Merging close circumcenters...")
        quad_cells = []
        quad_ccents = []
        quad_sa = []
        quad_rcircs = []
        quadcell_i = []
        qcell_verts = []
        quad_cents = []
        for ai, blist in enumerate(merge_list):
            vertsa = self.tri_cells[ai]
            cc1 = self.tri_ccents[ai]
            c1 = self.tri_cents[ai]
            a1 = self.tri_sa[ai]
            rc1 = self.tri_rcircs[ai]
            if len(blist) != 0:
                bi = blist[0]
                vertsb = self.tri_cells[bi]
                cc2 = self.tri_ccents[bi]
                c2 = self.tri_cents[bi]
                a2 = self.tri_sa[bi]
                rc2 = self.tri_rcircs[bi]
                if ai in self.free_to_merge:
                    if bi in self.free_to_merge:
                        quad_i = np.unique((vertsa, vertsb))
                        shared_ij = np.intersect1d(vertsa, vertsb)
                        if len(quad_i) == 4 and len(shared_ij) == 2:
                            quad_pts = self.tri_verts[quad_i]
                            cent = quad_pts.mean(axis=0)
                            angles = np.arctan2(quad_pts[:, 1] - cent[1], quad_pts[:, 0] - cent[0])
                            sorted_region = quad_i[np.argsort(angles)]
                            sorted_pts = quad_pts[np.argsort(angles)]
                            conv_quad = is_convex(sorted_pts)
                            cycl_quad = is_cyclic_quad(
                                sorted_pts[0], sorted_pts[1], sorted_pts[2], sorted_pts[3]
                            )
                            if conv_quad and cycl_quad:
                                Rq, areaq, ccxq, ccyq = self.quad_circumc(
                                    sorted_pts[0], sorted_pts[1], sorted_pts[2], sorted_pts[3]
                                )
                                quad_cells.append(sorted_region)
                                qcell_verts.append(sorted_pts)
                                quad_ccents.append([ccxq, ccyq])
                                quad_rcircs.append(Rq)
                                quad_sa.append(areaq)
                                quadcell_i.append(ai)
                                cx, cy = self.poly_centroid(sorted_pts)
                                quad_cents.append([cx, cy])
                            else:
                                ptsa = self.tri_verts[vertsa]
                                ptsb = self.tri_verts[vertsb]
                                quad_cells.append(vertsa)
                                qcell_verts.append(ptsa)
                                quad_ccents.append(cc1)
                                quad_rcircs.append(rc1)
                                quad_sa.append(a1)
                                quadcell_i.append(ai)
                                quad_cents.append(c1)
                                quad_cells.append(vertsb)
                                qcell_verts.append(ptsb)
                                quad_ccents.append(cc2)
                                quad_rcircs.append(rc2)
                                quad_sa.append(a2)
                                quadcell_i.append(bi)
                                quad_cents.append(c2)
                            self.free_to_merge.remove(ai)
                            self.free_to_merge.remove(bi)
                    else:
                        ptsa = self.tri_verts[vertsa]
                        quad_cells.append(vertsa)
                        qcell_verts.append(ptsa)
                        quad_ccents.append(cc1)
                        quad_rcircs.append(rc1)
                        quad_sa.append(a1)
                        quadcell_i.append(ai)
                        quad_cents.append(c1)
                        self.free_to_merge.remove(ai)
            else:
                ptsa = self.tri_verts[vertsa]
                quad_cells.append(vertsa)
                qcell_verts.append(ptsa)
                quad_ccents.append(cc1)
                quad_rcircs.append(rc1)
                quad_sa.append(a1)
                quadcell_i.append(ai)
                quad_cents.append(c1)
                self.free_to_merge.remove(ai)
        quad_cents = np.asarray(quad_cents)
        self.tri_cells = np.asarray(quad_cells, dtype=object)
        self.tri_ccents = np.asarray(quad_ccents)
        self.tri_rcircs = np.asarray(quad_rcircs)
        self.tri_cents = quad_cents
        self.tcell_verts = np.asarray(qcell_verts, dtype=object)
        self.tri_sa = np.asarray(quad_sa)
        self.n_tcell = len(self.tri_cells)
        self.tri_cell_i = np.asarray([i for i in range(self.n_tcell)])

    def process_primary_edges(self):
        """
        Process the edges and boundary of the primary mesh.
        """
        self._cells_log("log_info", "Defining edges of tri mesh...")
        all_edges = set()
        unique_edges = set()
        hull_points = []
        hull_edges = []
        tri_mids = []
        tri_edge_len = []
        tri_tang = []
        for verti_o in self.tri_cells:
            verti_i = np.roll(verti_o, -1)
            for vi, vj in zip(verti_o, verti_i, strict=False):
                all_edges.add((vi, vj))
        for va, vb in all_edges:
            if (va, vb) in all_edges and (vb, va) not in all_edges:
                hull_points.append(va)
                hull_points.append(vb)
                hull_edges.append([va, vb])
            if (vb, va) not in unique_edges:
                unique_edges.add((va, vb))
        self.bflags_tverts = np.unique(hull_points)
        self.tri_edges = np.asarray(list(unique_edges))
        self.n_tedges = len(self.tri_edges)
        tri_edges = self.tri_edges.tolist()
        bflags_tedges = []
        for vi, vj in hull_edges:
            if [vi, vj] in tri_edges:
                kk = tri_edges.index([vi, vj])
            elif [vj, vi] in tri_edges:
                kk = tri_edges.index([vj, vi])
            bflags_tedges.append(kk)
        self.bflags_tedges = np.asarray(bflags_tedges)
        self.tri_edge_i = np.linspace(0, self.n_tedges - 1, self.n_tedges, dtype=int)
        self.inner_tedge_i = np.delete(self.tri_edge_i, self.bflags_tedges)
        for ei, (vi, vj) in enumerate(self.tri_edges):
            tpi = self.tri_verts[vi]
            tpj = self.tri_verts[vj]
            tan_t = tpj - tpi
            tri_len = np.linalg.norm(tan_t)
            tan_ti = tan_t / tri_len
            assert np.round(tri_len, 15) != 0.0, (
                "Tri-edge length equal to zero! Duplicate seed points exist!"
            )
            pptm = (tpi + tpj) / 2
            tri_mids.append(pptm)
            tri_edge_len.append(tri_len)
            tri_tang.append(tan_ti)
        self.tri_mids = np.asarray(tri_mids)
        self.tri_edge_len = np.asarray(tri_edge_len)
        self.tri_tang = np.asarray(tri_tang)
        self.inner_tvert_i = np.delete(self.tri_vert_i, self.bflags_tverts)
        self.centroid = np.mean(self.tri_verts, axis=0)

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
        edge_tree = self._cells_tree(self.tri_edges)
        for ci, vertsi_o in enumerate(self.tri_cells):
            vertsi_i = np.roll(vertsi_o, -1)
            for vi, vj in zip(vertsi_o, vertsi_i, strict=False):
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

    def define_vorverts(self):
        """
        Add perpendicular bisectors into the vor mesh.

        When constructing a voronoi diagram, the vor mesh edges intersecting
        the incredible hull of the tri mesh must be defined by a new set of vor
        mesh vertices added outside the tri mesh hull. This method adds these
        perpendicular bisectors into the vor mesh.
        """
        self._cells_log("log_info", "Calculating Voronoi cells...")
        vcell_verts = []
        vor_verts = []
        vor_sa = []
        vor_cents = []
        vor_edge_verts = []
        tri_sa_o = []
        for ti, tc_indso in enumerate(self._tverts_to_tcell):
            tc_inds = np.unique(tc_indso)
            assert len(tc_indso) != 0, "Tri-vert belongs to no simplices!"
            if self.use_centroids:
                vvertso = self.tri_cents[tc_inds]
            else:
                vvertso = self.tri_ccents[tc_inds]
            trisai = self.tri_sa[tc_inds]
            if ti in self.bflags_tverts:
                tedge_inds = np.unique(self.tverts_to_tedges[ti])
                for tei in tedge_inds:
                    if tei in self.bflags_tedges:
                        bedge_verts = self.tri_verts[self.tri_edges[tei]]
                        bedge_mid = np.mean(bedge_verts, axis=0)
                        simp_i = self.tedges_to_tcell[tei]
                        if self.use_centroids:
                            pt_o = self.tri_cents[simp_i[0]]
                        else:
                            pt_o = self.tri_ccents[simp_i[0]]
                        dist_diff = bedge_mid - pt_o
                        intpt = bedge_mid + dist_diff
                        bsa = self.tri_sa[simp_i[0]]
                        vvertso = np.vstack((vvertso, intpt))
                        trisai = np.hstack((trisai, bsa))
            inds_vsort = self.cc_sort_inds(vvertso)
            vverts = vvertso[inds_vsort]
            trisaj = trisai[inds_vsort]
            vor_verts.extend(vverts)
            tri_sa_o.extend(trisaj)
            vcell_verts.append(vverts)
            vor_sa.append(self.area(vverts))
            vor_cents.append(self.poly_centroid(vverts))
            vedge_verts = np.asarray(
                [[vi, vj] for vi, vj in zip(vverts, np.roll(vverts, -1, axis=0), strict=False)]
            )
            vor_edge_verts.extend(vedge_verts)
        self.vcell_verts = np.asarray(vcell_verts, dtype=object)
        self.vor_verts_duplicates = vor_verts * 1
        self.vor_verts = np.unique(np.asarray(vor_verts), axis=0)
        self.vor_sa = np.asarray(vor_sa)
        self.vor_cents = np.asarray(vor_cents)
        self.vor_edge_verts = np.unique(np.asarray(vor_edge_verts), axis=0)
        tri_sa_o = np.asarray(tri_sa_o)
        vord_tree = self._cells_tree(self.vor_verts_duplicates)
        _, vi = vord_tree.query(self.vor_verts)
        self.tri_sa_o = tri_sa_o[vi]

    def process_voredges(self):
        self._cells_log("log_info", "Calculating Voronoi edges...")
        all_edges = set()
        vedge_set = set()
        hull_points = []
        hull_edges = []
        vor_mids = []
        vor_tang = []
        vor_edge_len = []
        vor_cells = []
        vor_tree = self._cells_tree(self.vor_verts)
        if self.use_centroids:
            _, self.inner_vvert_i = vor_tree.query(self.tri_cents)
        else:
            _, self.inner_vvert_i = vor_tree.query(self.tri_ccents)
        for vpts in self.vcell_verts:
            di, vi = vor_tree.query(vpts)
            vor_cells.append(vi)
        for vedge in self.vor_edge_verts:
            di, vi = vor_tree.query(vedge)
            all_edges.add((vi[0], vi[1]))
        for va, vb in all_edges:
            if (va, vb) in all_edges and (vb, va) not in all_edges:
                hull_points.append(va)
                hull_points.append(vb)
                hull_edges.append([va, vb])
            if (vb, va) not in vedge_set:
                vedge_set.add((va, vb))
        self.bflags_vverts = np.unique(hull_points)
        vor_edges = np.asarray(list(vedge_set))
        vedge_tree = self._cells_tree(vor_edges)
        bflags_vedges = []
        for vi, vj in hull_edges:
            dedgea, ea = vedge_tree.query([vi, vj])
            dedgeb, eb = vedge_tree.query([vj, vi])
            if dedgea == 0.0:
                kk = ea
            elif dedgeb == 0.0:
                kk = eb
            bflags_vedges.append(kk)
        self.bflags_vedges = np.asarray(bflags_vedges)
        for ei, (vi, vj) in enumerate(vor_edges):
            vpi = self.vor_verts[vi]
            vpj = self.vor_verts[vj]
            tan_v = vpj - vpi
            vor_len = np.linalg.norm(tan_v)
            tan_vi = tan_v / vor_len
            assert np.round(vor_len, 15) != 0.0, (
                "Tri-edge length equal to zero! Duplicate seed points exist!"
            )
            ppvm = (vpi + vpj) / 2
            vor_mids.append(ppvm)
            vor_edge_len.append(vor_len)
            vor_tang.append(tan_vi)
        vor_mids = np.asarray(vor_mids)
        vor_edge_len = np.asarray(vor_edge_len)
        vor_tang = np.asarray(vor_tang)
        self.vor_cells = np.asarray(vor_cells, dtype=object)
        vor_tree = self._cells_tree(vor_mids)
        di, map_vedge_to_tedge = vor_tree.query(self.tri_mids)
        vor_edges = np.asarray(vor_edges)
        self.vor_edges = vor_edges[map_vedge_to_tedge]
        self.vor_mids = vor_mids[map_vedge_to_tedge]
        self.vor_edge_len = vor_edge_len[map_vedge_to_tedge]
        self.vor_tang = vor_tang[map_vedge_to_tedge]
        for ei, (vti, tti) in enumerate(zip(self.vor_tang, self.tri_tang, strict=False)):
            sign = np.sign(det1d(tti, vti))
            if sign == 1.0:
                self.vor_tang[ei] = -vti
                va, vb = self.vor_edges[ei]
                self.vor_edges[ei] = [vb, va]
        self.n_vedges = len(self.vor_edges)
        self.vor_edge_i = np.linspace(0, self.n_vedges - 1, self.n_vedges, dtype=int)
        self.n_vverts = len(self.vor_verts)
        self.n_vcells = len(self.vor_cells)
        self.vor_vert_i = np.linspace(0, self.n_vverts - 1, self.n_vverts, dtype=int)
        self.vor_cell_i = np.linspace(0, self.n_vcells - 1, self.n_vcells, dtype=int)
        xmin = self.vor_verts[:, 0].min()
        xmax = self.vor_verts[:, 0].max()
        ymin = self.vor_verts[:, 1].min()
        ymax = self.vor_verts[:, 1].max()
        self.xyaxis = [xmin * 1.1, xmax * 1.1, ymin * 1.1, ymax * 1.1]

    def sanity_check(self):
        self._cells_log("log_info", "Check for unused vertices...")
        unused_tverts = []
        for tvi, sverts in enumerate(self._tverts_to_tcell):
            if len(sverts) == 0:
                unused_tverts.append(tvi)
        unused_tverts = np.asarray(unused_tverts)
        if len(unused_tverts) and self.removed_bad_verts is False:
            self._cells_log(
                "log_info",
                "Some seed verts are not used in any mesh simplexes! \n"
                "Decrease alpha_shape value to avoid this case. \n"
                "Removing unused seed points from mesh...",
            )
            self.tri_verts = self._cells_delete_seed_rows(
                unused_tverts, axis=0, cause="sanity_check"
            )
            self.n_tverts = len(self.tri_verts)
            self.tri_vert_i = np.linspace(0, self.n_tverts - 1, self.n_tverts, dtype=int)
            self.trimesh_core_calcs()
            self.removed_bad_verts = True
        elif len(unused_tverts) and self.removed_bad_verts is True:
            self._cells_log("log_warning", "Something is seriously wrong with your mesh!")

    def area(self, p):
        """
        Calculates the unsigned area of an arbitrarily shaped polygon defined by a set of
        counter-clockwise oriented points in 2D.

        Parameters
        ----------
        p               xy list of polygon points

        Returns
        -------
        area            area of a polygon in square meters

        Notes
        -------
        The algorithm is an application of Green's theorem for the functions -y and
        x, exactly in the way a planimeter works.
        """
        foo = np.asarray(p)
        foo_p = np.roll(foo, -1, axis=0)
        ai = foo[:, 0] * foo_p[:, 1] - foo_p[:, 0] * foo[:, 1]
        aa = 1 / 2 * np.sum(ai)
        return aa

    def poly_centroid(self, p):
        """
        Calculates the centroid (geometric centre of mass) of a polygon.

        Parameters
        ----------
        p       array of [x,y] points defining polygon vertices

        Returns
        --------
        cx, cy  polygon centroid coordinates

        reference: https://en.wikipedia.org/wiki/Centroid#Of_a_polygon
        """
        foo = np.asarray(p)
        foo_p = np.roll(foo, -1, axis=0)
        ai = foo[:, 0] * foo_p[:, 1] - foo_p[:, 0] * foo[:, 1]
        aa = 1 / 2 * np.sum(ai)
        if aa != 0.0:
            cx = (
                1
                / (6 * aa)
                * np.sum(
                    (foo[:, 0] + foo_p[:, 0]) * (foo[:, 0] * foo_p[:, 1] - foo_p[:, 0] * foo[:, 1])
                )
            )
            cy = (
                1
                / (6 * aa)
                * np.sum(
                    (foo[:, 1] + foo_p[:, 1]) * (foo[:, 0] * foo_p[:, 1] - foo_p[:, 0] * foo[:, 1])
                )
            )
        else:
            mid = np.mean(p, axis=1)
            cx = mid[0]
            cy = mid[1]
        return (cx, cy)

    def circumc(self, A, B, C):
        """
        Calculates the circumcenter and circumradius of a triangle with
        vertices A = [Ax, Ay], B = [Bx, By], and C = [Cx, Cy]

        returns ox, oy, rc, the x and y coordinates of the circumcentre and
        the circumradius, respectively.

        """
        Ax = A[0]
        Ay = A[1]
        Bx = B[0]
        By = B[1]
        Cx = C[0]
        Cy = C[1]
        A2 = Ax**2 + Ay**2
        B2 = Bx**2 + By**2
        C2 = Cx**2 + Cy**2
        denom = 2 * (Ax * (By - Cy) + Bx * (Cy - Ay) + Cx * (Ay - By))
        ox = (A2 * (By - Cy) + B2 * (Cy - Ay) + C2 * (Ay - By)) / denom
        oy = (A2 * (Cx - Bx) + B2 * (Ax - Cx) + C2 * (Bx - Ax)) / denom
        a = np.sqrt((Ax - Bx) ** 2 + (Ay - By) ** 2)
        b = np.sqrt((Bx - Cx) ** 2 + (By - Cy) ** 2)
        c = np.sqrt((Cx - Ax) ** 2 + (Cy - Ay) ** 2)
        s = (a + b + c) / 2.0
        area = np.sqrt(s * (s - a) * (s - b) * (s - c))
        if area > 0.0:
            rc = a * b * c / (4.0 * area)
        else:
            rc = 0.0
        ri = 2 * area / (a + b + c)
        return (ox, oy, rc, ri)

    def quad_circumc(self, A, B, C, D):
        a = np.linalg.norm(B - A)
        b = np.linalg.norm(C - B)
        c = np.linalg.norm(D - C)
        d = np.linalg.norm(A - D)
        s = 1 / 2 * (a + b + c + d)
        area = np.sqrt((s - a) * (s - b) * (s - c) * (s - d))
        R = 1 / 4 * (np.sqrt((a * c + b * d) * (a * d + b * c) * (a * b + c * d)) / area)
        tando = C - A
        tanl = np.linalg.norm(C - A)
        tand = tando / tanl
        cx = A[0] + R * tand[0]
        cy = A[1] + R * tand[1]
        return (R, area, cx, cy)

    def cc_sort_inds(self, points_o):
        """
        Takes an assortment of points and sorts them counterclockwise to the
        mean of the point cloud.

        Returns indices requried to sort the points counterclockwise.
        """
        cent = points_o.mean(axis=0)
        angles = np.arctan2(points_o[:, 1] - cent[1], points_o[:, 0] - cent[0])
        inds_sort = np.argsort(angles)
        return inds_sort
