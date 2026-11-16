"""A charged capacitor component is refused at definition (F1 and F3 of the 16 November audit).

A component's capacitor rows sum to zero, so its charges are consistent only if they sum to zero.
The field solve fixes each component's representative, whose row residual is then the component's
net charge and enters no potential. Gauge option 2 (9 November 2026) took those rows out of the
solve's convergence and gave them to the capacitor ledgers, whose allowance is zero at zero steps.
Definition checks had relied on that convergence, so a charged component then passed parse:
- the run paths failed late, not open: run, run_windowed, run_batch, run_batch_windowed and
  run_vector_windowed refused at step 0, at the capacitor ledger's first row (NumericalError);
- the stationary analysis was fail-open: on W1's P5 world (the composite, gauge) with 1e-17 C put
  on its cell it converged to a membrane voltage of 6.13e-7 V, exactly 1e-17 C / Cm, against
  0 V clean;
- an unsolvable excision cut reached the cut's own ledger before its refusal (F3).
No registered world was affected: of the 116 worlds of the results baseline and the kinds pair,
7 have a representative, and every representative residual is exactly 0 C, so the W1 and W2
judgements stand (evidence: /mnt/workspaces/Cells/core-fixes-20261116/f1/).

The check (surface_field.check_neutral_components) is the capacitor ledger's own first-row test,
charge_tolerance at zero steps, run where the field is bound (surface_tissue.initial_values), so
every identity on the field solver refuses at parse. Planted net charges at twice the bound are
refused and at half of it admitted, on a floating component and on a closed world's gauge.
"""

import copy

import numpy as np
import pytest

from cells.core.specs import ConfigError, parse_spec
from cells.models import surface_pump_v3, surface_tissue
from cells.numerics import surface_field as field
from cells.numerics import surface_imex as imex
from validation.tissue import surface_field_fixtures as field_fixtures
from validation.tissue import surface_pump_v3_fixtures as fixtures

# (arm, owner, the node a net charge is planted on): a cell of a floating component, whose
# representative is an outside node of it, and a closed world's gauge, its own component.
CASES = {
    "floating": ("open", ("cells", 0)),
    "gauge": ("closed", ("extracellular", 4)),
}
SIDES = {"twice": 2.0, "half": 0.5}


def component_bound(charge, p, node):
    """The zero-step bound at the representative of the component that holds node."""
    members = np.asarray(p.floating_basis)[:, np.asarray(p.floating_basis)[node] > 0][:, 0] > 0
    (own,) = np.flatnonzero(field.representatives(p) & members)
    return float(field.charge_tolerance(charge, np.zeros_like(charge), 0, p)[own])


@pytest.mark.parametrize("side", SIDES)
@pytest.mark.parametrize("case", CASES)
def test_check_refuses_a_charged_component_at_the_ledger_bound(case, side):
    raw = field_fixtures.definition("closed" if case == "gauge" else "open")
    *_, cell, outside, _, _, boundary, p = field_fixtures.arrays(raw)
    n = cell.size
    node = n + 4 if case == "gauge" else 0
    charge = np.r_[cell, outside]
    zero = np.r_[np.zeros(n), boundary]
    field.check_neutral_components(charge, field._capacitor_solve(charge, zero, p, xp=np), p)
    planted = charge.copy()
    planted[node] += SIDES[side] * component_bound(charge, p, node)
    potential = field._capacitor_solve(planted, zero, p, xp=np)
    if side == "half":
        field.check_neutral_components(planted, potential, p)
    else:
        with pytest.raises(ValueError, match="carries net charge"):
            field.check_neutral_components(planted, potential, p)


def planted_definition(case, factor=None, charge=None):
    arm, (key, index) = CASES[case]
    raw = fixtures.definition(arm, solver=imex.ARS222_ID)
    if factor is not None:
        spec = parse_spec(raw)
        _, p = surface_pump_v3.initial_values(spec)
        layout = surface_tissue.field_layout(p)
        q = np.r_[p.initial_cell_charge_C, p.initial_outside_charge_C]
        node = index if key == "cells" else p.active.size + index
        charge = factor * component_bound(q, layout, node)
    raw = copy.deepcopy(raw)
    owner = raw["model"][key][index]
    owner["initial_charge_C"] += charge
    owner["fixed_charge_equivalent_fmol"] += charge / surface_tissue.CHARGE_PER_FMOL
    return raw


@pytest.mark.parametrize("side", SIDES)
@pytest.mark.parametrize("case", CASES)
def test_pump_tissue_v3_refuses_a_charged_component_at_parse(case, side):
    """@3's parse, which the composite's runs through, on both sides of the bound."""
    raw = planted_definition(case, factor=SIDES[side])
    if side == "half":
        parse_spec(raw)
    else:
        with pytest.raises(ConfigError, match="carries net charge"):
            parse_spec(raw)
