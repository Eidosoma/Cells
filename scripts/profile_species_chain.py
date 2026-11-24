"""FR-43 part 1's performance report (C1.4): the chain world on the CPU, one figure per process.

FR-43 asks, at one declared accuracy, for the compile time, the time per simulated second after
compilation and the peak memory, with the device and precision, at 16 rows (the control), 32, 256
and 1,024 (D347's gap 2, D365). This runs the engine as the tree it runs from holds it, nothing
patched (the species cap, the fold's gate and the trace budget are the tree's), on FR-43's chain
(tests/species_cap_fixtures.chain_world, the species-cap tests' world and the design probe's;
docs/FR43_SHARED_INVENTORIES_DESIGN.md §1.2): by default dt 5 ms over 2 s (400 steps), observed
every 0.25 s, through the runner (jit) with every host check on every row.

Engine models it runs: resolved_pump_composite@1 over resolved_pump_tissue@3, with
local_species_reactions@1 (its links ideal_detailed_balance_mass_action@1), the solver
imex_ars222_face_electromigration@1 and the field solver capacitive_reduction_gauged_damped_newton@2
(each record lists them as its definition names them).

  run --rows N --out FILE [--dt S] [--end S] [--every S]
      One figure, in this process: the definition's build and parse seconds; the runner's own
      timings (compile, execute, host checks); seconds per simulated second (execute over the
      horizon) and ms per step; the process's peak RSS after the parse and after the run (read
      before the closed form is computed); the accuracy reached (the error and the plant over the
      largest amount, the heat residual: tests/species_cap_fixtures.chain_checks) and the ledgers'
      diagnostics; how busy the timed cores and their siblings were during the run; the
      environment (device, precision, packages, BLAS threads, CPU model and affinity, XLA flags and
      the compilation cache); and the source (an execution snapshot's SNAPSHOT.json revision and
      patch, or a checkout's HEAD and its state).
  summary --records FILE... --out FILE [--design-cpu DIR] [--design-gpu DIR]
      The figures by size, every repeat and the median and range of each timed quantity, beside the
      design note's records read from their folders (the CPU's out/v2, the L4's out/gpu), with a
      Markdown table of each printed to stdout.
"""

import argparse
import hashlib
import json
import os
import platform
import resource
import statistics
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

RUN_KIND = "cells.fr43_chain_performance_run@1"
SUMMARY_KIND = "cells.fr43_chain_performance@1"
# What the design note's records are (docs/FR43_SHARED_INVENTORIES_DESIGN.md), beside today's.
DESIGN_CPU_LABEL = (
    "The design probe's CPU records (the note's sections 1.2 and 1.4): the design snapshot "
    "92e18df4 with the species cap raised in its process only, before part 1 landed. Its unrolled "
    "arm folds every species sum unrolled, which the landed fold's gate keeps only up to 16 terms; "
    "its scan arm rebinds every species sum to the scan, which the gate takes only above 16 terms. "
    "So 16 rows compare with the unrolled arm, and 32, 256 and 1,024 rows with the scan arm."
)
DESIGN_GPU_LABEL = (
    "The design probe's L4 column (the note's section 1.8), kept and not re-measured: the design "
    "snapshot 92e18df4 with the species cap raised in its process only, through the runner with "
    "every host check, on the NVIDIA L4 in float64, its host thread on a shared CPU. It was taken "
    "on the composite on a GPU, the path D336 found unqualified (the composite's device checks "
    "failed their GPU qualification, D330); the vector windows refuse it since D336 "
    "(execution/vector_windows.refuse_unqualified_gpu)."
)
EMPTY_PATCH = hashlib.sha256(b"").hexdigest()
ENVIRONMENT = (
    "JAX_PLATFORMS",
    "CUDA_VISIBLE_DEVICES",
    "JAX_ENABLE_X64",
    "JAX_ENABLE_COMPILATION_CACHE",
    "JAX_COMPILATION_CACHE_DIR",
    "XLA_FLAGS",
    "OPENBLAS_NUM_THREADS",
    "PYTHONPATH",
)
WATCHED_CPUS = (4, 5, 20, 21)  # The timed cores and their sibling threads.
TIMED = (
    "build_seconds",
    "parse_seconds",
    "compile_seconds",
    "execute_seconds",
    "seconds_per_simulated_second",
    "ms_per_step",
    "host_check_seconds",
    "peak_rss_mib",
    "peak_rss_mib_at_end",
)


def utc():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def peak_rss_bytes():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024


def cpu_times():
    """{cpu: (total, idle)} jiffies from /proc/stat for the watched CPUs."""
    out = {}
    for line in Path("/proc/stat").read_text().splitlines():
        name = line.split(maxsplit=1)[0]
        if name.startswith("cpu") and name[3:].isdigit() and int(name[3:]) in WATCHED_CPUS:
            values = [int(v) for v in line.split()[1:]]
            out[int(name[3:])] = (sum(values), values[3] + values[4])
    return out


def busy(before, after):
    """The fraction of each watched CPU's time spent busy between two cpu_times readings."""
    return {
        str(c): round(1 - (after[c][1] - before[c][1]) / max(1, after[c][0] - before[c][0]), 3)
        for c in sorted(before)
        if c in after
    }


def source():
    """The tree this process runs: an execution snapshot (its SNAPSHOT.json's revision and patch)
    or, for a development run, the checkout's HEAD and whether its tracked files differ."""
    snapshot = ROOT / "SNAPSHOT.json"
    if snapshot.is_file():
        doc = json.loads(snapshot.read_text())
        return dict(
            kind="execution_snapshot",
            snapshot=str(ROOT),
            git_revision=doc.get("git_revision"),
            patch_sha256=doc.get("patch_sha256"),
            clean=doc.get("patch_sha256") == EMPTY_PATCH,
        )

    def git(*args):
        return subprocess.run(
            ["git", "-C", str(ROOT), *args], capture_output=True, text=True, check=True
        ).stdout.strip()

    return dict(
        kind="checkout",
        git_revision=git("rev-parse", "HEAD"),
        clean=git("status", "--porcelain", "--untracked-files=no") == "",
    )


def environment():
    import jax

    from cells.execution import blas_threads
    from cells.records.io import runtime_identity

    device = jax.devices()[0]
    try:
        cpu_model = next(
            line.split(":", 1)[1].strip()
            for line in Path("/proc/cpuinfo").read_text().splitlines()
            if line.startswith("model name")
        )
    except (OSError, StopIteration):
        cpu_model = None
    cache = {}
    for option in ("jax_enable_compilation_cache", "jax_compilation_cache_dir"):
        try:
            cache[option] = getattr(jax.config, option)
        except AttributeError as error:  # Recorded, never repaired.
            cache[option] = repr(error)
    return dict(
        device=str(device),
        platform=device.platform,
        device_kind=device.device_kind,
        precision="float64" if jax.config.read("jax_enable_x64") else "float32",
        runtime=runtime_identity("cpu"),
        blas=blas_threads.libraries(),
        cpu_model=cpu_model,
        cpu_count=os.cpu_count(),
        affinity=sorted(os.sched_getaffinity(0)),
        python_executable=sys.executable,
        python=platform.python_version(),
        compilation_cache=cache,
        environ={key: os.environ.get(key) for key in ENVIRONMENT},
    )


def models(raw):
    """The engine models the definition names: the model, its inner model, operators, the laws of
    their reactions, and the solvers."""
    model, execution = raw["model"], raw["execution"]
    operators = [o["law"] for o in model.get("operators", [])]
    laws = sorted(
        {r["law"] for o in model.get("operators", []) for r in o.get("reactions", []) if "law" in r}
    )
    return dict(
        model=model["id"],
        inner_model=model.get("inner_model"),
        operators=operators,
        reaction_laws=laws,
        solver=execution.get("solver"),
        field_solver=execution.get("field_solver"),
    )


def cmd_run(a):
    import jax

    jax.config.update("jax_enable_x64", True)

    from cells.definitions.specs import parse_spec
    from cells.execution.resources import trace_bytes
    from cells.execution.runner import run
    from tests.species_cap_fixtures import (
        CHAIN_ACCURACY,
        CHAIN_IONS,
        chain_checks,
        chain_world,
        held_bytes,
    )

    started, wall = utc(), perf_counter()
    steps = int(round(a.end / a.dt))
    out = dict(
        kind=RUN_KIND,
        rows=a.rows,
        chain_species=a.rows - CHAIN_IONS,
        routes=a.rows - CHAIN_IONS - 1,
        dt=a.dt,
        end=a.end,
        every=a.every,
        steps=steps,
        argv=[sys.executable, *sys.argv],
        cwd=os.getcwd(),
        started_utc=started,
        source=source(),
    )
    t0 = perf_counter()
    raw = chain_world(a.rows, dt=a.dt, end=a.end, every=a.every)
    t1 = perf_counter()
    spec = parse_spec(raw)
    t2 = perf_counter()
    out.update(
        build_seconds=t1 - t0,
        parse_seconds=t2 - t1,
        species=len(spec.model.species_ids),
        models=models(raw),
        trace_bytes_estimate=int(trace_bytes(spec, steps)),
        max_trace_bytes=int(spec.execution.max_trace_bytes),
        peak_rss_bytes_after_parse=peak_rss_bytes(),
    )
    before = cpu_times()
    result = run(spec)  # Every host check on every accepted row, or a refusal.
    after = cpu_times()
    out["peak_rss_bytes_after_run"] = peak_rss_bytes()  # Before the closed form below.
    timings = {key: float(value) for key, value in result.timings.items()}
    out.update(
        timings=timings,
        compile_seconds=timings["compile_or_cache_seconds"],
        execute_seconds=timings["execute_seconds"],
        seconds_per_simulated_second=timings["execute_seconds"] / a.end,
        ms_per_step=1e3 * timings["execute_seconds"] / steps,
        host_check_seconds=timings["analysis_seconds"],
        peak_rss_mib=out["peak_rss_bytes_after_run"] / 2**20,
        cpu_busy_during_run=busy(before, after),
        accepted_rows=len(result.times),
        held_bytes=int(held_bytes(result)),
        diagnostics={
            key: float(value)
            for key, value in result.diagnostics.items()
            if isinstance(value, (int, float))
        },
    )
    checks = chain_checks(raw, spec, result)
    out["accuracy"] = dict(
        declared=CHAIN_ACCURACY,
        error_over_largest=checks["error"],
        plant_over_largest=checks["seen"],
        heat_residual_relative=checks["heat"],
        met=checks["error"] <= CHAIN_ACCURACY,
        plant_seen=checks["seen"] > 5 * CHAIN_ACCURACY,
    )
    # The design note's tables give the process's peak at its end, after the closed form.
    out["peak_rss_bytes_at_end"] = peak_rss_bytes()
    out["peak_rss_mib_at_end"] = out["peak_rss_bytes_at_end"] / 2**20
    out["environment"] = environment()
    out["wall_seconds"] = perf_counter() - wall
    out["status"] = "complete"
    Path(a.out).write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
    print(
        json.dumps({k: out[k] for k in ("rows", "compile_seconds", "ms_per_step", "peak_rss_mib")})
    )


# ------------------------------------------------------------------ summary


def spread(values):
    values = [float(v) for v in values]
    return dict(values=values, median=statistics.median(values), min=min(values), max=max(values))


def design_records(folder, platform_name):
    """The design note's run records in `folder` (out/v2 on the CPU, out/gpu on the L4), by
    (rows, arm): the same quantities, read from the records as the probe wrote them. Their peak
    RSS is given both after the run and at the process's end (the note's tables give the end)."""
    out = []
    for path in sorted(Path(folder).glob("run-*.json")):
        doc = json.loads(path.read_text())
        if doc.get("kind") != "run" or doc.get("status") != "complete" or "timings" not in doc:
            continue
        t = doc["timings"]
        card = (doc.get("device_memory_after_run") or {}).get("peak_bytes_in_use")
        out.append(
            dict(
                record=str(path),
                rows=doc["rows"],
                arm=doc["arm"],
                platform=doc["environment"]["platform"],
                device=doc["environment"]["device"],
                precision=doc["environment"]["precision"],
                revision=doc["environment"]["revision"],
                steps=doc["steps"],
                parse_seconds=doc["parse_seconds"],
                compile_seconds=t["compile_or_cache_seconds"],
                ms_per_step=doc["execute_ms_per_step"],
                seconds_per_simulated_second=doc["seconds_per_simulated_second"],
                host_check_seconds=t["analysis_seconds"],
                peak_rss_mib=doc["peak_rss_bytes_after_run"] / 2**20,
                peak_rss_mib_at_end=doc["peak_rss_bytes"] / 2**20,
                device_peak_mib=None if card is None else card / 2**20,
                error_over_largest=doc["error_over_largest_species"],
                plant_over_largest=doc["planted_error_over_largest_species"],
            )
        )
    assert all(r["platform"] == platform_name for r in out), folder
    return sorted(out, key=lambda r: (r["rows"], r["arm"]))


def table(rows, columns):
    head = "| " + " | ".join(c for c, _ in columns) + " |"
    rule = "| " + " | ".join("---" for _ in columns) + " |"
    return "\n".join(
        [head, rule, *("| " + " | ".join(f(r) for _, f in columns) + " |" for r in rows)]
    )


def cmd_summary(a):
    records = [json.loads(Path(p).read_text()) for p in a.records]
    if any(r.get("kind") != RUN_KIND or r.get("status") != "complete" for r in records):
        raise SystemExit("summary refused: a record is not a complete run of this driver")
    revisions = {r["source"]["git_revision"] for r in records}
    if len(revisions) != 1 or not all(r["source"]["clean"] for r in records):
        raise SystemExit(f"summary refused: the records' sources differ or are dirty: {revisions}")
    sizes = []
    for rows in sorted({r["rows"] for r in records}):
        mine = [r for r in records if r["rows"] == rows]
        env = mine[0]["environment"]
        sizes.append(
            dict(
                rows=rows,
                chain_species=mine[0]["chain_species"],
                routes=mine[0]["routes"],
                repeats=len(mine),
                records=[
                    str(Path(p))
                    for p, r in zip(a.records, records, strict=True)
                    if r["rows"] == rows
                ],
                commands=[r["argv"] for r in mine],
                device=env["device"],
                precision=env["precision"],
                accuracy_met=all(
                    r["accuracy"]["met"] and r["accuracy"]["plant_seen"] for r in mine
                ),
                error_over_largest=spread(r["accuracy"]["error_over_largest"] for r in mine),
                plant_over_largest=spread(r["accuracy"]["plant_over_largest"] for r in mine),
                heat_residual_relative=spread(
                    r["accuracy"]["heat_residual_relative"] for r in mine
                ),
                trace_bytes_estimate=mine[0]["trace_bytes_estimate"],
                max_trace_bytes=mine[0]["max_trace_bytes"],
                cpu_busy_during_run=[r["cpu_busy_during_run"] for r in mine],
                **{key: spread(r[key] for r in mine) for key in TIMED},
            )
        )
    first = records[0]
    doc = dict(
        kind=SUMMARY_KIND,
        written_utc=utc(),
        source=first["source"],
        models=first["models"],
        world=dict(dt=first["dt"], end=first["end"], every=first["every"], steps=first["steps"]),
        declared_accuracy=first["accuracy"]["declared"],
        environment=first["environment"],
        sizes=sizes,
    )
    if a.design_cpu:
        doc["design_cpu"] = design_records(a.design_cpu, "cpu")
        doc["design_cpu_label"] = DESIGN_CPU_LABEL
    if a.design_gpu:
        doc["design_gpu"] = design_records(a.design_gpu, "gpu")
        doc["design_gpu_label"] = DESIGN_GPU_LABEL
    Path(a.out).write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n")

    def m(key, fmt):
        return lambda s: (
            fmt.format(s[key]["median"])
            + " ("
            + fmt.format(s[key]["min"])
            + "–"
            + fmt.format(s[key]["max"])
            + ")"
        )

    print(
        table(
            sizes,
            [
                ("Rows", lambda s: f"{s['rows']:,}"),
                ("Repeats", lambda s: str(s["repeats"])),
                ("Build s", m("build_seconds", "{:.1f}")),
                ("Parse s", m("parse_seconds", "{:.1f}")),
                ("Compile s", m("compile_seconds", "{:.1f}")),
                ("ms per step", m("ms_per_step", "{:.3g}")),
                ("s per simulated s", m("seconds_per_simulated_second", "{:.3g}")),
                ("Host checks s", m("host_check_seconds", "{:.2f}")),
                ("Peak RSS MiB after run", m("peak_rss_mib", "{:,.0f}")),
                ("at end", m("peak_rss_mib_at_end", "{:,.0f}")),
                ("Error / largest", lambda s: f"{s['error_over_largest']['max']:.3g}"),
                ("Plant / largest", lambda s: f"{s['plant_over_largest']['min']:.3g}"),
            ],
        )
    )
    for key in ("design_cpu", "design_gpu"):
        if key in doc:
            print()
            print(
                table(
                    doc[key],
                    [
                        ("Rows", lambda r: f"{r['rows']:,}"),
                        ("Arm", lambda r: r["arm"]),
                        ("Device", lambda r: r["device"]),
                        ("Compile s", lambda r: f"{r['compile_seconds']:.1f}"),
                        ("ms per step", lambda r: f"{r['ms_per_step']:.3g}"),
                        ("s per simulated s", lambda r: f"{r['seconds_per_simulated_second']:.3g}"),
                        ("Peak RSS MiB after run", lambda r: f"{r['peak_rss_mib']:,.0f}"),
                        ("at end", lambda r: f"{r['peak_rss_mib_at_end']:,.0f}"),
                        ("Error / largest", lambda r: f"{r['error_over_largest']:.3g}"),
                    ],
                )
            )


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="command", required=True)
    r = sub.add_parser("run")
    r.add_argument("--rows", type=int, required=True)
    r.add_argument("--dt", type=float, default=0.005)
    r.add_argument("--end", type=float, default=2.0)
    r.add_argument("--every", type=float, default=0.25)
    r.add_argument("--out", required=True)
    s = sub.add_parser("summary")
    s.add_argument("--records", nargs="+", required=True)
    s.add_argument("--out", required=True)
    s.add_argument("--design-cpu", help="the design probe's CPU run records (out/v2)")
    s.add_argument("--design-gpu", help="the design probe's L4 run records (out/gpu)")
    a = p.parse_args(argv)
    {"run": cmd_run, "summary": cmd_summary}[a.command](a)


if __name__ == "__main__":
    main()
