# ruff: noqa: C408
import argparse
import functools
import importlib
import json
import math
import os
import struct
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

if __package__:
    from .betse_normal_ecm_molecule_events_execution_contract import read, require, sha, write
else:
    from betse_normal_ecm_molecule_events_execution_contract import read, require, sha, write


def verify_pytest_ids(tests, expected):
    actual = [
        case.attrib["classname"].replace(".", "/") + ".py::" + case.attrib["name"] for case in tests
    ]
    if (
        len(expected) != len(set(expected))
        or len(actual) != len(set(actual))
        or set(actual) != set(expected)
    ):
        raise ValueError("Pytest IDs differ from the exact unique prepared set")
    if any(
        (
            any((case.find(tag) is not None for tag in ("failure", "error", "skipped")))
            for case in tests
        )
    ):
        raise ValueError("A prepared pytest check failed, errored or skipped")
    return actual


def runtime(row, inputs, family, cpu, *, reference=False, native=False):
    require(row["measured_cpu_affinity"] == [cpu], "Actual child affinity differs")
    require(row["executable"] == inputs["interpreter"], "Actual child interpreter differs")
    files = row["loaded_files"]
    require(files, "Actual loaded files required")
    packet = Path(inputs["packets"][family]["packet"]) / "source"
    source_pins = inputs["source_pins"][family]
    bundle = Path(inputs["bundle_destination"])
    modules = set(files) | set(row["modules_without_files"])
    blocked = {"cells", "betse", "jax", "jaxlib"} | ({"numpy", "scipy"} if reference else set())
    if reference or native:
        require(
            not any((name.split(".")[0] in blocked for name in modules)),
            "Forbidden actual child module",
        )
    for module, item in files.items():
        require(not item.get("unavailable"), "Unavailable loaded child file")
        path = Path(item["path"])
        if path.is_relative_to(packet):
            pin = source_pins.get(str(path.relative_to(packet)))
        elif path.is_relative_to(bundle):
            pin = inputs["runner_source_pins"].get(str(path.relative_to(bundle)))
        else:
            pin = inputs["library_pins"].get(str(path))
        require(
            pin is not None and item.get("sha256") == pin,
            "Unbound actual child file: " + module + " " + str(path),
        )
        require(sha(path) == pin, "Loaded file changed after child inventory")


class Archives:
    def __init__(self, packet, profile):
        sys.path.insert(0, str(Path(packet) / "tools"))
        self.binding = importlib.import_module("capture_binding")
        self.binding.verify_profile(profile)
        self.profile = profile
        self.records = {}
        self.locations = {}

    @staticmethod
    def key(value):
        return (value["dtype"], tuple(value["shape"]), value["fortran"], value["payload_sha256"])

    def _read(self, folder, *, decoded):
        folder = Path(folder)
        bound = self.binding.core.bind(folder, decoded=decoded)
        record, value = bound if decoded else (bound, None)
        with zipfile.ZipFile(folder / "arrays.npz") as archive:
            require(
                all(
                    (
                        r.compress_type == zipfile.ZIP_STORED and r.file_size >= 128
                        for r in archive.infolist()
                    )
                ),
                "Original uncompressed profile policy required",
            )
        compact = {
            key: record[key]
            for key in ("manifest_sha256", "files", "arrays", "numeric_scalars", "typed_nodes")
        }
        old = self.records.get(str(folder))
        require(old is None or old == compact, "Evidence changed between binding and consumption")
        self.records[str(folder)] = compact
        if decoded:
            for name, header in record["typed_headers"].items():
                self.locations[self.key(header)] = (folder / "arrays.npz", name + ".npy")
        return value

    def validate(self, folder):
        self._read(folder, decoded=False)

    def load(self, folder):
        return self._read(folder, decoded=True)

    @staticmethod
    @functools.lru_cache(maxsize=2)
    def payload(path, name):
        if __package__:
            from validation.geometry.qualification_typed_evidence import array_header
        else:
            from qualification_typed_evidence import array_header
        with zipfile.ZipFile(path) as archive:
            data = archive.read(name)
        return (data, array_header(data))

    def values(self, value):
        location = self.locations[self.key(value)]
        data, header = self.payload(*location)
        dtype = header["dtype"]
        endian, kind, size = (dtype[0], dtype[1], int(dtype[2:]))
        formats = {
            ("b", 1): "?",
            ("i", 1): "b",
            ("u", 1): "B",
            ("i", 2): "h",
            ("u", 2): "H",
            ("i", 4): "i",
            ("u", 4): "I",
            ("i", 8): "q",
            ("u", 8): "Q",
            ("f", 2): "e",
            ("f", 4): "f",
            ("f", 8): "d",
        }
        require((kind, size) in formats, "Supported numeric scalar decoder required")
        code = ("<" if endian == "|" else endian) + formats[kind, size]
        shape = header["shape"]
        for index in range(header["count"]):
            offset = index
            if header["fortran"] and len(shape) > 1:
                coordinates = []
                rest = index
                for length in reversed(shape):
                    coordinates.append(rest % length)
                    rest //= length
                offset, stride = (0, 1)
                for coordinate, length in zip(reversed(coordinates), shape, strict=True):
                    offset += coordinate * stride
                    stride *= length
            yield struct.unpack_from(code, data, header["offset"] + offset * size)[0]

    def exact(self, actual, expected):
        array_a = isinstance(actual, dict) and actual.get("__typed_array__") is True
        array_b = isinstance(expected, dict) and expected.get("__typed_array__") is True
        if array_a or array_b:
            if array_a and array_b:
                require(
                    actual["dtype"] == expected["dtype"] and actual["shape"] == expected["shape"],
                    "Exact numeric array dtype/shape changed",
                )
                if self.key(actual) == self.key(expected):
                    return
                pairs = zip(self.values(actual), self.values(expected), strict=True)
            else:
                array, scalar = (actual, expected) if array_a else (expected, actual)
                require(
                    array["shape"] == [] and type(scalar) in (float, int, bool),
                    "Array/scalar category differs",
                )
                pairs = [(next(self.values(array)), scalar)]
            require(
                all(
                    (
                        a == b
                        or (
                            isinstance(a, float)
                            and isinstance(b, float)
                            and math.isnan(a)
                            and math.isnan(b)
                        )
                        for a, b in pairs
                    )
                ),
                "Exact numeric buffers differ",
            )
        elif isinstance(expected, dict):
            require(
                isinstance(actual, dict) and set(actual) == set(expected),
                "Exact mapping fields differ",
            )
            for key in expected:
                self.exact(actual[key], expected[key])
        elif isinstance(expected, list):
            require(
                isinstance(actual, list) and len(actual) == len(expected),
                "Exact sequence fields differ",
            )
            for a, b in zip(actual, expected, strict=True):
                self.exact(a, b)
        else:
            require(actual == expected, "Exact scalar field differs")


def complete_outcome(value, *, status, stage):
    require(value["status"] == status, "Outcome status differs from actual expected result")
    if status == "source_returned":
        require(
            value["stage"] == stage
            and "returned" in value
            and isinstance(value["available"], dict),
            "Complete returned outcome required",
        )
    else:
        require(
            value["failure"]["stage"] == stage and value["failure"]["traceback"],
            "Original stage/traceback required",
        )
        require(not value["capture_errors"], "Incomplete outcome reader capture")
        require(
            set(value["available"]) >= {"partial", "exception_chain"},
            "Complete original partial/cause chain required",
        )
        require(value["available"]["exception_chain"], "Missing original cause chain")


def conditional_child(item, inputs, family, output, kind, *, refinement=None):
    require(item is not None, "Actual conditional subprocess association missing")
    command = item["command"]
    output = Path(output)
    source = output.parent / "inputs.json"
    module = "validation.betse.betse_normal_ecm_molecule_" + family + "_" + kind
    expected = ["-B", "-m", module, "--inputs", str(source), "--output", str(output)]
    if refinement is not None:
        expected += ["--refinement", str(refinement)]
    require(
        Path(command[0]).resolve() == Path(inputs["interpreter"]["path"])
        and command[1:] == expected,
        "Actual conditional command/input/refinement differs",
    )
    require(
        item["input_record"] == dict(path=str(source.resolve()), sha256=sha(source)),
        "Actual conditional input hash differs",
    )
    return read(source)


def metric(row):
    require(
        row["fresh_conditional_reference"] is True
        and row["carried_reference_forms"] == 0
        and (row["physical_global_conservation_credit"] is False),
        "Original conditional comparison contract required",
    )
    require(
        row["fields"] and set(row["fields"]) == set(row["resolutions"]),
        "Complete paired metrics required",
    )
    for key, limit in (("fields", 1.0), ("resolutions", 0.1)):
        for value in row[key].values():
            error = value["normalized_max_error"]
            require(
                type(error) in (float, int) and math.isfinite(error) and (0 <= error <= limit),
                "Original error/resolution budget failed",
            )


def pytest_identity(row, inputs, cpu):
    require(
        row["cpu_affinity"] == [cpu]
        and row["executable"] == inputs["interpreter"]["path"]
        and (row["executable_sha256"] == inputs["interpreter"]["sha256"]),
        "Actual pytest CPU/interpreter required",
    )
    require(row.get("optimize") == 0, "Actual pytest assertions must be enabled")


def validate_child(inputs, family, group, target, cpu):
    target = Path(target)
    expected = inputs["rosters"][family][group]["node_ids"]
    observed = verify_pytest_ids(
        ET.parse(target / "tests.xml").getroot().findall(".//testcase"), expected
    )
    start, finish = (read(target / name) for name in ("pytest-start.json", "pytest-finish.json"))
    launched = read(target / "process/process-started.json")
    require(
        start["pid"] == finish["pid"] == launched["pid"]
        and start["start_ticks"] == finish["start_ticks"],
        "Actual pytest child identity differs",
    )
    require(
        finish["exitstatus"] == 0 and finish["testscollected"] == len(expected),
        "Actual pytest completion required",
    )
    for row in (start, finish):
        pytest_identity(row, inputs, cpu)
    reports = finish["reports"]
    require(
        reports
        == [
            json.loads(line) for line in (target / "pytest-reports.jsonl").read_text().splitlines()
        ],
        "Durable child report stream differs",
    )
    require(
        len(reports) == 3 * len(expected)
        and {(r["nodeid"], r["when"]) for r in reports}
        == {(n, phase) for n in expected for phase in ("setup", "call", "teardown")}
        and all((r["outcome"] == "passed" and r["wasxfail"] is False for r in reports)),
        "Complete unskipped child test outcomes required",
    )
    runtime(finish["runtime"], inputs, family, cpu)
    process = read(target / "process/result.json")
    require(
        process["status"] == "completed"
        and process["returncode"] == 0
        and (process["samples"] > 0)
        and (process["minimum_available_host_memory_bytes"] >= 8 * 2**30),
        "Actual resource-bounded child completion required",
    )
    limits = inputs["resources"][family]
    require(
        process["limits"]["max_process_tree_rss_bytes"] == limits["max_process_tree_rss_bytes"]
        and process["limits"]["min_available_host_memory_bytes"]
        == limits["min_available_host_memory_bytes"]
        and (process["limits"]["max_wall_seconds"] == limits["max_scientific_command_seconds"]),
        "Original process limits changed",
    )
    require(
        process["sampled_peak_process_tree_rss_bytes"] <= limits["max_process_tree_rss_bytes"]
        and process["observed_process_high_water_bytes"] <= limits["max_process_tree_rss_bytes"],
        "Actual process memory allowance exceeded",
    )
    return dict(node_ids=observed, evidence=evidence(inputs, family, group, target, cpu))


def evidence(inputs, family, group, target, cpu):
    if __package__:
        from .betse_normal_ecm_molecule_events_execution_evidence import evidence as consume
    else:
        from betse_normal_ecm_molecule_events_execution_evidence import evidence as consume
    return consume(inputs, family, group, target, cpu, sys.modules[__name__])


def main():
    import resource

    if __package__:
        from .betse_normal_ecm_molecule_events_execution_contract import (
            output_location,
            verify_bundle,
            verify_packet,
        )
    else:
        from betse_normal_ecm_molecule_events_execution_contract import (
            output_location,
            verify_bundle,
            verify_packet,
        )
    if __package__:
        from .betse_normal_ecm_molecule_events_execution_resources import memory_available
    else:
        from betse_normal_ecm_molecule_events_execution_resources import memory_available
    resource.setrlimit(resource.RLIMIT_AS, (512 * 2**20,) * 2)
    require(memory_available() >= 8 * 2**30, "Reader host reserve unavailable")
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--family", choices=("events",), required=True)
    parser.add_argument("--group", required=True)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--cpu", type=int, required=True)
    args = parser.parse_args()
    bundle = Path(__file__).resolve().parent
    inputs = verify_bundle(bundle)
    require(args.inputs.resolve() == bundle / "inputs.json", "Exact frozen inputs required")
    require(os.sched_getaffinity(0) == {args.cpu}, "Actual coordinated reader CPU required")
    require(args.group in inputs["rosters"][args.family], "Exact prepared events57 group required")
    source = verify_packet(inputs["packets"][args.family])
    require(
        source["source_sha256"] == inputs["source_pins"][args.family],
        "Reader source/profile association differs",
    )
    output_location(bundle, inputs, args.target)
    require(
        args.target.is_dir() and (not args.target.is_symlink()),
        "Existing saved evidence output required",
    )
    try:
        result = validate_child(inputs, args.family, args.group, args.target, args.cpu)
        denied = [
            n
            for n in sys.modules
            if n.split(".")[0] in {"cells", "betse", "numpy", "scipy", "jax", "jaxlib", "pytest"}
        ]
        require(not denied, "Metadata reader imported a scientific implementation")
        write(
            args.target / "reader-result.json",
            dict(
                status="passed",
                scope="saved_evidence_semantic_validation_only",
                execution_hold=True,
                scientific_release_authorized=False,
                reader_identity=dict(
                    pid=os.getpid(),
                    cpu_affinity=sorted(os.sched_getaffinity(0)),
                    scientific_imports=[],
                ),
                **result,
            ),
        )
    except BaseException as error:
        import traceback

        write(
            args.target / "reader-failure.json",
            dict(
                status="failed",
                type=type(error).__name__,
                message=str(error),
                traceback=traceback.format_exc(),
                preserve_raw=True,
                no_accuracy_credit=True,
            ),
        )
        raise


if __name__ == "__main__":
    main()
