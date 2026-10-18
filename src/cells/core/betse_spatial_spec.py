"""Portable fixed-geometry inputs for the native BETSE active compatibility law."""

from dataclasses import asdict, dataclass
from typing import NamedTuple

import numpy as np

from cells.core.multispecies_spec import identifier
from cells.core.specs import (
    ConfigError,
    MultispeciesExecutionSpec,
    SimulationSpec,
    _fields,
    _integer,
    _number,
)
from cells.numerics import betse_active as active
from cells.numerics import betse_spatial as passive
from cells.processes import kinetic_pump, voltage_gates

MODEL_ID = active.MODEL_ID
SOLVER_ID = "betse_ordered_euler@1"
INITIAL_FIELDS = (
    "cell_concentration",
    "membrane_concentration",
    "outside_concentration",
    "m_gate",
    "h_gate",
)
INTEGER_FIELDS = ("cell_owner", "outside_owner", "partner", "valence")


@dataclass(frozen=True)
class BetseSpatialModel:
    species_ids: tuple[str, ...]
    tissue: tuple
    pump: tuple
    sodium_index: int
    potassium_index: int
    pump_available: tuple
    channel_permeability: tuple
    initial: tuple


@dataclass(frozen=True)
class Change:
    time: float
    pump: tuple[float, ...]
    channel: tuple[float, ...]


class Control(NamedTuple):
    pump: object
    channel: object


@dataclass(frozen=True)
class Experiment:
    end_time: float
    observation_times: tuple[float, ...]
    changes: tuple[Change, ...] = ()


@dataclass(frozen=True)
class Execution(MultispeciesExecutionSpec):
    extracellular_capacity: int = 0


def immutable(value):
    return tuple(immutable(v) for v in value) if isinstance(value, list) else value


def portable(value):
    return [portable(v) for v in value] if isinstance(value, tuple) else value


def array(value, name, kind="float"):
    try:
        result = np.asarray(value)
        allowed = {"float": "fiu", "int": "iu", "bool": "b"}[kind]
        if result.dtype.kind not in allowed or not np.isfinite(result).all():
            raise ValueError("Wrong element type or nonfinite value")
        return result.astype({"float": np.float64, "int": np.int64, "bool": bool}[kind])
    except (TypeError, ValueError, OverflowError) as error:
        raise ConfigError("Invalid BETSE array: " + name) from error


def definition_arrays(model):
    tissue = passive.Layout(
        *(
            array(
                v,
                name,
                "bool" if name == "moving" else "int" if name in INTEGER_FIELDS else "float",
            )
            for name, v in zip(passive.Layout._fields, model.tissue, strict=True)
        )
    )
    layout = active.validate_layout(
        active.Layout(
            tissue,
            kinetic_pump.Parameters(*(np.asarray(v, dtype=float) for v in model.pump)),
            np.asarray(model.sodium_index, dtype=np.int64),
            np.asarray(model.potassium_index, dtype=np.int64),
            np.asarray(model.pump_available, dtype=float),
            np.asarray(model.channel_permeability, dtype=float),
        )
    )
    values = [np.asarray(v, dtype=float) for v in model.initial]
    state = active.initial_state(passive.initial_state(*values[:3], tissue), layout, *values[3:])
    return state, layout


def to_dict(spec):
    m, e, x = spec.model, spec.experiment, spec.execution
    if type(e) is not Experiment or type(x) is not Execution:
        raise ConfigError("BETSE compatibility requires its own experiment and execution")
    return dict(
        schema_version=1,
        model=dict(
            id=MODEL_ID,
            species=list(m.species_ids),
            tissue=dict(zip(passive.Layout._fields, map(portable, m.tissue), strict=True)),
            pump=dict(zip(kinetic_pump.Parameters._fields, map(portable, m.pump), strict=True)),
            sodium_index=m.sodium_index,
            potassium_index=m.potassium_index,
            pump_available=portable(m.pump_available),
            channel_permeability=portable(m.channel_permeability),
            initial=dict(zip(INITIAL_FIELDS, map(portable, m.initial), strict=True)),
        ),
        experiment=dict(end_time=e.end_time, observation_times=list(e.observation_times))
        | (
            {
                "changes": [
                    dict(time=c.time, pump=list(c.pump), channel=list(c.channel)) for c in e.changes
                ]
            }
            if e.changes
            else {}
        ),
        execution=asdict(x)
        | {
            "material_balance_atol_fmol": dict(
                zip(m.species_ids, x.material_balance_atol_fmol, strict=True)
            )
        },
    )


def parse(data, *, horizon_s=256e-6):
    m = _fields(
        data["model"],
        {
            "id",
            "species",
            "tissue",
            "pump",
            "sodium_index",
            "potassium_index",
            "pump_available",
            "channel_permeability",
            "initial",
        },
        "BETSE spatial model",
    )
    if m["id"] != MODEL_ID or type(m["species"]) is not list or not m["species"]:
        raise ConfigError("Require the active BETSE model and an ordered species list")
    ids = tuple(identifier(v) for v in m["species"])
    if len(set(ids)) != len(ids):
        raise ConfigError("Species IDs must be unique")
    tissue = _fields(m["tissue"], set(passive.Layout._fields), "BETSE static tissue")
    pump = _fields(m["pump"], set(kinetic_pump.Parameters._fields), "BETSE maintained pump")
    initial = _fields(m["initial"], set(INITIAL_FIELDS), "BETSE initial state")

    def frozen(value, name, kind="float"):
        return immutable(array(value, name, kind).tolist())

    model = BetseSpatialModel(
        ids,
        tuple(
            frozen(
                tissue[k], k, "bool" if k == "moving" else "int" if k in INTEGER_FIELDS else "float"
            )
            for k in passive.Layout._fields
        ),
        tuple(frozen(pump[k], k) for k in kinetic_pump.Parameters._fields),
        _integer(m["sodium_index"], "sodium_index", minimum=0, maximum=len(ids) - 1),
        _integer(m["potassium_index"], "potassium_index", minimum=0, maximum=len(ids) - 1),
        frozen(m["pump_available"], "pump_available"),
        frozen(m["channel_permeability"], "channel_permeability"),
        tuple(frozen(initial[k], k) for k in INITIAL_FIELDS),
    )
    try:
        state, layout = definition_arrays(model)
        p = layout.tissue
        if p.valence.size != len(ids) or np.any(p.valence != np.rint(p.valence)):
            raise ValueError("Species/valence inventory differs")
        if ids[model.sodium_index] != "Na" or ids[model.potassium_index] != "K":
            raise ValueError("Pump roles must name Na and K")
        field = passive.field(state.tissue, p, xp=np)
        lo, hi = voltage_gates.VOLTAGE_DOMAIN_V
        if any(not np.isfinite(v).all() for v in field) or np.any(
            (field.membrane_voltage_V < lo) | (field.membrane_voltage_V > hi)
        ):
            raise ValueError("Initial field is outside the active voltage domain")
    except (ValueError, TypeError, IndexError, ArithmeticError) as error:
        raise ConfigError("Invalid BETSE definition: " + str(error)) from error

    x = _fields(data["execution"], set(Execution.__dataclass_fields__), "BETSE execution")
    if x["solver"] != SOLVER_ID or x["precision"] != "float64":
        raise ConfigError("BETSE compatibility requires its ordered solver and float64")
    if x["backend"] not in ("cpu", "gpu") or type(x["jit"]) is not bool:
        raise ConfigError("Require CPU/GPU backend and boolean jit")
    dt = _number(x["dt"], "dt")
    if not 0 < dt <= 1e-6:
        raise ConfigError("BETSE compatibility timestep must be positive and at most 1 us")
    counts = dict(
        capacity=p.cell_volume.size,
        membrane_capacity=p.membrane_area.size,
        edge_capacity=p.membrane_area.size,
        extracellular_capacity=p.boundary_values.size,
    )
    for key, expected in counts.items():
        if _integer(x[key], key) != expected:
            raise ConfigError("BETSE capacities must equal explicit geometry: " + key)
    budgets = _fields(x["material_balance_atol_fmol"], set(ids), "material tolerances")
    atol = tuple(_number(budgets[k], "material tolerance") for k in ids)
    if any(v <= 0 for v in atol):
        raise ConfigError("Material tolerances must be positive")
    execution = Execution(
        dt=dt,
        **counts,
        jit=x["jit"],
        backend=x["backend"],
        precision="float64",
        solver=SOLVER_ID,
        max_steps=_integer(x["max_steps"], "max_steps", maximum=1_000_000),
        max_trace_bytes=_integer(x["max_trace_bytes"], "max_trace_bytes", maximum=2**53 - 1),
        material_balance_atol_fmol=atol,
    )
    fields = {"end_time", "observation_times"}
    if isinstance(data["experiment"], dict) and "changes" in data["experiment"]:
        fields.add("changes")
    e = _fields(data["experiment"], fields, "BETSE experiment")

    def clock(value):
        time = _number(value, "completed time")
        index = round(time / dt)
        if index < 0 or abs(time - index * dt) > 8 * np.finfo(float).eps * max(time, dt):
            raise ConfigError("BETSE times must be completed fixed-step boundaries")
        return index * dt, index

    end, steps = clock(e["end_time"])
    if not 0 < end <= horizon_s or steps > execution.max_steps:
        raise ConfigError(
            f"Initial BETSE runner requires a positive horizon up to {horizon_s * 1e6:g} us "
            "within max_steps"
        )
    if type(e["observation_times"]) is not list or not e["observation_times"]:
        raise ConfigError("Require explicit accepted observation times")
    observations = tuple(clock(v)[0] for v in e["observation_times"])
    if (
        observations[0] < 0
        or observations[-1] > end
        or any(b <= a for a, b in zip(observations, observations[1:], strict=False))
    ):
        raise ConfigError("Observation times must increase within the horizon")
    changes = []
    if "changes" in e:
        if type(e["changes"]) is not list or not e["changes"]:
            raise ConfigError("BETSE changes must be a nonempty list starting at zero")
        for entry in e["changes"]:
            entry = _fields(entry, {"time", "pump", "channel"}, "BETSE intervention")
            time, _ = clock(entry["time"])
            controls = []
            for key in ("pump", "channel"):
                if type(entry[key]) is not list or len(entry[key]) != p.membrane_area.size:
                    raise ConfigError("BETSE intervention fractions require one value per patch")
                values = np.asarray([_number(v, key) for v in entry[key]])
                if np.any((values < 0) | (values > 1)):
                    raise ConfigError(
                        "BETSE intervention fractions require one [0,1] value per patch"
                    )
                controls.append(tuple(values.tolist()))
            if time > end or (changes and time <= changes[-1].time) or (not changes and time != 0):
                raise ConfigError("BETSE changes must increase from zero within the horizon")
            changes.append(Change(time, *controls))
    return SimulationSpec(model, Experiment(end, observations, tuple(changes)), execution)
