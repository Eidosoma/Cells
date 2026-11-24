"""Host-only tests of FR-38's second comparison judge, on invented inputs only.

**Seconds:** 19 to 39 s on one core (26 s for its 21 tests on CPU 7, 24 November 2026).
**Reason (D224):** the judge decides FR-38's registered verdict, so each C0 refusal, each failure
and inconclusive mode, the retry and each plant (caught and not caught) must be shown to move it
the registered way before any engine run is judged.

- **Inputs.** The references' invented file (`reference_invented.json`, read from the tree or
  from tag `fr38-v2-references-2026-11-24`; the test fails if neither has it), invented families
  of profiles B, C and D derived from it here, and engine records invented here. The registered
  branches (AF's two blanks, AN's restart, the plants' runs, the arms) run on invented families
  given the registered roles.
- **No engine** is compiled, imported or run, and no engine output is read.
- **The honest invented engine** scales every deviation from t = 0 by 1 + C3 dt³, which keeps every
  linear identity and every structural zero and gives each readout an observed order of 3.
"""

import copy
import json
import math
import os
import shutil
import subprocess
import types

import numpy as np
import pytest

from validation.gene_regulation.fr38_v2.judge import judge as J
from validation.gene_regulation.fr38_v2.judge import records, rules, spec

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


class Synth:
    """Writes an engine export for one invented family from its reference."""

    def __init__(self, doc, profile, mapping):
        self.doc, self.profile, self.mapping = doc, profile, mapping
        self.family = doc["family"]
        self.inputs = doc["inputs"]
        self.times = list(doc["times_s"])
        self.window = tuple(self.inputs["window_s"])
        self.samples = list(doc["samples_s"])
        self.horizon = float(self.inputs["horizon_s"])
        self.two_blanks = False
        self.tweaks = []  # (predicate(rec), function(rec)) applied before writing

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

    def record(self, run, role, dt, *, attempt="primary", plant=None, machine="returned"):
        base = "blank" if run == "blank" else run
        series = self.series(base, dt, attempt)
        stub = types.SimpleNamespace(run=run, role=role, plant=plant, machine=machine)
        restart = self.horizon / 2.0 if role == "restart" else None
        definition = records.expected_definition(
            self.inputs, stub, restart=restart, gene_unit_volume=self.profile == "D"
        )
        if run == "blank":
            definition["machine"] = machine
        rec = {
            "kind": records.RUN_KIND,
            "family": self.family,
            "run": run,
            "role": role,
            "plant": plant,
            "attempt": attempt,
            "dt_s": dt,
            "status": "completed",
            "refusal": None,
            "definition": definition,
            "times_s": self.times,
        }
        if role == "twin":
            series = {
                k: v
                for k, v in series.items()
                if not k.startswith(("label_", "released_present_gross_"))
            }
        rec["series"] = series
        if run != "blank":
            r2, sv = self.host(self.series(base, dt, attempt))
            rec["route2"] = r2
            if role != "twin":
                rec["survival"] = sv
        rec["checks"] = {"invented_check": 1.0e-20}
        if role == "plant":
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
        for attempt, rungs in (("primary", spec.PRIMARY_RUNGS),):
            for dt in rungs:
                for r in honest:
                    recs.append(self.record(r, "honest", dt, attempt=attempt))
                if self.has_blank():
                    recs.append(self.record("blank", "blank", dt, attempt=attempt))
                    if self.two_blanks:
                        recs.append(
                            self.record("blank", "blank", dt, attempt=attempt, machine="held")
                        )
                twins = honest if self.profile == "B" else ["p_sched returned"]
                for r in twins:
                    if r in honest:
                        recs.append(self.record(r, "twin", dt, attempt=attempt))
        if "p_sched returned" in honest:
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

    def write(self, folder, recs=None):
        recs = self.all_records() if recs is None else recs
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, "manifest.json"), "w") as fh:
            fh.write(json.dumps({"kind": records.EXPORT_KIND, "provenance": {"invented": True}}))
        for i, rec in enumerate(recs):
            for pred, fn in self.tweaks:
                if pred(rec):
                    fn(rec)
            out = dict(rec)
            out["series"] = {k: [float(x) for x in v] for k, v in rec["series"].items()}
            run = rec["run"].replace(" ", "_")
            name = (
                f"{rec['family']}_{i:03d}_{rec['role']}_{run}_{rec['attempt']}_{rec['dt_s']}.json"
            )
            with open(os.path.join(folder, name), "w") as fh:
                fh.write(json.dumps(out))  # the C encoder: json.dump streams in Python
        return folder


def is_(run=None, role=None, dt=None, plant=None, attempt=None, machine=None):
    def pred(rec):
        return (
            (run is None or rec["run"] == run)
            and (role is None or rec["role"] == role)
            and (dt is None or rec["dt_s"] == dt)
            and (plant is None or rec["plant"] == plant)
            and (attempt is None or rec["attempt"] == attempt)
            and (machine is None or rec["definition"].get("machine") == machine)
        )

    return pred


def write_refs(folder, doc):
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, f"reference_{doc['family']}.json"), "w") as fh:
        fh.write(json.dumps(doc))
    return folder


def run_judge(tmp_path, docs, synths, name="x"):
    """docs: reference documents; synths: their engine writers. Returns the verdict."""
    refs = write_refs(str(tmp_path / f"refs_{name}"), docs[0])
    for d in docs[1:]:
        write_refs(refs, d)
    export = str(tmp_path / f"export_{name}")
    for s in synths:
        s.write(export, getattr(s, "records_override", None))
    fams = {d["family"]: s.profile for d, s in zip(docs, synths, strict=True)}
    return J.judge(refs, export, families=fams)


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

    def check(rec):
        rec["checks"] = {"invented_check": 2.0e-20}

    v = _perturbed(
        invented, mapping, tmp_path, [(is_("p_sched returned", "twin", 0.5), check)], "twin_checks"
    )
    assert verdict_of(v, "invented", "p_sched returned") == "fail"
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

    # C0 refusals of engine records: a definition off, a missing output, a missing readout, a
    # non-finite value, a duplicate, and a missing rung
    def off(rec):
        rec["definition"]["tau_s"] = rec["definition"]["tau_s"] * (1 + 1e-9)

    def short(rec):
        rec["times_s"] = rec["times_s"][:-1]

    def missing(rec):
        rec["series"].pop("H_deg_R_s")

    def nonfinite(rec):
        rec["series"]["n_M"] = rec["series"]["n_M"].copy()
        rec["series"]["n_M"][3] = float("nan")

    for name, f in (
        ("definition", off),
        ("short", short),
        ("missing", missing),
        ("nonfinite", nonfinite),
    ):
        v = _perturbed(
            invented, mapping, tmp_path, [(is_("p=0 returned", "honest", 0.5), f)], f"c0_{name}"
        )
        assert verdict_of(v, "invented", "p=0 returned") == "refused", name
        assert v["c0"]["engine"]["refused_records"], name

    # a record naming one of the judge's own plants (P1′ here) is refused
    def judge_plant(rec):
        rec["plant"] = "P1′"

    v = _perturbed(
        invented, mapping, tmp_path, [(is_(role="plant", plant="P5"), judge_plant)], "c0_p1p"
    )
    faults = [f for r in v["c0"]["engine"]["refused_records"] for f in r["faults"]]
    assert any("not an engine-record plant" in f for f in faults)
    assert plant_status(v, "P5") == "refused"
    s = Synth(invented, "A", mapping)
    recs = s.all_records()
    dup = [r for r in recs if r["run"] == "p=1 returned" and r["role"] == "honest"][0]
    s.records_override = recs + [copy.deepcopy(dup)]
    v = run_judge(tmp_path, [invented], [s], name="dup")
    assert verdict_of(v, "invented", "p=1 returned") == "refused"
    s.records_override = [
        r
        for r in recs
        if not (r["run"] == "p=1 returned" and r["dt_s"] == 2.0 and r["role"] == "honest")
    ]
    v = run_judge(tmp_path, [invented], [s], name="gap")
    assert verdict_of(v, "invented", "p=1 returned") == "refused"


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

    # a judge-side refusal is not a catch: a plant whose definition carries an unregistered change
    def wrong(rec):
        rec["definition"]["tau_s"] = 61.0

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
    for f, d in docs.items():
        s = Synth(d, profiles[f], mapping)
        s.two_blanks = roles[f] == "AF"
        s.write(export)
    return types.SimpleNamespace(
        refs=refs, export=export, profiles=profiles, roles=roles, docs=docs, tmp=tmp
    )


def judge_registered(reg, export=None):
    return J.judge(reg.refs, export or reg.export, families=reg.profiles, roles=reg.roles)


def edited(reg, name, pred, fn=None):
    """A copy of the registered export with matching records edited, or removed (fn None)."""
    dst = str(reg.tmp / name)
    shutil.copytree(reg.export, dst)
    for fname in sorted(os.listdir(dst)):
        if fname == "manifest.json":
            continue
        path = os.path.join(dst, fname)
        with open(path) as fh:
            rec = json.loads(fh.read())
        if not pred(rec):
            continue
        if fn is None:
            os.remove(path)
            continue
        fn(rec)
        with open(path, "w") as fh:
            fh.write(json.dumps(rec))
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
    honest = None
    for fname in os.listdir(registered.export):
        if fname.startswith("inv_AF") and "_honest_p_sched_returned_primary_0.5" in fname:
            with open(os.path.join(registered.export, fname)) as fh:
                honest = json.loads(fh.read())

    def same(rec):
        rec["series"] = honest["series"]

    v = judge_registered(
        registered, edited(registered, "p5", where("inv_AF", role="plant", plant="P5"), same)
    )
    assert v["comparison"]["arms"] == {"A": "pass", "B": "pass"}
    assert plant_status(v, "P5") == "not caught" and v["comparison"]["FR-38"] == "fail"
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
