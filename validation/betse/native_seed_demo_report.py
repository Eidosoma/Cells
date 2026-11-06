"""Read saved SEED demonstrations without importing or running BETSE.

A completed report establishes recorded execution and evidence consistency only.
It neither compares numerical solutions nor grants INIT, SIM or restart parity.
Original and disabled flux-inverse modes retain their separate dispositions.
"""

import argparse
import ast
import hashlib
import json
import math
import re
import struct
import zipfile
from pathlib import Path

from validation import source_snapshot as snapshot
from validation.betse import native_seed_demo_evidence as evidence
from validation.betse import native_single_cell_prefix_payload as payload

KIND = "cells.saved_seed_demo_report@1"
LAUNCH_KINDS = tuple(
    f"cells.genuine_seed_demo_detached_launch@{v}" for v in (6, 7, 8, 9, 10, 11, 12)
)
DEMO_KINDS = tuple(
    f"cells.genuine_seed_core_profiles_junctions_demo@{v}" for v in (2, 3, 4, 5, 6, 7, 8)
)
ENDPOINTS = (
    "seed",
    "init_setup",
    "init_prelude",
    "init_dynamics",
    "init_electrical",
    "init_first_step",
    "init_short_history",
    "init_terminal",
)
DEMO = "validation/betse/native_seed_demo.py"
LAUNCH = "validation/betse/native_seed_demo_launch.py"
PARAMETER = "validation/betse/betse_native_parameter_world_ready_qualification.py"
NUMPY_ORIGIN = "src/cells/processes/betse_native_numpy_copy_origin.py"
NUMPY_ORIGIN_KIND = "cells.original_numpy_copy_import_origin@1"
MOLECULE_WRAPPER = "src/cells/processes/betse_native_init_molecule_wrapper_authority.py"
IMPORT_PROTOCOL = "closed_original_molecule_import_before_callback_handoff@1"
INITIAL_RNG = "validation/betse/native_seed_initial_rng.py"
INITIAL_RNG_KIND = "cells.common_initial_rng_observation@1"
INITIAL_RNG_EPOCH = "pre_SEED_before_world_construction"
INITIAL_RNG_BOUNDARY = "after_issued_WorldReady_before_geometry_phase_construction"
RNG_MODULES = (
    "numpy",
    "numpy.random",
    "numpy.random.mtrand",
    "numpy.random._mt19937",
    "numpy.random.bit_generator",
    "random",
    "_random",
)
WRAPPER_ENDPOINTS = (
    "init_dynamics",
    "init_electrical",
    "init_first_step",
    "init_short_history",
    "init_terminal",
)
GEOMETRY_STAGES = (
    "four_aliases",
    "cell_index",
    "cellVerts",
    "cellMatrices",
    "cell_vols",
    "mem_processing",
    "near_neigh",
    "makeECM",
    "environment",
    "grid_len",
    "make_maskM",
)


COMMON_FILE = "validation/betse/native_common_start_rng.py"
COMMON_ORIGINAL = "validation/betse/native_init_terminal_reference.py"
COMMON_KIND = "cells.explicit_fresh_common_start_rng_program@1"
COMMON_DECLARATION = "cells.paired_common_start_preparation@1"
COMMON_EPOCH = "after_parameters_before_world_construction"
COMMON_SHA256 = "b52c20c4ede1fc9afbcefd9f22e65626156852cae552a12c14837e65dd1b9eb4"
COMMON_REVIEW_SHA256 = "58e4090dfaf544435bd132b703e470d59d49381ade83ea25a7ab0fe3a919d72e"
COMMON_STEPS = (
    ("python_before", "python_get", None),
    ("numpy_before", "numpy_get", None),
    ("python_seed", "python_seed", "python_seed"),
    ("python_after", "python_get", None),
    ("numpy_seed", "numpy_seed", "numpy_seed"),
    ("numpy_after", "numpy_get", None),
    ("python_readback", "python_get", None),
    ("numpy_readback", "numpy_get", None),
)


def source_plan():
    return dict(
        kind=KIND,
        accepted_launch_kinds=LAUNCH_KINDS,
        accepted_outcome_kinds=DEMO_KINDS,
        endpoints=ENDPOINTS,
        owner_hydration=False,
        model_execution=False,
        numerical_comparison=False,
        polling=False,
        scientific_credit=0,
        parameter_load_prefix="Saved returns and archive bytes; never usable-owner credit",
        parameter_reader_bounds=dict(operations=32, archives=1024, aggregate_file_bytes=2**30),
    )


def require(value, message):
    if not value:
        raise ValueError(message)


def _common_document(value):
    """Independent saved-data parser; no executable RNG producer is imported."""
    require(type(value) is dict, "Exact common-start program document required")
    require(
        type(value.get("python_seed")) is int
        and 0 <= value["python_seed"] < 2**256
        and type(value.get("numpy_seed")) is int
        and 0 <= value["numpy_seed"] < 2**32
        and _hash_identity(value.get("input_identity"))
        and type(value.get("consumer_sources")) is dict
        and set(value["consumer_sources"]) == {"cells", "original"}
        and all(_hash_identity(pin) for pin in value["consumer_sources"].values()),
        "Declared bounded seeds, both callers and input inventory required",
    )
    expected = dict(
        kind=COMMON_KIND,
        epoch=COMMON_EPOCH,
        python_seed=value["python_seed"],
        python_seed_version=2,
        numpy_seed=value["numpy_seed"],
        numpy_api="legacy global RandomState.seed",
        input_identity=value["input_identity"],
        consumer_sources=value["consumer_sources"],
        operations=[list(row) for row in COMMON_STEPS],
        draws=0,
        setstate_or_generator_replacement=False,
    )
    require(_common_seal(value) == _common_seal(expected), "Canonical program changed")
    return expected


def _common_seal(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def _common_declaration(reader, plan, demo, files):
    selected = "common_start" in demo
    require(("common_start" in plan) is selected, "Common-start declaration association changed")
    if not selected:
        require(
            "common_start" not in demo.get("source_plan", {})
            and "CELLS_COMMON_START_RNG_RELEASED" not in plan.get("release_environment", {}),
            "Ambient source policy cannot silently select common start",
        )
        return None
    value = demo["common_start"]
    require(
        type(value) is dict
        and set(value) == {"kind", "mode", "program", "program_identity", "provider"}
        and value["kind"] == COMMON_DECLARATION
        and value["mode"] == plan["flux_operator"]
        and _common_seal(plan["common_start"]) == _common_seal(value)
        and _common_seal(demo["source_plan"].get("common_start")) == _common_seal(value),
        "Exact per-mode prepared common-start program required",
    )
    doc = _common_document(value["program"])
    require(
        _hash_identity(COMMON_SHA256)
        and _hash_identity(COMMON_REVIEW_SHA256)
        and value["provider"]
        == dict(file=COMMON_FILE, sha256=COMMON_SHA256, review_sha256=COMMON_REVIEW_SHA256)
        and value["program_identity"] == _common_seal(doc)
        and doc["input_identity"] == plan["_initial_rng_inputs"]["inventory_sha256"]
        and doc["consumer_sources"] == {"cells": files[DEMO], "original": files[COMMON_ORIGINAL]}
        and files.get(COMMON_FILE) == plan["producers"].get(COMMON_FILE) == COMMON_SHA256
        and plan["producers"].get(COMMON_ORIGINAL) == files[COMMON_ORIGINAL]
        and plan["release_environment"].get("CELLS_COMMON_START_RNG_RELEASED") == "1",
        "Accepted source/review, immutable callers, input and opt-in release required",
    )
    for name in (COMMON_FILE, COMMON_ORIGINAL):
        reader.bind(dict(path=str(Path(plan["source"]) / name), sha256=files[name]))
    return value


def _common_captures(reader, root, plan, value, captures):
    """Authenticate only this process's record; paired starting authority stays separate."""
    rows = [row for row in value["captures"] if row["label"] == "common_start_rng"]
    selected = plan.get("_common_start")
    if selected is None:
        require(
            not rows and "common_start_program" not in value,
            "Ambient outcome cannot promote a common-start return",
        )
        return None
    capture = value.get("common_start_program")
    if capture is None:
        require(
            value["status"] == "failed"
            and not any(row["name"] in ("initial_rng", "geometry") for row in value["operations"]),
            "Common-start failure must precede ambient observation and geometry",
        )
        return dict(completed=False, common_starting_authority_established=False)
    require(
        len(rows) == 1 and capture == rows[0] and capture["status"] == "saved",
        "One original saved common-start return required",
    )
    record = next(
        row["common_start_wire"] for row in captures if row["label"] == "common_start_rng"
    )
    completed = reader.read(root / "common-start-rng/COMPLETED.json")
    require(_common_seal(record) == _common_seal(completed), "Durable publication differs")
    require(
        type(record) is dict
        and set(record)
        == {
            "kind",
            "status",
            "program",
            "program_identity",
            "role",
            "pid",
            "epoch",
            "source",
            "runtime",
            "generator_identities",
            "state",
            "operations",
            "work",
            "states_loaded",
            "generators_replaced",
            "biological_or_phase_admission",
        }
        and record["kind"] == COMMON_KIND
        and record["status"] == "completed"
        and _common_seal(_common_document(record["program"])) == _common_seal(selected["program"])
        and record["program_identity"] == selected["program_identity"]
        and record["role"] == "cells"
        and type(record["pid"]) is int
        and record["pid"] > 0
        and record["epoch"] == COMMON_EPOCH
        and record["operations"] == [[row[0], "returned"] for row in COMMON_STEPS]
        and record["states_loaded"] is record["generators_replaced"] is False
        and record["biological_or_phase_admission"] is False,
        "Actual complete common-start input program required",
    )
    require(
        record["source"]
        == dict(
            helper=COMMON_FILE,
            helper_sha256=COMMON_SHA256,
            provenance="validation/betse/native_rng_runtime.py",
            provenance_sha256=plan["producers"]["validation/betse/native_rng_runtime.py"],
        )
        and type(record["generator_identities"]) is dict
        and set(record["generator_identities"]) == {"python", "numpy"}
        and all(type(n) is int and n > 0 for n in record["generator_identities"].values()),
        "Original helper/provenance and both actual generator identities required",
    )
    states = record["state"]
    require(
        type(states) is dict
        and set(states)
        == {
            kind + "_" + stage
            for kind in ("python", "numpy")
            for stage in ("before", "after", "readback")
        },
        "Complete before/after/readback state evidence required",
    )
    for stage in ("before", "after", "readback"):
        _initial_rng_state(
            dict(
                numpy_random=states["numpy_" + stage],
                python_random=states["python_" + stage],
                initial_random_reset_or_replacement=False,
            )
        )
    require(
        all(
            _common_seal(states[k + "_after"]) == _common_seal(states[k + "_readback"])
            for k in ("python", "numpy")
        ),
        "Program readback changed",
    )
    witness_rows = [row for row in captures if row["label"] == "pre_seed_rng_witness"]
    if witness_rows:
        witness = witness_rows[0]["initial_rng_wire"]
        require(
            value["captures"].index(rows[0])
            < next(
                i
                for i, row in enumerate(value["captures"])
                if row["label"] == "before_seed_random_states"
            )
            and _common_seal(record["runtime"])
            == _common_seal(witness["common_binding"]["runtime"])
            and _common_seal(witness["state"])
            == _common_seal(
                dict(
                    numpy_random=states["numpy_readback"],
                    python_random=states["python_readback"],
                    initial_random_reset_or_replacement=False,
                )
            ),
            "Actual ambient witness differs from common-start readback/runtime/order",
        )
    else:
        require(value["status"] == "failed", "Completed program requires its subsequent witness")
    work = record["work"]
    require(
        type(work) is dict
        and type(work.get("program_API_calls")) is int
        and work["program_API_calls"] == 8
        and type(work.get("visible_RNG_observer_events")) is int
        and 0 < work["visible_RNG_observer_events"] <= 256
        and work.get("opaque_C_internals_not_independent_cases") is True
        and work.get("inherited_observer_RNG_effects_require_reviewed_caller_contract") is True,
        "Bounded actual RNG work required; not independent cases",
    )
    return dict(
        completed=True,
        capture_row=capture,
        program_identity=record["program_identity"],
        common_starting_authority_established=False,
        scientific_credit=0,
    )


def _iterations(plan):
    value = plan.get("init_iterations")
    if plan.get("endpoint", "seed") == "init_short_history":
        require(type(value) is int and 1 <= value <= 64, "Exact short-history count in [1,64]")
    else:
        require(value is None, "Iteration count belongs only to the short-history endpoint")
    return value


def _hash_identity(value):
    return (
        type(value) is str
        and len(value) == 64
        and all(char in "0123456789abcdef" for char in value)
    )


def _initial_rng_declaration(reader, plan, demo, bundle, parameters, files):
    """Authenticate saved input/source declarations, without importing an observer."""
    if demo.get("source_plan", {}).get("initial_rng_observation", {}).get("kind") == (
        "cells.common_initial_rng_observation@2"
    ):
        from validation.betse import native_seed_rng_report as versioned

        return versioned.initial_rng_declaration(reader, plan, demo, bundle, parameters, files)
    if demo.get("kind") != DEMO_KINDS[6]:
        require(
            "initial_rng_inputs" not in demo and "initial_rng_inputs" not in plan,
            "Initial RNG input declaration requires demo@8",
        )
        return None
    from validation.betse import native_seed_demo_input_profiles as profiles

    require(plan["kind"] == LAUNCH_KINDS[6], "Initial RNG observation requires launch@12")
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
    require(
        policy
        == dict(
            kind=INITIAL_RNG_KIND,
            epoch=INITIAL_RNG_EPOCH,
            boundary=INITIAL_RNG_BOUNDARY,
            full_numpy_MT_and_python_state=True,
            complete_input_inventory_bound=True,
            reset_draw_or_replacement=False,
            common_starting_authority_established=False,
            producer="validation.betse.native_seed_initial_rng",
            producer_sha256=producer,
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


def _initial_rng_state(value):
    """Validate archive.snapshot's small fixed MT wire, retaining every float bit."""
    require(
        type(value) is dict
        and set(value) == {"numpy_random", "python_random", "initial_random_reset_or_replacement"}
        and value["initial_random_reset_or_replacement"] is False,
        "Complete observation-only random state required",
    )
    mt, py = value["numpy_random"], value["python_random"]
    require(
        type(mt) is list
        and len(mt) == 5
        and mt[0] == "MT19937"
        and type(mt[2]) is int
        and 0 <= mt[2] <= 624
        and type(mt[3]) is int
        and mt[3] in (0, 1),
        "Complete NumPy MT state required",
    )
    array = mt[1]
    require(
        type(array) is dict
        and set(array) == {"__ndarray__", "dtype", "shape", "strides", "raw_bytes_hex"}
        and array["__ndarray__"] is True
        and array["dtype"] in ("<u4", ">u4")
        and array["shape"] == [624]
        and type(array["shape"][0]) is int
        and array["strides"] == [4]
        and type(array["strides"][0]) is int,
        "Exact archive MT array header required",
    )
    raw = array["raw_bytes_hex"]
    require(
        type(raw) is str
        and len(raw) == 624 * 8
        and bytes.fromhex(raw).hex() == raw
        and any(bytes.fromhex(raw)),
        "Complete nonzero canonical MT bytes required",
    )

    def float_bits(item):
        return (
            type(item) is dict
            and set(item) == {"float64_bits"}
            and type(item["float64_bits"]) is str
            and len(item["float64_bits"]) == 16
            and bytes.fromhex(item["float64_bits"]).hex() == item["float64_bits"]
        )

    require(float_bits(mt[4]), "Original cached Gaussian float bits required")
    require(
        type(py) is list
        and len(py) == 3
        and type(py[0]) is int
        and py[0] == 3
        and type(py[1]) is list
        and len(py[1]) == 625
        and all(type(word) is int and 0 <= word < 2**32 for word in py[1][:-1])
        and type(py[1][-1]) is int
        and 0 <= py[1][-1] <= 624
        and (py[2] is None or float_bits(py[2])),
        "Complete Python MT state required",
    )


def _initial_rng_captures(reader, root, plan, value, captures):
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
    _initial_rng_state(raw)
    require(type(witness) is dict, "Original initial RNG witness object required")
    _initial_rng_state(witness.get("state"))
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
        and witness["kind"] == plan.get("_initial_rng_kind", INITIAL_RNG_KIND)
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
                    (INITIAL_RNG, DEMO, "validation/betse/native_rng_runtime.py")
                    if witness["kind"] == "cells.common_initial_rng_observation@2"
                    else (INITIAL_RNG, DEMO)
                )
            },
            snapshot_sha256=plan["source_snapshot"]["sha256"],
            parameter_packet_sha256=plan["parameter_inputs"]["sha256"],
        ),
        "Initial RNG source epoch changed",
    )
    order = witness["order"]
    prefix = ["callback", "constructor_preflight", "parameters", "initial_rng"]
    if plan.get("_common_start") is not None:
        prefix.insert(prefix.index("initial_rng"), "common_start_rng")
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
    runtime = common["runtime"]
    if witness["kind"] == "cells.common_initial_rng_observation@2":
        from validation.betse import native_rng_runtime as provenance

        final_path = root.parent / "runtime-after.json"
        final = reader.read(final_path) if final_path.exists() else None
        provenance.validate_saved(
            reader,
            runtime,
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
    require(
        type(runtime) is dict
        and set(runtime) == {"python", "executable", "numpy_version", "files"}
        and all(type(runtime[k]) is str and runtime[k] for k in ("python", "numpy_version"))
        and runtime["executable"] == plan["runtime"]["executable"]
        and type(runtime["files"]) is dict
        and set(runtime["files"]) == set(RNG_MODULES),
        "Complete initial RNG runtime binding required",
    )
    reader.bind(runtime["executable"])
    roots = [Path(path) for path in plan["runtime_roots"]]
    for row in runtime["files"].values():
        path = reader.bind(row)
        require(
            any(path.is_relative_to(folder) for folder in roots),
            "Undeclared initial RNG runtime origin",
        )
    final_path = root.parent / "runtime-after.json"
    if final_path.exists():
        final = reader.read(final_path)
        require(
            final.get("python") == runtime["python"]
            and all(
                final["loaded_files"].get(name) == row for name, row in runtime["files"].items()
            ),
            "Initial RNG runtime differs from recorded loaded producers",
        )
    else:
        require(
            value["status"] != "completed",
            "Completed initial RNG witness needs final runtime evidence",
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


class Reader:
    """Bind the files actually read; capture problems remain separate from failures."""

    def __init__(self):
        self.pins, self.issues = {}, []

    def bind(self, row):
        require(type(row) is dict and set(row) == {"path", "sha256"}, "Exact file pin required")
        path = payload._regular(row["path"])
        require(path.is_file() and path.stat().st_nlink == 1, "Regular unlinked file required")
        before = path.stat()
        actual = snapshot.digest(path)
        after = path.stat()
        require(
            (before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
            == (after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns),
            "File changed while hashing",
        )
        require(actual == row["sha256"], "Changed file: " + str(path))
        require(self.pins.get(str(path), actual) == actual, "Conflicting saved file pins")
        self.pins[str(path)] = actual
        return path

    def read(self, path, expected=None):
        path = payload._regular(path)
        value, digest = payload._metadata(path, payload.MAX_METADATA, expected)
        self.bind(dict(path=str(path), sha256=digest))
        require(type(value) is dict, "JSON object required: " + str(path))
        return value

    def bound(self, row):
        return self.read(self.bind(row), row["sha256"])

    def check(self, section, function):
        try:
            return function()
        except Exception as error:
            self.issues.append(dict(section=section, type=type(error).__name__, message=str(error)))
            return None


def _parameter_roster(reader, plan):
    """Read literal public operation labels from the frozen qualifier, never import it."""
    path = reader.bind(
        dict(path=str(Path(plan["source"]) / PARAMETER), sha256=plan["producers"][PARAMETER])
    )
    require(path.stat().st_size <= 2**20, "Qualifier source metadata bound")
    tree = ast.parse(path.read_bytes())
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_execute"]
    require(len(functions) == 1, "Exact frozen qualifier operation source required")
    names = []

    def literal(node, values):
        if isinstance(node, ast.Constant) and type(node.value) is str:
            return node.value
        if isinstance(node, ast.Name) and node.id in values:
            return values[node.id]
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            return literal(node.left, values) + literal(node.right, values)
        raise ValueError("Unsupported dynamic qualifier operation label")

    def scan(statements, values):
        for node in statements:
            if isinstance(node, ast.FunctionDef):
                continue  # The local op adapter is a definition, not another operation.
            calls = [
                n
                for n in ast.walk(node)
                if isinstance(n, ast.Call)
                and isinstance(n.func, ast.Name)
                and n.func.id in ("op", "take")
            ]
            if not calls:
                continue
            if isinstance(node, ast.For):
                require(
                    not node.orelse and isinstance(node.target, ast.Tuple), "Literal qualifier loop"
                )
                rows = ast.literal_eval(node.iter)
                keys = [n.id for n in node.target.elts if isinstance(n, ast.Name)]
                require(
                    len(keys) == len(node.target.elts) and type(rows) is tuple and len(rows) <= 32,
                    "Bounded literal qualifier loop",
                )
                for row in rows:
                    require(
                        type(row) is tuple
                        and len(row) == len(keys)
                        and all(type(v) is str for v in row),
                        "Literal qualifier loop values",
                    )
                    scan(node.body, dict(values, **dict(zip(keys, row, strict=True))))
            else:
                call = node.value if isinstance(node, (ast.Assign, ast.Expr)) else None
                require(
                    len(calls) == 1 and call is calls[0] and len(call.args) >= 2,
                    "Direct original qualifier operation required",
                )
                names.append(literal(call.args[1], values))
                require(len(names) <= 32, "Original qualifier operation count bound")

    scan(functions[0].body, {})
    require(
        len(names) == len(set(names))
        and names[-3:] == ["actual-world-ready", "final-history", "final-live-parameters"],
        "Frozen qualifier final validation order changed",
    )
    require(
        all(re.fullmatch(r"[a-z][a-z0-9-]{0,79}", name) for name in names),
        "Canonical qualifier operation labels required",
    )
    return names


def _parameter_archive(reader, reference, directory, budget):
    """Authenticate opaque codec graphs and full numeric bytes without decoding owners."""
    require(Path(reference["path"]) == directory / "manifest.json", "Parameter archive association")
    manifest = reader.bound(reference)
    require(
        set(manifest)
        == {
            "kind",
            "files",
            "fingerprint",
            "complete",
            "owner_admission",
            "reconstruct_live_owners",
        }
        and manifest["kind"] == "parameter_observation@1"
        and manifest["complete"] is True
        and manifest["owner_admission"] is False
        and manifest["reconstruct_live_owners"] is False
        and _hash_identity(manifest["fingerprint"])
        and set(manifest["files"]) == {"state.json", "arrays.npz"},
        "Complete closed parameter observation manifest required",
    )
    paths = {}
    for name, row in manifest["files"].items():
        require(Path(row["path"]) == directory / name, "Parameter archive file escaped its owner")
        paths[name] = payload._regular(row["path"])
        size = paths[name].stat().st_size
        require(
            size <= (16 if name == "state.json" else 64) * 2**20,
            "Original parameter archive file bound",
        )
        budget["bytes"] += size
        require(budget["bytes"] <= 2**30, "Parameter prefix reader aggregate byte bound")
        reader.bind(row)
        budget["authenticated_bytes"] += size
    budget["archives"] += 1
    require(budget["archives"] <= 1024, "Parameter prefix reader archive count bound")
    tree = reader.read(paths["state.json"], manifest["files"]["state.json"]["sha256"])
    require(
        set(tree) == {"kind", "root", "nodes"}
        and tree["kind"] == "cells.ordinary_ecm_molecule_checkpoint_graph@1"
        and type(tree["nodes"]) is list
        and len(tree["nodes"]) <= 200000,
        "Bounded original parameter codec graph required",
    )
    descriptors = {}
    for node in tree["nodes"]:
        require(type(node) is dict and type(node.get("tag")) is str, "Parameter graph node")
        if node["tag"] in ("array", "scalar"):
            require(
                set(node) == {"tag", "key", "dtype", "shape", "fortran", "writable"}
                and type(node["key"]) is str
                and re.fullmatch(r"a[0-9]{8}", node["key"])
                and node["key"] not in descriptors
                and type(node["writable"]) is bool
                and type(node["shape"]) is list
                and all(type(n) is int for n in node["shape"])
                and (node["tag"] != "scalar" or node["shape"] == []),
                "Unique parameter numeric owner required",
            )
            descriptors[node["key"]] = node
    require(
        set(descriptors) == {f"a{i:08d}" for i in range(len(descriptors))}
        and len(descriptors) <= 8192,
        "Original parameter array roster bound",
    )
    path = paths["arrays.npz"]
    with path.open("rb") as stream:
        require(path.stat().st_size >= 22, "Truncated parameter ZIP")
        stream.seek(-22, 2)
        end = struct.unpack("<4s4H2IH", stream.read(22))
    require(
        end[0] == b"PK\x05\x06"
        and end[1] == end[2] == end[7] == 0
        and end[3] == end[4] == len(descriptors)
        and end[5] + end[6] == path.stat().st_size - 22,
        "Parameter ZIP directory/count",
    )
    # Bound the actual central records before ZipFile allocates its entry list.
    with path.open("rb") as stream:
        stream.seek(end[6])
        stop = end[6] + end[5]
        for _ in range(end[4]):
            central = stream.read(46)
            require(
                len(central) == 46 and central[:4] == b"PK\x01\x02",
                "Truncated parameter ZIP central record",
            )
            name, extra, comment = struct.unpack_from("<3H", central, 28)
            require(
                0 < name <= 32 and extra <= 256 and comment == 0,
                "Original parameter ZIP central record bound",
            )
            stream.seek(name + extra, 1)
            require(stream.tell() <= stop, "Parameter ZIP central extent")
        require(stream.tell() == stop, "Parameter ZIP central count mismatch")
    arrays, expanded = {}, 0
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        require(
            len(entries) == len(descriptors)
            and {e.filename for e in entries} == {key + ".npy" for key in descriptors},
            "Exact unique parameter NPY roster required",
        )
        for entry in entries:
            require(
                entry.compress_type == zipfile.ZIP_STORED
                and not entry.flag_bits & 1
                and not entry.is_dir(),
                "Original uncompressed parameter numeric archive",
            )
            expanded += entry.file_size
            require(expanded <= 64 * 2**20, "Original parameter expanded archive bound")
            key = entry.filename[:-4]
            with archive.open(entry) as stream:
                magic = stream.read(8)
                require(
                    magic[:6] == b"\x93NUMPY"
                    and magic[6:] in (b"\x01\x00", b"\x02\x00", b"\x03\x00"),
                    "Parameter NPY magic",
                )
                width = 2 if magic[6] == 1 else 4
                raw_length = stream.read(width)
                require(len(raw_length) == width, "Truncated parameter NPY header length")
                size = int.from_bytes(raw_length, "little")
                require(0 < size <= 16384, "Original parameter NPY header bound")
                raw_header = stream.read(size)
                require(len(raw_header) == size, "Truncated parameter NPY header")
                header = ast.literal_eval(raw_header.decode("utf8" if magic[6] == 3 else "latin1"))
                require(
                    type(header) is dict and set(header) == {"descr", "shape", "fortran_order"},
                    "Parameter NPY header schema",
                )
                dtype, shape, order = header["descr"], header["shape"], header["fortran_order"]
                require(
                    type(dtype) is str
                    and re.fullmatch(r"[<>|][biuf][1248]", dtype)
                    and (dtype[1], int(dtype[2:]))
                    in {
                        ("b", 1),
                        *((k, n) for k in "iu" for n in (1, 2, 4, 8)),
                        ("f", 2),
                        ("f", 4),
                        ("f", 8),
                    }
                    and type(shape) is tuple
                    and len(shape) <= 8
                    and all(type(n) is int and 0 <= n <= 8 * 2**20 for n in shape)
                    and type(order) is bool,
                    "Plain bounded parameter numeric metadata",
                )
                extent = math.prod(shape) * int(dtype[2:])
                require(
                    math.prod(shape) <= 8 * 2**20 and 8 + width + size + extent == entry.file_size,
                    "Parameter NPY extent mismatch",
                )
                desc = descriptors[key]
                require(
                    desc["dtype"] == dtype
                    and desc["shape"] == list(shape)
                    and type(desc["fortran"]) is bool
                    and desc["fortran"] is order,
                    "Parameter graph/NPY metadata mismatch",
                )
                digest, count = hashlib.sha256(), 0
                while block := stream.read(2**20):
                    digest.update(block)
                    count += len(block)
                require(count == extent, "Truncated parameter numeric payload")
                arrays[key] = dict(dtype=dtype, shape=list(shape), sha256=digest.hexdigest())
    fingerprint = hashlib.sha256(
        json.dumps(
            dict(tree=tree, arrays=arrays), sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()
    require(fingerprint == manifest["fingerprint"], "Parameter graph/array fingerprint changed")
    return dict(
        manifest=reference,
        arrays=len(arrays),
        numeric_bytes=sum(
            math.prod(row["shape"]) * int(row["dtype"][2:]) for row in arrays.values()
        ),
        bytes_authenticated=True,
        graph_reconstructed=False,
        owner_admission=False,
    )


def _parameter_load_prefix(reader, root, plan, outcome):
    """Retain a returned load prefix independently of later public validation failure."""
    directory = root / "parameters"
    present = [name for name in ("acquisition.json", "failure.json") if (directory / name).exists()]
    summary = dict(
        status="not_recorded",
        journal_files=present,
        operations=[],
        actual_world_ready_returned=False,
        completed_history_returned=False,
        final_live_parameters=None,
        acquisition_returned=False,
        usable_owner=False,
        init_or_sim_credit=False,
        scientific_credit=0,
        failure_present="failure.json" in present,
        evidence_complete=False,
    )
    if not present:
        if directory.exists():
            reader.issues.append(
                dict(
                    section="parameter_load_prefix",
                    type="MissingEvidence",
                    message="Parameter directory has no saved acquisition/failure journal",
                )
            )
            summary["status"] = "incomplete_evidence"
        return summary
    summary["status"] = "incomplete_evidence"
    records = {
        name: reader.check(
            "parameter_load_prefix." + name, lambda name=name: reader.read(directory / name)
        )
        for name in present
    }
    journal = (
        records.get("failure.json")
        if "failure.json" in present
        else records.get("acquisition.json")
    )
    if journal is None:
        return summary
    summary["primary"] = journal.get("primary")

    def declaration():
        roster = _parameter_roster(reader, plan)
        rows = journal["operations"]
        require(
            type(rows) is list
            and len(rows) <= len(roster)
            and all(type(row) is dict for row in rows)
            and [row.get("name") for row in rows] == roster[: len(rows)],
            "Original ordered unique parameter operation prefix required",
        )
        if "failure.json" in records:
            require(
                journal.get("source_or_evidence_incomplete") is True
                and type(journal.get("primary")) is dict,
                "Original parameter failure record",
            )
        if "acquisition.json" in records and records["acquisition.json"] is not None:
            acquired = records["acquisition.json"]
            require(
                acquired["packet"] == plan["parameter_inputs"]
                and acquired["construction_claim_opened"] is False
                and acquired["phase_or_persisted_owner_admission"] is False
                and len(acquired["operations"]) == len(roster)
                and type(acquired["actual_world_ready_identity"]) is int
                and type(acquired["actual_p_identity"]) is int,
                "Acquisition packet/source scope changed",
            )
            reader.bound(acquired["packet"])
            require(
                acquired["actual_world_ready_identity"]
                == acquired["operations"][-3].get("returned_identity")
                and acquired["actual_p_identity"]
                == acquired["operations"][-1].get("returned_identity"),
                "Acquisition returned object identities changed",
            )
            if "failure.json" in records:
                require(acquired["operations"] == rows, "Conflicting parameter journals")
        return roster, rows

    declared = reader.check("parameter_load_prefix.journal", declaration)
    if declared is None:
        return summary
    roster, rows = declared
    budget = dict(bytes=0, authenticated_bytes=0, archives=0)
    valid_prefix = True
    for index, row in enumerate(rows):
        item = dict(
            name=row["name"],
            status="incomplete_evidence",
            returned_observed=False,
            evidence_complete=False,
            archives=[],
            primary=row.get("primary"),
            capture_errors=row.get("errors"),
            journal_returned=row.get("returned"),
            returned_identity=row.get("returned_identity"),
        )
        summary["operations"].append(item)
        operation = directory / "evidence" / f"{index:02d}-{row['name']}"

        def operation_metadata(row=row, operation=operation, index=index):
            require(
                row.get("attempted") is True
                and type(row.get("returned")) is bool
                and type(row.get("evidence_complete")) is bool
                and type(row.get("errors")) is list,
                "Exact parameter operation status fields",
            )
            require(
                reader.read(operation / "attempt.json")
                == dict(name=row["name"], attempt=index + 1),
                "Parameter attempt ordinal changed",
            )
            require(
                reader.read(operation / "outcome.json") == row, "Parameter outcome/journal mismatch"
            )
            if row["returned"]:
                require(
                    type(row.get("returned_identity")) is int
                    and row["returned_identity"] > 0
                    and row.get("primary") is None,
                    "Actual parameter return identity/status",
                )
            else:
                require(
                    type(row.get("primary")) is dict
                    and reader.read(operation / "primary.json") == row["primary"],
                    "Original parameter API failure evidence",
                )
            return True

        observed = reader.check("parameter_load_prefix." + row["name"], operation_metadata)
        if observed:
            item["returned_observed"] = row["returned"]
            if row.get("primary") is not None:
                item["status"] = "failed"
            archive_ok = True
            refs = [("payload", row.get("payload"))]
            for key, prefix in (("graphs", "graph-"), ("captures", "capture-")):
                values = row.get(key)
                if type(values) is not dict or len(values) > 64:
                    archive_ok = False
                    reader.issues.append(
                        dict(
                            section="parameter_load_prefix." + row["name"],
                            type="InvalidEvidence",
                            message="Bounded archive map required",
                        )
                    )
                    continue
                for name, reference in values.items():
                    if type(name) is not str or re.fullmatch(r"[A-Za-z0-9_-]{1,80}", name) is None:
                        archive_ok = False
                        reader.issues.append(
                            dict(
                                section="parameter_load_prefix." + row["name"],
                                type="InvalidEvidence",
                                message="Canonical archive role required",
                            )
                        )
                        continue
                    refs.append((prefix + name, reference))
            for role, reference in refs:
                archived = reader.check(
                    "parameter_load_prefix." + row["name"] + "." + role,
                    lambda role=role, reference=reference, operation=operation: _parameter_archive(
                        reader, reference, operation / role, budget
                    ),
                )
                archive_ok &= archived is not None
                item["archives"].append(dict(role=role, verified=archived))
            item["evidence_complete"] = (
                row["evidence_complete"] and not row["errors"] and archive_ok
            )
            if row["returned"] and item["evidence_complete"]:
                item["status"] = "returned"
        if not valid_prefix:
            reader.issues.append(
                dict(
                    section="parameter_load_prefix." + row["name"],
                    type="InvalidOrder",
                    message="Operation follows a failed/incomplete predecessor",
                )
            )
            item["evidence_complete"] = False
            item["status"] = "incomplete_evidence"
        valid_prefix &= item["status"] == "returned"
    by_name = {row["name"]: row for row in summary["operations"]}
    summary.update(
        actual_world_ready_returned=by_name.get("actual-world-ready", {}).get("status")
        == "returned",
        completed_history_returned=by_name.get("final-history", {}).get("status") == "returned",
        final_live_parameters=by_name.get("final-live-parameters"),
        evidence_complete=all(row["evidence_complete"] for row in summary["operations"]),
        archive_count=budget["archives"],
        authenticated_payload_bytes=budget["authenticated_bytes"],
        reader_charged_file_bytes=budget["bytes"],
    )
    summary["acquisition_returned"] = (
        len(rows) == len(roster)
        and valid_prefix
        and not summary["failure_present"]
        and type(outcome) is dict
        and type(outcome.get("operations")) is list
        and any(row == dict(name="parameters", status="returned") for row in outcome["operations"])
    )
    summary["status"] = (
        "failed_after_recorded_prefix"
        if summary["failure_present"]
        else "returned_acquisition"
        if summary["acquisition_returned"]
        else "recorded_prefix"
    )
    if not summary["evidence_complete"]:
        summary["status"] = "incomplete_evidence"
    return summary


def _plan(reader, path, digest):
    require(
        type(digest) is str and len(digest) == 64 and all(c in "0123456789abcdef" for c in digest),
        "Explicit SHA-256 plan binding required",
    )
    plan = reader.read(path, digest)
    require(plan.get("kind") in LAUNCH_KINDS, "Unsupported launch schema")
    require(plan.get("held") is True and plan.get("automatic_retry") is False, "Held plan required")
    require(plan.get("flux_operator") in ("original", "disabled"), "Unknown flux mode")
    require(plan.get("endpoint", "seed") in ENDPOINTS, "Unknown endpoint")
    source = payload._regular(plan["source"])
    require(
        reader.bind(plan["source_snapshot"]) == source / "SNAPSHOT.json", "Snapshot association"
    )
    manifest = snapshot.verify(source, manifest_sha256=plan["source_snapshot"]["sha256"])
    files = {name: row["sha256"] for name, row in manifest["files"].items()}
    producers = plan["producers"]
    require(all(name in producers for name in (DEMO, LAUNCH, PARAMETER)), "Missing producer roster")
    require(
        all(files.get(name) == sha for name, sha in producers.items()), "Producer source mismatch"
    )
    demo, parameters = reader.bound(plan["demo_plan"]), reader.bound(plan["parameter_inputs"])
    import_policy = demo.get("source_plan", {}).get("optional_molecule_import_authority")
    if plan.get("endpoint", "seed") in WRAPPER_ENDPOINTS and import_policy is not None:
        require(
            type(import_policy) is dict
            and import_policy.get("protocol") == IMPORT_PROTOCOL
            and import_policy.get("modules")
            == {"molecule_wrappers": "cells.processes.betse_native_init_molecule_wrapper_authority"}
            and set(import_policy.get("source_pins", {})) == {"molecule_wrappers"}
            and set(import_policy.get("review_pins", {})) == {"molecule_wrappers"}
            and _hash_identity(import_policy["source_pins"]["molecule_wrappers"])
            and _hash_identity(import_policy["review_pins"]["molecule_wrappers"])
            and files.get(MOLECULE_WRAPPER) == import_policy["source_pins"]["molecule_wrappers"],
            "Declared original import observer source/review is not in the immutable closure",
        )
    else:
        import_policy = None
    plan = dict(plan, _molecule_import_policy=import_policy, _demo_kind=demo.get("kind"))
    if plan.get("endpoint") == "init_electrical":
        require(
            plan["kind"] in LAUNCH_KINDS[2:] and demo.get("kind") in DEMO_KINDS[2:],
            "Electrical endpoint requires its declared plan schemas",
        )
    if plan.get("endpoint") == "init_first_step":
        require(
            plan["kind"] in LAUNCH_KINDS[3:] and demo.get("kind") in DEMO_KINDS[3:],
            "First-step endpoint requires its declared plan schemas",
        )
    count = _iterations(plan)
    if plan.get("endpoint") == "init_short_history":
        require(
            plan["kind"] in LAUNCH_KINDS[4:] and demo.get("kind") in DEMO_KINDS[4:],
            "Short-history endpoint requires its declared plan schemas",
        )
    if plan.get("endpoint") == "init_terminal":
        require(
            plan["kind"] in LAUNCH_KINDS[5:] and demo.get("kind") in DEMO_KINDS[5:],
            "Natural terminal endpoint requires its declared plan schemas",
        )
        terminal_policy = demo.get("source_plan", {}).get("optional_init_terminal", {})
        require(
            type(terminal_policy.get("maximum_iterations")) is int
            and terminal_policy["maximum_iterations"] == 512
            and terminal_policy.get("init_iterations") is None
            and terminal_policy.get("full_original_calendar") is True
            and terminal_policy.get("normal_loop_context_and_caller_return") is True
            and terminal_policy.get("selected_stop") is False
            and terminal_policy.get("before_native_pickle") is True,
            "Natural terminal source declaration must retain the whole bounded calendar",
        )
    require(
        type(demo.get("init_iterations")) is type(count) and demo.get("init_iterations") == count,
        "Prepared iteration count changed",
    )
    require(
        demo["snapshot_sha256"] == plan["source_snapshot"]["sha256"]
        and Path(demo["parameter_packet"]) / "source" == source
        and Path(demo["parameter_packet"]) / "inputs.json" == Path(plan["parameter_inputs"]["path"])
        and demo["parameter_sha256"] == plan["parameter_inputs"]["sha256"]
        and demo["flux_operator"] == plan["flux_operator"]
        and demo.get("endpoint", "seed") == plan.get("endpoint", "seed")
        and parameters["source_snapshot"] == plan["source_snapshot"]
        and parameters["runtime"] == plan["runtime"],
        "Prepared source/input/endpoint association changed",
    )
    bundle = reader.bound(plan["input_bundle"])
    from validation.betse import native_seed_demo_input_profiles as profiles

    require(
        bundle.get("configuration_profile", "original")
        == parameters["program"].get("input_profile", "original"),
        "Saved configuration profile and parameter program differ",
    )
    selected = bundle["modes"][plan["flux_operator"]]
    require(
        selected["program"] == parameters["program"]["manifest"]
        and selected["config"] == parameters["program"]["root"],
        "Actual input mode association changed",
    )
    declared_program = reader.bound(selected["program"])
    require(
        declared_program.get("input_profile", "original")
        == bundle.get("configuration_profile", "original"),
        "Saved raw input program profile changed",
    )
    for row in plan["external_files"]:
        reader.bind(row)
    originals = {}
    for name, row in sorted(profiles.selected_inventory(bundle)["files"].items()):
        snapshot.relative_path(name)
        originals[name] = row["sha256"]
    require(bool(originals), "Empty original input inventory")
    expected = [
        dict(path=str(Path(selected["config"]) / name), sha256=sha)
        for name, sha in originals.items()
    ]
    require(plan["input_files"] == expected, "Selected input file roster changed")
    for row in expected:
        reader.bind(row)
    plan["_initial_rng_inputs"] = _initial_rng_declaration(
        reader, plan, demo, bundle, parameters, files
    )
    common = _common_declaration(reader, plan, demo, files)
    if common is not None:
        plan["_common_start"] = common
    return plan, files, originals


def _terminal_calendar(value, pins):
    """Read the complete, bounded saved calendar bits; no numerical array is built."""
    require(type(value) is dict, "Natural calendar cache object required")
    descriptor = value.get("descriptor_json")
    require(
        type(descriptor) is str
        and len(descriptor) <= 4096
        and hashlib.sha256(descriptor.encode()).hexdigest() == value.get("identity"),
        "Natural calendar descriptor identity required",
    )

    def pairs(rows):
        result = {}
        for key, item in rows:
            require(key not in result, "Duplicate natural calendar descriptor key")
            result[key] = item
        return result

    node = json.loads(descriptor, object_pairs_hook=pairs)
    require(type(node) is dict and node.get("kind") == "numeric_array", "Original calendar array")
    layout = node.get("source_layout")
    shape = layout.get("shape") if type(layout) is dict else None
    require(
        type(shape) is list
        and len(shape) == 1
        and type(shape[0]) is int
        and 1 <= shape[0] <= 512
        and layout.get("dtype") in ("<f8", ">f8"),
        "Complete original binary64 calendar in [1,512] required",
    )
    columns = value.get("columns")
    require(
        type(columns) is list
        and len(columns) == 1
        and type(columns[0]) is dict
        and columns[0].get("name") == node.get("column"),
        "One original calendar column required",
    )
    array = columns[0].get("values")
    require(
        type(array) is dict
        and array.get("__ndarray__") is True
        and array.get("dtype") == layout["dtype"]
        and array.get("shape") == shape,
        "Original calendar typed column required",
    )
    raw = array.get("raw_bytes_hex")
    size = 8 * shape[0]
    if type(raw) is str:
        require(len(raw) == 2 * size, "Original calendar byte extent required")
        encoded = raw
        raw = bytes.fromhex(encoded)
        require(raw.hex() == encoded, "Canonical calendar hex required")
    else:
        require(
            type(raw) is dict
            and set(raw) == {payload.TOKEN}
            and _hash_identity(raw[payload.TOKEN]),
            "Original calendar raw bytes or authenticated token required",
        )
        digest = raw[payload.TOKEN]
        matches = [
            Path(pin["path"])
            for pin in pins
            if pin["sha256"] == digest and Path(pin["path"]).name == digest + ".bin"
        ]
        require(bool(matches), "Original calendar sidecar pin required")
        with payload._regular(matches[0]).open("rb") as stream:
            raw = stream.read(size + 1)
        require(
            len(raw) == size and hashlib.sha256(raw).hexdigest() == digest,
            "Original calendar sidecar extent/identity changed",
        )
    require(hashlib.sha256(raw).hexdigest() == node.get("sha256"), "Calendar column digest changed")
    chunks = [raw[index : index + 8] for index in range(0, size, 8)]
    return dict(
        calendar_length=shape[0],
        calendar_time_bits=[
            (chunk[::-1] if layout["dtype"] == "<f8" else chunk).hex() for chunk in chunks
        ],
    )


def _captures(reader, directory, rows):
    require(type(rows) is list, "Capture list required")
    paths, summary = set(), []
    for row in rows:
        name = row["path"]
        snapshot.relative_path(name)
        require(name not in paths, "Duplicate capture path")
        paths.add(name)
        require(type(row["label"]) is str, "Capture label required")
        require(row["status"] in ("saved", "capture_failed"), "Unknown capture disposition")
        record = dict(row)
        if row["status"] == "saved":
            pins = evidence.files(directory / name, expected_sha256=row["sha256"])
            for pin in pins:
                reader.bind(pin)
            record["verified_files"] = len(pins)
            # Retain only the small linkage inventory in the report. Raw columns,
            # returns and work remain in the hash-bound, fully checked sidecars.
            value = evidence.read(directory / name, expected_sha256=row["sha256"], expand=False)
            if row["label"] in ("before_seed_random_states", "pre_seed_rng_witness"):
                # These fixed-size MT states are below the ordinary inline threshold.
                # The canonical wire is archive.snapshot, not a Cache descriptor.
                record["initial_rng_wire"] = value
            if row["label"] == "common_start_rng":
                record["common_start_wire"] = value
            if type(value) is dict:
                record["identity"] = value.get("identity")
                if row["label"].endswith(".record"):
                    record["references"] = {
                        key: value[key]
                        for key in (
                            "before",
                            "after",
                            "cache",
                            "helper_cache",
                            "rng_before",
                            "rng_after",
                            "stream_before",
                            "stream_after",
                            "before_MT",
                            "after_MT",
                            "stages",
                            "calendar",
                            "sampled",
                            "t",
                            "dt",
                            "index",
                            "complete",
                            "loop_returned",
                            "context_returned",
                            "selected_stop",
                            "molecule_record",
                            "tissue_record",
                            "tail_source_completed",
                            "timesteps_completed",
                            "completed_INIT_or_independent_case",
                            "request",
                            "parent",
                            "iterations",
                            "work",
                            "helpers",
                            "callbacks",
                            "source_completed",
                            "initial_diagnostics",
                        )
                        if key in value
                    }
                if row["label"] in (
                    "init_dynamics.tissue_record",
                    "init_dynamics.molecule_record",
                ):
                    record["references"] = {
                        key: value[key]
                        for key in (
                            "record_identity",
                            "completion_claim_identity",
                            "molecules_identity",
                            "core_identity",
                            "source_completed",
                            "work_views_are_non_additive",
                            "live_claim_or_frame_serialization",
                            "import_record_identity",
                        )
                        if key in value
                    }
            if row["label"] == "molecule_imports.record":
                require(type(value) is dict, "Original import record metadata required")
                record["references"] = value
            if row["label"] == "molecule_imports.raw_returns":
                require(type(value) is list and len(value) <= 4096, "Bounded import work required")
                record["sequence_length"] = len(value)
            if row["label"] in (
                "init_first_step.stream_before",
                "init_first_step.stream_after",
                "init_short_history.stream_before",
                "init_short_history.stream_after",
                "init_terminal.stream_before",
                "init_terminal.stream_after",
            ):
                record["stream_identities"] = value
            if row["label"] in ("init_short_history.linkage", "init_terminal.linkage"):
                require(type(value) is dict, "Short-history linkage object required")
                record["references"] = value
            if row["label"] in (
                "init_short_history.work",
                "init_short_history.helpers",
                "init_short_history.callbacks",
                "init_terminal.work",
                "init_terminal.helpers",
                "init_terminal.callbacks",
            ):
                require(
                    type(value) is list and len(value) <= 100000, "Bounded work sequence required"
                )
                record["sequence_length"] = len(value)
            if row["label"] == "init_terminal.calendar":
                record.update(_terminal_calendar(value, pins))
        else:
            require("error" in row, "Capture failure must retain its error")
        summary.append(record)
    return summary


def _required_captures(captures, labels):
    saved = [row["label"] for row in captures if row["status"] == "saved"]
    require(
        all(saved.count(label) == 1 for label in labels),
        "Missing or duplicate required raw capture",
    )


def _molecule_captures(value, captures, endpoint):
    """Validate optional saved molecular linkage, never reconstruct live authority."""
    fields = ("init_native_molecules", "init_molecule_network_completed")
    present = tuple(name in value for name in fields)
    require(present[0] == present[1], "Both optional molecular route flags required")
    selected = value.get(fields[0])
    completed = value.get(fields[1], False)
    require(
        (selected is None or type(selected) is bool) and type(completed) is bool,
        "Exact optional molecular selection/completion flags required",
    )
    labels = ("init_dynamics.molecule_record", "init_dynamics.molecule_raw_returns")
    rows = {row["label"]: row for row in captures if row["status"] == "saved"}
    completion = rows.get("init_dynamics.record", {}).get("references", {})
    if selected is not True:
        require(
            not completed
            and not any(row["label"] in labels for row in captures)
            and completion.get("molecule_record") is None,
            "Molecular evidence cannot be promoted without explicit enabled selection",
        )
    if present[0]:
        dynamics = endpoint in (
            "init_dynamics",
            "init_electrical",
            "init_first_step",
            "init_short_history",
            "init_terminal",
        )
        require(selected is None or dynamics, "Molecular route selected before its endpoint")
        if value["status"] == "completed" and dynamics:
            require(type(selected) is bool, "Completed dynamics requires its molecular selection")
            require(completed is selected, "Completed dynamics molecular flags disagree")
    if completed:
        require(
            selected is True
            and value.get("init_dynamics_completed") is True
            and type(value.get("completed_stage_trials")) is list
            and value["completed_stage_trials"].count("init_dynamics") == 1,
            "Completed molecular stage requires completed INIT dynamics evidence",
        )
        _required_captures(
            captures, (*labels, "init_dynamics.record", "init_dynamics.tissue_record")
        )
    molecular = rows.get(labels[0])
    if molecular is not None:
        identity = molecular.get("identity")
        require(
            type(identity) is str
            and len(identity) == 64
            and all(char in "0123456789abcdef" for char in identity),
            "Original molecular record hash identity required",
        )
        record = molecular.get("references", {})
        tissue = rows.get("init_dynamics.tissue_record", {}).get("references", {})
        for name, metadata in (("molecular", record), ("tissue", tissue)):
            require(
                metadata.get("source_completed") is True
                and metadata.get("work_views_are_non_additive") is True
                and metadata.get("live_claim_or_frame_serialization") is False,
                "Completed non-additive metadata without live serialization required: " + name,
            )
            for key in ("record_identity", "completion_claim_identity"):
                require(
                    type(metadata.get(key)) is int and metadata[key] > 0,
                    "Exact saved object identity required: " + name + "." + key,
                )
        for key in ("molecules_identity", "core_identity"):
            require(
                type(record.get(key)) is int and record[key] > 0,
                "Exact original molecular object identity required: " + key,
            )
        require(
            record["completion_claim_identity"] == tissue["completion_claim_identity"],
            "Molecular and tissue completion claims differ",
        )
        require(
            type(completion.get("molecule_record")) is int
            and completion["molecule_record"] == record["record_identity"]
            and type(completion.get("tissue_record")) is int
            and completion["tissue_record"] == tissue["record_identity"]
            and completion.get("tail_source_completed") is True
            and type(completion.get("timesteps_completed")) is int
            and completion["timesteps_completed"] == 0
            and completion.get("completed_INIT_or_independent_case") is False,
            "Completion trial molecular/tissue linkage or execution scope changed",
        )
    return dict(
        selected=selected,
        completed=completed,
        identity=(molecular.get("identity") if completed else None),
    )


def _molecule_import_captures(value, captures, endpoint, policy):
    """A saved import record proves recorded linkage, never live wrapper issuance."""
    protocol = value.get("molecule_import_protocol")
    completed = value.get("molecule_import_completed", False)
    require(type(completed) is bool, "Exact import completion flag required")
    declared = policy is not None
    if declared:
        require(protocol == IMPORT_PROTOCOL, "Required import protocol missing or changed")
        if value["status"] == "completed":
            require(completed, "Completed endpoint lacks its required import observation")
    elif protocol is not None:
        raise ValueError("Import observation is not bound by the prepared source declaration")
    if value.get("init_molecule_network_completed", False) is True:
        require(
            completed and declared, "Enabled molecular completion lacks required import evidence"
        )
    labels = ("molecule_imports.record", "molecule_imports.raw_returns")
    rows = {row["label"]: row for row in captures if row["status"] == "saved"}
    record = rows.get(labels[0], {}).get("references", {})
    if completed:
        require(declared and endpoint in WRAPPER_ENDPOINTS, "Import work exceeds declared endpoint")
        _required_captures(captures, labels)
        require(
            record.get("protocol") == IMPORT_PROTOCOL
            and record.get("law") == "fresh_original_molecule_channel_imported_beartype_factory@1"
            and record.get("source_completed") is True
            and record.get("published") is True
            and record.get("active") is False
            and record.get("hooks_restored") is True
            and record.get("monitor_restored") is True
            and record.get("work_views_are_non_additive") is True
            and record.get("live_claim_or_frame_serialization") is False
            and record.get("producer_sha256") == policy["source_pins"]["molecule_wrappers"],
            "Original import publication/source/cleanup metadata is incomplete",
        )
        for name in ("context_identity", "record_identity", "factories"):
            require(type(record.get(name)) is int and record[name] > 0, "Exact import " + name)
        require(
            record["factories"] <= 512
            and type(record.get("generated")) is int
            and 0 <= record["generated"] <= record["factories"]
            and type(record.get("raw_returns")) is int
            and record["raw_returns"] == rows[labels[1]].get("sequence_length")
            and type(record.get("source_errors")) is int
            and record["source_errors"] == 0
            and type(value.get("molecule_import_record_identity")) is int
            and value["molecule_import_record_identity"] == record["record_identity"]
            and value.get("molecule_import_operations")
            == [dict(name="enter", status="returned"), dict(name="exit", status="returned")],
            "Import record/work/operation linkage changed",
        )
        molecular = rows.get("init_dynamics.molecule_record")
        if molecular is not None:
            require(
                type(molecular.get("references", {}).get("import_record_identity")) is int
                and molecular["references"]["import_record_identity"] == record["record_identity"],
                "Molecular completion does not retain the original closed import record",
            )
    return dict(declared=declared, completed=completed, record=record if completed else None)


def _first_step_captures(captures):
    """Check saved first-iteration linkage without decoding or advancing model state."""
    rows = {row["label"]: row for row in captures if row["status"] == "saved"}
    record = rows["init_first_step.record"].get("references", {})
    require(
        record.get("complete") is True
        and type(record.get("index")) is int
        and record["index"] == 0
        and type(record.get("loop_returned")) is bool
        and type(record.get("selected_stop")) is bool
        and record["loop_returned"] != record["selected_stop"],
        "Exactly one completed original INIT iteration required",
    )
    for key, label in (
        ("before", "before"),
        ("after", "after"),
        ("calendar", "calendar"),
        ("sampled", "sampled"),
        ("t", "source_time_label"),
        ("dt", "configured_dt"),
    ):
        identity = record.get(key)
        require(
            type(identity) is str
            and len(identity) == 64
            and all(char in "0123456789abcdef" for char in identity)
            and rows["init_first_step." + label].get("identity") == identity,
            "First-step original snapshot linkage changed: " + label,
        )
    for key, label in (("rng_before", "stream_before"), ("rng_after", "stream_after")):
        identities = record.get(key)
        require(
            type(identities) is list
            and len(identities) == 2
            and all(
                type(value) is str
                and len(value) == 64
                and all(char in "0123456789abcdef" for char in value)
                for value in identities
            )
            and rows["init_first_step." + label].get("stream_identities") == identities,
            "First-step original RNG capture changed: " + label,
        )
    electrical = rows["init_electrical.record"].get("references", {})
    require(
        electrical.get("rng_after") == record["rng_before"],
        "First-step RNG handoff differs from retained electrical trial",
    )


def _short_history_captures(captures, count, mode, *, natural=False):
    """Check a recorded contiguous history without executing its numerical model."""
    prefix = "init_terminal" if natural else "init_short_history"
    rows = {row["label"]: row for row in captures if row["status"] == "saved"}
    record_row = rows[prefix + ".record"]
    record = record_row.get("references", {})
    linkage = rows[prefix + ".linkage"].get("references", {})
    require(
        [row["label"] for row in captures if row["label"].startswith(prefix + ".iteration.")]
        == [f"{prefix}.iteration.{i:04d}.after" for i in range(count)],
        "Exact ordered iteration snapshot roster required",
    )
    require(
        record.get("source_completed") is True
        and record.get("loop_returned") is natural
        and (not natural or record.get("context_returned") is True)
        and record.get("selected_stop") is (not natural),
        "Completed bounded original-loop selection required",
    )
    require(
        type(linkage.get("configured_iterations" if natural else "requested_iterations")) is int
        and linkage["configured_iterations" if natural else "requested_iterations"] == count
        and linkage.get("operator_mode")
        == (
            "original_value_and_flux" if mode == "original" else "original_value_only_flux_omitted"
        ),
        "Short-history count or retained operator mode changed",
    )
    if natural:
        calendar = rows[prefix + ".calendar"]
        require(
            type(linkage.get("maximum_iterations")) is int
            and linkage["maximum_iterations"] == 512
            and 1 <= count <= 512
            and all(
                linkage.get(key) is True
                for key in (
                    "source_completed",
                    "loop_returned",
                    "context_returned",
                    "full_original_calendar",
                    "before_native_pickle",
                )
            )
            and linkage.get("selected_stop") is False
            and calendar.get("calendar_length") == count,
            "Complete natural calendar and normal loop/context/caller return required",
        )
    for key, actual in (
        ("trial_identity", record_row.get("identity")),
        ("request_identity", record.get("request")),
        ("parent_identity", record.get("parent")),
    ):
        require(
            _hash_identity(actual) and linkage.get(key) == actual,
            "Short-history request/parent/trial linkage changed: " + key,
        )
    for key, label in (
        ("before", "before"),
        ("after", "after"),
        ("calendar", "calendar"),
        ("sampled", "sampled"),
        ("dt", "configured_dt"),
    ):
        identity = record.get(key)
        require(
            _hash_identity(identity) and rows[prefix + "." + label].get("identity") == identity,
            "Short-history original snapshot linkage changed: " + label,
        )
    for key, label in (("rng_before", "stream_before"), ("rng_after", "stream_after")):
        identities = linkage.get(key)
        require(
            type(identities) is list
            and len(identities) == 2
            and all(_hash_identity(identity) for identity in identities)
            and record.get(key) == identities
            and rows[prefix + "." + label].get("stream_identities") == identities,
            "Short-history original RNG capture changed: " + label,
        )
    require(
        rows["init_electrical.record"].get("references", {}).get("rng_after")
        == linkage["rng_before"],
        "Short-history RNG handoff differs from retained electrical trial",
    )
    for key in ("work", "helpers", "callbacks"):
        require(type(record.get(key)) is int and record[key] >= 0, "Exact work count required")
        require(
            rows[prefix + "." + key].get("sequence_length") == record[key],
            "Original captured work/helper/callback count changed: " + key,
        )
    native_rows, linked_rows = record.get("iterations"), linkage.get("iterations")
    require(
        type(native_rows) is list
        and type(linked_rows) is list
        and len(native_rows) == len(linked_rows) == count,
        "Exactly the requested contiguous history rows required",
    )
    work_end = callbacks_end = 0
    for ordinal, (native, linked) in enumerate(zip(native_rows, linked_rows, strict=True)):
        require(
            type(native) is list and len(native) == 8 and type(linked) is dict,
            "Original eight-field iteration record required",
        )
        require(
            type(native[0]) is int
            and type(linked.get("ordinal")) is int
            and native[0] == linked["ordinal"] == ordinal,
            "Contiguous original iteration ordinals required",
        )
        bits = native[1]
        require(
            type(bits) is str
            and len(bits) == 16
            and all(char in "0123456789abcdef" for char in bits)
            and linked.get("source_time_bits") == bits
            and type(linked.get("sampled")) is bool
            and type(native[2]) is bool
            and native[2] is linked["sampled"],
            "Original time-label bits and sample flag required",
        )
        require(
            _hash_identity(native[3])
            and linked.get("after_identity") == native[3]
            and rows[f"{prefix}.iteration.{ordinal:04d}.after"].get("identity") == native[3],
            "Actual per-iteration state snapshot changed",
        )
        require(
            type(native[4]) is int
            and type(native[5]) is int
            and type(linked.get("work_end")) is int
            and type(linked.get("callbacks_end")) is int
            and work_end <= native[4] == linked["work_end"] <= record["work"]
            and callbacks_end <= native[5] == linked["callbacks_end"] <= record["callbacks"],
            "Ordered non-additive iteration work/callback boundaries required",
        )
        require(
            type(native[6]) is int
            and native[6] > 0
            and type(linked.get("molecular_record_identity")) is int
            and linked["molecular_record_identity"] == native[6],
            "Retained molecular iteration record required",
        )
        work_end, callbacks_end = native[4], native[5]
    if natural:
        require(
            [row[1] for row in native_rows] == rows[prefix + ".calendar"]["calendar_time_bits"],
            "Natural iteration labels differ from the entire original calendar",
        )
    require(native_rows[-1][3] == record["after"], "Final iteration state differs from final trial")
    return dict(
        **(
            {
                "configured_iterations": count,
                "maximum_iterations": 512,
                "loop_returned": True,
                "context_returned": True,
                "selected_stop": False,
            }
            if natural
            else {"requested_iterations": count}
        ),
        recorded_iterations=count,
        original_time_bits=[row[1] for row in native_rows],
        initial_diagnostics=record.get("initial_diagnostics"),
        iteration_diagnostics=[row[7] for row in native_rows],
        numerical_or_conservation_qualification=False,
    )


def _geometry_captures(captures):
    names = ("phase", "lattice", "image", "mesh", "lifecycle", "geometry")
    _required_captures(
        captures,
        [name + ".record" for name in names]
        + [
            "completed_geometry.cache",
            "diagnostics",
            *(f"phase.stage_trials.{index}.cache.cache" for index in range(4)),
        ],
    )
    identities = {row.get("identity") for row in captures if type(row.get("identity")) is str}
    records = {
        row["label"]: row.get("references", {})
        for row in captures
        if row["label"].endswith(".record")
    }
    for name in names[1:]:
        record = records[name + ".record"]
        for field in ("before", "cache"):
            require(
                type(record.get(field)) is str and record[field] in identities,
                "Missing geometry raw cache: " + name + "." + field,
            )
        for field in (
            "helper_cache",
            "rng_before",
            "rng_after",
            "stream_before",
            "stream_after",
            "before_MT",
            "after_MT",
        ):
            if record.get(field) is not None:
                require(record[field] in identities, "Missing geometry RNG/helper capture")
    stages = records["geometry.record"]["stages"]
    require([name for name, _ in stages] == list(GEOMETRY_STAGES), "Geometry stage roster changed")
    require(
        all(identity in identities for _, identity in stages), "Missing intermediate geometry cache"
    )


def _runtime(reader, root, plan, files):
    source, roots = Path(plan["source"]), [Path(p) for p in plan["runtime_roots"]]
    external = {row["path"]: row["sha256"] for row in plan["external_files"]}
    inventories, producers = [], {}
    for name in ("runtime-before.json", "runtime-after.json"):
        value = reader.read(root / name)
        require(value["measured_cpu_affinity"] == [plan["policy"]["cpu"]], "Recorded CPU mismatch")
        require(
            value["executable"] == plan["runtime"]["executable"], "Recorded executable mismatch"
        )
        reader.bind(value["executable"])
        for module, row in value["loaded_files"].items():
            path = reader.bind(row)
            if (
                module == "cells"
                or module.startswith(("cells.", "validation."))
                or path.is_relative_to(source)
            ):
                require(path.is_relative_to(source), "Mutable project producer: " + module)
                relative = str(path.relative_to(source))
                require(files.get(relative) == row["sha256"], "Unbound snapshot producer")
                producers[relative] = row["sha256"]
            else:
                require(
                    any(path.is_relative_to(folder) for folder in roots)
                    or external.get(str(path)) == row["sha256"],
                    "Undeclared loaded origin: " + module,
                )
        for row in value["mapped_files"]:
            reader.bind(row)
        inventories.append(value)
    require(
        all(name in producers for name in (LAUNCH, PARAMETER)), "Actual recorder producers missing"
    )
    if plan.get("_initial_rng_inputs") is not None:
        require(
            all(name in producers for name in (DEMO, INITIAL_RNG)),
            "Actual initial RNG producers missing",
        )
    require(
        all(
            inventories[1]["loaded_files"].get(k) == v
            for k, v in inventories[0]["loaded_files"].items()
        ),
        "Loaded producer removed or changed during execution",
    )
    after = reader.read(root / "source-after.json")
    require(
        after["source_snapshot"] == plan["source_snapshot"]
        and after["producers"] == plan["producers"],
        "Final source binding changed",
    )
    return dict(
        before_modules=len(inventories[0]["loaded_files"]),
        after_modules=len(inventories[1]["loaded_files"]),
        snapshot_producers=producers,
    )


def _resources(reader, output, plan_path, plan, digest, terminal):
    process_dir = output / "process"
    result = reader.read(
        process_dir / ("failure.json" if (process_dir / "failure.json").exists() else "result.json")
    )
    inputs = reader.read(output / "process/process-inputs.json")
    command = inputs["command"]
    for flag, expected in (
        ("--worker", str(Path(plan_path).absolute())),
        ("--plan-sha256", digest),
        ("--output", str(output / "worker")),
    ):
        require(
            command.count(flag) == 1 and command[command.index(flag) + 1] == expected,
            "Process association changed",
        )
    require(inputs["cwd"] == plan["source"], "Process source directory changed")
    limits, policy = result["limits"], plan["policy"]
    require(
        inputs["limits"] == limits
        and limits["max_wall_seconds"] == policy["wall_seconds"]
        and limits["max_process_tree_rss_bytes"] == policy["max_rss_bytes"]
        and limits["min_available_host_memory_bytes"] == policy["reserve_bytes"]
        and result["process_tree_memory_metric"] == "rss",
        "Resource policy association changed",
    )
    within = (
        result["elapsed_seconds"] <= policy["wall_seconds"]
        and result["sampled_peak_process_tree_rss_bytes"] <= policy["max_rss_bytes"]
        and result["minimum_available_host_memory_bytes"] >= policy["reserve_bytes"]
        and result["samples"] > 0
    )
    if terminal is not None:
        require(
            result == terminal["process"]
            and result["status"] == "completed"
            and result["returncode"] == 0
            and within,
            "Completed worker/resource evidence disagrees",
        )
    return dict(
        result=result, sampled_limits_met=within, high_water_is_distinct_from_sampled_peak=True
    )


def _outcome(reader, root, plan, value):
    require(value.get("kind") in DEMO_KINDS, "Unsupported demo outcome schema")
    if plan.get("_initial_rng_inputs") is not None or value.get("kind") == DEMO_KINDS[6]:
        require(
            value.get("kind") == plan.get("_demo_kind") == DEMO_KINDS[6],
            "Initial RNG outcome schema differs from its prepared producer",
        )
    require(
        value["flux_operator"] == plan["flux_operator"]
        and value.get("endpoint", "seed") == plan.get("endpoint", "seed"),
        "Outcome mode/endpoint changed",
    )
    require(value["status"] in ("completed", "failed"), "Unknown demo disposition")
    endpoint = plan.get("endpoint", "seed")
    first_step = endpoint == "init_first_step"
    short_history = endpoint == "init_short_history"
    terminal = endpoint == "init_terminal"
    count = _iterations(plan)
    completed = value["status"] == "completed"
    if first_step:
        require(value["kind"] in DEMO_KINDS[3:], "First-step endpoint requires its declared schema")
    if short_history:
        require(
            value["kind"] in DEMO_KINDS[4:], "Short-history endpoint requires its declared schema"
        )
    if terminal:
        require(value["kind"] in DEMO_KINDS[5:], "Natural terminal requires its declared schema")
        if completed:
            require(
                type(value.get("init_time_steps_completed")) is int
                and 1 <= value["init_time_steps_completed"] <= 512,
                "Complete natural calendar count in [1,512] required",
            )
    require(
        type(value.get("init_iterations")) is type(count) and value.get("init_iterations") == count,
        "Outcome requested iteration count changed",
    )
    require(
        value["original_flux_defect_repaired"] is False
        and type(value["scientific_or_physical_credit"]) is int
        and value["scientific_or_physical_credit"] == 0
        and type(value["init_time_steps_completed"]) is int
        and value["init_time_steps_completed"]
        == (
            value["init_time_steps_completed"]
            if terminal and completed
            else count
            if short_history and completed
            else int(first_step and completed)
        )
        and value.get("init_first_step_completed", False) is (first_step and completed)
        and value.get("init_short_history_completed", False) is (short_history and completed)
        and value.get("init_terminal_completed", False) is (terminal and completed)
        and value["complete_seed_runner_or_INIT_SIM_restart_claim"] is False
        and value["stage_work_is_non_additive"] is True,
        "Outcome exceeds the supported demonstration claim",
    )
    captures = _captures(reader, root, value["captures"])
    common_start = _common_captures(reader, root, plan, value, captures)
    initial_rng = _initial_rng_captures(reader, root, plan, value, captures)
    molecules = _molecule_captures(value, captures, endpoint)
    imports = _molecule_import_captures(
        value, captures, endpoint, plan.get("_molecule_import_policy")
    )
    if terminal and completed:
        require(
            molecules["selected"] is True
            and molecules["completed"] is True
            and imports["declared"] is True
            and imports["completed"] is True,
            "Natural terminal requires its genuine enabled molecular/import ancestry",
        )
    history = None
    natural_terminal = None
    if value["status"] == "completed":
        stages = ["geometry", "poisson", "core", "profiles", "junctions"]
        if endpoint != "seed":
            stages.append("init_setup")
        if endpoint in (
            "init_prelude",
            "init_dynamics",
            "init_electrical",
            "init_first_step",
            "init_short_history",
            "init_terminal",
        ):
            stages.append("init_prelude")
        if endpoint in (
            "init_dynamics",
            "init_electrical",
            "init_first_step",
            "init_short_history",
            "init_terminal",
        ):
            stages.append("init_dynamics")
        if endpoint in (
            "init_electrical",
            "init_first_step",
            "init_short_history",
            "init_terminal",
        ):
            require(
                value["kind"] in DEMO_KINDS[2:], "Electrical endpoint requires its declared schema"
            )
            stages.extend(("init_storage", "init_electrical"))
        if first_step:
            stages.append("init_first_step")
        if short_history:
            stages.append("init_short_history")
        if terminal:
            stages.append("init_terminal")
        require(
            value["methods_completed"] is True
            and value["primary"] is None
            and value["secondary"] == [],
            "Completed outcome retains a failure",
        )
        require(value["completed_stage_trials"] == stages, "Incomplete or reordered stage trials")
        require(
            value["init_setup_completed"] is (endpoint != "seed")
            and value.get("init_prelude_completed", False)
            is (
                endpoint
                in (
                    "init_prelude",
                    "init_dynamics",
                    "init_electrical",
                    "init_first_step",
                    "init_short_history",
                    "init_terminal",
                )
            )
            and value.get("init_dynamics_completed", False)
            is (
                endpoint
                in (
                    "init_dynamics",
                    "init_electrical",
                    "init_first_step",
                    "init_short_history",
                    "init_terminal",
                )
            )
            and value.get("init_storage_completed", False)
            is (
                endpoint
                in ("init_electrical", "init_first_step", "init_short_history", "init_terminal")
            )
            and value.get("init_electrical_completed", False)
            is (
                endpoint
                in ("init_electrical", "init_first_step", "init_short_history", "init_terminal")
            ),
            "Endpoint completion flags changed",
        )
        required = ["callback", "parameters", "geometry"]
        if plan.get("_initial_rng_inputs") is not None:
            required = [
                "callback",
                "constructor_preflight",
                "parameters",
                "initial_rng",
                "geometry",
            ]
            if plan.get("_common_start") is not None:
                required.insert(required.index("initial_rng"), "common_start_rng")
        elif any(row["name"] == "constructor_preflight" for row in value["operations"]):
            # Older @7 producers already emitted this exact metadata operation.
            # Optional once in its original position; no other operation is ignored.
            required.insert(1, "constructor_preflight")
        for name in stages[1:]:
            required.extend((name + "_request", name))
        observed = []
        file_entries = {
            "profile_image_file": "profiles_request",
            "init_dynamics_file": "init_dynamics_request",
        }
        for row in value["operations"]:
            target = file_entries.get(row["name"])
            if target is None:
                observed.append(row["name"])
            else:
                require(
                    len(observed) < len(required) and required[len(observed)] == target,
                    "File declaration outside its next public request",
                )
        require(
            observed == required
            and all(row["status"] == "returned" for row in value["operations"]),
            "Incomplete or reordered public operations",
        )
        require(
            all(row["status"] == "saved" for row in captures), "Completed outcome has capture gaps"
        )
        labels = [name + ".record" for name in stages[1:]] + [
            "poisson.cache",
            "core.cache",
            "profiles.after",
            "junctions.cache",
        ]
        if endpoint != "seed":
            labels.extend(("init_setup.before", "init_setup.after"))
        if endpoint in (
            "init_prelude",
            "init_dynamics",
            "init_electrical",
            "init_first_step",
            "init_short_history",
            "init_terminal",
        ):
            labels.extend(("init_prelude.before", "init_prelude.after", "init_prelude.raw_returns"))
        if endpoint in (
            "init_dynamics",
            "init_electrical",
            "init_first_step",
            "init_short_history",
            "init_terminal",
        ):
            labels.extend(
                "init_dynamics." + name
                for name in (
                    "before",
                    "after",
                    "stream_before",
                    "stream_after",
                    "rng_calls",
                    "tissue_record",
                    "raw_returns",
                )
            )
        if endpoint in (
            "init_electrical",
            "init_first_step",
            "init_short_history",
            "init_terminal",
        ):
            for name, streams in (
                ("init_storage", ("stream_before", "stream_after")),
                ("init_electrical", ("rng_before", "rng_after")),
            ):
                labels.extend(
                    name + "." + field
                    for field in ("before", "after", *streams, "stores", "raw_returns")
                )
        if first_step:
            labels.extend(
                "init_first_step." + field
                for field in (
                    "before",
                    "after",
                    "calendar",
                    "sampled",
                    "source_time_label",
                    "configured_dt",
                    "stream_before",
                    "stream_after",
                    "stores",
                    "raw_returns",
                )
            )
        if short_history or terminal:
            prefix = "init_terminal" if terminal else "init_short_history"
            count = value["init_time_steps_completed"] if terminal else count
            labels.extend(
                prefix + "." + field
                for field in (
                    "linkage",
                    "before",
                    "after",
                    "calendar",
                    "sampled",
                    "configured_dt",
                    "stream_before",
                    "stream_after",
                    "work",
                    "helpers",
                    "callbacks",
                    "raw_returns",
                    "initial_diagnostics",
                )
            )
            labels.extend(f"{prefix}.iteration.{i:04d}.after" for i in range(count))
        _required_captures(captures, labels)
        if first_step:
            _first_step_captures(captures)
        if short_history:
            history = _short_history_captures(captures, count, plan["flux_operator"])
        if terminal:
            natural_terminal = _short_history_captures(
                captures, count, plan["flux_operator"], natural=True
            )
    return dict(
        outcome=value,
        captures=captures,
        molecule_network=molecules,
        molecule_imports=imports,
        short_history=history,
        **({"initial_rng": initial_rng} if plan.get("_initial_rng_inputs") is not None else {}),
        **({"common_start": common_start} if plan.get("_common_start") is not None else {}),
        **({"natural_terminal": natural_terminal} if terminal else {}),
    )


def _numpy_origin(reader, root):
    value = reader.read(root / "numpy-copy-origin.json")
    require(
        value.get("kind") == NUMPY_ORIGIN_KIND and type(value.get("completed")) is bool,
        "Original NumPy construction evidence schema changed",
    )
    files = value.get("source_files")
    require(type(files) is dict, "Original NumPy construction source roster required")
    for path, digest in files.items():
        require(type(path) is str and Path(path).is_absolute(), "Absolute original source path")
        reader.bind(dict(path=path, sha256=digest))
    if value["completed"]:
        require(
            bool(files)
            and value.get("hooks_restored") is True
            and value.get("source_error") is None
            and value.get("capture_errors") == []
            and value.get("cleanup_errors") == [],
            "Completed NumPy construction evidence retains an observation failure",
        )
    return value


def inspect_attempt(plan_path, *, plan_sha256, output=None):
    """One explicit read of saved terminal paths; never query or wait on a job."""
    reader = Reader()
    plan, files, originals = _plan(reader, Path(plan_path), plan_sha256)
    bundle = reader.bound(plan["input_bundle"])
    report = dict(
        kind=KIND,
        status="prepared_only",
        plan_sha256=plan_sha256,
        flux_operator=plan["flux_operator"],
        endpoint=plan.get("endpoint", "seed"),
        init_iterations_requested=plan.get("init_iterations"),
        source_files=files,
        original_input_files={
            name: row["sha256"] for name, row in bundle["source_inventory"]["files"].items()
        },
        selected_input_files=originals,
        configuration_profile=bundle.get("configuration_profile", "original"),
        configuration_changes=bundle.get("configuration_changes", []),
        policy=plan["policy"],
        original_flux_defect_repaired=False,
        numerical_comparison=False,
        scientific_credit=0,
        time_steps_qualified=0,
        init_iterations_completed=0,
        init_native_molecules=None,
        init_molecule_network_completed=False,
        restart_qualified=False,
        source_execution_complete=False,
        source_evidence_complete=False,
        evidence_scope=(
            "Endpoint and geometry captures plus declared source/input/runtime/resource/"
            "filesystem records and available parameter operation archives; "
            "no live failed-owner serialization claim"
        ),
    )
    if plan.get("_initial_rng_inputs") is not None:
        report.update(
            initial_rng_inputs=plan["_initial_rng_inputs"],
            common_starting_authority_established=False,
        )
    if output is not None:
        output = payload._regular(output)
        root = output / "worker"
        names = (
            "result.json",
            "failure.json",
            "worker/failure.json",
            "process/failure.json",
            "worker/demo/outcome.json",
        )
        present = {name for name in names if (output / name).exists()}
        report.update(output=str(output), observed_terminal_files=sorted(present))
        if not present:
            report["status"] = "no_terminal_observed"
        else:
            terminal = (
                reader.check("controller", lambda: reader.read(output / "result.json"))
                if "result.json" in present
                else None
            )
            failures = []
            failure_names = {name for name in present if name.endswith("failure.json")}
            for name in sorted(failure_names):
                failure = reader.check(name, lambda name=name: reader.read(output / name))
                if failure is not None:
                    failures.append(dict(path=name, failure=failure))
            report["failures"] = failures
            report["status"] = "failed" if failure_names else "incomplete_evidence"
            report["resources"] = reader.check(
                "resources",
                lambda: _resources(reader, output, plan_path, plan, plan_sha256, terminal),
            )
            report["runtime"] = reader.check("runtime", lambda: _runtime(reader, root, plan, files))
            if NUMPY_ORIGIN in plan["producers"]:
                report["numpy_copy_origin"] = reader.check(
                    "numpy_copy_origin", lambda: _numpy_origin(reader, root)
                )
            raw_outcome = reader.check(
                "outcome_read", lambda: reader.read(root / "demo/outcome.json")
            )
            prefix = _parameter_load_prefix(reader, root / "demo", plan, raw_outcome)
            report["parameter_load_prefix"] = prefix
            if prefix["failure_present"]:
                report["status"] = "failed"
                failures.append(
                    dict(
                        path="worker/demo/parameters/failure.json",
                        failure=dict(
                            primary=prefix.get("primary"),
                            evidence_complete=prefix["evidence_complete"],
                        ),
                    )
                )
            result = (
                reader.check("outcome", lambda: _outcome(reader, root / "demo", plan, raw_outcome))
                if raw_outcome is not None
                else None
            )
            report["demonstration"] = result
            if result is not None:
                report.update(
                    init_native_molecules=result["molecule_network"]["selected"],
                    init_molecule_network_completed=result["molecule_network"]["completed"],
                )
            if raw_outcome is not None and raw_outcome.get("status") == "failed":
                report["status"] = "failed"
                failures.append(dict(path="worker/demo/outcome.json", failure=raw_outcome))
            filesystem = reader.check("filesystem", lambda: reader.read(root / "filesystem.json"))
            if filesystem is not None:
                reader.check(
                    "filesystem_failures",
                    lambda: require(
                        filesystem["failures"] == [] and filesystem["first_error"] is None,
                        "Recorded filesystem failure",
                    ),
                )
            geometry_path = root / "demo/geometry/outcome.json"
            if geometry_path.exists():

                def geometry():
                    value = reader.read(geometry_path)
                    captures = _captures(reader, geometry_path.parent, value["captures"])
                    if value["status"] == "source_completed":
                        require(
                            value["source_completed"] is True
                            and value["source_error"] is None
                            and value["metadata_error"] is None
                            and value["capture_errors"] == []
                            and all(row["status"] == "saved" for row in captures),
                            "Completed geometry retains an execution/capture failure",
                        )
                        _geometry_captures(captures)
                    return dict(status=value["status"], diagnostics=value["diagnostics"])

                report["geometry"] = reader.check("geometry", geometry)
            elif result is not None and result["outcome"]["status"] == "completed":
                reader.issues.append(
                    dict(
                        section="geometry",
                        type="MissingEvidence",
                        message="Completed demonstration lacks geometry outcome",
                    )
                )
            if terminal is not None:

                def completed():
                    require(
                        terminal["kind"] == plan["kind"]
                        and terminal["status"] == "source_completed_unqualified"
                        and terminal["plan_sha256"] == plan_sha256
                        and terminal["scientific_credit"] == 0,
                        "Controller completion binding",
                    )
                    require(
                        Path(terminal["worker"]["path"]) == root / "result.json",
                        "Worker result association",
                    )
                    worker = reader.bound(terminal["worker"])
                    require(
                        worker["kind"] == plan["kind"]
                        and worker["status"] == terminal["status"]
                        and worker["plan_sha256"] == plan_sha256
                        and worker["flux_operator"] == plan["flux_operator"]
                        and worker.get("endpoint", "seed") == report["endpoint"]
                        and type(worker.get("init_iterations")) is type(plan.get("init_iterations"))
                        and worker.get("init_iterations") == plan.get("init_iterations"),
                        "Worker completion binding",
                    )
                    require(
                        all(
                            worker.get(k) is True
                            for k in (
                                "public_entry_attempted",
                                "public_entry_returned",
                                "runtime_before_available",
                                "runtime_after_available",
                                "filesystem_audit_installed",
                            )
                        ),
                        "Incomplete worker observations",
                    )
                    if NUMPY_ORIGIN in plan["producers"]:
                        require(
                            worker.get("numpy_copy_origin_available") is True
                            and worker.get("numpy_copy_origin_completed") is True
                            and type(report.get("numpy_copy_origin")) is dict
                            and report["numpy_copy_origin"].get("completed") is True,
                            "Incomplete original NumPy construction proof",
                        )
                    require(
                        result is not None and result["outcome"]["status"] == "completed",
                        "Missing completed demonstration",
                    )
                    require(
                        (report.get("geometry") or {}).get("status") == "source_completed",
                        "Geometry did not complete",
                    )

                reader.check("completed_chain", completed)
                if not reader.issues and not failures:
                    report.update(
                        status="completed_unqualified",
                        source_execution_complete=True,
                        source_evidence_complete=True,
                        init_iterations_completed=result["outcome"]["init_time_steps_completed"],
                    )
    report["verification_issues"] = reader.issues
    report["observed_file_pins"] = [dict(path=k, sha256=v) for k, v in sorted(reader.pins.items())]
    return report


def compare_modes(original, disabled):
    """Compare two checked execution reports, never their numerical solutions."""
    require(original.get("kind") == disabled.get("kind") == KIND, "Saved report schemas required")
    require(
        original["flux_operator"] == "original" and disabled["flux_operator"] == "disabled",
        "Exact separate original/disabled reports required",
    )
    checks = {
        name: original[name] == disabled[name]
        for name in ("source_files", "original_input_files", "policy", "endpoint")
    }
    checks["init_iterations_requested"] = type(original.get("init_iterations_requested")) is type(
        disabled.get("init_iterations_requested")
    ) and original.get("init_iterations_requested") == disabled.get("init_iterations_requested")
    checks["configuration_profile"] = original.get(
        "configuration_profile", "original"
    ) == disabled.get("configuration_profile", "original")
    checks["selected_input_files"] = original.get(
        "selected_input_files", original["original_input_files"]
    ) == disabled.get("selected_input_files", disabled["original_input_files"])
    checks["configuration_changes"] = original.get("configuration_changes", []) == disabled.get(
        "configuration_changes", []
    )
    checks["init_native_molecules"] = original.get("init_native_molecules") is disabled.get(
        "init_native_molecules"
    )
    if "initial_rng_inputs" in original or "initial_rng_inputs" in disabled:
        checks["initial_rng_inputs"] = (
            original.get("initial_rng_inputs") is not None
            and original.get("initial_rng_inputs") == disabled.get("initial_rng_inputs")
            and original.get("common_starting_authority_established") is False
            and disabled.get("common_starting_authority_established") is False
        )
    complete = all(
        value.get("source_execution_complete") is True
        and value.get("source_evidence_complete") is True
        and value["status"] == "completed_unqualified"
        and value["verification_issues"] == []
        for value in (original, disabled)
    )
    return dict(
        kind=KIND,
        original=original,
        disabled=disabled,
        matching=checks,
        paired_execution_complete=complete and all(checks.values()),
        numerical_equality_checked=False,
        physical_parity=False,
        restart_qualified=False,
        original_flux_defect_repaired=False,
        flux_note=(
            "Original mode retains the native inverse; disabled mode skips that inverse. "
            "Ordinary transport is unchanged."
        ),
        work_ledgers_additive=False,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--plan-sha256", required=True)
    parser.add_argument("--attempt", type=Path)
    parser.add_argument("--disabled-plan", type=Path)
    parser.add_argument("--disabled-plan-sha256")
    parser.add_argument("--disabled-attempt", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    value = inspect_attempt(args.plan, plan_sha256=args.plan_sha256, output=args.attempt)
    if args.disabled_plan is not None:
        require(args.disabled_plan_sha256 is not None, "Disabled plan digest required")
        value = compare_modes(
            value,
            inspect_attempt(
                args.disabled_plan,
                plan_sha256=args.disabled_plan_sha256,
                output=args.disabled_attempt,
            ),
        )
    else:
        require(
            args.disabled_plan_sha256 is None and args.disabled_attempt is None,
            "Disabled plan required",
        )
    if args.output is not None:
        snapshot.write_json(args.output, value)
    else:
        print(json.dumps(value, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
