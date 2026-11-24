"""SPEC.md's inputs as the engine's own declaration states them (amendment 4, §8.5).

C0's echo check reads each run's `definition`, the engine's declaration as run, at §8.5's keys.

- **Paths.** `a.b[x].c`: `[x]` is a dict's key x, or the one list entry whose `id`, `route_id`,
  `compartment_id` or `membrane_id` is x (§8.5's matching rule).
- **Open shapes.** Where §8.5 names a key but not the shape of its value, or names an operator but
  not where it sits, this module reads one narrow shape (`OPEN_SHAPES`) and fails closed on any
  other: the run is refused, never repaired. Each needs a dated amendment.
- **Unchecked inputs.** SPEC.md inputs with no §8.5 key are listed in the verdict (`unchecked`),
  never skipped silently.
- **Plants.** A plant's definition is compared with its honest run's: every leaf that differs must
  be its registered change (`plant_change_faults`).
"""

import math

from . import spec

MATCH_FIELDS = ("id", "route_id", "compartment_id", "membrane_id")
GENE_UNIT = "templated_polymerisation@1"
LABEL_OWNER = "neutral_arrival_labels@1"
STORE = "local_species_reactions@1"
WATER = "ideal_osmosis_linear_compliance_water@1"

OPEN_SHAPES = (
    "an operator's declaration: the one object anywhere in `definition` with a string value equal "
    "to its law (templated_polymerisation@1, neutral_arrival_labels@1, local_species_reactions@1, "
    "ideal_osmosis_linear_compliance_water@1)",
    "`chains[*].draws`, `releases` and `saturation_mM`: objects {species: number}",
    '`chains[tx].release.fates`: {"durable": "R", "short_lived": "R_s"}',
    "`degradations[*].monomers`: the monomer's species id, a string",
    "`experiment.label_arrivals`: a list; a row's own entry {species, schedule} has no `source`; "
    'the source entry is {species, source: "tx", schedule}; schedule entries {time, label}',
    "the label owner's `species[*].labels`: a list of label names, the base (resyn) first; "
    "`initial`: a list of {node, shares}, shares {label: share}",
    "`reactions[store_M]`: `sites` a list of node ids, `reactants` and `products` {species: "
    "number}; `experiment.reaction_controls[store_M].schedule`: entries {time, value}",
    "`experiment.water_controls`: a list of {time, availability}",
)


class Unreadable(Exception):
    """A §8.5 key, or its shape, is not where the reader looks: the run is refused."""


def _sel(node, key):
    """(value, raw step): a dict's key, or the one list entry matching key by §8.5's fields."""
    if isinstance(node, dict):
        if key in node:
            return node[key], key
        raise Unreadable(f"no key {key!r}")
    if isinstance(node, list):
        hits = [i for i, e in enumerate(node) if isinstance(e, dict)
                and any(e.get(f) == key for f in MATCH_FIELDS)]  # fmt: skip
        if len(hits) != 1:
            raise Unreadable(f"{len(hits)} entries match [{key}]")
        return node[hits[0]], hits[0]
    raise Unreadable(f"[{key}] on a {type(node).__name__}")


def _parse(path):
    steps = []
    for seg in path.split("."):
        name, _, rest = seg.partition("[")
        if name:
            steps.append(name)
        while rest:
            sel, _, rest = rest.partition("]")
            steps.append(sel)
            rest = rest[1:] if rest.startswith("[") else rest
    return steps


def operator(defn, law):
    """(object, raw path): the one object in the declaration that names `law` as a string value
    (an open shape)."""
    hits = []

    def walk(x, p):
        if isinstance(x, dict):
            if any(isinstance(v, str) and v == law for v in x.values()):
                hits.append((x, p))
            for k, v in x.items():
                walk(v, p + (k,))
        elif isinstance(x, list):
            for i, v in enumerate(x):
                walk(v, p + (i,))

    walk(defn, ())
    if len(hits) != 1:
        raise Unreadable(f"{len(hits)} declarations name {law}")
    return hits[0]


def locate(defn, path, root=None, cache=None):
    """(value, raw JSON path) of a §8.5 key in this declaration. `cache` keeps each operator's
    lookup for one declaration."""
    if root is None:
        node, raw = defn, ()
    elif cache is not None:
        if root not in cache:
            try:
                cache[root] = operator(defn, root)
            except Unreadable as exc:
                cache[root] = exc
        if isinstance(cache[root], Unreadable):
            raise cache[root]
        node, raw = cache[root]
    else:
        node, raw = operator(defn, root)
    for step in _parse(path):
        node, k = _sel(node, step)
        raw = raw + (k,)
    return node, raw


def get(defn, path, root=None, cache=None):
    return locate(defn, path, root, cache)[0]


# ------------------------------------------------------------------ comparisons


def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _close(a, b):
    return abs(a - b) <= spec.REL_INPUT * max(abs(a), abs(b))


def _cmp_num(got, exp):
    if not (_num(got) and _close(float(got), float(exp))):
        raise Unreadable(f"expected {exp!r}, found {got!r}")


def _cmp_map(got, exp):
    if not isinstance(got, dict) or set(got) != set(exp):
        raise Unreadable(f"expected {exp!r}, found {got!r}")
    for k, v in exp.items():
        _cmp_num(got[k], v)


def _cmp_schedule(got, exp, field="value"):
    """[{time, <field>}] element by element against [(time, value)]."""
    if not isinstance(got, list) or len(got) != len(exp):
        raise Unreadable(f"expected the schedule {exp!r}, found {got!r}")
    for e, (t, v) in zip(got, exp, strict=True):
        if not isinstance(e, dict) or "time" not in e or field not in e:
            raise Unreadable(f"a schedule entry {e!r} is not {{time, {field}}}")
        _cmp_num(e["time"], t)
        if isinstance(v, str):
            if e[field] != v:
                raise Unreadable(f"expected {field} {v!r} at {t!r} s, found {e[field]!r}")
        else:
            _cmp_num(e[field], v)


def _cmp_exact(got, exp):
    if got != exp or type(got) is not type(exp):
        raise Unreadable(f"expected {exp!r}, found {got!r}")


def _cmp_nums(got, exp):
    if not isinstance(got, list) or len(got) != len(exp):
        raise Unreadable(f"expected {len(exp)} numbers, found {got!r}"[:200])
    for a, b in zip(got, exp, strict=True):
        _cmp_num(a, b)


def _cmp_weights(got, exp):
    """Moiety weights: the expected entries equal; any other entry is zero."""
    if not isinstance(got, dict):
        raise Unreadable(f"weights {got!r} are not an object")
    for k, v in exp.items():
        if k not in got:
            raise Unreadable(f"no weight for {k}")
        _cmp_num(got[k], v)
    for k, v in got.items():
        if k not in exp and not (_num(v) and v == 0):
            raise Unreadable(f"weight {k} = {v!r} where SPEC.md declares none")


# ------------------------------------------------------------------ SPEC.md at §8.5's keys


def _get(inputs, *keys, default=None):
    for k in keys:
        if k in inputs:
            return inputs[k]
    if default is not None:
        return default
    raise KeyError(keys[0])


def _p_entry(p_schedule):
    """`durable_fraction`: the constant, or "scheduled" with the schedule under tx_release."""
    if len(p_schedule) == 1 and float(p_schedule[0][0]) == 0.0:
        return float(p_schedule[0][1]), None
    return "scheduled", [(float(t), float(v)) for t, v in p_schedule]


def checks_for(inputs, profile, run, role, machine, dt):
    """(what, root, path, kind, expected): SPEC.md's declaration of one run at §8.5's keys, and the
    SPEC.md inputs §8.5 gives no key for (unchecked)."""
    blank = run == "blank"
    labelled = role != "twin"
    V = float(inputs["volume_pL"])
    rows_gene = ["N", "M", "Pi", "R", "R_s"] + (["A", "ATP", "ADP", "P"] if profile == "B" else [])
    mu0 = dict(inputs["mu0_RT_at_1M"])
    out, unchecked = [], []

    def add(what, path, kind, exp, root=None):
        out.append((what, root, path, kind, exp))

    const = inputs["constants"]
    add("temperature", "model.temperature_K", "num", const["T_K"])
    add("c°", "model.standard_concentration_mM", "num", const["c_standard_mM"])
    add("the cell's volume", "model.cells[cell_0].volume_pL", "num", V)
    # the cell's initial amounts, in fmol
    amounts = {}
    if profile == "B":
        for r, c in inputs["initial_mM"].items():
            amounts[r] = float(c) * V
    else:
        for r, c in inputs["initial_mM"].items():
            amounts[r] = float(c) * V
        for r, n in inputs["initial_copies"].items():
            amounts[r] = float(n) * spec.COPY_FMOL
        for ion, c in inputs["cell_background_mM"].items():
            amounts[ion] = float(c) * V
        if profile == "C":
            amounts["Mx"] = float(inputs["store"]["Mx_initial_mM"]) * V
    for r, a in sorted(amounts.items()):
        add(f"initial {r}", f"model.cells[cell_0].initial_amount_fmol[{r}]", "num", a)
    # the held bath (the hold worlds)
    if profile != "B":
        vb = float(inputs["bath_volume_pL"])
        bath = {ion: float(c) * vb for ion, c in inputs["bath_mM"].items()}
        traced = ["N", "M", "Pi", "R", "R_s"] + (["Mx"] if profile == "C" else [])
        bath.update({r: float(inputs["bath_trace_mM"]) * vb for r in traced})
        for r, a in sorted(bath.items()):
            add(f"bath {r}", f"model.extracellular[bath_0].initial_amount_fmol[{r}]", "num", a)
        add("the bath is held", "model.extracellular[bath_0].reservoir", "exact", True)
        unchecked += ["the bath's volume (1.0 pL)", "the patch's area (10⁻¹⁰ m²)",
                      "the patch's solute permeabilities (0)"]  # fmt: skip
    # potentials, in the model and in the gene unit
    pot = {r: float(mu0[r]) for r in rows_gene}
    if profile == "C":
        pot_model = dict(pot, Mx=float(inputs["store"]["mu0_Mx_RT_at_1M"]))
    else:
        pot_model = pot
    for r, m in sorted(pot_model.items()):
        add(f"μ°/RT of {r}", f"model.species[{r}].standard_mu_RT", "num", m)
    for r, m in sorted(pot.items()):
        add(f"the gene unit's μ°/RT of {r}", f"species[{r}].standard_mu_RT", "num", m, GENE_UNIT)
    # moieties
    for moiety, weights in sorted(inputs["moieties"].items()):
        w = {k: float(v) for k, v in weights.items()}
        if profile == "C" and moiety in inputs["store"]["Mx_moieties"]:
            w["Mx"] = float(inputs["store"]["Mx_moieties"][moiety])
        add(f"the {moiety} moiety", f"model.moieties[{moiety}].weights", "weights", w)
    # the gene unit: pool, chain, release, degradations
    L = spec.chain_length(inputs)
    add("the pool", "pools[pol].machines", "num",
        float(_get(inputs, "pool_machines_copies", "M_pol_copies")), GENE_UNIT)  # fmt: skip
    ch = "chains[tx]"
    add("the template copies", f"{ch}.template.copies", "num", float(inputs["template_copies"]),
        GENE_UNIT)  # fmt: skip
    add("the product", f"{ch}.product", "exact", "R", GENE_UNIT)
    add("the residues", f"{ch}.residues", "num", float(L), GENE_UNIT)
    add("the stages", f"{ch}.stages", "num", float(_get(inputs, "stages", "m_tx")), GENE_UNIT)
    add("the speed", f"{ch}.speed_per_s", "num",
        float(_get(inputs, "speed_nt_per_s", "v_tx_nt_per_s")), GENE_UNIT)  # fmt: skip
    add("the draws", f"{ch}.draws", "map",
        {"N": float(_get(inputs, "N_per_residue", default=1))}, GENE_UNIT)  # fmt: skip
    add("the releases", f"{ch}.releases", "map",
        {"Pi": float(_get(inputs, "Pi_per_residue", default=2))}, GENE_UNIT)  # fmt: skip
    add("N's saturation", f"{ch}.saturation_mM", "map",
        {"N": float(_get(inputs, "K_N_mM", "K_N_tx_mM"))}, GENE_UNIT)  # fmt: skip
    rel = f"{ch}.release"
    add("τ", f"{rel}.dwell_s", "num", float(inputs["tau_s"]), GENE_UNIT)
    if blank:
        add("the machine", f"{rel}.machine", "exact", machine, GENE_UNIT)
        add("H(0)", f"{rel}.initial_copies", "nums", [0.0], GENE_UNIT)
        p_sched = None
    else:
        rdef = inputs["runs"][run]
        add("the machine", f"{rel}.machine", "exact", rdef["machine"], GENE_UNIT)
        df, p_sched = _p_entry(rdef["p"])
        add("p", f"{rel}.durable_fraction", "exact" if isinstance(df, str) else "num", df,
            GENE_UNIT)  # fmt: skip
        add("H(0)", f"{rel}.initial_copies", "nums", [float(inputs["H0_copies"])], GENE_UNIT)
    add("the fates", f"{rel}.fates", "exact", {"durable": "R", "short_lived": "R_s"}, GENE_UNIT)
    add("the label's marking", f"{rel}.label", "exact", {"at": "release"}, GENE_UNIT)
    for deg, row in (("deg_R", "R"), ("deg_R_s", "R_s")):
        add(f"{deg}'s polymer", f"degradations[{deg}].polymer", "exact", row, GENE_UNIT)
        add(f"{deg}'s residues", f"degradations[{deg}].residues", "num", float(L), GENE_UNIT)
        add(f"{deg}'s monomers", f"degradations[{deg}].monomers", "exact", "M", GENE_UNIT)
    # the rates
    pc = "experiment.polymerisation_controls"
    k_i = 0.0 if blank else float(_get(inputs, "k_I_tx_per_mM_s", "k_I_per_mM_s"))
    add("k_I", f"{pc}[tx].schedule", "schedule", [(0.0, k_i)])
    add("k_d", f"{pc}[deg_R].schedule", "schedule", [(0.0, float(inputs["k_d_per_s"]))])
    add("k_s", f"{pc}[deg_R_s].schedule", "schedule", [(0.0, float(inputs["k_s_per_s"]))])
    if p_sched is not None:
        add("p's schedule", f"{pc}[tx_release].schedule", "schedule", p_sched)
    # the labels
    if labelled:
        shares = {k: float(v) for k, v in inputs["initial_label_shares"].items()}
        sched = inputs["label_schedule_s"]
        source = [(float(sched["pre"]), "pre"), (float(sched["win"]), "win"),
                  (float(sched["post"]), "post")]  # fmt: skip
        for row in ("R", "R_s"):
            add(f"{row}'s labels", f"species[{row}].labels", "labels", list(spec.CLASSES),
                LABEL_OWNER)  # fmt: skip
            add(f"{row}'s initial shares", f"species[{row}].initial", "initial", shares,
                LABEL_OWNER)  # fmt: skip
            add(f"{row}'s own label", row, "arrivals_own", [(0.0, "resyn")])
            add(f"{row}'s source schedule", row, "arrivals_source", source)
    else:
        unchecked.append("how a twin's declaration shows it is unlabelled")
    # the grid
    add("the horizon", "experiment.end_time", "num", float(inputs["horizon_s"]))
    add("the outputs", "experiment.observation_times", "nums", spec.grid(inputs))
    add("the step", "execution.dt", "num", float(dt))
    if profile == "C":
        st = inputs["store"]
        add("the network's c0", "standard_concentration_mM", "num", float(st["network_c0_mM"]),
            STORE)  # fmt: skip
        for r in ("M", "Mx"):
            add(f"the network's μ°/RT of {r}", f"species[{r}].standard_mu_RT", "num",
                float(st["network_mu0_RT_at_c0"][r]), STORE)  # fmt: skip
        mm = {m: float(w["M"]) for m, w in inputs["moieties"].items() if "M" in w}
        add("M's moieties in the network", "species[M].moieties", "map", mm, STORE)
        add("Mx's moieties in the network", "species[Mx].moieties", "map",
            {k: float(v) for k, v in st["Mx_moieties"].items()}, STORE)  # fmt: skip
        r = "reactions[store_M]"
        add("the store's sites", f"{r}.sites", "exact", ["cell_0"], STORE)
        add("the store's reactants", f"{r}.reactants", "map", {"M": 1.0}, STORE)
        add("the store's products", f"{r}.products", "map", {"Mx": 1.0}, STORE)
        add("the store's law", f"{r}.law", "exact", "ideal_detailed_balance_mass_action@1", STORE)
        add("the store's forward rate", f"{r}.forward_rate_per_s", "num",
            float(st["forward_per_s_at_c0"]), STORE)  # fmt: skip
        add("the store's multiplier", "experiment.reaction_controls[store_M].schedule",
            "schedule", [(0.0, float(st["multiplier"]))])  # fmt: skip
    if profile == "D":
        w = inputs["water"]
        c = "compartments[cell_0]"
        for key, val in (("reference_volume_pL", w["V_ref_pL"]), ("minimum_volume_pL",
                         w["V_min_pL"]), ("maximum_volume_pL", w["V_max_pL"]),
                         ("impermeant_amount_fmol", w["impermeant_fmol"]),
                         ("bulk_modulus_Pa", w["bulk_modulus_Pa"]),
                         ("pressure_offset_Pa", w["pressure_offset_Pa"])):  # fmt: skip
            add(f"water's {key}", f"{c}.{key}", "num", float(val), WATER)
        add("the bath's pressure", "baths[bath_0].hydrostatic_pressure_Pa", "num",
            float(w["bath_pressure_Pa"]), WATER)  # fmt: skip
        add("L_p", "membranes[patch_0].hydraulic_permeability_m_per_Pa_s", "num",
            float(w["L_p_m_per_Pa_s"]), WATER)  # fmt: skip
        add("water's availability", "experiment.water_controls", "availability",
            [(0.0, float(w["availability"]))])  # fmt: skip
    if profile == "B":
        if "L_P_aa" in inputs:
            Lp = float(inputs["L_P_aa"])
            add("the ribosomes", "pools[rib].machines", "num", float(inputs["M_rib_copies"]),
                GENE_UNIT)  # fmt: skip
            for c in ("tl", "tl_s"):
                ch = f"chains[{c}]"
                add(f"{c}'s product", f"{ch}.product", "exact", "P", GENE_UNIT)
                add(f"{c}'s residues", f"{ch}.residues", "num", Lp, GENE_UNIT)
                add(f"{c}'s stages", f"{ch}.stages", "num", float(inputs["m_tl"]), GENE_UNIT)
                add(f"{c}'s speed", f"{ch}.speed_per_s", "num", float(inputs["v_tl_aa_per_s"]),
                    GENE_UNIT)  # fmt: skip
                add(f"{c}'s draws", f"{ch}.draws", "map", {"A": 1.0, "ATP": 4.0}, GENE_UNIT)
                add(f"{c}'s releases", f"{ch}.releases", "map", {"ADP": 4.0, "Pi": 4.0},
                    GENE_UNIT)  # fmt: skip
                add(f"{c}'s saturation", f"{ch}.saturation_mM", "map",
                    {"A": float(inputs["K_A_tl_mM"]), "ATP": float(inputs["K_ATP_tl_mM"])},
                    GENE_UNIT)  # fmt: skip
                add(f"{c}'s initiation", f"{pc}[{c}].schedule", "schedule",
                    [(0.0, float(inputs["k_I_tl_per_mM_s"]))])  # fmt: skip
            add("deg_P's polymer", "degradations[deg_P].polymer", "exact", "P", GENE_UNIT)
            add("deg_P's residues", "degradations[deg_P].residues", "num", Lp, GENE_UNIT)
            add("deg_P's monomers", "degradations[deg_P].monomers", "exact", "A", GENE_UNIT)
            add("k_P", f"{pc}[deg_P].schedule", "schedule", [(0.0, float(inputs["k_P_per_s"]))])
        unchecked += [
            "tl's and tl_s's templates (R and R_s)",
            "the recharging transfer (V_C, K_M_rc, K_ATP_rc)",
            "the regulator's turnover (P_on, k_X, t_off)",
            "the coupling (K_X, n_X, b_X) and the factor on transcription's initiation",
        ]
    return out, unchecked


def _arrival(defn, row, source):
    arr = get(defn, "experiment.label_arrivals")
    if not isinstance(arr, list):
        raise Unreadable("experiment.label_arrivals is not a list")
    hits = [e for e in arr if isinstance(e, dict) and e.get("species") == row
            and ((e.get("source") == "tx") if source else ("source" not in e))]  # fmt: skip
    if len(hits) != 1:
        kind = "source" if source else "own"
        raise Unreadable(f"{len(hits)} {kind} label-arrival entries for {row}")
    return hits[0].get("schedule")


def check_definition(defn, inputs, profile, run, role, machine, dt):
    """C0's echo check of one run's declaration. Returns (faults, unchecked)."""
    faults = []
    if not isinstance(defn, dict):
        return [f"definition is not an object ({type(defn).__name__})"], []
    items, unchecked = checks_for(inputs, profile, run, role, machine, dt)
    cache = {}
    for what, root, path, kind, exp in items:
        try:
            if kind == "arrivals_own":
                _cmp_schedule(_arrival(defn, path, False), exp, "label")
                continue
            if kind == "arrivals_source":
                _cmp_schedule(_arrival(defn, path, True), exp, "label")
                continue
            got = get(defn, path, root, cache)
            if kind == "num":
                _cmp_num(got, exp)
            elif kind == "exact":
                _cmp_exact(got, exp)
            elif kind == "nums":
                _cmp_nums(got, exp)
            elif kind == "map":
                _cmp_map(got, exp)
            elif kind == "weights":
                _cmp_weights(got, exp)
            elif kind == "schedule":
                _cmp_schedule(got, exp)
            elif kind == "availability":
                _cmp_schedule(got, exp, "availability")
            elif kind == "labels":
                if not (isinstance(got, list) and got and got[0] == "resyn"
                        and sorted(got) == sorted(exp) and len(got) == len(exp)):  # fmt: skip
                    raise Unreadable(f"expected the labels {exp!r}, base first, found {got!r}")
            elif kind == "initial":
                if not isinstance(got, list):
                    raise Unreadable(f"initial is not a list: {got!r}")
                cell = [e for e in got if isinstance(e, dict) and e.get("node") == "cell_0"]
                if len(cell) != 1:
                    raise Unreadable(f"{len(cell)} initial entries for cell_0")
                _cmp_map(cell[0].get("shares"), exp)
            else:
                raise KeyError(kind)
        except Unreadable as exc:
            where = f"{root}: " if root else ""
            faults.append(f"definition: {what} ({where}{path}): {exc}")
    return faults, unchecked


# ------------------------------------------------------------------ the plants (§8.5)


def leaf_diff(a, b, path=()):
    """Every leaf where two declarations differ, as (path, honest, planted); a missing key or an
    unequal list length is a leaf."""
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for k in sorted(set(a) | set(b), key=str):
            if k not in a or k not in b:
                out.append((path + (k,), a.get(k, "<absent>"), b.get(k, "<absent>")))
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
    if a == b and type(a) is type(b):
        return []
    if _num(a) and _num(b) and float(a) == float(b):
        return []
    return [(path, a, b)]


def _raw_path(defn, path, root=None):
    return locate(defn, path, root)[1]


def plant_change_faults(plant, honest, planted, family_inputs):
    """§8.5: the plant's declaration equals its honest run's except for its registered change."""
    if not isinstance(honest, dict) or not isinstance(planted, dict):
        return ["a declaration is not an object"]
    diff = leaf_diff(honest, planted)
    t1, t2 = (float(x) for x in family_inputs["window_s"])
    old = t1 if plant == "P3a" else t2

    def scaled(factor):
        def check(h, p):
            return _num(h) and _num(p) and _close(float(p), float(h) * factor)

        return check

    def becomes(a, b):
        def check(h, p):
            return h == a and p == b

        return check

    def late(h, p):
        return _num(h) and _num(p) and float(h) == old and _close(float(p), old + spec.H_STEP_S)

    def leak(h, p):
        return _num(p) and _close(float(p), 1.0 - 2.0**-30)

    try:
        if plant == "P9":  # the gene unit reads V₀ through a host-side patch: no declared change
            allowed, check = (), None
        elif plant == "P2":
            allowed = (_raw_path(planted, "chains[tx].release.durable_fraction", GENE_UNIT),)
            check = leak
        elif plant == "P4":
            allowed = (_raw_path(planted, "chains[tx].release.label", GENE_UNIT) + ("at",),)
            check = becomes("release", "completion")
        elif plant == "P7":
            allowed = (_raw_path(planted, "chains[tx].release.machine", GENE_UNIT),)
            check = becomes("held", "returned")
        elif plant == "P5":
            allowed = (_raw_path(planted, "experiment.polymerisation_controls[deg_R_s].schedule"),)
            check = scaled(1.0 + 1e-4)
        elif plant == "P8":
            allowed = (_raw_path(planted, "reactions[store_M].forward_rate_per_s", STORE),)
            check = scaled(1.01)
        elif plant in ("P3a", "P3b"):
            arr = get(planted, "experiment.label_arrivals")
            base = _raw_path(planted, "experiment.label_arrivals")
            allowed = tuple(base + (i,) for i, e in enumerate(arr)
                            if isinstance(e, dict) and e.get("source") == "tx")  # fmt: skip
            check = late
        else:
            return [f"{plant} has no registered declaration change"]
    except Unreadable as exc:
        return [f"{plant}'s registered change is not where §8.5 puts it: {exc}"]
    faults = []
    for path, h, p in diff:
        where = "/".join(map(str, path))
        if not any(path[: len(a)] == a for a in allowed):
            faults.append(f"{plant}: the declaration differs from its honest run's at {where} "
                          f"({h!r} → {p!r}), not its registered change")  # fmt: skip
        elif plant in ("P3a", "P3b") and path[-1] != "time":
            faults.append(f"{plant}: a source schedule differs at {where}")
        elif check is not None and not check(h, p):
            faults.append(f"{plant}: its registered change reads {h!r} → {p!r}")
    if plant != "P9" and not diff:
        faults.append(f"{plant}: the declaration equals its honest run's (no registered change)")
    return faults
