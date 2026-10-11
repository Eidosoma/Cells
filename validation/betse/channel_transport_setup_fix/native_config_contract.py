"""Real BETSE YAML loader and annotated runtime type contract, without world preparation."""

import argparse
import os
import time
import traceback
import warnings
from pathlib import Path
from typing import get_type_hints

import setup_context as setup

c, t = setup.c, setup.t


def probe(output):
    # This is a configuration/type regression, not a native network initialization
    # or transport result. Actual native initialization belongs to the later capture.
    original = setup.authenticate_preservation()
    import betse
    from beartype.door import is_bearable
    from betse.science.chemistry.networks import MasterOfNetworks
    from betse.science.parameters import Parameters
    from ruamel.yaml import YAML

    package = Path(betse.__file__).resolve().parent
    installed = {f"betse/{p.relative_to(package)}": c.sha(p) for p in package.rglob("*.py")}
    expected = {
        k: v
        for k, v in original["upstream"]["files_sha256"].items()
        if k.startswith("betse/") and k.endswith(".py")
    }
    c.require(
        installed == expected and package.is_relative_to(c.REFERENCE_PYTHON.parent.parent),
        "Wrong native runtime/source",
    )
    hint = get_type_hints(MasterOfNetworks.tissue_init)["config_substances"]
    c.require(
        hasattr(MasterOfNetworks.tissue_init, "__wrapped__"), "Native type wrapper is missing"
    )
    yaml = YAML(typ="safe")
    yaml.default_flow_style = False
    with (c.SOURCE / "betse/data/yaml/sim_config.yaml").open() as handle:
        template = yaml.load(handle)
    rows = []
    for variant in original["protocol"]["variants"]:
        folder = output / variant["id"]
        folder.mkdir(exist_ok=False)
        args = (template, original["base_protocol"], original["protocol"], variant, folder)
        old, corrected = t.configuration(*args), setup.configuration(*args)
        expected_config = t.configuration(*args)
        expected_config["general network"]["biomolecules"] = []
        c.require(corrected == expected_config, "Unexpected additional configuration change")
        loaded, hashes = {}, {}
        for name, conf in (("original", old), ("corrected", corrected)):
            path = folder / f"{name}.yaml"
            with path.open("x") as handle:
                yaml.dump(conf, handle)
            digest = c.sha(path)
            p = Parameters()
            p.load(str(path))
            c.require(c.sha(path) == digest, "Native loader rewrote input")
            loaded[name] = {
                "biomolecules": p.network_config["biomolecules"],
                "accepted_by_tissue_init_annotation": is_bearable(
                    p.network_config["biomolecules"], hint
                ),
                "network_enabled": p.molecules_enabled,
                "temperature_K": p.T,
                "init_dt_s": p.init_time_step,
                "sim_dt_s": p.sim_time_step,
            }
            hashes[name] = digest
        c.require(
            loaded["original"]["biomolecules"] is None
            and loaded["original"]["accepted_by_tissue_init_annotation"] is False,
            "Original null input no longer reproduces the rejected native type contract",
        )
        c.require(
            loaded["corrected"]["biomolecules"] == []
            and loaded["corrected"]["accepted_by_tissue_init_annotation"] is True,
            "Corrected empty sequence violates the native type contract",
        )
        rows.append({"id": variant["id"], "loaded": loaded, "yaml_sha256": hashes})
    return {
        "schema": "cells.betse_channel_configuration_contract@1",
        "status": "pass",
        "rows": rows,
        "native_annotation": str(hint),
        "installed_python_sha256": installed,
        "native_method_file": str(package / "science/chemistry/networks.py"),
        "native_parameter_loader_used": True,
        "native_world_seeded": False,
        "native_network_initialized": False,
        "transport_executed": False,
        "environment": c.environment(),
        "cpu_affinity": sorted(os.sched_getaffinity(0)),
        "amendment_sha256": c.sha(setup.AMENDMENT),
        "script_sha256": c.sha(Path(__file__)),
        "configuration_provider_sha256": c.sha(Path(setup.__file__)),
    }


def main(output):
    c.require(output.is_dir() and not any(output.iterdir()), "Use an empty contract-test directory")
    began = time.monotonic()
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = probe(output)
        result["warnings"] = [
            {"category": w.category.__name__, "message": str(w.message)} for w in caught
        ]
        result["elapsed_seconds"] = time.monotonic() - began
        c.write(output / "result.json", result)
        c.require(result["warnings"] == [], "Configuration regression emitted warnings")
    except BaseException:
        c.write(
            output / "failure.json",
            {
                "status": "configuration_contract_failed",
                "traceback": traceback.format_exc(),
                "automatic_retry": False,
            },
        )
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    main(parser.parse_args().output.resolve())
