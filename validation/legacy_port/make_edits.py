"""Write the deletion's own edits at a revision: edits.json, which goes with every deletion, and
edits-optional.json, which goes with the optional batch (make_deletion.py's --edits and
--optional-edits).

Usage: make_edits.py REPO REV OUT_DIR

Each text to replace is checked to stand exactly once in its file at REV, so a page that changed
since stops the script here and not in the deletion. An edit is {"file", "names", "replace", "why"}:
top-level definitions to remove from a Python file, and texts to replace; or {"file", "note"}: a
note under a document's title.
"""

import json
import subprocess
import sys
from pathlib import Path

REPO, REV, OUT = sys.argv[1], sys.argv[2], Path(sys.argv[3])
LAWS = "src/cells/laws/"
PAGES = "docs/library/cells/laws/"
PLASMA, STORE = LAWS + "reactions/plasma_calcium.py", LAWS + "reactions/er_calcium.py"
GATES = LAWS + "channels/calcium_gates.py"
PUMPS = (LAWS + "pumps/ca_atp_mass_action_positive.py", LAWS + "pumps/calcium_atpase.py")
edits = []


def show(path):
    argv = ["git", "-C", REPO, "show", f"{REV}:{path}"]
    return subprocess.run(argv, capture_output=True, text=True, check=True).stdout


def doc(path):
    """A module's docstring, as it stands."""
    text = show(path)
    return text[: text.index('"""', 3) + 3] + "\n"


def edit(path, names=(), replace=(), why=""):
    edits.append(dict(file=path, names=list(names), replace=[list(r) for r in replace], why=why))


# ---------------------------------------------------------------- the laws that only legacy used
edit(
    PLASMA,
    [
        "EXCHANGER_LAW",
        "ExchangerParameters",
        "exchange_rates",
        "PUMP_LAW",
        "MAX_AFFINITY_RT",
        "PumpParameters",
        "chemical_drive",
    ],
    [
        (
            doc(PLASMA),
            '''"""The calcium pump's kernel at a plasma membrane, on positive concentrations.

laws/pumps/ca_atp_mass_action_positive.py evaluates it. The one-calcium form with its numeric-mM ATP
quotient is BETSE v1.5.0's pumpCaATP (betse/science/sim_toolbox.py; docs/PLASMA_CALCIUM.md).
Positive cycles move Ca out. The exchange that was here is a cycle law of its own
(laws/cycles/sodium_calcium_exchange_symmetric_barrier.py).
"""
''',
        )
    ],
    "the superseded exchange kernel and four names that only legacy used (the lead, rulings 2 and "
    "3); pump_rates and MAX_VOLTAGE stay",
)
STORE_DOC = '''\
"""The calcium pump's kernel from the cytosol into a store, on positive concentrations.

One calcium per formal turnover, with a numeric-mM metabolic quotient: BETSE v1.5.0's pumpCaER
(betse/science/sim_toolbox.py; docs/ER_CALCIUM.md). It deliberately does not imply a two-calcium
SERCA cycle or proton exchange. Maintained ATP, ADP and Pi supply external chemical work. The
plasma membrane's pump evaluates it too (laws/reactions/plasma_calcium.py). The factor of a store's
release is laws/reactions/hill_product_factor.py.
"""
'''
edit(
    STORE,
    ["PUMP_LAW", "RELEASE_LAW", "METABOLISM", "release_open"],
    [
        (
            doc(STORE),
            STORE_DOC,
        )
    ],
    "by use (the lead): MAX_AFFINITY_RT, PumpParameters, chemical_drive and pump_rates stay, a "
    "live law runs them; release_open goes with its last user, tests/unit/test_er_calcium.py",
)
edit(
    "docs/CORE_LAWS_ROADMAP.md",
    replace=[
        (
            "the older kernels are `er_calcium`'s `release_open` and, for IP3, only at the tag",
            "the older kernels are only at the tag",
        )
    ],
    why="true once release_open goes",
)
edit(
    GATES,
    ["TEMPERATURE_K", "MIN_TAU_S"],
    [
        (
            doc(GATES),
            '''"""The CaV1.2-type gate law's names, in volts and seconds, for the calcium catalogue.

The law's own module is laws/channels/cav1p2_m2h.py (docs/CORE_SEAMS_DESIGN.md §8.2), which
declares it; this one re-imports its names for laws/channels/cav_channels.py. Continuous relaxation:
the gates are integrated by their host's solver.
"""
''',
        )
    ],
    "two names that only legacy used (the lead, ruling 3)",
)
for path in PUMPS:
    edit(
        path,
        replace=[
            (
                """Neutral identity for the equations of the existing Cells law
``plasma_calcium.PUMP_LAW``, evaluated by that same kernel
(``plasma_calcium.pump_rates``); its module cites the source law. Positive
cycles move one divalent Ca from the cytosol to the outside and hydrolyse one
ATP from maintained ATP/ADP/Pi pools. Saturation is in cytosolic Ca and ATP;
the thermodynamic factor is (1 - exp(affinity)) with
""",
                """Neutral identity for the equations of an older family's calcium pump, evaluated
by that family's kernel (``plasma_calcium.pump_rates``); its module cites the
source law. Positive cycles move one divalent Ca from the cytosol to the outside
and hydrolyse one ATP from maintained ATP/ADP/Pi pools. Saturation is in
cytosolic Ca and ATP; the thermodynamic factor is (1 - exp(affinity)) with
""",
            )
        ],
        why="the docstring named plasma_calcium.PUMP_LAW",
    )
# --------------------------------------------------------- three pages whose words become false
edit(
    PAGES + "sodium_calcium_exchange_symmetric_barrier@1.md",
    replace=[
        (
            "**The same rate elsewhere:** an older model family runs it as "
            "`ncx_3na_1ca_symmetric_barrier@1`,\nthrough a kernel that no live model runs and no "
            "test checks any more: the rows that checked it now\ncheck this law. It retires in "
            "that family's deletion, and its file then keeps the calcium pump alone.\n",
            "**The same rate elsewhere:** nowhere now. An older model family ran it as\n"
            "`ncx_3na_1ca_symmetric_barrier@1` and left with its kernel; the rows that checked "
            "that kernel check\nthis law.\n",
        )
    ],
    why="false once the deletion is in",
)
edit(
    PAGES + "atp_driven_transporter_mass_action_positive@2.md",
    replace=[
        (
            "| the older family's two calcium pump laws | that family | At its deletion; the two "
            "rate functions they are built on stay, since the inner model's own calcium pump calls "
            "them |",
            "| the older family's two calcium pump laws | no one: the family is gone | Gone with "
            "it; the two rate functions they were built on stay, since the inner model's own "
            "calcium pump calls them |",
        )
    ],
    why="false once the deletion is in",
)
edit(
    PAGES + "cav1p2_m2h@1.md",
    replace=[
        (
            "Older rows run the source's unchanged class out of process and compare it with these "
            "kernels, which the\nolder families still call. No run was compared with a "
            "measurement.\n",
            "Rows of the older calcium catalogue's test run the source's unchanged class out of "
            "process and compare\nit with these kernels, which that catalogue "
            "(`resolved_tissue@8`'s) still calls. No run was compared\nwith a measurement.\n",
        )
    ],
    why="false once the deletion is in",
)
# ------------------------------------------------------------------------- notes under a title
TAG = "`pre-cleanup-2026-11-25`"
PINNED = (
    "> **Legacy cleanup (25 November 2026, D386).** The models, configurations, commands, tests "
    "and tools\n> that this page names for the older families left the tree, and the tag "
    f"{TAG} keeps\n> them. Old records pin this page's bytes by their hash: the pinned bytes are "
    "the tag's, without\n> this note.\n\n"
)
BATCH = (
    "> **Legacy cleanup's optional batch (D386).** The references, tests and tools that this page "
    "names\n> under `tests/`, `scripts/` and `validation/` left the tree with the batch; the tag\n"
    f"> {TAG} keeps them. The page, its reports and its frozen results stay.\n\n"
)
BATCH_PINNED = BATCH.rstrip("\n") + (
    " Old records\n> pin this page's bytes by their hash: the pinned bytes are the tag's, without "
    "this note.\n\n"
)
PINNED_PAGES = (  # No check that stays reads their pins, with or without the optional batch.
    "BIOELECTRIC_CELL_SPEC",
    "BIOELECTRIC_PAIR",
    "FINITE_EXTRACELLULAR",
    "MULTISPECIES_MEMBRANE",
    "MULTISPECIES_MEMBRANE_NEXT",
    "PHYSICAL_IONIC_GRAPH",
    "SPATIAL_EXTRACELLULAR",
    "SPATIAL_EXTRACELLULAR_ACCEPTANCE",
)
PINNED_BATCH_PAGES = ("MULTISPECIES_MEMBRANE_SPEC", "SELECTIVE_CONTACT_SPEC")  # Batch scripts read.
BATCH_PAGES = (  # Old records pin each.
    "BETSE_VOLTAGE_GATE_CONTACT",
    "BIOELECTRIC_NUMERICS",
    "E02_BDF_REFINEMENT_A1",
    "E02_CANDIDATE_ENGINEERING",
    "E02_COMPARISON_RECORDING",
    "E02_DIAGNOSTIC_OPTIMIZATION",
    "E02_INTEGRATION_EVALUATION",
    "E02_LOSSLESS_EVIDENCE",
    "E02_REFERENCE_POLICY_A2",
    "FINITE_EXTRACELLULAR_SPEC",
    "PHYSICAL_IONIC_GRAPH_SPEC",
    "SELECTIVE_CONTACT_NUMERICS",
    "SOURCE_COUPLING_MAP",
    "SOURCE_EMT_GRAPH_REFERENCE",
    "SOURCE_EMT_PAIR_NUMERICS",
    "SOURCE_GRAPH_CONTINUATION",
    "SOURCE_GRAPH_PATHS_REFERENCE",
    "SOURCE_PREPARATION_REFERENCE",
)
NOTED_BATCH_PAGES = (  # They have a note already: the batch's goes after it.
    "docs/EMT_REFERENCE.md",
    "docs/VOLTAGE_GATED_MEMBRANE.md",
    "validation/betse/README.md",
)
why = "pinned by hash in old records; no check that stays reads the pin"
edits += [dict(file=f"docs/{p}.md", note=PINNED, why=why) for p in PINNED_PAGES]
why = "names files of the optional batch"
optional = [dict(file=f"docs/{p}.md", note=BATCH_PINNED, why=why) for p in BATCH_PAGES]
optional += [
    dict(file=p, note=BATCH, after_note=True, why=why + "; it already has a note")
    for p in NOTED_BATCH_PAGES
]
why = "pinned by hash; the scripts that read the pin are the batch's"
optional += [dict(file=f"docs/{p}.md", note=PINNED, why=why) for p in PINNED_BATCH_PAGES]
optional.append(
    dict(
        file="docs/ROADMAP.md",
        names=[],
        replace=[
            [
                "which the cleanup's optional batch would\n> take. After the cleanup the first two "
                "are not on `main`, and with the batch none of the three is. The\n> EMT switch "
                "itself",
                "which left with the cleanup's optional\n> batch. None of the three is on `main`. "
                "The EMT switch itself",
            ]
        ],
        why="true once the batch is in",
    )
)
# ----------------------------------------------------------------------------------- the checks
for entry in edits + optional:
    text = show(entry["file"])
    for old, _ in entry.get("replace", ()):
        assert text.count(old) == 1, (entry["file"], text.count(old), old[:60])
    if "note" in entry:
        assert text.startswith("# "), entry["file"]
        noted = "Legacy cleanup" in text.split("\n\n", 2)[1]
        assert noted == bool(entry.get("after_note")), (entry["file"], "has a note", noted)
for name, value in (("edits.json", edits), ("edits-optional.json", optional)):
    (OUT / name).write_text(json.dumps(value, indent=1, ensure_ascii=False) + "\n")
print(len(edits), "edits,", len(optional), "with the optional batch")
