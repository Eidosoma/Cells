"""Declared global-event controls and source-order observations, never a solver.

The existing literal event laws remain the only numerical implementation.
Metadata configuration/order/store checks execute no pulse or transport law.
The observer reads already-executing source frames only after Root release.
"""

import ast
import copy
import hashlib
import json
import math
import os
import sys
from pathlib import Path

GLOBAL_ORDER = ("K_env", "Cl_env", "Na_env", "T_change", "gj_block", "NaKATP_block")
SALT_KEYS = GLOBAL_ORDER[:3]
STORES = ("T", "c_env_bound", "gj_block", "NaKATP_block")
CONFIGURATIONS = {
    "global_K_env": ("K_env",),
    "global_Cl_env": ("Cl_env",),
    "global_Na_env": ("Na_env",),
    "global_salts": SALT_KEYS,
    "global_salts_reversed_declaration": SALT_KEYS,
    "global_salts_signed_reversal": SALT_KEYS,
    "global_GJ_block": ("gj_block",),
    "global_NaK_block": ("NaKATP_block",),
    "global_combined": GLOBAL_ORDER,
    "global_boundaries": GLOBAL_ORDER,
}
SCENARIOS = tuple(CONFIGURATIONS)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def program(raw, scenario, labels):
    """Copy the existing combined declaration into an explicit global control.

    Non-global mechanisms are deliberately disabled in this NEW configuration;
    original fixture bytes, physical owners and persisted state are not changed.
    Signed reversal changes only the supplied salt amplitudes. A reversed
    declaration changes mapping insertion order, never source execution order.
    """
    require(scenario in SCENARIOS and len(labels) == 3, "Declared bounded global control required")
    from validation.betse.betse_normal_ecm_event_join_fixtures import finalize_fields

    value = copy.deepcopy(raw)
    owner = value["event_owner"]
    original = owner["global_options"]
    require(set(original) == set(GLOBAL_ORDER), "Complete existing global configuration required")
    selected = CONFIGURATIONS[scenario]
    configured = {
        key: copy.deepcopy(original[key]) if key in selected else 0 for key in GLOBAL_ORDER
    }
    for key in selected:
        row = configured[key]
        size = 3 if key == "NaKATP_block" else 4
        require(
            type(row) is list and len(row) == size and row[0] < row[1] and row[2] > 0,
            "Existing nondegenerate global event configuration required: " + key,
        )
        if scenario == "global_salts_signed_reversal":
            row[3] = -row[3]
        if scenario == "global_boundaries":
            row[:2] = [labels[1], labels[2]]
    if scenario == "global_salts_reversed_declaration":
        configured = dict(reversed(list(configured.items())))
    owner.update(
        global_options=configured,
        scheduled_options=dict.fromkeys(owner["scheduled_options"], 0),
        callbacks={},
        voltage=None,
    )
    owner["handler_fields"] = finalize_fields(
        configured, owner["scheduled_options"], owner, len(owner["owners"]["membrane_ids"])
    )
    value["case_id"] = scenario
    value["provenance"] += "; explicit deterministic global checkpoint configuration/control"
    return value


def affected_stores(options):
    fields = []
    for key in GLOBAL_ORDER:
        if options[key] != 0:
            field = "c_env_bound" if key in SALT_KEYS else "T" if key == "T_change" else key
            if field not in fields:
                fields.append(field)
    return fields


def check_stores(value, anchor):
    """Bind source and post-owner epochs without assuming they are identical."""
    options = anchor["global_options"]
    require(set(options) == set(GLOBAL_ORDER), "Global configuration ownership differs")
    require(value["global_options"] == options, "Changed global configuration after restore")
    require(
        set(value["post_owner_controls"]) == {"gj_block", "NaKATP_block"},
        "Post-owner control epoch missing; do not substitute post-global controls",
    )
    if options["NaKATP_block"] != 0:
        entry = anchor["entry_global"]["NaKATP_block"]
        require(
            entry["category"] == "array" and len(entry["shape"]) == 1,
            "Configured NaK entry must retain the complete source vector initialization",
        )
    for row in value["rows"]:
        for epoch in ("global_before", "global_after", "events_after"):
            require(set(row[epoch]) == set(STORES), "Missing complete global event store epoch")
            for stamp in row[epoch].values():
                require(
                    set(stamp) == {"fingerprint", "category", "shape", "dtype"}
                    and stamp["category"] in {"array", "numpy_scalar", "scalar"},
                    "Typed event store observation required",
                )
        if options["NaKATP_block"] != 0:
            stamp = row["global_after"]["NaKATP_block"]
            require(
                stamp["category"] != "array" and stamp["shape"] == [],
                "NaK source setter must retain its scalar branch after vector entry",
            )
        if options["gj_block"] != 0:
            stamp = row["global_after"]["gj_block"]
            require(
                stamp["category"] == "array"
                and stamp["shape"] == anchor["entry_global"]["gj_block"]["shape"],
                "GJ source setter changed its complete membrane axis",
            )
        if options["T_change"] == 0:
            require(
                row["global_before"]["T"] == row["global_after"]["T"],
                "Unconfigured temperature event changed its source store",
            )
    require(
        set(value["transport"])
        == {
            "material",
            "rate",
            "NaK_rate",
            "field",
            "runtime_binding",
            "runtime_definition",
            "owner_caches",
            "all_stores",
        },
        "Complete material/rate/field/runtime/owner transport observations required",
    )
    if value["cursor"] == 3:
        for field in affected_stores(options):
            require(
                len({row["global_after"][field]["fingerprint"] for row in value["rows"]}) > 1,
                "Configured global event has no reached source-store effect: " + field,
            )
    return value


def source_order(path):
    """Read literal global branch order; import/evaluate no source model."""
    path = Path(path)
    data = path.read_bytes()
    tree = ast.parse(data)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "TissueHandler")
    function = next(
        n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "_fire_events_global"
    )
    branches = []
    for node in function.body:
        if not isinstance(node, ast.If):
            continue
        keys = [
            n.slice.value
            for n in ast.walk(node.test)
            if isinstance(n, ast.Subscript)
            and ast.unparse(n.value) == "p.global_options"
            and isinstance(n.slice, ast.Constant)
        ]
        require(len(keys) == 1 and keys[0] in GLOBAL_ORDER, "Unrecognized global source branch")
        branches.append(dict(key=keys[0], line=node.lineno, end=node.end_lineno))
    require(
        tuple(row["key"] for row in branches) == GLOBAL_ORDER,
        "Literal global source ordering changed",
    )
    return dict(path=str(path), sha256=hashlib.sha256(data).hexdigest(), branches=branches)


def check_pulses(accounting, options, labels):
    """Use actual source returns; never force a sigmoid tail to zero at release."""
    groups = accounting["global_dispatches"]
    require(
        len(groups) == 6 and accounting["global_profile_complete"],
        "Incomplete global source observations",
    )
    active = [key for key in GLOBAL_ORDER if options[key] != 0]
    for index, group in enumerate(groups):
        require(
            group["label"] == labels[index % 3] and group["exited"],
            "Global source clock/return missing",
        )
        require(
            [row["key"] for row in group["pulses"]] == active,
            "Omitted/duplicate/reversed global source branch",
        )
        for row in group["pulses"]:
            require(
                row["parameters"] == [group["label"], *options[row["key"]][:3]],
                "Changed source onset/release/width/time",
            )
            require(
                row["returned"] and type(row["value"]) is float and math.isfinite(row["value"]),
                "Missing actual finite source pulse return",
            )
    return groups


def observer(base, stream, source_path, directory):
    """Extend the existing invocation observer without wrapping source methods."""
    binding = source_order(source_path)
    pulse_stream = (Path(directory) / "global-pulses.jsonl").open("x")

    class Observed(base):
        def __init__(self):
            super().__init__(stream)
            self.pulse_stream = pulse_stream
            self.groups = []
            self.global_frames = {}
            self.pulse_frames = {}

        def save_pulse(self, row):
            pulse_stream.write(json.dumps(row, allow_nan=False) + "\n")
            pulse_stream.flush()
            os.fsync(pulse_stream.fileno())

        def observe(self, frame, event, arg):
            super().observe(frame, event, arg)
            if (
                frame.f_globals.get("__name__")
                != "cells.processes.betse_normal_ecm_event_join_source"
            ):
                return
            name = frame.f_code.co_name
            if name == "_fire_events_global":
                if event == "call":
                    group = dict(label=float(frame.f_locals["t"]), pulses=[], exited=False)
                    self.groups.append(group)
                    self.global_frames[id(frame)] = group
                elif event == "return":
                    group = self.global_frames.pop(id(frame), None)
                    if group is not None:
                        group["exited"] = True
                return
            if name != "pulse":
                return
            if event == "call":
                caller = frame.f_back
                if caller is None or id(caller) not in self.global_frames:
                    return
                branch = next(
                    (
                        row
                        for row in binding["branches"]
                        if row["line"] <= caller.f_lineno <= row["end"]
                    ),
                    None,
                )
                require(branch is not None, "Actual pulse has no bound source branch")
                row = dict(
                    key=branch["key"],
                    parameters=[
                        float(frame.f_locals[k]) for k in ("t", "t_on", "t_off", "t_change")
                    ],
                    returned=False,
                    value=None,
                )
                self.global_frames[id(caller)]["pulses"].append(row)
                self.pulse_frames[id(frame)] = row
                self.save_pulse(dict(event="entry", **row))
            elif event == "return":
                row = self.pulse_frames.pop(id(frame), None)
                if row is not None:
                    if arg is not None:
                        row.update(returned=True, value=float(arg))
                    self.save_pulse(dict(event="return_or_unwind", **row))

        def stop(self):
            try:
                result = super().stop()
                result.update(
                    global_dispatches=self.groups,
                    global_source_binding=binding,
                    global_profile_complete=not self.global_frames and not self.pulse_frames,
                )
                return result
            finally:
                primary = sys.exception()
                try:
                    pulse_stream.close()
                except BaseException as secondary:
                    if primary is None:
                        raise
                    primary.add_note("Global pulse journal close also failed: " + repr(secondary))

    return Observed()
