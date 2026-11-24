"""Generate FR-45's reference files (SPEC.md §5) from SPEC.md and CRITERIA.md alone.

  OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONHASHSEED=0 \
  taskset -c 6 python validation/fr45/references/run_references.py \
      --spec-root <copy>/spec --spec-sums <copy>/SHA256SUMS-...txt --spec-label <tag> --out <dir>

It refuses to run unless BLAS is pinned to one thread, the spec copy matches its sums file,
SPEC.md's rows match the transcribed worlds, and (without --allow-dirty) the checkout is clean
with no untracked files. It writes the reference files (SPEC.md §5; ten from amendment 2) and
accuracy.json into --out,
which must be new or empty; run-specific facts (seed, CPU, timings) go to run.log only, so the
compared outputs are identical across hash seeds and cores. ``--sample`` writes the invented
format sample instead.
"""

from __future__ import annotations

import os
import sys

_PIN = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")
if __name__ == "__main__":
    bad = [v for v in _PIN if os.environ.get(v) != "1"]
    if bad:
        sys.exit(f"refused: BLAS is not pinned to one thread ({', '.join(bad)} must be 1)")

import argparse  # noqa: E402
import hashlib  # noqa: E402
import pathlib  # noqa: E402
import subprocess  # noqa: E402
import time  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(HERE), *args], capture_output=True, text=True, check=True
    ).stdout


def checkout_state() -> tuple[str, bool, list[str]]:
    rev = _git("rev-parse", "HEAD").strip()
    status = _git("status", "--porcelain", "--untracked-files=all")
    dirty = [line for line in status.split("\n") if line.strip()]
    return rev, not dirty, dirty


def verify_spec(spec_root: pathlib.Path, sums: pathlib.Path) -> list[str]:
    """Every file the sums file lists must hash to its listed value (read at run time)."""
    checked = []
    for line in sums.read_text(encoding="utf-8").split("\n"):
        if not line.strip():
            continue
        digest, rel = line.split(None, 1)
        rel = rel.strip().lstrip("*")
        path = (spec_root / rel).resolve()
        got = hashlib.sha256(path.read_bytes()).hexdigest()
        if got != digest:
            raise SystemExit(f"refused: {rel} does not match {sums.name}")
        checked.append(rel[2:] if rel.startswith("./") else rel)
    if not any(c.endswith("SPEC.md") for c in checked) or not any(
        c.endswith("CRITERIA.md") for c in checked
    ):
        raise SystemExit("refused: the sums file must cover SPEC.md and CRITERIA.md")
    return checked


def blas_threads() -> list[int]:
    from threadpoolctl import threadpool_info

    return sorted({int(p.get("num_threads", 0)) for p in threadpool_info()})


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--spec-root", required=True, type=pathlib.Path)
    ap.add_argument("--spec-sums", required=True, type=pathlib.Path)
    ap.add_argument("--spec-label", required=True)
    ap.add_argument("--out", required=True, type=pathlib.Path)
    ap.add_argument(
        "--allow-dirty", action="store_true", help="development runs only; marked in provenance"
    )
    ap.add_argument("--only", default="", help="comma-separated world ids (development)")
    ap.add_argument("--sample", action="store_true", help="write the invented format sample only")
    ap.add_argument(
        "--profile",
        default="reference",
        choices=("reference", "reference50"),
        help="working precision: reference (70 digits) or reference50 (the first 50-digit profile)",
    )
    args = ap.parse_args(argv)

    sys.path.insert(0, str(HERE))
    import fr45ref_worlds as WL
    import fr45ref_writer as WR
    import numpy
    import scipy

    threads = blas_threads()
    if threads and threads != [1]:
        raise SystemExit(f"refused: BLAS pools report {threads} threads")
    out = args.out
    if out.exists() and any(out.iterdir()):
        raise SystemExit(f"refused: {out} is not empty")
    out.mkdir(parents=True, exist_ok=True)
    log_lines = []

    def log(msg):
        line = f"[{time.strftime('%H:%M:%S')}] {msg}"
        log_lines.append(line)
        print(line, flush=True)

    t0 = time.perf_counter()
    if args.sample:
        payload = WR.build_sample()
        (out / "format_sample_INVENTED.json").write_text(WR.dumps(payload), encoding="utf-8")
        log("format sample written")
        return 0

    rev, clean, dirty = checkout_state()
    if not clean and not args.allow_dirty:
        raise SystemExit(
            "refused: the checkout has uncommitted or untracked files:\n" + "\n".join(dirty)
        )
    checked = verify_spec(args.spec_root, args.spec_sums)
    spec_md = None
    for rel in checked:
        if rel.endswith("SPEC.md"):
            spec_md = (args.spec_root / rel).read_text(encoding="utf-8")
    rows = WL.check_against_spec(spec_md)
    log(
        f"revision {rev} clean={clean}; spec verified against {args.spec_sums.name}; "
        f"{len(rows)} SPEC rows matched"
    )
    spec = {
        "label": args.spec_label,
        "files": checked,
        "verified_against": args.spec_sums.name,
        "rows_matched": len(rows),
    }
    prov = WR.make_provenance(rev, clean, spec, args.profile)
    if not clean:
        prov["dirty_paths"] = dirty
    only = [w for w in args.only.split(",") if w] or None
    files, acc = WR.build_all(prov, args.profile, only=only, log=log)
    for name, payload in files.items():
        (out / name).write_text(WR.dumps(payload), encoding="utf-8")
    acc["provenance"] = prov
    (out / "accuracy.json").write_text(WR.dumps(acc), encoding="utf-8")
    log(f"wrote {len(files)} reference files and accuracy.json in {time.perf_counter() - t0:.1f} s")
    log(
        f"python {sys.version.split()[0]} numpy {numpy.__version__} scipy {scipy.__version__} "
        f"PYTHONHASHSEED={os.environ.get('PYTHONHASHSEED', '(unset)')} "
        f"cpus={sorted(os.sched_getaffinity(0))} blas_threads={threads}"
    )
    (out / "run.log").write_text("\n".join(log_lines) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
