"""Unchanged production trajectories/checkpoint restart plus copied-state side probes."""

import timed_context as ctx

c, io = ctx.c, ctx.io


def side_probes(view, definition, record):
    import jax
    import jax.numpy as jnp
    import numpy as np

    from cells.core.schedule import PhysicalIonicGraphControl, control_values
    from cells.core.specs import parse_spec
    from cells.models import finite_extracellular as model

    spec = parse_spec(definition)
    _, layout = model.initial_values(spec)
    condition = record["id"].split("/")[0]
    base = PhysicalIonicGraphControl(*(v[0] for v in control_values(spec, [0.0])))

    def evaluate(state, control):
        return (
            model.rhs(state, control, layout, layout.active, xp=jnp),
            model.channel_readouts(state, control.channel, layout, xp=jnp),
        )

    run = jax.jit(evaluate) if definition["execution"]["jit"] else evaluate
    result = []
    for time_s in (view["protocol"]["duration_s"] / 4, view["protocol"]["duration_s"] / 2):
        index = round(time_s / definition["execution"]["dt"])
        state = model.STATE_TYPE(
            **{
                name: np.asarray(row["values"][index], dtype=np.float64)
                for name, row in record["history"].items()
            }
        )
        row = {"time_s": time_s, "state": {k: v.tolist() for k, v in state._asdict().items()}}
        for side in ("left", "right"):
            u = ctx.availability(view["schedules"][condition], time_s, side)
            values = np.zeros_like(base.channel)
            values[: len(spec.model.channels)] = u
            control = base._replace(channel=values)
            before = [np.asarray(v).tobytes() for v in (*state, *layout, *control)]
            rate, channels = run(state, control)
            c.require(
                before == [np.asarray(v).tobytes() for v in (*state, *layout, *control)],
                "Side probe mutated carried state",
            )
            row[side] = {
                "availability": u,
                "rhs": {k: np.asarray(v).tolist() for k, v in rate._asdict().items()},
                "flux_fmol_per_s": np.asarray(channels.flux_fmol_per_s).tolist(),
                "permeability_m_per_s": np.asarray(
                    channels.effective_permeability_m_per_s
                ).tolist(),
                "power_pJ_per_s": np.asarray(channels.dissipation_rate_pJ_per_s).tolist(),
            }
        result.append(row)
    return result


def worker(r, output):
    import feedback_cells

    results = {}
    for history, view in r["views"].items():
        local = output / history
        aggregate = feedback_cells.worker(view, local)
        paths = {}
        for key, path in aggregate["records"].items():
            record = io.read_compressed(local / path)
            probes = side_probes(view, view["cells_definitions"][key], record)
            target = local / "cells" / key / "side-probes.json.gz"
            io.write_compressed(target, probes)
            paths[key] = str(target.relative_to(local))
        aggregate["side_probes"] = paths
        results[history] = aggregate
    return {
        "by_history": results,
        "cells_trajectories": sum(v["cells_trajectories"] for v in results.values()),
        "resumed_segments": sum(v["resumed_segments"] for v in results.values()),
    }
