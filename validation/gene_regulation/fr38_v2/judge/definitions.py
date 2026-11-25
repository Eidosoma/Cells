"""SPEC.md's inputs in the engine's own declaration (amendment 4, §8.5; amendment 5, items 6 and 7).

C0's echo check reads each run's `definition` at the keys those amendments state, by name and
never by position.

- **Paths.** `a.b[f=x].c`: `[f=x]` is the one list entry whose field f is x.
- **Values.** Numbers to 10⁻¹² relative, a declared zero exactly zero, lists and schedules entry by
  entry (in order of time); integers, strings, booleans and nulls exactly, and an integer only as a
  JSON integer (amendment 4, item 7; amendment 5, §2).
- **What fixes each value.** SPEC.md, the sheet's §5.1 table, or an amendment's own text. Where
  none states the declaration's convention for a value, its key and type are checked, the value is
  recorded, and a departure from the sheet's reading is flagged to the checker (`recorded`), never
  refused.
- **Runs that are another run's declaration** (item 6). A plant's is its honest run's except for its
  registered change, and anything else refuses it (`plant_change_faults`). A blank's is its
  family's p_sched run of the same machine with H(0) = 0 and k_I = 0, and a twin's is its labelled
  run's without the label owner and `label_arrivals`: the echo checks both against SPEC.md, and a
  difference at a key no SPEC.md or §5.1 value covers is recorded and flagged.
"""

import math
import re

from . import spec
from .shapes import COUPLING, GENE_UNIT, LABEL_OWNER, STORE, TURNOVER, WATER

G = f"model.operators[law={GENE_UNIT}]"
TX = f"{G}.chains[id=tx]"
REL = f"{TX}.release"
PC = "experiment.polymerisation_controls"
LAB = f"model.operators[law={LABEL_OWNER}]"
NET = f"model.operators[law={STORE}]"
WAT = f"model.operators[law={WATER}]"
TRN = f"model.operators[law={TURNOVER}]"
CPL = f"model.operators[law={COUPLING}].couplings[id=c_regulator]"
RC = f"{G}.transfers[id=recharge]"

LAWS = {"A": {GENE_UNIT, LABEL_OWNER}, "B": {GENE_UNIT, LABEL_OWNER, TURNOVER, COUPLING},
        "C": {GENE_UNIT, LABEL_OWNER, STORE}, "D": {GENE_UNIT, LABEL_OWNER, WATER}}  # fmt: skip
NAME_FIELDS = ("id", "route_id", "reaction_id", "membrane_id", "compartment_id", "coupling_id",
               "node")  # fmt: skip
ABSENT = "<absent>"


class Unreadable(Exception):
    """A key, its type or its value is not what SPEC.md and the amendments state."""


# what a malformed declaration may raise where a name or a list is another type: C0 refuses it
MALFORMED = (Unreadable, TypeError, AttributeError, ValueError)


# ------------------------------------------------------------------ paths

_STEP = re.compile(r"([^.\[\]]+)|\[([^=\]]+)=([^\]]+)\]")


def _steps(path):
    return [m.group(1) if m.group(1) is not None else (m.group(2), m.group(3))
            for m in _STEP.finditer(path)]  # fmt: skip


def locate(defn, path):
    node = defn
    for step in _steps(path):
        if isinstance(step, str):
            if not isinstance(node, dict):
                raise Unreadable(f"no key {step!r} in a {type(node).__name__}")
            if step not in node:
                raise Unreadable(f"no key {step!r}")
            node = node[step]
        else:
            field, name = step
            if not isinstance(node, list):
                raise Unreadable(f"[{field}={name}] in a {type(node).__name__}")
            hits = [e for e in node if isinstance(e, dict) and e.get(field) == name]
            if len(hits) != 1:
                raise Unreadable(f"{len(hits)} entries have {field} {name!r}")
            node = hits[0]
    return node


# ------------------------------------------------------------------ comparisons


def _num(x):
    return type(x) in (int, float) and math.isfinite(x)


def _close(a, b):
    return abs(a - b) <= spec.REL_INPUT * max(abs(a), abs(b))


def _cmp_num(got, exp):
    if not (_num(got) and _close(float(got), float(exp))):
        raise Unreadable(f"expected {exp!r}, found {got!r}")


def _cmp_exact(got, exp):
    if got != exp or type(got) is not type(exp):
        raise Unreadable(f"expected {exp!r}, found {got!r}")


def _cmp_keys(got, exp):
    if not isinstance(got, dict) or set(got) != set(exp):
        found = sorted(got) if isinstance(got, dict) else got
        raise Unreadable(f"expected the keys {sorted(exp)!r}, found {found!r}")


def _cmp_map(got, exp):
    _cmp_keys(got, exp)
    for k, v in exp.items():
        _cmp_num(got[k], v)


def _cmp_ints(got, exp):
    _cmp_keys(got, exp)
    for k, v in exp.items():
        if type(got[k]) is not int or got[k] != v:
            raise Unreadable(f"expected {k} = {v!r} (an integer), found {got[k]!r}")


def _cmp_weights(got, exp):
    """Moiety weights: the expected integers; any other row's is a zero."""
    if not isinstance(got, dict):
        raise Unreadable(f"weights {got!r} are not an object")
    for k, v in exp.items():
        if k not in got:
            raise Unreadable(f"no weight for {k}")
        if type(got[k]) is not int or got[k] != v:
            raise Unreadable(f"expected the weight {k} = {v!r} (an integer), found {got[k]!r}")
    for k, v in got.items():
        if k not in exp and not (type(v) is int and v == 0):
            raise Unreadable(f"weight {k} = {v!r} where SPEC.md declares none")


def _cmp_nums(got, exp):
    if not isinstance(got, list) or len(got) != len(exp):
        raise Unreadable(f"expected {len(exp)} numbers, found {str(got)[:120]}")
    for a, b in zip(got, exp, strict=True):
        _cmp_num(a, b)


def _schedule(got, field):
    """[(time, value)] in order of time."""
    if not isinstance(got, list):
        raise Unreadable(f"expected a schedule, found {got!r}")
    out = []
    for e in got:
        if not isinstance(e, dict) or field not in e or not _num(e.get("time")):
            raise Unreadable(f"a schedule entry {e!r} is not {{{field}, time}}")
        out.append((float(e["time"]), e[field]))
    return sorted(out, key=lambda x: x[0])


def _cmp_schedule(got, exp, field, *, merge=False):
    rows = _schedule(got, field)
    if merge:  # the same function of time: a repeated value is no new step
        rows = [r for i, r in enumerate(rows) if i == 0 or r[1] != rows[i - 1][1]]
    if len(rows) != len(exp):
        raise Unreadable(f"expected the schedule {exp!r}, found {rows!r}")
    for (t, v), (te, ve) in zip(rows, exp, strict=True):
        _cmp_num(t, te)
        if isinstance(ve, str):
            _cmp_exact(v, ve)
        else:
            _cmp_num(v, ve)


def _cmp_names(got, field, exp):
    if not isinstance(got, list):
        raise Unreadable(f"expected a list, found {got!r}")
    names = [e.get(field) if isinstance(e, dict) else None for e in got]
    if len(names) != len(set(names)) or set(names) != set(exp):
        raise Unreadable(f"expected the entries {sorted(exp)!r} by {field}, found {names!r}")


def _cmp_strings(got, exp):
    if (
        not isinstance(got, list)
        or sorted(map(str, got)) != sorted(exp)
        or any(not isinstance(x, str) for x in got)
    ):
        raise Unreadable(f"expected {sorted(exp)!r} by name, found {got!r}")


def _cmp_zeros(got, species):
    if not isinstance(got, dict) or not set(species) <= set(got):
        raise Unreadable(f"expected one number per species {sorted(species)!r}, found {got!r}")
    for k, v in got.items():
        if not (_num(v) and v == 0):
            raise Unreadable(f"{k} = {v!r}, where every permeability is exactly zero")


def _cmp_initial(got, exp):
    if not isinstance(got, list):
        raise Unreadable(f"initial is not a list: {got!r}")
    _cmp_names(got, "node", {"cell_0"})
    _cmp_map(got[0].get("shares"), exp)


def _cmp_arrivals(got, exp):
    """Three entries by (species, source): each fate row's own, and the source entry (item 6)."""
    if not isinstance(got, list):
        raise Unreadable("label_arrivals is not a list")
    names = [(e.get("species"), e.get("source")) if isinstance(e, dict) else None for e in got]
    if len(names) != len(set(names)) or set(names) != set(exp):
        raise Unreadable(f"expected the entries {sorted(map(str, exp))!r}, found {names!r}")
    for name, rows in exp.items():
        entry = got[names.index(name)]
        try:
            _cmp_schedule(entry.get("schedule"), rows, "label")
        except Unreadable as exc:
            raise Unreadable(f"{name}: {exc}") from exc


def compare(kind, got, exp):
    if kind == "num":
        _cmp_num(got, exp)
    elif kind == "exact":
        _cmp_exact(got, exp)
    elif kind == "int":
        if type(got) is not int or got != exp:
            raise Unreadable(f"expected the integer {exp!r}, found {got!r}")
    elif kind == "keys":  # an object of integers whose values no spec text states
        _cmp_keys(got, exp)
        if any(type(v) is not int for v in got.values()):
            raise Unreadable(f"expected integers, found {got!r}")
    elif kind.startswith("schedule"):
        _cmp_schedule(got, exp, kind.partition(":")[2].rstrip("~"), merge=kind.endswith("~"))
    elif kind.startswith("names:"):
        _cmp_names(got, kind.partition(":")[2], exp)
    else:
        {"map": _cmp_map, "ints": _cmp_ints, "weights": _cmp_weights, "nums": _cmp_nums,
         "strings": _cmp_strings, "zeros": _cmp_zeros, "initial": _cmp_initial,
         "arrivals": _cmp_arrivals}[kind](got, exp)  # fmt: skip


# ------------------------------------------------------------------ SPEC.md's declaration


def _get(inputs, *keys):
    for k in keys:
        if k in inputs:
            return inputs[k]
    raise KeyError(keys[0])


def _p(p_schedule):
    """`durable_fraction`: the constant, or "scheduled" with its control."""
    if len(p_schedule) == 1 and float(p_schedule[0][0]) == 0.0:
        return float(p_schedule[0][1]), None
    return "scheduled", [(float(t), float(v)) for t, v in p_schedule]


def declared(inputs, profile, run, role, machine, dt):
    """(what, path, kind, expected) for one run: SPEC.md at the amendments' keys."""
    blank, labelled = run == "blank", role != "twin"
    V = float(inputs["volume_pL"])
    L = spec.chain_length(inputs)
    hold = profile != "B"
    out = []

    def add(what, path, kind, exp):
        out.append((what, path, kind, exp))

    # ---- the model
    const = inputs["constants"]
    add("the temperature", "model.temperature_K", "num", const["T_K"])
    add("c°", "model.standard_concentration_mM", "num", const["c_standard_mM"])
    laws = LAWS[profile] - (set() if labelled else {LABEL_OWNER})
    add("the operators", "model.operators", "names:law", laws)
    add("the cells", "model.cells", "names:id", {"cell_0"})
    add("the cell's volume", "model.cells[id=cell_0].volume_pL", "num", V)
    amounts = {r: float(c) * V for r, c in inputs["initial_mM"].items()}
    if hold:
        amounts.update({r: float(n) * spec.COPY_FMOL
                        for r, n in inputs["initial_copies"].items()})  # fmt: skip
        amounts.update({i: float(c) * V for i, c in inputs["cell_background_mM"].items()})
    if profile == "C":
        amounts["Mx"] = float(inputs["store"]["Mx_initial_mM"]) * V
    for r, a in sorted(amounts.items()):
        add(f"the cell's {r}", f"model.cells[id=cell_0].initial_amount_fmol.{r}", "num", a)
    rows = ["N", "M", "Pi", "R", "R_s"] + (["A", "ATP", "ADP", "P"] if not hold else [])
    if hold:  # SPEC.md §1.1 declares the bath and the patch; §2 declares none for arm B
        vb = float(inputs["bath_volume_pL"])
        bath = "model.extracellular[id=bath_0]"
        patch = "model.membranes[id=patch_0]"
        traced = rows + (["Mx"] if profile == "C" else [])
        add("the baths", "model.extracellular", "names:id", {"bath_0"})
        add("the bath's volume", f"{bath}.volume_pL", "num", vb)
        add("the bath is held", f"{bath}.reservoir", "exact", True)
        for i, c in sorted(inputs["bath_mM"].items()):
            add(f"the bath's {i}", f"{bath}.initial_amount_fmol.{i}", "num", float(c) * vb)
        for r in traced:
            add(f"the bath's {r}", f"{bath}.initial_amount_fmol.{r}", "num",
                float(inputs["bath_trace_mM"]) * vb)  # fmt: skip
        add("the patches", "model.membranes", "names:id", {"patch_0"})
        add("the patch's area", f"{patch}.area_m2", "num", float(inputs["patch_area_m2"]))
        add("the patch's permeabilities", f"{patch}.permeability_m_per_s", "zeros",
            traced + ["K", "Y"])  # fmt: skip
        for i, z in (("K", 1), ("Y", -1)):
            add(f"{i}'s valence", f"model.species[id={i}].valence", "int", z)
        for r in traced:
            add(f"{r} is neutral", f"model.species[id={r}].valence", "int", 0)
    mu = {r: float(inputs["mu0_RT_at_1M"][r]) for r in rows}
    for r, m in sorted(mu.items()):
        add(f"μ°/RT of {r}", f"model.species[id={r}].standard_mu_RT", "num", m)
        add(f"the gene unit's μ°/RT of {r}", f"{G}.species[id={r}].standard_mu_RT", "num", m)
    if profile == "C":
        add("μ°/RT of Mx", "model.species[id=Mx].standard_mu_RT", "num",
            float(inputs["store"]["mu0_Mx_RT_at_1M"]))  # fmt: skip
    add("the moieties", "model.moieties", "names:id", set(inputs["moieties"]))
    for moiety, weights in sorted(inputs["moieties"].items()):
        w = {k: int(v) for k, v in weights.items()}
        if profile == "C" and moiety in inputs["store"]["Mx_moieties"]:
            w["Mx"] = int(inputs["store"]["Mx_moieties"][moiety])
        add(f"the {moiety} moiety", f"model.moieties[id={moiety}].weights", "weights", w)
    # ---- the gene unit
    chains, degs, pools = {"tx"}, {"deg_R", "deg_R_s"}, {"pol"}
    routes = {"tx", "deg_R", "deg_R_s"}
    if not hold:
        chains |= {"tl", "tl_s"}
        degs |= {"deg_P"}
        pools |= {"rib"}
        routes |= {"tl", "tl_s", "deg_P", "recharge"}
    add("the gene unit's c°", f"{G}.standard_concentration_mM", "num", const["c_standard_mM"])
    add("the pools", f"{G}.pools", "names:id", pools)
    add("the polymerases", f"{G}.pools[id=pol].machines", "num",
        float(_get(inputs, "pool_machines_copies", "M_pol_copies")))  # fmt: skip
    add("the pool's cell", f"{G}.pools[id=pol].cell", "exact", "cell_0")
    add("the chains", f"{G}.chains", "names:id", chains)
    add("the template copies", f"{TX}.template.copies", "int", int(inputs["template_copies"]))
    add("the product", f"{TX}.product", "exact", "R")
    add("the chain's pool", f"{TX}.pool", "exact", "pol")
    add("the residues", f"{TX}.residues", "int", L)
    add("the stages", f"{TX}.stages", "int", int(_get(inputs, "stages", "m_tx")))
    add("the speed", f"{TX}.speed_per_s", "num",
        float(_get(inputs, "speed_nt_per_s", "v_tx_nt_per_s")))  # fmt: skip
    add("the draws", f"{TX}.draws", "ints", {"N": int(inputs.get("N_per_residue", 1))})
    add("the releases", f"{TX}.releases", "ints", {"Pi": int(inputs.get("Pi_per_residue", 2))})
    add("N's saturation", f"{TX}.saturation_mM", "map",
        {"N": float(_get(inputs, "K_N_mM", "K_N_tx_mM"))})  # fmt: skip
    # ---- the release: a blank's is its family's p_sched run's, with H(0) = 0 (item 6)
    df, p_sched = _p(inputs["p_sched"] if blank else inputs["runs"][run]["p"])
    add("the release", f"{REL}.id", "exact", "tx_release")
    add("τ", f"{REL}.dwell_s", "num", float(inputs["tau_s"]))
    add("the machine", f"{REL}.machine", "exact",
        machine if blank else inputs["runs"][run]["machine"])  # fmt: skip
    add("p", f"{REL}.durable_fraction", "exact" if isinstance(df, str) else "num", df)
    add("H(0)", f"{REL}.initial_copies", "nums", [0.0 if blank else float(inputs["H0_copies"])])
    add("the fates", f"{REL}.fates", "exact", [{"durable": "R", "short_lived": "R_s"}])
    add("the label's marking", f"{REL}.label", "exact", {"at": "release"})
    add("the degradations", f"{G}.degradations", "names:id", degs)
    for deg, row in (("deg_R", "R"), ("deg_R_s", "R_s")):
        add(f"{deg}'s polymer", f"{G}.degradations[id={deg}].polymer", "exact", row)
        add(f"{deg}'s residues", f"{G}.degradations[id={deg}].residues", "int", L)
        add(f"{deg}'s monomers", f"{G}.degradations[id={deg}].monomers", "keys", {"M"})
    if hold:
        add("no recharging", f"{G}.transfers", "exact", [])
    # ---- the rates
    if p_sched is not None:
        routes |= {"tx_release"}
    add("the controlled routes", PC, "names:route_id", routes)
    k_i = 0.0 if blank else float(_get(inputs, "k_I_tx_per_mM_s", "k_I_per_mM_s"))
    for route, what, v in (("tx", "k_I", k_i), ("deg_R", "k_d", float(inputs["k_d_per_s"])),
                           ("deg_R_s", "k_s", float(inputs["k_s_per_s"]))):  # fmt: skip
        add(what, f"{PC}[route_id={route}].schedule", "schedule:value", [(0.0, v)])
    if p_sched is not None:
        add("p's schedule", f"{PC}[route_id=tx_release].schedule", "schedule:value", p_sched)
    # ---- the labels
    if labelled:
        shares = {k: float(v) for k, v in inputs["initial_label_shares"].items()}
        s = {k: float(v) for k, v in inputs["label_schedule_s"].items()}
        add("the labelled rows", f"{LAB}.species", "names:id", {"R", "R_s"})
        for row in ("R", "R_s"):
            add(f"{row}'s labels", f"{LAB}.species[id={row}].labels", "strings",
                list(spec.CLASSES))  # fmt: skip
            add(f"{row}'s initial shares", f"{LAB}.species[id={row}].initial", "initial", shares)
        add("the label arrivals", "experiment.label_arrivals", "arrivals",
            {("R", None): [(0.0, "resyn")], ("R_s", None): [(0.0, "resyn")],
             ("R", "tx"): [(s["pre"], "pre"), (s["win"], "win"), (s["post"], "post")]})  # fmt: skip
    # ---- the grid
    add("the horizon", "experiment.end_time", "num", float(inputs["horizon_s"]))
    add("the outputs", "experiment.observation_times", "nums", spec.grid(inputs))
    add("the step", "execution.dt", "num", float(dt))
    if profile == "C":
        _declare_store(inputs, add)
    if profile == "D":
        _declare_water(inputs, add)
    if profile == "B":
        _declare_a1(inputs, add)
    return out


def _declare_store(inputs, add):
    st = inputs["store"]
    add("the network's c0", f"{NET}.standard_concentration_mM", "num", float(st["network_c0_mM"]))
    add("the network's species", f"{NET}.species", "names:id", {"M", "Mx"})
    moieties = {"M": {m: int(w["M"]) for m, w in inputs["moieties"].items() if "M" in w},
                "Mx": {k: int(v) for k, v in st["Mx_moieties"].items()}}  # fmt: skip
    for r in ("M", "Mx"):
        add(f"the network's μ°/RT of {r}", f"{NET}.species[id={r}].standard_mu_RT", "num",
            float(st["network_mu0_RT_at_c0"][r]))  # fmt: skip
        add(f"{r}'s moieties in the network", f"{NET}.species[id={r}].moieties", "ints",
            moieties[r])  # fmt: skip
    rx = f"{NET}.reactions[id=store_M]"
    add("the network's reactions", f"{NET}.reactions", "names:id", {"store_M"})
    add("the store's law", f"{rx}.law", "exact", "ideal_detailed_balance_mass_action@1")
    add("the store's sites", f"{rx}.sites", "exact", {"cells": ["cell_0"]})
    add("the store's reactants", f"{rx}.reactants", "ints", {"M": 1})
    add("the store's products", f"{rx}.products", "ints", {"Mx": 1})
    add("the store's forward rate", f"{rx}.forward_rate_per_s", "num",
        float(st["forward_per_s_at_c0"]))  # fmt: skip
    add("the store's factors", f"{rx}.factors", "exact", [])
    rc = "experiment.reaction_controls"
    add("the controlled reactions", rc, "names:reaction_id", {"store_M"})
    add("the store's multiplier", f"{rc}[reaction_id=store_M].schedule", "schedule:multiplier",
        [(0.0, float(st["multiplier"]))])  # fmt: skip
    add("the store's site", f"{rc}[reaction_id=store_M].site", "exact", None)


def _declare_water(inputs, add):
    w = inputs["water"]
    add("water's compartments", f"{WAT}.compartments", "names:compartment_id", {"cell_0"})
    for key, val in (("reference_volume_pL", "V_ref_pL"), ("minimum_volume_pL", "V_min_pL"),
                     ("maximum_volume_pL", "V_max_pL"),
                     ("impermeant_amount_fmol", "impermeant_fmol"),
                     ("bulk_modulus_Pa", "bulk_modulus_Pa"),
                     ("pressure_offset_Pa", "pressure_offset_Pa")):  # fmt: skip
        add(f"water's {key}", f"{WAT}.compartments[compartment_id=cell_0].{key}", "num",
            float(w[val]))  # fmt: skip
    add("water's baths", f"{WAT}.baths", "names:compartment_id", {"bath_0"})
    add("the bath's pressure", f"{WAT}.baths[compartment_id=bath_0].hydrostatic_pressure_Pa",
        "num", float(w["bath_pressure_Pa"]))  # fmt: skip
    add("water's patches", f"{WAT}.membranes", "names:membrane_id", {"patch_0"})
    add("L_p", f"{WAT}.membranes[membrane_id=patch_0].hydraulic_permeability_m_per_Pa_s", "num",
        float(w["L_p_m_per_Pa_s"]))  # fmt: skip
    wc = "experiment.water_controls"
    add("the controlled patches", wc, "names:membrane_id", {"patch_0"})
    add("water's availability", f"{wc}[membrane_id=patch_0].schedule", "schedule:availability",
        [(0.0, float(w["availability"]))])  # fmt: skip


def _declare_a1(inputs, add):
    """Arm B: translation, the ribosomes, deg_P, recharging, the regulator and its factor, at the
    sheet's §5.1 values (amendment 5, item 6). The per-residue draws and releases of `tl` and `tl_s`
    are the judge's reading that item 6 confirms."""
    Lp = int(inputs["L_P_aa"])
    add("the ribosomes", f"{G}.pools[id=rib].machines", "num", float(inputs["M_rib_copies"]))
    for c, template in (("tl", "R"), ("tl_s", "R_s")):
        ch = f"{G}.chains[id={c}]"
        add(f"{c}'s template", f"{ch}.template.species", "exact", template)
        add(f"{c}'s product", f"{ch}.product", "exact", "P")
        add(f"{c}'s pool", f"{ch}.pool", "exact", "rib")
        add(f"{c}'s residues", f"{ch}.residues", "int", Lp)
        add(f"{c}'s stages", f"{ch}.stages", "int", int(inputs["m_tl"]))
        add(f"{c}'s speed", f"{ch}.speed_per_s", "num", float(inputs["v_tl_aa_per_s"]))
        add(f"{c}'s draws", f"{ch}.draws", "ints", {"A": 1, "ATP": 4})
        add(f"{c}'s releases", f"{ch}.releases", "ints", {"ADP": 4, "Pi": 4})
        add(f"{c}'s saturation", f"{ch}.saturation_mM", "map",
            {"A": float(inputs["K_A_tl_mM"]), "ATP": float(inputs["K_ATP_tl_mM"])})  # fmt: skip
        add(f"{c} has no release", f"{ch}.release", "absent", None)
        add(f"{c}'s initiation", f"{PC}[route_id={c}].schedule", "schedule:value",
            [(0.0, float(inputs["k_I_tl_per_mM_s"]))])  # fmt: skip
    dp = f"{G}.degradations[id=deg_P]"
    add("deg_P's polymer", f"{dp}.polymer", "exact", "P")
    add("deg_P's residues", f"{dp}.residues", "int", Lp)
    add("deg_P's monomers", f"{dp}.monomers", "keys", {"A"})
    add("k_P", f"{PC}[route_id=deg_P].schedule", "schedule:value",
        [(0.0, float(inputs["k_P_per_s"]))])  # fmt: skip
    add("the transfers", f"{G}.transfers", "names:id", {"recharge"})
    add("recharging's saturation", f"{RC}.saturation_mM", "map",
        {"ATP": float(inputs["K_ATP_rc_mM"]), "M": float(inputs["K_M_rc_mM"])})  # fmt: skip
    add("recharging's stoichiometry", f"{RC}.stoichiometry", "keys", {"ADP", "ATP", "M", "N"})
    add("V_C", f"{PC}[route_id=recharge].schedule", "schedule:value",
        [(0.0, float(inputs["V_C_mM_per_s"]))])  # fmt: skip
    # the regulator: X's production until t_off, and its clearance in both phases (§5.1). The
    # sheet states the rates as functions of time, so a repeated value is no new step.
    add("the regulator's routes", f"{TRN}.routes", "names:id", {"x_production", "x_clearance"})
    for r in ("x_production", "x_clearance"):
        add(f"{r}'s species", f"{TRN}.routes[id={r}].species", "exact", "X")
    add("the turnover's templates", f"{TRN}.templates", "exact", [])
    tc = "experiment.turnover_controls"
    add("the controlled turnover", tc, "names:route_id", {"x_production", "x_clearance"})
    add("P_X", f"{tc}[route_id=x_production].schedule", "schedule:rate~",
        [(0.0, float(inputs["P_on_fmol_per_s"])), (float(inputs["t_off_s"]), 0.0)])  # fmt: skip
    add("k_X", f"{tc}[route_id=x_clearance].schedule", "schedule:rate~",
        [(0.0, float(inputs["k_X_per_s"]))])  # fmt: skip
    cp = f"model.operators[law={COUPLING}]"
    add("the couplings", f"{cp}.couplings", "names:id", {"c_regulator"})
    add("the coupling's states", f"{cp}.states", "exact", [])
    add("the factor's law", f"{CPL}.law", "exact", "hill_activation")
    add("b_X", f"{CPL}.basal", "num", float(inputs["b_X"]))
    add("K_X", f"{CPL}.half_saturation_mM", "num", float(inputs["K_X_mM"]))
    add("n_X", f"{CPL}.hill_coefficient", "num", float(inputs["n_X"]))
    add("the factor's source", f"{CPL}.source.species", "exact", "X")
    add("the controlled couplings", "experiment.coupling_controls", "names:coupling_id",
        {"c_regulator"})  # fmt: skip


def check_definition(defn, inputs, profile, run, role, machine, dt):
    """C0's echo check of one run's declaration: the faults, by key."""
    if not isinstance(defn, dict):
        return [f"definition: an object expected, {type(defn).__name__} found"]
    faults = []
    for what, path, kind, exp in declared(inputs, profile, run, role, machine, dt):
        try:
            if kind == "absent":
                _absent(defn, path)
                continue
            compare(kind, locate(defn, path), exp)
        except MALFORMED as exc:
            faults.append(f"definition.{path}: {what}: {exc}")
    if role == "twin":  # item 7: no label owner (the operators above) and no label_arrivals
        try:
            _absent(defn, "experiment.label_arrivals")
        except MALFORMED as exc:
            faults.append(f"definition.experiment.label_arrivals: a twin is unlabelled: {exc}")
    return faults


def _absent(defn, path):
    head, _, key = path.rpartition(".")
    if key in locate(defn, head):
        raise Unreadable(f"{key!r} is present")


# ------------------------------------------------------------------ recorded, never refused


def recorded(defn, inputs, profile):
    """Values no SPEC.md or §5.1 text states in the declaration's own convention: recorded, and
    flagged where they depart from the sheet's reading (item 6's last bullet)."""
    L = spec.chain_length(inputs)
    values, flags = {}, []

    def take(path, ok=None, reading=""):
        try:
            v = locate(defn, path)
        except Unreadable as exc:
            flags.append(f"{path}: not recorded ({exc})")
            return None
        values[path] = v
        try:
            departs = ok is not None and not ok(v)
        except (AttributeError, TypeError):
            departs = True
        if departs:
            flags.append(f"{path} = {v!r}, where the sheet reads {reading}")
        return v

    for deg, m, n in (("deg_R", "M", L), ("deg_R_s", "M", L)):
        take(f"{G}.degradations[id={deg}].monomers", lambda v, m=m, n=n: v.get(m) in (1, n),
             f"{n} {m} per molecule (1 per residue)")  # fmt: skip
    if profile == "B":
        take(f"{G}.degradations[id=deg_P].monomers",
             lambda v: v.get("A") in (1, int(inputs["L_P_aa"])),
             f"{inputs['L_P_aa']} A per molecule (1 per residue)")  # fmt: skip
        take(f"{RC}.stoichiometry", lambda v: v == {"N": 1, "M": -1, "ATP": -2, "ADP": 2},
             "M + 2 ATP → N + 2 ADP, products positive (§2)")  # fmt: skip
        take(f"{RC}.share", lambda v: v == 2, "2 (§4.5)")
        take(f"{CPL}.target", lambda v: v.get("ids") == ["tx"], "transcription's initiation (§4.6)")
        take("experiment.coupling_controls[coupling_id=c_regulator].schedule",
             lambda v: [x.get("enabled") for x in v] == [1], "in force throughout")  # fmt: skip
        take("model.membranes[id=patch_0].permeability_m_per_s",
             lambda v: not any(v.values()),
             "no exchange (SPEC.md §2 declares no bath)")  # fmt: skip
    model = defn.get("model")
    species = model.get("species") if isinstance(model, dict) else None
    have = {e["id"] for e in species if isinstance(e, dict) and isinstance(e.get("id"), str)
            } if isinstance(species, list) else set()  # fmt: skip
    rows = {"N", "M", "Pi", "R", "R_s", "K", "Y"} | ({"Mx"} if profile == "C" else set())
    if profile == "B":
        rows |= {"X", "A", "ATP", "ADP", "P"}
    if have - rows:
        flags.append(
            f"model.species: entries beyond SPEC.md's rows: {sorted(map(str, have - rows))}"
        )
    return values, flags


def declared_rate(defn, fate):
    """The fate's k_f in this run's own declaration (P5's is the planted one)."""
    deg = "deg_R" if fate == "durable" else "deg_R_s"
    rows = _schedule(locate(defn, f"{PC}[route_id={deg}].schedule"), "value")
    return float(rows[0][1])


# ------------------------------------------------------------------ one declaration against another


def canonical(x, path=()):
    """A declaration with its lists matched by name: named entries keyed by name, schedules in
    order of time, lists of strings sorted. Numeric lists keep their order."""
    if isinstance(x, dict):
        return {k: canonical(v, path + (k,)) for k, v in x.items()}
    if not isinstance(x, list):
        return x
    here = path[-1] if path else ""
    if x and all(isinstance(e, dict) for e in x):
        if here == "schedule":
            return [canonical(e, path) for e in sorted(x, key=lambda e: (
                e["time"] if _num(e.get("time")) else math.inf))]  # fmt: skip
        if here == "operators":
            names = [e.get("law") for e in x]
        elif here == "label_arrivals":
            names = [(e.get("species"), e.get("source")) for e in x]
        else:
            field = next((f for f in NAME_FIELDS if all(isinstance(e.get(f), str) for e in x)),
                         None)  # fmt: skip
            names = None if field is None else [e[field] for e in x]
        if names is None:
            return [canonical(e, path) for e in x]
        if len(set(names)) != len(names):
            raise Unreadable(f"{'/'.join(map(str, path))}: two entries of one name")
        return {n: canonical(e, path + (n,)) for n, e in zip(names, x, strict=True)}
    if x and all(isinstance(e, str) for e in x):
        return sorted(x)
    return [canonical(e, path) for e in x]


def leaf_diff(a, b, path=()):
    """Every leaf where two canonical declarations differ, as (path, first, second)."""
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for k in sorted(set(a) | set(b), key=str):
            if k not in a or k not in b:
                out.append((path + (k,), a.get(k, ABSENT), b.get(k, ABSENT)))
            else:
                out += leaf_diff(a[k], b[k], path + (k,))
        return out
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return [(path, a, b)]
        out = []
        for i, (x, y) in enumerate(zip(a, b, strict=True)):
            out += leaf_diff(x, y, path + (i,))
        return out
    if (a == b and type(a) is type(b)) or (_num(a) and _num(b) and float(a) == float(b)):
        return []
    return [(path, a, b)]


def _where(path):
    return "/".join(map(str, path))


_REL = ("model", "operators", GENE_UNIT, "chains", "tx", "release")
_SOURCE = ("experiment", "label_arrivals", ("R", "tx"), "schedule")


def _change(plant, inputs):
    """(the one leaf that may differ, a check of its honest and planted values) — item 6."""

    def scaled(factor):
        return lambda h, p: _num(h) and _num(p) and _close(float(p), float(h) * factor)

    def becomes(a, b):
        return lambda h, p: h == a and p == b

    def late(old):
        return lambda h, p: (
            _num(h) and _num(p) and _close(float(h), old)
            and _close(float(p), old + spec.H_STEP_S))  # fmt: skip

    t1, t2 = (float(x) for x in inputs["window_s"])
    return {
        "P2": (_REL + ("durable_fraction",),
               lambda h, p: _num(h) and _num(p) and float(h) == 1.0
               and _close(float(p), 1.0 - 2.0**-30)),
        "P3a": (_SOURCE + (1, "time"), late(t1)),
        "P3b": (_SOURCE + (2, "time"), late(t2)),
        "P4": (_REL + ("label", "at"), becomes("release", "completion")),
        "P5": (("experiment", "polymerisation_controls", "deg_R_s", "schedule", 0, "value"),
               scaled(1.0 + 1e-4)),
        "P7": (_REL + ("machine",), becomes("held", "returned")),
        "P8": (("model", "operators", STORE, "reactions", "store_M", "forward_rate_per_s"),
               scaled(1.01)),
        "P9": (None, None),
    }[plant]  # fmt: skip


def plant_change_faults(plant, honest, planted, inputs):
    """Item 6: the registered change, at its key, is all that may differ from the honest run's."""
    try:
        diff = leaf_diff(canonical(honest), canonical(planted))
    except MALFORMED as exc:
        return [f"{plant}: {exc}"]
    key, ok = _change(plant, inputs)
    faults = []
    for path, h, p in diff:
        if path != key:
            faults.append(f"{plant}: the declaration differs from its honest run's at "
                          f"{_where(path)} ({h!r} → {p!r}), not its registered change")  # fmt: skip
        elif not ok(h, p):
            faults.append(f"{plant}: its registered change at {_where(path)} reads {h!r} → {p!r}")
    if key is not None and not any(path == key for path, _, _ in diff):
        faults.append(f"{plant}: no registered change at {_where(key)}")
    return faults


def twin_differences(labelled, twin):
    """Item 6: a twin's declaration is its labelled run's without the label owner and
    `label_arrivals`. What else differs is recorded (the echo refuses what SPEC.md covers)."""
    try:
        a, b = canonical(labelled), canonical(twin)
        a["model"]["operators"].pop(LABEL_OWNER, None)
        a["experiment"].pop("label_arrivals", None)
    except (KeyError, *MALFORMED) as exc:
        return [f"not compared: {exc}"]
    return [f"{_where(p)}: {h!r} → {q!r}"[:200] for p, h, q in leaf_diff(a, b)]


def blank_differences(p_sched, blank):
    """Item 6: a blank's declaration is its family's p_sched run of the same machine option, with
    H(0) = 0 and k_I = 0 and nothing else changed. What else differs is recorded."""
    allowed = {_REL + ("initial_copies", 0),
               ("experiment", "polymerisation_controls", "tx", "schedule", 0, "value")}  # fmt: skip
    try:
        diff = leaf_diff(canonical(p_sched), canonical(blank))
    except MALFORMED as exc:
        return [f"not compared: {exc}"]
    return [f"{_where(p)}: {h!r} → {q!r}"[:200] for p, h, q in diff if p not in allowed]
