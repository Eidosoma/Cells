// <cells-panel>: everything known about the selected part, in plain words first.

import { h, emit, formatDate, statusSwatch } from "./dom.js";

const KIND_ORDER = ["modelled_by", "shown_as", "implements", "requires", "reads", "writes", "provides", "conflicts", "operator_of", "wraps", "runs", "compared_with", "runs_on", "delivers", "extends", "uses"];
// How a relation reads from the far end.
const INVERSE = {
  modelled_by: "holds the law for",
  shown_as: "stands in the cell view for",
  implements: "is behind",
  requires: "is required by",
  reads: "is read by",
  writes: "is written by",
  provides: "is provided by",
  operator_of: "has the operator",
  wraps: "is wrapped by",
  runs: "is run by",
  compared_with: "is the reference for",
  runs_on: "runs",
  delivers: "is delivered by",
  extends: "would be extended by",
  uses: "is used by",
};
const SHOWN = 7;

class CellsPanel extends HTMLElement {
  show({ model, entity }) {
    this.replaceChildren();
    this.hidden = !entity;
    if (!entity) return;
    const status = model.statuses.get(entity.status);
    const chips = [];
    // A part may bring its own chips (the protein atlas: how sure the mapping is, and where the law acts).
    for (const chip of entity.chips || []) {
      chips.push(h("span", { class: chip.swatch ? "chip" : "chip chip-plain", title: chip.title || "" }, chip.swatch ? statusSwatch(chip.swatch) : null, chip.label));
    }
    if (status) {
      chips.push(h("span", { class: "chip", title: status.description }, statusSwatch(entity.status), status.label, entity.as_of ? ` · ${formatDate(entity.as_of)}` : ""));
    }
    const representation = (model.raw.representations || []).find((item) => item.id === entity.representation);
    if (representation) chips.push(h("span", { class: "chip chip-plain", title: representation.description }, representation.label));
    for (const groupId of entity.runs_in || []) {
      const group = (model.raw.model_groups || []).find((item) => item.id === groupId);
      if (group) chips.push(h("span", { class: "chip chip-plain", title: group.description }, `Runs in: ${group.label}`));
    }

    const body = h("div", { class: "panel-body" });
    if (entity.plain) body.append(h("p", { class: "panel-plain" }, entity.plain));
    if (entity.note) body.append(h("p", { class: "panel-note" }, entity.note));
    if (entity.detail) body.append(h("p", { class: "panel-detail" }, entity.detail));
    // What one species' atlas found for this unit (the protein atlas, on a species other than the inventory's).
    if (entity.finding) {
      const found = entity.finding;
      body.append(
        h(
          "div",
          { class: "panel-finding" },
          h("p", { class: "finding-title" }, found.title, found.organism ? h("i", {}, ` · ${found.organism}`) : null),
          h("p", { class: "finding-line" }, found.swatch ? statusSwatch(found.swatch) : null, found.text),
          found.note ? h("p", { class: "finding-note" }, found.note) : null,
          found.more ? h("p", { class: "finding-more" }, found.more) : null
        )
      );
    }
    if (entity.facts?.length) {
      body.append(
        h("dl", { class: "facts" }, entity.facts.map(([label, value]) => [h("dt", {}, label), h("dd", {}, value)]))
      );
    }
    if (entity.members?.length) {
      const title = entity.kind === "gate" ? "Deliverables" : "Contains";
      body.append(this.list(title, entity.members.map((member) => h("li", {}, member.label, member.detail ? h("span", { class: "quiet" }, ` · ${member.detail}`) : null))));
    }
    if (entity.chart) {
      // A record of this part over the run, with the playhead (the replay view).
      const trace = document.createElement("cells-trace");
      body.append(trace);
      trace.data = entity.chart;
    }
    // A figure the view draws itself for this part (the tissue's switch, for a chosen cell): its own element.
    if (entity.figure && typeof entity.figure === "object" && entity.figure.nodeType === 1) body.append(entity.figure);
    // A door into another view: which view, and what to show there (the Protein atlas on one set of a species' proteins).
    // A door is pressed: it opens another view, or does what its own view does with it ("Look closer" at a machine). An item that
    // says `says` is words in a door's place and opens nothing (the Laws library on a unit's laws that it does not show).
    for (const door of entity.doors || []) body.append(!door.says ? h("p", { class: "panel-door" }, h("button", { class: "link-button", type: "button", onclick: () => emit(this, "cells-door", door) }, `${door.label} →`)) : h("p", { class: "panel-door quiet" }, door.label));
    for (const section of entity.sections || []) {
      if (section.items?.length) body.append(this.list(section.title, section.items.map(item), "items", section.note, section.count === false ? null : section.items.length));
    }
    // Background a reader may want but need not see at once (how a replay was derived).
    for (const more of entity.disclosures || []) {
      if (more.lines?.length) body.append(h("details", { class: "panel-more" }, h("summary", {}, more.title), h("ul", {}, more.lines.map((line) => h("li", {}, line)))));
    }
    // Parts of the scene this one points at without a relation of its own (a run and the engine parts it ran).
    for (const group of entity.related || []) {
      const parts = group.ids.map((id) => model.get(id)).filter(Boolean);
      if (!parts.length) continue;
      // Two parts may share a name (a model and the capability it gives), so each says where it sits.
      const items = parts.map((part) =>
        h(
          "li",
          {},
          h("button", { class: "link-button", type: "button", onclick: () => emit(this, "cells-select", { id: part.id, fly: true }) }, statusSwatch(part.swatch || part.status), part.label),
          h("span", { class: "quiet" }, ` · ${kindName(part, model)}`)
        )
      );
      body.append(this.list(group.title, items, "connection"));
    }
    // Parts the view makes itself that this one leads to (a family's proteins; a protein's family).
    for (const group of entity.opens || []) {
      if (!group.items?.length) continue;
      const items = group.items.map((part) =>
        h("li", {}, h("button", { class: "link-button", type: "button", onclick: () => emit(this, "cells-select", { id: part.id, fly: true }) }, statusSwatch(part.swatch), part.label))
      );
      const more = group.more > 0 ? h("li", { class: "quiet" }, `and ${group.more.toLocaleString("en-US")} more: the list finds each by name`) : null;
      body.append(this.list(group.title, more ? [...items, more] : items, "opens", null, group.count));
    }
    const connections = this.connections(model, entity);
    if (connections.length) body.append(h("h3", {}, "Connections"), ...connections);
    if (entity.sources?.length) {
      body.append(
        h("h3", {}, "Sources"),
        h(
          "ul",
          { class: "sources" },
          entity.sources.map((source) => {
            const url = model.sourceUrl(source);
            const name = url ? h("a", { href: url, target: "_blank", rel: "noopener" }, source.path) : h("span", {}, source.path);
            return h("li", {}, name, source.where ? h("span", { class: "quiet" }, ` · ${source.where}`) : null);
          })
        )
      );
    }

    this.append(
      h(
        "header",
        { class: "panel-head" },
        h("div", {}, h("p", { class: "eyebrow" }, entity.eyebrow || kindName(entity, model)), h("h2", {}, entity.label)),
        h("button", { class: "icon-button", type: "button", "aria-label": "Close", onclick: () => emit(this, "cells-select", { id: null }) }, "×")
      ),
      ...(chips.length ? [h("div", { class: "chips" }, chips)] : []),
      body
    );
    this.scrollTop = 0;
  }

  connections(model, entity) {
    const groups = new Map();
    for (const link of model.links(entity.id)) {
      const kind = model.kinds.get(link.relation.kind);
      const directed = kind?.directed !== false;
      const phrase = !directed || link.outward ? kind?.label || link.relation.kind : INVERSE[link.relation.kind] || kind?.label;
      const key = `${link.relation.kind}:${directed && !link.outward ? "in" : "out"}`;
      if (!groups.has(key)) groups.set(key, { kind: link.relation.kind, phrase, links: [] });
      groups.get(key).links.push(link);
    }
    const ordered = [...groups.values()].sort((a, b) => KIND_ORDER.indexOf(a.kind) - KIND_ORDER.indexOf(b.kind));
    return ordered.map((group) => {
      group.links.sort((a, b) => (b.relation.weight || 0) - (a.relation.weight || 0));
      const items = group.links.map((link) => {
        const other = model.get(link.other);
        return h(
          "li",
          {},
          h("button", { class: "link-button", type: "button", onclick: () => emit(this, "cells-select", { id: other.id, fly: true }) }, statusSwatch(other.swatch || other.status), other.label),
          link.relation.label ? h("span", { class: "quiet" }, ` · ${link.relation.label}`) : null
        );
      });
      return this.list(capitalise(group.phrase), items, "connection");
    });
  }

  list(title, items, className = "", note = null, count = items.length) {
    const first = items.slice(0, SHOWN), rest = items.slice(SHOWN);
    // A list whose items are no count of anything (a card's standing, in the Experiments landing's detail) says no number.
    const block = h("div", { class: `panel-list ${className}` }, h("h4", {}, title, count === null ? null : h("span", { class: "quiet" }, ` ${count.toLocaleString("en-US")}`)), note ? h("p", { class: "list-note" }, note) : null, h("ul", {}, first));
    if (rest.length) block.append(h("details", {}, h("summary", {}, `Show ${rest.length} more`), h("ul", {}, rest)));
    return block;
  }
}

/** One entry of a part's own list: a law, a gene product, a reference structure. Links open outside the page. */
export function item(entry) {
  const links = (entry.links || []).filter((link) => /^https:\/\//.test(link.url));
  return h(
    "li",
    { class: "item" },
    h(
      "div",
      { class: "item-head" },
      h("span", { class: entry.code ? "item-label code" : "item-label" }, entry.label),
      entry.tag ? h("span", { class: "tag", title: entry.tag_title || "" }, entry.tag) : null
    ),
    entry.detail ? h("p", { class: "item-detail" }, entry.detail) : null,
    (entry.lines || []).map((line) => h("p", { class: "item-line" }, line)),
    entry.note ? h("p", { class: "item-note" }, entry.note) : null,
    links.length ? h("p", { class: "item-links" }, links.map((link, index) => [index ? " · " : null, h("a", { href: link.url, target: "_blank", rel: "noopener" }, link.text)])) : null
  );
}

function kindName(entity, model) {
  if (entity.kind === "capability") return "Capability";
  if (entity.kind === "scale") return "Scale";
  const group = model.groups.find((item) => item.id === entity.group);
  return group ? group.label : entity.kind;
}

const capitalise = (text) => text.charAt(0).toUpperCase() + text.slice(1);

customElements.define("cells-panel", CellsPanel);
