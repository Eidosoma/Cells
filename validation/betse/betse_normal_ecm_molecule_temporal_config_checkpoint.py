"""Held selected native temporal-store preparation, using one early p/_conf.

The configuration is a declared normalized projection. Only actual selected
construction earns a source-store receipt; this helper never supplies one.
Native constructor/finalizer/model qualification remains coordinated by Root.
"""

import copy
import os
from pathlib import Path

from cells.processes import betse_normal_ecm_molecule_temporal_config as temporal
from validation.betse import betse_normal_ecm_molecule_membrane_event_checkpoint as membrane
from validation.betse import betse_normal_ecm_molecule_periodic_checkpoint as periodic
from validation.betse import betse_normal_ecm_molecule_sweep_checkpoint as sweep

ROUTE = temporal.MODE
SCENARIOS = periodic.SCENARIOS + sweep.SCENARIOS
require = temporal.require


def configure_sim(raw, scenario, *, configuration):
    """Declare raw lookups without parsing floats or manufacturing live authority."""
    declared = temporal.check_configuration(configuration)
    family = declared["family"]
    choices = periodic.SCENARIOS if family == "periodic" else sweep.SCENARIOS
    require(scenario in choices, "Selected temporal family/scenario differs")
    require(
        not temporal.KEYS.intersection(raw["source_setup"])
        and not any(k.startswith("periodic_") for k in raw["source_setup"]),
        "No late source-route rebase or manual periodic properties coexistence",
    )
    prefix = "periodic_" if family == "periodic" else "sweep_"
    suffix = scenario.removeprefix(prefix)
    base = "membrane_combined" if suffix == "mixed_constant" else "membrane_" + suffix
    result = membrane.configure_sim(raw, base)
    table = result["sim_phase"]["setup"]
    for key, row in table["scheduled_options"].items():
        if row != 0 and (suffix != "mixed_constant" or key == "Na_mem"):
            row[5] = family
    cfg = result["source_setup"]
    # The unchanged no-intervention material table still has its common schema.
    # Its unused frequency_sweep declaration is not the selected source store.
    cfg.pop("frequency_sweep", None)
    cfg[temporal.CONFIG_KEY] = copy.deepcopy(declared)
    cfg[temporal.TABLE_KEY] = copy.deepcopy(table)
    result["sim_phase"] = copy.deepcopy(raw["sim_phase"])
    cfg["provenance"] += "; " + temporal.AUTHORITY
    result["provenance"] += "; explicit selected temporal configuration: " + scenario
    temporal.selection(result)
    return result


def released():
    require(
        os.environ.get("CELLS_ECM_MOLECULE_RUN_LIFECYCLE_RELEASED") == "1"
        and os.environ.get("CELLS_ECM_MOLECULE_EVENTS_RELEASED") == "1",
        "Selected temporal parameter/finalizer preparation remains held",
    )


def prepare_sim(
    directory, init_binding, init_parent, attempts, *, scenario, event_owner_inputs, configuration
):
    """Gated actual preparation; supplied inputs stay the same typed object."""
    released()
    from cells.processes import betse_normal_ecm_molecule_event_owner as bridge
    from validation.betse import betse_normal_ecm_molecule_checkpoint as preparation

    # Refuse before directory creation, complete_INIT, model/RNG/finalizer work.
    declared_config = temporal.check_configuration(configuration)
    choices = periodic.SCENARIOS if declared_config["family"] == "periodic" else sweep.SCENARIOS
    require(scenario in choices, "Selected temporal family/scenario differs")
    actual = init_binding.composition
    supplied = bridge.check_inputs(event_owner_inputs, expected_INIT=actual.identity)
    require(
        supplied.source_geometry_binding_identity
        == actual.material_binding.geometry_binding.identity,
        "Foreign selected temporal geometry before complete_INIT",
    )
    directory = Path(directory)
    directory.mkdir(exist_ok=False)
    take = preparation._retainer(directory, attempts)
    complete = take(
        "actual-complete-INIT",
        lambda: preparation.run.complete_INIT(init_binding, init_parent),
        init_binding=init_binding,
        init_parent=init_parent,
        explicit_configuration=declared_config,
        explicit_event_owner_inputs=supplied,
    )
    original = take(
        "original-SIM-fixture",
        lambda: preparation.fixtures.sim_inputs("zero_INIT_calls", complete.complete_init),
        complete=complete,
    )
    raw = take(
        "selected-temporal-SIM-configuration",
        lambda: configure_sim(original, scenario, configuration=declared_config),
        original=original,
        configuration=declared_config,
    )
    component = take(
        "SIM-component-binding",
        lambda: preparation.leaf.bind(raw, event_owner_inputs=supplied),
        raw=raw,
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
            provenance="Actual early selected temporal p/_conf construction and finalization; "
            "normalized projection only",
        ),
        component=component,
        declared=run_inputs,
        init_parent=init_parent,
    )


def declaration(binding, entry, scenario):
    """Re-use the existing literal event route after exact retained publication."""
    selected = temporal.selection(binding.inputs)
    require(selected is not None, "No supplied-state promotion into selected temporal mode")
    producer = periodic if selected["family"] == "periodic" else sweep
    return producer.declaration(binding, entry, scenario)


def held_plan():
    return dict(
        route=ROUTE,
        scenarios=SCENARIOS,
        released=False,
        actual_constructors_finalizers_events_RNG=0,
        independent_cases=0,
        source_configuration_authority=temporal.AUTHORITY,
        prerequisite="genuine Root input authorities, final source/runtime/resource review, "
        "both scientific release gates; actual source stores/finalizer observations",
        work="complete_INIT and nested verification/replay/constructor/factory/RNG/event work "
        "are invocation work, never independent biological cases",
    )
