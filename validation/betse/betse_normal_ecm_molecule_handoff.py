"""Saved owner-declaration diagnosis and release-held Cells continuity checks.

Reading saved declarations admits no INIT parent and executes no geometry,
setup, RNG, timestep or transition. Actual transition/continuation work requires
the existing Root run-lifecycle release and retains each invocation/output.
"""

import argparse
import gc
import hashlib
import json
import os
import struct
import sys
from pathlib import Path

from validation.betse.betse_normal_ecm_init_phase_capture import record_failure
from validation.source_snapshot import write_json

RELEASE_ENV = "CELLS_ECM_MOLECULE_RUN_LIFECYCLE_RELEASED"
MAX_DATA_BYTES = 32 * 2**20
MAX_EVIDENCE_BYTES = 96 * 2**20
OWNER_PATHS = {
    "geometry": ("geometry",),
    "world": ("world",),
    "current_geometry": ("current_definition", "geometry"),
    "ions": ("current_definition", "ions"),
}


def _sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _json(path, limit):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
        raise ValueError("Bounded regular saved metadata required: " + str(path))

    def pairs(rows):
        result = {}
        for key, value in rows:
            if key in result:
                raise ValueError("Duplicate saved metadata key")
            result[key] = value
        return result

    def invalid(value):
        raise ValueError("Nonstandard saved metadata scalar: " + value)

    return json.loads(path.read_bytes(), object_pairs_hook=pairs, parse_constant=invalid)


def _archive(directory):
    manifest = _json(directory / "manifest.json", 2**20)
    if (
        set(manifest) != {"kind", "complete", "files"}
        or manifest["kind"] != "cells.betse_normal_current_raw_evidence@1"
        or manifest["complete"] is not True
        or set(manifest["files"]) != {"data.json", "arrays.npz"}
    ):
        raise ValueError("Complete saved raw archive required")
    for name, value in manifest["files"].items():
        path = directory / name
        if (
            path.is_symlink()
            or not path.is_file()
            or path.stat().st_size > MAX_EVIDENCE_BYTES
            or _sha(path) != value
        ):
            raise ValueError("Changed saved handoff evidence: " + name)
    return dict(
        path=str(directory),
        manifest_sha256=_sha(directory / "manifest.json"),
        files=manifest["files"],
    )


def _get(node, *keys):
    for key in keys:
        if type(node) is not dict or set(node) != {"mapping"}:
            raise ValueError("Expected saved raw mapping at " + key)
        rows = node["mapping"]
        values = dict(rows)
        if len(values) != len(rows):
            raise ValueError("Duplicate saved raw owner key")
        node = values[key]
    return node


def _declaration(node):
    """Decode only JSON declaration data, never state/cache arrays or objects."""
    if type(node) in (type(None), str, int, bool):
        return node
    if type(node) is not dict:
        raise ValueError("Unexpected saved declaration node")
    if set(node) == {"mapping"}:
        rows = node["mapping"]
        if len({key for key, _ in rows}) != len(rows):
            raise ValueError("Duplicate saved owner mapping")
        return {key: _declaration(value) for key, value in rows}
    if set(node) == {"sequence"}:
        return [_declaration(value) for value in node["sequence"]]
    if set(node) == {"float64_bits"}:
        return struct.unpack("<d", bytes.fromhex(node["float64_bits"]))[0]
    raise ValueError("Only saved declaration scalars/sequences are supported; no state hydration")


def differences(left, right, path=""):
    """Record order separately; never normalize coordinates or owner axes."""
    result = []
    if type(left) is dict and type(right) is dict:
        if set(left) != set(right):
            result.append(dict(path=path, kind="mapping_keys", INIT=list(left), SIM=list(right)))
        elif list(left) != list(right):
            result.append(dict(path=path, kind="mapping_order", INIT=list(left), SIM=list(right)))
        for key in left:
            if key in right:
                result.extend(differences(left[key], right[key], path + "/" + key))
    elif type(left) is list and type(right) is list:
        if len(left) != len(right):
            result.append(dict(path=path, kind="sequence_extent", INIT=len(left), SIM=len(right)))
        for index, (before, after) in enumerate(zip(left, right, strict=False)):
            result.extend(differences(before, after, path + "/" + str(index)))
    elif type(left) is not type(right) or (
        struct.pack("<d", left) != struct.pack("<d", right)
        if type(left) is float and type(right) is float
        else left != right
    ):
        result.append(
            dict(
                path=path,
                kind="value_or_type",
                INIT=left,
                SIM=right,
                INIT_type=type(left).__name__,
                SIM_type=type(right).__name__,
            )
        )
    return result


def compare_saved(transition_directory):
    """Project the original saved parent/failed-input pair, without replay."""
    directory = Path(transition_directory)
    artifacts = {
        name: _archive(directory / name)
        for name in ("actual-complete-INIT", "SIM-component-binding", "actual-INIT-to-SIM")
    }
    encoded = _json(directory / "actual-complete-INIT/data.json", MAX_DATA_BYTES)
    returned = _get(encoded, "returned")
    completed = _get(returned, "complete_init")
    old = json.loads(
        _get(completed, "binding", "material_binding", "geometry_binding", "definition_json")
    )
    old_supplied = _get(
        completed, "binding", "inputs_raw", "field", "definition", "environment_geometry_definition"
    )
    original_raw_owners = {
        name: _declaration(_get(old_supplied, *keys)) for name, keys in OWNER_PATHS.items()
    }
    identities = dict(
        complete_init=_get(completed, "identity"),
        INIT_binding=_get(completed, "binding", "identity"),
        INIT_parent=_get(completed, "parent", "identity"),
        completed_run=_get(returned, "identity"),
    )
    del encoded, returned, completed
    gc.collect()
    encoded = _json(directory / "SIM-component-binding/data.json", MAX_DATA_BYTES)
    component = _get(encoded, "returned")
    supplied = _declaration(
        _get(
            component,
            "inputs",
            "sim_phase",
            "field",
            "definition",
            "environment_geometry_definition",
        )
    )
    bound = json.loads(
        _get(
            component,
            "declaration",
            "base",
            "material_binding",
            "geometry_binding",
            "definition_json",
        )
    )
    identities.update(
        SIM_component=_get(component, "identity"),
        SIM_expected_INIT=_get(component, "expected_init_identity"),
    )
    if identities["SIM_expected_INIT"] != identities["INIT_binding"]:
        raise ValueError("Saved SIM declaration names a different INIT binding")
    projected = {}
    for name, keys in OWNER_PATHS.items():
        before, raw, after = old, supplied, bound
        for key in keys:
            before, raw, after = before[key], raw[key], after[key]
        projected[name] = dict(
            INIT=before,
            raw_SIM=raw,
            bound_SIM=after,
            original_raw_differences=differences(original_raw_owners[name], raw),
            raw_differences=differences(before, raw),
            bound_differences=differences(before, after),
        )
    return dict(
        source_artifacts=artifacts,
        identities=identities,
        projections=projected,
        whole_bound_definition_differences=differences(old, bound),
        scientific_acceptance=False,
        actual_setup_bind_transition_RNG_timestep_calls=0,
        scope="Saved JSON declarations only; no state/cache hydration or parent admission",
    )


def actual_continuity(directory, *, case):
    """Prospective short actual check; no native/reference or checkpoint parity.

    The existing Root release is checked before any evolving call/output. Both
    continuation branches are executions and are retained/counted separately.
    Failures stay failures; no known-refusal xfail, replay-as-load or retry.
    """
    if os.environ.get(RELEASE_ENV) != "1":
        raise RuntimeError("Held actual handoff/continuity: Root run-lifecycle release required")
    if case not in {"zero_INIT_calls", "one_INIT_call"}:
        raise ValueError("Use an original bounded INIT specimen for prospective continuity")
    from cells.processes import betse_normal_ecm_molecule_checkpoint as checkpoint
    from cells.processes import betse_normal_ecm_molecule_run_lifecycle as run
    from validation.betse import betse_normal_ecm_molecule_checkpoint as preparation

    directory = Path(directory)
    directory.mkdir(exist_ok=False)
    attempts = []
    (directory / "operations").mkdir()
    take = preparation._retainer(directory / "operations", attempts)

    def checkpoint_call(name, operation):
        event = dict(
            operation=name,
            numerical_work_possible=True,
            status="attempted",
            operation_status="attempted",
        )
        attempts.append(event)
        try:
            value = operation()
        except BaseException:
            event.update(status="refused", operation_status="refused")
            raise
        event["operation_status"] = "returned"
        receipt = value.receipt if type(value) is checkpoint.Loaded else value
        metadata = dict(vars(receipt), directory=str(receipt.directory))
        try:
            preparation.archives.write_archive(
                directory / "operations" / name,
                dict(
                    receipt=metadata,
                    actual_checkpoint_operations=str(directory / "checkpoint"),
                    actual_load_operations=str(directory / "load")
                    if name == "checkpoint-load"
                    else None,
                ),
            )
        except BaseException:
            event["status"] = "retention_refused"
            raise
        event["status"] = "returned"
        return value

    binding = parent = sim_binding = sim = loaded = None
    try:
        binding, parent = preparation.prepare_INIT(directory / "INIT", case, attempts)
        parent = preparation.accepted_prefix(
            directory / "INIT-calls", binding, parent, attempts, calls=binding.calendar.step_count
        )
        init_identity = parent.identity
        sim_binding, sim = preparation.prepare_SIM(
            directory / "transition", binding, parent, attempts, case=case
        )
        source_init = sim.active.source_init
        assert sim.entry_receipt["previous_phase"].run.identity == init_identity
        assert source_init.binding.identity == binding.composition.identity
        for identity in sim.active.receipt["source_setup"]["dual_owners_reinitialized"][
            "owner_identity"
        ].values():
            if identity is not None:
                assert identity["owner_retained"] and identity["core_retained"]
                assert all(identity["molecule_objects_retained"].values())
                assert identity["fresh_cold_owner_created"] is False
                assert identity["read_substances_called"] is False
        before = checkpoint.codec.fingerprint((sim_binding, sim))
        sim = preparation.accepted_prefix(
            directory / "SIM-prefix", sim_binding, sim, attempts, calls=1
        )
        paused = take("SIM-pause", lambda: run.pause(sim_binding, sim), parent=sim)
        saved = checkpoint_call(
            "checkpoint-save",
            lambda: checkpoint.save_checkpoint(
                directory / "checkpoint",
                sim_binding,
                paused,
                expected_phase="SIM",
                expected_parent_identity=paused.identity,
            ),
        )
        loaded = checkpoint_call(
            "checkpoint-load",
            lambda: checkpoint.load_checkpoint(
                directory / "checkpoint",
                binding=sim_binding,
                expected_phase="SIM",
                expected_parent_identity=paused.identity,
                expected_checkpoint_identity=saved.identity,
                evidence_directory=directory / "load",
            ),
        )
        assert checkpoint.codec.fingerprint((sim_binding, paused)) == checkpoint.codec.fingerprint(
            (loaded.binding, loaded.parent)
        )
        take(
            "loaded-ownership",
            lambda: run.verify(loaded.binding, loaded.parent),
            parent=loaded.parent,
        )
        restored = take(
            "SIM-resume", lambda: run.resume(loaded.binding, loaded.parent), parent=loaded.parent
        )
        uninterrupted = preparation.accepted_prefix(
            directory / "uninterrupted", sim_binding, sim, attempts, calls=1
        )
        continued = preparation.accepted_prefix(
            directory / "restored", loaded.binding, restored, attempts, calls=1
        )
        assert uninterrupted.identity == continued.identity
        assert checkpoint.codec.fingerprint(
            (sim_binding, uninterrupted)
        ) == checkpoint.codec.fingerprint((loaded.binding, continued))
        assert (
            parent.identity == init_identity
            and source_init.parent.identity == parent.active.identity
        )
        result = dict(
            case=case,
            status="conditional_continuity_returned",
            INIT_parent=init_identity,
            SIM_entry_fingerprint=before,
            checkpoint=saved.identity,
            cursor=continued.cursor,
            journals=len(continued.history),
            observations=len(continued.observations),
            restored_exact=True,
            native_reference_parity=False,
            scientific_acceptance=False,
        )
    except BaseException as error:
        record_failure(
            error,
            stage="held_actual_handoff_continuity",
            readers={
                "INIT_binding": lambda: binding,
                "INIT_parent": lambda: parent,
                "SIM_binding": lambda: sim_binding,
                "SIM_prefix": lambda: sim,
                "attempts": lambda: attempts,
                "partial": lambda original_error=error: getattr(original_error, "partial", None),
            },
            retain=lambda value: preparation.archives.write_archive(
                directory / "failure", run.ions.data(value)
            ),
        )
        raise
    finally:
        primary = sys.exception()
        try:
            write_json(
                directory / "attempts.json",
                dict(
                    attempts=attempts,
                    policy=(
                        "Root invocations counted; nested checkpoint verification "
                        "also appears in checkpoint operation records"
                    ),
                ),
            )
        except BaseException as logging_error:
            if primary is not None:
                primary.add_note("Attempt ledger write failed: " + repr(logging_error))
            else:
                raise
    write_json(directory / "result.json", result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--saved-transition-directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(exist_ok=False)
    result = compare_saved(args.saved_transition_directory)
    write_json(args.output / "owner-comparison.json", result)


if __name__ == "__main__":
    main()
