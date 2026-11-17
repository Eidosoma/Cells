"""The lineage runner: the family's own runner shape (event-driven, not fixed-step).

Three entries, all on the same compiled programs (kernel.program, one per structure and lane
count), so a world's values never depend on how it was run:
- run(spec, start=None, stop=None): one world's lineage. `start` is a checkpoint to continue or
  branch from (checkpoints.py); `stop` an event count at which the run stops, its state saved for a
  checkpoint (the lineage's cumulative events: a stop between two events of a growth, or right
  after the join that makes a fission due, which then stays pending);
- run_lanes(specs, starts=None): several worlds of one structure, as lanes of one program (each
  lane's values its own), each fresh or from a checkpoint;
- run_population(spec): every descendant (mode every_descendant, below).

The host loop of one batch of lanes:

    repeat:  if a lane is FISSION_DUE, run the fission pass (a no-op for the others);
             advance one chunk of events (a lane that is not RUNNING waits and draws nothing);
    until no lane is RUNNING or FISSION_DUE.

A stop is exact: within one chunk of it, the loop advances by a program of one event per call (the
same event function, compiled for a chunk of one; the chunk changes no value), so the lane stops
exactly at its stop. Every other program is untouched.

**Records** (records.py declares them): the rows (the start; per fission the parent before the
split and the followed daughter after it, both at the fission's time; and always a final end row,
the lineage's state when the run ended), the fission table, the event trace (one growth per life
that ran), the lives (keys.py: one row per birth and end, with its end reason), and the run's
qualifier and start. The ledger is closed at every row (ledger.py). A passive law's run whose
ledger does not close is refused: its status says so, and check() raises. Nothing is repaired,
and failed runs keep their records.

**Every descendant** (RELATIONSHIPS_DESIGN §1.4, P-a). Every daughter lives as its own lane. Lives
run generation by generation, in batches of `execution.lanes` lanes padded with empty lanes (one
compiled program for every generation): each runs from its birth state to its fission, its
extinction, the event guard or a stall. Then each fission's followed daughter is the fission
pass's own lane, as in single-lineage mode, and its sibling is the sibling pass's (kernel.sibling).
Once a generation has ended, new sub-lineages are numbered (keys.number_sublineages) and the next
generation runs. Every life's lane inherits its parent's cumulative state, so the followed path is
the single lineage's bitwise: the same programs on the same states, keyed by the same keys. Lives
of the generation limit (experiment.fissions) are born and censored at the horizon. When a
generation's runnable lives exceed what is left of experiment.life_budget, the whole generation is
censored at its birth and the run ends. Growth is 2**g lives at generation g; the bound is stated
in the run (bound).

Timings: compile (once per structure and lane count, cached) apart from the run, and the event
rate of the run itself, measured, never presumed.
"""

from dataclasses import dataclass, field
from time import perf_counter

import numpy as np

from cells.core.specs import ConfigError
from cells.models.assembly_lineages import (
    EVERY_DESCENDANT,
    MODE,
    balance,
    checkpoints,
    factors,
    kernel,
    keys,
    ledger,
    model,
)

ROW_KINDS = ("start", "parent", "daughter", "end")
START, PARENT, DAUGHTER, END = range(4)
_COMPILED = {}
_STOPPED = "stopped"


class LedgerRefused(ConfigError):
    """A passive law's ledger did not close at a saved row."""


@dataclass
class LineageRun:
    spec: object
    structure: object
    verdict: dict
    world_report: dict | None
    status: str
    rows: dict
    fissions: dict
    trace: dict
    diagnostics: dict
    closure: dict
    lives: dict
    qualifier: str
    start: object  # "fresh", or the start record of a run from a checkpoint.
    final: dict  # The last lane state (host arrays), as a checkpoint saves it.
    timings: dict = field(default_factory=dict)
    bound: dict | None = None  # Every descendant: the stated bound.

    def check(self):
        """Raise if the run was refused (a passive law's ledger that did not close)."""
        if self.closure["refused"]:
            raise LedgerRefused(self.closure["refused"])
        return self

    def checkpoint(self):
        """The checkpoint of the run's last state: a landmark after its last fission, or the
        state at its stop (single-lineage runs)."""
        return checkpoints.make(self.spec, self.qualifier, self.final)


# ------------------------------------------------------------------ programs


def _compiled(structure, lanes, layout):
    """(initial, advance, split, compile seconds) of one structure for `lanes` lanes."""
    import jax

    key = (structure, lanes)
    if key not in _COMPILED:
        started = perf_counter()
        program = kernel.program(structure)
        founders = jax.ShapeDtypeStruct((lanes, structure.capacity), np.int64)
        initial = program.initial.lower(founders, layout).compile()
        shapes = jax.eval_shape(program.initial, founders, layout)
        advance = program.advance.lower(shapes, layout).compile()
        split = program.split.lower(shapes, layout).compile()
        _COMPILED[key] = (initial, advance, split, perf_counter() - started)
    return _COMPILED[key]


def _sibling(structure, lanes, layout):
    import jax

    key = ("sibling", structure, lanes)
    if key not in _COMPILED:
        program = kernel.sibling_program(structure)
        founders = jax.ShapeDtypeStruct((lanes, structure.capacity), np.int64)
        shapes = jax.eval_shape(kernel.program(structure).initial, founders, layout)
        first = jax.ShapeDtypeStruct((lanes, structure.capacity), np.int64)
        followed = jax.ShapeDtypeStruct((lanes,), np.int64)
        _COMPILED[key] = program.lower(shapes, layout, first, followed).compile()
    return _COMPILED[key]


def _stack(trees):
    import jax

    return jax.tree_util.tree_map(lambda *xs: np.stack([np.asarray(x) for x in xs]), *trees)


def _lane(tree, i):
    """Lane i of a stacked lane tree, as {field: host array} (factor_state () when absent)."""
    out = {}
    for name in kernel.Lane._fields:
        value = getattr(tree, name)
        out[name] = () if isinstance(value, tuple) and not value else np.asarray(value)[i].copy()
    return out


def _restack(lanes):
    """Host lane dicts as one stacked kernel.Lane of host arrays."""
    fields = {}
    for name in kernel.Lane._fields:
        values = [lane.get(name, ()) for lane in lanes]
        fields[name] = () if isinstance(values[0], tuple) else np.stack(values)
    return kernel.Lane(**fields)


def _host_row(lane, count):
    """A row (a lane's state, declared types only) from a host lane dict."""
    out = {name: np.asarray(lane[name]).copy() for name in kernel.Row._fields}
    for name in ("counts", "joined", "left", "discarded"):
        out[name] = out[name][:count]
    return out


# ------------------------------------------------------------------ preparing a batch


def _prepare(specs):
    """The structure, the law's verdict and reports, and the batch's layout (host)."""
    structures = {model.structure(s) for s in specs}
    if len(structures) != 1:
        raise ConfigError("Lanes share one structure (capacities, laws, rules and recording)")
    (structure,) = structures
    if len({s.execution.backend for s in specs}) != 1:
        raise ConfigError("Lanes share one backend")
    verdict = balance.verdict(structure.factor)  # Refuses a failing law declared passive.
    law = None if structure.factor is None else factors.resolve(structure.factor)
    reports = [
        balance.world_report(s) if law is not None and law.energy_role == "driven" else None
        for s in specs
    ]
    return structure, verdict, reports


def _steps_into(out, structure, holders, count_lanes):
    """Append each lane's committed events of one advance call to its holder's steps."""
    committed = np.asarray(out.committed)
    if not committed.any():
        return
    channel, time = np.asarray(out.channel), np.asarray(out.time)
    draws = np.asarray(out.uniforms) if structure.uniforms else None
    for i in range(count_lanes):
        holder = holders[i]
        if holder is None:
            continue
        mask = committed[:, i]
        if mask.any():
            holder.steps.append(
                (channel[mask, i], time[mask, i], None if draws is None else draws[mask, i])
            )


class _Lineage:
    """One lane's records in single-lineage mode (host side)."""

    def __init__(self, count, lane, start):
        self.count = count
        self.rows = [_host_row(lane, count) | {"kind": START, "fission": 0}]
        self.sublineage = int(lane["next_carrier"]) >> 32  # Its counter's: 0 in one lineage.
        self.steps = []
        self.splits = []
        self.start = start  # "fresh" or the start record.


# ------------------------------------------------------------------ single lineage


def run(spec, *, start=None, stop=None):
    """One world's lineage, fresh or from a checkpoint, to its end or to an exact stop."""
    return run_lanes([spec], starts=[start], stop=stop)[0]


def run_lanes(specs, *, starts=None, stop=None, calls=None):
    """Several worlds of one structure, as lanes of one program; one LineageRun each.

    `calls`, when given, pauses the batch after that many device calls (event chunks and fission
    passes): each lane still running is then `stopped`, its state saved for a checkpoint
    (LineageRun.checkpoint), from which a later batch resumes it bitwise."""
    import jax

    from cells.core.devices import execution_device

    if any(s.execution.mode != MODE for s in specs):
        raise ConfigError(f"run_lanes runs {MODE} worlds; every_descendant runs run_population")
    starts = list(starts) if starts is not None else [None] * len(specs)
    if len(starts) != len(specs):
        raise ConfigError("One start (a checkpoint or None) per world")
    if stop is not None and len(specs) != 1:
        raise ConfigError("A stop is declared for one lineage at a time")
    structure, verdict, reports = _prepare(specs)
    admitted = [
        None if c is None else checkpoints.admit(s, c) for s, c in zip(specs, starts, strict=True)
    ]
    if stop is not None:
        first_events = 0 if admitted[0] is None else int(admitted[0][1]["events"])
        if type(stop) is not int or stop <= first_events:
            raise ConfigError("A stop is a lineage event count after the run's start")
    device = execution_device(specs[0].execution.backend)
    host_layout = _stack([model.layout(s) for s in specs])
    layout = jax.device_put(host_layout, device)
    founders = jax.device_put(np.stack([model.founder(s) for s in specs]), device)
    count = [s.model.world.types.count for s in specs]
    L = len(specs)
    with jax.default_device(device):
        initial, advance, split, compile_seconds = _compiled(structure, L, layout)
        one = None
        if stop is not None:
            _, one, _, _ = _compiled(structure._replace(chunk=1), L, layout)
        started = perf_counter()
        lanes = initial(founders, layout)
        if any(a is not None for a in admitted):
            host = [_lane(lanes, i) if a is None else a[1] for i, a in enumerate(admitted)]
            lanes = jax.device_put(_restack(host), device)
        holders = [
            _Lineage(count[i], _lane(lanes, i), admitted[i][0] if admitted[i] else "fresh")
            for i in range(L)
        ]
        chunks = made = 0
        held = np.zeros(L, dtype=bool)
        while True:
            status = np.asarray(lanes.status)
            active = (status == kernel.RUNNING) | (status == kernel.FISSION_DUE)
            if stop is not None and int(np.asarray(lanes.events)[0]) >= stop:
                held[0] = True
                break
            if not active.any():
                break
            if calls is not None and made >= calls:
                held = active
                break
            made += 1
            if (status == kernel.FISSION_DUE).any():
                lanes, record = split(lanes, layout)
                _record_splits(record, structure, holders, count)
                continue
            program = advance
            if stop is not None and stop - int(np.asarray(lanes.events)[0]) < structure.chunk:
                program = one
            lanes, out = program(lanes, layout)
            chunks += 1
            _steps_into(out, structure, holders, L)
        jax.block_until_ready(lanes)
        run_seconds = perf_counter() - started
    results = []
    for i, spec in enumerate(specs):
        final = _lane(lanes, i)
        holder = holders[i]
        holder.rows.append(_host_row(final, count[i]) | {"kind": END, "fission": 0})
        status = _STOPPED if held[i] else kernel.STATUS[int(final["status"])]
        events = sum(len(c) for c, _, _ in holder.steps)
        start = holder.start
        qualifier = keys.qualifier(
            spec.fingerprint, "fresh" if start == "fresh" else {"checkpoint": start["checkpoint"]}
        )
        results.append(
            _assemble(
                spec,
                structure,
                verdict,
                reports[i],
                status,
                holder.rows,
                holder.splits,
                holder.steps,
                _single_lives(holder, status),
                _single_growths(holder),
                qualifier,
                start,
                final,
                {
                    "compile_seconds": compile_seconds,
                    "run_seconds": run_seconds,
                    "lanes": L,
                    "chunks": chunks,
                    "events": events,
                    "events_per_second": events / run_seconds if run_seconds > 0 else None,
                    "scope": "wall time of the whole lane batch on its device; compile apart "
                    "(cached per structure and lane count)",
                },
            )
        )
    return results


def _record_splits(record, structure, holders, count):
    """Rows and fission-table entries of one fission pass (each fired lane's holder)."""
    import jax

    fired = np.asarray(record.fired)
    host = jax.tree_util.tree_map(np.asarray, record)
    for i in np.flatnonzero(fired):
        holder = holders[i]
        if holder is None:
            continue
        k = int(host.after.fissions[i])  # The fission's number along the lineage's path.
        holder.splits.append(_split_entry(host, i, structure, count[i]))
        before = {name: getattr(host.before, name)[i] for name in kernel.Row._fields}
        after = {name: getattr(host.after, name)[i] for name in kernel.Row._fields}
        holder.rows.append(_host_row(before, count[i]) | {"kind": PARENT, "fission": k})
        holder.rows.append(_host_row(after, count[i]) | {"kind": DAUGHTER, "fission": k})


def _split_entry(host, i, structure, count):
    return {
        "parent": host.parent[i],
        "daughters": host.daughters[i],
        "followed": host.followed[i],
        "first": host.first[i][:count],
        "similarity": host.similarity[i],
        "time": host.before.time[i],
        "events": host.before.events[i],
        "places": None if not structure.uniforms else host.places[i],
        "choice": None if not structure.uniforms else host.choice[i],
    }


def _censored_by(status):
    return {
        "complete": "horizon",
        "event_limit": "event_limit",
        "stalled": "stalled",
        _STOPPED: "stop",
    }.get(status)


def _life(key, *, slot, parent, birth_kind, time, event, fission, generation, root, sub, size):
    return {
        "key": int(key),
        "slot": int(slot),
        "parent": int(parent),
        "birth_kind": birth_kind,
        "birth_time": float(time),
        "birth_event": int(event),
        "birth_fission": int(fission),
        "end_reason": None,
        "censored_by": "",
        "end_time": np.nan,
        "end_event": -1,
        "end_fission": -1,
        "generation": int(generation),
        "root": int(root),
        "sublineage": int(sub),
        "size_at_birth": int(size),
    }


def _end(life, reason, time, event, fission=-1, censored_by=""):
    life.update(
        end_reason=reason,
        end_time=float(time),
        end_event=int(event),
        end_fission=int(fission),
        censored_by=censored_by,
    )


def _single_lives(holder, status):
    """The lives of one single-lineage run, in (generation, parent key, daughter index) order."""
    first = holder.rows[0]
    fresh = holder.start == "fresh"
    current = _life(
        first["occupant"],
        slot=0,
        parent=-1,
        birth_kind="founder" if fresh else "continued",
        time=first["time"],
        event=first["events"],
        fission=-1,
        generation=first["generation"],
        root=keys.FOUNDER,
        sub=holder.sublineage,
        size=first["size"],
    )
    lives = [current]
    parents = [r for r in holder.rows if r["kind"] == PARENT]
    for index, split in enumerate(holder.splits):
        time, event = split["time"], split["events"]
        _end(current, "divided", time, event, index)
        taken = int(np.asarray(split["first"]).sum())
        sizes = (taken, int(parents[index]["size"]) - taken)
        followed = int(split["followed"])
        nxt = None
        for d in (0, 1):
            life = _life(
                split["daughters"][d],
                slot=0 if d == followed else -1,
                parent=split["parent"],
                birth_kind="division",
                time=time,
                event=event,
                fission=index,
                generation=current["generation"] + 1,
                root=current["root"],
                sub=current["sublineage"] if d == followed else -1,
                size=sizes[d],
            )
            if d != followed:
                _end(life, "extinct" if sizes[d] == 0 else "not_followed", time, event, index)
            elif sizes[d] == 0:
                _end(life, "extinct", time, event, index)
            lives.append(life)
            if d == followed:
                nxt = life
        current = nxt
    if current["end_reason"] is None:
        last = holder.rows[-1]
        if status == "extinct":
            _end(current, "extinct", last["time"], last["events"])
        else:
            _end(current, "censored", last["time"], last["events"], -1, _censored_by(status))
    return lives


def _single_growths(holder):
    """(events per growth, its carrier): one growth per occupant of the slot in this run."""
    rows = holder.rows
    occupants = [rows[0]] + [r for r in rows if r["kind"] == DAUGHTER]
    ends = [r for r in rows if r["kind"] == PARENT] + [rows[-1]]
    growths = []
    for j, (born, ended) in enumerate(zip(occupants, ends, strict=True)):
        growths.append(int(ended["age"]) - (int(born["age"]) if j == 0 else 0))
    return np.asarray(growths, dtype=np.int64), np.asarray(
        [int(r["occupant"]) for r in occupants], dtype=np.int64
    )


# ------------------------------------------------------------------ the fission pass alone


def fission_pass(spec, parents, lineages):
    """Diagnostic: the run's fission pass applied once to each supplied parent state.

    Lane k holds parents[k] (counts of the declared types) with its fission due, as the founder
    `0:0` of the world keyed by lineage word lineages[k] (the definition's seed, environment and
    branch), and the compiled fission pass splits it exactly as a run would: the partition from
    the parent's partition stream, the continuation from its continuation stream. Returns the
    pass's records per lane: first daughters [k, types], followed [k], similarities [k, 2], and
    the partition uniforms [k, places] when the definition records uniforms."""
    import dataclasses

    import jax

    from cells.core.devices import execution_device

    if spec.execution.mode != MODE:
        raise ConfigError("The fission pass is run on single-lineage definitions")
    parents = np.asarray(parents, dtype=np.int64)
    words = [int(w) for w in lineages]
    if parents.ndim != 2 or parents.shape[0] != len(words):
        raise ConfigError("One parent state per lineage word")
    count = spec.model.world.types.count
    if parents.shape[1] != count or np.any(parents < 0):
        raise ConfigError(f"Parents hold non-negative counts of the {count} types")
    if np.any(parents.sum(1) < 2) or np.any(parents.sum(1) > spec.execution.molecule_capacity):
        raise ConfigError("A parent holds from 2 molecules to the molecule capacity")
    specs = [
        dataclasses.replace(spec, execution=dataclasses.replace(spec.execution, lineage=w))
        for w in words
    ]
    structure, _, _ = _prepare(specs)
    device = execution_device(spec.execution.backend)
    layout = jax.device_put(_stack([model.layout(s) for s in specs]), device)
    founders = jax.device_put(np.stack([model.founder(s) for s in specs]), device)
    with jax.default_device(device):
        initial, _, split, _ = _compiled(structure, len(specs), layout)
        lanes = [_lane(initial(founders, layout), k) for k in range(len(specs))]
        for lane, parent in zip(lanes, parents, strict=True):
            lane["counts"] = np.zeros(structure.capacity, dtype=np.int64)
            lane["counts"][:count] = parent
            lane["size"] = np.int64(parent.sum())
            lane["status"] = np.int32(kernel.FISSION_DUE)
        _, record = split(jax.device_put(_restack(lanes), device), layout)
        host = jax.tree_util.tree_map(np.asarray, record)
    if not np.all(host.fired):
        raise AssertionError("Every supplied parent splits")
    out = {
        "first": host.first[:, :count],
        "followed": host.followed,
        "similarity": host.similarity,
        "daughters": host.daughters,
    }
    if structure.uniforms:
        out["partition_uniforms"] = host.places
        out["continuation_uniform"] = host.choice
    return out


# ------------------------------------------------------------------ every descendant


class _Life:
    """One life in every-descendant mode (host side): its birth lane, its records."""

    def __init__(self, lane, row_kind, record):
        self.lane = lane  # Its birth state (host lane dict).
        self.row_kind = row_kind  # START for the founder, DAUGHTER for a daughter.
        self.record = record  # Its lives-table row.
        self.steps = []
        self.splits = []
        self.end_row = None
        self.end_lane = None
        self.at_birth = False  # It never ran: extinct, or censored, at its birth.


def run_population(spec):
    """Every descendant of one world's founder (mode every_descendant), generation by generation."""
    import jax

    from cells.core.devices import execution_device

    if spec.execution.mode != EVERY_DESCENDANT:
        raise ConfigError(f"run_population runs {EVERY_DESCENDANT} worlds")
    structure, verdict, reports = _prepare([spec])
    count = spec.model.world.types.count
    width = spec.execution.lanes
    budget = spec.experiment.life_budget
    device = execution_device(spec.execution.backend)
    layout = jax.device_put(_stack([model.layout(spec)] * width), device)
    founders = np.zeros((width, structure.capacity), dtype=np.int64)
    founders[0] = model.founder(spec)
    lives = []
    with jax.default_device(device):
        initial, advance, split, compile_seconds = _compiled(structure, width, layout)
        sibling = _sibling(structure, width, layout)
        started = perf_counter()
        empty = _lane(initial(jax.device_put(np.zeros_like(founders), device), layout), 0)
        founder_lane = _lane(initial(jax.device_put(founders, device), layout), 0)
        founder = _Life(
            founder_lane,
            START,
            _life(
                founder_lane["occupant"],
                slot=-1,
                parent=-1,
                birth_kind="founder",
                time=founder_lane["time"],
                event=founder_lane["events"],
                fission=-1,
                generation=0,
                root=keys.FOUNDER,
                sub=0,
                size=founder_lane["size"],
            ),
        )
        generation, next_sub, used, chunks = [founder], 1, 0, 0
        budget_hit = False
        while generation:
            lives.extend(generation)
            alive = (kernel.RUNNING, kernel.FISSION_DUE)  # Born at the size: it splits at once.
            runnable = [g for g in generation if int(g.lane["status"]) in alive]
            for life in generation:
                if int(life.lane["status"]) not in alive:
                    _end_at_birth(life, count)
            if len(runnable) > budget - used:
                for life in runnable:
                    _end_at_birth(life, count, censored_by="budget")
                budget_hit = True
                break
            used += len(runnable)
            born = []
            for start in range(0, len(runnable), width):
                batch = runnable[start : start + width]
                chunks += _run_batch(
                    batch, empty, structure, layout, advance, split, sibling, count, width, born
                )
            numbers = keys.number_sublineages(
                [
                    (b["parent"].record["generation"] + 1, b["parent"].record["key"], b["index"])
                    for b in born
                    if b["starts"]
                ],
                next_sub,
            )
            next_sub += len(numbers)
            generation = []
            for b in sorted(born, key=lambda b: (b["parent"].record["key"], b["index"])):
                lane = b["lane"]
                if b["starts"]:
                    sub = numbers[(b["parent"].record["key"], b["index"])]
                    lane["next_carrier"] = np.int64(keys.key(sub, 1))
                    b["record"]["sublineage"] = sub
                generation.append(_Life(lane, DAUGHTER, b["record"]))
        jax.block_until_ready(layout)
        run_seconds = perf_counter() - started
    return _assemble_population(
        spec,
        structure,
        verdict,
        reports[0],
        lives,
        budget_hit,
        {
            "compile_seconds": compile_seconds,
            "run_seconds": run_seconds,
            "lanes": width,
            "chunks": chunks,
            "lives": len(lives),
            "scope": "wall time of every generation's batches on the device; compile apart",
        },
    )


def _end_at_birth(life, count, censored_by=None):
    """A life that never runs: extinct (no molecule), censored at the horizon, or by budget."""
    lane = life.lane
    status = int(lane["status"])
    record = life.record
    life.end_lane = lane
    life.at_birth = True
    life.end_row = _host_row(lane, count) | {"kind": END, "fission": 0}
    if censored_by is not None:
        _end(record, "censored", lane["time"], lane["events"], -1, censored_by)
    elif status == kernel.EXTINCT:
        _end(record, "extinct", lane["time"], lane["events"])  # Its fission: set later.
    elif status == kernel.COMPLETE:
        _end(record, "censored", lane["time"], lane["events"], -1, "horizon")
    else:
        raise AssertionError(f"A life born {kernel.STATUS[status]} runs")


def _run_batch(batch, empty, structure, layout, advance, split, sibling, count, width, born):
    """Run one batch of lives from their births to their ends; collect their daughters."""
    import jax

    lanes_host = [life.lane for life in batch] + [empty] * (width - len(batch))
    lanes = jax.device_put(_restack(lanes_host))
    holders = list(batch) + [None] * (width - len(batch))
    chunks = 0
    while True:
        status = np.asarray(lanes.status)
        if not (status == kernel.RUNNING).any():
            break
        lanes, out = advance(lanes, layout)
        chunks += 1
        _steps_into(out, structure, holders, width)
    before = lanes
    status = np.asarray(before.status)
    due = status == kernel.FISSION_DUE
    for i, life in enumerate(batch):
        lane = _lane(before, i)
        life.end_lane = lane
        if not due[i]:
            reason = kernel.STATUS[int(status[i])]
            row = _host_row(lane, count) | {"kind": END, "fission": 0}
            life.end_row = row
            if reason == "extinct":
                _end(life.record, "extinct", lane["time"], lane["events"])
            else:
                _end(life.record, "censored", lane["time"], lane["events"], -1, reason)
    if not due.any():
        return chunks
    after, record = split(before, layout)
    others = sibling(before, layout, record.first, record.followed)
    host = jax.tree_util.tree_map(np.asarray, record)
    for i, life in enumerate(batch):
        if not due[i]:
            continue
        k = int(host.after.fissions[i])
        entry = _split_entry(host, i, structure, count)
        life.splits.append(entry)
        life.end_row = _host_row(_lane(before, i), count) | {"kind": PARENT, "fission": k}
        _end(life.record, "divided", entry["time"], entry["events"], -1)  # Index set later.
        followed = int(entry["followed"])
        first = np.asarray(entry["first"])
        sizes = (int(first.sum()), int(life.end_row["size"]) - int(first.sum()))
        for d in (0, 1):
            lane = _lane(after, i) if d == followed else _lane(others, i)
            starts = d != followed and sizes[d] > 0
            born.append(
                {
                    "parent": life,
                    "index": d,
                    "lane": lane,
                    "starts": starts,
                    "record": _life(
                        entry["daughters"][d],
                        slot=-1,
                        parent=entry["parent"],
                        birth_kind="division",
                        time=entry["time"],
                        event=entry["events"],
                        fission=-1,  # Set with the fission table's order.
                        generation=life.record["generation"] + 1,
                        root=life.record["root"],
                        sub=life.record["sublineage"] if d == followed else -1,
                        size=sizes[d],
                    ),
                }
            )
    return chunks


def _assemble_population(spec, structure, verdict, report, lives, budget_hit, timings):
    """Every-descendant records: rows per life (birth, end), the fission table in lives order,
    the trace per life, and the lives table."""
    count = spec.model.world.types.count
    divided = [life for life in lives if life.splits]
    index = {id(life): k for k, life in enumerate(divided)}
    by_key = {life.record["key"]: life for life in lives}
    if len(by_key) != len(lives):
        raise AssertionError("Every life has its own key")
    for life in lives:
        record = life.record
        if record["end_reason"] == "divided":
            record["end_fission"] = index[id(life)]
        parent = by_key.get(record["parent"])
        if parent is not None:
            record["birth_fission"] = index[id(parent)]
            if life.at_birth and record["end_reason"] == "extinct":
                record["end_fission"] = record["birth_fission"]
    rows, splits, steps, growths, carriers = [], [], [], [], []
    for life in lives:
        first = _host_row(life.lane, count)
        kind = life.row_kind
        k = 0 if kind == START else int(life.lane["fissions"])
        rows.append(first | {"kind": kind, "fission": k})
        rows.append(life.end_row)
        splits.extend(life.splits)
        steps.extend(life.steps)
        growths.append(int(life.end_lane["age"]) - int(life.lane["age"]))
        carriers.append(life.record["key"])
    statuses = {life.record["censored_by"] for life in lives}
    status = "complete"
    for word in ("stalled", "event_limit", "budget"):
        if word in statuses:
            status = word
            break
    bound = {
        "generation_limit": spec.experiment.fissions,
        "life_budget": spec.experiment.life_budget,
        "lives_at_most": int(
            min(2 ** (spec.experiment.fissions + 1) - 1, 2 * spec.experiment.life_budget + 1)
        ),
        "growth": "2**g lives at generation g; at most life_budget lives run, and each that runs "
        "makes at most two daughters; a generation whose runnable lives exceed what is left of "
        "the budget is censored at its birth (never dropped), and the run ends",
        "lanes": spec.execution.lanes,
    }
    return _assemble(
        spec,
        structure,
        verdict,
        report,
        status,
        rows,
        splits,
        steps,
        [life.record for life in lives],
        (np.asarray(growths, dtype=np.int64), np.asarray(carriers, dtype=np.int64)),
        keys.qualifier(spec.fingerprint, "fresh"),
        "fresh",
        lives[-1].end_lane,
        timings | {"events": sum(len(c) for c, _, _ in steps)},
        bound=bound,
        slot=-1,
    )


# ------------------------------------------------------------------ assembling the records


LIFE_COLUMNS = {
    "life_key": ("key", np.int64),
    "life_slot": ("slot", np.int64),
    "life_parent": ("parent", np.int64),
    "life_birth_kind": ("birth_kind", keys.TEXT),
    "life_birth_time": ("birth_time", np.float64),
    "life_birth_event": ("birth_event", np.int64),
    "life_birth_fission": ("birth_fission", np.int64),
    "life_end_reason": ("end_reason", keys.TEXT),
    "life_censored_by": ("censored_by", keys.TEXT),
    "life_end_time": ("end_time", np.float64),
    "life_end_event": ("end_event", np.int64),
    "life_end_fission": ("end_fission", np.int64),
    "life_generation": ("generation", np.int64),
    "life_root": ("root", np.int64),
    "life_sublineage": ("sublineage", np.int64),
    "life_size_at_birth": ("size_at_birth", np.int64),
}


def _assemble(
    spec,
    structure,
    verdict,
    report,
    status,
    rows,
    splits,
    steps,
    lives,
    growths,
    qualifier,
    start,
    final,
    timings,
    *,
    bound=None,
    slot=0,
):
    world = spec.model.world
    count = world.types.count
    lay = model.layout(spec)
    log_theta, log_factorial = lay.log_theta[:count], lay.log_factorial

    def column(name, dtype=None):
        return np.asarray([r[name] for r in rows], dtype=dtype)

    counts = column("counts", np.int64)
    sizes = column("size", np.int64)
    phi = np.asarray(
        [
            ledger.log_weight(c, s, log_theta, log_factorial, np)
            for c, s in zip(counts, sizes, strict=True)
        ]
    )
    founder_phi = ledger.log_weight(
        np.asarray(world.founder, dtype=np.int64),
        np.int64(sum(world.founder)),
        log_theta,
        log_factorial,
        np,
    )
    phi_0 = phi[0] if start == "fresh" else founder_phi
    heat, work, sink = (
        column("heat", np.float64),
        column("work", np.float64),
        column("sink", np.float64),
    )
    residual = ledger.residual(heat, phi, phi_0, work, sink)
    tolerance = ledger.closure_tolerance(
        column("heat_magnitude"), phi, phi_0, column("work_magnitude"), column("sink_magnitude")
    )
    passive = verdict["energy_role"] == "passive"
    worst = int(np.argmax(np.abs(residual) - tolerance))
    closes = bool(np.all(np.abs(residual) <= tolerance))
    refused = None
    if passive and not closes:
        refused = (
            f"the ledger of a passive law does not close: residual {residual[worst]:.3g} k_BT at "
            f"row {worst} exceeds its rounding bound {tolerance[worst]:.3g}"
        )
        status = "refused"
    closure = {
        "law_energy_role": verdict["energy_role"],
        "checked": passive,
        "holds": closes,
        "max_abs_residual_kT": float(np.max(np.abs(residual))),
        "tolerance_rtol": ledger.RTOL,
        "refused": refused,
        "reads": "for a passive law the residual is rounding; for a driven law it is the "
        "unsourced cycle work, reported and never closed",
    }
    one = lambda a: a[:, None]  # noqa: E731  The assembly axis (one slot).
    row_arrays = {
        "row_time": column("time", np.float64),
        "row_event": column("events", np.int64),
        "row_kind": column("kind", np.int8),
        "row_fission": column("fission", np.int64),
        "assembly_count": counts[:, :, None],
        "joined_total": column("joined", np.int64)[:, :, None],
        "left_total": column("left", np.int64)[:, :, None],
        "discarded_total": column("discarded", np.int64)[:, :, None],
        "exchange_heat_kT": one(heat),
        "fission_work_kT": one(work),
        "discarded_free_energy_kT": one(sink),
        "log_weight": one(phi),
        "ledger_residual_kT": one(residual),
        "occupant": one(column("occupant", np.int64)),
        "generation": one(column("generation", np.int64)),
    }
    fission_arrays = {
        "fission_time": np.asarray([s["time"] for s in splits], dtype=np.float64),
        "fission_slot": np.full(len(splits), slot, dtype=np.int64),
        "fission_parent": np.asarray([s["parent"] for s in splits], dtype=np.int64),
        "fission_daughters": np.asarray([s["daughters"] for s in splits], dtype=np.int64).reshape(
            -1, 2
        ),
        "fission_followed": np.asarray([s["followed"] for s in splits], dtype=np.int64),
        "fission_split": np.asarray([s["first"] for s in splits], dtype=np.int64).reshape(
            -1, count
        ),
        "fission_similarity": np.asarray(
            [s["similarity"] for s in splits], dtype=np.float64
        ).reshape(-1, 2),
        "fission_partition_counter": np.zeros(len(splits), dtype=np.int64),
    }
    trace = {}
    if spec.experiment.trace:
        trace = {
            "event_time": np.concatenate([t for _, t, _ in steps]) if steps else np.zeros(0),
            "event_channel": (
                np.concatenate([c for c, _, _ in steps]).astype(np.int32)
                if steps
                else np.zeros(0, dtype=np.int32)
            ),
            "events_per_growth": growths[0],
            "growth_carrier": growths[1],
        }
    diagnostics = {}
    if structure.uniforms:
        diagnostics = {
            "event_uniforms": (
                np.concatenate([u for _, _, u in steps]) if steps else np.zeros((0, 2))
            ),
            "partition_uniforms": np.asarray(
                [s["places"] for s in splits], dtype=np.float64
            ).reshape(-1, structure.molecule_capacity),
            "continuation_uniform": np.asarray([s["choice"] for s in splits], dtype=np.float64),
        }
    life_arrays = {
        name: np.asarray([life[key] for life in lives], dtype=dtype)
        for name, (key, dtype) in LIFE_COLUMNS.items()
    }
    return LineageRun(
        spec=spec,
        structure=structure,
        verdict=verdict,
        world_report=report,
        status=status,
        rows=row_arrays,
        fissions=fission_arrays,
        trace=trace,
        diagnostics=diagnostics,
        closure=closure,
        lives=life_arrays,
        qualifier=qualifier,
        start=start,
        final=final,
        timings=timings,
        bound=bound,
    )
