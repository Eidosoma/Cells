"""FR-45's declared worlds (SPEC.md §2), transcribed once as the literals written there.

Each world's table rows are rebuilt below from the same literal strings the numbers come
from, and ``check_against_spec`` requires every rebuilt row to occur verbatim in that
world's section of SPEC.md. A transcription slip therefore stops the run instead of
reaching a reference file.

The capacity S_s = alpha*nu*N/N_f is taken as the binary64 nearest to the exact value of
those binary64 inputs (one rounding); ``capacity`` also reports whether plain left-to-right
binary64 evaluation gives the same number.
"""

from __future__ import annotations

from fractions import Fraction

from fr45ref_hp import D, lit

NU = "ν"
ALPHA = "α"
MICRO = "µ"

# SPEC §0, exact.
N_F = 602214076  # sites per fmol
N_A_TEXT = "6.02214076e23"
K_B_TEXT = "1.380649e-23"
T_TEXT = "310"
TRACE_MM_TEXT = "1e-12"
STANDARD_MM_TEXT = "1"

CONSTANT_ROWS = [
    "N_f = 602,214,076 sites per fmol, exact",
    "N_A = 6.02214076 × 10²³ per mol",
    "k_B = 1.380649 × 10⁻²³ J/K",
    "the temperature T = 310 K",
    "RT = 10⁻³·R·T pJ/fmol",
    "the standard concentration is 1 mM",
    "A trace is 10⁻¹² mM",
]


def gas_constant_RT():
    """RT in pJ/fmol: 1e-3 * N_A * k_B * T, exact in decimal."""
    return D("1e-3") * D(N_A_TEXT) * D(K_B_TEXT) * D(T_TEXT)


def capacity(alpha: float, nu: int, copies: float) -> tuple[float, bool]:
    exact = Fraction(alpha) * nu * Fraction(copies) / N_F
    s = float(exact)  # correctly rounded
    naive = alpha * nu * copies / N_F
    return s, naive == s


# --------------------------------------------------------------------------------------
# World literals. Each builder returns (world, {spec section: [rows]}).


def _pop(pid, set_id, ligand, kon, koff, occ):
    return {
        "id": pid,
        "set": set_id,
        "ligand": ligand,
        "k_on": kon,
        "k_off": koff,
        "occupancy": occ,
    }


def _w1_literals():
    return dict(
        V="1.0",
        n1="1.6e-3",
        n2="0.9e-3",
        N="1445314.0",
        nu="1",
        alpha="1.0",
        kon1="1.2e3",
        koff1="0.9",
        occ1="0.0",
        kon2="5.0e2",
        koff2="0.15",
        occ2="0.0",
        dt="0.008",
    )


def _w1_base(times, horizon):
    L = _w1_literals()
    world = {
        "nodes": [{"id": "well", "kind": "node", "V": L["V"]}],
        "ligands": ["L1", "L2"],
        "free": [
            {"ligand": "L1", "node": "well", "n": L["n1"]},
            {"ligand": "L2", "node": "well", "n": L["n2"]},
        ],
        "sets": [
            {
                "id": "matrix",
                "owner": "node well",
                "faces": "well",
                "copies": L["N"],
                "sites_per_copy": L["nu"],
                "accessible_fraction": L["alpha"],
            }
        ],
        "populations": [
            _pop("matrix_L1", "matrix", "L1", L["kon1"], L["koff1"], L["occ1"]),
            _pop("matrix_L2", "matrix", "L2", L["kon2"], L["koff2"], L["occ2"]),
        ],
        "dt": [L["dt"]],
        "times": times,
        "horizon": horizon,
        "wash": None,
    }
    rows = [
        f"| Node `well` | V = {L['V']} pL |",
        f"| Free L1, L2 at `well` | {L['n1']} fmol, {L['n2']} fmol |",
        f"| Set `matrix` (owner: node `well`) | "
        f"N = {L['N']} copies, {NU} = {L['nu']}, {ALPHA} = {L['alpha']} |",
        f"| Population `matrix_L1` | "
        f"L1; k_on {L['kon1']}; k_off {L['koff1']}; initial occupancy {L['occ1']} |",
        f"| Population `matrix_L2` | "
        f"L2; k_on {L['kon2']}; k_off {L['koff2']}; initial occupancy {L['occ2']} |",
        f"| dt | {L['dt']} s |",
    ]
    return world, rows


def world_W1():
    times = ["0.2", "0.4", "0.8", "1.6", "3.2", "6.4", "12.8", "25.6", "51.2"]
    world, rows = _w1_base(times, "51.2")
    rows += [f"| Observation times | {', '.join(times)} s |", "| Horizon | 51.2 s |"]
    world.update(id="W1", title="one node-owned set, two ligands, from empty sites")
    return world, {"W1": rows}


def world_W1eq_inputs():
    """W1eq before its start is written: W1's inputs with W1eq's times (SPEC §2)."""
    times = ["0.8", "4.0", "8.0"]
    world, rows = _w1_base(times, "8.0")
    world.update(id="W1eq", title="W1 started at its equilibrium")
    own = [
        f"| Observation times | {', '.join(times)} s |",
        "| Horizon | 8.0 s |",
        "| Everything else | as in W1 |",
    ]
    return world, {"W1": rows, "W1eq": own}


def world_W1p():
    times = ["0.2", "0.4", "0.8", "1.6", "3.2", "6.4"]
    world, rows = _w1_base(times, "6.4")
    world.update(id="W1p", title="W1 cut to 6.4 s, for the plants")
    own = [
        f"| Observation times | {', '.join(times)} s |",
        "| Horizon | 6.4 s |",
        "| Everything else | as in W1 |",
    ]
    return world, {"W1": rows, "W1p": own}


def world_W2():
    L = dict(
        V="1.0e6",
        n1="50.0",
        n2="1.0e-6",
        N="15055351900.0",
        nu="1",
        alpha="1.0",
        kon1="1.2e4",
        koff1="0.6",
        occ1="0.5",
        kon2="1.5e4",
        koff2="0.12",
        occ2="0.0",
        tw="4.0",
        f="0.5",
        cb1="1.0e-12",
        cb2="1.6e-4",
        dt="0.0125",
    )
    times = ["2.0", "4.0", "4.0125", "5.0", "7.5", "10.0", "20.0", "40.0", "60.0", "75.0"]
    world = {
        "id": "W2",
        "title": "bind, wash and unbind",
        "nodes": [{"id": "well", "kind": "node", "V": L["V"]}],
        "ligands": ["L1", "L2"],
        "free": [
            {"ligand": "L1", "node": "well", "n": L["n1"]},
            {"ligand": "L2", "node": "well", "n": L["n2"]},
        ],
        "sets": [
            {
                "id": "matrix",
                "owner": "node well",
                "faces": "well",
                "copies": L["N"],
                "sites_per_copy": L["nu"],
                "accessible_fraction": L["alpha"],
            }
        ],
        "populations": [
            _pop("matrix_L1", "matrix", "L1", L["kon1"], L["koff1"], L["occ1"]),
            _pop("matrix_L2", "matrix", "L2", L["kon2"], L["koff2"], L["occ2"]),
        ],
        "dt": [L["dt"]],
        "times": times,
        "horizon": "75.0",
        "wash": {
            "t": L["tw"],
            "node": "well",
            "f": L["f"],
            "buffer": [{"ligand": "L1", "c": L["cb1"]}, {"ligand": "L2", "c": L["cb2"]}],
        },
    }
    rows = [
        f"| Node `well` | V = {L['V']} pL (1 {MICRO}L) |",
        f"| Free L1 at `well` | {L['n1']} fmol |",
        f"| Free L2 at `well` | at its trace: {L['n2']} fmol |",
        f"| Set `matrix` (owner: node `well`) | "
        f"N = {L['N']} copies, {NU} = {L['nu']}, {ALPHA} = {L['alpha']} |",
        f"| Population `matrix_L1` | "
        f"L1; k_on {L['kon1']}; k_off {L['koff1']}; initial occupancy {L['occ1']} |",
        f"| Population `matrix_L2` | "
        f"L2; k_on {L['kon2']}; k_off {L['koff2']}; initial occupancy {L['occ2']} |",
        f"| The wash | t = {L['tw']} s, node `well`, f = {L['f']}; "
        f"buffer L1 {L['cb1']} mM, L2 {L['cb2']} mM |",
        f"| dt | {L['dt']} s |",
        f"| Observation times | {', '.join(times)} s |",
        "| Horizon | 75.0 s |",
    ]
    return world, {"W2": rows}


def _w3_base(times, horizon):
    L = dict(
        V="1.0",
        n1="2.0e-3",
        n2="1.5e-3",
        n3="1.0e-3",
        Vc="1.0",
        n4="1.0e-3",
        n5="2.0e-3",
        NA="2000000.0",
        nuA="2",
        aA="0.75",
        NB="1000000.0",
        nuB="1",
        aB="0.6",
        NC="1500000.0",
        nuC="1",
        aC="1.0",
        dt="0.004",
    )
    P = {
        "A_L1": ("A", "L1", "2.0e3", "2.0", "0.2"),
        "A_L2": ("A", "L2", "1.0e3", "0.5", "0.1"),
        "A_L3": ("A", "L3", "2.0e3", "0.4", "0.0"),
        "B_L2": ("B", "L2", "3.0e3", "0.3", "0.05"),
        "C_L4": ("C", "L4", "1.0e3", "1.0", "0.0"),
        "C_L5": ("C", "L5", "2.0e3", "0.4", "0.0"),
    }
    world = {
        "nodes": [
            {"id": "well", "kind": "node", "V": L["V"]},
            {"id": "specimen", "kind": "cell", "V": L["Vc"]},
        ],
        "patches": [{"id": "specimen_face", "inside": "specimen", "outside": "well"}],
        "ligands": ["L1", "L2", "L3", "L4", "L5"],
        "free": [
            {"ligand": "L1", "node": "well", "n": L["n1"]},
            {"ligand": "L2", "node": "well", "n": L["n2"]},
            {"ligand": "L3", "node": "well", "n": L["n3"]},
            {"ligand": "L4", "node": "specimen", "n": L["n4"]},
            {"ligand": "L5", "node": "specimen", "n": L["n5"]},
        ],
        "sets": [
            {
                "id": "A",
                "owner": "node well",
                "faces": "well",
                "copies": L["NA"],
                "sites_per_copy": L["nuA"],
                "accessible_fraction": L["aA"],
            },
            {
                "id": "B",
                "owner": "node well",
                "faces": "well",
                "copies": L["NB"],
                "sites_per_copy": L["nuB"],
                "accessible_fraction": L["aB"],
            },
            {
                "id": "C",
                "owner": "patch specimen_face, inside face",
                "faces": "specimen",
                "copies": L["NC"],
                "sites_per_copy": L["nuC"],
                "accessible_fraction": L["aC"],
            },
        ],
        "populations": [_pop(pid, *v) for pid, v in P.items()],
        "dt": [L["dt"]],
        "times": times,
        "horizon": horizon,
        "wash": None,
    }

    def row(pid):
        s, lig, kon, koff, occ = P[pid]
        return f"`{pid}`: {lig}, k_on {kon}, k_off {koff}, occupancy {occ}"

    rows = [
        f"| Node `well` | V = {L['V']} pL; free L1 {L['n1']}, L2 {L['n2']}, L3 {L['n3']} fmol |",
        f"| Cell `specimen` | V = {L['Vc']} pL; free L4 {L['n4']}, L5 {L['n5']} fmol |",
        f"| Set `A` (owner: node `well`) | N = {L['NA']}, {NU} = {L['nuA']}, {ALPHA} = {L['aA']} |",
        f"| Populations on `A` | {row('A_L1')}. {row('A_L2')}. {row('A_L3')} |",
        f"| Set `B` (owner: node `well`; one population) | "
        f"N = {L['NB']}, {NU} = {L['nuB']}, {ALPHA} = {L['aB']} |",
        f"| Population on `B` | {row('B_L2')} |",
        f"| Set `C` (owner: patch `specimen_face`, inside face, facing `specimen`) | "
        f"N = {L['NC']}, {NU} = {L['nuC']}, {ALPHA} = {L['aC']} |",
        f"| Populations on `C` | {row('C_L4')}. {row('C_L5')} |",
        f"| dt | {L['dt']} s |",
        "The patch `specimen_face` has `specimen` inside and `well` outside.",
    ]
    return world, rows


def world_W3():
    times = ["0.1", "0.2", "0.5", "1.0", "2.0", "4.0", "8.0", "16.0", "30.0"]
    world, rows = _w3_base(times, "30.0")
    rows += [f"| Observation times | {', '.join(times)} s |", "| Horizon | 30.0 s |"]
    world.update(
        id="W3",
        title="a set with three ligands, a second set at the same node, and a set inside a cell",
    )
    return world, {"W3": rows}


def world_W3p():
    times = ["0.1", "0.2", "0.5", "1.0", "2.0"]
    world, rows = _w3_base(times, "2.0")
    world.update(id="W3p", title="W3 cut to 2 s, for the plants")
    own = [
        "W3's inputs, with observation times 0.1, 0.2, 0.5, 1.0 and 2.0 s and a horizon of 2.0 s."
    ]
    return world, {"W3": rows, "W3p": own}


def world_W4():
    L = dict(
        V="1.0e9",
        n1="1.2e6",
        n2="0.8e6",
        N="1445314.0",
        nu="1",
        alpha="1.0",
        kon1="1.2e3",
        koff1="0.9",
        occ1="0.0",
        kon2="5.0e2",
        koff2="0.15",
        occ2="0.0",
    )
    dts = ["0.08", "0.04", "0.02"]
    times = ["0.4", "0.8", "1.2", "1.6"]
    world = {
        "id": "W4",
        "title": "fixed concentrations, and the engine's order",
        "nodes": [{"id": "vat", "kind": "node", "V": L["V"]}],
        "ligands": ["L1", "L2"],
        "free": [
            {"ligand": "L1", "node": "vat", "n": L["n1"]},
            {"ligand": "L2", "node": "vat", "n": L["n2"]},
        ],
        "sets": [
            {
                "id": "matrix",
                "owner": "node vat",
                "faces": "vat",
                "copies": L["N"],
                "sites_per_copy": L["nu"],
                "accessible_fraction": L["alpha"],
            }
        ],
        "populations": [
            _pop("matrix_L1", "matrix", "L1", L["kon1"], L["koff1"], L["occ1"]),
            _pop("matrix_L2", "matrix", "L2", L["kon2"], L["koff2"], L["occ2"]),
        ],
        "dt": dts,
        "times": times,
        "horizon": "1.6",
        "wash": None,
    }
    rows = [
        f"| Node `vat` | V = {L['V']} pL (1 mL); free L1 {L['n1']} fmol, L2 {L['n2']} fmol |",
        f"| Set `matrix` (owner: node `vat`) | "
        f"N = {L['N']}, {NU} = {L['nu']}, {ALPHA} = {L['alpha']} |",
        f"| Populations | `matrix_L1`: L1, k_on {L['kon1']}, k_off {L['koff1']}, "
        f"occupancy {L['occ1']}. "
        f"`matrix_L2`: L2, k_on {L['kon2']}, k_off {L['koff2']}, occupancy {L['occ2']} |",
        f"| dt | three runs: {dts[0]}, {dts[1]} and {dts[2]} s |",
        f"| Observation times | {', '.join(times)} s |",
        "| Horizon | 1.6 s |",
    ]
    return world, {"W4": rows}


def world_W5():
    L = dict(
        V="1.0",
        n1="1.0e-3",
        n2="1.0e-3",
        N="602.0",
        nu="1",
        alpha="1.0",
        kon1="6.0e3",
        koff1="0.1",
        occ1="0.0",
        kon2="6.0e3",
        koff2="0.1",
        occ2="0.0",
        dt="0.1",
    )
    world = {
        "id": "W5",
        "title": "the stage condition's edge",
        "nodes": [{"id": "well", "kind": "node", "V": L["V"]}],
        "ligands": ["L1", "L2"],
        "free": [
            {"ligand": "L1", "node": "well", "n": L["n1"]},
            {"ligand": "L2", "node": "well", "n": L["n2"]},
        ],
        "sets": [
            {
                "id": "matrix",
                "owner": "node well",
                "faces": "well",
                "copies": L["N"],
                "sites_per_copy": L["nu"],
                "accessible_fraction": L["alpha"],
            }
        ],
        "populations": [
            _pop("matrix_L1", "matrix", "L1", L["kon1"], L["koff1"], L["occ1"]),
            _pop("matrix_L2", "matrix", "L2", L["kon2"], L["koff2"], L["occ2"]),
        ],
        "dt": [L["dt"]],
        "times": [],
        "horizon": "1.0",
        "wash": None,
    }
    rows = [
        f"| Node `well` | V = {L['V']} pL; free L1 {L['n1']}, L2 {L['n2']} fmol |",
        f"| Set `matrix` (owner: node `well`) | "
        f"N = {L['N']}, {NU} = {L['nu']}, {ALPHA} = {L['alpha']} |",
        f"| Populations | `matrix_L1`: L1, k_on {L['kon1']}, k_off {L['koff1']}, "
        f"occupancy {L['occ1']}. "
        f"`matrix_L2`: L2, k_on {L['kon2']}, k_off {L['koff2']}, occupancy {L['occ2']} |",
        f"| dt | {L['dt']} s |",
        "| Horizon | 1.0 s |",
    ]
    return world, {"W5": rows}


def world_W6():
    L = dict(
        V="1.0",
        n1="1.5e-3",
        n2="1.0e-3",
        N="1204428.0",
        nu="1",
        alpha="0.8",
        kon1="1.5e3",
        koff1="0.75",
        occ1="0.1",
        kon2="1.0e3",
        koff2="1.0",
        occ2="0.05",
        dt="0.00625",
    )
    times = ["0.25", "0.5", "1.0", "2.0", "4.0", "8.0", "16.0", "25.0"]
    world = {
        "id": "W6",
        "title": "a set on a patch's outside face, from a partial occupancy",
        "nodes": [{"id": "well", "kind": "node", "V": L["V"]}],
        "ligands": ["L1", "L2"],
        "free": [
            {"ligand": "L1", "node": "well", "n": L["n1"]},
            {"ligand": "L2", "node": "well", "n": L["n2"]},
        ],
        "sets": [
            {
                "id": "D",
                "owner": "patch specimen_face, outside face",
                "faces": "well",
                "copies": L["N"],
                "sites_per_copy": L["nu"],
                "accessible_fraction": L["alpha"],
            }
        ],
        "populations": [
            _pop("D_L1", "D", "L1", L["kon1"], L["koff1"], L["occ1"]),
            _pop("D_L2", "D", "L2", L["kon2"], L["koff2"], L["occ2"]),
        ],
        "dt": [L["dt"]],
        "times": times,
        "horizon": "25.0",
        "wash": None,
    }
    rows = [
        f"| Node `well` | V = {L['V']} pL; free L1 {L['n1']}, L2 {L['n2']} fmol |",
        f"| Set `D` (owner: patch `specimen_face`, outside face, facing `well`) | "
        f"N = {L['N']}, {NU} = {L['nu']}, {ALPHA} = {L['alpha']} |",
        f"| Populations | `D_L1`: L1, k_on {L['kon1']}, k_off {L['koff1']}, occupancy {L['occ1']}. "
        f"`D_L2`: L2, k_on {L['kon2']}, k_off {L['koff2']}, occupancy {L['occ2']} |",
        f"| dt | {L['dt']} s |",
        f"| Observation times | {', '.join(times)} s |",
        "| Horizon | 25.0 s |",
    ]
    return world, {"W6": rows}


def _w7_literals():
    return dict(
        V="1.0",
        n1="8.0",
        n2="4.0",
        N="3613284456.0",
        S="6.0",
        nu="1",
        alpha="1.0",
        kon1="1.0",
        koff1="12.0",
        occ1="0.3333333333333333",
        kon2="0.25",
        koff2="3.0",
        occ2="0.16666666666666666",
        tw="1.0",
        f="0.5",
        cb1="1.0e-12",
        cb2="8.0",
        dt="0.005",
    )


def _w7_set_row(L):
    return (
        f"| Set `matrix` (owner: node `well`) | "
        f"N = {L['N']} copies (S = {L['S']} fmol), {NU} = {L['nu']}, {ALPHA} = {L['alpha']} |"
    )


def _w7_pop_row(L, n):
    return (
        f"| Population `matrix_L{n}` | "
        f"L{n}; k_on {L[f'kon{n}']}; k_off {L[f'koff{n}']}; initial occupancy {L[f'occ{n}']} |"
    )


def world_W7():
    """W7, the user's example washed (AMENDMENT-2-2026-11-24.md). ``stated`` holds the facts
    SPEC.md states about its start, as the literals written there, for the build to check."""
    L = _w7_literals()
    stated = dict(
        S="6.0",
        B_start={"matrix_L1": "2.0", "matrix_L2": "1.0"},
        R_start="3.0",
        K_mM="12",
        removed_at_start={"L1": "4.0", "L2": "2.0"},
        supplied_at_start={"L2": "4.0"},
        rows_before_wash=["0.5", "1.0"],
        first_row_after_wash="1.005",
    )
    times = ["0.5", "1.0", "1.005", "1.5", "2.0", "3.0", "5.0", "8.0", "12.0"]
    world = {
        "id": "W7",
        "title": "the user's example, washed",
        "nodes": [{"id": "well", "kind": "node", "V": L["V"]}],
        "ligands": ["L1", "L2"],
        "free": [
            {"ligand": "L1", "node": "well", "n": L["n1"]},
            {"ligand": "L2", "node": "well", "n": L["n2"]},
        ],
        "sets": [
            {
                "id": "matrix",
                "owner": "node well",
                "faces": "well",
                "copies": L["N"],
                "sites_per_copy": L["nu"],
                "accessible_fraction": L["alpha"],
            }
        ],
        "populations": [
            _pop("matrix_L1", "matrix", "L1", L["kon1"], L["koff1"], L["occ1"]),
            _pop("matrix_L2", "matrix", "L2", L["kon2"], L["koff2"], L["occ2"]),
        ],
        "dt": [L["dt"]],
        "times": times,
        "horizon": "12.0",
        "wash": {
            "t": L["tw"],
            "node": "well",
            "f": L["f"],
            "buffer": [{"ligand": "L1", "c": L["cb1"]}, {"ligand": "L2", "c": L["cb2"]}],
        },
        "stated": stated,
    }
    B1, B2 = stated["B_start"]["matrix_L1"], stated["B_start"]["matrix_L2"]
    rem = stated["removed_at_start"]
    rows = [
        f"| Node `well` | V = {L['V']} pL |",
        f"| Free L1 (the example's A), L2 (its B) at `well` | {L['n1']} fmol, {L['n2']} fmol |",
        _w7_set_row(L),
        _w7_pop_row(L, 1),
        _w7_pop_row(L, 2),
        f"| The wash | t = {L['tw']} s, node `well`, f = {L['f']}; "
        f"buffer L1 {L['cb1']} mM, L2 {L['cb2']} mM |",
        f"| dt | {L['dt']} s |",
        f"| Observation times | {', '.join(times)} s |",
        "| Horizon | 12.0 s |",
        f"B = {B1} and {B2} fmol, and R = {stated['R_start']} fmol.",
        f"Both K are {stated['K_mM']} mM, so B_b/R_s = c_l/K_b holds at the start.",
        "Both of §1.2's net fluxes are 0.0 in binary64.",
        f"**The row at {L['tw']} s holds the state the wash acts on.** "
        f"{stated['first_row_after_wash']} s is the first row after it.",
        f"removes exactly {rem['L1']} fmol of L1 and {rem['L2']} fmol of L2, and supplies\n"
        f"  {stated['supplied_at_start']['L2']} fmol of L2.",
    ]
    return world, {"W7": rows}


def world_W7s():
    """W7s, W7's single-ligand limit: L1 alone on W7's sites, from W7's occupancy, no wash.
    L2 is absent (SPEC.md: moved by no law, so left out), so the world has one ligand."""
    L = _w7_literals()
    times = ["0.5", "1.0", "2.0", "3.0", "5.0", "8.0", "12.0"]
    world = {
        "id": "W7s",
        "title": "W7's single-ligand limit",
        "nodes": [{"id": "well", "kind": "node", "V": L["V"]}],
        "ligands": ["L1"],
        "free": [{"ligand": "L1", "node": "well", "n": L["n1"]}],
        "sets": [
            {
                "id": "matrix",
                "owner": "node well",
                "faces": "well",
                "copies": L["N"],
                "sites_per_copy": L["nu"],
                "accessible_fraction": L["alpha"],
            }
        ],
        "populations": [_pop("matrix_L1", "matrix", "L1", L["kon1"], L["koff1"], L["occ1"])],
        "dt": [L["dt"]],
        "times": times,
        "horizon": "12.0",
        "wash": None,
    }
    own = [
        f"| Node `well` | V = {L['V']} pL; free L1 {L['n1']} fmol |",
        "| Set `matrix` (owner: node `well`) | as W7 |",
        "| Population `matrix_L1` | as W7, the set's only population |",
        f"| dt | {L['dt']} s |",
        f"| Observation times | {', '.join(times)} s |",
        "| Horizon | 12.0 s |",
        "**L2 is absent.**",
    ]
    return world, {"W7": [_w7_set_row(L), _w7_pop_row(L, 1)], "W7s": own}


BUILDERS = {
    "W1": world_W1,
    "W1p": world_W1p,
    "W2": world_W2,
    "W3": world_W3,
    "W3p": world_W3p,
    "W4": world_W4,
    "W5": world_W5,
    "W6": world_W6,
    "W7": world_W7,
    "W7s": world_W7s,
}


def _sections(spec_text: str) -> dict[str, str]:
    """World id -> the text of its '### Wn:' section of SPEC.md §2."""
    out = {}
    lines = spec_text.split("\n")
    current = None
    buf: list[str] = []
    for line in lines:
        if line.startswith("### ") or line.startswith("## "):
            if current is not None:
                out[current] = "\n".join(buf)
            current = None
            buf = []
            if line.startswith("### W") and ":" in line:
                current = line[4 : line.index(":")].strip()
        if current is not None:
            buf.append(line)
    if current is not None:
        out[current] = "\n".join(buf)
    return out


def check_against_spec(spec_text: str) -> list[str]:
    """Every rebuilt row must occur verbatim in its world's section; returns the rows checked."""
    sections = _sections(spec_text)
    checked = []
    for row in CONSTANT_ROWS:
        if row not in spec_text:
            raise ValueError(f"SPEC.md lacks the constant row: {row!r}")
        checked.append(row)
    builders = dict(BUILDERS)
    builders["W1eq"] = world_W1eq_inputs
    for wid in ("W1", "W1eq", "W1p", "W2", "W3", "W3p", "W4", "W5", "W6", "W7", "W7s"):
        _, rows = builders[wid]()
        for section, section_rows in rows.items():
            if section not in sections:
                raise ValueError(f"SPEC.md has no section for {section}")
            for row in section_rows:
                if row not in sections[section]:
                    raise ValueError(f"{wid}: SPEC.md section {section} lacks the row {row!r}")
                checked.append(f"{section}: {row}")
    return checked


def numeric(world: dict) -> dict:
    """The world with its literal strings turned into binary64 (and ints for sites per copy)."""
    w = {k: v for k, v in world.items()}
    w["nodes"] = [{"id": n["id"], "kind": n["kind"], "V": lit(n["V"])} for n in world["nodes"]]
    w["free"] = [
        {"ligand": f["ligand"], "node": f["node"], "n": lit(f["n"])} for f in world["free"]
    ]
    sets = []
    for s in world["sets"]:
        nu = int(s["sites_per_copy"])
        if str(nu) != s["sites_per_copy"]:
            raise ValueError("sites per copy is an integer")
        alpha = lit(s["accessible_fraction"])
        copies = lit(s["copies"])
        S, naive_same = capacity(alpha, nu, copies)
        sets.append(
            {
                "id": s["id"],
                "owner": s["owner"],
                "faces": s["faces"],
                "copies": copies,
                "sites_per_copy": nu,
                "accessible_fraction": alpha,
                "S": S,
                "S_naive_binary64_same": naive_same,
            }
        )
    w["sets"] = sets
    w["populations"] = [
        {
            "id": p["id"],
            "set": p["set"],
            "ligand": p["ligand"],
            "k_on": lit(p["k_on"]),
            "k_off": lit(p["k_off"]),
            "occupancy": lit(p["occupancy"]),
        }
        for p in world["populations"]
    ]
    w["dt"] = [lit(x) for x in world["dt"]]
    w["times"] = [lit(x) for x in world["times"]]
    w["horizon"] = lit(world["horizon"])
    w["time_texts"] = list(world["times"])
    w["dt_texts"] = list(world["dt"])
    w["horizon_text"] = world["horizon"]
    if world.get("wash"):
        wsh = world["wash"]
        w["wash"] = {
            "t": lit(wsh["t"]),
            "t_text": wsh["t"],
            "node": wsh["node"],
            "f": lit(wsh["f"]),
            "buffer": [{"ligand": b["ligand"], "c": lit(b["c"])} for b in wsh["buffer"]],
        }
    else:
        w["wash"] = None
    return w


def steps(t_text: str, dt_text: str) -> int:
    """k_t = t/dt as an exact integer from the decimal literals (refuses a non-integer)."""
    q = Fraction(t_text) / Fraction(dt_text)
    if q.denominator != 1:
        raise ValueError(f"{t_text}/{dt_text} is not a whole number of steps")
    return int(q)
