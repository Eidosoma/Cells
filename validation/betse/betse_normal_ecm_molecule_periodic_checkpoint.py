"""Held source-finalized periodic controls; never invoke a law during metadata.

Source setup must observe the real factory. Restart keeps its closed receipt,
not its Python callable: execution recreates a qualified periodic with retained
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

ROUTE = "finalized_periodic"
CONDITIONS = tuple("periodic_" + key for key in membrane.MEMBRANE_KEYS) + (
    "periodic_combined",
    "periodic_mixed_constant",
)
CONTROLS = ("periodic_duplicate_targets", "periodic_boundaries")
SCENARIOS = CONDITIONS + CONTROLS
require = global_events.require


def configure_sim(raw, scenario, *, periodic_properties):
    """Declare a periodic before actual finalization; no closure/receipt is supplied."""
    require(scenario in SCENARIOS, "Explicit bounded periodic scenario required")
    from cells.processes import betse_normal_ecm_molecule_periodic_authority as authority

    configured = authority.properties(periodic_properties)
    base = "membrane_" + scenario.removeprefix("periodic_")
    if scenario == "periodic_mixed_constant":
        base = "membrane_combined"
    result = membrane.configure_sim(raw, base)
    setup = result["sim_phase"]["setup"]
    for key, row in setup["scheduled_options"].items():
        if row != 0 and (scenario != "periodic_mixed_constant" or key == "Na_mem"):
            row[5] = "periodic"
    cfg = result["source_setup"]
    if "periodic_properties" in cfg:
        require(
            authority.same(cfg["periodic_properties"], configured),
            "Foreign existing periodic configuration",
        )
    cfg["periodic_properties"] = configured
    cfg["periodic_event_configuration"] = copy.deepcopy(setup)
    cfg["periodic_preparation_route"] = ROUTE
    result["sim_phase"] = copy.deepcopy(raw["sim_phase"])
    authority.configuration(result)
    cfg["provenance"] += (
        "; explicit supplied periodic properties, conditional; "
        "native parser derivation unestablished"
    )
    result["provenance"] += "; separately declared native periodic configuration: " + scenario
    return result


def prepare_sim(
    directory,
    init_binding,
    init_parent,
    attempts,
    *,
    scenario,
    event_owner_inputs,
    periodic_properties,
):
    from cells.processes import betse_normal_ecm_molecule_event_owner as bridge
    from cells.processes import betse_normal_ecm_molecule_periodic_authority as authority
    from validation.betse import betse_normal_ecm_molecule_checkpoint as preparation

    require(scenario in SCENARIOS, "Unknown explicit periodic route")
    directory = Path(directory)
    directory.mkdir(exist_ok=False)
    take = preparation._retainer(directory, attempts)

    def checked():
        actual = init_binding.composition
        value = bridge.check_inputs(event_owner_inputs, expected_INIT=actual.identity)
        authority.require(
            value.source_geometry_binding_identity
            == actual.material_binding.geometry_binding.identity,
            "Foreign supplied periodic geometry authority",
        )
        return value

    supplied = take("typed-event-owner-inputs", checked, supplied=event_owner_inputs)
    configured = take(
        "required-periodic-configuration",
        lambda: authority.properties(periodic_properties),
        supplied=periodic_properties,
    )
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
        "declared-periodic-SIM-configuration",
        lambda: configure_sim(original, scenario, periodic_properties=configured),
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
            provenance=(
                "Actual observed source periodic finalization; no synthetic callback admission"
            ),
        ),
        component=component,
        declared=declared,
        init_parent=init_parent,
    )


def declaration(binding, entry, scenario):
    from cells.processes import betse_normal_ecm_molecule_event_owner as bridge
    from cells.processes import betse_normal_ecm_molecule_events as events
    from cells.processes import betse_normal_ecm_molecule_periodic_authority as authority

    require(scenario in SCENARIOS, "Explicit finalized periodic route required")
    published = bridge.resolve(binding, entry)
    owner = events.ions.data(published.owner)
    require(
        owner["voltage"] is None
        and owner["event_cut"] is None
        and owner["scheduled_options"]["pressure"] == 0
        and owner["scheduled_options"]["ecmJ"] == 0
        and all(row == 0 for row in owner["global_options"].values()),
        "Periodic route retains its closed membrane-only configuration",
    )
    authority.validate(binding, owner, published, published.event_finalized)
    return dict(
        kind=events.INPUT_KIND,
        case_id=scenario,
        provenance="Actual retained SIM source periodic factory/closure authority; publication "
        + published.identity,
        source_binding_identity=binding.identity,
        source_entry_identity=entry.identity,
        scope=copy.deepcopy(events.SCOPE),
        event_owner=owner,
    )


def source_authority(binding):
    fields = binding.base.setup_receipt["event_finalization"]["source_fields"]
    require(
        "periodic_callback_authority" in fields, "Missing actual observed periodic factory receipt"
    )
    return {
        name: fields[name]
        for name in ("constant_callback_authority", "periodic_callback_authority")
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
        if isinstance(n, ast.If) and ast.unparse(n.test) == "kind == 'periodic'"
    )
    callbacks = [n for n in ast.walk(branch) if isinstance(n, ast.Lambda)]
    require(
        len(callbacks) == 1
        and ast.unparse(callbacks[0]) == "lambda t: time_laws.evaluate(program, t, xp=np).value",
        "Changed qualified periodic recreation source",
    )
    return dict(value, periodic_callback_line=callbacks[0].lineno)


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
        for kind in ("constant", "periodic")
    }
    journal = (Path(directory) / "periodic-callbacks.jsonl").open("x")

    class Observed(base):
        def __init__(self, output):
            super().__init__(output)
            self.periodic_stream = journal
            self.periodic_groups, self.tissue, self.active_callbacks = [], {}, {}

        def emit_periodic(self, value):
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
                    self.periodic_groups.append(group)
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
                require(branch is not None, "Unowned periodic callback/pulse branch")
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
                        "Foreign qualified periodic/constant runtime callable",
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
                    if kind == "periodic":
                        program = frame.f_locals["program"]
                        require(
                            type(program) is time_laws.Program
                            and program.kind == "periodic"
                            and callback.__code__.co_freevars == ("program",)
                            and len(callback.__closure__) == 1
                            and callback.__closure__[0].cell_contents is program,
                            "Foreign recreated periodic program/closure owner",
                        )
                        require(
                            time_laws.record(program)["identity"] == program.identity,
                            "Changed actual recreated periodic program record",
                        )
                        row["program"] = dict(
                            identity=program.identity,
                            frequency=program.frequency_Hz,
                            phase=program.phase_rad,
                            provenance=program.provenance,
                        )
                self.tissue[id(caller)]["events"].append(row)
                self.active_callbacks[id(frame)] = row
                self.emit_periodic(dict(event="entry", **row))
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
                    self.emit_periodic(dict(event="return_or_unwind", **row))

        def stop(self):
            try:
                result = super().stop()
                result.update(
                    periodic_dispatches=self.periodic_groups,
                    periodic_source_binding=binding,
                    periodic_profile_complete=not self.tissue and not self.active_callbacks,
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
                        "Periodic callback journal close also failed: " + repr(secondary)
                    )

    try:
        return global_events.observer(Observed, stream, source_path, directory)
    except BaseException:
        primary = sys.exception()
        try:
            journal.close()
        except BaseException as secondary:
            primary.add_note("Periodic callback journal close also failed: " + repr(secondary))
        raise


def check_calls(accounting, anchor):
    groups = accounting["periodic_dispatches"]
    require(
        len(groups) == 6 and accounting["periodic_profile_complete"],
        "Incomplete periodic continuation observations",
    )
    keys = membrane.active_keys(anchor["scheduled_options"], anchor["ion_ids"])
    for index, group in enumerate(groups):
        require(
            group["exited"]
            and group["label"] == anchor["labels"][index % 3]
            and [(r["key"], r["operation"]) for r in group["events"]]
            == [(k, op) for k in keys for op in ("callback", "pulse")],
            "Duplicate/omitted/reordered periodic callback/pulse",
        )
        for row in group["events"]:
            require(
                row["returned"] and math.isfinite(row["value"]),
                "Periodic callback/pulse failed or nonfinite",
            )
            configured = anchor["scheduled_options"][row["key"]]
            if row["operation"] == "pulse":
                require(
                    row["parameters"] == [group["label"], *configured[:3]],
                    "Changed periodic pulse parameters",
                )
                continue
            kind = "periodic" if configured[5] == "periodic" else "constant"
            require(
                row["kind"] == kind
                and row["parameters"] == [group["label"]]
                and type(row["scalar"]) is int
                and row["scalar"] == 1
                and row["targets"] == anchor["targets"][row["key"]]
                and row["source_sha256"] == accounting["periodic_source_binding"]["sha256"]
                and row["callback_line"]
                == accounting["periodic_source_binding"][kind + "_callback_line"]
                and row["runtime_code_matches"] is True,
                "Changed actual periodic callback/target/code authority",
            )
            if kind == "constant":
                require(
                    row["value_type"] == "int" and row["value"] == 1,
                    "Changed constant callback in mixed periodic",
                )
            else:
                dynamic = anchor["callbacks"][membrane.MEMBRANE_KEYS[row["key"]]]["dynamic"]
                require(
                    row["value_shape"] == []
                    and row["value_dtype"] == "<f8"
                    and row["program"]["frequency"] == dynamic["frequency"]
                    and row["program"]["phase"] == dynamic["phase"]
                    and row["program"]["provenance"] == dynamic["provenance"],
                    "Periodic recreation lost actual factory-derived parameters/shape",
                )
    counts = accounting["counts"]
    work = {
        name: count
        for name, count in counts.items()
        if name.endswith((".periodic", ".prepared_callback", ".periodic_program", ".evaluate"))
    }
    require(
        any(n.endswith(".periodic") and c > 0 for n, c in work.items())
        and any(n.endswith(".periodic_program") and c > 0 for n, c in work.items()),
        "Missing actual factory/recreation accounting",
    )
    return dict(dispatches=groups, factory_recreation_and_nested_work=work, independent_cases=0)
