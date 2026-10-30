"""Bounded native scalar-control recipes; helpers execute only when requested."""

import math

CASES = (
    "square_zero",
    "square_disordered",
    "square_one_point",
    "square_count_below",
    "square_count_above",
    "square_twist_cache",
    "hex_zero",
    "hex_disordered",
    "hex_max_disorder",
    "hex_red_empty",
    "hex_raw_count_zero",
    "hex_cached",
)


def fixture(case="square_disordered"):
    if case not in CASES:
        raise ValueError("Require a declared bounded native lattice recipe")
    radius = 5e-6
    diameter = radius * 2
    length = 4 * diameter
    disorder = 0.35
    if case.endswith("zero") or case == "hex_red_empty":
        disorder = 0.0
    if case == "square_one_point":
        length = 1.1 * diameter
    elif case == "square_count_below":
        length = math.nextafter(4 * diameter, 0.0)
    elif case == "square_count_above":
        length = math.nextafter(4 * diameter, math.inf)
    elif case == "hex_red_empty":
        length = 2 * diameter
    elif case == "hex_raw_count_zero":
        length, disorder = 0.75 * diameter, 0.6
    elif case == "hex_max_disorder":
        disorder = 1.0
    warmup = 296 if case == "square_twist_cache" else 13 if case == "hex_cached" else 0
    return dict(
        recipe=dict(
            kind="cells.betse_lattice_seed_recipe@1",
            provenance="Native scalar world controls, no image/mesh or biological geometry",
            lattice_type="HEX" if case.startswith("hex") else "SQUARE",
            world_len_m=length,
            cell_radius_m=radius,
            lattice_disorder=disorder,
        ),
        stream_setup=dict(
            seed=17 if not case.startswith("hex") else 23,
            warmup_uniforms=warmup,
            has_gauss=1 if "cache" in case else 0,
            cached_gaussian=-0.25 if "cache" in case else 0.0,
        ),
    )


def empty(lattice_type):
    return dict(
        kind="cells.betse_lattice_seed_recipe@1",
        provenance="Retained empty-source failure",
        lattice_type=lattice_type,
        world_len_m=5e-6,
        cell_radius_m=5e-6,
        lattice_disorder=0.0,
    )


def overflowing_centre():
    return dict(
        kind="cells.betse_lattice_seed_recipe@1",
        provenance="Finite source coordinates with retained native mean overflow",
        lattice_type="SQUARE",
        world_len_m=1e308,
        cell_radius_m=1e307,
        lattice_disorder=0.0,
    )
