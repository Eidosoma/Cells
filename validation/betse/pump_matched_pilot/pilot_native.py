"""Refined native driver capture through the frozen preparation adapter."""

import copy
import importlib
import sys
from pathlib import Path

import pilot_context as ctx

sys.path.insert(0, str(ctx.HERE.parent / "pump_loop_preflight"))
native = importlib.import_module("pump_native")
c = ctx.c


def worker(r, output):
    import betse
    import numpy as np
    from ruamel.yaml import YAML

    package = Path(betse.__file__).resolve().parent
    installed = {f"betse/{p.relative_to(package)}": c.sha(p) for p in package.rglob("*.py")}
    c.require(
        installed
        == {
            k: v
            for k, v in r["native_preparation"]["upstream"]["files_sha256"].items()
            if k.startswith("betse/") and k.endswith(".py")
        }
        and package.is_relative_to(c.REFERENCE_PYTHON.parent.parent),
        "Installed native source changed",
    )
    c.require(c.environment()["packages"] == c.locked_reference_packages(), "Native package lock")
    with (c.SOURCE / "betse/data/yaml/sim_config.yaml").open() as stream:
        template = YAML(typ="safe").load(stream)
    records = {}
    with np.errstate(over="raise", invalid="raise", divide="raise"):
        for step in r["protocol"]["native_steps_s"]:
            current = copy.deepcopy(r["native_preparation"])
            current["protocol"].update(
                dt_s=step,
                duration_s=r["protocol"]["duration_s"],
                steps=round(r["protocol"]["duration_s"] / step),
            )
            directory = output / "native_steps" / f"dt_{step:.8g}"
            for variant in current["protocol"]["variants"]:
                observed = None
                for mode in ("observed", "unobserved"):
                    row = native.run_row(current, variant, mode, directory, package, template)
                    if mode == "observed":
                        observed = row
                    else:
                        for name in set(row) - {"mode", "trace"}:
                            c.require(
                                observed[name] == row[name], "Native observer interference: " + name
                            )
                    path = directory / "native" / variant["id"] / mode / "result.json"
                    records[ctx.key(variant["id"], step) + "/" + mode] = str(
                        path.relative_to(output)
                    )
                    used = sum(p.stat().st_size for p in output.rglob("*") if p.is_file())
                    c.require(
                        used < r["protocol"]["resources"]["artifact_bytes"] - 64 * 1024**2,
                        "Native disk budget",
                    )
                print("native pair captured: " + ctx.key(variant["id"], step), flush=True)
    c.require(
        len(records) == 36 and not any(n == "cells" or n.startswith("cells.") for n in sys.modules),
        "Native scope/isolation",
    )
    return dict(
        engine="unmodified_betse_FULL_INIT_matched_constants",
        records=records,
        native_runs=36,
        observer_pairs=18,
        installed_python_sha256=installed,
        environment=c.environment(),
    )
