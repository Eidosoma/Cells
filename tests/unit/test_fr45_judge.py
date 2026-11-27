"""FR-45's judge (validation/fr45/judge.py) on hand-built fragments: one pass row and one fail row for each class of
pair, the refusal mapping, the plants' rules, the plant rule and the structural comparison (TABLE §11, §8, §12.1).

Seconds and reason (D224): about 1 s, pure Python, no engine; the judge is loaded by its path, as it loads
agreement.py, so no package's __init__ is imported. Self-contained fragments only (the lead's ruling 5c): no file of
the binding tag is read, and G is a stand-in (ruling 6).
"""

import copy
import importlib.util
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
    """A stand-in G (ruling 6): the sum of the node's amounts, enough to route C3b."""
    return -sum(amounts.values())


INPUTS = dict(
    world="INVENTED-W1",
    nodes=[dict(id="pond", kind="node", volume_pL=2.0, registered=True)],
    free_amounts=[dict(ligand="X", node="pond", n_fmol=1.0, declared=True)],
    sets=[
        dict(
            id="s",
            shared=False,
            owner="pond",
            face=None,
            faces="pond",
            copies=1.0,
            sites_per_copy=1,
            accessible_fraction=1.0,
        )
    ],  # fmt: skip
    populations=[dict(id="b", set="s", ligand="X", k_on=1.0, k_off=1.0, initial_occupancy=0.0)],
    wash=dict(time_s=0.1, node="pond", fraction=0.5, buffer_mM={"X": 0.25}),
)


def row(step, t, n=1.0, B=0.25, R=0.75, heat=0.0, theta=0.25, collected=0.0, supplied=0.0):
    return dict(step=step, time_s=t, amounts={"n:X@pond": n, "B:b": B, "R:s": R},
                records={"X@pond": dict(collected=collected, supplied=supplied)}, site_heat_pJ={"pond": heat},
                site_occupied_fraction={"b": theta})  # fmt: skip


def run(**changes):
    entry = dict(status="completed", world="INVENTED-W1", plant=None, dt_s=0.1, steps=2, backend="compiled",
                 driver=dict(window_steps=1), rows=[row(0, 0.0), row(2, 0.2, heat=0.5)], capacities={"s": 1.0},
                 free_sites={"s": "state"}, events=[], event_map=[], step_report=None, refusal=None,
                 checks={"energy": dict(failures=[])}, operators=["cells.model.resolved_pump_composite@1"],
                 inputs=copy.deepcopy(INPUTS), definition={}, source={}, record="records/x.json", record_sha256="0" * 64)  # fmt: skip
    entry.update(changes)
    return entry


def reference(*pairs, plants=()):
    world = dict(dt=0.1, observation_times=[0.2], horizon=0.2, sets=[dict(id="s", faces="pond", S=1.0)],
                 populations=[dict(id="b", set="s", ligand="X", k_on=1.0, k_off=1.0)],
                 nodes=[dict(id="pond", kind="node", V=2.0)], start=[], constants={})  # fmt: skip
    return dict(world=world, pairs=list(pairs), trajectory=[], plants=list(plants))


def pair(criterion, observable, value=None, tolerance=None, time_s=0.2, **extra):
    cls = extra.pop("cls", "band")
    return dict(criterion=criterion, observable=observable, time_s=time_s, value=value, tolerance=tolerance,
                **{"class": cls}, **extra)  # fmt: skip


def verdict(p, entry, ref=None):
    table = dict(runs={"INVENTED-W1": entry})
    ctx = J.Context(table, "W1", ref or reference(p), "INVENTED-")
    return J.evaluate(p, ctx, AGREEMENT, stand_in_g)


ROWS = {
    "C1 band within": (pair("C1", "n:X@pond", 1.0 + 1e-7, 1e-6), run(), True),
    "C1 band beyond": (pair("C1", "n:X@pond", 1.0 + 1e-5, 1e-6), run(), False),
    "C2b derived within": (pair("C2b", "B:b", 0.25, 1e-15, cls="derived"), run(), True),
    "C2b derived beyond": (pair("C2b", "B:b", 0.25 + 1e-12, 1e-15, cls="derived"), run(), False),
    "C3a heat within": (pair("C3a", "H:pond", 0.5, 1e-9, start_s=0.0, end_s=0.2), run(), True),
    "C3a heat beyond": (pair("C3a", "H:pond", 0.6, 1e-9, start_s=0.0, end_s=0.2), run(), False),
    "C3b against -dG": (
        pair("C3b", "H:pond", None, 1e-12, cls="derived", start_s=0.0, end_s=0.2),
        run(rows=[row(0, 0.0), row(2, 0.2, n=1.5, heat=0.5)]),
        True,
    ),  # fmt: skip
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
    "C1 a clock off the grid is not formed": (
        pair("C1", "n:X@pond", 1.0, 1e-6),
        run(rows=[row(0, 0.0), row(2, 0.2 + 1e-9)]),
        False,
    ),  # fmt: skip
}


@pytest.mark.parametrize("name", sorted(ROWS))
def test_each_class_passes_and_fails_as_written(name):
    p, entry, passes = ROWS[name]
    result = verdict(p, entry)
    assert bool(result.get("passes")) is passes, result


def _mapped_entry(before, after, f=0.5, variant="numpy"):
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
    maps = [_mapped_entry(before, after, variant=v) for v in ("numpy", "compiled")]
    entry = run(event_map=maps)
    c4b = pair(
        "C4b",
        "n:X@pond",
        time_s=0.1,
        cls="derived",
        tolerance_terms=dict(eps_factor=4 * EPS, f_V_c_buf=0.25),
    )
    removed = pair(
        "C4b",
        "removed:X@pond",
        time_s=0.1,
        cls="derived",
        tolerance_terms=dict(eps_factor=2 * EPS, f=0.5),
    )
    c6 = pair("C6", "B:b", "unchanged", None, time_s=0.1, cls="constant")
    assert verdict(c4b, entry)["passes"] and verdict(removed, entry)["passes"]
    assert bool(verdict(c6, entry)["passes"]) is honest
    one = run(event_map=maps[:1])
    assert "unformed" in verdict(c6, one)


def test_c7_c10_and_c8_by_their_outcome_rules():
    report = dict(step=1, h_s=0.05, loads=[dict(kind="L_R", id="s", sums=["a", "b"], per_s=12.0),
                                          dict(kind="L_B", id="a", sums=["a"], per_s=1.0)], limit=0.5,
                  h_max_load=0.6, verdict="refused")  # fmt: skip
    report["max_load"] = report["loads"][0]
    refusal = dict(kind="stage", raised="cells.execution.errors.NumericalError", book=None, name="stage condition",
                   message="", step=1, time_s=0.0)  # fmt: skip
    w5 = run(
        world="INVENTED-W5",
        status="refused",
        refusal=refusal,
        step_report=report,
        rows=[row(0, 0.0)],
    )
    assert J._c7(w5)["passes"]
    assert not J._c7(dict(w5, step_report=dict(report, h_max_load=0.4)))["passes"]
    ctx = J.Context(dict(runs={"INVENTED-W1": run()}), "W1", reference(), "INVENTED-")
    assert J._c10(run(), ctx)["passes"]
    assert not J._c10(run(checks={"energy": dict(failures=[dict(step=1, message="x")])}), ctx)[
        "passes"
    ]
    assert not J._c10(run(rows=[row(0, 0.0)]), ctx)["passes"]


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


def _plant_table(planted_n, honest_n=1.0, refusal=None):
    honest = run(rows=[row(0, 0.0), row(2, 0.2, n=honest_n)])
    plant = run(plant=dict(id="P1", patch="validation/fr45/plants/p1.py", change="x", inputs_changed=[]),
                rows=[row(0, 0.0), row(2, 0.2, n=planted_n)], refusal=refusal,
                status="refused" if refusal else "completed")  # fmt: skip
    return dict(runs={"INVENTED-W1": honest, "INVENTED-W1-P1": plant})


@pytest.mark.parametrize(
    "planted, honest, caught",
    [(1.5, 1.0, True), (1.0, 1.0, False), (1.5, 1.5, False)],
    ids=["a fail on the plant with a passing baseline", "no fail", "a failed baseline"],
)
def test_a_plant_is_caught_only_where_its_honest_baseline_passes(planted, honest, caught):
    ref = reference(pair("C1", "n:X@pond", 1.0, 1e-6), plants=[dict(plant="P1", criterion="C1", world="W1",
                                                                     time_s=None, compared={})])  # fmt: skip
    out = J.judge_plants(
        _plant_table(planted, honest), {"W1": ref}, AGREEMENT, stand_in_g, prefix="INVENTED-"
    )
    assert out["P1"]["caught"] is caught


def test_a_check_refusal_catches_where_the_row_names_no_book():
    refusal = dict(kind="check", raised="cells.execution.errors.NumericalError", book="moiety ledger",
                   name="site_moiety_entity", message="", step=1, time_s=0.0)  # fmt: skip
    ref = reference(pair("C1", "n:X@pond", 1.0, 1e-6), plants=[dict(plant="P1", criterion="C1", world="W1",
                                                                     time_s=None, compared={})])  # fmt: skip
    out = J.judge_plants(
        _plant_table(1.0, refusal=refusal), {"W1": ref}, AGREEMENT, stand_in_g, prefix="INVENTED-"
    )
    assert out["P1"]["caught"]


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


def test_the_blob_check_is_gits():
    assert J.git_blob(b"") == "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391"
