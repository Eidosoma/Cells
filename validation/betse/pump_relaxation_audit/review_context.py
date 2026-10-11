"""Sealed 10 ms inputs and explicit case-specific scope; no producer imports."""

import importlib.util
import sys
from functools import lru_cache
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "pump_pilot_audit"))
import audit_evidence as original  # noqa: E402

sys.path.insert(0, str(HERE.parent / "pump_relaxation_scope"))
import relax_context as inherited  # noqa: E402

c, e, util = inherited.c, original.e, inherited.previous
ROOT = c.ROOT
EXTRAS = ("launch.json", "runner.stdout.log", "runner.stderr.log")
PACKETS = {
    "reference": (
        "ref-005e-reference-scope-2026-09-17/scope-01",
        "3a41f3bb4e51ab73c6894b810cd263a155c0476f85493aea7155fd47371892b2",
        "3a7710f88c309b16c2cca9739282801fc2b3b9bad8bf61253add4c816404d29c",
        24,
    ),
    "probe": (
        "ref-005e-native-probe-2026-09-17/probe-01",
        "c7ab26e3fdde3d9a46471508b20f7275b0622d0ef72c859445bd464d7a31746a",
        "cd0c629469baa03d162b39a06a038701516d27dc97f0a3a78b64a8d8ad3c7414",
        947,
    ),
    "finer": (
        "ref-005e-finer-native-2026-09-17/refinement-01",
        "71e7cfebc0a933f569e8bee4c7913ab509dfdbcc482120b63487e46115d42f10",
        "c27ad36b6f9496c1622cbea64f3ee1dc4ed5b20143407b2234b219ee8472854d",
        3403,
    ),
    "matched": (
        "ref-005e-matched-10ms-2026-09-17/campaign-01",
        "4d62da1d279ecdc9b51ce06653e151e51e344dbe2ec0f93be5f892aad9293567",
        "b1370c34ba9875b2f3d2a52b90803773552cef9eea0169e01a262723c0573cfc",
        18385,
    ),
    "diagnosis": (
        "ref-005e-bath-diagnosis-2026-09-18/diagnosis-01",
        "63cd0eb7edd207f665dad43aabe4349a4672ad7a3216f321f095cfe16ae102c8",
        "9620748cecd851edb8d3b8cbcc45a8eb30aca97031a5200998500182381350ad",
        10,
    ),
    "range": (
        "ref-005e-pump-range-2026-09-18/range-01",
        "fd9c318bd154de58bbd5e2de7f2109850bbde6630ec361cb27cf9226ceb5f5c9",
        "ab812df589a62c0e6a79857ce6f50e809868c0e5c0b20098c33b7f5cea828cb4",
        535,
    ),
}
VARIANTS = ["pump_leak", "pump_only", "leak_only", "all_blocked", "half_density", "closed_boundary"]
RANGES = {
    name: [6.25e-6, 3.125e-6, 1.5625e-6]
    if name == "pump_only"
    else [1.5625e-6, 7.8125e-7, 3.90625e-7]
    for name in VARIANTS
}
SCOPE = dict(
    duration_s=0.01,
    native_step_ranges_s=RANGES,
    native_rows=18,
    native_updates=235200,
    finest_observer_pairs=6,
    cells_trajectories=24,
    loaded_restart_suffixes=6,
    reference_solves_reused=18,
    new_simulator_runs=0,
    decimal_digits=70,
    native_every_update_accounting=True,
    cells_independent_accounting="41 common observations per trajectory",
    original_common_range_remains_failed=True,
    matched_10ms_qualification="case-specific timesteps only, conditional on independent pass",
    biology_validated=False,
    gpu_tested=False,
    steady_state_qualified=False,
    full_betse_parity=False,
    automatic_polling=False,
    automatic_retry=False,
    automatic_followup=False,
)
e.FORBIDDEN += (
    "matched_job",
    "matched_work",
    "range_job",
    "range_work",
    "refined_job",
    "refined_work",
    "refined_recording",
    "probe_job",
    "probe_work",
    "relax_job",
    "relax_reference",
    "native_row",
    "record_codec",
    "stream_compare",
    "refinement_check",
    "pilot_math",
)


def path(name):
    return ROOT / "runs" / PACKETS[name][0]


def private(name, source):
    spec = importlib.util.spec_from_file_location(name, source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@lru_cache(maxsize=1)
def reader():
    module = private("_relax_review_wire", Path(c.wire.__file__))
    c.need(
        module.STREAM_BYTES == 32 * 1024**2 and module.CHUNK_BYTES == 8 * 1024**2,
        "Independent reader defaults",
    )
    module.STREAM_BYTES = 128 * 1024**2
    return module.Stream


@lru_cache(maxsize=1)
def cells_reader():
    # Only the evidence root changes in this private instance of the qualified
    # archive/restart/checkpoint reader. No shared module is mutated.
    module = private("_relax_review_cells", Path(original.diagnostic.__file__))
    module.CAPTURE = path("matched")
    return module


def preparation():
    return c.read(path("reference") / "registration.json", None), inherited.inherited()


def contract(reference, old, result, previous, registered):
    plan = reference["protocol"]
    c.need(
        plan["duration_s"] == 0.01
        and plan["common_times_s"] == [i * 0.00025 for i in range(41)]
        and plan["restart_time_s"] == 0.005,
        "10 ms clock",
    )
    for name in (
        "accounting",
        "trajectory",
        "mapping",
        "refinement",
        "reference",
        "cells_steps_s",
        "cells_eager_step_s",
        "restart_step_s",
        "variants",
    ):
        original.same_record(plan[name], old["protocol"][name], "Scientific contract: " + name)
    for name, case in reference["cases"].items():
        c.need(case == dict(old["cases"][name], end_time_s=0.01), "Case preparation")
    c.need(set(reference["cases"]) == set(VARIANTS), "Case coverage")
    c.need(
        registered["scope"]["native_step_ranges_s"] == RANGES
        and RANGES["pump_only"] == old["protocol"]["native_steps_s"],
        "Case-specific ranges",
    )
    c.need(
        result["producer_passed"] is True
        and set(result["cases"]) == set(VARIANTS)
        and all(v["passed"] is True for v in result["cases"].values())
        and {k: v["native_steps_s"] for k, v in result["cases"].items()} == RANGES,
        "Producer case-specific pass",
    )
    c.need(
        previous["producer_passed"] is False
        and previous["cases"]["pump_only"]["refinement"]["amount"]["passed"] is False,
        "Original common range remains failed",
    )
    for name in (
        "original_common_range_passed",
        "original_verdict_changed",
        "physics_changed",
        "production_changed",
        "scientific_tolerances_changed",
        "matched_10ms_qualified",
    ):
        c.need(result[name] is False, "Changed producer scope: " + name)
    c.need(result["independent_review_pending"] is True, "Premature qualification")


def authenticate_inputs():
    inherited.authenticate_r0()
    receipts = {}
    for name, (_, reg_sha, done_sha, count) in PACKETS.items():
        directory = path(name)
        c.need(c.sha(directory / "registration.json") == reg_sha, "Input registration: " + name)
        done, files = c.packet(directory, "completion.json", done_sha, extras=EXTRAS, count=count)
        r = c.read(directory / "registration.json", None)
        c.capsule(directory, r["sources_sha256"])
        c.need(
            c.read(directory / "launch.json", None)["registration_sha256"] == reg_sha
            and (directory / "runner.stderr.log").read_bytes() == b"",
            "Input launch/stderr",
        )
        if "software" in r:
            software = r["software"]
            sd, _ = c.packet(
                c.child(ROOT, software["path"]).parent,
                "completion.json",
                software["sha256"],
                pytest_links=True,
            )
            c.need(
                sd["sources_sha256"] == r["sources_sha256"]
                and sd["software"] == software["xml"]
                and e.software(c.child(ROOT, software["xml"]["path"]), software["xml"]["tests"])
                == software["xml"],
                "Producer software binding",
            )
        receipts[name] = dict(
            registration_sha256=reg_sha,
            completion_sha256=done_sha,
            payloads=len(done["files_sha256"]),
            regular_files=len(files),
        )
    reference, old = preparation()
    result = c.read(path("range") / "comparison.json", None)
    previous = c.read(path("matched") / "comparison.json", None)
    contract(reference, old, result, previous, c.read(path("range") / "registration.json", None))
    focused = c.read(path("probe") / "review.json", None)
    c.need(
        focused["status"] == "focused_reference_review_pass"
        and focused["reference_solves"] == 18
        and focused["new_integrations"] == 0,
        "Reviewed references",
    )
    c.need(
        c.read(path("range") / "completion.json", None)["producer_passed"] is True,
        "Range terminal verdict",
    )
    return receipts


def rows():
    """Explicit evidence map; no producer selection/comparison code is imported."""
    result = []
    for name in VARIANTS:
        if name == "pump_leak":
            origins = [("probe", "native/2"), ("finer", "native/medium"), ("finer", "native/fine")]
            quiet = path("finer") / "native/fine_quiet"
        elif name == "pump_only":
            origins = [
                ("range", "native/pump_only/coarse"),
                ("range", "native/pump_only/medium"),
                ("matched", "native/pump_only/0"),
            ]
            quiet = path("range") / "native/pump_only/fine_quiet"
        else:
            origins = [("matched", "native/" + name + "/" + str(i)) for i in range(3)]
            quiet = path("matched") / "native" / name / "quiet"
        for i, ((source, leaf), step) in enumerate(zip(origins, RANGES[name], strict=True)):
            result.append(
                dict(
                    case=name,
                    index=i,
                    dt_s=step,
                    directory=str((path(source) / leaf).relative_to(ROOT)),
                    quiet=str(quiet.relative_to(ROOT)) if i == 2 else None,
                )
            )
    return result


def sources():
    names = (
        set(c.sources())
        | set(original.source_manifest())
        | {
            "validation/betse/pump_relaxation_scope/relax_context.py",
            "validation/betse/pump_coupled_audit/coupled_audit.py",
        }
    )
    names.update(str(p.relative_to(ROOT)) for p in HERE.glob("*.py"))
    return {n: c.sha(c.child(ROOT, n)) for n in sorted(names)}
