"""FR-28. Resolve the wash event and the following binding step in the same finite well."""

import json

import jax
import jax.numpy as jnp
import numpy as np

from cells.definitions import pump_composite_spec as composite
from cells.definitions.specs import parse_spec
from cells.execution.runner import run
from cells.operators import site_occupancy, wash_schedule
from cells.registry.models import get_model
from validation.tissue import wash_schedule_fixtures as fx

EVENT_TIME = 0.05
DT = 0.01


def compare(owner, fraction, buffer, *, trajectory):
    well = fx.well(wall=owner, dt=DT, end=0.1)
    definition = fx.with_wash(well, ["well"], [(EVENT_TIME, "well", fraction, {fx.TRACER: buffer})])
    spec = parse_spec(definition)
    model = get_model(spec.model)
    before, p = model.initial_values(spec)
    species = list(spec.model.species_ids).index(fx.TRACER)
    node = [n.id for n in spec.model.extracellular].index("well")
    sites = next(d for d in spec.model.operators if d.law == site_occupancy.LAW_ID)
    ids = [pop.id for pop in sites.populations]
    wall = ids.index("wall_sites")
    specimen = ids.index("specimen_sites")
    assert sites.populations[wall].owner_kind == ("node" if owner == "node" else "patch")
    if trajectory:
        result = run(spec)
        before = result.checkpoint_at(EVENT_TIME).state
    control = model.CONTROL_TYPE(*(v[0] for v in composite.control_values(spec, [EVENT_TIME])))
    wash = next(op for op in model.events if op.LAW_ID == wash_schedule.LAW_ID)
    after, valid = jax.jit(lambda row: wash.event(row, control, p, xp=jnp))(before)
    assert bool(valid)
    ref = float(p.extracellular_amount_reference[species, node])
    volume = float(p.extracellular_volume[node])
    free = float(ref + before.extracellular_amount_increment[species, node])
    liquid = float(ref + after.extracellular_amount_increment[species, node])
    collected = float(after.wash_collected_fmol[species, node])
    supplied = float(after.wash_supplied_fmol[species, node])
    bound = np.asarray(p.site_bound_anchor_fmol + before.site_bound_increment_fmol)
    vacant = np.asarray(p.site_free_anchor_fmol + before.site_free_increment_fmol)
    np.testing.assert_allclose(
        [free, bound[wall], bound[specimen]], [60, 10, 30], rtol=0, atol=1e-14
    )
    site_fields = [field for field in before._fields if field.startswith("site_")]
    assert site_fields
    for field in site_fields:
        assert (
            np.asarray(getattr(before, field)).tobytes()
            == np.asarray(getattr(after, field)).tobytes()
        ), field
    bound_after = np.asarray(p.site_bound_anchor_fmol + after.site_bound_increment_fmol)
    np.testing.assert_allclose(
        [collected, supplied], [fraction * free, fraction * volume * buffer], rtol=3e-15, atol=0
    )
    np.testing.assert_allclose(liquid, (1 - fraction) * free + supplied, rtol=0, atol=2e-14)
    _, initial_rate, _ = site_occupancy.readouts(before, control, p)
    _, rate, uptake = site_occupancy.readouts(after, control, p)
    predicted = -fraction * np.asarray(p.site_on_rate) * vacant * (free / volume - buffer)
    np.testing.assert_allclose(initial_rate, 0, rtol=0, atol=2e-15)
    np.testing.assert_allclose(rate, predicted, rtol=2e-14, atol=2e-15)
    np.testing.assert_array_equal(uptake, 0)
    report = dict(
        owner=owner,
        fraction=fraction,
        buffer_mM=buffer,
        pre_draw_free_fmol=free,
        collected_fmol=collected,
        refill_fmol=supplied,
        immediate_free_fmol=liquid,
        immediate_wall_fmol=float(bound_after[wall]),
        immediate_specimen_fmol=float(bound_after[specimen]),
        bitwise_preserved_site_fields=len(site_fields),
        immediate_wall_binding_fmol_s=float(rate[wall]),
        immediate_specimen_binding_fmol_s=float(rate[specimen]),
        error_if_drawn_from_all_tracer_fmol=float(fraction * (free + bound.sum()) - collected),
    )
    if not trajectory:
        return report, None
    hist = result.history
    times = np.asarray(result.times)
    event = int(np.flatnonzero(times == EVENT_TIME)[0])
    np.testing.assert_allclose(times[event + 1], EVENT_TIME + DT, rtol=0, atol=1e-15)
    liquid_rows = ref + np.asarray(hist.extracellular_amount_increment)[:, species, node]
    sites_rows = np.asarray(p.site_bound_anchor_fmol) + np.asarray(hist.site_bound_increment_fmol)
    drawn = np.asarray(hist.wash_collected_fmol)[:, species, node]
    refill = np.asarray(hist.wash_supplied_fmol)[:, species, node]
    np.testing.assert_array_equal(drawn[: event + 1], 0)
    np.testing.assert_array_equal(drawn[event + 1 :], collected)
    np.testing.assert_array_equal(refill[event + 1 :], supplied)
    residual = liquid_rows + sites_rows.sum(axis=1) + drawn - refill - (free + bound.sum())
    np.testing.assert_allclose(residual, 0, rtol=0, atol=1e-12)
    assert (
        sites_rows[event + 1, wall] < bound[wall]
        and sites_rows[event + 1, specimen] < bound[specimen]
    )
    assert liquid_rows[event + 1] > liquid
    report.update(
        delay_to_next_row_s=DT,
        next_wall_fmol=float(sites_rows[event + 1, wall]),
        next_specimen_fmol=float(sites_rows[event + 1, specimen]),
        next_free_fmol=float(liquid_rows[event + 1]),
        final_wall_fmol=float(sites_rows[-1, wall]),
        max_inventory_error_fmol=float(np.abs(residual).max()),
    )
    return report, (liquid_rows, sites_rows, drawn, refill)


if __name__ == "__main__":
    jax.config.update("jax_enable_x64", True)
    node, node_rows = compare("node", 0.5, fx.TRACE_mM, trajectory=True)
    stand_in, stand_in_rows = compare("stand-in", 0.5, fx.TRACE_mM, trajectory=True)
    for n, s in zip(node_rows, stand_in_rows, strict=True):
        assert n.tobytes() == s.tobytes()
    matched, _ = compare("node", 0.5, 60 / fx.V_WELL, trajectory=False)
    whole, _ = compare("node", 1.0, fx.TRACE_mM, trajectory=False)
    print(
        json.dumps(
            {"half": node, "stand_in": stand_in, "matched_buffer": matched, "whole": whole},
            indent=2,
        )
    )
