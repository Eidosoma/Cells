"""Q3 development comparison: trajectories after partition against R-tissue (S5 design §8.3).

The comparison is built from validation/division/REFERENCES_USAGE.md alone (the lead's ruling).
R-tissue's source, docstrings and tests are not read. The J2 bright line binds: this module
reads neither J1 input nor the J1 record. It takes only R-full's Pulses, a dataclass, from
cleft_egg_reference, as the note's example does.

The world is S5's compact 1 -> 2 -> 4 furrow world (tests/partition_fixtures.cleft_quartered),
made passive: no channel populations, as R-tissue's worlds are (§8.1). Its parts:
* the furrow onset at 1 ms and the first division at 2 ms, with a bridge closing linearly
  over 1 ms;
* the second onsets at 3 ms and the second divisions at 5 ms;
* 1 pA into d1 from its birth to its division;
* the end at 10 ms.
It is converted to R-tissue's World:
* species Na, K, M and P, with P impermeant;
* the founder at the engine's initial potential, so its background is the engine's;
* the bath at the engine's held bath's composition;
* the same patches, onsets, schedules, clefts, faces, bridge (D^cyt from the engine's
  declaration) and division maps;
* the injection as one Pulses pulse.

Compared at the records strictly after each division instant (Q3's timing ruling; the instant
itself is Q2's):
* each live cell's Vm;
* each lumen's volume and composition;
* the bridge current, D1 to D2.
Reported per quantity: the largest difference engine - R-tissue, and two terms beside it:
* the engine's step term: the same world at dt and dt/2;
* the reference term: R-tissue at its SMALL atol against 1000 times tighter (the lead's ruling).
No tolerance is registered, so nothing is judged.

Usage: python -m validation.division.q3_tissue_comparison OUTPUT_DIR (through
scripts/run_detached.sh).
"""

import json
import math
import sys
import time
from pathlib import Path

import jax
import numpy as np

from cells.core.runner import run
from cells.core.specs import parse_spec
from cells.models import pump_composite_adapter as adapter
from cells.models.registry import get_model
from cells.processes.electrochemistry import CHARGE_PER_FMOL
from tests import partition_fixtures as fx
from validation.division import cleft_egg_reference as rfull  # Pulses only (the note's example).
from validation.division import cleft_tissue_reference as rt

STATUS = "Development comparison for Q3 (S5a); not judged; no tolerance registered"
END = 0.010
DT = 2.5e-4
RECORDS = (0.0025, 0.003, 0.004, 0.006, 0.008, 0.010)  # Strictly after the divisions at 2, 5 ms;
# 2.5 ms lies inside the bridge's open interval (2 to 3 ms), so its current is compared there.
SMALL = dict(
    cell_charge=1e-15, cleft_charge=1e-17, cell_amount=1e-12, cleft_amount=1e-14, heat=1e-15
)
TIGHT = {k: v * 1e-3 for k, v in SMALL.items()}
INJECTION_A = 1e-12


def passive(raw):
    """raw without channel populations (in place)."""
    raw["model"]["channels"] = []
    raw["experiment"]["channel_controls"] = []
    raw["execution"]["channel_capacity"] = 0
    for block in raw["model"]["operators"]:
        if block["law"] == "membrane_entity_state@1":
            block["populations"] = []
        for division in block.get("divisions", []):
            division["populations"] = []
    return raw


def engine_world(dt):
    raw = passive(fx.cleft_quartered(injection=INJECTION_A, end=END))
    raw["execution"].update(dt=dt, max_steps=int(math.ceil(END / dt)) + 8)
    raw["experiment"]["observation_times"] = [0.0, *RECORDS]
    return raw


def tissue_world(raw, spec, model):
    """R-tissue's World for the engine definition raw (module docstring)."""
    m, e = raw["model"], raw["experiment"]
    species = tuple(s["id"] for s in m["species"])
    z = tuple(s["valence"] for s in m["species"])
    state, p = model.initial_values(spec)
    q = model.view(p, state, xp=np)
    phi = adapter.node_potentials(state, q, xp=np)
    cells = [c["id"] for c in m["cells"]]
    bath = next(c for c in m["extracellular"] if c.get("reservoir"))
    node = {bath["id"]: rt.BATH}
    founder = next(c for c in m["cells"] if c["id"] == "cell_0")
    initial_v = float(phi[cells.index("cell_0")] - phi[len(cells) + 0])
    cell_specs = {
        c["id"]: rt.CellSpec(
            volume_pL=founder["volume_pL"],
            mM=tuple(founder["initial_amount_fmol"][s] / founder["volume_pL"] for s in species),
            initial_V=initial_v,
        )
        if c["id"] == "cell_0"
        else rt.CellSpec()
        for c in m["cells"]
    }
    insertion = next(o for o in m["operators"] if o["law"] == fx.INSERTION2)
    capacitance = {
        k["membrane_id"]: k["specific_capacitance_F_per_m2"] for k in insertion["patches"]
    }
    controls = {c["membrane_id"]: c for c in e["insertion_controls"]}
    divisions = next(o for o in m["operators"] if o["law"] == fx.PARTITION)["divisions"]
    daughters_of = {x for d in divisions for k in d["patches"] for x in k["daughters"]}
    patches = {}
    for k in m["membranes"]:
        perm = tuple(k["permeability_m_per_s"][s] for s in species)
        kwargs = dict(
            cell=k["inside"], node=node.get(k["outside"], k["outside"]), permeability_m_s=perm
        )
        control = controls.get(k["id"])
        if control is not None:
            kwargs["specific_capacitance_F_m2"] = capacitance[k["id"]]
            kwargs["schedule"] = tuple(
                (c["time"], c["rate_m2_per_s"]) for c in control["schedule"] if c["time"] > 0
            )
            if control["onset_time"] is not None:
                kwargs.update(
                    onset_s=control["onset_time"],
                    area_m2=k["area_m2"],
                    capacitance_F=k["capacitance_F"],
                )
        if k["id"] not in daughters_of and kwargs.get("onset_s") is None:
            kwargs.update(area_m2=k["area_m2"], capacitance_F=k["capacitance_F"])
        patches[k["id"]] = rt.PatchSpec(**kwargs)
    lumens = next(o for o in m["operators"] if o["law"] == fx.LUMEN2)["lumens"]
    clefts = {x["node_id"]: rt.CleftSpec(gap_width_m=x["gap_width_m"]) for x in lumens}
    faces = {
        f["id"]: rt.FaceSpec(
            nodes=(node.get(f["sender"], f["sender"]), node.get(f["receiver"], f["receiver"])),
            a_over_l_m=f["area_m2"] / f["length_m"],
            diffusivity_m2_s=tuple(f["diffusivity_m2_per_s"][s] for s in species),
        )
        for f in m["faces"]
    }
    bridge = next(o for o in m["operators"] if o["law"] == fx.BRIDGE)["bridges"][0]
    division_specs = {}
    for d in divisions:
        event = next(x for x in e["partition_events"] if x["division"] == d["id"])
        spec_bridge = {}
        if set(d["daughters"]) == {"d1", "d2"}:
            spec_bridge = dict(
                bridge=bridge["junction_id"],
                bridge_spec=rt.BridgeSpec(
                    a0_m=bridge["initial_aperture_m"],
                    diffusivity_m2_s=tuple(
                        bridge["cytoplasmic_diffusivity_m2_per_s"][s] for s in species
                    ),
                    law=bridge["closure"],
                    tau_s=bridge["closure_time_s"],
                ),
            )
        division_specs[d["id"]] = rt.DivisionSpec(
            parent=d["parent"],
            daughters=tuple(d["daughters"]),
            time_s=event["time"],
            f=d["volume_fraction"],
            patches={k["parent"]: (*k["daughters"], k["fraction"]) for k in d["patches"]},
            carriers=dict(d["mismatch_carriers"]),
            **spec_bridge,
        )
    injection = next(o for o in m["operators"] if o["law"] == fx.INJECTION)
    changes = e["injection_controls"][0]["schedule"]
    start, stop = changes[1]["time"], changes[2]["time"]
    pulses = rfull.Pulses(
        amplitude_A=changes[1]["current_A"],
        duration_s=stop - start,
        period_s=10 * END,
        first_onset_s=start,
        sample_s=0.5 * (stop - start),
    )
    carriers = dict(injection["electrodes"][0]["carriers"])
    return rt.World(
        temperature_K=m["temperature_K"],
        bath_mM=tuple(bath["initial_amount_fmol"][s] / bath["volume_pL"] for s in species),
        cells=cell_specs,
        patches=patches,
        clefts=clefts,
        faces=faces,
        injections=(rt.InjectionSpec("d1", pulses, carriers),),
        divisions=division_specs,
        species=species,
        z=z,
    )


def engine_records(spec, result):
    """{t: {"V": {cell: Vm}, "lumens": {cleft: (volume, mM)}, "bridge_A": current}}."""
    model = get_model(spec.model)
    _, p = model.initial_values(spec)
    h, times = result.history, np.asarray(result.times)
    cells = [c.id for c in spec.model.cells]
    nodes = [c.id for c in spec.model.extracellular]
    obs = result.observations
    e = [j.id for j in spec.model.junctions].index("bridge_1")
    out = {}
    for t in RECORDS:
        i = int(np.flatnonzero(np.isclose(times, t, rtol=0, atol=1e-12))[0])
        k = list(np.asarray(obs.times)).index(t)
        state = model.STATE_TYPE(*(np.asarray(v[i]) for v in h))
        q = model.view(p, state, xp=np)
        phi = adapter.node_potentials(state, q, xp=np)
        n = len(cells)
        bath = n + [j for j, c in enumerate(spec.model.extracellular) if c.reservoir][0]
        voltages = {
            cells[c]: float(phi[c] - phi[bath]) for c in np.flatnonzero(np.asarray(q.active))
        }
        lumens = {
            nodes[c]: (
                float(obs.lumen_volume_pL[k, c]),
                np.asarray(obs.lumen_concentration_mM)[k][:, c],
            )
            for c in range(len(nodes))
            if nodes[c].startswith("cleft") and q.outside_active[c]
        }
        current = None
        if q.junction_active[e]:
            control = model.CONTROL_TYPE(
                *(np.asarray(v[0]) for v in fx.cs.control_values(spec, [t]))
            )
            flux = np.asarray(
                model.readouts(state, control, p, xp=np).field.rates.junction_flux_fmol_s
            )
            current = float(CHARGE_PER_FMOL * np.sum(np.ravel(p.valence) * flux[:, e]))
        out[t] = dict(V=voltages, lumens=lumens, bridge_A=current)
    return out


def tissue_records(run_):
    out = {}
    for t in RECORDS:
        r = run_.at[t]
        bridge = r["junctions"].get("bridge_1")
        out[t] = dict(
            V=dict(r["V"]),
            lumens={c: (x["volume_pL"], np.asarray(x["mM"])) for c, x in r["lumens"].items()},
            bridge_A=None if bridge is None else bridge["current_A"],
        )
    return out


def differences(a, b):
    """{quantity: largest |a - b|} over the records (absolute, in each quantity's units)."""
    out = dict(V=0.0, lumen_volume_pL=0.0, lumen_mM=0.0, bridge_A=0.0)
    for t in RECORDS:
        for c, v in a[t]["V"].items():
            out["V"] = max(out["V"], abs(v - b[t]["V"][c]))
        for c, (vol, mm) in a[t]["lumens"].items():
            out["lumen_volume_pL"] = max(out["lumen_volume_pL"], abs(vol - b[t]["lumens"][c][0]))
            out["lumen_mM"] = max(out["lumen_mM"], float(np.max(np.abs(mm - b[t]["lumens"][c][1]))))
        if a[t]["bridge_A"] is not None and b[t]["bridge_A"] is not None:
            out["bridge_A"] = max(out["bridge_A"], abs(a[t]["bridge_A"] - b[t]["bridge_A"]))
    return out


def main(output):
    jax.config.update("jax_enable_x64", True)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    engine = {}
    for dt in (DT, 0.5 * DT):
        raw = engine_world(dt)
        spec = parse_spec(raw)
        start = time.perf_counter()
        engine[dt] = (raw, spec, engine_records(spec, run(spec)))
        print(f"engine dt={dt}: {time.perf_counter() - start:.1f} s", flush=True)
    raw, spec, mine = engine[DT]
    world = tissue_world(raw, spec, get_model(spec.model))
    rt.check_world(world)
    start = time.perf_counter()
    reference = tissue_records(rt.simulate_divisions(world, END, record=RECORDS, atol=SMALL))
    tight = tissue_records(rt.simulate_divisions(world, END, record=RECORDS, atol=TIGHT))
    print(f"R-tissue (two runs): {time.perf_counter() - start:.1f} s", flush=True)
    report = dict(
        status=STATUS,
        records_s=list(RECORDS),
        dt_s=DT,
        engine_minus_reference=differences(mine, reference),
        engine_step_term=differences(mine, engine[0.5 * DT][2]),
        reference_term=differences(reference, tight),
        sample=dict(
            t=RECORDS[-1],
            engine_V=mine[RECORDS[-1]]["V"],
            reference_V=reference[RECORDS[-1]]["V"],
        ),
    )
    (output / "q3_tissue.json").write_text(json.dumps(report, indent=1, default=float) + "\n")
    print(json.dumps(report, indent=1, default=float), flush=True)


if __name__ == "__main__":
    main(sys.argv[1])
