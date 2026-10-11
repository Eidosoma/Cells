"""D129 saved-evidence authentication. No live producer or simulator imports."""

import os
import sys
from pathlib import Path, PurePosixPath

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "native_recording_audit"))
import codec_audit_context as old  # noqa: E402
import codec_review as exact  # noqa: E402, F401 -- public independent comparison primitive
import wire_decode as wire  # noqa: E402

sys.path.insert(0, str(HERE.parent / "kinetic_family_audit"))
import artifacts as arrays  # noqa: E402, F401 -- public independent NPZ reader

ROOT, e, LEGACY = old.ROOT, old.e, old.LEGACY
CAPTURE = ROOT / "runs/ref-005d-output-layout-2026-09-17/qualification-01"
NATIVE = ROOT / "runs/ref-005d-live-recording-2026-09-17/qualification-01"
STOPPED = ROOT / "runs/ref-005d-live-continuation-2026-09-17/continuation-01"
CODEC_AUDIT = ROOT / "runs/ref-005d-codec-audit-2026-09-17/audit-01"
REG_SHA = "1cd7694949963f6f8d80bb222b78c5a039eb4a8425c1d20b5674dd35d72d8b33"
DONE_SHA = "bb6448d1be688c1b3613e8580c3e365cc75a6a794fb6bab22f7fffa4612bf2c1"
CODEC_AUDIT_SHA = "b7cc5472783236f12ccec4e658374ba83c28dba11851543a4ebdca81e3fc883f"
LAYOUT = dict(
    baseline="baseline",
    recording_full="recordings/full",
    recording_observations="recordings/observations",
    recording_checkpoints="recordings/checkpoints",
    resumed="resumed",
)
LAYOUT_VERSION = "cells.matched_window_outputs@2"
PROBE_KEY = "pump_leak/dt_2.5e-05/jax_jit"
COUNTS = {
    "probe": dict(
        full_trajectories=1,
        window_runs=3,
        disk_recordings=3,
        restart_suffixes=1,
        restart_window_runs=1,
        zero_length_runs=1,
        sparse_schedule_controls=0,
    ),
    "matrix": dict(
        full_trajectories=24,
        window_runs=72,
        disk_recordings=18,
        restart_suffixes=6,
        restart_window_runs=6,
        zero_length_runs=6,
        sparse_schedule_controls=2,
    ),
}
PRODUCERS = (
    "live_context",
    "live_job",
    "live_native",
    "live_observer",
    "matched_windows",
    "stream_compare",
    "preflight_job",
    "resume_context",
    "resume_job",
    "output_context",
    "output_job",
    "output_worker",
    "pilot_context",
    "pilot_job",
    "refine_context",
    "refine_job",
    "validation.betse.live_recording",
    "validation.betse.live_recording_resume",
    "validation.betse.live_recording_paths",
    "validation.betse.pump_matched_pilot",
    "validation.betse.pump_refined_pilot",
)
e.FORBIDDEN += tuple(n for n in PRODUCERS if n not in e.FORBIDDEN)
need, read, sha = wire.need, wire.read_json, wire.sha


def child(root, name):
    """No absolute, noncanonical, escaping or ancestor-linked artifact paths."""
    need(type(name) is str and name and "\\" not in name, "Artifact path")
    rel = PurePosixPath(name)
    need(
        not rel.is_absolute() and str(rel) == name and ".." not in rel.parts,
        "Noncanonical artifact path",
    )
    p = Path(root)
    need(not p.is_symlink(), "Linked artifact root")
    for part in rel.parts:
        p = p / part
        need(not p.is_symlink(), "Linked artifact ancestor")
    need(p.resolve().is_relative_to(Path(root).resolve()), "Escaping artifact")
    return p


def inventory(directory, *, pytest_links=False):
    need(directory.is_dir() and not directory.is_symlink(), "Artifact directory")
    files, links = {}, {}
    for base, dirs, names in os.walk(directory, followlinks=False):
        for name in sorted(dirs + names):
            p = Path(base) / name
            rel = str(p.relative_to(directory))
            if p.is_symlink():
                need(
                    pytest_links
                    and rel.startswith("tests/")
                    and p.name.endswith("current")
                    and p.resolve().is_relative_to(directory / "tests")
                    and (p.resolve().is_dir() or p.resolve().is_file()),
                    "Unsafe artifact link",
                )
                links[rel] = os.readlink(p)
            else:
                need(p.is_file() or p.is_dir(), "Nonregular artifact")
                if p.is_file():
                    files[rel] = sha(p)
    return dict(sorted(files.items())), dict(sorted(links.items()))


def hashes(directory, values):
    for name, digest in values.items():
        wire.digest_string(digest)
        need(sha(child(directory, name)) == digest, "Artifact digest: " + name)


def capsule(directory, sources):
    hashes(ROOT, sources)
    old.prior.evidence.capsule(directory, sources)


def packet(directory, terminal, digest, *, extras=(), count=None, pytest_links=False):
    need(sha(directory / terminal) == digest, "Terminal evidence identity")
    done = read(directory / terminal, None)
    files, links = inventory(directory, pytest_links=pytest_links)
    sealed = done["files_sha256"]
    need(set(files) == set(sealed) | {terminal, *extras}, "Packet membership")
    need(all(files[k] == v for k, v in sealed.items()), "Packet payload changed")
    need(count is None or len(sealed) == count, "Packet coverage")
    need(links == done.get("pytest_internal_links", {}), "Pytest link coverage")
    return done, files


def software(record, sources, tests, status):
    path = child(ROOT, record["path"])
    need(
        path.is_relative_to(ROOT / "runs") and path.name == "completion.json",
        "Software packet location",
    )
    done, files = packet(path.parent, path.name, record["sha256"], pytest_links=True)
    need(
        done["status"] == status
        and done["sources_sha256"] == sources
        and done["software"] == record["xml"],
        "Software source/result binding",
    )
    need(
        e.software(child(ROOT, record["xml"]["path"]), tests) == record["xml"]
        and record["xml"]["tests"] == tests,
        "Software tests",
    )
    return files


def cells_keys():
    return sorted(
        f"{case}/dt_{dt}/{mode}"
        for case in (
            "all_blocked",
            "closed_boundary",
            "half_density",
            "leak_only",
            "pump_leak",
            "pump_only",
        )
        for dt, mode in (
            ("1.25e-05", "jax_jit"),
            ("2.5e-05", "jax_jit"),
            ("5e-05", "jax_eager"),
            ("5e-05", "jax_jit"),
        )
    )


def authenticate():
    """Authenticate the full prerequisite chain, including both preserved failures."""
    _, _, codec_files = old.authenticate()
    ad, audit_files = packet(
        CODEC_AUDIT,
        "completion.json",
        CODEC_AUDIT_SHA,
        extras=("launch.json", "runner.stdout.log", "runner.stderr.log"),
        count=40,
    )
    ar = read(CODEC_AUDIT / "registration.json", None)
    need(
        ad["status"] == "offline_lossless_recording_independently_closed"
        and ad["rows"] == 36
        and ad["failed_comparisons"] == 0
        and ar["capture_files_sha256"] == codec_files,
        "Offline closure",
    )
    capsule(CODEC_AUDIT, ar["sources_sha256"])
    need(
        e.software(child(ROOT, ar["software"]["path"]), 133) == ar["software"],
        "Offline reviewer software",
    )
    need(sha(CAPTURE / "registration.json") == REG_SHA, "D128 registration identity")
    r = read(CAPTURE / "registration.json", None)
    done, files = packet(
        CAPTURE,
        "completion.json",
        DONE_SHA,
        extras=("launch.json", "runner.stdout.log", "runner.stderr.log"),
        count=516,
    )
    need(
        r["schema"] == "cells.live_recording_output_layout@1"
        and r["decision"] == "D128"
        and r["duration_s"] == 0.001
        and r["cells_keys"] == cells_keys()
        and r["phase_counts"] == COUNTS
        and r["output_layout"] == LAYOUT
        and r["output_layout_version"] == LAYOUT_VERSION
        and done["status"] == "live_recording_and_matched_windows_pass_pending_independent_review"
        and done["actual_worker_probe_complete"] is True,
        "D128 scope",
    )
    for name in (
        "production_changed",
        "scientific_tolerances_changed",
        "partial_cells_reused",
        "automatic_followup",
        "native_memory_bounded",
        "biology_validated",
        "gpu_tested",
        "longer_horizon_qualified",
        "independent_live_review_complete",
    ):
        need(done[name] is False, "Expanded producer claim: " + name)
    need(
        done["new_native_runs"] == 0
        and done["native_runs_reused"] == 36
        and done["observer_pairs"] == 18
        and done["observed_updates"] == 6720
        and done["history_samples"] == 13404
        and done["earlier_attempts_stay_failed"] is True,
        "Producer native reuse scope",
    )
    need(read(CAPTURE / "launch.json")["registration_sha256"] == REG_SHA, "Producer launch binding")
    need(len(r["sources_sha256"]) == 680, "Producer source coverage")
    capsule(CAPTURE, r["sources_sha256"])
    software(r["software"], r["sources_sha256"], 51, "output_layout_software_pass")
    for phase, counts in COUNTS.items():
        stamp = read(CAPTURE / (phase + "-complete.json"), None)
        result = read(CAPTURE / (phase + ".json"), None)
        phase_files, _ = inventory(CAPTURE / phase)
        need(
            stamp["status"] == "phase_pass"
            and stamp["phase"] == phase
            and stamp["registration_sha256"] == REG_SHA
            and stamp["result_sha256"] == sha(CAPTURE / (phase + ".json"))
            and stamp["files_sha256"] == phase_files,
            "Phase seals",
        )
        need({k: result[k] for k in counts} == counts == done[phase + "_counts"], "Phase counts")
        keys = [PROBE_KEY] if phase == "probe" else cells_keys()
        need(
            sorted(result["records"]) == keys and result["production_changed"] is False,
            "Phase case coverage",
        )
        for key, row in result["records"].items():
            need(
                row["directory"] == "cells/" + key
                and row["sha256"]
                == sha(child(CAPTURE / phase, row["directory"]) / "comparison.json"),
                "Case comparison seal",
            )
    for name in ("runner.stderr.log", "probe.stderr.log", "matrix.stderr.log"):
        need((CAPTURE / name).read_bytes() == b"", "Unexpected producer stderr")
    accepted = dict(
        audit_completion_sha256=CODEC_AUDIT_SHA,
        audit_files_sha256=audit_files,
        codec_files_sha256=codec_files,
    )
    need(r["prior"]["accepted"] == accepted, "Accepted prerequisite inventories")
    native, stopped = r["prior"]["reused_native"], r["prior"]["stopped_continuation"]
    for directory, record, count, source_count in (
        (NATIVE, native, 964, 668),
        (STOPPED, stopped, 24, 674),
    ):
        need(record["directory"] == str(directory.relative_to(ROOT)), "Failed packet location")
        hashes(directory, record["identities"])
        inv, _ = inventory(directory)
        need(
            inv == record["files_sha256"]
            and len(inv) == count
            and "completion.json" not in inv
            and "failure.json" in inv,
            "Failed packet preserved",
        )
        saved = read(directory / "registration.json", None)
        need(
            len(saved["sources_sha256"]) == source_count and saved["prior"] == accepted,
            "Failed packet sources/prerequisite",
        )
        capsule(directory, saved["sources_sha256"])
        need(
            read(directory / "launch.json")["registration_sha256"]
            == sha(directory / "registration.json"),
            "Preserved launch binding",
        )
        if directory == STOPPED:
            need(saved["reused_native"] == native, "Continuation native binding")
            software(saved["software"], saved["sources_sha256"], 54, "continuation_software_pass")
        else:
            need(len(saved["sources_sha256"]) == native["source_inputs"], "Native source count")
            need(
                e.software(child(ROOT, saved["software"]["path"]), 79) == saved["software"],
                "Native software XML",
            )
            preflight = ROOT / "runs/ref-005d-live-preflight-2026-09-17/detached-01"
            pd, _ = packet(
                preflight,
                "completion.json",
                "b0ba23dc666ef5a4a328bb9be0f55bd009bb86cf14eb2893a7d2d790e168a224",
                extras=("launch.json", "runner.stdout.log", "runner.stderr.log"),
                pytest_links=True,
            )
            need(
                read(preflight / "registration.json", None)["sources_sha256"]
                == saved["sources_sha256"]
                and pd["software"] == saved["software"],
                "Native software source binding",
            )
            capsule(preflight, saved["sources_sha256"])
    need(r["prior"]["partial_cells_reused"] is False, "Partial Cells reused")
    return r, dict(
        capture=files,
        native=native["files_sha256"],
        stopped=stopped["files_sha256"],
        codec=codec_files,
        codec_audit=audit_files,
    )


def sources():
    names = set(old.source_manifest())
    names.update(str(p.relative_to(ROOT)) for p in HERE.iterdir() if p.suffix in (".py", ".md"))
    names.add("reports/REF005D_LIVE_AUDIT_HANDOFF.md")
    return {n: sha(child(ROOT, n)) for n in sorted(names)}
