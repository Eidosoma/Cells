"""Compiled guards of Q4's limits (S5 design §7.3), at 0.25 ms.

* Symmetric division (f = a_k = 1/2): the daughters stay equal to rounding afterwards. Every
  state field with a cell, patch or population axis is compared, slot against twin slot, on
  every row after the event (the event itself is bitwise; test_partition.py).
* a = 0: once the bridge has closed, a small current into d1 couples into d2 as the
  trans-cleft T-network does, d1 and d2 joined through their furrows to the cleft and the cleft
  to the bath through the access face; and as the same world without a bridge does.
* Sealed (A/L = 0): with the access face removed, the daughters join through their two furrow
  membranes in series, R_j = 1/G_f1 + 1/G_f2 = 2 r_new / A_face.
The circuit predictions use small-signal conductances computed here from the declared laws at
the base run's state: each patch's constant-field slope dI/dV, and the access face's
(F^2/RT) sum z^2 D (A/L) c_logmean. The voltages are changes from the same world without
current, after a settling time of more than ten of its slowest time constants.

The furrow world for the circuit limits is S5's compact furrow world (cleft_divided, symmetric,
passive) with three value changes: every membrane permeability x 100, which brings the
membrane time constant from about 1.5 s to 15 ms and keeps each patch's reversal potential;
the daughters' furrows stop inserting at the division, so the geometry holds still; and the
access face's area is 1.5e-13 m^2, so its resistance is comparable with a furrow's.

Stated tolerances: the circuit quantities (coupling, cleft over d1, input resistance, R_j) to
1%; the closed bridge against no bridge to 1e-9; the symmetric daughters to 64 eps x each
field's scale (and each potential to 64 eps of itself). The development measurement
(/mnt/workspaces/Cells/cell-division-s5-20261113-01/probe/limits-1.json, from the worktree at
2845b3f) found the circuit quantities within 6e-4, the closed bridge's response identical to
the bridge-free world's, and the symmetric daughters equal in every field and potential.
A few minutes on one core (seven compiled runs).
"""

import copy
import math

import jax
import numpy as np
import pytest

from cells.core.runner import run
from cells.core.specs import parse_spec
from cells.models import pump_composite_adapter as adapter
from cells.models.registry import get_model
from cells.processes.electrochemistry import CHARGE_PER_FMOL, F, R
from tests import partition_fixtures as fx

DT = 2.5e-4
CLOSED = 0.003  # The bridge's linear closure ends here: division at 2 ms, tau 1 ms.
END = 0.25  # Settling: the slowest time constant is about 15 ms.
CURRENT_A = 1e-14
SCALE = 100.0  # Membrane permeabilities.
ACCESS_AREA_M2 = 1.5e-13
EPS = float(np.finfo(float).eps)


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


def passive(raw):
    """raw without channel populations (in place)."""
    raw["model"]["channels"] = []
    raw["experiment"]["channel_controls"] = []
    raw["execution"]["channel_capacity"] = 0
    for block in raw["model"]["operators"]:
        if block["law"] == "membrane_entity_state@1":
            block["populations"] = []
        for division in block.get("divisions", []):
            division["populations"] = []
    return raw


def furrow_world(*, bridge, injected, sealed=False):
    """The circuit limits' furrow world (module docstring), raw."""
    kw = dict(injection=CURRENT_A, injection_start=CLOSED) if injected else {}
    raw = fx.cleft_divided(end=END, bridge=("linear", 0.001) if bridge else None, **kw)
    passive(raw)
    m, e = raw["model"], raw["experiment"]
    for patch in m["membranes"]:
        patch["permeability_m_per_s"] = {
            s: SCALE * v for s, v in patch["permeability_m_per_s"].items()
        }
    for control in e["insertion_controls"]:
        if control["membrane_id"] != "furrow":  # The daughters' furrows: no insertion.
            control["schedule"] = [dict(time=0.0, rate_m2_per_s=0.0)]
    if sealed:
        m["faces"] = []
    else:
        m["faces"][0]["area_m2"] = ACCESS_AREA_M2
    raw["execution"].update(dt=DT, max_steps=int(math.ceil(END / DT)) + 8)
    e["observation_times"] = [0.0, END]
    return raw


def final(raw):
    """(spec, model, layout, final state, control at the end) of one compiled run."""
    spec = parse_spec(raw)
    model = get_model(spec.model)
    result = run(spec)
    _, p = model.initial_values(spec)
    state = model.STATE_TYPE(*(np.asarray(v[-1]) for v in result.history))
    control = model.CONTROL_TYPE(*(np.asarray(v[0]) for v in fx.cs.control_values(spec, [END])))
    return spec, model, p, state, control


def potentials(spec, model, p, state):
    """{cell or node id: potential (V)} with the held bath at 0."""
    q = model.view(p, state, xp=np)
    phi = adapter.node_potentials(state, q, xp=np)
    names = [c.id for c in spec.model.cells] + [c.id for c in spec.model.extracellular]
    return dict(zip(names, (float(x) for x in phi), strict=True))


def concentrations(spec, model, p, state):
    """{cell or node id: mM per species} at the view."""
    q = model.view(p, state, xp=np)
    cells = np.asarray(p.amount_reference) + np.asarray(state.amount_increment)
    nodes = np.asarray(p.extracellular_amount_reference) + np.asarray(
        state.extracellular_amount_increment
    )
    out = {c.id: cells[:, i] / np.asarray(p.volume)[i] for i, c in enumerate(spec.model.cells)}
    for i, c in enumerate(spec.model.extracellular):
        out[c.id] = nodes[:, i] / np.asarray(q.extracellular_volume)[i]
    return out


def slope_conductance(patch, spec, model, p, state):
    """dI/dV of a constant-field patch at its voltage (S), computed here from the law."""
    k = [m.id for m in spec.model.membranes].index(patch.id)
    q = model.view(p, state, xp=np)
    area = float(np.asarray(p.membrane_area)[k] + np.asarray(state.membrane_area_increment_m2)[k])
    phi, c = potentials(spec, model, p, state), concentrations(spec, model, p, state)
    ci, co = c[patch.inside], c[patch.outside]
    z, perm = np.ravel(p.valence), np.asarray(p.membrane_permeability)[:, k]
    rt = R * spec.model.temperature_K
    assert q.membrane_active[k]

    def outward(v):  # Goldman-Hodgkin-Katz current, cell to outside (A).
        u = z * F * v / rt
        flux = perm * area * u * (ci - co * np.exp(-u)) / (1.0 - np.exp(-u))  # mol/s
        return float(F * np.sum(z * flux))

    v = phi[patch.inside] - phi[patch.outside]
    h = 1e-6
    return (outward(v + h) - outward(v - h)) / (2 * h)


def face_conductance(spec, model, p, state):
    """The access face's small-signal conductance, (F^2/RT) sum z^2 D (A/L) c_logmean (S)."""
    face = spec.model.faces[0]
    c = concentrations(spec, model, p, state)
    a, b = c[face.sender], c[face.receiver]
    mean = np.where(np.isclose(a, b, rtol=1e-12), a, (a - b) / (np.log(a) - np.log(b)))
    z = np.ravel(p.valence)
    d = np.asarray(face.diffusivity_m2_per_s)  # Species order.
    return float(F * F / (R * spec.model.temperature_K) * np.sum(z * z * d * mean)) * (
        face.area_m2 / face.length_m
    )


def patch(spec, name):
    return next(m for m in spec.model.membranes if m.id == name)


def network(spec, model, p, state, *, sealed):
    """Conductances (S) of the T-network: G1, G2 (old patches), Gf1, Gf2 (furrows), Ga."""
    g = {
        k: slope_conductance(patch(spec, name), spec, model, p, state)
        for k, name in (
            ("G1", "membrane_0_d1"),
            ("G2", "membrane_0_d2"),
            ("Gf1", "furrow_d1"),
            ("Gf2", "furrow_d2"),
        )
    }
    g["Ga"] = 0.0 if sealed else face_conductance(spec, model, p, state)
    return g


def predicted(g):
    """(V1, V2, Vc) per ampere into d1: Kirchhoff's law at d1, d2 and the cleft."""
    matrix = np.array(
        [
            [g["G1"] + g["Gf1"], 0.0, -g["Gf1"]],
            [0.0, g["G2"] + g["Gf2"], -g["Gf2"]],
            [-g["Gf1"], -g["Gf2"], g["Gf1"] + g["Gf2"] + g["Ga"]],
        ]
    )
    return np.linalg.solve(matrix, np.array([1.0, 0.0, 0.0]))


def response(*, bridge, sealed=False):
    """The injected run's voltage changes from its base run, and the base run's operating
    point."""
    base = final(furrow_world(bridge=bridge, injected=False, sealed=sealed))
    hot = final(furrow_world(bridge=bridge, injected=True, sealed=sealed))
    v0, v1 = potentials(*base[:4]), potentials(*hot[:4])
    delta = {k: v1[k] - v0[k] for k in ("d1", "d2", "cleft")}
    return delta, base, hot


def test_a_closed_bridge_couples_as_the_trans_cleft_t_network():
    closed, base, _ = response(bridge=True)
    alone, _, _ = response(bridge=False)
    spec, model, p, state, _ = base
    assert float(np.max(np.asarray(state.bridge_aperture_m))) == 0.0  # a = 0 at the end.
    v1, v2, vc = predicted(network(spec, model, p, state, sealed=False))
    # The T-network's DC response to the current, coupling and input resistance, to 1%.
    assert closed["d2"] / closed["d1"] == pytest.approx(v2 / v1, rel=0.01)
    assert closed["cleft"] / closed["d1"] == pytest.approx(vc / v1, rel=0.01)
    assert closed["d1"] / CURRENT_A == pytest.approx(v1, rel=0.01)
    # A closed bridge carries nothing: the world without a bridge responds the same, to 1e-9.
    for k in ("d1", "d2", "cleft"):
        assert closed[k] == pytest.approx(alone[k], rel=1e-9)


def test_a_sealed_cleft_joins_the_daughters_through_two_furrows_in_series():
    delta, base, hot = response(bridge=False, sealed=True)
    spec, model, p, state, _ = base
    g = network(spec, model, p, state, sealed=True)
    v1, v2, _ = predicted(g)
    assert delta["d2"] / delta["d1"] == pytest.approx(v2 / v1, rel=0.01)
    # R_j from the run: d1 - d2 over the furrow current into d2 (the engine's readout, whose
    # membrane flux is positive from the cell to its outside node).
    k = [m.id for m in spec.model.membranes].index("furrow_d2")
    currents = []
    for _, m, layout, x, control in (base, hot):
        flux = np.asarray(m.readouts(x, control, layout, xp=np).field.rates.membrane_flux_fmol_s)
        currents.append(-CHARGE_PER_FMOL * float(np.sum(np.ravel(layout.valence) * flux[:, k])))
    rj = (delta["d1"] - delta["d2"]) / (currents[1] - currents[0])
    series = 1.0 / g["Gf1"] + 1.0 / g["Gf2"]
    assert rj == pytest.approx(series, rel=0.01)
    # 2 r_new / A_face: the two furrows are equal halves of the parent's (a = 1/2).
    area = float(np.asarray(p.membrane_area)[k] + np.asarray(state.membrane_area_increment_m2)[k])
    r_new = area / g["Gf2"]  # The furrow membrane's specific resistance (ohm m^2).
    assert series == pytest.approx(2 * r_new / area, rel=1e-6)


def test_a_symmetric_division_keeps_its_daughters_equal():
    raw = fx.divided(end=0.05)
    raw["experiment"]["observation_times"] = [0.0, 0.05]
    raw["execution"].update(dt=DT, max_steps=int(math.ceil(0.05 / DT)) + 8)
    spec = parse_spec(raw)
    model = get_model(spec.model)
    result = run(spec)
    times = np.asarray(result.times)
    after = times > fx.EVENT
    twins = {
        "cell_slot": ([c.id for c in spec.model.cells], ("d1", "d2")),
        "membrane_slot": ([m.id for m in spec.model.membranes], ("membrane_0_d1", "membrane_0_d2")),
    }
    channels = [c.id for c in spec.model.channels]
    pairs = [(f"{c}_d1", f"{c}_d2") for c in channels if f"{c}_d1" in channels]
    compared = 0
    for name, axes in model.STATE_AXES.items():
        values = np.asarray(getattr(result.history, name))[after]
        axis = axes[-1]
        if axis == "channel_slot":
            slots = [(channels.index(a), channels.index(b)) for a, b in pairs]
        elif axis in twins:
            ids, (a, b) = twins[axis]
            slots = [(ids.index(a), ids.index(b))]
        else:
            continue
        scale = float(np.max(np.abs(values))) if values.size else 0.0
        for i, j in slots:
            difference = float(np.max(np.abs(values[..., i] - values[..., j])))
            assert difference <= 64 * EPS * scale, (name, difference, scale)
            compared += 1
    assert compared >= 20
    # The potentials too.
    _, p = model.initial_values(spec)
    cells = [c.id for c in spec.model.cells]
    for row in np.flatnonzero(after):
        state = model.STATE_TYPE(*(np.asarray(v[row]) for v in result.history))
        phi = adapter.node_potentials(state, model.view(p, state, xp=np), xp=np)
        a, b = phi[cells.index("d1")], phi[cells.index("d2")]
        assert abs(a - b) <= 64 * EPS * abs(a)


def test_the_limits_world_keeps_its_reversal_potentials():
    raw = furrow_world(bridge=False, injected=False)
    plain = fx.cleft_divided(end=END)
    for scaled, declared in zip(
        raw["model"]["membranes"], plain["model"]["membranes"], strict=True
    ):
        ratios = {
            s: scaled["permeability_m_per_s"][s] / v
            for s, v in declared["permeability_m_per_s"].items()
            if v > 0
        }
        assert set(ratios.values()) == {SCALE}  # Every permeant species alike.
    assert copy.deepcopy(raw)["model"]["faces"][0]["area_m2"] == ACCESS_AREA_M2
