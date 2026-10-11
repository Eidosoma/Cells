"""Close the development integration checks, explicitly not CORE-010 release acceptance."""

import hashlib
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cells.io import _write_json, runtime_identity, source_hashes  # noqa: E402
from scripts.test_spatial_extracellular_build import implementation_hashes  # noqa: E402

DOCUMENTS = {
    "PROGRESS.md",
    "README.md",
    "docs/ARCHITECTURE.md",
    "docs/BETSE_CAPABILITY_ROADMAP.md",
    "docs/DECISIONS.md",
    "docs/EXPERIMENTS.md",
    "docs/MULTISCALE_DESIGN.md",
    "docs/MULTISCALE_EXECUTION_ARCHITECTURE.md",
    "docs/ROADMAP.md",
    "docs/SCIENTIFIC_BASIS.md",
}
API_AND_VERSION = {
    "pyproject.toml",
    "src/cells/__init__.py",
    "src/cells/core/specs.py",
    "src/cells/core/schedule.py",
    "src/cells/core/state.py",
    "src/cells/models/registry.py",
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def close():
    baseline = json.loads((ROOT / "reports/core-010-workspace-baseline.json").read_text())[
        "files_sha256"
    ]
    missing = [p for p in baseline if not (ROOT / p).is_file()]
    if missing:
        raise ValueError(f"Pre-existing files are missing: {missing}")
    changed = {
        p: {"before": value, "after": sha(ROOT / p)}
        for p, value in baseline.items()
        if sha(ROOT / p) != value
    }
    if set(changed) != DOCUMENTS | API_AND_VERSION:
        raise ValueError(
            f"Unexpected baseline changes: {sorted(set(changed) ^ (DOCUMENTS | API_AND_VERSION))}"
        )
    matrix_path = ROOT / "reports/core-010-regression-01/verification.json"
    matrix = json.loads(matrix_path.read_text())
    if matrix["status"] != "pass" or matrix["implementation_sha256"] != implementation_hashes():
        raise ValueError("Passing matrix does not authenticate this unchanged implementation")
    preflight = ROOT / "reports/core-010-preflight-06.xml"
    suites = ET.parse(preflight).getroot().findall("testsuite")
    preflight_counts = {
        k: sum(int(s.get(k, 0)) for s in suites) for k in ("tests", "failures", "errors", "skipped")
    }
    if any(preflight_counts[k] for k in ("failures", "errors", "skipped")):
        raise ValueError("Expanded preflight is not passing")
    preserved = json.loads((ROOT / "reports/core-010-preservation.json").read_text())
    if sha(ROOT / preserved["archive"]) != preserved["archive_sha256"]:
        raise ValueError("Accepted source archive changed")
    audit_path = ROOT / "reports/core-010-preserved-num010-audit.json"
    audit = json.loads(audit_path.read_text())
    if audit["status"] != "verified" or audit["ode_calls"] != 0 or audit["production_imported"]:
        raise ValueError("Preserved reference read-only audit failed")
    current = source_hashes()
    old_changes = {p for p, value in preserved["source_hashes"].items() if current.get(p) != value}
    if old_changes != {
        p.removeprefix("src/cells/") for p in API_AND_VERSION if p.startswith("src/cells/")
    }:
        raise ValueError("Existing physical law or shared execution module changed")
    quality = {}
    for name, args in (("lint", ["check"]), ("format", ["format", "--check"])):
        worker = subprocess.run(
            [str(ROOT / ".venv/bin/ruff"), *args, "src", "tests", "scripts"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        quality[name] = worker.stdout.strip()
    listed = (
        subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z", "--", "."],
            cwd=ROOT,
            capture_output=True,
            check=True,
        )
        .stdout.decode()
        .split("\0")
    )
    new = {
        p: sha(ROOT / p) for p in sorted(set(listed) - set(baseline) - {""}) if (ROOT / p).is_file()
    }
    result = {
        "status": "pass",
        "scope": "CORE-010 development integration and regression only",
        "core010_release_accepted": False,
        "next_gate": (
            "Frozen full production panel, independent saved-data/corruption audit, "
            "fresh-process paths and release closeout"
        ),
        "runtime": runtime_identity(),
        "production_sources": len(current),
        "source_hashes": current,
        "baseline_files": len(baseline),
        "unchanged_baseline_files": len(baseline) - len(changed),
        "changed_baseline_files": changed,
        "missing_baseline_files": missing,
        "unchanged_old_production_files": len(preserved["source_hashes"]) - len(old_changes),
        "new_production_files": sorted(set(current) - set(preserved["source_hashes"])),
        "new_workspace_files_sha256_before_receipt": new,
        "preservation_sha256": sha(ROOT / "reports/core-010-preservation.json"),
        "preserved_reference_audit_sha256": sha(audit_path),
        "preflight": preflight_counts | {"sha256": sha(preflight)},
        "regression": {
            "total_tests": matrix["total_tests"],
            "contexts": matrix["contexts"],
            "sha256": sha(matrix_path),
        },
        "quality": quality,
        "driver_sha256": sha(__file__),
        "retained_preflight_failures": {
            "reports/core-010-preflight-01.xml": (
                "Four test API errors (.checkpoint instead of .final); 69 passing tests."
            ),
            "reports/core-010-preflight-03.xml": (
                "One test incorrectly assumed initial-step depletion; 49 passing execution tests. "
                "Replaced with a definite negative trial, not relaxed checks."
            ),
        },
        "biological_validation": False,
        "gpu_tested": False,
    }
    _write_json(ROOT / "reports/core-010-implementation-closeout.json", result)
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "status",
                    "baseline_files",
                    "unchanged_baseline_files",
                    "production_sources",
                    "core010_release_accepted",
                )
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    close()
