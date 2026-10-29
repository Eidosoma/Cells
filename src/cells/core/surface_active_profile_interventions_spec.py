"""Scheduled native background membrane D on the complete active @12 parent."""

from copy import deepcopy
from dataclasses import asdict, dataclass, fields, replace

import numpy as np

from cells.core import surface_kinetic_spec as base
from cells.core import surface_profile_interventions_spec as native_spec
from cells.core import tissue_profile_preparation as profiles
from cells.core.specs import ConfigError, SimulationSpec, _fields, _integer, _number, digest
from cells.processes import betse_tissue_profiles as native

MODEL_ID = "resolved_active_membrane_profiles@1"
TIMING_POLICY = native_spec.TIMING_POLICY
RESET_POLICY = native_spec.RESET_POLICY
Event = native_spec.Event
bindings = native_spec.bindings


@dataclass(frozen=True)
class SurfaceActiveProfileInterventionModel(base.SurfaceHCNExtraModel):
    profile_preparation: dict
    interventions: tuple
    phase: str
    timing_policy: str
    reset_policy: str


@dataclass(frozen=True)
class Execution(base.Execution):
    intervention_capacity: int = 0
    intervention_target_capacity: int = 0


def active_spec(spec):
    return replace(
        spec,
        model=base.SurfaceHCNExtraModel(
            **{f.name: getattr(spec.model, f.name) for f in fields(base.SurfaceHCNExtraModel)}
        ),
        execution=base.Execution(
            **{f.name: getattr(spec.execution, f.name) for f in fields(base.Execution)}
        ),
    )


def to_dict(spec):
    raw = base.to_dict(active_spec(spec))
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


def parse(data):
    _fields(
        data, {"schema_version", "model", "experiment", "execution"}, "active profile definition"
    )
    if type(data["schema_version"]) is not int or data["schema_version"] != 1:
        raise ConfigError("Require active scheduled profile schema_version 1")
    raw = deepcopy(data)
    m, x = raw["model"], raw["execution"]
    extra = {"profile_preparation", "interventions", "phase", "timing_policy", "reset_policy"}
    if not isinstance(m, dict) or m.get("id") != MODEL_ID or not extra <= m.keys():
        raise ConfigError("Require the complete active scheduled membrane-profile model")
    additions = {key: m.pop(key) for key in extra}
    if (
        additions["phase"] not in ("INIT", "SIM")
        or additions["timing_policy"] != TIMING_POLICY
        or additions["reset_policy"] != RESET_POLICY
    ):
        raise ConfigError("Declare explicit fresh INIT/SIM RK-stage clock and zero-buffer policies")
    artifact = additions["profile_preparation"]
    _fields(artifact, {"definition", "provenance"}, "complete active static profile artifact")
    if artifact["provenance"].get("kind") != profiles.KIND:
        raise ConfigError("Require the qualified direct static profile preparation for active @12")
    prepared = profiles.replay(artifact["provenance"])
    if digest(prepared.definition) != digest(artifact["definition"]) or digest(
        prepared.provenance
    ) != digest(artifact["provenance"]):
        raise ConfigError("Active static profile artifact disagrees with its complete recipe")
    if prepared.definition["model"]["id"] != base.HCN_EXTRA_MODEL_ID:
        raise ConfigError(
            "Require complete active resolved_tissue@12; other owners/cuts/compositions refused"
        )
    m["id"] = base.HCN_EXTRA_MODEL_ID
    if digest(m) != digest(prepared.definition["model"]):
        raise ConfigError(
            "All physical owners, channels, gates and pumps must match the static artifact"
        )
    events = additions["interventions"]
    if type(events) is not list:
        raise ConfigError("Require an explicit ordered membrane intervention list")
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
    if type(ordinary.model) is not base.SurfaceHCNExtraModel:
        raise ConfigError("Require exactly the complete @12 active owner")
    declarations = artifact["provenance"]["profile_declarations"]
    parsed = []
    for row in events:
        _fields(row, {f.name for f in fields(Event)}, "active background membrane intervention")
        if row["kind"] not in native_spec.KINDS:
            raise ConfigError("Only Na/K/Cl/Ca membrane events; pressure/ECM refused")
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
            raise ConfigError(
                "Active scheduled ion needs its explicit physical species and valence"
            )
        on, off, change = (_number(row[k], k) for k in ("on_s", "off_s", "change_s"))
        if not 0 <= on < off <= ordinary.experiment.end_time or change <= 0:
            raise ConfigError("Require 0<=on<off<=phase horizon and positive transition time")
        for key in ("amplitude", "dynamic_factor"):
            if type(row[key]) not in (int, float) or not np.isfinite(row[key]):
                raise ConfigError("Require finite explicit signed intervention factors")
        if type(row["profiles"]) is not list or any(type(v) is not str for v in row["profiles"]):
            raise ConfigError("Declare ordered target profiles, retaining duplicate occurrences")
        if row["spatial"] is not None:
            _fields(row["spatial"], {"values", "axis"}, "explicit spatial samples")
            if row["spatial"]["axis"] not in ("occurrence", "membrane"):
                raise ConfigError("Membrane samples need explicit occurrence or membrane axes")
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
    result = SimulationSpec(
        SurfaceActiveProfileInterventionModel(
            **vars(ordinary.model),
            profile_preparation=deepcopy(artifact),
            interventions=tuple(parsed),
            phase=additions["phase"],
            timing_policy=TIMING_POLICY,
            reset_policy=RESET_POLICY,
        ),
        ordinary.experiment,
        Execution(
            **vars(ordinary.execution), intervention_capacity=ec, intervention_target_capacity=tc
        ),
    )
    try:
        bindings(result.model, result.execution)
        from cells.models.surface_active_profile_interventions import check_definition

        check_definition(result)
    except (ValueError, TypeError, ArithmeticError) as error:
        raise ConfigError("Invalid active scheduled membrane definition: " + str(error)) from error
    return result


def artifact(spec):
    _, bound, events, dynamic, _, _ = bindings(spec.model, spec.execution)
    record = profiles._json(
        dict(
            kind="cells.scheduled_active_membrane_profiles@1",
            definition=to_dict(spec),
            profiles=native.binding_manifest(bound),
            interventions=native.intervention_manifest(events, bound),
            dynamic_factor=dynamic.tolist(),
            kinetic_scope=(
                "native scheduling modifies background membrane D only; "
                "actual @12 gates/pumps retained"
            ),
        )
    )
    record["identity"] = digest(record)
    return record


def replay(record):
    try:
        row = deepcopy(record)
        seal = row.pop("identity")
        if row["kind"] != "cells.scheduled_active_membrane_profiles@1" or digest(row) != seal:
            raise ConfigError("Stale active scheduled membrane artifact")
        spec = parse(row["definition"])
        if digest(artifact(spec)) != digest(record):
            raise ConfigError("Active scheduled membrane binding or physical owner recipe changed")
        return spec
    except (KeyError, TypeError, ValueError, ArithmeticError) as error:
        raise ConfigError(
            "Invalid complete active scheduled membrane artifact: " + str(error)
        ) from error
