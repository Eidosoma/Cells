"""Native source gradients, independent geometry and compiled world isolation."""

import copy
import json
import os
from dataclasses import asdict, replace
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.processes import betse_spatial_modulation as modulation
from validation.perturbations import spatial_modulation_native as native
from validation.perturbations import spatial_modulation_reference as reference

LENGTH = 2.0**-20
CASES = (
    ("x-membranes", "gradient_x", "membranes", {}),
    ("y-membranes", "gradient_y", "membranes", {}),
    ("x-cells", "gradient_x", "cells", dict(exponent=0.75)),
    ("y-cells", "gradient_y", "cells", dict(slope=-2.0, z_offset=1.1)),
    ("x-repeat", "gradient_x", "membranes", dict(target_ids=["m0"] * 6)),
    ("x-negative-middle", "gradient_x", "membranes", dict(x_offset=-1.0)),
    ("y-zero-power", "gradient_y", "membranes", dict(exponent=0.0)),
    ("y-steep", "gradient_y", "cells", dict(exponent=7.5, x_offset=-0.25)),
    ("r-full", "gradient_r", "membranes", {}),
    ("r-subset", "gradient_r", "membranes", dict(target_ids=["m1", "m4"])),
    ("r-repeat", "gradient_r", "membranes", dict(target_ids=["m2", "m2", "m0"])),
    ("r-zero-scale", "gradient_r", "membranes", dict(slope=0.0, z_offset=-0.3)),
)


def program(kind="gradient_x", domain="membranes", **changes):
    cells, membranes = [f"c{i}" for i in range(3)], [f"m{i}" for i in range(6)]
    parameters = dict(
        kind=kind,
        target_domain=domain,
        target_ids=cells if domain == "cells" else membranes,
        cell_ids=cells,
        membrane_ids=membranes,
        cell_centres_m=np.array([[-2, 1], [1, -1], [4, 3]], dtype=np.float64) * LENGTH,
        membrane_midpoints_m=np.array(
            [[-3, 0], [-1, 2], [0, -2], [2, 0], [3, 2], [5, 4]], dtype=np.float64
        )
        * LENGTH,
        centre_m=[LENGTH, 0.5 * LENGTH],
        x_offset=0.25 * LENGTH if kind == "gradient_r" else 0.13,
        exponent=None if kind == "gradient_r" else 2.0,
        slope=0.7,
        z_offset=0.2,
        provenance="Manufactured pinned-source geometry; explicit metres and ordered owners",
    )
    return modulation.bind(**(parameters | changes))


def evidence(name, payload):
    if directory := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        folder = Path(directory) / "spatial-modulation"
        folder.mkdir(parents=True, exist_ok=True)
        with (folder / (name + ".json")).open("x") as stream:
            json.dump(payload, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")


def compare(actual, wanted):
    assert np.asarray(actual.finite).all()
    errors = dict(
        factor=float(
            np.max(abs(np.asarray(actual.factor) - wanted["factor"])) / wanted["factor_budget"]
        ),
        normalization=float(
            abs(float(actual.normalization_m) - wanted["normalization_m"])
            / wanted["normalization_budget_m"]
        ),
    )
    assert max(errors.values()) <= 1, errors
    return errors


@pytest.mark.parametrize("name,kind,domain,changes", CASES)
def test_source_and_independent_geometry(name, kind, domain, changes):
    bound = program(kind, domain, **changes)
    saved = modulation.record(bound)
    actual, source = modulation.evaluate(bound, xp=np), native.evaluate(saved)
    np.testing.assert_array_equal(actual.factor, source["factor"])
    assert source["dynamic"] == [1, 1, 1]
    wanted = reference.evaluate(saved)
    errors = compare(actual, wanted)
    evidence(
        name,
        dict(
            parameters=saved,
            reference=wanted,
            error_fractions=errors,
            actual={k: np.asarray(v).tolist() for k, v in actual._asdict().items()},
            source=dict(
                factor=source["factor"].tolist(),
                dynamic=source["dynamic"],
                source_sha256=source["source_sha256"],
            ),
            biological_cases=0,
        ),
    )


def test_axis_source_uses_length_and_full_geometry_not_target_order_or_values():
    first = program()
    for targets in (tuple(reversed(first.target_ids)), ("m0",) * 6):
        other = program(target_ids=targets)
        assert other.identity != first.identity
        np.testing.assert_array_equal(
            modulation.evaluate(first, xp=np).factor, modulation.evaluate(other, xp=np).factor
        )
    # Source tie chooses membranes, even when the caller intended cell indices.
    saved = modulation.record(first)
    saved.update(
        cell_ids=list(first.membrane_ids),
        cell_centres_m=[list(p) for p in first.membrane_midpoints_m],
        target_domain="cells",
    )
    source = native.evaluate(saved)
    np.testing.assert_array_equal(source["factor"], modulation.evaluate(first, xp=np).factor)
    with pytest.raises(ValueError, match="target-count"):
        modulation.bind(**{k: v for k, v in saved.items() if k not in ("identity", "law")})


def test_partial_axis_selection_retains_native_unbound_axis_failure():
    first = program()
    saved = modulation.record(first)
    saved["target_ids"] = ["m1", "m3"]
    with pytest.raises(UnboundLocalError):
        native.evaluate(saved)
    with pytest.raises(ValueError, match="target-count"):
        program(target_ids=["m1", "m3"])
    # Three membrane targets would silently select the three cell centres.
    saved["target_ids"] = ["m1", "m2", "m3"]
    assert native.evaluate(saved)["factor"].shape == (3,)
    with pytest.raises(ValueError, match="target-count"):
        program(target_ids=saved["target_ids"])
    evidence(
        "native-axis-refusals",
        dict(
            native_partial_failure="UnboundLocalError",
            native_count_tie_branch="membranes",
            wrong_domain_selected_by_length=True,
            cells_bind_refusal=True,
            source_sha256=native.PINNED,
        ),
    )


def test_radial_support_offset_and_unit_translation():
    bound = program("gradient_r", target_ids=["m1", "m4"])
    original = modulation.evaluate(bound, xp=np)
    np.testing.assert_array_equal(original.factor[[0, 2, 3, 5]], bound.z_offset)
    values = asdict(bound)
    values.pop("identity")
    # Translate coordinates and centre together; retain both-axis source offset.
    translation = np.array([16, -32], dtype=np.float64) * LENGTH
    moved = modulation.bind(
        **(
            values
            | dict(
                membrane_midpoints_m=np.asarray(bound.membrane_midpoints_m) + translation,
                cell_centres_m=np.asarray(bound.cell_centres_m) + translation,
                centre_m=np.asarray(bound.centre_m) + translation,
            )
        )
    )
    np.testing.assert_array_equal(original.factor, modulation.evaluate(moved, xp=np).factor)
    scaled = modulation.bind(
        **(
            values
            | dict(
                membrane_midpoints_m=np.asarray(bound.membrane_midpoints_m) * 8,
                cell_centres_m=np.asarray(bound.cell_centres_m) * 8,
                centre_m=np.asarray(bound.centre_m) * 8,
                x_offset=bound.x_offset * 8,
            )
        )
    )
    answer = modulation.evaluate(scaled, xp=np)
    np.testing.assert_array_equal(original.factor, answer.factor)
    assert answer.normalization_m == 8 * original.normalization_m


@pytest.mark.parametrize(
    "defect", ("owner", "coordinate", "units", "target", "coefficient", "missing", "extra", "seal")
)
def test_saved_full_geometry_and_coefficients_cannot_be_reassociated(defect):
    bound = program("gradient_r")
    saved = modulation.record(bound)
    changed = copy.deepcopy(saved)
    if defect == "owner":
        changed["membrane_ids"][0] = "different-owner"
    elif defect == "coordinate":
        changed["membrane_midpoints_m"][1][0] += LENGTH
    elif defect == "units":
        changed["membrane_midpoints_m"] = (
            np.asarray(changed["membrane_midpoints_m"]) * 1e6
        ).tolist()
    elif defect == "target":
        changed["target_ids"].pop()
    elif defect == "coefficient":
        changed["x_offset"] += LENGTH
    elif defect == "missing":
        changed.pop("centre_m")
    elif defect == "extra":
        changed["implicit_axis"] = "cells"
    else:
        changed["identity"] = "0" * 64
    with pytest.raises(ValueError):
        modulation.restore(changed, expected_identity=bound.identity)
    restored = modulation.restore(json.loads(json.dumps(saved)), expected_identity=bound.identity)
    assert restored == bound
    with pytest.raises(ValueError):
        modulation.validate(replace(bound, slope=1.5))


@pytest.mark.parametrize("defect", ("flat", "midpoint", "power", "overflow", "empty_radial"))
def test_native_nonfinite_geometry_is_reported_without_regularization(defect):
    changes = {}
    kind = "gradient_x"
    if defect == "flat":
        changes["membrane_midpoints_m"] = [[0.0, 0.0]] * 6
    elif defect == "midpoint":
        changes["x_offset"] = -0.5
    elif defect == "power":
        changes.update(x_offset=-1.0, exponent=0.5)
    elif defect == "overflow":
        kind = "gradient_r"
        changes["membrane_midpoints_m"] = [[1e200, -1e200]] * 6
    else:
        kind = "gradient_r"
        changes["target_ids"] = []
    bound = program(kind, **changes)
    with np.errstate(all="ignore"):
        actual, source = (
            modulation.evaluate(bound, xp=np),
            native.evaluate(modulation.record(bound)),
        )
    assert not actual.finite.all() and not np.isfinite(source["factor"]).all()
    np.testing.assert_array_equal(np.isfinite(actual.factor), np.isfinite(source["factor"]))
    evidence(
        "native-nonfinite-" + defect,
        dict(
            parameters=modulation.record(bound),
            actual_finite=actual.finite.tolist(),
            source_finite=np.isfinite(source["factor"]).tolist(),
            normalized_or_clipped=False,
            source_sha256=native.PINNED,
        ),
    )


@pytest.mark.parametrize("bad", (True, float("inf"), float("nan"), "1"))
def test_binding_requires_finite_explicit_coefficients(bad):
    with pytest.raises(ValueError):
        program(slope=bad)


@pytest.mark.parametrize(
    "defect", ("duplicate", "missing_owner", "coordinates", "centre", "radial_cells", "law")
)
def test_binding_refuses_incomplete_or_inconsistent_owner_geometry(defect):
    changes = {
        "duplicate": dict(cell_ids=["c0"] * 3),
        "missing_owner": dict(target_ids=["absent"] * 6),
        "coordinates": dict(cell_centres_m=[[1.0, 2.0]]),
        "centre": dict(centre_m=[1.0]),
        "radial_cells": dict(kind="gradient_r", domain="cells"),
        "law": dict(kind="gradient_bitmap"),
    }
    with pytest.raises(ValueError):
        program(**changes[defect])


@pytest.mark.parametrize("dtype", (np.float32, np.int64, np.bool_))
def test_kernels_reject_implicit_precision(dtype):
    with pytest.raises(ValueError, match="float64"):
        modulation.axis(np.ones(3, dtype=dtype), 0.1, 2.0, 0.7, 0.2, xp=np)


def test_kernel_world_broadcast_and_empty_world_axes():
    coordinates = np.asarray(program().membrane_midpoints_m)
    actual = modulation.axis(coordinates[:, 0], np.array([0.13, 0.25]), 2.0, 0.7, 0.2, xp=np)
    assert actual.factor.shape == (2, 6)
    for i, offset in enumerate((0.13, 0.25)):
        compare(
            modulation.Values(*(v[i] for v in actual)),
            reference.evaluate(modulation.record(program(x_offset=offset))),
        )
    empty = modulation.axis(np.empty((0, 6)), 0.13, 2.0, 0.7, 0.2, xp=np)
    assert empty.factor.shape == (0, 6) and empty.normalization_m.shape == (0,)
    empty = modulation.radial(
        np.empty((0, 6, 2)), np.ones(6, dtype=bool), np.zeros(2), 0.0, 0.7, 0.2, xp=np
    )
    assert empty.factor.shape == (0, 6)
    with pytest.raises(ValueError):
        modulation.axis(np.empty(0), 0.1, 2.0, 0.7, 0.2, xp=np)


@pytest.mark.parametrize("kind", ("gradient_x", "gradient_r"))
def test_cpu_jax_compiled_batched_geometry_and_invalid_world_isolation(kind):
    assert jax.config.jax_enable_x64 and jax.default_backend() == "cpu"
    programs = [program(kind), program(kind, slope=-1.2)]
    coordinates = jnp.asarray([p.membrane_midpoints_m for p in programs], dtype=jnp.float64)
    slopes = jnp.asarray([p.slope for p in programs])
    if kind == "gradient_x":
        kernel = jax.jit(jax.vmap(lambda x, s: modulation.axis(x[:, 0], 0.13, 2.0, s, 0.2)))
    else:
        kernel = jax.jit(
            jax.vmap(
                lambda x, s: modulation.radial(
                    x,
                    jnp.ones(6, dtype=bool),
                    jnp.asarray(programs[0].centre_m),
                    0.25 * LENGTH,
                    s,
                    0.2,
                )
            )
        )
    output = kernel(coordinates, slopes)
    worlds = []
    for i, bound in enumerate(programs):
        saved = modulation.record(bound)
        answer = modulation.Values(*(np.asarray(v[i]) for v in output))
        wanted = reference.evaluate(saved)
        worlds.append(
            dict(
                parameters=saved,
                reference=wanted,
                error_fractions=compare(answer, wanted),
                actual={k: v.tolist() for k, v in answer._asdict().items()},
            )
        )
    bad = coordinates.at[0].set(jnp.nan)
    invalid = kernel(bad, slopes)
    assert not np.asarray(invalid.finite[0]).any() and np.asarray(invalid.finite[1]).all()
    np.testing.assert_array_equal(invalid.factor[1], output.factor[1])
    evidence(
        "cpu-jax-" + kind, dict(worlds=worlds, invalid_world_isolated=True, biological_cases=0)
    )
