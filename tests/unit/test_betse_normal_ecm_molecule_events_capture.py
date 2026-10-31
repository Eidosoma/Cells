"""Frozen capture plumbing for the held molecule lifecycle suite."""

import json
import os
import subprocess
import sys
from pathlib import Path

from cells.processes import betse_normal_ion_join as ions
from tests.unit.test_betse_fast_solver import archive_read
from validation.betse import betse_normal_grn_join_native as archives


def root(tmp_path):
    return (
        Path(os.environ.get("CELLS_COMPONENT_EVIDENCE", str(tmp_path)))
        / "normal-ecm-molecule-events"
    )


def archive(tmp_path, name, value):
    return archives.write_archive(root(tmp_path) / name, ions.data(value))


def references(folder, inputs):
    folder.mkdir(parents=True, exist_ok=False)
    from validation.betse.betse_normal_ecm_event_join_fixtures import plain as json_values

    (folder / "inputs.json").write_text(
        json.dumps(json_values(ions.data(inputs)), indent=2, allow_nan=False) + "\n"
    )
    results = []
    for level in (1, 2):
        output = folder / ("reference-" + str(level) + ".json")
        with (folder / ("reference-" + str(level) + ".stdout.log")).open("x") as stream:
            subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "-m",
                    "validation.betse.betse_normal_ecm_molecule_events_reference",
                    "--inputs",
                    str(folder / "inputs.json"),
                    "--output",
                    str(output),
                    "--refinement",
                    str(level),
                ],
                stdout=stream,
                stderr=subprocess.STDOUT,
                check=True,
                timeout=180,
            )
        result = json.loads(output.read_text())
        assert result["production_imports_denied"] and (not result["loaded_production_modules"])
        assert result["carried_reference_forms"] == 0 and result["decimal_precision"] == (
            100 if level == 1 else 160
        )
        assert result["runtime"]["measured_cpu_affinity"] == sorted(os.sched_getaffinity(0))
        results.append(result)
    return results


def isolated(folder, inputs):
    from validation.betse.betse_normal_ecm_event_join_fixtures import plain as json_values

    folder.mkdir(parents=True, exist_ok=False)
    (folder / "inputs.json").write_text(
        json.dumps(json_values(ions.data(inputs)), indent=2, allow_nan=False) + "\n"
    )
    with (folder / "native.stdout.log").open("x") as stream:
        subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "validation.betse.betse_normal_ecm_molecule_events_native",
                "--inputs",
                str(folder / "inputs.json"),
                "--output",
                str(folder / "native"),
            ],
            stdout=stream,
            stderr=subprocess.STDOUT,
            check=True,
            timeout=180,
        )
    value = archive_read(folder / "native")
    assert value["production_imports_denied"] and (not value["loaded_production_modules"])
    return value


def check(tmp_path, name, folder, rows):
    archive(
        tmp_path,
        name + "-comparison-metrics",
        dict(fields=rows, physical_global_conservation_credit=False),
    )
    report = dict(
        fields={key: row["metric"] for key, row in rows.items()},
        resolutions={key: row["resolution"] for key, row in rows.items()},
        fresh_conditional_reference=True,
        carried_reference_forms=0,
        physical_global_conservation_credit=False,
    )
    with (folder / "comparison.json").open("x") as stream:
        stream.write(json.dumps(report, indent=2, allow_nan=False) + "\n")
    assert rows and max(row["normalized_max_error"] for row in report["fields"].values()) <= 1
    assert max(row["normalized_max_error"] for row in report["resolutions"].values()) <= 0.1
