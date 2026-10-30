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

"""Private attributed clipping source; static preparation, not qualified geometry."""
# Preserve original unused source stores/loop variables for trace comparison.
# ruff: noqa: F841, B007

from collections.abc import Sequence
from numbers import Number
from types import GeneratorType, SimpleNamespace

import numpy as np

NumpyArrayType = np.ndarray
NumericTypes = (Number,)
SequenceTypes = (Sequence, np.ndarray)
ndarray = np.ndarray
classes = SimpleNamespace(get_name_unqualified=lambda value: value.__name__)


class BetseMathLineException(ValueError):
    pass


class BetseMathPointException(ValueError):
    pass


class BetseMathPolygonException(ValueError):
    pass


class BetseIterableException(ValueError):
    pass


class Tools:
    def clip_counterclockwise(self, subject_polygon, clip_polygon):
        try:
            self.die_unless_polygon(subject_polygon, clip_polygon)
            subj_poly_curr = subject_polygon
            subj_poly_prev = None
            clip_vert_curr = clip_polygon[-1]
            clip_vert_next = None
            subj_vert_curr = None
            subj_vert_next = None
            is_subj_vert_curr_inside = None
            is_subj_vert_next_inside = None
            for clip_vert_next in clip_polygon:
                self._cells_edge(locals())
                if len(subj_poly_curr) == 0:
                    break
                subj_poly_prev = subj_poly_curr
                subj_poly_curr = []
                subj_vert_curr = subj_poly_prev[-1]
                is_subj_vert_curr_inside = self.is_left_of_vector(
                    subject_point=subj_vert_curr,
                    vector_head_point=clip_vert_next,
                    vector_tail_point=clip_vert_curr,
                )
                for subj_vert_next in subj_poly_prev:
                    is_subj_vert_next_inside = self.is_left_of_vector(
                        subject_point=subj_vert_next,
                        vector_head_point=clip_vert_next,
                        vector_tail_point=clip_vert_curr,
                    )
                    if is_subj_vert_curr_inside != is_subj_vert_next_inside:
                        subj_poly_curr.append(
                            self.intersect_lines(
                                line1_point1=clip_vert_curr,
                                line1_point2=clip_vert_next,
                                line2_point1=subj_vert_curr,
                                line2_point2=subj_vert_next,
                            )
                        )
                    if is_subj_vert_next_inside:
                        subj_poly_curr.append(subj_vert_next)
                    subj_vert_curr = subj_vert_next
                    is_subj_vert_curr_inside = is_subj_vert_next_inside
                clip_vert_curr = clip_vert_next
            self._cells_return_locals(locals())
            return self.iterable_to_iterable(iterable=subj_poly_curr, cls=type(subject_polygon))
        except Exception:
            self._cells_partial(locals())
            raise

    def orient_counterclockwise(self, polygon):
        pass
        self.die_unless_polygon(polygon)
        poly_verts = self.array_from_iterable(polygon)
        poly_centre = poly_verts.mean(axis=0)
        poly_angles = np.arctan2(
            poly_verts[:, 1] - poly_centre[1], poly_verts[:, 0] - poly_centre[0]
        )
        poly_verts_sorted_index = poly_angles.argsort()
        poly_verts_sorted = poly_verts[poly_verts_sorted_index]
        self._cells_return_locals(locals())
        return self.array_to_iterable(array=poly_verts_sorted, cls=type(polygon))

    def die_unless_polygon(self, *polygons):
        if not self.is_polygon(*polygons):
            for polygon in polygons:
                if not self.is_polygon(polygon):
                    raise BetseMathPolygonException(
                        (
                            "Sequence not a two-dimensional polygon "
                            "(i.e., length < 3 or item length != 2): {!r}"
                        ).format(polygon)
                    )

    def is_polygon(self, *polygons):
        pass
        return all((len(polygon) >= 3 and self.is_point(*polygon) for polygon in polygons))

    def die_unless_point(self, *points):
        if not self.is_point(*points):
            for point in points:
                if not self.is_point(point):
                    if len(point) != 2:
                        raise BetseMathPointException(
                            "Sequence not a two-dimensional point (i.e., length != 2): {!r}".format(
                                point
                            )
                        )
                    else:
                        raise BetseMathPointException(
                            (
                                "Sequence not a two-dimensional point "
                                "(i.e., one or more coordinates not numbers): {!r}"
                            ).format(point)
                        )

    def is_point(self, *points):
        return all(
            (
                len(point) == 2
                and (
                    isinstance(point, NumpyArrayType)
                    or all(
                        (isinstance(point_coordinate, NumericTypes) for point_coordinate in point)
                    )
                )
                for point in points
            )
        )

    def is_left_of_vector(self, subject_point, vector_head_point, vector_tail_point):
        self.die_unless_point(subject_point, vector_head_point, vector_tail_point)
        return (vector_head_point[0] - vector_tail_point[0]) * (
            subject_point[1] - vector_tail_point[1]
        ) > (vector_head_point[1] - vector_tail_point[1]) * (
            subject_point[0] - vector_tail_point[0]
        )

    def intersect_lines(self, line1_point1, line1_point2, line2_point1, line2_point2):
        self.die_unless_point(line1_point1, line1_point2, line2_point1, line2_point2)
        cx = line1_point1[0]
        dx = line1_point2[0]
        sx = line2_point1[0]
        tx = line2_point2[0]
        cy = line1_point1[1]
        dy = line1_point2[1]
        sy = line2_point1[1]
        ty = line2_point2[1]
        dcx = dx - cx
        dcy = dy - cy
        tsx = tx - sx
        tsy = ty - sy
        detM = dcx * tsy - dcy * tsx
        if detM == 0:
            raise BetseMathLineException(
                (
                    "Line through points {!r} and {!r} and line through points {!r} "
                    "and {!r} either infinitely or never intersect."
                ).format(cx, dx, sx, tx)
            )
        detdc = dx * cy - dy * cx
        detts = tx * sy - ty * sx
        intersection_point = (
            (detdc * tsx - detts * dcx) / detM,
            (detdc * tsy - detts * dcy) / detM,
        )
        intersection_point_sequence = self.iterable_to_iterable(
            iterable=intersection_point, cls=type(line1_point1)
        )
        self.die_unless_point(intersection_point_sequence)
        self._cells_return_locals(locals())
        return intersection_point_sequence

    def array_from_iterable(self, iterable):
        sequence = iterable if self.is_sequence(iterable) else tuple(iterable)
        return np.asarray(sequence)

    def array_to_iterable(self, array, cls):
        if cls is NumpyArrayType:
            return array
        array_list = array.tolist()
        if cls is list:
            return array_list
        return cls(array_list)

    def iterable_to_iterable(self, iterable, cls=None, item_cls=None):
        pass
        pass
        pass
        pass
        iterable_src_cls = type(iterable)
        iterable_trg_cls = cls
        if iterable_trg_cls is None:
            if self.is_generator(iterable):
                iterable_trg_cls = tuple
            else:
                iterable_trg_cls = iterable_src_cls
        if iterable_src_cls is iterable_trg_cls and item_cls is None:
            return iterable
        if iterable_src_cls is ndarray:
            if item_cls is not None:
                raise BetseIterableException(
                    'Numpy array not convertible to item class "{}".'.format(
                        classes.get_name_unqualified(item_cls)
                    )
                )
            return self.array_to_iterable(array=iterable, cls=iterable_trg_cls)
        if iterable_trg_cls is ndarray:
            if item_cls is not None:
                raise BetseIterableException(
                    'Numpy array not convertible to item class "{}".'.format(
                        classes.get_name_unqualified(item_cls)
                    )
                )
            return self.array_from_iterable(iterable)
        return (
            iterable_trg_cls(iterable)
            if item_cls is None
            else iterable_trg_cls((item_cls(item) for item in iterable))
        )

    def is_sequence(self, *objs):
        return all((isinstance(obj, SequenceTypes) for obj in objs))

    def is_generator(self, obj):
        return isinstance(obj, GeneratorType)


class ClipKernel:
    def search_point_cloud(self, pts, pt_cloud):
        try:
            if len(pts) == 0:
                matched_pts = []
                unmatched_pts = []
            elif len(pt_cloud) == 0:
                matched_pts = []
                unmatched_pts = []
            else:
                search_M = 99 * np.ones((len(pts), len(pt_cloud)))
                pts_inds = np.asarray([i for i, cc in enumerate(pts)])
                for i, pt in enumerate(pts):
                    for j, ptc in enumerate(pt_cloud):
                        dist = np.sqrt((pt[0] - ptc[0]) ** 2 + (pt[1] - ptc[1]) ** 2)
                        if dist < 1e-15:
                            search_M[i, j] = 1.0
                        else:
                            search_M[i, j] = 0.0
                matched_inds, matched_inds_cloud = (search_M == 1).nonzero()
                unmatched_inds = np.setdiff1d(pts_inds, matched_inds)
                matched_pts = pts[matched_inds]
                unmatched_pts = pts[unmatched_inds]
            self._cells_return_locals(locals())
            return (matched_pts, unmatched_pts)
        except Exception:
            self._cells_partial(locals())
            raise

    def clip_to_curve(self, imagemask):
        try:
            clip_vor_verts = []
            clip_vor_cents = []
            self.removed_bad_verts = False
            for ii, (poly_ind, cell_poly, vor_cent) in enumerate(
                zip(self.vor_cells, self.vcell_verts, self.vor_cents, strict=False)
            ):
                self._cells_cell_enter(ii, poly_ind, cell_poly, vor_cent)
                cent_val = imagemask.clipping_function(vor_cent[0], vor_cent[1])
                if cent_val != 0.0:
                    cent_val = 1.0
                if len(poly_ind) >= 3:
                    cell_polya = cell_poly.tolist()
                    point_check = np.zeros(len(cell_poly))
                    for i, pnt in enumerate(cell_poly):
                        point_val = imagemask.clipping_function(pnt[0], pnt[1])
                        if point_val != 0.0:
                            point_check[i] = 1.0
                    if point_check.sum() == len(cell_poly):
                        clip_vor_verts.append(np.array(cell_polya))
                        cx, cy = self.poly_centroid(cell_polya)
                        clip_vor_cents.append([cx, cy])
                    elif (
                        point_check.sum() > 0.0
                        and point_check.sum() < len(cell_poly)
                        and (cent_val == 1.0)
                    ):
                        clip_poly = self._cells_tools.clip_counterclockwise(
                            cell_poly, imagemask.clipcurve
                        )
                        if len(clip_poly):
                            old_poly_pts, new_poly_pts = self.search_point_cloud(
                                clip_poly, cell_poly
                            )
                            throw_away_pts, keeper_pts = self.search_point_cloud(
                                new_poly_pts, imagemask.clipcurve
                            )
                            outside_cell_a, outside_cell_b = self.search_point_cloud(
                                cell_poly, clip_poly
                            )
                            if len(keeper_pts) == 0:
                                out_stack = []
                                in_stack = old_poly_pts * 1
                            else:
                                out_stack = np.vstack((outside_cell_b, keeper_pts))
                                in_stack = np.vstack((old_poly_pts, keeper_pts))
                            if len(in_stack) >= 3:
                                in_vor_cell = self._cells_tools.orient_counterclockwise(in_stack)
                                clip_vor_verts.append(in_vor_cell)
                                cx, cy = self.poly_centroid(in_vor_cell)
                                clip_vor_cents.append([cx, cy])
                self._cells_cell_exit(locals())
            clip_vor_cents = np.asarray(clip_vor_cents)
            self.tri_verts = clip_vor_cents
            self._cells_centroids_replaced(clip_vor_verts, clip_vor_cents)
            self.image_mask = imagemask
            self.pre_mesh()
        except Exception:
            self._cells_partial(locals())
            raise
