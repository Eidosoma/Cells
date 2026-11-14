"""Transport and reactions see the same material under the declared splitting (D152 v1; the
coordinator's milestone-3 addition, from an external architecture review the advisor confirmed).

A regression guard outside MG0c's judged list (the lead's protocol review, ruling 10). The
exchange's half-step map below is the engine agent's own, written from D150's documented law, so
one author holds both sides, as with D150's step map, which the lead also moved out of its judged
list. The reference-independent checks of the composed world (supply counted once, the rejected
step, restart and batch) stay judged guards in test_species_reactions_composition.py.

A face-free composition of D150's first-order export and the reactions: one 1 pL cell and its 1 pL
node, with no face. The run equals the composed map E(dt/2) R(dt/2) I(dt) R(dt/2) E(dt/2) at
rounding:
- E is the export's exact half-step, from D150's documented law: J = k_e n_c, moving
  n_c (1 - e^{-k_e h});
- R is SSPRK(3,3)'s map, from validation/reactions/chain_reference.half_step_linear_map, used
  through REFERENCES_USAGE.md only;
- I, @3's step, is the identity for these rows here.
The other order is far off, and the composition converges at second order to the coupled system's
exact solution. Under a minute of compiles.
"""

import json
import os
from pathlib import Path

import jax
import numpy as np
from scipy.linalg import expm

from cells.core.runner import run
from cells.core.specs import parse_spec
from cells.models.registry import get_model
from validation.reactions import chain_reference as cr
from validation.tissue import secreted_species_fixtures as fx
from validation.tissue import species_reactions_fixtures as rfx

jax.config.update("jax_enable_x64", True)
KE, KR, KD = 0.5, 1.0, 0.3  # The export, the conversion and the decay (1/s).


def record(test, **values):
    """Append measured values to this run's output folder (the tier runner's CELLS_OUTPUT_ROOT)."""
    root = os.environ.get("CELLS_OUTPUT_ROOT")
    if root:
        path = Path(root) / "species_reactions_same_material.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a") as out:
            out.write(json.dumps(dict(test=test, **values), default=float) + "\n")


def linear_composition(dt, end=2.0):
    """Face-free (one 1 pL cell and its 1 pL node, no face): S exported from the cell at first
    order (D150's law: J = k_e n_c, its exact half-step moving n_c (1 - e^{-k_e h})); at ecs_0, S
    -> P at k_r and P -> 0 at k_d. The exchange is declared before the network, so the composite's
    split order is E R I R E."""
    raw = rfx.species_world(
        ("P",),
        profile=dict(S=dict(cell_0=1e-3, ecs_0=1e-4), P=dict(ecs_0=1e-5)),
        faces=False,
        dt=dt,
        end=end,
        observation_times=fx.grid_times(end, dt, end / 4),
    )
    raw = fx.with_exchange(
        raw, [("sec", "contact_0", "export", "first_order")], [("sec", "cell_0", [(0.0, KE)])]
    )
    node = {"outside": ["ecs_0"]}
    reactions = [
        rfx.mass_action("convert", node, {"S": 1}, {"P": 1}, KR),
        rfx.mass_action("decay", node, {"P": 1}, {}, KD),
    ]
    species = [rfx.species("S", moieties={"X": 1}), rfx.species("P", moieties={"X": 1})]
    return rfx.with_reactions(raw, species, reactions, rfx.always(["convert", "decay"]))


def linear_amounts(result):
    """[T, 3]: S in the cell, S and P at ecs_0 (fmol), anchors plus increments."""
    spec = result.spec
    model = get_model(spec.model)
    _, p = model.initial_values(spec)
    ids = list(spec.model.species_ids)
    s, q = ids.index("S"), ids.index("P")
    o = [c.id for c in spec.model.extracellular].index("ecs_0")
    h = result.history
    cell = np.asarray(p.amount_reference)[s, 0] + np.asarray(h.amount_increment)[:, s, 0]
    node_s = (
        np.asarray(p.extracellular_amount_reference)[s, o]
        + np.asarray(h.extracellular_amount_increment)[:, s, o]
    )
    node_p = (
        np.asarray(p.extracellular_amount_reference)[q, o]
        + np.asarray(h.extracellular_amount_increment)[:, q, o]
    )
    return np.stack([cell, node_s, node_p], axis=1)


def test_exchange_and_reactions_see_the_same_material_under_the_declared_splitting():
    K = np.array([[-KR, 0.0], [KR, -KD]])
    G = np.array([[-KE, 0.0, 0.0], [KE, -KR, 0.0], [0.0, KR, -KD]])  # The coupled system.
    errors, worst = [], 0.0
    for dt in (0.05, 0.025):
        result = run(parse_spec(linear_composition(dt)))  # Every host check on every row.
        x = linear_amounts(result)
        h = 0.5 * dt
        e = np.exp(-KE * h)
        E = np.array([[e, 0.0, 0.0], [1.0 - e, 1.0, 0.0], [0.0, 0.0, 1.0]])
        M, q = cr.half_step_linear_map(K, h)
        assert q is None or np.all(np.asarray(q) == 0)
        R = np.eye(3)
        R[1:, 1:] = np.asarray(M)
        step = E @ R @ R @ E  # Applied right to left: E, R, I (identity here), R, E.
        other = R @ E @ E @ R  # The other order, for contrast.
        times = np.asarray(result.times)
        steps = np.rint(times / dt).astype(int)
        scale = float(np.max(np.abs(x)))
        mapped = np.asarray([np.linalg.matrix_power(step, k) @ x[0] for k in steps])
        swapped = np.asarray([np.linalg.matrix_power(other, k) @ x[0] for k in steps])
        exact = np.asarray([expm(G * t) @ x[0] for t in times])
        difference = float(np.max(np.abs(x - mapped))) / scale
        worst = max(worst, difference)
        assert difference <= 1e-13  # Rounding over 40 and 80 steps.
        assert float(np.max(np.abs(x - swapped))) / scale > 1e3 * difference  # The order shows.
        errors.append(float(np.max(np.abs(x - exact))) / scale)
    record("same_material", against_composed_map=worst, against_exact=errors)
    assert 3.6 <= errors[0] / errors[1] <= 4.4  # Second order to the coupled system's solution.
