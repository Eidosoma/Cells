"""FR-45's judge (validation/fr45/judge.py) on hand-built fragments: one pass row and one fail row for each class of
pair, the identity checks and the faults' scope, the plants' rules, the echo's comparison and the references' reads
(TABLE §1, §4.1, §8.2, §10, §11, §12.1, §12.3).

Seconds and reason (D224): 1 s measured cold on one timed core (tier 1), pure Python, no engine; the judge is loaded by its path, as it loads
agreement.py, so no package's __init__ is imported. Self-contained fragments only (the lead's ruling 5c): no file of
the binding tag is read, and G is a stand-in (ruling 6).
"""

import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


J = _load("fr45_judge_under_test", ROOT / "validation" / "fr45" / "judge.py")
AGREEMENT = J.load_by_path(
    "fr45_agreement_under_test", ROOT / "validation" / "assembly_lineages_v2" / "agreement.py"
)
EPS = 2.0**-52


def stand_in_g(world, node, amounts):
    """A stand-in G (ruling 6): minus the sum of the node's amounts, enough to route C3b."""
    return -sum(amounts.values())


REG = dict(
    runs={"W1": dict(world="W1", plant=None, dt_s=0.1), "W1-P1": dict(world="W1", plant="P1", dt_s=0.1)},
    rows={"W1": {"0.1": [[0.0, 0], [0.2, 2]]}}, wash={}, maps={}, files={"W1": "W1"}, heat_nodes={"W1": ["pond"]},
    operators={"W1": list(J.BASE_OPERATORS)}, plants=[["P1", "C1", "W1", None]],
)  # fmt: skip
INPUTS = dict(
    world="INVENTED-W1", constants=dict(sites_per_fmol=1.0, temperature_K=300.0, RT_pJ_per_fmol=2.5),
    nodes=[dict(id="pond", kind="node", volume_pL=2.0, registered=True)], patches=[], ligands=["X"],
    free_amounts=[dict(ligand="X", node="pond", n_fmol=1.0, declared=True)],
    sets=[dict(id="s", shared=False, owner="pond", face=None, faces="pond", copies=1.0, sites_per_copy=1,
               accessible_fraction=1.0)],
    populations=[dict(id="b", set="s", ligand="X", k_on=1.0, k_off=1.0, initial_occupancy=0.0)], wash=None,
    permeabilities=[], ion_permeabilities={}, multipliers=[dict(of="b", name="site_binding_multiplier", value=1.0)],
    charges={"X": 0}, capacitor_components=[], host_values=dict(areas={}, capacitances={}, ion_amounts={}),
    dt_s=0.1, observation_times_s=[0.2], horizon_s=0.2,
)  # fmt: skip
SOURCE = dict(engine_revision="a" * 40, checkout_dirty=False, snapshot="snap", snapshot_patch_sha256="0" * 64,
              python="3", numpy="2", scipy="1", jax="0", jaxlib="0", jax_enable_x64=True, jax_platforms="cpu",
              blas_threads=1, machine="x86_64", external_modules=[])  # fmt: skip


def row(step, t, n=1.0, B=0.25, R=0.75, heat=0.0, theta=0.25):
    return dict(step=step, time_s=t, amounts={"n:X@pond": n, "B:b": B, "R:s": R}, records={},
                site_heat_pJ={"pond": heat}, site_occupied_fraction={"b": theta})  # fmt: skip


def run(**changes):
    entry = dict(status="completed", world="INVENTED-W1", plant=None, dt_s=0.1, steps=2, backend="compiled",
                 driver=dict(window_steps=1), rows=[row(0, 0.0), row(2, 0.2, heat=0.5)], capacities={"s": 1.0},
                 free_sites={"s": "state"}, events=[], event_map=[], step_report=None, refusal=None,
                 checks={"energy": dict(failures=[])}, operators=list(J.BASE_OPERATORS), inputs=copy.deepcopy(INPUTS),
                 definition=dict(execution=dict(solver=J.SOLVER, dt=0.1, jit=True, backend="cpu")),
                 source=dict(SOURCE), record="records/x.json", record_sha256="0" * 64)  # fmt: skip
    entry.update(changes)
    return entry


def plant_run(**changes):
    plant = dict(id="P1", patch="validation/fr45/plants/p1.py", change="x", inputs_changed=[])
    return run(plant=plant, **changes)


def reference(*pairs):
    world = dict(dt=0.1, observation_times=[0.2], horizon=0.2, sets=[dict(id="s", faces="pond", S=1.0)],
                 populations=[dict(id="b", set="s", ligand="X", k_on=1.0, k_off=1.0)],
                 nodes=[dict(id="pond", kind="node", V=2.0)],
                 start=[dict(observable=o, value=v) for o, v in (("n:X@pond", 1.0), ("B:b", 0.0), ("R:s", 1.0))],
                 constants={})  # fmt: skip
    trajectory = [dict(observable=o, time_s=0.2, value=v, tolerance_gap=0.0)
                  for o, v in (("n:X@pond", 1.0), ("B:b", 0.25), ("R:s", 0.75))]  # fmt: skip
    return dict(world=world, pairs=list(pairs), trajectory=trajectory, plants=[])


def pair(criterion, observable, value=None, tolerance=None, time_s=0.2, **extra):
    cls = extra.pop("cls", "band")
    return dict(criterion=criterion, observable=observable, time_s=time_s, value=value, tolerance=tolerance,
                **{"class": cls}, **extra)  # fmt: skip


def env_of(runs, *pairs):
    table = dict(kind=J.KIND_TABLE, protocol=J.PROTOCOL, units=dict(J.UNITS), missing=[],
                 runs={f"INVENTED-{n}": r for n, r in runs.items()})  # fmt: skip
    env = J.Env(
        table, {"W1": reference(*pairs)}, J.Registration(REG, "INVENTED-"), AGREEMENT, stand_in_g
    )
    J.identity(env)
    return env


def verdict(p, entry):
    return J.evaluate(env_of({"W1": entry}, p), "W1", p, "W1")


def test_the_fragment_is_a_clean_registered_run():
    assert env_of({"W1": run(), "W1-P1": plant_run()}).faults == []


ROWS = {
    "C1 band within": (pair("C1", "n:X@pond", 1.0 + 1e-7, 1e-6), run(), True),
    "C1 band beyond": (pair("C1", "n:X@pond", 1.0 + 1e-5, 1e-6), run(), False),
    "C1 a null engine value is not formed": (
        pair("C1", "n:X@pond", 1.0, 1e-6),
        run(rows=[row(0, 0.0), row(2, 0.2, n=None)]),
        False,
    ),  # fmt: skip
    "C2b derived within": (pair("C2b", "B:b", 0.25, 1e-15, cls="derived"), run(), True),
    "C2b derived beyond": (pair("C2b", "B:b", 0.25 + 1e-12, 1e-15, cls="derived"), run(), False),
    "C3a heat within": (pair("C3a", "H:pond", 0.5, 1e-9, start_s=0.0, end_s=0.2), run(), True),
    "C3a heat beyond": (pair("C3a", "H:pond", 0.6, 1e-9, start_s=0.0, end_s=0.2), run(), False),
    "C3b against -dG": (
        pair("C3b", "H:pond", None, 1e-12, cls="derived", start_s=0.0, end_s=0.2),
        run(rows=[row(0, 0.0), row(2, 0.2, n=1.5, heat=0.5)]),
        True,
    ),  # fmt: skip
    "C3b a heat off -dG": (
        pair("C3b", "H:pond", None, 1e-12, cls="derived", start_s=0.0, end_s=0.2),
        run(),
        False,
    ),
    "C3c a rise passes": (
        pair(
            "C3c", "cumulative_site_heat:pond", None, 1e-15, cls="derived", start_s=0.0, end_s=0.2
        ),
        run(),
        True,
    ),  # fmt: skip
    "C3c a fall fails": (
        pair(
            "C3c", "cumulative_site_heat:pond", None, 1e-15, cls="derived", start_s=0.0, end_s=0.2
        ),
        run(rows=[row(0, 0.0, heat=1.0), row(2, 0.2, heat=0.5)]),
        False,
    ),  # fmt: skip
    "C4a books close": (pair("C4a", "books:X@pond", 1.25, 1e-15, cls="derived"), run(), True),
    "C4a books open": (pair("C4a", "books:X@pond", 1.3, 1e-15, cls="derived"), run(), False),
    "C5 moiety holds": (pair("C5", "sites:s", 1.0, 1e-15, cls="derived"), run(), True),
    "C5 moiety departs": (
        pair("C5", "sites:s", 1.0, 1e-15, cls="derived"),
        run(rows=[row(0, 0.0), row(2, 0.2, R=0.8)]),
        False,
    ),  # fmt: skip
    "C9 theta within its terms": (
        pair("C9", "theta:b", cls="derived", tolerance_terms=dict(eps_term=4 * EPS)),
        run(),
        True,
    ),  # fmt: skip
    "C9 theta as B/(B+R) of a departed moiety": (
        pair("C9", "theta:b", cls="derived", tolerance_terms=dict(eps_term=4 * EPS)),
        run(rows=[row(0, 0.0), row(2, 0.2, theta=0.3)]),
        False,
    ),
    "C1 a time the registration lacks is not formed": (
        pair("C1", "n:X@pond", 1.0, 1e-6, time_s=0.3),
        run(),
        False,
    ),
}


@pytest.mark.parametrize("name", sorted(ROWS))
def test_each_class_passes_and_fails_as_written(name):
    p, entry, passes = ROWS[name]
    result = verdict(p, entry)
    assert (result.get("passes") is True) is passes, result


def _map(before, after, f=0.5, variant="numpy"):
    return dict(state_step=1, variant=variant, node="pond", fraction=f, buffer_mM={"X": 0.25},
                before=dict(amounts=before, records={"X@pond": dict(collected=0.0, supplied=0.0)}),
                after=dict(amounts=after, records={"X@pond": dict(collected=f * before["n:X@pond"],
                                                                   supplied=f * 2.0 * 0.25)}))  # fmt: skip


@pytest.mark.parametrize("honest", [True, False], ids=["the map", "a planted map"])
def test_c4b_and_c6_read_both_variants_of_the_map(honest):
    before = {"n:X@pond": 1.0, "B:b": 0.25, "R:s": 0.75}
    after = {
        "n:X@pond": 0.5 * 1.0 + 0.5 * 2.0 * 0.25,
        "B:b": 0.25 if honest else 0.125,
        "R:s": 0.75,
    }
    maps = [_map(before, after, variant=v) for v in ("numpy", "compiled")]
    rows = [row(0, 0.0), dict(row(1, 0.1), amounts=before), row(2, 0.2)]
    reg = copy.deepcopy(REG)
    reg["rows"]["W1"]["0.1"] = [[0.0, 0], [0.1, 1], [0.2, 2]]
    entry = run(event_map=maps, rows=rows)
    table = dict(
        kind=J.KIND_TABLE,
        protocol=J.PROTOCOL,
        units=dict(J.UNITS),
        missing=[],
        runs={"INVENTED-W1": entry},
    )
    env = J.Env(table, {"W1": reference()}, J.Registration(reg, "INVENTED-"), AGREEMENT, stand_in_g)
    c4b = pair(
        "C4b",
        "n:X@pond",
        time_s=0.1,
        cls="derived",
        tolerance_terms=dict(eps_factor=4 * EPS, f_V_c_buf=0.25),
    )
    removed = pair(
        "C4b", "removed:X@pond", time_s=0.1, cls="derived", tolerance_terms=dict(eps_factor=2 * EPS)
    )
    c6 = pair("C6", "B:b", "unchanged", None, time_s=0.1, cls="constant")
    assert (
        J.evaluate(env, "W1", c4b, "W1")["passes"]
        and J.evaluate(env, "W1", removed, "W1")["passes"]
    )
    assert J.evaluate(env, "W1", c6, "W1")["passes"] is honest
    entry["event_map"] = maps[:1]
    assert "unformed" in J.evaluate(env, "W1", c6, "W1")


@pytest.mark.parametrize(
    "change, item, touches_c1",
    [(dict(dt_s=0.2), 2, True), (dict(backend="numpy"), 2, True), (dict(record_sha256="x"), 12, True),
     (dict(driver=dict(window_steps=2)), 14, True), (dict(capacities={"s": 1.5}), 4, True),
     (dict(source=dict(SOURCE, checkout_dirty=True)), 11, True), (dict(operators=["x"]), 9, True),
     (dict(rows=[row(0, 0.0), row(2, 0.2 + 1e-9)]), 3, True),
     (dict(events=[dict(kind="wash")]), 5, False)],
)  # fmt: skip
def test_a_fault_touches_the_entries_that_read_its_key(change, item, touches_c1):
    env = env_of({"W1": run(**change)}, pair("C1", "n:X@pond", 1.0, 1e-6))
    assert item in {f["item"] for f in env.faults}, env.faults
    result = J.evaluate(env, "W1", pair("C1", "n:X@pond", 1.0, 1e-6), "W1")
    assert ("fault" in result) is touches_c1


def test_a_top_level_fault_touches_every_entry():
    env = env_of({"W1": run()})
    env.table["units"] = {}
    env.faults.clear()
    J.identity(env)
    assert any(f["run"] is None for f in env.faults)
    assert "fault" in J.evaluate(env, "W1", pair("C1", "n:X@pond", 1.0, 1e-6), "W1")


@pytest.mark.parametrize(
    "refusal, expected",
    [
        (
            dict(raised="cells.execution.errors.NumericalError", name="site_moiety_entity"),
            ("check", "moiety ledger"),
        ),
        (
            dict(raised="cells.execution.errors.NumericalError", name="energy"),
            ("check", "energy ledger"),
        ),
        (
            dict(raised="cells.execution.errors.NumericalError", name="dissipation"),
            ("check", "dissipation check"),
        ),
        (
            dict(raised="cells.execution.errors.NumericalError", name="outside"),
            ("check", "host check: outside"),
        ),
        (
            dict(raised="cells.execution.errors.NumericalError", name="stage condition"),
            ("stage", None),
        ),
        (
            dict(raised="cells.execution.errors.NumericalError", name="solver domain"),
            ("domain", None),
        ),
        (
            dict(
                raised="cells.definitions.specs.ConfigError",
                name="initial occupancies over 1 on a set",
            ),
            ("domain", None),
        ),
        (
            dict(
                raised="cells.definitions.specs.ConfigError",
                name="a set named by fewer than two populations",
            ),
            ("definition", None),
        ),
        (dict(raised=None, name="driver time limit"), ("harness", None)),
    ],
)
def test_the_judges_own_refusal_mapping(refusal, expected):
    assert J.mapped(refusal) == expected


MOIETY = dict(kind="check", raised="cells.execution.errors.NumericalError", book="moiety ledger",
              name="site_moiety_entity", message="", step=2, time_s=0.1)  # fmt: skip


@pytest.mark.parametrize(
    "planted, honest, caught",
    [(dict(rows=[row(0, 0.0), row(2, 0.2, n=1.5)]), {}, True),
     (dict(), {}, False),
     (dict(rows=[row(0, 0.0), row(2, 0.2, n=1.5)]), dict(rows=[row(0, 0.0), row(2, 0.2, n=1.5)]), False),
     (dict(status="refused", refusal=MOIETY, steps=1, rows=[row(0, 0.0)]), {}, True),
     (dict(status="refused", refusal=MOIETY, steps=1, rows=[row(0, 0.0)]),
      dict(status="refused", refusal=MOIETY, steps=1, rows=[row(0, 0.0)]), False),
     (dict(status="refused", refusal=dict(MOIETY, kind="stage", name="stage condition", book=None), steps=1,
           rows=[row(0, 0.0)]), {}, False),
     (dict(rows=[row(0, 0.0), row(2, 0.2, n=1.5)], dt_s=0.2), {}, False),
     (dict(status="refused", refusal=MOIETY, steps=1, rows=[row(0, 0.0)]), dict(driver=dict(window_steps=2)),
      False)],
    ids=["fails with a passing baseline", "no fail", "a failed baseline", "a check refusal",
         "a check refusal with the honest run refused", "a stage refusal", "a fault on the plant run",
         "a check refusal with a fault on the honest run"],
)  # fmt: skip
def test_a_plant_is_caught_by_section_8_2(planted, honest, caught):
    env = env_of(
        {"W1": run(**honest), "W1-P1": plant_run(**planted)}, pair("C1", "n:X@pond", 1.0, 1e-6)
    )
    assert J.judge_plants(env)["P1"]["caught"] is caught


def test_p4_is_caught_by_its_verdict_alone_and_a_null_forms_nothing():
    report = dict(step=1, h_s=0.05, loads=[dict(kind="L_R", id="s", sums=["b"], per_s=12.0)], limit=0.5,
                  h_max_load=0.6, verdict="refused")  # fmt: skip
    report["max_load"] = report["loads"][0]
    stage = dict(kind="stage", raised="cells.execution.errors.NumericalError", book=None, name="stage condition",
                 message="", step=1, time_s=0.0)  # fmt: skip
    reg = copy.deepcopy(REG)
    reg.update(runs={"W5": dict(world="W5", plant=None, dt_s=0.1), "W5-P4": dict(world="W5", plant="P4", dt_s=0.1)},
               rows={"W5": {"0.1": [[0.0, 0], [1.0, 10]]}}, files={"W5": "W5"}, heat_nodes={"W5": ["pond"]},
               operators={"W5": list(J.BASE_OPERATORS)}, plants=[["P4", "C7", "W5", None]])  # fmt: skip
    honest = run(world="INVENTED-W5", status="refused", refusal=stage, steps=0, step_report=report,
                 rows=[row(0, 0.0)])  # fmt: skip
    admitted = dict(report, h_max_load=0.3, verdict="admitted")
    for planted, caught in (
        (admitted, True),
        (dict(admitted, h_max_load=None), False),
        (report, False),
    ):
        p4 = dict(honest, plant=dict(id="P4", patch="validation/fr45/plants/p4.py", change="x", inputs_changed=[]),
                  step_report=planted)  # fmt: skip
        table = dict(kind=J.KIND_TABLE, protocol=J.PROTOCOL, units=dict(J.UNITS), missing=[],
                     runs={"INVENTED-W5": honest, "INVENTED-W5-P4": p4})  # fmt: skip
        ref = reference(pair("C7", "stage:first_step", "refused", None, time_s=0.0, cls="constant"))
        env = J.Env(table, {"W5": ref}, J.Registration(reg, "INVENTED-"), AGREEMENT, stand_in_g)
        J.identity(env)
        assert not [f for f in env.faults if f["run"] == "W5"], env.faults
        assert J.judge_plants(env)["P4"]["caught"] is caught


def test_c10_reads_status_rows_and_checks():
    env = env_of({"W1": run()})
    assert J._c10(env, "W1")["passes"]
    env = env_of({"W1": run(checks={"energy": dict(failures=[dict(step=1, message="x")])})})
    assert not J._c10(env, "W1")["passes"]
    assert not J._c10(env_of({}), "W1")["passes"]


def test_the_echo_compares_numbers_as_binary64_and_lists_as_sets():
    markers = dict(trace="trace marker", volume="volume marker", host_values="host marker")
    want = copy.deepcopy(INPUTS)
    want["constants"].update(sites_per_fmol=1, RT_pJ_per_fmol=None)
    want["nodes"].append(dict(id="bath", kind="node", volume_pL="volume marker", registered=False))
    want["free_amounts"].append(
        dict(ligand="X", node="bath", n_fmol="trace marker", declared=False)
    )
    got = copy.deepcopy(INPUTS)
    got["nodes"].insert(0, dict(id="bath", kind="node", volume_pL=140.0, registered=False))
    got["free_amounts"].append(dict(ligand="X", node="bath", n_fmol=1e-12 * 140.0, declared=False))
    result = J.Echo(markers).compare(got, want)
    assert result.departures == [] and result.unchecked
    got["free_amounts"][-1]["n_fmol"] = 1.4e-10 * 1.5
    got["populations"][0]["k_on"] = 2.0
    assert len(J.Echo(markers).compare(got, want).departures) == 2


def _echoed_reference():
    ref = reference(pair("C1", "n:X@pond", 1.0, 1e-6, against="r"))
    ref["world"].update(constants=dict(N_f_sites_per_fmol=1.0, T_K=300.0), ligands=["X"],
                        free_amounts=[dict(ligand="X", node="pond", n=1.0, declared=True)],
                        sets=[dict(id="s", faces="pond", copies=1.0, sites_per_copy=1, accessible_fraction=1.0)],
                        populations=[dict(id="b", set="s", ligand="X", faces="pond", k_on=1.0, k_off=1.0,
                                          initial_occupancy=0.0)])  # fmt: skip
    return ref


def test_the_cross_check_and_the_references_structure_report_departures():
    reg = J.Registration(REG, "INVENTED-")
    want = copy.deepcopy(INPUTS)
    ref = _echoed_reference()
    assert J.cross_check(dict(runs={"W1": want}), {"W1": ref}, reg) == []
    want["populations"][0]["k_off"] = 2.0
    assert len(J.cross_check(dict(runs={"W1": want}), {"W1": ref}, reg)) == 1
    ref.update(schema="x", invented=True, units={}, equilibrium={}, balances={}, heats={}, spread="none",
               spread_note="", distance_at_horizon={}, provenance={})  # fmt: skip
    ref["plants"] = [dict(plant="P1", criterion="C1", world="W1", time_s=None, compared={})]
    assert J.reference_structure({"W1": ref}, reg, True) == []
    ref["pairs"].append(pair("C1", "speed:X", 1.0, 1e-6, against="r"))
    assert len(J.reference_structure({"W1": ref}, reg, True)) == 1
    found = J.invented_file_structure(
        ref
    )  # The file the judge reads first must hold every census form.
    assert (
        any("speed:X" in f for f in found)
        and sum("is not in the invented file" in f for f in found) == 18
    )


def test_the_files_are_read_strictly(tmp_path):
    (tmp_path / "a.json").write_text('{"x": NaN}')
    (tmp_path / "b.json").write_text('{"x": 1, "x": 2}')
    for name in ("a.json", "b.json"):
        with pytest.raises(ValueError):
            J.strict_load(tmp_path / name)
    (tmp_path / "table.json").write_text("{}")
    (tmp_path / "SHA256SUMS").write_text("0" * 64 + "  table.json\n")
    assert J.table_sha256(tmp_path)[1] == ["SHA256SUMS is not the one line of table.json's sha256"]
    assert J.git_blob(b"") == "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391"
    assert J.check_blobs({"a": "1", "b": "2"}, {"a": "1", "c": "3"}) == {
        "b": ("2", None),
        "c": (None, "3"),
    }


def test_the_tags_blobs_are_gits_own(tmp_path):
    import subprocess

    def git(*args):
        subprocess.run(["git", "-C", str(tmp_path), *args], check=True, capture_output=True)

    (tmp_path / "refs").mkdir()
    (tmp_path / "refs" / "a.json").write_bytes(b'{"a": 1}\n')
    git("init", "-q")
    git("add", "refs/a.json")
    git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "t")
    git("tag", "binding")
    assert J.tag_blobs(tmp_path, "binding", ["refs"]) == {"refs/a.json": J.git_blob(b'{"a": 1}\n')}


def test_the_registered_rows_are_the_tables_integers():
    reg = J.Registration(J.REGISTERED)
    for world, by_dt in J.REGISTERED["rows"].items():
        for dt, rows in by_dt.items():
            assert all(k == round(t / float(dt)) for t, k in rows), world
    assert set(reg.rows("W3p", 0.004)) <= set(reg.rows("W3", 0.004))
    assert {s["world"] for s in J.REGISTERED["runs"].values()} == set(J.REGISTERED["rows"])
    assert {tuple(e) for e in J.REGISTERED["plants"]} >= {
        ("P5", "C6", "W7", 0.0),
        ("P5", "C6", "W7", 1.0),
    }
    assert json.loads(json.dumps(J.REGISTERED)) == J.REGISTERED


def test_the_plant_rule_applies_declared_changes_and_finds_others():
    honest = run(definition=dict(model=dict(operators=[dict(law="cells.operator.site_occupancy@1", populations=[
        dict(id="b", dissociation_rate_per_s=1.0)])])))  # fmt: skip
    plant = copy.deepcopy(honest)
    plant["plant"] = dict(id="P2", patch="validation/fr45/plants/p2.py", change="x",
                          inputs_changed=["populations[id=b].k_off"])  # fmt: skip
    plant["inputs"]["populations"][0]["k_off"] = 2.0
    plant["definition"]["model"]["operators"][0]["populations"][0]["dissociation_rate_per_s"] = 2.0
    table = dict(runs={"INVENTED-W1": honest, "INVENTED-W1-P2": plant})
    assert J.plant_rule(table)["departures"] == 0
    plant["dt_s"] = 0.05
    assert J.plant_rule(table)["runs"]["INVENTED-W1-P2"]["departures"] == ["dt_s"]


def test_the_structural_comparison_finds_types_and_lost_keys():
    table = dict(kind="k", runs={"A": run(), "B": run()}, missing=[], units={})
    assert J.compare(table, table)["identical"]
    other = copy.deepcopy(table)
    other["runs"]["A"]["steps"] = 2.0
    assert "runs.<key>.steps" in J.compare(other, table)["types"]
    lost = copy.deepcopy(table)
    del lost["runs"]["B"]["rows"][0]["records"]
    assert J.compare(lost, table)["keys"]


def test_steps_1_to_3_run_without_a_table_and_a_registered_judgement_needs_its_owed_inputs(
    tmp_path,
):
    ref = _echoed_reference()
    ref.update(schema="x", invented=True, units={}, equilibrium={}, balances={}, heats={}, spread="none",
               spread_note="", distance_at_horizon={}, provenance={})  # fmt: skip
    ref["plants"] = [dict(plant="P1", criterion="C1", world="W1", time_s=None, compared={})]
    (tmp_path / "refs" / "outputs").mkdir(parents=True)
    (tmp_path / "refs" / "outputs" / "reference_W1.json").write_text(json.dumps(ref))
    (tmp_path / "expected.json").write_text(json.dumps(dict(runs={"W1": INPUTS})))
    (tmp_path / "registration.json").write_text(json.dumps(REG))
    common = [
        "judge",
        "--references",
        str(tmp_path / "refs"),
        "--expected",
        str(tmp_path / "expected.json"),
    ]
    assert (
        J.main(
            [
                *common,
                "--registration",
                str(tmp_path / "registration.json"),
                "--out",
                str(tmp_path / "a"),
            ]
        )
        == 0
    )
    verdict = json.loads((tmp_path / "a" / "verdict.json").read_text())
    assert verdict["scope"].startswith("§12.3 steps 1 to 3") and verdict["stopped"] is None
    assert J.main([*common, "--table", str(tmp_path), "--out", str(tmp_path / "b")]) == 2
    stopped = json.loads((tmp_path / "b" / "verdict.json").read_text())["stopped"]
    assert all(
        flag in stopped for flag in ("--tag", "--table-sha256", "--addendum", "--execution-record")
    )
