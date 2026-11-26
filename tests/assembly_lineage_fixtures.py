"""Small assembly-lineage worlds for the family's unit tests (cells.model.assembly_lineages@1)."""

import copy

import numpy as np

from cells.models.assembly_lineages import (
    CONTINUATION,
    EXCHANGE_LAW,
    FISSION,
    GARD_PAIR_CONSISTENT,
    GARD_SINGLE_EVENT,
    MODEL_ID,
)

FORMS = (GARD_SINGLE_EVENT, GARD_PAIR_CONSISTENT)


def world(
    count=6,
    size=12,
    *,
    seed=3,
    matrix=True,
    sigma=2.0,
    founder_size=6,
    partition=None,
    daughter="first",
    empty="extinct",
    transfer_constant=3.0,
    supply=None,
    leave_rate=1.0,
    beta=None,
):
    """A world of `count` types splitting at `size`, with a lognormal catalysis matrix, or `beta`
    when given (then no matrix is drawn, and the founder's draw is unchanged)."""
    rng = np.random.default_rng(seed)
    founder = np.bincount(rng.integers(0, count, founder_size), minlength=count)
    result = {
        "types": {"prefix": "t", "count": count, "transfer_constant": transfer_constant},
        "supply": supply if supply is not None else (1.0 / count),
        "exchange": {"law": EXCHANGE_LAW, "leave_rate": leave_rate},
        "founder": founder.tolist(),
        "fission": {
            "operator": FISSION,
            "size": size,
            "partition": partition or {"rule": "exact_fraction", "fraction": 0.5},
        },
        "continuation": {
            "operator": CONTINUATION,
            "daughter": daughter,
            "empty": empty,
            "sink": "discard",
        },
    }
    if beta is not None:
        result["law_data"] = {"catalysis_matrix": [list(map(float, row)) for row in beta]}
    elif matrix:
        beta = np.exp(-1.0 + sigma * rng.standard_normal((count, count)))
        result["law_data"] = {"catalysis_matrix": beta.tolist()}
    return result


def definition(
    the_world,
    law=GARD_PAIR_CONSISTENT,
    *,
    fissions=4,
    uniforms=False,
    trace=True,
    seed=1,
    environment=0,
    lineage=0,
    branch=0,
    capacity=8,
    molecules=16,
    chunk=16,
    limit=100000,
):
    model = {"id": MODEL_ID, "world": copy.deepcopy(the_world)}
    if law is not None:
        model["rate_factor"] = {"law": law}
    return {
        "schema_version": 1,
        "model": model,
        "experiment": {
            "fissions": fissions,
            "growth_event_limit": limit,
            "trace": trace,
            "uniforms": uniforms,
        },
        "execution": {
            "backend": "cpu",
            "precision": "float64",
            "mode": "single_lineage",
            "stream": {
                "seed": seed,
                "environment": environment,
                "lineage": lineage,
                "branch": branch,
            },
            "type_capacity": capacity,
            "molecule_capacity": molecules,
            "chunk_events": chunk,
            "unroll": 8,
        },
    }
