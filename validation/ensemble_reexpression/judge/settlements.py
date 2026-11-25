"""The settlements' file: what the checker settled of the flags that leave an entry at best
inconclusive (Amendment 2: item 5 (a), readings 12, 24 and 25), and of the copy guard's refusals
(reading 28). Its form is the README's section 6.

A settlement names the record in which the checker saw the flag, by its sha256, and is read beside
that record alone.
"""

from __future__ import annotations

import re
from pathlib import Path

from . import constants as c
from . import strictjson

FLAG_KEYS = ("flag", "record_sha256", "counts_as", "checker", "when", "words", "evidence")
GUARD_KEYS = (
    "run",
    "comparison",
    "record_sha256",
    "outcome",
    "checker",
    "when",
    "words",
    "evidence",
    "lead_note",
)
NOTE_KEYS = ("path", "sha256", "date", "words")
HEX = re.compile(r"[0-9a-f]{64}")
UTC = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?Z")


class SettlementFault(Exception):
    """A settlements' file that cannot be used, and why."""


class Settlements:
    """What was settled: by a flag's ID, and by a run and the copy guard's comparison."""

    def __init__(self, data: dict, digest: str, records: dict):
        """`records` is sha256 to a judge's record, one that a settlement may name."""
        faults = faults_of(data, records)
        if faults:
            raise SettlementFault("; ".join(faults[:5]))
        self.sha256 = digest
        self.flags = {item["flag"]: item for item in data["flags"]}
        self.guard = {(item["run"], item["comparison"]): item for item in data["copy_guard"]}


def allowed(kind) -> tuple:
    """What a flag of a kind may count as. A reload is shown by the record (`by the rule`) or it is
    not (`inconclusive`): it is no fail (CRITERIA section 4.1).
    """
    return tuple(x for x in c.COUNTS_AS if kind != c.RELOAD or x != c.FAIL)


class ReloadsConfirmed:
    """Invented settlements for the judge's own plants and tests: every restart's reload is
    confirmed, and nothing else is settled. Without them no honest table of a consumer that has a
    restart passes, and no claim on its verdict could be read.
    """

    sha256 = "invented by the judge: every reload is confirmed"
    guard: dict = {}

    class _Flags(dict):
        def get(self, key, default=None):
            if not str(key).startswith(f"{c.RELOAD}; "):
                return default
            return {"flag": key, "counts_as": c.BY_THE_RULE, "checker": "invented by the judge"}

    flags = _Flags()


def faults_of(data, records: dict) -> list:
    """What makes the file unusable: every key is required, and no other is there."""
    if not isinstance(data, dict):
        return ["the settlements are not an object"]
    out = []
    if set(data) != {"kind", "protocol", "part", "flags", "copy_guard"}:
        return [f"the settlements' keys are {sorted(data)}"]
    if data["kind"] != c.SETTLEMENTS_KIND or data["protocol"] != c.PROTOCOL:
        out.append("the settlements' kind or protocol")
    if data["part"] != c.PART:
        out.append("the settlements' part")
    seen = set()
    for group, keys in (("flags", FLAG_KEYS), ("copy_guard", GUARD_KEYS)):
        if not isinstance(data[group], list):
            out.append(f"{group} is not a list")
            continue
        for i, item in enumerate(data[group]):
            where = f"{group}[{i}]"
            if not isinstance(item, dict) or set(item) != set(keys):
                out.append(f"{where}: its keys are not {list(keys)}")
                continue
            out += _item_faults(group, item, where, records, seen)
    return out


def _item_faults(group, item, where, records, seen) -> list:
    out = []
    key = (group, item["flag"]) if group == "flags" else (group, item["run"], item["comparison"])
    if key in seen:
        out.append(f"{where}: {key[1:]} is settled twice")
    seen.add(key)
    for name in ("checker", "words"):
        if not isinstance(item[name], str) or not item[name].strip():
            out.append(f"{where}: {name} is empty")
    if not isinstance(item["when"], str) or not UTC.fullmatch(item["when"]):
        out.append(f"{where}: when is no UTC time")
    if not isinstance(item["evidence"], list) or not all(
        isinstance(e, str) and e for e in item["evidence"]
    ):
        out.append(f"{where}: evidence is not a list of strings")
    digest = item["record_sha256"]
    if not isinstance(digest, str) or not HEX.fullmatch(digest):
        out.append(f"{where}: record_sha256 is no sha256")
        return out
    record = records.get(digest)
    if record is None:
        out.append(f"{where}: the record that it names is not one that was given")
        return out
    if group == "flags":
        found = {f["id"]: f["kind"] for f in record["flags_to_settle"]}
        if item["flag"] not in found:
            out.append(f"{where}: its record holds no flag {item['flag']!r}")
        if item["counts_as"] not in allowed(found.get(item["flag"])):
            out.append(f"{where}: counts_as is {item['counts_as']!r}")
        return out
    if item["outcome"] not in (c.STANDS, c.LIFTED):
        out.append(f"{where}: outcome is {item['outcome']!r}")
    hits = {(h["run"], h["comparison"]) for h in record["copy_guard"]}
    if (item["run"], item["comparison"]) not in hits:
        out.append(f"{where}: its record holds no such refusal by the copy guard")
    note = item["lead_note"]
    if (item["outcome"] == c.LIFTED) != (note is not None):
        out.append(f"{where}: a lifted refusal needs the lead's dated note, and another has none")
    elif note is not None and (
        not isinstance(note, dict)
        or set(note) != set(NOTE_KEYS)
        or not all(isinstance(note[k], str) and note[k] for k in NOTE_KEYS)
        or not HEX.fullmatch(note["sha256"])
    ):
        out.append(f"{where}: lead_note is not {list(NOTE_KEYS)}")
    return out


def fabricated(record: dict, counts_as=None, outcome=None) -> Settlements:
    """Settlements of every flag and every copy guard's refusal of a record, for the judge's own
    tests: the checker is invented, and so is the lead's note of a lifted refusal. A reload is
    confirmed where the flags count as a fail, which it cannot.
    """
    data, records = fabricated_data(record, counts_as, outcome)
    return Settlements(data, "fabricated", records)


def fabricated_data(record: dict, counts_as=None, outcome=None) -> tuple:
    """The same as a file would hold them, and the record that they name, by its sha256."""
    digest = strictjson.sha256(strictjson.encode(record))
    common = {
        "record_sha256": digest,
        "checker": "fabricated by the judge",
        "when": "2026-11-25T00:00:00Z",
        "words": "invented, for the judge's self-test",
        "evidence": [],
    }
    note = {"path": "invented", "sha256": "0" * 64, "date": "2026-11-25", "words": "invented"}
    data = {
        "kind": c.SETTLEMENTS_KIND,
        "protocol": c.PROTOCOL,
        "part": c.PART,
        "flags": [
            {
                "flag": item["id"],
                "counts_as": counts_as if counts_as in allowed(item["kind"]) else c.BY_THE_RULE,
                **common,
            }
            for item in record["flags_to_settle"]
        ],
        "copy_guard": [
            {
                "run": hit["run"],
                "comparison": hit["comparison"],
                "outcome": outcome,
                "lead_note": note if outcome == c.LIFTED else None,
                **common,
            }
            for hit in record["copy_guard"]
        ],
    }
    return data, {digest: record}


def read(path, wanted: str, records: dict) -> Settlements:
    """The settlements of a file that must have the recorded sha256. The lead's note of a lifted
    refusal must be there, and have its sha256: its bytes are hashed, and it is not opened.
    """
    try:
        data, digest = strictjson.read(path)
    except (OSError, ValueError) as error:  # a duplicate key is a ValueError too
        raise SettlementFault(f"{path}: {error}") from error
    if digest != wanted:
        raise SettlementFault(f"the sha256 of {path} is {digest}, and the recorded one is {wanted}")
    out = Settlements(data, digest, records)
    for item in out.guard.values():
        note = item["lead_note"]
        if note is None:
            continue
        try:
            found = strictjson.sha256(Path(note["path"]).read_bytes())
        except OSError as error:
            raise SettlementFault(f"the lead's note of {item['run']}: {error}") from error
        if found != note["sha256"]:
            raise SettlementFault(f"the lead's note of {item['run']} has another sha256")
    return out
