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

import contextvars
import copy
from contextlib import contextmanager
from dataclasses import asdict, dataclass, replace

from cells.definitions import surface_kinetic_spec as kinetic
from cells.definitions import surface_tissue_spec as base
from cells.definitions.kinetic_pump_spec import parse_pump, pump_to_dict
from cells.definitions.spec_values import fraction, identifier, positive
from cells.definitions.specs import ChannelChange, ConfigError, _fields, _number
from cells.laws.junctions import junction_gate
from cells.laws.pumps.kinetic_pump import TEMPERATURE_DOMAIN_K
from cells.numerics import surface_imex as imex
from cells.numerics.surface_field import FACTORED_SOLVER_ID, FLOOR_SOLVER_ID

MODEL_ID = "resolved_pump_tissue@1"
GATE_LAW_ID = junction_gate.RELAXATION_LAW_ID
SOLVERS = ("rk4", imex.EULER_ID, imex.ARS222_ID)
GATE_FIELDS = ("law", "threshold_voltage_V", "minimum_open_fraction", "initial_gate")
EXECUTION_FIELDS = set(kinetic.Execution.__dataclass_fields__) - {"channel_capacity"}
# FR-30 (D262; the @3 owner's recorded exception in this file): the gate laws a calling family's
# parse admits beyond this model's own, each by its law ID with its block's parser, block ->
# (minimum, initial, junction class, its extra fields), the minimum and initial being the
# junction's conductance. Empty outside such a parse, so @1 and @2 refuse every other law;
# resolved_pump_tissue@3's parse admits junction_series_gates@1 (admitting).
_ADMITTED_GATES = contextvars.ContextVar("admitted_gate_laws", default=())


@contextmanager
def admitting(parsers):
    """Within the block, this parse admits the given gate laws ({law ID: block parser})."""
    token = _ADMITTED_GATES.set(tuple(parsers.items()))
    try:
        yield
    finally:
        _ADMITTED_GATES.reset(token)


# The field solvers a later family admits beyond versions 2 and 3: resolved_pump_tissue@3's parse
# admits surface_field.SPARSE_SOLVER_ID (FR-17 stage 1) within its block, so @3 and the models that
# parse through it accept it, while this parse and @2's refuse it as any other declaration.
_ADMITTED_FIELD_SOLVERS = contextvars.ContextVar("admitted_field_solvers", default=())


@contextmanager
def admitting_field_solvers(ids):
    """Within the block, this parse admits the given field solver IDs as declared."""
    token = _ADMITTED_FIELD_SOLVERS.set(tuple(ids))
    try:
        yield
    finally:
        _ADMITTED_FIELD_SOLVERS.reset(token)


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
        target["gate"] = (  # FR-30: an admitted law's junction writes its own block.
            p.gate_block()
            if isinstance(p, kinetic.SeriesJunction)
            else {k: getattr(p, k) for k in GATE_FIELDS}
        )
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
    gates, admitted_junctions, admitted = {}, {}, dict(_ADMITTED_GATES.get())
    for p in m["junctions"]:
        _fields(p, set(base.Junction.__dataclass_fields__) | {"law", "gate"}, "junction")
        block = p.pop("gate")
        if isinstance(block, dict) and block.get("law") in admitted:  # FR-30: a caller's law.
            minimum, initial, junction_class, extra = admitted[block["law"]](block)
            gates[p["id"]] = (block["law"], 0.0, minimum, initial)  # Its threshold: read by none.
            admitted_junctions[p["id"]] = (junction_class, extra)
            continue
        g = _fields(block, set(GATE_FIELDS), "junction gate")
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
    scaled = []
    for group in e["junction_controls"]:
        _fields(group, {"junction_id", "schedule"}, "junction control")
        if group["junction_id"] not in gates or type(group["schedule"]) is not list:
            raise ConfigError("Unknown or malformed junction control")
        changes = []
        for c in group["schedule"]:
            _fields(c, {"time", "availability"}, "junction control change")
            changes.append(
                {
                    **c,
                    "availability": fraction(c["availability"], "availability")
                    * (gates[group["junction_id"]][3]),
                }
            )
        scaled.append({**group, "schedule": changes})
    # New control objects: a schedule shared with another control stays unscaled there.
    e["junction_controls"] = scaled
    m["id"], x["solver"] = base.MODEL_ID, "rk4"
    # The factored field, version 2 or (declared) version 3, or a field solver a later family
    # admits (admitting_field_solvers); any other declaration fails the passive parser's field
    # solver check as before.
    declared = x.get("field_solver")
    admitted = (FLOOR_SOLVER_ID, *_ADMITTED_FIELD_SOLVERS.get())
    passive = base.parse(
        raw, field_solver=declared if declared in admitted else FACTORED_SOLVER_ID
    )
    m0 = passive.model
    membranes = tuple(
        kinetic.Membrane(**asdict(p), pump=parse_pump(q, m0.species_ids, m0.valence))
        for p, q in zip(m0.membranes, pumps, strict=True)
    )
    today = (kinetic.Junction, {})
    junctions = tuple(
        admitted_junctions.get(p.id, today)[0](
            **asdict(p),
            **dict(zip(GATE_FIELDS, gates[p.id], strict=True)),
            **admitted_junctions.get(p.id, today)[1],
        )
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
