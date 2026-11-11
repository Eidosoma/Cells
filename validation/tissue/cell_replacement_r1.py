"""R1: resolved_pump_replacement@1 against pre-screen 9's driver-based turnover (development).

Regression of the engine operation against frozen evidence, not a qualification.
Engine model: resolved_pump_replacement@1 (inner resolved_pump_tissue@3), its own
checked_step in a plain jitted loop with no row checks, as the pre-screen's driver
stepped @3 through the analysis step map. The design note (R1) explains why the
analysis harness itself cannot run the wrapper.

Reproduced from validation/stationary/heredity_turnover.py (pre-screen 9, stage 2):
- world: 127-cell sheet, 37-cell written disc, E07 voltage-gated junctions, held
  baths, dt 5 ms, coupling scale s through the analysis parameter;
- start: the stationary disc of heredity_conversion.disc_state, embedded by the
  analysis (ledgers zero); the inner layout is the analysis layout at s;
- events: the driver's schedule (heredity_turnover.schedule), the same steps and
  slots; newcomer: the sheet's H initial state (an isolated_template from cell 0's
  declared state);
- rule (a), the driver's "open": A0 1, lag 0, gate_at_arrival law_open;
- records every 10 s, taken before an event at the same step: the D set (Vm above
  the U voltage) and the written disc's voltage range; the run stops at the first
  record with no D cell, as the driver's did.

Criteria (criteria.json, written by --criteria before any run):
- identical D-set strings at every record, and an identical stop time;
- the written disc's voltage range within 1 uV per record;
- otherwise the first divergence is reported (time, slots, largest voltage
  difference). The pre-screen's own trajectory is the analysis step map's
  residual form, u + T (Phi_T(u) - u) / T, not bitwise.

Usage: python -m validation.tissue.cell_replacement_r1 --output DIR
       [--criteria] (--case s:rate:order ... | --screen s:slot ...)
"""

import argparse
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np

jax.config.update("jax_enable_x64", True)

from cells.core.specs import parse_spec  # noqa: E402
from cells.models import cell_replacement as model  # noqa: E402
from validation.stationary import heredity_conversion as hc  # noqa: E402
from validation.stationary import heredity_prescreen as hp  # noqa: E402
from validation.stationary import heredity_turnover as ht  # noqa: E402
from validation.stationary import worlds  # noqa: E402
from validation.tissue import cell_replacement_fixtures as fx  # noqa: E402
from validation.tissue import surface_pump_v3_fixtures as v3fx  # noqa: E402

PRESCREEN = ht.PRESCREEN_8.parent / "prescreen-09-turnover" / "stage2-turnover"
DT, RECORD_S, HORIZON = ht.DT, ht.RECORD_S, ht.HORIZON_S
VOLTAGE_TOL_MV = 1e-3
RULE_A = dict(
    law="delayed_first_order_junction_formation@1",
    initial_abundance=1.0,
    lag_s=0.0,
    time_constant_s=40.0,
    gate_at_arrival="law_open",
)
CRITERIA = dict(
    kind="cells.cell_replacement_r1_criteria@1",
    scope="R1 regression of resolved_pump_replacement@1 against pre-screen 9 (development)",
    reference=str(PRESCREEN),
    rule="pre-screen 9 rule (a) 'open' as A0 1, lag 0, law_open",
    pass_if=[
        "identical d_slots at every record time",
        "identical stop time (first record without a D cell) or both reach the horizon",
        f"written disc voltage range within {VOLTAGE_TOL_MV} mV at every record",
    ],
    report_otherwise="first divergence: time, slots that differ, largest range difference",
    cases=["0.6:20:oldest", "0.6:6:random", "0.3:6:oldest"],
)
SCREENS = [f"{s}:{slot}" for s in ("0.3", "0.6") for slot in ht.SLOT_NAMES]
CRITERIA_C = dict(
    kind="cells.cell_replacement_r1c_criteria@1",
    scope="R1 rule (c): pre-screen 9 stage-1 single-newcomer screens, steady rule",
    reference=str(PRESCREEN.parent / "stage1-screen" / "runs_main.jsonl"),
    rule="pre-screen 9 rule (c) 'steady' as A0 1, lag 0, law_steady",
    method="newcomer placed by the engine's event map; forward through heredity_conversion.run "
    "(the driver's records, early stop and verdict) with the wrapper's checked step",
    pass_if=[
        "same record times, and identical slots_d, disc_other_d and outside_other_d per record",
        f"slot voltage within {VOLTAGE_TOL_MV} mV per record",
        "same number of records, outcome and latency bracket",
    ],
    report_otherwise="first divergence (record), placement difference from the driver's place()",
    cases=SCREENS,
)


def reference(scale, rate, order):
    path = PRESCREEN / f"runs_control_s{scale:g}.jsonl"
    for line in path.read_text().splitlines():
        r = json.loads(line)
        if (
            r.get("kind") == "turnover"
            and r["rule"] == "open"
            and r["rate_percent_per_min"] == rate
            and r["order"] == order
            and r["scale"] == scale
        ):
            return r
    raise KeyError((scale, rate, order))


def world(case, plan):
    """The wrapper's definition: the analysis' base sheet (all H) plus the driver's events."""
    states = {k: v[:4] for k, v in v3fx.HEREDITY_STATES.items()}
    raw = worlds.ionic_background(
        worlds.e07_sheet_definition(
            [states["H"]] * len(case.cells), case.edges, gated=True, dt=DT, end_time=HORIZON
        )
    )
    raw["experiment"]["observation_times"] = [0.0, HORIZON]
    template = fx.template_from_cell(raw, "cell_0", "h")
    events = [
        (int(k) * DT, f"cell_{int(slot)}", "h", f"n{i}")
        for i, (k, slot) in enumerate(zip(plan["steps"], plan["slots"], strict=True))
    ]
    return parse_spec(fx.with_replacement(raw, [template], events, formation=RULE_A))


def run_case(scale, rate, order):
    unit = hp.units()["theta_per_unit_scale"]
    case = ht.Sheet(*ht.DISCS[37])
    n, written = len(case.cells), case.full
    plan = ht.schedule(n, rate, order, HORIZON)
    started = time.perf_counter()
    u_disc = hc.disc_state(case, scale, unit)
    state_inner, p_inner, control_inner = case.pb.embed(u_disc, scale)
    prepared = time.perf_counter() - started
    spec = world(case, plan)
    state, p = model.initial_values(spec)
    p = p._replace(**{k: np.asarray(getattr(p_inner, k)) for k in type(p_inner)._fields})
    state = model.STATE_TYPE(
        *(np.asarray(v) for v in state_inner),
        *(getattr(state, k) for k in model.REPLACEMENT_STATE_AXES),
    )

    # Inner controls: the analysis' (held over the run); counts from the event table.
    def control_at(t):
        c = model.Control(*(np.asarray(v[0]) for v in model.control_values(spec, [t])))
        return c._replace(
            **{k: np.asarray(getattr(control_inner, k)) for k in control_inner._fields}
        )

    @jax.jit
    def advance(s, c, q, k):
        def body(_, carry):
            x, ok = carry
            x, valid = model.checked_step(x, DT, c, q, q.active)
            return x, ok & valid

        return jax.lax.fori_loop(0, k, body, (s, jnp.asarray(True)))

    @jax.jit
    def voltages(s, c, q):
        return model.field_values(s, c, q).rates.membrane_voltage_V

    every = int(round(RECORD_S / DT))
    total = plan["total_steps"]
    events = {int(k) for k in plan["steps"]}
    marks = sorted(set(range(0, total + 1, every)) | events)
    s = jax.tree.map(jnp.asarray, state)
    q = jax.tree.map(jnp.asarray, p)
    records, stop, k_now, refused = [], None, 0, None
    for k in marks:
        c = control_at(k_now * DT)
        if k > k_now:
            s, ok = advance(s, jax.tree.map(jnp.asarray, c), q, k - k_now)
            if not bool(ok):
                refused = dict(time_s=k * DT, reason="a step was refused")
                break
            k_now = k
        if k % every == 0:
            v = np.asarray(voltages(s, jax.tree.map(jnp.asarray, control_at(k * DT)), q))[:n]
            d = v > case.threshold
            records.append(
                dict(
                    time_s=k * DT,
                    d_slots="".join("1" if x else "0" for x in d),
                    written_voltage_range_mV=[
                        1e3 * float(v[written].min()),
                        1e3 * float(v[written].max()),
                    ],
                )
            )
            if k > 0 and not d.any():
                stop = k * DT
                break
    return dict(
        scale=scale,
        rate_percent_per_min=rate,
        order=order,
        records=records,
        stop_time_s=stop,
        refused=refused,
        events_planned=plan["count"],
        preparation_s=prepared,
        wall_s=time.perf_counter() - started,
        generation_end=np.asarray(s.generation).tolist(),
    )


def compare(mine, theirs):
    ref = {r["time_s"]: r for r in theirs["records"]}
    first, worst = None, 0.0
    for r in mine["records"]:
        other = ref.get(r["time_s"])
        if other is None:
            first = first or dict(time_s=r["time_s"], reason="no pre-screen record")
            continue
        diff = max(
            abs(a - b)
            for a, b in zip(
                r["written_voltage_range_mV"], other["written_voltage_range_mV"], strict=True
            )
        )
        worst = max(worst, diff)
        if first is None and (r["d_slots"] != other["d_slots"] or diff > VOLTAGE_TOL_MV):
            slots = [
                i
                for i, (a, b) in enumerate(zip(r["d_slots"], other["d_slots"], strict=True))
                if a != b
            ]
            first = dict(time_s=r["time_s"], differing_slots=slots, range_difference_mV=diff)
    their_stop = (theirs.get("stopped") or {}).get("time_s")
    same_stop = mine["stop_time_s"] == their_stop
    return dict(
        verdict="pass" if first is None and same_stop and mine["refused"] is None else "diverged",
        records_compared=len(mine["records"]),
        stop_time_s=dict(engine=mine["stop_time_s"], prescreen=their_stop),
        max_range_difference_mV=worst,
        first_divergence=first,
    )


RULE_C = dict(RULE_A, gate_at_arrival="law_steady")


def screen_case(scale, slot_name):
    """Rule (c): one newcomer placed by the engine's event map at the stationary disc,
    then forward through heredity_conversion.run (the driver's own records, early stop
    and verdict) with the wrapper's checked step as the advance."""
    unit = hp.units()["theta_per_unit_scale"]
    case = ht.Sheet(*ht.SCREEN_DISC)
    slot = hc.slots(case, case.radius)[slot_name]
    inside = slot_name != "outside"
    started = time.perf_counter()
    u_disc = hc.disc_state(case, scale, unit)
    state_inner, p_inner, control_inner = case.pb.embed(u_disc, scale)
    states = {k: v[:4] for k, v in v3fx.HEREDITY_STATES.items()}
    raw = worlds.ionic_background(
        worlds.e07_sheet_definition(
            [states["H"]] * len(case.cells), case.edges, gated=True, dt=DT, end_time=1.0
        )
    )
    raw["experiment"]["observation_times"] = [0.0, 1.0]
    template = fx.template_from_cell(raw, "cell_0", "h")
    spec = parse_spec(
        fx.with_replacement(raw, [template], [(DT, f"cell_{slot}", "h", "n0")], formation=RULE_C)
    )
    state, p = model.initial_values(spec)
    p = p._replace(**{k: np.asarray(getattr(p_inner, k)) for k in type(p_inner)._fields})
    extra = {k: np.asarray(getattr(state, k)) for k in model.REPLACEMENT_STATE_AXES}
    state = model.STATE_TYPE(*(np.asarray(v) for v in state_inner), *extra.values())
    control = model.Control(*(np.asarray(v[0]) for v in model.control_values(spec, [DT])))
    control = control._replace(
        **{k: np.asarray(getattr(control_inner, k)) for k in control_inner._fields}
    )
    after, ok = jax.jit(lambda x, c, q: model.apply_events(x, c, q))(
        jax.tree.map(jnp.asarray, state), jax.tree.map(jnp.asarray, control), p
    )
    assert bool(ok)
    after = model.STATE_TYPE(*(np.asarray(v) for v in after))
    u0 = np.asarray(case.pb.coordinates(model.ionic_state(after), model.ionic_layout(p, xp=np)))
    driver_u0, _ = ht.place(case, u_disc, [slot], "steady", scale)
    kept = {k: after[i] for i, k in enumerate(model.STATE_TYPE._fields) if k in extra}
    pj, cj = jax.tree.map(jnp.asarray, p), jax.tree.map(jnp.asarray, control)

    @jax.jit
    def residual(u, k):
        inner, _, _ = case.pb.embed(u, scale)
        x = model.STATE_TYPE(*inner, *(jnp.asarray(kept[k_]) for k_ in extra))

        def body(_, carry):
            y, good = carry
            y, valid = model.checked_step(y, DT, cj, pj, pj.active)
            return y, good & valid

        final, good = jax.lax.fori_loop(0, k, body, (x, jnp.asarray(True)))
        rate = (case.pb._extract(model.ionic_state(final)) - u) / (k * DT)
        return jnp.where(good, rate, jnp.nan)

    rows, _ = hc.run(case, lambda u, s_, k: residual(jnp.asarray(u), k), u0, scale, [slot], inside)
    others = int(case.full.sum()) - (1 if inside else 0)
    return dict(
        scale=scale,
        slot=slot_name,
        cell=slot,
        placement_max_abs_difference=float(np.max(np.abs(u0 - driver_u0))),
        **hc.verdict(rows, [slot], others, inside),
        trajectory=rows,
        wall_s=time.perf_counter() - started,
    )


def screen_reference(scale, slot_name):
    path = PRESCREEN.parent / "stage1-screen" / "runs_main.jsonl"
    for line in path.read_text().splitlines():
        r = json.loads(line)
        if r.get("rule") == "steady" and r["scale"] == scale and r["slot"] == slot_name:
            return r
    raise KeyError((scale, slot_name))


def screen_compare(mine, theirs):
    first, worst = None, 0.0
    counts = ("slots_d", "disc_other_d", "outside_other_d")
    pairs = list(zip(mine["trajectory"], theirs["trajectory"], strict=False))
    for a, b in pairs:
        if "slots_d" not in a or "slots_d" not in b:
            same = a.get("refused") == b.get("refused")
            first = first or (None if same else dict(time_s=a.get("time_s"), reason="refusal"))
            continue
        diff = max(
            abs(x - y) for x, y in zip(a["slot_voltage_mV"], b["slot_voltage_mV"], strict=True)
        )
        worst = max(worst, diff)
        if first is None and (
            a["time_s"] != b["time_s"] or any(a[k] != b[k] for k in counts) or diff > VOLTAGE_TOL_MV
        ):
            first = dict(time_s=a["time_s"], engine=a, prescreen=b)
    same = (
        len(mine["trajectory"]) == len(theirs["trajectory"])
        and mine["outcome"] == theirs["outcome"]
        and mine["latency_bracket_s"] == theirs["latency_bracket_s"]
    )
    return dict(
        verdict="pass" if first is None and same else "diverged",
        rows=dict(engine=len(mine["trajectory"]), prescreen=len(theirs["trajectory"])),
        outcome=dict(engine=mine["outcome"], prescreen=theirs["outcome"]),
        latency_bracket_s=dict(
            engine=mine["latency_bracket_s"], prescreen=theirs["latency_bracket_s"]
        ),
        max_slot_voltage_difference_mV=worst,
        placement_max_abs_difference=mine["placement_max_abs_difference"],
        first_divergence=first,
    )


def provenance():
    git = ["git", "-C", str(Path(__file__).resolve().parents[2])]
    return dict(
        argv=sys.argv,
        host=platform.node(),
        jax=jax.__version__,
        revision=subprocess.run(
            [*git, "rev-parse", "HEAD"], capture_output=True, text=True
        ).stdout.strip(),
        dirty=subprocess.run(
            [*git, "status", "--porcelain", "--untracked-files=no"], capture_output=True, text=True
        ).stdout,
    )


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--criteria", action="store_true")
    parser.add_argument("--case", action="append", default=[])
    parser.add_argument("--screen", action="append", default=[])
    args = parser.parse_args(argv)
    args.output.mkdir(parents=True, exist_ok=True)
    if args.criteria:
        name = "criteria_c.json" if args.screen else "criteria.json"
        with open(args.output / name, "x") as f:
            json.dump((CRITERIA_C if args.screen else CRITERIA) | provenance(), f, indent=1)
        return
    needed = (["criteria.json"] if args.case else []) + (["criteria_c.json"] if args.screen else [])
    if any(not (args.output / n).exists() for n in needed):
        raise SystemExit("Write the criteria (--criteria) before any run")
    for item in args.case:
        s, rate, order = item.split(":")
        scale, rate = float(s), float(rate)
        mine = run_case(scale, rate, order)
        result = dict(
            case=item, comparison=compare(mine, reference(scale, rate, order)), engine=mine
        )
        result |= provenance()
        with open(args.output / f"r1_{item.replace(':', '_')}.json", "x") as f:
            json.dump(result, f, indent=1)
        print(item, json.dumps(result["comparison"]), flush=True)
    for item in args.screen:
        s, slot = item.split(":")
        mine = screen_case(float(s), slot)
        comparison = screen_compare(mine, screen_reference(float(s), slot))
        result = dict(case=item, rule="c (law_steady)", comparison=comparison, engine=mine)
        result |= provenance()
        with open(args.output / f"r1c_{item.replace(':', '_')}.json", "x") as f:
            json.dump(result, f, indent=1, default=float)
        print(item, json.dumps(comparison, default=float)[:600], flush=True)


if __name__ == "__main__":
    main()
