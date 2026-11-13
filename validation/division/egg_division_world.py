"""S5's egg-scale accounting world (docs/CELL_DIVISION_S5_DESIGN.md §8.1; Q1 and Q11 at egg scale).

A development run, not judged: it shows that every ledger, domain and dissipation check closes
across egg-scale partitions, and that the retirement record is state wherever state goes.

Engine models: resolved_pump_composite@1 over resolved_pump_tissue@3, with:
* membrane_entity_state@1;
* scheduled_membrane_insertion@2 and restricted_cleft_lumen@2;
* isopotential_partition@1 and cytoplasmic_bridge_closure@1;
* electrode_current_injection@1.

The egg is the S0 smoke test's declared egg, as the risk-1 probe builds it
(validation/tissue/egg_scale_smoke): dL74's water volume and cytosol activities, Steinberg's
bath, the old membrane's permeability from Rin 852 kOhm, and 0.62 uF/cm2. Neither J1 input is
read (the J2 bright line).

Added, nominal:
* a furrow patch, 0.01 mm^2 at onset and 1 uF/cm^2, with the old membrane's permeability per
  area, into a cleft (gap 1 um, at bath composition, zero charge anchor) with a narrow access
  face to the bath;
* a bridge of 10 um aperture at sigma_cyt 0.5 S/m, closing linearly over 5 s;
* 30 nA into e1, 1 s on and 1 s off with alternating sign, from 6 s to 13 s, so the daughters
  differ. The carriers are K and Cl, the injection law's default.

Timeline, compressed (§8.1):
* the onset at 1 s;
* the first partition (egg into e1, e2; f = 1/2, the only egg-scale split admitted, decision
  11) at 5 s;
* the daughters' second onsets at 6 s, each onto its own cleft;
* the second partitions at 15 s;
* the end at 30 s, at 0.25 ms.
The furrow inserts 2e-7 m^2/s until the first partition and its halves continue. The second
furrows insert at the same rate until the second partitions, and their halves continue to the
end. Every cleft is a lumen.

Checks, written to OUTPUT_DIR/egg_division.json:
* Q1: the run's host checks on every row, and the diagnostics;
* Q11: the recorded rows, written and replayed. check_values closes every ledger, the record is
  carried after each partition, and the negative control (the record zeroed) fails the local
  ledger.
The run is windowed (cells.core.windows), because a whole trace would need about 4.2 GiB.

Usage: python -m validation.division.egg_division_world OUTPUT_DIR [--scale X]. X < 1 compresses
every time, for a trial of the mechanics; 1 is the world. Run it through scripts/run_detached.sh:
about 120,000 steps.
"""

import argparse
import copy
import json
import math
import sys
import time
from pathlib import Path

import jax
import numpy as np

from cells.core import partition_spec as ps
from cells.core import pump_composite_spec as cs
from validation.tissue import egg_scale_smoke as egg

STATUS = "Development run of S5's egg-scale accounting world (Q1, Q11); not judged"
DT = 2.5e-4
END = 30.0
ONSET, FIRST, SECOND_ONSET, SECOND = 1.0, 5.0, 6.0, 15.0
FURROW_AREA_M2 = 1e-8
FURROW_RATE = 2e-7  # m^2/s
SPECIFIC_CAPACITANCE = 0.01  # F/m^2
GAP_M = 1e-6
ACCESS_AREA_M2, ACCESS_LENGTH_M = 1e-8, 1e-2
APERTURE_M, SIGMA_CYT, CLOSURE_S = 1e-5, 0.5, 5.0
FREE_D = {"Na": 1.33e-9, "K": 1.96e-9, "Cl": 2.03e-9}
INJECTION_A = 3e-8
CARRIERS = {"K": 0.4912, "Cl": 0.5088}


def cleft_node(node_id, volume_pL, valence):
    amounts = {s: c * volume_pL for s, c in egg.BATH_mM.items()}
    return dict(
        id=node_id,
        volume_pL=volume_pL,
        initial_amount_fmol=amounts,
        fixed_charge_equivalent_fmol=-math.fsum(valence[s] * v for s, v in amounts.items()),
        initial_charge_C=0.0,
        reservoir=False,
        boundary_potential_V=0.0,
    )


def add_furrow(raw, *, patch_id, cell, node_id, face_id):
    """A furrow patch of cell into a new cleft node with an access face to the bath."""
    m, e, x = raw["model"], raw["experiment"], raw["execution"]
    valence = {s["id"]: s["valence"] for s in m["species"]}
    old = next(p for p in m["membranes"] if p["id"] == "old_membrane")
    m["extracellular"].append(cleft_node(node_id, 0.5e15 * GAP_M * FURROW_AREA_M2, valence))
    m["membranes"].append(
        dict(
            copy.deepcopy(old),
            id=patch_id,
            inside=cell,
            outside=node_id,
            area_m2=FURROW_AREA_M2,
            capacitance_F=SPECIFIC_CAPACITANCE * FURROW_AREA_M2,
        )
    )
    m["faces"].append(
        dict(
            id=face_id,
            sender=node_id,
            receiver="steinberg",
            area_m2=ACCESS_AREA_M2,
            length_m=ACCESS_LENGTH_M,
            diffusivity_m2_per_s=dict(FREE_D),
            law="logmean_electrodiffusion@1",
        )
    )
    e["membrane_controls"].append(
        dict(membrane_id=patch_id, schedule=[dict(time=0.0, availability=1.0)])
    )
    x.update(
        extracellular_capacity=len(m["extracellular"]),
        membrane_capacity=len(m["membranes"]),
        face_capacity=len(m["faces"]),
    )


def definition(*, scale=1.0, dt=DT, injection=True):
    """The egg-scale division world as a raw composition (module docstring); scale compresses
    every time, each placed on the step grid as k * dt."""

    def at(time):
        """time x scale on the step grid, as k * dt: the schedules' own test of exactness."""
        return round(time * scale / dt) * dt

    end, onset, first, second_onset, second = (
        at(x) for x in (END, ONSET, FIRST, SECOND_ONSET, SECOND)
    )
    base, _ = egg.egg_definition(end_time=end, dt=dt, observe_every=1.0)
    add_furrow(base, patch_id="furrow", cell="egg", node_id="cleft", face_id="access")
    raw = cs.frozen_definition(base)
    m, e = raw["model"], raw["experiment"]
    blocks = [ps.add_division(raw, division_id="first", parent="egg", daughters=("e1", "e2"))]
    cell = next(c for c in m["cells"] if c["id"] == "egg")
    cytosol = {s: a / cell["volume_pL"] for s, a in cell["initial_amount_fmol"].items()}
    valence = {s["id"]: s["valence"] for s in m["species"]}
    diffusivity = ps.cytoplasmic_diffusivities(
        SIGMA_CYT, cytosol, FREE_D, valence, m["temperature_K"]
    )
    bridge = ps.add_bridge(
        raw, junction_id="bridge_1", daughters=("e1", "e2"), aperture_m=APERTURE_M,
        diffusivity=diffusivity,
    )  # fmt: skip
    for d in ("e1", "e2"):
        add_furrow(
            raw, patch_id=f"furrow2_{d}", cell=d, node_id=f"cleft2_{d}", face_id=f"access2_{d}"
        )
    halves = {"e1": ("q1", "q2"), "e2": ("q3", "q4")}
    for d, kids in halves.items():
        blocks.append(
            ps.add_division(
                raw, division_id=f"second_{d}", parent=d, daughters=kids, bridges=("bridge_1",)
            )
        )
    r = FURROW_RATE
    schedules = {"furrow": (onset, [(0.0, 0.0), (onset, r), (first, 0.0)])}
    for d, kids in halves.items():
        schedules[f"furrow_{d}"] = (None, [(0.0, 0.0), (first, 0.5 * r), (second, 0.0)])
        schedules[f"furrow2_{d}"] = (second_onset, [(0.0, 0.0), (second_onset, r), (second, 0.0)])
        for g in kids:
            schedules[f"furrow_{d}_{g}"] = (None, [(0.0, 0.0), (second, 0.25 * r)])
            schedules[f"furrow2_{d}_{g}"] = (None, [(0.0, 0.0), (second, 0.5 * r)])
    m["operators"] = [
        dict(law="membrane_entity_state@1", populations=[]),
        dict(
            law="scheduled_membrane_insertion@2",
            patches=[
                dict(
                    membrane_id=k,
                    specific_capacitance_F_per_m2=SPECIFIC_CAPACITANCE,
                    population_densities_per_m2={},
                )
                for k in schedules
            ],
        ),
        dict(
            law="restricted_cleft_lumen@2",
            lumens=[
                dict(node_id=k, source_id="steinberg", gap_width_m=GAP_M)
                for k in ("cleft", "cleft2_e1", "cleft2_e2")
            ],
        ),
        dict(law="isopotential_partition@1", divisions=blocks),
        dict(
            law="cytoplasmic_bridge_closure@1",
            bridges=[dict(bridge, closure="linear", closure_time_s=at(CLOSURE_S))],
        ),
    ]
    e["bridge_controls"] = [dict(junction_id="bridge_1", start_time=first)]
    e["insertion_controls"] = [
        dict(
            membrane_id=k,
            onset_time=onset,
            schedule=[dict(time=t, rate_m2_per_s=v) for t, v in changes],
        )
        for k, (onset, changes) in schedules.items()
    ]
    e["partition_events"] = [
        dict(division="first", time=first, carriers=["c1", "c2"]),
        dict(division="second_e1", time=second, carriers=["c11", "c12"]),
        dict(division="second_e2", time=second, carriers=["c21", "c22"]),
    ]
    if injection:
        m["operators"].append(
            dict(
                law="electrode_current_injection@1",
                electrodes=[dict(cell_id="e1", carriers=dict(CARRIERS))],
            )
        )
        pulses = [dict(time=0.0, current_A=0.0)]
        for k, start in enumerate(at(x) for x in (6.0, 8.0, 10.0, 12.0)):
            sign = 1.0 if k % 2 == 0 else -1.0
            pulses += [
                dict(time=start, current_A=sign * INJECTION_A),
                dict(time=round((start + at(1.0)) / dt) * dt, current_A=0.0),
            ]
        e["injection_controls"] = [dict(cell_id="e1", schedule=pulses)]
    return raw


def main(argv=None):
    from cells.core.errors import NumericalError
    from cells.core.specs import parse_spec
    from cells.core.windows import WindowPolicy, run_windowed
    from cells.models.operators import partition
    from cells.models.registry import get_model

    parser = argparse.ArgumentParser()
    parser.add_argument("output")
    parser.add_argument("--scale", type=float, default=1.0)
    args = parser.parse_args(argv)
    jax.config.update("jax_enable_x64", True)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    spec = parse_spec(definition(scale=args.scale))
    model = get_model(spec.model)
    rows, accepted, phases = [], [], []

    def keep(window):
        """Each window's recorded rows (its observation times), after the window's checks."""
        rows.append([np.asarray(v) for v in window.history])
        accepted.append(np.asarray(window.times))
        phases.append(np.asarray(window.observations.partition_slot_phase))

    start = time.perf_counter()
    # Q1: windowed execution, whose host checks raise on any failing row of any window. A whole
    # trace would need about 4.2 GiB at 120,000 steps (runner.trace_bytes).
    result = run_windowed(spec, WindowPolicy(4096, "observations"), sink=keep)
    seconds = time.perf_counter() - start
    fields = model.STATE_TYPE._fields
    arrays = {k: np.concatenate([r[i] for r in rows]) for i, k in enumerate(fields)}
    np.savez(output / "trajectory.npz", accepted_times=np.concatenate(accepted), **arrays)
    saved = np.load(output / "trajectory.npz")  # Q11: the written rows, replayed.
    history = model.STATE_TYPE(*(saved[name] for name in fields))
    times = np.asarray(saved["accepted_times"])
    steps = np.rint(times / spec.execution.dt).astype(int)
    replay = model.check_values(history, spec, steps)  # Q11: the written run, replayed.
    after = times > round(FIRST * args.scale, 3) + 1e-9
    record = np.asarray(history.partition_retired_membrane_heat_pJ)
    blank = history._replace(
        **{k: np.zeros_like(getattr(history, k)) for k in partition.RECORD.values()}
    )
    try:
        model.check_values(blank, spec, steps)
        negative = "passed (the control failed to fail)"
    except NumericalError as error:
        negative = str(error)
    report = dict(
        status=STATUS,
        scale=args.scale,
        dt_s=spec.execution.dt,
        seconds=seconds,
        diagnostics={k: float(v) for k, v in result.diagnostics.items()},
        replay_diagnostics={k: float(v) for k, v in replay.items()},
        record_after_first_partition_pJ=float(np.max(record[after])) if after.any() else None,
        record_before_first_partition_pJ=float(np.max(np.abs(record[~after]))),
        negative_control=negative,
        final_phase=np.concatenate(phases)[-1].tolist(),
        windows=result.resources.get("windows"),
        rows_replayed=int(len(times)),
    )
    (output / "egg_division.json").write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps(report, indent=1), flush=True)


if __name__ == "__main__":
    sys.exit(main())
