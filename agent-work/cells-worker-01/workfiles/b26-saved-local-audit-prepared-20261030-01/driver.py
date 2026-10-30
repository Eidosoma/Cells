"""Prepare a B26 saved-data local audit; execute only in a later requested round.

Preparation uses stdlib hashes/JSON/AST only. Execution reads saved arrays and
fresh independent references; it never reruns native BETSE or the Cells model.
"""

import argparse
import ast
import copy
import hashlib
import json
import os
import subprocess
import sys
import traceback
from pathlib import Path

ORIGINAL = Path("/mnt/workspaces/Cells/betse-normal-gated-join-tests-20261030-01")
RESULT_SHA = "d1f11ecf9293bc33e8dc0bf7c73a1aa2d28c1bfb66d9862b1165ce135b112f5b"
INPUTS_SHA = "8e9d7e73c32ae3425b8485de8b2a641e27979d8b2a996052982da2f41fb3fbde"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, data):
    with Path(path).open("x") as stream:
        json.dump(data, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def prepare(directory):
    if sha(ORIGINAL / "result.json") != RESULT_SHA:
        raise ValueError("Original B26 terminal receipt changed")
    if sha(ORIGINAL / "inputs.json") != INPUTS_SHA:
        raise ValueError("Original B26 frozen inputs changed")
    original = json.loads((ORIGINAL / "inputs.json").read_text())
    source = ORIGINAL / "source"
    for name, expected in original["source_hashes"].items():
        if sha(source / name) != expected:
            raise ValueError("Frozen B26 source changed: " + name)
    tree = ast.parse((source / "validation/betse/betse_normal_gated_join_fixtures.py").read_text())
    cases = next(
        ast.literal_eval(n.value)
        for n in tree.body
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "CASES" for t in n.targets)
    )
    rows, evidence = [], {}
    for case in cases:
        case_inputs = ORIGINAL / "evidence/normal-gated-join" / ("isolated-" + case) / "inputs.json"
        evidence[str(case_inputs)] = sha(case_inputs)
        for call in range(3):
            saved = ORIGINAL / "evidence/normal-gated-join" / ("actual-" + case + "-" + str(call))
            manifest = json.loads((saved / "manifest.json").read_text())
            if not manifest["complete"]:
                raise ValueError("Incomplete saved actual state")
            evidence[str(saved / "manifest.json")] = sha(saved / "manifest.json")
            for name, expected in manifest["files"].items():
                if sha(saved / name) != expected:
                    raise ValueError("Saved numeric evidence changed")
                evidence[str(saved / name)] = expected
            rows.append(dict(case=case, call=call, inputs=str(case_inputs), saved=str(saved)))
    budgets = {}
    for name in (
        "validation/betse/junction_gate/protocol.json",
        "validation/betse/betse_normal_current_protocol.json",
        "validation/betse/betse_normal_ion_join_protocol.json",
        "validation/betse/betse_normal_voltage_protocol.json",
        "tests/unit/test_betse_normal_ion_join.py",
    ):
        budgets[name] = sha(source / name)
    directory.mkdir(exist_ok=False)
    (directory / "driver.py").write_bytes(Path(__file__).read_bytes())
    write(
        directory / "inputs.json",
        dict(
            kind="cells.b26_saved_actual_parent_local_audit@1",
            status="prepared_not_executed",
            original_result=dict(path=str(ORIGINAL / "result.json"), sha256=RESULT_SHA),
            original_inputs_sha256=sha(ORIGINAL / "inputs.json"),
            frozen_source=str(source),
            frozen_source_sha256=original["source_hashes"],
            saved_evidence_sha256=evidence,
            inherited_budget_source_sha256=budgets,
            driver_sha256=sha(directory / "driver.py"),
            rows=rows,
            planned_actual_parent_calls=36,
            planned_fresh_reference_forms=72,
            gate_checkpoints="Actual pre-update opening/voltage/block/dt; two Decimal precisions",
            material_budget="128*eps*(ions+membranes+4+32)*local gross + registered named floors",
            current_budget="32*eps*(ions+membranes+16)*local gross+1e-30",
            voltage_budget="1024*eps*(ions+membranes+gridpoints+16+64)*local gross+1e-30",
            gate_open_budget="Registered source_gate_atol+source_gate_rtol*abs(reference)",
            constructor_only_cache_revalidation=False,
            conditional_scope=(
                "One complete call from actual incoming float state; gate checkpoints "
                "additionally conditional on actual incoming per-ion state"
            ),
            physical_accuracy_or_trajectory_bound_claim=False,
            no_observed_error_tuning=True,
            resources=dict(
                threads=1,
                max_command_seconds=480,
                max_tree_rss_bytes=2**30,
                min_available_host_memory_bytes=8 * 2**30,
            ),
            numerical_runs=0,
            numerical_imports_during_preparation=0,
            native_reruns=0,
            production_model_reruns=0,
            execution_requires_new_requested_audit_round=True,
            cpu=None,
            automatic_launch=False,
            automatic_polling=False,
            automatic_followup=False,
        ),
    )
    print(
        json.dumps(
            dict(
                status="prepared_not_executed",
                inputs=str(directory / "inputs.json"),
                sha256=sha(directory / "inputs.json"),
                numerical_runs=0,
            )
        )
    )


def reference_worker(inputs_path, output, refinement, frozen_source):
    import builtins
    import importlib
    import importlib.abc
    from decimal import Decimal, localcontext

    blocked = {"cells", "betse", "numpy", "jax", "jaxlib"}
    original_import = builtins.__import__

    def guarded(name, *args, **kwargs):
        if name.split(".")[0] in blocked:
            raise ImportError("Saved local reference import denied: " + name)
        return original_import(name, *args, **kwargs)

    class Guard(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split(".")[0] in blocked:
                raise ImportError("Reference import denied: " + fullname)

    builtins.__import__ = guarded
    sys.meta_path.insert(0, Guard())
    sys.path[:0] = [str(frozen_source)]
    equation = importlib.import_module("validation.betse.betse_normal_gated_join_reference")
    packet = json.loads(inputs_path.read_text())
    answer = equation.evaluate(packet["call_inputs"], refinement=refinement)
    gates = []
    with localcontext() as ctx:
        ctx.prec = 90 if refinement == 1 else 140
        for gate in packet["gate_inputs"]:
            values = equation.gate_step(
                [equation.d(x) for x in gate["opening_before"]],
                [abs(equation.d(x)) for x in gate["opening_before"]],
                [equation.d(x) for x in gate["voltage_before_nonce_V"]],
                [abs(equation.d(x)) for x in gate["voltage_before_nonce_V"]],
                equation.d(gate["dt_s"]),
                [equation.d(x) for x in gate["block"]],
                packet["call_inputs"]["gate_definition"],
                gate["ion_id"],
                gate["update_index"],
            )[2]
            gates.append(equation.tree(values, lambda x: float(x) if isinstance(x, Decimal) else x))
    loaded = [name for name in sys.modules if name.split(".")[0] in blocked]
    if loaded:
        raise ValueError("Independent audit reference loaded forbidden packages")
    answer.update(
        actual_parent_identity=packet["actual_parent_identity"],
        conditional_gate_checkpoints=gates,
        constructor_only_cache_is_not_audited=True,
        production_imports_denied=True,
        loaded_production_modules=loaded,
        measured_cpu_affinity=sorted(os.sched_getaffinity(0)),
    )
    write(output, answer)


def read_archive(path):
    import struct

    import numpy as np

    def decode(node, arrays):
        if not isinstance(node, dict):
            return node
        if "mapping" in node:
            return {key: decode(value, arrays) for key, value in node["mapping"]}
        if "sequence" in node:
            return [decode(value, arrays) for value in node["sequence"]]
        if "float64_bits" in node:
            return struct.unpack("<d", bytes.fromhex(node["float64_bits"]))[0]
        if "array" in node:
            value = arrays[node["array"]]
            if value.dtype.str != node["dtype"] or list(value.shape) != node["shape"]:
                raise ValueError("Saved array axes/dtype changed")
            return value.copy()
        raise ValueError("Unknown saved evidence node")

    with np.load(path / "arrays.npz", allow_pickle=False) as arrays:
        return decode(json.loads((path / "data.json").read_text()), arrays)


def plain(value):
    if hasattr(value, "tolist"):
        return value.tolist()
    if isinstance(value, dict):
        return {key: plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [plain(item) for item in value]
    return value


def execute(directory, cpu):
    """Saved-data arithmetic only; fail honestly on inherited-budget violations."""
    import numpy as np

    inputs = json.loads((directory / "inputs.json").read_text())
    source = Path(inputs["frozen_source"])
    sys.path.insert(0, str(source))
    floors_tree = ast.parse((source / "tests/unit/test_betse_normal_ion_join.py").read_text())
    floor_value = next(
        n.value
        for n in floors_tree.body
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "FLOORS" for t in n.targets)
    )
    if isinstance(floor_value, ast.Dict):
        floors = ast.literal_eval(floor_value)
    elif (
        isinstance(floor_value, ast.Call)
        and isinstance(floor_value.func, ast.Name)
        and floor_value.func.id == "dict"
        and not floor_value.args
    ):
        floors = {item.arg: ast.literal_eval(item.value) for item in floor_value.keywords}
    else:
        raise ValueError(
            "Registered material floor declaration changed; no fallback/tolerance tuning"
        )
    gate_tolerance = json.loads(
        (source / "validation/betse/junction_gate/protocol.json").read_text()
    )["tolerances"]
    results = []
    for row in inputs["rows"]:
        trial = read_archive(Path(row["saved"]))["trial"]
        parent = trial["parent"]
        call = copy.deepcopy(json.loads(Path(row["inputs"]).read_text()))
        forcing = copy.deepcopy(call["drives"][row["call"]])
        call["initial"] = plain(parent["material"]["values"])
        call["drives"] = [forcing]
        gate_inputs = [
            plain(
                {
                    key: event[key]
                    for key in (
                        "ion_id",
                        "update_index",
                        "opening_before",
                        "voltage_before_nonce_V",
                        "dt_s",
                    )
                }
            )
            | dict(block=forcing["material"]["junction_block"])
            for event in trial["material"]["gate_updates"]
        ]
        folder = directory / (row["case"] + "-" + str(row["call"]))
        folder.mkdir()
        write(
            folder / "inputs.json",
            dict(
                call_inputs=call,
                gate_inputs=gate_inputs,
                actual_parent_identity=parent["identity"],
                outgoing_answers_supplied=False,
            ),
        )
        answers = []
        for precision in (1, 2):
            output = folder / ("reference-" + str(precision) + ".json")
            command = [
                sys.executable,
                "-B",
                str(directory / "driver.py"),
                "reference",
                str(folder / "inputs.json"),
                "--output",
                str(output),
                "--refinement",
                str(precision),
                "--source",
                str(source),
            ]
            with (folder / ("reference-" + str(precision) + ".log")).open("x") as stream:
                subprocess.run(
                    command, stdout=stream, stderr=subprocess.STDOUT, check=True, timeout=180
                )
            answer = json.loads(output.read_text())
            if answer["measured_cpu_affinity"] != [cpu] or not answer["production_imports_denied"]:
                raise ValueError("Conditional reference runtime guard failed")
            answers.append(answer)
        standard, tight = answers
        expected = tight["history"][0]
        less = standard["history"][0]
        ni = len(call["ion_definition"]["ions"]["ids"])
        nm = len(call["initial"]["voltage_V"])
        eps = np.finfo(np.float64).eps
        metrics = {}

        def compare(name, actual, target, budget, lo=None, record_into=metrics):
            error = abs(np.asarray(actual) - np.asarray(target))
            allowance = np.broadcast_to(budget, error.shape)
            where = np.unravel_index(np.argmax(error), error.shape)
            record = dict(
                absolute_error=float(np.max(error)),
                budget_at_worst_absolute=float(allowance[where]),
                index=[int(x) for x in where],
                min_budget=float(np.min(allowance)),
                max_budget=float(np.max(allowance)),
                normalized_max=float(np.max(error / allowance)),
                pass_local=bool(np.all(error <= allowance)),
            )
            if lo is not None:
                resolution = abs(np.asarray(lo) - np.asarray(target))
                record["reference_resolution_max_fraction"] = float(np.max(resolution / allowance))
                record["pass_local"] = (
                    record["pass_local"] and record["reference_resolution_max_fraction"] <= 0.1
                )
            record_into[name] = record

        for group, actual, target, gross, lo in (
            (
                "material",
                trial["material"]["candidate"]["material"]["values"],
                expected["material_state"],
                expected["material_gross"],
                less["material_state"],
            ),
            (
                "current",
                trial["current"]["values"],
                expected["current"]["values"],
                expected["current"]["gross"],
                less["current"]["values"],
            ),
            (
                "voltage",
                trial["voltage"]["values"],
                expected["voltage"]["values"],
                expected["voltage"]["gross"],
                less["voltage"]["values"],
            ),
        ):
            for name, value in actual.items():
                factor = (
                    128 * eps * (ni + nm + 4 + 32)
                    if group == "material"
                    else 32 * eps * (ni + nm + 16)
                    if group == "current"
                    else 1024
                    * eps
                    * (ni + nm + np.prod(call["voltage_definition"]["grid"]["shape"]) + 16 + 64)
                )
                budget = factor * np.asarray(gross[name]) + (
                    floors[name] if group == "material" else 1e-30
                )
                compare(group + "/" + name, value, target[name], budget, lo[name])
        for index, (actual, expected_gate, less_gate) in enumerate(
            zip(
                trial["material"]["gate_updates"],
                tight["conditional_gate_checkpoints"],
                standard["conditional_gate_checkpoints"],
                strict=True,
            )
        ):
            for name in ("opening_unblocked", "opening_stored"):
                target = np.asarray(expected_gate["values"][name])
                budget = gate_tolerance["source_gate_atol"] + gate_tolerance[
                    "source_gate_rtol"
                ] * abs(target)
                compare(
                    "gate/" + str(index) + "/" + name,
                    actual[name],
                    target,
                    budget,
                    less_gate["values"][name],
                )
        record = dict(
            case=row["case"],
            call=row["call"],
            actual_parent_identity=parent["identity"],
            fields=metrics,
            pass_local=all(value["pass_local"] for value in metrics.values()),
            physical_accuracy_claim=False,
        )
        write(folder / "comparison.json", record)
        results.append(record)
    passed = all(row["pass_local"] for row in results)
    write(
        directory / ("result.json" if passed else "comparison-failure.json"),
        dict(
            status="passed_conditional_local" if passed else "failed_conditional_local",
            calls=len(results),
            fresh_reference_forms=72,
            results=results,
            native_reruns=0,
            production_model_reruns=0,
            physical_accuracy_claim=False,
            automatic_followup=False,
        ),
    )
    if not passed:
        raise AssertionError(
            "Inherited conditional local budgets failed; evidence preserved without tuning"
        )


def run(directory, cpu):
    inputs = json.loads((directory / "inputs.json").read_text())
    if sha(directory / "driver.py") != inputs["driver_sha256"]:
        raise ValueError("Prepared audit driver changed")
    for name, expected in inputs["saved_evidence_sha256"].items():
        if sha(name) != expected:
            raise ValueError("Saved evidence changed")
    source = Path(inputs["frozen_source"])
    for name, expected in inputs["frozen_source_sha256"].items():
        if sha(source / name) != expected:
            raise ValueError("Frozen source changed")
    if (directory / "execution.json").exists():
        raise FileExistsError("Audit already launched")
    os.sched_setaffinity(0, {cpu})
    sys.path[:0] = [str(source / "src"), str(source)]
    from validation.assembly.component_process import run_bounded

    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("JAX_", "XLA_", "CELLS_", "PYTEST_"))
    }
    env.update(
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONPATH=str(source),
        CELLS_B26_SAVED_AUDIT_REQUESTED="1",
        OMP_NUM_THREADS="1",
        OPENBLAS_NUM_THREADS="1",
        MKL_NUM_THREADS="1",
        NUMEXPR_NUM_THREADS="1",
        BLIS_NUM_THREADS="1",
        VECLIB_MAXIMUM_THREADS="1",
        CUDA_VISIBLE_DEVICES="",
    )
    process = directory / "process"
    process.mkdir()
    write(
        directory / "execution.json",
        dict(
            cpu=cpu,
            authorization="Explicit later requested audit round",
            native_reruns=0,
            production_reruns=0,
        ),
    )
    try:
        resources = run_bounded(
            [
                sys.executable,
                "-B",
                str(directory / "driver.py"),
                "execute",
                str(directory),
                "--cpu",
                str(cpu),
            ],
            directory=process,
            cwd=source,
            env=env,
            timeout=480,
            max_rss_bytes=2**30,
            min_available_bytes=8 * 2**30,
            process_tree_memory_metric="rss",
        )
        write(directory / "resources.json", resources)
    except BaseException:
        write(
            directory / "failure.json",
            dict(traceback=traceback.format_exc(), automatic_retry=False, tolerances_changed=False),
        )
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "run", "execute", "reference"))
    parser.add_argument("directory", type=Path)
    parser.add_argument("--cpu", type=int)
    parser.add_argument("--requested-audit", action="store_true")
    parser.add_argument("--cpu-coordinated", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--refinement", type=int, choices=(1, 2))
    parser.add_argument("--source", type=Path)
    args = parser.parse_args()
    if args.action == "prepare":
        prepare(args.directory.resolve())
    elif args.action == "run":
        if not args.requested_audit or not args.cpu_coordinated or args.cpu is None:
            parser.error(
                "Do not run until a new audit round and CPU are explicitly requested/coordinated"
            )
        run(args.directory.resolve(), args.cpu)
    elif args.action == "execute":
        if os.environ.get("CELLS_B26_SAVED_AUDIT_REQUESTED") != "1" or args.cpu is None:
            parser.error("Saved numerical audit requires the later requested/coordinated runner")
        execute(args.directory.resolve(), args.cpu)
    else:
        if os.environ.get("CELLS_B26_SAVED_AUDIT_REQUESTED") != "1":
            parser.error("Reference worker is reserved for a later explicitly requested audit")
        if not args.output or not args.refinement or not args.source:
            parser.error("Reference requires explicit output/precision/frozen source")
        reference_worker(args.directory, args.output, args.refinement, args.source)


if __name__ == "__main__":
    main()
