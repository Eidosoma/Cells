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

"""Private native lifecycle transcription; hooks observe source math unchanged."""
# Keep original unused source stores/loop variables for exact raw traces.
# ruff: noqa: F841, B007

import numpy as np


class LifecycleKernel:
    def init_mesh(self):
        try:
            self.pre_mesh()
            self.create_core_operators()
            if self.make_all_operators:
                self.create_aux_operators()
            self._cells_log("log_info", "Mesh creation complete!")
            self._cells_lifecycle_return(locals())
        except Exception:
            self._cells_lifecycle_partial(locals())
            raise

    def create_core_operators(self):
        try:
            self._cells_log("log_info", "Creating core operators...")
            delta_tri_0 = np.zeros((self.n_tedges, self.n_tverts))
            for ei, (vi, vj) in enumerate(self.tri_edges):
                delta_tri_0[ei, vj] = 1.0
                delta_tri_0[ei, vi] = -1.0
            self.delta_tri_0 = np.asarray(delta_tri_0)
            self.delta_tri_0_inv = self._cells_pinv(
                self.delta_tri_0, _cells_label="self.delta_tri_0_inv"
            )
            self._cells_lifecycle_return(locals())
        except Exception:
            self._cells_lifecycle_partial(locals())
            raise

    def create_aux_operators(self):
        try:
            self._cells_log("log_info", "Creating auxiliary operators...")
            delta_tri_1 = np.zeros((self.n_tcell, self.n_tedges))
            tedge_tree = self._cells_tree(self.tri_edges)
            for ic, vertis_o in enumerate(self.tri_cells):
                vertis_1 = np.roll(vertis_o, -1)
                for vi, vj in zip(vertis_o, vertis_1, strict=False):
                    disttea, ea = tedge_tree.query([vi, vj])
                    distteb, eb = tedge_tree.query([vj, vi])
                    if disttea == 0.0 and distteb != 0.0:
                        delta_tri_1[ic, ea] = 1
                    elif distteb == 0.0 and disttea != 0.0:
                        delta_tri_1[ic, eb] = -1
            self.delta_tri_1 = np.asarray(delta_tri_1)
            self.delta_tri_1_inv = self._cells_pinv(
                self.delta_tri_1, _cells_label="self.delta_tri_1_inv"
            )
            delta_vor_0 = np.zeros((self.n_vedges, self.n_vverts))
            for ei, (vi, vj) in enumerate(self.vor_edges):
                delta_vor_0[ei, vj] = 1.0
                delta_vor_0[ei, vi] = -1.0
            self.delta_vor_0 = np.asarray(delta_vor_0)
            self.delta_vor_0_inv = self._cells_pinv(
                self.delta_vor_0, _cells_label="self.delta_vor_0_inv"
            )
            delta_vor_1 = np.zeros((len(self.inner_tvert_i), self.n_vedges))
            vedge_tree = self._cells_tree(self.vor_edges)
            for ic, cell_verts in enumerate(self.vor_cells[self.inner_tvert_i]):
                cell_verts_roll = np.roll(cell_verts, 1)
                for vi, vj in zip(cell_verts, cell_verts_roll, strict=False):
                    distvea, ea = vedge_tree.query([vi, vj])
                    distveb, eb = vedge_tree.query([vj, vi])
                    if distvea == 0.0 and distveb != 0.0:
                        delta_vor_1[ic, ea] = 1
                    elif distveb == 0.0 and distvea != 0.0:
                        delta_vor_1[ic, eb] = -1
            self.delta_vor_1 = np.asarray(delta_vor_1)
            self.delta_vor_1_inv = self._cells_pinv(
                self.delta_vor_1, _cells_label="self.delta_vor_1_inv"
            )
            self._cells_lifecycle_return(locals())
        except Exception:
            self._cells_lifecycle_partial(locals())
            raise

    def mesh_quality_calc(self):
        try:
            uu = np.linalg.norm(self.tri_ccents - self.tri_cents, axis=1) ** 2
            self._cells_lifecycle_return(locals())
            return uu
        except Exception:
            self._cells_lifecycle_partial(locals())
            raise

    def refine_mesh(self, max_steps=25, convergence=7.5, fix_bounds=True):
        try:
            self._cells_log("log_info", "Initializing Voronoi mesh optimization...")
            opti_steps = np.arange(max_steps)
            ui = self.mesh_quality_calc()
            UU = np.sum(ui) / self.cell_radius**2
            for i in opti_steps:
                self._cells_iteration_start(locals())
                self.removed_bad_verts = False
                if UU > convergence:
                    self.removed_bad_verts = False
                    if fix_bounds:
                        self._cells_move_before("inner", axis=None, indices=self.inner_tvert_i)
                        self.tri_verts[self.inner_tvert_i] = self.vor_cents[self.inner_tvert_i] * 1
                        self._cells_move_after()
                    else:
                        self._cells_move_before("all", axis=None, indices=None)
                        self.tri_verts = self.vor_cents * 1
                        self._cells_move_after()
                    self.pre_mesh()
                    ui = self.mesh_quality_calc()
                    UU = np.sum(ui) / self.cell_radius**2
                    conv_mess = "Step {}: mesh energy {}".format(i, UU)
                    self._cells_log("log_info", conv_mess)
                else:
                    self.mesh_qual = UU
                    self._cells_log("log_info", "Convergence condition met for mesh optimization.")
                    self._cells_log("log_info", "Final mesh quality %f", UU)
                    self._cells_iteration_end(locals(), termination="converged")
                    break
                self._cells_iteration_end(locals(), termination="step_completed")
            self._cells_lifecycle_return(locals())
        except Exception:
            self._cells_lifecycle_partial(locals())
            raise

    def laplacian_smoothing(self, stepsize):
        try:
            if stepsize is not None:
                self._cells_log("log_info", "Smoothing mesh...")
                self.removed_bad_verts = False
                II = np.diag(np.ones(self.n_tverts))
                HH2 = np.diag(1 / self.vor_sa)
                HH1 = np.diag(self.vor_edge_len / self.tri_edge_len)
                term1 = self._cells_dot(HH2, -self.delta_tri_0.T, _cells_label="term1")
                term2 = self._cells_dot(HH1, self.delta_tri_0, _cells_label="term2")
                LL = self._cells_dot(term1, term2, _cells_label="LL")
                MM = II - stepsize * LL
                MM_inv = self._cells_pinv(MM, _cells_label="MM_inv")
                self._cells_move_before("coordinate", axis=0, indices=None)
                self.tri_verts[:, 0] = self._cells_dot(
                    MM_inv, self.tri_verts[:, 0], _cells_label="self.tri_verts[:, 0]"
                )
                self._cells_move_after()
                self._cells_move_before("coordinate", axis=1, indices=None)
                self.tri_verts[:, 1] = self._cells_dot(
                    MM_inv, self.tri_verts[:, 1], _cells_label="self.tri_verts[:, 1]"
                )
                self._cells_move_after()
            self._cells_lifecycle_return(locals())
        except Exception:
            self._cells_lifecycle_partial(locals())
            raise

    def after_clip_lifecycle(
        self, smoothing=None, refinement=True, max_steps=25, convergence=7.5, fix_bounds=True
    ):
        try:
            if smoothing is not None:
                self.init_mesh()
                self.laplacian_smoothing(stepsize=smoothing)
                self.pre_mesh()
            if refinement:
                self.refine_mesh(
                    max_steps=max_steps, convergence=convergence, fix_bounds=fix_bounds
                )
                self.pre_mesh()
            self.create_core_operators()
            if self.make_all_operators:
                self.create_aux_operators()
            self._cells_log("log_info", "Mesh creation complete!")
            self._cells_lifecycle_return(locals())
        except Exception:
            self._cells_lifecycle_partial(locals())
            raise
