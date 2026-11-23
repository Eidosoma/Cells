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
- `manifest KEYS OUT`: each compared row's engine reading (MAPPING) as xc0_engine's manifest; rows no
  mapping covers are listed apart (names and keys only).
- `judge TABLE VALUES BANDS OUT [--retry RETRY_TABLE]`: first resolves every compared row to one table
  row, with the values file unopened (a refusal prints family names and keys only); then loads the
  values file, finds every compared key in it, and only then reads values, aux and bands, recomputes
  each abs row's band by the rule from its stored floor and tolerances (a stored band that disagrees
  refuses; a sign row's stored band decides its power), and gives the verdicts. With --retry, the
  retry table's rows replace the first table's inconclusive rows and the judgement is after-retry.
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
    is kept as {"word": ...} and the mapping refuses it."""
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
    if isinstance(a, str) or isinstance(b, str):
        return a == b
    return a == b or abs(a - b) <= MATCH_RTOL * max(abs(a), abs(b))


def same_params(a, b):
    return set(a) == set(b) and all(same(a[k], b[k]) for k in a)


# ------------------------------------------------------------------ the mapping (the rule's)

# Each rule: (family pattern, engine measure or None, params builder, needs). A family no rule
# matches is unmapped: the judge refuses it (its name and keys printed). `needs` lists the parsed
# parameters a key must carry; a key lacking one is unmapped. NOT_RUN lists the rows the rule does
# not run, with the reason (the lead's ruling of 23 November 2026 for version 2's kinetic rows).
STATE = ("ion_set", "exterior", "T")


def keep(*names, **fixed):
    def build(family, params):
        return {**{n: params[n] for n in names if n in params}, **fixed}

    return build


def ion_from_family(prefix):
    def build(family, params):
        return {**{n: params[n] for n in STATE}, "ion": family[len(prefix):]}

    return build


def scenario(*names):
    def build(family, params):
        out = {n: params[n] for n in names if n in params}
        out["scenario"] = params["word"]
        if "d" in params:
            out["delta"] = params["d"]
        return out

    return build


def two_cell(family, params):
    out = {"x": params.get("x", 1.0)}
    word = params.get("word")
    if word == "sym":
        return out
    for name in ("kir_g", "x_gly"):
        if name in params:
            out[name] = params[name]
            return out
    raise KeyError("no two-cell scenario")


def symporter(family, params):
    out = {n: params[n] for n in ("n", "Nain", "Naout", "BP", "rB", "T", "off", "V", "Vrest", "f")
           if n in params}  # fmt: skip
    return out


def voltage_named(params):
    if not any(n in params for n in ("V", "off", "Vrest")):
        raise KeyError("no voltage")


def eq_ratio(family, params):
    """The equilibrium ratio: J's root over B_in/B_out, which version 1's J = k a S (1 - e^x) puts
    where x = 0 whatever B_out is (S > 0), so a key without BP reads the declared dose bath's B."""
    voltage_named(params)
    return {"BP": 10.0, "T": 291.15, **symporter(family, params)}


def capacity(family, params):
    voltage_named(params)
    return symporter(family, params)


def diagram(family, params):
    """Version 2's keys (NaP, BP, BN[, V]): Na_N 21 mM and 291.15 K, fixed in the reference's
    generator (SEMANTICS.md, reading 7), unless the key names them."""
    out = {"n": 2, "Nain": params.get("NaN", 21.0), "Naout": params["NaP"], "BP": params["BP"],
           "rB": params["BN"] / params["BP"], "T": params.get("T", 291.15)}
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
    return {"scenario": params["word"], "k": params["k"]}


def two_cell_cell(family, params):
    out = two_cell(family, {k: v for k, v in params.items() if k != "cell"})
    out["cell"] = f"cell{int(params['cell'])}"
    return out


def capacity_b(family, params):
    """C6.v1_capacity_ratio's state b (SEMANTICS.md, reading 7): Na_N 21, Na_P 19.9, B_N 0.0001,
    B_P 10 mM, -0.0899 V, n 2, 291.15 K; state a's voltage is not stated (not mappable)."""
    if params.get("word") != "b":
        raise KeyError("only state b is defined")
    return {"n": 2, "Nain": 21.0, "Naout": 19.9, "BP": 10.0, "rB": 0.0001 / 10.0, "T": 291.15,
            "V": -0.0899, "f": params["f"]}


def pump_counts(family, params):
    measure = {"dNa_cell": "pump_counts_Na", "dK_cell": "pump_counts_K",
               "outward_charge": "pump_outward_charge"}[params["word"]]
    return {"measure": measure}


def pump_state(family, params):
    out = {"ion_set": params["ion_set"], "exterior": params["exterior"], "T": params["T"]}
    if params.get("word") == "Vghk":
        out["word"] = "Vghk"
    elif "V" in params:
        out["V"] = params["V"]
    else:
        raise KeyError("no voltage")
    return out


def sym_offset(family, params):
    return {n: params[n] for n in ("n", "Nain", "Naout", "BP", "rB", "T", "off")}


def sym_at_stall(family, params):
    return {**{n: params[n] for n in ("n", "Nain", "Naout", "BP", "rB", "T")}, "off": 0.0}


def counts_word(family, params):
    return {"n": params["n"], "word": params["word"]}


def c8_species(family, params):
    if params.get("word") not in ("Na", "K", "Cl"):
        raise KeyError("no species")
    return {"species": params["word"]}


def c8_species_t(family, params):
    out = c8_species(family, params)
    out["t"] = params["t"]
    return out


def c8_t(family, params):
    return {"t": params["t"]}


def cl_sign_side(family, params):
    return {"ion_set": params["ion_set"], "exterior": params["exterior"], "T": params["T"],
            "ion": "Cl"}


SYM = ("n", "Nain", "Naout", "BP", "rB", "T")
OFF = (*SYM, "off")
PUMP = ("ion_set", "exterior", "T")
# The erratum's mapping (erratum 1, 23 November 2026, from the tagged reader's keys stage and the
# confirmer's SEMANTICS.md). Each rule: (family pattern, engine measure, params builder, needs).
MAPPING = (
    (r"^C0\.E_(K|Na|Cl)$", "e_zero", ion_from_family("C0.E_"), STATE),
    (r"^C0\.V_ghk_area$", "v_zero", keep(*STATE), STATE),
    (r"^C0\.k_effect_sign_area$", "effect_sign", keep(*STATE, ion="K"), STATE),
    (r"^C0\.cl_effect_sign_area$", "effect_sign", keep(*STATE, ion="Cl"), STATE),
    (r"^C0\.cl_bound_area$", "cl_bound", keep(*STATE), STATE),
    (r"^C0\.cl_i_critical_area$", "cl_threshold", keep(*STATE), STATE),
    (r"^C0\.cl_i_threshold_V(-?[0-9.]+)$", "cl_threshold",
     from_family(r"^C0\.cl_i_threshold_V(-?[0-9.]+)$", "V"), STATE),
    (r"^C0\.feasible_19p4_area$", "feasible_19p4", keep(*STATE), STATE),
    (r"^C1\.zero_(K|Cl)$", "e_zero", ion_from_family("C1.zero_"), STATE),
    (r"^C1\.sign_I_(K|Cl)_dV(-?[0-9.]+)$", "ion_current", sign_current, STATE),
    (r"^C1\.kir_zero_at_EK$", "kir_current_ek", with_state(u=0.0), STATE),
    (r"^C1\.kir_I_u(-?[0-9.]+)$", "kir_current_ek", from_family(r"^C1\.kir_I_u(-?[0-9.]+)$", "u"),
     STATE),
    (r"^C1\.kir_slope_u(-?[0-9.]+)$", "kir_slope_ek",
     from_family(r"^C1\.kir_slope_u(-?[0-9.]+)$", "u"), STATE),
    (r"^C1\.kir_sqrtKo_ratio$", "kir_sqrtko_ratio", keep("ion_set", "T"), ("ion_set", "T")),
    (r"^C2\.V_ghk_area$", "v_zero", keep(*STATE), STATE),
    (r"^C2\.sign_dVdt_dV(-?[0-9.]+)$", "dvdt_offset",
     from_family(r"^C2\.sign_dVdt_dV(-?[0-9.]+)$", "offset"), STATE),
    (r"^C3\.V_inf$", "c3_v_inf", scenario(), ("word",)),
    (r"^C3\.g$", "c3_g", scenario(), ("word",)),
    (r"^C3\.tau_lin$", "tau_lin", scenario(), ("word",)),
    (r"^C3\.tau_doubling$", "c3_tau_doubling", scenario(), ("word",)),
    (r"^C3\.tau_fit$", "tau_fit", scenario(), ("word", "d")),
    (r"^C3\.ratio_t$", "ratio_t", scenario("k"), ("word", "d", "k")),
    (r"^C3\.Q_over_CV_error$", "c3_q_minus_cv", scenario("k"), ("word", "d", "k")),
    (r"^C4\.V_zero_both$", "v_zero", with_state(P=3e-8, g=3.0, a=1.0), STATE),
    (r"^C4\.V_zero_glycine$", "v_zero", keep(*STATE, "P", "a"), (*STATE, "P", "a")),
    (r"^C4\.V_zero_kir$", "v_zero", keep(*STATE, "g", "a"), (*STATE, "g", "a")),
    (r"^C4\.shift_kir$", "shift", keep(*STATE, "g", "a"), (*STATE, "g", "a")),
    (r"^C4\.shift_glycine_sign$", "shift", with_state(P=1e-8, a=1.0), STATE),
    (r"^C4\.monotone_kir$", "c4_monotone_kir", keep(*STATE), STATE),
    (r"^C4\.monotone_glycine$", "c4_monotone_glycine", keep(*STATE), STATE),
    (r"^C4\.flux_at_a0$", "c4_flux_at_a0", keep(*STATE, "V"), (*STATE, "V")),
    (r"^C5\.V1_ss$", "c5_v1", two_cell, ()),
    (r"^C5\.V2_ss$", "c5_v2", two_cell, ()),
    (r"^C5\.tau_common$", "c5_tau_common", two_cell, ()),
    (r"^C5\.tau_diff$", "c5_tau_diff", two_cell, ()),
    (r"^C5\.V_limit$", "c5_v_limit", two_cell, ()),
    (r"^C5\.g_J$", "c5_g_j", two_cell, ()),
    (r"^C5\.g_m$", "c5_g_m", two_cell_cell, ("cell",)),
    (r"^C5\.junction_charge_sum$", "c5_junction_charge_sum", two_cell, ()),
    (r"^C5\.tau_fit_common$", "c5_tau_fit_common", two_cell, ()),
    (r"^C5\.tau_fit_diff$", "c5_tau_fit_diff", two_cell, ()),
    (r"^C6\.S_hill$", "sym_s_at", keep("NaP", "BP"), ("NaP", "BP")),
    (r"^C6\.v1_V_stall$", "sym_stall", symporter, SYM),
    (r"^C6\.v1_J_at_stall$", "sym_j", sym_at_stall, SYM),
    (r"^C6\.v1_dJdV_at_stall$", "sym_dj_dv", sym_at_stall, SYM),
    (r"^C6\.v1_J_offset$", "sym_j", sym_offset, OFF),
    (r"^C6\.v1_ratio_Jm_Jp$", "sym_ratio", sym_offset, OFF),
    (r"^C6\.v1_sign_J_offset$", "sym_j", sym_offset, OFF),
    (r"^C6\.v1_x_offset$", "sym_x", sym_offset, OFF),
    (r"^C6\.v1_eq_ratio$", "sym_eq_ratio", eq_ratio, ("n", "Nain", "Naout")),
    (r"^C6\.v1_eq_x$", "sym_eq_x", eq_ratio, ("n", "Nain", "Naout")),
    (r"^C6\.v1_capacity_ratio$", "sym_capacity_ratio", capacity_b, ("f",)),
    (r"^C6\.v2_V_stall$", "diag_stall", diagram, ("NaP", "BP", "BN")),
    (r"^C6\.v2_ratio_Jm_Jp$", "diag_ratio", diagram, ("NaP", "BP", "BN", "V")),
    (r"^C7\.pump_cycle_counts$", "pump_counts", pump_counts, ("word",)),
    (r"^C7\.pump_cell_charge_per_fmol$", "pump_cell_charge_per_fmol", keep(), ()),
    (r"^C7\.pump_dG_atp$", "pump_dG_atp_at", pump_state, PUMP),
    (r"^C7\.pump_dG_chem$", "pump_dG_chem_at", pump_state, PUMP),
    (r"^C7\.pump_dU_cap$", "pump_dU_cap_at", pump_state, PUMP),
    (r"^C7\.pump_heat$", "pump_heat_at", pump_state, PUMP),
    (r"^C7\.pump_heat_nonneg$", "pump_heat_nonneg_at", pump_state, PUMP),
    (r"^C7\.relax_dQ$", "c7_relax_dQ", scenario_k, ("word", "k")),
    (r"^C7\.relax_charge_identity$", "c7_relax_identity", scenario_k, ("word", "k")),
    (r"^C7\.sym_dG_chem$", "sym_dG_chem", sym_offset, OFF),
    (r"^C7\.sym_dU_cap$", "sym_dU_cap", sym_offset, OFF),
    (r"^C7\.sym_heat_per_cycle$", "sym_heat_per_cycle", sym_offset, OFF),
    (r"^C7\.sym_heat_power$", "sym_heat_power", sym_offset, OFF),
    (r"^C7\.sym_heat_nonneg$", "sym_heat_nonneg", sym_offset, OFF),
    (r"^C7\.sym_cycle_counts$", "sym_counts", counts_word, ("n", "word")),
    (r"^C8\.a_dE_K$", "c8a_e_K", keep("ion_set", "T"), ("ion_set", "T")),
    (r"^C8\.a_dV_ghk_area$", "c8a_v_zero", keep("ion_set", "T"), ("ion_set", "T")),
    (r"^C8\.a_cl_sign_bath_vs_local$", "effect_sign", cl_sign_side, ("ion_set", "exterior", "T")),
    (r"^C8\.b_final_c$", "c8b_final_saved", c8_species, ("word",)),
    (r"^C8\.b_final_psi$", "c8b_psi_final_saved", keep(), ()),
    (r"^C8\.bc_t_e$", "c8b_t_e_saved", c8_species, ("word",)),
    (r"^C8\.bc_c_t$", "c8b_at_saved", c8_species_t, ("word", "t")),
    (r"^C8\.bc_psi_t$", "c8b_psi_at_saved", c8_t, ("t",)),
)  # fmt: skip
NOT_RUN = (
    (r"^C6\.v2_early", "not run on main: cells.na2_anion_symport_diagram@1 fixes zeta at 0 on "
     "e3/e5/e6/e7 (b_P, b_N, na2_N, na1_N), so DESIGN §3.4's charge placement cannot be declared "
     "and the early-uptake ratio, which depends on it, is not the design's (the lead, 23 November "
     "2026; a declared zeta on every edge is queued with the kinds lane as a general feature)"),
    (r"^C6\.v2_(J|KA|king|ka)", "not run on main: the King-Altman J depends on the charge placement "
     "(as above)"),
    (r"^C6\.S_half$", "not run: its states hold 1e12 mM, which the engine cannot declare (a node's "
     "initial inventory must hold its charge anchor to 1e-20 C, beyond float64 at 1e15 fmol)"),
    (r"^C8\.a_dV_ghk_unit$", "not run: an unweighted (unit) row, info by the lead's ruling in the "
     "references' amendment (REFERENCES_USAGE.md, after the erratum), though its bands entry says "
     "abs; the engine has no unweighted membrane"),
)  # fmt: skip
# Rows the confirmer's SEMANTICS.md leaves without a definition or a needed value: refused at
# judging as not mappable (the lead, 23 November 2026), reported, and neutral in the verdicts.
NOT_MAPPABLE = (
    (r"^C4\.T1_reachable$", None, "SEMANTICS.md defines no C4.T1_reachable"),
    (r"^C5\.V_dev_t$", None, "its times need the generator's step count N: 'needs a value; not "
     "stated' (SEMANTICS.md, C5's fits)"),
    (r"^C6\.J_over_k_grid$", None, "the state behind 'dG_cyc far negative' (the N end, V) is not "
     "stated (SEMANTICS.md, reading 7: names and keys only)"),
    (r"^C6\.v1_n1_(J|dJ_over_V)$", None, "the n = 1 rows' other concentrations are not stated "
     "(SEMANTICS.md, reading 7: names and keys only)"),
    (r"^C6\.v1_capacity_ratio$", "a", "state a's voltage: 'needs a value; not stated' "
     "(SEMANTICS.md, reading 7)"),
    (r"^C6\.v2_alt_set_ratio$", None, "its second constant set: 'needs a value; not stated' "
     "(SEMANTICS.md, reading 7)"),
    (r"^C8\.b_final_is_bath$", None, "its criterion: 'needs a value; not stated' (SEMANTICS.md, "
     "C8 (b))"),
)  # fmt: skip


def mapped(family, key):
    """(measure, params) for one compared row, ('not_run', reason), ('not_mappable', reason), or
    None (unmapped: the judge refuses)."""
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
    for pattern, measure, build, needs in MAPPING:
        if not re.search(pattern, family):
            continue
        if any(n not in params for n in needs):
            return None
        try:
            built = build(family, params)
        except (KeyError, AttributeError):
            return None
        if "measure" in built:  # A builder that picks the measure by the key's word.
            return built.pop("measure"), built
        return measure, built
    return None


RULE = HERE / "xc0_rule.json"  # Tagged xc0-rule-registered-2026-11-23; kept as tagged.
ERRATUM = HERE / "xc0_rule_erratum_1.json"  # Erratum 1: the mapping this module now holds.


def rule_mapping():
    """The mapping as the erratum renders it, from this module (one source)."""
    return dict(
        rules=[dict(family=p, measure=m, needs=list(n)) for p, m, b, n in MAPPING],
        not_run=[dict(family=p, reason=r) for p, r in NOT_RUN],
        not_mappable=[dict(family=p, key_word=w, reason=r) for p, w, r in NOT_MAPPABLE],
    )


def check_rule(path=ERRATUM):
    """Refuses when the registered erratum's mapping is not this module's. Returns the tagged rule
    with the erratum's entries over its own, the erratum itself under "erratum"."""
    erratum = json.loads(Path(path).read_text())
    if erratum["mapping"] != rule_mapping():
        raise SystemExit(f"refused: {path}'s mapping is not the reader's")
    rule = json.loads(RULE.read_text())
    return {**rule, **{k: v for k, v in erratum.items() if k in rule}, "erratum": erratum}


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


def manifest(key_list):
    """The engine manifest for the compared rows, and the unmapped and not-run rows apart."""
    entries, unmapped, not_run = [], [], []
    for family, entry in sorted(key_list.items()):
        if entry["kind"] == "info":
            continue
        for key in entry["keys"]:
            m = mapped(family, key)
            if m is None:
                unmapped.append((family, key))
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
    such a row is judged as engine_refused."""
    rows = table_rows(table)
    resolved, problems = {}, []
    for family, entry in sorted(key_list.items()):
        if entry["kind"] == "info":
            continue
        for key in entry["keys"]:
            m = mapped(family, key)
            if m is None:
                problems.append(("unmapped", family, key))
                continue
            if m[0] in ("not_run", "not_mappable"):
                resolved[(family, key)] = m
                continue
            params = parse_key(key)
            hits = [r for f, p, measure, r in rows if f == family and measure == m[0]
                    and same_params(p, params)]  # fmt: skip
            if len(hits) != 1:
                problems.append(("no table row" if not hits else "several table rows", family, key))
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


def judge(table, values, bands, *, after_retry=False):
    """The verdicts. `values` is the values file's content, or a function that loads it: it is
    loaded only after every compared row resolves to a table row (a refusal reads no value), and
    then only after every compared key is found in it."""
    key_list = {f: dict(kind=e["kind"], unit=e["unit"], keys=sorted(e["rows"]))
                for f, e in bands["families"].items()}  # fmt: skip
    for family, entry in key_list.items():
        if entry["kind"] not in KINDS:
            raise SystemExit(f"refused: family {family} has kind {entry['kind']!r}")
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
        if kind == "abs":  # The band rule is checked where REFERENCES_USAGE.md defines its terms.
            band = band_of(entry, row, reference)
            stored = number(str(row["band"]))
            if abs(stored - band) > decimal.Decimal("1e-12") * max(abs(band), decimal.Decimal(
                    "1e-300")):  # fmt: skip
                raise SystemExit(f"refused: {family} | {key}: stored band disagrees with the rule")
        elif kind == "sign":  # The stored band decides power (|aux| > band).
            band = number(str(row["band"]))
        aux = None
        if kind == "sign":
            aux = number(values["families"][family]["aux"][key])
        outcome = compare(kind, engine_text(item), reference, band, aux)
        rows.append(dict(family=family, key=key, kind=kind, outcome=outcome, engine=item["value"],
                         reference=ref_text, band=None if band is None else str(band),
                         aux=None if aux is None else str(aux),
                         retried=bool(item.get("retried"))))  # fmt: skip
    for family, entry in bands["families"].items():
        if entry["kind"] == "info":
            rows.extend(dict(family=family, key=k, outcome="info") for k in entry["rows"])
    return verdicts(rows)


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
    m = sub.add_parser("manifest")
    m.add_argument("keys")
    m.add_argument("out")
    m.add_argument("--calibrations", action="store_true", help="T1 and T2's readings (unscored)")
    j = sub.add_parser("judge")
    for name in ("table", "values", "bands", "out"):
        j.add_argument(name)
    j.add_argument("--retry", help="the retry's table, merged over the first (after-retry)")
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
    elif args.command == "manifest":
        result = manifest(json.loads(Path(args.keys).read_text()))
        if args.calibrations:  # D312: T1 and T2 are unscored calibrations, reported beside the verdict.
            result["entries"] += calibrations()
        Path(args.out).write_text(json.dumps(result, indent=1))
        print(f"{len(result['entries'])} rows mapped, {len(result['not_run'])} not run or not "
              f"mappable, {len(result['unmapped'])} unmapped")
        for family, key in result["unmapped"]:
            print(f"unmapped: {family} | {key}")
    elif args.command == "judge":
        rule = check_rule()
        table = json.loads(Path(args.table).read_text())
        check_table(table, rule)
        digests = dict(engine_table_sha256=hashlib.sha256(Path(args.table).read_bytes()).hexdigest())
        if args.retry:
            retry = json.loads(Path(args.retry).read_text())
            check_table(retry, rule)
            if not retry["record"].get("retry"):
                raise SystemExit("refused: the retry table was not built with --retry")
            digests["retry_table_sha256"] = hashlib.sha256(Path(args.retry).read_bytes()).hexdigest()
            table = merge(table, retry)
        bands = json.loads(Path(args.bands).read_text())
        result = judge(table, lambda: json.loads(Path(args.values).read_text()), bands,
                       after_retry=bool(args.retry))  # fmt: skip
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
