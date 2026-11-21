"""FR-33's regional readouts and its host-side passive tracer, from the engine's existing records
(docs/LABELLED_PROTEIN_READOUTS.md; docs/COHORT_LABELS_DESIGN.md, option C). Validation only: no
engine change.

**The world map** (world_map) gives, for one species:
- its nodes: the cells, then the outside nodes;
- which cell owns each compartment (cell_owned_compartments@1);
- each exchange route's source and destination.

**The region export** (region_rows): one row per sample for one species and a declared region, a
list of one cell's nodes. Amounts are in fmol; losses and transfers are cumulative from t = 0.
- inside: the amount over the region's nodes;
- outside: the amount over the cell's other nodes (its cytosol and its other compartments);
- whole_cell: inside + outside, the cell and every compartment it owns;
- loss per node: turnover's cleared amount at each of the cell's nodes (turnover_cleared_fmol at the
  cell, turnover_outside_cleared_fmol at a compartment), with a reaction's consumed amount;
- transfer per route: each exchange route's amount moved from its source to its destination
  (exchange_moved_fmol counts export positive, so an import's is negated);
- and, beside them, the amount at each of the cell's nodes and the cumulative production there
  (turnover_produced_fmol, with a reaction's produced amount).

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
without naming one (the wash, scheduled_compartment_wash@1) is refused too: a check that looked
for a species field would miss it, and the tracer would keep the washed-out label (a review
finding, 21 November 2026).

**The tracer** (trace) carries cohorts within the species' row, beside it, from the movers'
per-step records. It reads every accepted step, and changes no flux, so it applies where no law
reads the cohort.
- **Each step's records:** at each node, turnover's production and loss; on each exchange route,
  the amount moved from its source to its destination. Each record is one-way: a route moves only
  from its source, so its record carries the direction of every labelled molecule it moves.
- **A closure check:** each node's change must equal those records, within rounding, or the trace
  is refused. A mover it does not read (a face, a junction, permeation) would break it.
- **Production** joins the cohort that the label schedule names at the step's start. Each label
  switch must fall on a step's boundary, or the trace is refused.
- **A node's outflow** (its loss and its routes out) leaves each cohort in proportion to that
  cohort's mean amount over the step, (start + end)/2, the trapezoid. A route's outflow carries
  its source's split into its destination.
- **The step's cohort amounts** at every node solve one linear system per step (nodes by nodes,
  shared by every cohort). Every cohort's amounts sum to the node's amount.
- **The returned rows are checked** (_check_rows): at every row and node, each cohort is
  non-negative and the cohorts sum to the node's amount, both within the closure's tolerance, on
  the dictionary as returned. Cohort names `unlabelled` and `produced` are the tracer's own and
  are refused as a caller's.

**Its limits.**
- **The resolution** (a review finding, 21 November 2026). A cohort present at a step's start
  survives it as (1 - r)/(1 + r), with r = O/S the node's outflow over the step against its start
  and end amounts, S = n0 + n1. Where the node gains no material in the step this equals n1/n0,
  so it is exact for any r. Where material enters (production or a route in), it is not:
  - at a steady node it is the (1,1) Pade form of the true survival e^(-2r), 2r^3/3 off per step;
  - at r = 1 it reads 0, where the truth is e^(-2) = 0.135; above 1 it is negative (the
    reviewer's steady pool: 1 fmol made and cleared at 4 per s, one 1 s step: -0.333 for e^(-4)
    = 0.0183), and the closure check cannot see it, since the cohorts still sum to the amount.
  So the trace refuses a step in which a node that gains material has r above RESOLUTION = 0.01,
  and reports the largest such r (resolution_largest). At that bound, over four closed-form
  scenarios (a steady pool, a node filling from near-empty, a draining node with production, a
  node fed by a route), a node's starting cohort stays within 4.3e-4 of its exact amount,
  relative to that amount, after five e-foldings of loss, and each step adds at most 7.61e-6 of
  the node's amount (measured; for the steady pool 1.7e-4 and 6.5e-7, near Pade's kT r^2/3 and
  2r^3/3). The error is second order: halving the step quarters it. A node empty at both ends of
  a step holds no cohort; material that passes through an empty node within one step is refused.
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

TURNOVER = "scheduled_species_turnover@1"
EXCHANGE = "scheduled_species_exchange@1"
REACTIONS = "local_species_reactions@1"
COMPARTMENTS = "cell_owned_compartments@1"
CLOSURE_ULPS = 64
# The largest O/S at a node that gains material in a step (module docstring, "The resolution").
RESOLUTION = 0.01
RESERVED = ("unlabelled", "produced")  # The tracer's own cohorts.


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
    "ideal_osmosis_linear_compliance_water@1": "changes volumes, never amounts",
    "membrane_entity_state@1": "provides channel abundances, membrane areas and capacitances",
    COMPARTMENTS: "declares which cell owns each compartment",
    "species_regulated_availability@1": "scales other laws' availabilities; its state is its own",
    "species_regulated_availability@2": "scales other laws' availabilities and rates; its state "
    "is its own",
    "site_occupant_replacement@1": "resets site pools at replacement events; free amounts stay",
}
# Every other registered law, with why it is refused (fail closed: a law in no list is refused
# too, until it is classified here).
REFUSED = {
    REACTIONS: "is not read by the tracer (a reversible reaction's net record has no direction)",
    "site_occupancy@1": "binds and releases its ligands (a two-way exchange with bound pools)",
    "population_unit_turnover@1": "consumes its precursors into units",
    "k_anion_symport_mass_action@1": "moves its potassium and anion across membranes in-step",
    "electrode_current_injection@1": "moves its carriers between the electrode and a cell",
    "scheduled_cell_replacement@1": "swaps a replaced cell's pools at its events",
    "scheduled_cell_replacement@2": "swaps a replaced cell's pools at its events",
    "isopotential_partition@1": "splits a dividing cell's contents between its daughters",
    "cytoplasmic_bridge_closure@1": "sets a daughter bridge's availability (with the partition)",
    "scheduled_membrane_insertion@1": "opens onset nodes with their declared contents",
    "scheduled_membrane_insertion@2": "opens and retires nodes and patches",
    "restricted_cleft_lumen@1": "fills a lumen node with bath fluid as it grows",
    "restricted_cleft_lumen@2": "fills a lumen node with bath fluid as it grows",
    "scheduled_bath_composition@1": "sets held baths' compositions at its events",
    "scheduled_membrane_trafficking@1": "moves membrane, and the charges on it, between nodes",
    "scheduled_compartment_wash@1": "collects and refills every free species at its nodes",
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


def region_rows(spec, times, states, species, region, *, samples=None):
    """The region export (module docstring) at the sampled times (every given time by default):
    {times, inside_fmol, outside_fmol, whole_cell_fmol, node_fmol: {node: [...]},
    produced_fmol: {node: [...]}, loss_fmol: {node: [...]}, transfer_fmol: {route: [...]}, region,
    cell_nodes}."""
    check_movers(spec, species, EXPORT_READS)
    wmap = world_map(spec, species)
    _, layout = get_model(spec.model).initial_values(spec)
    owners = {wmap["owner"].get(n) for n in region if n not in wmap["cells"]}
    owners |= {n for n in region if n in wmap["cells"]}
    if len(owners) != 1 or None in owners:
        raise ValueError(f"the region {region} is not the nodes of one cell")
    (cell,) = owners
    cell_nodes = [cell] + [n for n, o in wmap["owner"].items() if o == cell]
    index = {n: i for i, n in enumerate(wmap["nodes"])}
    picked = set(samples) if samples is not None else None
    out = dict(times=[], inside_fmol=[], outside_fmol=[], whole_cell_fmol=[],
               node_fmol={n: [] for n in cell_nodes}, produced_fmol={n: [] for n in cell_nodes},
               loss_fmol={n: [] for n in cell_nodes},
               transfer_fmol={r["id"]: [] for r in wmap["routes"]},
               region=list(region), cell_nodes=cell_nodes)  # fmt: skip
    for t, state in zip(times, states, strict=True):
        if picked is not None and t not in picked:
            continue
        amount, made, lost, moved = node_records(spec, layout, state, wmap)
        inside = sum(amount[index[n]] for n in region)
        whole = sum(amount[index[n]] for n in cell_nodes)
        out["times"].append(t)
        out["inside_fmol"].append(float(inside))
        out["outside_fmol"].append(float(whole - inside))
        out["whole_cell_fmol"].append(float(whole))
        for n in cell_nodes:
            out["node_fmol"][n].append(float(amount[index[n]]))
            out["produced_fmol"][n].append(float(made[index[n]]))
            out["loss_fmol"][n].append(float(lost[index[n]]))
        for r, value in zip(wmap["routes"], moved, strict=True):
            out["transfer_fmol"][r["id"]].append(float(value))
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


def _check_rows(result, totals, scales):
    """The returned rows' invariant (module docstring): at every row and node, each cohort
    non-negative and the cohorts summing to the node's amount, within the closure's tolerance, on
    the dictionary as returned (so a column a name replaced, or a negative split, is seen)."""
    eps = np.finfo(float).eps
    amount = result["amount"]
    for node, total in totals.items():
        for k, t in enumerate(result["times"]):
            tol = CLOSURE_ULPS * eps * scales[node][k]
            values = [amount[c][node][k] for c in amount]
            if min(values) < -tol:
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
    closure_bound, resolution_largest, resolution_bound}; refused, with its reason, at setup (the
    movers), at a step the records do not close, at a step it cannot resolve (r above RESOLUTION
    at a node that gains material) and where a returned row breaks the invariant."""
    check_movers(spec, species, TRACER_READS)
    for t, _ in produced:
        if t > times[0] and not any(abs(t - u) <= 1e-12 * max(1.0, abs(t)) for u in times):
            raise ValueError(f"the label switch at {t} s is not on a step's boundary")
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
    totals, scales = [start.copy()], [np.abs(start)]
    closure, bound, resolution = 0.0, 0.0, 0.0
    previous = node_records(spec, layout, states[0], wmap)
    eps = np.finfo(float).eps
    for t0, t1, state in zip(times[:-1], times[1:], states[1:], strict=True):
        now = node_records(spec, layout, state, wmap)
        n0, n1 = previous[0], now[0]
        made, lost, m = now[1] - previous[1], now[2] - previous[2], now[3] - previous[3]
        inflow, outflow = np.zeros(len(nodes)), lost.copy()
        for r, amount in zip(routes, m, strict=True):
            inflow[index[r["destination"]]] += amount
            outflow[index[r["source"]]] += amount
        residual = (n1 - n0) - (made + inflow - outflow)
        scale = np.abs(n0) + np.abs(n1) + np.abs(made) + np.abs(lost) + inflow + outflow
        closure = max(closure, float(np.max(np.abs(residual) / np.maximum(scale, 1e-300))))
        tol = CLOSURE_ULPS * eps * scale
        if np.any(np.abs(residual) > tol):
            raise ValueError(f"the records do not close the species' amounts at t = {t1}")
        bound = CLOSURE_ULPS * eps
        # The resolution (module docstring): r = O/S, tested where the node gains material.
        S = n0 + n1
        filled = S > 0
        inv = np.where(filled, 1.0 / np.where(filled, S, 1.0), 0.0)
        ratio = np.where(filled, outflow * inv, np.where(outflow > tol, np.inf, 0.0))
        gaining = made + inflow > tol
        if np.any(gaining):
            resolution = max(resolution, float(np.max(ratio[gaining])))
        if np.any(gaining & (ratio > RESOLUTION)):
            k = int(np.argmax(np.where(gaining, ratio, -1.0)))
            raise ValueError(
                f"the step to t = {t1} s takes {outflow[k]:.6g} fmol out of {nodes[k]}, which "
                f"gains {made[k] + inflow[k]:.6g} fmol in it: r = O/S = {ratio[k]:.3g} of its "
                f"start and end amounts, above the tracer's resolution {RESOLUTION} (a cohort "
                "present at the step's start would survive as (1 - r)/(1 + r): 0 at r = 1, where "
                "the truth is e^-2 = 0.135, and negative above it); take smaller steps"
            )
        label = next((c for t, c in reversed(produced) if t <= t0), "produced")
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
        x, previous = x1, now
        out["times"].append(t1)
        out["amount"].append(x.copy())
        out["loss"].append(loss.copy())
        out["transfer"].append(moved.copy())
        totals.append(n1.copy())
        scales.append(scale)

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
    )
    return result
