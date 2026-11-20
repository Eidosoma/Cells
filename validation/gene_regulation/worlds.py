"""Gene regulation's option A, its worlds for the engine (development, not judged): the sheet's A1
and A1-M's fifteen worlds, at any potential set.

Every value is the sheet's (docs/TEMPLATED_POLYMERISATION_LAWS.md, tag gr1-sheet-2026-11-20b), read
from validation/gene_regulation/sheet_check.py, whose default check holds its typed numbers to the
sheet's text. A potential set is the four symbols of §3.3 in RT units at the sheet's T, as
sheet_check.potential_sets gives them; the numeric test instance by default. The registration names
the fuel's source later (G6).

The engine's layout choices, none of them physics:
- the cell is a 1 pL node holding K+ and an impermeant anion Y- as inert background, 140 mM each;
- a patch with zero permeability faces a 1 pL bath held at 0 V, so no ion moves: the cell has no
  channels (the sheet's arms);
- the expression rows are inventory species, at the declared trace in the bath, which the
  impermeant rows can neither enter nor leave;
- the operators are templated_polymerisation@1 and, in A1, D150's turnover for the regulator X and
  B1′'s coupling of X onto transcription's initiation rate.

The worlds' names are those of the sheet's §5 as G2's interface writes them: "A1", "pol T=<T>",
"two-gene" and "rib n_R=<n>".
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
POLYMERISATION = "templated_polymerisation@1"
C0_MM = 1000.0  # The sheet's c° = 1 M, so the potentials need no shift.
BASIS = "temperature_independent"  # The sheet's kJ entries (§3.3).
A1_ROWS = ("X", "N", "M", "A", "ATP", "ADP", "Pi", "R", "P")
POL_ROWS = ("N", "M", "ATP", "ADP", "Pi", "R")
TWO_ROWS = ("N", "M", "ATP", "ADP", "Pi", "R1", "R2")
RIB_ROWS = ("A", "ATP", "ADP", "Pi", "R", "P")


def _f(table, name):
    return float(table[name])


def test_instance():
    """The numeric test instance's four symbols, in RT units (sheet_check.potential_sets)."""
    return sheet.potential_sets()["test instance"]


def potentials_RT(symbols=None, polymers=None):
    """{row: mu°/RT at 1 M} at a potential set: ADP, Pi, M and A at 0; ATP and N from the
    entries; each polymer row L times its residue's, each formed once from the exact value. polymers
    is {row: (residue, L)}, residue "R_res" or "P_res"; A1's R and P by default."""
    mu = sheet.test_instance_potentials(test_instance() if symbols is None else symbols)
    polymers = {"R": ("R_res", 1200), "P": ("P_res", 400)} if polymers is None else polymers
    out = {row: float(mu[row]) for row in ("ATP", "ADP", "Pi", "N", "M", "A")}
    for row, (residue, length) in polymers.items():
        out[row] = float(length * mu[residue])
    return out


def _identity(name):
    return dict(id=name, catalogue=None, evidence=None)


def _schedule(changes, key):
    return [{"time": float(t), key: float(v)} for t, v in changes]


def _grid(end, every):
    rows = [k * every for k in range(int(math.floor(end / every + 1e-9)) + 1)]
    if abs(rows[-1] - end) > 1e-9:
        rows.append(end)
    return rows


def _skeleton(*, dt, end, every, start, volume):
    """The inert cell, bath and patch, with the rows at their initial concentrations (mM)."""
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
            observation_times=_grid(end, every),
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
    for row, concentration in start.items():
        raw = add_inventory_species(
            raw,
            row,
            trace_mM=TRACE_mM,
            diffusivity_m2_per_s=DIFFUSIVITY,
            floor_fmol=FLOOR_FMOL,
            concentrations_mM={CELL: concentration},
        )
        raw["execution"]["material_balance_atol_fmol"][row] = 1e-16
    return raw


def _with_registry(raw, mu, moieties):
    """The rows' potentials at c0 = 1000 mM and the sheet's moieties over the world's rows (§1.4),
    so species_registry's checks read the operator's potentials, entries and moves."""
    out = copy.deepcopy(raw)
    m = out["model"]
    m["standard_concentration_mM"] = C0_MM
    for entry in m["species"]:
        if entry["id"] in mu:
            entry["standard_mu_RT"] = mu[entry["id"]]
    m["moieties"] = [dict(id=k, weights=v) for k, v in moieties.items() if v]
    return out


def _moieties(rows, lengths):
    """The sheet's four moieties restricted to the world's rows; lengths {polymer row: L}."""
    present = set(rows)

    def keep(weights):
        return {k: v for k, v in weights.items() if k in present}

    phosphorus = dict(N=3, M=1, ATP=3, ADP=2, Pi=1)
    nucleoside = dict(N=1, M=1)
    amino = dict(A=1)
    for row, length in lengths.items():
        if row == "P":
            amino[row] = length
        else:
            phosphorus[row] = length
            nucleoside[row] = length
    out = dict(
        adenine=keep(dict(ATP=1, ADP=1)),
        phosphorus=keep(phosphorus),
        nucleoside=keep(nucleoside),
        amino_acid=keep(amino),
    )
    # A moiety of one row (the rib worlds' nucleoside: R alone, held) says nothing.
    return {k: v for k, v in out.items() if len(v) > 1}


def _degradation(route, polymer, length, monomer, symbol_kJ):
    return dict(
        id=route,
        cell=CELL,
        polymer=polymer,
        residues=length,
        monomers={monomer: 1},
        standard_free_energy=dict(
            dG_kJ_mol=float(length * symbol_kJ), basis=BASIS, dG_RT_offset=0.0
        ),
    )


def _recharging(symbols):
    a = sheet.A1
    return dict(
        id="recharge",
        cell=CELL,
        stoichiometry=dict(M=-1, ATP=-2, N=1, ADP=2),
        saturation_mM=dict(M=_f(a, "K_M_rc"), ATP=_f(a, "K_ATP_rc")),
        share=2,
        standard_free_energy=dict(dG_RT=float(symbols["E_rc"])),
    )


def _transcription(route, product, copies, length, pool="pol"):
    a = sheet.A1
    return dict(
        id=route,
        pool=pool,
        template=dict(copies=int(copies)),
        product=product,
        residues=int(length),
        stages=int(a["m_tx"]),
        speed_per_s=_f(a, "v_tx"),
        draws=dict(N=1),
        releases=dict(Pi=2),
        saturation_mM=dict(N=_f(a, "K_N_tx")),
    )


def _translation(route="tl", template="R", pool="rib"):
    a = sheet.A1
    return dict(
        id=route,
        pool=pool,
        template=dict(species=template),
        product="P",
        residues=int(a["L_P"]),
        stages=int(a["m_tl"]),
        speed_per_s=_f(a, "v_tl"),
        draws=dict(A=1, ATP=4),
        releases=dict(ADP=4, Pi=4),
        saturation_mM=dict(A=_f(a, "K_A_tl"), ATP=_f(a, "K_ATP_tl")),
    )


def _block(mu, rows, pools, chains, degradations, transfers):
    """The operator's declaration over the world's rows (X excluded)."""
    return dict(
        law=POLYMERISATION,
        standard_concentration_mM=C0_MM,
        species=[dict(_identity(row), standard_mu_RT=mu[row]) for row in rows if row != "X"],
        pools=[dict(id=k, cell=CELL, machines=float(v)) for k, v in pools.items()],
        chains=chains,
        degradations=degradations,
        transfers=transfers,
    )


def _finish(raw, block, rates, *, extra_operators=(), extra_controls=None):
    out = copy.deepcopy(raw)
    out["model"]["operators"] = [*extra_operators, block]
    e = out["experiment"]
    e.update(extra_controls or {})
    e["polymerisation_controls"] = [
        dict(route_id=route, schedule=_schedule(changes, "value"))
        for route, changes in rates.items()
    ]
    return out


# ------------------------------------------------------------------ A1 (§5.1)


def a1(*, dt=0.5, end=None, every=60.0, symbols=None):
    """The sheet's A1 (§5.1): one gene, open loop, phase 1 to t_off and production of X off
    after, to `end` (the sheet's t_end by default), observed every `every` seconds."""
    a = sheet.A1
    symbols = test_instance() if symbols is None else symbols
    end = _f(a, "t_end") if end is None else float(end)
    start = {row: _f(a, f"c_{row}") for row in A1_ROWS}
    raw = _skeleton(dt=dt, end=end, every=every, start=start, volume=_f(a, "V"))
    L_R, L_P = int(a["L_R"]), int(a["L_P"])
    mu = potentials_RT(symbols, {"R": ("R_res", L_R), "P": ("P_res", L_P)})
    raw = _with_registry(raw, mu, _moieties(A1_ROWS, {"R": L_R, "P": L_P}))
    raw = cs.frozen_definition(raw)
    kJ = {k: symbols[k] * sheet.RT for k in ("E_pd", "E_pep")}
    block = _block(
        mu,
        A1_ROWS,
        {"pol": a["M_pol"], "rib": a["M_rib"]},
        [_transcription("tx", "R", a["T_copies"], L_R), _translation()],
        [
            _degradation("deg_R", "R", L_R, "M", kJ["E_pd"]),
            _degradation("deg_P", "P", L_P, "A", kJ["E_pep"]),
        ],
        [_recharging(symbols)],
    )
    t_off = _f(a, "t_off")
    production = [(0.0, _f(a, "P_on"))] + ([(t_off, 0.0)] if t_off < end else [])
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
                    operating_range=[0.0, 2.0 * _f(a, "c_X")],
                ),
                source={"species": "X"},
                law="hill_activation",
                half_saturation_mM=_f(a, "K_X"),
                hill_coefficient=_f(a, "n_X"),
                basal=_f(a, "b_X"),
            )
        ],
    )
    controls = dict(
        turnover_controls=[
            dict(route_id="x_production", carrier_id=CELL,
                 schedule=_schedule(production, "rate")),
            dict(route_id="x_clearance", carrier_id=CELL,
                 schedule=_schedule([(0.0, _f(a, "k_X"))], "rate")),
        ],
        coupling_controls=[dict(coupling_id=COUPLING, schedule=[dict(time=0.0, enabled=1)])],
        regulatory_writes=[],
    )  # fmt: skip
    rates = {
        "tx": [(0.0, _f(a, "k_I_tx"))],
        "tl": [(0.0, _f(a, "k_I_tl"))],
        "deg_R": [(0.0, _f(a, "k_R"))],
        "deg_P": [(0.0, _f(a, "k_P"))],
        "recharge": [(0.0, _f(a, "V_C"))],
    }
    return _finish(raw, block, rates, extra_operators=(turnover, coupling), extra_controls=controls)


# ------------------------------------------------------------------ A1-M (§5.2)


def polymerase_limited(T, *, dt=0.5, symbols=None, two_gene=False):
    """A1-M's polymerase-limited world at T copies, or its two-gene world: transcription, mRNA
    degradation and recharging, every polymerase free at the start, outputs every 30 s."""
    a, m = sheet.A1, sheet.A1M
    symbols = test_instance() if symbols is None else symbols
    end, every = _f(m, "t_end_pol"), 30.0
    rows = TWO_ROWS if two_gene else POL_ROWS
    start = {row: _f(a, f"c_{row}") for row in ("M", "ATP", "ADP", "Pi")}
    start["N"] = _f(m, "c_N")
    L_R = int(a["L_R"])
    if two_gene:
        genes = {"R1": ("tx1", m["T_1"], L_R), "R2": ("tx2", m["T_2"], int(m["L_2"]))}
    else:
        genes = {"R": ("tx", T, L_R)}
    for row in genes:
        start[row] = _f(a, "c_R")
    raw = _skeleton(dt=dt, end=end, every=every, start=start, volume=_f(a, "V"))
    lengths = {row: length for row, (_, _, length) in genes.items()}
    mu = potentials_RT(symbols, {row: ("R_res", length) for row, length in lengths.items()})
    raw = cs.frozen_definition(_with_registry(raw, mu, _moieties(rows, lengths)))
    E_pd_kJ = symbols["E_pd"] * sheet.RT
    suffix = {"R": "", "R1": "1", "R2": "2"}
    block = _block(
        mu,
        rows,
        {"pol": m["M_pol"]},
        [_transcription(route, row, copies, length) for row, (route, copies, length)
         in genes.items()],
        [_degradation(f"deg_R{suffix[row]}", row, length, "M", E_pd_kJ)
         for row, length in lengths.items()],
        [_recharging(symbols)],
    )  # fmt: skip
    rates = {route: [(0.0, _f(m, "k_I_tx"))] for route, _, _ in genes.values()}
    for row in genes:
        rates[f"deg_R{suffix[row]}"] = [(0.0, _f(a, "k_R"))]
    rates["recharge"] = [(0.0, _f(a, "V_C"))]
    return _finish(raw, block, rates)


def ribosome_limited(n_R, *, dt=0.5, symbols=None):
    """A1-M's ribosome-limited world: the mRNA held at n_R copies (no route writes it),
    translation and protein degradation, every ribosome free at the start, outputs every 10 s."""
    a, m = sheet.A1, sheet.A1M
    symbols = test_instance() if symbols is None else symbols
    end, every = _f(m, "t_end_rib"), 10.0
    volume = _f(a, "V")
    start = {row: _f(a, f"c_{row}") for row in ("ATP", "ADP", "Pi", "P")}
    start["A"] = _f(m, "c_A")
    start["R"] = float(n_R * sheet.COPY_FMOL) / volume
    raw = _skeleton(dt=dt, end=end, every=every, start=start, volume=volume)
    L_R, L_P = int(a["L_R"]), int(a["L_P"])
    mu = potentials_RT(symbols, {"R": ("R_res", L_R), "P": ("P_res", L_P)})
    raw = cs.frozen_definition(_with_registry(raw, mu, _moieties(RIB_ROWS, {"R": L_R, "P": L_P})))
    E_pep_kJ = symbols["E_pep"] * sheet.RT
    block = _block(
        mu,
        RIB_ROWS,
        {"rib": m["M_rib"]},
        [_translation()],
        [_degradation("deg_P", "P", L_P, "A", E_pep_kJ)],
        [],
    )
    rates = {"tl": [(0.0, _f(m, "k_I_tl"))], "deg_P": [(0.0, _f(a, "k_P"))]}
    return _finish(raw, block, rates)


def names():
    """The sixteen worlds, in G2's order."""
    return (
        ["A1"]
        + [f"pol T={T}" for T in sheet.SWEEP]
        + ["two-gene"]
        + [f"rib n_R={n}" for n in sheet.SWEEP]
    )


def world(name, *, dt=0.5, symbols=None, end=None):
    """The raw definition of a world by its name (names())."""
    if name == "A1":
        return a1(dt=dt, end=end, symbols=symbols)
    if end is not None:
        raise ValueError("only A1 takes another horizon")
    if name == "two-gene":
        return polymerase_limited(None, dt=dt, symbols=symbols, two_gene=True)
    kind, value = name.split(" ", 1)
    number = int(value.split("=")[1])
    if kind == "pol":
        return polymerase_limited(number, dt=dt, symbols=symbols)
    if kind == "rib":
        return ribosome_limited(number, dt=dt, symbols=symbols)
    raise ValueError(f"unknown world {name!r}")


def polymerisation_block(symbols=None):
    """A1's operator declaration at a potential set (the test instance by default)."""
    (block,) = [
        op for op in a1(dt=0.5, end=60.0, symbols=symbols)["model"]["operators"]
        if op["law"] == POLYMERISATION
    ]  # fmt: skip
    return block
