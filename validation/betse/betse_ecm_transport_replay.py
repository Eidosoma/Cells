"""Fresh native/reference ECM saved-column replay with production denied."""

import argparse
import builtins
import hashlib
import importlib.abc
import json
import os
import sys
from importlib import metadata
from pathlib import Path

BLOCKED = {"cells", "betse", "jax", "jaxlib"}
original_import = builtins.__import__


def guarded(name, *args, **kwargs):
    if name.split(".")[0] in BLOCKED:
        raise ImportError("Production/native package import denied: " + name)
    return original_import(name, *args, **kwargs)


class Guard(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in BLOCKED:
            raise ImportError("Production/native package import denied: " + fullname)


builtins.__import__ = guarded
sys.meta_path.insert(0, Guard())

import numpy as np  # noqa: E402

from validation.betse import betse_ecm_transport_checks as checks  # noqa: E402


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def all_columns(rows, *, ledgers):
    result = {}
    for index, row in enumerate(rows):
        result.update(
            {
                "step_" + str(index) + "." + key: value
                for key, value in checks.columns(row, ledgers=ledgers).items()
            }
        )
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", required=True, choices=("native", "reference"))
    args = parser.parse_args()
    if args.mode == "native":
        from validation.betse import betse_ecm_transport_native as provider
    else:
        from validation.betse import betse_ecm_transport_reference as provider
    directory = Path(os.environ["CELLS_COMPONENT_EVIDENCE"])
    complete = calls = snapshots = env_records = refused = 0
    cases = []
    for path in sorted((directory / "ecm-transport").glob("*.json")):
        record = json.loads(path.read_text())
        inputs = record["inputs"]
        if record["mode"] == "raw_nonfinite_source_refusal" and args.mode == "reference":
            assert record["no_partial_commit"] and not record["binary64_overflow_reference_parity"]
            if record["failure_kind"] == "electroflux_overflow":
                assert min(inputs["initial"]["voltage_V"]) <= -1e6
            else:
                assert np.max(abs(np.asarray(inputs["steps"][0]["electric_x_source"]))) >= 1e308
                assert max(inputs["steps"][0]["boundary_mol_m3"]) >= 1000
            refused += 1
            continue
        proof = provider.evaluate(inputs)
        with np.load(path.with_suffix(".npz"), allow_pickle=False) as arrays:
            if args.mode == "native":
                assert (
                    proof["native_source_sha256"] == record["native_source_sha256"]
                    and proof["RNG_unchanged"]
                )
            if record["mode"] == "complete_source_history":
                assert (
                    record["full_refined_buffers_retained"]
                    and not record["carried_error_allowance"]
                )
                if args.mode == "native":
                    assert proof["failure"] is None and not proof["warnings"]
                    assert proof["source_sites"] == record["native_source_sites"]
                    assert proof["geometry_source_sites"] == record["geometry_source_sites"]
                    numeric = all_columns(proof["history"], ledgers=False)
                    checks.compare(
                        checks.saved(arrays, "actual", record["native_fields"]), numeric, exact=True
                    )
                    checks.compare(
                        checks.saved(arrays, "native", record["native_fields"]), numeric, exact=True
                    )
                    maximum = resolution = 0.0
                else:
                    assert canonical(proof) == canonical(record["reference"])
                    refined = provider.evaluate(inputs, refinement=2)
                    assert canonical(refined) == canonical(record["refined_reference"])
                    wanted, resolved = (
                        all_columns(proof["history"], ledgers=True),
                        all_columns(refined["history"], ledgers=True),
                    )
                    checks.compare(
                        checks.saved(arrays, "reference", record["fields"]), wanted, exact=True
                    )
                    checks.compare(
                        checks.saved(arrays, "refined", record["fields"]), resolved, exact=True
                    )
                    maximum = checks.compare(
                        checks.saved(arrays, "actual", record["fields"]), wanted
                    )
                    resolution = checks.compare(wanted, resolved)
                    assert resolution <= 0.1
                    for row in proof["history"]:
                        assert all(
                            abs(oracle["balance_residual_mol"]) <= 1e-85
                            for oracle in row["conservative_exchange"]
                        )
                assert len(proof["history"]) == record["source_calls"]
                for i, row in enumerate(proof["history"]):
                    assert canonical(checks.metadata(row)) == canonical(record["frame_metadata"][i])
                complete += 1
                calls += len(proof["history"])
                snapshots += sum(len(row["frames"]) for row in proof["history"])
                env_records += sum(len(row["environment_records"]) for row in proof["history"])
                cases.append(
                    dict(
                        case=path.name,
                        maximum_error_fraction=maximum,
                        maximum_reference_resolution_fraction=resolution,
                    )
                )
            else:
                assert (
                    record["mode"] == "raw_nonfinite_source_refusal" and record["no_partial_commit"]
                )
                row = proof["history"][0]
                assert canonical(checks.metadata(row)) == canonical(record["frame_metadata"])
                wanted = checks.columns(row, ledgers=False)
                checks.compare(checks.saved(arrays, "trial", record["fields"]), wanted, exact=True)
                checks.compare(checks.saved(arrays, "native", record["fields"]), wanted, exact=True)
                assert bool(proof["failure"]) == bool(record["native_failure"])
                refused += 1
    assert (complete, calls, snapshots, env_records, refused) == (18, 48, 1248, 132, 2), (
        complete,
        calls,
        snapshots,
        env_records,
        refused,
    )
    loaded = [name for name in sys.modules if name.split(".")[0] in BLOCKED]
    assert not loaded
    files = {}
    for module in tuple(sys.modules.values()):
        name = getattr(module, "__file__", None)
        if name and Path(name).is_file():
            path = Path(name).resolve()
            files[str(path)] = sha(path)
    executable = Path(sys.executable).resolve()
    files[str(executable)] = sha(executable)
    result = dict(
        mode=args.mode,
        complete_cases=complete,
        source_calls=calls,
        complete_snapshots=snapshots,
        environment_records=env_records,
        raw_refusals=refused,
        cases=cases,
        production_imports_denied=True,
        loaded_production_modules=loaded,
        full_refined_buffers_retained=True,
        carried_error_allowance=False,
        physical_material_or_energy_parity=False,
        binary64_overflow_reference_parity=False,
        runtime=dict(
            files=files,
            affinity=sorted(os.sched_getaffinity(0)),
            python=sys.version,
            packages={name: metadata.version(name) for name in ("numpy", "scipy")},
        ),
    )
    with (directory / (args.mode + "-replay.json")).open("x") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "mode",
                    "complete_cases",
                    "source_calls",
                    "complete_snapshots",
                    "environment_records",
                    "raw_refusals",
                )
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
