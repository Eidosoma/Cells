"""Explicit held global interventions on an actual later owner Publication.

Source setup uses supplied typed authorities and its original configuration.
The intervention is a separate declared control on the complete retained owner.
No fixture owner, reservoir, default-profile role or boundary ID is fabricated.
"""

import copy
import math

from validation.betse import betse_normal_ecm_molecule_global_event_checkpoint as global_events

ROUTE = "published_global"
TEMPERATURE_SCENARIOS = ("temperature", "no_events", "temperature_boundaries")
MIXED = "membrane_mixed_global"
SCENARIOS = TEMPERATURE_SCENARIOS + global_events.SCENARIOS + (MIXED,)
SOURCE_FIELDS = (
    "kind",
    "provenance",
    "geometry_declaration_sha256",
    "owners",
    "tissue_default",
    "tissue_target_inds",
    "cell_target_inds",
    "env_target_inds",
    "configured_environment",
    "voltage",
    "event_cut",
)
require = global_events.require


def check_route(scenario):
    require(scenario in SCENARIOS, "Unsupported explicit global Publication route/scenario")


def prepare_sim(directory, init_binding, init_parent, attempts, *, scenario, event_owner_inputs):
    """Carry supplied authority; never replace source setup with an event owner."""
    check_route(scenario)
    from cells.processes import betse_normal_ecm_molecule_event_owner as owner_bridge
    from validation.betse import betse_normal_ecm_molecule_checkpoint as preparation
    from validation.betse import betse_normal_ecm_molecule_membrane_event_checkpoint as membrane

    actual = init_binding.composition
    supplied = owner_bridge.check_inputs(event_owner_inputs, expected_INIT=actual.identity)
    require(
        supplied.source_geometry_binding_identity
        == actual.material_binding.geometry_binding.identity,
        "Foreign supplied geometry authority before published global SIM preparation",
    )
    if scenario == MIXED:
        return membrane.prepare_sim(
            directory,
            init_binding,
            init_parent,
            attempts,
            scenario=scenario,
            event_owner_inputs=event_owner_inputs,
        )
    return preparation.prepare_SIM(
        directory, init_binding, init_parent, attempts, event_owner_inputs=event_owner_inputs
    )


def intervention_options(scenario, labels, dt):
    """Existing literal event-specimen parameters, explicitly declared as controls.

    This evaluates no pulse or physiological law. Numerical configuration is
    the existing on=.5dt/off=2dt/width=.7dt specimen, never inferred from stores.
    """
    check_route(scenario)
    require(
        len(labels) == 3 and type(dt) in (int, float) and dt > 0 and math.isfinite(dt),
        "Original bounded N3 source labels/dt required",
    )
    on, off, width = 0.5 * dt, 2.0 * dt, 0.7 * dt
    template = {
        "K_env": [on, off, width, 0.02],
        "Cl_env": [on, off, width, 0.015],
        "Na_env": [on, off, width, 0.01],
        "T_change": [on, off, width, 0.01],
        "gj_block": [on, off, width, 100],
        "NaKATP_block": [on, off, width],
    }
    if scenario == "no_events":
        selected = ()
    elif scenario in ("temperature", "temperature_boundaries"):
        selected = ("T_change",)
    elif scenario == MIXED:
        selected = global_events.GLOBAL_ORDER
    else:
        selected = global_events.CONFIGURATIONS[scenario]
    options = {
        key: list(template[key]) if key in selected else 0 for key in global_events.GLOBAL_ORDER
    }
    for key in selected:
        if scenario in ("temperature_boundaries", "global_boundaries"):
            options[key][:2] = [labels[1], labels[2]]
        if scenario == "global_salts_signed_reversal":
            options[key][3] = -options[key][3]
    if scenario == "global_salts_reversed_declaration":
        options = dict(reversed(list(options.items())))
    return options


def declaration(source_binding, source_entry, *, scenario, labels, dt):
    """Start only from resolved retained owner data, then declare intervention."""
    check_route(scenario)
    from cells.processes import betse_normal_ecm_molecule_event_owner as owner_bridge
    from cells.processes import betse_normal_ecm_molecule_events as events
    from validation.betse.betse_normal_ecm_event_join_fixtures import finalize_fields

    published = owner_bridge.resolve(source_binding, source_entry)
    require(
        dt == source_entry.phase_binding.calendar.dt_s
        and tuple(labels) == tuple(float(t) for t in source_entry.active.clock.source_times_s),
        "Declared global intervention must retain actual source labels/dt",
    )
    owner = events.ions.data(published.owner)
    require(
        owner["voltage"] is None
        and owner["event_cut"] is None
        and owner["scheduled_options"]["pressure"] == 0
        and owner["scheduled_options"]["ecmJ"] == 0,
        "Pressure/ecmJ/voltage/cutting remain outside published global preparation",
    )
    if scenario == MIXED:
        require(
            any(
                owner["scheduled_options"][key] != 0
                for key in ("Na_mem", "K_mem", "Cl_mem", "Ca_mem")
            )
            and owner["callbacks"]
            and all(row["source_function"] == "None" for row in owner["callbacks"].values()),
            "Mixed route requires actual finalized constant membrane authority",
        )
    else:
        require(
            all(row == 0 for row in owner["scheduled_options"].values()) and not owner["callbacks"],
            "Pure global/zero route cannot drop source membrane/callback authority",
        )
    options = intervention_options(scenario, labels, dt)
    spec = dict(
        kind="cells.declared_global_intervention_on_published_owner@1",
        scenario=scenario,
        source_publication_identity=published.identity,
        source_binding_identity=source_binding.identity,
        source_entry_identity=source_entry.identity,
        source_configuration_identity=events.ions.digest(
            source_binding.inputs["sim_phase"]["setup"]
        ),
        source_inputs_provenance=published.inputs.provenance,
        source_event_finalized_identity=published.event_finalized_identity,
        later_epoch=published.epoch,
        source_labels=list(labels),
        source_dt_s=dt,
        global_options=options,
        provenance=(
            "Separate conditional declared intervention using existing event-specimen parameters; "
            "no native derivation or biological admission"
        ),
    )
    spec["identity"] = events.ions.digest(spec)
    owner["global_options"] = copy.deepcopy(options)
    owner["handler_fields"] = finalize_fields(
        options, owner["scheduled_options"], owner, len(owner["owners"]["membrane_ids"])
    )
    raw = dict(
        kind=events.INPUT_KIND,
        case_id=scenario,
        provenance="Actual retained later source Publication "
        + published.identity
        + "; separate declared global intervention "
        + spec["identity"],
        source_binding_identity=source_binding.identity,
        source_entry_identity=source_entry.identity,
        scope=copy.deepcopy(events.SCOPE),
        event_owner=owner,
    )
    return raw, spec


def association(component, spec):
    """Recheck source/intervention separation on original and decoded graphs."""
    from cells.processes import betse_normal_ecm_molecule_event_owner as owner_bridge
    from cells.processes import betse_normal_ecm_molecule_events as events

    require(type(component) is events.Binding, "Require typed actual event binding")
    payload = {key: value for key, value in spec.items() if key != "identity"}
    require(
        spec["identity"] == events.ions.digest(payload),
        "Changed explicit global intervention record",
    )
    published = owner_bridge.resolve(component.source_binding, component.source_entry)
    require(
        published.identity == spec["source_publication_identity"]
        and published.event_finalized_identity == spec["source_event_finalized_identity"]
        and published.epoch == spec["later_epoch"]
        and component.source_binding.identity == spec["source_binding_identity"]
        and component.source_entry.identity == spec["source_entry_identity"]
        and events.ions.digest(component.source_binding.inputs["sim_phase"]["setup"])
        == spec["source_configuration_identity"]
        and published.inputs.provenance == spec["source_inputs_provenance"],
        "Foreign source configuration/publication/epoch for global intervention",
    )
    raw, expected = declaration(
        component.source_binding,
        component.source_entry,
        scenario=spec["scenario"],
        labels=spec["source_labels"],
        dt=spec["source_dt_s"],
    )
    require(
        owner_bridge.same(expected, spec) and owner_bridge.same(component.raw, raw),
        "Changed global intervention or substituted source owner",
    )
    return dict(
        source_publication=published.identity,
        source_configuration=spec["source_configuration_identity"],
        source_event_finalized=published.event_finalized_identity,
        source_publication_epoch=published.epoch,
        declared_intervention=spec["identity"],
    )
