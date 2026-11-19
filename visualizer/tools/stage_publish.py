#!/usr/bin/env python3
"""Stage a publish of the page: what goes up, in which uploads.

After `npm run export`, this copies the exported page and every file it lists into one
folder laid out as the published artifact is, compares that folder with the one staged
for the last publish, and splits the files that changed into uploads.

    python3 tools/stage_publish.py --new out/publish-v14 --old out/publish-v13

- The new folder is the record of what was published: keep it until the next publish,
  when it is the `--old` one. Without `--old` every file is sent.
- A publish takes at most 255 files and 64 MB, and keeps the files it does not send. Each
  upload here stays under 240 files and 55 MB.
- One version of an artifact holds at most 511 files and 256 MB in all, the page among
  them. The staging says how much of that the artifact will then hold (the files listed
  now, the page, and what was published before and is no longer listed, which stays until
  it is removed by name), and stops when it would be over.
- `upload-N.json` in the new folder lists an upload's files as the Artifact tool takes
  them, relative to the new folder (its `root`).
- A link that was published from somewhere else has no staged folder to compare with:
  `--remote FILE` takes what the link holds from the Artifact tool's own listing of its
  files (saved as text, or as a JSON list of paths), and every file is sent unless `--old`
  is given too. `--remove` writes the files that are published and no longer listed into
  the first upload as removals (a map of path to path, with `null` for a file to remove),
  so that the link holds the page and its files and nothing else. The removals go first,
  and no upload adds more new files than the link has room for before its own removals
  count, so the link never passes a version's limit while the uploads land.

Standard library only. It reads `out/` and writes only the new folder.
"""
import argparse
import filecmp
import json
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PAGE = "cells-architecture.html"
MAX_FILES, MAX_BYTES = 240, 55_000_000
VERSION_FILES, VERSION_BYTES = 511, 256_000_000


def remote_listing(path):
    """What a link holds, from a saved listing: {published path: bytes or None}. The page itself is left out."""
    text = Path(path).read_text(encoding="utf-8")
    held = {}
    try:
        rows = json.loads(text)
    except ValueError:
        rows = None
    if isinstance(rows, list):
        for row in rows:
            name = row if isinstance(row, str) else row.get("path")
            held[name] = None if isinstance(row, str) else row.get("bytes")
    else:
        # The Artifact tool's listing: one line a file, `- "path"  type  N bytes`.
        for line in text.splitlines():
            found = re.match(r'\s*-\s+"([^"]+)"(?:.*?\s(\d+) bytes)?', line)
            if found:
                held[found.group(1)] = int(found.group(2)) if found.group(2) else None
    if not held:
        sys.exit(f"no file is named in the listing given with --remote: {Path(path).name}")
    return {name: size for name, size in held.items() if name not in ("index.html", PAGE)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--new", required=True, help="the folder to stage this publish in (made anew)")
    parser.add_argument("--old", help="the folder staged for the last publish; left out, every file is sent")
    parser.add_argument("--remote", help="what the link holds now: the Artifact tool's listing of its files, saved as text or as a JSON list of paths")
    parser.add_argument("--remove", action="store_true", help="write what is published and no longer listed into the first upload, as removals")
    parser.add_argument("--root", default=str(HERE.parent), help="the visualizer folder (default: this tool's)")
    arguments = parser.parse_args(argv)

    root, new = Path(arguments.root).resolve(), Path(arguments.new).resolve()
    old = Path(arguments.old).resolve() if arguments.old else None
    if old is not None and not old.is_dir():
        sys.exit(f"the folder given with --old does not exist: {old.name}")
    if old is not None and (new == old or old in new.parents or new in old.parents):
        sys.exit("--new and --old must be two separate folders")
    remote = remote_listing(arguments.remote) if arguments.remote else {}
    listed = json.loads((root / "out" / "cells-architecture.files.json").read_text(encoding="utf-8"))
    missing = [source for source in listed.values() if not (root / source).is_file()]
    if missing:
        sys.exit(f"{len(missing)} file(s) the export lists are not on disk, for one {missing[0]}: run the export again")

    if new.exists():
        shutil.rmtree(new)
    new.mkdir(parents=True)
    shutil.copy2(root / "out" / PAGE, new / PAGE)
    for published, source in listed.items():
        target = new / published
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / source, target)

    def same_as_before(published):
        return old is not None and (old / published).is_file() and filecmp.cmp(old / published, new / published, shallow=False)

    changed = [published for published in listed if not same_as_before(published)]
    # What is published and no longer listed, with its size where one is known: from the folder staged
    # last time, and from the link's own listing.
    gone = {}
    if old is not None:
        for path in old.rglob("*"):
            name = str(path.relative_to(old))
            if path.is_file() and name not in listed and name != PAGE and not name.startswith("upload-"):
                gone[name] = path.stat().st_size
    for name, held_size in remote.items():
        if name not in listed:
            gone[name] = held_size if held_size is not None else gone.get(name, 0)
    gone_sizes, gone = gone, sorted(gone)

    size = lambda name: (new / name).stat().st_size
    # What the link holds now, by name: what was staged last time and what its own listing names. The page is one more.
    held_names = set(remote)
    if old is not None:
        held_names |= {str(path.relative_to(old)) for path in old.rglob("*") if path.is_file() and str(path.relative_to(old)) != PAGE and not str(path.relative_to(old)).startswith("upload-")}
    is_new = lambda name: name not in held_names
    removing = gone if arguments.remove else []
    # The uploads, in order. Removals go first (every upload carries the new page, which names none of them), as many
    # to an upload as it may hold; files follow in the room that is left. An upload never adds so many new files that
    # the link would pass a version's limit before that upload's own removals count, whichever the service counts first.
    pending = [removing[k:k + MAX_FILES] for k in range(0, len(removing), MAX_FILES)]
    names, sent, held, most = sorted(changed), 0, len(held_names) + 1, len(held_names) + 1
    uploads, stuck = [], False
    while sent < len(names) or pending:
        remove = pending.pop(0) if pending else []
        send, total, added = [], 0, 0
        while sent < len(names):
            name = names[sent]
            if len(send) + len(remove) >= MAX_FILES or (send and total + size(name) > MAX_BYTES):
                break
            if is_new(name) and held + added + 1 > VERSION_FILES:
                break
            send.append(name)
            total += size(name)
            added += is_new(name)
            sent += 1
        if not send and not remove:
            # No room for the next new file, and nothing left to remove: the count below says by how much it is over.
            stuck = True
            break
        uploads.append((send, remove))
        most = max(most, held + added)
        held += added - len(remove)
    for number, (send, remove) in enumerate(uploads, 1):
        # An upload that also removes is a map of published path to its file, null for a file to remove.
        content = {**{name: None for name in remove}, **{name: name for name in send}} if remove else [{"path": name} for name in send]
        (new / f"upload-{number}.json").write_text(json.dumps(content, indent=1) + "\n", encoding="utf-8")

    megabytes = lambda names: f"{sum(size(name) for name in names) / 1e6:.1f} MB"
    print(f"{len(listed)} files beside the page ({megabytes(listed)}); the page is {size(PAGE) / 1e6:.2f} MB")
    print(f"to send: {len(changed)} ({megabytes(changed)}); the same as last time: {len(listed) - len(changed)}; published before and no longer listed: {len(gone)}")
    for number, (send, remove) in enumerate(uploads, 1):
        print(f"  upload {number}: {len(send)} files, {megabytes(send)}{f', and {len(remove)} removed by name' if remove else ''} -> {new.name}/upload-{number}.json")
    for name in gone[:8]:
        print(f"  no longer listed: {name}")
    if len(gone) > 8:
        print(f"  and {len(gone) - 8} more")
    if removing:
        print(f"  the first upload{'s remove' if len(removing) > MAX_FILES else ' removes'} them by name ({len(removing)}), before the new files go up")
        print(f"  while the uploads land the link holds at most {most} files")
    # What the artifact then holds in all: a publish keeps what it does not send, so what is no longer
    # listed still counts until it is removed by name.
    kept = [] if removing else gone
    held = len(listed) + 1 + len(kept)
    held_bytes = sum(size(name) for name in listed) + size(PAGE) + sum(gone_sizes[name] or 0 for name in kept)
    print(f"the artifact then holds {held} of at most {VERSION_FILES} files, the page among them, and {held_bytes / 1e6:.1f} of {VERSION_BYTES / 1e6:.0f} MB")
    if held > VERSION_FILES or held_bytes > VERSION_BYTES:
        sys.exit("that is over what one version of an artifact holds: remove what is no longer listed, or publish fewer files")
    if stuck:
        sys.exit(f"the link has no room for the next new file ({names[sent]}): remove what is no longer listed first (--remove), or publish fewer files")
    if held > 0.9 * VERSION_FILES or held_bytes > 0.9 * VERSION_BYTES:
        print("  that is nine tenths of the limit or more")


if __name__ == "__main__":
    main()
