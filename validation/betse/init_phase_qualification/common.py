"""INIT runner metadata only; source02 remains held and immutable."""

import hashlib
import json
import math
import os
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
METADATA_LIMIT = 16 * 2**20
RAW_LIMIT = 64 * 2**20


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read(path, limit=METADATA_LIMIT):
    path = Path(path)
    require(
        path.is_file() and not path.is_symlink(),
        "Regular metadata required: " + str(path),
    )
    require(path.stat().st_size <= limit, "Metadata byte limit: " + str(path))

    def pairs(rows):
        out = {}
        for key, value in rows:
            require(key not in out, "Duplicate JSON key")
            out[key] = value
        return out

    def invalid(value):
        raise ValueError("Nonstandard JSON number: " + value)

    return json.loads(path.read_text(), object_pairs_hook=pairs, parse_constant=invalid)


def write(path, value, *, mutable=False):
    path = Path(path)
    require(
        not path.exists() or mutable and path.name == "status.json",
        "Existing evidence is immutable",
    )
    pending = path.with_name(path.name + ".pending")
    with pending.open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    pending.replace(path)


def utc():
    return datetime.now(timezone.utc).isoformat()


def memory():
    mem = next(
        int(line.split()[1]) * 1024
        for line in Path("/proc/meminfo").read_text().splitlines()
        if line.startswith("MemAvailable:")
    )
    process = {
        line.split(":", 1)[0]: int(line.split()[1]) * 1024
        for line in Path("/proc/self/status").read_text().splitlines()
        if line.startswith(("VmHWM:", "VmRSS:"))
    }
    return dict(available_host_bytes=mem, current_image=process)


def canonical(name):
    path = Path(name)
    require(
        type(name) is str
        and name
        and not path.is_absolute()
        and ".." not in path.parts
        and str(path) == name,
        "Canonical relative path required",
    )
    return path


def verify_files(root, files, *, exact=False):
    root = Path(root)
    for name, digest in files.items():
        path = root / canonical(name)
        require(
            re.fullmatch("[0-9a-f]{64}", digest) is not None
            and path.is_file()
            and not path.is_symlink()
            and sha(path) == digest,
            "Frozen file mismatch: " + str(path),
        )
    if exact:
        paths = list(root.rglob("*"))
        require(not any(p.is_symlink() for p in paths), "Linked frozen file")
        require(
            {str(p.relative_to(root)) for p in paths if p.is_file()} == set(files),
            "Exact frozen file roster",
        )


def exact_ids(path, expected):
    path = Path(path)
    require(
        path.is_file() and not path.is_symlink() and path.stat().st_size <= METADATA_LIMIT,
        "JUnit identity/bound",
    )
    root = ET.parse(path).getroot()
    cases = root.findall(".//testcase")
    ids = [c.attrib["classname"].replace(".", "/") + ".py::" + c.attrib["name"] for c in cases]
    require(
        len(ids) == len(set(ids)) and set(ids) == set(expected),
        "Exact unique JUnit IDs",
    )
    require(
        not any(list(root.iter(tag)) for tag in ("failure", "error", "skipped")),
        "Failed/skipped check is not passing credit",
    )
    return ids


def resource_receipt(row, seconds):
    require(
        row["status"] == "completed" and row["returncode"] == 0,
        "Resource refusal is not a pass",
    )
    expected = dict(
        process_tree_memory_metric="rss",
        max_process_tree_memory_bytes=2**30,
        max_individual_process_rss_bytes=2**30,
        min_available_host_memory_bytes=8 * 2**30,
        max_wall_seconds=seconds,
        sample_interval_seconds=0.25,
        max_process_tree_rss_bytes=2**30,
    )
    require(row["limits"] == expected, "Exact original resource envelope")
    for key in (
        "sampled_peak_process_tree_rss_bytes",
        "observed_process_high_water_bytes",
    ):
        require(row[key] <= 2**30, "Recorded RSS limit exceeded")
    require(
        row["elapsed_seconds"] <= seconds
        and row["minimum_available_host_memory_bytes"] >= 8 * 2**30,
        "Recorded wall/reserve limit exceeded",
    )


def verify_runtime(
    row,
    *,
    source_root,
    source_hashes,
    runner_root,
    runner_hashes,
    executable,
    executable_sha256,
    cpu,
    role,
    external_roots=(),
    extra_file_pins=None,
):
    require(row.get("measured_cpu_affinity") == [cpu], "Runtime affinity mismatch")
    declared_exe = row.get("executable", {})
    require(
        Path(declared_exe.get("path", "")).resolve() == Path(executable).resolve()
        and declared_exe.get("sha256") == executable_sha256
        and sha(executable) == executable_sha256,
        "Runtime executable mismatch",
    )
    require(
        type(row.get("loaded_files")) is dict
        and row["loaded_files"]
        and type(row.get("modules_without_files")) is list,
        "Incomplete runtime inventory",
    )
    source_root, runner_root = Path(source_root).resolve(), Path(runner_root).resolve()
    external_roots = [Path(p).resolve() for p in external_roots]
    extra_file_pins = {} if extra_file_pins is None else extra_file_pins
    denied = (
        {"cells", "betse", "numpy", "scipy", "jax", "jaxlib"}
        if role == "reference"
        else {"cells", "betse", "jax", "jaxlib"}
        if role == "native"
        else set()
    )
    module_names = set(row["loaded_files"]) | set(row["modules_without_files"])
    require(
        not any(name.split(".")[0] in denied for name in module_names),
        "Denied scientific runtime import",
    )
    scientific = 0
    for name, record in row["loaded_files"].items():
        require(
            not record.get("unavailable")
            and type(record.get("path")) is str
            and type(record.get("sha256")) is str,
            "Unavailable runtime file",
        )
        path = Path(record["path"]).resolve()
        require(
            path.is_file() and sha(path) == record["sha256"],
            "Runtime loaded bytes changed: " + str(path),
        )
        if path.is_relative_to(source_root):
            require(
                source_hashes.get(str(path.relative_to(source_root))) == record["sha256"],
                "Unpinned frozen runtime file",
            )
            scientific += 1
        elif path.is_relative_to(runner_root):
            require(
                runner_hashes.get(str(path.relative_to(runner_root))) == record["sha256"]
                or extra_file_pins.get(str(path)) == record["sha256"],
                "Unpinned runner runtime file",
            )
        else:
            require(
                name.split(".")[0] not in {"cells", "validation", "tests", "betse"},
                "Foreign scientific runtime origin",
            )
            require(
                extra_file_pins.get(str(path)) == record["sha256"]
                or any(path.is_relative_to(root) for root in external_roots),
                "Undeclared external runtime file origin",
            )
        if name.split(".")[0] in {"cells", "validation", "tests"}:
            require(
                path.is_relative_to(source_root),
                "Scientific module outside exact frozen source",
            )
    require(
        scientific > 0 or role in ("controller", "reader"),
        "Runtime omits the frozen scientific source",
    )
    namespaces = []
    for name in row["modules_without_files"]:
        if name.split(".")[0] in {"cells", "validation", "tests", "betse"}:
            directory = source_root.joinpath(*name.split("."))
            require(
                (
                    name.startswith("validation")
                    or (
                        role == "pytest"
                        and name == "tests.unit"
                        and row["loaded_files"].get("tests", {}).get("path")
                        == str(source_root / "tests/__init__.py")
                        and row["loaded_files"].get("tests", {}).get("sha256")
                        == source_hashes.get("tests/__init__.py")
                    )
                )
                and directory.is_dir()
                and not (directory / "__init__.py").exists()
                and any(n.startswith(name + ".") for n in row["loaded_files"]),
                "Unbound scientific module without a file: " + name,
            )
            namespaces.append(name)
    return dict(
        role=role,
        loaded_files=len(row["loaded_files"]),
        frozen_scientific_files=scientific,
        affinity=[cpu],
        executable_sha256=executable_sha256,
        fileless_namespace_packages=namespaces,
        namespace_binding=(
            "declared empty package directories plus all actual loaded descendant file origins"
        ),
    )


def finite_budget(value, limit):
    return type(value) in (int, float) and math.isfinite(value) and 0 <= value <= limit


def verify_release(root=HERE):
    root = Path(root)
    plan = read(root / "plan.json")
    require(
        plan.get("status") == "sealed_held" and plan.get("reference_successor_reviewed") is True,
        "Draft/source02 cannot be released",
    )
    seal = read(root / "seal.json")
    verify_files(root, seal["files"])
    for name, digest in plan["pins"].items():
        require(sha(name) == digest, "Reviewed prerequisite changed: " + name)
    require(
        sha(root / "source-resource-contract.json") == plan["source_resource_contract_sha256"]
        and sha(root / "expected-evidence.json") == plan["evidence_contract_sha256"],
        "Exact runner contracts",
    )
    release = read(root / "release.json")
    require(
        release.get("authorized") is True
        and release.get("requested_round") is True
        and release.get("cpu_coordinated") is True
        and release.get("source_and_runner_accepted_by_root") is True
        and release.get("cpu") == plan["cpu"]
        and release.get("plan_sha256") == sha(root / "plan.json")
        and release.get("seal_sha256") == sha(root / "seal.json")
        and type(release.get("authorization_note")) is str
        and release["authorization_note"].strip(),
        "Explicit matching Root release required",
    )
    require(not sys.flags.optimize, "Python assertions must remain enabled")
    return plan
