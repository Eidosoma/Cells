"""FR-37 (D274): a draw from chosen parts of an unevenly mixed liquid, with existing operators.

**The answer: yes, with declared regions and declared draws.** cells.operator.scheduled_compartment_wash@1 (FR-27)
draws a fraction of a well-mixed finite node and refills it with buffer, so a liquid declared as
two regions, A and B, each its own finite node, takes a draw of chosen volumes from each:
one wash event per region at the same time, with fraction = drawn volume / region volume.

**The synthetic test** (the request's words): a passive neutral tracer S, 8 fmol in A and 2 fmol in
B (100 pL each), above the same buffer background (S's trace, 1e-12 mM). Each case starts fresh
and collects 100 pL, refilled with buffer at the background:
- "unmixed": all 100 pL from A (A's fraction 1.0; B has no event): sample 8, left 2;
- "mixed": A and B mixed completely, then drawn. The mixed state is declared (5 fmol in each): no
  operator mixes two finite nodes beside a wash, since the wash refuses a face at a washed node
  (D246, until a face's booking of the step is measured). 50 pL from each: sample 5, left 5;
- "port": 75 pL from A and 25 pL from B (fractions 0.75 and 0.25): sample 6.5, left 3.5.

**What each case reports** (report()), all from the wash's own records at the event:
- each region's drawn volume (its fraction times its volume);
- the sample: the sum over the regions of wash_collected_fmol, with its concentration over the
  drawn volume. The engine holds one collected record per region: the sample as one amount is
  this host-side sum, of records that the wash books exactly;
- each region's remainder, and the buffer supplied by the refills (wash_supplied_fmol), recorded
  separately;
- the account: sample + remainders = the starting 10 fmol (plus the background) + the buffer
  supplied, within rounding.

**Checked edge cases:** a fraction of exactly 1.0 is admitted ((0, 1]); a fraction of 0 is refused,
so a region with no draw takes no event; events on two nodes at one time are admitted (times must
increase only per node). The regions are separate finite nodes, each facing the probe cell through
a patch nothing crosses (which places it in the cell's capacitor component); the event is
instantaneous, so no transport acts during the draw.

**The inputs.**
- **Declared by the user in this test:**
  - the regions, as finite nodes with their volumes;
  - the starting distribution;
  - each region's drawn volume and the draw's time;
  - the refill buffer.

  An assumed dye-rich region reproduces a high reading, and the remainders it predicts (each
  region's, above) are what a measurement of the dye left behind tests.
- **Not calculated by Cells from the port, flow and timing.** Cells has no bulk flow: liquid moves
  between nodes only by a face's diffusion (Fick) and by declared routes, and nothing models a
  port's suction. So which parts of the liquid a draw takes cannot be computed, only declared.
  Mixing can be computed, by diffusion on a face, but not beside the wash: the wash refuses a face
  at a washed node until that booking is measured (D246). So a mixed state is declared here.
- **The smallest general addition,** if the split is to be predicted:
  - an advection operator on faces, a declared volumetric flow toward a port node carrying each
    upstream node's concentration, conservative and upwind;
  - with it, the measurement that lifts the wash's face refusal.

  It is not needed for this test.

report(case) applies the composite's own event maps to the bound state on the host, the same code
the runner compiles (no run is needed: nothing moves before the draw); run(case) runs the case
through the runner, for a user who wants the records in a run's history.

Run: PYTHONPATH=src:. JAX_ENABLE_X64=1 JAX_PLATFORMS=cpu python -m validation.sampling.uneven_draw
"""

import json

import numpy as np

from cells.definitions import pump_composite_spec as cs
from cells.definitions.specs import parse_spec
from cells.registry.models import get_model
from validation.tissue import secreted_species_fixtures as fx
from validation.tissue import wash_schedule_fixtures as wfx

S = fx.SPECIES
REGIONS = ("A", "B")
VOLUME_PL = 100.0
BACKGROUND_mM = 1e-12  # S's trace: the buffer's and every region's background.
DT, T_DRAW = 1e-3, 1e-3
# fmol above the background at the start, and each region's drawn volume (pL), per case.
CASES = {
    "unmixed": (dict(A=8.0, B=2.0), dict(A=100.0)),
    "mixed": (dict(A=5.0, B=5.0), dict(A=50.0, B=50.0)),
    "port": (dict(A=8.0, B=2.0), dict(A=75.0, B=25.0)),
}


def world(case):
    """The two regions with the case's starting tracer, the probe cell facing each through a patch
    nothing crosses, and the case's draws as wash events at T_DRAW."""
    start, drawn = CASES[case]
    raw = fx.world(
        cells=(("probe_cell", 1.0),),
        nodes=tuple((r, VOLUME_PL) for r in REGIONS),
        baths=("bath",),
        contacts=tuple((f"port_{r}", "probe_cell", r) for r in REGIONS),
        faces=(),
        dt=DT,
        end=2 * DT,
        observation_times=[0.0, T_DRAW, 2 * DT],
        trace_mM=BACKGROUND_mM,
        concentrations_mM={r: start[r] / VOLUME_PL + BACKGROUND_mM for r in REGIONS},
    )
    events = [(T_DRAW, r, v / VOLUME_PL, {S: BACKGROUND_mM}) for r, v in drawn.items()]
    return wfx.with_wash(raw, list(REGIONS), events)


def _amounts(spec, p, state):
    outside = [c.id for c in spec.model.extracellular]
    s = list(spec.model.species_ids).index(S)
    ref = np.asarray(p.extracellular_amount_reference)[s]
    inc = np.asarray(state.extracellular_amount_increment)[s]
    return {r: float(ref[outside.index(r)] + inc[outside.index(r)]) for r in REGIONS}, s, outside


def report(case):
    """The case's draw (module docstring), from the composite's event maps at T_DRAW."""
    spec = parse_spec(world(case))
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    control = model.CONTROL_TYPE(*(v[0] for v in cs.control_values(spec, [T_DRAW])))
    after = state
    for op in model.events:
        after, ok = op.event(after, control, p, xp=np)
        assert ok is None or bool(ok), f"{case}: an event refused the step"
    before, s, outside = _amounts(spec, p, state)
    left, _, _ = _amounts(spec, p, after)
    collected = np.asarray(after.wash_collected_fmol)[s]
    supplied = np.asarray(after.wash_supplied_fmol)[s]
    _, drawn = CASES[case]
    volume = {r: drawn.get(r, 0.0) for r in REGIONS}
    sample = float(sum(collected[outside.index(r)] for r in REGIONS))
    refill = float(sum(supplied[outside.index(r)] for r in REGIONS))
    background = BACKGROUND_mM * VOLUME_PL
    return dict(
        case=case,
        drawn_pL=volume,
        sample_fmol=sample,
        sample_mM=sample / sum(volume.values()),
        sample_above_background_fmol=sample - BACKGROUND_mM * sum(volume.values()),
        remainder_fmol=left,
        remainder_above_background_fmol={r: left[r] - background for r in REGIONS},
        refill_supplied_fmol=refill,
        start_fmol=before,
        account_residual_fmol=sample + sum(left.values()) - sum(before.values()) - refill,
    )


def run(case):
    """The case through the runner: (spec, RunResult); the draw is the history's row after
    T_DRAW (the wash records at the start of the step leaving T_DRAW)."""
    from cells.execution.runner import run as run_spec

    spec = parse_spec(world(case))
    return spec, run_spec(spec)


if __name__ == "__main__":
    import jax

    jax.config.update("jax_enable_x64", True)
    print(json.dumps({case: report(case) for case in CASES}, indent=1))
