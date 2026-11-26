"""The engine's development runs of gene regulation's option A (G4): worlds of worlds.py at
potential sets and a step, each with the sheet's §6 readouts under G2's interface names, except
each move's dG and A1's u(t), which are not exported (README.md). Development, not judged.

Per run (world, potential set, dt) it writes `<set>/<world>.json` into a fresh directory:
- the output times and, at each, the readouts: every row's amount n_*, each pool's free machines
  F_*, every stage's complexes C_*_j, E_* and the residues in transit W_* = r sum_j (j - 1) C_j, the
  cumulative extents int_J_I_*, int_S_*, int_Q_*, int_D_<polymer> and int_J_C (signed), and the
  five heat classes H_tx, H_tl, H_deg_R, H_deg_P and H_rc, each the sum of its routes' heats;
- J_bar_* over the final window in A1-M's worlds;
- G_minus_G0, G(t) - G(0) from the state alone (§3.4): every row's n [mu° + RT (ln a - 1)] and each
  route's mu°_res W, in 60-digit decimal arithmetic, never from extents or bookings;
- the engine's own: H_total, the booked heat, and each route's heat, H_route_*;
- the checks the bookings cannot certify themselves: G's identity, G(t) - G(0) + H_total, and the
  routes' sum against H_total, each with the largest over the outputs.
`run_record.json` holds the revision, whether the checkout was dirty (its diff in checkout.patch),
the potential sets, the step and every run's wall time and end-state own ledgers.

**Keyed by ID, never by position** (D264, findings 3 and 4).
- **The exported cell** is found by its ID: the one cell holding every route of the operator (its
  pools, degradations and transfers), or the cell named. A world whose routes span several cells
  must name it, and only that cell's routes are exported. The record names the cell. Reordering
  the declared cells changes nothing exported.
- **Each loss counter is summed once** per product, cell and output: int_D_<polymer> is the sum of
  the native counters of every degradation route of that polymer at the cell. Each route's own
  counter is int_D_route_<route>. A product of the cell's chains with no loss route there, named
  by no other operator, is lossless by its definition: its int_D is a zero series (D265).
- **Every exported series has exactly one value per output,** or the export is refused.

The heat classes are assigned by route: a chain templated by a gene's copies is transcription
(tx), one templated by a species row is translation (tl); a degradation is deg_R or deg_P as its
polymer is made by transcription or translation; a transfer is recharging (rc).

Run: PYTHONPATH=src:. JAX_ENABLE_X64=1 python -m validation.gene_regulation.engine_run
[--worlds NAME ... | all | release | release2] [--sets LABEL ...] [--dt S] [--end S] --out DIR.
"release" is R1's runs (worlds.release_names(), FR-38), at dt worlds.R1_DT; "release2" is R2's,
its development check's and A1, at A1's 0.5 s; "switch" is R1S's (worlds.r1s) and its unlabelled
twin R1SU's, at R1's dt. All export the release's readouts: the hold H_<release>, its releases
int_Q_<release>_<fate>, each fate's class total n_<release>_<fate>
and its heat class H_rel_<release>_<fate>, and the hold's term in G_minus_G0 (the sheet's §9).

A world that declares FR-42's labels (cells.operator.neutral_arrival_labels@1, D289) also exports each labelled
row's amount carrying each of its labels at the exported cell, label_<row>_<label>: the row's
amount times the label's share, keyed by the species' and label's IDs; and each release's hold by
the labels of its durable fate row, label_H_<release>_<label>, the hold times its share in the
label owner's pool (D296). In R1L label_R_cohort and label_R_s_cohort are §9.8's route 1 on shares
(errata C and F), the window's releases still present, marked on transcription's own label
schedule, with no blank. A label never changes a physical readout. The labels are the owner's
derived list, so producer labels (amendment G, §9.20) are exported with the declared ones.

**The export** (amendment T, the sheet's §9.17; erratum H, §9.21). Where the exported cell's own
exports carry a row out, the export also reads each node they feed, keyed by the node's ID:
- each row the operator writes there (the exported rows, and its outside degradations' polymers
  and monomers), n_<row>_<node>, and with FR-42's labels label_<row>_<label>_<node>, the row times
  its share at the node;
- each export's one-way parts, int_E_<export>_forward (cell to node, with the cell's shares) and
  int_E_<export>_backward (node to cell); each outside degradation's int_D_route_<route>, and
  their sum per polymer and node, int_D_<polymer>_<node>;
- the heat classes H_exp, the exports' heat (each export's whole heat, which the operator books
  at its cell), and H_odeg, the outside degradations' (booked at their node), each route's as
  H_route_<route>.

Then G_minus_G0 extends over the rows written at the nodes (§9.17.2), and H_total, the routes' sum
and the energy magnitude include the nodes' heat and bookings, so G's identity closes over the
cell and its nodes. An exported row is no lossless product (D265): it leaves its cell by export.
The checks name the nodes (exported_nodes). A node that another cell's export also feeds is
refused, since that export's heat is booked at its own cell, so G over this cell and its nodes
would not close against their heat: a shared node's cells are not exported (version 1). Without
an export from the exported cell nothing here is read, and the record is unchanged.

**Beside a second writer or water** (FR-43's parts 2A and 2B; FR-38's second comparison, families C
and D, validation/gene_regulation/fr38_v2/spec/READOUTS.md):
- **cells.operator.local_species_reactions@1** (D152) on the exported cell adds the rows of its own that the gene
  unit does not list (n_<row>, n_Mx in family C), its heat there, H_store
  (reaction_dissipated_energy_pJ), its work there (reaction_work_pJ: zero on a passive route such
  as family C's, not on a driven one), and its bookings' magnitude. G_minus_G0 adds those rows at
  the network's potentials, converted to the gene unit's c0.
- **cells.operator.ideal_osmosis_linear_compliance_water@1** makes the cell's volume current, V (pL). It adds
  water's heat H_water (water_dissipated_energy_pJ, summed) and the held baths' water work W_bath
  (bath_water_work_pJ, summed). G_minus_G0 then reads every species row at the current V, K and Y
  included at mu° 0 (their amounts move by nothing, their terms by dilution; n_K and n_Y are
  exported), and the elastic energy U(V) is 0 at no modulus.
- G's identity is formed over them: G(t) - G(0) + H_total + H_store - W_network + H_water - W_bath.
  With water it closes at second order (water's bookings, FR-43's C2.7), not at rounding.

Without either operator nothing here is read, and the record is unchanged.
"""

import argparse
import hashlib
import json
import math
import platform
import re
import subprocess
import time
from datetime import UTC, datetime
from decimal import Decimal, localcontext
from pathlib import Path

import numpy as np

from cells.definitions.specs import parse_spec
from cells.execution.windows import WindowPolicy, iter_windows
from cells.operators import OPERATORS, species_labels
from cells.operators import templated_polymerisation as polymerisation
from cells.registry.models import get_model
from validation.gene_regulation import sheet_check as sheet
from validation.gene_regulation import worlds

ROOT = Path(__file__).resolve().parents[2]
SHEET_TAG = "gr1-sheet-2026-11-20b"
RELEASE_SHEET_TAG = "gr1-sheet-fr38-erratum-c-2026-11-22"  # The sheet's §9, as amended (FR-38).
LABELS = "cells.operator.neutral_arrival_labels@1"  # FR-42's label owner (D289).
REACTIONS = "cells.operator.local_species_reactions@1"  # D152's network: family C's store (FR-43 part 2A).
WATER = "cells.operator.ideal_osmosis_linear_compliance_water@1"  # Family D's swelling cell (FR-43 part 2B).
POLICY = WindowPolicy(window_steps=10000, recording="observations")
DIGITS = 60


def git(*args):
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout


SOURCE_SCOPE = ("src", "validation")  # What a run imports or reads from the checkout.


def provenance(out=None):
    """(The source's identity, the dirty diff or None), for a run's record.
    - From a frozen snapshot (validation/source_snapshot.py): its record.
    - From the checkout (the review's finding 8 and its class, D259: a receipt named a revision
      without the script that ran):
      - validation/executed_sources.checkout: the status with every untracked file, and the dirty
        diff, `git diff --binary HEAD` joined to the full content of every executed source Git
        does not track, wherever it lives (the root, scripts/, tests/ fixtures). The record lists
        those sources as untracked_executed;
      - beside it, every untracked, nonignored file under SOURCE_SCOPE, executed or not yet, is
        frozen into OUT/untracked-sources by validation/source_snapshot.freeze, and the record
        names the folder, the files and the manifest's digest.

      Without an OUT, a checkout with either kind is refused. A source loaded later in the run is
      added at its end (late_sources)."""
    snapshot = ROOT / "SNAPSHOT.json"
    if snapshot.exists():
        d = json.loads(snapshot.read_text())
        clean = d["patch_sha256"] == hashlib.sha256(b"").hexdigest()
        return dict(
            engine_revision=d["git_revision"],
            checkout_dirty=not clean,
            snapshot=str(ROOT),
            snapshot_patch_sha256=d["patch_sha256"],
        ), None
    from validation import executed_sources

    found = executed_sources.checkout(ROOT)
    listed = git("ls-files", "--others", "--exclude-standard", "-z", "--", *SOURCE_SCOPE)
    untracked = sorted(name for name in listed.split("\0") if name)
    if out is None:
        executed_sources.refuse_untracked(ROOT, "this run, with no output folder for its record,")
        if untracked:
            raise RuntimeError(
                f"untracked source {untracked[:3]} would not be recorded: commit it, run from a "
                "frozen snapshot, or give the run an output folder to freeze it into"
            )
    dirty = bool(found["status"].strip())
    record = dict(
        engine_revision=git("rev-parse", "HEAD").strip(),
        checkout_dirty=dirty,
        checkout_status=found["status"].splitlines(),
        dirty_diff="checkout.patch" if found["diff"] else None,
        untracked_executed=found["untracked_executed"],
    )
    if untracked:
        from validation import source_snapshot

        folder = Path(out) / "untracked-sources"
        source_snapshot.freeze(ROOT, folder, {name: name for name in untracked})
        manifest = (folder / "SNAPSHOT.json").read_bytes()
        record["untracked_sources"] = dict(
            folder="untracked-sources",
            files=untracked,
            manifest_sha256=hashlib.sha256(manifest).hexdigest(),
        )
    return record, found["diff"] or None


def late_sources(out, source):
    """source, with any executed source Git does not track that the run loaded after provenance()
    took its record: each one's full content appended to OUT/checkout.patch, its path to
    untracked_executed (validation/executed_sources.untracked)."""
    if "snapshot" in source:
        return source
    from validation import executed_sources

    known = set(source.get("untracked_executed", ()))
    new = [p for p in executed_sources.untracked(ROOT) if p not in known]
    if not new:
        return source
    with (Path(out) / "checkout.patch").open("a") as stream:
        stream.write(executed_sources.untracked_diff(ROOT, new))
    return dict(
        source,
        checkout_dirty=True,
        dirty_diff="checkout.patch",
        untracked_executed=sorted(known | set(new)),
        untracked_executed_after_start=sorted(
            {*source.get("untracked_executed_after_start", ()), *new}
        ),  # fmt: skip
    )


def slug(text):
    return re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-")


def collect(spec):
    """The state at each observed step of a windowed run of `spec`: {step: state}."""
    dt = spec.execution.dt
    wanted = {int(round(float(t) / dt)) for t in spec.experiment.observation_times}
    states = {}
    for window in iter_windows(spec, POLICY):
        for i, _ in enumerate(np.asarray(window.times)):
            k = window.start_step + i
            if k in wanted:
                states[k] = type(window.history)(*(np.asarray(v)[i] for v in window.history))
    return states


def classes(block):
    """{class: [(kind, route index), ...]}: the sheet's five heat classes (module docstring)."""
    gene_made = {c.product for c in block.chains if c.template_copies is not None}
    # A gene's release (§9.12, reading 5): a fate row that is not its product has its own class.
    fates = {
        row
        for c, r in polymerisation.releases_of(block)
        if c.template_copies is not None
        for row in r.rows()
    } - gene_made
    out = {"H_tx": [], "H_tl": [], "H_deg_R": [], "H_deg_P": [], "H_rc": []}
    for i, c in enumerate(block.chains):
        out["H_tx" if c.template_copies is not None else "H_tl"].append(("chain", i))
    for i, d in enumerate(block.degradations):
        if d.polymer in fates:
            out.setdefault(f"H_deg_{d.polymer}", []).append(("degradation", i))
        else:
            out["H_deg_R" if d.polymer in gene_made else "H_deg_P"].append(("degradation", i))
    for i, _ in enumerate(block.transfers):
        out["H_rc"].append(("transfer", i))
    out["H_exp"] = [("export", i) for i, _ in enumerate(block.exports)]  # Amendment T (§9.17).
    out["H_odeg"] = [("outside", i) for i, _ in enumerate(block.outside_degradations)]
    return {k: v for k, v in out.items() if v}


def free_energy(amounts, transit, mu, residue_mu, volume, c0):
    """G of a state (§3.4) in pJ, as a Decimal: sum over rows n RT (mu°/RT + ln(n/(V c0)) - 1)
    plus sum over chains RT mu°_res/RT W. amounts and mu are {row: value}; transit and
    residue_mu {chain: value}."""
    with localcontext() as ctx:
        ctx.prec = DIGITS
        rt = sheet.R_GAS * sheet.T_K / 1000  # kJ/mol, so fmol times kJ/mol is pJ.
        v, c = Decimal(repr(volume)), Decimal(repr(c0))
        total = Decimal(0)
        for row, n in amounts.items():
            n = Decimal(repr(n))
            total += n * rt * (Decimal(repr(mu[row])) + (n / (v * c)).ln() - 1)
        for chain, w in transit.items():
            total += rt * Decimal(repr(residue_mu[chain])) * Decimal(repr(w))
        return total


def exported_cell(spec, block, cell=None):
    """The cell the export reads, by its ID (module docstring): the one cell holding every route,
    or the named one. Refused where the routes span several cells and none is named."""
    cells = [c.id for c in spec.model.cells]
    hosts = sorted({p.cell for p in block.pools} | {d.cell for d in block.degradations}
                   | {t.cell for t in block.transfers})  # fmt: skip
    if cell is None:
        if len(hosts) != 1:
            raise ValueError(f"the routes are in cells {hosts}: name the cell to export")
        return hosts[0]
    if cell not in cells:
        raise ValueError(f"no cell {cell!r}: the cells are {cells}")
    return cell


def export_nodes(block, cell):
    """The nodes the exported cell's exports feed (amendment T, §9.17), in their order; [] without
    one. Refused where another cell's export feeds one too (module docstring)."""
    nodes = list(dict.fromkeys(e.node for e in block.exports if e.cell == cell))
    shared = sorted(
        (e.node, e.cell, e.id) for e in block.exports if e.node in nodes and e.cell != cell
    )
    if shared:
        node, other, export = shared[0]
        raise ValueError(
            f"node {node} also takes {other}'s export {export}, whose heat is booked at {other}: "
            f"G over {cell} and its nodes would not close; a shared node's cells are not exported "
            "(version 1)"
        )
    return nodes


def node_rows(block, node):
    """The listed rows the operator writes at an exported node (§9.17.2), in listed order: its
    exports' rows there, and its outside degradations' polymers and monomers there."""
    written = {e.row for e in block.exports if e.node == node}
    for d in block.outside_degradations:
        if d.node == node:
            written |= {d.polymer, *(row for row, _ in d.monomers)}
    return [s.id for s in block.species if s.id in written]


def labelled(spec):
    """((species, its labels), ...) of FR-42's label owner, in its order, each species' labels the
    owner's derived list (its declared labels, then its producers', amendment G); () where the
    world declares none."""
    for d in spec.model.operators:
        if d.law == LABELS:
            return tuple((s.id, s.labels) for s in species_labels.derived(spec, d)[0].species)
    return ()


def readouts(spec, states, cell=None):
    """(times, {readout: [value per output]}, checks) of one run, at the exported cell
    (exported_cell), which checks names as exported_cell."""
    model = get_model(spec.model)
    _, p = model.initial_values(spec)
    species = list(spec.model.species_ids)
    reference = np.asarray(p.amount_reference)
    dt = spec.execution.dt
    (block,) = [d for d in spec.model.operators if d.law == worlds.POLYMERISATION]
    cell = exported_cell(spec, block, cell)
    at = [c.id for c in spec.model.cells].index(cell)
    nodes = export_nodes(block, cell)  # Amendment T (§9.17): [] without an export from the cell.
    axis = polymerisation.exported_nodes(block)  # The operator's own node axis (its fields').
    rows = [s.id for s in block.species] + (["X"] if "X" in species else [])
    mu = dict(zip([s.id for s in block.species], block.mu_RT, strict=True))
    volume = float(next(c.volume_pL for c in spec.model.cells if c.id == cell))
    network, watered, g_mu = _second_writers(spec, block, mu)  # FR-43, FR-38's C and D.
    rows += [row for row in g_mu if row not in rows]
    residue_mu = {
        c.id: (mu[c.product] - float(np.log(block.c0_mM / sheet_c0()))) / c.residues
        for c in block.chains
    }
    here = dict(
        chain=[i for i, c in enumerate(block.chains) if c.cell == cell],
        pool=[i for i, q in enumerate(block.pools) if q.cell == cell],
        degradation=[i for i, d in enumerate(block.degradations) if d.cell == cell],
        transfer=[i for i, x in enumerate(block.transfers) if x.cell == cell],
        export=[i for i, e in enumerate(block.exports) if e.cell == cell],
        outside=[i for i, d in enumerate(block.outside_degradations) if d.node in nodes],
    )
    membership = {
        name: [(kind, i) for kind, i in members if i in here[kind]]
        for name, members in classes(block).items()
    }
    membership = {name: members for name, members in membership.items() if members}
    # D265, finding 7: a product of the cell's chains with no loss route there, and named by no
    # other operator, is established as lossless, and exported with a zero loss series. A
    # release's fate rows (FR-38, the sheet's §9; every class's) are filled by its chain as a
    # product is, so the rule covers them too (the Lean lane's finding, 22 November 2026). FR-42's
    # label owner names species but moves no material, so it is no other mover.
    lost = {block.degradations[i].polymer for i in here["degradation"]}
    others = {getattr(x, "id", x) for op in spec.model.operators
              if op.law not in (worlds.POLYMERISATION, LABELS)
              for x in getattr(op, "species", ())}  # fmt: skip
    releases = [
        (i, c, r) for i, (c, r) in enumerate(polymerisation.releases_of(block)) if c.cell == cell
    ]
    made = {block.chains[i].product for i in here["chain"]}
    made |= {row for _, _, r in releases for row in r.rows()}
    exported = {block.exports[i].row for i in here["export"]}  # It leaves by export (§9.17).
    zero_loss = sorted(made - lost - others - exported)
    times = [float(t) for t in spec.experiment.observation_times]
    out = {}

    def put(name, value):
        out.setdefault(name, []).append(float(value))

    shared = labelled(spec)
    g0 = None
    for t in times:
        s = states[int(round(t / dt))]
        increment = np.asarray(s.amount_increment)
        amounts = {
            row: float(reference[species.index(row), at] + increment[species.index(row), at])
            for row in rows
        }
        for row in rows:
            put(f"n_{row}", amounts[row])
        if shared:  # FR-42 (D289): each labelled row's amount by label, the row times its share.
            share = np.asarray(s.label_share)  # [labelled species, label, cell]
            for j, (row, names) in enumerate(shared):
                n = float(reference[species.index(row), at] + increment[species.index(row), at])
                for k, name in enumerate(names):
                    put(f"label_{row}_{name}", n * float(share[j, k, at]))
            # D296: each hold at the exported cell by its durable fate row's labels, the hold
            # times its share (the operator the only pool reporter; its pools, its releases).
            pooled = np.asarray(s.label_pool_share)[0]  # [label, pool]
            hold = np.asarray(s.poly_hold_fmol)
            for i, _, r in releases:
                names = dict(shared).get(r.fates[0][0], ())
                for k, name in enumerate(names):
                    put(f"label_H_{r.id}_{name}", float(hold[i, 0]) * float(pooled[k, i]))
        free = np.asarray(s.poly_free_machines_fmol)
        for i in here["pool"]:
            put(f"F_{block.pools[i].id}", free[i])
        complexes = np.asarray(s.poly_complexes_fmol)
        transit = {}
        held = _held(s, releases)
        for i in here["chain"]:
            c = block.chains[i]
            r = c.residues // c.stages
            for j in range(c.stages):
                put(f"C_{c.id}_{j + 1}", complexes[i, j])
            put(f"E_{c.id}", float(np.sum(complexes[i, : c.stages])) + held.get(c.id, 0.0))
            transit[c.id] = float(r * sum(j * complexes[i, j] for j in range(c.stages)))
            put(f"W_{c.id}", transit[c.id])
            put(f"int_J_I_{c.id}", np.asarray(s.poly_initiated_fmol)[i])
            put(f"int_S_{c.id}", np.asarray(s.poly_stage_exits_fmol)[i])
            put(f"int_Q_{c.id}", np.asarray(s.poly_released_fmol)[i])
        degraded = np.asarray(s.poly_degraded_fmol)
        for polymer in zero_loss:
            put(f"int_D_{polymer}", 0.0)
        for polymer in sorted({block.degradations[i].polymer for i in here["degradation"]}):
            mine = [i for i in here["degradation"] if block.degradations[i].polymer == polymer]
            put(f"int_D_{polymer}", math.fsum(float(degraded[i]) for i in mine))
        for i in here["degradation"]:
            put(f"int_D_route_{block.degradations[i].id}", degraded[i])
        for i in here["transfer"]:
            x = block.transfers[i]
            name = "int_J_C" if len(here["transfer"]) == 1 else f"int_J_C_{x.id}"
            put(name, np.asarray(s.poly_transferred_fmol)[i])
        if nodes:  # Amendment T (§9.17): the nodes' rows, labels and counters, and their G.
            g_nodes = _node_readouts(put, s, spec, block, nodes, here, p, shared, mu, residue_mu)
        current = volume
        if watered:  # Family D: the cell's current volume, water's heat and the bath's work.
            current = float(np.asarray(p.volume)[at] + np.asarray(s.volume_increment_pL)[at])
            put("V", current)
            put("H_water", math.fsum(float(x) for x in np.asarray(s.water_dissipated_energy_pJ)))
            put("W_bath", math.fsum(float(x) for x in np.asarray(s.bath_water_work_pJ)))
        if network is not None:  # Family C: the store's heat and the network's work at the cell.
            put("H_store", np.asarray(s.reaction_dissipated_energy_pJ)[at])
            put("W_network", np.asarray(s.reaction_work_pJ)[at])
        heats = {
            "chain": np.asarray(s.poly_chain_heat_pJ),
            "degradation": np.asarray(s.poly_degradation_heat_pJ),
            "transfer": np.asarray(s.poly_transfer_heat_pJ),
            "export": np.asarray(s.poly_export_heat_pJ),
            "outside": np.asarray(s.poly_outside_degradation_heat_pJ),
        }
        routes = {
            "chain": block.chains,
            "degradation": block.degradations,
            "transfer": block.transfers,
            "export": block.exports,
            "outside": block.outside_degradations,
        }
        for kind, items in routes.items():
            for i in here[kind]:
                put(f"H_route_{items[i].id}", heats[kind][i])
        for name, members in membership.items():
            put(name, sum(float(heats[kind][i]) for kind, i in members))
        booked = float(np.asarray(s.poly_dissipated_energy_pJ)[at])
        if nodes:  # Amendment T: the heat booked at each node, its outside degradations'.
            node_heat = np.asarray(s.poly_outside_dissipated_energy_pJ)
            booked = math.fsum([booked, *(float(node_heat[axis.index(o)]) for o in nodes)])
        put("H_total", booked)
        release_heat = _release_readouts(put, s, releases, amounts)
        put(
            "H_routes_sum",
            sum(float(heats[kind][i]) for kind in heats for i in here[kind]) + release_heat,
        )
        residues = dict(transit)  # G's residue term: in transit, and held complete (§9.5).
        hold = np.asarray(s.poly_hold_fmol)
        for i, c, _ in releases:
            residues[c.id] = residues[c.id] + c.residues * float(np.sum(hold[i]))
        g = free_energy(
            {row: amounts[row] for row in g_mu}, residues, g_mu, residue_mu, current, block.c0_mM
        )
        if nodes:  # §9.17.2: G extends over the nodes the operator writes.
            with localcontext() as ctx:
                ctx.prec = DIGITS
                g = g + g_nodes
        g0 = g if g0 is None else g0
        put("G_minus_G0", g - g0)
    ribosome = any(c.template_species for c in block.chains)
    window = float(sheet.A1M["window_rib" if ribosome else "window_pol"])
    full = float(sheet.A1M["t_end_rib" if ribosome else "t_end_pol"])
    if "X" not in rows and times[-1] == full:  # A1-M's release rate over its final window (§5.2).
        k_end, k_start = len(times) - 1, times.index(times[-1] - window)
        for i in here["chain"]:
            q = out[f"int_Q_{block.chains[i].id}"]
            out[f"J_bar_{block.chains[i].id}"] = [(q[k_end] - q[k_start]) / window]
    uneven = sorted(k for k, v in out.items() if not k.startswith("J_bar") and len(v) != len(times))
    if uneven:
        raise ValueError(f"the export holds {uneven[:3]} with other than one value per output")
    scale = max(abs(v) for v in out["H_total"]) or 1.0
    zeros = [0.0] * len(times)
    beside = zeros  # The second writer's heat and water's heat less the bath's work.
    for name, sign in (("H_store", 1.0), ("W_network", -1.0), ("H_water", 1.0), ("W_bath", -1.0)):
        beside = [b + sign * v for b, v in zip(beside, out.get(name, zeros), strict=True)]
    identity = [
        g + h + b for g, h, b in zip(out["G_minus_G0"], out["H_total"], beside, strict=True)
    ]
    split = [a - b for a, b in zip(out["H_routes_sum"], out["H_total"], strict=True)]
    last = states[max(states)]
    magnitude = float(np.asarray(last.poly_energy_magnitude_pJ)[at])
    if nodes:  # Amendment T: the bookings at the nodes.
        node_magnitude = np.asarray(last.poly_outside_energy_magnitude_pJ)
        magnitude = math.fsum([magnitude, *(float(node_magnitude[axis.index(o)]) for o in nodes)])
    if network is not None:  # FR-43 2A: the network's bookings at the cell.
        magnitude += float(np.asarray(last.reaction_energy_magnitude_pJ)[at])
    if watered:  # FR-43 2B: water's heat (non-negative) and the bath's work.
        magnitude += max(abs(v) for v in out["H_water"]) + max(abs(v) for v in out["W_bath"])
    checks = dict(
        G_identity_largest_pJ=max(abs(x) for x in identity),
        G_identity_over_sum_H_at_end=max(abs(x) for x in identity) / scale,
        routes_minus_total_largest_pJ=max(abs(x) for x in split),
        routes_minus_total_over_magnitude=max(abs(x) for x in split) / (magnitude or 1.0),
        H_total_at_end_pJ=out["H_total"][-1],
        energy_magnitude_at_end_pJ=magnitude,
        smallest_class_increment={
            name: min(b - a for a, b in zip(out[name], out[name][1:], strict=False))
            for name in [*membership, *(k for k in out if k.startswith("H_rel_"))]
        },
        exported_cell=cell,
        **({"exported_nodes": nodes} if nodes else {}),
    )
    return times, out, checks


def _second_writers(spec, block, mu):
    """(the D152 network or None, whether water changes the volumes, G's potentials {row: mu°/RT
    at the gene unit's c0}) (module docstring): the gene unit's rows, then the network's own rows
    at its potentials converted to that c0 (mu°' = mu° + ln(c0_gene/c0_network)), then, under
    water, every other species row at mu° 0 (LAWS.md §5 of FR-38's second comparison)."""
    network = next((d for d in spec.model.operators if d.law == REACTIONS), None)
    watered = any(d.law == WATER for d in spec.model.operators)
    g_mu = dict(mu)
    if network is not None:
        shift = math.log(block.c0_mM / network.standard_concentration_mM)
        for entry in network.species:
            g_mu.setdefault(entry.identity.id, float(entry.standard_mu_RT) + shift)
    if watered:
        for row in spec.model.species_ids:
            g_mu.setdefault(row, 0.0)
    return network, watered, g_mu


def _node_readouts(put, s, spec, block, nodes, here, p, shared, mu, residue_mu):
    """Amendment T's readouts at one output (module docstring), keyed by the nodes' and routes'
    IDs: each node's written rows (node_rows) and their labels, the exports' one-way parts and
    the outside degradations' counters. Returns the nodes' G over those rows (§3.4, as
    free_energy, with no transit), as a Decimal. The node amounts and their shares are on the
    model's extracellular slots, the bath's among them, so each node is found there by its ID."""
    species = list(spec.model.species_ids)
    slots = [c.id for c in spec.model.extracellular]
    reference = np.asarray(p.extracellular_amount_reference)
    increment = np.asarray(s.extracellular_amount_increment)
    labels = dict(shared)
    position = {row: j for j, (row, _) in enumerate(shared)}
    share = np.asarray(s.label_outside_share) if shared else None  # [labelled, label, slot]
    with localcontext() as ctx:
        ctx.prec = DIGITS
        g = Decimal(0)
        for node in nodes:
            k = slots.index(node)
            amounts = {
                row: float(reference[species.index(row), k] + increment[species.index(row), k])
                for row in node_rows(block, node)
            }
            for row, n in amounts.items():
                put(f"n_{row}_{node}", n)
            for row, n in amounts.items():
                for j, name in enumerate(labels.get(row, ())):
                    put(f"label_{row}_{name}_{node}", n * float(share[position[row], j, k]))
            volume = float(spec.model.extracellular[k].volume_pL)
            g += free_energy(amounts, {}, mu, residue_mu, volume, block.c0_mM)
    forward = np.asarray(s.poly_export_forward_fmol)
    backward = np.asarray(s.poly_export_backward_fmol)
    for i in here["export"]:
        put(f"int_E_{block.exports[i].id}_forward", forward[i])
        put(f"int_E_{block.exports[i].id}_backward", backward[i])
    degraded = np.asarray(s.poly_outside_degraded_fmol)
    outside = [(i, block.outside_degradations[i]) for i in here["outside"]]
    for node in nodes:
        for polymer in sorted({d.polymer for _, d in outside if d.node == node}):
            mine = [i for i, d in outside if d.node == node and d.polymer == polymer]
            put(f"int_D_{polymer}_{node}", math.fsum(float(degraded[i]) for i in mine))
    for i, d in outside:
        put(f"int_D_route_{d.id}", degraded[i])
    return g


def _held(s, releases):
    """{chain: the machines its hold engages}: H where the machine is held (§9.3, §9.12 reading
    6: E = sum C + sum H under held), none under returned."""
    hold = np.asarray(s.poly_hold_fmol)
    return {
        c.id: math.fsum(float(v) for v in hold[i]) for i, c, r in releases if r.machine == "held"
    }


def _release_readouts(put, s, releases, amounts):
    """The release's readouts at one output (the sheet's §9.7), each per release and fate, the
    classes summed (a class's own where K > 1): the hold H_<release>, the releases
    int_Q_<release>_<fate>, each fate's rows n_<release>_<fate> (the class totals, so total RNA
    per fate reads without the labels) and the heat class H_rel_<release>_<fate>. Returns the
    release heats' sum, for H_routes_sum."""
    hold = np.asarray(s.poly_hold_fmol)
    released = np.asarray(s.poly_hold_released_fmol)
    heat = np.asarray(s.poly_release_heat_pJ)
    total = 0.0
    for i, _, r in releases:
        K = len(r.fates)
        put(f"H_{r.id}", math.fsum(float(v) for v in hold[i]))
        for k in range(K if K > 1 else 0):
            put(f"H_{r.id}_{k + 1}", hold[i, k])
        for f, fate in enumerate(polymerisation.FATES):
            put(f"int_Q_{r.id}_{fate}", math.fsum(float(v) for v in released[i, :, f]))
            put(f"n_{r.id}_{fate}", math.fsum(amounts[pair[f]] for pair in r.fates))
            put(f"H_rel_{r.id}_{fate}", math.fsum(float(v) for v in heat[i, :, f]))
            total += math.fsum(float(v) for v in heat[i, :, f])
            for k in range(K if K > 1 else 0):
                put(f"int_Q_{r.id}_{fate}_{k + 1}", released[i, k, f])
    return total


def sheet_c0():
    return worlds.C0_MM


def own_ledgers(spec, state):
    op = OPERATORS[worlds.POLYMERISATION]
    _, p = get_model(spec.model).initial_values(spec)
    own = op.own_ledgers(state, p, xp=np)
    return {k: [float(x) for x in np.atleast_1d(v)] for k, v in own.items()}


def run(name, label, symbols, dt, end, out):
    raw = worlds.world(name, dt=dt, symbols=symbols, end=end if name == "A1" else None)
    spec = parse_spec(raw)
    started = time.perf_counter()
    states = collect(spec)
    wall = time.perf_counter() - started
    times, values, checks = readouts(spec, states)
    path = out / slug(label) / f"{slug(name)}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    record = dict(
        kind="cells.gene_regulation.engine_run@1",
        world=name,
        cell=checks["exported_cell"],
        set=label,
        symbols_RT={k: str(v) for k, v in symbols.items()},
        dt_s=dt,
        end_s=float(spec.experiment.end_time),
        steps=int(round(float(spec.experiment.end_time) / dt)),
        wall_s=wall,
        t=times,
        readouts=values,
        checks=checks,
        own_ledgers_at_end=own_ledgers(spec, states[max(states)]),
        definition=raw,
    )
    path.write_text(json.dumps(record, indent=1, default=float) + "\n")
    return dict(world=name, set=label, wall_s=wall, file=str(path.relative_to(out)), **checks)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--worlds", nargs="+", default=["all"])
    parser.add_argument("--sets", nargs="+", default=["test instance", "Spirin's E_pep"])
    parser.add_argument("--dt", type=float, default=0.5)
    parser.add_argument("--end", type=float, help="A1 only: another horizon")
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    source, patch = provenance(out)
    if patch is not None:
        (out / "checkout.patch").write_text(patch)
    everything = sheet.potential_sets(interior=any(s.startswith("interior") for s in args.sets))
    sets = {label: everything[label] for label in args.sets}
    names = dict(
        all=worlds.names(),
        release=worlds.release_names(),
        release2=[*worlds.r2_names(), *worlds.r2_check_names(), "A1"],
        switch=["R1S returned", "R1S held", "R1SU returned", "R1SU held"],
    ).get(args.worlds[0] if len(args.worlds) == 1 else None, args.worlds)
    record = dict(
        what="The engine's development runs of option A (G4). Development, not judged.",
        sheet_tag=SHEET_TAG,
        **(
            {"release_sheet_tag": RELEASE_SHEET_TAG}
            if any(n.startswith(("R1", "R2")) for n in names)  # R1, R1L, R1S, R2 and R2A.
            else {}
        ),
        **source,
        python=platform.python_version(),
        dt_s=args.dt,
        sets={label: {k: str(v) for k, v in s.items()} for label, s in sets.items()},
        worlds=names,
        created_utc=stamp,
        runs=[],
    )
    for label, symbols in sets.items():
        for name in names:
            record["runs"].append(run(name, label, symbols, args.dt, args.end, out))
            record.update(late_sources(out, record))
            (out / "run_record.json").write_text(json.dumps(record, indent=1) + "\n")
            print(json.dumps(record["runs"][-1]), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
