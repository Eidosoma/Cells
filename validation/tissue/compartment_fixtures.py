"""Small worlds for cell_owned_compartments@1 (FR-1, docs/CLOSED_COMPARTMENT_DESIGN.md).

All values are synthetic. The worlds are secreted_species_fixtures' quiescent worlds (passive
cells, zero ion permeability on every patch, no pump, every node at the bath's ion composition with
a zero charge anchor), so the compartment is neutral and silent by construction (design §3.3).

* loaded_compartment: D150's face-free topology (§1.2): cell_0 with its wall patch on the held bath
  `bath`, and its contact patch `contact_0` the only patch of the finite node ecs_0, which no face
  names. ecs_0 is the compartment, contact_0 its bounding patch, cell_0 its owner. Exchange loads
  the neutral species S from the cytosol into it (a first-order export, loading with retention);
  `declared=False` gives the same world without the declaration.
* without_compartment: the same world without ecs_0 and contact_0 (and so without the
  declaration and the route): S4's comparison.
* with_compartments: the declaration's block on any composite definition.
* bindings and traced: what S5 compares (D148's "what crossrev compares"), through
  validation/tissue/composite_crossrev's own tracing: every initial state, layout and control
  array at every schedule time and the device-check constants; and the jaxpr text of the checked
  step, right-hand side and device row checks with the record of their closed-over constants.
"""

import copy

import numpy as np

from validation.tissue import composite_crossrev as crossrev
from validation.tissue import secreted_species_fixtures as fx

LAW = "cell_owned_compartments@1"
NODE, PATCH, OWNER = "ecs_0", "contact_0", "cell_0"
LOAD_ROUTE = "load"


def compartment(node=NODE, patch=PATCH, owner=OWNER, label="lysosome pool", reference=None):
    return dict(node=node, patch=patch, owner=owner, label=label, reference=reference)


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


def bindings(raw):
    """{name: array} of a definition's bindings (composite_crossrev.bindings' arrays)."""
    from cells.core.schedule import control_values
    from cells.core.specs import parse_spec
    from cells.models.registry import get_model

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


def silence(spec, observations):
    """S1 to S3 (design §3.3) on every row of `observations`, a run's or a window's columns.

    {s1: every ion row of the node's extracellular_amount_increment equals its initial value
    bitwise; s2: the largest |V_b| over (CHARGE_ATOL_C + CHARGE_RTOL |C_b V_b|) / C_b, with
    q_comp = 0 (exactly so once S1 holds, since the node's charge is its zero anchor plus its ion
    increments); s3: the largest capacitor energy (1/2) C_b V_b^2 over
    (1/2) (CHARGE_ATOL_C + CHARGE_RTOL |C_b V_b|)^2 / C_b; rows; loaded: S's increment at the node
    over the rows (the loading moves S while no ion moves)}. S2 and S3 hold when their ratios are
    at most 1.
    """
    from cells.models.registry import get_model
    from cells.numerics import surface_field as field

    model = get_model(spec.model)
    state, _ = model.initial_values(spec)
    ions = [i for i, z in enumerate(spec.model.valence) if z != 0]
    s = list(spec.model.species_ids).index(fx.SPECIES)
    j = [c.id for c in spec.model.extracellular].index(NODE)
    k = [p.id for p in spec.model.membranes].index(PATCH)
    initial = np.asarray(state.extracellular_amount_increment)[ions, j]
    increment = np.asarray(observations.extracellular_amount_increment)
    rows = np.ascontiguousarray(increment[:, ions, j])
    expected = np.ascontiguousarray(np.broadcast_to(initial, rows.shape))
    c_b = spec.model.membranes[k].capacitance_F
    v = np.asarray(observations.membrane_voltage_V)[:, k]
    allowance = field.CHARGE_ATOL_C + field.CHARGE_RTOL * np.abs(c_b * v)
    return dict(
        s1=rows.dtype == expected.dtype and rows.tobytes() == expected.tobytes(),
        s2=float(np.max(np.abs(v) / (allowance / c_b))),
        s3=float(np.max((0.5 * c_b * v**2) / (0.5 * allowance**2 / c_b))),
        rows=int(v.shape[0]),
        loaded=float(increment[-1, s, j] - increment[0, s, j]),
    )
