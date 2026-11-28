"""D327's sequence probe for FR-49's site pairing and wash narrowing (host only: parses and
bindings; nothing is stepped).

**Why a probe of its own.** FR-64's validation/fr64/d327_probe.py counts the structure check's
admissions (pump_composite.structure_errors) over every ordered sequence of one to three registered
operators, and parses crossrev's catalogue with a voltage shift. FR-49 changes no structure check:
its two list entries and their own checks run at the definition. So this probe parses FR-49's
compositions themselves at a tree, as they are and with each of the inner model's later options,
and records each outcome with the check that gave it (D424: each newly parsing set gets a check or
a refusal by name). It is run, like FR-64's, on frozen snapshots of a head and its base.

**What it parses:**
- FR-49's registered worlds and their variants (validation/fr49/worlds_bc.py, loaded from this
  file's own folder, so a base tree that lacks the module is probed with the same definitions; the
  engine and the fixtures it reads are the tree's);
- the design checks: an inward population or set on the bounding patch, the compartment's node in
  the wash's nodes, sets with a wash elsewhere, cells.operator.species_regulated_availability@2
  reading a lumen-facing population, C4's four-way form and its three-way subset (invented values);
- each of World B, its node-owned variant, C1 and C2 with each later option: X2
  (execution.energy_check, bound as well as parsed, since it attaches after the definition's
  checks), the sparse field solver, @3's own one-way records (FR-50 phase 2), and a gate-free K leak
  on the owner's wall patch, alone, blocked (FR-51) and with a declared voltage shift on its block
  (FR-64);
- the compartments' law-level pairs: the marks of the composition matrix's rule for their admitted
  list (validation/tissue/composition_matrix.py), the pairs the declarations admit that the list
  refuses.

Usage, from a checkout that holds this file, against any tree (a checkout or a frozen snapshot):
    python validation/fr49/d327_probe.py <tree> <out.json>
"""

import copy
import importlib.util
import json
import subprocess
import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
X2 = {"check": "cells.execution.step_doubled_energy@1", "integration_error_cap": 2e-3}
SPARSE = "cells.solver.sparse_capacitive_reduction_gauged_damped_newton@1"
LEAK = "cells.channel.kleak_always_open@1"
GATED = "cells.channel.kv1p5_mh@1"  # Gates m and h; FR-64's gate shift reads a reversal.
BLOCK = {  # FR-51's B1 (as validation/fr64/d327_probe.py takes it).
    "law": "cells.channel_block.open_channel_block_weighted_modes@1",
    "blocker": {"id": "blocker", "valence": 4, "side": "inside", "concentration_mM": 5e-3},
    "modes": [
        {"weight": 0.6, "k0_mM": 1e-3, "electrical_distance": 0.85},
        {"weight": 0.4, "k0_mM": 1e-1, "electrical_distance": 0.30},
    ],
}
LABELS_LAW = "cells.operator.neutral_arrival_labels@1"
COUPLING_V2 = "cells.operator.species_regulated_availability@2"


def git(tree, *args):
    result = subprocess.run(["git", "-C", tree, *args], capture_output=True, text=True)
    return result.stdout.strip()


def identity(tree):
    """The tree's revision and dirty files, or a frozen snapshot's (SNAPSHOT.json)."""
    manifest = Path(tree) / "SNAPSHOT.json"
    if manifest.is_file():
        snapshot = json.loads(manifest.read_text(encoding="utf-8"))
        return dict(revision=snapshot["git_revision"], snapshot=str(tree),
                    patch_sha256=snapshot["patch_sha256"])  # fmt: skip
    return dict(revision=git(tree, "rev-parse", "HEAD"),
                dirty=git(tree, "status", "--short").splitlines())  # fmt: skip


def load_worlds():
    """This checkout's worlds_bc, importing the tree's engine, fixtures and World L."""
    spec = importlib.util.spec_from_file_location("fr49_worlds_bc", HERE / "worlds_bc.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def head_of(message):
    """The refusal's leading clause: the check that gave it, without the composite's prefix."""
    text = message.split("Invalid composite definition: ", 1)[-1]
    return text[:260]


def outcome(build, *, bind=False):
    """("parses" | "binds" | "refused" | "build error", detail) of one definition."""
    from cells.definitions.specs import ConfigError, parse_spec
    from cells.registry.models import get_model

    try:
        raw = build()
    except Exception as error:  # A builder that cannot run at this tree: recorded.
        return ["build error", f"{type(error).__name__}: {error}"[:400]]
    try:
        spec = parse_spec(copy.deepcopy(raw))
        if not bind:
            return ["parses", None]
        get_model(spec.model).initial_values(spec)
        return ["binds", None]
    except ConfigError as error:
        return ["refused", head_of(str(error))]
    except Exception as error:
        return ["error", f"{type(error).__name__}: {error}"[:400] + traceback.format_exc(limit=2)]


# ------------------------------------------------------------------ the options


def with_x2(raw):
    out = copy.deepcopy(raw)
    out["execution"]["energy_check"] = dict(X2)
    return out


def with_sparse(raw):
    out = copy.deepcopy(raw)
    out["execution"]["field_solver"] = SPARSE
    return out


def wall_patch(raw):
    """The first patch on a held bath (its inside a cell): the owner's wall in FR-49's worlds."""
    m = raw["model"]
    baths = {n["id"] for n in m["extracellular"] if n.get("reservoir")}
    return next(p for p in m["membranes"] if p["outside"] in baths)


def with_records(raw):
    """@3's own one-way records (FR-50 phase 2) on a wall patch's own K route."""
    out = copy.deepcopy(raw)
    patch = wall_patch(out)
    out["model"]["one_way_records"] = [dict(entity="membrane", id=patch["id"], species=["K"])]
    return out


def with_leak(raw, *, block=False, shift=False):
    """A gate-free K leak on a wall patch (never a bounding patch), blocked by FR-51's B1, and with
    the block's voltage shift on the K reversal (FR-64)."""
    out = copy.deepcopy(raw)
    m, e, x = out["model"], out["experiment"], out["execution"]
    patch = wall_patch(out)
    channel = dict(id="probe_leak", membrane_id=patch["id"], kinetic_law=LEAK,
                   max_permeability_m_per_s=1e-12, abundance=1.0, initial_gate=[],
                   permeant_ions=[dict(species_id="K", relative_permeability=1.0)])  # fmt: skip
    if block:
        channel["block"] = copy.deepcopy(BLOCK)
    if shift:
        channel["voltage_shift"] = {"block": {"reversal_of": "K"}}
    m["channels"] = [*m.get("channels", []), channel]
    e["channel_controls"] = [*e.get("channel_controls", []),
                             dict(channel_id="probe_leak",
                                  schedule=[dict(time=0.0, availability=1.0)])]  # fmt: skip
    x["channel_capacity"] = len(m["channels"])
    return out


def with_gated(raw):
    """A gated K channel (gates m and h) on a wall patch, its m gate shifted to the K reversal
    (FR-64's gate shift, alone: no block)."""
    out = copy.deepcopy(raw)
    m, e, x = out["model"], out["experiment"], out["execution"]
    patch = wall_patch(out)
    channel = dict(id="probe_gated", membrane_id=patch["id"], kinetic_law=GATED,
                   max_permeability_m_per_s=1e-12, abundance=1.0, initial_gate=[0.0, 1.0],
                   permeant_ions=[dict(species_id="K", relative_permeability=1.0)],
                   voltage_shift={"gates": {"m": {"reversal_of": "K"}}})  # fmt: skip
    m["channels"] = [*m.get("channels", []), channel]
    e["channel_controls"] = [*e.get("channel_controls", []),
                             dict(channel_id="probe_gated",
                                  schedule=[dict(time=0.0, availability=1.0)])]  # fmt: skip
    x["channel_capacity"] = len(m["channels"])
    return out


OPTIONS = {
    "X2 (execution.energy_check)": (with_x2, True),
    "the sparse field solver": (with_sparse, False),
    "@3's own one-way records": (with_records, False),
    "a gate-free K leak": (with_leak, False),
    "the leak blocked (FR-51)": (lambda raw: with_leak(raw, block=True), False),
    "the leak's block shifted (FR-64)": (lambda raw: with_leak(raw, block=True, shift=True), False),
    "a gated channel's gate shifted (FR-64)": (with_gated, False),
}


# ------------------------------------------------------------------ the worlds


def unlabelled_sites(raw, sfx, add_inventory_species, node, patch):
    """C4's addition (invented values): an outward population on the bounding patch `patch` binding
    G, an unlabelled neutral ligand at 1e-3 mM in the compartment `node`, 1e-12 mM elsewhere."""
    raw = add_inventory_species(raw, "G", trace_mM=1e-12, diffusivity_m2_per_s=1e-10,
                                floor_fmol=1e-20, concentrations_mM={node: 1e-3})  # fmt: skip
    population = sfx.population("lumen_g", patch=patch, face="outside", copies=6e4,
                                sites_per_copy=1, alpha=1.0, k_on=1e3, k_off=1e-3, theta0=0.0,
                                unit="lumen_site")  # fmt: skip
    population["ligand"] = "G"
    return sfx.with_site_occupancy(
        raw, [population], ligands=[sfx.ligand(trace_mM=1e-12, species="G")]
    )


def coupling_on_lumen(wb, sfx, fx, rf, owner):
    """@2 reading World B's lumen population (no wash) as its owner's source, its target the
    specimen's production of S (D424's Q10 row)."""
    raw = wb.set_amount(wb.topology(dt=0.1, end=1.0, every=0.5), wb.LYS, wb.LIGAND, 1e-4)
    raw = sfx.with_site_occupancy(raw, [wb.lumen_population(owner=owner)],
                                  ligands=[sfx.ligand(trace_mM=wb.B_TRACE_mM)])  # fmt: skip
    raw = fx.with_turnover(raw, [("make_x", "specimen", "production")],
                           [("make_x", "specimen", [(0.0, 1e-9)])])  # fmt: skip
    entry = dict(
        id="c_lumen",
        target=dict(operator=fx.TURNOVER, control="turnover_rate", ids=["make_x"],
                    evaluation="target_half_steps", operating_range=[0.0, 1.0]),
        source={"site_population": "lumen_sites", "quantity": "occupied_fraction"},
        law="site_fraction", basal=0.1,
    )  # fmt: skip
    raw = rf.with_coupling(raw, species=[], couplings=[entry])
    next(b for b in raw["model"]["operators"] if b["law"] == rf.LAW)["law"] = COUPLING_V2
    rank = {"cells.operator.site_occupancy@1": 0, COUPLING_V2: 1, fx.TURNOVER: 2}
    raw["model"]["operators"].sort(key=lambda b: rank.get(b["law"], -1))
    return raw


def catalogue(wb):
    """{name: (build, bind)} of FR-49's worlds and design checks."""
    from cells.registry.inventory_species import add_inventory_species
    from validation import id_table
    from validation.fr49 import worlds
    from validation.tissue import regulated_availability_fixtures as rf
    from validation.tissue import secreted_species_fixtures as fx
    from validation.tissue import site_occupancy_fixtures as sfx

    def c4(labelled_wash):
        raw = wb.world_c1() if labelled_wash else id_table.translate(worlds.world_l())
        raw = unlabelled_sites(raw, sfx, add_inventory_species, worlds.NODE, worlds.PATCH)
        for event in raw["experiment"].get("compartment_wash_events", ()):
            event["buffer_mM"]["G"] = 1e-12  # A buffer names every neutral species: G at its trace.
        return raw

    return {
        "World L (the control: a compartment world with neither law)": lambda: id_table.translate(
            worlds.world_l()
        ),
        "World B": wb.world_b,
        "World B at dt 0.05 s": lambda: wb.world_b(dt=0.05),
        "World B's twin": lambda: wb.world_b(event=False),
        "World B, node-owned": lambda: wb.world_b(owner="node"),
        "C1": wb.world_c1,
        "C1's twin": lambda: wb.world_c1(event=False),
        "C2": wb.world_c2,
        "C2 at dt 0.05 s": lambda: wb.world_c2(dt=0.05),
        "an inward population on the bounding patch": lambda: wb.world_b(face="inside"),
        "an inward set on the bounding patch": lambda: wb.world_c2(face="inside"),
        "a set owned by the compartment's node": lambda: wb.world_c2(owner="node"),
        "the compartment's node among the wash's nodes": lambda: wb.world_b(nodes=("well", "lys")),
        "the compartment washed": lambda: wb.world_b(nodes=("lys",), event_node="lys"),
        "sets at the compartment, a wash elsewhere": lambda: wb.world_c2(wash=True),
        "@2 reading the lumen population": lambda: coupling_on_lumen(wb, sfx, fx, rf, "patch"),
        "@2 reading the node's own sites": lambda: coupling_on_lumen(wb, sfx, fx, rf, "node"),
        "C4's four-way form (C1 with unlabelled sites; invented)": lambda: c4(True),
        "the three-way form (World L with unlabelled sites; invented)": lambda: c4(False),
    }


WITH_OPTIONS = (
    "World L (the control: a compartment world with neither law)",
    "World B",
    "World B, node-owned",
    "C1",
    "C2",
)


def matrix_pairs():
    """The marks of the compartments' list rule (law pairs the declarations admit and the list
    refuses), and the laws the list admits, at this tree."""
    from cells.operators import compartments
    from validation.tissue import composition_matrix as cm

    rule = next(r for r in cm.RULES if r["rule"].startswith(f"{compartments.LAW_ID} composes only"))
    marks = sorted({law for pair in rule.get("marks", ()) for law in pair} - {compartments.LAW_ID})
    return dict(admitted=list(compartments.ADMITTED), refused_by_the_list=marks)


def main(tree, out_path):
    sys.path[:0] = [tree + "/src", tree]
    started = time.time()
    wb = load_worlds()
    record = dict(**identity(tree), probe=str(Path(__file__).resolve()), worlds={}, options={})
    for name, build in catalogue(wb).items():
        record["worlds"][name] = outcome(build, bind=True)
    builders = catalogue(wb)
    for name in WITH_OPTIONS:
        record["options"][name] = {
            option: outcome(lambda add=add, name=name: add(builders[name]()), bind=bind)
            for option, (add, bind) in OPTIONS.items()
        }
    try:
        record["matrix"] = matrix_pairs()
    except Exception as error:  # Recorded: a matrix this tree cannot import.
        record["matrix"] = f"{type(error).__name__}: {error}"[:400]
    record["seconds"] = round(time.time() - started, 1)
    Path(out_path).write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8")
    parsed = sum(v[0] in ("parses", "binds") for v in record["worlds"].values())
    print(record["revision"][:8], f"{parsed} of {len(record['worlds'])} worlds parse;",
          record["seconds"], "s")  # fmt: skip


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
