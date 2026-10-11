"""Prospective CORE-010 panel identities and bounded execution settings."""

from pathlib import Path

from cells.core.batch import BatchSpec, WorldSpec
from tests.spatial_extracellular_fixtures import load_reference, spec_for

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "docs/SPATIAL_EXTRACELLULAR_ACCEPTANCE.md"
MAX_SECONDS, MAX_BYTES = 3600, 2 * 2**30
THREADS = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")
GROUPS = {
    "membrane": (
        "single_outside",
        "two_cells_chain",
        "membrane_block_release",
        "membrane_short_pulse",
        "pure_bulk",
    ),
    "mesh": ("line_8", "line_16", "line_32"),
    "ternary": ("ternary_loop",),
    "divalent": ("divalent",),
}
CAPACITIES = {
    "membrane": (3, 4, 4, 4),
    "mesh": (1, 2, 33, 32),
    "ternary": (2, 3, 4, 4),
    "divalent": (2, 3, 3, 2),
}
WINDOW_CASES = {
    "membrane": "membrane_block_release",
    "mesh": "line_32",
    "ternary": "ternary_loop",
    "divalent": "divalent",
}
CAPACITY_KEYS = ("capacity", "membrane_capacity", "extracellular_capacity", "face_capacity")
SCALAR_MODES = ("jit", "eager", "refined", "resumed")
PREVIOUS = ROOT / "runs/core-009-2026-09-10/acceptance-02"
PREVIOUS_SHA = "247e2bd8f00cb58736e2b6e7ef2bf0c0855742fa8e929e6067ef861bc2ad3b92"
RELEASE = ROOT / "runs/core-009-2026-09-10/release-audit.json"
RELEASE_SHA = "940c2289d15f2df6e04ca4a1abaece05e5a0ef7c0e4fedccc73af073d0b9133a"


def registered_spec(case, mode="jit"):
    groups = [group for group, names in GROUPS.items() if case.id in names]
    sizes = dict(zip(CAPACITY_KEYS, CAPACITIES[groups[0]], strict=True)) if groups else None
    return spec_for(
        case,
        dt=0.0000625 if mode == "refined" else 0.000125,
        jit=mode != "eager",
        capacities=sizes,
        samples=load_reference(case)["sample_times_s"],
    )


def cohort(group, cases):
    available = {c.id: c for c in cases}
    return BatchSpec(
        tuple(
            WorldSpec(i + 1, registered_spec(available[name]))
            for i, name in enumerate(GROUPS[group])
        ),
        5,
        50000,
        2**29,
    )


def window_width(group):
    return 32 if group == "mesh" else 128


def eager_schedule(cases):
    groups, weights = [[] for _ in range(4)], [0.0] * 4
    for case in sorted(cases, key=lambda c: (-c.horizon_s, c.id)):
        cpu = min(range(4), key=lambda i: weights[i])
        groups[cpu].append(case.id)
        weights[cpu] += case.horizon_s
    return {str(i): names for i, names in enumerate(groups) if names}
