"""execution.fine_windows: declared fine windows of a simulation definition (C; D235).

docs/LONG_DURATION_MODE_DESIGN.md §4.2 (fine windows around interventions), §4.4 (the mode lives
in the definition from the start) and §4.5 (compiled window rollouts); FR-8 rung 1's registration,
§10.10, scopes version 1 for its first consumer: fixed windows, one definition, one clock with two
rates. Absent, the default, a definition, its serialization, its fingerprint, its clock and its
run are unchanged. Present, the definition's clock (cells.execution.grid.EventGrid) takes the fine
step inside each declared window and the coarse step execution.dt outside, in one run. Every field
is required:

  method   "cells.execution.fixed_fine_windows@1"
  dt       the fine step h (s); execution.dt / h is a whole number m >= 2
  windows  [{"start_time", "end_time"}, ...]: non-empty, increasing and non-overlapping intervals
           (they may touch) inside the horizon, each end a point of the coarse grid, i x
           execution.dt exactly (a window may end at the run's end where that is one)

The clock keeps every coarse point and adds the m - 1 fine points (m i + r) x h inside each coarse
step of a window (cells.execution.grid). Events stay compulsory boundaries: schedule changes,
doses and writes, operators' schedules included; one within rounding of a point of the clock it
does not equal, fine or coarse, is refused, naming the point to declare. Read a window's rows off
the clock, EventGrid(spec), which does not depend on observation_times. Each step is taken at its
own size: the rollout reads it from the clock, and the step-doubled energy check
(execution.energy_check), which composes with the block and is not required by it, doubles each
step at its own size. A checkpoint at any boundary restarts on the same clock (§4.4). The block is
execution, not physics: the model, experiment and the other execution fields are parsed by the
model's own parser, unchanged, as for execution.projective and execution.energy_check.

Refused, fail-closed:
- a model other than ADMITTED_MODELS: one that reads execution.dt in its dynamics would take it for
  its step, and a model with its own runner would ignore the block;
- in the composite, an operator law not on ADMITTED_OPERATORS. Each admitted law's step parts, and
  the functions they pass the step to, were read for version 1: its events compare its state with
  time-scheduled controls, its half-steps, RK4 rates and in-step process take the step the
  composite gives them (their in-step conditions, such as h max L <= 1/2, hold more easily at a
  finer step), and it keeps no count of steps. Its definition checks read execution.dt, the
  clock's largest step, as a bound or as the grid of its event times, which stay exact multiples
  of execution.dt inside a window (an event at a fine-only instant is refused by the operator's
  own rule). REFUSED_OPERATORS names the laws refused with their reason; a law registered later
  is refused until it is read and added;
- a projective block beside it (projective counts steps of the declared dt; it is paused);
- the batch and vector paths, and a branch that changes the block (cells.execution.grid's
  require_scalar_path; cells.execution.runner.branch_checkpoint).
The windows are fixed. Ending a window by a settling threshold is a later version (§10.10, 5).
"""

from dataclasses import dataclass, replace

from cells.definitions.specs import ConfigError, _fields, _number

METHOD_ID = "cells.execution.fixed_fine_windows@1"
FIELDS = ("method", "dt", "windows")
COMPOSITE_ID = "cells.model.resolved_pump_composite@1"
ADMITTED_MODELS = ("cells.model.resolved_pump_tissue@3", COMPOSITE_ID)
ADMITTED_OPERATORS = (
    "cells.operator.cell_owned_compartments@1",
    "cells.operator.cytoplasmic_bridge_closure@1",
    "cells.operator.electrode_current_injection@1",
    "cells.operator.ideal_osmosis_linear_compliance_water@1",
    "cells.operator.isopotential_partition@1",
    "cells.operator.k_anion_symport_mass_action@1",
    "cells.operator.local_species_reactions@1",
    "cells.operator.membrane_entity_state@1",
    "cells.operator.population_unit_turnover@1",
    "cells.operator.restricted_cleft_lumen@1",
    "cells.operator.restricted_cleft_lumen@2",
    "cells.operator.scheduled_bath_composition@1",
    "cells.operator.scheduled_cell_replacement@1",
    "cells.operator.scheduled_cell_replacement@2",
    "cells.operator.scheduled_membrane_insertion@1",
    "cells.operator.scheduled_membrane_insertion@2",
    "cells.operator.scheduled_membrane_trafficking@1",
    "cells.operator.scheduled_species_exchange@1",
    "cells.operator.scheduled_species_turnover@1",
    "cells.operator.site_occupancy@1",
)
_COUNTS_STEPS = (
    "its crossing record counts steps and reads time as count x dt "
    "(docs/LONG_DURATION_MODE_DESIGN.md §4.1, counting records)"
)
REFUSED_OPERATORS = {
    "cells.operator.species_regulated_availability@1": _COUNTS_STEPS,
    "cells.operator.species_regulated_availability@2": _COUNTS_STEPS,
}


@dataclass(frozen=True)
class FineWindow:
    start_time: float
    end_time: float


@dataclass(frozen=True)
class FineWindows:
    """The declared method, fine step and windows."""

    method: str
    dt: float
    windows: tuple[FineWindow, ...]


def admit(spec):
    """Refuse a definition whose model or operators version 1 does not admit (module docstring)."""
    from cells.registry.models import get_model

    model = getattr(get_model(spec.model), "MODEL_ID", None)
    if model not in ADMITTED_MODELS:
        raise ConfigError(
            f"execution.fine_windows admits {' and '.join(ADMITTED_MODELS)}; "
            f"{model or type(spec.model).__name__} is refused (fails closed)"
        )
    if model == COMPOSITE_ID:
        from cells.definitions.pump_composite_spec import operator_laws

        for law in operator_laws(spec.model):
            if law not in ADMITTED_OPERATORS:
                reason = REFUSED_OPERATORS.get(
                    law, "it is not on version 1's admitted list (fails closed)"
                )
                raise ConfigError(f"execution.fine_windows: operator {law} is refused: {reason}")


def parse(data, spec):
    """The fine_windows block of an already parsed definition: its fields, its admission and its
    clock (cells.execution.grid.EventGrid refuses windows off the coarse grid, a fine dt that does
    not divide execution.dt, an event within rounding of a clock point and a clock above
    max_steps)."""
    _fields(data, set(FIELDS), "execution.fine_windows")
    if data["method"] != METHOD_ID:
        raise ConfigError(f"execution.fine_windows requires method {METHOD_ID}")
    fine = _number(data["dt"], "execution.fine_windows.dt", positive=True)
    if fine >= spec.execution.dt:
        raise ConfigError("execution.fine_windows dt must be smaller than execution.dt")
    if type(data["windows"]) is not list or not data["windows"]:
        raise ConfigError("execution.fine_windows windows must be a non-empty list")
    windows, previous = [], 0.0
    for item in data["windows"]:
        _fields(item, {"start_time", "end_time"}, "execution.fine_windows window")
        start = _number(item["start_time"], "execution.fine_windows window start_time")
        stop = _number(item["end_time"], "execution.fine_windows window end_time")
        if not previous <= start < stop <= spec.experiment.end_time:
            raise ConfigError(
                "execution.fine_windows windows must increase, not overlap and fit the horizon"
            )
        windows.append(FineWindow(start, stop))
        previous = stop
    value = FineWindows(METHOD_ID, fine, tuple(windows))
    admit(spec)
    from cells.execution.grid import EventGrid

    EventGrid(replace(spec, fine_windows=value))
    return value


def to_dict(value):
    return dict(
        method=value.method,
        dt=value.dt,
        windows=[dict(start_time=w.start_time, end_time=w.end_time) for w in value.windows],
    )


def parse_definition(data, parse_fine):
    """parse_spec for a definition whose execution block holds a fine_windows block. It is
    dispatched first, so the definition it checks carries any projective or energy_check block."""
    raw = dict(data)
    execution = dict(raw["execution"])
    block = execution.pop("fine_windows")
    raw["execution"] = execution
    spec = parse_fine(raw)
    if getattr(spec, "projective", None) is not None:
        raise ConfigError(
            "execution.fine_windows runs on the fine engine; execution.projective, which has its "
            "own windows and counts steps of execution.dt, is refused beside it"
        )
    return replace(spec, fine_windows=parse(block, spec))
