"""resolved_pump_tissue@1: resolved patches, Na/K-ATPase and junction gates.

The rates and ledgers are those of resolved_tissue@2 with no channel
population: passive constant-field patches, the nak_atp_mass_action_positive@1
pump, the physical-time junction gate (junction_voltage_relaxation@1, the same
equations as the rate-based junction law), logmean extracellular faces
and held reservoirs, closed by resolved_capacitor_components_current_continuity@1.
Differences: temperature may lie anywhere in the pump's 200-400 K domain (the
gate law has no temperature term), the field uses the Cholesky-factored solver
(capacitive_reduction_gauged_damped_newton@2, up to 2048 cell+outside nodes),
and the solver may be RK4 or an IMEX scheme with implicit face
electromigration (numerics/surface_imex.py).
"""

import copy
from dataclasses import asdict, dataclass, replace

from cells.core import surface_kinetic_spec as kinetic
from cells.core import surface_tissue_spec as base
from cells.core.bioelectric_spec import positive
from cells.core.kinetic_finite_spec import parse_pump, pump_to_dict
from cells.core.multispecies_spec import identifier
from cells.core.specs import ChannelChange, ConfigError, _fields, _number
from cells.core.voltage_gated_spec import fraction
from cells.numerics import surface_imex as imex
from cells.numerics.surface_field import FACTORED_SOLVER_ID
from cells.processes import junction_gate
from cells.processes.kinetic_pump import TEMPERATURE_DOMAIN_K

MODEL_ID = "resolved_pump_tissue@1"
GATE_LAW_ID = junction_gate.RELAXATION_LAW_ID
SOLVERS = ("rk4", imex.EULER_ID, imex.ARS222_ID)
GATE_FIELDS = ("law", "threshold_voltage_V", "minimum_open_fraction", "initial_gate")
EXECUTION_FIELDS = set(kinetic.Execution.__dataclass_fields__) - {"channel_capacity"}


@dataclass(frozen=True)
class SurfacePumpModel:
    species_ids: tuple[str, ...]
    valence: tuple[int, ...]
    temperature_K: float
    cells: tuple[base.Compartment, ...]
    extracellular: tuple[base.Outside, ...]
    membranes: tuple[kinetic.Membrane, ...]
    junctions: tuple[kinetic.Junction, ...]
    faces: tuple
    gauge_reference: str | None
    channels: tuple = ()  # Always empty; the shared kinetic rates read it.


def to_dict(spec):
    m, e, x = spec.model, spec.experiment, spec.execution
    if (
        type(m) is not SurfacePumpModel
        or type(e) is not kinetic.Experiment
        or type(x) is not kinetic.Execution
        or m.channels
    ):
        raise ConfigError("Resolved pump tissue requires its own model, experiment and execution")
    raw = base.to_dict(kinetic.passive_spec(spec))
    raw["model"]["id"] = MODEL_ID
    for target, p in zip(raw["model"]["membranes"], m.membranes, strict=True):
        target["pump"] = pump_to_dict(p, m.species_ids)
    for target, p in zip(raw["model"]["junctions"], m.junctions, strict=True):
        target["gate"] = {k: getattr(p, k) for k in GATE_FIELDS}
    raw["experiment"]["pump_controls"] = [
        dict(pump_id=p.pump.id, schedule=[asdict(c) for c in g])
        for p, g in zip(m.membranes, e.pumps, strict=True)
        if p.pump is not None
    ]
    raw["execution"]["solver"] = x.solver
    return raw


def _schedules(groups, kind, names, end):
    if type(groups) is not list:
        raise ConfigError("Require explicit " + kind + " controls")
    result = {}
    for group in groups:
        _fields(group, {kind + "_id", "schedule"}, "control")
        name, changes = identifier(group[kind + "_id"]), group["schedule"]
        if name in result or type(changes) is not list or not changes:
            raise ConfigError("Each route needs one nonempty control schedule")
        for c in changes:
            _fields(c, {"time", "availability"}, "control change")
        values = tuple(
            ChannelChange(_number(c["time"], "time"), fraction(c["availability"], "availability"))
            for c in changes
        )
        if (
            values[0].time != 0
            or any(c.time > end for c in values)
            or any(b.time <= a.time for a, b in zip(values, values[1:], strict=False))
        ):
            raise ConfigError("Controls must start at zero and increase within the horizon")
        result[name] = values
    if set(result) != set(names):
        raise ConfigError("Control IDs must exactly match their routes")
    return result


def parse(data):
    raw = copy.deepcopy(data)
    m, e, x = raw["model"], raw["experiment"], raw["execution"]
    _fields(
        m,
        {
            "id",
            "species",
            "temperature_K",
            "cells",
            "extracellular",
            "membranes",
            "junctions",
            "faces",
            "closure",
        },
        "resolved pump model",
    )
    _fields(
        e,
        {
            "end_time",
            "observation_times",
            "membrane_controls",
            "junction_controls",
            "pump_controls",
        },
        "resolved pump experiment",
    )
    _fields(x, EXECUTION_FIELDS, "resolved pump execution")
    if m["id"] != MODEL_ID or x["solver"] not in SOLVERS:
        raise ConfigError("Require resolved_pump_tissue@1 with rk4 or a declared IMEX solver")
    temperature = positive(m["temperature_K"], "temperature")
    if not TEMPERATURE_DOMAIN_K[0] <= temperature <= TEMPERATURE_DOMAIN_K[1]:
        raise ConfigError("Resolved pump tissue requires 200-400 K, the pump law's domain")
    for key in ("species", "membranes", "junctions"):
        if type(m[key]) is not list:
            raise ConfigError(key + " requires an explicit list")
    gates = {}
    for p in m["junctions"]:
        _fields(p, set(base.Junction.__dataclass_fields__) | {"law", "gate"}, "junction")
        g = _fields(p.pop("gate"), set(GATE_FIELDS), "junction gate")
        threshold = _number(g["threshold_voltage_V"], "junction threshold")
        minimum, initial = (fraction(g[k], k) for k in ("minimum_open_fraction", "initial_gate"))
        if (
            g["law"] != GATE_LAW_ID
            or not 0 <= threshold <= junction_gate.MAX_ABS_VOLTAGE_V
            or initial < minimum
        ):
            raise ConfigError(
                "Junction gate requires junction_voltage_relaxation@1, a threshold in "
                "[0, 0.120] V and an initial gate in [minimum, 1]"
            )
        gates[p["id"]] = (GATE_LAW_ID, threshold, minimum, initial)
    for p in m["membranes"]:
        _fields(p, set(base.Membrane.__dataclass_fields__) | {"law", "pump"}, "membrane")
    pumps = [p.pop("pump") for p in m["membranes"]]
    pump_controls = e.pop("pump_controls")
    solver = x.pop("solver")
    # The passive parser checks the initial field with the actual openings.
    original = copy.deepcopy(e["junction_controls"])
    if type(original) is not list:
        raise ConfigError("Require explicit junction controls")
    for group in e["junction_controls"]:
        _fields(group, {"junction_id", "schedule"}, "junction control")
        if group["junction_id"] not in gates or type(group["schedule"]) is not list:
            raise ConfigError("Unknown or malformed junction control")
        for c in group["schedule"]:
            _fields(c, {"time", "availability"}, "junction control change")
            c["availability"] = (
                fraction(c["availability"], "availability") * (gates[group["junction_id"]][3])
            )
    m["id"], x["solver"] = base.MODEL_ID, "rk4"
    passive = base.parse(raw, field_solver=FACTORED_SOLVER_ID)
    m0 = passive.model
    membranes = tuple(
        kinetic.Membrane(**asdict(p), pump=parse_pump(q, m0.species_ids, m0.valence))
        for p, q in zip(m0.membranes, pumps, strict=True)
    )
    junctions = tuple(
        kinetic.Junction(**asdict(p), **dict(zip(GATE_FIELDS, gates[p.id], strict=True)))
        for p in m0.junctions
    )
    names = [
        p.id
        for p in (
            *m0.cells,
            *m0.extracellular,
            *membranes,
            *junctions,
            *m0.faces,
            *(p.pump for p in membranes if p.pump is not None),
        )
    ]
    if len(names) != len(set(names)):
        raise ConfigError("Owner, route and pump IDs must be globally unique")
    end = passive.experiment.end_time
    ps = _schedules(
        pump_controls, "pump", [p.pump.id for p in membranes if p.pump is not None], end
    )
    js = _schedules(original, "junction", [p.id for p in junctions], end)
    model = SurfacePumpModel(
        **{
            k: getattr(m0, k)
            for k in base.SurfaceTissueModel.__dataclass_fields__
            if k not in ("membranes", "junctions")
        },
        membranes=membranes,
        junctions=junctions,
    )
    experiment = kinetic.Experiment(
        end,
        passive.experiment.observation_times,
        passive.experiment.membranes,
        tuple(js[p.id] for p in junctions),
        (),
        tuple((ChannelChange(0.0, 0.0),) if p.pump is None else ps[p.pump.id] for p in membranes),
    )
    spec = replace(
        passive,
        model=model,
        experiment=experiment,
        execution=kinetic.Execution(
            **(asdict(passive.execution) | {"solver": solver}), channel_capacity=0
        ),
    )
    from cells.models.surface_pump import check_definition

    try:
        check_definition(spec)
    except (ArithmeticError, ValueError) as error:
        raise ConfigError("Invalid resolved pump definition: " + str(error)) from error
    return spec
