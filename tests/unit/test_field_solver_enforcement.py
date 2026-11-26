"""D147 enforced on the repository's guard and registered worlds (D156; the lead's ruling, 14 Nov).

validation/tissue/field_solver_choice.declare(raw) == raw for every world definition built here:
the auto choice would change nothing, so each declares the field solver D147 asks of it. A future
guard or registered world with a free field offset that skipped declare() fails here, in tier 1,
without any src/ change.

Covered, exactly:
- the crossrev sets: validation/tissue/composite_crossrev.py's worlds (base), qualification_worlds
  (W1, W2, G2-Q1, W37 and the 825-node worlds among them), injection_worlds and volume_worlds;
  validation/division/division_crossrev.division_worlds (S5's compact worlds);
  validation/tissue/secreted_species_crossrev.species_worlds (D150's operators);
  validation/tissue/species_reactions_crossrev.reaction_worlds (D152's operator);
- D150's registered qualification arms (secreted_species_qualification.arm_world, all eight);
- S5's registered egg (egg_division_world.definition). S3's cleft egg, a J1 world
  (cleft_egg_engine.definition), is checked in test_field_solver_enforcement_cleft_egg.py: no
  module may hold a J1 source beside a partition source (the J2 bright line,
  tests/unit/test_j2_bright_line.py), and this one holds partition sources.
Not covered: the other registered protocols' worlds, built inside their own drivers (many before
D147), and E07-v1's arms, which its run driver declares by construction (e07_v1_run.build).

EXEMPT names the legacy-ID guard worlds that run as declared, version 2, on purpose, as D147's
EXEMPT (tests/unit/test_d147_drivers.py) names drivers. They are not evaluated here: two of them
are the 825-node world. The non-composite IDs take the path they took before D156's composite
clause (field_solver_choice.in_family reduces to the old prefix test for them).
"""

import pytest

from validation.tissue import field_solver_choice as choice

EXEMPT = {
    "base/replacement_padded": (
        "cells.model.resolved_pump_replacement@1",
        "crossrev guard world run as declared (version 2); one free offset",
    ),
    "qualification/S825_closed_water": (
        "cells.model.resolved_pump_water@1",
        "crossrev guard world on the 825-node world run as declared (version 2); 172 free offsets",
    ),
    "qualification/S825_event_free": (
        "cells.model.resolved_pump_replacement@1",
        "crossrev guard world on the 825-node world run as declared (version 2); 172 free offsets",
    ),
}


def raw_of(value):
    if isinstance(value, dict) and "model" in value:
        return value
    return next(v for v in value if isinstance(v, dict) and "model" in v)


def worlds():
    from validation.division import division_crossrev, egg_division_world
    from validation.tissue import composite_crossrev as cx
    from validation.tissue import secreted_species_crossrev as species
    from validation.tissue import secreted_species_qualification as d150
    from validation.tissue import species_reactions_crossrev as reactions

    sets = dict(
        base=cx.worlds(),
        qualification=cx.qualification_worlds(),
        injection=cx.injection_worlds(),
        volume=cx.volume_worlds(),
        division=division_crossrev.division_worlds(),
        species=species.species_worlds(),
        reactions=reactions.reaction_worlds(),
        d150_arms={name: d150.arm_world(name) for name in d150.ARMS},
        eggs=dict(s5_egg=egg_division_world.definition()),
    )
    return {f"{s}/{name}": raw_of(v) for s, members in sets.items() for name, v in members.items()}


WORLDS = worlds()


def test_every_exemption_names_a_world_of_its_legacy_id():
    for name, (model_id, reason) in EXEMPT.items():
        assert WORLDS[name]["model"]["id"] == model_id and reason


def test_non_composite_ids_take_the_path_they_took_before():
    for raw in WORLDS.values():
        model_id = raw["model"]["id"]
        if not model_id.startswith(choice.COMPOSITE):
            assert choice.in_family(raw) == model_id.startswith(choice.FAMILY)


@pytest.mark.parametrize("name", sorted(set(WORLDS) - set(EXEMPT)))
def test_the_auto_choice_would_change_nothing(name):
    raw = WORLDS[name]
    assert choice.declare(raw) == raw


def test_a_free_offset_composite_that_skipped_declare_would_be_caught():
    """The control: tests/field_solver_fixtures.py's minimal composite, one free offset, built
    with version 2 and never declared, is a world this test would refuse."""
    from tests.field_solver_fixtures import minimal

    raw = minimal()
    assert choice.declare(raw) != raw
