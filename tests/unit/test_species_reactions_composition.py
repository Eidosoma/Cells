"""local_species_reactions@1 composed with transport and with other writers (D152 v1, milestone 3;
design §3.4 guard 2, §4.5 claim 3, §5).

* **§3.4 guard 2, the reaction-transport check.** Linear networks on MG0c's closed chain
  (validation/morphogenesis/mg0c_turing: passive A <-> B with D_A != D_B; open 0 -> A -> 0,
  A -> B -> 0) have an exactly known engine-order map, P(dt/2) I(dt) P(dt/2) mode by mode
  (chain_reference.strang_mode_map, used through REFERENCES_USAGE.md only). The compiled run must
  equal that map iterated, to rounding, and pass every host check on every window at the species'
  floors. Its residual over the shared energy bound is recorded; it is the faces' booking, second
  order in dt (probe 1).
* **Idle claim 3** (§4.5, as D150's test_secreted_species_ions), reported, not promised. XLA's
  reduction order over the species axis is program-specific. With Schnakenberg active on the
  chain, every ion row of every species-axis field, and every field U and V do not enter, is
  bitwise the chain's without U and V; so is the chain with U and V declared and no network. U
  and V enter their own rows, the operator's fields and the faces' heat.
* **A development composition with other writers** (§5), making no acceptance claim. Every host
  check passes on every row at the species' floors, and each writer moves something:
  - D150's exchange of S across both cells' patches, on rows the network writes;
  - D150's turnover clearing the catalyst E at ecs_0, a row the network only reads;
  - replacement@1 replacing cell_0 mid-run, with the network on outside routes only (cell routes
    on a replaced slot are refused, §2.1).

A few minutes of compiles: tier 3.
"""

import json
import os
from pathlib import Path

import jax
import numpy as np
import pytest

from cells.core.inventory_species import add_inventory_species
from cells.core.runner import run
from cells.core.specs import parse_spec
from validation.morphogenesis import mg0c_turing as mg
from validation.reactions import chain_reference as cr
from validation.tissue import secreted_species_fixtures as fx
from validation.tissue import species_reactions_fixtures as rfx

jax.config.update("jax_enable_x64", True)
IONS = ("Na", "K", "Cl")


def record(test, **values):
    """Append measured values to this run's output folder (the tier runner's CELLS_OUTPUT_ROOT)."""
    root = os.environ.get("CELLS_OUTPUT_ROOT")
    if root:
        path = Path(root) / "species_reactions_composition.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a") as out:
            out.write(json.dumps(dict(test=test, **values), default=float) + "\n")


# ------------------------------------------------------------------ §3.4 guard 2


@pytest.mark.parametrize("label", ["passive", "open"])
def test_guard_2_linear_networks_on_the_chain_run_the_engine_orders_map(label):
    world = mg.passive_pair() if label == "passive" else mg.open_pair()
    n_nodes, dt, end = 12, 0.05, 10.0
    shape = np.asarray(cr.mode_basis(n_nodes))
    base = world["base_mM"]
    profile = {s: c * (1.0 + 0.05 * shape[2] + 0.02 * shape[5]) for s, c in base.items()}
    times, stop = mg.grid_times(dt, [end / 2], end)
    raw = mg.chain_world(
        profile,
        network=world["network"],
        diffusivities=world["diffusivities"],
        dt=dt,
        end=stop,
        observation_times=times,
    )
    run_ = mg.run_chain(raw, base)  # Every host check on every window; a failure raises.
    names = list(profile)
    D = np.asarray([world["diffusivities"][s] for s in names])
    K, source = (np.asarray(v) for v in cr.linear_rates(rfx.reference_network(raw)))
    a = mg.coefficients(run_)
    a[:, :, 0] += np.asarray([base[s] * mg.VOLUME_PL for s in names]) / run_["volume"][0]
    scale = float(np.max(np.abs(a[0])))
    worst = exact = 0.0
    for t, value in zip(run_["times"][1:], a[1:], strict=True):
        steps = int(round(t / dt))
        mapped = mg._iterate_maps(K, D, n_nodes, dt, steps, a[0], source)
        truth = np.asarray(cr.propagate_modes(K, D, n_nodes, mg.SPACING_M, a[0], t, source=source))
        worst = max(worst, float(np.max(np.abs(value - mapped))) / scale)
        exact = max(exact, float(np.max(np.abs(value - truth))) / scale)
    checks = run_["checks"]
    record(
        "guard_2",
        world=label,
        steps=run_["steps"],
        against_engine_order_map=worst,
        against_exact=exact,
        **checks,
    )
    assert worst <= 1e-12  # 200 steps: rounding (the usage note: k eps accumulated at most).
    assert exact <= 1e-5  # The scheme's second-order error at 50 ms, far above the map's.
    assert 0.0 < checks["energy_over_bound"] < 1.0  # The faces' booking, inside the bound.
    assert checks["material_over_bound"] <= 1.0


# ------------------------------------------------------------------ idle claim 3 (§4.5)


def differing(ions, other, species):
    """The ion world's fields whose values differ in the other world (ion rows compared)."""
    rows = [species.index(k) for k in IONS]
    out = []
    for name in type(ions)._fields:
        a, b = np.asarray(getattr(ions, name)), np.asarray(getattr(other, name))
        if b.ndim >= 2 and b.shape[1] == len(species) and a.shape[1] == len(IONS):
            b = b[:, rows]
        if a.shape != b.shape or a.tobytes() != b.tobytes():
            out.append(name)
    return out


def test_idle_claim_3_ion_rows_are_bitwise_with_the_network_active():
    n_nodes, dt, end = 12, 0.05, 5.0
    times = [0.0, 2.5, end]
    profile = mg.noise_profile(n_nodes, 3)
    ions = parse_spec(mg.chain_world({}, n_nodes=n_nodes, dt=dt, end=end, observation_times=times))
    active = parse_spec(mg.chain_world(profile, dt=dt, end=end, observation_times=times))
    declared = parse_spec(
        rfx.without_reactions(mg.chain_world(profile, dt=dt, end=end, observation_times=times))
    )
    a, b, c = run(ions), run(active), run(declared)  # Host checks on every row of each.
    species = list(active.model.species_ids)
    with_network = differing(a.history, b.history, species)
    without_network = differing(a.history, c.history, species)
    record("idle_claim_3", with_network=with_network, species_without_network=without_network)
    expected = {"face_dissipated_energy_pJ"}  # U and V diffuse on the chain's faces.
    assert set(with_network) <= expected, with_network
    assert set(without_network) <= expected, without_network
    extents = np.asarray(b.history.reaction_extent_fmol)[-1]
    assert np.all(extents != 0)  # The network did act.


# ------------------------------------------------------------------ other writers (§5)

EVENT = 0.006


def composition(end=0.01, dt=1e-3):
    """Two cells and their nodes leaking to the bath (D150's swapped world, at its 1 ms step, which
    the junction gate's kinetic bound needs): S exported from both cells; E (the catalyst) and P
    at the nodes; replacement of cell_0 at EVENT; the network on outside routes only:
    Michaelis-Menten S -> P catalysed by E at ecs_0, passive S <-> P at ecs_1, P -> 0 inhibited
    by S at both nodes (at ecs_1 at half the rate)."""
    base = fx.world(
        cells=(("cell_0", 1.0), ("cell_1", 1.0)),
        nodes=(("ecs_0", 1.0), ("ecs_1", 1.0)),
        contacts=(("contact_0", "cell_0", "ecs_0"), ("contact_1", "cell_1", "ecs_1")),
        faces=(("face_0", "ecs_0", "bath", 1e-10, 1e-5), ("face_1", "ecs_1", "bath", 1e-10, 1e-5)),
        junctions=(("junction_0", "cell_0", "cell_1"),),
        dt=dt,
        end=end,
        observation_times=[0.0, 0.003, EVENT, 0.008, end],
        concentrations_mM=dict(cell_0=1e-3, cell_1=1e-3, ecs_0=5e-4, ecs_1=5e-4),
    )
    for name, profile in (("E", dict(ecs_0=1e-4)), ("P", dict(ecs_0=1e-5, ecs_1=1e-5))):
        base = add_inventory_species(
            base,
            name,
            trace_mM=rfx.TRACE_mM,
            diffusivity_m2_per_s=rfx.D_SPECIES,
            floor_fmol=rfx.FLOOR_FMOL,
            concentrations_mM=profile,
        )
    template = fx.template(base, "cell_0", "T", s_mM=1.2e-3)
    raw = fx.with_replacement(base, [template], [(EVENT, "cell_0", "T", "c0_new")])
    raw = fx.with_exchange(
        raw,
        [
            ("sec_0", "contact_0", "export", "first_order"),
            ("sec_1", "contact_1", "export", "first_order"),
        ],
        [("sec_0", "cell_0", [(0.0, 0.2)]), ("sec_1", "cell_1", [(0.0, 0.2)])],
        templates=[("T", {"sec_0": {"rate": 0.1}})],
    )
    raw = fx.with_turnover(
        raw,
        [("e_clear", "ecs_0", "clearance")],
        [("e_clear", None, [(0.0, 0.05)])],
        species=[dict(id="E", catalogue=None, evidence=None)],
    )
    raw["model"]["operators"][-1]["routes"][0]["species"] = "E"  # A row the network only reads.
    node0, node1, nodes = {"outside": ["ecs_0"]}, {"outside": ["ecs_1"]}, {"outside": "all"}
    reactions = [
        rfx.michaelis_menten("conversion", node0, "S", {"P": 1}, 1.0, 5e-4, catalyst="E"),
        rfx.passive("swap", node1, {"S": 1}, {"P": 1}, 0.5),
        rfx.mass_action(
            "removal",
            nodes,
            {"P": 1},
            {},
            0.5,
            factors=[rfx.hill("hill_inhibition", "S", 1e-3, 2.0)],
        ),
    ]
    species = [
        rfx.species("S", moieties={"X": 1}),
        rfx.species("E", moieties={"Y": 1}),
        rfx.species("P", moieties={"X": 1}, mu=-1.0),
    ]
    controls = [*rfx.always(["conversion", "swap", "removal"]), ("removal", "ecs_1", [(0.0, 0.5)])]
    return rfx.with_reactions(raw, species, reactions, controls)


def test_a_development_composition_with_exchange_turnover_and_replacement():
    spec = parse_spec(composition())
    result = run(spec)  # Every host check on every accepted row, at the species' floors.
    h = result.history
    species = list(spec.model.species_ids)
    s, e = species.index("S"), species.index("E")
    moved = np.asarray(h.exchange_moved_fmol)[-1]
    cleared = np.asarray(h.turnover_outside_cleared_fmol)[-1][e]
    extents = np.asarray(h.reaction_extent_fmol)[-1]
    generation = np.asarray(h.generation)[-1]
    supplied = np.asarray(h.replacement_supplied_fmol)[-1][s, 0]
    record(
        "composition",
        exchange_moved_fmol=moved.tolist(),
        turnover_cleared_E_fmol=cleared.tolist(),
        extents_fmol=extents.tolist(),
        generation=generation.tolist(),
        supplied_S_fmol=float(supplied),
        diagnostics={k: float(v) for k, v in result.diagnostics.items() if np.isscalar(v)},
    )
    assert np.all(moved > 0)  # Both cells exported S.
    assert cleared[[c.id for c in spec.model.extracellular].index("ecs_0")] > 0  # E cleared.
    assert np.all(extents != 0)  # Every route acted.
    assert generation.tolist() == [1, 0]  # The event fired on cell_0 only.
    assert supplied == pytest.approx(1.2e-3)  # The newcomer's S pool.
