"""D327's sequence probe for FR-64 (host only: structure checks and parses; nothing is run).

**Origin.** Ported from FR-65's scratch tools (/mnt/workspaces/Cells/fr65-coupling-20261126/probe/,
built_count.py and d327_probe.py, 26 and 27 November 2026; the note's §17, ruling 4). Those count
the structure check's admissions (pump_composite.structure_errors) over every ordered sequence of
one to three registered operators that holds a focus operator, on @3's bare adapter.

**What changes for FR-64.** FR-64 declares no operator: a voltage shift is an option of @3's
channel populations. It reaches the structure check only through the inner a composite is given,
whose layout gains the shift's fields. So every ordered sequence of one to three registered
operators is enumerated, with no focus, on several inners:
- FR-65's bare adapter;
- each catalogue world's own inner, unshifted and shifted (a twin pair).
For the sequences the structure check admits, FR-64's slot rule (pump_composite.block_slot_errors)
is evaluated beside each world. That is the rule counted on itself, not independent evidence.

**The catalogue.** Every world of crossrev's seven sets (validation/tissue/composite_crossrev.py)
is parsed as it is. A world in a frozen family's form (water@1, water@2, replacement@1) is also
parsed as the composition it rewrites to (pump_composite_spec.frozen_definition). Each world is
then parsed with a shift, against an unshifted twin:
- **a gate's shift** on a gated population: a gate on the reversal of a permeant ion. The
  injections are tried in order until one is not refused on its voltage domain, since a reversal
  can move a gate's voltage off its law's domain; the twin is the world as it is;
- **a block's shift**, where no population is gated: FR-51's B1 block on the first population that
  carries an ion, on that ion's reversal. Its twin is the same block, reading V.
Each refusal is classified by the check that raised it. The note's own rows
(validation/fr64/worlds.py) are parsed where the tree has them.

Runs against either tree, a checkout or a frozen snapshot, and records its revision and its dirty
files or the snapshot's patch:
    python validation/fr64/d327_probe.py <checkout> <out.json>
A base tree cannot express a shift, so its shifted rows are its refusal of the key.
"""

import copy
import itertools
import json
import subprocess
import sys
import time
from pathlib import Path

SHIFT = "voltage_shift"
FROZEN_FAMILIES = (
    "cells.model.resolved_pump_water@1",
    "cells.model.resolved_pump_water@2",
    "cells.model.resolved_pump_replacement@1",
)
BLOCK = {  # FR-51's B1 (validation/fr51/references/spec/cases.json, two_modes_inside).
    "law": "cells.channel_block.open_channel_block_weighted_modes@1",
    "blocker": {"id": "blocker", "valence": 4, "side": "inside", "concentration_mM": 5e-3},
    "modes": [
        {"weight": 0.6, "k0_mM": 1e-3, "electrical_distance": 0.85},
        {"weight": 0.4, "k0_mM": 1e-1, "electrical_distance": 0.30},
    ],
}
ATTEMPTS = 8  # Gate injections tried per world before its domain refusal is recorded.


def git(checkout, *args):
    result = subprocess.run(["git", "-C", checkout, *args], capture_output=True, text=True)
    return result.stdout.strip()


def identity(checkout):
    """The tree's revision and dirty files, or a frozen snapshot's (SNAPSHOT.json, written by
    scripts/gates/freeze_snapshot.py), which holds no Git checkout."""
    manifest = Path(checkout) / "SNAPSHOT.json"
    if manifest.is_file():
        snapshot = json.loads(manifest.read_text(encoding="utf-8"))
        return dict(revision=snapshot["git_revision"], snapshot=str(checkout),
                    patch_sha256=snapshot["patch_sha256"])  # fmt: skip
    return dict(revision=git(checkout, "rev-parse", "HEAD"),
                dirty=git(checkout, "status", "--short").splitlines())  # fmt: skip


def classify(error):
    """(class, message) of a refusal: the check that raised it, by its message's own words."""
    message = f"{type(error).__name__}: {error}"
    if SHIFT in message and ("nknown" in message or "nexpected" in message):
        return "the key is unknown at this tree", message
    if "a path without that structure would drop the shift" in message:
        return "fail-closed, by name: a path without @3's structure", message
    if "operator composition" in message or "refused beside" in message or "site sets" in message:
        return "composition, by name", message
    if "domain" in message:
        return "domain", message
    return "other", message


def parse(raw):
    from cells.definitions.specs import parse_spec

    try:
        return parse_spec(copy.deepcopy(raw)), None
    except Exception as error:  # Recorded with its class: the probe parses, it never runs.
        return None, classify(error)


def carried(channel):
    return [
        ion["species_id"]
        for ion in channel.get("permeant_ions", ())
        if ion.get("relative_permeability", 0) > 0
    ]


def gate_injections(raw):
    """Each (raw with one gate's shift, label), in order: populations, gates, carried ions."""
    from cells.definitions import surface_pump_v3_spec as spec_v3

    laws = spec_v3.channel_laws()
    for index, channel in enumerate(raw.get("model", {}).get("channels", ())):
        gates = getattr(laws.get(channel.get("kinetic_law")), "gates", ())
        if SHIFT in channel or not gates:
            continue
        for gate in gates:
            for ion in carried(channel):
                out = copy.deepcopy(raw)
                shift = {"gates": {gate: {"reversal_of": ion}}}
                out["model"]["channels"][index][SHIFT] = shift
                yield out, f"{channel['id']}: {gate} on the {ion} reversal"


def block_pair(raw):
    """(twin with B1's block on the first population carrying an ion, the same with the block on
    that ion's reversal, label), or None."""
    for index, channel in enumerate(raw.get("model", {}).get("channels", ())):
        ions = carried(channel)
        if ions and SHIFT not in channel and not channel.get("block"):
            twin = copy.deepcopy(raw)
            twin["model"]["channels"][index]["block"] = copy.deepcopy(BLOCK)
            out = copy.deepcopy(twin)
            out["model"]["channels"][index][SHIFT] = {"block": {"reversal_of": ions[0]}}
            return twin, out, f"{channel['id']}: B1's block on the {ions[0]} reversal"
    return None


def outcome(refusal):
    return "parses" if refusal is None else list(refusal)


def shifted_rows(raw, spec):
    """The world's shifted row: {kind, label, twin, shifted}, with the parsed pair (or None)."""
    first, attempts = None, 0
    for out, label in gate_injections(raw):  # The twin is the world as it is.
        attempts += 1
        shifted_spec, refusal = parse(out)
        if first is None:
            first = (label, refusal)
        if refusal is None or refusal[0] != "domain" or attempts == ATTEMPTS:
            row = dict(kind="gate", label=label, attempts=attempts, shifted=outcome(refusal))
            pair = (spec, shifted_spec) if spec is not None and shifted_spec is not None else None
            return row, pair
    if first is not None:  # Every injection refused on its domain.
        return dict(kind="gate", label=first[0], attempts=attempts, shifted=outcome(first[1])), None
    blocked = block_pair(raw)
    if blocked is None:
        return dict(kind="none", shifted="no population carries an ion"), None
    twin_raw, out, label = blocked
    twin_spec, twin_refusal = parse(twin_raw)
    shifted_spec, refusal = parse(out)
    row = dict(kind="block", label=label, twin=outcome(twin_refusal), shifted=outcome(refusal))
    pair = (twin_spec, shifted_spec) if twin_spec is not None and shifted_spec is not None else None
    return row, pair


def inner_of(spec):
    """The inner a composite of this world is given: a composite's own, else @3's adapter for the
    world's structure (pump_composite.model_for)."""
    from cells.models import pump_composite_adapter as adapter
    from cells.models import surface_pump_v3 as v3
    from cells.registry.models import get_model

    inner = getattr(get_model(spec.model), "inner", None)
    return inner if inner is not None else adapter.for_structure(v3.structure(spec.model))


def admitted(inner, sequences):
    from cells.models import pump_composite
    from cells.operators import OPERATORS

    return [
        s
        for s in sequences
        if not pump_composite.structure_errors(inner, tuple(OPERATORS[k] for k in s))
    ]


def slot_refused(sequences, spec):
    """How many sequences the slot rule refuses beside a parsed world, by the change it names."""
    from cells.models import pump_composite
    from cells.operators import OPERATORS

    out = {}
    for s in sequences:
        for message in pump_composite.block_slot_errors([(OPERATORS[k], None) for k in s], spec):
            reason = "FR-64" if "voltage shift" in message else "FR-51"
            out[reason] = out.get(reason, 0) + 1
    return out


def catalogue():
    """{set: {world: raw}} of crossrev's seven sets, each builder's failure recorded."""
    from validation.tissue import composite_crossrev as crossrev

    builders = {
        "base": crossrev.worlds,
        "qualification": crossrev.qualification_worlds,
        "injection": crossrev.injection_worlds,
        "volume": crossrev.volume_worlds,
        "kinds": crossrev.kinds_worlds,
        "acceptances": crossrev.acceptances_worlds,
        "replication": crossrev.replication_worlds,
    }
    out, failed = {}, {}
    for name, build in builders.items():
        try:
            out[name] = build()
        except Exception as error:  # Recorded: a set this tree cannot build.
            failed[name] = f"{type(error).__name__}: {str(error)[:300]}"
    return out, failed


def named_worlds():
    """The note's own rows, where the tree has validation/fr64 (FR-64's head)."""
    try:
        from validation.fr51 import engine as fr51
        from validation.fr64 import worlds
    except ImportError as error:
        return {}, f"absent at this tree: {error}"
    return {
        "D327's pair world (FR-50's records beside shifts, B4)": worlds.pair_world,
        "the composed world (bath schedule, B4, every reader)": worlds.composed_world,
        "FR-51's B1 (the block on the K reversal)": lambda: fr51.raw_world("B1_two_modes_E1"),
    }, None


def main(checkout, out_path):
    sys.path[:0] = [checkout + "/src", checkout]
    from cells.definitions import pump_composite_spec as composite_spec
    from cells.models import pump_composite_adapter as adapter
    from cells.operators import OPERATORS

    started = time.time()
    laws = list(OPERATORS)
    sequences = [s for n in (1, 2, 3) for s in itertools.permutations(laws, n)]
    bare = admitted(adapter, sequences)
    bare_set = set(bare)
    record = dict(
        **identity(checkout),
        operators=laws,
        checked=len(sequences),
        bare_adapter=dict(admitted=len(bare), sequences=[list(s) for s in bare]),
    )
    sets, failed = catalogue()
    record["catalogue_failed"] = failed
    rows, pairs_to_check = {}, {}
    for set_name, worlds in sets.items():
        for name, raw in worlds.items():
            forms = {f"{set_name}/{name}": raw}
            if raw.get("model", {}).get("id") in FROZEN_FAMILIES:
                composed = composite_spec.frozen_definition(raw)
                forms[f"{set_name}/{name} (as a composition)"] = composed
            for key, form in forms.items():
                spec, refusal = parse(form)
                row, pair = shifted_rows(form, spec)
                rows[key] = {"as it is": outcome(refusal), **row}
                if pair is not None:
                    pairs_to_check[key] = pair
    record["catalogue"] = rows
    pairs, seen = {}, {}
    for key, (twin_spec, shifted_spec) in pairs_to_check.items():
        twin, shifted_inner = inner_of(twin_spec), inner_of(shifted_spec)
        signature = (id(twin), id(shifted_inner))
        if signature in seen:
            pairs[key] = dict(same_inners_as=seen[signature])
            continue
        seen[signature] = key
        a, b = admitted(twin, sequences), admitted(shifted_inner, sequences)
        a_set, b_set = set(a), set(b)
        pairs[key] = dict(
            twin=len(a),
            shifted=len(b),
            newly_admitted=sorted(list(s) for s in b_set - a_set),
            no_longer_admitted=sorted(list(s) for s in a_set - b_set),
            twin_equals_bare_adapter=a_set == bare_set,
            slot_rule_beside_twin=slot_refused(a, twin_spec),
            slot_rule_beside_shifted=slot_refused(b, shifted_spec),
        )
    record["structure_pairs"] = pairs
    named, absent = named_worlds()
    record["named"] = {"absent": absent} if absent else {}
    for name, build in named.items():
        try:
            raw = build()
        except Exception as error:  # Recorded: a builder this tree cannot run.
            record["named"][name] = ["builder failed", f"{type(error).__name__}: {error}"[:600]]
            continue
        record["named"][name] = outcome(parse(raw)[1])
    record["seconds"] = round(time.time() - started, 1)
    with open(out_path, "w", encoding="utf-8") as handle:
        json.dump(record, handle, indent=1)
    state = f"{len(record['dirty'])} dirty" if "dirty" in record else "a frozen snapshot"
    print(record["revision"][:8], state, len(sequences), "sequences,",
          len(bare), "admitted on the bare adapter;", len(rows), "catalogue rows,", len(pairs),
          "twin pairs;", record["seconds"], "s")  # fmt: skip


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
