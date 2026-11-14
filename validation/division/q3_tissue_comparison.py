"""Q3 development comparison: trajectories after partition against R-tissue (S5 design §8.3).

The comparison is built from validation/division/REFERENCES_USAGE.md alone (the lead's ruling).
R-tissue's source, docstrings and tests are not read. The J2 bright line binds: this module
reads neither J1 input nor the J1 record. It takes only R-full's Pulses, a dataclass, from
cleft_egg_reference, as the note's example does.

Two worlds, both made passive (no channel populations, as R-tissue's worlds are, §8.1):
* quartered furrow: S5's compact 1 -> 2 -> 4 furrow world (tests/partition_fixtures.
  cleft_quartered):
  - the furrow onset at 1 ms and the first division at 2 ms, with a bridge closing linearly
    over 1 ms;
  - the second onsets at 3 ms and the second divisions at 5 ms;
  - 1 pA into d1 from its birth to its division;
  - the end at 10 ms.
* neighbour contact: the compact asymmetric world with a neighbour (tests/partition_fixtures.
  divided):
  - cell_0 (heredity state H) and cell_1 (state D), each on its own held bath, joined by a
    contact whose gate is fixed open, as the bridge's is (R-tissue's contacts hold fixed
    gates; the gate law's kinetics are @3's own qualification's, the lead, 14 November);
  - cell_0 divides at 2 ms into d1 and d2 at f 0.75, its patch split at 0.6, with three
    mismatch carriers (Na 0.3, K 0.5, M 0.2); the contact maps to d1 and d2 at a_e 1/2;
  - 1 pA into d1 from its birth;
  - the end at 10 ms.
Each is converted to R-tissue's World:
* species Na, K, M and P, with P impermeant;
* each founder at the engine's initial potential, so its background is the engine's;
* the held baths as R-tissue's one bath: they must share one composition at 0 V;
* the same patches, onsets, schedules, clefts, faces, contacts, bridge (D^cyt from the
  engine's declaration) and division maps;
* the injection as one Pulses pulse.

Compared at each world's records, strictly after each division instant and off the onset
instants (Q3's timing ruling; the instant itself is Q2's; at an event instant the engine
records the state before the event and R-tissue the state after it):
* each live cell's Vm;
* each lumen's volume and composition;
* the bridge current, D1 to D2, and each contact's current in R-tissue's direction (its
  record's cells[0] to cells[1]).
Reported per world and quantity, over the records and at each record: the largest difference
engine - R-tissue, and two terms beside it:
* the engine's step term: the same world at dt and dt/2;
* the reference term: R-tissue at its SMALL atol against 1000 times tighter (the lead's ruling).
Each quantity's scale, its largest |value| over the records, is reported for the rounding
floor (the PROPOSED protocol, validation/division/s5_protocol.json), and at each record how
many of its entries are live. No tolerance is registered, so nothing is judged.

Usage: python -m validation.division.q3_tissue_comparison OUTPUT_DIR [WORLD ...] (through
scripts/run_detached.sh; every world by default).
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
SMALL = dict(
    cell_charge=1e-15, cleft_charge=1e-17, cell_amount=1e-12, cleft_amount=1e-14, heat=1e-15
)
TIGHT = {k: v * 1e-3 for k, v in SMALL.items()}
INJECTION_A = 1e-12
CARRIERS = {"Na": 0.3, "K": 0.5, "M": 0.2}
# A gate fixed open, as core/partition_spec.add_bridge declares the bridge's.
FIXED_OPEN = dict(
    law="junction_voltage_relaxation@1",
    threshold_voltage_V=0.0,
    minimum_open_fraction=1.0,
    initial_gate=1.0,
)


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


def quartered():
    return passive(fx.cleft_quartered(injection=INJECTION_A, end=END))


def neighbour():
    raw = fx.divided(
        neighbour=True,
        f=0.75,
        area_fraction=0.6,
        carriers=CARRIERS,
        injection=INJECTION_A,
        end=END,
    )
    for junction in raw["model"]["junctions"]:  # The contact and its daughter slots.
        junction["gate"] = dict(FIXED_OPEN)
    return passive(raw)


# {world: (builder, records)}. Records: strictly after the divisions (2 ms; and 5 ms in the
# quartered world) and off the onset instants (1 and 3 ms there). 2.5 ms lies inside the
# quartered world's bridge's open interval (2 to 3 ms).
WORLDS = {
    "quartered furrow": (quartered, (0.0025, 0.0035, 0.004, 0.006, 0.008, 0.010)),
    "neighbour contact": (neighbour, (0.0025, 0.003, 0.004, 0.006, 0.008, 0.010)),
}


def engine_world(name, dt):
    build, records = WORLDS[name]
    raw = build()
    raw["execution"].update(dt=dt, max_steps=int(math.ceil(END / dt)) + 8)
    raw["experiment"]["observation_times"] = [0.0, *records]
    return raw


def operator(raw, law):
    return next((o for o in raw["model"]["operators"] if o["law"] == law), None)


def bridge_ids(raw):
    block = operator(raw, fx.BRIDGE)
    return {b["junction_id"] for b in block["bridges"]} if block else set()


def tissue_world(raw, spec, model):
    """R-tissue's World for the engine definition raw (module docstring)."""
    m, e = raw["model"], raw["experiment"]
    species = tuple(s["id"] for s in m["species"])
    z = tuple(s["valence"] for s in m["species"])
    state, p = model.initial_values(spec)
    q = model.view(p, state, xp=np)
    phi = adapter.node_potentials(state, q, xp=np)
    cells = [c["id"] for c in m["cells"]]
    nodes = [c["id"] for c in m["extracellular"]]
    baths = [c for c in m["extracellular"] if c.get("reservoir")]
    bath = baths[0]
    composition = tuple(bath["initial_amount_fmol"][s] / bath["volume_pL"] for s in species)
    for b in baths:  # R-tissue holds one bath at 0 V.
        mm = tuple(b["initial_amount_fmol"][s] / b["volume_pL"] for s in species)
        assert b["boundary_potential_V"] == 0.0 and mm == composition, (b["id"], mm)
    node = {b["id"]: rt.BATH for b in baths}
    divisions = operator(raw, fx.PARTITION)["divisions"]
    daughters = {x for d in divisions for x in d["daughters"]}
    bath_patch = {
        k["inside"]: k["outside"] for k in m["membranes"] if k["outside"] in node
    }  # Each founder's bath-facing patch's node.

    def initial_v(cell):
        return float(phi[cells.index(cell)] - phi[len(cells) + nodes.index(bath_patch[cell])])

    cell_specs = {
        c["id"]: rt.CellSpec()
        if c["id"] in daughters
        else rt.CellSpec(
            volume_pL=c["volume_pL"],
            mM=tuple(c["initial_amount_fmol"][s] / c["volume_pL"] for s in species),
            initial_V=initial_v(c["id"]),
        )
        for c in m["cells"]
    }
    insertion = operator(raw, fx.INSERTION2)
    capacitance = {
        k["membrane_id"]: k["specific_capacitance_F_per_m2"]
        for k in (insertion["patches"] if insertion else ())
    }
    controls = {c["membrane_id"]: c for c in e.get("insertion_controls", [])}
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
    lumen = operator(raw, fx.LUMEN2)
    clefts = {
        x["node_id"]: rt.CleftSpec(gap_width_m=x["gap_width_m"])
        for x in (lumen["lumens"] if lumen else ())
    }
    faces = {
        f["id"]: rt.FaceSpec(
            nodes=(node.get(f["sender"], f["sender"]), node.get(f["receiver"], f["receiver"])),
            a_over_l_m=f["area_m2"] / f["length_m"],
            diffusivity_m2_s=tuple(f["diffusivity_m2_per_s"][s] for s in species),
        )
        for f in m["faces"]
    }
    contacts = {}
    for j in m["junctions"]:
        if j["id"] in bridge_ids(raw):
            continue
        gate = j["gate"]  # R-tissue's contacts hold fixed gates: fixed open here.
        assert gate["minimum_open_fraction"] == 1.0 and gate["initial_gate"] == 1.0, j["id"]
        perm = tuple(j["permeability_m_per_s"][s] for s in species)
        ends = (j["sender"], j["receiver"])
        if daughters & set(ends):  # A daughter contact: its division writes its area.
            contacts[j["id"]] = rt.ContactSpec(cells=ends, permeability_m_s=perm)
        else:
            contacts[j["id"]] = rt.ContactSpec(
                cells=ends, permeability_m_s=perm, area_m2=j["area_m2"], gate=1.0
            )
    bridges = operator(raw, fx.BRIDGE)["bridges"] if operator(raw, fx.BRIDGE) else []
    junction_ends = {j["id"]: {j["sender"], j["receiver"]} for j in m["junctions"]}
    division_specs = {}
    for d in divisions:
        event = next(x for x in e["partition_events"] if x["division"] == d["id"])
        extra = {}
        for b in bridges:
            if junction_ends[b["junction_id"]] == set(d["daughters"]):
                extra = dict(
                    bridge=b["junction_id"],
                    bridge_spec=rt.BridgeSpec(
                        a0_m=b["initial_aperture_m"],
                        diffusivity_m2_s=tuple(
                            b["cytoplasmic_diffusivity_m2_per_s"][s] for s in species
                        ),
                        law=b["closure"],
                        tau_s=b["closure_time_s"],
                    ),
                )
        if d["contacts"]:
            extra["contacts"] = {
                c["parent"]: (*c["daughters"], c["fraction"]) for c in d["contacts"]
            }
        division_specs[d["id"]] = rt.DivisionSpec(
            parent=d["parent"],
            daughters=tuple(d["daughters"]),
            time_s=event["time"],
            f=d["volume_fraction"],
            patches={k["parent"]: (*k["daughters"], k["fraction"]) for k in d["patches"]},
            carriers=dict(d["mismatch_carriers"]),
            **extra,
        )
    injection = operator(raw, fx.INJECTION)
    changes = e["injection_controls"][0]["schedule"]
    start = changes[1]["time"]
    stop = changes[2]["time"] if len(changes) > 2 else END
    pulses = rfull.Pulses(
        amplitude_A=changes[1]["current_A"],
        duration_s=stop - start,
        period_s=10 * END,
        first_onset_s=start,
        sample_s=0.5 * (stop - start),
    )
    carriers = dict(injection["electrodes"][0]["carriers"])
    electrode = injection["electrodes"][0]["cell_id"]
    extra = dict(contacts=contacts) if contacts else {}
    return rt.World(
        temperature_K=m["temperature_K"],
        bath_mM=composition,
        cells=cell_specs,
        patches=patches,
        clefts=clefts,
        faces=faces,
        injections=(rt.InjectionSpec(electrode, pulses, carriers),),
        divisions=division_specs,
        species=species,
        z=z,
        **extra,
    )


def engine_records(spec, result, records):
    """{t: {"V": {cell: Vm}, "lumens": {cleft: (volume, mM)}, "junctions": {id: (ends, A)}}}:
    each live junction's current from its sender to its receiver."""
    model = get_model(spec.model)
    _, p = model.initial_values(spec)
    h, times = result.history, np.asarray(result.times)
    cells = [c.id for c in spec.model.cells]
    nodes = [c.id for c in spec.model.extracellular]
    junctions = spec.model.junctions
    obs = result.observations
    lumen = hasattr(obs, "lumen_volume_pL")
    out = {}
    for t in records:
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
            if lumen and nodes[c].startswith("cleft") and q.outside_active[c]
        }
        currents = {}
        live = np.flatnonzero(np.asarray(q.junction_active))
        if live.size:
            control = model.CONTROL_TYPE(
                *(np.asarray(v[0]) for v in fx.cs.control_values(spec, [t]))
            )
            flux = np.asarray(
                model.readouts(state, control, p, xp=np).field.rates.junction_flux_fmol_s
            )
            for e in live:
                current = float(CHARGE_PER_FMOL * np.sum(np.ravel(p.valence) * flux[:, e]))
                currents[junctions[e].id] = ((junctions[e].sender, junctions[e].receiver), current)
        out[t] = dict(V=voltages, lumens=lumens, junctions=currents)
    return out


def tissue_records(run_, records):
    out = {}
    for t in records:
        r = run_.at[t]
        out[t] = dict(
            V=dict(r["V"]),
            lumens={c: (x["volume_pL"], np.asarray(x["mM"])) for c, x in r["lumens"].items()},
            junctions={
                name: (tuple(x["cells"]), x["current_A"]) for name, x in r["junctions"].items()
            },
        )
    return out


def oriented(current, ends, to):
    """current along ends, expressed along to (the same two cells)."""
    assert set(ends) == set(to), (ends, to)
    return current if tuple(ends) == tuple(to) else -current


QUANTITIES = ("V", "lumen_volume_pL", "lumen_mM", "bridge_A", "contact_A")


def differences(a, b, records, bridges):
    """{quantity: largest |a - b|} over the records (absolute, in each quantity's units)."""
    rows = per_record(a, b, records, bridges)
    return {k: max(rows[t][k] for t in records) for k in QUANTITIES}


def scales(a, records, bridges):
    """{quantity: its largest |value|} over the records: the scale of the rounding floor."""
    out = dict.fromkeys(QUANTITIES, 0.0)
    for t in records:
        for v in a[t]["V"].values():
            out["V"] = max(out["V"], abs(v))
        for vol, mm in a[t]["lumens"].values():
            out["lumen_volume_pL"] = max(out["lumen_volume_pL"], abs(vol))
            out["lumen_mM"] = max(out["lumen_mM"], float(np.max(np.abs(mm))))
        for name, (_, current) in a[t]["junctions"].items():
            key = "bridge_A" if name in bridges else "contact_A"
            out[key] = max(out[key], abs(current))
    return out


def live(record, bridges):
    """{quantity: how many entries are live at the record} (the engine's)."""
    junctions = record["junctions"]
    return dict(
        V=len(record["V"]),
        lumen_volume_pL=len(record["lumens"]),
        lumen_mM=len(record["lumens"]),
        bridge_A=sum(name in bridges for name in junctions),
        contact_A=sum(name not in bridges for name in junctions),
    )


def per_record(a, b, records, bridges):
    """{t: {quantity: largest |a - b| at t}} (absolute, in each quantity's units); each
    junction's currents compared along b's direction."""
    rows = {}
    for t in records:
        out = dict.fromkeys(QUANTITIES, 0.0)
        assert set(a[t]["V"]) == set(b[t]["V"]), (t, "live cells differ")
        assert set(a[t]["lumens"]) == set(b[t]["lumens"]), (t, "live lumens differ")
        assert set(a[t]["junctions"]) == set(b[t]["junctions"]), (t, "live junctions differ")
        for c, v in a[t]["V"].items():
            out["V"] = max(out["V"], abs(v - b[t]["V"][c]))
        for c, (vol, mm) in a[t]["lumens"].items():
            out["lumen_volume_pL"] = max(out["lumen_volume_pL"], abs(vol - b[t]["lumens"][c][0]))
            out["lumen_mM"] = max(out["lumen_mM"], float(np.max(np.abs(mm - b[t]["lumens"][c][1]))))
        for name, (ends, current) in a[t]["junctions"].items():
            to, theirs = b[t]["junctions"][name]
            key = "bridge_A" if name in bridges else "contact_A"
            out[key] = max(out[key], abs(oriented(current, ends, to) - theirs))
        rows[t] = out
    return rows


def compare(name, *, judged=False):
    """One world's report (module docstring); judged, only the judged step and R-tissue at its
    SMALL atol, for the verdict against the registered tolerances."""
    records = WORLDS[name][1]
    engine = {}
    for dt in (DT,) if judged else (DT, 0.5 * DT):
        raw = engine_world(name, dt)
        spec = parse_spec(raw)
        start = time.perf_counter()
        engine[dt] = (raw, spec, engine_records(spec, run(spec), records))
        print(f"{name}: engine dt={dt}: {time.perf_counter() - start:.1f} s", flush=True)
    raw, spec, mine = engine[DT]
    world = tissue_world(raw, spec, get_model(spec.model))
    rt.check_world(world)
    start = time.perf_counter()
    reference = tissue_records(
        rt.simulate_divisions(world, END, record=records, atol=SMALL), records
    )
    bridges = bridge_ids(raw)
    if judged:
        return dict(
            records_s=list(records),
            dt_s=DT,
            per_record={
                t: dict(
                    engine_minus_reference=per_record(mine, reference, records, bridges)[t],
                    live=live(mine[t], bridges),
                )
                for t in records
            },
        )
    tight = tissue_records(rt.simulate_divisions(world, END, record=records, atol=TIGHT), records)
    print(f"{name}: R-tissue (two runs): {time.perf_counter() - start:.1f} s", flush=True)
    halved = engine[0.5 * DT][2]
    return dict(
        records_s=list(records),
        dt_s=DT,
        engine_minus_reference=differences(mine, reference, records, bridges),
        engine_step_term=differences(mine, halved, records, bridges),
        reference_term=differences(reference, tight, records, bridges),
        scale=scales(mine, records, bridges),
        per_record={
            t: dict(
                engine_minus_reference=per_record(mine, reference, records, bridges)[t],
                engine_step_term=per_record(mine, halved, records, bridges)[t],
                reference_term=per_record(reference, tight, records, bridges)[t],
                live=live(mine[t], bridges),
            )
            for t in records
        },
        sample=dict(
            t=records[-1],
            engine_V=mine[records[-1]]["V"],
            reference_V=reference[records[-1]]["V"],
        ),
    )


def verdict(report, item):
    """Q3's verdict: every live quantity at every record within its registered tolerance."""
    rows, ok = {}, True
    for name, world in item["tolerances"]["worlds"].items():
        for q, entry in world["quantities"].items():
            for t, registered in entry["records"].items():
                seen = report["worlds"][name]["per_record"][t]["engine_minus_reference"][q]
                passed = seen <= registered["tolerance"]
                rows[f"{name} {q} {t}"] = dict(
                    difference=seen, tolerance=registered["tolerance"], passed=passed
                )
                ok &= passed
    return dict(items=rows, verdict="pass" if ok else "fail")


def judge(output, protocol_path=None, root=None):
    """The judged run: refused first unless the S5 protocol is registered and the source a
    clean snapshot (s5_protocol.registered); then each world at the judged step against
    R-tissue, with the verdict."""
    from validation.division import s5_protocol

    _, item = s5_protocol.registered(
        "Q3", protocol_path or s5_protocol.PROTOCOL, root or s5_protocol.ROOT
    )
    if item["judged_dt_s"] != DT:
        raise SystemExit("Refused: the registered judged step is not the driver's")
    jax.config.update("jax_enable_x64", True)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    report = dict(status="Judged run of Q3", worlds={})
    for name in WORLDS:
        report["worlds"][name] = compare(name, judged=True)
    # The run first, then its verdict, computed on what was written: the JSON round trip
    # gives the record keys the protocol's form ("0.0025").
    path = output / "q3_judged.json"
    path.write_text(json.dumps(report, indent=1, default=float) + "\n")
    report = json.loads(path.read_text())
    report["verdict"] = verdict(report, item)
    path.write_text(json.dumps(report, indent=1, default=float) + "\n")
    return report


def main(output, names=()):
    jax.config.update("jax_enable_x64", True)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    report = dict(status=STATUS, worlds={})
    for name in names or WORLDS:
        report["worlds"][name] = compare(name)
        (output / "q3_tissue.json").write_text(json.dumps(report, indent=1, default=float) + "\n")
    print(json.dumps(report, indent=1, default=float), flush=True)


if __name__ == "__main__":
    if sys.argv[1:2] == ["judge"]:
        judge(sys.argv[2])
    else:
        main(sys.argv[1], tuple(sys.argv[2:]))
