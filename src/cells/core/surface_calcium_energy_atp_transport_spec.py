"""Explicit native ATP hydrolysis coupled to one membrane owner's finite pool.

The supported native conversion is exactly ATP -> ADP + Pi. Ionic species
are transported without conversion. Fuels have the neutral transformed 1-M
standard; ionic stores retain their declared 1-mM zero standard potentials.
"""

from copy import deepcopy
from dataclasses import asdict, dataclass, replace

import numpy as np

from cells.core import surface_calcium_energy_spec as prior
from cells.core import surface_calcium_energy_transport_spec as legacy
from cells.core.bioelectric_spec import signed_number
from cells.core.specs import ConfigError, _fields, _integer, _number
from cells.core.surface_energy_spec import identifier
from cells.processes import betse_network_transport as process
from cells.processes import finite_energy as fuel
from cells.processes.electrochemistry import F, R

MODEL_ID = "resolved_calcium_energy_atp_transport@1"
ACCOUNTING = "finite_pool_atp_hydrolysis_species_transport@1"
DRIVE = "finite_energy_pool_hydrolysis@1"
CONSTANTS = dict(
    faraday_C_mol=F,
    gas_constant_J_mol_K=R,
    ionic_standard_state_mM=1.0,
    fuel_standard_state_mM=fuel.STANDARD_STATE_mM,
)


@dataclass(frozen=True)
class Drive:
    kind: str
    pool_id: str
    atp_per_cycle: int


@dataclass(frozen=True)
class Transporter:
    id: str
    membrane_id: str
    density_multiplier: float
    configuration: dict
    drive: Drive


@dataclass(frozen=True)
class SurfaceCalciumEnergyATPTransportModel(legacy.SurfaceCalciumEnergyTransportModel):
    network_transporters: tuple[Transporter, ...]


Execution, Control, Change, Experiment = (
    legacy.Execution,
    legacy.Control,
    legacy.Change,
    legacy.Experiment,
)
base_spec = legacy.base_spec


def to_dict(spec):
    if (
        type(spec.model) is not SurfaceCalciumEnergyATPTransportModel
        or type(spec.execution) is not Execution
        or type(spec.experiment) is not Experiment
    ):
        raise ConfigError("Require the exact ATP transport model/experiment/execution")
    raw = prior.to_dict(base_spec(spec))
    raw["model"].update(
        id=MODEL_ID,
        network_transport=dict(
            law=process.LAW_ID,
            accounting=ACCOUNTING,
            constants=dict(CONSTANTS),
            routes=[asdict(row) for row in spec.model.network_transporters],
        ),
    )
    raw["experiment"]["network_transport_controls"] = [
        dict(transporter_id=row.id, schedule=[asdict(change) for change in group])
        for row, group in zip(
            spec.model.network_transporters, spec.experiment.network_transports, strict=True
        )
    ]
    raw["execution"]["network_transport_capacity"] = spec.execution.network_transport_capacity
    return raw


def _routes(block, model):
    _fields(block, {"law", "accounting", "constants", "routes"}, "ATP transport")
    constants = _fields(block["constants"], set(CONSTANTS), "ATP transport constants/standards")
    if (
        block["law"] != process.LAW_ID
        or block["accounting"] != ACCOUNTING
        or any(_number(constants[key], key) != value for key, value in CONSTANTS.items())
    ):
        raise ConfigError("Declare the native law, finite-fuel accounting and physical standards")
    if type(block["routes"]) is not list:
        raise ConfigError("ATP transport routes must be a list")
    if set(model.species_ids) & set(fuel.SPECIES):
        raise ConfigError("ATP/ADP/Pi belong exclusively to the finite neutral energy pools")
    membranes, pools = (
        {row.id: row for row in model.membranes},
        {row.id: row for row in model.energy_pools},
    )
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
    result, native_names = [], set()
    for row in block["routes"]:
        _fields(row, set(Transporter.__dataclass_fields__), "ATP transporter")
        name, membrane = identifier(row["id"]), identifier(row["membrane_id"])
        density = _number(row["density_multiplier"], "ATP transport density")
        if name in occupied or membrane not in membranes or density < 0:
            raise ConfigError(
                "Require unique ATP route IDs, membrane owners and nonnegative density"
            )
        occupied.add(name)
        drive = _fields(row["drive"], set(Drive.__dataclass_fields__), "finite ATP drive")
        pool = identifier(drive["pool_id"])
        if (
            drive["kind"] != DRIVE
            or isinstance(drive["atp_per_cycle"], bool)
            or _number(drive["atp_per_cycle"], "ATP per cycle") != 1
            or pool not in pools
            or pools[pool].cell_id != membranes[membrane].inside
        ):
            raise ConfigError("Require exactly one ATP from this membrane's cytosolic energy pool")
        config = row["configuration"]
        if type(config) is not dict:
            raise ConfigError("Require an explicit native ATP transporter configuration")
        try:
            process.bind(
                [config],
                (*model.species_ids, *fuel.SPECIES),
                (*model.valence, 0, 0, 0),
                [0],
                [1],
                [True, True],
                area_m2=[1.0],
                temperature_K=model.temperature_K,
            )
        except (ValueError, TypeError) as error:
            raise ConfigError("Invalid native ATP transporter: " + str(error)) from error
        if config["name"] in native_names:
            raise ConfigError("Native ATP transporter names must be unique")
        native_names.add(config["name"])
        standard = signed_number(config["standard free energy"], "numeric native standard energy")
        if standard != pools[pool].delta_g0_J_per_mol:
            raise ConfigError(
                "Native standard energy must equal the pool's 1-M hydrolysis delta_g0"
            )
        reactants = dict(zip(config["reactants"], config["reactant multipliers"], strict=True))
        products = dict(zip(config["products"], config["product multipliers"], strict=True))
        if (
            {key: value for key, value in reactants.items() if key in fuel.SPECIES} != {"ATP": 1}
            or {key: value for key, value in products.items() if key in fuel.SPECIES}
            != {"ADP": 1, "Pi": 1}
            or {key: value for key, value in reactants.items() if key not in fuel.SPECIES}
            != {key: value for key, value in products.items() if key not in fuel.SPECIES}
        ):
            raise ConfigError("Require exactly ATP -> ADP + Pi and preserved ionic coefficients")
        if config.get("ignore ECM", False) is not False or config.get("apply to", "all") != "all":
            raise ConfigError("Require the finite exterior and explicit membrane owner")
        inward, outward = config["transfered into cell"], config["transfered out of cell"]
        inward = [] if inward is None or inward == "None" else inward
        outward = [] if outward is None or outward == "None" else outward
        if set(fuel.SPECIES) & (set(inward) | set(outward)):
            raise ConfigError("ATP/ADP/Pi are internal neutral pools, never membrane cargo")
        if set(inward) == set(outward):
            raise ConfigError("Require at least one net transported ionic species")
        result.append(Transporter(name, membrane, density, deepcopy(config), Drive(DRIVE, pool, 1)))
    return tuple(result)


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
        raise ConfigError("Declare ATP transport, controls and capacity") from error
    raw["model"]["id"] = prior.HCN_EXTRA_MODEL_ID
    original = prior.parse(raw)
    routes = _routes(block, original.model)
    spec = replace(
        original,
        model=SurfaceCalciumEnergyATPTransportModel(
            **vars(original.model), network_transporters=routes
        ),
        experiment=Experiment(
            **vars(original.experiment),
            network_transports=legacy._controls(schedules, routes, original.experiment.end_time),
        ),
        execution=Execution(
            **vars(original.execution),
            network_transport_capacity=_integer(
                capacity, "ATP route capacity", minimum=len(routes)
            ),
        ),
    )
    from cells.models import surface_calcium_energy_atp_transport as implementation

    try:
        with np.errstate(all="ignore"):
            implementation.check_definition(spec)
    except (ValueError, ArithmeticError) as error:
        raise ConfigError("Invalid finite ATP transport: " + str(error)) from error
    return spec
