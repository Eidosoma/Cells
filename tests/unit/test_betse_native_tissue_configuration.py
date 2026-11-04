"""Native-blocked pre-phase constructor controls; no real factory or selector work."""

import hashlib
import os
import pickle
import sys
import types
from collections.abc import Mapping, MutableSequence, Reversible, Sequence
from dataclasses import replace
from enum import Enum
from pathlib import Path
from types import SimpleNamespace

import pytest

from cells.processes import betse_native_tissue_configuration as stage
from validation.betse.betse_native_single_cell_core_synthetic import (
    SyntheticCaptureFailure,
    SyntheticSourceCause,
    SyntheticSourceFailure,
    save,
)


@pytest.fixture
def evidence(request, tmp_path):
    root = Path(os.environ.get("CELLS_TISSUE_CONFIGURATION_EVIDENCE", str(tmp_path)))
    path = root / hashlib.sha256(request.node.nodeid.encode()).hexdigest()[:20]
    path.mkdir(parents=True, exist_ok=False)
    save(
        path, "case", dict(nodeid=request.node.nodeid, synthetic_only=True, native_execution=False)
    )
    return path


def fixture(monkeypatch, *, failure=None):
    calls, errors, hooks = [], {}, {}

    class PickerType(Enum):
        ALL = 1
        INDICES = 2

    def point(name):
        calls.append(name)
        if name in hooks:
            hooks[name]()
        if name == failure:
            cause = SyntheticSourceCause("native-shaped constructor cause")
            error = SyntheticSourceFailure("synthetic " + name)
            errors.update(source=error, cause=cause)
            raise error from cause

    class Descriptor:
        def __get__(self, p, owner=None):
            point("descriptor_read")
            return p._conf["tissue profile definition"]["profiles enabled"]

    class Yaml:
        def __init__(self):
            point("yaml_construct")
            self._conf = None

        def load(self, conf):
            point("yaml_load")
            self._conf = conf

    class Item(Yaml):
        @classmethod
        def make_list(cls):
            return YamlList(item_type=cls)

        @classmethod
        def make_default(cls, *a):
            calls.append("forbidden_class_delegate")
            raise AssertionError("No raw classmethod source execution")

    class YamlList(Yaml):
        def __init__(self, item_type):
            super().__init__()
            self._item_type = item_type
            self._confs_wrap = None

        def load(self, conf):
            super().load(conf)
            self._confs_wrap = []
            for entry in conf:
                item = self._item_type()
                item.load(conf=entry)
                self._confs_wrap.append(item)

        def __iter__(self):
            return iter(self._confs_wrap)

    factory_namespace = {"YamlList": YamlList}
    exec("def make_list(cls,*a,**k): return YamlList(*a,item_type=cls,**k)", factory_namespace)
    Item.make_list = classmethod(factory_namespace["make_list"])

    class Picker:
        def __init__(self, **kwargs):
            point("picker_construct")
            vars(self).update(kwargs)

        def pick_cells(self, *a, **k):
            calls.append("forbidden_pick_delegate")
            raise AssertionError("No selector execution")

    class Profile:
        def __init__(self, **kwargs):
            point("profile_construct")
            vars(self).update(kwargs)

    def setup(context):
        context.factory_raw = SimpleNamespace(marker="actual synthetic partial factory locals")
        point("setup")
        context.descriptor = Descriptor()
        context.descriptor_occurrence = ("synthetic", 0, 1)
        context.factories = dict(
            SimConfCutListItem=Item,
            SimConfTissueDefault=Yaml,
            SimConfTissueListItem=Item,
            YamlList=YamlList,
            TissuePickerAll=Picker,
            TissuePickerIndices=Picker,
            TissueProfile=Profile,
        )
        context.symbols = dict(CellsPickerType=PickerType, BetseSimTissueException=ValueError)

    monkeypatch.setattr(stage, "_native_setup", setup)
    monkeypatch.setattr(stage.aliases, "_check_modules", lambda: None)
    namespace = dict(point=point, **vars(stage.source))
    text = """
def construct(self):
    point('p_construct')
    self.cut_profiles=SimConfCutListItem.make_list()
    self.tissue_default=SimConfTissueDefault()
    self.tissue_profiles=SimConfTissueListItem.make_list()
def load(self):
    point('p_load')
    self.cut_profiles.load(conf=self._conf['tissue profile definition']['cut profiles'])
    self.tissue_default.load(conf=self._conf['tissue profile definition']['tissue']['default'])
    self.tissue_profiles.load(conf=self._conf['tissue profile definition']['tissue']['profiles'])
def __init__(self,p):
    point('handler_init')
    self.event_cut=None
    self._event_voltage=None
    self._wound_channel=None
    self._init_tissues(p)
    self._init_cuts(p)
    self._init_events(p)
def _init_tissues(self,p):
    point('tissues')
    self.tissue_name_to_profile=OrderedDict()
    self.cell_target_inds=self.env_target_inds=self.tissue_target_inds=None
    if not p.is_tissue_profiles: return
    picker=TissuePickerAll()
    self.tissue_default=self.tissue_name_to_profile['Default']=TissueProfile(
        name='Default',picker=picker,is_gj_insular=True)
    for item in p.tissue_profiles:
        raw=item._conf
        picker=TissuePickerIndices(cells_index=raw['cell targets']['indices'])
        self.tissue_name_to_profile[raw['name']]=TissueProfile(
            name=raw['name'],picker=picker,is_gj_insular=raw['insular'])
    point('tissues_after')
def _init_cuts(self,p):
    point('cuts')
    self.cut_name_to_profile=OrderedDict()
def _init_events(self,p):
    self._init_events_global(p)
def _init_events_global(self,p):
    point('events')
"""
    exec(compile(text, "<synthetic-tissue-constructor>", "exec"), namespace)
    monkeypatch.setattr(
        stage, "_STORES", {name: namespace[name] for name in stage.PARAMETER_METHODS}
    )
    monkeypatch.setattr(stage, "_NATIVE", {name: namespace[name] for name in stage.METHODS})
    diffusion = {key: 1e-18 for key in ("Dm_Na", "Dm_K", "Dm_Cl", "Dm_Ca", "Dm_M")}
    diffusion["Dm_P"] = 0.0

    def profile(name):
        return {
            "name": name,
            "insular": True,
            "diffusion constants": dict(diffusion),
            "cell targets": {"type": "indices", "indices": [0, 1]},
            "equal": {"value": 1},
        }

    conf = {
        "cutting event": {"event happens": False},
        "apply external voltage": {"event happens": False},
        "tissue profile definition": {
            "profiles enabled": True,
            "cut profiles": [],
            "tissue": {
                "default": {"name": "Default", "diffusion constants": dict(diffusion)},
                "profiles": [
                    profile("First"),
                    profile("Second"),
                ],
            },
        },
    }
    request = stage.from_configuration(conf, law_id=stage.LAW_ID)
    return SimpleNamespace(request=request, conf=conf, calls=calls, errors=errors, hooks=hooks)


def retain(error):
    partial = error.partial or {}
    context = partial.get("context")

    def local(value, seen=None):
        seen = set() if seen is None else seen
        if value is context:
            return {"live_context_retained_in_memory": True}
        if value is None or type(value) in (str, int, bool, float, bytes):
            return value
        if id(value) in seen:
            return {"repeated_local_reference": True}
        seen.add(id(value))
        if isinstance(value, types.ModuleType):
            return {"module": value.__name__, "file": getattr(value, "__file__", None)}
        if isinstance(value, type):
            return {"class": value.__module__ + "." + value.__qualname__}
        if callable(value):
            return {"callable": getattr(value, "__qualname__", type(value).__name__)}
        if isinstance(value, dict):
            return {key: local(item, seen) for key, item in value.items()}
        if isinstance(value, (tuple, list)):
            return [local(item, seen) for item in value]
        if any(value is obj for _, obj in partial.get("raw_objects", [])):
            return value
        return {
            "type": type(value).__module__ + "." + type(value).__qualname__,
            "other_raw_object_retained_in_memory": True,
        }

    return dict(
        error=error,
        source_error=error.source_error,
        capture_error=error.capture_error,
        trial=error.trial,
        completed=partial.get("completed"),
        events=partial.get("events"),
        objects=[(name, vars(obj)) for name, obj in partial.get("raw_objects", [])],
        raw_locals={
            key: local(values) for key, values in (partial.get("raw_locals") or {}).items()
        },
        factory_raw=local(getattr(context, "factory_raw", None)),
        work=partial.get("work"),
    )


def test_software_ast_literal_stores_bodies_and_true_seed_dependencies(evidence):
    pins = stage._verify_sources()
    assert len(stage.source.SOURCE_PINS) == 272
    assert stage.source.PARAMETER_CONSTRUCTOR_LINES == (463, 464, 465)
    assert stage.source.PARAMETER_LOAD_LINES == (503, 505, 507)
    assert len(stage.METHODS) == 5 and len(stage.INVALIDATED_OWNERS) == 11
    assert not hasattr(stage.source.TissueConstructor, "init_profiles")
    save(evidence, "native-source-pins", pins)


@pytest.mark.parametrize("kind", ["mapping", "forged", "law", "oversized"])
def test_software_request_refusal_without_source_or_consumption(monkeypatch, evidence, kind):
    h = fixture(monkeypatch)
    with pytest.raises(stage.ConfigurationRejected) as caught:
        if kind == "mapping":
            stage.prepare(dict(configuration_json=h.request.configuration_json))
        elif kind == "forged":
            stage.prepare(replace(h.request))
        elif kind == "law":
            stage.from_configuration(h.conf, law_id="full_native_phase")
        else:
            stage.from_configuration({"oversized": "x" * 65536}, law_id=stage.LAW_ID)
    assert h.calls == [] and h.request not in stage._CONSUMED
    save(evidence, "request-refusal", retain(caught.value))


def test_software_complete_fresh_aliases_original_parameters_no_phase_or_mapping(
    monkeypatch, evidence
):
    h = fixture(monkeypatch)
    owner = stage.prepare(h.request)
    c = stage._authority(owner)
    p, handler = owner.parameters, owner.handler
    assert p is c.p and handler is c.handler
    assert c.completed == ["p_construct", "p_load", "__init__"]
    conf = c.configuration["tissue profile definition"]
    assert p._conf is c.configuration
    assert p.cut_profiles._conf is conf["cut profiles"]
    assert p.tissue_default._conf is conf["tissue"]["default"]
    assert p.tissue_profiles._conf is conf["tissue"]["profiles"]
    assert p.tissue_profiles._confs_wrap[0]._conf is conf["tissue"]["profiles"][0]
    assert handler.tissue_default is handler.tissue_name_to_profile["Default"]
    assert handler.cell_target_inds is None and handler.env_target_inds is None
    assert h.calls.index("p_construct") < h.calls.index("p_load") < h.calls.index("handler_init")
    for call in (
        lambda: handler._init_tissues(p),
        lambda: p.tissue_default.load({}),
        lambda: handler.tissue_default.picker.pick_cells(None, None),
        lambda: p.is_tissue_profiles,
        lambda: p.tissue_profiles._item_type.make_default(),
    ):
        with pytest.raises(stage.ConfigurationRejected, match="unavailable"):
            call()
    assert "forbidden_pick_delegate" not in h.calls
    assert "forbidden_class_delegate" not in h.calls
    with pytest.raises(stage.ConfigurationRejected, match="consumed"):
        stage.prepare(h.request)
    with pytest.raises(stage.ConfigurationRejected) as caught:
        stage.require_profile_mapping(owner, phase=object())
    assert caught.value.stage == "profile_mapping_prerequisites"
    with pytest.raises(TypeError):
        pickle.dumps(owner)
    save(evidence, "trial", owner.trial)
    save(evidence, "alias-state", dict(parameters=vars(p), handler=vars(handler)))


def test_software_profiles_disabled_is_fresh_mode_not_old_parameter_retrofit(monkeypatch, evidence):
    h = fixture(monkeypatch)
    h.conf["tissue profile definition"]["profiles enabled"] = False
    request = stage.from_configuration(h.conf, law_id=stage.LAW_ID)
    owner = stage.prepare(request)
    assert not owner.handler.tissue_name_to_profile
    assert "tissues_after" not in h.calls
    assert h.request not in stage._CONSUMED and request in stage._CONSUMED
    save(evidence, "disabled-trial", owner.trial)


@pytest.mark.parametrize(
    "where",
    ["setup", "p_construct", "p_load", "yaml_load", "handler_init", "tissues_after", "events"],
)
def test_software_source_failures_keep_partial_cause_and_irreversible_attempt(
    monkeypatch, evidence, where
):
    h = fixture(monkeypatch, failure=where)
    previous, trace = stage.sys.getprofile(), stage.sys.gettrace()
    with pytest.raises(stage.ConfigurationRejected) as caught:
        stage.prepare(h.request)
    error = caught.value
    assert error.source_error is h.errors["source"] and error.__cause__ is h.errors["source"]
    assert error.source_error.__cause__ is h.errors["cause"]
    assert h.request in stage._CONSUMED and not error.trial.source_completed
    assert stage.sys.getprofile() is previous and stage.sys.gettrace() is trace
    assert not error.partial["usable_child_available"]
    if where == "setup":
        assert error.partial["context"].factory_raw.marker
    if where == "events":
        assert error.partial["handler"].tissue_default is not None
    with pytest.raises(stage.ConfigurationRejected, match="consumed"):
        stage.prepare(h.request)
    save(evidence, "failed-state", retain(error))


@pytest.mark.parametrize(
    "kind",
    [
        "configuration",
        "equal_reference",
        "descriptor_link",
        "request_registry",
        "object_registry",
        "runtime_code",
        "namespace_helper",
    ],
)
def test_software_completed_identity_binding_and_alias_drift(monkeypatch, evidence, kind):
    h = fixture(monkeypatch)
    owner = stage.prepare(h.request)
    c = stage._authority(owner)
    if kind == "configuration":
        c.configuration["tissue profile definition"]["profiles enabled"] = False
    elif kind == "equal_reference":
        items = c.p.tissue_profiles._confs_wrap
        before = stage._snapshot(c).identity
        items[1]._conf["equal"] = items[0]._conf["equal"]
        assert stage._snapshot(c).identity == before
    elif kind == "descriptor_link":
        type(c.p).__dict__["is_tissue_profiles"].native = type(c.descriptor)()
    elif kind == "request_registry":
        monkeypatch.delitem(stage._REQUESTS, h.request)
    elif kind == "object_registry":
        monkeypatch.delitem(stage._OBJECTS, c.p.tissue_default)
    elif kind == "runtime_code":
        monkeypatch.setattr(type(c.p.tissue_default), "load", lambda *a: None)
    else:
        c.methods["__init__"].__globals__["logs"].log_warning = lambda *a: None
    with pytest.raises(stage.ConfigurationRejected) as caught:
        _ = owner.handler
    save(evidence, "drift-refusal", retain(caught.value))


@pytest.mark.parametrize(
    "where", ["p_construct_enter", "TissueProfile.__init___return", "__init___unwind"]
)
def test_software_observation_failure_stops_and_keeps_primary(monkeypatch, evidence, where):
    h = fixture(monkeypatch, failure="events" if where.endswith("unwind") else None)
    capture = SyntheticCaptureFailure("observer capture")
    original = stage._event

    def event(context, kind, raw):
        if kind == where:
            stage.captures._remember_observation_error(context, capture, origin=kind, raw=raw)
        else:
            original(context, kind, raw)

    monkeypatch.setattr(stage, "_event", event)
    with pytest.raises(stage.ConfigurationRejected) as caught:
        stage.prepare(h.request)
    error = caught.value
    assert error.capture_error is capture and error.trial is None
    if where == "p_construct_enter":
        assert "p_construct" not in h.calls
    if where.endswith("unwind"):
        assert error.source_error is h.errors["source"]
    save(evidence, "capture-failure", retain(error))


def test_software_final_sealing_failure_keeps_primary_objects(monkeypatch, evidence):
    h = fixture(monkeypatch, failure="events")
    capture = SyntheticCaptureFailure("final snapshot")
    original = stage._snapshot

    def snapshot(context):
        if context.stage == "__init__":
            raise capture
        return original(context)

    monkeypatch.setattr(stage, "_snapshot", snapshot)
    with pytest.raises(stage.ConfigurationRejected) as caught:
        stage.prepare(h.request)
    error = caught.value
    assert error.source_error is h.errors["source"] and error.capture_error is capture
    assert error.__cause__ is h.errors["source"] and error.partial["handler"].tissue_default
    save(evidence, "sealing-failure", retain(error))


@pytest.mark.parametrize("kind", ["new_module", "unlisted", "old_code_drift", "failed_import"])
def test_software_import_issuance_exact_pins_and_no_failed_authorization(
    monkeypatch, tmp_path, evidence, kind
):
    native = tmp_path / "native"
    native.mkdir()
    one = native / "one.py"
    one.write_text("native source metadata one\n")
    two = native / "two.py"
    two.write_text("native source metadata two\n")
    old = types.ModuleType("betse.old")
    new = types.ModuleType("betse.new")
    old.fn = lambda: None
    rows = {"betse.old": (old, one, hashlib.sha256(one.read_bytes()).hexdigest())}
    auth = {"betse.old": (rows["betse.old"], stage.aliases._module_bindings(old))}
    monkeypatch.setattr(stage.aliases, "NATIVE", native)
    monkeypatch.setattr(stage.aliases, "_MODULE_AUTH", auth)
    monkeypatch.setattr(stage.aliases, "_module_records", lambda: dict(rows))
    pins = {"one.py": rows["betse.old"][2]}
    if kind != "unlisted":
        pins["two.py"] = hashlib.sha256(two.read_bytes()).hexdigest()

    def execute():
        with stage.aliases.issuing_native_imports(pins):
            rows["betse.new"] = (new, two, hashlib.sha256(two.read_bytes()).hexdigest())
            if kind == "old_code_drift":
                old.fn = lambda: 42
            if kind == "failed_import":
                raise SyntheticSourceFailure("original import failure")

    if kind == "new_module":
        execute()
        assert stage.aliases._MODULE_AUTH["betse.new"][0] == rows["betse.new"]
        stage.aliases._check_modules()
    else:
        with pytest.raises((ValueError, SyntheticSourceFailure)) as caught:
            execute()
        assert "betse.new" not in stage.aliases._MODULE_AUTH
        save(evidence, "import-refusal", caught.value)
    save(evidence, "import-state", dict(pins=pins, authorized=list(auth)))


def _factory_probe(mode):
    """Synthetic factory bodies, optionally using the real decorator library."""
    marker, calls = object(), []

    class YamlList:
        def __init__(self, *, item_type, token, flag):
            self.item_type, self.token, self.flag = item_type, token, flag

    namespace = dict(YamlList=YamlList, marker=marker, calls=calls, __name__=__name__)
    exec(
        "def make_list(cls, token=marker, *, flag=marker):\n"
        "    calls.append((cls, token, flag))\n"
        "    return YamlList(item_type=cls, token=token, flag=flag)\n",
        namespace,
    )
    body = function = namespace["make_list"]
    if mode == "beartype":
        from beartype import beartype

        function.__annotations__ = {"return": YamlList}
        function = beartype(function)
        assert function is not body and function.__wrapped__ is body
        assert function.__kwdefaults__["__beartype_func"] is body
    elif mode == "closure":

        def wrapper(*args, **kwargs):
            return body(*args, **kwargs)

        wrapper.__wrapped__ = body
        function = wrapper
    native = type("SyntheticListItem", (), {"make_list": classmethod(function)})
    return SimpleNamespace(
        function=function, body=body, native=native, yaml=YamlList, calls=calls, marker=marker
    )


@pytest.mark.parametrize("mode", ["plain", "beartype", "closure"])
def test_software_factory_copy_preserves_decorators_defaults_and_owned_return(mode, evidence):
    probe = _factory_probe(mode)
    original = stage._factory_atoms(probe.function)
    issued = []

    def owned(**kwargs):
        result = probe.yaml(**kwargs)
        issued.append(result)
        return result

    copied = stage._copy_factory(probe.function, owned)
    result = copied(probe.native)
    assert result is issued[0] and result.item_type is probe.native
    assert result.token is result.flag is probe.marker
    assert probe.calls == [(probe.native, probe.marker, probe.marker)]
    stage._same(stage._factory_atoms(probe.function), original)
    assert probe.body.__globals__["YamlList"] is probe.yaml
    if mode == "beartype":
        assert copied.__kwdefaults__["__beartype_func"] is copied.__wrapped__
        assert copied.__wrapped__ is not probe.body
        assert copied.__kwdefaults__ is not probe.function.__kwdefaults__
        for name, value in probe.function.__kwdefaults__.items():
            if name != "__beartype_func":
                assert copied.__kwdefaults__[name] is value
    save(evidence, "factory-copy", dict(mode=mode, owned_return=True, original_unchanged=True))


def test_software_factory_copy_keeps_actual_beartype_return_check(evidence):
    probe = _factory_probe("beartype")
    from beartype.roar import BeartypeCallHintReturnViolation

    copied = stage._copy_factory(probe.function, lambda **_kwargs: object())
    with pytest.raises(BeartypeCallHintReturnViolation) as caught:
        copied(probe.native)
    assert len(probe.calls) == 1
    save(evidence, "return-type-refusal", dict(error=type(caught.value).__qualname__))


@pytest.mark.parametrize("mode", ["plain", "beartype", "closure"])
def test_software_factory_copy_preserves_original_exception_and_cause(mode, evidence):
    probe = _factory_probe(mode)
    primary = SyntheticSourceFailure("synthetic original constructor failure")
    cause = SyntheticSourceCause("same original cause")

    def failed(**_kwargs):
        raise primary from cause

    copied = stage._copy_factory(probe.function, failed)
    with pytest.raises(SyntheticSourceFailure) as caught:
        copied(probe.native)
    assert caught.value is primary and caught.value.__cause__ is cause
    save(evidence, "original-failure", dict(mode=mode, same_primary=True, same_cause=True))


@pytest.mark.parametrize("mutation", ["keywords", "keyword_value", "delegate", "code", "closure"])
def test_software_factory_binding_refuses_drift_with_outer_identity_unchanged(
    mutation, monkeypatch, evidence
):
    probe = _factory_probe("closure" if mutation == "closure" else "beartype")
    retained = stage._surface(probe.native)
    original = probe.function
    if mutation == "keywords":
        monkeypatch.setattr(original, "__kwdefaults__", dict(original.__kwdefaults__))
    elif mutation == "keyword_value":
        monkeypatch.setitem(probe.body.__kwdefaults__, "flag", object())
    elif mutation == "delegate":
        replacement = types.FunctionType(
            probe.body.__code__, probe.body.__globals__, argdefs=probe.body.__defaults__
        )
        replacement.__kwdefaults__ = dict(probe.body.__kwdefaults__)
        monkeypatch.setitem(original.__kwdefaults__, "__beartype_func", replacement)
    elif mutation == "code":
        monkeypatch.setattr(probe.body, "__code__", probe.body.__code__.replace())
    else:
        original.__closure__[0].cell_contents = lambda *a, **k: None
    assert probe.native.make_list.__func__ is original and not probe.calls
    with pytest.raises(ValueError, match="binding changed"):
        stage._same(stage._surface(probe.native), retained)
    save(evidence, "factory-drift", dict(mutation=mutation, delegates=0))


@pytest.mark.parametrize("kind", ["cycle", "non_function", "too_deep"])
def test_software_factory_copy_refuses_unbounded_or_invalid_wrapped_chain(kind, evidence):
    probe = _factory_probe("plain")
    if kind == "cycle":
        probe.function.__wrapped__ = probe.function
    elif kind == "non_function":
        probe.function.__wrapped__ = object()
    else:
        current = probe.function
        for _ in range(16):
            following = types.FunctionType(probe.body.__code__, probe.body.__globals__)
            current.__wrapped__ = following
            current = following
    with pytest.raises(ValueError, match="acyclic Python factory wrapper chain"):
        stage._copy_factory(probe.function, lambda **kwargs: None)
    assert not probe.calls
    save(evidence, "invalid-chain", dict(kind=kind, delegates=0))


@pytest.mark.parametrize("mode", ["plain", "beartype", "closure"])
def test_software_factory_runtime_class_uses_actual_owned_list_and_preserves_input(
    mode, monkeypatch, evidence
):
    probe = _factory_probe(mode)
    context = SimpleNamespace(
        active=True,
        thread=stage.get_ident(),
        observation_error=None,
        runtime_types={},
        runtime_bindings={},
        objects=[],
        work=[],
        events=[],
        factories={"SimConfCutListItem": probe.native, "YamlList": probe.yaml},
    )
    native = stage._surface(probe.native)

    def check(actual):
        assert actual is context
        stage._same(stage._surface(probe.native), native)
        for name, cls in context.runtime_types.items():
            stage._same(stage._surface(cls), context.runtime_bindings[name])

    # Isolated factory metadata adapter, not an issued parameter/phase owner.
    monkeypatch.setattr(stage, "_ACTIVE", [context])
    monkeypatch.setattr(stage, "_check", check)
    cls = stage._runtime_type(context, "SimConfCutListItem")
    result = cls.make_list()
    assert type(result) is context.runtime_types["YamlList"]
    assert isinstance(result, probe.yaml) and result.item_type is cls
    assert stage._OBJECTS[result] is context
    assert result.token is result.flag is probe.marker
    assert probe.body.__globals__["YamlList"] is probe.yaml and len(probe.calls) == 1
    check(context)
    context.active = False
    with pytest.raises(stage.ConfigurationRejected):
        cls.make_list()
    assert len(probe.calls) == 1
    save(evidence, "runtime-factory", dict(mode=mode, owned_result=True, raw_entry_refused=True))


@pytest.mark.parametrize("mutation", ["lookup", "constructor_code", "constructor_closure"])
def test_software_factory_copied_namespace_retarget_refuses_before_constructor(
    mutation, monkeypatch, evidence
):
    probe = _factory_probe("beartype")
    context = SimpleNamespace(
        active=True,
        thread=stage.get_ident(),
        observation_error=None,
        runtime_types={},
        runtime_bindings={},
        objects=[],
        work=[],
        events=[],
        factories={"SimConfCutListItem": probe.native, "YamlList": probe.yaml},
    )

    def check(actual):
        assert actual is context
        for name, cls in context.runtime_types.items():
            stage._same(stage._surface(cls), context.runtime_bindings[name])

    monkeypatch.setattr(stage, "_ACTIVE", [context])
    monkeypatch.setattr(stage, "_check", check)
    cls = stage._runtime_type(context, "SimConfCutListItem")
    wrapper = vars(cls)["make_list"].__func__
    values = dict(zip(wrapper.__code__.co_freevars, wrapper.__closure__, strict=True))
    delegate = values["delegate"].cell_contents
    body = delegate.__wrapped__
    constructor = body.__globals__["YamlList"]
    original = (wrapper, wrapper.__code__, delegate, delegate.__code__, delegate.__kwdefaults__)
    replacements = []

    def foreign(**kwargs):
        replacements.append(kwargs)
        return probe.yaml(**kwargs)  # Valid native base type, but unissued.

    if mutation == "lookup":
        monkeypatch.setitem(body.__globals__, "YamlList", foreign)
    elif mutation == "constructor_code":
        monkeypatch.setattr(constructor, "__code__", constructor.__code__.replace())
    else:
        constructor.__closure__[0].cell_contents = SimpleNamespace(
            active=True, thread=stage.get_ident(), observation_error=None
        )
    assert all(
        a is b
        for a, b in zip(
            original,
            (wrapper, wrapper.__code__, delegate, delegate.__code__, delegate.__kwdefaults__),
            strict=True,
        )
    )
    with pytest.raises(ValueError, match="binding changed"):
        check(context)
    with pytest.raises(ValueError):
        cls.make_list()
    assert not replacements and not probe.calls and not context.objects
    save(evidence, "namespace-retarget", dict(mutation=mutation, constructor_calls=0))


def _abc_probe(monkeypatch, *, hook_base=None):
    calls = []

    class SyntheticYamlList(MutableSequence if hook_base is None else hook_base):
        def __init__(self):
            calls.append("construct")

        def __getitem__(self, index):
            calls.append("getitem")

        def __setitem__(self, index, value):
            calls.append("setitem")

        def __delitem__(self, index):
            calls.append("delitem")

        def __len__(self):
            calls.append("len")
            return 0

        def insert(self, index, value):
            calls.append("insert")

        @classmethod
        def make_default(cls):
            calls.append("factory")

    context = SimpleNamespace(
        active=True,
        thread=stage.get_ident(),
        observation_error=None,
        runtime_types={},
        runtime_bindings={},
        objects=[],
        work=[],
        events=[],
        factories={"YamlList": SyntheticYamlList},
    )
    monkeypatch.setattr(stage, "_ACTIVE", [context])
    # Only stdlib protocol metadata is exercised, never an issued native owner.
    return context, SyntheticYamlList, calls


@pytest.mark.parametrize("state", ["closed", "no_active_context", "other_thread"])
def test_software_abc_hook_keeps_unrelated_type_checks_outside_source_epoch(
    state, monkeypatch, evidence
):
    context, native, calls = _abc_probe(monkeypatch)
    cls = stage._runtime_type(context, "YamlList")
    assert "__subclasshook__" not in vars(cls)
    assert cls.__subclasshook__.__func__ is Reversible.__subclasshook__.__func__
    if state == "closed":
        context.active = False
    elif state == "no_active_context":
        stage._ACTIVE.clear()
    else:
        context.thread = -1
    reached = []
    previous, trace = sys.getprofile(), sys.gettrace()

    def observer(frame, event, arg):
        if event == "call" and frame.f_code is stage._REVERSIBLE_HOOK_CODE:
            reached.append(frame.f_locals["cls"])
        if previous is not None:
            previous(frame, event, arg)

    class Unrelated:
        pass

    try:
        sys.setprofile(observer)
        assert not issubclass(Unrelated, Sequence)
        assert not isinstance(Unrelated(), Sequence)
    finally:
        sys.setprofile(previous)
    assert any(actual is cls for actual in reached)
    assert sys.getprofile() is previous and sys.gettrace() is trace
    assert not calls and not context.work and not context.events and not context.objects
    assert issubclass(cls, native) and issubclass(cls, MutableSequence)
    with pytest.raises(stage.ConfigurationRejected):
        cls()
    with pytest.raises(stage.ConfigurationRejected):
        cls.make_default()
    assert not calls
    save(evidence, "abc-closed-check", dict(state=state, actual_stdlib_hook_reached=True))


@pytest.mark.parametrize("value", [{"configuration": True}, [1, 2], object()])
def test_software_abc_hook_preserves_real_decorator_yaml_return_validation(
    value, monkeypatch, evidence
):
    from beartype import beartype
    from beartype.roar import BeartypeCallHintReturnViolation

    context, _native, calls = _abc_probe(monkeypatch)
    cls = stage._runtime_type(context, "YamlList")
    context.active = False

    @beartype
    def yaml_return() -> Mapping | Sequence:
        return value

    if type(value) is object:
        with pytest.raises(BeartypeCallHintReturnViolation):
            yaml_return()
    else:
        assert yaml_return() is value
    assert cls.__subclasshook__(type(value)) is NotImplemented
    assert not calls and not context.work and not context.events
    save(evidence, "abc-decorator-check", dict(type=type(value).__name__, unchanged_result=True))


@pytest.mark.parametrize("mode", ["override", "stdlib_label"])
def test_software_abc_hook_does_not_exempt_other_classmethods(mode, monkeypatch, evidence):
    calls = []

    class Foreign:
        @classmethod
        def __subclasshook__(cls, candidate):
            calls.append(candidate)
            return True

    if mode == "stdlib_label":
        Foreign.__module__, Foreign.__name__ = "collections.abc", "Reversible"
    context, _native, _methods = _abc_probe(monkeypatch, hook_base=Foreign)
    cls = stage._runtime_type(context, "YamlList")
    context.active = False
    with pytest.raises(stage.ConfigurationRejected):
        cls.__subclasshook__(dict)
    assert not calls
    save(evidence, "abc-foreign-refused", dict(mode=mode, source_calls=0))


@pytest.mark.parametrize("mode", ["descriptor", "function", "code", "global"])
def test_software_abc_hook_refuses_changed_stdlib_before_class_issuance(
    mode, monkeypatch, evidence
):
    context, _native, calls = _abc_probe(monkeypatch)
    original = vars(Reversible)["__subclasshook__"]
    with monkeypatch.context() as patch:
        if mode == "descriptor":
            patch.setattr(Reversible, "__subclasshook__", classmethod(original.__func__))
        elif mode == "function":
            replacement = types.FunctionType(
                original.__func__.__code__, original.__func__.__globals__
            )
            patch.setattr(Reversible, "__subclasshook__", classmethod(replacement))
        elif mode == "code":
            patch.setattr(original.__func__, "__code__", original.__func__.__code__.replace())
        else:
            patch.setitem(original.__func__.__globals__, "Reversible", object())
        with pytest.raises(ValueError, match="Original stdlib Reversible"):
            stage._runtime_type(context, "YamlList")
    assert not context.runtime_types and not context.objects and not calls
    save(evidence, "abc-mutated-refused", dict(mode=mode, class_issued=False))
