"""Separate-interpreter instantaneous probes. No ODEs or native cell-world setup."""

import importlib.metadata as metadata
import sys
from pathlib import Path
from types import SimpleNamespace

import pump_reference as ref

c = ref.c


def columns(raw, profile):
    """Convert actual returned densities, retaining the third native return."""
    rows = {}
    for case, values in zip(profile["cases"], raw, strict=True):
        na, k, third = map(float, values)
        area = case["area_m2"]
        rows[case["id"]] = {
            "na_in_fmol_s": na * area * 1e15,
            "k_in_fmol_s": k * area * 1e15,
            "third_out_na_fmol_s": third * area * 1e15,
            "cycles_density_mol_m2_s": -na / 3,
            "inward_current_A": profile["constants"]["F"] * area * (na + k),
        }
    return rows


def native(registration):
    import betse
    import numpy as np
    from betse.science import sim_toolbox

    package = Path(betse.__file__).resolve().parent
    c.require(package.is_relative_to(c.REFERENCE_PYTHON.parent.parent), "Wrong BETSE origin")
    expected = {
        name: digest
        for name, digest in registration["upstream"]["files_sha256"].items()
        if name.startswith("betse/") and name.endswith(".py")
    }
    installed = {f"betse/{p.relative_to(package)}": c.sha(p) for p in package.rglob("*.py")}
    c.require(installed == expected and len(installed) == 332, "Installed BETSE source differs")
    c.require(metadata.version("betse") == "1.5.0", "Wrong BETSE version")
    c.require(c.environment()["packages"] == c.locked_reference_packages(), "Native lock differs")
    results, raw_results = {}, {}
    for name, profile in registration["protocol"]["profiles"].items():
        v = {
            field: np.asarray([row[field] for row in profile["cases"]], dtype=np.float64)
            for field in ref.FIELDS
        }
        parameters = SimpleNamespace(
            **profile["constants"],
            cATP=v["atp_mM"],
            cADP=v["adp_mM"],
            cPi=v["pi_mM"],
            KmNK_Na=v["km_na_mM"],
            KmNK_K=v["km_k_mM"],
            KmNK_ATP=v["km_atp_mM"],
            deltaGATP=v["delta_g0_J_mol"],
            alpha_NaK=v["alpha_mol_m2_s"],
        )
        before = {key: value.copy() for key, value in v.items()}
        parameter_before = {
            key: value.copy() if isinstance(value, np.ndarray) else value
            for key, value in vars(parameters).items()
        }

        def invoke(met, v=v, parameters=parameters):
            return np.stack(
                sim_toolbox.pumpNaKATP(
                    v["na_in_mM"],
                    v["na_out_mM"],
                    v["k_in_mM"],
                    v["k_out_mM"],
                    v["voltage_V"],
                    v["temperature_K"],
                    parameters,
                    v["availability"],
                    met=met,
                ),
                axis=-1,
            )

        raw = invoke(None)
        poisoned_met = invoke(object())  # Invalid metabolism object must remain unused.
        c.require(np.array_equal(raw, poisoned_met), "Native met argument now affects output")
        c.require(
            all(np.array_equal(v[k], value) for k, value in before.items()),
            "Native pump mutated input",
        )
        c.require(
            set(vars(parameters)) == set(parameter_before)
            and all(
                np.array_equal(getattr(parameters, key), value)
                for key, value in parameter_before.items()
            ),
            "Native pump mutated parameters",
        )
        c.require(np.array_equal(raw[:, 2], -raw[:, 0]), "Third return is not outward Na")
        c.require(bool(np.isfinite(raw).all()), "Nonfinite native density")
        results[name], raw_results[name] = columns(raw, profile), raw.tolist()
    c.require(
        not any(n == "cells" or n.startswith("cells.") for n in sys.modules),
        "Native worker imported Cells",
    )
    return {
        "engine": "unmodified_betse_pumpNaKATP",
        "results": {"native": results},
        "raw_density_mol_m2_s": raw_results,
        "input_unchanged": True,
        "met_ignored": True,
        "third_is_outward_na": True,
        "installed_python_sha256": installed,
        "environment": c.environment(),
        "module_path": sim_toolbox.__file__,
        "input_carrier": "vector parameter carrier; prescribed states; no native world",
    }


def prototype(registration):
    import jax
    import jax.numpy as jnp
    import numpy as np
    import pump_array

    c.require(jax.default_backend() == "cpu" and jax.config.x64_enabled, "Need CPU float64")
    c.require(not jax.config.jax_disable_jit, "JIT disabled")
    c.require(
        c.environment()["packages"] == registration["prototype_environment"]["packages"],
        "Prototype environment changed",
    )
    results = {name: {} for name in ref.ENGINES if name != "native"}
    raw_results = {name: {} for name in results}
    for name, profile in registration["protocol"]["profiles"].items():
        data = np.asarray(
            [[row[field] for field in ref.FIELDS] for row in profile["cases"]], dtype=np.float64
        )
        before = data.copy()
        constants = profile["constants"]
        array = jnp.asarray(data)
        outputs = {
            "numpy": pump_array.densities(data, constants, np),
            "jax_eager": pump_array.densities(array, constants, jnp),
            "jax_jit": jax.jit(
                lambda values, constants=constants: pump_array.densities(values, constants, jnp)
            )(array),
        }
        for engine, value in outputs.items():
            raw = np.asarray(value)
            c.require(
                raw.dtype == np.float64 and bool(np.isfinite(raw).all()), "Invalid array result"
            )
            results[engine][name] = columns(raw, profile)
            raw_results[engine][name] = raw.tolist()
        c.require(
            np.array_equal(before, data) and np.array_equal(before, np.asarray(array)),
            "Prototype input changed",
        )
    c.require(
        not any(n in ("cells", "betse") or n.startswith(("cells.", "betse.")) for n in sys.modules),
        "Prototype imported a simulator",
    )
    return {
        "engine": "validation_only_nak_array_law",
        "results": results,
        "raw_density_mol_m2_s": raw_results,
        "input_unchanged": True,
        "environment": c.environment(),
        "dtype": "float64",
        "backend": "cpu",
    }
