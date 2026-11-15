"""S1 to S3 in the vector-window program (FR-1; design §3.3).

The criteria are test_cell_owned_compartments_silence.py's, fixed before any run, checked on every
row of core/vector_windows.run_vector_windowed (every step observed): every round's observations of
every world. The cohort is three live-owner worlds W+ with different export rates and, as a fourth
world, the planted control (a), a K route on the bounding patch (the refusal bypassed by
monkeypatch, the same composition and program), which must break S1 and S2 in its own rows. One
program's compile: not tier 1.
"""

import jax

from cells.core.batch import BatchSpec, WorldSpec
from cells.core.specs import parse_spec
from cells.core.vector_windows import run_vector_windowed
from cells.core.windows import WindowPolicy
from cells.models.operators import compartments as comp
from validation.tissue import compartment_fixtures as cfx

jax.config.update("jax_enable_x64", True)

END, DT = 0.008, 1e-3
ROWS = int(round(END / DT)) + 1
RATES = (0.2, 0.5, 0.05)


def test_the_vector_window_program_is_silent_and_its_planted_control_is_not(monkeypatch):
    monkeypatch.setattr(comp, "refuse_ion_routes", lambda *a: None)
    specs = [parse_spec(cfx.live_compartment(end=END, dt=DT, export=r)) for r in RATES]
    specs.append(parse_spec(cfx.live_compartment(end=END, dt=DT, planted_route=cfx.PLANTED_ROUTE)))
    cohort = BatchSpec(
        tuple(WorldSpec(i + 1, s) for i, s in enumerate(specs)), len(specs), 10**6, 2**31
    )
    seen = []
    run_vector_windowed(cohort, WindowPolicy(3, "checkpoints"), sink=seen.append)
    rows = {w.world_id: 0 for w in cohort.worlds}
    planted = []
    for window in seen:
        for identity, observations in window.observations.items():
            spec = specs[identity - 1]
            if identity <= len(RATES):
                rows[identity] += cfx.assert_silent_and_live(spec, observations)
            else:
                planted.append(cfx.silence(spec, observations))
    assert all(rows[i + 1] == ROWS for i in range(len(RATES)))
    assert planted and not all(f["s1"] for f in planted)
    assert max(f["s2"] for f in planted) > 1.0
