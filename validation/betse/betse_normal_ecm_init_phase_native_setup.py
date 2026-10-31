# ruff: noqa: E731, F841
"""Independent literal INIT setup and pump source, never importing Cells.

These are bounded source slices/whole helpers on supplied pre-setup tissue/core
and conditional initializer-cache owners. No whole init_dynamics/load claim.
"""

import copy
import hashlib
import json
import random
import sys
from types import SimpleNamespace

import numpy as np

from validation.betse import betse_normal_ecm_catalog_join_native_network as network
from validation.betse import betse_normal_ecm_event_join_native_events as rng_native


def static_and_blocks(self, cells, p, rng):
    Dm_cellsA = np.asarray(self.Dm_cells)
    self.Dm_base = np.copy(Dm_cellsA)
    self.Dm_scheduled = np.copy(Dm_cellsA)
    self.Dm_scheduled[:] = 0
    self.P_mod = np.copy(self.P_cells[:])
    self.P_base = np.copy(self.P_cells[:])
    self.div_u_osmo = np.zeros(self.cdl)
    self.channel_noise_factor = rng.random(self.mdl)
    self.Dm_cells[self.iK] = (
        p.channel_noise_level * self.channel_noise_factor + 1
    ) * self.Dm_cells[self.iK]
    if p.global_options["gj_block"] != 0:
        self.gj_block = np.ones(len(cells.mem_i))
    else:
        self.gj_block = 1
    if p.global_options["NaKATP_block"] != 0:
        self.NaKATP_block = np.ones(self.mdl)
    else:
        self.NaKATP_block = 1
    self.CaATP_block = np.ones(self.mdl)
    if p.ions_dict["Ca"] == 1 and p.Ca_dyn:
        self.endo_retic = EndoRetic(self, cells, p)
    else:
        self.endo_retic = None


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


def nak_call(self, cells, p):
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


def _finalize_events_global(self, phase, *, shuffle):
    """
    Initialize all **global scheduled interventions** (i.e., events
    globally applicable to all cells) for the passed simulation phase.

    Parameters
    ----------
    phase : SimPhase
        Current simulation phase.
    """
    cells = phase.cells
    p = phase.p
    if p.global_options["K_env"] != 0:
        self.t_on_Kenv = p.global_options["K_env"][0]
        self.t_off_Kenv = p.global_options["K_env"][1]
        self.t_change_Kenv = p.global_options["K_env"][2]
        self.mem_mult_Kenv = p.global_options["K_env"][3]
    if p.global_options["Cl_env"] != 0:
        self.t_on_Clenv = p.global_options["Cl_env"][0]
        self.t_off_Clenv = p.global_options["Cl_env"][1]
        self.t_change_Clenv = p.global_options["Cl_env"][2]
        self.mem_mult_Clenv = p.global_options["Cl_env"][3]
    if p.global_options["Na_env"] != 0:
        self.t_on_Naenv = p.global_options["Na_env"][0]
        self.t_off_Naenv = p.global_options["Na_env"][1]
        self.t_change_Naenv = p.global_options["Na_env"][2]
        self.mem_mult_Naenv = p.global_options["Na_env"][3]
    if p.global_options["T_change"] != 0:
        self.tonT = p.global_options["T_change"][0]
        self.toffT = p.global_options["T_change"][1]
        self.trampT = p.global_options["T_change"][2]
        self.multT = p.global_options["T_change"][3]
    if p.global_options["gj_block"] != 0:
        self.tonGJ = p.global_options["gj_block"][0]
        self.toffGJ = p.global_options["gj_block"][1]
        self.trampGJ = p.global_options["gj_block"][2]
        numo = int(p.global_options["gj_block"][3])
        if numo > 100:
            numo = 100
        elif numo < 1:
            numo = 1
        data_length = len(cells.mem_i)
        data_fraction = int(numo / 100 * data_length)
        mem_i_copy = np.copy(cells.mem_i[:])
        shuffle(mem_i_copy)
        self.targets_gj_block = [cells.mem_i[x] for x in range(0, data_fraction)]
    if p.global_options["NaKATP_block"] != 0:
        self.tonNK = p.global_options["NaKATP_block"][0]
        self.toffNK = p.global_options["NaKATP_block"][1]
        self.trampNK = p.global_options["NaKATP_block"][2]


def _finalize_events_tissue(self, phase):
    """
    Initialize all **targeted scheduled interventions** (i.e., events only
    applicable to specific tissue profiles) for the passed simulation
    phase.

    Parameters
    ----------
    phase : SimPhase
        Current simulation phase.
    """
    cells = phase.cells
    p = phase.p
    if p.scheduled_options["Na_mem"] != 0:
        self.t_on_Namem = p.scheduled_options["Na_mem"][0]
        self.t_off_Namem = p.scheduled_options["Na_mem"][1]
        self.t_change_Namem = p.scheduled_options["Na_mem"][2]
        self.mem_mult_Namem = p.scheduled_options["Na_mem"][3]
        self.apply_Namem = p.scheduled_options["Na_mem"][4]
        self.function_Namem = p.scheduled_options["Na_mem"][5]
        self.targets_Namem = []
        for profile in self.apply_Namem:
            targets = self.tissue_target_inds[profile]
            self.targets_Namem.append(targets)
        self.targets_Namem = [item for sublist in self.targets_Namem for item in sublist]
        self.scalar_Namem = 1
        self.dyna_Namem = lambda t: 1
        if self.function_Namem != "None":
            self.scalar_Namem, self.dyna_Namem = getattr(mod, self.function_Namem)(
                self.targets_Namem, cells, p
            )
    if p.scheduled_options["K_mem"] != 0:
        self.t_on_Kmem = p.scheduled_options["K_mem"][0]
        self.t_off_Kmem = p.scheduled_options["K_mem"][1]
        self.t_change_Kmem = p.scheduled_options["K_mem"][2]
        self.mem_mult_Kmem = p.scheduled_options["K_mem"][3]
        self.apply_Kmem = p.scheduled_options["K_mem"][4]
        self.function_Kmem = p.scheduled_options["K_mem"][5]
        self.targets_Kmem = []
        for profile in self.apply_Kmem:
            targets = self.tissue_target_inds[profile]
            self.targets_Kmem.append(targets)
        self.targets_Kmem = [item for sublist in self.targets_Kmem for item in sublist]
        self.scalar_Kmem = 1
        self.dyna_Kmem = lambda t: 1
        if self.function_Kmem != "None":
            self.scalar_Kmem, self.dyna_Kmem = getattr(mod, self.function_Kmem)(
                self.targets_Kmem, cells, p
            )
    if p.scheduled_options["Cl_mem"] != 0:
        self.t_on_Clmem = p.scheduled_options["Cl_mem"][0]
        self.t_off_Clmem = p.scheduled_options["Cl_mem"][1]
        self.t_change_Clmem = p.scheduled_options["Cl_mem"][2]
        self.mem_mult_Clmem = p.scheduled_options["Cl_mem"][3]
        self.apply_Clmem = p.scheduled_options["Cl_mem"][4]
        self.function_Clmem = p.scheduled_options["Cl_mem"][5]
        self.targets_Clmem = []
        for profile in self.apply_Clmem:
            targets = self.tissue_target_inds[profile]
            self.targets_Clmem.append(targets)
        self.targets_Clmem = [item for sublist in self.targets_Clmem for item in sublist]
        self.scalar_Clmem = 1
        self.dyna_Clmem = lambda t: 1
        if self.function_Clmem != "None":
            self.scalar_Clmem, self.dyna_Clmem = getattr(mod, self.function_Clmem)(
                self.targets_Clmem, cells, p
            )
    if p.scheduled_options["Ca_mem"] != 0:
        self.t_on_Camem = p.scheduled_options["Ca_mem"][0]
        self.t_off_Camem = p.scheduled_options["Ca_mem"][1]
        self.t_change_Camem = p.scheduled_options["Ca_mem"][2]
        self.mem_mult_Camem = p.scheduled_options["Ca_mem"][3]
        self.apply_Camem = p.scheduled_options["Ca_mem"][4]
        self.function_Camem = p.scheduled_options["Ca_mem"][5]
        self.targets_Camem = []
        for profile in self.apply_Camem:
            targets = self.tissue_target_inds[profile]
            self.targets_Camem.append(targets)
        self.targets_Camem = [item for sublist in self.targets_Camem for item in sublist]
        self.scalar_Camem = 1
        self.dyna_Camem = lambda t: 1
        if self.function_Camem != "None":
            self.scalar_Camem, self.dyna_Camem = getattr(mod, self.function_Camem)(
                self.targets_Camem, cells, p
            )
    if p.scheduled_options["pressure"] != 0:
        self.t_onP = p.scheduled_options["pressure"][0]
        self.t_offP = p.scheduled_options["pressure"][1]
        self.t_changeP = p.scheduled_options["pressure"][2]
        self.rate_P = p.scheduled_options["pressure"][3]
        self.apply_P = p.scheduled_options["pressure"][4]
        self.function_P = p.scheduled_options["pressure"][5]
        self.targets_P = []
        for profile in self.apply_P:
            targets = self.cell_target_inds[profile]
            self.targets_P.append(targets)
        self.targets_P = [item for sublist in self.targets_P for item in sublist]
        self.scalar_P = 1
        self.dyna_P = lambda t: 1
        if self.function_P != "None":
            self.scalar_P, self.dyna_P = getattr(mod, self.function_P)(self.targets_P, cells, p)
    if p.scheduled_options["ecmJ"] != 0 and p.is_ecm:
        self.t_on_ecmJ = p.scheduled_options["ecmJ"][0]
        self.t_off_ecmJ = p.scheduled_options["ecmJ"][1]
        self.t_change_ecmJ = p.scheduled_options["ecmJ"][2]
        self.apply_ecmJ = p.scheduled_options["ecmJ"][3]
        self.mult_ecmJ = p.scheduled_options["ecmJ"][4]
        self.targets_ecmJ = []
        for profile in self.apply_ecmJ:
            targets = self.env_target_inds[profile]
            self.targets_ecmJ.append(targets)
        self.targets_ecmJ = [item for sublist in self.targets_ecmJ for item in sublist]


def f_sweep(pc, cells, p):
    """
    Create and return a time-dependent sweep of a sinusoidal function through
    various frequencies.

    Parameters
    ----------
    pc                 Indices of cells (p.is_ecm == False) or membranes (p.is_ecm == True)
    cells              Instance of Cells module
    p                  Instance of parameters

    Returns
    ---------
    y              Data values from 0 to 1 defining a periodic signal.
    scalar         Null output corresponding to spatial variation.
    """
    scalar = 1
    if p.f_scan_properties["f slope"] is None and p._run_sim:
        p.f_scan_properties["f slope"] = (
            p.f_scan_properties["f stop"] - p.f_scan_properties["f start"]
        ) / p.sim_time_total
    f_slope = p.f_scan_properties["f slope"]
    y = lambda t: np.sin(np.pi * (f_slope * t + p.f_scan_properties["f start"]) * t) ** 2
    return (scalar, y)


def nak_defaults(self):
    self.cATP = 1.5
    self.cADP = 0.1
    self.cPi = 0.1
    self.KmNK_Na = 12.0
    self.KmNK_K = 0.2
    self.KmNK_ATP = 0.5
    self.deltaGATP = -37000


mod = SimpleNamespace(f_sweep=f_sweep)
stb = SimpleNamespace(pumpNaKATP=pumpNaKATP)
EndoRetic = None  # unreachable under the explicit ordinary Ca_dyn=False guard
STORES = (
    "T",
    "P_cells",
    "P_base",
    "P_mod",
    "div_u_osmo",
    "Dm_base",
    "Dm_scheduled",
    "Dm_cells",
    "D_env_base",
    "D_env",
    "D_free",
    "channel_noise_factor",
    "gj_block",
    "NaKATP_block",
    "CaATP_block",
    "rho_pump",
    "rho_channel",
    "met_concs",
    "endo_retic",
    "c_env_bound",
    "bound_V",
)


def snapshot(sim):
    return {key: network.clone(getattr(sim, key)) for key in STORES if hasattr(sim, key)}


def document_hash(payload):
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def python_manifest(rng):
    payload = dict(
        kind="python.random.MT19937.full_state@1",
        implementation=sys.implementation.name,
        python_version=list(sys.version_info[:3]),
        state=json.loads(json.dumps(rng.getstate())),
    )
    return dict(payload, identity=document_hash(payload))


def tuples(value):
    return tuple(tuples(v) for v in value) if isinstance(value, (list, tuple)) else value


def callable_record(value):
    if callable(value):
        return dict(
            callable=True,
            evaluated=False,
            name=value.__name__,
            free_variables=list(value.__code__.co_freevars),
            closure=[]
            if value.__closure__ is None
            else [
                None
                if c.cell_contents is None
                else c.cell_contents
                if isinstance(c.cell_contents, (int, float, str))
                else type(c.cell_contents).__name__
                for c in value.__closure__
            ],
        )
    return network.clone(value)


class Owner:
    def __init__(self, ctx, declaration):
        self.ctx, self.declaration = ctx, declaration
        raw = declaration["setup"]
        self.rng = rng_native.restore_rng(raw["numpy_rng"])
        self.python = random.Random(0)
        self.python.setstate(tuples(raw["python_rng"]["state"]))
        if python_manifest(self.python) != raw["python_rng"]:
            raise ValueError("Independent native Python setup stream mismatch")
        p, sim = ctx.p, ctx.sim
        p._run_sim = False
        ctx.phase.kind = "INIT"
        p.channel_noise_level = raw["channel_noise_level"]
        p.global_options = copy.deepcopy(raw["global_options"])
        p.scheduled_options = copy.deepcopy(raw["scheduled_options"])
        p.f_scan_properties = copy.deepcopy(raw["frequency_sweep"])
        p.Ca_dyn = False
        p.is_ecm = True
        sim.P_cells = np.zeros(sim.cdl)
        sim.D_env_base = sim.D_env.copy()
        sim.bound_V = dict(declaration["field"]["bootstrap"]["boundary_V"])
        before = sim.Dm_cells.copy()
        static_and_blocks(sim, ctx.cells, p, self.rng)
        if hasattr(sim, "rho_pump"):
            del sim.rho_pump
        if hasattr(sim, "rho_channel"):
            del sim.rho_channel
        sim.met_concs = None
        self.pre = dict(
            stage="pre_cold_static_setup",
            source_phase="INIT",
            legacy_run_sim=False,
            setup_draw_count=1,
            numpy_rng_before=raw["numpy_rng"],
            numpy_rng_after=rng_native.manifest(self.rng),
            python_rng_before=raw["python_rng"],
            static_uniforms=sim.channel_noise_factor.copy(),
            static_level=p.channel_noise_level,
            static_diffusion_before=before,
            stores=snapshot(sim),
            store_presence_before_cold=dict(rho_pump=False, rho_channel=False),
            receipts=raw["receipts"],
        )
        nak_defaults(p)
        p.alpha_NaK = declaration["flags"]["alpha_NaK"]
        self.nak_history = []

    def finalize(self):
        ctx, raw = self.ctx, self.declaration["setup"]
        for key, values in raw["maps"].items():
            setattr(ctx.sim.dyna, key, copy.deepcopy(values))
        owner = SimpleNamespace(
            **{key: network.clone(value) for key, value in vars(ctx.sim.dyna).items()}
        )
        _finalize_events_global(owner, ctx.phase, shuffle=self.python.shuffle)
        _finalize_events_tissue(owner, ctx.phase)
        return dict(
            stage="event_finalization_after_cold",
            global_options=raw["global_options"],
            scheduled_options=raw["scheduled_options"],
            finalized_fields={key: callable_record(value) for key, value in vars(owner).items()},
            frequency_sweep_after=copy.deepcopy(ctx.p.f_scan_properties),
            python_rng_before=raw["python_rng"],
            python_rng_after=python_manifest(self.python),
            event_fire_calls=0,
            dynamic_noise_calls=0,
            dynamic_noise_configuration=raw["dynamic_noise"],
            source_phase="INIT",
            legacy_run_sim=False,
        )

    def pump(self, values):
        ctx, p, sim = self.ctx, self.ctx.p, self.ctx.sim
        packet = dict(
            alpha_NaK=p.alpha_NaK,
            block=np.broadcast_to(sim.NaKATP_block, (sim.mdl,)).copy(),
            rho_pump=np.broadcast_to(sim.rho_pump, (sim.mdl,)).copy(),
            met_concs=None,
        )
        before = dict(
            mode="nak",
            definition=copy.deepcopy(self.declaration["field"]["definition"]),
            values_before=values(),
            parameters={
                k: getattr(p, k)
                for k in ("cATP", "cADP", "cPi", "KmNK_Na", "KmNK_K", "KmNK_ATP", "deltaGATP")
            },
            packet=packet,
            incoming_rate=dict(
                present=hasattr(sim, "rate_NaKATP"),
                value=network.clone(getattr(sim, "rate_NaKATP", None)),
            ),
            runtime_temperature_K=sim.T,
            boundary=ctx.cells.bflags_mems.copy(),
            cluster_open=p.cluster_open,
            source_phase="INIT",
            legacy_run_sim=False,
        )
        before["definition"]["ions"]["membrane_diffusion_m2_s"] = sim.Dm_cells.copy()
        raw = {}
        previous = sys.gettrace()
        fields = dict(
            Qnumo="quotient_numerator",
            Qdenomo="quotient_denominator_used",
            Q="quotient",
            Keq="equilibrium",
            numo_E="saturation_numerator",
            denomo_E="saturation_denominator",
            fwd_co="saturation",
            f_Na="raw_sodium_flux_mol_m2_s",
            f_K="raw_potassium_flux_mol_m2_s",
        )

        def trace(frame, event, arg):
            if previous is not None:
                previous(frame, event, arg)
            if frame.f_code is pumpNaKATP.__code__:
                local = frame.f_locals
                if event == "line" and "Qdenomo" in local and "inds_Z" not in local:
                    raw.setdefault(
                        "quotient_denominator_raw", np.array(local["Qdenomo"], copy=True)
                    )
                if event == "return":
                    raw.update(
                        {
                            key: network.clone(local[native])
                            for native, key in fields.items()
                            if native in local
                        }
                    )
                    if "inds_Z" in local:
                        raw["zero_denominator_indices"] = local["inds_Z"][0].copy()
                    if arg is not None:
                        raw["raw_rate_proxy_mol_m2_s"] = arg[2].copy()
            return trace

        completed = False
        try:
            sys.settrace(trace)
            nak_call(sim, ctx.cells, p)
            completed = True
        finally:
            sys.settrace(previous)
            result = dict(
                before=before,
                arithmetic=raw if p.alpha_NaK > 0 else None,
                applied_flux=sim.fluxes_mem.copy(),
                raw_rate_proxy=network.clone(getattr(sim, "rate_NaKATP", None)),
                source_completed=completed,
            )
            self.nak_history.append(copy.deepcopy(result))
        return result
