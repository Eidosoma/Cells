"""Closed observations of the literal SIM sweep factory, never saved callables.

The live observer checks the actual factory return/closure against its retained
parameter owner. Restart retains data and source provenance only. install_owner
recreates a declared sweep through the existing qualified time-law producer;
that creation and any validation replay are work, not independent cases.
"""

import copy
import hashlib
import math
import sys
from collections.abc import Mapping
from pathlib import Path
from types import CodeType, FunctionType

import numpy as np

from cells.processes import betse_normal_ecm_molecule_lifecycle_source as source
from cells.processes import betse_normal_ecm_molecule_temporal_config as temporal
from cells.processes import betse_normal_ion_join as ions
from cells.processes import betse_time_modulation as time_laws

MEMBRANE_KEYS = dict(Na_mem="Namem", K_mem="Kmem", Cl_mem="Clmem", Ca_mem="Camem")
FACTORY = source.f_sweep
FINALIZER = source._finalize_events_tissue
FACTORY_CODE = FACTORY.__code__
FINALIZER_CODE = FINALIZER.__code__
KIND = "cells.actual_finalized_SIM_sweep_callback@1"


def require(ok, message):
    if not ok:
        raise ValueError(message)


def same(actual, expected):
    if isinstance(expected, Mapping):
        return (
            isinstance(actual, Mapping)
            and set(actual) == set(expected)
            and all(same(actual[key], value) for key, value in expected.items())
        )
    if isinstance(expected, (list, tuple)):
        return (
            isinstance(actual, (list, tuple))
            and len(actual) == len(expected)
            and all(same(a, b) for a, b in zip(actual, expected, strict=True))
        )
    return type(actual) is type(expected) and actual == expected


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def callback_code():
    codes = [c for c in FACTORY_CODE.co_consts if type(c) is CodeType]
    require(len(codes) == 1, "Changed literal sweep factory closure")
    code = codes[0]
    require(
        code.co_name == "<lambda>"
        and code.co_argcount == 1
        and code.co_varnames == ("t",)
        and code.co_freevars == ("f_slope", "p"),
        "Changed literal sweep callback contract",
    )
    return code


def source_identity():
    require(
        source.f_sweep is FACTORY
        and source.mod.f_sweep is FACTORY
        and source._finalize_events_tissue is FINALIZER
        and FACTORY.__code__ is FACTORY_CODE
        and FINALIZER.__code__ is FINALIZER_CODE
        and FACTORY.__globals__ is vars(source)
        and source.np is np,
        "Foreign sweep factory/source globals",
    )
    code = callback_code()
    return dict(
        source_module=source.__name__,
        source_sha256=hashlib.sha256(Path(source.__file__).read_bytes()).hexdigest(),
        factory_line=FACTORY.__code__.co_firstlineno,
        factory_bytecode_sha256=hashlib.sha256(FACTORY.__code__.co_code).hexdigest(),
        callback_line=code.co_firstlineno,
        callback_bytecode_sha256=hashlib.sha256(code.co_code).hexdigest(),
        time_law_id=time_laws.LAW_ID,
        time_law_sha256=hashlib.sha256(Path(time_laws.__file__).read_bytes()).hexdigest(),
    )


def properties(value, *, resolved):
    require(
        isinstance(value, Mapping) and set(value) == {"f start", "f stop", "f slope"},
        "Require complete retained source sweep properties",
    )
    require(
        all(finite(value[k]) for k in ("f start", "f stop"))
        and (finite(value["f slope"]) or (not resolved and value["f slope"] is None)),
        "Unresolved/nonfinite source sweep coefficient",
    )
    return ions.data(value)


def inspect_callback(callback, scalar, parameters):
    require(
        type(callback) is FunctionType
        and callback.__code__ is callback_code()
        and callback.__globals__ is vars(source)
        and callback.__defaults__ is None
        and callback.__kwdefaults__ is None
        and callback.__closure__ is not None
        and len(callback.__closure__) == 2
        and type(scalar) is int
        and scalar == 1,
        "Require actual source sweep callback/code/scalar authority",
    )
    closure = dict(
        zip(
            callback.__code__.co_freevars,
            (cell.cell_contents for cell in callback.__closure__),
            strict=True,
        )
    )
    require(
        closure["p"] is parameters
        and same(
            closure["f_slope"], properties(parameters.f_scan_properties, resolved=True)["f slope"]
        ),
        "Foreign retained sweep parameter/closure owner",
    )
    return closure["f_slope"]


def record(
    suffix,
    sequence,
    initial,
    before,
    after,
    duration,
    targets,
    profiles,
    *,
    configuration_store=None,
):
    """Expected data shape only; this never produces a live factory receipt."""
    value = dict(
        kind=KIND,
        suffix=suffix,
        sequence=sequence,
        source=source_identity(),
        source_function="f_sweep",
        source_scalar=1,
        source_configuration=dict(frequency_sweep=ions.data(initial), sim_total_s=duration),
        before=ions.data(before),
        after=ions.data(after),
        slope_policy="factory_resolved_None" if before["f slope"] is None else "retained_explicit",
        closure=dict(
            f_slope=after["f slope"], parameters=ions.data(after), retained_parameter_owner=True
        ),
        targets=list(targets),
        profiles=list(profiles),
        source_phase="SIM",
        legacy_run_sim=True,
        factory_return_observed=True,
        evaluated=False,
        callable_instance_persisted=False,
    )
    if configuration_store is not None:
        value["configuration_store"] = ions.data(configuration_store)
    return dict(value, identity=ions.digest(value))


class FactoryObservation:
    """Observe source entry/return while forwarding the existing work profiler.

    Runtime objects stay on this temporary observer. Only data() and records
    are published; neither decoding nor admission installs this observer.
    """

    def __init__(self, owner, phase, initial, *, parameter_issuance=None):
        self.owner, self.phase, self.p = owner, phase, phase.p
        self.parameter_issuance = parameter_issuance
        if parameter_issuance is not None:
            temporal.callback_association(parameter_issuance, phase)
        self.initial = properties(initial, resolved=False)
        self.duration = self.p.sim_time_total
        require(
            self.p._run_sim is True
            and finite(self.p.sim_time_total)
            and self.p.sim_time_total > 0
            and same(self.initial, self.p.f_scan_properties),
            "Sweep factory requires retained SIM configuration/duration",
        )
        self.selected = [
            (key, suffix)
            for key, suffix in MEMBRANE_KEYS.items()
            if self.p.scheduled_options[key] != 0 and self.p.scheduled_options[key][5] == "f_sweep"
        ]
        require(self.selected, "Require an explicitly configured membrane sweep")
        self.entries, self.records, self.returned = [], {}, {}
        self.entry_attempts = self.return_events = 0
        self.return_or_unwind_events = []
        self.pending = None
        self.complete = False
        self.previous = self.installed = None

    def observe(self, frame, event, arg):
        if frame.f_code is not FACTORY_CODE or event not in ("call", "return"):
            return
        if event == "call":
            self.entry_attempts += 1
            self.complete = False
        else:
            self.return_events += 1
            if arg is None:
                # CPython uses return(None) for both an exception unwind and
                # a normal None return. Do not validate a successful tuple or
                # inspect possibly half-mutated parameters from this event.
                # Keep the pending entry incomplete: __exit__ propagates an
                # active source error unchanged; finish refuses a normal None.
                self.complete = False
                matched = self.pending is not None and self.pending[0] == id(frame)
                sequence = self.pending[3]["sequence"] if matched else None
                self.return_or_unwind_events.append(
                    dict(sequence=sequence, matched_entry=matched, return_value_is_None=True)
                )
                if matched:
                    self.pending[3].update(status="return_or_unwind_incomplete")
                return
        require(
            self.p._run_sim is True and same(self.p.sim_time_total, self.duration),
            "Changed retained SIM sweep parameter context",
        )
        if self.parameter_issuance is not None:
            temporal.callback_association(self.parameter_issuance, self.phase)
        if event == "call":
            require(
                self.pending is None and len(self.entries) < len(self.selected),
                "Duplicate/unowned sweep factory entry",
            )
            key, suffix = self.selected[len(self.entries)]
            before = properties(self.p.f_scan_properties, resolved=False)
            entry = dict(
                sequence=len(self.entries),
                suffix=suffix,
                before=before,
                status="entered",
                targets=list(getattr(self.owner, "targets_" + suffix)),
            )
            self.entries.append(entry)
            caller = frame.f_back
            require(
                frame.f_globals is vars(source)
                and frame.f_locals["p"] is self.p
                and frame.f_locals["cells"] is self.phase.cells
                and frame.f_locals["pc"] is getattr(self.owner, "targets_" + suffix)
                and caller is not None
                and caller.f_code is FINALIZER_CODE
                and caller.f_globals is vars(source)
                and caller.f_locals["self"] is self.owner
                and caller.f_locals["phase"] is self.phase,
                "Foreign sweep factory/finalizer/target/parameter association",
            )
            self.pending = (id(frame), key, suffix, entry)
            return
        require(
            self.pending is not None and self.pending[0] == id(frame),
            "Missing sweep factory entry before return",
        )
        _, key, suffix, entry = self.pending
        require(
            type(arg) is tuple and len(arg) == 2, "Sweep factory did not return its scalar/callback"
        )
        scalar, callback = arg
        after = properties(self.p.f_scan_properties, resolved=True)
        inspect_callback(callback, scalar, self.p)
        require(
            same(frame.f_locals["f_slope"], after["f slope"])
            and all(same(entry["before"][k], after[k]) for k in ("f start", "f stop"))
            and (
                entry["before"]["f slope"] is None
                or same(entry["before"]["f slope"], after["f slope"])
            ),
            "Changed source sweep mutation or captured coefficient",
        )
        self.records[suffix] = record(
            suffix,
            entry["sequence"],
            self.initial,
            entry["before"],
            after,
            self.p.sim_time_total,
            entry["targets"],
            self.p.scheduled_options[key][4],
            **(
                dict(
                    configuration_store=temporal.callback_association(
                        self.parameter_issuance, self.phase
                    )
                )
                if self.parameter_issuance is not None
                else {}
            ),
        )
        self.returned[suffix] = callback
        entry.update(status="returned", after=after)
        self.pending = None

    def profile(self, frame, event, arg):
        if self.previous is not None:
            self.previous(frame, event, arg)
        self.observe(frame, event, arg)

    def __enter__(self):
        source_identity()
        self.previous = sys.getprofile()
        self.installed = self.profile
        sys.setprofile(self.installed)
        return self

    def finish(self):
        self.complete = False
        if self.parameter_issuance is not None:
            temporal.callback_association(self.parameter_issuance, self.phase)
        require(
            self.pending is None
            and not self.return_or_unwind_events
            and len(self.records) == len(self.selected),
            "Missing/omitted sweep factory return",
        )
        require(
            self.p._run_sim is True
            and same(self.p.sim_time_total, self.duration)
            and same(
                properties(self.p.f_scan_properties, resolved=True),
                self.records[self.selected[-1][1]]["after"],
            ),
            "Changed retained parameters after source sweep finalization",
        )
        for _, suffix in self.selected:
            require(
                getattr(self.owner, "dyna_" + suffix, None) is self.returned[suffix],
                "Finalizer replaced its observed sweep callback",
            )
            inspect_callback(self.returned[suffix], getattr(self.owner, "scalar_" + suffix), self.p)
        self.complete = True

    def __exit__(self, kind, error, tb):
        intact = sys.getprofile() is self.installed
        sys.setprofile(self.previous)
        if error is not None:
            if not intact:
                error.add_note(
                    "Sweep factory profiler lost before restoration; observation incomplete"
                )
            return False
        require(intact, "Sweep factory work profiler was replaced")
        self.finish()

    def data(self):
        return dict(
            kind="cells.source_sweep_factory_observation@1",
            complete=self.complete,
            factory_entry_attempts=self.entry_attempts,
            factory_return_events=self.return_events,
            factory_returns=len(self.records),
            return_or_unwind_events=copy.deepcopy(self.return_or_unwind_events),
            entries=copy.deepcopy(self.entries),
            records=copy.deepcopy(self.records),
            independent_cases=0,
            callable_instances_persisted=False,
        )


def validate(source_binding, owner, published, fields):
    """Compare an existing observed receipt to its retained typed source graph."""
    selected = [
        (key, suffix)
        for key, suffix in MEMBRANE_KEYS.items()
        if owner["scheduled_options"][key] != 0 and owner["scheduled_options"][key][5] == "f_sweep"
    ]
    require(selected, "Require an actual finalized membrane sweep")
    authorities = fields.get("sweep_callback_authority")
    require(
        isinstance(authorities, Mapping) and set(authorities) == {s for _, s in selected},
        "Missing/foreign actual sweep callback authority; no hydration allowed",
    )
    original = source_binding.inputs
    store = temporal.validate_receipt(source_binding, fields)
    initial = properties(
        original["source_setup"]["frequency_sweep"]
        if store is None
        else store["initial"]["f_sweep"],
        resolved=False,
    )
    after = properties(fields["frequency_sweep_after"], resolved=True)
    duration = original["sim_phase"]["time_profile"]["sim_total_s"]
    require(
        finite(duration)
        and duration > 0
        and fields["source_phase"] == "SIM"
        and fields["legacy_run_sim"] is True
        and type(fields["event_fire_calls"]) is int
        and fields["event_fire_calls"] == 0,
        "Foreign actual sweep phase/epoch/duration",
    )
    previous = initial
    for index, (key, suffix) in enumerate(selected):
        row, callback = owner["scheduled_options"][key], owner["callbacks"][suffix]
        expected = record(
            suffix,
            index,
            initial,
            previous,
            after,
            duration,
            published.owner["handler_fields"]["targets_" + suffix],
            row[4],
            **(
                dict(
                    configuration_store=dict(
                        source_binding_identity=source_binding.identity,
                        configuration_identity=ions.digest(store["configuration"]),
                        authority=temporal.AUTHORITY,
                    )
                )
                if store is not None
                else {}
            ),
        )
        require(
            same(authorities[suffix], expected),
            "Changed actual sweep factory/closure/source authority",
        )
        dynamic = callback["dynamic"]
        require(
            set(dynamic) == {"kind", "start", "slope", "provenance"}
            and dynamic["kind"] == "sweep"
            and same(dynamic["start"], after["f start"])
            and same(dynamic["slope"], after["f slope"])
            and type(dynamic["provenance"]) is str
            and bool(dynamic["provenance"].strip())
            and callback["source_function"] == "f_sweep"
            and type(callback["source_scalar"]) is int
            and callback["source_scalar"] == 1,
            "Changed retained sweep dynamic coefficients/scalar",
        )
        require(
            all(same(initial[k], after[k]) for k in ("f start", "f stop"))
            and (previous["f slope"] is None or same(previous["f slope"], after["f slope"])),
            "Changed source sweep setup mutation order",
        )
        previous = after
    return authorities
