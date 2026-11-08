#!/usr/bin/env python3
"""Run unmodified BETSE out of process: ``betse seed``, ``betse init``, ``betse sim``.

BETSE is an external reference (AGENTS.md, "BETSE's role"). This tool never
imports BETSE. It executes the ``betse`` command of a separate virtual
environment on a *copy* of a prepared configuration directory, under a CPU
affinity list, with an isolated HOME and per-process RSS / host-memory guards.

Run directory layout::

    config/          copy of the prepared configuration directory; BETSE writes
                     its INITS/SIMS/RESULTS outputs here (relative YAML paths)
    home/            isolated HOME; BETSE user data and log land in home/.betse
    logs/<phase>.stdout.log, logs/<phase>.stderr.log
    inputs.json      plan and provenance, written before BETSE starts
    result.json      on success, or failure.json on any failure (outputs kept)

Usage, from the checkout root (any Python 3.11+ can orchestrate ``run``)::

    python3 validation/betse/betse_reference_run.py run \\
        --config-dir PREPARED_CONFIG_DIR [--config-file sim_config.yaml] \\
        --out betse-reference-YYYYMMDD-NN/CASE/run --venv VENV_BETSE

``prepare`` builds a fresh configuration directory from a base BETSE data
directory (e.g. ``betse/data/yaml`` of the BETSE source). Without options it
is a byte copy. ``--replace OLD NEW`` edits exactly one occurrence of a text in
the copied YAML and records the parsed keys that changed. ``--overrides``
applies declared ``[key path, value]`` pairs using the ruamel safe load/dump
procedure of validation/betse/alignment.py (asset paths ``geo/...`` and
``extra_configs/...`` are re-expressed relative to the written YAML). It needs
ruamel.yaml, so run it with the BETSE environment's Python::

    VENV_BETSE/bin/python -I validation/betse/betse_reference_run.py prepare \\
        --base BETSE_SRC/betse/data/yaml --out DIR \\
        [--replace OLD NEW]... | [--overrides FILE.json [--overrides-key KEY]] \\
        [--assets-dest REL] [--yaml-dest REL] [--expect-yaml-sha256 HEX]

Relative ``--out`` paths resolve against $CELLS_OUTPUT_ROOT. The BETSE
environment is ``--venv``, else $BETSE_VENV, else <output root>/venv-betse.
Provenance is the Cells Git revision, ``git status --porcelain`` and the dirty
diff (including untracked content of the executed tool files).
"""

import argparse
import copy
import hashlib
import json
import os
import shutil
import signal
import stat
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KIND = "cells.betse_reference_run@1"
PREPARE_KIND = "cells.betse_reference_config@1"
PHASES = ("seed", "init", "sim")
DEFAULT_OUTPUT_ROOT = "/mnt/workspaces/Cells"  # default only; $CELLS_OUTPUT_ROOT wins
ASSET_PREFIXES = ("geo/", "extra_configs/")
VERSION_PACKAGES = (
    "betse",
    "numpy",
    "scipy",
    "matplotlib",
    "ruamel.yaml",
    "dill",
    "beartype",
    "pillow",
)
INLINE_DIFF_LIMIT = 4 * 2**20
GIB = 2**30
SIGNALS = (signal.SIGTERM, signal.SIGINT, signal.SIGHUP)


class RunFailure(RuntimeError):
    """A BETSE phase or a run check failed; evidence is retained."""


class Interrupted(BaseException):
    """The runner received SIGTERM/SIGINT/SIGHUP."""


# ............................................................ small helpers


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_json(path, value):
    """Exclusive JSON write; never overwrites an existing record."""
    with Path(path).open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False, default=str)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def output_root():
    return Path(os.environ.get("CELLS_OUTPUT_ROOT") or DEFAULT_OUTPUT_ROOT)


def resolve_out(value):
    path = Path(value)
    return (path if path.is_absolute() else output_root() / path).absolute()


def resolve_venv(value):
    path = Path(value or os.environ.get("BETSE_VENV") or output_root() / "venv-betse")
    path = path.absolute()
    if not (path / "bin/python").is_file() or not (path / "bin/betse").is_file():
        raise SystemExit(f"Not a BETSE virtual environment (bin/python, bin/betse): {path}")
    return path


def relative_name(value):
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise SystemExit(f"Require a relative path inside the configuration: {value}")
    return path


def parse_cpus(text):
    cpus = []
    for part in str(text).split(","):
        lo, _, hi = part.strip().partition("-")
        cpus.extend(range(int(lo), int(hi or lo) + 1))
    if not cpus:
        raise SystemExit("Empty CPU list")
    return sorted(set(cpus))


def inventory(root):
    """Every regular file below root with size and sha256; links are refused."""
    root = Path(root)
    files = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise RunFailure(f"Symbolic link in configuration tree: {path}")
        if path.is_file():
            files[str(path.relative_to(root))] = {
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
    return files


def inventory_changes(before, after):
    return {
        "created": {k: v for k, v in after.items() if k not in before},
        "modified": {k: v for k, v in after.items() if k in before and before[k] != v},
        "removed": sorted(k for k in before if k not in after),
    }


def copy_tree(source, target):
    """Byte copy of regular files and directories; refuses links and specials."""
    source, target = Path(source), Path(target)
    target.mkdir(parents=True, exist_ok=False)
    for path in sorted(source.rglob("*")):
        rel = path.relative_to(source)
        if path.is_symlink():
            raise RunFailure(f"Symbolic link in configuration source: {path}")
        if path.is_dir():
            (target / rel).mkdir(parents=True, exist_ok=True)
        elif path.is_file():
            (target / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target / rel)
        else:
            raise RunFailure(f"Unsupported file type in configuration source: {path}")


def stat_record(path):
    path = Path(path)
    if not path.exists():
        return None
    info = path.stat()
    return {"path": str(path), "size_bytes": info.st_size, "mtime_ns": info.st_mtime_ns}


# ............................................................ provenance


def _git(*args, check=True):
    return subprocess.run(
        ["git", "--no-optional-locks", "-C", str(ROOT), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
        timeout=120,
    )


def git_provenance(sources, sidecar=None):
    """Revision, branch, porcelain status and dirty diff of the Cells checkout.

    The diff is ``git diff HEAD`` for tracked files plus the full content of
    any *untracked* executed tool file (``sources``), so the exact source used
    is reconstructible from the revision. ``sidecar`` receives the diff when it
    is too large to inline.
    """
    try:
        revision = _git("rev-parse", "HEAD").stdout.decode().strip()
        branch = _git("rev-parse", "--abbrev-ref", "HEAD").stdout.decode().strip()
        porcelain = _git("status", "--porcelain=v1", "--untracked-files=all").stdout
        tracked_diff = _git("diff", "--binary", "--no-ext-diff", "HEAD").stdout
    except (OSError, subprocess.SubprocessError) as error:
        return {"repository": str(ROOT), "error": repr(error)}
    files, untracked_diff = {}, b""
    for source in sources:
        source = Path(source).resolve()
        if not source.is_relative_to(ROOT):
            files[str(source)] = {"sha256": sha256_file(source), "tracked": None}
            continue
        rel = str(source.relative_to(ROOT))
        tracked = _git("ls-files", "--error-unmatch", "--", rel, check=False).returncode == 0
        files[rel] = {"sha256": sha256_file(source), "tracked": tracked}
        if not tracked:
            untracked_diff += _git(
                "diff", "--binary", "--no-index", "--", "/dev/null", rel, check=False
            ).stdout
    diff = tracked_diff + untracked_diff
    record = {
        "repository": str(ROOT),
        "branch": branch,
        "revision": revision,
        "status_porcelain": porcelain.decode("utf-8", "surrogateescape").splitlines(),
        "dirty": bool(porcelain.strip()),
        "executed_sources": files,
        "dirty_diff_sha256": hashlib.sha256(diff).hexdigest(),
        "dirty_diff_bytes": len(diff),
        "dirty_diff_scope": "git diff HEAD (tracked) + untracked executed sources",
    }
    if len(diff) <= INLINE_DIFF_LIMIT or sidecar is None:
        record["dirty_diff"] = diff.decode("utf-8", "surrogateescape")
    else:
        Path(sidecar).write_bytes(diff)
        record["dirty_diff_file"] = str(sidecar)
    return record


_PROBE = r"""
import hashlib, importlib.metadata as md, importlib.util as iu, json, os, platform, sys
def tree(root):
    h, n = hashlib.sha256(), 0
    for base, dirs, names in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d != "__pycache__")
        for name in sorted(names):
            if name.endswith((".pyc", ".pyo")):
                continue
            path = os.path.join(base, name)
            h.update(os.path.relpath(path, root).encode() + b"\0")
            with open(path, "rb") as f:
                h.update(f.read())
            h.update(b"\0")
            n += 1
    return {"sha256": h.hexdigest(), "files": n}
versions = {}
for name in json.loads(sys.argv[1]):
    try:
        versions[name] = md.version(name)
    except md.PackageNotFoundError:
        versions[name] = None
spec = iu.find_spec("betse")
package = os.path.dirname(spec.origin) if spec and spec.origin else None
source = sys.argv[2] if len(sys.argv) > 2 else None
print(json.dumps({
    "python": sys.version,
    "executable": sys.executable,
    "prefix": sys.prefix,
    "platform": platform.platform(),
    "versions": versions,
    "betse_package": package,
    "betse_package_tree": tree(package) if package else None,
    "betse_source_tree": tree(os.path.join(source, "betse")) if source else None,
}))
"""


def probe_environment(venv, env, betse_source=None):
    """Versions and package digests, without importing BETSE (find_spec only)."""
    argv = [str(venv / "bin/python"), "-I", "-c", _PROBE, json.dumps(VERSION_PACKAGES)]
    if betse_source is not None:
        argv.append(str(betse_source))
    done = subprocess.run(argv, env=env, capture_output=True, text=True, timeout=300, check=True)
    record = json.loads(done.stdout)
    record["venv"] = str(venv)
    if betse_source is not None:
        source = {"path": str(betse_source)}
        try:
            run = ["git", "--no-optional-locks", "-C", str(betse_source)]
            source["revision"] = subprocess.run(
                [*run, "rev-parse", "HEAD"], capture_output=True, text=True, check=True
            ).stdout.strip()
            source["status_porcelain"] = subprocess.run(
                [*run, "status", "--porcelain=v1"], capture_output=True, text=True, check=True
            ).stdout.splitlines()
        except (OSError, subprocess.SubprocessError) as error:
            source["git_error"] = repr(error)
        tree, installed = record.pop("betse_source_tree"), record["betse_package_tree"]
        source["betse_tree"] = tree
        source["installed_package_matches_source"] = bool(tree and installed and tree == installed)
        record["betse_source"] = source
    else:
        record.pop("betse_source_tree")
    return record


# ............................................................ process guard


def _proc_rss_bytes(pid):
    try:
        with open(f"/proc/{pid}/status") as stream:
            for line in stream:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) * 1024
    except OSError:
        pass
    return 0


def _group_members(pgid):
    members = []
    for name in os.listdir("/proc"):
        if not name.isdigit():
            continue
        try:
            with open(f"/proc/{name}/stat") as stream:
                fields = stream.read().rsplit(")", 1)[1].split()
        except (OSError, IndexError):
            continue
        if len(fields) > 2 and int(fields[2]) == pgid:
            members.append(int(name))
    return members


def mem_available_bytes():
    with open("/proc/meminfo") as stream:
        for line in stream:
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) * 1024
    raise RunFailure("MemAvailable not reported by /proc/meminfo")


def kill_group(pgid, grace_s=10.0):
    try:
        os.killpg(pgid, signal.SIGTERM)
    except ProcessLookupError:
        return
    deadline = time.monotonic() + grace_s
    while time.monotonic() < deadline:
        if not _group_members(pgid):
            return
        time.sleep(0.2)
    try:
        os.killpg(pgid, signal.SIGKILL)
    except ProcessLookupError:
        pass


class Guard(threading.Thread):
    """Samples RSS of the BETSE process group; kills it on a limit or timeout."""

    def __init__(self, pgid, max_rss, min_available, timeout_s, interval_s=0.25):
        super().__init__(daemon=True)
        self.pgid, self.max_rss, self.min_available = pgid, max_rss, min_available
        self.timeout_s, self.interval_s = timeout_s, interval_s
        self.done = threading.Event()
        self.start_time = time.monotonic()
        self.reason = None
        self.peak_process_rss = 0
        self.peak_group_rss = 0
        self.min_seen_available = None
        self.samples = 0

    def run(self):
        while not self.done.wait(self.interval_s):
            members = _group_members(self.pgid)
            rss = [_proc_rss_bytes(pid) for pid in members]
            available = mem_available_bytes()
            self.samples += 1
            self.peak_process_rss = max([self.peak_process_rss, *rss])
            self.peak_group_rss = max(self.peak_group_rss, sum(rss))
            if self.min_seen_available is None or available < self.min_seen_available:
                self.min_seen_available = available
            elapsed = time.monotonic() - self.start_time
            if rss and max(rss) > self.max_rss:
                self.reason = f"process RSS {max(rss)} B exceeded limit {self.max_rss} B"
            elif available < self.min_available:
                self.reason = f"host MemAvailable {available} B fell below {self.min_available} B"
            elif elapsed > self.timeout_s:
                self.reason = f"phase exceeded timeout {self.timeout_s} s"
            if self.reason:
                kill_group(self.pgid)
                return

    def stop(self):
        self.done.set()
        self.join(timeout=30)


# ............................................................ BETSE phases


def betse_env(home, threads):
    keep = ("PATH", "LANG", "LC_ALL", "LC_CTYPE", "TZ")
    env = {key: os.environ[key] for key in keep if key in os.environ}
    for sub in (".config/matplotlib", ".cache", ".local/share", "tmp"):
        (home / sub).mkdir(parents=True, exist_ok=True)
    env.update(
        HOME=str(home),
        XDG_CONFIG_HOME=str(home / ".config"),
        XDG_CACHE_HOME=str(home / ".cache"),
        XDG_DATA_HOME=str(home / ".local/share"),
        MPLCONFIGDIR=str(home / ".config/matplotlib"),
        MPLBACKEND="Agg",
        TMPDIR=str(home / "tmp"),
        PYTHONNOUSERSITE="1",
        PYTHONHASHSEED="0",
        OMP_NUM_THREADS=str(threads),
        OPENBLAS_NUM_THREADS=str(threads),
        MKL_NUM_THREADS=str(threads),
        NUMEXPR_NUM_THREADS=str(threads),
    )
    return env


def run_phase(record, phase, argv, env, cwd, logs, limits):
    """Run one phase, filling ``record`` (owned by the caller) as it proceeds."""
    stdout_path, stderr_path = logs / f"{phase}.stdout.log", logs / f"{phase}.stderr.log"
    record.update(
        argv=argv,
        cwd=str(cwd),
        stdout_log=str(stdout_path),
        stderr_log=str(stderr_path),
        started_utc=utc_now(),
        available_bytes_at_start=mem_available_bytes(),
    )
    if record["available_bytes_at_start"] < limits["min_available_bytes"]:
        raise RunFailure(f"{phase}: host MemAvailable below the guard before starting")
    with stdout_path.open("xb") as out, stderr_path.open("xb") as err:
        start = time.monotonic()
        process = subprocess.Popen(
            argv,
            cwd=cwd,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=out,
            stderr=err,
            start_new_session=True,
        )
        guard = Guard(
            process.pid,
            limits["max_rss_bytes"],
            limits["min_available_bytes"],
            limits["timeout_s"],
        )
        guard.start()
        record["pid"] = process.pid
        try:
            _, status, usage = os.wait4(process.pid, 0)
        except BaseException:
            guard.stop()
            kill_group(process.pid)
            record.update(
                interrupted_after_s=time.monotonic() - start,
                sampled_peak_process_rss_bytes=guard.peak_process_rss,
                guard_reason=guard.reason,
            )
            raise
        wall = time.monotonic() - start
        process.returncode = os.waitstatus_to_exitcode(status)
        guard.stop()
    leftovers = _group_members(process.pid)
    if leftovers:
        kill_group(process.pid, grace_s=2.0)
    record.update(
        finished_utc=utc_now(),
        wall_time_s=wall,
        exit_code=process.returncode,
        peak_rss_bytes=usage.ru_maxrss * 1024,
        peak_rss_source="os.wait4 ru_maxrss of the phase process",
        sampled_peak_process_rss_bytes=guard.peak_process_rss,
        sampled_peak_group_rss_bytes=guard.peak_group_rss,
        rss_samples=guard.samples,
        min_sampled_available_bytes=guard.min_seen_available,
        cpu_user_s=usage.ru_utime,
        cpu_system_s=usage.ru_stime,
        guard_reason=guard.reason,
        leftover_group_processes=leftovers,
        stdout_bytes=stdout_path.stat().st_size,
        stderr_bytes=stderr_path.stat().st_size,
    )
    return record


def _signal_handler(signum, _frame):
    raise Interrupted(f"runner received signal {signum}")


def cmd_run(args):
    out = resolve_out(args.out)
    if out.exists():
        raise SystemExit(f"Refusing existing output directory: {out}")
    venv = resolve_venv(args.venv)
    source = Path(args.config_dir).absolute()
    config_file = relative_name(args.config_file)
    if not (source / config_file).is_file():
        raise SystemExit(f"Configuration file not found: {source / config_file}")
    phases = list(args.phases)
    if [p for p in PHASES if p in phases] != phases:
        raise SystemExit("Phases must be an ordered subset of seed, init, sim")
    cpus = parse_cpus(args.cpus)
    threads = args.threads or len(cpus)
    betse_source = Path(args.betse_source).absolute() if args.betse_source else None
    input_records = [Path(p).absolute() for p in args.input_record]

    out.mkdir(parents=True)
    logs, home, config = out / "logs", out / "home", out / "config"
    logs.mkdir()
    home.mkdir()
    env = betse_env(home, threads)
    global_options = ["--log-level", args.log_level] + (["--headless"] if args.headless else [])
    record = {
        "kind": KIND,
        "status": "running",
        "case": args.case,
        "started_utc": utc_now(),
        "command": sys.argv,
        "runner_python": sys.version,
        "output_root": str(output_root()),
        "run_directory": str(out),
        "phases_requested": phases,
        "limits": {
            "cpus": cpus,
            "threads": threads,
            "max_rss_bytes": int(args.max_rss_gib * GIB),
            "min_available_bytes": int(args.min_available_gib * GIB),
            "timeout_s": args.timeout_s,
        },
        "betse_global_options": global_options,
        "environment": env,
        "phases": {},
    }
    previous = {sig: signal.signal(sig, _signal_handler) for sig in SIGNALS}
    real_log = Path(os.path.expanduser("~")) / ".betse/betse.log"
    try:
        record["provenance"] = git_provenance([Path(__file__)], out / "git-dirty.diff")
        record["betse_environment"] = probe_environment(venv, env, betse_source)
        copy_tree(source, config)
        config_inventory = inventory(config)
        record["config"] = {
            "source_directory": str(source),
            "directory": str(config),
            "config_file": str(config_file),
            "config_file_sha256": config_inventory[str(config_file)]["sha256"],
            "files": config_inventory,
        }
        record["input_records"] = {
            str(p): {"sha256": sha256_file(p), "size_bytes": p.stat().st_size}
            for p in input_records
        }
        record["real_home_betse_log_before"] = stat_record(real_log)
        write_json(out / "inputs.json", record)
        yaml_path = config / config_file
        taskset = shutil.which("taskset")
        if taskset is None:
            raise RunFailure("taskset is required for CPU affinity")
        limits = record["limits"]
        for phase in phases:
            argv = [taskset, "-c", ",".join(map(str, cpus)), str(venv / "bin/betse")]
            argv += [*global_options, phase, str(yaml_path)]
            before = inventory(config)
            result = record["phases"][phase] = {}
            run_phase(result, phase, argv, env, yaml_path.parent, logs, limits)
            result["outputs"] = inventory_changes(before, inventory(config))
            result["pickles"] = sorted(
                k
                for k in result["outputs"]["created"] | result["outputs"]["modified"]
                if k.endswith(".betse.gz")
            )
            if result["guard_reason"]:
                raise RunFailure(f"{phase}: guard stopped BETSE: {result['guard_reason']}")
            if result["exit_code"] != 0:
                raise RunFailure(f"{phase}: betse exited with code {result['exit_code']}")
            if not result["pickles"]:
                raise RunFailure(f"{phase}: no BETSE pickle (*.betse.gz) was written")
        record["checks"] = run_checks(record, config, home, real_log)
        failed = [name for name, row in record["checks"].items() if row.get("pass") is False]
        if failed:
            raise RunFailure(f"run checks failed: {failed}")
        record["status"] = "complete"
        record["finished_utc"] = utc_now()
        write_json(out / "result.json", record)
        print(json.dumps({"status": "complete", "result": str(out / "result.json")}))
        return 0
    except (Exception, Interrupted) as error:
        record["status"] = "failed"
        record["finished_utc"] = utc_now()
        record["error"] = {"type": type(error).__name__, "message": str(error)}
        record["outputs_preserved"] = True
        try:
            record.setdefault("checks", run_checks(record, config, home, real_log))
        except Exception as check_error:  # noqa: BLE001 - keep the primary failure
            record["checks_error"] = repr(check_error)
        write_json(out / "failure.json", record)
        print(json.dumps({"status": "failed", "failure": str(out / "failure.json")}))
        return 1
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)


def run_checks(record, config, home, real_log):
    checks = {}
    if "config" in record and config.is_dir():
        now = inventory(config)
        inputs = record["config"]["files"]
        changed = sorted(k for k, v in inputs.items() if now.get(k) != v)
        checks["config_inputs_unchanged"] = {"pass": not changed, "changed": changed}
    log = home / ".betse/betse.log"
    text = log.read_text(errors="replace") if log.is_file() else ""
    checks["isolated_home"] = {
        "pass": log.is_file() and log.stat().st_size > 0,
        "home": str(home),
        "betse_log": str(log),
        # BETSE logs where it saved its pickles, i.e. inside this run's config copy.
        "betse_log_mentions_run_config_dir": str(config) in text,
        "files": {
            str(p.relative_to(home)): p.stat().st_size
            for p in sorted(home.rglob("*"))
            if p.is_file() and not p.is_symlink()
        },
    }
    before = record.get("real_home_betse_log_before")
    after = stat_record(real_log)
    checks["real_home_betse_log"] = {
        "before": before,
        "after": after,
        "unchanged": before == after,
        "note": "informational: other processes may write there; BETSE here had HOME=" + str(home),
    }
    return checks


# ............................................................ prepare


def _apply_overrides(conf, overrides):
    conf = copy.deepcopy(conf)
    for path, value in overrides:
        target = conf
        for key in path[:-1]:
            target = target[key]
        if path[-1] not in target:
            raise RunFailure(f"Unknown YAML option: {path}")
        target[path[-1]] = value
    return conf


def _rewrite_assets(value, assets, yaml_dir):
    if isinstance(value, dict):
        return {k: _rewrite_assets(v, assets, yaml_dir) for k, v in value.items()}
    if isinstance(value, list):
        return [_rewrite_assets(v, assets, yaml_dir) for v in value]
    if isinstance(value, str) and value.startswith(ASSET_PREFIXES):
        return os.path.relpath(assets / value, yaml_dir)
    return value


def cmd_prepare(args):
    out = resolve_out(args.out)
    if out.exists():
        raise SystemExit(f"Refusing existing output directory: {out}")
    base = Path(args.base).absolute()
    yaml_name = relative_name(args.yaml)
    if not (base / yaml_name).is_file():
        raise SystemExit(f"Base YAML not found: {base / yaml_name}")
    assets_dest = Path(args.assets_dest)
    if assets_dest.is_absolute() or ".." in assets_dest.parts:
        raise SystemExit("--assets-dest must be relative")
    yaml_dest = relative_name(args.yaml_dest) if args.yaml_dest else assets_dest / yaml_name
    record = {
        "kind": PREPARE_KIND,
        "status": "running",
        "started_utc": utc_now(),
        "command": sys.argv,
        "python": sys.version,
        "base_directory": str(base),
        "base_yaml": str(yaml_name),
        "assets_dest": str(assets_dest),
        "yaml_dest": str(yaml_dest),
    }
    out.mkdir(parents=True)
    try:
        sidecar = out.parent / f"{out.name}.prepare-dirty.diff"
        record["provenance"] = git_provenance([Path(__file__)], sidecar)
        record["base_files"] = inventory(base)
        if assets_dest == Path("."):
            _copy_into(base, out)
        else:
            copy_tree(base, out / assets_dest)
        if args.overrides:
            from ruamel.yaml import YAML
            from ruamel.yaml import __version__ as ruamel_version

            overrides_path = Path(args.overrides).absolute()
            declared = json.loads(overrides_path.read_text())
            overrides = declared[args.overrides_key] if args.overrides_key else declared
            yaml = YAML(typ="safe")
            # As alignment.py: block style, so BETSE's round-trip loader accepts the keys.
            yaml.default_flow_style = False
            with (base / yaml_name).open() as handle:
                conf = _apply_overrides(yaml.load(handle), overrides)
            target = out / yaml_dest
            target.parent.mkdir(parents=True, exist_ok=True)
            conf = _rewrite_assets(conf, out / assets_dest, target.parent)
            with target.open("x") as handle:
                yaml.dump(conf, handle)
            record["overrides"] = {
                "file": str(overrides_path),
                "file_sha256": sha256_file(overrides_path),
                "key": args.overrides_key,
                "values": overrides,
                "procedure": "ruamel safe load, declared overrides, asset paths relative "
                "to the written YAML, safe dump with default_flow_style=False",
                "ruamel_yaml": ruamel_version,
            }
        elif yaml_dest != assets_dest / yaml_name:
            raise RunFailure("--yaml-dest without --overrides is not a byte copy")
        if args.replace:
            if args.overrides:
                raise RunFailure("--replace and --overrides are exclusive")
            target = out / yaml_dest
            before = target.read_bytes()
            after = before
            for old, new in args.replace:
                if after.count(old.encode()) != 1:
                    raise RunFailure(f"--replace text must occur exactly once: {old!r}")
                after = after.replace(old.encode(), new.encode(), 1)
            target.unlink()  # the copy may be read-only; write a fresh file
            target.write_bytes(after)
            record["replacements"] = {
                "pairs": args.replace,
                "before_sha256": hashlib.sha256(before).hexdigest(),
                "after_sha256": hashlib.sha256(after).hexdigest(),
                "changed_keys": _changed_keys(before, after),
                "procedure": "exact single-occurrence text replacement; all other bytes kept",
            }
        record["yaml_sha256"] = sha256_file(out / yaml_dest)
        if args.expect_yaml_sha256:
            record["expected_yaml_sha256"] = args.expect_yaml_sha256
            record["expected_yaml_sha256_source"] = args.expect_source
            if record["yaml_sha256"] != args.expect_yaml_sha256:
                raise RunFailure("Prepared YAML differs from the expected SHA-256")
        for path in out.rglob("*"):
            if path.is_file():
                path.chmod(stat.S_IMODE(path.stat().st_mode) & ~0o222)
        record["files"] = inventory(out)
        record["status"] = "complete"
        record["finished_utc"] = utc_now()
        write_json(out.parent / f"{out.name}.prepare.json", record)
        print(json.dumps({"status": "complete", "config_dir": str(out), "yaml": str(yaml_dest)}))
        return 0
    except Exception as error:
        record["status"] = "failed"
        record["error"] = {"type": type(error).__name__, "message": str(error)}
        write_json(out.parent / f"{out.name}.prepare-failure.json", record)
        print(json.dumps({"status": "failed", "config_dir": str(out)}))
        return 1


def _changed_keys(before, after):
    """Parsed-YAML differences [{path, before, after}] between two config texts."""
    try:
        from ruamel.yaml import YAML
    except ImportError:
        return "unchecked: ruamel.yaml not importable"
    yaml = YAML(typ="safe")
    changes = []

    def walk(a, b, path):
        if isinstance(a, dict) and isinstance(b, dict):
            for key in sorted(set(a) | set(b), key=str):
                walk(a.get(key), b.get(key), [*path, key])
        elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
            for i, (x, y) in enumerate(zip(a, b, strict=True)):
                walk(x, y, [*path, i])
        elif type(a) is not type(b) or a != b:
            changes.append({"path": path, "before": a, "after": b})

    walk(yaml.load(before.decode()), yaml.load(after.decode()), [])
    return changes


def _copy_into(base, out):
    for path in sorted(base.iterdir()):
        if path.is_dir() and not path.is_symlink():
            copy_tree(path, out / path.name)
        elif path.is_file() and not path.is_symlink():
            shutil.copy2(path, out / path.name)
        else:
            raise RunFailure(f"Unsupported entry in base directory: {path}")


# ............................................................ CLI


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="run betse seed/init/sim on a copy of a config dir")
    run.add_argument("--config-dir", required=True, help="prepared BETSE config directory")
    run.add_argument("--config-file", default="sim_config.yaml", help="YAML inside it")
    run.add_argument("--out", required=True, help="fresh run dir (relative: output root)")
    run.add_argument("--venv", help="BETSE venv (default $BETSE_VENV or root/venv-betse)")
    run.add_argument("--case", help="case label recorded in the result")
    run.add_argument("--phases", nargs="+", default=list(PHASES), choices=PHASES)
    run.add_argument("--cpus", default="1,2", help="taskset CPU list (default 1,2)")
    run.add_argument("--threads", type=int, help="BLAS/OpenMP threads (default: #cpus)")
    run.add_argument("--max-rss-gib", type=float, default=4.0)
    run.add_argument("--min-available-gib", type=float, default=8.0)
    run.add_argument("--timeout-s", type=float, default=4 * 3600.0, help="per phase")
    run.add_argument("--log-level", default="info")
    run.add_argument("--no-headless", dest="headless", action="store_false")
    run.add_argument("--betse-source", help="BETSE source checkout to compare and record")
    run.add_argument(
        "--input-record",
        action="append",
        default=[],
        help="preparation record(s) to hash into the run inputs",
    )
    run.set_defaults(func=cmd_run)

    prep = sub.add_parser("prepare", help="build a fresh config dir (needs ruamel.yaml)")
    prep.add_argument("--base", required=True, help="base BETSE data dir (YAML + assets)")
    prep.add_argument("--yaml", default="sim_config.yaml", help="base YAML inside --base")
    prep.add_argument("--out", required=True, help="fresh config dir (relative: output root)")
    prep.add_argument("--overrides", help="JSON with [key path, value] pairs")
    prep.add_argument("--overrides-key", default="yaml_overrides")
    prep.add_argument("--assets-dest", default=".", help="where --base is copied inside out")
    prep.add_argument("--yaml-dest", help="where the overridden YAML is written inside out")
    prep.add_argument(
        "--replace",
        nargs=2,
        action="append",
        metavar=("OLD", "NEW"),
        help="replace exactly one occurrence of OLD by NEW in the copied YAML (repeatable)",
    )
    prep.add_argument("--expect-yaml-sha256", help="fail unless the YAML has this SHA-256")
    prep.add_argument("--expect-source", help="where the expected SHA-256 was recorded")
    prep.set_defaults(func=cmd_prepare)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
