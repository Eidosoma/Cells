"""Held real-parent x/y preparation and checkpoint-ready event run.

The original source configuration is distinct from the event intervention.
All native stores/finalizers, verification, RNG and event construction are work,
never independent biological cases. Radial lacks native centre ownership.
"""

import copy
import os
from pathlib import Path

from cells.processes import betse_normal_ecm_molecule_spatial_authority as authority
from cells.processes import betse_normal_ecm_molecule_spatial_config as config
from validation.betse import betse_normal_ecm_molecule_membrane_event_checkpoint as membrane

require = config.require
ROUTE = authority.ROUTE
RELEASES = ("CELLS_ECM_MOLECULE_RUN_LIFECYCLE_RELEASED", "CELLS_ECM_MOLECULE_EVENTS_RELEASED")
SCENARIOS = tuple(
    "spatial_" + axis + "_" + case
    for axis in ("x", "y")
    for case in ("Na_mem", "K_mem", "Cl_mem", "Ca_mem", "combined", "mixed_constant")
) + ("spatial_xy_combined",)


def released():
    require(
        all(os.environ.get(name) == "1" for name in RELEASES),
        "Spatial real-parent preparation remains held",
    )


def output_directory(directory):
    path = Path(directory).resolve()
    for source in (
        Path(__file__).resolve().parents[2],
        Path("/mnt/workspaces/Cells/betse-v1.5.0").resolve(),
    ):
        require(
            not path.is_relative_to(source),
            "Spatial output may not mutate checkout/snapshot/original source",
        )
    return path


def configure_sim(raw, scenario, *, configuration):
    """Declare a separate source table; never supply factory outputs or geometry."""
    require(scenario in SCENARIOS, "Unknown spatial checkpoint condition/control")
    supplied = config.check_configuration(configuration)
    require(
        not config.KEYS.intersection(raw["source_setup"])
        and not config.temporal.KEYS.intersection(raw["source_setup"])
        and not any(key.startswith("periodic_") for key in raw["source_setup"]),
        "No silent spatial/source route rebase",
    )
    _, axis, case = scenario.split("_", 2)
    base = "membrane_combined" if case in ("combined", "mixed_constant") else "membrane_" + case
    result = membrane.configure_sim(raw, base)
    table = result["sim_phase"]["setup"]
    for index, key in enumerate(authority.MEMBRANE_KEYS):
        row = table["scheduled_options"][key]
        if row != 0 and (case != "mixed_constant" or key == "Na_mem"):
            row[5] = (
                "gradient_" + ("x" if index % 2 == 0 else "y")
                if axis == "xy"
                else "gradient_" + axis
            )
    cfg = result["source_setup"]
    cfg[config.CONFIG_KEY] = config.ions.data(supplied)
    cfg[config.TABLE_KEY] = copy.deepcopy(table)
    result["sim_phase"] = copy.deepcopy(raw["sim_phase"])
    cfg["provenance"] += "; " + config.AUTHORITY
    result["provenance"] += "; explicit spatial source configuration: " + scenario
    config.selection(result)
    return result


def prepare_sim(
    directory,
    init_binding,
    init_parent,
    attempts,
    *,
    scenario,
    event_owner_inputs,
    configuration,
    expected_INIT_binding_identity,
    expected_INIT_parent_identity,
):
    """Use an actual exhausted INIT; no helper constructs or substitutes one."""
    released()
    from cells.processes import betse_normal_ecm_molecule_event_owner as bridge
    from cells.processes import betse_normal_ecm_molecule_lifecycle_phase as phase
    from validation.betse import betse_normal_ecm_molecule_checkpoint as preparation

    require(
        type(init_binding) is preparation.run.Binding
        and type(init_parent) is preparation.run.RunState
        and type(init_binding.composition) is phase.Binding
        and type(init_parent.active) is phase.State
        and init_binding.composition.calendar.phase == "INIT",
        "Require the existing actual typed INIT run and owner",
    )
    require(
        type(expected_INIT_binding_identity) is str
        and bool(expected_INIT_binding_identity)
        and type(expected_INIT_parent_identity) is str
        and bool(expected_INIT_parent_identity)
        and init_binding.identity == expected_INIT_binding_identity
        and init_parent.binding_identity == init_binding.identity
        and init_parent.identity == expected_INIT_parent_identity
        and init_parent.status == "exhausted"
        and init_parent.active.cursor == init_binding.composition.calendar.step_count,
        "Missing/foreign/failed/paused/capped INIT prefix; no replay-as-parent",
    )
    supplied = bridge.check_inputs(
        event_owner_inputs, expected_INIT=init_binding.composition.identity
    )
    require(
        supplied.source_geometry_binding_identity
        == init_binding.composition.material_binding.geometry_binding.identity,
        "Foreign actual spatial source INIT geometry authority",
    )
    declared = config.check_configuration(configuration)
    require(
        scenario in SCENARIOS and "gradient_r" not in declared["families"], config.MISSING_CENTRE
    )
    axis = scenario.split("_", 2)[1]
    expected_families = ("gradient_x", "gradient_y") if axis == "xy" else ("gradient_" + axis,)
    require(
        tuple(declared["families"]) == expected_families,
        "Spatial configuration family differs before complete_INIT",
    )
    directory = output_directory(directory)
    directory.mkdir(exist_ok=False)
    take = preparation._retainer(directory, attempts)
    complete = take(
        "actual-complete-INIT",
        lambda: preparation.run.complete_INIT(init_binding, init_parent),
        init_binding=init_binding,
        init_parent=init_parent,
        configuration=declared,
        supplied=supplied,
    )
    original = take(
        "original-SIM-fixture",
        lambda: preparation.fixtures.sim_inputs("zero_INIT_calls", complete.complete_init),
        complete=complete,
    )
    raw = take(
        "selected-spatial-SIM-configuration",
        lambda: configure_sim(original, scenario, configuration=declared),
        original=original,
        configuration=declared,
    )
    component = take(
        "SIM-component-binding",
        lambda: preparation.leaf.bind(raw, event_owner_inputs=supplied),
        raw=raw,
    )
    require(
        component.event_owner_inputs is supplied, "Actual spatial preparation replaced typed Inputs"
    )
    run_inputs = take(
        "SIM-run-inputs", lambda: preparation.fixtures.declaration("zero_INIT_calls", component)
    )
    return take(
        "actual-INIT-to-SIM",
        lambda: preparation.run.transition(
            init_binding,
            init_parent,
            component,
            run_inputs,
            provenance=(
                "Actual retained INIT, issued spatial p/_conf/stores and "
                "observed source finalizers; normalized projection only"
            ),
        ),
        component=component,
        declared=run_inputs,
        init_parent=init_parent,
    )


def declaration(binding, entry, scenario):
    """Use the retained actual Publication and scalar arrays, never a fixture owner."""
    from cells.processes import betse_normal_ecm_molecule_event_owner as bridge
    from cells.processes import betse_normal_ecm_molecule_events as events

    require(scenario in SCENARIOS, "Unknown spatial continuation condition/control")
    config.selection(binding.inputs)
    published = bridge.resolve(binding, entry)
    fields = entry.phase_binding.setup_receipt["event_finalization"]["source_fields"]
    owner = events.ions.data(published.owner)
    require(
        set(owner) == membrane.OWNER_KEYS,
        "Missing complete actual spatial publication; no hydration",
    )
    authority.validate(binding, owner, published, fields)
    return dict(
        kind=events.INPUT_KIND,
        case_id=scenario,
        provenance=(
            "Actual x/y factory output/configuration/geometry and retained INIT/SIM publication"
        ),
        source_binding_identity=binding.identity,
        source_entry_identity=entry.identity,
        scope=copy.deepcopy(events.SCOPE),
        event_owner=owner,
    )


def checkpoint_ready_run(directory, sim_binding, sim_parent, attempts, *, scenario):
    """Existing event/run APIs transport the complete graph; no checkpoint codec adapter."""
    released()
    from cells.processes import betse_normal_ecm_molecule_events as events
    from validation.betse import betse_normal_ecm_molecule_checkpoint as preparation

    directory = output_directory(directory)
    directory.mkdir(exist_ok=False)
    take = preparation._retainer(directory, attempts)
    raw = take(
        "retained-spatial-event-declaration",
        lambda: declaration(sim_binding.composition, sim_parent.active, scenario),
        sim_binding=sim_binding,
        sim_parent=sim_parent,
    )
    component = take(
        "actual-event-binding",
        lambda: events.bind(raw, sim_binding.composition, sim_parent.active),
        raw=raw,
    )
    entry = take("actual-event-entry", lambda: events.begin(component), component=component)
    declared = take(
        "event-run-inputs", lambda: preparation.fixtures.declaration("zero_INIT_calls", component)
    )
    binding = take(
        "event-run-binding", lambda: preparation.run.bind(declared, component), declared=declared
    )
    receipt = take(
        "actual-event-run-receipt",
        lambda: preparation.run.entry_receipt(
            binding,
            entry,
            provenance=(
                "Actual observed spatial callback publication; no synthetic receipt admission"
            ),
            previous_phase=sim_parent.entry_receipt["previous_phase"],
        ),
        entry=entry,
    )
    parent = take(
        "actual-event-run-begin",
        lambda: preparation.run.begin(binding, entry, receipt),
        entry=entry,
        receipt=receipt,
    )
    return binding, parent


def held_plan():
    return dict(
        route=ROUTE,
        scenarios=SCENARIOS,
        released=False,
        actual_constructors_factories_events_RNG=0,
        independent_cases=0,
        configuration_authority=config.AUTHORITY,
        radial_prerequisite=config.MISSING_CENTRE,
        prerequisite=(
            "Genuine exhausted INIT + typed Inputs; Root source/runtime review "
            "and both releases/resources"
        ),
        callable_instance_persisted=False,
        source_scalar_arrays="full native count-selected axis; no gathering/shape repair",
        checkpoint=(
            "existing run/checkpoint graph and ownership verification; "
            "no native pickle/geometry admission"
        ),
    )
