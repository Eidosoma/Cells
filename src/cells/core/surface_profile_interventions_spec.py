"""Explicit phase-local scheduled membrane profiles on ordinary passive tissue."""

from copy import deepcopy
from dataclasses import asdict, dataclass, fields, replace

import numpy as np

from cells.core import geometry_profile_preparation as geometry_profiles
from cells.core import surface_tissue_spec as base
from cells.core import tissue_profile_preparation as profiles
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

MODEL_ID = "resolved_membrane_profiles@1"
TIMING_POLICY = "phase_clock_rk_stage_native_logistic@1"
RESET_POLICY = "fresh_phase_zero_scheduled_sim_only@1"
KINDS = ("Na_mem", "K_mem", "Cl_mem", "Ca_mem")


@dataclass(frozen=True)
class Event:
    name: str
    kind: str
    profiles: tuple
    on_s: float
    off_s: float
    change_s: float
    amplitude: float
    spatial: object
    source_function: str
    dynamic_factor: float


@dataclass(frozen=True)
class SurfaceProfileInterventionModel(base.SurfaceTissueModel):
    profile_preparation: dict
    interventions: tuple
    phase: str
    timing_policy: str
    reset_policy: str


@dataclass(frozen=True)
class Execution(SpatialExtracellularExecutionSpec):
    intervention_capacity: int = 0
    intervention_target_capacity: int = 0


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
    raw = base.to_dict(base_spec(spec))
    m = spec.model
    raw["model"].update(
        id=MODEL_ID,
        profile_preparation=deepcopy(m.profile_preparation),
        interventions=[asdict(e) for e in m.interventions],
        phase=m.phase,
        timing_policy=m.timing_policy,
        reset_policy=m.reset_policy,
    )
    raw["execution"].update(
        intervention_capacity=spec.execution.intervention_capacity,
        intervention_target_capacity=spec.execution.intervention_target_capacity,
    )
    return profiles._json(raw)


def bindings(model, execution):
    p = model.profile_preparation["provenance"]
    if p["kind"] == geometry_profiles.KIND:
        p = p["profile_preparation"]
    raw = p["geometry"]
    g = deepcopy(raw)
    layout = g.pop("layout")
    view = profiles.Geometry(native.Layout(**layout), **g)
    rows = p["profile_declarations"]
    bound = native.compile_profiles(
        view.layout,
        profiles._decode_profile(rows["default"]),
        [profiles._decode_profile(r) for r in rows["profiles"]],
        ion_enabled=rows["ion_enabled"],
        enabled=rows["enabled"],
        is_ecm=rows["is_ecm"],
    )
    events = []
    factors = {}
    for e in model.interventions:
        spatial = None if e.spatial is None else native.Sampled(**e.spatial)
        events.append(
            native.Intervention(
                e.name,
                e.kind,
                e.profiles,
                e.on_s,
                e.off_s,
                e.change_s,
                e.amplitude,
                spatial,
                e.source_function,
            )
        )
        factors[e.name] = e.dynamic_factor
    interventions = native.compile_interventions(
        bound,
        events,
        event_capacity=execution.intervention_capacity,
        target_capacity=execution.intervention_target_capacity,
    )
    dynamic = np.asarray(
        [factors[name] for name in interventions.names]
        + [1.0] * (execution.intervention_capacity - len(events))
    )
    baseline = np.asarray(p["diffusivity_m2_s"], float)
    coefficient = np.zeros_like(baseline)
    k = interventions.kernel
    # This is a conservative support/bound calculation, never a physical
    # substitute for the unchanged native event kernel at actual stage times.
    for row in range(len(interventions.names)):
        if k.guard[row]:
            for slot in range(k.targets.shape[-1]):
                if k.selected[row, slot]:
                    coefficient[k.ion[row], k.targets[row, slot]] = (
                        k.default_diffusivity_m2_s[k.ion[row]]
                        * dynamic[row]
                        * k.amplitude[row]
                        * k.spatial[row, slot]
                    )
    if not np.isfinite(coefficient).all() or np.any(baseline + np.minimum(coefficient, 0) < 0):
        raise ConfigError(
            "Scheduled membrane event can produce negative physical diffusion; no clipping"
        )
    return view, bound, interventions, dynamic, baseline, coefficient


def parse(data):
    _fields(
        data, {"schema_version", "model", "experiment", "execution"}, "scheduled profile definition"
    )
    if type(data["schema_version"]) is not int or data["schema_version"] != 1:
        raise ConfigError("Require scheduled profile schema_version 1")
    raw = deepcopy(data)
    m = raw["model"]
    x = raw["execution"]
    extra = {"profile_preparation", "interventions", "phase", "timing_policy", "reset_policy"}
    if m.get("id") != MODEL_ID or not extra <= m.keys():
        raise ConfigError("Require the explicit scheduled passive membrane-profile model")
    additions = {key: m.pop(key) for key in extra}
    if (
        additions["phase"] not in ("INIT", "SIM")
        or additions["timing_policy"] != TIMING_POLICY
        or additions["reset_policy"] != RESET_POLICY
    ):
        raise ConfigError(
            "Declare the supported INIT/SIM, RK-stage timing and fresh zero-buffer policies"
        )
    artifact = additions["profile_preparation"]
    _fields(artifact, {"definition", "provenance"}, "complete static profile artifact")
    kind = artifact["provenance"].get("kind")
    if kind == profiles.KIND:
        prepared = profiles.replay(artifact["provenance"])
    elif kind == geometry_profiles.KIND:
        prepared = geometry_profiles.replay(artifact["provenance"])
    else:
        raise ConfigError("Require a qualified direct or initial-geometry static profile artifact")
    if digest(prepared.definition) != digest(artifact["definition"]) or digest(
        prepared.provenance
    ) != digest(artifact["provenance"]):
        raise ConfigError("Static profile artifact disagrees with its full recipe")
    if prepared.definition["model"]["id"] != "resolved_tissue@1":
        raise ConfigError(
            "Only ordinary passive profile artifacts are supported; no cuts or remaps"
        )
    m["id"] = base.MODEL_ID
    if digest(m) != digest(prepared.definition["model"]):
        raise ConfigError(
            "Physical parent must exactly match its prepared passive profile artifact"
        )
    events = additions["interventions"]
    if type(events) is not list:
        raise ConfigError("Require an explicit ordered intervention list")
    ec = _integer(
        x.pop("intervention_capacity"), "intervention capacity", minimum=len(events), maximum=4
    )
    tc = _integer(
        x.pop("intervention_target_capacity"),
        "intervention target capacity",
        minimum=0,
        maximum=65536,
    )
    ordinary = base.parse(raw)
    parsed = []
    direct = artifact["provenance"]
    if direct["kind"] == geometry_profiles.KIND:
        direct = direct["profile_preparation"]
    declarations = direct["profile_declarations"]
    for row in events:
        _fields(row, {f.name for f in fields(Event)}, "membrane intervention")
        if row["kind"] not in KINDS:
            raise ConfigError("Only Na/K/Cl/Ca membrane events; pressure and ECM refused")
        kind = row["kind"]
        ion = kind.split("_")[0]
        guarded = (
            kind in ("Cl_mem", "Ca_mem") and not declarations["ion_enabled"][native.IONS.index(ion)]
        )
        if not guarded and (
            ion not in ordinary.model.species_ids
            or ordinary.model.valence[ordinary.model.species_ids.index(ion)]
            != profiles.SUPPORTED_IONS[ion]
        ):
            raise ConfigError("Active scheduled ion needs its explicit physical species/valence")
        on, off, change = (_number(row[k], k) for k in ("on_s", "off_s", "change_s"))
        if not 0 <= on < off <= ordinary.experiment.end_time or change <= 0:
            raise ConfigError("Require 0<=on<off<=phase horizon and positive transition time")
        for key in ("amplitude", "dynamic_factor"):
            value = row[key]
            if type(value) not in (int, float) or not np.isfinite(value):
                raise ConfigError("Require finite explicit signed event factors")
        if type(row["profiles"]) is not list or any(type(v) is not str for v in row["profiles"]):
            raise ConfigError(
                "Declare ordered target profile names, including duplicate occurrences"
            )
        if row["spatial"] is not None:
            _fields(row["spatial"], {"values", "axis"}, "explicit spatial samples")
            if row["spatial"]["axis"] not in ("occurrence", "membrane"):
                raise ConfigError("Spatial membrane events need occurrence or membrane samples")
        parsed.append(
            Event(
                row["name"],
                kind,
                tuple(row["profiles"]),
                on,
                off,
                change,
                row["amplitude"],
                deepcopy(row["spatial"]),
                row["source_function"],
                row["dynamic_factor"],
            )
        )
    model = SurfaceProfileInterventionModel(
        **vars(ordinary.model),
        profile_preparation=deepcopy(artifact),
        interventions=tuple(parsed),
        phase=additions["phase"],
        timing_policy=TIMING_POLICY,
        reset_policy=RESET_POLICY,
    )
    execution = Execution(
        **vars(ordinary.execution), intervention_capacity=ec, intervention_target_capacity=tc
    )
    result = SimulationSpec(model, ordinary.experiment, execution)
    try:
        bindings(model, execution)
        from cells.models.surface_profile_interventions import check_definition

        check_definition(result)
    except (ValueError, TypeError, ArithmeticError) as error:
        raise ConfigError("Invalid scheduled passive profile definition: " + str(error)) from error
    return result


def artifact(spec):
    """Complete portable definition plus compiled identity metadata for replay."""
    _, bound, events, dynamic, _, _ = bindings(spec.model, spec.execution)
    record = dict(
        kind="cells.scheduled_membrane_profiles@1",
        definition=to_dict(spec),
        profiles=native.binding_manifest(bound),
        interventions=native.intervention_manifest(events, bound),
        dynamic_factor=dynamic.tolist(),
    )
    record = profiles._json(record)
    record["identity"] = digest(record)
    return record


def replay(record):
    try:
        row = deepcopy(record)
        identity = row.pop("identity")
        if row["kind"] != "cells.scheduled_membrane_profiles@1" or digest(row) != identity:
            raise ConfigError("Stale scheduled membrane profile artifact")
        spec = parse(row["definition"])
        if digest(artifact(spec)) != digest(record):
            raise ConfigError("Scheduled membrane profile recipe changed")
        return spec
    except (KeyError, TypeError, ValueError, ArithmeticError) as error:
        raise ConfigError(
            "Invalid complete scheduled membrane profile artifact: " + str(error)
        ) from error
