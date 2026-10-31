"""Explicit independent-world shape groups and declared array/evidence budgets."""

import json
import re
from dataclasses import dataclass

from cells.processes import charged_surface_backend_arrays as arrays
from cells.processes import charged_surface_work as scalar

KIND = "held_charged_surface_backend@1"
SCALAR_MANIFEST_SHA256 = "1bfe67b8611b7906aab4d35677dc5791e00b778ab5029b1c25abcd5c9ee2c037"
SCALAR_TEST_SUCCESSOR_MANIFEST_SHA256 = (
    "129b2405eed15313415b750cbd0de1a37fe73d311690249c67929c99e7e8292e"
)


@dataclass(frozen=True)
class World:
    world_id: int
    case_id: str
    declaration_json: str
    dimensions: tuple


@dataclass(frozen=True)
class Group:
    signature: str
    dimensions: tuple
    positions: tuple
    world_ids: tuple
    input_array_bytes: int
    output_array_bytes: int
    array_working_estimate_bytes: int
    typed_evidence_estimate_bytes: int


@dataclass(frozen=True)
class Plan:
    declaration_json: str
    worlds: tuple
    groups: tuple
    execution_json: str
    total_working_estimate_bytes: int
    total_evidence_estimate_bytes: int
    identity: str


def integer(value, name, *, low=1, high=2**31 - 1):
    if type(value) is not int or not low <= value <= high:
        raise ValueError("Bounded explicit integer required: " + name)
    return value


def make_plan(raw):
    """JSON/schema work only; allocate no science arrays and touch no devices."""
    raw = scalar.parse(json.dumps(raw, allow_nan=False), max_bytes=16 * 2**20)
    if set(raw) != {"kind", "worlds", "execution"} or raw["kind"] != KIND:
        raise ValueError("Complete explicit independent charged-surface cohort required")
    execution = raw["execution"]
    expected = {
        "engine",
        "backend",
        "jit",
        "mapping",
        "max_worlds",
        "max_group_worlds",
        "max_working_bytes",
        "max_evidence_bytes",
        "max_compiler_bytes",
    }
    if set(execution) != expected or execution["mapping"] != "lax_map":
        raise ValueError("Explicit lax_map execution and all resource bounds required")
    if (
        execution["engine"] not in ("numpy", "jax")
        or execution["backend"] not in ("cpu", "gpu")
        or type(execution["jit"]) is not bool
    ):
        raise ValueError("Explicit engine/backend/JIT required")
    if execution["engine"] == "numpy" and (execution["backend"] != "cpu" or execution["jit"]):
        raise ValueError("NumPy uses CPU and no JIT; no backend fallback")
    maximum = integer(execution["max_worlds"], "max_worlds", high=128)
    width = integer(execution["max_group_worlds"], "max_group_worlds", high=32)
    integer(execution["max_working_bytes"], "max_working_bytes", high=2 * 2**30)
    integer(execution["max_evidence_bytes"], "max_evidence_bytes", high=512 * 2**20)
    integer(execution["max_compiler_bytes"], "max_compiler_bytes", low=0, high=512 * 2**20)
    if execution["engine"] == "numpy" and execution["max_compiler_bytes"] != 0:
        raise ValueError("NumPy has no declared XLA compiler allowance")
    if type(raw["worlds"]) is not list or not 1 <= len(raw["worlds"]) <= maximum:
        raise ValueError("All declared worlds must fit the cohort bound")
    worlds, buckets = [], {}
    for position, row in enumerate(raw["worlds"]):
        if set(row) != {"world_id", "case_id", "declaration"}:
            raise ValueError(
                "Each slot requires stable world/case identity and complete scalar declaration"
            )
        world_id = integer(row["world_id"], "world_id")
        if (
            type(row["case_id"]) is not str
            or re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", row["case_id"]) is None
        ):
            raise ValueError("Case IDs follow the existing simple ensemble arm names")
        declaration = row["declaration"]
        if declaration.get("law") != scalar.LAW_ID:
            raise ValueError("One unchanged bounded charged-surface law only")
        owners = declaration["owners"]
        if set(owners) != {"cells", "patches", "populations", "edges"} or any(
            type(value) is not list for value in owners.values()
        ):
            raise ValueError("Complete original owner axes required before allocation planning")
        dimensions = tuple(len(owners[key]) for key in ("cells", "patches", "populations", "edges"))
        for size, limit, low in zip(dimensions, (16, 64, 8, 128), (1, 1, 1, 0), strict=True):
            integer(size, "original owner axis", low=low, high=limit)
        declaration_text = json.dumps(
            declaration, sort_keys=True, separators=(",", ":"), allow_nan=False
        )
        if len(declaration_text.encode()) > 2**20:
            raise ValueError("Scalar declaration exceeds its original JSON cap")
        worlds.append(World(world_id, row["case_id"], declaration_text, dimensions))
        signature = scalar.digest(
            dict(
                dimensions=dimensions,
                engine=execution["engine"],
                backend=execution["backend"],
                jit=execution["jit"],
                mapping="lax_map",
                dtype="binary64",
                law=scalar.LAW_ID,
                scalar_manifest=SCALAR_MANIFEST_SHA256,
            )
        )
        buckets.setdefault(signature, []).append(position)
    if len({world.world_id for world in worlds}) != len(worlds):
        raise ValueError("World IDs must be globally distinct, including across case/shape groups")
    groups = []
    for signature, positions in buckets.items():
        for start in range(0, len(positions), width):
            slots = tuple(positions[start : start + width])
            dimensions = worlds[slots[0]].dimensions
            schema = arrays.schemas(*dimensions)
            incoming = arrays.schema_bytes(schema["inputs"], worlds=len(slots))
            outgoing = arrays.schema_bytes(schema["attempt"], worlds=len(slots))
            state = arrays.schema_bytes(schema["state"], worlds=len(slots))
            # Existing batch conventions retain host/device input+output copies.
            # Extra factors reserve RK trial temporaries and typed hex evidence.
            working = 4 * (incoming + outgoing) + 16 * state
            headers = 2048 * len(arrays.leaf_list(schema["attempt"])) * len(slots)
            declarations = sum(len(worlds[index].declaration_json.encode()) for index in slots)
            evidence = (
                8 * outgoing
                + 4 * incoming
                + headers
                + declarations
                + 8 * state
                + 65536 * len(slots)
            )
            groups.append(
                Group(
                    signature,
                    dimensions,
                    slots,
                    tuple(worlds[index].world_id for index in slots),
                    incoming,
                    outgoing,
                    working,
                    evidence,
                )
            )
    total_evidence = sum(group.typed_evidence_estimate_bytes for group in groups)
    total_working = (
        sum(group.array_working_estimate_bytes for group in groups)
        + total_evidence
        + execution["max_compiler_bytes"]
    )
    if total_evidence > execution["max_evidence_bytes"]:
        raise ValueError(
            "Complete typed evidence exceeds the declared evidence budget before allocation"
        )
    if total_working > execution["max_working_bytes"]:
        raise ValueError(
            "Complete cohort working estimate exceeds declared budget before allocation"
        )
    text = json.dumps(raw, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return Plan(
        text,
        tuple(worlds),
        tuple(groups),
        json.dumps(execution, sort_keys=True),
        total_working,
        total_evidence,
        scalar.digest(raw),
    )


def validate_plan(plan):
    if (
        type(plan) is not Plan
        or make_plan(scalar.parse(plan.declaration_json, max_bytes=16 * 2**20)) != plan
    ):
        raise ValueError("Complete cohort grouping, identity or resource plan changed")
    return plan
