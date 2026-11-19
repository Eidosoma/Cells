"""Digitise Beard 2005's published model curves (Figs. 2-6) from the article's PDF.

Run at analysis time on a local copy of the PDF kept outside the repository; only the
resulting numbers (with their pixel uncertainty) are committed, in
``published_targets.json``. The figures themselves are never copied.

Method, per panel:
1. ``pdfimages`` extracts the embedded raster; the axes box is found from its long lines,
   and the axis limits are those printed at the box corners (read once from the figure,
   listed in ``PANELS``).
2. Each model curve is tracked column by column from a seed near its right end, taking the
   ink run nearest a linear prediction; dashes and markers become gaps.
3. The curves are drawn as straight segments between simulated points, so a value at a
   vertex ("knot") is taken from straight-line fits on both neighbouring segments, away
   from markers. The uncertainty is half the two sides' disagreement plus one pixel.
   Values at [Pi]e = 0 come from the first clean columns and carry a wider band.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

# figure -> PDF page, image index on that page (pdfimages -p numbering), colour
FIGURES = {
    "fig2": {"page": 8, "kind": "rgb"},
    "fig3": {"page": 9, "kind": "gray"},
    "fig4": {"page": 10, "index": 1, "kind": "gray"},
    "fig5": {"page": 10, "index": 0, "kind": "gray"},
    "fig6": {"page": 11, "kind": "stencil"},
}

# panel -> figure, search window for its box (x0, x1, y0, y1 in pixels), axis limits, curves.
# Each curve has a corridor: approximate values at the vertices, read once from the figure.
# The corridor is only a search window (+-4 px); the numbers come from the pixel fits.
KNOTS = (1.0, 2.0, 3.0, 5.0, 10.0)
_C = lambda *v: dict(zip((0.5, 1.0, 2.0, 3.0, 5.0, 10.0), v))
PANELS = {
    "fig4A": {"fig": "fig4", "win": (45, 470, 0, 340), "x": (0, 10), "y": (0, 1), "q": "NADH_frac", "curves": {
        "state4": _C(0.735, 0.752, 0.761, 0.768, 0.768, 0.769), "state3": _C(0.330, 0.317, 0.309, 0.3135, 0.328, 0.348)}},
    "fig4B": {"fig": "fig4", "win": (520, 932, 0, 340), "x": (0, 10), "y": (0, 350), "q": "MVO2_per_cyta", "curves": {
        "state3": _C(150, 204.7, 261.4, 288.4, 309.8, 320.2), "state4": _C(35, 35.1, 36.7, 36.5, 37, 37)}},
    "fig4C": {"fig": "fig4", "win": (45, 470, 340, 718), "x": (0, 10), "y": (0, 0.3), "q": "cytc_red_frac", "curves": {
        "state3": _C(0.12, 0.1437, 0.1656, 0.1787, 0.1928, 0.2069), "state4": _C(0.097, 0.1003, 0.1063, 0.1087, 0.1115, 0.1122)}},
    "fig4D": {"fig": "fig4", "win": (520, 932, 340, 718), "x": (0, 10), "y": (6.5, 7.5), "q": "pH_x", "edge": 7.14, "curves": {
        "state3": _C(7.138, 7.135, 7.127, 7.122, 7.111, 7.084), "state4": _C(7.12, 7.113, 7.104, 7.098, 7.087, 7.06)}},
    "fig5": {"fig": "fig5", "win": (60, 671, 0, 521), "x": (0, 10), "y": (140, 200), "q": "dPsi_mV", "curves": {
        "state4": _C(182.5, 185.4, 188.9, 190.8, 192.9, 196.1), "state3": _C(156.5, 156.7, 158.6, 160.7, 164.3, 169.8)}},
    "fig2A": {"fig": "fig2", "win": (45, 470, 0, 340), "x": (0, 10), "y": (0, 1), "q": "NADH_frac", "curves": {
        "state4": _C(0.73, 0.7467, 0.7558, 0.759, 0.7615, 0.7611), "state3": _C(0.33, 0.351, 0.361, 0.3565, 0.3424, 0.3154)}},
    "fig2B": {"fig": "fig2", "win": (520, 932, 0, 340), "x": (0, 10), "y": (0, 350), "q": "MVO2_per_cyta", "curves": {
        "state3": _C(150, 188.5, 237.6, 266, 298.6, 338.8), "state4": _C(34, 34.1, 34.25, 34.2, 34.2, 34.2)}},
    "fig2C": {"fig": "fig2", "win": (45, 470, 340, 718), "x": (0, 10), "y": (0, 0.3), "q": "cytc_red_frac", "curves": {
        "state3": _C(0.14, 0.1513, 0.16, 0.1648, 0.1673, 0.1678), "state4": _C(0.1, 0.1, 0.0989, 0.0993, 0.0983, 0.0955)},
        "red_curves": {"state3_noCytcFactor": _C(0.145, 0.1665, 0.1834, 0.1904, 0.1947, 0.1945),
                       "state4_noCytcFactor": _C(0.078, 0.0779, 0.0778, 0.0769, 0.0752, 0.0715)}},
    "fig2D": {"fig": "fig2", "win": (520, 932, 340, 718), "x": (0, 10), "y": (6.5, 7.5), "q": "pH_x", "edge": 7.145, "curves": {
        "state3": _C(7.142, 7.138, 7.131, 7.126, 7.117, 7.095), "state4": _C(7.125, 7.12, 7.11, 7.101, 7.09, 7.06)}},
    "fig3": {"fig": "fig3", "win": (60, 671, 0, 521), "x": (0, 10), "y": (140, 200), "q": "dPsi_mV", "curves": {
        "state4": _C(176.5, 177, 177.7, 178.3, 179.1, 181.1), "state3": _C(155, 152, 149.7, 148.7, 147.8, 147.4)}},
}


def read_pnm(path):
    b = Path(path).read_bytes()
    toks, i = [], 0
    while len(toks) < (3 if b[:2] == b"P4" else 4):
        while b[i:i + 1].isspace():
            i += 1
        j = i
        while not b[j:j + 1].isspace():
            j += 1
        toks.append(b[i:j])
        i = j
    i += 1
    w, h = int(toks[1]), int(toks[2])
    if toks[0] == b"P6":
        return np.frombuffer(b, np.uint8, w * h * 3, i).reshape(h, w, 3).astype(float)
    if toks[0] == b"P5":
        return np.frombuffer(b, np.uint8, w * h, i).reshape(h, w).astype(float)
    if toks[0] == b"P4":
        rb = (w + 7) // 8
        bits = np.unpackbits(np.frombuffer(b, np.uint8, rb * h, i).reshape(h, rb), axis=1)[:, :w]
        return (255.0 * (1 - bits))
    raise ValueError(toks[0])


def extract_images(pdf: Path, out: Path) -> dict:
    """Run pdfimages on the figure pages; return {figure: image array}."""
    out.mkdir(parents=True, exist_ok=True)
    subprocess.run(["pdfimages", "-f", "8", "-l", "11", "-p", str(pdf), str(out / "img")], check=True)
    files = sorted(out.glob("img-*"))
    imgs = {}
    for name, spec in FIGURES.items():
        page = [f for f in files if f.name.startswith(f"img-{spec['page']:03d}-") and f.suffix in (".ppm", ".pgm", ".pbm")]
        big = [f for f in page if f.stat().st_size > 50_000]
        big.sort(key=lambda f: int(f.stem.split("-")[-1]))
        f = big[spec.get("index", 0)]
        a = read_pnm(f)
        if spec["kind"] == "stencil":
            a = 255.0 - a   # the stencil is stored inverted
        imgs[name] = a
    return imgs


def _runs(v):
    out, i, n = [], 0, len(v)
    while i < n:
        if v[i]:
            j = i
            while j < n and v[j]:
                j += 1
            out.append((i, j - i))
            i = j
        else:
            i += 1
    return out


def find_box(gray, win):
    """Axes box (left, right, top, bottom) in pixels: the outermost near-full lines in the window."""
    x0, x1, y0, y1 = win
    sub = gray[y0:y1, x0:x1] < 220
    hs_count = sub.sum(axis=1)
    vs_count = sub.sum(axis=0)
    hs = np.nonzero(hs_count > 0.7 * hs_count.max())[0]
    vs = np.nonzero(vs_count > 0.5 * vs_count.max())[0]
    top = np.mean([y for y in hs if y < hs[0] + 3])
    bottom = np.mean([y for y in hs if y > hs[-1] - 3])
    left = np.mean([x for x in vs if x < vs[0] + 3])
    right = np.mean([x for x in vs if x > vs[-1] - 3])
    return x0 + left, x0 + right, y0 + top, y0 + bottom


def track(mask, box, xlim, ylim, corridor, tol_px=4.0, edge=None):
    """Ink along one curve: per column, the thin run nearest the corridor (within tol_px).

    Rows of (x_px, y_px, observed, run length). Markers (open circles, filled triangles)
    and label strokes give thick or distant runs and are skipped."""
    left, right, top, bottom = box
    to_px_x = lambda x: left + (x - xlim[0]) / (xlim[1] - xlim[0]) * (right - left)
    to_px_y = lambda y: bottom - (y - ylim[0]) / (ylim[1] - ylim[0]) * (bottom - top)
    cx = np.array([to_px_x(k) for k in sorted(corridor)])
    cy = np.array([to_px_y(corridor[k]) for k in sorted(corridor)])
    if edge is not None:
        cx = np.concatenate([[to_px_x(0.0)], cx])
        cy = np.concatenate([[to_px_y(edge)], cy])
    pts = []
    for x in range(int(np.ceil(left)) + 1, int(np.floor(right)) - 1):
        if x < cx[0] - 1:
            continue
        pred = float(np.interp(x, cx, cy))
        col = mask[int(top) + 2:int(bottom) - 1, x]
        runs = [(s0 + int(top) + 2 + (l - 1) / 2.0, l) for s0, l in _runs(col)]
        best = min(runs, key=lambda r: abs(r[0] - pred), default=None)
        if best is not None and abs(best[0] - pred) <= tol_px and best[1] <= 6:
            pts.append((x, best[0], 1, best[1]))
        else:
            pts.append((x, pred, 0, 0))
    return np.array(pts, float)


def knot_values(tr, box, xlim, ylim, knots=KNOTS, guard_px=5, with_edge=False):
    left, right, top, bottom = box
    to_px_x = lambda x: left + (x - xlim[0]) / (xlim[1] - xlim[0]) * (right - left)
    from_px_y = lambda py: ylim[0] + (bottom - py) / (bottom - top) * (ylim[1] - ylim[0])
    ypx_per_unit = (bottom - top) / (ylim[1] - ylim[0])
    x_px, y_px, obs, rl = tr.T
    ok = obs > 0
    med = np.median(rl[ok]) if ok.any() else 1
    out = {}
    edges = (0.5,) + tuple(knots)   # [0.5, 1] is the first straight segment used
    for k_i, k in enumerate(knots):
        kp = to_px_x(k)
        vals = []
        for lo, hi in ((edges[k_i], k), (k, edges[k_i + 2] if k_i + 2 < len(edges) else None)):
            if hi is None:
                continue
            a, b = to_px_x(lo), to_px_x(hi)
            sel = ok & (x_px > a + guard_px) & (x_px < b - guard_px) & (rl <= 2.5 * med + 1)
            if sel.sum() >= 5:
                c = np.polyfit(x_px[sel], y_px[sel], 1)
                vals.append(np.polyval(c, kp))
        if not vals:
            continue
        v = float(np.mean(vals))
        half = float(abs(vals[0] - vals[-1]) / 2.0) if len(vals) == 2 else 0.0
        out[k] = {"value": from_px_y(v), "unc": (half + 1.0) / ypx_per_unit, "sides": len(vals)}
    # the left end ([Pi]e = 0): first observed clean columns
    sel = ok & (x_px <= to_px_x(0) + 4) & (x_px >= to_px_x(0) + 1)
    if with_edge and sel.any():
        ys = y_px[sel]
        out[0.0] = {"value": from_px_y(float(np.mean(ys))),
                    "unc": (float(np.ptp(ys)) / 2.0 + 2.0) / ypx_per_unit, "sides": 0}
    return out


def digitise(pdf: Path, workdir: Path) -> dict:
    imgs = extract_images(pdf, workdir)
    res = {}
    for pname, P in PANELS.items():
        img = imgs[P["fig"]]
        gray = img.mean(axis=2) if img.ndim == 3 else img
        box = find_box(gray, P["win"])
        if img.ndim == 3:
            r, g, b = img[..., 0], img[..., 1], img[..., 2]
            black = (gray < 150) & (np.abs(r - g) < 60) & (np.abs(r - b) < 60)
            red = (r > 150) & (g < 120) & (b < 120)
        else:
            black = gray < 150
            red = None
        panel = {"box_px": [round(v, 1) for v in box], "x": P["x"], "y": P["y"], "quantity": P["q"],
                 "curves": {}}
        for cname, corridor in P["curves"].items():
            tr = track(black, box, P["x"], P["y"], corridor, edge=P.get("edge"))
            panel["curves"][cname] = knot_values(tr, box, P["x"], P["y"], with_edge="edge" in P)
        for cname, corridor in P.get("red_curves", {}).items():
            tr = track(red, box, P["x"], P["y"], corridor)
            panel["curves"][cname] = knot_values(tr, box, P["x"], P["y"])
        res[pname] = panel
    return res


TEXT_NUMBERS = {
    "P50_uM": {"value": 0.373, "where": "Results, 'Behavior of Model at Low Oxygen Concentration'",
               "conditions": "state 3, [ADP]e = 1.0 mM, [ATP]e = 0, [Pi]e unreported"},
    "P50_mmHg": {"value": 0.287, "where": "same"},
    "cytc_reduced_at_O2_50uM": {"value": 0.14, "where": "same", "conditions": "[ADP]e = 0.5 mM, [ATP]e = 0.87 mM, [Pi]e unreported"},
    "outer_membrane_ATP_ADP_gradient_uM": {"value": 20, "where": "Materials, 'Parameter values', class B",
                                           "conditions": "maximal respiration"},
    "O2_at_20_mmHg_M": {"value": 2.6e-5, "where": "'Simulation of isolated mitochondria'"},
}


def targets(digitised: dict) -> dict:
    """The committed targets file: the text's numbers and the digitised vertex values."""
    sig = lambda x, n: float(f"{x:.{n}g}")
    out = {
        "kind": "cells.validation.mito_reference_targets@1",
        "source": "Beard DA (2005) PLoS Comput Biol 1(4): e36, doi:10.1371/journal.pcbi.0010036 (CC BY). Numbers only; no figure is reproduced.",
        "method": "Model curves digitised from the article PDF's embedded figure rasters (200 ppi) by digitize.py: axes box from its lines, axis limits from the printed corner labels, curve ink within a +-4 px corridor, value at each simulated vertex ([Pi]e = 1, 2, 3, 5, 10 mM) from straight-line fits on both neighbouring segments. unc = half the two sides' disagreement + 1 px. [Pi]e = 0 is read only for the flat matrix-pH curves.",
        "text_numbers": TEXT_NUMBERS,
        "figures": {},
    }
    for p, panel in digitised.items():
        out["figures"][p] = {
            "quantity": panel["quantity"], "x_axis": "[Pi]e (mM)", "y_limits": panel["y"],
            "model": "with phosphate control" if p.startswith(("fig4", "fig5")) else "without phosphate control",
            "curves": {c: {f"{float(k):g}": [sig(v["value"], 5), sig(v["unc"], 2)]
                           for k, v in sorted(kv.items(), key=lambda t: float(t[0]))}
                       for c, kv in panel["curves"].items()}}
    return out


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("pdf", type=Path, help="local copy of the article PDF (kept outside the repository)")
    ap.add_argument("--out", type=Path, required=True, help="output JSON (workspace)")
    ap.add_argument("--targets", type=Path, default=None, help="also write the targets file (published_targets.json)")
    args = ap.parse_args(argv)
    with tempfile.TemporaryDirectory() as td:
        res = digitise(args.pdf, Path(td))
    args.out.write_text(json.dumps(res, indent=1, default=float))
    if args.targets is not None:
        args.targets.write_text(json.dumps(targets(res), indent=1))
    for p, d in res.items():
        for c, kv in d["curves"].items():
            print(p, c, {k: f"{v['value']:.4g}+-{v['unc']:.2g}" for k, v in sorted(kv.items())})


if __name__ == "__main__":
    sys.exit(main())
