"""Versioned assembly adapters; scientific families are explicit in every task.

**A family joins `cells ensemble` with no edit here** (docs/CORE_SEAMS_DESIGN.md §15's follow-up;
the lead's ruling (a), 18 November 2026): its row of the static model table names its
EnsembleAdapter (`ensemble`, "module:object"), loaded by name. MODELS holds the adapters' kinds,
then today's three; each hook below dispatches to the adapter of the spec's or definition's model,
falling back to today's chains for today's three families. A model ID is read in either form a
definition writes, a string or {"id": ..., ...} (model_of), once, in model_id and row_model, so the
planner, the launcher and the controller's summary compare strings (the second external review's
finding 5). A kind of PARKED is refused by its name until an adapter takes it (parked).
"""

import copy
import importlib
from collections.abc import Callable, Mapping
from typing import NamedTuple

from cells.registry import model_table

TODAY = {
    "assembly_ensemble@1": "capsid_graph@1",
    "finite_bond_ensemble@1": "finite_bond_assembly@1",
    "ionic_ensemble@1": "ionic_worlds@1",
}
PARKED = {
    "assembly_cell_ensemble@1": "GPU ensembles of assembly-regulated cells",
    "assembly_cluster_ensemble@1": "GPU ensembles of assembly-regulated clusters",
}


class EnsembleAdapter(NamedTuple):
    """A model family's hooks into `cells ensemble` (module docstring): its ensemble kind and the
    model its arms parse as, and the eight hooks today's families take here, each with today's
    signature: bind_definition(data, *, worlds, world_id_start, seed, reject_owned) -> data;
    population(spec) -> the part holding `recording` and `end_time_s`; output_bound(spec) ->
    bytes; parse_definition(data) -> spec; runtime(spec) -> (run, load_checkpoint,
    write_checkpoint); first_completion(spec, state) -> times or None; progress(spec, state) ->
    {name: value}; failure_state(spec, state) -> {name: array}; and aggregate(rows) -> {arm:
    summary}, the family's own summary of its completed tasks' result rows, which today's families
    have in cli and an adapter family must give (finding 5). The controller adds each arm's timing
    beside it (cli.ARM_TIMING_KEYS, which the family's summary may not use); a run's result row
    holds its worlds, as every family's does."""

    kind: str
    model: str
    bind_definition: Callable
    population: Callable
    output_bound: Callable
    parse_definition: Callable
    runtime: Callable
    first_completion: Callable
    progress: Callable
    failure_state: Callable
    aggregate: Callable


def adapter_errors(models):
    """Where the model table's `ensemble` entries break the protocol (empty: none do): each names
    an importable EnsembleAdapter, one per ensemble kind and per model, apart from today's three."""
    out, kinds = [], {}
    for model_id, row in models.items():
        if row.ensemble is None:
            continue
        module, _, name = row.ensemble.partition(":")
        try:
            adapter = getattr(importlib.import_module(module), name)
        except Exception as error:  # Reported, never swallowed: adapters() refuses on it.
            out.append(f"{model_id}: ensemble {row.ensemble!r} does not resolve ({error})")
            continue
        if not isinstance(adapter, EnsembleAdapter):
            out.append(f"{model_id}: ensemble {row.ensemble!r} is not an EnsembleAdapter")
        elif adapter.kind in kinds or adapter.kind in TODAY or adapter.model in TODAY.values():
            out.append(f"{model_id}: ensemble kind {adapter.kind} is taken")
        else:
            kinds[adapter.kind] = adapter
    return out


def adapters():
    """{ensemble kind: adapter} of the model table's rows that name one, in the table's order."""
    problems = adapter_errors(model_table.MODELS)
    if problems:
        raise ValueError("; ".join(problems))
    out = {}
    for row in model_table.MODELS.values():
        if row.ensemble is not None:
            module, _, name = row.ensemble.partition(":")
            adapter = getattr(importlib.import_module(module), name)
            out[adapter.kind] = adapter
    return out


class _Models(Mapping):
    """{ensemble kind: model} of the adapters' rows, then today's three (module docstring)."""

    def _models(self):
        return {**{kind: a.model for kind, a in adapters().items()}, **TODAY}

    def __getitem__(self, kind):
        return self._models()[kind]

    def __iter__(self):
        return iter(self._models())

    def __len__(self):
        return len(self._models())


MODELS = _Models()


def parked(name):
    """The refusal of a parked name: what is parked, and where it is re-expressed; or None."""
    what = PARKED.get(name) if isinstance(name, str) else None
    return what and (
        f"{name} is parked: {what}. Assembly-regulated cells and clusters are to be re-expressed "
        "on resolved_pump_composite@1, for cells run, windowed and batch"
    )


def model_of(model):
    """A definition's or a spec's model ID: today's families write a string, others {id, ...}."""
    return model.get("id") if isinstance(model, dict) else model


def row_model(row):
    """A completed task's result row's model ID: its own `model` where the run wrote one, else its
    definition's (worker.py writes every row's definition)."""
    if "model" in row:
        return model_of(row["model"])
    return model_of(row.get("definition", {}).get("model"))


def adapter_of(model):
    """The adapter of a model ID in either form, or None for today's families."""
    model = model_of(model)
    return next((a for a in adapters().values() if a.model == model), None)


def bind_definition(data, *, worlds, world_id_start, seed, reject_owned=False):
    adapter = adapter_of(data.get("model") if isinstance(data, dict) else None)
    if adapter is not None:
        return adapter.bind_definition(
            data,
            worlds=worlds,
            world_id_start=world_id_start,
            seed=seed,
            reject_owned=reject_owned,
        )
    result = copy.deepcopy(data)
    if reject_owned and {"worlds", "world_id_start", "seed"} & set(result):
        raise ValueError("Ensemble owns seed/world counts/IDs, not arm definitions")
    result.update(worlds=worlds, world_id_start=world_id_start, seed=seed)
    return result


def model_id(spec):
    """A spec's model ID as a string, whichever form its definition writes (model_of)."""
    return model_of(spec.to_dict()["model"])


def population(spec):
    adapter = adapter_of(model_id(spec))
    return spec if adapter is None else adapter.population(spec)


def output_bound(spec):
    adapter = adapter_of(model_id(spec))
    return spec.output_bound if adapter is None else adapter.output_bound(spec)


def parse_definition(data):
    adapter = adapter_of(data.get("model"))
    if adapter is not None:
        return adapter.parse_definition(data)
    if data.get("model") == "ionic_worlds@1":
        from cells.ensemble.ionic import parse_spec
    elif data.get("model") == "finite_bond_assembly@1":
        from cells.assembly_pool.spec import parse_spec
    else:
        from cells.assembly.spec import parse_spec
    return parse_spec(data)


def runtime_for(spec):
    adapter = adapter_of(model_id(spec))
    if adapter is not None:
        return adapter.runtime(spec)
    if model_id(spec) == "ionic_worlds@1":
        from cells.ensemble.ionic import load_checkpoint, run, write_checkpoint
    elif model_id(spec) == "finite_bond_assembly@1":
        from cells.assembly_pool.engine import run
        from cells.assembly_pool.io import load_checkpoint, write_checkpoint
    else:
        from cells.assembly.engine import run
        from cells.assembly.io import load_checkpoint, write_checkpoint
    return run, load_checkpoint, write_checkpoint


def first_completion(spec, state):
    adapter = adapter_of(model_id(spec))
    if adapter is not None:
        return adapter.first_completion(spec, state)
    if model_id(spec) == "ionic_worlds@1":
        return None
    if model_id(spec) == "finite_bond_assembly@1":
        return state.full_first_s
    return state.first_passage_s[:, 20]


def progress(spec, state):
    adapter = adapter_of(model_id(spec))
    if adapter is not None:
        return adapter.progress(spec, state)
    if model_id(spec) == "ionic_worlds@1":
        return {
            "world_steps": sum(cp.step_index for cp in state.values()),
            "through_time_s": min(cp.time for cp in state.values()),
        }
    return {
        "events": int(state.event_count.astype("uint64").sum()),
        "through_time_s": float(state.time_s.min()),
    }


def failure_state(spec, state):
    adapter = adapter_of(model_id(spec))
    if adapter is not None:
        return adapter.failure_state(spec, state)
    if model_id(spec) == "ionic_worlds@1":
        return {
            f"world_{identity}_{field}": value
            for identity, cp in state.items()
            for field, value in cp.state._asdict().items()
        }
    return state._asdict()
