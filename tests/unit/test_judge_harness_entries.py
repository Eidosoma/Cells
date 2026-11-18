"""The judges' harness at their judged entries (the external review's finding 4): the plants for the
wiring of 9a67ce89, 634bb80c and 189458c1.

- Each FR judge's main(["judged", ...]) on a judged results file whose evidence lacks one record is
  refused before any verdict is written: FR-6's A5'', FR-10, FR-3, FR-1, FR-4 and FR-5. The
  snapshot's own checks (compartment_ph_judge.refusal) are patched out; the merge's run here as
  registered.
- MG0c's judge (mg0c_turing.judge) and development values (mg0c_protocol.development_values) refuse
  an empty metric list before evaluate is called, and admit a non-empty one.
Without each entry's harness call, its test here fails.
"""

import json

import pytest

from tests.unit import test_judge_harness as th
from validation.tissue import compartment_ph_judge as base

SHA = "a" * 64


def fr45_parts(which):
    root = base.Path(base.__file__).resolve().parents[2]
    name = {"fr4": "fr4_acidification_v1.json", "fr5": "fr5_transfer_v1.json"}[which]
    protocol = json.loads((root / "validation" / "compartment_ph" / "protocols" / name).read_text())
    d = protocol["judge"]["derivation"]
    grid = [float(t) for t in range(0, 61)]
    if which == "fr4":
        worlds = {w: dict(record_s=list(grid)) for w in ("declared", "floor", "kinetic_outside")}
        names = [*d["ladder_parts"], d["declared_part"], d["half_part"], d["control_parts"][1]]
    else:
        worlds = {w: dict(record_s=list(grid)) for arm in d["arms"] for w in (arm, f"{arm}_floor")}
        names = [n for a in d["arms"].values()
                 for n in (*a["ladder_parts"], a["declared_part"], a["half_part"],
                           a["control_part"])]
    parts = {n: dict(kind="engine", record_s=list(grid)) for n in names}
    parts["reference"] = dict(worlds=worlds)
    if which == "fr5":  # FR-5's merge: every part on the extract its start part wrote.
        for part in parts.values():
            part["start"] = dict(extract_sha256=SHA)
        parts["start"] = dict(extract_sha256=SHA)
    return protocol, parts, names[0]


def cases():
    from validation.tissue import a5pp_acceptance_judge as a5pp
    from validation.tissue import bath_schedule_judge as fr10

    def a5pp_case():
        parts, protocol = th.a5pp_parts()
        return a5pp, protocol, parts, "a5pp_rung_0p5ms", "record_ms"

    def fr10_case():
        protocol, parts = th.fr10_complete()
        return fr10, protocol, parts, "W2_rung_0p5ms", "record_s"

    def fr1_case():
        module, protocol, parts = th.fr1_complete()
        return module, protocol, parts, "C6_rung_0p5ms", "record_s"

    def fr3_case():
        module, protocol, parts = th.fr3_complete()
        return module, protocol, parts, "q1_fast_rung_0p25ms", "record_ms"

    def fr45_case(which):
        protocol, parts, victim = fr45_parts(which)
        return base, protocol, parts, victim, "record_s"

    return {"fr6_a5pp": a5pp_case, "fr10": fr10_case, "fr1": fr1_case, "fr3": fr3_case,
            "fr4": lambda: fr45_case("fr4"), "fr5": lambda: fr45_case("fr5")}


@pytest.mark.parametrize("which", sorted(cases()))
def test_a_judged_entry_refuses_a_dropped_record(which, tmp_path, monkeypatch):
    module, protocol, parts, victim, key = cases()[which]()
    assert module.incomplete(parts, protocol) == []  # Complete evidence passes the check.
    record = dict(parts[victim])
    record[key] = record[key][:5] + record[key][6:]
    parts[victim] = record
    results = tmp_path / "results.json"
    results.write_text(json.dumps(dict(
        protocol_id=protocol["id"], status="Judged run of " + protocol["id"], complete=True,
        requested_parts=sorted(parts), parts=parts, source=dict(git_revision="snapshot"))))
    path = tmp_path / "protocol.json"
    path.write_text(json.dumps(protocol))
    monkeypatch.setattr(base, "refusal", lambda protocol, results_list, out_dir: None)
    with pytest.raises(SystemExit, match=f"incomplete evidence.*{victim}"):
        module.main(["judged", str(path), str(tmp_path / "verdict"), str(results)])
    assert not (tmp_path / "verdict").exists()


# ------------------------------------------------------------------------------------- MG0c


PROTOCOL = dict(id="mg0c-test", status="registered (a test)", judged_parts=["p"], criteria=[
    dict(id="c", metrics=["parts.p.values"], comparison="le", threshold=1.0, judged=True)])


def test_mg0c_development_values_refuse_an_empty_metric():
    from validation.morphogenesis import mg0c_protocol

    out = mg0c_protocol.development_values(PROTOCOL, dict(parts=dict(p=dict(values=[0.5]))))
    assert out["c"]["passed"] is True
    with pytest.raises(SystemExit, match="incomplete evidence.*parts.p.values"):
        mg0c_protocol.development_values(PROTOCOL, dict(parts=dict(p=dict(values=[]))))


@pytest.mark.parametrize("values, refused", [([0.5], False), ([], True)])
def test_mg0c_judge_refuses_an_empty_metric_before_evaluate(values, refused, tmp_path,
                                                            monkeypatch):
    from validation.morphogenesis import mg0c_turing

    monkeypatch.setattr(mg0c_turing, "registered", lambda path, output, root: PROTOCOL)
    monkeypatch.setattr(mg0c_turing, "snapshot_identity", lambda root: dict(git_revision="s"))
    monkeypatch.setattr(mg0c_turing, "accounting_summary", lambda results: {})
    results = tmp_path / "results.json"
    results.write_text(json.dumps(dict(
        status="Judged run of " + PROTOCOL["id"], source=dict(git_revision="s"), complete=True,
        requested_parts=["p"], parts=dict(p=dict(values=values)))))
    output = tmp_path / "verdict"
    if refused:
        with pytest.raises(SystemExit, match="incomplete evidence"):
            mg0c_turing.judge("protocol.json", output, [str(results)], root=tmp_path)
        assert not output.exists()
    else:
        try:
            mg0c_turing.judge("protocol.json", output, [str(results)], root=tmp_path)
        except SystemExit as refusal:  # Past the guard, the judge's own steps may refuse.
            assert "incomplete evidence" not in str(refusal)
