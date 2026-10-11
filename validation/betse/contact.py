"""Offline, source-bound BETSE passive-law contact. No production code or ODE changes."""

import argparse
import ast
import hashlib
import importlib.metadata as metadata
import json
import math
import os
import platform
import subprocess
import sys
import time
import traceback
import warnings
import zipfile
from datetime import UTC, datetime
from decimal import Decimal, localcontext
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SOURCE = ROOT / "upstream/betse-v1.5.0"
REFERENCE_PYTHON = ROOT / "upstream/betse-venv/bin/python"
CELLS_PYTHON = ROOT / ".venv/bin/python"
PRESERVATION = ROOT / "reports/ref-003a-preservation.json"
REVISION = "5269a714aa2593ed2a6708c4516289977d8ae1a2"
ADAPTER_FILES = ("contact.py", "protocol.json", "requirements-lock.txt", "test_contact.py")
PROFILES = ("source_constants", "matched_constants")
CELLS_BACKENDS = ("numpy", "jax_eager", "jax_jit")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def read(path):
    return json.loads(
        Path(path).read_text(),
        object_pairs_hook=unique_object,
        parse_constant=lambda value: require(False, f"Nonfinite JSON value: {value}"),
    )


def write(path, value):
    with Path(path).open("x") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")


def adapter_hashes():
    return {name: sha(HERE / name) for name in ADAPTER_FILES}


def authenticate_cells():
    preserved = read(PRESERVATION)
    require(preserved["status"] == "pass", "Missing development preservation")
    for name, digest in preserved["implementation_files_sha256"].items():
        require(sha(ROOT / name) == digest, f"Accepted implementation changed: {name}")
    require(
        sha(ROOT / preserved["preserved_capsule"]) == preserved["preserved_capsule_sha256"],
        "Accepted development capsule changed",
    )
    return preserved


def inspect_source():
    def git(*args):
        return subprocess.check_output(["git", "-C", str(SOURCE), *args], text=True).strip()

    require(git("rev-parse", "HEAD") == REVISION, "Wrong BETSE revision")
    require(git("rev-parse", "v1.5.0^{commit}") == REVISION, "Wrong BETSE tag")
    require(not git("status", "--porcelain", "--untracked-files=all"), "BETSE checkout is dirty")
    names = git("ls-files").splitlines()
    tree = ast.parse((SOURCE / "betse/science/parameters.py").read_text())
    parameter_class = next(
        n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Parameters"
    )
    loader = next(
        n for n in parameter_class.body if isinstance(n, ast.FunctionDef) and n.name == "load"
    )
    constants = {}
    for node in ast.walk(loader):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (
                    isinstance(target, ast.Attribute)
                    and isinstance(target.value, ast.Name)
                    and target.value.id == "self"
                    and target.attr in ("F", "R")
                ):
                    require(target.attr not in constants, "Ambiguous source constant assignment")
                    constants[target.attr] = float(ast.literal_eval(node.value))
    require(constants == {"F": 96485.0, "R": 8.314}, "Unexpected source-declared constants")
    return {
        "repository": "https://github.com/betsee/betse.git",
        "revision": REVISION,
        "source_constants": constants,
        "files_sha256": {name: sha(SOURCE / name) for name in names},
        "license_sha256": sha(SOURCE / "LICENSE"),
    }


def oracle(case, constants, precision=70):
    """Independent decimal symmetric-exponential constant-field expression, fmol/s."""
    with localcontext() as context:
        context.prec = precision
        d = lambda value: Decimal(str(value))  # noqa: E731
        x = (
            d(case["valence"])
            * d(constants["F"])
            * d(case["voltage_V"])
            / (d(constants["R"]) * d(case["temperature_K"]))
        )
        ci, co = d(case["inside_mM"]), d(case["outside_mM"])
        if x == 0:
            density_factor = co - ci
        else:
            half = (x / 2).exp()
            density_factor = x * (co / half - ci * half) / (half - 1 / half)
        return float(
            d(case["area_m2"]) * d(case["permeability_m_per_s"]) * density_factor / d(1e-15)
        )


def reversal(case, constants):
    with localcontext() as context:
        context.prec = 70
        d = lambda value: Decimal(str(value))  # noqa: E731
        return float(
            d(constants["R"])
            * d(case["temperature_K"])
            * (d(case["outside_mM"]) / d(case["inside_mM"])).ln()
            / (d(case["valence"]) * d(constants["F"]))
        )


def build_cases(protocol):
    require(protocol["schema"] == "cells.betse_passive_contact_protocol@1", "Wrong protocol")
    require(protocol["upstream_revision"] == REVISION, "Wrong protocol source")
    cases = []
    for species in protocol["species"]:
        base = {k: v for k, v in species.items() if k != "id"} | {
            "species": species["id"],
            "temperature_K": protocol["temperature_K"],
            "area_m2": protocol["area_m2"],
            "thickness_m": protocol["membrane_thickness_m"],
        }

        def add(label, *, base=base, species_id=species["id"], **changes):
            cases.append(base | {"id": f"{species_id}/{label}", "voltage_V": -0.04} | changes)

        for index, voltage in enumerate(protocol["voltage_grid_V"]):
            add(f"voltage_{index}", voltage_V=voltage)
        for profile in PROFILES:
            add(f"reversal_{profile}", voltage_V=reversal(base, protocol["profiles"][profile]))
        add("blocked", permeability_m_per_s=0.0)
        add("reversed", inside_mM=base["outside_mM"], outside_mM=base["inside_mM"], voltage_V=0.04)
        add("double_area", area_m2=2 * base["area_m2"])
        add("double_thickness", thickness_m=2 * base["thickness_m"])
        for label, voltage in (("zero", 0.0), ("negative", -1e-12), ("positive", 1e-12)):
            add(
                f"equal_{label}",
                inside_mM=protocol["equal_concentration_mM"],
                outside_mM=protocol["equal_concentration_mM"],
                voltage_V=voltage,
            )
        constants = protocol["profiles"]["matched_constants"]
        extreme = (
            protocol["domain_probe_abs_zFV_over_RT"]
            * constants["R"]
            * base["temperature_K"]
            / constants["F"]
        )
        add("domain_negative", voltage_V=-extreme)
        add("domain_positive", voltage_V=extreme)
    require(len(cases) == protocol["expected_cases"], "Unexpected probe count")
    require(len({c["id"] for c in cases}) == len(cases), "Duplicate probe ID")
    for case in cases:
        require(case["valence"] in (-1, 1), "Probe valence must be monovalent")
        for name, value in case.items():
            if name in ("id", "species"):
                continue
            require(type(value) in (int, float) and math.isfinite(value), f"Invalid {name}")
            if name not in ("valence", "voltage_V", "permeability_m_per_s"):
                require(value > 0, f"Nonpositive {name}")
        require(case["permeability_m_per_s"] >= 0, "Negative permeability")
        for constants in protocol["profiles"].values():
            x = (
                case["valence"]
                * constants["F"]
                * case["voltage_V"]
                / (constants["R"] * case["temperature_K"])
            )
            require(
                abs(x) <= protocol["domain_max_abs_zFV_over_RT"], "Probe outside voltage domain"
            )
    return cases


def reference_inputs(cases):
    return {
        "cA": [c["outside_mM"] for c in cases],
        "cB": [c["inside_mM"] for c in cases],
        "Dc": [c["permeability_m_per_s"] * c["thickness_m"] for c in cases],
        "d": [c["thickness_m"] for c in cases],
        "zc": [float(c["valence"]) for c in cases],
        "vBA": [c["voltage_V"] for c in cases],
        "T": [c["temperature_K"] for c in cases],
        "rho": [1.0 for _ in cases],
    }


def environment():
    return {
        "python": platform.python_version(),
        "executable": sys.executable,
        "packages": {d.metadata["Name"]: d.version for d in metadata.distributions()},
    }


def locked_reference_packages():
    pairs = [
        line.split("==")
        for line in (HERE / "requirements-lock.txt").read_text().splitlines()
        if line and not line.startswith("#")
    ]
    return dict(pairs) | {"betse": "1.5.0"}


def validate_provenance(registration, upstream, cells):
    expected = {
        name: digest
        for name, digest in registration["upstream"]["files_sha256"].items()
        if name.startswith("betse/") and name.endswith(".py")
    }
    require(upstream["engine"] == "unmodified_betse_electroflux", "Wrong reference engine")
    require(
        upstream["installed_python_sha256"] == expected,
        "Installed upstream source evidence differs",
    )
    require(
        upstream["environment"]["packages"] == locked_reference_packages(),
        "Reference dependency lock differs",
    )
    require(upstream["environment"]["python"] == "3.13.5", "Reference Python differs")
    require(
        Path(upstream["environment"]["executable"]) == REFERENCE_PYTHON,
        "Reference interpreter differs",
    )
    require(
        Path(upstream["module_path"]).is_relative_to(REFERENCE_PYTHON.parent.parent),
        "Reference module origin differs",
    )
    require(cells["engine"] == "unchanged_cells_ghk_leak", "Wrong Cells engine")
    require(
        cells["accepted_runtime"] == registration["cells_runtime"], "Cells runtime evidence differs"
    )
    module = ROOT / "src/cells/processes/electrochemistry.py"
    require(
        Path(cells["module_path"]) == module and cells["module_sha256"] == sha(module),
        "Cells source evidence differs",
    )


def reference_worker(registration):
    import betse
    import numpy as np
    from betse.science import sim_toolbox

    require(metadata.version("betse") == "1.5.0", "Unexpected installed BETSE version")
    package = Path(betse.__file__).resolve().parent
    require(
        package.is_relative_to(REFERENCE_PYTHON.parent.parent),
        "BETSE import outside isolated environment",
    )
    source_files = registration["upstream"]["files_sha256"]
    expected = {
        name: digest
        for name, digest in source_files.items()
        if name.startswith("betse/") and name.endswith(".py")
    }
    installed = {f"betse/{p.relative_to(package)}": sha(p) for p in package.rglob("*.py")}
    require(installed == expected, "Installed BETSE Python differs from clean pinned checkout")
    require(
        Path(sim_toolbox.electroflux.__code__.co_filename).resolve()
        == package / "science/sim_toolbox.py",
        "Unexpected function origin",
    )
    cases, protocol = registration["cases"], registration["protocol"]
    results = {}
    for profile in PROFILES:
        inputs = {k: np.asarray(v, dtype=np.float64) for k, v in reference_inputs(cases).items()}
        before = {k: v.tolist() for k, v in inputs.items()}
        constants = protocol["profiles"][profile]
        # A declared F/R input carrier, not a simulated BETSE Parameters/Simulator object.
        parameters = SimpleNamespace(**constants)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            density = sim_toolbox.electroflux(p=parameters, **inputs)
        require(
            density.dtype == np.float64 and density.shape == (len(cases),),
            "Unexpected upstream output shape/dtype",
        )
        amount = density * np.asarray([c["area_m2"] for c in cases]) / 1e-15
        results[profile] = {
            "dtype": str(density.dtype),
            "shape": list(density.shape),
            "constants": constants,
            "inputs_before": before,
            "inputs_after": {k: v.tolist() for k, v in inputs.items()},
            "raw_density_mol_per_m2_s": density.tolist(),
            "flux_fmol_per_s": amount.tolist(),
            "derived_inward_current_A": (
                amount * np.asarray([c["valence"] for c in cases]) * constants["F"] * 1e-15
            ).tolist(),
            "warnings": [
                {"category": w.category.__name__, "message": str(w.message)} for w in caught
            ],
        }
    require(
        not any(n == "cells" or n.startswith("cells.") for n in sys.modules),
        "Reference worker imported Cells",
    )
    return {
        "engine": "unmodified_betse_electroflux",
        "case_ids": [c["id"] for c in cases],
        "parameter_carrier": "SimpleNamespace(F,R); no simulator configuration loaded",
        "environment": environment(),
        "module_path": sim_toolbox.__file__,
        "installed_python_sha256": installed,
        "results": results,
    }


def cells_worker(registration):
    import jax
    import jax.numpy as jnp
    import numpy as np

    from cells.io import runtime_identity
    from cells.processes import electrochemistry as process

    require(jax.default_backend() == "cpu" and jax.config.x64_enabled, "Require CPU float64")
    require(not jax.config.jax_disable_jit, "JIT has been disabled")
    require(
        runtime_identity() == read(PRESERVATION)["runtime"],
        "Cells runtime differs from accepted build",
    )
    require(
        Path(process.__file__).resolve() == ROOT / "src/cells/processes/electrochemistry.py",
        "Unexpected Cells import path",
    )
    require(
        {"F": process.F, "R": process.R}
        == registration["protocol"]["profiles"]["matched_constants"],
        "Unexpected Cells constants",
    )
    cases = registration["cases"]
    names = (
        "inside_mM",
        "outside_mM",
        "voltage_V",
        "valence",
        "temperature_K",
        "area_m2",
        "permeability_m_per_s",
    )
    inputs = [np.asarray([c[name] for c in cases], dtype=np.float64) for name in names]
    inputs.append(np.ones(len(cases), dtype=np.float64))
    before = [a.copy() for a in inputs]
    values = {
        "numpy": process.ghk_leak(*inputs, xp=np),
        "jax_eager": process.ghk_leak(*[jnp.asarray(a) for a in inputs]),
        "jax_jit": jax.jit(process.ghk_leak)(*[jnp.asarray(a) for a in inputs]),
    }
    results = {}
    for name, value in values.items():
        value = np.asarray(value)
        require(
            value.dtype == np.float64 and value.shape == (len(cases),),
            "Unexpected Cells output shape/dtype",
        )
        results[name] = {
            "dtype": str(value.dtype),
            "shape": list(value.shape),
            "flux_fmol_per_s": value.tolist(),
            "derived_inward_current_A": (value * inputs[3] * process.F * 1e-15).tolist(),
        }
    require(
        all(a.tobytes() == b.tobytes() for a, b in zip(inputs, before, strict=True)),
        "Cells mutated inputs",
    )
    require(
        not any(n == "betse" or n.startswith("betse.") for n in sys.modules),
        "Cells worker imported BETSE",
    )
    return {
        "engine": "unchanged_cells_ghk_leak",
        "case_ids": [c["id"] for c in cases],
        "environment": environment(),
        "accepted_runtime": runtime_identity(),
        "module_path": process.__file__,
        "module_sha256": sha(process.__file__),
        "device": "cpu",
        "x64_enabled": True,
        "jit_disabled": False,
        "input_arrays_unchanged": True,
        "results": results,
    }


def normalized_error(actual, expected, absolute, relative):
    require(
        type(actual) in (int, float) and math.isfinite(actual), "Nonfinite or nonnumeric result"
    )
    require(math.isfinite(expected) and absolute > 0 and relative >= 0, "Invalid comparison")
    return abs(actual - expected) / (absolute + relative * abs(expected))


def evaluate(registration, upstream, cells):
    protocol, cases = registration["protocol"], registration["cases"]
    require(cases == build_cases(protocol), "Registered probe definitions differ")
    ids = [c["id"] for c in cases]
    require(upstream["case_ids"] == cells["case_ids"] == ids, "Output case coverage/order differs")
    require(set(upstream["results"]) == set(PROFILES), "Missing upstream profile")
    require(set(cells["results"]) == set(CELLS_BACKENDS), "Missing Cells backend")
    absolute = protocol["absolute_flux_tolerance_fmol_per_s"]
    current_absolute = protocol["absolute_current_tolerance_A"]
    relative = protocol["relative_tolerance"]
    comparisons = []

    def compare(label, actual, expected, *, current=False):
        score = normalized_error(
            actual, expected, current_absolute if current else absolute, relative
        )
        comparisons.append(
            {
                "id": label,
                "actual": actual,
                "expected": expected,
                "normalized_error": score,
                "pass": score <= 1,
            }
        )

    oracles = {
        profile: [
            oracle(c, protocol["profiles"][profile], protocol["decimal_precision"]) for c in cases
        ]
        for profile in PROFILES
    }
    contexts = {f"betse/{p}": (r, p) for p, r in upstream["results"].items()}
    contexts |= {f"cells/{p}": (r, "matched_constants") for p, r in cells["results"].items()}
    mutation_rows = []
    for profile, result in upstream["results"].items():
        require(result["constants"] == protocol["profiles"][profile], "Reference constants differ")
        require(not result["warnings"], "Upstream numerical warning")
        before = reference_inputs(cases)
        after = {
            k: ([x + 1e-25 for x in v] if k in ("zc", "vBA") else v) for k, v in before.items()
        }
        require(
            result["inputs_before"] == before and result["inputs_after"] == after,
            "Upstream input mapping/mutation differs",
        )
        require(
            len(result["raw_density_mol_per_m2_s"]) == len(cases), "Raw density coverage differs"
        )
        for index, case in enumerate(cases):
            density = result["raw_density_mol_per_m2_s"][index]
            compare(
                f"mapping/{profile}/{case['id']}",
                result["flux_fmol_per_s"][index],
                density * case["area_m2"] / 1e-15,
            )
        mutation_rows = [
            ids[i]
            for i, (a, b) in enumerate(zip(before["vBA"], after["vBA"], strict=True))
            if a != b
        ]
    require(
        cells["input_arrays_unchanged"] is True
        and cells["device"] == "cpu"
        and cells["x64_enabled"] is True
        and cells["jit_disabled"] is False,
        "Cells execution context differs",
    )
    for name, (result, profile) in contexts.items():
        require(
            result["dtype"] == "float64" and result["shape"] == [len(cases)],
            "Output dtype/shape differs",
        )
        require(
            len(result["flux_fmol_per_s"]) == len(result["derived_inward_current_A"]) == len(cases),
            "Output coverage differs",
        )
        constants = protocol["profiles"][profile]
        for i, case in enumerate(cases):
            actual = result["flux_fmol_per_s"][i]
            expected = oracles[profile][i]
            compare(f"oracle/{name}/{case['id']}", actual, expected)
            compare(
                f"current/{name}/{case['id']}",
                result["derived_inward_current_A"][i],
                expected * case["valence"] * constants["F"] * 1e-15,
                current=True,
            )
        rates = dict(zip(ids, result["flux_fmol_per_s"], strict=True))
        for species in protocol["species"]:
            prefix = species["id"]
            require(rates[f"{prefix}/blocked"] == 0.0, "Blocked route is not exactly zero")
            compare(f"zero/{name}/{prefix}", rates[f"{prefix}/equal_zero"], 0.0)
            compare(f"nernst/{name}/{prefix}", rates[f"{prefix}/reversal_{profile}"], 0.0)
            for label, factor in (("reversed", -1), ("double_area", 2), ("double_thickness", 1)):
                compare(
                    f"relation/{name}/{prefix}/{label}",
                    rates[f"{prefix}/{label}"],
                    factor * rates[f"{prefix}/voltage_1"],
                )
    paired = upstream["results"]["matched_constants"]
    for backend, result in cells["results"].items():
        for i, case in enumerate(cases):
            compare(
                f"paired/{backend}/{case['id']}",
                paired["flux_fmol_per_s"][i],
                result["flux_fmol_per_s"][i],
            )
            compare(
                f"paired_current/{backend}/{case['id']}",
                paired["derived_inward_current_A"][i],
                result["derived_inward_current_A"][i],
                current=True,
            )
    differences = []
    native = upstream["results"]["source_constants"]["flux_fmol_per_s"]
    compiled = cells["results"]["jax_jit"]["flux_fmol_per_s"]
    for i, case in enumerate(cases):
        actual = native[i] - compiled[i]
        predicted = oracles["source_constants"][i] - oracles["matched_constants"][i]
        # These differences are reporting, not an unqualified same-parameter parity claim.
        differences.append(
            {
                "id": case["id"],
                "native_minus_cells_fmol_per_s": actual,
                "predicted_constant_difference_fmol_per_s": predicted,
                "unexplained_residual_fmol_per_s": actual - predicted,
            }
        )
    return {
        "status": "pass" if all(c["pass"] for c in comparisons) else "failed",
        "case_count": len(cases),
        "comparison_count": len(comparisons),
        "exact_blocking_checks": len(contexts) * len(protocol["species"]),
        "maximum_normalized_error": max(c["normalized_error"] for c in comparisons),
        "maximum_matched_flux_difference_fmol_per_s": max(
            abs(a - b) for a, b in zip(paired["flux_fmol_per_s"], compiled, strict=True)
        ),
        "maximum_native_constant_difference_fmol_per_s": max(
            abs(c["native_minus_cells_fmol_per_s"]) for c in differences
        ),
        "maximum_unexplained_constant_residual_fmol_per_s": max(
            abs(c["unexplained_residual_fmol_per_s"]) for c in differences
        ),
        "voltage_input_mutations_per_upstream_profile": mutation_rows,
        "comparisons": comparisons,
        "native_constant_differences": differences,
        "trajectory_run": False,
        "biological_validation": False,
        "gpu_tested": False,
    }


def worker(kind, output):
    registration = read(output / "registration.json")
    require(registration["adapter_sha256"] == adapter_hashes(), "Adapter changed during capture")
    require(
        registration["preservation_sha256"] == sha(PRESERVATION), "Preservation identity changed"
    )
    if kind == "betse":
        result = reference_worker(registration)
    else:
        result = cells_worker(registration)
    result["registration_sha256"] = sha(output / "registration.json")
    write(output / f"{kind}.json", result)


def capture(output):
    output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    try:
        preserved = authenticate_cells()
        protocol = read(HERE / "protocol.json")
        upstream = inspect_source()
        require(
            upstream["source_constants"] == protocol["profiles"]["source_constants"],
            "Default constants differ",
        )
        registration = {
            "schema": "cells.betse_passive_contact_registration@1",
            "registered_utc": datetime.now(UTC).isoformat(),
            "protocol": protocol,
            "cases": build_cases(protocol),
            "upstream": upstream,
            "preservation_sha256": sha(PRESERVATION),
            "adapter_sha256": adapter_hashes(),
            "cells_runtime": preserved["runtime"],
            "reference_environment_lock_sha256": sha(HERE / "requirements-lock.txt"),
        }
        write(output / "registration.json", registration)
        with zipfile.ZipFile(
            output / "adapter_sources.zip", "x", compression=zipfile.ZIP_DEFLATED
        ) as archive:
            for name in ADAPTER_FILES:
                archive.write(HERE / name, arcname=name)
        base_environment = os.environ | {
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONNOUSERSITE": "1",
            "MPLBACKEND": "Agg",
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",
            "MPLCONFIGDIR": str(output / "matplotlib-cache"),
            "JAX_PLATFORMS": "cpu",
            "JAX_ENABLE_X64": "true",
        }
        base_environment.pop("PYTHONPATH", None)
        for kind, interpreter in (("betse", REFERENCE_PYTHON), ("cells", CELLS_PYTHON)):
            remaining = protocol["total_timeout_seconds"] - (time.monotonic() - started)
            require(remaining > 0, "Contact wall budget exceeded")
            command = [
                "taskset",
                "-c",
                "0-3",
                str(interpreter),
                "-B",
                str(Path(__file__).resolve()),
                "worker",
                kind,
                str(output),
            ]
            with (
                (output / f"{kind}.stdout.log").open("x") as out,
                (output / f"{kind}.stderr.log").open("x") as err,
            ):
                subprocess.run(
                    command,
                    cwd=ROOT,
                    env=base_environment,
                    stdin=subprocess.DEVNULL,
                    stdout=out,
                    stderr=err,
                    timeout=min(protocol["worker_timeout_seconds"], remaining),
                    check=True,
                )
        require(inspect_source() == upstream, "BETSE checkout changed during capture")
        authenticate_cells()
        require(
            registration["adapter_sha256"] == adapter_hashes(), "Adapter changed during capture"
        )
        reference_result, cells_result = read(output / "betse.json"), read(output / "cells.json")
        validate_provenance(registration, reference_result, cells_result)
        result = evaluate(registration, reference_result, cells_result)
        write(output / "comparison.json", result)
        require(
            result["status"] == "pass", "Passive contact comparisons failed; retain comparison.json"
        )
        require(
            time.monotonic() - started <= protocol["total_timeout_seconds"],
            "Contact wall budget exceeded",
        )
        payloads = {str(p.relative_to(output)): sha(p) for p in output.rglob("*") if p.is_file()}
        require(
            sum(p.stat().st_size for p in output.rglob("*") if p.is_file())
            < protocol["max_artifact_bytes"] - 65536,
            "Artifact budget exceeded",
        )
        receipt = {
            "schema": "cells.betse_passive_contact@1",
            "status": "pass",
            "finished_utc": datetime.now(UTC).isoformat(),
            "seconds": time.monotonic() - started,
            "files_sha256": payloads,
            "registration_sha256": sha(output / "registration.json"),
            "comparison_sha256": sha(output / "comparison.json"),
            "scope": protocol["scope"],
            "production_changed": False,
        }
        write(output / "verification.json", receipt)
        print(
            json.dumps(
                {
                    "status": "pass",
                    "cases": result["case_count"],
                    "comparisons": result["comparison_count"],
                    "seconds": receipt["seconds"],
                },
                sort_keys=True,
            )
        )
    except BaseException:
        write(
            output / "failure.json",
            {
                "status": "failed_not_qualified",
                "seconds": time.monotonic() - started,
                "traceback": traceback.format_exc(),
            },
        )
        raise


def audit(output):
    receipt = read(output / "verification.json")
    require(
        receipt["status"] == "pass" and not (output / "failure.json").exists(),
        "Incomplete/failed contact",
    )
    actual = {str(p.relative_to(output)) for p in output.rglob("*") if p.is_file()} - {
        "verification.json"
    }
    require(actual == set(receipt["files_sha256"]), "Contact payload membership differs")
    for name, digest in receipt["files_sha256"].items():
        require(sha(output / name) == digest, f"Contact payload changed: {name}")
    registration = read(output / "registration.json")
    require(
        sha(output / "registration.json") == receipt["registration_sha256"],
        "Registration identity differs",
    )
    require(
        registration["adapter_sha256"] == adapter_hashes(),
        "Use the captured adapter source context",
    )
    require(
        registration["preservation_sha256"] == sha(PRESERVATION), "Preservation identity differs"
    )
    with zipfile.ZipFile(output / "adapter_sources.zip") as archive:
        require(
            len(archive.namelist()) == len(ADAPTER_FILES)
            and set(archive.namelist()) == set(ADAPTER_FILES),
            "Adapter capsule coverage differs",
        )
        for name, digest in registration["adapter_sha256"].items():
            require(
                hashlib.sha256(archive.read(name)).hexdigest() == digest,
                "Adapter capsule bytes differ",
            )
    upstream, cells = read(output / "betse.json"), read(output / "cells.json")
    validate_provenance(registration, upstream, cells)
    require(
        upstream["registration_sha256"]
        == cells["registration_sha256"]
        == receipt["registration_sha256"],
        "Worker registration differs",
    )
    require(
        sha(output / "comparison.json") == receipt["comparison_sha256"],
        "Comparison identity differs",
    )
    evaluated = evaluate(registration, upstream, cells)
    require(
        evaluated == read(output / "comparison.json") and evaluated["status"] == "pass",
        "Saved comparison does not independently replay",
    )
    require(
        0 <= receipt["seconds"] <= registration["protocol"]["total_timeout_seconds"],
        "Contact exceeded its wall budget",
    )
    require(
        sum(p.stat().st_size for p in output.rglob("*") if p.is_file())
        <= registration["protocol"]["max_artifact_bytes"],
        "Artifact budget exceeded",
    )
    authenticate_cells()
    require(inspect_source() == registration["upstream"], "Pinned source provenance differs")
    return {
        "status": "pass",
        "case_count": evaluated["case_count"],
        "comparison_count": evaluated["comparison_count"],
        "payloads": len(actual),
        "verification_sha256": sha(output / "verification.json"),
        "upstream_calls": 0,
        "production_calls": 0,
        "trajectory_calls": 0,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("capture").add_argument("output", type=Path)
    auditor = sub.add_parser("audit")
    auditor.add_argument("output", type=Path)
    auditor.add_argument("--receipt", type=Path, required=True)
    child = sub.add_parser("worker")
    child.add_argument("kind", choices=("betse", "cells"))
    child.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.action == "capture":
        capture(args.output.resolve())
    elif args.action == "worker":
        worker(args.kind, args.output.resolve())
    else:
        audited = audit(args.output.resolve())
        write(args.receipt, audited)
        print(json.dumps(audited, sort_keys=True))
