"""Rectangular normal join with configured transporters before channels/chemistry.

Bath rows have original [ion,membrane] ndarray ownership and scalar-returning
Co writes broadcast into those rows. CaATP executes after ordinary refresh and
before late channels/deferred commit. ER/buffer state is a separate dependency.
STATIC PREPARATION: this new representation has no numerical qualification yet.
"""

import math
from collections.abc import Mapping
from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import NamedTuple

import numpy as np

from cells.core.errors import NumericalError
from cells.processes import betse_calcium_atp_source as calcium_source
from cells.processes import betse_channel_catalog_source as catalog
from cells.processes import betse_normal_current as current
from cells.processes import betse_normal_gated_join as gated
from cells.processes import betse_normal_ion_join as ions
from cells.processes import betse_normal_pump_join as pump
from cells.processes import betse_normal_transporter_source as network_source
from cells.processes import betse_normal_voltage as voltage

LAW_ID = "betse_normal_configured_transporter_execution_v1_5_0@1"
SOURCE_REVISION = pump.SOURCE_REVISION
CLASSES = tuple(catalog.CLASSES)
ROUTES = catalog.ROUTES


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
    calcium_rate_proxy_mol_m2_s: object
    initialization: object
    network_controls: object
    network_cache: object
    identity: str


class Packet(NamedTuple):
    phase_kind: str
    modulators: object
    substances_affect_charge: bool


@dataclass(frozen=True, slots=True)
class RoutePhase:
    ion_id: str
    relative_permeability: float
    sampled_bulk_mM: object
    sampled_membrane_mM: object
    sampled_bath_mM: object
    diffusion_m2_s: object
    flux_mol_m2_s: object
    network_current_before_A_m2: object
    network_current_after_A_m2: object
    values_before: ions.Values
    values_after: ions.Values
    cache_after: object


@dataclass(frozen=True, slots=True)
class ChannelPhase:
    channel_id: str
    class_name: str
    skipped: bool
    call_index: int
    cache_before: object
    cache_after: object
    voltage_before_V: object
    voltage_after_V: object
    routes: tuple
    values_before: ions.Values
    values_after: ions.Values
    dt_s: float
    native_dt: float


@dataclass(frozen=True, slots=True)
class MaterialTrial:
    parent: State
    pump: pump.MaterialTrial
    calcium_handler: object
    network_feedback: object
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


class MissingCoupledState(ValueError):
    """An explicit scientific dependency cannot be silently replaced."""


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
        or set(raw) != {"kind", "provenance", "channels", "calcium_handler", "network"}
        or raw["kind"] != "cells.betse_normal_transporter_join_inputs@1"
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
        for role, _ in ROUTES[row["class_name"]]:
            expected = {"Na": 1, "K": 1, "Cl": -1, "Ca": 2}[role]
            if role not in ib.ion_ids or ib.kernel.valence[ib.ion_ids.index(role)] != expected:
                raise ValueError("Missing explicitly supplied native ion role: " + role)
    if "Ca" not in ib.ion_ids:
        if raw["calcium_handler"] is not None:
            raise ValueError("Calcium policy requires an explicit live Ca row")
    else:
        if ib.kernel.valence[ib.ion_ids.index("Ca")] != 2:
            raise ValueError("Native Ca role must have valence+2")
        policy = raw["calcium_handler"]
        if (
            type(policy) is not dict
            or set(policy) != {"Ca_dyn", "maintained", "kinetics", "provenance"}
            or type(policy["Ca_dyn"]) is not int
            or policy["Ca_dyn"] != 0
        ):
            raise MissingCoupledState(
                "ER/buffer handling requires separate complete owned state; "
                "Ca_dyn must be explicit0"
            )
        if (
            type(policy["maintained"]) is not dict
            or set(policy["maintained"]) != {"cATP", "cADP", "cPi"}
            or type(policy["kinetics"]) is not dict
            or set(policy["kinetics"]) != {"KmCa_Ca", "KmCa_ATP", "deltaGATP"}
            or not isinstance(policy["provenance"], str)
            or not policy["provenance"].strip()
        ):
            raise ValueError("Require complete native CaATP maintained pools and kinetics")
        for key, value in (policy["maintained"] | policy["kinetics"]).items():
            if type(value) not in (int, float) or not math.isfinite(value):
                raise ValueError("Require finite original calcium parameter: " + key)
            if key.startswith("Km") and value <= 0:
                raise ValueError("Require positive native calcium Km")
        if (
            policy["maintained"] != ions.data(pump_binding.definition["maintained"])
            or policy["kinetics"]["deltaGATP"] != pump_binding.kernel.delta_g_J_mol
        ):
            raise ValueError(
                "NaK and CaATP must share the actual source maintained pools/deltaGATP"
            )
    network_source.validate(
        raw["network"],
        ib,
        pump_binding.gated_binding.voltage_binding.current_binding,
        pump_binding.gated_binding.voltage_binding.kernel.configured_temperature_K,
    )
    if (
        list(raw["network"]["membrane_to_environment"])
        != pump_binding.gated_binding.voltage_binding.kernel.membrane_to_grid.tolist()
    ):
        raise MissingCoupledState(
            "Network sampling must share the supplied native membrane-to-environment map"
        )
    if not np.array_equal(
        np.asarray(raw["network"]["radius_m"], np.float64),
        pump_binding.gated_binding.voltage_binding.kernel.radius_m,
    ):
        raise ValueError("Molecule intracellular radius must share the explicit voltage geometry")
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
    return ions.freeze(catalog.initialize(row["class_name"], vm, row["targets"]))


def _run_cache(row, incoming, vm, dt, modulator):
    return catalog.update(row["class_name"], incoming, vm, dt, modulator)


def _state(
    binding,
    parent,
    caches,
    calls,
    initialization,
    calcium_rate_cache,
    network_controls,
    network_cache,
):
    result = State(
        binding.identity,
        parent,
        ions.freeze(caches),
        tuple(calls),
        ions.freeze(calcium_rate_cache),
        ions.freeze(initialization),
        ions.freeze(network_controls),
        ions.freeze(network_cache),
        "",
    )
    return replace(result, identity=ions.digest(result))


def initialize(binding, parent, *, initial_calcium_rate_proxy_mol_m2_s):
    if type(parent) is not pump.State or parent.binding_identity != binding.pump_binding.identity:
        raise ValueError("Require original pump/gate/material parent")
    if binding.definition["calcium_handler"] is None:
        if initial_calcium_rate_proxy_mol_m2_s is not None:
            raise ValueError("No calcium rate cache without a live Ca row")
        calcium_cache = None
    else:
        calcium_cache = current._array(
            initial_calcium_rate_proxy_mol_m2_s,
            (len(parent.rate_proxy_mol_m2_s),),
            "explicit unchanged calcium rate cache",
        )
    caches = []
    for row in binding.definition["channels"]:
        try:
            caches.append(_init_cache(row, parent.gated.material.values.voltage_V))
        except Exception as error:
            partial = dict(
                channel_id=row["id"],
                prior_caches=tuple(caches),
                failed_core_cache=error.cache
                if isinstance(error, catalog.InitializationRefused)
                else {},
                source_exception=error.source_exception
                if isinstance(error, catalog.InitializationRefused)
                else type(error).__name__,
                no_repair_applied=True,
            )
            raise ChannelJoinRejected(
                error,
                stage="channel_initialization",
                parent=parent,
                initialization=ions.freeze(partial),
            ) from error
    return _state(
        binding,
        parent,
        caches,
        [0] * len(caches),
        caches,
        calcium_cache,
        network_source.controls(
            ions.data(binding.definition["network"]["initial_controls"]),
            len(parent.rate_proxy_mol_m2_s),
        ),
        network_source.initial_cache(binding.definition["network"]),
    )


def _values(arrays):
    """Freeze each array while retaining the original typed Values container."""
    return ions.Values(*(ions.freeze(value) for value in arrays))


def material_step(
    binding,
    parent,
    forcing,
    live_pump,
    live,
    live_calcium,
    *,
    extra_charge_C_m3,
    extra_current_A_m2,
    scheduled_controls=None,
    before_calcium=None,
    before_network=None,
    before_transporters=None,
):
    material = None
    phases = []
    network = {}
    feedback = {}
    calcium_phase = {}
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
                parent.calcium_rate_proxy_mol_m2_s,
                parent.network_controls,
                parent.network_cache,
            ).identity
            or len(parent.channel_caches) != len(binding.definition["channels"])
            or len(parent.channel_calls) != len(parent.channel_caches)
            or any(type(c) is not int or c < 0 for c in parent.channel_calls)
        ):
            raise ValueError("Changed channel parent/cache association")
        if binding.definition["calcium_handler"] is not None:
            calcium = parent.calcium_rate_proxy_mol_m2_s
            if (
                not isinstance(calcium, np.ndarray)
                or calcium.dtype != np.float64
                or calcium.shape != parent.pump.rate_proxy_mol_m2_s.shape
                or calcium.flags.writeable
                or not np.isfinite(calcium).all()
            ):
                raise ValueError("Require explicit immutable unchanged CaATP cache")
        elif parent.calcium_rate_proxy_mol_m2_s is not None:
            raise ValueError("Unexpected CaATP cache without live Ca state")
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
                set(catalog.CALCULATED_FIELDS[row["class_name"]]) | {"P"} if calls else set()
            )
            if set(cache) != expected_keys:
                raise ValueError("Missing or unexpected original class state")
            for key in ("m", "h"):
                if key not in initial:
                    if key in cache:
                        raise ValueError("Invented absent native gate")
                    continue
                shape = initial[key].shape if isinstance(initial[key], np.ndarray) else ()
                if np.asarray(cache[key]).shape != shape:
                    raise ValueError("Changed original scalar/target gate shape")
            dynamic = {
                "m",
                "h",
                "P",
                "DChan",
                "chan_flux",
                *catalog.CALCULATED_FIELDS[row["class_name"]],
            }
            for key in set(initial) - dynamic - {"modulator"}:
                if ions.record(cache[key]) != ions.record(initial[key]):
                    raise ValueError("Changed fixed source class metadata")
            for key in ("chan_flux", "DChan", "P"):
                if key == "P" and not calls or key == "DChan" and not calls:
                    continue
                if not isinstance(cache[key], np.ndarray) or cache[key].shape != (
                    len(parent.pump.rate_proxy_mol_m2_s),
                ):
                    raise ValueError("Changed original membrane cache shape")
        if (
            type(live_calcium) is not CalciumPacket
            or ions.record(calcium_packet(binding, **live_calcium._asdict()))
            != ions.record(live_calcium)
            or live_calcium.block.flags.writeable
        ):
            raise ValueError("Require immutable explicit live CaATP alpha/block packet")
        ib = binding.pump_binding.gated_binding.material_binding
        extra_charge_C_m3 = current._array(
            extra_charge_C_m3, (len(ib.cell_ids),), "explicit incoming network/readout charge"
        )
        extra_current_A_m2 = current._array(
            extra_current_A_m2, (len(ib.membrane_ids),), "explicit incoming network/readout current"
        )
        effective_controls = network_source.controls(
            ions.data(
                parent.network_controls if scheduled_controls is None else scheduled_controls
            ),
            len(ib.membrane_ids),
        )
        if not np.array_equal(
            forcing.junction_block, effective_controls["gj_block"]
        ) or not np.array_equal(live_pump.block, effective_controls["NaKATP_block"]):
            raise ValueError(
                "Effective native forcing must use the owned or explicitly scheduled controls"
            )
        caches, calls = list(parent.channel_caches), list(parent.channel_calls)

        def late_callback(arrays, observe):
            cell, membrane, bath, vm, fm, fg, vgj, egj, exy, opening = arrays
            extra = np.zeros(len(vm))
            network_values_before = _values(arrays)
            if binding.definition["calcium_handler"] is None:
                if live_calcium.alpha_Ca != 0:
                    raise ValueError("No CaATP without an explicit Ca row")
                calcium_phase.update(
                    enabled=False,
                    rate_before=None,
                    rate_after=None,
                    arithmetic=None,
                    source_completed=True,
                    values_before=ions.data(_values(arrays)),
                    values_after=ions.data(_values(arrays)),
                )
                if before_calcium is not None:
                    before_calcium(ions.freeze(calcium_phase))
            else:
                i = ib.ion_ids.index("Ca")
                policy = binding.definition["calcium_handler"]
                parameters = (
                    dict(policy["maintained"])
                    | dict(policy["kinetics"])
                    | dict(
                        alpha_Ca=live_calcium.alpha_Ca, F=ib.kernel.F_C_mol, R=ib.kernel.R_J_mol_K
                    )
                )
                calcium_phase.update(
                    values_before=ions.data(_values(arrays)),
                    alpha_Ca=live_calcium.alpha_Ca,
                    parameters=parameters,
                    rate_before=parent.calcium_rate_proxy_mol_m2_s,
                    rate_after=parent.calcium_rate_proxy_mol_m2_s,
                    rho_pump=live_pump.rho_pump,
                    block_unused=live_calcium.block,
                    met_unused=live_pump.met_concs,
                    dt_s=forcing.dt_s,
                    runtime_temperature_K=forcing.runtime_temperature_K,
                    membrane_before_mM=ions.freeze(membrane[i]),
                    bath_before_mM=ions.freeze(bath[i]),
                    voltage_V=ions.freeze(vm),
                    stored_before=ions.freeze(fm),
                    arithmetic=None,
                    source_rate_aliases_masked_flux=True,
                    Ca_dyn=0,
                    ER_executed=False,
                )
                if before_calcium is not None:
                    before_calcium(ions.freeze(calcium_phase))
                if live_calcium.alpha_Ca > 0:
                    core = None
                    try:
                        core = calcium_source.evaluate(
                            membrane_mM=membrane[i],
                            bath_mM=bath[i],
                            voltage_V=vm,
                            runtime_temperature_K=forcing.runtime_temperature_K,
                            parameters=parameters,
                            block=live_calcium.block,
                            met=live_pump.met_concs,
                        )
                    except calcium_source.CalciumSourceRefused as error:
                        core = error.partial
                        membrane[i] = core.membrane_after_mM
                        bath[i] = core.bath_after_mM
                        calcium_phase.update(
                            arithmetic=core,
                            source_failure=core.failure,
                            values_after=ions.data(_values(arrays)),
                        )
                        observe("calcium_handler_failure", i)
                        raise
                    membrane[i] = core.membrane_after_mM
                    bath[i] = core.bath_after_mM
                    masked = core.flux_mol_m2_s.copy()
                    if not ib.kernel.cluster_open:
                        masked[ib.kernel.boundary] = 0
                    # Source rate is the SAME array as raw flux, masked in place,
                    # before the single no-ECM rho multiplication in storage.
                    applied = live_pump.rho_pump * masked
                    fm[i] += applied
                    calcium_phase.update(
                        arithmetic=core,
                        rate_after=ions.freeze(masked),
                        applied_flux_mol_m2_s=ions.freeze(applied),
                    )
                calcium_phase.update(
                    stored_after=ions.freeze(fm),
                    values_after=ions.data(_values(arrays)),
                    cache_retained=live_calcium.alpha_Ca <= 0,
                    source_completed=True,
                )
                observe("calcium_handler", i)

            core, sim, geometry, p, phase = network_source.prepare(
                arrays,
                ion_ids=ib.ion_ids,
                parameters=dict(
                    runtime_temperature_K=forcing.runtime_temperature_K,
                    R=ib.kernel.R_J_mol_K,
                    F=ib.kernel.F_C_mol,
                    dt_s=forcing.dt_s,
                    valence=ib.kernel.valence,
                    substances_affect_charge=live.substances_affect_charge,
                    incoming_extra_charge=extra_charge_C_m3,
                    incoming_extra_current=extra_current_A_m2,
                    configured_temperature_K=ib.kernel.configured_temperature_K,
                    membrane_thickness_m=ib.kernel.membrane_thickness_m,
                    bath_volume_m3=ib.kernel.bath_volume_m3,
                    cluster_open=ib.kernel.cluster_open,
                    rho_pump=live_pump.rho_pump,
                    geometry=dict(
                        owner=ib.kernel.owner,
                        partner=ib.kernel.partner,
                        boundary=ib.kernel.boundary,
                        membrane_area_m2=ib.kernel.area_m2,
                        cell_volume_m3=ib.kernel.cell_volume_m3,
                        owner_sum=ib.kernel.owner_sum,
                        gap_length_m=ib.kernel.gap_length_m,
                    ),
                ),
                definition=binding.definition["network"],
                incoming_controls=effective_controls,
                incoming_cache=parent.network_cache,
                phase_kind=live.phase_kind,
            )
            extra = core.extra_J_mem
            writes = []
            core._observe_control = lambda name, value, actual: writes.append(
                ions.freeze(
                    dict(
                        rule_id=name,
                        target=core.modulators[name].target_label,
                        value=np.array(value, copy=True),
                        gj_block=np.array(actual.gj_block, copy=True),
                        NaKATP_block=np.array(actual.NaKATP_block, copy=True),
                    )
                )
            )
            observe("network_clear")
            transporter_execution = network_source.execution_inputs(
                core,
                sim,
                geometry,
                p,
                binding.definition["network"],
                ib.ion_ids,
                ions.data(_values(arrays)),
            )
            feedback["transporter_execution"] = transporter_execution
            if before_transporters is not None:
                before_transporters(ions.freeze(transporter_execution))
            try:
                with np.errstate(all="ignore"):
                    core.run_loop_transporters(0.0, sim, geometry, p)
                transporter_execution["source_completed"] = True
                observe("network_transporters")
            finally:
                transporter_execution.update(
                    values_after=ions.data(_values(arrays)),
                    concentrations_after=network_source.concentrations(core),
                    fluxes_after=network_source.fluxes(core),
                    extra_current_after_A_m2=core.extra_J_mem.copy(),
                    frames=tuple(core.transporter_frames),
                )
            with np.errstate(all="ignore"):
                for slot, row in enumerate(binding.definition["channels"]):
                    before = _values(arrays)
                    old_cache = caches[slot]
                    skip = live.phase_kind == "INIT" and not row["init_active"]
                    route_phases = []
                    if not skip:
                        cache = _run_cache(
                            row, old_cache, vm, forcing.dt_s, live.modulators[row["id"]]
                        )
                        calls[slot] += 1
                        observe("channel_update")
                        # Native order is class-specific; zero-weight routes still
                        # call get_ion/electroflux/update_Co and consume the nonce.
                        for ion_id, rel_perm in zip(cache["ions"], cache["rel_perm"], strict=True):
                            i = ib.ion_ids.index(ion_id)
                            sampled_bulk = cell[i].copy()
                            sampled_mem = cell[i][ib.kernel.owner].copy()
                            sampled_bath = np.asarray(bath[i]).copy()
                            route_before = _values(arrays)
                            current_before = extra.copy()
                            diffusion = (
                                cache["P"]
                                * rel_perm
                                * row["maxDm_m2_s"]
                                * live.modulators[row["id"]]
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
                                + -flux
                                * (ib.kernel.area_m2 / ib.kernel.bath_volume_m3)
                                * forcing.dt_s
                            ).mean()
                            extra += -flux * ib.kernel.F_C_mol * ib.kernel.valence[i]
                            # The native class retains ONLY the last ion route.
                            cache.update(chan_flux=flux, DChan=diffusion)
                            route_phases.append(
                                RoutePhase(
                                    ion_id,
                                    float(rel_perm),
                                    ions.freeze(sampled_bulk),
                                    ions.freeze(sampled_mem),
                                    ions.freeze(sampled_bath),
                                    ions.freeze(diffusion),
                                    ions.freeze(flux),
                                    ions.freeze(current_before),
                                    ions.freeze(extra),
                                    route_before,
                                    _values(arrays),
                                    ions.freeze(cache),
                                )
                            )
                            observe("channel_direct", i)
                        caches[slot] = ions.freeze(cache)
                    else:
                        observe("channel_skipped")
                    consumes_clock = not skip and old_cache.get("kinetic_gate", True)
                    phases.append(
                        ChannelPhase(
                            row["id"],
                            row["class_name"],
                            skip,
                            calls[slot],
                            old_cache,
                            caches[slot],
                            before.voltage_V,
                            _values(arrays).voltage_V,
                            tuple(route_phases),
                            before,
                            _values(arrays),
                            forcing.dt_s,
                            forcing.dt_s * old_cache["time_unit"] if consumes_clock else 0.0,
                        )
                    )
                feedback.update(
                    values_before=ions.data(_values(arrays)),
                    controls_before=effective_controls,
                    molecule_states_before=network_source.snapshot(core.molecules),
                    molecular_geometry=dict(
                        owner=ib.kernel.owner,
                        partner=ib.kernel.partner,
                        boundary=ib.kernel.boundary,
                        membrane_area_m2=ib.kernel.area_m2,
                        cell_volume_m3=ib.kernel.cell_volume_m3,
                        owner_sum=ib.kernel.owner_sum,
                        gap_length_m=ib.kernel.gap_length_m,
                        radius_m=binding.definition["network"]["radius_m"],
                    ),
                    configured_temperature_K=ib.kernel.configured_temperature_K,
                    membrane_thickness_m=ib.kernel.membrane_thickness_m,
                    bath_volume_m3=ib.kernel.bath_volume_m3,
                    cluster_open=ib.kernel.cluster_open,
                    gap_open=opening.copy(),
                    cache_before=parent.network_cache,
                    scheduled_control_outputs_supplied=scheduled_controls is not None,
                    definition=binding.definition["network"],
                    ion_ids=ib.ion_ids,
                    valence=ib.kernel.valence,
                    runtime_temperature_K=forcing.runtime_temperature_K,
                    F=ib.kernel.F_C_mol,
                    R=ib.kernel.R_J_mol_K,
                    dt_s=forcing.dt_s,
                    incoming_channel_current_A_m2=extra.copy(),
                    phase_kind=live.phase_kind,
                    substances_affect_charge=live.substances_affect_charge,
                    conditioned_before_model_network=True,
                    executed_chemistry=False,
                    control_writes=writes,
                    source_completed=False,
                )
                if before_network is not None:
                    before_network(ions.freeze(feedback))
                try:
                    core.run_loop_modulators(sim, geometry, p)
                    observe("network_modulators")
                    core.run_loop(phase, 0.0)
                    observe("network_molecule_chemistry")
                    feedback.update(
                        source_completed=True, configured_chemistry_run_loop_completed=True
                    )
                finally:
                    feedback.update(
                        cache_after=network_source.cache(core),
                        rhs=core.rhs,
                        molecule_frames=tuple(core.molecule_frames),
                        mover_frames=tuple(core.mover_frames),
                        molecule_states_after=network_source.snapshot(core.molecules),
                        chemical_rhs_evaluated=any(
                            row["stage"] == "rhs_ready" for row in core.molecule_frames
                        ),
                        executed_chemistry=any(
                            row["stage"] == "rhs_ready" for row in core.molecule_frames
                        )
                        and (
                            bool(binding.definition["network"]["reactions"])
                            or any(
                                row["growth"]["enabled"]
                                for row in binding.definition["network"]["molecules"]
                            )
                        ),
                        molecular_transports_completed=sum(
                            row["stage"] == "transport_after" for row in core.molecule_frames
                        ),
                        values_after=ions.data(_values(arrays)),
                        controls_after=dict(
                            gj_block=np.array(sim.gj_block, copy=True),
                            NaKATP_block=np.array(sim.NaKATP_block, copy=True),
                        ),
                    )
                feedback["controls_after"] = network_source.controls(
                    ions.data(feedback["controls_after"]), len(vm)
                )
                feedback["cache_after"] = network_source.checked_cache(
                    feedback["cache_after"], binding.definition["network"]
                )
                network.update(
                    values_before=network_values_before,
                    values_after=_values(arrays),
                    extra_current_A_m2=ions.freeze(extra),
                    extra_charge_C_m3=ions.freeze(core.extra_rho_cells),
                    substances_affect_charge=live.substances_affect_charge,
                    current_publication="replace"
                    if live.substances_affect_charge
                    else "retain incoming",
                    aliases_follow_live_rows=True,
                    user_molecules=len(core.molecules),
                    reactions=len(core.reactions),
                    energy_charge=ions.freeze(core.chi),
                    ordinary_Dm_unchanged=True,
                    channel_flux_added_to_ordinary_storage=False,
                    source_channel_flux_boundary_mask=False,
                )
                observe("network_publish")

        material = _pump_material_step(
            binding.pump_binding, parent.pump, forcing, live_pump, late_callback
        )
        candidate = _state(
            binding,
            material.candidate,
            caches,
            calls,
            parent.initialization,
            calcium_phase["rate_after"],
            feedback["controls_after"],
            feedback["cache_after"],
        )
        trial = MaterialTrial(
            parent,
            material,
            ions.freeze(calcium_phase),
            ions.freeze(feedback),
            tuple(phases),
            ions.freeze(network),
            candidate,
            "",
        )
        trial = replace(trial, identity=ions.digest(trial))
        if (
            calcium_phase.get("arithmetic") is not None and not calcium_phase["arithmetic"].finite
        ) or any(
            not np.isfinite(value).all()
            for cache in caches
            for value in cache.values()
            if isinstance(value, np.ndarray)
        ):
            raise ChannelJoinRejected(
                "Nonfinite published calcium/channel cache",
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
            network=ions.freeze(
                dict(network, calcium_handler=calcium_phase, network_feedback=feedback)
            ),
        ) from error


def advance(
    binding,
    parent,
    forcing,
    live_pump,
    live,
    live_calcium,
    *,
    before_calcium=None,
    before_network=None,
    before_transporters=None,
    scheduled_controls=None,
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
        material = material_step(
            binding,
            parent,
            forcing,
            live_pump,
            live,
            live_calcium,
            extra_charge_C_m3=extra_charge_C_m3,
            extra_current_A_m2=extra_current_A_m2,
            scheduled_controls=scheduled_controls,
            before_calcium=before_calcium,
            before_network=before_network,
            before_transporters=before_transporters,
        )
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
        final = vector_state(
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
            material.candidate.calcium_rate_proxy_mol_m2_s,
            material.candidate.network_controls,
            material.candidate.network_cache,
        )
        clock = ions.freeze(
            dict(
                call_index=final.step_index,
                elapsed_start_s=float(elapsed_s),
                elapsed_end_s=elapsed_s + forcing.dt_s,
                dt_s=forcing.dt_s,
                native_gate_calls=len(material.pump.gated.gate_updates),
                native_channel_calls=sum(not phase.skipped for phase in material.channel_phases),
                native_channel_ion_routes=sum(
                    len(phase.routes) for phase in material.channel_phases
                ),
                channel_native_dt=tuple(phase.native_dt for phase in material.channel_phases),
                channels_after_ordinary_refresh_before_commit=True,
                native_channel_temperature_scaling=False,
                event_calendar_claim=False,
                network_feedback_after_ordinary=True,
                native_network_modulator_calls=len(binding.definition["network"]["modulators"]),
                executed_chemistry=material.network_feedback["executed_chemistry"],
                scheduled_control_outputs_supplied=scheduled_controls is not None,
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
        checked = vector_state(binding, parent.values._asdict(), step_index=parent.step_index)
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
            bath_site_change = (bath - parent.values.bath_mol_m3) * k.bath_volume_m3
            bath_change = np.sum(bath_site_change, axis=1)
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
                    bath_site_change_mol=bath_site_change,
                    source_mixed_bath_residual_mol=bath_change + membrane_transfer,
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


def vector_state(binding, raw, *, step_index=0):
    if set(raw) != set(ions.Values._fields) or type(step_index) is not int or step_index < 0:
        raise ValueError("Require all original numeric state fields and a nonnegative step index")
    i, n, m = (len(binding.ion_ids), len(binding.cell_ids), len(binding.membrane_ids))
    shapes = ((i, n), (i, m), (i, m), (m,), (i, m), (i, m), (m,), (m,), (m, 2), (m,))
    values = ions.Values(
        *(
            current._array(raw[key], shape, key, nonnegative=key in {"cell_mol_m3", "gap_open"})
            for key, shape in zip(ions.Values._fields, shapes, strict=True)
        )
    )
    result = ions.State(binding.identity, step_index, values, "")
    return replace(result, identity=ions.digest((result.binding_identity, step_index, values)))


def _initialize_gate(binding, parent, *, initial_block):
    initialization = None
    try:
        if type(binding) is not gated.Binding or binding.identity != ions.digest(
            gated.binding_record(binding)
        ):
            raise ValueError("Changed gate binding")
        normalized = gated.bind(
            binding.material_binding, binding.voltage_binding, ions.data(binding.definition)
        )
        if ions.digest(gated.binding_record(normalized)) != ions.digest(
            gated.binding_record(binding)
        ):
            raise ValueError("Resealed gate parameters differ from definition")
        checked = vector_state(
            binding.material_binding, parent.values._asdict(), step_index=parent.step_index
        )
        if (
            parent.identity != checked.identity
            or ions.record(checked.values) != ions.record(parent.values)
            or any((v.flags.writeable for v in parent.values))
        ):
            raise ValueError("Changed or mutable explicit initial material state")
        block = current._array(
            initial_block, (len(parent.values.voltage_V),), "initial gate block", nonnegative=True
        )
        cached = parent.values.junction_voltage_V
        with np.errstate(all="ignore"):
            alpha, raw_beta, beta = gated._rates(cached, binding.threshold_mV)
            class_open = block * (alpha / (alpha + beta) + binding.minimum)
        memory = gated.Memory(*(ions.freeze(v) for v in (alpha, raw_beta, beta, class_open)), 0)
        initialization = gated.Initialization(parent, cached, block, memory, "")
        initialization = replace(initialization, identity=ions.digest(initialization))
        if not all((np.isfinite(v).all() for v in memory[:4])):
            raise ValueError("Nonfinite literal class initialization")
        return gated._state(binding, parent, memory, initialization)
    except Exception as error:
        raise gated.GatedJoinRejected(
            error, stage="initialization", parent=parent, initialization=initialization
        ) from error


class CalciumPacket(NamedTuple):
    alpha_Ca: float
    block: object


def calcium_packet(binding, *, alpha_Ca, block):
    if type(alpha_Ca) not in (int, float) or not math.isfinite(alpha_Ca):
        raise ValueError("Require explicit finite signed native alpha_Ca")
    m = len(binding.pump_binding.gated_binding.material_binding.membrane_ids)
    return CalciumPacket(float(alpha_Ca), current._array(block, (m,), "source-unused CaATP block"))


def initialize_values(binding, values, *, initial_gate_block, initial_NaK_rate, initial_CaATP_rate):
    pb = binding.pump_binding
    material = vector_state(pb.gated_binding.material_binding, values)
    active = _initialize_gate(pb.gated_binding, material, initial_block=initial_gate_block)
    proxy = current._array(
        initial_NaK_rate, (len(material.values.voltage_V),), "explicit initial NaK cache"
    )
    parent = pump._state(pb, active, proxy)
    return initialize(binding, parent, initial_calcium_rate_proxy_mol_m2_s=initial_CaATP_rate)
