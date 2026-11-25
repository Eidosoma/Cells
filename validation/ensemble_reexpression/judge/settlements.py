"""The settlements' file: what the checker settled of the flags that leave an entry at best
inconclusive (Amendment 2: item 5 (a), readings 12 and 24), and of the copy guard's refusals
(reading 28). Its form is the README's section 6.

A settlement names the record in which the checker saw the flag, by its sha256, and is read beside
that record alone.
"""

from __future__ import annotations

import re

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
        if item["counts_as"] not in c.COUNTS_AS:
            out.append(f"{where}: counts_as is {item['counts_as']!r}")
        if item["flag"] not in {f["id"] for f in record["flags_to_settle"]}:
            out.append(f"{where}: its record holds no flag {item['flag']!r}")
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


def read(path, wanted: str, records: dict) -> Settlements:
    """The settlements of a file that must have the recorded sha256."""
    try:
        data, digest = strictjson.read(path)
    except (OSError, ValueError) as error:  # a duplicate key is a ValueError too
        raise SettlementFault(f"{path}: {error}") from error
    if digest != wanted:
        raise SettlementFault(f"the sha256 of {path} is {digest}, and the recorded one is {wanted}")
    return Settlements(data, digest, records)
