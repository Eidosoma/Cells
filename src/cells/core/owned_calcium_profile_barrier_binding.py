"""Full calcium/fuel ownership with qualified coefficient-only declarations."""

from copy import deepcopy
from types import SimpleNamespace

from cells.core import owned_calcium_profile_barrier_preparation as preparation
from cells.core import owned_calcium_profile_binding as membrane_declarations
from cells.core import surface_active_profile_barrier_binding as coefficients
from cells.core.specs import ConfigError, _fields, digest

TIMING_POLICY = membrane_declarations.TIMING_POLICY
RESET_POLICY = membrane_declarations.RESET_POLICY
KIND = "cells.scheduled_calcium_profile_barriers@1"
EXTRA = {
    "coupled_preparation",
    "membrane_interventions",
    "barrier_intervention",
    "phase",
    "timing_policy",
    "reset_policy",
}


def parse_owner(data, model_id, parent_id, parent_parse, barrier_schema):
    try:
        _fields(
            data,
            {"schema_version", "model", "experiment", "execution"},
            "full calcium/fuel combined definition",
        )
        if type(data["schema_version"]) is not int or data["schema_version"] != 1:
            raise ConfigError("Require combined calcium/fuel schema_version 1")
        raw = deepcopy(data)
        m = raw["model"]
        if not isinstance(m, dict) or m.get("id") != model_id or not EXTRA <= m.keys():
            raise ConfigError("Require the exact combined calcium/fuel model identity")
        extra = {key: m.pop(key) for key in EXTRA}
        if (
            extra["phase"] not in ("INIT", "SIM")
            or extra["timing_policy"] != TIMING_POLICY
            or extra["reset_policy"] != RESET_POLICY
        ):
            raise ConfigError("Declare fresh phase, shared RK-stage clock and zero-buffer policies")
        artifact = _fields(
            extra["coupled_preparation"],
            {"definition", "provenance"},
            "full combined calcium/fuel preparation",
        )
        prepared = preparation.replay(artifact["provenance"])
        if digest(prepared.definition) != digest(artifact["definition"]) or digest(
            prepared.provenance
        ) != digest(artifact["provenance"]):
            raise ConfigError("Combined calcium/fuel artifact differs from its full recipe")
        if prepared.definition["model"]["id"] != parent_id:
            raise ConfigError("Combined model requires exactly " + parent_id)
        m["id"] = parent_id
        if digest(m) != digest(prepared.definition["model"]):
            raise ConfigError("Every store, channel, pool, owner and coefficient must match")
        first = deepcopy(raw)
        first["model"] = deepcopy(prepared.provenance["profile_preparation"]["definition"]["model"])
        # This parser validates declarations on the supplied exact parent;
        # it never invokes the older calcium@6 membrane runtime.
        first["model"].update(
            id=model_id,
            profile_preparation=deepcopy(prepared.provenance["profile_preparation"]),
            interventions=extra["membrane_interventions"],
            phase=extra["phase"],
            timing_policy=TIMING_POLICY,
            reset_policy=RESET_POLICY,
        )
        first["execution"].pop("barrier_target_capacity")
        _, _, events, ec, tc = membrane_declarations.parse_owner(
            first, model_id, parent_id, parent_parse
        )
        second = deepcopy(raw)
        second["model"].update(
            id=barrier_schema.MODEL_ID,
            barrier_preparation=deepcopy(prepared.provenance["barrier_preparation"]),
            intervention=extra["barrier_intervention"],
            phase=extra["phase"],
            timing_policy=TIMING_POLICY,
        )
        for key in ("intervention_capacity", "intervention_target_capacity"):
            second["execution"].pop(key)
        bs = barrier_schema.parse(second)
        ordinary = barrier_schema.owner_spec(bs)
        return (
            ordinary,
            extra,
            events,
            ec,
            tc,
            bs.model.intervention,
            bs.execution.barrier_target_capacity,
        )
    except (KeyError, TypeError, ValueError, ArithmeticError, AttributeError) as error:
        raise ConfigError("Invalid full calcium/fuel combined definition: " + str(error)) from error


def native_parameters(spec, parent):
    # Only the independently qualified direct coefficient declaration is
    # exposed. No physical calcium state, stage layout or fuel is projected.
    provenance = spec.model.coupled_preparation["provenance"]
    capability = dict(
        provenance=dict(
            profile_preparation=dict(
                provenance=provenance["profile_preparation"]["provenance"][
                    "direct_parameter_preparation"
                ]
            ),
            barrier_preparation=provenance["barrier_preparation"],
        )
    )
    view = SimpleNamespace(**(vars(spec.model) | dict(coupled_preparation=capability)))
    return coefficients.native_parameters(
        SimpleNamespace(model=view, experiment=spec.experiment, execution=spec.execution), parent
    )


check_ramp_steps = coefficients.check_ramp_steps


def artifact(spec, to_dict, model_id, parent_id):
    row = dict(
        kind=KIND,
        model_id=model_id,
        parent_model_id=parent_id,
        definition=to_dict(spec),
        preparation_identity=spec.model.coupled_preparation["provenance"]["identity"],
    )
    row["identity"] = digest(row)
    return row


def replay(record, parse, artifact, model_id, parent_id):
    try:
        row = deepcopy(record)
        identity = row.pop("identity")
        if (
            row["kind"] != KIND
            or row["model_id"] != model_id
            or row["parent_model_id"] != parent_id
            or digest(row) != identity
        ):
            raise ConfigError("Stale or wrong full-owner combined schedule artifact")
        spec = parse(row["definition"])
        if digest(artifact(spec)) != digest(record):
            raise ConfigError("Full-owner combined schedule recipe changed")
        return spec
    except (KeyError, TypeError, ValueError, ArithmeticError) as error:
        raise ConfigError(
            "Invalid calcium/fuel combined schedule artifact: " + str(error)
        ) from error
