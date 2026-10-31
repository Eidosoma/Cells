"""Read complete future evidence with the original profile02 caps; stdlib only."""

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

from betse_normal_ecm_molecule_qualification_contract import read, require, sha, write


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
        any(case.find(tag) is not None for tag in ("failure", "error", "skipped")) for case in tests
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
            not any(name.split(".")[0] in blocked for name in modules),
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
                    r.compress_type == zipfile.ZIP_STORED and r.file_size >= 128
                    for r in archive.infolist()
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
        from qualification_typed_evidence import array_header

        with zipfile.ZipFile(path) as archive:
            data = archive.read(name)
        return data, array_header(data)

    def values(self, value):
        location = self.locations[self.key(value)]
        data, header = self.payload(*location)
        dtype = header["dtype"]
        endian, kind, size = dtype[0], dtype[1], int(dtype[2:])
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
                offset, stride = 0, 1
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
                    a == b
                    or isinstance(a, float)
                    and isinstance(b, float)
                    and math.isnan(a)
                    and math.isnan(b)
                    for a, b in pairs
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


def metric(row):
    require(
        row["fresh_conditional_reference"] is True
        and row["carried_reference_forms"] == 0
        and row["physical_global_conservation_credit"] is False,
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
                type(error) in (float, int) and math.isfinite(error) and 0 <= error <= limit,
                "Original error/resolution budget failed",
            )


def raw_molecule(case, outcome, saved, native, archives, *, transport, ion_ids):
    complete_outcome(outcome, status="unexpected_source_failure", stage="raw_molecule_dispatch")
    chain = outcome["available"]["exception_chain"]
    species = "X" if case.startswith("first_") else "Y"
    role = "molecules" if "general" in case else "grn"
    message = (
        "Network concentration of "
        + species
        + " in cells below zero! Your simulation has become unstable."
    )
    wrapped = "Native ECM material refused at source: " + message
    require(
        [r["type"] for r in chain]
        == ["DispatchRejected", "ECMTransportRejected", "BetseSimUnstableException"],
        "Original molecular refusal types required",
    )
    require(
        [r["message"] for r in chain] == [wrapped, wrapped, message],
        "Original molecular refusal messages required",
    )
    require(
        chain[1]["attributes"]["stage"] == "source" and chain[1]["attributes"]["trial"] is None,
        "Original material refusal stage required",
    )
    partial = outcome["available"]["partial"]
    archives.exact(partial, saved["partial"])
    archives.exact(chain[0]["attributes"]["partial"], partial)
    archives.exact(partial["parent"], saved["parent"])
    require(
        saved["parent"]["clock"]["call_index"] == 0, "Failure cannot publish an accepted successor"
    )
    require(
        partial["stage"] == "general_then_GRN"
        and partial["automatic_retry"] is False
        and partial["inner_partial"] is None,
        "Original failure boundary differs",
    )
    require(
        partial["root_cause"] == dict(type="ECMTransportRejected", message=wrapped),
        "Original wrapped source refusal differs",
    )
    require(
        native["status"] == "source_refused"
        and native["failure"]["type"] == "BetseSimUnstableException"
        and native["failure"]["message"] == message
        and native["failure"]["stage"] == "native_dispatch",
        "Native literal source refusal differs",
    )
    require(
        native["failure_capture"] and not native["capture_errors"],
        "Complete native partial required",
    )
    holder = partial["holder"]
    require(
        "trial" not in holder and "before_commit" not in holder,
        "No completed material trial allowed after raw refusal",
    )
    frames = holder["material_partial"]["frames"]
    require(
        frames
        and all(isinstance(r, list) and len(r) == 3 for r in frames)
        and frames[-1][0] == "supplied_late_flux"
        and all(r[0] != "ecm_grn_dispatch" for r in frames),
        "Complete original positional Frame prefix required",
    )
    available = partial["available"]
    require(not available["capture_errors"], "Incomplete owned partial capture")
    order = []
    reached = ["molecules"] if role == "molecules" else ["molecules", "grn"]
    for owner in reached:
        stages = (
            ["before_dispatch", "clear_run_loop"]
            + (["run_loop_transporters"] if transport and owner == "molecules" else [])
            + ["run_loop_modulators"]
            + (["run_loop"] if owner != role else [])
        )
        order.extend(dict(role=owner, stage=stage) for stage in stages)
    archives.exact(native["order"], order)
    archives.exact(available["source_order"], order)
    archives.exact(available["material"], native["returned"]["material"])
    owners = available["owners"]
    archives.exact(owners["shared"], native["returned"]["shared"])
    require(
        owners["publication_owner"]
        == (saved["parent"]["owners"]["publication_owner"] if role == "molecules" else "molecules"),
        "Wrong last writer after raw failure",
    )
    for owner in ("molecules", "grn"):
        item = owners["handlers"][owner]
        archives.exact(
            None if item is None else item["cache"], native["returned"]["handlers"][owner]
        )
    for owner in reached:
        trace = available["traces"][owner]
        for key in (
            "molecule_frames",
            "mover_frames",
            "rhs",
            "control_writes",
            "dispatch_stages",
            "channel_events",
            "channel_initializations",
        ):
            archives.exact(trace[key], native["traces"][owner][key])
        completed = [
            r["species"] for r in trace["molecule_frames"] if r["stage"] == "transport_after"
        ]
        require(
            completed == (["X", "Y"] if owner != role else [] if species == "X" else ["X"]),
            "Synchronized omission in molecular transport prefix",
        )
        if transport and owner == "molecules":
            archives.exact(
                trace["transporter_frames"], native["traces"][owner]["transporter_frames"]
            )
            require(
                [(r["stage"], r["name"]) for r in trace["transporter_frames"]]
                == [
                    (s, "general_Na_import")
                    for s in (
                        "before",
                        "flux",
                        "current",
                        "reactant_commit",
                        "product_commit",
                        "after",
                    )
                ],
                "Complete configured transporter prefix required",
            )
    failed = available["traces"][role]
    expected = [("molecule_intra", "X"), ("molecule_intra", "Y"), ("rhs_ready", None)] + [
        ("chemical_commit", ion) for ion in ion_ids
    ]
    if species == "Y":
        expected += [(s, "X") for s in ("chemical_commit", "transport_before", "transport_after")]
    expected += [("chemical_commit", species), ("transport_before", species)]
    require(
        [(r["stage"], r["species"]) for r in failed["molecule_frames"]] == expected,
        "Complete actual chemistry insertion-order prefix required",
    )
    mover = [r for r in failed["mover_frames"] if r["species"] == species]
    require(
        mover
        and mover[-1]["stage"] == "environment_mix"
        and all(r["stage"] != "return" for r in mover),
        "Original failing mover prefix required",
    )
    values = mover[-1]["fields"]["cX_cells"]
    numeric = archives.values(values) if isinstance(values, dict) else values
    require(any(v < 0 for v in numeric), "Actual negative source buffer required")


def evidence(inputs, family, group, target, cpu):
    row = inputs["rosters"][family][group]
    packet = inputs["packets"][family]["packet"]
    case = row["case"]
    base = Path(target) / "evidence" / ("normal-ecm-molecule-" + family)
    archives = Archives(packet, inputs["packets"][family]["capture_profile"])
    folders = {}
    for manifest in sorted(base.rglob("manifest.json")):
        folders[str(manifest.parent.relative_to(base))] = manifest.parent
        archives.validate(manifest.parent)
    require(folders, "Complete typed evidence is required")
    starts = (
        [
            json.loads(line)
            for line in (Path(target) / "subprocess-start.jsonl").read_text().splitlines()
        ]
        if (Path(target) / "subprocess-start.jsonl").exists()
        else []
    )
    finishes = (
        [
            json.loads(line)
            for line in (Path(target) / "subprocess-finish.jsonl").read_text().splitlines()
        ]
        if (Path(target) / "subprocess-finish.jsonl").exists()
        else []
    )
    require(
        len({r["child_id"] for r in starts}) == len(starts)
        and len({r["child_id"] for r in finishes}) == len(finishes),
        "Unique actual subprocess records required",
    )
    require(
        {r["child_id"] for r in starts} == {r["child_id"] for r in finishes},
        "Incomplete actual child subprocess outcomes",
    )
    by_id = {r["child_id"]: r for r in finishes}
    for item in starts:
        done = by_id[item["child_id"]]
        require(
            item["pid"] == done["pid"]
            and done["returncode"] == 0
            and item["cpu_affinity"] == [cpu]
            and type(item["start_ticks"]) is int,
            "Actual child command failed or identity incomplete",
        )
    scientific_children = {}
    for item in starts:
        command = item["command"]
        if (
            isinstance(command, list)
            and "-m" in command
            and command[command.index("-m") + 1].startswith(
                "validation.betse.betse_normal_ecm_molecule_"
            )
        ):
            require(
                Path(command[0]).resolve() == Path(inputs["interpreter"]["path"]),
                "Conditional child interpreter differs",
            )
            require("--output" in command, "Conditional child output association required")
            output = command[command.index("--output") + 1]
            require(output not in scientific_children, "Repeated actual conditional child output")
            scientific_children[output] = command[command.index("-m") + 1]

    @functools.lru_cache(maxsize=8)
    def need(name):
        require(name in folders, "Missing complete outcome/archive: " + name)
        return archives.load(folders[name])

    raw_folders = set(base.rglob("reference-refusal-*.json")) | set(base.rglob("*.failure.json"))
    require(
        not raw_folders, "A reference refused; raw evidence is retained with no accuracy credit"
    )
    forms = list(base.rglob("reference-1.json")) + list(base.rglob("reference-2.json"))
    require(len(forms) == row["independent_forms"], "Exact independent reference inventory differs")
    for path in forms:
        value = read(path)
        level = int(path.stem[-1])
        require(
            value["production_imports_denied"] is True
            and not value["loaded_production_modules"]
            and value["carried_reference_forms"] == 0
            and value["decimal_precision"] == (100 if level == 1 else 160),
            "Fresh independent form required",
        )
        runtime(value["runtime"], inputs, family, cpu, reference=True)
        require(
            scientific_children.pop(str(path), None)
            == "validation.betse.betse_normal_ecm_molecule_" + family + "_reference",
            "Actual reference subprocess association missing",
        )
        require(
            path.with_name("reference-" + str(3 - level) + ".json").is_file(),
            "Paired precision form required",
        )
        require(
            (path.parent / "comparison.json").is_file(),
            "Every independent pair requires its original comparison",
        )
    comparisons = list(base.rglob("comparison.json"))
    require(
        {p.parent for p in comparisons} == {p.parent for p in forms},
        "Exact comparison/reference folder inventory differs",
    )
    for path in comparisons:
        metric(read(path))
    natives = {name: None for name in folders if name.endswith("/native")}
    require(len(natives) == row["native_captures"], "Exact native capture inventory differs")
    for name in natives:
        value = need(name)
        natives[name] = (value["status"], value["capture_errors"])
        require(
            scientific_children.pop(str(base / name), None)
            == "validation.betse.betse_normal_ecm_molecule_" + family + "_native",
            "Actual native subprocess association missing",
        )
        require(
            value["production_imports_denied"] is True and not value["loaded_production_modules"],
            "Actual independent native capture required",
        )
        runtime(value["runtime"], inputs, family, cpu, native=True)
        before = need(name + "-raw-before-runtime")
        archives.exact(
            {
                k: v
                for k, v in value.items()
                if k not in {"runtime", "loaded_production_modules", "production_imports_denied"}
            },
            before,
        )
    require(not scientific_children, "Unexpected conditional subprocess outputs")
    category = row["category"]
    if category in ("positive", "component_control"):
        summary = need(case + "-summary")
        require(
            summary["completed_calls"] == 3
            and summary["fresh_reference_forms"] == row["independent_forms"]
            and summary["native_conditional_captures"] == 4
            and summary["independently_carried_trajectory"] is False
            and summary["global_conservation_credit"] is False,
            "Complete original positive summary required",
        )
        for index in range(3):
            need(case + "-accepted-" + str(index))
        require(
            all(status == "source_completed" and not errors for status, errors in natives.values()),
            "Native positive source completion required",
        )
    elif category == "raw":
        complete_outcome(
            need(case + "-baseline-outcome"),
            status="source_returned",
            stage="raw_baseline_initialize",
        )
        outcome = need(case + "-dispatch-outcome")
        saved = need(case + "-original-failure")
        actual_native = need(case + "-native-dispatch/native")
        declaration = need(case + "-inputs-before-setup")
        ids = declaration["field"]["definition"]["environment_geometry_definition"][
            "current_definition"
        ]["ions"]["ids"]
        raw_molecule(
            case,
            outcome,
            saved,
            actual_native,
            archives,
            transport=family == "transport",
            ion_ids=ids,
        )
    elif category == "raw_setup":
        outcome = need(case + "-setup-outcome")
        complete_outcome(
            outcome, status="unexpected_source_failure", stage="raw_transporter_initialize"
        )
        require(
            [r["type"] for r in outcome["available"]["exception_chain"]][-1] == "KeyError",
            "Original setup KeyError required",
        )
        saved = need(case + "-original-setup-partial")
        partial = outcome["available"]["partial"]
        archives.exact(saved["partial"], partial)
        require(
            partial["root_cause"]["type"] == "KeyError"
            and "max rate" in partial["root_cause"]["message"],
            "Original missing-rate setup refusal required",
        )
        native = need(case + "-native-setup/native")
        require(
            native["status"] == "source_refused"
            and native["failure"]["type"] == "KeyError"
            and native["failure_capture"],
            "Complete native setup partial required",
        )
        actual = partial["available"]["owners"]["handlers"]["molecules"]["cache"]
        archives.exact(actual, native["returned"]["handlers"]["molecules"])
        fields = actual["wire"]["transporter_fields"]
        require(
            len(fields) == int(case[-1]) + 1 and all(f["flux"] is None for f in fields.values()),
            "Complete partial transporter construction required",
        )
    else:
        require(category == "dependency", "Unknown separate roster category")
        if case in inputs["warm_dependencies"][family]:
            complete_outcome(
                need(case + "-baseline-outcome"),
                status="source_returned",
                stage="dependency_baseline_initialize",
            )
        require(not forms and not natives, "Dependency cases cannot inherit accuracy credit")
    return dict(
        complete=True,
        family=family,
        group=group,
        archives=len(folders),
        reference_forms=len(forms),
        native_captures=len(natives),
        new_outcomes_required=True,
        physical_global_conservation_credit=False,
        source_qualification_not_biological=True,
    )


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
        require(
            row["cpu_affinity"] == [cpu]
            and row["executable"] == inputs["interpreter"]["path"]
            and row["executable_sha256"] == inputs["interpreter"]["sha256"],
            "Actual pytest CPU/interpreter required",
        )
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
        and all(r["outcome"] == "passed" and r["wasxfail"] is False for r in reports),
        "Complete unskipped child test outcomes required",
    )
    runtime(finish["runtime"], inputs, family, cpu)
    process = read(target / "process/result.json")
    require(
        process["status"] == "completed"
        and process["returncode"] == 0
        and process["samples"] > 0
        and process["minimum_available_host_memory_bytes"] >= 8 * 2**30,
        "Actual resource-bounded child completion required",
    )
    limits = inputs["resources"][family]
    require(
        process["limits"]["max_process_tree_rss_bytes"] == limits["max_process_tree_rss_bytes"]
        and process["limits"]["min_available_host_memory_bytes"]
        == limits["min_available_host_memory_bytes"]
        and process["limits"]["max_wall_seconds"] == limits["max_scientific_command_seconds"],
        "Original process limits changed",
    )
    require(
        process["sampled_peak_process_tree_rss_bytes"] <= limits["max_process_tree_rss_bytes"]
        and process["observed_process_high_water_bytes"] <= limits["max_process_tree_rss_bytes"],
        "Actual process memory allowance exceeded",
    )
    return dict(node_ids=observed, evidence=evidence(inputs, family, group, target, cpu))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--family", choices=("dispatch", "transport"), required=True)
    parser.add_argument("--group", required=True)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--cpu", type=int, required=True)
    args = parser.parse_args()
    inputs = read(args.inputs)
    try:
        result = validate_child(inputs, args.family, args.group, args.target, args.cpu)
        require(
            not any(
                name.split(".")[0]
                in {"cells", "betse", "numpy", "scipy", "jax", "jaxlib", "pytest"}
                for name in sys.modules
            ),
            "Metadata reader imported scientific implementation",
        )
        write(
            args.target / "reader-result.json",
            dict(
                status="passed",
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
            ),
        )
        raise


if __name__ == "__main__":
    main()
