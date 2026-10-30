"""Prepared initial-mesh requests; helpers execute only in an explicit panel."""

import hashlib
import json

import numpy as np

from cells.processes import betse_geometry_initialization as geometry
from cells.processes import betse_image_mask_prelude as image
from cells.processes import betse_initial_mesh_preparation as preparation
from cells.processes import betse_lattice_seed_generation as lattice
from cells.processes import betse_perturbations as streams
from validation.betse import betse_image_mask_prelude_fixtures as masks
from validation.betse import betse_lattice_seed_generation_fixtures as seeds

B09_CASES = (
    "irregular-centroid-aux",
    "irregular-circumcenter-aux",
    "native-single-preset-seed17",
    "native-single-preset-seed23",
    "merged-square-aux",
)
CALLER_CASES = (
    "caller-square-zero",
    "caller-square-disordered",
    "caller-hex-disordered",
    "caller-single-square-cache",
    "caller-single-hex-cache",
)
RAW_CASES = ("caller-single-point-lattice", "caller-alpha-removes-all")


def reused_B09(name):
    if name not in B09_CASES:
        raise ValueError("Require the declared reused B09 capture")
    receipt = geometry.B09_RECEIPT
    if hashlib.sha256(receipt.read_bytes()).hexdigest() != geometry.B09_SHA256:
        raise ValueError("Reviewed B09 receipt changed")
    authority = json.loads(receipt.read_text())
    relative = "native-source/" + name + ".json"
    path = receipt.parent / relative
    if hashlib.sha256(path.read_bytes()).hexdigest() != authority["output_sha256"][relative]:
        raise ValueError("Reused B09 source case changed")
    raw = json.loads(path.read_text())
    recipe = geometry.bind(
        dict(
            kind=geometry.KIND,
            classification="native_generated_ring_and_centre"
            if raw["input"]["seed_points_m"] is None
            else "manufactured_seed_cloud",
            provenance="Reuse reviewed B09 input; no new B09 geometry/RNG coverage credit",
            native_input=raw["input"],
        )
    )
    initial = geometry.load_initialization(recipe, geometry.initialise(recipe))
    return preparation.from_reused_B09(initial), raw


def caller(name, directory):
    if name not in (*CALLER_CASES, *RAW_CASES):
        raise ValueError("Require a declared native caller case")
    single = name.startswith("caller-single-") and name != "caller-single-point-lattice"
    case = (
        "square_one_point"
        if name == "caller-single-point-lattice"
        else "square_zero"
        if name == "caller-square-zero"
        else "hex_cached"
        if name == "caller-single-hex-cache"
        else "square_twist_cache"
        if name == "caller-single-square-cache"
        else "hex_disordered"
        if name == "caller-hex-disordered"
        else "square_disordered"
    )
    raw = seeds.fixture(case)
    setup = raw["stream_setup"]
    rng = np.random.RandomState(setup["seed"])
    rng.random(setup["warmup_uniforms"])
    saved = rng.get_state()
    before = streams._native_stream(
        [saved[0], saved[1].tolist(), int(saved[2]), setup["has_gauss"], setup["cached_gaussian"]],
        np.__version__,
    )
    binding = lattice.bind(raw["recipe"])
    seed_state = lattice.generate(binding, before)
    controls = masks.controls(single_cell=single)
    if name == "caller-alpha-removes-all":
        controls["alpha_shape"] = 100.0
    elif not single:
        controls["alpha_shape"] = 0.05
    image_recipe = masks.write_image(directory, "dense4")
    prelude = image.prepare(binding, seed_state, image.capture_image(image_recipe), controls)
    return preparation.from_image_prelude(binding, seed_state, prelude), dict(
        seed_recipe=raw["recipe"],
        seed_stream_before=streams.native_stream_manifest(before)["state"],
        controls=controls,
        image_recipe=image_recipe,
    )
