"""Strict fixed-graph assembly composed from the existing local physical schemas."""

from dataclasses import asdict, replace

from cells.core import multispecies_spec as ionic
from cells.core import voltage_gated_spec as gated
from cells.core.bioelectric_spec import positive
from cells.core.specs import (
    MULTISPECIES_ID,
    PHYSICAL_IONIC_GRAPH_ID,
    VOLTAGE_GATED_ID,
    ChannelChange,
    ChannelSpec,
    ConfigError,
    ContactChange,
    ExperimentSpec,
    IonicJunctionSpec,
    MembraneSchedule,
    MultispeciesExecutionSpec,
    MultispeciesSpec,
    PhysicalIonicGraphExecutionSpec,
    PhysicalIonicGraphExperimentSpec,
    PhysicalIonicGraphSpec,
    SimulationSpec,
    _fields,
    _integer,
    _number,
)

GATE_LAW = "symmetric_opposing_relaxation@1"
COMMON = (
    "species_ids",
    "valence",
    "bath_id",
    "temperature_K",
    "bath_mM",
    "bath_background_charge_mM",
)


def _tuple(value, kind, name, *, size=None):
    if type(value) is not tuple or any(type(v) is not kind for v in value):
        raise ConfigError(f"{name} must be an immutable tuple of {kind.__name__}")
    if size is not None and len(value) != size:
        raise ConfigError(f"{name} has an incompatible length")


def to_dict(spec):
    m, e, x = spec.model, spec.experiment, spec.execution
    if (
        type(e) is not PhysicalIonicGraphExperimentSpec
        or type(x) is not PhysicalIonicGraphExecutionSpec
    ):
        raise ConfigError("Physical ionic graph requires its own experiment/execution schemas")
    _tuple(m.cells, MultispeciesSpec, "cells")
    _tuple(m.channels, ChannelSpec, "channels")
    _tuple(m.junctions, IonicJunctionSpec, "junctions")
    if not m.cells:
        raise ConfigError("A graph requires at least one cell")
    _tuple(e.membranes, MembraneSchedule, "membrane schedules", size=len(m.cells))
    for groups, objects, kind in (
        (e.channels, m.channels, ChannelChange),
        (e.junctions, m.junctions, ContactChange),
    ):
        _tuple(groups, tuple, "route schedules", size=len(objects))
        for group in groups:
            _tuple(group, kind, "schedule")
    first = m.cells[0]
    if any(getattr(c, key) != getattr(first, key) for c in m.cells for key in COMMON):
        raise ConfigError("All cells require the identical declared species table and bath")
    channel_map = {c.membrane_id: c for c in m.channels}
    if len(channel_map) != len(m.channels) or not set(channel_map) <= {
        c.membrane_id for c in m.cells
    }:
        raise ConfigError("Require at most one channel per declared membrane")
    # Canonical channel order is owner cell order. Never silently reorder state/control axes.
    if (
        tuple(channel_map[c.membrane_id] for c in m.cells if c.membrane_id in channel_map)
        != m.channels
    ):
        raise ConfigError("Channel tuple must follow its owner cell order")
    local, schedules = [], []
    for cell, controls in zip(m.cells, e.membranes, strict=True):
        base = ionic.to_dict(
            SimulationSpec(
                cell,
                ExperimentSpec(
                    e.end_time, (), e.observation_times, leak=controls.leak, pump=controls.pump
                ),
                replace(gated.project(x, MultispeciesExecutionSpec), edge_capacity=0),
            )
        )
        c = channel_map.get(cell.membrane_id)
        if c is not None and (type(c.initial_gate) is not tuple or len(c.initial_gate) != 2):
            raise ConfigError("Channel requires its explicit immutable m/h pair")
        local.append(
            {k: base["model"][k] for k in ("cell", "membrane")}
            | {
                "channel": None
                if c is None
                else asdict(c)
                | {"initial_gate": dict(zip(("m", "h"), c.initial_gate, strict=True))}
            }
        )
        schedules.append(base["experiment"]["membrane_controls"])
    edges = []
    for edge in m.junctions:
        if any(
            type(getattr(edge, key)) is not tuple
            or len(getattr(edge, key)) != len(first.species_ids)
            for key in ("permeability_m_per_s", "residual_fraction")
        ):
            raise ConfigError("Junction species arrays must be complete immutable tuples")
        edges.append(
            {
                "id": edge.id,
                "from_cell": edge.from_cell,
                "to_cell": edge.to_cell,
                "area_m2": edge.area_m2,
                **{
                    key: dict(zip(first.species_ids, getattr(edge, key), strict=True))
                    for key in ("permeability_m_per_s", "residual_fraction")
                },
                "gate": {
                    key: getattr(edge, key)
                    for key in (
                        "law",
                        "sensitivity_per_V",
                        "half_voltage_V",
                        "tau_s",
                        "initial_gate",
                    )
                },
            }
        )
    execution = asdict(x) | {
        "material_balance_atol_fmol": base["execution"]["material_balance_atol_fmol"]
    }
    return {
        "schema_version": 1,
        "model": {
            "id": PHYSICAL_IONIC_GRAPH_ID,
            "species": base["model"]["species"],
            "bath": base["model"]["bath"],
            "cells": local,
            "junctions": edges,
        },
        "experiment": {
            "end_time": e.end_time,
            "observation_times": list(e.observation_times),
            "membrane_controls": schedules,
            "channel_controls": [
                {"channel_id": c.id, "schedule": [asdict(p) for p in group]}
                for c, group in zip(m.channels, e.channels, strict=True)
            ],
            "junction_controls": [
                {"junction_id": c.id, "schedule": [asdict(p) for p in group]}
                for c, group in zip(m.junctions, e.junctions, strict=True)
            ],
        },
        "execution": execution,
    }


def _controls(value, id_key, fields):
    if type(value) is not list:
        raise ConfigError("Control groups must be explicit lists, including when empty")
    result = {}
    for entry in value:
        _fields(entry, {id_key, *fields}, "controls")
        key = ionic.identifier(entry[id_key])
        if key in result:
            raise ConfigError("Duplicate control owner")
        result[key] = entry
    return result


def parse(data):
    root = _fields(data["model"], {"id", "species", "bath", "cells", "junctions"}, "model")
    e = _fields(
        data["experiment"],
        {
            "end_time",
            "observation_times",
            "membrane_controls",
            "channel_controls",
            "junction_controls",
        },
        "experiment",
    )
    x = _fields(
        data["execution"], set(PhysicalIonicGraphExecutionSpec.__dataclass_fields__), "execution"
    )
    if type(root["cells"]) is not list or not root["cells"] or type(root["junctions"]) is not list:
        raise ConfigError("Require a nonempty cell list and an explicit junction list")
    membranes = _controls(e["membrane_controls"], "membrane_id", ("leak", "pump"))
    channels = _controls(e["channel_controls"], "channel_id", ("schedule",))
    junctions = _controls(e["junction_controls"], "junction_id", ("schedule",))
    cells, channel_specs, membrane_schedules, channel_schedules = [], [], [], []
    for entry in root["cells"]:
        _fields(entry, {"cell", "membrane", "channel"}, "local cell")
        if not isinstance(entry["membrane"], dict):
            raise ConfigError("Local membrane must be an identified object")
        membrane_id = ionic.identifier(entry["membrane"].get("id"))
        if membrane_id not in membranes:
            raise ConfigError("Every local membrane needs an identified control schedule")
        c = entry["channel"]
        local = {
            "schema_version": 1,
            "model": {
                "id": MULTISPECIES_ID,
                "species": root["species"],
                "bath": root["bath"],
                "cell": entry["cell"],
                "membrane": entry["membrane"],
            },
            "experiment": {
                "end_time": e["end_time"],
                "observation_times": e["observation_times"],
                "membrane_controls": membranes[entry["membrane"]["id"]],
            },
            "execution": {
                k: v for k, v in x.items() if k not in ("edge_capacity", "channel_capacity")
            },
        }
        if c is None:
            base = ionic.parse(local)
        else:
            if not isinstance(c, dict):
                raise ConfigError("Local channel must be an identified object or null")
            channel_id = ionic.identifier(c.get("id"))
            if channel_id not in channels:
                raise ConfigError("Every local channel needs an identified availability schedule")
            local["model"].update(id=VOLTAGE_GATED_ID, channel=c)
            local["experiment"]["channel_controls"] = channels[c["id"]]
            # Local parsing validates only physical/control meaning, not global capacities.
            local["execution"]["channel_capacity"] = 1
            base = gated.parse(local)
            channel_specs.append(base.model.channel)
            channel_schedules.append(base.experiment.channel)
        cells.append(gated.project(base.model, MultispeciesSpec))
        membrane_schedules.append(MembraneSchedule(base.experiment.leak, base.experiment.pump))
    if set(membranes) != {c.membrane_id for c in cells} or set(channels) != {
        c.id for c in channel_specs
    }:
        raise ConfigError("Control owners must exactly match declared membranes/channels")
    first, edges, edge_schedules = cells[0], [], []
    owners = [first.bath_id]
    for cell in cells:
        owners += [cell.cell_id, cell.membrane_id]
        if cell.pump_id is not None:
            owners.append(cell.pump_id)
    owners += [c.id for c in channel_specs]
    pairs, cell_ids = set(), [c.cell_id for c in cells]
    for entry in root["junctions"]:
        _fields(
            entry,
            {
                "id",
                "from_cell",
                "to_cell",
                "area_m2",
                "permeability_m_per_s",
                "residual_fraction",
                "gate",
            },
            "junction",
        )
        g = _fields(
            entry["gate"],
            {"law", "sensitivity_per_V", "half_voltage_V", "tau_s", "initial_gate"},
            "junction gate",
        )
        edge = IonicJunctionSpec(
            *(ionic.identifier(entry[k]) for k in ("id", "from_cell", "to_cell")),
            positive(entry["area_m2"], "junction area"),
            ionic.aligned(
                entry["permeability_m_per_s"], first.species_ids, "junction permeability"
            ),
            ionic.aligned(
                entry["residual_fraction"], first.species_ids, "residual fraction", gated.fraction
            ),
            g["law"],
            positive(g["sensitivity_per_V"], "junction sensitivity"),
            _number(g["half_voltage_V"], "half voltage"),
            positive(g["tau_s"], "junction tau"),
            gated.fraction(g["initial_gate"], "junction gate"),
        )
        if (
            edge.law != GATE_LAW
            or edge.from_cell == edge.to_cell
            or any(c not in cell_ids for c in (edge.from_cell, edge.to_cell))
        ):
            raise ConfigError(
                "Junction requires supported gate law and distinct declared endpoints"
            )
        pair = frozenset((edge.from_cell, edge.to_cell))
        if pair in pairs:
            raise ConfigError("Duplicate physical edge, including a reversed duplicate")
        pairs.add(pair)
        owners.append(edge.id)
        if edge.id not in junctions:
            raise ConfigError("Every junction requires an identified schedule")
        schedule = junctions[edge.id]["schedule"]
        if type(schedule) is not list or not schedule:
            raise ConfigError("Junction schedule must be explicitly nonempty")
        changes = []
        for p in schedule:
            _fields(p, {"time", "open_fraction"}, "junction control")
            time = _number(p["time"], "junction time")
            if time > base.experiment.end_time or (changes and time <= changes[-1].time):
                raise ConfigError("Junction times must strictly increase within the horizon")
            changes.append(
                ContactChange(time, gated.fraction(p["open_fraction"], "junction availability"))
            )
        if changes[0].time != 0:
            raise ConfigError("Junction availability must explicitly start at zero")
        edges.append(edge)
        edge_schedules.append(tuple(changes))
    if len(set(owners)) != len(owners) or set(junctions) != {c.id for c in edges}:
        raise ConfigError("Physical IDs must be globally unique and control owners exact")
    execution = PhysicalIonicGraphExecutionSpec(
        **(
            asdict(gated.project(base.execution, MultispeciesExecutionSpec))
            | {
                "capacity": _integer(x["capacity"], "cell capacity", minimum=len(cells)),
                "membrane_capacity": _integer(
                    x["membrane_capacity"], "membrane capacity", minimum=len(cells)
                ),
                "channel_capacity": _integer(
                    x["channel_capacity"], "channel capacity", minimum=len(channel_specs)
                ),
                "edge_capacity": _integer(x["edge_capacity"], "edge capacity", minimum=len(edges)),
            }
        )
    )
    model = PhysicalIonicGraphSpec(tuple(cells), tuple(channel_specs), tuple(edges))
    from cells.models.physical_ionic_graph import check_definition

    check_definition(model)
    return SimulationSpec(
        model,
        PhysicalIonicGraphExperimentSpec(
            base.experiment.end_time,
            base.experiment.observation_times,
            tuple(membrane_schedules),
            tuple(channel_schedules),
            tuple(edge_schedules),
        ),
        execution,
    )
