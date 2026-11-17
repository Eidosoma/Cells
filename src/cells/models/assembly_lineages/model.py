"""The assembly-lineage family's entry in the model registry (models/registry.get_model).

The family's runner shape is its own (CORE_SEAMS_DESIGN §8.4): an event-driven lineage, not the
fixed-step runner's world, so it offers none of that runner's interface. What it offers, resolved
when the model is built (no value enters a program):

- structure(spec): the value-free structure that selects the compiled program (the compile key);
- layout(spec): the world's values as host arrays, one lane's;
- founder(spec): the founder's counts, padded to the type capacity;
- components(spec): the registered IDs the definition uses (model, laws, operators);
- run(spec) (runner.py) and write_run / write_pair (records.py); RUNNER names the entry.
"""

import numpy as np

from cells.models.assembly_lineages import MODEL_ID, factors, ledger, streams
from cells.models.assembly_lineages.kernel import Layout, Structure

OBSERVER_ID = None  # No fixed-step observer: records come from the lineage itself (records.py).
# Its own runner, declared as data: the command line's fixed-step paths (`cells validate`, `cells
# run`) refuse a model that declares one, naming it, before they build a time grid.
RUNNER = "cells.models.assembly_lineages.runner:run"


def structure(spec):
    m, e, x = spec.model, spec.experiment, spec.execution
    world = m.world
    return Structure(
        capacity=x.type_capacity,
        molecule_capacity=x.molecule_capacity,
        factor=m.rate_factor,
        partition=world.fission.partition.rule,
        daughter=world.continuation.daughter,
        empty=world.continuation.empty,
        chunk=x.chunk_events,
        unroll=x.unroll,
        uniforms=e.uniforms,
    )


def _padded(values, capacity):
    out = np.zeros(capacity, dtype=np.float64)
    out[: len(values)] = values
    return out


def layout(spec):
    """One lane's values (host NumPy arrays)."""
    m, e, x = spec.model, spec.experiment, spec.execution
    world, capacity = m.world, x.type_capacity
    supply = np.asarray(world.supply, dtype=np.float64)
    constants = np.asarray(world.types.transfer_constant, dtype=np.float64)
    leave = np.asarray(world.leave_rate, dtype=np.float64)
    join = constants * leave  # kf_i = K_i kb_i (exchange.py).
    law = None if m.rate_factor is None else factors.resolve(m.rate_factor)
    return Layout(
        kf_rho=_padded(join * supply, capacity),
        kb=_padded(leave, capacity),
        log_theta=_padded(np.log(constants * supply), capacity),
        log_factorial=ledger.log_factorials(x.molecule_capacity),
        split_size=np.int64(world.fission.size),
        split_value=np.float64(world.fission.partition.value),
        fission_limit=np.int64(e.fissions),
        growth_limit=np.int64(e.growth_event_limit),
        base_key=streams.base_key_data(x.seed, x.environment, x.lineage, x.branch),
        factor=() if law is None else law.layout(world.data, capacity),
    )


def founder(spec):
    counts = np.zeros(spec.execution.type_capacity, dtype=np.int64)
    counts[: spec.model.world.types.count] = spec.model.world.founder
    return counts


def components(spec):
    """The registered IDs the definition uses, by role."""
    m = spec.model
    world = m.world
    return {
        "model": MODEL_ID,
        "laws": [world.exchange_law] + ([m.rate_factor] if m.rate_factor else []),
        "operators": [world.fission.operator, world.continuation.operator],
    }
