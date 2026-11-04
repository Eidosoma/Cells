# Copyright 2014-2025 Alexis Pietak & Cecil Curry; see licenses/BETSE.txt.
# ruff: noqa: F821, F841, E501, B905, N802, N803, N806
"""Literal ordinary INIT calendar and transport bodies; no live authority.

Only definition decorators/annotations are omitted. Execution uses the exact
whole-native-module compiled code acquired from the actual retained Simulator;
these bodies independently pin its complete AST, including optional branches.
"""

SOURCE_PINS = {
    "betse/science/sim.py": "02a9a049b5daa5cf6bc543332aa89437f58a4700ed31310abc3ee13697f22d43",
    "betse/science/sim_toolbox.py": "d94b50e8c0fdcee28b6b301c493ffa5aaf42b18e87ea4750483e164a3bdcacec",
    "betse/science/math/finitediff.py": "8186bc5c013db8aec224f6ed9b0892e944b2ddd4247f135ff19caf7419478350",
    "betse/science/channels/gap_junction.py": "17b4bd95ea8801c0907a8363d71a194d14292df5f25509f9f353397f91d39bbd",
    "betse/util/type/contexts.py": "66fad70e4b3458f3d24e66c93c741628112be7ba591d745e034529caaa8da8ef",
}

ROSTER = (
    ("_plot_loop", "betse/science/sim.py", "Simulator", 2403, 2503),
    ("_run_sim_core_loop", "betse/science/sim.py", "Simulator", 1132, 1390),
    ("update_gj", "betse/science/sim.py", "Simulator", 2162, 2206),
    ("update_ecm", "betse/science/sim.py", "Simulator", 2209, 2254),
    ("update_intra", "betse/science/sim.py", "Simulator", 2257, 2310),
    ("update_all_concs", "betse/science/sim.py", "Simulator", 2086, 2111),
    ("ca_handler", "betse/science/sim.py", "Simulator", 2126, 2159),
    ("write2storage", "betse/science/sim.py", "Simulator", 1789, 1877),
    ("_log_solver_time_estimate", "betse/science/sim.py", "Simulator", 1645, 1677),
    ("electroflux", "betse/science/sim_toolbox.py", None, 18, 69),
    ("pumpNaKATP", "betse/science/sim_toolbox.py", None, 71, 122),
    ("pumpCaATP", "betse/science/sim_toolbox.py", None, 124, 182),
    ("nernst_planck_flux", "betse/science/sim_toolbox.py", None, 385, 413),
    ("update_Co", "betse/science/sim_toolbox.py", None, 1155, 1207),
    ("div_env", "betse/science/sim_toolbox.py", None, 1209, 1234),
    ("no_negs", "betse/science/sim_toolbox.py", None, 475, 503),
    ("check_v", "betse/science/sim_toolbox.py", None, 332, 344),
    ("integrator", "betse/science/math/finitediff.py", None, 1479, 1512),
    ("run", "betse/science/channels/gap_junction.py", "Gap_Junction", 53, 75),
    ("noop_context", "betse/util/type/contexts.py", None, 18, 23),
)


class FirstStepKernel:
    def _plot_loop(self, phase):
        """
        Display and/or save an animation during solving if requested *and*
        calculate data common to solving both with and without extracellular
        spaces.

        Parameters
        --------
        phase : SimPhase
            Current simulation phase.

        Returns
        --------
        (ndarray, set, ContextManager)
            3-tuple ``(time_steps, time_steps_sampled, solver_context)`` where:

            * ``time_steps`` is a one-dimensional Numpy array defining the
              time-steps vector for the current phase.
            * ``time_steps_sampled`` is the subset of the ``time_steps`` array
              whose elements are **sampled time steps** (i.e., time steps at
              which to sample data, substantially reducing data storage). In
              particular, the length of this set is exactly equal to:

              * The maximum progress value to be passed to the
                :meth:`SimCallbacksAPI.progress_ranged` callback.
              * The number of frames exported from each animation.

            * ``solver_context`` is the context manager intended to wrap the
              core time loop for this phase. Specifically, this is either:
              * If the configuration for this phase enables non-blocking display
                and/or saving of one or more in-phase exports (e.g., plots), the
                context manager doing so.
              * Else, the empty context manager doing nothing.
        """
        if phase.kind is SimPhaseKind.INIT:
            phase_verb = "Initializing"
            phase_noun = "initialization"
            phase_time_step_count = phase.p.init_tsteps
        else:
            phase_verb = "Simulating"
            phase_noun = "simulation"
            phase_time_step_count = phase.p.sim_tsteps
        phase_time_len = phase_time_step_count * phase.p.dt
        time_steps = np.linspace(0, phase_time_len, phase_time_step_count)
        time_steps_sampled = set()
        i = 0
        while i < len(time_steps) - phase.p.t_resample:
            i += phase.p.t_resample
            i = int(i)
            time_steps_sampled.add(time_steps[i])
        logs.log_info(
            "Your %s is running from 0 to %.2f s of in-world time in %d time steps (%d sampled).",
            phase_noun,
            phase_time_len,
            len(time_steps),
            len(time_steps_sampled),
        )
        solver_context = None
        if phase.p.anim.is_while_sim:
            phase_deformed = SimPhase(kind=phase.kind, sim=phase.sim, cells=self.cellso, p=phase.p)
            solver_context = AnimCellsWhileSolving(
                phase=phase_deformed,
                conf=phase.p.anim.anim_while_sim,
                time_step_count=len(time_steps_sampled),
                kind="Vmem",
                figure_title="Vmem while {}".format(phase_verb),
                colorbar_title="Voltage [mV]",
            )
        else:
            solver_context = noop_context()
        return (time_steps, time_steps_sampled, solver_context)

    def _run_sim_core_loop(self, phase, time_steps, time_steps_sampled, anim_cells):
        """
        Drive the time loop for the current simulation phase, including:

        * Gap-junction connections.
        * Calls to all dynamic channels and entities (when simulating).

        Parameters
        --------
        phase : SimPhase
            Current simulation phase.
        time_steps : ndarray
            One-dimensional Numpy array defining the time-steps vector for the
            current phase.
        time_steps_sampled : set
            Subset of the ``time_steps`` array whose elements are **sampled
            time steps** (i.e., time step at which to sample data,
            substantially reducing data storage). In particular, the length of
            this set governs the number of frames in each exported animation.
        anim_cells : (AnimCellsWhileSolving, NoneType)
            A mid-simulation animation of cell voltage as a function of time if
            enabled by this configuration *or* ``None`` otherwise.
        """
        p = phase.p
        cells = phase.cells
        is_time_step_first = True
        for t in time_steps:
            if is_time_step_first:
                loop_measure = time.time()
            self.fluxes_mem.fill(0)
            self.fluxes_gj.fill(0)
            if p.is_ecm:
                self.fluxes_env_x = np.zeros((len(self.zs), self.edl))
                self.fluxes_env_y = np.zeros((len(self.zs), self.edl))
            if phase.kind is SimPhaseKind.SIM:
                phase.dyna.fire_events(phase=phase, t=t)
            if p.alpha_NaK == 0.0:
                self.rate_NaKATP = np.zeros(self.mdl)
            if p.alpha_NaK > 0.0:
                if p.is_ecm:
                    fNa_NaK, fK_NaK, self.rate_NaKATP = stb.pumpNaKATP(
                        self.cc_at_mem[self.iNa],
                        self.cc_env[self.iNa][cells.map_mem2ecm],
                        self.cc_at_mem[self.iK],
                        self.cc_env[self.iK][cells.map_mem2ecm],
                        self.vm,
                        self.T,
                        p,
                        self.NaKATP_block,
                        met=self.met_concs,
                    )
                else:
                    fNa_NaK, fK_NaK, self.rate_NaKATP = stb.pumpNaKATP(
                        self.cc_at_mem[self.iNa],
                        self.cc_env[self.iNa],
                        self.cc_at_mem[self.iK],
                        self.cc_env[self.iK],
                        self.vm,
                        self.T,
                        p,
                        self.NaKATP_block,
                        met=self.met_concs,
                    )
                fNa_NaK = self.rho_pump * fNa_NaK
                fK_NaK = self.rho_pump * fK_NaK
                if p.cluster_open is False:
                    fNa_NaK[cells.bflags_mems] = 0
                    fK_NaK[cells.bflags_mems] = 0
                self.fluxes_mem[self.iNa] += fNa_NaK
                self.fluxes_mem[self.iK] += fK_NaK
            for i in self.movingIons:
                IdM = np.ones(self.mdl)
                if p.is_ecm:
                    f_ED = stb.electroflux(
                        self.cc_env[i][cells.map_mem2ecm],
                        self.cc_at_mem[i],
                        self.Dm_cells[i],
                        IdM * p.tm,
                        self.zs[i] * IdM,
                        self.vm,
                        self.T,
                        p,
                        rho=self.rho_channel,
                    )
                else:
                    f_ED = stb.electroflux(
                        self.cc_env[i],
                        self.cc_at_mem[i],
                        self.Dm_cells[i],
                        IdM * p.tm,
                        self.zs[i] * IdM,
                        self.vm,
                        self.T,
                        p,
                        rho=self.rho_channel,
                    )
                if not p.cluster_open:
                    f_ED[cells.bflags_mems] = 0
                self.fluxes_mem[i] += f_ED
                self.update_gj(cells, p, t, i)
                if p.is_ecm:
                    self.update_ecm(cells, p, t, i)
                self.update_intra(cells, p, i)
            if p.ions_dict["Ca"] == 1:
                self.ca_handler(cells, p)
            if p.molecules_enabled:
                self.molecules.core.clear_run_loop(self)
                if self.molecules.transporters:
                    self.molecules.core.run_loop_transporters(t, self, cells, p)
                if self.molecules.channels:
                    self.molecules.core.run_loop_channels(phase)
                if self.molecules.modulators:
                    self.molecules.core.run_loop_modulators(self, cells, p)
                self.molecules.core.run_loop(phase=phase, t=t)
            if p.grn_enabled:
                self.grn.core.clear_run_loop(self)
                if self.grn.transporters:
                    self.grn.core.run_loop_transporters(t, self, cells, p)
                if self.grn.channels:
                    self.grn.core.run_loop_channels(phase)
                if self.grn.modulators:
                    self.grn.core.run_loop_modulators(self, cells, p)
                self.grn.core.run_loop(phase=phase, t=t)
            if p.dynamic_noise == 1 and p.ions_dict["P"] == 1 and (phase.kind is SimPhaseKind.SIM):
                self.protein_noise_flux = p.dynamic_noise_level * (np.random.random(self.mdl) - 0.5)
                self.cc_cells[self.iP], self.cc_at_mem[self.iP], self.cc_env[self.iP] = (
                    stb.update_Co(
                        self,
                        self.cc_cells[self.iP],
                        self.cc_at_mem[self.iP],
                        self.cc_env[self.iP],
                        self.protein_noise_flux,
                        cells,
                        p,
                        ignoreECM=False,
                    )
                )
            if p.deform_osmo:
                osmotic_P(self, cells, p)
            if p.fluid_flow:
                getFlow(self, cells, p)
            if p.deformation:
                if p.td_deform:
                    timeDeform(self, cells, t, p)
                else:
                    getDeformation(self, cells, t, p)
            self.update_all_concs(cells, p)
            self.update_V(cells, p)
            stb.check_v(self.vm)
            if t in time_steps_sampled:
                phase.callbacks.progressed_next()
                self.write2storage(t, cells, p)
                if anim_cells is not None:
                    anim_cells.plot_frame(time_step=-1)
            if is_time_step_first:
                is_time_step_first = False
                self._log_solver_time_estimate(phase=phase, step_first_time=loop_measure)

    def update_gj(self, cells, p, t, i):
        self.vgj = self.vm[cells.nn_i] - self.vm[cells.mem_i]
        self.Egj = -self.vgj / cells.gj_len
        self.E_gj_x = self.Egj * cells.mem_vects_flat[:, 2]
        self.E_gj_y = self.Egj * cells.mem_vects_flat[:, 3]
        if p.v_sensitive_gj is True:
            self.gj_funk.run(self, cells, p)
        else:
            self.gjopen = self.gj_block * np.ones(len(cells.mem_i)) * cells.gj_default_weights
        conc_mem = self.cc_at_mem[i]
        fgj_X = stb.electroflux(
            conc_mem[cells.mem_i],
            conc_mem[cells.nn_i],
            self.D_gj[i] * p.gj_surface * self.gjopen,
            cells.gj_len * np.ones(self.mdl),
            self.zs[i] * np.ones(self.mdl),
            self.vgj,
            p.T,
            p,
            rho=1,
        )
        fgj_X[cells.bflags_mems] = 0.0
        self.fluxes_gj[i] = self.fluxes_gj[i] + fgj_X

    def update_ecm(self, cells, p, t, i):
        cenv = self.cc_env[i]
        cenv = cenv.reshape(cells.X.shape)
        cenv[:, 0] = self.c_env_bound[i]
        cenv[:, -1] = self.c_env_bound[i]
        cenv[0, :] = self.c_env_bound[i]
        cenv[-1, :] = self.c_env_bound[i]
        gcx, gcy = fd.gradient(cenv, cells.delta)
        if p.fluid_flow is True:
            ux = self.u_env_x
            uy = self.u_env_y
        else:
            ux = np.zeros(cells.X.shape)
            uy = np.zeros(cells.X.shape)
        denv = self.D_env[i].reshape(cells.X.shape) * self.TJ_modulator[i].reshape(cells.X.shape)
        fx, fy = stb.nernst_planck_flux(
            cenv, gcx, gcy, -self.E_env_x, -self.E_env_y, ux, uy, denv, self.zs[i], self.T, p
        )
        self.fluxes_env_x[i] = fx.ravel()
        self.fluxes_env_y[i] = fy.ravel()
        div_fa = fd.divergence(-fx, -fy, cells.delta, cells.delta)
        cenv = cenv + div_fa * p.dt
        if p.sharpness < 1.0:
            cenv = fd.integrator(cenv, sharp=p.sharpness)
        self.cc_env[i] = cenv.ravel()

    def update_intra(self, cells, p, i):
        cav = self.cc_cells[i][cells.mem_to_cells]
        self.cc_at_mem[i] = cav * 1

    def update_all_concs(self, cells, p):
        """
        Update all concentrations in all cells via membrane fluxes.
        """
        for i in self.movingIons:
            f_mem_i = self.fluxes_mem[i]
            f_gj_i = self.fluxes_gj[i]
            self.cc_cells[i], self.cc_at_mem[i], self.cc_env[i] = stb.update_Co(
                self,
                self.cc_cells[i],
                self.cc_at_mem[i],
                self.cc_env[i],
                f_mem_i,
                cells,
                p,
                ignoreECM=False,
            )
            delta_cgj = np.dot(cells.M_sum_mems, -f_gj_i * cells.mem_sa) / cells.cell_vol
            self.cc_cells[i] += p.dt * delta_cgj
            stb.no_negs(self.cc_cells[i])

    def ca_handler(self, cells, p):
        if p.alpha_Ca > 0.0:
            if p.is_ecm:
                f_CaATP = stb.pumpCaATP(
                    self.cc_at_mem[self.iCa],
                    self.cc_env[self.iCa][cells.map_mem2ecm],
                    self.vm,
                    self.T,
                    p,
                    self.CaATP_block,
                    met=self.met_concs,
                )
                f_CaATP = self.rho_pump * f_CaATP
            else:
                f_CaATP = stb.pumpCaATP(
                    self.cc_at_mem[self.iCa],
                    self.cc_env[self.iCa],
                    self.vm,
                    self.T,
                    p,
                    self.CaATP_block,
                    met=self.met_concs,
                )
            self.rate_CaATP = f_CaATP
            if p.cluster_open is False:
                f_CaATP[cells.bflags_mems] = 0
            self.fluxes_mem[self.iCa] += self.rho_pump * f_CaATP
        if p.Ca_dyn == 1:
            self.endo_retic.update(self, cells, p)

    def write2storage(self, t, cells, p):
        """
        Append each multidimensional Numpy array covering all time steps (e.g.,
        :attr:`cc_env_time`) with the corresponding Numpy array of fewer
        dimensions specific to the passed time step (e.g., :attr:`cc_env`).
        """
        if p.GHK_calc:
            stb.ghk_calculator(self, cells, p)
            self.vm_GHK_time.append(self.vm_GHK)
        self.efield_gj_x_time.append(self.E_gj_x * 1)
        self.efield_gj_y_time.append(self.E_gj_y * 1)
        concs = np.copy(self.cc_cells)
        self.cc_time.append(concs)
        concs = None
        envsc = np.copy(self.cc_env)
        self.cc_env_time.append(envsc)
        envsc = None
        ddc = np.copy(self.Dm_cells)
        ddc.tolist()
        self.dd_time.append(ddc)
        ddc = None
        self.I_cell_x_time.append(self.J_cell_x * 1)
        self.I_cell_y_time.append(self.J_cell_y * 1)
        self.I_mem_time.append(self.I_mem * 1)
        self.vm_time.append(self.vm * 1)
        self.rho_cells_time.append(self.rho_cells * 1)
        self.rate_NaKATP_time.append(self.rate_NaKATP * 1)
        self.P_cells_time.append(self.P_cells)
        self.venv_time.append(self.v_env * 1)
        if p.deform_osmo:
            self.osmo_P_delta_time.append(self.osmo_P_delta)
        if p.deformation:
            implement_deform_timestep(self, self.cellso, t, p)
            self.dx_cell_time.append(self.d_cells_x * 1)
            self.dy_cell_time.append(self.d_cells_y * 1)
        if p.fluid_flow:
            self.u_cells_x_time.append(self.u_cells_x * 1)
            self.u_cells_y_time.append(self.u_cells_y * 1)
        self.gjopen_time.append(self.gjopen * 1)
        self.time.append(t)
        if p.molecules_enabled:
            self.molecules.core.write_data(self, cells, p)
            self.molecules.core.report(self, p)
        if p.grn_enabled:
            self.grn.core.write_data(self, cells, p)
            self.grn.core.report(self, p)
        if p.Ca_dyn == 1 and p.ions_dict["Ca"] == 1:
            self.endo_retic.write_cache(self)
        self.I_tot_x_time.append(self.J_env_x * 1)
        self.I_tot_y_time.append(self.J_env_y * 1)
        if p.is_ecm:
            self.efield_ecm_x_time.append(self.E_env_x * 1)
            self.efield_ecm_y_time.append(self.E_env_y * 1)
            if p.fluid_flow:
                self.u_env_x_time.append(self.u_env_x * 1)
                self.u_env_y_time.append(self.u_env_y * 1)
        self.vm_ave_time.append(self.vm_ave)

    def _log_solver_time_estimate(self, phase, step_first_time):
        """
        Log an informational (i.e., with log level ``INFO``) estimate of the
        time required to compute the passed simulation phase.

        Parameters
        --------
        phase : SimPhase
            Current simulation phase.
        step_first_time : float
            Timestamp in fractional seconds at which the current solver began
            computing this phase.
        """
        step_first_duration = time.time() - step_first_time
        steps_total = phase.p.init_tsteps if phase.kind is SimPhaseKind.INIT else phase.p.sim_tsteps
        time_estimate = round(step_first_duration * steps_total, 2)
        logs.log_info("This run should take approximately %fs to compute...", time_estimate)


class GapJunctionKernel:
    def run(self, sim, cells, p):
        V1 = 1000.0 * np.abs(sim.vgj)
        self.alpha = self.lamb * np.exp(-self.A1 * (V1 - p.gj_vthresh))
        beta = self.lamb * np.exp(self.A2 * (V1 - p.gj_vthresh))
        self.beta = beta / (1 + 50 * beta)
        dt = p.dt * 1000.0
        sim.gjopen = (sim.gjopen + dt * (self.alpha + self.beta * p.gj_min)) / (
            1 + self.alpha * dt + self.beta * dt
        )
        sim.gjopen = sim.gj_block * sim.gjopen


def electroflux(cA, cB, Dc, d, zc, vBA, T, p, rho=1):
    """
    Electro-diffusion between two connected volumes. Note for cell work, 'b' is
    'inside', 'a' is outside, with a positive flux moving from a to b. The
    voltage is defined as Vb - Va (Vba), which is equivalent to Vmem.

    This function defaults to regular diffusion if Vba == 0.0.

    This function takes numpy matrix values as input. All inputs must be
    matrices of the same shape.

    This is the Goldman Flux/Current Equation (not to be confused with the
    Goldman Equation). Note: the Nernst-Planck equation has been trialed in
    place of this, and it does not reproduce proper reversal potentials.

    Parameters
    ----------
    cA          concentration in region A [mol/m3] (out)
    cB          concentration in region B [mol/m3] (in)
    Dc          Diffusion constant of c  [m2/s]
    d           Distance between region A and region B [m]
    zc          valence of ionic species c
    vBA         voltage difference between region B (in) and A (out) = Vmem
    p           an instance of the Parameters class

    Returns
    --------
    flux        Chemical flux magnitude between region A and B [mol/s]

    """
    FLOAT_NONCE = 1e-25
    vBA += FLOAT_NONCE
    zc += FLOAT_NONCE
    alpha = zc * vBA * p.F / (p.R * T)
    exp_alpha = np.exp(-alpha)
    deno = -np.expm1(-alpha)
    flux = -(Dc * alpha / d) * ((cB - cA * exp_alpha) / deno) * rho
    return flux


def pumpNaKATP(cNai, cNao, cKi, cKo, Vm, T, p, block, met=None):
    """
    Parameters
    ----------
    cNai            Concentration of Na+ inside the cell
    cNao            Concentration of Na+ outside the cell
    cKi             Concentration of K+ inside the cell
    cKo             Concentration of K+ outside the cell
    Vm              Voltage across cell membrane [V]
    p               An instance of Parameters object

    met             A "metabolism" vector containing concentrations of ATP, ADP and Pi


    Returns
    -------
    f_Na            Na+ flux (into cell +)
    f_K             K+ flux (into cell +)
    """
    deltaGATP_o = p.deltaGATP
    cATP = p.cATP
    cADP = p.cADP
    cPi = p.cPi
    Qnumo = cADP * 0.001 * (cPi * 0.001) * (cNao * 0.001) ** 3 * (cKi * 0.001) ** 2
    Qdenomo = cATP * 0.001 * (cNai * 0.001) ** 3 * (cKo * 0.001) ** 2
    inds_Z = (Qdenomo == 0.0).nonzero()
    Qdenomo[inds_Z] = 1e-15
    Q = Qnumo / Qdenomo
    Keq = np.exp(-(deltaGATP_o / (p.R * T) - p.F * Vm / (p.R * T)))
    numo_E = (cNai / p.KmNK_Na) ** 3 * (cKo / p.KmNK_K) ** 2 * (cATP / p.KmNK_ATP)
    denomo_E = (1 + (cNai / p.KmNK_Na) ** 3) * (1 + (cKo / p.KmNK_K) ** 2) * (1 + cATP / p.KmNK_ATP)
    fwd_co = numo_E / denomo_E
    f_Na = -3 * block * p.alpha_NaK * fwd_co * (1 - Q / Keq)
    f_K = -(2 / 3) * f_Na
    return (f_Na, f_K, -f_Na)


def pumpCaATP(cCai, cCao, Vm, T, p, block, met=None):
    """
    Parameters
    ----------
    cCai            Concentration of Ca2+ inside the cell
    cCao            Concentration of Ca2+ outside the cell
    voli            Volume of the cell [m3]
    volo            Volume outside the cell [m3]
    Vm              Voltage across cell membrane [V]
    p               An instance of Parameters object


    Returns
    -------
    cCai2           Updated Ca2+ inside cell
    cCao2           Updated Ca2+ outside cell
    f_Ca            Ca2+ flux (into cell +)
    """
    deltaGATP_o = p.deltaGATP
    no_negs(cCai)
    no_negs(cCao)
    cATP = p.cATP
    cADP = p.cADP
    cPi = p.cPi
    Qnumo = cADP * cPi * cCao
    Qdenomo = cATP * cCai
    inds_Z = (Qdenomo == 0.0).nonzero()
    Qdenomo[inds_Z] = 1e-16
    Q = Qnumo / Qdenomo
    Keq = np.exp(-(deltaGATP_o / (p.R * T) - 2 * (p.F * Vm / (p.R * T))))
    numo_E = cCai / p.KmCa_Ca * (cATP / p.KmCa_ATP)
    denomo_E = (1 + cCai / p.KmCa_Ca) * (1 + cATP / p.KmCa_ATP)
    frwd = numo_E / denomo_E
    numo_Eb = cCao / p.KmCa_Ca
    denomo_Eb = 1 + cCao / p.KmCa_Ca
    bkwrd = numo_Eb / denomo_Eb
    f_Ca = -p.alpha_Ca * frwd * (1 - Q / Keq)
    return f_Ca


def nernst_planck_flux(c, gcx, gcy, gvx, gvy, ux, uy, D, z, T, p, mu=0.0):
    """
     Calculate the flux component of the Nernst-Planck equation

     Parameters
     ------------

    c:     concentration
    gcx:   concentration gradient, x component
    gcy:   concentration gradient, y component
    gvx:   voltage gradient, x component
    gvy:   voltage gradient, y component
    ux:    fluid velocity, x component
    uy:    fluid velocity, y component
    D:     diffusion constant, D
    z:     ion charge
    T:     temperature
    p:     parameters object

    Returns
    --------
    fx, fx        mass flux in x and y directions
    """
    alpha = D * z * p.q / (p.kb * T)
    fx = -D * gcx - alpha * gvx * c + ux * c - mu * c * gvx
    fy = -D * gcy - alpha * gvy * c + uy * c - mu * c * gvy
    return (fx, fy)


def update_Co(sim, cX_cell, cX_mem, cX_env, flux, cells, p, ignoreECM=True, update_at_mems=False):
    """

    General updater for a concentration defined on
    cells and in environment.

    Parameters
    --------------
    cX_cell     Concentration inside cell defined on cell centres [mol/m3]
    cX_env      Concentration in extracellular spaces [mol/m3]
    flux        Flux of X, where into cell is + and component is normal to membranes  [mol/m2 s]
    cells       Instance of Cells
    p           Instance of Parameters

    Returns
    --------------
    cX_cell     Updated concentration in cell [mol/m3]
    cX_env      Updated concentration in environment [mol/m3]

    """
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


def div_env(flux, cells, p):
    """
    Calculates the divergence of the normal net flux component defined on a set of cell membranes
    with respect to the environmental grid spaces.

    :param flux:
    :param cells:
    :return:
    """
    if p.fast_update_ecm:
        flux_env = np.zeros(len(cells.xypts))
        flux_env[cells.map_mem2ecm] = flux
        delta_env = flux_env * cells.memSa_per_envSquare / cells.ecm_vol
    else:
        delta_env = np.dot(cells.M_divmap_mem2ecm, flux) / (p.cell_height * cells.delta**2)
    return delta_env


def no_negs(data):
    """
    This function screens an (concentration) array to
    ensure there are no NaNs and no negative values,
    crashing with an instability message if it finds any.
    """
    inds_nan = np.isnan(data).nonzero()
    inds_neg = (data < 0.0).nonzero()
    if len(inds_neg[0]) > 0:
        data[inds_neg] = 0.0
    if len(inds_nan[0]) > 0:
        raise BetseSimUnstableException(
            "Your simulation has become unstable. Please try a smaller time step,reduce gap junction radius, and/or reduce rate coefficients."
        )
    return data


def check_v(vm):
    """
    Does a quick check on Vmem values
    and displays error warning or exception if the value
    indicates the simulation is unstable.
    """
    isnans = np.isnan(vm)
    if isnans.any():
        raise BetseSimUnstableException(
            "Your simulation has become unstable. Please try a smaller time step,reduce gap junction radius, and/or reduce pump rate coefficients."
        )


def integrator(P, sharp=0.5):
    """
    Averages nearest neighbours of the environmental array with a weighting
    given by the "sharp" option.

    P: some 2D matrix
    sharp: weighting of the neigbouring averages; 0.5 is standard finite volume smoothing; 1.0 is no smoothing

    Thanks Sess!

    """
    F = np.zeros(P.shape)
    eP = P[:, 1:]
    wP = P[:, 0:-1]
    nP = P[1:, :]
    sP = P[0:-1, :]
    sides = (1 - sharp) / 4
    F[:, :] = sharp * P
    F[0:-1, :] += sides * nP
    F[1:, :] += sides * sP
    F[:, 0:-1] += sides * eP
    F[:, 1:] += sides * wP
    F[:, 0] = P[:, 0]
    F[:, -1] = P[:, -1]
    F[0, :] = P[0, :]
    F[-1, :] = P[-1, :]
    return F


def noop_context():
    """
    Empty context manager exiting immediately after being entered.
    """
    yield


# Exact caller statements 1049-1114; stop before _pickle_phase.
class SetupKernel:
    def after_update_V(self, phase):
        time_steps, time_steps_sampled, solver_context = self._plot_loop(phase)
        phase.callbacks.progress_ranged(progress_max=len(time_steps_sampled))
        exception_instability = None
        try:
            if phase.p.solver_type is SolverType.FULL:
                solver_label = "Full BETSE simulator"
                solver_method = self._run_sim_core_loop
            elif phase.p.solver_type is SolverType.FAST:
                solver_label = "Fast (equivalent circuit) simulator"
                solver_method = self._run_fast_sim_core_loop
            else:
                raise BetseSimException(
                    'Solver type "{}" unrecognized.'.format(phase.p.solver_type)
                )
            logs.log_info("Solver: %s in use.", solver_label)
            with solver_context:
                solver_method(
                    phase=phase,
                    time_steps=time_steps,
                    time_steps_sampled=time_steps_sampled,
                    anim_cells=solver_context
                    if isinstance(solver_context, AnimCellsWhileSolving)
                    else None,
                )
        except BetseSimUnstableException as exception:
            logs.log_error("Simulation halted prematurely due to computational instability.")
            exception_instability = exception
