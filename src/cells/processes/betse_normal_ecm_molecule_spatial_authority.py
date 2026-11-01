"""Actual x/y factory/geometry/callback authority, not supplied scalar promotion.

The constant time callback is reconstructed after loading; no live Python
callable is serialized. Full source scalar arrays retain their native count
selected cell/membrane axis and target occurrence order. Radial stays closed.
"""

import ast
import builtins
import copy
import hashlib
import sys
from collections.abc import Mapping
from pathlib import Path
from types import CodeType, FunctionType

import numpy as np

from cells.processes import betse_normal_ecm_init_phase_setup as common
from cells.processes import betse_normal_ecm_molecule_lifecycle_source as lifecycle_source
from cells.processes import betse_normal_ecm_molecule_periodic_authority as periodic
from cells.processes import betse_normal_ecm_molecule_spatial_config as config
from cells.processes import betse_normal_ecm_molecule_spatial_source as source
from cells.processes import betse_normal_ecm_molecule_sweep_authority as sweep
from cells.processes import betse_normal_ion_join as ions

require, same = config.require, config.same
MEMBRANE_KEYS = sweep.MEMBRANE_KEYS
FACTORIES = {name: getattr(source, name) for name in config.FAMILIES}
FACTORY_CODES = {name: value.__code__ for name, value in FACTORIES.items()}
FACTORY_AST = {
    "gradient_x": "85a5e81f1913295fb105b0663448ee7efb312d490c3f9f248a4d8e9685e8d737",
    "gradient_y": "78997b0e08f2e2bbdaac8cc0f53200682aa21c6efc0f0f492f13ba56b09d91e3",
    "gradient_r": "59aa65fa455f27683fcf0063d0c732a569da1d6fb90c07fbd9214922256c4e54",
}
LEN, GETATTR = len, getattr
FINALIZER = lifecycle_source._finalize_events_tissue
FINALIZER_CODE = FINALIZER.__code__
NUMPY_BINDINGS = (("sqrt", np.sqrt), ("zeros", np.zeros))
KIND = "cells.actual_finalized_SIM_spatial_callback@1"
ROUTE = "selected_spatial_finalizers"
real, perturbations = common.real, common.perturbations
GLOBAL_KEYS, TISSUE_KEYS = common.GLOBAL_KEYS, common.TISSUE_KEYS


def python_restore(saved):
    return common.python_restore(saved)


def selected(options):
    return [
        (key, suffix, row[5])
        for key, suffix in MEMBRANE_KEYS.items()
        if isinstance(row := options.get(key), (tuple, list))
        and len(row) == 6
        and row[5] in config.FAMILIES
    ]


def callback_code(family):
    require(family in FACTORY_CODES, "Unknown spatial source callback")
    codes = [value for value in FACTORY_CODES[family].co_consts if type(value) is CodeType]
    require(
        len(codes) == 1
        and codes[0].co_name == "<lambda>"
        and codes[0].co_argcount == 1
        and codes[0].co_varnames == ("t",)
        and codes[0].co_freevars == ()
        and codes[0].co_consts == (None, 1),
        "Changed source spatial constant dynamics",
    )
    return codes[0]


def source_identity():
    require(
        lifecycle_source._finalize_events_tissue is FINALIZER
        and FINALIZER.__code__ is FINALIZER_CODE
        and FINALIZER.__globals__ is vars(lifecycle_source)
        and source.np is np
        and all(getattr(np, name) is value for name, value in NUMPY_BINDINGS),
        "Changed spatial factory/finalizer globals or NumPy callable binding",
    )
    require(
        "len" not in vars(source)
        and builtins.len is LEN
        and "getattr" not in vars(lifecycle_source)
        and builtins.getattr is GETATTR,
        "Changed resolved spatial factory/finalizer builtin globals",
    )
    nodes = {
        node.name: node
        for node in ast.parse(Path(source.__file__).read_bytes()).body
        if isinstance(node, ast.FunctionDef)
    }
    for name, factory in FACTORIES.items():
        require(
            getattr(source, name) is factory
            and getattr(lifecycle_source.mod, name) is factory
            and factory.__code__ is FACTORY_CODES[name]
            and factory.__globals__ is vars(source)
            and factory.__defaults__ is None
            and factory.__kwdefaults__ is None
            and factory.__closure__ is None,
            "Foreign spatial factory/code/namespace: " + name,
        )
        require(
            hashlib.sha256(ast.dump(nodes[name], include_attributes=False).encode()).hexdigest()
            == FACTORY_AST[name],
            "Pinned spatial factory AST changed: " + name,
        )
        callback_code(name)
    return dict(
        source_module=source.__name__,
        source_sha256=hashlib.sha256(Path(source.__file__).read_bytes()).hexdigest(),
        finalizer_sha256=hashlib.sha256(Path(lifecycle_source.__file__).read_bytes()).hexdigest(),
        native_modulate_sha256="c29f4ae27930f00780736e075183e61f44263dd0caa9d7c2f9a30971f616bff7",
        factories={
            name: dict(line=code.co_firstlineno, bytecode=hashlib.sha256(code.co_code).hexdigest())
            for name, code in FACTORY_CODES.items()
        },
        callable_instance_persisted=False,
    )


def scalar_axis(targets, geometry):
    count = len(targets)
    if count == len(geometry["membrane_ids"]):
        return "membranes", count
    if count == len(geometry["cell_ids"]):
        return "cells", count
    return "native_unbound_axis", None


def inspect_callback(callback, scalar, family, targets, geometry):
    require(family in ("gradient_x", "gradient_y"), config.MISSING_CENTRE)
    require(
        type(callback) is FunctionType
        and callback.__code__ is callback_code(family)
        and callback.__globals__ is vars(source)
        and callback.__closure__ is None
        and callback.__defaults__ is None
        and callback.__kwdefaults__ is None,
        "Require actual spatial factory callback code/globals/constant authority",
    )
    axis, count = scalar_axis(targets, geometry)
    require(
        count is not None
        and type(scalar) is np.ndarray
        and scalar.dtype == np.dtype("float64")
        and scalar.shape == (count,)
        and np.isfinite(scalar).all(),
        "Preserve actual spatial full source scalar axis/dtype/values without repair",
    )
    return axis


def record(binding, store, *, suffix, sequence, family, targets, profiles, scalar, runtime):
    value = dict(
        kind=KIND,
        source=source_identity(),
        suffix=suffix,
        sequence=sequence,
        source_function=family,
        source_scalar=scalar.copy(),
        source_axis=scalar_axis(targets, store["geometry"])[0],
        targets=list(targets),
        profiles=list(profiles),
        source_binding_identity=binding.identity,
        configuration_identity=ions.digest(store["configuration"]),
        geometry_identity=ions.digest(store["geometry"]),
        properties=config.properties(store["initial"][family + "_properties"]),
        runtime=runtime,
        source_phase="SIM",
        legacy_run_sim=True,
        factory_return_observed=True,
        evaluated=False,
        callable_instance_persisted=False,
        configuration_authority=config.AUTHORITY,
    )
    return dict(value, identity=ions.digest(value))


class FactoryObservation(sweep.FactoryObservation):
    """Chain the current profiler and retain actual entry/return/unwind identity."""

    def __init__(self, owner, phase, *, issuance):
        require(type(issuance) is config.Issuance, "Missing actual spatial parameter issuance")
        self.owner, self.phase, self.p, self.issuance = owner, phase, phase.p, issuance
        self.binding = issuance.binding
        self.options = self.p.scheduled_options
        self.selected = selected(self.options)
        require(
            self.selected and all(row[2] != "gradient_r" for row in self.selected),
            config.MISSING_CENTRE,
        )
        self.entries, self.records, self.returned, self.scalars = [], {}, {}, {}
        self.entry_attempts = self.return_events = 0
        self.return_or_unwind_events = []
        self.pending = None
        self.complete = False
        self.previous = self.installed = None
        self.check_context()

    def check_context(self):
        self.issuance.check(self.phase)
        require(
            self.p.scheduled_options is self.options
            and same(
                self.options,
                self.binding.inputs["source_setup"][config.TABLE_KEY]["scheduled_options"],
            ),
            "Changed original spatial options owner/configuration/order",
        )

    def __enter__(self):
        source_identity()
        self.previous = sys.getprofile()
        self.installed = self.profile
        sys.setprofile(self.installed)
        return self

    def observe(self, frame, event, arg):
        if frame.f_code not in FACTORY_CODES.values() or event not in ("call", "return"):
            return
        self.complete = False
        if event == "call":
            self.entry_attempts += 1
        else:
            self.return_events += 1
            if arg is None:
                matched = self.pending is not None and self.pending[0] == id(frame)
                self.return_or_unwind_events.append(
                    dict(matched_entry=matched, return_value_is_None=True)
                )
                if matched:
                    self.pending[3]["status"] = "return_or_unwind_incomplete"
                return
        self.check_context()
        if event == "call":
            require(
                self.pending is None and len(self.entries) < len(self.selected),
                "Duplicate/unowned spatial factory entry",
            )
            key, suffix, family = self.selected[len(self.entries)]
            targets = getattr(self.owner, "targets_" + suffix)
            entry = dict(
                sequence=len(self.entries),
                suffix=suffix,
                family=family,
                targets=list(targets),
                status="entered",
            )
            self.entries.append(entry)
            caller = frame.f_back
            require(
                frame.f_code is FACTORY_CODES[family]
                and frame.f_globals is vars(source)
                and frame.f_locals["p"] is self.p
                and frame.f_locals["cells"] is self.phase.cells
                and frame.f_locals["pc"] is targets
                and caller is not None
                and caller.f_code is FINALIZER_CODE
                and caller.f_globals is vars(lifecycle_source)
                and caller.f_locals["self"] is self.owner
                and caller.f_locals["phase"] is self.phase,
                "Foreign actual spatial factory/finalizer/parameter/geometry/target association",
            )
            expected = [
                i
                for profile in self.options[key][4]
                for i in self.binding.inputs["source_setup"][config.TABLE_KEY]["maps"][
                    "tissue_target_inds"
                ][profile]
            ]
            require(same(targets, expected), "Spatial target/profile occurrence order changed")
            self.pending = (id(frame), key, suffix, entry)
            return
        require(
            self.pending is not None and self.pending[0] == id(frame),
            "Missing source spatial factory entry",
        )
        _, key, suffix, entry = self.pending
        require(
            type(arg) is tuple and len(arg) == 2, "Spatial factory must return full scalar/callback"
        )
        scalar, callback = arg
        inspect_callback(
            callback, scalar, entry["family"], entry["targets"], self.issuance.geometry
        )
        partial = dict(
            configuration=self.issuance.config,
            geometry=self.issuance.geometry,
            initial=self.issuance.initial,
        )
        self.records[suffix] = record(
            self.binding,
            partial,
            suffix=suffix,
            sequence=entry["sequence"],
            family=entry["family"],
            targets=entry["targets"],
            profiles=self.options[key][4],
            scalar=scalar,
            runtime=dict(
                parameter=id(self.p),
                cells=id(self.phase.cells),
                target_list=id(frame.f_locals["pc"]),
                scalar=id(scalar),
                callback=id(callback),
            ),
        )
        self.returned[suffix], self.scalars[suffix] = callback, scalar
        entry["status"] = "returned"
        self.pending = None

    def finish(self):
        self.complete = False
        require(
            self.pending is None
            and not self.return_or_unwind_events
            and len(self.records) == len(self.selected),
            "Missing/omitted spatial factory return",
        )
        self.check_context()
        for _key, suffix, family in self.selected:
            require(
                getattr(self.owner, "dyna_" + suffix, None) is self.returned[suffix]
                and getattr(self.owner, "scalar_" + suffix, None) is self.scalars[suffix],
                "Finalizer replaced actual spatial scalar/callback objects",
            )
            inspect_callback(
                self.returned[suffix],
                self.scalars[suffix],
                family,
                getattr(self.owner, "targets_" + suffix),
                self.issuance.geometry,
            )
        self.complete = True

    def __exit__(self, kind, error, tb):
        intact = sys.getprofile() is self.installed
        sys.setprofile(self.previous)
        if error is not None:
            if not intact:
                error.add_note(
                    "Spatial factory profiler lost; incomplete observation; prior profiler restored"
                )
            return False
        require(intact, "Spatial factory work profiler was replaced")
        self.finish()

    def data(self):
        scalars = {
            suffix: getattr(self.owner, "scalar_" + suffix, None) for _, suffix, _ in self.selected
        }
        return dict(
            super().data(),
            kind="cells.source_spatial_factory_observation@1",
            available_handler_scalars=copy.deepcopy(scalars),
            available_parameter_geometry_stores=self.issuance.available(),
            failed_prefix_is_owner_admission=False,
        )


def validate(binding, owner, published, fields):
    store = config.validate_receipt(binding, fields)
    require(store is not None, "Spatial callbacks require actual selected source stores")
    active = selected(owner["scheduled_options"])
    authority = fields.get("spatial_callback_authority")
    require(
        active and isinstance(authority, Mapping) and set(authority) == {s for _, s, _ in active},
        "Missing/foreign actual spatial scalar/callback authority",
    )
    require(
        fields["source_phase"] == "SIM"
        and fields["legacy_run_sim"] is True
        and type(fields["event_fire_calls"]) is int
        and fields["event_fire_calls"] == 0,
        "Changed spatial finalization phase/epoch",
    )
    for sequence, (key, suffix, family) in enumerate(active):
        require(family in ("gradient_x", "gradient_y"), config.MISSING_CENTRE)
        saved = authority[suffix]
        require(
            saved["identity"] == ions.digest({k: v for k, v in saved.items() if k != "identity"}),
            "Changed spatial source callback record digest",
        )
        targets = published.owner["handler_fields"]["targets_" + suffix]
        scalar = saved["source_scalar"]
        axis, count = scalar_axis(targets, store["geometry"])
        require(
            type(scalar) is np.ndarray
            and scalar.dtype == np.dtype("float64")
            and scalar.shape == (count,)
            and np.isfinite(scalar).all(),
            "Foreign source spatial scalar category/dtype/full axis",
        )
        runtime = saved["runtime"]
        require(
            set(runtime) == {"parameter", "cells", "target_list", "scalar", "callback"}
            and all(type(v) is int and v > 0 for v in runtime.values())
            and len(set(runtime.values())) == 5
            and runtime["parameter"] == store["runtime"]["parameter"]
            and runtime["cells"] == store["runtime"]["cells"],
            "Foreign actual spatial runtime association",
        )
        expected = record(
            binding,
            store,
            suffix=suffix,
            sequence=sequence,
            family=family,
            targets=targets,
            profiles=owner["scheduled_options"][key][4],
            scalar=scalar,
            runtime=runtime,
        )
        require(
            same(saved, expected) and saved["source_axis"] == axis,
            "Foreign actual source spatial factory/config/geometry/target/epoch",
        )
        callback = owner["callbacks"][suffix]
        actual = np.asarray(callback["source_scalar"])
        require(
            callback["source_function"] == family
            and callback["dynamic"] == dict(kind="constant")
            and actual.dtype == scalar.dtype
            and actual.shape == scalar.shape
            and np.array_equal(actual, scalar),
            "Changed actual spatial callback scalar/dynamics",
        )


def validator_correspondence():
    """Compare the entire pinned shared validator, allowing only whitelist delta."""
    periodic.common_guard_identity()
    original = next(
        n
        for n in ast.parse(Path(common.__file__).read_bytes()).body
        if isinstance(n, ast.FunctionDef) and n.name == "validate"
    )
    owned = copy.deepcopy(
        next(
            n
            for n in ast.parse(Path(__file__).read_bytes()).body
            if isinstance(n, ast.FunctionDef) and n.name == "_validate_SIM_spatial_setup"
        )
    )
    owned.name = "validate"
    branches = [
        n for n in ast.walk(owned) if isinstance(n, ast.Compare) and ast.unparse(n.left) == "row[5]"
    ]
    require(
        len(branches) == 1
        and ast.literal_eval(branches[0].comparators[0]) == ("None", "gradient_x", "gradient_y"),
        "Changed declared spatial callback whitelist",
    )
    branches[0].comparators[0] = ast.Tuple(
        elts=[ast.Constant("None"), ast.Constant("f_sweep")], ctx=ast.Load()
    )
    require(
        ast.dump(original, include_attributes=False) == ast.dump(owned, include_attributes=False),
        "Spatial setup differs beyond the explicit callback whitelist; upstream review required",
    )
    return dict(complete_validator_AST_equal=True, only_whitelist_delta=True)


def validate_SIM_setup(raw, base, *, phase, run_sim, preparation_route):
    require(
        phase == "SIM" and run_sim is True and preparation_route == ROUTE,
        "Spatial source setup is explicit SIM-only; original INIT guards unchanged",
    )
    active = selected(raw["scheduled_options"])
    require(
        active and all(family != "gradient_r" for _, _, family in active), config.MISSING_CENTRE
    )
    require(
        all(
            row == 0
            or (
                key in MEMBRANE_KEYS
                and len(row) == 6
                and row[5] in ("None", "gradient_x", "gradient_y")
            )
            for key, row in raw["scheduled_options"].items()
        ),
        "Spatial source setup keeps temporal/pressure/ecmJ/cutting families closed",
    )
    validator_correspondence()
    return _validate_SIM_spatial_setup(raw, base)


# Exact common schema/RNG/maps/noise checks; only the declared whitelist differs.
def _validate_SIM_spatial_setup(raw, base):
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
        (not isinstance(v, str) or not v.strip() for v in raw["receipts"].values())
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
            if row[5] not in ("None", "gradient_x", "gradient_y"):
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
                or (not isinstance(values, list))
                or any((type(v) is not int or not 0 <= v < size for v in values))
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
        if not isinstance(profiles, list) or any((name not in table for name in profiles)):
            raise ValueError("Unknown explicitly supplied event target profile")
    if not np.array_equal(base.inputs["initial"]["voltage_V"], np.zeros(len(cb.membrane_ids))):
        raise ValueError("This fresh INIT entry requires the source init_core zero voltage")
