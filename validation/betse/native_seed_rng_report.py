"""Explicit RNG-witness@2 reader, reusing the immutable legacy report checks.

The legacy c9f3 reader remains byte-exact. No witness or plan is relabelled, and
file-backed witness@1 continues through that original reader unchanged.
"""

import hashlib
import json
from pathlib import Path
from types import CodeType, FunctionType

from validation import source_snapshot as snapshot
from validation.betse import native_rng_runtime as runtime
from validation.betse import native_seed_demo_report as legacy

FILE = "validation/betse/native_seed_rng_report.py"
KIND = "cells.saved_seed_rng_demo_report@2"
LEGACY_SHA256 = "c9f3d6002e1faf680209c66123624ec6793c99781eb91179ee98974f1f627ad7"
LEGACY_KIND = legacy.INITIAL_RNG_KIND
WITNESS_KIND = "cells.common_initial_rng_observation@2"
DEMO, INITIAL_RNG = legacy.DEMO, legacy.INITIAL_RNG
INITIAL_RNG_EPOCH, INITIAL_RNG_BOUNDARY = legacy.INITIAL_RNG_EPOCH, legacy.INITIAL_RNG_BOUNDARY
require, _hash_identity = legacy.require, legacy._hash_identity


def source_plan():
    return dict(
        kind=KIND,
        legacy_report_sha256=LEGACY_SHA256,
        witness_versions=[LEGACY_KIND, WITNESS_KIND],
        shared_runtime=runtime.FILE,
        built_in_origin_is_file=False,
        state_reset_draw_or_replacement=False,
        common_starting_authority_established=False,
        scientific_credit=0,
    )


def initial_rng_declaration(
    reader,
    plan,
    demo,
    bundle,
    parameters,
    files,
    *,
    demo_kind=legacy.DEMO_KINDS[6],
    launch_kind=legacy.LAUNCH_KINDS[6],
):
    """Authenticate saved input/source declarations, without importing an observer."""
    if demo.get("kind") != demo_kind:
        require(
            "initial_rng_inputs" not in demo and "initial_rng_inputs" not in plan,
            "Initial RNG input declaration requires demo@8",
        )
        return None
    from validation.betse import native_seed_demo_input_profiles as profiles

    require(plan["kind"] == launch_kind, "Initial RNG observation requires launch@12")
    selected = demo.get("initial_rng_inputs")
    require(
        type(selected) is dict
        and set(selected) == {"profile", "inventory", "inventory_sha256"}
        and json.dumps(plan.get("initial_rng_inputs"), sort_keys=True, allow_nan=False)
        == json.dumps(selected, sort_keys=True, allow_nan=False)
        and selected["profile"]
        == profiles.require_profile(bundle.get("configuration_profile", "original"))
        == parameters["program"].get("input_profile", "original")
        and selected["inventory"] == profiles.selected_inventory(bundle),
        "Complete initial RNG input/profile declaration required",
    )
    inventory = selected["inventory"]
    require(
        type(inventory) is dict and set(inventory) == {"directories", "files"},
        "Full initial directory/file inventory required",
    )
    directories, inputs = inventory["directories"], inventory["files"]
    require(
        type(directories) is list
        and all(type(name) is str for name in directories)
        and directories == sorted(set(directories))
        and type(inputs) is dict
        and 0 < len(inputs) <= 512
        and len(inputs) + len(directories) <= 1024,
        "Bounded initial directory/file inventory required",
    )
    for name in (*directories, *inputs):
        snapshot.relative_path(name)
        require(
            all(str(parent) in directories for parent in Path(name).parents if str(parent) != "."),
            "Complete initial input ancestor directory roster required",
        )
    require(not set(directories).intersection(inputs), "Initial file/directory roles overlap")
    total = 0
    for name, row in inputs.items():
        require(
            type(row) is dict
            and set(row) == {"size_bytes", "sha256"}
            and type(row["size_bytes"]) is int
            and 0 <= row["size_bytes"] <= 8 * 2**20
            and _hash_identity(row["sha256"]),
            "Exact initial input extent/digest required",
        )
        actual = reader.bind(
            dict(path=str(Path(parameters["program"]["root"]) / name), sha256=row["sha256"])
        )
        require(actual.stat().st_size == row["size_bytes"], "Initial input extent changed")
        total += row["size_bytes"]
    require(total <= 16 * 2**20, "Initial input byte bound exceeded")
    digest = hashlib.sha256(
        json.dumps(inventory, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    require(
        _hash_identity(selected["inventory_sha256"]) and selected["inventory_sha256"] == digest,
        "Initial input inventory digest changed",
    )
    producer = files.get(INITIAL_RNG)
    require(
        _hash_identity(producer) and plan["producers"].get(INITIAL_RNG) == producer,
        "Original initial RNG producer missing from closure",
    )
    policy = demo.get("source_plan", {}).get("initial_rng_observation")
    require(type(policy) is dict, "Explicit initial RNG version required")
    version = policy.get("kind")
    require(version in (LEGACY_KIND, WITNESS_KIND), "Unsupported initial RNG witness version")
    extra = {}
    if version == WITNESS_KIND:
        expected = files.get(runtime.FILE)
        require(
            _hash_identity(expected) and plan["producers"].get(runtime.FILE) == expected,
            "Built-in RNG provenance helper missing from source closure",
        )
        extra = dict(
            runtime_producer="validation.betse.native_rng_runtime", runtime_producer_sha256=expected
        )
    plan["_initial_rng_kind"] = version
    require(
        policy
        == dict(
            kind=version,
            epoch=INITIAL_RNG_EPOCH,
            boundary=INITIAL_RNG_BOUNDARY,
            full_numpy_MT_and_python_state=True,
            complete_input_inventory_bound=True,
            reset_draw_or_replacement=False,
            common_starting_authority_established=False,
            producer="validation.betse.native_seed_initial_rng",
            producer_sha256=producer,
            **extra,
        )
        and all(
            type(policy[k]) is bool
            for k in (
                "full_numpy_MT_and_python_state",
                "complete_input_inventory_bound",
                "reset_draw_or_replacement",
                "common_starting_authority_established",
            )
        ),
        "Exact observation-only initial RNG source policy required",
    )
    return selected


def initial_rng_captures(reader, root, plan, value, captures, *, prefix=()):
    selected = plan.get("_initial_rng_inputs")
    labels = ("before_seed_random_states", "pre_seed_rng_witness")
    rows = [row for row in value["captures"] if row["label"] in labels]
    observation = value.get("initial_rng_observation")
    if selected is None:
        require(not rows and observation is None, "Legacy demo cannot promote initial RNG captures")
        return None
    require(
        value.get("common_starting_authority_established") is False,
        "Initial RNG evidence grants no common starting authority",
    )
    if observation is None:
        require(
            value["status"] != "completed"
            and not any(
                row["name"] == "geometry"
                or (row["name"] == "initial_rng" and row["status"] == "returned")
                for row in value["operations"]
            ),
            "Missing initial RNG witness before geometry/completion",
        )
        return dict(observed=False, capture_rows=rows, common_starting_authority_established=False)
    require(
        type(observation) is dict
        and set(observation) == {"path", "sha256", "label", "status"}
        and len(rows) == 2
        and [row["label"] for row in rows] == list(labels)
        and all(row["status"] == "saved" for row in rows)
        and observation == rows[1],
        "Exact completed initial RNG capture row required",
    )
    indices = [value["captures"].index(row) for row in rows]
    require(indices[1] == indices[0] + 1, "Initial random captures must remain consecutive")
    raw = next(row["initial_rng_wire"] for row in captures if row["label"] == labels[0])
    witness = next(row["initial_rng_wire"] for row in captures if row["label"] == labels[1])
    legacy._initial_rng_state(raw)
    require(type(witness) is dict, "Original initial RNG witness object required")
    legacy._initial_rng_state(witness.get("state"))
    require(
        type(witness) is dict
        and set(witness)
        == {
            "kind",
            "epoch",
            "common_binding",
            "state",
            "source",
            "order",
            "observed_states_equalized",
            "common_starting_authority_established",
            "scientific_physical_checkpoint_credit",
        }
        and witness["kind"] == plan.get("_initial_rng_kind", LEGACY_KIND)
        and witness["epoch"] == INITIAL_RNG_EPOCH
        and witness["state"] == raw
        and witness["observed_states_equalized"] is False
        and witness["common_starting_authority_established"] is False
        and type(witness["scientific_physical_checkpoint_credit"]) is int
        and witness["scientific_physical_checkpoint_credit"] == 0,
        "Complete initial RNG witness is observation only",
    )
    common = witness["common_binding"]
    require(
        type(common) is dict
        and set(common) == {"input_inventory_sha256", "mode", "profile", "runtime"}
        and common["input_inventory_sha256"] == selected["inventory_sha256"]
        and common["mode"] == plan["flux_operator"]
        and common["profile"] == selected["profile"],
        "Initial RNG selected input/mode/profile binding changed",
    )
    require(
        witness["source"]
        == dict(
            files={
                name: plan["producers"][name]
                for name in (
                    (INITIAL_RNG, DEMO, runtime.FILE)
                    if witness["kind"] == WITNESS_KIND
                    else (INITIAL_RNG, DEMO)
                )
            },
            snapshot_sha256=plan["source_snapshot"]["sha256"],
            parameter_packet_sha256=plan["parameter_inputs"]["sha256"],
        ),
        "Initial RNG source epoch changed",
    )
    order = witness["order"]
    prefix = [*prefix, "callback", "constructor_preflight", "parameters", "initial_rng"]
    require(
        type(order) is dict
        and set(order)
        == {
            "boundary",
            "parameter_identity",
            "world_ready_identity",
            "callback_identity",
            "same_parameter",
            "seed_entered",
            "selected_boundaries",
        }
        and order["boundary"] == INITIAL_RNG_BOUNDARY
        and order["same_parameter"] is True
        and order["seed_entered"] is False
        and all(
            type(order[k]) is int and order[k] > 0
            for k in ("parameter_identity", "world_ready_identity", "callback_identity")
        )
        and order["selected_boundaries"]
        == [
            [name, "returned" if i < len(prefix) - 1 else "attempted"]
            for i, name in enumerate(prefix)
        ]
        and [row["name"] for row in value["operations"][: len(prefix)]] == prefix
        and all(row["status"] == "returned" for row in value["operations"][: len(prefix) - 1]),
        "Initial RNG observation must precede phase/geometry construction",
    )
    final_path = root.parent / "runtime-after.json"
    final = reader.read(final_path) if final_path.exists() else None
    runtime.validate_saved(
        reader,
        common["runtime"],
        executable=plan["runtime"]["executable"],
        runtime_roots=plan["runtime_roots"],
        final=final,
        completed=value["status"] == "completed",
    )
    return dict(
        observed=True,
        capture_row=observation,
        inventory_sha256=selected["inventory_sha256"],
        epoch=witness["epoch"],
        state_bytes_preserved=True,
        common_starting_authority_established=False,
        observed_states_equalized=False,
        scientific_physical_checkpoint_credit=0,
    )


def _runtime(reader, root, plan, files):
    result = legacy._runtime(reader, root, plan, files)
    if plan.get("_initial_rng_kind") == WITNESS_KIND:
        require(
            result["snapshot_producers"].get(runtime.FILE) == plan["producers"][runtime.FILE],
            "Actual built-in RNG provenance producer missing",
        )
    return result


def _namespace():
    path = Path(legacy.__file__)
    require(snapshot.digest(path) == LEGACY_SHA256, "Immutable legacy report changed")
    codes = {
        c.co_name: c
        for c in compile(path.read_bytes(), str(path), "exec", dont_inherit=True).co_consts
        if type(c) is CodeType
    }
    namespace = dict(
        vars(legacy),
        KIND=KIND,
        _initial_rng_declaration=initial_rng_declaration,
        _initial_rng_captures=initial_rng_captures,
        _runtime=_runtime,
    )
    for name in ("_plan", "_outcome", "inspect_attempt"):
        actual = vars(legacy)[name]
        require(
            type(actual) is FunctionType
            and actual.__globals__ is vars(legacy)
            and actual.__code__ == codes[name]
            and actual.__closure__ is None,
            "Original saved-reader executable required",
        )
        function = FunctionType(actual.__code__, namespace, name, actual.__defaults__)
        function.__kwdefaults__ = actual.__kwdefaults__
        namespace[name] = function
    return namespace


def inspect_attempt(plan_path, *, plan_sha256, output=None):
    """Read only authenticated saved artifacts; never mutate the old schema."""
    namespace = _namespace()
    reader = legacy.Reader()
    plan = reader.read(Path(plan_path), plan_sha256)
    declaration = reader.bound(plan["demo_plan"])
    version = declaration.get("source_plan", {}).get("initial_rng_observation", {}).get("kind")
    if version in (None, LEGACY_KIND):
        return legacy.inspect_attempt(plan_path, plan_sha256=plan_sha256, output=output)
    require(version == WITNESS_KIND, "Unsupported initial RNG witness version")
    return namespace["inspect_attempt"](plan_path, plan_sha256=plan_sha256, output=output)
