"""Selected spatial stores on the actual early parameter/context owner.

Raw normalized configuration is conditional input, not Parameters/YAML/native
geometry authority. Only the existing real completed-INIT transition issues p
and its three stores before finalizers. Closed receipts never issue a live p.
Radial finalization remains closed: the phase has no retained native centre.
"""

import ast
import builtins
import hashlib
import math
from collections.abc import Mapping
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from cells.processes import betse_normal_ecm_molecule_spatial_config_source as source
from cells.processes import betse_normal_ecm_molecule_temporal_config as temporal
from cells.processes import betse_normal_ion_join as ions

context, require, same = temporal.context, temporal.require, temporal.same
FAMILIES = ("gradient_x", "gradient_y", "gradient_r")
MEMBRANE_KEYS = ("Na_mem", "K_mem", "Cl_mem", "Ca_mem")
STORE_NAMES = tuple(name + "_properties" for name in FAMILIES)
MODE = "selected_native_spatial_stores"
KIND = "cells.normalized_spatial_configuration_projection@1"
RECEIPT_KIND = "cells.actual_selected_spatial_configuration_stores@1"
CONFIG_KEY, TABLE_KEY = "spatial_configuration", "spatial_event_configuration"
KEYS = {CONFIG_KEY, TABLE_KEY}
AUTHORITY = (
    "selected native x/y/r dictionary/float/get-default assignments on one issued p/_conf; "
    "normalized spatial projection only, not full Parameters/YAML/parser or native geometry"
)
MISSING_CENTRE = (
    "Radial finalization requires retained native cells.centre authority; "
    "no mean/grid/probe inference"
)
POPULATE, FLOAT = source.populate, builtins.float
POPULATE_CODE = POPULATE.__code__
POPULATE_AST = "505da6d2360293d2cc419358df2c72d3f0d5dc961cf0cf534b6904b50dab9d54"


def check_configuration(value):
    require(
        isinstance(value, Mapping)
        and set(value) == {"kind", "mode", "families", "projection", "provenance"}
        and value["kind"] == KIND
        and value["mode"] == MODE
        and isinstance(value["families"], (tuple, list))
        and value["families"]
        and tuple(value["families"]) == tuple(k for k in FAMILIES if k in value["families"])
        and type(value["provenance"]) is str
        and bool(value["provenance"].strip()),
        "Require explicit normalized spatial configuration/families/provenance",
    )
    projection = value["projection"]
    temporal._closed(projection)
    require(
        isinstance(projection, Mapping) and set(projection) <= {"modulator function properties"},
        "Spatial configuration is a normalized projection, never full Parameters/YAML",
    )
    section = projection.get("modulator function properties")
    if isinstance(section, Mapping):
        require(set(section) <= set(FAMILIES), "Unowned non-spatial configuration")
        for row in section.values():
            if isinstance(row, Mapping):
                require(
                    set(row) <= {"slope", "x-offset", "z-offset", "exponent"},
                    "Foreign native spatial property",
                )
    # Missing keys, None and malformed float strings remain raw. Native lookup
    # order/defaults own their errors and partial stores; no hydration here.
    return value


def selection(raw):
    cfg = raw["source_setup"]
    if not KEYS.intersection(cfg):
        return None
    require(
        KEYS <= set(cfg)
        and not temporal.KEYS.intersection(cfg)
        and not any(key.startswith("periodic_") for key in cfg),
        "Spatial route cannot rebase/coexist with another selected source route",
    )
    value = check_configuration(cfg[CONFIG_KEY])
    phase = raw["sim_phase"]
    require(
        phase["time_profile"]["phase"] == "SIM" and phase["flags"]["_run_sim"] is True,
        "Spatial finalizers require actual SIM/_run_sim; INIT admission is unchanged",
    )
    material, table = phase["setup"], cfg[TABLE_KEY]
    require(
        all(
            row == 0
            for name in ("global_options", "scheduled_options")
            for row in material[name].values()
        ),
        "Spatial source table cannot replace the no-intervention material seam",
    )
    require(
        isinstance(table, Mapping)
        and set(table) == set(material)
        and all(same(table[k], material[k]) for k in material if k != "scheduled_options"),
        "Spatial source/material schema, clocks, RNG or maps differ",
    )
    active = []
    for key, row in table["scheduled_options"].items():
        if row == 0:
            continue
        require(
            key in MEMBRANE_KEYS
            and isinstance(row, (tuple, list))
            and len(row) == 6
            and row[5] in ("None", *value["families"]),
            "Spatial route admits declared membrane x/y and constants only",
        )
        if row[5] != "None":
            active.append(row[5])
    require(
        active and set(active) == set(value["families"]),
        "Missing declared spatial finalizer family",
    )
    require("gradient_r" not in active, MISSING_CENTRE)
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
        "Changed spatial assignment code/globals/float/parameter namespace",
    )
    node = next(
        n
        for n in ast.parse(Path(source.__file__).read_bytes()).body
        if isinstance(n, ast.FunctionDef) and n.name == "populate"
    )
    require(
        hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest()
        == POPULATE_AST,
        "Selected spatial assignment AST drift",
    )
    context.check_original()
    return dict(
        native_parameters_sha256=temporal.NATIVE_SHA,
        native_lines=(948, 970),
        source_sha256=hashlib.sha256(Path(source.__file__).read_bytes()).hexdigest(),
        selected_assignment_AST=POPULATE_AST,
        context_runtime_bindings=context.binding_record(),
        normalized_projection=True,
        full_Parameters_YAML_authority=False,
    )


def properties(value):
    require(
        isinstance(value, Mapping)
        and set(value) == {"slope", "x-offset", "z-offset", "exponent"}
        and all(type(v) is float and math.isfinite(v) for v in value.values()),
        "Require actual finite native float/default spatial properties",
    )
    return ions.data(value)


def geometry_record(completed):
    """Reference the actual typed completed INIT geometry, never a probe/cache."""
    from cells.processes import betse_normal_ecm_molecule_lifecycle as lifecycle
    from cells.processes import betse_normal_ecm_molecule_lifecycle_phase as phase

    require(
        type(completed) is lifecycle.CompleteInit and type(completed.binding) is phase.Binding,
        "Require retained typed complete INIT geometry authority",
    )
    gb = completed.binding.material_binding.geometry_binding
    cg = gb.current_binding
    return dict(
        geometry_binding_identity=gb.identity,
        source_INIT_binding_identity=completed.binding.identity,
        source_INIT_parent_identity=completed.parent.identity,
        source_complete_INIT_identity=completed.identity,
        cell_ids=tuple(cg.cell_ids),
        membrane_ids=tuple(cg.membrane_ids),
        cell_centres_m=gb.definition["geometry"]["cell_centres_m"],
        membrane_midpoints_m=gb.definition["geometry"]["membrane_midpoints_m"],
        radial_centre_authority="absent; radial finalization remains refused",
    )


class Issuance:
    """Live, one-attempt constructor used only by the retained-owner transition."""

    def __init__(self, binding, completed):
        from cells.processes import betse_normal_ecm_molecule_event_owner as bridge
        from cells.processes import betse_normal_ecm_molecule_lifecycle as lifecycle

        require(
            type(binding) is lifecycle.Binding, "Require retained typed source lifecycle binding"
        )
        self.geometry = geometry_record(completed)
        bridge.check_inputs(binding.event_owner_inputs, expected_INIT=completed.binding.identity)
        require(
            binding.expected_init_identity == completed.binding.identity
            and binding.event_owner_inputs.source_geometry_binding_identity
            == self.geometry["geometry_binding_identity"],
            "Foreign spatial actual INIT/input geometry authority",
        )
        self.config = selection(binding.inputs)
        require(self.config is not None, "No supplied-state promotion into spatial issuance")
        self.binding, self.completed = binding, completed
        self.p = self.conf = self.phase = self.cells = None
        self.stores, self.initial = {}, None
        self.geometry_arrays = {}
        self.attempts, self.stage = 0, "declared_projection_only"

    def __reduce__(self):
        raise TypeError("Live spatial issuance cannot be decoded/serialized as native authority")

    def construct(self, **fields):
        require(
            self.attempts == 0 and self.p is None, "Spatial parameter issuance is single-attempt"
        )
        self.attempts += 1
        self.stage = "selected_spatial_dictionary_and_float_default_assignments"
        source_identity()
        require(
            not {"_conf", *STORE_NAMES}.intersection(fields),
            "No late spatial property patch or supplied store owner",
        )
        self.conf = ions.data(self.config["projection"])
        self.p = SimpleNamespace(_conf=self.conf, **fields)
        source.populate(self.p)
        self.stores = {name: getattr(self.p, name) for name in STORE_NAMES}
        self.initial = {name: properties(value) for name, value in self.stores.items()}
        self.stage = "constructed_before_actual_phase_and_finalizers"
        return self.p

    def attach(self, ctx, component):
        from cells.processes import betse_normal_ecm_calcium_join as calcium

        require(
            type(component) is calcium.Binding
            and component.material_binding.geometry_binding.identity
            == self.geometry["geometry_binding_identity"]
            and self.phase is None
            and ctx.p is self.p
            and ctx.phase.p is self.p
            and ctx.phase.sim is ctx.sim
            and ctx.phase.cells is ctx.cells,
            "Require actual context/issued p/typed retained geometry association",
        )
        self.phase, self.cells = ctx.phase, ctx.cells
        for name in ("cell_i", "mem_i", "cell_centres", "mem_mids_flat"):
            self.geometry_arrays[name] = getattr(ctx.cells, name)
        self.check(ctx.phase, require_SIM=False)

    def check(self, phase, *, require_SIM=True):
        require(
            self.initial is not None
            and self.phase is phase
            and phase.cells is self.cells
            and phase.p is self.p
            and self.p._conf is self.conf
            and same(self.conf, self.config["projection"]),
            "Changed spatial live parameter/config/phase owner",
        )
        if require_SIM:
            require(
                phase.kind == "SIM" and self.p._run_sim is True,
                "Spatial factory requires actual SIM epoch",
            )
        for name, value in self.stores.items():
            require(
                getattr(self.p, name) is value and same(properties(value), self.initial[name]),
                "Changed issued spatial dictionary owner/value",
            )
        for name, expected in self.geometry_arrays.items():
            require(
                getattr(self.cells, name) is expected,
                "Replaced retained spatial geometry array: " + name,
            )
        for name, data in (
            ("cell_centres", self.geometry["cell_centres_m"]),
            ("mem_mids_flat", self.geometry["membrane_midpoints_m"]),
        ):
            value = getattr(self.cells, name)
            expected = np.asarray(data, dtype=np.float64)
            require(
                type(value) is np.ndarray
                and value.dtype == np.dtype("float64")
                and value.shape == expected.shape
                and np.array_equal(value, expected),
                "Changed actual retained source geometry values/axes: " + name,
            )
        for name, owners in (
            ("cell_i", self.geometry["cell_ids"]),
            ("mem_i", self.geometry["membrane_ids"]),
        ):
            value = getattr(self.cells, name)
            require(
                type(value) is np.ndarray
                and value.dtype == np.dtype("int64")
                and value.shape == (len(owners),)
                and np.array_equal(value, np.arange(len(owners))),
                "Changed actual complete source cell/membrane axes",
            )
        require(selection(self.binding.inputs) is not None, "Changed original spatial declaration")

    def association(self):
        self.check(self.phase)
        return dict(
            source_binding_identity=self.binding.identity,
            configuration_identity=ions.digest(self.config),
            geometry_identity=ions.digest(self.geometry),
            authority=AUTHORITY,
        )

    def receipt(self, observation):
        from cells.processes import betse_normal_ecm_molecule_spatial_authority as spatial

        require(
            type(observation) is spatial.FactoryObservation
            and observation.issuance is self
            and observation.complete
            and observation.pending is None
            and observation.entry_attempts == observation.return_events == len(observation.selected)
            and not observation.return_or_unwind_events,
            "Spatial receipt requires complete actual observed source finalizers",
        )
        self.check(self.phase)
        value = dict(
            kind=RECEIPT_KIND,
            authority=AUTHORITY,
            source=source_identity(),
            configuration=ions.data(self.config),
            source_binding_identity=self.binding.identity,
            source_SIM_declaration_identity=self.binding.declaration.identity,
            geometry=ions.freeze(self.geometry),
            initial=ions.data(self.initial),
            after={k: ions.data(v) for k, v in self.stores.items()},
            runtime=dict(
                parameter=id(self.p),
                configuration=id(self.conf),
                cells=id(self.cells),
                stores={k: id(v) for k, v in self.stores.items()},
                geometry_arrays={k: id(v) for k, v in self.geometry_arrays.items()},
            ),
            parameter_constructions=self.attempts,
            selected_dictionary_creations=3,
            selected_float_lookups=12,
            native_optional_get_defaults=9,
            factory_returns=len(observation.records),
            stage="after_actual_spatial_finalizers_before_event_finalized",
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
            geometry=self.geometry,
            partial_stores=None
            if self.p is None
            else {key: getattr(self.p, key) for key in STORE_NAMES if hasattr(self.p, key)},
            live_owner_admission=False,
        )


def validate_receipt(binding, fields, *, completed=None):
    """Closed correspondence only; never run constructors, factories or callbacks."""
    configured = selection(binding.inputs)
    saved = fields.get("spatial_configuration_store")
    if configured is None:
        require(saved is None, "Unselected route cannot promote a spatial receipt")
        return None
    require(isinstance(saved, Mapping), "Missing actual spatial store/finalizer receipt")
    require(
        saved["identity"] == ions.digest({k: v for k, v in saved.items() if k != "identity"}),
        "Changed spatial store receipt digest",
    )
    require(
        saved["kind"] == RECEIPT_KIND
        and saved["authority"] == AUTHORITY
        and same(saved["source"], source_identity())
        and same(saved["configuration"], configured)
        and saved["source_binding_identity"] == binding.identity
        and saved["source_SIM_declaration_identity"] == binding.declaration.identity,
        "Foreign spatial source/configuration/SIM parent",
    )
    geom = saved["geometry"]
    require(
        geom["source_INIT_binding_identity"] == binding.expected_init_identity
        and geom["geometry_binding_identity"]
        == binding.event_owner_inputs.source_geometry_binding_identity,
        "Foreign retained spatial INIT/geometry authority",
    )
    original = binding.inputs["sim_phase"]["field"]["definition"]["environment_geometry_definition"]
    require(
        same(geom["cell_centres_m"], original["geometry"]["cell_centres_m"])
        and same(geom["membrane_midpoints_m"], original["geometry"]["membrane_midpoints_m"])
        and same(geom["cell_ids"], original["current_definition"]["geometry"]["cell_ids"])
        and same(geom["membrane_ids"], original["current_definition"]["geometry"]["membrane_ids"])
        and geom["radial_centre_authority"] == "absent; radial finalization remains refused",
        "Changed original retained source geometry/axes",
    )
    if completed is not None:
        require(
            same(geom, geometry_record(completed)), "Foreign actual complete INIT geometry ancestry"
        )
    require(
        saved["stage"] == "after_actual_spatial_finalizers_before_event_finalized"
        and saved["replayed"] is False
        and saved["callable_instance_persisted"] is False
        and type(saved["independent_cases"]) is int
        and saved["independent_cases"] == 0,
        "Foreign spatial epoch/replay/callable scope",
    )
    for key, expected in (
        ("parameter_constructions", 1),
        ("selected_dictionary_creations", 3),
        ("selected_float_lookups", 12),
        ("native_optional_get_defaults", 9),
    ):
        require(
            type(saved[key]) is int and saved[key] == expected, "Changed spatial native work count"
        )
    require(
        type(saved["factory_returns"]) is int
        and saved["factory_returns"]
        == sum(
            row != 0 and row[5] in FAMILIES
            for row in binding.inputs["source_setup"][TABLE_KEY]["scheduled_options"].values()
        ),
        "Missing actual spatial finalizer returns",
    )
    require(
        set(saved["initial"]) == set(saved["after"]) == set(STORE_NAMES),
        "Incomplete original spatial stores",
    )
    for key in STORE_NAMES:
        properties(saved["initial"][key])
        properties(saved["after"][key])
        require(
            same(saved["initial"][key], saved["after"][key]),
            "Spatial factory changed native properties",
        )
    runtime = saved["runtime"]
    require(
        set(runtime) == {"parameter", "configuration", "cells", "stores", "geometry_arrays"}
        and set(runtime["stores"]) == set(STORE_NAMES)
        and set(runtime["geometry_arrays"]) == {"cell_i", "mem_i", "cell_centres", "mem_mids_flat"},
        "Incomplete spatial runtime owner observations",
    )
    ids = [runtime[k] for k in ("parameter", "configuration", "cells")]
    ids += list(runtime["stores"].values()) + list(runtime["geometry_arrays"].values())
    require(
        all(type(v) is int and v > 0 for v in ids) and len(set(ids)) == len(ids),
        "Foreign spatial runtime store/axis owners",
    )
    return saved
