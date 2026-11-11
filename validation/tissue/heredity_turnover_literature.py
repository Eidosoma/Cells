"""Turnover of a cue-written disc under the literature newcomer rule (development pre-screen).

Not judged. Question (E07-v1 renewal stage, docs/HEREDITY_FIRST_EXPERIMENT.md; D139):
is a cue-written D disc on the held-bath 127-cell sheet renewed when its carriers
are replaced oldest first by newcomers that arrive uncoupled and form gap junctions
by delayed_first_order_junction_formation@1? Newcomers are either the isolated H
template (D133) or a donor copy (an inheritance route: a junction neighbour divides
into the slot, D139). The inherit rule is excluded (D139) and is not offered.

Engine models run: resolved_pump_replacement@1 (scheduled_cell_replacement@1 and
delayed_first_order_junction_formation@1) over resolved_pump_tissue@3, IMEX
ARS(2,2,2) with exponential stage gates, junction_heat_booking
trapezoid_nonnegative@1 (only the heat ledger differs from the default; the state
is the same). The wrapper's checked_step and its device row checks run on every
accepted row in jitted loops, as validation/tissue/cell_replacement_r1.py and
heredity_pilot.part_sheetreplay step the models; a refused step or a failed row
check ends the arm with the state before that row. Nothing here adds physics.

World and start. The sheet of heredity_pilot.long_sheet_definition (127 cells with
their own held baths, E07 voltage-gated junctions at coupling scale s, homogeneous
heredity cells) without its cue populations, whose availability is 0 after the cue.
Each arm starts from the sheet70 run of the same disc and s at 120 s
(heredity-pilot-w1-20261110-01/sheet70/longsheet-v2-*/snapshots/t00120.000; cue
on [0.5, 2.5) s), declared as the definition's initial state: amounts, channel and
junction gates; every ledger starts at zero. Time 0 here is 120 s there. Only
discs that held for 70 min without turnover there are used (37 cells at s 1.0,
0.6 and 0.3; 19 cells at s 0.6 and 0.3), so a loss within that window is due to
replacement.

Turnover. Only the disc's cells are replaced. Founders all have the same age, so
they are taken in a fixed seeded permutation; afterwards the oldest carrier is
always the next, so slot i of the permutation is replaced every R seconds, where
R = k (lag + tau) is the residence (arrival to own replacement) and events fall
at (j + 1/2) R / N on the dt grid. Isolated newcomers take the sheet's declared H
state (the single heredity cell's isolated H steady state, as R1 and pre-screen 9
did). Donor copies take a uniformly drawn junction neighbour of the slot as the
dividing donor (seeded; disc or outside cell). Formation brackets (design note
section 1.2; docs/CELL_REPLACEMENT.md): fast (lag 2 min, tau 15 min, the ranges'
lower ends and the division-born fast arm of Boassa 2010), central (10, 30 min,
the documented default) and slow (20, 60 min, the upper ends); all with A0 = 0
and law_open.

Readouts (analyse): D (Vm above the U voltage, as heredity_pilot) inside and
outside the disc; Jaccard of the D set against the disc; loss times; per-carrier
conversion; per-cell composition and osmotic excess against the H start (the
start of every founder and of every isolated newcomer; fixed volume; flag 10%,
censor 15%), and for donor copies also against their own arrival; refusals.

Stop rules (fixed before any run): an arm ends at its planned end (two full
turnovers plus 5 min), or one minute after the first of two consecutive records
with no D cell anywhere (absorbing: newcomers are H templates or copies of
cells, and there is no cue), or at the first record whose osmotic excess exceeds
the censor in any cell (later rows are outside fixed-volume validity).

Usage: python -m validation.tissue.heredity_turnover_literature PART --output DIR
  predictions                      write predictions.json (refuses to overwrite)
  criteria                         write the numerics criteria (refuses to overwrite)
  importcheck                      no-event 60 s from each start against sheet70
  numerics --case N1|N2 --dt DT    numerics segment
  compare                          numerics verdict from the saved segments
  arm --arm ID [--dt DT] [--resume]
  analyse --arm ID | --all         outcomes against the predictions
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
from validation.stationary import worlds  # noqa: E402
from validation.tissue import cell_replacement_fixtures as fx  # noqa: E402
from validation.tissue import heredity_pilot as pilot  # noqa: E402
from validation.tissue import surface_pump_v3_fixtures as v3fx  # noqa: E402

SHEET70 = Path("/mnt/workspaces/Cells/heredity-pilot-w1-20261110-01/sheet70")
START_LABEL = "t00120.000"
START_S = 120.0  # sheet70 time of the start state
CUE_OFF_S = pilot.LONG_CUE_S[1]
RADIUS = pilot.SHEET_RADIUS
THRESHOLD_V = pilot.THRESHOLD_V
FLAG, CENSOR = pilot.OSMOTIC_FLAG, pilot.OSMOTIC_CENSOR
SPECIES = pilot.ION_IDS
BOOKING = "trapezoid_nonnegative@1"
HELD_DISCS = ((37, 1.0), (37, 0.6), (37, 0.3), (19, 0.6), (19, 0.3))
ORDER_SEED, DONOR_SEED = 20261111, 20261112
RECORD_S = 10.0
END_MARGIN_S = 300.0
ALL_H_TAIL_S = 60.0
SAVE_EVERY_WALL_S = 900.0
BRACKETS = dict(
    fast=dict(lag_s=120.0, time_constant_s=900.0),
    central=dict(lag_s=600.0, time_constant_s=1800.0),
    slow=dict(lag_s=1200.0, time_constant_s=3600.0),
)
STOP_RULES = [
    "planned end: two full turnovers plus 5 min (2 R + 300 s)",
    "all H: one minute after the first of two consecutive 10 s records with no D cell "
    "anywhere in the sheet (absorbing)",
    "censor: the first record with osmotic excess above 15% (against the H start) in any cell",
    "refusal: a step the model refuses or a row whose device check fails ends the arm",
]


def log(line):
    print(f"[{time.strftime('%H:%M:%S')}] {line}", flush=True)


def write_json(path, value, *, exclusive=False):
    path = Path(path)
    if exclusive:
        with open(path, "x") as f:
            json.dump(value, f, indent=1, default=pilot._default)
            f.write("\n")
        return
    pilot.write_json(path, value)


def provenance():
    git = ["git", "-C", str(Path(__file__).resolve().parents[2])]

    def run(*a):
        return subprocess.run([*git, *a], capture_output=True, text=True).stdout.strip()

    return dict(
        argv=sys.argv,
        host=platform.node(),
        jax=jax.__version__,
        revision=run("rev-parse", "HEAD") or None,
        dirty=run("status", "--porcelain", "--untracked-files=no") or "",
        source=str(Path(__file__).resolve()),
    )


# ------------------------------------------------------------------ geometry


def sheet():
    cells, edges = worlds.hexagon(RADIUS)
    neighbours = {i: [] for i in range(len(cells))}
    for a, b in edges:
        neighbours[a].append(b)
        neighbours[b].append(a)
    return cells, edges, neighbours


def disc_cells(size):
    cells, _, _ = sheet()
    return [i for i, c in enumerate(cells) if worlds.ring(c) <= pilot.DISCS[size]]


def slot_class(cell, size):
    """centre, interior (all neighbours in the disc), rim corner or rim side."""
    cells, _, _ = sheet()
    q, r = cells[cell]
    k = worlds.ring(cells[cell])
    if k == 0:
        return "centre"
    if k < pilot.DISCS[size]:
        return "interior"
    return "rim_corner" if sum(abs(v) == k for v in (q, r, q + r)) == 2 else "rim_side"


# ------------------------------------------------------------------ definitions


def start_state(size, s):
    """The sheet70 state at 120 s of the disc and s (arrays) and its definition."""
    folder = SHEET70 / f"longsheet-v2-disc{size}-s{s}" / "snapshots" / START_LABEL / "world-1"
    state = dict(np.load(folder / "state.npz"))
    spec = json.loads((folder / "manifest.json").read_text())["spec"]
    return state, spec, folder


def definition(size, s, dt, end_s, events, formation):
    """resolved_pump_replacement@1 on the sheet from the sheet70 start (raw definition)."""
    start, saved, _ = start_state(size, s)
    cells, edges, _ = sheet()
    h = v3fx.HEREDITY_STATES["H"][:4]
    raw = worlds.ionic_background(
        worlds.e07_sheet_definition([h] * len(cells), edges, scale=s, gated=True, dt=dt,
                                    end_time=end_s)
    )  # fmt: skip
    template = fx.template_from_cell(raw, "cell_0", "h_isolated")
    m = raw["model"]
    names = [row["id"] for row in m["species"]]
    if tuple(names) != SPECIES:
        raise ValueError("species order")
    ids = [c["id"] for c in m["channels"]]
    if ids != [c["id"] for c in saved["model"]["channels"]][: len(ids)]:
        raise ValueError("channel order differs from the sheet70 definition")
    pairs = [(j["sender"], j["receiver"]) for j in m["junctions"]]
    if pairs != [(j["sender"], j["receiver"]) for j in saved["model"]["junctions"]]:
        raise ValueError("junction order differs from the sheet70 definition")
    amounts = start["amount_reference"] + start["amount_increment"]
    for i, cell in enumerate(m["cells"]):
        cell["initial_amount_fmol"] = {k: float(amounts[j, i]) for j, k in enumerate(names)}
    gates = start["channel_gate"]
    for k, c in enumerate(m["channels"]):
        c["initial_gate"] = [float(g) for g in gates[: len(c["initial_gate"]), k]]
    for k, j in enumerate(m["junctions"]):
        j["gate"]["initial_gate"] = float(start["junction_gate"][k])
    worlds.ionic_background(raw)
    m["junction_heat_booking"] = BOOKING
    raw["experiment"]["observation_times"] = [0.0, end_s]
    raw["execution"]["backend"] = "cpu"
    rows = [
        (k * dt, f"cell_{slot}", "h_isolated" if donor is None else None, carrier,
         None if donor is None else f"cell_{donor}")
        for k, slot, donor, carrier in events
    ]  # fmt: skip
    return fx.with_replacement(
        raw, [template], rows, formation=dict(fx.FORMATION, **formation)
    ), template


def layout_check(spec, size, s):
    """The rebuilt world's layout equals sheet70's (cue populations excluded)."""
    start, _, _ = start_state(size, s)
    state0, p = model.initial_values(spec)
    nc = np.asarray(p.channel_permeability).size
    out = {}
    for k in ("volume", "membrane_capacitance", "membrane_permeability", "membrane_area",
              "junction_permeability", "junction_area", "pump_capacity", "boundary_V",
              "junction_threshold_voltage", "junction_minimum"):  # fmt: skip
        out[k] = float(np.max(np.abs(np.asarray(getattr(p, k)) - start[k]), initial=0.0))
    out["channel_permeability"] = float(
        np.max(np.abs(np.asarray(p.channel_permeability) - start["channel_permeability"][:nc]))
    )
    amounts = np.asarray(p.amount_reference) + np.asarray(state0.amount_increment)
    out["amounts"] = float(
        np.max(np.abs(amounts - (start["amount_reference"] + start["amount_increment"])))
    )
    return out


# ------------------------------------------------------------------ arms


def arm_id(kind, bracket, k, size, s):
    return f"{kind}-{bracket}-k{k}-d{size}-s{s}"


def parse_arm(name):
    kind, bracket, k, size, s = name.split("-")
    return dict(kind=kind, bracket=bracket, k=int(k[1:]), size=int(size[1:]), s=float(s[1:]))


def plan(kind, bracket, k, size, s, dt, *, end_s=None, kinds=None, grid_dt=None):
    """Events (step, slot, donor or None, carrier) and the turnover times of one arm.

    kinds alternates newcomer kinds by event (numerics only); grid_dt rounds event
    times on a coarser grid first, so runs at different dt share event times.
    """
    grid_dt = dt if grid_dt is None else grid_dt
    f = BRACKETS[bracket]
    formation_s = f["lag_s"] + f["time_constant_s"]
    residence = k * formation_s
    slots = disc_cells(size)
    n = len(slots)
    permutation = [int(v) for v in np.random.default_rng(ORDER_SEED).permutation(slots)]
    _, _, neighbours = sheet()
    donors = np.random.default_rng(DONOR_SEED)
    end = 2 * residence + END_MARGIN_S if end_s is None else end_s
    interval = residence / n
    events, j = [], 0
    while True:
        step = int(round((j + 0.5) * interval / grid_dt)) * int(round(grid_dt / dt))
        if step * dt >= end - dt:
            break
        slot = permutation[j % n]
        use = kind if kinds is None else kinds[j % len(kinds)]
        donor = None
        if use == "donor":
            donor = int(donors.choice(sorted(neighbours[slot])))
        events.append((step, slot, donor, f"n{j}"))
        j += 1
    return dict(
        kind=kind,
        bracket=bracket,
        formation=dict(f),
        formation_time_s=formation_s,
        k=k,
        residence_s=residence,
        size=size,
        s=s,
        dt=dt,
        end_s=end,
        interval_s=interval,
        permutation=permutation,
        events=events,
        turnover_complete_s=[
            (n - 0.5) * interval,  # last founder replaced
            (2 * n - 0.5) * interval,  # last first-generation newcomer replaced
        ],
        start=dict(sheet70_label=START_LABEL, sheet70_time_s=START_S,
                   seconds_after_cue_off_at_t0=START_S - CUE_OFF_S),
        seeds=dict(order=ORDER_SEED, donor=DONOR_SEED),
    )  # fmt: skip


def arm_set():
    """The arm set (queue order within each CPU), fixed before the long runs."""
    first = [arm_id("iso", "central", 1, d, s) for d, s in HELD_DISCS]
    donor = [arm_id("donor", "fast", 1, d, s) for d, s in HELD_DISCS]
    a, b = (37, 1.0), (37, 0.6)
    cpu2 = first + [
        arm_id("iso", "fast", 1, *a),
        arm_id("iso", "fast", 1, *b),
        arm_id("iso", "central", 3, *a),
        arm_id("iso", "fast", 3, *a),
        arm_id("iso", "fast", 10, *a),
        arm_id("iso", "slow", 1, *a),
        arm_id("donor", "fast", 10, *a),
    ]
    cpu3 = donor + [
        arm_id("iso", "central", 3, *b),
        arm_id("iso", "fast", 3, *b),
        arm_id("donor", "central", 1, *a),
        arm_id("donor", "fast", 3, *a),
    ]
    return dict(cpu2=cpu2, cpu3=cpu3)


# ------------------------------------------------------------------ predictions

# Written before any turnover run, from: sheet70 (cue-written discs held 70 min at
# these s; loading +2%/10 min, 10% at 56-58 min, extrapolated 15% at about 97 min
# after the cue for a cell that stays D); pre-screen 9 (loaded neighbours, A = 1:
# centre newcomers convert under the steady rule at s 0.3 and 0.6, rim newcomers
# stay H, the centre H defect is absent and rim defects are stable; converted
# newcomers are weaker D neighbours than loaded founders); pre-screen 8 (one rim
# newcomer can unzip a disc under the open rule); the G2 donor check (a D donor
# copy stays D uncoupled); the design note's prediction (B1 fails at every rate).
GENERAL = dict(
    isolated=[
        "A newcomer is H and uncoupled for the whole lag, so a slot in its lag is never D. "
        "At k = 1 the slots in their lag are lag/R of the disc in the second turnover "
        "(central and slow 25%, fast 12%), so J <= 0.75 there for central and slow by "
        "construction, before any physics.",
        "Rim newcomers (2-3 H outside neighbours) never convert, at any s, k or bracket: "
        "their junctions to H cells stay open, to D cells close to about 0.1 (|Vj| ~ 55 mV).",
        "Erosion: once a rim newcomer is H, the inner cells next to it become rim-like, and "
        "their own newcomers stay H; the D set shrinks inward through the turnovers.",
        "Interior newcomers with 5-6 D neighbours: no conversion at s 0.3; at s 0.6 a few "
        "late conversions (A above about 0.5) at k >= 3 only; at s 1.0 conversion at A "
        "about 0.2-0.6 when the slot keeps 5-6 D neighbours.",
        "s 1.0 (37 cells): the shrinking disc is lost collectively (all remaining D to H "
        "within seconds, as the 19-cell disc at s 1.0 was in sheet70) within the first "
        "turnover, most likely between 0.25 R and 0.75 R.",
        "s 0.3 and 0.6: founders stay D until replaced (no founder loss except next to "
        "several coupled H newcomers at s 0.6); the D count falls about linearly over the "
        "first turnover and the sheet is all H at about R (s 0.3) to 1.3 R (s 0.6).",
        "B1 (J >= 0.8 through two full turnovers) fails in every isolated arm.",
    ],
    donor=[
        "A donor copy takes the donor's state: from a D donor it arrives D and stays D while "
        "uncoupled; from an H donor (an outside cell, or an H disc cell) it arrives H.",
        "Rim slots draw an outside (H) donor with probability 1/3 (side) to 1/2 (corner); "
        "these H newcomers stay H, so the disc erodes from the rim, a voter-like process "
        "with a fixed H boundary: about 7 H newcomers per turnover in the 37-cell disc and "
        "5 in the 19-cell disc before secondary spread.",
        "Electrical conversion adds little at s 0.3; at s 0.6-1.0 H copies with 5-6 D "
        "neighbours may convert once coupled, and D copies with 3 or more coupled H "
        "neighbours may fall to H.",
        "J after one turnover: 0.70-0.90 (37 cells), 0.60-0.85 (19 cells); after two: "
        "0.50-0.80 (37), 0.40-0.70 (19). B1 fails narrowly in the 37-cell discs and clearly "
        "in the 19-cell discs; the disc is not lost entirely within two turnovers except "
        "possibly at s 1.0 (collective loss).",
        "Composition is inherited, so the disc keeps loading as without turnover: flag at "
        "about 57 min and censor at about 97 min after the cue if D persists.",
    ],
    common=[
        "No D outside the disc in any arm.",
        "No refusal and no failed device check (trapezoid junction-heat booking).",
        "Isolated arms: founders load until replaced (max excess about 2%/10 min of D "
        "residence after the cue); newcomers start at the H composition, so the flag is "
        "reached only where a D founder outlives about 57 min after the cue and the "
        "censor about 97 min.",
    ],
)


def arm_prediction(name):
    a = parse_arm(name)
    f = BRACKETS[a["bracket"]]
    tf = f["lag_s"] + f["time_constant_s"]
    r = a["k"] * tf
    t0_after_cue = START_S - CUE_OFF_S
    out = dict(arm=name, **a, residence_s=r, formation_time_s=tf, b1="fail")
    if a["kind"] == "iso":
        lag_share = f["lag_s"] / r
        out["j_bound_second_turnover_from_lag"] = 1.0 - lag_share
        if a["s"] == 1.0:
            out.update(
                collective_loss="yes, in the first turnover (0.25-0.75 R)",
                all_h_by_s=[0.25 * r, 1.0 * r],
                newcomers_converting="some interior newcomers (5-6 D neighbours), A 0.2-0.6; "
                "no rim newcomer",
                j_after_first_turnover=[0.0, 0.3],
                j_after_second_turnover=[0.0, 0.1],
            )
        elif a["s"] == 0.6:
            out.update(
                collective_loss="no",
                all_h_by_s=[0.9 * r, 1.5 * r],
                newcomers_converting="none at k = 1; at most a few interior newcomers at "
                "k >= 3 (A above 0.5); no rim newcomer",
                j_after_first_turnover=[0.0, 0.25],
                j_after_second_turnover=[0.0, 0.1],
            )
        else:
            out.update(
                collective_loss="no",
                all_h_by_s=[0.9 * r, 1.1 * r],
                newcomers_converting="none",
                j_after_first_turnover=[0.0, 0.1],
                j_after_second_turnover=[0.0, 0.0],
            )
        # D founders outlive their replacement window unless lost collectively (s 1.0).
        latest = t0_after_cue + (0.75 * r if a["s"] == 1.0 else r)
        when = "if the collective loss comes after" if a["s"] == 1.0 else "at about"
        out["osmotic"] = (
            f"censored {when} 97 min after the cue (unreplaced D founders)"
            if latest > 97 * 60
            else f"flagged {when} 57 min after the cue (unreplaced D founders), not censored"
            if latest > 57 * 60
            else "neither flagged nor censored"
        )
        out["d_outside"] = 0
    else:
        size = a["size"]
        out.update(
            collective_loss="possible at s 1.0 only",
            all_h_by_s=None,
            newcomers_converting="D copies stay D unless they have 3 or more coupled H "
            "neighbours at s >= 0.6; H copies with 5-6 D neighbours may convert at "
            "s >= 0.6",
            j_after_first_turnover=[0.70, 0.90] if size == 37 else [0.60, 0.85],
            j_after_second_turnover=[0.50, 0.80] if size == 37 else [0.40, 0.70],
            d_outside=0,
        )
        end_after_cue = t0_after_cue + 2 * r + END_MARGIN_S
        out["osmotic"] = (
            "censored at about 97 min after the cue (inherited loading)"
            if end_after_cue > 97 * 60
            else "flagged at about 57 min after the cue, not censored"
            if end_after_cue > 57 * 60
            else "neither flagged nor censored"
        )
    out["refusals"] = 0
    return out


def predictions():
    sets = arm_set()
    return dict(
        kind="cells.heredity_turnover_literature_predictions@1",
        status="written before any turnover run; development pre-screen, not judged",
        engine_models=["resolved_pump_replacement@1", "resolved_pump_tissue@3"],
        stop_rules=STOP_RULES,
        brackets=BRACKETS,
        general=GENERAL,
        arms={name: arm_prediction(name) for q in sets.values() for name in q},
        queues=sets,
    )


# ------------------------------------------------------------------ stepping


class Stepper:
    """Jitted segments of the wrapper's checked step with device row checks on every row."""

    def __init__(self, spec):
        self.spec = spec
        self.dt = spec.execution.dt
        state, p = model.initial_values(spec)
        model.check_steps(spec, np.array([self.dt]), model.control_values(spec, [0.0]))
        self.p = jax.tree.map(jnp.asarray, p)
        self.host_p = p
        self.n = int(np.asarray(p.active).sum())
        constants = jax.tree.map(jnp.asarray, model.device_check_constants(spec))
        nchecks, ndiag = len(model.DEVICE_CHECKS), len(model.DEVICE_DIAGNOSTICS)
        dt = self.dt

        def advance(s, c, q, k0, count):
            def body(i, carry):
                y, stopped, bad, failed_at, worst = carry
                new, ok = model.checked_step(y, dt, c, q, q.active)
                failed, values = model.device_checks(y, new, q, constants, k0 + i + 1)
                reject = ~ok | jnp.any(failed)
                first = ~stopped & reject
                bad = jnp.where(first, k0 + i + 1, bad)
                failed_at = jnp.where(first, jnp.concatenate([~ok[None], failed]), failed_at)
                keep = stopped | reject
                y = jax.tree.map(lambda a, b: jnp.where(keep, a, b), y, new)
                worst = jnp.where(keep, worst, jnp.maximum(worst, values))
                return y, stopped | reject, bad, failed_at, worst

            init = (
                s,
                jnp.asarray(False),
                jnp.asarray(-1, dtype=jnp.int64),
                jnp.zeros(nchecks + 1, dtype=bool),
                jnp.zeros(ndiag),
            )
            return jax.lax.fori_loop(0, count, body, init)

        def measure(s, c, q):
            field = model.field_values(s, c, q)
            return (
                field.rates.membrane_voltage_V,
                field.converged,
                q.amount_reference + s.amount_increment,
                1.0 - s.junction_abundance_deficit,
                s.junction_gate,
                s.generation,
            )

        self._advance = jax.jit(advance)
        self._measure = jax.jit(measure)
        self.state = jax.tree.map(jnp.asarray, state)

    def control(self, k):
        c = model.control_values(self.spec, [k * self.dt])
        return jax.tree.map(jnp.asarray, model.Control(*(np.asarray(v[0]) for v in c)))

    def advance(self, k0, k1):
        out = self._advance(
            self.state, self.control(k0), self.p, jnp.asarray(k0), jnp.asarray(k1 - k0)
        )
        state, stopped, bad, failed, worst = out
        self.state = state
        return bool(stopped), int(bad), np.asarray(failed), np.asarray(worst)

    def measure(self, k):
        vm, valid, amounts, a, gate, generation = self._measure(self.state, self.control(k), self.p)
        n = self.n
        return dict(
            vm=np.asarray(vm)[:n],
            valid=bool(valid),
            amounts=np.asarray(amounts)[:, :n],
            abundance=np.asarray(a),
            gate=np.asarray(gate),
            generation=np.asarray(generation)[:n],
        )

    def host_state(self):
        return {k: np.asarray(v) for k, v in self.state._asdict().items()}

    def load(self, saved):
        self.state = model.STATE_TYPE(*(jnp.asarray(saved[k]) for k in model.STATE_TYPE._fields))


FAILURE_NAMES = ("model_refused", *model.DEVICE_CHECKS)


def h_osmolarity():
    h = v3fx.HEREDITY_STATES["H"]
    return h[1] + h[2] + h[3] + v3fx.HEREDITY_FIXED_ANION_mM


def run_segments(
    stepper, marks, *, every, records, on_record=None, stop=None, start_k=0, save=None
):
    """Advance through the mark steps, measuring at each; returns (end step, refusal)."""
    volume = np.asarray(stepper.host_p.volume)[: stepper.n]
    k_now, last_save = start_k, time.perf_counter()
    worst = None
    for k in marks:
        if k <= k_now:
            continue
        stopped, bad, failed, diag = stepper.advance(k_now, k)
        worst = diag if worst is None else np.maximum(worst, diag)
        if stopped:
            refusal = dict(
                step=bad,
                time_s=bad * stepper.dt,
                failed=[n for n, f in zip(FAILURE_NAMES, failed, strict=True) if f],
                state_kept="the last accepted row before the refusal",
            )
            return k_now, refusal, worst
        k_now = k
        m = stepper.measure(k)
        m["t"] = k * stepper.dt
        m["regular"] = k % every == 0
        m["conc"] = m["amounts"][:3] / volume
        m["osm"] = m["amounts"].sum(axis=0) / volume
        records.append(m)
        if on_record is not None:
            on_record(m)
        if save is not None and time.perf_counter() - last_save > SAVE_EVERY_WALL_S:
            save(k_now, worst)
            last_save = time.perf_counter()
        if stop is not None and m["regular"]:
            reason = stop(m)
            if reason:
                return k_now, dict(stop=reason), worst
    return k_now, None, worst


def save_records(path, records, extra=None):
    keys = ("t", "vm", "conc", "osm", "abundance", "gate", "generation", "regular", "valid")
    data = {k: np.array([r[k] for r in records]) for k in keys}
    tmp = path.with_suffix(".tmp.npz")
    np.savez(tmp, **data, **(extra or {}))
    tmp.replace(path)


def load_records(path):
    z = np.load(path)
    keys = ("t", "vm", "conc", "osm", "abundance", "gate", "generation", "regular", "valid")
    return [{k: z[k][i] for k in keys} for i in range(len(z["t"]))]


# ------------------------------------------------------------------ parts


def part_predictions(args):
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    value = predictions() | dict(provenance=provenance())
    write_json(out / "predictions.json", value, exclusive=True)
    log(f"predictions for {len(value['arms'])} arms")


NUMERICS = dict(
    N1=dict(
        size=37,
        s=1.0,
        bracket="fast",
        formation=BRACKETS["fast"],
        end_s=600.0,
        every_s=2.0,
        kinds=("iso", "donor"),
        note="the first 21 events of the fast k = 1 schedule (every 27.6 s), alternating "
        "isolated and donor newcomers; formation fast (lag 2 min, tau 15 min)",
    ),
    N2=dict(
        size=19,
        s=0.6,
        bracket="stress",
        formation=dict(lag_s=10.0, time_constant_s=40.0),
        end_s=300.0,
        every_s=1.0,
        note="eight events every 20 s from 20 s (centre, interior and rim slots; isolated, "
        "H-donor and D-donor copies) with a compressed formation (lag 10 s, tau 40 s, the "
        "engine minimum; outside the literature range, a stress test of full coupling)",
    ),
)
NUMERICS_CRITERIA = dict(
    kind="cells.heredity_turnover_literature_numerics_criteria@1",
    status="written before the numerics segments",
    question="is dt 5 ms adequate against dt 1 ms (G2-Q1's qualified step) for the arms' "
    "readouts, on segments with replacement events and junction formation?",
    choose_5ms_if=[
        "no refusal and no failed device check at either step",
        "identical D sets (Vm above the U voltage) at every common record, except records "
        "within 1 s of a state change at either step; every state change (per cell, H to D "
        "or D to H) occurs at both steps, within 1 s",
        "max |Vm(5 ms) - Vm(1 ms)| at most 1 mV over all cells and records outside those "
        "windows (H, U and D are at least 15 mV apart; readouts resolve about 1 mV)",
        "max relative difference of cell amounts at most 1e-4, and of osmotic excess at most "
        "1e-4 (readouts resolve 0.1 percentage points)",
    ],
    otherwise="use 1 ms and re-size the arm set",
    cases=NUMERICS,
)


def numerics_events(name, dt):
    case = NUMERICS[name]
    if name == "N1":
        p = plan("iso", "fast", 1, case["size"], case["s"], dt, end_s=case["end_s"],
                 kinds=case["kinds"], grid_dt=0.005)  # fmt: skip
        return p["events"]
    _, _, neighbours = sheet()
    disc = set(disc_cells(case["size"]))
    by = {}
    for i in sorted(disc):
        by.setdefault(slot_class(i, case["size"]), []).append(i)
    centre = by["centre"][0]
    interior, corners, sides = by["interior"], by["rim_corner"], by["rim_side"]
    slots = [centre, corners[0], interior[0], sides[0], corners[3], interior[3], sides[3], sides[5]]
    donors = ["none", "outside", "inside", "none", "inside", "none", "outside", "none"]
    chosen = []
    for j, (slot, which) in enumerate(zip(slots, donors, strict=True)):
        earlier = set(slots[:j])  # A D donor is a founder not replaced before this event.
        donor = None
        if which == "outside":
            donor = min(x for x in neighbours[slot] if x not in disc)
        elif which == "inside":
            donor = min(x for x in neighbours[slot] if x in disc and x not in earlier)
        chosen.append((slot, donor))
    return [
        (int(round(20.0 * (j + 1) / dt)), slot, donor, f"n{j}")
        for j, (slot, donor) in enumerate(chosen)
    ]


def part_criteria(args):
    out = Path(args.output) / "numerics"
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "criteria.json", NUMERICS_CRITERIA | dict(provenance=provenance()),
               exclusive=True)  # fmt: skip


def part_numerics(args):
    name, dt = args.case, args.dt
    out = Path(args.output) / "numerics"
    if not (out / "criteria.json").exists():
        raise SystemExit("Write the numerics criteria (criteria part) before the segments")
    case = NUMERICS[name]
    events = numerics_events(name, dt)
    raw, _ = definition(case["size"], case["s"], dt, case["end_s"], events, case["formation"])
    spec = parse_spec(raw)
    tick = time.perf_counter()
    stepper = Stepper(spec)
    every = int(round(case["every_s"] / dt))
    end = int(round(case["end_s"] / dt))
    marks = sorted(set(range(every, end + 1, every)) | {k for k, *_ in events} | {end})
    records = []
    first = stepper.measure(0)
    first.update(t=0.0, regular=True)
    volume = np.asarray(stepper.host_p.volume)[: stepper.n]
    first["conc"], first["osm"] = (
        first["amounts"][:3] / volume,
        first["amounts"].sum(axis=0) / volume,
    )
    records.append(first)
    k_end, refusal, worst = run_segments(stepper, marks, every=every, records=records)
    label = f"{name}-dt{dt:g}"
    save_records(out / f"{label}.npz", records)
    write_json(
        out / f"{label}.json",
        dict(
            case=name,
            dt=dt,
            events=[dict(time_s=k * dt, slot=sl, donor=d, carrier=c) for k, sl, d, c in events],
            end_step=k_end,
            refusal=refusal,
            worst_diagnostics=dict(zip(model.DEVICE_DIAGNOSTICS, worst.tolist(), strict=True)),
            wall_s=time.perf_counter() - tick,
            provenance=provenance(),
        ),
    )
    log(f"numerics {label}: end {k_end * dt} s refusal {refusal}")


def transitions(times, d):
    """Per cell, the record times where its D state changes (after the first record)."""
    out = {}
    for i in range(d.shape[1]):
        change = np.flatnonzero(d[1:, i] != d[:-1, i]) + 1
        if len(change):
            out[i] = [(float(times[j]), bool(d[j, i])) for j in change]
    return out


def part_compare(args):
    out = Path(args.output) / "numerics"
    report = dict(kind="cells.heredity_turnover_literature_numerics@1", cases={})
    verdict = True
    for name in NUMERICS:
        fine, coarse = (load_records(out / f"{name}-dt{dt:g}.npz") for dt in (0.001, 0.005))
        meta = {
            dt: json.loads((out / f"{name}-dt{dt:g}.json").read_text()) for dt in (0.001, 0.005)
        }
        tf = {round(float(r["t"]), 6): r for r in fine if r["regular"]}
        tc = {round(float(r["t"]), 6): r for r in coarse if r["regular"]}
        common = sorted(set(tf) & set(tc))
        vf = np.array([tf[t]["vm"] for t in common])
        vc = np.array([tc[t]["vm"] for t in common])
        df, dc = vf > THRESHOLD_V, vc > THRESHOLD_V
        times = np.array(common)
        changes = dict(fine=transitions(times, df), coarse=transitions(times, dc))
        window = np.zeros_like(df)
        for which in changes.values():
            for i, rows in which.items():
                for t, _ in rows:
                    window[:, i] |= np.abs(times - t) <= 1.0 + 1e-9
        mismatch = (df != dc) & ~window
        dv = np.abs(vf - vc)
        af = np.array([tf[t]["conc"] for t in common])
        ac = np.array([tc[t]["conc"] for t in common])
        rel = np.abs(af - ac) / np.maximum(np.abs(af), 1e-30)
        of = np.array([tf[t]["osm"] for t in common])
        oc = np.array([tc[t]["osm"] for t in common])
        ex = np.abs(of - oc) / h_osmolarity()
        paired, unpaired = [], []
        for i in sorted(set(changes["fine"]) | set(changes["coarse"])):
            a_, b_ = changes["fine"].get(i, []), changes["coarse"].get(i, [])
            if len(a_) != len(b_) or any(x[1] != y[1] for x, y in zip(a_, b_, strict=False)):
                unpaired.append(dict(cell=i, fine=a_, coarse=b_))
                continue
            for x, y in zip(a_, b_, strict=True):
                paired.append(
                    dict(cell=i, to_D=x[1], fine_s=x[0], coarse_s=y[0], shift_s=y[0] - x[0])
                )
        refused = [meta[dt]["refusal"] for dt in meta if meta[dt]["refusal"] is not None]
        checks = dict(
            no_refusal=not refused,
            d_sets_identical_outside_windows=not bool(mismatch.any()),
            changes_paired_within_1s=not unpaired
            and all(abs(x["shift_s"]) <= 1.0 + 1e-9 for x in paired),
            vm_within_1mV=float(dv[~window].max(initial=0.0)) <= 1e-3,
            amounts_within_1em4=float(rel.max()) <= 1e-4,
            osmotic_excess_within_1em4=float(ex.max()) <= 1e-4,
        )
        verdict &= all(checks.values())
        report["cases"][name] = dict(
            common_records=len(common),
            checks=checks,
            max_vm_difference_mV_outside_windows=1e3 * float(dv[~window].max(initial=0.0)),
            max_vm_difference_mV_all=1e3 * float(dv.max()),
            rms_vm_difference_mV=1e3 * float(np.sqrt(np.mean(dv**2))),
            max_relative_amount_difference=float(rel.max()),
            max_osmotic_excess_difference=float(ex.max()),
            d_mismatch_records_outside_windows=int(mismatch.any(axis=1).sum()),
            d_count_final=dict(fine=int(df[-1].sum()), coarse=int(dc[-1].sum())),
            state_changes=paired,
            unpaired_state_changes=unpaired,
            refusals=refused,
            wall_s={str(dt): meta[dt]["wall_s"] for dt in meta},
        )
    report["choose"] = 0.005 if verdict else 0.001
    report["verdict"] = "5 ms adequate" if verdict else "use 1 ms"
    report["criteria"] = NUMERICS_CRITERIA["choose_5ms_if"]
    write_json(out / "verdict.json", report | dict(provenance=provenance()))
    log(f"numerics verdict: {report['verdict']}")


def part_importcheck(args):
    """No events: 60 s from each start against the sheet70 records (same world, 5 ms)."""
    out = Path(args.output) / "importcheck"
    out.mkdir(parents=True, exist_ok=True)
    report = dict(kind="cells.heredity_turnover_literature_importcheck@1", discs={})
    for size, s in HELD_DISCS if args.all_discs else HELD_DISCS[:1]:
        dt, end_s = 0.005, 60.0
        raw, _ = definition(size, s, dt, end_s, [], dict(BRACKETS["central"]))
        spec = parse_spec(raw)
        stepper = Stepper(spec)
        layout = layout_check(spec, size, s)
        rec = np.load(SHEET70 / f"longsheet-v2-disc{size}-s{s}" / "records" / "world-1-cells.npz")
        their_t = rec["times_s"] - START_S
        wanted = [t for t in their_t if 0 < t <= end_s + 1e-9]
        marks = [int(round(t / dt)) for t in wanted]
        records = []
        k_end, refusal, _ = run_segments(stepper, marks, every=marks[0] or 1, records=records)
        diffs = []
        for r in records:
            j = int(np.argmin(np.abs(their_t - r["t"])))
            diffs.append(float(np.max(np.abs(r["vm"] - rec["vm_V"][j]))))
        report["discs"][f"{size}-{s}"] = dict(
            layout_max_abs_difference=layout,
            records=len(records),
            max_vm_difference_V=max(diffs),
            refusal=refusal,
        )
        log(f"importcheck {size} {s}: {report['discs'][f'{size}-{s}']}")
    write_json(out / "importcheck.json", report | dict(provenance=provenance()))


def part_arm(args):
    name = args.arm
    a = parse_arm(name)
    base = Path(args.output)
    out = base / "arms" / name
    out.mkdir(parents=True, exist_ok=True)
    every_prediction = base / "predictions.json"
    if not every_prediction.exists():
        raise SystemExit("Write predictions.json (predictions part) before any arm")
    if not (out / "predictions.json").exists():
        arms = json.loads(every_prediction.read_text())["arms"]
        if name not in arms:
            raise SystemExit(f"{name} has no written prediction")
        write_json(out / "predictions.json", arms[name], exclusive=True)
    dt = args.dt
    p = plan(a["kind"], a["bracket"], a["k"], a["size"], a["s"], dt)
    raw, template = definition(a["size"], a["s"], dt, p["end_s"], p["events"], p["formation"])
    if not (out / "plan.json").exists():
        write_json(out / "plan.json", p)
        write_json(out / "definition.json", raw)
    tick = time.perf_counter()
    spec = parse_spec(raw)
    stepper = Stepper(spec)
    log(f"{name}: {len(p['events'])} events, end {p['end_s']} s, parsed and compiled set up "
        f"in {time.perf_counter() - tick:.1f} s")  # fmt: skip
    every = int(round(RECORD_S / dt))
    end = int(round(p["end_s"] / dt))
    marks = sorted(set(range(every, end + 1, every)) | {k for k, *_ in p["events"]} | {end})
    records, start_k, resumed = [], 0, None
    if args.resume and (out / "checkpoint.npz").exists():
        saved = dict(np.load(out / "checkpoint.npz"))
        stepper.load(saved)
        start_k = int(saved["step"])
        records = load_records(out / "records.npz")
        records = [r for r in records if int(round(float(r["t"]) / dt)) <= start_k]
        resumed = start_k * dt
        log(f"{name}: resumed at {resumed} s with {len(records)} records")
    volume = np.asarray(stepper.host_p.volume)[: stepper.n]
    if not records:
        first = stepper.measure(0)
        first.update(t=0.0, regular=True, conc=first["amounts"][:3] / volume,
                     osm=first["amounts"].sum(axis=0) / volume)  # fmt: skip
        records.append(first)
    osm_h = h_osmolarity()
    state = dict(all_h=0)
    progress = open(out / "progress.jsonl", "a", buffering=1)

    def on_record(m):
        if not m["regular"]:
            return
        d = m["vm"] > THRESHOLD_V
        if int(round(m["t"] / RECORD_S)) % 6 == 0:
            progress.write(json.dumps(dict(
                t=m["t"], d=int(d.sum()), generations=int(m["generation"].sum()),
                max_excess=float(m["osm"].max() / osm_h - 1.0),
                wall_s=time.perf_counter() - tick)) + "\n")  # fmt: skip

    def stop(m):
        d = m["vm"] > THRESHOLD_V
        if m["osm"].max() / osm_h - 1.0 > CENSOR:
            return "censor"
        state["all_h"] = state["all_h"] + 1 if not d.any() else 0
        if d.any():
            state.pop("all_h_since", None)
        if state["all_h"] >= 2:
            state.setdefault("all_h_since", m["t"] - RECORD_S)
        if "all_h_since" in state and m["t"] >= state["all_h_since"] + ALL_H_TAIL_S - 1e-9:
            return "all_h"
        return None

    def save(k_now, worst):
        save_records(out / "records.npz", records)
        tmp = out / "checkpoint.tmp.npz"
        np.savez(tmp, step=k_now, **stepper.host_state())
        tmp.replace(out / "checkpoint.npz")

    k_end, outcome, worst = run_segments(
        stepper, marks, every=every, records=records, on_record=on_record, stop=stop,
        start_k=start_k, save=save,
    )  # fmt: skip
    progress.close()
    save(k_end, worst)
    refusal = outcome if outcome is not None and "stop" not in outcome else None
    stop_reason = (outcome or {}).get("stop") or ("refusal" if refusal else "planned end")
    write_json(
        out / "result.json",
        dict(
            arm=name,
            engine_models=["resolved_pump_replacement@1 (inner resolved_pump_tissue@3)"],
            dt=dt,
            end_step=k_end,
            end_s=k_end * dt,
            planned_end_s=p["end_s"],
            stop=stop_reason,
            refusal=refusal,
            resumed_at_s=resumed,
            worst_device_diagnostics=None
            if worst is None
            else dict(zip(model.DEVICE_DIAGNOSTICS, worst.tolist(), strict=True)),
            wall_s=time.perf_counter() - tick,
            records=len(records),
            lineage_applied=model.lineage(spec, records[-1]["generation"]),
            provenance=provenance(),
        ),
    )
    log(f"{name}: stopped ({stop_reason}) at {k_end * dt} s; refusal {refusal}")
    analyse(out)
    return 0 if refusal is None else 3


# ------------------------------------------------------------------ analysis


def _jaccard(d, disc):
    union = np.sum(d | disc)
    return float(np.sum(d & disc) / union) if union else 1.0


def analyse(out):
    out = Path(out)
    p = json.loads((out / "plan.json").read_text())
    result = json.loads((out / "result.json").read_text())
    pred = json.loads((out / "predictions.json").read_text())
    records = load_records(out / "records.npz")
    size, dt = p["size"], p["dt"]
    disc_list = disc_cells(size)
    n_cells = len(records[0]["vm"])
    disc = np.zeros(n_cells, dtype=bool)
    disc[disc_list] = True
    osm_h = h_osmolarity()
    reg = [r for r in records if r["regular"]]
    t = np.array([float(r["t"]) for r in reg])
    d = np.array([r["vm"] > THRESHOLD_V for r in reg])
    jac = np.array([_jaccard(x, disc) for x in d])
    excess = np.array([r["osm"] / osm_h - 1.0 for r in reg])
    # Every record (regular and event-time rows) for the carriers' own histories.
    t_all = np.array([float(r["t"]) for r in records])
    d_all = np.array([r["vm"] > THRESHOLD_V for r in records])
    excess_all = np.array([r["osm"] / osm_h - 1.0 for r in records])
    by_time = {round(float(r["t"]), 9): r for r in records}
    events = [dict(step=k, slot=sl, donor=dn, carrier=c) for k, sl, dn, c in p["events"]]
    applied = [e for e in events if e["step"] < result["end_step"]]
    # Carriers: founders then newcomers, with their own records.
    carriers = []
    current = {i: dict(carrier=f"cell_{i}", slot=i, founder=True, birth_s=0.0) for i in disc_list}
    for e in applied:
        te = e["step"] * dt
        old = current[e["slot"]]
        old["death_s"] = te
        at = by_time.get(round(te, 9))
        rec = dict(carrier=e["carrier"], slot=e["slot"], founder=False, birth_s=te,
                   kind="donor" if e["donor"] is not None else "iso", donor=e["donor"])  # fmt: skip
        if at is not None and e["donor"] is not None:
            rec["donor_vm_at_event_mV"] = 1e3 * float(at["vm"][e["donor"]])
            rec["donor_D_at_event"] = bool(at["vm"][e["donor"]] > THRESHOLD_V)
            rec["arrival_osmotic_excess"] = float(at["osm"][e["donor"]] / osm_h - 1.0)
        else:
            rec["arrival_osmotic_excess"] = 0.0 if e["donor"] is None else None
        carriers.append(old)
        current[e["slot"]] = rec
    carriers.extend(current.values())
    lag, tau = p["formation"]["lag_s"], p["formation"]["time_constant_s"]
    for c in carriers:
        c["slot_class"] = slot_class(c["slot"], size)
        end_t = c.get("death_s") or result["end_s"]
        rows = [i for i, x in enumerate(t_all) if c["birth_s"] < x <= end_t + 1e-9]
        c["records"] = len(rows)
        if not rows:
            continue
        states = d_all[rows, c["slot"]]
        c["D_fraction_of_records"] = float(states.mean())
        c["D_at_first_record"] = bool(states[0])
        c["D_at_last_record"] = bool(states[-1])
        first_d = next((t_all[i] for i, s_ in zip(rows, states, strict=True) if s_), None)
        c["first_D_s"] = None if first_d is None else float(first_d)
        if not c["founder"] and first_d is not None:
            age = first_d - c["birth_s"]
            c["first_D_age_s"] = float(age)
            c["abundance_at_first_D"] = float(1.0 - np.exp(-max(0.0, age - lag) / tau))
        if c["founder"] or c.get("D_at_first_record"):
            lost = next((t_all[i] for i, s_ in zip(rows, states, strict=True) if not s_), None)
            c["first_H_s"] = None if lost is None else float(lost)
        ex = excess_all[rows, c["slot"]]
        c["max_osmotic_excess"] = float(ex.max())
        if c.get("arrival_osmotic_excess") is not None:
            base = c["arrival_osmotic_excess"]
            c["max_excess_against_arrival"] = float((1 + ex.max()) / (1 + base) - 1.0)
    turn = p["turnover_complete_s"]
    absorbed = result["stop"] == "all_h"

    def at_or_before(x, values=None):
        values = jac if values is None else values
        if x > t[-1] + 1e-9:
            return 0.0 if absorbed else None  # All H is absorbing; otherwise not reached.
        i = np.searchsorted(t, x + 1e-9) - 1
        return None if i < 0 else float(values[i])

    def basis(x):
        if x <= t[-1] + 1e-9:
            return "record"
        return "absorbed (all H)" if absorbed else result["stop"]

    def window(lo, hi):
        m = (t > lo) & (t <= hi + 1e-9)
        return float(jac[m].min()) if m.any() else None

    newcomers = [c for c in carriers if not c["founder"]]
    converted = [c for c in newcomers if c.get("first_D_s") is not None and c["kind"] == "iso"]
    first_lost = next(
        (float(x) for x, row in zip(t, d, strict=True) if row[disc].sum() < size), None
    )
    all_h = next((float(x) for x, row in zip(t, d, strict=True) if not row.any()), None)
    below = next((float(x) for x, j in zip(t, jac, strict=True) if j < 0.8), None)
    flag_t = next((float(x) for x, e in zip(t, excess, strict=True) if e.max() > FLAG), None)
    censor_t = next((float(x) for x, e in zip(t, excess, strict=True) if e.max() > CENSOR), None)
    reached = [x <= result["end_s"] + 1e-9 for x in turn]
    b1 = bool(all(reached) and censor_t is None and below is None)
    classes = {}
    for c in newcomers:
        if c.get("records"):
            k = (c["slot_class"], c["kind"], "D donor" if c.get("donor_D_at_event") else
                 "H donor" if c.get("donor_D_at_event") is False else "template")  # fmt: skip
            entry = classes.setdefault(
                " / ".join(k),
                dict(newcomers=0, ever_D=0, D_at_end_of_life=0, ages=[], abundances=[]),
            )
            entry["newcomers"] += 1
            entry["ever_D"] += int(c.get("first_D_s") is not None)
            entry["D_at_end_of_life"] += int(bool(c.get("D_at_last_record")))
            if c.get("first_D_age_s") is not None and not c.get("D_at_first_record"):
                entry["ages"].append(c["first_D_age_s"])
                entry["abundances"].append(c["abundance_at_first_D"])
    for entry in classes.values():
        ages, abundances = entry.pop("ages"), entry.pop("abundances")
        entry["converted_from_H"] = len(ages)
        entry["median_conversion_age_s"] = float(np.median(ages)) if ages else None
        entry["conversion_abundance_range"] = (
            [float(min(abundances)), float(max(abundances))] if abundances else None
        )
    # Collective loss: the largest fall of the sheet's D count between two 10 s records,
    # less the D carriers removed by events in that interval.
    total = d.sum(axis=1)
    drops = []
    for i in range(1, len(t)):
        removed = sum(
            1
            for e in applied
            if t[i - 1] < e["step"] * dt <= t[i] + 1e-9
            and (r_ := by_time.get(round(e["step"] * dt, 9))) is not None
            and r_["vm"][e["slot"]] > THRESHOLD_V
        )
        drops.append((int(total[i - 1] - total[i]) - removed, float(t[i])))
    largest = max(drops, default=(0, None))
    largest = largest if largest[0] > 0 else (0, None)
    after_cue = START_S - CUE_OFF_S
    summary = dict(
        kind="cells.heredity_turnover_literature_outcome@1",
        arm=out.name,
        stop=result["stop"],
        end_s=result["end_s"],
        planned_end_s=result["planned_end_s"],
        refusal=result["refusal"],
        residence_s=p["residence_s"],
        turnovers_complete_s=turn,
        turnovers_reached=reached,
        jaccard_after_turnover=[at_or_before(x) for x in turn],
        jaccard_after_turnover_basis=[basis(x) for x in turn],
        d_inside_after_turnover=[at_or_before(x, d[:, disc].sum(axis=1)) for x in turn],
        jaccard_min_in_turnover=[window(0.0, turn[0]), window(turn[0], turn[1])],
        largest_10s_fall_of_D_beyond_events=dict(cells=largest[0], at_s=largest[1]),
        first_jaccard_below_0p8_s=below,
        first_disc_loss_s=first_lost,
        all_h_s=all_h,
        d_inside_end=int(d[-1][disc].sum()),
        max_d_outside=int(d[:, ~disc].sum(axis=1).max()),
        newcomers=len(newcomers),
        isolated_newcomers_ever_D=len(converted),
        newcomer_classes=classes,
        founders_lost_before_replacement=sum(
            1 for c in carriers if c["founder"] and c.get("first_H_s") is not None
        ),
        d_newcomers_lost_before_replacement=sum(
            1 for c in newcomers if c.get("D_at_first_record") and c.get("first_H_s") is not None
        ),
        osmotic=dict(
            reference="H start (every founder at t = 0 of sheet70, and every isolated newcomer)",
            first_flag_s=flag_t,
            first_censor_s=censor_t,
            max_excess=float(excess.max()),
            first_flag_after_cue_min=None if flag_t is None else (flag_t + after_cue) / 60,
            first_censor_after_cue_min=None if censor_t is None else (censor_t + after_cue) / 60,
            max_excess_against_arrival_donor_copies=max(
                (
                    c["max_excess_against_arrival"]
                    for c in newcomers
                    if c["kind"] == "donor" and "max_excess_against_arrival" in c
                ),
                default=None,
            ),
        ),  # fmt: skip
        b1_jaccard_0p8_through_two_turnovers=b1,
        series=dict(
            t_s=t.tolist(),
            d_inside=d[:, disc].sum(axis=1).tolist(),
            d_outside=d[:, ~disc].sum(axis=1).tolist(),
            jaccard=jac.tolist(),
            max_excess=excess.max(axis=1).tolist(),
        ),  # fmt: skip
        carriers=carriers,
    )
    summary["against_prediction"] = compare_prediction(summary, pred)
    write_json(out / "outcome.json", summary)
    return summary


def _within(value, bounds):
    if value is None or bounds is None:
        return None
    return bounds[0] - 1e-9 <= value <= bounds[1] + 1e-9


def compare_prediction(o, pred):
    j = o["jaccard_after_turnover"]
    out = dict(
        b1=dict(predicted=pred["b1"], observed="pass" if o["b1_jaccard_0p8_through_two_turnovers"]
                else "fail"),
        j_after_first_turnover=dict(predicted=pred["j_after_first_turnover"], observed=j[0],
                                    within=_within(j[0], pred["j_after_first_turnover"])),
        j_after_second_turnover=dict(predicted=pred["j_after_second_turnover"], observed=j[1],
                                     within=_within(j[1], pred["j_after_second_turnover"])),
        d_outside=dict(predicted=pred.get("d_outside"), observed=o["max_d_outside"]),
        refusals=dict(predicted=0, observed=0 if o["refusal"] is None else 1),
        osmotic=dict(predicted=pred["osmotic"], observed=dict(
            flag_after_cue_min=o["osmotic"]["first_flag_after_cue_min"],
            censor_after_cue_min=o["osmotic"]["first_censor_after_cue_min"])),
        newcomers=dict(predicted=pred["newcomers_converting"], observed=o["newcomer_classes"]),
    )  # fmt: skip
    if pred.get("all_h_by_s") is not None:
        out["all_h"] = dict(predicted_s=pred["all_h_by_s"], observed_s=o["all_h_s"],
                            within=_within(o["all_h_s"], pred["all_h_by_s"]))  # fmt: skip
    return out


def part_analyse(args):
    base = Path(args.output) / "arms"
    names = (
        sorted(p.name for p in base.iterdir() if (p / "result.json").exists())
        if args.all
        else [args.arm]
    )
    table = {}
    for name in names:
        o = analyse(base / name)
        table[name] = {k: o[k] for k in ("stop", "end_s", "planned_end_s", "refusal",
                                         "turnovers_complete_s", "jaccard_after_turnover",
                                         "jaccard_after_turnover_basis",
                                         "d_inside_after_turnover", "jaccard_min_in_turnover",
                                         "first_jaccard_below_0p8_s", "first_disc_loss_s",
                                         "all_h_s", "max_d_outside", "newcomers",
                                         "isolated_newcomers_ever_D", "newcomer_classes",
                                         "founders_lost_before_replacement",
                                         "d_newcomers_lost_before_replacement",
                                         "largest_10s_fall_of_D_beyond_events",
                                         "b1_jaccard_0p8_through_two_turnovers",
                                         "osmotic", "against_prediction")}  # fmt: skip
        log(f"{name}: {json.dumps(table[name], default=float)[:400]}")
    if args.all:
        write_json(Path(args.output) / "summary.json", dict(arms=table, provenance=provenance()))


PARTS = dict(
    predictions=part_predictions,
    criteria=part_criteria,
    importcheck=part_importcheck,
    numerics=part_numerics,
    compare=part_compare,
    arm=part_arm,
    analyse=part_analyse,
)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("part", choices=sorted(PARTS))
    parser.add_argument("--output", required=True)
    parser.add_argument("--case", choices=sorted(NUMERICS))
    parser.add_argument("--dt", type=float, default=0.005)
    parser.add_argument("--arm")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--all-discs", action="store_true")
    args = parser.parse_args(argv)
    return PARTS[args.part](args) or 0


if __name__ == "__main__":
    sys.exit(main())
