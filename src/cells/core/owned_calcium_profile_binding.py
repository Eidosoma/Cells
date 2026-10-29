"""Native coefficient declarations for two explicit complete calcium owners.

The inner direct record is a geometry/coefficient capability only. Complete
physical state, controls, free chemistry and fuel remain with each owner.
"""

from copy import deepcopy
from dataclasses import asdict, dataclass, fields

import numpy as np

from cells.core import surface_profile_interventions_spec as membrane
from cells.core import tissue_profile_composition_preparation as composed
from cells.core import tissue_profile_preparation as direct
from cells.core.specs import ConfigError, _fields, _integer, _number, digest
from cells.processes import betse_tissue_profiles as native
from cells.processes.electrochemistry import F, R

TIMING_POLICY = membrane.TIMING_POLICY
RESET_POLICY = membrane.RESET_POLICY
EXTRA_FIELDS = {"profile_preparation", "interventions", "phase", "timing_policy", "reset_policy"}
ARTIFACT_KIND = "cells.scheduled_owned_calcium_membranes@1"


@dataclass(frozen=True)
class NativeDeclarations:
    profile_preparation: dict
    interventions: tuple


def binding_view(model):
    return NativeDeclarations(
        {"provenance": model.profile_preparation["provenance"]["direct_parameter_preparation"]},
        model.interventions,
    )


def bindings(model, execution):
    return membrane.bindings(binding_view(model), execution)


def parse_owner(data, model_id, parent_id, parent_parse):
    _fields(
        data,
        {"schema_version", "model", "experiment", "execution"},
        "owned calcium profile definition",
    )
    if type(data["schema_version"]) is not int or data["schema_version"] != 1:
        raise ConfigError("Require owned calcium profile schema version 1")
    raw = deepcopy(data)
    m, x = raw["model"], raw["execution"]
    if not isinstance(m, dict) or m.get("id") != model_id or not EXTRA_FIELDS <= m.keys():
        raise ConfigError("Require the explicit owner-specific scheduled model")
    extra = {key: m.pop(key) for key in EXTRA_FIELDS}
    if (
        extra["phase"] not in ("INIT", "SIM")
        or extra["timing_policy"] != TIMING_POLICY
        or extra["reset_policy"] != RESET_POLICY
    ):
        raise ConfigError("Declare explicit fresh INIT/SIM RK-stage and native buffer policies")
    artifact = extra["profile_preparation"]
    _fields(artifact, {"definition", "provenance"}, "complete composed profile preparation")
    if (
        not isinstance(artifact["provenance"], dict)
        or artifact["provenance"].get("kind") != composed.KIND
    ):
        raise ConfigError(
            "Require a full qualified composed preparation, not a physical projection"
        )
    prepared = composed.replay(artifact["provenance"])
    if digest(prepared.definition) != digest(artifact["definition"]) or digest(
        prepared.provenance
    ) != digest(artifact["provenance"]):
        raise ConfigError("Composed profile definition disagrees with its full owner recipe")
    if prepared.definition["model"]["id"] != parent_id:
        raise ConfigError("Unsupported owner: this profile model requires exactly " + parent_id)
    m["id"] = parent_id
    if digest(m) != digest(prepared.definition["model"]):
        raise ConfigError(
            "All actual stores, ions, gates, pumps, fuel and owner declarations must be retained"
        )
    events = extra["interventions"]
    if type(events) is not list:
        raise ConfigError("Require ordered explicit membrane interventions")
    if (
        not isinstance(x, dict)
        or not {"intervention_capacity", "intervention_target_capacity"} <= x.keys()
    ):
        raise ConfigError("Declare both native intervention capacities")
    ec = _integer(
        x.pop("intervention_capacity"), "intervention capacity", minimum=len(events), maximum=4
    )
    tc = _integer(
        x.pop("intervention_target_capacity"),
        "intervention target capacity",
        minimum=0,
        maximum=65536,
    )
    ordinary = parent_parse(raw)
    declarations = artifact["provenance"]["direct_parameter_preparation"]["profile_declarations"]
    result = []
    for row in events:
        _fields(
            row, {f.name for f in fields(membrane.Event)}, "owned calcium membrane intervention"
        )
        if row["kind"] not in membrane.KINDS:
            raise ConfigError("Only Na/K/Cl/Ca plasma background events; no pressure/ECM")
        ion = row["kind"].split("_")[0]
        guarded = (
            row["kind"] in ("Cl_mem", "Ca_mem")
            and not declarations["ion_enabled"][native.IONS.index(ion)]
        )
        if not guarded and (
            ion not in ordinary.model.species_ids
            or ordinary.model.valence[ordinary.model.species_ids.index(ion)]
            != direct.SUPPORTED_IONS[ion]
        ):
            raise ConfigError("Scheduled ion needs its declared actual species and valence")
        on, off, change = (_number(row[k], k) for k in ("on_s", "off_s", "change_s"))
        if not 0 <= on < off <= ordinary.experiment.end_time or change <= 0:
            raise ConfigError("Require ordered phase-local window and positive ramp")
        for key in ("amplitude", "dynamic_factor"):
            if type(row[key]) not in (int, float) or not np.isfinite(row[key]):
                raise ConfigError("Require finite explicit signed event factors")
        if type(row["profiles"]) is not list or any(type(v) is not str for v in row["profiles"]):
            raise ConfigError("Declare ordered profile names including duplicates")
        if row["spatial"] is not None:
            _fields(row["spatial"], {"values", "axis"}, "explicit spatial samples")
            if row["spatial"]["axis"] not in ("occurrence", "membrane"):
                raise ConfigError("Declare native occurrence or membrane sample axis")
        result.append(
            membrane.Event(
                row["name"],
                row["kind"],
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
    return ordinary, extra, tuple(result), ec, tc


def augment(raw, spec, model_id):
    m = spec.model
    raw["model"].update(
        id=model_id,
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
    return direct._json(raw)


def native_parameters(spec):
    view, _, events, dynamic, baseline, coefficient = bindings(spec.model, spec.execution)
    size = spec.execution.membrane_capacity
    index = np.zeros(size, dtype=np.int64)
    thickness = np.ones(size)
    for i, row in enumerate(spec.model.membranes):
        index[i] = view.layout.membrane_ids.index(row.id)
        thickness[i] = view.thickness_m[row.id]
    species = spec.model.species_ids
    values = {"intervention_" + k: v for k, v in events.kernel._asdict().items()}
    values.update(
        intervention_dynamic_factor=dynamic,
        native_baseline_m2_s=baseline,
        native_event_coefficient_m2_s=coefficient,
        membrane_native_index=index,
        membrane_thickness_m=thickness,
        species_native_index=np.asarray(
            [native.IONS.index(s) if s in native.IONS else 0 for s in species], dtype=np.int64
        ),
        species_native_supported=np.asarray([s in native.IONS for s in species], bool),
        profile_sim=np.asarray(spec.model.phase == "SIM"),
        phase_end_s=np.asarray(spec.experiment.end_time),
        phase_clock_atol_s=np.asarray(
            64 * np.finfo(float).eps * max(spec.experiment.end_time, spec.execution.dt)
        ),
    )
    return values


def artifact(spec, to_dict, model_id, parent_id):
    _, bound, events, dynamic, _, _ = bindings(spec.model, spec.execution)
    record = direct._json(
        dict(
            kind=ARTIFACT_KIND,
            model_id=model_id,
            parent_model_id=parent_id,
            definition=to_dict(spec),
            profiles=native.binding_manifest(bound),
            interventions=native.intervention_manifest(events, bound),
            dynamic_factor=dynamic.tolist(),
            scope="background plasma D only; complete actual chemical/fuel owner retained",
        )
    )
    record["identity"] = digest(record)
    return record


def replay(record, parse, artifact, model_id, parent_id):
    try:
        value = deepcopy(record)
        seal = value.pop("identity")
        if (
            value["kind"] != ARTIFACT_KIND
            or value["model_id"] != model_id
            or value["parent_model_id"] != parent_id
            or digest(value) != seal
        ):
            raise ConfigError("Stale or wrong-owner scheduled calcium artifact")
        spec = parse(value["definition"])
        if digest(artifact(spec)) != digest(record):
            raise ConfigError("Owned calcium binding or complete recipe changed")
        return spec
    except (KeyError, TypeError, ValueError, ArithmeticError) as error:
        raise ConfigError(
            "Invalid complete owned-calcium profile artifact: " + str(error)
        ) from error


def check_checkpoint(spec, checkpoint):
    clock = np.asarray(checkpoint.state.phase_clock_s)
    atol = 64 * np.finfo(float).eps * max(spec.experiment.end_time, spec.execution.dt)
    if (
        clock.shape != (1,)
        or not np.isfinite(clock).all()
        or abs(clock[0] - checkpoint.time) > atol
    ):
        raise ConfigError("Owned calcium phase clock differs from accepted checkpoint time")


def background_loss_bound(layout, maximum_voltage_V):
    """GHK outflow per actual free owner, at the complete scheduled upper P.

    For either voltage sign, the Bernoulli transport factor is <=1+|zFV/RT|.
    Incoming flux cannot deplete an owner. Summing all outgoing membrane terms
    per species/owner therefore bounds fractional background loss without
    replacing actual free chemical calcium by total ionic/bound inventory.
    The owner supplies its admitted membrane voltage domain and actual layout.
    """
    p = layout
    inside = np.zeros_like(p.amount_reference)
    outside = np.zeros_like(p.extracellular_amount_reference)
    factor = 1 + np.abs(p.valence[:, 0]) * F * maximum_voltage_V / (R * p.temperature)
    for i in np.flatnonzero(p.membrane_active):
        rate = p.membrane_permeability[:, i] * p.membrane_area[i] / 1e-15 * factor
        a, b = p.membrane_cell[i], p.membrane_outside[i]
        inside[:, a] += rate / p.volume[a]
        outside[:, b] += rate / p.extracellular_volume[b]
    return max(float(np.max(inside, initial=0)), float(np.max(outside, initial=0)))
