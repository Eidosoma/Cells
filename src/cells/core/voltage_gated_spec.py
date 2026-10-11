"""Strict channel assembly schema composed with the existing ionic definition."""

import math
from dataclasses import asdict, fields

from cells.core import multispecies_spec as ionic
from cells.core.specs import (
    MULTISPECIES_ID,
    VOLTAGE_GATED_ID,
    ChannelChange,
    ChannelSpec,
    ConfigError,
    ExperimentSpec,
    MultispeciesExecutionSpec,
    MultispeciesSpec,
    SimulationSpec,
    VoltageGatedExecutionSpec,
    VoltageGatedExperimentSpec,
    VoltageGatedSpec,
    _fields,
    _integer,
    _number,
)
from cells.processes.voltage_gates import LAW_ID, TEMPERATURE_K, VOLTAGE_DOMAIN_V


def fraction(value, name):
    value = _number(value, name)
    if value > 1:
        raise ConfigError(f"{name} must lie in [0, 1]")
    return value


def project(value, target):
    """Explicit host projection, never discard additional state on the device."""
    return target(**{f.name: getattr(value, f.name) for f in fields(target)})


def to_dict(spec):
    m, e, x = spec.model, spec.experiment, spec.execution
    if type(e) is not VoltageGatedExperimentSpec or type(x) is not VoltageGatedExecutionSpec:
        raise ConfigError("Gated membrane requires its own experiment and execution schemas")
    if type(m.channel) is not ChannelSpec or any(type(p) is not ChannelChange for p in e.channel):
        raise ConfigError("Channel and controls must use their declared immutable types")
    if not isinstance(m.channel.initial_gate, tuple) or len(m.channel.initial_gate) != 2:
        raise ConfigError("Channel initial_gate must explicitly retain the immutable m/h pair")
    base = SimulationSpec(
        project(m, MultispeciesSpec),
        ExperimentSpec(e.end_time, (), e.observation_times, leak=e.leak, pump=e.pump),
        project(x, MultispeciesExecutionSpec),
    )
    result = ionic.to_dict(base)
    result["model"]["id"] = VOLTAGE_GATED_ID
    result["model"]["channel"] = asdict(m.channel) | {
        "initial_gate": dict(zip(("m", "h"), m.channel.initial_gate, strict=True))
    }
    result["experiment"]["channel_controls"] = {
        "channel_id": m.channel.id,
        "schedule": [asdict(p) for p in e.channel],
    }
    result["execution"]["channel_capacity"] = x.channel_capacity
    return result


def parse(data):
    root = _fields(data["model"], {"id", "species", "cell", "bath", "membrane", "channel"}, "model")
    experiment = _fields(
        data["experiment"],
        {"end_time", "observation_times", "membrane_controls", "channel_controls"},
        "experiment",
    )
    execution = _fields(
        data["execution"],
        set(VoltageGatedExecutionSpec.__dataclass_fields__) - {"edge_capacity"},
        "execution",
    )
    base = ionic.parse(
        data
        | {
            "model": {k: v for k, v in root.items() if k != "channel"} | {"id": MULTISPECIES_ID},
            "experiment": {k: v for k, v in experiment.items() if k != "channel_controls"},
            "execution": {k: v for k, v in execution.items() if k != "channel_capacity"},
        }
    )
    c = _fields(root["channel"], set(ChannelSpec.__dataclass_fields__), "channel")
    g = _fields(c["initial_gate"], {"m", "h"}, "channel initial_gate")
    channel = ChannelSpec(
        ionic.identifier(c["id"]),
        ionic.identifier(c["membrane_id"]),
        ionic.identifier(c["species_id"]),
        c["kinetic_law"],
        _number(c["max_permeability_m_per_s"], "channel permeability"),
        _number(c["abundance"], "channel abundance"),
        (fraction(g["m"], "activation gate"), fraction(g["h"], "inactivation gate")),
    )
    m = base.model
    if channel.kinetic_law != LAW_ID:
        raise ConfigError("Unsupported channel kinetic law")
    if channel.id in (m.cell_id, m.bath_id, m.membrane_id, m.pump_id):
        raise ConfigError("Channel ID must be distinct from physical owner IDs")
    if channel.membrane_id != m.membrane_id:
        raise ConfigError("Channel must bind the declared membrane")
    if (
        channel.species_id not in m.species_ids
        or m.valence[m.species_ids.index(channel.species_id)] != 1
    ):
        raise ConfigError("Channel potassium role must bind a declared +1 species")
    if m.temperature_K != TEMPERATURE_K:
        raise ConfigError("The gate law supports only the 298.15 K engineering fixture")
    if not VOLTAGE_DOMAIN_V[0] <= m.initial_voltage_V <= VOLTAGE_DOMAIN_V[1]:
        raise ConfigError("Initial voltage outside channel [-0.120, 0.060] V domain")
    scaled = channel.max_permeability_m_per_s * channel.abundance
    if not math.isfinite(scaled) or not math.isfinite(m.area_m2 * scaled / 1e-15):
        raise ConfigError("Derived channel coefficient exceeds finite float64")
    controls = _fields(
        experiment["channel_controls"], {"channel_id", "schedule"}, "channel controls"
    )
    if controls["channel_id"] != channel.id:
        raise ConfigError("Channel controls must identify the declared channel")
    if not isinstance(controls["schedule"], list) or not controls["schedule"]:
        raise ConfigError("Channel availability requires an explicit nonempty schedule")
    changes = []
    for entry in controls["schedule"]:
        _fields(entry, {"time", "availability"}, "channel control")
        time = _number(entry["time"], "channel control time")
        if time > base.experiment.end_time or (changes and time <= changes[-1].time):
            raise ConfigError("Channel control times must strictly increase within the horizon")
        changes.append(ChannelChange(time, fraction(entry["availability"], "channel availability")))
    if changes[0].time != 0:
        raise ConfigError("Channel availability must explicitly start at zero")
    return SimulationSpec(
        VoltageGatedSpec(**asdict(m), channel=channel),
        VoltageGatedExperimentSpec(
            base.experiment.end_time,
            base.experiment.observation_times,
            base.experiment.leak,
            base.experiment.pump,
            tuple(changes),
        ),
        VoltageGatedExecutionSpec(
            **asdict(base.execution),
            channel_capacity=_integer(execution["channel_capacity"], "channel capacity"),
        ),
    )
