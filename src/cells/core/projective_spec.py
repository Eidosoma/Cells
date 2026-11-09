"""execution.projective: the opt-in coarse projective mode of a simulation definition.

Absent (the default), a definition, its serialization and its run are those of
the fine engine, unchanged. Present, cells.core.runner.run executes the
definition with cells.core.projective: bursts of fine checked steps of the
declared solver, and projective_forward_euler@1 jumps (numerics/projective.py)
inside the declared windows only. Every field is required:

  method        "projective_forward_euler@1"
  windows       [{"start_time", "end_time"}, ...]: increasing, disjoint model-time
                intervals inside the horizon. A jump and the fine burst that
                verifies it lie inside one window; fine stepping elsewhere.
  burst_steps   fine steps per burst (K); the burst after a jump verifies it
  slope_steps   chord length m of the slope and of the settling estimate, 2m <= K
  jump          {"rule": "fixed", "steps", "min_steps"} or
                {"rule": "error_controlled", "max_steps", "min_steps",
                 "max_growth", "safety_factor"}; lengths in fine steps
  tolerance     {"concentration_mM", "membrane_voltage_V", "gate"}: absolute
                local-error tolerances of the error coordinates, per jump
  safety        {"max_membrane_voltage_rate_V_per_s", "max_gate_distance",
                 "max_correction", "energy_defect_rtol", "energy_defect_atol_pJ",
                 "rejection_shrink", "cooldown_bursts"}
  row_checks    "host": the model's check_values on every accepted burst row
                (the ordinary runner's checks); "device": the model's compiled
                device_checks (the same tests, core/vector_windows.py) on every
                burst row, for models that declare them. Jumped rows always
                take check_values on the host.

The block is execution, not physics: the model, experiment and the fine
execution fields are parsed by the model's own parser, unchanged.
"""

from dataclasses import dataclass, replace

from cells.core.specs import ConfigError, _fields, _integer, _number
from cells.numerics.projective import METHOD_ID

# Model identities with projective readouts (models/surface_pump_projective.py).
SUPPORTED_MODELS = (
    "resolved_pump_tissue@1",
    "resolved_pump_tissue@2",
    "resolved_pump_tissue@3",
)
RULES = ("fixed", "error_controlled")
TOLERANCE_FIELDS = ("concentration_mM", "membrane_voltage_V", "gate")
SAFETY_FIELDS = (
    "max_membrane_voltage_rate_V_per_s",
    "max_gate_distance",
    "max_correction",
    "energy_defect_rtol",
    "energy_defect_atol_pJ",
    "rejection_shrink",
    "cooldown_bursts",
)
FIELDS = (
    "method",
    "windows",
    "burst_steps",
    "slope_steps",
    "jump",
    "tolerance",
    "safety",
    "row_checks",
)
ROW_CHECKS = ("host", "device")
DEVICE_HOOKS = (
    "device_checks",
    "device_check_constants",
    "device_failure_message",
    "DEVICE_CHECKS",
    "DEVICE_DIAGNOSTICS",
)
MAX_STEPS = 2**53 - 1


@dataclass(frozen=True)
class ProjectiveWindow:
    start_time: float
    end_time: float


@dataclass(frozen=True)
class JumpRule:
    rule: str
    max_steps: int  # The fixed rule's jump, or the error-controlled maximum.
    min_steps: int
    max_growth: float | None = None  # error_controlled: next / previous accepted jump.
    safety_factor: float | None = None  # error_controlled: target estimate / tolerance.


@dataclass(frozen=True)
class ProjectiveTolerance:
    concentration_mM: float
    membrane_voltage_V: float
    gate: float


@dataclass(frozen=True)
class ProjectiveSafety:
    max_membrane_voltage_rate_V_per_s: float
    max_gate_distance: float
    max_correction: float  # Post-jump correction, in tolerance units.
    energy_defect_rtol: float  # Per jump, of the energy flowing through the jump.
    energy_defect_atol_pJ: float
    rejection_shrink: float  # Next attempt after a rejection, as a fraction of it.
    cooldown_bursts: int  # Fine bursts before retrying when attempts fall below min_steps.


@dataclass(frozen=True)
class ProjectiveSpec:
    method: str
    windows: tuple[ProjectiveWindow, ...]
    burst_steps: int
    slope_steps: int
    jump: JumpRule
    tolerance: ProjectiveTolerance
    safety: ProjectiveSafety
    row_checks: str


def model_id(spec):
    from cells.models.registry import get_model

    return getattr(get_model(spec.model), "MODEL_ID", None)


def _jump(data):
    if not isinstance(data, dict) or data.get("rule") not in RULES:
        raise ConfigError("projective jump rule must be fixed or error_controlled")
    if data["rule"] == "fixed":
        _fields(data, {"rule", "steps", "min_steps"}, "projective jump")
        steps = _integer(data["steps"], "projective jump steps", maximum=MAX_STEPS)
        minimum = _integer(data["min_steps"], "projective min_steps", maximum=steps)
        return JumpRule("fixed", steps, minimum)
    _fields(
        data,
        {"rule", "max_steps", "min_steps", "max_growth", "safety_factor"},
        "projective jump",
    )
    steps = _integer(data["max_steps"], "projective max_steps", maximum=MAX_STEPS)
    minimum = _integer(data["min_steps"], "projective min_steps", maximum=steps)
    growth = _number(data["max_growth"], "projective max_growth", positive=True)
    factor = _number(data["safety_factor"], "projective safety_factor", positive=True)
    if growth <= 1 or factor > 1:
        raise ConfigError("projective max_growth must exceed 1 and safety_factor lie in (0, 1]")
    return JumpRule("error_controlled", steps, minimum, growth, factor)


def parse(data, spec):
    """The projective block of an already parsed fine definition."""
    _fields(data, set(FIELDS), "execution.projective")
    if data["method"] != METHOD_ID:
        raise ConfigError("execution.projective requires method " + METHOD_ID)
    if model_id(spec) not in SUPPORTED_MODELS:
        raise ConfigError("execution.projective supports " + ", ".join(SUPPORTED_MODELS))
    end = spec.experiment.end_time
    if type(data["windows"]) is not list:
        raise ConfigError("projective windows must be a list")
    windows, previous = [], 0.0
    for item in data["windows"]:
        _fields(item, {"start_time", "end_time"}, "projective window")
        start = _number(item["start_time"], "projective window start_time")
        stop = _number(item["end_time"], "projective window end_time")
        if not previous <= start < stop <= end:
            raise ConfigError("projective windows must increase, be disjoint and fit the horizon")
        windows.append(ProjectiveWindow(start, stop))
        previous = stop
    burst = _integer(data["burst_steps"], "projective burst_steps", minimum=2)
    slope = _integer(data["slope_steps"], "projective slope_steps", maximum=burst // 2)
    tolerance = _fields(data["tolerance"], set(TOLERANCE_FIELDS), "projective tolerance")
    tolerance = ProjectiveTolerance(
        *(
            _number(tolerance[k], "projective tolerance " + k, positive=True)
            for k in TOLERANCE_FIELDS
        )
    )
    safety = _fields(data["safety"], set(SAFETY_FIELDS), "projective safety")
    values = [
        _number(safety[k], "projective safety " + k, positive=k.startswith("max_"))
        for k in SAFETY_FIELDS[:-1]
    ]
    if not 0 < values[5] < 1:
        raise ConfigError("projective rejection_shrink must lie in (0, 1)")
    cooldown = _integer(safety["cooldown_bursts"], "projective cooldown_bursts", minimum=0)
    if data["row_checks"] not in ROW_CHECKS:
        raise ConfigError("projective row_checks must be host or device")
    if data["row_checks"] == "device":
        from cells.models.registry import get_model

        model = get_model(spec.model)
        if not all(hasattr(model, k) for k in DEVICE_HOOKS):
            raise ConfigError("projective device row checks require the model's device checks")
    return ProjectiveSpec(
        METHOD_ID,
        tuple(windows),
        burst,
        slope,
        _jump(data["jump"]),
        tolerance,
        ProjectiveSafety(*values, cooldown),
        data["row_checks"],
    )


def to_dict(value):
    jump = value.jump
    if jump.rule == "fixed":
        rule = dict(rule="fixed", steps=jump.max_steps, min_steps=jump.min_steps)
    else:
        rule = dict(
            rule="error_controlled",
            max_steps=jump.max_steps,
            min_steps=jump.min_steps,
            max_growth=jump.max_growth,
            safety_factor=jump.safety_factor,
        )
    return dict(
        method=value.method,
        windows=[dict(start_time=w.start_time, end_time=w.end_time) for w in value.windows],
        burst_steps=value.burst_steps,
        slope_steps=value.slope_steps,
        jump=rule,
        tolerance={k: getattr(value.tolerance, k) for k in TOLERANCE_FIELDS},
        safety={k: getattr(value.safety, k) for k in SAFETY_FIELDS},
        row_checks=value.row_checks,
    )


def parse_definition(data, parse_fine):
    """parse_spec for a definition whose execution block holds a projective block."""
    raw = dict(data)
    execution = dict(raw["execution"])
    block = execution.pop("projective")
    raw["execution"] = execution
    spec = parse_fine(raw)
    return replace(spec, projective=parse(block, spec))
