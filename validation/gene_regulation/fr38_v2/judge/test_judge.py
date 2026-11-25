"""Host-only tests of FR-38's second comparison judge, on invented inputs only.

**Seconds:** 50 to 70 s of CPU for its 32 tests, on light CPUs other jobs shared (25 November 2026).
**Reason (D224):** the judge decides FR-38's registered verdict, so each C0 refusal, each failure
and inconclusive mode, the retry and each plant (caught and not caught) must be shown to move it
the registered way before any engine run is judged.

- **Inputs.** The references' invented file (`reference_invented.json`, read from the tree or
  from tag `fr38-v2-references-2026-11-24`; the test fails if neither has it), invented families
  of profiles B, C and D derived from it here, and engine records invented here. The registered
  branches (AF's two blanks, AN's restart, the plants' runs, the arms) run on invented families
  given the registered roles.
- **The engine's tables** (amendments 4 and 5) are written by this file's own builder
  (`engine_definition`, `Synth`), apart from the judge's expectations (`definitions.py`), with every
  key the format sample's README lists and their lists backwards. The format sample itself is not
  read here: the check on it is a command of its own (`sample`, amendment 5, §5).
- **No engine** is compiled, imported or run, and no engine output is read.
- **The honest invented engine** scales every deviation from t = 0 by 1 + C3 dt³, which keeps every
  linear identity and every structural zero and gives each readout an observed order of 3.
"""

import copy
import hashlib
import json
import math
import os
import shutil
import subprocess
import types

import numpy as np
import pytest

from validation.gene_regulation.fr38_v2.judge import (
    definitions,
    records,
    rules,
    sample,
    shapes,
    spec,
)
from validation.gene_regulation.fr38_v2.judge import judge as J

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
TAG = "fr38-v2-references-2026-11-24"
INVENTED = "validation/gene_regulation/fr38_v2/references/out/reference_invented.json"
SHAPES = shapes.load_shapes()
C3 = 1e-6  # the honest engine's step error, relative to each deviation, times dt³


def _invented_bytes():
    path = os.path.join(REPO, INVENTED)
    if os.path.exists(path):
        return open(path, "rb").read()
    out = subprocess.run(["git", "-C", REPO, "show", f"{TAG}:{INVENTED}"], capture_output=True)
    if out.returncode != 0:
        pytest.fail(f"reference_invented.json is neither in the tree nor at tag {TAG}")
    return out.stdout


@pytest.fixture(scope="module")
def invented():
    return json.loads(_invented_bytes())


@pytest.fixture(scope="module")
def mapping():
    return J.load_mapping()


# ------------------------------------------------------------------ invented engine records


def _scaled(values, dt, c=C3, order=3):
    v = np.asarray(values, dtype=np.float64)
    return v + c * dt**order * (v - v[0])


def _shape(ref_values, times, t_e):
    """A planted change's shape: 1 at the reference's largest-distance time, 0 where the readout is
    a structural zero."""
    v = np.asarray(ref_values, dtype=np.float64)
    i = times.index(t_e)
    if not np.any(v != 0.0):
        return np.asarray(times) / t_e if t_e > 0 else np.ones(len(times))
    if t_e == 0.0 or v[i] == v[0]:
        return np.ones(len(times))
    return (v - v[0]) / (v[i] - v[0])


COPY = 1e15 / 6.02214076e23  # the test's own: one copy, in fmol
SPECIES = {"A": ["K", "Y", "N", "M", "Pi", "R", "R_s"],
           "B": ["K", "Y", "X", "N", "M", "A", "ATP", "ADP", "Pi", "R", "P", "R_s"],
           "C": ["K", "Y", "N", "M", "Pi", "R", "R_s", "Mx"],
           "D": ["K", "Y", "N", "M", "Pi", "R", "R_s"]}  # fmt: skip


def operator(defn, law):
    return next(o for o in defn["model"]["operators"] if o.get("law") == law)


def named(items, name, field="id"):
    return next(x for x in items if x.get(field) == name)


def _gene(defn):
    return operator(defn, "templated_polymerisation@1")


def release(rec):
    """The transcription chain's release block of a record's declaration."""
    return named(_gene(rec["definition"])["chains"], "tx")["release"]


def control(rec, route):
    return named(rec["definition"]["experiment"]["polymerisation_controls"], route, "route_id")


def _steps(*pairs, field="value"):
    return [{"time": float(t), field: v} for t, v in pairs]


def engine_definition(inputs, profile, run, role, plant, machine, dt):
    """An engine declaration with SPEC.md's inputs where amendments 4 and 5 put them and every key
    the format sample's README lists: the test's own builder, written apart from the judge's
    expectations (definitions.py). Its lists run backwards, since the reader matches by name."""
    V = float(inputs["volume_pL"])
    blank, hold, sp = run == "blank", profile != "B", SPECIES[profile]
    mu0 = {k: float(v) for k, v in inputs["mu0_RT_at_1M"].items()}
    cell = {r: float(c) * V for r, c in inputs["initial_mM"].items()}
    if hold:
        cell.update({r: float(n) * COPY for r, n in inputs["initial_copies"].items()})
        cell.update({i: float(c) * V for i, c in inputs["cell_background_mM"].items()})
        vb = float(inputs["bath_volume_pL"])
        bath = {s: float(inputs["bath_trace_mM"]) * vb for s in sp}
        bath.update({i: float(c) * vb for i, c in inputs["bath_mM"].items()})
    else:
        cell.update(K=140.0, Y=140.0)
        vb, bath = 1.0, {s: 1e-15 for s in sp}
    if profile == "C":
        cell["Mx"] = float(inputs["store"]["Mx_initial_mM"]) * V
        mu0["Mx"] = float(inputs["store"]["mu0_Mx_RT_at_1M"])
    rows = ["N", "M", "Pi", "R", "R_s"] + ([] if hold else ["A", "ATP", "ADP", "P"])
    L = inputs.get("L_residues", inputs.get("L_R_nt"))
    if blank:
        ps, m = inputs["p_sched"], machine
    else:
        ps, m = inputs["runs"][run]["p"], inputs["runs"][run]["machine"]
    constant = len(ps) == 1 and float(ps[0][0]) == 0.0
    free = {"dG_RT": -1.0} if hold else {"basis": "invented", "dG_RT_offset": 0.0,
                                         "dG_kJ_mol": 0.0}  # fmt: skip
    tx = {"id": "tx", "template": {"copies": inputs["template_copies"]}, "product": "R",
          "pool": "pol", "residues": L, "stages": inputs.get("stages", inputs.get("m_tx")),
          "speed_per_s": inputs.get("speed_nt_per_s", inputs.get("v_tx_nt_per_s")),
          "draws": {"N": inputs.get("N_per_residue", 1)},
          "releases": {"Pi": inputs.get("Pi_per_residue", 2)},
          "saturation_mM": {"N": inputs.get("K_N_mM", inputs.get("K_N_tx_mM"))},
          "release": {"id": "tx_release", "dwell_s": inputs["tau_s"], "machine": m,
                      "durable_fraction": float(ps[0][1]) if constant else "scheduled",
                      "fates": [{"durable": "R", "short_lived": "R_s"}],
                      "label": {"at": "release"},
                      "initial_copies": [
                          0.0 if blank else float(inputs["H0_copies"])]}}  # fmt: skip

    def deg(name, polymer, monomer, residues):
        return {"id": name, "cell": "cell_0", "polymer": polymer, "monomers": {monomer: 1},
                "residues": residues, "standard_free_energy": dict(free)}  # fmt: skip

    gene = {"law": "templated_polymerisation@1", "chains": [tx],
            "degradations": [deg("deg_R", "R", "M", L), deg("deg_R_s", "R_s", "M", L)],
            "pools": [{"id": "pol", "cell": "cell_0", "machines": float(
                inputs.get("pool_machines_copies", inputs.get("M_pol_copies")))}],
            "species": [{"id": r, "catalogue": None, "evidence": None, "standard_mu_RT": mu0[r]}
                        for r in rows],
            "standard_concentration_mM": inputs["constants"]["c_standard_mM"],
            "transfers": []}  # fmt: skip
    k_i = 0.0 if blank else float(inputs.get("k_I_tx_per_mM_s", inputs["k_I_per_mM_s"]))
    controls = [("tx", _steps((0, k_i))), ("deg_R", _steps((0, inputs["k_d_per_s"]))),
                ("deg_R_s", _steps((0, inputs["k_s_per_s"])))]  # fmt: skip
    if not constant:
        controls.append(("tx_release", _steps(*ps)))
    operators = [gene]
    n = int(round(float(inputs["horizon_s"]) / float(inputs["output_interval_s"])))
    exp = {"calcium_pump_controls": [], "channel_controls": [], "junction_controls": [],
           "pump_controls": [], "end_time": inputs["horizon_s"],
           "membrane_controls": [{"membrane_id": "patch_0",
                                  "schedule": _steps((0, 1.0), field="availability")}],
           "observation_times": [
               float(inputs["output_interval_s"]) * i for i in range(n + 1)]}  # fmt: skip
    if not hold:
        _a1(inputs, gene, controls, operators, exp, deg)
    exp["polymerisation_controls"] = [{"route_id": r, "schedule": s} for r, s in controls][::-1]
    if role != "twin":
        s = inputs["label_schedule_s"]
        operators.append({"law": "neutral_arrival_labels@1", "species": [
            {"id": r, "labels": ["post", "win", "pre", "pool0", "resyn"],
             "initial": [{"node": "cell_0", "shares": dict(inputs["initial_label_shares"])}]}
            for r in ("R_s", "R")]})  # fmt: skip
        exp["label_arrivals"] = [
            {"species": "R", "source": "tx", "schedule": _steps(
                (s["pre"], "pre"), (s["win"], "win"), (s["post"], "post"), field="label")},
            {"species": "R_s", "schedule": _steps((0, "resyn"), field="label")},
            {"species": "R", "schedule": _steps((0, "resyn"), field="label")},
        ]  # fmt: skip
    if profile == "C":
        st = inputs["store"]
        weights = {"M": {k: w["M"] for k, w in inputs["moieties"].items()}, "Mx": st["Mx_moieties"]}
        operators.append({
            "law": "local_species_reactions@1", "standard_concentration_mM": st["network_c0_mM"],
            "species": [{"id": r, "catalogue": None, "evidence": None, "moieties": dict(weights[r]),
                         "standard_mu_RT": st["network_mu0_RT_at_c0"][r]} for r in ("Mx", "M")],
            "reactions": [{"id": "store_M", "law": "ideal_detailed_balance_mass_action@1",
                           "sites": {"cells": ["cell_0"]}, "reactants": {"M": 1},
                           "products": {"Mx": 1}, "factors": [],
                           "forward_rate_per_s": st["forward_per_s_at_c0"]}]})  # fmt: skip
        exp["reaction_controls"] = [{"reaction_id": "store_M", "site": None, "schedule": _steps(
            (0, st["multiplier"]), field="multiplier")}]  # fmt: skip
    if profile == "D":
        w = inputs["water"]
        operators.append({
            "law": "ideal_osmosis_linear_compliance_water@1",
            "compartments": [{"compartment_id": "cell_0", "reference_volume_pL": w["V_ref_pL"],
                              "minimum_volume_pL": w["V_min_pL"],
                              "maximum_volume_pL": w["V_max_pL"],
                              "impermeant_amount_fmol": w["impermeant_fmol"],
                              "bulk_modulus_Pa": w["bulk_modulus_Pa"],
                              "pressure_offset_Pa": w["pressure_offset_Pa"]}],
            "baths": [{"compartment_id": "bath_0",
                       "hydrostatic_pressure_Pa": w["bath_pressure_Pa"]}],
            "membranes": [{"membrane_id": "patch_0",
                           "hydraulic_permeability_m_per_Pa_s": w["L_p_m_per_Pa_s"]}]})  # fmt: skip
        exp["water_controls"] = [{"membrane_id": "patch_0", "schedule": _steps(
            (0, w["availability"]), field="availability")}]  # fmt: skip
    moieties = []
    for name, w in inputs["moieties"].items():
        w = {k: int(v) for k, v in w.items()}
        if profile == "C":
            w["Mx"] = int(inputs["store"]["Mx_moieties"][name])
        moieties.append({"id": name, "weights": w})
    valence = {"K": 1, "Y": -1}
    model = {
        "id": "invented", "inner_model": "invented", "channels": [], "faces": [], "junctions": [],
        "closure": {"gauge_reference": None, "law": "invented"},
        "temperature_K": inputs["constants"]["T_K"],
        "standard_concentration_mM": inputs["constants"]["c_standard_mM"],
        "cells": [{"id": "cell_0", "volume_pL": V, "initial_amount_fmol": {s: cell[s] for s in sp},
                   "fixed_charge_equivalent_fmol": 0.0, "initial_charge_C": 0.0}],
        "extracellular": [{"id": "bath_0", "volume_pL": vb, "reservoir": True,
                           "initial_amount_fmol": bath, "boundary_potential_V": 0.0,
                           "fixed_charge_equivalent_fmol": 0.0, "initial_charge_C": 0.0}],
        "membranes": [{"id": "patch_0", "law": "constant_field@1", "inside": "cell_0",
                       "outside": "bath_0", "area_m2": float(inputs.get("patch_area_m2", 1e-10)),
                       "capacitance_F": 1e-12, "calcium_pump": None, "pump": None,
                       "permeability_m_per_s": {s: 0.0 for s in sp}}],
        "moieties": moieties[::-1], "operators": operators[::-1],
        "species": [dict({"id": s, "valence": valence.get(s, 0)}, **(
            {} if s in ("K", "Y", "X") else {"standard_mu_RT": mu0[s]})) for s in sp][::-1],
    }  # fmt: skip
    execution = {"dt": dt, "backend": "invented", "precision": "float64", "jit": True,
                 "solver": "invented", "field_solver": "invented", "max_steps": 100000,
                 "max_trace_bytes": 1000,
                 "material_balance_atol_fmol": {s: 1e-12 for s in sp}}  # fmt: skip
    for k in ("capacity", "channel_capacity", "edge_capacity", "extracellular_capacity",
              "face_capacity", "membrane_capacity"):  # fmt: skip
        execution[k] = 1
    defn = {"schema_version": 1, "execution": execution, "experiment": exp, "model": model}
    if plant is not None:
        _plant_declaration({"definition": defn}, plant)
    return defn


def _a1(inputs, gene, controls, operators, exp, deg):
    """Arm B's own declarations: translation, the ribosomes, deg_P, recharging, the regulator."""
    gene["pools"].append({"id": "rib", "cell": "cell_0", "machines": float(inputs["M_rib_copies"])})
    for c, template in (("tl", "R"), ("tl_s", "R_s")):
        gene["chains"].append({"id": c, "template": {"species": template}, "product": "P",
                               "pool": "rib", "residues": inputs["L_P_aa"],
                               "stages": inputs["m_tl"], "speed_per_s": inputs["v_tl_aa_per_s"],
                               "draws": {"A": 1, "ATP": 4}, "releases": {"ADP": 4, "Pi": 4},
                               "saturation_mM": {"A": inputs["K_A_tl_mM"],
                                                 "ATP": inputs["K_ATP_tl_mM"]}})  # fmt: skip
        controls.append((c, _steps((0, inputs["k_I_tl_per_mM_s"]))))
    gene["degradations"].append(deg("deg_P", "P", "A", inputs["L_P_aa"]))
    gene["transfers"].append({"id": "recharge", "cell": "cell_0", "share": 2,
                              "saturation_mM": {"ATP": inputs["K_ATP_rc_mM"],
                                                "M": inputs["K_M_rc_mM"]},
                              "stoichiometry": {"N": 1, "M": -1, "ATP": -2, "ADP": 2},
                              "standard_free_energy": {"dG_RT": -1.0}})  # fmt: skip
    controls += [("deg_P", _steps((0, inputs["k_P_per_s"]))),
                 ("recharge", _steps((0, inputs["V_C_mM_per_s"])))]  # fmt: skip
    operators.append({
        "law": "scheduled_species_turnover@1", "templates": [],
        "routes": [{"id": r, "kind": k, "node": "cell_0", "species": "X"} for r, k in (
            ("x_clearance", "clearance"), ("x_production", "production"))],
        "species": [{"id": "X", "catalogue": None, "evidence": None}]})  # fmt: skip
    exp["turnover_controls"] = [
        {"route_id": "x_clearance", "carrier_id": "X", "schedule": _steps(
            (0, inputs["k_X_per_s"]), (inputs["t_off_s"], inputs["k_X_per_s"]), field="rate")},
        {"route_id": "x_production", "carrier_id": "X", "schedule": _steps(
            (0, inputs["P_on_fmol_per_s"]), (inputs["t_off_s"], 0.0), field="rate")},
    ]  # fmt: skip
    operators.append({
        "law": "species_regulated_availability@2", "states": [],
        "couplings": [{"id": "c_regulator", "law": "hill_activation", "basal": inputs["b_X"],
                       "half_saturation_mM": inputs["K_X_mM"],
                       "hill_coefficient": float(inputs["n_X"]), "source": {"species": "X"},
                       "target": {"operator": "templated_polymerisation@1", "ids": ["tx"],
                                  "control": "initiation_rate", "evaluation": "invented",
                                  "operating_range": [0.02, 1.0]}}],
        "species": [{"id": "X", "catalogue": None, "evidence": None}]})  # fmt: skip
    exp["coupling_controls"] = [{"coupling_id": "c_regulator", "schedule": [
        {"time": 0.0, "enabled": 1}]}]  # fmt: skip
    exp["regulatory_writes"] = []


def _plant_declaration(rec, plant):
    """A world-data plant's registered change, written into its declaration (CRITERIA.md §6)."""
    defn = rec["definition"]
    if plant == "P2":
        release(rec)["durable_fraction"] = 1.0 - 2.0**-30
    elif plant in ("P3a", "P3b"):
        label = "win" if plant == "P3a" else "post"
        source = named(defn["experiment"]["label_arrivals"], "tx", "source")
        named(source["schedule"], label, "label")["time"] += 0.5
    elif plant == "P4":
        release(rec)["label"] = {"at": "completion"}
    elif plant == "P5":
        step = control(rec, "deg_R_s")["schedule"][0]
        step["value"] = step["value"] * (1 + 1e-4)
    elif plant == "P7":
        release(rec)["machine"] = "returned"
    elif plant == "P8":
        operator(defn, "local_species_reactions@1")["reactions"][0]["forward_rate_per_s"] *= 1.01


def write_sums(folder):
    lines = []
    for fn in sorted(os.listdir(folder)):
        if fn.startswith("table_") and fn.endswith(".json"):
            with open(os.path.join(folder, fn), "rb") as fh:
                lines.append(f"{hashlib.sha256(fh.read()).hexdigest()}  {fn}\n")
    with open(os.path.join(folder, "SHA256SUMS"), "w") as fh:
        fh.write("".join(lines))


SOURCE = {"checkout_dirty": False, "engine_revision": "invented revision",
          "snapshot": "invented snapshot",
          "snapshot_patch_sha256": hashlib.sha256(b"").hexdigest()}  # fmt: skip
V0_PATCH = {"id": "V0", "operator": "templated_polymerisation@1", "change": "invented",
            "code": "invented"}  # fmt: skip
CHECKS = {k: 1e-20 for k in (
    "G_identity_largest_pJ", "G_identity_over_sum_H_at_end", "H_total_at_end_pJ",
    "energy_magnitude_at_end_pJ", "routes_minus_total_largest_pJ",
    "routes_minus_total_over_magnitude")}  # fmt: skip
LABELLED_ONLY = ("label_", "released_present_gross_")
_BASES, _REFERENCES = {}, {}


class Synth:
    """Writes the engine's tables (amendments 4 and 5) for one invented family."""

    def __init__(self, doc, profile, mapping, role=None):
        self.doc, self.profile, self.mapping, self.role = doc, profile, mapping, role
        self.family = doc["family"]
        self.inputs = doc["inputs"]
        self.times = list(doc["times_s"])
        self.window = tuple(self.inputs["window_s"])
        self.samples = list(doc["samples_s"])
        self.horizon = float(self.inputs["horizon_s"])
        self.two_blanks = False
        self.tweaks = []  # (predicate(rec), function(rec) or None to drop it) before writing
        self.entry_tweaks = []  # (predicate(rec), function(entry)) on the entry as written
        self.table_tweaks = []  # function(table, attempt) on the table as written
        self._base = None

    def base(self):
        """The honest records, built once per document and role (writes copy them)."""
        if self._base is None:
            key = (id(self.doc), self.profile, self.role, self.two_blanks)
            if key not in _BASES:
                _BASES[key] = (self.doc, self.all_records())  # the document stays alive: its id too
            self._base = _BASES[key][1]
        return self._base

    def has_blank(self):
        return "blank" in self.doc["runs"]

    def series(self, run, dt, attempt="primary"):
        ref = self.doc["runs"][run]["series"]
        out = {k: _scaled(s["value"], dt) for k, s in ref.items()}
        if run != "blank" and self.has_blank():
            b = self.series("blank", dt)
            for fate, row in (("durable", "R"), ("short_lived", "R_s")):
                out[f"excess_over_blank_{fate}"] = out[f"n_{row}"] - b[f"n_{row}"]
        return out

    def exports(self, role):
        """engine_run's other exports, which no readout reads (item 4): recorded only."""
        names = SHAPES["readouts"][{"A": "AF", "B": "B", "C": "C", "D": "D"}[self.profile]]
        have = {e["engine"].partition("/")[2] for e in self.mapping["readouts"]
                if e["engine"].startswith("series/")}  # fmt: skip
        zero = np.zeros(len(self.times))
        return {n: zero for n in names if n not in have
                and not (role == "twin" and n.startswith(LABELLED_ONLY))}  # fmt: skip

    def host(self, series, definition):
        t1, t2 = self.window
        route2, survival = [], []
        for fate, row, deg in (("short_lived", "R_s", "deg_R_s"), ("durable", "R", "deg_R")):
            A = series[f"int_Q_tx_release_{fate}"]
            k = float(control({"definition": definition}, deg)["schedule"][0]["value"])
            for ts in self.samples[::-1]:
                value = rules.known_rate(self.times, A, k, t1, t2, ts)
                route2.append({"fate": fate, "ts_s": ts, "grid_error": 0.0, "k_per_s": k,
                               "value": value})  # fmt: skip
            win = series[f"label_{row}_win"]
            a2 = float(win[self.times.index(t2)])
            for ts in self.samples[1:]:
                a3 = float(win[self.times.index(ts)])
                ratio = a3 / a2 if a2 != 0.0 else None
                survival.append({"fate": fate, "t2_s": t2, "ts_s": ts, "alive_t2": a2,
                                 "alive_ts": a3, "ratio": ratio})  # fmt: skip
        return route2, survival

    def plant_name(self, plant, run):
        if plant == "P4":
            return "P4 B" if self.profile == "B" else "P4 AN"
        return "P8 blank" if plant == "P8" and run == "blank" else plant

    def record(self, run, role, dt, *, attempt="primary", plant=None, machine="returned"):
        series = self.series("blank" if run == "blank" else run, dt, attempt)
        name = {"blank": f"blank {machine}", "twin": f"{run} unlabelled", "restart": "restart",
                "plant": self.plant_name(plant, run)}.get(role, run)  # fmt: skip
        definition = engine_definition(self.inputs, self.profile, run, role, plant, machine, dt)
        rec = {"family": self.family, "name": name, "run": run, "role": role, "plant": plant,
               "attempt": attempt, "dt_s": dt, "machine": machine if run == "blank" else None,
               "status": "completed", "refusal": None, "times_s": list(self.times), "blank": None,
               "definition": definition, "source": dict(SOURCE),
               "record": f"records/{self.family}/{name}_{attempt}_{dt}.json",
               "record_sha256": hashlib.sha256(
                   f"{self.family}/{name}/{attempt}/{dt}".encode()).hexdigest(),
               "steps": int(round(self.horizon / dt)),
               "checks": dict(CHECKS, exported_cell="cell_0", smallest_class_increment={
                   h: 0.0 for h in rules.HEATS["B" if self.profile == "B" else "A"]}),
               "own": {"poly_machines": [0.0], "poly_residues": [0.0, 0.0]}}  # fmt: skip
        route2, survival = self.host(self.series("blank" if run == "blank" else run, dt, attempt),
                                     definition)  # fmt: skip
        rec["route2"] = route2
        if role != "twin":
            rec["survival"] = survival
        if role == "twin":
            series = {k: v for k, v in series.items() if not k.startswith(LABELLED_ONLY)}
        if run == "blank" or (role == "plant" and plant != "P8"):
            series = {k: v for k, v in series.items() if not k.startswith("excess_over_blank_")}
        elif plant == "P8":
            rec["blank"] = "P8 blank"
        elif self.has_blank():
            m = self.inputs["runs"][run]["machine"] if self.two_blanks else "returned"
            rec["blank"] = f"blank {m}"
        rec["series"] = {**series, **self.exports(role)}
        if role == "restart":
            rec["checkpoint"] = {"time_s": self.horizon / 2.0, "step_index": 600, "event_index": 0,
                                 "through": "snapshot files"}  # fmt: skip
        if role == "plant":
            rec["judged_as"] = run
            rec["host_patch"] = dict(V0_PATCH) if plant == "P9" else None
            self.plant_change(rec, plant, run)
        return rec

    def plant_change(self, rec, plant, run):
        """A planted run that differs from the honest one as the reference predicts."""
        for readout in spec.plant_readouts(plant):
            ents = [e for e in self.doc["plants"] if e["plant"] == plant and e["run"] == run
                    and e["quantity"] == readout]  # fmt: skip
            if not ents or readout not in rec["series"]:
                continue
            e = max(ents, key=lambda x: abs(x["planted"] - x["honest"]))
            ref = self.doc["runs"][run]["series"].get(readout)
            if ref is None:
                fate = readout[len("excess_over_blank_") :]
                ref_vals = self.doc["runs"][run]["excess_over_blank"][fate]["value"]
            else:
                ref_vals = ref["value"]
            shape = _shape(ref_vals, self.times, e["time_s"])
            rec["series"][readout] = rec["series"][readout] + (e["planted"] - e["honest"]) * shape

    def all_records(self):
        recs = []
        honest = [r for r in self.inputs["runs"] if r != "blank"]
        for dt in spec.PRIMARY_RUNGS:
            for r in honest:
                recs.append(self.record(r, "honest", dt))
            if self.has_blank():
                recs.append(self.record("blank", "blank", dt))
                if self.two_blanks:
                    recs.append(self.record("blank", "blank", dt, machine="held"))
            for r in honest if self.profile == "B" else ["p_sched returned"]:
                if r in honest:
                    recs.append(self.record(r, "twin", dt))
        if "p_sched returned" in honest and self.role in (None, "AN"):
            recs.append(self.record("p_sched returned", "restart", 0.5))
        allowed = shapes.PLANT_NAMES[self.role] if self.role else tuple(shapes.JUDGED_AS)
        for plant in sorted({e["plant"] for e in self.doc["plants"]}):
            if plant in shapes.JUDGE_PLANTS:
                continue
            for run in sorted({e["run"] for e in self.doc["plants"] if e["plant"] == plant}):
                if self.plant_name(plant, run) in allowed:
                    recs.append(self.record(run, "plant", 0.5, plant=plant))
            if plant == "P8":
                recs.append(self.record("blank", "plant", 0.5, plant="P8"))
        return recs

    def retry_records(self, runs):
        recs = []
        for dt in spec.RETRY_RUNGS:
            for r in runs:
                recs.append(self.record(r, "honest", dt, attempt="retry"))
            if self.has_blank():
                recs.append(self.record("blank", "blank", dt, attempt="retry"))
            for r in runs:
                if self.profile == "B" or r == "p_sched returned":
                    recs.append(self.record(r, "twin", dt, attempt="retry"))
        return recs

    def entry(self, rec):
        """An entry as the tables write it: a refused one has exactly four keys (item 5)."""
        if rec["status"] == "refused":
            return {"refused": True, "refusal": rec["refusal"], "definition": rec["definition"],
                    "record": rec["record"]}  # fmt: skip
        out = {"t": rec["times_s"], "readouts": {
                   k: [float(x) for x in v] for k, v in rec["series"].items()
                   if not k.startswith("excess_over_blank_")},
               "own_ledgers_at_end": rec["own"], "source": rec["source"]}  # fmt: skip
        for k in ("blank", "checks", "definition", "dt_s", "record", "record_sha256", "route2",
                  "steps", "survival", "checkpoint", "host_patch"):  # fmt: skip
            if k in rec:
                out[k] = rec[k]
        ex = {k[len("excess_over_blank_") :]: [float(x) for x in v]
              for k, v in rec["series"].items() if k.startswith("excess_over_blank_")}  # fmt: skip
        if ex:
            out["excess_over_blank"] = ex
        if rec["role"] == "plant":
            out["judged_as"] = rec["judged_as"]
        return out

    def write(self, folder, recs=None, extra_tweaks=()):
        recs = [copy.deepcopy(r) for r in (self.base() if recs is None else recs)]
        kept = []
        for rec in recs:
            drop = False
            for pred, fn in list(self.tweaks) + list(extra_tweaks):
                if pred(rec):
                    if fn is None:
                        drop = True
                        break
                    fn(rec)
            if not drop:
                kept.append(rec)
        for attempt, sub in (("primary", "table"), ("retry", "table-retry")):
            rs = [r for r in kept if r["attempt"] == attempt]
            if not rs and attempt == "retry":
                continue
            table = {"kind": "cells.fr38_v2.engine_table@1", "family": self.family,
                     "window_s": list(self.window), "samples_s": self.samples, "missing": [],
                     "rungs": {}, "plants": {}}  # fmt: skip
            for r in rs:
                dt = float(r["dt_s"])
                rung = table["rungs"].setdefault(repr(dt), {"dt_s": dt, "runs": {}})
                e = self.entry(r)
                for pred, fn in self.entry_tweaks:
                    if pred(r):
                        fn(e)
                if r["role"] == "restart":
                    table["restart"] = e
                elif r["role"] == "plant":
                    table["plants"][r["name"]] = e
                else:
                    rung["runs"][r["name"]] = e
            for fn in self.table_tweaks:
                fn(table, attempt)
            d = os.path.join(folder, sub)
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, f"table_{self.family}.json"), "w") as fh:
                fh.write(json.dumps(table))  # the C encoder: json.dump streams in Python
            write_sums(d)
        return folder


def is_(run=None, role=None, dt=None, plant=None, attempt=None, machine=None):
    def pred(rec):
        return (
            (run is None or rec["run"] == run)
            and (role is None or rec["role"] == role)
            and (dt is None or rec["dt_s"] == dt)
            and (plant is None or rec["plant"] == plant)
            and (attempt is None or rec["attempt"] == attempt)
            and (machine is None or rec["machine"] == machine)
        )

    return pred


def write_refs(folder, doc):
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, f"reference_{doc['family']}.json"), "w") as fh:
        fh.write(json.dumps(doc))
    return folder


def run_judge(tmp_path, docs, synths, name="x", roles=None):
    """docs: reference documents; synths: their engine writers. Returns the verdict. The documents
    are read once each time they are the same objects."""
    fams = {d["family"]: s.profile for d, s in zip(docs, synths, strict=True)}
    refs, key = str(tmp_path / f"refs_{name}"), tuple(map(id, docs))
    if key not in _REFERENCES:
        for d in docs:
            write_refs(refs, d)
        _REFERENCES[key] = (docs, J.read_references(refs, fams, synths[0].mapping))
    export = str(tmp_path / f"export_{name}")
    for s in synths:
        s.write(export, getattr(s, "records_override", None))
    return J.judge(refs, export, families=fams, roles=roles, references=_REFERENCES[key][1])


def verdict_of(v, family, run):
    return v["families"][family]["runs"][run]["verdict"]


def plant_status(v, plant):
    return v["plants"][plant]["status"]


# ------------------------------------------------------------------ C0 on the references


def test_reader_accepts_the_invented_file_first(invented, mapping, tmp_path):
    refs = write_refs(str(tmp_path / "r"), invented)
    v = J.judge(refs, None, families={"invented": "A"})
    c0 = v["c0"]["references"]["invented"]
    assert c0["accepted"], c0["faults"][:5]
    assert v["c0"]["read_order"][0] == "invented"


def _mutations(doc):
    """(name, mutate(doc) or None for a text mutation) — each must refuse the file."""
    t1 = doc["inputs"]["window_s"][0]
    i1 = doc["times_s"].index(t1)

    def set_series(run, name, key, i, val):
        def f(d):
            d["runs"][run]["series"][name][key][i] = val

        return f

    def class_flip(d):
        s = d["runs"]["p_sched returned"]["series"]["label_R_win"]
        s["class"][i1 + 1], s["value"][i1 + 1], s["accuracy"][i1 + 1] = "constant", 0.0, None

    def stepped_where_constant(d):
        s = d["runs"]["p_sched returned"]["series"]["label_R_win"]
        s["class"][1], s["accuracy"][1] = "stepped", 0.0

    def drop_time(d):
        d["times_s"] = d["times_s"][:-1]

    def drop_series_time(d):
        s = d["runs"]["p_sched returned"]["series"]["n_R"]
        for k in ("class", "value", "accuracy"):
            s[k] = s[k][:-1]

    def acc_over(d):
        s = d["runs"]["p_sched returned"]["series"]["n_R"]
        s["accuracy"][5] = 1e-10 * s["scale"]

    def scale_off(d):
        d["runs"]["p_sched returned"]["series"]["n_R"]["scale"] *= 1.001

    def route2_off(d):
        e = d["runs"]["p_sched returned"]["route2"][0]
        e["value"] *= 1.001

    def ratio_off(d):
        d["runs"]["p_sched returned"]["survival"][0]["ratio"] *= 1.001

    def idle_ratio_zero(d):
        for e in d["runs"]["p=0 returned"]["survival"]:
            if e["fate"] == "durable":
                e["ratio"] = 0.0

    def excess_constant(d):
        s = d["runs"]["p=0 returned"]["excess_over_blank"]["durable"]
        s["class"][0], s["accuracy"][0] = "constant", None

    def plant_key(d):
        del d["plants"][0]["honest"]

    return [
        ("kind", lambda d: d.update(kind="cells.fr38_v2.reference@0")),
        ("units", lambda d: d["units"].update(copy_fmol=1.66e-9)),
        ("missing output time", drop_time),
        ("missing output time in a series", drop_series_time),
        ("missing run", lambda d: d["runs"].pop("p=1 returned")),
        ("missing readout", lambda d: d["runs"]["p_sched held"]["series"].pop("H_deg_R")),
        ("missing excess", lambda d: d["runs"]["p_sched held"].pop("excess_over_blank")),
        (
            "missing cohort_net",
            lambda d: d["runs"]["p_sched held"]["not_compared"].pop("cohort_net_durable"),
        ),
        ("class: constant where SPEC makes it stepped", class_flip),
        ("class: stepped where SPEC makes it constant", stepped_where_constant),
        ("negative zero constant", set_series("p_sched returned", "label_R_win", "value", 0, -0.0)),
        (
            "constant with an accuracy",
            set_series("p_sched returned", "label_R_win", "accuracy", 0, 0.0),
        ),
        ("spread", set_series("p_sched returned", "n_R", "class", 3, "spread")),
        ("unknown class", set_series("p_sched returned", "n_R", "class", 3, "exact")),
        ("accuracy beyond 1e-11 s_y", acc_over),
        ("scale not READOUTS §3's", scale_off),
        ("route2 value is not the win class", route2_off),
        ("survival ratio", ratio_off),
        ("idle survival ratio 0", idle_ratio_zero),
        ("excess never constant", excess_constant),
        ("plant entry key", plant_key),
        ("safety factor", lambda d: d["method"].update(safety_factor=1.5)),
        ("run-time sidecar", lambda d: d["method"].update(run_time_s=12.0)),
        ("provenance flag", lambda d: d["provenance"].update(sha256_of_this_file_excluded=False)),
        ("provenance key", lambda d: d["provenance"].pop("writer_version")),
        ("samples", lambda d: d.update(samples_s=d["samples_s"][:-1])),
        (
            "no plant entry of a core plant",
            lambda d: d.update(plants=[e for e in d["plants"] if e["plant"] != "P6"]),
        ),
        (
            "window",
            lambda d: d["inputs"].update(
                window_s=[d["inputs"]["window_s"][0] + 10.0, d["inputs"]["window_s"][1]]
            ),
        ),
    ]


def test_reader_refuses_each_fault(invented, mapping, tmp_path):
    for i, (name, mutate) in enumerate(_mutations(invented)):
        d = copy.deepcopy(invented)
        mutate(d)
        path = str(tmp_path / f"m{i}.json")
        with open(path, "w") as fh:
            fh.write(json.dumps(d))
        ref = records.read_reference(path, "invented", "A", mapping)
        assert not ref.accepted, name
    # a non-finite token, and a file the reader cannot parse
    raw = _invented_bytes().decode()
    path = str(tmp_path / "nan.json")
    with open(path, "w") as fh:
        fh.write(raw.replace('"alive_t2":0.0', '"alive_t2":NaN', 1))
    assert not records.read_reference(path, "invented", "A", mapping).accepted
    # a reported entry's stated scale that departs from READOUTS.md §3 is recorded, not refused
    # (amendment 4, item 1); a judged entry's is refused (the "scale" row above)
    d = copy.deepcopy(invented)
    d["runs"]["p_sched returned"]["series"]["C_tx_1"]["scale"] *= 1.001
    path = str(tmp_path / "reported_scale.json")
    with open(path, "w") as fh:
        fh.write(json.dumps(d))
    ref = records.read_reference(path, "invented", "A", mapping)
    assert ref.accepted and any("C_tx_1" in n and "recorded" in n for n in ref.notes)
    # an unknown key is ignored, not a fault (amendment 2, Q6)
    d = copy.deepcopy(invented)
    d["runs"]["p_sched returned"]["extra_key"] = 1
    d["plants"][0]["extra"] = "x"
    path = str(tmp_path / "extra.json")
    with open(path, "w") as fh:
        fh.write(json.dumps(d))
    assert records.read_reference(path, "invented", "A", mapping).accepted


def test_first_read_refused_stops_the_judge(invented, mapping, tmp_path):
    d = copy.deepcopy(invented)
    d["units"]["energy"] = "kJ"
    s = Synth(invented, "A", mapping)
    v = run_judge(tmp_path, [d], [s])
    assert "refused" in v and "families" not in v


def test_spec_echo_check_against_spec_inputs():
    """The echo check compares SPEC.md's transcription: a value 10⁻⁹ off is a fault, 10⁻¹⁴ not."""
    for fam in spec.REAL_FAMILIES:
        exp = spec.spec_inputs(fam)
        assert records.compare_inputs(exp, copy.deepcopy(exp)) == []
        got = copy.deepcopy(exp)
        got["tau_s"] = exp["tau_s"] * (1 + 1e-9)
        assert records.compare_inputs(exp, got)
        got["tau_s"] = exp["tau_s"] * (1 + 1e-14)
        assert records.compare_inputs(exp, got) == []
        got2 = copy.deepcopy(exp)
        got2["runs"].pop(next(iter(got2["runs"])))
        assert records.compare_inputs(exp, got2)
    # SPEC.md's literals and amendment 1's quotients, as the spec states their doubles
    an = spec.spec_inputs("AN")
    assert an["mu_res_RT"] == -10.368889000000001 and an["k_d_per_s"] == 0.00011111111111111112
    assert spec.spec_inputs("AF")["mu_res_RT"] == 8.599269797012601
    assert spec.spec_inputs("C")["store"]["forward_per_s_at_c0"] == 0.0003333333333333333
    assert spec.spec_inputs("B")["k_s_per_s"] == 0.0009090909090909091
    assert spec.RT_J == 2578.730581020227 and spec.COPY_FMOL == 1.6605390671738468e-09


# ------------------------------------------------------------------ the honest invented run


@pytest.fixture(scope="module")
def honest(invented, mapping, tmp_path_factory):
    tmp = tmp_path_factory.mktemp("honest")
    s = Synth(invented, "A", mapping)
    s.two_blanks = True
    return run_judge(tmp, [invented], [s])


def test_honest_invented_engine_passes(honest):
    v = honest
    fam = v["families"]["invented"]
    bad = {
        r: x["primary"].get("why", x["primary"].get("refused"))
        for r, x in fam["runs"].items()
        if x["verdict"] != "pass"
    }
    assert not bad, bad
    assert not v["c0"]["engine"]["refused_records"], v["c0"]["engine"]["refused_records"][:2]
    for p in ("P1", "P1′", "P1″", "P2", "P3a", "P3b", "P4", "P5", "P6", "P7"):
        assert plant_status(v, p) == "caught", (p, v["plants"][p]["must_catch"])
    assert v["comparison"]["invented"] == "pass"
    # the orders: amounts at 3 in window [2.5, 3.5]; labels at 2 in [1.5, 3.5]
    items = {
        i["readout"]: i
        for i in fam["runs"]["p_sched returned"]["primary"]["readouts"]
        if "C2" in i and i.get("readout") and "ts_s" not in i
    }
    assert items["n_R"]["C2"]["p"] == 3 and items["label_R_win"]["C2"]["p"] == 2
    assert abs(items["n_R"]["C2"]["q"] - 3.0) < 1e-3 and items["n_R"]["C2"]["resolved"]
    assert items["C_tx_1"]["status"] == "reported"


# ------------------------------------------------------------------ C1, C4 and the equalities


def _perturbed(invented, mapping, tmp_path, tweaks, name, two_blanks=False):
    s = Synth(invented, "A", mapping)
    s.two_blanks = two_blanks
    s.tweaks = tweaks
    return run_judge(tmp_path, [invented], [s], name=name)


def test_negative_zero_at_a_constant_fails(invented, mapping, tmp_path):
    def f(rec):
        rec["series"]["label_R_win"] = rec["series"]["label_R_win"].copy()
        rec["series"]["label_R_win"][0] = -0.0

    v = _perturbed(invented, mapping, tmp_path, [(is_("p_sched returned", "honest", 1.0), f)], "nz")
    assert verdict_of(v, "invented", "p_sched returned") == "fail"


def test_twin_restart_and_two_blank_mismatches_fail(invented, mapping, tmp_path):
    def bump(name):
        def f(rec):
            rec["series"][name] = rec["series"][name] * (1 + 1e-15) + 1e-30

        return f

    v = _perturbed(
        invented, mapping, tmp_path, [(is_("p_sched returned", "twin", 2.0), bump("n_N"))], "twin"
    )
    run = v["families"]["invented"]["runs"]["p_sched returned"]["primary"]
    assert run["verdict"] == "fail" and run["equalities"]["twin@2.0"]["fails"]
    v = _perturbed(
        invented,
        mapping,
        tmp_path,
        [(is_("p_sched returned", "restart"), bump("label_R_win"))],
        "restart",
    )
    run = v["families"]["invented"]["runs"]["p_sched returned"]["primary"]
    assert run["verdict"] == "fail" and run["equalities"]["restart"]["fails"]

    # the restart compares every record, labels and released_present_gross included (amendment 4,
    # item 7, CRITERIA.md §2): a difference there alone fails
    v = _perturbed(
        invented,
        mapping,
        tmp_path,
        [(is_("p_sched returned", "restart"), bump("released_present_gross_durable"))],
        "restart_gross",
    )
    run = v["families"]["invented"]["runs"]["p_sched returned"]["primary"]
    assert run["verdict"] == "fail" and run["equalities"]["restart"]["fails"]

    def check(rec):
        rec["checks"] = dict(rec["checks"], G_identity_largest_pJ=2.0e-20)

    # a labelled run may carry label-only checks: the twin's checks need only be a subset of its
    # labelled run's, bit for bit; the restart's equal the uninterrupted run's whole
    def label_check(rec):
        rec["checks"] = dict(rec["checks"], label_only_check=1.0e-19)

    v = _perturbed(
        invented,
        mapping,
        tmp_path,
        [(lambda r: r["run"] == "p_sched returned" and r["role"] in ("honest", "restart"),
          label_check)],
        "twin_subset",
    )  # fmt: skip
    assert verdict_of(v, "invented", "p_sched returned") == "pass"
    # the twin compares the excess over the blank and the engine's checks too (item 7)
    for name, f in (("twin_checks", check), ("twin_excess", bump("excess_over_blank_short_lived"))):
        v = _perturbed(
            invented, mapping, tmp_path, [(is_("p_sched returned", "twin", 0.5), f)], name
        )
        run = v["families"]["invented"]["runs"]["p_sched returned"]["primary"]
        assert run["verdict"] == "fail" and run["equalities"]["twin@0.5"]["fails"], name
    v = _perturbed(
        invented,
        mapping,
        tmp_path,
        [(is_("blank", "blank", 0.5, machine="held"), bump("n_M"))],
        "blanks",
        two_blanks=True,
    )
    run = v["families"]["invented"]["runs"]["blank held"]["primary"]
    assert run["verdict"] == "fail" and run["equalities"]["two_blanks@0.5"]["fails"]


def test_identities_fail(invented, mapping, tmp_path):
    def membership(rec):
        rec["series"]["label_R_resyn"] = rec["series"]["label_R_resyn"] + 1e-15

    def hold(rec):
        rec["series"]["int_Q_tx"] = rec["series"]["int_Q_tx"] * (1 + 1e-9)

    def g(rec):
        rec["series"]["G_minus_G0"] = rec["series"]["G_minus_G0"] + 1e-6 * np.linspace(0, 1, 61)

    for name, f, ident in (
        ("membership", membership, "membership_sum_R"),
        ("hold", hold, "hold"),
        ("G", g, "G"),
    ):
        v = _perturbed(invented, mapping, tmp_path, [(is_("p_sched held", "honest", 2.0), f)], name)
        run = v["families"]["invented"]["runs"]["p_sched held"]["primary"]
        assert run["verdict"] == "fail", name
        assert any(r["identity"] == ident and r["fails"] for r in run["identities"]["2.0"]), name


# ------------------------------------------------------------------ C2 and C3


def _add(name, fn):
    """Add fn(dt, ref_series) to one series of p_sched held's honest records."""

    def f(rec):
        rec["series"][name] = rec["series"][name] + fn(rec["dt_s"], rec)

    return (is_("p_sched held", "honest"), f)


def _dev(rec, name):
    v = np.asarray(rec["series"][name])
    return (v - v[0]) / np.max(np.abs(v - v[0]))


def test_c2_and_c3_modes(invented, mapping, tmp_path):
    s_n = max(abs(x) for x in invented["runs"]["p_sched held"]["series"]["n_N"]["value"])
    # a C2 miss with the order in its window fails: third order plus an offset
    v = _perturbed(
        invented,
        mapping,
        tmp_path,
        [_add("n_N", lambda dt, r: 1e-6 * s_n * (dt**3 + 1.0) * _dev(r, "n_N"))],
        "miss_in",
    )
    assert verdict_of(v, "invented", "p_sched held") == "fail"
    # a C2 miss with the order unresolved fails: every rung the same, off the reference
    ref_n = np.asarray(invented["runs"]["p_sched held"]["series"]["n_N"]["value"])

    def flat(rec):
        rec["series"]["n_N"] = ref_n + 1e-9 * s_n * (ref_n - ref_n[0]) / np.max(
            np.abs(ref_n - ref_n[0])
        )

    v = _perturbed(
        invented, mapping, tmp_path, [(is_("p_sched held", "honest"), flat)], "miss_unres"
    )
    run = v["families"]["invented"]["runs"]["p_sched held"]["primary"]
    item = next(i for i in run["readouts"] if i.get("readout") == "n_N")
    assert run["verdict"] == "fail" and not item["C2"]["resolved"]
    # second order where 3 is declared, inside C2's band: inconclusive, without a miss
    v = _perturbed(
        invented,
        mapping,
        tmp_path,
        [_add("n_N", lambda dt, r: 1e-5 * s_n * dt**2 * _dev(r, "n_N"))],
        "out_nomiss",
    )
    run = v["families"]["invented"]["runs"]["p_sched held"]
    item = next(i for i in run["primary"]["readouts"] if i.get("readout") == "n_N")
    assert run["verdict"] == "inconclusive" and item["C2"]["passes"]
    assert item["C2"]["order_in_window"] is False and run.get("retry_pending")
    # second order with a miss: still inconclusive, not failed (CRITERIA.md §4)
    v = _perturbed(
        invented,
        mapping,
        tmp_path,
        [_add("n_N", lambda dt, r: 1e-5 * s_n * (dt**2 + 1.0) * _dev(r, "n_N"))],
        "out_miss",
    )
    run = v["families"]["invented"]["runs"]["p_sched held"]
    item = next(i for i in run["primary"]["readouts"] if i.get("readout") == "n_N")
    assert run["verdict"] == "inconclusive" and not item["C2"]["passes"]

    # a reported readout's miss changes nothing: complexes moved between stages 3 and 4, which
    # keeps the machines' identities
    def stages(rec):
        d = 1e-3 * _dev(rec, "C_tx_3") * float(np.max(np.abs(rec["series"]["C_tx_3"])))
        rec["series"]["C_tx_3"] = rec["series"]["C_tx_3"] + d
        rec["series"]["C_tx_4"] = rec["series"]["C_tx_4"] - d

    v = _perturbed(
        invented, mapping, tmp_path, [(is_("p_sched held", "honest"), stages)], "reported"
    )
    run = v["families"]["invented"]["runs"]["p_sched held"]["primary"]
    item = next(i for i in run["readouts"] if i.get("readout") == "C_tx_3")
    assert run["verdict"] == "pass" and not item["C2"]["passes"]


def test_retry(invented, mapping, tmp_path):
    s_n = max(abs(x) for x in invented["runs"]["p_sched held"]["series"]["n_N"]["value"])
    second = _add("n_N", lambda dt, r: 1e-5 * s_n * dt**2 * _dev(r, "n_N"))
    for name, retry_fn, expect in (
        ("pass", None, "pass"),
        ("fail", lambda dt, r: 1e-6 * s_n * (dt**3 + 1.0) * _dev(r, "n_N"), "fail"),
        ("inconclusive", lambda dt, r: 1e-5 * s_n * dt**2 * _dev(r, "n_N"), "inconclusive"),
    ):
        s = Synth(invented, "A", mapping)
        prim = [r for r in s.all_records()]
        retry = s.retry_records(["p_sched held"])
        s.tweaks = [(lambda rec: second[0](rec) and rec["attempt"] == "primary", second[1])]
        if retry_fn is not None:
            s.tweaks.append(
                (
                    lambda rec: rec["attempt"] == "retry" and rec["role"] == "honest",
                    _add("n_N", retry_fn)[1],
                )
            )
        s.records_override = prim + retry
        s.table_tweaks = [lambda t, attempt: attempt == "retry" and t.update(
            plants={"P5": {}}, restart={})]  # fmt: skip
        v = run_judge(tmp_path, [invented], [s], name=f"retry_{name}")
        notes = v["c0"]["engine"]["notes"]
        assert any("a retry's is ignored" in n for n in notes)
        assert any("invented retry: restart: only AN's" in n for n in notes)
        run = v["families"]["invented"]["runs"]["p_sched held"]
        assert run["primary"]["verdict"] == "inconclusive", name
        assert run["retry"]["rungs_s"] == [1.0, 0.5, 0.25] and run["verdict"] == expect, name


def refuse(rec):
    rec["status"], rec["refusal"] = "refused", "domain: y_f above X_DOM (invented)"


def test_refused_runs(invented, mapping, tmp_path):
    v = _perturbed(
        invented, mapping, tmp_path, [(is_("p=0 returned", "honest", 1.0), refuse)], "eng_refused"
    )
    assert verdict_of(v, "invented", "p=0 returned") == "refused"
    assert v["families"]["invented"]["verdict"] == "inconclusive"
    assert v["comparison"]["invented"] == "inconclusive"
    engine = v["c0"]["engine"]
    assert [r["entry"] for r in engine["engine_refusals"]] == ["rungs.1.0.runs.p=0 returned"]
    assert any("the checker's to confirm" in f for f in engine["flags_for_the_checker"])

    # a run whose declaration is 10⁻⁹ off is refused by C0, and a missing rung's run is too
    def off(rec):
        release(rec)["dwell_s"] *= 1 + 1e-9

    v = _perturbed(
        invented, mapping, tmp_path, [(is_("p=0 returned", "honest", 0.5), off)], "c0_definition"
    )
    assert verdict_of(v, "invented", "p=0 returned") == "refused"

    # an entry presenting itself as one of the judge's own plants (P1′ here) is excluded and
    # recorded, not refused (amendment 4, item 5); P5's own record is then missing
    def judge_plant(rec):
        rec["name"] = "P1′"

    v = _perturbed(
        invented, mapping, tmp_path, [(is_(role="plant", plant="P5"), judge_plant)], "c0_p1p"
    )
    assert not v["c0"]["engine"]["refused_records"]
    assert any("formed by the judge itself" in n for n in v["c0"]["engine"]["notes"])
    assert plant_status(v, "P5") == "refused" and plant_status(v, "P1′") == "caught"
    # an unknown run name is recorded and ignored; the export's step count is flagged only
    s = Synth(invented, "A", mapping)
    recs = s.all_records()
    extra = copy.deepcopy(next(r for r in recs if is_("p=1 returned", "honest")(r)))
    extra["name"] = "p=1 returned copy"
    next(r for r in recs if is_("p=1 returned", "honest", 1.0)(r))["steps"] = 7
    s.records_override = recs + [extra]
    v = run_judge(tmp_path, [invented], [s], name="unknown")
    assert verdict_of(v, "invented", "p=1 returned") == "pass"
    assert any("not a registered run name" in n for n in v["c0"]["engine"]["notes"])
    assert any(".steps: 7" in f for f in v["c0"]["engine"]["flags_for_the_checker"])
    s.records_override = [r for r in recs if not is_("p=1 returned", "honest", 2.0)(r)]
    v = run_judge(tmp_path, [invented], [s], name="gap")
    assert verdict_of(v, "invented", "p=1 returned") == "refused"


def test_a_refused_run_lists_its_failing_entries(invented, mapping, tmp_path):
    """CRITERIA.md §4: a run with a refused rung, twin or blank is scored refused. What C0 accepts
    of it is judged all the same, and a failing entry is listed beside the refusal, not hidden."""

    def negzero(rec):
        rec["series"]["label_R_win"] = rec["series"]["label_R_win"].copy()
        rec["series"]["label_R_win"][0] = -0.0

    bad = (is_("p_sched returned", "honest", 2.0), negzero)
    for name, gone in (
        ("twin", (is_("p_sched returned", "twin", 1.0), refuse)),
        ("blank", (is_("blank", "blank", 0.5), refuse)),
        ("rung", (is_("p_sched returned", "honest", 0.5), refuse)),
    ):
        v = _perturbed(invented, mapping, tmp_path, [gone], f"alone_{name}")
        assert verdict_of(v, "invented", "p_sched returned") == "refused", name
        assert v["refused_with_failing_entries"] == [], name
        v = _perturbed(invented, mapping, tmp_path, [bad, gone], f"both_{name}")
        assert verdict_of(v, "invented", "p_sched returned") == "refused", name
        listed = [x for x in v["refused_with_failing_entries"] if "p_sched returned (" in x]
        assert any("C1: label_R_win" in x for x in listed), (name, listed)
    # where the rungs are not all there, the plants on that run are unscorable
    assert plant_status(v, "P4") == "refused"


# ------------------------------------------------------------------ the tables (amendment 5)


@pytest.fixture(scope="module")
def read_once(invented, mapping, tmp_path_factory):
    refs = write_refs(str(tmp_path_factory.mktemp("refs")), invented)
    return J.read_references(refs, {"invented": "A"}, mapping)


def c0_of(read_once, mapping, folder):
    """C0 on an invented export, without the judgement."""
    refs, _ = read_once
    tables = records.read_tables(folder, ["invented"], sample=shapes.sample_hashes(SHAPES))
    fams = {"invented": J.Family("invented", "A", refs["invented"])}
    index, report = J.index_records(tables, fams, mapping, SHAPES)
    return tables, report


def faults_of(report, where):
    return [x for r in report["refused_records"] if r["entry"] == where for x in r["faults"]]


def test_structure_pass_reads_the_invented_tables(registered):
    """The judgement's own structure pass on tables with every key the README lists, lists
    backwards: no finding at all, and every entry read."""
    for fam, s in registered.synths.items():
        path = os.path.join(registered.export, "table", f"table_{fam}.json")
        doc, _ = records.load_lenient(path)
        tab = {"doc": doc, "family": fam, "attempt": "primary"}
        st = records.table_structure(
            tab, s.profile, s.role, s.inputs, "p_sched returned" if s.role == "AN" else None, SHAPES
        )
        found = st.findings + [f for e in st.entries for f in e.findings + e.definition_findings]
        assert found == [] and st.notes == [] and st.present == len(st.entries), (fam, found[:3])


# Each fault on its own entry of one export: (predicate, change to the entry as written, where the
# refused entry sits, what its fault names)
def _entry_faults():
    def drop(key):
        return lambda e: e.pop(key)

    def put(value, *path):
        def f(e):
            for k in path[:-1]:
                e = e[k]
            e[path[-1]] = value

        return f

    def nan(e):
        e["readouts"]["n_M"][3] = float("nan")

    def late(e):
        e["survival"][0]["ts_s"] = 451.0

    def labelled(e):
        e["readouts"]["label_R_win"] = [0.0] * len(e["t"])

    def own_labels(e):
        e["definition"]["model"]["operators"].append(
            {"law": "neutral_arrival_labels@1", "species": []}
        )

    def constant_p(e):
        rec = {"definition": e["definition"]}
        release(rec)["durable_fraction"] = 0.0
        e["definition"]["experiment"]["polymerisation_controls"].remove(control(rec, "tx_release"))

    def transcribes(e):
        control({"definition": e["definition"]}, "tx")["schedule"][0]["value"] = 50000.0

    alive = {"fate": "durable", "t2_s": 300.0, "ts_s": 450.0, "alive_t2": 0.0, "alive_ts": 0.0,
             "ratio": None}  # fmt: skip
    h = "honest"
    return [
        (is_("p=0 returned", h, 2.0), drop("own_ledgers_at_end"), "own_ledgers_at_end: missing"),
        (is_("p=0 returned", h, 1.0), put(600.0, "steps"), "steps: type: integer expected"),
        (is_("p=0 returned", h, 0.5), put(None, "blank"), "blank: type: string expected"),
        (is_("p=1 returned", h, 2.0), put("abc", "record_sha256"), "64 hexadecimal digits"),
        (is_("p=1 returned", h, 1.0), lambda e: e["source"].pop("snapshot"),
         "source.snapshot: missing"),
        (is_("p=1 returned", h, 0.5), put(True, "source", "checkout_dirty"), "checkout was dirty"),
        (is_("p_sched held", h, 2.0), put(None, "route2", 0, "grid_error"),
         "route2[0].grid_error: type: float expected"),
        (is_("p_sched held", h, 1.0), lambda e: e["route2"].pop(), "route2: missing (durable"),
        (is_("p_sched held", h, 0.5), lambda e: e["route2"].append(dict(e["route2"][0])),
         "is duplicated"),
        (is_("p_sched returned", h, 2.0), late, "no registered fate, t2 and later sample"),
        (is_("p_sched returned", h, 1.0), lambda e: e["checks"].pop("exported_cell"),
         "checks.exported_cell: missing"),
        (is_("p_sched returned", h, 0.5), nan, "readouts.n_M[3]: type: float expected"),
        (is_("p_sched returned", "twin", 2.0), put([alive], "survival"), "a twin is unlabelled"),
        (is_("p_sched returned", "twin", 1.0), labelled, "a twin is unlabelled"),
        (is_("p_sched returned", "twin", 0.5), own_labels, "the operators"),
        (is_("blank", "blank", 2.0), constant_p, "durable_fraction: p:"),
        (is_("blank", "blank", 1.0), transcribes, "k_I:"),
        (is_("blank", "blank", 0.5), lambda e: (e.pop("route2"), e.pop("survival")), None),
        (is_(role="restart"), put(7200.0, "checkpoint", "time_s"), "checkpoint.time_s: 7200.0"),
        (is_(plant="P2"), put(dict(V0_PATCH), "host_patch"), "host_patch: type: null expected"),
        (is_(plant="P3a"), put("p_sched held", "judged_as"), "judged_as: type"),
        (is_(plant="P3b"), lambda e: e["t"].pop(), "output grid"),
        (is_(plant="P4"), put(1.0, "dt_s"), "dt_s: 1.0 is not its step"),
        (is_(plant="P5"), put(1, "extra_key"), None),
        (is_(plant="P7"), lambda e: e["survival"].pop(), "survival: missing (durable"),
    ]  # fmt: skip


def _more_entry_faults():
    def twice(key):
        return lambda e: e[key].append(dict(e[key][0]))

    h = "honest"
    return [
        (is_("p=0 returned", h, 2.0), lambda e: e["readouts"].pop("H_deg_R_s"),
         "readouts.H_deg_R_s: missing readout"),
        (is_("p=0 returned", h, 1.0), lambda e: e.pop("record_sha256"), "record_sha256: missing"),
        (is_("p=0 returned", h, 0.5), lambda e: e["readouts"]["n_M"].append(0.0), "n_M has 62"),
        (is_("p=1 returned", h, 2.0), lambda e: e["route2"][0].update(fate="x"),
         "no registered fate and sample time"),
        (is_("p=1 returned", h, 1.0), lambda e: e.pop("survival"), "survival: missing"),
        (is_("p=1 returned", h, 0.5), lambda e: e.update(refused=False), "true expected"),
        (is_("p_sched held", h, 2.0), lambda e: e["excess_over_blank"].pop("durable"),
         "excess_over_blank.durable: missing"),
        (is_("p_sched held", h, 1.0), lambda e: e["excess_over_blank"]["durable"].pop(),
         "excess_over_blank_durable has 60"),
        (is_("p_sched held", h, 0.5), lambda e: e.update(record=None), "record: type"),
        (is_("p_sched returned", h, 2.0), lambda e: e.update(definition=[]), "definition: type"),
        (is_("p_sched returned", h, 1.0), lambda e: e.update(steps=True),
         "integer expected, boolean found"),
        (is_("p_sched returned", h, 0.5), lambda e: e["t"].__setitem__(1, "x"), "t[1]: type"),
        (is_("p_sched returned", "twin", 2.0), lambda e: e["route2"].pop(), "route2: missing ("),
        (is_("p_sched returned", "twin", 1.0), lambda e: e["source"].update(engine_revision=3),
         "source.engine_revision: type"),
        (is_("p_sched returned", "twin", 0.5), lambda e: e.pop("excess_over_blank"),
         "excess_over_blank: missing"),
        (is_(role="restart"), twice("survival"), "is duplicated"),
        (is_(plant="P2"), lambda e: e.pop("judged_as"), "judged_as: missing"),
        (is_(plant="P3a"), twice("route2"), "is duplicated"),
        (is_(plant="P5"), lambda e: e.update(blank="blank returned"), "blank: type: null expected"),
    ]  # fmt: skip


def test_c0_names_each_entry_fault(invented, mapping, read_once, tmp_path):
    """Amendment 5, §2 to §4: a missing or mistyped pinned key, an incomplete or doubled route-2 or
    survival list, a dirty checkout, a wrong checkpoint, `judged_as` or patch: each refuses its own
    entry and names it by path. An extra key, and a blank without its lists, refuse nothing."""
    for tag, rows in (("entries", _entry_faults()), ("more", _more_entry_faults())):
        s = Synth(invented, "A", mapping)
        s.entry_tweaks = [(pred, change) for pred, change, _ in rows]
        _, report = c0_of(read_once, mapping, s.write(str(tmp_path / tag)))
        for pred, _, needle in rows:
            rec = next(r for r in s.base() if pred(r))
            where = {"restart": "restart", "plant": f"plants.{rec['name']}"}.get(
                rec["role"], f"rungs.{float(rec['dt_s'])!r}.runs.{rec['name']}"
            )
            faults = faults_of(report, where)
            if needle is None:
                assert faults == [], (where, faults)
            else:
                assert any(needle in x for x in faults), (where, needle, faults[:3])
        assert tag == "more" or any("extra_key" in m for m in report["extra_keys"])
    # a null plant is a missing record, unscorable; a table's other plants are still read
    s = Synth(invented, "A", mapping)
    s.table_tweaks = [lambda t, attempt: t["plants"].update(P7=None)]
    v = run_judge(tmp_path, [invented], [s], name="null_plant")
    assert plant_status(v, "P7") == "refused" and plant_status(v, "P5") == "caught"
    assert any("null, a missing record" in n for n in v["c0"]["engine"]["notes"])


def _declaration_faults():
    def model(e):
        return e["definition"]["model"]

    def rec(e):
        return {"definition": e["definition"]}

    def tx(e):
        return named(_gene(e["definition"])["chains"], "tx")

    def arrivals(e):
        return e["definition"]["experiment"]["label_arrivals"]

    def patch(e):
        return model(e)["membranes"][0]

    def labels(e):
        return operator(e["definition"], "neutral_arrival_labels@1")["species"][0]["labels"]

    def unnamed(e):  # malformed: no set of names can hold it
        model(e)["operators"].append({"law": []})

    runs = [(r, "honest", d) for r in ("p=0 returned", "p=1 returned", "p_sched held",
                                       "p_sched returned") for d in (2.0, 1.0, 0.5)]  # fmt: skip
    runs += [("p_sched returned", "twin", 1.0), ("p_sched returned", "twin", 0.5),
             ("blank", "blank", 0.5), ("p_sched returned", "restart", 0.5)]  # fmt: skip
    changes = [
        (lambda e: model(e)["extracellular"][0].update(volume_pL=2.0), "the bath's volume"),
        (lambda e: patch(e).update(area_m2=2e-10), "the patch's area"),
        (lambda e: patch(e)["permeability_m_per_s"].update(M=1e-12), "permeabilities"),
        (lambda e: named(model(e)["species"], "K").update(valence=2), "K's valence"),
        (lambda e: tx(e).update(residues=1200.0), "the residues"),
        (lambda e: _gene(e["definition"])["transfers"].append({"id": "recharge"}), "no recharging"),
        (lambda e: arrivals(e).append(dict(arrivals(e)[0], species="R_s")), "the label arrivals"),
        (lambda e: arrivals(e)[0]["schedule"][1].update(time=100.0000001), "the label arrivals"),
        (lambda e: labels(e).remove("pre"), "labels"),
        (lambda e: model(e)["operators"].append({"law": "scheduled_compartment_wash@1"}),
         "the operators"),
        (lambda e: (control(rec(e), "tx")["schedule"].append({"time": 50.0, "value": 50000.0}),
                    unnamed(e)), "k_I"),
        (lambda e: (release(rec(e)).update(fates=[{"durable": "R_s", "short_lived": "R"}]),
                    unnamed(e)), "the fates"),
        (lambda e: (_gene(e["definition"]).update(law="templated_polymerisation@2"),
                    e["definition"].update(experiment=None)), "the operators"),
        (lambda e: model(e)["operators"].append(copy.deepcopy(_gene(e["definition"]))),
         "the operators"),
        (lambda e: model(e).update(moieties=[{"id": []}]), "the moieties"),
        (lambda e: model(e).update(species="x"), "K's valence"),
    ]  # fmt: skip
    pairs = zip(runs, changes, strict=True)
    return [(is_(r, role, d), f, what) for (r, role, d), (f, what) in pairs]


def test_c0_names_each_declaration_fault(invented, mapping, read_once, tmp_path):
    """Items 6 and 7: the located inputs, integers as integers, the label arrivals, the operators
    and routes by name. Keys no SPEC.md or §5.1 value covers are recorded, never refused."""
    s = Synth(invented, "A", mapping)
    rows = _declaration_faults()

    def uncovered(e):
        e["definition"]["execution"]["backend"] = 7
        e["definition"]["execution"].pop("jit")

    def monomers(e):
        named(_gene(e["definition"])["degradations"], "deg_R")["monomers"]["M"] = 3

    s.entry_tweaks = [(p, f) for p, f, _ in rows] + [
        (is_("blank", "blank", 2.0), uncovered),
        (is_("blank", "blank", 1.0), monomers),
        (is_("p_sched returned", "twin", 2.0), uncovered),
    ]
    tables, report = c0_of(read_once, mapping, s.write(str(tmp_path / "declarations")))
    for pred, _, what in rows:
        rec = next(r for r in s.base() if pred(r))
        at = f"rungs.{float(rec['dt_s'])!r}.runs.{rec['name']}"
        at = "restart" if rec["role"] == "restart" else at
        assert any(what in x for x in faults_of(report, at)), (at, what)
    assert len(report["refused_records"]) >= len(rows)
    for where in ("rungs.2.0.runs.blank returned", "rungs.1.0.runs.blank returned",
                  "rungs.2.0.runs.p_sched returned unlabelled"):  # fmt: skip
        assert faults_of(report, where) == [], where
    flags = report["flags_for_the_checker"]
    # a malformed declaration is refused, and what is compared with it is not: nothing crashes
    assert any("P5: unhashable" in x for x in faults_of(report, "plants.P5"))
    assert any("rungs.1.0.runs.blank returned" in f and "not compared: unhashable" in f
               for f in flags)  # fmt: skip
    assert any("monomers" in f and "the sheet reads" in f for f in flags)
    assert any("beside its run's: execution/backend" in f for f in flags)
    assert any(".execution.backend: type" in m for m in report["definition_shape"])
    assert any(".execution.jit: missing" in m for m in report["definition_shape"])


def test_flags_and_records_refuse_nothing(invented, mapping, tmp_path):
    """Item 4 and item 5: recorded and flagged to the checker, never judged."""
    s = Synth(invented, "A", mapping)
    s.entry_tweaks = [
        (is_("p=0 returned", "honest", 2.0), lambda e: e.update(blank="blank held")),
        (is_("p=0 returned", "honest", 1.0), lambda e: e["route2"][0].update(k_per_s=1.0)),
        (is_("p=1 returned", "honest", 2.0), lambda e: e["source"].update(snapshot="another")),
        (is_("p=1 returned", "honest", 1.0),
         lambda e: e["source"].update(snapshot_patch_sha256="0" * 64)),
        (is_("p_sched returned", "twin", 2.0), lambda e: e["readouts"].update(
            H_total=[1.0] * len(e["t"]))),
        (is_("blank", "blank", 2.0), lambda e: e["route2"][0].update(grid_error="x")),
    ]  # fmt: skip
    v = run_judge(tmp_path, [invented], [s], name="flags")
    assert v["comparison"]["invented"] == "pass"
    flags = v["c0"]["engine"]["flags_for_the_checker"]
    for needle in (
        "blank: 'blank held'",
        "k_per_s 1.0 is not the declared",
        "differ in source.snapshot",
        "not an empty file's",
        "twin@2.0: an export that is never judged differs: H_total",
    ):
        assert any(needle in f for f in flags), (needle, flags)
    assert any("route2[0].grid_error: blank list" in m for m in v["c0"]["engine"]["extra_keys"])


def test_index_and_table_hash(invented, mapping, read_once, tmp_path):
    """Amendment 5, §2, §4 (a) and §6: a missing SHA256SUMS is flagged; a departing, unlisted or
    malformed line's table, a missing top-level key, a repeated key, a wrong kind, window or rung,
    and the format sample's own table are refused; a listed table that is gone is a fault."""
    s = Synth(invented, "A", mapping)
    base = s.write(str(tmp_path / "base"))
    sums = os.path.join("table", "SHA256SUMS")
    name = os.path.join("table", "table_invented.json")

    def case(tag, edit=None, tweak=None):
        folder = str(tmp_path / tag)
        if tweak is not None:
            t = Synth(invented, "A", mapping)
            t._base = s.base()
            t.table_tweaks = [tweak]
            t.write(folder)
        else:
            shutil.copytree(base, folder)
        if edit is not None:
            edit(folder)
        return c0_of(read_once, mapping, folder)

    def rewrite(fn, text):
        def f(folder):
            with open(os.path.join(folder, fn), "w") as fh:
                fh.write(text(open(os.path.join(base, fn)).read()))

        return f

    refs = write_refs(str(tmp_path / "refs_idx"), invented)
    gone = str(tmp_path / "noindex")
    shutil.copytree(base, gone)
    os.remove(os.path.join(gone, sums))
    v = J.judge(refs, gone, families={"invented": "A"})
    assert v["comparison"]["invented"] == "pass"
    assert any("SHA256SUMS is missing" in f for f in v["c0"]["engine"]["flags_for_the_checker"])
    assert not v["c0"]["engine"]["index"]["table"]["SHA256SUMS"]
    stray = "0" * 64 + "  table_AN.json\n"
    one_space = lambda x: x.replace("  ", " ")  # noqa: E731
    twice = lambda x: x + "0" * 64 + "  table_invented.json\n"  # noqa: E731

    def dup_key(x):
        return x.replace('"plants": {', '"plants": {"P5": null, ', 1)

    for tag, kw, needle in (
        ("departs", {"edit": rewrite(name, lambda x: x + " ")}, "departs from"),
        ("unlisted", {"edit": rewrite(sums, lambda x: stray)}, "is not listed"),
        ("malformed", {"edit": rewrite(sums, one_space)}, "is not listed"),
        ("twice", {"edit": rewrite(sums, twice)}, "is not listed"),
        ("repeated", {"edit": lambda f: (rewrite(name, dup_key)(f), write_sums(
            os.path.join(f, "table")))}, "a key is repeated"),
        ("no plants", {"tweak": lambda t, a: t.pop("plants")}, "plants: missing"),
        ("kind", {"tweak": lambda t, a: t.update(kind="x")}, "kind: type"),
        ("window", {"tweak": lambda t, a: t.update(window_s=[100.0, 310.0])}, "window_s"),
        ("samples", {"tweak": lambda t, a: t.update(samples_s="x")}, "samples_s: type"),
        ("rung", {"tweak": lambda t, a: t["rungs"]["2.0"].update(dt_s=1.0)}, "rungs.2.0.dt_s"),
        ("restart", {"tweak": lambda t, a: t.update(restart=[])}, "restart: type"),
    ):  # fmt: skip
        tables, report = case(tag, **kw)
        (tab,) = tables["tables"]
        assert any(needle in x for x in tab["faults"]), (tag, tab["faults"])
        assert all(r["faults"] for r in report["refused_records"])
        assert len(report["refused_records"]) == report["entries"], tag
    tables, _ = case("listed", edit=lambda f: open(os.path.join(f, sums), "a").write(stray))
    assert any("missing from the folder" in x for x in tables["faults"])
    # §6: a table whose hash is one of the sample's is refused in judgement
    real = shapes.sample_hashes
    with open(os.path.join(base, name), "rb") as fh:
        digest = hashlib.sha256(fh.read()).hexdigest()
    try:
        shapes.sample_hashes = lambda s=None: {"table/table_AN.json": digest}
        v = J.judge(refs, base, families={"invented": "A"})
    finally:
        shapes.sample_hashes = real
    assert verdict_of(v, "invented", "p_sched returned") == "refused"
    assert any("format sample" in x for t in v["c0"]["engine"]["tables"] for x in t["faults"])


def test_route2_and_survival(invented, mapping, tmp_path):
    def r2(rec):
        for e in rec["route2"]:
            if e["fate"] == "short_lived" and e["ts_s"] == rec["times_s"][-1] - 30.0:
                e["value"] *= 1.01

    v = _perturbed(
        invented, mapping, tmp_path, [(is_("p_sched returned", "honest", 0.5), r2)], "r2"
    )
    run = v["families"]["invented"]["runs"]["p_sched returned"]["primary"]
    assert run["verdict"] == "fail" and any("route2_short_lived" in w for w in run["why"])
    for bad in (0.0, float("nan"), float("inf")):

        def ratio(rec, bad=bad):
            for e in rec["survival"]:
                if e["fate"] == "durable":
                    e["ratio"] = bad

        v = _perturbed(
            invented,
            mapping,
            tmp_path,
            [(is_("p=0 returned", "honest", 2.0), ratio)],
            f"ratio_{bad}",
        )
        run = v["families"]["invented"]["runs"]["p=0 returned"]["primary"]
        assert run["verdict"] == "fail", bad
        assert any(w.startswith("C1: survival_durable") for w in run["why"]), bad
    # at an active fate a ratio of None fails, and a NaN or infinite one is refused (amendment 4)
    for bad, expect in ((None, "fail"), (float("nan"), "refused"), (float("inf"), "refused")):

        def active(rec, bad=bad):
            for e in rec["survival"]:
                if e["fate"] == "short_lived":
                    e["ratio"] = bad

        v = _perturbed(
            invented, mapping, tmp_path, [(is_("p=0 returned", "honest", 0.5), active)],
            f"active_{bad}",
        )  # fmt: skip
        assert verdict_of(v, "invented", "p=0 returned") == expect, bad
    # the grid error: no estimate where the window holds no output to drop
    t = [0.0, 10.0, 20.0, 30.0]
    assert rules.grid_error(t, [0.0, 1.0, 2.0, 3.0], 0.01, 10.0, 20.0, 30.0) is None
    assert rules.grid_error(t, [0.0, 1.0, 2.5, 3.0], 0.01, 0.0, 20.0, 30.0) is not None
    out = {
        "readouts": [
            {
                "readout": "route2_durable",
                "ts_s": 30.0,
                "refused": "x",
                "refused_kind": "resolution",
            }
        ],
        "equalities": {},
        "identities": {},
    }
    assert J.run_verdict(out) == "inconclusive"
    # route 2's coarse grid counts even indices from the grid's first output, t1, t2 and ts kept
    # (amendment 4, item 7): with t1 on an odd index it is not every second output from t1
    tt = [float(x) for x in range(0, 11)]
    A = [0.0, 0.0, 0.3, 0.9, 1.4, 2.6, 2.9, 3.5, 4.4, 4.6, 4.6]
    g = rules.grid_error(tt, A, 0.05, 1.0, 9.0, 10.0)
    fine = list(range(1, 10))
    even = [1, 2, 4, 6, 8, 9]
    want = abs(rules.known_rate(tt, A, 0.05, 1.0, 9.0, 10.0, fine)
               - rules.known_rate(tt, A, 0.05, 1.0, 9.0, 10.0, even))  # fmt: skip
    from_t1 = abs(rules.known_rate(tt, A, 0.05, 1.0, 9.0, 10.0, fine)
                  - rules.known_rate(tt, A, 0.05, 1.0, 9.0, 10.0, [1, 3, 5, 7, 9]))  # fmt: skip
    assert g == want and g != from_t1
    # the known-rate and net-rate forms agree at a constant rate (LAWS.md §6)
    tt = [float(x) for x in range(0, 101, 10)]
    A = [0.0, 1.0, 1.5, 3.0, 3.2, 4.0, 4.0, 4.1, 4.1, 4.1, 4.1]
    n = [1.0 + 0.1 * i for i in range(11)]
    k = 0.02
    D = [0.0]
    for i in range(10):
        D.append(D[-1] + k * 0.5 * (n[i] + n[i + 1]) * 10.0)
    a = rules.known_rate(tt, A, k, 10.0, 60.0, 90.0)
    b = rules.net_rate_cohort(tt, A, D, n, 10.0, 60.0, 90.0)
    assert abs(a - b) <= 1e-14 * abs(a)


# ------------------------------------------------------------------ the plants


def test_plants_not_caught(invented, mapping, tmp_path):
    # world-data plants identical to the honest run are not caught
    def same(rec):
        honest = Synth(invented, "A", mapping).record(rec["run"], "honest", 0.5)
        rec["series"] = honest["series"]

    for p in ("P2", "P3a", "P3b", "P4", "P5", "P7"):
        v = _perturbed(invented, mapping, tmp_path, [(is_(role="plant", plant=p), same)], f"nc_{p}")
        assert plant_status(v, p) == "not caught", p
        assert v["comparison"]["invented"] == "fail", p

    # a planted run the engine refuses by its own books is caught
    def refuse(rec):
        rec["status"], rec["refusal"] = "refused", "its own books (invented)"

    v = _perturbed(invented, mapping, tmp_path, [(is_(role="plant", plant="P5"), refuse)], "p5ref")
    assert plant_status(v, "P5") == "caught"

    # §8.5: P9 declares no change, and P5's change is k_s × (1 + 10⁻⁴) exactly; anything else in a
    # plant's declaration refuses it, and the plant is unscorable, not caught
    def p5_factor(rec):
        for c in rec["definition"]["experiment"]["polymerisation_controls"]:
            if c["route_id"] == "deg_R_s":
                c["schedule"][0]["value"] *= 1.0 + 1e-6

    v = _perturbed(invented, mapping, tmp_path, [(is_(role="plant", plant="P5"), p5_factor)],
                   "p5def")  # fmt: skip
    faults = [x for r in v["c0"]["engine"]["refused_records"] for x in r["faults"]]
    assert plant_status(v, "P5") == "refused" and any(
        "its registered change at" in x for x in faults)  # fmt: skip

    # the registered change made at another key too is not the registered change
    def also_k_d(rec):
        step = control(rec, "deg_R")["schedule"][0]
        step["value"] = step["value"] * (1 + 1e-4)

    v = _perturbed(invented, mapping, tmp_path, [(is_(role="plant", plant="P5"), also_k_d)], "p5kd")
    faults = [x for r in v["c0"]["engine"]["refused_records"] for x in r["faults"]]
    assert plant_status(v, "P5") == "refused"
    assert any("not its registered change" in x for x in faults)

    # a judge-side refusal is not a catch: a plant whose definition carries an unregistered change
    def wrong(rec):
        release(rec)["dwell_s"] = 61.0

    v = _perturbed(invented, mapping, tmp_path, [(is_(role="plant", plant="P3a"), wrong)], "p3ref")
    assert plant_status(v, "P3a") == "refused" and v["comparison"]["invented"] != "pass"


def test_judge_side_plants_not_caught(invented, mapping, tmp_path):
    # P1: the engine's win class is the net tracker itself, so the confusion is invisible
    def net(rec):
        for fate, row in (("durable", "R"), ("short_lived", "R_s")):
            cn = np.asarray(invented["runs"][rec["run"]]["not_compared"][f"cohort_net_{fate}"])
            old = rec["series"][f"label_{row}_win"]
            rec["series"][f"label_{row}_win"] = cn.copy()
            rec["series"][f"label_{row}_resyn"] = rec["series"][f"label_{row}_resyn"] + (old - cn)

    v = _perturbed(
        invented,
        mapping,
        tmp_path,
        [(lambda r: r["role"] == "honest" and r["run"] != "blank", net)],
        "p1nc",
    )
    assert plant_status(v, "P1") == "not caught"

    # P1″: the engine's excess at an idle fate is +0.0
    def zero(rec):
        rec["series"]["excess_over_blank_durable"] = np.zeros(len(rec["times_s"]))

    v = _perturbed(invented, mapping, tmp_path, [(is_("p=0 returned", "honest"), zero)], "p1ppnc")
    assert plant_status(v, "P1″") == "not caught"

    # P1′: a net loss counter at the gross rate makes the net-rate form the known-rate form
    def gross(rec):
        t = rec["times_s"]
        for fate, row in (("durable", "R"), ("short_lived", "R_s")):
            k = spec.fate_rate(invented["inputs"], fate)
            n = rec["series"][f"n_{row}"]
            D = [0.0]
            for i in range(len(t) - 1):
                D.append(D[-1] + k * 0.5 * (n[i] + n[i + 1]) * (t[i + 1] - t[i]))
            rec["series"][f"int_D_{row}"] = np.asarray(D)

    v = _perturbed(invented, mapping, tmp_path, [(lambda r: r["role"] == "honest", gross)], "p1pnc")
    assert plant_status(v, "P1′") == "not caught"
    # P6, by the sizing rule: an honest G whose tolerance exceeds the plant's distance
    ent = max(
        (e for e in invented["plants"] if e["plant"] == "P6"),
        key=lambda e: abs(e["planted"] - e["honest"]),
    )
    d_e = abs(ent["planted"] - ent["honest"])
    H = np.asarray(invented["runs"]["p_sched returned"]["series"]["H_tx_release"]["value"])
    dg = -spec.RT_KJ * spec.residue_potential(invented["inputs"]) * 1200 * (H - H[0])
    shape = dg / abs(dg[invented["times_s"].index(ent["time_s"])])

    def big(rec):
        extra = 3.0 * d_e * rec["dt_s"] ** 3 * shape
        rec["series"]["G_minus_G0"] = rec["series"]["G_minus_G0"] + extra
        rec["series"]["H_tx"] = rec["series"]["H_tx"] - extra

    v = _perturbed(invented, mapping, tmp_path, [(is_("p_sched returned"), big)], "p6nc")
    assert verdict_of(v, "invented", "p_sched returned") == "pass"
    unit = v["plants"]["P6"]["units"][0]["items"][0]
    assert unit["C2_fails"] and not unit["sized"] and plant_status(v, "P6") == "not caught"


# ------------------------------------------------------------------ profiles B, C and D


def _smooth(times, a, tau):
    t = np.asarray(times)
    return a * (1.0 - np.exp(-t / tau))


def _add_series(doc, run, name, values, acc=1e-26):
    doc["runs"][run]["series"][name] = {
        "class": ["stepped"] * len(values),
        "value": [float(x) for x in values],
        "accuracy": [0.0] + [acc] * (len(values) - 1),
        "scale": 0.0,
    }


def _rescale(doc, profile, mapping):
    """Recompute every stated scale with READOUTS.md §3's rules, for a derived invented file."""
    blank = doc["runs"].get("blank")
    for name, run in doc["runs"].items():
        vals = {k: np.asarray(s["value"]) for k, s in run["series"].items()}
        bvals = (
            None
            if blank is None
            else {k: np.asarray(s["value"]) for k, s in blank["series"].items()}
        )
        ctx = rules.ScaleContext(
            profile, doc["inputs"], vals, blank=name == "blank", blank_values=bvals
        )
        for e in mapping["readouts"]:
            if e["status"].get(profile) is None:
                continue
            kind, _, rn = e["reference"].partition("/")
            if kind == "series" and rn in run["series"]:
                run["series"][rn]["scale"] = ctx.scale(e["scale"], rn)
            elif kind == "excess_over_blank" and "excess_over_blank" in run:
                run["excess_over_blank"][rn]["scale"] = ctx.scale(e["scale"], rn)
            elif kind == "route2" and "route2" in run:
                for x in run["route2"]:
                    if x["fate"] == rn and x["class"] == "stepped":
                        x["scale"] = ctx.scale(e["scale"], rn)


def _plant_entries(doc, plant, run, readouts, t_e, rel=1e-3):
    i = doc["times_s"].index(t_e)
    for q in readouts:
        if q.startswith("excess_over_blank_"):
            s = doc["runs"][run]["excess_over_blank"][q[len("excess_over_blank_") :]]
        else:
            s = doc["runs"][run]["series"][q]
        h = s["value"][i]
        doc["plants"].append(
            {
                "plant": plant,
                "run": run,
                "quantity": q,
                "time_s": t_e,
                "honest": h,
                "planted": h * (1 + rel) if h else rel * s["scale"],
                "relative_distance": rel,
                "scale": s["scale"],
            }
        )


def derive_c(doc, mapping):
    d = copy.deepcopy(doc)
    d["family"] = "invented_C"
    d["inputs"]["store"] = {
        "Mx_initial_mM": 1e-6,
        "Mx_moieties": {"nucleoside": 1, "phosphorus": 1},
        "forward_per_s_at_c0": 0.01,
        "mu0_Mx_RT_at_1M": 0.0,
        "multiplier": 1.0,
        "network_c0_mM": 1.0,
        "network_mu0_RT_at_c0": {"M": math.log(1e-3), "Mx": math.log(1e-3)},
    }
    for run in d["runs"]:
        t = d["times_s"]
        _add_series(d, run, "n_Mx", 1e-6 + _smooth(t, 4e-3, 150.0))
        hs = _smooth(t, 1e-4, 150.0)
        _add_series(d, run, "H_store", hs)
        g = d["runs"][run]["series"]["G_minus_G0"]
        g["value"] = [float(x - y) for x, y in zip(g["value"], hs, strict=True)]
    _rescale(d, "C", mapping)
    d["plants"] = []
    _plant_entries(d, "P8", "p_sched returned", spec.plant_readouts("P8"), 300.0)
    return d


def derive_d(doc, mapping):
    d = copy.deepcopy(doc)
    d["family"] = "invented_D"
    d["inputs"]["water"] = {
        "L_p_m_per_Pa_s": 1e-14,
        "V_max_pL": 3.0,
        "V_min_pL": 0.5,
        "V_ref_pL": 1.0,
        "availability": 1.0,
        "bulk_modulus_Pa": 0.0,
        "impermeant_fmol": 0.0,
        "pressure_offset_Pa": 0.0,
        "bath_pressure_Pa": 0.0,
    }
    for run in d["runs"]:
        t = d["times_s"]
        _add_series(d, run, "V", 1.0 + _smooth(t, 0.05, 200.0))
        hw, wb = _smooth(t, 2e-3, 200.0), _smooth(t, -1e-3, 200.0)
        _add_series(d, run, "H_water", hw)
        _add_series(d, run, "W_bath", wb)
        g = d["runs"][run]["series"]["G_minus_G0"]
        g["value"] = [float(x - a + b) for x, a, b in zip(g["value"], hw, wb, strict=True)]
    _rescale(d, "D", mapping)
    d["plants"] = []
    _plant_entries(d, "P9", "p_sched returned", spec.plant_readouts("P9"), 300.0, rel=1e-2)
    return d


def derive_b(doc, mapping, family="invented_B"):
    """Arm B's shape with B's run names, on the invented file's two p_sched runs."""
    d = copy.deepcopy(doc)
    d["family"] = family
    names = {"p_sched returned": "p=0.55 returned", "p_sched held": "p=0.55 held"}
    d["runs"] = {names[k]: v for k, v in d["runs"].items() if k in names}
    d["inputs"]["runs"] = {names[k]: v for k, v in d["inputs"]["runs"].items() if k in names}
    for e in d["plants"]:
        e["run"] = names.get(e["run"], e["run"])
    d["inputs"]["p_sched"] = [[0.0, 0.55]]
    for r in d["inputs"]["runs"].values():
        r["p"] = [[0.0, 0.55]]
    d["inputs"]["moieties"]["adenine"] = {"ATP": 1, "ADP": 1}
    d["inputs"]["moieties"]["amino_acid"] = {"A": 1, "P": 400}
    d["inputs"]["moieties"]["phosphorus"].update(ATP=3, ADP=2)
    d["inputs"]["M_rib_copies"] = 1000
    # arm B's own vocabulary (SPEC.md §2 with the sheet's §5.1 names), so that profile B's
    # declaration keys are read: translation's chains, the ribosomes, deg_P and their controls
    d["inputs"].update(
        {
            "L_P_aa": 400,
            "m_tl": 8,
            "v_tl_aa_per_s": 16.0,
            "K_A_tl_mM": 0.02,
            "K_ATP_tl_mM": 0.02,
            "k_I_tl_per_mM_s": 120.0,
            "k_P_per_s": 5e-4,
            "K_ATP_rc_mM": 0.1,
            "K_M_rc_mM": 0.1,
            "V_C_mM_per_s": 0.01,
            "P_on_fmol_per_s": 2e-6,
            "k_X_per_s": 2e-3,
            "t_off_s": 300.0,
            "K_X_mM": 1e-3,
            "n_X": 2,
            "b_X": 0.02,
        }
    )
    V = float(d["inputs"]["volume_pL"])
    for r, n in d["inputs"]["initial_copies"].items():
        d["inputs"]["initial_mM"][r] = float(n) * COPY / V
    d["inputs"]["initial_mM"].update({"X": 1e-3, "A": 2.0, "ATP": 5.0, "ADP": 0.5, "P": 1e-12})
    d["inputs"]["mu_res_P_RT"] = 5.0
    d["inputs"]["mu0_RT_at_1M"].update({"A": 0.0, "ATP": 12.0, "ADP": 0.0, "P": 2000.0})
    t = d["times_s"]
    m_rib = 1000 * spec.COPY_FMOL
    for run, r in d["runs"].items():
        r.pop("excess_over_blank", None)
        for row, a in (("X", 1e-3), ("A", 2.0), ("ATP", 5.0), ("ADP", 0.5), ("P", 1e-12)):
            _add_series(d, run, f"n_{row}", a + _smooth(t, 0.01 * a + 1e-9, 100.0 + len(row)))
        ctot = 0.0
        for ch in ("tl", "tl_s"):
            cs = 0.0
            for j in range(1, 9):
                c = _smooth(t, 1e-8 * j, 50.0 + j)
                _add_series(d, run, f"C_{ch}_{j}", c)
                cs = cs + c
            _add_series(d, run, f"E_{ch}", cs)
            _add_series(d, run, f"W_{ch}", 50.0 * cs)
            for n in ("int_J_I", "int_S", "int_Q"):
                _add_series(d, run, f"{n}_{ch}", _smooth(t, 1e-6, 300.0))
            ctot = ctot + cs
        _add_series(d, run, "F_rib", m_rib - ctot)
        for n in ("int_D_P", "int_J_C"):
            _add_series(d, run, n, _smooth(t, 1e-7, 300.0))
        hx = 0.0
        for n in ("H_tl", "H_deg_P", "H_rc"):
            h = _smooth(t, 1e-3, 250.0)
            _add_series(d, run, n, h)
            hx = hx + h
        g = r["series"]["G_minus_G0"]
        g["value"] = [float(x - y) for x, y in zip(g["value"], hx, strict=True)]
    _rescale(d, "B", mapping)
    d["plants"] = [e for e in d["plants"] if e["plant"] == "P4" and e["run"] in d["runs"]]
    return d


def test_profile_c_store_and_p8(invented, mapping, tmp_path):
    dc = derive_c(invented, mapping)
    ref = records.read_reference(
        write_refs(str(tmp_path / "rc"), dc) + "/reference_invented_C.json",
        "invented_C",
        "C",
        mapping,
    )
    assert ref.accepted, ref.faults[:3]
    v = run_judge(
        tmp_path,
        [invented, dc],
        [Synth(invented, "A", mapping), Synth(dc, "C", mapping)],
        name="c_ok",
    )
    assert v["families"]["invented_C"]["verdict"] == "pass", v["families"]["invented_C"]
    assert plant_status(v, "P8") == "caught" and v["plants"]["P8"]["negative_control_passes"]
    assert v["comparison"]["invented_C"] == "pass"
    # the negative control fails when a class that does not read M moves
    s = Synth(dc, "C", mapping)

    def pool0(rec):
        rec["series"]["label_R_pool0"] = rec["series"]["label_R_pool0"] * (1 - 1e-3)

    s.tweaks = [(is_(role="plant", plant="P8", run="p_sched returned"), pool0)]
    v = run_judge(tmp_path, [invented, dc], [Synth(invented, "A", mapping), s], name="c_nc")
    assert plant_status(v, "P8") == "caught" and not v["plants"]["P8"]["negative_control_passes"]
    # P8 not caught: the planted run is the honest one
    s = Synth(dc, "C", mapping)

    def same(rec):
        rec["series"] = Synth(dc, "C", mapping).record(
            rec["run"], "honest" if rec["run"] != "blank" else "blank", 0.5
        )["series"]

    s.tweaks = [(is_(role="plant", plant="P8"), same)]
    v = run_judge(tmp_path, [invented, dc], [Synth(invented, "A", mapping), s], name="c_miss")
    assert plant_status(v, "P8") == "not caught" and v["comparison"]["invented_C"] == "fail"
    # the store's heat enters G's identity
    s = Synth(dc, "C", mapping)

    def heat(rec):
        rec["series"]["H_store"] = rec["series"]["H_store"] * 1.001

    s.tweaks = [(is_("p_sched returned", "honest", 1.0), heat)]
    v = run_judge(tmp_path, [invented, dc], [Synth(invented, "A", mapping), s], name="c_g")
    run = v["families"]["invented_C"]["runs"]["p_sched returned"]["primary"]
    assert any(r["identity"] == "G" and r["fails"] for r in run["identities"]["1.0"])


def test_profile_d_energy_identity_and_p9(invented, mapping, tmp_path):
    dd = derive_d(invented, mapping)
    ref = records.read_reference(
        write_refs(str(tmp_path / "rd"), dd) + "/reference_invented_D.json",
        "invented_D",
        "D",
        mapping,
    )
    assert ref.accepted, ref.faults[:3]
    s_g = dd["runs"]["p_sched returned"]["series"]["G_minus_G0"]["scale"]
    shape = np.asarray(dd["times_s"]) / dd["times_s"][-1]

    def with_g(fn):
        s = Synth(dd, "D", mapping)

        def f(rec):
            rec["series"]["G_minus_G0"] = rec["series"]["G_minus_G0"] + fn(rec["dt_s"]) * shape

        s.tweaks = [(lambda r: r["run"] == "p_sched returned" and r["role"] != "plant", f)]
        return s

    def identity(v):
        run = v["families"]["invented_D"]["runs"]["p_sched returned"]
        item = next(i for i in run["primary"]["readouts"] if i["readout"] == "energy_identity_D")
        return run["verdict"], item["C2"]

    # Heun's second order: a residual that shrinks by 4 per halving passes, q = 2
    v = run_judge(
        tmp_path,
        [invented, dd],
        [Synth(invented, "A", mapping), with_g(lambda dt: 1e-8 * s_g * dt**2)],
        name="d2",
    )
    verdict, c = identity(v)
    assert verdict == "pass" and abs(c["q"] - 2.0) < 1e-6 and c["passes"]
    assert v["comparison"]["invented_D"] == "pass" and plant_status(v, "P9") == "caught"
    # an order-one error in the bookings: the rungs agree, the estimate is 0, and it fails
    v = run_judge(
        tmp_path,
        [invented, dd],
        [Synth(invented, "A", mapping), with_g(lambda dt: 1e-8 * s_g)],
        name="d0",
    )
    verdict, c = identity(v)
    assert verdict == "fail" and not c["passes"] and not c["resolved"]
    # a residual that shrinks at first order is inconclusive by C3, window [1.5, 3.5]
    v = run_judge(
        tmp_path,
        [invented, dd],
        [Synth(invented, "A", mapping), with_g(lambda dt: 1e-8 * s_g * dt)],
        name="d1",
    )
    verdict, c = identity(v)
    assert verdict == "inconclusive" and c["window"] == [1.5, 3.5] and c["order_in_window"] is False
    # P9's declaration names no change (its V₀ patch is host-side): any difference refuses it
    s = Synth(dd, "D", mapping)

    def declared(rec):
        release(rec)["dwell_s"] = release(rec)["dwell_s"] * 2.0

    s.tweaks = [(is_(role="plant", plant="P9"), declared)]
    v = run_judge(tmp_path, [invented, dd], [Synth(invented, "A", mapping), s], name="d_decl")
    assert plant_status(v, "P9") == "refused" and v["comparison"]["invented_D"] == "inconclusive"
    # P9 not caught: the planted run reads the volume as the honest one does
    s = Synth(dd, "D", mapping)

    def same(rec):
        rec["series"] = Synth(dd, "D", mapping).record(rec["run"], "honest", 0.5)["series"]

    s.tweaks = [(is_(role="plant", plant="P9"), same)]
    v = run_judge(tmp_path, [invented, dd], [Synth(invented, "A", mapping), s], name="d_miss")
    assert plant_status(v, "P9") == "not caught" and v["comparison"]["invented_D"] == "fail"


def test_profile_b_split_and_p4(invented, mapping, tmp_path):
    db = derive_b(invented, mapping)
    ref = records.read_reference(
        write_refs(str(tmp_path / "rb"), db) + "/reference_invented_B.json",
        "invented_B",
        "B",
        mapping,
    )
    assert ref.accepted, ref.faults[:3]
    v = run_judge(
        tmp_path,
        [invented, db],
        [Synth(invented, "A", mapping), Synth(db, "B", mapping)],
        name="b_ok",
    )
    fam = v["families"]["invented_B"]
    assert fam["verdict"] == "pass", {r: x["primary"].get("why") for r, x in fam["runs"].items()}
    assert set(fam["runs"]) == {"p=0.55 returned", "p=0.55 held"}  # no blank in B
    assert plant_status(v, "P4") == "caught"
    items = {
        i["readout"]: i
        for i in fam["runs"]["p=0.55 held"]["primary"]["readouts"]
        if "ts_s" not in i
    }
    assert items["n_N"]["status"] == "reported" and items["n_R"]["status"] == "judged"
    assert items["n_R"]["C2"]["p"] == 2 and "excess_over_blank_durable" not in items
    # A1's own readouts are reported: a miss there changes nothing; a judged miss fails
    s = Synth(db, "B", mapping)
    s.tweaks = [
        (
            lambda r: r["run"] == "p=0.55 held" and r["dt_s"] == 0.5,
            lambda r: r["series"].update(n_ATP=r["series"]["n_ATP"] * (1 + 1e-6)),
        )
    ]
    v = run_judge(tmp_path, [invented, db], [Synth(invented, "A", mapping), s], name="b_rep")
    assert v["families"]["invented_B"]["runs"]["p=0.55 held"]["verdict"] == "pass"
    # the ribosomes' identity, B's second pool
    s = Synth(db, "B", mapping)
    s.tweaks = [
        (
            is_("p=0.55 held", "honest", 0.5),
            lambda r: r["series"].update(F_rib=r["series"]["F_rib"] * (1 + 1e-9)),
        )
    ]
    v = run_judge(tmp_path, [invented, db], [Synth(invented, "A", mapping), s], name="b_rib")
    run = v["families"]["invented_B"]["runs"]["p=0.55 held"]["primary"]
    assert any(r["identity"] == "machines_rib" and r["fails"] for r in run["identities"]["0.5"])
    # each run of B has its twin
    s = Synth(db, "B", mapping)
    s.tweaks = [
        (
            is_("p=0.55 held", "twin", 1.0),
            lambda r: r["series"].update(n_P=r["series"]["n_P"] * (1 + 1e-15) + 1e-30),
        )
    ]
    v = run_judge(tmp_path, [invented, db], [Synth(invented, "A", mapping), s], name="b_twin")
    assert v["families"]["invented_B"]["runs"]["p=0.55 held"]["verdict"] == "fail"


def test_cli_writes_a_verdict(invented, mapping, tmp_path):
    from validation.gene_regulation.fr38_v2.judge import __main__ as cli

    refs = write_refs(str(tmp_path / "cli_refs"), invented)
    export = Synth(invented, "A", mapping).write(str(tmp_path / "cli_export"))
    out = str(tmp_path / "verdict.json")
    # the CLI judges the registered families; with only the invented file present, the invented
    # family's read is accepted and each registered family's file is missing, so refused
    assert cli.main(["c0", "--references", refs, "--out", out]) == 1
    v = json.load(open(out))
    assert v["c0"]["references"]["invented"]["accepted"]
    assert not v["c0"]["references"]["AN"]["accepted"]
    assert cli.main(["judge", "--engine", export, "--references", refs, "--out", out]) == 0
    v = json.load(open(out))
    assert v["comparison"]["FR-38"] == "inconclusive" and v["comparison"]["invented"] == "pass"


# ------------------------------------------------------------------ the registered branches


def derive_af(doc, mapping):
    """AF's runs: each p with both machine options. The held copies of p = 0 and p = 1 carry the
    hold among the engaged machines (E += H, F −= H)."""
    d = copy.deepcopy(doc)
    d["family"] = "inv_AF"
    for src, dst in (("p=0 returned", "p=0 held"), ("p=1 returned", "p=1 held")):
        run = copy.deepcopy(d["runs"][src])
        H = np.asarray(run["series"]["H_tx_release"]["value"])
        for name, sign in (("F_pol", -1.0), ("E_tx", 1.0)):
            v = np.asarray(run["series"][name]["value"]) + sign * H
            run["series"][name]["value"] = [float(x) for x in v]
        d["runs"][dst] = run
        d["inputs"]["runs"][dst] = {
            "machine": "held",
            "p": copy.deepcopy(d["inputs"]["runs"][src]["p"]),
        }
        d["plants"] += [
            dict(e, run=dst) for e in d["plants"] if e["run"] == src and e["plant"] in ("P1", "P1″")
        ]
    _rescale(d, "A", mapping)
    return d


@pytest.fixture(scope="module")
def registered(invented, mapping, tmp_path_factory):
    """Invented families judged in the registered roles: AN (the invented file), AF, B, C, D."""
    tmp = tmp_path_factory.mktemp("registered")
    docs = {
        "invented": invented,
        "inv_AF": derive_af(invented, mapping),
        "inv_B": derive_b(invented, mapping, "inv_B"),
        "invented_C": derive_c(invented, mapping),
        "invented_D": derive_d(invented, mapping),
    }
    profiles = {"invented": "A", "inv_AF": "A", "inv_B": "B", "invented_C": "C", "invented_D": "D"}
    roles = {"invented": "AN", "inv_AF": "AF", "inv_B": "B", "invented_C": "C", "invented_D": "D"}
    refs = str(tmp / "refs")
    for d in docs.values():
        write_refs(refs, d)
    export = str(tmp / "export")
    synths = {}
    for f, d in docs.items():
        s = Synth(d, profiles[f], mapping, role=roles[f])
        s.two_blanks = roles[f] == "AF"
        s.write(export)
        synths[f] = s
    references = J.read_references(refs, profiles, mapping)
    return types.SimpleNamespace(
        references=references,
        synths=synths,
        refs=refs,
        export=export,
        profiles=profiles,
        roles=roles,
        docs=docs,
        tmp=tmp,
    )


def judge_registered(reg, export=None):
    return J.judge(
        reg.refs,
        export or reg.export,
        families=reg.profiles,
        roles=reg.roles,
        references=reg.references,
    )


def edited(reg, name, pred, fn=None, *, table=None, entry=None, only=None):
    """The registered export with matching records edited, or dropped (fn None), or with their
    entries (`entry`) or their family's table (`table`) changed as written: the tables those
    records sit in are written again, with their index. `only` writes one family's table alone."""
    dst = str(reg.tmp / name)
    if only is None:
        shutil.copytree(reg.export, dst)
    for fam, s in reg.synths.items():
        if fam == only or (only is None and any(pred(r) for r in s.base())):
            s.table_tweaks = [table] if table else []
            s.entry_tweaks = [(pred, entry)] if entry else []
            s.write(dst, extra_tweaks=[] if table or entry else [(pred, fn)])
            s.table_tweaks, s.entry_tweaks = [], []
    return dst


def judge_one(reg, family, name, pred, fn=None, **kw):
    """One family of the registered export judged alone, after an edit."""
    refs, _ = reg.references
    return J.judge(
        reg.refs,
        edited(reg, name, pred, fn, only=family, **kw),
        families={family: reg.profiles[family]},
        roles={family: reg.roles[family]},
        references=({family: refs[family]}, [family]),
    )


def where(family, **kw):
    inner = is_(**kw)
    return lambda rec: rec["family"] == family and inner(rec)


def test_registered_roles_pass(registered):
    v = judge_registered(registered)
    cmp_ = v["comparison"]
    bad = {
        f: {
            r: x["primary"].get("why") or x["primary"].get("refused")
            for r, x in fam["runs"].items()
            if x["verdict"] != "pass"
        }
        for f, fam in v["families"].items()
        if fam["verdict"] != "pass"
    }
    assert not bad, bad
    assert cmp_["arms"] == {"A": "pass", "B": "pass"}, cmp_
    assert cmp_["FR-38"] == "pass" and cmp_["C"] == "pass" and cmp_["D"] == "pass"
    for p in spec.CORE_PLANTS:
        assert plant_status(v, p) == "caught", (p, v["plants"][p]["must_catch"])
    # AF's P1 is reported only; P1″ must be caught at each idle fate of AF and AN
    assert {u["family"] for u in v["plants"]["P1"]["reported_only"]} == {"inv_AF"}
    idle = [g["unit"] for g in v["plants"]["P1″"]["must_catch"] if " idle " in g["unit"]]
    assert len(idle) == 6 and sum(u.startswith("inv_AF") for u in idle) == 4
    # AN's restart and AF's two blanks were judged
    an = v["families"]["invented"]["runs"]["p_sched returned"]["primary"]
    assert "restart" in an["equalities"]
    assert (
        "two_blanks@0.5" in v["families"]["inv_AF"]["runs"]["blank held"]["primary"]["equalities"]
    )
    assert v["provenance"]["mapping_sha256"] and "revision" in v["provenance"]


def test_registered_fail_and_inconclusive(registered):
    def negzero(rec):
        rec["series"]["label_R_win"][0] = -0.0

    v = judge_registered(
        registered,
        edited(
            registered, "armb", where("inv_B", run="p=0.55 held", role="honest", dt=1.0), negzero
        ),
    )
    assert v["comparison"]["arms"]["B"] == "fail" and v["comparison"]["FR-38"] == "fail"
    # an uncaught core plant fails FR-38 with both arms passing
    honest = _honest_h(registered, "inv_AF", "p_sched returned")

    def same(rec):
        rec["series"] = honest["series"]

    v = judge_registered(
        registered, edited(registered, "p5", where("inv_AF", role="plant", plant="P5"), same)
    )
    assert v["comparison"]["arms"] == {"A": "pass", "B": "pass"}
    assert plant_status(v, "P5") == "not caught" and v["comparison"]["FR-38"] == "fail"

    # an unscorable core plant (a declaration C0 refuses) is neither caught nor "not caught": it
    # leaves FR-38 at best inconclusive and never fails it by itself (amendment 4, item 7)
    def unregistered(rec):
        release(rec)["dwell_s"] = release(rec)["dwell_s"] + 1.0

    v = judge_registered(
        registered,
        edited(registered, "p5ref", where("inv_AF", role="plant", plant="P5"), unregistered),
    )
    assert v["comparison"]["arms"] == {"A": "pass", "B": "pass"}
    assert plant_status(v, "P5") == "refused" and v["comparison"]["FR-38"] == "inconclusive"
    # AN's restart is required, and AF's held blank
    v = judge_registered(
        registered, edited(registered, "norestart", where("invented", role="restart"))
    )
    assert verdict_of(v, "invented", "p_sched returned") == "refused"
    assert v["comparison"]["FR-38"] == "inconclusive"
    v = judge_registered(
        registered,
        edited(registered, "noheld", where("inv_AF", role="blank", dt=1.0, machine="held")),
    )
    assert verdict_of(v, "inv_AF", "p_sched held") == "refused"
    assert verdict_of(v, "inv_AF", "blank held") == "refused"
    assert v["comparison"]["FR-38"] == "inconclusive"


def test_registered_af_p1_does_not_decide(registered):
    """AF's P1 is scored and reported: an honest win class whose tolerance exceeds P1's distance
    in AF leaves P1 uncaught there, and FR-38 still passes on AN's catch."""
    docs = registered.docs["inv_AF"]

    def big(rec):
        if rec["run"] == "blank":
            return
        for row in ("R", "R_s"):
            ref = np.asarray(docs["runs"][rec["run"]]["series"][f"label_{row}_win"]["value"])
            scale = docs["runs"][rec["run"]]["series"][f"label_{row}_win"]["scale"]
            dev = ref - ref[0]
            if not np.any(dev):
                continue
            extra = scale * rec["dt_s"] ** 3 * dev / np.max(np.abs(dev))
            w = np.asarray(rec["series"][f"label_{row}_win"]) + extra
            b = np.asarray(rec["series"][f"label_{row}_resyn"]) - extra
            rec["series"][f"label_{row}_win"] = [float(x) for x in w]
            rec["series"][f"label_{row}_resyn"] = [float(x) for x in b]

    v = judge_registered(
        registered,
        edited(
            registered, "afp1", lambda r: r["family"] == "inv_AF" and r["role"] == "honest", big
        ),
    )
    assert v["families"]["inv_AF"]["verdict"] == "pass"
    assert all(u["caught"] is False for u in v["plants"]["P1"]["reported_only"])
    assert plant_status(v, "P1") == "caught" and v["comparison"]["FR-38"] == "pass"


def test_registered_restart_and_patch(registered):
    """Items 5 and 7 and §4 (b) and (c) in the registered roles: AN's restart and its checkpoint,
    P9's patch, and what is ignored and recorded."""
    an = where("invented", role="restart")
    for name, kw in (
        ("null", {"table": lambda t, a: t.update(restart=None)}),
        ("refused", {"fn": refuse}),
        ("late", {"entry": lambda e: e["checkpoint"].update(time_s=301.0)}),
        ("bare", {"entry": lambda e: e.pop("checkpoint")}),
        ("typed", {"entry": lambda e: e["checkpoint"].update(step_index=600.0)}),
    ):
        v = judge_one(registered, "invented", f"re_{name}", an, **kw)
        assert verdict_of(v, "invented", "p_sched returned") == "refused", name
        assert verdict_of(v, "invented", "p_sched held") == "pass", name
        assert v["families"]["invented"]["verdict"] == "inconclusive", name
    # a restart in any other table is ignored and recorded (§4 (b))
    v = judge_one(registered, "inv_AF", "stray", where("inv_AF", run="p=0 held"),
                  table=lambda t, a: t.update(restart={"x": 1}))  # fmt: skip
    assert v["families"]["inv_AF"]["verdict"] == "pass"
    assert any("only AN's primary table has one" in n for n in v["c0"]["engine"]["notes"])
    # P9 without its patch, with another's, or refused (a refused entry names no patch): unscorable
    p9 = where("invented_D", role="plant", plant="P9")
    for name, kw in (
        ("none", {"entry": lambda e: e.update(host_patch=None)}),
        ("other", {"entry": lambda e: e["host_patch"].update(id="V1")}),
        ("operator", {"entry": lambda e: e["host_patch"].update(operator="x")}),
        ("refused", {"fn": refuse}),
    ):
        v = judge_one(registered, "invented_D", f"p9_{name}", p9, **kw)
        assert plant_status(v, "P9") == "refused", name
        assert v["comparison"]["D"] == "inconclusive", name
    # P9's patch is recorded in the verdict
    v = judge_one(registered, "invented_D", "p9_as_is", p9, entry=lambda e: None)
    assert list(v["c0"]["engine"]["host_patches"].values()) == [V0_PATCH]
    assert plant_status(v, "P9") == "caught" and v["comparison"]["D"] == "pass"


def test_c0_names_b_c_and_d_declaration_faults(registered, mapping, tmp_path):
    """Item 6 for arm B's chains, transfer, turnover and coupling, the store and the water. What no
    SPEC.md or §5.1 text states in the declaration's own convention is flagged, not refused."""

    def b(e, name):
        return named(_gene(e["definition"])["chains"], name)

    def op(e, law):
        return operator(e["definition"], law)

    def exp(e, key):
        return e["definition"]["experiment"][key]

    rc = "templated_polymerisation@1"
    turnover, coupling = "scheduled_species_turnover@1", "species_regulated_availability@2"
    store, water = "local_species_reactions@1", "ideal_osmosis_linear_compliance_water@1"
    runs_b = [(f"p=0.55 {m}", r, d) for m in ("held", "returned") for r in ("honest", "twin")
              for d in (2.0, 1.0, 0.5)]  # fmt: skip
    rows_b = [
        (lambda e: b(e, "tl").update(template={"species": "R_s"}), "tl's template"),
        (lambda e: b(e, "tl_s").update(residues=400.0), "tl_s's residues"),
        (lambda e: b(e, "tl").update(release={}), "tl has no release"),
        (lambda e: b(e, "tl")["draws"].update(ATP=2), "tl's draws"),
        (lambda e: op(e, rc)["transfers"][0]["saturation_mM"].update(M=0.2), "recharging's sat"),
        (lambda e: exp(e, "turnover_controls")[1]["schedule"][1].update(time=299.0), "P_X"),
        (lambda e: op(e, coupling)["couplings"][0].update(basal=0.03), "b_X"),
        (lambda e: op(e, coupling).update(states=[{"id": "s"}]), "the coupling's states"),
        (lambda e: op(e, turnover)["routes"].pop(), "the regulator's routes"),
        (lambda e: op(e, rc)["transfers"][0].update(share=3), None),
        (lambda e: op(e, coupling)["couplings"][0]["target"].update(ids=["tl"]), None),
        (lambda e: exp(e, "coupling_controls")[0]["schedule"][0].update(enabled=0), None),
    ]  # fmt: skip
    runs = [("p=0 returned", "honest", d) for d in (2.0, 1.0, 0.5)]
    rows_c = [
        (lambda e: op(e, store)["reactions"][0].update(sites=["cell_0"]), "the store's sites"),
        (lambda e: op(e, store)["reactions"][0].update(factors=[{"x": 1}]), "the store's factors"),
        (lambda e: exp(e, "reaction_controls")[0].update(site="cell_0"), "the store's site"),
    ]  # fmt: skip
    rows_d = [
        (lambda e: op(e, water)["compartments"][0].update(maximum_volume_pL=1.05), "maximum_vol"),
        (lambda e: exp(e, "water_controls")[0]["schedule"][0].update(availability=0.5), "avail"),
        (lambda e: op(e, water)["baths"][0].update(compartment_id="cell_0"), "water's baths"),
    ]  # fmt: skip
    for fam, rows, where_ in (
        ("inv_B", rows_b, runs_b),
        ("invented_C", rows_c, runs),
        ("invented_D", rows_d, runs),
    ):
        s = registered.synths[fam]
        pairs = zip(where_, rows, strict=True)
        s.entry_tweaks = [(is_(r, role, d), f) for (r, role, d), (f, _) in pairs]
        s.write(str(tmp_path / fam))
        s.entry_tweaks = []
        refs, _ = registered.references
        tables = records.read_tables(str(tmp_path / fam), [fam])
        fams = {fam: J.Family(fam, s.profile, refs[fam], role=s.role)}
        _, report = J.index_records(tables, fams, mapping, SHAPES)
        for (run, role, d), (_, what) in zip(where_, rows, strict=True):
            at = f"rungs.{d!r}.runs.{run}" + (" unlabelled" if role == "twin" else "")
            faults = faults_of(report, at)
            if what is None:
                assert faults == [], (at, faults)
            else:
                assert any(what in x for x in faults), (at, what, faults[:2])
        if fam == "inv_B":
            for path in ("share = 3", "target = ", "coupling_controls"):
                assert any(path in f for f in report["flags_for_the_checker"]), path


# ------------------------------------------------------------------ the sample check


@pytest.fixture(scope="module")
def invented_sample(registered, tmp_path_factory):
    """Six invented tables in the sample's own layout, with the registered families' run names."""
    root = tmp_path_factory.mktemp("sample")
    of = {"AN": "invented", "AF": "inv_AF", "B": "inv_B", "C": "invented_C", "D": "invented_D"}
    for sub in ("table", "table-retry"):
        os.makedirs(root / sub)
    for fam, inv in of.items():
        s = registered.synths[inv]
        names = [r for r in spec.spec_inputs(fam)["runs"] if r != "blank"]

        def keep(table, attempt, fam=fam, names=names):
            table["family"] = fam
            for rung in table["rungs"].values():
                for n in list(rung["runs"]):
                    if shapes.classify(n, names) is None:
                        rung["runs"].pop(n)
            if fam == "D" and attempt == "primary":
                e = table["rungs"]["2.0"]["runs"]["p_sched returned unlabelled"]
                table["rungs"]["2.0"]["runs"]["p_sched returned unlabelled"] = {
                    "refused": True, "refusal": "invented", "record": "invented",
                    "definition": e["definition"]}  # fmt: skip

        s.table_tweaks = [keep]
        s.write(str(root / inv), s.base() + (s.retry_records(["p_sched returned"])
                                             if fam == "C" else []))  # fmt: skip
        s.table_tweaks = []
        for sub in ("table", "table-retry"):
            src = root / inv / sub / f"table_{inv}.json"
            if src.exists():
                shutil.copy(src, root / sub / f"table_{fam}.json")
        shutil.rmtree(root / inv)
    for sub in ("table", "table-retry"):
        write_sums(str(root / sub))
    (root / "README.md").write_text("invented")
    return str(root)


def _registered_as(root):
    """The shapes with this invented sample's hashes in place of the registered ones."""
    out = {}
    for d, _, files in os.walk(root):
        for fn in files:
            path = os.path.join(d, fn)
            with open(path, "rb") as fh:
                out[os.path.relpath(path, root)] = hashlib.sha256(fh.read()).hexdigest()
    return dict(SHAPES, sample_sha256=out)


def test_sample_check_on_an_invented_sample(invented_sample, monkeypatch, tmp_path):
    """Amendment 5, §5: the hashes first, then structure only, every kind of entry covered, and any
    missing key, type departure, unlisted law or unread entry named by path."""
    parts = ("entry", "kinds", "checkpoint", "host_patch", "readouts", "definition")
    monkeypatch.setattr(shapes, "schema_from_readme", lambda text: {k: SHAPES[k] for k in parts})
    r = sample.check(invented_sample, _registered_as(invented_sample))
    assert r["passes"], (r["structural_faults"][:4], r["coverage"], r["unexpected_keys"][:3])
    assert r["unexpected_keys"] == [] and r["files"]["table/table_AN.json"]["checkpoint"]
    # a hash that differs stops the check before anything is read
    stopped = sample.check(invented_sample, SHAPES)
    assert stopped["stopped"] and not stopped["passes"] and "files" not in stopped

    # nine faults in one table, each on its own entry, each named by path
    root = str(tmp_path / "faulted")
    shutil.copytree(invented_sample, root)
    path = os.path.join(root, "table", "table_AN.json")
    with open(path) as fh:
        doc = json.loads(fh.read())
    runs = doc["rungs"]["0.5"]["runs"]
    runs["p_sched returned"].pop("steps")
    runs["p_sched held"]["route2"][1].update(ts_s="x")
    runs["p=0 returned"]["definition"]["model"]["cells"][0].update(volume_pL=True)
    runs["p=1 returned"]["definition"]["model"]["operators"].append({"law": "x@1"})
    runs["p_sched returned unlabelled"]["definition"]["experiment"].update(label_arrivals=[])
    runs["blank returned"]["readouts"].pop("H_route_tx")
    runs["stray"] = {}
    doc["plants"]["P3a"]["refused"] = False
    doc.pop("restart")
    with open(path, "w") as fh:
        fh.write(json.dumps(doc))
    write_sums(os.path.dirname(path))
    r = sample.check(root, _registered_as(root))
    at = "rungs.0.5.runs"
    for needle in (
        f"{at}.p_sched returned.steps: missing",
        f"{at}.p_sched held.route2[1].ts_s: type",
        f"{at}.p=0 returned.definition.model.cells[id=cell_0].volume_pL: type",
        f"{at}.p=1 returned.definition.model.operators[law=x@1]: forbidden",
        f"{at}.p_sched returned unlabelled.definition.experiment.label_arrivals: forbidden",
        f"{at}.blank returned.readouts.H_route_tx: missing",
        "entries in the file",
        "plants.P3a.refused: type",
        "restart: absent",
    ):
        assert any(needle in x for x in r["structural_faults"]), needle
    assert not r["passes"] and not r["coverage"]["the restart's checkpoint"]
    # a README the committed shapes do not equal, and a kind of entry the sample lacks
    with monkeypatch.context() as m:
        m.setattr(shapes, "schema_from_readme", lambda text: {"kinds": {}})
        assert not sample.check(invented_sample, _registered_as(invented_sample))["passes"]
    gone = str(tmp_path / "gone")
    shutil.copytree(invented_sample, gone)
    path = os.path.join(gone, "table", "table_C.json")
    with open(path) as fh:
        doc = json.loads(fh.read())
    doc["plants"] = {}
    with open(path, "w") as fh:
        fh.write(json.dumps(doc))
    write_sums(os.path.join(gone, "table"))
    r = sample.check(gone, _registered_as(gone))
    assert not r["coverage"]["P8 blank"] and not r["passes"]
    # the CLI's check stops on the registered hashes
    from validation.gene_regulation.fr38_v2.judge import __main__ as cli

    out = str(tmp_path / "report.json")
    assert cli.main(["sample", "--sample", invented_sample, "--out", out]) == 1
    with open(out) as fh:
        assert json.loads(fh.read())["stopped"]


def _honest_h(reg, family, run):
    return reg.synths[family].record(run, "honest", 0.5)


def test_registered_c_and_d_verdicts(registered):
    """C and D carry their own verdicts beside FR-38's and never decide it (CRITERIA.md §4)."""
    hc = _honest_h(registered, "invented_C", "p_sched returned")
    v = judge_registered(
        registered,
        edited(
            registered,
            "c_miss",
            where("invented_C", role="plant", plant="P8", run="p_sched returned"),
            lambda rec: rec.update(series=hc["series"]),
        ),
    )
    assert plant_status(v, "P8") == "not caught" and v["comparison"]["C"] == "fail"
    assert v["comparison"]["FR-38"] == "pass"

    def pool0(rec):
        rec["series"]["label_R_pool0"] = [x * (1 - 1e-3) for x in rec["series"]["label_R_pool0"]]

    v = judge_registered(
        registered,
        edited(
            registered,
            "c_nc",
            where("invented_C", role="plant", plant="P8", run="p_sched returned"),
            pool0,
        ),
    )
    assert plant_status(v, "P8") == "caught" and not v["plants"]["P8"]["negative_control_passes"]
    assert v["comparison"]["C"] == "inconclusive" and v["comparison"]["FR-38"] == "pass"
    hd = _honest_h(registered, "invented_D", "p_sched returned")
    v = judge_registered(
        registered,
        edited(
            registered,
            "d_miss",
            where("invented_D", role="plant", plant="P9"),
            lambda rec: rec.update(series=hd["series"]),
        ),
    )
    assert plant_status(v, "P9") == "not caught" and v["comparison"]["D"] == "fail"
    assert v["comparison"]["FR-38"] == "pass"


def test_registered_names_read_spec_inputs(mapping):
    """A smoke over the five registered families on SPEC.md's own inputs (no engine output): every
    definition the export must carry, and every accessor the rules read."""
    for fam in spec.REAL_FAMILIES:
        profile = spec.FAMILY_PROFILE[fam]
        inputs = spec.spec_inputs(fam)
        times = spec.grid(inputs)
        window = tuple(inputs["window_s"])
        samples = inputs["samples_s"]
        assert samples[0] == window[1] and all(t in times for t in samples)
        ref = types.SimpleNamespace(
            inputs=inputs,
            times=np.asarray(times),
            window=window,
            samples=samples,
            plants=[],
            accepted=True,
        )
        f = J.Family(fam, profile, ref)
        assert f.inputs == inputs and f.role == fam
        for fate in spec.FATES:
            assert spec.fate_rate(inputs, fate) > 0.0
        assert spec.chain_length(inputs) == 1200 and spec.pool_fmol(inputs, "pol") > 0.0
        assert spec.residue_potential(inputs) == inputs["mu0_RT_at_1M"]["R"] / 1200
        stubs = [(r, "honest", None, None) for r in spec.honest_runs(inputs)]
        if spec.has_blank(profile):
            stubs += [("blank", "blank", None, m) for m in f.blank_machines()]
        stubs += [(r, "twin", None, None) for r in f.twin_runs()]
        if f.restart():
            stubs.append((f.restart()[0], "restart", None, None))
        for plant, where_ in spec.PLANT_RUNS.items():
            stubs += [(r, "plant", plant, "returned") for ff, r in where_ if ff == fam]
        honest_def = {}
        for run, role, plant, machine in stubs:
            d = engine_definition(inputs, profile, run, role, plant, machine or "returned", 0.5)
            if role == "plant":
                base = honest_def["blank returned" if run == "blank" else run]
                assert definitions.plant_change_faults(plant, base, d, inputs) == [], (fam, plant)
                continue
            faults = definitions.check_definition(
                d, inputs, profile, run, role, machine or "returned", 0.5
            )
            assert faults == [], (fam, run, role, faults[:3])
            assert definitions.recorded(d, inputs, profile)[1] == [], (fam, run)
            if role in ("honest", "blank"):
                honest_def[f"blank {machine}" if run == "blank" else run] = d
        for p in list(spec.CORE_PLANTS) + ["P8", "P9"]:
            J.plant_units(f, p)
        assert J.plant_units(f, "P4") == (
            [("AN", "p_sched returned")]
            if fam == "AN"
            else [("B", "p=0.55 returned")]
            if fam == "B"
            else []
        )
        if fam == "B":
            assert spec.pool_fmol(inputs, "rib") > 0.0
        # every series' class rule, and the scales and identities on stand-in values
        names = [
            e["engine"].partition("/")[2]
            for e in mapping["readouts"]
            if e["status"].get(profile) and e["engine"].startswith("series/")
        ]
        vals = {n: np.linspace(1.0, 2.0, len(times)) for n in names}
        for run in spec.honest_runs(inputs) + ["blank"] * spec.has_blank(profile):
            idle = None if run == "blank" else spec.idle_fate(inputs["runs"][run]["p"])
            for n in names:
                spec.constant_mask(n, times, window, blank=run == "blank", idle=idle)
        ctx = rules.ScaleContext(profile, inputs, vals, blank=False, blank_values=vals)
        assert ctx.g_scale() > 0.0 and ctx.heat_scale() > 0.0
        if profile == "D":
            assert ctx.d_identity_scale() > 0.0
        assert rules.identities(vals, inputs, profile, "held", 28800, blank=False)
