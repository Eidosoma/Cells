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
    return _a1(dt=dt, end=end, every=every, symbols=symbols)


def _a1(*, dt, end, every, symbols, release=None):
    """A1's definition (a1); with `release`, R2's (r2): {machine, rates, dwell_s}."""
    a = sheet.A1
    symbols = test_instance() if symbols is None else symbols
    end = _f(a, "t_end") if end is None else float(end)
    rows = A1_ROWS if release is None else A1_ROWS + ("R_s",)
    start = {row: _f(a, f"c_{row}") for row in A1_ROWS}
    lengths = {"R": int(a["L_R"]), "P": int(a["L_P"])}
    if release is not None:  # R2's short-lived row: R's chemistry, at R's trace (§9.9, §9.12).
        start["R_s"] = _f(a, "c_R")
        lengths["R_s"] = lengths["R"]
    raw = _skeleton(dt=dt, end=end, every=every, start=start, volume=_f(a, "V"))
    L_R, L_P = int(a["L_R"]), int(a["L_P"])
    residues = {row: ("P_res" if row == "P" else "R_res", n) for row, n in lengths.items()}
    mu = potentials_RT(symbols, residues)
    raw = _with_registry(raw, mu, _moieties(rows, lengths))
    raw = cs.frozen_definition(raw)
    kJ = {k: symbols[k] * sheet.RT for k in ("E_pd", "E_pep")}
    chains = [_transcription("tx", "R", a["T_copies"], L_R), _translation()]
    degradations = [
        _degradation("deg_R", "R", L_R, "M", kJ["E_pd"]),
        _degradation("deg_P", "P", L_P, "A", kJ["E_pep"]),
    ]
    if release is not None:  # §9.9's addendum: tl_s on R_s, and R_s's own loss.
        chains[0]["release"] = _release(0.75, release["machine"], [0.0], [("R", "R_s")])
        chains[0]["release"]["dwell_s"] = release["dwell_s"]
        chains.append(_translation("tl_s", "R_s"))
        degradations.append(_degradation("deg_R_s", "R_s", L_R, "M", kJ["E_pd"]))
    block = _block(
        mu,
        rows,
        {"pol": a["M_pol"], "rib": a["M_rib"]},
        chains,
        degradations,
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
    if release is not None:
        rates["tl_s"] = [(0.0, _f(a, "k_I_tl"))]
        rates["deg_R"] = [(0.0, release["rates"][0])]
        rates["deg_R_s"] = [(0.0, release["rates"][1])]
    return _finish(raw, block, rates, extra_operators=(turnover, coupling), extra_controls=controls)


def r2(machine, *, fates="sheet", shrink=1, dt=0.5, end=None, every=60.0, symbols=None):
    """The sheet's R2 (§9.9, its addendum and §9.12): A1 with transcription's release at tau =
    3600/ln 2 s and p = 0.75 into R (durable) and R_s (short-lived), H(0) = 0, the fates' rates
    R1's, translation by tl on R and tl_s on R_s with A1's parameters, at a machine option.
    fates="A1" sets both fates' rates to A1's k_R and shrink divides tau: the addendum's
    development check, whose total RNA and protein approach A1's as tau shrinks."""
    a, r = sheet.A1, sheet.RELEASE
    if fates == "sheet":
        rates = (float(r["k_durable"]), float(r["k_short"]))
    elif fates == "A1":
        rates = (_f(a, "k_R"), _f(a, "k_R"))
    else:
        raise ValueError(f"fates is 'sheet' or 'A1', not {fates!r}")
    release = dict(machine=machine, rates=rates, dwell_s=float(r["tau"]) / shrink)
    return _a1(dt=dt, end=end, every=every, symbols=symbols, release=release)


def r2_names():
    """R2's runs (§9.9): each machine option."""
    return [f"R2 {machine}" for machine in ("returned", "held")]


def r2_check_names():
    """The addendum's development check: both fates at A1's k_R, tau divided by 1, 10 and 100,
    with each machine option, beside A1."""
    return [f"R2A tau/{k} {m}" for m in ("returned", "held") for k in (1, 10, 100)]


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


# ------------------------------------------------------------------ R1 (§9.9, FR-38)

RELEASE = "tx_release"
LABEL = "tx_label"
R1_ROWS = ("N", "M", "Pi", "R", "R_s")
R1_LABEL_ROWS = ("R_c2", "R_s_c2")  # Class 2's fate rows: the window's releases (§9.12).
R1_DT = 2.0  # s: dt kappa_tx = 2/3 <= 1; the hold's and fates' rates times dt are below 1e-3.
R1_EVERY = 60.0  # s: outputs every minute, the sheet's five among them (the cohort's grid).
R1_WINDOW = (0.0, 3600.0)  # The release-window cohort's [t1, t2] (§9.9).


def _release(p, machine, copies, fates, label=None):
    """Transcription's release block (§9.9): tau = 3600/ln 2 s and constant p."""
    return dict(
        id=RELEASE,
        dwell_s=float(sheet.RELEASE["tau"]),
        machine=machine,
        durable_fraction=float(p),
        fates=[dict(durable=d, short_lived=s) for d, s in fates],
        label=label,
        initial_copies=[float(c) for c in copies],
    )


def r1(
    p, *, machine="returned", blank=False, labelled=False, initiation=0.0, dt=R1_DT, symbols=None
):
    """The sheet's R1 (§9.9 and its R2 addendum), the requester's hold: one 1 pL cell with one
    chain of A1's transcription at k_I = 0, its release at tau = 3600/ln 2 s and constant p into
    the durable row R and the short-lived row R_s, H(0) = 80 copies (0 in the matched blank), M_pol
    = A1's; R and R_s at the sheet's trace c_R, each degraded at its own rate; N, M and Pi at A1's
    initial state, at a potential set (the test instance by default); outputs every R1_EVERY s to
    14,400 s. labelled: §9.8's route 1, a second class of fate rows (R_c2, R_s_c2) that the
    releases in R1_WINDOW enter, the label marking the release. initiation: transcription's k_I
    (mM^-1 s^-1), 0 in R1; the tests set A1's, so that completions arrive in the hold."""
    a, r = sheet.A1, sheet.RELEASE
    symbols = test_instance() if symbols is None else symbols
    rows = R1_ROWS + (R1_LABEL_ROWS if labelled else ())
    start = {row: _f(a, f"c_{row}") for row in ("N", "M", "Pi")}
    start |= dict.fromkeys(rows[3:], _f(a, "c_R"))
    end = float(r["t_out"][-1])
    raw = _skeleton(dt=dt, end=end, every=R1_EVERY, start=start, volume=_f(a, "V"))
    L_R = int(a["L_R"])
    polymers = {row: L_R for row in rows[3:]}
    mu = potentials_RT(symbols, {row: ("R_res", L_R) for row in polymers})
    raw = cs.frozen_definition(_with_registry(raw, mu, _moieties(rows, polymers)))
    E_pd_kJ = symbols["E_pd"] * sheet.RT
    fates = [("R", "R_s")] + ([R1_LABEL_ROWS] if labelled else [])
    label = dict(id=LABEL, at="release") if labelled else None
    chain = _transcription("tx", "R", a["T_copies"], L_R)
    chain["release"] = _release(p, machine, [0 if blank else r["H0"]], fates, label)
    rates = {"tx": [(0.0, float(initiation))]}
    degradations = []
    for row, fate in zip(rows[3:], ("k_durable", "k_short") * 2, strict=False):
        degradations.append(_degradation(f"deg_{row}", row, L_R, "M", E_pd_kJ))
        rates[f"deg_{row}"] = [(0.0, float(r[fate]))]
    block = _block(mu, rows, {"pol": a["M_pol"]}, [chain], degradations, [])
    if labelled:
        t1, t2 = R1_WINDOW
        rates[LABEL] = [(0.0, 2.0), (t2, 1.0)] if t1 == 0 else [(0.0, 1.0), (t1, 2.0), (t2, 1.0)]
    return _finish(raw, block, rates)


R1S_TIMES = (600.0, 900.0, 1800.0)  # psi's switch, p's change and the end, s.


def r1s(machine, *, dt=R1_DT, symbols=None):
    """A compiled check of the class axis labelled at completion and of a scheduled p, each changed
    mid-run (development; not one of §9.9's worlds): R1 with A1's k_I, so that completions arrive,
    its hold in two classes with class 1 holding R1's 80 copies; psi = 2 until R1S_TIMES[0], then
    1; p = 0.75 until R1S_TIMES[1], then 0.25; to R1S_TIMES[2], outputs every R1_EVERY s."""
    switch, change, end = R1S_TIMES
    k_I = _f(sheet.A1, "k_I_tx")
    raw = r1(0.75, machine=machine, labelled=True, initiation=k_I, dt=dt, symbols=symbols)
    chain = next(c for c in raw["model"]["operators"][-1]["chains"] if "release" in c)
    chain["release"].update(
        label=dict(id=LABEL, at="completion"),
        initial_copies=[float(sheet.RELEASE["H0"]), 0.0],
        durable_fraction="scheduled",
    )
    controls = raw["experiment"]["polymerisation_controls"]
    next(c for c in controls if c["route_id"] == LABEL)["schedule"] = _schedule(
        [(0.0, 2.0), (switch, 1.0)], "value"
    )
    fraction = _schedule([(0.0, 0.75), (change, 0.25)], "value")
    controls.append(dict(route_id=RELEASE, schedule=fraction))
    e = raw["experiment"]
    e["end_time"] = end
    e["observation_times"] = [t for t in e["observation_times"] if t <= end]
    raw["execution"]["max_steps"] = int(math.ceil(end / dt)) + 8
    return raw


def release_names():
    """R1's runs (§9.9): the four fractions with each machine option, the matched blanks, and the
    labelled pair of the release-window cohort's route 1 at p = 0.75."""
    out = []
    for machine in ("returned", "held"):
        out += [f"R1 p={_p(p)} {machine}" for p in sheet.RELEASE["p_cases"]]
        out += [f"R1 blank {machine}", f"R1L p=0.75 {machine}", f"R1L blank {machine}"]
    return out


def _p(value):
    return format(float(value), "g")


def _r1_world(name, dt, symbols):
    """R1's world by its name (release_names())."""
    kind, case, machine = name.split(" ")
    blank = case == "blank"
    p = 0.75 if blank else float(case.split("=")[1])
    return r1(p, machine=machine, blank=blank, labelled=kind == "R1L", dt=dt, symbols=symbols)


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
    if name.startswith(("R1 ", "R1L ")) and end is None:
        return _r1_world(name, dt, symbols)
    if name.startswith("R1S ") and end is None:
        return r1s(name.split(" ")[1], dt=dt, symbols=symbols)
    if name.startswith("R2 "):
        return r2(name.split(" ")[1], dt=dt, end=end, symbols=symbols)
    if name.startswith("R2A "):
        _, shrink, machine = name.split(" ")
        shrink = int(shrink.split("/")[1])
        return r2(machine, fates="A1", shrink=shrink, dt=dt, end=end, symbols=symbols)
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
