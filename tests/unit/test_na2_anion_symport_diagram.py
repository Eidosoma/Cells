"""na2_anion_symport_diagram@1 (laws/cycles/na2_anion_symport_diagram.py; D228 item 1, version 2)
on the cycle kind's general layout: two Na+ and one anion imported by an eight-state diagram whose
rates each population declares (forms.resolved).

Each claim with its plant (D187), on version 1's world (heredity cell D facing its held bath, with a
declared anion of valence -1 and the population's N its cell). Its rates are this file's own: the
last backward constant closes prod k0+ = prod k0-, and the zeta are dyadic, summing to -1.
- the law registers, hosted by the transporter, its form keeping its contract (eight states, one
  cycle through all of them, every rate named) and its citation (planted, each refused at
  registration: a named k0 on a cycle that converts a species, E3);
- a population parses and binds, Wegscheider's condition admitted for its declared values inside
  its band (planted, each refused at parse naming its law, mode and cycle: one k0 off by 1e-9
  relative, and one zeta off by 1e-9);
- its S is the eight-state master equation's at 50 digits, within the kernel's derived rounding,
  at three voltages; it depends on the voltage at fixed concentrations through the zeta, and with
  every zeta zero it does not;
- its thermodynamics are version 1's at n = 2: the same x, and J vanishing at version 1's stall
  voltage, inward below it and outward above it;
- one host step closes every ledger, the cell's anion changing by the cycles.
"""

import copy
import math
import re
from decimal import Decimal, localcontext

import numpy as np
import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.definitions.surface_pump_v3_spec import control_values
from cells.kinds import transporter
from cells.laws.cycles import forms
from cells.laws.cycles import na2_anion_symport_diagram as law
from cells.laws.electrochemistry import F, R
from cells.models import surface_pump
from cells.registry import laws as law_registry
from cells.registry.models import get_model
from tests.unit.test_cycle_forms import master_equation
from validation.tissue import pump_water_fixtures as water_fixtures

EPS = np.finfo(float).eps
U = EPS / 2
ANION = "Lac"
MM = {"cell_0": 5.0, "bath_0": 1.0}
ZETA = dict(  # Dyadic, so their sum is exactly -1: the Na well at P and both crossings.
    z_na1_P_f=-0.25, z_na1_P_b=0.0, z_na2_P_f=-0.25, z_na2_P_b=0.0, z_loaded_f=-0.25,
    z_loaded_b=0.25, z_empty_f=0.0, z_empty_b=0.0,
)  # fmt: skip


def rates(seed=3):
    """Its 16 rate constants: random over three decades, the last backward one closing detailed
    balance (prod k0+ = prod k0-, in binary64: a producer's few roundings)."""
    rng = np.random.default_rng(seed)
    k = {}
    for e in law.EDGES:
        k[f"k_{e}_f"], k[f"k_{e}_b"] = (float(10 ** rng.uniform(0, 3)) for _ in range(2))
    forward = math.prod(k[f"k_{e}_f"] for e in law.EDGES)
    k["k_empty_b"] = forward / math.prod(k[f"k_{e}_b"] for e in law.EDGES[:-1])
    return k


VALUES = rates() | ZETA


def world(values=VALUES, *, capacity=0.05):
    """Version 1's world: heredity cell D, the anion at MM (its charge in each node's fixed
    background), and one population importing into the cell."""
    raw = water_fixtures.heredity_cell("D", end_time=0.002)
    m = raw["model"]
    m["species"].append(dict(id=ANION, valence=-1))
    for node in (*m["cells"], *m["extracellular"]):
        amount = node["volume_pL"] * MM[node["id"]]
        node["initial_amount_fmol"][ANION] = amount
        node["fixed_charge_equivalent_fmol"] += amount
    for patch in m["membranes"]:
        patch["permeability_m_per_s"][ANION] = 0.0
    raw["execution"]["material_balance_atol_fmol"][ANION] = 1e-15
    m[transporter.MODEL_KEY] = [
        dict(
            id="symport_0", host="membrane_0", law=law.DECLARED_ID, orientation={"N": "a"},
            capacity_fmol_s=capacity, roles={"Na": "Na", "B": ANION}, parameters=dict(values),
            held_rows=[],
        )  # fmt: skip
    ]
    return raw


def bound(raw):
    spec = parse_spec(copy.deepcopy(raw))
    impl = get_model(spec.model)
    state, p = impl.initial_values(spec)
    control = impl.Control(*(v[0] for v in control_values(spec, [0.0])))
    return spec, impl, state, p, control


def concentrations(spec):
    """{(role, end): mM} at the start: N the cell, P its bath."""
    ids, cell, bath = list(spec.model.species_ids), spec.model.cells[0], spec.model.extracellular[0]

    def c(node, s):
        return node.initial_amount_fmol[ids.index(s)] / node.volume_pL

    return {
        ("Na", "N"): c(cell, "Na"), ("Na", "P"): c(bath, "Na"),
        ("B", "N"): c(cell, ANION), ("B", "P"): c(bath, ANION),
    }  # fmt: skip


def probed(p, state, control, volts):
    potentials = np.zeros(p.active.size + p.outside_active.size)
    potentials[0] = volts  # The cell at V, its bath at 0.
    return transporter.probe(state, potentials, control, p, xp=np).modes


def test_the_law_registers_hosted_with_its_named_rates_and_refuses_e3():
    registered = law_registry.active().lookup(law.DECLARED_ID)
    assert registered is law.LAW and registered.host == transporter.KIND_ID
    assert law.DECLARED_ID in transporter.hosted_laws() and law.CYCLE.errors() == []
    d = law.CYCLE.diagram
    assert len(d.states) == 8 and len(d.edges) == 8 and len(law.CYCLE.modes) == 1
    assert len(law.CYCLE.parameters) == 24  # 16 k0 and 8 zeta, every one declared.
    rates_named = [r for e in d.edges for r in (e.forward, e.backward)]
    assert all(isinstance(r.k0_per_s, str) for r in rates_named)
    (work,) = law.LAW.source.works
    assert work.doi == "10.1529/biophysj.107.108555"
    # Planted (E3): the anion consumed at P but never released at N converts it, and a converting
    # cycle's k0 must be the law's own numbers.
    b_n = d.edges[4]
    converting = law.CYCLE._replace(
        modes=(("import", (2, -2, 0, -1)),),
        diagram=d._replace(
            edges=(
                *d.edges[:4],
                b_n._replace(backward=b_n.backward._replace(orders=())),
                *d.edges[5:],
            )
        ),
    )
    found = "; ".join(converting.errors())
    assert "a cycle that converts a species gives every k0 on its edges as a number" in found


def test_a_population_parses_with_its_declared_rates_and_refuses_each_plant():
    spec, *_ = bound(world())
    (check,) = transporter.cycle_checks(spec)
    w = check.wegscheider
    assert check.admitted and (check.charge_sum, check.charge_moved) == (0, -1)
    assert w.psi == 0 and all(b == 0 for *_, b in w.coefficients)  # B and B_psi: exactly 0.
    assert abs(w.constant) <= w.band  # R0 of the declared doubles, inside 32 eps (T + N).
    cycle = (
        rf"\({re.escape(law.DECLARED_ID)}\): mode import, its cycle through na1_P, .*, "
        r"empty, "
    )
    for planted in (
        {"k_b_P_f": VALUES["k_b_P_f"] * (1 + 1e-9)},  # R0 = ln(1 + 1e-9), far past its band.
        {"z_loaded_b": 0.25 + 1e-9},  # B_psi = -1e-9, far past u sum |zeta|.
    ):
        with pytest.raises(ConfigError, match=cycle + "fails Wegscheider's condition"):
            parse_spec(world(VALUES | planted))


def j_plus(form, ln_c, psi):
    """j+ per carrier (1/s) of the one cycle, from the 50-digit master equation (test_cycle_forms):
    its net flux over 1 - prod alpha- / prod alpha+."""
    _, alphas, nets = master_equation(form, ln_c, psi)
    with localcontext() as ctx:
        ctx.prec = 50
        plus, minus = math.prod(f for f, _ in alphas), math.prod(b for _, b in alphas)
        return float(nets[0] / (Decimal(1) - minus / plus))


def test_its_s_is_the_master_equations_and_depends_on_the_voltage_through_its_zeta():
    spec, _, state, p, control = bound(world())
    c = concentrations(spec)
    resolved = forms.resolved(law.CYCLE, VALUES)
    rows = list(resolved.rows)
    ln_c = np.log([c[row] for row in rows])
    ln_a = ln_c - math.log(resolved.diagram.standard_state_mM)
    rt = R * spec.model.temperature_K
    unzeta = forms.resolved(law.CYCLE, VALUES | dict.fromkeys(ZETA, 0.0))  # Planted: no zeta.
    seen = []
    for volts in (-0.08, -0.03, 0.02):
        psi = F * volts / rt
        s = float(probed(p, state, control, volts).s[0, 0])
        # Each log alpha is within u of its terms A = |ln k0| + sum |order ln a| + |zeta psi| (up
        # to 8 roundings with the logsumexps), and log j+ sums at most n of them
        # (test_cycle_forms' derivation): relatively, 8 u n max A.
        terms = max(
            abs(math.log(r.k0_per_s)) + abs(r.zeta * psi)
            + sum(abs(o * ln_a[rows.index((a, b))]) for a, b, o in r.orders)
            for e in resolved.diagram.edges for r in (e.forward, e.backward)
        )  # fmt: skip
        rel = 8 * U * len(resolved.diagram.states) * terms
        exact = j_plus(resolved, ln_c, psi) / law.RATE_SCALE_PER_S
        assert s == pytest.approx(exact, rel=rel, abs=0), volts
        planted = j_plus(unzeta, ln_c, psi) / law.RATE_SCALE_PER_S
        assert abs(planted / s - 1) > 1e6 * rel  # The comparison sees the zeta.
        seen.append(s)
    assert max(seen) / min(seen) > 2  # S reads V at fixed concentrations: version 1's cannot.


def test_its_thermodynamics_are_version_1s_at_n_2():
    spec, _, state, p, control = bound(world())
    c = concentrations(spec)
    rt = R * spec.model.temperature_K
    sodium, anion = c[("Na", "N")] / c[("Na", "P")], c[("B", "N")] / c[("B", "P")]
    chemical = 2 * math.log(sodium) + math.log(anion)
    for volts in (-0.07, 0.01):
        modes = probed(p, state, control, volts)
        x = chemical + F * volts / rt
        terms = float(modes.x_terms[0, 0])
        assert float(modes.x[0, 0]) == pytest.approx(x, rel=0, abs=(terms + 8) * EPS)
    stall = -(rt / F) * chemical  # Version 1's at n = 2: (n - 1) F V_stall / RT = -chemical.
    at = probed(p, state, control, stall)
    floor = float(at.scale[0, 0]) * (float(at.x_terms[0, 0]) + 8) * EPS
    assert abs(float(at.j[0, 0])) <= 16 * floor
    below = float(probed(p, state, control, stall - 0.01).j[0, 0])
    above = float(probed(p, state, control, stall + 0.01).j[0, 0])
    assert below > 0 > above


def test_one_host_step_closes_every_ledger_and_moves_the_anion_by_its_cycles():
    spec, impl, state, p, control = bound(world())
    s1, valid = impl.imex_step(state, spec.execution.dt, control, p, xp=np)
    assert bool(valid)
    history = impl.STATE_TYPE(*(np.stack(v) for v in zip(state, s1, strict=True)))
    # The runner's host checks: each ledger within its bound, or NumericalError.
    diagnostics = impl.check_values(history, spec, steps=np.arange(2))
    assert diagnostics["max_global_charge_error_C"] <= surface_pump.GLOBAL_CHARGE_ATOL_C
    ids = list(spec.model.species_ids)
    cycles = float(np.sum(s1.cycle_count))
    # The anion is moved by nothing else (Na also crosses by the world's pump and channels).
    row = ids.index(ANION)
    anion = float(s1.amount_increment[row, 0] - state.amount_increment[row, 0])
    assert cycles > 0  # Downhill inward at the world's start.
    assert anion == pytest.approx(cycles, rel=8 * EPS, abs=0)
