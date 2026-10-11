"""D125 source-bound same-horizon recording qualification; no scientific changes."""

import hashlib
import json
import os
import resource
import shutil
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
LEGACY = ROOT / "runs/ref-005c-refined-pump-2026-09-16/refinement-01"
CODEC = ROOT / "runs/ref-005d-offline-codec-2026-09-17/qualification-01"
AUDIT = ROOT / "runs/ref-005d-codec-audit-2026-09-17/audit-01"
AUDIT_SHA = "b7cc5472783236f12ccec4e658374ba83c28dba11851543a4ebdca81e3fc883f"
AUDIT_REG_SHA = "e6c8a6c884aa243db1b554448048b702b9c31f746add10d1c384a803948a03f3"
CELLS_PYTHON = ROOT / ".venv/bin/python"
NATIVE_PYTHON = ROOT / "upstream/betse-venv/bin/python"
BOUNDS = dict(
    cpu_affinity=[0, 1, 2, 3],
    timeout_seconds=1800,
    native_timeout_seconds=900,
    cells_timeout_seconds=750,
    per_file_bytes=32 * 1024**2,
    artifact_bytes=512 * 1024**2,
    free_disk_reserve_bytes=1024**3,
    native_address_space_bytes=8 * 1024**3,
    cells_address_space_bytes=16 * 1024**3,
)


def need(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def path_for(directory, relative):
    path = directory / relative
    need(
        not Path(relative).is_absolute() and path.resolve().is_relative_to(directory), "Unsafe path"
    )
    need(not any(p.is_symlink() for p in (path, *path.parents)), "Linked evidence path")
    return path


def hashes(directory, manifest):
    for name, digest in manifest.items():
        need(sha(path_for(directory, name)) == digest, "Changed input: " + name)


def inventory(directory):
    result = {}
    for path in sorted(directory.rglob("*")):
        need(not path.is_symlink() and (path.is_dir() or path.is_file()), "Unsafe artifact")
        if path.is_file():
            result[str(path.relative_to(directory))] = sha(path)
    return result


def budget(directory, reserve=1024**2):
    total = 0
    for path in directory.rglob("*"):
        need(not path.is_symlink(), "Linked output")
        if path.is_file():
            size = path.stat().st_size
            need(size <= BOUNDS["per_file_bytes"], "Per-file quota")
            total += size
    need(total + reserve <= BOUNDS["artifact_bytes"], "Aggregate artifact quota")
    need(
        shutil.disk_usage(directory).free >= BOUNDS["free_disk_reserve_bytes"], "Free-disk reserve"
    )
    return total


def capsule(directory, sources):
    hashes(ROOT, sources)
    with zipfile.ZipFile(directory / "sources.zip") as archive:
        need(
            len(archive.namelist()) == len(sources) and set(archive.namelist()) == set(sources),
            "Capsule membership",
        )
        for name, digest in sources.items():
            need(hashlib.sha256(archive.read(name)).hexdigest() == digest, "Capsule bytes")


def prerequisite():
    """Controller-only, model-free authentication; not another decoder/audit run."""
    sys.path.insert(0, str(HERE.parent / "native_recording_audit"))
    import codec_audit_context as prior

    with prior.e.model_fence():
        _, _, captured = prior.authenticate()
        need(sha(AUDIT / "completion.json") == AUDIT_SHA, "Audit completion identity")
        need(sha(AUDIT / "registration.json") == AUDIT_REG_SHA, "Audit registration identity")
        r, done = read(AUDIT / "registration.json"), read(AUDIT / "completion.json")
        need(
            done["status"] == "offline_lossless_recording_independently_closed"
            and done["offline_codec_qualified"] is True
            and done["failed_comparisons"] == 0
            and done["rows"] == 36,
            "Offline review not closed",
        )
        need(r["capture_files_sha256"] == captured, "Reviewed codec inventory changed")
        files = inventory(AUDIT)
        need(
            set(files)
            == set(done["files_sha256"])
            | {"completion.json", "launch.json", "runner.stdout.log", "runner.stderr.log"},
            "Review packet membership",
        )
        hashes(AUDIT, done["files_sha256"])
        capsule(AUDIT, r["sources_sha256"])
        need(prior.e.software(ROOT / r["software"]["path"], 133) == r["software"], "Review tests")
        need(read(AUDIT / "launch.json")["registration_sha256"] == AUDIT_REG_SHA, "Review launch")
    return dict(
        audit_completion_sha256=AUDIT_SHA, audit_files_sha256=files, codec_files_sha256=captured
    )


def sources():
    names = set(read(LEGACY / "registration.json")["sources_sha256"])
    for directory in (CODEC, AUDIT):
        names.update(read(directory / "registration.json")["sources_sha256"])
    names.update(str(p.relative_to(ROOT)) for p in HERE.iterdir() if p.suffix in (".py", ".md"))
    names.update(("reports/REF005D_CODEC_CLOSEOUT.md", "reports/REF005D_LIVE_HANDOFF.md"))
    return {name: sha(ROOT / name) for name in sorted(names)}


def environment():
    env = os.environ.copy()
    for name in ("PYTHONPATH", "PYTEST_ADDOPTS", "PYTEST_PLUGINS"):
        env.pop(name, None)
    env.update(
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONNOUSERSITE="1",
        PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
        JAX_PLATFORMS="cpu",
        JAX_ENABLE_X64="true",
        JAX_DISABLE_JIT="false",
        OPENBLAS_NUM_THREADS="1",
        OMP_NUM_THREADS="1",
        MKL_NUM_THREADS="1",
        NUMEXPR_NUM_THREADS="1",
        MPLBACKEND="Agg",
    )
    return env


def rss():
    fields = dict(line.split(":", 1) for line in Path("/proc/self/status").read_text().splitlines())
    return dict(
        current_bytes=int(fields["VmRSS"].split()[0]) * 1024,
        process_peak_bytes=int(fields["VmHWM"].split()[0]) * 1024,
        rusage_peak_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
    )
