"""What the native spatial drivers share: the initial-condition hook, the seeded configuration and
the checks of the pinned BETSE environment. Runs in that environment and imports no Cells module.

Copied, with only the names of modules changed, from four REF-era modules that left with the legacy
cleanup, so that the drivers of tissue_contact, spatial_active, junction_transport and
junction_trajectory keep running. Each copy names its source, whose last state is at the tag
pre-cleanup-2026-11-25.
"""

import copy
import dis
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE / "fresh_rerun")]
import common as u  # noqa: E402
import contact as c  # noqa: E402

PROTOCOL = HERE / "pump_loop_preflight/protocol.json"
BASE_PROTOCOL = HERE / "alignment_protocol.json"


def successful_return(frame):
    """From channel_loop_preparation/loop_observer.py."""
    # Python's profiler also emits "return" when a frame unwinds an exception.
    # The pinned CPython 3.13 bytecode distinguishes it from a real return. Never
    # apply a fixture, or label a step complete, while native setup is failing.
    return dis.opname[frame.f_code.co_code[frame.f_lasti]] in ("RETURN_VALUE", "RETURN_CONST")


class InitialConditionHook:
    """Set the fixture once after real native initialization, in both modes.

    The initializer is explicitly mutating experimental setup, NOT an observer.
    No native methods, clocks, controls or integrator statements are replaced.

    From channel_loop_preparation/loop_observer.py.
    """

    def __init__(self, phase, science, initialise, observer=None):
        self.phase, self.initialise, self.observer = phase, initialise, observer
        self.source = str(Path(science).resolve() / "sim.py")
        self.calls = self.returns = 0
        self.hook = self._dispatch

    def __enter__(self):
        c.require(sys.getprofile() is None and self.calls == 0, "Occupied/reused profiling hook")
        sys.setprofile(self.hook)
        return self

    def __exit__(self, kind, error, traceback):
        active = sys.getprofile()
        sys.setprofile(None)
        if self.observer is not None:
            self.observer.loop_frame = None
        if kind is None:
            c.require(
                active is self.hook and self.calls == self.returns == 1,
                "Initial-condition lifecycle incomplete",
            )
            if self.observer is not None:
                self.observer.validate_complete()
        return False

    def _dispatch(self, frame, event, argument):
        if (
            frame.f_code.co_filename == self.source
            and frame.f_locals.get("self") is self.phase.sim
            and frame.f_code.co_name == "init_dynamics"
        ):
            if event == "call":
                self.calls += 1
                c.require(self.calls == 1, "Repeated native initialization")
            elif event == "return" and successful_return(frame):
                self.returns += 1
                c.require(self.calls == self.returns == 1, "Unexpected initialization return")
                self.initialise(self.phase)
        if self.observer is not None:
            self.observer.observe(frame, event, argument)


def base_configuration(base, protocol, config_dir=c.HERE):
    """Only declared YAML overrides; resolve existing geo asset paths, not code.

    From alignment.py, where it is named configuration.
    """
    conf = copy.deepcopy(base)
    for path, value in protocol["yaml_overrides"]:
        target = conf
        for key in path[:-1]:
            target = target[key]
        c.require(path[-1] in target, f"Unknown YAML option: {path}")
        target[path[-1]] = value

    def assets(value):
        if isinstance(value, dict):
            return {k: assets(v) for k, v in value.items()}
        if isinstance(value, list):
            return [assets(v) for v in value]
        if isinstance(value, str) and value.startswith(("geo/", "extra_configs/")):
            # BETSE's pathname join requires relative paths, even for disabled SVG input.
            return os.path.relpath(c.SOURCE / "betse/data/yaml" / value, config_dir)
        return value

    return assets(conf)


def configuration(template, p, variant, directory):
    """The seven-cell preparation's YAML configuration. From pump_loop_preflight/pump_context.py."""
    base = c.read(BASE_PROTOCOL)
    conf = base_configuration(template, base, directory)
    conf["variable settings"]["temperature"] = p["temperature_K"]
    conf["internal parameters"]["alpha_NaK"] = p["alpha_mol_per_m2_s"] if variant["pump"] else 0.0
    conf["internal parameters"]["substances affect Vmem"] = True
    conf["general network"] = dict.fromkeys(
        ("reactions", "transporters", "channels", "modulators"), None
    ) | {"implement network": False, "biomolecules": []}
    for block in ("init time settings", "sim time settings"):
        conf[block].update(
            {"time step": p["dt_s"], "total time": p["duration_s"], "sampling rate": p["dt_s"]}
        )
    d = conf["tissue profile definition"]["tissue"]["default"]["diffusion constants"]
    for name, permeability in zip(base["expected_species"], p["permeability_m_per_s"], strict=True):
        d["Dm_" + name] = permeability * base["thickness_m"] if variant["leak"] else 0.0
    return conf


def native_setup(workspace):
    """The pinned checkout, installation and package lock, checked; with the template and numpy.

    From fresh_rerun/prepare.py, without its first result: the module that held c and configuration.
    """
    import betse
    import numpy as np
    from ruamel.yaml import YAML

    c.SOURCE = workspace / "betse-v1.5.0"
    c.REFERENCE_PYTHON = workspace / "venv-betse/bin/python"
    source = c.inspect_source()
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
        c.environment()["packages"] == c.locked_reference_packages(),
        "Native package lock changed",
    )
    with (c.SOURCE / "betse/data/yaml/sim_config.yaml").open() as handle:
        template = YAML(typ="safe").load(handle)
    return package, template, source, np
