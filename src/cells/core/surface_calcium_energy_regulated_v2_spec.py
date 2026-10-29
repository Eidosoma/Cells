"""Owned chemical/fuel availability factors for Na/K, shared channels and GJ."""

from copy import deepcopy
from dataclasses import asdict, dataclass, replace

import numpy as np

from cells.core import surface_calcium_energy_regulated_spec as v1
from cells.core import surface_calcium_energy_spec as parent
from cells.core.specs import ConfigError, _fields, _integer
from cells.core.surface_energy_spec import _project, identifier
from cells.core.voltage_gated_spec import fraction
from cells.processes import betse_network_modulation as source
from cells.processes import finite_energy as energy

MODEL_ID = "resolved_calcium_energy_regulated@2"
TIMING = v1.TIMING
COMPOSITION = "scheduled_times_ordered_nak_channel_junction_factor@2"
CHANNEL_SCOPE = "native_voltage_independent_sim_factor_only@1"
JUNCTION_SCOPE = "explicit_endpoint_cytosol_no_exterior@1"
NAK, CHANNEL, JUNCTION = 1, 2, 3
KINDS = {"nak": NAK, "channel": CHANNEL, "junction": JUNCTION}
MAX_RULES, MAX_TERMS = v1.MAX_RULES, v1.MAX_TERMS


@dataclass(frozen=True)
class Rule:
    id: str
    kind: str
    target_id: str
    sample_cell_id: str
    sample_exterior_id: str | None
    fuel_pool_id: str
    configuration: dict


@dataclass(frozen=True)
class SurfaceCalciumEnergyRegulatedV2Model(parent.SurfaceCalciumEnergyHCNExtraModel):
    network_regulators: tuple[Rule, ...]


@dataclass(frozen=True)
class Execution(parent.Execution):
    regulation_capacity: int = 0


Control = parent.Control
Experiment = parent.Experiment


def base_spec(spec):
    return replace(
        spec,
        model=_project(spec.model, parent.SurfaceCalciumEnergyHCNExtraModel),
        execution=_project(spec.execution, parent.Execution),
    )


def control_values(spec, times):
    from cells.core.schedule import control_values as inherited

    return inherited(base_spec(spec), times)


def to_dict(spec):
    if (
        type(spec.model) is not SurfaceCalciumEnergyRegulatedV2Model
        or type(spec.execution) is not Execution
    ):
        raise ConfigError("Regulated @2 requires its own model/execution types")
    raw = parent.to_dict(base_spec(spec))
    raw["model"].update(
        id=MODEL_ID,
        network_regulation=dict(
            law=source.LAW_ID,
            timing=TIMING,
            control_composition=COMPOSITION,
            channel_scope=CHANNEL_SCOPE,
            junction_scope=JUNCTION_SCOPE,
            rules=[asdict(r) for r in spec.model.network_regulators],
        ),
    )
    raw["execution"]["regulation_capacity"] = spec.execution.regulation_capacity
    return raw


def bind_rule(rule, model):
    channels = rule.kind == "channel"
    return source.bind(
        [] if channels else [rule.configuration],
        [rule.configuration] if channels else [],
        (*model.species_ids, *energy.SPECIES),
        (*model.valence, 0, 0, 0),
        np.asarray([0], int),
        1,
        model.species_ids,
        tj_targets=np.asarray([False]),
        temperature_K=model.temperature_K,
    )


def _rules(block, model):
    _fields(
        block,
        {"law", "timing", "control_composition", "channel_scope", "junction_scope", "rules"},
        "regulation @2",
    )
    if (
        block["law"],
        block["timing"],
        block["control_composition"],
        block["channel_scope"],
        block["junction_scope"],
    ) != (source.LAW_ID, TIMING, COMPOSITION, CHANNEL_SCOPE, JUNCTION_SCOPE):
        raise ConfigError(
            "Declare @2 factor law, common stages and explicit consumer/sample scopes"
        )
    rows = block["rules"]
    if type(rows) is not list or len(rows) > MAX_RULES:
        raise ConfigError("Require a bounded ordered rule list")
    membranes = {m.id: m for m in model.membranes}
    pumps = {m.pump.id: (i, m) for i, m in enumerate(model.membranes) if m.pump is not None}
    channels = {c.id: c for c in model.channels}
    junctions = {j.id: j for j in model.junctions}
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
                *(m.pump for m in model.membranes if m.pump is not None),
            )
        }
    )
    result = []
    for row in rows:
        _fields(row, set(Rule.__dataclass_fields__), "@2 rule")
        data = deepcopy(row)
        for key in ("id", "target_id", "sample_cell_id", "fuel_pool_id"):
            data[key] = identifier(data[key])
        if data["sample_exterior_id"] is not None:
            data["sample_exterior_id"] = identifier(data["sample_exterior_id"])
        name, kind, target = data["id"], data["kind"], data["target_id"]
        if (
            name in occupied
            or type(kind) is not str
            or kind not in KINDS
            or data["fuel_pool_id"] not in pools
        ):
            raise ConfigError(
                "Require unique rule IDs, supported consumers and an explicit fuel owner"
            )
        occupied.add(name)
        if pools[data["fuel_pool_id"]].cell_id != data["sample_cell_id"]:
            raise ConfigError("Rule fuel must belong to its explicitly sampled cytosol")
        if kind == "nak":
            if target not in pumps:
                raise ConfigError("Unknown Na/K pump target")
            patch = pumps[target][1]
            if patch.pump.metabolism.pool_id != data["fuel_pool_id"]:
                raise ConfigError("Na/K target must read its own finite pump fuel")
        elif kind == "channel":
            if target not in channels:
                raise ConfigError("Only existing shared channel populations are supported")
            patch = membranes[channels[target].membrane_id]
        else:
            if target not in junctions:
                raise ConfigError("Unknown resolved junction target")
            edge = junctions[target]
            if (
                data["sample_cell_id"] not in (edge.sender, edge.receiver)
                or data["sample_exterior_id"] is not None
            ):
                raise ConfigError(
                    "Junction rules need an actual endpoint cytosol and no inferred exterior"
                )
        if kind != "junction" and (data["sample_cell_id"], data["sample_exterior_id"]) != (
            patch.inside,
            patch.outside,
        ):
            raise ConfigError("Membrane consumers must read their actual inside/outside owners")
        conf = data["configuration"]
        if type(conf) is not dict or conf.get("name") != name:
            raise ConfigError("Require an explicit matching native factor name")
        if kind == "channel":
            if (
                conf.get("max Dm") != 0.0
                or conf.get("max conductivity") is not None
                or conf.get("apply to") != "all"
                or conf.get("init active", True) is not True
            ):
                raise ConfigError(
                    "Factor-only SIM channels require zero native Dm "
                    "and no conductance/profile/INIT override"
                )
            for value in conf.get("inhibitor max") or []:
                if value is not None:
                    fraction(value, "channel inhibitor floor")
        else:
            if (
                conf.get("target") != ("Na/K-ATPase" if kind == "nak" else "GJ")
                or conf.get("target ion") is not None
            ):
                raise ConfigError("Require the matching native Na/K/GJ factor target")
            fraction(conf.get("max effect"), "bounded factor maximum")
        rule = Rule(**data)
        try:
            t, _ = bind_rule(rule, model)
        except (ValueError, ArithmeticError) as error:
            raise ConfigError("Unsupported native factor expression: " + str(error)) from error
        inf = t.influencers
        if inf.mode.shape[0] > MAX_TERMS:
            raise ConfigError("Too many native influencer terms")
        selected = inf.mode > 0
        if np.any((inf.species >= len(model.species_ids)) & selected & (inf.owner != 0)):
            raise ConfigError("Fuel has no exterior sample")
        if kind == "junction" and np.any(selected & (inf.owner != 0)):
            raise ConfigError(
                "Native GJ environment-zone samples need an explicit mapping, unsupported here"
            )
        if np.any(t.voltage_coefficient != 0):
            raise ConfigError(
                "Voltage-dependent channel Km needs a coupled field/regulation closure"
            )
        result.append(rule)
    return tuple(result)


def parse(data):
    _fields(data, {"schema_version", "model", "experiment", "execution"}, "regulated @2 definition")
    raw = deepcopy(data)
    if (
        type(raw["model"]) is not dict
        or raw["model"].get("id") != MODEL_ID
        or "network_regulation" not in raw["model"]
    ):
        raise ConfigError("Require the explicit regulated @2 identity")
    block = raw["model"].pop("network_regulation")
    raw["model"]["id"] = parent.HCN_EXTRA_MODEL_ID
    if type(raw["execution"]) is not dict or "regulation_capacity" not in raw["execution"]:
        raise ConfigError("Declare regulation capacity")
    capacity = raw["execution"].pop("regulation_capacity")
    original = parent.parse(raw)
    rules = _rules(block, original.model)
    capacity = _integer(capacity, "regulation capacity", minimum=len(rules), maximum=MAX_RULES)
    spec = replace(
        original,
        model=SurfaceCalciumEnergyRegulatedV2Model(
            **vars(original.model), network_regulators=rules
        ),
        execution=Execution(**vars(original.execution), regulation_capacity=capacity),
    )
    from cells.models import surface_calcium_energy_regulated_v2

    try:
        surface_calcium_energy_regulated_v2.check_definition(spec)
    except (ValueError, ArithmeticError) as error:
        raise ConfigError("Invalid @2 live regulation: " + str(error)) from error
    return spec
