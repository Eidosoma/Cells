"""Source/format accounting for complete event, mechanics and lifecycle archives.

No scientific module or NumPy writer is imported or evaluated. The bound charges
every repeated snapshot independently using the pinned uncompressed writer.
"""

import ast
import hashlib
import json
import struct
import sys
import zipfile
from pathlib import Path

ROOT = Path("/home/robert/Cells")
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
BASE = Path("/mnt/workspaces/Cells")
PREFIX = "betse_normal_ecm_capture_limits"
NUMPY = BASE / "venv-cpu/lib/python3.13/site-packages/numpy"
PROFILES = {
    "event04": (
        "betse-normal-ecm-event-join-prepared-20261031-04",
        "betse_normal_ecm_event_join",
        "normal-ecm-event-join",
    ),
    "event_mechanics03": (
        "betse-normal-ecm-event-mechanics-prepared-20261031-03",
        "betse_normal_ecm_event_mechanics",
        "normal-ecm-event-mechanics",
    ),
    "lifecycle02": (
        "betse-normal-ecm-run-lifecycle-prepared-20261031-02",
        "betse_normal_ecm_run_lifecycle",
        "normal-ecm-run-lifecycle",
    ),
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def row(path):
    return dict(path=str(path), sha256=sha(path))


def functions(path):
    return {
        n.name: n for n in ast.parse(Path(path).read_text()).body if isinstance(n, ast.FunctionDef)
    }


def site(path, node):
    return dict(
        path=str(path),
        line=node.lineno,
        end_line=node.end_lineno,
        AST_sha256=hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest(),
    )


def scopes(tree, node):
    enclosing = [
        n
        for n in ast.walk(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        and n.lineno <= node.lineno <= n.end_lineno
    ]
    return min(enclosing, key=lambda n: n.end_lineno - n.lineno).name if enclosing else "<module>"


def audit():
    npio_path, fmt_path = NUMPY / "lib/_npyio_impl.py", NUMPY / "lib/_format_impl.py"
    npio, fmt = functions(npio_path), functions(fmt_path)
    assert (
        ast.unparse(npio["savez"].body[-1])
        == "_savez(file, args, kwds, False, allow_pickle=allow_pickle)"
    )
    savez = ast.unparse(npio["_savez"])
    for marker in (
        "compression = zipfile.ZIP_STORED",
        "fname = key + '.npy'",
        "force_zip64=True",
        "format.write_array(",
        "zipf.close()",
    ):
        assert marker in savez, marker
    wrap, header = ast.unparse(fmt["_wrap_header"]), ast.unparse(fmt["_write_array_header"])
    assert "ARRAY_ALIGN - (MAGIC_LEN + struct.calcsize(fmt) + hlen) % ARRAY_ALIGN" in wrap
    assert "hlen = len(header) + 1" in wrap
    assert "header_prefix + header + b' ' * padlen + b'\\n'" in wrap
    assert "sorted(d.items())" in header and "repr(value)" in header
    assert "header.append('}')" in header and "fp.write(header)" in header
    fmt_tree = ast.parse(fmt_path.read_text())
    alignment = next(
        ast.literal_eval(n.value)
        for n in fmt_tree.body
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "ARRAY_ALIGN" for t in n.targets)
    )
    assert alignment == 64
    assert (zipfile.sizeFileHeader, zipfile.sizeCentralDir, zipfile.sizeEndCentDir) == (30, 46, 22)
    # The pinned writer formats a trailing comma/space after every header key.
    # Plain biuf dtype strings are at least three characters. Empty shape and
    # True give the shortest header (54); real scalars use False (55).
    headers = []
    for order in (True, False):
        value = (
            "{"
            + "".join(
                f"'{key}': {item!r}, "
                for key, item in sorted(dict(descr="|b1", fortran_order=order, shape=()).items())
            )
            + "}"
        )
        prefix = 6 + 2 + struct.calcsize("<H")
        bare = prefix + len(value) + 1
        padded = bare + alignment - bare % alignment
        headers.append(
            dict(
                fortran_order=order,
                header_characters=len(value),
                prefix_bytes=prefix,
                before_alignment_bytes=bare,
                NPY_header_bytes=padded,
            )
        )
    assert min(h["header_characters"] for h in headers) == 54
    assert min(h["NPY_header_bytes"] for h in headers) == 128
    npy_min = 128
    filename_min = len("a0.npy".encode("ascii"))
    per_member = npy_min + zipfile.sizeFileHeader + zipfile.sizeCentralDir + 2 * filename_min
    max_bytes = 64 * 2**20
    fixed = (max_bytes - zipfile.sizeEndCentDir) // per_member
    assert per_member == 216 and fixed == 310689
    assert 22 + fixed * 216 <= max_bytes < 22 + (fixed + 1) * 216
    packets = {}
    source_pins = {
        str(p): sha(p)
        for p in (
            NUMPY / "__init__.py",
            NUMPY / "lib/npyio.py",
            npio_path,
            NUMPY / "lib/format.py",
            fmt_path,
            Path(zipfile.__file__),
        )
    }
    for profile, (directory, prefix, evidence_root) in PROFILES.items():
        packet = BASE / directory
        inputs = json.loads((packet / "inputs.json").read_text())
        closure = inputs["scientific_import_closure"]
        writer_sites, call_sites = [], []
        for relative, expected in closure.items():
            path = packet / "source" / relative
            assert sha(path) == expected, relative
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr in ("savez", "savez_compressed")
                ):
                    assert ast.unparse(node.func) == "np.savez"
                    owner = scopes(tree, node)
                    assert owner == "write_archive"
                    writer = functions(path)[owner]
                    text = ast.unparse(writer)
                    assert "a.dtype.kind not in 'biuf'" in text
                    assert "key = 'a' + str(len(arrays))" in text
                    assert "np.array(a, copy=True)" in text
                    assert "np.savez(" in text and "savez_compressed" not in text
                    source_pins[str(path)] = sha(path)
                    writer_sites.append(
                        dict(
                            **site(path, writer),
                            module=relative,
                            no_identity_deduplication=True,
                            terminal_writer="np.savez",
                        )
                    )
            if relative in (
                "tests/unit/test_" + prefix + ".py",
                "validation/betse/" + prefix + "_native.py",
            ):
                for node in ast.walk(tree):
                    if not isinstance(node, ast.Call):
                        continue
                    callee = ast.unparse(node.func)
                    if callee == "archive" or callee.endswith(".write_archive"):
                        call_sites.append(
                            dict(
                                **site(path, node),
                                module=relative,
                                function=scopes(tree, node),
                                callee=callee,
                                payload_AST=ast.unparse(node.args[-1]) if node.args else None,
                            )
                        )
                source_pins[str(path)] = sha(path)
        assert {r["module"] for r in writer_sites} == {
            "validation/betse/betse_fast_solver_native.py",
            "validation/betse/betse_normal_current_native.py",
        }
        assert call_sites
        source_pins[str(packet / "inputs.json")] = sha(packet / "inputs.json")
        packets[profile] = dict(
            packet_inputs=row(packet / "inputs.json"),
            prefix=prefix,
            evidence_subdirectory=evidence_root,
            complete_writer_definition_sites=writer_sites,
            actual_capture_archive_call_sites=call_sites,
            archive_call_sites=len(call_sites),
            count_scope=(
                "Per emitted archive, never summed across a run or deduplicated across snapshots"
            ),
            maximum_member_count_implied_by_unchanged_writer_and_64MiB=fixed,
            new_fixed_limit=fixed,
            coverage=dict(
                native_complete_and_partial_capture=True,
                supplied_cold_bootstrap_and_typed_parents=True,
                actual_pre_and_post_component_callbacks=True,
                dependency_corruption_and_unexpected_failures=True,
                repeated_state_context_cache_and_array_owners_charged_separately=True,
                mechanics_trials_frames_and_native_partials=profile != "event04",
                clock_only_INIT_SIM_labels=profile == "lifecycle02",
                observer_callbacks_and_failed_last_accepted_run=profile == "lifecycle02",
                window_completed_transitions_caller_attempt_and_returned_candidate=profile
                == "lifecycle02",
                native_failed_reached_clock_component_exception_archive=profile == "lifecycle02",
                raw_case_specific_native_capture_plus_component_partial=profile == "lifecycle02",
            ),
            actual_case_member_counts_measured=False,
            all_captures_fit_64MiB_claim=False,
            qualification_or_release_credit=0,
        )
    return dict(
        kind="cells.complete_ECM_capture_member_capacity_source_accounting@1",
        status="source_format_capacity_bound_ready_for_independent_review",
        method=(
            "Charge every array occurrence at the actual uncompressed writer, including all "
            "repeated state/observer/failure paths; apply unchanged total archive bytes"
        ),
        scope_profiles=packets,
        source_sha256=source_pins,
        numeric_header_source=dict(
            source=row(fmt_path),
            header_function=site(fmt_path, fmt["_write_array_header"]),
            padding_function=site(fmt_path, fmt["_wrap_header"]),
            minimal_header_scalar_metadata_cases=headers,
        ),
        capacity_derivation=dict(
            unchanged_archive_file_bytes=max_bytes,
            unchanged_expanded_and_JSON_bytes=max_bytes,
            minimum_accepted_plain_dtype_string_length=3,
            minimum_header_text_characters=54,
            minimum_NPY_prefix_and_newline_bytes=11,
            alignment=64,
            minimum_NPY_member_bytes=npy_min,
            minimum_local_ZIP_header_bytes=30,
            minimum_central_ZIP_header_bytes=46,
            minimum_canonical_filename_bytes=filename_min,
            filename_copies=2,
            minimum_total_archive_bytes_per_member=per_member,
            minimum_end_record_bytes=22,
            formula="floor((67108864 - 22) / (128 + 30 + 46 + 2*6))",
            new_fixed_member_limit=fixed,
            ignored_positive_overhead=[
                "numeric payload bytes",
                "longer owner names",
                "ZIP64 extra fields",
                "ZIP64 end records",
                "longer shapes/dtypes/headers",
                "growth padding",
            ],
        ),
        original_catalog_limit=32768,
        original_catalog_schema_allowance=31726,
        original_catalog_allowance_remains_catalog_only=True,
        catalogue_profile_may_not_select_this_tool=True,
        producer_policy=(
            "Only pinned plain-numeric np.savez/ZIP_STORED capture writers; changed "
            "writer/format/compression requires a new review"
        ),
        no_semantic_case_maximum_or_physical_model_bound_claim=True,
        external_worker_memory_time_and_host_reserve_limits_still_required=True,
        all_other_type_shape_hash_CRC_byte_depth_and_owner_guards_unchanged=True,
        scientific_imports=0,
        scientific_AST_executions=0,
        fixture_evaluations=0,
        reference_evaluations=0,
        pytest_collection_runs=0,
        numerical_runs=0,
        active_job_queries=0,
        new_or_retained_qualification_passes=0,
        automatic_launch=False,
        automatic_polling=False,
        automatic_followup=False,
        python=dict(executable=sys.executable, version=sys.version),
    )


if __name__ == "__main__":
    result = audit()
    path = WORK / (PREFIX + "_accounting_01.json")
    with path.open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(
        json.dumps(
            dict(
                path=str(path),
                sha256=sha(path),
                member_limit=result["capacity_derivation"]["new_fixed_member_limit"],
                call_sites={
                    k: v["archive_call_sites"] for k, v in result["scope_profiles"].items()
                },
                numerical_runs=0,
            )
        )
    )
