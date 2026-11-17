// The tissue line's own styles (src/lenses/tissue_line.js): its colour tokens, light and dark, read by
// the lens from the page, and the rules of its card, its legend's scale and its labels. The lens puts
// `tissueTokens` into the page's document and `tissueCss` into the viewer's shadow root once, as a
// model system's view does (src/ui/entry_views.js, mountStyles); nothing else of the page changes.
//
// One quantity per cell, with a criterion of two thresholds (the experiment's driver states both):
// a diverging scale broken at them. Below the lower threshold one hue (orange), above the upper
// another (blue), each from light at its threshold to strong at the scale's end, and dark to light on
// a dark page; a neutral grey between the thresholds. Checked in OKLab (17 November 2026): each arm's
// lightness runs one way (light page: orange 0.85, 0.71, 0.51 and blue 0.77, 0.64, 0.42; dark page:
// orange 0.42, 0.62, 0.83 and blue 0.43, 0.60, 0.84), and each arm's colour at its threshold stands
// at least 9.5 (ΔE ×100) from the grey, so a value just past a threshold is not read as between.
// Orange and blue stay apart under every common colour-vision deficiency; neither is a status
// colour, and a cell's state is also written as the driver's letter where it is chosen.

export const TISSUE_COLOURS = {
  light: { below: ["#f6c095", "#e8853f", "#a14a0c"], between: "#cdd2d8", above: ["#8cb8ef", "#4a8ee0", "#174a8f"], frame: "#8a9aab", ground: "#ffffff" },
  dark: { below: ["#743a10", "#c96a26", "#f6b98a"], between: "#444b53", above: ["#1c4f94", "#3c82d4", "#a9cdf5"], frame: "#5b6f84", ground: "#101d29" },
};

const block = (colours) =>
  [
    ...colours.below.map((hex, k) => `--tissue-below-${k}: ${hex};`),
    `--tissue-between: ${colours.between};`,
    ...colours.above.map((hex, k) => `--tissue-above-${k}: ${hex};`),
    `--tissue-frame: ${colours.frame}; --tissue-ground: ${colours.ground};`,
  ].join(" ");

export const tissueTokens = `
:root { ${block(TISSUE_COLOURS.light)} }
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) { ${block(TISSUE_COLOURS.dark)} }
}
:root[data-theme="dark"] { ${block(TISSUE_COLOURS.dark)} }
`;

/** The tokens' names, in the order the lens reads them. */
export const TISSUE_TOKENS = {
  below: [0, 1, 2].map((k) => `--tissue-below-${k}`),
  between: "--tissue-between",
  above: [0, 1, 2].map((k) => `--tissue-above-${k}`),
  frame: "--tissue-frame",
  ground: "--tissue-ground",
};

/** The colours the page's tokens give now (light or dark), else the light ones. */
export function readTissueColours(host) {
  const style = host && typeof getComputedStyle === "function" ? getComputedStyle(host) : null;
  const dark = style?.getPropertyValue("--is-dark").trim() === "1";
  const fallback = dark ? TISSUE_COLOURS.dark : TISSUE_COLOURS.light;
  const read = (name, otherwise) => (style ? style.getPropertyValue(name).trim() : "") || otherwise;
  return {
    below: TISSUE_TOKENS.below.map((name, k) => read(name, fallback.below[k])),
    between: read(TISSUE_TOKENS.between, fallback.between),
    above: TISSUE_TOKENS.above.map((name, k) => read(name, fallback.above[k])),
    frame: read(TISSUE_TOKENS.frame, fallback.frame),
    ground: read(TISSUE_TOKENS.ground, fallback.ground),
    dark,
  };
}

export const tissueCss = `
.tissue-part { margin: 10px 0 0; }
.tissue-part .eyebrow { margin-bottom: 4px; }
.tissue-door { display: flex; width: 100%; text-align: left; gap: 8px; align-items: flex-start; font: inherit; color: var(--fg); background: var(--bg-raised); border: 1px solid var(--line); border-radius: 8px; padding: 8px 10px; min-height: 44px; cursor: pointer; }
.tissue-door:hover { border-color: var(--accent); }
.tissue-door:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.tissue-door[aria-pressed="true"] { border-color: var(--accent); box-shadow: inset 0 0 0 1px var(--accent); }
.tissue-door .tissue-door-mark { flex: none; width: 34px; height: 18px; margin-top: 2px; border-radius: 3px; background: linear-gradient(to right, var(--tissue-below-2) 0 24%, var(--tissue-above-0) 24% 40%, var(--tissue-above-2) 40%); }
.tissue-door .tissue-door-words { display: grid; gap: 2px; }
.tissue-door .tissue-door-title { font-weight: 600; font-size: 13.5px; }
.tissue-door .tissue-door-sub { color: var(--muted); font-size: 12px; line-height: 1.35; }
.tissue-back { display: inline-flex; align-items: center; gap: 6px; margin: 8px 0 0; font: inherit; font-size: 12.5px; color: var(--accent); background: var(--bg-raised); border: 1px solid var(--line); border-radius: 999px; padding: 6px 12px; min-height: 36px; cursor: pointer; }
.tissue-back:hover { border-color: var(--accent); }
.tissue-back:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.tissue-says { margin: 8px 0 0; padding: 0; list-style: none; display: grid; gap: 4px; font-size: 12.5px; line-height: 1.4; }
.tissue-says li { color: var(--fg); }
.tissue-says li:first-child { font-weight: 600; }
.tissue-slots { margin: 8px 0 0; display: grid; gap: 4px; }
.tissue-slot { display: grid; grid-template-columns: auto 1fr; gap: 2px 8px; align-items: baseline; font-size: 12.5px; line-height: 1.35; }
.tissue-slot b { font-weight: 600; white-space: nowrap; font-variant-numeric: tabular-nums; }
.tissue-slot.is-refused span { color: var(--muted); }
.tissue-slot .tissue-open { grid-column: 2; justify-self: start; font: inherit; font-size: 12px; color: var(--accent); background: none; border: 0; padding: 4px 0; min-height: 32px; cursor: pointer; text-decoration: underline; text-underline-offset: 2px; }
.label-tissue-head { font-weight: 600; font-size: 12.5px; color: var(--fg); background: color-mix(in srgb, var(--bg) 82%, transparent); border-radius: 4px; padding: 1px 5px; white-space: nowrap; pointer-events: none; }
.label-tissue-end { font-size: 11.5px; color: var(--muted); background: color-mix(in srgb, var(--bg) 82%, transparent); border-radius: 4px; padding: 1px 5px; white-space: nowrap; pointer-events: none; }
.tissue-criterion { margin: 8px 0 0; font-size: 12.5px; }
.tissue-criterion summary { cursor: pointer; min-height: 32px; display: flex; align-items: center; color: var(--accent); }
.tissue-criterion .card-text { overflow-wrap: anywhere; }
.tissue-criterion-source { color: var(--muted); }
.key-tissue-line { height: 12px; border-radius: 2px; background: radial-gradient(circle at 3px 2px, var(--tissue-below-2) 0 2px, transparent 2.5px) 0 0 / 5px 5px repeat-x, linear-gradient(to right, var(--tissue-below-2) 0 30%, var(--tissue-above-2) 30%) 0 6px / 100% 6px no-repeat; }
.key-tissue-bracket { height: 6px; margin-top: 4px; border: 1.5px solid var(--fg); border-bottom: 0; }
.key-tissue-refused { height: 10px; border: 1.5px dashed var(--muted); border-radius: 3px; }
.label-tissue-refused.is-vertical { writing-mode: vertical-rl; padding: 6px 1px; }
/* Lying along its place (the runs stacked, on a phone): its words wrap where the window is narrower than the line. */
.label-tissue-refused:not(.is-vertical) { white-space: normal; max-width: min(92vw, 420px); text-align: center; }
/* The label layer sets a label's bottom on its point; these stand centred on it, or under it, by their own height. */
.label-tissue-refused.is-centred { translate: 0 50%; }
.label-tissue-state { translate: 0 100%; }
.label-tissue-refused { font-size: 11.5px; color: var(--muted); background: color-mix(in srgb, var(--bg) 82%, transparent); border: 1px dashed var(--line); border-radius: 4px; padding: 1px 5px; white-space: nowrap; pointer-events: none; }
/* A tick's words end at its point, left of the picture (the label layer centres a label on its point; this moves it half its width). */
.label-tissue-tick { font-size: 10.5px; color: var(--muted); white-space: nowrap; pointer-events: none; font-variant-numeric: tabular-nums; translate: -50% 50%; min-width: 16px; text-align: right; } /* the label layer does not place a label under 12 px wide */
.label-tissue-tumor { font-size: 11px; color: var(--fg); white-space: nowrap; pointer-events: none; }
.label-tissue-state { font-size: 11px; font-weight: 600; color: var(--fg); background: var(--bg-raised); border: 1px solid var(--line); border-radius: 4px; padding: 0 4px; white-space: nowrap; pointer-events: none; }
`;
