"""cells.operator.local_species_reactions@1 composed with transport and with other writers (D152 v1, milestone 3;
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
* **The composed world's accounting and execution** (the coordinator's milestone-3 additions,
  from an external architecture review the advisor confirmed). These are reference-independent,
  so they stay judged guards (the lead's ruling 10). The same-material test, whose exchange map
  is the engine agent's own, lives in test_species_reactions_same_material.py, a regression
  guard outside the judged list:
  - supply is counted once across writers. Each network species' inventory over the cells and
    finite nodes changes at every row by exactly its writers' booked sources, each once: the
    reactions, the turnover, the replacement and the held bath's supply through the faces. At
    ecs_0, S changes by the exchange's delivery, the reactions' consumption and the face's
    outflow;
  - restart (in process, around the event, and through a snapshot read in a fresh process) and a
    vector batch preserve the composed world's results;
  - a rejected step restores the complete state, every field bitwise, the other writers'
    accumulators included.

A few minutes of compiles: tier 3.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.definitions import pump_composite_spec as cs
from cells.definitions.specs import parse_spec
from cells.execution.runner import run
from cells.registry.inventory_species import add_inventory_species
from cells.registry.models import get_model
from validation.morphogenesis import mg0c_turing as mg
from validation.reactions import chain_reference as cr
from validation.tissue import secreted_species_fixtures as fx
from validation.tissue import species_reactions_fixtures as rfx

jax.config.update("jax_enable_x64", True)
IONS = ("Na", "K", "Cl")
ROOT = Path(__file__).resolve().parents[2]


def bits(value):
    return np.asarray(value).tobytes()


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


def composition(
    end=0.01, dt=1e-3, *, export=0.2, template_rate=0.1, clear=0.05, kcat=1.0, kf=0.5, k_out=0.5
):
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
        [("sec_0", "cell_0", [(0.0, export)]), ("sec_1", "cell_1", [(0.0, export)])],
        templates=[("T", {"sec_0": {"rate": template_rate}})],
    )
    raw = fx.with_turnover(
        raw,
        [("e_clear", "ecs_0", "clearance")],
        [("e_clear", None, [(0.0, clear)])],
        species=[dict(id="E", catalogue=None, evidence=None)],
    )
    raw["model"]["operators"][-1]["routes"][0]["species"] = "E"  # A row the network only reads.
    node0, node1, nodes = {"outside": ["ecs_0"]}, {"outside": ["ecs_1"]}, {"outside": "all"}
    reactions = [
        rfx.michaelis_menten("conversion", node0, "S", {"P": 1}, kcat, 5e-4, catalyst="E"),
        rfx.passive("swap", node1, {"S": 1}, {"P": 1}, kf),
        rfx.mass_action(
            "removal",
            nodes,
            {"P": 1},
            {},
            k_out,
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


# ------------------------------------------------------------------ the composed world's accounting


def network_inventory(result, names):
    """{species: [T] its amount over the active cells and the finite outside nodes (fmol)} and
    {species: [T] the writers' booked sources, each once}; the replaced slot keeps its anchor."""
    spec = result.spec
    model = get_model(spec.model)
    _, p = model.initial_values(spec)
    h = result.history
    ids = list(spec.model.species_ids)
    finite = ~np.asarray(p.reservoir)
    held = np.asarray(p.reservoir)
    cells = np.asarray(p.active)
    inventory, sources = {}, {}
    for name in names:
        s = ids.index(name)
        cell = np.asarray(p.amount_reference)[s] + np.asarray(h.amount_increment)[:, s]
        node = (
            np.asarray(p.extracellular_amount_reference)[s]
            + np.asarray(h.extracellular_amount_increment)[:, s]
        )
        inventory[name] = cell[:, cells].sum(axis=1) + node[:, finite].sum(axis=1)

        def booked(field, columns, s=s):
            return np.asarray(getattr(h, field))[:, s][:, columns].sum(axis=1)

        sources[name] = dict(
            reactions=booked("reaction_produced_fmol", cells)
            - booked("reaction_consumed_fmol", cells)
            + booked("reaction_outside_produced_fmol", finite)
            - booked("reaction_outside_consumed_fmol", finite),
            turnover=booked("turnover_produced_fmol", cells)
            - booked("turnover_cleared_fmol", cells)
            - booked("turnover_outside_cleared_fmol", finite),
            replacement=booked("replacement_supplied_fmol", cells)
            - booked("replacement_removed_fmol", cells),
            held_bath=booked("reservoir_supplied", held),
        )
    return inventory, sources


def test_supply_is_counted_once_across_writers_and_the_node_sees_what_transport_brings():
    spec = parse_spec(composition())
    result = run(spec)
    names = ("S", "E", "P")
    inventory, sources = network_inventory(result, names)
    report = {}
    for name in names:
        total = sum(sources[name].values())
        residual = inventory[name] - inventory[name][0] - total
        scale = float(np.max(np.abs(inventory[name])))
        report[name] = dict(
            max_residual_of_scale=float(np.max(np.abs(residual))) / scale,
            sources_at_end={k: float(v[-1]) for k, v in sources[name].items()},
        )
        assert np.all(np.abs(residual) <= 64 * np.finfo(float).eps * scale), name
    # Each writer's term enters (so the closure is informative): S from the reactions, the
    # replacement and the bath; E from the turnover; P from the reactions and the bath.
    assert sources["S"]["reactions"][-1] < 0 < sources["S"]["replacement"][-1]
    assert sources["E"]["turnover"][-1] < 0 and sources["P"]["reactions"][-1] != 0
    assert sources["S"]["held_bath"][-1] != 0 and sources["P"]["held_bath"][-1] != 0
    # At ecs_0, S changes by the export's delivery, the reactions' consumption and the face's
    # outflow (face_0 from ecs_0 to the bath), at every row.
    model = get_model(spec.model)
    _, p = model.initial_values(spec)
    h = result.history
    ids = list(spec.model.species_ids)
    s = ids.index("S")
    o = [c.id for c in spec.model.extracellular].index("ecs_0")
    f = [face.id for face in spec.model.faces].index("face_0")
    node = np.asarray(h.extracellular_amount_increment)[:, s, o]
    delivered = np.asarray(h.exchange_moved_fmol)[:, 0]  # sec_0: cell_0 to ecs_0.
    consumed = np.asarray(h.reaction_outside_consumed_fmol)[:, s, o]
    produced = np.asarray(h.reaction_outside_produced_fmol)[:, s, o]
    outflow = np.asarray(h.face_transferred)[:, s, f]
    residual = node - (delivered - consumed + produced - outflow)
    scale = float(np.asarray(p.extracellular_amount_reference)[s, o])
    report["ecs_0_S"] = dict(
        max_residual_of_scale=float(np.max(np.abs(residual))) / scale,
        delivered=float(delivered[-1]),
        consumed=float(consumed[-1]),
        outflow=float(outflow[-1]),
    )
    record("supply_counted_once", **report)
    assert delivered[-1] > 0 and consumed[-1] > 0 and outflow[-1] != 0
    assert np.all(np.abs(residual) <= 64 * np.finfo(float).eps * scale)


FRESH = """
import json, sys
import jax
jax.config.update("jax_enable_x64", True)
import numpy as np
from cells.execution.runner import run
from cells.records.io import load_snapshot
loaded = load_snapshot(sys.argv[1])
result = run(loaded.spec, loaded.checkpoint)
np.savez(sys.argv[2], **{k: np.asarray(v) for k, v in result.history._asdict().items()})
print(json.dumps(dict(start=int(loaded.checkpoint.step_index))))
"""


def test_restart_and_a_vector_batch_preserve_the_composed_worlds_results(tmp_path):
    from cells.execution.batch import BatchSpec, WorldSpec
    from cells.execution.vector_windows import run_vector_windowed
    from cells.execution.windows import WindowPolicy
    from cells.records.io import write_snapshot

    spec = parse_spec(composition())
    result = run(spec)
    for t in (0.003, EVENT, 0.008):  # Before, at and after the replacement event.
        checkpoint = result.checkpoint_at(t)
        resumed = run(spec, checkpoint)
        for a, b in zip(resumed.history, result.history, strict=True):
            assert bits(a) == bits(np.asarray(b)[checkpoint.step_index :]), t
    checkpoint = result.checkpoint_at(0.008)
    write_snapshot(tmp_path / "checkpoint", result.spec, checkpoint)
    env = dict(
        os.environ,
        PYTHONPATH=os.pathsep.join([str(ROOT / "src"), str(ROOT)]),
        JAX_ENABLE_X64="1",
        JAX_PLATFORMS="cpu",
    )
    done = subprocess.run(
        [sys.executable, "-B", "-c", FRESH, str(tmp_path / "checkpoint"), str(tmp_path / "h.npz")],
        env=env,
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    assert done.returncode == 0, done.stderr[-2000:]
    start = json.loads(done.stdout.strip().splitlines()[-1])["start"]
    assert start == checkpoint.step_index
    fresh = np.load(tmp_path / "h.npz")
    for name, value in result.history._asdict().items():
        assert bits(fresh[name]) == bits(np.asarray(value)[start:]), name
    variants = [
        dict(),
        dict(export=0.3, template_rate=0.05, clear=0.08, kcat=1.5, kf=0.8, k_out=0.4),
        dict(export=0.1, template_rate=0.2, clear=0.02, kcat=0.7, kf=0.3, k_out=0.6),
    ]
    specs = [parse_spec(composition(**v)) for v in variants]
    model = get_model(specs[0].model)
    assert all(
        model.batch_signature(s.model) == model.batch_signature(specs[0].model) for s in specs
    )

    def batch(order):
        worlds = tuple(WorldSpec(i + 1, specs[j]) for i, j in enumerate(order))
        return run_vector_windowed(
            BatchSpec(worlds, len(worlds), 10**6, 2**31), WindowPolicy(4, "checkpoints")
        )

    forward, backward = batch([0, 1, 2]), batch([2, 1, 0])
    worst = 0.0
    for k, s in enumerate(specs):
        final = forward.worlds[k + 1].final.state
        for a, b in zip(final, backward.worlds[3 - k].final.state, strict=True):
            assert bits(a) == bits(b), k
        single = run(s).history
        for name in type(final)._fields:
            a, b = np.asarray(getattr(final, name)), np.asarray(getattr(single, name))[-1]
            if a.dtype.kind != "f":
                assert bits(a) == bits(b), (k, name)
                continue
            scale = float(np.max(np.abs(b), initial=0.0))
            difference = float(np.max(np.abs(a - b), initial=0.0))
            assert difference <= 1e-12 * scale + 1e-30, (k, name)
            if scale > 0:
                worst = max(worst, difference / scale)
    record("restart_and_batch", restart="bitwise", batch_reversed="bitwise", batch_vs_scalar=worst)


def test_a_rejected_step_restores_the_complete_state_of_the_composed_world():
    """After the event, the step at the declared dt is admitted and moves every writer; with the
    conversion's multiplier raised 1e7-fold (dt L far above 1) the step is refused and returns the
    start state bit for bit: @3's fields, the exchange's, the turnover's, the replacement's and the
    network's."""
    spec = parse_spec(composition())
    result = run(spec)
    checkpoint = result.checkpoint_at(0.008)
    model = get_model(spec.model)
    layout = checkpoint.layout
    state = type(checkpoint.state)(*(jnp.asarray(v) for v in checkpoint.state))
    controls = cs.control_values(spec, [0.008])
    control = type(controls)(*(jnp.asarray(v[0]) for v in controls))
    step = jax.jit(lambda x, c, dt: model.checked_step(x, dt, c, layout, layout.active))
    dt = jnp.asarray(spec.execution.dt)
    moved, ok = step(state, control, dt)
    assert bool(ok)
    changed = {
        name
        for name, a, b in zip(type(state)._fields, moved, state, strict=True)
        if bits(a) != bits(b)
    }
    assert {
        "exchange_moved_fmol",
        "turnover_outside_cleared_fmol",
        "reaction_extent_fmol",
        "extracellular_amount_increment",
    } <= changed
    big = control._replace(reaction_multiplier=control.reaction_multiplier * 1e7)
    refused, ok = step(state, big, dt)
    assert not bool(ok)
    for name, a, b in zip(type(state)._fields, refused, state, strict=True):
        assert bits(a) == bits(b), name
    record("rejected_step", admitted_changed=sorted(changed), refused="every field bitwise")
