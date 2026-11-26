"""validation/tissue/composite_crossrev.py's acceptances set (docs/CORE_SEAMS_DESIGN.md §18).

The set holds quick worlds of the judged acceptances FR-1, FR-3, FR-10 and FR-6's A5''. Each is
built by its registered protocol's own generator and recorded, like crossrev's other sets, as
programs (jaxprs) and bindings, compared bitwise at every core landing.
- The set builds: every world parses with its protocol's operators. The unscheduled worlds run
  over their first five steps; the scheduled ones keep their registered horizons, which hold
  their schedule changes. The bindings record itself again bit for bit.
- A planted change in one operator's parameter changes that world's record, and nothing else in
  the set's. Each plant is the protocol's own control or generator parameter: exchange@1's export
  rate (FR-1), cells.operator.site_occupancy@1's k_on (FR-3's K_rates), the bath schedule's KCl step 1% down
  (FR-10) and the A5'' state's per-cell prior swapped (its K_prior_swapped).
The programs are traced by the gates' crossrev runs, not here: this tier-1 file records bindings
only.
"""

import pytest

from validation.tissue import composite_crossrev as crossrev

EXCHANGE, TURNOVER = (
    "cells.operator.scheduled_species_exchange@1",
    "cells.operator.scheduled_species_turnover@1",
)
OPERATORS = {
    "fr1_load_and_degrade": {"cells.operator.cell_owned_compartments@1", EXCHANGE, TURNOVER},
    "fr1_load_and_react": {
        "cells.operator.cell_owned_compartments@1",
        EXCHANGE,
        "cells.operator.local_species_reactions@1",
    },
    "fr3_q5_inward": {"cells.operator.site_occupancy@1"},
    "fr3_q5_class_switch": {"cells.operator.site_occupancy@1"},
    "fr10_ion": {"cells.operator.scheduled_bath_composition@1"},
    "fr10_ledger": {"cells.operator.scheduled_bath_composition@1"},
    "fr6_a5pp": {TURNOVER, "cells.operator.species_regulated_availability@1"},
}
SCHEDULED = {"fr3_q5_class_switch", "fr10_ion", "fr10_ledger", "fr6_a5pp"}


def plants():
    """One planted parameter per protocol: (world, the planted world's builder)."""
    from validation.tissue import a5pp_acceptance_fixtures as a5pp
    from validation.tissue import bath_schedule_fixtures as bath
    from validation.tissue import compartment_acceptance_fixtures as compartment
    from validation.tissue import site_occupancy_acceptance_fixtures as occupancy

    return {
        "fr1_load_and_degrade": lambda: crossrev._first_steps(
            compartment.load_and_degrade(export=1.01 * compartment.C6_EXPORT)
        ),
        "fr3_q5_inward": lambda: crossrev._first_steps(
            occupancy.build(occupancy.rates("q5_inward", "k_on"))
        ),
        # 1% down: the operator admits the registered step's Na ratio (1.45) and no larger.
        "fr10_ion": lambda: bath.ion_world(step_mM=0.99 * bath.ION_STEP_mM),
        "fr6_a5pp": lambda: a5pp.build(a5pp.prior("swapped")),
    }


@pytest.fixture(scope="module")
def honest(tmp_path_factory):
    directory = tmp_path_factory.mktemp("honest")
    crossrev.bindings(directory, "acceptances")
    return directory


def test_the_set_builds(honest, tmp_path):
    from cells.definitions.specs import parse_spec

    worlds = crossrev.acceptances_worlds()
    assert set(worlds) == set(OPERATORS)
    for name, raw in worlds.items():
        spec = parse_spec(raw)
        assert {op["law"] for op in raw["model"]["operators"]} == OPERATORS[name], name
        changes = {c.time for c in spec.experiment.changes}
        if name in SCHEDULED:  # The registered horizon, holding a change after time 0.
            assert any(0.0 < t < spec.experiment.end_time for t in changes), name
        else:
            assert spec.experiment.end_time == 5 * spec.execution.dt and changes <= {0.0}, name
    assert sorted(p.name for p in honest.glob("*.npz")) == sorted(f"{n}.npz" for n in OPERATORS)
    again = tmp_path / "again"
    crossrev.bindings(again, "acceptances")
    assert crossrev.compare(honest, again)


@pytest.mark.parametrize("planted", sorted(plants()))
def test_a_planted_parameter_changes_its_record(planted, honest, tmp_path, monkeypatch, capsys):
    worlds = crossrev.acceptances_worlds()
    worlds[planted] = plants()[planted]()
    monkeypatch.setattr(crossrev, "acceptances_worlds", lambda: worlds)
    crossrev.bindings(tmp_path / "planted", "acceptances")
    capsys.readouterr()
    assert not crossrev.compare(honest, tmp_path / "planted")
    differs = [line for line in capsys.readouterr().out.splitlines() if "DIFFERS" in line]
    assert len(differs) == 1 and differs[0].startswith(f"{planted}.npz DIFFERS"), differs
