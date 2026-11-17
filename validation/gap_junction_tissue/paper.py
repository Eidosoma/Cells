"""The preprint's experiment, its reported numbers and independent references (no engine code).

Source: J. Grodstein, J. Mathews and M. Levin, "Membrane voltage and connexin expression work
together to enhance tumor growth and metastasis in cancer", bioRxiv 10.64898/2026.09.02.748840,
version 1, posted 3 September 2026, CC-BY 4.0. Only numbers are taken (D186, D201); each entry
names where the preprint prints it. A value read off a plotted curve is marked as read, with the
reading tolerance used to compare it; the tolerances were set after the closed forms below were
evaluated, so they check the reading, not the engine. One exception to "from the preprint": the
Cx45 gate constants (CX45), which the preprint does not print (see there).

Independent references, written from the preprint's equations alone:
* `eq2`: the steady state of two linear cells joined by one junction (the preprint's equation 2);
* `chain_paper`: the chain recursion as Figure 8 applies it (the appendix's printed definition
  without its outer reciprocal, which is dimensionally inconsistent; see RECURSION_NOTE);
* `chain_physical`: the Norton conductance of a physical straight chain, by recursion;
* `linear_steady_state`: the steady state of any network of linear cells by a dense solve, the
  check on both recursions and the reference for the engine runs;
* `chen_izu`: the two-state junction gate of Figure 1 (the preprint's gating equation).
"""

import math

import numpy as np

CITATION = "Grodstein, Mathews and Levin (2026), bioRxiv 10.64898/2026.09.02.748840 v1 (CC-BY 4.0)"
DOI_URL = "https://doi.org/10.64898/2026.09.02.748840"

# --- The reported numbers ----------------------------------------------------------------------

REPORTED = {
    "vmem_mV": {
        "healthy": (-70.0, "Abstract: fully differentiated cells, roughly -70 mV"),
        "tumor": (-30.0, "Abstract: tumor cells, about -30 mV"),
        "tumor_results": (-20.0, "Results, small tumors: -70 mV rises to roughly -20 mV"),
    },
    "valence_mirna_effective": (
        -1.0,
        "Methods: Manning condensation leaves -22*0.6/0.7 = -18.8; Debye screening "
        "(a = 2.5 nm, lambda_D = 0.8 nm) gives about -0.9, approximated as -1",
    ),
    "table1": {
        "where": "Table 1 and the Results text: a 6x6x6 tumor in a 25x25x25 field; the smallest "
        "GJ diffusion constant that normalizes the tumor, found by binary search",
        "units": "1e-15 m^2/s",
        "columns": ("neither", "depol_alone", "underexp_alone", "both"),
        "rows": {
            0.3: (1.1, 38.0, 3.3, 120.0),
            0.5: (1.1, 38.0, 2.1, 75.0),
            0.8: (1.1, 38.0, 1.3, 45.0),
        },
    },
    "table2": {
        "where": "Table 2: as Table 1 column 4 ('both'), one column per tumor size NxN",
        "units": "1e-14 m^2/s",
        "sizes": (1, 2, 3, 4, 5, 6, 7, 8),
        "rows": {
            0.3: (3.8, 7.7, 11.0, 15.0, 18.0, 21.0, 23.0, 25.0),
            0.5: (2.2, 4.6, 6.9, 9.0, 11.0, 13.0, 14.0, 15.0),
            0.8: (1.4, 2.9, 4.3, 5.7, 7.0, 8.2, 9.1, 9.8),
        },
    },
    "table3": {
        "where": "Table 3: GJ_power P, tumor GJs G0*P, border GJs G0*(1+P)/2, the minimum P "
        "for invasion of the whole surrounding field; units of G0 not printed",
        "g0": (1e-16, 3e-16, 2.6e-15, 7.8e-15, 2.3e-14),
        "depol": (">100", 95.0, 45.0, 21.0, 11.0),
        "hypol": (45.0, 14.0, 4.1, 1.5, 3.3),
        "neighbor_depol": (48.0, 17.0, 6.0, 2.4, 1.4),
    },
    "figure1": {
        "where": "Figure 1: Cx45/45 relative conductance against the junction voltage (read)",
        "small_ion_peak": 0.97,
        "small_ion_floor": 0.06,
        "mirna_peak": 0.945,
        "mirna_floor": 0.0,
        "tolerance": 0.01,
    },
    "figure3b": {
        "where": "Figure 3b: two equal cells, [mR] 5 and 10 before coupling; steady [mR] "
        "against G_GJ (read at G_GJ = 1; the limit is the text's equal-weights statement)",
        "unloaded": (5.0, 10.0),
        "at_g1": (6.67, 8.33),
        "limit": 7.5,
        "tolerance": 0.05,
    },
    "figure5": {
        "where": "Figure 5 caption: cell B 1.33x cell A; final value 7.15 rather than 7.5 "
        "(the text says 1.5x; the drawn network has 4 cells against 3)",
        "size_ratio": 4.0 / 3.0,
        "unloaded": {"A": 10.0, "B": 5.0},
        "final": 7.15,
        "tolerance": 0.01,
    },
    "figure8": {
        "where": "Figure 8: chains of 1-5 cells, [mR]_UL0 = 1 mol/m^3 (read at Iexit = -0.5 "
        "mol/s, and the Iexit-axis intercepts). G_eq,1 = G_GJ = 0.1 is not printed: it is "
        "inferred from the 1- and 2-cell lines (slope and intercept)",
        "unloaded": 1.0,
        "g_eq1": 0.1,
        "g_gj": 0.1,
        "at_minus_half": (6.0, 4.33, 3.4, 2.8, 2.45),
        "intercepts": (0.10, 0.15, 0.21, 0.28, 0.35),
        "tolerance": 0.05,
        "intercept_tolerance": 0.01,
    },
}

RECURSION_NOTE = (
    "The appendix prints G_eq,n+1 = 1 / [ (G_eq,n^-1 + G_GJ^-1)^-1 + G_eq,n ]: the outer "
    "reciprocal makes it a resistance, and the second term is the whole chain's G_eq,n where the "
    "derivation adds one cell, whose own decay conductance is G_eq,1. Figure 8 plots "
    "G_eq,n+1 = (G_eq,n^-1 + G_GJ^-1)^-1 + G_eq,n (no outer reciprocal). A physical straight "
    "chain has G_eq,n+1 = (G_eq,n^-1 + G_GJ^-1)^-1 + G_eq,1, which saturates."
)

# --- Independent references --------------------------------------------------------------------


def eq2(unloaded_a, unloaded_b, x, y):
    """Equation 2: steady [mR] of cells A and B, x = G_GJ/G_eq,A and y = G_GJ/G_eq,B.

    Derived here from the two cells' balances G_eq,A (u_A - a) + G_GJ (b - a) = 0 and
    G_eq,B (u_B - b) + G_GJ (a - b) = 0. The preprint prints cell A's line in this form."""
    d = 1.0 + x + y
    a = ((1.0 + y) * unloaded_a + x * unloaded_b) / d
    b = (y * unloaded_a + (1.0 + x) * unloaded_b) / d
    return a, b


def chain_paper(g1, gj, n):
    """[G_eq,1 .. G_eq,n] by the recursion Figure 8 plots (RECURSION_NOTE)."""
    values = [g1]
    while len(values) < n:
        values.append(1.0 / (1.0 / values[-1] + 1.0 / gj) + values[-1])
    return values


def chain_physical(g1, gj, n):
    """[G_eq,1 .. G_eq,n] of a straight chain: each added cell brings its own G_eq,1."""
    values = [g1]
    while len(values) < n:
        values.append(1.0 / (1.0 / values[-1] + 1.0 / gj) + g1)
    return values


def chain_limit(g1, gj):
    """The physical chain's limit: G = G_1 + G G_GJ / (G + G_GJ)."""
    return 0.5 * (g1 + math.sqrt(g1 * g1 + 4.0 * g1 * gj))


def linear_steady_state(conductance, unloaded, edges, probes=()):
    """Steady concentrations of linear cells, by a dense solve.

    conductance[i] = G_eq,i (decay, or the Norton conductance to the cell's unloaded value);
    unloaded[i]: the cell's unloaded concentration; edges: (i, j, G_GJ); probes: (i, G, c), an
    extra conductance from cell i to a held concentration c. Returns (c, probe fluxes out of
    the cells, G (c_i - c))."""
    matrix = np.diag(np.asarray(conductance, dtype=float))
    rhs = np.asarray(conductance, dtype=float) * np.asarray(unloaded, dtype=float)
    for i, j, g in edges:
        matrix[i, i] += g
        matrix[j, j] += g
        matrix[i, j] -= g
        matrix[j, i] -= g
    for i, g, c in probes:
        matrix[i, i] += g
        rhs[i] += g * c
    c = np.linalg.solve(matrix, rhs)
    flux = [g * (c[i] - held) for i, g, held in probes]
    return c, flux


def norton_from_two_loads(points):
    """(G, u) from two (exit flux, port concentration) points of c = u - i/G."""
    (i1, c1), (i2, c2) = points
    g = (i2 - i1) / (c1 - c2)
    return g, c1 + i1 / g


# The two-state gate of Figure 1. The preprint prints the equation, not its constants. These
# values reproduce Figure 1 (peak 0.97 and floor 0.06 for small ions, peak 0.945 and floor 0 for
# miRNA), in the preprint's sign convention. Their source is the Cx45/45 row of the authors'
# public code (GJ_lib.py, BITSEY revision b2cb370, which has no licence), attributed there to
# Chen-Izu, Moreno and Spangler (2001), Am J Physiol Cell Physiol 281:C1604, the preprint's
# ref. 52. Not checked against that paper (its publisher refused the request); their use here
# awaits the lead's ruling (docs/GAP_JUNCTION_CANCER_REPLICATION.md, section 2).
CX45 = {"A1_per_V": 110.0, "V01_V": -0.0102, "A2_per_V": 110.0, "V02_V": -0.0102, "Gmax": 1.56}
CX45_SMALL_ION_GMIN = 0.06


def chen_izu(delta_v, gmin, *, a1=CX45["A1_per_V"], v01=CX45["V01_V"], a2=CX45["A2_per_V"],
             v02=CX45["V02_V"], gmax=CX45["Gmax"]):  # fmt: skip
    """G = Gmin + (Gmax - Gmin) / (1 + exp(-A1 (-dV - V01)) + exp(-A2 (dV - V02))), dV in V."""
    dv = np.asarray(delta_v, dtype=float)
    return gmin + (gmax - gmin) / (1.0 + np.exp(-a1 * (-dv - v01)) + np.exp(-a2 * (dv - v02)))
