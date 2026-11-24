"""FR-30's generic junction-gate benchmark harness at Tag A (docs/JUNCTION_TWO_RELAXATION_DESIGN.md
§13.7; D334, D308).

Modules under test: validation/junction_gate_benchmark/score.py (the reader, the value-free check,
the split, the one-cell rule, the verdict and Part S) and harness.py (the conventions, the
prediction and verify).

Invented inputs only: no paper's value is used, and nothing is fitted to data. Each claim, with the
planted error it must catch:
- **G1, the passing path.**
  - Decays at 40 to 120 mV hold out 60 and 100 mV at both polarities. `check` passes, and matching
    predictions pass.
  - Planted: a G_ss off by 0.06, or tau_slow off by 30% at two voltages, each fails. One such time
    still passes (three of four, at least 75%).
- **G2, §13.6's container.** An object of named lists is refused, naming "observables".
- **G3, dispersions.**
  - An SD becomes SD/sqrt(n) only with n and what n counts.
  - An SD without them, or a range, widens nothing (planted: an SD with n but no n_counts).
- **G4, leakage.** A training entry at a held-out magnitude is refused.
- **G5, the split.** A declared held-out set or class that is not S0 to S5's is refused, and so are
  differing split blocks. Decays at one polarity only fall in training_only.
- **G6, the entry's checks.** A sign against its polarity, a negative pooled entry, an amplitude
  without its definition, and a value given as text are each refused, naming key paths only.
- **G7, more than half.** k = 2 needs 2, k = 3 needs 2, and k = 4 needs 3.
- **G8, the one-cell rule (D334).**
  - Under a one-cell protocol, disjoint ± G_ss windows are confounded, and the verdict rests on the
    rest.
  - Under a symmetric protocol, the same data fail.
  - Disjoint tau_slow windows at every held-out magnitude leave the verdict undetermined (below the
    minimum judged set), with Part S scored beside it.
  - The confound depends on the observations, never on a prediction.
- **G9, Part S.** Decays at two magnitudes only leave FR-30's verdict undetermined, and Part S
  judges the steady list's held-out G_ss.
- **G10, the conventions.**
  - Revilla's fields at 30 s give §13.5's constants. T = 10 s gives the scaled grid.
  - Planted: no step duration, a reference_step without its voltage, and a window beyond the step
    are each refused.
- **G11, verify** recomputes predictions from their one block. Planted: a time moved by 1e-5
  relative.
- **G12, values never printed.** `check`, `resolve` (both roles; the wrong role refused) and `score`
  print no value, and a refusal names its key path. score.py imports the standard library only.

Cost: about 1.5 s on one CPU (host arithmetic, no world compiled), most of it two readouts of
10,001-sample traces in G11. Reason: the harness is registered code (D308), and these are its
claims.
"""

import ast
import copy
import json
import math
import sys
from pathlib import Path

import pytest

from cells.laws.junctions import junction_series_gates as series
from validation.junction_gate_benchmark import harness
from validation.junction_gate_benchmark import score as scorer

STEADY = scorer.STEADY
UNIT = {
    "tau_fast": "s",
    "tau_slow": "s",
    "A_fast": "fraction",
    "A_slow": "fraction",
    STEADY: "G/G_0",
}
DECAY = (40, 60, 80, 100, 120)
HELD = (60, 100)
PLANTED = 7.654321  # A value no output may print.


def truth(m, observable):
    """Invented, smooth in |V_j| (mV)."""
    tau_fast = 0.5 + 2.0 * math.exp(-m / 40)
    return {
        "tau_fast": tau_fast,
        "tau_slow": 10 * tau_fast,
        "A_fast": 0.6,
        STEADY: 0.3 + 0.7 / (1 + math.exp((m - 60) / 10)),
    }[observable]


def sem_of(observable, value):
    return {"tau_fast": 0.05 * value, "tau_slow": 0.05 * value, "A_fast": 0.02, STEADY: 0.01}[
        observable
    ]


def entry(vj, observable, value=None, *, polarity=None, dispersion="SEM"):
    """One invented entry in §13.7's layout."""
    m = abs(vj)
    value = truth(m, observable) if value is None else value
    units = UNIT[observable]
    disp = None
    if dispersion == "SEM":
        disp = {"type": "SEM", "value": sem_of(observable, value), "units": units}
    elif isinstance(dispersion, dict):
        disp = dispersion
    return {
        "id": f"inv-{observable}-{vj:+d}",
        "vj_mV": vj,
        "polarity": polarity or ("+" if vj > 0 else "-"),
        "observable": observable,
        "maps_to": observable,
        "value": value,
        "units": units,
        "normalization": None if observable in scorer.TIMES else "prepulse",
        "amplitude_definition": "of_decaying_part" if observable in scorer.AMPLITUDES else None,
        "dispersion": disp,
        "n": 6,
        "source": "invented",
        "method": "printed",
        "digitizing_error": None,
    }


def convention(kind="one_sided"):
    return {
        "paper_vj_definition": "invented: Vj = V1 - V2",
        "protocol_type": kind,
        "stepped_cell": None if kind == "symmetric" else "cell_1",
        "holding_mV": {"cell_1": -40, "cell_2": -40},
        "sign_map": "as_printed",
    }


def field(value=None, status="stated"):
    if status == "not_stated":
        return {"value": None, "status": status, "quote": None, "place": None, "how": None}
    return {"value": value, "status": status, "quote": "invented", "place": "invented",
            "how": "invented"}  # fmt: skip


def protocol(kind="one_sided", **changes):
    fields = {name: field(status="not_stated") for name in scorer.PROTOCOL_FIELDS}
    fields.update(step_duration_s=field(10.0), normalization=field("prepulse"),
                  prepulse_mV=field(10.0))  # fmt: skip
    fields.update(changes)
    return {"schema": scorer.PROTOCOL_SCHEMA, "role": "protocol", "paper": {},
            "convention": convention(kind), "fields": fields}  # fmt: skip


def documents(kind="one_sided", decay=DECAY, steady_only=(20,), edits=None):
    """(fit, held_out, protocol): invented, consistent with S0 to S5. edits maps (vj, observable) to
    a planted observation."""
    edits = edits or {}
    entries = []
    for m in decay:
        for s in (-1, 1):
            for o in ("tau_fast", "tau_slow", "A_fast", STEADY):
                entries.append(entry(s * m, o, edits.get((s * m, o))))
    for m in steady_only:
        for s in (-1, 1):
            entries.append(entry(s * m, STEADY, edits.get((s * m, STEADY))))
    probe = [scorer.read_entry(e, "probe") for e in entries]
    classes = scorer.classify(probe)
    held_out = {"decay_mV": scorer.rank_rule(classes["decay_list"]),
                "steady_mV": scorer.rank_rule(classes["steady_list"])}  # fmt: skip
    split = {"rule": scorer.SPLIT_RULE, "classes_mV": classes, "seen_mV": [], "held_out": held_out}
    held_set = set(held_out["decay_mV"]) | set(held_out["steady_mV"])
    common = {"registration": {}, "paper": {}, "arm": "invented", "convention": convention(kind),
              "split": split, "not_used": []}  # fmt: skip
    fit = {"schema": scorer.OBSERVATIONS_SCHEMA, "role": "train", **common, "withheld": [],
           "observables": [e for e in entries if abs(e["vj_mV"]) not in held_set]}  # fmt: skip
    held = {"schema": scorer.OBSERVATIONS_SCHEMA, "role": "held_out", **common,
            "withheld": [{"name": "a Boltzmann", "why": "fitted across the held-out voltages"}],
            "observables": [e for e in entries if abs(e["vj_mV"]) in held_set]}  # fmt: skip
    return fit, held, protocol(kind)


def predictions(magnitudes=HELD, changes=None):
    """An invented predictions document at both polarities of each magnitude, matching truth()."""
    rows = []
    for m in magnitudes:
        for s in (-1.0, 1.0):
            share = truth(m, "A_fast")
            row = {
                "vj_mV": s * m,
                "status": "predicted",
                "degenerate": False,
                "degenerate_reasons": [],
                "tau_fast_s": truth(m, "tau_fast"),
                "tau_slow_s": truth(m, "tau_slow"),
                "A_fast": 0.5 * share,
                "A_slow": 0.5 * (1 - share),
                "A_fast_share": share,
                "C": 0.5,
                "G_ss_over_G0": truth(m, STEADY),
            }
            for (v, key), value in (changes or {}).items():
                if v == s * m:
                    row[key] = value
            rows.append(row)
    return {"schema": scorer.PREDICTIONS_SCHEMA, "law": scorer.LAW_ID,
            "kinds": ["boltzmann_eyring", "boltzmann_eyring"], "parameters": [{}, {}],
            "predictions": rows}  # fmt: skip


def test_g1_the_passing_path_and_its_planted_errors():
    fit, held, proto = documents()
    summary = scorer.check(fit, held, proto)
    assert summary["held_out_mV"] == {"decay_mV": [60.0, 100.0], "steady_mV": []}
    assert summary["confounding_protocol"]
    result = scorer.score(predictions(), held, fit)
    assert result["verdict"] == "pass" and result["confounded"] == [] and result["part_s"] is None
    assert result["judged"] == 16 and result["passed"] == 16  # 4 voltages x 4 observables
    off = predictions(changes={(60.0, "G_ss_over_G0"): truth(60, STEADY) + 0.06})
    assert scorer.score(off, held, fit)["verdict"] == "fail"
    slow = {(v, "tau_slow_s"): 1.3 * truth(abs(v), "tau_slow") for v in (60.0, 100.0)}
    assert scorer.score(predictions(changes=slow), held, fit)["verdict"] == "fail"
    one = {(60.0, "tau_slow_s"): 1.3 * truth(60, "tau_slow")}
    assert scorer.score(predictions(changes=one), held, fit)["verdict"] == "pass"


def test_g2_an_object_of_named_lists_is_refused():
    fit, held, proto = documents()
    held["observables"] = {"times": held["observables"]}
    with pytest.raises(scorer.Refusal, match="observables: an object of named lists"):
        scorer.check(fit, held, proto)


@pytest.mark.parametrize(
    "dispersion, sem, note",
    [
        ({"type": "SD", "value": 0.4, "units": "s", "n": 4, "n_counts": "cell pairs"}, 0.2, "SD/"),
        ({"type": "SD", "value": 0.4, "units": "s", "n": 4}, None, "no widening"),
        ({"type": "SD", "value": 0.4, "units": "s", "n_counts": "cell pairs"}, None, "no widening"),
        ({"type": "range", "value": [1.0, 2.0], "units": "s"}, None, "no widening"),
        ({"type": "SEM", "value": 0.3, "units": "s"}, 0.3, "SEM"),
        (None, None, "base tolerance"),
    ],
)
def test_g3_an_sd_converts_only_with_n_and_what_it_counts(dispersion, sem, note):
    e = scorer.read_entry(entry(60, "tau_fast", 1.0, dispersion=dispersion), "e")
    assert (e["sem"] is None and sem is None) or math.isclose(e["sem"], sem)
    assert note in e["sem_note"]


def test_g4_a_training_entry_at_a_held_out_magnitude_is_refused():
    fit, held, proto = documents()
    fit["observables"].append(held["observables"].pop(0))
    with pytest.raises(scorer.Refusal, match="K5"):
        scorer.check(fit, held, proto)


def test_g5_the_split_is_recomputed_from_the_entries():
    fit, held, proto = documents()
    for doc in (fit, held):
        doc["split"]["held_out"]["decay_mV"] = [80.0]
    with pytest.raises(scorer.Refusal, match="split.held_out.decay_mV"):
        scorer.check(fit, held, proto)
    fit, held, proto = documents()
    held["split"] = copy.deepcopy(held["split"])
    held["split"]["seen_mV"] = [40.0]
    with pytest.raises(scorer.Refusal, match="split: the two files' blocks differ"):
        scorer.check(fit, held, proto)
    fit, held, proto = documents()
    fit["observables"].append(entry(140, "tau_fast"))
    with pytest.raises(scorer.Refusal, match="classes_mV.training_only"):
        scorer.check(fit, held, proto)
    for doc in (fit, held):
        doc["split"]["classes_mV"]["training_only"] = [140.0]
    assert scorer.check(fit, held, proto)["classes_mV"]["training_only"] == [140.0]


@pytest.mark.parametrize(
    "change, named",
    [
        ({"polarity": "+"}, "polarity"),
        ({"polarity": "pooled"}, "polarity"),
        ({"amplitude_definition": None}, "amplitude_definition"),
        ({"value": str(PLANTED)}, "value"),
    ],
)
def test_g6_the_entry_checks_name_key_paths_only(change, named):
    e = entry(-60, "A_fast")
    e.update(change)
    with pytest.raises(scorer.Refusal) as caught:
        scorer.read_entry(e, "observables[3]")
    assert named in str(caught.value) and "observables[3]" in str(caught.value)
    assert str(PLANTED) not in str(caught.value)


def test_g7_more_than_half():
    assert [scorer.more_than_half(k) for k in (2, 3, 4)] == [2, 2, 3]


def test_g8_the_one_cell_rule():
    edits = {(60, STEADY): truth(60, STEADY) - 0.15}  # +60's window lies below -60's
    fit, held, _ = documents("one_sided", edits=edits)
    result = scorer.score(predictions(), held, fit)
    assert sorted(result["confounded"]) == [[-60.0, STEADY], [60.0, STEADY]]
    assert result["verdict"] == "pass" and result["judged"] == 14
    moved = predictions(changes={(60.0, "G_ss_over_G0"): 0.0, (-60.0, "G_ss_over_G0"): 1.0})
    assert scorer.score(moved, held, fit)["confounded"] == result["confounded"]
    fit, held, _ = documents("symmetric", edits=edits)
    symmetric = scorer.score(predictions(), held, fit)
    assert symmetric["confounded"] == [] and symmetric["verdict"] == "fail"
    for kind in ("other", "not_stated"):
        assert kind in scorer.CONFOUNDING_PROTOCOLS
    slow = {(m, "tau_slow"): 1.6 * truth(m, "tau_slow") for m in HELD}
    fit, held, _ = documents("one_sided", edits=slow)
    below = scorer.score(predictions(), held, fit)
    assert below["verdict"] == "undetermined" and "minimum judged set" in below["verdict_basis"]
    assert below["part_s"]["verdict"] == "pass"


def test_g9_part_s_when_fr30s_verdict_is_undetermined():
    fit, held, proto = documents(decay=(40, 120), steady_only=(20, 60, 100))
    assert scorer.check(fit, held, proto)["held_out_mV"] == {"decay_mV": [], "steady_mV": [60.0]}
    result = scorer.score(predictions(magnitudes=(60,)), held, fit)
    assert result["verdict"] == "undetermined" and "structure" in result["verdict_basis"]
    assert result["part_s"]["verdict"] == "pass"
    off = predictions(magnitudes=(60,), changes={(60.0, "G_ss_over_G0"): truth(60, STEADY) + 0.1})
    assert scorer.score(off, held, fit)["part_s"]["verdict"] == "fail"


def test_g10_the_conventions():
    revilla = protocol(step_duration_s=field(30.0, "read"), prepulse_mV=field(10.0))
    values = harness.conventions(revilla)["values"]
    assert values["tau_fast_grid_ms"] == [50, 100, 200, 500, 1000, 2000]
    assert values["tau_slow_grid_ms"] == [1000, 2000, 5000, 10000, 20000, 50000]
    assert (values["step_ms"], values["gss_ms"], values["window_ms"]) == (30000, 30000, [5, 30000])
    assert (values["hold_mV"], values["prepulse_mV"], values["prepulse_ms"]) == (0.0, 10.0, 0)
    assert values["max_tau_slow_ms"] == 300000
    ten = harness.conventions(protocol())["values"]
    assert ten["tau_fast_grid_ms"] == [20, 50, 100, 200, 500]
    assert ten["tau_slow_grid_ms"] == [500, 1000, 2000, 5000, 10000]
    for plant, named in (
        ({"step_duration_s": field(status="not_stated")}, "no step duration"),
        ({"normalization": field("reference_step")}, "reference_mV"),
        ({"fit_window_s": field([0.005, 12.0])}, "fit_window_s"),
    ):
        with pytest.raises(scorer.Refusal, match=named):
            harness.conventions(protocol(**plant))


def test_g11_verify_recomputes_predictions_from_their_one_block():
    BE = series.BoltzmannEyring
    params = harness.LawParameters(
        ("boltzmann_eyring", "boltzmann_eyring"),
        (BE(4.0, 90.0, 0.045, 0.4, 0.45), BE(0.3, 70.0, 0.050, 0.6, 0.55)),
    )
    conv = harness.Conventions.from_json(harness.conventions(protocol()))
    doc = harness.predictions_document(params, conv, [-60.0, 60.0])
    assert harness.verify(doc, conv, [-60.0, 60.0])
    a, b = doc["predictions"]
    assert a["status"] == "predicted" and a["tau_slow_s"] == b["tau_slow_s"]  # symmetric in |V_j|
    tampered = copy.deepcopy(doc)
    tampered["predictions"][1]["tau_fast_s"] *= 1 + 1e-5
    with pytest.raises(scorer.Refusal, match=r"predictions\[1\].tau_fast_s"):
        harness.verify(tampered, conv, [-60.0, 60.0])


def test_g12_values_are_never_printed(tmp_path, capsys):
    fit, held, proto = documents(edits={(60, STEADY): PLANTED / 10})
    paths = {}
    for name, doc in (("fit", fit), ("held", held), ("proto", proto)):
        paths[name] = tmp_path / f"{name}.json"
        paths[name].write_text(json.dumps(doc))
    preds = tmp_path / "predictions.json"
    preds.write_text(json.dumps(predictions()))
    code = scorer.main(["check", str(paths["fit"]), str(paths["held"]), str(paths["proto"])])
    assert code == 0
    code = scorer.main(["score", str(preds), str(paths["held"]), str(paths["fit"]),
                        str(tmp_path / "verdict.json")])  # fmt: skip
    assert code == 0
    for name, role in (("fit", "train"), ("held", "held_out")):  # the checker's resolve stage
        assert scorer.main(["resolve", str(paths[name]), "--role", role]) == 0
    assert scorer.main(["resolve", str(paths["held"]), "--role", "train"]) == 2  # the wrong role
    out = capsys.readouterr()
    assert "+60 mV (+) G_ss/G_0: observables[" in out.out and "role: absent or not" in out.err
    assert str(PLANTED / 10)[:6] not in out.out + out.err
    held["observables"][0]["value"] = str(PLANTED)
    paths["held"].write_text(json.dumps(held))
    assert scorer.main(["check", str(paths["fit"]), str(paths["held"]), str(paths["proto"])]) == 2
    out = capsys.readouterr()
    assert "observables[0].value" in out.err and str(PLANTED) not in out.out + out.err
    tree = ast.parse(Path(scorer.__file__).read_text())
    imported = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import)
                for a in n.names} | {n.module.split(".")[0] for n in ast.walk(tree)
                                     if isinstance(n, ast.ImportFrom)}  # fmt: skip
    assert imported <= set(sys.stdlib_module_names)
