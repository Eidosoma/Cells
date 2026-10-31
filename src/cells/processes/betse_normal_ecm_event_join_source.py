# ruff: noqa: B007, B905
"""Literal pre-step source events and post-GRN protein-noise interfaces.

Tissue/callback owners are explicit supplied post-finalization conditions.
No profile picking, mesh construction, native cold/restart or physics claim.
"""

from types import SimpleNamespace

import numpy as np

from cells.processes import betse_ecm_grn_source as material_source
from cells.processes import betse_normal_ecm_catalog_join_source as catalog_source
from cells.processes import betse_perturbations as perturbations
from cells.processes import betse_time_modulation as time_laws

clone = catalog_source.clone
logs = material_source.logs
SimPhaseKind = SimpleNamespace(SIM="SIM", INIT="INIT")
stb = SimpleNamespace(update_Co=material_source.update_Co)


def pulse(t, t_on, t_off, t_change):
    g = 1 / t_change * 10
    y1 = 1 / (1 + np.exp(-g * (t - t_on)))
    y2 = 1 / (1 + np.exp(-g * (t - t_off)))
    y = y1 - y2
    return y


class TissueHandler(object):
    def fire_events(self, phase, t):
        self._fire_events_global(phase=phase, t=t)
        self._observe("_fire_events_global", phase.sim)
        self._fire_events_tissue(phase=phase, t=t)
        self._observe("_fire_events_tissue", phase.sim)
        self.makeAllChanges(phase.sim)
        self._observe("makeAllChanges", phase.sim)

    def _fire_events_global(self, phase, t):
        p = phase.p
        sim = phase.sim
        if p.global_options["K_env"] != 0:
            effector_Kenv = tb.pulse(t, self.t_on_Kenv, self.t_off_Kenv, self.t_change_Kenv)
            if p.is_ecm:
                sim.c_env_bound[sim.iK] = (
                    self.mem_mult_Kenv * effector_Kenv * p.env_concs["K"] + p.env_concs["K"]
                )
                sim.c_env_bound[sim.iM] = (
                    self.mem_mult_Kenv * effector_Kenv * p.env_concs["K"] + p.env_concs["M"]
                )
            else:
                sim.cc_env[sim.iK][:] = (
                    self.mem_mult_Kenv * effector_Kenv * p.conc_env_k + p.conc_env_k
                )
        if p.global_options["Cl_env"] != 0 and p.ions_dict["Cl"] == 1:
            effector_Clenv = tb.pulse(t, self.t_on_Clenv, self.t_off_Clenv, self.t_change_Clenv)
            if not p.is_ecm:
                sim.cc_env[sim.iCl][:] = (
                    self.mem_mult_Clenv * effector_Clenv * p.conc_env_cl + p.conc_env_cl
                )
            else:
                sim.c_env_bound[sim.iCl] = (
                    self.mem_mult_Clenv * effector_Clenv * p.env_concs["Cl"] + p.env_concs["Cl"]
                )
                sim.c_env_bound[sim.iNa] = (
                    self.mem_mult_Clenv * effector_Clenv * p.env_concs["Cl"] + p.env_concs["Na"]
                )
        if p.global_options["Na_env"] != 0:
            effector_Naenv = tb.pulse(t, self.t_on_Naenv, self.t_off_Naenv, self.t_change_Naenv)
            if not p.is_ecm:
                sim.cc_env[sim.iNa][:] = (
                    self.mem_mult_Naenv * effector_Naenv * p.conc_env_na + p.conc_env_na
                )
            else:
                sim.c_env_bound[sim.iNa] = (
                    self.mem_mult_Naenv * effector_Naenv * p.env_concs["Na"] + p.env_concs["Na"]
                )
                sim.c_env_bound[sim.iM] = (
                    self.mem_mult_Naenv * effector_Naenv * p.env_concs["Na"] + p.env_concs["M"]
                )
        if p.global_options["T_change"] != 0:
            sim.T = self.multT * tb.pulse(t, self.tonT, self.toffT, self.trampT) * p.T + p.T
        if p.global_options["gj_block"] != 0:
            sim.gj_block[self.targets_gj_block] = 1.0 - tb.pulse(
                t, self.tonGJ, self.toffGJ, self.trampGJ
            )
        if p.global_options["NaKATP_block"] != 0:
            sim.NaKATP_block = 1.0 - tb.pulse(t, self.tonNK, self.toffNK, self.trampNK)

    def _fire_events_tissue(self, phase, t):
        cells = phase.cells
        p = phase.p
        sim = phase.sim
        if p.scheduled_options["Na_mem"] != 0:
            effector_Na = (
                self.scalar_Namem
                * self.dyna_Namem(t)
                * tb.pulse(t, self.t_on_Namem, self.t_off_Namem, self.t_change_Namem)
            )
            sim.Dm_scheduled[sim.iNa][self.targets_Namem] = (
                self.mem_mult_Namem * effector_Na * self.tissue_default.Dm_Na
            )
        if p.scheduled_options["K_mem"] != 0:
            effector_K = (
                self.scalar_Kmem
                * self.dyna_Kmem(t)
                * tb.pulse(t, self.t_on_Kmem, self.t_off_Kmem, self.t_change_Kmem)
            )
            sim.Dm_scheduled[sim.iK][self.targets_Kmem] = (
                self.mem_mult_Kmem * effector_K * self.tissue_default.Dm_K
            )
        if p.scheduled_options["Cl_mem"] != 0 and p.ions_dict["Cl"] != 0:
            effector_Cl = (
                self.scalar_Clmem
                * self.dyna_Clmem(t)
                * tb.pulse(t, self.t_on_Clmem, self.t_off_Clmem, self.t_change_Clmem)
            )
            sim.Dm_scheduled[sim.iCl][self.targets_Clmem] = (
                self.mem_mult_Clmem * effector_Cl * self.tissue_default.Dm_Cl
            )
        if p.scheduled_options["Ca_mem"] != 0 and p.ions_dict["Ca"] != 0:
            effector_Ca = (
                self.scalar_Camem
                * self.dyna_Camem(t)
                * tb.pulse(t, self.t_on_Camem, self.t_off_Camem, self.t_change_Camem)
            )
            sim.Dm_scheduled[sim.iCa][self.targets_Camem] = (
                self.mem_mult_Camem * effector_Ca * self.tissue_default.Dm_Ca
            )
        if p.scheduled_options["pressure"] != 0:
            sim.P_mod[self.targets_P] = (
                self.scalar_P
                * self.dyna_P(t)
                * self.rate_P
                * tb.pulse(t, self.t_onP, self.t_offP, self.t_changeP)
            )
        if p.scheduled_options["ecmJ"] != 0:
            if p.is_ecm:
                for i, _ in enumerate(sim.D_env):
                    effector_ecmJ = self.mult_ecmJ * tb.pulse(
                        t, self.t_on_ecmJ, self.t_off_ecmJ, self.t_change_ecmJ
                    )
                    sim.D_env[i][self.targets_ecmJ] = (
                        sim.D_env_base[i][self.targets_ecmJ] * (1 - effector_ecmJ)
                        + effector_ecmJ * sim.D_free[i]
                    )
                    sim.D_env_weight = sim.D_env_weight.ravel()
                    sim.D_env_weight_base = sim.D_env_weight_base.ravel()
                    sim.D_env_weight[self.targets_ecmJ] = (
                        sim.D_env_weight_base[self.targets_ecmJ] * (1 - effector_ecmJ)
                        + effector_ecmJ
                    )
                    sim.D_env_weight = sim.D_env_weight.reshape(cells.X.shape)
                    sim.D_env_weight_base = sim.D_env_weight_base.reshape(cells.X.shape)
            else:
                effector_ecmJ = self.mult_ecmJ * tb.pulse(
                    t, self.t_on_ecmJ, self.t_off_ecmJ, self.t_change_ecmJ
                )
                sim.D_env_weight = sim.D_env_weight.ravel()
                sim.D_env_weight_base = sim.D_env_weight_base.ravel()
                sim.D_env_weight[self.targets_ecmJ] = (
                    sim.D_env_weight_base[self.targets_ecmJ] * (1 - effector_ecmJ) + effector_ecmJ
                )
                sim.D_env_weight = sim.D_env_weight.reshape(cells.X.shape)
                sim.D_env_weight_base = sim.D_env_weight_base.reshape(cells.X.shape)
        if self.event_cut is not None and (not self.event_cut.is_fired) and (t >= p.event_cut_time):
            for cut_profile_name in p.event_cut_profile_names:
                logs.log_info('Cutting cell cluster via cut profile "%s"...', cut_profile_name)
                cut_profile_picker = self.cut_name_to_profile[cut_profile_name].picker
                self._cut_cells(phase=phase, tissue_picker=cut_profile_picker)
            logs.log_info("Cutting event successful! Resuming simulation...")
            self.data_length = len(cells.mem_i)
            self.init_profiles(phase)
            cells.redo_gj(phase)
            self.init_events(phase)
            self.event_cut.fire(phase=phase, time_step=t)
        if self._event_voltage is not None:
            self._event_voltage.fire(phase=phase, time_step=t)

    def makeAllChanges(self, sim):
        sim.Dm_cells = sim.Dm_scheduled + sim.Dm_base
        sim.P_cells = sim.P_mod + sim.P_base


class SimEventPulseVoltage(object):
    def fire(self, phase, time_step):
        effector = toolbox.pulse(
            time_step, self.start_time_step, self.stop_time_step, self.time_step_rate
        )
        phase.sim.bound_V[self.positive_voltage_boundary] = self.peak_voltage * effector
        phase.sim.bound_V[self.negative_voltage_boundary] = -self.peak_voltage * effector


def protein_noise(self, cells, p, phase):
    if p.dynamic_noise == 1 and p.ions_dict["P"] == 1 and (phase.kind is SimPhaseKind.SIM):
        self.protein_noise_flux = p.dynamic_noise_level * (p._native_random(self.mdl) - 0.5)
        self.cc_cells[self.iP], self.cc_at_mem[self.iP], self.cc_env[self.iP] = stb.update_Co(
            self,
            self.cc_cells[self.iP],
            self.cc_at_mem[self.iP],
            self.cc_env[self.iP],
            self.protein_noise_flux,
            cells,
            p,
            ignoreECM=False,
        )


tb = toolbox = SimpleNamespace(pulse=pulse)

EVENT_STORES = (
    "T",
    "c_env_bound",
    "gj_block",
    "NaKATP_block",
    "rho_channel",
    "bound_V",
    "Dm_base",
    "Dm_scheduled",
    "Dm_cells",
    "D_env_base",
    "D_env",
    "D_env_weight_base",
    "D_env_weight",
    "D_free",
    "P_base",
    "P_mod",
    "P_cells",
)


def event_snapshot(sim):
    return {key: clone(getattr(sim, key)) for key in EVENT_STORES}


def prepared_callback(record):
    # Source-return spatial arrays already belong to the supplied finalized owner.
    # Keep full shape and occurrence order; do not gather/repair them by targets.
    kind = record["kind"]
    if kind == "constant":
        return lambda t: 1
    if kind == "periodic":
        program = time_laws.periodic_program(
            frequency_Hz=record["frequency"],
            phase_rad=record["phase"],
            provenance=record["provenance"],
        )
        # Qualified helper preserves literal multiplication order, with NumPy only.
        return lambda t: time_laws.evaluate(program, t, xp=np).value
    if kind == "sweep":
        program = time_laws.sweep_program(
            start_Hz=record["start"],
            slope_Hz_s=record["slope"],
            run_sim=True,
            provenance=record["provenance"],
        )
        return lambda t: time_laws.evaluate(program, t, xp=np).value
    raise ValueError("Require explicit prepared constant/periodic/sweep callback ownership")


def install_owner(ctx, declaration, state, observer=None):
    handler = object.__new__(TissueHandler)
    # These are supplied actual handler fields, never guessed profile/initializer values.
    vars(handler).update(clone(declaration["handler_fields"]))
    handler.tissue_default = SimpleNamespace(**clone(declaration["tissue_default"]))
    for key in ("tissue_target_inds", "cell_target_inds", "env_target_inds"):
        setattr(handler, key, clone(declaration[key]))
    handler.event_cut = declaration["event_cut"]
    saved = declaration["voltage"]
    if saved is None:
        handler._event_voltage = None
    else:
        voltage = object.__new__(SimEventPulseVoltage)
        vars(voltage).update(clone(saved))
        handler._event_voltage = voltage
    for suffix, record in declaration["callbacks"].items():
        setattr(handler, "dyna_" + suffix, prepared_callback(record["dynamic"]))
        scalar = record["source_scalar"]
        setattr(
            handler,
            "scalar_" + suffix,
            np.asarray(scalar, np.float64) if isinstance(scalar, (list, tuple)) else scalar,
        )
    ctx.p.global_options = clone(declaration["global_options"])
    ctx.p.scheduled_options = clone(declaration["scheduled_options"])
    ctx.p.env_concs = clone(declaration["configured_environment"])
    for key, value in state.items():
        setattr(ctx.sim, key, clone(value))
    for ion in ("Na", "K", "Cl", "Ca", "M", "P"):
        ctx.p.ions_dict[ion] = int(ion in ctx.ion_ids)
        if ion in ctx.ion_ids:
            setattr(ctx.sim, "i" + ion, ctx.ion_ids.index(ion))

    def observe(stage, sim):
        if observer is not None:
            observer(dict(stage=stage, state=event_snapshot(sim)))

    handler._observe = observe
    ctx.sim.dyna = ctx.phase.dyna = handler
    return handler


class EventSourceRejected(RuntimeError):
    def __init__(self, error, partial):
        super().__init__(str(error))
        self.partial = clone(partial)


def fire(ctx, t, observer=None):
    before = event_snapshot(ctx.sim)
    result = dict(before=before, stages=[], source_time_s=float(t), source_completed=False)
    old = ctx.phase.dyna._observe

    def observe(stage, sim):
        snapshot = dict(stage=stage, state=event_snapshot(sim))
        result["stages"].append(snapshot)
        if observer is not None:
            observer(clone(snapshot))

    ctx.phase.dyna._observe = observe
    failure = None
    try:
        fire_events_guarded(ctx.phase, t)
        result["source_completed"] = True
    except Exception as error:
        failure = error
    finally:
        result["after"] = event_snapshot(ctx.sim)
        ctx.phase.dyna._observe = old
    if failure is not None:
        raise EventSourceRejected(failure, result) from failure
    return result


def noise(ctx, stream, noise_binding, index, configuration, observer=None):
    result = dict(
        before=catalog_source.material_values(ctx.sim),
        stream_before=perturbations.native_stream_manifest(stream),
        draws=[],
        source_completed=False,
    )
    active = stream

    def random(size):
        nonlocal active
        if size != len(noise_binding.membrane_ids):
            raise ValueError("Require the actual complete membrane noise draw axis")
        draw, active = perturbations.sample_native(
            active, noise_binding, site="protein_flux", tick=index
        )
        result["draws"].append(perturbations.draw_manifest(draw, noise_binding))
        result["stream_after_draw"] = perturbations.native_stream_manifest(active)
        if observer is not None:
            observer(clone(result))
        return draw.values.copy()

    ctx.p._native_random = random
    ctx.p.dynamic_noise = configuration["enabled"]
    ctx.p.dynamic_noise_level = configuration["level_mol_m2_s"]
    guard = (
        ctx.p.dynamic_noise == 1
        and ctx.p.ions_dict["P"] == 1
        and ctx.phase.kind is SimPhaseKind.SIM
    )
    result["guard_active"] = guard
    if observer is not None and not guard:
        observer(clone(result))
    failure = None
    try:
        protein_noise(ctx.sim, ctx.cells, ctx.p, ctx.phase)
        result["source_completed"] = True
    except Exception as error:
        failure = error
    finally:
        result.update(
            after=catalog_source.material_values(ctx.sim),
            stream_after=perturbations.native_stream_manifest(active),
            cache_present=hasattr(ctx.sim, "protein_noise_flux"),
            cache_value=clone(ctx.sim.protein_noise_flux)
            if hasattr(ctx.sim, "protein_noise_flux")
            else None,
        )
    if failure is not None:
        raise EventSourceRejected(failure, result) from failure
    return active, result


def reset_fluxes(self, p):
    self.fluxes_mem.fill(0)
    self.fluxes_gj.fill(0)
    if p.is_ecm:
        self.fluxes_env_x = np.zeros((len(self.zs), self.edl))
        self.fluxes_env_y = np.zeros((len(self.zs), self.edl))


def fire_events_guarded(phase, t):
    if phase.kind is SimPhaseKind.SIM:
        phase.dyna.fire_events(phase=phase, t=t)
