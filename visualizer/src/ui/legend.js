// <cells-legend>: what the forms and colours mean. The first block lists the lens's
// main distinction (status, or how sure a protein mapping is); clicking an entry shows
// only those parts. An optional second block is a filter of another kind.

import { h, emit, statusSwatch } from "./dom.js";

class CellsLegend extends HTMLElement {
  /**
   * title    the block's name, shown on the toggle of a narrow screen
   * items    [{ id, label, description, count, swatch }]
   * isolate  the id shown alone, or null
   * filter   { title, unit, items: [{ id, label, title, count }], active } or null
   * note     { swatch, text } or null
   */
  render({ title, items, isolate, open, filter, note }) {
    this.replaceChildren();
    const rows = items.map((item) =>
      h(
        "button",
        {
          class: "legend-item" + (isolate === item.id ? " is-on" : "") + (item.count ? "" : " is-empty"),
          type: "button",
          title: item.description,
          "aria-pressed": isolate === item.id ? "true" : "false",
          onclick: () => emit(this, "cells-isolate", isolate === item.id ? null : item.id),
        },
        statusSwatch(item.swatch),
        h("span", { class: "legend-label" }, item.label),
        h("span", { class: "legend-count" }, String(item.count))
      )
    );
    const body = h("div", { class: "legend-body" }, rows);
    if (filter?.items?.length) {
      body.append(
        h("p", { class: "legend-title" }, filter.title, filter.unit ? h("span", { class: "legend-unit" }, filter.unit) : null),
        ...filter.items.map((item) =>
          h(
            "button",
            {
              class: "legend-item legend-group" + (filter.active === item.id ? " is-on" : ""),
              type: "button",
              title: item.title,
              "aria-pressed": filter.active === item.id ? "true" : "false",
              onclick: () => emit(this, "cells-together", filter.active === item.id ? null : item.id),
            },
            h("span", { class: "legend-radio", "aria-hidden": "true" }),
            h("span", { class: "legend-label" }, item.label),
            item.count === undefined ? null : h("span", { class: "legend-count" }, String(item.count))
          )
        )
      );
    }
    if (note) body.append(h("p", { class: "legend-note" }, statusSwatch(note.swatch), note.text));
    this.append(
      h(
        "button",
        { class: "legend-toggle", type: "button", "aria-expanded": open ? "true" : "false", onclick: () => emit(this, "cells-legend-toggle") },
        h("span", {}, title),
        h("span", { class: "chevron", "aria-hidden": "true" })
      ),
      body
    );
    this.classList.toggle("is-open", Boolean(open));
  }
}

customElements.define("cells-legend", CellsLegend);
