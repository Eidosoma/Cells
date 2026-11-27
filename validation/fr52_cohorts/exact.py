"""FR-52's reference (docs/PASSIVE_COHORT_DESIGN.md §2.3, §3 and the amendment's §9.2), written from
the note, never from the engine's kernel: everything here is exact, in integers and rationals.

* tables(r, p): every legal pairing table of a channel, by brute force over its pairs; table(...)
  takes the one legal table, or the declared one, as the note's rule asks;
* update(...): the exact conditional expectation after one event (§2.3's four steps);
* enumerate_events(...): the exact distribution over individually labelled units, every equally
  likely choice of consumed and carried units (the frozen rows' control);
* read_run(...): the trace reader. It rebuilds each state's count from the trace's channels and the
  declared stoichiometry (never from the engine's counts), checks the rebuilt counts against the
  engine's recorded counts at every event (integer_trace_counts) and its saved counts at every
  row (integer_counts), forms the exact record from the declaration's own reading of the map,
  and holds the engine's binary64 record to it within 8 (K + 1) u N. Any failure is unresolved,
  never 0 or ∞.

A unit's labels are LABELS: present at t = 0, or arrived before, inside or after the window.
"""

import itertools
from fractions import Fraction

import numpy as np

LABELS = ("initial", "before", "inside", "after")
U = Fraction(1, 2**53)


# ------------------------------------------------------------------ the map


def tables(r, p):
    """Every legal table {(a, b): m >= 1} of a channel whose class reactants and products are r
    and p ({state: count}, no state on both sides): at most r[a] out of a, at most p[b] into b,
    min(R, P) in all. One empty table where R = 0 or P = 0."""
    total = min(sum(r.values()), sum(p.values()))
    pairs = [(a, b) for a in sorted(r) for b in sorted(p)]
    out = []

    def walk(i, values, rows, columns):
        # Every assignment of a whole number to each pair within the limits left, kept where
        # its sum is the total; the limits are checked again on each kept table.
        if i == len(pairs):
            if sum(values) == total:
                table = {pair: m for pair, m in zip(pairs, values, strict=True) if m}
                assert all(sum(m for (x, _), m in table.items() if x == a) <= r[a] for a in r)
                assert all(sum(m for (_, y), m in table.items() if y == b) <= p[b] for b in p)
                out.append(table)
            return
        a, b = pairs[i]
        for m in range(min(rows[a], columns[b], total - sum(values)) + 1):
            rows[a], columns[b] = rows[a] - m, columns[b] - m
            walk(i + 1, values + [m], rows, columns)
            rows[a], columns[b] = rows[a] + m, columns[b] + m

    walk(0, [], dict(r), dict(p))
    return out


def table(r, p, declared=None):
    """The channel's table: its one legal table, or the declared pairs [[a, b], ...] where it has
    two or more. ValueError where neither holds (the declaration would be refused)."""
    legal = tables(r, p)
    if declared is None:
        if len(legal) != 1:
            raise ValueError(f"{len(legal)} legal tables and none declared")
        return legal[0]
    if len(legal) == 1:
        raise ValueError("a declared table where the legal table is unique")
    found = {}
    for a, b in declared:
        found[(a, b)] = found.get((a, b), 0) + 1
    if found not in legal:
        raise ValueError(f"the declared table {found} is not legal")
    return found


def class_side(side, members):
    return {s: n for s, n in side.items() if s in members and n}


# ------------------------------------------------------------------ the exact update


def start_record(counts, members):
    """{state: [initial, before, inside, after]}: every unit of the class is initial at t = 0."""
    return {s: [Fraction(counts[s]), Fraction(0), Fraction(0), Fraction(0)] for s in members}


def label_index(time, window):
    start, end = window
    return 1 if time < start else (2 if time < end else 3)


def update(record, counts, r, p, pairs, label):
    """The record after one event (§2.3): counts {state: n} before it; r, p the channel's class
    stoichiometry; pairs its table; label the index of its time's label."""
    out = {s: list(v) for s, v in record.items()}
    shares = {a: [x / counts[a] for x in record[a]] for a in r}
    for a, taken in r.items():
        out[a] = [x * Fraction(counts[a] - taken, counts[a]) for x in record[a]]
    for (a, b), m in pairs.items():
        out[b] = [x + m * s for x, s in zip(out[b], shares[a], strict=True)]
    for b, made in p.items():
        carried = sum(m for (_, y), m in pairs.items() if y == b)
        out[b][label] += made - carried
    return out


# ------------------------------------------------------------------ the exact distribution


def enumerate_events(start, events, states):
    """The exact mean record after each event, enumerated over individually labelled units.

    start: {state: [label index, ...]} of the units present; events: [(r, p, pairs, label)], r
    and p the class stoichiometry, pairs the table; states: the class, in order. Each event
    consumes a uniformly random subset of r[a] units of each state a, independently, and a pair's
    unit is a uniformly random distinct one of those consumed. Returns [{state: [mean per
    label]}] after each event, as Fractions."""

    def key(units):
        return tuple(tuple(sorted(units.get(s, ()))) for s in states)

    distribution = {key(start): Fraction(1)}
    means = []
    for r, p, pairs, label in events:
        after = {}
        for composition, weight in distribution.items():
            units = {s: list(composition[i]) for i, s in enumerate(states)}
            for outcome, chance in _outcomes(units, r, p, pairs, label):
                k = key(outcome)
                after[k] = after.get(k, 0) + weight * chance
        distribution = after
        mean = {s: [Fraction(0)] * len(LABELS) for s in states}
        for composition, weight in distribution.items():
            for i, s in enumerate(states):
                for x in composition[i]:
                    mean[s][x] += weight
        means.append(mean)
    return means


def _outcomes(units, r, p, pairs, label):
    """[(units after, probability)] of one event over labelled units (enumerate_events)."""
    choices = []
    for a, taken in r.items():
        options = []
        subsets = list(itertools.combinations(range(len(units[a])), taken))
        for subset in subsets:
            consumed = [units[a][i] for i in subset]
            kept = [x for i, x in enumerate(units[a]) if i not in subset]
            targets = [(b, m) for (x, b), m in pairs.items() if x == a]
            assignments = list(_assign(consumed, targets))
            for carried in assignments:
                options.append((kept, carried, Fraction(1, len(subsets) * len(assignments))))
        choices.append((a, options))
    out = []
    for combination in itertools.product(*(options for _, options in choices)):
        after = {s: list(v) for s, v in units.items()}
        chance = Fraction(1)
        for (a, _), (kept, carried, c) in zip(choices, combination, strict=True):
            after[a] = list(kept)
            chance *= c
            for b, x in carried:
                after[b].append(x)
        for b, made in p.items():
            new = made - sum(m for (_, y), m in pairs.items() if y == b)
            after[b] += [label] * new
        out.append((after, chance))
    return out


def _assign(consumed, targets):
    """Every way of carrying m of the consumed units (each a label) to each target b: lists of
    (b, label), each consumed unit carried at most once, all ways equally likely."""
    if not targets:
        yield []
        return
    (b, m), rest = targets[0], targets[1:]
    for chosen in itertools.combinations(range(len(consumed)), m):
        left = [x for i, x in enumerate(consumed) if i not in chosen]
        for tail in _assign(left, rest):
            yield [(b, consumed[i]) for i in chosen] + tail


# ------------------------------------------------------------------ the trace reader


def site_of(block, site_id):
    """(site index, population) of a declared site: its position in declared order."""
    index = 0
    for population in block["populations"]:
        for site in population["sites"]:
            if site["id"] == site_id:
                return index, population
            index += 1
    raise ValueError(f"no site {site_id!r}")


def bound(events, most):
    return 8 * (events + 1) * U * most


def read_run(block, rows, cohort_id):
    """The reference's reading of one cohort over a run (module docstring).

    block: the operator's declaration as written in the definition; rows: {step: row}, each row
    with the operator's saved fields; cohort_id: the cohort to read. Returns {"resolved",
    "problems", "rows": {step: {"events", "exact", "worst_entry", "worst_sum", "bound"}}}, exact
    {state: [Fraction per label]}, the errors in units of the row's bound."""
    cohorts = block["cohorts"]
    q = next(i for i, c in enumerate(cohorts) if c["id"] == cohort_id)
    cohort = cohorts[q]
    i, population = site_of(block, cohort["site"])
    states = [u["id"] for u in population["unit_states"]]
    members = list(cohort["states"])
    weight = {u["id"]: u["subunits"] for u in population["unit_states"]}
    site = next(s for s in population["sites"] if s["id"] == cohort["site"])
    counts0 = dict(site["initial_counts"])
    window = tuple(cohort["window_s"])
    declared = {c["channel"]: c["pairs"] for c in cohort.get("carries", ())}
    channels = []
    for c in population["channels"]:
        r, p = class_side(c["reactants"], members), class_side(c["products"], members)
        channels.append((c, r, p, table(r, p, declared.get(c["id"]))))
    subunits = sum(weight[s] * n for s, n in counts0.items())
    most = subunits // min(weight[s] for s in members)
    problems = []
    last = rows[max(rows)]
    fired = int(np.asarray(last.integer_events)[i])
    capacity = np.asarray(last.integer_trace_channel).shape[1]
    held = min(fired, capacity)
    times = np.asarray(last.integer_trace_time_s)[i]
    chosen = np.asarray(last.integer_trace_channel)[i]
    recorded = np.asarray(last.integer_trace_counts)[i]
    k = len(states)
    # The slots agree with the channels: recorded where a channel is, -1 throughout beyond.
    for slot in range(capacity):
        if slot < held:
            if chosen[slot] < 0 or np.any(recorded[slot] < 0):
                problems.append(f"slot {slot} is recorded in its channel or counts only")
        elif chosen[slot] != -1 or np.any(recorded[slot] != -1):
            problems.append(f"slot {slot} lies beyond the events and is not -1 throughout")
    counts = dict(counts0)
    record = start_record(counts0, members)
    exact_after = [record]  # after 0, 1, ... events
    counts_after = [dict(counts)]
    for slot in range(held):
        c, r, p, pairs = channels[int(chosen[slot])]
        record = update(record, counts, r, p, pairs, label_index(float(times[slot]), window))
        for s, n in c["reactants"].items():
            counts[s] -= n
        for s, n in c["products"].items():
            counts[s] += n
        rebuilt = [counts[s] for s in states]
        if list(recorded[slot, :k]) != rebuilt or np.any(recorded[slot, k:] != 0):
            problems.append(
                f"event {slot}: the recorded counts {recorded[slot].tolist()} are not the rebuilt "
                f"{rebuilt} (padded with 0)"
            )
        exact_after.append(record)
        counts_after.append(dict(counts))
    out = {}
    for step in sorted(rows):
        row = rows[step]
        n = int(np.asarray(row.integer_events)[i])
        entry = dict(events=n, exact=None, worst_entry=None, worst_sum=None, bound=None)
        out[step] = entry
        if n > held:
            problems.append(f"step {step}: {n} events, past the trace's {capacity} slots")
            continue
        saved = np.asarray(row.integer_counts)[i]
        if [int(x) for x in saved[:k]] != [counts_after[n][s] for s in states] or np.any(
            saved[k:] != 0
        ):
            problems.append(f"step {step}: the saved counts are not the rebuilt ones")
            continue
        exact = exact_after[n]
        engine = np.asarray(row.integer_cohort_units)[q]
        b = bound(n, most)
        worst_entry = worst_sum = Fraction(0)
        for s in states:
            x = states.index(s)
            if s not in members:
                if np.any(engine[x] != 0):
                    problems.append(f"step {step}: {s}, outside the class, holds units")
                continue
            for label in range(len(LABELS)):
                departure = abs(Fraction(float(engine[x, label])) - exact[s][label])
                worst_entry = max(worst_entry, departure / b)
            total = Fraction(float(np.sum(engine[x])))
            worst_sum = max(worst_sum, abs(total - counts_after[n][s]) / b)
        entry.update(exact=exact, worst_entry=worst_entry, worst_sum=worst_sum, bound=b)
        if worst_entry > 1 or worst_sum > 1:
            problems.append(f"step {step}: the record lies outside its bound")
    return dict(resolved=not problems, problems=problems, rows=out, most=most)
