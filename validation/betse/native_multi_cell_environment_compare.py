"""Saved multi-cell ordinary evidence and one independently compiled reference.

Metadata comparison never rehydrates an owner. Only an exact source-reviewed
release may execute the reference, once, under the existing resource guard.
Exact source correspondence and population/domain diagnostics are independent
outcomes; neither grants physical, checkpoint or general make_world admission.
"""

import argparse
import json
import os
import resource
import runpy
import struct
import sys
from pathlib import Path
from types import FunctionType, SimpleNamespace

from validation import source_snapshot
from validation.betse import native_multi_cell_caller_compare as old_compare
from validation.betse import native_multi_cell_caller_comparison as old_runner
from validation.betse import native_multi_cell_caller_comparison_inputs as old_inputs
from validation.betse import native_multi_cell_caller_comparison_runtime as old_runtime
from validation.betse import native_multi_cell_environment_native as native
from validation.betse import native_multi_cell_environment_qualification as diagnostic
from validation.betse import native_single_cell_prefix_comparison as metadata
from validation.betse import native_single_cell_prefix_payload as payload

shared, wire = diagnostic.shared, old_compare.wire
ROOT = Path(__file__).resolve().parents[2]
OWN = "validation/betse/native_multi_cell_environment_compare.py"
ENDPOINT = native.ENDPOINT
KINDS = ("cells.multi_environment_comparison_plan@1", "cells.multi_environment_reference_release@1")
PURPOSE = "independent_original_multi_cell_ordinary_comparison"
NO_CREDIT = old_runner.NO_CREDIT
SELECTOR = "native_grid_size_yaml_alias@1"
TRIAL_FIELDS = (
    "request_identity",
    "parent_identity",
    "before",
    "cache",
    "stages",
    "events",
    "work",
    "stream_before",
    "stream_after",
    "warnings",
    "source_completed",
    "failure_stage",
    "failure_type",
    "failure_message",
    "identity",
)
CACHE_FIELDS = ("caller", "mesh", "parameters", "grid", "trees")
ALIASES = (
    "grid_is_actual",
    "X_is_grid",
    "Y_is_grid",
    "xy_is_grid",
    "map_is_grid",
    "all_points_cell_i_is_cell_i",
    "points_tree_is_retained",
    "voronoi_centres_is_xypts",
)
REFERENCE_FIELDS = (
    "kind",
    "stop_after",
    "status",
    "source_error",
    "capture_error",
    "failed_stage",
    "before",
    "stages",
    "cache",
    "stream_before",
    "stream_after",
    "warnings",
    "aliases",
    "original_source_pins",
    "source_sites",
    "image_file_sha256",
    "diagnostics",
)


def _same(a, b):
    return native.same(a, b)


def _clone_namespace(module, **overrides):
    """Private metadata adapter: no mutation of the read-only legacy module."""
    namespace = dict(vars(module), **overrides)
    for name, value in vars(module).items():
        if isinstance(value, FunctionType) and value.__module__ == module.__name__:
            namespace[name] = FunctionType(
                value.__code__, namespace, value.__name__, value.__defaults__, value.__closure__
            )
            namespace[name].__kwdefaults__ = value.__kwdefaults__
    return namespace


def _descriptor(request, trial):
    if request.get("grid_descriptor") != SELECTOR:
        raise ValueError("Fresh ordinary descriptor selector required")
    proof = trial.get("descriptor_proof")
    if type(proof) is not list or len(proof) != 3 or proof[0] != SELECTOR:
        raise ValueError("Missing before-birth descriptor proof")
    occurrence, pins = proof[1:]
    if (
        type(occurrence) is not list
        or len(occurrence) != 3
        or type(occurrence[0]) is not int
        or occurrence[0] < 0
        or type(occurrence[1]) is not int
        or occurrence[1] != occurrence[0] + 1
        or type(occurrence[2]) is not str
        or not 0 < len(occurrence[2]) <= 256
        or type(pins) is not list
        or not pins
    ):
        raise ValueError("Incomplete native descriptor occurrence/source proof")
    seen = set()
    expected = {
        str(shared.NATIVE / p): native.pins_for()[p]
        for p in (
            "betse/science/parameters.py",
            "betse/lib/yaml/yamlalias.py",
            "betse/util/type/descriptor/expralias.py",
            "betse/util/type/cls/classes.py",
            "betse/util/type/types.py",
            "betse/exceptions.py",
        )
    }
    for pair in pins:
        if (
            type(pair) is not list
            or len(pair) != 2
            or pair[0] in seen
            or expected.get(pair[0]) != pair[1]
        ):
            raise ValueError("Changed descriptor producer proof")
        seen.add(pair[0])
    if seen != set(expected):
        raise ValueError("Incomplete descriptor producer roster")


def capture_lineage(values, configuration, case):
    """Authenticate saved source associations, not live or physical authority."""
    if type(values) is not list or len(values) != len(diagnostic.STAGES):
        raise ValueError("Require all nine fresh ordinary capture boundaries")
    outer, caller, ordinary = values[6:]
    wire._keys(outer, ("caller_request", "identity"), "ordinary request")
    wire._digest(outer["identity"], "ordinary request identity")
    request = outer["caller_request"]
    wire._keys(
        request,
        (
            *("lifecycle_request", "lifecycle_state", "configuration_json", "identity"),
            "grid_descriptor",
        ),
        "ordinary caller request",
    )
    wire._keys(caller, (*old_compare.TRIAL_FIELDS, "descriptor_proof"), "ordinary caller Trial")
    _descriptor(request, caller)
    # Retain the legacy validator's full recipe/clip/lifecycle/MT checks. Its
    # exact two typed record rosters are extended only by these two declared
    # ordinary fields; no generic extra-key or old-request retrofit is allowed.
    prior = SimpleNamespace(
        CASES=diagnostic.CASES,
        STAGES=old_inputs.prior.STAGES,
        CONTROLS=diagnostic.CONTROLS,
        _declaration=diagnostic.prior._declaration,
        configuration=diagnostic.configuration,
    )
    comparison = SimpleNamespace(
        wire=wire,
        TRIAL_FIELDS=(*old_compare.TRIAL_FIELDS, "descriptor_proof"),
        CACHES=old_compare.CACHES,
        MASK_FIELDS=old_compare.MASK_FIELDS,
    )
    api = SimpleNamespace(inputs=native.inputs, source=native.legacy.source)
    scope = _clone_namespace(old_inputs, prior=prior, comparison=comparison, native=api)
    base_keys = scope["_keys"]

    def keys(value, names, label):
        if label == "plain caller request":
            names = (*names, "grid_descriptor")
        return base_keys(value, names, label)

    scope["_keys"] = keys
    raw = scope["capture_lineage"]([*values[:6], request, caller], configuration, case)
    wire._keys(ordinary, TRIAL_FIELDS, "ordinary Trial")
    for name in ("identity", "request_identity", "parent_identity"):
        wire._digest(ordinary[name], "ordinary." + name)
    if (
        ordinary["parent_identity"] != caller["identity"]
        or ordinary["source_completed"] is not True
        or any(
            ordinary[name] is not None
            for name in ("failure_stage", "failure_type", "failure_message")
        )
    ):
        raise ValueError("Incomplete ordinary source or mismatched actual caller trial")
    _stages(ordinary["stages"], "ordinary")
    for name in ("stream_before", "stream_after"):
        wire._stream(ordinary[name], "ordinary." + name)
    if not _same(ordinary["stream_before"], caller["stream_after"]):
        raise ValueError("Changed same-caller continuing RNG handoff")
    return raw


def _stages(rows, label):
    if (
        type(rows) is not list
        or len(rows) != len(native.METHODS)
        or any(type(row) is not list or len(row) != 2 for row in rows)
        or [row[0] for row in rows] != list(native.METHODS)
    ):
        raise ValueError(label + ": exact nine source-ordered methods required")
    return rows


def _mask(cache, label):
    fields = wire._fields(cache.tree, label, CACHE_FIELDS)
    mesh = fields["mesh"]
    proxy = SimpleNamespace(tree=mesh)
    # Exactly the three direct token-provenance scalars. Layouts, bits, mapping
    # order, clipcurve and every other image/cache field remain exact.
    old_compare._mask(proxy, label + ".mesh", cache.owned)
    parameters = wire._fields(fields["parameters"], label + ".parameters")
    if parameters.get("plot_grid_size") != dict(type="int", value=50):
        raise ValueError("Require original plot_grid_size50")
    return fields


def diagnostics_from_cache(value, *, owned=True):
    """Stdlib-only population/domain observations from authenticated typed bits.

    No interpolation, array restoration, source replay or independent geometric
    oracle. Empty support is a retained failed domain gate, never an input fix.
    """
    cache = wire._Cache(value, "diagnostics", owned)
    fields = wire._fields(cache.tree, "diagnostics", CACHE_FIELDS)
    caller = wire._fields(fields["caller"], "diagnostics.caller")
    result = dict(
        population={},
        support={},
        geometry={},
        observation_errors=[],
        physical_admission=False,
        native_grid_constants_changed=False,
    )

    def count(node):
        if node["type"] in ("array", "object_array"):
            return node["layout"]["shape"][0]
        if node["type"] in ("list", "tuple"):
            return len(node["items"])
        raise ValueError("Expected an original index/coordinate collection")

    def numbers(node):
        if node["type"] == "array":
            dtype = node["layout"]["dtype"]
            kind, width, order = wire._dtype(dtype, "diagnostic array")
            raw = bytes.fromhex(node["raw"])
            if kind in "iu":
                return [
                    int.from_bytes(raw[i : i + width], order, signed=kind == "i")
                    for i in range(0, len(raw), width)
                ]
            if kind == "f":
                return [
                    x[0]
                    for x in struct.iter_unpack(
                        ("<" if order == "little" else ">") + {2: "e", 4: "f", 8: "d"}[width], raw
                    )
                ]
            if kind == "b":
                return [bool(b) for b in raw]
            raise ValueError("Unexpected complex diagnostic field")
        if node["type"] == "float":
            return [struct.unpack("<d", bytes.fromhex(node["bits"]))[0]]
        if node["type"] in ("int", "bool"):
            return [node["value"]]
        if node["type"] in ("object_array", "list", "tuple"):
            return [v for child in node["items"] for v in numbers(child)]
        raise ValueError("Expected numeric diagnostic field")

    def finite(values):
        return all(v == v and v not in (float("inf"), -float("inf")) for v in values)

    for label, name in (
        ("cells", "cell_i"),
        ("membranes", "mem_i"),
        ("vertices", "ecm_verts_unique"),
        ("ecm_nodes", "xypts"),
    ):
        try:
            result["population"][label] = count(caller[name])
        except Exception as error:
            result["observation_errors"].append(dict(field=name, error=str(error)))
    for name in ("maskM", "maskECM", "voronoi_mask"):
        try:
            node = caller[name]
            values = numbers(node)
            result["support"][name] = dict(
                shape=node["layout"]["shape"],
                size=len(values),
                nonzero=sum(v != 0 for v in values),
                finite=finite(values),
            )
        except Exception as error:
            result["observation_errors"].append(dict(field=name, error=str(error)))
    for name in ("cell_vol", "mem_vol", "ecm_vol", "cell_centres", "ecm_verts_unique", "xypts"):
        try:
            values = numbers(caller[name])
            result["geometry"][name] = dict(
                size=len(values),
                finite=finite(values),
                positive=bool(values) and all(v > 0 for v in values)
                if name.endswith("vol")
                else None,
            )
        except Exception as error:
            result["observation_errors"].append(dict(field=name, error=str(error)))
    try:
        xmin, xmax, ymin, ymax = (
            numbers(caller[name])[0] for name in ("xmin", "xmax", "ymin", "ymax")
        )
        for name in ("cell_centres", "ecm_verts_unique"):
            points = numbers(caller[name])
            result["geometry"][name]["inside_native_bounds"] = sum(
                xmin <= x <= xmax and ymin <= y <= ymax
                for x, y in zip(points[::2], points[1::2], strict=True)
            )
    except Exception as error:
        result["observation_errors"].append(dict(field="bounds", error=str(error)))
    finite_masks = all(
        result["support"].get(name, {}).get("finite") is True
        for name in ("maskM", "maskECM", "voronoi_mask")
    )
    result["gates"] = dict(
        populated=result["population"].get("cells", 0) > 1,
        finite_geometry=bool(result["geometry"])
        and all(row["finite"] for row in result["geometry"].values()),
        positive_volumes=all(
            result["geometry"].get(name, {}).get("positive") is True
            for name in ("cell_vol", "mem_vol", "ecm_vol")
        ),
        finite_masks=finite_masks,
        mask_support=finite_masks
        and all(
            result["support"].get(name, {}).get("finite") is True
            and result["support"].get(name, {}).get("nonzero", 0) > 0
            for name in ("maskM", "maskECM")
        ),
    )
    result["domain_gate_passed"] = not result["observation_errors"] and all(
        result["gates"].values()
    )
    return result


def compare(owned, reference):
    wire._keys(owned, TRIAL_FIELDS, "owned")
    wire._keys(reference, REFERENCE_FIELDS, "reference")
    if reference["kind"] != native.KIND or reference["stop_after"] != ENDPOINT:
        raise ValueError("Wrong independent ordinary endpoint")
    for name in ("identity", "request_identity", "parent_identity"):
        wire._digest(owned[name], "owned." + name)
    wire._digest(reference["image_file_sha256"], "reference.image_file_sha256")
    if (
        reference["original_source_pins"] != native.pins_for()
        or type(reference["source_sites"]) is not dict
        or not reference["source_sites"]
    ):
        raise ValueError("Incomplete original-source authority")
    for side, value in (("owned", owned), ("reference", reference)):
        if type(value["warnings"]) is not list or any(
            type(row) is not str for row in value["warnings"]
        ):
            raise ValueError(side + ": original warning records required")
    _stages(owned["stages"], "owned")
    _stages(reference["stages"], "reference")
    wire._keys(reference["aliases"], ALIASES, "reference aliases")
    differences = []
    result = dict(
        exact_match=False,
        cache_pairs_compared=0,
        arrays_compared=0,
        streams_compared=0,
        differences=differences,
        reference_diagnostics=reference["diagnostics"],
        **NO_CREDIT,
    )
    for path, value, expected in (
        ("owned.source_completed", owned["source_completed"], True),
        ("reference.status", reference["status"], "source_completed"),
        *(
            ("owned." + n, owned[n], None)
            for n in ("failure_stage", "failure_type", "failure_message")
        ),
        *(
            ("reference." + n, reference[n], None)
            for n in ("source_error", "capture_error", "failed_stage")
        ),
        *(("reference.aliases." + n, reference["aliases"][n], True) for n in ALIASES),
    ):
        if type(value) is not type(expected) or value != expected:
            differences.append(
                dict(path=path, reason="incomplete_source_or_observation", observed=value)
            )
    if differences:
        return result
    caches = [
        ("before", owned["before"], reference["before"]),
        *((n, a, b) for (n, a), (_, b) in zip(owned["stages"], reference["stages"], strict=True)),
        ("final", owned["cache"], reference["cache"]),
    ]
    finite = []
    for name, a, b in caches:
        left, right = (
            wire._Cache(a, "owned." + name, True),
            wire._Cache(b, "reference." + name, False),
        )
        _mask(left, "owned." + name)
        _mask(right, "reference." + name)
        wire._difference(left.tree, right.tree, name, differences)
        result["cache_pairs_compared"] += 1
        result["arrays_compared"] += left.arrays
        finite.append(dict(stage=name, owned=left.finite, reference=right.finite))
    for name in ("stream_before", "stream_after"):
        wire._difference(
            wire._stream(owned[name], "owned." + name),
            wire._stream(reference[name], "reference." + name),
            name,
            differences,
        )
        result["streams_compared"] += 1
    result.update(
        exact_match=not differences,
        finite_observations=finite,
        provenance_normalization="only direct mesh.image_mask kind/identity/image_identity",
        all_numerical_bits_and_layouts_exact=not differences,
        physical_gate_independent=True,
        owned_diagnostics=diagnostics_from_cache(owned["cache"]),
        reference_cache_diagnostics=diagnostics_from_cache(reference["cache"], owned=False),
    )
    return result


def comparison_record(reference):
    return {name: reference[name] for name in REFERENCE_FIELDS}


def saved(diagnostic_path, parent):
    """No process query or replay; require complete, reviewed saved diagnostics."""
    path, parent = shared.output_path(diagnostic_path), shared.output_path(parent)
    if any(
        (path / p).exists()
        for p in ("failure.json", "process/failure.json", "process/resource-stop.json")
    ):
        raise ValueError("Failed diagnostic is evidence, never a completed comparison input")
    result, recorded = shared.read(path / "result.json"), shared.read(path / "diagnostic.json")
    if (
        result.get("status") != "completed_unqualified"
        or result.get("failure", True) is not None
        or result.get("diagnostic") != shared.pin(path / "diagnostic.json")
        or result.get("stop_after") != ENDPOINT
        or result.get("automatic_retry") is not False
        or recorded.get("status") != "source_completed_unqualified"
        or recorded.get("stop_after") != ENDPOINT
        or recorded.get("completed_stages") != list(diagnostic.STAGES)
        or any(
            recorded.get(n, "missing") is not None
            for n in (
                "failed_stage",
                "source_error",
                "observer_error",
                "interrupted_exception_graph",
            )
        )
    ):
        raise ValueError("Require a complete failure-free ordinary diagnostic")
    plan = diagnostic.verify_plan(parent, recorded["plan_sha256"])
    case = recorded["case"]
    process = shared.read(path / "process/result.json")
    if (
        case not in diagnostic.CASES
        or result.get("case") != case
        or process.get("status") != "completed"
        or type(process.get("returncode")) is not int
        or process["returncode"] != 0
        or result.get("process") != process
        or result.get("process_receipts") != [shared.pin(path / "process/result.json")]
    ):
        raise ValueError("Changed or failed guarded process receipt")
    launch = shared.read(path / "inputs.json")
    if any(launch.get(n) != recorded[n] for n in ("case", "plan_sha256", "stop_after")):
        raise ValueError("Changed exact launch inputs")
    shared.verify_pins([launch["release"]])
    grant = shared.read(launch["release"]["path"])
    fixed = dict(
        kind=diagnostic.KINDS[1],
        case=case,
        stop_after=ENDPOINT,
        plan_sha256=recorded["plan_sha256"],
        snapshot_sha256=plan["snapshot_sha256"],
        allow_actual_source_diagnostic=True,
        scientific_qualification=False,
    )
    if not _same({n: grant.get(n) for n in fixed}, fixed):
        raise ValueError("Changed exact ordinary release")
    shared.verify_pins([grant["source_review"]])
    rows, values, paths = recorded["captures"], [], set()
    if type(rows) is not list or len(rows) != len(diagnostic.STAGES):
        raise ValueError("All nine captures are required")
    for i, (stage, row) in enumerate(zip(diagnostic.STAGES, rows, strict=True)):
        wire._keys(row, ("label", "path", "status", "sha256"), "capture")
        relative = source_snapshot.relative_path(row["path"])
        if (
            row["label"] != stage
            or row["status"] != "saved"
            or relative in paths
            or str(relative) != f"capture-{i:04d}.json"
            or shared.pin(path / relative)["sha256"] != row["sha256"]
        ):
            raise ValueError("Changed, reordered, failed or duplicated capture")
        paths.add(relative)
        # Expand lossless sidecars before strict byte comparison, under their
        # existing bounds. No arrays or owners are reconstructed.
        values.append(diagnostic.read_capture(path / relative, row))
    raw = capture_lineage(values, plan["configuration"], case)
    shared.pin(path / "root-review.json")
    return dict(
        case=case,
        parent_plan=plan,
        captures=rows,
        raw=raw,
        configuration=plan["configuration"],
        owned=values[-1],
        values=values,
    )


def runtime_functions():
    """Inventory the unchanged libraries plus the exact shared descriptor closure."""
    scope = _clone_namespace(
        old_runtime,
        FORBIDDEN=frozenset(("cells", "jax", "jaxlib")),
        PACKAGES=(*old_runtime.PACKAGES, "beartype"),
        IMPORTS=(
            *old_runtime.IMPORTS,
            "scipy.ndimage",
            *native.shared.metadata_imports_for(ENDPOINT),
        ),
    )
    base = scope["_check_modules"]

    def check(*a, **k):
        base(*a, **k)
        native.shared.metadata_records(shared.NATIVE)

    scope["_check_modules"] = check
    return scope


def _bindings(path, parent, value):
    return old_runner.unique_pins(
        [
            *(
                shared.pin(path / p)
                for p in (
                    "result.json",
                    "diagnostic.json",
                    "inputs.json",
                    "root-review.json",
                    "process/result.json",
                )
            ),
            shared.pin(parent / "plan.json"),
            shared.pin(parent / "source/SNAPSHOT.json"),
            *(
                pin
                for row in value["captures"]
                for pin in diagnostic.capture_files(path / row["path"], row)
            ),
            *value["parent_plan"]["external_inputs"],
            *(dict(path=str(shared.NATIVE / p), sha256=h) for p, h in native.pins_for().items()),
        ]
    )


def prepare(destination, diagnostic_path, parent, *, cpu=6):
    destination, path, parent = map(shared.output_path, (destination, diagnostic_path, parent))
    if type(cpu) is not int or os.sched_getaffinity(0) != {cpu}:
        raise ValueError("Declare the actual one preparation CPU")
    if any(
        destination.is_relative_to(p) or p.is_relative_to(destination)
        for p in (ROOT, path, parent, shared.NATIVE)
    ):
        raise ValueError("Preparation overlaps retained evidence/source")
    value = saved(path, parent)
    external = _bindings(path, parent, value)
    runtime = runtime_functions()
    inventory = runtime["prepare_inventory"](value["parent_plan"]["runtime_paths"])
    _, sites = native.source_nodes(shared.NATIVE)
    shared.verify_pins(external)
    destination.mkdir(parents=True, exist_ok=False)
    try:
        closure = runpy.run_path(str(ROOT / shared.CLOSURE))["closure"]
        files = closure(ROOT, [*diagnostic.FILES, *diagnostic.TESTS])
        files[shared.CLOSURE] = source_snapshot.digest(ROOT / shared.CLOSURE)
        for directory in {Path(p).parent for p in files}:
            for p in (ROOT / directory).glob("*.json"):
                files[str(p.relative_to(ROOT))] = source_snapshot.digest(p)
        frozen = source_snapshot.freeze(ROOT, destination / "source", {p: p for p in files})
        plan = dict(
            kind=KINDS[0],
            purpose=PURPOSE,
            case=value["case"],
            stop_after=ENDPOINT,
            parent_diagnostic=str(path),
            parent_prepared=str(parent),
            configuration=value["configuration"],
            snapshot_sha256=source_snapshot.digest(destination / "source/SNAPSHOT.json"),
            git_revision=frozen["git_revision"],
            external_inputs=external,
            native_source_root=str(shared.NATIVE),
            original_source_sites=sites,
            runtime_paths=value["parent_plan"]["runtime_paths"],
            runtime_inventory=inventory,
            interpreter=str(Path(sys.executable).absolute()),
            cpu=cpu,
            limits=shared.LIMITS,
            native_executions=1,
            cells_replays=0,
            automatic_retry=False,
            capture_transport=payload.KIND,
            native_metadata_imports=list(native.shared.metadata_imports_for(ENDPOINT)),
            **NO_CREDIT,
        )
        source_snapshot.assert_checkout_unchanged(destination / "source")
        shared.verify_pins(external)
        runtime["verify_inventory"](inventory)
        shared.write(destination / "plan.json", plan)
        (destination / "plan.json").chmod(0o444)
        return plan
    except BaseException as error:
        old_runner._terminal(
            destination / "preparation-failure.json",
            dict(status="failed", error=old_runner._error(error), **NO_CREDIT),
        )
        raise


def verify(prepared, digest, release=None):
    prepared = shared.output_path(prepared)
    if source_snapshot.digest(prepared / "plan.json") != digest:
        raise ValueError("Changed reference plan")
    plan = shared.read(prepared / "plan.json")
    fixed = dict(
        kind=KINDS[0],
        purpose=PURPOSE,
        stop_after=ENDPOINT,
        limits=shared.LIMITS,
        native_executions=1,
        cells_replays=0,
        automatic_retry=False,
        capture_transport=payload.KIND,
        native_source_root=str(shared.NATIVE),
        native_metadata_imports=list(native.shared.metadata_imports_for(ENDPOINT)),
        **NO_CREDIT,
    )
    if (
        (prepared / "preparation-failure.json").exists()
        or not _same({k: plan.get(k) for k in fixed}, fixed)
        or plan.get("case") not in diagnostic.CASES
        or type(plan.get("cpu")) is not int
    ):
        raise ValueError("Incomplete or widened reference plan")
    source_snapshot.verify(prepared / "source", manifest_sha256=plan["snapshot_sha256"])
    shared.verify_pins(plan["external_inputs"])
    runtime_functions()["verify_inventory"](plan["runtime_inventory"])
    path, parent = (
        shared.output_path(plan["parent_diagnostic"]),
        shared.output_path(plan["parent_prepared"]),
    )
    value = saved(path, parent)
    _, sites = native.source_nodes(shared.NATIVE)
    if (
        value["case"] != plan["case"]
        or not _same(value["configuration"], plan["configuration"])
        or value["parent_plan"]["runtime_paths"] != plan["runtime_paths"]
        or not _same(sites, plan["original_source_sites"])
        or any(p not in plan["external_inputs"] for p in _bindings(path, parent, value))
    ):
        raise ValueError("Changed saved input/source/runtime associations")
    if release is not None:
        grant = shared.read(release)
        fixed = dict(
            kind=KINDS[1],
            plan_sha256=digest,
            snapshot_sha256=plan["snapshot_sha256"],
            case=plan["case"],
            stop_after=ENDPOINT,
            allow_one_native_reference=True,
            **NO_CREDIT,
        )
        if not _same({k: grant.get(k) for k in fixed}, fixed):
            raise ValueError("Exact reviewed one-reference release required")
        wire._keys(grant["source_review"], ("path", "sha256"), "source review")
        shared.verify_pins([grant["source_review"]])
        if os.sched_getaffinity(0) != {plan["cpu"]}:
            raise ValueError("Wrong reference CPU")
    return plan


def worker(prepared, digest, release, output):
    plan = verify(prepared, digest, release)
    source = Path(prepared) / "source"
    if ROOT != source or str(Path(sys.executable).absolute()) != plan["interpreter"]:
        raise ValueError("Frozen source and declared interpreter required")
    resource.setrlimit(resource.RLIMIT_AS, (2**30, 2**30))
    output = old_runner.protected_output(output, prepared, plan)
    authorization = old_runner.verify_claim(prepared, digest, release, output)
    with (output / "worker-started.json").open("x") as handle:
        json.dump(dict(claim=authorization, pid=os.getpid()), handle)
    runtime = runtime_functions()
    attempted, before = [], None
    sys.addaudithook(metadata.import_guard(plan, attempted))
    outcome = dict(
        status="failed",
        accepted_source_comparisons=0,
        reference_calls_attempted=0,
        stop_after=ENDPOINT,
        **NO_CREDIT,
    )
    try:
        metadata.verify_metadata_modules(plan)
        old_path = list(sys.path)
        try:
            sys.path.insert(0, str(shared.NATIVE))
            before = runtime["preflight"](plan["runtime_inventory"], source)
        finally:
            sys.path[:] = old_path
        shared.write(output / "runtime-before-source.json", before)
        value = saved(Path(plan["parent_diagnostic"]), Path(plan["parent_prepared"]))
        outcome["reference_calls_attempted"] = 1
        reference = native.evaluate(
            value["raw"],
            plan["configuration"],
            shared.NATIVE,
            record_exception=shared.exception_record,
        )
        outcome["source_summary"] = {
            k: reference[k]
            for k in (
                "status",
                "source_body_completed",
                "source_error",
                "capture_error",
                "failed_stage",
                "capture_errors",
            )
        }
        # Complete forensic data is sealed before selecting/comparing caches.
        serialized = shared.archive.snapshot(reference)
        payload.write(output / "native-full.json", serialized)
        summary = outcome["source_summary"]
        if (
            summary["status"] != "source_completed"
            or summary["source_body_completed"] is not True
            or summary["source_error"] is not None
            or summary["capture_error"] is not None
            or summary["capture_errors"]
            or summary["failed_stage"] is not None
        ):
            raise RuntimeError("Original source or capture failed; complete reference retained")
        selected = comparison_record(serialized)
        payload.write(output / "native-comparison.json", selected)
        comparison = compare(value["owned"], selected)
        shared.write(output / "comparison.json", comparison)
        verify(prepared, digest, release)
        metadata.verify_metadata_modules(plan)
        if attempted:
            raise RuntimeError("Prohibited model import attempted")
        outcome.update(
            status="exact_source_match" if comparison["exact_match"] else "source_mismatch",
            accepted_source_comparisons=int(comparison["exact_match"]),
        )
    except Exception as error:
        outcome["error"] = old_runner._error(error)
        old_runner._retain_runtime_refusal(output, error, outcome)
    finally:
        outcome["attempted_prohibited_imports"] = attempted
        try:
            metadata.verify_metadata_modules(plan)
            shared.write(output / "runtime-producers.json", shared.runtime_inventory(source))
            if before is None:
                outcome["dependency_preflight_incomplete"] = True
            else:
                shared.write(
                    output / "runtime-after-source.json",
                    runtime["finish"](plan["runtime_inventory"], source, before),
                )
        except Exception as error:
            outcome["runtime_capture_error"] = old_runner._error(error)
            old_runner._retain_runtime_refusal(output, error, outcome)
            outcome.update(status="failed", accepted_source_comparisons=0)
        outcome["saved_files"] = old_runner._saved_artifacts(output, outcome)
        old_runner._terminal(output / "worker-result.json", outcome)
    return int(outcome["status"] != "exact_source_match")


def launch(prepared, digest, release, output):
    plan = verify(prepared, digest, release)
    output = old_runner.protected_output(output, prepared, plan)
    output.mkdir(parents=True, exist_ok=False)
    process = error = None
    try:
        claim = old_runner.claim(prepared, digest, release, output)
        (output / "process").mkdir()
        shared.write(
            output / "inputs.json",
            dict(plan_sha256=digest, release=shared.pin(release), claim=claim, **NO_CREDIT),
        )
        if shared.guard.memory_available() < 12 * 2**30:
            raise RuntimeError("Require 12 GiB launch memory")
        process = shared.guard.run_bounded(
            [
                plan["interpreter"],
                "-B",
                "-m",
                "validation.betse.native_multi_cell_environment_compare",
                "worker",
                "--prepared",
                str(prepared),
                "--plan-sha256",
                digest,
                "--release",
                str(release),
                "--output",
                str(output),
            ],
            directory=output / "process",
            cwd=Path(prepared) / "source",
            env=shared.environment(Path(prepared) / "source", plan),
            **plan["limits"],
        )
        child = shared.read(output / "worker-result.json")
        if (
            process["returncode"] != 0
            or child.get("status") != "exact_source_match"
            or type(child.get("reference_calls_attempted")) is not int
            or child["reference_calls_attempted"] != 1
            or type(child.get("accepted_source_comparisons")) is not int
            or child["accepted_source_comparisons"] != 1
            or child.get("attempted_prohibited_imports") != []
        ):
            raise RuntimeError("Reference/comparison failed")
    except Exception as failure:
        error = old_runner._error(failure)
    record = dict(
        status="failed" if error else "exact_source_match_pending_review",
        process=process,
        error=error,
        worker_result=shared.pin(output / "worker-result.json")
        if (output / "worker-result.json").is_file()
        else None,
        process_receipts=[
            shared.pin(output / "process" / p)
            for p in ("result.json", "failure.json", "resource-stop.json")
            if (output / "process" / p).is_file()
        ],
        automatic_retry=False,
        **NO_CREDIT,
    )
    old_runner._terminal(output / ("failure.json" if error else "result.json"), record)
    return int(error is not None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    item = sub.add_parser("prepare")
    for name in ("output", "diagnostic", "parent"):
        item.add_argument("--" + name, type=Path, required=True)
    item.add_argument("--cpu", type=int, default=6)
    for name in ("run", "worker"):
        item = sub.add_parser(name)
        for field in ("prepared", "release", "output"):
            item.add_argument("--" + field, type=Path, required=True)
        item.add_argument("--plan-sha256", required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        resource.setrlimit(resource.RLIMIT_AS, (512 * 2**20, 2**30))
        prepare(args.output, args.diagnostic, args.parent, cpu=args.cpu)
        return 0
    return (worker if args.command == "worker" else launch)(
        args.prepared, args.plan_sha256, args.release, args.output
    )


if __name__ == "__main__":
    raise SystemExit(main())
