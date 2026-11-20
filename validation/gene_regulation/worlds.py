"""Gene regulation's option A, its worlds for the engine (development, not judged): the sheet's A1.

Every value is the sheet's (docs/TEMPLATED_POLYMERISATION_LAWS.md, tag gr1-sheet-2026-11-20b), read
from validation/gene_regulation/sheet_check.py, whose default check holds its typed numbers to the
sheet's text. The potentials are the sheet's numeric test instance (§3.3). The registration names
the source of the fuel's later (G6).

The engine's layout choices, none of them physics:
- the cell is a 1 pL node holding K+ and an impermeant anion Y- as inert background, 140 mM each;
- a patch with zero permeability faces a 1 pL bath held at 0 V, so no ion moves: the cell has no
  channels (the sheet's A1);
- the expression rows are inventory species, at the declared trace in the bath, which the
  impermeant rows can neither enter nor leave;
- the operators are D150's turnover for the regulator X, B1′'s coupling of X onto transcription's
  initiation rate, and templated_polymerisation@1.
"""

import copy
import math

from cells.definitions import pump_composite_spec as cs
from cells.registry.inventory_species import add_inventory_species
from validation.gene_regulation import sheet_check as sheet

CELL, BATH, PATCH = "cell_0", "bath_0", "patch_0"
COUPLING = "c_regulator"
IMEX = "imex_ars222_face_electromigration@1"
FIELD_SOLVER = "capacitive_reduction_gauged_damped_newton@2"
CLOSURE = "resolved_capacitor_components_current_continuity@1"
BACKGROUND_mM = 140.0
AREA_M2 = 1e-10
CAPACITANCE_F_PER_M2 = 0.01
TRACE_mM = 1e-15
FLOOR_FMOL = 1e-20
DIFFUSIVITY = 1e-10  # m^2/s: the cell has no face, so it moves nothing.
ROWS = ("X", "N", "M", "A", "ATP", "ADP", "Pi", "R", "P")
POLYMERISATION = "templated_polymerisation@1"


def _f(name):
    return float(sheet.A1[name])


def potentials_RT():
    """{row: mu°/RT at 1 M} of the sheet's numeric test instance (§3.3, §5.3): ADP, Pi, M and A
    at 0; ATP, N and the residues from the four symbols; each polymer L times its residue's."""
    mu = {k: float(v) for k, v in sheet.test_instance_potentials().items()}
    out = {row: mu[row] for row in ("ATP", "ADP", "Pi", "N", "M", "A")}
    out["R"] = _f("L_R") * mu["R_res"]
    out["P"] = _f("L_P") * mu["P_res"]
    return out


def _identity(name):
    return dict(id=name, catalogue=None, evidence=None)


def _schedule(changes, key):
    return [{"time": float(t), key: float(v)} for t, v in changes]


def a1(*, dt=0.5, end=None, every=60.0):
    """The sheet's A1 (§5.1): one gene, open loop, phase 1 to t_off and production of X off
    after, to `end` (the sheet's t_end by default), observed every `every` seconds."""
    end = _f("t_end") if end is None else float(end)
    rows = [k * every for k in range(int(math.floor(end / every)) + 1)]
    if rows[-1] != end:
        rows.append(end)
    volume = _f("V")
    background = {"K": BACKGROUND_mM * volume, "Y": BACKGROUND_mM * volume}
    raw = dict(
        schema_version=1,
        model=dict(
            id="resolved_pump_tissue@3",
            temperature_K=float(sheet.T_K),
            species=[dict(id="K", valence=1), dict(id="Y", valence=-1)],
            cells=[
                dict(
                    id=CELL,
                    volume_pL=volume,
                    initial_amount_fmol=dict(background),
                    fixed_charge_equivalent_fmol=0.0,
                    initial_charge_C=0.0,
                )
            ],
            extracellular=[
                dict(
                    id=BATH,
                    volume_pL=1.0,
                    initial_amount_fmol={"K": BACKGROUND_mM, "Y": BACKGROUND_mM},
                    fixed_charge_equivalent_fmol=0.0,
                    initial_charge_C=0.0,
                    reservoir=True,
                    boundary_potential_V=0.0,
                )
            ],
            membranes=[
                dict(
                    id=PATCH,
                    inside=CELL,
                    outside=BATH,
                    area_m2=AREA_M2,
                    capacitance_F=CAPACITANCE_F_PER_M2 * AREA_M2,
                    permeability_m_per_s={"K": 0.0, "Y": 0.0},
                    law="constant_field@1",
                    pump=None,
                    calcium_pump=None,
                )
            ],
            junctions=[],
            faces=[],
            closure=dict(law=CLOSURE, gauge_reference=None),
            channels=[],
        ),
        experiment=dict(
            end_time=end,
            observation_times=rows,
            membrane_controls=[
                dict(membrane_id=PATCH, schedule=_schedule([(0, 1)], "availability"))
            ],
            junction_controls=[],
            pump_controls=[],
            calcium_pump_controls=[],
            channel_controls=[],
        ),
        execution=dict(
            dt=dt,
            capacity=1,
            extracellular_capacity=1,
            membrane_capacity=1,
            edge_capacity=0,
            face_capacity=1,
            channel_capacity=0,
            backend="cpu",
            jit=True,
            precision="float64",
            solver=IMEX,
            field_solver=FIELD_SOLVER,
            max_steps=int(math.ceil(end / dt)) + 8,
            max_trace_bytes=2**31,
            material_balance_atol_fmol={"K": 1e-10, "Y": 1e-10},
        ),
    )
    start = dict(
        X=_f("c_X"), N=_f("c_N"), M=_f("c_M"), A=_f("c_A"), ATP=_f("c_ATP"),
        ADP=_f("c_ADP"), Pi=_f("c_Pi"), R=_f("c_R"), P=_f("c_P"),
    )  # fmt: skip
    for row in ROWS:
        raw = add_inventory_species(
            raw,
            row,
            trace_mM=TRACE_mM,
            diffusivity_m2_per_s=DIFFUSIVITY,
            floor_fmol=FLOOR_FMOL,
            concentrations_mM={CELL: start[row]},
        )
        raw["execution"]["material_balance_atol_fmol"][row] = 1e-16
    raw = _with_registry(raw)
    raw = cs.frozen_definition(raw)
    return _with_operators(raw, end)


def _with_registry(raw):
    """The rows' potentials at c0 = 1000 mM (the test instance's) and the sheet's four moieties
    (§1.4), so species_registry's checks read the operator's potentials and moves."""
    out = copy.deepcopy(raw)
    m = out["model"]
    m["standard_concentration_mM"] = sheet_c0()
    mu = potentials_RT()
    for entry in m["species"]:
        if entry["id"] in mu:
            entry["standard_mu_RT"] = mu[entry["id"]]
    L_R, L_P = int(_f("L_R")), int(_f("L_P"))
    m["moieties"] = [
        dict(id="adenine", weights=dict(ATP=1, ADP=1)),
        dict(id="phosphorus", weights=dict(N=3, M=1, ATP=3, ADP=2, Pi=1, R=L_R)),
        dict(id="nucleoside", weights=dict(N=1, M=1, R=L_R)),
        dict(id="amino_acid", weights=dict(A=1, P=L_P)),
    ]
    return out


def sheet_c0():
    return 1000.0  # mM: the sheet's c° = 1 M, so the test instance's potentials need no shift.


def polymerisation_block():
    """The operator's declaration: the sheet's A1 routes (§2, §4) at the test instance."""
    mu = potentials_RT()
    a = sheet.A1
    L_R, L_P = int(a["L_R"]), int(a["L_P"])
    return dict(
        law=POLYMERISATION,
        standard_concentration_mM=sheet_c0(),
        species=[
            dict(_identity(row), standard_mu_RT=mu[row])
            for row in ("N", "M", "A", "ATP", "ADP", "Pi", "R", "P")
        ],
        pools=[
            dict(id="pol", cell=CELL, machines=float(a["M_pol"])),
            dict(id="rib", cell=CELL, machines=float(a["M_rib"])),
        ],
        chains=[
            dict(
                id="tx",
                pool="pol",
                template=dict(copies=int(a["T_copies"])),
                product="R",
                residues=L_R,
                stages=int(a["m_tx"]),
                speed_per_s=float(a["v_tx"]),
                draws=dict(N=1),
                releases=dict(Pi=2),
                saturation_mM=dict(N=float(a["K_N_tx"])),
            ),
            dict(
                id="tl",
                pool="rib",
                template=dict(species="R"),
                product="P",
                residues=L_P,
                stages=int(a["m_tl"]),
                speed_per_s=float(a["v_tl"]),
                draws=dict(A=1, ATP=4),
                releases=dict(ADP=4, Pi=4),
                saturation_mM=dict(A=float(a["K_A_tl"]), ATP=float(a["K_ATP_tl"])),
            ),
        ],
        degradations=[
            dict(id="deg_R", cell=CELL, polymer="R", residues=L_R, monomers=dict(M=1)),
            dict(id="deg_P", cell=CELL, polymer="P", residues=L_P, monomers=dict(A=1)),
        ],
        transfers=[
            dict(
                id="recharge",
                cell=CELL,
                stoichiometry=dict(M=-1, ATP=-2, N=1, ADP=2),
                saturation_mM=dict(M=float(a["K_M_rc"]), ATP=float(a["K_ATP_rc"])),
                share=2,
            )
        ],
    )


def _with_operators(raw, end):
    out = copy.deepcopy(raw)
    a = sheet.A1
    t_off = float(a["t_off"])
    production = [(0.0, float(a["P_on"]))] + ([(t_off, 0.0)] if t_off < end else [])
    turnover = dict(
        law="scheduled_species_turnover@1",
        species=[_identity("X")],
        routes=[
            dict(id="x_production", species="X", node=CELL, kind="production"),
            dict(id="x_clearance", species="X", node=CELL, kind="clearance"),
        ],
        templates=[],
    )
    coupling = dict(
        law="species_regulated_availability@2",
        species=[_identity("X")],
        states=[],
        couplings=[
            dict(
                id=COUPLING,
                target=dict(
                    operator=POLYMERISATION,
                    control="polymerisation_initiation_rate",
                    ids=["tx"],
                    evaluation="target_half_steps",
                    operating_range=[0.0, 2.0 * float(a["c_X"])],
                ),
                source={"species": "X"},
                law="hill_activation",
                half_saturation_mM=float(a["K_X"]),
                hill_coefficient=float(a["n_X"]),
                basal=float(a["b_X"]),
            )
        ],
    )
    out["model"]["operators"] = [turnover, coupling, polymerisation_block()]
    e = out["experiment"]
    e["turnover_controls"] = [
        dict(route_id="x_production", carrier_id=CELL, schedule=_schedule(production, "rate")),
        dict(
            route_id="x_clearance",
            carrier_id=CELL,
            schedule=_schedule([(0.0, float(a["k_X"]))], "rate"),
        ),
    ]
    e["coupling_controls"] = [dict(coupling_id=COUPLING, schedule=[dict(time=0.0, enabled=1)])]
    e["regulatory_writes"] = []
    e["polymerisation_controls"] = [
        dict(route_id="tx", schedule=_schedule([(0.0, float(a["k_I_tx"]))], "value")),
        dict(route_id="tl", schedule=_schedule([(0.0, float(a["k_I_tl"]))], "value")),
        dict(route_id="deg_R", schedule=_schedule([(0.0, float(a["k_R"]))], "value")),
        dict(route_id="deg_P", schedule=_schedule([(0.0, float(a["k_P"]))], "value")),
        dict(route_id="recharge", schedule=_schedule([(0.0, float(a["V_C"]))], "value")),
    ]
    return out
