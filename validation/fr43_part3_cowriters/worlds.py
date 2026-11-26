"""FR-43 part 3's co-writers registration: the engine's worlds (the builder's; the protocol's §5).

docs/FR43_PART3_COWRITERS_PROTOCOL.md, with the spec folder spec/ (tag
fr43-part3-cowriters-criteria-2026-11-25). An inputs file of the spec's layout (spec/inputs.json,
or the references' invented inputs_invented.json for the rehearsal and the format sample) gives
each run's world, declared order, copy and step; `definition` builds that run's composite
definition, and `check_world` confirms the structure SPEC.md §1 asks of it.

**A copy** (LAWS.md §0, SPEC.md §1) is one cell (cell_0, V_c), one finite outside node (ecs_0,
V_o) and one patch between them (contact_0) holding one site of the population. Beside them, the
engine's inert background: Na+, K+ and Cl- at the bath's composition in every node with a zero
charge anchor, and the cell's wall patch on a held bath (validation/tissue/
secreted_species_fixtures' quiescent world). There is no face, no junction, no channel and no pump,
and every patch's permeability is zero for every species, so nothing but the two declared writers
moves a row of the world (check_world asserts it).

**The rows.** Each is a neutral, impermeant inventory species (cells.registry.inventory_species)
at its declared amount (fmol, written exactly, not through a concentration) in the cell or the
node; every other place of it holds a trace background of TRACE_mM, which nothing moves.

**The writers,** in the declared order the run names (`first`):
- the population (cells.operator.integer_unit_population@1): one site, `site_c<copy>` on
  contact_0 (the copy is read back from its ID), the world's unit states, channels (a read at the
  "cell" or the "node", the operator's "outside"), transfer and initial counts, the copy's seed,
  and a trace of TRACE_EVENTS events;
- W5 and W5-exact: D152's reactions (cells.operator.local_species_reactions@1), each driven mass
  action at cell_0 at multiplier 1, k in mM^(1-q)/s (the declared rate_unit is checked against the
  order q); X, S and W carry the moiety `s`, Y and W the moiety `y` (READOUTS.md §4's two sums);
- W6: the gene unit (cells.operator.templated_polymerisation@1), one pool of machines_copies
  machines, one transcription chain `tx` of template_copies copies into R, and one degradation
  `deg` of R into its monomer (per residue: the declared count over `residues`), no transfer
  (recharging), translation, regulator, hold or release; its rows' potentials are mu_RT at c0_mM,
  declared to the registry with the nucleoside and phosphorus moieties of LAWS.md §3. Its
  schedules hold k_I (`initiation_per_mM_s`) and k_R (`degradation.rate_per_s`) from t = 0.

**The runs' variants.** A restart's and a Lie plant's definition is its honest run's (the driver
resumes the one and patches the other). The invented set's `refused` and `stopped` runs apply
their `change` (a dotted path into the world's block, or the run's step) before the build.
"""

import copy
import json
import math
from pathlib import Path

from cells.definitions import pump_composite_spec as cs
from cells.registry.inventory_species import add_inventory_species
from validation.tissue import secreted_species_fixtures as ssf

HERE = Path(__file__).resolve().parent
INPUTS = HERE / "spec" / "inputs.json"

POPULATION = "cells.operator.integer_unit_population@1"
REACTIONS = "cells.operator.local_species_reactions@1"
GENE = "cells.operator.templated_polymerisation@1"
WRITERS = {"reactions": REACTIONS, "gene": GENE, "population": POPULATION}

CELL, NODE, BATH = "cell_0", "ecs_0", "bath"
PATCH, WALL = "contact_0", "wall_cell_0"
SITE = "site_c{copy}"
POPULATION_ID = "units"
TRANSFER_ID = "flow"
CHAIN, POOL, DEGRADATION = "tx", "machines", "deg"
TRACE_mM = 1e-9  # The background of a row where its world declares none (mM).
TRACE_EVENTS = 512  # The trace's capacity per site: above every K_all the spec allows (< 160).
FLOOR_FMOL = {"reactions": ssf.FLOOR_FMOL, "gene": 1e-16}  # The rows' ledger floors.
REACTION_C0_mM = 1.0
AT = {"cell": "cell", "node": "outside"}  # The spec's read places, as the operator names them.
UNIT = {1: "1/s", 2: "1/(mM s)"}  # Mass action's k at order q, mM^(1-q)/s.
MOIETIES = {"reactions": {"s": {"X": 1, "S": 1, "W": 1}, "y": {"Y": 1, "W": 1}}}


def read_inputs(path=INPUTS):
    return json.loads(Path(path).read_text())


def runs(inputs, *, retry=False):
    """{name: run} of the inputs' registered runs, or of the retry's runs (`retry`)."""
    listed = retry_runs(inputs) if retry else inputs["runs"]
    return {r["name"]: r for r in listed}


def retry_runs(inputs, families=None):
    """The retry's runs (CRITERIA.md §7): the inputs' list where it has one (the invented set's),
    else by the rule, `{world} {first}-first h={step!r} c{copy} retry` at retry_rung_s, one per
    copy, role judged, for every family with a retry rung; only `families`' where given."""
    listed = inputs["retry"].get("runs")
    if listed is None:
        arms = {world: int(arm) for arm, world in inputs["arms"].items()}
        listed = []
        for family in inputs["families"]:
            world = inputs["worlds"][family["world"]]
            step = world["retry_rung_s"]
            if step is None:
                continue
            for c in range(int(world["copies"])):
                name = f"{family['world']} {family['first']}-first h={step!r} c{c} retry"
                listed.append(dict(arm=arms[family["world"]], copy=c, first=family["first"],
                                   name=name, role="judged", step_s=step, variant=None,
                                   world=family["world"]))  # fmt: skip
    if families is None:
        return list(listed)
    return [r for r in listed if f"{r['world']} {r['first']}-first" in families]


def find_run(inputs, name):
    for retry in (False, True):
        found = runs(inputs, retry=retry).get(name)
        if found is not None:
            return found
    raise KeyError(f"no run named {name!r} in the inputs (registered or retry)")


def world_of(inputs, run):
    """The run's world block, with its `change` applied (the invented refused and stopped runs)."""
    world = copy.deepcopy(inputs["worlds"][run["world"]])
    for path, value in (run.get("change") or {}).items():
        if path == "step_s":
            continue  # The run's own step: already the run's.
        *head, last = path.split(".")
        target = world
        for key in head:
            target = target[key]
        if last not in target:
            raise KeyError(f"the change {path!r} names no key of the world")
        target[last] = value
    return world


def seed_of(inputs, run):
    return int(inputs["worlds"][run["world"]]["seeds"][run["copy"]])


# ------------------------------------------------------------------ the copy's skeleton


def skeleton(rows, *, cell_pL, node_pL, dt, end, samples, floor):
    """The quiescent cell, node and held bath (module docstring), with the world's rows declared:
    rows {species: {node: fmol}} (cell_0 and ecs_0), every other place at TRACE_mM."""
    outside = [ssf._node(BATH, 1.0, reservoir=True), ssf._node(NODE, node_pL)]
    cells = [ssf._node(CELL, cell_pL, outside=False)]
    membranes = [
        ssf._patch(WALL, CELL, BATH, ssf.WALL_AREA_M2, ssf.WALL_C_F),
        ssf._patch(PATCH, CELL, NODE, ssf.CONTACT_AREA_M2, ssf.CONTACT_C_F),
    ]
    always = [dict(time=0.0, availability=1.0)]
    raw = dict(
        schema_version=1,
        model=dict(
            id="cells.model.resolved_pump_tissue@3",
            temperature_K=310.0,
            species=[dict(id=s, valence=z) for s, z in ssf.ION_SPECIES],
            cells=cells,
            extracellular=outside,
            membranes=membranes,
            junctions=[],
            faces=[],
            closure=dict(
                law="cells.field_closure.resolved_capacitor_components_current_continuity@1",
                gauge_reference=None,
            ),
            channels=[],
        ),
        experiment=dict(
            end_time=float(end),
            observation_times=[float(t) for t in samples],
            membrane_controls=[
                dict(membrane_id=p["id"], schedule=copy.deepcopy(always)) for p in membranes
            ],
            junction_controls=[],
            pump_controls=[],
            calcium_pump_controls=[],
            channel_controls=[],
        ),
        execution=dict(
            dt=float(dt),
            capacity=1,
            extracellular_capacity=len(outside),
            membrane_capacity=len(membranes),
            edge_capacity=0,
            face_capacity=1,
            channel_capacity=0,
            backend="cpu",
            jit=True,
            precision="float64",
            solver=ssf.IMEX,
            field_solver="cells.solver.capacitive_reduction_gauged_damped_newton@2",
            max_steps=int(math.ceil(end / dt)) + 8,
            max_trace_bytes=2**31,
            material_balance_atol_fmol={s: 1e-10 for s, _ in ssf.ION_SPECIES},
        ),
    )
    raw = cs.frozen_definition(raw)
    volumes = {CELL: cell_pL, NODE: node_pL}
    for species, amounts in rows.items():
        raw = add_inventory_species(
            raw, species, trace_mM=TRACE_mM, diffusivity_m2_per_s=ssf.D_S, floor_fmol=floor
        )
        for node in (*raw["model"]["cells"], *raw["model"]["extracellular"]):
            if node["id"] in amounts:
                node["initial_amount_fmol"][species] = float(amounts[node["id"]])
        if set(amounts) - set(volumes):
            raise ValueError(f"{species}: amounts at unknown nodes {sorted(amounts)}")
    return raw


def rows_reactions(world):
    """W5's rows {species: {node: fmol}}: S in the cell and the node; X, Y, W in the cell."""
    r = world["rows_fmol"]
    return {
        "S": {CELL: r["S_cell"], NODE: r["S_node"]},
        "X": {CELL: r["X"]},
        "Y": {CELL: r["Y"]},
        "W": {CELL: r["W"]},
    }


def rows_gene(world):
    """W6's rows: N, M and Pi in the cell, R in the cell and the node."""
    r = world["rows_fmol"]
    return {
        "N": {CELL: r["N"]},
        "M": {CELL: r["M"]},
        "Pi": {CELL: r["Pi"]},
        "R": {CELL: r["R_cell"], NODE: r["R_node"]},
    }


# ------------------------------------------------------------------ the writers


def population(world, *, copy_index, seed):
    """The population's block (module docstring) from the world's `population`."""
    p = world["population"]
    channels = []
    for c in p["channels"]:
        read = c.get("read")
        channels.append(
            dict(
                id=c["id"],
                reactants=dict(c["reactants"]),
                products=dict(c["products"]),
                rate_per_s=float(c["rate_constant"]),
                read=None if read is None else dict(species=read["species"], at=AT[read["at"]]),
            )
        )
    transfer = p["transfer"]
    return dict(
        law=POPULATION,
        species=[dict(id=transfer["species"], catalogue=None, evidence=None)],
        read_species=[],
        seed=int(seed),
        trace_events=TRACE_EVENTS,
        populations=[
            dict(
                id=POPULATION_ID,
                unit_states=[
                    dict(id=u["id"], subunits=int(u["subunits"])) for u in p["unit_states"]
                ],
                channels=channels,
                transfers=[
                    dict(
                        id=TRANSFER_ID,
                        species=transfer["species"],
                        conductance_pL_per_s={
                            k: float(v) for k, v in transfer["conductance_pL_per_s"].items()
                        },
                    )
                ],
                division=None,
                sites=[
                    dict(
                        id=SITE.format(copy=int(copy_index)),
                        patch=PATCH,
                        initial_counts={k: int(v) for k, v in p["initial_counts"].items()},
                    )
                ],
            )
        ],
        divisions=[],
    )


def reactions(world):
    """(D152's block, its controls) for W5's reactions in the cell (module docstring)."""
    listed = []
    for row in ("X", "S", "Y", "W"):
        moieties = {m: w[row] for m, w in MOIETIES["reactions"].items() if row in w}
        listed.append(
            dict(id=row, moieties=moieties, standard_mu_RT=0.0, catalogue=None, evidence=None)
        )
    declared = []
    for r in world["reactions"]:
        order = sum(int(v) for v in r["reactants"].values())
        if UNIT.get(order) != r["rate_unit"]:
            raise ValueError(f"{r['id']}: a rate in {r['rate_unit']!r} at order {order}")
        declared.append(
            dict(
                id=r["id"],
                sites={"cells": [CELL]},
                reactants={k: int(v) for k, v in r["reactants"].items()},
                products={k: int(v) for k, v in r["products"].items()},
                law="mass_action",
                rate_constant=float(r["rate_constant"]),
                factors=[],
            )
        )
    block = dict(
        law=REACTIONS, standard_concentration_mM=REACTION_C0_mM, species=listed, reactions=declared
    )
    controls = [
        dict(reaction_id=r["id"], site=None, schedule=[dict(time=0.0, multiplier=1.0)])
        for r in declared
    ]
    return block, controls


def gene_moieties(g):
    """LAWS.md §3's two sums over N, M, Pi and R: nucleoside and phosphorus (per molecule)."""
    L = int(g["residues"])
    return {"nucleoside": {"N": 1, "M": 1, "R": L}, "phosphorus": {"N": 3, "M": 1, "Pi": 1, "R": L}}


def gene(world):
    """(the gene unit's block, its schedules) for W6 (module docstring)."""
    g = world["gene"]
    L, product = int(g["residues"]), g["product"]
    degradation = g["degradation"]
    if degradation["polymer"] != product or len(degradation["monomers"]) != 1:
        raise ValueError("W6 degrades its product into one monomer")
    ((monomer, total),) = degradation["monomers"].items()
    per_residue, rest = divmod(int(total), L)
    if rest or per_residue < 1:
        raise ValueError("the degradation's monomers are a whole count per residue")
    mu = {k: float(v) for k, v in g["mu_RT"].items()}
    block = dict(
        law=GENE,
        standard_concentration_mM=float(g["c0_mM"]),
        species=[
            dict(id=row, catalogue=None, evidence=None, standard_mu_RT=mu[row])
            for row in ("N", "M", "Pi", "R")
        ],
        pools=[dict(id=POOL, cell=CELL, machines=float(g["machines_copies"]))],
        chains=[
            dict(
                id=CHAIN,
                pool=POOL,
                template=dict(copies=int(g["template_copies"])),
                product=product,
                residues=L,
                stages=int(g["stages"]),
                speed_per_s=float(g["speed_per_s"]),
                draws={k: int(v) for k, v in g["draws"].items()},
                releases={k: int(v) for k, v in g["releases"].items()},
                saturation_mM={k: float(v) for k, v in g["saturation_mM"].items()},
            )
        ],
        degradations=[
            dict(
                id=DEGRADATION,
                cell=CELL,
                polymer=product,
                residues=L,
                monomers={monomer: per_residue},
                standard_free_energy=None,
            )
        ],
        transfers=[],
    )
    controls = [
        dict(route_id=CHAIN, schedule=[dict(time=0.0, value=float(g["initiation_per_mM_s"]))]),
        dict(
            route_id=DEGRADATION, schedule=[dict(time=0.0, value=float(degradation["rate_per_s"]))]
        ),
    ]
    return block, controls


def with_registry(raw, world):
    """The gene rows' potentials and moieties declared to the model's registry (W6)."""
    out = copy.deepcopy(raw)
    g = world["gene"]
    m = out["model"]
    m["standard_concentration_mM"] = float(g["c0_mM"])
    for entry in m["species"]:
        if entry["id"] in g["mu_RT"]:
            entry["standard_mu_RT"] = float(g["mu_RT"][entry["id"]])
    m["moieties"] = [dict(id=k, weights=v) for k, v in gene_moieties(g).items()]
    return out


# ------------------------------------------------------------------ one run's definition


def definition(inputs, run):
    """The run's composite definition (module docstring), checked by check_world."""
    world = world_of(inputs, run)
    kind = world["kind"]
    if kind not in ("reactions", "gene"):
        raise ValueError(f"unknown world kind {kind!r}")
    first = run["first"]
    if first not in (kind, "population"):
        raise ValueError(f"{run['name']}: first is {first!r} in a {kind} world")
    rows = rows_reactions(world) if kind == "reactions" else rows_gene(world)
    raw = skeleton(
        rows,
        cell_pL=float(world["cell_pL"]),
        node_pL=float(world["node_pL"]),
        dt=float(run["step_s"]),
        end=float(world["end_s"]),
        samples=world["samples_s"],
        floor=FLOOR_FMOL[kind],
    )
    units = population(world, copy_index=run["copy"], seed=seed_of(inputs, run))
    if kind == "reactions":
        writer, controls = reactions(world)
        raw["experiment"]["reaction_controls"] = controls
    else:
        raw = with_registry(raw, world)
        writer, controls = gene(world)
        raw["experiment"]["polymerisation_controls"] = controls
    order = [units, writer] if first == "population" else [writer, units]
    raw["model"]["operators"] = copy.deepcopy(order)
    check_world(raw, kind)
    return raw


def check_world(raw, kind):
    """SPEC.md §1's structure (module docstring): two writers, one site, no other route."""
    m = raw["model"]
    laws = [op["law"] for op in m["operators"]]
    if sorted(laws) != sorted([POPULATION, WRITERS[kind]]):
        raise ValueError(f"the writers are {laws}, not the population and the {kind}")
    if m["faces"] or m["junctions"] or m["channels"]:
        raise ValueError("a copy has no face, junction or channel")
    for patch in m["membranes"]:
        if patch.get("pump") or patch.get("calcium_pump"):
            raise ValueError(f"{patch['id']} holds a pump")
        moving = {s: v for s, v in patch["permeability_m_per_s"].items() if v != 0.0}
        if moving:
            raise ValueError(f"{patch['id']} conducts {sorted(moving)}")
    if [c["id"] for c in m["cells"]] != [CELL]:
        raise ValueError("a copy is one cell")
    finite = [n["id"] for n in m["extracellular"] if not n.get("reservoir")]
    if finite != [NODE]:
        raise ValueError("a copy has one finite outside node")
    units = next(op for op in m["operators"] if op["law"] == POPULATION)
    sites = [s for p in units["populations"] for s in p["sites"]]
    if len(units["populations"]) != 1 or len(sites) != 1 or sites[0]["patch"] != PATCH:
        raise ValueError("a copy's population has one site, on the contact patch")
