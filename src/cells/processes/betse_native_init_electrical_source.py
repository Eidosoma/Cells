# Copyright 2014-2025 Alexis Pietak & Cecil Curry; see licenses/BETSE.txt.
# ruff: noqa: F821, E501, B905, N802, N803, N806
"""Literal current/field/voltage closure; definitions grant no live authority."""

SOURCE_PINS = {
    "betse/science/sim.py": "02a9a049b5daa5cf6bc543332aa89437f58a4700ed31310abc3ee13697f22d43",
    "betse/science/physics/ion_current.py": "a9a82ef377853c3e83466c312e508fdb33cae28237c5310a00fb50df3f56bc9f",
    "betse/science/sim_toolbox.py": "d94b50e8c0fdcee28b6b301c493ffa5aaf42b18e87ea4750483e164a3bdcacec",
    "betse/science/math/finitediff.py": "8186bc5c013db8aec224f6ed9b0892e944b2ddd4247f135ff19caf7419478350",
}
ROSTER = (
    ("update_V", "betse/science/sim.py", "Simulator", 2007, 2083),
    ("get_current", "betse/science/physics/ion_current.py", None, 13, 171),
    ("HH_Decomp", "betse/science/sim_toolbox.py", None, 1236, 1290),
    ("smooth_flux", "betse/science/sim_toolbox.py", None, 1318, 1333),
    ("gradient", "betse/science/math/finitediff.py", None, 1236, 1266),
    ("diff", "betse/science/math/finitediff.py", None, 1268, 1303),
    ("divergence", "betse/science/math/finitediff.py", None, 1305, 1311),
)


class ElectricalKernel:
    def update_V(self, cells, p):
        vmo = self.vm * 1
        get_current(self, cells, p)
        self.sigma_cell = np.asarray(
            [
                z**2 * p.F**2 * cc * D * 0.1 / (p.R * p.T)
                for z, cc, D in zip(self.zs, self.cc_cells, self.D_free)
            ]
        ).mean(axis=0)
        if p.cell_polarizability == 0.0:
            rho_surf = self.rho_cells * cells.diviterm
            self.vm = 1 / p.cm * rho_surf[cells.mem_to_cells] - self.Phi_b[cells.map_mem2ecm]
            self.vm_ave = np.dot(cells.M_sum_mems, self.vm) / cells.num_mems
            self.E_cell_x = self.J_cell_x / self.sigma_cell
            self.E_cell_y = self.J_cell_y / self.sigma_cell
            self.Emc = (
                self.E_cell_x[cells.mem_to_cells] * cells.mem_vects_flat[:, 2]
                + self.E_cell_y[cells.mem_to_cells] * cells.mem_vects_flat[:, 3]
            )
        else:
            rho_surf = self.rho_cells * cells.diviterm
            vm_o = 1 / p.cm * rho_surf[cells.mem_to_cells]
            self.vm = (
                self.vm
                - p.dt / p.cm * self.Jn
                + p.dt * self.sigma_cell[cells.mem_to_cells] * vm_o / (p.cm * cells.R_rads)
            ) / (1 + p.dt * self.sigma_cell[cells.mem_to_cells] / (p.cm * cells.R_rads))
            self.vm_ave = np.dot(cells.M_sum_mems, self.vm) / cells.num_mems
            Rcells = cells.R_rads * (p.true_cell_size / p.cell_radius)
            gE = (self.vm - self.vm_ave[cells.mem_to_cells]) / Rcells
            gEx = -gE * cells.mem_vects_flat[:, 2]
            gEy = -gE * cells.mem_vects_flat[:, 3]
            self.E_cell_x = np.dot(cells.M_sum_mems, gEx * cells.mem_sa) / cells.cell_sa
            self.E_cell_y = np.dot(cells.M_sum_mems, gEy * cells.mem_sa) / cells.cell_sa
            self.Emc = (
                self.E_cell_x[cells.mem_to_cells] * cells.mem_vects_flat[:, 2]
                + self.E_cell_y[cells.mem_to_cells] * cells.mem_vects_flat[:, 3]
            )
        self.dvm = (self.vm - vmo) / p.dt


def get_current(sim, cells, p) -> None:
    """
    Calculate currents in both cells and the environment.
    """
    sim.rho_cells = np.dot(sim.zs * p.F, sim.cc_cells) + sim.extra_rho_cells
    sim.Jmem = -np.dot(sim.zs * p.F, sim.fluxes_mem) + sim.extra_J_mem
    sim.Jgj = np.dot(sim.zs * p.F, sim.fluxes_gj)
    sim.Jn = sim.Jmem + sim.Jgj
    Jn_ave = np.dot(cells.M_sum_mems, sim.Jn * cells.mem_sa) / cells.cell_sa
    sim.Jn = sim.smooth_weight_mem * sim.Jn + Jn_ave[cells.mem_to_cells] * sim.smooth_weight_o
    sim.I_mem = -sim.Jn * cells.mem_sa
    Jcx = sim.Jn * cells.mem_vects_flat[:, 2]
    Jcy = sim.Jn * cells.mem_vects_flat[:, 3]
    sim.J_cell_x = np.dot(cells.M_sum_mems, Jcx * cells.mem_sa) / cells.cell_sa
    sim.J_cell_y = np.dot(cells.M_sum_mems, Jcy * cells.mem_sa) / cells.cell_sa
    sim.Jc = (
        sim.J_cell_x[cells.mem_to_cells] * cells.mem_vects_flat[:, 2]
        + sim.J_cell_y[cells.mem_to_cells] * cells.mem_vects_flat[:, 3]
    )
    if p.is_ecm is True:
        J_env_x_o = np.dot(p.F * sim.zs, sim.fluxes_env_x) + sim.extra_Jenv_x
        J_env_y_o = np.dot(p.F * sim.zs, sim.fluxes_env_y) + sim.extra_Jenv_y
        J_env_x_o = J_env_x_o.reshape(cells.X.shape)
        J_env_y_o = J_env_y_o.reshape(cells.X.shape)
        BB, sim.J_env_x, sim.J_env_y, _, Ja, Jb = stb.HH_Decomp(
            J_env_x_o, J_env_y_o, cells, bounds=sim.bound_V
        )
        sim.B_field = BB * p.mu
        sim.Jtx = sim.J_env_x + Ja
        sim.Jty = sim.J_env_y + Jb
        sim.rho_env = np.dot(sim.zs * p.F, sim.cc_env) + sim.extra_rho_env
        div_Jb = np.zeros(cells.X.shape)
        div_Jb[:, -1] = -sim.bound_V["R"] / cells.delta**2
        div_Jb[:, 0] = -sim.bound_V["L"] / cells.delta**2
        div_Jb[-1, :] = -sim.bound_V["T"] / cells.delta**2
        div_Jb[0, :] = -sim.bound_V["B"] / cells.delta**2
        Phi_b = np.dot(cells.lapENVinv, -div_Jb.ravel())
        sim.rho_env_surf = np.zeros(sim.edl)
        sim.rho_env_surf[cells.map_mem2ecm] = (
            sim.rho_env[cells.map_mem2ecm]
            * (p.cell_height * cells.delta**2)
            / cells.memSa_per_envSquare[cells.map_mem2ecm].mean()
        )
        sim.v_env = sim.rho_env_surf / (sim.ko_env * p.eo * p.er)
        screen = 2 / (sim.ko_env * cells.delta) * (p.cell_radius / p.true_cell_size)
        sim.v_env = (
            gaussian_filter(sim.v_env.reshape(cells.X.shape), 1, mode="constant", cval=0.0).ravel()
            + Phi_b
        )
        gVex, gVey = fd.gradient(screen * sim.v_env.reshape(cells.X.shape), cells.delta)
        sim.E_env_x = -gVex
        sim.E_env_y = -gVey
        sim.Eme = (
            sim.E_env_x.ravel()[cells.map_mem2ecm] * cells.mem_vects_flat[:, 2]
            + sim.E_env_y.ravel()[cells.map_mem2ecm] * cells.mem_vects_flat[:, 3]
        )
        sim.Phi_b = Phi_b
    else:
        vc = sim.vm / 2
        vce = np.zeros(len(cells.xypts))
        vce[cells.map_mem2ecm] = vc[cells.mem_to_cells]
        Phi = -vce.reshape(cells.X.shape)
        Phi = gaussian_filter(Phi, 1)
        gVex, gVey = fd.gradient(cells.delta * Phi.reshape(cells.X.shape), cells.delta)
        gVex, gVey = stb.smooth_flux(
            gVex.reshape(cells.X.shape), gVey.reshape(cells.X.shape), cells
        )
        sim.E_env_x = -gVex
        sim.E_env_y = -gVey
        Jxo = sim.sigma * sim.E_env_x * sim.D_env_weight
        Jyo = sim.sigma * sim.E_env_y * sim.D_env_weight
        BB, sim.J_env_x, sim.J_env_y, _, Ja, Jb = stb.HH_Decomp(Jxo, Jyo, cells)
        sim.B_field = BB * p.mu
        sim.Jtx = sim.J_env_x + Ja
        sim.Jty = sim.J_env_y + Jb
        sim.Eme = (
            sim.E_env_x.ravel()[cells.map_mem2ecm] * cells.mem_vects_flat[:, 2]
            + sim.E_env_y.ravel()[cells.map_mem2ecm] * cells.mem_vects_flat[:, 3]
        )
        sim.v_env = Phi.ravel()
        div_Jb = np.zeros(cells.X.shape)
        div_Jb[:, -1] = -sim.bound_V["R"] / cells.delta**2
        div_Jb[:, 0] = -sim.bound_V["L"] / cells.delta**2
        div_Jb[-1, :] = -sim.bound_V["T"] / cells.delta**2
        div_Jb[0, :] = -sim.bound_V["B"] / cells.delta**2
        Phi_b = np.dot(cells.lapENVinv, -div_Jb.ravel())
        sim.Phi_b = Phi_b


def HH_Decomp(JJx, JJy, cells, bounds=None, sigma=1.0):
    if bounds is not None:
        Lb = bounds["L"]
        Rb = bounds["R"]
        Tb = bounds["T"]
        Bb = bounds["B"]
    else:
        Lb = 0.0
        Rb = 0.0
        Tb = 0.0
        Bb = 0.0
    Jxr = -JJy.reshape(cells.X.shape)
    Jyr = JJx.reshape(cells.X.shape)
    divJr = fd.divergence(Jxr, Jyr, cells.delta, cells.delta)
    divJr[:, 0] = 0.0
    divJr[:, -1] = 0.0
    divJr[0, :] = 0.0
    divJr[-1, :] = 0.0
    AA = np.dot(cells.lapENVinv, -divJr.ravel())
    gAx, gAy = fd.gradient(AA.reshape(cells.X.shape), cells.delta)
    Fx = -gAy
    Fy = gAx
    divJd = fd.divergence(
        JJx.reshape(cells.X.shape) / sigma,
        JJy.reshape(cells.X.shape) / sigma,
        cells.delta,
        cells.delta,
    )
    divJd[:, 0] = -Lb * (1 / cells.delta**2)
    divJd[:, -1] = -Rb * (1 / cells.delta**2)
    divJd[0, :] = -Bb * (1 / cells.delta**2)
    divJd[-1, :] = -Tb * (1 / cells.delta**2)
    BB = np.dot(cells.lapENVinv, divJd.ravel())
    Gx, Gy = fd.gradient(BB.reshape(cells.X.shape), cells.delta)
    return (AA, Fx, Fy, BB, Gx, Gy)


def smooth_flux(Fxo, Fyo, cells):
    """
    Uses the Helmholtz-Hodge decomposition to smooth a vector field in a manner that does not change the physics.
    Fxo, Fyo must be arrays defined on the environmental grid

    """
    _, Frx, Fry, _, Fdx, Fdy = HH_Decomp(Fxo, Fyo, cells)
    Fx = Frx + Fdx
    Fy = Fry + Fdy
    return (Fx, Fy)


def gradient(F, delx, dely=None):
    if dely is None:
        dely = delx
    dF_interior_y = -(F[:-2, :] - F[2:, :]) / (2 * dely)
    dF_interior_x = -(F[:, :-2] - F[:, 2:]) / (2 * delx)
    dF_B = (F[1, :] - F[0, :]) / dely
    dF_T = (F[-1, :] - F[-2, :]) / dely
    dF_L = (F[:, 1] - F[:, 0]) / delx
    dF_R = (F[:, -1] - F[:, -2]) / delx
    dFx = np.zeros(F.shape)
    dFy = np.zeros(F.shape)
    dFx[:, 1:-1] = dF_interior_x
    dFy[1:-1, :] = dF_interior_y
    dFx[:, 0] = dF_L
    dFx[:, -1] = dF_R
    dFy[0, :] = dF_B
    dFy[-1, :] = dF_T
    return (dFx, dFy)


def diff(F, delx, axis=0):
    if axis == 1:
        dF_interior = -(F[:-2, :] - F[2:, :]) / (2 * delx)
        dF_B = -(F[1, :] - F[0, :]) / delx
        dF_T = -(F[-1, :] - F[-2, :]) / delx
        dF = np.zeros(F.shape)
        dF[1:-1, :] = dF_interior
        dF[0, :] = dF_B
        dF[-1, :] = dF_T
    elif axis == 0:
        dF_interior = -(F[:, :-2] - F[:, 2:]) / (2 * delx)
        dF_L = (F[:, 0] - F[:, 1]) / delx
        dF_R = (F[:, -2] - F[:, -1]) / delx
        dF = np.zeros(F.shape)
        dF[:, 1:-1] = dF_interior
        dF[:, 0] = dF_L
        dF[:, -1] = dF_R
    return dF


def divergence(Fx, Fy, delx, dely):
    gx = diff(Fx, delx, axis=0)
    gy = diff(Fy, dely, axis=1)
    div = gx + gy
    return div
