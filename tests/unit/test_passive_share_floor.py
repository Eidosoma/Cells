"""§7.5's sign rule with its floor (cells.kind.passive_routes@1, amended 17 November 2026).

A step is refused only where an exact route's share lies below its floor: minus 16 eps times the
share's scale, (|mu-bar_in| + |mu-bar_out| + 2) |m|, in the share's unit (pJ, 1e-3 RT). The
scale is the raw-sum check's factor on the share's own terms, |mu-bar| |m| at each end, plus its
potentials' evaluation rounding, 2 |m| (passive_routes._shares). On FR-1's closed pair
(test_passive_routes_kind.closed_pair):
- (a) the identical-cells step measured in the gap-junction replication's line of 25 cells (D =
  1.25e-14 m^2/s, dt = 1/8 s, healthy miR200 at 0.1 mM). It moved 4.8e-20 fmol per route, below
  the amounts' resolution, against a potential difference of 4.44e-16, so each share was
  -2.1e-35 RT fmol. Planted with the same numbers, the step is admitted, and the share is booked
  as computed, bitwise (no clamp);
- (b) the floor's factor, unit and scale: a share at half its floor is admitted, and one at twice
  it is refused, at 0.1 mM and at 1 mM. At 1 mM, where mu-bar vanishes, the floor is the 2 |m|
  alone. A share a million times below its floor at 1 mM, and an honest uphill step 1.2e13
  times below its floor, are still refused, the latter with the runner's text as before. The
  sign rule is what refuses the uphill step: with the raw-sum verdict alone it is admitted;
- (c) the ledgers close in (a): the engine's host row checks pass on the booked step. The energy
  ledger's residual is the booked share, and the dissipation checks pass.
Near c = 1 mM, where the floor without 2 |m| closed (FR-19's band), identical-cells steps at
rounding level are admitted and booked as computed (the last test).
"""

import dataclasses
import re

import numpy as np
import pytest

from cells.definitions.specs import parse_spec
from cells.execution.errors import NumericalError
from cells.execution.runner import run
from cells.kinds import passive_routes
from cells.laws.electrochemistry import R
from cells.registry import kind_registry
from cells.registry.models import get_model
from tests.unit.test_passive_routes_kind import closed_pair, host_step
from validation.tissue import secreted_species_fixtures as fx

EPS = np.finfo(float).eps
HEALTHY_mM = 0.1  # The replication's healthy miR200 (100 uM): ln c = -2.3.
MOVED = 4.8e-20  # fmol per route in the measured step, below the amounts' resolution.
MEASURED_DMU = 4.440892098500626e-16  # mu-bar_in - mu-bar_out (RT) in the measured step.


def planted(ulps, *, c=HEALTHY_mM, moved=MOVED):
    """The closed pair (both 1 pL) with the cell `ulps` ulp richer than its node, and one step
    that moves `moved` fmol inward, node to cell, uphill at rounding. The increments and the
    recorded transfer carry the move; the stored amounts (reference + increment) do not change,
    as in the measured step. Returns (spec, model, start, end, p, s)."""
    spec = parse_spec(closed_pair(node_mM=c, pool_mM=float(c + ulps * np.spacing(c))))
    model = get_model(spec.model)
    start, p = model.initial_values(spec)
    s = list(spec.model.species_ids).index(fx.SPECIES)
    node = int(p.passive_outside[0]) - p.active.size
    cell, outside = start.amount_increment.copy(), start.extracellular_amount_increment.copy()
    cell[s, 0] += moved
    outside[s, node] -= moved
    record = start.passive_transferred.copy()
    record[s, 0] += moved
    end = start._replace(
        amount_increment=cell, extracellular_amount_increment=outside, passive_transferred=record
    )
    return spec, model, start, end, p, s


def potentials(start, end, p, s):
    """(mu-bar_in, mu-bar_out) of the route, in RT, from the kernel."""
    volume, _ = passive_routes._volumes(p, np)
    mu = passive_routes.passive.divided_potential_RT(
        passive_routes._amounts(start, p, np),
        passive_routes._amounts(end, p, np),
        volume[None, :],
        xp=np,
    )
    return mu[s, p.passive_inside[0]], mu[s, p.passive_outside[0]]


def test_the_identical_cells_share_is_admitted_and_booked_as_computed():
    spec, _, start, end, p, s = planted(4)
    unchanged = passive_routes._amounts(start, p, np) == passive_routes._amounts(end, p, np)
    assert np.all(unchanged)  # The move is below the amounts' resolution.
    mu_in, mu_out = potentials(start, end, p, s)
    assert mu_in - mu_out == MEASURED_DMU
    shares, floor, exact = passive_routes.share_check(start, end, p)
    share = shares[s, 0]
    assert exact[s, 0] and share < 0  # Version 1 as first built refused this step.
    rt = 1e-3 * R * spec.model.temperature_K
    assert share / rt == pytest.approx(-MOVED * MEASURED_DMU, rel=1e-12)  # -2.1e-35 RT fmol.
    assert floor[s, 0] < share and share / floor[s, 0] < 0.05  # About 1/53 of its floor.
    heat, positive, within = passive_routes.exact_booking(start, end, p, xp=np)
    assert positive and within
    booked, valid = passive_routes.book(None, start, end, None, p, spec.execution.dt, xp=np)
    assert valid
    expected = start.passive_dissipated_energy_pJ + np.asarray([share])
    assert expected[0] < start.passive_dissipated_energy_pJ[0]  # The heat falls by the share.
    assert booked["passive_dissipated_energy_pJ"].tobytes() == expected.tobytes()  # No clamp.


@pytest.mark.parametrize(
    ("c", "ratio", "admitted"),
    [
        (HEALTHY_mM, 0.5, True),
        (HEALTHY_mM, 2.0, False),
        (1.0, 0.5, True),
        (1.0, 2.0, False),
        (1.0, 1e6, False),
    ],
)
def test_the_floor_is_the_raw_sum_factor_on_the_share_scale(c, ratio, admitted):
    """The cell's lead in ulps sets the potential difference, so the share's ratio to its floor.
    The floor is 16 eps times the share's scale, (|mu-bar_in| + |mu-bar_out| + 2) |m|, in pJ.
    - At 0.1 mM: a floor in RT fmol (2.6 times smaller) would refuse the first case, and a factor
      of 32 would admit the second.
    - At 1 mM, mu-bar is 0 at the node and about 1e-14 at the cell, so the floor is the 2 |m|:
      without it the half case would be refused (FR-19's band).
    - A share a million times below its floor there is refused."""
    scale = 2 * abs(np.log(c)) + 2  # |mu-bar_in| + |mu-bar_out| + 2, both ends near ln c.
    lead = ratio * passive_routes.RAW_SUM_FACTOR * EPS * scale
    spec, _, start, end, p, s = planted(round(lead * c / np.spacing(c)), c=c)
    shares, floor, exact = passive_routes.share_check(start, end, p)
    mu_in, mu_out = potentials(start, end, p, s)
    terms = (abs(mu_in) + abs(mu_out) + 2) * MOVED  # RT fmol.
    rt = 1e-3 * R * spec.model.temperature_K
    expected = -passive_routes.RAW_SUM_FACTOR * EPS * rt * terms
    assert exact[s, 0] and floor[s, 0] == pytest.approx(expected, rel=1e-12)
    assert shares[s, 0] / floor[s, 0] == pytest.approx(ratio, rel=0.15)
    _, positive, within = passive_routes.exact_booking(start, end, p, xp=np)
    _, valid = passive_routes.book(None, start, end, None, p, spec.execution.dt, xp=np)
    assert within and bool(positive) is admitted and bool(valid) is admitted


def uphill_rates(state, potentials, control, p, *, xp):
    """The kind's rates with every flux reversed: S moves from the dilute node into the richer
    cell, and is recorded as it moves (an honest uphill step)."""
    r = passive_routes.rates(state, potentials, control, p, xp=xp)
    return r._replace(
        cell=-r.cell,
        outside=-r.outside,
        derivatives={name: -value for name, value in r.derivatives.items()},
        heat_pJ_s=-r.heat_pJ_s,
        membrane_flux=-r.membrane_flux,
    )


def raw_sums_only(applied, start, end, control, p, dt, *, xp):
    """The kind's booking with the raw-sum verdict alone: the sign rule dropped."""
    values, _ = passive_routes.book(applied, start, end, control, p, dt, xp=xp)
    return values, passive_routes.exact_booking(start, end, p, xp=xp)[2]


def scoped(**hooks):
    kinds = kind_registry.KindRegistry()
    kinds.register(dataclasses.replace(passive_routes.PASSIVE_ROUTES, **hooks))
    return kind_registry.scope(kinds)


def test_an_uphill_share_far_below_its_floor_is_still_refused():
    raw = closed_pair()
    refusal = "domain failure on [0.0, 0.001]; no invalid step accepted"  # The runner's, unchanged.
    with scoped(rates=uphill_rates):
        with pytest.raises(NumericalError, match=re.escape(refusal)):
            run(parse_spec(raw))
        assert not host_step(raw)[3]
    with scoped(rates=uphill_rates, book=raw_sums_only):
        start, end, p, valid = host_step(raw)
    assert valid  # The raw sums hold, so the refusal above is the sign rule's.
    heat, positive, within = passive_routes.exact_booking(start, end, p, xp=np)
    assert within and not positive and heat[0] < 0
    shares, floor, exact = passive_routes.share_check(start, end, p)
    assert np.all(shares[exact] / floor[exact] > 1e10)  # 1.2e13 below its floor.


def test_the_ledgers_close_in_the_identical_cells_step():
    """The engine's host row checks on the booked step: every ledger within its bound, and
    passive_dissipated_energy_pJ nonnegative and nondecreasing within the dissipation tolerance.
    No stored amount changes, so the energy ledger's residual is the booked share itself."""
    spec, model, start, end, p, _ = planted(4)
    booked, valid = passive_routes.book(None, start, end, None, p, spec.execution.dt, xp=np)
    assert valid
    end = end._replace(**booked)
    history = type(start)(*(np.stack(pair) for pair in zip(start, end, strict=True)))
    diagnostics = model.check_values(history, spec, steps=[0, 1])
    heat = float(end.passive_dissipated_energy_pJ[0])
    assert heat < 0
    assert diagnostics["max_energy_balance_error_pJ"] == pytest.approx(-heat, rel=1e-12)
    for name in ("balance", "extracellular_balance", "global_balance"):
        assert diagnostics[f"max_{name}_error_fmol"] == 0.0  # The increments carry the move.


@pytest.mark.parametrize(("c", "ulps"), [(1.0, 4), (1.01, 4), (0.99, 16)])
def test_the_floor_holds_near_one_millimolar(c, ulps):
    """|mu-bar| vanishes at c = 1 mM, but the potential difference keeps the ulp of ln c + 1 (the
    kernel's ln c + 1 - 1). The floor's 2 |m| carries that rounding, so the identical-cells step
    at rounding level is admitted near 1 mM too, and booked as computed. Without the 2 |m|, the
    4-ulp step at 1.01 mM was 12.6 times its floor and refused (FR-19's band)."""
    spec, _, start, end, p, s = planted(ulps, c=c)
    mu_in, mu_out = potentials(start, end, p, s)
    assert 0 < mu_in - mu_out < 32 * EPS  # A few ulp of ln c + 1.
    shares, floor, _ = passive_routes.share_check(start, end, p)
    share = shares[s, 0]
    assert floor[s, 0] < share < 0 and share / floor[s, 0] < 0.5
    booked, valid = passive_routes.book(None, start, end, None, p, spec.execution.dt, xp=np)
    assert valid
    expected = start.passive_dissipated_energy_pJ + np.asarray([share])
    assert booked["passive_dissipated_energy_pJ"].tobytes() == expected.tobytes()
