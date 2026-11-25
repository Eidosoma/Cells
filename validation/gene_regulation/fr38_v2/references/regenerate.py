"""Regenerate the references under several PYTHONHASHSEED values and check them bitwise.

    python -B regenerate.py --work DIR [--seeds 0,1,4242] [--cpus 6,7,22,23] [--publish]

Each (seed, family) runs the writer in its own process, pinned to one CPU, with every BLAS
pinned to one thread (OMP_NUM_THREADS, OPENBLAS_NUM_THREADS and MKL_NUM_THREADS = 1). The
working tree must be clean, since each file's provenance records the revision. After all runs,
every reference_*.json must be byte-identical across the seeds (amendment 2, Q5). With
--publish, the first seed's files are copied into out/, and out/SHA256SUMS, out/provenance.json
and out/run_times.json are written after the check.
"""

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
WRITER = os.path.join(HERE, "fr38v2_writer.py")
FAMILIES = ["B", "AF", "AN", "C", "D", "invented"]      # longest first, for packing


def _git(*args):
    return subprocess.run(["git", *args], cwd=HERE, capture_output=True, text=True,
                          check=True).stdout


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _platform():
    cpu = "unknown"
    try:
        with open("/proc/cpuinfo", encoding="ascii", errors="replace") as fh:
            for line in fh:
                if line.startswith("model name"):
                    cpu = line.split(":", 1)[1].strip()
                    break
    except OSError:
        pass
    fi = np.finfo(np.longdouble)
    return {
        "machine": platform.machine(),
        "processor": cpu,
        "operating_system": platform.platform(),
        "libc": " ".join(platform.libc_ver()),
        "python": sys.version,
        "numpy": np.__version__,
        "long_double": (f"x86 extended precision: {fi.nmant + 1}-bit significand, {fi.nexp}-bit "
                        f"exponent, eps {fi.eps!r}, {np.dtype(np.longdouble).itemsize} bytes "
                        f"stored"),
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True)
    ap.add_argument("--seeds", default="0,1,4242")
    ap.add_argument("--cpus", default="6,7,22,23")
    ap.add_argument("--families", default=",".join(FAMILIES))
    ap.add_argument("--publish", action="store_true")
    a = ap.parse_args(argv)
    seeds = [int(s) for s in a.seeds.split(",")]
    cpus = a.cpus.split(",")
    fams = a.families.split(",")
    dirty = _git("status", "--porcelain=v1", "--untracked-files=all").strip()
    if dirty:
        raise SystemExit("refused: the working tree is not clean:\n" + dirty)
    rev = _git("rev-parse", "HEAD").strip()
    env = dict(os.environ, OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1",
               PYTHONDONTWRITEBYTECODE="1")
    jobs = [(s, f) for f in fams for s in seeds]
    running, free, done = [], list(cpus), []
    t0 = time.time()
    while jobs or running:
        while jobs and free:
            seed, fam = jobs.pop(0)
            cpu = free.pop(0)
            out = os.path.join(a.work, f"seed_{seed}", fam)
            os.makedirs(out, exist_ok=True)
            log = open(os.path.join(a.work, f"seed_{seed}_{fam}.log"), "w")
            p = subprocess.Popen(["taskset", "-c", cpu, sys.executable, "-B", WRITER, "--out", out,
                                  "--families", fam],
                                 env=dict(env, PYTHONHASHSEED=str(seed)), stdout=log,
                                 stderr=subprocess.STDOUT, cwd=HERE)
            running.append((p, cpu, seed, fam, log))
        time.sleep(2)
        for item in list(running):
            p, cpu, seed, fam, log = item
            if p.poll() is not None:
                log.close()
                running.remove(item)
                free.append(cpu)
                if p.returncode != 0:
                    raise SystemExit(f"refused: seed {seed} family {fam} failed "
                                     f"(code {p.returncode}); see its log")
                done.append((seed, fam))
                print(f"done seed {seed} {fam} at {time.time() - t0:.0f} s", flush=True)
    if _git("rev-parse", "HEAD").strip() != rev or _git("status", "--porcelain=v1").strip():
        raise SystemExit("refused: the checkout changed during the regeneration")

    shas = {s: {} for s in seeds}
    for s in seeds:
        for fam in fams:
            name = f"reference_{fam}.json"
            shas[s][name] = _sha(os.path.join(a.work, f"seed_{s}", fam, name))
    first = shas[seeds[0]]
    identical = all(shas[s] == first for s in seeds)
    for name in sorted(first):
        same = all(shas[s][name] == first[name] for s in seeds)
        print(f"{name}: {'identical' if same else 'DIFFERS'} across seeds {seeds}: {first[name]}")
    if not identical:
        raise SystemExit("refused: the files are not bitwise identical across seeds")

    times = {}
    for s in seeds:
        times[str(s)] = {}
        for fam in fams:
            with open(os.path.join(a.work, f"seed_{s}", fam, "run_times.json")) as fh:
                times[str(s)].update(json.load(fh)["wall_time_s_per_family"])
    if a.publish:
        out = os.path.join(HERE, "out")
        os.makedirs(out, exist_ok=True)
        for name in sorted(first):
            fam = name[len("reference_"):-len(".json")]
            shutil.copyfile(os.path.join(a.work, f"seed_{seeds[0]}", fam, name),
                            os.path.join(out, name))
            assert _sha(os.path.join(out, name)) == first[name]
        with open(os.path.join(out, "SHA256SUMS"), "w", encoding="ascii", newline="\n") as fh:
            for name in sorted(first):
                fh.write(f"{first[name]}  {name}\n")
        prov = {
            "generating_commit": rev,
            "dirty_paths_at_generation": [],
            "hash_seeds_checked": seeds,
            "bitwise_identical_across_seeds": True,
            "files_checked": sorted(first),
            "sha256": first,
            "blas_threads": {"OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1",
                             "MKL_NUM_THREADS": "1"},
            "platform": _platform(),
            "note": ("long double is the same bits only on one platform; the bitwise check "
                     "holds on the platform recorded here (amendment 2, Q7)"),
        }
        with open(os.path.join(out, "provenance.json"), "w", encoding="ascii",
                  newline="\n") as fh:
            fh.write(json.dumps(prov, sort_keys=True, indent=1) + "\n")
        with open(os.path.join(out, "run_times.json"), "w", encoding="ascii",
                  newline="\n") as fh:
            fh.write(json.dumps({"wall_time_s_per_seed_and_family": times,
                                 "note": "wall times; excluded from the bitwise check"},
                                sort_keys=True, indent=1) + "\n")
        print("published into", out)


if __name__ == "__main__":
    main()
