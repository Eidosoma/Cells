"""Design pre-screen 8: newcomer conversion next to the retention window (development, not judged).

Question (heredity design E07-v1, stage B renewal): at each junction coupling,
does a reset H newcomer inside a written D disc convert to D while the disc
survives, and does a newcomer in the H ring just outside the disc stay H?
Pre-screen 7 (heredity_prescreen) mapped the retention window, the couplings
at which the written disc is a stable stationary state. This maps the
conversion window next to it.

Engine model analysed: resolved_pump_tissue@3, unmodified, through
stationary_continuation_analysis@1 (cells.analysis.stationary) in slow mode,
and forward runs with the model's own checked IMEX step through the analysis
step map. Worlds, units, the disc test and the sweep machinery are pre-screen
7's (heredity_prescreen.Case, sweep, solve, classify, units): held-bath sheets
of heredity cells with E07-v1's voltage-gated junctions, theta = s x 1.657.

Newcomer (design.json protocol.replacement_boundary_specification): the slot's
intracellular amounts and channel gates are reset to the isolated single-cell
H steady state (in these homogeneous sheets the sheet's own H initial values),
its incident junction gates to the open initial value (the gate's steady state
at Vj = 0, 0.967, which is every junction's initial value in an all-H world),
and everything else is retained. Slots: the disc centre, the disc's corner cell
(r, 0) (three disc neighbours, the most exposed boundary cell) and the outside
cell (r + 1, -1) of the first H ring (two disc neighbours, the most exposed
outside cell).

Parts:
- stationary: for each disc (19, 37 cells in the 127-cell sheet; 61, 91 in the
  217-cell sheet) and inside slot, the "defect" state (the disc with that slot
  at H) is continued from theta 0.005 as in pre-screen 7, with its stability
  loss and branch end bisected; outcomes at s = 0.2, 0.3, 0.5, 0.7, 1.0, 1.5
  and at 0.99 x the disc's own stability end. A stable defect means the
  newcomer does not convert; absent or unstable means it does not persist as H.
  The same for a 25% batch (a 9-cell ring sector) in the 37-cell disc. Closers:
  (a) do seed 3's cells 64 and 73 (pre-screen 7 extras, CV 15%) have a D state
  of their own (single-cell world, homotopy in the factors); (b) the 37-cell
  disc's critical theta for seed 1 at the design's per-cell CV of 10%.
- transient: newcomers placed in the stationary disc at about three couplings
  per disc (the window's lowest grid point and edge, and the grid points either
  side of a change in the stationary answer), run forward; outcome (converts,
  stays H, disc lost) and latency. Then the 25% batch at the 37-cell disc's
  slowest converting coupling.

Host ledger checks are not run in the forward runs (no ledgers are carried).

Usage: python -m validation.stationary.heredity_conversion --output DIR
       (--stationary | --transient STATIONARY_JSON | --summarize: DIR holds stationary/ and
       transient/)
"""

import argparse
import json
import sys
import time
import traceback
from pathlib import Path

import jax
import numpy as np

jax.config.update("jax_enable_x64", True)

from cells import __version__  # noqa: E402
from cells.analysis import stationary as sa  # noqa: E402
from cells.core.specs import parse_spec  # noqa: E402
from validation.stationary import heredity_prescreen as hp  # noqa: E402
from validation.stationary import targets, worlds  # noqa: E402

PRESCREEN_7 = Path(
    "/mnt/workspaces/Cells/heredity-design-20261108-01/prescreen-07-stationary/final.json"
)
DISCS = ((6, 2), (6, 3), (8, 4), (8, 5))  # (sheet radius, disc radius): 19, 37 | 61, 91 cells
MULTIPLIERS = (0.2, 0.3, 0.5, 0.7, 1.0, 1.5)
EDGE_FRACTION = 0.99  # the "own stability end" point, just inside the retention window
CLASSIFY_FROM = 0.05  # theta; spectra from s = 0.03 up
BISECTIONS = 10  # as pre-screen 7's extras
BATCH_CELLS = 9  # 25% of the 37-cell disc
DT = 5e-3  # admitted by check_steps (pre-screen 7)
TIMES = (0, 0.02, 0.05, 0.1, 0.2, 0.3, 0.5, 0.7, 1, 1.5, 2, 3, 5, 7, 10, 15, 20, 30, 45, 60)
TIMES += (90, 120, 180, 240, 300, 420)  # then HORIZON
HORIZON = 600.0
SEED3 = dict(seed=3, cell_cv=0.15, junction_cv=0.20)
SEED3_CELLS = (64, 73)
CV10 = dict(seed=1, cell_cv=0.10, junction_cv=0.20)
HOMOTOPY = np.linspace(0.0, 1.0, 11)
HOMOTOPY_BISECTIONS = 7

_log = hp._log


def _states():
    from validation.tissue import surface_pump_v3_fixtures as fx

    return {k: v[:4] for k, v in fx.HEREDITY_STATES.items()}


class Pattern(hp.Case):
    """Pre-screen 7's gated homogeneous sheet whose written pattern is the disc minus holes."""

    def __init__(self, sheet_radius, disc_radius, holes=()):
        super().__init__(sheet_radius, disc_radius, True, dt=DT)
        self.full = self.disc.copy()
        self.holes = tuple(int(i) for i in holes)
        if self.holes:
            self.disc = self.full.copy()
            self.disc[list(self.holes)] = False
            s = _states()
            written = [s["D"] if d else s["H"] for d in self.disc]
            raw = worlds.e07_sheet_definition(written, self.edges, gated=True, dt=DT)
            spec = parse_spec(worlds.ionic_background(raw))
            self.written = self.pb.coordinates(*self.pb.model.initial_values(spec))
        self.label = dict(self.label, holes=list(self.holes), pattern_d_cells=int(self.disc.sum()))


def slots(case, disc_radius):
    """centre; boundary = corner (r, 0), 3 disc neighbours; outside = (r + 1, -1), 2 disc
    neighbours; side = mid-side boundary cell (r, -1), 4 disc neighbours (follow-up)."""
    index = {c: i for i, c in enumerate(case.cells)}
    r = disc_radius
    return dict(
        centre=index[(0, 0)],
        boundary=index[(r, 0)],
        outside=index[(r + 1, -1)],
        side=index[(r, -1)],
    )


def sector(case, count=BATCH_CELLS):
    """The count non-centre disc cells nearest the +q axis in angle (a ring sector)."""
    keyed = []
    for i, (q, r) in enumerate(case.cells):
        if case.full[i] and (q, r) != (0, 0):
            angle = np.arctan2(np.sqrt(3) / 2 * r, q + r / 2)
            keyed.append((round(abs(angle), 9), round(angle, 9), worlds.ring((q, r)), i))
    return [k[-1] for k in sorted(keyed)[:count]]


def newcomer_index(case, cells):
    """Coordinate positions reset for newcomers in cells: amounts, channel gates, incident gates."""
    cells, n, pb = set(cells), len(case.cells), case.pb
    owner_channel = np.array([int(c.membrane_id.split("_")[-1]) for c in pb.spec.model.channels])
    out, start = [], 0
    for b in pb.blocks:
        if b.field == "amount_increment":
            mask = np.isin(b.flat % n, list(cells))
        elif b.field == "channel_gate":
            mask = np.isin(owner_channel[b.flat % len(owner_channel)], list(cells))
        elif b.field == "junction_gate":
            mask = np.array([a in cells or c in cells for a, c in (case.edges[k] for k in b.flat)])
        else:
            raise ValueError(f"unexpected block {b.field}")
        out.append(np.flatnonzero(mask) + start)
        start += len(b.flat)
    return np.concatenate(out)


def place(case, u, cells):
    """Newcomers in cells: those entries from the isolated-H, open-gate initial state."""
    index = newcomer_index(case, cells)
    new = np.array(u, copy=True)
    new[index] = np.asarray(case.pb.anchor)[index]
    return new


def retention():
    """Pre-screen 7's stability loss and branch end for the gated homogeneous discs."""
    rows = json.loads(PRESCREEN_7.read_text())["slow"]
    out = {}
    for r in rows:
        if r["gating"] == "voltage-gated" and not r["heterogeneity"] and not r.get("start"):
            out[(r["sheet_cells"], r["disc_cells"])] = dict(
                theta_stability_loss=r["theta_stability_loss"], theta_end=r["theta_end"]
            )
    return out


def grid(theta_unit, theta_loss):
    edge = EDGE_FRACTION * theta_loss / theta_unit
    return sorted({*MULTIPLIERS, edge}), edge


def _outcomes(result, scales, theta_unit):
    return {f"{s:.4g}": hp.outcome(result, s * theta_unit) for s in scales}


def stationary(output):
    """Defect states (disc with slots at H) at the grid, plus the two closers."""
    hp.BISECTIONS = BISECTIONS
    u = hp.units()
    unit = u["theta_per_unit_scale"]
    kept = retention()
    out = dict(
        kind="cells.heredity_design_prescreen@8_stationary",
        scope="Design input only (development analysis, not judged).",
        cells_version=__version__,
        units=u,
        prescreen_7=str(PRESCREEN_7),
        edge_fraction=EDGE_FRACTION,
        bisections=BISECTIONS,
        classify_from_theta=CLASSIFY_FROM,
        discs=[],
        failures=[],
    )
    for sheet, radius in DISCS:
        base = Pattern(sheet, radius)
        key = (len(base.cells), int(base.full.sum()))
        theta_loss = kept[key]["theta_stability_loss"]
        scales, edge = grid(unit, theta_loss)
        where = slots(base, radius)
        entry = dict(
            sheet_cells=key[0],
            disc_cells=key[1],
            retention=dict(kept[key], s_stability_loss=theta_loss / unit),
            scales=scales,
            edge_scale=edge,
            inside_window={f"{s:.4g}": bool(s * unit < theta_loss) for s in scales},
            slots=where,
            defects={},
        )
        holes = {k: [where[k]] for k in ("centre", "boundary")}
        if key[1] == 37:
            holes["batch"] = sector(base)
        for name, cells in holes.items():
            _log(f"defect {name} {cells} in disc {key[1]} (sheet {key[0]})")
            try:
                case = Pattern(sheet, radius, cells)
                result = hp.sweep(case, unit, np.asarray(scales), classify_from=CLASSIFY_FROM)
                result["outcomes"] = _outcomes(result, scales, unit)
                entry["defects"][name] = result
                _log(f"  outcomes {result['outcomes']}")
            except Exception as error:  # Kept as evidence.
                out["failures"].append(
                    dict(case=[sheet, radius, name], error=repr(error), tb=traceback.format_exc())
                )
        out["discs"].append(entry)
    for name, fn in (("seed3_cells", seed3_cells), ("cv10", cv10)):
        _log(f"closer {name}")
        try:
            out[name] = fn(unit)
        except Exception as error:  # Kept as evidence.
            out["failures"].append(dict(case=name, error=repr(error), tb=traceback.format_exc()))
    with open(output / "stationary.json", "x") as stream:
        json.dump(targets._json(out), stream, indent=1)
    with open(output / "stationary_table.md", "x") as stream:
        stream.write(stationary_table(targets._json(out)) + "\n")
    return out


def _one_cell(factors, state="D", guess=None):
    """The isolated cell with these factors: Newton (no pseudo-transient) from guess."""
    s = _states()
    raw = worlds.e07_sheet_definition([s[state]], [], gated=True, dt=DT, cell_factors=[factors])
    pb = sa.problem(parse_spec(worlds.ionic_background(raw)), mode="slow")
    result = sa.newton(pb, pb.anchor if guess is None else guess, globalization="newton")
    out = dict(converged=bool(result.converged), message=result.message)
    if result.converged:
        v = float(np.asarray(pb.evaluate(result.u, None)[3])[0])
        st = sa.stability(pb, result.u, count=4)
        out.update(
            voltage_mV=1e3 * v,
            is_D=bool(v > s["U"][0]),
            classification=st["classification"],
            leading_eigenvalues_per_s=st["eigenvalues_per_s"][:2],
        )
    return out, (result.u if result.converged else None)


def seed3_cells(theta_unit=None):
    """Closer (a): D of seed 3's cells 64 and 73 on their own, by homotopy factors**lambda."""
    sheet_cells, sheet_edges = worlds.hexagon(hp.SHEET_RADIUS)
    factors, _ = worlds.e07_heterogeneity(len(sheet_cells), len(sheet_edges), **SEED3)
    out = dict(heterogeneity=SEED3, cells=[])
    for i in SEED3_CELLS:
        f = factors[i]

        def at(lam, guess, f=f):
            return _one_cell({k: v**lam for k, v in f.items()}, guess=guess)

        path, guess, last_ok = [], None, None
        for lam in HOMOTOPY:
            point, u = at(lam, guess)
            ok = point["converged"] and point["is_D"]
            path.append(dict(lam=float(lam), **point))
            if not ok:
                break
            guess, last_ok = u, float(lam)
        fold = None
        if last_ok is not None and last_ok < 1.0:
            lo, hi = last_ok, path[-1]["lam"]
            for _ in range(HOMOTOPY_BISECTIONS):
                mid = 0.5 * (lo + hi)
                point, u = at(mid, guess)
                if point["converged"] and point["is_D"]:
                    lo, guess = mid, u
                else:
                    hi = mid
            fold = dict(lam_bracket=[lo, hi], factors_at_lo={k: v**lo for k, v in f.items()})
        single = {}
        for k in f:
            point, _ = _one_cell({kk: (f[kk] if kk == k else 1.0) for kk in f})
            single[k] = point
        d_draw, _ = _one_cell(f)
        h_draw, _ = _one_cell(f, state="H")
        out["cells"].append(
            dict(
                cell=i,
                factors=f,
                d_at_draw_from_written_D=d_draw,
                h_at_draw=h_draw,
                homotopy=path,
                d_branch_end=fold,
                d_exists_at_draw=bool(last_ok == 1.0),
                one_factor_at_a_time=single,
            )
        )
        _log(f"  cell {i}: D at draw {last_ok == 1.0}, fold {fold}")
    return out


def cv10(theta_unit):
    """Closer (b): seed 1 at per-cell CV 10%, per-junction CV 20%, 37-cell disc."""
    case = hp.Case(hp.SHEET_RADIUS, 3, True, heterogeneity=CV10)
    return hp.sweep(case, theta_unit, np.asarray(hp.ARMS), classify_from=hp.CLASSIFY_FROM)


def stationary_table(out):
    lines = []
    for e in out["discs"]:
        scales = [f"{s:.4g}" for s in e["scales"]]
        kept = e["retention"]
        lines += [
            f"disc {e['disc_cells']} (sheet {e['sheet_cells']}): retention stable up to theta "
            f"{kept['theta_stability_loss']:.4g} (s {kept['s_stability_loss']:.4g})",
            "",
            "| defect | stable up to theta | loss | ends | "
            + " | ".join(f"s {s}" for s in scales)
            + " |",
            "|---|---|---|---|" + "---|" * len(scales),
            "| (disc retained) | | | | "
            + " | ".join("in window" if e["inside_window"][s] else "outside" for s in scales)
            + " |",
        ]
        for name, d in e["defects"].items():
            sb, eb = d.get("stability_boundary"), d.get("existence_boundary")
            loss = "-" if not sb or sb.get("theta") is None else f"{sb['theta']:.4g}"
            kind = "-" if not sb or not sb.get("kind") else sb["kind"].split(" ")[0]
            end = "-" if not eb else f"{eb['theta']:.4g}"
            if d.get("start"):
                loss, kind = "no start", "-"
            lines.append(
                f"| {name} | {loss} | {kind} | {end} | "
                + " | ".join(d["outcomes"][s] for s in scales)
                + " |"
            )
        lines.append("")
    return "\n".join(lines)


# ------------------------------------------------------------------ transients


def disc_state(case, scale, theta_unit, steps_per_e=4):
    """The stationary full disc at scale, by continuation from theta 0.005 (None if lost)."""
    lo = hp.THETA_RANGE[0] / theta_unit
    count = max(2, int(np.ceil(steps_per_e * np.log(scale / lo))) + 1)
    path = np.geomspace(lo, scale, count)
    u, history = np.asarray(case.written), []
    for s in path:
        guess = u
        if len(history) > 1:
            (x0, u0), (x1, u1) = history[-2], history[-1]
            guess = u1 + (u1 - u0) * (np.log(s) - x1) / (x1 - x0)
        solution = hp.solve(case, guess, s) or hp.solve(case, u, s)
        if solution is None or not case.is_disc(case.voltages(solution.u, s)):
            return None
        u = solution.u
        history.append((np.log(s), u))
    return u


def _record(case, u, scale, t, cells):
    v = case.voltages(u, scale)
    d = v > case.threshold
    mine = np.zeros(len(d), dtype=bool)
    mine[list(cells)] = True
    return dict(
        time_s=t,
        slots_d=int(d[mine].sum()),
        disc_other_d=int(d[case.full & ~mine].sum()),
        outside_other_d=int(d[~case.full & ~mine].sum()),
        slot_voltage_mV=[float(1e3 * v[i]) for i in cells],
        disc_voltage_range_mV=[float(1e3 * v[case.full].min()), float(1e3 * v[case.full].max())],
    )


def run(case, advance, u, scale, cells, inside):
    """Forward from u with newcomers in cells; stops early once the outcome is settled."""
    rows, t = [_record(case, u, scale, 0.0, cells)], 0.0
    others = int(case.full.sum()) - (len(cells) if inside else 0)
    converted_at = None
    for target in (*TIMES[1:], HORIZON):
        k = int(round((target - t) / DT))
        rate = np.asarray(advance(u, scale, k))
        if not np.all(np.isfinite(rate)):
            rows.append(dict(time_s=target, refused="a step was refused (NaN)"))
            break
        u, t = u + k * DT * rate, target
        row = _record(case, u, scale, t, cells)
        rows.append(row)
        total = row["slots_d"] + row["disc_other_d"] + row["outside_other_d"]
        if total == 0:
            break
        full = row["disc_other_d"] == others and row["outside_other_d"] == 0
        if inside and full and row["slots_d"] == len(cells):
            converted_at = t if converted_at is None else converted_at
            if t >= max(60.0, 3 * converted_at):
                break
        else:
            converted_at = None
    return rows, u


def verdict(rows, cells, others, inside):
    """Outcome and latency bracket from the records."""
    records = [r for r in rows if "slots_d" in r]
    last = records[-1]
    refused = any("refused" in r for r in rows)
    intact = last["disc_other_d"] == others and last["outside_other_d"] == 0
    n = len(cells)
    if last["slots_d"] + last["disc_other_d"] + last["outside_other_d"] == 0:
        outcome = "disc lost (all H)"
    elif not intact:
        outcome = "disc damaged" if last["outside_other_d"] == 0 else "D spread outside"
    elif last["slots_d"] == n:
        outcome = "converts to D" if inside else "goes to D (spurious)"
    elif last["slots_d"] == 0:
        outcome = "stays H"
    else:
        outcome = f"partial ({last['slots_d']} of {n} D)"
    latency = None
    if last["slots_d"] == n and intact:
        k = len(records) - 1
        while k > 0 and records[k - 1]["slots_d"] == n:
            k -= 1
        latency = [records[k - 1]["time_s"] if k else 0.0, records[k]["time_s"]]
    return dict(
        outcome=outcome, latency_bracket_s=latency, last_time_s=last["time_s"], refused=refused
    )


def _defect(entry, name, s):
    return entry["defects"].get(name, {}).get("outcomes", {}).get(f"{s:.4g}")


def choose_points(entry):
    """The window's lowest point and edge, the points either side of each change of the
    inside slots' stationary answer, and the middle point if that leaves fewer than three."""
    window = [s for s in entry["scales"] if entry["inside_window"][f"{s:.4g}"]]

    def answer(s):
        return tuple(_defect(entry, k, s) == "stable" for k in ("centre", "boundary"))

    points = {window[0], window[-1]}
    for a, b in zip(window, window[1:], strict=False):
        if answer(a) != answer(b):
            points |= {a, b}
    if len(points) < 3:
        points.add(window[len(window) // 2])
    return sorted(points)


def transient(output, stationary_path):
    """Newcomers placed in the stationary disc, forward; then the 37-cell 25% batch."""
    saved = json.loads(Path(stationary_path).read_text())
    unit = hp.units()["theta_per_unit_scale"]
    out = dict(
        kind="cells.heredity_design_prescreen@8_transient",
        scope="Design input only (development analysis, not judged); no ledgers carried.",
        stationary=str(stationary_path),
        dt_s=DT,
        record_times_s=[*TIMES, HORIZON],
        runs=[],
        batch=None,
        failures=[],
    )
    progress = open(output / "runs.jsonl", "x")  # one line per finished run, as it lands

    def keep(res):
        out["runs"].append(res)
        progress.write(json.dumps(targets._json(res)) + "\n")
        progress.flush()

    for entry in saved["discs"]:
        try:
            case, advance = _disc_transients(entry, unit, keep)
            if entry["disc_cells"] == 37 and "batch" in entry["defects"]:
                out["batch"] = batch(case, advance, entry, out["runs"], unit)
                progress.write(json.dumps(targets._json(dict(batch=out["batch"]))) + "\n")
                progress.flush()
        except Exception as error:  # Kept as evidence.
            out["failures"].append(
                dict(case=entry["disc_cells"], error=repr(error), tb=traceback.format_exc())
            )
    progress.close()
    with open(output / "transient.json", "x") as stream:
        json.dump(targets._json(out), stream, indent=1)
    with open(output / "transient_table.md", "x") as stream:
        stream.write(transient_table(targets._json(out)) + "\n")
    return out


def _disc_transients(entry, unit, keep):
    """Single newcomers at each chosen point of one disc; keep(result) per run."""
    sheet, radius = next((s, r) for s, r in DISCS if 3 * r * (r + 1) + 1 == entry["disc_cells"])
    case = Pattern(sheet, radius)
    advance = jax.jit(lambda x, s, k, c=case: c.pb.step_residual(x, s, k))
    points = choose_points(entry)
    _log(f"disc {entry['disc_cells']}: transient points s {points}")
    for s in points:
        u_disc = disc_state(case, s, unit)
        if u_disc is None:
            keep(dict(disc_cells=entry["disc_cells"], scale=s, error="no disc"))
            continue
        for name in ("centre", "boundary", "outside"):
            cells, inside = [entry["slots"][name]], name != "outside"
            others = int(case.full.sum()) - (1 if inside else 0)
            started = time.perf_counter()
            try:
                rows, u_end = run(case, advance, place(case, u_disc, cells), s, cells, inside)
            except Exception as error:  # Kept as evidence.
                keep(
                    dict(
                        disc_cells=entry["disc_cells"],
                        scale=s,
                        slot=name,
                        error=repr(error),
                        tb=traceback.format_exc(),
                    )
                )
                continue
            v_gap = np.max(np.abs(case.voltages(u_end, s) - case.voltages(u_disc, s)))
            res = dict(
                disc_cells=entry["disc_cells"],
                scale=s,
                theta=s * unit,
                slot=name,
                cells=cells,
                stationary=_defect(entry, name, s) if inside else None,
                **verdict(rows, cells, others, inside),
                max_abs_V_from_disc_mV=1e3 * float(v_gap),
                wall_seconds=time.perf_counter() - started,
                trajectory=rows,
            )
            keep(res)
            _log(
                f"  s {s:.4g} {name}: {res['outcome']} latency {res['latency_bracket_s']} "
                f"(defect {res['stationary']}, {res['wall_seconds']:.0f} s wall)"
            )
    return case, advance


def batch(case, advance, entry, runs, unit):
    """The 9-cell sector at the converting s with the slowest single-newcomer conversion."""
    mine = [r for r in runs if "outcome" in r and r["disc_cells"] == 37 and r["slot"] != "outside"]
    converting = {}
    for r in mine:
        converting.setdefault(r["scale"], []).append(r)
    candidates = [
        (max(x["latency_bracket_s"][1] for x in rs), s)
        for s, rs in converting.items()
        if all(x["outcome"] == "converts to D" for x in rs)
    ]
    if not mine:
        return dict(error="no single-newcomer runs to choose from")
    if candidates:
        latency, s = max(candidates)
        why = f"slowest converting point (single-newcomer latency up to {latency:g} s)"
    else:
        s = max(r["scale"] for r in mine)
        why = "no point where both single newcomers converted; the edge point"
    cells = entry["defects"]["batch"]["case"]["holes"]
    _log(f"batch {cells} at s {s:.4g}: {why}")
    u_disc = disc_state(case, s, unit)
    if u_disc is None:
        return dict(scale=s, error="no disc")
    others = int(case.full.sum()) - len(cells)
    rows, u_end = run(case, advance, place(case, u_disc, cells), s, cells, True)
    res = dict(
        scale=s,
        theta=s * unit,
        cells=cells,
        chosen=why,
        stationary=_defect(entry, "batch", s),
        **verdict(rows, cells, others, True),
        max_abs_V_from_disc_mV=1e3
        * float(np.max(np.abs(case.voltages(u_end, s) - case.voltages(u_disc, s)))),
        trajectory=rows,
    )
    _log(f"  batch: {res['outcome']} latency {res['latency_bracket_s']}")
    return res


def transient_table(out):
    lines = [
        "| disc | s | theta | slot | stationary defect | outcome | latency s | last record s |",
        "|---|---|---|---|---|---|---|---|",
    ]
    rows = list(out["runs"])
    if out.get("batch") and "outcome" in out["batch"]:
        rows.append(
            dict(out["batch"], disc_cells=37, slot=f"batch of {len(out['batch']['cells'])}")
        )
    for r in rows:
        if "outcome" not in r:
            lines.append(
                f"| {r['disc_cells']} | {r['scale']:.4g} | - | - | - | {r['error']} | - | - |"
            )
            continue
        lat = r["latency_bracket_s"]
        lat = "-" if lat is None else f"{lat[0]:g}-{lat[1]:g}"
        lines.append(
            f"| {r['disc_cells']} | {r['scale']:.4g} | {r['theta']:.4g} | {r['slot']} | "
            f"{r['stationary'] or '-'} | {r['outcome']} | {lat} | {r['last_time_s']:g} |"
        )
    return "\n".join(lines)


FOLLOWUP_DEFECTS = ((6, 3, "side"), (8, 5, "side"))
FOLLOWUP_RUNS = (  # (sheet radius, disc radius, slot, scales; "edge" = the window's edge point)
    (6, 3, "side", (0.2, 0.3, 0.5, 0.7, "edge")),
    (6, 3, "batch", (0.2, 0.7)),
    (8, 4, "boundary", (0.5, 0.7)),
    (8, 5, "boundary", (0.5, 0.7)),
    (8, 5, "side", (0.3, 0.7, 1.0)),
)


def followup(output, stationary_path):
    """Stage C: the mid-side boundary cell, the batch at the weakest single conversion
    (s 0.2, where the centre newcomer converts slowest; the corner never converts) and at
    s 0.7, and the corner at s 0.5 and 0.7 of the 61- and 91-cell discs."""
    hp.BISECTIONS = BISECTIONS
    saved = json.loads(Path(stationary_path).read_text())
    entries = {e["disc_cells"]: e for e in saved["discs"]}
    unit = hp.units()["theta_per_unit_scale"]
    out = dict(
        kind="cells.heredity_design_prescreen@8_followup",
        scope="Design input only (development analysis, not judged); no ledgers carried.",
        stationary=str(stationary_path),
        dt_s=DT,
        record_times_s=[*TIMES, HORIZON],
        defects={},
        runs=[],
        failures=[],
    )
    progress = open(output / "runs.jsonl", "x")
    for sheet, radius, name in FOLLOWUP_DEFECTS:
        base = Pattern(sheet, radius)
        entry = entries[int(base.full.sum())]
        cells = [slots(base, radius)[name]]
        _log(f"defect {name} {cells} in disc {entry['disc_cells']} (sheet {sheet})")
        try:
            case = Pattern(sheet, radius, cells)
            result = hp.sweep(case, unit, np.asarray(entry["scales"]), classify_from=CLASSIFY_FROM)
            result["outcomes"] = _outcomes(result, entry["scales"], unit)
            out["defects"].setdefault(str(entry["disc_cells"]), {})[name] = result
            entry["defects"][name] = result
            _log(f"  outcomes {result['outcomes']}")
        except Exception as error:  # Kept as evidence.
            out["failures"].append(
                dict(case=[sheet, radius, name], error=repr(error), tb=traceback.format_exc())
            )
    cases = {}
    for sheet, radius, name, scales in FOLLOWUP_RUNS:
        try:
            if (sheet, radius) not in cases:
                case = Pattern(sheet, radius)
                advance = jax.jit(lambda x, s, k, c=case: c.pb.step_residual(x, s, k))
                cases[(sheet, radius)] = (case, advance, {})
            case, advance, states = cases[(sheet, radius)]
            entry = entries[int(case.full.sum())]
            if name == "batch":
                cells = entry["defects"]["batch"]["case"]["holes"]
            else:
                cells = [slots(case, radius)[name]]
            inside = name != "outside"
            for s in scales:
                s = entry["edge_scale"] if s == "edge" else float(s)
                if s not in states:
                    states[s] = disc_state(case, s, unit)
                u_disc = states[s]
                if u_disc is None:
                    res = dict(disc_cells=entry["disc_cells"], scale=s, slot=name, error="no disc")
                else:
                    started = time.perf_counter()
                    others = int(case.full.sum()) - (len(cells) if inside else 0)
                    rows, u_end = run(case, advance, place(case, u_disc, cells), s, cells, inside)
                    gap = np.max(np.abs(case.voltages(u_end, s) - case.voltages(u_disc, s)))
                    res = dict(
                        disc_cells=entry["disc_cells"],
                        scale=s,
                        theta=s * unit,
                        slot=name if name != "batch" else f"batch of {len(cells)}",
                        cells=cells,
                        stationary=_defect(entry, name, s),
                        **verdict(rows, cells, others, inside),
                        max_abs_V_from_disc_mV=1e3 * float(gap),
                        wall_seconds=time.perf_counter() - started,
                        trajectory=rows,
                    )
                    _log(
                        f"  disc {entry['disc_cells']} s {s:.4g} {res['slot']}: {res['outcome']} "
                        f"latency {res['latency_bracket_s']} (defect {res['stationary']})"
                    )
                out["runs"].append(res)
                progress.write(json.dumps(targets._json(res)) + "\n")
                progress.flush()
        except Exception as error:  # Kept as evidence.
            out["failures"].append(
                dict(case=[sheet, radius, name], error=repr(error), tb=traceback.format_exc())
            )
    progress.close()
    with open(output / "followup.json", "x") as stream:
        json.dump(targets._json(out), stream, indent=1)
    with open(output / "followup_table.md", "x") as stream:
        stream.write(transient_table(targets._json(dict(out, batch=None))) + "\n")
    return out


SHORT = {"converts to D": "D", "stays H": "H", "disc lost (all H)": "lost"}


def _stable_up_to(defect, unit):
    """s up to which the defect state is stable (its first loss, else its branch end)."""
    if defect is None or defect.get("start"):
        return None
    sb, eb = defect.get("stability_boundary"), defect.get("existence_boundary")
    theta = sb["theta"] if sb and sb.get("theta") is not None else (eb or {}).get("theta")
    return None if theta is None else theta / unit


def summarize(directory):
    """Retention window against conversion, per disc: final.json and final_table.md."""
    directory = Path(directory)

    def load(name):
        path = directory / name
        return json.loads(path.read_text()) if path.exists() else None

    st, tr = load("stationary/stationary.json"), load("transient/transient.json")
    fu = load("followup/followup.json") or dict(defects={}, runs=[])
    unit = st["units"]["theta_per_unit_scale"]
    singles = [r for r in tr["runs"] + fu["runs"] if not r.get("slot", "").startswith("batch")]
    batches = [tr["batch"]] if tr.get("batch") else []
    batches += [r for r in fu["runs"] if r.get("slot", "").startswith("batch")]
    rows = []
    for e in st["discs"]:
        defects = dict(e["defects"], **fu["defects"].get(str(e["disc_cells"]), {}))
        keep_to = e["retention"]["s_stability_loss"]
        hold = {k: _stable_up_to(defects.get(k), unit) for k in ("centre", "boundary", "side")}
        pair = [hold[k] for k in ("centre", "boundary")]
        start = None if None in pair else max(pair)
        by_s = {}
        for r in singles:
            if r["disc_cells"] == e["disc_cells"] and "outcome" in r:
                by_s.setdefault(r["scale"], {})[r["slot"]] = r
        rows.append(
            dict(
                disc_cells=e["disc_cells"],
                sheet_cells=e["sheet_cells"],
                retention_s_below=keep_to,
                defect_stable_up_to_s=hold,
                stationary_conversion_window_s=None
                if start is None or start >= keep_to
                else [start, keep_to],
                transient={
                    f"{s:.4g}": {
                        k: dict(outcome=r["outcome"], latency_bracket_s=r["latency_bracket_s"])
                        for k, r in slots.items()
                    }
                    for s, slots in sorted(by_s.items())
                },
            )
        )
    out = dict(
        kind="cells.heredity_design_prescreen@8_summary",
        units=st["units"],
        discs=rows,
        batches=[{k: v for k, v in b.items() if k != "trajectory"} for b in batches],
        seed3_cells=st.get("seed3_cells"),
        cv10={
            k: (st.get("cv10") or {}).get(k)
            for k in ("case", "start", "stability_boundary", "existence_boundary")
        },
        sources=dict(
            stationary="stationary/stationary.json",
            transient="transient/transient.json",
            followup="followup/followup.json",
        ),
    )
    with open(directory / "final.json", "x") as stream:
        json.dump(targets._json(out), stream, indent=1)

    def f(v):
        return "-" if v is None else f"{v:.3g}"

    def short(x):
        if x is None:
            return "-"
        text = SHORT.get(x["outcome"], x["outcome"])
        if text == "D" and x["latency_bracket_s"]:
            text += f" ({x['latency_bracket_s'][0]:g}-{x['latency_bracket_s'][1]:g} s)"
        return text

    lines = [
        "| disc | retention: s below | defect stable to s: centre / corner / side | "
        "stationary window s (centre and corner) |",
        "|---|---|---|---|",
    ]
    for r in rows:
        w = r["stationary_conversion_window_s"]
        w = "none" if w is None else f"{w[0]:.3g}-{w[1]:.3g}"
        h = r["defect_stable_up_to_s"]
        lines.append(
            f"| {r['disc_cells']} | {f(r['retention_s_below'])} | "
            f"{f(h['centre'])} / {f(h['boundary'])} / {f(h['side'])} | {w} |"
        )
    names = ("centre", "boundary", "side", "outside")
    lines += [
        "",
        "| disc | s | centre | corner | side | outside |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        for s, slots in r["transient"].items():
            cells = " | ".join(short(slots.get(k)) for k in names)
            lines.append(f"| {r['disc_cells']} | {s} | {cells} |")
    lines += ["", "| batch (37-cell disc) | s | stationary defect | outcome | latency s |"]
    lines += ["|---|---|---|---|---|"]
    for b in batches:
        if "outcome" in b:
            lat = b["latency_bracket_s"]
            lat = "-" if lat is None else f"{lat[0]:g}-{lat[1]:g}"
            lines.append(
                f"| {len(b['cells'])} cells | {b['scale']:.4g} | {b['stationary']} | "
                f"{b['outcome']} | {lat} |"
            )
    with open(directory / "final_table.md", "x") as stream:
        stream.write("\n".join(lines) + "\n")
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--stationary", action="store_true", help="defect states and closers")
    parser.add_argument("--transient", type=Path, help="forward runs from a stationary.json")
    parser.add_argument("--followup", type=Path, help="stage C from a stationary.json")
    parser.add_argument("--summarize", action="store_true", help="final.json from all stages")
    args = parser.parse_args(argv)
    args.output.mkdir(parents=True, exist_ok=True)  # results are never overwritten
    if args.stationary:
        stationary(args.output)
        _log("stationary done")
    elif args.transient:
        transient(args.output, args.transient)
        _log("transient done")
    elif args.followup:
        followup(args.output, args.followup)
        _log("followup done")
    elif args.summarize:
        summarize(args.output)
    else:
        parser.error("give --stationary, --transient, --followup or --summarize")
    return 0


if __name__ == "__main__":
    sys.exit(main())
