"""Two vesicles compete for one exchangeable lipid and one permeant solute."""

import argparse
import json
import math
from itertools import permutations
from pathlib import Path
from traceback import extract_tb

import jax
import numpy as np

from cells.definitions.specs import parse_spec
from cells.models.assembly_lineages_v2 import OSMOTIC_LUMEN, SHARED_POOL, model, population, runner
from tests.assembly_lineage_v2_fixtures import definition, species, step
from tests.unit.test_assembly_lineages_v2_geometry import Q, lipid_world


def population_spec(founder_sizes):
    raw = lipid_world(lumen=True)
    raw["steps"] = [s for s in raw["steps"] if s["id"] != "iso"]
    raw["steps"][1]["permeability_m_per_s"]["value"] = 2e-8
    raw["phases"]["pool"]["volume_L"] = 5e-23
    raw["conventions"]["lumen_volume"] = "osmotic"
    del raw["phases"]["lumen"]["volume_L"]
    raw["free_energy"].append(
        dict(law=OSMOTIC_LUMEN, outside_osmolarity_mM=dict(value=1000.0, provenance="control"))
    )
    raw["geometry"]["sigma_max_N_per_m"] = dict(value=1000.0, provenance="control")
    raw["founder"] = {"L@pool": 1, "S@pool": 1, "L@membrane": 0, "P@membrane": 0, "S@lumen": 0}
    next(s for s in raw["species"] if s["id"] == "P")["standard_mu_RT"]["solution"] = 0
    raw["phases"]["pool"]["species"].append(dict(id="P", kind="finite"))
    raw["founder"]["P@pool"] = 0
    for name in ("A", "B"):
        raw["species"].append(species(name, {"marker": 1}, solution=0))
        raw["phases"]["pool"]["species"].append(dict(id=name, kind="finite"))
        raw["founder"][name + "@pool"] = int(name == "A")
    raw["steps"].append(step("marker", {"A": 1}, {"B": 1}, 0.2, phase="pool"))
    founders = [{"P@membrane": n, "L@membrane": 0, "S@lumen": 0} for n in founder_sizes]
    raw["population"] = dict(structure=SHARED_POOL, slots=3, founders=founders)
    d = definition(raw, molecules=64, horizon=5000, event_limit=96, row_every=1)
    d["execution"]["mode"] = "population"
    return parse_spec(d)


group_rates = jax.jit(population.all_rates, static_argnames=("structure",))


def rate_controls(spec):
    world, layout, structure = spec.model.world, model.layout(spec), model.structure(spec)
    pool = model.founder(spec)
    slots = np.zeros((3, len(pool)), dtype=np.int64)
    for i, founder in enumerate(world.population["founders"]):
        slots[i, : len(founder)] = founder
    live = np.array([True, True, False])
    masks = population.masks(world, structure.places, structure.steps)

    def rates(p, s, active):
        return np.asarray(group_rates(p, s, active, layout, structure, masks))

    original = rates(pool, slots, live)
    # One pool-only A -> B reaction, counted once across the world.
    assert math.isclose(original[0, 2], 0.2, rel_tol=2e-13)
    np.testing.assert_array_equal(original[1:, 2], 0)
    np.testing.assert_array_equal(original[0, :2], 0)
    np.testing.assert_array_equal(original[-1], 0)
    for order in permutations(range(3)):
        idx = list(order)
        table = rates(pool, slots[idx], live[idx])
        np.testing.assert_array_equal(table[0], original[0])
        np.testing.assert_array_equal(table[1:], original[1:][idx])
        assert math.fsum(table.flat) == math.fsum(original.flat)

    # Hold one vesicle's surface fixed while its neighbour takes the only lipid.
    after = pool.copy()
    after[world.place_index("L@pool")] -= 1
    changed = slots.copy()
    changed[0, world.place_index("L@membrane")] += 1
    depleted = rates(after, changed, live)
    np.testing.assert_array_equal(depleted[:, 0], 0)
    np.testing.assert_array_equal(depleted[2:, 1], original[2:, 1])
    area = Q * 60 * slots[:, world.place_index("P@membrane")] / 2
    per_molecule = 2e-8 * area / (world.volume("pool") * 1e-3)
    np.testing.assert_allclose(
        original[1:, :2], np.column_stack((per_molecule, per_molecule)), rtol=2e-13, atol=0
    )
    return dict(
        permutations=6,
        one_lipid_entry_rates_s=original[1:, 0].tolist(),
        depleted_entry_rates_s=depleted[1:, 0].tolist(),
        pool_only_rate_s=original[0, 2],
    )


def trajectory(spec):
    run = runner.run(spec).check()
    assert run.closure["holds"] and run.status == "event_limit"
    world, rows = spec.model.world, run.rows
    # Each row below contains bath, first vesicle, second vesicle and empty slot counts.
    counts = np.zeros((2, 4), dtype=np.int64)
    counts[:, 0] = 1
    history = [counts.copy()]
    entries = np.zeros((2, 3), dtype=int)
    pool_events = 0
    for group, channel in zip(run.trace["event_group"], run.trace["event_channel"], strict=True):
        direction = int(np.sign(channel))
        species_index = abs(channel) - 1
        if species_index < 2:
            assert group in (1, 2)
            counts[species_index, 0] -= direction
            counts[species_index, group] += direction
            assert counts.min() >= 0 and (counts.sum(axis=1) == 1).all()
            entries[species_index, group - 1] += int(direction > 0)
        else:
            assert species_index == 2 and group == 0
            pool_events += 1
        history.append(counts.copy())
    expected = np.stack(history)[rows["row_event"]]
    for i, (pool_name, slot_name) in enumerate((("L@pool", "L@membrane"), ("S@pool", "S@lumen"))):
        observed = np.column_stack(
            (
                rows["pool_count"][:, world.place_index(pool_name)],
                rows["slot_count"][:, :, world.place_index(slot_name)],
            )
        )
        np.testing.assert_array_equal(observed, expected[:, i])
    assert (entries[:, :2] > 0).all() and pool_events > 0
    return dict(
        events=len(history) - 1,
        entries_by_species_and_slot=entries.tolist(),
        pool_only_events=pool_events,
        max_count_error=0,
        max_closure_residual_kT=float(np.abs(rows["ledger_residual_kT"]).max()),
    )


def declared_volume_case():
    raw = lipid_world(lumen=True)
    raw["steps"] = [s for s in raw["steps"] if s["id"] == "entry"]
    raw["founder"] = {"L@pool": 0, "S@pool": 1, "L@membrane": 0, "P@membrane": 0, "S@lumen": 0}
    founder = {"L@membrane": 0, "P@membrane": 4, "S@lumen": 0}
    raw["population"] = dict(structure=SHARED_POOL, slots=1, founders=[founder])
    d = definition(raw, molecules=16, horizon=1e7, event_limit=1, row_every=1)
    d["execution"]["mode"] = "population"
    spec = parse_spec(d)
    volume = spec.model.world.volume("lumen")
    try:
        run = runner.run(spec).check()
    except TypeError as error:
        frame = extract_tb(error.__traceback__)[-1]
        if Path(frame.filename).name != "lumen.py" or frame.name != "constants":
            raise
        return dict(
            records_returned=False,
            declared_volume_L=volume,
            error=str(error),
            location="lumen.constants, called by population._assemble",
        )
    assert run.timings["events"] == 1
    np.testing.assert_equal(
        run.rows["slot_count"][-1, 0, spec.model.world.place_index("S@lumen")], 1
    )
    return dict(records_returned=True, declared_volume_L=volume, events=run.timings["events"])


def competition_measurement():
    data = json.loads(
        (Path(__file__).with_name("data") / "vesicle_exchange_measurements.json").read_text()
    )["chen2004"]
    # Assume equal lipid footprints and no net change of the free bath inventory.
    predicted = (
        -data["initial_donor_to_recipient_lipid_ratio"]
        * data["approximate_isotonic_area_change_percent"]
    )
    return dict(
        conditional_recipient_gain_percent=predicted,
        observed_approximate_percent=data["approximate_swollen_area_change_percent"],
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--controls-only", action="store_true")
    mode.add_argument("--declared-only", action="store_true")
    args = parser.parse_args()
    report = {}
    if not args.declared_only:
        first = population_spec((4, 16))
        report.update(
            rate_controls=rate_controls(first),
            original=trajectory(first),
            relabelled=trajectory(population_spec((16, 4))),
            chen2004=competition_measurement(),
        )
    if not args.controls_only:
        report["declared_volume"] = declared_volume_case()
    print(json.dumps(report, indent=2, allow_nan=False))
    raise SystemExit(
        int(not args.controls_only and not report["declared_volume"]["records_returned"])
    )
