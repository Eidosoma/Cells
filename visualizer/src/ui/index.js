// <cells-index>: every part as a list, grouped the way the current lens groups them.
// It is the text view of the map: usable without WebGL and from the keyboard.

import { h, emit, statusSwatch } from "./dom.js";

class CellsIndex extends HTMLElement {
  render({ sections, selected }) {
    this.sections = sections;
    this.selected = selected;
    if (!this.search) {
      this.search = h("input", {
        id: "cells-index-search",
        class: "index-search",
        type: "search",
        placeholder: "Find a part",
        "aria-label": "Find a part",
        oninput: () => this.fill(),
      });
      this.list = h("div", { class: "index-list" });
      this.append(h("div", { class: "index-head" }, this.search), this.list);
    }
    this.fill();
  }

  fill() {
    const query = this.search.value.trim().toLowerCase();
    const blocks = [];
    for (const section of this.sections) {
      // A section may be long (the proteins of a family): it shows its first rows, and typing
      // searches all of it. One marked searchOnly is listed only while something is typed.
      if (section.searchOnly && !query) continue;
      const found = section.entities.filter((entity) => !query || [entity.label, entity.id, entity.short, entity.keywords].some((text) => text && text.toLowerCase().includes(query)));
      const limit = section.limit || Infinity;
      const rows = found
        .slice(0, limit)
        .map((entity) =>
          h(
            "button",
            {
              class: "index-row" + (entity.id === this.selected ? " is-on" : "") + (entity.sign ? " has-sign" : ""),
              type: "button",
              onclick: () => emit(this, "cells-select", { id: entity.id, fly: true }),
            },
            statusSwatch(entity.swatch || entity.status),
            h("span", { class: "index-name" }, entity.label),
            // A further sign with its words (the protein atlas: where a species differs).
            entity.sign ? h("span", { class: `swatch swatch-${entity.sign.swatch}`, role: "img", title: entity.sign.title, "aria-label": entity.sign.title }) : null
          )
        );
      if (found.length > limit) rows.push(h("p", { class: "index-more" }, `and ${(found.length - limit).toLocaleString("en-US")} more: type a name or an identifier to find one`));
      if (rows.length) blocks.push(h("section", {}, h("h3", {}, section.label), rows));
    }
    this.list.replaceChildren(...(blocks.length ? blocks : [h("p", { class: "index-empty" }, "No part matches.")]));
  }
}

customElements.define("cells-index", CellsIndex);
