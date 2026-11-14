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
   * filter   { title, unit, items: [{ id, label, title, count }], active, folded } or null; folded: the block
   *          starts closed under its title, to leave room (it opens on a press, or while it filters)
   * findings { title, unit, items: [{ id, label, title, count, swatch }], active } or null: a further
   *          block that filters, each entry with the mark it is drawn with (what a species' atlas found)
   * note     { swatch, text } or null
   * scale    { label, unit, gradient, ticks: [{ at, text }], marks: [{ at, text }], steps: [{ colour, text }] } or null
   * keys     [{ key, text }]: other marks drawn in the scene, each with a small picture
   * folded   the keys and the note start closed (a short window)
   */
  render({ title, items = [], isolate, open, filter, findings, note, scale, keys, folded = false }) {
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
    const lines = (keys || []).map((item) => h("p", { class: "legend-key" }, h("span", { class: `key key-${item.key}`, "aria-hidden": "true" }), item.text));
    // On a short window the marks fold away, so the card above the legend has room.
    if (lines.length && folded) body.append(h("details", { class: "legend-keys" }, h("summary", {}, "Marks on the sheet"), lines));
    else body.append(...lines);
    if (filter?.items?.length) {
      const heading = [filter.title, filter.unit ? h("span", { class: "legend-unit" }, filter.unit) : null];
      const entries = filter.items.map((item) =>
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
      );
      if (filter.folded) {
        // Once opened it stays open, also when the legend is drawn again.
        const fold = h("details", { class: "legend-fold", open: Boolean(filter.active) || this.foldOpen === true, ontoggle: () => (this.foldOpen = fold.open) }, h("summary", { class: "legend-title" }, heading), entries);
        body.append(fold);
      } else {
        body.append(h("p", { class: "legend-title" }, heading), ...entries);
      }
    }
    if (findings?.items?.length) {
      body.append(
        h("p", { class: "legend-title" }, findings.title, findings.unit ? h("span", { class: "legend-unit" }, findings.unit) : null),
        ...findings.items.map((item) =>
          h(
            "button",
            {
              class: "legend-item legend-group" + (findings.active === item.id ? " is-on" : "") + (item.count ? "" : " is-empty"),
              type: "button",
              title: item.title,
              dataset: { finding: item.id },
              "aria-pressed": findings.active === item.id ? "true" : "false",
              onclick: () => emit(this, "cells-finding", findings.active === item.id ? null : item.id),
            },
            // An entry that is drawn with no mark keeps an empty place for one.
            item.swatch ? statusSwatch(item.swatch) : h("span", { "aria-hidden": "true" }),
            h("span", { class: "legend-label" }, item.label),
            h("span", { class: "legend-count" }, String(item.count))
          )
        )
      );
    }
    if (note && !(folded && lines.length)) body.append(h("p", { class: note.swatch ? "legend-note" : "legend-note legend-note-plain" }, note.swatch ? statusSwatch(note.swatch) : null, note.text));
    else if (note) body.querySelector(".legend-keys")?.append(h("p", { class: "legend-key legend-key-note" }, note.text));
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
