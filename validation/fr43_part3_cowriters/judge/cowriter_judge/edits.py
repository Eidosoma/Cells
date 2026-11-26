"""The record plants' edits (CRITERIA.md §6.1, §6.3), read from each plant's registered `change` text.

A record plant edits a copy of one honest record (copy 0 of the family named, at the world's coarsest rung) and is
caught when every named check fails on the edited copy. The edited copy is the judge's own and is no run of any
table. Four forms of `change` are registered:

- "<book> x (1 + <f>)"                                : the book times (1 + f) at every sample
- "<names> at its|their t = 0 value(s) at every sample": each named row held at its t = 0 value
- "<names> at t = 0 each x <f>"                        : each named row's t = 0 value times f
- "event k = floor(K_c/2) of the record removed, ..."  : that event removed, the later renumbered, events_total - 1
A change of another form is refused (the judge cannot form that plant).
"""

from __future__ import annotations

import copy as copy_module
import re
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Edit:
    form: str  # "scale", "hold", "start", "remove_event"
    names: tuple[str, ...]
    factor: str | None = None  # the declared decimal text


def _names(text: str) -> tuple[str, ...]:
    text = re.sub(r"\(.*?\)", "", text).strip()
    parts = re.split(r",\s*|\s+and\s+", text)
    return tuple(p.strip() for p in parts if p.strip())


def parse(change: str) -> Edit:
    # A trailing gloss in words, "(a product not released)", is not part of the edit; "(1 + 1e-3)" is.
    text = re.sub(r"\s*\([A-Za-z][^)]*\)\s*$", "", change.strip())
    m = re.fullmatch(r"(\w+) x \(1 \+ ([0-9.eE+-]+)\)", text)
    if m:
        return Edit("scale", (m.group(1),), m.group(2))
    m = re.fullmatch(r"(.+?) at (?:its|their) t = 0 values? at every sample", text)
    if m:
        return Edit("hold", _names(m.group(1)))
    m = re.fullmatch(r"(.+?) at t = 0 each x ([0-9.eE+-]+)", text)
    if m:
        return Edit("start", _names(m.group(1)), m.group(2))
    if re.match(r"event k = floor\(K_c/2\) of the record removed", text):
        return Edit("remove_event", ())
    raise ValueError(f"a record plant's change of no registered form: {change!r}")


def factor_value(edit: Edit) -> float:
    """The edit's factor as a double: (1 + f) for 'scale', f for 'start' (each formed from the declared decimal)."""
    if edit.form == "scale":
        return float(Decimal(1) + Decimal(edit.factor))
    if edit.form == "start":
        return float(Decimal(edit.factor))
    raise ValueError(edit.form)


def apply(edit: Edit, series: dict[str, list[float]], events: dict, events_total: int | None, k_c: int,
          t0_index: int = 0) -> tuple[dict[str, list[float]], dict, int | None]:
    """Return an edited deep copy of (series, events, events_total). `events` holds time_s, channel, counts_after."""
    new_series = copy_module.deepcopy(series)
    new_events = copy_module.deepcopy(events)
    new_total = events_total
    if edit.form == "scale":
        f = factor_value(edit)
        for name in edit.names:
            new_series[name] = [v * f for v in new_series[name]]
    elif edit.form == "hold":
        for name in edit.names:
            value0 = new_series[name][t0_index]
            new_series[name] = [value0 for _ in new_series[name]]
    elif edit.form == "start":
        f = factor_value(edit)
        for name in edit.names:
            new_series[name][t0_index] = new_series[name][t0_index] * f
    elif edit.form == "remove_event":
        k = k_c // 2
        first = int(new_events.get("first_index", 0))
        i = k - first
        for key in ("time_s", "channel", "counts_after"):
            del new_events[key][i]
        if new_total is not None:
            new_total = new_total - 1
    else:
        raise ValueError(edit.form)
    return new_series, new_events, new_total
