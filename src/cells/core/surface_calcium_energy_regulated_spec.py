"""Free-state Na/K regulation over the existing 38-field finite-calcium model."""

from copy import deepcopy
from dataclasses import asdict, dataclass, replace

import numpy as np

from cells.core import surface_calcium_energy_spec as prior
from cells.core.specs import ConfigError, _fields, _integer
from cells.core.surface_energy_spec import _project, identifier
from cells.core.voltage_gated_spec import fraction
from cells.processes import betse_network_modulation as modulation
from cells.processes import finite_energy as energy

MODEL_ID = "resolved_calcium_energy_regulated@1"
TIMING = "common_stage_free_cytosol_exterior_fuel@1"
COMPOSITION = "scheduled_times_ordered_native_nak_factor@1"
MAX_RULES = 64
MAX_TERMS = 16


@dataclass(frozen=True)
class Rule:
    id: str
    pump_id: str
    fuel_pool_id: str
    configuration: dict


@dataclass(frozen=True)
class SurfaceCalciumEnergyRegulatedModel(prior.SurfaceCalciumEnergyHCNExtraModel):
    network_regulators: tuple[Rule, ...]


@dataclass(frozen=True)
class Execution(prior.Execution):
    regulation_capacity: int = 0


Control = prior.Control
Experiment = prior.Experiment


def base_spec(spec):
    return replace(
        spec,
        model=_project(spec.model, prior.SurfaceCalciumEnergyHCNExtraModel),
        execution=_project(spec.execution, prior.Execution),
    )


def control_values(spec, times):
    from cells.core.schedule import control_values as inherited

    return inherited(base_spec(spec), times)


def to_dict(spec):
    if (
        type(spec.model) is not SurfaceCalciumEnergyRegulatedModel
        or type(spec.execution) is not Execution
    ):
        raise ConfigError("Regulated calcium requires its own model and execution declaration")
    raw = prior.to_dict(base_spec(spec))
    raw["model"].update(
        id=MODEL_ID,
        network_regulation=dict(
            law=modulation.LAW_ID,
            timing=TIMING,
            control_composition=COMPOSITION,
            rules=[asdict(r) for r in spec.model.network_regulators],
        ),
    )
    raw["execution"]["regulation_capacity"] = spec.execution.regulation_capacity
    return raw


def bind_rule(configuration, model):
    """One literal native rule on two owner-concentration read views, not pools."""
    return modulation.bind(
        [configuration],
        [],
        (*model.species_ids, *energy.SPECIES),
        (*model.valence, 0, 0, 0),
        np.asarray([0], int),
        1,
        model.species_ids,
        tj_targets=np.asarray([False]),
        temperature_K=model.temperature_K,
    )


def _rules(block, model):
    _fields(block, {"law", "timing", "control_composition", "rules"}, "network regulation")
    if (
        block["law"] != modulation.LAW_ID
        or block["timing"] != TIMING
        or block["control_composition"] != COMPOSITION
    ):
        raise ConfigError(
            "Declare source factor law, common-stage samples and schedule composition"
        )
    rows = block["rules"]
    if type(rows) is not list or len(rows) > MAX_RULES:
        raise ConfigError("Require an ordered bounded regulator list")
    pumps = {
        patch.pump.id: (patch, patch.pump) for patch in model.membranes if patch.pump is not None
    }
    pools = {p.id: p for p in model.energy_pools}
    occupied = (
        set(model.species_ids)
        | set(energy.SPECIES)
        | {
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
    )
    result = []
    for row in rows:
        _fields(row, set(Rule.__dataclass_fields__), "pump regulation rule")
        name, pump_id, pool_id = (identifier(row[k]) for k in ("id", "pump_id", "fuel_pool_id"))
        if name in occupied or pump_id not in pumps or pool_id not in pools:
            raise ConfigError(
                "Regulators need distinct IDs, an existing Na/K pump and named fuel owner"
            )
        occupied.add(name)
        patch, pump = pumps[pump_id]
        if pool_id != pump.metabolism.pool_id or pools[pool_id].cell_id != patch.inside:
            raise ConfigError("Regulator fuel samples must use the target pump's own finite pool")
        configuration = deepcopy(row["configuration"])
        if (
            type(configuration) is not dict
            or configuration.get("name") != name
            or configuration.get("target") != "Na/K-ATPase"
            or configuration.get("target ion") is not None
        ):
            raise ConfigError(
                "Require a named native Na/K-ATPase factor, without ion-only targeting"
            )
        fraction(configuration.get("max effect"), "Na/K regulator maximum effect")
        try:
            t, _ = bind_rule(configuration, model)
        except (ValueError, ArithmeticError) as error:
            raise ConfigError("Invalid native factor configuration: " + str(error)) from error
        if t.influencers.mode.shape[0] > MAX_TERMS:
            raise ConfigError("Regulator term count exceeds the declared dense limit")
        fuel = t.influencers.species >= len(model.species_ids)
        if np.any(fuel & (t.influencers.mode > 0) & (t.influencers.owner != 0)):
            raise ConfigError("Finite fuel has no exterior sample; declare the owner cell zone")
        result.append(Rule(name, pump_id, pool_id, configuration))
    return tuple(result)


def parse(data):
    _fields(data, {"schema_version", "model", "experiment", "execution"}, "regulated definition")
    raw = deepcopy(data)
    if (
        type(raw["model"]) is not dict
        or raw["model"].get("id") != MODEL_ID
        or "network_regulation" not in raw["model"]
    ):
        raise ConfigError("Require the explicit regulated finite-calcium model identity")
    block = raw["model"].pop("network_regulation")
    raw["model"]["id"] = prior.HCN_EXTRA_MODEL_ID
    if type(raw["execution"]) is not dict or "regulation_capacity" not in raw["execution"]:
        raise ConfigError("Declare the regulator rule capacity")
    capacity = raw["execution"].pop("regulation_capacity")
    original = prior.parse(raw)
    rules = _rules(block, original.model)
    capacity = _integer(capacity, "regulation capacity", minimum=len(rules), maximum=MAX_RULES)
    spec = replace(
        original,
        model=SurfaceCalciumEnergyRegulatedModel(**vars(original.model), network_regulators=rules),
        execution=Execution(**vars(original.execution), regulation_capacity=capacity),
    )
    from cells.models import surface_calcium_energy_regulated

    try:
        surface_calcium_energy_regulated.check_definition(spec)
    except (ValueError, ArithmeticError) as error:
        raise ConfigError("Invalid integrated pump regulation: " + str(error)) from error
    return spec
