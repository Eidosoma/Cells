"""Early selected native temporal-store provenance on an issued parameter owner.

The input is a normalized temporal configuration projection, not a full native
Parameters, YAML, or parser authority. A declaration is never a live issuance.
The original parameter constructor is used by every unselected path. Only the
selected constructor below creates p and its _conf together, before finalizers.
Closed receipts survive checkpoints; decoding cannot issue a live parameter.
"""

import ast
import builtins
import hashlib
import math
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType, SimpleNamespace

from cells.processes import betse_normal_ecm_molecule_temporal_config_context as context
from cells.processes import betse_normal_ecm_molecule_temporal_config_source as source
from cells.processes import betse_normal_ion_join as ions

MODE = "selected_native_temporal_stores"
KIND = "cells.normalized_temporal_configuration_projection@1"
RECEIPT_KIND = "cells.actual_selected_temporal_configuration_stores@1"
CONFIG_KEY, TABLE_KEY = "temporal_configuration", "temporal_event_configuration"
KEYS = {CONFIG_KEY, TABLE_KEY}
MEMBRANE_KEYS = ("Na_mem", "K_mem", "Cl_mem", "Ca_mem")
AUTHORITY = (
    "selected native temporal dictionary/float assignments on the same issued p/_conf; "
    "normalized projection only, not full Parameters/YAML/parser or biological authority"
)
NATIVE_SHA = "f36ec747918aa285ca043fe51086bcff4e4e2198cd4f30a138f1e58a51ecf85e"
POPULATE = source.populate
POPULATE_CODE = POPULATE.__code__
POPULATE_AST = "76490d877736e9119b32a18d5cfbdcd97c809074c308d7b01a12da613464d010"
FLOAT = builtins.float


def require(ok, message):
    if not ok:
        raise ValueError(message)


def same(left, right):
    from cells.processes.betse_normal_ecm_molecule_event_owner import same as compare

    return compare(left, right)


def _closed(value, depth=0):
    """Bound the projection without evaluating, coercing or filling missing keys."""
    require(depth <= 5, "Temporal projection exceeds bounded depth")
    if type(value) in (dict, MappingProxyType):
        require(len(value) <= 16, "Temporal projection mapping too large")
        for key, entry in value.items():
            require(type(key) is str and len(key) <= 128, "Invalid projection key")
            _closed(entry, depth + 1)
    elif type(value) in (list, tuple):
        require(len(value) <= 16, "Temporal projection sequence too large")
        for entry in value:
            _closed(entry, depth + 1)
    else:
        require(
            value is None
            or type(value) in (bool, int)
            or (type(value) is float and math.isfinite(value))
            or (type(value) is str and len(value) <= 4096),
            "Projection accepts bounded plain data only, never __float__/parser/callable owners",
        )


def check_configuration(value):
    require(
        isinstance(value, Mapping)
        and set(value) == {"kind", "mode", "family", "projection", "provenance"}
        and value["kind"] == KIND
        and value["mode"] == MODE
        and value["family"] in ("periodic", "f_sweep")
        and type(value["provenance"]) is str
        and bool(value["provenance"].strip()),
        "Require the explicit selected temporal projection; no supplied-state promotion",
    )
    projection = value["projection"]
    _closed(projection)
    require(
        isinstance(projection, Mapping) and set(projection) <= {"modulator function properties"},
        "Only a normalized temporal projection is accepted; not full configuration/YAML",
    )
    section = projection.get("modulator function properties")
    if isinstance(section, Mapping):
        require(set(section) <= {"periodic", "f_sweep"}, "Non-temporal projection field")
        for name, keys in (
            ("periodic", {"frequency", "phase"}),
            ("f_sweep", {"start frequency", "end frequency"}),
        ):
            if isinstance(section.get(name), Mapping):
                require(set(section[name]) <= keys, "Foreign temporal lookup/default")
    # Missing keys/bad leaf types stay missing/bad: the native assignments own
    # their KeyError/TypeError/ValueError and ordered partial stores later.
    return value


def selection(raw):
    cfg = raw["source_setup"]
    if not KEYS.intersection(cfg):
        return None
    require(KEYS <= set(cfg), "Incomplete explicit temporal store route")
    require(
        "frequency_sweep" not in cfg and not any(key.startswith("periodic_") for key in cfg),
        "Selected stores cannot coexist with manual temporal properties routes",
    )
    value = check_configuration(cfg[CONFIG_KEY])
    material = raw["sim_phase"]["setup"]
    table = cfg[TABLE_KEY]
    require(
        raw["sim_phase"]["time_profile"]["phase"] == "SIM"
        and raw["sim_phase"]["flags"]["_run_sim"] is True,
        "Selected temporal stores require actual SIM/_run_sim, never fabricated INIT",
    )
    require(
        all(
            row == 0
            for name in ("global_options", "scheduled_options")
            for row in material[name].values()
        ),
        "Selected source configuration cannot replace the no-intervention material seam",
    )
    require(
        isinstance(table, Mapping)
        and set(table) == set(material)
        and all(same(table[key], material[key]) for key in material if key != "scheduled_options"),
        "Selected source/material common fields, streams or maps differ",
    )
    family = value["family"]
    options = table["scheduled_options"]
    require(
        all(
            row == 0
            or (
                key in MEMBRANE_KEYS
                and isinstance(row, (tuple, list))
                and len(row) == 6
                and row[5] in ("None", family)
            )
            for key, row in options.items()
        )
        and any(row != 0 and row[5] == family for row in options.values()),
        "Selected stores admit one temporal membrane family and constants only",
    )
    return value


def finalizer_setup(raw):
    return None if selection(raw) is None else raw["source_setup"][TABLE_KEY]


def source_identity():
    require(
        source.populate is POPULATE
        and POPULATE.__code__ is POPULATE_CODE
        and POPULATE.__globals__ is vars(source)
        and "float" not in vars(source)
        and builtins.float is FLOAT
        and SimpleNamespace is context.PARAMETER_NAMESPACE,
        "Changed selected temporal assignment function/globals/float/parameter namespace",
    )
    node = next(
        n
        for n in ast.parse(Path(source.__file__).read_bytes()).body
        if isinstance(n, ast.FunctionDef) and n.name == "populate"
    )
    require(
        hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest()
        == POPULATE_AST,
        "Selected temporal assignment AST drift",
    )
    context.check_original()
    return dict(
        native_parameters_sha256=NATIVE_SHA,
        native_lines=(952, 978),
        source_sha256=hashlib.sha256(Path(source.__file__).read_bytes()).hexdigest(),
        selected_assignment_AST=POPULATE_AST,
        context_sha256=hashlib.sha256(Path(context.__file__).read_bytes()).hexdigest(),
        original_context_AST=context.ORIGINAL_AST,
        context_runtime_bindings=context.binding_record(),
        excluded="gradient stores/lookups, other Parameters/YAML/parser and native constructors",
        temporal_defaults="none; native sweep slope None assigned last",
    )


class Issuance:
    """Ephemeral actual-construction owner, intentionally absent from the codec.

    No method accepts a completed parameter owner or a saved receipt. A failed
    construction stays failed, keeps its exact p/config/partial stores and may
    not be retried on this issuer. Phase is attached only after real augment.
    """

    def __init__(self, binding, completed):
        from cells.processes import betse_normal_ecm_molecule_lifecycle as lifecycle

        require(
            type(binding) is lifecycle.Binding and type(completed) is lifecycle.CompleteInit,
            "Selected issuance requires retained typed lifecycle/complete INIT owners",
        )
        lifecycle.validate_binding(binding)
        from cells.processes import betse_normal_ecm_molecule_event_owner as bridge

        bridge.check_inputs(
            binding.event_owner_inputs, expected_INIT=binding.expected_init_identity
        )
        self.config = selection(binding.inputs)
        require(self.config is not None, "Selected issuance is not the supplied route")
        require(
            completed.binding.identity == binding.expected_init_identity,
            "Foreign original INIT before selected parameter creation",
        )
        self.binding, self.completed = binding, completed
        self.p = self.conf = self.periodic = self.sweep = self.phase = None
        self.initial = None
        self.attempts = 0
        self.stage = "declared_projection_only"

    def __reduce__(self):
        raise TypeError("Live temporal issuance cannot be serialized or reconstructed from data")

    def construct(self, **fields):
        require(self.attempts == 0 and self.p is None, "Parameter issuance is single-attempt")
        self.attempts += 1
        self.stage = "selected_temporal_dictionary_and_float_assignments"
        source_identity()
        require(
            not {"_conf", "periodic_properties", "f_scan_properties"}.intersection(fields),
            "No late patch or supplied temporal property owner",
        )
        self.conf = ions.data(self.config["projection"])
        self.p = SimpleNamespace(_conf=self.conf, **fields)
        # A native exception passes unchanged. No fallback fills or rolls back
        # the partially populated dictionaries; available() retains them.
        source.populate(self.p)
        self.periodic, self.sweep = self.p.periodic_properties, self.p.f_scan_properties
        self.initial = dict(periodic=ions.data(self.periodic), f_sweep=ions.data(self.sweep))
        self.stage = "constructed_before_actual_phase_and_finalizers"
        return self.p

    def attach(self, ctx):
        require(
            self.stage == "constructed_before_actual_phase_and_finalizers"
            and self.phase is None
            and ctx.p is self.p
            and ctx.phase.p is self.p
            and ctx.phase.sim is ctx.sim
            and ctx.phase.cells is ctx.cells,
            "Require original actual context/parameter association; no fabricated phase",
        )
        self.phase = ctx.phase
        self.check(ctx.phase)

    def check(self, phase, *, resolved=False):
        require(
            self.initial is not None
            and self.phase is phase
            and phase.p is self.p
            and self.p._conf is self.conf
            and self.p.periodic_properties is self.periodic
            and self.p.f_scan_properties is self.sweep
            and same(self.conf, self.config["projection"])
            and same(self.periodic, self.initial["periodic"])
            and all(
                same(self.sweep[key], self.initial["f_sweep"][key]) for key in ("f start", "f stop")
            )
            and (resolved or self.sweep["f slope"] is None),
            "Changed issued p/config/store/phase association or temporal values",
        )
        require(selection(self.binding.inputs) is not None, "Changed retained selected route")

    def receipt(self, observation):
        from cells.processes import betse_normal_ecm_molecule_periodic_authority as periodic
        from cells.processes import betse_normal_ecm_molecule_sweep_authority as sweep

        expected = (
            periodic.FactoryObservation
            if self.config["family"] == "periodic"
            else sweep.FactoryObservation
        )
        require(
            type(observation) is expected
            and observation.parameter_issuance is self
            and observation.p is self.p
            and observation.phase is self.phase
            and observation.complete is True
            and observation.pending is None
            and observation.entry_attempts == observation.return_events == len(observation.selected)
            and not observation.return_or_unwind_events,
            "Receipt requires complete original observed temporal finalizers, never supplied state",
        )
        require(
            self.phase is not None and self.phase.kind == "SIM" and self.p._run_sim is True,
            "Selected receipt requires the actual SIM epoch, not a declaration",
        )
        self.check(self.phase, resolved=True)
        value = dict(
            kind=RECEIPT_KIND,
            authority=AUTHORITY,
            source=source_identity(),
            source_binding_identity=self.binding.identity,
            source_INIT_binding_identity=self.completed.binding.identity,
            source_INIT_parent_identity=self.completed.parent.identity,
            source_complete_INIT_identity=self.completed.identity,
            source_SIM_declaration_identity=self.binding.declaration.identity,
            configuration=ions.data(self.config),
            initial=ions.data(self.initial),
            after=dict(periodic=ions.data(self.periodic), f_sweep=ions.data(self.sweep)),
            runtime=dict(
                parameter_object_id=id(self.p),
                configuration_object_id=id(self.conf),
                periodic_store_object_id=id(self.periodic),
                sweep_store_object_id=id(self.sweep),
            ),
            stage="after_actual_temporal_finalizers_before_event_finalized",
            parameter_constructions=self.attempts,
            selected_dictionary_creations=2,
            selected_float_lookups=4,
            factory_returns=len(observation.records),
            sweep_slope_initial_assignment=None,
            replayed=False,
            callable_instance_persisted=False,
            independent_cases=0,
        )
        return dict(value, identity=ions.digest(value))

    def available(self):
        return dict(
            stage=self.stage,
            parameter_construction_attempts=self.attempts,
            configuration=self.conf,
            partial_stores=None
            if self.p is None
            else {
                key: getattr(self.p, key)
                for key in ("periodic_properties", "f_scan_properties")
                if hasattr(self.p, key)
            },
            live_owner_admission=False,
        )


def validate_receipt(binding, fields, *, completed=None):
    """Closed source/binding check, no float lookup, owner construction or replay."""
    configured = selection(binding.inputs)
    saved = fields.get("temporal_configuration_store")
    if configured is None:
        require(saved is None, "Unselected route cannot promote a store receipt")
        return None
    require(isinstance(saved, Mapping), "Missing actual selected parameter-store observation")
    value = {key: entry for key, entry in saved.items() if key != "identity"}
    require(saved["identity"] == ions.digest(value), "Changed selected store receipt digest")
    require(
        saved["kind"] == RECEIPT_KIND
        and saved["authority"] == AUTHORITY
        and same(saved["source"], source_identity())
        and same(saved["configuration"], configured)
        and saved["source_binding_identity"] == binding.identity
        and saved["source_INIT_binding_identity"] == binding.expected_init_identity
        and saved["source_SIM_declaration_identity"] == binding.declaration.identity,
        "Foreign selected source/configuration/INIT/SIM binding",
    )
    if completed is not None:
        require(
            saved["source_INIT_parent_identity"] == completed.parent.identity
            and saved["source_complete_INIT_identity"] == completed.identity,
            "Foreign selected store original INIT parent",
        )
    require(
        saved["stage"] == "after_actual_temporal_finalizers_before_event_finalized"
        and type(saved["parameter_constructions"]) is int
        and saved["parameter_constructions"] == 1
        and type(saved["selected_dictionary_creations"]) is int
        and saved["selected_dictionary_creations"] == 2
        and type(saved["selected_float_lookups"]) is int
        and saved["selected_float_lookups"] == 4
        and type(saved["factory_returns"]) is int
        and saved["factory_returns"]
        == sum(
            row != 0 and row[5] == configured["family"]
            for row in binding.inputs["source_setup"][TABLE_KEY]["scheduled_options"].values()
        )
        and saved["sweep_slope_initial_assignment"] is None
        and saved["replayed"] is False
        and saved["callable_instance_persisted"] is False
        and type(saved["independent_cases"]) is int
        and saved["independent_cases"] == 0,
        "Invalid selected constructor work/epoch/callable scope",
    )
    runtime = saved["runtime"]
    require(
        set(runtime)
        == {
            "parameter_object_id",
            "configuration_object_id",
            "periodic_store_object_id",
            "sweep_store_object_id",
        }
        and all(type(number) is int and number > 0 for number in runtime.values())
        and len(set(runtime.values())) == 4,
        "Invalid retained runtime owner observations",
    )
    from cells.processes import betse_normal_ecm_molecule_periodic_authority as periodic
    from cells.processes import betse_normal_ecm_molecule_sweep_authority as sweep

    initial, after = saved["initial"], saved["after"]
    require(set(initial) == set(after) == {"periodic", "f_sweep"}, "Incomplete temporal stores")
    periodic.properties(initial["periodic"])
    periodic.properties(after["periodic"])
    sweep.properties(initial["f_sweep"], resolved=False)
    sweep.properties(after["f_sweep"], resolved=configured["family"] == "f_sweep")
    require(
        initial["f_sweep"]["f slope"] is None
        and same(initial["periodic"], after["periodic"])
        and all(
            same(initial["f_sweep"][key], after["f_sweep"][key]) for key in ("f start", "f stop")
        )
        and same(fields["frequency_sweep_after"], after["f_sweep"]),
        "Changed initial/surviving selected temporal stores",
    )
    if configured["family"] == "periodic":
        require(
            after["f_sweep"]["f slope"] is None
            and same(fields["periodic_properties_after"], after["periodic"]),
            "Foreign periodic/sweep release state",
        )
    return saved


def callback_association(issuance, phase):
    """Check actual live store ownership at each factory boundary, not decode."""
    require(type(issuance) is Issuance, "Missing actual selected configuration issuance")
    require(
        phase.kind == "SIM" and phase.p._run_sim is True,
        "Selected callback requires actual SIM phase/legacy flag",
    )
    issuance.check(phase, resolved=True)
    return dict(
        source_binding_identity=issuance.binding.identity,
        configuration_identity=ions.digest(issuance.config),
        authority=AUTHORITY,
    )
