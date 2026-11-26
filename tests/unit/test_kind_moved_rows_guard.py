"""The moved-rows guard (CORE_SEAMS §18, amended at f609dd7f; the lead's ruling 3 (a), 18 November
2026): a kind's rates move only the rows its moved_rows declares, since refusal 4 admits a kind by
them. Checked on the host at binding, at the initial and a perturbed state, with no program change.

Planted kinds from tests/kind_fixtures.py's `tests.kind.exchange@1` (B from a heredity cell to its
outside node), each with a planted error the guard must catch:
- the honest kind, whose moved_rows names its two rows, is admitted;
- one that declares no rows while it moves B is refused, naming the kind and the row;
- one that declares only its cell row is refused at the outside node;
- one that moves an undeclared row only away from the initial concentrations is refused through
  the perturbed state alone;
- a kind with rates that move nothing (FR-5's patch damage) is admitted with no rows.
"""

import dataclasses

import numpy as np
import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.registry import kind_registry
from tests import kind_fixtures as kf
from tests.unit.test_kind_seams import world


def registry(kind):
    out = kind_registry.KindRegistry()
    out.register(kind)
    return out


def test_the_honest_kind_is_admitted():
    with kind_registry.scope(registry(kf.EXCHANGE)):
        spec = parse_spec(world())
    assert dict(spec.model.kinds)[kf.KIND_ID]


@pytest.mark.parametrize(
    "declared,where",
    [
        (lambda d: (), "at cell_0"),  # Plant: no rows declared.
        (lambda d: ((d[0], d[1]),), "at bath_0"),  # Plant: the outside row left out.
    ],
)
def test_a_kind_that_moves_an_undeclared_row_is_refused(declared, where):
    planted = dataclasses.replace(kf.EXCHANGE, moved_rows=declared)
    with kind_registry.scope(registry(planted)), pytest.raises(ConfigError) as caught:
        parse_spec(world())
    message = str(caught.value)
    assert f"Kind {kf.KIND_ID}'s rates move B {where}" in message
    assert "moved_rows does not declare" in message


def _drifting_rates(state, potentials, control, p, *, xp):
    """The honest rates, plus a move of Na (row 0) at the outside node (index 0), a row the kind
    never declares, only where the cell's B stands above its initial amount: the perturbed state
    reaches it, the initial state does not. Host only (the guard runs at binding)."""
    honest = kf.EXCHANGE.rates(state, potentials, control, p, xp=xp)
    row = int(np.argmax(np.asarray(p.exchange_rate_fmol_s).sum(axis=1) > 0))  # B's row.
    initial = p.amount_reference[row, 0]
    above = initial + state.amount_increment[row, 0] > 1.0001 * initial
    stray = np.zeros(np.shape(honest.outside))
    stray[0, 0] = 1e-9
    return honest._replace(outside=honest.outside + np.where(above, stray, 0.0))


def test_a_move_only_away_from_the_initial_state_is_refused_through_the_perturbed_state():
    planted = dataclasses.replace(kf.EXCHANGE, rates=_drifting_rates)
    with kind_registry.scope(registry(planted)):
        raw = world()
        assert raw["model"]["species"][0]["id"] == "Na"
        with pytest.raises(ConfigError, match=r"rates move Na at bath_0"):
            parse_spec(raw)


def test_a_kind_whose_rates_move_nothing_needs_no_rows():
    from tests.unit.test_fr5_source_kinds import world as fr4_with_sources

    spec = parse_spec(fr4_with_sources())  # FR-5's patch damage and pH condition, built in.
    kinds = dict(spec.model.kinds)
    assert "cells.kind.patch_damage@1" in kinds and "cells.kind.ph_condition@1" in kinds
