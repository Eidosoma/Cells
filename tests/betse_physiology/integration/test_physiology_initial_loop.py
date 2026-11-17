"""Full initial INIT/SIM loops with private-tape replay, restart and atomic IO."""

import json
import os
import shutil
import subprocess
import sys
from copy import deepcopy
from dataclasses import asdict, replace
from pathlib import Path

import numpy as np
import pytest

from cells.core.specs import ConfigError, digest
from tests.betse_physiology.unit.test_physiology_initial_preparation import (
    request as original_request,
)
from validation.betse.physiology import physiology_initial_loop_io as public

initial, loop, paired = public.initial, public.loop, public.paired
FAMILIES = ("passive", "ionic", "calcium", "fuel")


def request(family="passive", phase="SIM"):
    raw = original_request(family, reverse=True, profile="INIT" if phase == "INIT" else "normal")
    execution = raw["preparation"]["definition"]["execution"]
    if family == "passive":
        execution["dt"] /= 256
        execution["max_steps"] *= 256
    raw["component"]["controls"]["dt_s"] = 2 * execution["dt"]
    return raw


def evidence(name, payload, arrays=None):
    if directory := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        root = Path(directory) / "initial-loop"
        root.mkdir(parents=True, exist_ok=True)
        with (root / (name + ".json")).open("x") as handle:
            json.dump(initial._json(payload), handle, indent=2, sort_keys=True, allow_nan=False)
            handle.write("\n")
        if arrays is not None:
            np.savez_compressed(root / (name + ".npz"), **arrays)


def tree_arrays(value, label, output):
    if hasattr(value, "_asdict"):
        for name, child in value._asdict().items():
            tree_arrays(child, label + "_" + name, output)
    elif isinstance(value, (tuple, list)):
        for index, child in enumerate(value):
            tree_arrays(child, f"{label}_{index}", output)
    elif value is not None:
        output[label] = np.asarray(value)


def component_fields(component):
    return dict(
        protein=component.protein._asdict(),
        diffusion=component.diffusion._asdict(),
        controls=asdict(component.controls),
        time_s=component.time_s,
        loop_calls=component.loop_calls,
        stream_next_tick=component.stream.next_tick,
    )


def test_handoff_and_load_do_not_redraw_or_replay_initialization(tmp_path, monkeypatch):
    value = public.prepare(initial.initialize(request()))
    path = public.write_handoff(tmp_path / "managed", value)

    def forbidden(*args, **kwargs):
        raise AssertionError("Handoff/restore must not consume or replay initial random tapes")

    for module, name in (
        (initial, "initialize"),
        (initial, "replay"),
        (initial.profiles, "prepare"),
        (initial.step, "initialise"),
        (initial.streams, "draw"),
        (initial.perturb, "sample_native"),
    ):
        monkeypatch.setattr(module, name, forbidden)
    assert public.record(public.prepare(value.initialization)) == public.record(value)
    assert public.record(public.load_handoff(path)) == public.record(value)
    evidence("draw-free", dict(record=public.record(value), draws=0, initialization_replays=0))


@pytest.mark.parametrize("fault", ("origin", "managed", "handoff", "extra", "source", "cursor"))
def test_complete_origin_and_managed_child_associations_refuse_tampering(
    fault, tmp_path, monkeypatch
):
    value = public.prepare(initial.initialize(request()))
    root = public.write_handoff(tmp_path / "managed", value)
    if fault == "cursor":
        bad = replace(value, cursor=replace(value.cursor, loop_index=1))
        with pytest.raises((ConfigError, ValueError)):
            public.validate(bad)
        return
    if fault in ("origin", "managed"):
        target = root / ("origin/manifest.json" if fault == "origin" else "loop/manifest.json")
        target.write_bytes(target.read_bytes() + b"changed")
    elif fault == "handoff":
        target = root / "handoff.json"
        row = json.loads(target.read_text())
        row["initialization_identity"] = "0" * 64
        row["identity"] = digest({k: v for k, v in row.items() if k != "identity"})
        target.write_text(json.dumps(row))
        manifest = json.loads((root / "manifest.json").read_text())
        manifest["handoff_identity"] = row["identity"]
        manifest["files"]["handoff.json"] = paired._sha(target)
        manifest["identity"] = digest({k: v for k, v in manifest.items() if k != "identity"})
        (root / "manifest.json").write_text(json.dumps(manifest))
    elif fault == "extra":
        (root / "extra.json").write_text("{}")
    else:
        monkeypatch.setattr(public, "source_hashes", lambda: {"changed": "source"})
    with pytest.raises((ConfigError, ValueError)):
        public.load_handoff(root)


def test_failed_publication_preserves_origin_and_cannot_be_loaded(tmp_path, monkeypatch):
    value = public.prepare(initial.initialize(request()))
    before = deepcopy(value.initialization.provenance)
    original = paired._write_json

    def fail(path, payload):
        if path.name == "handoff.json":
            raise OSError("injected handoff publication failure")
        original(path, payload)

    monkeypatch.setattr(paired, "_write_json", fail)
    root = tmp_path / "failed"
    with pytest.raises(OSError):
        public.write_handoff(root, value)
    assert (root / "failure.json").is_file() and not (root / "manifest.json").exists()
    assert value.initialization.provenance == before
    with pytest.raises(ConfigError):
        public.load_handoff(root)
    evidence("publication-refusal", dict(directory=str(root), original_unchanged=True))


def test_valid_managed_child_from_another_counter_cannot_be_substituted(tmp_path):
    origin = initial.initialize(request())
    root = public.write_handoff(tmp_path / "managed", public.prepare(origin))
    different = request()
    different["component"]["next_tick"] += 7
    other = public.prepare(initial.initialize(different))
    # Preserve the real child; substitute a valid sibling and reseal the outer
    # byte hash. Complete cursor/source association must still reject it.
    shutil.move(root / "loop", tmp_path / "original-loop")
    item = other.initialization
    paired.write_physiology_checkpoint(
        root / "loop",
        item.spec,
        item.checkpoint,
        item.component.stream,
        item.binding.component,
        component_state=item.component,
        tissue_binding=item.binding,
        loop_cursor=other.cursor,
    )
    manifest = json.loads((root / "manifest.json").read_text())
    manifest["files"]["loop/manifest.json"] = paired._sha(root / "loop/manifest.json")
    manifest["identity"] = digest({k: v for k, v in manifest.items() if k != "identity"})
    (root / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises((ConfigError, ValueError)):
        public.load_handoff(root)
    evidence(
        "cross-child-refusal",
        dict(directory=str(root), original_loop=str(tmp_path / "original-loop")),
    )


@pytest.mark.parametrize(
    "name", ("origin", "loop", "loop/snapshot", "loop/component.json", "handoff.json")
)
def test_linked_payload_is_refused_without_touching_external_origin(name, tmp_path):
    value = public.prepare(initial.initialize(request()))
    root = public.write_handoff(tmp_path / "managed", value)
    public.load_handoff(root)
    target = root / name
    external = tmp_path / "external"
    shutil.move(target, external)
    paths = [external] if external.is_file() else sorted(external.rglob("*"))
    before = {str(path): paired._sha(path) for path in paths if path.is_file()}
    target.symlink_to(external, target_is_directory=external.is_dir())
    with pytest.raises(ConfigError, match="must not contain symbolic links"):
        public.load_handoff(root)
    assert target.is_symlink()
    assert {path: paired._sha(Path(path)) for path in before} == before
    evidence(
        "external-link-refusal-" + name.replace("/", "-"),
        dict(directory=str(root), linked_entry=name, external_files_sha256=before),
    )


def test_exhausted_future_draw_retains_complete_initial_parent(tmp_path):
    raw = request()
    raw["component"]["next_tick"] = 2**64 - 2
    origin = initial.initialize(raw)
    value = public.prepare(origin)
    root = public.write_handoff(tmp_path / "managed", value)
    assert origin.component.stream.next_tick == 2**64 - 1
    with pytest.raises(loop.TissueLoopRejected) as caught:
        paired.advance_loop_checkpoint(
            root / "loop", tmp_path / "refused", origin.binding.component
        )
    failure = caught.value
    assert not (tmp_path / "refused").exists() and not failure.tissue_steps
    assert initial._arrays(failure.source_checkpoint) == initial._arrays(origin.checkpoint)
    assert (
        initial.streams.stream_record(failure.source_component.stream)
        == origin.provenance["active_stream"]
    )
    arrays = {}
    tree_arrays(failure.source_checkpoint.state, "source", arrays)
    tree_arrays(failure.source_checkpoint.layout, "layout", arrays)
    if failure.component_rejection is not None and failure.component_rejection.trial is not None:
        tree_arrays(failure.component_rejection.trial.protein, "trial_protein", arrays)
        tree_arrays(failure.component_rejection.trial.diffusion, "trial_diffusion", arrays)
    evidence(
        "counter-refusal",
        dict(
            provenance=origin.provenance,
            failure=str(failure),
            stage=failure.stage,
            proposed_stream=None
            if failure.proposed_stream is None
            else initial.streams.stream_record(failure.proposed_stream),
            accepted_numeric_steps=0,
            destination_created=False,
        ),
        arrays,
    )


def test_fresh_cli_handoff_and_validation(tmp_path):
    origin = initial.initialize(request())
    public.initial_io.write_initialization(tmp_path / "origin", origin)
    commands = [
        [
            sys.executable,
            "-B",
            "-m",
            "validation.betse.physiology.physiology_initial_loop_io",
            "prepare",
            str(tmp_path / "origin"),
            "--output",
            str(tmp_path / "managed"),
        ],
        [
            sys.executable,
            "-B",
            "-m",
            "validation.betse.physiology.physiology_initial_loop_io",
            "validate",
            str(tmp_path / "managed"),
        ],
    ]
    results = []
    for command in commands:
        result = subprocess.run(
            command, capture_output=True, text=True, check=True, env=dict(os.environ)
        )
        results.append(json.loads(result.stdout))
    assert results[0] == results[1]
    with pytest.raises(FileExistsError):
        public.write_handoff(tmp_path / "managed", public.prepare(origin))
    evidence("public-cli", dict(commands=commands, results=results))
