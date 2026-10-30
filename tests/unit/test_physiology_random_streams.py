"""Host stream ownership/replay over frozen samplers; no physiology loop runs."""

import json
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace

import numpy as np
import pytest

from cells.core import physiology_random_streams as streams
from cells.processes import betse_perturbations as perturb


@pytest.fixture
def layout():
    return perturb.Layout(
        cell_ids=("a", "b", "c"),
        membrane_ids=("a0", "a1", "b0", "b1", "c0", "c1", "c2"),
        environment_ids=("outside0", "outside1"),
        ion_ids=("Na", "K", "Cl"),
        membrane_cell_ids=("a", "a", "b", "b", "c", "c", "c"),
        membrane_environment_ids=(
            "outside0",
            "outside1",
            "outside1",
            "outside0",
            "outside0",
            "outside1",
            "outside0",
        ),
        boundary_cell_occurrences=("c", "a", "c", "b", "c", "a"),
        membrane_area_m2=np.arange(1, 8, dtype=float) * 1e-12,
        cell_volume_m3=np.asarray([1.1e-16, 1.3e-16, 1.7e-16]),
        environment_parameter_volume_m3=2e-15,
        environment_mode="matrix",
        provenance=dict(synthetic_geometry=True, purpose="stream ownership unit fixture"),
    )


@pytest.fixture
def binding(layout):
    return perturb.bind_layout(layout)


def new(binding, law="native", *, world=7, tick=0):
    rng = perturb.native_stream(17) if law == "native" else perturb.StableCoordinates(17, world)
    return streams.new_stream(
        binding, rng, stream_id="physiology-main", world_id=world, next_tick=tick
    )


def same_packet(a, b, binding):
    assert perturb.draw_manifest(a, binding) == perturb.draw_manifest(b, binding)
    np.testing.assert_array_equal(a.values, b.values)


def reseal(record):
    record["identity"] = streams._digest(
        {key: value for key, value in record.items() if key != "identity"}
    )


def survivors(layout):
    at = [3, 1, 0]  # Explicit surviving membrane IDs, deliberately reordered.
    return replace(
        layout,
        cell_ids=("a", "b"),
        membrane_ids=tuple(layout.membrane_ids[i] for i in at),
        membrane_cell_ids=tuple(layout.membrane_cell_ids[i] for i in at),
        membrane_environment_ids=tuple(layout.membrane_environment_ids[i] for i in at),
        membrane_area_m2=layout.membrane_area_m2[at],
        cell_volume_m3=layout.cell_volume_m3[:2],
        boundary_cell_occurrences=tuple(
            value for value in layout.boundary_cell_occurrences if value != "c"
        ),
    )


@pytest.mark.parametrize("law", ["native", "stable"])
def test_stream_fields_and_nested_rng_are_immutable(binding, law):
    stream = new(binding, law)
    for key, value in (
        ("stream_id", "other"),
        ("world_id", 8),
        ("next_tick", 1),
        ("layout_identity", "0" * 64),
        ("rng", None),
    ):
        with pytest.raises(FrozenInstanceError):
            setattr(stream, key, value)
    with pytest.raises(FrozenInstanceError):
        setattr(stream.rng, "seed" if law == "stable" else "identity", 23)
    record = streams.stream_record(stream)
    record["rng"]["seed" if law == "stable" else "state"] = None
    assert streams.stream_record(stream)["rng"] != record["rng"]


def test_native_shared_tick_and_packets_match_qualified_sampler_exactly(binding):
    stream = new(binding, tick=2**40 + 3)
    original = streams.stream_record(stream)
    expected = stream.rng
    for offset, site in enumerate(
        (
            "static_K",
            "boundary_choice",
            "microtubule_gaussian",
            "protein_flux",
            "microtubule_gaussian",
        )
    ):
        tick = 2**40 + 3 + offset
        packet, after = streams.draw(stream, binding, site=site)
        target, expected = perturb.sample_native(expected, binding, site=site, tick=tick)
        same_packet(packet, target, binding)
        assert packet.tick == tick and after.next_tick == tick + 1
        assert perturb.native_stream_manifest(after.rng) == perturb.native_stream_manifest(expected)
        stream = after
    assert original["next_tick"] == 2**40 + 3


@pytest.mark.parametrize("law", ["native", "stable"])
@pytest.mark.parametrize("site", perturb.SITES)
def test_disabled_site_consumes_no_tick_rng_or_gaussian_cache(binding, law, site, monkeypatch):
    stream = new(binding, law, tick=streams.MAX_TICK)
    before = streams.stream_record(stream)

    def forbidden(*args, **kwargs):
        pytest.fail("Disabled stream called a sampler")

    monkeypatch.setattr(perturb, "sample_native", forbidden)
    monkeypatch.setattr(perturb, "sample_stable", forbidden)
    packet, after = streams.draw(stream, binding, site=site, enabled=False)
    assert packet is None and after is stream
    assert streams.stream_record(after) == before


@pytest.mark.parametrize("law", ["native", "stable"])
def test_enabled_zero_effect_still_draws_and_advances_global_tick(binding, law):
    stream = new(binding, law)
    packet, after = streams.draw(stream, binding, site="static_K")
    initial = np.ones((len(binding.ion_ids), len(binding.membrane_ids))) * 1e-18
    result = perturb.static_initialize(initial, packet.values, 0.0, binding, xp=np)
    np.testing.assert_array_equal(result.current_m2_s, initial)
    assert packet.tick == 0 and after.next_tick == 1
    assert after.rng != stream.rng if law == "native" else after.rng == stream.rng
    next_packet, again = streams.draw(after, binding, site="protein_flux")
    assert next_packet.tick == 1 and again.next_tick == 2


def test_native_cache_and_complete_state_survive_JSON_restart_without_global_rng_changes(binding):
    global_before = np.random.get_state()
    stream = new(binding)
    _, stream = streams.draw(stream, binding, site="microtubule_gaussian")
    saved = streams.stream_record(stream)
    assert saved["rng"]["state"][3] == 1  # Seven normals leave the native cached Gaussian.
    restored = streams.restore_stream(json.loads(json.dumps(saved)), binding)
    assert restored == stream and streams.stream_record(restored) == saved
    packet, after = streams.draw(stream, binding, site="microtubule_gaussian")
    repeated, restarted = streams.draw(restored, binding, site="microtubule_gaussian")
    same_packet(packet, repeated, binding)
    assert streams.stream_record(after) == streams.stream_record(restarted)
    global_after = np.random.get_state()
    assert global_before[0] == global_after[0] and global_before[2:] == global_after[2:]
    np.testing.assert_array_equal(global_before[1], global_after[1])


def test_stable_restart_uses_qualified_world_site_and_full_uint64_tick(binding):
    stream = new(binding, "stable", world=2**32 + 7, tick=2**40 + 3)
    restored = streams.restore_stream(
        json.loads(json.dumps(streams.stream_record(stream))), binding
    )
    packet, after = streams.draw(restored, binding, site="protein_flux")
    target = perturb.sample_stable(stream.rng, binding, site="protein_flux", tick=stream.next_tick)
    same_packet(packet, target, binding)
    assert after.next_tick == stream.next_tick + 1 and after.rng == stream.rng
    other_world, _ = streams.draw(
        new(binding, "stable", world=7, tick=stream.next_tick), binding, site="protein_flux"
    )
    other_site, _ = streams.draw(stream, binding, site="static_K")
    assert not np.array_equal(packet.values, other_world.values)
    assert not np.array_equal(packet.values, other_site.values)


@pytest.mark.parametrize(
    "field,value",
    [
        ("world_id", -1),
        ("world_id", 2**64),
        ("world_id", True),
        ("next_tick", -1),
        ("next_tick", 2**64),
        ("next_tick", True),
        ("stream_id", ""),
        ("stream_id", 4),
    ],
)
def test_new_stream_rejects_invalid_identifiers_and_uint64_coordinates(binding, field, value):
    args = dict(stream_id="s", world_id=7, next_tick=0)
    args[field] = value
    with pytest.raises(ValueError):
        streams.new_stream(binding, perturb.native_stream(17), **args)


@pytest.mark.parametrize("enabled", [0, 1, np.bool_(True)])
def test_draw_requires_an_explicit_boolean_activity_flag(binding, enabled):
    with pytest.raises(ValueError, match="enabled boolean"):
        streams.draw(new(binding), binding, site="static_K", enabled=enabled)


def test_invalid_sites_and_uint64_overflow_refuse_before_sampling(binding, monkeypatch):
    stream = new(binding, tick=streams.MAX_TICK)

    def forbidden(*args, **kwargs):
        pytest.fail("Invalid/overflowing request called a sampler")

    monkeypatch.setattr(perturb, "sample_native", forbidden)
    with pytest.raises(ValueError, match="site"):
        streams.draw(stream, binding, site="unknown", enabled=False)
    with pytest.raises(ValueError, match="overflow"):
        streams.draw(stream, binding, site="static_K")
    restored = streams.restore_stream(streams.stream_record(stream), binding)
    assert restored == stream


def test_last_representable_increment_is_exact(binding):
    packet, after = streams.draw(
        new(binding, tick=streams.MAX_TICK - 1), binding, site="boundary_choice"
    )
    assert packet.tick == streams.MAX_TICK - 1 and after.next_tick == streams.MAX_TICK


def test_missing_binding_is_refused_even_for_disabled_draw_or_rebind(binding):
    stream = new(binding)
    with pytest.raises(ValueError, match="Binding"):
        streams.draw(stream, None, site="static_K", enabled=False)
    with pytest.raises(ValueError, match="Binding"):
        streams.rebind_stream(stream, None, binding)


def test_stable_foreign_world_and_unsupported_rng_refuse(binding):
    for rng in (perturb.StableCoordinates(17, 8), perturb.StableCoordinates(2**32, 7), object()):
        with pytest.raises(ValueError):
            streams.new_stream(binding, rng, stream_id="s", world_id=7)


def test_native_world_label_does_not_invent_a_different_sequential_law(binding):
    a, _ = streams.draw(new(binding, world=7), binding, site="static_K")
    b, _ = streams.draw(new(binding, world=8), binding, site="static_K")
    np.testing.assert_array_equal(a.values, b.values)  # Same explicitly supplied native state.


@pytest.mark.parametrize("law", ["native", "stable"])
def test_explicit_survivor_rebind_preserves_counter_rng_and_old_stream(layout, binding, law):
    stream = new(binding, law, tick=2**40 + 3)
    if law == "native":
        _, stream = streams.draw(stream, binding, site="microtubule_gaussian")
    old_record = streams.stream_record(stream)
    cut = perturb.bind_layout(survivors(layout))
    after = streams.rebind_stream(stream, binding, cut)
    assert after.layout_identity == cut.identity
    assert after.next_tick == stream.next_tick and after.rng == stream.rng
    assert after.stream_id == stream.stream_id and after.world_id == stream.world_id
    assert streams.stream_record(stream) == old_record
    assert streams.restore_stream(streams.stream_record(after), cut) == after
    with pytest.raises(ValueError, match="layout"):
        streams.draw(stream, cut, site="protein_flux")
    with pytest.raises(ValueError, match="layout"):
        streams.restore_stream(old_record, cut)
    packet, _ = streams.draw(after, cut, site="protein_flux")
    if law == "stable":
        original = perturb.sample_stable(
            stream.rng, binding, site="protein_flux", tick=stream.next_tick
        )
        np.testing.assert_array_equal(packet.values, original.values[[3, 1, 0]])
    else:
        target, rng = perturb.sample_native(
            stream.rng, cut, site="protein_flux", tick=stream.next_tick
        )
        same_packet(packet, target, cut)
        assert rng != stream.rng


@pytest.mark.parametrize("axis", ["cell", "membrane", "environment", "ion"])
def test_rebind_rejects_explicit_foreign_owner_axes(layout, binding, axis):
    if axis == "cell":
        other = replace(
            layout,
            cell_ids=("foreign", "b", "c"),
            membrane_cell_ids=tuple("foreign" if v == "a" else v for v in layout.membrane_cell_ids),
            boundary_cell_occurrences=tuple(
                "foreign" if v == "a" else v for v in layout.boundary_cell_occurrences
            ),
        )
    elif axis == "membrane":
        other = replace(layout, membrane_ids=("foreign", *layout.membrane_ids[1:]))
    elif axis == "environment":
        other = replace(
            layout,
            environment_ids=("foreign", "outside1"),
            membrane_environment_ids=tuple(
                "foreign" if v == "outside0" else v for v in layout.membrane_environment_ids
            ),
        )
    else:
        other = replace(layout, ion_ids=("Na", "K", "foreign"))
    with pytest.raises(ValueError, match="foreign owner"):
        streams.rebind_stream(new(binding), binding, perturb.bind_layout(other))


@pytest.mark.parametrize("owner", ["cell", "environment"])
def test_rebind_rejects_reassignment_of_surviving_membrane(layout, binding, owner):
    other = replace(
        layout,
        **(
            {"membrane_cell_ids": ("b", *layout.membrane_cell_ids[1:])}
            if owner == "cell"
            else {"membrane_environment_ids": ("outside1", *layout.membrane_environment_ids[1:])}
        ),
    )
    with pytest.raises(ValueError, match="reassigned"):
        streams.rebind_stream(new(binding), binding, perturb.bind_layout(other))


def test_stale_binding_identity_cannot_hide_foreign_names(layout, binding):
    stream = new(binding)
    stale = replace(binding, membrane_ids=("foreign", *binding.membrane_ids[1:]))
    for action in (
        lambda: streams.new_stream(stale, stream.rng, stream_id="s", world_id=7),
        lambda: streams.draw(stream, stale, site="static_K"),
        lambda: streams.restore_stream(streams.stream_record(stream), stale),
    ):
        with pytest.raises(ValueError, match="changed after binding"):
            action()


@pytest.mark.parametrize(
    "defect",
    ["hash", "extra", "missing", "kind", "law", "tick", "world", "rng_extra", "cache", "version"],
)
def test_restore_refuses_corrupted_records_even_when_outer_identity_is_rehashed(binding, defect):
    law = "stable" if defect in ("world", "rng_extra") else "native"
    stream = new(binding, law)
    record = deepcopy(streams.stream_record(stream))
    if defect == "hash":
        record["next_tick"] = 1
    elif defect == "extra":
        record["foreign"] = True
    elif defect == "missing":
        del record["next_tick"]
    elif defect == "kind":
        record["kind"] = "foreign"
    elif defect == "law":
        record["law_id"] = "foreign"
    elif defect == "tick":
        record["next_tick"] = True
    elif defect == "world":
        record["world_id"] = 8
    elif defect == "rng_extra":
        record["rng"]["foreign"] = True
    elif defect == "cache":
        record["rng"]["state"][3] = 2
    else:
        record["rng"]["numpy_version"] = "foreign"
    if defect != "hash":
        reseal(record)
    with pytest.raises(ValueError):
        streams.restore_stream(record, binding)
