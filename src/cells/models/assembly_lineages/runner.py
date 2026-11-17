"""The lineage runner: the family's own runner shape (event-driven, not fixed-step).

run(spec) runs one world's lineage; run_lanes(specs) runs several worlds of one structure as
lanes of one compiled program (each lane's values its own). The host loop:

    lanes = initial(founders, layout)
    repeat:  advance one chunk of events (a lane that is not RUNNING waits and draws nothing);
             if a lane is FISSION_DUE, run the fission pass (a no-op for the others);
    until no lane is RUNNING or FISSION_DUE.

It keeps the saved rows (the founder; per fission the parent before the split and the followed
daughter after it, both at the fission's time; and the end state when the lineage stops between
fissions), the fission table and the event trace, then closes the ledger at every row
(ledger.py). A passive law's run whose ledger does not close is refused: its status says so, and
check() raises. Nothing is repaired, and failed runs keep their records.

Timings: compile (once per structure and lane count, cached) apart from the run, and the event
rate of the run itself, measured, never presumed.
"""

from dataclasses import dataclass, field
from time import perf_counter

import numpy as np

from cells.core.specs import ConfigError
from cells.models.assembly_lineages import balance, factors, kernel, ledger, model

ROW_KINDS = ("start", "parent", "daughter", "end")
_COMPILED = {}


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
    timings: dict = field(default_factory=dict)

    def check(self):
        """Raise if the run was refused (a passive law's ledger that did not close)."""
        if self.closure["refused"]:
            raise LedgerRefused(self.closure["refused"])
        return self


def _compiled(structure, founders, layout):
    import jax

    key = (structure, founders.shape[0])
    if key not in _COMPILED:
        started = perf_counter()
        program = kernel.program(structure)
        initial = program.initial.lower(founders, layout).compile()
        shapes = jax.eval_shape(program.initial, founders, layout)
        advance = program.advance.lower(shapes, layout).compile()
        split = program.split.lower(shapes, layout).compile()
        _COMPILED[key] = (initial, advance, split, perf_counter() - started)
    return _COMPILED[key]


def _stack(trees):
    import jax

    return jax.tree_util.tree_map(lambda *xs: np.stack([np.asarray(x) for x in xs]), *trees)


def _host_row(row, lane, count):
    """One lane's Row as host values (declared types only)."""
    take = lambda a: np.asarray(a)[lane]  # noqa: E731
    out = {name: take(getattr(row, name)) for name in row._fields}
    for name in ("counts", "joined", "left", "discarded"):
        out[name] = out[name][:count]
    return out


def run(spec):
    """One world's lineage."""
    return run_lanes([spec])[0]


def run_lanes(specs):
    """Several worlds of one structure, as lanes of one program; one LineageRun each."""
    import jax

    from cells.core.devices import execution_device

    structures = {model.structure(s) for s in specs}
    if len(structures) != 1:
        raise ConfigError("Lanes share one structure (capacities, laws, rules and recording)")
    (structure,) = structures
    if len({s.execution.backend for s in specs}) != 1:
        raise ConfigError("Lanes share one backend")
    device = execution_device(specs[0].execution.backend)
    verdict = balance.verdict(structure.factor)  # Refuses a failing law declared passive.
    law = None if structure.factor is None else factors.resolve(structure.factor)
    reports = [
        balance.world_report(s) if law is not None and law.energy_role == "driven" else None
        for s in specs
    ]
    layout = jax.device_put(_stack([model.layout(s) for s in specs]), device)
    founders = jax.device_put(np.stack([model.founder(s) for s in specs]), device)
    with jax.default_device(device):
        initial, advance, split, compile_seconds = _compiled(structure, founders, layout)
        started = perf_counter()
        lanes = initial(founders, layout)
        count = [s.model.world.types.count for s in specs]
        L = len(specs)
        rows = [
            [_host_row(kernel.row(lanes), i, count[i]) | {"kind": 0, "fission": 0}]
            for i in range(L)
        ]
        steps = [[] for _ in range(L)]
        splits = [[] for _ in range(L)]
        chunks = 0
        while True:
            lanes, out = advance(lanes, layout)
            chunks += 1
            committed = np.asarray(out.committed)
            if committed.any():
                channel, time = np.asarray(out.channel), np.asarray(out.time)
                draws = np.asarray(out.uniforms) if structure.uniforms else None
                for i in range(L):
                    mask = committed[:, i]
                    if mask.any():
                        steps[i].append(
                            (
                                channel[mask, i],
                                time[mask, i],
                                None if draws is None else draws[mask, i],
                            )
                        )
            status = np.asarray(lanes.status)
            if (status == kernel.FISSION_DUE).any():
                lanes, record = split(lanes, layout)
                fired = np.asarray(record.fired)
                host = jax.tree_util.tree_map(np.asarray, record)
                for i in np.flatnonzero(fired):
                    k = len(splits[i]) + 1
                    splits[i].append(
                        {
                            "parent": host.parent[i],
                            "daughters": host.daughters[i],
                            "followed": host.followed[i],
                            "first": host.first[i][: count[i]],
                            "similarity": host.similarity[i],
                            "places": None if not structure.uniforms else host.places[i],
                            "choice": None if not structure.uniforms else host.choice[i],
                        }
                    )
                    rows[i].append(
                        _host_row(record.before, i, count[i]) | {"kind": 1, "fission": k}
                    )
                    rows[i].append(_host_row(record.after, i, count[i]) | {"kind": 2, "fission": k})
                status = np.asarray(lanes.status)
            if not ((status == kernel.RUNNING) | (status == kernel.FISSION_DUE)).any():
                break
        jax.block_until_ready(lanes)
        run_seconds = perf_counter() - started
    final = jax.tree_util.tree_map(np.asarray, kernel.row(lanes))
    results = []
    for i, spec in enumerate(specs):
        end = _host_row(final, i, count[i])
        last = rows[i][-1]
        if (int(end["events"]), int(end["fissions"])) != (
            int(last["events"]),
            int(last["fissions"]),
        ):
            rows[i].append(end | {"kind": 3, "fission": 0})
        events = sum(len(c) for c, _, _ in steps[i])
        results.append(
            _assemble(
                spec,
                structure,
                verdict,
                reports[i],
                kernel.STATUS[int(end["status"])],
                rows[i],
                splits[i],
                steps[i],
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


def _assemble(spec, structure, verdict, report, status, rows, splits, steps, timings):
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
    heat, work, sink = (
        column("heat", np.float64),
        column("work", np.float64),
        column("sink", np.float64),
    )
    residual = ledger.residual(heat, phi, phi[0], work, sink)
    tolerance = ledger.closure_tolerance(
        column("heat_magnitude"), phi, phi[0], column("work_magnitude"), column("sink_magnitude")
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
    parents = [r for r in rows if r["kind"] == 1]
    fission_arrays = {
        "fission_time": np.asarray([r["time"] for r in parents], dtype=np.float64),
        "fission_slot": np.zeros(len(splits), dtype=np.int64),
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
    growths = [int(r["age"]) for r in parents]
    if rows[-1]["kind"] == 3:
        growths.append(int(rows[-1]["age"]))
    trace = {}
    if spec.experiment.trace:
        trace = {
            "event_time": np.concatenate([t for _, t, _ in steps]) if steps else np.zeros(0),
            "event_channel": (
                np.concatenate([c for c, _, _ in steps]).astype(np.int32)
                if steps
                else np.zeros(0, dtype=np.int32)
            ),
            "events_per_growth": np.asarray(growths, dtype=np.int64),
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
        timings=timings,
    )
