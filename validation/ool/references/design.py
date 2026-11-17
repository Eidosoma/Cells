"""The registered OL1 reference design, as one machine-readable file (``designs/ol1_design.json``).

It is generated from the constants the reference modules use, so the file and the code cannot
drift (a test holds the committed copy byte-equal to this generator's output). The magnitudes
of the planted controls are the reference's own outputs on the registered inputs, recorded here
when the design was registered and re-derived by the tests.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import closed_world, ledger, mass_action, probes, ssa_oracle
from .common import ALPHA, MIN_POWER
from .detailed_balance import TOL_FACTOR
from .registered import REGISTERED_ON, WB_RUNGS
from .world import CONVENTION_MENU, REFUSED_TOKENS

DESIGN_FILE = "ol1_design.json"
PROBED_CONVENTIONS = (
    {"condensed_measure": "multinomial", "last_molecule": "kept"},
    {"condensed_measure": "multinomial_less_one", "last_molecule": "extinct"},
)
LEDGER_RUN = {"world": "ol1_wa", "max_events": 2000, "t_end_s": 60.0, "row_every_events": 100,
              "diagnostic": True, "fission": "none (no fission threshold is reached, or none declared)"}
RESCALE_RUN = {"worlds": ["ol1_wa_closed", "ol1_wa_closed_x2"], "events": 500, "shared_stream": True}

# Planted-control magnitudes on the registered inputs (the reference's outputs, 17 November 2026,
# under both probed conventions; evidence in the staging folder's evidence/ directory).
REGISTERED_MAGNITUDES = {
    "OL1-1": {
        "check": "the largest |residual| of the named check over the registered probe, under (multinomial, kept); "
                 "re-derived at amendment 4 on the amended law and the 592-state probe",
        "honest": {"kolmogorov": 2.7e-15, "identity": 1.4e-15},
        "at_state_factor": {"kolmogorov": 0.0074, "identity": 1.39},
        "forward_only_catalysis": {"kolmogorov": 0.057, "identity": 0.92},
        "one_sided": {"kolmogorov": 0.061, "identity": 0.40},
        "wrong_sign": {"identity": 10.6},
        "dropped_c0": {"identity": 6.91, "forward_form": 6.91},
        "power_propensity": {"forward_form": 0.693},
        "normaliser_power": {"forward_form": 1.5},
        "extent_offset": {"forward_form": 0.693, "note": "an error under c = 0 only; under c = 1 it is the rule"},
        "other_measure": {"identity": 0.693},
        "wrong_last_molecule_token": {"reverse_rates": "zero pattern differs at the boundary states"},
        "empty_m_zero": {"forward_form": "zero-pattern mismatch at 3 entries (reference rates >= 0.5 per s)"},
        "singular_as_zero": {"forward_form": "one singular-pattern mismatch, and one in the reverse rates, under "
                                             "multinomial_less_one"},
    },
    "OL1-2": {
        "check": "total variation of the planted table's stationary law from exp(-F)/Z on ol1_wa_closed",
        "at_state_factor": 0.083,
        "forward_only_catalysis": 0.30,
        "one_sided": 0.0079,
        "dropped_c0": 0.997,
        "wrong_sign": 0.997,
        "other_measure": 0.035,
    },
    "OL1-4b": {"family_power_at_R_2000": {"power_propensity": 0.998, "dropped_c0": 1.0, "wrong_sign": 1.0,
                                          "coefficient": 1.0, "biased_selection": 1.0}},
    "design_e1": {"tv": closed_world.E1_TV, "worst_cycle_ratio": str(closed_world.E1_WORST_CYCLE)},
    "design_e2": {"tv": closed_world.E2_TV, "worst_cycle_ratio": str(closed_world.E2_WORST_CYCLE)},
}


def design_document() -> dict:
    return {
        "format": "ool_references.design@1",
        "milestone": "OL1",
        "registered": REGISTERED_ON,
        "design_note": "docs/ORIGIN_OF_LIFE_ENGINE_DESIGN.md: §0.1, §0.2a (the lead's rulings, amended 17 November "
                       "2026: the last molecule's rate is the pair rule in its cancelled form, in either direction), "
                       "§2.1-2.4, §3.3, §7.1-7.2",
        "statistics": {"alpha": ALPHA, "min_power": MIN_POWER},
        "conventions": {
            "menu": {k: list(v) for k, v in CONVENTION_MENU.items()},
            "refused": {k: list(v) for k, v in REFUSED_TOKENS.items()},
            "pairing": {"reversible": "multinomial only", "extinct": "multinomial_less_one only"},
            "probed": list(PROBED_CONVENTIONS),
            "covered_by_the_references": "all four admissible (condensed_measure, last_molecule) pairs",
            "rule": "every bundle and probe declares every token; a missing or unknown token is refused (status 2)",
        },
        "amendments": [
            {"date": "2026-11-17", "after_commit": "08870ef6", "before_engine_output": True,
             "what": "world ol1_boundary and its probe states (role boundary_probe, row OL1-1): §0.2a's extinct "
                     "rule in the forward direction; anti-parallel two-cycles added to the Kolmogorov check",
             "why": "ol1_wa reaches the extinct boundary only through the reverse of a join"},
            {"date": "2026-11-17", "after_commit": "08870ef6", "before_engine_output": True,
             "what": "the harness enforces the registered sizes: 2,000 runs per rung (row OL1-4b) and 500 events "
                     "per rescale run (row OL1-3b), as it does the ledger run's 2,000 events",
             "why": "a smaller submission would otherwise be judged at a power the design never registered"},
            {"date": "2026-11-17", "after_commit": "d17e05c9", "before_engine_output": True,
             "what": "the harness requires every per-pair role to hold exactly the two probed convention pairs, once "
                     "each, and the ledger run to save the registered rows (every 100 events, and the last)",
             "why": "one pair alone, or a ledger run that saves row 0 only, would otherwise pass vacuously"},
            {"date": "2026-11-17", "after_commit": "2d69c118 (main d3d58d8e merged)", "before_engine_output": True,
             "what": "amendment 4: (a) §0.2a as amended: the cancelled form wherever the membrane factor is 0/0, "
                     "under every last_molecule token, and kept zeroing only pairs with an empty end state; the "
                     "kernel probe gains each membrane step's reactant-only and product-only states (592 states); "
                     "the superseded reading is planted (empty_m_zero). (b) §0.2b rule 8: world_role = probe on the "
                     "worlds holding r4 (ol1_wa, ol1_wa_closed and its two variants); a tenth refusal; the probe's "
                     "expectation is +inf at r4's singular pair under multinomial_less_one. (c) runs declare an "
                     "end_reason, and a registered run that ends stalled fails its row",
             "why": "the lead's rulings of 17 November (§0.2a amended; §0.2b rule 8)"},
        ],
        "worlds": {
            "registered": ["ol1_wa", "ol1_wa_closed", "ol1_wa_closed_uncatalysed", "ol1_wa_closed_x2",
                           "ol1_boundary"]
            + [f"ol1_wb_m{M}" for M in WB_RUNGS],
            "refusals": "designs/refusals/*.world.json: each must be refused at parse",
            "files": "designs/<id>.world.json",
        },
        "rows": {
            "OL1-1": {
                "claim": "every channel keeps local detailed balance (§0.1, §7.1)",
                "role": "kernel_probe; boundary_probe (amendment)",
                "world": "ol1_wa; ol1_boundary (amendment)",
                "inputs": {"seed": probes.KERNEL_PROBE_SEED, "bases": probes.KERNEL_PROBE_BASES,
                           "max_count": probes.KERNEL_PROBE_MAX_COUNT,
                           "states": "probes.kernel_probe_states (written by make-probes; echoed by the engine)"},
                "checks": ["Kolmogorov on every registered square and two-cycle (convention-free)",
                           "ln a-(n') - ln a+(n) = F(n') - F(n) - w under the declared tokens",
                           "reverse rates equal the reference's (the extinct boundary's continued form included)"],
                "tolerance": f"{TOL_FACTOR:g} u (8 + Sum|ln a|) per cycle; {TOL_FACTOR:g} u (4 + |ln a+| + |ln a-| "
                             "+ |DeltaF|) per edge",
                "planted": ["at_state_factor", "forward_only_catalysis", "one_sided (r3's reverse times "
                            "exp(x_D), lam = 1)", "wrong_sign", "dropped_c0", "the other measure",
                            "a literal zero for the last molecule's rate under extinct",
                            "empty_m_zero (amendment 4)", "zero for +inf at the singular pair (amendment 4)"],
                "registered_magnitudes": REGISTERED_MAGNITUDES["OL1-1"],
            },
            "OL1-2": {
                "claim": "a closed world relaxes to exp(-F/k_BT) (§7.1)",
                "role": "closed_world",
                "world": "ol1_wa_closed",
                "inputs": {"states": "probes.closed_world_states from the world's initial state (387 states)"},
                "checks": ["exact edge identity in the reference (RatExp)",
                           "the engine table's stationary law against exp(-F)/Z",
                           "Kolmogorov on every square of the closed world"],
                "tolerance": {"total_variation": closed_world.TV_ATOL},
                "planted": ["at_state_factor", "one_sided", "forward_only_catalysis", "dropped_c0", "wrong_sign"],
                "registered_magnitudes": {k: v for k, v in REGISTERED_MAGNITUDES["OL1-2"].items()},
                "reproduced_design_probes": {"E1": REGISTERED_MAGNITUDES["design_e1"],
                                             "E2": REGISTERED_MAGNITUDES["design_e2"]},
            },
            "OL1-3": {
                "claim": "catalysis is kinetic only (§2.4, §7.1)",
                "roles": ["closed_world (with and without catalysts)", "rescale_pair"],
                "worlds": ["ol1_wa_closed", "ol1_wa_closed_uncatalysed", "ol1_wa_closed_x2"],
                "rescale_run": RESCALE_RUN,
                "checks": ["both closed-world tables relax to exp(-F)/Z",
                           "identical channel sequence, times exactly halved (bitwise)"],
                "planted": ["forward_only_catalysis", "the factor on forward channels only"],
            },
            "OL1-4": {
                "claim": "mass action with registry potentials (§2.1, §7.1)",
                "a_forward_form": {"role": "kernel_probe", "check": "a+ equals k g(m) E(m) theta+(n) under the "
                                   "declared tokens", "planted": ["power_propensity", "normaliser_power",
                                                                  "extent_offset", "dropped_c0"]},
                "b_large_system": {"role": "wb_ensemble", "worlds": [f"ol1_wb_m{M}" for M in WB_RUNGS],
                                   "runs_per_rung": mass_action.ENSEMBLE_RUNS, "t_end_s": 2.0,
                                   "observation_times_s": list(mass_action.OBSERVATION_TIMES),
                                   "cut": "the state after the last event at or before each time",
                                   "streams": "independent, one per run; none shared",
                                   "null": "the exact master-equation mean on each rung (not the ODE)",
                                   "test": "two-sided z on each mean, Bonferroni over 16 (z = 4.003)",
                                   "planted": list(mass_action.PLANTED_ENSEMBLE),
                                   "family_power": REGISTERED_MAGNITUDES["OL1-4b"]["family_power_at_R_2000"]},
                "c_exact_ssa": {"role": "ledger_run (diagnostic)", "conventions": {"tau": ssa_oracle.TAU_NEG_LOG_U1,
                                "select": ssa_oracle.SELECT_FIRST_PREFIX_GT}, "tie_rtol": ssa_oracle.TIE_RTOL,
                                "time_rtol": ssa_oracle.TIME_RTOL,
                                "planted": [f"reverse channels selected at {ssa_oracle.PLANTED_REVERSE_WEIGHT} of "
                                            "their weight"]},
                "d_moieties": {"roles": ["refusals", "ledger_run"], "checks": ["each registered refusal refused",
                               "every moiety conserved at every row, held exchange counted from the trace"]},
            },
            "OL1-5": {
                "claim": "the ledgers for reactions close: F(n_t) - F(n_0) = W_t - Q_t at every row (§3.3)",
                "role": "ledger_run",
                "run": LEDGER_RUN,
                "tolerance": "2 [16 u E (1 + L) + gamma_E (Sum|q| + Sum|w|) + 4 u (|F_t| + |F_0|)] (ledger.py)",
                "planted": ["a heat sign error", "the reservoir work dropped"],
                "note": ledger.__name__,
            },
            "OL1-6": {
                "claim": "streams: bitwise replay; distinct identities share no uniforms (§7.1)",
                "roles": ["ledger_run", "replay", "other_stream"],
                "planted": ["a reused key"],
            },
        },
    }


CONVENTIONS_FILE = "ol1_conventions.json"
KERNEL_PROBE_FILE = "ol1_kernel_probe_states.json"
CLOSED_WORLD_FILE = "ol1_closed_world_states.json"
BOUNDARY_PROBE_FILE = "ol1_boundary_probe_states.json"
BOUNDARY_MAX_A = 5

TOKEN_MEANINGS = {
    "free_energy_form": {"discrete": "F uses ln n! exactly (the exact kernel's only form)",
                         "continuum": "Stirling's n ln n - n: refused by the exact kernel"},
    "condensed_measure": {"multinomial": "c = 0: -ln N! + Sum ln n_i!",
                          "multinomial_less_one": "c = 1: -ln (N - 1)! + Sum ln n_i!, G1's measure; 0 at N = 0"},
    "membrane_kinetics": {"count_on_m": "membrane activities prod ff(n_i, a_i)/ff(N - c, r) at the firing "
                                        "state; extent N(m) - c + 1 on the common state m"},
    "lumen_volume": {"declared": "the lumen's volume_L is a constant (no lumen in OL1's registered worlds)"},
    "empty_catalyst_phase": {"uncatalysed": "g = 1 where the membrane (the only catalysing phase) is empty at m"},
    "last_molecule": {"kept": "rate zero only for a pair one of whose end states has an empty membrane (amendment "
                              "4, §0.2a as amended): the membrane never empties and nothing else is frozen",
                      "reversible": "c = 0 only: the empty membrane is an ordinary state",
                      "extinct": "c = 1 only: a channel whose result empties the membrane fires at the pair rule's "
                                 "cancelled form, 1/ff(N - 1, r - 1) for E(m)/ff(N - 1, r), in either direction "
                                 "(k- for the last molecule's leave); it is one-way, and a literal zero is an error"},
}

EMPTY_COMMON_STATE = ("§0.2a as amended (amendment 4): wherever the membrane factor E(m)/ff(N - c, r) is 0/0 - the "
                      "common state's membrane is empty while neither end state's is (a lone molecule changing form, two "
                      "joining), or under extinct a channel whose result empties the membrane - it takes its continuous "
                      "extension 1/ff(N - 1, r - 1), under every last_molecule token; detailed balance holds there")
SINGULAR_RATE = ("§0.2b rule 8 (amendment 4): under multinomial_less_one a step with a membrane place on both sides "
                 "is +inf at N = r and is admitted only in a world declaring world_role = probe (optional key, only "
                 "value probe); there the probe reports +inf, and a run that reaches it stops with end_reason stalled, "
                 "which fails its row")


def conventions_document() -> dict:
    """The closed menu of declared conventions, the file the engine side is given."""
    return {
        "format": "ool_references.conventions@1",
        "registered": REGISTERED_ON,
        "authority": "docs/ORIGIN_OF_LIFE_ENGINE_DESIGN.md §0.2a (the lead's rulings for OL1, D215, amended "
                     "17 November 2026); token names as the OL1 family's draft format declares them",
        "rule": "every run bundle and probe declares every key below, with one token each; a missing key, an "
                "unknown token or a refused token makes the harness exit with status 2; there are no defaults",
        "menu": {k: list(v) for k, v in CONVENTION_MENU.items()},
        "refused": {k: list(v) for k, v in REFUSED_TOKENS.items()},
        "pairing": {"last_molecule=reversible": "condensed_measure=multinomial only",
                    "last_molecule=extinct": "condensed_measure=multinomial_less_one only"},
        "meanings": TOKEN_MEANINGS,
        "phases": {"membrane": "condensed: count_on_m; the only catalysing phase in OL1",
                   "pool, lumen": "dilute: mass action scaled by X = N_A V c0 (activity ff(n, a)/X^a, extent X)"},
        "probed_pairs": list(PROBED_CONVENTIONS),
        "covered_pairs": "all four admissible (condensed_measure, last_molecule) pairs",
        "empty_common_state": EMPTY_COMMON_STATE,
        "singular_rate": SINGULAR_RATE,
        "world_role": {"key": "optional", "values": ["probe"]},
        "end_reason": "every run declares one; the registered runs end at their registered event count "
                      "('max_events'); any other end, 'stalled' included, fails the run's row",
    }


def kernel_probe_document() -> dict:
    from .registered import registered_world

    w = registered_world("ol1_wa")
    states = probes.kernel_probe_states(w)
    return {"format": "ool_references.probe_states@1", "registered": REGISTERED_ON, "world": "ol1_wa",
            "places": [p.name for p in w.finite], "steps": [st.name for st in w.steps],
            "generator": {"function": "probes.kernel_probe_states", "seed": probes.KERNEL_PROBE_SEED,
                          "bases": probes.KERNEL_PROBE_BASES, "max_count": probes.KERNEL_PROBE_MAX_COUNT},
            "report": "a_plus[state, step] (rate of state -> state + nu) and a_minus[state, step] (rate of "
                      "state -> state - nu), zero where impossible, with these states echoed",
            "count": int(len(states)), "states": [[int(v) for v in s] for s in states]}


def closed_world_document() -> dict:
    from .registered import registered_world

    w = registered_world("ol1_wa_closed")
    states = probes.closed_world_states(w, w.initial_state)
    return {"format": "ool_references.probe_states@1", "registered": REGISTERED_ON,
            "worlds": ["ol1_wa_closed", "ol1_wa_closed_uncatalysed"],
            "places": [p.name for p in w.finite], "steps": [st.name for st in w.steps],
            "generator": {"function": "probes.closed_world_states", "from": "the world's initial_state"},
            "report": "a_plus and a_minus at every listed state, for each of the two worlds",
            "count": int(len(states)), "states": [[int(v) for v in s] for s in states]}


def boundary_probe_document() -> dict:
    """Amendment, 17 November 2026: the boundary world's probe states, A@membrane = 0..5."""
    from .registered import registered_world

    w = registered_world("ol1_boundary")
    states = [[a] for a in range(BOUNDARY_MAX_A + 1)]
    return {"format": "ool_references.probe_states@1", "registered": REGISTERED_ON, "amendment": True,
            "world": "ol1_boundary", "places": [p.name for p in w.finite], "steps": [st.name for st in w.steps],
            "generator": {"function": "A@membrane = 0..5"},
            "report": "a_plus and a_minus at every listed state (as the kernel probe)",
            "count": len(states), "states": states}


def canonical_bytes(doc: dict) -> bytes:
    return json.dumps(doc, indent=1).encode()


def write_design(out_dir) -> list[Path]:
    """Write the design, the convention menu and the probe-state files into out_dir."""
    out = []
    for name, doc in ((DESIGN_FILE, design_document()), (CONVENTIONS_FILE, conventions_document()),
                      (KERNEL_PROBE_FILE, kernel_probe_document()), (CLOSED_WORLD_FILE, closed_world_document()),
                      (BOUNDARY_PROBE_FILE, boundary_probe_document())):
        p = Path(out_dir) / name
        p.write_bytes(canonical_bytes(doc))
        out.append(p)
    return out
