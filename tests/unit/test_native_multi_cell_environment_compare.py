"""Lossless synthetic cache/lineage controls; no owner or array restoration."""

import copy
import json
import struct
from pathlib import Path

import pytest

from tests.unit import test_native_multi_cell_caller_compare as fixture
from tests.unit import test_native_multi_cell_caller_comparison_inputs as inputs
from validation.betse import native_multi_cell_environment_compare as c


def cache():
    old, _ = fixture.inputs()
    mesh = json.loads(old["mesh_cache"]["descriptor_json"])
    tree = fixture.mapping(
        [
            ("caller", fixture.mapping([("cell_count", fixture.scalar(2))])),
            ("mesh", mesh),
            ("parameters", fixture.mapping([("plot_grid_size", fixture.scalar(50))])),
            ("grid", fixture.scalar(None)),
            ("trees", dict(kind="list", items=[])),
        ]
    )
    return fixture.cache(tree, old["mesh_cache"]["columns"])


def pair():
    snapshot = cache()
    owned = dict(
        request_identity="a" * 64,
        parent_identity="b" * 64,
        before=snapshot,
        cache=copy.deepcopy(snapshot),
        stages=[[name, copy.deepcopy(snapshot)] for name in c.native.METHODS],
        events=[],
        work=[],
        stream_before=fixture.stream(),
        stream_after=fixture.stream(position=53),
        warnings=[],
        source_completed=True,
        failure_stage=None,
        failure_type=None,
        failure_message=None,
        identity="c" * 64,
    )
    reference = dict(
        kind=c.native.KIND,
        stop_after=c.ENDPOINT,
        status="source_completed",
        source_error=None,
        capture_error=None,
        failed_stage=None,
        before=fixture.native_cache(snapshot),
        stages=[[name, fixture.native_cache(snapshot)] for name in c.native.METHODS],
        cache=fixture.native_cache(snapshot),
        stream_before=copy.deepcopy(owned["stream_before"]),
        stream_after=copy.deepcopy(owned["stream_after"]),
        warnings=[],
        aliases={name: True for name in c.ALIASES},
        original_source_pins=c.native.pins_for(),
        source_sites={"synthetic": "metadata"},
        image_file_sha256="d" * 64,
        diagnostics={"domain_gate_passed": False},
    )
    # Independent token provenance differs in exactly its declared three slots.
    for snapshot in [
        reference["before"],
        *(row[1] for row in reference["stages"]),
        reference["cache"],
    ]:
        mesh = next(value for key, value in snapshot["tree"]["values"] if key["value"] == "mesh")
        token = next(value for key, value in mesh["values"] if key["value"] == "image_mask")
        token["values"][0][1]["value"] = "independent_image_mask_token"
        for i in (1, 2):
            token["values"][i][1] = dict(type="NoneType", value=None)
    return owned, reference


def test_exact_eleven_pairs_and_two_complete_mt_records_preserve_negative_mask_layout():
    owned, reference = pair()
    before = copy.deepcopy((owned, reference))
    result = c.compare(owned, reference)
    assert (
        result["exact_match"]
        and result["cache_pairs_compared"] == 11
        and result["streams_compared"] == 2
    )
    assert result["arrays_compared"] == 44 and result["physical_geometry_admitted"] is False
    assert result["reference_diagnostics"]["domain_gate_passed"] is False
    assert result["all_numerical_bits_and_layouts_exact"] is True
    assert (owned, reference) == before


def test_zero_mask_is_retained_as_a_failed_domain_gate_without_changing_any_bytes():
    value = cache()
    tree = json.loads(value["descriptor_json"])
    caller = tree["items"][0][1]
    for name in ("cell_i", "mem_i"):
        caller["items"].append(
            [fixture.scalar(name), dict(kind="list", items=[fixture.scalar(0), fixture.scalar(1)])]
        )
    columns = list(value["columns"])
    for name in ("maskM", "maskECM", "voronoi_mask"):
        node, column = fixture.column(name, values=(0.0, -0.0))
        caller["items"].append([fixture.scalar(name), node])
        columns.append(column)
    value = fixture.cache(tree, columns)
    before = copy.deepcopy(value)
    report = c.diagnostics_from_cache(value)
    assert report["population"]["cells"] == 2 and report["gates"]["populated"]
    assert all(row["nonzero"] == 0 for row in report["support"].values())
    assert report["gates"]["mask_support"] is False and report["domain_gate_passed"] is False
    assert report["physical_admission"] is False and value == before


@pytest.mark.parametrize(
    "mutation", ["bits", "layout", "order", "stream", "alias", "capture", "extra", "stage"]
)
def test_non_provenance_changes_never_gain_exact_match(mutation):
    owned, reference = pair()
    if mutation == "bits":
        snapshot = reference["cache"]
        row = next(iter(snapshot["columns"].values()))
        row["raw_bytes_hex"] = "01" + row["raw_bytes_hex"][2:]
    elif mutation == "layout":
        mesh = reference["cache"]["tree"]["values"][1][1]
        token = mesh["values"][0][1]
        node = token["values"][5][1]
        node["layout"]["strides_bytes"] = [16, 8]
        node["layout"]["C_contiguous"] = True
    elif mutation == "order":
        reference["cache"]["tree"]["values"].reverse()
    elif mutation == "stream":
        reference["stream_after"] = fixture.stream(position=54)
    elif mutation == "alias":
        reference["aliases"][c.ALIASES[0]] = False
    elif mutation == "capture":
        reference["capture_error"] = {"type": "OSError"}
    elif mutation == "extra":
        reference["supplied_parent"] = {}
    else:
        reference["stages"][6:8] = reversed(reference["stages"][6:8])
    try:
        result = c.compare(owned, reference)
    except ValueError:
        return
    assert not result["exact_match"] and result["differences"]
    assert result.get("all_numerical_bits_and_layouts_exact", False) is False


def descriptor_proof():
    files = (
        "betse/science/parameters.py",
        "betse/lib/yaml/yamlalias.py",
        "betse/util/type/descriptor/expralias.py",
        "betse/util/type/cls/classes.py",
        "betse/util/type/types.py",
        "betse/exceptions.py",
    )
    return [
        c.SELECTOR,
        [3, 4, "SyntheticOnlyExprAlias"],
        sorted([[str(c.shared.NATIVE / p), c.native.pins_for()[p]] for p in files]),
    ]


def lineage(tmp_path):
    rows = inputs.lineage(tmp_path)
    conf = c.diagnostic.configuration()
    rows[0]["configuration"] = c.shared.archive.snapshot(conf)
    request, trial = rows[-2:]
    request["configuration_json"] = json.dumps(conf)
    request["grid_descriptor"] = c.SELECTOR
    trial["descriptor_proof"] = descriptor_proof()
    owned, _ = pair()
    owned["parent_identity"] = trial["identity"]
    owned["stream_before"] = trial["stream_after"]
    return [*rows[:6], dict(caller_request=request, identity="e" * 64), trial, owned], conf


@pytest.mark.parametrize("case", c.diagnostic.CASES)
def test_ordinary_lineage_retains_all_prior_native_recipe_checks(tmp_path, case):
    # The two registered lattice recipes remain exact; none is substituted.
    rows, conf = lineage(tmp_path)
    if case != c.diagnostic.CASES[0]:
        # Build the hex recipe independently via the existing metadata fixture.
        other = tmp_path / "hex"
        other.mkdir()
        old = inputs.lineage(other, case)
        rows[:6] = old[:6]
        rows[0]["configuration"] = c.shared.archive.snapshot(conf)
        req, trial = old[-2:]
        req.update(configuration_json=json.dumps(conf), grid_descriptor=c.SELECTOR)
        trial["descriptor_proof"] = descriptor_proof()
        rows[6] = dict(caller_request=req, identity="e" * 64)
        rows[7] = trial
        rows[8]["parent_identity"] = trial["identity"]
        rows[8]["stream_before"] = trial["stream_after"]
    before = copy.deepcopy(rows)
    raw = c.capture_lineage(rows, conf, case)
    assert raw["seed_recipe"]["lattice_type"] == (
        "SQUARE" if case == c.diagnostic.CASES[0] else "HEX"
    )
    assert rows == before and set(raw) == set(c.old_inputs.RAW_FIELDS)


@pytest.mark.parametrize(
    "mutation",
    ["legacy", "proof", "occurrence", "pins", "parent", "stream", "configuration", "method"],
)
def test_descriptor_and_same_parent_lineage_cannot_be_retrofitted(tmp_path, mutation):
    rows, conf = lineage(tmp_path)
    if mutation == "legacy":
        del rows[6]["caller_request"]["grid_descriptor"]
    elif mutation == "proof":
        rows[7]["descriptor_proof"] = []
    elif mutation == "occurrence":
        rows[7]["descriptor_proof"][1][1] = 5
    elif mutation == "pins":
        rows[7]["descriptor_proof"][2].pop()
    elif mutation == "parent":
        rows[-1]["parent_identity"] = "f" * 64
    elif mutation == "stream":
        rows[-1]["stream_before"] = fixture.stream(position=3)
    elif mutation == "configuration":
        rows[6]["caller_request"]["configuration_json"] = "{}"
    else:
        rows[-1]["stages"].reverse()
    with pytest.raises(ValueError):
        c.capture_lineage(rows, conf, c.diagnostic.CASES[0])


def test_reference_runtime_adaptation_preserves_legacy_inventory_contract():
    before = (c.old_runtime.FORBIDDEN, c.old_runtime.PACKAGES, c.old_runtime.IMPORTS)
    scope = c.runtime_functions()
    assert scope["PACKAGES"] == (*c.old_runtime.PACKAGES, "beartype")
    assert "betse.science.cells" not in scope["IMPORTS"] and "scipy.ndimage" in scope["IMPORTS"]
    assert set(scope["FORBIDDEN"]) == {"cells", "jax", "jaxlib"}
    assert before == (c.old_runtime.FORBIDDEN, c.old_runtime.PACKAGES, c.old_runtime.IMPORTS)


def test_reference_plan_refuses_before_native_or_inventory_when_hash_changed(tmp_path, monkeypatch):
    monkeypatch.setattr(
        c, "saved", lambda *a: (_ for _ in ()).throw(AssertionError("No evidence reads"))
    )
    path = tmp_path / "plan.json"
    path.write_text("{}\n")
    with pytest.raises(ValueError, match="Changed reference plan"):
        c.verify(tmp_path, "0" * 64)


@pytest.mark.parametrize("mutation", [None, "capture_order", "endpoint", "resource_failure"])
def test_complete_saved_nine_stage_transport_and_release_are_checked(
    tmp_path, monkeypatch, mutation
):
    rows, conf = lineage(tmp_path)
    diagnostic = tmp_path / "diagnostic"
    parent = tmp_path / "parent"
    diagnostic.mkdir()
    parent.mkdir()
    (diagnostic / "process").mkdir()
    monkeypatch.setattr(c.shared, "BASE", tmp_path)
    plan = dict(configuration=conf, snapshot_sha256="b" * 64, runtime_paths=[])
    monkeypatch.setattr(c.diagnostic, "verify_plan", lambda *a: plan)
    capture_rows = []
    for i, (stage, value) in enumerate(zip(c.diagnostic.STAGES, rows, strict=True)):
        path = diagnostic / f"capture-{i:04d}.json"
        c.payload.write(path, value)
        capture_rows.append(
            dict(label=stage, path=path.name, status="saved", sha256=c.shared.pin(path)["sha256"])
        )
    process = dict(status="completed", returncode=0)
    if mutation == "resource_failure":
        process["returncode"] = 1
    c.shared.write(diagnostic / "process/result.json", process)
    recorded = dict(
        case=c.diagnostic.CASES[0],
        plan_sha256="a" * 64,
        stop_after=c.ENDPOINT,
        status="source_completed_unqualified",
        completed_stages=list(c.diagnostic.STAGES),
        captures=capture_rows,
        failed_stage=None,
        source_error=None,
        observer_error=None,
        interrupted_exception_graph=None,
    )
    if mutation == "capture_order":
        capture_rows[7]["path"] = "capture-0008.json"
    c.shared.write(diagnostic / "diagnostic.json", recorded)
    c.shared.write(
        diagnostic / "result.json",
        dict(
            status="completed_unqualified",
            failure=None,
            diagnostic=c.shared.pin(diagnostic / "diagnostic.json"),
            stop_after=c.ENDPOINT,
            automatic_retry=False,
            case=c.diagnostic.CASES[0],
            process=process,
            process_receipts=[c.shared.pin(diagnostic / "process/result.json")],
        ),
    )
    review = tmp_path / "source-review.json"
    c.shared.write(review, dict(scope="synthetic metadata only"))
    release = tmp_path / "release.json"
    c.shared.write(
        release,
        dict(
            kind=c.diagnostic.KINDS[1],
            case=c.diagnostic.CASES[0],
            plan_sha256="a" * 64,
            snapshot_sha256="b" * 64,
            stop_after="cell_index" if mutation == "endpoint" else c.ENDPOINT,
            allow_actual_source_diagnostic=True,
            scientific_qualification=False,
            source_review=c.shared.pin(review),
        ),
    )
    c.shared.write(
        diagnostic / "inputs.json",
        dict(
            case=c.diagnostic.CASES[0],
            plan_sha256="a" * 64,
            stop_after=c.ENDPOINT,
            release=c.shared.pin(release),
        ),
    )
    c.shared.write(diagnostic / "root-review.json", dict(scope="synthetic saved-result review"))
    if mutation is not None:
        with pytest.raises(ValueError):
            c.saved(diagnostic, parent)
    else:
        value = c.saved(diagnostic, parent)
        assert value["owned"] == rows[-1] and len(value["captures"]) == 9
        assert set(value["raw"]) == set(c.old_inputs.RAW_FIELDS)


def test_legacy_endpoint_and_provenance_parser_interfaces_stay_read_only():
    assert c.old_compare.ENDPOINT == "cell_index"
    assert c.old_inputs.prior.STAGES[-1] == "cell_index"
    assert len(c.old_compare.TRIAL_FIELDS) + 1 == 21
    assert Path(c.native.legacy.__file__).name == "native_multi_cell_caller_native.py"


def namespace_fixture(tmp_path):
    scope = c.runtime_functions()
    packages = {}
    for name in scope["PACKAGES"]:
        root = tmp_path / name
        root.mkdir()
        packages[name] = dict(root=str(root))
    namespace = tmp_path / "scipy/_lib/vendor"
    namespace.mkdir(parents=True)
    child = namespace / "producer.py"
    child.write_text("raise AssertionError('metadata fixture must never be imported')\n")
    row = dict(object_id=42, kind="namespace", origin=None, paths=[str(namespace)])
    declaration = dict(packages=packages, files=[c.old_runtime._pin(child)])
    observed = dict(modules={"scipy._lib.vendor": row}, mapped_libraries=[])
    source = tmp_path / "snapshot"
    source.mkdir()
    return scope, namespace, row, declaration, observed, source


def test_runtime_namespace_inherits_exact_root_fix_without_changing_legacy_globals(tmp_path):
    before = c.old_runtime._check_package_namespace.__globals__
    scope, _, _, declaration, observed, source = namespace_fixture(tmp_path)
    assert (
        scope["_check_package_namespace"].__code__
        is c.old_runtime._check_package_namespace.__code__
    )
    assert scope["_check_package_namespace"].__globals__ is scope
    scope["_check_modules"](observed, declaration, source, {})
    scope["_check_modules"](observed, declaration, source, {}, dict(modules={}))
    scope["_check_modules"](observed, declaration, source, {}, copy.deepcopy(observed))
    assert c.old_runtime._check_package_namespace.__globals__ is before
    assert c.old_runtime.PACKAGES == ("numpy", "scipy", "PIL")
    assert "betse" in c.old_runtime.FORBIDDEN


@pytest.mark.parametrize(
    "mutation",
    [
        "foreign",
        "multiple",
        "linked",
        "regular_package",
        "unlisted",
        "top_level",
        "origin",
        "opaque",
    ],
)
def test_runtime_namespace_refuses_lookalike_or_unbound_containers(tmp_path, mutation):
    scope, namespace, row, declaration, observed, source = namespace_fixture(tmp_path)
    if mutation == "foreign":
        foreign = tmp_path / "foreign"
        foreign.mkdir()
        row["paths"] = [str(foreign)]
    elif mutation == "multiple":
        row["paths"].append(str(tmp_path))
    elif mutation == "linked":
        target = namespace.with_name("target")
        namespace.rename(target)
        namespace.symlink_to(target, target_is_directory=True)
    elif mutation == "regular_package":
        (namespace / "__init__.py").write_text("# never imported\n")
    elif mutation == "unlisted":
        declaration["files"] = []
    elif mutation == "top_level":
        observed["modules"] = {"scipy": row}
    elif mutation == "origin":
        row["origin"] = "supplied origin"
    else:
        row["kind"] = "opaque"
    with pytest.raises(ValueError):
        scope["_check_modules"](observed, declaration, source, {}, dict(modules={}))


def test_runtime_namespace_replacement_after_baseline_refuses_with_files_unchanged(tmp_path):
    scope, _, row, declaration, observed, source = namespace_fixture(tmp_path)
    baseline = copy.deepcopy(observed)
    row["object_id"] += 1
    with pytest.raises(ValueError, match="removed or changed"):
        scope["_check_modules"](observed, declaration, source, {}, baseline)


def repair_c4_cache(mask=None, invalid_bits=None):
    value = cache()
    tree = json.loads(value["descriptor_json"])
    caller = tree["items"][0][1]
    columns = list(value["columns"])
    for name in ("cell_i", "mem_i"):
        caller["items"].append(
            [fixture.scalar(name), dict(kind="list", items=[fixture.scalar(0), fixture.scalar(1)])]
        )
    arrays = {
        "cell_vol": ((1.0, 2.0), (2,)),
        "mem_vol": ((1.0, 2.0), (2,)),
        "ecm_vol": ((2.0, 3.0), (2,)),
        "cell_centres": ((0.25, 0.25, 0.75, 0.75), (2, 2)),
        "ecm_verts_unique": ((0.0, 0.0, 1.0, 1.0), (2, 2)),
        "xypts": ((0.0, 0.0, 1.0, 1.0), (2, 2)),
        "maskM": ((1.0, 1.0), (2,)),
        "maskECM": ((1.0, 1.0), (2,)),
        "voronoi_mask": ((1.0, 1.0), (2,)),
    }
    for name, (values, shape) in arrays.items():
        if name == mask:
            values = (struct.unpack("<d", bytes.fromhex(invalid_bits))[0], 1.0)
        strides = (16, 8) if len(shape) == 2 else (8,)
        node, column = fixture.column(
            name, values, shape=shape, strides=strides, c=True, f=len(shape) == 1
        )
        caller["items"].append([fixture.scalar(name), node])
        columns.append(column)
    for name, number in (("xmin", 0.0), ("xmax", 1.0), ("ymin", 0.0), ("ymax", 1.0)):
        caller["items"].append([fixture.scalar(name), fixture.scalar(number)])
    return fixture.cache(tree, columns, finite=mask is None)


@pytest.mark.parametrize("mask", ["maskM", "maskECM", "voronoi_mask"])
@pytest.mark.parametrize("bits", ["010000000000f87f", "000000000000f07f", "000000000000f0ff"])
def test_repair_c4_nan_inf_masks_cannot_pass_domain_gate_with_all_geometry_valid(mask, bits):
    baseline = repair_c4_cache()
    assert c.diagnostics_from_cache(baseline)["domain_gate_passed"] is True
    value = repair_c4_cache(mask, bits)
    before = copy.deepcopy(value)
    report = c.diagnostics_from_cache(value)
    assert (
        report["gates"]["populated"]
        and report["gates"]["finite_geometry"]
        and report["gates"]["positive_volumes"]
    )
    assert report["support"][mask]["nonzero"] == 2 and report["support"][mask]["finite"] is False
    assert not report["gates"]["finite_masks"] and not report["gates"]["mask_support"]
    assert report["domain_gate_passed"] is False and value == before


def test_repair_c4_exact_source_bits_are_distinct_from_nonfinite_mask_admission():
    owned, reference = pair()
    value = repair_c4_cache("maskM", "010000000000f87f")
    independent = fixture.native_cache(value)
    mesh = independent["tree"]["values"][1][1]
    token = mesh["values"][0][1]
    token["values"][0][1]["value"] = "independent_image_mask_token"
    for i in (1, 2):
        token["values"][i][1] = dict(type="NoneType", value=None)
    for key in ("before", "cache"):
        owned[key] = copy.deepcopy(value)
        reference[key] = copy.deepcopy(independent)
    owned["stages"] = [[name, copy.deepcopy(value)] for name in c.native.METHODS]
    reference["stages"] = [[name, copy.deepcopy(independent)] for name in c.native.METHODS]
    before = copy.deepcopy((owned, reference))
    result = c.compare(owned, reference)
    assert result["exact_match"] and result["cache_pairs_compared"] == 11
    assert result["owned_diagnostics"]["domain_gate_passed"] is False
    assert result["reference_cache_diagnostics"]["domain_gate_passed"] is False
    assert not result["physical_geometry_admitted"] and (owned, reference) == before


def repair_c3_worker(tmp_path, monkeypatch, reference):
    source = tmp_path / "prepared/source"
    source.mkdir(parents=True)
    output = tmp_path / "output"
    output.mkdir()
    plan = dict(
        interpreter=str(Path(c.sys.executable).absolute()),
        runtime_inventory={},
        parent_diagnostic="synthetic_parent",
        parent_prepared="synthetic_prepared",
        configuration={},
    )
    monkeypatch.setattr(c, "ROOT", source)
    monkeypatch.setattr(c, "verify", lambda *a: plan)
    monkeypatch.setattr(c.old_runner, "protected_output", lambda *a: output)
    monkeypatch.setattr(c.old_runner, "verify_claim", lambda *a: {"synthetic": "claim"})
    monkeypatch.setattr(c.resource, "setrlimit", lambda *a: None)
    monkeypatch.setattr(c.sys, "addaudithook", lambda *a: None)
    monkeypatch.setattr(c.metadata, "verify_metadata_modules", lambda *a: {})
    monkeypatch.setattr(c.metadata, "import_guard", lambda *a: lambda *b: None)
    monkeypatch.setattr(
        c,
        "runtime_functions",
        lambda: {
            "preflight": lambda *a: {"bound": True},
            "finish": lambda *a: {"bound_after": True},
        },
    )
    monkeypatch.setattr(
        c, "saved", lambda *a: dict(raw={"synthetic": "no source"}, owned={"synthetic": "owned"})
    )
    monkeypatch.setattr(c.native, "evaluate", lambda *a, **k: reference)
    monkeypatch.setattr(c.shared, "runtime_inventory", lambda *a: {})
    projections = []

    def project(value):
        assert (output / "native-full.json").is_file()
        projections.append("projected")
        return {"synthetic": "selected"}

    monkeypatch.setattr(c, "comparison_record", project)

    def compare(*args):
        projections.append("compared")
        return dict(exact_match=True)

    monkeypatch.setattr(c, "compare", compare)
    return source.parent, output, projections


@pytest.mark.parametrize(
    "failure", ["status", "body", "body_type", "source", "capture", "capture_list", "stage"]
)
def test_repair_c3_failed_reference_is_fully_saved_before_gate_and_never_projected(
    tmp_path, monkeypatch, failure
):
    reference = dict(
        status="source_completed",
        source_body_completed=True,
        source_error=None,
        capture_error=None,
        capture_errors=[],
        failed_stage=None,
        retained_partial=[1, 2],
    )
    if failure == "status":
        reference["status"] = "source_failed"
    elif failure == "body":
        reference["source_body_completed"] = False
    elif failure == "body_type":
        reference["source_body_completed"] = 1
    elif failure == "source":
        reference["source_error"] = {"primary": "original failure", "cause": "original cause"}
    elif failure == "capture":
        reference["capture_error"] = {"secondary": "original capture"}
    elif failure == "capture_list":
        reference["capture_errors"] = [{"original": "capture attempt"}]
    else:
        reference["failed_stage"] = "descriptor_construction"
    before = copy.deepcopy(reference)
    prepared, output, projections = repair_c3_worker(tmp_path, monkeypatch, reference)
    assert c.worker(prepared, "synthetic_digest", "synthetic_release", output) == 1
    result = c.shared.read(output / "worker-result.json")
    assert result["status"] == "failed" and result["accepted_source_comparisons"] == 0
    assert projections == [] and not (output / "native-comparison.json").exists()
    assert c.payload.read(output / "native-full.json") == c.shared.archive.snapshot(reference)
    assert result["source_summary"]["source_error"] == reference["source_error"]
    assert reference == before


def test_repair_c3_successful_reference_reaches_projection_only_after_full_save(
    tmp_path, monkeypatch
):
    reference = dict(
        status="source_completed",
        source_body_completed=True,
        source_error=None,
        capture_error=None,
        capture_errors=[],
        failed_stage=None,
    )
    prepared, output, projections = repair_c3_worker(tmp_path, monkeypatch, reference)
    assert c.worker(prepared, "synthetic_digest", "synthetic_release", output) == 0
    assert projections == ["projected", "compared"]
    assert c.shared.read(output / "worker-result.json")["status"] == "exact_source_match"
