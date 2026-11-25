"""FR-30's harness for Revilla, Castro and Barrio (1999) at its tag (D308): the prediction, the
readout and the scorer (validation/junction_gate_benchmark/revilla1999.py and revilla1999_score.py;
docs/JUNCTION_TWO_RELAXATION_DESIGN.md §13.5), with the scorer's reader erratum 1 (§13.6).

Synthetic inputs only: invented gate parameters, invented decays and invented held-out documents in
the extractor's fit.json structure and in held_out.json's flat list. No training or held-out value
is used, and nothing is fitted to data. Each claim with the planted error it must catch:
- H1, the readout: an off-grid two-exponential decay's times, amplitudes and offset are recovered
  from the fixed grid's start, and G_ss/G_0 is the end-of-step sample, not the offset C (planted:
  a readout left on the grid would miss the off-grid times);
- H2, the prediction: the law's trace is the product of its gates' exact relaxations from their
  0-mV steady states, with G_0 that state's conductance; it is the same at both polarities, and
  outside the law's domain it cannot be predicted (planted: gates started open);
- H3, a time: a 30% error fails where 2 SEM is narrower, and the ln band is asymmetric (planted:
  +30% and -22% fail where +24% and -15% pass); a wide SEM rescues +30%, recorded as "2 SEM";
- H4, G_ss: off by 0.06 fails where 2 SEM is below 0.05 (planted), 0.04 passes by 0.05, a wide
  SEM rescues 0.06, recorded as "2 SEM", and no SEM leaves 0.05;
- H5, a degenerate predicted trace: a slow gate that never closes leaves one exponential, the fit
  is degenerate, and its times fail even where they match (planted); each criterion on its own;
- H6, the reader fails closed and names key paths only (planted: no observables, a missing key,
  entry or dispersion, a duplicate, a value as text, an SD, unknown units, a sign against its
  polarity); the command line withholds an error's text; the scorer imports the standard library
  only;
- H7, verify recomputes predictions.json from its one parameter block (planted: a time moved by
  1e-5 relative; a per-voltage parameter block);
- H8, reader erratum 1 (§13.6): held_out.json's one flat list of entries resolves to the same
  entries, at paths observables[i], and scores to the same comparisons as fit.json's object of
  named lists (planted: the tagged reader, which refused the flat list); in the flat list a
  malformed entry is refused by its path, and an "observables" of neither shape is refused, saying
  that the key is present.

Cost: about 5 s on one CPU (host arithmetic in NumPy and SciPy, no world compiled), most of it
importing the engine and seven readouts of 30,001-sample traces. Reason: the harness is registered
code (D308), and these are its claims.
"""

import ast
import copy
import json
import math
import sys
from pathlib import Path

import numpy as np
import pytest

from cells.laws.junctions import junction_series_gates as series
from validation import id_table
from validation.junction_gate_benchmark import revilla1999 as harness
from validation.junction_gate_benchmark import revilla1999_score as scorer

BE = series.BoltzmannEyring
KINDS = ("boltzmann_eyring", "boltzmann_eyring")
FAST = BE(rate_per_s=4.0, slope_per_V=90.0, midpoint_V=0.045, split=0.4, residual=0.45)
SLOW = BE(rate_per_s=0.3, slope_per_V=70.0, midpoint_V=0.050, split=0.6, residual=0.55)
PARAMS = harness.LawParameters(KINDS, (FAST, SLOW))
V = (-80, 80)
TIMES = {-80: (0.9, 9.0), 80: (1.1, 11.0)}  # Invented (tau_fast, tau_slow), s.
STEADY = {-80: 0.55, 80: 0.45}  # Invented G_ss/G_0.
STEADY_UNITS = "G/G(10-mV prepulse)"
PLANTED = 7.654321  # A value no refusal may print.


@pytest.fixture(autouse=True)
def _the_scorer_reads_the_law_by_the_engines_id(monkeypatch):
    """The frozen scorer keeps the ID it was tagged with; the harness writes the engine's."""
    monkeypatch.setattr(scorer, "LAW_ID", id_table.translate(scorer.LAW_ID))


def trace_of(y, g0=0.8):
    """A synthetic trace in predict's shape, from y(t) = g/G_0 on the protocol's grid."""
    t = harness.time_grid()
    return {
        "vj_mV": 0.0,
        "protocol": harness.PROTOCOL,
        "t_s": t,
        "g": g0 * y(t),
        "G0": g0,
        "domain": {},
        "in_domain": True,
        "gates": [],
    }


def held_out(sem_time=0.01, sem_steady=0.005):
    """An invented held-out document in fit.json's structure (lists under "observables")."""

    def sem(value, units):
        return None if value is None else {"type": "SEM", "value": value, "units": units}

    times = [
        {
            "id": f"synthetic-{o}-{v}",
            "vj_mV": v,
            "polarity": "-" if v < 0 else "+",
            "observable": o,
            "maps_to_registered_observable": m,
            "value": TIMES[v][j],
            "units": "s",
            "dispersion": sem(sem_time, "s"),
            "digitizing_error": 0.01,
            "digitizing_error_ln": 0.001,
        }
        for v in V
        for j, (o, m) in enumerate((("tau1", "tau_fast"), ("tau2", "tau_slow")))
    ]
    steady = [
        {
            "id": f"synthetic-Gjss-{v}",
            "vj_mV": v,
            "polarity": "-" if v < 0 else "+",
            "observable": "Gjss",
            "maps_to_registered_observable": "G_ss/G_0",
            "value": STEADY[v],
            "units": STEADY_UNITS,
            "dispersion": sem(sem_steady, STEADY_UNITS),
            "digitizing_error": 0.003,
        }
        for v in V
    ]
    ratio = {"id": "synthetic-ratio", "vj_mV": -80, "observable": "ratio", "value": 2, "units": "1"}
    return {
        "observables": {
            "time_constants_text": [ratio],
            "time_constants_fig3B": times,
            "steady_state_fig3C": steady,
        }
    }


def flat(doc):
    """The same document in held_out.json's structure (reader erratum 1): one flat list of entries
    under "observables", the named lists' entries in name order."""
    lists = doc["observables"]
    return {**doc, "observables": [e for name in sorted(lists) for e in lists[name]]}


def predictions(times=TIMES, steady=STEADY, degenerate=None):
    """A predictions document in the scorer's schema; by default it matches held_out() exactly."""
    entries = []
    for v in V:
        reasons = list((degenerate or {}).get(v, []))
        entries.append(
            {
                "vj_mV": float(v),
                "status": "predicted",
                "tau_fast_s": times[v][0],
                "tau_slow_s": times[v][1],
                "A_fast": 0.3,
                "A_slow": 0.2,
                "C": 0.5,
                "G_ss_over_G0": steady[v],
                "degenerate": bool(reasons),
                "degenerate_reasons": reasons,
            }
        )
    return {
        "schema": scorer.PREDICTIONS_SCHEMA,
        "law": series.LAW_ID,
        "kinds": list(KINDS),
        "parameters": PARAMS.to_json()["gates"],
        "predictions": entries,
    }


def comparison(result, v, observable):
    (found,) = [
        c for c in result["comparisons"] if (c["vj_mV"], c["observable"]) == (v, observable)
    ]
    return found


def test_the_readout_recovers_a_two_exponential_decay():
    r = harness.readout(
        trace_of(lambda t: 0.42 + 0.31 * np.exp(-t / 0.37) + 0.27 * np.exp(-t / 13.3))
    )
    assert r["status"] == "predicted" and r["degenerate_reasons"] == [] and r["samples"] == 29_996
    rule = harness.READOUT
    grid = [(f, s) for f in rule.tau_fast_grid_s for s in rule.tau_slow_grid_s if f < s]
    assert len(grid) == 33 and tuple(r["grid_start_s"]) in grid
    for key, value in (
        ("tau_fast_s", 0.37),
        ("tau_slow_s", 13.3),
        ("A_fast", 0.31),
        ("A_slow", 0.27),
        ("C", 0.42),
    ):
        assert r[key] == pytest.approx(value, rel=1e-9)
    end = 0.42 + 0.31 * math.exp(-30 / 0.37) + 0.27 * math.exp(-30 / 13.3)
    assert r["G_ss_over_G0"] == pytest.approx(end, rel=1e-12)
    assert r["G_ss_over_G0"] - r["C"] > 0.02  # The end-of-step sample, not the offset.


def test_the_prediction_is_the_laws_clamped_trace():
    trace = harness.predict(PARAMS, 70)
    t = trace["t_s"]
    assert (t.size, t[5], t[-1]) == (30_001, 0.005, 30.0)
    held = [float(r.target) for r in series.kinetics(0.0, PARAMS.gates, kinds=KINDS, xp=np)]
    step = series.kinetics(0.070, PARAMS.gates, kinds=KINDS, xp=np)
    gates = [
        s.target + (c - s.target) * np.exp(-s.relaxation_per_s * t)
        for c, s in zip(held, step, strict=True)
    ]
    np.testing.assert_allclose(trace["g"], gates[0] * gates[1], rtol=1e-13, atol=0)
    assert trace["G0"] == pytest.approx(held[0] * held[1], rel=1e-15) and trace["G0"] < 0.99
    r = harness.readout(trace)
    assert r["G_ss_over_G0"] == pytest.approx(gates[0][-1] * gates[1][-1] / trace["G0"], rel=1e-13)
    opened = [s.target + (1.0 - s.target) * np.exp(-s.relaxation_per_s * t) for s in step]
    assert np.max(np.abs(opened[0] * opened[1] - trace["g"])) > 1e-3  # Planted: gates open at 0.
    np.testing.assert_array_equal(harness.predict(PARAMS, -70)["g"], trace["g"])  # |V_j|
    outside = harness.readout(harness.predict(PARAMS, 130))  # Beyond the law's 120 mV.
    assert outside["status"] == "cannot_predict" and not outside["domain"]["step"]


def test_a_time_off_by_30_percent_fails_and_the_tolerance_used_is_recorded():
    base = scorer.score(predictions(), held_out())
    assert (base["verdict"], base["passed"], base["compared"]) == ("pass", 6, 6)

    def tau_fast_at_minus_80(factor, sem=0.01):
        times = {**TIMES, -80: (TIMES[-80][0] * factor, TIMES[-80][1])}
        result = scorer.score(predictions(times=times), held_out(sem_time=sem))
        return result, comparison(result, -80, "tau_fast")

    result, c = tau_fast_at_minus_80(1.30)  # Planted: 2 SEM (0.02 s) is narrower than 25%.
    assert (result["verdict"], result["passed"]) == ("fail", 5)
    assert (c["passes"], c["within_ln"], c["within_sem"], c["applied"], c["side"]) == (
        False,
        False,
        False,
        "ln 1.25",
        "above",
    )
    for factor, passes in ((1.24, True), (0.85, True), (0.78, False)):  # The band: -20%, +25%.
        assert tau_fast_at_minus_80(factor)[1]["passes"] is passes
    result, c = tau_fast_at_minus_80(1.30, sem=0.2)  # 2 SEM = 0.4 s, wider than 25% of 0.9 s.
    assert result["verdict"] == "pass"
    assert (c["within_ln"], c["within_sem"], c["applied"]) == (False, True, "2 SEM")
    result, c = tau_fast_at_minus_80(1.10, sem=None)  # No SEM: ln 1.25 alone.
    assert (c["passes"], c["within_sem"], c["applied"], c["sem"]) == (True, None, "ln 1.25", None)


def test_a_g_ss_off_by_0_06_fails_where_2_sem_is_below_0_05():
    def steady_at_plus_80(offset, sem=0.005):
        steady = {**STEADY, 80: STEADY[80] + offset}
        result = scorer.score(predictions(steady=steady), held_out(sem_steady=sem))
        return result, comparison(result, 80, "G_ss/G_0")

    result, c = steady_at_plus_80(0.06)  # Planted.
    assert result["verdict"] == "fail"
    assert (c["passes"], c["applied"], c["tolerance"]) == (False, "0.05", 0.05)
    assert steady_at_plus_80(-0.06)[1]["passes"] is False
    assert steady_at_plus_80(0.04)[1]["passes"] is True
    result, c = steady_at_plus_80(0.06, sem=0.04)  # 2 SEM = 0.08, wider than 0.05.
    assert result["verdict"] == "pass" and (c["passes"], c["applied"]) == (True, "2 SEM")
    result, c = steady_at_plus_80(0.04, sem=None)
    assert (c["passes"], c["applied"], c["sem"]) == (True, "0.05", None)


def test_a_degenerate_predicted_trace_fails_its_relaxation_comparisons():
    never = SLOW._replace(residual=1.0)  # A slow gate that never closes: one exponential.
    r = harness.readout(harness.predict(harness.LawParameters(KINDS, (FAST, never)), 70))
    assert r["status"] == "predicted" and r["degenerate"]
    assert any(
        reason.startswith(("A_fast below", "A_slow below", "tau_slow/tau_fast below"))
        for reason in r["degenerate_reasons"]
    )
    result = scorer.score(predictions(degenerate={80: r["degenerate_reasons"]}), held_out())
    assert (result["verdict"], result["passed"]) == ("fail", 4)  # Its times match, and still fail.
    for observable in ("tau_fast", "tau_slow"):
        c = comparison(result, 80, observable)
        assert not c["passes"] and c["reason"].startswith("degenerate fit: ")
    assert comparison(result, 80, "G_ss/G_0")["passes"]  # G_ss is still judged.


@pytest.mark.parametrize(
    "change, reason",
    [
        ({"tau_slow_s": 1.4}, "tau_slow/tau_fast below 1.5"),
        ({"A_fast": 5e-4}, "A_fast below 0.001"),
        ({"A_slow": -0.02}, "A_slow below 0.001"),  # Signed: a rising term is degenerate.
        ({"tau_slow_s": 301.0}, "tau_slow above 300 s"),
        ({"refinement": {"converged": False}}, "the refinement did not converge"),
        ({"C": math.nan}, "a fitted value is not finite, or a time not positive"),
    ],
)
def test_each_degenerate_criterion(change, reason):
    fit = {
        "tau_fast_s": 1.0,
        "tau_slow_s": 10.0,
        "A_fast": 0.3,
        "A_slow": 0.2,
        "C": 0.5,
        "refinement": {"converged": True},
    }
    assert harness.degenerate_reasons(fit) == []
    assert reason in harness.degenerate_reasons({**fit, **change})


def _entry(doc, group="time_constants_fig3B", index=0):
    return doc["observables"][group][index]


def _no_observables(doc):
    return {"held": doc["observables"]}


def _no_dispersion(doc):
    _entry(doc)["value"] = PLANTED
    del _entry(doc)["dispersion"]
    return doc


def _no_entry(doc):
    doc["observables"]["time_constants_fig3B"].pop()  # tau_slow at +80 mV.
    return doc


def _duplicate(doc):
    doc["observables"]["time_constants_text"].append({**_entry(doc), "value": PLANTED})
    return doc


def _text_value(doc):
    _entry(doc)["value"] = str(PLANTED)
    return doc


def _sd(doc):
    _entry(doc)["value"] = PLANTED
    _entry(doc)["dispersion"]["type"] = "SD"
    return doc


def _units(doc):
    _entry(doc)["value"] = PLANTED
    _entry(doc)["units"] = "min"
    return doc


def _polarity(doc):
    _entry(doc)["value"] = PLANTED
    _entry(doc)["polarity"] = "+"  # At -80 mV.
    return doc


def _dispersion_units(doc):
    _entry(doc)["dispersion"]["value"] = PLANTED
    _entry(doc)["dispersion"]["units"] = "ms"
    return doc


def _flat_sd(doc):  # held_out.json's flat list (erratum 1), its first entry with an SD.
    doc = flat(doc)
    doc["observables"][0]["value"] = PLANTED
    doc["observables"][0]["dispersion"]["type"] = "SD"
    return doc


def _observables_text(doc):  # The key is present, but its value has neither shape.
    return {**doc, "observables": str(PLANTED)}


@pytest.mark.parametrize(
    "plant, named",
    [
        (_no_observables, "top-level keys: ['held']"),
        (_no_dispersion, "observables.time_constants_fig3B[0]: no key 'dispersion'"),
        (_no_entry, "no entry for tau_slow at +80 mV"),
        (_duplicate, "two entries for tau_fast at -80 mV"),
        (_text_value, "observables.time_constants_fig3B[0].value: not a finite number"),
        (_sd, "observables.time_constants_fig3B[0].dispersion.type"),
        (_units, "observables.time_constants_fig3B[0].units"),
        (_polarity, "observables.time_constants_fig3B[0].polarity"),
        (_dispersion_units, "observables.time_constants_fig3B[0].dispersion.units"),
        (_flat_sd, "observables[0].dispersion.type"),
        (_observables_text, "observables: present, but neither an object of lists nor a list"),
    ],
)
def test_the_reader_fails_closed_naming_key_paths_only(plant, named):
    with pytest.raises(scorer.Refusal) as refused:
        scorer.score(predictions(), plant(copy.deepcopy(held_out())))
    assert named in str(refused.value) and str(PLANTED) not in str(refused.value)


def test_the_reader_takes_held_out_jsons_flat_list():
    grouped, listed = held_out(), flat(held_out())
    by_list = scorer.resolve(listed)
    assert sorted(e["path"] for e in by_list["entries"].values()) == [
        f"observables[{i}]" for i in range(6)
    ]
    assert (by_list["skipped"], by_list["outside"]) == (["observables[6]"], [])  # The ratio.

    def entries(resolved):
        return {
            k: {f: x for f, x in e.items() if f != "path"} for k, e in resolved["entries"].items()
        }

    assert len(entries(by_list)) == 6 and entries(by_list) == entries(scorer.resolve(grouped))
    by_groups, by_flat = (scorer.score(predictions(), doc) for doc in (grouped, listed))
    assert (by_flat["verdict"], by_flat["passed"], by_flat["compared"]) == ("pass", 6, 6)

    def comparisons(result):
        return [{k: x for k, x in c.items() if k != "held_out_path"} for c in result["comparisons"]]

    assert comparisons(by_flat) == comparisons(by_groups)


def test_the_command_line_withholds_values(tmp_path, capsys, monkeypatch):
    doc = tmp_path / "held_out.json"
    doc.write_text(json.dumps(_text_value(held_out())))
    assert scorer.main(["resolve", str(doc)]) == 2
    err = capsys.readouterr().err
    assert err.startswith("REFUSED: observables.") and str(PLANTED) not in err

    def leaks(*args, **kwargs):
        raise ValueError(f"a value {PLANTED}")

    monkeypatch.setattr(scorer, "resolve", leaks)  # Any other error: its type, never its text.
    assert scorer.main(["resolve", str(doc)]) == 3
    err = capsys.readouterr().err
    assert err.startswith("ERROR: ValueError, its message withheld") and str(PLANTED) not in err


def test_the_scorer_imports_the_standard_library_only():
    tree = ast.parse(Path(scorer.__file__).read_text())
    names = {
        a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names
    }
    names |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert names and names <= set(sys.stdlib_module_names)


def test_verify_recomputes_predictions_from_their_one_block():
    doc = json.loads(json.dumps(harness.predictions_document(PARAMS, (70,))))
    assert harness.verify(copy.deepcopy(doc))
    moved = copy.deepcopy(doc)
    moved["predictions"][0]["tau_slow_s"] *= 1 + 1e-5  # Planted.
    with pytest.raises(scorer.Refusal, match=r"predictions\[0\]\.tau_slow_s"):
        harness.verify(moved)
    own = copy.deepcopy(doc)
    own["predictions"][0]["parameters"] = doc["parameters"]  # Planted: a per-voltage block.
    with pytest.raises(scorer.Refusal, match="its own kinds or parameters"):
        harness.verify(own)
