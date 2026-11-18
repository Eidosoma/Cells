"""A bacterium's ribosome as its species file gives it (schema/SPECIES_SHAPES.md, `ribosome`).

The size is the viewer's own measure of E. coli's ribosome from the coordinates of two entries of
the Protein Data Bank, made by tools/measure_particle.py and kept in data/measures/ecoli.ribosome.json
(tests/measure_particle.test.mjs makes it again from the entries saved with the downloads). A PDB
entry states no size: each species file says whose measure it is, by which definition and tool,
and from which entry. The three bacteria's build tools write this block from here, so that the
measure is one, and a species with a structure of its own ribosome would give its own.
"""

from __future__ import annotations

import json
from pathlib import Path

RECORD = Path(__file__).resolve().parents[2] / "data" / "measures" / "ecoli.ribosome.json"
DRAWN = "7K00"  # the entry drawn: the finer of the two (1.98 Å); 5MDZ is given beside it as a second measure
BESIDE = "5MDZ"
PDB_TERMS = 'CC0 1.0: "Data files contained in the PDB archive are available under the CC0 1.0 Universal (CC0 1.0) Public Domain Dedication." (the wwPDB\'s usage policies)'
# Fetched by id from files.rcsb.org on 17 November 2026, with the wwPDB's terms read the day before (ecoli/wwpdb-ribosome/ and
# ecoli/wwpdb-terms/ among the downloads, each with its MANIFEST).
READ = "2026-11-17"


def sources():
    """The two entries, as sources of a species file: each permissive (CC0), named by its id."""
    record = json.loads(RECORD.read_text(encoding="utf-8"))["measured"]
    out = {}
    for entry in (DRAWN, BESIDE):
        said = record[entry]
        out[f"pdb{entry.lower()}"] = {
            "text": f"Protein Data Bank entry {entry}: {said['title']} ({said['method'].lower()}, {said['resolution_A']} Å; Escherichia coli).",
            "doi": f"10.2210/pdb{entry}/pdb",
            "url": f"https://www.rcsb.org/structure/{entry}",
            "licence": PDB_TERMS,
            "class": "permissive",
            "accessed": READ,
        }
    return out


def part(note=None):
    """The block `cell.parts.ribosome`: the measure the picture draws, the second entry's beside it, and whose measure it is."""
    data = json.loads(RECORD.read_text(encoding="utf-8"))
    drawn, beside = data["measured"][DRAWN], data["measured"][BESIDE]
    subunit = lambda one: {"across_nm": one["across_nm"], "centre_nm": one["centre_nm"], "axes": one["axes"]}  # noqa: E731
    block = {
        "large": subunit(drawn["large"]),
        "small": subunit(drawn["small"]),
        "across_nm": drawn["whole"]["across_nm"],
        "farthest_nm": drawn["whole"]["farthest_nm"],
        "between_nm": drawn["between_centres_nm"],
        "of": "Escherichia coli",
        "entry": DRAWN,
        "beside": {"entry": BESIDE, "across_nm": beside["whole"]["across_nm"], "farthest_nm": beside["whole"]["farthest_nm"], "between_nm": beside["between_centres_nm"]},
        "measured": f"The viewer's own measure from the entry's coordinates, by {data['tool']}: {data['definition']}. The frame: {data['frame']}. The Protein Data Bank states no size.",
        "sources": [f"pdb{DRAWN.lower()}", f"pdb{BESIDE.lower()}"],
    }
    if note:
        block["note"] = note
    return block


def fact(own=True):
    """The species' fact on its ribosome's size, in words, with how far the two entries differ."""
    data = json.loads(RECORD.read_text(encoding="utf-8"))["measured"]
    drawn, beside = data[DRAWN], data[BESIDE]
    size = lambda values: " by ".join(f"{value:g}" for value in values)  # noqa: E731
    differ = max(abs(a - b) for a, b in zip(drawn["whole"]["across_nm"], beside["whole"]["across_nm"]))
    whose = "its ribosome" if own else "drawn as E. coli's ribosome"
    return (
        f"{whose}, measured by the viewer from the coordinates of the Protein Data Bank's entry {DRAWN}: as the ellipsoids of the same spread "
        f"as their atoms, the large subunit {size(drawn['large']['across_nm'])} nm across and the small one {size(drawn['small']['across_nm'])} nm, "
        f"their centres {drawn['between_centres_nm']:g} nm apart, the whole {size(drawn['whole']['across_nm'])} nm (its farthest atoms "
        f"{size(drawn['whole']['farthest_nm'])} nm). The entry {BESIDE} gives {size(beside['whole']['across_nm'])} nm, within {differ:.1f} nm of it"
    )
