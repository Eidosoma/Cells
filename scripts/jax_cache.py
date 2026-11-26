"""This VM's shared JAX compilation cache for development runs (D321, step 1). Host only: the
standard library, no JAX.

The cache was qualified on this machine's CPU on 20 November 2026 in JAX's default mode (no lock,
no eviction, every compile written; /mnt/workspaces/Cells/cache-qualify-20261119/run-1). This tool
keeps it in that mode:
- one CPU-only folder per jaxlib version and CPU model, ROOT/cpu-jaxlib<VERSION>-<CPU>. JAX's key
  covers the jaxlib version but not the host CPU's features, so a VM moved to another CPU type, or a
  venv upgrade, starts a fresh folder instead of loading another machine's executables;
- the qualified settings: every compile written (minimum compile time 0, no minimum entry size),
  the CPU only;
- size by a nightly sweep, not JAX's own eviction: JAX's LRUCache needs the filelock package, was
  never qualified here, and scans every entry under its lock on each write.

Who opts in: development units through `scripts/run_detached.sh --jax-cache`, and one command
through `scripts/with_jax_cache.sh`. Nothing else: every other run_detached unit, the tier runner and
the gates run with the cache disabled, so tier seconds stay cold and judged runs stay as registered.

  folder [--root ROOT] [--python PY]
      This machine's folder for PY's jaxlib (default venv-cpu's). ROOT defaults to
      /mnt/workspaces/Cells/jax-cache, or CELLS_JAX_CACHE_ROOT when set (tests).
  env [--root ROOT] [--python PY]
      The opt-in environment, one NAME=VALUE per line: the folder, the qualified settings, the CPU
      only, and CELLS_JAX_CACHE (the folder again, for a run's own record of its cache).
  sweep [--root ROOT] [--python PY] [--cap SIZE] [--min-age SECONDS] [--dry-run]
      The nightly sweep (D321 option B): folders of another jaxlib or CPU removed; in this machine's
      folder, entries older than --min-age (default 600 s) that do not decompress removed (a torn
      write: JAX's put writes in place, and never replaces an existing key), reading only entries
      written since the last sweep (ROOT/sweep-state.json) and never touching an access time; then,
      above --cap (default 8G), the least recently read entries removed down to 90% of it (relatime
      keeps a daily access time). One JSON line per sweep, printed and appended to
      ROOT/sweep.jsonl.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import time
import zlib
from datetime import datetime, timezone
from pathlib import Path

# CELLS_JAX_CACHE_ROOT moves the folders elsewhere (tests keep them in their own tmp_path).
ROOT = Path(os.environ.get("CELLS_JAX_CACHE_ROOT", "/mnt/workspaces/Cells/jax-cache"))
PYTHON = Path("/mnt/workspaces/Cells/venv-cpu/bin/python")
CAP = 8 * 1024**3
SUFFIX = "-cache"  # jax/_src/lru_cache.py's _CACHE_SUFFIX
ZSTD_MAGIC = b"\x28\xb5\x2f\xfd"  # A zstd frame, if zstandard is ever installed (not checkable here)
SIZE = re.compile(r"^(\d+(?:\.\d+)?)([KMGT]?)$")


def jaxlib_version(python):
    """PY's jaxlib version, read from its venv's metadata (no import)."""
    venv = Path(python).absolute().parent.parent
    for meta in sorted(venv.glob("lib/python*/site-packages/jaxlib-*.dist-info/METADATA")):
        for line in meta.read_text(errors="replace").splitlines():
            if line.startswith("Version:"):
                return line.split(":", 1)[1].strip()
    raise SystemExit(f"no jaxlib in {venv}")


def cpu_signature(cpuinfo="/proc/cpuinfo"):
    """vendor-family-model-<8 hex of the sorted flags>, from the first processor's block."""
    fields = {}
    for line in Path(cpuinfo).read_text().splitlines():
        if not line.strip():
            break
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    vendor = {"GenuineIntel": "intel", "AuthenticAMD": "amd"}.get(fields.get("vendor_id"), "cpu")
    flags = " ".join(sorted(fields.get("flags", "").split()))
    return "-".join((vendor, fields.get("cpu family", "x"), fields.get("model", "x"),
                     hashlib.sha256(flags.encode()).hexdigest()[:8]))


def folder(root=ROOT, python=PYTHON, cpuinfo="/proc/cpuinfo"):
    return Path(root) / f"cpu-jaxlib{jaxlib_version(python)}-{cpu_signature(cpuinfo)}"


def environment(path):
    """The opt-in environment for FOLDER (module docstring): CPU only, every compile written."""
    return {"JAX_ENABLE_COMPILATION_CACHE": "true", "JAX_COMPILATION_CACHE_DIR": str(path),
            "JAX_PERSISTENT_CACHE_MIN_COMPILE_TIME_SECS": "0",
            "JAX_PERSISTENT_CACHE_MIN_ENTRY_SIZE_BYTES": "0", "JAX_PLATFORMS": "cpu",
            "CUDA_VISIBLE_DEVICES": "", "CELLS_JAX_CACHE": str(path)}


def size_bytes(text):
    m = SIZE.match(text.strip().upper())
    if not m:
        raise argparse.ArgumentTypeError(f"not a size: {text}")
    return int(float(m.group(1)) * 1024 ** " KMGT".index(m.group(2) or " "))


def read_quietly(path, st):
    """PATH's bytes without touching its access time, which the sweep's LRU order is read from."""
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOATIME", 0))
    except PermissionError:  # O_NOATIME needs the file's owner: read, then put the times back.
        data = path.read_bytes()
        os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns))
        return data
    with os.fdopen(fd, "rb") as handle:
        return handle.read()


def torn(path, st):
    """Whether a cache entry is unreadable: JAX writes zlib (zstandard is not installed here)."""
    data = read_quietly(path, st)
    if data.startswith(ZSTD_MAGIC):
        return False
    try:
        zlib.decompress(data)
    except zlib.error:
        return True
    return False


def sweep(root=ROOT, current=None, cap=CAP, min_age=600.0, dry_run=False, now=None, since=None):
    """One sweep (module docstring). An entry is never rewritten once complete (JAX's put leaves an
    existing key alone), so only entries written since SINCE (epoch seconds; None: all) are read."""
    root, now = Path(root), time.time() if now is None else now
    report = {"utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "root": str(root),
              "folder": str(current), "cap_bytes": cap, "dry_run": dry_run,
              "removed_folders": [], "removed_torn": [], "removed_lru": 0, "freed_bytes": 0,
              "checked": 0, "checked_until": now - min_age}
    for other in sorted(root.glob("cpu-*")):
        if other.is_dir() and other != current:
            report["removed_folders"].append(other.name)
            if not dry_run:
                shutil.rmtree(other)
    entries = sorted(current.glob("*" + SUFFIX)) if current and current.is_dir() else []
    report["entries_before"] = len(entries)
    kept = []
    for path in entries:
        st = path.stat()
        due = now - st.st_mtime >= min_age and (since is None or st.st_mtime >= since)
        report["checked"] += due
        if due and torn(path, st):
            report["removed_torn"].append(path.name)
            report["freed_bytes"] += st.st_size
            if not dry_run:
                path.unlink()
        else:
            kept.append((st.st_atime, st.st_size, path))
    total = sum(size for _, size, _ in kept)
    report["bytes_before"] = total + report["freed_bytes"]
    if total > cap:
        for atime, size, path in sorted(kept):  # Least recently read first.
            if total <= 0.9 * cap:
                break
            if not dry_run:
                path.unlink()
            total -= size
            report["removed_lru"] += 1
            report["freed_bytes"] += size
    report["entries_after"] = len(kept) - report["removed_lru"]
    report["bytes_after"] = total
    return report


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="command", required=True)
    for name in ("folder", "env", "sweep"):
        s = sub.add_parser(name)
        s.add_argument("--root", type=Path, default=ROOT)
        s.add_argument("--python", type=Path, default=PYTHON)
        if name == "sweep":
            s.add_argument("--cap", type=size_bytes, default=CAP)
            s.add_argument("--min-age", type=float, default=600.0)
            s.add_argument("--dry-run", action="store_true")
    a = p.parse_args(argv)
    path = folder(a.root, a.python)
    if a.command == "folder":
        print(path)
    elif a.command == "env":
        for name, value in environment(path).items():
            print(f"{name}={value}")
    else:
        state = a.root / "sweep-state.json"  # Where the last sweep's checks reached.
        since = json.loads(state.read_text())["checked_until"] if state.is_file() else None
        report = sweep(a.root, path, a.cap, a.min_age, a.dry_run, since=since)
        line = json.dumps(report)
        if not a.dry_run and a.root.is_dir():
            with open(a.root / "sweep.jsonl", "a") as log:
                log.write(line + "\n")
            state.write_text(json.dumps({"checked_until": report["checked_until"]}) + "\n")
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
