"""Compare authenticated saved SEED and INIT observations, without model imports.

Each saved report is reproduced by the read-only report verifier before use.
Cache identities are not cross-process state equality: typed descriptors are
compared after resolving their numeric columns to authenticated byte digests.
No owner, checkpoint, numerical solver or physical admission is constructed.
"""

import argparse
import hashlib
import json
import math
import re
import struct
from pathlib import Path

from validation.betse import native_seed_demo_evidence as evidence
from validation.betse import native_seed_demo_report as report

KIND = "cells.saved_seed_paired_observations@1"
ENDPOINTS = ("seed", "init_short_history", "init_terminal")
MAX_TERMINAL_ITERATIONS = 512
MAX_CAPTURES = 4096
MAX_NODES = evidence.MAX_NODES
MAX_DIFFERENCES = 128
NATIVE_RNG_ID = "numpy_mt19937_legacy_state_with_gaussian_cache@1"
_ABSENT = object()


def source_plan():
    return dict(
        kind=KIND,
        endpoints=list(ENDPOINTS),
        saved_report_and_underlying_pins_reverified=True,
        matching_inputs_endpoint_iterations_required=True,
        natural_INIT_requires_complete_calendar_and_normal_loop_context_returns=True,
        stopped_history_is_not_natural_INIT=True,
        max_natural_terminal_iterations=MAX_TERMINAL_ITERATIONS,
        byte_comparison="authenticated SHA256 of complete raw bytes; exact typed layouts",
        process_specific_cache_identities_are_not_state_equality=True,
        model_execution=False,
        owner_hydration=False,
        scientific_credit=0,
        physical_parity=False,
        original_flux_defect_repaired=False,
    )


def _same(left, right):
    return json.dumps(left, sort_keys=True, allow_nan=False) == json.dumps(
        right, sort_keys=True, allow_nan=False
    )


def _seal(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def _issue(error):
    return dict(type=type(error).__name__, message=str(error)[:500])


def _json_text(text):
    def invalid(value):
        raise ValueError("Nonstandard descriptor constant: " + value)

    def pairs(rows):
        result = {}
        for key, value in rows:
            report.require(key not in result, "Duplicate descriptor key")
            result[key] = value
        return result

    return json.loads(text, object_pairs_hook=pairs, parse_constant=invalid)


def _raw_bytes(value, pins):
    if type(value) is str:
        report.require(len(value) <= 2 * evidence.payload.MAX_BLOB, "Raw column extent bound")
        raw = bytes.fromhex(value)
        report.require(raw.hex() == value, "Canonical raw column bytes required")
        return dict(sha256=hashlib.sha256(raw).hexdigest(), size=len(raw))
    report.require(
        type(value) is dict and set(value) == {evidence.payload.TOKEN},
        "Authenticated raw column or sidecar token required",
    )
    digest = value[evidence.payload.TOKEN]
    matches = [p for p in pins if p["sha256"] == digest and Path(p["path"]).name == digest + ".bin"]
    report.require(bool(matches), "Raw token lacks its verified binary sidecar")
    sizes = {Path(row["path"]).stat().st_size for row in matches}
    report.require(len(sizes) == 1, "Conflicting raw sidecar extents")
    return dict(sha256=digest, size=sizes.pop())


def _array(value, pins):
    report.require(
        type(value) is dict
        and set(value) == {"__ndarray__", "dtype", "shape", "strides", "raw_bytes_hex"}
        and value["__ndarray__"] is True,
        "Plain numeric array observation required",
    )
    dtype, shape, strides = value["dtype"], value["shape"], value["strides"]
    report.require(
        type(dtype) is str
        and re.fullmatch(r"[<>=|][biufc](1|2|4|8|16)", dtype)
        and type(shape) is list
        and len(shape) <= 32
        and all(type(n) is int and n >= 0 for n in shape)
        and type(strides) is list
        and len(strides) == len(shape)
        and all(type(n) is int for n in strides),
        "Typed numeric dtype, shape and strides required",
    )
    count = 1
    for size in shape:
        count *= size
        report.require(count <= evidence.payload.MAX_BLOB, "Array element extent bound")
    raw = _raw_bytes(value["raw_bytes_hex"], pins)
    report.require(raw["size"] == count * int(dtype[2:]), "Array byte extent differs from shape")
    return dict(kind="numeric_array", dtype=dtype, shape=shape, strides=strides, bytes=raw)


def _cache(value, pins):
    descriptor = value["descriptor_json"]
    report.require(type(descriptor) is str, "Original descriptor text required")
    report.require(
        hashlib.sha256(descriptor.encode()).hexdigest() == value.get("identity"),
        "Cache descriptor identity changed",
    )
    report.require(type(value.get("all_finite")) is bool, "Typed finite observation required")
    columns = value["columns"]
    if type(columns) is list:
        report.require(
            all(type(row) is dict and set(row) == {"name", "values"} for row in columns),
            "Exact column observations required",
        )
        report.require(len({row["name"] for row in columns}) == len(columns), "Duplicate columns")
        columns = {row["name"]: row["values"] for row in columns}
    report.require(type(columns) is dict, "Named numeric cache columns required")
    used, count = set(), 0

    def walk(node, depth=0):
        nonlocal count
        count += 1
        report.require(count <= MAX_NODES and depth <= 64, "Cache descriptor tree bound")
        report.require(type(node) is dict and type(node.get("kind")) is str, "Typed cache node")
        kind = node["kind"]
        if kind == "numeric_array":
            report.require(
                set(node) == {"kind", "source_layout", "column", "sha256"},
                "Exact numeric descriptor fields required",
            )
            name, layout = node["column"], node["source_layout"]
            report.require(type(name) is str and name in columns, "Missing referenced column")
            array = _array(columns[name], pins)
            report.require(
                type(layout) is dict
                and set(layout)
                == {"dtype", "shape", "strides_bytes", "C_contiguous", "F_contiguous"}
                and layout["dtype"] == array["dtype"]
                and layout["shape"] == array["shape"]
                and type(layout["strides_bytes"]) is list
                and len(layout["strides_bytes"]) == len(array["shape"])
                and all(type(n) is int for n in layout["strides_bytes"])
                and type(layout["C_contiguous"]) is bool
                and type(layout["F_contiguous"]) is bool
                and node["sha256"] == array["bytes"]["sha256"],
                "Original array layout/column bytes disagree",
            )
            used.add(name)
            return dict(kind=kind, source_layout=layout, column_observation=array)
        if kind in ("dict", "list", "tuple", "set", "frozenset", "object_array"):
            items = node.get("items")
            report.require(type(items) is list, "Ordered typed items required")
            result = dict(node)
            if kind == "dict":
                report.require(
                    all(type(row) is list and len(row) == 2 for row in items), "Dict items"
                )
                result["items"] = [[walk(k, depth + 1), walk(v, depth + 1)] for k, v in items]
            else:
                result["items"] = [walk(child, depth + 1) for child in items]
            return result
        if kind == "float":
            report.require(set(node) == {"kind", "bits"}, "Exact float cache node required")
            report.require(type(node["bits"]) is str and len(node["bits"]) == 16, "Float bits")
            report.require(
                bytes.fromhex(node["bits"]).hex() == node["bits"], "Canonical float bits"
            )
            return node
        if kind == "numpy_scalar":
            report.require(set(node) == {"kind", "dtype", "bits"}, "Exact scalar cache node")
            raw = _raw_bytes(node["bits"], pins)
            report.require(
                type(node["dtype"]) is str
                and re.fullmatch(r"[<>=|][biufc](1|2|4|8|16)", node["dtype"])
                and raw["size"] == int(node["dtype"][2:]),
                "Scalar dtype/extent",
            )
            return node
        types = {"str": str, "int": int, "bool": bool, "NoneType": type(None)}
        report.require(
            kind in types and set(node) == {"kind", "value"} and type(node["value"]) is types[kind],
            "Unsupported typed scalar cache node",
        )
        return node

    tree = walk(_json_text(descriptor))
    report.require(used == set(columns), "Unused or missing cache columns")
    return dict(kind="typed_cache", all_finite=value["all_finite"], descriptor=tree)


def _observation(value, pins):
    if type(value) is dict and "descriptor_json" in value:
        return _cache(value, pins)
    if type(value) is dict and value.get("__ndarray__") is True:
        return _array(value, pins)
    if type(value) is dict and set(value) == {"float64_bits"}:
        raw = _raw_bytes(value["float64_bits"], pins)
        report.require(raw["size"] == 8, "Float64 scalar extent")
        return dict(kind="float64", bytes=raw)
    if type(value) is list and value and all(report._hash_identity(v) for v in value):
        return dict(kind="stream_identity_roster_only", values=value, full_MT_state_available=False)
    if type(value) is dict and set(value) == {"state_json", "numpy_version", "identity"}:
        state, version = _json_text(value["state_json"]), value["numpy_version"]
        report.require(
            type(state) is list
            and len(state) == 5
            and state[0] == "MT19937"
            and type(state[1]) is list
            and len(state[1]) == 624
            and all(type(v) is int and 0 <= v < 2**32 for v in state[1])
            and any(state[1])
            and type(state[2]) is int
            and 0 <= state[2] <= 624
            and type(state[3]) is int
            and state[3] in (0, 1)
            and type(state[4]) is float
            and math.isfinite(state[4])
            and type(version) is str
            and 0 < len(version) <= 64,
            "Complete typed saved MT19937 state required",
        )
        report.require(
            _seal(dict(rng_id=NATIVE_RNG_ID, numpy_version=version, state=state))
            == value["identity"],
            "Saved MT state identity changed",
        )
        # Preserve original state text and Gaussian bits; no RNG object or draw.
        return dict(
            kind="saved_full_MT_state",
            state_json=value["state_json"],
            numpy_version=version,
            gaussian_bits=struct.pack("!d", state[4]).hex(),
        )
    if type(value) is list and len(value) == 2 and all(type(v) is dict for v in value):
        parts = [_observation(v, pins) for v in value]
        if all(part is not None for part in parts):
            return dict(kind="saved_full_stream_pair", values=parts)
    return None


def _side(reference, mode):
    side = dict(
        mode=mode, reference=reference, authenticated=False, error=None, reader=report.Reader()
    )
    if reference is None:
        side["status"] = "missing_report"
        return side
    try:
        report.require(
            type(reference) is dict and set(reference) == {"report", "plan"}, "Attempt pins"
        )
        reader = side["reader"]
        saved, plan = reader.bound(reference["report"]), reader.bound(reference["plan"])
        report.require(saved.get("kind") == report.KIND, "Saved report schema required")
        report.require(
            saved.get("plan_sha256") == reference["plan"]["sha256"], "Saved plan binding"
        )
        report.require(saved.get("flux_operator") == mode, "Exact original/disabled side required")
        report.require(saved.get("endpoint") in ENDPOINTS, "Only explicit SEED/INIT endpoints")
        fresh = report.inspect_attempt(
            reference["plan"]["path"],
            plan_sha256=reference["plan"]["sha256"],
            output=saved.get("output"),
        )
        report.require(
            _same(saved, fresh), "Saved report differs from current authenticated inspection"
        )
        pins = fresh["observed_file_pins"]
        report.require(len(pins) <= 32768, "Saved report file roster bound")
        for row in pins:
            reader.bind(row)
        side.update(
            authenticated=True,
            status=fresh["status"],
            saved=fresh,
            plan=plan,
            complete=(
                fresh["status"] == "completed_unqualified"
                and fresh.get("source_execution_complete") is True
                and fresh.get("source_evidence_complete") is True
                and fresh["verification_issues"] == []
            ),
        )
    except Exception as error:
        side.update(status="unverified_report", error=_issue(error))
    return side


def _pinned_json(side, path):
    reader = side["reader"]
    path = evidence.payload._regular(path)
    report.require(str(path) in reader.pins, "Observation is outside authenticated report pins")
    return reader.bound(dict(path=str(path), sha256=reader.pins[str(path)]))


def _selected_label(label):
    return (
        label
        in (
            "completed_geometry.cache",
            "poisson.cache",
            "core.cache",
            "profiles.after",
            "junctions.cache",
        )
        or label.startswith("geometry.stage-")
        or (
            label.split(".")[0] in ("phase", "lattice", "image", "mesh", "lifecycle", "geometry")
            and label.endswith(
                (".cache", ".rng_before", ".rng_after", ".stream_before", ".stream_after")
            )
        )
        or (
            label.startswith("init_")
            and label.endswith(
                (
                    ".before",
                    ".after",
                    ".calendar",
                    ".sampled",
                    ".configured_dt",
                    ".stream_before",
                    ".stream_after",
                    ".rng_before",
                    ".rng_after",
                )
            )
        )
    )


def _read_capture(side, reference):
    pins = evidence.files(reference["path"], expected_sha256=reference["sha256"])
    for pin in pins:
        report.require(
            side["reader"].pins.get(pin["path"]) == pin["sha256"], "Unbound capture sidecar"
        )
        side["reader"].bind(pin)
    return evidence.read(reference["path"], expected_sha256=reference["sha256"], expand=False), pins


def _record_associations(side, rows, folder, domain):
    """Use the actual producer's record/tuple positions, not synthetic labels."""
    expected = {}
    for row in rows:
        label = row["label"]
        if not label.endswith(".record") or row["status"] != "saved":
            continue
        role = label.removesuffix(".record")
        report.snapshot.relative_path(row["path"])
        record, _ = _read_capture(side, dict(path=str(folder / row["path"]), sha256=row["sha256"]))
        report.require(type(record) is dict, "Typed saved stage record required")

        def association(target, *, record_label=label, record_sha256=row["sha256"], **fields):
            value = dict(record_label=record_label, record_sha256=record_sha256, **fields)
            report.require(
                target not in expected or expected[target] == value,
                "Conflicting record associations",
            )
            expected[target] = value

        if domain == "geometry":
            if role == "phase":
                stages = record.get("stages")
                report.require(
                    type(stages) is list and len(stages) == 4,
                    "Four phase-stage identities required",
                )
                for index, identity in enumerate(stages):
                    association(
                        f"phase.stage_trials.{index}.cache.cache",
                        stage_index=index,
                        stage_trial_identity=identity,
                        cache_identity_not_in_record=True,
                    )
            if role == "geometry":
                stages = record.get("stages", [])
                report.require(
                    type(stages) is list and len(stages) <= 64, "Geometry stage record bound"
                )
                for index, entry in enumerate(stages):
                    report.require(
                        type(entry) is list
                        and len(entry) == 2
                        and all(type(v) is str for v in entry),
                        "Named stage/cache identity pair required",
                    )
                    association(
                        f"geometry.stage_caches.{index}.1.cache",
                        stage_index=index,
                        native_method=entry[0],
                        expected_identity=entry[1],
                    )
            for field, target in (
                ("before_MT", "stream_before"),
                ("after_MT", "stream_after"),
                ("rng_before", "rng_before"),
                ("rng_after", "rng_after"),
                ("stream_before", "stream_before"),
                ("stream_after", "stream_after"),
            ):
                if record.get(field) is not None:
                    association(role + "." + target, expected_identity=record[field])
        else:
            mapping = (("rng_before", "rng_before"), ("rng_after", "rng_after"))
            if role in ("init_short_history", "init_terminal"):
                mapping = (("rng_before", "stream_before"), ("rng_after", "stream_after"))
            elif role == "init_storage":
                mapping = (("streams_before", "stream_before"), ("streams_after", "stream_after"))
            elif role == "init_dynamics":
                mapping = (("stream_before", "stream_before"), ("stream_after", "stream_after"))
            for field, target in mapping:
                if record.get(field) is not None:
                    association(role + "." + target, expected_stream_ids=record[field])
            if role == "init_terminal":
                for field, target in (
                    ("before", "before"),
                    ("after", "after"),
                    ("calendar", "calendar"),
                    ("sampled", "sampled"),
                    ("dt", "configured_dt"),
                ):
                    if record.get(field) is not None:
                        report.require(
                            report._hash_identity(record[field]),
                            "Original terminal cache identity required",
                        )
                        association(role + "." + target, expected_identity=record[field])
                iterations = record.get("iterations", [])
                report.require(
                    type(iterations) is list and len(iterations) <= MAX_TERMINAL_ITERATIONS,
                    "Bounded retained terminal iteration records required",
                )
                for ordinal, entry in enumerate(iterations):
                    report.require(
                        type(entry) is list
                        and len(entry) == 8
                        and type(entry[0]) is int
                        and entry[0] == ordinal
                        and report._hash_identity(entry[3]),
                        "Original terminal iteration/cache association required",
                    )
                    association(
                        f"init_terminal.iteration.{ordinal:04d}.after",
                        expected_identity=entry[3],
                        iteration_ordinal=ordinal,
                    )
    return expected


def _observations(side):
    observed = {}
    if not side["authenticated"] or "output" not in side["saved"]:
        return observed
    root = Path(side["saved"]["output"]) / "worker" / "demo"
    for domain, folder in (("tissue_INIT", root), ("geometry", root / "geometry")):
        path = folder / "outcome.json"
        if str(path) not in side["reader"].pins:
            continue
        outcome = _pinned_json(side, path)
        rows = outcome.get("captures", [])
        report.require(type(rows) is list and len(rows) <= MAX_CAPTURES, "Capture roster bound")
        associations = _record_associations(side, rows, folder, domain)
        seen = set()
        for row in rows:
            label = row["label"]
            report.require(
                type(label) is str and label not in seen, "Unique capture labels required"
            )
            seen.add(label)
            is_timing = label in ("init_short_history.record", "init_terminal.record")
            if not _selected_label(label) and not is_timing:
                continue
            key = domain + ":" + label
            item = dict(
                status=row["status"],
                association=associations.get(label),
                stage_completed=(
                    outcome.get("status") == "source_completed"
                    if domain == "geometry"
                    else label.split(".")[0] in outcome.get("completed_stage_trials", [])
                ),
            )
            observed[key] = item
            if row["status"] != "saved":
                continue
            report.snapshot.relative_path(row["path"])
            item["raw"] = dict(path=str(folder / row["path"]), sha256=row["sha256"])
            item["timing"] = is_timing
            if label == "init_terminal.record":
                item["natural_terminal"] = True
        for label, association in associations.items():
            key = domain + ":" + label
            if key not in observed:
                observed[key] = dict(
                    status="missing_producer_observation",
                    association=association,
                    stage_completed=False,
                )
    return observed


def _iteration_observation(value, *, natural_terminal=False):
    """Compare original time bits; a selected stop cannot pass as natural return."""
    values = value["iterations"]
    maximum = MAX_TERMINAL_ITERATIONS if natural_terminal else 64
    report.require(
        type(values) is list and 1 <= len(values) <= maximum, "Bounded iteration records"
    )
    timing = []
    for ordinal, row in enumerate(values):
        report.require(
            type(row) is list
            and len(row) == 8
            and type(row[0]) is int
            and row[0] == ordinal
            and type(row[1]) is str
            and re.fullmatch("[0-9a-f]{16}", row[1])
            and type(row[2]) is bool,
            "Original ordinal/time/sample record",
        )
        timing.append(dict(ordinal=ordinal, source_time_bits=row[1], sampled=row[2]))
    result = dict(kind="time_sample_records", values=timing)
    if natural_terminal:
        expected = dict(
            source_completed=True, loop_returned=True, context_returned=True, selected_stop=False
        )
        report.require(
            all(value.get(name) is wanted for name, wanted in expected.items()),
            "Actual whole-calendar normal INIT returns required; selected stops are not terminals",
        )
        result["natural_terminal"] = dict(**expected, completed_iterations=len(values))
    return result


def _load_observation(side, item):
    if item is None or item["status"] != "saved":
        return None
    try:
        value, pins = _read_capture(side, item["raw"])
        association = item.get("association") or {}
        if "expected_identity" in association:
            report.require(
                type(value) is dict and value.get("identity") == association["expected_identity"],
                "Actual capture differs from its stage record identity",
            )
        if "expected_stream_ids" in association:
            if type(value) is not list or not (
                all(report._hash_identity(v) for v in value)
                or all(type(v) is dict and report._hash_identity(v.get("identity")) for v in value)
            ):
                item["status"] = "unsupported_stream_observation"
                return None
            identities = (
                [v["identity"] for v in value] if value and type(value[0]) is dict else value
            )
            report.require(
                _same(identities, association["expected_stream_ids"]),
                "Actual stream capture differs from stage record",
            )
        if item["timing"]:
            return _iteration_observation(
                value, natural_terminal=item.get("natural_terminal") is True
            )
        result = _observation(value, pins)
        if result is None:
            item["status"] = "unsupported_or_identity_only_observation"
        return result
    except Exception as error:
        item.update(status="unverified_observation", error=_issue(error))
        return None


def _differences(left, right):
    rows, total, nodes = [], 0, 0

    def walk(a, b, path):
        nonlocal total, nodes
        nodes += 1
        report.require(nodes <= MAX_NODES, "Comparison tree bound")
        if type(a) is dict and type(b) is dict:
            for key in sorted(a.keys() | b.keys()):
                walk(a.get(key, _ABSENT), b.get(key, _ABSENT), path + [key])
            return
        if type(a) is list and type(b) is list:
            for index in range(max(len(a), len(b))):
                walk(
                    a[index] if index < len(a) else _ABSENT,
                    b[index] if index < len(b) else _ABSENT,
                    path + [index],
                )
            return
        if a is _ABSENT or b is _ABSENT or not _same(a, b):
            total += 1
            if len(rows) < MAX_DIFFERENCES:

                def small(value):
                    if value is _ABSENT:
                        return None
                    if type(value) in (dict, list):
                        return dict(
                            container=type(value).__name__, length=len(value), sha256=_seal(value)
                        )
                    return value

                rows.append(
                    dict(
                        path=path,
                        original_present=a is not _ABSENT,
                        disabled_present=b is not _ABSENT,
                        original=small(a),
                        disabled=small(b),
                    )
                )

    walk(left, right, [])
    return dict(
        equal=total == 0,
        difference_count=total,
        differences=rows,
        difference_list_complete=total <= MAX_DIFFERENCES,
    )


def compare_saved(original, disabled):
    """Read only explicitly pinned saved reports; never discover, query or wait for jobs."""
    sides = [_side(original, "original"), _side(disabled, "disabled")]
    result = dict(
        kind=KIND,
        status="incomplete_evidence",
        attempts={},
        provenance={},
        observations=[],
        timing=None,
        paired_execution_complete=False,
        all_available_observations_equal=None,
        numerical_or_conservation_qualification=False,
        scientific_credit=0,
        physical_parity=False,
        ordinary_checkpoint_admitted=False,
        original_flux_defect_repaired=False,
        work_ledgers_additive=False,
        independent_cases=0,
        comparison_scope="Saved typed data/layout/byte digests and time/sample/RNG evidence only",
    )
    for side in sides:
        result["attempts"][side["mode"]] = dict(
            reference=side["reference"],
            status=side["status"],
            authenticated=side["authenticated"],
            error=side["error"],
            complete=side.get("complete", False),
            verified_file_pins=len(side["reader"].pins),
            saved_failure_records=len(side.get("saved", {}).get("failures", [])),
            saved_verification_issues=side.get("saved", {}).get("verification_issues", []),
        )
    if not all(side["authenticated"] for side in sides):
        return result
    left, right = (side["saved"] for side in sides)
    mandatory = (
        "source_files",
        "original_input_files",
        "selected_input_files",
        "configuration_profile",
        "configuration_changes",
        "endpoint",
        "init_iterations_requested",
        "init_native_molecules",
    )
    checks = {name: _same(left.get(name), right.get(name)) for name in mandatory}
    checks["distinct_saved_attempts"] = (
        original["report"]["path"] != disabled["report"]["path"]
        and original["plan"]["path"] != disabled["plan"]["path"]
        and left.get("output") != right.get("output")
    )
    result["provenance"] = checks
    result["policy_equal"] = _same(left.get("policy"), right.get("policy"))
    result["domain_diagnostics"] = {
        side["mode"]: (side["saved"].get("geometry") or {}).get("diagnostics") for side in sides
    }
    result["flux_modes"] = dict(
        original="native_flux_inverse_retained", disabled="only_flux_inverse_omitted"
    )
    if not all(checks.values()):
        result["status"] = "incompatible_provenance"
        return result
    collected = []
    for side in sides:
        try:
            collected.append(_observations(side))
        except Exception as error:
            result["attempts"][side["mode"]]["observation_error"] = _issue(error)
            collected.append({})
    a, b = collected
    compared, unavailable, equal = 0, 0, True
    for key in sorted(a.keys() | b.keys()):
        pair = [a.get(key), b.get(key)]
        row = dict(label=key, original=pair[0], disabled=pair[1])
        values = [_load_observation(side, item) for side, item in zip(sides, pair, strict=True)]
        if all(value is not None for value in values):
            try:
                row["comparison"] = _differences(*values)
                compared += 1
                equal = equal and row["comparison"]["equal"]
                if values[0]["kind"] == values[1]["kind"] == "time_sample_records":
                    result["timing"] = row["comparison"]
            except Exception as error:
                row["comparison_error"] = _issue(error)
                unavailable += 1
        else:
            unavailable += 1
        # Raw values stay in their pinned captures; do not duplicate large descriptors.
        for label, item in (("original", pair[0]), ("disabled", pair[1])):
            if item is not None:
                row[label] = {k: v for k, v in item.items() if k not in ("raw", "timing")}
        result["observations"].append(row)
    complete = all(side.get("complete") for side in sides)
    result.update(
        status="compared_completed_attempts" if complete else "compared_partial_or_failed_attempts",
        paired_execution_complete=complete,
        compared_observations=compared,
        unavailable_observations=unavailable,
        all_available_observations_equal=equal if compared else None,
        all_requested_observations_available=(compared > 0 and unavailable == 0),
    )
    for side in sides:
        try:
            for path, pin in tuple(side["reader"].pins.items()):
                side["reader"].bind(dict(path=path, sha256=pin))
        except Exception as error:
            result["attempts"][side["mode"]]["final_pin_error"] = _issue(error)
            result.update(
                status="evidence_changed_during_comparison",
                paired_execution_complete=False,
                all_available_observations_equal=None,
            )
    result["reader_producers"] = {
        str(Path(module.__file__).resolve()): report.snapshot.digest(Path(module.__file__))
        for module in (report, evidence)
    }
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for mode in ("original", "disabled"):
        parser.add_argument("--" + mode + "-report", type=Path)
        parser.add_argument("--" + mode + "-report-sha256")
        parser.add_argument("--" + mode + "-plan", type=Path)
        parser.add_argument("--" + mode + "-plan-sha256")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    def reference(mode):
        path = getattr(args, mode + "_report")
        if path is None:
            report.require(
                all(
                    getattr(args, mode + suffix) is None
                    for suffix in ("_report_sha256", "_plan", "_plan_sha256")
                ),
                "Missing side has partial arguments",
            )
            return None
        return dict(
            report=dict(path=str(path), sha256=getattr(args, mode + "_report_sha256")),
            plan=dict(
                path=str(getattr(args, mode + "_plan")), sha256=getattr(args, mode + "_plan_sha256")
            ),
        )

    result = compare_saved(reference("original"), reference("disabled"))
    report.snapshot.write_json(args.output, result)
    return 0 if result["paired_execution_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
