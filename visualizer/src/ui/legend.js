// <cells-legend>: what the forms and colours mean. The first block lists the lens's
// main distinction (status, or how sure a protein mapping is); clicking an entry shows
// only those parts. An optional second block is a filter of another kind. A view that
// colours by a magnitude gives a scale instead: the ramp with its limits and unit.

import { h, emit, statusSwatch } from "./dom.js";

class CellsLegend extends HTMLElement {
  /**
   * title    the block's name, shown on the toggle of a narrow screen
   * items    [{ id, label, description, count, swatch }]
   * isolate  the id shown alone, or null
   * filter   { title, unit, items: [{ id, label, title, count }], active } or null
   * note     { swatch, text } or null
   * scale    { label, unit, gradient, ticks: [{ at, text }], marks: [{ at, text }], steps: [{ colour, text }] } or null
   * keys     [{ key, text }]: other marks drawn in the scene, each with a small picture
   */
  render({ title, items = [], isolate, open, filter, note, scale, keys }) {
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
    const body = h("div", { class: "legend-body" }, scale ? this.scale(scale) : null, rows);
    for (const item of keys || []) {
      body.append(h("p", { class: "legend-key" }, h("span", { class: `key key-${item.key}`, "aria-hidden": "true" }), item.text));
    }
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
    if (note) body.append(h("p", { class: note.swatch ? "legend-note" : "legend-note legend-note-plain" }, note.swatch ? statusSwatch(note.swatch) : null, note.text));
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

/** The ramp of a magnitude: the colours, the limits in the shown unit, and any marked value. */
CellsLegend.prototype.scale = function (scale) {
  const head = h("p", { class: "legend-scale-title" }, scale.label, scale.unit ? h("span", { class: "legend-unit" }, scale.unit) : null);
  if (scale.steps) {
    // A count: one swatch per step, not a continuous ramp.
    return [head, h("div", { class: "ramp-steps" }, scale.steps.map((step) => h("span", { class: "ramp-step" }, h("i", { style: `background:${step.colour}` }), step.text)))];
  }
  const ramp = h("div", { class: "ramp", style: `background:${scale.gradient}` }, (scale.marks || []).map((mark) => h("i", { class: "ramp-mark", style: `left:${(mark.at * 100).toFixed(2)}%`, title: mark.text })));
  const ticks = h("div", { class: "ramp-ticks" }, scale.ticks.map((tick) => h("span", { style: `left:${(tick.at * 100).toFixed(2)}%` }, tick.text)));
  const marks = (scale.marks || []).map((mark) => h("p", { class: "legend-key" }, h("span", { class: "key key-mark", "aria-hidden": "true" }), mark.text));
  return [head, ramp, ticks, marks];
};

customElements.define("cells-legend", CellsLegend);
