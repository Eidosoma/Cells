"""GJ-L1, the linear model's registered comparison: its rule, its table, its reader and its judge.

docs/GJ_LINEAR_REGISTRATION.md is the authority; this module is its arithmetic and
linear_rule.json (written by `rule`) every number. The engine's two forms of the preprint's linear
("intuitive") model (bioRxiv 10.64898/2026.09.02.748840, equations 1-2, appendix, Figures 3b, 5
and 8) are judged against code-blind references, which are read through their interface alone
(INTERFACE, schema in `interface_schema`). The reader exists at the registration's tag (D308) and
refuses any interface that does not match the registered declarations, units or keys.

**The two forms** (validation/gap_junction_tissue/run.py, worlds.py):
- NORTON: resolved_pump_tissue@3, constant_field@1 membranes and junctions for one neutral
  species, each cell's generation and decay as its Norton membrane to a held reservoir. Judged at
  the step rule's dt alone: its compared steady state is the explicit scheme's fixed point, which
  no step error moves, so its tolerance is the floor of two stated terms (transient, rounding).
- AS_WRITTEN: resolved_pump_composite@1 over @3, local_species_reactions@1 (a source and a decay
  in each cell) and passive_neutral_permeation@1 routes. Judged at dt/4 from the triple dt, dt/2,
  dt/4, by FR-25's rule (validation/gene_regulation/registration.py): the estimate
  |y(dt/2) - y(dt/4)| / (2^p - 1) at the declared order p = 2, the tolerance max(3 est, floor),
  the observed order inside [p - 0.5, 3.5] or the arm is inconclusive.

**The error terms** (each a function below, per arm, from the registered declaration and the
engine's own run alone; no reference value enters a tolerance):
- transient: A exp(-K_dec T), A = sqrt(N V_max / V_min) (max - min) / min over the arm's
  unloaded and held values; every mode decays at least at K_dec (the Norton matrix dominates
  K_dec V), and the scheme's per-step factor exceeds exp(-x) by at most x^3/6 (factor 1.01);
- rounding of the state at the fixed point: 4u (rho / (K_dec dt) + (1 + G_max)(1 + rho) + 1),
  u = 2^-53, rho = (max - min) / min, G_max the largest summed junction and probe conductance of a
  cell in units of its own G_eq: each step's rounding is damped at K_dec dt per step at least;
- the ledger's rounding: 2u N (T / S), N steps, S the averaging window (worst-case summation into a
  running total that reaches T / S times the window's transfer, at both ends of the window);
- each reference value's own declared accuracy (accuracy_rel), added to its tolerance.
The Norton floor is F_N (transient + rounding), F_N = 2.

**What is judged** per arm, against the reference of its network (MAPPING): each cell's steady
concentration; for each chain, the Norton conductance G_eq,n / G_eq,1 and the intercept from its
two loads (Figure 8, against independently derived physical balances, D219); each run's steadiness
and, in the Norton form, its probe ledger against G_probe (c - held), both against the engine's
own terms. The planted controls must fail. The preprint's printed and read values are reported
against the references as publication-target findings, never judged.

Commands (PYTHONPATH=src:. JAX_ENABLE_X64=1):
- python -m validation.gap_junction_tissue.linear_judge rule --out FILE
- python -m validation.gap_junction_tissue.linear_judge spec --out FILE  (the references' input)
- python -m validation.gap_junction_tissue.linear_judge table RUN_DIR --out FILE  (engine only)
- python -m validation.gap_junction_tissue.linear_judge judge TABLE [--retry TABLE]
  [--interface DIR] --out FILE
- python -m validation.gap_junction_tissue.linear_judge structure [--interface DIR]
"""

import argparse
import hashlib
import json
import math
from pathlib import Path

from validation.gap_junction_tissue import paper, worlds

HERE = Path(__file__).resolve().parent
RULE_FILE = HERE / "linear_rule.json"
INTERFACE = HERE / "references" / "interface"
INTERFACE_FILE = "linear.json"
REFERENCE_FORMAT = "gap_junction_tissue.linear_references@1"
REGISTRATION = "docs/GJ_LINEAR_REGISTRATION.md"
PROPOSED_TAG = "gj-linear-registered-2026-11-23"

U = 2.0**-53  # float64's unit roundoff.
F_N = 2.0  # The Norton floor's factor of safety on its two stated terms.
F_W = 3.0  # Roache's factor of safety for two grids at an assumed order (FR-25's F).
P_DECLARED = 2  # Strang's split of SSPRK(3,3) halves about @3's ARS(2,2,2) step: second order.
ORDER_WINDOW = (P_DECLARED - 0.5, 3.5)  # FR-25's [p - 0.5, 3.5]; 3.5 is SSPRK(3,3)'s 3 + 0.5.
SCHEME_FACTOR = 1.01  # The scheme's per-step factor against exp(-x): at most 1 + x^3/6 per step.
REFERENCE_ACCURACY_MAX = 1e-13  # The largest accuracy_rel a reference value may declare.
DECLARATION_MATCH = 1e-12  # Relative: the interface's echo of a declaration against the rule's.
NORTON, AS_WRITTEN = "norton", "as_written"
FRACTIONS = (1.0, 0.5, 0.25)  # The as-written triple: dt, dt/2, dt/4 (run.py's DT_STUDY).
RETRY = dict(
    fractions=(0.5, 0.25, 0.125),
    judged_fraction=0.125,
    once=True,
    arms="inconclusive as-written arms only",
    harness="a run stopped by the harness (memory, runtime limit, machine fault) is rerun once "
    "from the same snapshot; an engine refusal is a result, never rerun",
)
PLANTED_SCALE = 1.01
FIGURE3_G = (0.5, 1.0, 2.0, 5.0, 10.0, 50.0)
FIGURE5_G = (1.0, 10.0, 50.0)
AS_WRITTEN_FIGURE3_G = (0.5, 1.0, 2.0, 5.0, 10.0)
AS_WRITTEN_FIGURE5_LUMPED_G = (1.0, 10.0)
AS_WRITTEN_FIGURE5_NETWORK_G = (1.0, 10.0)  # 10 through the windowed path (run.py's WINDOWED).
FIGURE8_N = (1, 2, 3, 4, 5, 10)
FIGURE8_LOADS = (0.5, 2.0)
SIZE_RATIO = 4.0 / 3.0
FIGURE3_UNLOADED = (5.0, 10.0)
FIGURE5_UNLOADED = (10.0, 5.0)


class ComparisonError(ValueError):
    """A comparison that cannot be made as registered: a refusal, never a pass or a fail."""


# --- The registered networks -------------------------------------------------------------------


def declaration(network):
    """A worlds.Network as data the references read (no engine code): cells with their unloaded
    concentration and size (volume, and so G_eq, in units of one cell's), junctions with g =
    G_GJ / G_eq,1, probes with their held concentration and g_probe = G_probe / G_eq,1."""
    cells = [dict(id=c, unloaded=u, size=size) for c, u, size in network.cells]
    ids = [c for c, _, _ in network.cells]
    junctions = [dict(id=j, a=ids[i], b=ids[k], g=g) for j, i, k, g in network.edges]
    probes = [dict(id=p, cell=ids[i], held=h, g=g) for p, i, h, g in network.probes]
    return dict(cells=cells, junctions=junctions, probes=probes)


def networks():
    """Every registered network, by its reference id."""
    out = {}
    for g in sorted(set(FIGURE3_G) | set(AS_WRITTEN_FIGURE3_G)):
        out[f"figure3-g{g:g}"] = worlds.figure3(g, FIGURE3_UNLOADED)
    for g in FIGURE5_G:
        out[f"figure5-lumped-g{g:g}"] = worlds.figure5_lumped(g, SIZE_RATIO, FIGURE5_UNLOADED)
        out[f"figure5-network-g{g:g}"] = worlds.figure5_network(g, FIGURE5_UNLOADED)
    for n in FIGURE8_N:
        for held in FIGURE8_LOADS:
            out[f"figure8-chain{n}-held{held:g}"] = worlds.chain(n, held)
    return out


def arms():
    """Every judged arm: (engine arm id, form, reference network id, windowed, planted)."""
    out = []

    def add(arm_id, form, network_id, *, windowed=False, planted=False):
        out.append(
            dict(arm=arm_id, form=form, network=network_id, windowed=windowed, planted=planted)
        )

    for g in FIGURE3_G:
        add(f"figure3-g{g:g}", NORTON, f"figure3-g{g:g}")
    for g in FIGURE5_G:
        add(f"figure5-lumped-g{g:g}", NORTON, f"figure5-lumped-g{g:g}")
        add(f"figure5-network-g{g:g}", NORTON, f"figure5-network-g{g:g}")
    for n in FIGURE8_N:
        for held in FIGURE8_LOADS:
            add(f"figure8-chain{n}-held{held:g}", NORTON, f"figure8-chain{n}-held{held:g}")
    add("control-planted", NORTON, "figure3-g1", planted=True)
    for g in AS_WRITTEN_FIGURE3_G:
        add(f"aw-figure3-g{g:g}", AS_WRITTEN, f"figure3-g{g:g}")
    for g in AS_WRITTEN_FIGURE5_LUMPED_G:
        add(f"aw-figure5-lumped-g{g:g}", AS_WRITTEN, f"figure5-lumped-g{g:g}")
    for g in AS_WRITTEN_FIGURE5_NETWORK_G:
        add(f"aw-figure5-network-g{g:g}", AS_WRITTEN, f"figure5-network-g{g:g}", windowed=g == 10)
    for n in FIGURE8_N:
        for held in FIGURE8_LOADS:
            add(f"aw-figure8-chain{n}-held{held:g}", AS_WRITTEN, f"figure8-chain{n}-held{held:g}")
    add("aw-control-planted", AS_WRITTEN, "figure3-g1", planted=True)
    return out


def chains():
    """Every judged chain (Figure 8): its id, form, n and its two load arms."""
    out = []
    for form, prefix in ((NORTON, ""), (AS_WRITTEN, "aw-")):
        for n in FIGURE8_N:
            loads = [f"{prefix}figure8-chain{n}-held{h:g}" for h in FIGURE8_LOADS]
            out.append(dict(id=f"{prefix}figure8-chain{n}", form=form, n=n, loads=loads))
    return out


MAPPING = {
    "rule": "an engine arm is compared with the reference network named by its `network`; a "
    "chain's Norton conductance and intercept with the reference chain of its n",
    "engine to reference": "the same id without the as-written prefix 'aw-'; both planted "
    "controls with figure3-g1, the unperturbed network",
    "cells": "by id, never by position: the engine's concentrations are in its network's cell "
    "order, which the declaration lists",
}


# --- The error terms ---------------------------------------------------------------------------


def _values(network):
    return [u for _, u, _ in network.cells] + [h for _, _, h, _ in network.probes]


def rho(network):
    """(max - min) / min over the arm's unloaded and held concentrations."""
    values = _values(network)
    return (max(values) - min(values)) / min(values)


def g_max(network):
    """The largest summed junction and probe conductance of a cell, in units of its own G_eq."""
    total = [0.0] * len(network.cells)
    for _, i, j, g in network.edges:
        total[i] += g
        total[j] += g
    for _, i, _, g in network.probes:
        total[i] += g
    return max(t / size for t, (_, _, size) in zip(total, network.cells, strict=True))


def transient(network, end=worlds.END_S):
    """A exp(-K_dec T) with A = sqrt(N V_max / V_min) rho, times SCHEME_FACTOR."""
    sizes = [size for _, _, size in network.cells]
    amplitude = math.sqrt(len(sizes) * max(sizes) / min(sizes)) * rho(network)
    return SCHEME_FACTOR * amplitude * math.exp(-worlds.K_DEC_PER_S * end)


def rounding(network, dt):
    """4u (rho / (K_dec dt) + (1 + G_max)(1 + rho) + 1)."""
    r = rho(network)
    return 4.0 * U * (r / (worlds.K_DEC_PER_S * dt) + (1.0 + g_max(network)) * (1.0 + r) + 1.0)


def floor(network, dt):
    """The Norton floor of a concentration, relative: F_N (transient + rounding)."""
    return F_N * (transient(network) + rounding(network, dt))


def ledger(dt, end=worlds.END_S, window=worlds.SETTLE_S):
    """The ledger's summation rounding over the averaging window, relative: 2u N (T / S)."""
    return 2.0 * U * (end / dt) * (end / window)


def two_load(points, c_floor, i_floor):
    """(G, intercept, relative bound on G, relative bound on the intercept) from two (exit flux,
    port concentration) points, each concentration within c_floor and each flux within i_floor,
    both relative (first-order propagation)."""
    (i1, c1), (i2, c2) = points
    g, u = paper.norton_from_two_loads(points)
    di = [abs(i1) * i_floor, abs(i2) * i_floor]
    dc = [abs(c1) * c_floor, abs(c2) * c_floor]
    dg = (di[0] + di[1]) / abs(i2 - i1) + (dc[0] + dc[1]) / abs(c1 - c2)
    du = dc[0] + di[0] / abs(g) + abs(i1) * dg / abs(g)
    return g, u, dg, du / abs(u)


# --- The rule ----------------------------------------------------------------------------------


def rule():
    """The rule as data (written to linear_rule.json and tagged before any judged run)."""
    nets = networks()
    return dict(
        format="gap_junction_tissue.linear_rule@1",
        registration=REGISTRATION,
        proposed_tag=PROPOSED_TAG,
        citation=paper.CITATION,
        engine_models=dict(
            norton=["resolved_pump_tissue@3", "constant_field@1 (membranes and junctions)"],
            as_written=[
                "resolved_pump_composite@1 over resolved_pump_tissue@3",
                "local_species_reactions@1 (a zeroth-order source and a first-order decay)",
                "cells.passive_routes@1 with passive_neutral_permeation@1 (junctions and probes)",
            ],
            both=[
                "junction_voltage_relaxation@1, pinned open",
                "resolved_capacitor_components_current_continuity@1",
                f"{worlds.SOLVER} with {worlds.FIELD_SOLVER}",
            ],
        ),
        world=dict(
            radius_m=worlds.R_CELL_M,
            k_dec_per_s=worlds.K_DEC_PER_S,
            g_eq1_m3_s=worlds.G_EQ1_M3_S,
            end_s=worlds.END_S,
            settle_s=worlds.SETTLE_S,
            base_dt_s=worlds.BASE_DT_S,
            step_rule="dt = BASE_DT_S halved until dt x @3's explicit rate <= 0.04 "
            "(worlds.step); the rate is 2 max_i sum of P A / V_i",
            as_written_scale_mM=worlds.AS_WRITTEN_SCALE_mM,
            units="concentrations in the preprint's [mR] units (1 mM in the Norton form, 1 uM as "
            "written); conductances in units of one cell's G_eq,1 = V_cell K_dec",
        ),
        networks={k: declaration(v) for k, v in nets.items()},
        arms=[
            dict(
                **a,
                dt_s=worlds.step(
                    nets[a["network"]].cells, nets[a["network"]].edges, nets[a["network"]].probes
                ),  # fmt: skip
                steps=[f for f in (FRACTIONS if a["form"] == AS_WRITTEN else (1.0,))],
            )
            for a in arms()
        ],
        chains=chains(),
        mapping=MAPPING,
        error_terms=dict(
            unit_roundoff=U,
            transient="A exp(-K_dec T) x 1.01, A = sqrt(N V_max/V_min) rho",
            rounding="4u (rho/(K_dec dt) + (1 + G_max)(1 + rho) + 1)",
            ledger="2u N (T/S)",
            reference="each value's declared accuracy_rel, at most 1e-13",
        ),
        norton=dict(
            judged_step="dt (the step rule's)",
            concentration_tolerance="F_N (transient + rounding) + accuracy_rel",
            factor_of_safety=F_N,
            steady="the relative change over the last S <= F_N (transient + rounding)",
            ledger="|ledger flux - G_probe (c - held)| / |G_probe (c - held)| <= F_N ledger + 2 "
            "(c / |c - held|) F_N (transient + rounding)",
            chains="G and the intercept from the two loads, first-order propagation of the "
            "concentrations' floor and the fluxes' (ledger + the concentration's share)",
        ),
        as_written=dict(
            steps="dt, dt/2, dt/4",
            judged_step="dt/4",
            estimate="max over cells |c(dt/2) - c(dt/4)| / |c(dt/4)| / (2^p - 1), p = 2",
            order_declared=P_DECLARED,
            order_reason="Strang's split of the reactions' SSPRK(3,3) halves about @3's "
            "ARS(2,2,2) step (resolved_pump_composite@1): second order",
            tolerance="max(F_W est, floor) + accuracy_rel, F_W = 3 (Roache's two-grid factor at "
            "an assumed order, as FR-25), floor = the Norton floor at dt/4",
            factor_of_safety=F_W,
            order_window=list(ORDER_WINDOW),
            at_floor="where F_W est <= floor the arm is judged against the floor and the order "
            "check is skipped",
            chains="G and the intercept at each step from its two loads, by the same rule",
        ),
        verdicts=dict(
            arm="inconclusive if an order falls outside the window; else failed if any judged "
            "quantity exceeds its tolerance or the engine refused the run; else passed",
            plants="each planted control must fail by its gap (it ran, and its gap exceeds its "
            "tolerance); a plant that passes, is missing, refused or inconclusive makes the "
            "comparison 'instrument not validated', whatever the other arms show",
            overall="any failed arm makes the comparison failed; else any inconclusive arm makes "
            "it inconclusive; else passed (FR-25's precedence, D308)",
        ),
        retry={
            **RETRY,
            "fractions": list(RETRY["fractions"]),
            "driver": "run.py takes the triple from the step rule's dt and runs every arm: a "
            "retry needs a tagged amendment adding the finer base step and the arm filter "
            "before it runs (D308)",
        },
        plants=plant_rows(),
        reported=dict(
            publication_targets="the references' closed forms against the preprint's printed "
            "and read values (paper.REPORTED), with each value's rounding half-unit: findings, "
            "never judged",
            printed_recursion="the appendix's chain recursion, literal and read as Figure 7's "
            "resistance form, against the physical balances: a finding (D219)",
        ),
        interface=interface_schema(),
        not_blind=(
            "The registrant ran the development runs smoke-01 and dev-01 to dev-06 (17-18 "
            "November) and read their values: Norton concentrations within 2.7e-14 of the "
            "registrant's dense solve, ledgers within 5.8e-13, as written within 1.0e-5 at dt and "
            "2.5e-6 at dt/2 with orders 2.00-2.01. No tolerance is set from them: every "
            "tolerance is a stated error term's, from the declaration and the engine's own run. "
            "The references' values are not known to the registrant beyond the closed forms the "
            "preprint itself implies (equation 2, the chain's golden-ratio limit). A smoke of "
            "the registered code paths at a 20 s horizon (probes/smoke-registered-01) ran every "
            "arm. Most were far from steady, but Figure 3b and 5b at 10 and 50 G_eq were at or "
            "within a few times 1e-9 of their fixed points (no probe, so no uniform mode). For "
            "aw-figure3-g10 and aw-figure5-lumped-g10 the smoke's table printed their dt/4 "
            "tolerance (7.3e-7) and orders (2.013, 2.011), in effect the judged triple's. No "
            "engine value was compared with a reference."
        ),
    )


def plant_rows():
    """The planted failures and the effect each must show (module docstring of `plants`)."""
    return [
        dict(
            id="P-N1",
            where="engine (judged run, arm control-planted)",
            what="the Norton form of Figure 3 at G_GJ = G_eq with every junction permeability "
            "x1.01, judged against the unperturbed figure3-g1 reference",
            expected="fails: its steady state moves by 8.3e-4 of the reference, about 1e9 "
            "times its tolerance",
        ),
        dict(
            id="P-W1",
            where="engine (judged run, arm aw-control-planted)",
            what="the same plant as written, every junction route x1.01, with its own triple",
            expected="fails: 8.3e-4 against a tolerance below 1e-5",
        ),
        dict(
            id="P-R1",
            where="reader (synthetic interface, tests)",
            what="a reference concentration raised by 1e-9 of itself",
            expected="fails the Norton arm judged against it",
        ),
        dict(
            id="P-R2",
            where="reader (synthetic interface, tests)",
            what="Figure 8's printed recursion read as Figure 7's resistance form (P_res) in place "
            "of the physical balance",
            expected="fails at n >= 3 (31% at n = 3) and passes at n = 1 and 2, where the two "
            "agree",
        ),
        dict(
            id="P-R3",
            where="reader (synthetic interface, tests)",
            what="an interface whose echo of a network's declaration differs (unloaded values "
            "swapped)",
            expected="refused (ComparisonError) before any value is compared",
        ),
        dict(
            id="P-R4",
            where="reader (synthetic interface, tests)",
            what="an interface missing a registered network",
            expected="refused (ComparisonError), never passed",
        ),
        dict(
            id="P-O1",
            where="judge (synthetic triple, tests)",
            what="an as-written triple with a step-independent bias of 1e-5 and a second-order "
            "error",
            expected="fails: the order is 2, but the gap exceeds 3 est",
        ),
        dict(
            id="P-O2",
            where="judge (synthetic triple, tests)",
            what="an as-written triple converging at first order",
            expected="inconclusive: its order, 1, lies outside [1.5, 3.5]",
        ),
    ]


# --- What the references read, and the interface they write ------------------------------------

SPEC_FILE = HERE / "references" / "spec" / "linear.json"


def spec():
    """What the code-blind references read (references/spec/linear.json): the model, the networks
    and the interface, with no engine's or run's value."""
    return dict(
        format="gap_junction_tissue.linear_spec@1",
        registration=REGISTRATION,
        citation=paper.CITATION,
        model=dict(
            balance="each cell i: V_i dc_i/dt = G_eq,i (u_i - c_i) + sum over its junctions of "
            "G_GJ (c_j - c_i) + sum over its probes of G_probe (h_p - c_i), with G_eq,i = size_i "
            "G_eq,1 and V_i = size_i V_1: the preprint's equation 1 with generation K_dec u_i "
            "and decay K_dec, and its junctions (Fick, no drift)",
            steady_state="the concentrations at which every cell's right side is zero",
            chain="a straight chain of n equal cells, every junction G_GJ = G_eq,1, unloaded 1, "
            "sealed at its first cell and seen from its last (the port): its steady port "
            "concentration is u_n - i_exit / G_eq,n (the preprint's Figure 8), where i_exit "
            "leaves the port; g_eq_ratio is G_eq,n / G_eq,1 and intercept is u_n",
            units="concentrations in the preprint's [mR] units; conductances in units of "
            "G_eq,1 = V_1 K_dec; size is a cell's volume in units of V_1",
        ),
        networks={k: declaration(v) for k, v in networks().items()},
        chains=list(FIGURE8_N),
        requested=dict(
            limits="figure3: the common limit of Figure 3b's two cells (unloaded 5 and 10, equal "
            "sizes) as G_GJ grows without bound; figure5b: the same for Figure 5b's pair (A "
            "unloaded 10, size 1; B unloaded 5, size 4/3); chain: G_eq,n / G_eq,1 as n grows, "
            "at G_GJ = G_eq,1",
            printed_recursion="the appendix's chain recursion as printed (p. 15 and p. 20), "
            "G_eq,n+1 = 1 / [(G_eq,n^-1 + G_GJ^-1)^-1 + G_eq,n], at G_GJ = G_eq,1 = 1 for n = 1 "
            "to 10: 'literal' as printed, and 'resistance_form' read as Figure 7's resistance "
            "form, G_eq,n+1 = (G_eq,n^-1 + G_GJ^-1)^-1 + G_eq,n",
        ),
        interface=interface_schema(),
    )


# --- The interface the references write --------------------------------------------------------


def interface_schema():
    """The interface the code-blind references write (references/interface/linear.json)."""
    return dict(
        file=f"validation/gap_junction_tissue/references/interface/{INTERFACE_FILE}",
        format=REFERENCE_FORMAT,
        keys=dict(
            format=REFERENCE_FORMAT,
            registration="the tag the references read",
            networks="{network id: {declaration, concentrations, accuracy_rel, method}} for "
            "every network id listed under `networks`; declaration echoes that listing's "
            "{cells, junctions, probes} exactly as read; concentrations is {cell id: steady "
            "concentration} in the preprint's [mR] units",
            chains="{n: {g_eq_ratio, intercept, accuracy_rel, method}} for n in 1, 2, 3, 4, 5, "
            "10: the Norton conductance of a straight chain of n cells at G_GJ = G_eq,1 in units "
            "of G_eq,1, sealed at its far end and seen from cell n, and its open-circuit "
            "concentration (mR_UL0 = 1)",
            limits="{figure3: the two cells' common limit as G_GJ grows (unloaded 5 and 10), "
            "figure5b: the lumped model's (A unloaded 10, B 4/3 of A unloaded 5), chain: the "
            "chain's Norton conductance as n grows, in units of G_eq,1}",
            printed_recursion="{literal: [G_eq,1 .. G_eq,10], resistance_form: [...]}: the "
            "appendix's recursion taken literally (in units of G_eq,1) and read as Figure 7's "
            "resistance form, at G_GJ = G_eq,1",
        ),
        accuracy=f"every accuracy_rel at most {REFERENCE_ACCURACY_MAX:g}",
    )


def read_interface(directory=INTERFACE, rule_data=None):
    """The references' interface, checked against the rule: format, every registered network and
    chain present, each declaration echoed exactly, every cell's value present and finite, and
    every accuracy at most REFERENCE_ACCURACY_MAX. Any mismatch is refused (ComparisonError)."""
    rule_data = rule() if rule_data is None else rule_data
    path = Path(directory) / INTERFACE_FILE
    if not path.is_file():
        raise ComparisonError(f"No interface at {path}")
    data = json.loads(path.read_text())
    if data.get("format") != REFERENCE_FORMAT:
        raise ComparisonError(f"Interface format {data.get('format')!r}, not {REFERENCE_FORMAT}")
    nets = data.get("networks") or {}
    missing = sorted(set(rule_data["networks"]) - set(nets))
    if missing:
        raise ComparisonError(f"The interface lacks registered networks: {missing[:4]}")
    for net_id, declared in rule_data["networks"].items():
        entry = nets[net_id]
        _match_declaration(net_id, declared, entry.get("declaration"))
        values = entry.get("concentrations") or {}
        cells = [c["id"] for c in declared["cells"]]
        if sorted(values) != sorted(cells):
            raise ComparisonError(f"{net_id}: concentrations for {sorted(values)}, not {cells}")
        if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in values.values()):
            raise ComparisonError(f"{net_id}: a concentration is not a finite number")
        _accuracy(net_id, entry)
    chain_entries = data.get("chains") or {}
    for n in FIGURE8_N:
        entry = chain_entries.get(str(n))
        if entry is None:
            raise ComparisonError(f"The interface lacks chain n = {n}")
        for key in ("g_eq_ratio", "intercept"):
            if not isinstance(entry.get(key), (int, float)) or not math.isfinite(entry[key]):
                raise ComparisonError(f"chain {n}: {key} is not a finite number")
        _accuracy(f"chain {n}", entry)
    return data


def _accuracy(label, entry):
    a = entry.get("accuracy_rel")
    if not isinstance(a, (int, float)) or not 0.0 <= a <= REFERENCE_ACCURACY_MAX:
        raise ComparisonError(f"{label}: accuracy_rel {a!r} is not within [0, 1e-13]")


def _match_declaration(net_id, declared, echoed):
    if not isinstance(echoed, dict):
        raise ComparisonError(f"{net_id}: no echoed declaration")
    for key in ("cells", "junctions", "probes"):
        a, b = declared[key], echoed.get(key)
        if not isinstance(b, list) or len(a) != len(b):
            raise ComparisonError(f"{net_id}: the echoed {key} differ in number")
        for x, y in zip(sorted(a, key=lambda r: r["id"]), sorted(b, key=lambda r: r.get("id", "")),
                        strict=True):  # fmt: skip
            for field, value in x.items():
                other = y.get(field)
                if isinstance(value, float):
                    ok = isinstance(other, (int, float)) and abs(other - value) <= (
                        DECLARATION_MATCH * max(1.0, abs(value))
                    )
                else:
                    ok = other == value
                if not ok:
                    raise ComparisonError(
                        f"{net_id}: the echoed {key[:-1]} {x['id']}'s {field} is {other!r}, "
                        f"registered {value!r}"
                    )


def structure(directory=INTERFACE):
    """The interface's keys and value types only, never a value (D308's reading discipline)."""
    data = json.loads((Path(directory) / INTERFACE_FILE).read_text())

    def shape(x):
        if isinstance(x, dict):
            return {k: shape(v) for k, v in x.items()}
        if isinstance(x, list):
            return [shape(x[0])] if x else []
        return type(x).__name__

    return shape(data)


# --- The table: the engine's runs alone -------------------------------------------------------


def _engine_arms(results):
    """{engine arm id: its result} from run.py's results.json, both forms."""
    parts = results["parts"]
    out = {}

    def take(result):
        if isinstance(result, dict) and result.get("arm_id"):
            out[result["arm_id"]] = result

    for name in ("figure3", "figure5", "aswritten"):
        res = parts.get(name, {}).get("result", {})
        for key in ("figure3", "figure5_lumped", "figure5_network"):
            for result in res.get(key, []):
                take(result)
        take(res.get("control_planted"))
    for name in ("figure8", "aswritten"):
        for chain in parts.get(name, {}).get("result", {}).get("chains", []):
            for load in chain.get("loads", []):
                take(load)
    take(parts.get("control", {}).get("result"))
    return out


def _steps(result):
    """The engine's runs of an arm at FRACTIONS: [run at dt, at dt/2, at dt/4] (as written)."""
    steps = [dict(result, fraction=1.0)]
    for entry in result.get("dt_study") or []:
        steps.append(entry)
    return steps


def _relative(a, b, scale):
    return max(abs(x - y) / abs(s) for x, y, s in zip(a, b, scale, strict=True))


def table(results, rule_data=None):
    """The table of one judged run (run.py's results.json), from the engine alone: per arm its
    values, floors, estimates, orders and tolerances, before any reference is read."""
    rule_data = rule() if rule_data is None else rule_data
    nets = networks()
    engine = _engine_arms(results)
    rows = {}
    for a in rule_data["arms"]:
        arm_id, network = a["arm"], nets[a["network"]]
        cells = [c for c, _, _ in network.cells]
        result = engine.get(arm_id)
        row = dict(arm=arm_id, form=a["form"], network=a["network"], planted=a["planted"])
        if result is None:
            row.update(status="missing")
            rows[arm_id] = row
            continue
        runs = _steps(result) if a["form"] == AS_WRITTEN else [dict(result, fraction=1.0)]
        refused = [r for r in runs if r.get("status") != "done"]
        if a["form"] == AS_WRITTEN and len(runs) != len(FRACTIONS):
            refused.append(dict(status="missing dt study"))
        if refused:
            row.update(
                status="refused", refusals=[r.get("error", r.get("status")) for r in refused]
            )
            rows[arm_id] = row
            continue
        judged = runs[-1]
        dt = judged["dt_s"]
        values = judged["concentration_mM"]
        f = floor(network, dt)
        row.update(
            status="ready",
            cells=cells,
            dt_s=[r["dt_s"] for r in runs],
            values=dict(zip(cells, values, strict=True)),
            floor=f,
            terms=dict(transient=transient(network), rounding=rounding(network, dt)),
            steady=[dict(dt_s=r["dt_s"], change=r["steady_rel_change"],
                         bound=floor(network, r["dt_s"]),
                         ok=r["steady_rel_change"] <= floor(network, r["dt_s"])) for r in runs],
        )  # fmt: skip
        if a["form"] == NORTON:
            row.update(tolerance=f, at_floor=True, order=None, in_window=True)
            if "exit_flux_mol_s" in judged:
                c, held = judged["port_mM"], network.probes[-1][2]
                share = 2.0 * c / abs(c - held) * f
                bound = F_N * ledger(dt) + share
                row["ledger"] = dict(
                    error=judged["ledger_rel_error"],
                    bound=bound,
                    ok=judged["ledger_rel_error"] <= bound,
                )
        else:
            c0, c1, c2 = (r["concentration_mM"] for r in runs)
            d_fine, d_coarse = _relative(c1, c2, c2), _relative(c0, c1, c2)
            est = d_fine / (2**P_DECLARED - 1)
            at_floor = F_W * est <= f
            order = math.log2(d_coarse / d_fine) if d_fine > 0 and d_coarse > 0 else None
            in_window = at_floor or (
                order is not None and ORDER_WINDOW[0] <= order <= ORDER_WINDOW[1]
            )
            row.update(
                estimate=est,
                tolerance=max(F_W * est, f),
                at_floor=at_floor,
                order=order,
                in_window=in_window,
            )
        if not all(s["ok"] for s in row["steady"]) or not row.get("ledger", {}).get("ok", True):
            row["engine_checks"] = "failed"
        row["status"] = "ready" if row["in_window"] else "inconclusive"
        rows[arm_id] = row
    chain_rows = {}
    for chain in rule_data["chains"]:
        loads = [rows.get(arm) for arm in chain["loads"]]
        entry = dict(id=chain["id"], form=chain["form"], n=chain["n"], loads=chain["loads"])
        if any(r is None or r["status"] not in ("ready", "inconclusive") for r in loads):
            entry.update(status="refused")
            chain_rows[chain["id"]] = entry
            continue
        results_ = [engine[arm] for arm in chain["loads"]]
        per_step = []
        n_steps = len(FRACTIONS) if chain["form"] == AS_WRITTEN else 1
        for k in range(n_steps):
            runs = [_steps(r)[k] for r in results_]
            points = [(r["exit_flux_mol_s"], r["port_mM"]) for r in runs]
            dt = runs[0]["dt_s"]
            network = nets[f"figure8-chain{chain['n']}-held{FIGURE8_LOADS[0]:g}"]
            cf = floor(network, dt)
            share = max(
                2.0 * r["port_mM"] / abs(r["port_mM"] - h) * cf
                for r, h in zip(runs, FIGURE8_LOADS, strict=True)
            )
            g, u, dg, du = two_load(points, cf, F_N * ledger(dt) + share)
            per_step.append(
                dict(dt_s=dt, g_eq_ratio=g / worlds.G_EQ1_M3_S, intercept=u, dg=dg, du=du)
            )
        judged = per_step[-1]
        entry.update(status="ready", steps=per_step)
        for key, bound_key in (("g_eq_ratio", "dg"), ("intercept", "du")):
            if chain["form"] == NORTON:
                entry[key] = dict(value=judged[key], tolerance=judged[bound_key], at_floor=True,
                                  order=None, in_window=True)  # fmt: skip
                continue
            y0, y1, y2 = (s[key] for s in per_step)
            d_fine, d_coarse = abs(y1 - y2) / abs(y2), abs(y0 - y1) / abs(y2)
            est = d_fine / (2**P_DECLARED - 1)
            at_floor = F_W * est <= judged[bound_key]
            order = math.log2(d_coarse / d_fine) if d_fine > 0 and d_coarse > 0 else None
            in_window = at_floor or (
                order is not None and ORDER_WINDOW[0] <= order <= ORDER_WINDOW[1]
            )
            entry[key] = dict(value=y2, estimate=est, tolerance=max(F_W * est, judged[bound_key]),
                              at_floor=at_floor, order=order, in_window=in_window)  # fmt: skip
        entry["status"] = (
            "ready" if all(entry[k]["in_window"] for k in ("g_eq_ratio", "intercept"))
            else "inconclusive"
        )  # fmt: skip
        chain_rows[chain["id"]] = entry
    return dict(
        format="gap_junction_tissue.linear_table@1",
        rule_sha256=_sha256_text(json.dumps(rule_data, sort_keys=True)),
        record=results.get("record"),
        arms=rows,
        chains=chain_rows,
    )


def _sha256_text(text):
    return hashlib.sha256(text.encode()).hexdigest()


# --- The judge ---------------------------------------------------------------------------------


def judge(table_data, interface, retry=None):
    """Each arm's and chain's verdict against the references (module docstring), the plants'
    and the comparison's. retry: the table of the one finer retry, whose arms replace the
    inconclusive ones of the first table."""
    arms_ = dict(table_data["arms"])
    chains_ = dict(table_data["chains"])
    if retry is not None:
        for key, row in retry["arms"].items():
            if arms_.get(key, {}).get("status") == "inconclusive":
                arms_[key] = dict(row, retried=True)
        for key, row in retry["chains"].items():
            if chains_.get(key, {}).get("status") == "inconclusive":
                chains_[key] = dict(row, retried=True)
    nets = interface["networks"]
    verdicts = {}
    for arm_id, row in arms_.items():
        verdicts[arm_id] = _arm_verdict(row, nets.get(row["network"]))
    chain_refs = interface["chains"]
    for chain_id, row in chains_.items():
        verdicts[chain_id] = _chain_verdict(row, chain_refs.get(str(row["n"])))
    plants = {k: v for k, v in verdicts.items() if v.get("planted")}
    real = {k: v for k, v in verdicts.items() if not v.get("planted")}
    statuses = [v["status"] for v in real.values()]
    overall = (
        "failed" if "failed" in statuses
        else "inconclusive" if "inconclusive" in statuses
        else "passed"
    )  # fmt: skip
    caught = sorted(k for k, v in plants.items() if caught_by_gap(v))
    uncaught = sorted(k for k in plants if k not in caught)
    if uncaught:
        overall = "instrument not validated"
    return dict(
        format="gap_junction_tissue.linear_verdict@1",
        verdict=overall,
        plants_caught=caught,
        plants_uncaught=uncaught,
        arms=verdicts,
        reported=publication_targets(interface),
    )


def caught_by_gap(verdict):
    """A plant is caught only when it ran and its gap exceeds its tolerance: a plant that is
    missing, refused or inconclusive is not caught."""
    return (
        verdict["status"] == "failed"
        and verdict.get("reason") is None
        and verdict.get("margin", 0.0) > 1.0
    )


def _arm_verdict(row, reference):
    out = dict(arm=row["arm"], network=row["network"], planted=row["planted"])
    if row["status"] in ("missing", "refused"):
        return dict(out, status="failed", reason=row["status"], detail=row.get("refusals"))
    accuracy = reference["accuracy_rel"]
    refs = reference["concentrations"]
    gaps = {c: abs(row["values"][c] - refs[c]) / abs(refs[c]) for c in row["cells"]}
    tolerance = row["tolerance"] + accuracy
    worst = max(gaps, key=gaps.get)
    out.update(
        gaps=gaps,
        tolerance=tolerance,
        margin=gaps[worst] / tolerance,
        worst_cell=worst,
        order=row.get("order"),
        at_floor=row.get("at_floor"),
        engine_checks=row.get("engine_checks", "passed"),
    )
    if row["status"] == "inconclusive":
        return dict(out, status="inconclusive", reason="order outside the window")
    failed = gaps[worst] > tolerance or row.get("engine_checks") == "failed"
    return dict(out, status="failed" if failed else "passed")


def _chain_verdict(row, reference):
    out = dict(chain=row["id"], n=row["n"], form=row["form"], planted=False)
    if row["status"] == "refused":
        return dict(out, status="failed", reason="a load arm was refused or is missing")
    accuracy = reference["accuracy_rel"]
    failed, gaps = False, {}
    for key in ("g_eq_ratio", "intercept"):
        gap = abs(row[key]["value"] - reference[key]) / abs(reference[key])
        tolerance = row[key]["tolerance"] + accuracy
        gaps[key] = dict(gap=gap, tolerance=tolerance, margin=gap / tolerance,
                         order=row[key]["order"])  # fmt: skip
        failed = failed or gap > tolerance
    out["gaps"] = gaps
    if row["status"] == "inconclusive":
        return dict(out, status="inconclusive", reason="order outside the window")
    return dict(out, status="failed" if failed else "passed")


def publication_targets(interface):
    """The preprint's printed and read values against the references (reported, never judged).
    A printed value agrees when it is within half a unit of its last printed digit."""
    nets, limits = interface["networks"], interface.get("limits", {})
    rep = paper.REPORTED
    rows = []
    at_g1 = nets["figure3-g1"]["concentrations"]
    for cell, read in zip(("A", "B"), rep["figure3b"]["at_g1"], strict=True):
        rows.append(_printed("Figure 3b at G_GJ = G_eq, cell " + cell + " (read)", read,
                             at_g1[cell], 0.005))  # fmt: skip
    if "figure3" in limits:
        rows.append(_printed("Figure 3b's limit (the text's equal weights)",
                             rep["figure3b"]["limit"], limits["figure3"], 0.05))  # fmt: skip
    if "figure5b" in limits:
        rows.append(_printed("Figure 5's caption, final value 7.15", rep["figure5"]["final"],
                             limits["figure5b"], 0.005))  # fmt: skip
    recursion = interface.get("printed_recursion", {})
    physical = {int(n): e["g_eq_ratio"] for n, e in interface["chains"].items()}
    findings = []
    for name in ("literal", "resistance_form"):
        values = recursion.get(name) or []
        for n, value in enumerate(values, start=1):
            if n in physical:
                findings.append(dict(form=name, n=n, printed=value, physical=physical[n],
                                     relative=(value - physical[n]) / physical[n]))  # fmt: skip
    return dict(printed_values=rows, printed_recursion=findings)


def _printed(label, printed, reference, half_unit):
    return dict(
        label=label,
        printed=printed,
        reference=reference,
        difference=reference - printed,
        half_unit=half_unit,
        agrees=abs(reference - printed) <= half_unit,
    )


# --- Command line ------------------------------------------------------------------------------


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("rule").add_argument("--out", required=True)
    sub.add_parser("spec").add_argument("--out", required=True)
    t = sub.add_parser("table")
    t.add_argument("run_dir")
    t.add_argument("--out", required=True)
    j = sub.add_parser("judge")
    j.add_argument("table")
    j.add_argument("--retry")
    j.add_argument("--interface", default=str(INTERFACE))
    j.add_argument("--out", required=True)
    s = sub.add_parser("structure")
    s.add_argument("--interface", default=str(INTERFACE))
    args = parser.parse_args(argv)
    if args.command == "rule":
        out = rule()
    elif args.command == "spec":
        out = spec()
    elif args.command == "table":
        out = table(json.loads((Path(args.run_dir) / "results.json").read_text()))
    elif args.command == "structure":
        print(json.dumps(structure(args.interface), indent=1))
        return 0
    else:
        interface = read_interface(args.interface)
        retry = json.loads(Path(args.retry).read_text()) if args.retry else None
        out = judge(json.loads(Path(args.table).read_text()), interface, retry)
    Path(args.out).write_text(json.dumps(out, indent=1, allow_nan=False) + "\n")
    print(out.get("verdict", out["format"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
