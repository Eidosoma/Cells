// Styles for everything inside <cells-viewer>. Colours and fonts come from the page's
// tokens (see page.css); this sheet defines none of its own.

export const css = /* css */ `
:host { display: block; position: relative; overflow: hidden; color: var(--fg); font-family: var(--font-body); font-size: 14px; line-height: 1.45; }
* { box-sizing: border-box; }
button { font: inherit; color: inherit; background: none; border: 0; padding: 0; cursor: pointer; }
button:focus-visible, a:focus-visible, input:focus-visible, canvas:focus-visible, summary:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
[hidden] { display: none !important; }
h2, h3, h4, p, ul, dl, dd { margin: 0; }
ul { padding: 0; list-style: none; }

.stage { position: absolute; inset: 0; background: radial-gradient(ellipse 75% 70% at 50% 46%, var(--bg-glow), var(--bg) 78%); }
canvas { display: block; width: 100%; height: 100%; outline-offset: -4px; }
.labels { position: absolute; inset: 0; pointer-events: none; overflow: hidden; }

/* ---------------------------------------------------------------- labels */
.label { position: absolute; left: 0; top: 0; white-space: nowrap; pointer-events: auto; touch-action: none; user-select: none; will-change: transform; transition: opacity .16s ease; }
.labels .label.is-off { opacity: 0; pointer-events: none; }
.label-part { font-size: 11.5px; font-weight: 500; line-height: 1.2; padding: 2px 6px; border-radius: 5px; color: var(--fg); background: color-mix(in srgb, var(--bg) 80%, transparent); }
.label-part::after { content: ""; position: absolute; left: 50%; top: 100%; width: 1px; height: 8px; background: var(--muted); opacity: .7; }
.label-part:hover { background: var(--bg-raised); box-shadow: 0 0 0 1px var(--line); }
.label-part.is-dim { opacity: .38; }
.label-part.is-focus { background: var(--fg); color: var(--bg); font-weight: 600; opacity: 1; }
.label-layer { font-family: var(--font-display); font-size: 12px; font-weight: 600; letter-spacing: .07em; text-transform: uppercase; color: var(--muted); pointer-events: none; }
.label-scale { font-family: var(--font-display); font-size: 13px; font-weight: 600; color: var(--fg); padding: 3px 9px; border-radius: 999px; border: 1px dashed var(--ghost); background: color-mix(in srgb, var(--bg) 82%, transparent); }
.label-note { font-size: 11px; color: var(--muted); font-style: italic; pointer-events: none; }

/* ---------------------------------------------------------------- top bar */
.bar { position: absolute; inset: 0 0 auto 0; display: flex; flex-wrap: wrap; align-items: center; gap: 10px 18px; padding-block: 12px; padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px)); pointer-events: none; }
.bar > * { pointer-events: auto; }
.brand { display: flex; align-items: baseline; gap: 9px; min-width: 0; }
.brand b { font-family: var(--font-display); font-size: 20px; font-weight: 700; letter-spacing: -.01em; }
.brand span { font-family: var(--font-display); font-size: 14px; font-weight: 500; color: var(--muted); }
.switch { display: inline-flex; padding: 3px; border-radius: 999px; background: var(--bg-raised); box-shadow: 0 0 0 1px var(--line); }
.switch button { padding: 6px 14px; border-radius: 999px; font-weight: 500; color: var(--muted); }
.switch button[aria-pressed="true"] { background: var(--fg); color: var(--bg); }
.bar-end { margin-left: auto; display: flex; align-items: center; gap: 12px; min-width: 0; }
.stamp { font-size: 12px; color: var(--muted); font-variant-numeric: tabular-nums; white-space: nowrap; }
.pill-button { padding: 6px 13px; border-radius: 999px; background: var(--bg-raised); box-shadow: 0 0 0 1px var(--line); font-weight: 500; }
.pill-button[aria-pressed="true"] { background: var(--fg); color: var(--bg); }

/* ---------------------------------------------------------------- cards */
.card { background: color-mix(in srgb, var(--bg-raised) 94%, transparent); box-shadow: 0 0 0 1px var(--line), 0 10px 30px -18px rgb(0 0 0 / .45); border-radius: 12px; backdrop-filter: blur(8px); }

cells-legend { position: absolute; left: max(16px, env(safe-area-inset-left, 0px)); bottom: calc(16px + env(safe-area-inset-bottom, 0px)); width: 236px; padding: 6px; }
.legend-toggle { display: none; width: 100%; justify-content: space-between; align-items: center; padding: 6px 8px; font-family: var(--font-display); font-weight: 600; }
.chevron { width: 8px; height: 8px; border-right: 2px solid currentColor; border-bottom: 2px solid currentColor; transform: rotate(-135deg); transition: transform .15s; }
.is-open .chevron { transform: rotate(45deg); }
.legend-body { display: grid; gap: 1px; }
.legend-item { display: grid; grid-template-columns: 14px 1fr auto; align-items: center; gap: 9px; padding: 5px 8px; border-radius: 7px; text-align: left; }
.legend-item:hover { background: color-mix(in srgb, var(--fg) 7%, transparent); }
.legend-item.is-on { background: color-mix(in srgb, var(--fg) 12%, transparent); }
.legend-item.is-empty { opacity: .45; }
.legend-count { color: var(--muted); font-size: 12px; font-variant-numeric: tabular-nums; }
.legend-title { font-family: var(--font-display); font-size: 11px; font-weight: 600; letter-spacing: .07em; text-transform: uppercase; color: var(--muted); padding: 8px 8px 3px; border-top: 1px solid var(--line); margin-top: 4px; }
.legend-group { grid-template-columns: 14px 1fr; }
.legend-radio { width: 10px; height: 10px; border-radius: 50%; border: 1.5px solid var(--muted); justify-self: center; }
.legend-group.is-on .legend-radio { background: var(--fg); border-color: var(--fg); }
.legend-note { display: grid; grid-template-columns: 14px 1fr; gap: 9px; align-items: start; padding: 6px 8px 4px; font-size: 12px; color: var(--muted); border-top: 1px solid var(--line); margin-top: 4px; }

/* How each status is drawn, repeated small. */
.swatch { display: inline-block; width: 12px; height: 12px; border-radius: 3px; flex: none; position: relative; vertical-align: -1px; }
.swatch-qualified { background: var(--st-qualified); }
.swatch-landed { background: var(--st-landed); }
.swatch-established { background: var(--st-established); }
.swatch-external { background: var(--st-external); border-radius: 50%; }
.swatch-unstated { background: var(--st-unstated); border-radius: 50%; }
.swatch-designed { background: color-mix(in srgb, var(--st-designed) 32%, transparent); box-shadow: inset 0 0 0 1.5px var(--st-designed); }
.swatch-planned { border: 1.5px dashed var(--ghost); }
.swatch-illustration { border: 1.5px solid var(--ghost); border-radius: 50%; margin-top: 3px; }
.swatch-failed { background: var(--st-failed); }
.swatch-failed::before, .swatch-failed::after { content: ""; position: absolute; left: 50%; top: 50%; width: 10px; height: 1.5px; background: var(--bg-raised); transform: translate(-50%, -50%) rotate(45deg); }
.swatch-failed::after { transform: translate(-50%, -50%) rotate(-45deg); }

/* ---------------------------------------------------------------- panel */
cells-panel { position: absolute; top: 64px; right: max(16px, env(safe-area-inset-right, 0px)); bottom: calc(16px + env(safe-area-inset-bottom, 0px)); width: min(360px, calc(100% - 32px)); display: flex; flex-direction: column; overflow: hidden; }
.panel-head { display: flex; justify-content: space-between; gap: 12px; align-items: start; padding: 16px 16px 10px; }
.eyebrow { font-size: 11px; font-weight: 600; letter-spacing: .07em; text-transform: uppercase; color: var(--muted); }
.panel-head h2 { font-family: var(--font-display); font-size: 21px; line-height: 1.2; font-weight: 600; text-wrap: balance; margin-top: 2px; }
.icon-button { width: 30px; height: 30px; flex: none; border-radius: 50%; font-size: 20px; line-height: 1; color: var(--muted); }
.icon-button:hover { background: color-mix(in srgb, var(--fg) 9%, transparent); color: var(--fg); }
.chips { display: flex; flex-wrap: wrap; gap: 6px; padding: 0 16px 12px; }
.chip { display: inline-flex; align-items: center; gap: 6px; padding: 3px 9px; border-radius: 999px; font-size: 12px; font-weight: 500; box-shadow: inset 0 0 0 1px var(--line); }
.chip-plain { color: var(--muted); }
.panel-body { overflow-y: auto; padding: 0 16px 18px; display: grid; gap: 12px; align-content: start; min-height: 0; }
.panel-plain { font-size: 15px; line-height: 1.5; }
.panel-note { font-size: 13px; color: var(--muted); padding-left: 10px; border-left: 2px solid var(--line); }
.panel-detail { font-size: 12.5px; color: var(--muted); font-family: var(--font-mono); line-height: 1.5; overflow-wrap: anywhere; }
.panel-body h3 { font-family: var(--font-display); font-size: 13px; font-weight: 600; letter-spacing: .05em; text-transform: uppercase; color: var(--muted); padding-top: 10px; border-top: 1px solid var(--line); }
.panel-body h4 { font-size: 12.5px; font-weight: 600; margin-bottom: 3px; }
.facts { display: grid; grid-template-columns: minmax(0, 11em) minmax(0, 1fr); gap: 4px 12px; font-size: 12.5px; }
.facts dt { color: var(--muted); }
.facts dd { overflow-wrap: anywhere; font-variant-numeric: tabular-nums; }
.panel-list ul { display: grid; gap: 2px; font-size: 13px; }
.panel-list li { overflow-wrap: anywhere; }
.quiet { color: var(--muted); font-weight: 400; font-size: 12px; }
.link-button { display: inline-flex; align-items: baseline; gap: 6px; text-align: left; border-radius: 4px; text-decoration: underline; text-decoration-color: var(--line); text-underline-offset: 3px; }
.link-button:hover { text-decoration-color: currentColor; }
details summary { cursor: pointer; font-size: 12.5px; color: var(--muted); padding: 3px 0; }
.sources { display: grid; gap: 3px; font-size: 12.5px; }
.sources a { color: var(--accent); overflow-wrap: anywhere; }

/* ---------------------------------------------------------------- index */
cells-index { position: absolute; top: 64px; left: max(16px, env(safe-area-inset-left, 0px)); bottom: calc(16px + env(safe-area-inset-bottom, 0px)); width: min(300px, calc(100% - 32px)); display: flex; flex-direction: column; overflow: hidden; z-index: 2; }
.index-head { padding: 12px 12px 8px; }
.index-search { width: 100%; padding: 8px 11px; border-radius: 8px; border: 1px solid var(--line); background: var(--bg); color: var(--fg); font: inherit; }
.index-list { overflow-y: auto; padding: 0 8px 12px; min-height: 0; }
.index-list h3 { font-family: var(--font-display); font-size: 11.5px; font-weight: 600; letter-spacing: .07em; text-transform: uppercase; color: var(--muted); padding: 10px 6px 4px; }
.index-row { display: grid; grid-template-columns: 14px 1fr; gap: 9px; align-items: center; width: 100%; padding: 5px 6px; border-radius: 6px; text-align: left; }
.index-row:hover { background: color-mix(in srgb, var(--fg) 7%, transparent); }
.index-row.is-on { background: color-mix(in srgb, var(--fg) 13%, transparent); font-weight: 600; }
.index-name { min-width: 0; overflow-wrap: anywhere; }
.index-empty { padding: 12px 6px; color: var(--muted); }

/* ---------------------------------------------------------------- notes on the stage */
.caveat { position: absolute; left: 50%; transform: translateX(-50%); bottom: calc(14px + env(safe-area-inset-bottom, 0px)); width: min(46ch, calc(100% - 560px)); text-align: center; font-size: 12px; color: var(--muted); text-wrap: balance; pointer-events: none; padding: 5px 12px; border-radius: 10px; background: color-mix(in srgb, var(--bg) 82%, transparent); }
.hint { position: absolute; left: 50%; transform: translateX(-50%); bottom: calc(18px + env(safe-area-inset-bottom, 0px)); font-size: 12px; color: var(--muted); pointer-events: none; transition: opacity .4s; white-space: nowrap; }
.hint.is-off { opacity: 0; }
.rail { position: absolute; right: max(16px, env(safe-area-inset-right, 0px)); top: 50%; transform: translateY(-50%); display: grid; gap: 2px; padding: 6px; }
.rail button { display: grid; grid-template-columns: 12px auto; align-items: center; gap: 9px; padding: 6px 10px 6px 8px; border-radius: 8px; text-align: left; font-weight: 500; color: var(--muted); }
.rail button::before { content: ""; width: 8px; height: 8px; border-radius: 50%; border: 2px solid currentColor; justify-self: center; }
.rail button:hover { background: color-mix(in srgb, var(--fg) 7%, transparent); }
.rail button[aria-pressed="true"] { color: var(--fg); background: color-mix(in srgb, var(--fg) 10%, transparent); }
.rail button[aria-pressed="true"]::before { background: currentColor; }
.rail .rail-title { font-family: var(--font-display); font-size: 11px; font-weight: 600; letter-spacing: .07em; text-transform: uppercase; color: var(--muted); padding: 4px 8px 2px; }
.has-panel .rail { display: none; }

.fallback { position: absolute; inset: 64px 0 0 0; padding-block: 16px; padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px)); color: var(--muted); }

/* ---------------------------------------------------------------- narrow screens */
@media (max-width: 760px) {
  .brand span, .stamp { display: none; }
  .bar { gap: 8px 10px; padding-block: 10px; }
  .switch button { padding: 6px 11px; }
  .hint { bottom: calc(64px + env(safe-area-inset-bottom, 0px)); }
  cells-legend { width: auto; right: auto; max-width: calc(100% - 32px); }
  .legend-toggle { display: flex; gap: 14px; }
  cells-legend:not(.is-open) .legend-body { display: none; }
  cells-panel { top: auto; left: 0; right: 0; bottom: 0; width: 100%; max-height: 56%; border-radius: 16px 16px 0 0; padding-bottom: env(safe-area-inset-bottom, 0px); z-index: 3; }
  cells-index { top: 56px; }
  .caveat { width: calc(100% - 32px); bottom: calc(58px + env(safe-area-inset-bottom, 0px)); }
  .rail { top: 104px; transform: none; right: max(10px, env(safe-area-inset-right, 0px)); }
  .rail .rail-title { display: none; }
  .rail button { padding: 5px 8px 5px 6px; font-size: 12.5px; }
  .has-panel cells-legend, .has-panel .caveat { display: none; }
}
@media (prefers-reduced-motion: reduce) {
  .label, .hint, .chevron { transition: none; }
}
.is-still .label, .is-still .hint, .is-still .chevron { transition: none; }
`;
