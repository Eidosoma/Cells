"""Held source-finalized f_sweep controls; never invoke a law during metadata.

Source setup must observe the real factory. Restart keeps its closed receipt,
not its Python callable: execution recreates a qualified sweep with retained
coefficients, and every recreation/validation replay remains counted work.
"""

import ast
import copy
import json
import math
import os
import sys
from pathlib import Path
from types import CodeType, FunctionType

from validation.betse import betse_normal_ecm_molecule_global_event_checkpoint as global_events
from validation.betse import betse_normal_ecm_molecule_membrane_event_checkpoint as membrane

ROUTE = "finalized_sweep"
CONDITIONS = tuple("sweep_" + key for key in membrane.MEMBRANE_KEYS) + (
    "sweep_combined",
    "sweep_mixed_constant",
)
CONTROLS = ("sweep_duplicate_targets", "sweep_boundaries")
SCENARIOS = CONDITIONS + CONTROLS
require = global_events.require


def configure_sim(raw, scenario):
    """Declare a sweep before actual finalization; no closure/receipt is supplied."""
    require(scenario in SCENARIOS, "Explicit bounded sweep scenario required")
    base = "membrane_" + scenario.removeprefix("sweep_")
    if scenario == "sweep_mixed_constant":
        base = "membrane_combined"
    result = membrane.configure_sim(raw, base)
    setup = result["sim_phase"]["setup"]
    for key, row in setup["scheduled_options"].items():
        if row != 0 and (scenario != "sweep_mixed_constant" or key == "Na_mem"):
            row[5] = "f_sweep"
    require(
        "frequency_sweep" in result["source_setup"],
        "Missing real source frequency-sweep configuration; no defaults",
    )
    result["provenance"] += "; separately declared native f_sweep configuration: " + scenario
    return result


def prepare_sim(directory, init_binding, init_parent, attempts, *, scenario, event_owner_inputs):
    from cells.processes import betse_normal_ecm_molecule_event_owner as bridge
    from cells.processes import betse_normal_ecm_molecule_sweep_authority as authority
    from validation.betse import betse_normal_ecm_molecule_checkpoint as preparation

    require(scenario in SCENARIOS, "Unknown explicit sweep route")
    directory = Path(directory)
    directory.mkdir(exist_ok=False)
    take = preparation._retainer(directory, attempts)

    def checked():
        actual = init_binding.composition
        value = bridge.check_inputs(event_owner_inputs, expected_INIT=actual.identity)
        authority.require(
            value.source_geometry_binding_identity
            == actual.material_binding.geometry_binding.identity,
            "Foreign supplied sweep geometry authority",
        )
        return value

    supplied = take("typed-event-owner-inputs", checked, supplied=event_owner_inputs)
    complete = take(
        "actual-complete-INIT",
        lambda: preparation.run.complete_INIT(init_binding, init_parent),
        init_binding=init_binding,
        init_parent=init_parent,
    )
    original = take(
        "original-SIM-fixture",
        lambda: preparation.fixtures.sim_inputs("zero_INIT_calls", complete.complete_init),
        complete=complete,
    )
    raw = take(
        "declared-sweep-SIM-configuration",
        lambda: configure_sim(original, scenario),
        original=original,
    )
    component = take(
        "SIM-component-binding",
        lambda: preparation.leaf.bind(raw, event_owner_inputs=supplied),
        raw=raw,
    )
    declared = take(
        "SIM-run-inputs", lambda: preparation.fixtures.declaration("zero_INIT_calls", component)
    )
    return take(
        "actual-INIT-to-SIM",
        lambda: preparation.run.transition(
            init_binding,
            init_parent,
            component,
            declared,
            provenance="Actual observed source sweep finalization; no synthetic callback admission",
        ),
        component=component,
        declared=declared,
        init_parent=init_parent,
    )


def declaration(binding, entry, scenario):
    from cells.processes import betse_normal_ecm_molecule_event_owner as bridge
    from cells.processes import betse_normal_ecm_molecule_events as events
    from cells.processes import betse_normal_ecm_molecule_sweep_authority as authority

    require(scenario in SCENARIOS, "Explicit finalized sweep route required")
    published = bridge.resolve(binding, entry)
    owner = events.ions.data(published.owner)
    require(
        owner["voltage"] is None
        and owner["event_cut"] is None
        and owner["scheduled_options"]["pressure"] == 0
        and owner["scheduled_options"]["ecmJ"] == 0
        and all(row == 0 for row in owner["global_options"].values()),
        "Sweep route retains its closed membrane-only configuration",
    )
    authority.validate(binding, owner, published, published.event_finalized)
    return dict(
        kind=events.INPUT_KIND,
        case_id=scenario,
        provenance="Actual retained SIM source f_sweep factory/closure authority; publication "
        + published.identity,
        source_binding_identity=binding.identity,
        source_entry_identity=entry.identity,
        scope=copy.deepcopy(events.SCOPE),
        event_owner=owner,
    )


def source_authority(binding):
    fields = binding.base.setup_receipt["event_finalization"]["source_fields"]
    require("sweep_callback_authority" in fields, "Missing actual observed sweep factory receipt")
    return {
        name: fields[name]
        for name in ("constant_callback_authority", "sweep_callback_authority")
        if name in fields
    }


def source_order(path):
    value = membrane.source_order(path)
    tree = ast.parse(Path(path).read_bytes())
    function = next(
        n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "prepared_callback"
    )
    branch = next(
        n
        for n in function.body
        if isinstance(n, ast.If) and ast.unparse(n.test) == "kind == 'sweep'"
    )
    callbacks = [n for n in ast.walk(branch) if isinstance(n, ast.Lambda)]
    require(
        len(callbacks) == 1
        and ast.unparse(callbacks[0]) == "lambda t: time_laws.evaluate(program, t, xp=np).factor",
        "Changed qualified sweep recreation source",
    )
    return dict(value, sweep_callback_line=callbacks[0].lineno)


def observer(base, stream, source_path, directory):
    """Read already-executing source frames; never call a factory/callback/law."""
    from cells.processes import betse_normal_ecm_event_join_source as literal
    from cells.processes import betse_time_modulation as time_laws

    binding = source_order(source_path)
    codes = {
        kind: next(
            c
            for c in literal.prepared_callback.__code__.co_consts
            if type(c) is CodeType and c.co_firstlineno == binding[kind + "_callback_line"]
        )
        for kind in ("constant", "sweep")
    }
    journal = (Path(directory) / "sweep-callbacks.jsonl").open("x")

    class Observed(base):
        def __init__(self, output):
            super().__init__(output)
            self.sweep_stream = journal
            self.sweep_groups, self.tissue, self.active_callbacks = [], {}, {}

        def emit_sweep(self, value):
            journal.write(json.dumps(value, allow_nan=False) + "\n")
            journal.flush()
            os.fsync(journal.fileno())

        def observe(self, frame, event, arg):
            super().observe(frame, event, arg)
            if frame.f_globals is not vars(literal):
                return
            name = frame.f_code.co_name
            if name == "_fire_events_tissue":
                if event == "call":
                    group = dict(label=float(frame.f_locals["t"]), events=[], exited=False)
                    self.sweep_groups.append(group)
                    self.tissue[id(frame)] = group
                elif event == "return":
                    group = self.tissue.pop(id(frame), None)
                    if group is not None:
                        group["exited"] = True
                return
            if name not in ("pulse", "<lambda>"):
                return
            if event == "call":
                caller = frame.f_back
                if caller is None or id(caller) not in self.tissue:
                    return
                branch = next(
                    (
                        row
                        for row in binding["branches"]
                        if row["line"] <= caller.f_lineno <= row["end"]
                    ),
                    None,
                )
                require(branch is not None, "Unowned sweep callback/pulse branch")
                row = dict(
                    key=branch["key"],
                    operation="pulse" if name == "pulse" else "callback",
                    returned=False,
                )
                if name == "pulse":
                    row["parameters"] = [
                        float(frame.f_locals[k]) for k in ("t", "t_on", "t_off", "t_change")
                    ]
                else:
                    kind = next((k for k, code in codes.items() if frame.f_code is code), None)
                    handler, suffix = caller.f_locals["self"], membrane.MEMBRANE_KEYS[branch["key"]]
                    callback = getattr(handler, "dyna_" + suffix)
                    scalar = getattr(handler, "scalar_" + suffix)
                    require(
                        kind is not None
                        and type(callback) is FunctionType
                        and callback.__code__ is frame.f_code
                        and callback.__globals__ is frame.f_globals
                        and type(scalar) is int
                        and scalar == 1,
                        "Foreign qualified sweep/constant runtime callable",
                    )
                    row.update(
                        kind=kind,
                        parameters=[float(frame.f_locals["t"])],
                        scalar=scalar,
                        targets=list(getattr(handler, "targets_" + suffix)),
                        source_sha256=binding["sha256"],
                        callback_line=frame.f_code.co_firstlineno,
                        runtime_code_matches=True,
                    )
                    if kind == "sweep":
                        program = frame.f_locals["program"]
                        require(
                            type(program) is time_laws.Program
                            and program.kind == "sweep"
                            and callback.__code__.co_freevars == ("program",)
                            and len(callback.__closure__) == 1
                            and callback.__closure__[0].cell_contents is program,
                            "Foreign recreated sweep program/closure owner",
                        )
                        require(
                            time_laws.record(program)["identity"] == program.identity,
                            "Changed actual recreated sweep program record",
                        )
                        row["program"] = dict(
                            identity=program.identity,
                            start=program.frequency_Hz,
                            slope=program.slope_Hz_s,
                            automatic_slope=program.automatic_slope,
                            provenance=program.provenance,
                        )
                self.tissue[id(caller)]["events"].append(row)
                self.active_callbacks[id(frame)] = row
                self.emit_sweep(dict(event="entry", **row))
            elif event == "return":
                row = self.active_callbacks.pop(id(frame), None)
                if row is not None:
                    if arg is not None:
                        category = (
                            "array"
                            if hasattr(arg, "shape")
                            and hasattr(arg, "ndim")
                            and type(arg).__name__ == "ndarray"
                            else "numpy_scalar"
                            if hasattr(arg, "dtype")
                            else "scalar"
                        )
                        row.update(
                            returned=True,
                            value=float(arg),
                            value_type=type(arg).__name__,
                            value_category=category,
                            value_shape=list(arg.shape) if hasattr(arg, "shape") else [],
                            value_dtype=arg.dtype.str if hasattr(arg, "dtype") else None,
                        )
                    self.emit_sweep(dict(event="return_or_unwind", **row))

        def stop(self):
            try:
                result = super().stop()
                result.update(
                    sweep_dispatches=self.sweep_groups,
                    sweep_source_binding=binding,
                    sweep_profile_complete=not self.tissue and not self.active_callbacks,
                )
                return result
            finally:
                primary = sys.exception()
                try:
                    journal.close()
                except BaseException as secondary:
                    if primary is None:
                        raise
                    primary.add_note("Sweep callback journal close also failed: " + repr(secondary))

    try:
        return global_events.observer(Observed, stream, source_path, directory)
    except BaseException:
        primary = sys.exception()
        try:
            journal.close()
        except BaseException as secondary:
            primary.add_note("Sweep callback journal close also failed: " + repr(secondary))
        raise


def check_calls(accounting, anchor):
    groups = accounting["sweep_dispatches"]
    require(
        len(groups) == 6 and accounting["sweep_profile_complete"],
        "Incomplete sweep continuation observations",
    )
    keys = membrane.active_keys(anchor["scheduled_options"], anchor["ion_ids"])
    for index, group in enumerate(groups):
        require(
            group["exited"]
            and group["label"] == anchor["labels"][index % 3]
            and [(r["key"], r["operation"]) for r in group["events"]]
            == [(k, op) for k in keys for op in ("callback", "pulse")],
            "Duplicate/omitted/reordered sweep callback/pulse",
        )
        for row in group["events"]:
            require(
                row["returned"] and math.isfinite(row["value"]),
                "Sweep callback/pulse failed or nonfinite",
            )
            configured = anchor["scheduled_options"][row["key"]]
            if row["operation"] == "pulse":
                require(
                    row["parameters"] == [group["label"], *configured[:3]],
                    "Changed sweep pulse parameters",
                )
                continue
            kind = "sweep" if configured[5] == "f_sweep" else "constant"
            require(
                row["kind"] == kind
                and row["parameters"] == [group["label"]]
                and type(row["scalar"]) is int
                and row["scalar"] == 1
                and row["targets"] == anchor["targets"][row["key"]]
                and row["source_sha256"] == accounting["sweep_source_binding"]["sha256"]
                and row["callback_line"]
                == accounting["sweep_source_binding"][kind + "_callback_line"]
                and row["runtime_code_matches"] is True,
                "Changed actual sweep callback/target/code authority",
            )
            if kind == "constant":
                require(
                    row["value_type"] == "int" and row["value"] == 1,
                    "Changed constant callback in mixed sweep",
                )
            else:
                dynamic = anchor["callbacks"][membrane.MEMBRANE_KEYS[row["key"]]]["dynamic"]
                require(
                    row["value_shape"] == []
                    and row["value_dtype"] == "<f8"
                    and row["program"]["start"] == dynamic["start"]
                    and row["program"]["slope"] == dynamic["slope"]
                    and row["program"]["provenance"] == dynamic["provenance"]
                    and row["program"]["automatic_slope"] is False,
                    "Sweep recreation lost actual factory-derived coefficients/shape",
                )
    counts = accounting["counts"]
    work = {
        name: count
        for name, count in counts.items()
        if name.endswith((".f_sweep", ".prepared_callback", ".sweep_program", ".evaluate"))
    }
    require(
        any(n.endswith(".f_sweep") and c > 0 for n, c in work.items())
        and any(n.endswith(".sweep_program") and c > 0 for n, c in work.items()),
        "Missing actual factory/recreation accounting",
    )
    return dict(dispatches=groups, factory_recreation_and_nested_work=work, independent_cases=0)
