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
.label-part.is-callout::after { display: none; }
.label-unit { font-size: 10.5px; padding: 1px 5px; }
.label-unit::after { height: 6px; }
.label-part .swatch { width: 8px; height: 8px; margin-right: 6px; vertical-align: 0; }
.label-part .swatch-failed::before, .label-part .swatch-failed::after { width: 7px; }
.leaders { position: absolute; inset: 0; width: 100%; height: 100%; overflow: visible; pointer-events: none; }
.leaders path { fill: none; stroke: var(--muted); stroke-width: 1; opacity: .7; }
.leaders circle { fill: var(--bg-raised); stroke: var(--fg); stroke-width: 1.2; }
.leaders .lead-off { display: none; }
.leaders .lead-dim { opacity: .2; }
.leaders path.lead-focus { stroke: var(--fg); stroke-width: 1.6; opacity: 1; }
.leaders circle.lead-focus { fill: var(--fg); }
.label-part:hover { background: var(--bg-raised); box-shadow: 0 0 0 1px var(--line); }
.label-part.is-dim { opacity: .38; }
.label-part.is-focus { background: var(--fg); color: var(--bg); font-weight: 600; opacity: 1; }
.label-layer { font-family: var(--font-display); font-size: 12px; font-weight: 600; letter-spacing: .07em; text-transform: uppercase; color: var(--muted); pointer-events: none; }
.label-district { font-size: 11px; color: var(--fg); padding: 1px 7px; border-radius: 5px; background: color-mix(in srgb, var(--bg) 58%, transparent); }
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
.switch .short { display: none; }
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
.legend-group { grid-template-columns: 14px 1fr auto; }
.legend-unit { float: right; font-weight: 500; letter-spacing: 0; text-transform: none; }
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
/* The protein atlas's mappings: a named protein, a candidate, a generic law. */
.swatch-map-assigned { background: var(--bio-protein); }
.swatch-map-candidate { background: color-mix(in srgb, var(--bio-protein) 26%, transparent); box-shadow: inset 0 0 0 1.5px var(--bio-protein); }
.swatch-map-generic { background: var(--atlas-generic); border-radius: 50%; }
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
.items ul { gap: 11px; }
.item-head { display: flex; flex-wrap: wrap; align-items: baseline; gap: 3px 8px; }
.item-label { font-weight: 600; overflow-wrap: anywhere; }
.item-label.code { font-family: var(--font-mono); font-size: 12px; font-weight: 500; }
.tag { font-size: 11px; line-height: 1.5; padding: 0 7px; border-radius: 999px; box-shadow: inset 0 0 0 1px var(--line); color: var(--muted); white-space: nowrap; }
.item-detail, .item-line, .item-note { font-size: 12.5px; color: var(--muted); margin-top: 2px; overflow-wrap: anywhere; }
.item-note { padding-left: 8px; border-left: 2px solid var(--line); }
.item-links { font-size: 12.5px; margin-top: 3px; }
.item-links a, .view details a { color: var(--accent); }
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

.view { position: absolute; left: max(16px, env(safe-area-inset-left, 0px)); top: 64px; padding: 8px 10px 9px; display: grid; gap: 6px; width: 236px; }
.seg-row { display: grid; grid-template-columns: 52px 1fr; align-items: center; gap: 8px; }
.seg-label { font-family: var(--font-display); font-size: 11px; font-weight: 600; letter-spacing: .07em; text-transform: uppercase; color: var(--muted); }
.seg { display: grid; grid-template-columns: 1fr 1fr; padding: 2px; border-radius: 8px; background: color-mix(in srgb, var(--fg) 7%, transparent); }
.seg button { padding: 4px 6px; border-radius: 6px; font-size: 12.5px; font-weight: 500; color: var(--muted); }
.seg button[aria-pressed="true"] { background: var(--bg-raised); color: var(--fg); box-shadow: 0 0 0 1px var(--line); }
.view-note { font-size: 11.5px; line-height: 1.4; color: var(--muted); }
.view-card { width: 268px; gap: 8px; padding: 11px 12px 10px; }
.card-title { font-family: var(--font-display); font-weight: 600; font-size: 14px; }
.stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
.stat b { display: block; font-family: var(--font-display); font-size: 21px; font-weight: 600; line-height: 1.1; font-variant-numeric: tabular-nums; }
.stat span { display: block; font-size: 11px; line-height: 1.25; color: var(--muted); }
.card-text { font-size: 11.5px; line-height: 1.4; color: var(--muted); }
.view details { font-size: 11.5px; line-height: 1.4; }
.view details ul { display: grid; gap: 5px; margin-top: 5px; color: var(--muted); max-height: 190px; overflow-y: auto; }
.scalebar { position: absolute; right: max(16px, env(safe-area-inset-right, 0px)); bottom: calc(18px + env(safe-area-inset-bottom, 0px)); display: grid; justify-items: end; gap: 4px; pointer-events: none; }
.scalebar-line { height: 5px; border: 1.5px solid var(--fg); border-top: 0; }
.scalebar-text { font-size: 12px; font-variant-numeric: tabular-nums; color: var(--fg); background: color-mix(in srgb, var(--bg) 78%, transparent); padding: 1px 6px; border-radius: 5px; }
.has-panel .scalebar { right: calc(max(16px, env(safe-area-inset-right, 0px)) + 376px); bottom: calc(58px + env(safe-area-inset-bottom, 0px)); }
/* The resting look's switch and its few words, over the scale bar: there they take no room from the labels' column.
   Like the scale bar they let the pointer through to the picture; the switch alone takes it. */
.look-box { display: grid; justify-items: end; gap: 4px; margin-bottom: 6px; }
.look-switch { padding: 3px 3px 3px 10px; pointer-events: auto; }
.look-switch .seg-row { grid-template-columns: auto 124px; }
.look-note { max-width: 250px; font-size: 11.5px; line-height: 1.4; text-align: right; color: var(--muted); background: color-mix(in srgb, var(--bg) 78%, transparent); padding: 1px 6px; border-radius: 5px; }
.fallback { position: absolute; inset: 64px 0 0 0; padding-block: 16px; padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px)); color: var(--muted); }

/* ---------------------------------------------------------------- replay: the run's card */
.run-card { width: 268px; gap: 7px; }
.view { overflow-y: auto; }
.run-class-note summary { font-size: 11.5px; }
.run-card .eyebrow { margin-bottom: -6px; }
.run-lead { font-size: 12.5px; line-height: 1.4; color: var(--fg); }
.runs { display: grid; gap: 2px; }
.runs .seg-label { padding: 0 0 2px; }
.run-row { display: grid; gap: 1px; text-align: left; padding: 5px 8px; border-radius: 7px; box-shadow: inset 0 0 0 1px var(--line); }
.run-row + .run-row { margin-top: 3px; }
.run-row:hover { background: color-mix(in srgb, var(--fg) 6%, transparent); }
.run-row[aria-pressed="true"] { background: color-mix(in srgb, var(--fg) 10%, transparent); box-shadow: inset 0 0 0 1.5px var(--fg); }
.run-name { font-family: var(--font-mono); font-size: 11.5px; overflow-wrap: anywhere; }
.run-sub { font-size: 11.5px; color: var(--muted); }
.run-select { width: 100%; padding: 6px 8px; border-radius: 7px; border: 1px solid var(--line); background: var(--bg); color: var(--fg); font: inherit; font-size: 12.5px; }
.run-class { display: grid; gap: 4px; }
.run-class-line { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.chip-strong { font-weight: 600; box-shadow: inset 0 0 0 1.5px var(--fg); }
/* A fact from the record: a mark and its words. The mark's colour repeats what the sign says. */
.mark { display: inline-grid; place-items: center; width: 15px; height: 15px; border-radius: 50%; flex: none; background: var(--muted); }
.mark svg { width: 15px; height: 15px; fill: none; stroke: var(--bg-raised); stroke-width: 1.9; stroke-linecap: round; stroke-linejoin: round; }
.mark-yes { background: var(--st-qualified); }
.mark-no { background: var(--st-failed); }
.mark-mixed { background: var(--st-designed); }
.fact { display: inline-flex; align-items: center; gap: 5px; font-size: 12px; font-weight: 500; }
.experiments { display: grid; gap: 3px; }
.exp-row { display: grid; gap: 2px; text-align: left; padding: 5px 8px; border-radius: 7px; box-shadow: inset 0 0 0 1px var(--line); }
.exp-row:hover { background: color-mix(in srgb, var(--fg) 6%, transparent); }
.exp-row[aria-pressed="true"] { background: color-mix(in srgb, var(--fg) 10%, transparent); box-shadow: inset 0 0 0 1.5px var(--fg); }
.exp-name { font-family: var(--font-display); font-weight: 600; font-size: 13px; }
.exp-found { display: flex; flex-wrap: wrap; gap: 3px 10px; color: var(--muted); }
.exp-found .fact { font-size: 11.5px; font-weight: 400; }
.found { display: grid; gap: 4px; }
.found-facts { display: flex; flex-wrap: wrap; gap: 4px 12px; }
.run-ended { display: flex; align-items: center; gap: 6px; }
.legend-keys { padding: 2px 8px 4px; font-size: 12px; }
.legend-keys summary { color: var(--muted); padding: 2px 0; }
.legend-key-note { color: var(--muted); }
.run-actions { display: flex; gap: 8px; }
.pill-small { padding: 4px 11px; font-size: 12.5px; box-shadow: inset 0 0 0 1px var(--line); background: none; }
.pill-small:hover { background: color-mix(in srgb, var(--fg) 7%, transparent); }
.run-card details { font-size: 11.5px; }
.run-card details p { margin-top: 4px; }
.run-card .seg-row { grid-template-columns: 52px 1fr; }

/* ---------------------------------------------------------------- replay: the legend's scale and keys */
.legend-scale-title { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; padding: 4px 8px 6px; font-size: 12.5px; font-weight: 600; }
.legend-scale-title .legend-unit { float: none; color: var(--muted); font-size: 12px; }
.ramp { position: relative; height: 12px; margin: 0 8px; border-radius: 3px; }
.ramp-mark { position: absolute; top: -3px; bottom: -3px; width: 2px; margin-left: -1px; background: var(--fg); box-shadow: 0 0 0 1px var(--bg-raised); }
.ramp-ticks { position: relative; height: 17px; margin: 3px 8px 3px; font-size: 11.5px; color: var(--muted); font-variant-numeric: tabular-nums; }
.ramp-ticks span { position: absolute; transform: translateX(-50%); white-space: nowrap; }
.ramp-ticks span:first-child { transform: none; }
.ramp-ticks span:last-child { transform: translateX(-100%); }
.ramp-steps { display: flex; flex-wrap: wrap; gap: 4px 12px; padding: 0 8px 6px; font-size: 12px; color: var(--muted); font-variant-numeric: tabular-nums; }
.ramp-step { display: inline-flex; align-items: center; gap: 5px; }
.ramp-step i { display: inline-block; width: 16px; height: 12px; border-radius: 3px; }
.legend-key { display: grid; grid-template-columns: 22px 1fr; gap: 8px; align-items: start; padding: 3px 8px; font-size: 12px; line-height: 1.35; color: var(--muted); }
.key { position: relative; display: inline-block; width: 20px; height: 12px; margin-top: 2px; }
.key-seam { background: linear-gradient(to right, var(--seq-1) 0 8px, var(--fg) 8px 12px, var(--seq-1) 12px); border-radius: 2px; }
.key-frame { height: 10px; border: 2px solid var(--fg); border-radius: 3px; }
.key-ring { width: 12px; height: 12px; margin-left: 4px; border: 2px solid var(--fg); border-radius: 50%; }
.key-mark::before { content: ""; position: absolute; left: 9px; top: -1px; bottom: -1px; width: 2px; background: var(--fg); }
.legend-note-plain { grid-template-columns: 1fr; }
/* The switch for quantity layers: a row for each visual channel. */
.legend-layers { padding-bottom: 2px; }
.layer-row { display: grid; grid-template-columns: minmax(0, 1fr); gap: 2px; padding: 3px 8px; }
.layer-channel { font-size: 11.5px; color: var(--muted); }
.layer-seg button { padding: 3px 2px; font-size: 11.5px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.layer-seg button[aria-busy="true"] { font-style: italic; }
.layer-cannot, .layer-problem { padding: 2px 8px; font-size: 12px; line-height: 1.35; color: var(--muted); }
.layer-cannot-name { color: var(--fg); font-weight: 500; }
.layer-more { padding: 3px 8px 2px; font-size: 12px; }
.key-wedge, .key-wedge-hollow { width: 14px; height: 12px; margin-left: 3px; background: var(--fg); clip-path: polygon(0 0, 100% 50%, 0 100%); }
.key-wedge-hollow::after { content: ""; position: absolute; inset: 0; background: var(--bg-raised); clip-path: polygon(16% 26%, 68% 50%, 16% 74%); }
.key-break { width: 12px; height: 12px; margin-left: 4px; background: linear-gradient(to right, var(--fg) 0 4px, transparent 4px 8px, var(--fg) 8px 12px); }
.key-level { height: 3px; margin-top: 7px; background: var(--fg); border-radius: 2px; }
.layer-hint { padding: 3px 8px; font-size: 12px; line-height: 1.35; color: var(--fg); }
.experiments + .eyebrow { margin-top: 10px; }
.legend-key-chips { grid-template-columns: 1fr; }
.key-chips { display: inline-flex; gap: 9px; margin-right: 8px; color: var(--fg); font-weight: 500; }
.key-chip i { display: inline-block; width: 9px; height: 9px; margin-right: 4px; border-radius: 2px; }
.key-arrow-hollow, .key-arrow-faint, .key-arrow-solid { width: 12px; height: 13px; margin-left: 4px; background: var(--fg); clip-path: polygon(50% 0, 100% 46%, 68% 46%, 68% 100%, 32% 100%, 32% 46%, 0 46%); }
.key-arrow-faint { opacity: .45; }
.key-arrow-hollow::after { content: ""; position: absolute; inset: 0; background: var(--bg-raised); clip-path: polygon(50% 20%, 76% 37%, 57% 37%, 57% 100%, 43% 100%, 43% 37%, 24% 37%); }
.key-charges { width: 20px; height: 13px; }
.key-charges::before, .key-charges::after { position: absolute; top: -3px; font-size: 13px; font-weight: 600; line-height: 1.3; color: var(--fg); }
.key-charges::before { content: "+"; left: 1px; }
.key-charges::after { content: "\\2212"; left: 11px; }
.key-bead { width: 9px; height: 9px; margin: 3px 0 0 6px; border-radius: 50%; background: var(--fg); }
.key-time { width: 11px; height: 11px; margin: 2px 0 0 5px; border: 1.5px solid var(--fg); border-radius: 50%; }
.key-time::after { content: ""; position: absolute; left: 4px; top: 1px; width: 1.5px; height: 5px; background: var(--fg); }
.label-closeup { font-size: 11.5px; font-weight: 500; line-height: 1.25; color: var(--fg); pointer-events: none; text-align: center; white-space: pre-line; font-variant-numeric: tabular-nums; }
.label-closeup-ion::first-line { font-weight: 700; }
.label-closeup-number { font-size: 10.5px; color: var(--muted); }
.label-closeup-side { font-size: 10.5px; font-weight: 600; letter-spacing: .04em; text-transform: uppercase; color: var(--muted); }
.label-closeup-caption { font-size: 11px; font-weight: 400; color: var(--muted); white-space: pre-line; }
.label-closeup-caption::first-line { font-weight: 600; color: var(--fg); }

/* ---------------------------------------------------------------- replay: the timeline */
cells-timeline { position: absolute; left: 268px; right: 244px; bottom: calc(16px + env(safe-area-inset-bottom, 0px)); max-width: 780px; margin-inline: auto; display: grid; grid-template-columns: auto minmax(0, 1fr) auto; align-items: center; gap: 12px; padding: 7px 12px 8px; }
.has-panel cells-timeline { right: 392px; }
.tl-play { display: grid; place-items: center; width: 38px; height: 38px; border-radius: 50%; background: var(--fg); color: var(--bg); }
.tl-play:hover { background: color-mix(in srgb, var(--fg) 84%, var(--bg)); }
.tl-play svg { width: 20px; height: 20px; fill: currentColor; }
.tl-body { display: grid; gap: 2px; min-width: 0; }
.tl-track { position: relative; height: 32px; }
.tl-rail { position: absolute; left: 0; right: 0; top: 17px; height: 4px; border-radius: 2px; background: color-mix(in srgb, var(--fg) 15%, transparent); overflow: hidden; }
.tl-fill { width: 0; height: 100%; background: var(--accent); }
.tl-marks { position: absolute; left: 0; top: 7px; width: 100%; height: 24px; overflow: visible; pointer-events: none; }
.tl-tick { stroke: var(--muted); stroke-width: 1; vector-effect: non-scaling-stroke; }
.tl-judged { stroke: var(--fg); stroke-width: 1.5; vector-effect: non-scaling-stroke; }
.tl-invalid { fill: var(--st-unstated); }
.tl-flag { position: absolute; top: -3px; transform: translateX(-50%); padding: 0 4px; border-radius: 4px; font-size: 10.5px; font-weight: 600; letter-spacing: .03em; color: var(--fg); background: color-mix(in srgb, var(--bg-raised) 90%, transparent); pointer-events: none; white-space: nowrap; }
.tl-range { position: absolute; left: -7px; top: 7px; width: calc(100% + 14px); height: 24px; margin: 0; padding: 0; -webkit-appearance: none; appearance: none; background: transparent; cursor: pointer; }
.tl-range::-webkit-slider-runnable-track { height: 24px; background: transparent; }
.tl-range::-webkit-slider-thumb { -webkit-appearance: none; appearance: none; width: 14px; height: 14px; margin-top: 5px; border-radius: 50%; background: var(--fg); border: 2px solid var(--bg-raised); box-shadow: 0 0 0 1px var(--fg); }
.tl-range::-moz-range-track { height: 24px; background: transparent; }
.tl-range::-moz-range-thumb { width: 10px; height: 10px; border-radius: 50%; background: var(--fg); border: 2px solid var(--bg-raised); box-shadow: 0 0 0 1px var(--fg); }
.tl-read { font-size: 12px; color: var(--muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-variant-numeric: tabular-nums; }
.tl-read b { color: var(--fg); font-weight: 600; }
.tl-speed { min-width: 48px; padding: 6px 9px; border-radius: 999px; box-shadow: inset 0 0 0 1px var(--line); font-size: 12.5px; font-weight: 600; font-variant-numeric: tabular-nums; }
.tl-speed:hover { background: color-mix(in srgb, var(--fg) 7%, transparent); }
.has-timeline.has-panel .scalebar { bottom: calc(96px + env(safe-area-inset-bottom, 0px)); }
.label-read { font-variant-numeric: tabular-nums; pointer-events: none; }
.label-region { font-style: normal; font-weight: 600; color: var(--fg); padding: 1px 7px; border-radius: 5px; background: color-mix(in srgb, var(--bg) 66%, transparent); }

/* ---------------------------------------------------------------- replay: a record over the run, in the panel */
cells-trace { display: grid; gap: 4px; }
.trace-title { font-size: 12.5px; font-weight: 600; }
.trace-read { font-size: 12.5px; color: var(--muted); font-variant-numeric: tabular-nums; }
.trace-value { font-family: var(--font-display); font-size: 19px; font-weight: 600; color: var(--fg); }
.trace-plot { display: block; width: 100%; height: auto; border-radius: 6px; cursor: crosshair; touch-action: pan-y; }
.trace-grid { stroke: var(--line); stroke-width: 1; }
.trace-tick { fill: var(--muted); font-family: var(--font-body); font-size: 10px; font-variant-numeric: tabular-nums; }
.trace-flag { fill: var(--fg); font-weight: 600; }
.trace-line { fill: none; stroke: var(--accent); stroke-width: 2; stroke-linejoin: round; stroke-linecap: round; }
.trace-judged { stroke: var(--fg); stroke-width: 1; opacity: .75; }
.trace-level { stroke: var(--ghost); stroke-width: 1; }
.trace-event { fill: var(--fg); }
.trace-head { stroke: var(--fg); stroke-width: 1.5; }
.trace-dot { fill: var(--accent); stroke: var(--bg-raised); stroke-width: 2; }
.trace-cross { stroke: var(--muted); stroke-width: 1; }
.trace-dot-cross { fill: var(--bg-raised); stroke: var(--accent); stroke-width: 2; }
.trace-keys { display: flex; flex-wrap: wrap; gap: 3px 14px; font-size: 11.5px; color: var(--muted); }
.trace-keys span { display: inline-flex; align-items: center; gap: 6px; }
.trace-key { display: inline-block; flex: none; }
.trace-key-event { width: 0; height: 0; border-left: 4px solid transparent; border-right: 4px solid transparent; border-bottom: 7px solid var(--fg); }
.trace-key-level { width: 14px; height: 0; border-top: 1px solid var(--ghost); }
.trace-scroll { max-height: 190px; overflow-y: auto; margin-top: 4px; }
.trace-table table { width: 100%; border-collapse: collapse; font-size: 12px; font-variant-numeric: tabular-nums; }
.trace-table th, .trace-table td { padding: 2px 8px 2px 0; text-align: left; border-bottom: 1px solid var(--line); font-weight: 400; }
.trace-table th { color: var(--muted); position: sticky; top: 0; background: var(--bg-raised); }
.trace-table tr.is-event td { font-weight: 600; }
.panel-more ul { display: grid; gap: 6px; margin-top: 6px; font-size: 12.5px; color: var(--muted); }

/* ---------------------------------------------------------------- protein atlas: one species' side */
/* The species switch: in the bar on a wide window, at the head of a card on a narrow one. */
.species { display: inline-flex; align-items: center; gap: 8px; min-width: 0; }
.species-label { font-family: var(--font-display); font-size: 11px; font-weight: 600; letter-spacing: .07em; text-transform: uppercase; color: var(--muted); }
/* The switch is a dropdown: a pill that names the species in view, and a list of the page's own under it. */
.species-pick { display: inline-flex; align-items: center; gap: 9px; padding: 6px 12px 6px 14px; border-radius: 999px; background: var(--bg-raised); box-shadow: 0 0 0 1px var(--line); font-size: 13px; font-weight: 500; white-space: nowrap; }
.species-pick:hover, .species-pick[aria-expanded="true"] { background: color-mix(in srgb, var(--fg) 8%, var(--bg-raised)); }
/* Every species' name lies in the pill, one over the other: its width is that of the longest and does not change with the species. */
.species-pick-name { display: inline-grid; text-align: left; }
.species-pick-name > * { grid-area: 1 / 1; }
.species-pick-name > [aria-hidden="true"] { visibility: hidden; }
.species-pick-caret { flex: none; width: 7px; height: 7px; margin-top: -4px; border-right: 1.5px solid currentColor; border-bottom: 1.5px solid currentColor; transform: rotate(45deg); opacity: .7; }
.species-pick[aria-expanded="true"] .species-pick-caret { margin-top: 3px; transform: rotate(225deg); }
.seg-species .species-pick { width: 100%; justify-content: space-between; padding: 5px 10px 5px 11px; border-radius: 8px; font-size: 12.5px; }
.species-veil { position: absolute; inset: 0; z-index: 5; }
.species-list { position: absolute; z-index: 6; display: grid; align-content: start; gap: 2px; padding: 6px; overflow-y: auto; overscroll-behavior: contain; border-radius: 12px; background: var(--bg-raised); box-shadow: 0 0 0 1px var(--line), 0 16px 36px -16px rgb(0 0 0 / .5); }
.species-group { display: grid; gap: 2px; }
.species-group + .species-group { margin-top: 4px; padding-top: 6px; border-top: 1px solid var(--line); }
.species-group-name { padding: 3px 9px 2px; font-family: var(--font-display); font-size: 10.5px; font-weight: 600; letter-spacing: .07em; text-transform: uppercase; color: var(--muted); }
/* A row: the name and what Cells models of it on one line, the organism under them across the row. */
.species-option { display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: center; gap: 1px 10px; padding: 7px 9px; border-radius: 8px; cursor: pointer; }
.species-option-name { grid-column: 1; grid-row: 1; font-size: 13.5px; font-weight: 600; line-height: 1.3; }
.species-option-organism { grid-column: 1 / -1; grid-row: 2; font-size: 12px; font-style: italic; line-height: 1.3; color: var(--muted); overflow-wrap: break-word; }
.species-option-state { grid-column: 2; grid-row: 1; padding: 2px 8px; border-radius: 999px; font-size: 11px; font-weight: 500; color: var(--muted); box-shadow: inset 0 0 0 1px var(--line); white-space: nowrap; }
.species-option-state[data-state="proposed"] { color: var(--fg); box-shadow: inset 0 0 0 1.5px var(--fg); }
.species-option.is-active { background: color-mix(in srgb, var(--fg) 9%, transparent); }
/* The species in view carries a tick after its name. */
.species-option[aria-selected="true"] .species-option-name::after { content: ""; display: inline-block; width: 4px; height: 8px; margin: 0 0 1px 9px; border-right: 2px solid currentColor; border-bottom: 2px solid currentColor; transform: rotate(45deg); }
.species-state { padding: 4px 10px; border-radius: 999px; font-size: 12px; font-weight: 500; color: var(--muted); box-shadow: inset 0 0 0 1px var(--line); white-space: nowrap; }
.species-state::after { content: "›"; margin-left: 6px; opacity: .6; }
.species-state:hover { background: color-mix(in srgb, var(--fg) 7%, transparent); }
.species-state[data-state="proposed"] { color: var(--fg); box-shadow: inset 0 0 0 1.5px var(--fg); }
.species-state[aria-pressed="true"] { background: var(--fg); color: var(--bg); }
.species-line { margin: -1px 0 1px; }
.rail-note { max-width: 148px; font-size: 11.5px; line-height: 1.35; color: var(--muted); padding: 6px 8px 3px; margin-top: 2px; border-top: 1px solid var(--line); }
/* With the species switch in it, the bar stays on one line: the date gives way first. */
.with-species { flex-wrap: nowrap; }
.with-species .bar-end { flex: 0 1 auto; overflow: hidden; }
.with-species .stamp { overflow: hidden; text-overflow: ellipsis; min-width: 0; }
.with-species .switch, .with-species .species, .with-species .pill-button { flex: none; }
.with-species .brand { flex: none; white-space: nowrap; }
@media (max-width: 1340px) { .with-species .brand span { display: none; } }
@media (max-width: 1240px) { .with-species .switch .long { display: none; } .with-species .switch .short { display: inline; } }
@media (max-width: 1180px) { .with-species .stamp { display: none; } }
/* Where the words are wider than that (more species, or a fallback font), the viewer asks for the same, by measure. */
.with-species[data-tight="1"] .brand span, .with-species[data-tight="2"] .brand span { display: none; }
.with-species[data-tight="2"] .switch .long { display: none; }
.with-species[data-tight="2"] .switch .short { display: inline; }
.with-species[data-tight="2"] .stamp { display: none; }
.card-organism { font-size: 12.5px; font-style: italic; margin-top: -3px; }
/* A species file may hold a long word (a file's name, an identifier): it wraps inside the card. */
.view-card:not(.run-card) > * { min-width: 0; }
.view-card:not(.run-card) .card-text, .view-card:not(.run-card) details li { overflow-wrap: anywhere; }
.view .card-extra { gap: 9px; }
.card-extra .item-label { font-size: 12px; color: var(--fg); }
.card-extra .item-detail, .card-extra .item-line, .card-extra .item-note, .card-extra .item-links { font-size: 11.5px; }
/* What a species' atlas found, where it differs: a ring beside the unit, never the unit's form.
   An unbroken ring is another protein family; a broken ring is nothing found. */
.swatch-find-band { border: 3px solid currentColor; border-radius: 50%; }
.swatch-find-dashes { border: 2px dashed currentColor; border-radius: 50%; }
.swatch-find-faint { border: 1.5px solid color-mix(in srgb, currentColor 35%, transparent); background: color-mix(in srgb, currentColor 12%, transparent); border-radius: 50%; }
.label.is-faint { opacity: .5; }
.label-part .swatch-find-band, .label-part .swatch-find-dashes { width: 9px; height: 9px; margin-right: 4px; vertical-align: -1px; }
.label-part .swatch-find-band { border-width: 2.5px; }
.label-part .swatch-find-dashes { border-width: 1.5px; }
.legend-fold > summary { padding: 8px 8px 5px; }
.legend-fold .legend-item { width: 100%; margin-top: 1px; }
.index-row.has-sign { grid-template-columns: 14px 1fr auto; }
.panel-finding { display: grid; gap: 5px; padding: 9px 11px 10px; border-radius: 9px; box-shadow: inset 0 0 0 1px var(--line); background: color-mix(in srgb, var(--fg) 4%, transparent); }
.finding-title { font-size: 12px; font-weight: 600; }
.finding-title i { font-weight: 400; color: var(--muted); }
.finding-line { display: flex; align-items: baseline; gap: 7px; font-size: 14px; font-weight: 600; line-height: 1.35; }
.finding-line .swatch { flex: none; align-self: center; }
.finding-note { font-size: 13px; }
.finding-more, .list-note { font-size: 12px; color: var(--muted); }
.list-note { margin: -1px 0 5px; }

/* ---------------------------------------------------------------- a species' own proteins on shelves */
.seg.seg-wide button { padding: 5px 4px; font-size: 12px; line-height: 1.2; white-space: normal; text-wrap: balance; }
.card-notice { font-size: 12px; line-height: 1.4; padding: 6px 9px; border-radius: 7px; border-left: 2px solid var(--ghost); background: color-mix(in srgb, var(--fg) 6%, transparent); overflow-wrap: anywhere; }
.card-open { display: flex; align-items: center; justify-content: space-between; gap: 8px; font-size: 12.5px; padding: 5px 5px 5px 9px; border-radius: 8px; box-shadow: inset 0 0 0 1px var(--line); }
.card-open-name { min-width: 0; overflow-wrap: anywhere; line-height: 1.3; }
.card-open .pill-button { flex: none; }
.card-marks { display: grid; grid-template-columns: auto 1fr; align-items: center; gap: 8px; }
.card-marks .run-select { padding: 4px 6px; font-size: 12px; min-width: 0; }
.tag-terms { font-size: 10.5px; }
.index-more { padding: 4px 6px 2px 29px; font-size: 12px; color: var(--muted); }
/* Where a marker sits against the membrane: on it, through it, under it, or apart. */
.swatch-own-outside, .swatch-own-in, .swatch-own-inside { border-radius: 0; background: linear-gradient(var(--bio-membrane), var(--bio-membrane)) no-repeat; }
.swatch-own-outside { background-position: 0 8px; background-size: 100% 3px; }
.swatch-own-in { background-position: 0 4px; background-size: 100% 4px; }
.swatch-own-inside { background-position: 0 1px; background-size: 100% 3px; }
.swatch-own-outside::before, .swatch-own-in::before, .swatch-own-inside::before { content: ""; position: absolute; left: 3px; width: 6px; background: var(--atlas-generic); }
.swatch-own-outside::before { top: 0; height: 6px; border-radius: 50%; }
.swatch-own-in::before { left: 4px; width: 4px; top: 0; height: 12px; border-radius: 2px; }
.swatch-own-inside::before { top: 6px; height: 6px; border-radius: 50%; }
.swatch-own-unknown { border: 1.5px dashed var(--ghost); border-radius: 50%; }
.swatch-own-plain { background: var(--atlas-generic); border-radius: 50%; transform: scale(.75); }
.swatch-own-family { background: var(--atlas-generic); border-radius: 50% / 38%; }
/* A district's name on a shelf: many stand side by side, so they are written small and plain. */
.label-shelf { font-family: var(--font-body, inherit); font-size: 11px; font-weight: 600; letter-spacing: 0; text-transform: none; padding: 0 5px; }
/* The name that follows the pointer or the selection over the shelves. */
.label-hot { z-index: 2; background: var(--fg); color: var(--bg); font-weight: 600; pointer-events: none; }
.label-hot::after { background: var(--fg); opacity: 1; }

/* ---------------------------------------------------------------- narrow screens */
@media (max-width: 760px) {
  .card-notice { font-size: 11.5px; padding: 4px 7px; }
  .card-open { font-size: 12px; }
  .card-marks { display: none; }
  .seg.seg-wide button { padding: 4px 3px; font-size: 11.5px; }
  .brand span, .stamp { display: none; }
  .bar { gap: 8px 10px; padding-block: 10px; }
  .switch button { padding: 6px 11px; }
  .switch .long { display: none; }
  .switch .short { display: inline; }
  .view-card { width: 216px; padding: 8px 10px; }
  .view-card .card-text, .view-card details { display: none; }
  .stat b { font-size: 17px; }
  .hint { bottom: calc(64px + env(safe-area-inset-bottom, 0px)); }
  cells-legend { width: auto; right: auto; max-width: calc(100% - 32px); }
  .legend-toggle { display: flex; gap: 14px; }
  cells-legend:not(.is-open) .legend-body { display: none; }
  cells-panel { top: auto; left: 0; right: 0; bottom: 0; width: 100%; max-height: 56%; border-radius: 16px 16px 0 0; padding-bottom: env(safe-area-inset-bottom, 0px); z-index: 3; }
  cells-index { top: 56px; }
  .view { top: 54px; width: 208px; padding: 6px 8px; gap: 4px; }
  .view-note { display: none; }
  .seg-row { grid-template-columns: 46px 1fr; }
  .has-panel .scalebar, .has-panel .view { display: none; }
  .scalebar { bottom: calc(104px + env(safe-area-inset-bottom, 0px)); }
  .seg button { padding: 4px 2px; font-size: 12px; white-space: nowrap; }
  .species-option { padding: 9px 9px; }
  .caveat { width: calc(100% - 32px); bottom: calc(58px + env(safe-area-inset-bottom, 0px)); }
  .rail { top: 124px; transform: none; right: max(10px, env(safe-area-inset-right, 0px)); }
  .rail .rail-title { display: none; }
  .rail button { padding: 5px 8px 5px 6px; font-size: 12.5px; }
  .has-panel cells-legend, .has-panel .caveat { display: none; }
  .run-card { width: min(232px, calc(100% - 32px)); max-height: none; padding: 8px 10px; gap: 6px; }
  .run-card .run-plain, .run-card .run-class-note, .run-card details, .run-card .eyebrow { display: none; }
  .run-row { padding: 4px 7px; }
  cells-timeline { left: max(12px, env(safe-area-inset-left, 0px)); right: max(12px, env(safe-area-inset-right, 0px)); bottom: calc(64px + env(safe-area-inset-bottom, 0px)); max-width: none; gap: 8px; padding: 6px 9px 7px; }
  .has-panel cells-timeline { display: none; }
  .has-timeline .scalebar { bottom: calc(146px + env(safe-area-inset-bottom, 0px)); }
  .tl-play { width: 34px; height: 34px; }
}
@media (max-width: 440px) {
  .bar { gap: 8px; }
  .brand b { font-size: 18px; }
  .switch button { padding: 6px 8px; font-size: 13px; }
  .pill-button { padding: 6px 10px; }
}
@media (prefers-reduced-motion: reduce) {
  .label, .hint, .chevron { transition: none; }
}
.is-still .label, .is-still .hint, .is-still .chevron { transition: none; }
`;
