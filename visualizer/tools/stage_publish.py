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
- `upload-N.json` in the new folder lists an upload's files as the Artifact tool takes
  them, relative to the new folder (its `root`).

Standard library only. It reads `out/` and writes only the new folder.
"""
import argparse
import filecmp
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PAGE = "cells-architecture.html"
MAX_FILES, MAX_BYTES = 240, 55_000_000


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--new", required=True, help="the folder to stage this publish in (made anew)")
    parser.add_argument("--old", help="the folder staged for the last publish; left out, every file is sent")
    parser.add_argument("--root", default=str(HERE.parent), help="the visualizer folder (default: this tool's)")
    arguments = parser.parse_args(argv)

    root, new = Path(arguments.root).resolve(), Path(arguments.new).resolve()
    old = Path(arguments.old).resolve() if arguments.old else None
    if old is not None and not old.is_dir():
        sys.exit(f"the folder given with --old does not exist: {old.name}")
    if old is not None and (new == old or old in new.parents or new in old.parents):
        sys.exit("--new and --old must be two separate folders")
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
    gone = []
    if old is not None:
        gone = sorted(name for name in (str(path.relative_to(old)) for path in old.rglob("*") if path.is_file()) if name not in listed and name != PAGE and not name.startswith("upload-"))

    size = lambda name: (new / name).stat().st_size
    uploads, upload, total = [], [], 0
    for name in sorted(changed):
        if upload and (len(upload) >= MAX_FILES or total + size(name) > MAX_BYTES):
            uploads.append(upload)
            upload, total = [], 0
        upload.append(name)
        total += size(name)
    if upload:
        uploads.append(upload)
    for number, names in enumerate(uploads, 1):
        (new / f"upload-{number}.json").write_text(json.dumps([{"path": name} for name in names], indent=1) + "\n", encoding="utf-8")

    megabytes = lambda names: f"{sum(size(name) for name in names) / 1e6:.1f} MB"
    print(f"{len(listed)} files beside the page ({megabytes(listed)}); the page is {size(PAGE) / 1e6:.2f} MB")
    print(f"to send: {len(changed)} ({megabytes(changed)}); the same as last time: {len(listed) - len(changed)}; published before and no longer listed: {len(gone)}")
    for number, names in enumerate(uploads, 1):
        print(f"  upload {number}: {len(names)} files, {megabytes(names)} -> {new.name}/upload-{number}.json")
    for name in gone[:8]:
        print(f"  no longer listed: {name}")
    if len(gone) > 8:
        print(f"  and {len(gone) - 8} more")


if __name__ == "__main__":
    main()
