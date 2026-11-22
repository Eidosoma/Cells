"""Reconstruct machine and residue ledgers from public, compiled polymerisation trajectories."""

import json
import math

import jax
import numpy as np

from cells.definitions.specs import parse_spec
from cells.registry.models import get_model
from validation.gene_regulation import engine_run, kernel, sheet_check, worlds

EPS = np.finfo(float).eps


def replay(raw):
    spec = parse_spec(raw)
    model = get_model(spec.model)
    _, layout = model.initial_values(spec)
    block = next(d for d in spec.model.operators if d.law == worlds.POLYMERISATION)
    op = next(op for op in model.operators if op.LAW_ID == worlds.POLYMERISATION)
    states = engine_run.collect(spec)
    times, exported, _ = engine_run.readouts(spec, states)
    np.testing.assert_array_equal(times, spec.experiment.observation_times)
    assert len(states) == len(times)
    rows = sorted(states.items())
    dt = spec.execution.dt
    pools, chains = {}, {}
    for i, pool in enumerate(block.pools):
        members = [j for j, c in enumerate(block.chains) if c.pool == pool.id]
        total = pool.machines * float(sheet_check.COPY_FMOL)
        residuals, omitted = [], []
        for k, (step, row) in enumerate(rows):
            assert math.isclose(step * dt, times[k], abs_tol=1e-12)
            complexes = np.asarray(row.poly_complexes_fmol)
            engaged = [math.fsum(complexes[j, : block.chains[j].stages]) for j in members]
            free = float(row.poly_free_machines_fmol[i])
            assert free == exported[f"F_{pool.id}"][k]
            error = math.fsum([free, *engaged, -total])
            internal = op.own_ledgers(row, layout, xp=np)["poly_machines"][i]
            assert abs(error) <= 128 * EPS * total and abs(error - internal) <= 8 * EPS * total
            residuals.append(abs(error))
            if len(members) > 1:
                omitted.append(abs(math.fsum([free, engaged[0], -total])))
        pools[pool.id] = dict(
            routes=[block.chains[j].id for j in members],
            total_fmol=total,
            max_balance_error_fmol=max(residuals),
        )
        if omitted:
            assert max(omitted) > 1e-3 * total
            pools[pool.id]["max_error_omitting_other_chains_fmol"] = max(omitted)
    for i, chain in enumerate(block.chains):
        r = chain.residues // chain.stages
        residuals, transits, releases = [], [], []
        for k, (_, row) in enumerate(rows):
            exits = float(row.poly_stage_exits_fmol[i])
            released = float(row.poly_released_fmol[i])
            cs = np.asarray(row.poly_complexes_fmol)[i]
            np.testing.assert_array_equal(cs[chain.stages :], 0)
            w = math.fsum(j * r * float(cs[j]) for j in range(chain.stages))
            np.testing.assert_allclose(w, exported[f"W_{chain.id}"][k], rtol=3e-15, atol=0)
            assert (
                exits == exported[f"int_S_{chain.id}"][k]
                and released == exported[f"int_Q_{chain.id}"][k]
            )
            done = chain.residues * released
            residual = math.fsum((r * exits, -w, -done))
            scale = math.fsum((abs(r * exits), abs(w), abs(done)))
            internal = op.own_ledgers(row, layout, xp=np)["poly_residues"][i]
            assert (
                abs(residual) <= 128 * EPS * scale and abs(residual - internal) <= 8 * EPS * scale
            )
            residuals.append(abs(residual))
            transits.append(w)
            releases.append(done)
        assert releases[-1] > 0
        if chain.stages == 1:
            assert max(transits) == 0
        else:
            assert max(transits) > 0
        chains[chain.id] = dict(
            stages=chain.stages,
            residues_per_stage=r,
            final_in_transit_fmol=transits[-1],
            final_in_released_products_fmol=releases[-1],
            max_balance_error_fmol=max(residuals),
        )
    return dict(saved_rows=len(times), dt_s=dt, end_s=times[-1], pools=pools, chains=chains)


if __name__ == "__main__":
    jax.config.update("jax_enable_x64", True)
    a1 = worlds.a1(end=30.0, every=0.5)
    shared = kernel.truncated(worlds.world("two-gene"), 30.0)
    shared["experiment"]["observation_times"] = a1["experiment"]["observation_times"]
    # Exercise a one-stage chain and zero padding alongside an eight-stage chain in the same pool.
    mixed = kernel.truncated(shared, 30.0)
    kernel.block(mixed)["chains"][0]["stages"] = 1
    print(
        json.dumps(
            {
                name: replay(raw)
                for name, raw in (("A1", a1), ("two_gene", shared), ("one_and_eight_stages", mixed))
            },
            indent=2,
            allow_nan=False,
        )
    )
