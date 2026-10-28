"""Actual legacy cagPotassium function, unit context and container-defect captures."""

import argparse
import ast
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from validation.channels import calcium_activated_potassium_reference as reference

ROOT = Path(__file__).resolve().parents[3]
PROTOCOL = json.loads(
    (ROOT / "validation/channels/calcium_activated_potassium_protocol.json").read_text()
)


def write(path, value):
    path.write_text(
        json.dumps(value, indent=2, allow_nan=False, default=lambda v: v.tolist()) + "\n"
    )


def setup(calcium, voltage, temperature=298.15, owners=None, targets=None):
    calcium, voltage = np.asarray(calcium, float), np.asarray(voltage, float)
    owners = np.arange(len(voltage), dtype=int) if owners is None else np.asarray(owners, dtype=int)
    targets = (
        np.arange(len(voltage), dtype=int) if targets is None else np.asarray(targets, dtype=int)
    )
    concentrations = np.stack((calcium, np.full_like(calcium, 130.0), np.full_like(calcium, 5.0)))
    sim = SimpleNamespace(
        cc_cells=concentrations,
        iCa=0,
        iK=1,
        vm=voltage,
        T=temperature,
        Dm_cag=np.zeros((3, len(voltage))),
    )
    sim.Dm_cag[[0, 2]] = 7e-19
    return (
        SimpleNamespace(targets_cagK=targets, maxDmKcag=2e-18),
        sim,
        SimpleNamespace(mem_to_cells=owners),
        SimpleNamespace(F=float(reference.F), R=float(reference.R)),
    )


def execute(function, objects):
    dyna, sim, cells, p = objects
    before = sim.cc_cells.copy()
    before_other = sim.Dm_cag[[0, 2]].copy()
    result = function(dyna, sim, cells, p)
    assert result is None
    np.testing.assert_array_equal(sim.cc_cells, before)
    np.testing.assert_array_equal(sim.Dm_cag[[0, 2]], before_other)
    return sim.Dm_cag[sim.iK] / dyna.maxDmKcag


def compare(actual, expected):
    t = PROTOCOL["tolerances"]
    np.testing.assert_allclose(
        actual, expected, rtol=t["native_relative"], atol=t["native_opening_atol"]
    )


def inventory(checkout, output):
    scanned, symbols, classes = {}, [], {}
    for path in sorted(checkout.rglob("*.py")):
        data = path.read_bytes()
        relative = str(path.relative_to(checkout))
        scanned[relative] = hashlib.sha256(data).hexdigest()
        if b"cagPotassium" in data:
            tree = ast.parse(data)
            for line, text in enumerate(data.decode().splitlines(), 1):
                if "cagPotassium" in text:
                    symbols.append(dict(path=relative, line=line, text=text.strip()))
            assert not any(
                isinstance(n, ast.Call)
                and (
                    (isinstance(n.func, ast.Name) and n.func.id == "cagPotassium")
                    or (isinstance(n.func, ast.Attribute) and n.func.attr == "cagPotassium")
                )
                for n in ast.walk(tree)
            )
        if path.parent == checkout / "betse/science/channels":
            classes[relative] = [
                n.name for n in ast.parse(data).body if isinstance(n, ast.ClassDef)
            ]
    assert len(symbols) == 1 and symbols[0]["text"].startswith("def cagPotassium(")
    record = dict(
        status="inspected",
        scanned_python_sha256=scanned,
        channel_classes=classes,
        symbol_occurrences=symbols,
        cagPotassium_call_sites_found=0,
        scope=(
            "Literal function/call occurrence inventory in pinned Python files; "
            "not a modern runtime support claim"
        ),
    )
    write(output / "source-inventory.json", record)
    return len(scanned)


def capture(output):
    output.mkdir(parents=True, exist_ok=False)
    installed, checkout = (Path(PROTOCOL["native_probe"][k]) for k in ("installed", "checkout"))
    revision = subprocess.check_output(
        ["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True
    ).strip()
    manifest = dict(status="capturing", revision=revision, files={})
    write(output / "source-manifest.json", manifest)
    assert revision == PROTOCOL["source_revision"]
    for relative, expected in PROTOCOL["source_files"].items():
        data = (installed / relative).read_bytes()
        target = output / "upstream" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(installed / relative, target)
        entry = dict(
            sha256=hashlib.sha256(data).hexdigest(),
            checkout_match=data == (checkout / relative).read_bytes(),
        )
        manifest["files"][relative] = entry
        write(output / "source-manifest.json", manifest)
        assert entry["sha256"] == expected and entry["checkout_match"]
    metadata = ast.parse((installed / "betse/metadata.py").read_text())
    version = next(
        ast.literal_eval(n.value)
        for n in metadata.body
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "VERSION" for t in n.targets)
    )
    assert version == PROTOCOL["source_version"]
    source = ast.parse((installed / "betse/science/tissue/channels_o.py").read_text())
    selected = [
        n for n in source.body if isinstance(n, ast.FunctionDef) and n.name == "cagPotassium"
    ]
    assert len(selected) == 1
    namespace = dict(np=np, __name__="pinned_legacy_cagpotassium_probe")
    exec(
        compile(
            ast.Module(body=selected, type_ignores=[]),
            str(installed / "betse/science/tissue/channels_o.py"),
            "exec",
        ),
        namespace,
    )
    function = namespace["cagPotassium"]
    scanned = inventory(checkout, output)
    ordinary = []
    for temperature in (200.0, 298.15, 400.0):
        calcium = np.array([0.0, 1e-9, 0.89e-6, 10.22e-6, 1e-4, 0.01])
        voltage = np.array([-0.120, -0.080, -0.040, 0.0, 0.020, 0.060])
        objects = setup(calcium, voltage, temperature)
        with np.errstate(all="raise"):
            probability = execute(function, objects)
        record = dict(
            status="captured",
            temperature_K=temperature,
            calcium_free_mM=calcium,
            voltage_V=voltage,
            probability=probability,
            coefficient=objects[1].Dm_cag[1],
        )
        path = output / f"native-ordinary-{temperature:.9g}.json"
        write(path, record)
        expected = [
            reference.evaluate(float(v), float(c), temperature)["opening"]
            for v, c in zip(voltage, calcium, strict=True)
        ]
        compare(probability, expected)
        record["status"] = "passed"
        write(path, record)
        ordinary.append(record)
    # Two membranes share each selected owner; changing free cytosolic Ca changes
    # only those owner's readouts. The native routine does not consume this Ca.
    objects = setup([0.0, 2e-5, 8.9e-7], [-0.100, -0.040, 0.020, 0.060], owners=[0, 1, 0, 2])
    before = execute(function, objects)
    objects[1].cc_cells[0, 0] = 1e-5
    after = execute(function, objects)
    changed = np.flatnonzero(after != before)
    np.testing.assert_array_equal(changed, [0, 2])
    write(
        output / "native-owner-read.json",
        dict(
            status="passed",
            membrane_to_cytosol=objects[2].mem_to_cells,
            before=before,
            after=after,
            changed_membranes=changed,
            calcium_consumed=False,
        ),
    )
    failures = []
    for label, targets in (
        ("full", [0, 1, 2, 3]),
        ("reordered-full", [3, 0, 1, 2]),
        ("duplicates-full", [0, 0, 1, 1]),
        ("singleton", [1]),
        ("subset", [2, 0]),
        ("empty", []),
    ):
        objects = setup(
            [0.0, 2e-5, 8.9e-7],
            [-0.100, -0.040, 0.020, 0.060],
            owners=[0, 1, 0, 2],
            targets=targets,
        )
        dyna, sim, cells, _ = objects
        record = dict(
            status="prepared",
            kind="native-container-behavior",
            targets=targets,
            full_voltage_V=sim.vm,
            membrane_to_cytosol=cells.mem_to_cells,
            selected_calcium_mM=sim.cc_cells[0][cells.mem_to_cells][dyna.targets_cagK],
        )
        path = output / ("native-container-" + label + ".json")
        write(path, record)
        try:
            with np.errstate(all="raise"):
                result = execute(function, objects)
        except ValueError as exc:
            record.update(
                status="captured-native-container-failure",
                exception=dict(type=type(exc).__name__, message=str(exc)),
            )
            write(path, record)
            assert label in ("subset", "empty")
            failures.append(label)
            continue
        selected_c = record["selected_calcium_mM"]
        paired_c = np.broadcast_to(selected_c, sim.vm.shape)
        expected = [
            reference.evaluate(float(v), float(c), 298.15)["opening"]
            for v, c in zip(sim.vm, paired_c, strict=True)
        ]
        compare(result, expected)
        record.update(
            status="captured-native-assignment",
            probability=result,
            assigned_membranes=np.flatnonzero(sim.Dm_cag[sim.iK] != 0),
            source_pairs_selected_Ca_with_full_V=True,
            whole_K_row_assignment=True,
            canonical_target_scatter_parity_claim=False,
        )
        write(path, record)
        if label == "singleton":
            assert len(record["assigned_membranes"]) == 4
    assert failures == ["subset", "empty"]
    empty = setup([0.0], [], owners=[], targets=[])
    assert execute(function, empty).shape == (0,)
    write(output / "native-empty-container.json", dict(status="passed", membranes=0))
    huge = setup([1e308], [0.0])
    error = None
    try:
        with np.errstate(all="raise"):
            execute(function, huge)
    except FloatingPointError as exc:
        error = dict(type=type(exc).__name__, message=str(exc))
    assert error is not None
    with np.errstate(all="ignore"):
        raw = execute(function, setup([1e308], [0.0]))
    np.savez_compressed(
        output / "native-numeric-overflow.npz", calcium_mM=[1e308], raw_probability=raw
    )
    write(
        output / "native-numeric-overflow.json",
        dict(
            status="captured-native-overflow",
            exception=error,
            raw_finite=bool(np.isfinite(raw).all()),
            arrays="native-numeric-overflow.npz",
            stable_algebraic_limit_claim_separate=True,
        ),
    )
    assert not np.isfinite(raw).all()
    manifest.update(
        status="passed",
        version=version,
        ordinary_cases=3,
        ordinary_points=18,
        owner_read_cases=1,
        container_cases=6,
        expected_native_container_failures=failures,
        native_empty_container=True,
        expected_native_numeric_overflow=1,
        inspected_python_files=scanned,
        cagPotassium_call_sites_found=0,
        channel_state_count=0,
        native_tissue_simulation=False,
        physical_scope=PROTOCOL["source_status"],
    )
    write(output / "source-manifest.json", manifest)
    print(json.dumps(manifest | dict(files="captured separately")))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        capture(args.output)
    except Exception as exc:
        if args.output.is_dir():
            write(args.output / "failure.json", dict(type=type(exc).__name__, message=str(exc)))
        raise
