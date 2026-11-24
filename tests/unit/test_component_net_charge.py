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

A component that holds a held bath has no representative: its electrodes carry its net charge into
the global charge ledger, whose bound scaled only with the charge moved through the boundary. Behind
a closed patch that is the residual itself, so the 3e-25 C floor alone refused MT-1b's world at
step 64,756 (D305). The ledger now also allows the component rule's rounding on the grounded nodes'
increments (surface_field.grounded_tolerance): a closed-patch world the floor refused passes far
inside it, and a planted supply leak at twice the bound still fails, on the host and the device.

A node's charge anchor is refused at definition too when it disagrees with its inventory and fixed
background (surface_tissue.check_definition). Its 1e-20 C floor alone is finer than float64 from
2^19 fmol and refused XC0's balanced nodes (D332's C6). Above the floor the residual is now held to
the rounding budget of the anchor rule that writes a node (D333), the bound of an independent
exact-rational check of 24 November 2026. Its 17 controls are rows here, as data. The 15 balanced
nodes are admitted (the floor alone refused seven), and the two backgrounds four spacings off are
refused, as is one small inventory's anchor 2e-20 C off. Parse only: no program is compiled.
"""

import copy
import math

import jax
import numpy as np
import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.execution.errors import NumericalError
from cells.execution.runner import run
from cells.laws.electrochemistry import CHARGE_PER_FMOL
from cells.models import surface_pump, surface_pump_v3, surface_tissue
from cells.numerics import surface_field as field
from cells.numerics import surface_imex as imex
from validation.tissue import surface_field_fixtures as field_fixtures
from validation.tissue import surface_pump_v3_fixtures as fixtures

EPS = np.finfo(float).eps


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


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


# --- a held bath behind a closed patch (D305) --------------------------------------


def closed_patch(steps=200, dt=4.7e-5):
    """A held bath behind a closed patch, MT-1b's topology in miniature: @1 under ARS(2,2,2).

    One cell faces two finite lumens through open patches passing K and M, and a held bath
    through a closed patch (every permeability 0, no pump). KM flows from lumen_a through the
    cell to lumen_b, and no charge crosses the boundary, so the moved charge is the global
    charge's residual itself. Synthetic: 5e-8 F patches and 100 pL nodes make the grounded
    nodes' stored increments reach 1e-7 C in 200 steps, so their rounding passes 3e-25 C early.
    """
    z = dict(Na=1, K=1, M=-1, P=-1)
    mM = dict(
        cell_0=dict(Na=5.0, K=75.0, M=75.0, P=5.0),
        bath_0=dict(Na=145.0, K=5.0, M=140.0, P=10.0),
        lumen_a=dict(Na=5.0, K=150.0, M=145.0, P=10.0),
        lumen_b=dict(Na=5.0, K=5.0, M=5.0, P=5.0),
    )

    def node(name, **extra):
        amounts = {s: c * 100.0 for s, c in mM[name].items()}
        background = -math.fsum(z[s] * a for s, a in amounts.items())
        return dict(
            id=name,
            volume_pL=100.0,
            initial_amount_fmol=amounts,
            fixed_charge_equivalent_fmol=background,
            initial_charge_C=0.0,
            **extra,
        )

    def patch(name, outside, capacitance, permeability):
        return dict(
            id=name,
            inside="cell_0",
            outside=outside,
            area_m2=capacitance / 1e-2,
            capacitance_F=capacitance,
            law="constant_field@1",
            pump=None,
            permeability_m_per_s=dict(Na=0.0, K=permeability, M=permeability, P=0.0),
        )

    membranes = [
        patch("inner_a", "lumen_a", 5e-8, 1e-7),
        patch("inner_b", "lumen_b", 5e-8, 1e-7),
        patch("plasma_0", "bath_0", 1e-14, 0.0),
    ]
    finite = dict(reservoir=False, boundary_potential_V=0.0)
    return dict(
        schema_version=1,
        model=dict(
            id="resolved_pump_tissue@1",
            temperature_K=310.0,
            species=[dict(id=s, valence=v) for s, v in z.items()],
            cells=[node("cell_0")],
            extracellular=[
                node("bath_0", reservoir=True, boundary_potential_V=0.0),
                node("lumen_a", **finite),
                node("lumen_b", **finite),
            ],
            membranes=membranes,
            junctions=[],
            faces=[],
            closure=dict(
                law="resolved_capacitor_components_current_continuity@1", gauge_reference=None
            ),
        ),
        experiment=dict(
            end_time=dt * steps,
            observation_times=[0.0, dt * steps],
            membrane_controls=[
                dict(membrane_id=p["id"], schedule=[dict(time=0.0, availability=1.0)])
                for p in membranes
            ],
            junction_controls=[],
            pump_controls=[],
        ),
        execution=dict(
            dt=dt,
            capacity=1,
            extracellular_capacity=3,
            membrane_capacity=3,
            edge_capacity=0,
            face_capacity=0,
            backend="cpu",
            jit=True,
            precision="float64",
            solver=imex.ARS222_ID,
            field_solver="capacitive_reduction_gauged_damped_newton@2",
            max_steps=steps + 8,
            max_trace_bytes=2**30,
            material_balance_atol_fmol=dict.fromkeys(z, 1e-10),
        ),
    )


@pytest.fixture(scope="module")
def closed():
    spec = parse_spec(closed_patch())
    value = run(spec)
    _, p = surface_pump.initial_values(spec)
    return spec, value, surface_pump.STATE_TYPE(*(np.asarray(v) for v in value.history)), p


def global_charge_rows(history, p, spec):
    """Per row: |residual|, the moved-charge bound alone (before D305) and the checked bound."""
    tol = np.asarray(spec.execution.material_balance_atol_fmol)
    out = []
    for n in range(len(history.amount_increment)):
        row = type(history)(*(v[n] for v in history))
        magnitudes = surface_pump.pump_magnitudes(row, p)
        _, limits = surface_pump.ledger_limits(row, p, tol, 2e-3, steps=n, magnitudes=magnitudes)
        moved = surface_pump.global_charge_bound(row, p) + (
            surface_pump.LEDGER_STEP_ROUNDING * EPS * n * magnitudes[5]
        )
        out.append((abs(surface_pump.balances(row, p)["global_charge"]), moved, limits[5]))
    return np.asarray(out, dtype=float)


def test_closed_patch_passes_far_inside_the_grounded_allowance_the_moved_charge_refused(closed):
    """Refused by the moved-charge bound alone from row 15 (76x it at worst); passes the checked
    bound at most 0.03 of it. The residual is the bath electrode's charge, minus the grounded
    nodes' net charge change (cell and lumens), since no supply crosses the closed patch."""
    spec, value, history, p = closed
    rows = global_charge_rows(history, p, spec)
    assert value.diagnostics["max_global_charge_bound_ratio"] <= 0.05
    assert np.max(rows[:, 0] / rows[:, 2]) <= 0.05
    assert np.max(rows[:, 0] / rows[:, 1]) > 10  # Refused before D305, within 20 rows.
    assert np.flatnonzero(rows[:, 0] > rows[:, 1])[0] < 20
    last = type(history)(*(v[-1] for v in history))
    assert not np.any(last.reservoir_supplied)  # Nothing crosses the closed patch.
    layout = surface_tissue.field_layout(p)
    grounded = field.grounded_nodes(layout)
    assert grounded.tolist() == [True, False, True, True] + [False] * (grounded.size - 4)
    net = np.sum(np.where(grounded, surface_tissue.charge_increment(last, p, xp=np), 0.0))
    np.testing.assert_allclose(np.sum(last.electrode_charge_transferred_C), -net, rtol=0.05)


@pytest.mark.parametrize("factor, first", [(2.0, "global_charge"), (0.5, "reservoir_work")])
def test_supply_leak_behind_the_closed_patch_is_refused_on_both_sides_of_the_bound(
    closed, factor, first
):
    """A K supply leak at the bath of twice the checked global-charge bound fails global_charge
    first, on the host and the device. Half of it passes the global charge and fails the
    reservoir work ledger, whose fixed 3e-12 pJ its chemical work (about 8e-11 pJ) exceeds, so
    neither is admitted. At row 100 the bound (3.6e-21 C) is below K's material floor (1e-10
    fmol, 9.6e-21 C), so no material ledger sees either leak."""
    spec, _, history, p = closed
    n = 100
    one = type(history)(*(v[n : n + 1] for v in history))
    row = type(history)(*(v[0] for v in one))
    tol = np.asarray(spec.execution.material_balance_atol_fmol)
    magnitudes = surface_pump.pump_magnitudes(row, p)
    _, limits = surface_pump.ledger_limits(row, p, tol, 2e-3, steps=n, magnitudes=magnitudes)
    assert 2 * limits[5] < CHARGE_PER_FMOL * 1e-10  # Twice the bound is below K's floor.
    supplied = np.array(one.reservoir_supplied, copy=True)
    bath = int(np.flatnonzero(p.reservoir)[0])
    supplied[0, 1, bath] += factor * float(limits[5]) / CHARGE_PER_FMOL  # K, z = +1.
    seeded = one._replace(reservoir_supplied=supplied)
    try:
        surface_pump.check_values(seeded, spec, steps=[n])
        message = None
    except NumericalError as error:
        message = str(error).removeprefix(surface_pump.LEDGER_MESSAGE)
    assert message == first
    seeded_row = type(seeded)(*(v[0] for v in seeded))
    constants = surface_pump.device_check_constants(spec)
    failed, values = jax.jit(surface_pump.device_checks)(seeded_row, seeded_row, p, constants, n)
    failed = np.asarray(failed)
    assert surface_pump.DEVICE_CHECKS[int(np.argmax(failed))] == first
    ratio = float(np.asarray(values)[-1])  # max_global_charge_bound_ratio.
    assert (ratio > 1) == (factor > 1) and abs(ratio - factor) < 0.01 * factor


# --- a charge anchor at large inventories (D333) -------------------------------------------------

ANCHOR_Z = dict(Na=1, K=1, Cl=-1, A=-1, B=-1)  # XC0's cell rows, in this order below.
XC0_ANCHOR_C = -3.1415926535897935e-12  # XC0's anchor, C_total V0.
NA21, NA38 = 1374.4467859455344, 2487.0941840919195  # XC0's cell Na (fmol) at 21 and 38 mM.
TRACE_B = 0.006544984694978736  # XC0's cell B (fmol) at its trace.


def xc0_row(sodium, b, background, admitted=True, anchor=XC0_ANCHOR_C):
    """XC0's 65.45 pL cell at its K, Cl and A, with Na and the impermeant B as given."""
    amounts = (sodium, 5890.486225480862, 1963.4954084936207, 5301.437602932776, b)
    return amounts, 65.44984694978736, background, anchor, admitted


def sum_row(total, background, anchor):
    """An exact ionic sum, Na = total fmol in 1 pL beside 3, 1, 1 and 1 fmol."""
    return (total, 3.0, 1.0, 1.0, 1.0), 1.0, background, anchor, True


# The independent exact-rational check's controls (24 November 2026), row for row: case ->
# (amounts in ANCHOR_Z's order, volume pL, fixed background fmol, anchor C, admitted). Each
# background is the anchor rule's fl(fl(anchor / CHARGE_PER_FMOL) - fsum(z n)), or four of its
# spacings off that (offset). (*): the 1e-20 C floor alone refused the balanced node. The last row
# is not one of the check's.
ANCHORS = {
    "baseline": xc0_row(NA21, TRACE_B, -0.026015328716958122),
    "Na21-B-binade18": xc0_row(NA21, 393216.0, 393215.9674396866),
    "Na21-B-binade19": xc0_row(NA21, 786432.0, 786431.9674396865),
    "Na21-B-binade20": xc0_row(NA21, 1572864.0, 1572863.9674396866),
    "Na21-B-binade21": xc0_row(NA21, 3145728.0, 3145727.9674396864),  # (*)
    "Na21-B-binade22": xc0_row(NA21, 6291456.0, 6291455.967439687),  # (*)
    "Na38-B-binade18": xc0_row(NA38, 393216.0, 392103.3200415402),
    "Na38-B-binade19": xc0_row(NA38, 786432.0, 785319.3200415402),
    "Na38-B-binade20": xc0_row(NA38, 1572864.0, 1571751.3200415403),  # (*)
    "Na38-B-binade20-offset-4": xc0_row(NA38, 1572864.0, 1571751.3200415394, admitted=False),
    "Na38-B-binade20-offset+4": xc0_row(NA38, 1572864.0, 1571751.3200415412, admitted=False),
    "Na38-B-binade21": xc0_row(NA38, 3145728.0, 3144615.32004154),  # (*)
    "Na38-B-binade22": xc0_row(NA38, 6291456.0, 6290343.32004154),  # (*)
    # The anchor half a spacing of the exact ionic sum 1.5 x 2^p fmol off zero (each sign), or 0.
    "binade19-half-spacings+1": sum_row(786432.0, -786432.0, 5.616185495356914e-21),
    "binade20-half-spacings+1": sum_row(1572864.0, -1572864.0, 1.1232370990713828e-20),  # (*)
    "binade20-half-spacings-1": sum_row(1572864.0, -1572864.0, -1.1232370990713828e-20),  # (*)
    "binade26-half-spacings+0": sum_row(100663296.0, -100663296.0, 0.0),
    # A small inventory's anchor 2e-20 C off (XC0_ANCHOR_C + 2e-20), twice the floor.
    "baseline-anchor+2e-20": xc0_row(
        NA21, TRACE_B, -0.026015328716958122, False, -3.1415926335897933e-12
    ),
}


def anchor_world(amounts, volume, background, anchor, dt=4.7e-5):
    """A control's node as one cell beside a held bath (XC0's bath amounts), behind a closed patch
    of 2 pi x 10 pF (-50 mV at XC0's anchor): @1 under ARS(2,2,2)."""
    bath = dict(Na=9900.0, K=200.0, Cl=10100.0, A=1e-6, B=1e-6)
    capacitance = 6.283185307179586e-11
    patch = dict(
        id="plasma_0",
        inside="cell_0",
        outside="bath_0",
        area_m2=capacitance / 1e-2,
        capacitance_F=capacitance,
        law="constant_field@1",
        pump=None,
        permeability_m_per_s=dict.fromkeys(ANCHOR_Z, 0.0),
    )
    return dict(
        schema_version=1,
        model=dict(
            id="resolved_pump_tissue@1",
            temperature_K=291.15,
            species=[dict(id=s, valence=v) for s, v in ANCHOR_Z.items()],
            cells=[
                dict(
                    id="cell_0",
                    volume_pL=volume,
                    initial_amount_fmol=dict(zip(ANCHOR_Z, amounts, strict=True)),
                    fixed_charge_equivalent_fmol=background,
                    initial_charge_C=anchor,
                )
            ],
            extracellular=[
                dict(
                    id="bath_0",
                    volume_pL=1000.0,
                    initial_amount_fmol=bath,
                    fixed_charge_equivalent_fmol=-math.fsum(
                        ANCHOR_Z[s] * a for s, a in bath.items()
                    ),
                    initial_charge_C=0.0,
                    reservoir=True,
                    boundary_potential_V=0.0,
                )
            ],
            membranes=[patch],
            junctions=[],
            faces=[],
            closure=dict(
                law="resolved_capacitor_components_current_continuity@1", gauge_reference=None
            ),
        ),
        experiment=dict(
            end_time=dt,
            observation_times=[0.0, dt],
            membrane_controls=[
                dict(membrane_id="plasma_0", schedule=[dict(time=0.0, availability=1.0)])
            ],
            junction_controls=[],
            pump_controls=[],
        ),
        execution=dict(
            dt=dt,
            capacity=1,
            extracellular_capacity=1,
            membrane_capacity=1,
            edge_capacity=0,
            face_capacity=0,
            backend="cpu",
            jit=True,
            precision="float64",
            solver=imex.ARS222_ID,
            field_solver="capacitive_reduction_gauged_damped_newton@2",
            max_steps=8,
            max_trace_bytes=2**30,
            material_balance_atol_fmol=dict.fromkeys(ANCHOR_Z, 1e-10),
        ),
    )


@pytest.mark.parametrize("case", ANCHORS)
def test_a_charge_anchor_is_admitted_within_its_rounding_budget_and_refused_beyond_it(case):
    """The whole parse admits each balanced control and refuses each off one at the anchor."""
    amounts, volume, background, anchor, admitted = ANCHORS[case]
    raw = anchor_world(amounts, volume, background, anchor)
    if admitted:
        parse_spec(raw)
    else:
        with pytest.raises(ConfigError, match="explicit charge anchor disagree"):
            parse_spec(raw)
