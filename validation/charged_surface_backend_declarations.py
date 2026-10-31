"""Prospective independent-world declarations; no fixture is constructed here."""

from copy import deepcopy

from validation import charged_surface_work_declarations as scalar_cases


def execution(mode, *, width=2):
    if mode not in ("numpy", "jax_eager", "jax_jit"):
        raise ValueError("Only CPU qualification modes are declared this round")
    return dict(
        engine="numpy" if mode == "numpy" else "jax",
        backend="cpu",
        jit=mode == "jax_jit",
        mapping="lax_map",
        max_worlds=128,
        max_group_worlds=width,
        max_working_bytes=512 * 2**20,
        max_evidence_bytes=256 * 2**20,
        max_compiler_bytes=64 * 2**20 if mode == "jax_jit" else 0,
    )


def cohort(mode, *, width=2):
    return dict(
        kind="held_charged_surface_backend@1",
        execution=execution(mode, width=width),
        worlds=[
            dict(world_id=71, case_id="positive-a", declaration=scalar_cases.two_patch(charge=1.0)),
            dict(
                world_id=12,
                case_id="negative-b",
                declaration=scalar_cases.two_patch(charge=-1.0, steps=64),
            ),
            dict(world_id=90, case_id="multi-padded", declaration=scalar_cases.multi_owner()),
            dict(world_id=4, case_id="no-edges", declaration=scalar_cases.no_edges()),
        ],
    )


def analytic(mode, charge, steps):
    return dict(
        kind="held_charged_surface_backend@1",
        execution=execution(mode),
        worlds=[
            dict(
                world_id=317,
                case_id="two-patch-analytic",
                declaration=scalar_cases.two_patch(charge=charge, steps=steps),
            ),
        ],
    )


def reordered(raw, *, width):
    value = deepcopy(raw)
    value["worlds"] = list(reversed(value["worlds"]))
    value["execution"]["max_group_worlds"] = width
    return value
