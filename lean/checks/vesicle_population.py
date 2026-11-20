"""Check molecular inventories and signed work at serial transfer and shear fission."""

import json
import math
from dataclasses import replace
from pathlib import Path

import numpy as np

from cells.definitions.specs import parse_spec
from cells.models.assembly_lineages_v2 import (
    SHARED_POOL,
    SHEAR_FISSION,
    division,
    population,
    runner,
)
from tests.assembly_lineage_v2_fixtures import definition
from tests.unit.test_assembly_lineages_v2_division import spec_of, vesicle_f, world_a
from tests.unit.test_assembly_lineages_v2_lumen import C_EXT_MM, K_L, NA, Q, osmotic_world
from tests.unit.test_assembly_lineages_v2_population import FOUNDER, pop_spec


def compare_energy(actual, expected, errors):
    error = abs(actual - expected)
    assert error <= 2e-11, (actual, expected)
    errors.append(float(error))


def places(world):
    # All three species have one finite pool place and one membrane or lumen place.
    bath = [world.place_index(p) for p in ("L@pool", "S@pool", "I@pool")]
    cargo = [world.place_index(p) for p in ("L@membrane", "S@lumen", "I@lumen")]
    return bath, cargo


def pool_energy(counts, volume_l):
    # Ideal dilute bath, standard concentration 1 M and all standard potentials zero.
    return math.fsum(math.lgamma(int(n) + 1) - n * math.log(NA * volume_l) for n in counts)


def transfers():
    world = osmotic_world(L_pool=30, L_mem=0, S_pool=6, S_lumen=0, I_lumen=0)
    world["founder"]["I@pool"] = 5
    founders = [{"L@membrane": 8 + j, "S@lumen": 1, "I@lumen": 1 + j} for j in range(3)]
    world["population"] = dict(structure=SHARED_POOL, slots=4, founders=founders)
    world["division"] = {"law": SHEAR_FISSION}
    raw = definition(world, molecules=128, horizon=2.5, event_limit=20000, row_every=1)
    raw["execution"]["mode"] = "population"
    raw["experiment"]["schedules"] = [
        dict(index=4, kind="transfer", times_s=[1.0, 2.0], K_keep=4, fresh_pool=[5, 0, 0]),
        dict(index=5, kind="transfer", times_s=[1.0], K_keep=1, fresh_pool=[9, 2, 4]),
    ]
    spec = parse_spec(raw)
    run = runner.run(spec).check()
    assert run.closure["holds"] and run.status == "complete"
    world, rows = spec.model.world, run.rows
    bath, cargo = places(world)
    schedules = {s.index: s for s in spec.experiment.schedules}
    columns = run.population["schedule_columns"]
    stops = np.flatnonzero(rows["row_kind"] == population.TRANSFER)
    events = run.population["transfers"]
    assert [t["schedule"] for t in events] == [4, 5, 4]
    assert stops[1] == stops[0] + 1
    errors, tracer = [], []
    for r, event in zip(stops, events, strict=True):
        # With one row per chemical event, the preceding row is the exact pre-transfer state.
        assert rows["row_event"][r - 1] == rows["row_event"][r]
        schedule = schedules[event["schedule"]]
        keys, post_keys = rows["slot_key"][r - 1 : r + 1]
        old, new = rows["pool_count"][r - 1 : r + 1, bath]
        before, after = rows["slot_count"][r - 1 : r + 1]
        live = np.flatnonzero(keys >= 0).tolist()
        draws = [u for _, _, u in event["draws"]]
        ranked = sorted(zip(draws, live, strict=True))
        kept = sorted(slot for _, slot in ranked[: schedule.keep])
        removed = sorted(set(live) - set(kept))
        assert event["kept"] == kept and event["removed"] == removed
        keep_mask = np.isin(np.arange(len(keys)), kept)
        np.testing.assert_array_equal(post_keys, np.where(keep_mask, keys, -1))
        np.testing.assert_array_equal(after, np.where(keep_mask[:, None], before, 0))
        fresh = np.asarray(schedule.fresh)
        np.testing.assert_array_equal(new, fresh)
        exported = old + before[removed].sum(axis=0)[cargo]
        np.testing.assert_array_equal(
            new + after.sum(axis=0)[cargo] + exported, old + before.sum(axis=0)[cargo] + fresh
        )
        work = pool_energy(fresh, world.volume("pool"))
        sink = pool_energy(old, world.volume("pool")) + math.fsum(
            vesicle_f(world, before[s]) for s in removed
        )
        compare_energy(event["work_kT"], work, errors)
        compare_energy(event["sink_kT"], sink, errors)

        expected_columns = np.zeros(len(columns))
        expected_columns[columns.index(schedule.index)] = work
        changes = rows["schedule_work_kT"][r] - rows["schedule_work_kT"][r - 1]
        for actual, expected in zip(changes, expected_columns, strict=True):
            compare_energy(actual, expected, errors)
        for field, expected in (
            ("discarded_free_energy_kT", sink),
            ("free_energy_kT", work - sink),
        ):
            compare_energy(rows[field][r] - rows[field][r - 1], expected, errors)
        tracer.append(
            dict(
                kept=kept,
                bath_before=int(old[2]),
                bath_after=int(new[2]),
                kept_cargo=int(after[:, cargo[2]].sum()),
                exported=int(exported[2]),
            )
        )
    assert [x["bath_before"] for x in tracer] == [5, 0, 4]
    assert [len(x["kept"]) for x in tracer] == [3, 1, 1]
    assert tracer[0]["kept_cargo"] == 6 and 0 < tracer[1]["kept_cargo"] < 6
    return dict(
        tracer=tracer,
        max_energy_error_kT=max(errors),
        closure_kT=run.closure["max_abs_residual_kT"],
    )


def fissions(spec, *, all_daughters):
    # The observation after each schedule also exposes the unchanged state of a refused split.
    times = spec.experiment.schedules[0].times
    spec = replace(
        spec,
        experiment=replace(spec.experiment, row_every_events=1, observation_times_s=tuple(times)),
    )
    run = runner.run(spec).check()
    assert run.closure["holds"]
    world, rows = spec.model.world, run.rows
    bath, cargo = places(world)
    table = (run.population if all_daughters else run.division)["fissions"]
    shear_kind = population.SHEAR if all_daughters else runner.SHEAR
    accepted_rows = iter(np.flatnonzero(rows["row_kind"] == shear_kind))
    outcomes = [division.POPULATION_OUTCOMES[i] for i in table["fission_outcome"]]
    errors, pairs, floor_parent_lipids = [], [], []
    for j, outcome in enumerate(outcomes):
        parent = table["fission_parent_counts"][j]
        daughters = table["fission_daughter_counts"][j]
        time = table["fission_time"][j]
        if outcome != "split":
            assert table["fission_shear_work_kT"][j] == table["fission_discarded_kT"][j] == 0
            assert not daughters.any() and (table["fission_daughters"][j] == -1).all()
            if all_daughters:
                assert outcome == "slots_full" and table["fission_counter"][j] == -1
                # The terminal row has the existing parent and the one common bath.
                slot = table["fission_slot"][j]
                np.testing.assert_array_equal(
                    rows["pool_count"][-1] + rows["slot_count"][-1, slot], parent
                )
            else:
                assert outcome == "refused_floor" and table["fission_counter"][j] >= 0
                floor_parent_lipids.append(int(parent[cargo[0]]))
                (r,) = np.flatnonzero(
                    (rows["row_time"] == time) & (rows["row_kind"] == runner.OBSERVED)
                )
                np.testing.assert_array_equal(rows["place_count"][r], parent)
                np.testing.assert_array_equal(rows["place_count"][r - 1], parent)
                assert rows["row_event"][r - 1] == rows["row_event"][r]
            continue
        r = next(accepted_rows)
        assert rows["row_time"][r] == time and rows["row_event"][r] == rows["row_event"][r - 1]
        assert not table["fission_lysed_at_birth"][j].any()
        np.testing.assert_array_equal(daughters[:, cargo].sum(axis=0), parent[cargo])
        assert (daughters[:, cargo[0]] >= 4).all()  # Four L molecules supply the declared floor.
        energies = [vesicle_f(world, d) for d in daughters]
        work = math.fsum(energies) - vesicle_f(world, parent)
        followed = table["fission_followed"][j]
        if all_daughters:
            assert followed == -1
            new_slots = table["fission_daughter_slots"][j]
            old_slot = table["fission_slot"][j]
            old_slots, slots = rows["slot_count"][r - 1 : r + 1]
            pool = rows["pool_count"][r]
            np.testing.assert_array_equal(rows["pool_count"][r - 1], pool)
            np.testing.assert_array_equal(old_slots[old_slot] + pool, parent)
            np.testing.assert_array_equal(slots[new_slots][:, cargo], daughters[:, cargo])
            np.testing.assert_array_equal(
                rows["slot_key"][r, new_slots], table["fission_daughters"][j]
            )
            np.testing.assert_array_equal(slots.sum(axis=0), old_slots.sum(axis=0))
            sink = 0.0
        else:
            assert 0 <= followed < len(daughters)
            pre, post = rows["place_count"][r - 1 : r + 1]
            np.testing.assert_array_equal(pre, parent)
            np.testing.assert_array_equal(post[cargo], daughters[followed, cargo])
            np.testing.assert_array_equal(pre[bath], post[bath])
            sink = math.fsum(e for i, e in enumerate(energies) if i != followed)
        compare_energy(table["fission_shear_work_kT"][j], work, errors)
        compare_energy(table["fission_discarded_kT"][j], sink, errors)
        for field, expected in (
            ("shear_work_kT", work),
            ("discarded_free_energy_kT", sink),
            ("free_energy_kT", work - sink),
        ):
            compare_energy(rows[field][r] - rows[field][r - 1], expected, errors)
        pairs.append((int(parent[cargo[2]]), int(daughters[:, cargo[2]].sum())))
    assert next(accepted_rows, None) is None
    assert outcomes == (
        ["split", "split", "slots_full"] if all_daughters else ["split"] * 3 + ["refused_floor"] * 2
    )
    assert run.status == ("slots_full" if all_daughters else "complete")
    return dict(
        outcomes=outcomes,
        tracer_pairs=pairs,
        floor_parent_lipids=floor_parent_lipids,
        max_energy_error_kT=max(errors),
        closure_kT=run.closure["max_abs_residual_kT"],
    )


def split_controls():
    rng = np.random.default_rng(320)
    membrane, weights, lumen = np.array([13, 7]), np.array([2, 5]), np.array([5, 9, 0])
    for k in (2, 3, 4):
        for _ in range(16):
            u = rng.random(int(membrane.sum() + lumen.sum() + k))
            shell, inside = division.split(membrane, weights, lumen, k, Q, u)
            np.testing.assert_array_equal(shell.sum(axis=0), membrane)
            np.testing.assert_array_equal(inside.sum(axis=0), lumen)
            assert (shell @ weights).sum() == membrane @ weights
            impossible_floor = int(membrane @ weights) // k + 1
            assert min(shell @ weights) < impossible_floor
    raw = world_a()
    raw["division"]["critical_stress_Pa"] = dict(value=2.0, provenance="control")
    world = spec_of(raw, stress=3.0).model.world
    edge_l = (Q * K_L * 12 / 2) ** 1.5 / (6 * math.sqrt(2 * math.pi)) * 1e3
    assert division.admitted_volume(edge_l * (1 - 1e-9), K_L * 12, Q, 2)
    assert not division.admitted_volume(edge_l * (1 + 1e-9), K_L * 12, Q, 2)
    parent = np.zeros(len(world.places), dtype=np.int64)
    parent[world.place_index("L@membrane")] = 12
    parent[world.place_index("I@lumen")] = math.ceil(edge_l * NA * C_EXT_MM / 1e3)

    def unexpected_energy(_):
        raise AssertionError("a pre-draw refusal reached energy booking")

    for stress, outcome in ((1.0, "refused_stress"), (3.0, "refused_volume")):
        saved = parent.copy()
        a = division.attempt(world, parent, 0, 0, (1.0, 0, 2, stress), (0, 1), unexpected_energy, 1)
        assert (a.outcome, a.counter, a.keys, a.shear_work, a.sink) == (outcome, -1, (), 0, 0)
        np.testing.assert_array_equal(a.parent_counts, saved)
        np.testing.assert_array_equal(parent, saved)


def main():
    split_controls()
    wash = transfers()
    lineage = fissions(spec_of(world_a()), all_daughters=False)
    founders = [dict(FOUNDER, **{"L@membrane": n}) for n in (12, 10)]
    shear = [dict(index=2, kind="shear", k=2, times_s=[1.0, 2.0])]
    pop = fissions(pop_spec(founders, 4, schedules=shear), all_daughters=True)
    parent, daughters = np.asarray(lineage["tracer_pairs"] + pop["tracer_pairs"]).T
    assert parent @ parent > 0
    slope = (parent @ daughters) / (parent @ parent)
    assert slope == 1
    data = json.loads(
        (Path(__file__).with_name("data") / "vesicle_population_measurements.json").read_text()
    )
    div, wash_data = data["deshpande2018"], data["fayolle2018"]
    lipid = np.asarray(wash_data["retentate_lipid_nmol"]) / wash_data["loaded_lipid_nmol"]
    print(
        json.dumps(
            dict(
                serial_transfer=wash,
                lineage_fission=lineage,
                population_fission=pop,
                tracer_slope=float(slope),
                measured_slope=div["slope"],
                measured_lipid_recovery=lipid.tolist(),
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
