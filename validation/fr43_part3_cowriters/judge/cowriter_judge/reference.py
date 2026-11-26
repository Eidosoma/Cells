"""The reference files (SPEC.md §7) as the judge reads them, and C0 (CRITERIA.md §4.2).

C0 is the judge's first read, before any engine run is read: `reference_invented.json`, then each reference file,
then `draws_check`, `inputs_sha256` and the protocol's hashes. A fault is named and refuses the reference; a refused
reference refuses the comparison of its world.

Beyond §4.2's list, C0 recomputes from the published numbers what the criteria define (the judge's own checks,
each named `recomputed ...` or `consistency ...`): the sizing's used differences, q, est and tau from its own d; the
pair's and rungs' thresholds; the scales from the published series (READOUTS.md §2); the plants' distances from the
planted series; K and K_all from the published times; the trace's alternation and ledger; and the closed forms of
LAWS.md §4 against the draws (every wait in a state where nothing read is active, and W5-exact's times).

The lead's ruling 7 (26 November 2026): a fault is one the spec names, judged on the published values (§4.2's list,
a duplicate key, a NaN or an infinity, a missing registered key, a margin below 10, an invented number equal to a
registered one; and the hashes §4.2 reads). A disagreement of the judge's own recomputation or consistency check
with a published value is not a fault but a finding: it refuses nothing, and the judge stops and reports it to the
lead before anything is scored.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from decimal import Decimal, localcontext
from fractions import Fraction
from typing import Any

from . import edits as edit_module
from . import strictjson as sj
from .registry import (M_ROW, M_TIME, ORDER_HALF_WINDOW, P3_C0_HALF_WINDOW, PAIR_FACTOR, PLANT_MARGIN,
                       SCALE_LINES, SIZING_ORDER_HALF_WINDOW, U, Inputs, World, e_round, steps)
from .rules import check_trace, identity_at, ledger_fails, start_at
from .stats import ladder, log_slope, pooled_rms, round_bound, tau

REFERENCE_KIND = "fr43 part 3 co-writers reference, version 2"
REL_RECOMPUTE = 1e-9  # a recomputed statistic agrees with the published one to this, relative
REL_SCALE = 1e-12


@dataclass
class Fault:
    code: str
    where: str
    message: str

    def as_dict(self) -> dict:
        return {"code": self.code, "where": self.where, "message": self.message}


class Collector:
    def __init__(self) -> None:
        self.faults: list[Fault] = []  # the spec's named faults: they refuse the reference
        self.findings: list[Fault] = []  # ruling 7: the judge's own checks; they stop the judge, refuse nothing
        self.flags: list[Fault] = []
        self.comparisons: list[dict] = []

    def fault(self, code: str, where: str, message: str) -> None:
        self.faults.append(Fault(code, where, message))

    def finding(self, code: str, where: str, message: str) -> None:
        self.findings.append(Fault(code, where, message))

    def flag(self, code: str, where: str, message: str) -> None:
        self.flags.append(Fault(code, where, message))

    def compare(self, what: str, published: Any, recomputed: Any, rel: float, finding_code: str | None) -> bool:
        ok = _agree(published, recomputed, rel)
        self.comparisons.append({"what": what, "published": published, "recomputed": recomputed, "agree": ok})
        if not ok and finding_code is not None:
            self.finding(finding_code, what, f"published {published!r}, recomputed {recomputed!r} (relative {rel:g})")
        return ok


def _agree(a: Any, b: Any, rel: float) -> bool:
    if a is None or b is None:
        return a is None and b is None
    if isinstance(a, bool) or isinstance(b, bool):
        return a == b
    if isinstance(a, int) and isinstance(b, int):
        return a == b
    a = float(a)
    b = float(b)
    if a == b:
        return True
    return abs(a - b) <= rel * max(abs(a), abs(b))


_MISSING = object()

TYPE_CHECKS = {
    "number": sj.is_number,
    "integer": sj.is_integer,
    "string": sj.is_string,
    "bool": sj.is_bool,
    "object": sj.is_object,
    "list": sj.is_list,
}


def need(coll: Collector, obj: Any, key: str, kind: str, where: str, nullable: bool = False) -> Any:
    """A registered key: missing or of another type is a fault (SPEC.md §7: a missing registered key)."""
    if not isinstance(obj, dict):
        coll.fault("missing registered key", f"{where}/{key}", "its parent is not an object")
        return _MISSING
    if key not in obj:
        coll.fault("missing registered key", f"{where}/{key}", "missing")
        return _MISSING
    value = obj[key]
    if value is None and nullable:
        return None
    if not TYPE_CHECKS[kind](value):
        coll.fault("missing registered key", f"{where}/{key}", f"not a {kind}: {type(value).__name__}")
        return _MISSING
    return value


def number_list(coll: Collector, obj: Any, key: str, where: str, length: int | None = None) -> list[float] | None:
    value = need(coll, obj, key, "list", where)
    if value is _MISSING:
        return None
    if not all(sj.is_number(v) for v in value):
        coll.fault("missing registered key", f"{where}/{key}", "a list member that is not a finite number")
        return None
    if length is not None and len(value) != length:
        coll.fault("missing registered key", f"{where}/{key}", f"length {len(value)}, not {length}")
        return None
    return [float(v) for v in value]


@dataclass
class RefCopy:
    copy: int
    seed: int
    K: int
    K_all: int
    times: list[float]
    channels: list[str]
    counts: list[tuple[int, ...]]
    accuracy_s: float
    samples: list[float] = field(default_factory=list)
    series: dict[str, list[float]] = field(default_factory=dict)
    accuracy: dict[str, list[float]] = field(default_factory=dict)


@dataclass
class ReferenceWorld:
    world: str
    copies: list[RefCopy]
    scales: dict[str, float]
    classes: dict[str, str]
    planted: dict[str, dict[str, Any]]
    sizing: dict
    plants: list[dict]
    raw: dict


def _read_events(coll: Collector, obj: Any, where: str, n_states: int) -> dict | None:
    events = need(coll, obj, "events", "object", where)
    if events is _MISSING:
        return None
    w = f"{where}/events"
    k = need(coll, events, "K", "integer", w)
    k_all = need(coll, events, "K_all", "integer", w)
    times = number_list(coll, events, "time_s", w)
    channels = need(coll, events, "channel", "list", w)
    counts = need(coll, events, "counts_after", "list", w)
    accuracy = need(coll, events, "accuracy_s", "number", w)
    if _MISSING in (k, k_all, channels, counts, accuracy) or times is None:
        return None
    if not all(isinstance(c, str) for c in channels):
        coll.fault("missing registered key", f"{w}/channel", "a member that is not a string")
        return None
    if not all(isinstance(c, list) and len(c) == n_states and all(sj.is_integer(x) for x in c) for c in counts):
        coll.fault("missing registered key", f"{w}/counts_after", "a member that is not a list of integer counts")
        return None
    k = int(k)
    k_all = int(k_all)
    if not (len(times) == len(channels) == len(counts)):
        coll.fault("missing registered key", w, f"the event lists are of {len(times)}, {len(channels)} and "
                                                f"{len(counts)} members")
        return None
    if len(times) != k_all:
        coll.finding("consistency events", w, f"{len(times)} listed events against K_all {k_all}")
    return {"K": k, "K_all": k_all, "times": times, "channels": list(channels),
            "counts": [tuple(int(x) for x in c) for c in counts], "accuracy_s": float(accuracy)}


def _read_series(coll: Collector, obj: Any, where: str, names: list[str], length: int) -> tuple[dict, dict] | None:
    series = need(coll, obj, "series", "object", where)
    if series is _MISSING:
        return None
    values: dict[str, list[float]] = {}
    accuracy: dict[str, list[float]] = {}
    ok = True
    for name in names:
        entry = need(coll, series, name, "object", f"{where}/series")
        if entry is _MISSING:
            ok = False
            continue
        v = number_list(coll, entry, "value", f"{where}/series/{name}", length)
        a = number_list(coll, entry, "accuracy", f"{where}/series/{name}", length)
        if v is None or a is None:
            ok = False
            continue
        values[name] = v
        accuracy[name] = a
    return (values, accuracy) if ok else None


def read_world(coll: Collector, obj: Any, inputs: Inputs, world_name: str, where: str) -> ReferenceWorld | None:
    """SPEC.md §7's layout for one world; every registered key is checked for presence and type."""
    if world_name not in inputs.worlds:
        coll.fault("unregistered world", where, f"{world_name!r} is not a world of the inputs")
        return None
    world = inputs.worlds[world_name]
    if not isinstance(obj, dict):
        coll.fault("missing registered key", where, "the world's reference is not an object")
        return None
    kind = need(coll, obj, "kind", "string", where)
    if kind is not _MISSING and kind != REFERENCE_KIND:
        coll.fault("missing registered key", f"{where}/kind", f"{kind!r} is not {REFERENCE_KIND!r}")
    name = need(coll, obj, "world", "string", where)
    if name is not _MISSING and name != world_name:
        coll.fault("unregistered world", f"{where}/world", f"{name!r} where {world_name!r} is read")
    sha = need(coll, obj, "inputs_sha256", "string", where)
    if sha is not _MISSING and sha.lower() != inputs.sha256:
        coll.fault("inputs_sha256", f"{where}/inputs_sha256", f"{sha} is not the inputs file's {inputs.sha256}")
    for key, kind_ in (("scales", "object"), ("classes", "object"), ("planted", "object"), ("sizing", "object"),
                       ("plants", "list"), ("draws_check", "object"), ("reported", "list"),
                       ("provenance", "object")):
        need(coll, obj, key, kind_, where)
    copies_raw = need(coll, obj, "copies", "list", where)
    copies: list[RefCopy] = []
    if copies_raw is not _MISSING:
        if len(copies_raw) != world.copies:
            coll.fault("missing registered key", f"{where}/copies", f"{len(copies_raw)} copies, not {world.copies}")
        for c, raw in enumerate(copies_raw[:world.copies]):
            w = f"{where}/copies/{c}"
            cc = need(coll, raw, "copy", "integer", w)
            seed = need(coll, raw, "seed", "integer", w)
            if cc is not _MISSING and int(cc) != c:
                coll.finding("consistency copies", f"{w}/copy", f"copy {cc} at position {c}")
            if seed is not _MISSING and int(seed) != world.seeds[c]:
                coll.finding("consistency copies", f"{w}/seed", f"seed {seed}, registered {world.seeds[c]}")
            ev = _read_events(coll, raw, w, len(world.unit_states))
            samples = number_list(coll, raw, "samples_s", w)
            if samples is not None and samples != [float(s) for s in world.samples]:
                coll.finding("consistency samples", f"{w}/samples_s", "not the registered samples_s")
            ser = _read_series(coll, raw, w, world.series, len(world.samples))
            checks = need(coll, raw, "checks", "list", w)
            if checks is not _MISSING:
                _check_checks(coll, checks, f"{w}/checks")
            if ev is None or ser is None or cc is _MISSING or seed is _MISSING:
                continue
            copies.append(RefCopy(copy=c, seed=int(seed), K=ev["K"], K_all=ev["K_all"], times=ev["times"],
                                  channels=ev["channels"], counts=ev["counts"], accuracy_s=ev["accuracy_s"],
                                  samples=[float(s) for s in world.samples], series=ser[0], accuracy=ser[1]))
    scales_raw = obj.get("scales") if isinstance(obj.get("scales"), dict) else {}
    scales: dict[str, float] = {}
    for readout in ["t_events"] + world.series:
        value = need(coll, scales_raw, readout, "number", f"{where}/scales")
        if value is _MISSING:
            continue
        if not value > 0:
            coll.fault("scale not positive", f"{where}/scales/{readout}", f"{value!r}")
        scales[readout] = float(value)
    classes_raw = obj.get("classes") if isinstance(obj.get("classes"), dict) else {}
    planted = _read_planted(coll, obj.get("planted"), inputs, world, f"{where}/planted")
    sizing = obj.get("sizing") if isinstance(obj.get("sizing"), dict) else {}
    plants = obj.get("plants") if isinstance(obj.get("plants"), list) else []
    return ReferenceWorld(world=world_name, copies=copies, scales=scales, classes=dict(classes_raw), planted=planted,
                          sizing=sizing, plants=plants, raw=obj)


def _check_checks(coll: Collector, checks: list, where: str) -> None:
    for i, entry in enumerate(checks):
        w = f"{where}/{i}"
        name = need(coll, entry, "name", "string", w)
        residual = need(coll, entry, "residual", "number", w)
        bound = need(coll, entry, "bound", "number", w)
        passes = need(coll, entry, "passes", "bool", w)
        if _MISSING in (name, residual, bound, passes):
            continue
        if passes is not True or not residual <= bound:
            coll.fault("check does not pass", w, f"{name}: residual {residual!r}, bound {bound!r}, passes {passes}")


def _read_planted(coll: Collector, planted_raw: Any, inputs: Inputs, world: World, where: str) -> dict:
    out: dict[str, dict[str, Any]] = {}
    if not isinstance(planted_raw, dict):
        return out
    for plant in inputs.plants_of(world.name):
        if plant.kind != "reference":
            continue
        entry = need(coll, planted_raw, plant.id, "object", where)
        if entry is _MISSING:
            continue
        out[plant.id] = {}
        s_names = [check for cls, check in plant.must_fail if cls == "S" and check != "t_events"]
        for fam in plant.families:
            w = f"{where}/{plant.id}/{fam}"
            if plant.base == "P4":
                block = need(coll, entry, fam, "object", f"{where}/{plant.id}")
                if block is _MISSING:
                    continue
                shift = need(coll, block, "shift_s", "number", w)
                if shift is not _MISSING:
                    out[plant.id][fam] = {"shift_s": float(shift)}
                continue
            lst = need(coll, entry, fam, "list", f"{where}/{plant.id}")
            if lst is _MISSING:
                continue
            if len(lst) != world.copies:
                coll.fault("missing registered key", w, f"{len(lst)} planted copies, not {world.copies}")
                continue
            copies = []
            for c, raw in enumerate(lst):
                wc = f"{w}/{c}"
                cc = need(coll, raw, "copy", "integer", wc)
                if cc is not _MISSING and int(cc) != c:
                    coll.finding("consistency copies", f"{wc}/copy", f"copy {cc} at position {c}")
                ev = _read_events(coll, raw, wc, len(world.unit_states))
                ser = _read_series(coll, raw, wc, s_names, len(world.samples))
                if ev is None or ser is None:
                    continue
                copies.append(RefCopy(copy=c, seed=world.seeds[c], K=ev["K"], K_all=ev["K_all"], times=ev["times"],
                                      channels=ev["channels"], counts=ev["counts"], accuracy_s=ev["accuracy_s"],
                                      samples=[float(s) for s in world.samples], series=ser[0], accuracy=ser[1]))
            if len(copies) == world.copies:
                out[plant.id][fam] = copies
    return out


# ---------------------------------------------------------------------------------------------------------------
# The quantities the criteria read from a reference


def k_c_cut(inputs: Inputs, world: World) -> float:
    """T - g h_1: K_c counts the events at or before it (SPEC.md §3)."""
    return float(Fraction(world.end_s) - inputs.guard_steps * Fraction(world.rungs[0]))


def e_ref_events(copies: list[RefCopy]) -> float:
    """The reference's largest accuracy over the entries of t_events (copies with a judged event)."""
    values = [c.accuracy_s for c in copies if c.K > 0]
    return max(values) if values else 0.0


def e_ref_series(copies: list[RefCopy], readout: str, samples: list[float]) -> float:
    """The reference's largest accuracy over the entries of a row or book (samples t > 0)."""
    values = [c.accuracy[readout][i] for c in copies for i, t in enumerate(samples) if t > 0]
    return max(values) if values else 0.0


def recompute_scale(copies: list[RefCopy], readout: str, end_s: float) -> float:
    """READOUTS.md §2."""
    if readout == "t_events":
        return end_s
    line = SCALE_LINES.get(readout, [(readout, "t")])
    best = 0.0
    for c in copies:
        for i in range(len(c.samples)):
            total = math.fsum(abs(c.series[name][i] if when == "t" else c.series[name][0]) for name, when in line)
            best = max(best, total)
    return best


def honest_entries(world: World, copies: list[RefCopy], readout: str) -> list[tuple[int, int]]:
    """READOUTS.md §5's entries: (copy, k) for k < K_c of t_events; (copy, sample index) for t > 0 otherwise."""
    if readout == "t_events":
        return [(c.copy, k) for c in copies for k in range(c.K)]
    return [(c.copy, i) for c in copies for i, t in enumerate(c.samples) if t > 0]


def ref_value(copy: RefCopy, readout: str, index: int) -> float:
    return copy.times[index] if readout == "t_events" else copy.series[readout][index]


# ---------------------------------------------------------------------------------------------------------------
# C0 on one world


def c0_world(coll: Collector, ref: ReferenceWorld, inputs: Inputs, draws: dict | None, where: str) -> dict:
    world = inputs.worlds[ref.world]
    summary: dict[str, Any] = {}
    obj = ref.raw
    copies = ref.copies
    complete_copies = len(copies) == world.copies

    # classes (SPEC.md §7): the judged readouts of the world and nothing else
    expected_classes = {readout: "S" for readout, _ in world.s_readouts()}
    if "t_events" in world.judged.get("R", []):
        expected_classes["t_events"] = "R"
    if ref.classes != expected_classes:
        coll.fault("class", f"{where}/classes", f"{ref.classes} against inputs.json's judged {expected_classes}")

    # draws_check (CRITERIA.md §4.2)
    dc = obj.get("draws_check")
    if isinstance(dc, dict):
        identical = need(coll, dc, "identical", "bool", f"{where}/draws_check")
        entries = need(coll, dc, "entries", "integer", f"{where}/draws_check")
        if identical is not _MISSING and identical is not True:
            coll.fault("draws_check", f"{where}/draws_check", "not identical")
        if entries is not _MISSING:
            summary["draws_check_entries"] = int(entries)
            expected_entries = 2 * world.copies * inputs.pairs_per_copy
            if int(entries) <= 0:
                coll.finding("draws_check", f"{where}/draws_check", "no entry compared")
            elif int(entries) != expected_entries:
                coll.flag("draws_check entries", f"{where}/draws_check",
                          f"{entries} entries; 2 x copies x pairs_per_copy = {expected_entries}")

    # provenance and reported (registered keys)
    prov = obj.get("provenance")
    if isinstance(prov, dict):
        for key in ("revision", "python", "numpy", "scipy"):
            need(coll, prov, key, "string", f"{where}/provenance")
        need(coll, prov, "sha256_of_this_file_excluded", "bool", f"{where}/provenance")
        summary["provenance"] = {k: prov.get(k) for k in ("revision", "python", "numpy", "scipy")}
    rep = obj.get("reported")
    if isinstance(rep, list):
        for i, entry in enumerate(rep):
            need(coll, entry, "name", "string", f"{where}/reported/{i}")
            if not (isinstance(entry, dict) and "value" in entry):
                coll.fault("missing registered key", f"{where}/reported/{i}/value", "missing")

    if not complete_copies:
        coll.fault("incomplete", f"{where}/copies", "not every copy could be read; the rest of C0 is not formed")
        return summary

    # accuracy against SPEC.md §4
    exact_times = "t_events" in world.judged.get("R", [])
    event_limit = (1e-15 if exact_times else 1e-11) * world.end_s
    for c in copies:
        if not c.accuracy_s >= 0 or c.accuracy_s > event_limit:
            coll.fault("accuracy", f"{where}/copies/{c.copy}/events/accuracy_s",
                       f"{c.accuracy_s!r} against SPEC.md §4's {event_limit!r}")
        for name in world.series:
            limit = 1e-11 * ref.scales.get(name, 0.0)
            worst = max(c.accuracy[name])
            if min(c.accuracy[name]) < 0 or worst > limit:
                coll.fault("accuracy", f"{where}/copies/{c.copy}/series/{name}/accuracy",
                           f"largest {worst!r} against SPEC.md §4's {limit!r}")
    for pid, fams in ref.planted.items():
        for fam, block in fams.items():
            if not isinstance(block, list):
                continue
            for c in block:
                if c.accuracy_s > event_limit:
                    coll.fault("accuracy", f"{where}/planted/{pid}/{fam}/{c.copy}/events",
                               f"{c.accuracy_s!r} against {event_limit!r}")
                for name, acc in c.accuracy.items():
                    limit = 1e-11 * ref.scales.get(name, 0.0)
                    if max(acc) > limit:
                        coll.fault("accuracy", f"{where}/planted/{pid}/{fam}/{c.copy}/series/{name}",
                                   f"largest {max(acc)!r} against {limit!r}")

    # scales: positive (read_world) and as READOUTS.md §2 defines them, from the published series
    for readout, value in ref.scales.items():
        coll.compare(f"{where}/scales/{readout}", value, recompute_scale(copies, readout, world.end_s), REL_SCALE,
                     "recomputed scale")

    # the events: K and K_all from the times, the guard, the trace and ledger, the closed forms
    cut = k_c_cut(inputs, world)
    ks = []
    for c in copies:
        w = f"{where}/copies/{c.copy}/events"
        if any(not (0 < t <= world.end_s) for t in c.times):
            coll.finding("consistency events", w, "an event time outside (0, T]")
        k_count = sum(1 for t in c.times if t <= cut)
        if k_count != c.K:
            coll.finding("consistency events", w, f"K = {c.K}, but {k_count} times are at or before T - g h_1")
        if c.times and min(abs(Fraction(t) - Fraction(cut)) for t in c.times) <= Fraction(1e-9) * Fraction(
                world.end_s):
            coll.finding("guard", w, "an event within 1e-9 T of T - g h_1 (SPEC.md §9.8)")
        if not c.K_all < inputs.pairs_per_copy:
            coll.finding("draws", w, f"K_all {c.K_all} is not below pairs_per_copy {inputs.pairs_per_copy}")
        trace = check_trace(world, c.times, c.channels, c.counts, 0, c.K_all, c.K, c.channels, c.counts,
                            world.initial_counts, True, True)
        if trace.fails:
            coll.finding("consistency trace", w, "; ".join(trace.fails))
        led = ledger_fails(world, None, c.counts)
        if led:
            coll.finding("consistency ledger", w, "; ".join(led))
        ks.append(c.K)
        if draws is not None:
            summary["closed_forms_checked"] = summary.get("closed_forms_checked", 0) + _closed_forms(
                coll, world, c, draws, w, exact_times)
    summary["K"] = ks
    summary["K_all"] = [c.K_all for c in copies]
    # minimum events (by the reference's K_c: per copy and in all)
    if min(ks) < world.minimum_per_copy:
        coll.fault("minimum events", f"{where}/copies", f"a copy with K = {min(ks)} below {world.minimum_per_copy}")
    if sum(ks) < world.minimum_total:
        coll.fault("minimum events", f"{where}/copies", f"K in all {sum(ks)} below {world.minimum_total}")

    # the references' own conservation on their published rows, read as the run's identities are (to rounding)
    for c in copies:
        at0 = {name: c.series[name][0] for name in world.series}
        for ident in world.judged.get("identities", []):
            terms = world.identities[ident]
            for i in range(len(c.samples)):
                at_t = {name: c.series[name][i] for name in world.series}
                value = identity_at(terms, at_t, at0, Fraction(0))
                summary["identities_checked"] = summary.get("identities_checked", 0) + 1
                # bound with S = 0 and 16 u s_id: the published doubles must close to a few roundings
                if not value.passes:
                    coll.finding("consistency identity", f"{where}/copies/{c.copy}/{ident}/sample {i}",
                               f"residual {float(value.residual)!r} over 16 u s_id {float(value.bound)!r}")
        for readout in world.start:
            declared = inputs.start_value(world.name, readout)
            if not start_at(c.series[readout][0], declared).passes:
                coll.finding("start", f"{where}/copies/{c.copy}/series/{readout}/0",
                           f"{c.series[readout][0]!r} against the declared {declared!r}")

    if "t_events" in world.judged.get("R", []):
        summary["ruling_4_p5_tolerance"] = p5_tolerance_readings(ref, inputs, world)
    _c0_sizing(coll, ref, inputs, world, where, summary)
    _c0_pair_and_rungs(coll, ref, inputs, world, where, summary)
    _c0_running(coll, ref, inputs, world, where)
    _c0_plants(coll, ref, inputs, world, where, summary)
    return summary


def _closed_forms(coll: Collector, world: World, c: RefCopy, draws: dict, where: str, exact_times: bool) -> int:
    """LAWS.md §4 against the draws: a wait in a state where no active channel reads equals E_k / a_0 (and in
    W5-exact every time is the decimal sum). Returns the number of events checked."""
    u1 = draws.get(c.copy)
    checked = 0
    if u1 is None:
        coll.finding("draws", where, "no draws for this copy")
        return checked
    with localcontext() as ctx:
        ctx.prec = 50
        state = tuple(world.initial_counts)
        clock = Decimal(0)
        previous_time = Decimal(0)
        for k, t in enumerate(c.times):
            if k >= len(u1):
                coll.finding("draws", where, f"event {k} beyond the draws")
                return checked
            a0 = Decimal(0)
            reads = False
            for cid in world.channel_order:
                ch = world.block["population"]["channels"][world.channel_order.index(cid)]
                ff = 1
                for s_index, s_name in enumerate(world.unit_states):
                    r = int(ch.get("reactants", {}).get(s_name, 0))
                    n = state[s_index]
                    for i in range(r):
                        ff *= max(n - i, 0)
                if ff == 0:
                    continue
                if ch.get("read") is not None:
                    reads = True
                a0 += Decimal(ff) * Decimal(float(ch["rate_constant"]))
            energy = -Decimal(u1[k]).ln()
            if not reads and a0 > 0:
                checked += 1
                wait = energy / a0
                t_dec = Decimal(t)
                if exact_times:
                    clock += wait
                    if abs(t_dec - clock) > Decimal(c.accuracy_s):
                        coll.finding("closed form", f"{where}/time_s/{k}",
                                   f"{t!r} against the decimal sum {float(clock)!r} (accuracy {c.accuracy_s!r})")
                elif abs((t_dec - previous_time) - wait) > 2 * Decimal(c.accuracy_s):
                    coll.finding("closed form", f"{where}/time_s/{k}",
                               f"wait {float(t_dec - previous_time)!r} against E_k/a_0 {float(wait)!r}")
            elif exact_times:
                coll.finding("closed form", f"{where}/time_s/{k}", "a read channel is active in a constant-rate world")
                return checked
            previous_time = Decimal(t)
            state = c.counts[k]
    return checked


def _c0_sizing(coll: Collector, ref: ReferenceWorld, inputs: Inputs, world: World, where: str,
               summary: dict) -> None:
    sizing = ref.sizing
    named = set(world.at_rounding())
    rows = []
    for fam_id in world.families:
        fam = inputs.families[fam_id]
        block = need(coll, sizing, fam_id, "object", f"{where}/sizing")
        if block is _MISSING:
            continue
        for readout, p in world.s_readouts():
            w = f"{where}/sizing/{fam_id}/{readout}"
            entry = need(coll, block, readout, "object", f"{where}/sizing/{fam_id}")
            if entry is _MISSING:
                continue
            n = len(fam.rungs)
            d = number_list(coll, entry, "d", w, n - 1)
            used = need(coll, entry, "used", "integer", w)
            q = need(coll, entry, "q", "number", w, nullable=True)
            e_n = need(coll, entry, "E", "number", w)
            est = need(coll, entry, "est", "number", w)
            tau_pub = need(coll, entry, "tau", "number", w)
            retry = need(coll, entry, "retry", "object", w)
            if retry is not _MISSING:
                number_list(coll, retry, "d", f"{w}/retry", n - 1)
                for key in ("used",):
                    need(coll, retry, key, "integer", f"{w}/retry")
                need(coll, retry, "q", "number", f"{w}/retry", nullable=True)
                for key in ("E", "est", "tau"):
                    need(coll, retry, key, "number", f"{w}/retry")
            if d is None or _MISSING in (used, q, e_n, est, tau_pub):
                continue
            used = int(used)
            # §4.2's conditions on the published values
            if readout in named:
                if used >= 3:
                    coll.fault("sizing at_rounding", w, f"named in at_rounding but {used} used differences")
            else:
                if used < 3 or q is None:
                    coll.fault("sizing order", w, f"the expected order cannot be formed ({used} used)")
                elif not (p - SIZING_ORDER_HALF_WINDOW <= q <= p + SIZING_ORDER_HALF_WINDOW):
                    coll.fault("sizing order", w, f"q = {q!r} outside [p - 0.4, p + 0.4], p = {p}")
            if not e_n <= tau_pub:
                coll.fault("sizing size", w, f"E = {e_n!r} above tau = {tau_pub!r}")
            # the judge's recomputation from the published d, scales and accuracies
            m = world.m_of(readout)
            scale = ref.scales.get(readout)
            if scale is None:
                continue
            lad = ladder(p, fam.rungs, d, m, world.end_s, scale)
            e_ref = e_ref_events(ref.copies) if readout == "t_events" else e_ref_series(ref.copies, readout,
                                                                                         world.samples)
            tau_re = tau(lad.est, e_ref, m, world.end_s, fam.rungs[-1], scale)
            coll.compare(f"{w}/used", used, lad.used, 0.0, "recomputed sizing")
            coll.compare(f"{w}/q", q, lad.q, REL_RECOMPUTE, "recomputed sizing")
            coll.compare(f"{w}/est", est, lad.est, REL_RECOMPUTE, "recomputed sizing")
            coll.compare(f"{w}/tau", tau_pub, tau_re, REL_RECOMPUTE, "recomputed sizing")
            if readout not in named and lad.q is not None and not (
                    p - SIZING_ORDER_HALF_WINDOW <= lad.q <= p + SIZING_ORDER_HALF_WINDOW):
                coll.finding("sizing order", w, f"recomputed q = {lad.q!r} outside [p - 0.4, p + 0.4]")
            if lad.any_zero:
                coll.finding("sizing order", w, "a zero step difference")
            rows.append({"family": fam_id, "readout": readout, "p": p, "used": used, "q": q, "E": e_n, "tau": tau_pub,
                         "E_over_tau": e_n / tau_pub if tau_pub > 0 else None,
                         "least_resolution_ratio": min((dj / th for dj, th in zip(d[:max(used, 1)],
                                                                                   lad.thresholds)), default=None)})
    summary["sizing"] = rows
    # P3 (the mutant): its expected order within 1/4 of p - 1, over its three rungs
    mutant = sizing.get("mutant") if isinstance(sizing.get("mutant"), dict) else None
    if mutant is None:
        coll.fault("missing registered key", f"{where}/sizing/mutant", "missing")
        return
    for plant in inputs.plants_of(world.name):
        if plant.kind != "engine":
            continue
        rungs = sorted({spec.step for spec in inputs.run_list if spec.role == "plant" and spec.world == world.name
                        and spec.variant == "second halves in declared order"}, reverse=True)
        for fam_id in plant.families:
            w = f"{where}/sizing/mutant/{fam_id}"
            entry = need(coll, mutant, fam_id, "object", f"{where}/sizing/mutant")
            if entry is _MISSING:
                continue
            e_list = number_list(coll, entry, "E", w, len(rungs))
            q = need(coll, entry, "q", "number", w)
            if e_list is None or q is _MISSING:
                continue
            p = world.order_of("t_events")
            if not abs(q - (p - 1)) <= P3_C0_HALF_WINDOW:
                coll.fault("sizing P3", w, f"q = {q!r} not within 1/4 of p - 1 = {p - 1}")
            if all(e > 0 for e in e_list):
                q_re = log_slope(rungs, e_list)
                coll.compare(f"{w}/q", q, q_re, REL_RECOMPUTE, "recomputed sizing")
                if not abs(q_re - (p - 1)) <= P3_C0_HALF_WINDOW:
                    coll.finding("sizing P3", w, f"recomputed q = {q_re!r} not within 1/4 of p - 1")
            else:
                coll.finding("sizing P3", w, "a non-positive E")
            summary.setdefault("mutant", {})[fam_id] = {"E": e_list, "q": q, "rungs": rungs}


def _c0_pair_and_rungs(coll: Collector, ref: ReferenceWorld, inputs: Inputs, world: World, where: str,
                       summary: dict) -> None:
    sizing = ref.sizing
    h1 = world.rungs[0]
    pair = need(coll, sizing, "pair", "object", f"{where}/sizing")
    summary["pair"] = {}
    if pair is not _MISSING:
        for readout in world.judged.get("orders_differ", []):
            _ratio_entry(coll, pair, readout, f"{where}/sizing/pair", world, ref, h1, summary["pair"])
    if world.judged.get("rungs_differ"):
        rungs = need(coll, sizing, "rungs", "object", f"{where}/sizing")
        summary["rungs"] = {}
        if rungs is not _MISSING:
            for fam_id in world.families:
                block = need(coll, rungs, fam_id, "object", f"{where}/sizing/rungs")
                if block is _MISSING:
                    continue
                summary["rungs"][fam_id] = {}
                for readout in world.judged["rungs_differ"]:
                    _ratio_entry(coll, block, readout, f"{where}/sizing/rungs/{fam_id}", world, ref, h1,
                                 summary["rungs"][fam_id])


def _ratio_entry(coll: Collector, block: dict, readout: str, where: str, world: World, ref: ReferenceWorld,
                 h1: float, out: dict) -> None:
    entry = need(coll, block, readout, "object", where)
    if entry is _MISSING:
        return
    w = f"{where}/{readout}"
    rms = need(coll, entry, "rms", "number", w)
    threshold = need(coll, entry, "threshold", "number", w)
    ratio_pub = need(coll, entry, "ratio", "number", w)
    if _MISSING in (rms, threshold, ratio_pub):
        return
    scale = ref.scales.get(readout)
    if scale is not None:
        threshold_re = PAIR_FACTOR * round_bound(world.m_of(readout), world.end_s, h1, scale)
        coll.compare(f"{w}/threshold", threshold, threshold_re, REL_RECOMPUTE, "recomputed threshold")
        coll.compare(f"{w}/ratio", ratio_pub, rms / threshold_re, REL_RECOMPUTE, "recomputed threshold")
    if not ratio_pub >= PAIR_FACTOR:
        coll.fault("pair", w, f"expected ratio {ratio_pub!r} below {PAIR_FACTOR}")
    out[readout] = ratio_pub


def _c0_running(coll: Collector, ref: ReferenceWorld, inputs: Inputs, world: World, where: str) -> None:
    """CRITERIA.md §3.2's running check on the references' own extents, at every rung's S (SPEC.md §9.8)."""
    running = world.judged.get("running")
    if not running:
        return
    carrying = running_carriers(world)
    multiple = float(running["multiple"])
    last = len(world.samples) - 1
    for c in ref.copies:
        at0 = {name: c.series[name][0] for name in world.series}
        at_t = {name: c.series[name][last] for name in world.series}
        for h in world.rungs:
            s_steps = steps(world.samples[last], h)
            for readout in running["readouts"]:
                ident = carrying[readout]
                bound = identity_at(world.identities[ident], at_t, at0, s_steps).bound
                value = abs(Fraction(at_t[readout])) if readout == "moved" else Fraction(at_t[readout])
                if not value > multiple * bound:
                    coll.fault("running check", f"{where}/copies/{c.copy}/{readout} at h={h!r}",
                               f"{float(value)!r} not above {multiple:g} x {float(bound)!r}")


def running_carriers(world: World) -> dict[str, str]:
    """CRITERIA.md §3.2: X carries xi_1, Y carries xi_2, S node carries moved."""
    return {"xi_1": "X", "xi_2": "Y", "moved": "S node"}


def _c0_plants(coll: Collector, ref: ReferenceWorld, inputs: Inputs, world: World, where: str,
               summary: dict) -> None:
    entries: dict[tuple[str, str | None, str], list[dict]] = {}
    for i, entry in enumerate(ref.plants):
        w = f"{where}/plants/{i}"
        plant = need(coll, entry, "plant", "string", w)
        family = need(coll, entry, "family", "string", w, nullable=True)
        check = need(coll, entry, "check", "string", w)
        need(coll, entry, "distance", "number", w)
        need(coll, entry, "expected_tolerance", "number", w)
        need(coll, entry, "margin", "number", w, nullable=True)
        need(coll, entry, "no_margin", "bool", w)
        if _MISSING in (plant, family, check):
            continue
        entries.setdefault((plant, family, check), []).append(entry)
    margins = []
    for plant in inputs.plants_of(world.name):
        fams: list[str | None] = [None] if plant.kind == "record" else list(plant.families)
        for fam in fams:
            for cls, check in plant.must_fail:
                key = (plant.id, fam, check)
                w = f"{where}/plants/{plant.id}/{fam}/{check}"
                found = entries.get(key, [])
                if not found:
                    coll.fault("missing expected value", w, "no plants entry")
                    continue
                if len(found) > 1:
                    coll.fault("missing expected value", w, f"{len(found)} plants entries")
                entry = found[0]
                if not all(sj.is_number(entry.get(k)) for k in ("distance", "expected_tolerance")):
                    continue
                distance = float(entry["distance"])
                tolerance = float(entry["expected_tolerance"])
                margin = entry.get("margin")
                no_margin = entry.get("no_margin")
                row = {"plant": plant.id, "family": fam, "check": check, "distance": distance,
                       "expected_tolerance": tolerance, "margin": margin}
                margins.append(row)
                if plant.no_margin:
                    if no_margin is not True:
                        coll.finding("plant margin", w, "a no_margin plant without no_margin true")
                    if cls == "E" and not distance > 0:
                        coll.fault("plant margin", w, "a class E plant with a zero distance")
                    _plant_recompute(coll, ref, inputs, world, plant, fam, cls, check, distance, tolerance, w)
                    continue
                if no_margin is not False:
                    coll.finding("plant margin", w, "no_margin is not false")
                if not sj.is_number(margin):
                    coll.fault("missing expected value", w, "no margin")
                    continue
                if not margin >= PLANT_MARGIN:
                    coll.fault("plant margin", w, f"margin {margin!r} below 10 (1 - 1e-9)")
                if tolerance > 0:
                    coll.compare(f"{w}/margin", margin, distance / tolerance, REL_RECOMPUTE, "recomputed margin")
                # the judge's recomputation of the expected tolerance and the distance
                _plant_recompute(coll, ref, inputs, world, plant, fam, cls, check, distance, tolerance, w)
    summary["plants"] = margins


def _plant_recompute(coll: Collector, ref: ReferenceWorld, inputs: Inputs, world: World, plant, fam, cls: str,
                     check: str, distance: float, tolerance: float, w: str) -> None:
    sizing = ref.sizing
    if cls == "S" and fam is not None:
        tau_pub = sizing.get(fam, {}).get(check, {}).get("tau") if isinstance(sizing.get(fam), dict) else None
        if sj.is_number(tau_pub):
            coll.compare(f"{w}/expected_tolerance", tolerance, tau_pub, REL_RECOMPUTE, "recomputed margin")
        if plant.base == "P4":
            shift = ref.planted.get(plant.id, {}).get(fam, {}).get("shift_s")
            if shift is not None:
                coll.compare(f"{w}/distance", distance, shift, REL_RECOMPUTE, "recomputed margin")
                if sj.is_number(tau_pub):
                    coll.compare(f"{w}/shift_s", shift, 10.0 * tau_pub, 1e-12, "recomputed margin")
            return
        if plant.kind == "engine":
            mutant = sizing.get("mutant", {}).get(fam, {})
            if isinstance(mutant, dict) and isinstance(mutant.get("E"), list) and mutant["E"]:
                coll.compare(f"{w}/distance (P3, read at its coarsest rung)", distance, max(mutant["E"]),
                             REL_RECOMPUTE, None)
            return
        planted = ref.planted.get(plant.id, {}).get(fam)
        if isinstance(planted, list):
            d = plant_distance(ref.copies, planted, check)
            if d is None:
                coll.fault("plant margin", w, "no common entry between the honest and planted references")
            else:
                coll.compare(f"{w}/distance", distance, d, REL_RECOMPUTE, "recomputed margin")
                if sj.is_number(tau_pub) and tau_pub > 0 and not d / tau_pub >= PLANT_MARGIN:
                    coll.finding("plant margin", w, f"recomputed margin {d / tau_pub!r} below 10 (1 - 1e-9)")
        return
    if cls == "R" and plant.kind == "reference" and check == "t_events":
        planted = ref.planted.get(plant.id, {}).get(fam)
        if isinstance(planted, list):
            h1 = world.rungs[0]
            best = None
            for c, pc in zip(ref.copies, planted):
                for k in range(min(c.K, pc.K_all)):
                    dist = abs(pc.times[k] - c.times[k])
                    tol = e_round(M_TIME, steps(world.end_s, h1), world.end_s) + c.accuracy_s
                    if best is None or dist / tol > best[0] / best[1]:
                        best = (dist, tol)
            if best is not None:
                coll.compare(f"{w}/margin (R, farthest event)", distance / tolerance if tolerance else None,
                             best[0] / best[1], 1e-6, None)
                if not best[0] / best[1] >= PLANT_MARGIN:
                    coll.finding("plant margin", w, "recomputed margin below 10 (1 - 1e-9)")
        return
    if plant.kind == "record" and cls == "E":
        coll.compare(f"{w}/distance (E, entries that differ)", distance,
                     float(record_plant_event_distance(ref, world, plant)), 0.0, "recomputed margin")
        return
    if plant.kind == "record" and cls == "R":
        margin = record_plant_margin(ref, inputs, world, plant, check)
        if margin is not None:
            coll.compare(f"{w}/margin (record, copy 0 of the reference)", distance / tolerance if tolerance else None,
                         margin, 1e-6, None)
            if not margin >= PLANT_MARGIN:
                coll.finding("plant margin", w, f"recomputed margin {margin!r} below 10 (1 - 1e-9)")


def p5_tolerance_readings(ref: ReferenceWorld, inputs: Inputs, world: World) -> list[dict]:
    """The lead's ruling 4: for each class R plant on the event times (P5), the published tolerance and what the
    other reading of S gives at the same event. The published one is read at the judged event the farthest away
    (|planted - honest| over e_round(S = T/h_1) + the copy's accuracy); S = t_k/h_1 is evaluated there."""
    out = []
    h1 = world.rungs[0]
    for entry in ref.plants:
        if not (isinstance(entry, dict) and entry.get("check") == "t_events" and entry.get("family") in
                ref.planted.get(entry.get("plant"), {})):
            continue
        planted = ref.planted[entry["plant"]][entry["family"]]
        if not isinstance(planted, list):
            continue
        best = None
        for c, pc in zip(ref.copies, planted):
            tol_t = e_round(M_TIME, steps(world.end_s, h1), world.end_s) + c.accuracy_s
            for k in range(min(c.K, pc.K_all)):
                r = abs(pc.times[k] - c.times[k]) / tol_t
                if best is None or r > best[0]:
                    best = (r, c, k)
        if best is None:
            continue
        _, c, k = best
        t_k = c.times[k]
        s_tk = t_k / h1
        out.append({
            "plant": entry["plant"], "family": entry["family"],
            "published_tolerance": entry.get("expected_tolerance"),
            "event": {"copy": c.copy, "k": k, "t_k": t_k},
            "S_T_over_h": float(steps(world.end_s, h1)),
            "tolerance_S_T_over_h": e_round(M_TIME, steps(world.end_s, h1), world.end_s) + c.accuracy_s,
            "S_tk_over_h": s_tk,
            "tolerance_S_tk_over_h": M_TIME * (s_tk + 1.0) * 2.0**-53 * world.end_s + c.accuracy_s,
        })
    return out


def plant_distance(honest: list[RefCopy], planted: list[RefCopy], readout: str) -> float | None:
    """CRITERIA.md §6.2: the pooled RMS between the honest and planted references over the common entries (for
    t_events the events k < K_c that the planted reference also lists; for a row or book every sample t > 0)."""
    diffs = []
    for c, pc in zip(honest, planted):
        if readout == "t_events":
            for k in range(min(c.K, pc.K_all)):
                diffs.append(pc.times[k] - c.times[k])
        else:
            for i, t in enumerate(c.samples):
                if t > 0:
                    diffs.append(pc.series[readout][i] - c.series[readout][i])
    return pooled_rms(diffs)


def record_plant_margin(ref: ReferenceWorld, inputs: Inputs, world: World, plant, check: str) -> float | None:
    """A record plant's margin on the references' own copy 0 (S = t/h_1, s_id of the honest terms, the sample of
    the largest ratio): how far the edited record departs from the honest one over the honest bound."""
    edit = edit_module.parse(plant.change)
    c = ref.copies[0]
    if edit.form == "remove_event":
        return None
    series, _, _ = edit_module.apply(edit, c.series, {"time_s": [], "channel": [], "counts_after": []}, None, c.K)
    return _record_margin_from(ref, inputs, world, c, series, check)


def record_plant_event_distance(ref: ReferenceWorld, world: World, plant) -> int:
    """P8's distance (CRITERIA.md §6.2, class E): the judged events of copy 0 whose channel or counts differ from the
    reference's after the edit."""
    c = ref.copies[0]
    edit = edit_module.parse(plant.change)
    _, events, _ = edit_module.apply(edit, {}, {"time_s": list(c.times), "channel": list(c.channels),
                                                "counts_after": [list(x) for x in c.counts]}, c.K_all, c.K)
    differ = 0
    for k in range(c.K):
        if k >= len(events["channel"]) or events["channel"][k] != c.channels[k] or tuple(
                events["counts_after"][k]) != tuple(c.counts[k]):
            differ += 1
    return differ


def _record_margin_from(ref: ReferenceWorld, inputs: Inputs, world: World, c: RefCopy, series: dict,
                        check: str) -> float | None:
    h1 = world.rungs[0]
    best = None
    if check.startswith("identity "):
        terms = world.identities[check[len("identity "):]]
        at0_h = {n: c.series[n][0] for n in world.series}
        at0_e = {n: series[n][0] for n in world.series}
        for i, t in enumerate(c.samples):
            s_steps = steps(t, h1)
            honest = identity_at(terms, {n: c.series[n][i] for n in world.series}, at0_h, s_steps)
            edited = identity_at(terms, {n: series[n][i] for n in world.series}, at0_e, s_steps)
            if honest.bound == 0:
                continue
            r = float(abs(edited.residual - honest.residual) / honest.bound)
            best = r if best is None else max(best, r)
        return best
    if check.startswith("start "):
        readout = check[len("start "):]
        declared = inputs.start_value(world.name, readout)
        value = start_at(series[readout][0], declared)
        if value.bound == 0:
            return None
        return float(abs(Fraction(series[readout][0]) - Fraction(c.series[readout][0])) / value.bound)
    return None


def load_draws(path: str, world: World, coll: Collector, where: str) -> dict[int, list[float]] | None:
    """The first draws u1 of each copy (LAWS.md §6), read from the spec's draws table; its seeds are checked."""
    loaded = sj.load_file(path)
    if list(sj.problems(loaded.data)):
        coll.finding("draws", where, "the draws file has a duplicate key or a non-finite number")
        return None
    out: dict[int, list[float]] = {}
    for entry in loaded.data["worlds"][world.name]["copies"]:
        c = int(entry["copy"])
        if c >= world.copies or int(entry["seed"]) != world.seeds[c] or int(entry["site_index"]) != 0:
            coll.finding("draws", f"{where}/{c}", "the draws table's copy, seed or site does not match the inputs")
            return None
        out[c] = [float.fromhex(x) for x in entry["u1"]]
    if sorted(out) != list(range(world.copies)):
        coll.finding("draws", where, "the draws table does not hold every copy")
        return None
    return out
