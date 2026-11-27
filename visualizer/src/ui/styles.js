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
/* The tick under a name points at its part: in the middle, or where the name was moved along to stay inside the window (core/labels.js). */
.label-part::after { content: ""; position: absolute; left: var(--tick, 50%); top: 100%; width: 1px; height: 8px; background: var(--muted); opacity: .7; }
.label-part.is-callout::after { display: none; }
.label-part.is-below::after { top: auto; bottom: 100%; }
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
.switch { display: inline-flex; padding: 3px; border-radius: 999px; background: var(--bg-raised); box-shadow: 0 0 0 1px var(--line); }
.switch button { padding: 6px 14px; border-radius: 999px; font-weight: 500; color: var(--muted); }
.switch button[aria-pressed="true"] { background: var(--fg); color: var(--bg); }
.switch .short { display: none; }
.bar-end { margin-left: auto; display: flex; align-items: center; gap: 12px; min-width: 0; }
.stamp { font-size: 12px; color: var(--muted); font-variant-numeric: tabular-nums; white-space: nowrap; }
.pill-button { padding: 6px 13px; border-radius: 999px; background: var(--bg-raised); box-shadow: 0 0 0 1px var(--line); font-weight: 500; }
.pill-button[aria-pressed="true"] { background: var(--fg); color: var(--bg); }

/* ---------------------------------------------------------------- cards */
/* A card has no backdrop blur: over a picture that is drawn anew every frame the blur is made anew every frame too. Measured on the
   project's graphics card (16 November 2026), it halved the frames a second while a card lay over the moving picture, for a backdrop
   that showed through by 6%. The card is a little more opaque instead. */
.card { background: color-mix(in srgb, var(--bg-raised) 96%, transparent); box-shadow: 0 0 0 1px var(--line), 0 10px 30px -18px rgb(0 0 0 / .45); border-radius: 12px; }
/* A card or list that scrolls inside itself shows that it does: a shade along an edge that has more beyond it.
   The covers scroll with the content and hide the shade where nothing is beyond (no script, both themes). */
cells-legend.card, .view.card, .panel-body, .tl-speeds, .index-list, .species-list {
  --cover: var(--bg-raised);
  --shade: color-mix(in srgb, var(--fg) 24%, transparent);
  background-image: linear-gradient(var(--cover) 40%, transparent), linear-gradient(transparent, var(--cover) 60%), linear-gradient(var(--shade), transparent), linear-gradient(transparent, var(--shade));
  background-position: top, bottom, top, bottom;
  background-repeat: no-repeat;
  background-size: 100% 40px, 100% 40px, 100% 18px, 100% 18px;
  background-attachment: local, local, scroll, scroll;
}

cells-legend { position: absolute; left: max(16px, env(safe-area-inset-left, 0px)); bottom: calc(16px + env(safe-area-inset-bottom, 0px)); width: 236px; padding: 6px; overflow-y: auto; }
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
/* A long word (an identifier, a file's path) wraps inside the panel: unwrapped, it widened the head past the close
   button and the body past the panel's edge, where the rest was cut. */
.panel-head > div { min-width: 0; }
.eyebrow { font-size: 11px; font-weight: 600; letter-spacing: .07em; text-transform: uppercase; color: var(--muted); }
.panel-head h2 { font-family: var(--font-display); font-size: 21px; line-height: 1.2; font-weight: 600; text-wrap: balance; margin-top: 2px; overflow-wrap: anywhere; }
.icon-button { width: 30px; height: 30px; flex: none; border-radius: 50%; font-size: 20px; line-height: 1; color: var(--muted); }
.icon-button:hover { background: color-mix(in srgb, var(--fg) 9%, transparent); color: var(--fg); }
.chips { display: flex; flex-wrap: wrap; gap: 6px; padding: 0 16px 12px; }
.chip { display: inline-flex; align-items: center; gap: 6px; padding: 3px 9px; border-radius: 999px; font-size: 12px; font-weight: 500; box-shadow: inset 0 0 0 1px var(--line); }
.chip-plain { color: var(--muted); }
.panel-body { overflow-y: auto; padding: 0 16px 18px; display: grid; grid-template-columns: minmax(0, 1fr); gap: 12px; align-content: start; min-height: 0; }
.panel-plain { font-size: 15px; line-height: 1.5; overflow-wrap: anywhere; }
.panel-note { font-size: 13px; color: var(--muted); padding-left: 10px; border-left: 2px solid var(--line); overflow-wrap: anywhere; }
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
/* A view whose rail marks what is chosen (the Machines view's scale) folds it, while a panel is open on a wide window, behind the page's own button, beside the panel. */
@media (min-width: 761px) { .frame.rail-beside-panel.has-panel .rail-toggle { display: flex; position: absolute; top: 68px; right: calc(max(16px, env(safe-area-inset-right, 0px)) + 376px); align-items: center; gap: 12px; padding: 0 14px; min-height: 44px; font-weight: 500; } .frame.rail-beside-panel.has-panel .rail-toggle .chevron { transform: rotate(45deg); margin-top: -4px; } .frame.rail-beside-panel.has-panel .rail-toggle.is-open .chevron { transform: rotate(-135deg); margin-top: 3px; } .frame.rail-beside-panel.has-panel.rail-open .rail { display: grid; top: 118px; transform: none; right: calc(max(16px, env(safe-area-inset-right, 0px)) + 376px); z-index: 2; } }
/* On a phone the rail folds behind one button that names the level shown (viewer.js); a wide window has no need of it. */
.rail-toggle, .view-toggle, .view-notice { display: none; }

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
/* The note lies over the whole picture, the panel's place included, and stands after the panel: it lets a press through, so
   that a part's panel and About's can be pressed where no 3D is drawn. Nothing in the note is pressed. */
.fallback { pointer-events: none; }

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
/* A sweep's chart in the experiment's card (replay/sweep.js): each arm a column of points, a button over it. */
.sweep { display: grid; grid-template-columns: minmax(0, 1fr); gap: 4px; margin-top: 8px; min-width: 0; }
.sweep-numbers { overflow-x: auto; }
.view.run-card { grid-template-columns: minmax(0, 1fr); }
.sweep-choose { display: grid; gap: 2px; min-width: 0; }
.sweep-choose select { max-width: 100%; }
.sweep-card { position: absolute; right: max(16px, env(safe-area-inset-right, 0px)); top: 104px; width: 280px; padding: 4px 12px 10px; max-height: calc(100% - 104px - 150px); overflow-y: auto; }
.has-panel .sweep-card { display: none; }
.sweep-chart { position: relative; min-width: 0; width: 100%; }
.sweep-svg { display: block; width: 100%; max-width: 100%; height: auto; overflow: visible; }
.sweep-axis { stroke: var(--line); stroke-width: 1; }
.sweep-tick { font-size: 8.5px; fill: var(--muted); font-variant-numeric: tabular-nums; }
.sweep-axis-label { font-size: 9px; fill: var(--muted); }
.sweep-shown { fill: color-mix(in srgb, var(--accent) 16%, transparent); }
.sweep-line polyline { stroke-width: 1.4; opacity: 0.7; }
.sweep-line-0 { color: var(--accent); stroke: var(--accent); fill: var(--accent); }
.sweep-line-1 { color: #d9822b; stroke: #d9822b; fill: #d9822b; }
.sweep-line-2 { color: #3b9c6e; stroke: #3b9c6e; fill: #3b9c6e; }
.sweep-line-3 { color: #8a63c9; stroke: #8a63c9; fill: #8a63c9; }
.sweep-line polyline { fill: none; }
.sweep-point.is-shown { stroke: var(--fg); stroke-width: 1.4; }
.sweep-ref { fill: none; stroke-width: 1.2; stroke-dasharray: 2 1.6; }
.sweep-arm { position: absolute; width: 22px; border-radius: 6px; background: transparent; cursor: pointer; padding: 0; }
.sweep-arm:hover:not(:disabled) { background: color-mix(in srgb, var(--fg) 8%, transparent); }
.sweep-arm:disabled { cursor: default; }
.sweep-arm[aria-pressed="true"] { box-shadow: inset 0 0 0 1px var(--accent); }
.sweep-key { display: flex; flex-wrap: wrap; gap: 4px 10px; font-size: 11.5px; color: var(--muted); margin: 0; }
.sweep-key-item { display: inline-flex; align-items: center; gap: 4px; }
.sweep-swatch { display: inline-block; width: 12px; height: 3px; border-radius: 2px; background: currentColor; }
.sweep-ring { width: 9px; height: 9px; border-radius: 50%; background: transparent; box-shadow: inset 0 0 0 1.2px var(--muted); }
.sweep-note { font-size: 11.5px; color: var(--muted); }
.sweep-table { border-collapse: collapse; font-size: 11.5px; font-variant-numeric: tabular-nums; width: 100%; }
.sweep-table th, .sweep-table td { text-align: right; padding: 2px 4px; border-bottom: 1px solid var(--line); }
.sweep-table th[scope="row"], .sweep-table thead th:first-child { text-align: left; }
.sweep-table tr.is-shown { background: color-mix(in srgb, var(--accent) 12%, transparent); }
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
/* While a part of the example is shown: its short name under the example's row, a corner mark joining them. */
.exp-within { position: relative; padding-left: 15px; font-size: 11.5px; font-weight: 600; color: var(--fg); }
.exp-within-chosen { margin: 4px 0 0 2px; }
.exp-within::before { content: ""; position: absolute; left: 3px; top: 1px; width: 7px; height: 7px; border-left: 1.5px solid var(--muted); border-bottom: 1.5px solid var(--muted); }
.found { display: grid; gap: 4px; }
.found-facts { display: flex; flex-wrap: wrap; gap: 4px 12px; }
.run-ended { display: flex; align-items: center; gap: 6px; }
/* Under a scale, whose its quantity is (one an experiment states beside its run); and the line that says an experiment's runs
   state one quantity in other units (two forms of a model): by the runs, and by the sweep's chart. */
.legend-scale-said { margin: 6px 0 0; font-size: 11.5px; line-height: 1.4; color: var(--muted); }
.run-units { margin: 6px 0 0; font-size: 12px; line-height: 1.4; color: var(--muted); }
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
.legend-body > .legend-layers:first-child > .legend-title { border-top: 0; margin-top: 0; }
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
.layer-example { margin: 2px 8px 5px; padding: 3px 7px; border: 1px solid var(--fg); border-radius: 5px; font-size: 12px; font-weight: 600; line-height: 1.3; color: var(--fg); }
.key-tile, .key-tile-held { height: 11px; border: 1.5px solid var(--muted); border-radius: 2px; }
.key-tile-held { outline: 1.5px solid var(--muted); outline-offset: -5px; }
.key-amount { width: 12px; height: 12px; margin-left: 4px; border-radius: 50%; background: linear-gradient(to right, var(--seq-1), var(--seq-4)); }
.key-way { width: 15px; height: 2px; margin: 7px 0 0 1px; background: var(--fg); }
.key-way::after { content: ""; position: absolute; right: -4px; top: -3px; border-left: 6px solid var(--fg); border-top: 4px solid transparent; border-bottom: 4px solid transparent; }
.key-unplaced { width: 9px; height: 9px; margin: 3px 0 0 6px; border: 1.5px dashed var(--muted); border-radius: 50%; }
.key-pump { width: 12px; height: 12px; margin-left: 4px; border: 1.5px solid var(--fg); border-radius: 2px; }
.key-glow, .key-glow-spot, .key-glow-route { height: 11px; border-radius: 6px; background: radial-gradient(closest-side, #dd7a14, transparent); }
.key-glow-rim { width: 13px; height: 13px; margin-left: 3px; border-radius: 50%; background: radial-gradient(closest-side, transparent 42%, #dd7a14 68%, transparent); }
.key-glow-spot { width: 11px; margin-left: 5px; }
.key-glow-route { opacity: .55; }
.label-example { font-weight: 700; border: 1px solid var(--fg); background: var(--bg-raised); }
.label-flow { font-weight: 500; font-variant-numeric: tabular-nums; white-space: pre-line; text-align: center; }
.key-head { width: 0; height: 0; margin: 3px 0 0 6px; border-left: 9px solid var(--fg); border-top: 5px solid transparent; border-bottom: 5px solid transparent; }
.legend-layers.is-dense .layer-row { grid-template-columns: 50px minmax(0, 1fr); column-gap: 5px; align-items: center; padding: 2px 8px; }
.legend-layers.is-dense .layer-channel, .legend-layers.is-dense .layer-seg button { font-size: 11px; }

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
/* Stops (a binding's events with words, src/ui/timeline.js): a mark to press for each, and the previous and next beside play. */
cells-timeline.has-stops { grid-template-columns: auto auto auto minmax(0, 1fr) auto; }
.tl-step { display: grid; place-items: center; width: 32px; height: 32px; border-radius: 50%; border: 1px solid var(--line); background: var(--bg-raised); color: var(--fg); }
.tl-step:hover { border-color: var(--accent); }
.tl-step svg { width: 16px; height: 16px; fill: currentColor; }
.tl-stops { position: absolute; inset: 0; pointer-events: none; }
.tl-stop { position: absolute; top: 3px; width: 12px; height: 26px; margin-left: -6px; padding: 0; border: 0; background: none; pointer-events: auto; cursor: pointer; }
.tl-stop::before { content: ""; position: absolute; left: 5px; top: 2px; bottom: 2px; width: 2px; border-radius: 1px; background: var(--accent); }
.tl-stop:hover::before, .tl-stop:focus-visible::before { left: 3px; width: 6px; }
.tl-stop:focus-visible { outline: 2px solid var(--accent); outline-offset: 1px; border-radius: 3px; }
/* A species' life stages (schema/SPECIES_STAGES.md): the same timeline, each stage a dot on the track, a stage named and not
   drawn hollow, the one shown ringed, and their short names under them on a wide window. The picture's words rise above it. */
cells-timeline.no-play { grid-template-columns: minmax(0, 1fr); }
cells-timeline.has-stops.no-play { grid-template-columns: auto auto minmax(0, 1fr); }
cells-timeline.no-play .tl-speed { display: none; } /* a pace is for playing */
cells-timeline.is-stages .tl-stop { width: 22px; margin-left: -11px; }
cells-timeline.is-stages .tl-stop::before { left: 6px; top: 11px; bottom: auto; width: 10px; height: 10px; border-radius: 50%; background: var(--fg); }
cells-timeline.is-stages .tl-stop:hover::before, cells-timeline.is-stages .tl-stop:focus-visible::before { left: 5px; top: 10px; width: 12px; height: 12px; }
cells-timeline.is-stages .tl-stop.is-named::before { background: var(--bg-raised); box-shadow: inset 0 0 0 2px var(--muted); }
cells-timeline.is-stages .tl-stop[aria-current]::before { box-shadow: 0 0 0 3px color-mix(in srgb, var(--accent) 50%, transparent); }
cells-timeline.is-stages .tl-stop-name { position: absolute; top: 25px; left: 50%; transform: translateX(-50%); font-size: 11px; line-height: 1.2; white-space: nowrap; color: var(--muted); pointer-events: none; }
cells-timeline.is-stages .tl-stop[aria-current] .tl-stop-name { color: var(--fg); font-weight: 600; }
/* The names at the two ends stand inside the track, clear of the buttons beside it. */
cells-timeline.is-stages .tl-stop:first-child .tl-stop-name { transform: none; margin-left: -6px; }
cells-timeline.is-stages .tl-stop:last-child .tl-stop-name { left: auto; right: 50%; transform: none; margin-right: -6px; }
cells-timeline.is-stages.has-names .tl-track { margin-bottom: 12px; }
.has-stages .caveat { bottom: calc(96px + env(safe-area-inset-bottom, 0px)); }
/* In Scope the look's note stands at the right of the foot, up to 266 px from the edge: the strip ends before it (at 1280 px it ran under the note's first words). */
@media (min-width: 761px) { .has-stages cells-timeline { right: 280px; } }
@media (max-width: 760px) { cells-timeline.is-stages .tl-stop { width: 44px; height: 44px; top: -6px; margin-left: -22px; } cells-timeline.is-stages .tl-stop::before { left: 17px; top: 17px; } cells-timeline.is-stages .tl-stop:hover::before, cells-timeline.is-stages .tl-stop:focus-visible::before { left: 16px; top: 16px; } }
/* On a phone the strip takes the foot: the picture's words stand just above it and the scale bar above them, and the look's own notes
   fold while the strip shows, so that the foot is about as tall as it is without a strip (the legend keeps what moves at rest and what is scenery). */
@media (max-width: 760px) { .has-stages .caveat { bottom: calc(160px + env(safe-area-inset-bottom, 0px)); } .has-stages .look-note { display: none; } .has-stages .scalebar { bottom: calc(216px + env(safe-area-inset-bottom, 0px)); } }
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
.tl-speeds { position: absolute; right: 0; bottom: calc(100% + 6px); display: grid; gap: 1px; width: min(330px, calc(100vw - 24px)); max-height: min(60vh, 420px); overflow: auto; padding: 5px; border-radius: 12px; background-color: var(--bg-raised); box-shadow: 0 0 0 1px var(--line), 0 10px 30px -18px rgb(0 0 0 / .45); }
.tl-speeds[hidden] { display: none; }
.tl-speeds.opens-down { top: calc(100% + 6px); bottom: auto; }
cells-timeline.is-choosing { z-index: 4; }
.tl-speed-step { display: grid; grid-template-columns: 92px minmax(0, 1fr); gap: 8px; align-items: baseline; padding: 5px 8px; border-radius: 8px; text-align: left; font-size: 12.5px; line-height: 1.3; color: var(--fg); }
.tl-speed-step b { font-weight: 600; font-variant-numeric: tabular-nums; }
.tl-speed-step span { color: var(--muted); }
.tl-speed-step:hover { background: color-mix(in srgb, var(--fg) 7%, transparent); }
.tl-speed-step[aria-pressed="true"] { background: color-mix(in srgb, var(--accent) 16%, transparent); }
.tl-speed-step[aria-pressed="true"] span { color: var(--fg); }
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
.species-list { position: absolute; z-index: 6; display: grid; align-content: start; gap: 2px; padding: 6px; overflow-y: auto; overscroll-behavior: contain; border-radius: 12px; background-color: var(--bg-raised); box-shadow: 0 0 0 1px var(--line), 0 16px 36px -16px rgb(0 0 0 / .5); }
.species-section { display: grid; gap: 2px; }
.species-section + .species-section { margin-top: 4px; padding-top: 6px; border-top: 1px solid var(--line); }
.species-group { display: grid; gap: 2px; }
.species-subgroup { margin-inline-start: 10px; padding-inline-start: 5px; border-inline-start: 1px solid var(--line); }
.species-subgroup + .species-subgroup { margin-top: 4px; }
.species-group-name { padding: 3px 9px 2px; font-family: var(--font-display); font-size: 10.5px; font-weight: 600; letter-spacing: .07em; text-transform: uppercase; color: var(--muted); }
.species-group-name.is-top { font-size: 11px; color: var(--fg); }
/* A row: the name and what Cells models of it on one line, the organism under them across the row. */
.species-option { display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: center; gap: 1px 10px; padding: 7px 9px; border-radius: 8px; cursor: pointer; }
.species-option-name { grid-column: 1; grid-row: 1; font-size: 13.5px; font-weight: 600; line-height: 1.3; }
.species-option-organism { grid-column: 1 / -1; grid-row: 2; font-size: 12px; font-style: italic; line-height: 1.3; color: var(--muted); overflow-wrap: break-word; }
.species-option-state { grid-column: 2; grid-row: 1; padding: 2px 8px; border-radius: 999px; font-size: 11px; font-weight: 500; color: var(--muted); box-shadow: inset 0 0 0 1px var(--line); white-space: nowrap; }
.species-option-state[data-state="proposed"] { color: var(--fg); box-shadow: inset 0 0 0 1.5px var(--fg); }
/* The switch's other entries (schema/ENTRIES.md): a model system's line names what it is, not an organism; a cell type stands under its species. */
.species-option-state[data-state="planned"], .species-option-state[data-state="designed"], .species-state[data-state="planned"], .species-state[data-state="designed"] { color: var(--fg); box-shadow: inset 0 0 0 1.5px var(--fg); }
.species-option.is-model .species-option-organism { font-style: normal; }
.species-option.is-type { padding-left: 22px; }
.species-option.is-type .species-option-name { font-weight: 500; }
/* On a narrow window the rail's button stands under the bar, however many rows it takes (the viewer sets --bar-height). */
@media (max-width: 760px) { .frame .rail-toggle { top: max(68px, calc(var(--bar-height, 0px) + 8px)); } .frame .rail { top: max(118px, calc(var(--bar-height, 0px) + 58px)); } }
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
@media (max-width: 1180px) { .with-species .stamp { display: none; } }
/* Where the words are wider than that (more species, or a fallback font), the viewer asks for a tighter bar, by measure:
   no date, the switch's own word ("Species") out of sight and still read out, and the first tab by its short name
   where a model system stands in it. The Experiments tab keeps its name on a wide window: it is "Runs" on a phone only.
   (Until 19 November 2026 the tight bar also drew it by its short name, so at some widths the tab read "Runs" in the
   views that have a species switch and "Experiments" in the others, and changed when it was pressed.) */
.with-species[data-tight="2"] .switch .long { display: none; }
.with-species[data-tight="2"] .switch .short { display: inline; }
.with-species[data-tight="2"] .switch [data-lens="experiments"] .long { display: inline; }
.with-species[data-tight="2"] .switch [data-lens="experiments"] .short { display: none; }
.with-species[data-tight="2"] .species-label { position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); white-space: nowrap; }
.with-species[data-tight="2"] .stamp { display: none; }
/* A model system shown in the Experiments tab's place: its stamp is shortened clear of the card at the left. On a phone no
   stamp is shown, and the bar's end holds only the List, which stays whole. */
@media (min-width: 760px) { .tab-example .bar-end { max-width: calc(100% - 300px); overflow: hidden; } }
.tab-example .stamp { overflow: hidden; text-overflow: ellipsis; min-width: 0; }
/* A part of an example shown there (the tissue line): its pictures and their heads reach up to the bar, so the bar stays on
   one line and the stamp is shortened where the line is short, its first words (the part's standing) kept. A phone shows
   no stamp and its row of tabs scrolls, as everywhere. */
@media (min-width: 760px) {
  .tab-part { flex-wrap: nowrap; }
  .tab-part .bar-end { flex: 0 1 auto; min-width: 0; max-width: none; overflow: hidden; }
  .tab-part .switch, .tab-part .brand, .tab-part .pill-button { flex: none; }
}
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
.seg.seg-one-row { grid-template-columns: repeat(var(--seg-count, 2), minmax(0, 1fr)); }
.seg.seg-one-row button { padding: 5px 2px; font-size: 11.5px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
/* On a phone the card is too narrow for four whole words in a row: two rows of two, none cut. */
@media (max-width: 560px) { .seg.seg-one-row { grid-template-columns: repeat(min(var(--seg-count, 2), 2), minmax(0, 1fr)); } }
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
  .stamp { display: none; }
  .bar { gap: 8px 10px; padding-block: 8px; }
  /* A thing to press is at least 44 px in its smaller dimension on a phone. The names on the picture are
     the exception: they stand for their parts, and the List gives every part as a row to press. */
  .switch { padding: 0; }
  .switch button { min-height: 44px; padding: 6px 11px; }
  .pill-button, .icon-button, .legend-toggle, .rail-toggle, .view-toggle, .species-pick, .species-state, .run-select, .index-search, .tl-speed, .tl-speed-step, .legend-item, .rail button, .run-row, .exp-row, .index-row { min-height: 44px; }
  .seg { padding: 0; }
  .seg button, .layer-seg button { min-height: 44px; }
  .icon-button { width: 44px; height: 44px; margin: -8px -8px 0 0; }
  .species-state { display: inline-flex; align-items: center; }
  .panel-body summary, .legend-keys summary, .legend-fold > summary, .view details summary { min-height: 44px; padding-block: 12px; }
  .panel-body .link-button, .layer-more .link-button { min-height: 44px; align-items: center; }
  /* A door into another view is a button of its own, its words wrapping inside it. */
  .panel-door .link-button { display: flex; width: 100%; padding: 8px 12px; border-radius: 9px; box-shadow: inset 0 0 0 1px var(--line); text-decoration: none; text-wrap: pretty; }
  .panel-door .link-button:hover { background: color-mix(in srgb, var(--fg) 6%, transparent); }
  .switch .long { display: none; }
  .switch .short { display: inline; }
  .view-card { width: 216px; padding: 8px 10px; }
  /* How a view's data was made and its sources and licences stay a press away: their lines, not their words, are shown. */
  .view-card .card-text { display: none; }
  /* The atlas's card keeps to the top of the picture: what is below its fold is a scroll away, and its edge says so. */
  .view-card:not(.run-card) { max-height: min(40%, 260px); }
  .stat b { font-size: 17px; }
  .hint { bottom: calc(80px + env(safe-area-inset-bottom, 0px)); }
  cells-legend { width: auto; right: auto; max-width: calc(100% - 32px); }
  .legend-toggle { display: flex; gap: 14px; }
  cells-legend:not(.is-open) .legend-body { display: none; }
  cells-panel { top: auto; left: 0; right: 0; bottom: 0; width: 100%; max-height: 56%; border-radius: 16px 16px 0 0; padding-bottom: env(safe-area-inset-bottom, 0px); z-index: 3; }
  cells-index { top: 68px; }
  .view { top: 68px; width: 208px; max-height: calc(100% - 68px - 160px); padding: 6px 8px; gap: 4px; }
  .view-note { display: none; }
  .seg-row { grid-template-columns: 46px 1fr; }
  /* With a panel open the view's card folds behind one button under the bar; a press opens it over the picture. */
  .has-panel:not(.view-open) .view { display: none; }
  .has-panel .view-toggle { display: flex; position: absolute; top: 68px; left: max(16px, env(safe-area-inset-left, 0px)); align-items: center; gap: 12px; padding: 0 14px; font-weight: 500; z-index: 4; }
  .view-toggle .chevron { transform: rotate(45deg); margin-top: -4px; }
  .view-toggle.is-open .chevron { transform: rotate(-135deg); margin-top: 3px; }
  .has-panel.view-open .view { top: 118px; max-height: calc(100% - var(--sheet, 56%) - 126px); z-index: 4; }
  .has-panel.view-open .view-notice { display: block; margin: 0 0 2px; }
  /* Clear of a caveat that wraps to three lines, as it does where the page's own font did not arrive (and lifted further where it would still meet it: viewer.js). */
  .scalebar { bottom: calc(148px + env(safe-area-inset-bottom, 0px)); }
  .seg button { padding: 4px 2px; font-size: 12px; white-space: nowrap; }
  .species-option { padding: 9px 9px; }
  .caveat { width: calc(100% - 32px); bottom: calc(80px + env(safe-area-inset-bottom, 0px)); }
  /* The scale rail folds behind one button under the bar, at the right; open, its levels stand under it. */
  .rail-toggle { display: flex; position: absolute; top: 68px; right: max(16px, env(safe-area-inset-right, 0px)); align-items: center; gap: 12px; padding: 0 14px; font-weight: 500; }
  .rail-toggle .seg-label { margin-right: -4px; }
  .rail-toggle .chevron { transform: rotate(45deg); margin-top: -4px; }
  .rail-toggle.is-open .chevron { transform: rotate(-135deg); margin-top: 3px; }
  .rail { top: 118px; transform: none; right: max(16px, env(safe-area-inset-right, 0px)); z-index: 2; }
  .frame:not(.rail-open) .rail, .has-panel .rail-toggle { display: none; }
  .rail .rail-title { display: none; }
  .rail button { padding: 5px 12px 5px 8px; font-size: 12.5px; }
  .has-panel .caveat { display: none; }
  /* With a panel open the switches of the foot stand on its top edge: the legend's title at the left, the look's switch
     at the right, a replay's timeline over them. The sheet's height is the viewer's (--sheet). */
  .has-panel cells-legend { bottom: calc(var(--sheet, 56%) + 8px); z-index: 3; }
  .has-panel .scalebar { right: max(16px, env(safe-area-inset-right, 0px)); bottom: calc(var(--sheet, 56%) + 8px); }
  .has-panel .scalebar-line, .has-panel .scalebar-text, .has-panel .look-note { display: none; }
  .has-panel .look-box { margin-bottom: 0; }
  .run-card { width: min(232px, calc(100% - 32px)); max-height: 40%; padding: 8px 10px; gap: 6px; }
  .run-card .run-plain, .run-card .run-class-note, .run-card details, .run-card .eyebrow { display: none; }
  .run-row { padding: 4px 7px; align-content: center; }
  .run-card .run-select { font-size: 12px; padding: 6px 4px; }
  .exp-row { align-content: center; }
  cells-timeline { left: max(12px, env(safe-area-inset-left, 0px)); right: max(12px, env(safe-area-inset-right, 0px)); bottom: calc(80px + env(safe-area-inset-bottom, 0px)); max-width: none; gap: 8px; padding: 5px 9px 6px; }
  .has-panel cells-timeline { right: max(12px, env(safe-area-inset-right, 0px)); bottom: calc(var(--sheet, 56%) + 72px); }
  .has-timeline .scalebar { bottom: calc(168px + env(safe-area-inset-bottom, 0px)); }
  .tl-play { width: 44px; height: 44px; }
  .tl-speed { min-width: 52px; }
  /* The read-out wraps to a second line rather than being cut where the row is narrow. */
  .tl-read { white-space: normal; line-height: 1.3; }
  /* The playhead is pressed and dragged over the full 44 px of its row. */
  .tl-track { height: 44px; }
  .tl-rail { top: 20px; }
  .tl-marks { top: 10px; }
  .tl-flag { top: -4px; }
  .tl-range { top: 0; height: 44px; }
  .tl-range::-webkit-slider-runnable-track { height: 44px; }
  .tl-range::-webkit-slider-thumb { width: 18px; height: 18px; margin-top: 13px; }
  .tl-range::-moz-range-track { height: 44px; }
}
@media (max-width: 440px) {
  .bar { gap: 8px; }
  /* The folded rail's button keeps clear of the view's card: the level's name alone, its button says "Scale" to a reader. */
  .rail-toggle .seg-label { display: none; }
  .brand b { font-size: 18px; }
  .switch button { padding: 6px 8px; font-size: 13px; }
  .pill-button { padding: 6px 10px; }
}
@media (prefers-reduced-motion: reduce) {
  .label, .hint, .chevron { transition: none; }
}
.is-still .label, .is-still .hint, .is-still .chevron { transition: none; }

/* The protein atlas's own proteins (docs/ATLAS_LOOK.md, decided 16 November 2026): the sides in colour, the two ramps
   "Colour" offers, the trail with its search, and the map of the stack. Colours are the page's tokens (--own-*). */
.swatch-own-side-outside, .swatch-own-side-in, .swatch-own-side-inside { border-radius: 0; background: linear-gradient(var(--bio-membrane), var(--bio-membrane)) no-repeat; }
.swatch-own-side-outside { background-position: 0 8px; background-size: 100% 3px; }
.swatch-own-side-in { background-position: 0 4px; background-size: 100% 4px; }
.swatch-own-side-inside { background-position: 0 1px; background-size: 100% 3px; }
.swatch-own-side-outside::before, .swatch-own-side-in::before, .swatch-own-side-inside::before { content: ""; position: absolute; left: 2px; width: 8px; }
.swatch-own-side-outside::before { top: 0; height: 7px; border-radius: 50%; background: var(--own-outside); }
.swatch-own-side-in::before { left: 3px; width: 6px; top: 0; height: 12px; border-radius: 3px; background: var(--own-in); }
.swatch-own-side-inside::before { top: 5px; height: 7px; border-radius: 50%; background: var(--own-inside); }
.swatch-own-basis-1, .swatch-own-basis-2, .swatch-own-basis-3, .swatch-own-mark-1, .swatch-own-mark-2, .swatch-own-mark-3 { border-radius: 50%; transform: scale(.85); }
.swatch-own-basis-1 { background: var(--own-basis-1); } .swatch-own-basis-2 { background: var(--own-basis-2); } .swatch-own-basis-3 { background: var(--own-basis-3); }
.swatch-own-mark-1 { background: var(--own-mark-1); } .swatch-own-mark-2 { background: var(--own-mark-2); } .swatch-own-mark-3 { background: var(--own-mark-3); }
/* "Colour" above its select, so that the select has the legend's whole width and its longest choice stands whole beside its arrow. */
.legend-colour { display: grid; grid-template-columns: minmax(0, 1fr); gap: 4px; padding: 4px 6px 2px; }
.legend-colour .run-select { min-width: 0; width: 100%; padding-right: 24px; text-overflow: ellipsis; }
.legend-colour-title { margin-top: 4px; }
.atlas-trail { position: absolute; top: 64px; left: 324px; right: max(16px, env(safe-area-inset-right, 0px)); max-width: 920px; display: flex; align-items: center; gap: 10px; padding: 5px 6px; z-index: 4; }
.has-panel .atlas-trail { right: calc(min(360px, 100% - 32px) + 32px); }
.has-panel .atlas-findbox { flex-basis: 180px; }
.atlas-findbox { position: relative; flex: 0 0 248px; min-width: 0; }
.atlas-find { width: 100%; box-sizing: border-box; font: inherit; font-size: 13px; padding: 6px 10px; border-radius: 8px; border: 1px solid var(--line); background: var(--bg-raised); color: var(--fg); }
.atlas-find:focus-visible { outline: 2px solid var(--accent); outline-offset: 1px; }
.atlas-results { position: absolute; top: calc(100% + 6px); left: 0; width: 380px; max-width: calc(100vw - 32px); max-height: min(60vh, 520px); overflow-y: auto; padding: 6px; display: grid; gap: 6px; background: var(--bg-raised); border-radius: 10px; box-shadow: 0 0 0 1px var(--line), 0 12px 30px -16px rgb(0 0 0 / .5); z-index: 6; }
.atlas-results h4 { margin: 4px 6px 2px; font: 600 10.5px/1.2 var(--font-mono); letter-spacing: .08em; text-transform: uppercase; color: var(--muted); }
.atlas-results > * { min-width: 0; }
.atlas-hit { display: grid; grid-template-columns: 14px minmax(0, 1fr); column-gap: 8px; width: 100%; min-width: 0; box-sizing: border-box; white-space: normal; text-align: left; padding: 6px 8px; border: 0; border-radius: 7px; background: transparent; color: var(--fg); font: inherit; font-size: 12.5px; cursor: pointer; }
.atlas-hit:hover, .atlas-hit:focus-visible { background: color-mix(in srgb, var(--fg) 7%, transparent); outline: none; }
.atlas-hit .swatch { grid-row: span 2; margin-top: 2px; }
.atlas-hit-name { overflow-wrap: anywhere; }
.atlas-hit-where { color: var(--muted); font-size: 11.5px; overflow-wrap: anywhere; }
.atlas-note { margin: 4px 8px; font-size: 12px; color: var(--muted); }
.atlas-where { display: flex; align-items: center; gap: 6px; min-width: 0; flex: 1 1 auto; }
.atlas-back { flex: none; width: 30px; height: 30px; border-radius: 50%; border: 1px solid var(--line); background: var(--bg-raised); color: var(--fg); font: inherit; font-size: 15px; cursor: pointer; }
.atlas-back:disabled { opacity: .35; cursor: default; }
.atlas-crumbs { display: flex; align-items: center; list-style: none; margin: 0; padding: 0; min-width: 0; flex: 1 1 auto; overflow: hidden; font-size: 12.5px; white-space: nowrap; }
.atlas-crumbs li { display: flex; align-items: center; gap: 5px; flex: none; }
.atlas-crumbs li[hidden] { display: none; }
.atlas-crumbs li + li::before { content: "\\203A"; color: var(--muted); margin: 0 5px; }
.atlas-crumbs li.is-here { flex: none; }
.atlas-crumbs.is-tight li.is-here { flex: 0 1 auto; min-width: 9ch; }
.atlas-crumb { display: inline-flex; align-items: center; font: inherit; color: var(--accent); background: none; border: 0; padding: 4px 2px; cursor: pointer; max-width: 24ch; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.atlas-crumb > span, .is-here .atlas-crumb { display: block; overflow: hidden; text-overflow: ellipsis; line-height: 22px; }
.is-here .atlas-crumb { max-width: 34ch; }
.atlas-more .atlas-crumb { color: var(--muted); cursor: default; }
.is-here .atlas-crumb { color: var(--fg); font-weight: 600; cursor: default; }
.is-opening .atlas-crumb { color: var(--muted); font-style: italic; cursor: default; }
.atlas-find-open { display: none; }
/* The map is a column of bars at the window's right edge; it opens to the shelves' names under the pointer or the keyboard. */
.atlas-map { position: absolute; right: max(16px, env(safe-area-inset-right, 0px)); bottom: calc(16px + env(safe-area-inset-bottom, 0px)); width: 56px; box-sizing: border-box; padding: 6px; display: grid; grid-template-columns: minmax(0, 1fr); gap: 3px; overflow: hidden; z-index: 3; }
.atlas-map > * { min-width: 0; }
.atlas-map:hover, .atlas-map:focus-within { width: 248px; }
/* Opening it only widens it: every row keeps its height and place, so that a press aimed at a bar lands on its row. */
.atlas-map:not(:hover):not(:focus-within) .atlas-map-key, .atlas-map:not(:hover):not(:focus-within) .atlas-row-name, .atlas-map:not(:hover):not(:focus-within) .atlas-row-count { visibility: hidden; }
.atlas-map:not(:hover):not(:focus-within) .atlas-bar { width: 100% !important; }
.has-panel .atlas-map { right: calc(min(360px, 100% - 32px) + 32px); }
.atlas-map-title { margin: 0 2px 4px; font: 600 10.5px/1.3 var(--font-mono); letter-spacing: .08em; text-transform: uppercase; color: var(--muted); display: flex; justify-content: space-between; gap: 6px; }
.atlas-map-key { text-transform: none; letter-spacing: 0; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; min-width: 0; }
.atlas-map-title { overflow: hidden; }
.atlas-row { display: grid; grid-template-columns: minmax(0, 1fr) auto; align-content: center; gap: 3px 8px; height: 34px; box-sizing: border-box; overflow: hidden; padding: 3px 6px; border: 0; border-radius: 7px; background: transparent; color: var(--fg); font: inherit; font-size: 12px; text-align: left; cursor: pointer; }
.atlas-row-name, .atlas-row-count { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.atlas-row:hover { background: color-mix(in srgb, var(--fg) 6%, transparent); }
.atlas-row:focus-visible { outline: 2px solid var(--accent); outline-offset: -2px; }
.atlas-row.is-on { background: color-mix(in srgb, var(--accent) 14%, transparent); box-shadow: inset 3px 0 0 var(--accent); }
.atlas-row-count { color: var(--muted); font-variant-numeric: tabular-nums; }
.atlas-row-open { color: var(--accent); font-weight: 600; }
.atlas-bar { grid-column: 1 / -1; display: flex; height: 6px; border-radius: 3px; overflow: hidden; }
.atlas-seg { display: block; height: 100%; }
.atlas-seg-outside { background: var(--own-outside); } .atlas-seg-in { background: var(--own-in); } .atlas-seg-inside { background: var(--own-inside); }
.atlas-seg-unknown { background: repeating-linear-gradient(90deg, var(--ghost) 0 2px, transparent 2px 4px); }
@media (max-width: 760px) {
  /* On a phone the trail is one row under the bar: the arrow back, the step you are at, and a button that opens the search over it. */
  .atlas-trail { left: max(16px, env(safe-area-inset-left, 0px)); right: max(16px, env(safe-area-inset-right, 0px)); top: 64px; padding: 0 4px; gap: 4px; }
  .has-panel .atlas-trail { right: max(16px, env(safe-area-inset-right, 0px)); }
  .atlas-findbox { display: none; position: absolute; left: 0; right: 0; top: calc(100% + 6px); flex: none; }
  .atlas-trail.is-finding .atlas-findbox { display: block; }
  .atlas-find { min-height: 44px; font-size: 16px; }
  .atlas-results { width: 100%; max-width: none; max-height: 52vh; }
  .atlas-back { width: 44px; height: 44px; border: 0; background: transparent; }
  .atlas-crumbs li:not(.is-here):not(:nth-last-child(2)) { display: none; }
  .atlas-crumbs li:nth-last-child(2) { max-width: 30%; }
  .atlas-crumbs li:nth-last-child(2)::before, .atlas-crumbs li:nth-last-child(2) .swatch { display: none; }
  .atlas-crumbs li:only-child::before { display: none; }
  .atlas-crumb { min-height: 44px; }
  .is-here .atlas-crumb, .atlas-more .atlas-crumb { line-height: 44px; }
  .atlas-results { box-sizing: border-box; }
  .atlas-find-open { display: block; flex: none; min-height: 44px; padding: 0 12px; border: 0; border-left: 1px solid var(--line); background: transparent; color: var(--accent); font: inherit; font-weight: 600; cursor: pointer; }
  .atlas-hit { min-height: 44px; }
  .has-trail .view, .has-trail cells-index { top: 116px; }
  /* The legend, open, reaches up to the bar: over the trail, which it hides while it is open. */
  .has-trail cells-legend.is-open { z-index: 5; }
  .has-trail .view { max-height: calc(100% - 116px - 160px); }
  .has-trail.has-panel .view-toggle { top: 116px; }
  .has-trail.has-panel.view-open .view { top: 166px; max-height: calc(100% - var(--sheet, 56%) - 174px); }
  .atlas-map { right: 8px; left: auto; bottom: auto; top: 172px; width: 46px; padding: 4px; gap: 4px; }
  .has-panel .atlas-map { display: none; }
  .atlas-map-title, .atlas-row-name, .atlas-row-count { display: none; }
  .atlas-row { height: 44px; padding: 4px; align-content: center; }
  .atlas-bar { width: 100% !important; height: 10px; }
}

/* ---------------------------------------------------------------- a phone, its second pass (17 November 2026)
   Below 760 px only: the phone block above also takes a window 760 px wide, and what is added here leaves that window as it was.
   The picture first: a view's card folds to one line, the trail stays on one line and never cuts a word, the atlas's caveat
   stands in the legend's sheet, the map of the stack says a shelf's name when a bar is pressed, and the bar keeps to one row.
   Nothing here lies over the canvas with a backdrop blur (see .card). */
.atlas-say { display: none; }
@media (max-width: 759px) {
  /* The bar on one row. Every switch is at least 44 px wide as well as tall; where the words would still wrap the bar (a model
     system's longer name, the stand-in font), the viewer squeezes it in steps (viewer.js fitBar, data-squeeze). */
  .switch button, .bar-end .pill-button { min-width: 44px; }
  .bar[data-squeeze~="1"] { gap: 6px; }
  .bar[data-squeeze~="1"] .switch button { padding-inline: 6px; }
  .bar[data-squeeze~="1"] .bar-end .pill-button { padding-inline: 8px; }
  .bar[data-squeeze~="2"] .brand b { font-size: 16px; }
  .bar[data-squeeze~="2"] .switch button { padding-inline: 5px; font-size: 12.5px; }
  /* The page's name gives way last; it is still read out. */
  .bar[data-squeeze~="3"] .brand { position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); white-space: nowrap; }
  .bar[data-squeeze~="4"] .switch button { padding-inline: 4px; font-size: 12px; }
  /* Last, where six tabs and the List still do not fit (a 360 px phone, the stand-in font): the tabs' row scrolls sideways inside
     the bar, the bar keeps to one row and the List stays whole; each cut edge fades (viewer.js fadeTabs), and the tab of the
     view shown is brought into sight (showPressedTab). */
  .bar[data-squeeze~="5"] { flex-wrap: nowrap; }
  .bar[data-squeeze~="5"] .bar-end { flex: none; }
  .bar[data-squeeze~="5"] .switch { flex: 0 1 auto; min-width: 0; overflow-x: auto; overscroll-behavior-x: contain; scrollbar-width: none;
    -webkit-mask-image: linear-gradient(to right, transparent 0, #000 var(--fade-l, 0px), #000 calc(100% - var(--fade-r, 0px)), transparent 100%);
    mask-image: linear-gradient(to right, transparent 0, #000 var(--fade-l, 0px), #000 calc(100% - var(--fade-r, 0px)), transparent 100%); }
  .bar[data-squeeze~="5"] .switch::-webkit-scrollbar { display: none; }
  .bar[data-squeeze~="5"] .switch button { flex: none; }
  /* A view's card (the protein atlas, the Laws library, a model system's) folds to one line under the bar, or under the trail;
     a press opens it over the picture, and opening the legend folds it again (viewer.js). */
  .card-folds:not(.view-open) .view { display: none; }
  .card-folds .view-toggle { display: flex; position: absolute; top: max(68px, calc(var(--bar-height, 0px) + 8px)); left: max(16px, env(safe-area-inset-left, 0px)); max-width: calc(100% - 32px); align-items: center; gap: 12px; padding: 0 14px; font-weight: 500; z-index: 4; }
  .card-folds.has-map .view-toggle { max-width: calc(100% - 96px); }
  .card-folds .view-toggle > span:first-child { white-space: nowrap; overflow: hidden; }
  .card-folds.has-trail .view-toggle { top: max(116px, calc(var(--bar-height, 0px) + 56px)); }
  .card-folds.view-open .view { top: max(118px, calc(var(--bar-height, 0px) + 58px)); max-height: calc(100% - 118px - 96px); z-index: 4; }
  /* An example's mark stands in the opened card too: the card may cover the mark on the picture. */
  .card-folds.view-open .view-notice { display: block; margin: 0 0 6px; }
  .card-folds.has-trail.view-open .view { top: max(166px, calc(var(--bar-height, 0px) + 106px)); max-height: calc(100% - 166px - 96px); }
  .card-folds.has-panel.view-open .view { max-height: calc(100% - var(--sheet, 56%) - 126px); }
  .card-folds.has-trail.has-panel.view-open .view { max-height: calc(100% - var(--sheet, 56%) - 174px); }
  /* The trail never cuts a word: the steps in its middle give way to "…", then words from a step's end (atlas_nav.js). */
  .atlas-crumbs li:not(.is-here):not(:nth-last-child(2)):not([hidden]) { display: flex; }
  .atlas-crumbs li:nth-last-child(2) { max-width: none; }
  .atlas-crumbs li:nth-last-child(2)::before { display: inline; }
  .atlas-crumbs li:nth-last-child(2) .swatch { display: inline-block; }
  .atlas-crumbs li:first-child::before, .atlas-crumbs li.is-lead::before { display: none; }
  .atlas-crumb, .is-here .atlas-crumb { max-width: none; text-overflow: clip; }
  /* The atlas's caveat stands at the head of the legend's sheet, not over the picture (viewer.js renderLegend). */
  .caveat-in-legend .caveat { display: none; }
  /* Links in a card's or a panel's lists (sources, a protein's databases) are pressed as often as buttons: a line of 44 px. */
  .view details li a, .item-links a, .sources a { display: inline-block; min-width: 44px; min-height: 44px; line-height: 44px; }
  /* The hint (drag, zoom, choose) would lie under a panel's sheet. */
  .has-panel .hint { display: none; }
  /* The map of the stack: a column of bars 44 px wide that does not open under a pointer; a press on a bar, or the keyboard on
     it, brings its shelf near and says its name beside it (atlas_nav.js). */
  .atlas-map, .atlas-map:hover, .atlas-map:focus-within { width: 52px; }
  .atlas-say { display: flex; align-items: center; position: absolute; right: calc(max(8px, env(safe-area-inset-right, 0px)) + 58px); transform: translateY(-50%); z-index: 4; max-width: calc(100% - 96px); min-height: 36px; margin: 0; padding: 0 12px; border-radius: 8px; background: var(--bg-raised); box-shadow: 0 0 0 1px var(--line), 0 8px 20px -12px rgb(0 0 0 / .45); font-size: 13px; font-weight: 600; white-space: nowrap; pointer-events: none; }
  .atlas-say[hidden] { display: none; }
}
/* The legend's opening words, where a view gives them (on a phone, the protein atlas's caveat). */
.legend-lead { margin: 0 0 4px; padding: 4px 8px 8px; font-size: 12.5px; line-height: 1.4; color: var(--muted); border-bottom: 1px solid var(--line); }

/* ---------------------------------------------------------------- the origin-of-life view, a phone's third pass (17 November 2026)
   A view whose picture reaches the page's top edge (the origin view's water and free molecules: lineage.js drawsUnderBar) gives
   the bar's words a ground at every width: a fade of the page's own ground inside the bar's box, solid behind the words and gone
   at the bar's foot, so that nothing under the bar is veiled (the names on the picture keep below it). At 94 % the bar's muted
   words stand at 4.5 : 1 or more over the view's darkest head in pale water, and over white in dark. A painted gradient costs
   no frame; a backdrop blur halved the frame rate through Vulkan. */
.bar-ground .bar { background: linear-gradient(to bottom, color-mix(in srgb, var(--bg) 94%, transparent) 0, color-mix(in srgb, var(--bg) 94%, transparent) 65%, transparent); }
@media (max-width: 759px) {
  /* A model system's card, opened, shows its choices (the composition's form, the similarity), which a phone keeps from other cards:
     each its name over its select, which takes the card's width and so its words. */
  .model-card .view .card-marks { display: grid; grid-template-columns: minmax(0, 1fr); gap: 2px; }
  /* A timeline stands where the hint (drag, pinch, tap) would be, and over it: the hint gives way. */
  .has-timeline .hint { display: none; }
  /* Where the folded line and the rail's button would meet, the button steps under the line, and its levels and the opened card
     under it (viewer.js fitFolded). */
  .card-folds.rail-under .rail-toggle { top: max(116px, calc(var(--bar-height, 0px) + 56px)); }
  .card-folds.rail-under .rail, .card-folds.rail-under.view-open .view { top: max(166px, calc(var(--bar-height, 0px) + 106px)); }
  .card-folds.rail-under.view-open .view { max-height: calc(100% - 166px - 96px); }
}
`;
