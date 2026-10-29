"""Native coefficient capabilities on three explicit complete full56 owners."""

from copy import deepcopy
from dataclasses import asdict, dataclass, fields
from types import SimpleNamespace

import numpy as np

from cells.core import environment_barrier_composition_preparation as composed
from cells.core import environment_barrier_interventions_spec as native
from cells.core.multispecies_spec import identifier
from cells.core.specs import ConfigError, _fields, _integer, _number, digest
from cells.processes.betse_tissue_profiles import IONS

TIMING_POLICY = native.TIMING_POLICY
Event = native.Event
EXTRA = {"barrier_preparation", "intervention", "phase", "timing_policy"}
KIND = "cells.scheduled_complete_extracellular_barriers@1"


@dataclass(frozen=True)
class CoefficientDeclarations:
    cells: tuple
    membranes: tuple
    species_ids: tuple
    intervention: object
    barrier_preparation: dict


def bindings(model, execution):
    # This view declares geometry/coefficient inputs only; it is never a
    # physical state, parent model, field or flux source.
    view = CoefficientDeclarations(
        model.cells,
        model.membranes,
        model.species_ids,
        model.intervention,
        {"provenance": model.barrier_preparation["provenance"]["direct_parameter_preparation"]},
    )
    return native.bindings(view, execution)


def parse_owner(data, model_id, parent_id, parent_parse):
    _fields(
        data, {"schema_version", "model", "experiment", "execution"}, "complete barrier definition"
    )
    if type(data["schema_version"]) is not int or data["schema_version"] != 1:
        raise ConfigError("Require complete barrier schema_version 1")
    raw = deepcopy(data)
    model, execution = raw["model"], raw["execution"]
    if not isinstance(model, dict) or model.get("id") != model_id or not EXTRA <= model.keys():
        raise ConfigError("Require the explicit complete-owner barrier model")
    extra = {key: model.pop(key) for key in EXTRA}
    if extra["phase"] not in ("INIT", "SIM") or extra["timing_policy"] != TIMING_POLICY:
        raise ConfigError("Declare the supported fresh INIT/SIM stage-clock policy")
    artifact = _fields(
        extra["barrier_preparation"],
        {"definition", "provenance"},
        "full composed barrier preparation",
    )
    if (
        not isinstance(artifact["provenance"], dict)
        or artifact["provenance"].get("kind") != composed.KIND
    ):
        raise ConfigError("Require the complete composed barrier preparation, not a passive owner")
    checked = composed.replay(artifact["provenance"])
    if digest(checked.definition) != digest(artifact["definition"]) or digest(
        checked.provenance
    ) != digest(artifact["provenance"]):
        raise ConfigError("Composed barrier artifact disagrees with its full physical recipe")
    if checked.definition["model"]["id"] != parent_id:
        raise ConfigError("This barrier model requires exactly " + parent_id)
    model["id"] = parent_id
    if digest(model) != digest(checked.definition["model"]):
        raise ConfigError(
            "Every physical owner, store, channel and pool must match the prepared parent"
        )
    if not isinstance(execution, dict) or "barrier_target_capacity" not in execution:
        raise ConfigError("Declare the native target-occurrence capacity")
    capacity = _integer(
        execution.pop("barrier_target_capacity"),
        "barrier target capacity",
        minimum=0,
        maximum=65536,
    )
    ordinary = parent_parse(raw)
    if any(s not in IONS for s in ordinary.model.species_ids):
        raise ConfigError("Native ECM needs explicitly named Na/K/Cl/Ca/M/P ionic species")
    event = extra["intervention"]
    if event is not None:
        _fields(event, {f.name for f in fields(Event)}, "single complete-owner ECM intervention")
        name = identifier(event["name"])
        sites = event["site_ids"]
        owned = {p.id for p in ordinary.model.extracellular}
        if (
            type(sites) is not list
            or not sites
            or any(type(s) is not str or s not in owned for s in sites)
        ):
            raise ConfigError("Declare ordered owned ECM sites; duplicate occurrences are retained")
        on, off, change, amplitude = (
            _number(event[k], k) for k in ("on_s", "off_s", "change_s", "amplitude")
        )
        if (
            not 0 <= on < off <= ordinary.experiment.end_time
            or change <= 0
            or not 0 <= amplitude <= 1
        ):
            raise ConfigError(
                "Require ordered phase-local ECM window, positive ramp and amplitude in [0,1]"
            )
        event = Event(name, tuple(sites), on, off, change, amplitude)
    return ordinary, extra, event, capacity


def augment(raw, spec, model_id):
    model = spec.model
    raw["model"].update(
        id=model_id,
        barrier_preparation=deepcopy(model.barrier_preparation),
        intervention=None if model.intervention is None else asdict(model.intervention),
        phase=model.phase,
        timing_policy=TIMING_POLICY,
    )
    raw["execution"]["barrier_target_capacity"] = spec.execution.barrier_target_capacity
    return composed.direct._json(raw)


def native_parameters(spec, parent):
    from cells.models import environment_barrier_interventions as coefficients

    event, site, modifiers, free, weight = bindings(spec.model, spec.execution)
    sites = spec.model.barrier_preparation["provenance"]["request"]["grid"]["site_ids"]
    size = spec.execution.face_capacity
    sender, receiver = np.zeros(size, dtype=np.int64), np.zeros(size, dtype=np.int64)
    measure = np.zeros(size)
    for i, face in enumerate(spec.model.faces):
        sender[i], receiver[i] = sites.index(face.sender), sites.index(face.receiver)
        measure[i] = face.area_m2 / face.length_m
    values = {"barrier_" + k: v for k, v in event._asdict().items()}
    values.update(
        barrier_base_m2_s=site,
        barrier_modulator=modifiers,
        barrier_free_m2_s=free,
        barrier_weight_base=weight,
        barrier_species_index=np.asarray([IONS.index(s) for s in spec.model.species_ids]),
        barrier_face_sender=sender,
        barrier_face_receiver=receiver,
        barrier_face_measure_m=measure,
        barrier_union_factor=parent.face_factor,
        barrier_sim=np.asarray(spec.model.phase == "SIM"),
        phase_end_s=np.asarray(spec.experiment.end_time),
        phase_clock_atol_s=np.asarray(
            64 * np.finfo(float).eps * max(spec.experiment.end_time, spec.execution.dt)
        ),
    )
    view = SimpleNamespace(**(parent._asdict() | values))
    upper = site.copy()
    intervention = spec.model.intervention
    if spec.model.phase == "SIM" and intervention is not None and intervention.amplitude > 0:
        for name in intervention.site_ids:
            i = sites.index(name)
            upper[:, i] = np.maximum(upper[:, i], free)
    effective = (upper * modifiers)[values["barrier_species_index"]]
    union = coefficients.harmonic_faces(effective, view, xp=np) * measure
    values["barrier_union_factor"] = np.maximum(union, parent.face_factor)
    return values


def check_ramp_steps(spec, steps):
    event = spec.model.intervention
    if event is None or spec.model.phase == "INIT":
        return
    ceiling = event.change_s / 8
    if spec.execution.dt > ceiling * (1 + 16 * np.finfo(float).eps):
        raise ConfigError("Complete-owner ECM execution.dt must be <= transition time/8")
    allowance = max(2 * np.spacing(spec.experiment.end_time), 16 * np.finfo(float).eps * ceiling)
    if np.max(steps, initial=0) > ceiling + allowance:
        raise ConfigError("Complete-owner ECM RK4 steps must resolve transition time/8")


def artifact(spec, to_dict, model_id, parent_id):
    record = dict(
        kind=KIND,
        model_id=model_id,
        parent_model_id=parent_id,
        definition=to_dict(spec),
        static_preparation_identity=spec.model.barrier_preparation["provenance"]["identity"],
        scope=(
            "stage extracellular coefficients only; "
            "exact complete parent physics and original ledgers"
        ),
    )
    record["identity"] = digest(record)
    return record


def replay(record, parse, artifact, model_id, parent_id):
    try:
        raw = deepcopy(record)
        seal = raw.pop("identity")
        if (
            raw["kind"] != KIND
            or raw["model_id"] != model_id
            or raw["parent_model_id"] != parent_id
            or digest(raw) != seal
        ):
            raise ConfigError("Stale or wrong complete-owner scheduled barrier artifact")
        spec = parse(raw["definition"])
        if digest(artifact(spec)) != digest(record):
            raise ConfigError("Complete barrier owner or coefficient recipe changed")
        return spec
    except (KeyError, TypeError, ValueError, ArithmeticError) as error:
        raise ConfigError(
            "Invalid complete-owner scheduled barrier artifact: " + str(error)
        ) from error
