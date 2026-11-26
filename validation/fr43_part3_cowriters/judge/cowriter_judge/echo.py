"""The echo (CRITERIA.md §4.1): the run's `inputs`, its own keys and `operators` against the registered ones.

- Numbers to 1e-12 relative; a declared zero exactly zero; a registered JSON integer exactly (as a real: 4 and 4.0
  are equal); strings and booleans exactly.
- null and an absent key are equal where the registered value is null (`read`, and every optional key), and an
  extra key whose value is null is read as absent.
- A collection keyed by id (the reactions) is compared by id in any order; a declared order (`channels`,
  `unit_states`, `operators`) is compared as a list.
- The echoed keys are exactly `inputs.json`'s `echo`: the world's keys of its kind and the run's keys. A missing one
  departs, and so does an extra one with a value (the judge's reading of "exactly the keys").
"""

from __future__ import annotations

import copy
from fractions import Fraction
from typing import Any

from .registry import REL_TIME, Inputs, RunSpec

DECLARED_ORDER = {"channels", "unit_states", "operators", "samples_s"}


def _is_num(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def compare(registered: Any, run: Any, path: str, key: str = "") -> list[str]:
    """Every departure of `run` from `registered`, as text."""
    if registered is None:
        return [] if run is None else [f"{path}: {run!r} where null is registered"]
    if isinstance(registered, bool):
        return [] if (isinstance(run, bool) and run == registered) else [f"{path}: {run!r} against {registered!r}"]
    if _is_num(registered):
        if not _is_num(run) or isinstance(run, float) and run != run:
            return [f"{path}: {run!r} is not a number ({registered!r} registered)"]
        if isinstance(registered, int) or registered == 0:
            return [] if Fraction(run) == Fraction(registered) else [f"{path}: {run!r} against {registered!r}"]
        if abs(Fraction(run) - Fraction(registered)) <= Fraction(REL_TIME) * abs(Fraction(registered)):
            return []
        return [f"{path}: {run!r} against {registered!r} (1e-12 relative)"]
    if isinstance(registered, str):
        return [] if run == registered else [f"{path}: {run!r} against {registered!r}"]
    if isinstance(registered, dict):
        if not isinstance(run, dict):
            return [f"{path}: not an object"]
        out: list[str] = []
        for k, v in registered.items():
            if k not in run:
                if v is not None:
                    out.append(f"{path}/{k}: missing")
                continue
            out.extend(compare(v, run[k], f"{path}/{k}", k))
        for k, v in run.items():
            if k not in registered and v is not None:
                out.append(f"{path}/{k}: a key that is not registered")
        return out
    if isinstance(registered, list):
        if not isinstance(run, list):
            return [f"{path}: not a list"]
        keyed = (key not in DECLARED_ORDER and registered and all(isinstance(e, dict) and "id" in e
                                                                    for e in registered))
        if keyed:
            if not all(isinstance(e, dict) and "id" in e for e in run):
                return [f"{path}: a member without an id"]
            reg_ids = [e["id"] for e in registered]
            run_ids = [e["id"] for e in run]
            if len(set(run_ids)) != len(run_ids):
                return [f"{path}: an id given twice"]
            if set(reg_ids) != set(run_ids):
                return [f"{path}: ids {sorted(map(str, run_ids))} against {sorted(map(str, reg_ids))}"]
            by_id = {e["id"]: e for e in run}
            out = []
            for e in registered:
                out.extend(compare(e, by_id[e["id"]], f"{path}/{e['id']}"))
            return out
        if len(run) != len(registered):
            return [f"{path}: {len(run)} members against {len(registered)}"]
        out = []
        for i, (a, b) in enumerate(zip(registered, run)):
            out.extend(compare(a, b, f"{path}/{i}", key))
        return out
    return [f"{path}: an unreadable registered value"]


def registered_echo(inputs: Inputs, spec: RunSpec) -> dict:
    """The registered `inputs` of a run: the world's keys of its kind, plus seed, step_s, first and copy."""
    world = inputs.worlds[spec.world]
    keys = inputs.echo["world_keys"][world.kind]
    block = {k: world.block[k] for k in keys if k in world.block}
    for k in keys:
        if k not in world.block:
            block[k] = None
    block["seed"] = world.seeds[spec.copy]
    block["step_s"] = spec.raw["step_s"]
    block["first"] = spec.first
    block["copy"] = spec.copy
    change = spec.raw.get("change")
    if isinstance(change, dict):  # a run's own declared change (the invented set's refused and stopped runs)
        block = copy.deepcopy(block)
        for dotted, value in change.items():
            parts = dotted.split(".")
            target = block
            for part in parts[:-1]:
                target = target[part]
            target[parts[-1]] = value
    return block


def echo_departures(inputs: Inputs, spec: RunSpec, entry: dict, operators: list[str] | None) -> list[str]:
    """CRITERIA.md §4.1. A planted (Lie) run and a resumed run carry their honest run's registered values apart
    from `variant`, which is their own; so each is compared with its own registered run's values."""
    out = []
    echoed = entry.get("inputs")
    if not isinstance(echoed, dict):
        out.append("inputs: no echo")
    else:
        expected = registered_echo(inputs, spec)
        allowed = set(inputs.echo["world_keys"][inputs.worlds[spec.world].kind]) | set(inputs.echo["run_keys"])
        for k, v in echoed.items():
            if k not in allowed and v is not None:
                out.append(f"inputs/{k}: not an echoed key")
        for k in allowed:
            if k not in echoed:
                if expected.get(k) is not None:
                    out.append(f"inputs/{k}: missing")
                continue
            out.extend(compare(expected.get(k), echoed[k], f"inputs/{k}", k))
    world = inputs.worlds[spec.world]
    own = {"world": spec.world, "first": spec.first, "copy": spec.copy, "step_s": spec.raw["step_s"],
           "seed": world.seeds[spec.copy], "variant": spec.variant}
    for k, v in own.items():
        if k not in entry:
            out.append(f"{k}: missing")
            continue
        out.extend(compare(v, entry[k], k, k))
    if operators is None:
        out.append("operators: no registered list to compare with")
    else:
        out.extend(compare(list(operators), entry.get("operators"), "operators", "operators"))
    return out
