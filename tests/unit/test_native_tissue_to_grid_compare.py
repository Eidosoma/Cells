"""Typed-byte synthetic controls; no NumPy, interpolation or owner hydration."""

import copy
import json
import struct
from types import SimpleNamespace as NS

import pytest

from tests.unit import test_native_multi_cell_caller_compare as f
from tests.unit import test_native_multi_cell_environment_compare as environment
from validation.betse import native_tissue_to_grid_compare as c


def seal(capture):
    trial = capture["trial"]
    trial["request_identity"] = c._digest(capture["request"])
    trial["identity"] = c._digest(
        dict(
            law=c.LAW,
            request=trial["request_identity"],
            parent=trial["parent_identity"],
            before=trial["before"]["identity"],
            after=trial["after"]["identity"],
            results=[[name, value["identity"]] for name, value in trial["results"]],
            events=trial["events"],
            work=trial["work"],
            warnings=trial["warnings"],
            source_completed=trial["source_completed"],
            failure_stage=trial["failure_stage"],
            invalidated_owners=capture["request"]["invalidated_owners"],
            physical_field_phase_admitted=False,
        )
    )


def pair():
    node, column = f.column("caller_values", values=(1.0, -0.0))
    indices, indices_column = f.column("cell_i", (0.0, 1.0))
    raw = struct.pack("<qq", 0, 1)
    indices["source_layout"]["dtype"] = "<i8"
    indices["sha256"] = f.digest(raw)
    indices_column["values"].update(dtype="<i8", raw_bytes_hex=raw.hex())
    retired = dict(kind="list", items=[f.scalar(0), f.scalar(1)])
    caller = f.mapping(
        [("original_values", node), ("cell_i", indices), ("all_points_cell_i", retired)]
    )
    before = f.cache(
        f.mapping(
            [
                ("poisson", f.scalar("a" * 64)),
                ("caller", caller),
                ("retained_tail", f.scalar(None)),
                ("helpers", dict(kind="list", items=[])),
            ]
        ),
        [column, indices_column],
    )
    probe_inputs = f.cache(
        dict(
            kind="list",
            items=[
                f.mapping(
                    [
                        ("data", dict(kind="list", items=[f.scalar(1.0), f.scalar(2.0)])),
                        ("target_points", f.scalar(None)),
                        ("data_factor", f.scalar(1)),
                    ]
                )
                for _ in range(4)
            ],
        )
    )
    results = []
    for name in c.native.PROBE_POLICY["names"]:
        values = (1.0, -0.0) if name.endswith("1d") else (1.0, -0.0, -1.0, 0.0)
        node, col = f.column(
            name,
            values,
            shape=(2,) if name.endswith("1d") else (2, 2),
            strides=(8,) if name.endswith("1d") else (16, 8),
            f=name.endswith("1d"),
        )
        results.append([name, f.cache(node, [col])])
    request = dict(
        law=c.LAW,
        parent="b" * 64,
        probes=[
            dict(
                name=name,
                method="grids" if name.startswith("grid_") else "points",
                inputs="c" * 64,
                interp_method="linear",
            )
            for name in c.native.PROBE_POLICY["names"]
        ],
        native_source_lines=c.native.SOURCE_LINES,
        boundary="selected source",
        metadata_verification="retained exact files",
        invalidated_owners=["held_" + str(i) for i in range(11)],
    )
    trial = dict(
        request_identity="",
        parent_identity="b" * 64,
        before=before,
        after=copy.deepcopy(before),
        results=results,
        events=[],
        work=[],
        warnings=[],
        source_completed=True,
        failure_stage=None,
        identity="",
    )
    owned = dict(
        kind=c.diagnostic.RESULT_KIND,
        probe_policy=copy.deepcopy(c.native.PROBE_POLICY),
        request=request,
        trial=trial,
        inputs=probe_inputs,
        environment_cache=environment.cache(),
        stream_before=f.stream(),
        stream_after=f.stream(),
        work_is_not_independent_cases=True,
    )
    seal(owned)
    native_caller = f.native_cache(f.cache(caller, [column, indices_column]))
    reference = dict(
        kind=c.native.KIND,
        stop_after=c.ENDPOINT,
        status="source_completed",
        source_body_completed=True,
        source_error=None,
        capture_error=None,
        capture_errors=[],
        failed_stage=None,
        environment={},
        before=native_caller,
        after=copy.deepcopy(native_caller),
        results=[[name, f.native_cache(value)] for name, value in results],
        inputs=f.native_cache(probe_inputs),
        stream_before=f.stream(),
        stream_after=f.stream(),
        aliases={name: True for name in c.ALIASES},
        work=[],
        warnings=[],
        original_source_pins=c.native.pins_for(),
        source_sites={},
        probe_policy=copy.deepcopy(c.native.PROBE_POLICY),
        reference_inputs=1,
    )
    return owned, reference


def test_exact_seven_cache_pairs_keep_source_and_domain_outcomes_separate():
    owned, reference = pair()
    original = copy.deepcopy((owned, reference))
    result = c.compare(owned, reference)
    assert result["exact_match"] and result["cache_pairs_compared"] == 7
    assert result["owned_diagnostics"]["domain_mask_gate_passed"] is False
    assert result["physical_geometry_admitted"] is False
    assert (owned, reference) == original


@pytest.mark.parametrize(
    "field", ["all_points_cell_i_is_original", "cell_i_is_tail_asarray_return"]
)
def test_reference_requires_both_distinct_tail_alias_witnesses(field):
    owned, reference = pair()
    reference["aliases"][field] = False
    result = c.compare(owned, reference)
    assert result["exact_match"] is False
    assert result["differences"][0]["reason"] == "incomplete_original_source_or_capture"


def test_old_alias_schema_cannot_claim_completed_tail_conversion():
    owned, reference = pair()
    del reference["aliases"]["cell_i_is_tail_asarray_return"]
    with pytest.raises(ValueError):
        c.compare(owned, reference)


@pytest.mark.parametrize("field", ["cell_i", "all_points_cell_i"])
def test_tail_typed_cache_comparison_preserves_list_ndarray_distinction(field):
    owned, reference = pair()
    values = dict((k["value"], v) for k, v in reference["before"]["tree"]["values"])
    assert values["cell_i"]["type"] == "array" and values["all_points_cell_i"]["type"] == "list"
    other = "cell_i" if field == "all_points_cell_i" else "all_points_cell_i"
    before = owned["trial"]["before"]
    caller = next(
        v for k, v in json.loads(before["descriptor_json"])["items"] if k["value"] == "caller"
    )
    typed = dict((k["value"], v) for k, v in caller["items"])
    for entry in caller["items"]:
        if entry[0]["value"] == field:
            entry[1] = copy.deepcopy(typed[other])
    # Re-encode the complete wrong source record with proper column traversal:
    # the refusal must concern list/ndarray semantics, not orphaned columns.
    wrong = f.native_cache(f.cache(caller, before["columns"]))
    reference.update(before=wrong, after=copy.deepcopy(wrong))
    result = c.compare(owned, reference)
    assert not result["exact_match"] and result["differences"]


@pytest.mark.parametrize(
    "kind",
    ["bits", "layout", "source", "stream", "alias", "alias_bool", "count_bool", "capture", "order"],
)
def test_nonexact_source_metadata_layout_or_values_never_gain_credit(kind):
    owned, reference = pair()
    if kind == "bits":
        value = next(iter(reference["results"][0][1]["columns"].values()))
        value["raw_bytes_hex"] = "ff" + value["raw_bytes_hex"][2:]
    elif kind == "layout":
        reference["results"][0][1]["tree"]["layout"]["strides_bytes"] = [-8]
        reference["results"][0][1]["tree"]["layout"]["C_contiguous"] = False
        reference["results"][0][1]["tree"]["layout"]["F_contiguous"] = False
    elif kind == "source":
        reference["original_source_pins"]["betse/science/cells.py"] = "0" * 64
    elif kind == "stream":
        reference["stream_after"] = f.stream(position=54)
    elif kind == "alias":
        reference["aliases"]["caller"] = False
    elif kind == "alias_bool":
        reference["aliases"]["caller"] = 1
    elif kind == "count_bool":
        reference["reference_inputs"] = True
    elif kind == "capture":
        reference["capture_error"] = {"type": "OSError"}
    else:
        reference["results"].reverse()
    try:
        result = c.compare(owned, reference)
    except (ValueError, TypeError):
        return
    assert result["exact_match"] is False


@pytest.mark.parametrize(
    "kind",
    [
        "trial_hash",
        "request_hash",
        "source_lines",
        "probe_order",
        "parent_changed",
        "cache_changed",
        "rng",
    ],
)
def test_changed_saved_owner_or_request_identity_refuses(kind):
    owned, _ = pair()
    if kind == "trial_hash":
        owned["trial"]["identity"] = "f" * 64
    elif kind == "request_hash":
        owned["request"]["parent"] = "e" * 64
    elif kind == "source_lines":
        owned["request"]["native_source_lines"] = dict(c.native.SOURCE_LINES, from_iterable=[1, 2])
        seal(owned)
    elif kind == "probe_order":
        owned["request"]["probes"].reverse()
        seal(owned)
    elif kind == "parent_changed":
        owned["trial"]["parent_identity"] = "e" * 64
        seal(owned)
    elif kind == "cache_changed":
        owned["trial"]["after"]["identity"] = "d" * 64
    else:
        owned["stream_after"] = f.stream(position=18)
    with pytest.raises(ValueError):
        c.validate_capture(owned)


def test_zero_mask_bytes_remain_a_failed_support_gate():
    owned, _ = pair()
    cache = owned["environment_cache"]
    tree = json.loads(cache["descriptor_json"])
    caller = tree["items"][0][1]
    columns = list(cache["columns"])
    for name in ("maskM", "maskECM", "voronoi_mask"):
        node, col = f.column(name, values=(0.0, -0.0))
        caller["items"].append([f.scalar(name), node])
        columns.append(col)
    owned["environment_cache"] = f.cache(tree, columns)
    previous = copy.deepcopy(owned)
    report = c.diagnostics(owned)
    assert report["domain_mask_gate_passed"] is False
    assert all(r["nonzero"] == 0 for r in report["environment"]["support"].values())
    assert owned == previous


def test_old_environment_and_runtime_namespaces_are_not_mutated():
    before = c.prefix.ENDPOINT, c.prefix.KINDS, c.prefix.OWN, c.prefix.native, c.prefix.diagnostic
    scope = c._scope()
    assert scope["ENDPOINT"] == c.ENDPOINT and scope["OWN"] == c.OWN
    assert (
        c.prefix.ENDPOINT,
        c.prefix.KINDS,
        c.prefix.OWN,
        c.prefix.native,
        c.prefix.diagnostic,
    ) == before
    assert scope["native"].shared.metadata_imports_for(
        c.ENDPOINT
    ) == c.native.prefix.shared.metadata_imports_for("lapENV_P_inv")


def test_reader_rejects_incomplete_prefix_before_any_source(monkeypatch):
    monkeypatch.setattr(c.prefix, "capture_lineage", lambda *a: pytest.fail("prefix replayed"))
    with pytest.raises(ValueError, match="all fresh"):
        c.capture_lineage([], {}, "case")


def complete_lineage(tmp_path):
    rows, conf = environment.lineage(tmp_path)
    stream = copy.deepcopy(rows[8]["stream_after"])
    poisson = dict(
        request_identity="a" * 64,
        parent_identity=rows[8]["identity"],
        identity="e" * 64,
        source_completed=True,
        stream_before=stream,
        stream_after=copy.deepcopy(stream),
    )
    tail = dict(
        request_identity="c" * 64,
        parent_identity=poisson["identity"],
        identity="b" * 64,
        source_completed=True,
        stream_before=copy.deepcopy(stream),
        stream_after=copy.deepcopy(stream),
    )
    capture, _ = pair()
    capture["environment_cache"] = copy.deepcopy(rows[8]["cache"])
    capture["stream_before"] = capture["stream_after"] = copy.deepcopy(stream)
    return [*rows, dict(poisson=poisson, tail=tail), capture], conf


def test_fresh_full_lineage_authenticates_eleven_captures_and_separate_world_trials(tmp_path):
    rows, conf = complete_lineage(tmp_path)
    before = copy.deepcopy(rows)
    raw = c.capture_lineage(rows, conf, c.diagnostic.CASES[0])
    assert raw["seed_recipe"]["lattice_type"] == "SQUARE" and rows == before


def test_legacy_twelve_capture_proposal_is_not_relabelled_as_new_schema(tmp_path):
    rows, conf = complete_lineage(tmp_path)
    old = [*rows[:9], rows[9]["poisson"], rows[9]["tail"], rows[10]]
    with pytest.raises(ValueError, match="all fresh"):
        c.capture_lineage(old, conf, c.diagnostic.CASES[0])


@pytest.mark.parametrize("change", ["extra", "missing"])
def test_compound_world_capture_requires_both_actual_trial_records(tmp_path, change):
    rows, conf = complete_lineage(tmp_path)
    if change == "extra":
        rows[9]["hydrated_world"] = {}
    else:
        del rows[9]["poisson"]
    with pytest.raises(ValueError):
        c.capture_lineage(rows, conf, c.diagnostic.CASES[0])


@pytest.mark.parametrize(
    "mutation",
    ["poisson_parent", "tail_parent", "mapping_parent", "poisson_rng", "tail_rng", "mapping_rng"],
)
def test_parent_or_continuing_rng_handoff_changes_refuse_without_replay(tmp_path, mutation):
    rows, conf = complete_lineage(tmp_path)
    if mutation == "poisson_parent":
        rows[9]["poisson"]["parent_identity"] = "f" * 64
    elif mutation == "tail_parent":
        rows[9]["tail"]["parent_identity"] = "f" * 64
    elif mutation == "mapping_parent":
        rows[10]["trial"]["parent_identity"] = "f" * 64
        rows[10]["request"]["parent"] = "f" * 64
        seal(rows[10])
    elif mutation == "poisson_rng":
        rows[9]["poisson"]["stream_before"] = f.stream(position=1)
    elif mutation == "tail_rng":
        rows[9]["tail"]["stream_after"] = f.stream(position=2)
    else:
        rows[10]["stream_before"] = rows[10]["stream_after"] = f.stream(position=3)
    with pytest.raises(ValueError):
        c.capture_lineage(rows, conf, c.diagnostic.CASES[0])


def reference_worker(tmp_path, monkeypatch, reference):
    scope = c._scope()
    source = tmp_path / "prepared/source"
    source.mkdir(parents=True)
    output = tmp_path / "output"
    output.mkdir()
    plan = dict(
        interpreter=str(c.prefix.sys.executable),
        runtime_inventory={},
        parent_diagnostic="parent",
        parent_prepared="prepared",
        configuration={},
    )
    scope.update(
        ROOT=source,
        verify=lambda *a: plan,
        saved=lambda *a: dict(raw={}, owned={}),
        native=NS(evaluate=lambda *a, **kw: reference),
        runtime_functions=lambda: dict(preflight=lambda *a: {}, finish=lambda *a: {}),
        sys=NS(
            executable=c.prefix.sys.executable,
            path=list(c.prefix.sys.path),
            addaudithook=lambda *a: None,
        ),
        resource=NS(RLIMIT_AS=c.prefix.resource.RLIMIT_AS, setrlimit=lambda *a: None),
    )
    monkeypatch.setattr(c.prefix.old_runner, "protected_output", lambda *a: output)
    monkeypatch.setattr(c.prefix.old_runner, "verify_claim", lambda *a: {"claim": "synthetic"})
    monkeypatch.setattr(c.prefix.metadata, "verify_metadata_modules", lambda *a: {})
    monkeypatch.setattr(c.prefix.metadata, "import_guard", lambda *a: lambda *b: None)
    monkeypatch.setattr(c.shared, "runtime_inventory", lambda *a: {})
    calls = []

    def project(value):
        assert (output / "native-full.json").is_file()
        calls.append("project")
        return {}

    scope.update(
        comparison_record=project,
        compare=lambda *a: calls.append("compare") or dict(exact_match=True),
    )
    return scope, output, calls


@pytest.mark.parametrize(
    "failure", ["status", "body", "body_type", "source", "capture", "capture_list", "stage"]
)
def test_failed_reference_is_fully_saved_before_projection_gate(tmp_path, monkeypatch, failure):
    reference = dict(
        status="source_completed",
        source_body_completed=True,
        source_error=None,
        capture_error=None,
        capture_errors=[],
        failed_stage=None,
        raw_primary={"retained": True},
    )
    if failure == "status":
        reference["status"] = "source_failed"
    elif failure == "body":
        reference["source_body_completed"] = False
    elif failure == "body_type":
        reference["source_body_completed"] = 1
    elif failure == "source":
        reference["source_error"] = {"original": "primary"}
    elif failure == "capture":
        reference["capture_error"] = {"original": "capture"}
    elif failure == "capture_list":
        reference["capture_errors"] = [{"original": "capture"}]
    else:
        reference["failed_stage"] = "mapping_source"
    scope, out, calls = reference_worker(tmp_path, monkeypatch, reference)
    assert scope["worker"](out.parent / "prepared", "hash", out / "release", out) == 1
    assert (out / "native-full.json").is_file() and calls == []
    assert c.shared.read(out / "worker-result.json")["accepted_source_comparisons"] == 0


def test_successful_reference_projection_follows_full_forensic_save(tmp_path, monkeypatch):
    reference = dict(
        status="source_completed",
        source_body_completed=True,
        source_error=None,
        capture_error=None,
        capture_errors=[],
        failed_stage=None,
    )
    scope, out, calls = reference_worker(tmp_path, monkeypatch, reference)
    assert scope["worker"](out.parent / "prepared", "hash", out / "release", out) == 0
    assert calls == ["project", "compare"]
