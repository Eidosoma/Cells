"""Regenerate the pinned seven-cell preparation without inventing old evidence."""

import contextlib
import copy
import math
import sys
from pathlib import Path

import common as u


def native_setup(workspace):
    import betse
    import numpy as np
    from ruamel.yaml import YAML

    u.module_path("pump_loop_preflight")
    import pump_native as native

    native.c.SOURCE = workspace / "betse-v1.5.0"
    native.c.REFERENCE_PYTHON = workspace / "venv-betse/bin/python"
    source = native.c.inspect_source()
    package = Path(betse.__file__).resolve().parent
    actual = {"betse/" + str(p.relative_to(package)): u.sha(p) for p in package.rglob("*.py")}
    expected = {
        k: v
        for k, v in source["files_sha256"].items()
        if k.startswith("betse/") and k.endswith(".py")
    }
    u.need(actual == expected, "Installed BETSE source differs from the pinned checkout")
    u.need(package.is_relative_to(workspace / "venv-betse"), "Wrong native environment")
    u.need(
        native.c.environment()["packages"] == native.c.locked_reference_packages(),
        "Native package lock changed",
    )
    with (native.c.SOURCE / "betse/data/yaml/sim_config.yaml").open() as handle:
        template = YAML(typ="safe").load(handle)
    return native, package, template, source, np


def seed(output, workspace):
    native, package, template, source, np = native_setup(workspace)
    from betse.science.parameters import Parameters
    from betse.science.simrunner import SimRunner
    from ruamel.yaml import YAML

    protocol = u.read(native.ctx.PROTOCOL)
    directory = output / "seed"
    directory.mkdir()
    yaml = YAML(typ="safe")
    yaml.default_flow_style = False
    with (directory / "native.yaml").open("x") as handle:
        yaml.dump(
            native.ctx.configuration(template, protocol, protocol["variants"][0], directory), handle
        )
    p = Parameters()
    p.load(str(directory / "native.yaml"))
    p.F, p.R = (protocol["constants"][k] for k in ("F", "R"))
    np.random.seed(protocol["seed"])
    cells = SimRunner(p).seed().cells
    geometry = dict(
        cell_count=len(cells.cell_i),
        membrane_count=len(cells.mem_i),
        cell_centres_m=cells.cell_centres.tolist(),
        cell_volumes_m3=cells.cell_vol.tolist(),
        cell_areas_m2=cells.cell_sa.tolist(),
        membrane_owners=cells.mem_to_cells.tolist(),
        membrane_areas_m2=cells.mem_sa.tolist(),
    )
    u.need(
        geometry["cell_count"] == 7 and geometry["membrane_count"] == 30,
        "Unexpected seeded geometry",
    )
    prepared = dict(protocol=protocol, expected_geometry=geometry, upstream=source)
    u.write(output / "native_preparation.json", prepared)
    rows = {}
    with np.errstate(over="raise", invalid="raise", divide="raise"):
        for variant in protocol["variants"]:
            for mode in protocol["modes"]:
                row = native.run_row(
                    prepared, variant, mode, output / "baseline", package, template
                )
                rows[variant["id"] + "/" + mode] = row
            a, b = (rows[variant["id"] + "/" + mode] for mode in protocol["modes"])
            u.need(
                all(a[k] == b[k] for k in a if k not in ("mode", "trace")),
                "Baseline observer interference",
            )
            print("Fresh baseline:", variant["id"], flush=True)
    u.module_path("pump_matched_pilot")
    import pilot_context

    cases = {
        v["id"]: pilot_context.case_for(rows[v["id"] + "/observed"], v, end=0.01)
        for v in protocol["variants"]
    }
    result = dict(
        native_preparation=prepared,
        cases=cases,
        rows=rows,
        native_geometry=rows["pump_leak/observed"]["geometry"],
        native_initial={
            v: rows[v + "/observed"]["trace"]["initial"]["physical"] for v in u.VARIANTS
        },
        baseline_runs=12,
        observed_updates=48,
        observer_pairs=6,
        historical_artifacts_recovered=False,
        prior_qualification_inherited=False,
    )
    u.write(output / "preparation.json", result)
    return dict(
        baseline_runs=12, observed_updates=48, observer_pairs=6, source_revision=source["revision"]
    )


def capture(
    output,
    workspace,
    preparation,
    name,
    index,
    mode,
    duration,
    *,
    stream_bytes=128 * 1024**2,
    dt_s=None,
    checkpoint_mode="native",
):
    maximum_stream = (
        2048 if dt_s is not None and checkpoint_mode == "numpy_inline_buffers@1" else 1024
    ) * 1024**2
    u.need(
        type(stream_bytes) is int and 32 * 1024**2 <= stream_bytes <= maximum_stream,
        "Native stream allowance exceeds the bounded writer/clock allowance",
    )
    u.need(checkpoint_mode in ("native", "numpy_inline_buffers@1"), "Unknown checkpoint writer")
    u.need(
        dt_s is None
        or (index is None and type(dt_s) is float and math.isfinite(dt_s) and dt_s > 0),
        "Explicit native timestep requires a positive finite float and no range index",
    )
    native, package, template, _, np = native_setup(workspace)
    u.module_path("live_recording")
    from types import SimpleNamespace

    import live_native
    import record_codec

    original = live_native.codec

    def sink(directory, **kwargs):
        u.need(kwargs == {"max_output_bytes": 32 * 1024**2}, "Unexpected recorder options")
        return record_codec.RecordSink(directory, max_output_bytes=stream_bytes)

    prepared = copy.deepcopy(preparation["native_preparation"])
    dt = u.RANGES[name][index] if dt_s is None else dt_s
    prepared["protocol"].update(dt_s=dt, duration_s=duration, steps=round(duration / dt))
    variant = next(v for v in prepared["protocol"]["variants"] if v["id"] == name)
    adapter = contextlib.nullcontext(None)
    if checkpoint_mode != "native":
        # The ordinary science import initializes BETSE's dill class. Do it
        # before installing the adapter, including in a fresh capture worker.
        import betse.science  # noqa: F401

        u.module_path("long_relaxation")
        import pickle_buffers

        adapter = pickle_buffers.inline_arrays()
    # Only the existing recorder's supported aggregate output budget changes.
    live_native.codec = SimpleNamespace(RecordSink=sink)
    try:
        with (
            adapter as checkpoint_facts,
            np.errstate(over="raise", invalid="raise", divide="raise"),
        ):
            result = live_native.run_row(prepared, variant, mode, output, package, template)
    finally:
        live_native.codec = original
    if checkpoint_facts is not None:
        u.need(checkpoint_facts["globals_restored"], "Native checkpoint writer was not restored")
        result["checkpoint_storage"] = checkpoint_facts
    u.need(
        not any(n == "cells" or n.startswith("cells.") for n in sys.modules),
        "Native imported Cells",
    )
    return result
