"""Explicit calcium channel ownership and controls on the plasma calcium family."""

from bisect import bisect_right
from dataclasses import asdict, dataclass, fields

from cells.core import plasma_calcium_spec as base
from cells.core.multispecies_spec import identifier
from cells.core.reaction_spec import bounded
from cells.core.spatial_calcium_spec import project
from cells.core.specs import ChannelChange, ChannelSpec, ConfigError, SimulationSpec, _fields
from cells.processes.calcium_gates import LAW_ID, TEMPERATURE_K

MODEL_ID = "spatial_calcium@3"


@dataclass(frozen=True)
class GatedCalciumModel(base.PlasmaModel):
    calcium_channels: tuple[ChannelSpec, ...]


@dataclass(frozen=True)
class GatedCalciumChange(base.PlasmaChange):
    calcium_channel: tuple[float, ...]


@dataclass(frozen=True)
class GatedCalciumExperiment(base.PlasmaExperiment):
    calcium_channel: tuple[tuple[ChannelChange, ...], ...]

    @property
    def changes(self):
        groups = [super().changes, *self.calcium_channel]
        times = [[p.time for p in group] for group in groups]
        return tuple(
            GatedCalciumChange(
                **(vars(groups[0][bisect_right(times[0], time) - 1]) | {"time": time}),
                calcium_channel=tuple(
                    g[bisect_right(ts, time) - 1].availability
                    for g, ts in zip(groups[1:], times[1:], strict=True)
                ),
            )
            for time in sorted({t for ts in times for t in ts})
        )


def base_spec(spec):
    return SimulationSpec(
        project(spec.model, base.PlasmaModel),
        project(spec.experiment, base.PlasmaExperiment),
        spec.execution,
    )


def to_dict(spec):
    raw = base.to_dict(base_spec(spec))
    raw["model"]["id"] = MODEL_ID
    raw["model"]["calcium_channels"] = [
        asdict(c) | {"initial_gate": dict(zip(("m", "h"), c.initial_gate, strict=True))}
        for c in spec.model.calcium_channels
    ]
    raw["experiment"]["calcium_channel_controls"] = [
        {"channel_id": c.id, "schedule": [asdict(p) for p in controls]}
        for c, controls in zip(
            spec.model.calcium_channels, spec.experiment.calcium_channel, strict=True
        )
    ]
    return raw


def parse(data, *, ionic_family=None):
    _fields(
        data["model"],
        {"id", "ionic", "stores", "plasma_transport", "calcium_channels"},
        "gated calcium model",
    )
    if data["model"]["id"] != MODEL_ID:
        raise ConfigError("Require the explicit gated calcium model identity")
    if "calcium_channel_controls" not in data["experiment"]:
        raise ConfigError("Require explicit calcium channel controls")
    original = base.parse(
        data
        | {
            "model": {k: v for k, v in data["model"].items() if k != "calcium_channels"}
            | {"id": base.MODEL_ID},
            "experiment": {
                k: v for k, v in data["experiment"].items() if k != "calcium_channel_controls"
            },
        },
        **({} if ionic_family is None else {"ionic_family": ionic_family}),
    )
    m = original.model
    membranes = [p.id for p in m.membranes]
    rows = data["model"]["calcium_channels"]
    if not isinstance(rows, list) or len(rows) != len(membranes):
        raise ConfigError("Require one calcium channel per membrane")
    occupied = {
        *(c.id for c in m.cells),
        *(c.id for c in m.channels),
        *(p.id for p in m.membranes),
        *(p.pump.id for p in m.membranes if p.pump is not None),
        *(j.id for j in m.junctions),
        *(f.id for f in m.faces),
        *(c.id for c in m.surroundings),
        m.extracellular.id,
        *m.species_ids,
    }
    channels = {}
    for row in rows:
        _fields(row, {f.name for f in fields(ChannelSpec)}, "calcium channel")
        gate = _fields(row["initial_gate"], {"m", "h"}, "calcium initial gate")
        name, owner, species = (identifier(row[k]) for k in ("id", "membrane_id", "species_id"))
        if name in occupied or owner not in membranes or owner in channels:
            raise ConfigError("Calcium channel IDs/owners must be distinct and declared")
        if species != m.calcium_species or row["kinetic_law"] != LAW_ID:
            raise ConfigError("Calcium channel requires the declared Ca(+2) and Cav1p2 law")
        occupied.add(name)
        channels[owner] = ChannelSpec(
            name,
            owner,
            species,
            LAW_ID,
            bounded(row["max_permeability_m_per_s"], "calcium permeability", 0, 1e-3),
            bounded(row["abundance"], "calcium channel abundance", 0, 1e6),
            tuple(bounded(gate[k], k + " gate", 0, 1) for k in ("m", "h")),
        )
    channels = tuple(channels[name] for name in membranes)
    if m.temperature_K != TEMPERATURE_K:
        raise ConfigError("Calcium gates require the 298.15 K engineering fixture")
    controls = data["experiment"]["calcium_channel_controls"]
    if not isinstance(controls, list) or len(controls) != len(channels):
        raise ConfigError("Require one calcium control per channel")
    schedules = {}
    for row in controls:
        _fields(row, {"channel_id", "schedule"}, "calcium channel control")
        name = identifier(row["channel_id"])
        if name not in {c.id for c in channels} or name in schedules:
            raise ConfigError("Calcium channel control owners must match exactly")
        schedule = row["schedule"]
        if not isinstance(schedule, list) or not schedule:
            raise ConfigError("Calcium channel schedules must start at zero")
        changes = []
        for p in schedule:
            _fields(p, {"time", "availability"}, "calcium channel availability")
            time = bounded(p["time"], "calcium control time", 0, original.experiment.end_time)
            if (not changes and time != 0) or (changes and time <= changes[-1].time):
                raise ConfigError("Calcium channel times must increase strictly from zero")
            changes.append(ChannelChange(time, bounded(p["availability"], "availability", 0, 1)))
        schedules[name] = tuple(changes)
    spec = SimulationSpec(
        GatedCalciumModel(**vars(m), calcium_channels=channels),
        GatedCalciumExperiment(
            **vars(original.experiment), calcium_channel=tuple(schedules[c.id] for c in channels)
        ),
        original.execution,
    )
    from cells.models.gated_calcium import check_definition

    check_definition(spec)
    return spec
