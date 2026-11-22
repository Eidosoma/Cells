"""Per-cell RNA readouts of FR-25's expression unit (FR-25's backlog; D268), with its two
controls. Development, not judged.

**The readout.** For each cell and gene, by the cell's ID (engine_run.readouts, D264), at each
sampling time:
- the total RNA;
- the transcripts started (int_J_I), completed (int_Q) and degraded (int_D);
- for a chosen window, the transcripts completed in it that are still present when sampled, as a
  pulse label measures them (cohort.survivors: one well-mixed pool, age-independent loss).

Raw per-cell values are kept, in copies, so an assay applies its own detection rule. The record
names its revision, units and sampling times.

**The worlds.** `expression_world` builds cells that each hold one gene of A1's transcript
(L = 1200 nt) and its own polymerases and mRNA degradation:
- **Steady production.** The gene's chain is a single stage, fed by abundant polymerases (10^6
  copies, so their depletion is below 1e-7) with saturation negligible. So it completes
  transcripts at its initiation rate P, after a first-order start-up of mean tau0 = L/v = 16 s.
- **Loss.** The mRNA is degraded at k = ln 2 / 3600 s^-1, a one-hour half-life.
- **The start-up.** It is compensated: R starts at R0 + P/(kappa - k), with kappa = 1/tau0. So
  after a few tau0 the total stays at R0 while production is P, which makes the controls' ideal
  numbers the engine's.

The step is 8 s, half a stage time, and the samples are every 120 s.

**The controls** (FR-25's backlog, the user's relay of 20 November 2026):
1. **Turnover:** 100 copies, a one-hour half-life, production 100 ln 2 per hour.
   - Every transcript completed in the marked hour [t_w, t_w + 3600 s] is marked, then production
     continues unmarked. t_w = 360 s, 22.5 start-up times.
   - Expected: the total stays at 100; 69.31 copies are completed in the marked hour; 50 of them
     remain at its end, and 25 an hour later.
2. **Responding cells:** two groups of four cells, making [0, 0, 20, 20] and [10, 10, 10, 10] new
   copies per cell over a window.
   - "New" means completed in the window [360 s, 960 s].
   - Expected: both groups average 10. At a threshold of one new copy, 50% and 100% of cells are
     positive, and the positive cells average 20 and 10.

Run: PYTHONPATH=src:. JAX_ENABLE_X64=1 python -m validation.gene_regulation.rna_readouts --out DIR
"""

import argparse
import copy
import json
import math
from pathlib import Path

from cells.operators.templated_polymerisation import COPY_FMOL
from validation.gene_regulation import cohort, engine_run, kernel, worlds
from validation.gene_regulation import sheet_check as sheet

DT = 8.0
SPEED = 75.0  # nt/s: tau0 = 1200/75 = 16 s at one stage.
MACHINES = 1e6  # copies per cell.
K_HALF_HOUR = math.log(2) / 3600.0  # 1/s: a one-hour half-life.
T_WARM = 360.0  # s: 22.5 start-up times, on the output grid.
THRESHOLD = 1.0  # copies: a cell is positive with at least one new copy.
EVERY = 120.0  # s: the sampling interval, a whole number of steps.


def tau0():
    return int(sheet.A1["L_R"]) / SPEED


def initiation_rate(production):
    """k_I (mM^-1 s^-1) giving `production` copies per second from one gene copy in 1 pL, with the
    machines abundant: J = k_I c_1 F."""
    c1 = float(sheet.COPY_FMOL) / float(sheet.A1["V"])  # mM per copy
    return production / (c1 * MACHINES)


def start_copies(total, production):
    """R0 that keeps the total at `total` once the start-up has passed (module docstring)."""
    return total + production / (1.0 / tau0() - K_HALF_HOUR)


def expression_world(productions, *, total=100.0, end, every=EVERY):
    """A definition with one cell per entry of `productions` (copies per second), each with its
    own gene, polymerases, mRNA degradation and recharging (module docstring)."""
    raw = kernel.truncated(worlds.world("pol T=1", dt=DT), DT)
    e, x, m = raw["experiment"], raw["execution"], raw["model"]
    e["end_time"] = float(end)
    e["observation_times"] = [k * every for k in range(int(round(end / every)) + 1)]
    x["max_steps"] = int(math.ceil(end / DT)) + 8
    block = kernel.block(raw)
    (chain,) = block["chains"]
    chain.update(stages=1, speed_per_s=SPEED, saturation_mM={"N": 1e-6})
    block["pools"][0]["machines"] = MACHINES
    template_cell, template_patch = m["cells"][0], m["membranes"][0]
    controls = {c["route_id"]: c for c in e["polymerisation_controls"]}
    cells, patches, pools, chains, degradations, transfers, schedules = [], [], [], [], [], [], []
    for i, production in enumerate(productions):
        cell_id, suffix = f"cell_{i}", f"_{i}"
        cell = dict(copy.deepcopy(template_cell), id=cell_id)
        cell["initial_amount_fmol"]["R"] = start_copies(total, production) * COPY_FMOL
        cells.append(cell)
        patches.append(dict(copy.deepcopy(template_patch), id=f"patch_{i}", inside=cell_id))
        pools.append(dict(copy.deepcopy(block["pools"][0]), id=f"pol{suffix}", cell=cell_id))
        chains.append(dict(copy.deepcopy(chain), id=f"tx{suffix}", pool=f"pol{suffix}"))
        degradation = copy.deepcopy(block["degradations"][0])
        degradations.append(dict(degradation, id=f"deg_R{suffix}", cell=cell_id))
        transfers.append(dict(copy.deepcopy(block["transfers"][0]), id=f"recharge{suffix}",
                              cell=cell_id))  # fmt: skip
        for route, value in (
            (f"tx{suffix}", initiation_rate(production)),
            (f"deg_R{suffix}", K_HALF_HOUR),
            (f"recharge{suffix}", controls["recharge"]["schedule"][0]["value"]),
        ):
            schedules.append(dict(route_id=route, schedule=[dict(time=0.0, value=value)]))
    m["cells"], m["membranes"] = cells, patches
    e["membrane_controls"] = [
        dict(membrane_id=p["id"], schedule=[dict(time=0.0, availability=1.0)]) for p in patches
    ]
    x["capacity"] = x["membrane_capacity"] = len(cells)
    block.update(pools=pools, chains=chains, degradations=degradations, transfers=transfers)
    e["polymerisation_controls"] = schedules
    return raw


def per_cell(spec, states, windows=()):
    """{cell: {t_s, total_RNA, started, completed, degraded (copies, per sampling time), windows:
    [{t1, t2, ts, completed, surviving} (copies)]}} by the cell's ID."""
    out = {}
    for cell in (c.id for c in spec.model.cells):
        times, x, _ = engine_run.readouts(spec, states, cell)
        (chain,) = [k[len("int_Q_") :] for k in x if k.startswith("int_Q_")]
        copies = {k: [v / COPY_FMOL for v in x[k]] for k in
                  ("n_R", f"int_J_I_{chain}", f"int_Q_{chain}", "int_D_R")}  # fmt: skip
        row = dict(
            t_s=times,
            total_RNA=copies["n_R"],
            started=copies[f"int_J_I_{chain}"],
            completed=copies[f"int_Q_{chain}"],
            degraded=copies["int_D_R"],
            windows=[],
        )
        for t1, t2, ts in windows:
            made, kept, _ = cohort.survivors(
                times, copies["n_R"], copies[f"int_Q_{chain}"], copies["int_D_R"], t1, t2, ts
            )
            row["windows"].append(dict(t1=t1, t2=t2, ts=ts, completed=made, surviving=kept))
        out[cell] = row
    return out


def turnover_control():
    """Control 1 (module docstring): the engine's per-cell readout and the control's numbers."""
    production = 100.0 * math.log(2) / 3600.0
    t_w = T_WARM
    end = t_w + 7200.0
    spec, _, states, _ = kernel.run(expression_world([production], end=end))
    windows = [(t_w, t_w + 3600.0, t_w + 3600.0), (t_w, t_w + 3600.0, t_w + 7200.0)]
    row = per_cell(spec, states, windows)["cell_0"]
    after = [n for t, n in zip(row["t_s"], row["total_RNA"], strict=True) if t >= t_w]
    return dict(
        expected=dict(total=100.0, marked=100.0 * math.log(2), at_end=50.0, hour_later=25.0),
        found=dict(
            total_min=min(after),
            total_max=max(after),
            marked=row["windows"][0]["completed"],
            at_end=row["windows"][0]["surviving"],
            hour_later=row["windows"][1]["surviving"],
        ),
        cell=row,
    )


def responding_cells_control():
    """Control 2 (module docstring): new copies per cell over the window, per group, and the
    groups' mean, positive fraction and positive mean at THRESHOLD."""
    t1, window = T_WARM, 600.0
    groups = {"A": [0.0, 0.0, 20.0, 20.0], "B": [10.0, 10.0, 10.0, 10.0]}
    out = {}
    for name, made in groups.items():
        spec, _, states, _ = kernel.run(
            expression_world([n / window for n in made], end=t1 + window)
        )
        cells = per_cell(spec, states)
        new = []
        for cell in sorted(cells, key=lambda c: int(c.split("_")[1])):
            row = cells[cell]
            i1, i2 = row["t_s"].index(t1), row["t_s"].index(t1 + window)
            new.append(row["completed"][i2] - row["completed"][i1])
        positive = [n for n in new if n >= THRESHOLD]
        out[name] = dict(
            expected_new=made,
            new_per_cell=new,
            mean=sum(new) / len(new),
            positive_fraction=len(positive) / len(new),
            positive_mean=sum(positive) / len(positive) if positive else None,
            cells=cells,
        )
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    source, patch = engine_run.provenance(out)
    if patch is not None:
        (out / "checkout.patch").write_text(patch)
    record = dict(
        kind="cells.gene_regulation.rna_readouts@1",
        units=dict(
            t_s="s",
            total_RNA="copies",
            started="copies, cumulative from t = 0",
            completed="copies, cumulative from t = 0",
            degraded="copies, cumulative from t = 0",
        ),  # fmt: skip
        turnover=turnover_control(),
        responding_cells=responding_cells_control(),
    )
    record.update(engine_run.late_sources(out, source))
    (out / "rna_readouts.json").write_text(json.dumps(record, indent=1) + "\n")
    print(json.dumps(dict(turnover=record["turnover"]["found"],
                          responding={k: {kk: v[kk] for kk in ("new_per_cell", "mean",
                                                               "positive_fraction",
                                                               "positive_mean")}
                                      for k, v in record["responding_cells"].items()}),
                     indent=1))  # fmt: skip
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
