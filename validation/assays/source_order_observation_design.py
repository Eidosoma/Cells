"""Select three observation times using authenticated calibration responses only.

The objective measures separation of fitted polylines, not generalization to
physical responses between calibration strengths. No held-out response is read.
"""

import argparse
import itertools
import json
import shutil
import sys
import time
import traceback
from pathlib import Path

import numpy as np

from cells.assembly.cli import output_path, utc
from cells.assembly.io import write_json
from validation.assays import source_order_spanning as assay
from validation.assays.template_readout import TemplateReader
from validation.betse.spatial_active.refinement import completed_prior, digest

ROOT = Path(__file__).resolve().parents[2]
PLAN = Path(__file__).with_name("source_order_long") / "calibration_observation_plan.json"
PLAN_SHA256 = "79d3de7f416a5fd2a87efcedf6e929bf4a13d4fabb7c64e2ac9751d76e0c9607"
ARMS = ("location_only", "timing_only", "joint", "disconnected", "no_cue")
TASKS = ("location", "timing")
TIME_SLICES = {
    128: ("middle128", 2),
    160: ("long256", 0),
    192: ("long256", 1),
    256: ("long256", 2),
    320: ("long512", 0),
    384: ("long512", 1),
    512: ("long512", 2),
}
TIE_ATOL_V = 1e-15


def segment_distance(p0, p1, q0, q1):
    """Global closed-segment minimum: four edges plus a feasible interior.

    Subtract the common origin before interpolation, and solve with normalized
    direction columns rather than cancellation-prone Gram determinants. These
    internal conditioning operations preserve the Euclidean metric in volts.
    """
    points = np.asarray([p0, p1, q0, q1], dtype=np.float64)
    if points.ndim != 2 or not points.shape[1] or not np.isfinite(points).all():
        raise ValueError("Four finite equal-length vectors required")
    p0, p1, q0, q1 = points
    u, v, w = p1 - p0, q1 - q0, p0 - q0
    scale = float(np.max(np.abs([u, v, w])))
    if not np.isfinite(scale):
        raise ValueError("Segment differences overflow")
    if scale == 0:
        return dict(distance_V=0.0, coordinates=[0.0, 0.0])
    u, v, w = u / scale, v / scale, w / scale
    uu, vv = float(u @ u), float(v @ v)
    coordinates = []
    for s in (0.0, 1.0):
        t = float(np.clip((w + s * u) @ v / vv, 0, 1)) if vv else 0.0
        coordinates.append((s, t))
    for t in (0.0, 1.0):
        s = float(np.clip((t * v - w) @ u / uu, 0, 1)) if uu else 0.0
        coordinates.append((s, t))
    if uu and vv:
        lengths = np.sqrt([uu, vv])
        matrix = np.column_stack((u / lengths[0], -v / lengths[1]))
        solution, _, rank, _ = np.linalg.lstsq(matrix, -w, rcond=None)
        s, t = solution / lengths
        # A rank-one (parallel) problem always has an edge minimizer.
        if rank == 2 and 0 <= s <= 1 and 0 <= t <= 1:
            coordinates.append((float(s), float(t)))
    distances = [float(np.linalg.norm(w + s * u - t * v)) for s, t in coordinates]
    index = int(np.argmin(distances))
    return dict(distance_V=scale * distances[index], coordinates=list(coordinates[index]))


def calibration_rows(rows, design):
    # Inspect the split first; even labels/IDs of held-out rows are unnecessary.
    selected = [r for r in rows if r["split"] == "calibration"]
    expected = set(itertools.product(ARMS, design["calibration_strengths"], (0, 1), (0, 1)))
    identities = [(r["arm"], r["amplitude"], r["location"], r["timing"]) for r in selected]
    if (
        len(selected) != len(expected)
        or set(identities) != expected
        or len({r["world_id"] for r in selected}) != len(selected)
    ):
        raise ValueError("Incomplete or duplicate calibration grid")
    return sorted(selected, key=lambda r: r["world_id"])


def validate_support(rule, design):
    if (
        design["available_postcue_times_us"] != list(TIME_SLICES)
        or design["cell_ids"] != rule["readout"]["cell_ids"]
        or design["cell_ids"] != [2, 3, 5, 6, 7]
        or design["feature_count"] != 15
        or design["candidate_count"] != 35
        or design["dt_s"] != rule["dt_s"]
        or len(design["dt_s"]) != 3
        or rule["reader"]["type"] != "nearest_calibrated_polyline"
        or rule["reader"]["voltage_margin_V"] != 2e-9
        or rule["observation_times_us"]["spanning512"] != design["incumbent_times_us"]
        or rule["observation_times_us"]["long512"] != design["late_comparator_times_us"]
    ):
        raise ValueError("Observation support, reader or declared grid changed")
    for observation, (panel, index) in TIME_SLICES.items():
        if rule["observation_times_us"][panel][index] != observation:
            raise ValueError("Recorded time identity changed")


def load_calibration(saved, rows, rule, design):
    """Fetch only named calibration arrays; never enumerate/read held-out keys."""
    validate_support(rule, design)
    training = calibration_rows(rows, design)
    observations, accessed = {}, []
    for level in range(len(design["dt_s"])):
        for row in training:
            panels = {}
            for panel in ("middle128", "long256", "long512", "spanning512"):
                key = f"{level}__{panel}__voltage__{row['world_id']}"
                value = np.asarray(saved[key], dtype=np.float64)
                if value.shape != (15,) or not np.isfinite(value).all():
                    raise ValueError("Invalid archived calibration feature: " + key)
                panels[panel] = value.reshape(3, 5)
                accessed.append(key)
            value = np.stack([panels[p][i] for p, i in TIME_SLICES.values()])
            incumbent = value[[list(TIME_SLICES).index(t) for t in design["incumbent_times_us"]]]
            if not np.array_equal(incumbent, panels["spanning512"]):
                raise ValueError("Reconstructed incumbent differs from its recorded features")
            value.setflags(write=False)
            observations[level, row["world_id"]] = value
    return training, observations, accessed


def task_separation(reader, task_index, strengths):
    """Return the worst opposite-label curve pair, including segment interiors."""
    best = None
    for a, b in itertools.combinations(range(len(reader.vertices)), 2):
        if reader.labels[a, task_index] == reader.labels[b, task_index]:
            continue
        for i, j in itertools.product(range(len(strengths) - 1), repeat=2):
            pair = segment_distance(
                reader.vertices[a, i],
                reader.vertices[a, i + 1],
                reader.vertices[b, j],
                reader.vertices[b, j + 1],
            )
            if best is None or pair["distance_V"] < best["distance_V"]:
                best = pair | dict(
                    half_distance_V=pair["distance_V"] / 2,
                    curve_labels=reader.labels[[a, b]].tolist(),
                    segments=[i, j],
                    inferred_strengths=[
                        strengths[k] + c * (strengths[k + 1] - strengths[k])
                        for k, c in zip((i, j), pair["coordinates"], strict=True)
                    ],
                )
    if best is None:
        raise ValueError("Both task labels required")
    return best


def choose(candidates, incumbent):
    if not candidates or any(not np.isfinite(r["score_V"]) for r in candidates):
        raise ValueError("Finite candidate scores required")
    maximum = max(r["score_V"] for r in candidates)
    tied = [r for r in candidates if maximum - r["score_V"] <= TIE_ATOL_V]
    tied.sort(key=lambda r: tuple(r["times_us"]))
    selected = next((r for r in tied if r["times_us"] == incumbent), tied[0])
    return dict(
        times_us=selected["times_us"],
        score_V=selected["score_V"],
        maximum_score_V=maximum,
        tied_times_us=[r["times_us"] for r in tied],
        tie_atol_V=TIE_ATOL_V,
        incumbent_preferred=selected["times_us"] == incumbent,
    )


def rank_schedules(rows, observations, rule, design):
    validate_support(rule, design)
    training = calibration_rows(rows, design)
    candidates = []
    for times in itertools.combinations(design["available_postcue_times_us"], 3):
        indices = [list(TIME_SLICES).index(t) for t in times]
        groups, nulls = [], []
        for level, dt in enumerate(design["dt_s"]):
            for arm in ARMS:
                selected = [r for r in training if r["arm"] == arm]
                tasks = list(TASKS)
                if arm.endswith("_only"):
                    task = arm.removesuffix("_only")
                    ignored = next(t for t in TASKS if t != task)
                    selected = [r for r in selected if r[ignored] == 0]
                    tasks = [task]
                features = np.stack(
                    [observations[level, r["world_id"]][indices].reshape(-1) for r in selected]
                )
                reader = TemplateReader.fit(
                    features,
                    np.array([[r[t] for t in tasks] for r in selected]),
                    [r["amplitude"] for r in selected],
                    minimum_margin=rule["reader"]["voltage_margin_V"],
                )
                if arm in ("no_cue", "disconnected"):
                    read = reader.read(features)
                    nulls.append(
                        dict(
                            arm=arm,
                            level=level,
                            dt_s=dt,
                            calibration_cases=len(selected),
                            tasks={
                                task: dict(
                                    maximum_absolute_score_V=float(
                                        np.abs(read["score"][:, i]).max()
                                    ),
                                    resolved_cases=int(read["resolved"][:, i].sum()),
                                )
                                for i, task in enumerate(tasks)
                            },
                            included_in_selection_objective=False,
                        )
                    )
                else:
                    for i, task in enumerate(tasks):
                        groups.append(
                            dict(arm=arm, task=task, level=level, dt_s=dt)
                            | (task_separation(reader, i, design["calibration_strengths"]))
                        )
        limiting = min(groups, key=lambda r: r["half_distance_V"])
        candidates.append(
            dict(
                times_us=list(times),
                feature_count=15,
                score_V=limiting["half_distance_V"],
                limiting_group=limiting,
                task_groups=groups,
                calibration_null_controls=nulls,
            )
        )
    if len(candidates) != design["candidate_count"]:
        raise ValueError("Candidate count changed")
    selection = choose(candidates, design["incumbent_times_us"])
    comparators = {
        name: next(r for r in candidates if r["times_us"] == design[key])["score_V"]
        for name, key in (("incumbent", "incumbent_times_us"), ("late", "late_comparator_times_us"))
    }
    return dict(
        candidates=candidates,
        selection=selection,
        comparator_scores_V=comparators,
        improvement_over_incumbent_V=selection["score_V"] - comparators["incumbent"],
    )


def backend_comparison(cpu, gpu):
    if [r["times_us"] for r in cpu["candidates"]] != [r["times_us"] for r in gpu["candidates"]]:
        raise ValueError("Backend candidate grids differ")
    differences = [
        abs(a["score_V"] - b["score_V"])
        for a, b in zip(cpu["candidates"], gpu["candidates"], strict=True)
    ]
    same = cpu["selection"]["times_us"] == gpu["selection"]["times_us"]
    return dict(
        winners_agree=same,
        maximum_candidate_score_difference_V=max(differences),
        selected_times_us=cpu["selection"]["times_us"] if same else None,
        reproducible_improvement=same
        and max(differences) <= TIE_ATOL_V
        and all(r["improvement_over_incumbent_V"] > TIE_ATOL_V for r in (cpu, gpu)),
    )


def authenticate(plan):
    print(json.dumps(dict(phase="authenticate_completed_evidence", utc=utc())), flush=True)
    binding = plan["source_binding"] | dict(require_completed_cpu_and_gpu=True)
    root = Path(binding["root"])
    if digest(root / "completion.json") != binding["completion_sha256"]:
        raise ValueError("Completed source binding differs")
    evidence = completed_prior(binding, current_root=ROOT)
    registration = json.loads((root / "registration.json").read_text())
    for name, sha in registration["sources_sha256"].items():
        if digest(ROOT / name) != sha:
            raise ValueError("Frozen source changed: " + name)
    evidence["all_prior_sources_unchanged"] = len(registration["sources_sha256"])
    prior = plan["diagnostic_binding"]
    folder = Path(prior["root"])
    for name in ("completion", "result"):
        if digest(folder / (name + ".json")) != prior[name + "_sha256"]:
            raise ValueError("Diagnostic binding differs: " + name)
    done = json.loads((folder / "completion.json").read_text())
    if done["status"] != "completed" or (folder / "failure.json").exists():
        raise ValueError("Diagnostic incomplete")
    if digest(folder / "inputs.json") != done["inputs_sha256"]:
        raise ValueError("Diagnostic inputs differ")
    inputs = json.loads((folder / "inputs.json").read_text())
    if inputs["source_binding"] != binding or done["result_sha256"] != prior["result_sha256"]:
        raise ValueError("Diagnostic source differs")
    for name, sha in inputs["diagnostic_sources_sha256"].items():
        if digest(folder / "source" / name) != sha or digest(ROOT / name) != sha:
            raise ValueError("Diagnostic source changed: " + name)
    rule = registration["component_protocol"]
    if rule != assay.protocol():
        raise ValueError("Registered observation protocol differs")
    return evidence, rule


def analyze(plan):
    authentication, rule = authenticate(plan)
    root, design = Path(plan["source_binding"]["root"]), plan["design"]
    backends = {}
    for backend in ("cpu", "gpu"):
        print(
            json.dumps(dict(phase="calibration_only_ranking", backend=backend, utc=utc())),
            flush=True,
        )
        archive = root / "evidence" / backend / "source-order-spanning-readouts.npz"
        with np.load(archive, allow_pickle=False) as saved:
            rows, observations, accessed = load_calibration(saved, assay.cases(rule), rule, design)
        backends[backend] = rank_schedules(rows, observations, rule, design) | dict(
            calibration_rows=rows,
            archive_sha256=digest(archive),
            accessed_array_keys=accessed,
            decoded_calibration_arrays=len(accessed),
            heldout_arrays_decoded=0,
        )
    comparison = backend_comparison(backends["cpu"], backends["gpu"])
    return dict(
        status="completed",
        kind="source_order_calibration_observation_design_result@1",
        authentication=authentication,
        backends=backends,
        backend_comparison=comparison,
        new_simulations=0,
        heldout_evaluations=0,
        automatic_followup=False,
        limitations=[
            "Selection criterion describes fitted calibration polylines, not physical responses.",
            "A geometric improvement is not a newly confirmed accuracy or biological noise bound.",
            "Known held-out outcomes motivated this design; "
            "fresh strengths are needed to confirm it.",
            "Archive bytes were hashed for integrity; only calibration arrays were decoded.",
            "Saved CPU and L4 data analyzed on CPU; no new GPU utilization measurement.",
        ],
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args(argv)
    output = output_path(args.output)
    output.mkdir()
    started = time.monotonic()
    try:
        if digest(PLAN) != PLAN_SHA256:
            raise ValueError("Declared design plan changed")
        plan = json.loads(PLAN.read_text())
        sources = {}
        for name in (
            "validation/assays/source_order_observation_design.py",
            "tests/unit/test_source_order_observation_design.py",
            str(PLAN.relative_to(ROOT)),
        ):
            target = output / "source" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
            sources[name] = digest(target)
        write_json(
            output / "inputs.json",
            dict(
                started_utc=utc(),
                command=sys.argv,
                python=sys.version,
                numpy=np.__version__,
                plan=plan,
                plan_sha256=PLAN_SHA256,
                design_sources_sha256=sources,
            ),
        )
        result = analyze(plan)
        write_json(
            output / "result.json",
            result
            | dict(
                finished_utc=utc(),
                elapsed_seconds=time.monotonic() - started,
            ),
        )
        write_json(
            output / "selection.json",
            dict(
                status="frozen_before_any_evaluation",
                frozen_utc=utc(),
                plan_sha256=PLAN_SHA256,
                inputs_sha256=digest(output / "inputs.json"),
                result_sha256=digest(output / "result.json"),
                source_binding=plan["source_binding"],
                selection_rule=plan["design"],
                backend_comparison=result["backend_comparison"],
                selections={b: r["selection"] for b, r in result["backends"].items()},
                all_candidate_scores_V={
                    b: [dict(times_us=r["times_us"], score_V=r["score_V"]) for r in v["candidates"]]
                    for b, v in result["backends"].items()
                },
                heldout_evaluations=0,
                confirmation_protocol_ready=False,
                automatic_followup=False,
            ),
        )
        write_json(
            output / "completion.json",
            dict(
                status="completed",
                inputs_sha256=digest(output / "inputs.json"),
                result_sha256=digest(output / "result.json"),
                selection_sha256=digest(output / "selection.json"),
            ),
        )
    except BaseException as exc:
        write_json(
            output / "failure.json",
            dict(
                status="failed",
                error=str(exc),
                traceback=traceback.format_exc(),
                utc=utc(),
            ),
        )
        raise
    print(json.dumps(dict(status="completed", output=str(output))), flush=True)


if __name__ == "__main__":
    main()
