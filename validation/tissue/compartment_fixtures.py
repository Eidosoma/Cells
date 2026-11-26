"""Small worlds for cells.operator.cell_owned_compartments@1 (FR-1, docs/CLOSED_COMPARTMENT_DESIGN.md).

All values are synthetic. The base worlds are secreted_species_fixtures' quiescent worlds (passive
cells, zero ion permeability on every patch, no pump, every node at the bath's ion composition with
a zero charge anchor).

* loaded_compartment: W, D150's face-free topology (§1.2): cell_0 with its wall patch on the held
  bath `bath`, and its contact patch `contact_0` the only patch of the finite node ecs_0, which no
  face names. ecs_0 is the compartment, contact_0 its bounding patch, cell_0 its owner. Exchange
  loads the neutral species S from the cytosol into it (a first-order export, loading with
  retention); `declared=False` gives the same world without the declaration. W's ions are
  quiescent, so its potentials are all 0 and silence cannot fail there (S5's worlds use it).
* live_compartment: W+, W with a live owner (the lead's ruling after milestone 1's first hand-back):
  a cytosol at K 140, Na 10 and Cl 20 mM, a K leak on the owner's wall patch and an initial owner
  potential of -0.06 V through its charge anchor, so K leaves and the owner's potential moves
  toward E_K. Planted controls, for tests that bypass the declaration's refusals 4 and 5 in a
  test-only way: `planted_route`, a K permeability on the bounding patch, and `planted_anchor`, a
  compartment charge anchor (C). Either must break silence.
* without_compartment / live_without_compartment: W or W+ without ecs_0 and contact_0 (and so
  without the declaration and the route): S4's comparison.
* with_compartments: the declaration's block on any composite definition.
* silence: S1 to S3 on every row of a run's or a window's observations, for any compartment, with
  what shows the check is live (the owner's ion rows moving, its potential).
* bindings and traced: what S5 compares (D148's "what crossrev compares"), through
  validation/tissue/composite_crossrev's own tracing: every initial state, layout and control
  array at every schedule time and the device-check constants; and the jaxpr text of the checked
  step, right-hand side and device row checks with the record of their closed-over constants.
"""

import copy
import math

import numpy as np

from validation.tissue import composite_crossrev as crossrev
from validation.tissue import secreted_species_fixtures as fx

LAW = "cells.operator.cell_owned_compartments@1"
NODE, PATCH, OWNER = "ecs_0", "contact_0", "cell_0"
LOAD_ROUTE = "load"
WALL = "wall_cell_0"
OWNER_mM = dict(Na=10.0, K=140.0, Cl=20.0)  # A cytosol: K high, Na and Cl low.
OWNER_V0 = -0.06  # V: the owner's initial potential, through its charge anchor.
WALL_K = 5e-10  # m/s of K on the owner's wall patch: K leaves toward E_K, at about 13/s.
PLANTED_ROUTE = 1e-13  # m/s of K on the bounding patch: planted control (a).
PLANTED_ANCHOR_C = 1e-17  # C on the compartment: planted control (b), V_b = -1e-4 V.


def compartment(
    cid="lys_0",
    node=NODE,
    patch=PATCH,
    owner=OWNER,
    label="lysosome pool",
    reference=None,
    role=None,
):
    """One declaration entry: its own ID `cid`, its node (storage), patch and owner; `role` is
    omitted (the default) when None."""
    entry = dict(id=cid, node=node, patch=patch, owner=owner, label=label, reference=reference)
    return entry if role is None else entry | dict(role=role)


def with_compartments(raw, compartments):
    """compartments: the declaration's entries (compartment(...) dicts)."""
    out = copy.deepcopy(raw)
    out["model"]["operators"].append(dict(law=LAW, compartments=[dict(c) for c in compartments]))
    return out


def loaded_compartment(
    *,
    dt=1e-3,
    end=0.02,
    solver=fx.IMEX,
    observation_times=None,
    export=0.2,
    changes=(),
    declared=True,
    pool_mM=1e-3,
    lumen_mM=1e-6,
    turnover=False,
):
    """The silence world W (module docstring). export: the loading rate (1/s); changes: later
    (time, rate) changes of it; turnover: also clear S at the node (degradation inside)."""
    raw = fx.face_free(
        pool_mM=pool_mM,
        node_mM=lumen_mM,
        dt=dt,
        end=end,
        solver=solver,
        observation_times=observation_times or fx.grid_times(end, dt, dt),
    )
    raw = fx.with_exchange(
        raw,
        [(LOAD_ROUTE, PATCH, "export", "first_order")],
        [(LOAD_ROUTE, OWNER, [(0.0, export), *changes])],
    )
    if turnover:
        raw = fx.with_turnover(
            raw, [("degrade", NODE, "clearance")], [("degrade", None, [(0.0, 0.5)])]
        )
    return with_compartments(raw, [compartment()]) if declared else raw


def without_compartment(*, dt=1e-3, end=0.02, solver=fx.IMEX, observation_times=None, pool_mM=1e-3):
    """S4's comparison world: W without ecs_0, contact_0, the route and the declaration."""
    return fx.world(
        cells=((OWNER, 1.0),),
        nodes=(),
        baths=("bath",),
        contacts=(),
        faces=(),
        dt=dt,
        end=end,
        solver=solver,
        observation_times=observation_times or fx.grid_times(end, dt, dt),
        concentrations_mM={OWNER: pool_mM},
    )


def _anchor(node, charge):
    """Set a node's charge anchor to `charge` (C), its fixed charge to match (the anchor rule)."""
    from cells.laws.electrochemistry import CHARGE_PER_FMOL

    ions = math.fsum(z * node["initial_amount_fmol"][s] for s, z in fx.ION_SPECIES)
    node["initial_charge_C"] = charge
    node["fixed_charge_equivalent_fmol"] = charge / CHARGE_PER_FMOL - ions


def _live(raw, *, planted_route=0.0, planted_anchor=0.0):
    """W+'s owner (module docstring), and the planted controls, on W's or S4's definition."""
    m = raw["model"]
    owner = next(c for c in m["cells"] if c["id"] == OWNER)
    for species, mM in OWNER_mM.items():
        owner["initial_amount_fmol"][species] = mM * owner["volume_pL"]
    wall = next(p for p in m["membranes"] if p["id"] == WALL)
    wall["permeability_m_per_s"]["K"] = WALL_K
    _anchor(owner, wall["capacitance_F"] * OWNER_V0)
    if planted_route:
        bounding = next(p for p in m["membranes"] if p["id"] == PATCH)
        bounding["permeability_m_per_s"]["K"] = planted_route
    if planted_anchor:
        _anchor(next(o for o in m["extracellular"] if o["id"] == NODE), planted_anchor)
    return raw


def live_compartment(*, planted_route=0.0, planted_anchor=0.0, **kwargs):
    """W+ (module docstring); kwargs as loaded_compartment's."""
    raw = loaded_compartment(**kwargs)
    return _live(raw, planted_route=planted_route, planted_anchor=planted_anchor)


def live_without_compartment(**kwargs):
    """S4's comparison world for W+: W+ without ecs_0, contact_0, the route and the declaration."""
    return _live(without_compartment(**kwargs))


def bindings(raw):
    """{name: array} of a definition's bindings (composite_crossrev.bindings' arrays)."""
    from cells.definitions.specs import parse_spec
    from cells.execution.schedule import control_values
    from cells.registry.models import get_model

    spec = parse_spec(raw)
    model = get_model(spec.model)
    state, layout = model.initial_values(spec)
    times = sorted({0.0, *(c.time for c in spec.experiment.changes), spec.experiment.end_time})
    arrays = {}
    for prefix, tree in (
        ("state.", state),
        ("layout.", layout),
        ("control.", control_values(spec, times)),
    ):
        for key, value in tree._asdict().items():
            arrays[prefix + key] = np.asarray(value)
    for key, value in crossrev.check_constants(model, spec):
        arrays["check." + key] = value
    return arrays


def traced(raw):
    """{program: (jaxpr text, constants record)} for the checked step, rhs and device checks."""
    closed = crossrev._traced(*crossrev._setup(raw))
    return {
        kind: (str(program), crossrev.const_record(program)) for kind, program in closed.items()
    }


def same_bindings(a, b):
    """The names whose dtype, shape or bytes differ, or that one side lacks (empty: identical)."""
    names = sorted(set(a) | set(b))
    return [
        k
        for k in names
        if k not in a
        or k not in b
        or (a[k].dtype, a[k].shape, a[k].tobytes()) != (b[k].dtype, b[k].shape, b[k].tobytes())
    ]


def silence(spec, observations, *, node=NODE, patch=PATCH, owner=OWNER):
    """S1 to S3 (design §3.3) on every row of `observations`, a run's or a window's columns.

    {s1: every ion row of the node's extracellular_amount_increment equals its initial value
    bitwise; s2: the largest |V_b| over (CHARGE_ATOL_C + CHARGE_RTOL |C_b V_b|) / C_b, with
    q_comp = 0 (exactly so once S1 holds, since the node's charge is its zero anchor plus its ion
    increments); s3: the largest capacitor energy (1/2) C_b V_b^2 over
    (1/2) (CHARGE_ATOL_C + CHARGE_RTOL |C_b V_b|)^2 / C_b; rows; and what shows the check is live:
    owner_ions_moved (an ion row of the owner's amount_increment left its initial value),
    max_phi_owner and max_phi_node (the largest |potential|), loaded (S's increment at the node
    over the rows, when S is declared)}. S2 and S3 hold when their ratios are at most 1.
    """
    from cells.numerics import surface_field as field
    from cells.registry.models import get_model

    model = get_model(spec.model)
    state, _ = model.initial_values(spec)
    ions = [i for i, z in enumerate(spec.model.valence) if z != 0]
    j = [c.id for c in spec.model.extracellular].index(node)
    k = [p.id for p in spec.model.membranes].index(patch)
    i = [c.id for c in spec.model.cells].index(owner)
    initial = np.asarray(state.extracellular_amount_increment)[ions, j]
    increment = np.asarray(observations.extracellular_amount_increment)
    rows = np.ascontiguousarray(increment[:, ions, j])
    expected = np.ascontiguousarray(np.broadcast_to(initial, rows.shape))
    owned = np.asarray(observations.amount_increment)[:, ions, i]
    owner_initial = np.asarray(state.amount_increment)[ions, i]
    c_b = spec.model.membranes[k].capacitance_F
    v = np.asarray(observations.membrane_voltage_V)[:, k]
    allowance = field.CHARGE_ATOL_C + field.CHARGE_RTOL * np.abs(c_b * v)
    species = list(spec.model.species_ids)
    s = species.index(fx.SPECIES) if fx.SPECIES in species else None
    return dict(
        s1=rows.dtype == expected.dtype and rows.tobytes() == expected.tobytes(),
        s2=float(np.max(np.abs(v) / (allowance / c_b))),
        s3=float(np.max((0.5 * c_b * v**2) / (0.5 * allowance**2 / c_b))),
        rows=int(v.shape[0]),
        owner_ions_moved=bool(np.any(owned != owner_initial[None, :])),
        max_phi_owner=float(np.max(np.abs(np.asarray(observations.cell_potential_V)[:, i]))),
        max_phi_node=float(
            np.max(np.abs(np.asarray(observations.extracellular_potential_V)[:, j]))
        ),
        loaded=None if s is None else float(increment[-1, s, j] - increment[0, s, j]),
    )


def assert_silent_and_live(spec, observations, rows=None):
    """S1 to S3 hold on every row, and the check is live: W+'s owner moves ions at a nonzero
    potential. Returns the row count."""
    found = silence(spec, observations)
    assert found["s1"], "S1: an ion row of the compartment changed"
    assert found["s2"] <= 1.0, f"S2: |V_b| at {found['s2']} of its bound"
    assert found["s3"] <= 1.0, f"S3: the capacitor energy at {found['s3']} of its bound"
    assert found["owner_ions_moved"] and found["max_phi_owner"] >= 0.05, ("not live", found)
    assert rows is None or found["rows"] == rows
    return found["rows"]


def assert_broken(spec, observations, *, route):
    """A planted control breaks silence: S2 always; S1 too for a planted ion route."""
    found = silence(spec, observations)
    assert found["s2"] > 1.0, ("the planted control kept S2", found)
    if route:
        assert not found["s1"], ("the planted route kept S1", found)
    return found


def identity_differences(build):
    """S5's comparison of build(True) (declared) with build(False): what differs (empty: none).

    Each traced program's jaxpr text and closed-over constants, then the bindings by name."""
    with_it, without = build(True), build(False)
    a, b = traced(with_it), traced(without)
    found = [] if a.keys() == b.keys() else ["programs: " + str(sorted(set(a) ^ set(b)))]
    for kind in sorted(set(a) & set(b)):
        if a[kind][0] != b[kind][0]:
            found.append(f"{kind}: jaxpr text")
        if a[kind][1] != b[kind][1]:
            found.append(f"{kind}: closed-over constants")
    return found + [f"binding {k}" for k in same_bindings(bindings(with_it), bindings(without))]
