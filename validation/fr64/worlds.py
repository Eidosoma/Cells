"""FR-64's compiled worlds, built from registered or fixture worlds, for its tests.

**pair_world** is D327's pair: FR-50 phase 2's one-way channel records on populations whose readers
are shifted (the lead's ruling 1 of 27 November; docs/FR64_VOLTAGE_SHIFT_DESIGN.md §17.5). It starts
from FR-50's World 1 (validation/fr50/engine.world_1), with E4's population and its registered
values: one 1 pL cell on the held bath at V = E_K, @3 alone, with no operator.
- **Added:** an H row and a buffer row B. B4 (cells.kind.rapid_proton_buffer@1) is declared at the
  cell, which sits at pH 7.2; the bath is held at pH 7.4.
- **The three populations,** each recording K:
  - `k_population`, E4's gate-free K population, its block now reading the cell's pH (inside, B4's
    free h) in place of E4's K reversal;
  - `kv_bath`, a Kv1.5 whose m reads the bath's pH;
  - `kv_reversal`, a Kv1.5 whose m reads V - E_K.
  - Each Kv1.5 starts at its gates' targets, m at its V_r and h at V.
- **It is steady.** At V = E_K every K population's net is zero, and nothing moves protons, so B4's
  free h and every dV stay put.
  - So every record is its one-way flux times t.
  - That flux is g c B(-+x) o u, with o the declared gates' opening and u FR-51's law at the
    block's V_ref (validation/fr64/closed_forms.py).
"""

import math

import numpy as np

from cells.laws.channels import kv1p5_mh
from cells.laws.channels import voltage_shift as vshift
from cells.laws.electrochemistry import F, R
from validation.fr50 import engine as fr50

PK = 7.2  # The buffer's pK.
BUFFER_mM = 10.0
CELL_PH, BATH_PH = 7.2, 7.4
SIGMA, REFERENCE_PH, WINDOW = -0.0234, 7.3, [6.8, 7.5]
KV = ("kv_bath", "kv_reversal")


def ph_shift(side):
    return {"ph": {"side": side, "shift_V_per_ph": SIGMA, "reference_ph": REFERENCE_PH,
                   "ph_window": list(WINDOW)}}  # fmt: skip


def h_mM(ph):
    return 1000.0 * 10.0**-ph


def pair_world(*, dt=1e-4, end=1e-2):
    """D327's pair's world (the module docstring), at step dt (s) to `end` (s)."""
    cases = fr50._cases()
    raw = fr50.world_1(None, cases["E4"], dt=dt, end=end, records=False)
    m, x = raw["model"], raw["execution"]
    m["species"] += [
        dict(id="H", valence=1, standard_mu_RT=0.0),
        dict(id="B", valence=-1, standard_mu_RT=0.0, protonated_standard_mu_RT=-PK * math.log(10)),
    ]
    m["standard_concentration_mM"] = 1000.0
    cell, bath = m["cells"][0], m["extracellular"][0]
    h0, k = h_mM(CELL_PH), h_mM(PK)
    for node, h_eq, b in ((cell, h0 + BUFFER_mM * h0 / (h0 + k), BUFFER_mM),
                          (bath, h_mM(BATH_PH), 1e-9)):  # fmt: skip
        volume = node["volume_pL"]
        node["initial_amount_fmol"] |= dict(H=h_eq * volume, B=b * volume)
        node["fixed_charge_equivalent_fmol"] -= h_eq * volume - b * volume
    for patch in m["membranes"]:
        patch["permeability_m_per_s"] |= dict(H=0.0, B=0.0)
    x["material_balance_atol_fmol"] |= dict(H=1e-10, B=1e-10)
    m["stage_reads"] = [dict(read_id="cells.kind.rapid_proton_buffer@1", proton_row="H",
                             buffers={cell["id"]: ["B"]}, k_on_per_mM_s={"B": 1e7})]  # fmt: skip
    k_population = m["channels"][0]
    k_population["voltage_shift"] = {"block": ph_shift("inside")}
    temperature = m["temperature_K"]
    c_in, c_out = cell["initial_amount_fmol"]["K"], bath["initial_amount_fmol"]["K"]  # 1 pL each.
    e_k = R * temperature / F * math.log(c_out / c_in)
    v_r = dict(
        kv_bath=e_k - vshift.PhShift.delta_v(np.float64(h_mM(BATH_PH)), SIGMA, REFERENCE_PH),
        kv_reversal=e_k - vshift.ReversalShift.delta_v(np.float64(c_in), np.float64(c_out), 1,
                                                       temperature),  # fmt: skip
    )
    shifts = dict(kv_bath={"m": ph_shift("outside")}, kv_reversal={"m": {"reversal_of": "K"}})
    for name in KV:
        at_vr = kv1p5_mh.kinetics(np.asarray([v_r[name]]), xp=np)[0]
        at_v = kv1p5_mh.kinetics(np.asarray([e_k]), xp=np)[0]
        m["channels"].append(
            dict(
                id=name, membrane_id=k_population["membrane_id"], kinetic_law=kv1p5_mh.LAW_ID,
                max_permeability_m_per_s=k_population["max_permeability_m_per_s"],
                abundance=1.0, initial_gate=[float(at_vr[0, 0]), float(at_v[1, 0])],
                permeant_ions=[dict(species_id="K", relative_permeability=1.0)],
                voltage_shift={"gates": shifts[name]},
            )
        )  # fmt: skip
        raw["experiment"]["channel_controls"].append(
            dict(channel_id=name, schedule=[dict(time=0.0, availability=1.0)])
        )
    x["channel_capacity"] = 3
    m["one_way_records"] = [
        dict(entity="channel", id=c["id"], species=["K"]) for c in m["channels"]
    ]
    return raw


CELL_PH_COMPOSED, BATH_PH_COMPOSED, WINDOW_COMPOSED = 7.0, 6.8, [6.5, 7.5]
K_STEP_mM = 14.6  # KCl for NaCl at the bath: K 5.4 -> 20 mM, inside probe I's measured points.


def composed_world(*, dt=2e-4, end=0.08, step_at=0.04, shifted=True):
    """The note's §9.3 composed world: cells.model.resolved_pump_composite@1 over @3, ARS(2,2,2),
    FR-51's one cell on its held bath (validation/fr51/engine.raw_world, B1), B4 at the cell (pH
    7.0), the bath held at pH 6.8 from the start, and one neutral KCl step at the bath at
    `step_at` (cells.operator.scheduled_bath_composition@1). Its four populations:
    - P1, kv_bath: a Kv1.5 whose m reads the bath's pH (dV = sigma (6.8 - 7.3));
    - P2, kv_reversal: a Kv1.5 whose m reads V - E_K, which the K step moves;
    - P3, population: B1's K population with FR-51's block on the K reversal;
    - P4, na_block: an Na leak with B1's block on the cell's pH (B4's free h).
    shifted False keeps every population and block and drops the shifts (the timing twin, D142).
    Every step is observed."""
    from validation.fr51 import engine as fr51
    from validation.tissue import bath_schedule_fixtures as bfx

    raw = fr51.raw_world("B1_two_modes_E1")
    m, e, x = raw["model"], raw["experiment"], raw["execution"]
    m["species"] += [
        dict(id="H", valence=1, standard_mu_RT=0.0),
        dict(id="B", valence=-1, standard_mu_RT=0.0, protonated_standard_mu_RT=-PK * math.log(10)),
    ]
    m["standard_concentration_mM"] = 1000.0
    cell, bath = m["cells"][0], m["extracellular"][0]
    h0, k = h_mM(CELL_PH_COMPOSED), h_mM(PK)
    for node, h_eq, b in ((cell, h0 + BUFFER_mM * h0 / (h0 + k), BUFFER_mM),
                          (bath, h_mM(BATH_PH_COMPOSED), 1e-9)):  # fmt: skip
        volume = node["volume_pL"]
        node["initial_amount_fmol"] |= dict(H=h_eq * volume, B=b * volume)
        node["fixed_charge_equivalent_fmol"] -= h_eq * volume - b * volume
    for patch in m["membranes"]:
        patch["permeability_m_per_s"] |= dict(H=0.0, B=0.0)
    x["material_balance_atol_fmol"] |= dict(H=1e-10, B=1e-10)
    m["stage_reads"] = [dict(read_id="cells.kind.rapid_proton_buffer@1", proton_row="H",
                             buffers={cell["id"]: ["B"]}, k_on_per_mM_s={"B": 1e7})]  # fmt: skip
    population = m["channels"][0]  # P3: B1's block, already on the K reversal (the driver's).
    window = dict(ph_window=list(WINDOW_COMPOSED))
    bath_ph, cell_ph = ph_shift("outside"), ph_shift("inside")
    bath_ph["ph"] |= window
    cell_ph["ph"] |= window
    patch = population["membrane_id"]
    kv = dict(membrane_id=patch, kinetic_law=kv1p5_mh.LAW_ID, max_permeability_m_per_s=1e-8,
              abundance=1.0, initial_gate=[0.01, 0.9],
              permeant_ions=[dict(species_id="K", relative_permeability=1.0)])  # fmt: skip
    m["channels"] += [
        dict(kv, id="kv_bath", voltage_shift={"gates": {"m": bath_ph}}),
        dict(kv, id="kv_reversal", voltage_shift={"gates": {"m": {"reversal_of": "K"}}}),
        dict(id="na_block", membrane_id=patch, kinetic_law="cells.channel.naleak_always_open@1",
             max_permeability_m_per_s=2e-9, abundance=1.0, initial_gate=[],
             permeant_ions=[dict(species_id="Na", relative_permeability=1.0)],
             block=population["block"], voltage_shift={"block": cell_ph}),
    ]  # fmt: skip
    if not shifted:
        for channel in m["channels"]:
            channel.pop("voltage_shift", None)
    for name in ("kv_bath", "kv_reversal", "na_block"):
        e["channel_controls"].append(dict(channel_id=name, schedule=[dict(time=0.0, availability=1.0)]))
    steps = round(end / dt)
    e["end_time"] = steps * dt
    e["observation_times"] = [i * dt for i in range(steps + 1)]
    x.update(dt=dt, solver="cells.solver.imex_ars222_face_electromigration@1", channel_capacity=4,
             max_steps=steps + 2)  # fmt: skip
    from cells.definitions import pump_composite_spec as cs

    composite = cs.frozen_definition(raw)
    swap = {"NaCl": -K_STEP_mM, "KCl": K_STEP_mM}  # KCl for NaCl, as probe I measured it.
    return bfx.with_bath_schedule(composite, [bath["id"]], dict(bfx.SALTS),
                                  [(step_at, [bath["id"]], swap)])  # fmt: skip
