"""`cells stationary CONFIG --output DIR`: opt-in stationary-state analysis.

The config names an ordinary world (a definition or a complete checkpoint) and
an analysis block; the output is a new directory with result.json and
states.npz. Nothing is written elsewhere and the world is only read.

Config (JSON; paths relative to the config file):

  {"schema_version": 1,
   "analysis": "stationary_continuation_analysis@1",
   "world": {"definition": "world.json"} | {"snapshot": "run/checkpoint_dir"},
   "mode": "slow" | "fast",                 (default slow)
   "formulation": "rhs" | "step_map",        (default rhs)
   "steps": 1,                               (step-map length in declared steps)
   "control_time_s": 0.0,                    (schedule time of the controls;
                                              default the checkpoint time or 0)
   "guesses": [{"label": "base"},            (the world's own state)
               {"label": "D", "definition": "world_D.json"},
               {"label": "late", "snapshot": "dir"}],
   "newton": {"tolerance": 1e-10, "max_iterations": 60, "linear_solver": "dense"|"gmres",
              "globalization": "auto"|"newton"|"pseudo_transient"},
   "stability": {"method": "dense"|"arnoldi", "count": 12},
   "continuation": null | {"parameter": {"kind": "...", "ids": [...] | "all", "species": "Na"},
                           "from_guess": "base", "start": null, "direction": 1,
                           "step": 0.01, "min_step": 1e-7, "max_step": 0.05,
                           "max_points": 400, "bounds": [0.0, 1.0], "parameter_scale": 1.0}}

A guess supplies a starting state on the world's layout shapes; the world's
parameters always come from "world". In slow mode a guess contributes its
physical amounts and gates; in fast mode its gates and its node-charge
difference from the world (the world's composition is frozen).
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np

from cells import __version__
from cells.analysis import continuation as cont
from cells.analysis import stationary as sa
from cells.core.errors import NumericalError
from cells.core.specs import ConfigError, load_spec, read_json

FIELDS = {
    "schema_version",
    "analysis",
    "world",
    "mode",
    "formulation",
    "steps",
    "control_time_s",
    "guesses",
    "newton",
    "stability",
    "continuation",
}
NEWTON_FIELDS = {"tolerance", "max_iterations", "linear_solver", "globalization"}
STABILITY_FIELDS = {"method", "count"}
CONTINUATION_FIELDS = {
    "parameter",
    "from_guess",
    "start",
    "direction",
    "step",
    "min_step",
    "max_step",
    "max_points",
    "bounds",
    "parameter_scale",
}


def _only(raw, allowed, what):
    if type(raw) is not dict or set(raw) - allowed:
        raise ConfigError(f"{what} accepts only {sorted(allowed)}")
    return raw


def _world(raw, base):
    raw = _only(raw, {"definition", "snapshot"}, "world")
    if len(raw) != 1:
        raise ConfigError("world names exactly one definition or snapshot")
    if "definition" in raw:
        return load_spec(base / raw["definition"]), None, None, None
    from cells.io import load_snapshot

    saved = load_snapshot(base / raw["snapshot"])
    c = saved.checkpoint
    return saved.spec, c.state, c.layout, float(c.time)


def _guess_state(raw, base, pb):
    raw = _only(raw, {"label", "definition", "snapshot"}, "guess")
    if type(raw.get("label")) is not str or len(raw) > 2:
        raise ConfigError("A guess has a label and at most one source")
    if "definition" in raw:
        spec = load_spec(base / raw["definition"])
        state, layout = pb.model.initial_values(spec)
    elif "snapshot" in raw:
        from cells.io import load_snapshot

        saved = load_snapshot(base / raw["snapshot"])
        state, layout = saved.checkpoint.state, saved.checkpoint.layout
    else:
        return raw["label"], pb.anchor
    for name, a, b in zip(type(pb.base)._fields, state, pb.base, strict=True):
        if np.shape(a) != np.shape(b):
            raise ConfigError(f"Guess {raw['label']} has a different {name} layout")
    return raw["label"], pb.coordinates(state, layout)


def run_analysis(config, base=Path(".")):
    """The analysis result (a JSON-ready dict) and the states to save."""
    _only(config, FIELDS, "stationary analysis config")
    if config.get("schema_version") != 1 or config.get("analysis") != sa.ANALYSIS_ID:
        raise ConfigError(f"Require schema_version 1 and analysis {sa.ANALYSIS_ID}")
    spec, state, layout, checkpoint_time = _world(config.get("world"), base)
    control_time = config.get("control_time_s", checkpoint_time if checkpoint_time else 0.0)
    newton = _only(config.get("newton", {}), NEWTON_FIELDS, "newton")
    stability = _only(config.get("stability", {}), STABILITY_FIELDS, "stability")
    plan = config.get("continuation")
    parameter = None
    if plan is not None:
        plan = _only(plan, CONTINUATION_FIELDS, "continuation")
        declared = _only(plan.get("parameter"), {"kind", "ids", "species"}, "parameter")
        parameter = sa.parameter(
            spec, declared.get("kind"), declared.get("ids"), species=declared.get("species")
        )
    pb = sa.problem(
        spec,
        state=state,
        layout=layout,
        mode=config.get("mode", "slow"),
        formulation=config.get("formulation", "rhs"),
        steps=config.get("steps", 1),
        control_time=control_time,
        parameter=parameter,
    )
    guesses = [_guess_state(g, base, pb) for g in config.get("guesses", [{"label": "base"}])]
    labels = [g[0] for g in guesses]
    if len(set(labels)) != len(labels):
        raise ConfigError("Guess labels must be unique")
    records, states = [], {}
    for label, u in guesses:
        record, solution = sa.solve_and_check(
            pb, u, label=label, newton_options=newton, stability_options=stability
        )
        records.append(record)
        states[f"guess_{label}"] = np.asarray(u)
        if solution.converged:
            states[f"stationary_{label}"] = solution.u
    result = dict(
        kind="cells.stationary_analysis_result@1",
        analysis=sa.ANALYSIS_ID,
        cells_version=__version__,
        definition_sha256=spec.fingerprint,
        model=sa.model_identity(spec),
        world=config["world"],
        mode=pb.mode,
        formulation=pb.formulation,
        steps=pb.steps,
        dt_s=pb.dt,
        control_time_s=pb.control_time,
        coordinates=dict(
            size=pb.size,
            reduced_size=pb.reduction().size,
            kinds={k: int(np.sum(pb.kinds() == k)) for k in ("amount", "gate", "charge")},
            labels=pb.labels(),
        ),
        conservation_laws=[dict(law) for law in pb.reduction().laws],
        states=records,
        continuation=None,
    )
    if plan is not None:
        source = plan.get("from_guess", labels[0])
        if f"stationary_{source}" not in states:
            raise NumericalError(f"Continuation start {source} did not converge")
        diagram = cont.continue_branch(
            pb,
            states[f"stationary_{source}"],
            theta_start=plan.get("start"),
            direction=plan.get("direction", 1),
            step=plan.get("step", 0.01),
            min_step=plan.get("min_step", 1e-7),
            max_step=plan.get("max_step", 0.05),
            max_points=plan.get("max_points", 400),
            bounds=plan.get("bounds", (0.0, 1.0)),
            parameter_scale=plan.get("parameter_scale", 1.0),
            tolerance=newton.get("tolerance", sa.NEWTON_TOLERANCE),
        )
        states["continuation"] = diagram.pop("_states")
        diagram["from_guess"] = source
        result["continuation"] = diagram
    return result, states


def write_result(output, result, states):
    output = Path(output)
    if output.exists():
        raise ConfigError(f"Output already exists; choose a new directory: {output}")
    output.mkdir(parents=True)
    with open(output / "result.json", "x") as stream:
        json.dump(result, stream, indent=1, allow_nan=True)
    np.savez(output / "states.npz", **states)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="cells stationary", description=__doc__.split("\n")[0])
    parser.add_argument("config", type=Path)
    parser.add_argument(
        "--output", type=Path, required=True, help="new directory; never overwritten"
    )
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    try:
        if args.output.exists():
            raise ConfigError(f"Output already exists; choose a new directory: {args.output}")
        config = read_json(args.config)
        result, states = run_analysis(config, args.config.resolve().parent)
        write_result(args.output, result, states)
    except (ConfigError, NumericalError, OSError) as exc:
        print(f"cells stationary: {exc}", file=sys.stderr)
        return 2
    summary = [
        dict(
            label=r["label"],
            converged=r["converged"],
            classification=r.get("stability", {}).get("classification"),
        )
        for r in result["states"]
    ]
    print(json.dumps(dict(status="complete", output=str(args.output), states=summary), indent=2))
    return 0
