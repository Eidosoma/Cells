"""Blocked spatial store/owner controls; synthetic graphs grant no admission."""

import ast
import copy
import hashlib
import json
import sys
from dataclasses import replace
from pathlib import Path
from types import FunctionType, SimpleNamespace

import numpy as np
import pytest

from cells.processes import betse_normal_ecm_molecule_checkpoint as checkpoint
from cells.processes import betse_normal_ecm_molecule_event_owner as bridge
from cells.processes import betse_normal_ecm_molecule_lifecycle as lifecycle
from cells.processes import betse_normal_ecm_molecule_spatial_authority as authority
from cells.processes import betse_normal_ecm_molecule_spatial_config as config
from tests.unit.test_betse_normal_ecm_molecule_checkpoint_codec import packed
from tests.unit.test_betse_normal_ecm_molecule_event_checkpoint import (
    no_actual_execution as no_actual_execution,
)
from tests.unit.test_betse_normal_ecm_molecule_event_checkpoint import plain_record
from tests.unit.test_betse_normal_ecm_molecule_event_owner import graph
from tests.unit.test_betse_normal_ecm_molecule_periodic_checkpoint import (
    forbid_actual_periodic as forbid_actual_periodic,
)
from tests.unit.test_betse_normal_ecm_molecule_periodic_checkpoint import source_template
from tests.unit.test_betse_normal_ecm_molecule_temporal_config_checkpoint import (
    no_actual_selected_constructor as no_actual_selected_constructor,
)
from validation.betse import betse_normal_ecm_molecule_spatial_checkpoint as validation
from validation.betse.betse_normal_ecm_event_join_fixtures import finalize_fields

NATIVE = Path("/mnt/workspaces/Cells/betse-v1.5.0")
PROJECTION = {
    "modulator function properties": {
        "gradient_x": {"slope": "0.7", "x-offset": "0.13", "exponent": "2"},
        "gradient_y": {"slope": "-0.25", "z-offset": "0.2"},
        "gradient_r": {"slope": "1.2", "x-offset": "0.00000025"},
    }
}


@pytest.fixture(autouse=True)
def block_actual_spatial(no_actual_selected_constructor, tmp_path):
    codes = {
        config.Issuance.__init__.__code__,
        config.Issuance.construct.__code__,
        config.source.populate.__code__,
        *authority.FACTORY_CODES.values(),
    }
    codes.update(authority.callback_code(k) for k in config.FAMILIES)
    attempted = []
    previous = sys.getprofile()

    def blocked(frame, event, arg):
        if previous is not None:
            previous(frame, event, arg)
        if event == "call" and frame.f_code in codes:
            attempted.append(frame.f_code.co_name)
            raise AssertionError("Actual spatial constructor/factory/callback execution forbidden")

    sys.setprofile(blocked)
    try:
        yield attempted
    finally:
        sys.setprofile(previous)
        (tmp_path / "spatial-owner-control.json").write_text(
            json.dumps(
                dict(
                    actual_spatial_constructor_factory_callback_entries=attempted,
                    synthetic_graph_admission=False,
                    independent_cases=0,
                )
            )
        )
    assert attempted == []


def configuration(families=("gradient_x",)):
    return dict(
        kind=config.KIND,
        mode=config.MODE,
        families=families,
        projection=copy.deepcopy(PROJECTION),
        provenance="Synthetic normalized spatial projection; not native parser/owner",
    )


def synthetic_populate():
    node = copy.deepcopy(
        next(
            n
            for n in ast.parse(Path(config.source.__file__).read_bytes()).body
            if isinstance(n, ast.FunctionDef)
        )
    )
    node.name = "synthetic_spatial_assignments"
    namespace = {}
    exec(
        compile(
            ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])),
            "<synthetic-spatial-assignment-control>",
            "exec",
        ),
        namespace,
    )
    return namespace[node.name]


def manufactured(scenario="spatial_x_combined", families=("gradient_x",)):
    g = graph()
    base = source_template()
    base["sim_phase"]["setup"]["maps"] = {
        name: lifecycle.ions.data(g.early["owner"][name])
        for name in ("tissue_target_inds", "cell_target_inds", "env_target_inds")
    }
    configured = validation.configure_sim(base, scenario, configuration=configuration(families))
    raw = lifecycle.ions.data(g.source.inputs)
    # Complete only the existing synthetic metadata graph; never submit it to
    # complete_INIT, initialize, bind, transition, native source or checkpoint IO.
    for key in ("setup", "flags", "time_profile"):
        raw["sim_phase"][key] = copy.deepcopy(configured["sim_phase"][key])
    raw["source_setup"].update(
        {
            key: copy.deepcopy(configured["source_setup"][key])
            for key in (*config.KEYS, "provenance")
        }
    )
    external = raw["sim_phase"]["field"]["definition"]["environment_geometry_definition"]
    external["geometry"].update(
        cell_centres_m=[[-1e-6, 0.0], [2e-6, 3e-6]],
        membrane_midpoints_m=[[-2e-6, 0.0], [0.0, 1e-6], [1e-6, 2e-6], [3e-6, -1e-6]],
    )
    external["current_definition"]["geometry"].update(
        cell_ids=["cell-A", "cell-B"], membrane_ids=["m-A", "m-B", "m-C", "m-D"]
    )
    g.source = replace(g.source, inputs=lifecycle.ions.freeze(raw))
    g.source = replace(g.source, identity=lifecycle.ions.digest(lifecycle.binding_record(g.source)))
    gb = g.completed.binding.material_binding.geometry_binding
    # environment.Binding stores its declaration as JSON, not a mutable field.
    gb = replace(gb, definition_json=json.dumps(external))
    material = replace(g.completed.binding.material_binding, geometry_binding=gb)
    g.completed = replace(
        g.completed, binding=replace(g.completed.binding, material_binding=material)
    )
    table = config.finalizer_setup(raw)
    p = SimpleNamespace(
        _conf=copy.deepcopy(PROJECTION), scheduled_options=table["scheduled_options"], _run_sim=True
    )
    synthetic_populate()(p)
    cells = SimpleNamespace(
        cell_i=np.arange(2, dtype=np.int64),
        mem_i=np.arange(4, dtype=np.int64),
        cell_centres=np.asarray(external["geometry"]["cell_centres_m"], dtype=np.float64),
        mem_mids_flat=np.asarray(external["geometry"]["membrane_midpoints_m"], dtype=np.float64),
    )
    phase = SimpleNamespace(p=p, cells=cells, kind="SIM")
    issuer = object.__new__(config.Issuance)
    stores = {key: getattr(p, key) for key in config.STORE_NAMES}
    issuer.__dict__.update(
        binding=g.source,
        completed=g.completed,
        config=config.selection(raw),
        p=p,
        conf=p._conf,
        phase=phase,
        cells=cells,
        stores=stores,
        initial={key: copy.deepcopy(value) for key, value in stores.items()},
        geometry=config.geometry_record(g.completed),
        geometry_arrays={
            key: getattr(cells, key) for key in ("cell_i", "mem_i", "cell_centres", "mem_mids_flat")
        },
        attempts=1,
        stage="constructed_before_actual_phase_and_finalizers",
    )
    fields = finalize_fields(table["global_options"], table["scheduled_options"], table["maps"], 4)
    actual = SimpleNamespace(**fields)
    for name, value in table["maps"].items():
        setattr(actual, name, copy.deepcopy(value))
    for _, suffix, _ in authority.selected(table["scheduled_options"]):
        setattr(actual, "scalar_" + suffix, 1)
    g.raw, g.table, g.p, g.live_phase, g.issuer, g.actual = raw, table, p, phase, issuer, actual
    g.trace = authority.FactoryObservation(actual, phase, issuance=issuer)
    return g


def returns(g):
    for _key, suffix, family in g.trace.selected:
        frame = SimpleNamespace(
            f_code=authority.FACTORY_CODES[family],
            f_globals=vars(authority.source),
            f_locals=dict(
                p=g.p, cells=g.live_phase.cells, pc=getattr(g.actual, "targets_" + suffix)
            ),
            f_back=SimpleNamespace(
                f_code=authority.FINALIZER_CODE,
                f_globals=vars(authority.lifecycle_source),
                f_locals=dict(self=g.actual, phase=g.live_phase),
            ),
        )
        g.trace.observe(frame, "call", None)
        _, count = authority.scalar_axis(frame.f_locals["pc"], g.issuer.geometry)
        scalar = np.linspace(0.1, 0.7, count, dtype=np.float64)
        callback = FunctionType(authority.callback_code(family), vars(authority.source))
        g.trace.observe(frame, "return", (scalar, callback))
        setattr(g.actual, "scalar_" + suffix, scalar)
        setattr(g.actual, "dyna_" + suffix, callback)
    g.trace.finish()
    return g


def observation(g):
    store = g.issuer.receipt(g.trace)
    early = dict(
        spatial_configuration_store=store,
        spatial_callback_authority=g.trace.records,
        source_phase="SIM",
        legacy_run_sim=True,
        event_fire_calls=0,
    )
    return early


def test_selected_spatial_source_is_exact_original_15_statements_with_native_defaults(tmp_path):
    path = NATIVE / "betse/science/parameters.py"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == config.temporal.NATIVE_SHA
    names = tuple("self." + k for k in config.STORE_NAMES)
    original = sorted(
        [
            node
            for node in ast.walk(ast.parse(path.read_bytes()))
            if isinstance(node, ast.Assign)
            and any(
                ast.unparse(target) == name or ast.unparse(target).startswith(name + "[")
                for target in node.targets
                for name in names
            )
        ],
        key=lambda n: n.lineno,
    )
    adopted = next(
        n
        for n in ast.parse(Path(config.source.__file__).read_bytes()).body
        if isinstance(n, ast.FunctionDef)
    )
    assert len(original) == 15
    assert [ast.dump(n, include_attributes=False) for n in original] == [
        ast.dump(n, include_attributes=False) for n in adopted.body
    ]
    plan = config.source_identity()
    assert plan["normalized_projection"] is True and plan["full_Parameters_YAML_authority"] is False
    (tmp_path / "selected-spatial-source.json").write_text(json.dumps(plan))


def test_all_three_factory_ASTs_match_pinned_original_without_execution():
    path = NATIVE / "betse/science/math/modulate.py"
    assert (
        hashlib.sha256(path.read_bytes()).hexdigest()
        == authority.source_identity()["native_modulate_sha256"]
    )
    original = {
        n.name: n for n in ast.parse(path.read_bytes()).body if isinstance(n, ast.FunctionDef)
    }
    adopted = {
        n.name: n
        for n in ast.parse(Path(authority.source.__file__).read_bytes()).body
        if isinstance(n, ast.FunctionDef)
    }
    for family in config.FAMILIES:
        assert ast.dump(original[family], include_attributes=False) == ast.dump(
            adopted[family], include_attributes=False
        )


def test_common_setup_copy_allows_only_declared_whitelist_delta():
    assert authority.validator_correspondence() == dict(
        complete_validator_AST_equal=True, only_whitelist_delta=True
    )


def test_mixed_xy_configuration_uses_literal_ion_order_not_mapping_insertion():
    base = source_template()
    base["sim_phase"]["setup"]["scheduled_options"] = dict(
        reversed(list(base["sim_phase"]["setup"]["scheduled_options"].items()))
    )
    result = validation.configure_sim(
        base, "spatial_xy_combined", configuration=configuration(("gradient_x", "gradient_y"))
    )
    table = result["source_setup"][config.TABLE_KEY]["scheduled_options"]
    assert [table[key][5] for key in authority.MEMBRANE_KEYS] == [
        "gradient_x",
        "gradient_y",
        "gradient_x",
        "gradient_y",
    ]


def test_synthetic_assignment_control_retains_native_defaults_and_float_types():
    p = SimpleNamespace(_conf=copy.deepcopy(PROJECTION))
    synthetic_populate()(p)
    assert p.gradient_x_properties == dict(
        slope=0.7, **{"x-offset": 0.13, "z-offset": 0.0, "exponent": 2.0}
    )
    assert p.gradient_y_properties == dict(
        slope=-0.25, **{"x-offset": 0.0, "z-offset": 0.2, "exponent": 1.0}
    )
    assert p.gradient_r_properties == dict(
        slope=1.2, **{"x-offset": 0.25e-6, "z-offset": 0.0, "exponent": 1.0}
    )
    assert all(type(v) is float for k in config.STORE_NAMES for v in getattr(p, k).values())


@pytest.mark.parametrize("family", config.FAMILIES)
@pytest.mark.parametrize("bad", ["missing-slope", "bad-float", "none"])
def test_raw_failures_keep_partial_native_store_order_in_synthetic_copy(family, bad):
    projection = copy.deepcopy(PROJECTION)
    row = projection["modulator function properties"][family]
    if bad == "missing-slope":
        row.pop("slope")
    elif bad == "bad-float":
        row["slope"] = "bad"
    else:
        row["slope"] = None
    p = SimpleNamespace(_conf=projection)
    with pytest.raises(
        {"missing-slope": KeyError, "bad-float": ValueError, "none": TypeError}[bad]
    ):
        synthetic_populate()(p)
    assert all(hasattr(p, name) for name in config.STORE_NAMES)
    assert list(getattr(p, family + "_properties")) == []
    assert all(
        len(getattr(p, k + "_properties")) == 4
        for k in config.FAMILIES[: config.FAMILIES.index(family)]
    )


@pytest.mark.parametrize("scenario", validation.SCENARIOS)
def test_configuration_is_separate_from_unchanged_material_and_never_contains_callback_outputs(
    scenario,
):
    families = (
        ("gradient_x", "gradient_y")
        if "_xy_" in scenario
        else ("gradient_y",)
        if "_y_" in scenario
        else ("gradient_x",)
    )
    raw = source_template()
    for key in ("field", "calcium", "catalog", "mechanics_definition", "mechanics_initial"):
        raw["sim_phase"][key] = {"synthetic_only": True}
    before = copy.deepcopy(raw)
    result = validation.configure_sim(raw, scenario, configuration=configuration(families))
    assert raw == before and result["sim_phase"] == before["sim_phase"]
    selected = config.selection(result)
    assert set(selected["families"]) == set(families)
    assert "callbacks" not in selected and "geometry" not in selected
    assert (
        lifecycle.setup.legacy_setup_inputs(result)["sim_composition_template"]["event_inputs"][
            "event_owner"
        ]["scheduled_options"]
        == result["source_setup"][config.TABLE_KEY]["scheduled_options"]
    )


@pytest.mark.parametrize(
    "defect",
    [
        "INIT",
        "legacy-flag",
        "source-schema",
        "source-map",
        "material-event",
        "temporal-mix",
        "supplied-scalar",
        "foreign-field",
        "duplicate-family",
        "unknown-family",
        "radial",
    ],
)
def test_wrong_scope_and_missing_radial_owner_refuse_without_hydration(defect):
    raw = validation.configure_sim(
        source_template(), "spatial_x_combined", configuration=configuration()
    )
    table = raw["source_setup"][config.TABLE_KEY]
    if defect == "INIT":
        raw["sim_phase"]["time_profile"]["phase"] = "INIT"
    elif defect == "legacy-flag":
        raw["sim_phase"]["flags"]["_run_sim"] = False
    elif defect == "source-schema":
        table["foreign_clock_metadata"] = {"epoch": "changed"}
    elif defect == "source-map":
        table["maps"]["tissue_target_inds"]["all"].reverse()
    elif defect == "material-event":
        raw["sim_phase"]["setup"]["scheduled_options"]["Na_mem"] = [
            0,
            1,
            1,
            1,
            ["all"],
            "gradient_x",
        ]
    elif defect == "temporal-mix":
        raw["source_setup"][config.temporal.CONFIG_KEY] = {}
    elif defect == "supplied-scalar":
        raw["source_setup"][config.CONFIG_KEY]["source_scalar"] = [1, 2]
    elif defect == "foreign-field":
        raw["source_setup"][config.CONFIG_KEY]["projection"]["geometry"] = {}
    elif defect == "duplicate-family":
        raw["source_setup"][config.CONFIG_KEY]["families"] = ["gradient_x", "gradient_x"]
    elif defect == "unknown-family":
        table["scheduled_options"]["Na_mem"][5] = "single_cell"
    else:
        raw["source_setup"][config.CONFIG_KEY]["families"] = ["gradient_r"]
        for row in table["scheduled_options"].values():
            if row != 0:
                row[5] = "gradient_r"
    with pytest.raises(ValueError):
        config.selection(raw)


@pytest.mark.parametrize(
    "phase,run_sim,route",
    [("INIT", False, authority.ROUTE), ("SIM", False, authority.ROUTE), ("SIM", True, "legacy")],
)
def test_setup_extension_is_only_explicit_actual_SIM(phase, run_sim, route):
    raw = validation.configure_sim(
        source_template(), "spatial_x_combined", configuration=configuration()
    )
    with pytest.raises(ValueError, match="SIM-only"):
        authority.validate_SIM_setup(
            raw["source_setup"][config.TABLE_KEY],
            object(),
            phase=phase,
            run_sim=run_sim,
            preparation_route=route,
        )


def test_positive_SIM_whitelist_routing_does_not_rewrite_names(monkeypatch):
    raw = validation.configure_sim(
        source_template(),
        "spatial_xy_combined",
        configuration=configuration(("gradient_x", "gradient_y")),
    )
    table = raw["source_setup"][config.TABLE_KEY]
    called = []
    monkeypatch.setattr(
        authority, "_validate_SIM_spatial_setup", lambda actual, base: called.append((actual, base))
    )
    authority.validate_SIM_setup(
        table, "synthetic-base", phase="SIM", run_sim=True, preparation_route=authority.ROUTE
    )
    assert called == [(table, "synthetic-base")]
    assert {row[5] for row in table["scheduled_options"].values() if row != 0} == {
        "gradient_x",
        "gradient_y",
    }


@pytest.mark.parametrize(
    "scenario,families",
    [
        ("spatial_x_combined", ("gradient_x",)),
        ("spatial_y_mixed_constant", ("gradient_y",)),
        ("spatial_xy_combined", ("gradient_x", "gradient_y")),
    ],
)
def test_synthetic_observation_binds_all_source_arrays_and_closed_store_graph(
    scenario, families, tmp_path
):
    g = returns(manufactured(scenario, families))
    early = observation(g)
    assert (
        config.validate_receipt(g.source, early, completed=g.completed)
        == early["spatial_configuration_store"]
    )
    for _, suffix, _ in g.trace.selected:
        assert g.trace.records[suffix]["source_scalar"].shape == (4,)
        assert g.trace.records[suffix]["callable_instance_persisted"] is False
    payload = dict(source=g.source, completed=g.completed, early=lifecycle.ions.freeze(early))
    document, arrays = packed(payload)
    decoded = checkpoint.codec.decode(document, arrays)
    assert checkpoint.codec.fingerprint(decoded) == checkpoint.codec.fingerprint(payload)
    assert config.validate_receipt(
        decoded["source"], decoded["early"], completed=decoded["completed"]
    )
    (tmp_path / "spatial-codec-control.json").write_text(
        json.dumps(dict(actual_decoder_setup_calls=0, native_callable_persistence=False))
    )


@pytest.mark.parametrize(
    "defect",
    [
        "p-owner",
        "conf-owner",
        "store-owner",
        "store-value",
        "geometry-owner",
        "geometry-value",
        "geometry-dtype",
        "cell-axis",
        "phase-owner",
        "phase-kind",
    ],
)
def test_live_association_rejects_equal_replacements_and_value_axis_drift(defect):
    g = manufactured()
    if defect == "p-owner":
        g.live_phase.p = copy.copy(g.p)
    elif defect == "conf-owner":
        g.p._conf = copy.deepcopy(g.p._conf)
    elif defect == "store-owner":
        g.p.gradient_x_properties = copy.deepcopy(g.p.gradient_x_properties)
    elif defect == "store-value":
        g.p.gradient_x_properties["slope"] += 0.1
    elif defect == "geometry-owner":
        g.live_phase.cells.mem_mids_flat = g.live_phase.cells.mem_mids_flat.copy()
    elif defect == "geometry-value":
        g.live_phase.cells.mem_mids_flat[0, 0] += 1e-6
    elif defect == "geometry-dtype":
        g.live_phase.cells.mem_mids_flat = g.live_phase.cells.mem_mids_flat.astype(np.float32)
    elif defect == "cell-axis":
        g.live_phase.cells.cell_i[0] = 1
    elif defect == "phase-owner":
        g.live_phase = copy.copy(g.live_phase)
    else:
        g.live_phase.kind = "INIT"
    with pytest.raises(ValueError):
        g.issuer.check(g.live_phase)


@pytest.mark.parametrize(
    "defect",
    [
        "source",
        "configuration",
        "geometry",
        "INIT",
        "SIM",
        "count",
        "epoch",
        "replay",
        "runtime",
        "property",
    ],
)
def test_resealed_closed_receipt_cannot_replace_source_or_owner_associations(defect):
    g = returns(manufactured())
    early = observation(g)
    saved = early["spatial_configuration_store"]
    if defect == "source":
        saved["source"]["source_sha256"] = "foreign"
    elif defect == "configuration":
        saved["configuration"]["provenance"] += "changed"
    elif defect == "geometry":
        saved["geometry"] = dict(saved["geometry"], membrane_midpoints_m=((0, 0),) * 4)
    elif defect == "INIT":
        saved["geometry"] = dict(saved["geometry"], source_INIT_parent_identity="foreign")
    elif defect == "SIM":
        saved["source_SIM_declaration_identity"] = "foreign"
    elif defect == "count":
        saved["selected_float_lookups"] = True
    elif defect == "epoch":
        saved["stage"] = "before-source-finalizers"
    elif defect == "replay":
        saved["replayed"] = True
    elif defect == "runtime":
        saved["runtime"]["cells"] = saved["runtime"]["parameter"]
    else:
        saved["after"]["gradient_x_properties"]["slope"] += 0.1
    saved["identity"] = lifecycle.ions.digest({k: v for k, v in saved.items() if k != "identity"})
    with pytest.raises(ValueError):
        config.validate_receipt(g.source, early, completed=g.completed)


@pytest.mark.parametrize(
    "bad", ["factory-code", "caller", "parameter", "cells", "target-owner", "target-order"]
)
def test_factory_frame_must_be_the_actual_finalizer_and_issued_targets(bad):
    g = manufactured()
    key, suffix, family = g.trace.selected[0]
    targets = getattr(g.actual, "targets_" + suffix)
    frame = SimpleNamespace(
        f_code=authority.FACTORY_CODES[family],
        f_globals=vars(authority.source),
        f_locals=dict(p=g.p, cells=g.live_phase.cells, pc=targets),
        f_back=SimpleNamespace(
            f_code=authority.FINALIZER_CODE,
            f_globals=vars(authority.lifecycle_source),
            f_locals=dict(self=g.actual, phase=g.live_phase),
        ),
    )
    if bad == "factory-code":
        frame.f_code = authority.FACTORY_CODES["gradient_y"]
    elif bad == "caller":
        frame.f_back.f_code = (lambda: None).__code__
    elif bad == "parameter":
        frame.f_locals["p"] = copy.copy(g.p)
    elif bad == "cells":
        frame.f_locals["cells"] = copy.copy(g.live_phase.cells)
    elif bad == "target-owner":
        frame.f_locals["pc"] = list(targets)
    else:
        targets.reverse()
    with pytest.raises(ValueError):
        g.trace.observe(frame, "call", None)


@pytest.mark.parametrize(
    "bad", ["dtype", "shape", "category", "callback-code", "closure", "nonfinite"]
)
def test_source_scalar_callback_categories_are_not_normalized(bad):
    g = manufactured()
    family = "gradient_x"
    targets = list(range(4))
    callback = FunctionType(authority.callback_code(family), vars(authority.source))
    scalar = np.arange(4, dtype=np.float64)
    if bad == "dtype":
        scalar = scalar.astype(np.float32)
    elif bad == "shape":
        scalar = scalar.reshape(2, 2)
    elif bad == "category":
        scalar = scalar.tolist()
    elif bad == "callback-code":

        def callback(t):
            return 1
    elif bad == "closure":
        callback.__defaults__ = (1,)
    else:
        scalar[0] = np.nan
    with pytest.raises(ValueError):
        authority.inspect_callback(callback, scalar, family, targets, g.issuer.geometry)


def test_count_tie_prefers_membranes_and_two_membrane_targets_use_full_cell_axis():
    g = manufactured()
    assert authority.scalar_axis([0, 1], g.issuer.geometry) == ("cells", 2)
    assert authority.scalar_axis([2, 2, 0, 3], g.issuer.geometry) == ("membranes", 4)
    geometry = dict(g.issuer.geometry, cell_ids=g.issuer.geometry["membrane_ids"])
    assert authority.scalar_axis([0, 0, 0, 0], geometry) == ("membranes", 4)
    assert authority.scalar_axis([0], g.issuer.geometry) == ("native_unbound_axis", None)


def test_live_issuer_is_not_a_checkpoint_record_or_serializable_owner():
    g = manufactured()
    with pytest.raises(TypeError):
        g.issuer.__reduce__()
    with pytest.raises((TypeError, ValueError)):
        checkpoint.codec.Encoder().capture(g.issuer)
    assert not any(name.endswith(".Issuance") for name in checkpoint.records.registry())


@pytest.mark.parametrize("releases", [(False, False), (True, False), (False, True)])
def test_both_release_gates_precede_parent_access_and_output(tmp_path, monkeypatch, releases):
    for name, enabled in zip(validation.RELEASES, releases, strict=True):
        monkeypatch.setenv(name, "1" if enabled else "0")
    output = tmp_path / "held"
    with pytest.raises(ValueError, match="remains held"):
        validation.prepare_sim(
            output,
            object(),
            object(),
            [],
            scenario="spatial_x_combined",
            event_owner_inputs=None,
            configuration=configuration(),
            expected_INIT_binding_identity="x",
            expected_INIT_parent_identity="y",
        )
    assert not output.exists()


def test_released_untyped_parent_refuses_without_binding_verification_or_artifacts(
    tmp_path, monkeypatch
):
    for name in validation.RELEASES:
        monkeypatch.setenv(name, "1")
    with pytest.raises(ValueError, match="actual typed INIT"):
        validation.prepare_sim(
            tmp_path / "bad",
            object(),
            object(),
            [],
            scenario="spatial_x_combined",
            event_owner_inputs=None,
            configuration=configuration(),
            expected_INIT_binding_identity="x",
            expected_INIT_parent_identity="y",
        )
    assert not (tmp_path / "bad").exists()


@pytest.mark.parametrize("mode", ["exception", "normal-None", "tuple"])
def test_actually_profiled_synthetic_factory_preserves_unwind_and_profiler(monkeypatch, mode):
    g = manufactured("spatial_x_Na_mem")
    primary, cause = ValueError("synthetic source factory error"), LookupError("synthetic cause")
    callback_code = authority.callback_code("gradient_x")
    fake_source = SimpleNamespace(primary=primary, cause=cause, mode=mode)
    scalar = np.linspace(0.1, 0.7, 4, dtype=np.float64)
    callback = FunctionType(callback_code, vars(fake_source))
    fake_source.scalar, fake_source.callback = scalar, callback

    def factory(pc, cells, p):
        if mode == "exception":
            raise primary from cause
        if mode == "normal-None":
            return None
        return scalar, callback

    actual_factory = FunctionType(factory.__code__, vars(fake_source), closure=factory.__closure__)
    fake_lifecycle = SimpleNamespace(factory=actual_factory)

    def finalizer(self, phase):
        result = factory(self.targets_Namem, phase.cells, phase.p)
        if result is not None:
            self.scalar_Namem, self.dyna_Namem = result

    # Remove the enclosing Python closure so the caller/function globals are
    # truly the synthetic namespaces observed by the profiler.
    finalizer_node = ast.parse(
        "def finalizer(self,phase):\n"
        "    result=factory(self.targets_Namem,phase.cells,phase.p)\n"
        "    if result is not None:\n"
        "        self.scalar_Namem,self.dyna_Namem=result\n"
    )
    ns = vars(fake_lifecycle)
    exec(compile(finalizer_node, "<profiled-synthetic-spatial-finalizer>", "exec"), ns)
    actual_finalizer = ns["finalizer"]
    monkeypatch.setattr(authority, "source", fake_source)
    monkeypatch.setattr(authority, "lifecycle_source", fake_lifecycle)
    monkeypatch.setattr(authority, "FACTORY_CODES", {"gradient_x": actual_factory.__code__})
    monkeypatch.setattr(authority, "FINALIZER_CODE", actual_finalizer.__code__)
    monkeypatch.setattr(authority, "source_identity", lambda: dict(synthetic_only=True))
    monkeypatch.setattr(authority, "callback_code", lambda family: callback_code)
    previous = sys.getprofile()
    if mode == "exception":
        with pytest.raises(ValueError) as caught:
            with g.trace:
                actual_finalizer(g.actual, g.live_phase)
        assert caught.value is primary and primary.__cause__ is cause
    elif mode == "normal-None":
        with pytest.raises(ValueError, match="Missing/omitted"):
            with g.trace:
                actual_finalizer(g.actual, g.live_phase)
    else:
        with g.trace:
            actual_finalizer(g.actual, g.live_phase)
        assert g.trace.complete and g.trace.scalars["Namem"] is scalar
    assert sys.getprofile() is previous
    assert g.trace.entry_attempts == g.trace.return_events == 1
    if mode != "tuple":
        assert not g.trace.complete and g.trace.pending is not None
        assert g.trace.entries[0]["status"] == "return_or_unwind_incomplete"
        assert g.trace.data()["available_handler_scalars"]["Namem"] == 1


@pytest.mark.parametrize(
    "defect", ["numpy-callable", "len-shadow", "getattr-shadow", "source-function", "source-code"]
)
def test_resolved_factory_and_finalizer_bindings_are_checked_without_execution(monkeypatch, defect):
    if defect == "numpy-callable":
        monkeypatch.setattr(np, "sqrt", lambda value: value)
    elif defect == "len-shadow":
        monkeypatch.setattr(authority.source, "len", len, raising=False)
    elif defect == "getattr-shadow":
        monkeypatch.setattr(authority.lifecycle_source, "getattr", getattr, raising=False)
    elif defect == "source-function":
        monkeypatch.setattr(authority.source, "gradient_x", lambda *args: None)
    else:
        monkeypatch.setattr(
            authority.FACTORIES["gradient_x"], "__code__", (lambda *args: None).__code__
        )
    with pytest.raises(ValueError):
        authority.source_identity()


def metadata_INIT_run(status="exhausted"):
    from cells.processes import betse_normal_ecm_molecule_run_lifecycle as run

    g = graph()
    phase = replace(g.completed.binding, calendar=SimpleNamespace(phase="INIT", step_count=0))
    binding = plain_record(run.Binding, composition=phase, identity="outer-INIT")
    parent = plain_record(
        run.RunState,
        binding_identity=binding.identity,
        status=status,
        identity="outer-parent",
        active=plain_record(lifecycle.init.State, clock=SimpleNamespace(call_index=0)),
    )
    return g, binding, parent


@pytest.mark.parametrize(
    "defect",
    [
        "absent-Inputs",
        "foreign-Inputs",
        "foreign-geometry",
        "wrong-parent",
        "failed",
        "paused",
        "capped",
        "radial",
    ],
)
def test_explicit_input_and_parent_refusals_precede_complete_INIT(tmp_path, monkeypatch, defect):
    for name in validation.RELEASES:
        monkeypatch.setenv(name, "1")
    g, binding, parent = metadata_INIT_run(
        defect if defect in ("failed", "paused", "capped") else "exhausted"
    )
    supplied = g.source.event_owner_inputs
    configured = configuration()
    if defect == "absent-Inputs":
        supplied = None
    elif defect == "foreign-Inputs":
        supplied = replace(supplied, source_INIT_binding_identity="foreign")
    elif defect == "foreign-geometry":
        supplied = replace(supplied, source_geometry_binding_identity="foreign")
    elif defect == "wrong-parent":
        parent = replace(parent, identity="foreign")
    elif defect == "radial":
        configured = configuration(("gradient_r",))
    output = tmp_path / "preflight"
    with pytest.raises(ValueError):
        validation.prepare_sim(
            output,
            binding,
            parent,
            [],
            scenario="spatial_x_combined",
            event_owner_inputs=supplied,
            configuration=configured,
            expected_INIT_binding_identity="outer-INIT",
            expected_INIT_parent_identity="outer-parent",
        )
    assert not output.exists()


def test_closed_decoder_is_metadata_only_even_when_source_entrypoints_are_blocked():
    g = returns(manufactured())
    early = lifecycle.ions.freeze(observation(g))
    document, data = packed(early)
    loaded = checkpoint.codec.decode(document, data)
    assert checkpoint.codec.fingerprint(loaded) == checkpoint.codec.fingerprint(early)
    assert loaded["spatial_configuration_store"]["callable_instance_persisted"] is False


def publication_graph():
    g = returns(manufactured())
    early = observation(g)
    template = {key: copy.deepcopy(g.table[key]) for key in ("global_options", "scheduled_options")}
    template.update(callbacks={}, handler_fields={})
    template.update(copy.deepcopy(g.table["maps"]))
    early["owner"] = lifecycle.setup.finalized_owner(
        template, g.actual, g.p, spatial_observation=g.trace
    )
    early = lifecycle.ions.freeze(early)
    final = lifecycle.ions.data(g.source.inputs["sim_phase"])
    final["field"]["definition"]["environment_geometry_definition"]["cache_initial_state"] = {
        "epoch": "after source setup"
    }
    pub = bridge.publish(g.source, g.completed, early, final, g.mechanical, g.profiles)
    receipt = dict(
        source_phase="SIM",
        legacy_run_sim=True,
        source_init_identity=g.completed.identity,
        event_finalization=dict(source_fields=early, owner_publication=pub),
        source_setup=dict(event_finalized=early, event_owner_published=pub),
    )
    phase = replace(
        g.phase,
        inputs_raw=lifecycle.ions.freeze(final),
        inputs=lifecycle.ions.freeze(final["field"]),
        setup_receipt=lifecycle.ions.freeze(receipt),
        material_binding=g.completed.binding.material_binding,
    )
    entry = replace(
        g.entry, binding_identity=g.source.identity, source_init=g.completed, phase_binding=phase
    )
    g.early, g.final, g.pub, g.phase, g.entry = early, final, pub, phase, entry
    return g


def test_later_publication_retains_early_epoch_and_typed_source_array_authority():
    g = publication_graph()
    actual = bridge.resolve(g.source, g.entry)
    assert actual.identity == g.pub.identity and bridge.same(actual.event_finalized, g.early)
    assert (
        actual.epoch == bridge.EPOCH
        and actual.event_finalized_identity == lifecycle.ions.digest(g.early)
    )
    assert all(
        type(row["source_scalar"]) is np.ndarray
        for row in g.early["spatial_callback_authority"].values()
    )
    declaration = validation.declaration(g.source, g.entry, "spatial_x_combined")
    assert bridge.same(declaration["event_owner"], lifecycle.ions.data(g.pub.owner))
    component = SimpleNamespace(
        raw=declaration, base=g.phase, source_binding=g.source, source_entry=g.entry
    )
    lifecycle_run = checkpoint.run.composition
    lifecycle_run.event_scope(component)


@pytest.mark.parametrize(
    "bad",
    [
        "scalar-value",
        "scalar-dtype",
        "scalar-shape",
        "source-function",
        "runtime",
        "targets",
        "profiles",
        "sequence",
    ],
)
def test_resealed_callback_record_cannot_replace_retained_scalar_or_owner(bad):
    g = publication_graph()
    owner = lifecycle.ions.data(g.pub.owner)
    fields = lifecycle.ions.data(g.early)
    # Preserve typed arrays rather than turning a source category into JSON.
    fields["spatial_callback_authority"] = copy.deepcopy(g.trace.records)
    fields["spatial_configuration_store"] = g.early["spatial_configuration_store"]
    saved = fields["spatial_callback_authority"]["Namem"]
    if bad == "scalar-value":
        saved["source_scalar"][0] += 0.01
    elif bad == "scalar-dtype":
        saved["source_scalar"] = saved["source_scalar"].astype(np.float32)
    elif bad == "scalar-shape":
        saved["source_scalar"] = saved["source_scalar"].reshape(2, 2)
    elif bad == "source-function":
        saved["source_function"] = "gradient_r"
    elif bad == "runtime":
        saved["runtime"]["cells"] += 1
    elif bad == "targets":
        saved["targets"].reverse()
    elif bad == "profiles":
        saved["profiles"] = ["region0"]
    else:
        saved["sequence"] += 1
    saved["identity"] = lifecycle.ions.digest({k: v for k, v in saved.items() if k != "identity"})
    with pytest.raises(ValueError):
        authority.validate(g.source, owner, g.pub, fields)
