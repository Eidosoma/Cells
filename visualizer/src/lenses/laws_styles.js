// The Laws library's legend swatches: the page's legend draws a swatch as
// <span class="swatch swatch-{id}"> (ui/dom.js statusSwatch), so each of the view's marks
// (laws.js MARKS) has a rule here, drawn as the mark is drawn in the room. None of them is
// dashed, outlined in a status colour or coloured by a status: those are the page's statuses.

export const LAWS_CSS = `
.swatch-laws-declared { background: var(--ghost); }
.swatch-laws-design { background: color-mix(in srgb, var(--plate) 45%, transparent); box-shadow: inset 0 0 0 1.5px var(--edge); }
.swatch-laws-height { background: repeating-linear-gradient(0deg, var(--ghost) 0 2px, transparent 2px 4px); }
.swatch-laws-rack { background: var(--plate); box-shadow: inset 0 0 0 2px var(--plate-edge); }
.swatch-laws-case { background: var(--plate-edge); height: 7px; vertical-align: 1px; }
.swatch-laws-slot { background: linear-gradient(var(--ghost), var(--ghost)) center / 8px 5px no-repeat, var(--plate); box-shadow: inset 0 0 0 1px var(--plate-edge); }
.swatch-laws-block { background: linear-gradient(var(--plate-edge), var(--plate-edge)) center 2px / 12px 4px no-repeat, var(--plate); }
.swatch-laws-next { background: color-mix(in srgb, var(--edge) 55%, transparent); }
.swatch-laws-none { background: color-mix(in srgb, var(--edge) 55%, transparent); width: 18px; }
.swatch-laws-found { background: linear-gradient(90deg, var(--ghost) 0 50%, color-mix(in srgb, var(--ghost) 30%, var(--bg)) 50%); }
.swatch-laws-empty { background: color-mix(in srgb, var(--ghost) 25%, transparent); }
.swatch-laws-chosen { background: var(--accent); box-shadow: 0 0 6px var(--accent); }
.swatch-laws-room { background: var(--plate); box-shadow: inset 0 0 0 1px var(--plate-edge); }
.laws-navigation { display:grid; gap:9px; }
.bar-card:has(.laws-navigation) { display:grid; width:248px; max-height:52%; overflow:auto; }
.view:has(.laws-navigation) { max-height:calc(100% - 116px); overflow:auto; scrollbar-width:thin; }
.view:has(.laws-navigation) .stats:empty { display:none; }
.laws-control { display:grid; gap:3px; min-width:0; }
.laws-control > span { font-size:11.5px; color:var(--muted); font-weight:600; }
.laws-navigation .run-select { width:100%; max-width:100%; min-width:0; }
.laws-control input[type=range] { width:100%; accent-color:var(--accent); }
.laws-filters summary { color:var(--muted); font-size:12px; cursor:pointer; }
.laws-filters[open] summary { margin-bottom:5px; }
.laws-tally,.laws-guide,.laws-subject { margin:0; line-height:1.4; }
.laws-guide,.laws-tally { font-size:12px; color:var(--muted); }
.laws-tally { font-variant-numeric:tabular-nums; }
.laws-subject { font:600 15px/1.35 var(--font-display); overflow-wrap:anywhere; }
.laws-action { border:1px solid var(--line); border-radius:7px; background:var(--bg-raised); color:var(--fg); padding:7px 9px; text-align:left; font-size:12px; }
.laws-action:hover,.laws-action:focus-visible { border-color:var(--accent); }
.laws-primary { color:var(--bg-raised); background:var(--fg); border-color:var(--fg); text-align:center; }
.laws-results { display:grid; gap:4px; }.laws-results button { overflow-wrap:anywhere; }
.laws-sets { display:grid; grid-template-columns:repeat(3,1fr); gap:4px; border-block:1px solid var(--line); padding:7px 0; text-align:center; }
.laws-sets strong,.laws-sets span { display:block; }.laws-sets span { font-size:11px; color:var(--muted); }
.label-atlas-subject,.label-atlas-orbit { font-weight:650; }
.label-atlas-subject,.label-atlas-orbit,.label-atlas-model,.label-atlas-node,.label-atlas-piece,.label-atlas-family,.label-atlas-count { color:var(--fg); background:color-mix(in srgb,var(--bg-raised) 86%,transparent); font-size:12px; line-height:1.25; padding:2px 5px; border-radius:4px; }
.label-atlas-subject,.label-atlas-orbit { box-shadow:inset 0 -2px var(--line); }
.label-atlas-deck { color:var(--muted); text-transform:uppercase; font-size:10px; letter-spacing:.06em; }
.label-atlas-count { border-radius:50%; font-variant-numeric:tabular-nums; }
.swatch-laws-atlas-island,.swatch-laws-atlas-first,.swatch-laws-atlas-route,.swatch-laws-atlas-requires,.swatch-laws-atlas-requiredBy { background:light-dark(#087b70,#72d7c7); }
.swatch-laws-atlas-island { clip-path:polygon(25% 0,75% 0,100% 50%,75% 100%,25% 100%,0 50%); }
.swatch-laws-atlas-route { height:3px; }.swatch-laws-atlas-dock { background:var(--edge); transform:rotate(45deg) scale(.76); }
.swatch-laws-atlas-inner,.swatch-laws-atlas-reads { background:light-dark(#346ba0,#82b9ee); }
.swatch-laws-atlas-kind,.swatch-laws-atlas-ledgers,.swatch-laws-atlas-shared { background:light-dark(#645ca8,#b6b2ff); }
.swatch-laws-atlas-writes { background:light-dark(#a45619,#ffb470); }
.swatch-laws-atlas-direct { background:light-dark(#375c70,#a2c7d4); }
.swatch-laws-atlas-owns { background:light-dark(#53667a,#9caab8); }
.swatch-laws-atlas-provides { background:light-dark(#377556,#85d1ac); }
.swatch-laws-atlas-conflicts { background:light-dark(#aa4755,#ffa4ab); }
@media(max-width:759px) { .view:has(.laws-navigation) { max-height:min(49%,415px); }.laws-navigation {gap:7px;} }
@media(pointer:coarse) { .laws-action,.laws-control input[type=range] { min-height:44px; } }
`;
