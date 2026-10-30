"""Native None-energy transport with separate, declared physical work ownership."""

from copy import deepcopy
from dataclasses import dataclass, replace

import numpy as np

from cells.core import surface_calcium_energy_spec as prior
from cells.core import surface_calcium_energy_transport_spec as legacy
from cells.core.bioelectric_spec import signed_number
from cells.core.specs import ConfigError, _fields, _integer, _number
from cells.core.surface_energy_spec import identifier
from cells.processes import betse_network_transport as process
from cells.processes.electrochemistry import F, R

MODEL_ID = "resolved_calcium_energy_irreversible_transport@1"
ACCOUNTING = "irreversible_species_transport_explicit_physical_work@1"
DRIVE = legacy.DRIVE
Drive, Transporter = legacy.Drive, legacy.Transporter
Execution, Control, Change, Experiment = (
    legacy.Execution,
    legacy.Control,
    legacy.Change,
    legacy.Experiment,
)
base_spec = legacy.base_spec


@dataclass(frozen=True)
class SurfaceCalciumEnergyIrreversibleTransportModel(legacy.SurfaceCalciumEnergyTransportModel):
    """A distinct physical model; the reversible identity remains unchanged."""


def to_dict(spec):
    if (
        type(spec.model) is not SurfaceCalciumEnergyIrreversibleTransportModel
        or type(spec.execution) is not Execution
        or type(spec.experiment) is not Experiment
    ):
        raise ConfigError("Require the exact irreversible transport model/experiment/execution")
    # This is serialization of declarations, never a reversible parse/evaluation.
    old = replace(spec, model=legacy.SurfaceCalciumEnergyTransportModel(**vars(spec.model)))
    raw = legacy.to_dict(old)
    raw["model"]["id"] = MODEL_ID
    raw["model"]["network_transport"]["accounting"] = ACCOUNTING
    return raw


def _routes(block, model):
    _fields(block, {"law", "accounting", "constants", "routes"}, "irreversible network transport")
    constants = _fields(
        block["constants"], {"faraday_C_mol", "gas_constant_J_mol_K"}, "transport constants"
    )
    if (
        block["law"] != process.LAW_ID
        or block["accounting"] != ACCOUNTING
        or _number(constants["faraday_C_mol"], "Faraday constant") != F
        or _number(constants["gas_constant_J_mol_K"], "gas constant") != R
    ):
        raise ConfigError("Declare the native law, irreversible physical work and Cells constants")
    if type(block["routes"]) is not list:
        raise ConfigError("Irreversible network routes must be a list")
    membranes = {row.id for row in model.membranes}
    occupied = set(model.species_ids) | {
        row.id
        for row in (
            *model.cells,
            *model.extracellular,
            *model.membranes,
            *model.junctions,
            *model.faces,
            *model.channels,
            *model.calcium_channels,
            *model.energy_pools,
            *model.regeneration_ports,
            *(row.pump for row in model.membranes if row.pump is not None),
        )
    }
    result = []
    for row in block["routes"]:
        _fields(row, set(Transporter.__dataclass_fields__), "irreversible transporter")
        name, membrane = identifier(row["id"]), identifier(row["membrane_id"])
        density = _number(row["density_multiplier"], "transport density")
        if name in occupied or membrane not in membranes or density < 0:
            raise ConfigError(
                "Require unique route IDs, physical membrane owners and nonnegative density"
            )
        occupied.add(name)
        config = row["configuration"]
        if type(config) is not dict:
            raise ConfigError("Require an explicit native configuration")
        try:
            process.bind(
                [config],
                model.species_ids,
                model.valence,
                [0],
                [1],
                [True, True],
                area_m2=[1.0],
                temperature_K=model.temperature_K,
            )
        except (ValueError, TypeError) as error:
            raise ConfigError("Invalid native irreversible transporter: " + str(error)) from error
        standard = config["standard free energy"]
        if standard is not None and standard != "None":
            raise ConfigError("Irreversible transport must retain native None/string-None energy")
        reactants = dict(zip(config["reactants"], config["reactant multipliers"], strict=True))
        products = dict(zip(config["products"], config["product multipliers"], strict=True))
        if reactants != products:
            raise ConfigError(
                "Irreversible coupling preserves every species; conversion is unsupported"
            )
        if config.get("ignore ECM", False) is not False or config.get("apply to", "all") != "all":
            raise ConfigError("Require the finite exterior and explicit membrane owner")
        inside, outside = config["transfered into cell"], config["transfered out of cell"]
        inside = [] if inside is None or inside == "None" else inside
        outside = [] if outside is None or outside == "None" else outside
        if set(inside) == set(outside):
            raise ConfigError("Require at least one net transferred species")
        drive = _fields(row["drive"], set(Drive.__dataclass_fields__), "explicit transport work")
        supplied = signed_number(
            drive["supplied_energy_J_per_mol"], "signed external work per cycle"
        )
        if drive["kind"] != DRIVE:
            raise ConfigError("Declare maintained external work; no implicit ATP consumption")
        result.append(
            Transporter(name, membrane, density, deepcopy(config), Drive(DRIVE, supplied))
        )
    return tuple(result)


def parse(data):
    _fields(data, {"schema_version", "model", "experiment", "execution"}, "definition")
    raw = deepcopy(data)
    if type(raw["model"]) is not dict or raw["model"].get("id") != MODEL_ID:
        raise ConfigError("Require " + MODEL_ID)
    try:
        block = raw["model"].pop("network_transport")
        controls = raw["experiment"].pop("network_transport_controls")
        capacity = raw["execution"].pop("network_transport_capacity")
    except (KeyError, TypeError, AttributeError) as error:
        raise ConfigError("Declare irreversible routes, controls and capacity") from error
    raw["model"]["id"] = prior.HCN_EXTRA_MODEL_ID
    original = prior.parse(raw)
    routes = _routes(block, original.model)
    spec = replace(
        original,
        model=SurfaceCalciumEnergyIrreversibleTransportModel(
            **vars(original.model), network_transporters=routes
        ),
        experiment=Experiment(
            **vars(original.experiment),
            network_transports=legacy._controls(controls, routes, original.experiment.end_time),
        ),
        execution=Execution(
            **vars(original.execution),
            network_transport_capacity=_integer(
                capacity, "network transport capacity", minimum=len(routes)
            ),
        ),
    )
    from cells.models import surface_calcium_energy_irreversible_transport as implementation

    try:
        with np.errstate(all="ignore"):
            implementation.check_definition(spec)
    except (ValueError, ArithmeticError) as error:
        raise ConfigError("Invalid irreversible transport: " + str(error)) from error
    return spec
