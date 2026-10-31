"""Periodic prerequisite/authority controls; actual factories/laws stay blocked."""

import ast
import copy
import hashlib
import io
import json
import sys
from dataclasses import replace
from pathlib import Path
from types import CellType, CodeType, FunctionType, SimpleNamespace

import numpy as np
import pytest

from cells.processes import betse_normal_ecm_event_join_source as literal
from cells.processes import betse_normal_ecm_molecule_checkpoint as checkpoint
from cells.processes import betse_normal_ecm_molecule_event_owner as bridge
from cells.processes import betse_normal_ecm_molecule_events as events
from cells.processes import betse_normal_ecm_molecule_lifecycle as lifecycle
from cells.processes import betse_normal_ecm_molecule_periodic_authority as authority
from cells.processes import betse_normal_ecm_molecule_run_lifecycle as run
from cells.processes import betse_time_modulation as time_laws
from tests.unit.test_betse_normal_ecm_molecule_event_checkpoint import (
    no_actual_execution as no_actual_execution,
)
from tests.unit.test_betse_normal_ecm_molecule_event_checkpoint import plain_record
from tests.unit.test_betse_normal_ecm_molecule_event_owner import explicit_inputs, graph
from tests.unit.test_betse_normal_ecm_molecule_membrane_event_checkpoint import sim_template
from validation.betse import betse_normal_ecm_molecule_checkpoint as preparation
from validation.betse import betse_normal_ecm_molecule_event_checkpoint as validation
from validation.betse import betse_normal_ecm_molecule_periodic_checkpoint as periodic
from validation.betse.betse_normal_ecm_event_join_fixtures import finalize_fields

PROPERTIES = {"frequency": -3.75, "phase": -0.25}


@pytest.fixture(autouse=True)
def forbid_actual_periodic(no_actual_execution):
    codes = {
        authority.FACTORY_CODE,
        authority.FINALIZER_CODE,
        authority.callback_code(),
        authority.sweep.FACTORY_CODE,
        authority.sweep.callback_code(),
        time_laws.periodic_program.__code__,
        time_laws.sweep_program.__code__,
        time_laws.evaluate.__code__,
        literal.prepared_callback.__code__,
    }
    codes.update(c for c in literal.prepared_callback.__code__.co_consts if type(c) is CodeType)
    codes.update(
        lifecycle.setup.constant_callback_code(s) for s in lifecycle.setup.CONSTANT_SUFFIXES
    )
    previous = sys.getprofile()

    def guard(frame, event, arg):
        if event == "call" and frame.f_code in codes:
            no_actual_execution.append("actual factory/callback/finalizer/time law")
            raise AssertionError("Actual periodic execution forbidden")

    sys.setprofile(guard)
    try:
        yield codes
    finally:
        sys.setprofile(previous)


def source_template():
    raw = sim_template()
    raw["sim_phase"]["setup"]["global_options"] = dict.fromkeys(
        raw["sim_phase"]["setup"]["global_options"], 0
    )
    raw["sim_phase"]["setup"]["scheduled_options"] = dict.fromkeys(
        raw["sim_phase"]["setup"]["scheduled_options"], 0
    )
    raw["sim_phase"]["flags"] = dict(_run_sim=True)
    raw["source_setup"] = dict(
        provenance="Unowned synthetic configuration; not native parsed",
        frequency_sweep={"f start": 500.0, "f stop": 1500.0, "f slope": None},
    )
    return raw


def manufactured(scenario="periodic_combined"):
    configured = periodic.configure_sim(source_template(), scenario, periodic_properties=PROPERTIES)
    setup = configured["source_setup"]["periodic_event_configuration"]
    owner = dict(
        global_options=setup["global_options"],
        scheduled_options=setup["scheduled_options"],
        handler_fields=finalize_fields(
            setup["global_options"], setup["scheduled_options"], setup["maps"], 4
        ),
        callbacks={
            suffix: dict(
                source_function=row[5],
                source_scalar=1,
                dynamic=dict(
                    kind="periodic", **PROPERTIES, provenance="Actual SIM periodic finalizer result"
                )
                if row[5] == "periodic"
                else dict(kind="constant"),
                provenance="Unowned manufactured metadata; no source admission",
            )
            for key, suffix in authority.MEMBRANE_KEYS.items()
            if (row := setup["scheduled_options"][key]) != 0
        },
    )
    g = graph()
    initial_early = run.ions.data(g.early)
    initial_early["owner"].update(owner)
    g.early = run.ions.freeze(initial_early)
    raw = run.ions.data(g.source.inputs)
    raw["sim_phase"]["setup"] = copy.deepcopy(configured["sim_phase"]["setup"])
    raw["sim_phase"]["time_profile"] = copy.deepcopy(configured["sim_phase"]["time_profile"])
    raw["sim_phase"]["flags"] = copy.deepcopy(configured["sim_phase"]["flags"])
    raw["source_setup"].update(
        periodic_properties=copy.deepcopy(PROPERTIES),
        periodic_event_configuration=copy.deepcopy(setup),
        periodic_preparation_route=periodic.ROUTE,
        provenance=configured["source_setup"]["provenance"],
    )
    g.source = replace(g.source, inputs=run.ions.freeze(raw))
    g.source = replace(g.source, identity=run.ions.digest(lifecycle.binding_record(g.source)))
    g.final["setup"] = copy.deepcopy(configured["sim_phase"]["setup"])
    object.__setattr__(g.phase, "inputs_raw", run.ions.freeze(g.final))
    p = SimpleNamespace(
        _run_sim=True,
        sim_time_total=3.25,
        periodic_properties=copy.deepcopy(PROPERTIES),
        scheduled_options=setup["scheduled_options"],
    )
    phase = SimpleNamespace(p=p, cells=object())
    actual = SimpleNamespace(**owner["handler_fields"], **setup["maps"])
    trace = authority.FactoryObservation(actual, phase, PROPERTIES, binding=g.source)
    g.configured, g.p, g.live_phase, g.actual, g.trace = configured, p, phase, actual, trace
    return g


def callback(value):
    return FunctionType(
        authority.callback_code(), vars(authority.source), closure=(CellType(value.p),)
    )


def call_frame(value, suffix):
    return SimpleNamespace(
        f_code=authority.FACTORY_CODE,
        f_globals=vars(authority.source),
        f_locals=dict(
            p=value.p, cells=value.live_phase.cells, pc=getattr(value.actual, "targets_" + suffix)
        ),
        f_back=SimpleNamespace(
            f_code=authority.FINALIZER_CODE,
            f_globals=vars(authority.source),
            f_locals=dict(self=value.actual, phase=value.live_phase),
        ),
    )


def returns(value):
    for _, suffix in value.trace.selected:
        frame = call_frame(value, suffix)
        value.trace.observe(frame, "call", None)
        function = callback(value)
        setattr(value.actual, "dyna_" + suffix, function)
        setattr(value.actual, "scalar_" + suffix, 1)
        value.trace.observe(frame, "return", (1, function))
    value.trace.finish()
    return value


def reseal(value, early):
    value.early = run.ions.freeze(early)
    value.pub = bridge.publish(
        value.source, value.completed, value.early, value.final, value.mechanical, value.profiles
    )
    value.receipt["event_finalization"].update(
        source_fields=value.early, owner_publication=value.pub
    )
    value.receipt["source_setup"].update(
        event_finalized=value.early, event_owner_published=value.pub
    )
    object.__setattr__(value.entry, "binding_identity", value.source.identity)
    value.component = events.Binding(
        value.source,
        value.entry,
        dict(event_owner=run.ions.data(value.pub.owner)),
        "unowned metadata binding",
    )


def published(scenario="periodic_combined"):
    value = returns(manufactured(scenario))
    early = run.ions.data(value.early)
    early.update(
        periodic_callback_authority=value.trace.records,
        periodic_properties_after=copy.deepcopy(PROPERTIES),
    )
    constants = {
        s: lifecycle.setup.constant_callback_record(s)
        for s, row in early["owner"]["callbacks"].items()
        if row["source_function"] == "None"
    }
    if constants:
        early["constant_callback_authority"] = constants
    reseal(value, early)
    return value


def test_exact_pinned_periodic_factory_and_native_configuration_path(tmp_path):
    root = Path("/mnt/workspaces/Cells/betse-v1.5.0")
    for name, expected in authority.NATIVE_PINS.items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == expected
    native = ast.parse((root / "betse/science/math/modulate.py").read_bytes())
    adopted = ast.parse(Path(authority.source.__file__).read_bytes())

    def function(tree):
        return next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "periodic")

    assert ast.dump(function(native), include_attributes=False) == ast.dump(
        function(adopted), include_attributes=False
    )
    parameters = ast.parse((root / "betse/science/parameters.py").read_bytes())
    assignments = [
        ast.unparse(n)
        for n in ast.walk(parameters)
        if isinstance(n, ast.Assign)
        and any(ast.unparse(t).startswith("self.periodic_properties[") for t in n.targets)
    ]
    assert len(assignments) == 2
    assert all(
        "self._conf['modulator function properties']['periodic']" in n and "float(" in n
        for n in assignments
    )
    assert authority.source.mod.periodic is authority.FACTORY
    assert authority.callback_code().co_freevars == ("p",)
    (tmp_path / "native-literal-pins.json").write_text(
        json.dumps(
            dict(
                pins=authority.NATIVE_PINS,
                factory="periodic",
                configuration_path=authority.NATIVE_CONFIGURATION_PATH,
                executed=False,
            )
        )
    )


def test_SIM_common_validator_retains_every_original_guard_except_periodic_whitelist():
    authority.common_guard_identity()
    old = next(
        n
        for n in ast.parse(Path(authority.common.__file__).read_bytes()).body
        if isinstance(n, ast.FunctionDef) and n.name == "validate"
    )
    new = next(
        n
        for n in ast.parse(Path(authority.__file__).read_bytes()).body
        if isinstance(n, ast.FunctionDef) and n.name == "_validate_SIM_periodic_setup"
    )
    new.name = old.name
    changed = 0
    for node in ast.walk(new):
        if isinstance(node, ast.Tuple) and [
            x.value for x in node.elts if isinstance(x, ast.Constant)
        ] == ["None", "f_sweep", "periodic"]:
            node.elts = node.elts[:2]
            changed += 1
    assert changed == 1 and ast.dump(old, include_attributes=False) == ast.dump(
        new, include_attributes=False
    )


@pytest.mark.parametrize("scenario", periodic.SCENARIOS)
def test_declared_configuration_preserves_original_inputs_and_never_supplies_callback_authority(
    scenario,
):
    original = source_template()
    before = copy.deepcopy(original)
    value = periodic.configure_sim(original, scenario, periodic_properties=PROPERTIES)
    assert original == before
    assert value["source_setup"]["periodic_properties"] == PROPERTIES
    assert value["source_setup"]["frequency_sweep"] == before["source_setup"]["frequency_sweep"]
    assert value["source_setup"]["provenance"].startswith(before["source_setup"]["provenance"])
    assert value["sim_phase"]["setup"]["maps"] == before["sim_phase"]["setup"]["maps"]
    assert (
        "callbacks" not in value["sim_phase"]["setup"]
        and "periodic_callback_authority" not in value["sim_phase"]["setup"]
    )


@pytest.mark.parametrize(
    "properties",
    [
        None,
        {},
        dict(frequency=1.0),
        dict(frequency=1.0, phase=0.0, extra=1),
        dict(frequency=True, phase=0.0),
        dict(frequency=1, phase=0.0),
        dict(frequency=np.float64(1), phase=0.0),
        dict(frequency=np.array(1.0), phase=0.0),
        dict(frequency=float("inf"), phase=0.0),
    ],
)
def test_missing_foreign_or_ill_typed_periodic_configuration_has_no_default(properties):
    with pytest.raises(ValueError):
        authority.properties(properties)


@pytest.mark.parametrize(
    "fault", ["missing-properties", "unused-properties", "pressure", "sweep-mix"]
)
def test_periodic_source_configuration_cannot_be_inferred_or_widened(fault):
    raw = periodic.configure_sim(
        source_template(), "periodic_Na_mem", periodic_properties=PROPERTIES
    )
    if fault == "missing-properties":
        del raw["source_setup"]["periodic_properties"]
    elif fault == "unused-properties":
        raw["source_setup"]["periodic_event_configuration"]["scheduled_options"]["Na_mem"] = 0
    elif fault == "pressure":
        raw["source_setup"]["periodic_event_configuration"]["scheduled_options"]["pressure"] = [
            0.0,
            1.0,
            0.1,
            1.0,
            ["all"],
            "periodic",
        ]
    else:
        raw["source_setup"]["periodic_event_configuration"]["scheduled_options"]["K_mem"] = [
            0.0,
            1.0,
            0.1,
            1.0,
            ["all"],
            "f_sweep",
        ]
    with pytest.raises(ValueError):
        authority.configuration(raw)


@pytest.mark.parametrize(
    "fault", ["code", "globals", "p", "float", "array", "defaults", "kwdefaults"]
)
def test_actual_callback_code_parameter_closure_and_scalar_are_exact(fault):
    value = manufactured("periodic_Na_mem")
    function = callback(value)
    scalar = 1
    if fault == "code":

        def function(t):
            return 1
    elif fault == "globals":
        function = FunctionType(authority.callback_code(), {}, closure=function.__closure__)
    elif fault == "p":
        function = FunctionType(
            authority.callback_code(),
            vars(authority.source),
            closure=(CellType(copy.copy(value.p)),),
        )
    elif fault == "float":
        scalar = 1.0
    elif fault == "array":
        scalar = np.array(1)
    elif fault == "defaults":
        function.__defaults__ = (1,)
    else:
        function.__kwdefaults__ = {"t": 1}
    with pytest.raises(ValueError):
        authority.inspect_callback(function, scalar, value.p)


@pytest.mark.parametrize(
    "fault", ["p", "pc", "caller", "omitted", "duplicate", "mapping-replaced", "value-changed"]
)
def test_factory_owner_order_parameter_mapping_and_failed_prefixes_are_retained(fault):
    value = manufactured("periodic_Na_mem")
    frame = call_frame(value, "Namem")
    if fault in ("p", "pc"):
        frame.f_locals[fault] = object()
    elif fault == "caller":
        frame.f_back.f_code = (lambda: None).__code__
    elif fault == "mapping-replaced":
        value.p.periodic_properties = copy.deepcopy(PROPERTIES)
    elif fault == "value-changed":
        value.p.periodic_properties["phase"] += 1.0
    if fault in ("p", "pc", "caller", "mapping-replaced", "value-changed"):
        with pytest.raises(ValueError):
            value.trace.observe(frame, "call", None)
    else:
        value.trace.observe(frame, "call", None)
        with pytest.raises(ValueError):
            if fault == "duplicate":
                value.trace.observe(frame, "call", None)
            else:
                value.trace.finish()
    assert not value.trace.data()["complete"] and value.trace.data()["factory_returns"] == 0


@pytest.mark.parametrize("scenario", periodic.SCENARIOS)
def test_actual_finalizer_observation_is_required_and_published_owner_retained(scenario):
    value = published(scenario)
    run.composition.event_scope(value.component)
    before = checkpoint.codec.fingerprint((value.source, value.early, value.pub))
    raw = periodic.declaration(value.source, value.entry, scenario)
    assert bridge.same(raw["event_owner"], value.pub.owner)
    assert checkpoint.codec.fingerprint((value.source, value.early, value.pub)) == before


@pytest.mark.parametrize(
    "fault",
    [
        "missing",
        "source",
        "binding",
        "configuration",
        "closure",
        "sequence",
        "target",
        "dynamic",
        "epoch",
    ],
)
def test_resealed_source_callback_authority_and_program_drift_refuse(fault):
    value = published()
    early = run.ions.data(value.early)
    row = early["periodic_callback_authority"]["Kmem"]
    if fault == "missing":
        del early["periodic_callback_authority"]
    elif fault == "dynamic":
        value.component.raw["event_owner"]["callbacks"]["Kmem"]["dynamic"]["phase"] += 1.0
    else:
        if fault == "source":
            row["source"]["source_sha256"] = "0" * 64
        elif fault == "binding":
            row["source_binding_identity"] = "foreign"
        elif fault == "configuration":
            row["before"]["frequency"] += 1.0
        elif fault == "closure":
            row["closure"]["retained_parameter_mapping"] = False
        elif fault == "sequence":
            row["sequence"] = 0
        elif fault == "target":
            row["targets"].reverse()
        else:
            row["source_phase"] = "INIT"
        row["identity"] = run.ions.digest({k: v for k, v in row.items() if k != "identity"})
    if fault != "dynamic":
        reseal(value, early)
    with pytest.raises(ValueError):
        run.composition.event_scope(value.component)


@pytest.mark.parametrize(
    "scenario", ["periodic_Na_mem", "periodic_mixed_constant", "periodic_duplicate_targets"]
)
def test_closed_graph_transport_keeps_original_later_epochs_and_input_aliases(tmp_path, scenario):
    value = published(scenario)
    graph = dict(
        component=value.component,
        early=value.early,
        publication=value.pub,
        inputs=value.source.event_owner_inputs,
    )
    encoder = checkpoint.codec.Encoder()
    tree = encoder.capture(graph)
    encoder.write(tmp_path, tree)
    decoded = checkpoint.codec.decode(tree, (tmp_path / "arrays.npz").read_bytes())
    assert checkpoint.codec.fingerprint(decoded) == checkpoint.codec.fingerprint(graph)
    assert (
        decoded["component"].source_binding.event_owner_inputs
        is decoded["inputs"]
        is decoded["publication"].inputs
    )
    assert decoded["publication"].event_finalized is decoded["early"]
    assert (
        decoded["component"].base.setup_receipt["event_finalization"]["owner_publication"]
        is decoded["publication"]
    )
    run.composition.event_scope(decoded["component"])


@pytest.mark.parametrize("flag", [None, *validation.RELEASES])
def test_periodic_route_remains_behind_both_existing_gates(tmp_path, monkeypatch, flag):
    if flag:
        monkeypatch.setenv(flag, "1")
    with pytest.raises(ValueError, match="both existing Root releases"):
        validation.actual_continuity(
            tmp_path / "held",
            scenario="periodic_Na_mem",
            cut=1,
            preparation_route=periodic.ROUTE,
            event_owner_inputs=explicit_inputs(),
            periodic_properties=PROPERTIES,
        )
    assert not (tmp_path / "held").exists()


@pytest.mark.parametrize("route", ["legacy", "finalized_sweep", "published_global"])
def test_periodic_configuration_requires_its_separate_route(tmp_path, monkeypatch, route):
    for flag in validation.RELEASES:
        monkeypatch.setenv(flag, "1")
    with pytest.raises(ValueError):
        validation.actual_continuity(
            tmp_path / "refused",
            scenario="temperature",
            cut=1,
            preparation_route=route,
            periodic_properties=PROPERTIES,
        )
    assert not (tmp_path / "refused").exists()


@pytest.mark.parametrize(
    "fault", [None, "INIT", "voltage", "map", "profile", "row", "rng", "validator-replaced"]
)
def test_SIM_only_common_guard_checks_are_not_skipped_or_disguised(monkeypatch, fault):
    value = manufactured("periodic_Na_mem")
    raw = copy.deepcopy(value.configured["source_setup"]["periodic_event_configuration"])
    raw.update(
        kind="cells.supplied_pre_INIT_setup@1",
        provenance="Unowned SIM validation control",
        receipts=dict(
            tissue_profiles="supplied", init_core="supplied", initializer_cache="supplied"
        ),
        numpy_rng=dict(synthetic="not actual RNG"),
        python_rng=dict(synthetic="not actual RNG"),
        channel_noise_level=0.0,
        frequency_sweep={"f start": 500.0, "f stop": 1500.0, "f slope": None},
        dynamic_noise=dict(enabled=False, level=0.0),
    )
    calls = []

    def stream(saved):
        calls.append(saved)
        if fault == "rng":
            raise ValueError("Synthetic RNG validation refusal")
        return object()

    monkeypatch.setattr(authority.perturbations, "native_stream_from_manifest", stream)
    monkeypatch.setattr(authority.common, "python_restore", stream)
    base = SimpleNamespace(
        material_binding=SimpleNamespace(
            geometry_binding=SimpleNamespace(
                current_binding=SimpleNamespace(
                    membrane_ids=tuple(range(4)), cell_ids=tuple(range(2))
                ),
                geometry=SimpleNamespace(grid_points_m=tuple(range(4))),
            )
        ),
        inputs=dict(initial=dict(voltage_V=np.zeros(4))),
    )
    if fault == "voltage":
        base.inputs["initial"]["voltage_V"][0] = 1.0
    elif fault == "map":
        raw["maps"]["tissue_target_inds"]["all"] = [4]
    elif fault == "profile":
        raw["scheduled_options"]["Na_mem"][4] = ["foreign"]
    elif fault == "row":
        raw["scheduled_options"]["Na_mem"][0] = float("inf")
    elif fault == "validator-replaced":
        monkeypatch.setattr(authority.common, "validate", lambda *a: None)
    before = copy.deepcopy(raw)
    if fault is None:
        authority.validate_SIM_setup(
            raw, base, phase="SIM", run_sim=True, preparation_route=periodic.ROUTE
        )
        assert (
            len(calls) == 2
            and raw == before
            and raw["scheduled_options"]["Na_mem"][5] == "periodic"
        )
    else:
        with pytest.raises(ValueError):
            authority.validate_SIM_setup(
                raw,
                base,
                phase="INIT" if fault == "INIT" else "SIM",
                run_sim=fault != "INIT",
                preparation_route=periodic.ROUTE,
            )


@pytest.mark.parametrize("outcome", ["raise", "raise-after-context-change", "None", "tuple"])
def test_real_synthetic_profile_preserves_factory_cause_None_refusal_and_profiler(
    tmp_path, monkeypatch, outcome
):
    value = manufactured("periodic_Na_mem")
    native_code = authority.callback_code()
    module = sys.modules[__name__]
    function = FunctionType(native_code, vars(module), closure=(CellType(value.p),))
    primary = RuntimeError("Synthetic periodic factory failure")
    cause = LookupError("Original synthetic cause")

    def factory(pc, cells, p):
        if outcome.startswith("raise"):
            if outcome.endswith("context-change"):
                p.periodic_properties["phase"] += 1.0
            raise primary from cause
        return (1, function) if outcome == "tuple" else None

    def finalizer(self, phase):
        result = factory(self.targets_Namem, phase.cells, phase.p)
        if result is not None:
            self.scalar_Namem, self.dyna_Namem = result

    monkeypatch.setattr(authority, "FACTORY_CODE", factory.__code__)
    monkeypatch.setattr(authority, "FINALIZER_CODE", finalizer.__code__)
    monkeypatch.setattr(authority, "source", module)
    monkeypatch.setattr(authority, "source_identity", lambda: dict(unowned_synthetic=True))
    monkeypatch.setattr(authority, "callback_code", lambda: native_code)
    previous = sys.getprofile()
    seen = []

    def chained(frame, event, arg):
        if previous is not None:
            previous(frame, event, arg)
        if frame.f_code is factory.__code__ and event in ("call", "return"):
            seen.append(dict(event=event, arg_is_None=arg is None))

    sys.setprofile(chained)
    try:
        if outcome.startswith("raise"):
            with pytest.raises(RuntimeError) as error:
                with value.trace:
                    finalizer(value.actual, value.live_phase)
            assert error.value is primary and error.value.__cause__ is cause
        elif outcome == "None":
            with pytest.raises(
                ValueError, match="Missing/omitted periodic factory return"
            ) as error:
                with value.trace:
                    finalizer(value.actual, value.live_phase)
            codes = []
            tb = error.value.__traceback__
            while tb is not None:
                codes.append(tb.tb_frame.f_code)
                tb = tb.tb_next
            assert (
                authority.FactoryObservation.finish.__code__ in codes
                and authority.FactoryObservation.observe.__code__ not in codes
            )
        else:
            with value.trace:
                finalizer(value.actual, value.live_phase)
            assert value.trace.complete and value.actual.dyna_Namem is function
        assert sys.getprofile() is chained
    finally:
        sys.setprofile(previous)
    data = value.trace.data()
    assert seen == [
        dict(event="call", arg_is_None=True),
        dict(event="return", arg_is_None=outcome != "tuple"),
    ]
    assert data["complete"] is (outcome == "tuple") and data["factory_returns"] == int(
        outcome == "tuple"
    )
    (tmp_path / "periodic-profile-control.json").write_text(
        json.dumps(
            dict(
                outcome=outcome,
                observed_synthetic_events=seen,
                primary_identity_and_cause_preserved=True if outcome.startswith("raise") else None,
                observation=data,
                parent_admission=False,
                scientific_acceptance=False,
            )
        )
    )


@pytest.mark.parametrize("fault", ["source-function", "lookup", "code", "numpy"])
def test_periodic_factory_source_identity_refuses_live_substitution(monkeypatch, fault):
    def foreign(pc, cells, p):
        raise AssertionError("Never execute foreign factory")

    if fault == "source-function":
        monkeypatch.setattr(authority.source, "periodic", foreign)
    elif fault == "lookup":
        monkeypatch.setattr(authority.source.mod, "periodic", foreign)
    elif fault == "code":
        monkeypatch.setattr(authority.FACTORY, "__code__", foreign.__code__)
    else:
        monkeypatch.setattr(authority.source, "np", object())
    with pytest.raises(ValueError, match="Foreign periodic factory"):
        authority.source_identity()


@pytest.mark.parametrize(
    "fault",
    [
        "missing-Inputs",
        "dictionary-Inputs",
        "foreign-INIT",
        "foreign-geometry",
        "missing-parameters",
    ],
)
def test_preparation_refuses_missing_foreign_authority_before_complete_INIT(tmp_path, fault):
    value = manufactured("periodic_Na_mem")
    supplied = explicit_inputs()
    configured = PROPERTIES
    if fault == "missing-Inputs":
        supplied = None
    elif fault == "dictionary-Inputs":
        supplied = run.ions.data(supplied)
    elif fault == "foreign-INIT":
        supplied = replace(supplied, source_INIT_binding_identity="foreign")
    elif fault == "foreign-geometry":
        supplied = replace(supplied, source_geometry_binding_identity="foreign")
    else:
        configured = None
    attempts = []
    with pytest.raises(ValueError):
        periodic.prepare_sim(
            tmp_path / "SIM",
            plain_record(run.Binding, composition=value.completed.binding),
            "unowned INIT",
            attempts,
            scenario="periodic_Na_mem",
            event_owner_inputs=supplied,
            periodic_properties=configured,
        )
    assert attempts[-1]["status"] == "refused" and not any(
        r["operation"] == "actual-complete-INIT" for r in attempts
    )
    assert (tmp_path / "SIM" / attempts[-1]["operation"] / "manifest.json").is_file()


def test_preparation_keeps_actual_input_instance_original_config_and_transition_cause(
    tmp_path, monkeypatch
):
    value = manufactured("periodic_Na_mem")
    supplied = explicit_inputs()
    original = source_template()
    before = copy.deepcopy(original)
    monkeypatch.setattr(
        run,
        "complete_INIT",
        lambda *a: plain_record(run.CompletedInitRun, complete_init="unowned complete INIT"),
    )
    monkeypatch.setattr(preparation.fixtures, "sim_inputs", lambda *a: original)
    seen = []

    def bind(raw, **kwargs):
        assert kwargs["event_owner_inputs"] is supplied
        assert raw["source_setup"]["periodic_properties"] == PROPERTIES
        assert (
            raw["source_setup"]["periodic_event_configuration"]["scheduled_options"]["Na_mem"][5]
            == "periodic"
        )
        assert all(row == 0 for row in raw["sim_phase"]["setup"]["scheduled_options"].values())
        seen.append(raw)
        return lifecycle.Binding(
            run.ions.freeze(raw), "INIT-binding", None, "unowned component", supplied
        )

    monkeypatch.setattr(lifecycle, "bind", bind)
    monkeypatch.setattr(
        preparation.fixtures, "declaration", lambda *a: dict(synthetic="unowned declaration")
    )
    primary = RuntimeError("synthetic pre-transition refusal")
    cause = LookupError("source synthetic cause")

    def transition(*args, **kwargs):
        assert args[2].event_owner_inputs is supplied
        raise primary from cause

    monkeypatch.setattr(run, "transition", transition)
    attempts = []
    with pytest.raises(RuntimeError) as error:
        periodic.prepare_sim(
            tmp_path / "SIM",
            plain_record(run.Binding, composition=value.completed.binding),
            "unowned INIT",
            attempts,
            scenario="periodic_Na_mem",
            event_owner_inputs=supplied,
            periodic_properties=PROPERTIES,
        )
    assert (
        error.value is primary
        and error.value.__cause__ is cause
        and original == before
        and len(seen) == 1
    )
    assert (tmp_path / "SIM/actual-INIT-to-SIM/manifest.json").is_file() and attempts[-1][
        "status"
    ] == "refused"


@pytest.mark.parametrize("missing", ["parameters", "Inputs"])
def test_dispatcher_retains_missing_authority_before_INIT_work(
    tmp_path, monkeypatch, forbid_actual_periodic, no_actual_execution, missing
):
    from validation.betse.betse_normal_ecm_molecule_handoff_run_plugin import Calls

    original = Calls.observe

    def guarded(self, frame, event, arg):
        if event == "call" and frame.f_code in forbid_actual_periodic:
            no_actual_execution.append("actual periodic during dispatcher control")
            raise AssertionError("Actual periodic forbidden")
        return original(self, frame, event, arg)

    monkeypatch.setattr(Calls, "observe", guarded)
    for flag in validation.RELEASES:
        monkeypatch.setenv(flag, "1")
    before = sys.getprofile()
    sys.setprofile(None)
    try:
        with pytest.raises(ValueError):
            validation.actual_continuity(
                tmp_path / "refused",
                scenario="periodic_Na_mem",
                cut=1,
                preparation_route=periodic.ROUTE,
                event_owner_inputs=None if missing == "Inputs" else explicit_inputs(),
                periodic_properties=None if missing == "parameters" else PROPERTIES,
            )
    finally:
        sys.setprofile(before)
    assert (tmp_path / "refused/failure/manifest.json").is_file() and not (
        tmp_path / "refused/result.json"
    ).exists()
    value = json.loads((tmp_path / "refused/attempts.json").read_bytes())
    assert (
        value["attempts"][-1]["status"] == "refused"
        and value["invocation_accounting"]["profile_intact"] is True
    )


@pytest.mark.parametrize("scenario", ["periodic_Na_mem", "periodic_mixed_constant"])
def test_finalize_owner_cannot_hydrate_missing_periodic_factory_trace(scenario):
    value = returns(manufactured(scenario))
    template = run.ions.data(value.early["owner"])
    for key, suffix in authority.MEMBRANE_KEYS.items():
        row = template["scheduled_options"][key]
        if row != 0 and row[5] == "None":
            setattr(
                value.actual,
                "dyna_" + suffix,
                FunctionType(
                    lifecycle.setup.constant_callback_code(suffix), vars(authority.source)
                ),
            )
            setattr(value.actual, "scalar_" + suffix, 1)
    with pytest.raises(ValueError, match="Missing actual periodic factory"):
        lifecycle.setup.finalized_owner(template, value.actual, value.p)
    owner = lifecycle.setup.finalized_owner(
        template, value.actual, value.p, periodic_observation=value.trace
    )
    assert owner["callbacks"]["Namem"]["dynamic"] == dict(
        kind="periodic", **PROPERTIES, provenance="Actual SIM periodic finalizer result"
    )


def test_periodic_runtime_observer_keeps_global_groups_and_qualified_program_separate(tmp_path):
    class Base:
        def __init__(self, stream):
            pass

        def observe(self, *args):
            pass

        def stop(self):
            return dict(counts={})

    observed = periodic.observer(Base, io.StringIO(), literal.__file__, tmp_path)
    source = periodic.source_order(literal.__file__)
    program = plain_record(
        time_laws.Program,
        kind="periodic",
        frequency_Hz=PROPERTIES["frequency"],
        phase_rad=PROPERTIES["phase"],
        slope_Hz_s=0.0,
        automatic_slope=False,
        requested_stop_Hz=None,
        original_duration_s=None,
        provenance="Actual SIM periodic finalizer result",
        identity="",
    )
    object.__setattr__(program, "identity", time_laws.record(program)["identity"])
    code = next(
        c
        for c in literal.prepared_callback.__code__.co_consts
        if type(c) is CodeType and c.co_firstlineno == source["periodic_callback_line"]
    )
    function = FunctionType(code, vars(literal), closure=(CellType(program),))
    handler = SimpleNamespace(dyna_Namem=function, scalar_Namem=1, targets_Namem=[2, 0, 2, 0])
    outer = SimpleNamespace(
        f_code=literal.TissueHandler._fire_events_tissue.__code__,
        f_globals=vars(literal),
        f_locals=dict(t=0.0, self=handler),
        f_lineno=source["branches"][0]["line"] + 1,
        f_back=None,
    )
    frame = SimpleNamespace(
        f_code=code, f_globals=vars(literal), f_locals=dict(t=0.0, program=program), f_back=outer
    )
    global_frame = SimpleNamespace(
        f_code=literal.TissueHandler._fire_events_global.__code__,
        f_globals=vars(literal),
        f_locals=dict(t=0.0),
        f_back=None,
    )
    for event in ("call", "return"):
        observed.observe(global_frame, event, None)
    observed.observe(outer, "call", None)
    observed.observe(frame, "call", None)
    observed.observe(frame, "return", np.float64(0.4))
    observed.observe(outer, "return", None)
    result = observed.stop()
    assert len(result["periodic_dispatches"]) == len(result["global_dispatches"]) == 1
    row = result["periodic_dispatches"][0]["events"][0]
    assert (
        row["returned"]
        and row["program"]["frequency"] == PROPERTIES["frequency"]
        and row["program"]["phase"] == PROPERTIES["phase"]
    )
    assert observed.periodic_stream.closed and observed.pulse_stream.closed


def call_observations():
    value = published("periodic_mixed_constant")
    owner = value.component.raw["event_owner"]
    binding = periodic.source_order(literal.__file__)
    labels = [0.0, 1.5, 3.0]
    targets = {
        k: owner["handler_fields"]["targets_" + s]
        for k, s in authority.MEMBRANE_KEYS.items()
        if owner["scheduled_options"][k] != 0
    }
    anchor = dict(
        labels=labels,
        ion_ids=["Na", "K", "Cl", "Ca"],
        targets=targets,
        scheduled_options=owner["scheduled_options"],
        callbacks=owner["callbacks"],
    )
    groups = []
    for index in range(6):
        t = labels[index % 3]
        rows = []
        for key in targets:
            configured = owner["scheduled_options"][key]
            kind = "periodic" if configured[5] == "periodic" else "constant"
            row = dict(
                key=key,
                operation="callback",
                returned=True,
                parameters=[t],
                kind=kind,
                scalar=1,
                targets=targets[key],
                source_sha256=binding["sha256"],
                callback_line=binding[kind + "_callback_line"],
                runtime_code_matches=True,
                value=0.4 if kind == "periodic" else 1.0,
                value_type="float64" if kind == "periodic" else "int",
                value_shape=[],
                value_dtype="<f8" if kind == "periodic" else None,
            )
            if kind == "periodic":
                dynamic = owner["callbacks"][authority.MEMBRANE_KEYS[key]]["dynamic"]
                row["program"] = dict(
                    frequency=dynamic["frequency"],
                    phase=dynamic["phase"],
                    provenance=dynamic["provenance"],
                )
            rows.extend(
                [
                    row,
                    dict(
                        key=key,
                        operation="pulse",
                        returned=True,
                        value=0.5,
                        parameters=[t, *configured[:3]],
                    ),
                ]
            )
        groups.append(dict(label=t, exited=True, events=rows))
    return dict(
        periodic_dispatches=groups,
        periodic_source_binding=binding,
        periodic_profile_complete=True,
        counts={
            authority.source.__name__ + ".periodic": 37,
            literal.__name__ + ".prepared_callback": 77,
            time_laws.__name__ + ".periodic_program": 99,
        },
    ), anchor


@pytest.mark.parametrize(
    "fault",
    [
        None,
        "duplicate",
        "omitted",
        "order",
        "clock",
        "target",
        "frequency",
        "phase",
        "provenance",
        "shape",
        "unwind",
        "factory-count",
    ],
)
def test_runtime_comparison_preserves_order_parameters_clock_and_nested_work(fault):
    accounting, anchor = call_observations()
    group = accounting["periodic_dispatches"][0]
    row = group["events"][0]
    if fault == "duplicate":
        group["events"].append(copy.deepcopy(row))
    elif fault == "omitted":
        group["events"].pop()
    elif fault == "order":
        group["events"].reverse()
    elif fault == "clock":
        group["label"] += 0.1
    elif fault == "target":
        row["targets"] = [1]
    elif fault in ("frequency", "phase"):
        row["program"][fault] += 1.0
    elif fault == "provenance":
        row["program"]["provenance"] = "foreign"
    elif fault == "shape":
        row["value_shape"] = [1]
    elif fault == "unwind":
        row["returned"] = False
    elif fault == "factory-count":
        accounting["counts"] = {}
    if fault is None:
        result = periodic.check_calls(accounting, anchor)
        assert (
            result["independent_cases"] == 0
            and result["factory_recreation_and_nested_work"][
                authority.source.__name__ + ".periodic"
            ]
            == 37
        )
    else:
        with pytest.raises(ValueError):
            periodic.check_calls(accounting, anchor)


@pytest.mark.parametrize("kind", ["function", "code", "cell", "observer"])
def test_closed_codec_refuses_executable_or_live_periodic_ownership(kind):
    value = manufactured("periodic_Na_mem")
    function = callback(value)
    payload = {
        "function": function,
        "code": function.__code__,
        "cell": function.__closure__[0],
        "observer": value.trace,
    }[kind]
    with pytest.raises(ValueError):
        checkpoint.codec.Encoder().capture(payload)


def test_periodic_streams_close_and_preserve_primary_accounting_error(tmp_path):
    primary = OSError("synthetic accounting failure")

    class Base:
        def __init__(self, stream):
            pass

        def observe(self, *args):
            pass

        def stop(self):
            raise primary

    observed = periodic.observer(Base, io.StringIO(), literal.__file__, tmp_path)
    with pytest.raises(OSError) as error:
        observed.stop()
    assert (
        error.value is primary and observed.periodic_stream.closed and observed.pulse_stream.closed
    )


@pytest.mark.parametrize(
    "phase_name,function",
    [
        ("INIT", "None"),
        ("INIT", "f_sweep"),
        ("INIT", "periodic"),
        ("SIM", "None"),
        ("SIM", "f_sweep"),
    ],
)
def test_original_material_setup_validator_routing_is_preserved(phase_name, function):
    """Execute just the unchanged routing AST; no phase/model/RNG work."""
    phase_module = lifecycle.init
    tree = ast.parse(Path(phase_module.__file__).read_bytes())
    bind = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "bind")
    call = next(
        n
        for n in bind.body
        if isinstance(n, ast.Expr)
        and isinstance(n.value, ast.Call)
        and ast.unparse(n.value.func) == "setup.validate"
    )
    setup = dict(scheduled_options=dict(Na_mem=[0.0, 1.0, 0.1, 0.15, ["all"], function]))
    raw = dict(time_profile=dict(phase=phase_name), setup=setup)
    base = object()
    seen = []

    def original(actual, actual_base):
        seen.append((actual, actual_base))

    namespace = dict(raw=raw, base=base, setup=SimpleNamespace(validate=original))
    exec(
        compile(
            ast.fix_missing_locations(ast.Module(body=[copy.deepcopy(call)], type_ignores=[])),
            "<owned original validator routing>",
            "exec",
        ),
        namespace,
    )
    assert (
        seen == [(setup, base)]
        and seen[0][0] is setup
        and setup["scheduled_options"]["Na_mem"][5] == function
    )


def test_original_no_intervention_owner_guards_and_material_bind_AST_are_unchanged():
    path = Path(lifecycle.init.__file__)
    original = (
        Path(
            "/mnt/workspaces/Cells/molecule-sweep-profile-unwind-repair-20261031-01/source-final/src/cells/processes"
        )
        / path.name
    )

    def functions(p):
        return {n.name: n for n in ast.parse(p.read_bytes()).body if isinstance(n, ast.FunctionDef)}

    old, new = functions(original), functions(path)
    for name in ("bind", "expected_flags", "validate_owner_scope"):
        assert ast.dump(old[name], include_attributes=False) == ast.dump(
            new[name], include_attributes=False
        )


@pytest.mark.parametrize("fault", ["INIT", "run-false", "run-int", "route", "count", "unknown"])
def test_explicit_source_finalizer_validation_refuses_wrong_phase_route_or_callback(
    monkeypatch, fault
):
    value = manufactured("periodic_combined")
    setup = copy.deepcopy(value.configured["source_setup"]["periodic_event_configuration"])
    declaration = plain_record(
        lifecycle.init.Declaration,
        calendar=SimpleNamespace(
            phase="INIT" if fault == "INIT" else "SIM", step_count=4 if fault == "count" else 3
        ),
        inputs=dict(
            flags=dict(
                _run_sim=False if fault == "run-false" else 1 if fault == "run-int" else True
            )
        ),
        base=object(),
    )
    if fault == "unknown":
        setup["scheduled_options"]["Na_mem"][5] = "unknown"
    with pytest.raises(ValueError):
        lifecycle.init.validate_periodic_finalizer_setup(
            declaration, setup, preparation_route="legacy" if fault == "route" else periodic.ROUTE
        )


@pytest.mark.parametrize("fault", ["material-event", "map", "stream", "route", "run", "phase"])
def test_distinct_source_table_preserves_material_owners_and_common_fields(fault):
    value = periodic.configure_sim(
        source_template(), "periodic_Na_mem", periodic_properties=PROPERTIES
    )
    material = value["sim_phase"]
    table = value["source_setup"]["periodic_event_configuration"]
    if fault == "material-event":
        material["setup"]["scheduled_options"]["Na_mem"] = copy.deepcopy(
            table["scheduled_options"]["Na_mem"]
        )
    elif fault == "map":
        table["maps"]["tissue_target_inds"]["all"].reverse()
    elif fault == "stream":
        table["python_rng"] = dict(foreign=True)
    elif fault == "route":
        value["source_setup"]["periodic_preparation_route"] = "legacy"
    elif fault == "run":
        material["flags"]["_run_sim"] = False
    else:
        material["time_profile"]["phase"] = "INIT"
    with pytest.raises(ValueError):
        authority.configuration(value)


def test_lowering_keeps_no_intervention_phase_and_complete_source_program_distinct():
    raw = periodic.configure_sim(
        source_template(), "periodic_Na_mem", periodic_properties=PROPERTIES
    )
    raw["sim_phase"].update(
        field=dict(unowned="field"),
        calcium=dict(unowned="calcium"),
        catalog=dict(unowned="catalog"),
        mechanics_definition={},
        mechanics_initial={},
    )
    before = copy.deepcopy(raw)
    lowered = lifecycle.setup.legacy_setup_inputs(raw)
    assert raw == before and lowered["_phase_input"]["setup"] == raw["sim_phase"]["setup"]
    assert all(v == 0 for v in lowered["_phase_input"]["setup"]["scheduled_options"].values())
    assert (
        lowered["sim_composition_template"]["event_inputs"]["event_owner"]["scheduled_options"]
        == raw["source_setup"]["periodic_event_configuration"]["scheduled_options"]
    )


@pytest.mark.parametrize("key", ["global_options", "scheduled_options"])
def test_resolver_rejects_synchronized_resealed_copies_against_actual_source_table(key):
    value = published("periodic_Na_mem")
    before = checkpoint.codec.fingerprint(value.source)
    early = run.ions.data(value.early)
    owner = run.ions.data(value.pub.owner)
    if key == "global_options":
        early["owner"][key]["T_change"] = [0.5, 2.0, 0.7, 0.01]
    else:
        early["owner"][key]["Na_mem"][3] *= 2
    owner[key] = copy.deepcopy(early["owner"][key])
    frozen = run.ions.freeze(early)
    altered = replace(
        value.pub,
        event_finalized=frozen,
        event_finalized_identity=run.ions.digest(frozen),
        owner=run.ions.freeze(owner),
    )
    altered = replace(altered, identity=run.ions.digest(bridge.record(altered)))
    value.receipt["event_finalization"].update(source_fields=frozen, owner_publication=altered)
    value.receipt["source_setup"].update(event_finalized=frozen, event_owner_published=altered)
    with pytest.raises(ValueError):
        bridge.resolve(value.source, value.entry)
    assert checkpoint.codec.fingerprint(value.source) == before
