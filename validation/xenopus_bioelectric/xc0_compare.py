"""XC0's comparison reader: the engine-only table (xc0_engine.py) against the references' registered
interface (tag xc0-references-landed-2026-11-22; validation/xenopus_bioelectric/references/designs/).

Written from `references/REFERENCES_USAGE.md` alone (D308's rule: a registration names a reader that
exists at its tag): its file layout, its five kinds, its band rule and its key grammar. Never from
the interface files' contents, the references' code, README or tests. The builder never opened
either designs file; only this module opens them, and only in its `keys` and `judge` stages, after
the rule's tag.

The interface, as REFERENCES_USAGE.md states it:
- values: families[<family>]["values"][<key>] (a 50-digit decimal string) and, for sign rows only,
  families[<family>]["aux"][<key>] (the quantity that decides the sign);
- bands: families[<family>] = {claim, quantity, unit, kind, tol_abs, tol_rel, tol_source, note,
  rows[<key>] = {floor, band}}, a row's own tol_abs overriding the family's;
- kinds: abs (|engine - reference| <= band), sign (the engine's sign is the reference's, compared only
  where |aux| > band, else the row has no power), exact_zero (the engine's value is exactly 0), flag
  ("true"/"false" equality), info (not compared);
- the band rule: band = max(tol_abs + tol_rel |reference|, 10 floor).

Stages (each a command):
- `keys BANDS OUT [--with-text]`: the bands file's family names, kinds, units and row keys (with
  --with-text, at the lead's leave, each family's claim and quantity strings), written to OUT; never
  a value, aux, floor, band, tolerance or note. With the MAPPING, the table's manifest.
- `check-keys KEYS`: the reader's guard over the keys stage's output (erratum 1, revised): every
  compared row is mapped, not run or not mappable, and every token of a mapped row's key is one
  its rule reads (MAPPING's `reads`), every word one its builder knows; any other row is listed
  with the reason (names and keys only) and the stage exits 1.
- `manifest KEYS OUT [--changed]`: each compared row's engine reading (MAPPING) as xc0_engine's
  manifest; it refuses, writing nothing, where check-keys would (names and keys only). With
  --changed (erratum 2), the changed families' rows alone: the rerun's manifest.
- `judge TABLE VALUES BANDS OUT --carry D329_JUDGE [--retry RETRY_TABLE]` (erratum 2): checks the
  rule (check_rule), the table's clean snapshot, cap and engine sources (the frozen engine of D329's
  snapshot), and the carried file's digest; then resolves every row of the changed families to one
  table row, with the values file unopened (a refusal prints family names and keys only), and
  refuses a table row of another family or one built with other parameters; then loads the values
  file, finds every compared key in it, and only then reads values, aux and bands, recomputes each
  abs row's band by the rule from its stored floor and tolerances (a stored band that disagrees
  refuses; a sign row's stored band decides its power; erratum 2's ruled tolerance floors C7's
  band), and judges the changed families. D329's judged rows of every other family are carried
  (family, key, outcome and reason), and the verdicts are given over every row, each judged once.
  With --retry, the retry table's rows replace the first table's inconclusive rows and the
  judgement is after-retry.
- `carry-check KEYS D329_JUDGE` (erratum 2): the carried file's digest, and its rows against the
  keys stage's rows (names and keys only).
- `retry-manifest TABLE OUT`: the retry's manifest, the table's inconclusive rows.
- `synthetic OUT`: an invented interface and table (no engine, no reference), for the end-to-end check.
- `structure FILE`: the key layout of an interface-shaped file, no value (for the invented one).
- `selfcheck OUT`: the end-to-end check on the invented interface (the rule's pre-tag check).

Verdicts (the rule's): a row passes, fails, has no power (a sign row whose |aux| <= band), is info,
is not run (the rule's not-run list, with its reason) or, after the retry, is engine_refused. A
family fails if any row fails; else it is not testable if any row is engine_refused; else it passes
if any row passes; else it is neutral (info, not run, or no power: it neither passes nor blocks its
claim). A claim (C0-C8) fails if any family fails; else it is not testable if any family is; else it
passes if any family passes; else (nothing had power) it is not testable. XC0 fails if any claim
fails, else it is not testable if any claim is, else it passes. A table's refused, errored or
step-unconverged rows are inconclusive: they stop the judgement before any value is read, and the
retry (once) re-measures them into a second table that the judge merges row by row (`--retry`).
"""

import argparse
import decimal
import hashlib
import json
import math
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DESIGNS = HERE / "references" / "designs"
VALUES = "xc0_reference_values.json"
BANDS = "xc0_interface_bands.json"
FLOOR_FACTOR = 10  # REFERENCES_USAGE.md's band rule.
KINDS = ("abs", "sign", "exact_zero", "flag", "info")
ION_SETS = ("primary", "bracket_Cl_high", "bracket_second_hand_table")
EXTERIORS = ("bath", "local", "bath70_Na", "bath70_inert", "bath_Cl10", "bath_Cl11p1")
NUMBER = re.compile(r"^([A-Za-z][A-Za-z_]*?)([-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)$")
MATCH_RTOL = 1e-9  # A key's number meets a manifest's within this relative difference.


# ------------------------------------------------------------------ keys


def parse_key(key):
    """A row key's parameters, by REFERENCES_USAGE.md's grammar: a leading state
    `ionset|exterior|T<K>`, then `|`-separated tokens, each `<name><number>` (P, g, a, d, k, x, n,
    Nain, Naout, BP, BN, NaP, NaN, rB, T, off, V, kir_g, x_gly, ...), `Vrest_<exterior>`, a lone
    ion set or exterior, or a word (a scenario such as sym or S1_leaks_bath). Returns {name: float or str}; a token it cannot read
    is kept as {"word": ...}. The mapping refuses a key that carries a parameter its rule does not
    read, or a word its builder does not know (the token guard, mapped())."""
    tokens = key.split("|")
    params = {}
    if len(tokens) >= 3 and tokens[0] in ION_SETS and tokens[1] in EXTERIORS:
        m = NUMBER.match(tokens[2])
        if m and m.group(1) == "T":
            params.update(ion_set=tokens[0], exterior=tokens[1], T=float(m.group(2)))
            tokens = tokens[3:]
    words = []
    for token in tokens:
        if token.startswith("Vrest_") and token[6:] in EXTERIORS:
            params["Vrest"] = token[6:]
            continue
        if token in ION_SETS and "ion_set" not in params:  # A lone ion set (C8 (a)'s pairs).
            params["ion_set"] = token
            continue
        if token in EXTERIORS and "exterior" not in params:
            params["exterior"] = token
            continue
        m = NUMBER.match(token)
        if m and not re.match(r"^S\d", token):
            name, value = m.group(1), float(m.group(2))
            if name in params:
                raise ValueError(f"key {key!r} repeats {name}")
            params[name] = value
        else:
            words.append(token)
    if words:
        params["word"] = "|".join(words)
    return params


def same(a, b):
    if isinstance(a, (list, tuple)) or isinstance(b, (list, tuple)):  # Erratum 2's ratio domain.
        return (isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)) and len(a) == len(b)
                and all(same(x, y) for x, y in zip(a, b, strict=True)))  # fmt: skip
    if isinstance(a, str) or isinstance(b, str):
        return a == b
    return a == b or abs(a - b) <= MATCH_RTOL * max(abs(a), abs(b))


def same_params(a, b):
    return set(a) == set(b) and all(same(a[k], b[k]) for k in a)


# ------------------------------------------------------------------ the mapping (the rule's)

# Each rule: (family pattern, engine measure, params builder, needs, reads). A family no rule
# matches is unmapped: the judge refuses it (its name and keys printed). `needs` lists the parsed
# parameters a key must carry and `reads` every parsed parameter the rule reads, its needs among
# them. A key that lacks a need, carries a token outside `reads` (the token guard: every parsed
# token is read) or holds a word or value its builder does not know is unmapped. NOT_RUN lists the
# rows the rule does not run, with the reason (the lead's ruling of 23 November 2026 for version
# 2's kinetic rows); NOT_MAPPABLE the rows the confirmer's semantics leave without a definition or a
# needed value.
STATE = ("ion_set", "exterior", "T")
# The scenario words of C3 and of C7's relaxations (SEMANTICS.md, section 2's tokens).
C3_SCENARIOS = (
    "S1_leaks_bath", "S2_glycine1e-8_bath", "S3_glycine3e-8_bath", "S4_glycine1e-8_bath70Na",
    "S5_glycine1e-8_bath70inert", "S6_kir3_bath", "S7_leaks_bath_Clhigh",
    "S8_leaks_bath_secondhand", "S9_leaks_bath_T287",
)  # fmt: skip
C7_SCENARIOS = ("S1_leaks_bath", "S2_glycine1e-8_bath", "S4_glycine1e-8_bath70Na")
SYM_COUNT_WORDS = ("dNa_in", "dB_in", "dNa_out", "dB_out", "charge_inward")


def word_in(params, allowed):
    """The key's word, or KeyError (the row unmapped) where it is not one of `allowed`."""
    word = params.get("word")
    if word not in allowed:
        raise KeyError(f"word {word!r}")
    return word


def keep(*names, **fixed):
    def build(family, params):
        return {**{n: params[n] for n in names if n in params}, **fixed}

    return build


def ion_from_family(prefix):
    def build(family, params):
        return {**{n: params[n] for n in STATE}, "ion": family[len(prefix):]}

    return build


def scenario(*names):
    """C3: the scenario word (C3_SCENARIOS), d<delta> as delta, and the named tokens."""

    def build(family, params):
        out = {n: params[n] for n in names if n in params}
        out["scenario"] = word_in(params, C3_SCENARIOS)
        if "d" in params:
            out["delta"] = params["d"]
        return out

    return build


def two_cell(family, params):
    """C5's scenario: the word sym, or exactly one of kir_g<g> and x_gly<P> (cell 2's element);
    x<m>, the junction's multiple, where the key carries it (1 otherwise)."""
    out = {"x": params.get("x", 1.0)}
    elements = [n for n in ("kir_g", "x_gly") if n in params]
    if params.get("word") == "sym" and not elements:
        return out
    if "word" in params or len(elements) != 1:
        raise KeyError("no two-cell scenario")
    out[elements[0]] = params[elements[0]]
    return out


def sym_state(family, params):
    """A version-1 state key: n, Nain, Naout, BP, rB and T."""
    return {n: params[n] for n in SYM}


def eq_ratio(family, params):
    """The equilibrium ratio (and x there): J's root over B_in/B_out at the key's voltage, V<V> or
    Vrest_<exterior>, at 291.15 K (SEMANTICS.md, reading 7: these keys carry no T). Version 1's
    J = k a S (1 - e^x) puts it where x = 0 whatever B_out is (S > 0), so B_out is the declared dose
    bath's B."""
    voltage = [n for n in ("V", "Vrest") if n in params]
    if len(voltage) != 1:
        raise KeyError("no voltage")
    return {"BP": 10.0, "T": 291.15, **{n: params[n] for n in ("n", "Nain", "Naout", *voltage)}}


def diagram(family, params):
    """Version 2's keys (NaP, BP, BN[, V]): Na_N 21 mM and 291.15 K, fixed in the reference's
    generator (SEMANTICS.md, reading 7; SEMANTICS-2.md, question 6)."""
    out = {"n": 2, "Nain": 21.0, "Naout": params["NaP"], "BP": params["BP"],
           "rB": params["BN"] / params["BP"], "T": 291.15}  # fmt: skip
    if "V" in params:
        out["V"] = params["V"]
    return out


def from_family(pattern, name, value=float):
    """A parameter carried in the family's name (C0.cl_i_threshold_V<V>, C1.kir_I_u<u>,
    C1.kir_slope_u<u>, C2.sign_dVdt_dV<off>)."""

    def build(family, params):
        m = re.match(pattern, family)
        return {**{n: params[n] for n in STATE if n in params}, name: value(m.group(1))}

    return build


def with_state(**fixed):
    def build(family, params):
        return {**{n: params[n] for n in STATE}, **fixed}

    return build


def sign_current(family, params):
    m = re.match(r"^C1\.sign_I_(K|Cl)_dV(-?[0-9.]+)$", family)
    return {**{n: params[n] for n in STATE}, "ion": m.group(1), "offset": float(m.group(2))}


def scenario_k(family, params):
    """C7's relaxations: the scenario word (C7_SCENARIOS) and k."""
    return {"scenario": word_in(params, C7_SCENARIOS), "k": params["k"]}


def two_cell_cell(family, params):
    """C5.g_m: the scenario and the cell, cell1 or cell2."""
    if params["cell"] not in (1.0, 2.0):
        raise KeyError("no such cell")
    return {**two_cell(family, params), "cell": f"cell{int(params['cell'])}"}


def capacity_state(family, params):
    """C6.v1_capacity_ratio's states (SEMANTICS.md, reading 7), n 2 at 291.15 K: b (Na_N 21, Na_P
    19.9, B_N 0.0001, B_P 10 mM) at its stated -0.0899 V, and a (Na_N 21, Na_P 9.9, B_N 1, B_P 1
    mM), whose voltage is not stated, at 0 V. The row is J at capacity f k0 over J at k0; version
    1's J+ = k a S and J- = J+ e^x both scale with k at every state, so the ratio does not depend
    on the voltage wherever J is not 0, and at 0 V state a's x = n ln(Na_N/Na_P) + ln(B_N/B_P) is
    not 0."""
    if word_in(params, ("a", "b")) == "b":
        na_out, b_out, r_b, v = 19.9, 10.0, 0.0001 / 10.0, -0.0899
    else:
        na_out, b_out, r_b, v = 9.9, 1.0, 1.0, 0.0
    return {"n": 2, "Nain": 21.0, "Naout": na_out, "BP": b_out, "rB": r_b, "T": 291.15, "V": v,
            "f": params["f"]}  # fmt: skip


def pump_counts(family, params):
    measure = {"dNa_cell": "pump_counts_Na", "dK_cell": "pump_counts_K",
               "outward_charge": "pump_outward_charge"}[params["word"]]
    return {"measure": measure}


def pump_cell(family, params):
    """C7.pump_cell_charge_per_fmol's one key, the word cell."""
    word_in(params, ("cell",))
    return {}


def pump_state(family, params):
    """C7's pump keys primary|<exterior>|T<K>|<Vtag>, Vtag the word Vghk or V<V> (one of them). The
    engine's pump world is the primary set's, so a key with another ion set is refused."""
    if params["ion_set"] != "primary" or ("word" in params) == ("V" in params):
        raise KeyError("not a pump key")
    out = {"ion_set": params["ion_set"], "exterior": params["exterior"], "T": params["T"]}
    if "word" in params:
        out["word"] = word_in(params, ("Vghk",))
    else:
        out["V"] = params["V"]
    return out


def sym_offset(family, params):
    return {n: params[n] for n in ("n", "Nain", "Naout", "BP", "rB", "T", "off")}


def sym_at_stall(family, params):
    return {**{n: params[n] for n in ("n", "Nain", "Naout", "BP", "rB", "T")}, "off": 0.0}


def counts_word(family, params):
    return {"n": params["n"], "word": word_in(params, SYM_COUNT_WORDS)}


def c8_species(family, params):
    return {"species": word_in(params, ("Na", "K", "Cl"))}


def c8_species_t(family, params):
    out = c8_species(family, params)
    out["t"] = params["t"]
    return out


def c8_t(family, params):
    return {"t": params["t"]}


def c8_psi(family, params):
    """C8.b_final_psi's one key, the word psi."""
    word_in(params, ("psi",))
    return {}


def cl_sign_side(family, params):
    return {"ion_set": params["ion_set"], "exterior": params["exterior"], "T": params["T"],
            "ion": "Cl"}


# Erratum 2 (D333): the settings of the changed readings, rendered in the erratum's mapping block so
# that check_rule refuses unless they are this module's, and carried in each changed row's manifest
# parameters so that the judge refuses a table row built with others (resolve).
SETTINGS = dict(
    # C6.v1_eq_ratio and C6.v1_eq_x: the reader's B_out (mM) and the ratio's search domain; every
    # searched world's charge-anchor terms stay below anchor_bound_fmol, where the parse's 1e-20 C
    # anchor check cannot fail in float64 (D332: the residual is at most 2^(k-52) fmol in the binade
    # [2^k, 2^(k+1)), 5.6e-21 C below 2^19 fmol).
    eq_ratio=dict(B_out_mM=1e-5, domain=[1e-6, 1e8], anchor_bound_fmol=2.0**19),
    # C8 (b): each P1LB reading's horizon (s). "Final" is the bare node's end state, read at the
    # bare run's horizon; the coupled run keeps erratum 1's 64 s.
    c8b_horizon_s=dict(bare=192.0, coupled=64.0),
    # A floor on a proposed tolerance, which REFERENCES_USAGE.md leaves open to the lead's ruling by
    # a dated note: this erratum proposes it, and the lead's tag of the erratum makes it the ruling.
    # The stored band is still checked against the band rule first.
    tolerance_rulings={"C7.pump_cell_charge_per_fmol": dict(tol_rel=1e-10)},
)  # fmt: skip


def eq_ratio_e2(family, params):
    """Erratum 2: C6.v1_eq_ratio and C6.v1_eq_x at the reader's B_out of SETTINGS (the ratio is the
    root where x = 0, whatever B_out is, since S > 0), its search domain and the anchor bound, at
    291.15 K and the key's V<V> or Vrest_<exterior>."""
    voltage = [n for n in ("V", "Vrest") if n in params]
    if len(voltage) != 1:
        raise KeyError("no voltage")
    s = SETTINGS["eq_ratio"]
    return {"BP": s["B_out_mM"], "T": 291.15, "domain": list(s["domain"]),
            "anchor_bound_fmol": s["anchor_bound_fmol"],
            **{n: params[n] for n in ("n", "Nain", "Naout", *voltage)}}  # fmt: skip


def c8_end_species(family, params):
    """Erratum 2: C8.b_final_c, the bare node's end state, read at the bare run's horizon."""
    return {**c8_species(family, params), "horizon_s": SETTINGS["c8b_horizon_s"]["bare"]}


def c8_end_psi(family, params):
    """Erratum 2: C8.b_final_psi, the bare node's end-state potential, at the bare run's horizon."""
    c8_psi(family, params)
    return {"horizon_s": SETTINGS["c8b_horizon_s"]["bare"]}


def c8_t_e_end(family, params):
    """Erratum 2: C8.bc_t_e, the coupled run's 1/e time from the bare node's end state (the same
    "final" as C8.b_final_c: SEMANTICS.md's c_f), each run checked to end at its horizon."""
    h = SETTINGS["c8b_horizon_s"]
    return {**c8_species(family, params), "horizon_s": h["bare"], "coupled_horizon_s": h["coupled"]}


SYM = ("n", "Nain", "Naout", "BP", "rB", "T")
OFF = (*SYM, "off")
PUMP = ("ion_set", "exterior", "T")
EQ = ("n", "Nain", "Naout")
V2 = ("NaP", "BP", "BN")
C5 = ("word", "kir_g", "x_gly")
C5_X = (*C5, "x")
# Erratum 1's mapping (23 November 2026, from the tagged reader's keys stage and the confirmer's
# SEMANTICS.md and SEMANTICS-2.md), kept verbatim: erratum 2 replaces the rules of its changed
# families in place (E2_RULES, below). Each rule: (family pattern, engine measure, params builder,
# needs, reads).
MAPPING_E1 = (
    (r"^C0\.E_(K|Na|Cl)$", "e_zero", ion_from_family("C0.E_"), STATE, STATE),
    (r"^C0\.V_ghk_area$", "v_zero", keep(*STATE), STATE, STATE),
    (r"^C0\.k_effect_sign_area$", "effect_sign", keep(*STATE, ion="K"), STATE, STATE),
    (r"^C0\.cl_effect_sign_area$", "effect_sign", keep(*STATE, ion="Cl"), STATE, STATE),
    (r"^C0\.cl_bound_area$", "cl_bound", keep(*STATE), STATE, STATE),
    (r"^C0\.cl_i_critical_area$", "cl_threshold", keep(*STATE), STATE, STATE),
    (r"^C0\.cl_i_threshold_V(-?[0-9.]+)$", "cl_threshold",
     from_family(r"^C0\.cl_i_threshold_V(-?[0-9.]+)$", "V"), STATE, STATE),
    (r"^C0\.feasible_19p4_area$", "feasible_19p4", keep(*STATE), STATE, STATE),
    (r"^C1\.zero_(K|Cl)$", "e_zero", ion_from_family("C1.zero_"), STATE, STATE),
    (r"^C1\.sign_I_(K|Cl)_dV(-?[0-9.]+)$", "ion_current", sign_current, STATE, STATE),
    (r"^C1\.kir_zero_at_EK$", "kir_current_ek", with_state(u=0.0), STATE, STATE),
    (r"^C1\.kir_I_u(-?[0-9.]+)$", "kir_current_ek", from_family(r"^C1\.kir_I_u(-?[0-9.]+)$", "u"),
     STATE, STATE),
    (r"^C1\.kir_slope_u(-?[0-9.]+)$", "kir_slope_ek",
     from_family(r"^C1\.kir_slope_u(-?[0-9.]+)$", "u"), STATE, STATE),
    (r"^C1\.kir_sqrtKo_ratio$", "kir_sqrtko_ratio", keep("ion_set", "T"), ("ion_set", "T"),
     ("ion_set", "T")),
    (r"^C2\.V_ghk_area$", "v_zero", keep(*STATE), STATE, STATE),
    (r"^C2\.sign_dVdt_dV(-?[0-9.]+)$", "dvdt_offset",
     from_family(r"^C2\.sign_dVdt_dV(-?[0-9.]+)$", "offset"), STATE, STATE),
    (r"^C3\.V_inf$", "c3_v_inf", scenario(), ("word",), ("word",)),
    (r"^C3\.g$", "c3_g", scenario(), ("word",), ("word",)),
    (r"^C3\.tau_lin$", "tau_lin", scenario(), ("word",), ("word",)),
    (r"^C3\.tau_doubling$", "c3_tau_doubling", scenario(), ("word",), ("word",)),
    (r"^C3\.tau_fit$", "tau_fit", scenario(), ("word", "d"), ("word", "d")),
    (r"^C3\.ratio_t$", "ratio_t", scenario("k"), ("word", "d", "k"), ("word", "d", "k")),
    (r"^C3\.Q_over_CV_error$", "c3_q_minus_cv", scenario("k"), ("word", "d", "k"),
     ("word", "d", "k")),
    (r"^C4\.V_zero_both$", "v_zero", with_state(P=3e-8, g=3.0, a=1.0), STATE, STATE),
    (r"^C4\.V_zero_glycine$", "v_zero", keep(*STATE, "P", "a"), (*STATE, "P", "a"),
     (*STATE, "P", "a")),
    (r"^C4\.V_zero_kir$", "v_zero", keep(*STATE, "g", "a"), (*STATE, "g", "a"), (*STATE, "g", "a")),
    (r"^C4\.shift_kir$", "shift", keep(*STATE, "g", "a"), (*STATE, "g", "a"), (*STATE, "g", "a")),
    (r"^C4\.shift_glycine_sign$", "shift", with_state(P=1e-8, a=1.0), STATE, STATE),
    (r"^C4\.monotone_kir$", "c4_monotone_kir", keep(*STATE), STATE, STATE),
    (r"^C4\.monotone_glycine$", "c4_monotone_glycine", keep(*STATE), STATE, STATE),
    (r"^C4\.flux_at_a0$", "c4_flux_at_a0", keep(*STATE, "V"), (*STATE, "V"), (*STATE, "V")),
    (r"^C5\.V1_ss$", "c5_v1", two_cell, (), C5_X),
    (r"^C5\.V2_ss$", "c5_v2", two_cell, (), C5_X),
    (r"^C5\.tau_common$", "c5_tau_common", two_cell, (), C5_X),
    (r"^C5\.tau_diff$", "c5_tau_diff", two_cell, (), C5_X),
    (r"^C5\.V_limit$", "c5_v_limit", two_cell, (), C5),
    (r"^C5\.g_J$", "c5_g_j", two_cell, (), C5),
    (r"^C5\.g_m$", "c5_g_m", two_cell_cell, ("cell",), (*C5, "cell")),
    (r"^C5\.tau_fit_common$", "c5_tau_fit_common", two_cell, (), C5),
    (r"^C5\.tau_fit_diff$", "c5_tau_fit_diff", two_cell, (), C5),
    (r"^C6\.S_hill$", "sym_s_at", keep("NaP", "BP"), ("NaP", "BP"), ("NaP", "BP")),
    (r"^C6\.v1_V_stall$", "sym_stall", sym_state, SYM, SYM),
    (r"^C6\.v1_J_at_stall$", "sym_j", sym_at_stall, SYM, SYM),
    (r"^C6\.v1_dJdV_at_stall$", "sym_dj_dv", sym_at_stall, SYM, SYM),
    (r"^C6\.v1_J_offset$", "sym_j", sym_offset, OFF, OFF),
    (r"^C6\.v1_ratio_Jm_Jp$", "sym_ratio", sym_offset, OFF, OFF),
    (r"^C6\.v1_sign_J_offset$", "sym_j", sym_offset, OFF, OFF),
    (r"^C6\.v1_x_offset$", "sym_x", sym_offset, OFF, OFF),
    (r"^C6\.v1_eq_ratio$", "sym_eq_ratio", eq_ratio, EQ, (*EQ, "V", "Vrest")),
    (r"^C6\.v1_eq_x$", "sym_eq_x", eq_ratio, EQ, (*EQ, "V", "Vrest")),
    (r"^C6\.v1_capacity_ratio$", "sym_capacity_ratio", capacity_state, ("word", "f"), ("word", "f")),
    (r"^C6\.v2_V_stall$", "diag_stall", diagram, V2, V2),
    (r"^C6\.v2_ratio_Jm_Jp$", "diag_ratio", diagram, (*V2, "V"), (*V2, "V")),
    # SEMANTICS-2.md (question 6): J-/J+ of the diagram with a second constant set that keeps
    # detailed balance and the charge sum, so the same e^x as v2_ratio_Jm_Jp at its key.
    (r"^C6\.v2_alt_set_ratio$", "diag_ratio", diagram, (*V2, "V"), (*V2, "V")),
    (r"^C7\.pump_cycle_counts$", "pump_counts", pump_counts, ("word",), ("word",)),
    (r"^C7\.pump_cell_charge_per_fmol$", "pump_cell_charge_per_fmol", pump_cell, (), ("word",)),
    (r"^C7\.pump_dG_atp$", "pump_dG_atp_at", pump_state, PUMP, (*PUMP, "word", "V")),
    (r"^C7\.pump_dG_chem$", "pump_dG_chem_at", pump_state, PUMP, (*PUMP, "word", "V")),
    (r"^C7\.pump_dU_cap$", "pump_dU_cap_at", pump_state, PUMP, (*PUMP, "word", "V")),
    (r"^C7\.pump_heat$", "pump_heat_at", pump_state, PUMP, (*PUMP, "word", "V")),
    (r"^C7\.pump_heat_nonneg$", "pump_heat_nonneg_at", pump_state, PUMP, (*PUMP, "word", "V")),
    (r"^C7\.relax_dQ$", "c7_relax_dQ", scenario_k, ("word", "k"), ("word", "k")),
    (r"^C7\.relax_charge_identity$", "c7_relax_identity", scenario_k, ("word", "k"), ("word", "k")),
    (r"^C7\.sym_dG_chem$", "sym_dG_chem", sym_offset, OFF, OFF),
    (r"^C7\.sym_dU_cap$", "sym_dU_cap", sym_offset, OFF, OFF),
    (r"^C7\.sym_heat_per_cycle$", "sym_heat_per_cycle", sym_offset, OFF, OFF),
    (r"^C7\.sym_heat_power$", "sym_heat_power", sym_offset, OFF, OFF),
    (r"^C7\.sym_heat_nonneg$", "sym_heat_nonneg", sym_offset, OFF, OFF),
    (r"^C7\.sym_cycle_counts$", "sym_counts", counts_word, ("n", "word"), ("n", "word")),
    (r"^C8\.a_dE_K$", "c8a_e_K", keep("ion_set", "T"), ("ion_set", "T"), ("ion_set", "T")),
    (r"^C8\.a_dV_ghk_area$", "c8a_v_zero", keep("ion_set", "T"), ("ion_set", "T"), ("ion_set", "T")),
    (r"^C8\.a_cl_sign_bath_vs_local$", "effect_sign", cl_sign_side, STATE, STATE),
    (r"^C8\.b_final_c$", "c8b_final_saved", c8_species, ("word",), ("word",)),
    (r"^C8\.b_final_psi$", "c8b_psi_final_saved", c8_psi, (), ("word",)),
    (r"^C8\.bc_t_e$", "c8b_t_e_saved", c8_species, ("word",), ("word",)),
    (r"^C8\.bc_c_t$", "c8b_at_saved", c8_species_t, ("word", "t"), ("word", "t")),
    (r"^C8\.bc_psi_t$", "c8b_psi_at_saved", c8_t, ("t",), ("t",)),
)  # fmt: skip
# Erratum 2 (D333): the changed families' rules, each in place of erratum 1's rule of the same
# pattern; every other rule stays erratum 1's. Deleting a line here returns that family to erratum
# 1's rule and to D329's judged outcome (the judge carries it). C7's rule is erratum 1's reading,
# listed because its band is ruled (SETTINGS) and it is rerun.
E2_RULES = (
    (r"^C6\.v1_eq_ratio$", "sym_eq_ratio_e2", eq_ratio_e2, EQ, (*EQ, "V", "Vrest")),
    (r"^C6\.v1_eq_x$", "sym_eq_x_e2", eq_ratio_e2, EQ, (*EQ, "V", "Vrest")),
    (r"^C7\.pump_cell_charge_per_fmol$", "pump_cell_charge_per_fmol", pump_cell, (), ("word",)),
    (r"^C8\.b_final_c$", "c8b_end_c", c8_end_species, ("word",), ("word",)),
    (r"^C8\.b_final_psi$", "c8b_end_psi", c8_end_psi, (), ("word",)),
    (r"^C8\.bc_t_e$", "c8b_t_e_end", c8_t_e_end, ("word",), ("word",)),
)  # fmt: skip
E2 = {rule[0]: rule for rule in E2_RULES}
if not set(E2) <= {rule[0] for rule in MAPPING_E1}:
    raise RuntimeError("an erratum 2 rule replaces no rule of erratum 1")
MAPPING = tuple(E2.get(rule[0], rule) for rule in MAPPING_E1)
# The changed families (each E2 pattern names one family exactly): the rerun's rows; every other
# family's outcome is D329's, carried by the judge.
CHANGED = tuple(p[1:-1].replace("\\.", ".") for p in E2)
NOT_RUN = (
    (r"^C6\.v2_early_ratio(_rest)?$", "not run on main: cells.na2_anion_symport_diagram@1 fixes "
     "zeta at 0 on e3/e5/e6/e7 (b_P, b_N, na2_N, na1_N), so DESIGN §3.4's charge placement cannot "
     "be declared and the early-uptake ratio, which depends on it, is not the design's (the lead, "
     "23 November 2026; a declared zeta on every edge is queued with the kinds lane as a general "
     "feature)"),
    (r"^C6\.v2_J_over_k$", "not run on main: the King-Altman J/k depends on the charge placement "
     "(as above)"),
    (r"^C6\.S_half$", "not run: its states hold 1e12 mM, which the engine cannot declare (a node's "
     "initial inventory must hold its charge anchor to 1e-20 C, beyond float64 at 1e15 fmol)"),
    (r"^C8\.a_dV_ghk_unit$", "not run: an unweighted (unit) row, info by the lead's ruling in the "
     "references' amendment (REFERENCES_USAGE.md, after the erratum), though its bands entry says "
     "abs; the engine has no unweighted membrane"),
)  # fmt: skip
# Rows the confirmer's SEMANTICS.md and SEMANTICS-2.md leave without a definition or a needed
# value: refused at judging as not mappable (the lead, 23 November 2026), reported, and neutral in
# the verdicts.
NOT_MAPPABLE = (
    (r"^C4\.T1_reachable$", None, "SEMANTICS.md defines no C4.T1_reachable"),
    (r"^C5\.V_dev_t$", None, "its times need the generator's step count N: 'needs a value; not "
     "stated' (SEMANTICS.md, C5's fits)"),
    (r"^C5\.junction_charge_sum$", None, "its run, window and statistic are not stated: the "
     "reference's two-cell model books no ionic charge, and SEMANTICS-2.md (question 2) leaves "
     "them to the lead's ruling"),
    (r"^C6\.J_over_k_grid$", None, "the state of its J/k (unit 1; SEMANTICS-2.md, question 4) is "
     "not stated: the N end and V (SEMANTICS.md, reading 7: names and keys only)"),
    (r"^C6\.v1_n1_(J|dJ_over_V)$", None, "the n = 1 rows' other concentrations are not stated "
     "(SEMANTICS.md, reading 7: names and keys only)"),
    (r"^C8\.b_final_is_bath$", None, "its criterion: 'needs a value; not stated' (SEMANTICS.md, "
     "C8 (b))"),
)  # fmt: skip


def rule_of(family):
    """The MAPPING rule whose pattern the family matches (the first), or None."""
    for rule in MAPPING:
        if re.search(rule[0], family):
            return rule
    return None


def mapped(family, key):
    """(measure, params) for one compared row, ('not_run', reason), ('not_mappable', reason), or
    None (unmapped: the judge refuses; refusal() says why)."""
    for pattern, reason in NOT_RUN:
        if re.search(pattern, family):
            return "not_run", reason
    try:
        params = parse_key(key)
    except ValueError:
        return None
    for pattern, word, reason in NOT_MAPPABLE:
        if re.search(pattern, family) and (word is None or params.get("word") == word):
            return "not_mappable", reason
    rule = rule_of(family)
    if rule is None:
        return None
    _, measure, build, needs, reads = rule
    if any(n not in params for n in needs) or any(n not in reads for n in params):
        return None  # A need missing, or a token the rule does not read (the token guard).
    try:
        built = build(family, params)
    except (KeyError, AttributeError):
        return None
    if "measure" in built:  # A builder that picks the measure by the key's word.
        return built.pop("measure"), built
    return measure, built


def refusal(family, key):
    """Why mapped() gives a compared row no reading (names and keys only), or "" where it maps
    it (or does not run it, or finds it not mappable)."""
    if mapped(family, key) is not None:
        return ""
    try:
        params = parse_key(key)
    except ValueError as exc:
        return str(exc)
    rule = rule_of(family)
    if rule is None:
        return "no rule maps the family"
    lacking = [n for n in rule[3] if n not in params]
    unread = sorted(n for n in params if n not in rule[4])
    if lacking:
        return "lacks " + ", ".join(lacking)
    if unread:
        return "carries a token its rule does not read: " + ", ".join(unread)
    return "its builder refuses the key (a word or a value it does not know)"


RULE = HERE / "xc0_rule.json"  # Tagged xc0-rule-registered-2026-11-23; kept as tagged.
ERRATUM_1 = HERE / "xc0_rule_erratum_1.json"  # Tag xc0-rule-erratum-1-2026-11-23; kept as tagged.
ERRATUM = HERE / "xc0_rule_erratum_2.json"  # Erratum 2 (D333): the mapping this module now holds.


def rule_mapping():
    """The mapping as the erratum renders it, from this module (one source): the rules, the not-run
    and not-mappable rows, and erratum 2's changed families and settings."""
    return dict(
        rules=[dict(family=p, measure=m, needs=list(n), reads=list(r)) for p, m, b, n, r in MAPPING],
        not_run=[dict(family=p, reason=r) for p, r in NOT_RUN],
        not_mappable=[dict(family=p, key_word=w, reason=r) for p, w, r in NOT_MAPPABLE],
        changed=list(CHANGED),
        settings=json.loads(json.dumps(SETTINGS)),
    )


def check_rule(path=ERRATUM):
    """Refuses when the registered erratum's mapping (with erratum 2's changed families and
    settings) is not this module's. Returns the tagged rule with erratum 1's entries over its own
    and erratum 2's over both, erratum 2 itself under "erratum"."""
    erratum = json.loads(Path(path).read_text())
    if erratum.get("erratum") != 2 or erratum["mapping"] != rule_mapping():
        raise SystemExit(f"refused: {path}'s mapping is not the reader's")
    rule = json.loads(RULE.read_text())
    first = json.loads(ERRATUM_1.read_text())
    merged = {**rule, **{k: v for k, v in first.items() if k in rule}}
    return {**merged, **{k: v for k, v in erratum.items() if k in rule}, "erratum": erratum}


def check_table(table, rule):
    """Refuses a table that was not built from a clean frozen snapshot at the rule's X2 cap."""
    record = table.get("record", {})
    source = record.get("source", {})
    if not source.get("snapshot") or source.get("checkout_dirty", True):
        raise SystemExit("refused: the table was not built from a clean frozen snapshot")
    if record.get("x2_cap") != rule["x2"]["integration_error_cap"]:
        raise SystemExit("refused: the table's X2 cap is not the rule's")


# ------------------------------------------------------------------ stages


def keys(bands_path, *, with_text=False):
    """{family: {"kind", "unit", "keys": [...]}} from the bands file: names, kinds, units and row
    keys only; with_text (the lead's leave) adds each family's claim and quantity strings. Never a
    value, aux, floor, band, tolerance or note."""
    bands = json.loads(Path(bands_path).read_text())
    out = {}
    for family, entry in bands["families"].items():
        out[family] = dict(kind=entry["kind"], unit=entry["unit"], keys=sorted(entry["rows"]))
        if with_text:
            out[family] |= dict(claim=entry["claim"], quantity=entry["quantity"])
    return out


# DESIGN §4's tolerance for a run row's step-halving check (xc0_engine.step_check): the claim's own,
# never the references' band. C3.ratio_t carries C3's 2 % on tau to the decay at t = k tau / 4.
STEP_TOLERANCE = (
    (r"^C3\.tau_fit$", lambda p: {"rel": 0.02}),
    (r"^C3\.ratio_t$", lambda p: {"rel": 0.02 * p["k"] / 4.0}),
    (r"^C3\.Q_over_CV_error$|^C7\.relax_(dQ|charge)|^C5\.junction_charge_sum$",
     lambda p: {"abs": 1e-14}),
    (r"^C5\.tau_fit", lambda p: {"rel": 0.03}),
    (r"^C8\.b", lambda p: {"rel": 0.05}),
)  # fmt: skip


def step_tolerance(family, params):
    for pattern, rule in STEP_TOLERANCE:
        if re.search(pattern, family):
            return rule(params)
    return None


def check_keys(key_list):
    """The reader's guard over the keys stage's output ({family: {kind, unit, keys}}): each compared
    row (info rows aside) is mapped, with every token of its key read by its rule and every word
    known to its builder, or is not run or not mappable. Returns (counts, unmapped), each unmapped
    row as (family, key, reason): names and keys only. counts["changed"] holds erratum 2's changed
    families' mapped rows by family (the rerun's rows)."""
    counts, unmapped = dict(mapped=0, not_run=0, not_mappable=0, unmapped=0, info=0), []
    changed = {}
    for family, entry in sorted(key_list.items()):
        if entry["kind"] == "info":
            counts["info"] += len(entry["keys"])
            continue
        for key in entry["keys"]:
            m = mapped(family, key)
            if m is None:
                unmapped.append((family, key, refusal(family, key)))
                counts["unmapped"] += 1
            else:
                counts[m[0] if m[0] in ("not_run", "not_mappable") else "mapped"] += 1
                if family in CHANGED and m[0] not in ("not_run", "not_mappable"):
                    changed[family] = changed.get(family, 0) + 1
    counts["changed"] = changed
    return counts, unmapped


def key_list_of(bands):
    """The keys stage's view of a bands file's content: each family's kind, unit and row keys."""
    return {f: dict(kind=e["kind"], unit=e["unit"], keys=sorted(e["rows"]))
            for f, e in bands["families"].items()}  # fmt: skip


def manifest(key_list, *, changed_only=False):
    """The engine manifest for the compared rows, the not-run and not-mappable rows apart, and the
    unmapped rows with check-keys' reasons (the manifest stage refuses where any is unmapped). With
    changed_only (erratum 2's rerun), the rows of the changed families alone."""
    entries, unmapped, not_run = [], [], []
    for family, entry in sorted(key_list.items()):
        if entry["kind"] == "info" or (changed_only and family not in CHANGED):
            continue
        for key in entry["keys"]:
            m = mapped(family, key)
            if m is None:
                unmapped.append((family, key, refusal(family, key)))
            elif m[0] in ("not_run", "not_mappable"):
                not_run.append((family, key, m[0]))
            else:
                item = dict(family=family, key=key, measure=m[0], params=m[1])
                tolerance = step_tolerance(family, parse_key(key))
                if tolerance is not None:
                    item["step_tolerance"] = tolerance
                entries.append(item)
    return dict(entries=entries, unmapped=unmapped, not_run=not_run)


def table_rows(table):
    """The table's rows by (family, parsed key, measure)."""
    rows = []
    for row in table["rows"]:
        rows.append((row["family"], parse_key(row["key"]), row["measure"], row))
    return rows


def resolve(table, key_list, *, after_retry=False):
    """Each compared row's table row, or the reasons it has none. Reads no value. Before the retry
    a refused, errored or step-unconverged table row is a problem (the judgement stops); after it,
    such a row is judged as engine_refused. A table row whose recorded parameters are not the
    mapping's (erratum 2: its settings ride in them) is a problem."""
    rows = table_rows(table)
    resolved, problems = {}, []
    for family, entry in sorted(key_list.items()):
        if entry["kind"] == "info":
            continue
        for key in entry["keys"]:
            m = mapped(family, key)
            if m is None:
                problems.append((f"unmapped ({refusal(family, key)})", family, key))
                continue
            if m[0] in ("not_run", "not_mappable"):
                resolved[(family, key)] = m
                continue
            params = parse_key(key)
            hits = [r for f, p, measure, r in rows if f == family and measure == m[0]
                    and same_params(p, params)]  # fmt: skip
            if len(hits) != 1:
                problems.append(("no table row" if not hits else "several table rows", family, key))
            elif not same_params(hits[0].get("params", {}), m[1]):
                problems.append(("a table row built with other parameters than the mapping's",
                                 family, key))  # fmt: skip
            elif not inconclusive(hits[0]) and (hits[0]["type"] == "flag") != (entry["kind"] == "flag"):
                problems.append((f"a {hits[0]['type']} row for a {entry['kind']} family", family, key))
            elif inconclusive(hits[0]):
                if after_retry:
                    resolved[(family, key)] = ("engine_refused", inconclusive(hits[0]))
                else:
                    problems.append((f"table row {inconclusive(hits[0])}", family, key))
            else:
                resolved[(family, key)] = ("row", hits[0])
    return resolved, problems


def inconclusive(row):
    """Why a table row cannot be judged as it stands (empty if it can)."""
    if row["type"] in ("refused", "error"):
        return row["type"]
    if "step_check" in row and not row["step_check"]["converged"]:
        return "step unconverged"
    return ""


def number(text):
    return decimal.Decimal(text)


def band_of(entry, row, reference):
    """REFERENCES_USAGE.md's band: max(tol_abs + tol_rel |reference|, 10 floor), the row's own
    tol_abs overriding the family's, in decimal arithmetic."""
    tol_abs = number(str(row.get("tol_abs", entry["tol_abs"])))
    tol_rel = number(str(entry["tol_rel"]))
    floor = number(str(row["floor"]))
    return max(tol_abs + tol_rel * abs(reference), FLOOR_FACTOR * floor)


def compare(kind, engine, reference, band, aux=None):
    """One row's outcome: pass, fail or no_power."""
    if kind == "abs":
        return "pass" if abs(number(engine) - reference) <= band else "fail"
    if kind == "sign":
        if aux is None or abs(aux) <= band:
            return "no_power"
        e = number(engine)
        sign = (e > 0) - (e < 0)
        return "pass" if decimal.Decimal(sign) == reference else "fail"
    if kind == "exact_zero":
        return "pass" if number(engine) == 0 else "fail"
    if kind == "flag":
        return "pass" if engine == reference else "fail"
    raise ValueError(f"kind {kind} is not compared")


def engine_text(row):
    return row["value"]


def merge(first, retry):
    """The first table with the retry's rows in place of its rows of the same family, measure and
    key (met by number); the retry re-measures only the first table's inconclusive rows, and
    a retry row with no such row in the first table is refused."""
    replaced = []
    rows = [dict(r) for r in first["rows"]]
    for new in retry["rows"]:
        hits = [i for i, r in enumerate(rows) if r["family"] == new["family"]
                and r["measure"] == new["measure"]
                and same_params(parse_key(r["key"]), parse_key(new["key"]))]  # fmt: skip
        if len(hits) != 1 or not inconclusive(rows[hits[0]]):
            raise SystemExit(f"refused: the retry's row {new['family']} | {new['key']} does not "
                             "replace one inconclusive row of the first table")  # fmt: skip
        rows[hits[0]] = dict(new, retried=True)
        replaced.append((new["family"], new["key"]))
    return dict(first, rows=rows, retried=replaced)


def retry_manifest(table):
    """The retry's manifest: the table's inconclusive rows, with their measures and parameters."""
    entries = []
    for r in table["rows"]:
        if inconclusive(r):
            entry = dict(family=r["family"], key=r["key"], measure=r["measure"], params=r["params"])
            if r.get("step_tolerance") is not None:
                entry["step_tolerance"] = r["step_tolerance"]
            entries.append(entry)
    return dict(entries=entries, unmapped=[], not_run=[])


def judge(table, values, bands, *, after_retry=False, only=None):
    """The verdicts. `values` is the values file's content, or a function that loads it: it is
    loaded only after every compared row resolves to a table row (a refusal reads no value), and
    then only after every compared key is found in it. With `only` (erratum 2's changed families),
    only those families are judged, and a table row of any other family refuses."""
    key_list = key_list_of(bands)
    for family, entry in key_list.items():
        if entry["kind"] not in KINDS:
            raise SystemExit(f"refused: family {family} has kind {entry['kind']!r}")
    if only is not None:
        stray = sorted({r["family"] for r in table["rows"] if r["family"] not in only})
        if stray:
            raise SystemExit("refused before any value was read: the table holds rows of families "
                             "it does not judge: " + ", ".join(stray))  # fmt: skip
        key_list = {f: e for f, e in key_list.items() if f in only}
    resolved, problems = resolve(table, key_list, after_retry=after_retry)
    if problems:
        lines = [f"{why}: {family} | {key}" for why, family, key in problems]
        raise SystemExit("refused before any value was read:\n" + "\n".join(lines))
    values = values() if callable(values) else values
    missing = [(f, k) for (f, k), (what, _) in sorted(resolved.items()) if what == "row" and (
        k not in values["families"].get(f, {}).get("values", {})
        or (key_list[f]["kind"] == "sign" and k not in values["families"][f].get("aux", {})))]
    if missing:
        lines = [f"no reference: {f} | {k}" for f, k in missing]
        raise SystemExit("refused before any value was read:\n" + "\n".join(lines))
    # Only now are values, aux, floors and bands read.
    rows, decimal.getcontext().prec = [], 60
    for (family, key), (what, item) in sorted(resolved.items()):
        entry = bands["families"][family]
        if what in ("not_run", "not_mappable"):
            rows.append(dict(family=family, key=key, outcome=what, reason=item))
            continue
        if what == "engine_refused":
            rows.append(dict(family=family, key=key, outcome="engine_refused", reason=item))
            continue
        row = entry["rows"][key]
        kind = entry["kind"]
        ref_text = values["families"][family]["values"][key]
        reference, band = (ref_text, None) if kind == "flag" else (number(ref_text), None)
        ruled = None
        if kind == "abs":  # The band rule is checked where REFERENCES_USAGE.md defines its terms.
            band = band_of(entry, row, reference)
            stored = number(str(row["band"]))
            if abs(stored - band) > decimal.Decimal("1e-12") * max(abs(band), decimal.Decimal(
                    "1e-300")):  # fmt: skip
                raise SystemExit(f"refused: {family} | {key}: stored band disagrees with the rule")
            ruling = SETTINGS["tolerance_rulings"].get(family)
            if ruling is not None:  # Erratum 2: a floor on the row's tol_rel, the stored band kept.
                ruled = band_of(dict(entry, tol_rel=ruling["tol_rel"]), row, reference)
                band, stored_band = max(band, ruled), band
        elif kind == "sign":  # The stored band decides power (|aux| > band).
            band = number(str(row["band"]))
        aux = None
        if kind == "sign":
            aux = number(values["families"][family]["aux"][key])
        outcome = compare(kind, engine_text(item), reference, band, aux)
        out = dict(family=family, key=key, kind=kind, outcome=outcome, engine=item["value"],
                   reference=ref_text, band=None if band is None else str(band),
                   aux=None if aux is None else str(aux), retried=bool(item.get("retried")))
        if ruled is not None:
            out["band_stored"] = str(stored_band)
        rows.append(out)
    for family, entry in bands["families"].items():
        if entry["kind"] == "info" and (only is None or family in only):
            rows.extend(dict(family=family, key=k, outcome="info") for k in entry["rows"])
    return verdicts(rows)


def carry(carried, new, bands):
    """Erratum 2's verdict (D333): D329's judged rows (`carried`, its judge.json) of every family
    erratum 2 does not change, with `new`, the judged rows of the changed families. Reads only the
    carried rows' family, key, outcome and reason. Refuses unless every row of the interface is
    judged exactly once."""
    keep = ("family", "key", "outcome", "reason")
    rows = [{k: r[k] for k in keep if k in r} for r in carried["rows"]
            if r["family"] not in CHANGED]  # fmt: skip
    rows += [dict(r, erratum=2) for r in new["rows"]]
    seen = {}
    for r in rows:
        seen[(r["family"], r["key"])] = seen.get((r["family"], r["key"]), 0) + 1
    want = {(f, k) for f, e in bands["families"].items() for k in e["rows"]}
    if set(seen) != want or any(n != 1 for n in seen.values()):
        lacking = sorted(want - set(seen))[:20]
        extra = sorted(set(seen) - want)[:20]
        twice = sorted(fk for fk, n in seen.items() if n > 1)[:20]
        raise SystemExit(f"refused: the carried and new rows do not judge every row once (lacking "
                         f"{lacking}, not in the interface {extra}, twice {twice})")  # fmt: skip
    return verdicts(rows)


def file_digest(path, expected):
    """A file's sha256 (its bytes only, nothing parsed), refused unless it is `expected`."""
    digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    if digest != expected:
        raise SystemExit(f"refused: {path} has sha256 {digest}, not the erratum's {expected}")
    return digest


def snapshot_sources(snapshot):
    """{path: sha256} of a frozen snapshot's engine sources (src/), from its SNAPSHOT.json."""
    record = json.loads((Path(snapshot) / "SNAPSHOT.json").read_text())
    return {p: f["sha256"] for p, f in record["files"].items() if p.startswith("src/")}


def same_engine(table, base_snapshot):
    """D333: the rerun runs on the same frozen engine as D329's record. Refuses unless the table's
    snapshot holds the engine sources (every src/ file, by sha256) of the base snapshot."""
    ours = snapshot_sources(table["record"]["source"]["snapshot"])
    base = snapshot_sources(base_snapshot)
    differ = sorted(p for p in set(ours) | set(base) if ours.get(p) != base.get(p))
    if differ:
        raise SystemExit(f"refused: the table's engine sources are not the base snapshot's "
                         f"({len(differ)} files differ, among them {differ[:10]})")  # fmt: skip


def verdicts(rows):
    """Families, claims and XC0 (the rule's verdicts). A family whose rows all lack power (or are
    info or not run) is neutral, as info is: it neither passes nor blocks its claim."""
    families = {}
    for r in rows:
        families.setdefault(r["family"], []).append(r["outcome"])

    def family_verdict(outcomes):
        if "fail" in outcomes:
            return "fail"
        if "engine_refused" in outcomes:
            return "not_testable"
        if "pass" in outcomes:
            return "pass"
        if all(o == "info" for o in outcomes):
            return "info"
        if all(o == "not_run" for o in outcomes):
            return "not_run"
        if all(o in ("not_run", "not_mappable") for o in outcomes):
            return "not_mappable"
        return "no_power"

    fam = {f: family_verdict(o) for f, o in families.items()}
    claims = {}
    for f, v in fam.items():
        claims.setdefault(f.split(".", 1)[0], []).append(v)

    def claim_verdict(vs):
        if "fail" in vs:
            return "fail"
        if "not_testable" in vs:
            return "not_testable"
        if "pass" in vs:
            return "pass"
        return "not_testable"  # Nothing in the claim had power.

    claim = {c: claim_verdict(v) for c, v in claims.items()}
    overall = ("fail" if "fail" in claim.values()
               else "not_testable" if "not_testable" in claim.values() else "pass")  # fmt: skip
    counts = {}
    for r in rows:
        counts[r["outcome"]] = counts.get(r["outcome"], 0) + 1
    return dict(overall=overall, claims=claim, families=fam, counts=counts, rows=rows)


# ------------------------------------------------------------------ the documented grammar

P_GRID = (1e-9, 3e-9, 1e-8, 3e-8)  # REFERENCES_USAGE.md's grids (and DESIGN §3.2, §3.5).
G_GRID = (0.1, 0.3, 1.0, 3.0)
A_ROWS = (0.25, 0.5, 1.0)  # The availabilities with rows; 0 and 0.75 feed the monotone flags.
TEMPERATURES = (291.15, 287.15)


def state_keys():
    return [f"{i}|{e}|T{t:g}" for i in ION_SETS for e in EXTERIORS for t in TEMPERATURES]


def grammar():
    """The key list of the families whose names and keys REFERENCES_USAGE.md documents in full
    (the 36 states; C4's grids), in the keys stage's format, built with no interface file: the
    table's manifest for the rule's option A. Every other compared family's keys come from the
    interface itself at judging (option B), or from the refusal's list (option A)."""
    states = state_keys()
    out = {}
    for family in ("C0.E_K", "C0.E_Na", "C0.E_Cl", "C0.V_ghk_area", "C1.zero_K", "C1.zero_Cl",
                   "C2.V_ghk_area"):  # fmt: skip
        out[family] = dict(kind="abs", unit="V", keys=list(states))
    out["C4.V_zero_glycine"] = dict(kind="abs", unit="V", keys=[
        f"{s}|P{p:g}|a{a:g}" for s in states for p in P_GRID for a in A_ROWS])
    out["C4.V_zero_kir"] = dict(kind="abs", unit="V", keys=[
        f"{s}|g{g:g}|a{a:g}" for s in states for g in G_GRID for a in A_ROWS])
    return out


def calibrations():
    """T1 and T2's engine readings (published numbers, outside the reference verdict): T2, the
    GlyR arm's change in the 70 mM Cl- bath (both cation options) per ion set, temperature and
    P_GlyR; T1, the m_kleak availability that depolarises by the published 11 mV in 0.1x MMR."""
    entries = []
    for i in ION_SETS:
        for t in TEMPERATURES:
            for e in ("bath70_Na", "bath70_inert"):
                for p in P_GRID:
                    key = f"{i}|{e}|T{t:g}|P{p:g}"
                    entries.append(dict(family="T2.shift", key=key, measure="t2_shift",
                                        params=dict(ion_set=i, exterior=e, T=t, P=p)))  # fmt: skip
            key = f"{i}|bath|T{t:g}"
            entries.append(dict(family="T1.kleak_availability", key=key,
                                measure="t1_kleak_availability",
                                params=dict(ion_set=i, exterior="bath", T=t, shift_V=0.011)))  # fmt: skip
    return entries


# ------------------------------------------------------------------ the invented check


def synthetic(out):
    """An invented interface and engine table in the interface's documented layout: a pass, a fail,
    a sign with and without power, an exact zero, a flag, an info row, a not-run row, a C4 key and a
    C6 key whose numbers are written differently in the table than in the interface."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    state = "primary|bath|T291.15"
    fams = {
        "C2.V_ghk_area": ("abs", 1e-6, 0.0, {state: ("-0.0123456", "1e-17")}),
        "C1.zero_K": ("abs", 1e-6, 0.0, {state: ("-0.1000000", "1e-17")}),
        "C0.k_effect_sign_area": ("sign", 1e-6, 0.0, {state: ("-1", "1e-17"),
                                                      "primary|local|T291.15": ("1", "1e-17")}),
        "C4.V_zero_glycine": ("abs", 1e-5, 0.0, {f"{state}|P1e-08|a0.5": ("-0.02", "1e-17")}),
        "C6.v1_V_stall": ("abs", 1e-5, 0.0, {"n2|Nain21|Naout9.9|BP10|rB1|T291.15": ("-0.03", "1e-17")}),
        "C7.pump_heat_nonneg": ("flag", 0.0, 0.0, {f"{state}|V-0.04": ("true", "0")}),
        "C8.b_final_is_bath": ("flag", 0.0, 0.0, {"bath": ("false", "0")}),
        "C0.V_ghk_unit": ("info", 0.0, 0.0, {state: ("-0.07", "1e-17")}),
        "C6.v2_early_ratio_rest": ("abs", 0.0, 1e-6, {"Vrest_bath": ("2.0", "1e-17")}),
    }
    values, bands = dict(families={}), dict(families={})
    for f, (kind, tol_abs, tol_rel, rows) in fams.items():
        values["families"][f] = dict(values={k: v for k, (v, _) in rows.items()})
        if kind == "sign":
            values["families"][f]["aux"] = {state: "-0.08", "primary|local|T291.15": "1e-9"}
        bands["families"][f] = dict(claim=f.split(".")[0], quantity="invented", unit="invented",
                                    kind=kind, tol_abs=tol_abs, tol_rel=tol_rel,
                                    tol_source="invented", note="invented", rows={})  # fmt: skip
        for k, (v, floor) in rows.items():
            ref = abs(float(v)) if kind not in ("flag",) else 0.0
            band = max(tol_abs + tol_rel * ref, FLOOR_FACTOR * float(floor))
            bands["families"][f]["rows"][k] = dict(floor=floor, band=repr(band))
    table = dict(rows=[
        dict(family="C2.V_ghk_area", key=state, measure="v_zero", type="number", value="-0.0123459"),
        dict(family="C1.zero_K", key=state, measure="e_zero", type="number", value="-0.0999"),
        dict(family="C0.k_effect_sign_area", key=state, measure="effect_sign", type="number",
             value="-1.0"),
        dict(family="C0.k_effect_sign_area", key="primary|local|T291.15", measure="effect_sign",
             type="number", value="-1.0"),
        dict(family="C4.V_zero_glycine", key=f"{state}|P1e-8|a0.50", measure="v_zero", type="number",
             value="-0.020004"),
        dict(family="C6.v1_V_stall", key="n2|Nain21.0|Naout9.90|BP10.0|rB1.0|T291.15",
             measure="sym_stall", type="number", value="-0.0300001"),
        dict(family="C7.pump_heat_nonneg", key=f"{state}|V-0.04", measure="pump_heat_nonneg_at",
             type="flag", value="true"),
    ])  # fmt: skip
    for row in table["rows"]:  # As the engine's table holds them: the measure's parameters.
        row["params"] = mapped(row["family"], row["key"])[1]
    for name, data in ((VALUES, values), (BANDS, bands), ("engine_table.json", table)):
        (out / name).write_text(json.dumps(data, indent=1))
    return out


def selfcheck(out):
    """The reader's end-to-end check on the invented interface (no engine, no reference): each
    planted case's verdict, and each refusal before any value is read. Returns the failures."""
    import copy

    out = synthetic(out)
    values = json.loads((out / VALUES).read_text())
    bands = json.loads((out / BANDS).read_text())
    table = json.loads((out / "engine_table.json").read_text())
    failures = []

    def expect(name, condition):
        if not condition:
            failures.append(name)

    r = judge(table, values, bands)
    planted = {"C2.V_ghk_area": "pass", "C1.zero_K": "fail", "C0.k_effect_sign_area": "pass",
               "C4.V_zero_glycine": "pass", "C6.v1_V_stall": "pass", "C7.pump_heat_nonneg": "pass",
               "C0.V_ghk_unit": "info", "C6.v2_early_ratio_rest": "not_run",
               "C8.b_final_is_bath": "not_mappable"}  # fmt: skip
    for family, verdict in planted.items():
        expect(f"{family} {verdict}", r["families"][family] == verdict)
    outcomes = {(x["family"], x["key"]): x["outcome"] for x in r["rows"]}
    expect("a sign without power", outcomes[("C0.k_effect_sign_area", "primary|local|T291.15")]
           == "no_power")  # fmt: skip
    expect("overall fail", r["overall"] == "fail" and r["claims"]["C1"] == "fail")

    def refuses(name, t, v, b, **kw):
        try:
            judge(t, v, b, **kw)
            failures.append(f"{name}: not refused")
        except SystemExit:
            pass

    missing = copy.deepcopy(table)
    missing["rows"] = [x for x in missing["rows"] if x["family"] != "C2.V_ghk_area"]
    refuses("a missing row", missing, values, bands)
    poisoned = copy.deepcopy(values)
    for f in poisoned["families"].values():
        f["values"] = {k: "POISON" for k in f["values"]}
    refuses("a missing row before a poisoned value", missing, poisoned, bands)
    for name, change in (("a refused row", dict(type="refused", reason="invented")),
                         ("a step-unconverged row", dict(step_check=dict(converged=False))),
                         ("a flag row for an abs family", dict(type="flag", value="true"))):
        t = copy.deepcopy(table)
        t["rows"][0] |= change
        refuses(name, t, values, bands)
    unmapped = copy.deepcopy(bands)
    unmapped["families"]["C9.unknown"] = dict(kind="abs", unit="V", tol_abs=0, tol_rel=0,
                                              rows={"x": dict(floor="0", band="0")})  # fmt: skip
    refuses("an unmapped family", table, values, unmapped)
    band = copy.deepcopy(bands)
    band["families"]["C2.V_ghk_area"]["rows"]["primary|bath|T291.15"]["band"] = "2e-6"
    refuses("a disagreeing stored band", table, values, band)
    first = copy.deepcopy(table)
    first["rows"][0] |= dict(type="refused", reason="invented")
    manifest_rows = retry_manifest(first)["entries"]
    expect("the retry's manifest holds the inconclusive row alone",
           [(e["family"], e["key"]) for e in manifest_rows] == [("C2.V_ghk_area", table["rows"][0]["key"])])
    fixed = dict(rows=[dict(table["rows"][0], key="primary|bath|T291.150")])  # Met by number.
    merged = judge(merge(first, fixed), values, bands, after_retry=True)
    expect("a retried row judged in the merged table", merged["families"]["C2.V_ghk_area"] == "pass")
    still = dict(rows=[dict(table["rows"][0], type="refused", reason="again")])
    after = judge(merge(first, still), values, bands, after_retry=True)
    expect("after the retry: engine_refused, not testable",
           after["families"]["C2.V_ghk_area"] == "not_testable" and after["overall"] != "pass")
    try:
        merge(table, fixed)
        failures.append("a retry row over a judged row: not refused")
    except SystemExit:
        pass
    weak = copy.deepcopy(values)
    weak["families"]["C0.k_effect_sign_area"]["aux"]["primary|bath|T291.15"] = "1e-12"
    w = judge(table, weak, bands)
    expect("a powerless family is neutral; its claim, with nothing else passing, not testable",
           w["families"]["C0.k_effect_sign_area"] == "no_power" and w["claims"]["C0"] == "not_testable")
    lazy = judge(copy.deepcopy(table), lambda: values, bands)
    expect("values loaded lazily give the same verdicts", lazy["families"] == r["families"])
    try:
        judge(missing, lambda: (_ for _ in ()).throw(AssertionError("values opened")), bands)
    except SystemExit:
        pass
    except AssertionError:
        failures.append("the values file opened before resolution")
    # The token guard (erratum 1, revised): a key with a token its rule does not read, or a word or
    # value its builder does not know, is unmapped; the rows SEMANTICS-2.md settles map as stated.
    state = "primary|bath|T291.15"
    sym_key = "n2|Nain21|Naout9.9|BP10|rB1|T291.15"
    v2_key = "NaP19.9|BP0.1|BN0.0001|V-0.04"
    guard = (
        ("C2.V_ghk_area", f"{state}|x5", None), ("C2.V_ghk_area", f"{state}|foo", None),
        ("C5.g_J", "sym|x10", None), ("C5.g_J", "kir_g3", "c5_g_j"),
        ("C5.V1_ss", "sym|x10", "c5_v1"), ("C5.V1_ss", "kir_g3|x_gly3e-8|x1", None),
        ("C5.V1_ss", "sym|kir_g3|x1", None), ("C5.g_m", "sym|cell3", None),
        ("C5.junction_charge_sum", "kir_g3", "not_mappable"),
        ("C3.tau_lin", "S1_leaks_bath|d0.002", None), ("C3.tau_lin", "S10_leaks_bath", None),
        ("C7.relax_dQ", "S3_glycine3e-8_bath|k1", None),
        ("C7.pump_heat", f"{state}|Vghk", "pump_heat_at"), ("C7.pump_heat", f"{state}|V-0.04|Vghk", None),
        ("C7.pump_heat", "bracket_Cl_high|bath|T291.15|V-0.04", None),
        ("C7.pump_cell_charge_per_fmol", "cell", "pump_cell_charge_per_fmol"),
        ("C7.pump_cell_charge_per_fmol", "cells", None), ("C7.sym_cycle_counts", "n2|dA_in", None),
        ("C6.v1_V_stall", sym_key, "sym_stall"), ("C6.v1_V_stall", f"{sym_key}|off0.01", None),
        ("C6.v1_eq_ratio", "n2|Nain21|Naout9.9|V-0.04", "sym_eq_ratio_e2"),
        ("C6.v1_eq_ratio", "n2|Nain21|Naout9.9|T291.15|V-0.04", None),
        ("C6.v1_eq_ratio", "n2|Nain21|Naout9.9|V-0.04|Vrest_bath", None),
        ("C6.v1_capacity_ratio", "a|f0.5", "sym_capacity_ratio"),
        ("C6.v1_capacity_ratio", "c|f0.5", None), ("C6.S_hill", "NaP10|BP0.1", "sym_s_at"),
        ("C6.v2_V_stall", "NaP19.9|BP0.1|BN0.0001", "diag_stall"),
        ("C6.v2_ratio_Jm_Jp", f"{v2_key}|NaN21", None), ("C6.v2_alt_set_ratio", v2_key, "diag_ratio"),
        ("C6.v2_J_over_k", v2_key, "not_run"), ("C6.v2_early_ratio", "Vrest_bath", "not_run"),
        ("C6.v2_unknown", v2_key, None), ("C8.b_final_psi", "psi", "c8b_end_psi"),
        ("C8.b_final_psi", "phi", None), ("C8.bc_c_t", "A|t1", None),
    )  # fmt: skip
    for family, key, want in guard:
        m = mapped(family, key)
        expect(f"the token guard: {family} | {key}", (m[0] if m else None) == want)
    expect("state a read at 0 V", mapped("C6.v1_capacity_ratio", "a|f0.5")[1]["V"] == 0.0)
    expect("a refusal's reason names the unread token",
           "does not read: x" in refusal("C5.g_J", "sym|x10"))  # fmt: skip
    expect("check-keys passes the invented interface", check_keys(key_list_of(bands))[1] == [])
    unread = copy.deepcopy(bands)
    unread["families"]["C2.V_ghk_area"]["rows"][f"{state}|x5"] = dict(floor="0", band="0")
    expect("check-keys lists the unread token",
           [(f, k) for f, k, _ in check_keys(key_list_of(unread))[1]] == [("C2.V_ghk_area", f"{state}|x5")])
    try:
        judge(table, lambda: (_ for _ in ()).throw(AssertionError("values opened")), unread)
        failures.append("a key with a token its rule does not read: not refused")
    except SystemExit:
        pass
    except AssertionError:
        failures.append("the values file opened before the token guard refused")
    failures += selfcheck_e2(out)
    return failures


def interface_of(fams):
    """An invented interface ({family: (kind, tol_abs, tol_rel, {key: (reference, floor)})}) as the
    values and bands files' content, each band by the rule."""
    values, bands = dict(families={}), dict(families={})
    for f, (kind, tol_abs, tol_rel, rows) in fams.items():
        values["families"][f] = dict(values={k: v for k, (v, _) in rows.items()})
        bands["families"][f] = dict(claim=f.split(".")[0], quantity="invented", unit="invented",
                                    kind=kind, tol_abs=tol_abs, tol_rel=tol_rel,
                                    tol_source="invented", note="invented", rows={})  # fmt: skip
        for k, (v, floor) in rows.items():
            band = max(tol_abs + tol_rel * abs(float(v)), FLOOR_FACTOR * float(floor))
            bands["families"][f]["rows"][k] = dict(floor=floor, band=repr(band))
    return values, bands


def selfcheck_e2(out):
    """Erratum 2's cases on invented interfaces, tables and records (no engine, no reference): its
    mapping is erratum 1's but for the changed families, whose settings ride in their parameters;
    C7's ruled tolerance; the judge's carry of D329's rows and its refusals before any value is
    read; check_rule's refusal of a mutated mapping or setting; the same-engine check. Returns the
    failures."""
    import copy
    import tempfile

    failures = []

    def expect(name, condition):
        if not condition:
            failures.append(f"erratum 2: {name}")

    def refuses(name, fn, *args, **kw):
        try:
            fn(*args, **kw)
            failures.append(f"erratum 2: {name}: not refused")
        except SystemExit:
            pass

    def unopened():
        raise AssertionError("values opened")

    # 1. The mapping is erratum 1's but for the changed families' rules, each in place.
    first, ours = json.loads(ERRATUM_1.read_text())["mapping"], rule_mapping()
    pairs = list(zip(first["rules"], ours["rules"], strict=False))
    expect("as many rules as erratum 1", len(first["rules"]) == len(ours["rules"]))
    expect("every rule in erratum 1's order", all(a["family"] == b["family"] for a, b in pairs))
    expect("every unchanged rule is erratum 1's",
           all(a == b for a, b in pairs if a["family"] not in E2))
    expect("only changed families' rules differ",
           {a["family"] for a, b in pairs if a != b} <= set(E2))
    expect("the not-run and not-mappable rows are erratum 1's",
           first["not_run"] == ours["not_run"] and first["not_mappable"] == ours["not_mappable"])
    expect("the changed families", CHANGED == (
        "C6.v1_eq_ratio", "C6.v1_eq_x", "C7.pump_cell_charge_per_fmol", "C8.b_final_c",
        "C8.b_final_psi", "C8.bc_t_e"))  # fmt: skip

    # 2. The changed rows' readings, their settings in their parameters (invented keys).
    eq_key = "n3|Nain17|Naout55|V-0.06"
    expect("an equilibrium ratio at B_out 1e-5 mM on [1e-6, 1e8], the anchor bound 2^19 fmol",
           mapped("C6.v1_eq_ratio", eq_key) == ("sym_eq_ratio_e2", dict(
               BP=1e-5, T=291.15, domain=[1e-6, 1e8], anchor_bound_fmol=2.0**19, n=3.0, Nain=17.0,
               Naout=55.0, V=-0.06)))  # fmt: skip
    x = mapped("C6.v1_eq_x", "n3|Nain17|Naout55|Vrest_bath")
    expect("x at the equilibrium ratio, at Vrest", x[0] == "sym_eq_x_e2" and x[1]["Vrest"] == "bath"
           and x[1]["BP"] == 1e-5 and "V" not in x[1])  # fmt: skip
    expect("C8.b_final_c: the bare run at its 192 s horizon",
           mapped("C8.b_final_c", "K") == ("c8b_end_c", dict(species="K", horizon_s=192.0)))
    expect("C8.b_final_psi: the bare run at its 192 s horizon",
           mapped("C8.b_final_psi", "psi") == ("c8b_end_psi", dict(horizon_s=192.0)))
    expect("C8.bc_t_e: c_f the bare end state, the coupled run to 64 s",
           mapped("C8.bc_t_e", "Na") == ("c8b_t_e_end", dict(
               species="Na", horizon_s=192.0, coupled_horizon_s=64.0)))  # fmt: skip
    expect("C8.bc_c_t stays erratum 1's", mapped("C8.bc_c_t", "Na|t4")[0] == "c8b_at_saved")
    expect("C7's reading stays erratum 1's",
           mapped("C7.pump_cell_charge_per_fmol", "cell") == ("pump_cell_charge_per_fmol", {}))

    # 3. An invented interface with changed and unchanged families; a rerun table; D329-like rows.
    fams = {
        "C2.V_ghk_area": ("abs", 1e-6, 0.0, {"primary|bath|T291.15": ("-0.0123456", "1e-17")}),
        "C7.pump_cell_charge_per_fmol": ("abs", 0.0, 1e-12, {"cell": ("-1.0e-10", "1e-27")}),
        "C8.b_final_c": ("abs", 0.0, 1e-6, {"Na": ("40.0", "1e-16"), "K": ("0.8", "1e-16"),
                                             "Cl": ("3.0", "1e-16")}),
        "C6.v1_eq_ratio": ("abs", 0.0, 1e-6, {eq_key: ("2500.0", "1e-12")}),
        "C8.b_c_t": ("info", 0.0, 0.05, {"K|t64": ("0.81", "1e-16")}),
    }  # fmt: skip
    values, bands = interface_of(fams)
    engine = {("C7.pump_cell_charge_per_fmol", "cell"): repr(-1.0e-10 * (1 + 3.4e-11)),
              ("C8.b_final_c", "Na"): "40.00001", ("C8.b_final_c", "K"): "0.8000004",
              ("C8.b_final_c", "Cl"): "2.999999",
              ("C6.v1_eq_ratio", eq_key): "2500.001"}  # fmt: skip
    rerun = dict(rows=[])
    for (family, key), value in engine.items():
        measure, params = mapped(family, key)
        rerun["rows"].append(dict(family=family, key=key, measure=measure, params=params,
                                  type="number", value=value))  # fmt: skip
    new = judge(rerun, values, bands, only=CHANGED)
    expect("the rerun's families judged alone, and pass",
           new["families"] == {"C7.pump_cell_charge_per_fmol": "pass", "C8.b_final_c": "pass",
                               "C6.v1_eq_ratio": "pass"})  # fmt: skip
    c7 = next(r for r in new["rows"] if r["family"] == "C7.pump_cell_charge_per_fmol")
    expect("C7's ruled band is 1e-10 relative, the stored band recorded beside it",
           decimal.Decimal(c7["band"]) == decimal.Decimal("1e-20")
           and decimal.Decimal(c7["band_stored"]) == decimal.Decimal("1e-22"))
    expect("a 3.4e-11 relative gap fails the stored 1e-12 band",
           compare("abs", engine[("C7.pump_cell_charge_per_fmol", "cell")],
                   decimal.Decimal("-1.0e-10"), decimal.Decimal("1e-22")) == "fail")  # fmt: skip
    wide = copy.deepcopy(rerun)
    wide["rows"][0]["value"] = repr(-1.0e-10 * (1 + 2e-10))
    widened = judge(wide, values, bands, only=CHANGED)
    expect("a 2e-10 relative gap fails the ruled band",
           widened["families"]["C7.pump_cell_charge_per_fmol"] == "fail")
    disagree = copy.deepcopy(bands)
    disagree["families"]["C7.pump_cell_charge_per_fmol"]["rows"]["cell"]["band"] = "1e-20"
    refuses("a stored band that disagrees with the rule, under a ruling", judge, rerun, values,
            disagree, only=CHANGED)  # fmt: skip

    carried = dict(rows=[
        dict(family="C2.V_ghk_area", key="primary|bath|T291.15", outcome="pass", engine="x"),
        dict(family="C8.b_c_t", key="K|t64", outcome="info"),
        dict(family="C7.pump_cell_charge_per_fmol", key="cell", outcome="fail"),
        *(dict(family="C8.b_final_c", key=s, outcome="fail") for s in ("Na", "K", "Cl")),
        dict(family="C6.v1_eq_ratio", key=eq_key, outcome="engine_refused", reason="refused"),
    ])  # fmt: skip
    v = carry(carried, new, bands)
    expect("the carry: the changed families' new outcomes, the others D329's",
           v["overall"] == "pass" and v["families"]["C2.V_ghk_area"] == "pass"
           and v["families"]["C8.b_c_t"] == "info" and v["families"]["C8.b_final_c"] == "pass"
           and v["counts"] == {"pass": 6, "info": 1})
    expect("a carried row keeps family, key, outcome and reason only",
           all(set(r) <= {"family", "key", "outcome", "reason"} for r in v["rows"]
               if r["family"] == "C2.V_ghk_area"))  # fmt: skip
    failed = copy.deepcopy(carried)
    failed["rows"][0]["outcome"] = "fail"
    expect("a carried fail stands", carry(failed, new, bands)["overall"] == "fail")
    lacking = dict(rows=carried["rows"][1:])
    refuses("a carried file lacking an unchanged row", carry, lacking, new, bands)
    extra = dict(rows=[*carried["rows"], dict(family="C2.V_ghk_area", key="x", outcome="pass")])
    refuses("a carried file with a row outside the interface", carry, extra, new, bands)
    stray = copy.deepcopy(rerun)
    stray["rows"].append(dict(family="C2.V_ghk_area", key="primary|bath|T291.15", measure="v_zero",
                              params=mapped("C2.V_ghk_area", "primary|bath|T291.15")[1],
                              type="number", value="-0.0123459"))  # fmt: skip
    refuses("a rerun table with a row of an unchanged family", judge, stray, unopened, bands,
            only=CHANGED)  # fmt: skip
    short = copy.deepcopy(rerun)
    short["rows"] = [r for r in short["rows"] if r["key"] != "K"]
    try:
        judge(short, unopened, bands, only=CHANGED)
        failures.append("erratum 2: a rerun table lacking a changed row: not refused")
    except SystemExit:
        pass
    except AssertionError:
        failures.append("erratum 2: the values file opened before a missing changed row refused")
    for name, change in (("B_out", ("C6.v1_eq_ratio", "BP", 1e-4)),
                         ("ratio domain", ("C6.v1_eq_ratio", "domain", [1e-6, 1e6])),
                         ("bare horizon", ("C8.b_final_c", "horizon_s", 64.0))):
        other = copy.deepcopy(rerun)
        for r in other["rows"]:
            if r["family"] == change[0]:
                r["params"][change[1]] = change[2]
        try:
            judge(other, unopened, bands, only=CHANGED)
            failures.append(f"erratum 2: a table row built with another {name}: not refused")
        except SystemExit:
            pass
        except AssertionError:
            failures.append(f"erratum 2: the values file opened before another {name} refused")
    # The retry through the carry: a refused rerun row, re-measured once, judged after the retry.
    refused = copy.deepcopy(rerun)
    first_row = next(r for r in refused["rows"] if r["family"] == "C6.v1_eq_ratio")
    first_row.update(type="refused", reason="invented")
    first_row.pop("value")
    retry_rows = retry_manifest(refused)["entries"]
    expect("the retry's manifest holds the refused rerun row alone",
           [(e["family"], e["key"]) for e in retry_rows] == [("C6.v1_eq_ratio", eq_key)])
    refuses("the refused rerun row before the retry", judge, refused, values, bands, only=CHANGED)
    again = dict(rows=[dict(e, type="refused", reason="again") for e in retry_rows])
    still = carry(carried, judge(merge(refused, again), values, bands, after_retry=True,
                                 only=CHANGED), bands)  # fmt: skip
    expect("after the retry, a row still refused is engine_refused, its family and XC0 untestable",
           still["families"]["C6.v1_eq_ratio"] == "not_testable"
           and still["counts"].get("engine_refused") == 1 and still["overall"] == "not_testable")
    fixed = dict(rows=[dict(e, type="number", value="2500.001") for e in retry_rows])
    recovered = carry(carried, judge(merge(refused, fixed), values, bands, after_retry=True,
                                     only=CHANGED), bands)  # fmt: skip
    expect("after the retry, a recovered row is judged",
           recovered["families"]["C6.v1_eq_ratio"] == "pass" and recovered["overall"] == "pass")

    key_list = {f: dict(kind=k, unit="u", keys=sorted(rows)) for f, (k, _, _, rows) in fams.items()}
    counts, unmapped = check_keys(key_list)
    expect("check-keys counts the changed rows by family", unmapped == [] and counts["changed"] == {
        "C6.v1_eq_ratio": 1, "C7.pump_cell_charge_per_fmol": 1, "C8.b_final_c": 3})
    rerun_manifest = manifest(key_list, changed_only=True)["entries"]
    expect("the rerun's manifest holds the changed rows alone, C8's with the step tolerance",
           sorted((e["family"], e["key"]) for e in rerun_manifest) == sorted(engine)
           and all(e.get("step_tolerance") == {"rel": 0.05} for e in rerun_manifest
                   if e["family"].startswith("C8.")))  # fmt: skip

    # 4. check_rule refuses unless erratum 2's mapping and settings are this module's.
    if not ERRATUM.exists():
        failures.append("erratum 2: no erratum 2 file to check")
        return failures
    text = ERRATUM.read_text()
    try:
        check_rule()
    except SystemExit:
        failures.append("erratum 2: check_rule refused the registered erratum 2")
    settings = ("mapping", "settings")
    mutations = (
        ("B_out", (*settings, "eq_ratio", "B_out_mM"), 1e-4),
        ("ratio domain", (*settings, "eq_ratio", "domain"), [1e-6, 1e6]),
        ("anchor bound", (*settings, "eq_ratio", "anchor_bound_fmol"), 2.0**20),
        ("bare horizon", (*settings, "c8b_horizon_s", "bare"), 128.0),
        ("coupled horizon", (*settings, "c8b_horizon_s", "coupled"), 192.0),
        ("C7's ruled tolerance", (*settings, "tolerance_rulings", "C7.pump_cell_charge_per_fmol",
                                  "tol_rel"), 1e-11),
        ("changed families", ("mapping", "changed"), list(CHANGED[:-1])),
        ("rule's measure", ("mapping", "rules", 0, "measure"), "v_zero"),
        ("erratum number", ("erratum",), 1),
    )  # fmt: skip
    out = Path(out) / "erratum-2"
    out.mkdir(parents=True, exist_ok=True)
    for name, path, value in mutations:
        e = json.loads(text)
        node = e
        for step in path[:-1]:
            node = node[step]
        node[path[-1]] = value
        (out / "mutated.json").write_text(json.dumps(e))
        refuses(f"check_rule with a mutated {name}", check_rule, out / "mutated.json")
    saved = SETTINGS["eq_ratio"]["B_out_mM"]
    SETTINGS["eq_ratio"]["B_out_mM"] = 1e-4
    try:
        refuses("check_rule with the module's B_out changed", check_rule)
    finally:
        SETTINGS["eq_ratio"]["B_out_mM"] = saved

    # 5. The same-engine check and the carried file's digest, on invented records.
    with tempfile.TemporaryDirectory() as tmp:

        def snap(name, files):
            d = Path(tmp) / name
            d.mkdir()
            record = {"files": {p: {"sha256": h} for p, h in files.items()}}
            (d / "SNAPSHOT.json").write_text(json.dumps(record))
            return d

        def table_at(d):
            return {"record": {"source": {"snapshot": str(d)}}}

        base = snap("base", {"src/a.py": "1", "src/b.py": "2", "validation/x.py": "3"})
        try:
            same_engine(table_at(snap("same", {"src/a.py": "1", "src/b.py": "2",
                                               "validation/x.py": "4"})), base)  # fmt: skip
        except SystemExit:
            failures.append("erratum 2: the same engine sources refused")
        refuses("a changed engine source", same_engine,
                table_at(snap("other", {"src/a.py": "1", "src/b.py": "5"})), base)
        refuses("a missing engine source", same_engine, table_at(snap("fewer", {"src/a.py": "1"})),
                base)  # fmt: skip
        (Path(tmp) / "carried.json").write_bytes(b"{}")
        refuses("a carried file with another digest", file_digest, Path(tmp) / "carried.json",
                "0" * 64)  # fmt: skip
    return failures


def structure(path):
    """The key layout of an interface-shaped file: family names, their entries' keys and the number
    of rows; no value is printed."""
    data = json.loads(Path(path).read_text())
    for family, entry in sorted(data.get("families", {}).items()):
        parts = {k: (len(v) if isinstance(v, dict) else type(v).__name__) for k, v in entry.items()}
        print(family, parts)


def main(argv=None):
    a = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = a.add_subparsers(dest="command", required=True)
    k = sub.add_parser("keys")
    k.add_argument("bands")
    k.add_argument("out")
    k.add_argument("--with-text", action="store_true", help="each family's claim and quantity")
    ck = sub.add_parser("check-keys", help="the token guard over the keys stage's output")
    ck.add_argument("keys")
    m = sub.add_parser("manifest")
    m.add_argument("keys")
    m.add_argument("out")
    m.add_argument("--calibrations", action="store_true", help="T1 and T2's readings (unscored)")
    m.add_argument("--changed", action="store_true", help="erratum 2's rerun: the changed families")
    j = sub.add_parser("judge")
    for name in ("table", "values", "bands", "out"):
        j.add_argument(name)
    j.add_argument("--retry", help="the retry's table, merged over the first (after-retry)")
    j.add_argument("--carry", required=True,
                   help="erratum 2: D329's judge.json, its unchanged families' rows carried")
    cc = sub.add_parser("carry-check", help="erratum 2: the carried judge.json against the keys")
    cc.add_argument("keys")
    cc.add_argument("carried")
    rm = sub.add_parser("retry-manifest")
    rm.add_argument("table")
    rm.add_argument("out")
    s = sub.add_parser("synthetic")
    s.add_argument("out")
    st = sub.add_parser("structure")
    st.add_argument("file")
    g = sub.add_parser("grammar")
    g.add_argument("out")
    c = sub.add_parser("selfcheck")
    c.add_argument("out")
    args = a.parse_args(argv)
    if args.command == "keys":
        data = json.dumps(keys(args.bands, with_text=args.with_text), indent=1, sort_keys=True)
        Path(args.out).write_text(data)
        print(hashlib.sha256(data.encode()).hexdigest())
    elif args.command == "check-keys":
        counts, unmapped = check_keys(json.loads(Path(args.keys).read_text()))
        print(json.dumps(counts))
        for family, key, why in unmapped:
            print(f"unmapped: {family} | {key}: {why}")
        return 1 if unmapped else 0
    elif args.command == "manifest":
        result = manifest(json.loads(Path(args.keys).read_text()), changed_only=args.changed)
        if result["unmapped"]:  # The token guard and the mapping refuse before any table is built.
            for family, key, why in result["unmapped"]:
                print(f"unmapped: {family} | {key}: {why}")
            print(f"refused: {len(result['unmapped'])} unmapped rows; no manifest written")
            return 1
        if args.calibrations:  # D312: T1 and T2 are unscored calibrations, reported beside the verdict.
            result["entries"] += calibrations()
        Path(args.out).write_text(json.dumps(result, indent=1))
        print(f"{len(result['entries'])} rows mapped, {len(result['not_run'])} not run or not "
              f"mappable, 0 unmapped")
    elif args.command == "carry-check":
        # Names and keys only: the carried file's digest and rows against the keys stage's rows.
        base = check_rule()["erratum"]["rerun"]["base"]
        file_digest(args.carried, base["judge_sha256"])
        key_list = json.loads(Path(args.keys).read_text())
        carried = json.loads(Path(args.carried).read_text())
        rows = {(r["family"], r["key"]) for r in carried["rows"]}
        want = {(f, k) for f, e in key_list.items() for k in e["keys"]}
        kept = {(f, k) for f, k in rows if f not in CHANGED}
        print(json.dumps(dict(carried_rows=len(carried["rows"]), distinct=len(rows),
                              interface_rows=len(want), carried_unchanged=len(kept),
                              changed_rows=len(want) - len(kept), equal=rows == want)))  # fmt: skip
        return 0 if rows == want and len(rows) == len(carried["rows"]) else 1
    elif args.command == "judge":
        rule = check_rule()
        base = rule["erratum"]["rerun"]["base"]
        file_digest(Path(base["snapshot"]) / "SNAPSHOT.json", base["snapshot_record_sha256"])
        table = json.loads(Path(args.table).read_text())
        check_table(table, rule)
        same_engine(table, base["snapshot"])
        digests = dict(engine_table_sha256=hashlib.sha256(Path(args.table).read_bytes()).hexdigest())
        if args.retry:
            retry = json.loads(Path(args.retry).read_text())
            check_table(retry, rule)
            same_engine(retry, base["snapshot"])
            if not retry["record"].get("retry"):
                raise SystemExit("refused: the retry table was not built with --retry")
            digests["retry_table_sha256"] = hashlib.sha256(Path(args.retry).read_bytes()).hexdigest()
            table = merge(table, retry)
        digests["carried_judge_sha256"] = file_digest(args.carry, base["judge_sha256"])
        bands = json.loads(Path(args.bands).read_text())
        new = judge(table, lambda: json.loads(Path(args.values).read_text()), bands,
                    after_retry=bool(args.retry), only=CHANGED)  # fmt: skip
        result = carry(json.loads(Path(args.carry).read_text()), new, bands)
        result |= digests
        Path(args.out).write_text(json.dumps(result, indent=1))
        print(json.dumps(dict(overall=result["overall"], claims=result["claims"],
                              counts=result["counts"]), indent=1))  # fmt: skip
    elif args.command == "synthetic":
        print(synthetic(args.out))
    elif args.command == "structure":
        structure(args.file)
    elif args.command == "retry-manifest":
        result = retry_manifest(json.loads(Path(args.table).read_text()))
        Path(args.out).write_text(json.dumps(result, indent=1))
        print(f"{len(result['entries'])} rows to retry")
    elif args.command == "selfcheck":
        failures = selfcheck(args.out)
        print("selfcheck: " + ("passed" if not failures else "FAILED: " + "; ".join(failures)))
        return 1 if failures else 0
    elif args.command == "grammar":
        result = manifest(grammar())
        result["entries"] += calibrations()
        Path(args.out).write_text(json.dumps(result, indent=1))
        print(f"{len(result['entries'])} rows, {len(result['unmapped'])} unmapped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
