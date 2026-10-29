"""Full calcium/fuel bath INIT carry with an explicit new SIM operation."""

import json
from dataclasses import dataclass, fields, replace

from cells.core import surface_open_calcium_energy_bath_events_spec as scheduled
from cells.core.specs import ConfigError, _fields, canonical_json, digest

MODEL_ID = "resolved_open_calcium_energy_bath_epoch@1"
POLICIES = dict(
    operation="explicit_init_checkpoint_to_new_sim_epoch@1",
    state_policy="carry_all_owned_calcium_fuel_bath_nonclock_arrays_original_anchors@1",
    clock_policy="new_sim_clock_zero_archive_both_init_clocks@1",
    controller_policy="explicit_new_sim_initial_dose_electrode_charge_and_work@1",
    control_policy="new_zero_based_sim_controls_archive_complete_init_history@1",
    carried_pool_policy="actual_carried_pools_all_sim_controls_and_pulse_box_corners@1",
    ionic_domain_policy="actual_carried_ions_plus_sim_dose_hard_moiety_limits@1",
)


@dataclass(frozen=True)
class SurfaceOpenCalciumEnergyBathEpochModel(scheduled.SurfaceOpenCalciumEnergyBathEventModel):
    handoff_json: str


def scheduled_spec(spec):
    return replace(
        spec,
        model=scheduled.SurfaceOpenCalciumEnergyBathEventModel(
            **{
                f.name: getattr(spec.model, f.name)
                for f in fields(scheduled.SurfaceOpenCalciumEnergyBathEventModel)
            }
        ),
    )


def to_dict(spec):
    if type(spec.model) is not SurfaceOpenCalciumEnergyBathEpochModel:
        raise ConfigError("Require the exact full calcium/fuel bath epoch")
    raw = scheduled.to_dict(scheduled_spec(spec))
    raw["model"] = dict(
        id=MODEL_ID, scheduled=raw["model"], handoff=json.loads(spec.model.handoff_json)
    )
    return raw


def parse(data):
    _fields(data, {"schema_version", "model", "experiment", "execution"}, "bath SIM epoch")
    model = _fields(data["model"], {"id", "scheduled", "handoff"}, "bath SIM epoch model")
    if model["id"] != MODEL_ID:
        raise ConfigError("Require " + MODEL_ID)
    record = _fields(
        model["handoff"],
        {*POLICIES, "source", "clocks", "controller_operation", "carried_admission"},
        "explicit bath INIT/SIM handoff",
    )
    if any(record[key] != value for key, value in POLICIES.items()):
        raise ConfigError(
            "Declare explicit complete carry, clock and controller-operation policies"
        )
    target = scheduled.parse(dict(data, model=model["scheduled"]))
    from cells.core.open_calcium_bath_phase_handoff import (
        decode_source,
        transition_record,
        validate_pair,
    )

    source, point = decode_source(record["source"])
    validate_pair(source, point, target)
    if digest(record) != digest(transition_record(record["source"], source, point, target)):
        raise ConfigError("Bath clock or new SIM dose/charge/work operation disagrees")
    result = replace(
        target,
        model=SurfaceOpenCalciumEnergyBathEpochModel(
            **vars(target.model), handoff_json=canonical_json(record)
        ),
    )
    from cells.models.surface_open_calcium_energy_bath_epoch import check_definition

    check_definition(result)
    return result
