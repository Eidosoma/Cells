"""The judge's commands, in the order of the campaign. `README.md` says which command opens which
file.

python -m validation.ensemble_reexpression.judge <command> ...
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import constants as c
from . import fabricate, flag_rows, plants, scoring, strictjson, structure
from .c0 import C0
from .legacy import Captures, Fault, Planted
from .registration import SPEC, Registration, StringsNote, load_profile
from .scoring import OrderFault
from .settlements import SettlementFault
from .settlements import read as read_settlements
from .table import TableSet, hash_folder


def registration(args) -> Registration:
    """The registered inputs, or a rehearsal's by its profile."""
    if args.profile:
        return Registration(
            folder=Path(args.spec), profile=load_profile(args.profile), rehearsal=True
        )
    return Registration(folder=Path(args.spec))


def recorded(folder, record_file) -> dict:
    """The recorded hashes of a folder of tables. Refuses where the folder is not the
    recorded one.
    """
    record, digest = strictjson.read(Path(record_file))
    if record.get("kind") != c.HASHES_KIND:
        raise OrderFault(f"{record_file} is no record of table hashes")
    if hash_folder(folder)["files"] != record["files"]:
        raise OrderFault(f"the tables of {folder} are not the recorded ones")
    return {"record_sha256": digest, "files": record["files"]}


def first_inputs(args, reg):
    """What stage 1 and stage 2 both read: the tables (which must be the recorded ones), the note,
    C0's record, and their hashes.
    """
    held = recorded(args.tables, args.tables_record)
    note = StringsNote.read(args.strings, reg.rehearsal)
    c0, c0_digest = strictjson.read(Path(args.c0))
    hashes = {
        "spec": reg.files,
        "tables": held,
        "strings_sha256": note.sha256,
        "c0_sha256": c0_digest,
    }
    return TableSet.read(args.tables, reg.consumers), note, c0, hashes


def file_with_digest(path, wanted: str):
    """A JSON file that must have the recorded sha256."""
    value, digest = strictjson.read(Path(path))
    if digest != wanted:
        raise OrderFault(f"the sha256 of {path} is {digest}, and the recorded one is {wanted}")
    return value


def cmd_hash(args):
    """Hash the tables' bytes. Nothing is parsed."""
    record = dict(hash_folder(args.tables), folder=str(args.tables))
    print(strictjson.dump(args.out, record), args.out)


def cmd_c0(args):
    """C0: the spec folder, the captures and the planted runs. No table."""
    reg = registration(args)
    record = C0(reg).run()
    if args.tables_record:
        record["tables_record_sha256"] = strictjson.sha256(Path(args.tables_record).read_bytes())
    digest = strictjson.dump(args.out, record)
    for clause in record["clauses"]:
        print(
            f"{clause['status']:5s} {clause['checked']:6d} {clause['clause']}"
            + (f"  {clause['faults'][:3]}" if clause["faults"] else "")
        )
    print("C0", record["status"], digest, args.out)
    return record["status"] == "pass"


def cmd_stage1(args):
    """Stage 1: power. Opens no capture and no planted run."""
    reg = registration(args)
    tables, note, c0, hashes = first_inputs(args, reg)
    power = scoring.stage1(scoring.Tables(reg, note, tables), c0, hashes)
    print(strictjson.dump(args.out, power), args.out)


def settled(args, hashes: dict, first=None) -> tuple:
    """The settlements and the record that they settle, or (None, None). A record must be a
    judgement of the same files. `first` is the first pass's record and its sha256, in a retry.
    """
    if not args.settlements:
        if args.settlements_sha256 or args.settled_record:
            raise OrderFault("a settlements' sha256 or record is given, and no settlements")
        return None, None
    if not args.settlements_sha256 or not args.settled_record:
        raise OrderFault("settlements need their recorded sha256, and the record that they settle")
    record, digest = strictjson.read(Path(args.settled_record))
    records = {digest: record} if first is None else {digest: record, first[1]: first[0]}
    for known in records.values():
        if known.get("kind") != c.RECORD_KIND:
            raise OrderFault("what is settled is no record of the judge's")
        of = {k: known["hashes"].get(k) for k in ("spec", "tables", "strings_sha256", "c0_sha256")}
        if of != {k: hashes[k] for k in of}:
            raise OrderFault("what is settled is a judgement of other files")
    return read_settlements(args.settlements, args.settlements_sha256, records), record


def cmd_stage2(args):
    """Stage 2: the scores, the retry owed, the verdicts. Needs power.json's recorded sha256."""
    reg = registration(args)
    power = file_with_digest(args.power, args.power_sha256)
    tables, note, c0, hashes = first_inputs(args, reg)
    scoring.check_power(scoring.Tables(reg, note, tables), c0, power, hashes)
    settlements, before = settled(args, hashes)
    state = scoring.Tables(reg, note, tables, settlements=settlements)
    record = scoring.Stage2(state, c0, power, Captures(reg), Planted(reg)).run()
    record["hashes"]["power_sha256"] = args.power_sha256
    written = before is not None and not before["retry_owed_waits_on"]
    if settlements is not None:
        record["hashes"]["settlements_sha256"] = settlements.sha256
        if written and before["retry_owed"] != record["retry_owed"]:
            raise OrderFault("what the retry is owed is not what is written already")
    write(args.out, record, owed=not written)


def cmd_retry_stage1(args):
    """Stage 1 of the retry: power of what the first pass owes, on the new triples."""
    reg = registration(args)
    first, owed, power, hashes, tables, note, c0, retry = retry_inputs(args, reg)
    state = scoring.Tables(reg, note, tables, retry, owed["runs"])
    print(strictjson.dump(args.out, scoring.stage1(state, c0, hashes, first)), args.out)


def cmd_retry_stage2(args):
    """Stage 2 of the retry: what was owed is judged again, and the verdicts are final."""
    reg = registration(args)
    power2 = file_with_digest(args.power_retry, args.power_retry_sha256)
    first, owed, power, hashes, tables, note, c0, retry = retry_inputs(args, reg)
    state = scoring.Tables(reg, note, tables, retry, owed["runs"])
    scoring.check_power(state, c0, power2, hashes, first)
    settlements, _ = settled(args, hashes, (first, hashes["first_record_sha256"]))
    state = scoring.Tables(reg, note, tables, retry, owed["runs"], settlements)
    record = scoring.Stage2(state, c0, power, Captures(reg), Planted(reg), power2, first).run()
    record["hashes"]["power_retry_sha256"] = args.power_retry_sha256
    if settlements is not None:
        record["hashes"]["settlements_sha256"] = settlements.sha256
    write(args.out, record, owed=False)


def retry_inputs(args, reg):
    """What both stages of the retry read: the first pass's files by their recorded sha256, and the
    retry's tables.
    """
    tables, note, c0, hashes = first_inputs(args, reg)
    power = file_with_digest(args.power, args.power_sha256)
    scoring.check_power(scoring.Tables(reg, note, tables), c0, power, hashes)
    owed = file_with_digest(args.owed, args.owed_sha256)
    first, first_digest = strictjson.read(Path(args.record))
    if (
        first["kind"] != c.RECORD_KIND
        or first["retry_owed"] != owed
        or first["hashes"].get("power_sha256") != args.power_sha256
    ):
        raise OrderFault(
            "the first pass's record, its power.json and its retry_owed.json do not belong together"
        )
    if not owed["runs"]:
        raise OrderFault("no retry is owed")
    hashes = {
        **hashes,
        "retry_tables": recorded(args.retry_tables, args.retry_record),
        "power_sha256": args.power_sha256,
        "owed_sha256": args.owed_sha256,
        "first_record_sha256": first_digest,
    }
    retry = TableSet.read(args.retry_tables, reg.consumers, retry=True)
    return first, owed, power, hashes, tables, note, c0, retry


def write(folder, record, owed: bool):
    """Write the record, the verdicts beside it, and (in the first pass) what the retry is owed. The
    last is written once, and after the copy guard's refusals are settled (Amendment 2, reading 28):
    a judgement that settles a flag alone leaves the one that stands beside the settled record.
    """
    folder = Path(folder)
    print(strictjson.dump(folder / "record.json", record), folder / "record.json")
    if owed and record["retry_owed_waits_on"]:
        print(
            f"retry_owed.json is not written: the copy guard's refusals "
            f"{record['retry_owed_waits_on']} wait for the checker"
        )
    elif owed:
        print(
            strictjson.dump(folder / "retry_owed.json", record["retry_owed"]),
            folder / "retry_owed.json",
        )
    verdicts = scoring.verdict_of(record)
    print(strictjson.dump(folder / "verdict.json", verdicts), folder / "verdict.json")
    for consumer, block in record["consumers"].items():
        print(f"{consumer}: {shown(block)}")


def shown(block) -> str:
    """A consumer's verdict as it is printed. What is pending is never shown as a pass."""
    if not block["pending"]:
        return block["verdict"]
    only = "pending on" if block["state"] == c.PENDING else "with"
    return f"{block['verdict']}, {only} {len(block['pending'])} flag(s) to the checker"


def cmd_structure(args):
    """The structure-only mode, for the format sample."""
    found = [structure.table_faults(args.tables)]
    if args.retry_tables:
        found.append(structure.table_faults(args.retry_tables))
    if args.out:
        strictjson.dump(args.out, found)
    faults = [fault for block in found for fault in block["faults"]]
    for block in found:
        print(block["folder"], block["consumers"], block["kinds_of_run"])
    for fault in faults[:40]:
        print("fault:", fault)
    print(f"{len(faults)} faults")
    return not faults


def cmd_fabricate(args):
    """The judge's own honest tables, with their SHA256SUMS and a strings note. They are
    fabricated.
    """
    reg = registration(args)
    made, note = fabricate.Fabricator(reg, Captures(reg), Planted(reg)).tables()
    folder = Path(args.out)
    write_tables(folder / "table", made)
    print(
        strictjson.dump(folder / "registered_strings.json", note),
        folder / "registered_strings.json",
    )


def write_tables(folder: Path, tables: dict):
    """Write tables and their SHA256SUMS."""
    lines = []
    for consumer, table in tables.items():
        name = f"table_{consumer}.json"
        lines.append(f"{strictjson.dump(folder / name, table)}  {name}")
    (folder / "SHA256SUMS").write_text("\n".join(lines) + "\n")


def cmd_selftest(args):
    """C0, the fabricated honest tables, and the judge's plants on them."""
    reg = registration(args)
    made = C0(reg)
    c0 = made.run()
    fabricator = fabricate.Fabricator(reg, made.captures, made.planted)
    tables, note_data = fabricator.tables()
    junctions = reg.families[reg.profile["plant_targets"]["junctions"]]
    retry = fabricator.retry_tables([junctions.retry_name])
    note = StringsNote(note_data, "fabricated", reg.rehearsal)
    record = plants.run_plants(reg, note, tables, c0, made.captures, made.planted, retry=retry)
    record = {
        "kind": "ensemble-reexpression judge self-test, version 1",
        "c0": c0["status"],
        **record,
    }
    # The three flag paths, which no judge's plant covers (Amendment 2, items 5 (a) and 9).
    record["flag_rows"] = flag_rows.rows(reg, note, tables, c0, made.captures, made.planted, retry)
    record["all_as_stated"] &= all(row["scores_as_stated"] for row in record["flag_rows"])
    # Amendment 2, item 9.5: the sha256 of each table as it was made and used. `fabricate` writes
    # the same bytes.
    record["fabricated"] = fabricate.MARK
    record["fabricated_tables_sha256"] = fabricate.digests(tables)
    record["fabricated_retry_tables_sha256"] = fabricate.digests(retry)
    return report_plants(args, record) and c0["status"] == "pass"


def cmd_plants(args):
    """The judge's plants on altered copies of the registered tables."""
    reg = registration(args)
    tables, note, c0, hashes = first_inputs(args, reg)
    refused = {k: f.refusals for k, f in tables.files.items() if f.refusals or f.data is None}
    if refused:
        raise OrderFault(f"a table is refused or absent, so no plant is formed: {refused}")
    data = {consumer: file.data for consumer, file in tables.files.items()}
    retry = None
    if bool(args.retry_tables) != bool(args.retry_record):
        raise OrderFault("a retry's tables and their hashes are given together, or not at all")
    if args.retry_tables:
        hashes["retry_tables"] = recorded(args.retry_tables, args.retry_record)
        held = TableSet.read(args.retry_tables, reg.consumers, retry=True).files
        retry = {k: f.data for k, f in held.items() if f.data is not None and not f.refusals}
    record = plants.run_plants(reg, note, data, c0, Captures(reg), Planted(reg), retry=retry)
    return report_plants(
        args,
        {
            "kind": "ensemble-reexpression judge's plants on the registered tables, version 1",
            "hashes": hashes,
            **record,
        },
    )


def report_plants(args, record) -> bool:
    """Write a record of plants and print each one's score."""
    digest = strictjson.dump(args.out, record)
    said = {True: "as stated", False: "NOT as stated", None: "not formed"}
    print("baseline:", record["baseline"])
    lines = [(p["plant"], p) for p in record["plants"]]
    lines += [(f"{r['row']} ({r['where']})", r) for r in record.get("flag_rows", ())]
    for name, item in lines:
        wrong = [what for what, good in item.get("checks", []) if good is False]
        why = wrong or item.get("cannot_be_formed") or item.get("not_formed") or ""
        print(f"{name:14s} {said[item['scores_as_stated']]} {why}")
    print("all as stated:", record["all_as_stated"], digest, args.out)
    return record["all_as_stated"]


def parser() -> argparse.ArgumentParser:
    """The command line."""
    top = argparse.ArgumentParser(
        prog="validation.ensemble_reexpression.judge", description=__doc__
    )
    sub = top.add_subparsers(dest="command", required=True)

    def add(name, run, *options):
        p = sub.add_parser(name, help=run.__doc__)
        p.add_argument("--spec", default=str(SPEC), help="the folder of the data files")
        p.add_argument("--profile", help="a rehearsal's profile (README)")
        for option in options:
            p.add_argument(option.rstrip("?"), required=not option.endswith("?"))
        p.set_defaults(run=run)

    first = ("--tables", "--tables-record", "--strings", "--c0")
    again = (
        "--power",
        "--power-sha256",
        "--record",
        "--owed",
        "--owed-sha256",
        "--retry-tables",
        "--retry-record",
    )
    add("hash", cmd_hash, "--tables", "--out")
    add("c0", cmd_c0, "--out", "--tables-record?")
    add("stage1", cmd_stage1, *first, "--out")
    settles = ("--settlements?", "--settlements-sha256?", "--settled-record?")
    add("stage2", cmd_stage2, *first, "--power", "--power-sha256", *settles, "--out")
    add("retry-stage1", cmd_retry_stage1, *first, *again, "--out")
    add(
        "retry-stage2",
        cmd_retry_stage2,
        *first,
        *again,
        "--power-retry",
        "--power-retry-sha256",
        *settles,
        "--out",
    )
    add("structure", cmd_structure, "--tables", "--retry-tables?", "--out?")
    add("fabricate", cmd_fabricate, "--out")
    add("selftest", cmd_selftest, "--out")
    add("plants", cmd_plants, *first, "--retry-tables?", "--retry-record?", "--out")
    return top


def main(argv=None) -> int:
    """Run one command. 0: done (and, for c0, selftest, plants and structure, without a fault)."""
    args = parser().parse_args(argv)
    try:
        good = args.run(args)
    except (OrderFault, Fault, SettlementFault) as error:
        print(f"refused: {error}", file=sys.stderr)
        return 2
    return 0 if good is None or good else 1


if __name__ == "__main__":
    sys.exit(main())
