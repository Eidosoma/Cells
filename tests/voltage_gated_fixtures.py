"""Schema adapter for frozen NUM-007 cases; never a numerical oracle."""

from dataclasses import asdict

import numpy as np

from cells.core.specs import VOLTAGE_GATED_ID, parse_spec
from tests import multispecies_fixtures as ionic


def definition(case, *, dt=0.0005, channel_capacity=1, **kwargs):
    result = ionic.definition(case, dt=dt, **kwargs)
    result["model"]["id"] = VOLTAGE_GATED_ID
    result["model"]["channel"] = asdict(case.channel)
    result["execution"]["channel_capacity"] = channel_capacity
    result["experiment"]["channel_controls"] = {
        "channel_id": case.channel.id,
        "schedule": [{"time": c.time_s, "availability": c.availability} for c in case.controls],
    }
    return result


def spec_for(case, **kwargs):
    return parse_spec(definition(case, **kwargs))


def canonical_values(case, state):
    return np.concatenate(
        (
            ionic.canonical_values(case, state),
            state.gate[..., :, 0],
            state.channel_transferred[..., :1],
        ),
        axis=-1,
    )
