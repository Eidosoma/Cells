"""Compare pinned complete-INIT observations without importing a model or NumPy.

Saved observation equality is separate from execution parity. The current
producers do not retain a common authenticated initial RNG epoch; this reader
reports that absence, never guesses a state, resets a stream, or searches for a
time shift. Only explicit producer observation boundaries may be aligned.
"""

import argparse
import ast
import hashlib
import json
import re
from pathlib import Path

from validation import source_snapshot as snapshot
from validation.betse import native_seed_demo_compare as saved
from validation.betse import native_seed_demo_evidence as evidence
from validation.betse import native_seed_demo_report as report

KIND = "cells.original_INIT_saved_reference_comparison@1"
REFERENCE_KIND = "cells.original_betse_complete_init_reference@2"
MAX_ITERATIONS, MAX_CAPTURES, MAX_NODES = 512, 2048, evidence.MAX_NODES
FIELDS = (
    "vm",
    "cc_cells",
    "cc_env",
    "cc_at_mem",
    "fluxes_mem",
    "fluxes_gj",
    "fluxes_env_x",
    "fluxes_env_y",
)
EPOCH = "original_full_INIT_body_end_before_next_FOR_ITER"
EPOCH_MAP = dict(
    reference=dict(
        ordinal_base=1,
        label="iteration_{ordinal:04d}",
        boundary="line_at_original_outer_for_with_previous_t",
    ),
    demo=dict(
        ordinal_base=0,
        label="init_terminal.iteration.{ordinal:04d}.after",
        boundary="original_outer_FOR_ITER_after_completed_body",
    ),
    common=EPOCH,
    searched_shift=False,
)
REF_SOURCE = "validation/betse/native_init_terminal_reference.py"
REFERENCE_AST_SHA256 = "2f52dd2f2bbf8f495044f5014a245ef8701d3bd59f64605094a6a1133aa740f8"
REVIEW_NAMES = {
    "SOURCE_REVIEW_SHA256",
    "BOOTSTRAP_REVIEW_SHA256",
    "WRITER_REVIEW_SHA256",
    "EXECUTION_RELEASE_SHA256",
}
_MISSING = object()


def source_plan():
    return dict(
        kind=KIND,
        maximum_iterations=MAX_ITERATIONS,
        fields=list(FIELDS),
        epochs=EPOCH_MAP,
        stdlib_readers_only=True,
        no_NumPy_model_RNG_or_owner_imports=True,
        exact_raw_bits_dtype_shape_source_layout=True,
        tolerance=None,
        unmatched_initial_rng="execution_parity_unavailable_not_numerical_mismatch",
        current_common_initial_rng_witness_available=False,
        partial_failure_never_complete=True,
        work_is_not_input_credit=True,
        scientific_physical_checkpoint_or_solver_repair_credit=0,
    )


def require(condition, message):
    if not condition:
        raise ValueError(message)


def _same(a, b):
    return type(a) is type(b) and json.dumps(a, sort_keys=True, allow_nan=False) == json.dumps(
        b, sort_keys=True, allow_nan=False
    )


def _issue(error):
    return dict(type=type(error).__name__, message=str(error)[:1000])


def _capture(reader, reference):
    path = reader.bind(reference)
    pins = evidence.files(path, expected_sha256=reference["sha256"])
    for row in pins:
        reader.bind(row)
    return evidence.read(path, expand=False, expected_sha256=reference["sha256"]), pins


def _layout(value):
    require(
        type(value) is dict
        and set(value) == {"dtype", "shape", "strides_bytes", "C_contiguous", "F_contiguous"},
        "Exact source layout",
    )
    dtype, shape, strides = value["dtype"], value["shape"], value["strides_bytes"]
    require(
        type(dtype) is str and re.fullmatch(r"[<>|][biufc](1|2|4|8|16)", dtype),
        "Explicit numeric dtype required",
    )
    require(
        type(shape) is list
        and len(shape) <= 32
        and all(type(n) is int and n >= 0 for n in shape)
        and type(strides) is list
        and len(strides) == len(shape)
        and all(type(n) is int for n in strides)
        and type(value["C_contiguous"]) is bool
        and type(value["F_contiguous"]) is bool,
        "Typed shape/stride/contiguity required",
    )
    count = 1
    for size in shape:
        count *= size
        require(count <= evidence.payload.MAX_BLOB, "Bounded array extent")

    def contiguous(order):
        if count == 0:
            return True
        expected = int(dtype[2:])
        for axis in order:
            if shape[axis] > 1 and strides[axis] != expected:
                return False
            expected *= shape[axis]
        return True

    require(
        value["C_contiguous"] is contiguous(range(len(shape) - 1, -1, -1))
        and value["F_contiguous"] is contiguous(range(len(shape))),
        "Source contiguity disagrees with exact shape/strides",
    )
    return count * int(dtype[2:])


def wire(value, pins):
    """Validate the independent wire tree and all columns; never decode an owner."""
    require(
        type(value) is dict
        and set(value) == {"tree", "columns"}
        and type(value["columns"]) is dict,
        "Independent typed wire record required",
    )
    columns, used, nodes = value["columns"], set(), 0

    def walk(node, depth=0):
        nonlocal nodes
        nodes += 1
        require(
            nodes <= MAX_NODES and depth <= 64 and type(node) is dict,
            "Bounded typed wire tree required",
        )
        kind = node.get("type")
        if kind == "array":
            require(set(node) == {"type", "layout", "column", "sha256"}, "Exact array node")
            name, layout = node["column"], node["layout"]
            require(
                type(name) is str and name in columns and name not in used, "Unique wire column"
            )
            used.add(name)
            column = columns[name]
            require(
                type(column) is dict and set(column) == {"dtype", "shape", "raw_bytes_hex"},
                "Exact numeric column",
            )
            size = _layout(layout)
            raw = saved._raw_bytes(column["raw_bytes_hex"], pins)
            require(
                column["dtype"] == layout["dtype"]
                and column["shape"] == layout["shape"]
                and raw["size"] == size
                and raw["sha256"] == node["sha256"],
                "Wire column extent/layout/bytes disagree",
            )
            return dict(kind="array", layout=layout, bytes=raw)
        if kind == "object_array":
            require(set(node) == {"type", "layout", "values"}, "Exact object-array node")
            layout = node["layout"]
            require(
                type(layout) is dict and type(layout.get("shape")) is list, "Object-array layout"
            )
            count = 1
            for n in layout["shape"]:
                require(type(n) is int and n >= 0, "Object-array extent")
                count *= n
            require(
                type(node["values"]) is list and count == len(node["values"]),
                "Object-array item extent",
            )
            return dict(
                kind=kind, layout=layout, items=[walk(v, depth + 1) for v in node["values"]]
            )
        if kind in ("dict", "tuple", "list", "set", "frozenset"):
            require(
                set(node) == {"type", "values"} and type(node["values"]) is list,
                "Exact typed container",
            )
            if kind == "dict":
                require(
                    all(type(row) is list and len(row) == 2 for row in node["values"]),
                    "Typed dictionary items",
                )
                items = [[walk(k, depth + 1), walk(v, depth + 1)] for k, v in node["values"]]
            else:
                items = [walk(item, depth + 1) for item in node["values"]]
            return dict(kind=kind, items=items)
        if kind in ("float", "numpy_scalar"):
            expected = {"type", "bits"} if kind == "float" else {"type", "dtype", "bits"}
            require(set(node) == expected, "Exact scalar bit fields")
            raw = saved._raw_bytes(node["bits"], pins)
            if kind == "float":
                require(raw["size"] == 8, "Python float64 extent")
            else:
                require(
                    type(node["dtype"]) is str
                    and re.fullmatch(r"[<>|][biufc](1|2|4|8|16)", node["dtype"])
                    and raw["size"] == int(node["dtype"][2:]),
                    "NumPy scalar extent",
                )
            return {"kind": kind, **{k: v for k, v in node.items() if k != "type"}}
        types = {"str": str, "int": int, "bool": bool, "NoneType": type(None)}
        require(
            kind in types and set(node) == {"type", "value"} and type(node["value"]) is types[kind],
            "Exact typed primitive",
        )
        return dict(kind=kind, value=node["value"])

    result = walk(value["tree"])
    require(used == set(columns), "Unreferenced wire columns")
    return result


def _mapping(node):
    require(type(node) is dict and node.get("kind") == "dict", "Typed dictionary required")
    result = {}
    for key, value in node["items"]:
        require(
            key.get("kind") == "str"
            and type(key.get("value")) is str
            and key["value"] not in result,
            "Unique named dictionary fields required",
        )
        result[key["value"]] = value
    return result


def _scalar(node, kind):
    require(type(node) is dict and node.get("kind") == kind, "Exact typed " + kind)
    return node["value"]


def _f64(node):
    require(node.get("kind") in ("float", "numpy_scalar"), "Original float64 scalar required")
    raw = bytes.fromhex(node["bits"])
    require(len(raw) == 8, "Original float64 extent")
    if node["kind"] == "numpy_scalar":
        require(node["dtype"] in ("<f8", ">f8"), "Explicit float64 dtype")
        if node["dtype"] == ">f8":
            return raw.hex()
    return raw[::-1].hex()


def _demo_node(node):
    """Map authenticated cache nodes to the independent wire's typed vocabulary."""
    kind = node["kind"]
    if kind == "numeric_array":
        layout = node["source_layout"]
        require(_layout(layout) == node["column_observation"]["bytes"]["size"], "Cache extent")
        return dict(kind="array", layout=layout, bytes=node["column_observation"]["bytes"])
    if kind in ("dict", "tuple", "list", "set", "frozenset", "object_array"):
        if kind == "dict":
            items = [[_demo_node(k), _demo_node(v)] for k, v in node["items"]]
        else:
            items = [_demo_node(item) for item in node["items"]]
        result = dict(kind=kind, items=items)
        if kind == "object_array":
            result["layout"] = node["source_layout"]
        return result
    return dict(node)


def _simulator(cache):
    root = cache["descriptor"]
    require(root.get("kind") == "tuple", "Original complete simulator root roster required")
    matches = []
    for item in root["items"]:
        require(item.get("kind") == "tuple" and len(item["items"]) == 2, "Named root tuple")
        name, fields = item["items"]
        if name == dict(kind="str", value="Simulator"):
            matches.append(fields)
    require(len(matches) == 1, "Unique actual INIT Simulator root required; no historical fallback")
    fields = _mapping(_demo_node(matches[0]))
    return {name: fields[name] for name in FIELDS if name in fields}


def _read_iteration(reader, reference, ordinal):
    value, pins = _capture(reader, reference)
    fields = _mapping(wire(value, pins))
    require(
        set(fields)
        == {
            "ordinal",
            "source_time",
            "sampled",
            "configured_dt",
            "fields",
            "numpy_random",
            "python_random",
        },
        "Exact reference iteration fields",
    )
    require(_scalar(fields["ordinal"], "int") == ordinal, "Original one-based reference ordinal")
    return dict(
        ordinal=ordinal - 1,
        source_time_bits=_f64(fields["source_time"]),
        sampled=_scalar(fields["sampled"], "bool"),
        dt_bits=_f64(fields["configured_dt"]),
        fields=_mapping(fields["fields"]),
        epoch=EPOCH,
        rng=dict(epoch=EPOCH, numpy=fields["numpy_random"], python=fields["python_random"]),
    )


def _reference_source(raw):
    """Adoption may fill four reviewed pins; all other producer AST stays exact."""
    tree = ast.parse(raw)
    constants, pins, kept = {}, {}, []
    for node in tree.body:
        if isinstance(node, ast.Assign) and all(isinstance(t, ast.Name) for t in node.targets):
            names = [t.id for t in node.targets]
            if set(names) <= REVIEW_NAMES:
                value = ast.literal_eval(node.value)
                require(value is None or report._hash_identity(value), "Typed review pin adoption")
                pins.update({name: value for name in names})
                continue
            if len(names) == 1 and names[0] in ("CRITICAL", "KIND"):
                constants[names[0]] = ast.literal_eval(node.value)
        kept.append(node)
    tree.body = kept
    require(
        hashlib.sha256(ast.dump(tree, include_attributes=False).encode()).hexdigest()
        == REFERENCE_AST_SHA256,
        "Unreviewed reference source/epoch revision",
    )
    require(set(pins) == REVIEW_NAMES, "Complete reference adoption roster")
    constants["NATIVE_POLICY"] = dict(
        cpu=5, threads=1, max_rss_bytes=2**30, wall_seconds=7200, reserve_bytes=8 * 2**30
    )
    return constants, pins


def _raw_small(value, pins, limit):
    observed = saved._raw_bytes(value, pins)
    require(observed["size"] <= limit, "Bounded calendar bytes required")
    if type(value) is str:
        return bytes.fromhex(value)
    digest = value[evidence.payload.TOKEN]
    row = next(
        row for row in pins if row["sha256"] == digest and Path(row["path"]).name == digest + ".bin"
    )
    raw = Path(row["path"]).read_bytes()
    require(
        len(raw) == observed["size"] and hashlib.sha256(raw).hexdigest() == digest,
        "Calendar sidecar drift",
    )
    return raw


def _reference_calendar(value, pins):
    node = wire(value, pins)
    require(node.get("kind") == "tuple" and len(node["items"]) == 2, "Original calendar/set tuple")
    calendar, samples = node["items"]
    require(
        calendar.get("kind") == "array"
        and len(calendar["layout"]["shape"]) == 1
        and calendar["layout"]["dtype"] in ("<f8", ">f8"),
        "Original float64 calendar",
    )
    count = calendar["layout"]["shape"][0]
    require(type(count) is int and 1 <= count <= MAX_ITERATIONS, "Full original calendar capacity")
    source_array = value["tree"]["values"][0]
    raw = _raw_small(
        value["columns"][source_array["column"]]["raw_bytes_hex"], pins, 8 * MAX_ITERATIONS
    )
    times = [
        raw[i : i + 8].hex() if calendar["layout"]["dtype"] == ">f8" else raw[i : i + 8][::-1].hex()
        for i in range(0, len(raw), 8)
    ]
    require(samples.get("kind") in ("set", "frozenset"), "Original sampled-time set required")
    sampled = [_f64(item) for item in samples["items"]]
    require(len(set(sampled)) == len(sampled), "No duplicate sampled-time bit records")
    return times, set(sampled)


def _reference(reference):
    side = dict(authenticated=False, error=None, complete=False, reader=report.Reader(), rows=[])
    try:
        require(
            type(reference) is dict
            and set(reference) == {"prepared", "release", "controller", "worker"},
            "Exact saved reference file roster required",
        )
        reader = side["reader"]
        plan, release, controller, worker = (
            reader.bound(reference[key]) for key in ("prepared", "release", "controller", "worker")
        )
        require(
            plan.get("kind") == REFERENCE_KIND
            and plan.get("held") is True
            and worker.get("kind") == REFERENCE_KIND,
            "Original reference schema required",
        )
        source = Path(plan["execution_source"]["root"])
        manifest = snapshot.verify(
            source, manifest_sha256=plan["execution_source"]["snapshot_sha256"]
        )
        require(
            release["prepared_sha256"] == reference["prepared"]["sha256"]
            and release["snapshot_sha256"] == plan["execution_source"]["snapshot_sha256"]
            and release["worker_output"] == str(Path(reference["worker"]["path"]).parent),
            "Prepared/release/worker association changed",
        )
        for name, pin in plan["execution_source"]["owned_files"].items():
            require(manifest["files"][name]["sha256"] == pin, "Reference source producer drift")
        native = plan["native_inventory"]
        require(
            saved._seal(native) == plan["native_inventory_sha256"],
            "Original source inventory digest",
        )
        raw_source = (source / REF_SOURCE).read_bytes()
        require(
            hashlib.sha256(raw_source).hexdigest()
            == plan["execution_source"]["owned_files"][REF_SOURCE],
            "Actual reference epoch producer required",
        )
        constants, adoption = _reference_source(raw_source)
        require(
            constants["KIND"] == REFERENCE_KIND
            and constants["CRITICAL"] == plan["source_plan"]["critical_source_pins"]
            and all(native[name]["sha256"] == pin for name, pin in constants["CRITICAL"].items()),
            "Original critical source authority changed",
        )
        for name, variable in (
            ("source", "SOURCE_REVIEW_SHA256"),
            ("bootstrap", "BOOTSTRAP_REVIEW_SHA256"),
            ("writer", "WRITER_REVIEW_SHA256"),
            ("execution", "EXECUTION_RELEASE_SHA256"),
        ):
            require(
                report._hash_identity(adoption[variable])
                and release["reviews"][name]["sha256"] == adoption[variable],
                "Unadopted or retargeted reference release review",
            )
            reader.bound(release["reviews"][name])
        output = Path(release["worker_output"])
        runtime = reader.read(output / "runtime.json")
        for name, row in runtime["loaded_files"].items():
            if row.get("unavailable") is True:
                raise ValueError("Unverifiable loaded reference producer")
            reader.bind(row)
            path = Path(row["path"])
            if path.is_relative_to(source):
                require(
                    manifest["files"][str(path.relative_to(source))]["sha256"] == row["sha256"],
                    "Loaded immutable reference producer drift",
                )
            if name == "betse" or name.startswith("betse."):
                relative = str(path.relative_to(Path(plan["native_root"])))
                require(
                    native[relative]["sha256"] == row["sha256"]
                    and worker["native_producers"][name]["sha256"] == row["sha256"],
                    "Actual original loaded producer drift",
                )
        process_root = Path(reference["controller"]["path"]).parent / "process"
        process_inputs = reader.read(process_root / "process-inputs.json")
        command = process_inputs["command"]
        for flag, expected in (
            ("--worker", reference["prepared"]["path"]),
            ("--prepared-sha256", reference["prepared"]["sha256"]),
            ("--release", reference["release"]["path"]),
            ("--release-sha256", reference["release"]["sha256"]),
            ("--output", str(output)),
        ):
            require(
                command.count(flag) == 1 and command[command.index(flag) + 1] == expected,
                "Reference guarded command association changed",
            )
        require(process_inputs["cwd"] == str(source), "Guarded source directory changed")
        process = reader.read(
            process_root
            / ("failure.json" if (process_root / "failure.json").exists() else "result.json")
        )
        policy, limits = constants["NATIVE_POLICY"], process["limits"]
        require(
            process_inputs["limits"] == limits
            and release["policy"] == policy
            and limits["max_wall_seconds"] == policy["wall_seconds"]
            and limits["max_process_tree_rss_bytes"] == policy["max_rss_bytes"]
            and limits["min_available_host_memory_bytes"] == policy["reserve_bytes"],
            "Reference resource association changed",
        )
        selected = {
            name: row["sha256"] for name, row in plan["inputs"]["inventory"]["files"].items()
        }
        for name, pin in selected.items():
            reader.bind(
                dict(
                    path=str(Path(plan["inputs"]["root"]) / snapshot.relative_path(name)),
                    sha256=pin,
                )
            )
        captures = worker["captures"]
        require(
            type(captures) is list and len(captures) <= MAX_CAPTURES, "Bounded reference captures"
        )
        by_label = {}
        for row in captures:
            require(
                type(row["label"]) is str and row["label"] not in by_label,
                "Unique reference labels",
            )
            by_label[row["label"]] = row
            if row["status"] == "saved":
                require(type(row["files"]) is list and row["files"], "Saved capture pin roster")
                for pin in row["files"]:
                    reader.bind(pin)
                require(
                    Path(row["files"][0]["path"]).is_relative_to(output / "captures"),
                    "Reference capture escaped its actual output",
                )
                require(
                    evidence.files(
                        row["files"][0]["path"], expected_sha256=row["files"][0]["sha256"]
                    )
                    == row["files"],
                    "Complete actual capture/sidecar roster required",
                )
        iterations = worker["iterations"]
        require(
            type(iterations) is list and len(iterations) <= MAX_ITERATIONS,
            "Bounded original iterations",
        )
        for ordinal, pin in enumerate(iterations, 1):
            row = by_label.get(f"iteration_{ordinal:04d}")
            require(
                row is not None and row["status"] == "saved" and pin in row["files"],
                "Original iteration/label/capture association changed",
            )
            side["rows"].append(_read_iteration(reader, pin, ordinal))
        calendar, sample_set, configuration = None, None, None
        if (row := by_label.get("original_calendar")) is not None and row["status"] == "saved":
            value, pins = _capture(reader, row["files"][0])
            calendar, sample_set = _reference_calendar(value, pins)
            require(
                len(side["rows"]) <= len(calendar), "Iterations exceed retained original calendar"
            )
            for index, iteration in enumerate(side["rows"]):
                require(
                    iteration["source_time_bits"] == calendar[index]
                    and iteration["sampled"] is (calendar[index] in sample_set),
                    "Reference row time/sample differs from original calendar/set",
                )
        if (row := by_label.get("final_calendar_configuration")) is not None and row[
            "status"
        ] == "saved":
            value, pins = _capture(reader, row["files"][0])
            configuration = _mapping(wire(value, pins))
        complete = worker.get("status") == "completed"
        if complete:
            require(
                worker.get("primary") is None
                and worker.get("capture_errors") == []
                and worker.get("source_returned") is True
                and worker.get("inherited_hooks_restored") is True
                and worker.get("filesystem_audit_installed") is True
                and worker.get("observer_coverage_failed") is False
                and controller.get("status") == "completed"
                and controller["worker_result_sha256"] == reference["worker"]["sha256"]
                and process["returncode"] == 0
                and process["status"] == "completed",
                "Incomplete reference success",
            )
            require(
                calendar is not None
                and configuration is not None
                and len(iterations) == len(calendar) == _scalar(configuration["init_tsteps"], "int")
                and all(row["dt_bits"] == _f64(configuration["dt"]) for row in side["rows"]),
                "Complete original configured calendar and dt required",
            )
            essential = {
                "betse.science.sim",
                "betse.science.cells",
                "betse.science.parameters",
                "betse.science.phase.phasecls",
                "betse.science.simrunner",
                "betse.science.filehandling",
            }
            require(
                essential <= runtime["loaded_files"].keys(),
                "Completed reference lacks original caller/phase/kernel origins",
            )
            filesystem = reader.read(output / "filesystem.json")
            require(
                filesystem.get("installed") is True
                and filesystem.get("first_error") is None
                and filesystem.get("failures") == []
                and filesystem.get("write_policy", {}).get("first_error") is None
                and filesystem.get("write_policy", {}).get("failures") == [],
                "Completed reference retains filesystem audit failure",
            )
            seed = worker["seed"]
            seed_record = seed["record"]
            require(
                seed_record["path"] == str(output / "config/INITS/world_1.betse.gz")
                and seed["attempts"]
                == [dict(kind="loadWorld", path=seed_record["path"], admitted=True)],
                "Fresh same-workflow native seed association required",
            )
            seed_path = reader.bind(dict(path=seed_record["path"], sha256=seed_record["sha256"]))
            require(
                seed_path.stat().st_size == seed_record["size_bytes"], "Native seed extent changed"
            )
            execution = reader.read(output / "execution-inputs.json")
            require(
                execution["root"] == str(output / "config")
                and execution["source_root"] == plan["inputs"]["root"]
                and execution["inventory"] == plan["inputs"]["inventory"],
                "Fresh execution input association changed",
            )
            copies = execution["files"]
            require(
                type(copies) is list
                and len(copies) == len(selected)
                and all(type(row) is dict and type(row.get("name")) is str for row in copies)
                and len({row["name"] for row in copies}) == len(copies)
                and {row["name"] for row in copies} == set(selected),
                "Exact unique complete execution copy roster required",
            )
            for row in copies:
                require(
                    set(row) == {"name", "status", "sha256", "source_inode", "execution_inode"}
                    and row["status"] == "copied"
                    and all(
                        type(row[key]) is list
                        and len(row[key]) == 2
                        and all(type(value) is int and value >= 0 for value in row[key])
                        for key in ("source_inode", "execution_inode")
                    )
                    and row["source_inode"] != row["execution_inode"]
                    and selected[row["name"]] == row["sha256"],
                    "Execution copy identity changed",
                )
                path = reader.bind(
                    dict(
                        path=str(output / "config" / snapshot.relative_path(row["name"])),
                        sha256=row["sha256"],
                    )
                )
                original = Path(plan["inputs"]["root"]) / row["name"]
                require(
                    [original.stat().st_dev, original.stat().st_ino] == row["source_inode"]
                    and [path.stat().st_dev, path.stat().st_ino] == row["execution_inode"],
                    "Execution copy actual inode association changed",
                )
            require(
                process["elapsed_seconds"] <= policy["wall_seconds"]
                and process["sampled_peak_process_tree_rss_bytes"] <= policy["max_rss_bytes"]
                and process["minimum_available_host_memory_bytes"] >= policy["reserve_bytes"]
                and process["samples"] > 0,
                "Completed reference breached sampled resources",
            )
        side.update(
            authenticated=True,
            complete=complete,
            plan=plan,
            worker=worker,
            mode=plan["inputs"]["mode"],
            selected_input_files=selected,
            source_pins=constants["CRITICAL"],
            runtime=runtime,
            calendar=calendar,
            initial_rng=dict(
                available=False,
                reason="no_authenticated_common_initial_epoch",
                retained_epoch="before_SEED",
            ),
        )
        side["native_inventory"] = {name: row["sha256"] for name, row in native.items()}
        side["configuration_profile"] = plan["source_plan"]["input_profile"]
    except Exception as error:
        side["error"] = _issue(error)
    return side


def _raw_failure_scalar(value, pins):
    """Read archive.snapshot's two float64 scalar encodings without coercion."""
    require(type(value) is dict, "Typed retained failure scalar required")
    if set(value) == {"float64_bits"}:
        raw = _raw_small(value["float64_bits"], pins, 8)
        require(len(raw) == 8, "Retained Python float64 extent")
        return raw[::-1].hex()
    require(
        set(value) == {"numpy_scalar_dtype", "raw_bytes_hex"}
        and value["numpy_scalar_dtype"] in ("<f8", ">f8"),
        "Exact retained NumPy float64 scalar encoding required",
    )
    raw = _raw_small(value["raw_bytes_hex"], pins, 8)
    require(len(raw) == 8, "Retained NumPy float64 extent")
    return (raw[::-1] if value["numpy_scalar_dtype"] == "<f8" else raw).hex()


def _failure_calendar(value, pins):
    if type(value) is dict and "descriptor_json" in value:
        return (
            report._terminal_calendar(value, pins)["calendar_time_bits"],
            dict(encoding="sealed_trial_cache", observation=saved._observation(value, pins)),
        )
    observed = saved._array(value, pins)
    require(
        observed["dtype"] in ("<f8", ">f8")
        and len(observed["shape"]) == 1
        and 1 <= observed["shape"][0] <= MAX_ITERATIONS,
        "Retained raw float64 calendar in [1,512] required",
    )
    raw = _raw_small(value["raw_bytes_hex"], pins, 8 * MAX_ITERATIONS)
    times = [
        (
            raw[index : index + 8][::-1] if observed["dtype"] == "<f8" else raw[index : index + 8]
        ).hex()
        for index in range(0, len(raw), 8)
    ]
    return times, dict(encoding="raw_context_ndarray", observation=observed)


def _failure_samples(value, pins):
    if type(value) is dict and "descriptor_json" in value:
        observed = saved._observation(value, pins)
        require(observed["descriptor"].get("kind") == "tuple", "Retained sampling tuple cache")
        nodes = observed["descriptor"]["items"]
        require(len(nodes) <= MAX_ITERATIONS, "Bounded retained sampling cache")
        bits = [_f64(node) for node in nodes]
        encoding = "sealed_trial_cache"
    else:
        require(
            type(value) is list and len(value) <= MAX_ITERATIONS,
            "Retained raw context scalar sampling list required",
        )
        bits = [_raw_failure_scalar(node, pins) for node in value]
        encoding = "raw_context_scalar_list"
    require(len(set(bits)) == len(bits), "Duplicate retained sampling bits")
    return set(bits), dict(encoding=encoding, float64_bits=bits, original_encoding=value)


def _failed_demo_rows(side, outcome):
    """Read the producer's failure projections, never a synthetic success record."""
    prefix = "init_terminal.failure."
    retained = dict(
        primary=outcome.get("primary"),
        secondary=outcome.get("secondary"),
        saved_failures=side["saved"].get("failures", []),
        capture_attempts=outcome.get("terminal_failure_captures"),
        primary_capture=None,
        completed_iteration_links=[],
        success_record_required=False,
    )
    side["failure_evidence"] = retained
    side["complete"] = False
    require(
        outcome.get("status") == "failed" and retained["primary"] is not None,
        "Actual failed terminal primary required",
    )
    attempts, captures = retained["capture_attempts"], outcome.get("captures")
    require(
        type(attempts) is list
        and len(attempts) <= MAX_CAPTURES
        and type(captures) is list
        and len(captures) <= saved.MAX_CAPTURES,
        "Bounded failed-terminal capture rosters required",
    )
    available = {}
    for row in captures:
        require(
            type(row) is dict and type(row.get("label")) is str and row["label"] not in available,
            "Unique actual capture labels required",
        )
        available[row["label"]] = row
    by_label = {}
    for attempt in attempts:
        require(
            type(attempt) is dict
            and type(attempt.get("label")) is str
            and attempt["label"].startswith(prefix)
            and attempt["label"] not in by_label
            and attempt.get("status") in ("saved", "unavailable", "capture_failed"),
            "Exact failed-terminal attempt labels/statuses required",
        )
        by_label[attempt["label"]] = attempt
        capture = available.get(attempt["label"])
        if attempt["status"] == "saved":
            require(
                capture is not None and capture.get("status") == "saved",
                "Missing declared saved failure capture",
            )
        elif attempt["status"] == "unavailable":
            require(capture is None, "Unavailable failure observation has an actual capture")
        else:
            require("error" in attempt, "Failed observation must retain its capture error")
            require(
                capture is None or capture.get("status") == "capture_failed",
                "Failure observation status differs from actual capture",
            )
    require(
        all(label in by_label for label in available if label.startswith(prefix)),
        "Unlisted failed-terminal capture",
    )
    folder = Path(side["saved"]["output"]) / "worker/demo"

    def load(name):
        attempt = by_label.get(prefix + name)
        if attempt is None or attempt["status"] != "saved":
            return None
        row = available[prefix + name]
        path = folder / snapshot.relative_path(row["path"])
        return saved._read_capture(side, dict(path=str(path), sha256=row["sha256"]))

    primary = load("primary")
    if primary is not None:
        retained["primary_capture"] = primary[0]
    calendar = load("calendar")
    side["calendar"] = None
    if calendar is not None:
        side["calendar"], retained["calendar"] = _failure_calendar(*calendar)
    labels = sorted(
        label
        for label in by_label
        if re.fullmatch(re.escape(prefix) + r"iteration\.[0-9]{4}\.linkage", label)
    )
    after_labels = {
        label
        for label in by_label
        if re.fullmatch(re.escape(prefix) + r"iteration\.[0-9]{4}\.after", label)
    }
    require(
        len(labels) <= MAX_ITERATIONS
        and labels == [prefix + f"iteration.{i:04d}.linkage" for i in range(len(labels))]
        and after_labels == {label.removesuffix(".linkage") + ".after" for label in labels},
        "Contiguous paired failed-terminal linkage/cache roster required",
    )
    if not labels:
        return
    dt, sampled = load("configured_dt"), load("sampled")
    require(
        sampled is not None and calendar is not None,
        "Retained original failure calendar/sample required for prefix rows",
    )
    sample_bits, retained["sampled"] = _failure_samples(*sampled)
    dt_bits = None
    if dt is not None:
        if type(dt[0]) is dict and "descriptor_json" in dt[0]:
            dt_bits = _f64(saved._observation(*dt)["descriptor"])
        else:
            dt_bits = _raw_failure_scalar(*dt)
    retained["configured_dt"] = dict(
        available=dt_bits is not None,
        bits=dt_bits,
        capture_status=by_label.get(prefix + "configured_dt", {}).get("status", "missing"),
        inferred=False,
    )
    for ordinal, label in enumerate(labels):
        name = label.removeprefix(prefix).removesuffix(".linkage")
        link, after = load(name + ".linkage"), load(name + ".after")
        if link is None or after is None:
            retained["unavailable_iteration_ordinal"] = ordinal
            break
        linked = link[0]
        require(
            type(linked) is dict
            and set(linked)
            == {
                "ordinal",
                "source_time_bits",
                "sampled",
                "after_identity",
                "work_end",
                "callbacks_end",
                "molecular_record_identity",
            }
            and type(linked["ordinal"]) is int
            and linked["ordinal"] == ordinal
            and type(linked["sampled"]) is bool
            and ordinal < len(side["calendar"])
            and linked["source_time_bits"] == side["calendar"][ordinal]
            and linked["sampled"] is (linked["source_time_bits"] in sample_bits)
            and all(
                type(linked[key]) is int and linked[key] >= 0
                for key in ("work_end", "callbacks_end", "molecular_record_identity")
            ),
            "Actual failed-prefix time/sample/linkage changed",
        )
        require(
            type(after[0]) is dict
            and report._hash_identity(linked["after_identity"])
            and after[0].get("identity") == linked["after_identity"],
            "Actual failed-prefix state differs from retained linkage",
        )
        cache = saved._observation(*after)
        require(cache is not None, "Unavailable completed failure-prefix cache")
        retained["completed_iteration_links"].append(linked)
        side["rows"].append(
            dict(
                ordinal=ordinal,
                source_time_bits=linked["source_time_bits"],
                sampled=linked["sampled"],
                dt_bits=dt_bits,
                dt_available=dt_bits is not None,
                epoch=EPOCH,
                fields=_simulator(cache),
            )
        )


def _demo(reference, mode):
    side = saved._side(reference, mode)
    side["rows"] = []
    if not side["authenticated"]:
        return side
    try:
        require(side["saved"]["endpoint"] == "init_terminal", "Natural INIT demo endpoint required")
        outcome = saved._pinned_json(
            side, Path(side["saved"]["output"]) / "worker/demo/outcome.json"
        )
        if outcome.get("status") == "failed":
            _failed_demo_rows(side, outcome)
        else:
            observations = saved._observations(side)
            record_item = observations["tissue_INIT:init_terminal.record"]
            record = saved._load_observation(side, record_item)
            require(
                record is not None and record["kind"] == "time_sample_records",
                "Authenticated timing record",
            )
            dt = saved._load_observation(
                side, observations["tissue_INIT:init_terminal.configured_dt"]
            )
            require(dt is not None, "Original configured dt capture")
            dt_bits = _f64(dt["descriptor"])
            for row in record["values"]:
                ordinal = row["ordinal"]
                item = observations.get(f"tissue_INIT:init_terminal.iteration.{ordinal:04d}.after")
                if item is None:
                    break
                cache = saved._load_observation(side, item)
                if cache is None:
                    break
                side["rows"].append(
                    dict(row, dt_bits=dt_bits, epoch=EPOCH, fields=_simulator(cache))
                )
            side["calendar"] = side["saved"]["demonstration"]["natural_terminal"][
                "original_time_bits"
            ]
        require(len(side["rows"]) <= MAX_ITERATIONS, "Demo iteration capacity")
        runtime_path = Path(side["saved"]["output"]) / "worker/runtime-after.json"
        side["runtime"] = saved._pinned_json(side, runtime_path)
        side["selected_input_files"] = side["saved"]["selected_input_files"]
        side["initial_rng"] = dict(
            available=False,
            reason="only_terminal_rng_identity_rosters",
            retained_epoch="INIT_loop_before_setup",
        )
        side["mode"] = mode
        require(
            side["saved"].get("init_native_molecules") is True,
            "Original enabled network/transport selection required",
        )
        require(
            len(side["calendar"]) == len(side["rows"]) if side["complete"] else True,
            "Completed demo lacks the entire calendar",
        )
        side["source_pins"] = {}
        source_root = Path(side["plan"]["source"])
        producer = side["plan"]["producers"].get(
            "src/cells/processes/betse_native_init_terminal_source.py"
        )
        # Native source identities are retained separately from owned source
        # hashes. Do not equate a source-code file digest with a numerical cache.
        demo_plan = side["reader"].bound(side["plan"]["demo_plan"])
        side["native_declaration"] = demo_plan["source_plan"]
        side["owned_source_root"] = str(source_root)
        side["terminal_literal_source_pin"] = producer
        shared = {}
        mandatory = {
            "src/cells/processes/betse_native_init_first_step_source.py": "SOURCE_PINS",
            "src/cells/processes/betse_native_init_molecule_network_source.py": "PINS",
        }
        for relative, binding in mandatory.items():
            path = source_root / relative
            require(
                side["saved"]["source_files"].get(relative) == snapshot.digest(path),
                "Exact literal transport/network source producer required",
            )
            tables = [
                node
                for node in ast.parse(path.read_bytes()).body
                if isinstance(node, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == binding for t in node.targets)
            ]
            require(len(tables) == 1, "Original source table missing")
            for name, pin in ast.literal_eval(tables[0].value).items():
                require(
                    type(name) is str
                    and name.startswith("betse/")
                    and report._hash_identity(pin)
                    and shared.get(name, pin) == pin,
                    "Typed consistent original source pin",
                )
                shared[name] = pin
        side["shared_native_sources"] = shared
        side["configuration_profile"] = side["saved"]["configuration_profile"]
    except Exception as error:
        side.update(authenticated=False, error=_issue(error))
    return side


def compare_views(reference, demo):
    """Pure typed-observation comparison; no saved input becomes a live state."""
    result = dict(
        kind=KIND,
        status="unverified_evidence",
        epochs=EPOCH_MAP,
        provenance={},
        observations=[],
        exact_execution_parity=dict(available=False, equal=None),
        paired_source_complete=False,
        scientific_physical_checkpoint_credit=0,
        work_is_additive=False,
        independent_case_credit=0,
        evidence_authenticated=bool(reference.get("authenticated") and demo.get("authenticated")),
        source_failures=dict(
            reference=dict(
                primary=reference.get("worker", {}).get("primary"),
                capture_errors=reference.get("worker", {}).get("capture_errors", []),
            ),
            demo=demo.get("failure_evidence"),
        ),
    )
    if not reference.get("authenticated") or not demo.get("authenticated"):
        result["errors"] = dict(reference=reference.get("error"), demo=demo.get("error"))
        return result
    checks = dict(
        flux_mode=reference["mode"] == demo["mode"],
        exact_input_files=_same(reference["selected_input_files"], demo["selected_input_files"]),
        configuration_profile=reference.get("configuration_profile")
        == demo.get("configuration_profile"),
    )
    sources = demo.get("shared_native_sources", {})
    checks["original_transport_network_sources"] = bool(sources) and all(
        reference.get("native_inventory", {}).get(name) == pin for name, pin in sources.items()
    )
    result["provenance"] = checks
    if not all(checks.values()):
        result["status"] = "incompatible_provenance"
        return result
    a, b = reference["rows"], demo["rows"]
    require(len(a) <= MAX_ITERATIONS and len(b) <= MAX_ITERATIONS, "Original iteration bound")
    for side, rows in ((reference, a), (demo, b)):
        require(
            all(
                type(row["ordinal"]) is int and row["ordinal"] == index and row["epoch"] == EPOCH
                for index, row in enumerate(rows)
            ),
            "Exact contiguous observation epochs; no shift",
        )
        require(
            all(
                type(row["sampled"]) is bool
                and type(row["source_time_bits"]) is str
                and re.fullmatch("[0-9a-f]{16}", row["source_time_bits"])
                and (
                    type(row["dt_bits"]) is str
                    and re.fullmatch("[0-9a-f]{16}", row["dt_bits"])
                    and row.get("dt_available", True) is True
                    or row["dt_bits"] is None
                    and row.get("dt_available") is False
                    and side["complete"] is False
                )
                for row in rows
            ),
            "Exact original float64 times and typed sample flags",
        )
    complete = reference["complete"] and demo["complete"]
    equality, unavailable, unavailable_timing = True, 0, 0
    for ordinal in range(max(len(a), len(b))):
        left = a[ordinal] if ordinal < len(a) else None
        right = b[ordinal] if ordinal < len(b) else None
        row = dict(ordinal=ordinal, epoch=EPOCH, fields={}, timing=None)
        if left is None or right is None:
            row["status"] = "missing_observation"
            unavailable += 1
        else:
            timing = {
                name: _same(left[name], right[name]) for name in ("source_time_bits", "sampled")
            }
            timing["dt_bits"] = (
                _same(left["dt_bits"], right["dt_bits"])
                if left["dt_bits"] is not None and right["dt_bits"] is not None
                else None
            )
            row["timing"] = timing
            if timing["dt_bits"] is None:
                unavailable += 1
                unavailable_timing += 1
            if any(value is False for value in timing.values()):
                row["status"] = "different_explicit_time_epoch"
                equality = False
            else:
                row["status"] = (
                    "compared_saved_fields_with_unavailable_dt"
                    if timing["dt_bits"] is None
                    else "compared_aligned_saved_observations"
                )
                for name in FIELDS:
                    if name not in left["fields"] or name not in right["fields"]:
                        row["fields"][name] = dict(available=False, equal=None)
                        unavailable += 1
                    else:
                        same = _same(left["fields"][name], right["fields"][name])
                        row["fields"][name] = dict(available=True, equal=same)
                        equality = equality and same
        result["observations"].append(row)
    ra, rb = reference.get("initial_rng", {}), demo.get("initial_rng", {})
    matched_rng = (
        ra.get("available") is True
        and rb.get("available") is True
        and ra.get("epoch") == rb.get("epoch")
        and "state" in ra
        and "state" in rb
        and _same(ra["state"], rb["state"])
    )
    result.update(
        status="compared_saved_observations" if complete else "compared_partial_failed_sources",
        paired_source_complete=bool(complete),
        compared_epochs=min(len(a), len(b)),
        unavailable_observations=unavailable,
        aligned_observations_equal=equality if a and b and unavailable_timing == 0 else None,
        unavailable_timing_observations=unavailable_timing,
        dt_dependent_comparison_available=bool(a and b and unavailable_timing == 0),
    )
    if not matched_rng:
        result["exact_execution_parity"] = dict(
            available=False,
            equal=None,
            reason="unmatched_or_missing_authenticated_common_initial_rng_epoch",
            reference_epoch=ra.get("epoch", ra.get("retained_epoch")),
            demo_epoch=rb.get("epoch", rb.get("retained_epoch")),
        )
    else:
        result["exact_execution_parity"] = dict(
            available=bool(complete and not unavailable),
            equal=equality if complete and not unavailable else None,
            scope="declared saved fields/epochs only",
        )
    return result


def compare_saved(reference, demo):
    """Only explicitly pinned saved paths are read. No discovery, jobs or replay."""
    ref = _reference(reference)
    other = _demo(demo, ref.get("mode", "original"))
    result = compare_views(ref, other)
    result["file_pins"] = {}
    for name, side in (("reference", ref), ("demo", other)):
        reader = side["reader"]
        try:
            for path, pin in tuple(reader.pins.items()):
                reader.bind(dict(path=path, sha256=pin))
        except Exception as error:
            if "unverified_forensics" not in result:
                result["unverified_forensics"] = {
                    key: result[key]
                    for key in (
                        "observations",
                        "aligned_observations_equal",
                        "paired_source_complete",
                        "exact_execution_parity",
                        "provenance",
                        "compared_epochs",
                        "dt_dependent_comparison_available",
                    )
                    if key in result
                }
            result.update(
                status="evidence_changed_during_comparison",
                evidence_authenticated=False,
                paired_source_complete=False,
                observations=[],
                aligned_observations_equal=None,
                compared_epochs=0,
                dt_dependent_comparison_available=False,
                exact_execution_parity=dict(
                    available=False, equal=None, reason="final_evidence_authentication_failed"
                ),
            )
            result.setdefault("errors", {})[name] = _issue(error)
        result["file_pins"][name] = [
            dict(path=path, sha256=pin) for path, pin in sorted(reader.pins.items())
        ]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--request-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    request = report.Reader().bound(dict(path=str(args.request), sha256=args.request_sha256))
    require(set(request) == {"reference", "demo"}, "Exact saved comparison request")
    result = compare_saved(request["reference"], request["demo"])
    snapshot.write_json(args.output, result)
    return int(
        not (
            result.get("evidence_authenticated") is True
            and result.get("paired_source_complete") is True
            and result.get("status") == "compared_saved_observations"
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
