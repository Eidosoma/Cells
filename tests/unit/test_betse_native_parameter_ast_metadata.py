"""Closed metadata only: no native import, constructed owner, or compiled body."""

import ast
import copy
import operator
from types import CodeType

import pytest

from tests.unit import test_betse_native_source_compilation_cache as reused

RAW = b"class Example:\n def values(self):\n  return 3, 0, 0.0\n def next(self):\n  return 'next'\n"


def immutable_plan(value):
    return type(value) in (str, int, CodeType) or (
        type(value) is tuple and all(immutable_plan(child) for child in value)
    )


@pytest.fixture(autouse=True)
def blocked(monkeypatch, request, tmp_path):
    yield from reused.blocked.__wrapped__(monkeypatch, request, tmp_path)


@pytest.fixture
def metadata(tmp_path, blocked):
    return reused.metadata.__wrapped__(tmp_path, blocked)


def setup(metadata, tmp_path):
    path, tree = reused._source(metadata, tmp_path, RAW)
    cls = tree.body[0]
    p = metadata.parameters
    code = p._method_code(cls, "values", str(path), native_context=True)
    _, classes, _, _, _ = p._compiled_source(RAW, str(path))
    dump, plan = next((dump, plan) for name, dump, plan in classes if name == "Example")
    return p, path, cls, code, dump, plan


def test_ast_metadata_warm_clone_uses_same_original_code_and_no_mutable_ast_plan(
    metadata, tmp_path
):
    p, path, cls, code, _, plan = setup(metadata, tmp_path)
    with reused._compiler_calls(p) as compiles:
        assert p._method_code(copy.deepcopy(cls), "values", str(path), native_context=True) is code
    assert not compiles
    assert immutable_plan(plan)
    pending = [plan]
    while pending:
        value = pending.pop()
        assert not isinstance(value, ast.AST)
        if type(value) is tuple:
            pending.extend(value)
    assert p._compilation_class_matches(cls, plan)
    cls.body[0].body[0].value.elts[0].value = 4
    assert not p._compilation_class_matches(cls, plan)
    with pytest.raises(ValueError, match="original class AST"):
        p._method_code(cls, "values", str(path), native_context=True)


@pytest.mark.parametrize("member,removed", (("_fields", "name"), ("_attributes", "lineno")))
def test_ast_metadata_cold_roster_list_then_warm_mutation_refuses(
    member, removed, metadata, tmp_path, monkeypatch
):
    p = metadata.parameters
    mutable = list(getattr(ast.ClassDef, member))
    monkeypatch.setattr(ast.ClassDef, member, mutable)
    path, tree = reused._source(metadata, tmp_path, RAW)
    cls = tree.body[0]
    first = p._method_code(cls, "values", str(path), native_context=True)
    before = p._compiled_source(RAW, str(path))
    dump, plan = next((dump, plan) for name, dump, plan in before[1] if name == "Example")
    assert not plan and immutable_plan(before)
    assert p._method_code(cls, "values", str(path), native_context=True) is first
    mutable.remove(removed)
    assert getattr(cls, member) is mutable
    assert dump != ast.dump(cls, include_attributes=True)
    assert not p._compilation_class_matches(cls, plan)
    with pytest.raises(ValueError, match="original class AST"):
        p._method_code(cls, "values", str(path), native_context=True)
    assert p._compiled_source(RAW, str(path)) is before and immutable_plan(before)


@pytest.mark.parametrize("member", ("_fields", "_attributes"))
@pytest.mark.parametrize("kind", ("tuple_subclass", "label_subclass"))
def test_ast_metadata_cold_roster_subclasses_keep_original_fallback(
    member, kind, metadata, tmp_path, monkeypatch
):
    class Tuple(tuple):
        pass

    class Label(str):
        pass

    p = metadata.parameters
    original = getattr(ast.ClassDef, member)
    roster = Tuple(original) if kind == "tuple_subclass" else tuple(Label(v) for v in original)
    monkeypatch.setattr(ast.ClassDef, member, roster)
    path, tree = reused._source(metadata, tmp_path, RAW)
    cls = tree.body[0]
    code = p._method_code(cls, "values", str(path), native_context=True)
    result = p._compiled_source(RAW, str(path))
    assert not result[1][0][2] and immutable_plan(result)
    assert p._method_code(cls, "values", str(path), native_context=True) is code


@pytest.mark.parametrize(
    "change",
    (
        "int_float",
        "int_complex",
        "int_bool",
        "signed_zero",
        "location",
        "body",
        "sequence",
        "child_type",
        "field_order",
    ),
)
def test_ast_metadata_current_input_drift_cannot_reuse_warm_proof(change, metadata, tmp_path):
    p, path, original, _, dump, plan = setup(metadata, tmp_path)
    cls = copy.deepcopy(original)
    constants = cls.body[0].body[0].value.elts
    if change == "int_float":
        constants[0].value = 3.0
    elif change == "int_complex":
        constants[0].value = complex(3, 0)
    elif change == "int_bool":
        constants[1].value = False
    elif change == "signed_zero":
        constants[2].value = -0.0
    elif change == "location":
        cls.body[0].end_col_offset += 1
    elif change == "body":
        cls.body.pop()
    elif change == "sequence":
        cls.body.reverse()
    elif change == "child_type":
        cls.body[0].body[0].value = ast.copy_location(
            ast.List(elts=constants, ctx=ast.Load()), cls.body[0].body[0].value
        )
    else:
        cls._fields = tuple(reversed(cls._fields))
    assert ast.dump(cls, include_attributes=True) != dump
    assert not p._compilation_class_matches(cls, plan)
    with pytest.raises(ValueError, match="original class AST"):
        p._method_code(cls, "values", str(path), native_context=True)


@pytest.mark.parametrize("change", ("omitted_empty", "copied_fields", "extra_attribute"))
def test_ast_metadata_fallback_preserves_original_dump_equivalence(change, metadata, tmp_path):
    p, path, original, code, dump, plan = setup(metadata, tmp_path)
    cls = copy.deepcopy(original)
    if change == "omitted_empty":
        del cls.decorator_list
    elif change == "copied_fields":
        cls._fields = tuple(list(cls._fields))
    else:
        cls.unreached_annotation = object()
    assert ast.dump(cls, include_attributes=True) == dump
    assert p._method_code(cls, "values", str(path), native_context=True) is code


@pytest.mark.parametrize("member", ("_fields", "_attributes"))
def test_ast_metadata_equal_field_labels_cannot_hide_changed_display(member, metadata, tmp_path):
    p, path, cls, _, dump, plan = setup(metadata, tmp_path)

    class ForeignLabel(str):
        def __str__(self):
            return "foreign"

    setattr(cls, member, tuple(ForeignLabel(label) for label in getattr(cls, member)))
    assert getattr(cls, member) == getattr(type(cls), member)
    assert ast.dump(cls, include_attributes=True) != dump
    assert not p._compilation_class_matches(cls, plan)
    with pytest.raises(ValueError, match="original class AST"):
        p._method_code(cls, "values", str(path), native_context=True)


@pytest.mark.parametrize("change", ("none_default", "empty_field_origin"))
def test_ast_metadata_rechecks_ast_dump_omission_rules(change, metadata, tmp_path, monkeypatch):
    p, path, cls, _, dump, plan = setup(metadata, tmp_path)
    if change == "none_default":
        monkeypatch.setattr(ast.FunctionDef, "returns", False)
    else:
        monkeypatch.setitem(ast.ClassDef._field_types, "decorator_list", object)
    assert ast.dump(cls, include_attributes=True) != dump
    assert not p._compilation_class_matches(cls, plan)
    with pytest.raises(ValueError, match="original class AST"):
        p._method_code(cls, "values", str(path), native_context=True)


def test_ast_metadata_large_fast_plan_falls_back_without_narrowing_compilation_domain(
    metadata, tmp_path
):
    raw = b"class Example:\n def values(self):\n" + b"  value = 0\n" * 5000 + b"  return value\n"
    path, tree = reused._source(metadata, tmp_path, raw)
    p, cls = metadata.parameters, tree.body[0]
    actual = p._method_code(cls, "values", str(path), native_context=True)
    compiled, classes, _, _, _ = p._compiled_source(raw, str(path))
    _, dump, plan = classes[0]
    assert not plan and ast.dump(cls, include_attributes=True) == dump
    assert actual is reused._body(compiled, "Example.values")


def test_ast_metadata_descriptor_fallback_preserves_earlier_original_primary(
    metadata, tmp_path, monkeypatch
):
    p, path, cls, _, _, plan = setup(metadata, tmp_path)
    primary, cause, secondary = ValueError("earlier field"), OSError("cause"), TypeError("later")
    invoked = []

    class Name:
        def __eq__(self, value):
            return value == "Example"

        def __repr__(self):
            raise primary from cause

    def later(value):
        invoked.append(value)
        raise secondary

    cls.name = Name()
    monkeypatch.setattr(ast.ClassDef, "body", property(later), raising=False)
    assert not p._compilation_class_matches(cls, plan)
    with pytest.raises(ValueError) as caught:
        p._method_code(cls, "values", str(path), native_context=True)
    assert caught.value is primary and primary.__cause__ is cause and not invoked


@pytest.mark.parametrize(
    "target",
    (
        "plan_code",
        "match_code",
        "plan_function",
        "match_function",
        "attrgetter_export",
        "itemgetter_export",
        "attrgetter_alias",
        "itemgetter_alias",
    ),
)
def test_ast_metadata_new_helper_or_selector_drift_refuses_before_foreign_body(
    target, metadata, tmp_path, monkeypatch
):
    p, path, cls, _, _, _ = setup(metadata, tmp_path)
    calls = []

    def foreign(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("Foreign metadata delegate must stay unreachable")

    if target == "plan_code":
        monkeypatch.setattr(
            p._compilation_class_plan, "__code__", p._compilation_class_plan.__code__.replace()
        )
    elif target == "match_code":
        monkeypatch.setattr(
            p._compilation_class_matches,
            "__code__",
            p._compilation_class_matches.__code__.replace(),
        )
    elif target == "plan_function":
        monkeypatch.setattr(p, "_compilation_class_plan", foreign)
    elif target == "match_function":
        monkeypatch.setattr(p, "_compilation_class_matches", foreign)
    elif target.endswith("_export"):
        monkeypatch.setattr(operator, target.removesuffix("_export"), foreign)
    else:
        monkeypatch.setattr(p, "_COMPILATION_" + target.removesuffix("_alias").upper(), foreign)
    with pytest.raises(ValueError, match="Original source compil"):
        p._method_code(cls, "values", str(path), native_context=True)
    assert not calls
