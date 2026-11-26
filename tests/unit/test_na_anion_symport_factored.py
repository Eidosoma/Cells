"""cells.cycle.na_anion_symport_factored@1 (laws/cycles/na_anion_symport_factored.py; D228 item 1) on the
cycle kind's general layout: a fuel-free, electrogenic import of n Na+ and one monovalent anion.

Each claim with its plant (D187), on this file's own world (heredity cell D facing its held bath,
with a declared anion of valence -1 and the population's N its cell):
- the law registers, hosted by the transporter, its form keeping its contract, its rows Na and the
  anion at both ends, its one named count n_Na, and its citation the abstract it rests on (planted:
  a fractional Hill number refused at registration);
- a population parses, binds and imports: each mode conserves charge and carries n - 1 charges
  into its cell, its binding names the law's roles, ends and count, and its free energy and
  saturation are their closed forms (planted, each refused at parse: n_Na 5, n_Na 1.5, and the
  anion role bound to a cation);
- J vanishes at the stall voltage, runs inward below it and outward above it, scales with the
  capacity at every state without moving it, and an n = 1 population is electroneutral (no
  voltage term, no conductance);
- its rows move n Na+ and one anion per cycle, from P to N, and one host step closes every ledger
  with the cell's anion (moved by nothing else) changing by the cycles.
"""

import copy
import math

import numpy as np
import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.definitions.surface_pump_v3_spec import control_values
from cells.kinds import transporter
from cells.laws.cycles import na_anion_symport_factored as law
from cells.laws.cycles.forms import Saturation
from cells.laws.electrochemistry import F, R
from cells.registry import kind_registry
from cells.registry import laws as law_registry
from cells.registry.models import get_model
from validation.tissue import pump_water_fixtures as water_fixtures

EPS = np.finfo(float).eps
ANION = "Lac"
MM = {"cell_0": 5.0, "bath_0": 1.0}
PARAMETERS = dict(n_Na=2, K_Na_mM=30.0, K_B_mM=0.1, hill_Na=2, hill_B=1)


def world(*, capacity=0.05, roles=None, **parameters):
    """Heredity cell D, the anion at MM (its charge kept in each node's fixed background), and one
    population importing into the cell."""
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
            capacity_fmol_s=capacity, roles=roles or {"Na": "Na", "B": ANION},
            parameters={**PARAMETERS, **parameters}, held_rows=[],
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
    ids, cell, bath = list(spec.model.species_ids), spec.model.cells[0], spec.model.extracellular[0]

    def c(node, s):
        return node.initial_amount_fmol[ids.index(s)] / node.volume_pL

    return {s: (c(cell, s), c(bath, s)) for s in ("Na", ANION)}


def probed(p, state, control, volts):
    potentials = np.zeros(p.active.size + p.outside_active.size)
    potentials[0] = volts  # The cell at V, its bath at 0.
    return transporter.probe(state, potentials, control, p, xp=np)


def test_the_law_registers_hosted_with_its_form_and_citation():
    registered = law_registry.active().lookup(law.DECLARED_ID)
    assert registered is law.LAW and registered.host == transporter.KIND_ID
    assert law.DECLARED_ID in transporter.hosted_laws() and law.CYCLE.errors() == []
    assert kind_registry.law_roles(law.LAW) == {"Na", "B"}
    assert kind_registry.law_ends(law.LAW) == {"N", "P"}
    assert kind_registry.law_count_names(law.LAW) == {"n_Na"}
    (work,) = law.LAW.source.works
    assert work.doi == "10.1529/biophysj.107.108555" and work.year == 2007
    # Planted: a fractional Hill number is refused at registration (the factored form's integers).
    fractional = law.CYCLE._replace(
        saturation=((Saturation(("Na", "P"), "K_Na_mM", 1.5), law.CYCLE.saturation[0][1]),)
    )
    assert any("Hill number" in error for error in fractional.errors())


def test_a_population_imports_n_na_and_one_anion_with_n_minus_one_charges():
    spec, _, state, p, control = bound(world())
    (check,) = transporter.cycle_checks(spec)
    # Charge-conserving and admitted, its charge moved from N to P -(n - 1).
    assert (check.charge_sum, check.charge_moved, check.admitted) == (0, -1, True)
    (binding,) = kind_registry.kind_role_species(
        transporter.TRANSPORTER, dict(spec.model.kinds)[transporter.KIND_ID]
    )
    assert binding.roles == {"Na": "Na", "B": ANION} and binding.parameters == {"n_Na": 2}
    assert binding.ends == {"N": "cell_0", "P": "bath_0"}
    c = concentrations(spec)
    n, volts = 2, -0.05
    modes = probed(p, state, control, volts).modes
    psi = F * volts / (R * spec.model.temperature_K)
    x = n * math.log(c["Na"][0] / c["Na"][1]) + math.log(c[ANION][0] / c[ANION][1]) + (n - 1) * psi
    terms = float(modes.x_terms[0, 0])
    assert float(modes.x[0, 0]) == pytest.approx(x, rel=0, abs=(terms + 8) * EPS)
    s = 1 / (1 + (30.0 / c["Na"][1]) ** 2) / (1 + 0.1 / c[ANION][1])  # At the source end, P.
    assert float(modes.s[0, 0]) == pytest.approx(s, rel=(terms + 8) * EPS, abs=0)
    # Its rows: n Na+ and one anion from P to N per cycle (each nu J, one mode: exact).
    rows = probed(p, state, control, volts).rows
    j = float(modes.j[0, 0])
    ids = list(spec.model.species_ids)
    for k in range(int(np.sum(p.cycle_row_present))):
        species, at_n = ids[int(p.cycle_row_species[k, 0])], bool(p.cycle_row_at_n[k, 0])
        nu = (n if species == "Na" else 1) * (1 if at_n else -1)
        assert float(rows.rate[k, 0]) == nu * j, (species, at_n)
    # Planted, each refused at parse: n_Na out of its range, n_Na fractional, the anion role on Na.
    for planted, reason in (
        (world(n_Na=5), "n_Na"),
        (world(n_Na=1.5), "n_Na"),
        (world(roles={"Na": "Na", "B": "K"}), "valence"),
    ):
        with pytest.raises(ConfigError, match=reason):
            parse_spec(planted)


def test_j_stalls_at_its_voltage_scales_with_capacity_and_n_one_is_electroneutral():
    spec, _, state, p, control = bound(world())
    c = concentrations(spec)
    rt = R * spec.model.temperature_K
    n = 2
    chemical = n * math.log(c["Na"][0] / c["Na"][1]) + math.log(c[ANION][0] / c[ANION][1])
    stall = -(rt / ((n - 1) * F)) * chemical
    at = probed(p, state, control, stall).modes
    floor = float(at.scale[0, 0]) * (float(at.x_terms[0, 0]) + 8) * EPS
    assert abs(float(at.j[0, 0])) <= 16 * floor  # Its stall (and reversal) voltage.
    below = float(probed(p, state, control, stall - 0.01).modes.j[0, 0])
    above = float(probed(p, state, control, stall + 0.01).modes.j[0, 0])
    assert below > 0 > above  # Inward below the stall, outward above it.
    # The capacity scales J at every state, and moves neither x nor the stall.
    spec2, _, state2, p2, control2 = bound(world(capacity=0.1))
    for volts in (stall - 0.03, stall + 0.02, -0.07):
        one, two = probed(p, state, control, volts).modes, probed(p2, state2, control2, volts).modes
        assert float(two.x[0, 0]) == float(one.x[0, 0])
        # J+ = exp(ln k + ln a + ln S): each evaluation within a few roundings of its exponent.
        exponent = abs(math.log(float(one.j_plus[0, 0])))
        allowed = 4 * EPS * (exponent + 4)
        assert float(two.j[0, 0]) == pytest.approx(2 * float(one.j[0, 0]), rel=allowed, abs=0)
    # n = 1: electroneutral, so no voltage term and no conductance.
    spec1, _, state1, p1, control1 = bound(world(n_Na=1))
    (check,) = transporter.cycle_checks(spec1)
    assert check.charge_moved == 0
    low, high = probed(p1, state1, control1, -0.1), probed(p1, state1, control1, 0.05)
    assert float(low.modes.x[0, 0]) == float(high.modes.x[0, 0])
    assert float(low.populations.conductance_pS[0]) == 0.0


def test_one_host_step_closes_every_ledger_and_moves_the_anion_by_its_cycles():
    spec, impl, state, p, control = bound(world())
    s1, valid = impl.imex_step(state, spec.execution.dt, control, p, xp=np)
    assert bool(valid)
    history = impl.STATE_TYPE(*(np.stack(v) for v in zip(state, s1, strict=True)))
    diagnostics = impl.check_values(history, spec, steps=np.arange(2))  # The runner's host checks.
    assert diagnostics["max_global_charge_error_C"] == 0.0
    ids = list(spec.model.species_ids)
    cycles = float(np.sum(s1.cycle_count))
    # The anion is moved by nothing else (Na also crosses by the world's pump and channels).
    row = ids.index(ANION)
    anion = float(s1.amount_increment[row, 0] - state.amount_increment[row, 0])
    assert cycles > 0  # Downhill inward at the world's start.
    assert anion == pytest.approx(cycles, rel=8 * EPS, abs=0)
