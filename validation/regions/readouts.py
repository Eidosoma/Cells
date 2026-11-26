"""FR-33's regional readouts and its host-side passive tracer, from the engine's existing records
(docs/LABELLED_PROTEIN_READOUTS.md; docs/COHORT_LABELS_DESIGN.md, option C). Validation only: no
engine change.

**The world map** (world_map) gives, for one species:
- its nodes: the cells, then the outside nodes;
- which cell owns each compartment (cells.operator.cell_owned_compartments@1);
- each exchange route's source and destination.

**The region export** (region_rows): one row per sample for one species and a declared region, a
list of one cell's distinct nodes (a node named twice is refused). Each sample is resolved once to
the one accepted step its time names (step_index), as the tracer's label switches are. Amounts are
in fmol; losses and transfers are cumulative from t = 0. Every row is held to 0 <= inside <= whole
cell, so outside >= 0, within its stored amounts' rounding.
- inside: the amount over the region's nodes;
- outside: the amount over the cell's other nodes (its cytosol and its other compartments);
- whole_cell: inside + outside, the cell and every compartment it owns;
- loss per node: turnover's cleared amount at each of the cell's nodes (turnover_cleared_fmol at the
  cell, turnover_outside_cleared_fmol at a compartment), with a reaction's consumed amount;
- transfer per route: each exchange route's amount moved from its source to its destination
  (exchange_moved_fmol counts export positive, so an import's is negated);
- and, beside them, the amount at each of the cell's nodes and the cumulative production there
  (turnover_produced_fmol, with a reaction's produced amount).

**A label's amounts** (label_nodes; FR-42's neutral labels, D289, which replaced D1's label
families, retired by D300): where cells.operator.neutral_arrival_labels@1 labels the species, the label owner
carries each label's shares across every mover the engine follows (faces and routes included), so a
label's amount at a node is the species' amount there times the label's share, read from the
state, at every node. The movers' cumulative records stay the species' own (region_rows), since
shares record no per-label flow.

**What each tool reads, and what it refuses at setup** (check_movers, fail closed). The export
reads turnover, exchange and the reactions; the tracer reads turnover and exchange only. Each
refuses a world in which anything else could move the species:
- a charged species (its channel, pump and membrane fluxes are in-step laws neither tool reads);
- a face's diffusion, or a junction's or a patch's permeation, of the species;
- every operator law that it neither reads nor lists as shown inert (SHOWN_INERT: laws whose
  declarations write no species amount, provide no amount view and close no node). REFUSED gives
  each registered law's reason, and a law in neither list is refused until it is classified here;
- every declared kind, since none is classified.

The export's transfer columns would miss those moves. For the tracer it is worse: a two-way
movement can leave every net record at zero while labelled material goes one way and unlabelled
the other (two equal nodes exchanging by diffusion keep both totals and the net face flux at 0).
The tracer would then report no movement at all. A law that moves every species at its nodes
without naming one (the wash, cells.operator.scheduled_compartment_wash@1) is refused too: a check that looked
for a species field would miss it, and the tracer would keep the washed-out label (a review
finding, 21 November 2026).

**The tracer** (trace) carries cohorts within the species' row, beside it, from the movers'
per-step records. It reads every accepted step, and changes no flux, so it applies where no law
reads the cohort.
- **Each step's records:** at each node, turnover's production and loss; on each exchange route,
  the amount moved from its source to its destination. Each record is one-way: a route moves only
  from its source, so its record carries the direction of every labelled molecule it moves.
- **A closure check:** each node's change must equal those records, or the trace is refused. A
  mover it does not read (a face, a junction, permeation) would break it.
  - **Its tolerance** is 64 ulps of the terms actually summed: the step's amounts and records,
    each stored amount's reference and increment, and each cumulative record at both ends of the
    step (records_rounding).
  - **Why those sizes count:** with the step's own amounts alone, a long run's drained node was
    refused for the rounding of its reference and its records, from about 1% of its reference
    on (D260; tests/unit/test_region_readouts.py).
  - **Its floor:** an unread movement smaller than those 64 ulps is not seen, and in a long run
    the cumulative records set that floor.
- **Production** joins the cohort that the label schedule names at the step's start. Each label
  switch is resolved once to the one accepted step its time names, within TIME_RTOL (step_index),
  and the schedule is read by that index alone: a time no step matches, or that two match, is
  refused (D265: 0.3 and 0.1 + 0.2 had assigned the step's production differently).
- **A node's outflow** (its loss and its routes out) leaves each cohort in proportion to that
  cohort's mean amount over the step, (start + end)/2, the trapezoid. A route's outflow carries
  its source's split into its destination.
- **The step's cohort amounts** at every node solve one linear system per step (nodes by nodes,
  shared by every cohort). Every cohort's amounts sum to the node's amount.
- **The returned rows are checked** (_check_rows): at every row and node, each cohort is
  non-negative within the rounding of the step's own terms, and the cohorts sum to the node's
  amount within the closure's tolerance, on the dictionary as returned. Cohort names
  `unlabelled` and `produced` are the tracer's own and are refused as a caller's.

**Its limits.**
- **The resolution** (a review finding, 21 November 2026). A cohort present at a step's start
  survives it as (1 - r)/(1 + r), with r = O/S the node's outflow over the step against its start
  and end amounts, S = n0 + n1. Where the node gains no material in the step this equals n1/n0,
  so it is exact for any r. Where material enters (production or a route in), it is not:
  - at a steady node it is the (1,1) Pade form of the true survival e^(-2r), 2r^3/3 off per step;
  - at r = 1 it reads 0, where the truth is e^(-2) = 0.135; above 1 it is negative (the
    reviewer's steady pool: 1 fmol made and cleared at 4 per s, one 1 s step: -0.333 for e^(-4)
    = 0.0183), and the closure check cannot see it, since the cohorts still sum to the amount.
  - A node that sends material along a route needs the same bound, though its own split stays
    exact: its arrivals shape its receiver's. A donor draining most of itself in one step (r =
    0.76) into a receiver at r = 0.01 put 9.4e-4 of the receiver's amount on the wrong cohort in
    that one step.
  So the trace refuses a step in which a node that gains material, or sends it along a route, has
  r above RESOLUTION = 0.01. Whether a node gained or sent material reads the step's own terms,
  not the closure's tolerance (D265 finding 4): after a long drain the cumulative records'
  rounding can exceed the node's whole pool, which had hidden a step at r = 2 (a cohort at -33%).
  resolution_largest is the largest r over the nodes the bound tests, those that gained material
  or sent it along a route in a step. It is 0.0 when no node did: a
  node that only loses material is exact at any r and is not counted, so a loss-only run's 0.0 does
  not mean its r was small. At that bound,
  measured on 15 closed-form scenarios (a steady pool, a node filling from near-empty, a draining
  node with production, and a donor drained by a route at 0.5 to 100 times the node's loss rate,
  the node starting at 1e-3 to 1e3 times the donor's amount):
  - each step adds at most 7.61e-6 of the node's amount to a starting cohort's error (6.5e-7 for
    the steady pool, near Pade's 2r^3/3);
  - over each run (five e-foldings of the slower of the node's loss and the route, at most 30
    route time constants) the cohort stays within 5.6e-4 of its exact amount, relative to itself
    (1.7e-4 for the steady pool, near kT r^2/3), the worst a node fed slowly by a donor 1000 times
    larger. The error grows about linearly with the e-foldings run;
  - it is second order: halving the step quarters it.
  A node empty at both ends of a step holds no cohort; material that passes through an empty node
  within one step is refused.
- **Directions.** It is right only where the per-step records carry the direction of every
  labelled movement, as one-way routes do. A two-way law's net record (Fick's flux on a face, a
  junction's or a patch's permeation, a reversible reaction) does not, so those are refused at
  setup. Tracing through them needs engine work (docs/COHORT_LABELS_DESIGN.md, option C): the
  label carried by the transport law itself, as label rows, or directional records from each
  two-way law.
- **The split.** At a node with no inflow, every cohort leaves at the node's one per-molecule rate
  under first-order laws, so the composition is constant over the step and the split is exact: two
  cohorts at the example's donor keep their fractions to 5.6e-16. Where material flows in during a
  step, the composition changes within it:
  - the start-of-step split of the design note would be first order in dt; the trapezoid used here
    is second order;
  - its size is set by the inflow within one step relative to the node's amount, not by k dt alone.
    In the example the cell first receives about its own amount every millisecond. The error of
    its own starting cohort is 1.3e-6, 6.4e-6, 2.6e-5 and 9.4e-5 at steps of 1, 2, 4 and 8 ms. The
    made cohorts' errors are 1.3e-7 and 2.2e-7 at 1 ms;
  - the received cohort's error, 1.8e-7 at 1 ms, is mostly the engine's own: the cell's total
    differs from the closed form by 1.1e-7.

Under age- or region-selective laws a cohort's own rate differs, so the cohorts are dynamics, not
bookkeeping: that is the design note's option D, not this tracer.
"""

import numpy as np

from cells.registry.models import get_model

TURNOVER = "cells.operator.scheduled_species_turnover@1"
EXCHANGE = "cells.operator.scheduled_species_exchange@1"
REACTIONS = "cells.operator.local_species_reactions@1"
COMPARTMENTS = "cells.operator.cell_owned_compartments@1"
CLOSURE_ULPS = 64
# The largest O/S at a node that gains material in a step or sends it along a route (module
# docstring, "The resolution").
RESOLUTION = 0.01
RESERVED = ("unlabelled", "produced")  # The tracer's own cohorts.
TIME_RTOL = 1e-12  # A requested time names the step within this of it (relative, at least 1 s).


def step_index(times, t, what):
    """The one accepted step a requested time names (D265 finding 2): the step whose time lies
    within TIME_RTOL max(1, |t|) s of t, so equivalent spellings (0.3 and 0.1 + 0.2) name the same
    step, and the tracer's labels and the export's samples use that index alone. A time no step
    matches, or that two steps match, is refused."""
    tol = TIME_RTOL * max(1.0, abs(t))
    hits = [k for k, u in enumerate(times) if abs(u - t) <= tol]
    if not hits:
        raise ValueError(f"{what} at {t!r} s is not an accepted step's time")
    if len(hits) > 1:
        raise ValueError(f"{what} at {t!r} s is ambiguous: {len(hits)} steps within {tol:.3g} s")
    return hits[0]


def _distinct(region):
    """Refuse a region that names a node twice (D265 finding 5: each would be counted twice)."""
    if len(set(region)) != len(region):
        raise ValueError(f"the region {list(region)} names a node twice")


def world_map(spec, species):
    """The species' row, its nodes, the owners of the compartments and the exchange routes."""
    m = spec.model
    cells = [c.id for c in m.cells]
    outside = [o.id for o in m.extracellular]
    owner = {}
    routes = []
    for op in m.operators:
        if op.law == COMPARTMENTS:
            owner.update({c.node: c.owner for c in op.compartments})
        if op.law == EXCHANGE:
            routes = [
                dict(
                    id=r.id,
                    index=i,
                    species=r.species,
                    source=r.cell if r.direction == "export" else r.outside,
                    destination=r.outside if r.direction == "export" else r.cell,
                    sign=1.0 if r.direction == "export" else -1.0,
                )
                for i, r in enumerate(op.routes)
            ]
    return dict(
        row=list(m.species_ids).index(species),
        cells=cells,
        outside=outside,
        nodes=cells + outside,
        owner=owner,
        routes=[r for r in routes if r["species"] == species],
    )


EXPORT_READS = (TURNOVER, EXCHANGE, REACTIONS)
TRACER_READS = (TURNOVER, EXCHANGE)
# Laws shown to move no species amount: their declarations write no amount field, provide no
# amount view and close no node (test_region_readouts.py checks each against its contract).
SHOWN_INERT = {
    "cells.operator.ideal_osmosis_linear_compliance_water@1": "changes volumes, never amounts",
    "cells.operator.membrane_entity_state@1": "provides channel abundances, membrane areas and capacitances",
    COMPARTMENTS: "declares which cell owns each compartment",
    "cells.operator.species_regulated_availability@1": "scales other laws' availabilities; its state is its own",
    "cells.operator.species_regulated_availability@2": "scales other laws' availabilities and rates; its state "
    "is its own",
    "cells.operator.site_occupant_replacement@1": "resets site pools at replacement events; free amounts stay",
    "cells.operator.neutral_arrival_labels@1": "holds labels' shares of species rows; it moves no amount (FR-42)",
}
# Every other registered law, with why it is refused (fail closed: a law in no list is refused
# too, until it is classified here).
REFUSED = {
    REACTIONS: "is not read by the tracer (a reversible reaction's net record has no direction)",
    "cells.operator.site_occupancy@1": "binds and releases its ligands (a two-way exchange with bound pools)",
    "cells.operator.population_unit_turnover@1": "consumes its precursors into units",
    "cells.operator.integer_unit_population@1": "moves species across its sites' patches, between cells and "
    "outside nodes; the readouts do not read its transfers",
    "cells.operator.k_anion_symport_mass_action@1": "moves its potassium and anion across membranes in-step",
    "cells.operator.electrode_current_injection@1": "moves its carriers between the electrode and a cell",
    "cells.operator.scheduled_cell_replacement@1": "swaps a replaced cell's pools at its events",
    "cells.operator.scheduled_cell_replacement@2": "swaps a replaced cell's pools at its events",
    "cells.operator.isopotential_partition@1": "splits a dividing cell's contents between its daughters",
    "cells.operator.cytoplasmic_bridge_closure@1": "sets a daughter bridge's availability (with the partition)",
    "cells.operator.scheduled_membrane_insertion@1": "opens onset nodes with their declared contents",
    "cells.operator.scheduled_membrane_insertion@2": "opens and retires nodes and patches",
    "cells.operator.restricted_cleft_lumen@1": "fills a lumen node with bath fluid as it grows",
    "cells.operator.restricted_cleft_lumen@2": "fills a lumen node with bath fluid as it grows",
    "cells.operator.scheduled_bath_composition@1": "sets held baths' compositions at its events",
    "cells.operator.scheduled_membrane_trafficking@1": "moves membrane, and the charges on it, between nodes",
    "cells.operator.scheduled_compartment_wash@1": "collects and refills every free species at its nodes",
    # Gene regulation's option A (G4): a recorded exception naming the table's owner.
    "cells.operator.templated_polymerisation@1": "makes, degrades and recharges species at its routes' cells; "
    "neither tool reads its counters",
}


def check_movers(spec, species, reads):
    """Refuse a world in which anything but the laws `reads` could move the species (module
    docstring; fail closed): a face's diffusivity, a junction's or a patch's permeability for it,
    every operator law neither read nor shown inert (REFUSED says why), and every declared kind."""
    m = spec.model
    s = list(m.species_ids).index(species)
    found = []
    valence = getattr(m, "valence", None)
    if valence is None or valence[s] != 0:
        found.append(
            "it is charged, or its charge is not declared (its channel, pump and membrane fluxes "
            "are in-step laws neither tool reads)"
        )
    for face in getattr(m, "faces", ()):
        if face.diffusivity_m2_per_s[s] != 0:
            found.append(f"face {face.id} diffuses it")
    for junction in getattr(m, "junctions", ()):
        if junction.permeability_m_per_s[s] != 0:
            found.append(f"junction {junction.id} permeates it")
    for patch in getattr(m, "membranes", ()):
        if patch.permeability_m_per_s[s] != 0:
            found.append(f"patch {patch.id} permeates it")
    for op in m.operators:
        if op.law in reads or op.law in SHOWN_INERT:
            continue
        why = REFUSED.get(op.law, "is not classified here (neither read nor shown inert)")
        found.append(f"{op.law} {why}")
    for kind_id, _ in getattr(m, "kinds", ()):
        found.append(f"kind {kind_id} is declared (no kind is read or shown inert)")
    if found:
        raise ValueError(
            f"{species}: {'; '.join(found)}. Not read here: a two-way movement's net record can "
            "stay at zero while labelled and unlabelled material cross in opposite directions, so "
            f"only {', '.join(reads)} are read, beside laws shown inert"
        )


def runs(spec):
    """(times, states) of every accepted step of a windowed run of `spec` (memory: one state per
    step, so this suits the short worlds of the examples)."""
    from cells.execution.windows import WindowPolicy, iter_windows

    times, states = [], []
    for window in iter_windows(spec, WindowPolicy(window_steps=1000, recording="observations")):
        for i, t in enumerate(np.asarray(window.times)):
            if times and float(t) <= times[-1]:
                continue  # Adjacent windows share an endpoint.
            times.append(float(t))
            states.append(type(window.history)(*(np.asarray(v)[i] for v in window.history)))
    return times, states


def _field(state, name, shape):
    value = getattr(state, name, None)
    return np.zeros(shape) if value is None else np.asarray(value)


def node_records(spec, layout, state, wmap):
    """(amount, produced, lost) per node and moved per route, cumulative, at one state. A mover
    it does not read (a face, a junction, permeation) shows in the tracer's closure check."""
    row, nc, no = wmap["row"], len(wmap["cells"]), len(wmap["outside"])
    ref_c = np.asarray(layout.amount_reference)[row, :nc]
    ref_o = np.asarray(layout.extracellular_amount_reference)[row, :no]
    amount = np.concatenate([
        ref_c + np.asarray(state.amount_increment)[row, :nc],
        ref_o + np.asarray(state.extracellular_amount_increment)[row, :no],
    ])  # fmt: skip
    species = np.asarray(state.amount_increment).shape[0]
    shape_c, shape_o = (species, nc), (species, no)

    def at(name, shape, n):
        return _field(state, name, shape)[row, :n]

    produced = np.concatenate([
        at("turnover_produced_fmol", shape_c, nc) + at("reaction_produced_fmol", shape_c, nc),
        at("reaction_outside_produced_fmol", shape_o, no),
    ])  # fmt: skip
    lost = np.concatenate([
        at("turnover_cleared_fmol", shape_c, nc) + at("reaction_consumed_fmol", shape_c, nc),
        at("turnover_outside_cleared_fmol", shape_o, no)
        + at("reaction_outside_consumed_fmol", shape_o, no),
    ])  # fmt: skip
    moved_all = _field(state, "exchange_moved_fmol", (0,))
    moved = np.array([r["sign"] * moved_all[r["index"]] for r in wmap["routes"]])
    return amount, produced, lost, moved


def stored_magnitudes(layout, state, wmap):
    """[node] |reference| + |increment| of the species' stored amount at each node: the size whose
    rounding the amount the tracer reads carries (the engine stores anchored increments)."""
    row, nc, no = wmap["row"], len(wmap["cells"]), len(wmap["outside"])
    cells = np.abs(np.asarray(layout.amount_reference)[row, :nc]) + np.abs(
        np.asarray(state.amount_increment)[row, :nc]
    )
    outside = np.abs(np.asarray(layout.extracellular_amount_reference)[row, :no]) + np.abs(
        np.asarray(state.extracellular_amount_increment)[row, :no]
    )
    return np.concatenate([cells, outside])


def records_rounding(stored, stored_now, previous, now, routes, index):
    """[node] the sizes whose rounding a step's summed terms carry, beyond the step's own amounts
    (D260): the stored amount's reference and increment and each cumulative record (produced,
    lost, and each route's at its source and destination), at both ends of the step."""
    scale = stored + stored_now + sum(np.abs(previous[j]) + np.abs(now[j]) for j in (1, 2))
    for r, a0, a1 in zip(routes, previous[3], now[3], strict=True):
        for node in (r["source"], r["destination"]):
            scale[index[node]] += abs(a0) + abs(a1)
    return scale


def region_rows(spec, times, states, species, region, *, samples=None):
    """The region export (module docstring) at the sampled times (every given time by default):
    {times, inside_fmol, outside_fmol, whole_cell_fmol, node_fmol: {node: [...]},
    produced_fmol: {node: [...]}, loss_fmol: {node: [...]}, transfer_fmol: {route: [...]}, region,
    cell_nodes}."""
    check_movers(spec, species, EXPORT_READS)
    _distinct(region)
    wmap = world_map(spec, species)
    _, layout = get_model(spec.model).initial_values(spec)
    owners = {wmap["owner"].get(n) for n in region if n not in wmap["cells"]}
    owners |= {n for n in region if n in wmap["cells"]}
    if len(owners) != 1 or None in owners:
        raise ValueError(f"the region {region} is not the nodes of one cell")
    (cell,) = owners
    cell_nodes = [cell] + [n for n, o in wmap["owner"].items() if o == cell]
    index = {n: i for i, n in enumerate(wmap["nodes"])}
    if samples is None:
        picked = list(range(len(times)))
    else:
        picked = [step_index(times, t, "the sample") for t in samples]
        if len(set(picked)) != len(picked):
            raise ValueError("two samples name the same step")
        picked.sort()
    eps = np.finfo(float).eps
    routes = wmap["routes"]
    out = dict(times=[], inside_fmol=[], outside_fmol=[], whole_cell_fmol=[],
               node_fmol={n: [] for n in cell_nodes}, produced_fmol={n: [] for n in cell_nodes},
               loss_fmol={n: [] for n in cell_nodes},
               transfer_fmol={r["id"]: [] for r in routes},
               region=list(region), cell_nodes=cell_nodes)  # fmt: skip
    if len(times) != len(states):
        raise ValueError("times and states differ in length")
    for k in picked:
        t, state = times[k], states[k]
        amount, made, lost, transfers = node_records(spec, layout, state, wmap)
        moved = {route["id"]: value for route, value in zip(routes, transfers, strict=True)}
        inside = sum(amount[index[n]] for n in region)
        whole = sum(amount[index[n]] for n in cell_nodes)
        # The row's bounds (finding 5): 0 <= inside <= whole cell, so outside >= 0, within the
        # rounding of the cell's stored amounts.
        stored = stored_magnitudes(layout, state, wmap)
        tol = CLOSURE_ULPS * eps * sum(abs(amount[index[n]]) + stored[index[n]] for n in cell_nodes)
        if inside < -tol or whole - inside < -tol:
            raise ValueError(
                f"the region {list(region)} at t = {t} holds {inside} fmol of a cell holding "
                f"{whole} fmol: outside {whole - inside} fmol, below 0"
            )
        out["times"].append(t)
        out["inside_fmol"].append(float(inside))
        out["outside_fmol"].append(float(whole - inside))
        out["whole_cell_fmol"].append(float(whole))
        for n in cell_nodes:
            out["node_fmol"][n].append(float(amount[index[n]]))
            out["produced_fmol"][n].append(float(made[index[n]]))
            out["loss_fmol"][n].append(float(lost[index[n]]))
        for r in routes:
            out["transfer_fmol"][r["id"]].append(float(moved.get(r["id"], 0.0)))
    return out


def label_nodes(spec, times, states, species, label, *, samples=None):
    """A label's amounts (module docstring) at the sampled times (every given time by default):
    {times, node_fmol: {node: [...]}, nodes, species, label}, at every node (the cells, then the
    outside nodes), each the species' amount there times the label's share, the shares read from
    the states (cells.operator.neutral_arrival_labels@1's label_share and label_outside_share). A species or label
    the world does not label is refused."""
    owner = next(
        (d for d in getattr(spec.model, "operators", ()) if d.law == "cells.operator.neutral_arrival_labels@1"),
        None,
    )
    labelled = [] if owner is None else [s.id for s in owner.species]
    if species not in labelled:
        raise ValueError(f"{species} is not labelled (cells.operator.neutral_arrival_labels@1 names {labelled})")
    entry = owner.species[labelled.index(species)]
    if label not in entry.labels:
        raise ValueError(f"{species} has no label {label!r} (its labels: {list(entry.labels)})")
    j, position = labelled.index(species), entry.labels.index(label)
    wmap = world_map(spec, species)
    _, layout = get_model(spec.model).initial_values(spec)
    nc, no = len(wmap["cells"]), len(wmap["outside"])
    if samples is None:
        picked = list(range(len(times)))
    else:
        picked = sorted(step_index(times, t, "the sample") for t in samples)
    out = dict(times=[], node_fmol={n: [] for n in wmap["nodes"]}, nodes=list(wmap["nodes"]),
               species=species, label=label)  # fmt: skip
    for k in picked:
        state = states[k]
        amount = node_records(spec, layout, state, wmap)[0]
        share = np.concatenate(
            (
                np.asarray(state.label_share)[j, position, :nc],
                np.asarray(state.label_outside_share)[j, position, :no],
            )
        )
        out["times"].append(float(times[k]))
        for i, n in enumerate(wmap["nodes"]):
            out["node_fmol"][n].append(float(amount[i]) * float(share[i]))
    return out


def _cohort_shares(cohorts, nodes):
    """[node, cohort] the caller's cohorts' fractions of each node's starting amount, refused
    where a name is the tracer's own, a node is unknown, a fraction lies outside [0, 1] or a node's
    fractions sum above 1 (by more than 1e-12; within it they are scaled to sum to 1)."""
    index = {n: i for i, n in enumerate(nodes)}
    share = np.zeros((len(nodes), len(cohorts)))
    for c, (name, fractions) in enumerate(cohorts.items()):
        if name in RESERVED:
            raise ValueError(
                f"cohort {name!r} is the tracer's own name ({', '.join(RESERVED)}): name it "
                "otherwise (the tracer's own column would replace it on export)"
            )
        for node, fraction in fractions.items():
            if node not in index:
                raise ValueError(f"cohort {name!r} names an unknown node {node!r}")
            if not 0.0 <= fraction <= 1.0:
                raise ValueError(f"cohort {name!r}'s fraction at {node} lies outside [0, 1]")
            share[index[node], c] = fraction
    total = share.sum(axis=1)
    if np.any(total > 1.0 + 1e-12):
        raise ValueError("a node's cohort fractions sum above 1")
    over = total > 1.0
    share[over] /= total[over, None]
    return share


def _check_rows(result, totals, scales, local_scales):
    """The returned rows' invariant (module docstring): at every row and node, each cohort
    non-negative within the rounding of the step's own terms (local_scales: D265 finding 4, since
    the cumulative records' rounding can exceed a drained node's whole pool), and the cohorts
    summing to the node's amount within the closure's tolerance (scales), on the dictionary as
    returned (so a column a name replaced, or a negative split, is seen)."""
    eps = np.finfo(float).eps
    amount = result["amount"]
    for node, total in totals.items():
        for k, t in enumerate(result["times"]):
            tol = CLOSURE_ULPS * eps * scales[node][k]
            values = [amount[c][node][k] for c in amount]
            if min(values) < -CLOSURE_ULPS * eps * local_scales[node][k]:
                raise ValueError(
                    f"the trace's cohorts at {node}, t = {t}, are not non-negative ({min(values)} "
                    "fmol)"
                )
            if abs(sum(values) - total[k]) > tol:
                raise ValueError(
                    f"the trace's cohorts at {node}, t = {t}, sum to {sum(values)} fmol, not the "
                    f"node's {total[k]} fmol"
                )


def trace(spec, times, states, species, cohorts, *, produced=()):
    """The passive tracer (module docstring) over consecutive accepted steps.

    cohorts: {name: {node: fraction of the node's starting amount}}; at each node the fractions sum
    to at most 1 over the cohorts, and a node no cohort names starts in "unlabelled" (a name the
    caller may not use, nor "produced"). produced: [(time, cohort), ...], the cohort new material
    joins from each time on ("produced" before the first). Returns {times, amount: {cohort: {node:
    [...]}}, loss: {cohort: {node: [...]}}, transfer: {cohort: {route: [...]}}, closure_largest,
    closure_bound, resolution_largest (the largest r = O/S over the nodes the bound tests, those
    that gained material or sent it along a route in a step; 0.0 when none did, since a loss-only
    node is exact at any r and is not counted), resolution_bound}; refused, with its reason, at
    setup (the
    movers), at a step the records do not close, at a step it cannot resolve (r above RESOLUTION
    at a node that gains material) and where a returned row breaks the invariant."""
    check_movers(spec, species, TRACER_READS)
    switches = sorted((step_index(times, t, f"the label switch to {c!r}"), c) for t, c in produced)
    if len({k for k, _ in switches}) != len(switches):
        raise ValueError("two label switches name the same step")
    wmap = world_map(spec, species)
    _, layout = get_model(spec.model).initial_values(spec)
    nodes, routes = wmap["nodes"], wmap["routes"]
    index = {n: i for i, n in enumerate(nodes)}
    names = list(cohorts)
    start = node_records(spec, layout, states[0], wmap)[0]
    share = _cohort_shares(cohorts, nodes)
    share = np.concatenate([share, (1.0 - share.sum(axis=1))[:, None].clip(min=0.0)], axis=1)
    names = names + ["unlabelled"]
    for label in [c for _, c in produced] + ["produced"]:
        if label not in names:
            names.append(label)
            share = np.concatenate([share, np.zeros((len(nodes), 1))], axis=1)
    x = start[:, None] * share  # [node, cohort]
    loss = np.zeros_like(x)
    moved = np.zeros((len(routes), len(names)))
    out = dict(times=[times[0]], amount=[x.copy()], loss=[loss.copy()], transfer=[moved.copy()])
    stored = stored_magnitudes(layout, states[0], wmap)
    totals, scales, locals_ = [start.copy()], [np.abs(start) + stored], [np.abs(start)]
    closure, bound, resolution = 0.0, 0.0, 0.0
    previous = node_records(spec, layout, states[0], wmap)
    eps = np.finfo(float).eps
    for k0, (t1, state) in enumerate(zip(times[1:], states[1:], strict=True)):
        now = node_records(spec, layout, state, wmap)
        stored_now = stored_magnitudes(layout, state, wmap)
        n0, n1 = previous[0], now[0]
        made, lost, m = now[1] - previous[1], now[2] - previous[2], now[3] - previous[3]
        inflow, outflow = np.zeros(len(nodes)), lost.copy()
        for r, amount in zip(routes, m, strict=True):
            inflow[index[r["destination"]]] += amount
            outflow[index[r["source"]]] += amount
        residual = (n1 - n0) - (made + inflow - outflow)
        scale = np.abs(n0) + np.abs(n1) + np.abs(made) + np.abs(lost) + inflow + outflow
        # The rounding the summed terms carry (D260): without it a node drained far below its
        # reference, or its cumulative records, was refused for their own rounding.
        scale = scale + records_rounding(stored, stored_now, previous, now, routes, index)
        closure = max(closure, float(np.max(np.abs(residual) / np.maximum(scale, 1e-300))))
        tol = CLOSURE_ULPS * eps * scale
        if np.any(np.abs(residual) > tol):
            raise ValueError(f"the records do not close the species' amounts at t = {t1}")
        bound = CLOSURE_ULPS * eps
        # The resolution (module docstring): r = O/S, tested where the node gains material or
        # sends it along a route (its route's arrivals then shape a receiver's split). Its test
        # reads the step's own terms (D265 finding 4): the closure's tolerance carries the
        # cumulative records' rounding, and after a long drain it can exceed the whole pool.
        local = np.abs(n0) + np.abs(n1) + np.abs(made) + np.abs(lost) + inflow + outflow
        local_tol = CLOSURE_ULPS * eps * local
        S = n0 + n1
        filled = S > 0
        inv = np.where(filled, 1.0 / np.where(filled, S, 1.0), 0.0)
        ratio = np.where(filled, outflow * inv, np.where(outflow > local_tol, np.inf, 0.0))
        checked = made + inflow > local_tol
        for r, amount in zip(routes, m, strict=True):
            s = index[r["source"]]
            checked[s] |= amount > local_tol[s]
        if np.any(checked):
            resolution = max(resolution, float(np.max(ratio[checked])))
        if np.any(checked & (ratio > RESOLUTION)):
            k = int(np.argmax(np.where(checked, ratio, -1.0)))
            raise ValueError(
                f"the step to t = {t1} s takes {outflow[k]:.6g} fmol out of {nodes[k]}, which "
                "gains material in it or sends it along a route: r = O/S = "
                f"{ratio[k]:.3g} of its start and end amounts, above the tracer's resolution "
                f"{RESOLUTION} (a cohort present at the step's start would survive as (1 - r)/(1 + "
                "r): 0 at r = 1, where the truth is e^-2 = 0.135, and negative above it; a route "
                "sender's arrivals shape its receiver's split); take smaller steps"
            )
        label = next((c for k, c in reversed(switches) if k <= k0), "produced")
        A = np.diag(1.0 + outflow * inv)
        B = x * (1.0 - outflow * inv)[:, None]
        B[:, names.index(label)] += made
        for r, amount in zip(routes, m, strict=True):
            i, s = index[r["destination"]], index[r["source"]]
            A[i, s] -= amount * inv[s]
            B[i] += amount * inv[s] * x[s]
        x1 = np.linalg.solve(A, B)
        mean = (x + x1) * inv[:, None]  # Each cohort's share of the step's outflow.
        loss += lost[:, None] * mean
        for k, (r, amount) in enumerate(zip(routes, m, strict=True)):
            moved[k] += amount * mean[index[r["source"]]]
        x, previous, stored = x1, now, stored_now
        out["times"].append(t1)
        out["amount"].append(x.copy())
        out["loss"].append(loss.copy())
        out["transfer"].append(moved.copy())
        totals.append(n1.copy())
        scales.append(scale)
        locals_.append(local)

    def by(array_list, labels):
        stacked = np.array(array_list)  # [time, label, cohort]
        return {name: {lab: stacked[:, j, c].tolist() for j, lab in enumerate(labels)}
                for c, name in enumerate(names)}  # fmt: skip

    result = dict(
        times=out["times"],
        amount=by(out["amount"], nodes),
        loss=by(out["loss"], nodes),
        transfer=by(out["transfer"], [r["id"] for r in routes]),
        closure_largest=closure,
        closure_bound=bound,
        resolution_largest=resolution,
        resolution_bound=RESOLUTION,
    )
    _check_rows(
        result,
        {n: [float(v[i]) for v in totals] for i, n in enumerate(nodes)},
        {n: [float(v[i]) for v in scales] for i, n in enumerate(nodes)},
        {n: [float(v[i]) for v in locals_] for i, n in enumerate(nodes)},
    )
    return result
