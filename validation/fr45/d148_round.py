"""D148's round for FR-45's in-place widening of cells.operator.site_occupancy@1 (D148, D327): the glue only.

Every site world is written once as JSON (`defs`), and the checkout's two existing tools read those definitions
at each revision's snapshot:
- `validation/fr43_part3/pair_check.py trace` and `compare`: the four traced programs after dead-code elimination,
  their constants, the bindings, and every state field at every step of a full-recording window;
- `validation/results_baseline.py`'s `run_paths`: runner.run and the windowed, batch, batch-windowed and
  vector-windowed paths (`paths`, a later step of the round).

This module builds definitions and adds no comparison of its own.

The worlds:
- fr3_*: every registered world of fr3-site-occupancy-v1, from its own generator
  (validation/tissue/site_occupancy_acceptance_fixtures.registered_world, at its declared dt);
- suite_*: the suite's development site worlds, one per feature the widening could reach: binding alone,
  internalisation, the wash beside a stand-in wall and beside a node's own sites (FR-27, FR-28), W on a replaced
  slot (FR-26), and @2 reading a site population's occupied fraction (FR-24).

Usage (PYTHONPATH at a snapshot, JAX_ENABLE_X64=1, the CPUs the lead assigns):
  python -B -m validation.fr45.d148_round defs DEFS
"""

import argparse
import json
import sys
from pathlib import Path


def fr3_worlds():
    """{name: raw definition} of fr3-site-occupancy-v1's registered worlds."""
    from validation.tissue import site_occupancy_acceptance_fixtures as acceptance

    return {f"fr3_{w}": acceptance.registered_world(w) for w in acceptance.world_ids()}


def _site_routed():
    """@2 routing a site population's occupied fraction to the turnover's production in its cell (FR-24's
    development form: the face-free cell, r0 on contact_0 at theta0 0.4, the site operator, @2, the turnover)."""
    from cells.registry.inventory_species import add_inventory_species
    from validation.tissue import regulated_availability_fixtures as rf
    from validation.tissue import secreted_species_fixtures as fx
    from validation.tissue import site_occupancy_fixtures as sfx

    raw = sfx.face_free_sites([sfx.population("r0", theta0=0.4)], end=0.02)
    raw = add_inventory_species(
        raw, "X0", trace_mM=1e-9, diffusivity_m2_per_s=1e-10, floor_fmol=1e-20
    )
    target = dict(operator=fx.TURNOVER, control="turnover_rate", ids=["make_x0"],
                  evaluation="target_half_steps", operating_range=[0.0, 1.0])  # fmt: skip
    entry = dict(id="c_site", target=target, law="site_fraction", basal=0.1,
                 source={"site_population": "r0", "quantity": "occupied_fraction"})  # fmt: skip
    raw = rf.with_coupling(raw, species=[], couplings=[entry])
    coupling = next(
        b
        for b in raw["model"]["operators"]
        if b["law"].startswith("cells.operator.species_regulated_availability@")
    )
    coupling["law"] = "cells.operator.species_regulated_availability@2"
    raw["model"]["operators"].append(dict(
        law=fx.TURNOVER, species=rf.identities(["X0"]), templates=[],
        routes=[dict(id="make_x0", species="X0", node="cell_0", kind="production")]))  # fmt: skip
    raw["experiment"]["turnover_controls"] = [
        dict(route_id="make_x0", carrier_id="cell_0", schedule=[dict(time=0.0, rate=2e-4)])
    ]
    return raw


def suite_worlds():
    """{name: raw definition} of the suite's development site worlds (the module docstring)."""
    from validation.tissue import site_occupancy_fixtures as sfx
    from validation.tissue import wash_schedule_fixtures as wfx

    washed = dict(dt=0.01, end=0.05, observation_times=[0.0, 0.02, 0.05])
    event = [(0.02, "well", 0.5, {wfx.TRACER: wfx.TRACE_mM})]
    occupied = [sfx.population("o0", patch="contact_0", theta0=0.4),
                sfx.population("o1", patch="contact_1", theta0=0.1)]  # fmt: skip
    return {
        "suite_binding": sfx.face_free_sites(),
        "suite_internalisation": sfx.face_free_sites([sfx.population("i0", theta0=0.3, k_int=0.5)]),
        "suite_wash_stand_in": wfx.with_wash(wfx.well(**washed), ["well"], event),
        "suite_wash_node_sites": wfx.with_wash(wfx.well(wall="node", **washed), ["well"], event),
        "suite_occupant": sfx.replaced_sites(occupied, {"o1": (0.6, 1.0, None)}),
        "suite_site_source": _site_routed(),
    }


def defs(out):
    """Write every world's definition as DEFS/NAME.json (sorted keys), then list the names."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    made = {**fr3_worlds(), **suite_worlds()}
    for name, raw in made.items():
        (out / f"{name}.json").write_text(json.dumps(raw, sort_keys=True))
    print(len(made), "worlds:", " ".join(sorted(made)))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("defs").add_argument("defs")
    args = parser.parse_args(argv)
    return defs(args.defs)


if __name__ == "__main__":
    sys.exit(main())
