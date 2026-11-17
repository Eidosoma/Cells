"""Draw a lineage tree and a supply graph from cells.relations@1 tables, with no engine code (D202).

D202 settles the format by a test: the arrays load with ``numpy.load(..., allow_pickle=False)``,
and a short script that imports no engine code draws a lineage tree and a supply graph from the
tables. This is that script. It imports numpy and the standard library only, never ``cells`` or
``jax``, and reads nothing but a run's relations.json, relations.npz and the record files the
descriptor names. It writes SVG by hand (no plotting library is a dependency).

Usage: python draw_relations.py RUN_DIR OUT_DIR

- lineage.svg: each life a bar from its birth to its end on the run's clock, one row per life, a
  root's descendants below it depth first; parent_of links from a parent's end to each daughter
  (labelled with the daughter's share), dashed precedes_in_slot links (a newcomer after the
  occupant it replaced) and dotted copied_from links (a copy from its donor). Each bar is labelled
  with its id, key (s:c) and end reason.
- supply.svg: the sources (left) and the vertices they supply or that lose material to a sink
  (right), each link weighed by its records: an edge with an event by the record's change across
  that event (the descriptor's event_rows), an edge without one by its change over the run, summed
  over species.
- graphs.json: what was drawn, with every weight, for checking.
"""

import json
import sys
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

import numpy as np

FORMAT = "cells.relations@1"
COUNT = 2**32  # A key is s * 2**32 + c.


def load(directory):
    """(descriptor, {table: {column: array}}), every array loaded without pickle."""
    directory = Path(directory)
    descriptor = json.loads((directory / "relations.json").read_text())
    if descriptor.get("format") != FORMAT:
        raise SystemExit(f"{directory}: not {FORMAT}")
    with np.load(directory / descriptor["arrays"], allow_pickle=False) as saved:
        arrays = {name: saved[name] for name in saved.files}
    tables = {
        table: {c["name"]: arrays[c["array"]] for c in entry["columns"]}
        for table, entry in descriptor["tables"].items()
    }
    return descriptor, tables


def rows(table):
    """A table's rows as dicts of plain values."""
    names = list(table)
    count = len(table[names[0]]) if names else 0
    return [{n: table[n][i].item() for n in names} for i in range(count)]


def record(directory, descriptor, name):
    """(times, values) of a record, its files joined in row order."""
    entry = descriptor["records"][name]
    times, values = [], []
    for part in entry["files"]:
        with np.load(Path(directory) / part["file"], allow_pickle=False) as saved:
            times.append(saved[entry["times"]])
            values.append(saved[entry["array"]])
    return np.concatenate(times), np.concatenate(values)


def weight(directory, descriptor, edge, event_times, cache):
    """An edge's weight: its own number, or its record's change across its event (event_rows) or
    over the whole run."""
    if not edge["weight_record"]:
        return None if np.isnan(edge["weight"]) else float(edge["weight"])
    name = edge["weight_record"]
    if name not in cache:
        cache[name] = record(directory, descriptor, name)
    times, values = cache[name]
    index = tuple(int(p) for p in edge["weight_index"].split(",")) if edge["weight_index"] else ()
    column = values[(slice(None), *index)]
    if edge["event"]:
        row = int(np.searchsorted(times, event_times[edge["event"]], side="left"))
        return float(column[row + 1] - column[row])
    return float(column[-1] - column[0])


def key_text(value):
    return f"{value // COUNT}:{value % COUNT}"


# ------------------------------------------------------------------ the lineage tree


def lineage_order(lives):
    """Lives depth first: each root by key, then its daughters by key, recursively."""
    daughters = {}
    for life in lives:
        daughters.setdefault(life["parent"], []).append(life)
    for group in daughters.values():
        group.sort(key=lambda x: x["key"])
    out = []

    def visit(life):
        out.append(life)
        for child in daughters.get(life["id"], []):
            visit(child)

    for root in daughters.get("", []):
        visit(root)
    return out


def lineage_svg(lives, title):
    order = lineage_order(lives)
    row = {life["id"]: i for i, life in enumerate(order)}
    start = min(x["birth_time"] for x in lives)
    stop = max(x["end_time"] for x in lives)
    span = (stop - start) or 1.0
    left, width, top, pitch = 40, 560, 50, 26
    label_x = left + width + 20

    def x(t):
        return left + width * (t - start) / span

    def y(life_id):
        return top + pitch * row[life_id]

    parts = [
        f'<text x="{left}" y="24" class="title">{escape(title)}</text>',
        f'<line x1="{left}" y1="{top - 14}" x2="{left + width}" y2="{top - 14}" class="axis"/>',
        f'<text x="{left}" y="{top - 18}" class="tick">{start:g}</text>',
        f'<text x="{left + width}" y="{top - 18}" class="tick" text-anchor="end">{stop:g}</text>',
    ]
    for life in order:
        y0, x0, x1 = y(life["id"]), x(life["birth_time"]), x(life["end_time"])
        if x1 - x0 < 1.0:
            parts.append(f'<circle cx="{x0:.1f}" cy="{y0}" r="3.5" class="life"/>')
        else:
            parts.append(f'<line x1="{x0:.1f}" y1="{y0}" x2="{x1:.1f}" y2="{y0}" class="life"/>')
        if life["parent"]:
            parent = y(life["parent"])
            parts.append(
                f'<path d="M{x0:.1f},{parent} L{x0:.1f},{y0}" class="parent_of"/>'
                f'<text x="{x0 + 3:.1f}" y="{y0 - 4}" class="share">{life["share"]:g}</text>'
            )
        for relation, other in (
            ("precedes_in_slot", life["predecessor"]),
            ("copied_from", life["donor"]),
        ):
            if other:
                parts.append(f'<path d="M{x0:.1f},{y(other)} L{x0:.1f},{y0}" class="{relation}"/>')
        label = f"{life['id']}  {key_text(life['key'])}  {life['end_reason']}"
        parts.append(f'<text x="{label_x}" y="{y0 + 4}" class="label">{escape(label)}</text>')
    height = top + pitch * len(order) + 20
    return _svg(label_x + 330, height, parts)


# ------------------------------------------------------------------ the supply graph


def supply_svg(links, title):
    """links: [(from, to, relation, weight)], one per (from, to, relation), weights summed."""
    sources = sorted({a for a, _, _, _ in links})
    targets = sorted({b for _, b, _, _ in links})
    top, pitch = 50, 34
    rows_used = max(len(sources), len(targets), 1)
    left_x, right_x = 230, 560
    ys = {name: top + pitch * i for i, name in enumerate(sources)}
    yt = {name: top + pitch * i for i, name in enumerate(targets)}
    largest = max([abs(w) for *_, w in links if w is not None] or [1.0]) or 1.0
    parts = [f'<text x="20" y="24" class="title">{escape(title)}</text>']
    for a, b, relation, w in links:
        stroke = 1.0 + 7.0 * (abs(w) / largest if w is not None else 0.0)
        text = "" if w is None else f"{w:.4g}"
        mid_y = (ys[a] + yt[b]) / 2
        parts.append(
            f'<line x1="{left_x}" y1="{ys[a]}" x2="{right_x}" y2="{yt[b]}" class="{relation}" '
            f'stroke-width="{stroke:.2f}"/>'
            f'<text x="{(left_x + right_x) / 2:.0f}" y="{mid_y - 4:.0f}" '
            f'class="share">{text}</text>'
        )
    for name, y0 in ys.items():
        parts.append(
            f'<text x="{left_x - 8}" y="{y0 + 4}" class="label" '
            f'text-anchor="end">{escape(name)}</text>'
        )
    for name, y0 in yt.items():
        parts.append(f'<text x="{right_x + 8}" y="{y0 + 4}" class="label">{escape(name)}</text>')
    return _svg(right_x + 260, top + pitch * rows_used + 20, parts)


def _svg(width, height, parts):
    style = (
        "text{font-family:sans-serif;fill:#222}.title{font-size:15px;font-weight:bold}"
        ".label{font-size:12px}.tick,.share{font-size:10px;fill:#555}.axis{stroke:#999}"
        ".life{stroke:#1f5fa8;stroke-width:5;fill:#1f5fa8}"
        ".parent_of{stroke:#1f5fa8;fill:none;stroke-width:1.5}"
        ".precedes_in_slot{stroke:#a85f1f;fill:none;stroke-width:1.5;stroke-dasharray:5 3}"
        ".copied_from{stroke:#2e8b57;fill:none;stroke-width:1.5;stroke-dasharray:2 3}"
        ".supplies{stroke:#2e8b57}.removes_to{stroke:#a83232}"
    )
    body = "\n".join(parts)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}"><style>{style}</style>'
        f'<rect width="100%" height="100%" fill="#fff"/>\n{body}\n</svg>\n'
    )


def draw(directory, out):
    """Draw both graphs from a run's tables into `out`; returns what was drawn."""
    directory, out = Path(directory), Path(out)
    descriptor, tables = load(directory)
    lives = rows(tables["lives"])
    edges = rows(tables["edges"])
    event_times = {e["id"]: e["time"] for e in rows(tables["events"])}
    sources = {s["id"]: s for s in rows(tables["sources"])}
    cache, links = {}, {}
    for edge in edges:
        if edge["relation"] not in ("supplies", "removes_to"):
            continue
        w = weight(directory, descriptor, edge, event_times, cache)
        link = (edge["from"], edge["to"], edge["relation"])
        if w is not None:
            links[link] = links.get(link, 0.0) + w
        else:
            links.setdefault(link, None)
    tree = [
        {
            "from": e["from"],
            "to": e["to"],
            "relation": e["relation"],
            "weight": None if np.isnan(e["weight"]) else e["weight"],
        }
        for e in edges
        if e["relation"] in ("parent_of", "precedes_in_slot", "copied_from")
    ]
    out.mkdir(parents=True, exist_ok=True)
    world = descriptor["world"][:12]
    (out / "lineage.svg").write_text(lineage_svg(lives, f"Lineage, world {world}"))
    drawn = sorted((a, b, r, w) for (a, b, r), w in links.items())
    labels = {k: f"{k} ({sources[k]['class']})" for k in sources}
    shown = [(labels.get(a, a), b, r, w) for a, b, r, w in drawn]
    (out / "supply.svg").write_text(supply_svg(shown, f"Supply, world {world}"))
    report = {
        "world": descriptor["world"],
        "lives": len(lives),
        "descent": sorted(tree, key=lambda e: (e["relation"], e["from"], e["to"])),
        "supply": [{"from": a, "to": b, "relation": r, "weight": w} for a, b, r, w in drawn],
        "zip_members": sorted(zipfile.ZipFile(directory / descriptor["arrays"]).namelist()),
    }
    text = json.dumps(report, indent=1, sort_keys=True, allow_nan=False)
    (out / "graphs.json").write_text(text + "\n")
    return report


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: python draw_relations.py RUN_DIR OUT_DIR")
    draw(sys.argv[1], sys.argv[2])
