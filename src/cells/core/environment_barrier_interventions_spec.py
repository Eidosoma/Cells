"""A single native ECM-opening pulse on explicitly prepared passive tissue."""

from copy import deepcopy
from dataclasses import asdict, dataclass, fields, replace

import numpy as np

from cells.core import environment_barrier_preparation as preparation
from cells.core import surface_tissue_spec as base
from cells.core.multispecies_spec import identifier
from cells.core.specs import (
    ConfigError,
    SimulationSpec,
    SpatialExtracellularExecutionSpec,
    _fields,
    _integer,
    _number,
    digest,
)
from cells.processes import betse_tissue_profiles as native

MODEL_ID = "resolved_extracellular_barriers@1"
TIMING_POLICY = "phase_clock_rk_stage_native_logistic@1"


@dataclass(frozen=True)
class Event:
    name: str
    site_ids: tuple[str, ...]
    on_s: float
    off_s: float
    change_s: float
    amplitude: float


@dataclass(frozen=True)
class EnvironmentBarrierModel(base.SurfaceTissueModel):
    barrier_preparation: dict
    intervention: Event | None
    phase: str
    timing_policy: str


@dataclass(frozen=True)
class Execution(SpatialExtracellularExecutionSpec):
    barrier_target_capacity: int = 0


def base_spec(spec):
    return replace(
        spec,
        model=base.SurfaceTissueModel(
            **{f.name: getattr(spec.model, f.name) for f in fields(base.SurfaceTissueModel)}
        ),
        execution=SpatialExtracellularExecutionSpec(
            **{
                f.name: getattr(spec.execution, f.name)
                for f in fields(SpatialExtracellularExecutionSpec)
            }
        ),
    )


def to_dict(spec):
    if type(spec.model) is not EnvironmentBarrierModel or type(spec.execution) is not Execution:
        raise ConfigError("Require exact scheduled extracellular-barrier model/execution types")
    raw = base.to_dict(base_spec(spec))
    m = spec.model
    raw["model"].update(
        id=MODEL_ID,
        barrier_preparation=deepcopy(m.barrier_preparation),
        intervention=None if m.intervention is None else asdict(m.intervention),
        phase=m.phase,
        timing_policy=m.timing_policy,
    )
    raw["execution"]["barrier_target_capacity"] = spec.execution.barrier_target_capacity
    return preparation._json(raw)


def bindings(model, execution):
    """Bind the already qualified native event kernel to explicit ordered sites."""
    provenance = model.barrier_preparation["provenance"]
    request = provenance["request"]
    sites = tuple(request["grid"]["site_ids"])
    event = model.intervention
    count = 0 if event is None else len(event.site_ids)
    capacity = execution.barrier_target_capacity
    if count > capacity:
        raise ConfigError("Barrier target capacity must include duplicate occurrences")
    target = np.zeros((1, capacity), dtype=np.int64)
    selected = np.zeros((1, capacity), dtype=bool)
    if event is not None:
        target[0, :count] = [sites.index(name) for name in event.site_ids]
        selected[0, :count] = True
    kernel = native.InterventionKernel(
        np.ones(len(model.cells), dtype=bool),
        np.ones(len(model.membranes), dtype=bool),
        np.ones(len(sites), dtype=bool),
        np.asarray([0 if event is None else native.ECM_EVENT], dtype=np.int64),
        np.zeros(1, dtype=np.int64),
        np.asarray([event is not None], dtype=bool),
        target,
        selected,
        np.asarray([0.0 if event is None else event.on_s]),
        np.asarray([0.0 if event is None else event.off_s]),
        np.asarray([1.0 if event is None else event.change_s]),
        np.asarray([0.0 if event is None else event.amplitude]),
        selected.astype(float),
        np.zeros(6),
    )
    base_values = np.zeros((6, len(sites)))
    modifiers = np.ones_like(base_values)
    free = np.zeros(6)
    for species in model.species_ids:
        i = native.IONS.index(species)
        base_values[i] = [provenance["coefficients"]["site_base_m2_s"][species][s] for s in sites]
        modifiers[i] = [request["ion_modulators"][species][s] for s in sites]
        free[i] = request["free_diffusion_m2_s"][species]
    weight = np.asarray([provenance["sodium_weight"][s] for s in sites])
    return kernel, base_values, modifiers, free, weight


def parse(data):
    _fields(data, {"schema_version", "model", "experiment", "execution"}, "barrier definition")
    if type(data["schema_version"]) is not int or data["schema_version"] != 1:
        raise ConfigError("Require barrier definition schema_version 1")
    raw = deepcopy(data)
    m, x = raw["model"], raw["execution"]
    extra = {"barrier_preparation", "intervention", "phase", "timing_policy"}
    if not isinstance(m, dict) or m.get("id") != MODEL_ID or not extra <= m.keys():
        raise ConfigError("Require the explicit extracellular-barrier model")
    additions = {key: m.pop(key) for key in extra}
    if additions["phase"] not in ("INIT", "SIM") or additions["timing_policy"] != TIMING_POLICY:
        raise ConfigError("Declare INIT/SIM and the supported RK-stage phase-clock policy")
    artifact = _fields(
        additions["barrier_preparation"],
        {"definition", "provenance"},
        "complete barrier preparation",
    )
    prepared = preparation.replay(artifact["provenance"])
    if digest(prepared.definition) != digest(artifact["definition"]) or digest(
        prepared.provenance
    ) != digest(artifact["provenance"]):
        raise ConfigError("Barrier preparation differs from its complete recipe")
    m["id"] = base.MODEL_ID
    if digest(m) != digest(prepared.definition["model"]):
        raise ConfigError("Physical parent must match the prepared barrier model exactly")
    if not isinstance(x, dict) or "barrier_target_capacity" not in x:
        raise ConfigError("Declare barrier target capacity explicitly")
    capacity = _integer(
        x.pop("barrier_target_capacity"), "barrier target capacity", minimum=0, maximum=65536
    )
    ordinary = base.parse(raw)
    if any(s not in native.IONS for s in ordinary.model.species_ids):
        raise ConfigError("Scheduled native ECM requires the named Na/K/Cl/Ca/M/P species")
    row, event = additions["intervention"], None
    if row is not None:
        _fields(row, {f.name for f in fields(Event)}, "single ECM intervention")
        name = identifier(row["name"])
        sites = row["site_ids"]
        owned = {p.id for p in ordinary.model.extracellular}
        if (
            type(sites) is not list
            or not sites
            or any(type(s) is not str or s not in owned for s in sites)
        ):
            raise ConfigError("Declare nonempty ordered owned ECM sites; duplicates are retained")
        on, off, change, amplitude = (
            _number(row[key], key) for key in ("on_s", "off_s", "change_s", "amplitude")
        )
        if not 0 <= on < off <= ordinary.experiment.end_time or change <= 0:
            raise ConfigError("Require 0<=on<off<=horizon and positive transition time")
        if not 0 <= amplitude <= 1:
            raise ConfigError("Physical ECM opening amplitude must be in [0,1]; no clipping")
        event = Event(name, tuple(sites), on, off, change, amplitude)
    model = EnvironmentBarrierModel(
        **vars(ordinary.model),
        barrier_preparation=deepcopy(artifact),
        intervention=event,
        phase=additions["phase"],
        timing_policy=TIMING_POLICY,
    )
    execution = Execution(**vars(ordinary.execution), barrier_target_capacity=capacity)
    result = SimulationSpec(model, ordinary.experiment, execution)
    try:
        bindings(model, execution)
        from cells.models.environment_barrier_interventions import check_definition

        check_definition(result)
    except (ValueError, TypeError, ArithmeticError) as error:
        raise ConfigError("Invalid scheduled ECM barrier definition: " + str(error)) from error
    return result
