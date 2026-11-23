"""Reconcile an event-triggered lysis from the saved lineage and population records (R9)."""

import argparse
import json
import math
from pathlib import Path
from tempfile import TemporaryDirectory

import jax
import numpy as np

from cells.definitions.specs import parse_spec
from cells.models.assembly_lineages_v2 import lumen, population, records, runner
from tests.assembly_lineage_v2_fixtures import definition
from tests.unit.test_assembly_lineages_v2_lumen import K_L, osmotic_world, spec_of


def release_spec(mode, held):
    # One lipid detaches and crosses the lysis threshold. Both membrane and lumen contain L,
    # so two source places feed the same destination. Impermeant I has no step flux.
    world = osmotic_world(
        L_pool=0, L_mem=5, S_pool=0, S_lumen=0, I_lumen=2, mu_bilayer=3.0, floor=K_L
    )
    world["phases"]["lumen"]["species"].append("L")
    world["founder"]["L@lumen"] = 2
    if held:
        inert = next(row for row in world["phases"]["pool"]["species"] if row["id"] == "I")
        inert.update(kind="held", held_mM=10.0)
        del world["founder"]["I@pool"]
    initial = spec_of(world).model.world
    world["geometry"]["sigma_max_N_per_m"]["value"] = 1.0001 * lumen.host_tension(
        initial, initial.founder
    )
    if mode == "population":
        founder = {p.name: world["founder"][p.name] for p in initial.places if p.phase != "pool"}
        other = dict.fromkeys(founder, 0)
        other["L@membrane"] = 1
        world["population"] = {
            "structure": population.SHARED_POOL,
            "slots": 2,
            "founders": [founder, other],
        }
        world["founder"].update(dict.fromkeys(founder, 0))
    raw = definition(world, horizon=50.0, event_limit=2000, row_every=1, molecules=64)
    raw["execution"]["mode"] = mode
    raw["experiment"]["diagnostic"] = True
    return parse_spec(raw)


def read_release(directory):
    meta = json.loads((directory / "run.json").read_text())
    diag = json.loads((directory / "diagnostic.json").read_text())
    with np.load(directory / "diagnostic.npz") as event, np.load(directory / "records.npz") as rows:
        (i,) = np.flatnonzero(event["event_lysed"])
        time = event["event_time"][i]
        places = meta["places"]
        names = [p["name"] for p in places]
        finite_names = [p["name"] for p in places if p["phase"] == "pool" and p["kind"] == "finite"]
        pop = meta["mode"] == "population"
        kind = "lysis" if pop else "end"
        legend = meta["records"]["row_kind"]["legend"]
        (j,) = [
            n
            for n in np.flatnonzero((rows["row_event"] == i + 1) & (rows["row_time"] == time))
            if legend[str(rows["row_kind"][n])] == kind
        ]
        if pop:
            (release,) = [r for r in diag["lyses"] if r["event"] == i + 1 and not r["at_birth"]]
            slot = release["slot"]
            assert event["event_group"][i] == slot + 1
            assert rows["slot_key"][j, slot] == -1 and not rows["slot_count"][j, slot].any()
            assert (rows["slot_key"][j] >= 0).sum() == 1
            vesicle_names = pool_names = diag["places"]
            post = rows["pool_count"][j]
        else:
            release = meta["osmotic"]["lysis"]
            vesicle_names, pool_names = diag["vesicle_places"], diag["pool_places"]
            post = rows["place_count"][j]
            final = diag["states"]["final"]
            assert final["pool"] == [int(post[names.index(p)]) for p in pool_names]
            assert not any(final["slots"][0]["counts"])
            assert all(post[p["index"]] == 0 for p in places if p["phase"] != "pool")
        assert release["time_s"] == time
        cargo = dict(zip(vesicle_names, event["event_vesicle_after"][i], strict=True))
        step_pool = dict(zip(pool_names, event["event_pool_after"][i], strict=True))
        pools = {p["species"]: p for p in places if p["phase"] == "pool"}
        expected = {}
        for p in places:
            if p["phase"] != "pool" and cargo[p["name"]]:
                dest = pools[p["species"]]["name"]
                expected[dest] = expected.get(dest, 0) + int(cargo[p["name"]])
        assert release["returned"] == expected
        expected_work = 0.0
        for p in pools.values():
            name, k = p["name"], p["index"]
            receipt = expected.get(name, 0)
            if p["kind"] == "finite":
                assert post[k] == step_pool[name] + receipt
            else:
                assert post[k] == rows["pool_count" if pop else "place_count"][0, k]
                if name in step_pool:
                    assert post[k] == step_pool[name]
                # Only impermeant I is held in this fixture. Its first exchange is the release.
                assert (
                    rows["reservoir_supplied"][j, k] - rows["reservoir_supplied"][0, k] == -receipt
                )
                mu = p["standard_mu_RT"] + math.log(p["held_mM"] / 1000.0)
                expected_work -= mu * receipt
        assert math.isclose(
            release["release_reservoir_work_kT"], expected_work, abs_tol=1e-12, rel_tol=1e-12
        )
        return dict(
            event=int(i + 1),
            cargo={p: int(cargo[p]) for p in vesicle_names if cargo[p]},
            step_finite_pool={p: int(step_pool[p]) for p in finite_names},
            returned=expected,
            final_finite_pool={p: int(post[names.index(p)]) for p in finite_names},
            held_supply_change={
                p["name"]: int(
                    rows["reservoir_supplied"][j, p["index"]]
                    - rows["reservoir_supplied"][0, p["index"]]
                )
                for p in pools.values()
                if p["kind"] == "held"
            },
            release_work_kT=release["release_reservoir_work_kT"],
        )


def compare(directory):
    cases = {}
    for mode in ("single_lineage", "population"):
        for held in (False, True):
            name = f"{mode}_{'held' if held else 'finite'}"
            run = runner.run(release_spec(mode, held)).check()
            assert run.closure["holds"]
            records.write_run(directory / name, run)
            cases[name] = read_release(directory / name)
            assert cases[name]["step_finite_pool"]["L@pool"] > 0
            assert cases[name]["cargo"]["L@membrane"] > 0 and cases[name]["cargo"]["L@lumen"] > 0
    return cases


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="keep the four Cells run bundles here")
    args = parser.parse_args()
    jax.config.update("jax_enable_x64", True)
    if args.output:
        results = compare(args.output)
    else:
        with TemporaryDirectory() as tmp:
            results = compare(Path(tmp))
    print(json.dumps(results, indent=2, allow_nan=False))
