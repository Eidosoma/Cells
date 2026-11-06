"""Dependency projection controls: source is parsed, never imported or applied."""

import ast
import copy
import json
import sys
from pathlib import Path

import pytest

from validation.betse import native_init_demo_adoption as adoption


def example():
    sources = {
        "leaf.py": b"VALUE = 5\nraise RuntimeError('candidate source executed')\n",
        "caller.py": (
            b"HELPER = REVIEW = None\n"
            b"MODULES = {'leaf': 'leaf.py', 'helper': 'helper.py'}\n"
            b"PINS = dict.fromkeys(MODULES)\n"
            b"HELD = {'native': None}\n"
            b"def body():\n    return 'unchanged'\n"
        ),
        "helper.py": (
            b"LEAF = None\nBACK = None\nREVIEW = None\n"
            b"class Uncalled:\n    def body(self):\n        raise RuntimeError('executed')\n"
        ),
    }
    plan = {
        "module_aliases": {"L": "leaf.py", "A": "caller.py", "B": "helper.py"},
        "recipes": {
            "BT": {
                "target": "helper.py",
                "excluded_slots": ["BACK", "REVIEW"],
                "binding_kind": "example_helper@1",
            }
        },
        "required_declaration_splits": [{"path": "caller.py", "slots": ["HELPER", "REVIEW"]}],
        "required_assignments": {
            "A": {
                "slots": {
                    "HELPER": "T(BT)",
                    "REVIEW": "R_B",
                    "PINS[leaf]": "H(L)",
                    "PINS[helper]": "T(BT)",
                }
            },
            "B": {"slots": {"LEAF": "H(L)", "BACK": "H(A)", "REVIEW": "R_B"}},
        },
        "topological_order": ["L", "BT", "A", "B"],
    }
    return plan, sources, {"R_B": "a" * 64}


def value(raw, name):
    return ast.literal_eval(adoption.node_at(raw, (name,)))


def test_acyclic_backrefs_preserve_source_and_never_execute_or_adopt():
    plan, sources, reviews = example()
    before = copy.deepcopy((plan, sources, reviews))
    candidate, report = adoption.project(
        plan, sources, reviews, preserve=(("caller.py", ("HELD",)),)
    )
    assert (plan, sources, reviews) == before
    assert candidate["leaf.py"] is sources["leaf.py"]
    assert value(candidate["helper.py"], "BACK") == adoption.digest(candidate["caller.py"])
    assert value(candidate["helper.py"], "LEAF") == adoption.digest(sources["leaf.py"])
    assert value(candidate["caller.py"], "HELPER") == adoption.byte_template(
        candidate["helper.py"], slots=("BACK", "REVIEW"), kind="example_helper@1"
    )
    assert value(candidate["caller.py"], "PINS") == {
        "leaf": adoption.digest(candidate["leaf.py"]),
        "helper": value(candidate["caller.py"], "HELPER"),
    }
    assert value(candidate["caller.py"], "HELD") == {"native": None}
    assert report["all_operations_reversible"]
    assert report["all_other_bytes_and_function_class_import_ASTs_exact"]
    assert not report["source_files_written"]
    assert not report["actual_execution_released"]
    assert not report["reviews_authenticated_by_projection"]


def test_operations_reverse_all_declared_bytes_including_utf8_offsets():
    plan, sources, reviews = example()
    sources["helper.py"] = b"caption = '\xc3\xb8'; LEAF = None\nBACK = None\nREVIEW = None\n"
    candidate, report = adoption.project(plan, sources, reviews)
    reverse = dict(candidate)
    for row in reversed(report["literal_operations"]):
        raw = reverse[row["path"]]
        start, after = row["start"], row["after"].encode()
        assert raw[start : start + len(after)] == after
        reverse[row["path"]] = raw[:start] + row["before"].encode() + raw[start + len(after) :]
    assert reverse == sources


@pytest.mark.parametrize("literal", ["None", repr("1" * 64), '"' + "f" * 64 + '"'])
def test_template_excludes_only_pin_literal(literal):
    raw = ("PIN = " + literal + "  # retained\ndef body():\n    return 1\n").encode()
    canonical = b"PIN = None  # retained\ndef body():\n    return 1\n"
    expected = adoption.digest(b"source@1\0" + canonical)
    assert adoption.byte_template(raw, slots=("PIN",), kind="source@1") == expected
    assert adoption.byte_template(raw + b"# changed\n", slots=("PIN",), kind="source@1") != expected


@pytest.mark.parametrize(
    "raw",
    [
        b"PIN = None\nPIN = None\n",
        b"PIN = None\ndef hidden():\n    PIN = None\n",
        b"PIN = 3\n",
        b"PIN = 'not a SHA256'\n",
        ("PIN = " + repr("F" * 64) + "\n").encode(),
        ("PIN = '''" + "f" * 64 + "'''\n").encode(),
        ("PIN = '" + "f" * 32 + "' '" + "f" * 32 + "'\n").encode(),
        b"PIN: str = None\n",
        b"OTHER = None\n",
    ],
)
def test_template_refuses_noncanonical_or_ambiguous_declarations(raw):
    with pytest.raises(ValueError):
        adoption.byte_template(raw, slots=("PIN",), kind="source@1")


@pytest.mark.parametrize("slots", [(), ("PIN", "PIN"), ["PIN"], (3,)])
def test_template_requires_exact_nonempty_unique_roster(slots):
    with pytest.raises(ValueError):
        adoption.byte_template(b"PIN = None\n", slots=slots, kind="source@1")


@pytest.mark.parametrize("change", ["missing", "extra", "duplicate_path"])
def test_project_refuses_source_roster_drift(change):
    plan, sources, reviews = example()
    if change == "missing":
        sources.pop("leaf.py")
    elif change == "extra":
        sources["foreign.py"] = b"VALUE = 0\n"
    else:
        plan["module_aliases"]["X"] = "leaf.py"
        plan["topological_order"].append("X")
    with pytest.raises(ValueError, match="source roster"):
        adoption.project(plan, sources, reviews)


@pytest.mark.parametrize(
    "order", [["L", "BT", "A"], ["L", "BT", "A", "B", "B"], ["L", "BT", "B", "A"]]
)
def test_project_refuses_omitted_repeated_or_cyclic_order(order):
    plan, sources, reviews = example()
    plan["topological_order"] = order
    with pytest.raises(ValueError):
        adoption.project(plan, sources, reviews)


def test_project_refuses_late_changed_full_hash_even_if_dependencies_resolve():
    plan, sources, reviews = example()
    # A template cannot be finalized before a non-excluded dependency changes.
    plan["recipes"]["BT"]["excluded_slots"] = ["LEAF", "BACK", "REVIEW"]
    plan["topological_order"] = ["BT", "L", "A", "B"]
    # The order is valid when all future changes are explicitly excluded.
    adoption.project(plan, sources, reviews)
    # Hidden double targeting changes an already computed template/full digest.
    plan["recipes"]["AT"] = {
        "target": "caller.py",
        "excluded_slots": ["REVIEW"],
        "binding_kind": "caller@1",
    }
    plan["topological_order"].append("AT")
    plan["required_assignments"]["A"]["slots"]["REVIEW"] = "T(AT)"
    with pytest.raises(ValueError, match="Unresolved or cyclic"):
        adoption.project(plan, sources, reviews)


@pytest.mark.parametrize("expression", ["R_missing", "H(absent)", "T(absent)"])
def test_project_never_silently_accepts_missing_review_or_dependency(expression):
    plan, sources, reviews = example()
    plan["required_assignments"]["A"]["slots"]["REVIEW"] = expression
    with pytest.raises(ValueError):
        adoption.project(plan, sources, reviews)


def test_held_slot_refuses_even_an_otherwise_valid_planned_change():
    plan, sources, reviews = example()
    plan["required_assignments"]["A"]["slots"]["HELD[native]"] = "R_B"
    with pytest.raises(ValueError, match="held or legacy"):
        adoption.project(plan, sources, reviews, preserve=(("caller.py", ("HELD",)),))


def test_whole_mapping_review_is_materialized_without_importing_roster():
    plan, sources, reviews = example()
    slots = plan["required_assignments"]["A"]["slots"]
    slots.pop("PINS[leaf]")
    slots.pop("PINS[helper]")
    slots["PINS"] = "leaf=H(L), helper=R_B"
    candidate, _ = adoption.project(plan, sources, reviews)
    assert value(candidate["caller.py"], "PINS") == {
        "leaf": adoption.digest(sources["leaf.py"]),
        "helper": reviews["R_B"],
    }


@pytest.mark.parametrize("replacement", [b"make_pins()", b"dict.fromkeys(make_modules())"])
def test_materialization_does_not_evaluate_source_expressions(replacement):
    plan, sources, reviews = example()
    sources["caller.py"] = sources["caller.py"].replace(b"dict.fromkeys(MODULES)", replacement)
    with pytest.raises(ValueError, match="dict.fromkeys"):
        adoption.project(plan, sources, reviews)


def test_duplicate_map_member_is_not_a_selected_literal():
    plan, sources, reviews = example()
    sources["caller.py"] = sources["caller.py"].replace(
        b"dict.fromkeys(MODULES)", b"{'leaf': None, 'leaf': None, 'helper': None}"
    )
    with pytest.raises(ValueError, match="mapping member"):
        adoption.project(plan, sources, reviews)


def test_review_hash_must_be_exact_but_acceptance_is_external():
    plan, sources, reviews = example()
    reviews["R_B"] = "approved"
    with pytest.raises(ValueError, match="review hashes"):
        adoption.project(plan, sources, reviews)


@pytest.mark.parametrize("name", ["H(B)", "T(BT)", "plain_text", 1])
def test_review_names_cannot_override_dependency_edges_or_hide_a_cycle(name):
    plan, sources, reviews = example()
    # A->B and B->A is cyclic: a review cannot stand in for either hash edge.
    plan["required_assignments"]["A"]["slots"]["HELPER"] = "H(B)"
    reviews[name] = "f" * 64
    with pytest.raises(ValueError, match="Review names"):
        adoption.project(plan, sources, reviews)


def test_bounded_source_and_exact_bytes_required():
    with pytest.raises(ValueError):
        adoption.byte_template(b"#" * (2**21 + 1), slots=("PIN",), kind="x")
    with pytest.raises(ValueError):
        adoption.byte_template(bytearray(b"PIN = None\n"), slots=("PIN",), kind="x")


def test_review_document_projection_is_explicit_reversible_and_does_not_open_files(monkeypatch):
    plan, sources, reviews = example()
    plan["required_assignments"]["A"]["slots"]["REVIEW"] = "D(R_B)"
    documents = {"R_B": {"path": "/unopened/review=with,spaces.json", "sha256": reviews["R_B"]}}
    before = copy.deepcopy((plan, sources, reviews, documents))

    def forbidden(*args, **kwargs):
        raise AssertionError("Projection must not read or authenticate review files")

    monkeypatch.setattr("builtins.open", forbidden)
    candidate, report = adoption.project(plan, sources, reviews, review_documents=documents)
    assert value(candidate["caller.py"], "REVIEW") == documents["R_B"]
    assert value(candidate["helper.py"], "REVIEW") == reviews["R_B"]
    assert report["all_operations_reversible"]
    assert not report["reviews_authenticated_by_projection"]
    assert not report["source_files_written"] and not report["actual_execution_released"]
    assert (plan, sources, reviews, documents) == before
    report["review_documents"]["R_B"]["path"] = "/changed.json"
    assert documents == before[3]


def test_empty_review_documents_preserve_legacy_projection_exactly():
    plan, sources, reviews = example()
    assert adoption.project(plan, sources, reviews) == adoption.project(
        plan, sources, reviews, review_documents={}
    )


@pytest.mark.parametrize("expression", ["D(R_B)", "D(R_missing)", "D(H(B))"])
def test_missing_or_malformed_review_documents_never_become_literal_values(expression):
    plan, sources, reviews = example()
    plan["required_assignments"]["A"]["slots"]["REVIEW"] = expression
    with pytest.raises(ValueError):
        adoption.project(plan, sources, reviews)


@pytest.mark.parametrize(
    "documents",
    [
        [],
        {"R_unknown": {"path": "/review.json", "sha256": "a" * 64}},
        {"R_B": {"path": "/review.json", "sha256": "b" * 64}},
        {"R_B": {"path": "/review.json", "sha256": "a" * 64, "accepted": True}},
        {"R_B": {"path": "/review.json"}},
    ],
)
def test_review_document_cannot_replace_hash_authority_or_add_acceptance(documents):
    plan, sources, reviews = example()
    with pytest.raises(ValueError, match="review document|Review document"):
        adoption.project(plan, sources, reviews, review_documents=documents)


@pytest.mark.parametrize(
    "path",
    [
        "relative.json",
        "/a/../b.json",
        "/a/./b.json",
        "/a//b.json",
        "//review.json",
        "/",
        "/a/",
        "/a\n.json",
    ],
)
def test_review_document_requires_an_unambiguous_absolute_path(path):
    plan, sources, reviews = example()
    with pytest.raises(ValueError, match="Canonical absolute"):
        adoption.project(
            plan,
            sources,
            reviews,
            review_documents={"R_B": {"path": path, "sha256": reviews["R_B"]}},
        )


@pytest.fixture
def sim_projection(tmp_path):
    """Frozen checkout bytes and clearly synthetic review data; no adoption."""
    root = Path(__file__).resolve().parents[2]
    plan = json.loads((root / "validation/betse/native_sim_demo_adoption_plan.json").read_text())
    sources = {path: (root / path).read_bytes() for path in plan["module_aliases"].values()}
    reviews = {
        token: adoption.digest(("metadata-only-unaccepted-review:" + token).encode())
        for token in plan["required_review_tokens"]
    }
    documents = {
        token: {"path": "/metadata-only-unopened/" + token + ".json", "sha256": reviews[token]}
        for token in plan["required_review_documents"]
    }
    producer_names = {path.removeprefix("src/")[:-3].replace("/", ".") for path in sources}
    attempts, prior = [], (sys.getprofile(), sys.gettrace())

    def profile(frame, event, arg):
        if prior[0] is not None:
            prior[0](frame, event, arg)
        if event == "call":
            name = frame.f_globals.get("__name__", "")
            forbidden = (
                name in producer_names
                or name.startswith("betse.")
                or (name == "random" and frame.f_code.co_name in ("seed", "getstate", "random"))
            )
        elif event == "c_call":
            module = getattr(arg, "__module__", "") or ""
            forbidden = module in ("random", "_random") or module.startswith("numpy.random")
            name = frame.f_globals.get("__name__", "") if forbidden else ""
        else:
            return
        if forbidden:
            attempts.append((name, event, frame.f_code.co_name))
            raise AssertionError("Metadata projection must not enter a producer/native/RNG")

    try:
        sys.setprofile(profile)
        yield plan, sources, reviews, documents
    finally:
        sys.setprofile(prior[0])
        restored = sys.getprofile() is prior[0] and sys.gettrace() is prior[1]
        (tmp_path / "metadata-blocked.json").write_text(
            json.dumps(
                dict(
                    attempted=attempts, both_hooks_restored=restored, actual_review_acceptance=False
                )
            )
        )
        assert restored and not attempts


def _project_sim(values):
    plan, sources, reviews, documents = values
    return adoption.project(
        plan,
        sources,
        reviews,
        preserve=tuple((row["path"], tuple(row["slot"])) for row in plan["preserve"]),
        review_documents=documents,
    )


def _sim_runtime_closure(plan, candidate, reviews):
    paths = plan["module_aliases"]
    parameter = adoption.digest(candidate[paths["parameter_qualifier"]])
    callback, geometry, demo = (
        candidate[paths[name]] for name in ("callback_prelude", "geometry_qualifier", "demo")
    )
    assert value(callback, "RUNTIME_SOURCE_SHA256") == parameter
    assert value(geometry, "PARAMETER_ENTRY_SOURCE_SHA256") == parameter
    assert value(callback, "RUNTIME_REVIEW_SHA256") == reviews["R_parameter_qualifier"]
    assert value(geometry, "PARAMETER_ENTRY_REVIEW_SHA256") == reviews["R_parameter_qualifier"]
    assert value(geometry, "EVIDENCE_SOURCE_SHA256") == adoption.digest(
        candidate[paths["evidence"]]
    )
    assert value(candidate[paths["inputs"]], "PARAMETER_METADATA_SHA256") == parameter
    assert value(demo, "SOURCE_PINS")["parameters"] == parameter
    assert value(demo, "SOURCE_PINS")["callback"] == adoption.digest(callback)
    assert value(demo, "SOURCE_PINS")["geometry"] == adoption.digest(geometry)
    assert value(demo, "REVIEW_PINS")["callback"] == reviews["R_callback_prelude"]
    assert value(demo, "REVIEW_PINS")["geometry"] == reviews["R_geometry_qualifier"]
    assert value(demo, "EVIDENCE_SOURCE_SHA256") == adoption.digest(candidate[paths["evidence"]])
    assert value(demo, "CAPTURE_BUDGET_SHA256") == adoption.digest(
        candidate[paths["capture_budget"]]
    )


def test_sim_adoption_current_checkout_projection_has_complete_runtime_closure(
    sim_projection, tmp_path
):
    plan, sources, reviews, documents = sim_projection
    before = copy.deepcopy(sim_projection)
    candidate, report = _project_sim(sim_projection)
    _sim_runtime_closure(plan, candidate, reviews)
    assert sim_projection == before
    assert report["all_operations_reversible"]
    assert report["all_other_bytes_and_function_class_import_ASTs_exact"]
    assert not report["source_files_written"] and not report["actual_execution_released"]
    assert not report["reviews_authenticated_by_projection"]
    assert report["review_documents"] == documents
    assert len(plan["recipes"]) == 13
    assert set(report["normalized_interfaces"]) == set(plan["recipes"])
    # Native callback factory pins are unchanged literal input, not a new
    # dict(keyword) materialization or a silently expanded source recipe.
    callback = plan["module_aliases"]["callback_prelude"]
    assert ast.dump(adoption.node_at(sources[callback], ("SOURCE_PINS",))) == ast.dump(
        adoption.node_at(candidate[callback], ("SOURCE_PINS",))
    )
    (tmp_path / "current-runtime-closure.json").write_text(
        json.dumps(
            dict(
                full_hashes=report["full_hashes"],
                review_tokens=sorted(reviews),
                actual_execution=False,
                review_acceptance=False,
                direct_parameter_runtime_consumers=[
                    "callback_prelude",
                    "geometry_qualifier",
                    "inputs",
                ],
                operations=report["literal_operations"],
            )
        )
    )


def test_sim_adoption_selected_declared_validation_runtime_edges_cannot_be_omitted(
    sim_projection, tmp_path
):
    plan, sources, _, _ = sim_projection
    aliases = plan["module_aliases"]
    names = {
        path.removeprefix("src/")[:-3].replace("/", "."): alias for alias, path in aliases.items()
    }
    found, edges = set(), []
    for alias, path in aliases.items():
        declarations = {
            target.id: node.value
            for node in ast.parse(sources[path]).body
            if isinstance(node, ast.Assign)
            for target in node.targets
            if isinstance(target, ast.Name)
        }
        for name, node in declarations.items():
            if (
                (not name.endswith("_MODULE") and name != "MODULE")
                or not isinstance(node, ast.Constant)
                or type(node.value) is not str
                or node.value not in names
                or not node.value.startswith("validation.")
                or names[node.value] == alias
            ):
                continue
            prefix, target = name.removesuffix("_MODULE"), names[node.value]
            if name == "MODULE" and "OBSERVER_SHA256" in declarations:
                prefix = "OBSERVER"
            slot = next(
                (
                    prefix + suffix
                    for suffix in ("_SOURCE_SHA256", "_SHA256")
                    if prefix + suffix in declarations
                ),
                None,
            )
            if slot is None:
                continue
            review = next(
                (
                    prefix + suffix
                    for suffix in ("_REVIEW_SHA256", "_REVIEW")
                    if prefix + suffix in declarations
                ),
                None,
            )
            edges.append((alias, name, target, slot, review))
            found.add((alias, name, target))
    (tmp_path / "declared-validation-runtime-edges.json").write_text(json.dumps(edges))
    for alias, _, target, slot, review in edges:
        slots = plan["required_assignments"][alias]["slots"]
        assert slots.get(slot) == "H(" + target + ")"
        if review is not None:
            expression = slots[review]
            if expression.startswith("D("):
                assert expression[2:-1] in plan["required_review_documents"]
            else:
                assert expression in plan["required_review_tokens"]
    assert found == {
        ("callback_prelude", "RUNTIME_MODULE", "parameter_qualifier"),
        ("geometry_qualifier", "PARAMETER_ENTRY_MODULE", "parameter_qualifier"),
        ("geometry_qualifier", "EVIDENCE_MODULE", "evidence"),
        ("demo", "EVIDENCE_MODULE", "evidence"),
        ("demo", "CAPTURE_BUDGET_MODULE", "capture_budget"),
        ("demo", "SIM_MODULE", "sim_orchestration"),
        ("sim_observation_transport", "MODULE", "sim_observer"),
    }


@pytest.mark.parametrize(
    "alias,slot",
    (
        ("callback_prelude", "RUNTIME_SOURCE_SHA256"),
        ("callback_prelude", "RUNTIME_REVIEW_SHA256"),
        ("geometry_qualifier", "PARAMETER_ENTRY_SOURCE_SHA256"),
        ("geometry_qualifier", "PARAMETER_ENTRY_REVIEW_SHA256"),
    ),
)
def test_sim_adoption_stale_runtime_literal_rebound_before_final_consumer_hash(
    alias, slot, sim_projection, tmp_path
):
    plan, sources, reviews, _ = sim_projection
    path = plan["module_aliases"][alias]
    raw = sources[path]
    node = adoption.node_at(raw, (slot,))
    start, stop = adoption._span(raw, node)
    stale = "9a2623cbc466cd082e2d5472e946fb64b73366b2928eaaca8b10e95356e4e90e"
    sources[path] = raw[:start] + repr(stale).encode() + raw[stop:]
    assert value(sources[path], slot) == stale
    candidate, report = _project_sim(sim_projection)
    _sim_runtime_closure(plan, candidate, reviews)
    operation = next(
        row for row in report["literal_operations"] if row["path"] == path and row["label"] == slot
    )
    assert ast.literal_eval(operation["before"]) == stale
    assert ast.literal_eval(operation["after"]) != stale
    # Deliberately corrupt the projected data, without importing a consumer:
    # the complete declared correspondence cannot then be asserted.
    corrupt = dict(candidate)
    node = adoption.node_at(corrupt[path], (slot,))
    start, stop = adoption._span(corrupt[path], node)
    corrupt[path] = corrupt[path][:start] + repr(stale).encode() + corrupt[path][stop:]
    with pytest.raises(AssertionError):
        _sim_runtime_closure(plan, corrupt, reviews)
    (tmp_path / "stale-runtime-repair.json").write_text(
        json.dumps(
            dict(
                alias=alias,
                slot=slot,
                old=stale,
                final=ast.literal_eval(operation["after"]),
                final_consumer=report["full_hashes"]["demo"],
                actual_producer_entries=0,
            )
        )
    )


def test_sim_adoption_changed_parameter_leaf_propagates_through_both_runtime_consumers(
    sim_projection,
):
    plan, sources, reviews, _ = sim_projection
    before, _ = _project_sim(sim_projection)
    path = plan["module_aliases"]["parameter_qualifier"]
    sources[path] += b"\n# metadata-only source-byte dependency probe; never executed\n"
    after, report = _project_sim(sim_projection)
    _sim_runtime_closure(plan, after, reviews)
    for alias in (
        "parameter_qualifier",
        "callback_prelude",
        "geometry_qualifier",
        "inputs",
        "demo",
    ):
        path = plan["module_aliases"][alias]
        assert adoption.digest(before[path]) != adoption.digest(after[path])
    assert report["all_operations_reversible"]


@pytest.mark.parametrize(
    "token", ("R_parameter_qualifier", "R_callback_prelude", "R_geometry_qualifier")
)
def test_sim_adoption_missing_runtime_or_consumer_review_refuses(token, sim_projection):
    _, _, reviews, _ = sim_projection
    reviews.pop(token)
    with pytest.raises(ValueError, match="Unknown dependency or review"):
        _project_sim(sim_projection)


@pytest.mark.parametrize("consumer", ("callback_prelude", "geometry_qualifier"))
def test_sim_adoption_runtime_leaf_must_be_sealed_before_consumer(consumer, sim_projection):
    plan, _, _, _ = sim_projection
    order = plan["topological_order"]
    order.remove(consumer)
    order.insert(order.index("parameter_qualifier"), consumer)
    with pytest.raises(
        ValueError, match=r"Unresolved or cyclic dependency: H\(parameter_qualifier\)"
    ):
        _project_sim(sim_projection)
