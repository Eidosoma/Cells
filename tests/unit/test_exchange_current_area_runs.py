"""Tier-2 test: exchange's current-area read (D191) compiled, beside membrane state (FR-7 item 3).

The only compiled coverage of D191's first production current-value read at stage split
(cells.operator.scheduled_species_exchange@1 reading membrane_area through the composite's reader view; the lead's
rulings of 20 November 2026). The host-only checks are in test_cell_owned_compartments.py (the
viewed half-step bitwise the declared-area one, and a doubled area doubling the rate constant); this
file runs the traced program: FR-7's U2 world in miniature (validation/fr7/unit_turnover_fixtures:
the unit producer on kir_0, cells.operator.species_regulated_availability@2 routing a template onto its assembly
rate, a compartment of the cell holding template, and an exchange import releasing it), 300 steps
of 1 ms through the windowed runner. Every step is checked by the runner; exchange is the
composition's one view reader; and the compartment's template follows n0 exp(-kappa t), which the
import's rate constant sets from the area it reads (the declared one, bit for bit, since nothing
writes the areas).

Its cost and reason (D224): about 30 s on one CPU, almost all of it the compile (28.8 s on the timed
lane, 42 s as a workspace probe on a loaded light CPU); the reason is above.
"""

import numpy as np

from cells.definitions.specs import parse_spec
from cells.execution.windows import WindowPolicy, iter_windows
from cells.registry.models import get_model
from validation.fr7 import unit_turnover_fixtures as ufx

KAPPA = 0.5  # 1/s: the release's rate constant out of the compartment, synthetic.
END, EVERY = 0.3, 0.01  # s: 300 steps, observed every 10 steps.


def world():
    obs = [round(EVERY * k, 9) for k in range(int(round(END / EVERY)) + 1)]
    raw = ufx.with_producer(
        ufx.cell(end=END, observation_times=obs),
        [ufx.route("kir_units", "kir_0")],
        {"kir_units": [(0.0, 0.02, 0.01)]},
    )
    raw = ufx.with_compartment(ufx.with_template_route(raw), amounts_fmol={ufx.TEMPLATE: 1e-5})
    return ufx.with_release(raw, [(0.0, ufx.release_velocity(KAPPA))])


def test_the_compiled_import_reads_the_area_through_the_view():
    spec = parse_spec(world())
    model = get_model(spec.model)
    assert [op.LAW_ID for op in model.view_readers] == ["cells.operator.scheduled_species_exchange@1"]
    _, p = model.initial_values(spec)
    species = list(spec.model.species_ids).index(ufx.TEMPLATE)
    node = [o.id for o in spec.model.extracellular].index(ufx.NODE)
    n0 = float(np.asarray(p.extracellular_amount_reference)[species, node])
    dt = spec.execution.dt
    wanted = {int(round(float(t) / dt)) for t in spec.experiment.observation_times}
    seen = set()  # Adjacent windows share one endpoint (EventGrid.windows): count steps, not rows.
    for window in iter_windows(spec, WindowPolicy(window_steps=100, recording="observations")):
        for i, _ in enumerate(np.asarray(window.times)):
            k = window.start_step + i
            if k not in wanted:
                continue
            increment = np.asarray(window.history.extracellular_amount_increment)[i]
            n = n0 + float(increment[species, node])
            exact = n0 * np.exp(-KAPPA * k * dt)
            assert abs(n - exact) <= 1e-12 * exact, (k, n, exact)
            seen.add(k)
    assert seen == wanted
