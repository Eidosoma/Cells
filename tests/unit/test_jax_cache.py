"""This VM's shared JAX compilation cache for development runs (D321 step 1): scripts/jax_cache.py,
scripts/run_detached.sh --jax-cache and scripts/with_jax_cache.sh. Host only, about 1 s: no JAX, no
unit started (run_detached.sh --dry-run), every folder in tmp_path (CELLS_JAX_CACHE_ROOT).

- One folder per jaxlib version and CPU: another jaxlib or another CPU's flags is another folder.
- The opt-in environment is the qualified mode (every compile written) on the CPU only.
- run_detached.sh disables the cache in every unit without --jax-cache, after the caller's --env, so
  it wins. --jax-cache gives the opt-in environment, and is refused with a visible GPU.
- with_jax_cache.sh gives one command the same environment, and refuses a visible GPU.
- The sweep removes other folders, torn entries old enough (never a young one, which may still be
  being written), and above the cap the least recently read entries down to 90% of it. It reads
  without touching an access time, only entries written since the last sweep, and a dry run
  removes nothing.
"""

import importlib.util
import json
import os
import subprocess
import time
import zlib
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
spec = importlib.util.spec_from_file_location("jax_cache", SCRIPTS / "jax_cache.py")
jc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(jc)
needs_venv = pytest.mark.skipif(not jc.PYTHON.exists(), reason="no venv-cpu (its jaxlib names the folder)")
CPUINFO = ("processor\t: 0\nvendor_id\t: GenuineIntel\ncpu family\t: 6\nmodel\t\t: 85\n"
           "flags\t\t: fpu sse avx512f avx512_vnni\n\nprocessor\t: 1\nvendor_id\t: GenuineIntel\n")


def venv(tmp_path, version):
    meta = (tmp_path / f"venv-{version}" / "lib" / "python3.13" / "site-packages"
            / f"jaxlib-{version}.dist-info" / "METADATA")
    meta.parent.mkdir(parents=True, exist_ok=True)
    meta.write_text(f"Metadata-Version: 2.1\nName: jaxlib\nVersion: {version}\n")
    return tmp_path / f"venv-{version}" / "bin" / "python"


def test_one_folder_per_jaxlib_version_and_cpu(tmp_path):
    info, other = tmp_path / "cpuinfo", tmp_path / "cpuinfo-2"
    info.write_text(CPUINFO)
    other.write_text(CPUINFO.replace(" avx512_vnni", ""))
    one = jc.folder(tmp_path / "root", venv(tmp_path, "0.11.1"), info)
    assert one.parent == tmp_path / "root" and one.name.startswith("cpu-jaxlib0.11.1-intel-6-85-")
    assert jc.folder(tmp_path / "root", venv(tmp_path, "0.12.0"), info) != one
    assert jc.folder(tmp_path / "root", venv(tmp_path, "0.11.1"), other) != one
    assert jc.environment(one) == {
        "JAX_ENABLE_COMPILATION_CACHE": "true", "JAX_COMPILATION_CACHE_DIR": str(one),
        "JAX_PERSISTENT_CACHE_MIN_COMPILE_TIME_SECS": "0",
        "JAX_PERSISTENT_CACHE_MIN_ENTRY_SIZE_BYTES": "0", "JAX_PLATFORMS": "cpu",
        "CUDA_VISIBLE_DEVICES": "", "CELLS_JAX_CACHE": str(one)}


def dry(*args, **env):
    done = subprocess.run(["bash", str(SCRIPTS / "run_detached.sh"), "t", "1G", "--dry-run", *args,
                           "--", "true"], capture_output=True, text=True, timeout=60,
                          env=dict(os.environ, **env))
    return done.returncode, done.stdout.splitlines(), done.stderr


@needs_venv
def test_run_detached_disables_the_cache_unless_a_unit_opts_in(tmp_path):
    code, argv, _ = dry("--env", "JAX_ENABLE_COMPILATION_CACHE=true", "--env", "X=1")
    sets = [a for a in argv if a.startswith("--setenv=")]
    assert code == 0 and "--setenv=X=1" in sets
    assert sets[-1] == "--setenv=JAX_ENABLE_COMPILATION_CACHE=false"  # After the caller's: it wins.
    code, argv, _ = dry("--jax-cache", CELLS_JAX_CACHE_ROOT=str(tmp_path))
    want = {f"--setenv={k}={v}" for k, v in jc.environment(jc.folder(tmp_path)).items()}
    assert code == 0 and want <= set(argv), argv
    assert "--setenv=JAX_ENABLE_COMPILATION_CACHE=false" not in argv
    assert not any(tmp_path.iterdir())  # A dry run makes no folder.
    for bad in ("CUDA_VISIBLE_DEVICES=0", "JAX_PLATFORMS=cuda"):
        code, argv, err = dry("--jax-cache", "--env", bad, CELLS_JAX_CACHE_ROOT=str(tmp_path))
        assert code == 2 and "CPU-only" in err and not argv
    code, argv, _ = dry("--jax-cache", "--env", "JAX_PLATFORMS=cpu", "--env", "CUDA_VISIBLE_DEVICES=",
                        CELLS_JAX_CACHE_ROOT=str(tmp_path))
    assert code == 0


@needs_venv
def test_with_jax_cache_gives_one_command_the_opt_in_and_refuses_a_gpu(tmp_path):
    base = {k: v for k, v in os.environ.items() if k not in ("CUDA_VISIBLE_DEVICES", "JAX_PLATFORMS")}
    base["CELLS_JAX_CACHE_ROOT"] = str(tmp_path)

    def wrapped(**env):
        return subprocess.run(["bash", str(SCRIPTS / "with_jax_cache.sh"), "env"], capture_output=True,
                              text=True, timeout=60, env=dict(base, **env))

    done = wrapped()
    assert done.returncode == 0, done.stderr
    seen = dict(line.split("=", 1) for line in done.stdout.splitlines() if "=" in line)
    folder = jc.folder(tmp_path)
    assert {k: seen.get(k) for k in jc.environment(folder)} == jc.environment(folder)
    assert folder.is_dir()
    for bad in ({"CUDA_VISIBLE_DEVICES": "0"}, {"JAX_PLATFORMS": "gpu"}):
        done = wrapped(**bad)
        assert done.returncode == 2 and "CPU-only" in done.stderr and not done.stdout


def entry(folder, name, data, age, read_ago=None):
    """A cache entry written AGE seconds ago and last read READ_AGO seconds ago (default: AGE)."""
    path = folder / f"{name}-{'0' * 64}-cache"
    path.write_bytes(data)
    now = time.time()
    os.utime(path, (now - (age if read_ago is None else read_ago), now - age))
    return path


def test_the_sweep_keeps_one_folder_drops_torn_entries_and_caps_by_last_read(tmp_path):
    root = tmp_path / "root"
    current, other = root / "cpu-jaxlib0.11.1-intel-6-85-aaaaaaaa", root / "cpu-jaxlib0.10.0-x"
    current.mkdir(parents=True)
    other.mkdir()
    good = zlib.compress(os.urandom(4000))
    size = len(good)
    a = entry(current, "jit_a", good, 7200, read_ago=3 * 86400)
    b = entry(current, "jit_b", good, 7200, read_ago=86400)
    c = entry(current, "jit_c", good, 7200, read_ago=0)
    torn_old, torn_young = entry(current, "jit_t", good[:-9], 7200), entry(current, "jit_y", good[:-9], 5)
    atimes = {p: p.stat().st_atime_ns for p in (a, b, c)}

    dry_run = jc.sweep(root, current, cap=10**9, dry_run=True)
    assert dry_run["removed_folders"] == [other.name] and dry_run["removed_torn"] == [torn_old.name]
    assert other.is_dir() and torn_old.exists()
    report = jc.sweep(root, current, cap=10**9)
    assert not other.exists() and not torn_old.exists() and torn_young.exists()
    assert report["removed_lru"] == 0 and report["checked"] == 4
    assert {p: p.stat().st_atime_ns for p in (a, b, c)} == atimes  # Read without touching them.
    assert jc.sweep(root, current, cap=10**9, since=time.time())["checked"] == 0

    # Above the cap: the least recently read first (a, then b), down to 90% of it.
    report = jc.sweep(root, current, cap=int(2.5 * size))
    assert report["removed_lru"] == 2 and not a.exists() and not b.exists()
    assert c.exists() and torn_young.exists() and report["bytes_after"] <= 0.9 * 2.5 * size


def test_the_sweep_command_records_each_sweep_and_where_its_checks_reached(tmp_path):
    root, py = tmp_path / "root", venv(tmp_path, "0.11.1")
    folder = jc.folder(root, py)
    folder.mkdir(parents=True)
    entry(folder, "jit_a", zlib.compress(b"a" * 100), 7200)
    assert jc.main(["sweep", "--root", str(root), "--python", str(py), "--cap", "1G"]) == 0
    first = json.loads((root / "sweep.jsonl").read_text().splitlines()[-1])
    assert first["checked"] == 1 and first["entries_after"] == 1
    assert jc.main(["sweep", "--root", str(root), "--python", str(py), "--cap", "1G"]) == 0
    assert json.loads((root / "sweep.jsonl").read_text().splitlines()[-1])["checked"] == 0
