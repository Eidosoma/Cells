# ruff: noqa: B007, B905, E501
"""Literal nonempty molecule chemistry and real no-ECM transport.

This is a conditional configured-state seam, not full native initialization.
Static preparation only; no numeric qualification has run.
"""

import copy
from abc import ABCMeta
from collections import OrderedDict
from collections.abc import Mapping, MutableMapping
from types import MappingProxyType, SimpleNamespace

import numpy as np

from cells.processes import betse_normal_ion_join as ions
from cells.processes import betse_normal_network_join_source as feedback_source


def _outside_scope(*args, **kwargs):
    raise ValueError("Requires separately owned ECM/intracellular-field/motor state")


fd = SimpleNamespace(gradient=_outside_scope, divergence=_outside_scope, integrator=_outside_scope)
div_env = _outside_scope
nernst_planck_flux = _outside_scope


class BetseException(Exception, metaclass=ABCMeta):
    pass


class BetseSimException(BetseException):
    pass


class BetseSimUnstableException(BetseSimException):
    pass


def electroflux(cA, cB, Dc, d, zc, vBA, T, p, rho=1):
    FLOAT_NONCE = 1e-25
    vBA += FLOAT_NONCE
    zc += FLOAT_NONCE
    alpha = zc * vBA * p.F / (p.R * T)
    exp_alpha = np.exp(-alpha)
    deno = -np.expm1(-alpha)
    flux = -(Dc * alpha / d) * ((cB - cA * exp_alpha) / deno) * rho
    return flux


def molecule_mover(
    sim,
    cX_env_o,
    cX_cells,
    cells,
    p,
    z=0,
    Dm=1e-18,
    Do=1e-09,
    Dgj=1e-12,
    Ftj=1.0,
    c_bound=0.0,
    ignoreECM=True,
    smoothECM=False,
    ignoreTJ=False,
    ignoreGJ=False,
    rho=1,
    cmems=None,
    time_dilation_factor=1.0,
    update_intra=False,
    name="Unknown",
    transmem=False,
    mu_mem=0.0,
    umt=0.0,
):
    if p.is_ecm is True:
        cX_env = cX_env_o[cells.map_mem2ecm]
    else:
        cX_env = cX_env_o[:]
    if cmems is None:
        cX_mems = cX_cells[cells.mem_to_cells]
    elif len(cmems) == sim.mdl:
        cX_mems = cmems
    Dm_vect = np.ones(len(cX_mems)) * Dm
    if Dm != 0.0:
        IdM = np.ones(sim.mdl)
        f_X_ED = electroflux(
            cX_env, cX_mems, Dm_vect, p.tm * IdM, z * IdM, sim.vm, sim.T, p, rho=rho
        )
        if p.cluster_open is False:
            f_X_ED[cells.bflags_mems] = 0
    else:
        f_X_ED = np.zeros(sim.mdl)
    cX_cells, cX_mems, cX_env_o = update_Co(
        sim,
        cX_cells,
        cX_mems,
        cX_env_o,
        f_X_ED,
        cells,
        p,
        ignoreECM=ignoreECM,
        update_at_mems=update_intra,
    )
    p._mover_observe("membrane_commit", name, locals(), sim)
    if ignoreGJ is False:
        fgj_X = electroflux(
            cX_mems[cells.mem_i],
            cX_mems[cells.nn_i],
            Dgj * sim.gj_block * sim.gjopen,
            cells.gj_len * np.ones(sim.mdl),
            z * np.ones(sim.mdl),
            sim.vgj,
            p.T,
            p,
            rho=1,
        )
        fgj_X[cells.bflags_mems] = 0.0
        delta_cco = np.dot(cells.M_sum_mems, -fgj_X * cells.mem_sa) / cells.cell_vol
        if update_intra is False:
            cX_cells = cX_cells + p.dt * delta_cco * time_dilation_factor
            cX_mems = cX_cells[cells.mem_to_cells]
        else:
            cX_cells = cX_cells + p.dt * delta_cco * time_dilation_factor
            cX_mems += (
                -fgj_X * (cells.mem_sa / (3 / 4 * cells.mem_vol)) * time_dilation_factor * p.dt
            )
    else:
        fgj_X = np.zeros(sim.mdl)
    p._mover_observe("junction_commit", name, locals(), sim)
    if update_intra is False and ignoreGJ and (transmem is True):
        nx = cells.mem_vects_flat[:, 2]
        ny = cells.mem_vects_flat[:, 3]
        gcc, gccmx, gccmy = cells.gradient(cX_cells)
        mcc = (cX_mems[cells.nn_i] + cX_mems[cells.mem_i]) / 2
        umtx = 0.0
        umty = 0.0
        emtx = (
            sim.E_cell_x[cells.mem_to_cells][cells.nn_i]
            + sim.E_cell_x[cells.mem_to_cells][cells.nn_i]
        ) / 2
        emty = (
            sim.E_cell_y[cells.mem_to_cells][cells.nn_i]
            + sim.E_cell_y[cells.mem_to_cells][cells.nn_i]
        ) / 2
        alpha = Do * p.q * z / (p.kb * sim.T)
        flux_mtx = -Do * gccmx + umtx * mcc * umt + (mu_mem + alpha) * emtx * mcc
        flux_mty = -Do * gccmy + umty * mcc * umt + (mu_mem + alpha) * emty * mcc
        flux_mtn = flux_mtx * nx + flux_mty * ny
        flux_mtn[cells.bflags_mems] = 0.0
        div_ccmt = -np.dot(cells.M_sum_mems, flux_mtn * cells.mem_sa) / cells.cell_vol
        cX_cells += div_ccmt * p.dt * time_dilation_factor
        cX_mems = cX_cells[cells.mem_to_cells] * 1
    if p.is_ecm is True:
        env_check = len((cX_env_o != 0.0).nonzero()[0])
        if env_check != 0.0 or c_bound > 1e-15:
            cenv = cX_env_o
            cenv = cenv.reshape(cells.X.shape)
            cenv[:, 0] = c_bound
            cenv[:, -1] = c_bound
            cenv[0, :] = c_bound
            cenv[-1, :] = c_bound
            denv_multiplier = np.ones(len(cells.xypts))
            if ignoreTJ is False:
                denv_multiplier = denv_multiplier.reshape(cells.X.shape) * sim.D_env_weight
                denv_multiplier.ravel()[sim.TJ_targets] = (
                    denv_multiplier.ravel()[sim.TJ_targets] * Ftj
                )
            else:
                denv_multiplier = denv_multiplier.reshape(cells.X.shape)
            gcx, gcy = fd.gradient(cenv, cells.delta)
            if p.fluid_flow is True:
                ux = sim.u_env_x.reshape(cells.X.shape)
                uy = sim.u_env_y.reshape(cells.X.shape)
            else:
                ux = 0.0
                uy = 0.0
            fx, fy = nernst_planck_flux(
                cenv,
                gcx,
                gcy,
                -sim.E_env_x,
                -sim.E_env_y,
                ux,
                uy,
                denv_multiplier * Do,
                z,
                sim.T,
                p,
                mu=mu_mem,
            )
            div_fa = fd.divergence(-fx, -fy, cells.delta, cells.delta)
            fenvx = fx
            fenvy = fy
            cenv = cenv + div_fa * p.dt * time_dilation_factor
            if p.sharpness < 1.0:
                cenv = fd.integrator(cenv, sharp=p.sharpness)
            cX_env_o = cenv.ravel()
        else:
            fenvx = np.zeros(sim.edl)
            fenvy = np.zeros(sim.edl)
    else:
        cX_env_temp = cX_env_o.mean()
        cX_env_o = np.zeros(sim.mdl)
        cX_env_o[:] = cX_env_temp
        fenvx = 0
        fenvy = 0
    p._mover_observe("environment_mix", name, locals(), sim)
    indsZm = (cX_mems < 0.0).nonzero()[0]
    indsZc = (cX_cells < 0.0).nonzero()[0]
    if len(indsZc) > 0:
        raise BetseSimUnstableException(
            "Network concentration of "
            + name
            + " in cells below zero! Your simulation has become unstable."
        )
    if len(indsZm) > 0:
        raise BetseSimUnstableException(
            "Network concentration of "
            + name
            + " on membrane below zero! Your simulation has become unstable."
        )
    indsZe = (cX_env_o < 0.0).nonzero()[0]
    if len(indsZe) > 0:
        print(name, c_bound)
        raise BetseSimUnstableException(
            "Network concentration of "
            + name
            + " in environment below zero! Your simulation has become unstable."
        )
    p._mover_observe("return", name, locals(), sim)
    return (cX_env_o, cX_cells, cX_mems, f_X_ED, fgj_X, fenvx, fenvy)


def update_Co(sim, cX_cell, cX_mem, cX_env, flux, cells, p, ignoreECM=True, update_at_mems=False):
    delta_cells = np.dot(cells.M_sum_mems, flux * cells.mem_sa) / cells.cell_vol
    if update_at_mems is False:
        cX_cell = cX_cell + delta_cells * p.dt
        cX_mem = cX_cell[cells.mem_to_cells]
    else:
        cX_mem += flux * (cells.mem_sa / (3 / 4 * cells.mem_vol)) * p.dt
        cX_cell = cX_cell + delta_cells * p.dt
    if p.is_ecm is True:
        delta_env = div_env(-flux, cells, p)
        cX_env = cX_env + delta_env * p.dt
    else:
        delta_env = -flux * (cells.mem_sa / p.vol_env)
        cX_env_o = cX_env + delta_env * p.dt
        cX_env = cX_env_o.mean()
    return (cX_cell, cX_mem, cX_env)


class _Molecule:
    def __init__(self, sim, cells, p):
        self.c_cello = None
        self.c_memo = None
        self.c_env = None
        self.z = None
        self.Dm = None
        self.Do = None
        self.c_bound = None
        self.Kgd = None
        self.use_pumping = None
        self.pumps_use_ATP = None
        self.pump_to_cell = None
        self.pump_max_val = None
        self.pump_Km = None
        self.use_gating_ligand = None
        self.gating_extracell = None
        self.gating_max_val = None
        self.gating_Hill_K = None
        self.gating_Hill_n = None
        self.gating_ion = None
        self.change_at_bounds = None
        self.change_bounds_start = None
        self.change_bounds_end = None
        self.change_bounds_rate = None
        self.change_bounds_target = None
        self.make_plots = None
        self.make_ani = None
        self.plot_autoscale = None
        self.plot_max = None
        self.plot_min = None
        self.r_production = None
        self.r_decay = None
        self.n_decay = None
        self.growth_activators_list = None
        self.growth_activators_Km = None
        self.growth_activators_n = None
        self.growth_inhibitors_list = None
        self.growth_inhibitors_Km = None
        self.growth_inhibitors_n = None
        self.ion_activators_list = None
        self.ion_activators_Km = None
        self.ion_activators_n = None
        self.ion_inhibitors_list = None
        self.ion_inhibitors_Km = None
        self.ion_inhibitors_n = None
        self.growth_targets_cell = cells.cell_i
        self.gating_mod = 1.0

    def transport(self, sim, cells, p):
        self.c_env, self.c_cells, self.cc_at_mem, self.f_mem, self.f_gj, self.fenvx, self.fenvy = (
            stb.molecule_mover(
                sim,
                self.c_env,
                self.c_cells,
                cells,
                p,
                z=self.z,
                Dm=self.Dm,
                Do=self.Do,
                Dgj=self.Dgj,
                c_bound=self.c_bound,
                ignoreECM=self.ignore_ECM_pump,
                smoothECM=False,
                ignoreTJ=self.ignoreTJ,
                ignoreGJ=self.ignoreGJ,
                Ftj=self.TJ_factor,
                rho=sim.rho_channel,
                cmems=self.cc_at_mem,
                time_dilation_factor=self.modify_time_factor,
                update_intra=self.update_intra_conc,
                name=self.name,
                transmem=self.transmem,
                mu_mem=self.Mu_mem,
                umt=self.u_mt,
            )
        )

    def update_intra(self, sim, cells, p):
        cav = self.c_cells[cells.mem_to_cells]
        cmi = self.cc_at_mem
        z = self.z
        Do = self.Do
        cp = (cav + cmi) / 2
        cg = (cmi - cav) / cells.R_rads
        if self.update_intra_conc is False:
            self.cc_at_mem = cav * 1
        elif self.update_intra_conc is True:
            alpha_motor = 0.0
            if self.transmem is False:
                if z != 0.0 or self.Mu_mem != 0.0:
                    En = (
                        sim.E_cell_x[cells.mem_to_cells] * cells.mem_vects_flat[:, 2]
                        + sim.E_cell_y[cells.mem_to_cells] * cells.mem_vects_flat[:, 3]
                    )
                else:
                    En = 0.0
                uflow = 0.0
            else:
                if z != 0.0 or self.Mu_mem != 0.0:
                    vex, vey = fd.gradient(
                        sim.v_env.reshape(cells.X.shape), cells.delta, cells.delta
                    )
                    _, _, En = stb.map_to_cells(-vex, -vey, cells, p, smoothing=1.0)
                else:
                    En = 0.0
                if p.fluid_flow is True:
                    _, _, uflow = stb.map_to_cells(
                        sim.u_env_x, sim.u_env_y, cells, p, smoothing=1.0
                    )
                    uflow[cells.bflags_mems] = 0.0
                else:
                    uflow = 0.0
            gamma = cells.mem_sa / (3 / 4 * cells.mem_vol)
            alpha_En_A = Do * p.q * z / (p.kb * sim.T) * En
            alpha_En_B = self.Mu_mem * En
            alpha_flow = uflow
            alpha_tot = alpha_motor + alpha_En_A + alpha_En_B + alpha_flow
            dt = p.dt * self.modify_time_factor
            self.cc_at_mem = (
                gamma * Do * dt * cav / cells.R_rads
                + gamma * alpha_tot * cav * dt / 2
                + self.cc_at_mem
            ) / (1 + gamma * Do * dt / cells.R_rads - gamma * alpha_tot * dt / 2)
            cflux = -Do * cg + alpha_tot * cp
            self.flux_intra = cflux * 1
        indsZ = (self.cc_at_mem < 0.0).nonzero()
        if len(indsZ[0]):
            raise BetseSimUnstableException(
                "Network concentration "
                + self.name
                + " on membrane below zero! Your simulation has become unstable."
            )

    def init_growth(self, phase):
        if (
            self.growth_profiles_list is not None
            and self.growth_profiles_list != "all"
            and (self.growth_profiles_list != "express")
        ):
            self.growth_targets_cell = []
            self.growth_targets_mem = []
            for profile in self.growth_profiles_list:
                targets_cell = phase.dyna.cell_target_inds[profile]
                self.growth_targets_cell.extend(targets_cell)
                targets_mem = phase.dyna.tissue_target_inds[profile]
                self.growth_targets_mem.extend(targets_mem)
        elif self.growth_profiles_list == "express":
            self.growth_targets_cell = phase.cells.cell_i
            self.growth_targets_mem = phase.cells.mem_i
            self.expr_map_cell = np.zeros(phase.sim.cdl)
            self.expr_map_mem = np.zeros(phase.sim.mdl)
            for region, val in phase.p.expression_data[self.name].items():
                tinds_mem = phase.dyna.tissue_target_inds[region]
                tinds_cell = phase.dyna.cell_target_inds[region]
                self.expr_map_mem[tinds_mem] = val
                self.expr_map_cell[tinds_cell] = val
            self.vmax = self.vmax * self.expr_map_cell
        else:
            self.growth_targets_cell = phase.cells.cell_i
            self.growth_targets_mem = phase.cells.mem_i


class _Network(feedback_source._LiteralNetwork):
    def run_loop(self, phase, t):
        cells = phase.cells
        p = phase.p
        sim = phase.sim
        gad_rates_o = []
        gad_targs = []
        init_rates = []
        gad_rates = []
        globalo = globals()
        localo = locals()
        for mol in self.molecules:
            obj = self.molecules[mol]
            obj.update_intra(sim, cells, p)
            self._observe_chem("molecule_intra", mol, sim)
            gad_rates_o.append(eval(self.molecules[mol].gad_eval_string, globalo, localo))
            gad_targs.append(self.molecules[mol].growth_targets_cell)
            init_rates.append(np.zeros(sim.cdl))
        for mat, trgs, rts in zip(init_rates, gad_targs, gad_rates_o):
            mat[trgs] = rts[trgs]
            gad_rates.append(mat)
        gad_rates = np.asarray(gad_rates)
        self.reaction_rates = np.asarray(
            [
                eval(self.reactions[rn].reaction_eval_string, globalo, localo)
                for rn in self.reactions
            ]
        )
        if len(self.reaction_rates) > 0:
            all_rates = np.vstack((gad_rates, self.reaction_rates))
        else:
            all_rates = gad_rates
        self.delta_conc = np.dot(self.reaction_matrix, all_rates)
        self._observe_rhs(gad_rates, self.reaction_rates, all_rates)
        self._observe_chem("rhs_ready", None, sim)
        if self.mit_enabled and len(self.reactions_mit) > 0:
            self.reaction_rates_mit = np.asarray(
                [
                    eval(self.reactions_mit[rn].reaction_eval_string, globalo, localo)
                    for rn in self.reactions_mit
                ]
            )
            self.delta_conc_mit = np.dot(self.reaction_matrix_mit, self.reaction_rates_mit)
        if len(self.reactions_env) > 0:
            self.reaction_rates_env = np.asarray(
                [
                    eval(self.reactions_env[rn].reaction_eval_string, globalo, localo)
                    for rn in self.reactions_env
                ]
            )
            self.delta_conc_env = np.dot(self.reaction_matrix_env, self.reaction_rates_env)
        else:
            self.delta_conc_env = None
        if self.delta_conc_env is not None:
            for name_env, deltae in zip(self.env_concs, self.delta_conc_env):
                conce = self.env_concs[name_env]
                self.env_concs[name_env] = conce + deltae * p.dt
        for ii, (name, deltac) in enumerate(zip(self.cell_concs, self.delta_conc)):
            conco = self.cell_concs[name]
            if name not in p.ions_dict:
                obj = self.molecules[name]
            else:
                obj = None
            self.cell_concs[name] = conco + deltac * p.dt
            self._observe_chem("chemical_commit", name, sim)
            if obj is not None:
                if obj.active_pumping:
                    obj.pump(sim, cells, p)
                if obj.ion_channel_gating:
                    obj.gating_mod = eval(obj.gating_mod_eval_string, globalo, localo)
                    obj.gating(sim, cells, p)
                if obj.change_bounds and phase.kind:
                    obj.update_boundary(t, p)
                if obj.cell_clamp:
                    obj.cell_clamp_method(t, p, cells)
                self._observe_chem("transport_before", name, sim)
                obj.transport(sim, cells, p)
                self._observe_chem("transport_after", name, sim)
                stb.no_negs(obj.c_cells)
                stb.no_negs(obj.c_env)
                if p.substances_affect_charge:
                    self.extra_rho_cells[:] += p.F * obj.c_cells * obj.z * obj.scale_factor
                    self.extra_J_mem[:] += (
                        -obj.z * obj.f_mem * p.F * obj.scale_factor
                        + obj.z * obj.f_gj * p.F * obj.scale_factor
                    )
                    if p.is_ecm:
                        self.extra_rho_env[:] += p.F * obj.c_env * obj.z * obj.scale_factor
                        self.extra_Jenv_x += obj.fenvx.ravel() * obj.z * p.F * obj.scale_factor
                        self.extra_Jenv_y += obj.fenvy.ravel() * obj.z * p.F * obj.scale_factor
            if self.mit_enabled and len(self.reactions_mit) > 0:
                concm = self.mit_concs[name]
                self.mit_concs[name] = concm + self.delta_conc_mit[ii] * p.dt
                stb.no_negs(self.mit_concs[name])
            if self.mit_enabled and obj is not None:
                self.extra_rho_mit[:] += p.F * obj.c_mit * obj.z
        self.energy_charge(sim)
        if p.substances_affect_charge:
            sim.extra_rho_cells = self.extra_rho_cells
            sim.extra_rho_env = self.extra_rho_env
            sim.extra_J_mem = self.extra_J_mem
            sim.extra_Jenv_x = self.extra_Jenv_x
            sim.extra_Jenv_y = self.extra_Jenv_y
        if self.mit_enabled:
            self.mit.extra_rho = self.extra_rho_mit[:]
            self.mit.update(sim, cells, p)


def no_negs(data):
    inds_nan = (np.isnan(data)).nonzero()
    inds_neg = (data < 0.0).nonzero()
    if len(inds_neg[0]) > 0:
        data[inds_neg] = 0.0
    if len(inds_nan[0]) > 0:
        raise BetseSimUnstableException(
            "Your simulation has become unstable. Please try a smaller time step,"
            "reduce gap junction radius, and/or reduce rate coefficients."
        )
    return data


stb = SimpleNamespace(molecule_mover=molecule_mover, no_negs=no_negs, map_to_cells=_outside_scope)
controls = feedback_source.controls
DYNAMIC = ("c_cells", "cc_at_mem", "c_env", "flux_intra", "f_mem", "f_gj", "fenvx", "fenvy")
BASE_FIELDS = set(DYNAMIC[:4])
PARAMETERS = {
    "z",
    "Dm",
    "Do",
    "Dgj",
    "c_bound",
    "TJ_factor",
    "ignoreTJ",
    "ignoreGJ",
    "ignore_ECM_pump",
    "update_intra_conc",
    "transmem",
    "modify_time_factor",
    "Mu_mem",
    "u_mt",
    "scale_factor",
    "active_pumping",
    "ion_channel_gating",
    "change_bounds",
    "cell_clamp",
}
GROWTH = {"enabled", "production_rate_mM_s", "decay_rate_per_s", "decay_max_per_s", "scale_factor"}


def _number(value, *, nonnegative=False, positive=False):
    return (
        type(value) in (int, float)
        and np.isfinite(value)
        and (not nonnegative or value >= 0)
        and (not positive or value > 0)
    )


def _dynamic(raw, n, m, *, initial=False):
    expected = BASE_FIELDS if initial else set(DYNAMIC) | {"present_fields"}
    if not isinstance(raw, dict) or set(raw) != expected:
        raise ValueError("Require all owned molecule arrays and cache-presence fields")
    values = {}
    for name in DYNAMIC:
        value = raw.get(name)
        if value is None:
            if name in BASE_FIELDS:
                raise ValueError("Missing owned molecule concentration/cache: " + name)
            values[name] = None
            continue
        shape = (n,) if name == "c_cells" else () if name in ("fenvx", "fenvy") else (m,)
        array = np.asarray(value, np.float64)
        if array.shape != shape or not np.isfinite(array).all():
            raise ValueError("Require finite shaped molecule state: " + name)
        if name in ("c_cells", "cc_at_mem", "c_env") and np.any(array < 0):
            raise ValueError("Published molecule state requires nonnegative concentrations")
        if name in ("fenvx", "fenvy"):
            if value != 0:
                raise ValueError("No-ECM environmental flux caches are the literal scalar zero")
            values[name] = value
        else:
            values[name] = ions.freeze(array)
    present = [name for name in DYNAMIC if values[name] is not None]
    if not initial and list(raw["present_fields"]) != present:
        raise ValueError("Changed source molecule cache presence")
    values["present_fields"] = tuple(present)
    return ions.freeze(values)


def validate(definition, ion_binding, current_binding, configured_temperature_K):
    required = {
        "owner",
        "reactions",
        "modulators",
        "initial_controls",
        "membrane_to_environment",
        "provenance",
        "molecules",
        "radius_m",
        "rho_channel",
    }
    if (
        not isinstance(definition, dict)
        or set(definition) != required
        or definition["owner"] != "molecules"
    ):
        raise ValueError("Require the distinct complete single-core molecule declaration")
    ordinary = {
        key: value
        for key, value in definition.items()
        if key not in ("molecules", "radius_m", "rho_channel")
    }
    ordinary["reactions"] = []
    feedback_source.validate(ordinary, ion_binding, current_binding, configured_temperature_K)
    n, m = len(ion_binding.cell_ids), len(ion_binding.membrane_ids)
    radius = np.asarray(definition["radius_m"], np.float64)
    rho = np.asarray(definition["rho_channel"], np.float64)
    if (
        radius.shape != (m,)
        or not np.isfinite(radius).all()
        or np.any(radius <= 0)
        or rho.shape != (m,)
        or not np.array_equal(rho, np.ones(m))
    ):
        raise ValueError(
            "Require owned positive membrane radii and the declared native rho_channel=1 scope"
        )
    rows = definition["molecules"]
    if (
        not isinstance(rows, list)
        or len(rows) != 2
        or {row.get("name") for row in rows} != {"X", "Y"}
    ):
        raise ValueError("First seam requires two real declared molecules X and Y")
    for row in rows:
        if (
            set(row) != {"name", "parameters", "growth", "initial", "provenance"}
            or row["name"] in ion_binding.ion_ids
            or not isinstance(row["provenance"], str)
            or not row["provenance"].strip()
        ):
            raise ValueError("Require separate molecular roles and provenance")
        params, growth = row["parameters"], row["growth"]
        if (
            not isinstance(params, dict)
            or set(params) != PARAMETERS
            or not isinstance(growth, dict)
            or set(growth) != GROWTH
        ):
            raise ValueError("Require complete molecule transport and growth parameters")
        if params["ignore_ECM_pump"] is not True:
            raise ValueError("Require the literal native ignore_ECM_pump=True initialization")
        flags = (
            "ignoreTJ",
            "ignoreGJ",
            "update_intra_conc",
            "transmem",
            "active_pumping",
            "ion_channel_gating",
            "change_bounds",
            "cell_clamp",
        )
        if any(type(params[name]) is not bool for name in flags) or any(
            params[name] for name in flags[2:]
        ):
            raise ValueError(
                "ECM, shell-field, motor, pumps, gating and event branches require separate state"
            )
        if (
            any(
                not _number(params[name], nonnegative=True)
                for name in ("Dm", "Do", "Dgj", "c_bound", "TJ_factor", "scale_factor")
            )
            or not _number(params["modify_time_factor"], positive=True)
            or not _number(params["z"])
            or abs(params["z"]) > 1
            or any(not _number(params[key]) or params[key] != 0.0 for key in ("Mu_mem", "u_mt"))
        ):
            raise ValueError("Invalid declared molecule transport parameters")
        if (
            type(growth["enabled"]) is not bool
            or any(
                not _number(growth[name], nonnegative=True)
                for name in ("production_rate_mM_s", "decay_rate_per_s", "decay_max_per_s")
            )
            or not _number(growth["scale_factor"], positive=True)
        ):
            raise ValueError("Require finite ordinary growth/decay parameters")
        _dynamic(row["initial"], n, m, initial=True)
    names = {row["name"]: row for row in rows}
    reactions = definition["reactions"]
    if not isinstance(reactions, list) or len(reactions) > 1:
        raise ValueError("First coupled seam has one bounded optional X to Y cell reaction")
    for row in reactions:
        keys = {
            "name",
            "reaction zone",
            "reactants",
            "products",
            "reactant multipliers",
            "product multipliers",
            "Km reactants",
            "Km products",
            "max rate",
            "standard free energy",
        }
        if (
            set(row) != keys
            or row["name"] != "X_to_Y"
            or row["reaction zone"] != "cell"
            or row["reactants"] != ["X"]
            or row["products"] != ["Y"]
            or row["reactant multipliers"] != [1.0]
            or row["product multipliers"] != [1.0]
            or row["standard free energy"] != "None"
            or not _number(row["max rate"], nonnegative=True)
            or any(
                not isinstance(row[key], list)
                or len(row[key]) != 1
                or not _number(row[key][0], positive=True)
                for key in ("Km reactants", "Km products")
            )
        ):
            raise ValueError("Require the explicitly irreversible native X to Y source expression")
        if any(
            names["X"]["parameters"][key] != names["Y"]["parameters"][key]
            for key in ("z", "scale_factor")
        ):
            raise ValueError(
                "Reaction conversion must preserve declared molecular charge weighting"
            )


def initial_cache(definition):
    rows = definition["molecules"]
    n, m = len(rows[0]["initial"]["c_cells"]), len(rows[0]["initial"]["cc_at_mem"])
    return ions.freeze(
        dict(
            present_fields=(),
            molecule_states={
                row["name"]: _dynamic(ions.data(row["initial"]), n, m, initial=True) for row in rows
            },
        )
    )


def snapshot(molecules):
    return {
        name: dict(
            {key: copy.deepcopy(getattr(obj, key, None)) for key in DYNAMIC},
            present_fields=tuple(key for key in DYNAMIC if hasattr(obj, key)),
        )
        for name, obj in molecules.items()
    }


class Concentrations(MutableMapping):
    def __init__(self, sim, molecules, ion_ids, ionic_attribute, molecular_attribute):
        self.sim, self.molecules, self.ion_ids = sim, molecules, tuple(ion_ids)
        self.ionic_attribute, self.molecular_attribute = ionic_attribute, molecular_attribute
        self.names = self.ion_ids + tuple(molecules)

    def __getitem__(self, key):
        return (
            getattr(self.sim, self.ionic_attribute)[self.ion_ids.index(key)]
            if key in self.ion_ids
            else getattr(self.molecules[key], self.molecular_attribute)
        )

    def __setitem__(self, key, value):
        if key in self.ion_ids:
            getattr(self.sim, self.ionic_attribute)[self.ion_ids.index(key)] = value
        else:
            setattr(self.molecules[key], self.molecular_attribute, value)

    def __delitem__(self, key):
        raise TypeError("Owned concentration axes cannot be deleted")

    def __iter__(self):
        return iter(self.names)

    def __len__(self):
        return len(self.names)


def _molecules(definition, incoming_cache, sim, cells, p):
    _require_immutable(incoming_cache)
    if (
        incoming_cache is None
        or "molecule_states" not in incoming_cache
        or set(incoming_cache["molecule_states"])
        != {row["name"] for row in definition["molecules"]}
    ):
        raise ValueError(
            "Require complete owned molecular state; no silent reset to initial values"
        )
    result = OrderedDict()
    for row in definition["molecules"]:
        obj = _Molecule(sim, cells, p)
        obj.name = row["name"]
        for key, value in row["parameters"].items():
            setattr(obj, key, value)
        growth = row["growth"]
        obj.simple_growth = growth["enabled"]
        obj.r_production = growth["production_rate_mM_s"]
        obj.r_decay = growth["decay_rate_per_s"]
        obj.decay_max = growth["decay_max_per_s"]
        obj.gad_scale_factor = growth["scale_factor"]
        obj.growth_profiles_list = "all" if obj.simple_growth else None
        obj.growth_mod_function_cells = np.ones(sim.cdl)
        for prefix in ("growth", "decay"):
            for sign in ("activators", "inhibitors"):
                for suffix in ("list", "Km", "n", "zone"):
                    setattr(obj, prefix + "_" + sign + "_" + suffix, None)
        obj.init_growth(SimpleNamespace(sim=sim, cells=cells, p=p))
        dynamic = _dynamic(ions.data(incoming_cache["molecule_states"][obj.name]), sim.cdl, sim.mdl)
        for key in dynamic["present_fields"]:
            setattr(obj, key, copy.deepcopy(dynamic[key]))
        result[obj.name] = obj
    return result


def _require_immutable(value):
    if isinstance(value, np.ndarray):
        if value.flags.writeable or not np.isfinite(value).all():
            raise ValueError("Require immutable finite owned molecular buffers")
    elif isinstance(value, Mapping):
        if not isinstance(value, MappingProxyType):
            raise ValueError("Require immutable owned molecular mappings")
        for item in value.values():
            _require_immutable(item)
    elif isinstance(value, (list, tuple)):
        if isinstance(value, list):
            raise ValueError("Require immutable owned molecular sequences")
        for item in value:
            _require_immutable(item)


def cache(net):
    values = ions.data(feedback_source.cache(net))
    values.update(
        molecule_states=snapshot(net.molecules),
        growth_expressions={name: obj.gad_eval_string for name, obj in net.molecules.items()},
    )
    return ions.freeze(values)


def checked_cache(raw, definition):
    n = len(definition["molecules"][0]["initial"]["c_cells"])
    m = len(definition["radius_m"])
    if set(raw["molecule_states"]) != {row["name"] for row in definition["molecules"]}:
        raise ValueError("Changed owned molecular axis")
    for value in raw["molecule_states"].values():
        _dynamic(ions.data(value), n, m)
    return ions.freeze(raw)


def prepare(
    arrays, *, ion_ids, parameters, definition, incoming_controls, incoming_cache, phase_kind
):
    base_definition = {
        key: value
        for key, value in definition.items()
        if key not in ("molecules", "radius_m", "rho_channel")
    }
    base_definition["reactions"] = []
    original, sim, cells, p, phase = feedback_source.prepare(
        arrays,
        ion_ids=ion_ids,
        parameters=parameters,
        definition=base_definition,
        incoming_controls=incoming_controls,
        incoming_cache=incoming_cache,
        phase_kind=phase_kind,
    )
    g = parameters["geometry"]
    cells.mem_to_cells = np.asarray(g["owner"], np.int64)
    cells.nn_i = np.asarray(g["partner"], np.int64)
    cells.bflags_mems = np.asarray(g["boundary"], bool)
    cells.mem_sa = np.asarray(g["membrane_area_m2"], np.float64)
    cells.cell_vol = np.asarray(g["cell_volume_m3"], np.float64)
    cells.M_sum_mems = np.asarray(g["owner_sum"], np.float64)
    cells.gj_len = np.asarray(g["gap_length_m"], np.float64)
    cells.R_rads = np.asarray(definition["radius_m"], np.float64)
    sim.vgj, sim.gjopen = arrays[6], arrays[9]
    sim.rho_channel = np.asarray(definition["rho_channel"], np.float64).copy()
    p.T, p.tm = parameters["configured_temperature_K"], parameters["membrane_thickness_m"]
    p.vol_env, p.cluster_open = parameters["bath_volume_m3"], parameters["cluster_open"]
    net = _Network()
    vars(net).update(vars(original))
    net.molecules = _molecules(definition, incoming_cache, sim, cells, p)
    for attr, ionic, molecular in (
        ("cell_concs", "cc_cells", "c_cells"),
        ("mem_concs", "cc_at_mem", "cc_at_mem"),
        ("env_concs", "cc_env", "c_env"),
    ):
        setattr(net, attr, Concentrations(sim, net.molecules, ion_ids, ionic, molecular))
    net.zmol.update({name: obj.z for name, obj in net.molecules.items()})
    net.read_reactions(ions.data(definition["reactions"]), sim, cells, p)
    net.write_reactions()
    net.write_growth_and_decay()
    net.create_reaction_matrix()
    net.molecule_frames, net.mover_frames, net.rhs = [], [], {}

    def observe_chem(stage, species, actual):
        net.molecule_frames.append(
            ions.freeze(
                dict(
                    stage=stage,
                    species=species,
                    molecule_states=snapshot(net.molecules),
                    cell_concs=actual.cc_cells.copy(),
                    mem_concs=actual.cc_at_mem.copy(),
                    vm=actual.vm.copy(),
                    vgj=actual.vgj.copy(),
                    cache=cache(net),
                )
            )
        )

    def observe_mover(stage, name, local, actual):
        fields = (
            "cX_env_o",
            "cX_cells",
            "cX_mems",
            "f_X_ED",
            "fgj_X",
            "fenvx",
            "fenvy",
            "delta_cco",
            "Dm_vect",
        )
        net.mover_frames.append(
            ions.freeze(
                dict(
                    stage=stage,
                    species=name,
                    fields={key: copy.deepcopy(local.get(key)) for key in fields},
                    vm=actual.vm.copy(),
                    vgj=actual.vgj.copy(),
                )
            )
        )

    net._observe_chem, p._mover_observe = observe_chem, observe_mover
    net._observe_rhs = lambda growth, reaction, combined: net.rhs.update(
        growth_rates=np.array(growth, copy=True),
        reaction_rates=np.array(reaction, copy=True),
        all_rates=np.array(combined, copy=True),
    )
    return net, sim, cells, p, phase
