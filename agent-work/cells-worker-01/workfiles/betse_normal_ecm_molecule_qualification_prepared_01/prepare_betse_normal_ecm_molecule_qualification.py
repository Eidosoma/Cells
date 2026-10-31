"""Prepare exact held executable runner inputs; file metadata and AST only."""

import ast
import json
import os
import resource
import shutil
import sys
import sysconfig
from pathlib import Path

from betse_normal_ecm_molecule_qualification_contract import (
    HANDOFF,
    HANDOFF_SHA,
    PREFIX,
    REVIEW_SHA,
    read,
    require,
    sha,
    verify_packet,
    write,
)
from betse_normal_ecm_molecule_qualification_resources import memory_available

WORK = Path(__file__).parent
OUT = WORK / (PREFIX + "_prepared_01")
DEST = Path("/mnt/workspaces/Cells/ecm-molecule-qualification-runners-20261031-01")


def warm_dependencies(packet, roster):
    family = packet["family"]
    test = Path(packet["packet"]) / (
        "source/tests/unit/test_betse_normal_ecm_molecule_" + family + ".py"
    )
    tree = ast.parse(test.read_text())
    function = next(
        n
        for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name == "test_two_owner_dependency"
    )
    changes = next(
        n.value
        for n in function.body
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "changes" for t in n.targets)
    )
    initial = {ast.literal_eval(key) for key in changes.keys}
    result = {
        row["case"]
        for row in roster.values()
        if row["node_ids"][0].split("::")[1].startswith("test_two_owner_dependency[")
    } - initial
    if family == "transport":
        function = next(
            n
            for n in tree.body
            if isinstance(n, ast.FunctionDef) and n.name == "test_transporter_dependency"
        )
        guard = next(n for n in function.body if isinstance(n, ast.If))
        before = set(ast.literal_eval(guard.test.comparators[0]))
        result |= {
            row["case"]
            for row in roster.values()
            if row["node_ids"][0].split("::")[1].startswith("test_transporter_dependency[")
        } - before
    return sorted(result)


def libraries():
    paths = set()
    stdlib = Path(sysconfig.get_path("stdlib"))
    for directory, subdirs, files in os.walk(stdlib):
        subdirs[:] = [
            name
            for name in subdirs
            if name
            not in {
                "site-packages",
                "dist-packages",
                "__pycache__",
                "test",
                "tests",
                "idlelib",
                "tkinter",
                "turtledemo",
                "ensurepip",
            }
        ]
        for name in files:
            if name.endswith((".py", ".so")):
                paths.add((Path(directory) / name).resolve())
    site = Path(sysconfig.get_path("purelib"))
    selected = (
        "numpy",
        "numpy.libs",
        "scipy",
        "scipy.libs",
        "pytest",
        "_pytest",
        "pluggy",
        "packaging",
        "iniconfig",
        "pygments",
        "_distutils_hack",
    )
    for name in selected:
        folder = site / name
        require(folder.is_dir(), "Explicit runtime library directory missing: " + name)
        for path in folder.rglob("*"):
            if (
                path.is_file()
                and (path.suffix == ".py" or ".so" in path.name)
                and "__pycache__" not in path.parts
            ):
                paths.add(path.resolve())
    paths.update(path.resolve() for path in site.glob("*.py"))
    libpython = Path(sysconfig.get_config_var("LIBDIR")) / sysconfig.get_config_var("LDLIBRARY")
    if libpython.is_file():
        paths.add(libpython.resolve())
    return {str(path): sha(path) for path in sorted(paths)}


def main():
    os.sched_setaffinity(0, {0})
    resource.setrlimit(resource.RLIMIT_AS, (512 * 2**20, 512 * 2**20))
    resource.setrlimit(resource.RLIMIT_CPU, (120, 120))
    require(memory_available() >= 8 * 2**30, "8 GiB reserve required")
    require(not OUT.exists() and not DEST.exists(), "Exclusive new preparation required")
    require(sha(HANDOFF) == HANDOFF_SHA, "Chief handoff changed")
    review = HANDOFF.with_name("ROOT_VERIFICATION.json")
    require(sha(review) == REVIEW_SHA, "Root verification changed")
    handoff = read(HANDOFF)
    require(
        read(review)["status"] == "verified_exact_reviewed_capture02_source_deltas_held",
        "Reviewed02 source status required",
    )
    packets, rosters, resources, source_pins, warm = {}, {}, {}, {}, {}
    for packet in handoff["successors"]:
        family = packet["family"]
        inputs = verify_packet(packet)
        packets[family] = packet
        rosters[family] = inputs["groups"]
        resources[family] = inputs["resources"]
        source_pins[family] = inputs["source_sha256"]
        warm[family] = warm_dependencies(packet, rosters[family])
        require(
            resources[family]
            == dict(
                cpu_count=1,
                gpu=False,
                max_metadata_reader_seconds=120,
                max_process_tree_rss_bytes=2**30,
                max_scientific_command_seconds=480,
                min_available_host_memory_bytes=8 * 2**30,
                threads=1,
            ),
            "Original resource limits changed",
        )
    require(set(packets) == {"dispatch", "transport"}, "Distinct reviewed packet pair required")
    library_pins = libraries()
    OUT.mkdir()
    for name in (HANDOFF.name, review.name):
        shutil.copyfile(HANDOFF.with_name(name), OUT / name)
    own = sorted(path for path in WORK.glob("*" + PREFIX + "*.py") if path.is_file())
    for path in own:
        compile(path.read_text(), str(path), "exec")
        shutil.copyfile(path, OUT / path.name)
    notes = WORK / (PREFIX + "_implementation.md")
    shutil.copyfile(notes, OUT / notes.name)
    runner_pins = {p.name: sha(p) for p in own}
    inputs = dict(
        kind="cells.held_molecule_capture02_executable_runners@1",
        status="held_source_and_metadata_only",
        execution_hold=True,
        release_authorized=False,
        explicit_external_Chief_release_required=True,
        bundle_destination=str(DEST),
        handoff_sha256=HANDOFF_SHA,
        root_verification_sha256=REVIEW_SHA,
        packets=packets,
        rosters=rosters,
        planned={f: packets[f]["prospective"] for f in packets},
        warm_dependencies=warm,
        resources=resources,
        source_pins=source_pins,
        runner_source_pins=runner_pins,
        interpreter=dict(
            path=str(Path(sys.executable).resolve()), sha256=sha(Path(sys.executable).resolve())
        ),
        library_pins=library_pins,
        reader_caps=dict(
            max_process_tree_rss_bytes=512 * 2**20,
            min_available_host_memory_bytes=8 * 2**30,
            max_wall_seconds=120,
        ),
        capture_limits=dict(
            byte_caps=64 * 2**20,
            header_bytes=16 * 2**10,
            member_limit=310689,
            original_tool_and_profile02_pins_required=True,
            case_maximum_claim=False,
            all_captures_fit_claim=False,
        ),
        scientific_imports=0,
        scientific_AST_executions=0,
        fixture_reference_model_evaluations=0,
        pytest_collections=0,
        scientific_launches=0,
        active_job_queries=0,
        automatic_followup=False,
    )
    write(OUT / "inputs.json", inputs)
    (OUT / ".execution_hold").write_text(
        "Default held. Future start and worker both require a separately authorized "
        "exact external release contract; this source/metadata receipt is not that contract.\n"
    )
    write(
        OUT / "MANIFEST.json",
        dict(
            status="held_unrun",
            files={p.name: sha(p) for p in sorted(OUT.iterdir()) if p.is_file()},
        ),
    )
    require(
        not any(
            name.split(".")[0] in {"cells", "betse", "numpy", "scipy", "jax", "jaxlib", "pytest"}
            for name in sys.modules
        ),
        "No scientific imports during preparation",
    )
    print(
        json.dumps(
            dict(
                status="held_prepared",
                folder=str(OUT),
                libraries=len(library_pins),
                warm_dependencies=warm,
                groups={f: len(rosters[f]) for f in rosters},
                source_files=len(own),
            )
        )
    )


if __name__ == "__main__":
    main()
