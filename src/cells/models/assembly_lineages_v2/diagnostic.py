"""The diagnostic record of a run (§0.2d item 10.5): absent by default, written when the experiment
declares `diagnostic: true`, as diagnostic.json and diagnostic.npz beside the bundle's records.

It records every draw with its address (domain, carrier key, counter), its uniforms and its fate
(committed event, discarded at a schedule time, or the draw that ended the run); every schedule
draw; the channel table; each step event with its group, its heat and reservoir work, the changed
vesicle's counts after it and the pool after it; each shear event's attempts with their uniforms
(the used prefix), and its pool and living slots after it; each transfer event with its draws by
slot, and its pool and living slots after it; the initial and final states; the world's key and
the end reason; and the environment record (§0.2d item 9). An attempt states the heat and reservoir
work of its daughters' births beyond sigma_max, whose lysis rows book them (attribution, not a
second booking). OL1's `event_uniforms` keeps its meaning (committed events only). None of this
changes a run: the record is written from the run's own state, after it.

The uniforms are recomputed on the host from each draw's address, by the run's own derivation; a
committed draw's equal the device's own record when the experiment also records uniforms (checked).
"""

import numpy as np

from cells.models.assembly_lineages_v2 import division, kernel, streams

FATES = ("committed", "discarded_at_schedule", "ended_run")
COMMITTED, DISCARDED, ENDED = range(3)
USES = ("gap", "transfer")


def partitionable():
    import jax

    return bool(jax.config.jax_threefry_partitionable)


def environment():
    return {
        "jax_threefry_partitionable": partitionable(),
        "reads": "§0.2d item 9: a run refuses to start with the flag off",
    }


def regenerate(base_key, domain, addresses, width):
    """[len(addresses), width] uniforms of each (carrier key, counter) on `domain`'s streams."""
    import jax

    out = np.full((len(addresses), width), np.nan)
    by_key = {}
    for n, (key, counter) in enumerate(addresses):
        by_key.setdefault(int(key), []).append((n, int(counter)))
    for key, items in by_key.items():
        stream = streams.stream_key_data(base_key, key, domain)
        counters = np.asarray([c for _, c in items], dtype=np.int64)
        values = jax.vmap(lambda c, s=stream: streams.uniforms(s, c, width))(counters)
        out[[n for n, _ in items]] = np.asarray(values)
    return out


def _split(world, counts):
    membrane, inside = division.vesicle_places(world)
    vesicle = np.concatenate((membrane, inside))
    pool = np.asarray(
        [i for i, p in enumerate(world.places) if p.phase == "pool" and not p.held], dtype=np.int64
    )
    counts = np.asarray(counts)
    return counts[..., vesicle], counts[..., pool]


def build(spec, layout, holder, status, start_counts, final_counts, world_key, device_draws):
    """(diagnostic.json's body, diagnostic.npz's arrays) of a single-lineage run."""
    world = spec.model.world
    P = len(world.places)
    draws = list(holder.diagnostic["draws"])
    addresses = [(key, counter) for key, counter, _ in draws]
    uniforms = regenerate(layout.base_key, "events", addresses, 2)
    fates = np.asarray([fate for *_, fate in draws], dtype=np.int8)
    if device_draws is not None and len(device_draws):
        if not np.array_equal(uniforms[fates == COMMITTED], np.asarray(device_draws)):
            raise AssertionError("The recomputed draws differ from the device's record: a fault")
    # Step events: counts after each one rebuilt in exact integers, with each split's jump.
    channels = np.concatenate(holder.channels) if holder.channels else np.zeros(0, np.int32)
    times = np.concatenate(holder.times) if holder.times else np.zeros(0)
    heat = np.concatenate(holder.diagnostic["heat"]) if holder.channels else np.zeros(0)
    work = np.concatenate(holder.diagnostic["work"]) if holder.channels else np.zeros(0)
    R = layout.entry_place.shape[0]
    index = np.where(channels > 0, channels - 1, R + (-channels - 1)).astype(np.int64)
    from cells.models.assembly_lineages_v2 import runner

    change, _ = runner.changes(layout, _shape(layout))
    after = start_counts[None, :] + np.cumsum(change[index], axis=0)
    for at, jump in holder.diagnostic["jumps"]:  # a split after `at` events
        after[at:] += jump
    vesicle_after, pool_after = _split(world, after[:, :P])
    lysed = np.zeros(len(channels), dtype=bool)
    if status == "lysed" and len(channels) and not holder.diagnostic["lysed_at_stop"]:
        lysed[-1] = True
    arrays = {
        "draw_domain": np.ones(len(draws), dtype=np.int8),
        "draw_key": np.asarray([k for k, _ in addresses], dtype=np.int64),
        "draw_counter": np.asarray([c for _, c in addresses], dtype=np.int64),
        "draw_uniforms": uniforms,
        "draw_fate": fates,
        "event_time": times,
        "event_group": np.zeros(len(channels), dtype=np.int32),
        "event_channel": channels.astype(np.int32),
        "event_lysed": lysed,
        "event_heat_kT": np.diff(np.concatenate(([0.0], heat))),
        "event_reservoir_work_kT": np.diff(np.concatenate(([0.0], work))),
        "event_vesicle_after": vesicle_after,
        "event_pool_after": pool_after,
    }
    sched = holder.diagnostic["schedule_draws"]
    arrays |= {
        "schedule_draw_index": np.asarray([d[0] for d in sched], dtype=np.int64),
        "schedule_draw_counter": np.asarray([d[1] for d in sched], dtype=np.int64),
        "schedule_draw_uniform": np.asarray([d[2] for d in sched], dtype=np.float64),
        "schedule_draw_use": np.asarray([USES.index(d[3]) for d in sched], dtype=np.int8),
        "schedule_draw_time": np.asarray([d[4] for d in sched], dtype=np.float64),
    }
    shear, blocks = _shear_events(spec, layout, holder)
    arrays["attempt_uniforms"] = blocks
    start_v, start_p = _split(world, start_counts[:P])
    final_v, final_p = _split(world, final_counts[:P])
    body = {
        "format": "cells.assembly_lineages.diagnostic@1",
        "fates": list(FATES),
        "schedule_uses": list(USES),
        "groups": "single lineage: one group, the slot's (event_group 0): every declared step",
        "channels": {"lineage": kernel.channel_table(world)},
        "event_channel": "the kernel's signed code: +(r+1) step r's forward, -(r+1) its reverse",
        "vesicle_places": [
            world.places[i].name for i in np.concatenate(division.vesicle_places(world))
        ],
        "pool_places": [p.name for p in world.places if p.phase == "pool" and not p.held],
        "shear_events": shear,
        "transfer_events": [],
        "states": {
            "initial": {
                "slots": [{"slot": 0, "key": 0, "counts": start_v.tolist()}],
                "pool": start_p.tolist(),
            },
            "final": {
                "slots": [
                    {"slot": 0, "key": int(holder.diagnostic["key"]), "counts": final_v.tolist()}
                ],
                "pool": final_p.tolist(),
            },
        },  # fmt: skip
        "world": world_key,
        "end": status,
        "environment": environment(),
        "uniforms": "recomputed on the host from each draw's address (domain, key, counter); a "
        "committed draw's equal the device's record when experiment.uniforms is on (checked)",
    }
    return body, arrays


def _shape(layout):
    """A Structure-like holder of the step and place capacities, for runner.changes."""

    class Shape:
        steps = layout.entry_place.shape[0]
        places = layout.place_held.shape[0]

    return Shape()


def _shear_events(spec, layout, holder):
    """Each stop's attempts as the record states them, and their concatenated uniform blocks."""
    world = spec.model.world
    membrane, inside = division.vesicle_places(world)
    vesicle = np.concatenate((membrane, inside))
    pool = [i for i, p in enumerate(world.places) if p.phase == "pool" and not p.held]
    events, blocks, offset = {}, [], 0
    for attempt, _ in holder.attempts:
        n = int(attempt.parent_counts[membrane].sum())
        n_l = int(attempt.parent_counts[inside].sum())
        entry = {"slot": 0, "key": int(attempt.parent), "counter": int(attempt.counter),
                 "outcome": attempt.outcome, "uniforms_offset": offset,
                 "uniforms_count": 0}  # fmt: skip
        if attempt.counter >= 0:
            size = n + attempt.k + n_l
            blocks.append(division.block(layout.base_key, attempt.parent, attempt.counter, size))
            entry["uniforms_count"], offset = size, offset + size
        if attempt.outcome == "split":
            entry["daughters"] = [
                {"key": int(key), "slot": 0 if j == attempt.followed else None,
                 "counts": attempt.daughters[j][vesicle].tolist(),
                 "lysed_at_birth": bool(attempt.lysed[j])}
                for j, key in enumerate(attempt.keys)
            ]  # fmt: skip
            entry["followed"] = int(attempt.followed)
            entry["shear_work_kT"] = attempt.shear_work
            entry["sink_kT"] = attempt.sink
            entry["heat_kT"] = 0.0
            entry["reservoir_work_kT"] = 0.0
            entry["pool_after"] = attempt.daughters[attempt.followed][pool].tolist()
        stop = events.setdefault(
            (attempt.time, attempt.schedule),
            {"time": attempt.time, "schedule": attempt.schedule, "not_admitted": [],
             "attempts": []},
        )  # fmt: skip
        if attempt.outcome in ("refused_stress", "refused_volume"):
            stop["not_admitted"].append(0)
        stop["attempts"].append(entry)
        # The event's state after it: the followed daughter in slot 0 (none when it lysed at
        # birth, which ends the run), or the parent unchanged; and the pool.
        if attempt.outcome == "split":
            after = attempt.daughters[attempt.followed]
            living = not attempt.lysed[attempt.followed]
            key = int(attempt.keys[attempt.followed])
        else:
            after, living, key = attempt.parent_counts, True, int(attempt.parent)
        stop["pool_after"] = np.asarray(after)[pool].tolist()
        stop["slots_after"] = (
            [{"slot": 0, "key": key, "counts": np.asarray(after)[vesicle].tolist()}]
            if living
            else []
        )
    out = sorted(events.values(), key=lambda e: (e["time"], e["schedule"]))
    return out, (np.concatenate(blocks) if blocks else np.zeros(0))


def build_population(spec, layout, ctx, draws, committed, codes, values, after_events, status,
                     start, final, world_key, ended, offsets=None):  # fmt: skip
    """(diagnostic.json's body, diagnostic.npz's arrays) of a population run: the world's draws
    (domain 5, carrier word 0, counter = the draw's index) read from the device, each crossing draw
    discarded at its schedule stop and the last one ending the run when the device ended it.

    offsets: a run from a checkpoint's (FR-22, rung P): {events, counter, heat, work} before its
    start. Its draws' counters continue the checkpoint's, each event's heat and work are their
    increments over the checkpoint's sums, and a lysis's event index is the world's count. So its
    record is the uninterrupted run's after the cut (checkpoints.py states the joining rule)."""
    from cells.models.assembly_lineages import keys as keys_rules

    world = spec.model.world
    fates = np.where(committed, COMMITTED, DISCARDED).astype(np.int8)
    if ended and (~committed).any():
        fates[np.flatnonzero(~committed)[-1]] = ENDED
    stream = streams.stream_key_data(layout.base_key, streams.WORLD_CARRIER, "world")
    import jax

    first = 0 if offsets is None else offsets["counter"]
    counters = np.arange(first, first + len(draws), dtype=np.int64)
    again = np.asarray(jax.vmap(lambda c: streams.uniforms(stream, c, 3))(counters))
    if not np.array_equal(again, draws):
        raise AssertionError("The world's draws differ from their addresses' uniforms: a fault")
    heat = values[:, 1] if len(values) else np.zeros(0)
    work = values[:, 3] if len(values) else np.zeros(0)
    heat_0, work_0, k0 = (0.0, 0.0, 0) if offsets is None else (
        offsets["heat"], offsets["work"], offsets["events"])  # fmt: skip
    lysed = np.zeros(len(codes), dtype=bool)
    for record in ctx.lyses:
        if not record["at_birth"]:
            lysed[record["event"] - k0 - 1] = True
    arrays = {
        "draw_domain": np.full(len(draws), 5, dtype=np.int8),
        "draw_key": np.zeros(len(draws), dtype=np.int64),
        "draw_counter": counters,
        "draw_uniforms": np.asarray(draws, dtype=np.float64).reshape(len(draws), 3),
        "draw_fate": fates,
        "event_time": values[:, 0] if len(values) else np.zeros(0),
        "event_group": codes[:, 0].astype(np.int32),
        "event_channel": codes[:, 1].astype(np.int32),
        "event_lysed": lysed,
        "event_heat_kT": np.diff(np.concatenate(([heat_0], heat))),
        "event_reservoir_work_kT": np.diff(np.concatenate(([work_0], work))),
        # [event, place]: explicit widths, so a run with no step event (OL5's ol3_shear_probe,
        # 0.03 s) writes [0, P] rather than failing to reshape an empty array
        "event_vesicle_after": np.asarray([a for a, _ in after_events], dtype=np.int64).reshape(
            len(codes), len(world.places)
        ),
        "event_pool_after": np.asarray([b for _, b in after_events], dtype=np.int64).reshape(
            len(codes), len(world.places)
        ),
    }
    sched = ctx.schedule_draws
    arrays |= {
        "schedule_draw_index": np.asarray([d[0] for d in sched], dtype=np.int64),
        "schedule_draw_counter": np.asarray([d[1] for d in sched], dtype=np.int64),
        "schedule_draw_uniform": np.asarray([d[2] for d in sched], dtype=np.float64),
        "schedule_draw_use": np.asarray([USES.index(d[3]) for d in sched], dtype=np.int8),
        "schedule_draw_time": np.asarray([d[4] for d in sched], dtype=np.float64),
    }
    stops, blocks, offset = {}, [], 0
    places = len(world.places)
    membrane, inside = division.vesicle_places(world)

    def state_of(s):
        return {"slots": [{"slot": int(k), "key": int(s.keys[k]),
                           "counts": s.slots[k][: places].tolist()}
                          for k in np.flatnonzero(s.alive)],
                "pool": s.pool[: places].tolist()}  # fmt: skip

    # A daughter born beyond sigma_max lyses at birth (§0.2d item 10.3): its lysis row books the
    # release, and the attempt that bore it states that heat and work too (attribution, not a
    # second booking: FORMAT_OL2.md).
    born = {int(r["key"]): r for r in ctx.lyses if r["at_birth"]}
    for a, _, slot, homes in ctx.attempts:
        entry = {"slot": int(slot), "key": int(a.parent), "counter": int(a.counter),
                 "outcome": a.outcome, "uniforms_offset": offset, "uniforms_count": 0}  # fmt: skip
        if a.counter >= 0:
            size = int(a.parent_counts[membrane].sum()) + a.k + int(a.parent_counts[inside].sum())
            blocks.append(division.block(layout.base_key, a.parent, a.counter, size))
            entry["uniforms_count"], offset = size, offset + size
        if a.outcome == "split":
            vesicle = np.concatenate((membrane, inside))
            entry["daughters"] = [
                {"key": int(key), "slot": int(homes[j]),
                 "counts": a.daughters[j][vesicle].tolist(), "lysed_at_birth": bool(a.lysed[j])}
                for j, key in enumerate(a.keys)
            ]  # fmt: skip
            lysed = [born[int(key)] for key in a.keys if int(key) in born]
            entry |= {"shear_work_kT": a.shear_work,
                      "heat_kT": float(sum(r["release_heat_kT"] for r in lysed)),
                      "reservoir_work_kT": float(sum(r["release_reservoir_work_kT"]
                                                     for r in lysed)),
                      "sink_kT": 0.0}  # fmt: skip
        stop = stops.setdefault(
            (a.time, a.schedule),
            {"time": a.time, "schedule": a.schedule, "not_admitted": [], "attempts": []},
        )
        if a.outcome in ("refused_stress", "refused_volume"):
            stop["not_admitted"].append(int(slot))
        stop["attempts"].append(entry)
    arrays["attempt_uniforms"] = np.concatenate(blocks) if blocks else np.zeros(0)
    # Each shear and transfer event's pool and living slots after it (the shear's attempts and
    # birth lyses, or the transfer's sample and fresh pool applied), and each transfer draw's slot.
    transfers = {(t["time_s"], t["schedule"]): t for t in ctx.transfers}
    transfer_events = []
    for time, schedule, after, living in ctx.scheduled_after:
        state_after = state_of(after)
        if ctx.by_index[schedule].kind == "transfer":
            event = {k: v for k, v in transfers[(time, schedule)].items() if k != "draws"}
            drawn = transfers[(time, schedule)]["draws"]
            if len(drawn) != len(living):
                raise AssertionError("A transfer drew other than once per living assembly")
            event["draws"] = [{"slot": s, "counter": int(d[1]), "uniform": float(d[2])}
                              for s, d in zip(living, drawn, strict=True)]  # fmt: skip
            transfer_events.append(event | {"pool_after": state_after["pool"],
                                            "slots_after": state_after["slots"]})  # fmt: skip
            continue
        stop = stops.setdefault(
            (time, schedule),
            {"time": time, "schedule": schedule, "not_admitted": [], "attempts": []},
        )
        stop |= {"pool_after": state_after["pool"], "slots_after": state_after["slots"]}

    groups = {"pool": [], "vesicle": []}
    for direction in ("forward", "reverse"):
        for step in world.steps:
            names = [n for n, _ in (*step.reactants, *step.products)]
            vesicle = any(world.places[world.place_index(n)].phase != "pool" for n in names)
            groups["vesicle" if vesicle else "pool"].append([step.id, direction])
    body = {
        "format": "cells.assembly_lineages.diagnostic@1",
        "fates": list(FATES),
        "schedule_uses": list(USES),
        "groups": "event_group 0 is the pool, 1 + k slot k",
        "channels": groups,
        "event_channel": "the kernel's signed code: +(r+1) step r's forward, -(r+1) its reverse",
        "places": [p.name for p in world.places],
        "after": "event_vesicle_after is the event's slot over every place (pool places 0; all 0 "
        "for a pool event); event_pool_after the pool over every place (vesicle places 0)",
        "shear_events": sorted(stops.values(), key=lambda e: (e["time"], e["schedule"])),
        "transfer_events": transfer_events,
        "lyses": ctx.lyses,
        "states": {"initial": state_of(start), "final": state_of(final)},
        "keys": keys_rules.SPELLING,
        "world": world_key,
        "end": status,
        "environment": environment(),
        "uniforms": "the world's draws are the device's own, checked against their addresses",
    }
    if ctx.replacements:  # FR-20: each pool replacement, when declared (it draws nothing)
        body["replacement_events"] = ctx.replacements
    if ctx.withdrawals:  # FR-35: each withdrawal, its draws by address (index, number, size)
        body["withdrawal_events"] = ctx.withdrawals
    return body, arrays
