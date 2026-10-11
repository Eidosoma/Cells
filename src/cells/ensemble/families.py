"""Versioned assembly adapters; scientific families are explicit in every task."""

import copy

MODELS = {
    "assembly_ensemble@1": "capsid_graph@1",
    "finite_bond_ensemble@1": "finite_bond_assembly@1",
    "assembly_cell_ensemble@1": "assembly_regulated_cell@1",
    "assembly_cluster_ensemble@1": "assembly_regulated_cluster@1",
    "ionic_ensemble@1": "ionic_worlds@1",
}


def bind_definition(data, *, worlds, world_id_start, seed, reject_owned=False):
    result = copy.deepcopy(data)
    if result.get("model") == "assembly_regulated_cluster@1":
        for binding in result["pools"]:
            target = binding["pool"]
            stream = binding["stream_id"]
            if type(stream) is not int or not 0 <= stream < 2**32:
                raise ValueError("Cluster stream ID must be uint32")
            if reject_owned and {"worlds", "world_id_start", "seed"} & set(target):
                raise ValueError("Ensemble owns seed/world counts/IDs, not arm definitions")
            target.update(
                worlds=worlds, world_id_start=world_id_start, seed=(seed + stream) % 2**32
            )
        return result
    target = result["pool"] if result.get("model") == "assembly_regulated_cell@1" else result
    if reject_owned and {"worlds", "world_id_start", "seed"} & set(target):
        raise ValueError("Ensemble owns seed/world counts/IDs, not arm definitions")
    target.update(worlds=worlds, world_id_start=world_id_start, seed=seed)
    return result


def model_id(spec):
    return spec.to_dict()["model"]


def population(spec):
    return (
        spec.pool
        if model_id(spec) in ("assembly_regulated_cell@1", "assembly_regulated_cluster@1")
        else spec
    )


def output_bound(spec):
    if model_id(spec) == "assembly_regulated_cell@1":
        from cells.models.kinetic_finite_extracellular import working_size

        return spec.pool.output_bound + spec.pool.worlds * (32 * working_size(spec.ionic) + 4096)
    return spec.output_bound


def parse_definition(data):
    if data.get("model") == "assembly_regulated_cluster@1":
        from cells.assembly_cluster.spec import parse_spec
    elif data.get("model") == "assembly_regulated_cell@1":
        from cells.assembly_cell.spec import parse_spec
    elif data.get("model") == "ionic_worlds@1":
        from cells.ensemble.ionic import parse_spec
    elif data.get("model") == "finite_bond_assembly@1":
        from cells.assembly_pool.spec import parse_spec
    else:
        from cells.assembly.spec import parse_spec
    return parse_spec(data)


def runtime_for(spec):
    if model_id(spec) == "assembly_regulated_cluster@1":
        from cells.ensemble.cluster import load_checkpoint, run, write_checkpoint
    elif model_id(spec) == "assembly_regulated_cell@1":
        from cells.ensemble.coupled import load_checkpoint, run, write_checkpoint
    elif model_id(spec) == "ionic_worlds@1":
        from cells.ensemble.ionic import load_checkpoint, run, write_checkpoint
    elif model_id(spec) == "finite_bond_assembly@1":
        from cells.assembly_pool.engine import run
        from cells.assembly_pool.io import load_checkpoint, write_checkpoint
    else:
        from cells.assembly.engine import run
        from cells.assembly.io import load_checkpoint, write_checkpoint
    return run, load_checkpoint, write_checkpoint


def first_completion(spec, state):
    if model_id(spec) == "assembly_regulated_cluster@1":
        # Each cell has its own assembly outcome; do not turn two pools into
        # twice as many independent worlds or an implicit cluster outcome.
        return None
    if model_id(spec) == "assembly_regulated_cell@1":
        return state.pool.full_first_s
    if model_id(spec) == "ionic_worlds@1":
        return None
    if model_id(spec) == "finite_bond_assembly@1":
        return state.full_first_s
    return state.first_passage_s[:, 20]


def progress(spec, state):
    if model_id(spec) == "ionic_worlds@1":
        return {
            "world_steps": sum(cp.step_index for cp in state.values()),
            "through_time_s": min(cp.time for cp in state.values()),
        }
    pool = (
        state.pool
        if model_id(spec) in ("assembly_regulated_cell@1", "assembly_regulated_cluster@1")
        else state
    )
    return {
        "events": int(pool.event_count.astype("uint64").sum()),
        "through_time_s": float(pool.time_s.min()),
    }


def failure_state(spec, state):
    if model_id(spec) in ("assembly_regulated_cell@1", "assembly_regulated_cluster@1"):
        from cells.assembly_cell.io import flatten

        return flatten(state)
    if model_id(spec) == "ionic_worlds@1":
        return {
            f"world_{identity}_{field}": value
            for identity, cp in state.items()
            for field, value in cp.state._asdict().items()
        }
    return state._asdict()
