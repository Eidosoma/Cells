"""Explicit, held supplied-owner INIT->SIM handoff and separate phase journals.

This in-memory boundary performs real retained-GRN reinitialization. It is not a
native pickle/load or whole-phase attestation. Complete headless and failed-prefix
artifacts are distinct; failed/paused/capped INIT prefixes are never promoted.
"""

from dataclasses import dataclass, replace

import numpy as np

from cells.processes import betse_ecm_grn_join as network
from cells.processes import betse_ecm_transport as material
from cells.processes import betse_normal_ecm_catalog_join_source as catalog
from cells.processes import betse_normal_ecm_field_join as fields
from cells.processes import betse_normal_ecm_init_phase as init
from cells.processes import betse_normal_ecm_init_sim_transition_lifecycle as lifecycle
from cells.processes import betse_normal_ecm_init_sim_transition_setup as setup
from cells.processes import betse_normal_ion_join as ions

LAW_ID = "betse_supplied_retained_INIT_to_SIM_v1_5_0@1"
INPUT_KIND = "cells.normal_ecm_init_sim_transition_inputs@1"
FIXED_FLAGS = dict(
    phase="SIM",
    _run_sim=True,
    solver="FULL",
    is_ecm=True,
    grn_enabled=True,
    molecules_enabled=False,
    Ca_dyn=False,
    fluid_flow=False,
    td_deform=False,
    sim_eosmosis=False,
    physical_initialization=False,
    native_load=False,
    native_pickle=False,
)


@dataclass(frozen=True)
class CompleteInit:
    binding: object
    parent: object
    scope: str
    identity: str


@dataclass(frozen=True)
class FailedInitPrefix:
    binding: object
    accepted: object
    failure: object
    identity: str


@dataclass(frozen=True)
class Binding:
    inputs: object
    expected_init_identity: str
    identity: str


@dataclass(frozen=True)
class SimPhase:
    binding_identity: str
    source_init: CompleteInit
    run_binding: object
    run: object
    receipt: object
    nak_rate: object
    identity: str

    @property
    def cursor(self):
        return self.run.cursor


class TransitionRejected(RuntimeError):
    def __init__(self, error, partial):
        super().__init__(str(error))
        self.partial = ions.freeze(partial)


def complete_record(value):
    return (LAW_ID, "complete_headless_INIT", value.binding.identity, value.parent, value.scope)


def prepare_complete(binding, parent):
    init.verify(binding, parent)
    if (
        parent.status != "exhausted"
        or parent.cursor != binding.calendar.step_count
        or parent.cursor != binding.call_limit
    ):
        raise TransitionRejected(
            ValueError("Only an exhausted complete headless INIT may prepare a normal handoff"),
            dict(
                stage="INIT_completion_admission",
                parent=parent,
                original_count=binding.calendar.step_count,
                native_phase_completion_attested=False,
            ),
        )
    value = CompleteInit(
        binding, parent, "complete_headless_source_subset_no_native_persistence", ""
    )
    return replace(value, identity=ions.digest(complete_record(value)))


def prepare_failed_prefix(binding, accepted, error):
    if (
        type(error) is not init.InitRejected
        or not isinstance(error.partial, dict)
        and not hasattr(error.partial, "keys")
    ):
        raise ValueError("Require the actual retained INIT refusal with complete partial evidence")
    if accepted is None:
        if (
            type(binding) is not init.Declaration
            or binding.identity != ions.digest(init.declaration_record(binding))
            or error.partial.get("declaration") is None
            or error.partial["declaration"].identity != binding.identity
        ):
            raise ValueError("A setup failure requires its actual pre-setup INIT declaration")
    else:
        init.verify(binding, accepted)
    original = error.partial.get("parent")
    completed = error.partial.get("available", {}).get("accepted")
    if accepted is not None and not any(
        type(candidate) is init.State and candidate.identity == accepted.identity
        for candidate in (original, completed)
    ):
        raise ValueError("Failed INIT prefix is foreign to its actually accepted parent")
    failure = ions.freeze(
        dict(
            type=type(error).__name__,
            message=str(error),
            partial=error.partial,
            native_pickle_or_load_attested=False,
            automatic_retry=False,
        )
    )
    value = FailedInitPrefix(binding, accepted, failure, "")
    return replace(
        value,
        identity=ions.digest((LAW_ID, "failed_INIT_prefix", binding.identity, accepted, failure)),
    )


def check_complete(value):
    if type(value) is FailedInitPrefix:
        raise TransitionRejected(
            ValueError("Failed INIT prefixes cannot enter the normal SIM transition"),
            dict(
                stage="failed_prefix_transition_refusal",
                failed_prefix=value,
                native_pickle_or_completion_inferred=False,
            ),
        )
    if type(value) is not CompleteInit or value.identity != ions.digest(complete_record(value)):
        raise ValueError("Require the unchanged explicit complete-headless INIT artifact")
    init.verify(value.binding, value.parent)
    if (
        value.parent.status != "exhausted"
        or value.parent.cursor != value.binding.calendar.step_count
    ):
        raise ValueError("Changed INIT completion cursor or disposition")


def binding_record(value):
    return (LAW_ID, value.inputs, value.expected_init_identity)


def bind(raw):
    raw = ions.data(raw)
    if (
        set(raw)
        != {
            "kind",
            "case_id",
            "provenance",
            "expected_init_binding_identity",
            "flags",
            "time_profile",
            "sim_composition_template",
            "source_setup",
            "config_equality_receipt",
        }
        or raw["kind"] != INPUT_KIND
    ):
        raise ValueError("Require the complete separately declared INIT->SIM handoff")
    if set(raw["flags"]) != set(FIXED_FLAGS) | {"alpha_NaK"}:
        raise ValueError("Require all explicit ordinary SIM handoff flags")
    for key, value in FIXED_FLAGS.items():
        if type(raw["flags"][key]) is not type(value) or raw["flags"][key] != value:
            raise ValueError("Unsupported transition scope flag: " + key)
    if setup.init_setup.real(raw["flags"]["alpha_NaK"], "SIM alpha_NaK") < 0:
        raise ValueError("Transitioned maintained NaK scope requires nonnegative alpha")
    for key in ("case_id", "provenance", "expected_init_binding_identity"):
        if not isinstance(raw[key], str) or not raw[key].strip():
            raise ValueError("Require explicit handoff identity/provenance: " + key)
    if raw["time_profile"]["phase"] != "SIM":
        raise ValueError("Transition requires a newly selected SIM time profile")
    profile = lifecycle.profile(raw["time_profile"])["sim"]
    if profile["step_count"] != 3:
        raise ValueError(
            "The existing SIM lifecycle remains qualified only for its original N3 clock"
        )
    cfg = raw["source_setup"]
    if (
        set(cfg)
        != {
            "kind",
            "provenance",
            "rng_mode",
            "rng_provenance",
            "numpy_rng",
            "python_rng",
            "environment_diffusion",
            "tissue_profiles",
            "cbnd",
            "static_noise_level",
            "frequency_sweep",
        }
        or cfg["kind"] != "cells.supplied_SIM_reinitialization_seams@1"
    ):
        raise ValueError("Require every source SIM setup seam and process RNG owner")
    if cfg["rng_mode"] not in ("supplied_SIM_process_stream", "same_process_no_unowned_draws"):
        raise ValueError("Never infer process RNG continuity from native pickle data")
    for key in ("provenance", "rng_provenance"):
        if not isinstance(cfg[key], str) or not cfg[key].strip():
            raise ValueError("Require explicit conditional source setup provenance")
    setup.numpy_restore(cfg["numpy_rng"])
    setup.init_setup.python_restore(cfg["python_rng"])
    setup.init_setup.real(cfg["static_noise_level"], "SIM static noise")
    if set(cfg["frequency_sweep"]) != {"f start", "f stop", "f slope"}:
        raise ValueError("Require the actual SIM frequency factory inputs")
    for key, value in cfg["frequency_sweep"].items():
        if value is not None or key != "f slope":
            setup.init_setup.real(value, key)
    equality = raw["config_equality_receipt"]
    if (
        set(equality)
        != {"general_before", "general_after", "world_before", "world_after", "provenance"}
        or equality["general_before"] != equality["general_after"]
        or equality["world_before"] != equality["world_after"]
    ):
        raise ValueError(
            "Native seed compatibility compares both general and world options; "
            "supplied equality receipt differs"
        )
    if not isinstance(equality["provenance"], str) or not equality["provenance"].strip():
        raise ValueError("Config equality is supplied association, not a native loader attestation")
    packet = raw["sim_composition_template"]["event_inputs"]
    if (
        packet["calendar"]["phase"] != "SIM"
        or packet["calendar"]["step_count"] != 3
        or packet["calendar"]["dt_s"] != profile["dt_s"]
        or packet["calendar"]["sample_stride"] != profile["sample_stride"]
    ):
        raise ValueError("Keep the full original SIM count/dt/sampling clock, distinct from INIT")
    if (
        raw["sim_composition_template"]["mechanics_definition"]["policy"]["fluid_flow"]
        or raw["sim_composition_template"]["mechanics_definition"]["policy"]["td_deform"]
    ):
        raise ValueError("Ordinary transition cannot enable flow or dynamic deformation")
    if packet["event_owner"]["voltage"] is not None:
        raise ValueError("Voltage-event construction is outside this first retained-owner handoff")
    if packet["field"]["network"]["configuration"].get("transporters") is not None:
        raise ValueError(
            "Additional transporter owner reconstruction is outside the existing bounded GRN scope"
        )
    for row in packet["field"]["steps"]:
        for key in ("supplied_pump_membrane_flux_mol_m2_s", "supplied_late_membrane_flux_mol_m2_s"):
            if np.any(np.asarray(row["material"][key]) != 0):
                raise ValueError(
                    "Transitioned SIM requires actual NaK/CaATP/GRN producers, "
                    "without arbitrary extra flux"
                )
        if row["material"]["dt_s"] != profile["dt_s"]:
            raise ValueError("Material and new SIM phase dt differ")
    value = Binding(ions.freeze(raw), raw["expected_init_binding_identity"], "")
    return replace(value, identity=ions.digest(binding_record(value)))


def validate_binding(binding):
    if type(binding) is not Binding or binding.identity != ions.digest(binding_record(binding)):
        raise ValueError("Changed complete transition declaration")


def check_owners(binding, completed):
    raw = ions.data(binding.inputs)
    if binding.expected_init_identity != completed.binding.identity:
        raise ValueError("Transition declaration belongs to another INIT binding")
    old = completed.binding.material_binding.geometry_binding.definition
    new = raw["sim_composition_template"]["event_inputs"]["field"]["definition"][
        "environment_geometry_definition"
    ]
    if (
        not catalog.equal_tree(old["geometry"], new["geometry"])
        or not catalog.equal_tree(old["world"], new["world"])
        or not catalog.equal_tree(
            old["current_definition"]["geometry"], new["current_definition"]["geometry"]
        )
        or not catalog.equal_tree(
            old["current_definition"]["ions"], new["current_definition"]["ions"]
        )
    ):
        raise ValueError(
            "Transition may not replace retained ionic, cell, membrane or environment owners"
        )
    cfg = raw["source_setup"]
    if cfg["rng_mode"] == "same_process_no_unowned_draws":
        receipt = completed.binding.setup_receipt
        if cfg["numpy_rng"] != ions.data(receipt["numpy_rng_after"]) or cfg[
            "python_rng"
        ] != ions.data(receipt["event_finalization"]["python_rng_after"]):
            raise ValueError(
                "Declared same-process continuity differs from actual post-INIT setup streams"
            )
    cg = new["current_definition"]["geometry"]
    names = new["current_definition"]["ions"]["ids"]
    m, n, e = (
        len(cg["membrane_ids"]),
        len(cg["cell_ids"]),
        len(completed.parent.network.material.values.environment_mol_m3[0]),
    )
    denv = cfg["environment_diffusion"]
    if set(denv) != {
        "adherens_multiplier",
        "tight_junction_multiplier",
        "environment_in_cluster_indices",
        "tight_junction_relative",
        "provenance",
    }:
        raise ValueError("Require explicit retained-core initDenv inputs and provenance")
    for key in ("adherens_multiplier", "tight_junction_multiplier"):
        setup.init_setup.real(denv[key], key)
    if len(denv["tight_junction_relative"]) != len(names) or any(
        type(j) is not int or not 0 <= j < e for j in denv["environment_in_cluster_indices"]
    ):
        raise ValueError("Require complete owned initDenv ion/environment axes")
    profiles = cfg["tissue_profiles"]
    if (
        not isinstance(profiles, list)
        or not profiles
        or len({r["name"] for r in profiles}) != len(profiles)
    ):
        raise ValueError("Require ordered unique supplied tissue selector outputs")
    maps = {}
    for row in profiles:
        if set(row) != {
            "name",
            "cell_indices",
            "membrane_indices",
            "diffusion_m2_s",
            "provenance",
        } or set(row["diffusion_m2_s"]) != {"Dm_" + role for role in setup.ROLES}:
            raise ValueError("Require every literal native tissue permeability field")
        if any(type(j) is not int or not 0 <= j < n for j in row["cell_indices"]) or any(
            type(j) is not int or not 0 <= j < m for j in row["membrane_indices"]
        ):
            raise ValueError("Foreign supplied source profile selector output")
        for value in row["diffusion_m2_s"].values():
            setup.init_setup.real(value, "profile Dm")
        maps[row["name"]] = row["membrane_indices"]
    if maps != raw["sim_composition_template"]["event_inputs"]["catalog"]["tissue_profiles"]:
        raise ValueError(
            "Retained GRN and new tissue/event profiles must share actual supplied targets"
        )
    if cfg["cbnd"] is not None and (
        set(cfg["cbnd"]) != set(names) or any(not np.isfinite(v) for v in cfg["cbnd"].values())
    ):
        raise ValueError("Require every native configured ionic boundary override")


def phase_record(value):
    return (
        LAW_ID,
        value.binding_identity,
        value.source_init.identity,
        value.run_binding.identity,
        value.run,
        value.receipt,
        value.nak_rate,
    )


def phase(binding, completed, run_binding, run, receipt, nak_rate):
    value = SimPhase(
        binding.identity, completed, run_binding, run, ions.freeze(receipt), nak_rate, ""
    )
    return replace(value, identity=ions.digest(phase_record(value)))


def transition(binding, completed, *, observer=None, before_field=None):
    ctx = None
    reached = None
    stage = "complete_INIT_admission"
    try:
        validate_binding(binding)
        check_complete(completed)
        check_owners(binding, completed)
        raw = ions.data(binding.inputs)
        stage = "actual_SIM_source_setup"
        ctx, template, mechanical_state, reached = setup.prepare(
            completed.binding, completed.parent, raw, observer
        )
        stage = "new_SIM_lifecycle_binding"
        profile = raw["time_profile"]
        run_binding = lifecycle.bind(
            dict(
                kind=lifecycle.INPUT_KIND,
                case_id=raw["case_id"],
                run_id=raw["case_id"] + "/SIM",
                composition_inputs=template,
                time_profile=profile,
                entry_mode="supplied_reinitialized_INIT_to_SIM_subset",
                observation_mode="headless_only_native_display_refused",
                stop_policy="accepted_call_boundaries_only",
                persistence="none",
            )
        )
        eb = run_binding.composition.events
        # Source clear_cache can add storage-only channel fields. Phase-origin
        # metadata includes these actual writes; no gate state is recalculated.
        ctx.initial_channel_fields = catalog.channel_fields(ctx.sim.grn.core)
        cached = catalog.cache(ctx)
        initial = material.state(
            eb.material_binding, catalog.material_values(ctx.sim), step_index=0
        )
        controls = {
            key: catalog.clone(getattr(ctx.sim, key)) for key in ("gj_block", "NaKATP_block")
        }
        net = network._state(eb, initial, cached, controls)
        stage = "SIM_bootstrap"
        ready, field = fields.reconstruct(
            eb,
            net,
            eb.calendar.dt_s,
            ions.data(eb.entry_event_state["bound_V"]),
            "bootstrap",
            before_field,
        )
        clock = init.Clock(
            ions.freeze(lifecycle.calendars.window(eb.calendar).event_label_s), 0, 0.0
        )
        component = lifecycle.composition.event.joined_state(
            eb,
            ready,
            field,
            completed.parent.rate_cache,
            clock,
            ions.data(eb.entry_event_state),
            eb.entry_stream,
            eb.entry_noise_cache,
        )
        entry = lifecycle.composition.state(
            run_binding.composition,
            component,
            mechanical_state,
            lifecycle.composition.base.initial_sample_state(),
        )
        associated = lifecycle.entry_receipt(run_binding, entry, provenance=raw["provenance"])
        run = lifecycle.begin(run_binding, entry, associated)
        receipt = ions.freeze(
            dict(
                source_init_identity=completed.identity,
                entry_ca_rate_present=completed.parent.rate_cache.present,
                entry_nak_rate=completed.parent.nak_rate,
                source_setup=reached,
                source_phase="SIM",
                legacy_run_sim=True,
                original_INIT_clock=completed.parent.clock,
                new_SIM_clock=clock,
                source_reinitialize_called=True,
                fresh_cold_owner_created=False,
                native_init_core_called=False,
                native_load_called=False,
                native_pickle_called=False,
                whole_native_phase_completed=False,
                previous_INIT_history_retained=True,
                new_SIM_history_empty=True,
                headless_only=True,
            )
        )
        result = phase(binding, completed, run_binding, run, receipt, completed.parent.nak_rate)
        verify(binding, result)
        return result
    except Exception as error:
        raise TransitionRejected(
            error,
            dict(
                stage=stage,
                source_init=completed,
                reached=reached,
                available=setup.available(ctx),
                inner_partial=getattr(error, "partial", None),
                root_cause=dict(type=type(error).__name__, message=str(error)),
                automatic_retry=False,
            ),
        ) from error


def verify(binding, parent):
    validate_binding(binding)
    if (
        type(parent) is not SimPhase
        or parent.binding_identity != binding.identity
        or parent.identity != ions.digest(phase_record(parent))
    ):
        raise ValueError("Require the unchanged complete INIT->SIM phase artifact")
    check_complete(parent.source_init)
    lifecycle.verify(parent.run_binding, parent.run)
    if (
        parent.receipt["source_phase"] != "SIM"
        or parent.receipt["legacy_run_sim"] is not True
        or parent.receipt["fresh_cold_owner_created"] is not False
        or parent.receipt["native_load_called"] is not False
    ):
        raise ValueError("Changed actual SIM reinitialization or load-scope receipt")
    m = len(
        parent.run_binding.composition.events.material_binding.geometry_binding.current_binding.membrane_ids
    )
    alpha = parent.run_binding.composition.events.calcium["alpha_Ca"]
    expected = bool(parent.receipt["entry_ca_rate_present"] or alpha > 0 and parent.cursor > 0)
    init.check_rate(parent.run.active.events.rate_cache, m, expected)
    init.check_rate(
        parent.nak_rate, m, parent.cursor > 0 or parent.receipt["entry_nak_rate"].present
    )
    if parent.cursor == 0 and not catalog.equal_tree(
        ions.data(parent.nak_rate), ions.data(parent.receipt["entry_nak_rate"])
    ):
        raise ValueError("Initial SIM NaK rate must retain the actual INIT source cache")


def advance(binding, parent, *, observer=None, **callbacks):
    verify(binding, parent)
    try:
        run, details = lifecycle.advance(
            parent.run_binding,
            parent.run,
            observer=observer,
            entry_ca_rate_present=parent.receipt["entry_ca_rate_present"],
            nak_rate_before=parent.nak_rate,
            alpha_NaK=binding.inputs["flags"]["alpha_NaK"],
            **callbacks,
        )
        nak_rate = details["event_return"][-1]["nak_rate_after"]
        result = phase(
            binding, parent.source_init, parent.run_binding, run, parent.receipt, nak_rate
        )
        verify(binding, result)
        return result, details
    except Exception as error:
        raise TransitionRejected(
            error,
            dict(
                stage="transitioned_SIM_call",
                parent=parent,
                inner_partial=getattr(error, "partial", None),
                automatic_retry=False,
            ),
        ) from error


def pause(binding, parent):
    verify(binding, parent)
    return phase(
        binding,
        parent.source_init,
        parent.run_binding,
        lifecycle.pause(parent.run_binding, parent.run),
        parent.receipt,
        parent.nak_rate,
    )


def resume(binding, parent):
    verify(binding, parent)
    return phase(
        binding,
        parent.source_init,
        parent.run_binding,
        lifecycle.resume(parent.run_binding, parent.run),
        parent.receipt,
        parent.nak_rate,
    )


def run_window(binding, parent, *, stop, observer=None, **callbacks):
    verify(binding, parent)
    if type(stop) is not int or not parent.cursor <= stop <= parent.run_binding.calendar.step_count:
        raise ValueError("Require a stop on the unchanged new SIM calendar")
    current = resume(binding, parent) if parent.run.status == "paused" else parent
    returned = []
    while current.cursor < stop:
        current, details = advance(binding, current, observer=observer, **callbacks)
        returned.append(details)
    if current.run.status == "ready":
        current = pause(binding, current)
    return current, tuple(returned)
