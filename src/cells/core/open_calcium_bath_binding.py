"""Scheduled ideal baths around explicit open calcium/fuel transport owners.

The static owner is a transport input view. The scheduled model has its own
exterior policy, phase-clock controllers and variable chemical-work ledger.
Actual reservoir flags and fixed background charge are never changed.
"""

from copy import deepcopy
from dataclasses import fields

import numpy as np

from cells.core import open_calcium_declarations as admission
from cells.core import surface_bath_events_binding as bath
from cells.core.specs import ConfigError
from cells.models import open_calcium_admission as domain

EXTERIOR_POLICY = "scheduled_declared_ideal_chemical_and_fixed_voltage_reservoirs@1"


def parse_owner(data, model_id, parent):
    raw = deepcopy(data)
    if (
        not isinstance(raw, dict)
        or not isinstance(raw.get("model"), dict)
        or raw["model"].get("id") != model_id
        or raw["model"].get("exterior_policy") != EXTERIOR_POLICY
    ):
        raise ConfigError("Declare the scheduled open calcium/fuel exterior policy")
    raw["model"]["exterior_policy"] = admission.EXTERIOR_POLICY
    return bath.parse_owner(raw, model_id, parent.MODEL_ID, parent.parse)


def owner_fields(model, model_type):
    values = {field.name: getattr(model, field.name) for field in fields(model_type)}
    values["exterior_policy"] = admission.EXTERIOR_POLICY
    return values


def augment(raw, spec, model_id):
    raw = bath.augment(raw, spec, model_id)
    raw["model"]["exterior_policy"] = EXTERIOR_POLICY
    return raw


def check_initial_envelope(spec, state, p):
    """Admit initial material plus every dose in the conservative pulse box.

    This is a sufficient initial-program check. Evolving physical ionic totals
    must still obey the declared hard ceilings at every integration stage.
    """
    upper = domain.ionic_moieties(state, p, xp=np)
    upper = upper + np.sum(np.maximum(p.bath_amount_coefficient_fmol, 0.0), axis=(0, 2))
    if p.open_reservoir_world and np.any(upper > p.open_ionic_moiety_ceiling_fmol):
        raise ConfigError("Bath pulse envelope exceeds declared hard ionic-moiety ceilings")
    return upper
