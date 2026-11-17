"""The runner of version 2: one world per lane, event-driven (its own runner shape).

    run(spec)          one world, from its founder to the end of its lifecycle (kernel.py)
    run_lanes(specs)   several worlds of one structure, as lanes of one compiled program

The host loop of one batch of lanes: advance one chunk of events at a time until no lane is
RUNNING. A lane that is not RUNNING changes nothing and draws nothing, so the chunk size and the
lane batch change no value.

**Before a run,** the kernel's check runs on its generic probe (balance.verdict) and on the
world's own data (balance.world_report). Either refuses a world whose rates fail
ln a⁺ − ln a⁻ = −ΔF + w.

**Records** (records.py declares them):
- rows: the start, every `row_every_events` committed events, each observation time (the state
  after the last event at or before it), and the end, in time order;
- at each row, the counts of every place, the channels' cumulative counts, the held reservoirs'
  net supplies, and the cumulative heat Q and reservoir work W;
- the end row's time is the horizon when the state held to it (complete, inert), and the last
  event's otherwise. An observation time after the last event is filled from the final state when
  that state holds (complete, inert, extinct); a run stopped otherwise leaves it unobserved, and
  the run says how many (`observations_censored`).

The counts at a row are rebuilt on the host from the channels' cumulative counts, in exact
integers. At the end they must equal the lane's own counts: a run where they differ is a fault and
raises. Q and W are the device's own cumulative values at each row's event.

**The ledger** (ledger.py) is closed at every row: F(n_t) − F(n_0) = W − Q, to rounding. Every law
of this family is passive, so a run whose books do not close is refused: its status says so,
check() raises, and nothing is repaired.
"""

from dataclasses import dataclass, field
from time import perf_counter

import numpy as np

from cells.core.specs import ConfigError
from cells.models.assembly_lineages import keys
from cells.models.assembly_lineages_v2 import MODE, balance, kernel, ledger, model

ROW_KINDS = ("start", "periodic", "end", "observed")
START, PERIODIC, END, OBSERVED = range(4)
_COMPILED = {}
HELD_TO_HORIZON = ("complete", "inert")
HOLDS = ("complete", "inert", "extinct")  # The final state holds after the last event.


class LedgerRefused(ConfigError):
    """A run whose ledger did not close at a saved row."""


@dataclass
class WorldRun:
    spec: object
    structure: object
    verdict: dict
    world_report: dict
    status: str
    rows: dict
    trace: dict
    diagnostics: dict
    closure: dict
    qualifier: str
    final: dict  # The last lane state (host arrays).
    timings: dict = field(default_factory=dict)

    def check(self):
        """Raise if the run was refused (a ledger that did not close)."""
        if self.closure["refused"]:
            raise LedgerRefused(self.closure["refused"])
        return self


def _compiled(structure, lanes, layout):
    """(initial, advance, compile seconds) of one structure for `lanes` lanes."""
    import jax

    key = (structure, lanes)
    if key not in _COMPILED:
        started = perf_counter()
        program = kernel.program(structure)
        founders = jax.ShapeDtypeStruct((lanes, structure.places), np.int64)
        initial = program.initial.lower(founders, layout).compile()
        shapes = jax.eval_shape(program.initial, founders, layout)
        advance = program.advance.lower(shapes, layout).compile()
        _COMPILED[key] = (initial, advance, perf_counter() - started)
    return _COMPILED[key]


def _stack(trees):
    import jax

    return jax.tree_util.tree_map(lambda *xs: np.stack([np.asarray(x) for x in xs]), *trees)


def _lane(tree, i):
    """Lane i of a stacked lane tree, as {field: host value} (empty states kept as ())."""
    import jax

    out = {}
    for name in kernel.Lane._fields:
        value = getattr(tree, name)
        if isinstance(value, tuple) and not value:
            out[name] = ()
        else:
            out[name] = jax.tree_util.tree_map(lambda a: np.asarray(a)[i].copy(), value)
    return out


def changes(layout, structure):
    """(count change [2R, P], supply change [2R, P]) of each channel, in exact integers: a forward
    moves +ν over the finite places, a reverse −ν; a held place's supply moves −ν."""
    R, P = structure.steps, structure.places
    count = np.zeros((2 * R, P), dtype=np.int64)
    supply = np.zeros((2 * R, P), dtype=np.int64)
    for r in range(R):
        for k in range(kernel.ENTRIES):
            a, b = layout.entry_alpha[r, k], layout.entry_beta[r, k]
            if a + b == 0:
                continue
            place = layout.entry_place[r, k]
            if layout.entry_held[r, k]:
                supply[r, place] -= b - a
                supply[R + r, place] -= a - b
            else:
                count[r, place] += b - a
                count[R + r, place] += a - b
    return count, supply


class _World:
    """One lane's records (host side)."""

    def __init__(self, lane, row_every, observations):
        self.start = lane
        self.row_every = row_every
        self.rows = []  # (kind, event index, time, fired [2R], Q, |Q|, W, |W|)
        self.fired = np.zeros_like(lane["fired"])
        self.events = 0
        self.channels, self.times, self.draws = [], [], []
        self.observations = list(observations)
        self.booked = (0.0, 0.0, 0.0, 0.0)  # Q, |Q|, W, |W| after the last event taken.

    def observe(self, until):
        """Observation rows for every pending time before `until` (the next event's time)."""
        while self.observations and self.observations[0] < until:
            t = self.observations.pop(0)
            self.rows.append((OBSERVED, self.events, t, self.fired.copy(), *self.booked))

    def take(self, channel, time, heat, heat_mag, work, work_mag, draws, R):
        """The committed events of one chunk, in order (channel: the kernel's signed code)."""
        index = np.where(channel > 0, channel - 1, R + (-channel - 1)).astype(np.int64)
        for k in range(len(index)):
            self.observe(time[k])
            self.booked = (heat[k], heat_mag[k], work[k], work_mag[k])
            self.events += 1
            self.fired[index[k]] += 1
            if self.events % self.row_every == 0:
                self.rows.append(
                    (PERIODIC, self.events, time[k], self.fired.copy(), heat[k], heat_mag[k],
                     work[k], work_mag[k])
                )  # fmt: skip
        self.channels.append(channel)
        self.times.append(time)
        if draws is not None:
            self.draws.append(draws)


def run(spec):
    """One world, from its founder to the end of its lifecycle."""
    return run_lanes([spec])[0]


def run_lanes(specs):
    """Several worlds of one structure, as lanes of one program; one WorldRun each."""
    import jax

    from cells.core.devices import execution_device

    if any(s.execution.mode != MODE for s in specs):
        raise ConfigError(f"run_lanes runs {MODE} worlds")
    structures = {model.structure(s) for s in specs}
    if len(structures) != 1:
        raise ConfigError("Lanes share one structure (capacities, laws, conventions, recording)")
    (structure,) = structures
    if len({s.execution.backend for s in specs}) != 1:
        raise ConfigError("Lanes share one backend")
    kernel.refuse_unknown(structure)
    verdict = balance.verdict()  # Refuses a kernel that fails the identity on its probe.
    reports = [balance.world_report(s) for s in specs]
    device = execution_device(specs[0].execution.backend)
    host_layouts = [model.layout(s) for s in specs]
    layout = jax.device_put(_stack(host_layouts), device)
    founders = jax.device_put(np.stack([model.founder(s) for s in specs]), device)
    L, R = len(specs), structure.steps
    with jax.default_device(device):
        initial, advance, compile_seconds = _compiled(structure, L, layout)
        started = perf_counter()
        lanes = initial(founders, layout)
        holders = [
            _World(_lane(lanes, i), s.experiment.row_every_events, s.experiment.observation_times_s)
            for i, s in enumerate(specs)
        ]
        chunks = 0
        while True:
            status = np.asarray(lanes.status)
            if not (status == kernel.RUNNING).any():
                break
            lanes, out = advance(lanes, layout)
            chunks += 1
            committed = np.asarray(out.committed)
            if not committed.any():
                continue
            host = jax.tree_util.tree_map(np.asarray, out)
            for i in range(L):
                mask = committed[:, i]
                if mask.any():
                    holders[i].take(
                        host.channel[mask, i],
                        host.time[mask, i],
                        host.heat[mask, i],
                        host.heat_magnitude[mask, i],
                        host.work[mask, i],
                        host.work_magnitude[mask, i],
                        host.uniforms[mask, i] if structure.uniforms else None,
                        R,
                    )
        jax.block_until_ready(lanes)
        run_seconds = perf_counter() - started
    results = []
    for i, spec in enumerate(specs):
        final = _lane(lanes, i)
        events = holders[i].events
        timings = {
            "compile_seconds": compile_seconds,
            "run_seconds": run_seconds,
            "lanes": L,
            "chunks": chunks,
            "events": events,
            "events_per_second": events / run_seconds if run_seconds > 0 else None,
            "scope": "wall time of the whole lane batch on its device; compile apart (cached per "
            "structure and lane count)",
        }
        results.append(
            _assemble(spec, structure, host_layouts[i], verdict, reports[i], holders[i], final, timings)
        )
    return results


def _assemble(spec, structure, layout, verdict, report, holder, final, timings):
    world = spec.model.world
    status = kernel.STATUS[int(final["status"])]
    count_change, supply_change = changes(layout, structure)
    start = holder.start
    places = len(world.places)
    end_time = spec.experiment.time_horizon_s if status in HELD_TO_HORIZON else float(final["time"])
    if status in HOLDS:
        holder.observe(np.inf)  # The final state holds: every remaining time sees it.
    censored = len(holder.observations)
    zero_fired = np.zeros_like(holder.fired)
    rows = [(START, 0, 0.0, zero_fired, 0.0, 0.0, 0.0, 0.0)]
    rows += holder.rows
    rows.append(
        (END, holder.events, end_time, holder.fired.copy(), float(final["heat"]),
         float(final["heat_magnitude"]), float(final["work"]), float(final["work_magnitude"]))
    )  # fmt: skip
    fired = np.stack([r[3] for r in rows]).astype(np.int64)
    counts = start["counts"][None, :] + fired @ count_change
    supplied = fired @ supply_change
    if not np.array_equal(counts[-1], final["counts"]) or not np.array_equal(
        supplied[-1], final["supplied"]
    ):
        raise AssertionError(
            "The rows rebuilt from the channels' counts differ from the lane's own state: a fault"
        )
    tables = model.tables(spec)
    f = np.asarray(
        [ledger.free_energy(c, tables, world.terms, layout.terms) for c in counts], dtype=np.float64
    )
    heat = np.asarray([r[4] for r in rows], dtype=np.float64)
    heat_mag = np.asarray([r[5] for r in rows], dtype=np.float64)
    work = np.asarray([r[6] for r in rows], dtype=np.float64)
    work_mag = np.asarray([r[7] for r in rows], dtype=np.float64)
    residual = ledger.residual(heat, work, f, f[0])
    tolerance = ledger.closure_tolerance(heat_mag, work_mag, f, f[0])
    closes = bool(np.all(np.abs(residual) <= tolerance))
    worst = int(np.argmax(np.abs(residual) - tolerance))
    refused = None
    if not closes:
        refused = (
            f"the ledger does not close: residual {residual[worst]:.3g} k_BT at row {worst} "
            f"exceeds its rounding bound {tolerance[worst]:.3g}"
        )
        status = "refused"
    closure = {
        "checked": True,
        "holds": closes,
        "max_abs_residual_kT": float(np.max(np.abs(residual))),
        "tolerance_rtol": ledger.RTOL,
        "refused": refused,
        "reads": "every law of this family is passive: the residual is rounding, and a run whose "
        "books do not close is refused",
        "observations_censored": censored,
    }
    R_declared = len(world.steps)
    declared = np.r_[np.arange(R_declared), structure.steps + np.arange(R_declared)]
    row_arrays = {
        "row_time": np.asarray([r[2] for r in rows], dtype=np.float64),
        "row_event": np.asarray([r[1] for r in rows], dtype=np.int64),
        "row_kind": np.asarray([r[0] for r in rows], dtype=np.int8),
        "place_count": counts[:, :places],
        "reservoir_supplied": supplied[:, :places],
        "channel_fired": fired[:, declared],
        "event_heat_kT": heat,
        "reservoir_work_kT": work,
        "free_energy_kT": f,
        "ledger_residual_kT": residual,
    }
    trace = {}
    if spec.experiment.trace:
        trace = {
            "event_time": np.concatenate(holder.times) if holder.times else np.zeros(0),
            "event_channel": np.concatenate(holder.channels).astype(np.int32)
            if holder.channels
            else np.zeros(0, dtype=np.int32),
        }
    diagnostics = {}
    if structure.uniforms:
        diagnostics["event_uniforms"] = (
            np.concatenate(holder.draws) if holder.draws else np.zeros((0, 2))
        )
    qualifier = keys.qualifier(spec.fingerprint, "fresh", None)
    return WorldRun(
        spec=spec,
        structure=structure,
        verdict=verdict,
        world_report=report,
        status=status,
        rows=row_arrays,
        trace=trace,
        diagnostics=diagnostics,
        closure=closure,
        qualifier=qualifier,
        final=final,
        timings=timings,
    )
