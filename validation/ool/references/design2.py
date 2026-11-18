"""The registered OL2 and OL3 reference design, as one machine-readable file
(``designs/ol2_ol3_design.json``), generated from the constants the reference modules use.

The planted controls' magnitudes are the references' own outputs on the registered inputs
(18 November 2026, before any engine output; evidence in the staging folder's ``evidence/``:
``ol2_ol3_margins.py``/``.json``/``.out`` and ``ol2_ol3_coverage.py``/``.json``/``.out``), re-derived
in part by the tests.
"""

from __future__ import annotations

from pathlib import Path

from . import ol2_checks as OC
from . import population as P
from . import registered2 as R2
from .common import ALPHA, MIN_POWER
from .harness2 import COVERAGE, END_REASON, ROWS, RUN_OF_ROW

DESIGN_FILE = "ol2_ol3_design.json"

REGISTERED_MARGINS = {
    "OL2-1": {
        "check": "the named check's largest residual over the registered probe (both encounter tokens unless named); "
                 "tolerances: forward form 1e-12, identity and cycle closure 1e-8, geometry 1e-12, tension 1e-9",
        "honest": {"kolmogorov": 4.3e-14, "identity": 7.1e-15, "forward_form": 0.0, "geometry": 0.0},
        "extent_on_target": {"forward_form": 0.001},
        "radius_for_area": {"forward_form": 17.2, "note": "insertion_area only; the same form under diffusion_radius"},
        "dropped_c0": {"forward_form": 6.91},
        "no_lumen_term": {"identity": 72.8, "failing_edges": 442},
        "lumen_sign": {"identity": 146.0},
        "wrong_sign": {"identity": 167.0, "failing_edges": 918},
        "floor_all_steps": {"forward_form": "53 zero-pattern mismatches"},
        "aL_double": {"identity": 72.8, "forward_form": 0.693, "geometry_A": 1.0},
        "laplace_double": {"forward_form": "1852 lysis-flag mismatches", "geometry_tension": 0.552},
        "sphere_constant": {"identity": 40.7, "geometry_V_sph": 0.436},
        "no_m3_to_L": {"forward_form": "5326 lysis-flag mismatches", "geometry_V_sph": 0.999},
        "impermeants_only": {"identity": 6.7, "geometry_V_osm": 1.0},
    },
    "OL2-2": {
        "check": "total variation of the table's stationary law from exp(-F)/Z; tolerance 1e-7",
        "honest": {"ol2_closed": 1.3e-11, "ol2_two": 1.6e-11},
        "no_lumen_term": {"ol2_closed": 0.0696, "ol2_two": 0.510},
        "lumen_sign": {"ol2_closed": 0.990, "ol2_two": 1.0},
        "wrong_sign": {"ol2_closed": 1.0, "ol2_two": 1.0},
        "aL_double": {"ol2_closed": 0.0696, "ol2_two": 0.510},
        "sphere_constant": {"ol2_closed": 0.999, "ol2_two": 1.0},
        "no_m3_to_L": {"ol2_closed": 0.999, "ol2_two": 1.0},
    },
    "runs": {
        "check": "the honest replay of a planted stand-in trace (same uniforms): the first difference, and closure",
        "flat_select": {"rows": ["OL2-4", "OL3-2"], "caught_by": "replay (channel choice)"},
        "counter_not_advanced": {"rows": ["OL3-2", "OL3-3", "OL3-4"], "caught_by": "replay and streams"},
        "no_discard": {"rows": ["OL3-2", "OL3-3", "OL3-4"], "caught_by": "replay (a crossing draw fired)"},
        "transfer_largest": {"rows": ["OL3-2"], "caught_by": "replay (kept set)"},
        "transfer_skip_when_all_kept": {"rows": ["OL3-2"], "caught_by": "replay and streams (no draws at t = 2 s)"},
        "gap_one_minus": {"rows": ["OL3-2"], "caught_by": "replay (shear times)"},
        "admission_one_over_k": {"rows": ["OL3-2", "OL3-3", "OL3-4", "OL3-5"], "caught_by": "replay (attempts)"},
        "floor_on_parent": {"rows": ["OL3-2", "OL3-3", "OL3-4"], "caught_by": "replay (a split the floor refuses)"},
        "birth_lysis_kept": {"rows": ["OL3-3"], "caught_by": "replay (a daughter beyond sigma_max kept alive)"},
        "slots_highest": {"rows": ["OL3-2", "OL3-3"], "caught_by": "replay (daughters' slots)"},
        "transfer_fresh_to_sink": {"rows": ["OL3-2"], "caught_by": "replay (sink -37.1 against -1259.4 k_BT); closure "
                                                                   "holds, as the planted form keeps it"},
        "old_pool_not_sunk": {"rows": ["OL3-2"], "caught_by": "replay and closure (residual 4.45e3 k_BT)"},
        "closure_added_again": {"rows": ["OL3-2", "OL3-3", "OL3-4"],
                                "caught_by": "replay ((k - 1) C_close = 125.7 or 251.3 k_BT per fission) and closure"},
        "closure_not_released": {"rows": ["OL2-3", "OL3-3"], "caught_by": "replay (heat off by C_close = 125.7 k_BT) "
                                                                         "and closure"},
        "release_work_omitted": {"rows": ["OL2-3", "OL3-3"], "caught_by": "replay (heat and reservoir work); closure "
                                                                         "holds, as the planted form keeps it"},
        "no_lumen_term, dropped_c0, wrong_sign": {"rows": ["every run row"], "caught_by": "replay (times or choices)"},
        "closure_tolerance": "1e-9 of the run's F scale (3.5e-4 to 1.1e-3 k_BT); honest residuals 7e-12 to 1.2e-10",
    },
    "coverage": {
        "check": "the share of honest stand-in runs (200 seeds each) that exercise what their row needs "
                 "(harness2.COVERAGE) and end as registered",
        "ol2_shared_run": "200/200", "ol2_lysis_run": "200/200", "ol3_population_run": "200/200",
        "ol3_shear_probe_run": "200/200", "ol3_lineage_run": "200/200", "ol3_slots_full_run": "200/200",
        "birth_lysis_per_parent": 0.90, "birth_lysis_none_in_eight": 1e-8,
    },
    "OL3-1": {
        "check": "family power at M = 4000 attempts per parent, alpha 1e-3 over 12 tests",
        "g1_sizes": 1.0, "no_pi": 1.0, "lumen_by_area": 1.0, "lumen_equal": 1.0,
        "largest_c": "replay only (eq_N7_k2 and uneq_N5_k2: 5 mismatches each in the stand-in)",
        "lumen_z_planted": "-17.7 to -51.7 (by area), -54 to -194 (equal shares), critical 3.93",
    },
}

ZERO_POWER = [
    "radius_for_area under diffusion_radius: the two forms coincide there (OL2-1 holds it under insertion_area).",
    "The stationary rows (OL2-2) cannot see kinetic-only forms (extent_on_target, radius_for_area, dropped_c0, "
    "floor_all_steps), the Laplace factor (tension is not in F) or the permeants' count (no permeant in the closed "
    "worlds); OL2-1 holds each.",
    "Cycle closure alone passes any reverse derived from some F (wrong_sign, no_lumen_term); the identity row holds "
    "them.",
    "C3x's tie rule (ties_last): uniform ties have probability zero.",
    "C3x's smallest minimiser (largest_c): no distributional power, since pi randomises the order; replay holds it "
    "where |k S_c - t W| ties (N odd at k = 2).",
    "G1's sizes and the missing pi at N mod k = 0 with equal areas (eq_N6_k3): the same law.",
    "The lumen weights at equal daughter areas: every p_j is 1/k.",
    "The nextafter guard of the two-level map: it acts only when u a0 rounds to a0 (about 2^-53 per draw).",
    "Which daughter takes which slot: the daughters are exchangeable under pi; the replay follows the recorded map "
    "when its slot set is either reading (the parent's slot and the lowest free, or the lowest of the free and the "
    "parent's).",
    "Which daughter a single lineage follows (G1's daughter_continuation@1, recorded as fission_followed and "
    "required) and the daughters' carrier keys (the relations rule, read from the lives table): taken from the "
    "record; the checks are per key.",
    "Implemented as §0.2d 10 rules them, but not exercised by the registered runs: two scheduled events at one time, a "
    "declared time equal to t_end, daughters not re-tested in the event that made them, a total rate of zero with a "
    "schedule pending (no draw), and a shear's stress test (none is declared).",
    "The finite pool's c_ext drift (§0.2c rule 6): reported by the engine, not checked.",
    "The uniforms' own distribution in domains 1, 5 and 6: the replays check the maps from uniforms to events, and "
    "OL1's ensemble rows the generator; OL3-1's laws test domain 2's block draws end to end.",
    "Threefry's partitionability (§0.2d 9): only the environment record's flag is checked; block-size invariance is "
    "not observable from saved uniforms.",
    "Labels (§0.2d 8): out of the references.",
    "Lysis through a pool step: impossible, a pool step changes no vesicle.",
    "Whether a birth lysis is booked in the fission's ledger row or its own: the totals are the same (the shear work "
    "is the split's exact Delta F), and the rows compare the attempt's totals.",
]

READINGS = [
    "Ruled as §0.2d item 10 (c8b22371, 18 November 2026; the builder confirmed all seven): a shear event's set is "
    "fixed at its start, in slot order, its daughters not tested again; simultaneous events apply in schedule-index "
    "order, each to the assemblies alive at its own start; a declared time equal to t_end applies, a later one never.",
    "Ruled (10.2): an attempt runs the stress test, v <= k^(-1/2), the k - 1 free slots (population; else "
    "slots_full), the draw (rule 9's uniforms, then rule 10's), the split and the floor test, then applies or refuses; "
    "the fission counter counts draws.",
    "Ruled (10.3): every daughter counts as born, for the shear work (its F at its own V, with its closure cost) and "
    "for keys; each takes its slot before any birth lysis, which then frees the slot and is booked as a lysis, "
    "q = -(F(after release) - F(as born)) + w.",
    "Ruled (10.4): the first Poisson shear time is t_1 = -ln(u_0)/lambda from t = 0; the gaps follow lazily, one per "
    "scheduled shear.",
    "Ruled (10.5): the diagnostic record holds every draw with its address, uniforms and fate (discarded draws, the "
    "draw that ends the run, a gap past t_end, every transfer uniform, each partition block's used prefix), and each "
    "event's changes and ledger terms by payer; OL1's event_uniforms (committed events only) is not enough.",
    "Ruled (10.6): every counter starts at 0 (domains 5, 1 at each assembly's birth, 2 and 6); a new sub-lineage's "
    "key follows the relations rule and is read from the lives table.",
    "Ruled (10.7): a group's channels are its declared steps forward, then the same steps reverse, in both modes.",
    "Ruled (10, the record): every single-lineage split records the daughter it follows (fission_followed, "
    "generalised to k); a missing field is a record error (exit 2), never daughter 0.",
    "Mine, unruled and unexercised beyond the registered runs: admission's v = 6 sqrt(pi) V/A^(3/2) with "
    "V = min(V_osm, V_sph); a transfer replaces the pool's finite places and leaves held places; the time uniform is "
    "recorded as the value that enters -ln(u).",
]

AMENDMENTS = [
    {"id": 6, "date": "2026-11-18", "ruling": "§0.2d item 10 at c8b22371 (ol-rulings-20261118)",
     "registered_inputs": "unchanged (worlds, runs, probe states, parents, refusals)",
     "changes": [
         "a missing or out-of-range followed daughter on a single-lineage split is a record error, never daughter 0",
         "every counter starts at 0, a new lineage key's included (was: read from the record)",
         "every daughter takes its slot before any birth lysis, which then frees it (was: a birth-lysed daughter took "
         "none); this moves the daughters' slots in ol3_shear_probe_run's reference trace, and nothing else",
         "a scheduled event due now applies before any draw, so simultaneous events take no draw between them; a "
         "declared time equal to t_end applies (neither occurs in a registered run: every run's draws are unchanged)",
         "a single lineage's channel table must be the ruled order too (was: any declared order)",
         "every recorded draw must be the reference's: no exemption for a gap past t_end or a stopped attempt",
     ]},
]


def design_document() -> dict:
    runs = R2.runs()
    return {
        "format": "ool_references.design@1",
        "milestone": "OL2 and OL3",
        "registered": R2.REGISTERED_ON,
        "design_note": R2.AUTHORITY + "; §0.2d item 10 (the replay conventions) at c8b22371, amendment 6",
        "statistics": {"alpha": ALPHA, "min_power": MIN_POWER},
        "conventions": R2.CONVENTIONS,
        "tolerances": {"forward_rate_log": OC.FORWARD_RTOL, "identity_and_cycle_log": OC.LOG_ATOL,
                       "geometry_relative": OC.GEOMETRY_RTOL, "tension_relative_to_kT_NA_cext_R_over_2": OC.TENSION_RTOL,
                       "stationary_total_variation": OC.STATIONARY_TV, "replay_near_tie": P.TIE_RTOL,
                       "replay_time_relative": P.TIME_RTOL, "bookings_relative_to_F_scale": 1e-9,
                       "closure_relative_to_F_scale": 1e-9},
        "streams": {"world_selection": "domain 5, the world's carrier word, (u1, u2, u3) per draw (§0.2c 14, §0.2d 5)",
                    "lineage_events": "domain 1, the followed assembly's key, OL1's two per draw, the age counter "
                                      "(§0.2d 6 at 95c98b5a)",
                    "fission": "domain 2, the parent's key, the parent's attempt count, one block of N + k + N_L "
                               "(§0.2c 9-10, 12)",
                    "schedules": "domain 6, the declared index, one draw per Poisson gap or per living assembly "
                                 "(§0.2d 6, confirmed at 95c98b5a)",
                    "clock": "a draw crossing the next schedule time is discarded, the clock moves to it, the event "
                             "applies, the next draw takes the next counter; a draw crossing t_end ends the run"},
        "rows": {row: {"claim": claim,
                       **({"run": RUN_OF_ROW[row], "end_reason": END_REASON[RUN_OF_ROW[row]],
                           "coverage": COVERAGE.get(RUN_OF_ROW[row], {})} if row in RUN_OF_ROW else {})}
                 for row, claim in ROWS.items()},
        "inputs": {"worlds": sorted(f"{n}.world2.json" for n in R2.worlds()),
                   "runs": sorted(f"{n}.json" for n in runs),
                   "probe_states": ["ol2_wa_probe_states.json", "ol2_wa_diffusion_probe_states.json",
                                    "ol2_closed_states.json", "ol2_two_states.json"],
                   "partition": "ol3_parents.json", "refusals": "refusals2/"},
        "registered_margins": REGISTERED_MARGINS,
        "zero_power": ZERO_POWER,
        "readings": READINGS,
        "amendments": AMENDMENTS,
    }


def write_design(out_dir=R2.DESIGN_DIR) -> Path:
    p = Path(out_dir) / DESIGN_FILE
    p.write_bytes(R2.canonical(design_document()))
    return p

