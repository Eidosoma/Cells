"""Actual source periodic factory/parameter authority; closed restart data only.

The literal factory is periodic(pc,cells,p), with a live p closure and scalar1.
periodic_properties is a required supplied source-configuration seam, retained
on the typed lifecycle binding. This does not attest native Parameters parsing.
Only actual setup observes a factory return; declarations never supply one.
"""

import ast
import hashlib
from collections.abc import Mapping
from pathlib import Path
from types import CodeType, FunctionType

import numpy as np

from cells.processes import betse_normal_ecm_init_phase_setup as common
from cells.processes import betse_normal_ecm_molecule_lifecycle_source as source
from cells.processes import betse_normal_ecm_molecule_sweep_authority as sweep
from cells.processes import betse_normal_ecm_molecule_temporal_config as temporal
from cells.processes import betse_normal_ion_join as ions
from cells.processes import betse_time_modulation as time_laws

MEMBRANE_KEYS = sweep.MEMBRANE_KEYS
FACTORY, FINALIZER = source.periodic, source._finalize_events_tissue
FACTORY_CODE, FINALIZER_CODE = FACTORY.__code__, FINALIZER.__code__
KIND = "cells.actual_finalized_SIM_periodic_callback@1"
ROUTE = "finalized_periodic"
NATIVE_PINS = {
    "betse/science/math/modulate.py": (
        "c29f4ae27930f00780736e075183e61f44263dd0caa9d7c2f9a30971f616bff7"
    ),
    "betse/science/parameters.py": (
        "f36ec747918aa285ca043fe51086bcff4e4e2198cd4f30a138f1e58a51ecf85e"
    ),
}
NATIVE_CONFIGURATION_PATH = ("modulator function properties", "periodic")
COMMON_VALIDATE = common.validate
COMMON_VALIDATE_CODE = COMMON_VALIDATE.__code__
COMMON_VALIDATE_AST = "41ff5ff137e4026bdf7263dabf57901f06b428cc089c94ef4e2987a14d210597"
require, same = sweep.require, sweep.same
real, perturbations = common.real, common.perturbations
GLOBAL_KEYS, TISSUE_KEYS = common.GLOBAL_KEYS, common.TISSUE_KEYS


def python_restore(saved):
    # Delegate at call time so real RNG validation remains observable/guardable.
    return common.python_restore(saved)


def properties(value):
    require(
        isinstance(value, Mapping)
        and set(value) == {"frequency", "phase"}
        and all(type(v) is float and sweep.finite(v) for v in value.values()),
        "Require explicit finite native-parsed float periodic frequency/phase; no defaults",
    )
    return ions.data(value)


def selected(options):
    return [
        (key, suffix)
        for key, suffix in MEMBRANE_KEYS.items()
        if isinstance(options.get(key), (list, tuple))
        and len(options[key]) == 6
        and options[key][5] == "periodic"
    ]


def configuration(raw):
    cfg = raw["source_setup"]
    material = raw.get("sim_phase", {}).get("setup", {})
    table = cfg.get("periodic_event_configuration")
    options = {} if table is None else table.get("scheduled_options", {})
    active = selected(options)
    supplied = {"periodic_properties", "periodic_event_configuration", "periodic_preparation_route"}
    if not (supplied & set(cfg)) and not selected(material.get("scheduled_options", {})):
        return None
    require(
        active and supplied <= set(cfg) and cfg["periodic_preparation_route"] == ROUTE,
        "Periodic configuration must accompany actual scheduled periodic source options",
    )
    require(
        raw["sim_phase"]["time_profile"]["phase"] == "SIM"
        and raw["sim_phase"]["flags"]["_run_sim"] is True,
        "Periodic finalizer configuration requires actual SIM/_run_sim",
    )
    require(
        all(
            row == 0
            for name in ("global_options", "scheduled_options")
            for row in material[name].values()
        ),
        "Periodic source table must not replace the no-intervention material phase",
    )
    require(
        isinstance(table, Mapping)
        and set(table) == set(material)
        and all(
            same(table[name], material[name]) for name in material if name != "scheduled_options"
        ),
        "Periodic source table changed common material/source schema, maps or stream fields",
    )
    require(
        all(
            row == 0 or (key in MEMBRANE_KEYS and len(row) == 6 and row[5] in ("None", "periodic"))
            for key, row in options.items()
        ),
        "Periodic scope admits membrane periodic/constant only; sweep/pressure/ecmJ stay closed",
    )
    return properties(cfg["periodic_properties"])


def finalizer_setup(raw):
    """Original material setup stays no-intervention; source table is explicit."""
    return (
        None if configuration(raw) is None else raw["source_setup"]["periodic_event_configuration"]
    )


def require_source(binding, configured, *, configuration_store=None):
    from cells.processes import betse_normal_ecm_molecule_event_owner as bridge
    from cells.processes import betse_normal_ecm_molecule_lifecycle as lifecycle

    configured = properties(configured)
    require(
        type(binding) is lifecycle.Binding and type(binding.event_owner_inputs) is bridge.Inputs,
        "Periodic setup requires retained typed lifecycle/source-input owners",
    )
    if temporal.selection(binding.inputs) is None:
        require(
            configuration_store is None and same(configuration(binding.inputs), configured),
            "Foreign retained periodic source configuration",
        )
    else:
        require(
            temporal.selection(binding.inputs)["family"] == "periodic"
            and isinstance(configuration_store, Mapping)
            and same(configured, configuration_store["initial"]["periodic"]),
            "Missing selected periodic constructor receipt",
        )


def common_guard_identity():
    require(
        common.validate is COMMON_VALIDATE and common.validate.__code__ is COMMON_VALIDATE_CODE,
        "Shared setup validator replaced; periodic SIM guards require review",
    )
    node = next(
        n
        for n in ast.parse(Path(common.__file__).read_bytes()).body
        if isinstance(n, ast.FunctionDef) and n.name == "validate"
    )
    require(
        hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest()
        == COMMON_VALIDATE_AST,
        "Shared setup validator changed; periodic SIM guards require review",
    )


def validate_SIM_setup(raw, base, *, phase, run_sim, preparation_route):
    require(
        phase == "SIM"
        and run_sim is True
        and preparation_route == ROUTE
        and selected(raw["scheduled_options"]),
        "Periodic declaration validation is SIM-only; INIT admission unchanged",
    )
    require(
        all(
            row == 0 or (key in MEMBRANE_KEYS and len(row) == 6 and row[5] in ("None", "periodic"))
            for key, row in raw["scheduled_options"].items()
        ),
        "Periodic SIM declaration keeps pressure/ecmJ/sweep families closed",
    )
    common_guard_identity()
    return _validate_SIM_periodic_setup(raw, base)


def callback_code():
    codes = [c for c in FACTORY_CODE.co_consts if type(c) is CodeType]
    require(
        len(codes) == 1
        and codes[0].co_name == "<lambda>"
        and codes[0].co_argcount == 1
        and codes[0].co_varnames == ("t",)
        and codes[0].co_freevars == ("p",),
        "Changed literal periodic callback contract",
    )
    return codes[0]


def source_identity():
    require(
        source.periodic is FACTORY
        and source.mod.periodic is FACTORY
        and source._finalize_events_tissue is FINALIZER
        and FACTORY.__code__ is FACTORY_CODE
        and FINALIZER.__code__ is FINALIZER_CODE
        and FACTORY.__globals__ is vars(source)
        and source.np is np,
        "Foreign periodic factory/source code/globals",
    )
    code = callback_code()
    return dict(
        source_module=source.__name__,
        source_sha256=hashlib.sha256(Path(source.__file__).read_bytes()).hexdigest(),
        factory_line=FACTORY_CODE.co_firstlineno,
        factory_bytecode_sha256=hashlib.sha256(FACTORY_CODE.co_code).hexdigest(),
        callback_line=code.co_firstlineno,
        callback_bytecode_sha256=hashlib.sha256(code.co_code).hexdigest(),
        native_pins=NATIVE_PINS,
        native_factory="periodic",
        native_configuration_path=NATIVE_CONFIGURATION_PATH,
        qualified_time_law=time_laws.LAW_ID,
        time_law_sha256=hashlib.sha256(Path(time_laws.__file__).read_bytes()).hexdigest(),
    )


def inspect_callback(callback, scalar, parameters):
    require(
        type(callback) is FunctionType
        and callback.__code__ is callback_code()
        and callback.__globals__ is vars(source)
        and callback.__defaults__ is None
        and callback.__kwdefaults__ is None
        and callback.__closure__ is not None
        and len(callback.__closure__) == 1
        and callback.__closure__[0].cell_contents is parameters
        and type(scalar) is int
        and scalar == 1,
        "Require actual periodic factory code/closure/p/scalar authority",
    )
    return properties(parameters.periodic_properties)


def record(suffix, sequence, configured, targets, profiles, binding, *, configuration_store=None):
    value = dict(
        kind=KIND,
        suffix=suffix,
        sequence=sequence,
        source=source_identity(),
        source_function="periodic",
        source_scalar=1,
        before=properties(configured),
        after=properties(configured),
        source_binding_identity=binding.identity,
        source_configuration_provenance=binding.inputs["source_setup"]["provenance"],
        configuration_authority=(
            "conditional explicitly supplied properties on retained typed binding; "
            "native parser derivation unestablished"
        ),
        closure=dict(
            retained_parameter_owner=True,
            retained_parameter_mapping=True,
            periodic_properties=properties(configured),
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
        value["configuration_authority"] = temporal.AUTHORITY
        value["configuration_store"] = ions.data(configuration_store)
    return dict(value, identity=ions.digest(value))


class FactoryObservation(sweep.FactoryObservation):
    """Source-specific capture, sharing S1 profile/exit/failure mechanics."""

    def __init__(self, owner, phase, configured, *, binding, parameter_issuance=None):
        self.parameter_issuance = parameter_issuance
        if parameter_issuance is not None:
            temporal.callback_association(parameter_issuance, phase)
        require_source(
            binding,
            configured,
            **(
                dict(configuration_store=dict(initial=parameter_issuance.initial))
                if parameter_issuance is not None
                else {}
            ),
        )
        self.owner, self.phase, self.p, self.binding = owner, phase, phase.p, binding
        self.initial = properties(configured)
        self.parameter_owner = self.p.periodic_properties
        self.duration = self.p.sim_time_total
        self.selected = selected(self.p.scheduled_options)
        require(self.selected, "Require actual scheduled periodic membrane options")
        self.entries, self.records, self.returned = [], {}, {}
        self.entry_attempts = self.return_events = 0
        self.return_or_unwind_events = []
        self.pending = None
        self.complete = False
        self.previous = self.installed = None
        self.check_context()

    def check_context(self):
        if self.parameter_issuance is not None:
            temporal.callback_association(self.parameter_issuance, self.phase)
        require(
            self.p._run_sim is True
            and same(self.p.sim_time_total, self.duration)
            and self.p.periodic_properties is self.parameter_owner
            and same(properties(self.parameter_owner), self.initial),
            "Changed retained periodic parameter/mapping/phase owner",
        )

    def __enter__(self):
        source_identity()
        return super().__enter__()

    def observe(self, frame, event, arg):
        if frame.f_code is not FACTORY_CODE or event not in ("call", "return"):
            return
        if event == "call":
            self.entry_attempts += 1
            self.complete = False
        else:
            self.return_events += 1
            if arg is None:
                self.complete = False
                matched = self.pending is not None and self.pending[0] == id(frame)
                self.return_or_unwind_events.append(
                    dict(
                        sequence=self.pending[3]["sequence"] if matched else None,
                        matched_entry=matched,
                        return_value_is_None=True,
                    )
                )
                if matched:
                    self.pending[3].update(status="return_or_unwind_incomplete")
                return
        self.check_context()
        if event == "call":
            require(
                self.pending is None and len(self.entries) < len(self.selected),
                "Duplicate/unowned periodic factory entry",
            )
            key, suffix = self.selected[len(self.entries)]
            entry = dict(
                sequence=len(self.entries),
                suffix=suffix,
                before=properties(self.parameter_owner),
                targets=list(getattr(self.owner, "targets_" + suffix)),
                status="entered",
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
                "Foreign periodic factory/finalizer/target/parameter association",
            )
            self.pending = (id(frame), key, suffix, entry)
            return
        require(
            self.pending is not None and self.pending[0] == id(frame),
            "Missing periodic factory entry before return",
        )
        _, key, suffix, entry = self.pending
        require(
            type(arg) is tuple and len(arg) == 2, "Periodic factory did not return scalar/callback"
        )
        scalar, callback = arg
        inspect_callback(callback, scalar, self.p)
        self.records[suffix] = record(
            suffix,
            entry["sequence"],
            self.initial,
            entry["targets"],
            self.p.scheduled_options[key][4],
            self.binding,
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
        entry.update(status="returned", after=properties(self.parameter_owner))
        self.pending = None

    def finish(self):
        self.complete = False
        require(
            self.pending is None
            and not self.return_or_unwind_events
            and len(self.records) == len(self.selected),
            "Missing/omitted periodic factory return",
        )
        self.check_context()
        for _, suffix in self.selected:
            require(
                getattr(self.owner, "dyna_" + suffix, None) is self.returned[suffix],
                "Finalizer replaced periodic callback",
            )
            inspect_callback(self.returned[suffix], getattr(self.owner, "scalar_" + suffix), self.p)
        self.complete = True

    def data(self):
        return dict(super().data(), kind="cells.source_periodic_factory_observation@1")


def validate(binding, owner, published, fields):
    store = temporal.validate_receipt(binding, fields)
    configured = configuration(binding.inputs) if store is None else store["initial"]["periodic"]
    require_source(
        binding, configured, **(dict(configuration_store=store) if store is not None else {})
    )
    selected_options = selected(owner["scheduled_options"])
    authorities = fields.get("periodic_callback_authority")
    require(
        selected_options
        and isinstance(authorities, Mapping)
        and set(authorities) == {s for _, s in selected_options},
        "Missing/foreign actual periodic authority; no hydration allowed",
    )
    require(
        fields["source_phase"] == "SIM"
        and fields["legacy_run_sim"] is True
        and type(fields["event_fire_calls"]) is int
        and fields["event_fire_calls"] == 0
        and same(properties(fields["periodic_properties_after"]), configured),
        "Foreign actual periodic phase/configuration/epoch",
    )
    for index, (key, suffix) in enumerate(selected_options):
        callback = owner["callbacks"][suffix]
        expected = record(
            suffix,
            index,
            configured,
            published.owner["handler_fields"]["targets_" + suffix],
            owner["scheduled_options"][key][4],
            binding,
            **(
                dict(
                    configuration_store=dict(
                        source_binding_identity=binding.identity,
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
            "Changed periodic factory/source/closure/config authority",
        )
        require(
            callback["source_function"] == "periodic"
            and type(callback["source_scalar"]) is int
            and callback["source_scalar"] == 1
            and same(
                callback["dynamic"],
                dict(
                    kind="periodic",
                    frequency=configured["frequency"],
                    phase=configured["phase"],
                    provenance="Actual SIM periodic finalizer result",
                ),
            ),
            "Changed actual periodic parameters/scalar/time program",
        )


# SIM-only copy of the pinned common setup guards; only the function whitelist
# differs. validate_SIM_setup refuses if the original guards change. No INIT
# caller uses this function and no callback name is disguised for validation.
def _validate_SIM_periodic_setup(raw, base):
    if (
        set(raw)
        != {
            "kind",
            "provenance",
            "receipts",
            "numpy_rng",
            "python_rng",
            "channel_noise_level",
            "global_options",
            "scheduled_options",
            "maps",
            "frequency_sweep",
            "dynamic_noise",
        }
        or raw["kind"] != "cells.supplied_pre_INIT_setup@1"
    ):
        raise ValueError("Require the complete pre-setup INIT declaration")
    if not isinstance(raw["provenance"], str) or not raw["provenance"].strip():
        raise ValueError("Require supplied setup provenance")
    if set(raw["receipts"]) != {"tissue_profiles", "init_core", "initializer_cache"} or any(
        not isinstance(v, str) or not v.strip() for v in raw["receipts"].values()
    ):
        raise ValueError("Declare supplied tissue, core and conditional initializer-cache seams")
    real(raw["channel_noise_level"], "channel_noise_level")
    perturbations.native_stream_from_manifest(raw["numpy_rng"])
    python_restore(raw["python_rng"])
    if set(raw["global_options"]) != set(GLOBAL_KEYS) or set(raw["scheduled_options"]) != set(
        TISSUE_KEYS
    ):
        raise ValueError("Require all global and targeted event setup options")
    for key, row in raw["global_options"].items():
        if type(row) is int and row == 0:
            continue
        if not isinstance(row, list) or len(row) != (3 if key == "NaKATP_block" else 4):
            raise ValueError("Require disabled zero or the exact source global option: " + key)
        for value in row:
            real(value, key)
    for key, row in raw["scheduled_options"].items():
        if type(row) is int and row == 0:
            continue
        expected = 5 if key == "ecmJ" else 6
        if not isinstance(row, list) or len(row) != expected:
            raise ValueError("Require a literal targeted setup row: " + key)
        for value in row[:3]:
            real(value, key)
        if key != "ecmJ":
            real(row[3], key)
            if row[5] not in ("None", "f_sweep", "periodic"):
                raise ValueError("Only constant or dormant source f_sweep setup is admitted")
        else:
            real(row[4], key)
    if set(raw["frequency_sweep"]) != {"f start", "f stop", "f slope"}:
        raise ValueError("Require original frequency-sweep setup fields")
    for key, value in raw["frequency_sweep"].items():
        if value is not None or key != "f slope":
            real(value, key)
    if (
        set(raw["dynamic_noise"]) != {"enabled", "level"}
        or type(raw["dynamic_noise"]["enabled"]) is not bool
    ):
        raise ValueError("Require explicit dormant dynamic-noise configuration")
    real(raw["dynamic_noise"]["level"], "dormant dynamic noise")
    cb = base.material_binding.geometry_binding.current_binding
    g = base.material_binding.geometry_binding.geometry
    if set(raw["maps"]) != {"tissue_target_inds", "cell_target_inds", "env_target_inds"}:
        raise ValueError("Require explicit target maps, without profile selection")
    for key, size in (
        ("tissue_target_inds", len(cb.membrane_ids)),
        ("cell_target_inds", len(cb.cell_ids)),
        ("env_target_inds", len(g.grid_points_m)),
    ):
        for name, values in raw["maps"][key].items():
            if (
                not isinstance(name, str)
                or not name
                or not isinstance(values, list)
                or any(type(v) is not int or not 0 <= v < size for v in values)
            ):
                raise ValueError("Invalid supplied target ownership: " + key)
    for key, row in raw["scheduled_options"].items():
        if row == 0:
            continue
        profiles = row[3 if key == "ecmJ" else 4]
        table = raw["maps"][
            "env_target_inds"
            if key == "ecmJ"
            else "cell_target_inds"
            if key == "pressure"
            else "tissue_target_inds"
        ]
        if not isinstance(profiles, list) or any(name not in table for name in profiles):
            raise ValueError("Unknown explicitly supplied event target profile")
    if not np.array_equal(base.inputs["initial"]["voltage_V"], np.zeros(len(cb.membrane_ids))):
        raise ValueError("This fresh INIT entry requires the source init_core zero voltage")
