"""cells.transporter@1's population axis: seam A's general layout (the kinds owner's design
statement 1, confirmed 18 November 2026, and its amendments).

Each claim with its plant (D187); every world is this file's own (no seam-A reference state):
- selection (§1): a declaration in version 1's form keeps today's structure entry, fields and hooks
  (planted: an entry that does not remove the axis's hooks); the general form, two populations on
  one patch and finite fuel under the neutral law take the population axis; each entry writes
  back in the form it was declared in;
- the general parse refuses with its reason (unknown host, orientation, roles, valence, ranges,
  held rows, fuel kinds, a charged held row (Q4), chemistry at P (Q3), duplicate IDs);
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
- M2 (amendment 2): log, exp, expm1 and log1p within 1, 2, 4 and 2 ulp under jit on this device and
  in NumPy, against 60-digit decimals.
"""

import contextlib
import copy
import dataclasses
import math
from decimal import Decimal, localcontext

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.definitions.surface_pump_v3_spec import control_values
from cells.kinds import transporter
from cells.laws.electrochemistry import CHARGE_PER_FMOL, F, R
from cells.laws.cycles import forms
from cells.laws.cycles.forms import CycleForm, Diagram, FluxTerm, Saturation
from cells.models import surface_pump_v3
from cells.registry import kind_registry
from cells.registry import laws as law_registry
from cells.registry.models import get_model
from tests.unit import test_cycle_forms as tf
from tests.unit import test_transporter_kind as tk

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
    # with role_species, §5.2's admission's reading, which both layouts carry (host-side), and the
    # schedule's two definition-time hooks (D228 item 5): parse_schedule returns None without its
    # key and refuses it on version 1's layout, so its programs and change records are today's.
    hooks = [f.name for f in dataclasses.fields(bound) if callable(getattr(bound, f.name))]
    assert sorted(hooks) == sorted(
        ["parse", "to_dict", "structure_entry", "initial", "control_values", "rates",
         "stage_term", "bound_rate", "held_rows", "ledger_terms", "domain", "readouts",
         "moved_rows", "check_definition", "role_species", "parse_schedule", "schedule_to_dict"]
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
    with scoped(), pytest.raises(ConfigError, match="chemistry at P is refused in this pass"):
        parse_spec(raw)
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
    for form_name, reason in (("total", "read only where a closure holds the row"),
                              ("Mg", "read only where a closure holds the row")):
        total = rate._replace(orders=((forms.Reference("X", "N", form_name), 1.0),))
        law = dataclasses.replace(
            MONO, law_id=f"seamtest.monomial_{form_name.lower()}@1",
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
