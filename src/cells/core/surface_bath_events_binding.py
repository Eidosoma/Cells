"""Explicit ideal-reservoir controllers using the pinned native bath setters.

The literal native capability is compiled separately for each declared bath.
It declares species/ownership only; no synthetic spatial grid or transport
state is constructed. Original physical anchors remain immutable.
"""

import math
from copy import deepcopy
from dataclasses import asdict, dataclass, fields

import numpy as np

from cells.core.specs import ConfigError, _fields, _number, digest
from cells.processes.betse_environment_transport import BathEvent, compile_baths

TIMING_POLICY = "phase_clock_rk_stage_native_logistic@1"
CONTROLLER_POLICY = "explicit_ideal_reservoir_dose_voltage_compensation_work@1"
BASELINE_POLICY = "each_declared_reservoir_reference_concentration@1"
KIND = "cells.scheduled_surface_bath_events@1"
PREPARATION_KIND = "cells.surface_bath_initial_controller_operation@1"
ORDER = ("K_env", "Cl_env", "Na_env")
EXTRA = {
    "bath_events",
    "bath_site_ids",
    "enabled_Cl",
    "phase",
    "timing_policy",
    "controller_policy",
    "baseline_policy",
}
EXTRA_LAYOUT = (
    "bath_amount_coefficient_fmol",
    "bath_on_s",
    "bath_off_s",
    "bath_change_s",
    "bath_target",
    "bath_event_active",
    "phase_end_s",
    "phase_clock_atol_s",
)


@dataclass(frozen=True)
class BathOwners:
    identity: str
    species_ids: tuple
    site_ids: tuple


def _signed(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError("Bath amplitude must be a finite signed number")
    try:
        value = float(value)
    except OverflowError as error:
        raise ConfigError("Bath amplitude exceeds float64") from error
    if not math.isfinite(value):
        raise ConfigError("Bath amplitude must be finite")
    return value


def parse_owner(data, model_id, parent_id, parent_parse):
    _fields(data, {"schema_version", "model", "experiment", "execution"}, "bath definition")
    if type(data["schema_version"]) is not int or data["schema_version"] != 1:
        raise ConfigError("Require bath schema_version 1")
    raw = deepcopy(data)
    model = raw["model"]
    if not isinstance(model, dict) or model.get("id") != model_id or not EXTRA <= model.keys():
        raise ConfigError("Require the explicit passive or complete ionic bath model")
    extra = {key: model.pop(key) for key in EXTRA}
    if (
        extra["phase"] not in ("INIT", "SIM")
        or extra["timing_policy"] != TIMING_POLICY
        or extra["controller_policy"] != CONTROLLER_POLICY
        or extra["baseline_policy"] != BASELINE_POLICY
    ):
        raise ConfigError("Declare the supported bath clock, baseline and external controllers")
    if type(extra["enabled_Cl"]) is not bool:
        raise ConfigError("The native Cl guard must be an explicit boolean")
    model["id"] = parent_id
    ordinary = parent_parse(raw)
    sites = extra["bath_site_ids"]
    owned = {v.id: v for v in ordinary.model.extracellular}
    if (
        type(sites) is not list
        or any(type(v) is not str or v not in owned for v in sites)
        or len(sites) != len(set(sites))
        or any(not owned[v].reservoir for v in sites)
    ):
        raise ConfigError("Bath targets must be unique declared ideal reservoirs")
    events = extra["bath_events"]
    if type(events) is not list or len(events) > 3:
        raise ConfigError("Declare at most one event of each native K/Cl/Na kind")
    parsed = []
    for event in events:
        _fields(event, {f.name for f in fields(BathEvent)}, "native bath event")
        if event["kind"] not in ORDER:
            raise ConfigError("Unsupported bath kind")
        on, off, change = (_number(event[k], k) for k in ("on_s", "off_s", "change_s"))
        if not 0 <= on < off <= ordinary.experiment.end_time or change <= 0:
            raise ConfigError("Require an ordered phase-local bath window and positive transition")
        parsed.append(BathEvent(event["kind"], on, off, change, _signed(event["amplitude"])))
    kinds = [v.kind for v in parsed]
    if kinds != [k for k in ORDER if k in kinds]:
        raise ConfigError("Declare unique native bath events in K, Cl, Na overwrite order")
    if parsed and not sites:
        raise ConfigError("A bath program requires explicit reservoir targets")
    extra.update(bath_events=tuple(parsed), bath_site_ids=tuple(sites))
    return ordinary, extra


def augment(raw, spec, model_id):
    raw["model"].update(
        id=model_id,
        bath_events=[asdict(v) for v in spec.model.bath_events],
        bath_site_ids=list(spec.model.bath_site_ids),
        enabled_Cl=spec.model.enabled_Cl,
        phase=spec.model.phase,
        timing_policy=TIMING_POLICY,
        controller_policy=CONTROLLER_POLICY,
        baseline_policy=BASELINE_POLICY,
    )
    return raw


def native_parameters(spec, parent):
    """Seal literal source capabilities; retain only last-writer coefficients.

    Each target's own original concentrations supply its native baseline. This
    explicit Cells replication also permits distinct declared bath baselines;
    the native single global baseline is its uniform special case.
    """
    model = spec.model
    ids = model.species_ids
    sites = tuple(v.id for v in model.extracellular)
    coefficients = np.zeros((3, *parent.extracellular_amount_reference.shape))
    target = np.zeros_like(parent.reservoir)
    bindings = []
    for name in model.bath_site_ids:
        j = sites.index(name)
        target[j] = True
        baseline = parent.extracellular_amount_reference[:, j] / parent.extracellular_volume[j]
        owner = BathOwners(digest(dict(species=ids, site=name)), ids, (name,))
        bound = compile_baths(
            owner, model.bath_events, baseline, is_ecm=True, enabled_Cl=model.enabled_Cl
        )
        bindings.append(bound.identity)
        for event in model.bath_events:
            if event.kind == "Cl_env" and not model.enabled_Cl:
                continue
            ion = event.kind.split("_")[0]
            other = "Na" if ion == "Cl" else "M"
            for species in (ion, other):
                expected = 1 if species in ("Na", "K") else -1
                if model.valence[ids.index(species)] != expected:
                    raise ConfigError("Native bath counterions require Na/K +1 and Cl/M -1")
            rows = [ids.index(ion), ids.index(other)]
            coefficient = (
                event.amplitude * baseline[ids.index(ion)] * parent.extracellular_volume[j]
            )
            coefficients[:, rows, j] = 0.0
            coefficients[ORDER.index(event.kind), rows, j] = coefficient
    lower = parent.extracellular_amount_reference + np.sum(np.minimum(coefficients, 0), axis=0)
    upper = parent.extracellular_amount_reference + np.sum(np.maximum(coefficients, 0), axis=0)
    if (
        not np.isfinite(coefficients).all()
        or not np.isfinite(upper).all()
        or np.any(lower[:, parent.outside_active] <= 0)
    ):
        raise ConfigError("Bath program must remain strictly positive for every pulse in [0,1]")
    # INIT and a disabled Cl-only schedule retain exact parent physics. The
    # declarations and authenticated source identities remain in the artifact.
    if model.phase != "SIM":
        coefficients[:] = 0.0
    on, off, change = np.zeros(3), np.ones(3), np.ones(3)
    enabled = np.zeros(3, dtype=bool)
    for event in model.bath_events:
        i = ORDER.index(event.kind)
        on[i], off[i], change[i] = event.on_s, event.off_s, event.change_s
        enabled[i] = model.phase == "SIM" and (event.kind != "Cl_env" or model.enabled_Cl)
    values = dict(
        bath_amount_coefficient_fmol=coefficients,
        bath_on_s=on,
        bath_off_s=off,
        bath_change_s=change,
        bath_target=target,
        bath_event_active=enabled,
        phase_end_s=np.asarray(spec.experiment.end_time),
        phase_clock_atol_s=np.asarray(
            64 * np.finfo(float).eps * max(spec.experiment.end_time, spec.execution.dt)
        ),
    )
    return values, tuple(bindings)


def check_ramp_steps(spec, steps):
    steps = np.asarray(steps, dtype=float)
    if steps.ndim != 1 or not np.isfinite(steps).all() or np.any(steps < 0):
        raise ConfigError("Bath steps must be a finite nonnegative vector")
    if spec.model.phase == "INIT":
        return
    for event in spec.model.bath_events:
        if event.kind == "Cl_env" and not spec.model.enabled_Cl:
            continue
        ceiling = event.change_s / 8
        allowance = max(
            2 * np.spacing(spec.experiment.end_time), 16 * np.finfo(float).eps * ceiling
        )
        if spec.execution.dt > ceiling * (1 + 16 * np.finfo(float).eps) or (
            np.max(steps, initial=0) > ceiling + allowance
        ):
            raise ConfigError("Bath RK4 steps must resolve each active transition time/8")


def artifact(spec, to_dict, model_id, parent_id, initial_operation):
    record = dict(
        kind=KIND,
        model_id=model_id,
        parent_model_id=parent_id,
        definition=to_dict(spec),
        initial_operation=initial_operation,
        scope="ideal reservoirs only; literal native setters plus explicit physical controllers",
    )
    record["identity"] = digest(record)
    return record


def replay(record, parse, artifact):
    _fields(
        record,
        {
            "kind",
            "model_id",
            "parent_model_id",
            "definition",
            "initial_operation",
            "scope",
            "identity",
        },
        "bath artifact",
    )
    if record["kind"] != KIND or digest(artifact(parse(record["definition"]))) != digest(record):
        raise ConfigError("Bath replay differs from its original controller preparation")
    return parse(record["definition"])
