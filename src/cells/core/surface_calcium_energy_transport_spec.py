"""Reversible native transport with explicit owners and maintained driving work."""

from bisect import bisect_right
from copy import deepcopy
from dataclasses import asdict, dataclass, replace
from typing import NamedTuple

import numpy as np

from cells.core import surface_calcium_energy_spec as prior
from cells.core.bioelectric_spec import signed_number
from cells.core.specs import ChannelChange, ConfigError, _fields, _integer, _number
from cells.core.surface_energy_spec import _project, identifier
from cells.core.voltage_gated_spec import fraction
from cells.processes import betse_network_transport as process
from cells.processes.electrochemistry import F, R

MODEL_ID = "resolved_calcium_energy_transport@1"
ACCOUNTING = "reversible_pure_transport_maintained_drive@1"
DRIVE = "maintained_work_per_cycle@1"


@dataclass(frozen=True)
class Drive:
    kind: str
    supplied_energy_J_per_mol: float


@dataclass(frozen=True)
class Transporter:
    id: str
    membrane_id: str
    density_multiplier: float
    configuration: dict
    drive: Drive


@dataclass(frozen=True)
class SurfaceCalciumEnergyTransportModel(prior.SurfaceCalciumEnergyHCNExtraModel):
    network_transporters: tuple[Transporter, ...]


@dataclass(frozen=True)
class Execution(prior.Execution):
    network_transport_capacity: int = 0


Control = NamedTuple(
    "SurfaceCalciumEnergyTransportControl",
    [(k, object) for k in (*prior.Control._fields, "network_transport")],
)


@dataclass(frozen=True)
class Change(prior.Change):
    network_transport: tuple[float, ...]


@dataclass(frozen=True)
class Experiment(prior.Experiment):
    network_transports: tuple[tuple[ChannelChange, ...], ...]

    @property
    def changes(self):
        groups = (super().changes, *self.network_transports)
        clocks = [[c.time for c in group] for group in groups]
        return tuple(
            Change(
                **(vars(groups[0][bisect_right(clocks[0], time) - 1]) | dict(time=time)),
                network_transport=tuple(
                    group[bisect_right(clock, time) - 1].availability
                    for group, clock in zip(groups[1:], clocks[1:], strict=True)
                ),
            )
            for time in sorted({time for clock in clocks for time in clock})
        )


def base_spec(spec):
    return replace(
        spec,
        model=_project(spec.model, prior.SurfaceCalciumEnergyHCNExtraModel),
        experiment=_project(spec.experiment, prior.Experiment),
        execution=_project(spec.execution, prior.Execution),
    )


def to_dict(spec):
    if (
        type(spec.model) is not SurfaceCalciumEnergyTransportModel
        or type(spec.experiment) is not Experiment
        or type(spec.execution) is not Execution
    ):
        raise ConfigError("Network transport requires its own model/experiment/execution")
    raw = prior.to_dict(base_spec(spec))
    raw["model"].update(
        id=MODEL_ID,
        network_transport=dict(
            law=process.LAW_ID,
            accounting=ACCOUNTING,
            constants=dict(faraday_C_mol=F, gas_constant_J_mol_K=R),
            routes=[asdict(route) for route in spec.model.network_transporters],
        ),
    )
    raw["experiment"]["network_transport_controls"] = [
        dict(transporter_id=route.id, schedule=[asdict(c) for c in group])
        for route, group in zip(
            spec.model.network_transporters, spec.experiment.network_transports, strict=True
        )
    ]
    raw["execution"]["network_transport_capacity"] = spec.execution.network_transport_capacity
    return raw


def _routes(block, model):
    _fields(block, {"law", "accounting", "constants", "routes"}, "network transport")
    constants = _fields(
        block["constants"], {"faraday_C_mol", "gas_constant_J_mol_K"}, "transport constants"
    )
    if (
        block["law"] != process.LAW_ID
        or block["accounting"] != ACCOUNTING
        or _number(constants["faraday_C_mol"], "Faraday constant") != F
        or _number(constants["gas_constant_J_mol_K"], "gas constant") != R
    ):
        raise ConfigError(
            "Declare the native law, reversible physical accounting and Cells SI constants"
        )
    rows = block["routes"]
    if type(rows) is not list:
        raise ConfigError("Network transport routes must be a list")
    membranes = {m.id for m in model.membranes}
    occupied = set(model.species_ids) | {
        p.id
        for p in (
            *model.cells,
            *model.extracellular,
            *model.membranes,
            *model.junctions,
            *model.faces,
            *model.channels,
            *model.calcium_channels,
            *model.energy_pools,
            *model.regeneration_ports,
            *(p.pump for p in model.membranes if p.pump is not None),
        )
    }
    result = []
    for row in rows:
        _fields(row, set(Transporter.__dataclass_fields__), "network transporter")
        name, membrane = identifier(row["id"]), identifier(row["membrane_id"])
        rho = _number(row["density_multiplier"], "transport density")
        if name in occupied or membrane not in membranes or rho < 0:
            raise ConfigError(
                "Transporters require unique IDs, a membrane owner and nonnegative density"
            )
        occupied.add(name)
        configuration = row["configuration"]
        if type(configuration) is not dict:
            raise ConfigError("Require an explicit native transporter configuration")
        # Bind the native dictionary first: list lengths, unique terms, positive
        # coefficients, regulator syntax, and native failures remain its contract.
        try:
            process.bind(
                [configuration],
                model.species_ids,
                model.valence,
                [0],
                [1],
                [True, True],
                area_m2=[1.0],
                temperature_K=model.temperature_K,
            )
        except (ValueError, TypeError) as error:
            raise ConfigError("Invalid native transporter: " + str(error)) from error
        standard = signed_number(
            configuration["standard free energy"], "reversible standard energy"
        )
        reactants = dict(
            zip(configuration["reactants"], configuration["reactant multipliers"], strict=True)
        )
        products = dict(
            zip(configuration["products"], configuration["product multipliers"], strict=True)
        )
        if reactants != products:
            raise ConfigError(
                "Coupled network transport must preserve every species; conversion is unsupported"
            )
        if (
            configuration.get("ignore ECM", False) is not False
            or configuration.get("apply to", "all") != "all"
        ):
            raise ConfigError(
                "Transport must update its finite exterior and use its explicit membrane owner"
            )
        inward = configuration["transfered into cell"]
        outward = configuration["transfered out of cell"]
        inward = [] if inward is None or inward == "None" else inward
        outward = [] if outward is None or outward == "None" else outward
        if set(inward) == set(outward):
            raise ConfigError("Require at least one net transferred species")
        drive = _fields(row["drive"], set(Drive.__dataclass_fields__), "transport drive")
        supplied = signed_number(drive["supplied_energy_J_per_mol"], "transport supplied work")
        if drive["kind"] != DRIVE or supplied != -standard:
            raise ConfigError(
                "Maintained work per cycle must explicitly equal minus the native standard energy"
            )
        result.append(
            Transporter(name, membrane, rho, deepcopy(configuration), Drive(DRIVE, supplied))
        )
    return tuple(result)


def _controls(rows, routes, end):
    if type(rows) is not list:
        raise ConfigError("Require explicit network transport controls")
    result = {}
    for row in rows:
        _fields(row, {"transporter_id", "schedule"}, "network transport control")
        name, schedule = identifier(row["transporter_id"]), row["schedule"]
        if name in result or type(schedule) is not list or not schedule:
            raise ConfigError("Require unique transporter controls with nonempty schedules")
        for value in schedule:
            _fields(value, {"time", "availability"}, "network transport change")
        changes = tuple(
            ChannelChange(
                _number(v["time"], "transport time"),
                fraction(v["availability"], "transport availability"),
            )
            for v in schedule
        )
        if (
            changes[0].time != 0
            or any(c.time > end for c in changes)
            or any(b.time <= a.time for a, b in zip(changes, changes[1:], strict=False))
        ):
            raise ConfigError(
                "Transport controls must start at zero and increase within the horizon"
            )
        result[name] = changes
    if set(result) != {r.id for r in routes}:
        raise ConfigError("Network transport control IDs must exactly match routes")
    return tuple(result[r.id] for r in routes)


def parse(data):
    _fields(data, {"schema_version", "model", "experiment", "execution"}, "definition")
    raw = deepcopy(data)
    if type(raw["model"]) is not dict or raw["model"].get("id") != MODEL_ID:
        raise ConfigError("Require " + MODEL_ID)
    try:
        block = raw["model"].pop("network_transport")
        schedules = raw["experiment"].pop("network_transport_controls")
        capacity = raw["execution"].pop("network_transport_capacity")
    except (KeyError, TypeError, AttributeError) as error:
        raise ConfigError("Declare network transport, controls and capacity") from error
    raw["model"]["id"] = prior.HCN_EXTRA_MODEL_ID
    original = prior.parse(raw)
    routes = _routes(block, original.model)
    spec = replace(
        original,
        model=SurfaceCalciumEnergyTransportModel(
            **vars(original.model), network_transporters=routes
        ),
        experiment=Experiment(
            **vars(original.experiment),
            network_transports=_controls(schedules, routes, original.experiment.end_time),
        ),
        execution=Execution(
            **vars(original.execution),
            network_transport_capacity=_integer(
                capacity, "network transport capacity", minimum=len(routes)
            ),
        ),
    )
    from cells.models import surface_calcium_energy_transport

    try:
        with np.errstate(all="ignore"):
            surface_calcium_energy_transport.check_definition(spec)
    except (ValueError, ArithmeticError) as error:
        raise ConfigError("Invalid coupled network transport: " + str(error)) from error
    return spec
