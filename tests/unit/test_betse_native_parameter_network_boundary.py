"""Conditional input/frame schemas only; native join/parser are forbidden."""

import builtins
import dis
import hashlib
import sys
from dataclasses import replace
from pathlib import Path
from types import FunctionType, ModuleType, SimpleNamespace

import pytest

from cells.processes import betse_native_parameter_network_boundary as stage
from tests.unit import test_betse_native_parameter_event_declarations as earlier
from validation.betse.betse_native_single_cell_core_synthetic import save

blocked = earlier.blocked
ORIGINAL_COMPILE = stage._compile


@pytest.fixture(scope="module")
def plan():
    return stage.source_plan()


@pytest.fixture
def controlled(monkeypatch, tmp_path, request):
    scenario = getattr(request, "param", "network")
    h = earlier.controlled.__wrapped__(
        monkeypatch, tmp_path, stage.previous.source_plan(), SimpleNamespace(param=scenario)
    )
    owner = stage.previous.prepare(h.request(), enabled=True)
    parent = stage.previous._ISSUED[owner]
    paths = parent.parent.parent.parent
    file = h.prior.base.file
    # Explicit synthetic ancestry/observer provider. This is not native read
    # derivation; actual YAML/parser/constructor calls remain forbidden.
    source_module = sys.modules[__name__]
    parent.birth.source.modules = {"betse.science.parameters": source_module}

    def never_evaluate(*args, **kwargs):
        raise AssertionError("Source execution forbidden")

    parent.birth.source.modules["betse.science.parameters"] = sys.modules[never_evaluate.__module__]
    yowner = object.__new__(stage.prefix.YamlPrefixOwner)
    birth_owner = object.__new__(stage.prefix.parameters.ParameterOwner)
    parent.birth.owner = birth_owner
    monkeypatch.setitem(stage.prefix.parameters._ISSUED, birth_owner, parent.birth)
    yrequest = stage.prefix.Request(
        birth_owner, file, "synthetic_birth", "synthetic_source", "synthetic_read_request"
    )
    key = (
        str(
            stage.prefix.parameters.inherited.tissue.aliases.NATIVE
            / stage.prefix.parameters.PARAMETERS
        ),
        "Parameters.load",
    )
    frame = dict(
        self=h.p,
        __class__=parent.birth.source.cls,
        args=(file.filename,),
        kwargs={},
        YAML_VERSION="1.2",
    )
    cache = stage.prefix.parameters.inherited.tissue.core.caches.snapshot(
        {"conditional_original_read": True}
    )
    trial = stage.prefix.Trial(yrequest.identity, "conditional_before", cache, (), True, "")
    trial = replace(trial, identity=stage._digest(stage.prefix.trial_record(trial)))
    yaml = SimpleNamespace(
        owner=yowner,
        p=h.p,
        parent=parent.birth,
        prefix_completed=True,
        trial=trial,
        request=yrequest,
        function=never_evaluate,
        function_bindings=stage.prefix._function_bindings(never_evaluate),
        locals={key: frame},
    )
    monkeypatch.setitem(stage.prefix._ISSUED, yowner, yaml)
    monkeypatch.setitem(stage.prefix._CONSUMED, yrequest, yaml)
    monkeypatch.setitem(stage.prefix._CLAIMED, yrequest.parent, yaml)
    monkeypatch.setattr(paths, "yaml", yaml)
    monkeypatch.setattr(stage, "_compile", lambda context: (never_evaluate, never_evaluate))
    expression = None
    if scenario == "network":
        p = tmp_path / "missing-source.yaml"
        data = b"synthetic: expression-input\n"
        p.write_bytes(data)
        p.chmod(0o444)
        expression = stage.prefix.input_file(
            p,
            sha256=hashlib.sha256(data).hexdigest(),
            origin="conditional software bytes, not parsed/native derivation",
        )
    return SimpleNamespace(
        base=h,
        owner=owner,
        parent=parent,
        yaml=yaml,
        frame=frame,
        file=expression,
        prepare=lambda value=expression: stage.prepare(
            owner, law_id=stage.LAW_ID, expression_file=value
        ),
    )


def empty():
    assert not stage._ACTIVE and not stage.previous._ACTIVE and not stage.claims._ACTIVE
    assert not stage.previous.previous._ACTIVE and not stage.previous.previous.previous._ACTIVE
    assert not stage.previous.previous.previous.paths._ACTIVE


def test_literal_next_branch_and_explicit_local_transport_are_source_only(plan):
    assert plan["statement_slice"] == (61, 62) and plan["source_lines"] == (779, 796)
    assert plan["next_source_line"] == 802 and len(plan["native_pins"]) == 272
    assert plan["local_transport"] == "YAML_VERSION = kwargs['_cells_original_yaml_version']"
    assert (
        not plan["branch_join_parser_execution"]
        and not plan["parameter_advance_phase_INIT_admitted"]
    )


@pytest.mark.parametrize("controlled", ["zero", "network"], indirect=True)
def test_conditional_frame_and_file_schema_retains_same_p_without_advancing(controlled, tmp_path):
    h = controlled
    original = dict(vars(h.parent.p))
    boundary = h.prepare()
    assert boundary.parameters is h.parent.p and not h.parent.invalid
    assert all(vars(h.parent.p)[name] is value for name, value in original.items())
    b = boundary.binding
    assert (
        b.yaml_version is h.frame["YAML_VERSION"]
        and b.yaml_read_trial_identity == h.yaml.trial.identity
    )
    if h.file:
        assert b.file_identity == h.file.identity and b.join_arguments == (
            str(tmp_path),
            "missing-source.yaml",
        )
    else:
        assert b.file_identity is None and b.join_arguments is None
    with pytest.raises(stage.BoundaryRejected) as caught:
        stage.require_execution(boundary)
    assert (
        caught.value.stage == "native_branch_held"
        and not caught.value.partial["native_join_observed"]
    )
    empty()
    save(
        tmp_path,
        "boundary-inputs",
        dict(
            binding=b,
            original_fields_unchanged=True,
            conditional_source_provider=True,
            native_join_parser_calls=0,
            independent_cases=0,
        ),
    )


@pytest.mark.parametrize(
    "change",
    [
        "missing-version",
        "wrong-version",
        "foreign-self",
        "foreign-class",
        "foreign-args",
        "keyword",
        "no-issued-ancestor",
        "read-incomplete",
    ],
)
def test_missing_or_foreign_original_read_authority_refuses_exactly(controlled, change):
    h = controlled
    if change == "missing-version":
        h.frame.pop("YAML_VERSION")
    elif change == "wrong-version":
        h.frame["YAML_VERSION"] = "1.1"
    elif change == "foreign-self":
        h.frame["self"] = object()
    elif change == "foreign-class":
        h.frame["__class__"] = object
    elif change == "foreign-args":
        h.frame["args"] = ("supplied-path",)
    elif change == "keyword":
        h.frame["kwargs"]["yaml_version"] = "1.2"
    elif change == "no-issued-ancestor":
        stage.prefix._ISSUED.pop(h.yaml.owner)
    else:
        h.yaml.prefix_completed = False
    with pytest.raises(stage.BoundaryRejected) as caught:
        h.prepare()
    assert caught.value.stage == (
        "read_ancestry" if change in {"no-issued-ancestor", "read-incomplete"} else "read_frame"
    )
    assert h.parent.invalid
    empty()


def test_missing_expression_file_is_executable_refusal_before_compile(controlled, monkeypatch):
    h = controlled
    seen = []

    def no_compile(*args):
        seen.append(True)
        raise AssertionError("Compile must not precede file authority")

    monkeypatch.setattr(stage, "_compile", no_compile)
    with pytest.raises(stage.BoundaryRejected) as caught:
        h.prepare(None)
    assert caught.value.stage == "file_authority" and seen == [] and h.parent.invalid
    empty()


@pytest.mark.parametrize(
    "change", ["copied-file", "writable-file", "changed-file", "foreign-file-record"]
)
def test_immutable_file_registry_identity_and_bytes_are_required(controlled, tmp_path, change):
    h = controlled
    value = h.file
    if change == "copied-file":
        value = replace(value)
    elif change == "writable-file":
        Path(value.filename).chmod(0o644)
    elif change == "changed-file":
        p = Path(value.filename)
        p.chmod(0o644)
        p.write_bytes(b"changed\n")
        p.chmod(0o444)
    else:
        value = {"filename": value.filename, "sha256": value.sha256}
    with pytest.raises((ValueError, stage.prefix.YamlPrefixRejected)):
        h.prepare(value)
    assert h.parent.invalid
    empty()


@pytest.mark.parametrize("change", ["frame-value", "frame-copy", "file", "producer-binding"])
def test_retained_boundary_detects_later_ancestry_and_file_changes(controlled, monkeypatch, change):
    h = controlled
    boundary = h.prepare()
    if change == "frame-value":
        h.frame["YAML_VERSION"] = "1.1"
    elif change == "frame-copy":
        key = next(iter(h.yaml.locals))
        h.yaml.locals[key] = dict(h.frame)
    elif change == "file":
        Path(h.file.filename).chmod(0o644)
    else:
        monkeypatch.setattr(stage, "LOCAL_KEY", "foreign")
    with pytest.raises(ValueError):
        _ = boundary.binding
    assert h.parent.invalid
    empty()


@pytest.mark.parametrize(
    "value", [None, {}, SimpleNamespace(), object.__new__(stage.NetworkBoundary)]
)
def test_supplied_record_cannot_be_network_boundary(value):
    with pytest.raises(stage.BoundaryRejected) as caught:
        stage.require_execution(value)
    assert caught.value.stage == "boundary"


def test_source_failure_preserves_original_exception_with_read_only_parent(
    controlled, monkeypatch, tmp_path
):
    h = controlled
    primary = RuntimeError("source preparation failed")
    cause = KeyError("original cause")

    def fail(*args):
        raise primary from cause

    monkeypatch.setattr(stage, "_compile", fail)
    with pytest.raises(RuntimeError) as caught:
        h.prepare()
    assert caught.value is primary and primary.__cause__ is cause and h.parent.invalid
    ctx = primary.network_boundary_claim
    assert ctx.source_error is primary and not ctx.active
    empty()
    save(
        tmp_path,
        "preparation-failure",
        dict(primary=primary, secondary=ctx.capture_errors, raw=vars(h.parent.p), native_calls=0),
    )


def test_original_branch_compilation_restores_only_retained_local_without_evaluation(tmp_path):
    path, cls, load, selected = stage._ast()
    code = stage.prefix.parameters._method_code(cls, "load", str(path))
    holder = type("MetadataOnlyParameters", (), {})
    module = ModuleType("metadata_only_parameters")
    namespace = vars(module)
    namespace["__builtins__"] = builtins.__dict__

    def cell(value):
        return (lambda: value).__closure__[0]

    raw = FunctionType(code, namespace, "load", None, (cell(holder),))
    holder.load = raw
    parent = SimpleNamespace(
        birth=SimpleNamespace(
            source=SimpleNamespace(cls=holder, modules={"betse.science.parameters": module})
        )
    )
    function, original = ORIGINAL_COMPILE(parent)
    assert original is raw and function.__globals__ is namespace
    assert function.__builtins__ is raw.__builtins__ and function.__closure__ is None
    assert "YAML_VERSION" not in namespace and "1.2" not in function.__code__.co_consts
    instructions = list(dis.get_instructions(function))
    assert any(i.opname == "LOAD_FAST" and i.argval == "YAML_VERSION" for i in instructions)
    assert not any(i.opname == "LOAD_GLOBAL" and i.argval == "YAML_VERSION" for i in instructions)
    assert (
        "expression_data" in function.__code__.co_names
        and "grn_enabled" not in function.__code__.co_names
    )
    save(
        tmp_path,
        "compiled-branch",
        dict(
            original_branch_statements=len(selected),
            native_source_evaluations=0,
            transported_local=stage.LOCAL_KEY,
            source_globals_unchanged=True,
            version_default_regenerated=False,
        ),
    )
