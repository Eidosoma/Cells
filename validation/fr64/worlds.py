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
