"""Bounded stdlib-only archive controls; construct no scientific arrays or models."""

import ast
import hashlib
import importlib.abc
import importlib.util
import json
import resource
import signal
import struct
import sys
import time
import traceback
import zipfile
from pathlib import Path

from betse_normal_ecm_capture_limits_audit import BASE, PREFIX, WORK, sha

TOOLS = WORK / (PREFIX + "_prepared_01")
OUT = WORK / (PREFIX + "_software_01")
DENIED = {"cells", "betse", "numpy", "scipy", "jax", "jaxlib", "pytest"}


class NoScience(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in DENIED:
            raise ImportError("Metadata-only capture check denies: " + fullname)


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, sort_keys=True, allow_nan=False)
        stream.write("\n")


def available():
    return (
        int(
            next(
                line.split()[1]
                for line in Path("/proc/meminfo").read_text().splitlines()
                if line.startswith("MemAvailable:")
            )
        )
        * 1024
    )


def make(
    name, count=1, *, dtype="<f8", payload=struct.pack("<d", -0.0), compression=zipfile.ZIP_STORED
):
    folder = OUT / name
    folder.mkdir()
    header = (
        "{"
        + "".join(
            f"'{key}': {value!r}, "
            for key, value in sorted(dict(descr=dtype, fortran_order=False, shape=()).items())
        )
        + "}"
    )
    padding = 64 - ((10 + len(header) + 1) % 64)
    text = header.encode() + b" " * padding + b"\n"
    data = b"\x93NUMPY\x01\x00" + len(text).to_bytes(2, "little") + text + payload
    assert len(data) >= 128
    tree = dict(sequence=[dict(array="a" + str(i), dtype=dtype, shape=[]) for i in range(count)])
    write(folder / "data.json", tree)
    with zipfile.ZipFile(folder / "arrays.npz", "w", compression=compression) as archive:
        for i in range(count):
            archive.writestr("a" + str(i) + ".npy", data)
    write(
        folder / "manifest.json",
        dict(
            kind="cells.betse_normal_current_raw_evidence@1",
            complete=True,
            files={name: sha(folder / name) for name in ("arrays.npz", "data.json")},
        ),
    )
    return folder


def main():
    resource.setrlimit(resource.RLIMIT_AS, (512 * 2**20, 512 * 2**20))
    resource.setrlimit(resource.RLIMIT_CPU, (90, 90))
    signal.alarm(120)
    assert available() >= 8 * 2**30
    sys.meta_path.insert(0, NoScience())
    sys.path.insert(0, str(TOOLS))
    binding = load_module("capture_capacity_profile", TOOLS / "capture_binding.py")
    old = load_module(
        "catalog_capacity_unchanged",
        BASE / "ecm-catalog-archive-cardinality-repair-20261031-01/archive_binding.py",
    )
    OUT.mkdir(exist_ok=False)
    started = time.monotonic()
    rows = []

    def keep(name, **value):
        assert name not in [r["id"] for r in rows]
        assert available() >= 8 * 2**30
        rows.append(dict(id=name, status="passed", **value))

    def refuses(name, callback, fragment):
        try:
            callback()
        except (ValueError, KeyError, zipfile.BadZipFile) as error:
            assert fragment in str(error), (name, type(error).__name__, str(error))
            keep(
                name,
                expected_fragment=fragment,
                actual_type=type(error).__name__,
                actual_message=str(error),
            )
        else:
            raise AssertionError("Malformed metadata admitted: " + name)

    try:
        write(
            OUT / "inputs.json",
            dict(
                tools_inputs=dict(
                    path=str(TOOLS / "inputs.json"), sha256=sha(TOOLS / "inputs.json")
                ),
                metadata_check_source=dict(path=str(Path(__file__)), sha256=sha(__file__)),
                max_address_space_bytes=512 * 2**20,
                max_CPU_seconds=90,
                max_wall_seconds=120,
                min_host_reserve_bytes=8 * 2**30,
                scientific_imports=0,
                numerical_runs=0,
            ),
        )
        baseline = make("baseline")
        for profile in ("event04", "event_mechanics03", "lifecycle02"):
            value = binding.bind(baseline, profile=profile)
            assert value["arrays"] == 1 and value["fixed_member_limit"] == 310689
            assert (
                value["typed_headers"]["a0"]["payload_sha256"]
                == hashlib.sha256(struct.pack("<d", -0.0)).hexdigest()
            )
            keep("profile_" + profile, arrays=1, negative_zero_bits_preserved=True)
        refuses(
            "catalog_profile_refused",
            lambda: binding.bind(baseline, profile="catalog05"),
            "non-catalog",
        )
        above = make("above_catalog_limit", count=32769)
        refuses("catalog32768_limit_preserved", lambda: old.bind(above), "Expanded archive bound")
        value = binding.bind(above, profile="event04")
        assert value["arrays"] == 32769 and value["numeric_scalars"] == 32769
        keep(
            "actual_above_catalog_limit_accepted",
            arrays=32769,
            archive_bytes=(above / "arrays.npz").stat().st_size,
        )
        # Pure metadata guard arithmetic, not a huge physical capture or a claim
        # that an archive at the theoretical ceiling can fit every byte guard.
        for count, expected in ((310688, True), (310689, True), (310690, False)):
            assert (count <= binding.core.MAX_MEMBERS) is expected
            assert (22 + count * 216 <= 64 * 2**20) is expected
            keep(
                "fixed_count_metadata_" + str(count),
                admitted_by_count_and_minimum_byte_predicate=expected,
                actual_archive_constructed=False,
            )
        compressed = make("compressed_producer", compression=zipfile.ZIP_DEFLATED)
        refuses(
            "unreviewed_compression_refused",
            lambda: binding.bind(compressed, profile="event04"),
            "uncompressed NPY",
        )
        opaque = make("opaque_dtype", dtype="|O8")
        refuses(
            "opaque_dtype_refusal_preserved",
            lambda: binding.bind(opaque, profile="event04"),
            "Plain numeric dtype required",
        )
        corrupted = make("corrupted_hash")
        (corrupted / "data.json").write_text("{}\n")
        refuses(
            "manifest_hash_refusal_preserved",
            lambda: binding.bind(corrupted, profile="event04"),
            "Typed archive hash mismatch",
        )
        assert old.MAX_MEMBERS == 32768 and binding.core.MAX_BYTES == old.MAX_BYTES == 64 * 2**20
        before = (
            BASE / "ecm-catalog-archive-cardinality-repair-20261031-01/archive_binding.py"
        ).read_bytes()
        after = (TOOLS / "archive_binding.py").read_bytes()
        assert after.replace(b"MAX_MEMBERS=310689", b"MAX_MEMBERS=32768", 1) == before
        keep("all_other_helper_bytes_and_guards_unchanged", entire_helper_inverse_bytes_exact=True)
        loaded = [n for n in sys.modules if n.split(".")[0] in DENIED]
        assert not loaded
        hwm = (
            int(
                next(
                    line.split()[1]
                    for line in Path("/proc/self/status").read_text().splitlines()
                    if line.startswith("VmHWM:")
                )
            )
            * 1024
        )
        result = dict(
            kind="cells.capture_capacity_bounded_metadata_controls@1",
            status="passed_stdlib_synthetic_metadata_only",
            checks=rows,
            unique_checks=len(rows),
            elapsed_seconds=time.monotonic() - started,
            VmHWM_bytes=hwm,
            no_scientific_imports_attempted_or_loaded=True,
            scientific_modules_loaded=loaded,
            scientific_imports=0,
            scientific_AST_executions=0,
            model_fixture_or_reference_evaluations=0,
            pytest_collection_runs=0,
            numerical_runs=0,
            new_or_retained_qualification_passes=0,
            actual_evolved_captures=0,
            cap_endpoint_controls_are_scalar_metadata_not_full_archives=True,
            every_existing_byte_type_hash_CRC_guard_retained_by_exact_source_inverse=True,
            files_sha256={
                str(p.relative_to(OUT)): sha(p) for p in sorted(OUT.rglob("*")) if p.is_file()
            },
        )
        write(OUT / "result.json", result)
        print(
            json.dumps(
                dict(
                    status=result["status"],
                    checks=len(rows),
                    elapsed_seconds=result["elapsed_seconds"],
                    VmHWM_bytes=hwm,
                    result_sha256=sha(OUT / "result.json"),
                )
            )
        )
    except BaseException as error:
        write(
            OUT / "failure.json",
            dict(
                type=type(error).__name__,
                message=str(error),
                traceback=traceback.format_exc(),
                completed_checks=rows,
                numerical_runs=0,
                preserve_all_synthetic_inputs=True,
                automatic_retry=False,
            ),
        )
        raise


if __name__ == "__main__":
    main()
