"""Read Beard 2005 and its 2006 correction from the publisher, at run time.

Nothing here is committed from the papers: the XML is fetched from PLOS (or read from a
local download kept outside the repository), and only comparisons are printed or written to
the workspace.

- ``table1(xml)``: Table 1's rows as text (the XML table text agrees with the PDF tables,
  checked against the typeset pages, 19 November 2026);
- ``display_equations(xml)``: each display equation's MathML (kept inside XML comments)
  flattened to a token string, for comparison with the PDF, the version of record;
- ``check_model(model, article_xml, correction_xml)``: every printed parameter string in
  ``beard2005_model.json`` against both tables.
"""

from __future__ import annotations

import html
import json
import re
import sys
import urllib.request
from pathlib import Path

ARTICLE = "10.1371/journal.pcbi.0010036"
CORRECTION = "10.1371/journal.pcbi.0020008"
URL = "https://journals.plos.org/ploscompbiol/article/file?id={doi}&type={kind}"   # manuscript (XML) or printable (PDF)


def fetch(doi: str, kind: str = "manuscript") -> bytes:
    req = urllib.request.Request(URL.format(doi=doi, kind=kind), headers={"User-Agent": "research-client"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def read(doi: str, local_dir: Path | None, kind="manuscript") -> str:
    if local_dir is not None:
        p = Path(local_dir) / f"{doi.replace('/', '_')}_{kind}"
        if p.exists():
            return p.read_text(encoding="utf-8")
    return fetch(doi, kind).decode("utf-8")


def _cell_text(c: str) -> str:
    c = re.sub(r"<sub>(.*?)</sub>", r"_\1", c, flags=re.S)
    c = re.sub(r"<sup>(.*?)</sup>", r"^\1", c, flags=re.S)
    c = re.sub(r"<[^>]+>", "", c)
    return re.sub(r"\s+", " ", html.unescape(c)).strip()


def table1(xml: str) -> list[list[str]]:
    tw = re.findall(r"<table-wrap .*?</table-wrap>", xml, flags=re.S)[0]
    t = re.search(r"<table[ >].*?</table>", tw, flags=re.S).group(0)
    return [[_cell_text(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, flags=re.S)]
            for tr in re.findall(r"<tr>(.*?)</tr>", t, flags=re.S)]


def display_equations(xml: str) -> dict[str, str]:
    out = {}
    for b in re.findall(r"<disp-formula\b.*?</disp-formula>", xml, flags=re.S):
        fid = re.search(r'id="[^"]*-e(\d+)"', b).group(1)
        t = " ".join(re.findall(r"<!--(.*?)-->", b, flags=re.S))
        for tag, mark in (("msub", "_"), ("msup", "^")):
            t = re.sub(rf"<mml:{tag}>", f" {mark}{{", t)
            t = re.sub(rf"</mml:{tag}>", "} ", t)
        t = re.sub(r"<mml:mfrac>", " FRAC{", t)
        t = re.sub(r"</mml:mfrac>", "} ", t)
        t = re.sub(r"<[^>]+>", " ", t)
        out[str(int(fid))] = re.sub(r"\s+", " ", html.unescape(t)).strip()
    return out


def _norm(s: str | None) -> str | None:
    if s is None:
        return None
    s = s.replace("×", "x").replace("−", "-").replace("^", "").replace(" ", "")
    return s




def check_model(model: dict, article_xml: str, correction_xml: str) -> list[dict]:
    """Compare every printed value in the model file with both XML tables."""
    rows = {"e36": table1(article_xml), "e8": table1(correction_xml)}
    report = []
    for ver, tab in rows.items():
        by_name = {}
        for r in tab[1:]:
            key = re.sub(r"[\s_{}\^]", "", r[0]).replace("−", "-").lower()
            by_name[key] = r
        for name, p in model["parameters"].items():
            key = re.sub(r"[\s_,{}\^]", "", p["symbol"]).lower().replace("gamma", "γ")
            cand = [k for k in by_name if re.sub(r"[,]", "", k) == key]
            if not cand:
                report.append({"param": name, "table": ver, "status": "row not found"})
                continue
            r = by_name[cand[0]]
            for col, idx in (("without", 2), ("with", 3)):
                printed = _norm(r[idx]) if r[idx] not in ("—", "") else None
                mine = _norm(p[ver][col])
                report.append({"param": name, "table": ver, "column": col, "xml": printed, "model": mine,
                               "status": "ok" if printed == mine else "MISMATCH"})
    return report


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--local", type=Path, default=None, help="directory holding a local download (outside the repo)")
    ap.add_argument("--out", type=Path, required=True, help="workspace directory for the extracted comparison")
    args = ap.parse_args(argv)
    from .model import load
    art = read(ARTICLE, args.local)
    cor = read(CORRECTION, args.local)
    args.out.mkdir(parents=True, exist_ok=True)
    rep = check_model(load(), art, cor)
    (args.out / "table1_check.json").write_text(json.dumps(rep, indent=1))
    (args.out / "equations_web_xml.json").write_text(json.dumps(display_equations(art), indent=1, ensure_ascii=False))
    bad = [r for r in rep if r["status"] != "ok"]
    print(f"{len(rep)} table cells compared, {len(bad)} not ok")
    for r in bad:
        print(r)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
