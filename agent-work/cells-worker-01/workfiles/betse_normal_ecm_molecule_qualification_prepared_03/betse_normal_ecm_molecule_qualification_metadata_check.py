"""Bounded synthetic admission, child, outcome and source controls; no science."""

import argparse
import ast
import copy
import json
import os
import resource
import struct
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from types import SimpleNamespace

import betse_normal_ecm_molecule_qualification_plugin as plugin
import betse_normal_ecm_molecule_qualification_reader as reader
from betse_normal_ecm_molecule_qualification_contract import (
    PREFIX,
    read,
    require,
    sha,
    verify_bundle,
    verify_release,
    write,
)
from betse_normal_ecm_molecule_qualification_resources import memory_available, run_bounded


def normalized(node):
    return ast.dump(node, include_attributes=False)


def source_proofs(bundle):
    inputs = read(bundle / "inputs.json")
    root = Path(inputs["packets"]["transport"]["packet"]) / "source"
    resources = ast.parse((bundle / (PREFIX + "_resources.py")).read_text())
    original = ast.parse((root / "validation/assembly/component_process.py").read_text())
    proofs = []
    for node in original.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            own = next(
                n for n in resources.body if isinstance(n, type(node)) and n.name == node.name
            )
            require(
                normalized(own) == normalized(node), "Existing process guard changed: " + node.name
            )
            proofs.append("literal_process_guard/" + node.name)
    original = ast.parse((root / "validation/ensemble/profile_cluster.py").read_text())
    for name in ("memory_available", "process_sample", "process_tree"):
        a = next(n for n in resources.body if isinstance(n, ast.FunctionDef) and n.name == name)
        b = next(n for n in original.body if isinstance(n, ast.FunctionDef) and n.name == name)
        require(normalized(a) == normalized(b), "Existing descendant sampler changed")
        proofs.append("literal_descendant_sampler/" + name)
    reused = inputs["reused_sources"]["exact_pytest_ID_reader"]
    source = bundle / reused["path"]
    require(sha(source) == reused["sha256"], "Exact-ID reader source copy changed")
    a = next(
        n
        for n in ast.parse((bundle / (PREFIX + "_reader.py")).read_text()).body
        if isinstance(n, ast.FunctionDef) and n.name == "verify_pytest_ids"
    )
    b = next(
        n
        for n in ast.parse(source.read_text()).body
        if isinstance(n, ast.FunctionDef) and n.name == "verify_pytest_ids"
    )
    require(normalized(a) == normalized(b), "Existing exact pytest ID reader changed")
    proofs.append("literal_exact_pytest_ID_reader")
    for path in bundle.glob("*.py"):
        compile(path.read_text(), str(path), "exec")
        proofs.append("compile_without_execution/" + path.name)
    return proofs


def scalar_archive(folder, value=0.125, *, wrong_shape=False, compression=zipfile.ZIP_STORED):
    folder.mkdir()
    text = b"{'descr': '<f8', 'fortran_order': False, 'shape': (), }"
    header = text + b" " * (128 - 10 - len(text) - 1) + b"\n"
    payload = (
        b"\x93NUMPY"
        + bytes((1, 0))
        + struct.pack("<H", len(header))
        + header
        + struct.pack("<d", value)
    )
    with zipfile.ZipFile(folder / "arrays.npz", "x", compression=compression) as archive:
        archive.writestr("a0.npy", payload)
    write(
        folder / "data.json",
        dict(mapping=[["value", dict(array="a0", dtype="<f8", shape=[1] if wrong_shape else [])]]),
    )
    write(
        folder / "manifest.json",
        dict(
            kind="cells.betse_normal_current_raw_evidence@1",
            complete=True,
            files={name: sha(folder / name) for name in ("arrays.npz", "data.json")},
        ),
    )


def synthetic_witnesses():
    """Reuse only the reviewed metadata witness/chain functions, never its script."""
    base = Path("/mnt/workspaces/Cells/ecm-molecule-capture-repair-20261031-01")
    path = base / "software-03/metadata_checks.py"
    require(
        sha(path) == "32c72bb0f5d0a4305030f257393b526bc7deedbec30a1d7b7281e29dcad917d3",
        "Root synthetic witness source changed",
    )
    witness = next(
        n
        for n in ast.parse(path.read_text()).body
        if isinstance(n, ast.FunctionDef) and n.name == "witness"
    )
    path = base / "proposal/validation/betse/betse_normal_ecm_molecule_failure_checks.py"
    require(
        sha(path) == "95b303d2816379a719b045acf9c211b9dde2900ef19de3c9e81cb963410fca19",
        "Reviewed metadata chain helper changed",
    )
    chain = next(
        n
        for n in ast.parse(path.read_text()).body
        if isinstance(n, ast.FunctionDef) and n.name == "exception_chain"
    )
    scope = dict(copy=copy)
    exec(
        compile(
            ast.Module(body=[witness, chain], type_ignores=[]),
            "<reviewed synthetic metadata helpers>",
            "exec",
        ),
        scope,
    )
    return scope["witness"], scope["exception_chain"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    os.sched_setaffinity(0, {0})
    resource.setrlimit(resource.RLIMIT_AS, (512 * 2**20, 512 * 2**20))
    resource.setrlimit(resource.RLIMIT_CPU, (120, 120))
    require(memory_available() >= 8 * 2**30, "8 GiB metadata reserve required")
    require(not args.out.exists(), "Exclusive synthetic evidence output required")
    args.out.mkdir()
    began = time.monotonic()
    bundle = args.bundle.resolve()
    before = sha(bundle / "MANIFEST.json")
    inputs = verify_bundle(bundle)
    proofs = source_proofs(bundle)
    controls = []

    def test(name, action, *, refuses=False):
        try:
            action()
        except (ValueError, KeyError, AssertionError, AttributeError) as error:
            if not refuses:
                raise
            controls.append(
                dict(name=name, passed=True, refusal=type(error).__name__, message=str(error))
            )
        else:
            require(not refuses, "Unexpected metadata acceptance: " + name)
            controls.append(dict(name=name, passed=True))

    test(
        "separate_44_60_exact_rosters",
        lambda: require(
            [len(inputs["rosters"][f]) for f in ("dispatch", "transport")] == [44, 60]
            and [
                inputs["planned"][f]["independent_reference_forms"]
                for f in ("dispatch", "transport")
            ]
            == [942, 1306],
            "Separate rosters changed",
        ),
    )
    test(
        "held_start_without_release",
        lambda: verify_release(bundle, dict(requested_round=True, release_path=None)),
        refuses=True,
    )
    test(
        "held_worker_without_requested_round",
        lambda: verify_release(bundle, dict(requested_round=False)),
        refuses=True,
    )
    target = args.out / "must-not-exist"
    command = [
        sys.executable,
        "-B",
        str(bundle / (PREFIX + "_runner.py")),
        "start",
        "--families",
        "dispatch",
        "--cpu",
        "0",
        "--output",
        str(target),
        "--round-id",
        "synthetic-held",
        "--requested-round",
    ]
    held = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=15,
        check=False,
    )
    (args.out / "held-start.log").write_text(held.stdout)
    test(
        "held_CLI_refuses_before_run_directory",
        lambda: require(
            held.returncode != 0
            and "Held: separate Chief release contract required" in held.stdout
            and not target.exists(),
            "Held launch reached mutation",
        ),
    )
    expected = ["tests/unit/test_example.py::test_metadata[one]"]
    good = ET.fromstring(
        '<testsuite><testcase classname="tests.unit.test_example" '
        'name="test_metadata[one]"/></testsuite>'
    ).findall("testcase")
    test("unique_pytest_ID_accept", lambda: reader.verify_pytest_ids(good, expected))
    test(
        "duplicate_pytest_ID_refusal",
        lambda: reader.verify_pytest_ids(good + good, expected),
        refuses=True,
    )
    for kind in ("failure", "error", "skipped"):
        poisoned = copy.deepcopy(good)
        ET.SubElement(poisoned[0], kind)
        test(
            kind + "_pytest_refusal",
            lambda poisoned=poisoned: reader.verify_pytest_ids(poisoned, expected),
            refuses=True,
        )
    metric = dict(
        fresh_conditional_reference=True,
        carried_reference_forms=0,
        physical_global_conservation_credit=False,
        fields=dict(x=dict(normalized_max_error=1.0)),
        resolutions=dict(x=dict(normalized_max_error=0.1)),
    )
    test("original_metric_endpoints", lambda: reader.metric(metric))
    for label, part, value in (
        ("raised_budget", "fields", 1.00000001),
        ("raised_resolution", "resolutions", 0.100000001),
        ("NaN_metric", "fields", float("nan")),
    ):
        bad = copy.deepcopy(metric)
        bad[part]["x"]["normalized_max_error"] = value
        test(label, lambda bad=bad: reader.metric(bad), refuses=True)
    library_path = str(Path(json.__file__).resolve())
    runtime = dict(
        measured_cpu_affinity=[0],
        executable=inputs["interpreter"],
        loaded_files=dict(
            json=dict(path=library_path, sha256=inputs["library_pins"][library_path])
        ),
        modules_without_files=[],
    )
    test(
        "bound_runtime_metadata_accept",
        lambda: reader.runtime(runtime, inputs, "dispatch", 0, reference=True),
    )
    runtime_changes = {
        "actual_child_wrong_CPU": lambda value: value.update(measured_cpu_affinity=[3]),
        "actual_child_wrong_interpreter": lambda value: value["executable"].update(sha256="0" * 64),
        "actual_loaded_file_changed": lambda value: value["loaded_files"]["json"].update(
            sha256="0" * 64
        ),
        "actual_loaded_file_unbound": lambda value: value["loaded_files"]["json"].update(
            path="/tmp/foreign-source.py"
        ),
        "forbidden_reference_module": lambda value: value["modules_without_files"].append("numpy"),
    }
    for name, change in runtime_changes.items():
        value = copy.deepcopy(runtime)
        change(value)
        test(
            name,
            lambda value=value: reader.runtime(value, inputs, "dispatch", 0, reference=True),
            refuses=True,
        )
    witness, chain = synthetic_witnesses()
    exact = SimpleNamespace(exact=lambda a, b: require(a == b, "Synthetic exact-tree mismatch"))

    def raw_parts(case="second_GRN_negative", transport=True):
        error, native, partial, parent = witness(case, transport)
        outcome = dict(
            status="unexpected_source_failure",
            failure=dict(stage="raw_molecule_dispatch", traceback="synthetic metadata"),
            capture_errors=[],
            available=dict(partial=partial, exception_chain=chain(error)),
        )
        return outcome, dict(partial=partial, parent=parent), native

    def raw_call(parts, case="second_GRN_negative", transport=True):
        reader.raw_molecule(case, *parts, exact, transport=transport, ion_ids=["Na", "Cl"])

    for case in (
        "first_general_negative",
        "second_general_negative",
        "first_GRN_negative",
        "second_GRN_negative",
    ):
        for flag in (False, True):
            test(
                "synthetic_full_partial/" + case + "/" + str(flag),
                lambda case=case, flag=flag: raw_call(raw_parts(case, flag), case, flag),
            )
    mutations = {
        "missing_outcome_partial": lambda p: p[0]["available"].pop("partial"),
        "lost_cause_chain": lambda p: p[0]["available"].update(exception_chain=[]),
        "wrong_original_type": lambda p: p[0]["available"]["exception_chain"][2].update(
            type="KeyError"
        ),
        "wrong_source_stage": lambda p: p[0]["available"]["partial"].update(stage="field"),
        "accepted_trial_after_failure": lambda p: p[0]["available"]["partial"]["holder"].update(
            trial={}
        ),
        "wrong_native_failure": lambda p: p[2]["failure"].update(type="ValueError"),
        "wrong_native_cache": lambda p: p[2]["returned"]["handlers"]["grn"].update(owner="foreign"),
        "wrong_shared_fields": lambda p: p[2]["returned"]["shared"].update(charge=[1]),
        "wrong_original_Frame": lambda p: p[0]["available"]["partial"]["holder"][
            "material_partial"
        ]["frames"][0].__setitem__(0, "field"),
        "synchronized_chemistry_omission": lambda p: p[0]["available"]["partial"]["available"][
            "traces"
        ]["grn"]["molecule_frames"].pop(3),
        "synchronized_transporter_omission": lambda p: p[0]["available"]["partial"]["available"][
            "traces"
        ]["molecules"]["transporter_frames"].pop(3),
        "synchronized_nonnegative_cells": lambda p: p[0]["available"]["partial"]["available"][
            "traces"
        ]["grn"]["mover_frames"][-1]["fields"].update(cX_cells=[1]),
    }
    for name, mutate in mutations.items():
        parts = raw_parts()
        mutate(parts)
        if name.startswith("synchronized_"):
            parts[2]["traces"] = copy.deepcopy(
                parts[0]["available"]["partial"]["available"]["traces"]
            )
        test(name, lambda parts=parts: raw_call(parts), refuses=True)
    returned = dict(
        status="source_returned",
        stage="dependency_baseline_initialize",
        returned=dict(state=0),
        available={},
    )
    test(
        "complete_baseline_outcome",
        lambda: reader.complete_outcome(
            returned, status="source_returned", stage="dependency_baseline_initialize"
        ),
    )
    test(
        "unexpected_success_not_raw_failure",
        lambda: reader.complete_outcome(
            returned, status="unexpected_source_failure", stage="raw_molecule_dispatch"
        ),
        refuses=True,
    )
    for family in ("dispatch", "transport"):
        store = reader.Archives(
            inputs["packets"][family]["packet"], inputs["packets"][family]["capture_profile"]
        )
        scalar = args.out / (family + "-scalar")
        scalar_archive(scalar)
        value = store.load(scalar)["value"]
        test(
            family + "_profile02_scalar",
            lambda value=value, store=store: require(
                list(store.values(value)) == [0.125], "Wrong synthetic scalar decode"
            ),
        )
        minus = args.out / (family + "-negative-zero")
        scalar_archive(minus, -0.0)
        plus = args.out / (family + "-positive-zero")
        scalar_archive(plus, 0.0)
        a, b = store.load(minus)["value"], store.load(plus)["value"]
        test(
            family + "_signed_zero_original_equality",
            lambda a=a, b=b, store=store: store.exact(a, b),
        )
        test(
            family + "_zero_dimension_scalar_equivalence",
            lambda a=a, store=store: store.exact(a, 0.0),
        )
        test(
            family + "_profile01_refusal",
            lambda family=family, store=store: store.binding.verify_profile(
                "ordinary_ecm_molecule_" + family + "_01"
            ),
            refuses=True,
        )
        test(
            family + "_other_family_profile_refusal",
            lambda family=family, store=store: store.binding.verify_profile(
                "ordinary_ecm_molecule_"
                + ("transport" if family == "dispatch" else "dispatch")
                + "_02"
            ),
            refuses=True,
        )
        wrong = args.out / (family + "-wrong-shape")
        scalar_archive(wrong, wrong_shape=True)
        test(
            family + "_descriptor_shape_refusal",
            lambda wrong=wrong, store=store: store.load(wrong),
            refuses=True,
        )
        compressed = args.out / (family + "-compressed")
        scalar_archive(compressed, compression=zipfile.ZIP_DEFLATED)
        test(
            family + "_compressed_profile_refusal",
            lambda compressed=compressed, store=store: store.load(compressed),
            refuses=True,
        )
        for name in ("capture_binding", "archive_binding", "qualification_typed_evidence"):
            sys.modules.pop(name, None)
        sys.path.remove(str(Path(inputs["packets"][family]["packet"]) / "tools"))
    profile_path = args.out / "plugin"
    profile_path.mkdir()
    os.environ["CELLS_MOLECULE_RUNNER_PROVENANCE"] = str(profile_path)
    plugin.pytest_sessionstart(None)
    try:
        subprocess.run([sys.executable, "-B", "-c", "pass"], check=True, timeout=10)
        plugin.pytest_runtest_logreport(
            SimpleNamespace(
                nodeid=expected[0], when="call", outcome="passed", failed=False, skipped=False
            )
        )
    finally:
        subprocess.Popen = plugin.ORIGINAL_POPEN
    starts = [
        json.loads(line)
        for line in (profile_path / "subprocess-start.jsonl").read_text().splitlines()
    ]
    finishes = [
        json.loads(line)
        for line in (profile_path / "subprocess-finish.jsonl").read_text().splitlines()
    ]
    test(
        "actual_synthetic_subprocess_identity_and_exit",
        lambda: require(
            len(starts) == len(finishes) == 1
            and starts[0]["pid"] == finishes[0]["pid"]
            and starts[0]["cpu_affinity"] == [0]
            and finishes[0]["returncode"] == 0,
            "Incomplete actual metadata child record",
        ),
    )
    process = args.out / "bounded-metadata-child"
    process.mkdir()
    outcome = run_bounded(
        [sys.executable, "-B", "-c", "pass"],
        directory=process,
        cwd=args.out.resolve(),
        env=dict(os.environ),
        timeout=10,
        max_rss_bytes=512 * 2**20,
        min_available_bytes=8 * 2**30,
        process_tree_memory_metric="rss",
    )
    test(
        "existing_guard_actual_metadata_child",
        lambda: require(
            outcome["status"] == "completed"
            and outcome["returncode"] == 0
            and outcome["samples"] > 0
            and outcome["minimum_available_host_memory_bytes"] >= 8 * 2**30,
            "Metadata resource guard incomplete",
        ),
    )
    test(
        "sealed_preparation_unchanged",
        lambda: require(
            sha(bundle / "MANIFEST.json") == before and verify_bundle(bundle),
            "Prepared runner changed",
        ),
    )
    require(
        not any(
            n.split(".")[0] in {"cells", "betse", "numpy", "scipy", "jax", "jaxlib", "pytest"}
            for n in sys.modules
        ),
        "Scientific module imported by metadata controls",
    )
    peak = (
        int(
            next(
                line.split()[1]
                for line in Path("/proc/self/status").read_text().splitlines()
                if line.startswith("VmHWM:")
            )
        )
        * 1024
    )
    write(
        args.out / "result.json",
        dict(
            status="passed",
            controls=controls,
            source_proofs=proofs,
            elapsed_seconds=time.monotonic() - began,
            cpu_affinity=sorted(os.sched_getaffinity(0)),
            measured_process_VmHWM_bytes=peak,
            address_space_cap_bytes=512 * 2**20,
            host_reserve_bytes=8 * 2**30,
            scientific_imports=[],
            scientific_AST_executions=0,
            reviewed_synthetic_metadata_helpers_only=True,
            fixture_reference_model_evaluations=0,
            pytest_collections=0,
            scientific_launches=0,
            active_job_queries=0,
        ),
    )
    print(
        json.dumps(
            dict(
                status="passed",
                controls=len(controls),
                source_proofs=len(proofs),
                measured_process_VmHWM_bytes=peak,
            )
        )
    )


if __name__ == "__main__":
    main()
