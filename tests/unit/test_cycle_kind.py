"""cells.transporter@1's population axis: seam A's general layout (the kinds owner's design
statement 1, confirmed 18 November 2026, and its amendments).

Each claim with its plant (D187); every world is this file's own (no seam-A reference state):
- selection (§1): a declaration in version 1's form keeps today's structure entry, fields and hooks
  (planted: an entry that does not remove the axis's hooks); the general form, two populations on
  one patch and finite fuel under the neutral law take the population axis; each entry writes
  back in the form it was declared in;
- the general parse refuses with its reason (unknown host, orientation, roles, valence, ranges,
  held rows, fuel kinds, a charged held row (Q4), duplicate IDs), and admits chemistry at P (K3;
  refused before it, as Q3);
- the layouts agree (condition 2): at the start, the probe's x, S, J+, J-, J, heat, work, charge
  and conductance, and the proton law's step terms; over steps (@3's own IMEX step on the host, the
  runner's checked step for a declared tableau, without its compile), the cycles, amounts, supply,
  heat and work, within bounds derived from the two evaluations' rounding whose X and one-way
  scale are read from the probe at both ends, for the neutral world and the charged one (planted:
  one side's capacity 1e-9 larger, refused); the compiled path's agreement is FR-4's quick world,
  the kinds owner's evidence, and §10's composed world runs compiled in
  tests/unit/test_cycle_kind_runs.py;
- N = b: the role moves from the outside node, the free energy's voltage term turns with it;
- the probe is the run's own arithmetic: its rates are the rates hook's, J = J+ - J-, heat,
  rows, current, and its conductance and material slopes against central differences;
- the guard (§5.2): factored and diagram populations give G <= 0 exactly at every draw; an honest
  net-flow law stays within the allowance at states down to equilibrium, and so does one booked in
  a cycle basis with a signed weight, whose mode runs against its own free energy at some states;
  an effective-charge net-flow law, the basis law with a wrong sign and a planted factored
  evaluation (S - 0.05) are refused;
- Wegscheider at the definition: a diagram whose constants are off by 1e-9 is refused;
- availability schedules (D228 item 5): `transporter_controls` parses, writes back and reads back
  to the same schedule, its breakpoint a step boundary; without the key there is no schedule and
  the change records are today's, by value and type; it is refused with its reason (an unknown or
  repeated population, a value outside [0, 1], a breakpoint past the horizon, the key on version
  1's layout); the held value is right-continuous (planted: a left-continuous read), J+ scales
  with it, and a breakpoint to 0 stops the cycles there, every ledger closing; in every kinetic
  form (neutral and charged factored, diagram, net flow) a held availability is the capacity
  times it, and 0 runs no cycle;
- the sodium-calcium exchange (its section): the registered law meets its rate equation, its
  reversal, its stoichiometry and charge at both ends, detailed balance with a heat that is never
  negative, its slopes and its one-sided domain against 60-digit decimals; each of 14 plants misses
  exactly its criteria; a closed world's steps close every ledger both ways; its charge slope holds
  the step; its refusals; a closure's free calcium; a restart from the checkpoint file (its worlds
  are stepped in NumPy, and one evaluation is jitted: no world compiles);
- M2 (amendment 2): log, exp, expm1 and log1p within 1, 2, 4 and 2 ulp under jit on this device and
  in NumPy, against 60-digit decimals.
"""

import contextlib
import copy
import dataclasses
import functools
import math
from decimal import Decimal, localcontext

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.definitions.surface_pump_v3_spec import control_values
from cells.execution.errors import NumericalError
from cells.kinds import transporter
from cells.laws.electrochemistry import CHARGE_PER_FMOL, F, R
from cells.laws.cycles import forms
from cells.laws.cycles import sodium_calcium_exchange_symmetric_barrier as na_ca
from cells.laws.cycles.forms import CycleForm, Diagram, FluxTerm, Saturation
from cells.models import surface_pump_v3
from cells.registry import kind_registry
from cells.registry import laws as law_registry
from cells.registry.models import get_model
from tests.unit import test_cycle_forms as tf
from tests.unit import test_transporter_kind as tk
from validation.tissue import pump_water_fixtures as water_fixtures

EPS = np.finfo(float).eps
U = EPS / 2


# ------------------------------------------------------------------ worlds and laws


def general(entry, *, role=None, n_end="a"):
    """A version-1 entry written in the general form (statement 1, §1's map)."""
    params = dict(
        stoichiometry=entry["stoichiometry"],
        km_role_mM=entry["km_role_mM"],
        km_atp_mM=entry["km_atp_mM"],
    )
    proton = entry["law"] == transporter.PROTON_LAW
    if proton:
        params |= dict(ph_ref=entry["fuel"]["ph_ref"], ph_band=entry["fuel"]["ph_band"])
    rows = entry["fuel"]["rows"]
    name = role or ("proton" if proton else "role")
    held = entry["fuel"]["kind"] == transporter.HELD
    return dict(
        id=entry["id"],
        host=entry["patch"],
        law=entry["law"],
        orientation={"N": n_end},
        capacity_fmol_s=entry["capacity_fmol_s"],
        roles={name: entry["role"], "ATP": rows[0], "ADP": rows[1], "Pi": rows[2]},
        parameters=params,
        held_rows=[["ATP", "N"], ["ADP", "N"], ["Pi", "N"]] if held else [],
    )


def add_species(raw, sid, valence, mu_RT, mM):
    """raw with species sid (valence, mu°/RT at the world's c0) at {node: mM}, impermeant, its
    charge compensated in each node's fixed charge so the field starts where it did."""
    m = raw["model"]
    m["species"].append(dict(id=sid, valence=valence, standard_mu_RT=mu_RT))
    for node in (*m["cells"], *m["extracellular"]):
        amount = node["volume_pL"] * mM.get(node["id"], 1e-6)
        node["initial_amount_fmol"][sid] = amount
        node["fixed_charge_equivalent_fmol"] -= valence * amount
    for patch in m["membranes"]:
        patch["permeability_m_per_s"][sid] = 0.0
    raw["execution"]["material_balance_atol_fmol"][sid] = 1e-15
    return raw


SLIP = law_registry.CycleLaw(
    "seamtest.slip_exchanger@1",
    (),
    (),
    None,
    None,
    cycle=tf.slip_form(),
    host=transporter.KIND_ID,
    provenance="calibrated",
    source="a test-only diagram (tests/unit/test_cycle_forms.py), never shipped",
)
OFFSET = law_registry.CycleLaw(
    "seamtest.shifted_exchange@1",
    (),
    (),
    None,
    None,
    cycle=CycleForm(
        kinetics="net_flow",
        roles=(("X", 1), ("Y", 0)),
        rows=(("X", "N"), ("X", "P"), ("Y", "N"), ("Y", "P")),
        modes=(("exchange", (-1, 1, 1, -1)),),
        flux_terms=((FluxTerm(1.0, (-1, 1, 1, -1), 0.2),),),
    ),
    host=transporter.KIND_ID,
    provenance="calibrated",
    source="a test-only net-flow law with an effective-charge error, never shipped",
)
HONEST = dataclasses.replace(
    OFFSET,
    law_id="seamtest.net_exchange@1",
    cycle=OFFSET.cycle._replace(flux_terms=((FluxTerm(1.0, (-1, 1, 1, -1), 0.0),),)),
)
AT_P = law_registry.CycleLaw(
    "seamtest.chemistry_at_p@1",
    (),
    (),
    None,
    None,
    cycle=CycleForm(
        kinetics="factored",
        roles=(("Z", 0), ("W", 0)),
        rows=(("Z", "N"), ("Z", "P"), ("W", "P")),
        modes=(("cyc", (-1, 1, 1)),),
        saturation=((Saturation(("Z", "N"), 1.0, 1),),),
    ),
    host=transporter.KIND_ID,
    provenance="calibrated",
    source="a test-only law converting at P, refused in this pass (Q3)",
)
BASIS_ROWS = (("X", "N"), ("X", "P"), ("Y", "N"), ("Y", "P"))
CYCLE_A, CYCLE_B = (-1, 1, 0, 0), (0, 0, -1, 1)  # X, then Y, from N to P.
CYCLE_C = (-1, 1, 1, -1)  # C = A - B: X from N to P against Y from P to N.


def basis_law(law_id, sign, k=(0.02, 0.01, 0.4)):
    """Cycles A, B and C = A - B booked in the basis {A, B}: mode A runs J_A + J_C and mode B runs
    J_B + sign J_C, each J_x = k_x (1 - e^(x_x)) dissipative alone. With sign = -1 (a signed weight)
    sum_m J_m x_m = J_A x_A + J_B x_B + J_C x_C <= 0, though mode B may run against its own x_B;
    sign = +1 books C into B with the wrong sign, adding J_C (x_A + x_B) - J_C x_C, which the large
    k_C drives positive wherever |x_A| < |x_B|."""
    k_a, k_b, k_c = k
    return law_registry.CycleLaw(
        law_id,
        (),
        (),
        None,
        None,
        cycle=CycleForm(
            kinetics="net_flow",
            roles=(("X", 1), ("Y", 0)),
            rows=BASIS_ROWS,
            modes=(("A", CYCLE_A), ("B", CYCLE_B)),
            flux_terms=(
                (FluxTerm(k_a, CYCLE_A), FluxTerm(k_c, CYCLE_C)),
                (FluxTerm(k_b, CYCLE_B), FluxTerm(sign * k_c, CYCLE_C)),
            ),
        ),
        host=transporter.KIND_ID,
        provenance="calibrated",
        source="a test-only net-flow law booked in a cycle basis, never shipped",
    )


SIGNED = basis_law("seamtest.signed_basis@1", -1)
WRONG_SIGN = basis_law("seamtest.wrong_sign_basis@1", +1)
TEST_LAWS = (SLIP, OFFSET, HONEST, AT_P, SIGNED, WRONG_SIGN)


@contextlib.contextmanager
def scoped(*kinds):
    """The transporter (and kinds) in a test kind registry, the test laws in a test law registry."""
    with tk.scoped(*kinds), law_registry.scope(law_registry.BUILTIN.extended(*TEST_LAWS)):
        yield


def start(spec):
    structure = surface_pump_v3.structure(spec.model)
    state, p = surface_pump_v3.initial_values(spec, structure=structure)
    controls = control_values(spec, [0.0])
    control = type(controls)(*(v[0] for v in controls))
    return structure, state, p, control


def potentials_for(p, cell=0.0, outside=0.0):
    out = np.full(p.active.size + p.outside_active.size, outside)
    out[: p.active.size] = cell
    return out


def exchange_world(*populations, x=(12.0, 140.0), w=(0.8, 0.2)):
    """Heredity cell D (held_world's Y, ATP, ADP, Pi) with X+ and W (registry potentials), and the
    populations; the exchanger's neutral role Y binds W."""
    raw = tk.held_world(*populations)
    add_species(raw, "X", 1, -2.0, {"cell_0": x[0], "bath_0": x[1]})
    add_species(raw, "W", 0, 1.5, {"cell_0": w[0], "bath_0": w[1]})
    return raw


def exchanger(law="seamtest.slip_exchanger@1", capacity=0.05, **over):
    entry = dict(
        id="exchanger_0",
        host="membrane_0",
        law=law,
        orientation={"N": "a"},
        capacity_fmol_s=capacity,
        roles={"X": "X", "Y": "W"},
        parameters={},
        held_rows=[],
    )
    entry.update(over)
    return entry


# ------------------------------------------------------------------ selection (§1)


def test_version_1_form_keeps_todays_entry_fields_and_hooks():
    with scoped():
        spec = parse_spec(tk.held_world())
        ((kind_id, entry),) = surface_pump_v3.structure(spec.model).kinds
    assert entry == ((transporter.NEUTRAL_LAW,), (transporter.HELD,))  # Today's plain tuple.
    bound = kind_registry.bound(transporter.TRANSPORTER, entry)
    assert bound.state_axes == transporter.STATE_AXES
    assert bound.layout_fields == transporter.LAYOUT_FIELDS
    assert bound.control_fields == transporter.CONTROL_FIELDS
    assert bound.readout_columns == transporter.READOUT_COLUMNS
    assert bound.material_term is None and bound.view_sets is None  # Today's hooks, exactly,
    # with role_species, §5.2's admission's reading, which both layouts carry (host-side), the
    # schedule's two definition-time hooks (D228 item 5): parse_schedule returns None without its
    # key and refuses it on version 1's layout, so its programs and change records are today's;
    # and FR-42's two (D303 item 6), traced only where rows are labelled.
    hooks = [f.name for f in dataclasses.fields(bound) if callable(getattr(bound, f.name))]
    assert sorted(hooks) == sorted(
        ["parse", "to_dict", "structure_entry", "initial", "control_values", "rates",
         "stage_term", "bound_rate", "held_rows", "ledger_terms", "domain", "readouts",
         "moved_rows", "check_definition", "role_species", "parse_schedule", "schedule_to_dict",
         "label_refusals", "label_transfers"]
    )  # fmt: skip
    # Planted: an entry that keeps the axis's hooks gives version 1 a material_term.
    def keeps(entry):
        return transporter.declared_fields(entry)._replace(without=())

    planted = dataclasses.replace(transporter.TRANSPORTER, declared_fields=keeps)
    assert kind_registry.bound(planted, entry).material_term is not None


def test_the_general_form_and_both_diversions_take_the_population_axis_and_write_back():
    pump = tk.population()
    with scoped():
        for raw in (
            tk.held_world(general(pump)),
            tk.held_world(pump, tk.population(id="transporter_1", capacity_fmol_s=0.05)),
            tk.held_world(tk.population(fuel=tk.fuel(kind=transporter.FINITE))),
            tk.held_world(pump, dict(general(pump), id="transporter_1")),
        ):
            spec = parse_spec(copy.deepcopy(raw))
            ((_, entry),) = surface_pump_v3.structure(spec.model).kinds
            assert isinstance(entry, transporter.CycleAxis), raw["model"]["transporters"]
            declaration = dict(spec.model.kinds)[transporter.KIND_ID]
            assert transporter.to_dict(declaration) == raw["model"]["transporters"]
            # Exact types too, so a definition's bytes are kept: an int stays an int.
            for a, b in zip(transporter.to_dict(declaration), raw["model"]["transporters"], strict=True):
                assert repr(a) == repr(b)
        with pytest.raises(ConfigError, match="runs on held fuel"):  # Today's refusal, unchanged.
            finite = tk.fuel(kind=transporter.FINITE)
            parse_spec(tk.held_world(tk.population(law=transporter.PROTON_LAW, role="Na", fuel=finite)))


@pytest.mark.parametrize(
    "over,reason",
    [
        (dict(host="nowhere"), "a host is a membrane patch"),
        (dict(orientation={"N": "c"}), "orientation is"),
        (dict(roles={"role": "Y"}), "roles binds each of"),
        (dict(roles={"role": "Y", "ATP": "ATP", "ADP": "ATP", "Pi": "Pi"}), "distinct species"),
        (dict(parameters=dict(stoichiometry=5, km_role_mM=1.0, km_atp_mM=0.1)), "is at most 4"),
        (dict(parameters=dict(stoichiometry=1.5, km_role_mM=1.0, km_atp_mM=0.1)), "is an integer"),
        (dict(held_rows=[["ATP", "P"]]), "held_rows lists distinct rows"),
        (dict(held_rows=[["ATP", "N"]]), "held together or moved together"),
        (dict(law="cells.proton_atp_mass_action_positive@1"), "roles binds each of proton"),
        (dict(proton_readout="Y"), "proton_readout names the model's free-proton species row"),
        (dict(proton_readout="nowhere"), "proton_readout names the model's free-proton"),
    ],
)
def test_the_general_parse_refuses_with_its_reason(over, reason):
    entry = dict(general(tk.population()), **over)
    with scoped(), pytest.raises(ConfigError, match=reason):
        parse_spec(tk.held_world(entry))


def test_the_general_parse_refuses_a_charged_held_row_chemistry_at_p_and_moved_proton_fuel():
    base = general(tk.population(**tk.PUMP, fuel=tk.fuel(ph_ref=7.2, ph_band=0.05)))
    with scoped(*tk.CHARGED_KINDS):
        world = tk.charged_world()
        world["model"]["transporters"] = [dict(base, held_rows=[["proton", "N"], *base["held_rows"]])]
        with pytest.raises(ConfigError, match="a held row is neutral in this pass"):
            parse_spec(world)
        world["model"]["transporters"] = [dict(base, held_rows=[])]
        with pytest.raises(ConfigError, match="runs on held fuel"):
            parse_spec(world)
    raw = tk.held_world()
    raw = tk.held_world(
        dict(id="p_0", host="membrane_0", law="seamtest.chemistry_at_p@1", orientation={"N": "a"},
             capacity_fmol_s=0.1, roles={"Z": "Y", "W": "ATP"}, parameters={}, held_rows=[])
    )  # fmt: skip
    with scoped():  # Chemistry at P (Q3's refusal until K3) is admitted; its rows are neutral,
        ((_, entry),) = surface_pump_v3.structure(parse_spec(raw).model).kinds  # so no K3b field.
    assert entry == transporter.CycleAxis(("seamtest.chemistry_at_p@1",))
    with scoped(), pytest.raises(ConfigError, match="must be unique"):
        parse_spec(tk.held_world(general(tk.population()), general(tk.population())))


# ------------------------------------------------------------------ the layouts agree (condition 2)

STEPS = 8
X_MAX = 80.0  # The bounds' largest X, read from the probe at both ends of the steps.
RHO_MAX = 1.1  # Their largest one-way scale per net flux, (J+ + J-) / |J|, read the same way.
ROWS = 5  # K: the role at both ends and the three fuel rows, for both laws.


def stepped(raw, kinds=(), steps=STEPS):
    """(spec, the initial state, the state after `steps` of @3's own IMEX step on the host in
    NumPy, each valid, the layout, the control)."""
    with scoped(*kinds):
        spec = parse_spec(copy.deepcopy(raw))
        impl = get_model(spec.model)
        first, p = impl.initial_values(spec)
        assert p.imex_explicit.shape[0] > 0  # A declared tableau: the runner's checked step.
        control = impl.Control(*(v[0] for v in control_values(spec, [0.0])))
        state = first
        for _ in range(steps):
            state, valid = impl.imex_step(state, spec.execution.dt, control, p, xp=np)
            assert bool(valid)
    return spec, first, state, p, control


def probed(spec, state, p, control, kinds):
    """The probe at a state, at its own potentials (@3's readouts) and read."""
    from cells.kinds import proton_buffer

    with scoped(*kinds):
        structure = surface_pump_v3.structure(spec.model)
        values = surface_pump_v3.readouts(state, control, p, xp=np, structure=structure)
        read = proton_buffer.stage_read(state, p, xp=np)[0] if kinds else state
        return transporter.probe(read, values.field.potential_V, control, p, xp=np)


@pytest.mark.parametrize("charged", (False, True), ids=("neutral", "charged"))
def test_the_layouts_agree_over_steps_within_their_rounding(charged):
    raw, kinds = (tk.charged_world(), tk.CHARGED_KINDS) if charged else (tk.held_world(), ())
    twin = copy.deepcopy(raw)
    twin["model"]["transporters"] = [general(raw["model"]["transporters"][0])]
    _, _, a, _, _ = stepped(raw, kinds)
    spec, first, b, p, control = stepped(twin, kinds)
    for state in (first, b):  # The bounds' premises, read rather than assumed.
        modes = probed(spec, state, p, control, kinds).modes
        assert float(np.max(modes.x_terms[:, 0])) <= X_MAX
        assert float(np.max((modes.j_plus + modes.j_minus)[:, 0] / np.abs(modes.j[:, 0]))) <= RHO_MAX
    cycles_a = float(a.transporter_cycles[0])
    cycles_b = float(b.cycle_count[0, 0])
    # The bound, derived (statement 1, amendment 2): at every stage each layout's J is within
    # ((K + 10) X + 14) u of the exact, relative to its one-way scale J+ + J- <= RHO_MAX |J| (x's
    # error through e^x, and J+'s own exp and logs); the two layouts differ by twice that, and over
    # the STEPS steps (their increments, and each step's effect on the next one's state) by at most
    # STEPS times it relative to the cycles, since J keeps its sign.
    bound = STEPS * 2 * U * ((ROWS + 10) * X_MAX + 14) * RHO_MAX * abs(cycles_a)
    assert cycles_a != 0 and abs(cycles_a - cycles_b) <= bound, (cycles_a, cycles_b, bound)
    n = float(np.max(np.abs(p.cycle_nu)))  # The most of one row a cycle moves.
    for name in ("amount_increment", "extracellular_amount_increment", "reservoir_supplied"):
        x, y = getattr(a, name), getattr(b, name)
        assert float(np.max(np.abs(x - y))) <= n * bound, name
    # Heat and work, 1e-3 RT J x per stage (x the free energy or the held rows' drive): x within
    # (K + 1) u X of the exact and the product within 2 u, so each layout's within
    # u |J| X (((K + 10) X + 14) RHO_MAX + K + 3) of the exact, twice that apart, over STEPS steps.
    rt = 1e-3 * R * spec.model.temperature_K
    energy = STEPS * 2 * U * X_MAX * (((ROWS + 10) * X_MAX + 14) * RHO_MAX + ROWS + 3) * rt * abs(cycles_a)
    for v1, axis in (
        ("transporter_dissipated_energy_pJ", "cycle_dissipated_energy_pJ"),
        ("transporter_metabolic_work_pJ", "cycle_metabolic_work_pJ"),
    ):
        x, y = float(getattr(a, v1)[0]), float(getattr(b, axis)[0])
        assert x != 0 and abs(x - y) <= energy, (v1, x, y, energy)
    # Planted: a capacity 1e-9 larger on one side moves its cycles far outside the bound.
    planted = copy.deepcopy(twin)
    planted["model"]["transporters"][0]["capacity_fmol_s"] *= 1 + 1e-9
    _, _, c, _, _ = stepped(planted, kinds)
    assert abs(cycles_a - float(c.cycle_count[0, 0])) > 100 * bound
    heat_a, heat_c = float(a.transporter_dissipated_energy_pJ[0]), float(c.cycle_dissipated_energy_pJ[0])
    assert abs(heat_a - heat_c) > energy  # And its heat outside the heat's.


def test_the_probe_agrees_between_the_layouts_at_the_start():
    """The probe on version 1's layout and on the general form of the same world: x, S, J+, J-, J,
    heat, work, the charge moved and the conductance agree to rounding, for both of the laws."""
    from cells.kinds import proton_buffer

    for raw, kinds, volts in (
        (tk.held_world(), (), 0.0),
        (tk.charged_world(), tk.CHARGED_KINDS, -0.07),
    ):
        twin = copy.deepcopy(raw)
        twin["model"]["transporters"] = [general(raw["model"]["transporters"][0])]
        out = []
        with scoped(*kinds):
            for world in (raw, twin):
                spec = parse_spec(copy.deepcopy(world))
                _, state, p, control = start(spec)
                read = proton_buffer.stage_read(state, p, xp=np)[0] if kinds else state
                out.append(transporter.probe(read, potentials_for(p, volts), control, p, xp=np))
        one, two = out
        slot = 0  # The population's patch, membrane_0: slot 0 on version 1, population 0 here.
        for name in ("x", "s", "j_plus", "j_minus", "j"):
            a, b = float(getattr(one.modes, name)[0, slot]), float(getattr(two.modes, name)[0, 0])
            assert a == pytest.approx(b, rel=64 * U * 80, abs=1e-300), name
        for name in ("heat_pJ_s", "work_pJ_s", "charge_a_to_b_fmol_s", "conductance_pS"):
            a = float(getattr(one.populations, name)[slot])
            b = float(getattr(two.populations, name)[0])
            assert a == pytest.approx(b, rel=64 * U * 80, abs=1e-300), name


def test_the_population_axis_step_terms_are_version_1s_for_the_proton_law():
    with scoped(*tk.CHARGED_KINDS):
        v1 = parse_spec(tk.charged_world())
        raw = tk.charged_world()
        raw["model"]["transporters"] = [general(raw["model"]["transporters"][0])]
        gen = parse_spec(raw)
        rates = []
        for spec in (v1, gen):
            _, state, p, control = start(spec)
            from cells.kinds import proton_buffer

            read, ok = proton_buffer.stage_read(state, p, xp=np)
            assert bool(ok)
            bare = transporter.stage_term(read, None, control, p, xp=np)
            shaped = transporter.stage_term(read, potentials_for(p, -0.07), control, p, xp=np)
            bound = transporter.bound_rate(spec, dict(spec.model.kinds)[transporter.KIND_ID])
            rates.append((bare, shaped, bound))
    (b1, s1, r1), (b2, s2, r2) = rates
    np.testing.assert_allclose(b2, b1, rtol=64 * U * 100, atol=0.0)
    np.testing.assert_allclose(s2, s1, rtol=64 * U * 100, atol=0.0)
    assert r2 == pytest.approx(r1, rel=1e-13, abs=0)
    # Planted: a held row's steep saturation (the proton law's ATP factor at Hill 4, K 1e100 mM)
    # makes (K/c)^h overflow a float, which raised OverflowError; the bound, in log space, admits
    # it with that population's term at e^(-huge) = 0 (D148's recorded widening).
    form = transporter.PROTON.cycle
    steep_factors = (form.saturation[0][0], Saturation(("ATP", "N"), "km_atp_mM", 4))
    steep = dataclasses.replace(
        transporter.PROTON,
        law_id="tests.steep_fuel@1",
        cycle=form._replace(saturation=(steep_factors,)),
    )
    raw = tk.charged_world()
    entry = general(raw["model"]["transporters"][0])
    entry["law"], entry["parameters"]["km_atp_mM"] = "tests.steep_fuel@1", 1e100
    raw["model"]["transporters"] = [entry]
    with tk.scoped(*tk.CHARGED_KINDS), law_registry.scope(law_registry.BUILTIN.extended(steep)):
        spec = parse_spec(raw)
        assert transporter.bound_rate(spec, dict(spec.model.kinds)[transporter.KIND_ID]) == 0.0


# ------------------------------------------------------------------ finite fuel's population
# Its run, beside an exchanger on one patch: tests/unit/test_cycle_kind_runs.py.


FINITE_POP = dict(
    id="fuel_pump_0",
    host="membrane_0",
    law="cells.atp_driven_transporter_mass_action_positive@1",
    orientation={"N": "a"},
    capacity_fmol_s=0.1,
    roles={"role": "Y", "ATP": "ATP", "ADP": "ADP", "Pi": "Pi"},
    parameters=dict(stoichiometry=1, km_role_mM=1.0, km_atp_mM=0.1),
    held_rows=[],
)


# ------------------------------------------------------------------ N = b, and the probe


def test_n_at_b_takes_the_role_from_the_outside_node_and_turns_the_voltage_term():
    a = general(tk.population(id="t_a"))
    b = general(tk.population(id="t_b"), n_end="b")
    b["held_rows"] = [["ATP", "N"], ["ADP", "N"], ["Pi", "N"]]
    with scoped():
        spec = parse_spec(tk.held_world(a, b))
        _, state, p, control = start(spec)
    pr = transporter.probe(state, potentials_for(p, -0.05, 0.0), control, p, xp=np)
    m = spec.model
    ids, cell, bath = list(m.species_ids), m.cells[0], m.extracellular[0]

    def conc(node, row):
        return node.initial_amount_fmol[ids.index(row)] / node.volume_pL

    for j, (n_node, p_node) in enumerate(((cell, bath), (bath, cell))):
        drive = tk.DRIVE0_J_MOL / (R * m.temperature_K) + math.log(
            conc(n_node, "ADP") * conc(n_node, "Pi") / (conc(n_node, "ATP") * 1000.0)
        )
        x = drive + math.log(conc(p_node, "Y") / conc(n_node, "Y"))
        assert float(pr.modes.x[0, j]) == pytest.approx(x, rel=1e-12, abs=1e-12)
        s = 1.0 / (1.0 + 1.0 / conc(n_node, "Y")) / (1.0 + 0.1 / conc(n_node, "ATP"))
        assert float(pr.modes.s[0, j]) == pytest.approx(s, rel=1e-12, abs=0)
    rows = pr.rows.rate[:, 1]  # N = b: the role leaves the bath and enters the cell.
    j = float(pr.modes.j[0, 1])  # Each row is its nu times J, summed over the modes: within 4 u.
    assert rows[0] == pytest.approx(-j, rel=4 * U, abs=0) and rows[1] == pytest.approx(j, rel=4 * U, abs=0)


def test_the_probe_is_the_runs_own_arithmetic_with_its_slopes_against_differences():
    with scoped():
        spec = parse_spec(exchange_world(exchanger(), FINITE_POP))
        _, state, p, control = start(spec)
    v = potentials_for(p, -0.06, 0.0)
    pr = transporter.probe(state, v, control, p, xp=np)
    r = transporter.rates(state, v, control, p, xp=np)
    np.testing.assert_array_equal(r.derivatives["cycle_count"], pr.modes.j)
    # The solver's own switch (the third review's finding 4): on a closed patch J is zero, and so
    # are the diagram's population-scaled fields, which read its carriers (planted: k a alone).
    closed = p._replace(membrane_active=np.zeros_like(np.asarray(p.membrane_active)))
    off = transporter.probe(state, v, control, closed, xp=np)
    assert not np.any(off.modes.j) and not np.any(off.edges.net_fmol_s)
    assert not np.any(np.nan_to_num(off.modes.j_minus_diagram))
    # The diagram's carriers read k a as the material path does (the Lean project's eight-state
    # finding): at this world's k a, the formula before the fix, bit for bit; at k a = 1e-302 the
    # reverse cycle flux is the material J-, where the old floor at 1e-300 read it 100 times over.
    diagram = transporter._evaluate(state, v, control, p, xp=np).diagram
    dg = (p.cycle_form == transporter.FORM_CODES["diagram"])[None, :] & p.cycle_mode_present
    per_carrier = np.exp(diagram.log_minus + diagram.log_share)

    def floored(ka):
        return np.exp(np.log(np.maximum(ka, 1e-300)) - p.cycle_dg_log_scale)[None, :] * per_carrier

    ka = p.cycle_capacity_fmol_s * control.cycle_availability
    np.testing.assert_array_equal(pr.modes.j_minus_diagram[dg], floored(ka)[dg])
    low = p._replace(cycle_capacity_fmol_s=np.full_like(p.cycle_capacity_fmol_s, 1e-302))
    tiny = transporter.probe(state, v, control, low, xp=np)
    np.testing.assert_allclose(tiny.modes.j_minus_diagram[dg], tiny.modes.j_minus[dg], rtol=1e-9)
    planted = floored(1e-302 * control.cycle_availability)[dg] / tiny.modes.j_minus[dg]
    np.testing.assert_allclose(planted, 100.0, rtol=1e-9)
    fd_modes = p.cycle_form[None, :] != transporter.FORM_CODES["net_flow"]
    on = fd_modes & p.cycle_mode_present
    gap = np.abs(np.where(on, pr.modes.j_plus - pr.modes.j_minus - pr.modes.j, 0.0))
    assert np.all(gap <= 8 * U * np.where(on, pr.modes.j_plus + pr.modes.j_minus, 0.0))
    rt = R * spec.model.temperature_K
    np.testing.assert_allclose(r.heat_pJ_s, -1e-3 * rt * np.sum(pr.modes.j * pr.modes.x, axis=0), rtol=1e-14)
    # The conductance against central differences of the current in V (both populations' sum).
    def current(volts):
        q = transporter.probe(state, potentials_for(p, volts, 0.0), control, p, xp=np)
        return np.sum(q.populations.current_a_to_b_pA)

    h = 1e-6
    slope = (current(-0.06 + h) - current(-0.06 - h)) / (2 * h)  # pA/V = pS
    total = float(np.sum(np.abs(pr.populations.conductance_pS)))
    assert abs(abs(slope) - total) <= 1e-6 * total + 1e-12, (slope, total)
    # Planted: a conductance without the charge's second factor (q, not q^2) is off.
    assert abs(abs(slope) - total / 2) > 1e-3 * total


# ------------------------------------------------------------------ the guard (§5.2)


def evaluate_guard(raw, volts, *, plant=None):
    with scoped():
        spec = parse_spec(raw)
        _, state, p, control = start(spec)
    evaluate = jax.jit(lambda s, v, c, q: transporter._evaluate(s, v, c, q, xp=jnp))
    arrays = jax.tree.map(jnp.asarray, (state, control, p))
    out = []
    for volt in volts:
        e = evaluate(arrays[0], jnp.asarray(potentials_for(p, volt, 0.0)), arrays[1], arrays[2])
        out.append((np.asarray(e.guard), np.asarray(e.allowance), np.asarray(e.valid), np.asarray(e.x)))
    return out


def test_the_guard_holds_exactly_for_diagram_and_factored_populations():
    raw = exchange_world(exchanger(), FINITE_POP)
    # The exchanger's reversal (x = 3.84 - psi here, so at about +103 mV) lies in the sweep:
    # sweep V through it finely, under jit here.
    volts = np.linspace(-0.2, 0.2, 2001)
    xs = []
    for guard, _, valid, x in evaluate_guard(raw, volts):
        assert np.all(guard <= 0.0)
        assert np.all(valid)
        xs.append(x[0, 0])
    assert min(xs) < 0.0 < max(xs)  # The exchange mode's x changes sign inside the sweep.


def test_an_honest_net_flow_law_stays_within_the_allowance_and_an_offset_one_is_refused():
    honest = exchange_world(exchanger(law="seamtest.net_exchange@1", capacity=1.0))
    offset = exchange_world(exchanger(law="seamtest.shifted_exchange@1", capacity=1.0))
    with scoped():
        spec = parse_spec(honest)
        _, state, p, control = start(spec)
    # x = 0 where V equals the exchange's reversal; sweep finely around it.
    e0 = transporter.probe(state, potentials_for(p, 0.0, 0.0), control, p, xp=np)
    x0 = float(e0.modes.x[0, 0])
    v_rev = x0 * R * spec.model.temperature_K / (F * float(p.cycle_charge_moved[0, 0]))
    volts = v_rev + np.concatenate([np.linspace(-1e-3, 1e-3, 801), [0.0, 1e-15, -1e-15]])
    near = evaluate_guard(honest, volts)
    for guard, allowance, valid, _ in near:
        assert guard[0] <= allowance[0] and valid[0]
    # The offset law runs against its free energy between x = 0 and x = -0.2 psi: refused there.
    refused = [not bool(valid[0]) for _, _, valid, _ in evaluate_guard(offset, volts)]
    assert any(refused)
    margins = [g[0] / a[0] for g, a, v, _ in evaluate_guard(offset, volts) if not v[0]]
    assert min(margins) > 1.0


def test_a_signed_cycle_basis_is_admitted_and_silent_and_its_wrong_sign_is_refused():
    """A net-flow law booked in a cycle basis (a signed weight, J_B - J_C) is admitted, and the
    guard stays silent at every swept state, though mode B runs against its own free energy at
    some of them; each mode's one-way scale is its terms' own, with |w|; the same law with C booked
    into B with the wrong sign breaks sum J x <= 0, and the guard refuses it there, by a margin."""
    signed = exchange_world(exchanger(law=SIGNED.law_id, capacity=1.0))
    wrong = exchange_world(exchanger(law=WRONG_SIGN.law_id, capacity=1.0))
    # x_A = ln(140/12) - F V / RT and x_B = ln(0.2/0.8): |x_A| < |x_B| for V in about 29-103 mV.
    volts = np.linspace(-0.2, 0.2, 801)
    for guard, allowance, valid, _ in evaluate_guard(signed, volts):
        assert guard[0] <= allowance[0] and valid[0]
    with scoped():
        spec = parse_spec(signed)
        _, state, p, control = start(spec)
    against = []
    for volt in volts[::8]:
        modes = transporter.probe(state, potentials_for(p, volt, 0.0), control, p, xp=np).modes
        against.append(float(modes.j[1, 0] * modes.x[1, 0]) > 0.0)  # Mode B against its own x_B.
    assert any(against)
    # Each mode's one-way scale is its terms' own, k a sum_t |w_t| (1 + e^(y_t)), with y_A = x_A,
    # y_B = x_B and y_C = x_A - x_B here (planted: the signed sum, which a negative weight shrinks).
    modes = transporter.probe(state, potentials_for(p, 0.05, 0.0), control, p, xp=np).modes
    k_a, k_b, k_c = 0.02, 0.01, 0.4
    ka = float(p.cycle_capacity_fmol_s[0] * control.cycle_availability[0])
    x_a, x_b = float(modes.x[0, 0]), float(modes.x[1, 0])
    expected = (
        ka * (k_a * (1 + math.exp(x_a)) + k_c * (1 + math.exp(x_a - x_b))),
        ka * (k_b * (1 + math.exp(x_b)) + abs(-k_c) * (1 + math.exp(x_a - x_b))),
    )
    for m, phi in enumerate(expected):
        assert float(modes.scale[m, 0]) == pytest.approx(phi, rel=64 * U, abs=0), m
    refused = [(g[0], a[0]) for g, a, v, _ in evaluate_guard(wrong, volts) if not v[0]]
    assert refused and min(g / a for g, a in refused) > 1.0


def test_a_planted_factored_evaluation_is_refused_by_the_guard(monkeypatch):
    """S - 0.05 injected into the factored flux (the lead's substitution for the unrepresentable
    negative S): where S < 0.05 the flux runs against x, and the guard refuses."""
    raw = tk.held_world(FINITE_POP)
    original = forms.sign_exact_flux

    def planted(log_plus, x, *, xp=jnp):
        return (xp.exp(log_plus) - 0.05 * 0.1) * -xp.expm1(x)  # k S - k 0.05 with k = 0.1

    with scoped():
        spec = parse_spec(raw)
        _, state, p, control = start(spec)
        clean = transporter._evaluate(state, potentials_for(p, -0.05), control, p, xp=np)
        assert bool(clean.valid[0]) and float(clean.guard[0]) <= 0.0
        monkeypatch.setattr(forms, "sign_exact_flux", planted)
        # Starve the role so S < 0.05 at the cell: its read goes through the state's increment.
        ids = list(spec.model.species_ids)
        y = ids.index("Y")
        low = state.amount_increment.copy()
        low[y, 0] = -p.amount_reference[y, 0] * (1 - 1e-3)
        e = transporter._evaluate(state._replace(amount_increment=low), potentials_for(p, -0.05), control, p, xp=np)
        assert float(e.guard[0]) > float(e.allowance[0]) and not bool(e.valid[0])
    monkeypatch.setattr(forms, "sign_exact_flux", original)


# ------------------------------------------------------------------ Wegscheider at the definition


def test_an_inconsistent_diagram_is_refused_at_the_definition():
    form = tf.slip_form()
    edges = form.diagram.edges
    off = (edges[0]._replace(forward=edges[0].forward._replace(k0_per_s=edges[0].forward.k0_per_s * (1 + 1e-9))), *edges[1:])
    bad = dataclasses.replace(
        SLIP, law_id="seamtest.slip_off@1", cycle=form._replace(diagram=form.diagram._replace(edges=off))
    )
    with tk.scoped(), law_registry.scope(law_registry.BUILTIN.extended(*TEST_LAWS, bad)):
        parse_spec(exchange_world(exchanger()))  # The consistent one is admitted.
        with pytest.raises(ConfigError, match="fails Wegscheider's condition"):
            parse_spec(exchange_world(exchanger(law="seamtest.slip_off@1")))


# ------------------------------------------------------- availability schedules (D228 item 5)

BREAK_S = 0.002  # A step boundary inside held_world's 4 ms.


def scheduled(entries=None, *population):
    """held_world's general-layout population, with `transporter_controls` where given."""
    raw = tk.held_world(*(population or (general(tk.population()),)))
    if entries is not None:
        raw["experiment"][transporter.SCHEDULE_KEY] = entries
    return raw


def series(*points):
    return [{"time": t, "availability": a} for t, a in points]


def test_an_availability_schedule_parses_writes_back_and_without_the_key_keeps_todays_records():
    from cells.definitions.surface_pump_v3_spec import KindChange

    entries = [dict(transporter_id="transporter_0", schedule=series((0.0, 1.0), (BREAK_S, 0.25)))]
    with scoped():
        spec = parse_spec(scheduled(entries))
        schedule = kind_registry.declared_schedule(spec, transporter.KIND_ID)
        assert schedule.series == (("transporter_0.availability", ((0.0, 1.0), (BREAK_S, 0.25))),)
        records = spec.experiment._held_availabilities()
        assert BREAK_S in [r.time for r in records]  # Its breakpoint: a step boundary.
        assert all(isinstance(r, KindChange) for r in records)
        written = spec.to_dict()["experiment"][transporter.SCHEDULE_KEY]
        assert written == entries  # Written back whole, and read back to the same schedule.
        again = parse_spec(spec.to_dict())
        assert kind_registry.declared_schedule(again, transporter.KIND_ID) == schedule
        # Without the key: no schedule, and the change records are today's, by value and type.
        plain = parse_spec(scheduled())
        assert kind_registry.declared_schedule(plain, transporter.KIND_ID) is None
        today = plain.experiment._held_availabilities()
        assert not any(isinstance(r, KindChange) for r in today)
        assert transporter.SCHEDULE_KEY not in plain.to_dict()["experiment"]


@pytest.mark.parametrize(
    "entries,population,reason",
    [
        ([dict(transporter_id="nobody", schedule=series((0.0, 1.0)))], None, "unknown transporter"),
        ([dict(transporter_id="transporter_0", schedule=series((0.0, 1.0)))] * 2, None, "twice"),
        ([dict(transporter_id="transporter_0", schedule=series((0.0, 1.5)))], None, r"\[0, 1\]"),
        ([dict(transporter_id="transporter_0", schedule=series((0.0, 1.0), (0.01, 0.5)))], None,
         "past the horizon"),
        ([dict(transporter_id="transporter_0", schedule=series((0.0, 1.0)))], "version 1",
         "version 1's layout holds each patch's availability at 1"),
    ],
)  # fmt: skip
def test_an_availability_schedule_refuses_with_its_reason(entries, population, reason):
    raw = scheduled(entries, *((tk.population(),) if population else ()))
    with scoped(), pytest.raises(ConfigError, match=reason):
        parse_spec(raw)


def test_the_held_availability_scales_j_and_a_breakpoint_to_zero_stops_the_cycles():
    entries = [dict(transporter_id="transporter_0", schedule=series((0.0, 1.0), (BREAK_S, 0.0)))]
    quarter = [dict(transporter_id="transporter_0", schedule=series((0.0, 0.25)))]
    with scoped():
        spec = parse_spec(scheduled(entries))
        impl = get_model(spec.model)
        state, p = impl.initial_values(spec)
        times = [0.0, 0.001, BREAK_S, 0.003]
        held = [float(v[0]) for v in control_values(spec, times).cycle_availability]
        # Right-continuous: the new value from its breakpoint on, the old one just before it (a
        # planted left-continuous read would give 1 at the breakpoint).
        assert held == [1.0, 1.0, 0.0, 0.0]
        before = control_values(spec, [BREAK_S - 1e-9]).cycle_availability
        assert float(before[0, 0]) == 1.0
        full = impl.Control(*(v[0] for v in control_values(spec, [0.0])))
        spec4 = parse_spec(scheduled(quarter))
        part = impl.Control(*(v[0] for v in control_values(spec4, [0.0])))
        one = transporter.probe(state, potentials_for(p), full, p, xp=np).modes
        four = transporter.probe(state, potentials_for(p), part, p, xp=np).modes
        # J+ = exp(ln k + ln a + ln S): within a few roundings of its exponent (as for k alone).
        allowed = 4 * EPS * (abs(math.log(float(one.j_plus[0, 0]))) + 4)
        expected = 0.25 * float(one.j_plus[0, 0])
        assert float(four.j_plus[0, 0]) == pytest.approx(expected, rel=allowed, abs=0)
        # The run's own rule: each step holds the value at its start (the change times).
        states = [state]
        for k in range(4):
            control = impl.Control(*(v[0] for v in control_values(spec, [k * spec.execution.dt])))
            state, valid = impl.imex_step(state, spec.execution.dt, control, p, xp=np)
            assert bool(valid)
            states.append(state)
        cycles = [float(np.sum(s.cycle_count)) for s in states]
        assert cycles[1] > 0 and cycles[2] > cycles[1]  # Available: the cycles run.
        assert cycles[2] == cycles[3] == cycles[4]  # Unavailable from the breakpoint: none.
        history = impl.STATE_TYPE(*(np.stack(v) for v in zip(*states, strict=True)))
        impl.check_values(history, spec, steps=np.arange(len(states)))  # Every ledger closes.


def _charged_general(**over):
    raw = tk.charged_world(**over)
    raw["model"][transporter.MODEL_KEY] = [general(e) for e in raw["model"][transporter.MODEL_KEY]]
    return raw


def _neutral(**over):
    return scheduled(None, general(tk.population(**over)))


def _net_flow(**over):
    return exchange_world(exchanger(law="seamtest.net_exchange@1", **over))


FORMS = {  # Each kinetic form's world, its population and the kinds it needs.
    "neutral factored": (_neutral, "transporter_0", ()),
    "charged factored": (_charged_general, "transporter_0", tk.CHARGED_KINDS),
    "diagram": (lambda **over: exchange_world(exchanger(**over)), "exchanger_0", ()),
    "net flow": (_net_flow, "exchanger_0", ()),
    "monomial": (lambda **over: na_ca_world(na_ca_entry(**over)), "exchanger_0", ()),
}


def four_steps(raw, kinds):
    """The states after four of @3's own IMEX steps at dt 1e-4 (a step every form admits), with
    every step valid and every ledger closing."""
    raw = copy.deepcopy(raw)
    raw["execution"]["dt"] = 1e-4
    with scoped(*kinds):
        spec = parse_spec(raw)
        impl = get_model(spec.model)
        state, p = impl.initial_values(spec)
        control = impl.Control(*(v[0] for v in control_values(spec, [0.0])))
        states = [state]
        for _ in range(4):
            state, valid = impl.imex_step(state, spec.execution.dt, control, p, xp=np)
            assert bool(valid)
            states.append(state)
        history = impl.STATE_TYPE(*(np.stack(v) for v in zip(*states, strict=True)))
        impl.check_values(history, spec, steps=np.arange(len(states)))
    return state


@pytest.mark.parametrize("form", list(FORMS))
def test_a_held_availability_is_the_capacity_times_it_in_every_kinetic_form(form):
    """The availability enters every form only through k a: a schedule at 0.3 gives the steps of
    the capacity times 0.3 with none (within J+'s log-space rounding, ln k + ln a against ln(k a)),
    and a schedule at 0 runs no cycle."""
    build, pid, kinds = FORMS[form]
    raw = build()
    (entry,) = raw["model"][transporter.MODEL_KEY]
    k = entry["capacity_fmol_s"]
    at = {}
    for a in (0.3, 0.0):
        given = copy.deepcopy(raw)
        given["experiment"][transporter.SCHEDULE_KEY] = [
            dict(transporter_id=pid, schedule=series((0.0, a)))
        ]
        at[a] = four_steps(given, kinds)
    scaled = four_steps(build(capacity_fmol_s=k * 0.3), kinds)
    cycles = float(np.sum(at[0.3].cycle_count))
    assert cycles != 0 and cycles == pytest.approx(
        float(np.sum(scaled.cycle_count)), rel=1e-12, abs=0
    )
    np.testing.assert_allclose(at[0.3].amount_increment, scaled.amount_increment, rtol=1e-12)
    assert float(np.sum(np.abs(at[0.0].cycle_count))) == 0.0  # Unavailable: no cycle at all.


# ------------------------------------------------------- the monomial form on the kind (K6)

# A closure-free monomial exchanger: X+ from N to P against Y from P to N, its S a monomial in X at
# N and Y at P with a voltage term, one saturating factor on X at N, and a share of 2.
MONO = law_registry.CycleLaw(
    "seamtest.monomial_exchange@1",
    (),
    (),
    None,
    None,
    cycle=CycleForm(
        kinetics="monomial",
        roles=(("X", 1), ("Y", 0)),
        rows=(("X", "N"), ("X", "P"), ("Y", "N"), ("Y", "P")),
        modes=(("exchange", (-1, 1, 1, -1)),),
        monomial=forms.MonomialForm((
            forms.MonomialRate(
                log_k=math.log(2.0),
                orders=((forms.Reference("X", "N"), 1.0), (forms.Reference("Y", "P"), 1.0)),
                zeta=0.5,
                factors=(forms.MonomialFactor(1.0, (
                    forms.MonomialTerm(10.0, ((forms.Reference("X", "N"), 1.0),)),
                )),),
                share=2,
            ),
        )),
    ),
    host=transporter.KIND_ID,
    provenance="calibrated",
    source="a test-only monomial law (K6), never shipped",
)  # fmt: skip


@contextlib.contextmanager
def mono_scoped(*laws):
    with tk.scoped(), law_registry.scope(law_registry.BUILTIN.extended(*TEST_LAWS, MONO, *laws)):
        yield


def mono_world():
    return exchange_world(exchanger(law=MONO.law_id))


def mono_probe(spec, state, p, control, potentials):
    return transporter.probe(state, potentials, control, p, xp=np)


def test_a_monomial_population_runs_its_closed_form_with_exact_row_slopes():
    with mono_scoped():
        spec = parse_spec(mono_world())
        structure, state, p, control = start(spec)
        entry = dict(structure.kinds)[transporter.KIND_ID]
        bound = kind_registry.bound(transporter.TRANSPORTER, entry)
        assert set(transporter.MONOMIAL_FIELDS) <= set(bound.layout_fields)
        volts = -0.03
        potentials = potentials_for(p, volts)
        e = transporter._evaluate(state, potentials, control, p, xp=np)
    ids = list(spec.model.species_ids)
    cell, bath = spec.model.cells[0], spec.model.extracellular[0]

    def c(node, s):
        return node.initial_amount_fmol[ids.index(s)] / node.volume_pL

    a_x, a_y = c(cell, "X") / 1000.0, c(bath, "W") / 1000.0  # N is the cell; activities at 1 M.
    psi = F * volts / (R * spec.model.temperature_K)
    x = float(e.x[0, 0])
    log_s = math.log(2.0 * a_x * a_y) + 0.5 * psi - math.log1p(10.0 * a_x)
    log_s -= math.log(1.0 + math.exp(x / 2))  # The share, n = 2.
    terms = abs(math.log(2.0 * a_x * a_y)) + abs(0.5 * psi) + 2 + abs(x)
    assert float(e.log_s[0, 0]) == pytest.approx(log_s, rel=0, abs=32 * U * terms)
    j = float(e.j[0, 0])
    assert j * x <= 0 and float(e.j_plus[0, 0]) > 0  # The contract's sign, exactly.
    # The rows' slopes against central differences of J: X at N is read twice (the monomial and the
    # factor) and through x; Y at N only through x. Planted: X at N's factor slope dropped.
    with mono_scoped():
        numeric = {}
        for k, (row, node) in enumerate((("X", 0), ("X", 1), ("W", 0), ("W", 1))):
            numeric[k] = _row_difference(spec, state, p, control, potentials, ids.index(row), node)
            assert float(e.d_j_d_ln_c[0, k, 0]) == pytest.approx(numeric[k], rel=1e-6, abs=1e-12)
        h = 1e-6
        up = mono_probe(spec, state, p, control, potentials_for(p, volts + h)).modes.j[0, 0]
        down = mono_probe(spec, state, p, control, potentials_for(p, volts - h)).modes.j[0, 0]
        dpsi = (float(up) - float(down)) / (2 * h * F / (R * spec.model.temperature_K))
        assert float(e.d_j_d_psi[0, 0]) == pytest.approx(dpsi, rel=1e-6, abs=1e-12)
    no_factor = float(e.d_j_d_ln_c[0, 0, 0]) + j * 10.0 * a_x / (1 + 10.0 * a_x)
    assert abs(no_factor - numeric[0]) > 1e-3 * abs(numeric[0])  # Caught at 1e-6.


def _row_difference(spec, state, p, control, potentials, species, node, h=1e-6):
    """dJ/d ln c of one species at one node (0: the cell, 1: the outside node), by central
    differences of its amount at the probe's own arithmetic."""
    out = []
    for sign in (1.0, -1.0):
        if node == 0:
            inc = state.amount_increment.copy()
            total = p.amount_reference[species, 0] + inc[species, 0]
            inc[species, 0] += sign * h * total
            moved = state._replace(amount_increment=inc)
        else:
            inc = state.extracellular_amount_increment.copy()  # bath_0, the outside node.
            total = p.extracellular_amount_reference[species, 0] + inc[species, 0]
            inc[species, 0] += sign * h * total
            moved = state._replace(extracellular_amount_increment=inc)
        out.append(float(transporter.probe(moved, potentials, control, p, xp=np).modes.j[0, 0]))
    return (out[0] - out[1]) / (math.log1p(h) - math.log1p(-h))


def test_the_monomial_domain_is_one_sided_and_its_bare_terms_fail_closed():
    """x far below -80 is admitted for the monomial form and refused for the factored form it
    is not; without potentials its charged slope has no bound, so the bare stage term is +inf."""
    with mono_scoped():
        spec = parse_spec(mono_world())
        structure, state, p, control = start(spec)
        deep = potentials_for(p, 2.4)  # psi ~ +90: x ~ -86 for X+ from N to P.
        e = transporter._evaluate(state, deep, control, p, xp=np)
        assert float(e.x[0, 0]) < -80 and bool(e.valid[0])
        assert np.isinf(transporter.stage_term(state, None, control, p, xp=np)).any()
        assert np.all(np.isfinite(transporter.stage_term(state, deep, control, p, xp=np)))
    with scoped():
        spec2 = parse_spec(exchange_world(exchanger(law="seamtest.net_exchange@1")))
        _, state2, p2, control2 = start(spec2)
        e2 = transporter._evaluate(state2, potentials_for(p2, 2.4), control2, p2, xp=np)
        assert float(e2.x[0, 0]) < -80 and not bool(e2.valid[0])  # |x| <= 80 there.
        # The other forms keep their fields: no monomial field in a world that runs none.
        entry = dict(surface_pump_v3.structure(spec2.model).kinds)[transporter.KIND_ID]
        bound = kind_registry.bound(transporter.TRANSPORTER, entry)
        assert not set(transporter.MONOMIAL_FIELDS) & set(bound.layout_fields)


def test_a_monomial_reference_resolves_only_under_the_binding_owners_conditions():
    """A total, or a named form, is read only where a declared closure holds the row; a row with
    no declared forms has none to read (the binding owner's conditions 1 and 2)."""
    rate = MONO.cycle.monomial.rates[0]
    reason = "read only where a closure holds the row"
    for form_name, law_id in (("total", "seamtest.monomial_total@1"),
                              ("Mg", "seamtest.monomial_mg@1")):
        total = rate._replace(orders=((forms.Reference("X", "N", form_name), 1.0),))
        law = dataclasses.replace(
            MONO, law_id=law_id,
            cycle=MONO.cycle._replace(monomial=MONO.cycle.monomial._replace(rates=(total,))),
        )  # fmt: skip
        with mono_scoped(law), pytest.raises(ConfigError, match=reason):
            parse_spec(exchange_world(exchanger(law=law.law_id)))



def hydrolysis(dg_kj_mol, law_id="seamtest.monomial_hydrolysis@1"):
    """A converting monomial law at N, ATP -> ADP + Pi, its k from a cited dG° (K6)."""
    return law_registry.CycleLaw(
        law_id,
        (),
        (),
        None,
        None,
        cycle=CycleForm(
            kinetics="monomial",
            roles=(("ATP", 0), ("ADP", 0), ("Pi", 0)),
            rows=(("ATP", "N"), ("ADP", "N"), ("Pi", "N")),
            modes=(("hydrolysis", (-1, 1, 1)),),
            monomial=forms.MonomialForm((
                forms.MonomialRate(
                    log_k=forms.CitedConstant(dg_kj_mol, protons=0, scale=0.5, offset=0.25),
                    orders=((forms.Reference("ATP", "N"), 1.0),),
                ),
            )),
        ),
        host=transporter.KIND_ID,
        provenance="calibrated",
        source="a test-only converting monomial law (K6), never shipped",
    )  # fmt: skip


def hydrolysis_world(law_id):
    return tk.held_world(
        dict(
            id="hydrolysis_0", host="membrane_0", law=law_id, orientation={"N": "a"},
            capacity_fmol_s=0.01, roles={"ATP": "ATP", "ADP": "ADP", "Pi": "Pi"}, parameters={},
            held_rows=[],
        )  # fmt: skip
    )


def test_a_cited_dg_is_the_laws_seam_e_entry_and_builds_its_k_from_one_value():
    """The world's registry gives ADP's potential so that dG° = -30.5 kJ/mol (tk.DRIVE0_J_MOL): a
    law citing it is admitted, its entry carries the kJ form, and its k is built from the same
    converted value, bit for bit; a law citing -35 kJ/mol is refused by the registry's check."""
    from decimal import Decimal

    from cells.modules import TEMPERATURE_INDEPENDENT

    cited = tk.DRIVE0_J_MOL / 1000.0
    with mono_scoped(hydrolysis(cited)):
        spec = parse_spec(hydrolysis_world("seamtest.monomial_hydrolysis@1"))
        (entry,) = transporter.standard_free_energies(dict(spec.model.kinds)[transporter.KIND_ID])
        _, _, p, _ = start(spec)
    assert entry.dG_kJ_mol == cited and entry.dG_basis == TEMPERATURE_INDEPENDENT
    assert entry.dG_RT_offset == 0.0 and entry.c0 == 1000.0 and entry.mode == "hydrolysis"
    assert dict(entry.stoichiometry) == {"ATP": -1, "ADP": 1, "Pi": 1}
    rt = Decimal(R) * Decimal(spec.model.temperature_K)
    converted = float(Decimal(cited) * 1000 / rt + Decimal(0.0))  # The registry's own arithmetic.
    assert float(p.cycle_mono_log_k[0, 0]) == 0.25 - 0.5 * converted  # One value, bit for bit.
    with mono_scoped(hydrolysis(-35.0, "seamtest.monomial_off@1")):
        with pytest.raises(ConfigError, match="monomial_off"):
            parse_spec(hydrolysis_world("seamtest.monomial_off@1"))


# ------------------------------------------------------- the trapezoid heat booking (K2)


def trapezoid_booked(raw):
    raw = copy.deepcopy(raw)
    raw["model"]["heat_bookings"] = {transporter.KIND_ID: transporter.TRAPEZOID_BOOKING}
    return raw


@pytest.mark.parametrize("layout", ("version 1", "population axis"))
def test_the_trapezoid_books_the_kinds_heat_and_leaves_every_other_field(layout):
    """Seam D's trapezoid_nonnegative@1, picked for the kind: four steps under the tableau and
    under the trapezoid give every field but the heat bitwise equal, the heat non-decreasing, and
    every ledger closed (the energy ledger with the trapezoid's heat)."""
    raw = tk.held_world() if layout == "version 1" else tk.held_world(general(tk.population()))
    heat = "transporter_dissipated_energy_pJ"
    if layout != "version 1":
        heat = "cycle_dissipated_energy_pJ"
    ends = {}
    for name, world in (("tableau", raw), ("trapezoid", trapezoid_booked(raw))):
        with scoped():
            spec = parse_spec(copy.deepcopy(world))
            impl = get_model(spec.model)
            state, p = impl.initial_values(spec)
            control = impl.Control(*(v[0] for v in control_values(spec, [0.0])))
            states = [state]
            for _ in range(4):
                state, valid = impl.imex_step(state, spec.execution.dt, control, p, xp=np)
                assert bool(valid)
                states.append(state)
            history = impl.STATE_TYPE(*(np.stack(v) for v in zip(*states, strict=True)))
            impl.check_values(history, spec, steps=np.arange(len(states)))  # Every ledger closes.
            ends[name] = (spec, states)
    (_, tableau), (booked, trapezoid) = ends["tableau"], ends["trapezoid"]
    assert booked.model.heat_bookings == ((transporter.KIND_ID, transporter.TRAPEZOID_BOOKING),)
    for name in type(tableau[-1])._fields:
        if name != heat:
            assert np.array_equal(getattr(tableau[-1], name), getattr(trapezoid[-1], name)), name
    assert not np.array_equal(getattr(tableau[-1], heat), getattr(trapezoid[-1], heat))
    assert np.all(np.diff(np.stack([getattr(s, heat) for s in trapezoid]), axis=0) >= 0)


def test_the_trapezoid_pick_is_refused_for_a_net_flow_population_and_an_unadmitting_kind():
    """A net-flow population's heat is non-negative only within its guard's allowance, so the
    pick is refused where one is declared; planted: the kind without the declaration refuses it."""
    with scoped(), pytest.raises(ConfigError, match="only within its guard's allowance"):
        parse_spec(trapezoid_booked(exchange_world(exchanger(law="seamtest.net_exchange@1"))))
    plain = dataclasses.replace(transporter.TRANSPORTER, heat_bookings=())
    with tk.scoped(plain), pytest.raises(ConfigError, match="admits no heat booking"):
        parse_spec(trapezoid_booked(tk.held_world()))


# ----------------------------------------------------------------- the proton readouts (K4)

UNIPORT = law_registry.CycleLaw(
    "seamtest.proton_uniport@1",
    (),
    (),
    None,
    None,
    cycle=CycleForm(
        kinetics="net_flow",
        roles=(("H", 1),),
        rows=(("H", "N"), ("H", "P")),
        modes=(("uniport", (-2, 2)),),
        flux_terms=((FluxTerm(1.0, (-2, 2)),),),
    ),
    host=transporter.KIND_ID,
    provenance="calibrated",
    source="a test-only law moving two protons from N to P and nothing else, never shipped",
)


def proton_world():
    """held_world with H+ at pH 7.2 in the cell and 7.0 in the bath, and three proton uniports:
    two naming H for the proton readouts, N the cell for one and the bath for the other, and one
    naming none."""

    def uniport(name, n_end, **over):
        return dict(
            id=name,
            host="membrane_0",
            law=UNIPORT.law_id,
            orientation={"N": n_end},
            capacity_fmol_s=0.01,
            roles={"H": "H"},
            parameters={},
            held_rows=[],
            **over,
        )

    raw = tk.held_world(
        uniport("u_a", "a", proton_readout="H"),
        uniport("u_b", "b", proton_readout="H"),
        uniport("u_0", "a"),
    )
    return add_species(raw, "H", 1, 0.0, {"cell_0": 10.0**-4.2, "bath_0": 10.0**-4.0})


def test_the_proton_readouts_tie_delta_p_to_a_pure_proton_modes_x_with_beards_sign():
    """K4: delta psi = phi_P - phi_N and delta p = delta psi + (RT/F) ln(h_P / h_N) per asking
    population, so a mode moving two protons from N to P alone has RT x = 2 F delta p, at set
    potentials and through the core's observations (the stage read, the field's potentials).
    Turning N to the other end flips both; a population naming no row reads 0, and a definition
    without the key keeps today's entry, fields and columns. Planted: either sign flipped (delta
    psi as phi_N - phi_P, or ln(h_N / h_P)) breaks the tie. The run view states both as
    differences P less N, and the counts' N-to-P orientation."""
    from cells.execution.state import initialise
    from cells.records import run_view

    raw = proton_world()
    with mono_scoped(UNIPORT):
        spec = parse_spec(copy.deepcopy(raw))
        structure, state, p, control = start(spec)
        impl = get_model(spec.model)
        history = impl.STATE_TYPE(*(np.asarray(v)[None] for v in state))
        observed = impl.observe_history(np.zeros(1), history, p, [0.0], spec)
        plan = run_view.prepare(spec, run_view.Request(), layout=initialise(spec).layout)
        view = plan.view(run_view.single_file_bases([0.0], [0.0]), "write_run")
        for entry in raw["model"]["transporters"]:  # The same world without the key.
            entry.pop("proton_readout", None)
        bare = surface_pump_v3.structure(parse_spec(raw).model).kinds
    declaration = dict(spec.model.kinds)[transporter.KIND_ID]
    assert transporter.to_dict(declaration) == proton_world()["model"]["transporters"]
    ((_, entry),) = structure.kinds
    assert entry == transporter.CycleAxis((UNIPORT.law_id,), True)
    bound = kind_registry.bound(transporter.TRANSPORTER, entry)
    assert bound.readout_columns[-2:] == transporter.PROTON_READOUT_COLUMNS
    assert set(transporter.PROTON_READOUT_FIELDS) <= set(type(p)._fields)
    ((_, entry),) = bare  # Without the key: today's entry, fields and columns.
    assert entry == transporter.CycleAxis((UNIPORT.law_id,))
    bound = kind_registry.bound(transporter.TRANSPORTER, entry)
    assert bound.readout_columns == transporter.GENERAL_READOUT_COLUMNS
    assert not set(transporter.PROTON_READOUT_FIELDS) & set(bound.layout_fields)

    def ties(rt_x, delta_p):
        return np.allclose(rt_x, 2.0 * F * delta_p, rtol=1e-12, atol=0.0)

    potentials = potentials_for(p, -0.15, 0.0)
    _, rt_x, _, dpsi, dp = transporter.readouts(state, state, potentials, control, p, xp=np)
    observed_dp = observed.cycle_proton_motive_force_V[0]
    observed_rt_x = observed.cycle_free_energy_J_mol[0]
    assert dpsi[0] == 0.15 and dpsi[1] == -0.15 and dp[1] == -dp[0]  # N at the bath: flipped.
    log_ratio = 0.2 * math.log(10.0)  # ln(h_bath / h_cell)
    expected = 0.15 + R * spec.model.temperature_K / F * log_ratio
    assert dp[0] == pytest.approx(expected, rel=1e-12)
    assert ties(rt_x[0, :2], dp[:2]) and ties(observed_rt_x[0, :2], observed_dp[:2])
    assert observed_dp[0] != 0 and observed_dp[1] == -observed_dp[0]
    assert dpsi[2] == dp[2] == 0 and rt_x[0, 2] != 0  # Naming no row: 0, its x read as before.
    assert observed.cycle_membrane_potential_V[0][2] == observed_dp[2] == 0
    chem = dp - dpsi
    for planted in (chem - dpsi, dpsi - chem):  # Planted: each sign flipped.
        assert not ties(rt_x[0, :2], planted[:2])
    records = {r["field"]: r for r in view["records"]}
    for column in transporter.PROTON_READOUT_COLUMNS:
        record = records[column]
        assert record["unit"] == "V" and record["kind"] == "level", record
        assert (record["difference"]["plus"], record["difference"]["minus"]) == ("P", "N")
    count = records["cycle_count"]["sign"]
    assert (count["from"], count["to"]) == ("N", "P")
    run_view.validate(view)


def test_an_asking_population_reads_out_its_share_of_the_current_and_clamped_rates_agree():
    """FR-34 (D251, D252): cycle_current_A is each asking population's current through its host in
    A, outward-positive (end a to end b, the cell to the bath here): e times the charge its modes
    move N to P, turned where N is end b. A population that does not ask reads 0, and the H row's
    share of the patch's own outward flux is the three uniports' currents. clamped_rates at the
    row's own voltage gives the readouts' J and current exactly, and FR-34's control holds to
    rounding: half the availability, half the current. Without the key the world keeps its entry,
    fields and columns. The key round-trips, a non-boolean is refused, and the run view states the
    column's unit, kind and sign. Planted: the current left in the counts' N-to-P orientation
    misses u_b's, whose N is the bath. Parses and observes one world, without stepping: about 3 s."""
    from cells.execution.state import initialise
    from cells.records import run_view

    raw = proton_world()
    for entry in raw["model"]["transporters"][:2]:  # u_a (N the cell) and u_b (N the bath).
        entry[transporter.CURRENT_READOUT_KEY] = True
    with mono_scoped(UNIPORT):
        spec = parse_spec(copy.deepcopy(raw))
        structure, state, p, control = start(spec)
        impl = get_model(spec.model)
        history = impl.STATE_TYPE(*(np.asarray(v)[None] for v in state))
        observed = impl.observe_history(np.zeros(1), history, p, [0.0], spec)
        plan = run_view.prepare(spec, run_view.Request(), layout=initialise(spec).layout)
        view = plan.view(run_view.single_file_bases([0.0], [0.0]), "write_run")
        field = surface_pump_v3.readouts(state, control, p, xp=np, structure=structure).field
        bare_raw = copy.deepcopy(raw)
        for entry in bare_raw["model"]["transporters"]:
            entry.pop(transporter.CURRENT_READOUT_KEY, None)
        bare = surface_pump_v3.structure(parse_spec(bare_raw).model).kinds
        planted = copy.deepcopy(raw)
        planted["model"]["transporters"][0][transporter.CURRENT_READOUT_KEY] = "yes"
        with pytest.raises(ConfigError, match="current_readout is true or false"):
            parse_spec(planted)
    declaration = dict(spec.model.kinds)[transporter.KIND_ID]
    assert transporter.to_dict(declaration) == raw["model"]["transporters"]
    ((_, entry),) = structure.kinds
    assert entry == transporter.CycleAxis((UNIPORT.law_id,), True, False, True)
    bound = kind_registry.bound(transporter.TRANSPORTER, entry)
    assert bound.readout_columns[-1:] == transporter.CURRENT_READOUT_COLUMNS
    ((_, entry),) = bare  # Without the key: today's entry, fields and columns.
    assert entry == transporter.CycleAxis((UNIPORT.law_id,), True)
    bound = kind_registry.bound(transporter.TRANSPORTER, entry)
    assert not set(transporter.CURRENT_READOUT_COLUMNS) & set(bound.readout_columns)
    assert not set(transporter.CURRENT_READOUT_FIELDS) & set(bound.layout_fields)

    potentials = potentials_for(p, -0.15, 0.0)
    rate, *_, current = transporter.readouts(state, state, potentials, control, p, xp=np)
    toward_p = 2.0 * CHARGE_PER_FMOL * rate[0]  # Each moves 2 H+ from N to P per cycle.
    assert current[0] == toward_p[0] != 0 and current[1] == -toward_p[1] != 0  # u_b: N the bath.
    assert current[2] == 0 and rate[0, 2] != 0  # u_0 does not ask.
    assert current[1] != toward_p[1]  # Planted: the counts' orientation, not end a to end b.
    volts = np.full(3, potentials[0] - potentials[p.active.size])  # phi_cell - phi_bath.
    clamped, at_volts = transporter.clamped_rates(state, control, p, volts)
    assert np.array_equal(clamped, rate) and np.array_equal(at_volts[:2], current[:2])
    halved = control._replace(cycle_availability=0.5 * control.cycle_availability)
    _, half = transporter.clamped_rates(state, halved, p, volts)
    assert half == pytest.approx(0.5 * at_volts, rel=4 * np.finfo(float).eps, abs=0.0)
    # Observed: the uniports' currents are the H row's share of the patch's outward flux.
    h_row = list(spec.model.species_ids).index("H")
    patch_h = CHARGE_PER_FMOL * float(np.asarray(observed.membrane_flux_fmol_s[0])[h_row, 0])
    observed_v = np.asarray(field.potential_V)
    own = np.full(3, observed_v[0] - observed_v[p.active.size])  # The row's phi_cell - phi_bath.
    _, all_current = transporter.clamped_rates(state, control, p, own)
    assert float(np.sum(all_current)) == pytest.approx(patch_h, rel=1e-12, abs=0.0)
    assert np.array_equal(
        np.asarray(observed.cycle_current_A[0]), np.where([True, True, False], all_current, 0.0)
    )
    record = {r["field"]: r for r in view["records"]}["cycle_current_A"]
    assert (record["unit"], record["kind"]) == ("A", "rate")
    assert (record["sign"]["from"], record["sign"]["to"]) == ("inside", "outside")
    run_view.validate(view)


# ------------------------------------------------------- moved fuel at a closure node (K1)

CLOSURE_HYDROLYSIS = law_registry.CycleLaw(
    "seamtest.closure_hydrolysis@1",
    (),
    (transporter.FINITE,),
    None,
    None,
    reads=("rapid_binding@1",),
    forms="base",
    cycle=CycleForm(
        kinetics="net_flow",
        roles=(("ATP", -4), ("ADP", -3), ("Pi", -2), ("H", 1)),
        rows=(("ATP", "N"), ("ADP", "N"), ("Pi", "N"), ("H", "N")),
        modes=(("hydrolysis", (-1, 1, 1, 1)),),
        flux_terms=((FluxTerm(1.0, (-1, 1, 1, 1)),),),
        fuel_roles=("ATP", "ADP", "Pi"),
    ),
    host=transporter.KIND_ID,
    provenance="calibrated",
    source="a test-only base-form hydrolysis on finite fuel releasing its proton at N (K1), never "
    "shipped",
)


MU_H_SHIFT = 5.0  # H's mu°/RT off 0, so its standard part is not invisible to the ledger.


INHIBITED_HYDROLYSIS = law_registry.CycleLaw(
    "seamtest.inhibited_hydrolysis@1",
    (),
    (transporter.FINITE,),
    None,
    None,
    reads=("rapid_binding@1",),
    forms="base",
    cycle=CycleForm(
        kinetics="monomial",
        roles=(("ATP", -4), ("ADP", -3), ("Pi", -2), ("H", 1)),
        rows=(("ATP", "N"), ("ADP", "N"), ("Pi", "N"), ("H", "N")),
        modes=(("hydrolysis", (-1, 1, 1, 1)),),
        fuel_roles=("ATP", "ADP", "Pi"),
        monomial=forms.MonomialForm((
            forms.MonomialRate(
                log_k=-12.0,
                orders=((forms.Reference("ATP", "N"), 1.0), (forms.Reference("H", "N"), -1.0)),
            ),
        )),
    ),
    host=transporter.KIND_ID,
    provenance="calibrated",
    source="a test-only hydrolysis first order in free ATP and inhibited by free h (K3b), never "
    "shipped",
)  # fmt: skip


@contextlib.contextmanager
def closure_scoped():
    """The transporter and the binding closure's kind, the test laws, CLOSURE_HYDROLYSIS and the
    inhibited hydrolysis."""
    laws = law_registry.BUILTIN.extended(*TEST_LAWS, CLOSURE_HYDROLYSIS, INHIBITED_HYDROLYSIS)
    with tk.scoped(*tk.CHARGED_KINDS), law_registry.scope(laws):
        yield


def closure_fuel_world(closure="general", n_end="a", lumped=False, binder=False):
    """The binding owner's buffered cell (B binds H at the cell; every route, channel and pump at
    availability 0) with ATP4-, ADP3- and Pi2- rows, and one population hydrolysing ATP at the cell
    on finite fuel, its proton released into the cell's H row: fuel moving where protons move.
    H's potential is moved off 0 (and HB's with it, so B's binding constant is kept), so that a
    proton's standard part counted twice would show in the energy ledger. The fuel rows have no
    forms: the species registry refuses every mover of a row with forms (check_two_form_rows), a
    closure's binder included. closure: "general", rapid_binding@1 holding H at the cell;
    "version 1", rapid_proton_buffer@1 there; or "no proton row", the general closure declaring
    none. n_end "b" puts the population's N, and so its fuel and H, at the bath. lumped adds the
    built-in neutral law on finite fuel at the cell (transformed potentials: no base forms), its
    role Y and its lumped fuel nATP, nADP and nPi neutral rows that no closure holds. binder makes
    ATP a binder of the general closure at the cell (its form HATP, pK 7.8; the registry defers its
    base-form move to the closure's admission) and runs the inhibited hydrolysis on it."""
    from cells.kinds import proton_buffer
    from tests.unit.test_proton_buffer_kind import buffered_world
    from tests.unit.test_rapid_binding_world import general as closed

    raw = buffered_world(quiet=True)
    rows = {e["id"]: e for e in raw["model"]["species"]}
    rows["H"]["standard_mu_RT"] += MU_H_SHIFT
    rows["B"]["protonated_standard_mu_RT"] += MU_H_SHIFT
    if closure != "version 1":
        raw = closed(raw)
    m = raw["model"]
    if closure == "no proton row":
        del m[proton_buffer.MODEL_KEY][0]["proton_row"]
    cell, bath = m["cells"][0]["id"], m["extracellular"][0]["id"]
    fuel = (("ATP", -4, 0.0, 2.0), ("ADP", -3, -9.0, 0.2), ("Pi", -2, -6.0, 1.0))
    for sid, z, mu_RT, mM in fuel:
        add_species(raw, sid, z, mu_RT, {cell: mM, bath: mM})
    if binder:
        atp = next(e for e in m["species"] if e["id"] == "ATP")
        hatp = atp["standard_mu_RT"] + rows["H"]["standard_mu_RT"] - 7.8 * math.log(10.0)
        atp["forms"] = [dict(id="HATP", counts={"H": 1}, standard_mu_RT=hatp)]
        (read,) = m[proton_buffer.MODEL_KEY]
        read["binders"][cell] = sorted([*read["binders"][cell], "ATP"])
        read["k_on_per_mM_s"]["ATP"] = {"H": 1e7}
    m[transporter.MODEL_KEY] = [
        dict(
            id="hydrolysis_0",
            host=m["membranes"][0]["id"],
            law=(INHIBITED_HYDROLYSIS if binder else CLOSURE_HYDROLYSIS).law_id,
            orientation={"N": n_end},
            capacity_fmol_s=0.05,
            roles={"ATP": "ATP", "ADP": "ADP", "Pi": "Pi", "H": "H"},
            parameters={},
            held_rows=[],
        )
    ]
    if lumped:
        neutral = (("Y", 0.0, 1.0), ("nATP", 0.0, 2.0), ("nADP", -6.0, 0.2), ("nPi", -6.0, 1.0))
        for sid, mu_RT, mM in neutral:
            add_species(raw, sid, 0, mu_RT, {cell: mM, bath: mM})
        m[transporter.MODEL_KEY].append(
            dict(
                id="lumped_0",
                host=m["membranes"][0]["id"],
                law=transporter.NEUTRAL_LAW,
                orientation={"N": "a"},
                capacity_fmol_s=0.01,
                roles={"role": "Y", "ATP": "nATP", "ADP": "nADP", "Pi": "nPi"},
                parameters=dict(stoichiometry=1, km_role_mM=1.0, km_atp_mM=0.1),
                held_rows=[],
            )
        )
    return raw


def test_moved_fuel_at_a_general_closures_proton_row_runs_and_its_energy_closes():
    """K1, §5.2's one exception: fuel may move at a node whose proton row moves where a general
    binding closure holds that row. Four steps of a population hydrolysing ATP at the cell, whose
    H the general closure holds: the cycles run, the cell's ATP, ADP, Pi and H totals change by
    their counts, and every ledger closes, the energy ledger with the population's standard part,
    the closure's S_c and @3's ideal terms (the binding owner's split). Planted, each refused at
    the definition by §5.2's boundary: version 1's buffer at the cell; a general closure that
    declares no proton row; the population's N at the bath, where the closure holds nothing; and
    the built-in neutral law on lumped finite fuel at the cell (no base forms). Planted too,
    stepped once: the population's g° shifted by 1 (its heat then booked from a wrong x, RT per
    cycle, a fifth of a proton's standard part counted twice), which the energy ledger refuses.
    The population names H for K4's readouts: at the buffered cell, delta p's proton term is
    (RT/F) ln(h_bath / h_cell) of the closure's free h, about -12 mV, not of the stored totals,
    about -357 mV (@3's observations at the start)."""

    def run(spec, impl, p, steps=4):
        state, _ = impl.initial_values(spec)
        control = impl.Control(*(v[0] for v in control_values(spec, [0.0])))
        states = [state]
        for _ in range(steps):
            state, valid = impl.imex_step(state, spec.execution.dt, control, p, xp=np)
            assert bool(valid)
            states.append(state)
        history = impl.STATE_TYPE(*(np.stack(v) for v in zip(*states, strict=True)))
        impl.check_values(history, spec, steps=np.arange(len(states)))  # Every ledger closes.
        return states

    from cells.kinds import proton_buffer

    raw = closure_fuel_world()
    raw["model"][transporter.MODEL_KEY][0]["proton_readout"] = "H"  # K4's readouts too.
    with closure_scoped():
        spec = parse_spec(raw)
        impl = get_model(spec.model)
        _, p = impl.initial_values(spec)
        states = run(spec, impl, p)
        history = impl.STATE_TYPE(*(np.asarray(v)[None] for v in states[0]))
        observed = impl.observe_history(np.zeros(1), history, p, [0.0], spec)
        read, read_ok = proton_buffer.stage_read(states[0], p, xp=np)
        shifted = p._replace(cycle_standard_RT=p.cycle_standard_RT + 1.0)
        with pytest.raises(NumericalError, match="energy"):  # Planted: the ledger sees it.
            run(spec, impl, shifted, steps=1)
        for planted in (
            dict(closure="version 1"),
            dict(closure="no proton row"),
            dict(n_end="b"),  # The fuel and H at the bath, where the closure holds nothing.
            dict(lumped=True),  # A law without base forms at the closure's node.
        ):
            with pytest.raises(ConfigError, match="§5.2's boundary"):
                parse_spec(closure_fuel_world(**planted))
    cycles = float(states[-1].cycle_count[0, 0])
    assert cycles > 0
    ids = list(spec.model.species_ids)
    moved = states[-1].amount_increment[:, 0] - states[0].amount_increment[:, 0]
    for species, n in (("ATP", -1), ("ADP", 1), ("Pi", 1), ("H", 1)):
        assert moved[ids.index(species)] == pytest.approx(n * cycles, rel=1e-9), species

    def h_ratio(s):  # h at the bath over h at the cell, of state s's H rows.
        h = ids.index("H")
        cell = (p.amount_reference + s.amount_increment)[h, 0] / p.volume[0]
        bath = (p.extracellular_amount_reference + s.extracellular_amount_increment)[h, 0]
        return bath / p.extracellular_volume[0] / cell

    assert bool(read_ok)
    delta_p = observed.cycle_proton_motive_force_V[0][0]
    term = float(delta_p - observed.cycle_membrane_potential_V[0][0])
    rt_f = R * spec.model.temperature_K / F
    assert term == pytest.approx(rt_f * math.log(h_ratio(read)), rel=1e-9)  # Free h.
    assert term - rt_f * math.log(h_ratio(states[0])) > 0.3  # Not the stored totals' (planted).
    # K3b, at the start (no step): with ATP a binder of the closure, ATP's material slope runs
    # through the closure's derivative, its own D and free h's through the inhibition, and bounds
    # the central difference of its rate against its stored total; planted: through the free
    # amount instead (too tight by total over free) and through D's diagonal alone (too loose).
    with closure_scoped():
        spec = parse_spec(closure_fuel_world(binder=True))
        impl = get_model(spec.model)
        state, p = impl.initial_values(spec)
        control = impl.Control(*(v[0] for v in control_values(spec, [0.0])))
        volts = potentials_for(p, 0.0, 0.0)

        def flux(s):
            read, ok = proton_buffer.stage_read(s, p, xp=np)
            assert bool(ok)
            return float(transporter._evaluate(read, volts, control, p, xp=np).j[0, 0]), read

        j, read = flux(state)
        slopes, _ = transporter._material_slopes(read, volts, control, p, xp=np)
        e = transporter._evaluate(read, volts, control, p, xp=np)
        d, held = proton_buffer.free_log_sensitivity(read, p, xp=np)
    ids = list(spec.model.species_ids)
    a, h = ids.index("ATP"), ids.index("H")
    assert bool(held[a, 0]) and bool(held[h, 0]) and j > 0
    total = float((p.amount_reference + state.amount_increment)[a, 0])
    delta = 1e-4 * total  # Its curvature error ~1e-8; the closure's solve noise far below.
    moved = {}
    for sign in (1, -1):
        shifted = state.amount_increment.copy()
        shifted[a, 0] += sign * delta
        moved[sign], _ = flux(state._replace(amount_increment=shifted))
    central = abs(moved[1] - moved[-1]) / (2 * delta)  # |dJ/dn_ATP| at the cell (1/s)
    k = 0  # Row 0 is ATP at N, the cell.
    g = np.abs(e.d_j_d_ln_c[0, :, 0])  # Rows ATP, ADP, Pi, H.
    through = g[0] * abs(d[a, a, 0]) + g[3] * abs(d[h, a, 0])  # ATP's own term and free h's.
    assert float(slopes[k, 0]) == pytest.approx(through, rel=1e-12)
    assert float(slopes[k, 0]) == pytest.approx(central, rel=1e-5)  # The terms add: exact here.
    free = float((p.amount_reference + read.amount_increment)[a, 0])
    assert g[0] / free > 2.0 * central  # Planted: through the free amount, too tight.
    assert g[0] * abs(d[a, a, 0]) < 0.97 * central  # Planted: D's diagonal alone, too loose.


# ------------------------------------------------------------------- chemistry at P (K3)

Q_CYCLE = (-1, 1, -2, 2, -2, 4)  # QH2 + 2 Cox+ (P) + 2 H+ (N) -> Q + 2 Cred (P) + 4 H+ (P)


def p_redox(forms="base"):
    """A test-only cytochrome c reducer at P, complex III's net Q cycle on charged cytochrome c
    forms (Cox+ to Cred), saturating in Cox, its moves in base forms read through rapid_binding@1
    (never shipped)."""
    return law_registry.CycleLaw(
        "seamtest.p_side_redox@1",
        (),
        (),
        None,
        None,
        reads=("rapid_binding@1",),
        forms=forms,
        cycle=CycleForm(
            kinetics="factored",
            roles=(("QH2", 0), ("Q", 0), ("Cox", 1), ("Cred", 0), ("H", 1)),
            rows=(("QH2", "N"), ("Q", "N"), ("Cox", "P"), ("Cred", "P"), ("H", "N"), ("H", "P")),
            modes=(("q_cycle", Q_CYCLE),),
            saturation=((Saturation(("Cox", "P"), 1.0, 1),),),
        ),
        host=transporter.KIND_ID,
        provenance="calibrated",
        source="a test-only cytochrome c reducer at P (K3), never shipped",
    )


@contextlib.contextmanager
def p_redox_scoped(*kinds, law=None):
    laws = law_registry.BUILTIN.extended(*TEST_LAWS, law or p_redox())
    with tk.scoped(*(kinds or tk.CHARGED_KINDS)), law_registry.scope(laws):
        yield


def p_redox_world():
    """The binding owner's buffered cell under the general closure (H held at the cell; H's
    potential off 0, HB's with it) with Q, QH2 and cytochrome c's two forms, Cox+ and Cred, at
    distinct nonzero potentials, and one reducer whose N is the bath (end b): P is the buffered
    cell, so the mode's P rows meet §5.2's admission at the closure's H row. Its Cox pool is small,
    so Cox's material slope leads the cell's."""
    from tests.unit.test_proton_buffer_kind import buffered_world
    from tests.unit.test_rapid_binding_world import general as closed

    raw = buffered_world(quiet=True)
    rows = {e["id"]: e for e in raw["model"]["species"]}
    rows["H"]["standard_mu_RT"] += MU_H_SHIFT
    rows["B"]["protonated_standard_mu_RT"] += MU_H_SHIFT
    raw = closed(raw)
    m = raw["model"]
    cell, bath = m["cells"][0]["id"], m["extracellular"][0]["id"]
    redox = (
        ("QH2", 0, 0.0, 1.0),
        ("Q", 0, -8.0, 0.5),
        ("Cox", 1, -3.0, 0.02),
        ("Cred", 0, 2.0, 0.5),
    )
    for sid, z, mu_RT, mM in redox:
        add_species(raw, sid, z, mu_RT, {cell: mM, bath: mM})
    m[transporter.MODEL_KEY] = [
        dict(
            id="redox_0",
            host=m["membranes"][0]["id"],
            law="seamtest.p_side_redox@1",
            orientation={"N": "b"},
            capacity_fmol_s=0.05,
            roles={"QH2": "QH2", "Q": "Q", "Cox": "Cox", "Cred": "Cred", "H": "H"},
            parameters={},
            held_rows=[],
        )
    ]
    return raw


def test_a_mode_converting_cytochrome_c_at_p_moves_bounds_and_books_it_there():
    """K3: a mode that changes a species at P without changing it at N. Admitted, with its P rows
    through §5.2's admission at the closure's H row (planted: the law without base forms is
    refused there). At the start: the material term bounds the charged Cox+ row at P, its slope
    |nu dJ/dn| from the evaluation's own derivative (planted: without K3's rows the cell's term is
    far smaller); the membrane flux reads every P-side change as a crossing, so its charge is the
    patch's current, -q J outward with N at the bath. Four steps: the P rows move at the cell by
    their counts and every ledger closes, the energy ledger with the conversions' standard parts
    (planted: the P-side change booked at N, which the cell's material ledger refuses; and, stepped
    once, the population's g° shifted by 1, which the energy ledger refuses)."""

    def run(impl, spec, p, control, steps=4):
        state, _ = impl.initial_values(spec)
        states = [state]
        for _ in range(steps):
            state, valid = impl.imex_step(state, spec.execution.dt, control, p, xp=np)
            assert bool(valid)
            states.append(state)
        history = impl.STATE_TYPE(*(np.stack(v) for v in zip(*states, strict=True)))
        impl.check_values(history, spec, steps=np.arange(len(states)))  # Every ledger closes.
        return states, history

    with p_redox_scoped():
        spec = parse_spec(p_redox_world())
        impl = get_model(spec.model)
        _, p = impl.initial_values(spec)
        control = impl.Control(*(v[0] for v in control_values(spec, [0.0])))
        states, history = run(impl, spec, p, control)
        shifted = p._replace(cycle_standard_RT=p.cycle_standard_RT + 1.0)
        with pytest.raises(NumericalError, match="energy"):  # Planted: the ledger sees it.
            run(impl, spec, shifted, control, steps=1)
    with p_redox_scoped(law=p_redox(forms=None)), pytest.raises(ConfigError, match="base forms"):
        parse_spec(p_redox_world())
    booked_at_n = dataclasses.replace(
        transporter.TRANSPORTER,
        ledger_terms=lambda state, p, *, xp: transporter.ledger_terms(
            state, p._replace(cycle_row_at_n=xp.ones_like(p.cycle_row_at_n)), xp=xp
        ),
    )
    from cells.kinds import proton_buffer

    with p_redox_scoped(booked_at_n, proton_buffer.PROTON_BUFFER):  # Planted: P booked at N.
        with pytest.raises(NumericalError, match="accounting failed: local"):
            get_model(spec.model).check_values(history, spec, steps=np.arange(len(states)))
    entry = dict(impl.structure.kinds)[transporter.KIND_ID]
    assert entry.end_chemistry and "cycle_row_end_chemistry" in type(p)._fields
    ids, k = list(spec.model.species_ids), 2  # Row 2 is Cox at P.
    potentials = potentials_for(p, 0.0, 0.0)
    read, read_ok = proton_buffer.stage_read(states[0], p, xp=np)  # Free h at the cell.
    assert bool(read_ok)
    e = transporter._evaluate(read, potentials, control, p, xp=np)
    amount = (p.amount_reference + read.amount_increment)[ids.index("Cox"), 0]
    slope = abs(2.0 * float(e.d_j_d_ln_c[0, k, 0])) / float(amount)
    term = transporter.material_term(read, potentials, control, p, xp=np)
    assert float(term[0]) == pytest.approx(slope, rel=1e-12)  # The cell's term is Cox's slope.
    without = p._replace(cycle_row_end_chemistry=np.zeros_like(p.cycle_row_end_chemistry))
    assert float(transporter.material_term(read, potentials, control, without, xp=np)[0]) < (
        1e-3 * slope
    )
    rates = transporter.rates(read, potentials, control, p, xp=np)
    j = float(rates.derivatives["cycle_count"][0, 0])
    charge = float(np.sum(np.asarray(spec.model.valence) * rates.membrane_flux[:, 0]))
    assert j > 0 and charge == pytest.approx(-2.0 * j, rel=1e-12)  # q = 2, outward is P to N.
    cycles = float(states[-1].cycle_count[0, 0])
    moved = states[-1].amount_increment[:, 0] - states[0].amount_increment[:, 0]
    for species, n in (("Cox", -2), ("Cred", 2), ("H", 4)):
        assert moved[ids.index(species)] == pytest.approx(n * cycles, rel=1e-9), species


# ------------------------------------------------------ P at a finite outside node (K3b)

P_ACID = law_registry.CycleLaw(
    "seamtest.p_side_acid@1",
    (),
    (),
    None,
    None,
    reads=("rapid_binding@1",),
    forms="base",
    cycle=CycleForm(
        kinetics="factored",
        roles=(("HA", 0), ("A", -1), ("H", 1)),
        rows=(("HA", "P"), ("A", "P"), ("H", "P")),
        modes=(("release", (-1, 1, 1)),),
        saturation=((Saturation(("HA", "P"), 1.0, 1),),),
    ),
    host=transporter.KIND_ID,
    provenance="calibrated",
    source="a test-only acid releasing its proton at P only (K3b), never shipped",
)


def lumen_acid_world(closure_at_lumen):
    """FR-4's development world under the general closure (the binding owner's lumen_general), its
    lumen a finite outside node, with an acid HA and its base A- at every node and one population
    on the bounding patch, N at the cell and P at the lumen (host P's orientation), releasing H+
    from HA at P only. Without the closure at the lumen, the closure holds the cell's rows alone
    and B_L is a plain row."""
    from tests.unit.test_rapid_binding_world import fr, lumen_general

    raw = lumen_general()
    m = raw["model"]
    if not closure_at_lumen:
        (read,) = m["stage_reads"]
        read["binders"] = {fr.CELL: ["B_c"]}
        read["k_on_per_mM_s"] = {"B_c": {"H": 1e7}}
        del next(e for e in m["species"] if e["id"] == "B_L")["forms"]
    nodes = [node["id"] for node in (*m["cells"], *m["extracellular"])]
    for sid, z, mu_RT, mM in (("HA", 0, 0.0, 1.0), ("A", -1, -2.0, 0.1)):
        add_species(raw, sid, z, mu_RT, dict.fromkeys(nodes, mM))
    m[transporter.MODEL_KEY] = [
        dict(
            id="acid_0",
            host="bounding_0",
            law=P_ACID.law_id,
            orientation={"N": "a"},
            capacity_fmol_s=0.01,
            roles={"HA": "HA", "A": "A", "H": "H"},
            parameters={},
            held_rows=[],
        )
    ]
    return raw


@pytest.mark.parametrize("closure_at_lumen", (True, False))
def test_p_at_a_finite_outside_node_books_and_bounds_with_and_without_a_closure(closure_at_lumen):
    """K3b (b), host P's orientation: N at the cell, P at FR-4's lumen, a finite outside node. Two
    steps of an acid releasing H+ at P only: the lumen's rows move by their counts and every ledger
    closes. The H row it changes at P only is bounded through the closure's derivative where the
    closure holds the lumen's H, by sum_i |dJ/d ln c_i| |D_iH| and far below its free amount's
    slope (the buffer's capacity), and through the free amount where it does not."""
    from cells.kinds import proton_buffer

    laws = law_registry.BUILTIN.extended(*TEST_LAWS, P_ACID)
    with tk.scoped(*tk.CHARGED_KINDS), law_registry.scope(laws):
        spec = parse_spec(lumen_acid_world(closure_at_lumen))
        impl = get_model(spec.model)
        state, p = impl.initial_values(spec)
        control = impl.Control(*(v[0] for v in control_values(spec, [0.0])))
        states = [state]
        for _ in range(2):
            state, valid = impl.imex_step(state, spec.execution.dt, control, p, xp=np)
            assert bool(valid)
            states.append(state)
        history = impl.STATE_TYPE(*(np.stack(v) for v in zip(*states, strict=True)))
        impl.check_values(history, spec, steps=np.arange(len(states)))  # Every ledger closes.
        read, read_ok = proton_buffer.stage_read(states[0], p, xp=np)
        volts = potentials_for(p, 0.0, 0.0)
        slopes, row_node = transporter._material_slopes(read, volts, control, p, xp=np)
        e = transporter._evaluate(read, volts, control, p, xp=np)
        d, held = proton_buffer.free_log_sensitivity(read, p, xp=np)
    ids = list(spec.model.species_ids)
    n = len(spec.model.cells)
    o = [x.id for x in spec.model.extracellular].index("lumen_0")
    cycles = float(states[-1].cycle_count[0, 0])
    before, after = (s.extracellular_amount_increment[:, o] for s in (states[0], states[-1]))
    assert bool(read_ok) and cycles > 0
    for species, count in (("HA", -1), ("A", 1), ("H", 1)):
        moved = after[ids.index(species)] - before[ids.index(species)]
        assert moved == pytest.approx(count * cycles, rel=1e-9), species
    k, h = 2, ids.index("H")  # Row 2 is H at P, the lumen.
    assert int(row_node[k, 0]) == n + o and bool(held[h, n + o]) == closure_at_lumen
    g = np.abs(e.d_j_d_ln_c[0, :, 0])
    free_h = float((p.extracellular_amount_reference + read.extracellular_amount_increment)[h, o])
    by_amount = g[k] / free_h
    slope = float(slopes[k, 0])
    if closure_at_lumen:
        through = sum(g[i] * abs(d[ids.index(s), h, n + o]) for i, s in enumerate(("HA", "A", "H")))
        assert slope == pytest.approx(through, rel=1e-12) and 0 < slope < 1e-2 * by_amount
    else:
        assert slope == pytest.approx(by_amount, rel=1e-12) and slope > 0


# ------------------------------------------- the sodium-calcium exchange (a synthetic rate form)
# sodium_calcium_exchange_symmetric_barrier@1 on one small world of this file's own: heredity cell
# D's rows with calcium, closed, its bath finite and the gauge, with no pump, channel or
# permeability, so nothing moves but the exchanger. Its reference is the rate equation and the two
# ions' electrochemical potentials, as the module writes them, in 60-digit decimals from the SI
# constants: independent of the forms, not code-blind.

SI_F = Decimal("6.02214076e23") * Decimal("1.602176634e-19")  # C/mol
SI_R = Decimal("6.02214076e23") * Decimal("1.380649e-23")  # J/(mol K)
NA_CA_T_K = 310.0  # Heredity cell D's.
NA_CA_MM = dict(cell_0=dict(Ca=2e-4), bath_0=dict(Ca=1.8))  # The reversal is then -30.0 mV.
NA_CA_NU = (3, -3, -1, 1)  # (Na, N), (Na, P), (Ca, N), (Ca, P) per forward cycle.
NA_CA_RT_F = float(SI_R * Decimal(NA_CA_T_K) / SI_F)


def na_ca_entry(law=na_ca.DECLARED_ID, *, name="exchanger_0", k=0.5, km=(20.0, 1e-3), **over):
    """One population of the exchanger (or of `law`), its N the cell."""
    given = dict(
        id=name,
        capacity_fmol_s=k,
        roles={"Na": "Na", "Ca": "Ca"},
        parameters=dict(km_na_mM=km[0], km_ca_mM=km[1]),
    )
    given.update(over)
    return exchanger(law=law, **given)


def na_ca_world(*entries, volts=None, mM=NA_CA_MM, dt=1e-4):
    """Heredity cell D closed and bare: its bath finite and the gauge, no pump, channel or
    permeability; mM's species, calcium among them; the cell at `volts` (its own where None); and
    the exchangers."""
    raw = water_fixtures.heredity_cell("D", dt=dt, end_time=8 * dt)
    m, experiment = raw["model"], raw["experiment"]
    m["species"].append(dict(id="Ca", valence=2))
    z = {e["id"]: e["valence"] for e in m["species"]}
    (cell,), (bath,), (patch,) = m["cells"], m["extracellular"], m["membranes"]
    q = cell["initial_charge_C"] if volts is None else patch["capacitance_F"] * volts
    for node, charge in ((cell, q), (bath, -q)):
        amounts = node["initial_amount_fmol"]
        amounts.update({s: node["volume_pL"] * c for s, c in mM[node["id"]].items()})
        node["initial_charge_C"] = charge
        total = math.fsum(z[s] * n for s, n in amounts.items())
        node["fixed_charge_equivalent_fmol"] = charge / CHARGE_PER_FMOL - total
    bath["reservoir"], m["closure"]["gauge_reference"] = False, bath["id"]
    patch.update(pump=None, permeability_m_per_s=dict.fromkeys(z, 0.0))
    m["channels"], experiment["channel_controls"], experiment["pump_controls"] = [], [], []
    raw["execution"]["channel_capacity"] = 0
    raw["execution"]["material_balance_atol_fmol"]["Ca"] = 1e-10
    m[transporter.MODEL_KEY] = list(entries or [na_ca_entry()])
    return raw


def na_ca_conc(raw):
    """(Na_N, Na_P, Ca_N, Ca_P) of a definition, in mM."""
    nodes = (*raw["model"]["cells"], *raw["model"]["extracellular"])
    return tuple(n["initial_amount_fmol"][s] / n["volume_pL"] for s in ("Na", "Ca") for n in nodes)


def na_ca_start(raw):
    """(spec, implementation, state, layout, control) at the start, inside the caller's scope."""
    spec = parse_spec(copy.deepcopy(raw))
    impl = get_model(spec.model)
    state, p = impl.initial_values(spec)
    return spec, impl, state, p, impl.Control(*(v[0] for v in control_values(spec, [0.0])))


def na_ca_at(spec, state, p, conc):
    """The state whose nodes hold conc = (Na_N, Na_P, Ca_N, Ca_P) in mM, and the concentrations it
    gives back (each amount is a reference plus an increment, so it rounds)."""
    ids = list(spec.model.species_ids)
    inc, out = state.amount_increment.copy(), state.extracellular_amount_increment.copy()
    given = []
    for s, n, o in (("Na", *conc[:2]), ("Ca", *conc[2:])):
        k = ids.index(s)
        inc[k, 0] = n * p.volume[0] - p.amount_reference[k, 0]
        out[k, 0] = o * p.extracellular_volume[0] - p.extracellular_amount_reference[k, 0]
        given.append(float((p.amount_reference[k, 0] + inc[k, 0]) / p.volume[0]))
        stored = p.extracellular_amount_reference[k, 0] + out[k, 0]
        given.append(float(stored / p.extracellular_volume[0]))
    moved = state._replace(amount_increment=inc, extracellular_amount_increment=out)
    return moved, tuple(given)


@functools.cache
def na_ca_exact(conc, volts, k, k_na, k_ca):
    """(J+, J-, x) of the rate equation: J+ = k b^3 c e^(-u/2) / D and J- = k a^3 d e^(u/2) / D, and
    x from the electrochemical potentials of what a forward cycle moves, three Na+ from P to N and
    one Ca2+ from N to P (u = F (phi_N - phi_P)/RT)."""
    with localcontext() as ctx:
        ctx.prec = 60
        u = SI_F * Decimal(volts) / (SI_R * Decimal(NA_CA_T_K))
        na_n, na_p, ca_n, ca_p = map(Decimal, conc)
        a, b = na_n / Decimal(k_na), na_p / Decimal(k_na)
        c, d = ca_n / Decimal(k_ca), ca_p / Decimal(k_ca)
        per = Decimal(k) / ((1 + a**3 + b**3) * (1 + c + d))
        plus, minus = per * b**3 * c * (-u / 2).exp(), per * a**3 * d * (u / 2).exp()
        x = 3 * ((na_n / na_p).ln() + u) - ((ca_n / ca_p).ln() + 2 * u)
        assert abs(minus / plus / x.exp() - 1) < Decimal("1e-50")  # Its own detailed balance.
        return plus, minus, x


def na_ca_slopes(conc, volts, k, k_na, k_ca):
    """(dJ/dpsi, dJ/d ln c at each row), by central differences of the reference in decimals (their
    steps of 1e-20 leave an error far below a double's)."""
    with localcontext() as ctx:
        ctx.prec = 60
        h, per_u, out = Decimal("1e-20"), SI_R * Decimal(NA_CA_T_K) / SI_F, []
        for row in (None, 0, 1, 2, 3):
            ends = []
            for step in (h, -h):
                at = [Decimal(c) * (1 + step if i == row else 1) for i, c in enumerate(conc)]
                v = Decimal(volts) + (step * per_u if row is None else 0)
                plus, minus, _ = na_ca_exact(tuple(at), v, k, k_na, k_ca)
                ends.append(plus - minus)
            out.append((ends[0] - ends[1]) / (2 * h))
        return tuple(out)


def na_ca_reversal(conc):
    """3 E_Na - 2 E_Ca (V), from the two ions' Nernst potentials."""
    na_n, na_p, ca_n, ca_p = conc
    e_na, e_ca = (
        NA_CA_RT_F / z * math.log(o / n) for z, o, n in ((1, na_p, na_n), (2, ca_p, ca_n))
    )
    return 3 * e_na - 2 * e_ca


def na_ca_planted(law_id, *, counts=NA_CA_NU, standard_mM=1.0, power=-3, off=1.0, ends=2, **rate):
    """The exchanger with its form changed: its counts, its activities' standard state, the power of
    K_Na, its constant K_Ca^-1 times `off`, the ends its calcium factor reads, or a field of its
    rate."""
    (base,) = na_ca.CYCLE.monomial.rates
    k_na, k_ca = forms.Scaled("km_na_mM", 1.0, power), base.constants[1]
    sodium, calcium = base.factors
    sodium = sodium._replace(terms=tuple(t._replace(k=k_na) for t in sodium.terms))
    factors = (sodium, calcium._replace(terms=calcium.terms[:ends]))
    constants = (k_na, k_ca._replace(factor=off))
    changed = base._replace(factors=factors, constants=constants, **rate)
    cycle = na_ca.CYCLE._replace(
        modes=(("exchange", counts),),
        monomial=forms.MonomialForm((changed,), standard_state_mM=standard_mM),
    )
    return dataclasses.replace(na_ca.LAW, law_id=law_id, cycle=cycle)


# Each planted law with the criteria (na_ca_misses) it must miss, and no other. The free energy is
# the counts' and the kind's, whatever the synthetic form is: a plant of the form alone keeps the
# reversal, the detailed balance and the heat's sign, and only a plant of the counts misses them.
NA_CA_CRITERIA = {"rate", "slopes", "reversal", "cycle", "balance", "domain"}
OF_THE_FORM, OF_THE_COUNTS = {"rate", "slopes"}, NA_CA_CRITERIA
NA_CA_PLANTS = {
    "split reversed": (na_ca_planted("seamtest.na_ca_split_reversed@1", zeta=0.5), OF_THE_FORM),
    "no split": (na_ca_planted("seamtest.na_ca_no_split@1", zeta=0.0), OF_THE_FORM),
    "K_Na once": (na_ca_planted("seamtest.na_ca_linear_k_na@1", power=-1), OF_THE_FORM),
    "against 1 M": (na_ca_planted("seamtest.na_ca_molar@1", standard_mM=1e3), OF_THE_FORM),
    "off by 1e-9": (na_ca_planted("seamtest.na_ca_off@1", off=1 + 1e-9), OF_THE_FORM),
    "orders exchanged": (
        na_ca_planted("seamtest.na_ca_orders@1", orders=((na_ca.NA_P, 1.0), (na_ca.CA_N, 3.0))),
        OF_THE_FORM,
    ),
    "reverse term": (
        na_ca_planted(
            "seamtest.na_ca_reverse@1", orders=((na_ca.NA_N, 3.0), (na_ca.CA_P, 1.0)), zeta=0.5
        ),
        OF_THE_FORM,
    ),
    "one end in D": (na_ca_planted("seamtest.na_ca_one_end@1", ends=1), OF_THE_FORM),
    "four Na": (na_ca_planted("seamtest.na_ca_four@1", counts=(4, -4, -1, 1)), OF_THE_COUNTS),
    "backward": (na_ca_planted("seamtest.na_ca_backward@1", counts=(-3, 3, 1, -1)), OF_THE_COUNTS),
}
NA_CA_TOL = 2e-13  # Relative to the one-way scale J+ + J-, or to a one-way flux itself.


def na_ca_states():
    """((Na_N, Na_P, Ca_N, Ca_P) in mM, V, whether the domain admits it): random states, and the
    domain's edges, x just inside 80 and just outside, and far below -80 (it is one-sided), with
    calcium from 50 mM down to a trace."""
    rng, out = np.random.default_rng(20261125), []
    for _ in range(24):
        conc = (*10 ** rng.uniform(-1, 2.6, 2), *10 ** rng.uniform(-6, 1, 2))
        out.append((tuple(map(float, conc)), float(rng.uniform(-0.15, 0.15)), True))
    for conc in ((12.0, 140.0, 2e-4, 1.8), (140.0, 12.0, 1e-9, 50.0), (1e-3, 400.0, 10.0, 1e-9)):
        for x in (79.999999, 80.000001, -80.000001, -250.0):  # x = (V - reversal) F/RT.
            out.append((conc, na_ca_reversal(conc) + x * NA_CA_RT_F, x <= 80))
    return out


def na_ca_misses(world, sets):
    """{criterion: [P], whether each population misses it at some state}, for a started world
    (na_ca_start) and its populations' (capacity, K_Na, K_Ca):
    - rate: J, J+ and J- are the rate equation's (NA_CA_TOL);
    - balance: x is the moved ions' electrochemical free energy, so J+/J- = e^(-x); the heat is
      -RT J x and never negative, the guard holds, and nothing works;
    - cycle: the rows change by NA_CA_NU per cycle and the patch carries one charge inward;
    - reversal: J's sign is +, then -, 5 mV below and above 3 E_Na - 2 E_Ca, and J is 0 there;
    - slopes: dJ/dpsi and each dJ/d ln c are the reference's differences;
    - domain: valid exactly where x <= 80."""
    spec, _, state, p, control = world
    misses = {name: np.zeros(len(sets), dtype=bool) for name in sorted(NA_CA_CRITERIA)}
    rt, nu = SI_R * Decimal(NA_CA_T_K), np.array(NA_CA_NU)[:, None]

    def near(name, j, value, exact, scale, tol=NA_CA_TOL):
        misses[name][j] |= not abs(Decimal(float(value)) - exact) <= Decimal(tol) * scale

    def at(conc, volts):
        s, given = na_ca_at(spec, state, p, conc)
        potentials = np.array([volts, 0.0])
        pr = transporter.probe(s, potentials, control, p, xp=np)
        return pr, transporter._evaluate(s, potentials, control, p, xp=np), given

    for i, (conc, volts, admitted) in enumerate(na_ca_states()):
        pr, e, conc = at(conc, volts)
        m, pop, j = pr.modes, pr.populations, np.asarray(pr.modes.j[0])
        misses["domain"] |= np.asarray(pop.valid) != admitted
        misses["balance"] |= ~((pop.heat_pJ_s >= 0) & (pop.work_pJ_s == 0) & (pop.guard <= 0))
        misses["cycle"] |= np.any(np.abs(pr.rows.rate - nu * j) > 8 * U * np.abs(j), axis=0)
        misses["cycle"] |= np.abs(pop.charge_a_to_b_fmol_s + j) > 8 * U * np.abs(j)
        for n, values in enumerate(sets):
            plus, minus, x = na_ca_exact(conc, volts, *values)
            scale = plus + minus
            near("rate", n, j[n], plus - minus, scale)
            near("rate", n, m.j_plus[0, n], plus, plus)
            near("rate", n, m.j_minus[0, n], minus, minus)
            near("balance", n, m.x[0, n], x, Decimal(float(m.x_terms[0, n])), 8 * U)
            if not misses["rate"][n]:  # The heat's value needs the rate's; its sign does not.
                heat = -rt * x * (plus - minus) / 1000
                near("balance", n, pop.heat_pJ_s[n], heat, rt * scale * (abs(x) + 1) / 1000)
            if i < 6:
                d_psi, *d_ln_c = na_ca_slopes(conc, volts, *values)
                near("slopes", n, e.d_j_d_psi[0, n], d_psi, scale, 1e-12)
                for row, d in enumerate(d_ln_c):
                    near("slopes", n, e.d_j_d_ln_c[0, row, n], d, 4 * scale, 1e-12)
        if i < 6:
            head = na_ca_reversal(conc)
            below, zero, above = (at(conc, head + d)[0].modes for d in (-5e-3, 0.0, 5e-3))
            misses["reversal"] |= ~((below.j[0] > 0) & (above.j[0] < 0))
            misses["reversal"] |= ~(np.abs(zero.j[0]) <= NA_CA_TOL * zero.scale[0])
    return misses


NA_CA_RUN_MISSES = {  # The registered law besides: under jit, and under plants of the evaluation.
    "compiled": set(),
    "domain at 79": {"domain"},
    "no slope of its own": {"slopes"},
    "a standard part": NA_CA_CRITERIA - {"cycle"},
    "the flux reversed": NA_CA_CRITERIA - {"cycle"},  # Its heat is negative: the guard refuses it.
}


@pytest.fixture(scope="module")
def na_ca_judged():
    """{plant: the criteria it misses}: None, the registered law, and each planted law, in one world
    that holds six populations of each, every one with its own capacity, K_Na and K_Ca; and the
    registered law's six alone, under jit and under four plants of the kind's evaluation."""
    rng = np.random.default_rng(7)
    spans = ((-4, 1), (0, 2.3), (-5, 0.5))
    sets = [tuple(float(10 ** rng.uniform(*span)) for span in spans) for _ in range(6)]

    def started(laws):
        entries = [
            na_ca_entry(law, name=f"exchanger_{i}_{n}", k=k, km=km)
            for i, law in enumerate(laws)
            for n, (k, *km) in enumerate(sets)
        ]
        return na_ca_start(na_ca_world(*entries))

    def missed(found, i):
        return {name for name, by in found.items() if by[6 * i : 6 * (i + 1)].any()}

    def flat(values):
        return values._replace(d_psi=0.0 * values.d_psi)

    laws = {None: na_ca.LAW} | {name: law for name, (law, _) in NA_CA_PLANTS.items()}
    planted = law_registry.BUILTIN.extended(*(law for law, _ in NA_CA_PLANTS.values()))
    with tk.scoped(), law_registry.scope(planted):
        found = na_ca_misses(started([law.law_id for law in laws.values()]), sets * len(laws))
        world = started([na_ca.LAW.law_id])
    out = {name: missed(found, i) for i, name in enumerate(laws)}
    spec, impl, state, p, control = world
    shifted = p._replace(cycle_standard_RT=p.cycle_standard_RT + 1.0)
    out["a standard part"] = missed(na_ca_misses((spec, impl, state, shifted, control), sets), 0)
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(transporter, "MAX_ABS_AFFINITY_OVER_RT", 79.0)
        out["domain at 79"] = missed(na_ca_misses(world, sets), 0)
    with pytest.MonkeyPatch.context() as patch:
        flux = forms.sign_exact_flux
        patch.setattr(forms, "sign_exact_flux", lambda *a, **kw: -flux(*a, **kw))
        out["the flux reversed"] = missed(na_ca_misses(world, sets), 0)
    with pytest.MonkeyPatch.context() as patch:
        logs = forms.monomial_logs
        patch.setattr(forms, "monomial_logs", lambda *a, **kw: flat(logs(*a, **kw)))
        out["no slope of its own"] = missed(na_ca_misses(world, sets), 0)
    evaluate = jax.jit(lambda s, v, c, q: transporter._evaluate(s, v, c, q, xp=jnp).j)
    q, c = (jax.tree.map(jnp.asarray, tree) for tree in (p, control))
    out["compiled"] = set()
    for conc, volts, _ in na_ca_states():
        s, conc = na_ca_at(spec, state, p, conc)
        j = evaluate(jax.tree.map(jnp.asarray, s), jnp.array([volts, 0.0]), c, q)
        for n, values in enumerate(sets):
            plus, minus, _ = na_ca_exact(conc, volts, *values)
            if abs(Decimal(float(j[0, n])) - plus + minus) > Decimal(NA_CA_TOL) * (plus + minus):
                out["compiled"].add("rate")
    return out


def test_the_exchange_is_registered_as_a_moved_form_with_a_synthetic_rate():
    """Its declaration: hosted by the kind, moved from an older family and never calibrated, its
    Citation saying that only the coupling is supported and that the denominator, the split and
    every number are synthetic, with the works for and against it; a population's parameters its
    only numbers; and no step term of its own."""
    law = law_registry.active().lookup(na_ca.LAW_ID)
    assert law is na_ca.LAW and law.host == transporter.KIND_ID and law.cycle.errors() == []
    assert law.provenance == "parity" and law.source.source.startswith("only the 3:1 coupling")
    assert (
        "every number are synthetic" in law.source.source
        and "no number taken" in law.source.licence
    )
    assert [w.doi for w in law.source.works] == [
        "10.1085/jgp.100.6.963",
        "10.1113/jphysiol.2002.025866",
        "10.1111/j.1469-7793.2000.t01-2-00339.x",
        "10.1038/nature02271",
    ]
    assert law.cycle.parameter_names == ("km_na_mM", "km_ca_mM")
    assert law.reads == ("rapid_binding@1",) and law.forms == "base"
    assert all(getattr(law, name) is None for name in law_registry.STEP_TERMS)


@pytest.mark.parametrize("plant", [None, *NA_CA_RUN_MISSES, *NA_CA_PLANTS], ids=str)
def test_the_exchange_meets_its_rate_equation_and_each_plant_misses_its_criteria(
    na_ca_judged, plant
):
    """The registered law, in NumPy and under jit, meets every criterion of na_ca_misses against the
    60-digit reference, at 24 random states and at 12 of its domain's edges, for six parameter sets;
    each plant misses exactly the criteria it is planted against. The reference is independent of
    the forms, not code-blind."""
    expected = {None: set()} | NA_CA_RUN_MISSES | {name: c for name, (_, c) in NA_CA_PLANTS.items()}
    assert na_ca_judged[plant] == expected[plant]


@pytest.mark.parametrize(
    "volts,booking", [(-0.06, None), (0.02, transporter.TRAPEZOID_BOOKING)], ids=("out", "in")
)
def test_the_exchange_moves_its_counts_and_one_charge_and_closes_every_ledger(volts, booking):
    """Eight host steps of the closed world, calcium going out (below the reversal, the tableau's
    heat) and in (above it, the trapezoid's): per cycle the cell gains three Na+ and loses one Ca2+,
    the finite bath the opposite, and one charge crosses inward, which moves the voltage by the
    capacitor's closed form; the heat grows at every step, nothing works, and every ledger closes.
    Planted, each refused by its ledger: calcium moved twice, and the free energy off by one RT."""
    raw = na_ca_world(na_ca_entry(k=20.0), volts=volts)
    if booking is not None:
        raw = trapezoid_booked(raw)

    def run(impl, spec, p, control, state, steps):
        states = [state]
        for _ in range(steps):
            state, valid = impl.imex_step(state, spec.execution.dt, control, p, xp=np)
            assert bool(valid)
            states.append(state)
        history = impl.STATE_TYPE(*(np.stack(v) for v in zip(*states, strict=True)))
        impl.check_values(history, spec, steps=np.arange(len(states)))  # Every ledger closes.
        return states

    with tk.scoped():
        spec, impl, state, p, control = na_ca_start(raw)
        (check,) = transporter.cycle_checks(spec)
        assert (check.charge_sum, check.charge_moved, check.admitted) == (0, -1, True)
        states = run(impl, spec, p, control, state, 8)
        ends = [impl.readouts(s, control, p, xp=np).field.potential_V for s in (state, states[-1])]
        shifted = p._replace(cycle_standard_RT=p.cycle_standard_RT + 1.0)
        with pytest.raises(NumericalError, match="energy"):
            run(impl, spec, shifted, control, state, 1)
    ids, last = list(spec.model.species_ids), states[-1]
    cycles = float(last.cycle_count[0, 0])
    assert (cycles > 0) == (volts < na_ca_reversal(na_ca_conc(raw))) and cycles != 0
    for s, n in (("Na", 3), ("Ca", -1), ("K", 0)):
        k = ids.index(s)
        assert float(last.amount_increment[k, 0]) == pytest.approx(n * cycles, rel=8 * EPS, abs=0)
        out = float(last.extracellular_amount_increment[k, 0])
        assert out == pytest.approx(-n * cycles, rel=8 * EPS, abs=0), s
    volts_moved = float((ends[1][0] - ends[1][1]) - (ends[0][0] - ends[0][1]))
    charge = CHARGE_PER_FMOL * cycles / spec.model.membranes[0].capacitance_F
    assert volts_moved == pytest.approx(charge, rel=1e-9, abs=0)
    heat = np.stack([s.cycle_dissipated_energy_pJ[0] for s in states])
    assert np.all(np.diff(heat) > 0) and not np.any(last.cycle_metabolic_work_pJ)
    assert not np.any(last.cycle_supplied_fmol)

    def twice(state, potentials, control, p, *, xp):  # Planted: the cell loses two Ca2+ per cycle.
        r = transporter.rates(state, potentials, control, p, xp=xp)
        doubled = xp.where(xp.arange(len(ids))[:, None] == ids.index("Ca"), 2.0, 1.0)
        return r._replace(cell=doubled * r.cell)

    with tk.scoped(dataclasses.replace(transporter.TRANSPORTER, rates=twice)):
        spec, impl, state, p, control = na_ca_start(raw)
        with pytest.raises(NumericalError, match="accounting failed: local"):
            run(impl, spec, p, control, state, 1)


def test_the_exchanges_charge_slope_holds_the_step_at_both_its_ends():
    """The stage term is the reference's |dI/dV| at the cell and at the bath, at every voltage; over
    the cell's capacitance it is the step's charge rate, so a step 1% inside the bound is taken and
    one 1% outside is refused (at the reversal, where nothing moves). Without potentials it fails
    closed. Planted: the kind without its stage term takes the larger step. Its limit, as the module
    states it: the kind's material term counts no charged row that crosses."""
    k, km, mM = 0.5, (20.0, 1e-3), dict(cell_0=dict(Ca=0.1), bath_0=dict(Ca=1.8))
    conc = na_ca_conc(na_ca_world(mM=mM))
    head = na_ca_reversal(conc)
    raw = na_ca_world(na_ca_entry(k=k, km=km), mM=mM, volts=head)
    per_V = float(SI_F / (SI_R * Decimal(NA_CA_T_K)))

    def slope(volts):  # The reference's |dI/dV| (S): one charge per cycle.
        return CHARGE_PER_FMOL * per_V * abs(float(na_ca_slopes(conc, volts, k, *km)[0]))

    rate = slope(head) / raw["model"]["membranes"][0]["capacitance_F"]
    with tk.scoped():
        _, impl, state, p, control = na_ca_start(raw)
        for volts in (-0.15, -0.06, 0.0, 0.06, head):
            term = transporter.stage_term(state, np.array([volts, 0.0]), control, p, xp=np)
            assert list(term) == pytest.approx([slope(volts)] * 2, rel=1e-11, abs=0), volts
        assert np.all(np.isinf(transporter.stage_term(state, None, control, p, xp=np)))
        assert not np.any(transporter.material_term(state, np.array([0.0, 0.0]), control, p, xp=np))
        assert bool(impl.imex_step(state, 0.99 / rate, control, p, xp=np)[1])
        assert not bool(impl.imex_step(state, 1.01 / rate, control, p, xp=np)[1])
    with tk.scoped(dataclasses.replace(transporter.TRANSPORTER, stage_term=None)):
        _, impl, state, p, control = na_ca_start(raw)
        assert bool(impl.imex_step(state, 1.01 / rate, control, p, xp=np)[1])


UNEVEN = na_ca_planted("seamtest.na_ca_uneven@1", counts=(3, -2, -1, 1))  # It creates a charge.
NA_CA_REFUSALS = {  # name: (the entry's changes, the world's, the reason, None where admitted)
    "the twin of the rows below": ({}, {}, None),
    "a stoichiometry": (
        dict(parameters=dict(km_na_mM=20.0, km_ca_mM=1e-3, n_Na=4)), {}, "parameters gives km_na_mM"
    ),
    "a mode that creates charge": (dict(law=UNEVEN.law_id), {}, r"moves charge \+1: every mode"),
    "a missing role": (dict(roles={"Na": "Na"}), {}, "roles binds each of Na, Ca"),
    "a missing species": (dict(roles={"Na": "Na", "Ca": "Sr"}), {}, "a distinct species row"),
    "potassium for calcium": (dict(roles={"Na": "Na", "Ca": "K"}), {}, r"role Ca has valence \+2"),
    "the roles exchanged": (dict(roles={"Na": "Ca", "Ca": "Na"}), {}, r"role Na has valence \+1"),
    "a half-saturation of zero": (dict(km=(0.0, 1e-3)), {}, "parameter km_na_mM is positive"),
    "a held ion": (dict(held_rows=[["Na", "P"]]), {}, "a held row is neutral in this pass"),
    "x inside 80": ({}, dict(x=79.5), None),
    "x outside 80": ({}, dict(x=80.5), "domain invalid"),
    "x far below -80": ({}, dict(x=-95.0), None),
    "RK4": ({}, dict(solver="rk4"), "require an IMEX solver"),
}  # fmt: skip


@pytest.mark.parametrize("name", NA_CA_REFUSALS)
def test_an_exchange_population_is_refused_with_its_reason(name):
    """A stoichiometry (the law's, never a population's), a mode that creates charge, a missing or a
    wrong species, a half-saturation of zero, a held ion, a start outside the domain (one-sided, by
    its concentrations) and RK4 are each refused by name; the twin without the fault is admitted."""
    over, world, reason = NA_CA_REFUSALS[name]
    mM = NA_CA_MM
    if "x" in world:  # The bath's Na from x = 3 ln(Na_N/Na_P) + ln(Ca_P/Ca_N), the cell at 0 V.
        ca_n, ca_p = (1e-9, 50.0) if world["x"] > 0 else (50.0, 1e-9)
        na_p = na_ca_conc(na_ca_world())[0] * math.exp((math.log(ca_p / ca_n) - world["x"]) / 3)
        mM = dict(cell_0=dict(Ca=ca_n), bath_0=dict(Ca=ca_p, Na=na_p))
    raw = na_ca_world(na_ca_entry(**over), mM=mM, volts=0.0)
    raw["execution"]["solver"] = world.get("solver", raw["execution"]["solver"])
    with tk.scoped(), law_registry.scope(law_registry.BUILTIN.extended(UNEVEN)):
        if reason is None:
            parse_spec(raw)
        else:
            with pytest.raises(ConfigError, match=reason):
                parse_spec(raw)


def test_the_exchange_reads_a_closures_free_calcium():
    """Beside a calcium binder that the general closure holds at the cell (0.1 mM, K_d 1 uM: the
    free calcium is 1/84 of the total), the population reads the free calcium and moves the total's
    base row: x is the free concentration's, and one step takes its cycles from the total and closes
    every ledger. Planted: x at the stored total (off by ln 84); and, refused at the closure's row,
    the law without the read and the law without base forms."""
    from cells.kinds import proton_buffer

    free, k_d, binder = 2e-4, 1e-3, 0.1  # mM
    total = free + binder * free / (free + k_d)

    def world(law=na_ca.DECLARED_ID):
        raw = na_ca_world(na_ca_entry(law), mM=dict(cell_0=dict(Ca=total), bath_0=dict(Ca=1.8)))
        m = raw["model"]
        m["standard_concentration_mM"] = 1.0
        m["species"][-1]["standard_mu_RT"] = 0.0
        add_species(raw, "B", -2, 0.0, {"cell_0": binder, "bath_0": 1e-9})
        bound = dict(id="CaB", counts={"Ca": 1}, standard_mu_RT=math.log(k_d))
        m["species"][-1]["forms"] = [bound]
        m[proton_buffer.MODEL_KEY] = [
            dict(
                read_id="rapid_binding@1",
                ligand_rows=["Ca"],
                binders={"cell_0": ["B"]},
                k_on_per_mM_s={"B": {"Ca": 1e6}},
            )
        ]
        return raw

    unread = dataclasses.replace(na_ca.LAW, law_id="seamtest.na_ca_unread@1", reads=())
    formless = dataclasses.replace(na_ca.LAW, law_id="seamtest.na_ca_formless@1", forms=None)
    laws = law_registry.BUILTIN.extended(unread, formless)
    with tk.scoped(*tk.CHARGED_KINDS), law_registry.scope(laws):
        spec, impl, state, p, control = na_ca_start(world())
        volts = np.asarray(impl.readouts(state, control, p, xp=np).field.potential_V)
        read, ok = proton_buffer.stage_read(state, p, xp=np)
        after, valid = impl.imex_step(state, spec.execution.dt, control, p, xp=np)
        history = impl.STATE_TYPE(*(np.stack(v) for v in zip(state, after, strict=True)))
        impl.check_values(history, spec, steps=np.arange(2))  # Every ledger closes.
        for law, reason in ((unread, "lack rapid_binding@1"), (formless, "declares no base forms")):
            with pytest.raises(ConfigError, match=reason):
                parse_spec(world(law.law_id))
    assert bool(ok) and bool(valid)
    m = transporter.probe(read, volts, control, p, xp=np).modes
    na_n, na_p, _, ca_p = na_ca_conc(world())
    x = 3 * math.log(na_n / na_p) + math.log(ca_p / free) + float(volts[0] - volts[1]) / NA_CA_RT_F
    assert float(m.x[0, 0]) == pytest.approx(x, rel=0, abs=1e-11)  # The free calcium's, as solved.
    assert abs(float(m.x[0, 0]) - (x - math.log(total / free))) > 4  # Planted: the total's.
    ca, cycles = list(spec.model.species_ids).index("Ca"), float(after.cycle_count[0, 0])
    assert cycles != 0
    assert float(after.amount_increment[ca, 0]) == pytest.approx(-cycles, rel=8 * EPS, abs=0)


def test_an_exchange_world_restarts_bitwise_from_its_checkpoint_file(tmp_path):
    """Eight host steps, and four from a checkpoint file written after the first four, end in the
    same state bit for bit, the cycles and the heat with them. Planted: a checkpoint that lost its
    cycles is refused by its ledgers, and one unit in the last place of the restored calcium shows
    at the end. Host steps through the runner's own checkpoint file: nothing compiles."""
    from cells.execution.runner import timeline
    from cells.execution.state import initialise
    from cells.records.io import load_snapshot, write_snapshot

    def stepped(state, n):
        for _ in range(n):
            state, valid = impl.imex_step(state, spec.execution.dt, control, p, xp=np)
            assert bool(valid)
        return state

    with tk.scoped():
        spec, impl, state, p, control = na_ca_start(na_ca_world())
        half = stepped(state, 4)
        whole = stepped(half, 4)
        at = dict(time=float(timeline(spec)[4]), step_index=4)
        checkpoint = dataclasses.replace(initialise(spec), state=half, **at)
        snapshot = load_snapshot(write_snapshot(tmp_path / "half", spec, checkpoint))
        restored = impl.STATE_TYPE(*(np.asarray(v) for v in snapshot.checkpoint.state))
        resumed = stepped(restored, 4)
        lost = half._replace(cycle_count=np.zeros_like(half.cycle_count))
        with pytest.raises(NumericalError, match="accounting failed"):
            write_snapshot(tmp_path / "lost", spec, dataclasses.replace(checkpoint, state=lost))
        ca = (list(spec.model.species_ids).index("Ca"), 0)
        nudged = restored.amount_increment.copy()
        nudged[ca] = np.nextafter(nudged[ca], np.inf)
        other = stepped(restored._replace(amount_increment=nudged), 4)
    assert float(whole.cycle_count[0, 0]) != 0
    for name, a, b in zip(impl.STATE_TYPE._fields, whole, resumed, strict=True):
        assert np.array_equal(np.asarray(a), np.asarray(b)), name
    assert not np.array_equal(other.amount_increment, whole.amount_increment)


# ------------------------------------------------------------------ M2 on this device (amendment 2)

M2 = {"log": 1.0, "exp": 2.0, "expm1": 4.0, "log1p": 2.0}


def _exact(name, v):
    """The function's value at the double v, to 60 digits (more near 0 for expm1 and log1p)."""
    extra = 10 + (max(0, -int(math.floor(math.log10(abs(float(v)))))) if v else 0)
    with localcontext() as ctx:
        ctx.prec = 60 + (extra if name in ("expm1", "log1p") else 0)
        d = Decimal(float(v))
        if name == "log":
            return +d.ln()
        if name == "exp":
            return +d.exp()
        return +(d.exp() - 1) if name == "expm1" else +((1 + d).ln())


def test_the_transcendental_functions_keep_m2_under_jit_on_this_device_and_in_numpy():
    rng = np.random.default_rng(11)
    draws = {
        "log": 10.0 ** rng.uniform(-20, 10, 1500),
        "exp": rng.uniform(-300, 300, 1500),
        "expm1": np.concatenate([rng.uniform(-80, 80, 1000), 10.0 ** rng.uniform(-300, -3, 500)]),
        "log1p": np.concatenate([rng.uniform(-0.999, 1e3, 1000), 10.0 ** rng.uniform(-300, -3, 500)]),
    }
    for name, args in draws.items():
        for impl in (jax.jit(getattr(jnp, name)), getattr(np, name)):
            got = np.asarray(impl(jnp.asarray(args) if impl is not getattr(np, name) else args))
            worst = max(
                float(abs(Decimal(float(y)) - _exact(name, x)) / Decimal(math.ulp(float(_exact(name, x)))))
                for x, y in zip(args, got, strict=True)
            )
            assert worst <= M2[name], (name, impl, worst)
    # Planted: a function one ulp off everywhere for exp fails a 0.5-ulp claim.
    off = np.nextafter(np.exp(draws["exp"]), np.inf)
    worst = max(float(abs(Decimal(float(y)) - _exact("exp", x)) / Decimal(math.ulp(float(_exact("exp", x))))) for x, y in zip(draws["exp"], off, strict=True))
    assert worst > 0.5
