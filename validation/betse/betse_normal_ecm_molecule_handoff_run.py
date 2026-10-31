"""Prepare and run three held Cells continuity targets from a Git snapshot.

Preparation imports no scientific modules. Root supplies the release flag and
resource plan. Each pytest child has one exact target; skips/xfails, incomplete
evidence and unbound runtime/source files never become a successful delivery.
"""

import argparse
import json
import os
import sys
import sysconfig
import traceback
import zipfile
from collections import Counter
from importlib import metadata
from pathlib import Path

from validation import source_snapshot as snapshot
from validation.betse import betse_normal_ecm_molecule_handoff as handoff
from validation.betse.betse_normal_ecm_molecule_qualification_resources import run_bounded
from validation.geometry.qualification_typed_evidence import array_header, read_json, require

PREFIX = "validation.betse.betse_normal_ecm_molecule_handoff_run"
OWNED = (
    "validation/betse/betse_normal_ecm_molecule_handoff_run.py",
    "validation/betse/betse_normal_ecm_molecule_handoff_run_plugin.py",
    "tests/unit/test_betse_normal_ecm_molecule_handoff_run.py",
)
READERS = (
    "validation/geometry/qualification_typed_evidence.py",
    "validation/betse/betse_normal_channel_join_runtime.py",
)
BASE = "tests/unit/test_betse_normal_ecm_molecule_handoff.py::"
TARGETS = {
    "zero_INIT_calls": BASE
    + "test_actual_retained_handoff_and_checkpoint_continuation[zero_INIT_calls]",
    "one_INIT_call": BASE
    + "test_actual_retained_handoff_and_checkpoint_continuation[one_INIT_call]",
    "SIM_associations": (
        "tests/unit/test_betse_normal_ecm_molecule_checkpoint.py::"
        "test_actual_SIM_transition_and_both_phase_associations_roundtrip"
    ),
}
SCENARIOS = {
    "zero_INIT_calls": dict(INIT_setup_entries=1, INIT_advance_requests=0, SIM_branches=2),
    "one_INIT_call": dict(INIT_setup_entries=1, INIT_advance_requests=1, SIM_branches=2),
    # The existing module-scoped fixture creates both entries, even though
    # this target transitions only its zero-call entry. Do not omit that work.
    "SIM_associations": dict(INIT_setup_entries=2, INIT_advance_requests=0, SIM_branches=0),
}
PACKET_KIND = "cells.retained_molecule_continuity_run@1"
CHECKPOINT_KIND = "cells.ordinary_ecm_molecule_headless_checkpoint@1"


def ref(path):
    path = Path(path).resolve(strict=True)
    return dict(path=str(path), sha256=snapshot.digest(path))


def pinned(row):
    path = Path(row["path"])
    require(path.is_file() and not path.is_symlink(), "Regular pinned input required")
    require(snapshot.digest(path) == row["sha256"], "Changed pinned input: " + str(path))
    return path


def runtime_pins(producer):
    """Reuse checkpoint runtime pins and bind pytest plus the local stdlib."""
    files = dict(producer["runtime_code_sha256"])
    for package in ("pytest", "pluggy", "pygments", "iniconfig", "packaging"):
        distribution = metadata.distribution(package)
        require(distribution.files is not None, "Missing pytest runtime inventory")
        for member in distribution.files:
            if str(member).endswith((".py", ".so")):
                path = Path(distribution.locate_file(member)).resolve(strict=True)
                files[str(path)] = snapshot.digest(path)
    stdlib = Path(sysconfig.get_path("stdlib")).resolve(strict=True)
    for path in stdlib.rglob("*"):
        if (
            path.is_file()
            and path.suffix in {".py", ".so"}
            and not {"site-packages", "dist-packages", "__pycache__"}.intersection(path.parts)
        ):
            files[str(path.resolve())] = snapshot.digest(path)
    for name, value in files.items():
        require(snapshot.digest(Path(name)) == value, "Checkpoint runtime changed: " + name)
    return files


def prepare(repository, directory, *, reviewed_result, reviewed_sha256, review, review_sha256):
    """Select prior reviewed paths, but copy every source byte from Git only."""
    repository, directory = Path(repository).resolve(strict=True), Path(directory).absolute()
    require(snapshot.digest(Path(reviewed_result)) == reviewed_sha256, "Changed reviewed result")
    require(snapshot.digest(Path(review)) == review_sha256, "Changed Root software review")
    previous = read_json(reviewed_result)
    require(read_json(review)["result"] == ref(reviewed_result), "Root review names another result")
    require(previous["validation"]["passed"] == 34, "Final typed guard result required")
    require(previous["scientific_acceptance"] is False, "Continuity is still a held claim")
    selection_path = pinned(previous["source_snapshot"])
    selection = snapshot.verify(
        selection_path.parent, manifest_sha256=previous["source_snapshot"]["sha256"]
    )
    files = {name: row["checkout_path"] for name, row in selection["files"].items()}
    require(all(name == source for name, source in files.items()), "No historical source overlay")
    files.update({name: name for name in (*OWNED, *READERS)})
    # These factories and assertions are the existing targets, not successors.
    frozen = {
        name: row["sha256"]
        for name, row in selection["files"].items()
        if name.endswith("_fixtures.py")
        or name in {node.split("::")[0] for node in TARGETS.values()}
    }
    for name, value in frozen.items():
        require(
            snapshot.digest(repository / name) == value, "Changed original fixture/target: " + name
        )
    diagnosis = read_json(pinned(previous["saved_correspondence"]["comparison"]))
    transition = Path(diagnosis["source_artifacts"]["actual-INIT-to-SIM"]["path"]).parent
    original = handoff.compare_saved(transition)
    require(original["source_artifacts"] == diagnosis["source_artifacts"], "Changed failed parents")
    producer = read_json(pinned(previous["producer"]))
    libraries = runtime_pins(producer)
    directory.mkdir(parents=True, exist_ok=False)
    try:
        source = directory / "source"
        manifest = snapshot.freeze(repository, source, files)
        for name, value in frozen.items():
            require(manifest["files"][name]["sha256"] == value, "Fixture changed during freeze")
        expected_producer = dict(producer)
        expected_producer["source_hashes"] = {
            name: manifest["files"]["src/cells/" + name]["sha256"]
            for name in producer["source_hashes"]
        }
        inputs = dict(
            kind=PACKET_KIND,
            status="held_for_Root_release_and_resource_plan",
            snapshot=ref(source / "SNAPSHOT.json"),
            source_selection_only=ref(selection_path),
            original_typed_result=ref(reviewed_result),
            Root_software_review=ref(review),
            targets=TARGETS,
            scenarios=SCENARIOS,
            original_fixtures_and_assertions=frozen,
            original_failed_archives=original["source_artifacts"],
            original_parent_identities=original["identities"],
            expected_checkpoint_producer=expected_producer,
            runtime_files=libraries,
            interpreter=producer["executable"],
            release_env=handoff.RELEASE_ENV,
            independent_biological_cases=0,
            native_source_equivalence=False,
            scientific_acceptance=False,
            accounting=(
                "All observed boundary invocations, including verification, RNG and "
                "nested checkpoint work; no credit for duplicate entry/setup"
            ),
        )
        snapshot.write_json(directory / "inputs.json", inputs)
        snapshot.write_json(
            directory / "root-request-template.json",
            dict(
                packet_sha256=snapshot.digest(directory / "inputs.json"),
                cpu=None,
                timeout_seconds=None,
                max_rss_bytes=None,
                min_available_bytes=None,
            ),
        )
        return inputs
    except BaseException as error:
        retain_failure(directory, error, stage="prepare")
        raise


def verify_packet(directory, sha256):
    directory = Path(directory).resolve(strict=True)
    path = directory / "inputs.json"
    require(snapshot.digest(path) == sha256, "Changed held run inputs")
    inputs = read_json(path)
    require(
        inputs["kind"] == PACKET_KIND and inputs["targets"] == TARGETS,
        "Exact three targets required",
    )
    require(inputs["scenarios"] == SCENARIOS, "Changed scenario accounting")
    snapshot.verify(directory / "source", manifest_sha256=inputs["snapshot"]["sha256"])
    require(pinned(inputs["snapshot"]) == directory / "source/SNAPSHOT.json", "Foreign snapshot")
    for row in inputs["original_failed_archives"].values():
        require(handoff._archive(Path(row["path"])) == row, "Original failed input/parent changed")
    for row in (inputs["original_typed_result"], inputs["Root_software_review"]):
        pinned(row)
    for name, value in inputs["runtime_files"].items():
        require(snapshot.digest(Path(name)) == value, "Changed runtime dependency: " + name)
    require(ref(sys.executable) == inputs["interpreter"], "Different Python executable")
    return inputs


def released_request(inputs, request):
    require(os.environ.get(handoff.RELEASE_ENV) == "1", "Held: existing Root release required")
    require(__debug__ and sys.flags.optimize == 0, "Assertion-enabled interpreter required")
    require(
        set(request)
        == {"packet_sha256", "cpu", "timeout_seconds", "max_rss_bytes", "min_available_bytes"},
        "Explicit Root resource plan required",
    )
    require(type(request["cpu"]) is int and request["cpu"] >= 0, "Root must select a CPU")
    for name in ("timeout_seconds", "max_rss_bytes", "min_available_bytes"):
        require(type(request[name]) is int and request[name] > 0, "Root must supply " + name)
    require(request["min_available_bytes"] >= 8 * 2**30, "Preserve the 8 GiB host reserve")
    require(inputs["release_env"] == handoff.RELEASE_ENV, "Changed release gate")


def child_environment(source, target):
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("CELLS_", "PYTEST_", "JAX_", "XLA_"))
        and key not in {"PYTHONPATH", "PYTHONHOME", "CUDA_VISIBLE_DEVICES"}
    }
    env.update(
        PYTHONPATH=str(source / "src") + os.pathsep + str(source),
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONOPTIMIZE="0",
        PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
        OMP_NUM_THREADS="1",
        OPENBLAS_NUM_THREADS="1",
        MKL_NUM_THREADS="1",
        NUMEXPR_NUM_THREADS="1",
        BLIS_NUM_THREADS="1",
        VECLIB_MAXIMUM_THREADS="1",
        CUDA_VISIBLE_DEVICES="",
        JAX_PLATFORMS="cpu",
        MALLOC_ARENA_MAX="2",
        TMPDIR=str(target / "tmp"),
        XDG_CACHE_HOME=str(target / "cache"),
        CELLS_MOLECULE_HANDOFF_RUN=str(target),
        CELLS_CHECKPOINT_TEST_EVIDENCE=str(target),
        CELLS_ECM_MOLECULE_RUN_LIFECYCLE_RELEASED="1",
    )
    return env


def command(source, target, node):
    require(node in TARGETS.values(), "Exactly one existing target required")
    return [
        sys.executable,
        "-B",
        "-m",
        "pytest",
        "-c",
        str(source / "pyproject.toml"),
        "--noconftest",
        "-p",
        "no:cacheprovider",
        "-p",
        PREFIX + "_plugin",
        "--import-mode=importlib",
        "-q",
        node,
        "--basetemp",
        str(target / "tmp/pytest"),
        "--junitxml",
        str(target / "tests.xml"),
    ]


def bind_archive(folder):
    """Reuse raw manifest/NPY readers; hydrate no executable owner or cache."""
    row = handoff._archive(folder)
    with zipfile.ZipFile(folder / "arrays.npz") as archive:
        members = archive.infolist()
        require(
            len(members) <= 100000 and len({m.filename for m in members}) == len(members),
            "Unique bounded arrays required",
        )
        require(
            sum(m.file_size for m in members) <= handoff.MAX_EVIDENCE_BYTES, "Expanded array bound"
        )
        arrays = {}
        for member in members:
            require(
                member.compress_type == zipfile.ZIP_STORED and not member.is_dir(),
                "Original uncompressed raw arrays required",
            )
            require(
                member.filename.startswith("a")
                and member.filename[1:-4].isdigit()
                and member.filename.endswith(".npy"),
                "Raw array identity required",
            )
            arrays[member.filename[:-4]] = array_header(archive.read(member))
    stack = [handoff._json(folder / "data.json", handoff.MAX_EVIDENCE_BYTES)]
    used, nodes = set(), 0
    while stack:
        node = stack.pop()
        nodes += 1
        require(nodes <= 3000000, "Raw node bound")
        if node is None or type(node) in (str, int, bool):
            continue
        require(type(node) is dict, "Raw typed node required")
        if set(node) == {"mapping"}:
            pairs = node["mapping"]
            require(
                type(pairs) is list
                and all(type(p) is list and len(p) == 2 and type(p[0]) is str for p in pairs),
                "Raw mapping rows",
            )
            require(len({p[0] for p in pairs}) == len(pairs), "Unique raw mapping keys")
            stack.extend(p[1] for p in pairs)
        elif set(node) == {"sequence"}:
            require(type(node["sequence"]) is list, "Raw sequence")
            stack.extend(node["sequence"])
        elif set(node) == {"float64_bits"}:
            require(
                type(node["float64_bits"]) is str and len(bytes.fromhex(node["float64_bits"])) == 8,
                "Raw float bits",
            )
        else:
            require(
                set(node) == {"array", "dtype", "shape"} and node["array"] in arrays,
                "Bound raw array reference",
            )
            header = arrays[node["array"]]
            require(
                node["array"] not in used
                and node["dtype"] == header["dtype"]
                and node["shape"] == list(header["shape"]),
                "Raw array descriptor/ownership differs",
            )
            used.add(node["array"])
    require(used == set(arrays), "No orphan raw array payload")
    return row | dict(arrays=len(arrays), typed_nodes=nodes, scalar_0D_identity_claim=False)


def bind_calls(path, accounting):
    """Reconcile every durable major entry/exit with its aggregate counts."""
    require(
        path.is_file() and not path.is_symlink() and path.stat().st_size <= 96 * 2**20,
        "Bounded invocation journal required",
    )
    counts, phases, active, entries = Counter(), Counter(), {}, 0
    with path.open() as stream:
        for index, line in enumerate(stream):
            require(index < 1000000 and len(line) <= 2**20, "Invocation journal bound")
            row = json.loads(line)
            if row["event"] == "entry":
                entries += 1
                require(
                    row["invocation"] == entries and row["invocation"] not in active,
                    "Unique ordered invocation identities required",
                )
                require(
                    row["parent_invocation"] is None or row["parent_invocation"] in active,
                    "Nested invocation must name its active actual parent",
                )
                active[entries] = row
                counts[row["function"]] += 1
                if row["phase"] is not None:
                    require(row["phase"] in {"INIT", "SIM"}, "Explicit actual source phase")
                    phases[row["function"] + ":" + row["phase"]] += 1
            elif row["event"] == "exit":
                require(
                    row["invocation"] in active
                    and row["exit_event"] in {"return", "c_return", "c_exception"},
                    "Complete actual invocation exit required",
                )
                del active[row["invocation"]]
            else:
                require(row["event"] == "pytest_report", "Known invocation journal event")
    require(
        not active and entries == accounting["durable_major_entries"],
        "Incomplete/truncated invocation journal",
    )
    from validation.betse.betse_normal_ecm_molecule_handoff_run_plugin import Calls

    major = {
        name: count
        for name, count in accounting["counts"].items()
        if Calls.category(*name.rsplit(".", 1)) not in {None, "other_Cells_callable"}
    }
    require(dict(counts) == major, "Observed durable entry counts differ from final aggregate")
    require(dict(phases) == accounting["phase_counts"], "Observed phase counts differ")
    return dict(**ref(path), durable_major_entries=entries, observed_counts=dict(counts))


def bind_process(target, identity):
    """Use the existing supervisor's saved samples, with no live job queries."""
    process = target / "process"
    start, done = read_json(process / "process-started.json"), read_json(process / "result.json")
    require(
        start["pid"] == identity["pid"]
        and done["status"] == "completed"
        and done["returncode"] == 0,
        "Actual supervised pytest PID/terminal result differs",
    )
    observed = False
    path = process / "host-resources.jsonl"
    require(
        path.is_file() and not path.is_symlink() and path.stat().st_size <= 96 * 2**20,
        "Bounded saved supervisor samples required",
    )
    with path.open() as stream:
        for index, line in enumerate(stream):
            require(index < 1000000 and len(line) <= 2**20, "Supervisor sample bound")
            for row in json.loads(line)["processes"]:
                require(
                    row["pid"] == identity["pid"] and row["start_ticks"] == identity["start_ticks"],
                    "Actual child start-time differs or extra subprocess observed",
                )
                observed = True
    require(observed, "Actual pytest PID/start-time must have been observed")
    return dict(
        start=ref(process / "process-started.json"),
        terminal=ref(process / "result.json"),
        samples=ref(path),
    )


def read_target(target, inputs, *, label, cpu):
    """Bind saved outcomes; test assertions are conditional, not native parity."""
    start, finish = (
        read_json(target / "pytest-start.json"),
        read_json(target / "pytest-finish.json"),
    )
    require(
        start["pid"] == finish["pid"] and start["start_ticks"] == finish["start_ticks"],
        "Actual child identity differs",
    )
    require(
        finish["exitstatus"] == 0 and finish["collected"] == [TARGETS[label]],
        "Exact target must finish",
    )
    reports = finish["reports"]
    require(
        [r["when"] for r in reports] == ["setup", "call", "teardown"],
        "Complete single-target pytest phases required",
    )
    require(
        all(
            r["nodeid"] == TARGETS[label] and r["outcome"] == "passed" and not r["wasxfail"]
            for r in reports
        ),
        "No skip/xfail/failure qualification",
    )
    process = bind_process(target, start)
    require(finish["runtime"]["measured_cpu_affinity"] == [cpu], "Child CPU differs")
    require(finish["runtime"]["executable"] == inputs["interpreter"], "Child interpreter differs")
    require(finish["producer"] == inputs["expected_checkpoint_producer"], "Child producer differs")
    source = Path(inputs["snapshot"]["path"]).parent
    manifest = read_json(source / "SNAPSHOT.json")
    require(finish["runtime"]["loaded_files"], "Actual loaded runtime inventory required")
    for module, row in finish["runtime"]["loaded_files"].items():
        require(not row.get("unavailable"), "Unavailable actual runtime file")
        path = Path(row["path"])
        expected = (
            manifest["files"].get(str(path.relative_to(source)), {}).get("sha256")
            if path.is_relative_to(source)
            else inputs["runtime_files"].get(str(path))
        )
        require(
            expected is not None and expected == row["sha256"] == snapshot.digest(path),
            "Unbound loaded module: " + module,
        )
    require(not finish["forbidden_entries"], "Native/reference or subprocess entry attempted")
    require(
        finish["accounting"]["profile_intact"] and finish["accounting"]["active_invocations"] == 0,
        "Complete invocation accounting required",
    )
    journal = bind_calls(target / "invocations.jsonl", finish["accounting"])
    counts = finish["accounting"]["counts"]
    phase_counts = finish["accounting"]["phase_counts"]
    module = "cells.processes.betse_normal_ecm_molecule_"
    expected = SCENARIOS[label]
    require(
        counts.get(module + "lifecycle_phase.initialize") == expected["INIT_setup_entries"],
        "Count all original INIT setup entries, including unused fixture entries",
    )
    require(
        phase_counts.get(module + "lifecycle_phase.advance:INIT", 0)
        == expected["INIT_advance_requests"],
        "Original INIT source-call count differs",
    )
    sim_calls = 0 if label == "SIM_associations" else 3
    require(
        phase_counts.get(module + "lifecycle_phase.advance:SIM", 0) == sim_calls,
        "Count the prefix and both actual SIM continuation branches separately",
    )
    for name in ("save_checkpoint", "load_checkpoint"):
        require(
            counts.get(module + "checkpoint." + name) == 1, "Exactly one real checkpoint " + name
        )
    require(
        counts.get(module + "checkpoint._verify") == 2,
        "Both nested checkpoint ownership checks required",
    )
    require(
        counts.get(module + "lifecycle.check_owners", 0) >= 1,
        "Actual retained owner guard not reached",
    )
    require(
        counts.get(module + "run_lifecycle.verify", 0) >= 2,
        "Actual ownership verification required",
    )
    require(
        any(
            name.startswith(("numpy.random.", "random.")) and value > 0
            for name, value in counts.items()
        ),
        "Actual RNG boundary observations required; no inferred zero RNG work",
    )
    raw, checkpoints = [], []
    for path in sorted((target / "tmp/pytest").rglob("manifest.json")):
        value = read_json(path)
        if value.get("kind") == CHECKPOINT_KIND:
            require(
                value["complete"] is True and value["phase"] == "SIM",
                "Complete SIM checkpoint required",
            )
            require(value["producer"] == finish["producer"], "Checkpoint producer differs")
            require(
                set(value["files"])
                == {"state.json", "arrays.npz", "operation.json", "request.json"},
                "Complete checkpoint files required",
            )
            for name, pin in value["files"].items():
                require(snapshot.digest(path.parent / name) == pin, "Changed checkpoint payload")
            checkpoints.append(ref(path))
        else:
            raw.append(bind_archive(path.parent))
    require(raw and len(checkpoints) == 1, "Actual raw outcomes and one saved checkpoint required")
    bound_raw = {Path(row["path"]) for row in raw}
    for path in (target / "tmp/pytest").rglob("data.json"):
        require(path.parent in bound_raw, "Uncommitted/orphan raw payload refused")
    files = {
        str(p.relative_to(target)): snapshot.digest(p)
        for p in target.rglob("*")
        if p.is_file() and "reader-process" not in p.relative_to(target).parts
    }
    require(
        not any(p.is_symlink() for p in target.rglob("*")), "Unlinked execution evidence required"
    )
    return dict(
        target=TARGETS[label],
        scenario=SCENARIOS[label],
        status="conditional_target_returned",
        raw_archives=raw,
        checkpoints=checkpoints,
        invocation_accounting=finish["accounting"],
        invocation_journal=journal,
        process=process,
        files=files,
        independent_biological_cases=0,
        native_source_equivalence=False,
        scientific_acceptance=False,
    )


def retain_failure(directory, error, *, stage):
    """Best effort only: a secondary evidence failure must not mask the cause."""
    try:
        snapshot.write_json(
            Path(directory) / "failure.json",
            dict(
                stage=stage,
                type=type(error).__name__,
                message=str(error),
                traceback="".join(traceback.format_exception(error)),
                scientific_acceptance=False,
            ),
        )
    except BaseException as secondary:
        error.add_note("Failure record also refused: " + repr(secondary))


def worker(packet, output, request):
    # Check the existing gate before I/O, source imports, process launch or setup.
    require(os.environ.get(handoff.RELEASE_ENV) == "1", "Held: existing Root release required")
    output = Path(output).absolute()
    output.mkdir(parents=True, exist_ok=False)
    stage, completed = "preflight", {}
    try:
        packet = Path(packet).resolve(strict=True)
        inputs = verify_packet(packet, request["packet_sha256"])
        released_request(inputs, request)
        source = packet / "source"
        require(
            not output.resolve().is_relative_to(packet),
            "Output must be separate from the held packet",
        )
        require(
            Path(__file__).resolve() == source / OWNED[0], "Execute the immutable snapshot runner"
        )
        stage = "request"
        snapshot.write_json(output / "request.json", request)
        os.sched_setaffinity(0, {request["cpu"]})
        for label, node in TARGETS.items():
            stage = label + ":preflight"
            verify_packet(packet, request["packet_sha256"])
            target = output / label
            target.mkdir()
            for name in ("process", "reader-process", "tmp", "cache"):
                (target / name).mkdir()
            snapshot.write_json(
                target / "target.json",
                dict(
                    label=label,
                    node=node,
                    scenario=SCENARIOS[label],
                    packet=ref(packet / "inputs.json"),
                ),
            )
            stage = label + ":pytest"
            env = child_environment(source, target)
            run_bounded(
                command(source, target, node),
                directory=target / "process",
                cwd=source,
                env=env,
                timeout=request["timeout_seconds"],
                max_rss_bytes=request["max_rss_bytes"],
                min_available_bytes=request["min_available_bytes"],
                process_tree_memory_metric="rss",
            )
            stage = label + ":reader"
            read_command = [
                sys.executable,
                "-B",
                "-m",
                PREFIX,
                "read",
                "--packet",
                str(packet),
                "--packet-sha256",
                request["packet_sha256"],
                "--target",
                str(target),
                "--label",
                label,
                "--cpu",
                str(request["cpu"]),
            ]
            run_bounded(
                read_command,
                directory=target / "reader-process",
                cwd=source,
                env=env,
                timeout=request["timeout_seconds"],
                max_rss_bytes=request["max_rss_bytes"],
                min_available_bytes=request["min_available_bytes"],
                process_tree_memory_metric="rss",
            )
            completed[label] = ref(target / "read-result.json")
        snapshot.write_json(
            output / "result.json",
            dict(
                status="three_conditional_targets_returned",
                packet=ref(packet / "inputs.json"),
                completed=completed,
                independent_biological_cases=0,
                native_source_equivalence=False,
                scientific_acceptance=False,
            ),
        )
    except BaseException as error:
        retain_failure(output, error, stage=stage)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("--repository", type=Path, required=True)
    prep.add_argument("--output", type=Path, required=True)
    prep.add_argument("--reviewed-result", type=Path, required=True)
    prep.add_argument("--reviewed-sha256", required=True)
    prep.add_argument("--review", type=Path, required=True)
    prep.add_argument("--review-sha256", required=True)
    work = sub.add_parser("worker")
    work.add_argument("--packet", type=Path, required=True)
    work.add_argument("--output", type=Path, required=True)
    work.add_argument("--request", type=Path, required=True)
    read = sub.add_parser("read")
    read.add_argument("--packet", type=Path, required=True)
    read.add_argument("--packet-sha256", required=True)
    read.add_argument("--target", type=Path, required=True)
    read.add_argument("--label", choices=TARGETS, required=True)
    read.add_argument("--cpu", type=int, required=True)
    args = parser.parse_args()
    if args.action == "prepare":
        prepare(
            args.repository,
            args.output,
            reviewed_result=args.reviewed_result,
            reviewed_sha256=args.reviewed_sha256,
            review=args.review,
            review_sha256=args.review_sha256,
        )
    elif args.action == "worker":
        require(os.environ.get(handoff.RELEASE_ENV) == "1", "Held: existing Root release required")
        worker(args.packet, args.output, read_json(args.request))
    else:
        inputs = verify_packet(args.packet, args.packet_sha256)
        result = read_target(args.target, inputs, label=args.label, cpu=args.cpu)
        snapshot.write_json(args.target / "read-result.json", result)


if __name__ == "__main__":
    main()
