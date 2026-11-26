"""The scorer: CRITERIA.md §3 (E, R, S, D, the pair), §4 (faults), §6 (plants), §7 (retry) and §8 (verdicts).

Outcomes are `pass`, `fail`, `inconclusive` and `unformed` (an unformed judged entry makes its family inconclusive,
CRITERIA.md §3.0). Fail beats inconclusive beats pass. "Unformed is not unread": what can be compared is compared,
and a miss fails, except where nothing of a run is judged (its echo or its table's hash departs).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any

from . import edits as edit_module
from .echo import echo_departures
from .reference import ReferenceWorld, RefCopy
from .registry import (M_ROW, M_TIME, ORDER_HALF_WINDOW, P3_WINDOW, PAIR_FACTOR, REL_TIME, Inputs, RunSpec, World,
                       e_round, relative_equal, steps)
from .rules import check_trace, identity_at, ledger_fails, ratio, same_bits, start_at
from .stats import ladder, log_slope, pooled_rms, round_bound, tau
from .table import LIE_PATCH_ID, REFUSAL_KINDS, Entry, Issue, TableFile, read_entry

RETRY_KIND = "fr43 part 3 co-writers retry, version 2"
RECORD_KIND = "fr43 part 3 co-writers judge record, version 1"
LIE_VARIANT = "second halves in declared order"
RESTART_VARIANT = "restart"
ORDER = {"fail": 3, "inconclusive": 2, "unformed": 2, "pass": 1}


def worst(outcomes: list[str]) -> str:
    """Fail beats inconclusive beats pass; nothing passes empty."""
    if not outcomes:
        return "inconclusive"
    top = max(outcomes, key=lambda o: ORDER[o])
    return "inconclusive" if top == "unformed" else top


@dataclass
class RunState:
    spec: RunSpec
    entries: list[Entry] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)
    in_missing: bool = False

    @property
    def missing(self) -> bool:
        return not self.entries

    @property
    def listed_twice(self) -> bool:
        return len(self.entries) > 1 or (self.in_missing and bool(self.entries))

    def single(self) -> Entry | None:
        return self.entries[0] if len(self.entries) == 1 else None


def effects(state: RunState, entry: Entry | None) -> set[str]:
    out = {i.effect for i in state.issues}
    if entry is not None:
        out |= entry.effects()
    if state.missing:
        out.add("missing")
    if state.listed_twice:
        out.add("refused")
    return out


def nothing_judged(state: RunState, entry: Entry | None) -> bool:
    return entry is None or "nothing" in effects(state, entry) or state.missing


def refused_other(state: RunState, entry: Entry | None) -> bool:
    """Refused by a row other than provenance and a shared record hash (or missing, or not complete)."""
    e = effects(state, entry)
    return bool(e & {"refused", "not_complete", "missing", "nothing"})


def refused_any(state: RunState, entry: Entry | None) -> bool:
    e = effects(state, entry)
    return bool(e & {"refused", "not_complete", "missing", "nothing", "provenance", "shared"})


def completed(state: RunState, entry: Entry | None) -> bool:
    return entry is not None and entry.status == "completed" and "not_complete" not in effects(state, entry)


def refusal_kind(state: RunState, entry: Entry | None) -> str | None:
    for issue in (entry.issues if entry else []):
        if issue.effect == "not_complete":
            return issue.kind
    return None


@dataclass
class Result:
    """One judged entry of the record (CRITERIA.md §8)."""

    family: str | None
    run: str | None
    entry: str
    cls: str
    outcome: str
    statistic: Any = None
    tolerance: Any = None
    note: str = ""
    extra: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        r = None
        if isinstance(self.statistic, (int, float)) and isinstance(self.tolerance, (int, float)):
            r = ratio(self.statistic, self.tolerance)
        out = {"family": self.family, "run": self.run, "entry": self.entry, "class": self.cls,
               "outcome": self.outcome, "statistic": self.statistic, "tolerance": self.tolerance, "ratio": r,
               "note": self.note}
        out.update(self.extra)
        return out


def compared_outcome(miss: bool, formed: bool) -> str:
    """What can be compared is compared: a miss fails; else pass where formed, else unformed."""
    if miss:
        return "fail"
    return "pass" if formed else "unformed"


class Judge:
    def __init__(self, inputs: Inputs, references: dict[str, ReferenceWorld | None],
                 operators: dict[str, list[str]], registration_revision: str | None, rehearsal: bool,
                 retry_owed: dict | None = None) -> None:
        self.inputs = inputs
        self.references = references
        self.operators = operators
        self.registration_revision = registration_revision
        self.rehearsal = rehearsal
        self.retry_owed = retry_owed
        self.owed_families = set(retry_owed["families"]) if retry_owed else set()
        self.tables: list[TableFile] = []
        self.states: dict[str, RunState] = {}
        self.records: list[dict] = []  # refusals, flags and ignored names
        self.results: list[Result] = []

    # ---- reading ----

    def registered_specs(self) -> dict[str, RunSpec]:
        specs = dict(self.inputs.runs)
        for fam_id in sorted(self.owed_families):
            fam = self.inputs.families[fam_id]
            for c in range(self.inputs.worlds[fam.world].copies):
                spec = self.inputs.retry_spec(fam_id, c)
                specs[spec.name] = spec
        return specs

    def add_tables(self, tables: list[TableFile]) -> None:
        self.tables.extend(tables)

    def read(self) -> None:
        specs = self.registered_specs()
        self.states = {name: RunState(spec=spec) for name, spec in specs.items()}
        retry_names = {Inputs.retry_name(f, c): f.id for f in self.inputs.families.values() if f.retry_rung
                       for c in range(self.inputs.worlds[f.world].copies)}
        for table in self.tables:
            table_effect = table.effect()
            for issue in table.issues:
                self.records.append({"table": table.name, **issue.as_dict()})
            for name in table.missing:
                if name in self.states:
                    self.states[name].in_missing = True
            for entry in table.entries:
                if entry.name not in self.states:
                    if entry.name in retry_names:
                        self.records.append({"run": entry.name, "row": "unowed retry", "effect": "flag",
                                             "message": "an unowed retry run: recorded, flagged, not judged"})
                    else:
                        self.records.append({"run": entry.name, "row": "unregistered", "effect": "ignored",
                                             "message": "a run name no inputs list and no owed retry names"})
                    continue
                state = self.states[entry.name]
                kind = self.inputs.worlds[state.spec.world].kind
                read_entry(entry, kind)
                if table.world is not None and table.world != state.spec.world:
                    entry.add("echo", "nothing", "table", f"a {state.spec.world} run in {table.name}")
                if table_effect == "nothing":
                    entry.add("hash", "nothing", table.name, "its table's hash departs")
                elif table_effect == "refused":
                    entry.add("top-level key", "refused", table.name, "its table's top level is refused")
                state.entries.append(entry)
        for state in self.states.values():
            if state.missing:
                state.issues.append(Issue("missing", "missing", state.spec.name,
                                          "in missing" if state.in_missing else "in neither runs nor missing"))
            if state.listed_twice:
                state.issues.append(Issue("listed twice", "refused", state.spec.name,
                                          f"{len(state.entries)} entries" + (" and in missing" if state.in_missing
                                                                             else "")))
            for entry in state.entries:
                self._semantic(state, entry)
        self._shared_hashes()
        self._resumed_runs()

    def _semantic(self, state: RunState, entry: Entry) -> None:
        spec = state.spec
        raw = entry.raw if isinstance(entry.raw, dict) else {}
        world = self.inputs.worlds[spec.world]
        if entry.status == "refused" and raw.get("inputs") is None:
            entry.add("refused run", "flag", "inputs", "no echo: refused before its definition was parsed")
        else:
            departures = echo_departures(self.inputs, spec, raw, self.operators.get(spec.family))
            if departures:
                entry.add("echo", "nothing", "echo", "; ".join(departures[:6]) + (" ..." if len(departures) > 6
                                                                                     else ""))
        refusal = raw.get("refusal")
        if entry.status == "completed" and refusal is not None:
            kind = refusal.get("kind") if isinstance(refusal, dict) else None
            entry.add("status", "not_complete", "refusal", "a completed run with a refusal",
                      kind if kind in REFUSAL_KINDS else "harness")
        elif entry.status == "refused":
            if refusal is None:
                entry.add("status", "not_complete", "refusal", "a refused run without a refusal", "harness")
            else:
                kind = refusal.get("kind") if isinstance(refusal, dict) else None
                if kind not in REFUSAL_KINDS:
                    entry.add("refused run", "flag", "refusal/kind", f"{kind!r} is not a kind of TABLE.md §3")
                    kind = "harness"
                entry.add("refused run", "not_complete", "refusal", f"refused with kind {kind}", kind)
        if entry.events_total is not None and entry.trace_capacity is not None and (
                entry.events_total > entry.trace_capacity):
            entry.add("truncated", "not_complete", "events_total", "above trace_capacity", "harness")
        resumed = spec.variant == RESTART_VARIANT
        if entry.status == "completed" and not resumed and entry.t is not None:
            if not _samples_equal(entry.t, world.samples):
                entry.add("samples", "refused", "t", "not the registered samples_s")
        is_lie = spec.variant == LIE_VARIANT
        patch = raw.get("host_patch")
        if is_lie and (not isinstance(patch, dict) or patch.get("id") != LIE_PATCH_ID):
            entry.add("host_patch/restart", "refused", "host_patch", "the Lie plant's run without its patch id")
        if not is_lie and patch is not None:
            entry.add("host_patch/restart", "refused", "host_patch", "a host_patch on a run that is not the Lie plant's")
        if resumed and raw.get("restart") is None:
            entry.add("host_patch/restart", "refused", "restart", "a resumed run with a null restart")
        if not resumed and raw.get("restart") is not None:
            entry.add("host_patch/restart", "refused", "restart", "a restart on a run that is not a resumed one")
        source = raw.get("source")
        if isinstance(source, dict):
            if source.get("checkout_dirty") is True:
                entry.add("provenance", "provenance", "source/checkout_dirty", "a dirty checkout")
            if not self.rehearsal and isinstance(source.get("engine_revision"), str) and (
                    source["engine_revision"] != self.registration_revision):
                entry.add("provenance", "provenance", "source/engine_revision", "not the registration tag's revision")
        # recorded-only keys against the grid (flagged)
        if not resumed and sj_int(raw.get("steps")) is not None and sj_int(raw.get("steps")) != _grid_steps(
                world, spec.step):
            entry.add("recorded-only leaf", "flag", "steps", f"{raw.get('steps')} against the grid")
        echo_samples = raw.get("samples_echo")
        if isinstance(echo_samples, list) and not _samples_equal_any(echo_samples, world.samples):
            entry.add("recorded-only leaf", "flag", "samples_echo", "not the registered samples_s")

    def _shared_hashes(self) -> None:
        by_hash: dict[str, list[tuple[RunState, Entry]]] = {}
        for state in self.states.values():
            for entry in state.entries:
                if entry.record_sha256 is not None:
                    by_hash.setdefault(entry.record_sha256, []).append((state, entry))
        for digest, holders in by_hash.items():
            if len(holders) > 1:
                names = sorted({s.spec.name for s, _ in holders})
                for state, entry in holders:
                    entry.add("shared record hash", "shared", "record_sha256", f"shared with {names}")

    # ---- the restart (CRITERIA.md §3.1) ----

    def restart_pairs(self) -> list[tuple[RunState, RunState]]:
        out = []
        for world_name, block in (self.inputs.data.get("restart") or {}).items():
            uninterrupted = self.states.get(block["run"])
            resumed = [s for s in self.states.values() if s.spec.variant == RESTART_VARIANT
                       and s.spec.world == world_name and s.spec.name.startswith(block["run"] + " ")]
            for state in resumed:
                if uninterrupted is not None:
                    out.append((uninterrupted, state))
        return out

    def _resumed_runs(self) -> None:
        self.restart_checks: dict[str, dict] = {}
        for unint, resumed in self.restart_pairs():
            world = self.inputs.worlds[resumed.spec.world]
            time_reg = float((self.inputs.data["restart"][resumed.spec.world])["time_s"])
            info: dict[str, Any] = {"refusals": [], "differences": [], "formed": True}
            self.restart_checks[resumed.spec.name] = info
            u = unint.single()
            for r in resumed.entries:
                if nothing_judged(resumed, r):
                    info["formed"] = False
                    continue
                restart = r.restart
                if restart is None or not relative_equal(float(restart["time_s"]), time_reg, REL_TIME):
                    info["refusals"].append("restart.time_s departs from the registered checkpoint")
                if u is None or nothing_judged(unint, u) or u.times is None or u.t is None:
                    info["formed"] = False
                    continue
                n_before = sum(1 for t in u.times if t <= time_reg)
                if r.first_index is None or r.first_index != n_before:
                    info["refusals"].append(f"first_index {r.first_index} against {n_before} events at or before "
                                            f"the checkpoint")
                later_samples = [t for t in world.samples if t >= time_reg]
                if r.t is None or len(r.t) != len(later_samples) or not all(
                        relative_equal(a, b, REL_TIME) for a, b in zip(r.t, later_samples)):
                    info["refusals"].append("t does not list each registered sample at and after the checkpoint")
                if r.times is None or len(r.times) < len(u.times) - n_before:
                    info["refusals"].append("does not list every event of the uninterrupted run after the checkpoint")
                for reason in info["refusals"]:
                    r.add("resumed run", "refused", "restart", reason)
                info["differences"] = self._restart_differences(u, r, world, later_samples)
            if not resumed.entries:
                info["formed"] = False

    def _restart_differences(self, u: Entry, r: Entry, world: World, later: list[float]) -> list[str]:
        out = []
        if r.t is not None and u.t is not None:
            for i, t in enumerate(r.t):
                j = _index_of(u.t, t)
                if j is None:
                    continue
                for name, values in r.series.items():
                    other = u.series.get(name)
                    if other is not None and not same_bits(values[i], other[j]):
                        out.append(f"{name} at t = {t!r}: {values[i]!r} against {other[j]!r}")
        if r.times is not None and r.first_index is not None and u.times is not None:
            for i, t in enumerate(r.times):
                k = r.first_index + i
                if k >= len(u.times):
                    out.append(f"event {k}: the uninterrupted run has no such event")
                    continue
                if not same_bits(t, u.times[k]):
                    out.append(f"event {k} time: {t!r} against {u.times[k]!r}")
                if r.channels and u.channels and r.channels[i] != u.channels[k]:
                    out.append(f"event {k} channel")
                if r.counts and u.counts and tuple(r.counts[i]) != tuple(u.counts[k]):
                    out.append(f"event {k} counts")
        if r.events_total is not None and u.events_total is not None and r.events_total != u.events_total:
            out.append(f"events_total {r.events_total} against {u.events_total}")
        return out

    # ---- the reference's view of a run ----

    def ref_copy(self, world: str, copy: int) -> RefCopy | None:
        ref = self.references.get(world)
        return ref.copies[copy] if ref is not None and copy < len(ref.copies) else None

    def counts_before(self, state: RunState, entry: Entry) -> tuple[int, ...] | None:
        world = self.inputs.worlds[state.spec.world]
        if state.spec.variant != RESTART_VARIANT:
            return tuple(world.initial_counts)
        unint = self.uninterrupted_of(state)
        u = unint.single() if unint else None
        if entry.first_index is None or u is None or u.counts is None:
            return None
        if entry.first_index == 0:
            return tuple(world.initial_counts)
        if entry.first_index - 1 < len(u.counts):
            return tuple(u.counts[entry.first_index - 1])
        return None

    def uninterrupted_of(self, state: RunState) -> RunState | None:
        block = (self.inputs.data.get("restart") or {}).get(state.spec.world)
        return self.states.get(block["run"]) if block else None

    def t0_row(self, state: RunState, entry: Entry) -> dict[str, float] | None:
        """The t = 0 row and books (a resumed run reads its uninterrupted run's)."""
        source_state, source = state, entry
        if state.spec.variant == RESTART_VARIANT:
            unint = self.uninterrupted_of(state)
            source_state = unint
            source = unint.single() if unint else None
            if source is None or nothing_judged(unint, source):
                return None
        if source.t is None or not source.t or source.t[0] != 0.0:
            return None
        return {name: values[0] for name, values in source.series.items()}

    # ---- E, R and D of one run ----

    def judge_run(self, state: RunState, family: str | None, scored_for: str) -> list[Result]:
        """Every E, R and D entry of each entry under the run's name. `scored_for`: 'arm', 'plant' or 'support'."""
        out: list[Result] = []
        spec = state.spec
        world = self.inputs.worlds[spec.world]
        ref = self.ref_copy(spec.world, spec.copy)
        if state.missing:
            for name in self._entry_names(world, spec):
                out.append(Result(family, spec.name, name, _cls(name), "unformed", note="the run is missing",
                                  extra={"scored_for": scored_for}))
            return out
        for entry in state.entries:
            nothing = nothing_judged(state, entry)
            formed_run = not refused_any(state, entry)
            done = completed(state, entry)
            note = "" if formed_run else "refused: " + ", ".join(sorted(effects(state, entry) - {"flag", "leaf"}))
            if nothing:
                for name in self._entry_names(world, spec):
                    out.append(Result(family, spec.name, name, _cls(name), "unformed", note="nothing judged: " + note))
                continue
            resumed = spec.variant == RESTART_VARIANT
            # E: trace
            if ref is None or entry.times is None or entry.channels is None or entry.counts is None or (
                    entry.first_index is None):
                out.append(Result(family, spec.name, "E trace", "E", "unformed", note="a leaf of the trace is missing"))
            else:
                trace = check_trace(world, entry.times, entry.channels, entry.counts, entry.first_index,
                                    entry.events_total, ref.K, ref.channels, ref.counts,
                                    self.counts_before(state, entry), done, not resumed)
                formed = formed_run and "events_total" not in entry.bad_leaves and (
                    self.counts_before(state, entry) is not None)
                out.append(Result(family, spec.name, "E trace", "E", compared_outcome(not trace.passes, formed),
                                  statistic=trace.differs_from_reference, tolerance=0,
                                  note="; ".join(trace.fails[:4]) or note,
                                  extra={"contradicts": trace.contradicts, "too_few": trace.too_few}))
            # E: ledger
            led_fails = []
            if entry.ledger is not None:
                led_fails += ledger_fails(world, entry.ledger, [])
            if entry.counts is not None:
                led_fails += ledger_fails(world, None, entry.counts)
            formed = formed_run and entry.ledger is not None and entry.counts is not None
            out.append(Result(family, spec.name, "E ledger", "E", compared_outcome(bool(led_fails), formed),
                              note="; ".join(led_fails[:4]) or note))
            # R: start (not of a resumed run)
            if not resumed:
                for readout in world.start:
                    declared = self.inputs.start_value(spec.world, readout)
                    values = entry.series.get(readout)
                    if values is None or entry.t is None or not entry.t or entry.t[0] != 0.0:
                        out.append(Result(family, spec.name, f"R start {readout}", "R", "unformed",
                                          note="no t = 0 value"))
                        continue
                    sv = start_at(values[0], declared)
                    out.append(Result(family, spec.name, f"R start {readout}", "R",
                                      compared_outcome(not sv.passes, formed_run),
                                      statistic=float(sv.distance), tolerance=float(sv.bound), note=note))
            # R: identities at every sample
            out.extend(self._identities(state, entry, family, formed_run, note))
            # R: W5-exact's event times
            if "t_events" in world.judged.get("R", []):
                out.append(self._exact_times(state, entry, family, formed_run, done, note))
            # D
            kind = refusal_kind(state, entry)
            if spec.role == "judged" and kind == "check":
                out.append(Result(family, spec.name, "D", "D", "fail", note="refused with kind check"))
            elif done:
                out.append(Result(family, spec.name, "D", "D", "pass"))
            else:
                out.append(Result(family, spec.name, "D", "D", "unformed", note=f"did not complete ({kind})"))
        for r in out:
            r.extra["scored_for"] = scored_for
        return out

    def _entry_names(self, world: World, spec: RunSpec) -> list[str]:
        names = ["E trace", "E ledger"]
        if spec.variant != RESTART_VARIANT:
            names += [f"R start {r}" for r in world.start]
        names += [f"R identity {i}" for i in world.judged.get("identities", [])]
        if "t_events" in world.judged.get("R", []):
            names.append("R t_events")
        names.append("D")
        return names

    def _identities(self, state: RunState, entry: Entry, family: str | None, formed_run: bool,
                    note: str) -> list[Result]:
        spec = state.spec
        world = self.inputs.worlds[spec.world]
        at0 = self.t0_row(state, entry)
        running_ok, running_note = self._running(state, entry)
        out = []
        for ident in world.judged.get("identities", []):
            terms = world.identities[ident]
            needed = {name for name, _, _ in terms}
            if entry.t is None or at0 is None or any(n not in entry.series or n not in at0 for n in needed):
                out.append(Result(family, spec.name, f"R identity {ident}", "R", "unformed",
                                  note="a leaf it reads is missing, or no t = 0 row"))
                continue
            worst_ratio = 0.0
            miss = False
            worst_value = None
            registered = _registered_times(entry, world)
            for i, t in enumerate(entry.t):
                if spec.variant == RESTART_VARIANT and t == 0.0:
                    continue
                at_t = {n: entry.series[n][i] for n in needed}
                value = identity_at(terms, at_t, at0, steps(registered[i], spec.step))
                if value.ratio >= worst_ratio:
                    worst_ratio = value.ratio
                    worst_value = value
                if not value.passes:
                    miss = True
            formed = formed_run and running_ok
            outcome = compared_outcome(miss, formed)
            out.append(Result(family, spec.name, f"R identity {ident}", "R", outcome,
                              statistic=float(abs(worst_value.residual)) if worst_value else None,
                              tolerance=float(worst_value.bound) if worst_value else None,
                              note=note if formed_run else note, extra={"running_check": running_note}
                              if running_note else {}))
        return out

    def _running(self, state: RunState, entry: Entry) -> tuple[bool, str]:
        """W5-exact's running check (CRITERIA.md §3.2): True where the identities may be formed."""
        world = self.inputs.worlds[state.spec.world]
        running = world.judged.get("running")
        if not running:
            return True, ""
        ref = self.ref_copy(state.spec.world, state.spec.copy)
        at0 = self.t0_row(state, entry)
        if entry.t is None or not entry.t or at0 is None or ref is None:
            return False, "the running check cannot be formed"
        last = len(entry.t) - 1
        t_last = _registered_time(world, entry.t[last])
        if t_last != world.samples[-1]:
            return False, "no last sample"
        carriers = {"xi_1": "X", "xi_2": "Y", "moved": "S node"}
        reasons = []
        for readout in running["readouts"]:
            terms = world.identities[carriers[readout]]
            needed = {n for n, _, _ in terms} | {readout}
            if any(n not in entry.series for n in needed):
                reasons.append(f"{readout} missing")
                continue
            at_t = {n: entry.series[n][last] for n in needed}
            bound = identity_at(terms, at_t, at0, steps(t_last, state.spec.step)).bound
            value = Fraction(entry.series[readout][last])
            reference = Fraction(ref.series[readout][-1])
            size = abs(value) if readout == "moved" else value
            if not size > Fraction(running["multiple"]) * bound:
                reasons.append(f"{readout} not above {running['multiple']:g} times its identity's bound")
            if not (value * reference > 0 and abs(value) >= Fraction(running["fraction_of_reference"]) * abs(
                    reference)):
                reasons.append(f"{readout} below half of the reference's, or of another sign")
        return (not reasons), "; ".join(reasons)

    def _exact_times(self, state: RunState, entry: Entry, family: str | None, formed_run: bool, done: bool,
                     note: str) -> Result:
        spec = state.spec
        world = self.inputs.worlds[spec.world]
        ref = self.ref_copy(spec.world, spec.copy)
        if ref is None or entry.times is None or entry.first_index is None:
            return Result(family, spec.name, "R t_events", "R", "unformed", note="a leaf it reads is missing")
        bound_round = e_round(M_TIME, steps(world.end_s, spec.step), world.end_s)
        tol = bound_round + ref.accuracy_s
        miss = False
        worst_d = 0.0
        listed = 0
        for k in range(entry.first_index, ref.K):
            i = k - entry.first_index
            if i >= len(entry.times):
                break
            listed += 1
            d = abs(Fraction(entry.times[i]) - Fraction(ref.times[k]))
            worst_d = max(worst_d, float(d))
            if d > Fraction(tol):
                miss = True
        formed = formed_run and listed == ref.K - entry.first_index
        return Result(family, spec.name, "R t_events", "R", compared_outcome(miss, formed), statistic=worst_d,
                      tolerance=tol, note=note)

    # ---- S (CRITERIA.md §3.3) ----

    def s_rungs(self, family_id: str, retried: bool) -> list[tuple[float, bool]]:
        """(step, is_retry) of the rungs read: the family's n, or after a retry the finest n of n + 1."""
        fam = self.inputs.families[family_id]
        rungs = [(h, False) for h in fam.rungs]
        if retried:
            rungs = rungs[1:] + [(float(fam.retry_rung), True)]
        return rungs

    def run_at(self, family_id: str, step: float, copy: int, is_retry: bool) -> RunState | None:
        if is_retry:
            name = Inputs.retry_name(self.inputs.families[family_id], copy)
        else:
            name = self.inputs.judged_run(family_id, step, copy)
        return self.states.get(name) if name else None

    def series_of(self, state: RunState, readout: str, world: World) -> tuple[list[float] | None, str]:
        """The run's values at the entries of READOUTS.md §5 (k < K_c, or samples t > 0), or why there are none."""
        entry = state.single()
        if entry is None:
            return None, "missing or listed twice"
        ref = self.ref_copy(world.name, state.spec.copy)
        if readout == "t_events":
            if entry.times is None or entry.first_index is None or entry.channels is None or entry.counts is None:
                return None, "a leaf of the events is missing"
            trace = entry.__dict__.get("_trace_view")
            if trace is None:
                trace = check_trace(world, entry.times, entry.channels, entry.counts, entry.first_index,
                                    entry.events_total, ref.K, ref.channels, ref.counts, world.initial_counts,
                                    completed(state, entry), True)
                entry.__dict__["_trace_view"] = trace
            if trace.contradicts or trace.too_few or entry.first_index != 0 or len(entry.times) < ref.K:
                return None, "the record contradicts itself or lists fewer than K_c events"
            return entry.times[:ref.K], ""
        values = entry.series.get(readout)
        if values is None or entry.t is None:
            return None, f"{readout} is missing"
        out = []
        index = _sample_map(entry, world)
        for t in world.samples:
            if t <= 0:
                continue
            j = index.get(t)
            if j is None:
                return None, f"no sample at t = {t!r}"
            out.append(values[j])
        return out, ""

    def reference_values(self, world: World, copy: int, readout: str) -> list[float]:
        ref = self.ref_copy(world.name, copy)
        if readout == "t_events":
            return ref.times[:ref.K]
        return [ref.series[readout][i] for i, t in enumerate(world.samples) if t > 0]

    def s_entry(self, family_id: str, readout: str, p: int, retried: bool) -> Result:
        fam = self.inputs.families[family_id]
        world = self.inputs.worlds[fam.world]
        ref = self.references.get(world.name)
        named = readout in world.at_rounding()
        base = {"family": family_id, "run": None, "entry": f"S {readout}", "cls": "S"}
        if ref is None:
            return Result(**base, outcome="unformed", note="the world's reference is refused")
        rungs = self.s_rungs(family_id, retried)
        grid: list[list[list[float]]] = []
        not_compared = []
        compare_only = []
        for h, is_retry in rungs:
            row = []
            for c in range(world.copies):
                state = self.run_at(family_id, h, c, is_retry)
                if state is None:
                    not_compared.append(f"no run at h={h!r} c{c}")
                    row.append(None)
                    continue
                entry = state.single()
                if refused_other(state, entry):
                    not_compared.append(f"{state.spec.name}: refused or missing")
                    row.append(None)
                    continue
                values, why = self.series_of(state, readout, world)
                if values is None:
                    not_compared.append(f"{state.spec.name}: {why}")
                    row.append(None)
                    continue
                if refused_any(state, entry):
                    compare_only.append(state.spec.name)
                row.append(values)
            grid.append(row)
        if not_compared:
            return Result(**base, outcome="unformed", note="; ".join(not_compared[:4]))
        refs = [self.reference_values(world, c, readout) for c in range(world.copies)]
        e_n = pooled_rms([a - b for c in range(world.copies) for a, b in zip(grid[-1][c], refs[c])])
        d = []
        for j in range(len(rungs) - 1):
            d.append(pooled_rms([b - a for c in range(world.copies) for a, b in zip(grid[j][c], grid[j + 1][c])]))
        m = world.m_of(readout)
        scale = ref.scales[readout]
        hs = [h for h, _ in rungs]
        lad = ladder(p, hs, d, m, world.end_s, scale)
        e_ref = _e_ref(ref, readout, world)
        tol = tau(lad.est, e_ref, m, world.end_s, hs[-1], scale)
        size_ok = e_n <= tol
        window = lad.in_window(ORDER_HALF_WINDOW)
        extra = {"q": lad.q, "p": p, "used": lad.used, "d": d, "pairwise_orders": lad.pairwise_orders(),
                 "finest_triple_order": lad.finest_triple_order(), "named_at_rounding": named,
                 "rungs": hs, "e_ref": e_ref, "est": lad.est, "owes_retry": False, "retried": retried}
        if named:
            outcome = "pass" if size_ok else "fail"
            note = "named in at_rounding: judged by its size alone"
        elif lad.any_zero:
            outcome, note = "inconclusive", "a step difference is exactly zero (two rungs that are one series)"
        elif not lad.formed:
            outcome, note = "inconclusive", f"the order cannot be formed ({lad.used} used differences)"
        elif not window:
            outcome, note = "inconclusive", f"q = {lad.q:.4f} outside [p - 1/2, p + 1/2]"
            extra["owes_retry"] = not retried
        else:
            outcome = "pass" if size_ok else "fail"
            note = ""
        if compare_only and outcome != "fail":
            outcome = "unformed"
            extra["owes_retry"] = False  # an entry that is not formed owes no retry (CRITERIA.md §7)
            note = (note + "; " if note else "") + "refused by provenance or a shared record hash: compared, no miss"
        return Result(**base, outcome=outcome, statistic=e_n, tolerance=tol, note=note, extra=extra)

    # ---- the pair and W5-exact's two rungs (CRITERIA.md §3.5) ----

    def differ_entry(self, world: World, readout: str, runs_a: list[RunState | None], runs_b: list[RunState | None],
                     label: str, family: str | None) -> Result:
        ref = self.references.get(world.name)
        base = {"family": family, "run": None, "entry": label, "cls": "pair"}
        if ref is None:
            return Result(**base, outcome="unformed", note="the world's reference is refused")
        diffs = []
        for a, b in zip(runs_a, runs_b):
            for state in (a, b):
                if state is None or refused_any(state, state.single()):
                    return Result(**base, outcome="unformed", note="a run it reads is missing or refused")
            va, why_a = self.series_of(a, readout, world)
            vb, why_b = self.series_of(b, readout, world)
            if va is None or vb is None:
                return Result(**base, outcome="unformed", note=why_a or why_b)
            diffs.extend(x - y for x, y in zip(va, vb))
        rms = pooled_rms(diffs)
        threshold = PAIR_FACTOR * round_bound(world.m_of(readout), world.end_s, world.rungs[0], ref.scales[readout])
        if rms is None:
            return Result(**base, outcome="unformed", note="no entry")
        outcome = "pass" if rms > threshold else "inconclusive"
        return Result(**base, outcome=outcome, statistic=rms, tolerance=threshold,
                      note="" if outcome == "pass" else "the two are the same series")

    # ---- plants (CRITERIA.md §6) ----

    def honest_s(self, family_id: str, readout: str) -> Result | None:
        for r in self.s_results:
            if r.family == family_id and r.entry == f"S {readout}":
                return r
        return None

    def planted_values(self, plant_id: str, family_id: str, world: World, copy: int, readout: str) -> list[float]:
        ref = self.references[world.name]
        planted = ref.planted.get(plant_id, {}).get(family_id)
        honest = ref.copies[copy]
        if isinstance(planted, dict):  # P4: every reference event time moved by its shift
            return [t + planted["shift_s"] for t in honest.times[:honest.K]]
        pc = planted[copy]
        if readout == "t_events":
            return pc.times[:min(honest.K, pc.K_all)]
        return [pc.series[readout][i] for i, t in enumerate(world.samples) if t > 0]

    def score_reference_plant_s(self, plant, family_id: str, readout: str) -> dict:
        world = self.inputs.worlds[plant.world]
        honest = self.honest_s(family_id, readout)
        row = {"plant": plant.id, "family": family_id, "check": f"S {readout}"}
        if honest is None or honest.outcome != "pass":
            return {**row, "score": "unscorable", "note": "its honest entry did not pass"}
        rungs = self.s_rungs(family_id, honest.extra.get("retried", False))
        h, is_retry = rungs[-1]
        diffs, dist_diffs = [], []
        for c in range(world.copies):
            state = self.run_at(family_id, h, c, is_retry)
            values, _ = self.series_of(state, readout, world)
            planted = self.planted_values(plant.id, family_id, world, c, readout)
            honest_ref = self.reference_values(world, c, readout)
            n = min(len(values), len(planted))
            diffs.extend(values[i] - planted[i] for i in range(n))
            dist_diffs.extend(planted[i] - honest_ref[i] for i in range(n))
        e_planted = pooled_rms(diffs)
        distance = pooled_rms(dist_diffs)
        tol = honest.tolerance
        if e_planted is None:
            return {**row, "score": "unscorable", "note": "no common entry"}
        caught = e_planted > tol and not (distance is None or tol > distance)
        return {**row, "score": "caught" if caught else "not caught", "statistic": e_planted, "tolerance": tol,
                "ratio": ratio(e_planted, tol), "distance": distance, "margin": ratio(distance or 0.0, tol)}

    def score_p5(self, plant, family_id: str) -> dict:
        """A class R reference plant on W5-exact's event times."""
        world = self.inputs.worlds[plant.world]
        row = {"plant": plant.id, "family": family_id, "check": "R t_events"}
        honest = [r for r in self.run_results if r.family == family_id and r.entry == "R t_events"
                  and r.extra.get("scored_for") == "arm"]
        if not honest or any(r.outcome != "pass" for r in honest):
            return {**row, "score": "unscorable", "note": "its honest entries did not all pass"}
        fam = self.inputs.families[family_id]
        exceeds = 0
        best = 0.0
        distance_best = (0.0, 1.0)
        for h in fam.rungs:
            for c in range(world.copies):
                state = self.run_at(family_id, h, c, False)
                entry = state.single() if state is not None else None
                if entry is None or entry.times is None:
                    return {**row, "score": "unscorable", "note": "an honest run is missing or holds no times"}
                ref = self.ref_copy(world.name, c)
                planted = self.references[world.name].planted[plant.id][family_id][c]
                tol = e_round(M_TIME, steps(world.end_s, h), world.end_s) + ref.accuracy_s
                for k in range(min(ref.K, planted.K_all, len(entry.times))):
                    d = abs(entry.times[k] - planted.times[k])
                    best = max(best, d / tol)
                    if d > tol:
                        exceeds += 1
                    dist = abs(planted.times[k] - ref.times[k])
                    if dist / tol > distance_best[0] / distance_best[1]:
                        distance_best = (dist, tol)
        caught = exceeds > 0 and not (distance_best[1] > distance_best[0])
        return {**row, "score": "caught" if caught else "not caught", "statistic": best, "tolerance": 1.0,
                "entries_over_bound": exceeds, "distance": distance_best[0], "margin": ratio(*distance_best)}

    def score_p3(self, plant) -> list[dict]:
        world = self.inputs.worlds[plant.world]
        out = []
        p = world.order_of("t_events")
        for family_id in plant.families:
            row = {"plant": plant.id, "family": family_id, "check": "S t_events (order)"}
            honest = self.honest_s(family_id, "t_events")
            if honest is None or honest.outcome != "pass":
                out.append({**row, "score": "unscorable", "note": "its honest entry did not pass"})
                continue
            lie_runs = [s for s in self.states.values() if s.spec.role == "plant" and s.spec.variant == LIE_VARIANT
                        and s.spec.family == family_id]
            rungs = sorted({s.spec.step for s in lie_runs}, reverse=True)
            errors = []
            why = ""
            for h in rungs:
                diffs = []
                for c in range(world.copies):
                    found = [s for s in lie_runs if s.spec.step == h and s.spec.copy == c]
                    if len(found) != 1 or refused_any(found[0], found[0].single()):
                        why = f"a Lie run at h={h!r} c{c} is missing, refused or stopped"
                        break
                    values, reason = self.series_of(found[0], "t_events", world)
                    if values is None:
                        why = f"{found[0].spec.name}: {reason}"
                        break
                    diffs.extend(a - b for a, b in zip(values, self.reference_values(world, c, "t_events")))
                if why:
                    break
                errors.append(pooled_rms(diffs))
            if why:
                out.append({**row, "score": "unscorable", "note": why})
                continue
            if len(errors) < 2 or any(e is None or e <= 0 for e in errors):
                out.append({**row, "score": "not caught", "note": "its order cannot be formed", "E": errors})
                continue
            q = log_slope(rungs, errors)
            lo, hi = p + P3_WINDOW[0], p + P3_WINDOW[1]
            out.append({**row, "score": "caught" if lo <= q <= hi else "not caught", "q": q, "window": [lo, hi],
                        "E": errors, "rungs": rungs})
        return out

    def score_record_plant(self, plant) -> list[dict]:
        world = self.inputs.worlds[plant.world]
        family_id = plant.families[0]
        name = self.inputs.judged_run(family_id, world.rungs[0], 0)
        state = self.states.get(name)
        rows = []
        honest_results = {r.entry: r for r in self.run_results if r.run == name}
        entry = state.single() if state else None
        edit = edit_module.parse(plant.change)
        for cls, check in plant.must_fail:
            row = {"plant": plant.id, "family": family_id, "check": f"{cls} {check}", "run": name}
            honest = honest_results.get(f"{cls} {check}")
            if honest is None or honest.outcome != "pass" or entry is None:
                rows.append({**row, "score": "unscorable", "note": "its honest entry did not pass"})
                continue
            ref = self.ref_copy(world.name, 0)
            events = {"time_s": list(entry.times), "channel": list(entry.channels),
                      "counts_after": [list(c) for c in entry.counts], "first_index": entry.first_index}
            series, events, total = edit_module.apply(edit, entry.series, events, entry.events_total, ref.K,
                                                      t0_index=0)
            if check == "trace":
                trace = check_trace(world, events["time_s"], events["channel"],
                                    [tuple(c) for c in events["counts_after"]], events["first_index"], total, ref.K,
                                    ref.channels, ref.counts, world.initial_counts, True, True)
                rows.append({**row, "score": "caught" if not trace.passes else "not caught",
                             "note": "; ".join(trace.fails[:3])})
                continue
            if check.startswith("start "):
                readout = check[len("start "):]
                declared = self.inputs.start_value(world.name, readout)
                edited = start_at(series[readout][0], declared)
                distance = abs(Fraction(series[readout][0]) - Fraction(entry.series[readout][0]))
                caught = not edited.passes and not (edited.bound > distance)
                rows.append({**row, "score": "caught" if caught else "not caught",
                             "statistic": float(edited.distance), "tolerance": float(edited.bound),
                             "margin": ratio(distance, edited.bound)})
                continue
            if check.startswith("identity "):
                ident = check[len("identity "):]
                terms = world.identities[ident]
                at0_h = {n: v[0] for n, v in entry.series.items()}
                at0_e = {n: v[0] for n, v in series.items()}
                fails = 0
                best = (Fraction(0), Fraction(1))
                for i, t in enumerate(entry.t):
                    s_steps = steps(_registered_time(world, t), state.spec.step)
                    honest_v = identity_at(terms, {n: entry.series[n][i] for n, _, _ in terms}, at0_h, s_steps)
                    edited_v = identity_at(terms, {n: series[n][i] for n, _, _ in terms}, at0_e, s_steps)
                    if not edited_v.passes:
                        fails += 1
                    dist = abs(edited_v.residual - honest_v.residual)
                    if honest_v.bound > 0 and dist / honest_v.bound > best[0] / best[1]:
                        best = (dist, honest_v.bound)
                caught = fails > 0 and not (best[1] > best[0])
                rows.append({**row, "score": "caught" if caught else "not caught", "samples_over_bound": fails,
                             "margin": ratio(best[0], best[1])})
                continue
            rows.append({**row, "score": "unscorable", "note": "a check the judge cannot form"})
        return rows

    # ---- the whole pass ----

    def score(self) -> dict:
        self.read()
        inputs = self.inputs
        self.run_results: list[Result] = []
        # E, R, D of every judged run (and of the restarts, which are their uninterrupted runs')
        for state in self.states.values():
            spec = state.spec
            if spec.role == "judged":
                self.run_results.extend(self.judge_run(state, spec.family, "arm"))
            elif spec.role == "plant":
                self.run_results.extend(self.judge_run(state, None, "plant"))
        restart_results = []
        for unint, resumed in self.restart_pairs():
            family = unint.spec.family
            own = self.judge_run(resumed, family, "arm")
            for r in own:
                r.run = unint.spec.name
                r.entry = f"{r.entry} (restart)"
            # the support run's D counts against its own use only: its restart entry is unformed
            own = [r for r in own if not r.entry.startswith("D ")]
            restart_results.extend(own)
            info = self.restart_checks.get(resumed.spec.name, {})
            r_entry = resumed.single()
            if info.get("differences"):
                outcome = "fail"
            elif resumed.missing or refused_any(resumed, r_entry) or not info.get("formed", False) or (
                    unint.single() is None or refused_any(unint, unint.single())):
                outcome = "unformed"
            else:
                outcome = "pass"
            restart_results.append(Result(family, unint.spec.name, "E restart", "E", outcome,
                                          statistic=len(info.get("differences", [])), tolerance=0,
                                          note="; ".join((info.get("refusals", []) + info.get("differences", []))[:4]),
                                          extra={"scored_for": "arm", "resumed_run": resumed.spec.name}))
        self.run_results.extend(restart_results)
        # S, the pair and W5-exact's two rungs
        self.s_results: list[Result] = []
        owed = []
        for fam_id, fam in inputs.families.items():
            world = inputs.worlds[fam.world]
            for readout, p in world.s_readouts():
                first = self.s_entry(fam_id, readout, p, retried=False)
                first.extra["pass"] = "first"
                if first.extra.get("owes_retry"):
                    owed.append(fam_id)
                    if fam_id in self.owed_families:
                        second = self.s_entry(fam_id, readout, p, retried=True)
                        second.extra["pass"] = "retry"
                        second.extra["first_pass"] = first.as_dict()
                        self.s_results.append(second)
                        continue
                    if self.retry_owed is not None:
                        first.note += "; owed a retry that was not owed by the first pass's file"
                self.s_results.append(first)
        pair_results = []
        for world in inputs.worlds.values():
            fams = world.families
            if len(fams) != 2:
                continue
            for readout in world.judged.get("orders_differ", []):
                runs_a = [self.run_at(fams[0], world.rungs[0], c, False) for c in range(world.copies)]
                runs_b = [self.run_at(fams[1], world.rungs[0], c, False) for c in range(world.copies)]
                res = self.differ_entry(world, readout, runs_a, runs_b, f"pair {readout}", None)
                res.extra["families"] = list(fams)
                res.extra["world"] = world.name
                pair_results.append(res)
            for readout in world.judged.get("rungs_differ", []):
                for fam_id in fams:
                    fam = inputs.families[fam_id]
                    runs_a = [self.run_at(fam_id, fam.rungs[0], c, False) for c in range(world.copies)]
                    runs_b = [self.run_at(fam_id, fam.rungs[1], c, False) for c in range(world.copies)]
                    res = self.differ_entry(world, readout, runs_a, runs_b, f"rungs {readout}", fam_id)
                    res.extra["families"] = [fam_id]
                    res.extra["world"] = world.name
                    pair_results.append(res)
        # plants
        plant_rows: dict[str, list[dict]] = {}
        for plant in inputs.plants:
            rows: list[dict] = []
            if inputs.worlds[plant.world] is None or self.references.get(plant.world) is None:
                rows.append({"plant": plant.id, "score": "unscorable", "note": "the world's reference is refused"})
            elif plant.kind == "engine":
                rows = self.score_p3(plant)
            elif plant.kind == "record":
                rows = self.score_record_plant(plant)
            else:
                for family_id in plant.families:
                    for cls, check in plant.must_fail:
                        if cls == "S":
                            rows.append(self.score_reference_plant_s(plant, family_id, check))
                        elif cls == "R" and check == "t_events":
                            rows.append(self.score_p5(plant, family_id))
                        else:
                            rows.append({"plant": plant.id, "family": family_id, "check": f"{cls} {check}",
                                         "score": "unscorable", "note": "a check the judge cannot form"})
            plant_rows[plant.id] = rows
        plant_scores = {pid: _plant_score(rows) for pid, rows in plant_rows.items()}
        return self._verdicts(owed, pair_results, plant_rows, plant_scores)

    def _verdicts(self, owed: list[str], pair_results: list[Result], plant_rows: dict, plant_scores: dict) -> dict:
        inputs = self.inputs
        families: dict[str, dict] = {}
        for fam_id, fam in inputs.families.items():
            world = inputs.worlds[fam.world]
            runs = [s for s in self.states.values() if s.spec.role == "judged" and s.spec.family == fam_id]
            run_entries = [r for r in self.run_results if r.family == fam_id and r.extra.get("scored_for") == "arm"]
            s_entries = [r for r in self.s_results if r.family == fam_id]
            pairs = [r for r in pair_results if fam_id in r.extra.get("families", [])]
            run_fail = [r for r in run_entries if r.outcome == "fail"]
            s_fail = [r for r in s_entries if r.outcome == "fail"]
            reasons = []
            if run_fail or s_fail:
                verdict = "fail"
                reasons = [f"{r.run or ''} {r.entry}".strip() for r in (run_fail + s_fail)][:8]
            else:
                inconclusive = [r for r in run_entries + s_entries if r.outcome in ("unformed", "inconclusive")]
                bad_pairs = [r for r in pairs if r.outcome != "pass"]
                refused_runs = [s.spec.name for s in runs if any(refused_any(s, e) for e in (s.entries or [None]))]
                if self.references.get(world.name) is None:
                    reasons.append("the world's reference is refused")
                reasons += [f"{r.run or ''} {r.entry}: {r.outcome}".strip() for r in inconclusive][:8]
                reasons += [f"{r.entry}: {r.outcome}" for r in bad_pairs]
                reasons += [f"{name}: refused" for name in refused_runs][:8]
                verdict = "inconclusive" if (inconclusive or bad_pairs or refused_runs or self.references.get(
                    world.name) is None) else "pass"
            if not s_entries and not run_entries:
                verdict = "inconclusive"
                reasons.append("no judged entry formed")
            families[fam_id] = {"verdict": verdict, "reasons": reasons}
        arms = {}
        for arm_id, world_name in inputs.arms.items():
            world = inputs.worlds[world_name]
            fam_verdicts = [families[f]["verdict"] for f in world.families]
            plants = {p.id: plant_scores[p.id] for p in inputs.plants_of(world_name)}
            if "fail" in fam_verdicts or "not caught" in plants.values():
                verdict = "fail"
            elif "inconclusive" in fam_verdicts or "unscorable" in plants.values():
                verdict = "inconclusive"
            else:
                verdict = "pass"
            arms[world_name] = {"verdict": verdict, "families": {f: families[f]["verdict"] for f in world.families},
                                "plants": plants}
        lines = [arms[w]["verdict"] for w in inputs.arms.values()]
        claim = "fail" if "fail" in lines else ("pass" if all(v == "pass" for v in lines) else "inconclusive")
        retry_families = sorted(set(owed))
        retry_runs = sorted(Inputs.retry_name(inputs.families[f], c) for f in retry_families
                            for c in range(inputs.worlds[inputs.families[f].world].copies))
        record = {
            "kind": RECORD_KIND,
            "pass": "retry" if self.retry_owed is not None else "first",
            "claim": claim,
            "lines": {
                "W5": "second order beside the reactions",
                "W5-exact": "exact times with constant rates",
                "W6": "second order beside the gene unit, with the gene unit's own material judged",
            },
            "arms": arms,
            "families": families,
            "entries": [r.as_dict() for r in self.run_results + self.s_results + pair_results],
            "plants": {pid: {"score": plant_scores[pid], "entries": rows} for pid, rows in plant_rows.items()},
            "refusals_and_flags": self.records + self._entry_issues(),
            "retry_owed": {"kind": RETRY_KIND, "families": retry_families, "runs": retry_runs},
        }
        return record

    def _entry_issues(self) -> list[dict]:
        out = []
        for state in self.states.values():
            for issue in state.issues:
                out.append({"run": state.spec.name, **issue.as_dict()})
            for entry in state.entries:
                for issue in entry.issues:
                    out.append({"run": state.spec.name, "table": entry.table, **issue.as_dict()})
        return out


def _plant_score(rows: list[dict]) -> str:
    """CRITERIA.md §6.3: caught when every entry is caught; not caught if a scored one is not; else unscorable."""
    scores = [r.get("score") for r in rows]
    if not scores:
        return "unscorable"
    if "not caught" in scores:
        return "not caught"
    if "unscorable" in scores:
        return "unscorable"
    return "caught"


def _cls(name: str) -> str:
    return name.split(" ")[0]


def _e_ref(ref: ReferenceWorld, readout: str, world: World) -> float:
    if readout == "t_events":
        values = [c.accuracy_s for c in ref.copies if c.K > 0]
    else:
        values = [c.accuracy[readout][i] for c in ref.copies for i, t in enumerate(world.samples) if t > 0]
    return max(values) if values else 0.0


def _samples_equal(t: list[float], samples: list[float]) -> bool:
    """A completed run's t is the registered samples_s: none missing, none extra, 1e-12 relative (0 exactly)."""
    return len(t) == len(samples) and all(relative_equal(a, b, REL_TIME) for a, b in zip(t, samples))


def _samples_equal_any(values: list, samples: list[float]) -> bool:
    try:
        return _samples_equal([float(v) for v in values], samples)
    except (TypeError, ValueError):
        return False


def _index_of(ts: list[float], t: float) -> int | None:
    for j, x in enumerate(ts):
        if relative_equal(x, t, REL_TIME):
            return j
    return None


def _sample_map(entry: Entry, world: World) -> dict[float, int]:
    """The entry's index of each registered sample it holds (1e-12 relative), formed once per entry."""
    cache = entry.__dict__.get("_sample_map")
    if cache is None:
        cache = {}
        for j, x in enumerate(entry.t or []):
            reg = _registered_time(world, x)
            cache.setdefault(reg, j)
        entry.__dict__["_sample_map"] = cache
    return cache


def _registered_times(entry: Entry, world: World) -> list[float]:
    cache = entry.__dict__.get("_registered_times")
    if cache is None:
        cache = [_registered_time(world, x) for x in (entry.t or [])]
        entry.__dict__["_registered_times"] = cache
    return cache


def _registered_time(world: World, t: float) -> float:
    """The registered sample a run's time stands for (1e-12 relative); the run's own where none matches."""
    for s in world.samples:
        if relative_equal(t, s, REL_TIME):
            return s
    return t


def _grid_steps(world: World, step: float) -> int | None:
    s = steps(world.end_s, step)
    return int(s) if s.denominator == 1 else None


def sj_int(value: Any) -> int | None:
    from .strictjson import is_integer
    return int(value) if is_integer(value) else None
