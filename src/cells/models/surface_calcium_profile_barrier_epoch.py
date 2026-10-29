"""SIM dynamics after a deliberate INIT-state handoff, with continuous ledgers."""

import json
from dataclasses import make_dataclass
from typing import NamedTuple

import numpy as np

from cells.core.surface_calcium_profile_barrier_epoch_spec import MODEL_ID, scheduled_spec
from cells.models import surface_calcium_profile_barrier_interventions as scheduled

STATE_AXES = scheduled.STATE_AXES
STATE_TYPE = NamedTuple("SurfaceCalciumProfileBarrierEpochState", [(k, object) for k in STATE_AXES])
LAYOUT_TYPE = NamedTuple(
    "SurfaceCalciumProfileBarrierEpochLayout", [(k, object) for k in scheduled.LAYOUT_TYPE._fields]
)
OBSERVER_ID = "resolved_init_sim_calcium_profile_barrier_epoch_readouts@1"
OBSERVATION_SAMPLING = scheduled.OBSERVATION_SAMPLING
STAGE_DOMAIN_ID = scheduled.STAGE_DOMAIN_ID
BATCH_CAPACITIES = scheduled.BATCH_CAPACITIES
OBSERVATION_FIELDS = (*scheduled.OBSERVATION_FIELDS, "init_phase_clock_s", "elapsed_time_s")
Observations = make_dataclass(
    "SurfaceCalciumProfileBarrierEpochObservations",
    [(k, np.ndarray) for k in OBSERVATION_FIELDS],
    frozen=True,
)
parameters = scheduled.parameters
domain_valid = scheduled.domain_valid
control_domain_valid = scheduled.control_domain_valid
field_values = scheduled.field_values
readouts = scheduled.readouts
signal_values = scheduled.signal_values


def handoff_record(spec):
    return json.loads(spec.model.handoff_json)


def initial_values(spec):
    from cells.core.owned_calcium_profile_barrier_phase_handoff import decode_arrays

    zero, layout = scheduled.initial_values(scheduled_spec(spec))
    record = handoff_record(spec)
    source = decode_arrays(record["source"]["checkpoint"]["state"], zero)
    state = STATE_TYPE(*scheduled.parent_state(source), np.zeros_like(zero.phase_clock_s))
    return state, LAYOUT_TYPE(*layout)


def rhs(state, control, layout, active, **kwargs):
    return STATE_TYPE(*scheduled.rhs(state, control, layout, active, **kwargs))


def check_definition(spec):
    from cells.core.schedule import control_values
    from cells.core.specs import ConfigError

    state, layout = initial_values(spec)
    m = spec.model
    clocks = sorted(
        {
            0.0,
            spec.experiment.end_time,
            *(c.time for c in spec.experiment.changes),
            *(
                t
                for e in m.membrane_interventions
                for t in (e.on_s, (e.on_s + e.off_s) / 2, e.off_s)
            ),
        }
    )
    if m.barrier_intervention is not None:
        event = m.barrier_intervention
        clocks = sorted(set(clocks) | {event.on_s, (event.on_s + event.off_s) / 2, event.off_s})
    table = control_values(scheduled_spec(spec), clocks)
    for i, time in enumerate(clocks):
        trial = state._replace(phase_clock_s=np.asarray([time]))
        u = type(table)(*(v[i] for v in table))
        if not control_domain_valid(trial, u, layout, layout.active, xp=np):
            raise ConfigError(
                "Preserved INIT state does not admit declared SIM pulse/control stages"
            )


def check_steps(spec, steps, controls):
    return scheduled.check_steps(scheduled_spec(spec), steps, controls)


def check_values(state, spec):
    return scheduled.check_values(state, scheduled_spec(spec))


def check_checkpoint(spec, checkpoint):
    return scheduled.check_checkpoint(scheduled_spec(spec), checkpoint)


def batch_signature(model):
    return scheduled.batch_signature(model)


def working_size(spec):
    return scheduled.working_size(scheduled_spec(spec)) + 4 * len(spec.model.handoff_json)


def observe_history(times, history, layout, requested, spec):
    value = scheduled.observe_history(times, history, layout, requested, scheduled_spec(spec))
    clocks = handoff_record(spec)["clocks"]
    return Observations(
        *vars(value).values(),
        np.full_like(value.phase_clock_s, clocks["init_phase_clock_s"]),
        clocks["init_checkpoint_time_s"] + value.phase_clock_s,
    )


def ensemble_voltage(state, layout, spec, time):
    return scheduled.ensemble_voltage(state, layout, scheduled_spec(spec), time)


def summarize(history, diagnostics, spec):
    from cells.core.specs import digest

    record = handoff_record(spec)
    return scheduled.summarize(history, diagnostics, scheduled_spec(spec)) | dict(
        model=MODEL_ID,
        handoff_identity=digest(record),
        init_checkpoint_time_s=record["clocks"]["init_checkpoint_time_s"],
        init_phase_clock_s=record["clocks"]["init_phase_clock_s"],
        accounting_origin="original INIT physical definition; all ledgers carried continuously",
        transition_operation="explicit preparation; neither resume nor branch",
    )
