"""Blocked metadata integration: no Parameters, phase, RNG or native source entry."""

import ast
import copy
import gc
import hashlib
import json
import os
import statistics
import struct
import sys
import time
from pathlib import Path
from types import CodeType, FunctionType, SimpleNamespace

import pytest

from cells.processes import betse_native_immutable_graph_metadata as history
from tests.unit import test_betse_native_immutable_graph_metadata as base

ROOT = Path(__file__).resolve().parents[2]
CONSTANTS = "src/cells/processes/betse_native_parameter_initializer_constants.py"
REMAINDER = "src/cells/processes/betse_native_parameter_load_remainder.py"
SIMULATOR = "src/cells/processes/betse_native_simulator_construction.py"
QUALIFIER = "validation/betse/betse_native_parameter_world_ready_qualification.py"


@pytest.fixture(autouse=True)
def blocked(monkeypatch, tmp_path):
    yield from base.blocked.__wrapped__(monkeypatch, tmp_path)


def functions(path, names, namespace):
    """Compile complete source but execute only named metadata definitions."""
    code = compile((ROOT / path).read_bytes(), str(ROOT / path), "exec", dont_inherit=True)
    namespace = dict(namespace, __name__="isolated_parameter_history_metadata")
    for item in code.co_consts:
        if type(item) is CodeType and item.co_name in names:
            namespace[item.co_name] = FunctionType(item, namespace, item.co_name)
    assert set(names).issubset(namespace)
    return SimpleNamespace(**namespace)


def legacy_digest(value):
    return hashlib.sha256(base.original_bytes(value)).hexdigest()


def adapters():
    constants = functions(
        CONSTANTS,
        ("_digest", "_history_mode", "_history_plan", "_historical_capture"),
        dict(
            history_metadata=history,
            hashlib=hashlib,
            Path=Path,
            previous=SimpleNamespace(_digest=legacy_digest),
        ),
    )
    remainder = functions(REMAINDER, ("_digest",), dict(previous=constants))
    same = functions(SIMULATOR, ("_same_graph",), {})._same_graph
    return constants, remainder, same


def frozen():
    raw, descriptor = (object(), object()), base.graph_descriptor()
    return raw, descriptor, history.freeze_history_graph((raw, descriptor))


def test_exact_two_tuple_raw_references_and_original_wire_digest():
    raw, descriptor, image = frozen()
    constants, remainder, same = adapters()
    assert type(image) is tuple and len(image) == 2 and image[0] is raw
    assert type(image[1]) is history.HistoricalDescriptor
    assert constants._digest(image[1]) == remainder._digest(image[1]) == legacy_digest(descriptor)
    assert history.history_wire_descriptor(image[1]) == json.loads(base.original_bytes(descriptor))
    same((tuple(list(raw)), copy.deepcopy(descriptor)), image)
    same(image, (tuple(list(raw)), copy.deepcopy(descriptor)))
    same(image, history.freeze_history_graph((raw, descriptor)))


@pytest.mark.parametrize(
    "stage", ["world_construction", "phase_construction", "seed_init_transition"]
)
def test_world_init_sim_digest_forwarding_reaches_same_immutable_hash(stage):
    _, descriptor, image = frozen()
    _, remainder, _ = adapters()
    phase = SimpleNamespace(_digest=remainder._digest)
    namespace = dict(parameters=remainder, timing=phase)
    adapter = functions(
        f"src/cells/processes/betse_native_parameter_{stage}.py", ("_digest",), namespace
    )
    assert adapter._digest(image[1]) == legacy_digest(descriptor)


@pytest.mark.parametrize("field", ["token", "layout", "scalar_type", "sequence_type", "raw_object"])
def test_original_same_graph_rejects_fresh_live_changes(field):
    raw, descriptor, image = frozen()
    _, _, same = adapters()
    current = copy.deepcopy(descriptor)
    if field == "token":
        current["nodes"][0]["token"] = 7
    elif field == "layout":
        current["nodes"][0]["type"] = "different.source.layout"
    elif field == "scalar_type":
        current["nodes"][0]["token"] = False  # bool must not alias integer zero.
    elif field == "sequence_type":
        current["roots"] = tuple(current["roots"])
        assert base.original_bytes(current) == base.original_bytes(descriptor)
    else:
        raw = (object(), raw[1])
    with pytest.raises(ValueError, match="alias graph"):
        same((raw, current), image)


def test_fresh_live_comparison_never_freezes_encodes_hashes_or_decodes(monkeypatch):
    raw, descriptor, image = frozen()
    _, _, same = adapters()

    def forbidden(*args, **kwargs):
        pytest.fail("The live comparison must not freeze or serialize")

    for name in ("_parts", "_tree", "_encode", "freeze_graph", "freeze_history_graph"):
        monkeypatch.setattr(history, name, forbidden)
    monkeypatch.setattr(history.json, "loads", forbidden)
    monkeypatch.setattr(history.hashlib, "sha256", forbidden)
    for _ in range(10):
        same((raw, descriptor), image)
        assert type(history.history_digest(image[1])) is str


def test_completed_history_never_reenters_generic_tree_or_live_match(monkeypatch):
    _, descriptor, image = frozen()
    constants, remainder, _ = adapters()
    expected = legacy_digest(descriptor)

    def forbidden(*args, **kwargs):
        pytest.fail("Immutable history must not traverse live or generic metadata")

    monkeypatch.setattr(history, "_matches", forbidden)
    constants._digest.__globals__["previous"] = SimpleNamespace(_digest=forbidden)
    for _ in range(25):
        assert remainder._digest(image[1]) == expected


@pytest.mark.parametrize("target", ["json_hook", "capture_limit"])
def test_keyword_default_contents_are_bound_before_capture_or_wire_export(target):
    before = history.history_bindings()
    repeated = history.history_bindings()
    assert len(before) == len(repeated)
    assert all(a is b for a, b in zip(before, repeated, strict=True))
    function, key, replacement = (
        (history.json.loads, "object_hook", lambda value: {"changed": True})
        if target == "json_hook"
        else (history.freeze_history_graph, "limits", (1, 1, 1))
    )
    mapping = function.__kwdefaults__
    original = mapping[key]
    try:
        mapping[key] = replacement
        assert function.__kwdefaults__ is mapping
        current = history.history_bindings()
        assert len(current) == len(before)
        assert any(a is not b for a, b in zip(before, current, strict=True))
    finally:
        # Shared JSON defaults must be restored before the guard/report writer.
        mapping[key] = original
    restored = history.history_bindings()
    assert all(a is b for a, b in zip(before, restored, strict=True))


@pytest.mark.parametrize(
    "change", ["removed", "equal_registry", "equal_slot", "foreign_slot", "forged"]
)
def test_immutable_registry_or_slot_retarget_refuses(change):
    _, _, image = frozen()
    descriptor = image[1]
    row = history._history_entry(descriptor)
    try:
        if change == "removed":
            history._HISTORY_ISSUED.pop(id(descriptor))
        elif change == "equal_registry":
            history._HISTORY_ISSUED[id(descriptor)] = tuple(list(row))
        elif change == "equal_slot":
            object.__setattr__(descriptor, "_seal", tuple(list(row)))
        elif change == "foreign_slot":
            object.__setattr__(descriptor, "_seal", history._history_entry(frozen()[2][1]))
        else:
            descriptor = object.__new__(history.HistoricalDescriptor)
        with pytest.raises((ValueError, AttributeError)):
            history.history_digest(descriptor)
    finally:
        history._HISTORY_ISSUED[id(image[1])] = row
        object.__setattr__(image[1], "_seal", row)


def test_registry_replacement_is_rejected_before_foreign_callable():
    _, _, image = frozen()
    descriptor, calls = image[1], []
    row = history._history_entry(descriptor)
    try:
        history._HISTORY_ISSUED[id(descriptor)] = (lambda: calls.append(1), *row[1:])
        with pytest.raises(ValueError):
            history.history_digest(descriptor)
        assert not calls
    finally:
        history._HISTORY_ISSUED[id(descriptor)] = row


def test_no_hidden_mutable_tree_or_authoritative_export_and_weak_cleanup():
    _, _, image = frozen()
    descriptor, identity = image[1], id(image[1])
    row = history._history_entry(descriptor)
    pending = [row[2]]
    while pending:
        value = pending.pop()
        assert type(value) in (tuple, str, int, bool, type(None))
        if type(value) is tuple:
            pending.extend(value)
    exported = history.history_wire_descriptor(descriptor)
    exported["nodes"].clear()
    assert history.history_wire_descriptor(descriptor)["nodes"]
    with pytest.raises(AttributeError):
        descriptor._seal = row
    del image, descriptor
    gc.collect()
    assert identity not in history._HISTORY_ISSUED


@pytest.mark.parametrize(
    "field", ["matcher", "class_dispatch", "digest", "quote", "global", "file"]
)
def test_existing_binding_roster_can_observe_helper_and_class_drift(monkeypatch, field):
    before = history.history_bindings()
    # The JSON helper is shared with the forensic writer; restore before the
    # fixture writes its receipt, rather than waiting for outer fixture cleanup.
    with monkeypatch.context() as patch:
        if field == "matcher":
            patch.setattr(history._matches, "__code__", history._matches.__code__.replace())
        elif field == "class_dispatch":
            patch.setattr(history.HistoricalDescriptor, "__ne__", lambda self, other: False)
        elif field == "digest":
            patch.setattr(history, "history_digest", lambda value: "same-looking")
        elif field == "quote":
            patch.setattr(history.json.encoder, "encode_basestring_ascii", lambda value: '"x"')
        elif field == "global":
            patch.setattr(history, "len", lambda value: 0, raising=False)
        else:
            patch.setattr(history, "__file__", "/different/producer.py")
        after = history.history_bindings()
        assert len(before) != len(after) or any(
            a is not b for a, b in zip(before, after, strict=True)
        )
    assert all(a is b for a, b in zip(history.history_bindings(), before, strict=True))


def test_fresh_opt_in_plan_is_explicit_default_unchanged_and_cannot_relabel():
    constants, _, _ = adapters()
    legacy, selected = SimpleNamespace(), SimpleNamespace(immutable_history=True)
    plan = {"native": "unchanged"}
    graph = ((), base.graph_descriptor())
    assert constants._history_plan(legacy, plan) is plan
    assert constants._historical_capture(legacy, graph) is graph
    frozen_graph = constants._historical_capture(selected, graph)
    assert type(frozen_graph[1]) is history.HistoricalDescriptor
    source = constants._history_plan(selected, plan)
    assert source["historical_metadata"]["format"] == history.HISTORY_FORMAT
    assert source["historical_metadata"]["fresh_live_capture_unchanged"] is True
    selected.immutable_history = False
    assert legacy_digest(constants._history_plan(selected, plan)) != legacy_digest(source)
    selected.immutable_history = 1
    with pytest.raises(ValueError):
        constants._history_mode(selected)


@pytest.mark.parametrize("fault", ["before_publication", "after_publication"])
def test_issuance_observer_failure_keeps_original_error_raw_graph_and_no_usable_image(fault):
    graph, primary, cause = (
        ((object(),), base.graph_descriptor()),
        base.FalseyError("capture"),
        KeyError("cause"),
    )
    prior, seen = sys.getprofile(), []

    def profile(frame, event, arg):
        if prior is not None:
            prior(frame, event, arg)
        if frame.f_code is history._history_entry.__code__ and event == (
            "call" if fault == "before_publication" else "return"
        ):
            seen.append(frame.f_locals["descriptor"])
            raise primary from cause

    try:
        sys.setprofile(profile)
        with pytest.raises(history.MetadataRejected) as caught:
            history.freeze_history_graph(graph)
    finally:
        sys.setprofile(prior)
    assert caught.value.source_error is caught.value.__cause__ is primary
    assert primary.__cause__ is cause and caught.value.graph is graph
    assert len(seen) == 1 and id(seen[0]) not in history._HISTORY_ISSUED
    with pytest.raises(ValueError):
        history.history_digest(seen[0])


def test_cross_producer_integration_is_local_and_live_capture_functions_stay_unwrapped():
    constants = ast.parse((ROOT / CONSTANTS).read_bytes())
    remainder = ast.parse((ROOT / REMAINDER).read_bytes())
    cn = {n.name: n for n in constants.body if isinstance(n, ast.FunctionDef)}
    rn = {n.name: n for n in remainder.body if isinstance(n, ast.FunctionDef)}
    for node in (cn["_fields"], cn["_remainder_capture"], rn["_capture"]):
        text = ast.unparse(node)
        assert (
            "graphs.capture" in text and "historical_capture" not in text and "freeze" not in text
        )
    prepare = cn["prepare"]
    defaults = dict(
        zip((x.arg for x in prepare.args.kwonlyargs), prepare.args.kw_defaults, strict=True)
    )
    assert ast.literal_eval(defaults["immutable_history"]) is False
    assert "_historical_capture(base, _remainder_capture" in ast.unparse(cn["_remainder_enter"])
    assert "_same_graph(context.before_graph, base.after_graph)" in ast.unparse(
        cn["_remainder_enter"]
    )
    assert "previous._historical_capture(context, _capture(context))" in ast.unparse(
        rn["complete_load"]
    )
    assert (
        "previous._history_mode(context) is not previous._history_mode(context.parent)"
        in ast.unparse(rn["_history"])
    )
    assert "_same_graph(_capture(context), context.after_graph)" in ast.unparse(rn["_validate"])
    qualifier = (ROOT / QUALIFIER).read_text()
    assert "history_metadata.history_wire_descriptor(value[1])" in qualifier
    assert "object_identities=tuple(id(v) for v in value[0])" in qualifier


@pytest.mark.parametrize("mode", ["legacy", "immutable"])
def test_actual_qualifier_wire_expression_keeps_descriptor_and_reference_ids(mode):
    raw, descriptor, image = frozen()
    value = (raw, descriptor) if mode == "legacy" else image
    node = next(
        node
        for node in ast.walk(ast.parse((ROOT / QUALIFIER).read_bytes()))
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Subscript)
            and isinstance(target.value, ast.Name)
            and target.value.id == "graphs"
            for target in node.targets
        )
        and "history_wire_descriptor" in ast.unparse(node.value)
    )
    actual = eval(
        compile(ast.Expression(node.value), "<original-graph-wire-expression>", "eval"),
        dict(history_metadata=history, value=value),
    )
    expected = dict(data=descriptor, object_identities=tuple(id(v) for v in raw))
    assert base.original_bytes(actual) == base.original_bytes(expected)


def test_constants_grant_load_and_fresh_world_comparisons_share_exact_wire():
    constants, remainder, same = adapters()
    enabled = SimpleNamespace(immutable_history=True)
    raw, descriptor = (object(), object()), base.graph_descriptor()
    constants_after = constants._historical_capture(enabled, (raw, descriptor))
    grant_before = constants._historical_capture(enabled, (raw, copy.deepcopy(descriptor)))
    same(grant_before, constants_after)
    assert constants._digest(grant_before[1]) == constants._digest(constants_after[1])
    after = copy.deepcopy(descriptor)
    after["roots"].append(("ions", ("ref", 6)))
    after["nodes"].append(dict(token=6, type="dict", dict_storage=[]))
    grant_after = constants._historical_capture(enabled, (raw, after))
    load_after = constants._historical_capture(enabled, (raw, copy.deepcopy(after)))
    same(load_after, grant_after)
    same((raw, copy.deepcopy(after)), load_after)  # Existing world _bytes path.
    assert remainder._digest(load_after[1]) == constants._digest(grant_after[1])
    assert type(descriptor) is type(after) is dict


def test_comparison_refuses_slot_drift_after_match_without_later_delegate(monkeypatch):
    raw, descriptor, image = frozen()
    _, _, same = adapters()
    original, row, calls = history._matches, history._history_entry(image[1]), []

    def matches(actual, tree):
        calls.append("match")
        result = original(actual, tree)
        object.__setattr__(image[1], "_seal", tuple(list(row)))
        return result

    monkeypatch.setattr(history, "_matches", matches)
    try:
        with pytest.raises(ValueError, match="association"):
            same((raw, descriptor), image)
        assert calls == ["match"]
    finally:
        object.__setattr__(image[1], "_seal", row)


def _measure(directory):
    constants, _, same = adapters()
    raw, descriptor = (object(), object()), base.graph_descriptor()
    descriptor["synthetic_rows"] = [
        {"token": i, "items": [("ref", j) for j in range(8)]} for i in range(512)
    ]
    before = (raw, descriptor)
    started = time.perf_counter_ns()
    after = history.freeze_history_graph(before)
    frozen_ns = time.perf_counter_ns() - started
    baseline = functions(
        "src/cells/processes/betse_native_parameter_record_digest.py",
        ("_metadata_tree",),
        dict(_EXIT=object(), _FALLBACK=object(), _PACK=struct.pack),
    )
    expected = legacy_digest(descriptor)
    samples = []
    for repeat in range(7):
        for mode in ("baseline", "immutable") if repeat % 2 == 0 else ("immutable", "baseline"):
            started = time.perf_counter_ns()
            for _ in range(2):
                for _ in range(7):
                    if mode == "baseline":
                        tree = baseline._metadata_tree(descriptor, (131072, 128, 8 * 2**20))
                        value = legacy_digest(tree)
                    else:
                        value = constants._digest(after[1])
                    assert value == expected
                same((raw, descriptor), before if mode == "baseline" else after)
            samples.append(
                dict(mode=mode, repeat=repeat, cycles=2, wall_ns=time.perf_counter_ns() - started)
            )
    medians = {
        mode: statistics.median(r["wall_ns"] / r["cycles"] for r in samples if r["mode"] == mode)
        for mode in ("baseline", "immutable")
    }
    (directory / "measurement.json").write_text(
        json.dumps(
            dict(
                scope=(
                    "Seven historical graph checks plus one fresh comparison; "
                    "other owner/source checks excluded"
                ),
                samples=samples,
                median_ns_per_cycle=medians,
                one_time_freeze_ns=frozen_ns,
                fresh_capture_or_native_execution=False,
                metadata_sha256=hashlib.sha256(Path(history.__file__).read_bytes()).hexdigest(),
            ),
            sort_keys=True,
            indent=2,
        )
    )


def measure(directory):
    directory = Path(directory)
    directory.mkdir()
    if os.sched_getaffinity(0) != {3}:
        raise ValueError("CPU3 metadata measurement required")
    patches = pytest.MonkeyPatch()
    blockade = base.blocked.__wrapped__(patches, directory)
    next(blockade)
    try:
        _measure(directory)
    finally:
        try:
            next(blockade)
        except StopIteration:
            pass
        finally:
            patches.undo()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--measure", required=True)
    measure(parser.parse_args().measure)
