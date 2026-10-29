"""Explicit sequential static preparation of one complete full56 ionic owner."""

from copy import deepcopy

from cells.core import environment_barrier_composition_preparation as barriers
from cells.core import tissue_profile_preparation as profiles
from cells.core.specs import ConfigError, _fields, digest, parse_spec

REQUEST_KIND = "cells.active_profile_barrier_preparation_request@1"
KIND = "cells.active_profile_barrier_preparation@1"
PARENT_MODEL_ID = "resolved_tissue@12"
ORDER = "static_membrane_profiles_then_extracellular_barriers@1"
Preparation = barriers.Preparation


def prepare(request):
    try:
        raw = profiles._json(
            _fields(
                request,
                {"kind", "order", "profile_preparation", "barrier_request"},
                "combined preparation request",
            )
        )
        if raw["kind"] != REQUEST_KIND or raw["order"] != ORDER:
            raise ConfigError("Declare the explicit combined preparation order and identity")
        artifact = _fields(
            raw["profile_preparation"],
            {"definition", "provenance"},
            "complete active membrane preparation",
        )
        if artifact["provenance"].get("kind") != profiles.KIND:
            raise ConfigError("Require the qualified direct full56 membrane preparation")
        membrane = profiles.replay(artifact["provenance"])
        if digest(membrane.definition) != digest(artifact["definition"]) or digest(
            membrane.provenance
        ) != digest(artifact["provenance"]):
            raise ConfigError("Membrane preparation differs from its full recipe")
        if membrane.definition["model"]["id"] != PARENT_MODEL_ID:
            raise ConfigError("Combined preparation requires exactly resolved_tissue@12")
        barrier_request = raw["barrier_request"]
        if not isinstance(barrier_request, dict) or digest(
            barrier_request.get("definition")
        ) != digest(membrane.definition):
            raise ConfigError(
                "Barrier recipe must own the exact complete membrane-prepared definition"
            )
        final = barriers.prepare(barrier_request)
        before, after = (parse_spec(v) for v in (membrane.definition, final.definition))
        from cells.models import surface_hcn_extra as owner

        first, _ = owner.initial_values(before)
        last, _ = owner.initial_values(after)
        if profiles._state_identity(first) != profiles._state_identity(last):
            raise ConfigError("Combined preparation changed the complete parent state")
        provenance = dict(
            kind=KIND,
            order=ORDER,
            parent_model_id=PARENT_MODEL_ID,
            request=raw,
            profile_preparation=artifact,
            barrier_preparation=dict(definition=final.definition, provenance=final.provenance),
            initial_state_sha256=profiles._state_identity(first),
            initial_state_fields=list(first._fields),
            complete_definition_sha256=digest(final.definition),
            scope="static background membrane and exterior face coefficients; complete ionic physics",
        )
        provenance["identity"] = digest(provenance)
        return Preparation(final.definition, profiles._json(provenance))
    except (KeyError, TypeError, ValueError, ArithmeticError, AttributeError) as error:
        raise ConfigError("Invalid combined active preparation: " + str(error)) from error


def replay(provenance):
    try:
        row = deepcopy(provenance)
        identity = row.pop("identity")
        if row["kind"] != KIND or digest(row) != identity:
            raise ConfigError("Stale combined preparation identity")
        result = prepare(row["request"])
        if digest(result.provenance) != digest(provenance):
            raise ConfigError("Combined static owners or preparation recipe changed")
        return result
    except (KeyError, TypeError, ValueError, ArithmeticError) as error:
        raise ConfigError("Invalid combined active preparation replay: " + str(error)) from error
