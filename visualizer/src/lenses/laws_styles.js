// The Laws library's legend swatches: the page's legend draws a swatch as
// <span class="swatch swatch-{id}"> (ui/dom.js statusSwatch), so each of the view's marks
// (laws.js MARKS) has a rule here, drawn as the mark is drawn in the room. None of them is
// dashed, outlined in a status colour or coloured by a status: those are the page's statuses.

export const LAWS_CSS = `
.swatch-laws-main { background: var(--ghost); }
.swatch-laws-candidate { background: linear-gradient(90deg, var(--fg) 0 32%, var(--ghost) 32%); }
.swatch-laws-design { background: color-mix(in srgb, var(--plate) 45%, transparent); box-shadow: inset 0 0 0 1.5px var(--edge); }
.swatch-laws-older { background: var(--ghost); width: 8px; margin: 0 2px; }
.swatch-laws-height { background: repeating-linear-gradient(0deg, var(--ghost) 0 2px, transparent 2px 4px); }
.swatch-laws-rack { background: var(--plate); box-shadow: inset 0 0 0 2px var(--plate-edge); }
.swatch-laws-case { background: var(--plate-edge); height: 7px; vertical-align: 1px; }
.swatch-laws-slot { background: linear-gradient(var(--ghost), var(--ghost)) center / 8px 5px no-repeat, var(--plate); box-shadow: inset 0 0 0 1px var(--plate-edge); }
.swatch-laws-block { background: linear-gradient(var(--plate-edge), var(--plate-edge)) center 2px / 12px 4px no-repeat, var(--plate); }
.swatch-laws-next { background: color-mix(in srgb, var(--edge) 55%, transparent); }
.swatch-laws-found { background: linear-gradient(90deg, var(--ghost) 0 50%, color-mix(in srgb, var(--ghost) 30%, var(--bg)) 50%); }
.swatch-laws-empty { background: color-mix(in srgb, var(--ghost) 25%, transparent); }
.swatch-laws-chosen { background: var(--accent); box-shadow: 0 0 6px var(--accent); }
.swatch-laws-room { background: var(--plate); box-shadow: inset 0 0 0 1px var(--plate-edge); }
`;
