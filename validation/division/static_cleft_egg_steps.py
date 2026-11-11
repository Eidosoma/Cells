"""Static cleft egg on resolved_pump_tissue@3: definition check and step study (S0b step 3).

Engine model: resolved_pump_tissue@3, unmodified, as a plain definition. One egg-sized cell:
its old membrane faces a held Steinberg reservoir; its new-membrane patch, at the J1 default
area (1.39 mm2, fixed), faces a finite cleft node of volume w x one face, which has one
logmean_electrodiffusion@1 face to the reservoir with A/L and free-solution diffusivities.
The parameters are the registered J1 defaults (validation/division/j1_declared_inputs.json)
with P_old and A/L from R-full's prediction-of-record calibration (--record). There is no
insertion and no current injection (the family has no injection control; not added here).

Initial state: the cytosol at the declared composition and the old membrane's zero-current
potential; the cleft at bath composition with an uncharged new patch, so the cleft node starts
at the cytosol's potential and relaxes on the stiff membrane-cleft time scale (design note
5.4: dt x rate about 0.6-1.0 at 1 ms).

Parts (each writes <part>.json in --output):
  check      parse the definition for IMEX ARS(2,2,2) at 1, 0.5 and 0.25 ms and for RK4 at
             0.1 ms; refusals are results; reports @3's explicit-rate bound dt x rate
  run        one run (--solver imex|rk4, --dt) to --end: core/runner.run (host checks on every
             accepted row), then the device row checks and per-ledger ratios on every row
  rfull      R-full on the same static definition, for the engine-versus-reference check
  compare    the step study from the run files: errors against the finest run and R-full

Usage: python -m validation.division.static_cleft_egg_steps PART --output DIR --record FILE
       [--solver S --dt DT --end S]
"""

import argparse
import json
import math
import time
import traceback
from dataclasses import replace
from pathlib import Path

import jax
import numpy as np

jax.config.update("jax_enable_x64", True)

from cells.processes.electrochemistry import CHARGE_PER_FMOL  # noqa: E402
from validation.division import cleft_egg_reference as ref  # noqa: E402
from validation.tissue import egg_scale_smoke as smoke  # noqa: E402

SOLVERS = dict(imex="imex_ars222_face_electromigration@1", rk4="rk4")
FIELD_SOLVER = "capacitive_reduction_gauged_damped_newton@2"
FACE_LENGTH_M = 1.0e-6  # only area/length enters the face law


def observation_ms(end):
    """Dense early (the stiff transient), coarser later; whole milliseconds."""
    ms = list(range(0, 101)) + list(range(110, 1001, 10))
    ms += list(range(1100, int(round(end * 1000)) + 1, 100))
    return sorted({k for k in ms if k <= round(end * 1000)} | {int(round(end * 1000))})


def observation_times(end, dt=1e-3):
    """Observation times on the accepted grid of step dt: step index x dt, as the grid has them."""
    per_ms = 1e-3 / dt
    assert abs(per_ms - round(per_ms)) < 1e-9, dt
    return [round(k * per_ms) * dt for k in observation_ms(end)]


def static_egg(record_path):
    """The registered defaults at the J1 area, with the record's P_old and A/L (an Egg)."""
    d = ref.load_declared()
    values = ref.scalar_values(d)
    if record_path is None:
        p_old, al = 6.1537e-10, 1.6e-6  # provisional: definition checks only
    else:
        rec = json.loads(Path(record_path).read_text())
        p_old, al = rec["p_old_m_s"], rec["a_over_l_m"]
    egg = ref.build(d, values, p_old=p_old, a_over_l=al)
    area = values["new_membrane_area_at_j1_m2"]
    return replace(
        egg,
        onset_s=0.0,
        activation_area_m2=area,
        schedule=((0.0, 0.0),),
        pulses=replace(egg.pulses, enabled=False),
    ), d


def definition(egg, *, solver, dt, end, start=None):
    """The raw resolved_pump_tissue@3 definition of the static cleft egg.

    start None: the cytosol at its declared composition and zero-current potential, the cleft at
    bath composition with an uncharged new patch (the activation transient). start a J1 state
    from R-full (record's j1["at_j1"]): the cytosol and cleft compositions and node charges
    there, so the run starts near R-full's quasi-steady state at J1.
    """
    ids = list(ref.SPECIES)
    z = dict(zip(ids, ref.Z, strict=True))
    _, background_fmol, v0 = ref.initial_state(egg)
    cell_pL = egg.cytosol_volume_m3 * 1e15
    area = egg.activation_area_m2
    cleft_pL = egg.gap_width_m * area / 2.0 * 1e15
    if start is None:
        cytosol_mM, cleft_mM = egg.cytosol_mM, egg.bath_mM
        charge = egg.old_capacitance_F * v0  # the new patch starts uncharged
        cleft_charge = 0.0
    else:
        cytosol_mM, cleft_mM = start["cytosol_mM"], start["lumen_mM"]
        qi, qc = (start["state"][k] * ref.FMOL * ref.F for k in (ref.QI, ref.QC))
        charge, cleft_charge = qi, qc
    inside = {s: c * cell_pL for s, c in zip(ids, cytosol_mM, strict=True)}
    # Backgrounds from the rounded inventories, anchors from the exact sums (as stage 2).
    background = charge / CHARGE_PER_FMOL - math.fsum(z[s] * inside[s] for s in ids)
    anchor = CHARGE_PER_FMOL * math.fsum((background, *(z[s] * inside[s] for s in ids)))
    cleft = {s: c * cleft_pL for s, c in zip(ids, cleft_mM, strict=True)}
    cleft_background = cleft_charge / CHARGE_PER_FMOL - math.fsum(z[s] * cleft[s] for s in ids)
    cleft_anchor = CHARGE_PER_FMOL * math.fsum((cleft_background, *(z[s] * cleft[s] for s in ids)))
    bath = dict(zip(ids, egg.bath_mM, strict=True))
    always = [dict(time=0.0, availability=1.0)]
    times = observation_times(end, dt)
    raw = dict(
        schema_version=1,
        model=dict(
            id="resolved_pump_tissue@3",
            temperature_K=egg.temperature_K,
            species=[dict(id=s, valence=z[s]) for s in ids],
            cells=[
                dict(
                    id="egg",
                    volume_pL=cell_pL,
                    initial_amount_fmol=inside,
                    fixed_charge_equivalent_fmol=background,
                    initial_charge_C=anchor,
                )
            ],
            extracellular=[
                dict(
                    id="steinberg",
                    volume_pL=1.0,
                    initial_amount_fmol=dict(bath),
                    fixed_charge_equivalent_fmol=-math.fsum(z[s] * bath[s] for s in ids),
                    initial_charge_C=0.0,
                    reservoir=True,
                    boundary_potential_V=0.0,
                ),
                dict(
                    id="cleft",
                    volume_pL=cleft_pL,
                    initial_amount_fmol=cleft,
                    fixed_charge_equivalent_fmol=cleft_background,
                    initial_charge_C=cleft_anchor,
                    reservoir=False,
                    boundary_potential_V=0.0,
                ),
            ],
            membranes=[
                dict(
                    id="old_membrane",
                    inside="egg",
                    outside="steinberg",
                    area_m2=egg.old_area_m2,
                    capacitance_F=egg.old_capacitance_F,
                    permeability_m_per_s={
                        s: egg.p_old * w for s, w in zip(ids, egg.old_relative, strict=True)
                    },
                    law="constant_field@1",
                    pump=None,
                    calcium_pump=None,
                ),
                dict(
                    id="new_membrane",
                    inside="egg",
                    outside="cleft",
                    area_m2=area,
                    capacitance_F=egg.new_specific_capacitance_F_m2 * area,
                    permeability_m_per_s=dict(zip(ids, egg.new_permeability, strict=True)),
                    law="constant_field@1",
                    pump=None,
                    calcium_pump=None,
                ),
            ],
            junctions=[],
            faces=[
                dict(
                    id="access",
                    sender="cleft",
                    receiver="steinberg",
                    area_m2=egg.a_over_l_m * FACE_LENGTH_M,
                    length_m=FACE_LENGTH_M,
                    diffusivity_m2_per_s=dict(zip(ids, egg.access_D, strict=True)),
                    law="logmean_electrodiffusion@1",
                )
            ],
            closure=dict(
                law="resolved_capacitor_components_current_continuity@1", gauge_reference=None
            ),
            channels=[],
        ),
        experiment=dict(
            end_time=end,
            observation_times=times,
            membrane_controls=[
                dict(membrane_id=m, schedule=json.loads(json.dumps(always)))
                for m in ("old_membrane", "new_membrane")
            ],
            junction_controls=[],
            pump_controls=[],
            calcium_pump_controls=[],
            channel_controls=[],
        ),
        execution=dict(
            dt=dt,
            capacity=1,
            extracellular_capacity=2,
            membrane_capacity=2,
            edge_capacity=0,
            face_capacity=1,
            channel_capacity=0,
            backend="cpu",
            jit=True,
            precision="float64",
            solver=SOLVERS[solver],
            field_solver=FIELD_SOLVER,
            max_steps=int(math.ceil(end / dt)) + 8,
            max_trace_bytes=2**33,
            material_balance_atol_fmol={s: 1e-10 for s in ids},
        ),
    )
    inputs = dict(
        rest_V=v0,
        p_old_m_s=egg.p_old,
        new_permeability_m_s=list(egg.new_permeability),
        a_over_l_m=egg.a_over_l_m,
        new_area_m2=area,
        cleft_volume_pL=cleft_pL,
        capacitances_F=[egg.old_capacitance_F, egg.new_specific_capacitance_F_m2 * area],
        anchor_C=anchor,
        cleft_anchor_C=cleft_anchor,
        rfull_background_fmol=background_fmol,
    )
    return raw, inputs


def explicit_rate(spec):
    from cells.models import surface_pump as first

    return float(first.explicit_rate_bound(spec))


def start_state(args):
    """None (activation transient) or R-full's J1 state from record.json beside --record."""
    if args.start == "activation":
        return None
    full = json.loads((Path(args.record).parent / "record.json").read_text())
    return full["j1"]["at_j1"]


def part_check(args):
    """Parse each definition, then apply the runner's step checks (core/runner.timeline)."""
    from cells.core.runner import timeline
    from cells.core.specs import parse_spec

    egg, _ = static_egg(args.record)
    out = dict(cases=[])
    for solver, dt in (("imex", 1e-3), ("imex", 5e-4), ("imex", 2.5e-4), ("rk4", 1e-4)):
        raw, inputs = definition(egg, solver=solver, dt=dt, end=1.0)
        case = dict(solver=solver, dt=dt)
        try:
            spec = parse_spec(raw)
        except Exception as error:  # Kept: a refusal is the result.
            case.update(verdict="refused at definition", refusal=repr(error))
            out["cases"].append(case)
            continue
        case["explicit_rate_per_s"] = explicit_rate(spec)
        case["dt_x_rate"] = dt * case["explicit_rate_per_s"]
        try:
            timeline(spec)
            case["verdict"] = "accepted"
        except Exception as error:  # Kept: a refusal is the result.
            case.update(verdict="refused at step check", refusal=repr(error))
        out["cases"].append(case)
    out["inputs"] = inputs
    return out


def observed(result):
    obs = result.observations
    return dict(
        times_s=np.asarray(obs.times).tolist(),
        membrane_voltage_V=np.asarray(obs.membrane_voltage_V).tolist(),
        cell_potential_V=np.asarray(obs.cell_potential_V)[:, 0].tolist(),
        cleft_potential_V=np.asarray(obs.extracellular_potential_V)[:, 1].tolist(),
        cleft_amount_fmol=np.asarray(obs.extracellular_amount)[:, :, 1].tolist(),
        cell_amount_fmol=np.asarray(obs.amount)[:, :, 0].tolist(),
        field_charge_residual_C_max=float(np.max(np.abs(np.asarray(obs.charge_residual_C)))),
    )


def part_run(args):
    from cells.core.runner import run
    from cells.core.specs import parse_spec

    egg, _ = static_egg(args.record)
    raw, inputs = definition(
        egg, solver=args.solver, dt=args.dt, end=args.end, start=start_state(args)
    )
    out = dict(solver=args.solver, dt=args.dt, end=args.end, start=args.start, inputs=inputs)
    started = time.perf_counter()
    try:
        spec = parse_spec(raw)
        result = run(spec)
    except Exception as error:  # Kept: a refusal is the result.
        out.update(verdict="refused", refusal=repr(error), tb=traceback.format_exc())
        out["wall_s"] = time.perf_counter() - started
        return out
    out["host_checks"] = "passed (core/runner.run, every accepted row)"
    out["accepted_rows"] = len(result.times)
    out["host_diagnostics"] = {k: float(v) for k, v in result.diagnostics.items() if np.isscalar(v)}
    out["timings"] = dict(result.timings)
    out["observed"] = observed(result)
    out["device"] = smoke.device_rows(raw["model"]["id"], spec, result)
    out["verdict"] = (
        "accepted" if not out["device"]["device_failing_rows"] else "device check failed"
    )
    out["wall_s"] = time.perf_counter() - started
    return out


def rollout(spec):
    """The runner's own checked rollout (core/runner internals, read-only), without the host
    analysis that raises on the first failing ledger: returns (times, history, valid)."""
    from types import SimpleNamespace

    import jax as _jax

    from cells.core import runner
    from cells.core.schedule import control_values
    from cells.core.state import initialise
    from cells.models.registry import get_model

    model = get_model(spec.model)
    times = runner.timeline(spec)
    checkpoint = initialise(spec)
    state, layout = checkpoint.state, checkpoint.layout
    controls = control_values(spec, times[:-1])
    steps = runner.integration_steps(spec, times)
    args = (state, steps, controls, model.parameters(spec, layout), layout.active)
    compiled = runner._compiled_discrete_rollout.lower(*args, model.checked_step).compile()
    _, history, valid = compiled(*args)
    _jax.block_until_ready(history)
    arrays = tuple(
        np.concatenate((np.asarray(s)[None, :], np.asarray(h)), axis=0)
        for s, h in zip(state, history, strict=True)
    )
    return SimpleNamespace(
        times=times, history=type(state)(*arrays), start_step=0, valid=np.asarray(valid)
    )


def part_diagnose(args):
    """Every row's ledger residual over its bound (the smoke driver's device rows), so a refusal
    by the host checks is quantified rather than only named."""
    from cells.core.specs import parse_spec

    egg, _ = static_egg(args.record)
    raw, inputs = definition(
        egg, solver=args.solver, dt=args.dt, end=args.end, start=start_state(args)
    )
    spec = parse_spec(raw)
    started = time.perf_counter()
    result = rollout(spec)
    out = dict(solver=args.solver, dt=args.dt, end=args.end, start=args.start, inputs=inputs)
    out["refused_steps"] = int(np.count_nonzero(~result.valid))
    out["device"] = smoke.device_rows(raw["model"]["id"], spec, result)
    failing = out["device"]["device_failing_rows"]
    out["first_failing_time_s"] = float(result.times[failing[0]]) if failing else None
    out["wall_s"] = time.perf_counter() - started
    return out


def part_rfull(args):
    egg, _ = static_egg(args.record)
    times = observation_times(args.end)
    run = ref.simulate(egg, args.end, record=tuple(times), method="Radau", rtol=1e-10)
    rows = [run.at[t] for t in times]
    return dict(
        times_s=times,
        cell_potential_V=[r["V"] for r in rows],
        cleft_potential_V=[r["phi_lumen"] for r in rows],
        new_membrane_voltage_V=[r["v_new"] for r in rows],
        cleft_mM=[r["lumen_mM"] for r in rows],
        steps=run.steps,
        wall_s=run.wall_s,
    )


def part_compare(args):
    """Errors of each run against the finest run and against R-full (files in --output)."""
    folder = Path(args.output)
    runs = {}
    for path in sorted(folder.glob("run_*.json")):
        r = json.loads(path.read_text())
        if r.get("verdict") == "accepted":
            runs[path.stem] = r
    rfull = (
        json.loads((folder / "rfull.json").read_text())
        if (folder / "rfull.json").exists()
        else None
    )
    if not runs:
        return dict(note="no accepted runs")
    finest = min(runs, key=lambda k: runs[k]["dt"])
    t_ref = np.asarray(runs[finest]["observed"]["times_s"])

    def series(r):
        o = r["observed"]
        return np.asarray(o["cell_potential_V"]), np.asarray(o["cleft_potential_V"])

    vi_ref, vc_ref = series(runs[finest])
    out = dict(finest=finest, against_finest={}, against_rfull={})
    for name, r in runs.items():
        vi, vc = series(r)
        assert np.allclose(np.asarray(r["observed"]["times_s"]), t_ref, rtol=0, atol=1e-12)
        early = t_ref <= 0.1
        out["against_finest"][name] = dict(
            dt=r["dt"],
            max_cell_V=float(np.max(np.abs(vi - vi_ref))),
            max_cleft_V=float(np.max(np.abs(vc - vc_ref))),
            max_cleft_V_after_100ms=float(np.max(np.abs((vc - vc_ref)[~early]))),
            end_cell_V=float(abs(vi[-1] - vi_ref[-1])),
        )
        if rfull is not None:
            ti = np.asarray(rfull["times_s"])
            assert np.allclose(ti, t_ref, rtol=0, atol=1e-12)
            out["against_rfull"][name] = dict(
                max_cell_V=float(np.max(np.abs(vi - np.asarray(rfull["cell_potential_V"])))),
                max_cleft_V=float(np.max(np.abs(vc - np.asarray(rfull["cleft_potential_V"])))),
            )
    return out


PARTS = dict(
    check=part_check, run=part_run, diagnose=part_diagnose, rfull=part_rfull, compare=part_compare
)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("part", choices=sorted(PARTS))
    parser.add_argument("--output", required=True)
    parser.add_argument("--record", default=None)
    parser.add_argument("--solver", choices=sorted(SOLVERS), default="imex")
    parser.add_argument("--dt", type=float, default=1e-3)
    parser.add_argument("--end", type=float, default=10.0)
    parser.add_argument("--start", choices=("activation", "j1"), default="activation")
    args = parser.parse_args(argv)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    try:
        result = PARTS[args.part](args)
    except Exception as error:  # Kept as the part's result.
        result = dict(verdict="error", error=repr(error), tb=traceback.format_exc())
    result["provenance"] = smoke.provenance()
    result["part_wall_s"] = time.perf_counter() - started
    name = (
        args.part
        if args.part not in ("run", "diagnose", "rfull")
        else f"{args.part}_{args.start}"
        + ("" if args.part == "rfull" else f"_{args.solver}_{args.dt:g}")
    )
    (output / f"{name}.json").write_text(json.dumps(result, indent=1, default=float) + "\n")
    print(name, result.get("verdict", "done"), f"{result['part_wall_s']:.1f} s", flush=True)


if __name__ == "__main__":
    main()
