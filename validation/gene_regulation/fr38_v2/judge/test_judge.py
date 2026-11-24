"""Host-only tests of FR-38's second comparison judge, on invented inputs only.

**Seconds:** 33 s for its 24 tests on CPU 7 at load 25 (24 November 2026); 20 to 90 s with load.
**Reason (D224):** the judge decides FR-38's registered verdict, so each C0 refusal, each failure
and inconclusive mode, the retry and each plant (caught and not caught) must be shown to move it
the registered way before any engine run is judged.

- **Inputs.** The references' invented file (`reference_invented.json`, read from the tree or
  from tag `fr38-v2-references-2026-11-24`; the test fails if neither has it), invented families
  of profiles B, C and D derived from it here, and engine records invented here. The registered
  branches (AF's two blanks, AN's restart, the plants' runs, the arms) run on invented families
  given the registered roles.
- **The engine's tables** (amendment 4, §8) are written by this file's own builder
  (`engine_definition`, `Synth`), apart from the judge's expectations (`definitions.py`), in the
  narrow shapes the judge reads where §8 is silent.
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

from validation.gene_regulation.fr38_v2.judge import definitions, records, rules, spec
from validation.gene_regulation.fr38_v2.judge import judge as J

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
TAG = "fr38-v2-references-2026-11-24"
INVENTED = "validation/gene_regulation/fr38_v2/references/out/reference_invented.json"
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


def _gene(defn):
    return next(
        o for o in defn["model"]["operators"] if o.get("law") == "templated_polymerisation@1"
    )


def release(rec):
    """The transcription chain's release block of a record's declaration."""
    return _gene(rec["definition"])["chains"][0]["release"]


def engine_definition(inputs, profile, run, role, plant, machine, dt):
    """An engine declaration with SPEC.md's inputs where amendment 4, §8.5 puts them: the test's
    own builder, written apart from the judge's expectations (definitions.py)."""
    V = float(inputs["volume_pL"])
    blank = run == "blank"
    mu0 = inputs["mu0_RT_at_1M"]
    if profile == "B":
        cell = {r: float(c) * V for r, c in inputs["initial_mM"].items()}
    else:
        cell = {r: float(c) * V for r, c in inputs["initial_mM"].items()}
        cell.update({r: float(n) * COPY for r, n in inputs["initial_copies"].items()})
        cell.update({i: float(c) * V for i, c in inputs["cell_background_mM"].items()})
        if profile == "C":
            cell["Mx"] = float(inputs["store"]["Mx_initial_mM"]) * V
    gene_rows = ["N", "M", "Pi", "R", "R_s"] + (["A", "ATP", "ADP", "P"] if profile == "B" else [])
    species = [{"id": r, "standard_mu_RT": float(mu0[r])} for r in gene_rows]
    model_species = [dict(x) for x in species]
    if profile != "B":
        model_species += [
            {"id": "K", "standard_mu_RT": 0.0, "charge": 1},
            {"id": "Y", "standard_mu_RT": 0.0, "charge": -1},
        ]
    if profile == "C":
        model_species.append(
            {"id": "Mx", "standard_mu_RT": float(inputs["store"]["mu0_Mx_RT_at_1M"])}
        )
    moieties = []
    for m, w in inputs["moieties"].items():
        w = dict(w)
        if profile == "C" and m in inputs["store"]["Mx_moieties"]:
            w["Mx"] = inputs["store"]["Mx_moieties"][m]
        moieties.append({"id": m, "weights": w})
    model = {
        "temperature_K": inputs["constants"]["T_K"],
        "standard_concentration_mM": inputs["constants"]["c_standard_mM"],
        "cells": [{"id": "cell_0", "volume_pL": V, "initial_amount_fmol": cell}],
        "species": model_species,
        "moieties": moieties,
        "operators": [],
    }
    if profile != "B":
        vb = float(inputs["bath_volume_pL"])
        bath = {i: float(c) * vb for i, c in inputs["bath_mM"].items()}
        for r in ["N", "M", "Pi", "R", "R_s"] + (["Mx"] if profile == "C" else []):
            bath[r] = float(inputs["bath_trace_mM"]) * vb
        model["extracellular"] = [
            {"id": "bath_0", "volume_pL": vb, "initial_amount_fmol": bath, "reservoir": True}
        ]
        model["membranes"] = [{"membrane_id": "patch_0", "area_m2": 1e-10}]
    L = inputs.get("L_residues", inputs.get("L_R_nt"))
    if blank:
        df, p_sched, m = 0.0, None, machine
    else:
        ps, m = inputs["runs"][run]["p"], inputs["runs"][run]["machine"]
        if len(ps) == 1 and float(ps[0][0]) == 0.0:
            df, p_sched = float(ps[0][1]), None
        else:
            df, p_sched = "scheduled", ps
    chain = {
        "id": "tx",
        "template": {"copies": inputs["template_copies"]},
        "product": "R",
        "residues": L,
        "stages": inputs.get("stages", inputs.get("m_tx")),
        "speed_per_s": inputs.get("speed_nt_per_s", inputs.get("v_tx_nt_per_s")),
        "draws": {"N": inputs.get("N_per_residue", 1)},
        "releases": {"Pi": inputs.get("Pi_per_residue", 2)},
        "saturation_mM": {"N": inputs.get("K_N_mM", inputs.get("K_N_tx_mM"))},
        "release": {
            "id": "tx_release",
            "dwell_s": inputs["tau_s"],
            "machine": m,
            "durable_fraction": df,
            "fates": {"durable": "R", "short_lived": "R_s"},
            "label": {"at": "release"},
            "initial_copies": [0 if blank else inputs["H0_copies"]],
        },
    }
    gene = {
        "law": "templated_polymerisation@1",
        "species": species,
        "pools": [
            {
                "id": "pol",
                "machines": inputs.get("pool_machines_copies", inputs.get("M_pol_copies")),
            }
        ],
        "chains": [chain],
        "degradations": [
            {"id": "deg_R", "polymer": "R", "residues": L, "monomers": "M"},
            {"id": "deg_R_s", "polymer": "R_s", "residues": L, "monomers": "M"},
        ],
    }
    k_i = inputs.get("k_I_tx_per_mM_s", inputs["k_I_per_mM_s"])
    controls = [
        {"route_id": "tx", "schedule": [{"time": 0.0, "value": 0.0 if blank else k_i}]},
        {"route_id": "deg_R", "schedule": [{"time": 0.0, "value": inputs["k_d_per_s"]}]},
        {"route_id": "deg_R_s", "schedule": [{"time": 0.0, "value": inputs["k_s_per_s"]}]},
    ]
    if p_sched is not None:
        controls.append(
            {"route_id": "tx_release", "schedule": [{"time": t, "value": v} for t, v in p_sched]}
        )
    if profile == "B" and "L_P_aa" in inputs:
        gene["pools"].append({"id": "rib", "machines": inputs["M_rib_copies"]})
        for c, tmpl in (("tl", "R"), ("tl_s", "R_s")):
            gene["chains"].append(
                {
                    "id": c,
                    "template": {"species": tmpl},
                    "product": "P",
                    "residues": inputs["L_P_aa"],
                    "stages": inputs["m_tl"],
                    "speed_per_s": inputs["v_tl_aa_per_s"],
                    "draws": {"A": 1, "ATP": 4},
                    "releases": {"ADP": 4, "Pi": 4},
                    "saturation_mM": {"A": inputs["K_A_tl_mM"], "ATP": inputs["K_ATP_tl_mM"]},
                }
            )
            controls.append(
                {"route_id": c, "schedule": [{"time": 0.0, "value": inputs["k_I_tl_per_mM_s"]}]}
            )
        gene["degradations"].append(
            {"id": "deg_P", "polymer": "P", "residues": inputs["L_P_aa"], "monomers": "A"}
        )
        controls.append(
            {"route_id": "deg_P", "schedule": [{"time": 0.0, "value": inputs["k_P_per_s"]}]}
        )
        gene["transfers"] = [{"id": "rc", "capacity_mM_per_s": 0.01}]
        model["operators"] += [
            {"law": "scheduled_species_turnover@1", "species": "X"},
            {"law": "hill_activation@1", "route": "tx"},
        ]
    model["operators"].append(gene)
    times = [
        float(inputs["output_interval_s"]) * i
        for i in range(
            int(round(float(inputs["horizon_s"]) / float(inputs["output_interval_s"]))) + 1
        )
    ]
    exp = {
        "end_time": inputs["horizon_s"],
        "observation_times": times,
        "polymerisation_controls": controls,
    }
    if role != "twin":
        sched = inputs["label_schedule_s"]
        model["operators"].append(
            {
                "law": "neutral_arrival_labels@1",
                "species": [
                    {
                        "id": r,
                        "labels": ["resyn", "pool0", "pre", "win", "post"],
                        "initial": [
                            {"node": "cell_0", "shares": dict(inputs["initial_label_shares"])}
                        ],
                    }
                    for r in ("R", "R_s")
                ],
            }
        )
        exp["label_arrivals"] = []
        for r in ("R", "R_s"):
            exp["label_arrivals"] += [
                {"species": r, "schedule": [{"time": 0.0, "label": "resyn"}]},
                {
                    "species": r,
                    "source": "tx",
                    "schedule": [
                        {"time": sched["pre"], "label": "pre"},
                        {"time": sched["win"], "label": "win"},
                        {"time": sched["post"], "label": "post"},
                    ],
                },
            ]
    if profile == "C":
        st = inputs["store"]
        model["operators"].append(
            {
                "law": "local_species_reactions@1",
                "standard_concentration_mM": st["network_c0_mM"],
                "species": [
                    {
                        "id": "M",
                        "moieties": {k: w["M"] for k, w in inputs["moieties"].items() if "M" in w},
                        "standard_mu_RT": st["network_mu0_RT_at_c0"]["M"],
                    },
                    {
                        "id": "Mx",
                        "moieties": dict(st["Mx_moieties"]),
                        "standard_mu_RT": st["network_mu0_RT_at_c0"]["Mx"],
                    },
                ],
                "reactions": [
                    {
                        "id": "store_M",
                        "sites": ["cell_0"],
                        "reactants": {"M": 1},
                        "products": {"Mx": 1},
                        "law": "ideal_detailed_balance_mass_action@1",
                        "forward_rate_per_s": st["forward_per_s_at_c0"],
                    }
                ],
            }
        )
        exp["reaction_controls"] = [
            {"route_id": "store_M", "schedule": [{"time": 0.0, "value": st["multiplier"]}]}
        ]
    if profile == "D":
        w = inputs["water"]
        model["operators"].append(
            {
                "law": "ideal_osmosis_linear_compliance_water@1",
                "compartments": [
                    {
                        "compartment_id": "cell_0",
                        "reference_volume_pL": w["V_ref_pL"],
                        "minimum_volume_pL": w["V_min_pL"],
                        "maximum_volume_pL": w["V_max_pL"],
                        "impermeant_amount_fmol": w["impermeant_fmol"],
                        "bulk_modulus_Pa": w["bulk_modulus_Pa"],
                        "pressure_offset_Pa": w["pressure_offset_Pa"],
                    }
                ],
                "baths": [{"id": "bath_0", "hydrostatic_pressure_Pa": w["bath_pressure_Pa"]}],
                "membranes": [
                    {
                        "membrane_id": "patch_0",
                        "hydraulic_permeability_m_per_Pa_s": w["L_p_m_per_Pa_s"],
                    }
                ],
            }
        )
        exp["water_controls"] = [{"time": 0.0, "availability": w["availability"]}]
    defn = {"model": model, "experiment": exp, "execution": {"dt": dt}}
    if plant is not None:
        _plant_declaration(defn, plant)
    return defn


def _plant_declaration(defn, plant):
    """A world-data plant's registered change, written into its declaration (CRITERIA.md §6)."""
    rel = _gene(defn)["chains"][0]["release"]
    if plant == "P2":
        rel["durable_fraction"] = 1.0 - 2.0**-30
    elif plant in ("P3a", "P3b"):
        lab = "win" if plant == "P3a" else "post"
        for e in defn["experiment"]["label_arrivals"]:
            if e.get("source") == "tx":
                for x in e["schedule"]:
                    if x["label"] == lab:
                        x["time"] = x["time"] + 0.5
    elif plant == "P4":
        rel["label"] = {"at": "completion"}
    elif plant == "P5":
        for c in defn["experiment"]["polymerisation_controls"]:
            if c["route_id"] == "deg_R_s":
                c["schedule"][0]["value"] = c["schedule"][0]["value"] * (1 + 1e-4)
    elif plant == "P7":
        rel["machine"] = "returned"
    elif plant == "P8":
        store = next(
            o for o in defn["model"]["operators"] if o.get("law") == "local_species_reactions@1"
        )
        store["reactions"][0]["forward_rate_per_s"] *= 1.01


def write_sums(folder):
    lines = []
    for fn in sorted(os.listdir(folder)):
        if fn.startswith("table_") and fn.endswith(".json"):
            with open(os.path.join(folder, fn), "rb") as fh:
                lines.append(f"{hashlib.sha256(fh.read()).hexdigest()}  {fn}\n")
    with open(os.path.join(folder, "SHA256SUMS"), "w") as fh:
        fh.write("".join(lines))


class Synth:
    """Writes the engine's tables (amendment 4, §8) for one invented family from its reference."""

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
        self._base = None

    def base(self):
        """The honest records, built once (writes copy them)."""
        if self._base is None:
            self._base = self.all_records()
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

    def host(self, series):
        t1, t2 = self.window
        route2, survival = [], []
        for fate, row in (("durable", "R"), ("short_lived", "R_s")):
            A = series[f"int_Q_tx_release_{fate}"]
            k = spec.fate_rate(self.inputs, fate)
            for ts in self.samples:
                route2.append(
                    {
                        "fate": fate,
                        "ts_s": ts,
                        "value": rules.known_rate(self.times, A, k, t1, t2, ts),
                    }
                )
            win = series[f"label_{row}_win"]
            a2 = float(win[self.times.index(t2)])
            for ts in self.samples[1:]:
                a3 = float(win[self.times.index(ts)])
                survival.append(
                    {
                        "fate": fate,
                        "t2_s": t2,
                        "ts_s": ts,
                        "alive_t2": a2,
                        "alive_ts": a3,
                        "ratio": a3 / a2 if a2 != 0.0 else None,
                    }
                )
        return route2, survival

    def plant_name(self, plant, run):
        if plant == "P4":
            return "P4 B" if self.profile == "B" else "P4 AN"
        if plant == "P8" and run == "blank":
            return "P8 blank"
        return plant

    def record(self, run, role, dt, *, attempt="primary", plant=None, machine="returned"):
        base = "blank" if run == "blank" else run
        series = self.series(base, dt, attempt)
        if role == "blank":
            name = f"blank {machine}"
        elif role == "twin":
            name = f"{run} unlabelled"
        elif role == "restart":
            name = "restart"
        elif role == "plant":
            name = self.plant_name(plant, run)
        else:
            name = run
        rec = {
            "family": self.family,
            "name": name,
            "run": run,
            "role": role,
            "plant": plant,
            "attempt": attempt,
            "dt_s": dt,
            "machine": machine if run == "blank" else None,
            "status": "completed",
            "refusal": None,
            "times_s": list(self.times),
            "definition": engine_definition(
                self.inputs, self.profile, run, role, plant, machine, dt
            ),
            "source": f"invented engine for {self.family}",
            "record": f"records/{self.family}/{name}_{attempt}_{dt}.json",
            "record_sha256": hashlib.sha256(
                f"{self.family}/{name}/{attempt}/{dt}".encode()
            ).hexdigest(),
        }
        if role == "twin":
            series = {
                k: v
                for k, v in series.items()
                if not k.startswith(("label_", "released_present_gross_"))
            }
        rec["series"] = series
        if run != "blank" and self.has_blank():
            two = self.two_blanks
            rec["excess_blank"] = (
                "P8 blank"
                if plant == "P8"
                else f"blank {self.inputs['runs'][run]['machine'] if two else 'returned'}"
            )
        if run != "blank":
            r2, sv = self.host(self.series(base, dt, attempt))
            rec["route2"] = r2
            if role != "twin":
                rec["survival"] = sv
        rec["checks"] = {"invented_check": 1.0e-20}
        if role == "plant":
            rec["judged_as"] = "blank returned" if run == "blank" else run
            self.plant_change(rec, plant, run)
        return rec

    def plant_change(self, rec, plant, run):
        """A planted run that differs from the honest one as the reference predicts."""
        for readout in spec.plant_readouts(plant):
            ents = [
                e
                for e in self.doc["plants"]
                if e["plant"] == plant and e["run"] == run and e["quantity"] == readout
            ]
            if not ents:
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
        if "p_sched returned" in honest and self.profile != "B" and self.role in (None, "AN"):
            recs.append(self.record("p_sched returned", "restart", 0.5))
        for plant in sorted({e["plant"] for e in self.doc["plants"]}):
            if plant not in records.RECORD_PLANTS:
                continue
            for run in sorted({e["run"] for e in self.doc["plants"] if e["plant"] == plant}):
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
        if rec["status"] == "refused":
            out = {"refused": True, "refusal": rec["refusal"], "definition": rec["definition"]}
            if rec["role"] == "plant":
                out["judged_as"] = rec["judged_as"]
            return out
        out = {
            "t": rec["times_s"],
            "readouts": {
                k: [float(x) for x in v]
                for k, v in rec["series"].items()
                if not k.startswith("excess_over_blank_")
            },
            "checks": rec["checks"],
            "own_ledgers_at_end": {"invented": 0.0},
            "steps": rec.get("steps", int(round(self.horizon / rec["dt_s"]))),
            "dt_s": rec["dt_s"],
            "definition": rec["definition"],
        }
        for k in ("source", "record", "record_sha256"):
            if rec.get(k) is not None:
                out[k] = rec[k]
        ex = {
            k[len("excess_over_blank_") :]: [float(x) for x in v]
            for k, v in rec["series"].items()
            if k.startswith("excess_over_blank_")
        }
        if ex:
            out["excess_over_blank"] = {"blank": rec.get("excess_blank"), **ex}
        if "route2" in rec:
            out["route2"] = [dict(e, grid_error=0.0) for e in rec["route2"]]
        if "survival" in rec:
            out["survival"] = rec["survival"]
        if rec["role"] == "plant":
            out["judged_as"] = rec["judged_as"]
        if rec["role"] == "restart":
            out["checkpoint"] = {"time_s": self.horizon / 2.0, "files_sha256": "0" * 64}
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
            table = {
                "kind": "cells.fr38_v2.engine_table@1",
                "family": self.family,
                "window_s": list(self.window),
                "samples_s": self.samples,
                "missing": [],
                "rungs": {},
            }
            for r in rs:
                rung = table["rungs"].setdefault(
                    repr(float(r["dt_s"])), {"dt_s": float(r["dt_s"]), "runs": {}}
                )
                e = self.entry(r)
                if r["role"] == "restart":
                    table["restart"] = e
                elif r["role"] == "plant":
                    rung.setdefault("plants", {})[r["name"]] = e
                else:
                    rung["runs"][r["name"]] = e
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
    """docs: reference documents; synths: their engine writers. Returns the verdict."""
    refs = write_refs(str(tmp_path / f"refs_{name}"), docs[0])
    for d in docs[1:]:
        write_refs(refs, d)
    export = str(tmp_path / f"export_{name}")
    for s in synths:
        s.write(export, getattr(s, "records_override", None))
    fams = {d["family"]: s.profile for d, s in zip(docs, synths, strict=True)}
    return J.judge(refs, export, families=fams, roles=roles)


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
        rec["checks"] = {"invented_check": 2.0e-20}

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
        v = run_judge(tmp_path, [invented], [s], name=f"retry_{name}")
        run = v["families"]["invented"]["runs"]["p_sched held"]
        assert run["primary"]["verdict"] == "inconclusive", name
        assert run["retry"]["rungs_s"] == [1.0, 0.5, 0.25] and run["verdict"] == expect, name


def test_refused_runs(invented, mapping, tmp_path):
    def refused(rec):
        rec["status"], rec["refusal"] = "refused", "domain: y_f above X_DOM (invented)"
        for k in ("series", "route2", "survival", "times_s"):
            rec.pop(k, None)
        rec["series"] = {}

    v = _perturbed(
        invented, mapping, tmp_path, [(is_("p=0 returned", "honest", 1.0), refused)], "eng_refused"
    )
    assert verdict_of(v, "invented", "p=0 returned") == "refused"
    assert v["families"]["invented"]["verdict"] == "inconclusive"
    assert v["comparison"]["invented"] == "inconclusive"

    # C0 refusals of table entries: a declaration off (a value beyond 10⁻¹², an extra schedule
    # point, the gene unit not found or found twice), a missing output, a missing or non-finite
    # readout, a run without its provenance, an excess against the wrong blank
    def off(rec):
        release(rec)["dwell_s"] = release(rec)["dwell_s"] * (1 + 1e-9)

    def extra_point(rec):
        tx = rec["definition"]["experiment"]["polymerisation_controls"][0]
        tx["schedule"] = tx["schedule"] + [{"time": 50.0, "value": tx["schedule"][0]["value"]}]

    def no_gene(rec):
        _gene(rec["definition"])["law"] = "templated_polymerisation@2"

    def two_genes(rec):
        rec["definition"]["model"]["operators"].append(copy.deepcopy(_gene(rec["definition"])))

    def short(rec):
        rec["times_s"] = rec["times_s"][:-1]

    def missing(rec):
        rec["series"].pop("H_deg_R_s")

    def nonfinite(rec):
        rec["series"]["n_M"] = rec["series"]["n_M"].copy()
        rec["series"]["n_M"][3] = float("nan")

    def no_provenance(rec):
        rec.pop("record_sha256")

    def wrong_blank(rec):
        rec["excess_blank"] = "blank held"

    for name, f, needle in (
        ("definition", off, "τ"),
        ("schedule", extra_point, "k_I"),
        ("no gene unit", no_gene, "0 declarations name"),
        ("two gene units", two_genes, "2 declarations name"),
        ("short", short, "output grid"),
        ("missing", missing, "missing readout"),
        ("nonfinite", nonfinite, "finite"),
        ("provenance", no_provenance, "provenance"),
        ("blank name", wrong_blank, "matched"),
    ):
        v = _perturbed(
            invented, mapping, tmp_path, [(is_("p=0 returned", "honest", 0.5), f)], f"c0_{name}"
        )
        assert verdict_of(v, "invented", "p=0 returned") == "refused", name
        faults = [x for r in v["c0"]["engine"]["refused_records"] for x in r["faults"]]
        assert any(needle in x for x in faults), (name, faults[:3])

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
    # an unknown run name is recorded and ignored; the export's step count is recorded only
    s = Synth(invented, "A", mapping)
    recs = s.all_records()
    extra = copy.deepcopy(
        [r for r in recs if r["run"] == "p=1 returned" and r["role"] == "honest"][0]
    )
    extra["name"] = "p=1 returned copy"
    steps = [r for r in recs if r["run"] == "p=1 returned" and r["dt_s"] == 1.0][0]
    steps["steps"] = 7
    s.records_override = recs + [extra]
    v = run_judge(tmp_path, [invented], [s], name="unknown")
    assert verdict_of(v, "invented", "p=1 returned") == "pass"
    assert any("not a registered name" in n for n in v["c0"]["engine"]["notes"])
    assert any("steps 7" in n for r in v["c0"]["engine"]["record_notes"] for n in r["notes"])
    s.records_override = [
        r
        for r in recs
        if not (r["run"] == "p=1 returned" and r["dt_s"] == 2.0 and r["role"] == "honest")
    ]
    v = run_judge(tmp_path, [invented], [s], name="gap")
    assert verdict_of(v, "invented", "p=1 returned") == "refused"


def test_index_and_table_hash(invented, mapping, tmp_path):
    """A missing SHA256SUMS is recorded and flagged, not refused (amendment 4, item 6); a table
    whose hash departs from an index that lists it is refused."""
    s = Synth(invented, "A", mapping)
    refs = write_refs(str(tmp_path / "refs_idx"), invented)
    export = s.write(str(tmp_path / "export_idx"))
    os.remove(os.path.join(export, "table", "SHA256SUMS"))
    v = J.judge(refs, export, families={"invented": "A"})
    assert v["comparison"]["invented"] == "pass"
    assert (
        v["c0"]["engine"]["flags_for_the_checker"]
        and not v["c0"]["engine"]["index"]["table"]["SHA256SUMS"]
    )
    export = s.write(str(tmp_path / "export_mis"))
    with open(os.path.join(export, "table", "table_invented.json"), "a") as fh:
        fh.write(" ")
    v = J.judge(refs, export, families={"invented": "A"})
    assert verdict_of(v, "invented", "p_sched returned") == "refused"
    assert any("departs from" in f for t in v["c0"]["engine"]["tables"] for f in t["faults"])


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
    assert plant_status(v, "P5") == "refused" and any("registered change reads" in x
                                                      for x in faults)  # fmt: skip

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


def derive_b(doc, mapping, *, registered_names=False):
    d = copy.deepcopy(doc)
    d["family"] = "invented_B"
    keep = ("p_sched returned", "p_sched held")
    d["runs"] = {k: v for k, v in d["runs"].items() if k in keep}
    d["inputs"]["runs"] = {k: v for k, v in d["inputs"]["runs"].items() if k in keep}
    if registered_names:  # B's run names, so that the family can play role B
        d["family"] = "inv_B"
        names = {"p_sched returned": "p=0.55 returned", "p_sched held": "p=0.55 held"}
        d["runs"] = {names[k]: v for k, v in d["runs"].items()}
        d["inputs"]["runs"] = {names[k]: v for k, v in d["inputs"]["runs"].items()}
        for e in d["plants"]:
            e["run"] = names.get(e["run"], e["run"])
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
    assert set(fam["runs"]) == {"p_sched returned", "p_sched held"}  # no blank in B
    assert plant_status(v, "P4") == "caught"
    items = {
        i["readout"]: i
        for i in fam["runs"]["p_sched held"]["primary"]["readouts"]
        if "ts_s" not in i
    }
    assert items["n_N"]["status"] == "reported" and items["n_R"]["status"] == "judged"
    assert items["n_R"]["C2"]["p"] == 2 and "excess_over_blank_durable" not in items
    # A1's own readouts are reported: a miss there changes nothing; a judged miss fails
    s = Synth(db, "B", mapping)
    s.tweaks = [
        (
            lambda r: r["run"] == "p_sched held" and r["dt_s"] == 0.5,
            lambda r: r["series"].update(n_ATP=r["series"]["n_ATP"] * (1 + 1e-6)),
        )
    ]
    v = run_judge(tmp_path, [invented, db], [Synth(invented, "A", mapping), s], name="b_rep")
    assert v["families"]["invented_B"]["runs"]["p_sched held"]["verdict"] == "pass"
    # the ribosomes' identity, B's second pool
    s = Synth(db, "B", mapping)
    s.tweaks = [
        (
            is_("p_sched held", "honest", 0.5),
            lambda r: r["series"].update(F_rib=r["series"]["F_rib"] * (1 + 1e-9)),
        )
    ]
    v = run_judge(tmp_path, [invented, db], [Synth(invented, "A", mapping), s], name="b_rib")
    run = v["families"]["invented_B"]["runs"]["p_sched held"]["primary"]
    assert any(r["identity"] == "machines_rib" and r["fails"] for r in run["identities"]["0.5"])
    # each run of B has its twin
    s = Synth(db, "B", mapping)
    s.tweaks = [
        (
            is_("p_sched held", "twin", 1.0),
            lambda r: r["series"].update(n_P=r["series"]["n_P"] * (1 + 1e-15) + 1e-30),
        )
    ]
    v = run_judge(tmp_path, [invented, db], [Synth(invented, "A", mapping), s], name="b_twin")
    assert v["families"]["invented_B"]["runs"]["p_sched held"]["verdict"] == "fail"


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
        "inv_B": derive_b(invented, mapping, registered_names=True),
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


def edited(reg, name, pred, fn=None):
    """A copy of the registered export with matching records edited, or dropped (fn None): only
    the tables those records sit in are written again, with their index."""
    dst = str(reg.tmp / name)
    shutil.copytree(reg.export, dst)
    for s in reg.synths.values():
        if any(pred(r) for r in s.base()):
            s.write(dst, extra_tweaks=[(pred, fn)])
    return dst


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
            faults, _ = definitions.check_definition(
                d, inputs, profile, run, role, machine or "returned", 0.5
            )
            assert faults == [], (fam, run, role, faults[:3])
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
