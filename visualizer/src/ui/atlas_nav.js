// The ways around a species' own proteins in the protein atlas (docs/ATLAS_LOOK.md, decided 16 November 2026):
//   the trail    where the visitor is, always said: the species, the shelf in focus, a side shown alone, the
//                family open (or "Opening …" while its proteins are fetched), the protein chosen. Each step is a
//                button back to it; the arrow, and Escape (proteins.js escape()), go back one level.
//   the search   one field in view that finds a protein by its gene, its name or its identifier, also inside a
//                family not yet opened (from the names file beside a large catalogue's members), the families'
//                lines by name, and the shelves. On a phone it opens from a button at the trail's end.
//   the map      the stack as a small map: each shelf a bar of its sides, the one in focus marked, and where a
//                family is open. A press brings a shelf near. It stands in for the legend's list of shelves.
// The lens gives what they show (ProteinLens.ownChrome().nav) and does what they ask; this draws them.

import { h } from "./dom.js";

const number = (n) => Number(n).toLocaleString("en-US");
const SIDE_SWATCH = { outside: "own-side-outside", in: "own-side-in", inside: "own-side-inside", "not known": "own-unknown" };
const swatch = (side) => h("span", { class: `swatch swatch-${SIDE_SWATCH[side] || "own-family"}`, "aria-hidden": "true" });

/** Draw the trail, the search and the map for the atlas's own proteins, or put them away (nav null). */
export function renderAtlasNav(viewer, nav) {
  const lens = viewer.current;
  if (!viewer.atlasNav) {
    const trail = h("nav", { class: "atlas-trail card", "aria-label": "Where you are among the proteins", hidden: true });
    const map = h("nav", { class: "atlas-map card", "aria-label": "The stack of shelves", hidden: true });
    viewer.frame.append(trail, map);
    viewer.atlasNav = { trail, map, search: null, findOpen: false };
  }
  const box = viewer.atlasNav;
  const on = Boolean(nav) && viewer.state.lens === "proteins";
  box.trail.hidden = !on;
  box.map.hidden = !on || !nav?.map;
  viewer.frame.classList.toggle("has-trail", on);
  viewer.frame.classList.toggle("has-map", on && Boolean(nav?.map));
  if (!on) return;
  drawTrail(viewer, lens, nav, box);
  if (nav.map) drawMap(lens, nav.map, box.map);
}

function drawTrail(viewer, lens, nav, box) {
  // The search is made once for each species, so that what is typed and the focus stay while the trail is drawn again.
  if (!box.search || box.search.species !== nav.species) box.search = makeSearch(viewer, lens, nav);
  const levels = nav.trail || [];
  const back = h("button", { class: "atlas-back", type: "button", disabled: levels.length < 2, "aria-label": levels.length > 1 ? `Back to ${levels[levels.length - 2].label}` : "Back", title: "Back one level (Escape)", onclick: () => lens.escape() }, h("span", { "aria-hidden": "true" }, "←"));
  const crumbs = h(
    "ol",
    { class: "atlas-crumbs" },
    levels.map((level, index) => {
      const last = index === levels.length - 1;
      return h(
        "li",
        { class: `${last ? "is-here" : ""}${level.opening ? " is-opening" : ""}`.trim() || null },
        level.side ? swatch(level.side) : null,
        last || level.opening ? h("span", { class: "atlas-crumb", "aria-current": last ? "location" : null, role: level.opening ? "status" : null }, level.label) : h("button", { class: "atlas-crumb", type: "button", title: level.title, dataset: { level: level.id }, onclick: () => lens.goTo(level.id) }, level.label)
      );
    })
  );
  const find = h("button", { class: "atlas-find-open", type: "button", "aria-expanded": String(box.findOpen), "aria-controls": "atlas-find", title: "Find a protein, a family or a shelf", onclick: () => toggleFind(viewer, box, !box.findOpen) }, h("span", { "aria-hidden": "true" }, "Find"));
  box.trail.classList.toggle("is-finding", box.findOpen);
  // Drawn again, the trail keeps the keyboard where it was: on the arrow, on a step (or the arrow, if that step is
  // gone), or on the picture, so that Escape still reaches the page after a press on the trail.
  const had = viewer.shadowRoot.activeElement;
  const kept = had && box.trail.contains(had) && !box.search.box.contains(had) ? (had.classList.contains("atlas-back") ? "back" : had.dataset.level ? `level:${had.dataset.level}` : had.classList.contains("atlas-find-open") ? "find" : null) : null;
  box.trail.replaceChildren(box.search.box, h("div", { class: "atlas-where" }, back, crumbs, find));
  if (kept) {
    const target = kept === "find" ? find : kept.startsWith("level:") ? crumbs.querySelector(`[data-level="${kept.slice(6)}"]`) || back : back;
    (target.disabled ? viewer.canvas : target).focus({ preventScroll: true });
  }
  // Where the steps do not fit, the middle ones give way to "…" (its title names them), the first and the last stay whole.
  requestAnimationFrame(() => fitCrumbs(crumbs));
}

function fitCrumbs(crumbs) {
  const items = [...crumbs.children];
  const over = () => crumbs.scrollWidth > crumbs.clientWidth + 1;
  if (!over()) return;
  const tighten = () => {
    crumbs.classList.add("is-tight");
    const last = items.at(-1).querySelector(".atlas-crumb");
    if (last) last.title = last.textContent;
  };
  if (items.length < 3) return tighten();
  const more = h("li", { class: "atlas-more" }, h("span", { class: "atlas-crumb" }, "…"));
  items[0].after(more);
  // The steps between the first and the one above the last give way first; then the last is cut short; the step
  // just above the last (where the arrow goes) gives way only if even that is not enough.
  for (const item of items.slice(1, -2)) {
    if (!over()) break;
    item.hidden = true;
  }
  if (over()) tighten();
  if (over()) items.at(-2).hidden = true;
  if (!items.some((item) => item.hidden)) more.remove();
  else more.title = items.filter((item) => item.hidden).map((item) => item.textContent).join(" › ");
}

function toggleFind(viewer, box, open) {
  box.findOpen = open;
  box.trail.classList.toggle("is-finding", open);
  box.trail.querySelector(".atlas-find-open")?.setAttribute("aria-expanded", String(open));
  if (open) box.search.input.focus({ preventScroll: true });
  else box.search.close();
}

function makeSearch(viewer, lens, nav) {
  const input = h("input", { id: "atlas-find", class: "atlas-find", type: "search", placeholder: nav.finding, "aria-label": nav.finding, autocomplete: "off", spellcheck: "false" });
  const results = h("div", { class: "atlas-results", role: "listbox", "aria-label": "What the search finds", hidden: true });
  const box = h("div", { class: "atlas-findbox" }, input, results);
  let asked = 0, timer = null;
  const close = () => {
    results.hidden = true;
    results.replaceChildren();
  };
  const choose = (found) => {
    close();
    input.blur();
    if (viewer.atlasNav?.findOpen && viewer.clientWidth < 760) toggleFind(viewer, viewer.atlasNav, false);
    lens.reveal(found);
  };
  const row = (found, label, where) =>
    h("button", { class: "atlas-hit", type: "button", role: "option", onclick: () => choose(found) }, found.side ? swatch(found.side) : h("span", { class: "swatch swatch-own-family", "aria-hidden": "true" }), h("span", { class: "atlas-hit-name" }, label), h("span", { class: "atlas-hit-where" }, where));
  const shelfName = (shelves, id) => (id === null ? "No place known" : shelves.shelfById.get(id)?.label || "");
  const fill = async () => {
    const query = input.value, ticket = ++asked;
    if (query.trim().length < 2) return close();
    const shelves = lens.mounted?.shelves;
    if (shelves?.kind === "families" && !shelves.names && !shelves.namesError) {
      results.hidden = false;
      results.replaceChildren(h("p", { class: "atlas-note", role: "status" }, `Reading the names of ${number(shelves.total)} proteins…`));
    }
    const found = await lens.searchOwn(query);
    if (ticket !== asked || !found) return;
    const several = shelves.several;
    const block = (title, rows, more) => (rows.length ? h("section", {}, h("h4", {}, title), rows, more ? h("p", { class: "atlas-note" }, `and ${number(more)} more: type more of the name`) : null) : null);
    const proteins = found.proteins.map((item) => row(item, item.gene && item.gene !== item.label ? `${item.gene} · ${item.label}` : item.label, [several ? shelfName(shelves, item.shelf) : "", item.under].filter(Boolean).join(" · ")));
    const families = found.families.map((line) => row({ key: line.within && !line.members ? line.within.key : line.key, side: line.side }, `${line.label} · ${number(line.count)}`, several ? shelfName(shelves, line.shelf ?? null) : shelves.districtLabel(line)));
    const shelfRows = found.shelves.map((item) => row({ key: item.key }, item.label, `${number(item.count)} proteins`));
    const blocks = [block(`Proteins · ${number(found.total)}`, proteins, found.more), block("Families", families, found.familiesMore), block("Shelves", shelfRows, 0)].filter(Boolean);
    const missing = found.namesMissing ? h("p", { class: "atlas-note" }, `The names of the proteins inside its families could not be read${shelves.namesError ? ` (${shelves.namesError})` : ""}: the search finds families and shelves.`) : null;
    results.hidden = false;
    results.replaceChildren(...(blocks.length ? blocks : [h("p", { class: "atlas-note" }, "Nothing of this species' proteins matches.")]), ...(missing ? [missing] : []));
  };
  input.addEventListener("input", () => {
    clearTimeout(timer);
    timer = setTimeout(fill, 120);
  });
  input.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      // Escape in the field empties it (and on a phone puts it away); it does not also step the trail back.
      event.stopPropagation();
      if (input.value) input.value = "";
      else if (viewer.atlasNav?.findOpen) toggleFind(viewer, viewer.atlasNav, false);
      close();
    } else if (event.key === "ArrowDown") {
      const first = results.querySelector(".atlas-hit");
      if (first) (event.preventDefault(), first.focus());
    } else if (event.key === "Enter") {
      const first = results.querySelector(".atlas-hit");
      if (first) (event.preventDefault(), first.click());
    }
  });
  results.addEventListener("keydown", (event) => {
    const hits = [...results.querySelectorAll(".atlas-hit")], at = hits.indexOf(event.target);
    if (event.key === "ArrowDown" && at >= 0) (event.preventDefault(), hits[Math.min(hits.length - 1, at + 1)].focus());
    else if (event.key === "ArrowUp" && at >= 0) (event.preventDefault(), (at === 0 ? input : hits[at - 1]).focus());
    else if (event.key === "Escape") (event.stopPropagation(), close(), input.focus());
  });
  // A press elsewhere puts the results away.
  viewer.shadowRoot.addEventListener("pointerdown", (event) => {
    if (!event.composedPath().includes(box)) close();
  });
  return { species: nav.species, box, input, results, close, fill };
}

function drawMap(lens, map, box) {
  const bar = (counts, count) =>
    h(
      "span",
      { class: "atlas-bar", style: `width:${Math.max(16, (100 * count) / map.most).toFixed(1)}%`, "aria-hidden": "true" },
      ["outside", "in", "inside", "not known"].filter((side) => counts[side]).map((side) => h("i", { class: `atlas-seg atlas-seg-${side === "not known" ? "unknown" : side}`, style: `flex:${counts[side]}` }))
    );
  box.replaceChildren(
    h("p", { class: "atlas-map-title" }, "Stack", h("span", { class: "atlas-map-key" }, "beyond · in · enclosed · not known")),
    ...map.rows.map((row) =>
      h(
        "button",
        { class: `atlas-row${row.id === map.active ? " is-on" : ""}${row.open ? " has-open" : ""}`, type: "button", "aria-pressed": String(row.id === map.active), "aria-label": `${row.label}, ${number(row.count)} proteins${row.open ? ", a family open" : ""}`, title: `${row.label} · ${number(row.count)}`, dataset: { shelf: row.id }, onclick: () => lens.showShelf(row.id) },
        h("span", { class: "atlas-row-name" }, row.label, row.open ? h("span", { class: "atlas-row-open" }, " · open") : null),
        h("span", { class: "atlas-row-count" }, number(row.count)),
        bar(row.counts || map.whole, row.counts ? row.count : map.most)
      )
    )
  );
}
