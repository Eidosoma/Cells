"""Compare the FR-20 pulse and wash and check the fresh pool at molecule capacity."""

import argparse
import json
import math
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from cells.definitions.specs import ConfigError, parse_spec
from cells.models.assembly_lineages_v2 import population, records, runner
from cells.records import relations
from lean.checks.vesicle_population import pool_energy
from tests.unit import test_assembly_lineages_v2_replacement as fixture


def pulse_and_wash(directory):
    raw = fixture.raw_world()
    raw["experiment"]["row_every_events"] = 1
    spec = fixture.wash_spec(raw)
    world = spec.model.world
    run = runner.run(spec).check()
    records.write_run(directory, run)
    _, saved, rows = records.read(directory)
    _, tables = relations.read(directory)
    stops = saved["population"]["replacements"]
    assert run.status == "complete" and len(stops) == 2
    assert run.population["schedule_draws"] == []

    finite = {p.name: i for i, p in enumerate(world.places) if p.phase == "pool" and not p.held}
    tracer = [i for i, p in enumerate(world.places) if p.species in ("S", "C")]
    report, errors = [], []
    exchanged = np.zeros(len(rows["row_time"]), dtype=np.int64)
    for stop in stops:
        (i,) = np.flatnonzero((rows["row_kind"] == population.REPLACEMENT)
                              & (rows["row_time"] == stop["time_s"]))
        assert rows["row_event"][i - 1] == rows["row_event"][i]
        for field in ("slot_count", "slot_key"):
            np.testing.assert_array_equal(rows[field][i], rows[field][i - 1])
        old, fresh = ({p: int(rows["pool_count"][j, k]) for p, k in finite.items()}
                      for j in (i - 1, i))
        schedule = next(s for s in spec.experiment.schedules if s.index == stop["schedule"])
        assert stop["removed"] == old and stop["supplied"] == fresh
        assert tuple(fresh.values()) == schedule.fresh

        payer = f"source:replacement/{schedule.index}"
        expected_edges = [
            (kind, src, dst, world.places[finite[name]].species, count)
            for kind, src, dst, counts in (("removes_to", "node:pool", "sink:discard", old),
                                           ("supplies", payer, "node:pool", fresh))
            for name, count in counts.items() if count
        ]
        edges = [e for e in tables["edges"] if e.event == stop["id"]]
        saved_edges = [(e.relation, e.from_, e.to, e.species, e.weight) for e in edges]
        assert sorted(saved_edges) == sorted(expected_edges)
        assert all(
            e.mode == "event" and e.declared_by == "cells.operator.pool_replacement@1"
            for e in edges
        )

        # This fixture has an ideal bath and zero standard solution potentials for every species.
        sink, work = (pool_energy(c.values(), world.volume("pool")) for c in (old, fresh))
        cols = rows["schedule_work_kT"]
        column = run.population["schedule_columns"].index(schedule.index)
        actual = [stop["sink_kT"], stop["work_kT"], cols[i, column] - cols[i - 1, column],
                  rows["discarded_free_energy_kT"][i] - rows["discarded_free_energy_kT"][i - 1],
                  rows["free_energy_kT"][i] - rows["free_energy_kT"][i - 1]]
        reference = [sink, work, work, sink, work - sink]
        errors.extend(abs(a - b) for a, b in zip(actual, reference, strict=True))
        exchanged[i] = fresh["S@pool"] + fresh["C@pool"] - old["S@pool"] - old["C@pool"]
        report.append(dict(time_s=stop["time_s"], bath_tracer_before=old["S@pool"] + old["C@pool"],
                           bath_tracer_after=fresh["S@pool"] + fresh["C@pool"],
                           retained_tracer=int(rows["slot_count"][i][:, tracer].sum()),
                           bound_tracer=int(rows["slot_count"][i, :, world.place_index("C@membrane")].sum()),
                           material_edges=len(edges), work_kT=work, sink_kT=sink))

    total = (rows["pool_count"][:, tracer].sum(axis=1)
             + rows["slot_count"][:, :, tracer].sum(axis=(1, 2)))
    np.testing.assert_array_equal(total, total[0] + np.cumsum(exchanged))
    assert max(errors) < 2e-11
    assert report[1]["bath_tracer_after"] == 0 and report[1]["bound_tracer"] > 0
    steps = [s.id for s in world.steps]
    channels = [steps.index(s) + 1 for s in fixture.TRACER_STEPS]
    moves = [(float(t), int(c)) for t, c in zip(rows["event_time"], rows["event_channel"], strict=True)
             if t > fixture.WASH and abs(c) in channels]
    assert moves[0][1] < 0
    reentry = next(t for t, c in moves if c > 0)
    return dict(stops=report, rows=len(total), max_energy_error_kT=max(errors),
                first_release_s=moves[0][0], first_reentry_s=reentry)


def capacity_case(kind, capacity, count):
    raw = fixture.raw_world()
    raw["execution"]["molecule_capacity"] = capacity
    fresh = fixture.pool_of(raw, I=count)
    schedule = dict(index=1, kind=kind, times_s=[0.125])
    if kind == "replacement":
        schedule["pool"] = fresh
    else:
        schedule.update(K_keep=2, fresh_pool=fresh)
    raw["experiment"].update(time_horizon_s=0.125, observation_times_s=[], schedules=[schedule])
    row = dict(kind=kind, capacity=capacity, fresh_count=count)
    try:
        spec = parse_spec(raw)
        run = runner.run(spec).check()
    except ConfigError as error:
        if count <= capacity or "capaci" not in str(error).lower():
            raise
        return dict(row, status="refused", reason=str(error), within_contract=True)
    stops = run.population[kind + "s"]
    if not stops:
        assert count > capacity and run.status == "capacity"
        return dict(row, status=run.status, within_contract=True)
    (stop,) = stops
    assert run.final["pool"][spec.model.world.place_index("I@pool")] == count
    expected = pool_energy([count], spec.model.world.volume("pool"))
    booked = stop["work_kT"]
    error = expected - booked
    if count <= capacity:
        assert run.status == "complete" and abs(error) < 2e-11
    return dict(row, status=run.status, ledger_passed=bool(run.closure["holds"]),
                reference_work_kT=expected, booked_work_kT=booked, reference_minus_booked_kT=error,
                first_omitted_log_factorial_term_kT=math.log(capacity + 1) if count > capacity else 0.0,
                within_contract=count <= capacity)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=("pulse", "capacity", "all"), default="all")
    parser.add_argument("--bundle", type=Path, help="save the checked pulse/wash bundle in a new directory")
    args = parser.parse_args()
    report = {}
    if args.case in ("pulse", "all"):
        with TemporaryDirectory() as tmp:
            report["pulse_and_wash"] = pulse_and_wash(args.bundle or Path(tmp) / "run")
    if args.case in ("capacity", "all"):
        report["capacity"] = [capacity_case(kind, cap, count) for kind in ("replacement", "transfer")
                              for cap, count in ((32, 32), (32, 33), (64, 33))]
    print(json.dumps(report, indent=2, allow_nan=False))
    raise SystemExit(int(any(not case["within_contract"] for case in report.get("capacity", []))))
