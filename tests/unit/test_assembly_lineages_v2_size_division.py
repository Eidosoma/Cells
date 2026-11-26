"""cells.operator.size_threshold_division@1 in exact events (OL6 S7; the OL6 design note's §6.8, G2).

Protocol G §3's interface contract, re-derived here from the run's own trace and draws on a small
unregistered world (three types joining a membrane from held pools, under the transition-state
factor), never Protocol G's worlds or seeds, and never against @1 (Protocol G's checker runs that):
- each division is a join that brought N to the size, and every such join divides;
- its N uniforms are domain 2's at the parent's key, counter 0, the first N of a longer draw at
  that address;
- the first daughter is the first floor(f N) places ranked by u, ties by place, and the second the
  parent less the first;
- keys s:c and s:c+1 come from the parent's counter, the first is followed, and its next event
  draws from its own stream at counter 0;
- the books close, and the division rows and the fission table agree with the trace;
- chunk size and lane batch change no value (chunk 1 and a 2-lane batch at chunk 7 against chunk
  4096);
- a trigger that is the event guard's last event divides, then the lineage ends event_limit;
- the physical measure (multinomial, kept) closes its books, and its bundle's records and
  relations are written;
- the refusals, by name, in exact events and in the deterministic representation.
A new file for the operator (D224): four programs are compiled here (chunk 4096, chunk 1, a 2-lane
batch at chunk 7, and the physical measure), about 60 s on a light CPU.
"""

import collections
import copy
import json
import math

import jax
import numpy as np
import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.models.assembly_lineages_v2 import (
    IDEAL_MIXING,
    MASS_ACTION,
    MODEL_ID,
    SIZE_THRESHOLD_DIVISION,
    TRANSITION_STATE,
    model,
    records,
    runner,
    streams,
)
from tests.unit.test_assembly_lineages_v2_rate_equations import as_representation
from tests.unit.test_assembly_lineages_v2_rate_equations_vesicles import vesicle_world

jax.config.update("jax_enable_x64", True)

TYPES = ("a", "b", "c")
K = (2.0, 1.0, 3.0)  # each type's membrane affinity, mu°_bil = -ln K
KB = (1.0, 1.5, 0.8)  # leave rates (1/s); a join's k_f is K kb
RHO = (4.0, 4.0, 2.0)  # held pool concentrations (mM, c0 = 1 mM): sum K rho = 18, near the size
BETA = ((0.5, 3.0, 0.2), (1.0, 0.1, 4.0), (2.0, 0.3, 0.7))  # catalyst j on the join of i
FOUNDER = (3, 2, 3)
SIZE = 15  # odd, so floor(f N) differs from its ceiling; not a power of two, so streams.block cuts
MOLECULES = 64
MEASURES = {
    "exact": {"condensed_measure": "multinomial_less_one", "last_molecule": "extinct"},
    "physical": {"condensed_measure": "multinomial", "last_molecule": "kept"},
}


def world(measure="exact", **division):
    return {
        "units": {"time": "s", "temperature_K": 298.15, "standard_concentration_mM": 1.0},
        "conventions": {"free_energy_form": "discrete", "membrane_kinetics": "count_on_m",
                        "lumen_volume": "declared", "empty_catalyst_phase": "uncatalysed",
                        **MEASURES[measure]},
        "species": [{"id": s, "moieties": None,
                     "standard_mu_RT": {"solution": 0.0, "bilayer": -math.log(K[i])},
                     "catalogue": None, "evidence": None} for i, s in enumerate(TYPES)],
        "phases": {"pool": {"volume_L": 1e-21, "species": [
            {"id": s, "kind": "held", "held_mM": RHO[i]} for i, s in enumerate(TYPES)]},
                   "membrane": {"species": list(TYPES)}},
        "steps": [{"id": f"join_{s}", "locus": "membrane", "reactants": {f"{s}@pool": 1},
                   "products": {f"{s}@membrane": 1}, "law": MASS_ACTION,
                   "forward_rate_per_s": K[i] * KB[i]} for i, s in enumerate(TYPES)],
        "free_energy": [{"law": IDEAL_MIXING}],
        "rate_factor": {"law": TRANSITION_STATE, "catalysing_phase": "membrane",
                        "entries": [{"catalyst": TYPES[j], "step": f"join_{TYPES[i]}",
                                     "ddG_kT": math.log1p(BETA[i][j])}
                                    for i in range(3) for j in range(3)]},
        "founder": {f"{s}@membrane": FOUNDER[i] for i, s in enumerate(TYPES)},
        "division": {"law": SIZE_THRESHOLD_DIVISION, "size": SIZE,
                     "partition": {"rule": "exact_fraction", "fraction": 0.5},
                     "continuation": "first", **division},
    }  # fmt: skip


def definition(w, *, chunk=4096, seed=1, events=300, uniforms=True, diagnostic=None):
    out = {
        "schema_version": 1,
        "model": {"id": MODEL_ID, "world": copy.deepcopy(w)},
        "experiment": {"time_horizon_s": 100.0, "event_limit": events, "row_every_events": 7,
                       "observation_times_s": [0.1, 0.3], "trace": True, "uniforms": uniforms},
        "execution": {"backend": "cpu", "precision": "float64", "mode": "single_lineage",
                      "stream": {"seed": seed, "environment": 0, "lineage": 0, "branch": 0},
                      "molecule_capacity": MOLECULES, "place_capacity": 8, "step_capacity": 4,
                      "chunk_events": chunk},
    }  # fmt: skip
    if diagnostic is not None:
        out["experiment"]["diagnostic"] = diagnostic
    return out


@pytest.fixture(scope="module")
def exact_run():
    spec = parse_spec(definition(world()))
    return spec, runner.run(spec)


def _arrays(run):
    return records._arrays(run)


def _same(a, b):
    left, right = _arrays(a), _arrays(b)
    assert sorted(left) == sorted(right)
    for name in left:
        assert np.array_equal(left[name], right[name], equal_nan=True), name


def test_each_division_keeps_protocol_g_s_contract(exact_run):
    spec, run = exact_run
    again = parse_spec(spec.to_dict())  # the block round trips under `division`, by its law
    assert again.model.world == spec.model.world and again.fingerprint == spec.fingerprint
    assert spec.model.world.division is None and spec.to_dict()["model"]["world"]["division"] == (
        world()["division"])  # fmt: skip
    f = run.size_division["fissions"]
    divisions = len(f["fission_time"])
    assert run.status == "event_limit" and divisions >= 3 and run.closure["holds"]
    codes, times = run.trace["event_channel"], run.trace["event_time"]
    draws = run.diagnostics["event_uniforms"]
    assert (codes < 0).sum() > 0  # leaves happen too
    base = model.layout(spec).base_key
    membrane = [spec.model.world.place_index(f"{s}@membrane") for s in TYPES]
    counts, r, joins_at_size = np.array(FOUNDER, dtype=np.int64), 0, []
    for k, code in enumerate(codes):
        counts[abs(int(code)) - 1] += 1 if code > 0 else -1
        if code > 0 and counts.sum() == SIZE:
            joins_at_size.append(k + 1)
        if r < divisions and k + 1 == f["fission_event"][r]:
            # A join that brought N to the size, at its own time.
            assert code > 0 and counts.sum() == SIZE and f["fission_time"][r] == times[k]
            assert np.array_equal(f["fission_parent_counts"][r][membrane], counts)
            # The draw: domain 2 at the parent's key, counter 0, the first N of a longer draw.
            parent = int(f["fission_parent"][r])
            stream = streams.stream_key_data(base, parent, "partition")
            u = np.asarray(streams.uniforms(stream, 0, MOLECULES))[:SIZE]
            assert np.array_equal(f["partition_uniforms"][r], u)
            # The partition, re-derived: places by type in declared order, ranked by u, ties by
            # place; the first floor(f N) to the first daughter, the rest to the second.
            kinds = [i for i, n in enumerate(counts) for _ in range(n)]
            ranked = sorted(range(SIZE), key=lambda p: (u[p], p))
            chosen = collections.Counter(kinds[p] for p in ranked[: math.floor(0.5 * SIZE)])
            first = np.array([chosen[i] for i in range(3)], dtype=np.int64)
            daughters = f["fission_daughter_counts"][r][:, membrane]
            assert np.array_equal(daughters[0], first)
            assert np.array_equal(daughters[1], counts - first)
            # Keys from the parent's counter (founder 0:0, the counter from 0:1), the first
            # followed; its next event draws from its own stream at counter 0.
            assert list(f["fission_daughters"][r]) == [2 * r + 1, 2 * r + 2]
            assert parent == (0 if r == 0 else f["fission_daughters"][r - 1][0])
            assert f["fission_followed"][r] == 0
            if k + 1 < len(codes):
                own = streams.stream_key_data(base, int(f["fission_daughters"][r][0]), "events")
                assert np.array_equal(draws[k + 1], np.asarray(streams.uniforms(own, 0, 2)))
            counts = first.copy()
            r += 1
    assert r == divisions and joins_at_size == list(f["fission_event"])
    # The division rows: one per division, at its trigger, holding the followed daughter.
    rows = run.rows
    at = np.flatnonzero(rows["row_kind"] == runner.DIVISION)
    assert len(at) == divisions
    assert np.array_equal(rows["row_event"][at], f["fission_event"])
    assert np.array_equal(rows["place_count"][at][:, membrane],
                          f["fission_daughter_counts"][:, 0][:, membrane])  # fmt: skip
    # Periodic and observed rows beside the division rows, the books closed at every one.
    kinds = rows["row_kind"].tolist()
    assert kinds.count(runner.OBSERVED) == 2 and kinds.count(runner.PERIODIC) >= 10
    assert np.all(np.abs(rows["ledger_residual_kT"]) <= 1e-9)
    # The books: the division's work and the sink, F_m(first) + F_m(second) - F_m(parent).
    assert rows["division_work_kT"][-1] == pytest.approx(f["fission_work_kT"].sum(), abs=1e-9)
    assert rows["discarded_free_energy_kT"][-1] == pytest.approx(
        f["fission_discarded_kT"].sum(), abs=1e-9)  # fmt: skip
    lives = run.size_division["lives"]
    censored = [life["key"] for life in lives if life["end_reason"] == "censored"]
    assert len(lives) == 1 + 2 * divisions and censored == [f["fission_daughters"][-1][0]]


def test_chunk_size_and_lane_batch_change_no_value(exact_run):
    spec, run = exact_run
    one = runner.run(parse_spec(definition(world(), chunk=1)))
    _same(one, run)
    batch = runner.run_lanes([parse_spec(definition(world(), chunk=7, seed=s)) for s in (1, 2)])
    _same(batch[0], run)
    _same(batch[1], runner.run(parse_spec(definition(world(), seed=2))))
    assert not np.array_equal(batch[1].trace["event_channel"], run.trace["event_channel"])


def test_a_trigger_at_the_event_guard_divides_then_ends_event_limit(exact_run, tmp_path):
    _, run = exact_run
    f = run.size_division["fissions"]
    first = int(f["fission_event"][0])
    cut = runner.run(parse_spec(definition(world(), events=first)))
    g = cut.size_division["fissions"]
    assert cut.status == "event_limit" and len(g["fission_time"]) == 1 and cut.closure["holds"]
    assert np.array_equal(g["fission_daughter_counts"], f["fission_daughter_counts"][:1])
    assert int(cut.final["occupant"]) == f["fission_daughters"][0][0] and cut.final["age"] == 0
    assert np.array_equal(cut.final["counts"][: g["fission_daughter_counts"].shape[2]],
                          g["fission_daughter_counts"][0, 0])  # fmt: skip
    censored = [life["key"] for life in cut.size_division["lives"]
                if life["end_reason"] == "censored"]  # fmt: skip
    assert censored == [f["fission_daughters"][0][0]]
    # One event earlier, no division: empty fission arrays and the founder's one life, written.
    none = runner.run(parse_spec(definition(world(), events=first - 1)))
    assert none.status == "event_limit" and none.closure["holds"]
    assert none.size_division["fissions"]["fission_time"].shape == (0,)
    assert none.size_division["fissions"]["partition_uniforms"].shape == (0, SIZE)
    assert [life["end_reason"] for life in none.size_division["lives"]] == ["censored"]
    records.write_run(tmp_path / "none", none)
    assert json.loads((tmp_path / "none" / "run.json").read_text())["division"]["fissions"] == 0


def test_the_physical_measure_closes_its_books_and_writes_its_bundle(tmp_path):
    run = runner.run(parse_spec(definition(world("physical"), events=200, uniforms=False)))
    f = run.size_division["fissions"]
    assert run.closure["holds"] and len(f["fission_time"]) >= 1
    assert "partition_uniforms" not in f
    summary = records.write_run(tmp_path / "bundle", run)
    record = json.loads((tmp_path / "bundle" / "run.json").read_text())
    assert summary["ledger_closes"]
    assert SIZE_THRESHOLD_DIVISION in record["engine_models"]["operators"]
    assert record["division"]["operator"]["id"] == SIZE_THRESHOLD_DIVISION
    assert record["division"]["fissions"] == len(f["fission_time"])
    assert record["records"]["row_kind"]["legend"]["4"] == "division"
    assert (tmp_path / "bundle" / "relations.json").is_file()


def _geometry(raw):
    raw["model"]["world"] = vesicle_world()
    raw["model"]["world"]["division"] = world()["division"]
    return raw


def _two_molecules(raw):
    raw["model"]["world"]["steps"][0]["reactants"] = {"a@pool": 2}
    raw["model"]["world"]["steps"][0]["products"] = {"a@membrane": 2}
    return raw


def _set(path, value):
    def edit(raw):
        node = raw
        for key in path[:-1]:
            node = node[key]
        node[path[-1]] = value
        return raw

    return edit


@pytest.mark.parametrize(
    "edit, words",
    [
        (_geometry, "refused with a geometry"),
        (_two_molecules, "changes the membrane's count by 2"),
        (_set(("model", "world", "division", "size"), 8), "at or above the size 8"),
        (_set(("model", "world", "division", "partition", "fraction"), 0.06), "holds no molecule"),
        (_set(("model", "world", "division", "size"), 80), "above molecule_capacity 64"),
        (_set(("model", "world", "division", "continuation"), "uniform"), "continuation is first"),
        (_set(("experiment", "diagnostic"), True), "the diagnostic record is refused"),
        (as_representation, f"{SIZE_THRESHOLD_DIVISION} is refused in version 1"),
    ],
    ids=["geometry", "two molecules", "founder", "empty first", "capacity", "continuation",
         "diagnostic", "rate equations"],
)  # fmt: skip
def test_the_division_s_refusals(edit, words):
    with pytest.raises(ConfigError, match=words):
        parse_spec(edit(definition(world())))
