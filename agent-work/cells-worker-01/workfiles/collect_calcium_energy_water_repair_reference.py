"""Combine disjoint passing repair contracts without repeating scientific runs."""

import argparse
import ast
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PREFIX = Path("/mnt/workspaces/Cells")
TEST = "validation/tissue/test_calcium_energy_water_repair_reference.py"
OWNED = (
    TEST,
    "validation/tissue/calcium_energy_water_repair_reference.py",
    "validation/tissue/calcium_energy_water_repair_fixtures.py",
    "agent-work/cells-worker-01/workfiles/check_calcium_energy_water_repair_reference.py",
)
DEPENDENCIES = (
    "validation/tissue/calcium_energy_water_reference.py",
    "validation/tissue/morris_lecar_repair_reference.py",
    "validation/tissue/test_calcium_energy_water_reference.py",
    "validation/tissue/test_calcium_energy_reference.py",
    "validation/tissue/surface_reference.py",
    "validation/chemistry/finite_energy_reference.py",
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def syntax(path):
    nodes = ast.parse(path.read_text()).body
    return (
        {
            n.name: ast.dump(n, include_attributes=False)
            for n in nodes
            if isinstance(n, ast.FunctionDef)
        },
        {
            ast.dump(n, include_attributes=False)
            for n in nodes
            if not isinstance(n, ast.FunctionDef)
        },
    )


def collect(output, components):
    output.mkdir(exist_ok=False)
    final_functions, final_globals = syntax(ROOT / TEST)
    cases, reports, guards, verified, inputs = {}, {}, {}, {}, None
    runner_versions = {}
    for directory in components:
        report, arguments = read(directory / "result.json"), read(directory / "inputs.json")
        assert report["status"] == "passed"
        functions, globals_before = syntax(directory / "sources" / TEST)
        assert globals_before <= final_globals
        assert all(final_functions[name] == body for name, body in functions.items())
        for relative in (*OWNED[1:3], *DEPENDENCIES):
            assert digest(ROOT / relative) == report["source_sha256"][relative]
        runner = OWNED[3]
        old_runner = (directory / "sources" / runner).read_text()
        current_runner = (ROOT / runner).read_text()
        normalized = (
            current_runner.replace(
                '    parser.add_argument("--max-command-seconds", type=int, default=180)\n', ""
            )
            .replace(
                "    if not 1 <= args.max_command_seconds <= 540:\n"
                '        parser.error("Attached command allowance '
                'must be between 1 and 540 seconds")\n',
                "",
            )
            .replace("max_command_seconds=args.max_command_seconds", "max_command_seconds=180")
            .replace("timeout=args.max_command_seconds", "timeout=180")
        )
        assert ast.dump(ast.parse(old_runner)) in (
            ast.dump(ast.parse(current_runner)),
            ast.dump(ast.parse(normalized)),
        )
        runner_versions[str(directory)] = dict(
            sha256=report["source_sha256"][runner],
            allowance_s=arguments["max_command_seconds"],
            only_permitted_change=(
                "Optional command allowance, default180/max540; scientific inputs unchanged"
            ),
        )
        for relative, expected in report["output_sha256"].items():
            assert digest(directory / relative) == expected, str(directory / relative)
        verified[str(directory)] = len(report["output_sha256"])
        raw_inputs = arguments["serialized_input_sha256"]
        assert inputs is None or inputs == raw_inputs
        inputs = raw_inputs
        for item in ET.parse(directory / "tests.xml").getroot().iter("testcase"):
            assert not any(item.find(key) is not None for key in ("failure", "error", "skipped"))
            name = item.get("name")
            identity = item.get("classname") + "::" + name
            function = name.split("[", 1)[0]
            assert identity not in cases and functions[function] == final_functions[function]
            cases[identity] = dict(
                receipt=str(directory / "result.json"), function=function, ast_matches_final=True
            )
        guards[str(directory)] = read(directory / "pytest-guard/result.json")
        reports[str(directory)] = dict(
            result_sha256=digest(directory / "result.json"),
            xml_sha256=digest(directory / "tests.xml"),
            tests=report["tests"],
            sources_changed_during_checks=report["sources_changed_during_checks"],
        )
    assert len(cases) == 93
    result = dict(
        status="passed",
        distinct_independent_contracts=len(cases),
        selected_case_receipts=cases,
        component_receipts=reports,
        all_selected_functions_match_final=True,
        all_existing_helpers_and_module_globals_unchanged=True,
        added_imports="Independent finite-energy and material-accounting helpers only",
        owned_source_sha256={relative: digest(ROOT / relative) for relative in OWNED},
        frozen_dependency_sha256={relative: digest(ROOT / relative) for relative in DEPENDENCIES},
        serialized_input_sha256=inputs,
        verified_output_hash_counts=verified,
        resource_guards=guards,
        runner_versions=runner_versions,
        max_process_tree_rss_bytes=max(
            g["sampled_peak_process_tree_rss_bytes"] for g in guards.values()
        ),
        min_available_host_memory_bytes=min(
            g["minimum_available_host_memory_bytes"] for g in guards.values()
        ),
        all_attempts=[
            dict(
                path=str(p / "result.json"),
                sha256=digest(p / "result.json"),
                status=read(p / "result.json")["status"],
            )
            for p in sorted(PREFIX.glob("calcium-energy-water-repair-reference-20261028-*"))
            if (p / "result.json").is_file()
        ],
        endpoint_derivative=read(components[-1] / "evidence/endpoint-live-lesion-water-fuel.json"),
        physical_clocks=[
            dict(
                evidence=str(components[-1] / f"evidence/physical-repair-clock-{d}.json"),
                **{
                    key: value
                    for key, value in read(
                        components[-1] / f"evidence/physical-repair-clock-{d}.json"
                    ).items()
                    if key not in ("inputs", "traces")
                },
            )
            for d in ("0.0", "0.25", "1.0")
        ],
        short_full48=read(components[-1] / "evidence/short48-refinement.json"),
        oracle_unchanged_since_root_freeze=digest(ROOT / OWNED[1])
        == "b1e2ce8b7e3d684ace8b302369f701bc44181651c2722ef99dad02b364f356ce",
        scope=(
            "Independent CPU/NumPy/Decimal only; short full48 injury coupling and separate "
            "scalar physical clocks; structural repair energy not modelled; "
            "no GPU/full-cell settling claim"
        ),
    )
    (output / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(
        json.dumps(
            dict(
                path=str(output / "result.json"),
                sha256=digest(output / "result.json"),
                tests=len(cases),
            )
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--components", type=Path, nargs="+", required=True)
    args = parser.parse_args()
    collect(args.output, args.components)
