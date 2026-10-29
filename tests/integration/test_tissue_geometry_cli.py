"""Portable public JSON workflow over already-qualified geometry evidence."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
from copy import deepcopy
from functools import lru_cache
from pathlib import Path

import numpy as np
import pytest

from cells import tissue_geometry as cli
from cells.core.specs import ConfigError, digest, parse_spec
from cells.models import surface_tissue as model

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
CONTRACT = json.loads((WORK / "tissue_geometry_cli_contract.json").read_text())
EXAMPLE = ROOT / CONTRACT["repository_example"]["path"]

BOOTSTRAP = """
import os, runpy, sys
def refuse_external_capture(event, arguments):
    if event == 'open' and isinstance(arguments[0], (str, bytes)):
        path = os.fsdecode(arguments[0])
        if path.startswith(('/mnt/workspaces/Cells/betse-geometry-',
                            '/mnt/workspaces/Cells/geometry-tissue-preparation-')):
            raise RuntimeError('Portable CLI attempted an external geometry read: ' + path)
sys.addaudithook(refuse_external_capture)
sys.argv = ['cells.tissue_geometry', *sys.argv[1:]]
if entry := os.environ.get('CELLS_GEOMETRY_CLI_PATCHED_MAIN'):
    runpy.run_path(entry, run_name='__main__')
else:
    runpy.run_module('cells.tissue_geometry', run_name='__main__')
"""


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, data):
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")
    return path


def evidence(name, report):
    if folder := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        path = Path(folder)
        path.mkdir(parents=True, exist_ok=True)
        (path / ("tissue-geometry-cli-" + name + ".json")).write_text(
            json.dumps(dict(report, status="passed"), indent=2, allow_nan=False) + "\n"
        )


@lru_cache
def qualified():
    path = Path(os.environ.get("CELLS_GEOMETRY_CLI_REFERENCE", CONTRACT["frozen_example"]["path"]))
    for name, expected in CONTRACT["frozen_example"]["files_sha256"].items():
        assert sha(path / name) == expected
    return {
        name: cli.read_json(path / name)
        for name in ("request.json", "definition.json", "provenance.json")
    }


def child(arguments, cwd, *, entry=None):
    env = os.environ.copy()
    env.pop("CELLS_GEOMETRY_PREPARATION_NATIVE", None)
    env.pop("CELLS_GEOMETRY_CLI_REFERENCE", None)
    env.pop("CELLS_GEOMETRY_CLI_DISPATCH_BASE", None)
    env["PYTHONPATH"] = str(ROOT / "src")
    if entry is not None:
        env["CELLS_GEOMETRY_CLI_PATCHED_MAIN"] = str(entry)
    result = subprocess.run(
        [sys.executable, "-B", "-c", BOOTSTRAP, *map(str, arguments)],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout), dict(
        arguments=list(map(str, arguments)),
        stdout=result.stdout,
        stderr=result.stderr,
        exit_code=result.returncode,
    )


def assert_qualified_files(path):
    expected = qualified()
    definition = cli.read_json(path / "definition.json")
    provenance = cli.read_json(path / "provenance.json")
    assert definition == expected["definition.json"]
    assert provenance == expected["provenance.json"]
    states = [
        model.initial_values(parse_spec(raw))[0]
        for raw in (definition, expected["definition.json"])
    ]
    assert type(states[0]) is type(states[1])
    for a, b in zip(*states, strict=True):
        assert np.asarray(a).dtype == np.asarray(b).dtype
        np.testing.assert_array_equal(a, b)
    return dict(
        definition_sha256=digest(definition),
        identity=provenance["identity"],
        initial_state_sha256=provenance["initial_state_sha256"],
        state_fields=list(states[0]._fields),
    )


def test_fresh_process_prepare_relocate_validate_and_portable_replay(tmp_path):
    request = tmp_path / "request.json"
    shutil.copyfile(EXAMPLE, request)
    original = tmp_path / "original"
    before, first = child(["prepare", request, "--output", original], tmp_path)
    initial = assert_qualified_files(original)
    moved = tmp_path / "relocated" / "bundle"
    shutil.copytree(original, moved)
    shutil.rmtree(original)
    request.unlink()
    valid, second = child(["validate", moved], tmp_path / "relocated")
    rebuilt = tmp_path / "replayed"
    replayed, third = child(
        ["replay", moved / "provenance.json", "--output", rebuilt], tmp_path / "relocated"
    )
    final, fourth = child(["validate", rebuilt], tmp_path)
    assert_qualified_files(moved)
    assert assert_qualified_files(rebuilt) == initial
    assert [r["status"] for r in (before, valid, replayed, final)] == [
        "prepared",
        "valid",
        "replayed",
        "valid",
    ]
    assert all(
        r["definition_sha256"] == initial["definition_sha256"]
        for r in (before, valid, replayed, final)
    )
    evidence(
        "portable-workflow",
        dict(
            external_geometry_reads_blocked=True,
            fresh_processes=[first, second, third, fourth],
            exact_component_definition_and_initial_state=initial,
            original_input_and_output_removed=True,
        ),
    )


def test_unapplied_shared_dispatch_patch_in_isolated_copy(tmp_path):
    metadata = json.loads((WORK / "tissue_geometry_cli_dispatch.json").read_text())
    patch = WORK / "tissue_geometry_cli_dispatch.patch"
    assert sha(patch) == metadata["patch_sha256"]
    original = Path(
        os.environ.get("CELLS_GEOMETRY_CLI_DISPATCH_BASE", str(ROOT / metadata["path"]))
    )
    assert sha(original) == metadata["base_sha256"]
    target = tmp_path / metadata["path"]
    target.parent.mkdir(parents=True)
    shutil.copyfile(original, target)
    command = subprocess.run(
        ["git", "apply", str(patch)], cwd=tmp_path, capture_output=True, text=True, check=False
    )
    assert command.returncode == 0, command.stderr
    assert sha(target) == metadata["patched_sha256"]
    help_command = subprocess.run(
        [sys.executable, "-B", str(target), "--help"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert help_command.returncode == 0 and "tissue-geometry" in help_command.stdout
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    for name in ("definition.json", "provenance.json"):
        write(bundle / name, qualified()[name])
    result, capture = child(["tissue-geometry", "validate", bundle], tmp_path, entry=target)
    assert result["status"] == "valid"
    assert result["definition_sha256"] == digest(qualified()["definition.json"])
    assert sha(original) == metadata["base_sha256"]
    evidence(
        "dispatch-patch", dict(shared_source_unchanged=True, patch=metadata, fresh_process=capture)
    )


@pytest.mark.parametrize(
    "text",
    [
        '{"kind": 1, "kind": 2}',
        '{"nested": {"value": 1, "value": 1}}',
        '{"value": NaN}',
        '{"value": Infinity}',
        '{"value": -Infinity}',
        '{"value": 1e999}',
        '{"value": -1e999}',
        '{"kind":',
    ],
)
def test_strict_finite_json_and_duplicate_fields(text, tmp_path):
    path = tmp_path / "input.json"
    path.write_text(text)
    with pytest.raises(ConfigError):
        cli.read_json(path)
    evidence(
        "json-" + hashlib.sha256(text.encode()).hexdigest()[:12], dict(input=text, refused=True)
    )


@pytest.mark.parametrize(
    "fault",
    ["kind", "missing-physics", "unknown-field", "nested-shape", "cut-mode", "missing-inventory"],
)
def test_malformed_requests_fail_cleanly_without_output(fault, tmp_path, capsys):
    raw = deepcopy(qualified()["request.json"])
    if fault == "kind":
        raw["kind"] = "cells.cut_geometry@1"
    if fault == "missing-physics":
        raw.pop("physics")
    if fault == "unknown-field":
        raw["state"] = {}
    if fault == "nested-shape":
        raw["geometry_source"]["mesh"]["cell_ids"] = None
    if fault == "cut-mode":
        raw["geometry_source"]["generation"]["mode"] = "cut_epoch@1"
    if fault == "missing-inventory":
        raw["physics"]["cells"][0].pop("initial_amount_fmol")
    source = write(tmp_path / "request.json", raw)
    output = tmp_path / "output"
    assert cli.main(["prepare", str(source), "--output", str(output)]) == 2
    captured = capsys.readouterr()
    assert (
        captured.out == ""
        and "cells.tissue_geometry:" in captured.err
        and "Traceback" not in captured.err
    )
    assert not output.exists()
    evidence("request-refused-" + fault, dict(fault=fault, stderr=captured.err, output_absent=True))


@pytest.mark.parametrize(
    "fault", ["definition-hash", "geometry-identity", "physical-volume", "generation-rng"]
)
def test_resealed_tampered_recipes_refuse(fault, tmp_path, capsys):
    raw = deepcopy(qualified()["provenance.json"])
    if fault == "definition-hash":
        raw["prepared_definition_sha256"] = "0" * 64
    if fault == "geometry-identity":
        raw["geometry_manifest"]["identity"] = "0" * 64
    if fault == "physical-volume":
        raw["request"]["physics"]["extracellular"][0]["volume_m3"] *= 1.01
    if fault == "generation-rng":
        raw["request"]["geometry_source"]["generation"]["rng_after"][1][0] += 1
    raw.pop("identity")
    raw["identity"] = digest(raw)
    path = write(tmp_path / "provenance.json", raw)
    output = tmp_path / "output"
    assert cli.main(["replay", str(path), "--output", str(output)]) == 2
    captured = capsys.readouterr()
    assert captured.out == "" and "Traceback" not in captured.err
    assert not output.exists()
    evidence("replay-refused-" + fault, dict(fault=fault, stderr=captured.err, output_absent=True))


@pytest.mark.parametrize("file", ["definition.json", "provenance.json"])
@pytest.mark.parametrize("fault", ["duplicate", "nonfinite", "changed"])
def test_validate_strictly_checks_both_files(file, fault, tmp_path, capsys):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    for name in ("definition.json", "provenance.json"):
        write(bundle / name, qualified()[name])
    path = bundle / file
    raw = path.read_text()
    if fault == "duplicate":
        path.write_text(raw.replace("{", '{"duplicate": 0, "duplicate": 0,', 1))
    if fault == "nonfinite":
        path.write_text(raw.replace("{", '{"nonfinite": 1e999,', 1))
    if fault == "changed":
        value = json.loads(raw)
        if file == "definition.json":
            value["model"]["cells"][0]["volume_pL"] *= 1.01
        else:
            value["identity"] = "0" * 64
        write(path, value)
    before = {p.name: sha(p) for p in bundle.iterdir()}
    assert cli.main(["validate", str(bundle)]) == 2
    captured = capsys.readouterr()
    assert captured.out == "" and "Traceback" not in captured.err
    assert {p.name: sha(p) for p in bundle.iterdir()} == before
    evidence(
        "validate-" + file + "-" + fault,
        dict(file=file, fault=fault, refused_without_mutation=True),
    )


@pytest.mark.parametrize("kind", ["directory", "file", "dangling-symlink"])
def test_outputs_never_overwrite_and_refuse_before_loading_input(
    kind, tmp_path, monkeypatch, capsys
):
    output = tmp_path / "existing"
    if kind == "directory":
        output.mkdir()
        (output / "sentinel").write_text("keep")
    if kind == "file":
        output.write_text("keep")
    if kind == "dangling-symlink":
        output.symlink_to(tmp_path / "missing-target", target_is_directory=True)

    def unexpected(_):
        raise AssertionError("Nonoverwrite check must precede reading input")

    monkeypatch.setattr(cli, "read_json", unexpected)
    for command in ("prepare", "replay"):
        assert cli.main([command, str(tmp_path / "missing.json"), "--output", str(output)]) == 2
        assert "Output already exists" in capsys.readouterr().err
    if kind == "directory":
        assert (output / "sentinel").read_text() == "keep"
    if kind == "file":
        assert output.read_text() == "keep"
    if kind == "dangling-symlink":
        assert output.is_symlink() and not (tmp_path / "missing-target").exists()
    evidence(
        "nonoverwrite-" + kind,
        dict(kind=kind, refused_before_input=True, existing_output_unchanged=True),
    )


def test_public_helpers_preserve_full_request_and_component_recipe():
    request = deepcopy(qualified()["request.json"])
    before = deepcopy(request)
    result = cli.prepare_request(request)
    assert request == before
    assert result.definition == qualified()["definition.json"]
    assert result.provenance == qualified()["provenance.json"]
    assert cli.replay(result.provenance) == result
    evidence(
        "helpers",
        dict(request_unchanged=True, component_definition_and_complete_provenance_exact=True),
    )


@pytest.mark.parametrize("fault", ["boolean-schema", "float-capacity"])
def test_saved_definition_rejects_equal_python_values_with_different_json_types(
    fault, tmp_path, capsys
):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    definition = deepcopy(qualified()["definition.json"])
    if fault == "boolean-schema":
        definition["schema_version"] = True
    else:
        definition["execution"]["capacity"] = float(definition["execution"]["capacity"])
    assert definition == qualified()["definition.json"]
    assert digest(definition) != digest(qualified()["definition.json"])
    write(bundle / "definition.json", definition)
    write(bundle / "provenance.json", qualified()["provenance.json"])
    before = sha(bundle / "definition.json")
    assert cli.main(["validate", str(bundle)]) == 2
    assert "definition changed" in capsys.readouterr().err
    assert sha(bundle / "definition.json") == before
    evidence("typed-definition-" + fault, dict(fault=fault, exact_json_identity_enforced=True))


def test_frozen_geometry_receipt_sources_and_repository_example():
    receipt = CONTRACT["geometry_handoff"]
    assert sha(Path(receipt["path"])) == receipt["sha256"]
    prior = json.loads(Path(receipt["path"]).read_text())
    assert prior["status"] == "passed" and prior["tests"]["tests"] == 56
    for relative, expected in CONTRACT["readonly_source_sha256"].items():
        assert sha(ROOT / relative) == expected, relative
    assert sha(EXAMPLE) == CONTRACT["repository_example"]["sha256"]
    assert cli.read_json(EXAMPLE) == qualified()["request.json"]
    evidence(
        "component-evidence",
        dict(
            reused_geometry_handoff=receipt,
            readonly_source_sha256=CONTRACT["readonly_source_sha256"],
            repository_example=CONTRACT["repository_example"],
            component_suite_rerun=False,
        ),
    )
