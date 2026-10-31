"""Held constant membrane-event declarations and observations, never a solver.

Callbacks must come from the actual SIM finalizer. Neither fixture callbacks
nor missing owner fields are hydrated into runtime authority. Numerical event
laws, target assignments and checkpoint encoding remain in existing producers.
The checkpoint retains closed source/provenance records on typed setup owners.
Existing install_owner recreates declared constants through prepared_callback
during execution; this carries no native live-object persistence claim. Any
later setup, recreation or replay belongs in the actual work accounting.
"""

import ast
import copy
import hashlib
import json
import math
import os
import sys
from pathlib import Path
from types import CodeType, FunctionType

from validation.betse import betse_normal_ecm_molecule_global_event_checkpoint as global_events

MEMBRANE_KEYS = dict(Na_mem="Namem", K_mem="Kmem", Cl_mem="Clmem", Ca_mem="Camem")
MEMBRANE_ORDER = tuple(MEMBRANE_KEYS)
STORES = ("Dm_base", "Dm_scheduled", "Dm_cells")
CONDITIONS = tuple("membrane_" + key for key in MEMBRANE_KEYS) + (
    "membrane_combined",
    "membrane_mixed_global",
)
CONTROLS = (
    "membrane_boundaries",
    "membrane_duplicate_targets",
    "membrane_profiles",
    "membrane_profiles_reversed",
    "membrane_empty_targets",
)
SCENARIOS = CONDITIONS + CONTROLS
OWNER_KEYS = {
    "kind",
    "provenance",
    "geometry_declaration_sha256",
    "owners",
    "handler_fields",
    "tissue_default",
    "tissue_target_inds",
    "cell_target_inds",
    "env_target_inds",
    "global_options",
    "scheduled_options",
    "configured_environment",
    "callbacks",
    "voltage",
    "event_cut",
}

require = global_events.require


def configure_sim(raw, scenario):
    """New declared setup controls using the existing membrane-four parameters.

    These options precede the real SIM finalizer. Original fixture inputs are
    untouched. No callback scalar, callable or finalization receipt is supplied
    by this declaration. Profile names and occurrence order are never repaired.
    """
    require(scenario in SCENARIOS, "Declared membrane condition/control required")
    result = copy.deepcopy(raw)
    phase = result["sim_phase"]
    setup = phase["setup"]
    dt = phase["time_profile"]["sim_dt_s"]
    require(type(dt) in (int, float) and dt > 0, "Original positive SIM dt required")
    require(
        set(setup["global_options"]) == set(global_events.GLOBAL_ORDER)
        and set(setup["scheduled_options"]) == set(MEMBRANE_KEYS) | {"pressure", "ecmJ"},
        "Complete original setup option guards required",
    )
    selected = (
        [scenario.removeprefix("membrane_")] if scenario in CONDITIONS[:4] else list(MEMBRANE_KEYS)
    )
    profiles = (
        ["region0", "region0", "all"]
        if scenario == "membrane_duplicate_targets"
        else ["region0", "all"]
        if scenario == "membrane_profiles"
        else ["all", "region0"]
        if scenario == "membrane_profiles_reversed"
        else []
        if scenario == "membrane_empty_targets"
        else ["all"]
    )
    require(
        all(name in setup["maps"]["tissue_target_inds"] for name in profiles),
        "Missing actual supplied profile; do not infer or pick one",
    )
    on, off, width = 0.5 * dt, 2.0 * dt, 0.7 * dt
    if scenario == "membrane_boundaries":
        # The original N3 source labels are linspace(0, total, floor(total/dt)).
        # Use the existing metadata calendar, never a replacement time grid.
        from cells.core.physiology_native_calendar import bind, window
        from cells.processes.betse_normal_ecm_run_lifecycle import profile

        calendar = bind(
            phase="SIM",
            provenance="Original bounded membrane control clock",
            **profile(phase["time_profile"])["sim"],
        )
        labels = window(calendar).event_label_s
        require(len(labels) == 3, "Original separate bounded SIM N3 calendar required")
        on, off = float(labels[1]), float(labels[2])
    setup["scheduled_options"] = {
        key: [on, off, width, 0.15, list(profiles), "None"] if key in selected else 0
        for key in setup["scheduled_options"]
    }
    setup["global_options"] = dict.fromkeys(setup["global_options"], 0)
    if scenario == "membrane_mixed_global":
        for key, amplitude in (
            ("K_env", 0.02),
            ("Cl_env", 0.015),
            ("Na_env", 0.01),
            ("T_change", 0.01),
            ("gj_block", 100),
        ):
            setup["global_options"][key] = [on, off, width, amplitude]
        setup["global_options"]["NaKATP_block"] = [on, off, width]
    result["provenance"] += (
        "; declared constant membrane event configuration before actual SIM finalization: "
        + scenario
    )
    return result


def prepare_sim(
    directory, init_binding, init_parent, attempts, *, scenario, event_owner_inputs=None
):
    """Existing complete-INIT/transition path with the new explicit declaration."""
    from cells.processes import betse_normal_ecm_molecule_event_owner as owner_bridge
    from cells.processes import betse_normal_ecm_molecule_run_lifecycle as run
    from validation.betse import betse_normal_ecm_molecule_checkpoint as preparation

    directory = Path(directory)
    directory.mkdir(exist_ok=False)
    take = preparation._retainer(directory, attempts)
    supplied = take(
        "typed-event-owner-inputs",
        lambda: owner_bridge.check_inputs(event_owner_inputs),
        supplied=event_owner_inputs,
    )
    complete = take(
        "actual-complete-INIT",
        lambda: run.complete_INIT(init_binding, init_parent),
        init_binding=init_binding,
        init_parent=init_parent,
    )
    original = take(
        "original-SIM-fixture",
        lambda: preparation.fixtures.sim_inputs("zero_INIT_calls", complete.complete_init),
        complete=complete,
    )
    raw = take(
        "declared-membrane-SIM-configuration",
        lambda: configure_sim(original, scenario),
        original=original,
    )
    component = take(
        "SIM-component-binding",
        lambda: run.composition.lifecycle.bind(raw, event_owner_inputs=supplied),
        raw=raw,
    )
    declared = take(
        "SIM-run-inputs", lambda: preparation.fixtures.declaration("zero_INIT_calls", component)
    )
    return take(
        "actual-INIT-to-SIM",
        lambda: run.transition(
            init_binding,
            init_parent,
            component,
            declared,
            provenance="Actual transition/finalized callbacks; no fixture as admission",
        ),
        component=component,
        declared=declared,
        init_parent=init_parent,
    )


def declaration(binding, entry, scenario):
    """Require the actual complete returned owner; no synthetic fallback."""
    from cells.processes import betse_normal_ecm_molecule_event_owner as owner_bridge
    from cells.processes import betse_normal_ecm_molecule_events as events

    require(scenario in SCENARIOS, "Unknown membrane condition/control")
    fields = entry.phase_binding.setup_receipt["event_finalization"]["source_fields"]
    published = owner_bridge.resolve(binding, entry)
    owner = events.ions.data(published.owner)
    require(
        set(owner) == OWNER_KEYS,
        "Actual SIM finalizer lacks complete event-owner authority; continuation remains refused",
    )
    require(
        fields["source_phase"] == "SIM"
        and fields["legacy_run_sim"] is True
        and fields["event_fire_calls"] == 0
        and fields.get("constant_callback_authority"),
        "Missing actual SIM constant callback authority; no hydration allowed",
    )
    return dict(
        kind=events.INPUT_KIND,
        case_id=scenario,
        provenance="Actual finalized constant membrane callbacks and retained SIM/profile owners",
        source_binding_identity=binding.identity,
        source_entry_identity=entry.identity,
        scope=copy.deepcopy(events.SCOPE),
        event_owner=owner,
    )


def active_keys(options, ion_ids):
    # Native Na/K branches have no presence guard. Do not normalize them away.
    return [
        key
        for key in MEMBRANE_KEYS
        if options[key] != 0
        and (key not in ("Cl_mem", "Ca_mem") or key.removesuffix("_mem") in ion_ids)
    ]


def source_order(path):
    path = Path(path)
    data = path.read_bytes()
    tree = ast.parse(data)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "TissueHandler")
    fn = next(
        n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "_fire_events_tissue"
    )
    branches = []
    for node in fn.body:
        if not isinstance(node, ast.If):
            continue
        keys = [
            n.slice.value
            for n in ast.walk(node.test)
            if isinstance(n, ast.Subscript)
            and ast.unparse(n.value) == "p.scheduled_options"
            and isinstance(n.slice, ast.Constant)
        ]
        if keys and keys[0] in MEMBRANE_KEYS:
            branches.append(dict(key=keys[0], line=node.lineno, end=node.end_lineno))
    require(
        tuple(row["key"] for row in branches) == MEMBRANE_ORDER,
        "Literal membrane source ordering changed",
    )
    constant = next(
        n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "prepared_callback"
    )
    constant_branch = next(
        n
        for n in constant.body
        if isinstance(n, ast.If) and ast.unparse(n.test) == "kind == 'constant'"
    )
    lambdas = [n for n in ast.walk(constant_branch) if isinstance(n, ast.Lambda)]
    require(
        len(lambdas) == 1 and ast.unparse(lambdas[0]) == "lambda t: 1",
        "Changed prepared constant callback source",
    )
    return dict(
        path=str(path),
        sha256=hashlib.sha256(data).hexdigest(),
        branches=branches,
        constant_callback_line=lambdas[0].lineno,
    )


def observer(base, stream, source_path, directory):
    """Read real callback/pulse frames; never wrap, call or replace a handler."""
    binding = source_order(source_path)
    journal = (Path(directory) / "membrane-callbacks.jsonl").open("x")

    class Observed(base):
        def __init__(self, output):
            super().__init__(output)
            self.membrane_stream = journal
            self.membrane_groups = []
            self.tissue_frames = {}
            self.membrane_frames = {}

        def emit_membrane(self, row):
            journal.write(json.dumps(row, allow_nan=False) + "\n")
            journal.flush()
            os.fsync(journal.fileno())

        def observe(self, frame, event, arg):
            super().observe(frame, event, arg)
            if (
                frame.f_globals.get("__name__")
                != "cells.processes.betse_normal_ecm_event_join_source"
            ):
                return
            name = frame.f_code.co_name
            if name == "_fire_events_tissue":
                if event == "call":
                    group = dict(label=float(frame.f_locals["t"]), events=[], exited=False)
                    self.membrane_groups.append(group)
                    self.tissue_frames[id(frame)] = group
                elif event == "return":
                    group = self.tissue_frames.pop(id(frame), None)
                    if group is not None:
                        group["exited"] = True
                return
            if name not in ("pulse", "<lambda>"):
                return
            if event == "call":
                caller = frame.f_back
                if caller is None or id(caller) not in self.tissue_frames:
                    return
                branch = next(
                    (
                        row
                        for row in binding["branches"]
                        if row["line"] <= caller.f_lineno <= row["end"]
                    ),
                    None,
                )
                require(branch is not None, "Actual callback/pulse has no bound membrane branch")
                row = dict(
                    key=branch["key"],
                    operation="pulse" if name == "pulse" else "callback",
                    returned=False,
                    value=None,
                )
                if name == "pulse":
                    row["parameters"] = [
                        float(frame.f_locals[k]) for k in ("t", "t_on", "t_off", "t_change")
                    ]
                else:
                    require(
                        frame.f_code.co_firstlineno == binding["constant_callback_line"],
                        "Foreign runtime constant callback code",
                    )
                    handler = caller.f_locals["self"]
                    suffix = MEMBRANE_KEYS[branch["key"]]
                    callback = getattr(handler, "dyna_" + suffix)
                    factory = frame.f_globals.get("prepared_callback")
                    expected = (
                        [
                            code
                            for code in factory.__code__.co_consts
                            if type(code) is CodeType
                            and code.co_firstlineno == binding["constant_callback_line"]
                        ]
                        if type(factory) is FunctionType
                        else []
                    )
                    require(
                        len(expected) == 1
                        and frame.f_code is expected[0]
                        and type(callback) is FunctionType
                        and callback.__code__ is frame.f_code
                        and callback.__globals__ is frame.f_globals,
                        "Foreign runtime constant callback identity",
                    )
                    scalar = getattr(handler, "scalar_" + suffix)
                    row.update(
                        parameters=[float(frame.f_locals["t"])],
                        targets=list(getattr(handler, "targets_" + suffix)),
                        scalar_type=type(scalar).__name__,
                        scalar=scalar,
                        callback_source_sha256=binding["sha256"],
                        callback_line=frame.f_code.co_firstlineno,
                        callback_runtime_code_matches=True,
                    )
                self.tissue_frames[id(caller)]["events"].append(row)
                self.membrane_frames[id(frame)] = row
                self.emit_membrane(dict(event="entry", **row))
            elif event == "return":
                row = self.membrane_frames.pop(id(frame), None)
                if row is not None:
                    if arg is not None:
                        row.update(
                            returned=True, value=float(arg) if row["operation"] == "pulse" else arg
                        )
                    self.emit_membrane(dict(event="return_or_unwind", **row))

        def stop(self):
            try:
                result = super().stop()
                result.update(
                    membrane_dispatches=self.membrane_groups,
                    membrane_source_binding=binding,
                    membrane_profile_complete=not self.tissue_frames and not self.membrane_frames,
                )
                return result
            finally:
                primary = sys.exception()
                try:
                    journal.close()
                except BaseException as secondary:
                    if primary is None:
                        raise
                    primary.add_note(
                        "Membrane callback journal close also failed: " + repr(secondary)
                    )

    try:
        return global_events.observer(Observed, stream, source_path, directory)
    except BaseException:
        primary = sys.exception()
        try:
            journal.close()
        except BaseException as secondary:
            primary.add_note("Membrane callback journal close also failed: " + repr(secondary))
        raise


def check_calls(accounting, anchor):
    groups = accounting["membrane_dispatches"]
    require(
        len(groups) == 6 and accounting["membrane_profile_complete"],
        "Incomplete membrane source observations",
    )
    keys = active_keys(anchor["scheduled_options"], anchor["ion_ids"])
    for index, group in enumerate(groups):
        require(
            group["exited"] and group["label"] == anchor["labels"][index % 3],
            "Membrane source clock/return missing",
        )
        require(
            [(row["key"], row["operation"]) for row in group["events"]]
            == [(key, operation) for key in keys for operation in ("callback", "pulse")],
            "Omitted/duplicate/reordered membrane callback/pulse",
        )
        for row in group["events"]:
            require(row["returned"], "Membrane source callback/pulse did not return")
            if row["operation"] == "callback":
                require(
                    row["parameters"] == [group["label"]]
                    and type(row["value"]) is int
                    and row["value"] == 1
                    and row["scalar_type"] == "int"
                    and type(row["scalar"]) is int
                    and row["scalar"] == 1
                    and row["targets"] == anchor["targets"][row["key"]]
                    and row["callback_source_sha256"]
                    == accounting["membrane_source_binding"]["sha256"]
                    and row["callback_line"]
                    == accounting["membrane_source_binding"]["constant_callback_line"]
                    and row["callback_runtime_code_matches"] is True,
                    "Changed actual constant callback/ordered duplicate target authority",
                )
            else:
                require(
                    row["parameters"]
                    == [group["label"], *anchor["scheduled_options"][row["key"]][:3]]
                    and type(row["value"]) is float
                    and math.isfinite(row["value"]),
                    "Changed membrane pulse parameters or missing actual return",
                )
    return groups


def observe_row(trace, anchor, stamp, fingerprint):
    """Compare actual arrays only; do not evaluate a pulse/permeability law."""
    from numpy import array_equal

    epochs = {
        "before": trace["before"],
        "global": trace["stages"][0]["state"],
        "tissue": trace["stages"][1]["state"],
        "combined": trace["after"],
    }
    before, after = epochs["before"], epochs["tissue"]
    keys = active_keys(anchor["scheduled_options"], anchor["ion_ids"])
    untouched = {}
    for index, ion in enumerate(anchor["ion_ids"]):
        key = ion + "_mem"
        targets = anchor["targets"][key] if key in keys else []
        complement = [j for j in range(anchor["membrane_count"]) if j not in targets]
        untouched[ion] = dict(
            before=fingerprint(before["Dm_scheduled"][index, complement]),
            after=fingerprint(after["Dm_scheduled"][index, complement]),
        )
    return dict(
        epochs={name: {key: stamp(value[key]) for key in STORES} for name, value in epochs.items()},
        untouched=untouched,
        scheduled_rows={
            ion: stamp(after["Dm_scheduled"][i]) for i, ion in enumerate(anchor["ion_ids"])
        },
        source_sum_consistent=bool(
            array_equal(
                epochs["combined"]["Dm_cells"],
                epochs["combined"]["Dm_base"] + epochs["combined"]["Dm_scheduled"],
            )
        ),
    )


def check_stores(value, anchor):
    for name in ("scheduled_options", "callback_identity", "callback_authority"):
        require(
            value[name] == anchor[name],
            "Changed actual membrane callback/config ownership: " + name,
        )
    require(set(value["post_owner_membrane"]) == set(STORES), "Missing post-owner membrane epoch")
    shape = [len(anchor["ion_ids"]), anchor["membrane_count"]]
    for name, stamp in value["post_owner_membrane"].items():
        require(
            stamp["category"] == "array"
            and stamp["shape"] == shape
            and stamp["dtype"] == anchor["entry_membrane"][name]["dtype"],
            "Changed post-owner permeability axes or dtype",
        )
    keys = active_keys(anchor["scheduled_options"], anchor["ion_ids"])
    for row in value["rows"]:
        observed = row["membrane"]
        require(
            set(observed["epochs"]) == {"before", "global", "tissue", "combined"},
            "Missing membrane store epoch",
        )
        for epoch in observed["epochs"].values():
            require(set(epoch) == set(STORES), "Missing complete permeability stores")
            for name, stamp in epoch.items():
                require(
                    stamp["category"] == "array"
                    and stamp["shape"] == shape
                    and stamp["dtype"] == anchor["entry_membrane"][name]["dtype"],
                    "Changed permeability ion/membrane axes or dtype",
                )
        epochs = observed["epochs"]
        require(
            epochs["global"] == epochs["before"], "Global event changed a membrane source store"
        )
        require(
            epochs["tissue"]["Dm_base"] == epochs["before"]["Dm_base"]
            and epochs["combined"]["Dm_base"] == epochs["before"]["Dm_base"]
            and epochs["combined"]["Dm_scheduled"] == epochs["tissue"]["Dm_scheduled"]
            and observed["source_sum_consistent"] is True,
            "Base/scheduled/source-combination permeability epoch changed",
        )
        require(
            set(observed["untouched"]) == set(anchor["ion_ids"])
            and set(observed["scheduled_rows"]) == set(anchor["ion_ids"]),
            "Missing complete ion store observations",
        )
        require(
            all(record["before"] == record["after"] for record in observed["untouched"].values()),
            "Unselected ion/membrane occurrence changed",
        )
    if value["cursor"] == 3:
        for key in keys:
            if anchor["targets"][key]:
                ion = key.removesuffix("_mem")
                require(
                    len(
                        {
                            row["membrane"]["scheduled_rows"][ion]["fingerprint"]
                            for row in value["rows"]
                        }
                    )
                    > 1,
                    "Configured membrane event has no reached source-store effect: " + key,
                )
    return value
