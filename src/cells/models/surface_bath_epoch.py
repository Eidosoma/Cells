"""Shared epoch adapter; preserves every bath history, including chemical work."""

import json
from dataclasses import make_dataclass
from typing import NamedTuple

import numpy as np


class Adapter:
    def __init__(self, scheduled, schema, name):
        self.scheduled, self.schema = scheduled, schema
        self.STATE_TYPE = NamedTuple(name + "State", [(k, object) for k in scheduled.STATE_AXES])
        self.LAYOUT_TYPE = NamedTuple(
            name + "Layout", [(k, object) for k in scheduled.LAYOUT_TYPE._fields]
        )
        self.OBSERVATION_FIELDS = (
            *scheduled.OBSERVATION_FIELDS,
            "init_phase_clock_s",
            "elapsed_time_s",
        )
        self.Observations = make_dataclass(
            name + "Observations", [(k, np.ndarray) for k in self.OBSERVATION_FIELDS], frozen=True
        )

    def handoff_record(self, spec):
        return json.loads(spec.model.handoff_json)

    def initial_values(self, spec):
        from cells.core.membrane_profile_phase_handoff import decode_arrays

        zero, layout = self.scheduled.initial_values(self.schema.scheduled_spec(spec))
        record = self.handoff_record(spec)
        source = decode_arrays(record["source"]["checkpoint"]["state"], zero)
        state = self.STATE_TYPE(
            *(
                np.zeros_like(zero.phase_clock_s)
                if key == "phase_clock_s"
                else getattr(source, key)
                for key in zero._fields
            )
        )
        return state, self.LAYOUT_TYPE(*layout)

    def rhs(self, state, control, layout, active, **kwargs):
        return self.STATE_TYPE(*self.scheduled.rhs(state, control, layout, active, **kwargs))

    def check_definition(self, spec):
        from cells.core.surface_bath_phase_handoff import validate_carried_stages

        state, layout = self.initial_values(spec)
        self.scheduled.check_values(state, self.schema.scheduled_spec(spec))
        validate_carried_stages(self.schema.scheduled_spec(spec), state, layout)

    def check_steps(self, spec, steps, controls):
        return self.scheduled.check_steps(self.schema.scheduled_spec(spec), steps, controls)

    def check_values(self, state, spec):
        return self.scheduled.check_values(state, self.schema.scheduled_spec(spec))

    def check_checkpoint(self, spec, checkpoint):
        return self.scheduled.check_checkpoint(self.schema.scheduled_spec(spec), checkpoint)

    def initial_operation(self, spec):
        return self.scheduled.initial_operation(self.schema.scheduled_spec(spec))

    def working_size(self, spec):
        return self.scheduled.working_size(self.schema.scheduled_spec(spec)) + 4 * len(
            spec.model.handoff_json
        )

    def observe_history(self, times, history, layout, requested, spec):
        value = self.scheduled.observe_history(
            times, history, layout, requested, self.schema.scheduled_spec(spec)
        )
        clocks = self.handoff_record(spec)["clocks"]
        return self.Observations(
            *vars(value).values(),
            np.full_like(value.phase_clock_s, clocks["init_phase_clock_s"]),
            clocks["init_checkpoint_time_s"] + value.phase_clock_s,
        )

    def ensemble_voltage(self, state, layout, spec, time):
        return self.scheduled.ensemble_voltage(
            state, layout, self.schema.scheduled_spec(spec), time
        )

    def summarize(self, history, diagnostics, spec):
        from cells.core.specs import digest

        record = self.handoff_record(spec)
        return self.scheduled.summarize(
            history, diagnostics, self.schema.scheduled_spec(spec)
        ) | dict(
            model=self.schema.MODEL_ID,
            handoff_identity=digest(record),
            init_checkpoint_time_s=record["clocks"]["init_checkpoint_time_s"],
            init_phase_clock_s=record["clocks"]["init_phase_clock_s"],
            initial_controller_operation=record["controller_operation"],
            accounting_origin="original INIT physical definition; complete histories retained",
            transition_operation=(
                "exact transport/history carry plus explicit new SIM dose/charge/work"
            ),
        )
