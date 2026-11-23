"""XC0's worlds on resolved_pump_tissue@3, built from the declared inputs alone (the Xenopus lane's
first physical preparations; DESIGN.md version 2.1 §1-§3 in the lane's workspace folder
xenopus-lane-20261119/xc0/, and `references/reference_inputs.json`, the byte copy of its frozen
declared_inputs.json that the references' REFERENCES_USAGE.md names as the engine's input).

No physics lives here: every flux, potential and booking is the engine's. This module only writes
@3 definitions, with laws main holds, by ID:
- the four patches of DESIGN §2, the cell's capacitance split by area: m_main (60 %: the Na and Cl
  leaks, the Na/K pump, the symporter), m_kleak (20 %: the K leak), m_kir (10 %: the rectifier's
  host, every constant-field permeability zero) and m_glycine (10 %: GlyR F99A's host, every
  constant-field permeability zero);
- GlyR F99A as a population of the always-open chloride leak `clleak_always_open@1` (D228 item 3)
  on m_glycine, at its permeability P_GlyR, abundance 1, its availability the arm's (DESIGN's 0 or
  1). It moves what DESIGN's Cl-only patch moves (the law's own test); m_glycine's own
  permeabilities are zero, so the population is its only conductance, and m_glycine's membrane
  control (held at 1) scales nothing. Wherever the population is declared, its voltage domain is
  @3's channel domain, -120 mV to 60 mV;
- Kir4.1 as one route of `inward_rectifier_linear_driving_force@1` (D228 item 2) on m_kir, with
  DESIGN §3.2's coefficients (g_ref from its grid, K_ref 5 mM, V_h 10 mV, s 10 mV). Its opening
  is m_kir's availability, which the builder sets to the route's declared availability whenever
  the route is declared (and to 0 otherwise);
- SLC5A8 as a population of `cells.na_anion_symport_factored@1` (D228 item 1) on m_main, N the
  cell, with DESIGN §3.3's parameters and capacity 0.01 fmol/s times the arm's factor; and, for
  version 2's thermodynamic rows only, a population of `cells.na2_anion_symport_diagram@1` with
  DESIGN §3.4's constants, its charge lumped onto the edges the law lets a definition charge
  (DIAGRAM_CHARGE);
- the Na/K pump `nak_atp_mass_action_positive@1` on m_main with the declared constants;
- P2's junction (constant_field@1 with the inert gate: junction_voltage_relaxation@1 at
  minimum_open_fraction 1 and initial_gate 1) and P1LB's face `access` (logmean_electrodiffusion@1).

**The state grammar** of the references' interface (REFERENCES_USAGE.md, "Keys"): ion set x
exterior x temperature, 3 x 6 x 2 = 36 states.

**The charge anchor** (declared_inputs' charge_anchor_rule): a cell's fixed background holds
C_total V0 / CHARGE_PER_FMOL - sum z n, its initial charge C_total V0. A held bath's fixed
background is minus its ionic charge, its initial charge 0. An outside node in a capacitor
component with no held bath (P1L, P1LB) holds minus its cells' capacitor charge, since @3 requires
a component's charges to sum to zero (the declared rule's 0 is refused there at parse).

**Declared deviations from DESIGN §2**, each forced by an engine rule and changing no compared
quantity: a declared zero amount is TRACE_mM; the host's material tolerance is capped at 1e-10
fmol; P1L gauges its outside node; P1LB declares the floor field solver (D147). See each constant.
"""

import copy
import json
import math
from pathlib import Path

from cells.laws.electrochemistry import CHARGE_PER_FMOL

HERE = Path(__file__).resolve().parent
INPUTS = HERE / "references" / "reference_inputs.json"
MODEL = "resolved_pump_tissue@3"
RECTIFIER = "inward_rectifier_linear_driving_force@1"
CHLORIDE = "clleak_always_open@1"
SYMPORT = "cells.na_anion_symport_factored@1"
DIAGRAM = "cells.na2_anion_symport_diagram@1"
CLOSURE = "resolved_capacitor_components_current_continuity@1"
X2 = "step_doubled_energy@1"
# D147: a definition with a free field offset (P1LB's floating component, the cell and its local
# node, joined to the held bath by the face alone) declares the floor solver, version 3. @2
# refuses P1LB at parse: its face current's float64 floor lies above @2's absolute target.
FLOOR_FIELD = "capacitive_reduction_gauged_damped_newton@3"
PATCHES = ("m_main", "m_kleak", "m_kir", "m_glycine")
LEAKS = ("m_main", "m_kleak")
ION_SETS = ("primary", "bracket_Cl_high", "bracket_second_hand_table")
EXTERIORS = ("bath", "local", "bath70_Na", "bath70_inert", "bath_Cl10", "bath_Cl11p1")
TEMPERATURES = (291.15, 287.15)
INERT = "Ch"  # The inert monovalent cation of the 70 mM Cl- bath's alternative (declared_inputs).
V0 = -0.040  # The baseline charge anchor, V (DESIGN §2).
# @3's parse refuses a zero amount ("amount must be finite and positive"), so each declared zero
# (the baths' A and B, the local node's B, the cell's inert cation) is this trace. Every such row
# is impermeant at its node or moves only through the face, so no compared quantity sees it.
TRACE_mM = 1e-9
# @3 caps the host's material tolerance at 1e-10 fmol ("Material tolerance cannot exceed 1e-10
# fmol"), below the declared 1e-9: the run's own ledger check is the stricter one.
MATERIAL_ATOL_CAP_FMOL = 1e-10
# DESIGN §3.4's edges in the law's names, the cycle's order (laws/cycles/na2_anion_symport_diagram).
DIAGRAM_EDGES = (
    ("e1", "na1_P"), ("e2", "na2_P"), ("e3", "b_P"), ("e4", "loaded"),
    ("e5", "b_N"), ("e6", "na2_N"), ("e7", "na1_N"), ("e8", "empty"),
)  # fmt: skip
# The charge each edge carries from P to N (e). The law fixes zeta = 0 on b_P, b_N, na2_N and na1_N,
# so DESIGN §3.4's q on e3, e5, e6 and e7 (-0.1, -0.5, +0.4 and +0.4, +0.2 in all) is lumped onto the
# loaded crossing (0.4 + 0.2). The total is DESIGN's 1.0, so every thermodynamic relation (J-/J+ and
# the stall) is DESIGN's; the kinetics are not, and no kinetic row is run (the lead, 23 November).
DIAGRAM_CHARGE = {"na1_P": 0.2, "na2_P": 0.2, "loaded": 0.6, "empty": 0.0}


def inputs():
    """The declared inputs (the frozen byte copy beside the references)."""
    return json.loads(INPUTS.read_text())


def state_key(ion_set, exterior_name, temperature_K):
    """The references' state key, `ionset|exterior|T<K>` (REFERENCES_USAGE.md)."""
    return f"{ion_set}|{exterior_name}|T{temperature_K:g}"


def states():
    """The 36 registered states, as (ion set, exterior, temperature K)."""
    return [(i, e, t) for i in ION_SETS for e in EXTERIORS for t in TEMPERATURES]


def cytosol_mM(ion_set, d):
    """The cell's concentrations (mM) for an ion set, with the declared cell's B."""
    mm = dict(d["ion_sets"][ion_set]["cytosol_mM"])
    cell = d["nodes"]["cell"]
    mm.setdefault("B", cell["initial_amount_fmol"]["B"] / cell["volume_pL"])
    return mm


def exterior(name, d):
    """(concentrations mM, volume pL, reservoir) of an exterior: REFERENCES_USAGE.md's six, and
    the butyrate dose bath of the declared inputs."""
    nodes = d["nodes"]

    def node(key):
        n = nodes[key]["node"]
        v = n["volume_pL"]
        return {s: a / v for s, a in n["initial_amount_fmol"].items()}, v, n["reservoir"]

    bath, volume, reservoir = node("bath")
    if name == "bath":
        return bath, volume, reservoir
    if name == "local":
        return node("local")
    if name == "bath70_Na":
        return node("bath_70Cl")
    if name == "bath70_inert":  # Na_out stays 0.1x MMR's; the inert cation balances 70 mM Cl-.
        mm = dict(bath, Cl=70.0)
        mm[INERT] = mm["Cl"] - mm["Na"] - mm["K"]
        return mm, volume, reservoir
    if name == "bath_Cl10":
        return dict(bath, Cl=10.0), volume, reservoir
    if name == "bath_Cl11p1":
        return dict(bath, Cl=11.1), volume, reservoir
    if name == "bath_butyrate":
        return node("bath_butyrate_dose")
    raise KeyError(f"no exterior {name}")


def species_ids(d, extra=()):
    return [s["id"] for s in d["species"]] + list(extra)


def valences(d, extra=()):
    z = {s["id"]: s["valence"] for s in d["species"]}
    if INERT in extra:
        z[INERT] = 1
    return z


def total_capacitance(d):
    return math.fsum(m["capacitance_F"] for m in d["membranes"])


def positive(value_mM):
    """A declared concentration, or TRACE_mM where it is zero (the parse's positivity)."""
    return float(value_mM) if value_mM > 0 else TRACE_mM


def node_entry(node_id, mm, volume, charge, d, extra, *, outside=None):
    """A node at mm (mM) holding the charge anchor `charge` (C) in its fixed background."""
    ids, z = species_ids(d, extra), valences(d, extra)
    amounts = {s: positive(mm.get(s, 0.0)) * volume for s in ids}
    entry = dict(
        id=node_id,
        volume_pL=volume,
        initial_amount_fmol=amounts,
        fixed_charge_equivalent_fmol=charge / CHARGE_PER_FMOL
        - math.fsum(z[s] * amounts[s] for s in ids),
        initial_charge_C=charge,
    )
    if outside is not None:
        entry |= dict(reservoir=outside, boundary_potential_V=0.0)
    return entry


def pump_entry(cell_id, d):
    q = next(m for m in d["membranes"] if m["id"] == "m_main")["pump"]
    return dict(
        id=f"pump_{cell_id}",
        law=q["law"],
        roles=dict(sodium="Na", potassium="K"),
        stoichiometry=dict(q["stoichiometry"]),
        capacity_fmol_per_s=q["capacity_fmol_per_s"],
        km_na_mM=q["km_na_mM"],
        km_k_mM=q["km_k_mM"],
        km_atp_mM=q["km_atp_mM"],
        metabolism={
            k: q["metabolism"][k]
            for k in ("kind", "atp_mM", "adp_mM", "pi_mM", "delta_g0_J_per_mol")
        },
    )


def patch_entries(cell_id, outside_id, d, extra, *, pump, scale_capacitance):
    """The cell's four patches (DESIGN §2): the leaks' permeabilities on m_main and m_kleak, zero
    on m_kir and m_glycine; the pump on m_main when declared."""
    ids = species_ids(d, extra)
    out = []
    for m in d["membranes"]:
        permeability = {s: 0.0 for s in ids}
        if m["id"] in LEAKS:
            permeability |= {s: float(m["permeability_m_per_s"][s]) for s in species_ids(d)}
        out.append(
            dict(
                id=f"{m['id']}_{cell_id}",
                inside=cell_id,
                outside=outside_id,
                area_m2=m["area_m2"],
                capacitance_F=m["capacitance_F"] * scale_capacitance,
                permeability_m_per_s=permeability,
                law="constant_field@1",
                pump=pump_entry(cell_id, d) if pump and m["id"] == "m_main" else None,
                calcium_pump=None,
            )
        )
    return out


def glycine_population(cell_id, permeability):
    """GlyR F99A on the cell's m_glycine: the always-open chloride leak at P_GlyR, abundance 1."""
    return dict(
        id=f"glyr_{cell_id}",
        membrane_id=f"m_glycine_{cell_id}",
        kinetic_law=CHLORIDE,
        max_permeability_m_per_s=float(permeability),
        abundance=1.0,
        initial_gate=[],
        permeant_ions=[dict(species_id="Cl", relative_permeability=1.0)],
    )


def kir_route(cell_id, g_ref, d, *, k_ref_mM=None):
    """Kir4.1 on the cell's m_kir (DESIGN §3.2's declaration, g_ref the arm's)."""
    e = d["kir_route"]["entry"]
    return dict(
        id=f"kir_{cell_id}",
        patch=f"m_kir_{cell_id}",
        law=RECTIFIER,
        species="K",
        g_ref_S_per_m2=float(g_ref),
        k_ref_mM=float(e["k_ref_mM"] if k_ref_mM is None else k_ref_mM),
        v_half_V=float(e["v_half_V"]),
        slope_V=float(e["slope_V"]),
    )


def symporter(cell_id, capacity, d, *, n_na=None):
    """SLC5A8 version 1 on the cell's m_main, N the cell (DESIGN §3.3)."""
    s = d["symporter_v1"]["parameters"]
    return dict(
        id=f"symport_{cell_id}",
        host=f"m_main_{cell_id}",
        law=SYMPORT,
        orientation={"N": "a"},
        capacity_fmol_s=float(capacity),
        roles={"Na": "Na", "B": "B"},
        parameters=dict(
            n_Na=int(s["n_Na"] if n_na is None else n_na),
            K_Na_mM=float(s["K_Na_mM"]),
            K_B_mM=float(s["K_B_mM"]),
            hill_Na=int(s["hill_Na"]),
            hill_B=int(s["hill_B"]),
        ),
        held_rows=[],
    )


def diagram_parameters(d):
    """DESIGN §3.4's constants in the law's parameter names, with DIAGRAM_CHARGE's split
    (zeta_forward = -q/2, zeta_backward = +q/2: the declared symmetric barrier)."""
    edges = {e["id"]: e for e in d["symporter_v2"]["edges"]}
    parameters = {}
    for design, name in DIAGRAM_EDGES:
        parameters[f"k_{name}_f"] = float(edges[design]["forward"]["k0_per_s"])
        parameters[f"k_{name}_b"] = float(edges[design]["backward"]["k0_per_s"])
    for name, q in DIAGRAM_CHARGE.items():
        parameters[f"z_{name}_f"] = -0.5 * q
        parameters[f"z_{name}_b"] = 0.5 * q
    return parameters


def diagram_symporter(cell_id, capacity, d):
    """SLC5A8 version 2 on the cell's m_main, N the cell: for the thermodynamic rows only."""
    return dict(
        id=f"symport2_{cell_id}",
        host=f"m_main_{cell_id}",
        law=DIAGRAM,
        orientation={"N": "a"},
        capacity_fmol_s=float(capacity),
        roles={"Na": "Na", "B": "B"},
        parameters=diagram_parameters(d),
        held_rows=[],
    )


def schedule(value):
    return [dict(time=0.0, availability=float(value))]


def world(
    *,
    cells=(("cell_1", "primary"),),
    exterior_name="bath",
    temperature_K=291.15,
    v0=V0,
    cell_mm=None,
    exterior_mm=None,
    leaks=None,
    glycine=None,
    kir=None,
    pump=None,
    symport=None,
    diagram=None,
    junction=None,
    face=False,
    scale_capacitance=1.0,
    dt=None,
    end_time=None,
    observation_times=None,
    energy_check_cap=None,
    d=None,
):
    """One XC0 world (P1, P1L, P1LB or P2), every cell facing one outside node.

    cells: (cell id, ion set) per cell. cell_mm {cell: {species: mM}} and exterior_mm {species: mM}
    override concentrations. v0: the charge anchor (V), a number or {cell: V}.
    leaks {cell: {"m_main": a, "m_kleak": a}}: the leak patches' availabilities (default 1).
    glycine {cell: (P_GlyR, a)}: GlyR F99A declared, at availability a.
    kir {cell: (g_ref, a)}: the route declared, m_kir at availability a (m_kir is 0 otherwise).
    pump {cell: a}: the pump declared on m_main at availability a (none otherwise).
    symport {cell: capacity or (capacity, n_Na)} / diagram {cell: capacity}: version 1 / version 2
    on m_main. junction: a multiple of the declared junction permeability between the first two
    cells, or None. face: P1LB's face from the local node to a held bath (exterior "local" only).
    d: the inputs (default: the declared inputs; tests pass invented ones).
    """
    d = inputs() if d is None else d
    x = d["execution"]
    outside_mm, volume, reservoir = exterior(exterior_name, d)
    outside_mm = dict(outside_mm, **(exterior_mm or {}))
    extra = (INERT,) if INERT in outside_mm else ()
    ids = species_ids(d, extra)
    outside_id = "outside_local" if exterior_name == "local" else "outside_bath"
    c_total = total_capacitance(d) * scale_capacitance

    def anchor(cell_id):
        return v0[cell_id] if isinstance(v0, dict) else v0

    plates = 0.0 if reservoir else -math.fsum(c_total * anchor(c) for c, _ in cells)
    outside = [node_entry(outside_id, outside_mm, volume, plates, d, extra, outside=reservoir)]
    faces = []
    if face:
        if exterior_name != "local":
            raise ValueError("P1LB's face joins the local node to the bath")
        bath_mm, bath_volume, bath_reservoir = exterior("bath", d)
        outside.append(node_entry("outside_bath", bath_mm, bath_volume, 0.0, d, extra,
                                  outside=bath_reservoir))  # fmt: skip
        f = d["face"]
        faces.append(
            dict(
                id=f["id"],
                sender=f["sender"],
                receiver=f["receiver"],
                area_m2=f["area_m2"],
                length_m=f["length_m"],
                diffusivity_m2_per_s={s: float(f["diffusivity_m2_per_s"].get(s, 0.0)) for s in ids},
                law=f["law"],
            )
        )
    leaks, glycine, kir = leaks or {}, glycine or {}, kir or {}
    pump, symport, diagram = pump or {}, symport or {}, diagram or {}
    model_cells, membranes, channels, routes, transporters = [], [], [], [], []
    controls = {}
    for cell_id, ion_set in cells:
        mm = dict(cytosol_mM(ion_set, d), **(cell_mm or {}).get(cell_id, {}))
        model_cells.append(node_entry(cell_id, mm, volume_pl(d), c_total * anchor(cell_id), d, extra))
        membranes += patch_entries(cell_id, outside_id, d, extra, pump=cell_id in pump,
                                   scale_capacitance=scale_capacitance)  # fmt: skip
        for patch in LEAKS:
            controls[f"{patch}_{cell_id}"] = float(leaks.get(cell_id, {}).get(patch, 1.0))
        controls[f"m_glycine_{cell_id}"] = 1.0  # No permeability of its own: it scales nothing.
        controls[f"m_kir_{cell_id}"] = 0.0
        if cell_id in glycine:
            permeability, _ = glycine[cell_id]
            channels.append(glycine_population(cell_id, permeability))
        if cell_id in kir:
            g_ref, opening = kir[cell_id]
            routes.append(kir_route(cell_id, g_ref, d))
            controls[f"m_kir_{cell_id}"] = float(opening)
        if cell_id in symport:
            value = symport[cell_id]
            capacity, n_na = value if isinstance(value, tuple) else (value, None)
            transporters.append(symporter(cell_id, capacity, d, n_na=n_na))
        if cell_id in diagram:
            transporters.append(diagram_symporter(cell_id, diagram[cell_id], d))
    junctions = []
    if junction is not None:
        j = d["junction"]
        (a, _), (b, _) = cells[:2]
        junctions.append(
            dict(
                id=j["id"],
                sender=a,
                receiver=b,
                area_m2=j["area_m2"],
                permeability_m_per_s={
                    s: float(j["permeability_m_per_s"].get(s, 0.0)) * float(junction) for s in ids
                },
                law=j["law"],
                gate={k: j["gate"][k] for k in ("law", "threshold_voltage_V",
                                                "minimum_open_fraction", "initial_gate")},
            )  # fmt: skip
        )
    dt = float(x["dt_s"]) if dt is None else float(dt)
    end_time = dt if end_time is None else float(end_time)
    times = [0.0, end_time] if observation_times is None else list(observation_times)
    raw = dict(
        schema_version=1,
        model=dict(
            id=MODEL,
            temperature_K=float(temperature_K),
            species=[dict(id=s, valence=valences(d, extra)[s]) for s in ids],
            cells=model_cells,
            extracellular=outside,
            membranes=membranes,
            junctions=junctions,
            faces=faces,
            # A world with no held bath (P1L) gauges its one outside node (@3's closed-graph rule).
            closure=dict(
                law=CLOSURE,
                gauge_reference=None if any(o["reservoir"] for o in outside) else outside_id,
            ),
            channels=channels,
        ),
        experiment=dict(
            end_time=end_time,
            observation_times=times,
            membrane_controls=[
                dict(membrane_id=m["id"], schedule=schedule(controls[m["id"]])) for m in membranes
            ],
            junction_controls=[dict(junction_id=j["id"], schedule=schedule(1.0)) for j in junctions],
            pump_controls=[
                dict(pump_id=f"pump_{c}", schedule=schedule(pump[c])) for c, _ in cells if c in pump
            ],
            calcium_pump_controls=[],
            channel_controls=[
                dict(channel_id=f"glyr_{c}", schedule=schedule(glycine[c][1]))
                for c, _ in cells
                if c in glycine
            ],
        ),
        execution=dict(
            dt=dt,
            capacity=len(model_cells),
            extracellular_capacity=len(outside),
            membrane_capacity=len(membranes),
            edge_capacity=len(junctions),
            face_capacity=max(1, len(faces)),
            channel_capacity=len(channels),
            backend="cpu",
            jit=True,
            precision=x["precision"],
            solver=x["solver"],
            field_solver=FLOOR_FIELD if faces else x["field_solver"],
            max_steps=int(math.ceil(end_time / dt)) + 8,
            max_trace_bytes=2**31,
            material_balance_atol_fmol={
                s: min(float(x["material_balance_atol_fmol"].get(s, 1e-9)), MATERIAL_ATOL_CAP_FMOL)
                for s in ids
            },
        ),
    )
    if routes:
        raw["model"]["passive_routes"] = routes
    if transporters:
        raw["model"]["transporters"] = transporters
    if energy_check_cap is not None:
        raw["execution"]["energy_check"] = dict(check=X2, integration_error_cap=energy_check_cap)
    return copy.deepcopy(raw)


def volume_pl(d):
    return d["nodes"]["cell"]["volume_pL"]
