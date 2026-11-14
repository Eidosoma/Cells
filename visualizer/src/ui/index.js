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
      const rows = section.entities
        .filter((entity) => !query || [entity.label, entity.id, entity.short, entity.keywords].some((text) => text && text.toLowerCase().includes(query)))
        .map((entity) =>
          h(
            "button",
            {
              class: "index-row" + (entity.id === this.selected ? " is-on" : ""),
              type: "button",
              onclick: () => emit(this, "cells-select", { id: entity.id, fly: true }),
            },
            statusSwatch(entity.swatch || entity.status),
            h("span", { class: "index-name" }, entity.label)
          )
        );
      if (rows.length) blocks.push(h("section", {}, h("h3", {}, section.label), rows));
    }
    this.list.replaceChildren(...(blocks.length ? blocks : [h("p", { class: "index-empty" }, "No part matches.")]));
  }
}

customElements.define("cells-index", CellsIndex);
