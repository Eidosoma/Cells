"""Source-discrete late catalog channels in the no-ECM normal join.

Ordinary pump/ion/gap fluxes are deferred. Ordered network channels act directly
on their live concentration aliases before that commit and publish a separate
current by replacement. This law does not assign ordinary membrane diffusivity.
"""

import math
from collections.abc import Mapping
from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import NamedTuple

import numpy as np

from cells.core.errors import NumericalError
from cells.processes import betse_normal_current as current
from cells.processes import betse_normal_gated_join as gated
from cells.processes import betse_normal_ion_join as ions
from cells.processes import betse_normal_pump_join as pump
from cells.processes import betse_normal_voltage as voltage

LAW_ID = "betse_normal_late_channel_join_v1_5_0@1"
SOURCE_REVISION = pump.SOURCE_REVISION
CLASSES = ("Nav1p6", "Kv1p5", "Kv3p2", "ClLeak")
ROLES = dict(Nav1p6="Na", Kv1p5="K", Kv3p2="K", ClLeak="Cl")


@dataclass(frozen=True, slots=True)
class Binding:
    pump_binding: pump.Binding
    definition: object
    identity: str


@dataclass(frozen=True, slots=True)
class State:
    binding_identity: str
    pump: pump.State
    channel_caches: tuple
    channel_calls: tuple
    initialization: object
    identity: str


class Packet(NamedTuple):
    phase_kind: str
    modulators: object
    substances_affect_charge: bool


@dataclass(frozen=True, slots=True)
class ChannelPhase:
    channel_id: str
    class_name: str
    ion_id: str
    skipped: bool
    call_index: int
    cache_before: object
    cache_after: object
    voltage_before_V: object
    voltage_after_V: object
    sampled_bulk_mM: object
    sampled_membrane_mM: object
    sampled_bath_mM: object
    diffusion_m2_s: object
    flux_mol_m2_s: object
    network_current_before_A_m2: object
    network_current_after_A_m2: object
    values_before: ions.Values
    values_after: ions.Values
    dt_s: float
    native_dt: float


@dataclass(frozen=True, slots=True)
class MaterialTrial:
    parent: State
    pump: pump.MaterialTrial
    channel_phases: tuple
    network: object
    candidate: State
    identity: str


@dataclass(frozen=True, slots=True)
class CoupledTrial:
    parent: State
    material: MaterialTrial
    current: current.CurrentReadout
    voltage: voltage.Readout
    candidate: State
    clock: object
    identity: str


class ChannelJoinRejected(NumericalError):
    def __init__(
        self,
        reason,
        *,
        stage,
        parent,
        material=None,
        channel_phases=(),
        network=None,
        readout=None,
        voltage_trial=None,
        initialization=None,
    ):
        super().__init__("Native late-channel join refused at " + stage + ": " + str(reason))
        self.stage, self.parent, self.material = stage, parent, material
        self.channel_phases, self.network = channel_phases, network
        self.readout, self.voltage_trial = readout, voltage_trial
        self.initialization = initialization


def binding_record(binding):
    return dict(
        law=LAW_ID,
        revision=SOURCE_REVISION,
        pump_binding=binding.pump_binding.identity,
        definition=binding.definition,
    )


def bind(pump_binding, raw):
    if (
        type(pump_binding) is not pump.Binding
        or type(raw) is not dict
        or set(raw) != {"kind", "provenance", "channels"}
        or raw["kind"] != "cells.betse_normal_channel_join_inputs@1"
        or not isinstance(raw["provenance"], str)
        or not raw["provenance"].strip()
        or not isinstance(raw["channels"], (list, tuple))
        or len(raw["channels"]) > 16
    ):
        raise ValueError("Require bounded ordered native channel definitions")
    ib = pump_binding.gated_binding.material_binding
    names = set()
    for row in raw["channels"]:
        if (
            set(row) != {"id", "class_name", "targets", "maxDm_m2_s", "init_active"}
            or not isinstance(row["id"], str)
            or not row["id"].isidentifier()
            or row["id"] in names
            or row["class_name"] not in CLASSES
            or type(row["init_active"]) is not bool
            or type(row["maxDm_m2_s"]) not in (int, float)
            or not math.isfinite(row["maxDm_m2_s"])
            or row["maxDm_m2_s"] < 0
        ):
            raise ValueError("Invalid original channel population")
        names.add(row["id"])
        targets = row["targets"]
        if (
            not isinstance(targets, (list, tuple))
            or len(targets) > 128
            or any(type(i) is not int or not 0 <= i < len(ib.membrane_ids) for i in targets)
        ):
            raise ValueError("Require explicit ordered source target indices, including duplicates")
        role = ROLES[row["class_name"]]
        if role not in ib.ion_ids or ib.kernel.valence[ib.ion_ids.index(role)] != (
            -1 if role == "Cl" else 1
        ):
            raise ValueError("Native channel role/valence missing")
    result = Binding(pump_binding, ions.freeze(raw), "")
    return replace(result, identity=ions.digest(binding_record(result)))


def packet(binding, *, phase_kind, modulators, substances_affect_charge):
    rows = binding.definition["channels"]
    if (
        phase_kind not in ("INIT", "SIM")
        or type(substances_affect_charge) is not bool
        or not isinstance(modulators, Mapping)
        or set(modulators) != {r["id"] for r in rows}
    ):
        raise ValueError("Require explicit phase, publication switch and every modulator")
    m = len(binding.pump_binding.gated_binding.material_binding.membrane_ids)
    return Packet(
        phase_kind,
        ions.freeze(
            {
                r["id"]: current._array(
                    modulators[r["id"]], (m,), "signed source channel modulator"
                )
                for r in rows
            }
        ),
        substances_affect_charge,
    )


def _init_cache(row, vm):
    # Channel.init_channel builds a Python list from profile targets and calls
    # np.asarray without a dtype. The empty list becomes float64 and the native
    # class initializer refuses the subsequent voltage indexing operation.
    targets = np.asarray(row["targets"])
    V = vm[targets] * 1000 + 0.0
    name = row["class_name"]
    cache = dict(
        targets=targets,
        data_length=len(targets),
        mdl=len(vm),
        modulator=1.0,
        v_corr=0.0,
        time_unit=1.0 if name == "ClLeak" else 1e3,
    )
    if name == "Nav1p6":
        cache.update(
            vrev=50,
            _mpower=1.0,
            _hpower=0.0,
            m=1.0000 / (1 + np.exp(-0.03937 * 4.2 * (V - -17.000))),
            h=1.0,
        )
    elif name == "Kv1p5":
        cache.update(
            vrev=-65,
            _mpower=1,
            _hpower=1,
            m=1.0000 / (1 + np.exp((V - -6.0000) / -6.4000)),
            h=1.0000 / (1 + np.exp((V - -25.3000) / 3.5000)),
        )
    elif name == "Kv3p2":
        cache.update(
            vrev=-65, _mpower=2, _hpower=0, m=1 / (1 + np.exp((V - -0.373267) / -8.568187)), h=1
        )
    else:
        cache.update(_mpower=0, _hpower=0, m=np.ones(len(targets)), h=np.ones(len(targets)))
    cache.update(ions=[ROLES[name]], rel_perm=[1.0], chan_flux=np.zeros(len(vm)), DChan=None)
    return ions.freeze(cache)


def _run_cache(row, incoming, vm, dt, modulator):
    cache = {
        key: value.copy() if isinstance(value, np.ndarray) else value
        for key, value in incoming.items()
    }
    V = vm[cache["targets"]] * 1000 + cache["v_corr"]
    name = row["class_name"]
    cache["modulator"] = modulator
    if name == "Nav1p6":
        cache.update(
            _mInf=1.0000 / (1 + np.exp(-0.03937 * 4.2 * (V - -17.000))),
            _mTau=1,
            _hInf=1.0,
            _hTau=1.0,
        )
    elif name == "Kv1p5":
        cache.update(
            _mInf=1.0000 / (1 + np.exp((V - -6.0000) / -6.4000)),
            _mTau=(-0.1163 * V) + 8.3300,
            _hInf=1.0000 / (1 + np.exp((V - -25.3000) / 3.5000)),
            _hTau=(-15.5000 * V) + 1620.0000,
        )
    elif name == "Kv3p2":
        cache.update(
            _mInf=1 / (1 + np.exp((V - -0.373267) / -8.568187)),
            _mTau=3.241643 + (19.106496 / (1 + np.exp((V - 19.220623) / 4.451533))),
            _hInf=1,
            _hTau=1,
        )
    else:
        cache.update(_mInf=1, _mTau=1, _hInf=1, _hTau=1)
    native_dt = dt * cache["time_unit"]
    for gate in ("m", "h"):
        tau, target = cache["_" + gate + "Tau"], cache["_" + gate + "Inf"]
        cache[gate] = (tau * cache[gate] + native_dt * target) / (tau + native_dt)
    opening = (cache["m"] ** cache["_mpower"]) * (cache["h"] ** cache["_hpower"])
    cache["P"] = np.zeros(cache["mdl"])
    cache["P"][cache["targets"]] = opening
    return cache


def _state(binding, parent, caches, calls, initialization):
    result = State(
        binding.identity, parent, ions.freeze(caches), tuple(calls), ions.freeze(initialization), ""
    )
    return replace(result, identity=ions.digest(result))


def initialize(binding, parent):
    if type(parent) is not pump.State or parent.binding_identity != binding.pump_binding.identity:
        raise ValueError("Require original pump/gate/material parent")
    caches = []
    for row in binding.definition["channels"]:
        try:
            caches.append(_init_cache(row, parent.gated.material.values.voltage_V))
        except Exception as error:
            partial = dict(
                channel_id=row["id"],
                prior_caches=tuple(caches),
                failed_core_cache=dict(
                    targets=np.asarray(row["targets"]),
                    data_length=len(row["targets"]),
                    mdl=len(parent.gated.material.values.voltage_V),
                    modulator=1.0,
                    v_corr=0.0,
                ),
                source_exception=type(error).__name__,
                no_repair_applied=True,
            )
            raise ChannelJoinRejected(
                error,
                stage="channel_initialization",
                parent=parent,
                initialization=ions.freeze(partial),
            ) from error
    return _state(binding, parent, caches, [0] * len(caches), caches)


def _values(arrays):
    """Freeze each array while retaining the original typed Values container."""
    return ions.Values(*(ions.freeze(value) for value in arrays))


def material_step(binding, parent, forcing, live_pump, live):
    material = None
    phases = []
    network = {}
    try:
        if (
            type(binding) is not Binding
            or binding.identity != ions.digest(binding_record(binding))
            or ions.digest(
                binding_record(bind(binding.pump_binding, ions.data(binding.definition)))
            )
            != ions.digest(binding_record(binding))
        ):
            raise ValueError("Changed channel binding")
        if (
            type(parent) is not State
            or parent.binding_identity != binding.identity
            or parent.identity
            != _state(
                binding,
                parent.pump,
                parent.channel_caches,
                parent.channel_calls,
                parent.initialization,
            ).identity
            or len(parent.channel_caches) != len(binding.definition["channels"])
            or len(parent.channel_calls) != len(parent.channel_caches)
            or any(type(c) is not int or c < 0 for c in parent.channel_calls)
        ):
            raise ValueError("Changed channel parent/cache association")
        normalized = packet(binding, **live._asdict())
        if ions.record(normalized) != ions.record(live) or any(
            x.flags.writeable for x in live.modulators.values()
        ):
            raise ValueError("Changed channel packet")
        for row, cache, calls in zip(
            binding.definition["channels"], parent.channel_caches, parent.channel_calls, strict=True
        ):
            if not isinstance(cache, MappingProxyType):
                raise ValueError("Require immutable class cache mapping")
            for value in cache.values():
                if isinstance(value, np.ndarray) and (
                    value.flags.writeable or not np.isfinite(value).all()
                ):
                    raise ValueError("Require immutable finite original channel cache")
                if type(value) in (int, float) and not math.isfinite(value):
                    raise ValueError("Nonfinite scalar channel cache")
            initial = _init_cache(row, parent.pump.gated.material.values.voltage_V)
            expected_keys = set(initial) | (
                {"_mInf", "_hInf", "_mTau", "_hTau", "P"} if calls else set()
            )
            if set(cache) != expected_keys:
                raise ValueError("Missing or unexpected original class state")
            for key in ("m", "h"):
                shape = initial[key].shape if isinstance(initial[key], np.ndarray) else ()
                if np.asarray(cache[key]).shape != shape:
                    raise ValueError("Changed original scalar/target gate shape")
            for key in ("chan_flux", "DChan", "P"):
                if key == "P" and not calls or key == "DChan" and not calls:
                    continue
                if not isinstance(cache[key], np.ndarray) or cache[key].shape != (
                    len(parent.pump.rate_proxy_mol_m2_s),
                ):
                    raise ValueError("Changed original membrane cache shape")
            for key in (
                "targets",
                "data_length",
                "mdl",
                "time_unit",
                "v_corr",
                "ions",
                "rel_perm",
                "_mpower",
                "_hpower",
            ):
                if ions.record(cache[key]) != ions.record(initial[key]):
                    raise ValueError("Changed fixed source class metadata")
        ib = binding.pump_binding.gated_binding.material_binding
        caches, calls = list(parent.channel_caches), list(parent.channel_calls)

        def late_callback(arrays, observe):
            cell, membrane, bath, vm, fm, fg, vgj, egj, exy, opening = arrays
            extra = np.zeros(len(vm))
            before_network = _values(arrays)
            observe("network_clear")
            with np.errstate(all="ignore"):
                for slot, row in enumerate(binding.definition["channels"]):
                    i = ib.ion_ids.index(ROLES[row["class_name"]])
                    before = _values(arrays)
                    old_cache = caches[slot]
                    skip = live.phase_kind == "INIT" and not row["init_active"]
                    sampled_bulk = cell[i].copy()
                    sampled_mem = cell[i][ib.kernel.owner].copy()
                    sampled_bath = np.asarray(bath[i]).copy()
                    current_before = extra.copy()
                    diffusion = flux = None
                    if not skip:
                        cache = _run_cache(
                            row, old_cache, vm, forcing.dt_s, live.modulators[row["id"]]
                        )
                        diffusion = (
                            cache["P"] * 1.0 * row["maxDm_m2_s"] * live.modulators[row["id"]]
                        )
                        ones = np.ones(len(vm))
                        flux = ions._electroflux(
                            bath[i],
                            sampled_mem,
                            diffusion,
                            ones * ib.kernel.membrane_thickness_m,
                            ib.kernel.valence[i] * ones,
                            vm,
                            forcing.runtime_temperature_K,
                            ib.kernel,
                        )
                        # Actual update_Co(ignoreECM=True), including the source
                        # scalar bath mean. No cluster-boundary mask is applied.
                        cell[i] = (
                            cell[i]
                            + (
                                np.dot(ib.kernel.owner_sum, flux * ib.kernel.area_m2)
                                / ib.kernel.cell_volume_m3
                            )
                            * forcing.dt_s
                        )
                        membrane[i] = cell[i][ib.kernel.owner]
                        bath[i] = (
                            bath[i]
                            + -flux * (ib.kernel.area_m2 / ib.kernel.bath_volume_m3) * forcing.dt_s
                        ).mean()
                        extra += -flux * ib.kernel.F_C_mol * ib.kernel.valence[i]
                        cache.update(chan_flux=flux, DChan=diffusion)
                        caches[slot] = ions.freeze(cache)
                        calls[slot] += 1
                    after = _values(arrays)
                    phases.append(
                        ChannelPhase(
                            row["id"],
                            row["class_name"],
                            ib.ion_ids[i],
                            skip,
                            calls[slot],
                            old_cache,
                            caches[slot],
                            before.voltage_V,
                            after.voltage_V,
                            ions.freeze(sampled_bulk),
                            ions.freeze(sampled_mem),
                            ions.freeze(sampled_bath),
                            ions.freeze(diffusion),
                            ions.freeze(flux),
                            ions.freeze(current_before),
                            ions.freeze(extra),
                            before,
                            after,
                            forcing.dt_s,
                            0.0 if skip else forcing.dt_s * old_cache["time_unit"],
                        )
                    )
                    observe("channel_skipped" if skip else "channel_direct", i)
                # Empty network reaction system still publishes alias-preserving
                # bulk + 0*dt and energy_charge=0, then conditional replacement.
                for i in range(len(cell)):
                    cell[i] = cell[i] + 0.0 * forcing.dt_s
                network.update(
                    values_before=before_network,
                    values_after=_values(arrays),
                    extra_current_A_m2=ions.freeze(extra),
                    extra_charge_C_m3=np.zeros(cell.shape[1]),
                    substances_affect_charge=live.substances_affect_charge,
                    current_publication="replace"
                    if live.substances_affect_charge
                    else "retain incoming",
                    aliases_follow_live_rows=True,
                    user_molecules=0,
                    reactions=0,
                    energy_charge=np.zeros(cell.shape[1]),
                    ordinary_Dm_unchanged=True,
                    channel_flux_added_to_ordinary_storage=False,
                    source_channel_flux_boundary_mask=False,
                )
                observe("network_publish")

        material = _pump_material_step(
            binding.pump_binding, parent.pump, forcing, live_pump, late_callback
        )
        candidate = _state(binding, material.candidate, caches, calls, parent.initialization)
        trial = MaterialTrial(parent, material, tuple(phases), ions.freeze(network), candidate, "")
        trial = replace(trial, identity=ions.digest(trial))
        if any(
            not np.isfinite(value).all()
            for cache in caches
            for value in cache.values()
            if isinstance(value, np.ndarray)
        ):
            raise ChannelJoinRejected(
                "Nonfinite channel cache",
                stage="material_trial",
                parent=parent,
                material=trial,
                channel_phases=tuple(phases),
                network=network,
            )
        return trial
    except ChannelJoinRejected:
        raise
    except Exception as error:
        if isinstance(error, pump.PumpJoinRejected):
            material = error.material
        raise ChannelJoinRejected(
            error,
            stage="material_source",
            parent=parent,
            material=material,
            channel_phases=tuple(phases),
            network=ions.freeze(network),
        ) from error


def advance(
    binding,
    parent,
    forcing,
    live_pump,
    live,
    *,
    boundary_V,
    extra_charge_C_m3,
    extra_current_A_m2,
    elapsed_s,
):
    material = readout = voltage_trial = None
    try:
        if (
            type(elapsed_s) not in (int, float)
            or not math.isfinite(elapsed_s)
            or elapsed_s < 0
            or not math.isfinite(elapsed_s + forcing.dt_s)
        ):
            raise ValueError("Require finite explicit outer clock")
        material = material_step(binding, parent, forcing, live_pump, live)
        pb = binding.pump_binding
        values = material.pump.candidate.gated.material.values
        vb = pb.gated_binding.voltage_binding
        cb = vb.current_binding
        published = live.substances_affect_charge
        readout = current.evaluate(
            cb,
            current.inputs(
                cb,
                cell_mol_m3=values.cell_mol_m3,
                membrane_flux_mol_m2_s=values.membrane_flux_mol_m2_s,
                junction_flux_mol_m2_s=values.junction_flux_mol_m2_s,
                extra_charge_C_m3=material.network["extra_charge_C_m3"]
                if published
                else extra_charge_C_m3,
                extra_current_A_m2=material.network["extra_current_A_m2"]
                if published
                else extra_current_A_m2,
            ),
        )
        voltage_trial = voltage.evaluate(
            vb, readout, old_voltage_V=values.voltage_V, dt_s=forcing.dt_s, boundary_V=boundary_V
        )
        final = ions.state(
            pb.gated_binding.material_binding,
            values._replace(voltage_V=voltage_trial.values.voltage_V)._asdict(),
            step_index=material.pump.candidate.gated.material.step_index,
        )
        active = gated._state(
            pb.gated_binding,
            final,
            material.pump.candidate.gated.memory,
            parent.pump.gated.initialization,
        )
        next_pump = pump._state(pb, active, material.pump.candidate.rate_proxy_mol_m2_s)
        candidate = _state(
            binding,
            next_pump,
            material.candidate.channel_caches,
            material.candidate.channel_calls,
            parent.initialization,
        )
        clock = ions.freeze(
            dict(
                call_index=final.step_index,
                elapsed_start_s=float(elapsed_s),
                elapsed_end_s=elapsed_s + forcing.dt_s,
                dt_s=forcing.dt_s,
                native_gate_calls=len(material.pump.gated.gate_updates),
                native_channel_calls=sum(not phase.skipped for phase in material.channel_phases),
                channel_native_dt=tuple(phase.native_dt for phase in material.channel_phases),
                channels_after_ordinary_refresh_before_commit=True,
                native_channel_temperature_scaling=False,
                event_calendar_claim=False,
            )
        )
        trial = CoupledTrial(parent, material, readout, voltage_trial, candidate, clock, "")
        return replace(trial, identity=ions.digest(trial))
    except ChannelJoinRejected:
        raise
    except Exception as error:
        raise ChannelJoinRejected(
            error,
            stage="coupled_trial",
            parent=parent,
            material=material,
            channel_phases=material.channel_phases if material else (),
            network=material.network if material else None,
            readout=readout,
            voltage_trial=error.trial
            if isinstance(error, voltage.VoltageRejected)
            else voltage_trial,
        ) from error


def _pump_material_step(binding, parent, forcing, live, late_callback):
    phase = active = None
    try:
        if type(binding) is not pump.Binding or binding.identity != ions.digest(
            pump.binding_record(binding)
        ):
            raise ValueError("Changed pump binding")
        checked = pump.bind(binding.gated_binding, ions.data(binding.definition))
        if ions.digest(pump.binding_record(checked)) != ions.digest(pump.binding_record(binding)):
            raise ValueError("Resealed pump coefficients differ from definition")
        if (
            type(parent) is not pump.State
            or parent.binding_identity != binding.identity
            or parent.identity
            != pump._state(binding, parent.gated, parent.rate_proxy_mol_m2_s).identity
            or (parent.rate_proxy_mol_m2_s.dtype != np.float64)
            or parent.rate_proxy_mol_m2_s.flags.writeable
            or (
                parent.rate_proxy_mol_m2_s.shape
                != (len(binding.gated_binding.material_binding.membrane_ids),)
            )
            or (not np.isfinite(parent.rate_proxy_mol_m2_s).all())
        ):
            raise ValueError("Require complete immutable pump/gate parent and rate cache")
        if type(live) is not pump.Packet:
            raise ValueError("Require typed complete live pump packet")
        normalized = pump.packet(binding, **live._asdict())
        if ions.record(normalized) != ions.record(live) or any(
            (value.flags.writeable for value in (live.block, live.rho_pump))
        ):
            raise ValueError("Changed live packet dtype or mutable controls")
        if live.met_concs is not None and (
            not isinstance(live.met_concs, MappingProxyType)
            or any((value.flags.writeable for value in live.met_concs.values()))
        ):
            raise ValueError("Ignored metabolic argument must retain immutable full provenance")
        k, ib = (binding.kernel, binding.gated_binding.material_binding)

        def pump_callback(membrane, bath, vm, storage):
            nonlocal phase
            old_proxy = parent.rate_proxy_mol_m2_s
            before = storage.copy()
            arithmetic = None
            scaled_na = scaled_k = applied_na = applied_k = np.zeros(len(vm))
            proxy = old_proxy
            with np.errstate(all="ignore"):
                if live.alpha_NaK == 0:
                    proxy = np.zeros(len(vm))
                if live.alpha_NaK > 0:
                    arithmetic = pump._arithmetic(
                        binding,
                        membrane[k.sodium],
                        bath[k.sodium],
                        membrane[k.potassium],
                        bath[k.potassium],
                        vm,
                        forcing.runtime_temperature_K,
                        live,
                    )
                    proxy = arithmetic.raw_rate_proxy_mol_m2_s
                    scaled_na = live.rho_pump * arithmetic.raw_sodium_flux_mol_m2_s
                    scaled_k = live.rho_pump * arithmetic.raw_potassium_flux_mol_m2_s
                    applied_na, applied_k = (scaled_na.copy(), scaled_k.copy())
                    if not ib.kernel.cluster_open:
                        applied_na[ib.kernel.boundary] = 0
                        applied_k[ib.kernel.boundary] = 0
                    storage[k.sodium] += applied_na
                    storage[k.potassium] += applied_k
            finite = all(
                (
                    np.isfinite(value).all()
                    for value in (scaled_na, scaled_k, applied_na, applied_k, storage, proxy)
                )
            )
            if arithmetic is not None:
                finite = finite and all((np.isfinite(value).all() for value in arithmetic))
            phase = pump.Phase(
                parent.gated.material.identity,
                live,
                *(
                    ions.freeze(value)
                    for value in (
                        membrane[k.sodium],
                        membrane[k.potassium],
                        np.asarray(bath[k.sodium]),
                        np.asarray(bath[k.potassium]),
                        vm,
                    )
                ),
                forcing.runtime_temperature_K,
                arithmetic,
                *(
                    ions.freeze(value)
                    for value in (
                        scaled_na,
                        scaled_k,
                        applied_na,
                        applied_k,
                        before,
                        storage,
                        old_proxy,
                        proxy,
                    )
                ),
                ions.freeze(
                    dict(
                        finite=bool(finite),
                        helper_called=live.alpha_NaK > 0,
                        proxy_cleared=live.alpha_NaK == 0,
                        proxy_retained=live.alpha_NaK < 0,
                        maintained_parameters_used=True,
                        metabolic_argument_used=False,
                        proxy_is_cycle_flux=False,
                        source_concentrations_committed=False,
                    )
                ),
                "",
            )
            phase = replace(phase, identity=ions.digest(phase))

        failure = None
        try:
            active = _active_material_step(
                binding.gated_binding, parent.gated, forcing, pump_callback, late_callback
            )
        except gated.GatedJoinRejected as error:
            active, failure = (error.material, error)
        if active is None:
            raise failure
        candidate = pump._state(binding, active.candidate, phase.rate_proxy_after_mol_m2_s)
        trial = pump.MaterialTrial(parent, phase, active, candidate, "")
        trial = replace(trial, identity=ions.digest(trial))
        if failure or not phase.diagnostics["finite"]:
            raise pump.PumpJoinRejected(
                failure or "Nonfinite published pump arithmetic/cache",
                stage="material_trial",
                parent=parent,
                material=trial,
                phase=phase,
            )
        return trial
    except pump.PumpJoinRejected:
        raise
    except Exception as error:
        raise pump.PumpJoinRejected(error, stage="source", parent=parent, phase=phase) from error


def _pumped_material_step(binding, parent, forcing, gate_callback, pump_callback, late_callback):
    trial = None
    try:
        if type(binding) is not ions.Binding or binding.identity != ions.digest(
            ions.binding_record(binding)
        ):
            raise ValueError("Changed binding")
        fresh = ions.bind(ions.data(binding.definition))
        if ions.record(ions.data(ions.binding_record(fresh))) != ions.record(
            ions.data(ions.binding_record(binding))
        ):
            raise ValueError("Resealed derived source operators changed")
        if type(parent) is not ions.State or parent.binding_identity != binding.identity:
            raise ValueError("Wrong state/binding association")
        checked = ions.state(binding, parent.values._asdict(), step_index=parent.step_index)
        if (
            checked.identity != parent.identity
            or ions.record(checked.values) != ions.record(parent.values)
            or any((v.flags.writeable for v in parent.values))
        ):
            raise ValueError("Changed state, dtype or mutable source buffer")
        if type(forcing) is not ions.Drive:
            raise ValueError("Require complete typed source drive")
        normalized = ions.drive(binding, **forcing._asdict())
        if (
            ions.record(normalized) != ions.record(forcing)
            or forcing.junction_block.flags.writeable
        ):
            raise ValueError("Changed drive dtype or mutable buffer")
        k = binding.kernel
        arrays = {key: value.copy() for key, value in parent.values._asdict().items()}
        cell, membrane, bath, vm, fm, fg, vgj, egj, exy, opening = arrays.values()
        frames = []
        clipped_mol = np.zeros(len(binding.ion_ids))

        def observe(stage, ion=None):
            frames.append(
                ions.Frame(
                    stage,
                    None if ion is None else binding.ion_ids[ion],
                    ions.Values(
                        *(
                            ions.freeze(value)
                            for value in (cell, membrane, bath, vm, fm, fg, vgj, egj, exy, opening)
                        )
                    ),
                )
            )

        observe("initial")
        fm.fill(0)
        fg.fill(0)
        observe("reset_flux")
        pump_callback(membrane, bath, vm, fm)
        observe("pump_accumulated")
        failure = None
        with np.errstate(all="ignore"):
            for i in k.moving:
                ones = np.ones(len(binding.membrane_ids))
                leak = ions._electroflux(
                    bath[i],
                    membrane[i],
                    k.membrane_diffusion_m2_s[i],
                    ones * k.membrane_thickness_m,
                    k.valence[i] * ones,
                    vm,
                    forcing.runtime_temperature_K,
                    k,
                )
                if not k.cluster_open:
                    leak[k.boundary] = 0
                fm[i] += leak
                observe("membrane_flux", i)
                vgj = vm[k.partner] - vm[np.arange(len(vm))]
                egj = -vgj / k.gap_length_m
                exy = np.column_stack((egj * k.normal_xy[:, 0], egj * k.normal_xy[:, 1]))
                opening = gate_callback(i, vgj, opening)
                gap = ions._electroflux(
                    membrane[i][np.arange(len(vm))],
                    membrane[i][k.partner],
                    k.gap_diffusion_m2_s[i] * k.junction_surface_fraction * opening,
                    k.gap_length_m * np.ones(len(vm)),
                    k.valence[i] * np.ones(len(vm)),
                    vgj,
                    k.configured_temperature_K,
                    k,
                )
                gap[k.boundary] = 0
                fg[i] = fg[i] + gap
                observe("junction_flux", i)
                membrane[i] = cell[i][k.owner] * 1
                observe("refresh_at_mem", i)
            late_callback((cell, membrane, bath, vm, fm, fg, vgj, egj, exy, opening), observe)
            for i in k.moving:
                delta = np.dot(k.owner_sum, fm[i] * k.area_m2) / k.cell_volume_m3
                cell[i] = cell[i] + delta * forcing.dt_s
                membrane[i] = cell[i][k.owner]
                bath[i] = (bath[i] + -fm[i] * (k.area_m2 / k.bath_volume_m3) * forcing.dt_s).mean()
                observe("membrane_commit", i)
                delta_gap = np.dot(k.owner_sum, -fg[i] * k.area_m2) / k.cell_volume_m3
                cell[i] += forcing.dt_s * delta_gap
                observe("junction_commit", i)
                negative, nan = (cell[i] < 0, np.isnan(cell[i]))
                clipped_mol[i] = np.sum(np.where(negative, -cell[i], 0) * k.cell_volume_m3)
                cell[i][negative] = 0
                if np.any(nan):
                    observe("clip_bulk_failure", i)
                    failure = "Native no_negs sees NaN after its negative-value clipping"
                    break
                observe("clip_bulk", i)
            final = frames[-1].values
            candidate = ions.State(binding.identity, parent.step_index + 1, final, "")
            candidate = replace(
                candidate, identity=ions.digest((binding.identity, candidate.step_index, final))
            )
            cell_change = np.sum((cell - parent.values.cell_mol_m3) * k.cell_volume_m3, axis=1)
            bath_change = (bath - parent.values.bath_mol_m3) * k.bath_volume_m3
            membrane_transfer = forcing.dt_s * np.sum(fm * k.area_m2, axis=1)
            junction_transfer = forcing.dt_s * np.sum(fg * k.area_m2, axis=1)
            diagnostics = ions.freeze(
                dict(
                    finite=bool(
                        all(
                            (np.isfinite(value).all() for frame in frames for value in frame.values)
                        )
                    ),
                    moving_ids=tuple((binding.ion_ids[i] for i in k.moving)),
                    cell_change_mol=cell_change,
                    bath_change_mol=bath_change,
                    membrane_transfer_mol=membrane_transfer,
                    junction_transfer_mol=junction_transfer,
                    clipping_added_mol=clipped_mol,
                    cell_accounting_residual_mol=cell_change
                    - (membrane_transfer - junction_transfer + clipped_mol),
                    source_mixed_bath_residual_mol=bath_change + membrane_transfer / len(vm),
                    total_cell_bath_change_mol=cell_change + bath_change,
                    final_membrane_bulk_difference_mol_m3=membrane - cell[:, k.owner],
                    negative_bath_retained=bool(np.any(bath < 0)),
                    negative_membrane_retained=bool(np.any(membrane < 0)),
                    source_voltage_nonce_delta_V=vm - parent.values.voltage_V,
                    field_feedback_computed=False,
                    material_conservation_inferred=False,
                )
            )
        trial = ions.Trial(parent, forcing, tuple(frames), candidate, diagnostics, "")
        trial = replace(trial, identity=ions.digest(trial))
        if failure or not diagnostics["finite"]:
            raise ValueError(failure or "Nonfinite literal source intermediate/output")
        return trial
    except Exception as error:
        raise ions.IonJoinRejected(
            error,
            stage="ion_trial" if trial is not None else "source",
            parent=parent,
            drive=forcing,
            trial=trial,
        ) from error


def _active_material_step(binding, parent, forcing, pump_callback, late_callback):
    material = None
    updates = []
    candidate = None
    try:
        if type(binding) is not gated.Binding or binding.identity != ions.digest(
            gated.binding_record(binding)
        ):
            raise ValueError("Changed active-gate binding")
        checked_binding = gated.bind(
            binding.material_binding, binding.voltage_binding, ions.data(binding.definition)
        )
        if ions.digest(gated.binding_record(checked_binding)) != ions.digest(
            gated.binding_record(binding)
        ):
            raise ValueError("Resealed gate definition")
        if (
            type(parent) is not gated.State
            or parent.binding_identity != binding.identity
            or parent.identity
            != gated._state(binding, parent.material, parent.memory, parent.initialization).identity
        ):
            raise ValueError("Changed active gate/material association")
        if type(parent.memory.updates) is not int or parent.memory.updates < 0:
            raise ValueError("Invalid source gate invocation count")
        expected_updates = (
            parent.material.step_index - parent.initialization.parent.step_index
        ) * len(binding.material_binding.kernel.moving)
        if parent.memory.updates != expected_updates:
            raise ValueError("Gate invocation count differs from the ordered material-call lineage")
        for value in parent.memory[:4]:
            if (
                not isinstance(value, np.ndarray)
                or value.dtype != np.float64
                or value.shape != (len(binding.material_binding.membrane_ids),)
                or value.flags.writeable
                or (not np.isfinite(value).all())
            ):
                raise ValueError("Require immutable complete gate cache")
        last = [
            parent.memory.alpha_per_ms,
            parent.memory.raw_beta_per_ms,
            parent.memory.beta_per_ms,
        ]

        def gate_callback(i, vgj, opening):
            with np.errstate(all="ignore"):
                alpha, raw_beta, beta = gated._rates(vgj, binding.threshold_mV)
                dt_ms = forcing.dt_s * 1000.0
                unblocked = (opening + dt_ms * (alpha + beta * binding.minimum)) / (
                    1 + alpha * dt_ms + beta * dt_ms
                )
                stored = forcing.junction_block * unblocked
            updates.append(
                gated.GateFrame(
                    binding.material_binding.ion_ids[i],
                    parent.memory.updates + len(updates) + 1,
                    *(
                        ions.freeze(v)
                        for v in (vgj, opening, alpha, raw_beta, beta, unblocked, stored)
                    ),
                    forcing.dt_s,
                    dt_ms,
                )
            )
            last[:] = (alpha, raw_beta, beta)
            return stored

        failure = None
        try:
            material = _pumped_material_step(
                binding.material_binding,
                parent.material,
                forcing,
                gate_callback,
                pump_callback,
                late_callback,
            )
        except ions.IonJoinRejected as error:
            material, failure = (error.trial, error)
        if material is None:
            raise failure
        memory = gated.Memory(
            *(ions.freeze(v) for v in last),
            parent.memory.class_open,
            parent.memory.updates + len(updates),
        )
        candidate = gated._state(binding, material.candidate, memory, parent.initialization)
        trial = gated.MaterialTrial(parent, material, tuple(updates), candidate, "")
        trial = replace(trial, identity=ions.digest(trial))
        if failure:
            raise gated.GatedJoinRejected(
                failure, stage="material_trial", parent=parent, material=trial
            )
        return trial
    except gated.GatedJoinRejected:
        raise
    except Exception as error:
        raise gated.GatedJoinRejected(error, stage="source", parent=parent) from error
