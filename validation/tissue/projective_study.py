"""Development studies of the projective mode (core/projective.py) against fine stepping.

Each case runs one definition twice from the same initial state: projective
(execution.projective, the ordinary runner) and fine (the same definition
without the block). The fine reference here is a development harness: the
same compiled checked-step burst kernel as the projective bursts
(core/projective._Bursts.advance), with the model's per-row check_values
omitted, so rows before the first jump agree bitwise and long references stay
affordable. A judged comparison uses a fully checked fine run instead.

Compared at every observation time (fine rows in both runs): the error
coordinates of models/surface_pump_projective.py (concentrations, membrane
voltages, gates). The estimate-based allowance of class q at time t is
S * tol_q * sum of estimate_normalized over the jumps accepted before t
(numerics/projective.error_estimate; S = ESTIMATE_FACTOR). Also written: the
projective report (jumps, rejections, fallbacks, energy defects, linear-ledger
records), step and wall-time speed-ups, and the fine engine diagnostics.

Protocol cases (--protocol, a registered cells.protocol@1 such as
validation/tissue/protocols/projective_c_qualification_v1.json): each named case
is built from the protocol, never from the command line: its world (the driver
case of PROTOCOL_WORLDS), horizon, window, observation spacing, the protocol's
projective_parameters (burst, slope, jump rule, tolerance, safety, row checks)
and the case's tolerance_override. Each projective part records whether the
case's absolute caps (criteria.absolute_caps) are judged or, for Q1L, reported
(REPORTED_CAPS); validation/tissue/projective_judge.py evaluates them. Cases
this driver cannot build are refused. A protocol run is one part
of one case per process (--part):
  projective  the definition through cells.core.runner.run (every accepted row
              checked); saves the projective report, the error coordinates at
              every observation, fine-row switch times and wall time.
  reference   the checked fine reference (protocol reference.fine): the same
              definition without execution.projective through
              cells.core.windows.run_windowed, every row checked; saves the
              coordinates at every observation, its wall time, fine-row switch
              times and, for every row, max over patches of |dVm/dt| (the
              backward difference over the step ending at that row; amendment 1)
              in <case>-reference-rates.npz. Cases with the same fine definition
              (Q1, Q1L) share one reference; validation/tissue/projective_judge.py
              pairs them by the fine definition's digest.
F2-near-fold needs --f2-prescan, the recorded pre-scan whose selected NaV1.2
scale it runs (validation/tissue/projective_prescan.py); the scale and the
pre-scan file's digest are saved with each part. The run label
Q2-relax-world-5cell is Q2 on its pre-approved 5-cell world (amendment 2), run
only if the 7-cell Q2 is refused on global charge.

Usage:
  python -m validation.tissue.projective_study CASE [CASE ...] --output DIR
      [--end SECONDS] [--every SECONDS]
  python -m validation.tissue.projective_study --protocol PROTOCOL.json --part PART
      CASE_ID --output DIR
"""

import argparse
import hashlib
import json
import resource
import time
import traceback
from pathlib import Path

import jax
import numpy as np

jax.config.update("jax_enable_x64", True)

from cells.core.grid import EventGrid  # noqa: E402
from cells.core.projective import ROW_FINE, _Bursts  # noqa: E402
from cells.core.runner import run  # noqa: E402
from cells.core.specs import parse_spec  # noqa: E402
from cells.core.state import initialise  # noqa: E402
from cells.models import surface_pump_projective as readouts  # noqa: E402
from cells.models import surface_tissue as tissue  # noqa: E402
from cells.models.registry import get_model  # noqa: E402
from cells.numerics import surface_field as field  # noqa: E402
from cells.processes.electrochemistry import CHARGE_PER_FMOL  # noqa: E402
from validation.tissue import projective_fixtures as fixtures  # noqa: E402

ESTIMATE_FACTOR = 2.0  # Allowance / summed first-order local-error estimates.
# Protocol case id -> driver world. Cases absent here are not runnable on this driver.
PROTOCOL_WORLDS = {
    "Q1-relax-pair": "relax3",
    "Q1L-relax-pair-loose": "relax3",
    "F1-cue-in-window": "cue3",
    "A1-pump-pair": "pair1",
    "Q2-relax-world": "world7",
    "F2-near-fold": "fold1",
}
# Run labels other than a case id: (protocol case, driver world). Amendment 2: Q2's
# 5-cell world runs only if the 7-cell Q2 is refused on global charge.
PROTOCOL_VARIANTS = {"Q2-relax-world-5cell": ("Q2-relax-world", "world5")}
# criteria.absolute_caps: "All cases except Q1L"; Q1L's purpose: "the absolute caps
# are reported, not judged".
REPORTED_CAPS = frozenset({"Q1L-relax-pair-loose"})
REFERENCE_WIDTH = 5000  # Fine steps per reference burst.


def case_pair1(args):
    """@1: an H-composition cell and a Na-loaded cell, each with its own held bath."""
    end = args.end
    raw = fixtures.pump_cells(
        [fixtures.H, fixtures.LOADED],
        end_time=end,
        observation_times=fixtures.grid_times(1e-3, end, args.every),
    )
    raw["execution"]["projective"] = fixtures.projective_block(
        [(10.0, end)],
        burst_steps=args.burst,
        slope_steps=args.slope,
        max_steps=args.max_steps,
        tolerance=_tolerance(args),
    )
    return raw


def case_cue1(args):
    """@1 pair with a pump block (availability 0.3) for 5 s inside the window."""
    end = args.end
    cue = round(0.5 * end)
    raw = fixtures.pump_cells(
        [fixtures.H, fixtures.LOADED],
        end_time=end,
        observation_times=fixtures.grid_times(1e-3, end, args.every),
        pump_controls={0: [(0.0, 1.0), (float(cue), 0.3), (float(cue + 5), 1.0)]},
    )
    raw["execution"]["projective"] = fixtures.projective_block(
        [(10.0, end)],
        burst_steps=args.burst,
        slope_steps=args.slope,
        max_steps=args.max_steps,
        tolerance=_tolerance(args),
    )
    return raw


def case_closed1(args):
    """@1 closed synthetic tissue: junction gate, faces, finite outside nodes."""
    end = args.end
    raw = fixtures.closed_tissue(
        end_time=end, observation_times=fixtures.grid_times(1e-3, end, args.every)
    )
    raw["execution"]["projective"] = fixtures.projective_block(
        [(5.0, end)],
        burst_steps=args.burst,
        slope_steps=args.slope,
        max_steps=args.max_steps,
        tolerance=_tolerance(args),
    )
    return raw


def _heredity(args, cells, *, cue=None):
    """@3 heredity cells (surface_pump_v3_fixtures.heredity_cells) with a projective block.

    cue: optional (start, stop) of a 9x Na-leak cue on cell 0 (a NaLeak channel
    switched on and off by its schedule), as in surface_pump_v3_study.
    """
    from cells.core.surface_pump_v3_spec import NALEAK_LAW_ID
    from validation.tissue import surface_pump_v3_fixtures as heredity

    end = args.end
    raw = heredity.heredity_cells(
        [c[:4] for c in cells],
        end_time=end,
        observation_times=fixtures.grid_times(1e-3, end, args.every),
        gate_voltages=[c[0] for c in cells],
    )
    if cue is not None:
        raw["model"]["channels"].append(
            dict(
                id="cue_0",
                membrane_id="membrane_0",
                kinetic_law=NALEAK_LAW_ID,
                max_permeability_m_per_s=9 * heredity.HEREDITY_PERMEABILITY["Na"],
                abundance=1.0,
                initial_gate=[],
                permeant_ions=[dict(species_id="Na", relative_permeability=1.0)],
            )
        )
        raw["experiment"]["channel_controls"].append(
            dict(
                channel_id="cue_0",
                schedule=[
                    dict(time=0.0, availability=0.0),
                    dict(time=cue[0], availability=1.0),
                    dict(time=cue[1], availability=0.0),
                ],
            )
        )
        raw["execution"]["channel_capacity"] += 1
    raw["execution"]["projective"] = fixtures.projective_block(
        [(args.window_start, end)],
        burst_steps=args.burst,
        slope_steps=args.slope,
        max_steps=args.max_steps,
        tolerance=_tolerance(args),
        row_checks=args.row_checks,
    )
    return raw


def _near_saddle():
    from validation.tissue import surface_pump_v3_fixtures as heredity

    u = heredity.HEREDITY_STATES["U"]
    return [(u[0] - 0.002, *u[1:4]), (u[0] + 0.002, *u[1:4])]


def case_relax3(args):
    """@3 pair started at the saddle composition, +-2 mV: slow relaxation on both branches."""
    return _heredity(args, _near_saddle())


def case_cue3(args):
    """relax3 with a 0.3 s 9x Na-leak cue on cell 0 at mid-horizon, inside the window."""
    start = round(0.5 * args.end, 3)
    return _heredity(args, _near_saddle(), cue=(start, round(start + 0.3, 3)))


def case_world7(args):
    """@3 seven independent cells: U -+2 mV, U -+5 mV, H, D and H kicked by +10 mV."""
    from validation.tissue import surface_pump_v3_fixtures as heredity

    states = heredity.HEREDITY_STATES
    u, h, d = states["U"][:4], states["H"][:4], states["D"][:4]
    cells = [(u[0] + dv, *u[1:]) for dv in (-0.002, 0.002, -0.005, 0.005)]
    cells += [h, d, (h[0] + 0.010, *h[1:])]
    return _heredity(args, cells)


def case_world5(args):
    """Q2's pre-approved fallback (amendment 2): U -+2 mV, U -+5 mV and D."""
    from validation.tissue import surface_pump_v3_fixtures as heredity

    states = heredity.HEREDITY_STATES
    u, d = states["U"][:4], states["D"][:4]
    cells = [(u[0] + dv, *u[1:]) for dv in (-0.002, 0.002, -0.005, 0.005)] + [d]
    return _heredity(args, cells)


def case_fold1(args):
    """F2: one D-branch cell with NaV1.2 scaled by args.f2_scale (the recorded pre-scan)."""
    from validation.tissue import projective_prescan as prescan

    if getattr(args, "f2_scale", None) is None:
        raise ValueError("F2 needs the NaV1.2 scale selected by its recorded pre-scan")
    raw = prescan.f2_definition(args.f2_scale, end_time=args.end, every=args.every)
    raw["execution"]["projective"] = fixtures.projective_block(
        [(args.window_start, args.end)],
        burst_steps=args.burst,
        slope_steps=args.slope,
        max_steps=args.max_steps,
        tolerance=_tolerance(args),
        row_checks=args.row_checks,
    )
    return raw


def _tolerance(args):
    return dict(
        concentration_mM=args.tol_concentration,
        membrane_voltage_V=args.tol_voltage,
        gate=args.tol_gate,
    )


CASES = dict(
    pair1=case_pair1,
    cue1=case_cue1,
    closed1=case_closed1,
    relax3=case_relax3,
    cue3=case_cue3,
    world7=case_world7,
    world5=case_world5,
    fold1=case_fold1,
)


def protocol_case(protocol, label, *, f2_scale=None):
    """(driver world, argparse-like settings, projective block, case) of a protocol run.

    label is a case id or a PROTOCOL_VARIANTS label; f2_scale is F2's NaV1.2 scale.
    """
    case_id, world = PROTOCOL_VARIANTS.get(label, (label, PROTOCOL_WORLDS.get(label)))
    cases = {c["id"]: c for c in protocol["cases"]}
    if case_id not in cases:
        raise ValueError(f"{case_id} is not a case of {protocol['id']}")
    if world is None:
        raise ValueError(f"{label}: this driver has no world for it (not runnable)")
    if case_id == "F2-near-fold" and f2_scale is None:
        raise ValueError("F2 needs the NaV1.2 scale selected by its recorded pre-scan")
    case, params = cases[case_id], protocol["projective_parameters"]
    (start, stop), = case["windows"]  # fmt: skip
    if stop != case["horizon_s"]:
        raise ValueError(f"{case_id}: a window must end at the horizon")
    tolerance = dict(params["tolerance"]) | dict(case.get("tolerance_override", {}))
    jump = params["jump"]
    block = fixtures.projective_block(
        [(float(start), float(stop))],
        burst_steps=params["burst_steps"],
        slope_steps=params["slope_steps"],
        rule=jump["rule"],
        max_steps=jump["max_steps"],
        min_steps=jump["min_steps"],
        max_growth=jump["max_growth"],
        safety_factor=jump["safety_factor"],
        tolerance=tolerance,
        safety=params["safety"],
        row_checks=params["row_checks"].split()[0],
    )
    settings = argparse.Namespace(
        end=float(case["horizon_s"]),
        every=float(case["observation_every_s"]),
        window_start=float(start),
        burst=params["burst_steps"],
        slope=params["slope_steps"],
        max_steps=jump["max_steps"],
        tol_concentration=tolerance["concentration_mM"],
        tol_voltage=tolerance["membrane_voltage_V"],
        tol_gate=tolerance["gate"],
        row_checks=block["row_checks"],
        f2_scale=f2_scale,
    )
    return world, settings, block, case


def protocol_definition(protocol, label, *, f2_scale=None):
    """The run's definition: the driver world with the protocol's projective block."""
    world, settings, block, case = protocol_case(protocol, label, f2_scale=f2_scale)
    raw = CASES[world](settings)
    raw["execution"]["projective"] = block  # Exactly the protocol's parameters.
    return raw, case


SWITCH_V = -0.050  # near_fold_accuracy: switch time, first fine row with Vm < -50 mV.
REFERENCE_WINDOW_STEPS = 3000  # Rows per checked window of the fine reference.


def fine_definition(raw):
    """The same definition without execution.projective (protocol reference.fine)."""
    return dict(raw, execution={k: v for k, v in raw["execution"].items() if k != "projective"})


def definition_digest(raw):
    return hashlib.sha256(json.dumps(raw, sort_keys=True).encode()).hexdigest()


def voltage_map(p):
    """(initial Vm, A): active patch voltages are initial + A @ q, q the node charge increments.

    The capacitor map of surface_tissue.capacitor_change (models/surface_pump_projective
    membrane_voltage), linear in q, applied to unit charges once.
    """
    layout = tissue.field_layout(p)
    size, n = layout.active.size, p.active.size
    active = np.asarray(p.membrane_active, dtype=bool)
    columns = []
    for j in range(size):
        unit = np.zeros(size)
        unit[j] = 1.0
        dp = field._capacitor_solve(unit, np.zeros(size), layout, xp=np)
        columns.append((dp[p.membrane_cell] - dp[n + p.membrane_outside])[active])
    return np.asarray(p.initial_membrane_voltage_V)[active], np.stack(columns, axis=1)


def row_voltages(rows, p, vmap):
    """Active patch voltages (V) of every row of a [row, ...] state history."""
    initial, matrix = vmap
    z = np.asarray(p.valence).reshape(-1)
    q = CHARGE_PER_FMOL * np.concatenate(
        (
            np.einsum("s,rsn->rn", z, np.asarray(rows.amount_increment)),
            np.einsum("s,rsn->rn", z, np.asarray(rows.extracellular_amount_increment)),
        ),
        axis=1,
    )
    return initial + q @ matrix.T


def first_below(times, voltages, level=SWITCH_V):
    """Per patch, the time of the first row with Vm < level (None if none)."""
    out = []
    for k in range(voltages.shape[1]):
        hits = np.flatnonzero(voltages[:, k] < level)
        out.append(float(times[hits[0]]) if len(hits) else None)
    return out


def _observed(model, spec, p, times, rows, kinds=None):
    """Error coordinates at every observation time (fine rows) of a run's rows."""
    out = []
    for t in spec.experiment.observation_times:
        hits = np.flatnonzero(times == t)
        if not len(hits):
            continue
        i = int(hits[0])
        if kinds is not None and kinds[i] != ROW_FINE:
            raise ValueError(f"observation {t} s is not a fine row")
        row = type(rows)(*(np.asarray(v[i]) for v in rows))
        coords = readouts.coordinates(model, row, p)
        out.append(dict(time_s=float(t), **{k: v.tolist() for k, v in coords.items()}))
    return out


def protocol_reference(protocol, case_id, *, f2_scale=None):
    """The checked fine reference of a protocol run (one process, detached)."""
    from cells.core.windows import WindowPolicy, run_windowed

    raw, case = protocol_definition(protocol, case_id, f2_scale=f2_scale)
    fine = fine_definition(raw)
    spec = parse_spec(fine)
    model = get_model(spec.model)
    p = readouts.host_layout(initialise(spec).layout)
    vmap = voltage_map(p)
    grid = EventGrid(spec)
    rate = np.zeros(len(grid))
    threshold = protocol["projective_parameters"]["safety"]["max_membrane_voltage_rate_V_per_s"]
    switch = [None] * len(vmap[0])
    observations, diagnostics, windows = [], {}, [0]

    def sink(result):
        times = np.asarray(result.times)
        first = grid.exact_index(float(times[0]))
        vm = row_voltages(result.history, p, vmap)
        if len(times) > 1:
            dv = np.max(np.abs(np.diff(vm, axis=0)), axis=1, initial=0.0)
            rate[first + 1 : first + len(times)] = dv / np.diff(times)
        for k, t in enumerate(first_below(times, vm)):
            if switch[k] is None and t is not None:
                switch[k] = t
        observations.extend(
            o
            for o in _observed(model, spec, p, times, result.history)
            if not observations or o["time_s"] > observations[-1]["time_s"]
        )
        for name, value in result.diagnostics.items():
            if np.isscalar(value):
                diagnostics[name] = max(diagnostics.get(name, -np.inf), float(value))
        windows[0] += 1

    started = time.perf_counter()
    run_windowed(spec, WindowPolicy(REFERENCE_WINDOW_STEPS, "observations"), sink=sink)
    wall = time.perf_counter() - started
    above = np.flatnonzero(rate > threshold)
    return dict(
        part="reference",
        case=case_id,
        protocol=protocol["id"],
        fine_definition_sha256=definition_digest(fine),
        definition=fine,
        wall_s=wall,
        windows=windows[0],
        window_steps=REFERENCE_WINDOW_STEPS,
        steps=len(grid) - 1,
        diagnostics=diagnostics,
        observations=observations,
        switch_below_m50mV_s=switch,
        rate_threshold_V_per_s=threshold,
        rows_above_threshold=int(len(above)),
        max_rate_V_per_s=float(rate.max(initial=0.0)),
        peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
    ), dict(max_abs_dvm_dt_V_per_s=rate, times_s=np.asarray([grid[k] for k in range(len(grid))]))


def protocol_projective(protocol, case_id, *, f2_scale=None):
    """The projective run of a protocol run (one process, detached)."""
    raw, case = protocol_definition(protocol, case_id, f2_scale=f2_scale)
    spec = parse_spec(raw)
    started = time.perf_counter()
    result = run(spec)
    wall = time.perf_counter() - started
    model = get_model(spec.model)
    p = readouts.host_layout(result.final.layout)
    vm = row_voltages(result.history, p, voltage_map(p))
    fine = np.asarray(result.row_kinds) == ROW_FINE
    report = dict(result.projective)
    return dict(
        part="projective",
        case=case_id,
        protocol=protocol["id"],
        protocol_case=case,
        caps_judged=case["id"] not in REPORTED_CAPS,
        definition=raw,
        fine_definition_sha256=definition_digest(fine_definition(raw)),
        wall_s=wall,
        timings=result.timings,
        diagnostics=result.diagnostics,
        rows=int(len(result.times)),
        fine_rows=int(np.count_nonzero(fine)),
        observations=_observed(
            model, spec, p, np.asarray(result.times), result.history, np.asarray(result.row_kinds)
        ),  # fmt: skip
        switch_below_m50mV_s=first_below(np.asarray(result.times)[fine], vm[fine]),
        report=report,
        peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
    )


def run_protocol_part(protocol, part, case_id, output, *, f2_scale=None, prescan=None):
    """Run one part of one run; write <label>-<part>.json, or <label>-<part>-failure.json.

    prescan: provenance of F2's scale (the pre-scan file and its digest).
    """
    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    began = time.perf_counter()
    raw, _ = protocol_definition(protocol, case_id, f2_scale=f2_scale)
    digest = definition_digest(fine_definition(raw))
    try:
        if part == "reference":
            entry, arrays = protocol_reference(protocol, case_id, f2_scale=f2_scale)
            np.savez_compressed(out / f"{case_id}-reference-rates.npz", **arrays)
        else:
            entry = protocol_projective(protocol, case_id, f2_scale=f2_scale)
        entry["seconds"] = time.perf_counter() - began
        entry.update(f2_scale=f2_scale, prescan=prescan)
        path = out / f"{case_id}-{part}.json"
    except Exception as error:  # A failure or refusal is a result; keep it.
        entry = dict(
            part=part,
            case=case_id,
            fine_definition_sha256=digest,
            status="failed",
            error=repr(error),
            traceback=traceback.format_exc(),
            seconds=time.perf_counter() - began,
            peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
        )
        path = out / f"{case_id}-{part}-failure.json"
    else:
        entry["status"] = "completed"
    with open(path, "x") as stream:  # Never overwrite a result.
        stream.write(json.dumps(entry, indent=1, default=_json) + "\n")
    print(json.dumps(dict(case=case_id, part=part, status=entry["status"], path=str(path))))
    return entry


def fine_reference(spec, times):
    """States at the given grid times from unchecked fine bursts (development harness)."""
    from cells.core.grid import EventGrid

    model = get_model(spec.model)
    checkpoint = initialise(spec)
    grid = EventGrid(spec)
    bursts = _Bursts(spec, model, checkpoint.layout, REFERENCE_WIDTH)
    state, index, last = checkpoint.state, 0, len(grid) - 1
    targets = {grid.exact_index(t): t for t in times}
    rows = {}
    if 0 in targets:
        rows[targets[0]] = model.STATE_TYPE(*(np.asarray(v) for v in state))
    started = time.perf_counter()
    while index < last:
        count = min(REFERENCE_WIDTH, last - index)
        stamps = np.fromiter((grid[k] for k in range(index, index + count + 1)), np.float64)
        state, burst = bursts.advance(state, stamps)
        for k in range(1, count + 1):
            if index + k in targets:
                rows[targets[index + k]] = type(burst)(*(np.asarray(v[k]) for v in burst))
        index += count
    timing = dict(
        compile_seconds=bursts.compile_seconds,
        execute_seconds=bursts.execute_seconds,
        total_seconds=time.perf_counter() - started,
        steps=last,
    )
    return rows, timing


def compare(spec, result, rows):
    """Development mode: per observation, errors and estimate-based allowances."""
    model, p = get_model(spec.model), readouts.host_layout(result.final.layout)
    tolerance = {k: getattr(spec.projective.tolerance, k) for k in readouts.COORDINATES}
    jumps = result.projective["jump_log"]
    table = []
    for t in spec.experiment.observation_times:
        i = int(np.flatnonzero(result.times == t)[0])
        mine = readouts.coordinates(model, type(rows[t])(*(v[i] for v in result.history)), p)
        theirs = readouts.coordinates(model, rows[t], p)
        estimate = sum(j["estimate_normalized"] for j in jumps if j["to_time_s"] <= t)
        entry = dict(time_s=t, kind=int(result.row_kinds[i]), estimate_sum=estimate)
        for k in readouts.COORDINATES:
            error = float(np.max(np.abs(mine[k] - theirs[k]), initial=0.0))
            allowance = ESTIMATE_FACTOR * tolerance[k] * estimate
            entry[k] = dict(error=error, allowance=allowance)
        table.append(entry)
    worst = {
        k: dict(
            max_error=max(e[k]["error"] for e in table),
            max_ratio=max(
                (e[k]["error"] / e[k]["allowance"] if e[k]["allowance"] > 0 else
                 (np.inf if e[k]["error"] > 0 else 0.0))
                for e in table
            ),
        )
        for k in readouts.COORDINATES
    }  # fmt: skip
    return table, worst


def summary(report):
    ledgers = {}
    for jump in report["jump_log"]:
        for name, value in jump["ledgers"].items():
            entry = ledgers.setdefault(name, dict(max_after=0.0, max_affine_excess=0.0))
            entry["max_after"] = max(entry["max_after"], value["after"])
            entry["max_affine_excess"] = max(entry["max_affine_excess"], value["affine_excess"])
    jumps = report["jump_log"]
    return dict(
        ledgers=ledgers,
        max_energy_defect_ratio=max(
            (j["energy_defect_pJ"] / j["energy_bound_pJ"] for j in jumps), default=0.0
        ),
        max_correction=max((j["correction_normalized"] for j in jumps), default=0.0),
        max_estimate=max((j["estimate_normalized"] for j in jumps), default=0.0),
        jump_seconds=[j["to_time_s"] - j["from_time_s"] for j in jumps],
    )


def run_case(name, args):
    """Development mode: a driver case against the unchecked fine harness."""
    raw = CASES[name](args)
    spec = parse_spec(raw)
    fine = dict(raw, execution={k: v for k, v in raw["execution"].items() if k != "projective"})
    fine_spec = parse_spec(fine)
    out = Path(args.output)
    started = time.perf_counter()
    result = run(spec)
    projective_wall = time.perf_counter() - started
    rows, reference_timing = fine_reference(fine_spec, spec.experiment.observation_times)
    table, worst = compare(spec, result, rows)
    report = dict(result.projective)
    entry = dict(
        case=name,
        definition=raw,
        projective_wall_s=projective_wall,
        projective_timings=result.timings,
        reference_timing=reference_timing,
        diagnostics=result.diagnostics,
        comparison=table,
        worst=worst,
        estimate_factor=ESTIMATE_FACTOR,
        summary=summary(report),
        report=report,
        peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
    )
    (out / f"{name}.json").write_text(json.dumps(entry, indent=1, default=_json) + "\n")
    return dict(
        case=name,
        fine_steps=report["fine_steps"],
        jumped_steps=report["jumped_steps"],
        step_speedup=report["step_speedup"],
        jumps=report["jumps"],
        rejections=report["rejections"],
        fallbacks=report["fallback_counts"],
        worst=worst,
    )


def _json(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.floating, np.integer, np.bool_)):
        return value.item()
    if isinstance(value, complex):
        return [value.real, value.imag]
    return str(value)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("cases", nargs="+")
    parser.add_argument("--protocol", help="build the named protocol cases from this file")
    parser.add_argument("--part", choices=("projective", "reference"))
    parser.add_argument("--f2-prescan", help="F2: the recorded pre-scan (prescan.json)")
    parser.add_argument("--output", required=True)
    parser.add_argument("--end", type=float, default=300.0)
    parser.add_argument("--every", type=float, default=30.0)
    parser.add_argument("--burst", type=int, default=2000)
    parser.add_argument("--slope", type=int, default=250)
    parser.add_argument("--max-steps", type=int, default=60000)
    parser.add_argument("--tol-concentration", type=float, default=1e-3)
    parser.add_argument("--tol-voltage", type=float, default=1e-5)
    parser.add_argument("--tol-gate", type=float, default=1e-4)
    parser.add_argument("--window-start", type=float, default=3.0)
    parser.add_argument("--row-checks", choices=("host", "device"), default="host")
    args = parser.parse_args()
    args.protocol_document = None
    if args.protocol:
        args.protocol_document = json.loads(Path(args.protocol).read_text())
        scale, prescan = None, None
        if args.f2_prescan:
            text = Path(args.f2_prescan).read_bytes()
            scale = json.loads(text)["selected_scale"]
            if scale is None:
                parser.error("the pre-scan selected no NaV1.2 scale")
            prescan = dict(
                path=str(Path(args.f2_prescan).resolve()),
                sha256=hashlib.sha256(text).hexdigest(),
            )
        for name in args.cases:  # Refuse before anything runs.
            protocol_case(args.protocol_document, name, f2_scale=scale)
        if args.part is None or len(args.cases) != 1:
            parser.error("--protocol runs one --part of one case per process")
        run_protocol_part(
            args.protocol_document,
            args.part,
            args.cases[0],
            args.output,
            f2_scale=scale,
            prescan=prescan,
        )
        return
    if not set(args.cases) <= set(CASES):
        parser.error(f"cases must be among {sorted(CASES)} without --protocol")
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    status = {}
    for name in args.cases:
        began = time.perf_counter()
        try:
            status[name] = dict(status="completed", **run_case(name, args))
        except Exception as error:  # A failure is a result; keep it.
            status[name] = dict(
                status="failed", error=repr(error), traceback=traceback.format_exc()
            )
        status[name]["seconds"] = time.perf_counter() - began
        print(json.dumps({name: status[name]}, default=_json), flush=True)
    outcome = "failure" if any(v["status"] == "failed" for v in status.values()) else "result"
    (out / f"{outcome}.json").write_text(
        json.dumps(dict(cases=status, argv=vars(args)), indent=1, default=_json) + "\n"
    )


if __name__ == "__main__":
    main()
