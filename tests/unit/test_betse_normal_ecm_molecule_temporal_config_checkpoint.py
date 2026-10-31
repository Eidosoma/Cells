"""Selected temporal projection controls; actual constructors/factories stay held.

Manufactured graphs below are unowned metadata. Synthetic assignment controls
compile the statically compared selected AST into a different test function;
they do not call the production constructor/populate, native parser or model.
"""

import ast
import copy
import hashlib
import json
import sys
from dataclasses import replace
from pathlib import Path
from types import CellType, FunctionType, SimpleNamespace

import pytest

from cells.processes import betse_normal_ecm_molecule_checkpoint as checkpoint
from cells.processes import betse_normal_ecm_molecule_event_owner as bridge
from cells.processes import betse_normal_ecm_molecule_lifecycle as lifecycle
from cells.processes import betse_normal_ecm_molecule_periodic_authority as periodic
from cells.processes import betse_normal_ecm_molecule_sweep_authority as sweep
from cells.processes import betse_normal_ecm_molecule_temporal_config as temporal
from tests.unit.test_betse_normal_ecm_molecule_event_checkpoint import (
    no_actual_execution as no_actual_execution,
)
from tests.unit.test_betse_normal_ecm_molecule_event_checkpoint import plain_record
from tests.unit.test_betse_normal_ecm_molecule_event_owner import explicit_inputs, graph
from tests.unit.test_betse_normal_ecm_molecule_periodic_checkpoint import (
    forbid_actual_periodic as forbid_actual_periodic,
)
from tests.unit.test_betse_normal_ecm_molecule_periodic_checkpoint import reseal, source_template
from validation.betse import betse_normal_ecm_molecule_checkpoint as preparation
from validation.betse import betse_normal_ecm_molecule_temporal_config_checkpoint as validation
from validation.betse.betse_normal_ecm_event_join_fixtures import finalize_fields

PROJECTION = {
    "modulator function properties": {
        "periodic": {"frequency": "-3.75", "phase": "-0.25"},
        "f_sweep": {"start frequency": "500", "end frequency": "1500.0"},
    }
}
INITIAL = {
    "periodic": {"frequency": -3.75, "phase": -0.25},
    "f_sweep": {"f start": 500.0, "f stop": 1500.0, "f slope": None},
}


def configuration(family="periodic"):
    return dict(
        kind=temporal.KIND,
        mode=temporal.MODE,
        family=family,
        projection=copy.deepcopy(PROJECTION),
        provenance="Unowned normalized synthetic temporal projection, not native YAML",
    )


@pytest.fixture(autouse=True)
def no_actual_selected_constructor(forbid_actual_periodic, tmp_path):
    codes = {
        temporal.Issuance.__init__.__code__,
        temporal.Issuance.construct.__code__,
        temporal.source.populate.__code__,
        temporal.context.construct_context.__code__,
    }
    attempted = []
    previous = sys.getprofile()

    def guard(frame, event, arg):
        if previous is not None:
            previous(frame, event, arg)
        if event == "call" and frame.f_code in codes:
            attempted.append(frame.f_code.co_name)
            raise AssertionError("Actual selected constructor/source execution forbidden")

    sys.setprofile(guard)
    try:
        yield attempted
        assert not attempted
    finally:
        sys.setprofile(previous)
        (tmp_path / "selected-store-control.json").write_text(
            json.dumps(
                dict(
                    actual_constructor_entries=attempted,
                    actual_native_model_RNG=0,
                    synthetic_graph_admission=False,
                    independent_cases=0,
                )
            )
        )


def synthetic_populate():
    node = next(
        n
        for n in ast.parse(Path(temporal.source.__file__).read_bytes()).body
        if isinstance(n, ast.FunctionDef)
    )
    node.name = "synthetic_selected_assignments"
    module = ast.Module(body=[node], type_ignores=[])
    namespace = {}
    exec(
        compile(ast.fix_missing_locations(module), "<synthetic-temporal-assignments>", "exec"),
        namespace,
    )
    return namespace[node.name]


def manufactured(family="periodic", scenario=None):
    scenario = scenario or ("periodic_combined" if family == "periodic" else "sweep_combined")
    configured = validation.configure_sim(
        source_template(), scenario, configuration=configuration(family)
    )
    table = configured["source_setup"][temporal.TABLE_KEY]
    g = graph()
    raw = lifecycle.ions.data(g.source.inputs)
    for key in ("setup", "flags", "time_profile"):
        raw["sim_phase"][key] = copy.deepcopy(configured["sim_phase"][key])
    raw["source_setup"].update(
        {
            key: copy.deepcopy(configured["source_setup"][key])
            for key in (*temporal.KEYS, "provenance")
        }
    )
    g.source = replace(g.source, inputs=lifecycle.ions.freeze(raw))
    g.source = replace(g.source, identity=lifecycle.ions.digest(lifecycle.binding_record(g.source)))
    initial = copy.deepcopy(INITIAL)
    p = SimpleNamespace(
        _conf=copy.deepcopy(PROJECTION),
        periodic_properties=copy.deepcopy(initial["periodic"]),
        f_scan_properties=copy.deepcopy(initial["f_sweep"]),
        scheduled_options=table["scheduled_options"],
        _run_sim=True,
        sim_time_total=raw["sim_phase"]["time_profile"]["sim_total_s"],
    )
    phase = SimpleNamespace(p=p, kind="SIM", cells=object())
    # Intentionally unissued metadata object. Production construction is blocked.
    issuer = object.__new__(temporal.Issuance)
    issuer.__dict__.update(
        binding=g.source,
        completed=g.completed,
        config=temporal.selection(g.source.inputs),
        p=p,
        conf=p._conf,
        periodic=p.periodic_properties,
        sweep=p.f_scan_properties,
        phase=phase,
        initial=initial,
        attempts=1,
        stage="constructed_before_actual_phase_and_finalizers",
    )
    fields = finalize_fields(table["global_options"], table["scheduled_options"], table["maps"], 4)
    actual = SimpleNamespace(**fields)
    trace = (
        periodic.FactoryObservation(
            actual, phase, initial["periodic"], binding=g.source, parameter_issuance=issuer
        )
        if family == "periodic"
        else sweep.FactoryObservation(actual, phase, initial["f_sweep"], parameter_issuance=issuer)
    )
    g.configured, g.table, g.p, g.live_phase, g.issuer = configured, table, p, phase, issuer
    g.actual, g.trace, g.family = actual, trace, family
    return g


def returns(g):
    authority = periodic if g.family == "periodic" else sweep
    for _, suffix in g.trace.selected:
        frame = SimpleNamespace(
            f_code=authority.FACTORY_CODE,
            f_globals=vars(authority.source),
            f_locals=dict(
                p=g.p, cells=g.live_phase.cells, pc=getattr(g.actual, "targets_" + suffix)
            ),
            f_back=SimpleNamespace(
                f_code=authority.FINALIZER_CODE,
                f_globals=vars(authority.source),
                f_locals=dict(self=g.actual, phase=g.live_phase),
            ),
        )
        g.trace.observe(frame, "call", None)
        if g.family == "f_sweep":
            # Synthetic stand-in for the held source factory mutation; not a
            # source factory invocation or a time-law/trajectory observation.
            g.p.f_scan_properties["f slope"] = 1000.0 / g.p.sim_time_total
            frame.f_locals["f_slope"] = g.p.f_scan_properties["f slope"]
        closure = (
            (CellType(g.p),)
            if g.family == "periodic"
            else (CellType(g.p.f_scan_properties["f slope"]), CellType(g.p))
        )
        callback = FunctionType(authority.callback_code(), vars(authority.source), closure=closure)
        setattr(g.actual, "dyna_" + suffix, callback)
        setattr(g.actual, "scalar_" + suffix, 1)
        g.trace.observe(frame, "return", (1, callback))
    g.trace.finish()
    return g


def published(family="periodic"):
    g = returns(manufactured(family))
    early = lifecycle.ions.data(g.early)
    callbacks = {}
    for key, suffix in sweep.MEMBRANE_KEYS.items():
        row = g.table["scheduled_options"][key]
        if row == 0:
            continue
        dynamic = (
            dict(
                kind="periodic",
                **g.p.periodic_properties,
                provenance="Actual SIM periodic finalizer result",
            )
            if family == "periodic"
            else dict(
                kind="sweep",
                start=g.p.f_scan_properties["f start"],
                slope=g.p.f_scan_properties["f slope"],
                provenance="Actual SIM f_sweep finalizer result",
            )
        )
        callbacks[suffix] = dict(source_function=family, source_scalar=1, dynamic=dynamic)
    early["owner"].update(
        global_options=g.table["global_options"],
        scheduled_options=g.table["scheduled_options"],
        handler_fields=finalize_fields(
            g.table["global_options"], g.table["scheduled_options"], g.table["maps"], 4
        ),
        callbacks=callbacks,
    )
    early.update(
        temporal_configuration_store=g.issuer.receipt(g.trace),
        frequency_sweep_after=copy.deepcopy(g.p.f_scan_properties),
    )
    if family == "periodic":
        early.update(
            periodic_callback_authority=g.trace.records,
            periodic_properties_after=copy.deepcopy(g.p.periodic_properties),
        )
    else:
        early["sweep_callback_authority"] = g.trace.records
    g.final["setup"] = copy.deepcopy(g.configured["sim_phase"]["setup"])
    object.__setattr__(g.phase, "inputs_raw", lifecycle.ions.freeze(g.final))
    reseal(g, early)
    return g


def test_selected_statements_exact_native_AST_and_no_temporal_defaults(tmp_path):
    path = Path("/mnt/workspaces/Cells/betse-v1.5.0/betse/science/parameters.py")
    assert hashlib.sha256(path.read_bytes()).hexdigest() == temporal.NATIVE_SHA
    native = ast.parse(path.read_bytes())
    adopted = ast.parse(Path(temporal.source.__file__).read_bytes())
    names = ("self.periodic_properties", "self.f_scan_properties")
    statements = sorted(
        (
            node
            for node in ast.walk(native)
            if isinstance(node, ast.Assign)
            and any(
                ast.unparse(t) in names or any(ast.unparse(t).startswith(n + "[") for n in names)
                for t in node.targets
            )
        ),
        key=lambda node: node.lineno,
    )
    copied = next(n for n in adopted.body if isinstance(n, ast.FunctionDef)).body
    assert len(statements) == len(copied) == 7
    assert [ast.dump(n, include_attributes=False) for n in statements] == [
        ast.dump(n, include_attributes=False) for n in copied
    ]
    assert not any(
        isinstance(n, ast.Attribute) and n.attr == "get" for node in copied for n in ast.walk(node)
    )
    assert ast.literal_eval(copied[-1].value) is None
    (tmp_path / "native-selected-correspondence.json").write_text(
        json.dumps(
            dict(
                native_sha256=temporal.NATIVE_SHA,
                selected_statements=7,
                native_calls=0,
                excluded="full parser/YAML/gradient fields and their earlier failures",
            )
        )
    )


def test_context_only_early_constructor_delta_and_upstream_guard():
    temporal.context.check_original()
    assert temporal.source_identity()["original_context_AST"] == temporal.context.ORIGINAL_AST


@pytest.mark.parametrize("target", ["original", "selected", "populate", "float"])
def test_source_owner_substitution_refuses(monkeypatch, target):
    if target == "original":
        monkeypatch.setattr(temporal.context.network, "make_context", lambda: None)
    elif target == "selected":
        monkeypatch.setattr(temporal.context, "construct_context", lambda: None)
    elif target == "populate":
        monkeypatch.setattr(temporal.source, "populate", lambda: None)
    else:
        monkeypatch.setattr(temporal.source, "float", lambda x: 1.0, raising=False)
    with pytest.raises(ValueError):
        temporal.source_identity()


@pytest.mark.parametrize("scenario", validation.SCENARIOS)
def test_both_families_keep_material_and_explicit_raw_config(scenario):
    family = "periodic" if scenario.startswith("periodic_") else "f_sweep"
    raw = source_template()
    before = copy.deepcopy(raw)
    result = validation.configure_sim(raw, scenario, configuration=configuration(family))
    assert raw == before
    assert result["sim_phase"] == raw["sim_phase"]
    assert temporal.selection(result)["projection"] == PROJECTION
    assert "frequency_sweep" not in result["source_setup"]
    assert not set(result["source_setup"]).intersection(
        {"periodic_properties", "periodic_preparation_route"}
    )
    assert all(row == 0 for row in result["sim_phase"]["setup"]["scheduled_options"].values())


@pytest.mark.parametrize("position", range(4))
@pytest.mark.parametrize("bad", ["missing", "not-a-number", None, []])
def test_synthetic_native_raw_failure_order_partial_stores(position, bad, tmp_path):
    raw = copy.deepcopy(PROJECTION)
    paths = (
        ("periodic", "frequency"),
        ("periodic", "phase"),
        ("f_sweep", "start frequency"),
        ("f_sweep", "end frequency"),
    )
    section, key = paths[position]
    if bad == "missing":
        del raw["modulator function properties"][section][key]
    else:
        raw["modulator function properties"][section][key] = bad
    p = SimpleNamespace(_conf=raw)
    function = synthetic_populate()
    expected = KeyError if bad == "missing" else ValueError if bad == "not-a-number" else TypeError
    with pytest.raises(expected) as caught:
        function(p)
    assert p._conf is raw
    assert len(p.periodic_properties) == min(position, 2)
    assert len(p.f_scan_properties) == max(position - 2, 0)
    assert "f slope" not in p.f_scan_properties
    (tmp_path / "synthetic-store-failure.json").write_text(
        json.dumps(
            dict(
                source_execution=False,
                primary=dict(type=type(caught.value).__name__, message=str(caught.value)),
                failed_lookup=position,
                partial=dict(periodic=p.periodic_properties, f_sweep=p.f_scan_properties),
            )
        )
    )


@pytest.mark.parametrize("value", [0, -1, True, "1.25", " 1e3 "])
def test_synthetic_float_conversion_and_native_None_slope(value):
    raw = copy.deepcopy(PROJECTION)
    raw["modulator function properties"]["periodic"]["frequency"] = value
    p = SimpleNamespace(_conf=raw)
    synthetic_populate()(p)
    assert type(p.periodic_properties["frequency"]) is float
    assert p.periodic_properties["frequency"] == float(value)
    assert list(p.periodic_properties) == ["frequency", "phase"]
    assert list(p.f_scan_properties) == ["f start", "f stop", "f slope"]
    assert p.f_scan_properties["f slope"] is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("kind", "foreign"),
        ("mode", "supplied"),
        ("family", "gradient_x"),
        ("provenance", ""),
        ("projection", {"full YAML": {}}),
        ("projection", {"modulator function properties": {"gradient_x": {}}}),
        ("projection", {"modulator function properties": {"f_sweep": {"f slope": 1.0}}}),
        ("projection", {"modulator function properties": {"periodic": {"frequency": object()}}}),
    ],
)
def test_projection_does_not_promote_full_parser_defaults_or_arbitrary_objects(field, value):
    configured = configuration()
    configured[field] = value
    with pytest.raises(ValueError):
        temporal.check_configuration(configured)


@pytest.mark.parametrize(
    "change",
    [
        "INIT",
        "flag-int",
        "missing-table",
        "manual-periodic",
        "manual-sweep",
        "material-event",
        "common-map",
        "wrong-family",
        "unknown-callback",
    ],
)
def test_selected_source_route_refusals(change):
    raw = validation.configure_sim(
        source_template(), "periodic_combined", configuration=configuration()
    )
    if change == "INIT":
        raw["sim_phase"]["time_profile"]["phase"] = "INIT"
    elif change == "flag-int":
        raw["sim_phase"]["flags"]["_run_sim"] = 1
    elif change == "missing-table":
        del raw["source_setup"][temporal.TABLE_KEY]
    elif change == "manual-periodic":
        raw["source_setup"]["periodic_properties"] = INITIAL["periodic"]
    elif change == "manual-sweep":
        raw["source_setup"]["frequency_sweep"] = INITIAL["f_sweep"]
    elif change == "material-event":
        raw["sim_phase"]["setup"]["scheduled_options"]["Na_mem"] = [0, 1, 1, 1, ["all"], "None"]
    elif change == "common-map":
        raw["source_setup"][temporal.TABLE_KEY]["maps"]["tissue_target_inds"]["all"] = [0]
    elif change == "wrong-family":
        raw["source_setup"][temporal.CONFIG_KEY]["family"] = "f_sweep"
    else:
        raw["source_setup"][temporal.TABLE_KEY]["scheduled_options"]["Na_mem"][5] = "bitmap"
    with pytest.raises(ValueError):
        temporal.selection(raw)


@pytest.mark.parametrize("family", ["periodic", "f_sweep"])
@pytest.mark.parametrize(
    "change",
    [
        "p",
        "conf",
        "periodic-alias",
        "sweep-alias",
        "phase",
        "raw-category",
        "parsed-category",
        "start",
        "pre-slope",
    ],
)
def test_same_issued_owner_mapping_and_raw_value_association(family, change):
    g = manufactured(family)
    if change == "p":
        g.live_phase.p = SimpleNamespace(**vars(g.p))
    elif change == "conf":
        g.p._conf = copy.deepcopy(g.p._conf)
    elif change == "periodic-alias":
        g.p.periodic_properties = dict(g.p.periodic_properties)
    elif change == "sweep-alias":
        g.p.f_scan_properties = dict(g.p.f_scan_properties)
    elif change == "phase":
        g.live_phase = SimpleNamespace(**vars(g.live_phase))
    elif change == "raw-category":
        g.p._conf["modulator function properties"]["f_sweep"]["start frequency"] = 500.0
    elif change == "parsed-category":
        g.p.periodic_properties["phase"] = 0
    elif change == "start":
        g.p.f_scan_properties["f start"] += 1
    else:
        g.p.f_scan_properties["f slope"] = 1.0
    with pytest.raises(ValueError):
        g.issuer.check(g.live_phase)


@pytest.mark.parametrize("family", ["periodic", "f_sweep"])
def test_selected_metadata_publication_callback_association_and_both_epochs(family):
    g = published(family)
    assert bridge.resolve(g.source, g.entry) is g.pub
    authority = periodic if family == "periodic" else sweep
    authority.validate(g.source, g.pub.owner, g.pub, g.early)
    assert g.pub.event_finalized is g.early
    assert g.pub.epoch == bridge.EPOCH
    assert g.early["temporal_configuration_store"]["parameter_constructions"] == 1
    assert all(
        row["configuration_store"]["source_binding_identity"] == g.source.identity
        for row in g.trace.records.values()
    )
    assert g.p.f_scan_properties["f slope"] is None if family == "periodic" else g.trace.complete


@pytest.mark.parametrize("family", ["periodic", "f_sweep"])
@pytest.mark.parametrize(
    "change",
    [
        "source",
        "config",
        "INIT",
        "parent",
        "SIM",
        "stage",
        "work",
        "runtime-alias",
        "initial-slope",
        "surviving-periodic",
    ],
)
def test_resealed_store_receipt_refuses_foreign_source_parent_epoch_work(family, change):
    g = published(family)
    early = lifecycle.ions.data(g.early)
    saved = early["temporal_configuration_store"]
    if change == "source":
        saved["source"]["native_parameters_sha256"] = "foreign"
    elif change == "config":
        saved["configuration"]["projection"]["modulator function properties"]["periodic"][
            "phase"
        ] = "0"
    elif change == "INIT":
        saved["source_INIT_binding_identity"] = "foreign"
    elif change == "parent":
        saved["source_INIT_parent_identity"] = "foreign"
    elif change == "SIM":
        saved["source_SIM_declaration_identity"] = "foreign"
    elif change == "stage":
        saved["stage"] = "declared_projection_only"
    elif change == "work":
        saved["parameter_constructions"] = True
    elif change == "runtime-alias":
        saved["runtime"]["periodic_store_object_id"] = saved["runtime"]["sweep_store_object_id"]
    elif change == "initial-slope":
        saved["initial"]["f_sweep"]["f slope"] = 1.0
    else:
        saved["after"]["periodic"]["frequency"] += 1
    saved["identity"] = lifecycle.ions.digest({k: v for k, v in saved.items() if k != "identity"})
    with pytest.raises(ValueError):
        bridge.publish(g.source, g.completed, early, g.final, g.mechanical, g.profiles)


@pytest.mark.parametrize("family", ["periodic", "f_sweep"])
def test_missing_receipt_refuses_and_plain_dictionary_is_not_live_issuer(family):
    g = manufactured(family)
    with pytest.raises(ValueError, match="Missing actual"):
        temporal.validate_receipt(g.source, {})
    with pytest.raises(ValueError, match="actual selected"):
        temporal.callback_association(dict(initial=INITIAL), g.live_phase)
    with pytest.raises(TypeError, match="cannot be serialized"):
        g.issuer.__reduce__()


@pytest.mark.parametrize("gates", [("0", "0"), ("1", "0"), ("0", "1")])
def test_both_release_gates_first_and_no_artifacts(monkeypatch, tmp_path, gates):
    monkeypatch.setenv("CELLS_ECM_MOLECULE_RUN_LIFECYCLE_RELEASED", gates[0])
    monkeypatch.setenv("CELLS_ECM_MOLECULE_EVENTS_RELEASED", gates[1])
    path = tmp_path / "held"
    with pytest.raises(ValueError, match="remains held"):
        validation.prepare_sim(
            path,
            None,
            None,
            [],
            scenario="periodic_combined",
            event_owner_inputs=None,
            configuration=None,
        )
    assert not path.exists()


@pytest.mark.parametrize("bad", [None, {}, "foreign-INIT", "foreign-geometry", "family"])
def test_required_inputs_and_associations_before_complete_INIT(monkeypatch, tmp_path, bad):
    monkeypatch.setenv("CELLS_ECM_MOLECULE_RUN_LIFECYCLE_RELEASED", "1")
    monkeypatch.setenv("CELLS_ECM_MOLECULE_EVENTS_RELEASED", "1")
    g = graph()
    initial = SimpleNamespace(composition=g.completed.binding)
    inputs = explicit_inputs()
    if bad in (None, {}):
        inputs = bad
    elif bad == "foreign-INIT":
        inputs = replace(inputs, source_INIT_binding_identity="foreign")
    elif bad == "foreign-geometry":
        inputs = replace(inputs, source_geometry_binding_identity="foreign")
    configured = configuration("f_sweep" if bad == "family" else "periodic")
    path = tmp_path / "refused"
    with pytest.raises(ValueError):
        validation.prepare_sim(
            path,
            initial,
            object(),
            [],
            scenario="periodic_combined",
            event_owner_inputs=inputs,
            configuration=configured,
        )
    assert not path.exists()


def test_held_plan_no_new_biological_cases_or_parser_authority():
    plan = validation.held_plan()
    assert plan["released"] is False and plan["independent_cases"] == 0
    assert len(plan["scenarios"]) == 16
    assert "normalized projection only" in plan["source_configuration_authority"]
    assert "full Parameters/YAML/parser" in plan["source_configuration_authority"]


@pytest.mark.parametrize("family", ["periodic", "f_sweep"])
def test_closed_checkpoint_retains_store_epochs_aliases_without_issuance(family, tmp_path):
    g = published(family)
    payload = dict(
        source=g.source,
        entry=g.entry,
        early=g.early,
        publication=g.pub,
        store=g.early["temporal_configuration_store"],
        repeated=g.pub,
    )
    encoder = checkpoint.codec.Encoder()
    tree = encoder.capture(payload)
    archive = tmp_path / "arrays.npz"
    encoder.write(tmp_path, tree)
    decoded = checkpoint.codec.decode(tree, archive.read_bytes())
    assert decoded["publication"] is decoded["repeated"]
    assert decoded["early"] is decoded["publication"].event_finalized
    assert decoded["store"] is decoded["early"]["temporal_configuration_store"]
    assert bridge.resolve(decoded["source"], decoded["entry"]) is decoded["publication"]
    authority = periodic if family == "periodic" else sweep
    authority.validate(
        decoded["source"], decoded["publication"].owner, decoded["publication"], decoded["early"]
    )
    assert not any(isinstance(value, temporal.Issuance) for value in decoded.values())


def test_live_issuer_is_outside_closed_codec():
    g = manufactured()
    with pytest.raises((ValueError, TypeError)):
        checkpoint.codec.Encoder().capture(g.issuer)


@pytest.mark.parametrize("family", ["periodic", "f_sweep"])
def test_issued_values_alone_cannot_claim_completed_finalizer_epoch(family):
    g = manufactured(family)
    with pytest.raises(ValueError, match="complete original observed"):
        g.issuer.receipt(g.trace)
    with pytest.raises(ValueError, match="complete original observed"):
        g.issuer.receipt(dict(complete=True))


@pytest.mark.parametrize("family", ["periodic", "f_sweep"])
def test_new_source_lowering_keeps_original_material_owner_and_source_options(family):
    scenario = "periodic_combined" if family == "periodic" else "sweep_combined"
    raw = validation.configure_sim(source_template(), scenario, configuration=configuration(family))
    # This checks transport only. The reduced option template deliberately
    # omits scientific owners; supply explicit unowned sentinels for lowering,
    # never a fabricated admitted phase or a source/finalizer authority.
    for name in ("field", "calcium", "catalog", "mechanics_definition", "mechanics_initial"):
        raw["sim_phase"][name] = {"unowned_synthetic_transport_sentinel": name}
    lowered = lifecycle.setup.legacy_setup_inputs(raw)
    assert lowered["_phase_input"] == raw["sim_phase"]
    event = lowered["sim_composition_template"]["event_inputs"]["event_owner"]
    assert (
        event["scheduled_options"] == raw["source_setup"][temporal.TABLE_KEY]["scheduled_options"]
    )
    assert event["callbacks"] == {} and event["handler_fields"] == {}
    assert "frequency_sweep" not in lowered["source_setup"]


@pytest.mark.parametrize("family", ["periodic", "f_sweep"])
def test_selected_finalizer_guard_selection_preserves_original_common_validator(family):
    # Execute only the source's validator-selection fragment with spies. The
    # real material binder/schema/RNG functions remain blocked by fixtures.
    function = next(
        n
        for n in ast.parse(Path(lifecycle.__file__).read_bytes()).body
        if isinstance(n, ast.FunctionDef) and n.name == "bind"
    )
    start = next(
        i
        for i, n in enumerate(function.body)
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "selected" for t in n.targets)
    )
    end = next(
        i
        for i, n in enumerate(function.body[start:], start)
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "periodic_setup" for t in n.targets)
    )
    fragment = ast.Module(body=copy.deepcopy(function.body[start:end]), type_ignores=[])
    calls = []
    declaration = object()
    base = object()

    def original_guard(table, actual_base):
        calls.append(("original", table, actual_base))

    def periodic_guard(actual_declaration, table, *, preparation_route):
        assert actual_declaration is declaration and preparation_route == periodic.ROUTE
        calls.append(("periodic", table, base))

    original = validation.configure_sim(
        source_template(),
        "periodic_combined" if family == "periodic" else "sweep_combined",
        configuration=configuration(family),
    )
    # The f_sweep branch needs the original declaration's base, no substituted phase.
    if family == "f_sweep":
        declaration = SimpleNamespace(base=base)
    namespace = dict(
        original=original,
        declaration=declaration,
        temporal_config=temporal,
        periodic_authority=periodic,
        init=SimpleNamespace(validate_periodic_finalizer_setup=periodic_guard),
        setup=SimpleNamespace(init_setup=SimpleNamespace(validate=original_guard)),
    )
    exec(
        compile(ast.fix_missing_locations(fragment), "<synthetic-validator-routing>", "exec"),
        namespace,
    )
    assert calls == [
        (
            "periodic" if family == "periodic" else "original",
            original["source_setup"][temporal.TABLE_KEY],
            base,
        )
    ]


@pytest.mark.parametrize("family", ["periodic", "f_sweep"])
def test_stubbed_preparation_preserves_typed_input_identity_and_primary_failure(
    monkeypatch, tmp_path, family
):
    monkeypatch.setenv("CELLS_ECM_MOLECULE_RUN_LIFECYCLE_RELEASED", "1")
    monkeypatch.setenv("CELLS_ECM_MOLECULE_EVENTS_RELEASED", "1")
    g = graph()
    initial = plain_record(preparation.run.Binding, composition=g.completed.binding)
    parent = "unowned synthetic INIT parent"
    supplied = explicit_inputs()
    original = source_template()
    before = copy.deepcopy(original)
    seen = []
    completed_run = plain_record(preparation.run.CompletedInitRun, complete_init=g.completed)
    monkeypatch.setattr(preparation.run, "complete_INIT", lambda *args: completed_run)
    monkeypatch.setattr(preparation.fixtures, "sim_inputs", lambda *args: original)

    def bound(raw, *, event_owner_inputs):
        assert event_owner_inputs is supplied
        seen.append(raw)
        return "unowned synthetic component"

    monkeypatch.setattr(preparation.leaf, "bind", bound)
    monkeypatch.setattr(preparation.fixtures, "declaration", lambda *args: "synthetic run inputs")
    cause = TypeError("retained synthetic source cause")
    primary = RuntimeError("synthetic selected construction/finalizer failure")

    def failed(*args, **kwargs):
        raise primary from cause

    monkeypatch.setattr(preparation.run, "transition", failed)
    attempts = []
    path = tmp_path / "prepared"
    scenario = "periodic_combined" if family == "periodic" else "sweep_combined"
    with pytest.raises(RuntimeError) as caught:
        validation.prepare_sim(
            path,
            initial,
            parent,
            attempts,
            scenario=scenario,
            event_owner_inputs=supplied,
            configuration=configuration(family),
        )
    assert caught.value is primary and primary.__cause__ is cause
    assert original == before and temporal.selection(seen[0])["family"] == family
    assert primary.checkpoint_retention["complete"] is True
    assert primary.checkpoint_retention["source_error"] is primary
    assert attempts[-1]["operation"] == "actual-INIT-to-SIM"
    assert attempts[-1]["operation_status"] == "refused"
    assert all(item["numerical_work_possible"] for item in attempts)
