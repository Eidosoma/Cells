"""Actual native selections/target writes, independent owner reference and CPU JAX."""

import json
import os
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from validation.betse import native_profile_conventions as profiles
from validation.topology import betse_tissue_profiles_reference as reference
from validation.topology.betse_tissue_profiles_fixtures import base, cases

CASES = cases()
ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = json.loads(
    (ROOT / "validation/topology/betse_tissue_profiles_protocol.json").read_text()
)


def evidence(name, data):
    if folder := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        path = Path(folder)
        path.mkdir(parents=True, exist_ok=True)
        (path / ("betse-tissue-profiles-" + name + ".json")).write_text(
            json.dumps(data, indent=2, allow_nan=False) + "\n"
        )


def captured(name):
    if not (folder := os.environ.get("CELLS_BETSE_PROFILES_NATIVE_CAPTURE")):
        pytest.skip("Bounded wrapper supplies authenticated native tissue/profile captures")
    return json.loads((Path(folder) / (name + ".json")).read_text())


def make_layout(raw):
    t = raw["layout"]
    cells, membranes, env = (
        tuple(t[key]) for key in ("cell_ids", "membrane_ids", "environment_ids")
    )
    return profiles.validate_layout(
        profiles.Layout(
            cells,
            membranes,
            env,
            tuple(cells[i] for i in t["membrane_cell"]),
            tuple(env[i] if i >= 0 else None for i in t["membrane_environment"]),
            tuple(tuple(membranes[i] for i in row) for row in t["cell_membranes"]),
            np.asarray(t["cell_centres_m"], float),
            tuple(t["bounds_m"]),
            None if t["seed_fills"] is None else tuple(t["seed_fills"]),
        )
    )


def prepared(raw=None, permutations=None, native=None, padding=0, target_padding=0):
    raw = deepcopy(base() if raw is None else raw)
    layout = make_layout(raw)
    permutations = {} if permutations is None else permutations

    def row(config):
        kind = config["picker"]
        value = {
            "indices": config["indices"],
            "color": config["color"],
            "percent": config["percent"],
        }.get(kind)
        if kind == "image":
            if config.get("missing_image"):
                value = None
            else:
                value = profiles.Bitmap(np.asarray(config["bitmap"], np.float32))
        permutation = (
            tuple(
                layout.cell_ids[i]
                for i in permutations.get(config["name"], reversed(range(len(layout.cell_ids))))
            )
            if kind == "percent"
            else None
        )
        selector = profiles.Selector(
            kind,
            value,
            profiles.layout_identity(layout) if kind == "indices" else None,
            permutation,
        )
        return profiles.Profile(
            config["name"], selector, tuple(config["diffusivity_m2_s"]), config["insular"]
        )

    default, definitions = row(raw["default"]), [row(value) for value in raw["profiles"]]
    binding = profiles.compile_profiles(
        layout,
        default,
        definitions,
        ion_enabled=raw["ion_enabled"],
        is_ecm=raw["is_ecm"],
        enabled=raw["enabled"],
    )
    interventions = []
    for config in raw["events"]:
        samples = None
        if config["function"] != "None" and native is not None:
            samples = profiles.Sampled(
                native["event_declarations"][config["name"]]["scalar"], "occurrence"
            )
        interventions.append(
            profiles.Intervention(
                config["name"],
                config["kind"],
                tuple(config["profiles"]),
                config["on_s"],
                config["off_s"],
                config["change_s"],
                config["amplitude"],
                samples,
                config["function"],
            )
        )
    capacity = len(interventions) + padding
    targets = [
        profiles.bind_targets(
            binding,
            event.profiles,
            domain="cell"
            if event.kind == "pressure"
            else "environment"
            if event.kind == "ecmJ"
            else "membrane",
        )
        for event in interventions
    ]
    target_count = max((len(t.ids) for t in targets), default=0)
    events = profiles.compile_interventions(
        binding,
        interventions,
        event_capacity=capacity,
        target_capacity=target_count + target_padding,
    )
    dm_base = profiles.apply_profile_diffusion(
        np.asarray(raw["initial_membrane_m2_s"], float), binding.kernel, xp=np
    )
    state = profiles.InterventionState(
        dm_base,
        np.asarray(raw["initial_scheduled_m2_s"], float),
        np.asarray(raw["pressure_base_Pa"], float),
        np.asarray(raw["pressure_mod_Pa"], float),
        np.asarray(raw["environment_base_m2_s"], float),
        np.asarray(raw["environment_current_m2_s"], float),
        np.asarray(raw["environment_free_m2_s"], float),
        np.asarray(raw["environment_weight_base"], float),
        np.asarray(raw["environment_weight_current"], float),
    )
    return raw, binding, events, state


def adjacency(raw):
    n = len(raw["layout"]["cell_ids"])
    result = np.zeros((n, n), bool)
    for i, row in enumerate(raw["layout"]["cell_neighbors"]):
        result[i, row] = True
    return result


def close(actual, expected, field):
    atol = (
        1e-30
        if field.startswith("membrane")
        else 3e-13
        if field.startswith("pressure")
        else 1e-21
        if field == "environment_current_m2_s"
        else 3e-14
    )
    np.testing.assert_allclose(actual, expected, rtol=5e-12, atol=atol)


def test_empty_and_non_ECM_environment_absence_is_declared():
    for name in ("indices-empty", "ECM-disabled-maps-absent"):
        raw = next(r for r in CASES if r["name"] == name)
        _, binding, _, _ = prepared(raw)
        profile_name = "Empty" if name == "indices-empty" else "Patch"
        target = binding.targets[profile_name]
        assert not target.environment_declared
        assert target.environments.indices.dtype.kind == "i"
        with pytest.raises(ValueError, match="absent"):
            profiles.bind_targets(binding, [profile_name], domain="environment")


def test_stale_indices_owner_maps_and_manifests_are_rejected():
    raw, binding, events, _ = prepared()
    layout = binding.layout
    original = profiles.binding_manifest(binding)
    roundtrip = json.loads(json.dumps(original))
    profiles.validate_binding_manifest(roundtrip, binding)
    manifest = profiles.intervention_manifest(events, binding)
    profiles.validate_intervention_manifest(json.loads(json.dumps(manifest)), events, binding)
    moved = replace(layout, cell_centres_m=layout.cell_centres_m + 1e-8)
    stale = profiles.Profile(
        "Stale", profiles.Selector("indices", [0], binding.layout_identity), (1e-18,) * 6
    )
    default = profiles.Profile("Default", profiles.Selector("all"), (1e-18,) * 6)
    with pytest.raises(ValueError, match="layout identity"):
        profiles.compile_profiles(moved, default, [stale])
    other = profiles.compile_profiles(moved, default, [])
    with pytest.raises(ValueError, match="Stale"):
        profiles.validate_binding_manifest(original, other)
    with pytest.raises(ValueError, match="different profile"):
        profiles.intervention_manifest(events, other)
    malformed = replace(
        layout, cell_membrane_ids=(layout.cell_membrane_ids[1], *layout.cell_membrane_ids[1:])
    )
    with pytest.raises(ValueError, match="partition"):
        profiles.validate_layout(malformed)
    with pytest.raises(TypeError):
        binding.targets["x"] = binding.targets["Default"]
    with pytest.raises(ValueError):
        binding.targets["Default"].membranes.indices[0] = 99


def test_explicit_stable_ID_carry_requires_removed_owner_policy():
    _, binding, _, _ = prepared()
    old = binding.layout
    removed = old.cell_ids[2]
    cell_ids = tuple(v for v in old.cell_ids if v != removed)
    keep = [i for i, owner in enumerate(old.membrane_cell_ids) if owner != removed]
    membranes = tuple(old.membrane_ids[i] for i in keep)
    new = profiles.validate_layout(
        profiles.Layout(
            cell_ids,
            membranes,
            old.environment_ids,
            tuple(old.membrane_cell_ids[i] for i in keep),
            tuple(old.membrane_environment_ids[i] for i in keep),
            tuple(old.cell_membrane_ids[old.cell_ids.index(v)] for v in cell_ids),
            np.asarray([old.cell_centres_m[old.cell_ids.index(v)] for v in cell_ids]),
            old.bounds_m,
            tuple(old.seed_fills[old.cell_ids.index(v)] for v in cell_ids),
        )
    )
    with pytest.raises(ValueError, match="drop policy"):
        profiles.carry_cell_targets(binding, new)
    carried = profiles.carry_cell_targets(binding, new, missing="drop")
    assert removed not in carried["Default"].cells.ids
    assert all(v in membranes for target in carried.values() for v in target.membranes.ids)
    assert all(
        target.cells.layout_identity == profiles.layout_identity(new) for target in carried.values()
    )
    evidence(
        "stable-ID-carry",
        dict(
            status="passed",
            removed_cell_id=removed,
            before_identity=binding.layout_identity,
            after_identity=profiles.layout_identity(new),
            policy="Explicit carry/drop; native post-cut rerun is a separate operation",
        ),
    )


def test_intervention_padding_empty_buffers_and_no_input_mutation():
    raw = next(r for r in CASES if r["name"] == "event-all-kinds-and-order")
    _, binding, events, state = prepared(raw)
    _, _, padded, same = prepared(raw, padding=2, target_padding=3)
    original = deepcopy(state)
    left = profiles.apply_interventions(0.5, state, events.kernel, xp=np)
    right = profiles.apply_interventions(0.5, same, padded.kernel, xp=np)
    assert profiles.intervention_domain_valid(0.5, same, padded.kernel, xp=np)
    for a, b in zip(left.state, right.state, strict=True):
        np.testing.assert_array_equal(a, b)
    for a, b in zip(state, original, strict=True):
        np.testing.assert_array_equal(a, b)
    np.testing.assert_array_equal(right.pulse[-2:], 0.0)
    no_events = profiles.compile_interventions(binding, [], event_capacity=2, target_capacity=2)
    result = profiles.apply_interventions(0.5, state, no_events.kernel, xp=np)
    for a, b in zip(result.state, state, strict=True):
        np.testing.assert_array_equal(a, b)


@pytest.mark.parametrize(
    "variant",
    (
        "nan-state",
        "nan-clock",
        "zero-transition",
        "negative-transition",
        "invalid-target",
        "wrong-guard-type",
        "wrong-state-axis",
        "dirty-padding",
        "ecm-dynamic",
        "boolean-dynamic",
    ),
)
def test_invalid_intervention_domains(variant):
    raw = next(r for r in CASES if r["name"] == "event-all-kinds-and-order")
    _, _, events, state = prepared(raw, padding=1)
    k, time, dynamic = events.kernel, 0.5, 1.0
    if variant == "nan-state":
        state.pressure_mod_Pa[0] = np.nan
    elif variant == "nan-clock":
        time = np.nan
    elif variant == "zero-transition":
        k = k._replace(change_s=np.zeros_like(k.change_s))
    elif variant == "negative-transition":
        k = k._replace(change_s=-np.ones_like(k.change_s))
    elif variant == "invalid-target":
        k = k._replace(targets=np.full(k.targets.shape, 999))
    elif variant == "wrong-guard-type":
        k = k._replace(guard=k.guard.astype(int))
    elif variant == "wrong-state-axis":
        state = state._replace(membrane_base_m2_s=state.membrane_base_m2_s[:, :-1])
    elif variant == "dirty-padding":
        amplitude = k.amplitude.copy()
        amplitude[-1] = 1.0
        k = k._replace(amplitude=amplitude)
    elif variant == "ecm-dynamic":
        dynamic = np.full(k.kind.shape, 2.0)
    else:
        dynamic = True
    with np.errstate(all="ignore"):
        assert not profiles.intervention_domain_valid(time, state, k, dynamic, xp=np)


def test_cpu_jax_profile_diffusion_bitmap_and_insularity():
    import jax
    import jax.numpy as jnp

    raw, binding, _, state = prepared()
    assert jax.config.x64_enabled and all(device.platform == "cpu" for device in jax.devices())
    kernel = jax.tree.map(jnp.asarray, binding.kernel)
    expected = profiles.apply_profile_diffusion(
        np.asarray(raw["initial_membrane_m2_s"]), binding.kernel, xp=np
    )
    actual = jax.jit(lambda x: profiles.apply_profile_diffusion(x, kernel))(
        np.asarray(raw["initial_membrane_m2_s"])
    )
    np.testing.assert_array_equal(actual, expected)
    weights = jax.jit(
        lambda partner: profiles.insular_membrane_weights(
            binding, partner, jnp.asarray(adjacency(raw))
        )
    )(jnp.asarray(raw["layout"]["partner_membrane"]))
    np.testing.assert_array_equal(weights, reference.profiles(raw, {})["gj_weights"])
    image = raw["profiles"][0]["bitmap"]
    mask, x, y = profiles.bitmap_data(
        profiles.Bitmap(np.asarray(image, np.float32)), binding.layout.bounds_m
    )
    values = jax.jit(
        lambda points: profiles.bitmap_values(
            points, jnp.asarray(mask), jnp.asarray(x), jnp.asarray(y)
        )
    )(binding.layout.cell_centres_m)
    close(values, reference.image_values(raw["profiles"][0], raw["layout"]), "bitmap")


def test_cpu_jax_invalid_world_and_exact_control_carry_restart():
    import jax
    import jax.numpy as jnp

    raw = next(r for r in CASES if r["name"] == "event-all-kinds-and-order")
    _, _, events, state = prepared(raw)
    k, s = (jax.tree.map(jnp.asarray, v) for v in (events.kernel, state))
    valid = jax.jit(jax.vmap(lambda t: profiles.intervention_domain_valid(t, s, k)))(
        jnp.asarray([0.3, jnp.nan, 0.5])
    )
    np.testing.assert_array_equal(valid, [True, False, True])
    times = jnp.asarray([0.1, 0.3, 0.5, 0.9])

    def body(carry, time):
        result = profiles.apply_interventions(time, carry, k)
        return result.state, result.pressure_total_Pa

    run = jax.jit(lambda carry, clock: jax.lax.scan(body, carry, clock))
    full, trace = run(s, times)
    half, _ = run(s, times[:2])
    restarted, _ = run(half, times[2:])
    for a, b in zip(full, restarted, strict=True):
        np.testing.assert_array_equal(a, b)
    evidence(
        "jax-control-carry",
        dict(
            status="passed",
            times_s=[0.1, 0.3, 0.5, 0.9],
            exact_restart=True,
            shape=list(trace.shape),
            scope="Prescribed source control samples only; no solver/checkpoint migration",
        ),
    )


def test_cpu_jax_pressure_clock_gradient():
    import jax
    import jax.numpy as jnp

    raw = next(r for r in CASES if r["name"] == "event-pressure")
    _, _, events, state = prepared(raw)
    k, s = (jax.tree.map(jnp.asarray, v) for v in (events.kernel, state))
    owner = int(events.targets[0].indices[0])

    def scalar(time):
        return profiles.apply_interventions(time, s, k).pressure_total_Pa[owner]

    time, h = 0.215, 1e-6
    derivative = float(jax.jit(jax.grad(scalar))(time))
    finite = float((scalar(time + h) - scalar(time - h)) / (2 * h))
    np.testing.assert_allclose(derivative, finite, rtol=2e-8, atol=1e-8)
    assert derivative > 0 and np.isfinite(derivative)
    evidence(
        "jax-clock-gradient",
        dict(
            status="passed",
            time_s=time,
            derivative_Pa_s=derivative,
            central_difference_Pa_s=finite,
            step_s=h,
        ),
    )
