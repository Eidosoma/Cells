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
- and, beside them, the amount at each of the cell's nodes.

**The tracer** (trace) carries cohorts within the species' row, beside it, from the movers'
per-step records. It reads every accepted step, and changes no flux, so it applies where no law
reads the cohort.
- **Each step's records:** at each node, production and loss (turnover's and the reactions'); on
  each exchange route, the amount moved from its source to its destination.
- **A closure check:** each node's change must equal those records, within rounding, or the trace
  is refused. A mover it does not read (a face, a junction, permeation) would break it.
- **Production** joins the cohort that the label schedule names at the step's start.
- **A node's outflow** (its loss and its routes out) leaves each cohort in proportion to that
  cohort's mean amount over the step, (start + end)/2, the trapezoid. A route's outflow carries
  its source's split into its destination.
- **The step's cohort amounts** at every node solve one linear system per step (nodes by nodes,
  shared by every cohort). Every cohort's amounts sum to the node's amount.

**Its limit.** At a node with no inflow, every cohort leaves at the node's one per-molecule rate
under first-order laws, so the composition is constant over the step and the split is exact. Where
material flows in during a step, the composition changes within it. The start-of-step split of the
design note is first order in dt; the trapezoid used here is second order. At the example's 1 ms
step it is about (k dt)^2 k t / 12 of a cohort, k the node's per-molecule outflow rate: measured at
9.5e-7 against the closed form (tests/unit/test_region_readouts.py).

Under age- or region-selective laws a cohort's own rate differs, so the cohorts are dynamics, not
bookkeeping: that is the design note's option D, not this tracer.
"""

import numpy as np

from cells.registry.models import get_model

EXCHANGE = "scheduled_species_exchange@1"
COMPARTMENTS = "cell_owned_compartments@1"
CLOSURE_ULPS = 64


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
    loss_fmol: {node: [...]}, transfer_fmol: {route: [...]}, region, cell_nodes}."""
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
               node_fmol={n: [] for n in cell_nodes}, loss_fmol={n: [] for n in cell_nodes},
               transfer_fmol={r["id"]: [] for r in wmap["routes"]},
               region=list(region), cell_nodes=cell_nodes)  # fmt: skip
    for t, state in zip(times, states, strict=True):
        if picked is not None and t not in picked:
            continue
        amount, _, lost, moved = node_records(spec, layout, state, wmap)
        inside = sum(amount[index[n]] for n in region)
        whole = sum(amount[index[n]] for n in cell_nodes)
        out["times"].append(t)
        out["inside_fmol"].append(float(inside))
        out["outside_fmol"].append(float(whole - inside))
        out["whole_cell_fmol"].append(float(whole))
        for n in cell_nodes:
            out["node_fmol"][n].append(float(amount[index[n]]))
            out["loss_fmol"][n].append(float(lost[index[n]]))
        for r, value in zip(wmap["routes"], moved, strict=True):
            out["transfer_fmol"][r["id"]].append(float(value))
    return out


def trace(spec, times, states, species, cohorts, *, produced=()):
    """The passive tracer (module docstring) over consecutive accepted steps.

    cohorts: {name: {node: fraction of the node's starting amount}}; at each node the fractions sum
    to 1 over the cohorts, and a node no cohort names starts in "unlabelled". produced: [(time,
    cohort), ...], the cohort new material joins from each time on ("produced" before the first).
    Returns {times, amount: {cohort: {node: [...]}}, loss: {cohort: {node: [...]}}, transfer:
    {cohort: {route: [...]}}, closure_largest, closure_bound}."""
    wmap = world_map(spec, species)
    _, layout = get_model(spec.model).initial_values(spec)
    nodes, routes = wmap["nodes"], wmap["routes"]
    index = {n: i for i, n in enumerate(nodes)}
    names = list(cohorts)
    start = node_records(spec, layout, states[0], wmap)[0]
    share = np.zeros((len(nodes), len(names) + 1))
    for c, name in enumerate(names):
        for node, fraction in cohorts[name].items():
            share[index[node], c] = fraction
    share[:, -1] = 1.0 - share[:, :-1].sum(axis=1)
    if np.any(share[:, -1] < -1e-12):
        raise ValueError("a node's cohort fractions sum above 1")
    names = names + ["unlabelled"]
    for label in [c for _, c in produced] + ["produced"]:
        if label not in names:
            names.append(label)
            share = np.concatenate([share, np.zeros((len(nodes), 1))], axis=1)
    x = start[:, None] * share  # [node, cohort]
    loss = np.zeros_like(x)
    moved = np.zeros((len(routes), len(names)))
    out = dict(times=[times[0]], amount=[x.copy()], loss=[loss.copy()], transfer=[moved.copy()])
    closure, bound = 0.0, 0.0
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
        if np.any(np.abs(residual) > CLOSURE_ULPS * eps * scale):
            raise ValueError(f"the records do not close the species' amounts at t = {t1}")
        bound = CLOSURE_ULPS * eps
        label = next((c for t, c in reversed(produced) if t <= t0), "produced")
        S = n0 + n1
        A = np.diag(1.0 + outflow / S)
        B = x * (1.0 - outflow / S)[:, None]
        B[:, names.index(label)] += made
        for r, amount in zip(routes, m, strict=True):
            i, s = index[r["destination"]], index[r["source"]]
            A[i, s] -= amount / S[s]
            B[i] += amount / S[s] * x[s]
        x1 = np.linalg.solve(A, B)
        mean = (x + x1) / S[:, None]  # Each cohort's share of the step's outflow.
        loss += lost[:, None] * mean
        for k, (r, amount) in enumerate(zip(routes, m, strict=True)):
            moved[k] += amount * mean[index[r["source"]]]
        x, previous = x1, now
        out["times"].append(t1)
        out["amount"].append(x.copy())
        out["loss"].append(loss.copy())
        out["transfer"].append(moved.copy())

    def by(array_list, labels):
        stacked = np.array(array_list)  # [time, label, cohort]
        return {name: {lab: stacked[:, j, c].tolist() for j, lab in enumerate(labels)}
                for c, name in enumerate(names)}  # fmt: skip

    return dict(
        times=out["times"],
        amount=by(out["amount"], nodes),
        loss=by(out["loss"], nodes),
        transfer=by(out["transfer"], [r["id"] for r in routes]),
        closure_largest=closure,
        closure_bound=bound,
    )
