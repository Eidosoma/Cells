"""Sealed native background-D capabilities for the two full56 joint water owners.

The qualified composed preparation owns geometry and coefficient selection.
The complete water/fuel/repair model retains every physical declaration.
"""

from copy import deepcopy

from cells.core import owned_calcium_profile_binding as native
from cells.core.specs import ConfigError, digest

TIMING_POLICY = native.TIMING_POLICY
RESET_POLICY = native.RESET_POLICY
ARTIFACT_KIND = "cells.scheduled_joint_water_membranes@1"
bindings = native.bindings
parse_owner = native.parse_owner
augment = native.augment
native_parameters = native.native_parameters
background_loss_bound = native.background_loss_bound
check_checkpoint = native.check_checkpoint


def artifact(spec, to_dict, model_id, parent_id):
    record = native.artifact(spec, to_dict, model_id, parent_id)
    record.pop("identity")
    record.update(
        kind=ARTIFACT_KIND,
        scope=(
            "background plasma D only; actual full56 chemical, moving-volume, "
            "finite-fuel and prescribed-repair owners retained"
        ),
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
            raise ConfigError("Stale or wrong-owner scheduled joint water artifact")
        spec = parse(value["definition"])
        if digest(artifact(spec)) != digest(record):
            raise ConfigError("Joint water binding or complete physical recipe changed")
        return spec
    except (KeyError, TypeError, ValueError, ArithmeticError) as error:
        raise ConfigError("Invalid scheduled joint water artifact: " + str(error)) from error
