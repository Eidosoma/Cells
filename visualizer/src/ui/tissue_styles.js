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
  light: { below: ["#f6c095", "#e8853f", "#a14a0c"], between: "#cdd2d8", above: ["#8cb8ef", "#4a8ee0", "#174a8f"], frame: "#8a9aab", ground: "#ffffff", molecules: ["#0f9a87", "#7c55d0", "#c23b86"] },
  dark: { below: ["#743a10", "#c96a26", "#f6b98a"], between: "#444b53", above: ["#1c4f94", "#3c82d4", "#a9cdf5"], frame: "#5b6f84", ground: "#101d29", molecules: ["#2cc7b2", "#a58cf0", "#ea6fb4"] },
};

const block = (colours) =>
  [
    ...colours.below.map((hex, k) => `--tissue-below-${k}: ${hex};`),
    `--tissue-between: ${colours.between};`,
    ...colours.above.map((hex, k) => `--tissue-above-${k}: ${hex};`),
    `--tissue-frame: ${colours.frame}; --tissue-ground: ${colours.ground};`,
    ...colours.molecules.map((hex, k) => `--tissue-molecule-${k}: ${hex};`),
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
  molecules: [0, 1, 2].map((k) => `--tissue-molecule-${k}`),
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
    molecules: TISSUE_TOKENS.molecules.map((name, k) => read(name, fallback.molecules[k])),
    accent: read("--accent", dark ? "#5b9dee" : "#1f6fd0"),
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
@media (min-width: 760px) { .tissue-way-back { white-space: nowrap; min-height: 30px; padding: 4px 12px; font-size: 12px; } }
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
.label-tissue-change { font-size: 11.5px; font-weight: 600; color: var(--bg-raised); background: var(--accent); border-radius: 4px; padding: 1px 6px; white-space: nowrap; pointer-events: none; box-shadow: 0 1px 3px color-mix(in srgb, var(--fg) 30%, transparent); }
.key-tissue-bars { height: 12px; background: linear-gradient(to right, var(--tissue-molecule-0) 0 30%, transparent 30% 35%, var(--tissue-molecule-1) 35% 65%, transparent 65% 70%, var(--tissue-molecule-2) 70%); border-radius: 2px; }
.key-tissue-ring { width: 12px; height: 12px; margin-left: 4px; border: 2.5px solid var(--accent); border-radius: 50%; }
.tissue-changes { margin: 8px 0 0; font-size: 12.5px; }
.tissue-changes summary { cursor: pointer; min-height: 32px; display: flex; align-items: center; color: var(--accent); }
.tissue-changes ul { margin: 4px 0 0; padding-left: 18px; display: grid; gap: 2px; max-height: 220px; overflow: auto; }
.tissue-changes .link-button { text-align: left; font-size: 12px; }
/* Lying along its place (the runs stacked, on a phone): its words wrap where the window is narrower than the line. */
.label-tissue-refused:not(.is-vertical) { white-space: normal; max-width: min(92vw, 420px); text-align: center; }
.label-tissue-refused { font-size: 11.5px; color: var(--muted); background: color-mix(in srgb, var(--bg) 82%, transparent); border: 1px dashed var(--line); border-radius: 4px; padding: 1px 5px; white-space: nowrap; pointer-events: none; }
.label-tissue-tick { font-size: 10.5px; color: var(--muted); white-space: nowrap; pointer-events: none; font-variant-numeric: tabular-nums; min-width: 16px; text-align: left; } /* the label layer does not place a label under 12 px wide */
.label-tissue-state { font-size: 11px; font-weight: 600; color: var(--fg); background: var(--bg-raised); border: 1px solid var(--line); border-radius: 4px; padding: 0 4px; white-space: nowrap; pointer-events: none; }
/* The part's caption over its tissues, in full on the first screen (src/lenses/tissue_line.js keeps the room above them for it). */
.label-tissue-caption { font-size: 12.5px; line-height: 1.4; color: var(--fg); background: color-mix(in srgb, var(--bg) 90%, transparent); border: 1px solid var(--line); border-radius: 8px; padding: 5px 10px; white-space: normal; width: max-content; max-width: min(calc(100vw - 32px), 620px); text-align: center; text-wrap: balance; pointer-events: none; }
.tissue-door-button { margin: 0; color: var(--bg-raised); background: var(--accent); border-color: var(--accent); font-weight: 600; }
.label-tissue-group { font-weight: 600; font-size: 12.5px; color: var(--fg); background: color-mix(in srgb, var(--bg) 82%, transparent); border-radius: 4px; padding: 1px 5px; white-space: normal; width: max-content; max-width: min(calc(100vw - 40px), 560px); pointer-events: none; }
.key-tissue-threshold { height: 0; margin-top: 6px; border-top: 2px dashed var(--fg); }
/* The example's other part with a caption of its own (the sheet, from the line): its caption, then its door. */
.tissue-sibling-block { margin: 10px 0 0; padding: 8px 10px; border: 1px solid var(--line); border-radius: 10px; background: color-mix(in srgb, var(--accent) 7%, var(--bg-raised)); display: grid; gap: 4px; justify-items: start; }
.tissue-sibling-block .card-text { margin: 0; font-size: 12.5px; line-height: 1.4; color: var(--fg); }
.tissue-sibling-block .tissue-back { margin: 0; color: var(--bg-raised); background: var(--accent); border-color: var(--accent); font-weight: 600; }
.tissue-front { color: var(--muted); font-size: 12px; }
/* What a newcomer is looking at: the record's own sentences, each with its source. */
.tissue-intro { margin: 10px 0 0; padding: 8px 10px; border-radius: 10px; border: 1px solid var(--line); background: var(--bg-raised); display: grid; gap: 4px; }
.tissue-intro-title { margin: 0; font-size: 11px; font-weight: 600; letter-spacing: .04em; text-transform: uppercase; color: var(--muted); }
.tissue-intro-first { margin: 0; font-size: 12.5px; font-weight: 600; color: var(--fg); display: flex; gap: 6px; align-items: baseline; }
.tissue-intro-play { flex: none; width: 0; height: 0; border-style: solid; border-width: 5px 0 5px 8px; border-color: transparent transparent transparent var(--accent); translate: 0 1px; }
.tissue-intro-says { margin: 0; font-size: 12.5px; line-height: 1.45; color: var(--fg); }
.tissue-intro-source { font-size: 11px; color: var(--accent); text-decoration: none; white-space: nowrap; }
.tissue-intro-source:hover { text-decoration: underline; }
.tissue-intro-more { font-size: 12.5px; }
.tissue-intro-more summary { cursor: pointer; min-height: 30px; display: flex; align-items: center; color: var(--accent); }
.tissue-intro-more .tissue-intro-says { margin-top: 4px; }
/* A cell's switch: its records in the plane of its two stated concentrations. */
.tissue-switch-block { margin: 10px 0 0; display: grid; gap: 4px; }
.tissue-switch { margin: 0; display: grid; gap: 4px; }
.tissue-switch svg { width: 100%; max-width: 260px; height: auto; display: block; }
.tissue-switch figcaption { font-size: 11.5px; line-height: 1.4; color: var(--muted); }
.tissue-switch-band { font-size: 10.5px; font-weight: 600; fill: var(--fg); }
.tissue-switch-tick { font-size: 9.5px; fill: var(--muted); font-variant-numeric: tabular-nums; }
.tissue-switch-axis { font-size: 10px; fill: var(--muted); }
/* The walk: each coupling a point to press. */
.tissue-walk-block { margin: 10px 0 0; display: grid; gap: 4px; justify-items: start; }
.tissue-walk { margin: 0; display: grid; gap: 4px; }
.tissue-walk-block { justify-items: stretch; }
.tissue-walk svg { width: 100%; height: auto; display: block; }
.tissue-walk figcaption { font-size: 11.5px; line-height: 1.4; color: var(--muted); }
.tissue-walk-point { cursor: pointer; }
.tissue-walk-point:focus-visible { outline: none; }
.tissue-walk-point:focus-visible circle:last-of-type, .tissue-walk-point:hover circle:last-of-type { stroke-width: 3; }
.label-tissue-walk-label { background: color-mix(in srgb, var(--bg) 88%, transparent); border: 1px solid var(--line); border-radius: 8px; padding: 4px 8px 4px; white-space: normal; width: 270px; }
.label-tissue-walk-label .tissue-walk-block { margin: 0; }
.label-tissue-walk-label .tissue-walk-describe { display: none; }
.label-tissue-walk-label .tissue-walk figcaption { font-size: 10px; line-height: 1.3; }
.label-tissue-walk-label .tissue-intro-title { font-size: 10px; }
.label-tissue-switch-label { pointer-events: none; background: color-mix(in srgb, var(--bg) 88%, transparent); border: 1px solid var(--line); border-radius: 8px; padding: 4px 8px 4px; white-space: normal; width: 300px; }
.label-tissue-switch-label .tissue-switch svg { max-width: 200px; margin: 0 auto; }
.label-tissue-switch-label figcaption { font-size: 11px; line-height: 1.35; max-height: 2.8em; overflow: hidden; text-align: center; white-space: normal; }
/* The tissue's names on the picture (src/lenses/tissue_line.js lays them out so that none meets another or a cell: each
   stands with its middle bottom on its point, as the label layer places it, and no rule here moves it off that). */
.label-tissue-head .tissue-line, .label-tissue-end .tissue-line, .label-tissue-over .tissue-line { display: block; }
.label-tissue-head.is-stacked, .label-tissue-end.is-stacked { text-align: center; white-space: normal; width: max-content; }
.label-tissue-head .is-place { font-size: 13px; }
.label-tissue-head .is-value { font-size: 10.5px; font-weight: 500; color: var(--muted); white-space: nowrap; }
.label-tissue-end .is-early, .label-tissue-over .is-early { font-style: italic; }
.label-tissue-over.is-overlaid { display: grid; }
.label-tissue-over.is-overlaid > .tissue-line { grid-area: 1 / 1; }
.label-tissue-head.is-wrap, .label-tissue-end.is-wrap { white-space: normal; width: max-content; }
.label-tissue-over { font-size: 12px; line-height: 1.4; color: var(--fg); text-align: center; white-space: normal; width: max-content; padding: 1px 6px; pointer-events: none; }
/* The key over the tissues: the three dots in a cell, and a bead. */
.label-tissue-key { display: flex; flex-wrap: wrap; justify-content: center; gap: 2px 16px; width: max-content; font-size: 11.5px; line-height: 1.4; color: var(--muted); white-space: normal; pointer-events: none; padding: 1px 6px; }
.label-tissue-key .tissue-key-item { white-space: normal; }
.tissue-key-dot { display: inline-block; width: 9px; height: 9px; border-radius: 50%; margin-right: 2px; vertical-align: -1px; }
.tissue-key-dot.is-bead { width: 8px; height: 8px; box-shadow: 0 0 0 1.5px var(--fg); }
.label-tissue-door { pointer-events: auto; display: flex; flex-wrap: wrap; justify-content: flex-end; align-items: center; gap: 4px 10px; width: max-content; white-space: normal; }
/* A multiple of the threshold is written as the note writes it ("x2/2", "x2", "2 x2"): the page's font would draw a letter
   x between two numbers as a multiplication sign ("2 ×2"), so its contextual forms are off wherever the tissue writes one:
   its names on the picture, the whole of its card (the record's own lines and the switch's caption among them) and the
   panel of one of its cells. */
[class*="label-tissue"], .view:has(.tissue-intro), .tissue-slots, .tissue-walk, .tissue-switch, .tissue-intro, cells-panel:has(.tissue-switch) { font-variant-ligatures: no-contextual; }
/* On a wide window the tissue's long heading folds to one line in its card (in full under the pointer), so that "What you
   are looking at" comes up nearer the card's fold; the picture's head line and the list's row name it too. */
@media (min-width: 760px) {
  .view:has(.tissue-intro) > .card-title { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .view:has(.tissue-intro) > .card-title:hover { white-space: normal; }
}
/* The note's question, the line's head line on the picture, with its source as the card gives it. */
.label-tissue-question { font-size: 13px; font-weight: 600; line-height: 1.35; color: var(--fg); white-space: normal; width: max-content; text-align: left; padding: 2px 6px; border-radius: 6px; background: color-mix(in srgb, var(--bg) 85%, transparent); pointer-events: auto; }
.label-tissue-question .tissue-intro-source { font-weight: 400; font-size: 11.5px; color: var(--accent); }
/* The line's standing on its picture, where the bar's stamp may not show it. */
.label-tissue-door .tissue-standing { font-size: 12.5px; font-weight: 600; color: var(--fg); background: color-mix(in srgb, var(--bg) 90%, transparent); border: 1px solid var(--line); border-radius: 8px; padding: 4px 10px; }
.label-tissue-door .tissue-door-button { margin: 0; min-height: 32px; padding: 4px 12px; font-size: 12.5px; }
.label-tissue-door .tissue-walk-restore { margin: 0; min-height: 32px; padding: 4px 12px; font-size: 12.5px; }
.tissue-door-button { color: var(--bg-raised); background: var(--accent); border-color: var(--accent); font-weight: 600; }
`;
