"""Registered history axis around existing native loops and checked Cells runner."""

import sys
from pathlib import Path

import paired_context as ctx

c, io = ctx.c, ctx.io


def native(view, output):
    import betse
    import feedback_native as driver
    import numpy as np
    from ruamel.yaml import YAML

    package = Path(betse.__file__).resolve().parent
    installed = {"betse/" + str(p.relative_to(package)): c.sha(p) for p in package.rglob("*.py")}
    expected = {
        n: h
        for n, h in view["preparation_registration"]["upstream"]["files_sha256"].items()
        if n.startswith("betse/") and n.endswith(".py")
    }
    c.require(
        installed == expected and package.is_relative_to(c.REFERENCE_PYTHON.parent.parent),
        "Native installed source differs",
    )
    c.require(
        c.environment()["packages"] == c.locked_reference_packages(), "Native runtime differs"
    )
    with (c.SOURCE / "betse/data/yaml/sim_config.yaml").open() as stream:
        template = YAML(typ="safe").load(stream)
    records, updates = {}, 0
    with np.errstate(over="raise", invalid="raise", divide="raise"):
        for variant in view["preparation_registration"]["transport_protocol"]["variants"]:
            for step in view["protocol"]["native_steps_s"]:
                pair = {}
                key = ctx.feedback.key(variant["id"], step)
                for mode in ("observed", "unobserved"):
                    pair[mode] = driver.run_row(
                        view, variant, step, mode, output, package, template
                    )
                    updates += pair[mode]["steps"]
                exclude = {"mode", "trace", "fresh_probes"}
                c.require(
                    {k: v for k, v in pair["observed"].items() if k not in exclude}
                    == {k: v for k, v in pair["unobserved"].items() if k not in exclude},
                    "Observer changed native state",
                )
                records[key] = {mode: f"native/{key}/{mode}/result.json.gz" for mode in pair}
                print(f"Native {view['history_id']} pair completed: {key}", flush=True)
    c.require(
        not any(n.split(".")[0] in ("cells", "jax", "jaxlib") for n in sys.modules),
        "Native imported Cells",
    )
    return {
        "engine": "unmodified_betse_FULL_INIT_registered_fixture_and_observer",
        "records": records,
        "installed_python_sha256": installed,
        "package_path": str(package),
        "native_runs": 2 * len(records),
        "native_updates": updates,
        "observer_pairs": len(records),
        "trajectory_run": True,
    }


def worker(kind, r, output):
    results = {}
    for name, view in r["views"].items():
        directory = output / name
        if kind == "reference":
            import paired_reference

            directory.mkdir(parents=True, exist_ok=False)
            results[name] = paired_reference.worker(view, directory)
        elif kind == "betse":
            results[name] = native(view, directory)
        else:
            import feedback_cells

            c.require(kind == "cells", "Unknown paired worker")
            results[name] = feedback_cells.worker(view, directory)
    return {"by_history": results, "history_ids": list(results)}
