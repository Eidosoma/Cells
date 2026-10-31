"""Byte-for-byte AST scientific assertions reused from reviewed component successor."""

import copy

from tests.unit import test_betse_normal_ecm_event_mechanics as component

base, catalog, exact, established = (
    component.base,
    component.catalog,
    component.exact,
    component.established,
)
ions, np, joined = component.ions, component.np, component.joined
mechanical_rows = component.mechanical_rows


def compare_call(
    binding,
    parent,
    candidate,
    context,
    native_call,
    captured,
    incoming,
    index,
    observed,
    answers,
    tmp_path,
    case,
    point,
    check,
):
    inner, trial, feedback, calcium, noise, event_context = context["event_return"]
    exact(observed["events"], native_call["before_events"])
    exact(event_context["events"], native_call["events"])
    exact(event_context["reset_return"], native_call["reset_return"])
    packet = copy.deepcopy(observed["material"])
    packet.pop("prospective_noise_draw")
    exact(packet, native_call["material_before"])
    exact(observed["calcium"], native_call["calcium"]["before"])
    exact(observed["channels"], native_call["network"]["before_channels"])
    exact(observed["network"], native_call["network"]["before"])
    exact(observed["field"], native_call["field"]["before"])
    base.compare_native_material(trial, native_call)
    exact(feedback, native_call["network"])
    catalog.compare_calcium_native(calcium, native_call["calcium"])
    established.compare_noise_native(noise, native_call["noise"])
    exact(ions.data(inner.noise_cache), native_call["noise_cache_after"])
    exact(
        joined.event.random_source.native_stream_manifest(inner.noise_stream),
        native_call["noise_stream_after"],
    )
    exact(inner.event_stores, native_call["event_stores_after"])
    exact(inner.network.network_cache, native_call["post_material_cache"])
    exact(inner.network.material.values._asdict(), native_call["candidate"])
    exact(ions.data(inner.rate_cache), native_call["rate_cache_after"])
    exact(ions.data(parent.events.clock), native_call["clock_before"])
    exact(ions.data(inner.clock), native_call["clock_after"])
    for section, value in base.field_output(inner.field).items():
        exact(value, native_call["field"][section])
    mechanical = captured["mechanics_history"][index]
    assert mechanical["source_completed"] and mechanical["complete_available_buffers"]
    exact(context["mechanics_input"], mechanical["before"])
    exact(observed["mechanics"]["initial"], ions.data(parent.mechanics.cache))
    exact(context["mechanics_input"]["primary_cell_mM"], noise["after"]["cell_mol_m3"])
    exact(context["mechanics_input"]["primary_env_mM"], noise["after"]["environment_mol_m3"])
    exact(context["mechanics_input"]["pressure_Pa"], event_context["events"]["after"]["P_cells"])
    exact(context["mechanics_input"]["temperature_K"], event_context["events"]["after"]["T"])
    exact(candidate.sample_state, captured["sample_states"][index])
    assert not candidate.sample_state["display_completed"] and (
        not candidate.mechanics.sampled_steps
    )
    assert candidate.mechanics.step_index == inner.clock.call_index == index + 1
    assert inner.clock.material_dt_sum_s == (index + 1) * incoming["calendar"]["dt_s"]
    preview = observed["material"]
    assert preview["prospective_draw_is_uncommitted"]
    exact(preview["noise_stream_before"], noise["stream_before"])
    exact(preview["prospective_stream_after"], noise["stream_after"])
    if noise["guard_active"]:
        assert len(noise["draws"]) == 1
        np.testing.assert_array_equal(
            preview["prospective_noise_uniforms"], noise["draws"][0]["values"]
        )
    else:
        assert not noise["draws"] and preview["prospective_noise_uniforms"] is None
    noise_comparison = dict(
        ions.data(noise),
        reference_input=observed["noise"],
        geometry=binding.events.material_binding.geometry_binding.geometry,
    )
    comparisons = (
        (
            "events",
            established.compare_events(
                event_context["events"], event_context["reset_return"], *answers["events"]
            ),
        ),
        ("material", base.compare_material(trial, *answers["material"])),
        ("calcium", catalog.compare_calcium(calcium, *answers["calcium"])),
        ("channels", catalog.compare_channels(binding.events, feedback, *answers["channels"])),
        ("network", base.legacy.compare_local(feedback, *answers["network"])),
        ("noise", established.compare_noise(noise_comparison, *answers["noise"])),
        (
            "mechanics",
            mechanical_rows(context["mechanics_trial"], mechanical, *answers["mechanics"]),
        ),
        ("field", base.compare_field(binding.events, inner.field, *answers["field"])),
    )
    for mode, rows in comparisons:
        check(tmp_path, case + "-" + mode + "-errors-" + str(index), point / mode, rows)
