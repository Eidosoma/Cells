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
.frame.laws-space {
  color-scheme:dark; --bg:#091524; --bg-glow:#142941; --bg-raised:#101f32; --fg:#e5f4fa;
  --muted:#a7beca; --line:#2e4659; --accent:#83e9df; --plate:#152b3e; --edge:#aac5d0; --ghost:#8298ab;
  color:var(--fg);
}
.laws-space .stage { background:#081322; }
.laws-space .bar { background:linear-gradient(to bottom,#081320f5,transparent); }
.laws-space .card { background:color-mix(in srgb,var(--bg-raised) 95%,transparent); }
.label-star-family,.label-star-quiet,.label-star-piece,.label-star-subject,.label-star-target,.label-star-sector,.label-star-verb {
  color:#d9eaf2; background:#0c1c2ce8; border:1px solid #3b5767; border-radius:4px;
  padding:2px 6px; font:500 12px/1.2 var(--font-body); text-shadow:0 1px 2px #07121e;
}
.label-star-family { border-color:#47707f; }
.label-star-quiet { color:#a1b4c0; border-color:#324754; }
.label-star-sector { background:transparent; border:0; color:#adcdde; font:600 10px/1.2 var(--font-display); letter-spacing:.14em; text-transform:uppercase; pointer-events:none; }
.label-star-subject { color:#ebfffc; border-color:#82e6d9; padding:4px 7px; font-weight:650; }
.label-star-target { color:#edf7fb; border-color:#58788c; }
.label-star-verb { color:#c6f3ef; background:#102730ee; border:0; font-size:11px; pointer-events:none; }
.star-overlay {
  position:absolute; z-index:3; left:max(10px,var(--star-left)); right:max(10px,var(--star-right));
  bottom:calc(max(28px,env(safe-area-inset-bottom,0px)) + var(--star-bottom)); display:grid; justify-items:center; pointer-events:none;
}
.star-console { pointer-events:auto; min-width:0; max-width:100%; color:#e5f4fa; background:#0c1c2bf7;
  border:1px solid #365467; border-radius:12px; box-shadow:0 6px 24px #02071166; padding:7px 10px; }
.star-overview-console,.star-flight-console,.star-breadcrumbs,.star-matrix header,.star-matrix-filters,.star-pagination { display:flex; align-items:center; gap:8px; }
.star-console .laws-action { white-space:nowrap; }
.star-console button:focus-visible { outline:2px solid #9bf4e7; }
.star-overview-console .laws-primary { background:#b5f4e8; color:#102630; border-color:#b5f4e8; }
.star-family-index,.star-family-guide { display:grid; gap:5px; }
.star-family-index summary,.star-route-list summary { cursor:pointer; color:var(--muted); font-size:12px; padding:3px 0; }
.star-family-index[open] .laws-action,.star-route-list[open] .laws-action { display:block; width:100%; text-align:left; margin-top:5px; }
.star-family-guide .laws-action { white-space:normal; }
.star-destination small { display:block; color:var(--muted); padding:2px 0 5px; }
.star-scope { padding-inline:4px; color:#bad0db; font-size:12px; }
.star-flight-console { flex-wrap:wrap; }
.star-breadcrumbs { flex:1 1 auto; overflow-x:auto; padding:3px; min-width:0; max-width:100%; scrollbar-width:thin; }
.star-breadcrumbs > * { flex:none; }
.star-stop,.star-matrix td,.star-matrix th { font-size:12px; }
.star-stop { color:#efd1a1; padding:5px 2px; }
.star-stop[aria-current] { color:#f2ffff; font-weight:650; }
.star-hop { color:#b7a07c; font-size:11px; }
.star-flight-console .laws-control { display:flex; gap:6px; align-items:center; }
.star-flight-console .run-select { width:auto; padding:4px 6px; }
.star-destinations,.star-model-pair { display:grid; gap:5px; }
.star-destinations .laws-action { border-left:2px solid var(--accent); }
.swatch-star-trail { background:#e8b97a; height:3px; }
.swatch-star-piece { width:9px; height:9px; border-radius:50%; background:#9bf3ea; box-shadow:0 0 5px #83e9df; }
.swatch-star-design { width:10px; height:10px; border:1.5px solid #e9bc87; border-radius:50%; background:transparent; }
.star-matrix { width:min(620px,100%); display:grid; gap:9px; padding:13px; }
.star-matrix h3 { color:#e7f4fa; font:600 16px var(--font-display); }
.star-matrix header,.star-pagination { justify-content:space-between; }
.star-model-pair { grid-template-columns:repeat(2,minmax(0,1fr)); gap:8px; }
.star-matrix-filters { flex-wrap:wrap; gap:4px; }
.star-matrix-filters button,.star-pagination button { padding:4px 8px; border:1px solid var(--line); border-radius:6px; color:var(--muted); font-size:12px; }
.star-matrix-filters [aria-pressed=true] { color:var(--fg); border-color:#7bb6b6; background:#1c3945; }
.star-pagination button:disabled { opacity:.45; }
.star-table-scroll { max-height:min(32vh,320px); overflow:auto; overscroll-behavior:contain; scrollbar-width:thin; }
.star-matrix table { width:100%; border-collapse:collapse; table-layout:fixed; }
.star-matrix th,.star-matrix td { padding:5px; border-bottom:1px solid var(--line); text-align:left; overflow-wrap:anywhere; }
.star-matrix th:first-child { width:48%; }.star-matrix th { font-weight:550; }
.star-matrix thead { position:sticky; top:0; background:#102235; }
.star-matrix tbody button { text-align:left; color:#d2ecec; padding:3px 0; }
.star-membership { color:#b4dfed; }.star-membership.inner,.star-membership.kind { color:#d0b7eb; }
.star-pagination { font-size:12px; color:var(--muted); }
.star-matrix-enter { animation:star-drawer-in .23s ease-out; }
@keyframes star-drawer-in { from { transform:translateY(14px); opacity:0; } to { transform:translateY(0); opacity:1; } }
@media(prefers-reduced-motion:reduce) { .star-matrix-enter { animation:none; } }
@media(max-width:759px) {
  .star-overlay { bottom:calc(max(62px,env(safe-area-inset-bottom,0px)) + var(--star-bottom)); }
  .star-scope { display:none; }.star-console { padding:5px 7px; }.star-breadcrumbs { flex-basis:100%; }
  .star-flight-console { gap:2px; }.star-flight-console .laws-control { margin-inline:auto; }
  .star-matrix { padding:8px;gap:6px; }.star-table-scroll { max-height:23vh; }
  .laws-space.has-panel .star-overlay,.laws-space.view-open .star-overlay { visibility:hidden; }
  .laws-space.view-open .star-overlay:has(.star-matrix) { visibility:visible; }
}
`;
