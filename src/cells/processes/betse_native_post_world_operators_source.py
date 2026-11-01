# Copyright 2014-2025 Alexis Pietak & Cecil Curry; see licenses/BETSE.txt.
"""Literal native graph operator body; vectors reuse the owned literal kernel."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np

CELLS_SHA256 = "be38678a4f0bd084044fe7d952d74a4550003ce9701f5d073d1f124ba6daeaf2"
NATIVE_LINES = {"calc_gj_vects": (2018, 2118), "graphLaplacian": (1845, 1894)}
logs = SimpleNamespace(log_debug=lambda *args: None)


class PostWorldKernel:
    def graphLaplacian(self, p) -> None:
        """
        Define an abstract inverse Laplacian used to solve Poisson's equation
        on the irregular Voronoi grid of this cell cluster.

        Parameters
        ----------
        p : Parameters
            Current simulation configuration.

        Creates
        ----------
        self.lapGJinv          Solver for Poisson equation with Neumann (zero gradient) boundary
        """
        logs.log_debug("Creating cell network Poisson solver...")
        star_eij = np.diag(self.mesh.vor_edge_len / self.mesh.tri_edge_len)
        L1 = np.dot(star_eij, self.mesh.delta_tri_0)
        star_a = np.diag(1 / self.mesh.vor_sa)
        L2 = np.dot(star_a, -self.mesh.delta_tri_0.T)
        star_eij_inv = np.diag(self.mesh.tri_edge_len / self.mesh.vor_edge_len)
        L1_inv = np.dot(self.mesh.delta_tri_0_inv, star_eij_inv)
        star_a_inv = np.diag(self.mesh.vor_sa)
        L2_inv = np.dot(-self.mesh.delta_tri_0_inv.T, star_a_inv)
        self.lapGJinv = np.dot(L1_inv, L2_inv)
        self.lapGJ = np.dot(L2, L1)
        self.geom_weight = np.dot(self.M_sum_mems, self.mem_sa / self.mem_vol) * p.cell_height
