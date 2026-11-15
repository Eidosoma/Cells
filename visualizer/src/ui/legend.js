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
   * layers   { title, rows: [{ channel, label, options: [{ id, label, on, off, busy, title }], problem }],
   *            cannot: [{ id, label, why }], strength: { options: [{ id, label, on }] }, keys: [{ key, text, chips }], hint, details } or null:
   *          the switch for quantity layers (schema/QUANTITY_LAYERS.md): one layer on each channel, the signs
   *          the layers add to the scene (a key may list `chips`, [{ colour, label }]: each ion's colour beside its name),
   *          a hint on how to see a layer that waits for a cell to be chosen, and the id of the panel that says
   *          what stands behind them
   * folded   the keys and the note start closed (a short window)
   */
  render({ title, items = [], isolate, open, filter, findings, note, scale, keys, layers, folded = false }) {
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
    if (layers?.rows?.length || layers?.cannot?.length) body.append(this.layers(layers));
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

/**
 * The switch for quantity layers: for each visual channel, the layers the run can feed
 * and which one holds it; how strongly the marks are drawn; the layers the run cannot
 * feed, each with the reason; and what stands behind the numbers of those that are on.
 */
CellsLegend.prototype.layers = function ({ title, rows = [], cannot = [], strength, keys = [], hint = null, details = null }) {
  const short = (label) => label.replace(/^Membrane /, "").replace(/^./, (letter) => letter.toUpperCase());
  const segment = (options, press) =>
    h(
      "span",
      { class: "seg layer-seg", style: `grid-template-columns: repeat(${options.length}, minmax(0, 1fr))` },
      options.map((option) => h("button", { type: "button", "aria-pressed": String(Boolean(option.on)), "aria-busy": option.busy ? "true" : null, title: option.title || null, dataset: { layer: option.id ?? "" }, onclick: () => press(option) }, option.busy ? "Fetching…" : short(option.label)))
    );
  const block = h("div", { class: "legend-layers" }, h("p", { class: "legend-title" }, title || "Layers"));
  for (const row of rows) {
    block.append(
      h(
        "div",
        { class: "layer-row", role: "group", "aria-label": row.label, dataset: { channel: row.channel } },
        h("span", { class: "layer-channel" }, row.label),
        // "Off" lets go of the layer that holds the channel; another option takes the channel for its layer.
        segment(row.options, (option) => (option.id ? !option.on && emit(this, "cells-layer", { id: option.id, on: true }) : option.off && emit(this, "cells-layer", { id: option.off, on: false })))
      )
    );
    if (row.problem) block.append(h("p", { class: "layer-problem", role: "status" }, row.problem));
  }
  if (strength && rows.length) {
    block.append(h("div", { class: "layer-row", role: "group", "aria-label": "How strongly the layers are drawn", dataset: { channel: "strength" } }, h("span", { class: "layer-channel" }, "Drawn"), segment(strength.options, (option) => !option.on && emit(this, "cells-strength", option.id))));
  }
  // A layer that is on and waits for a cell to be chosen says how it is seen.
  if (hint) block.append(h("p", { class: "layer-hint", role: "status" }, hint));
  for (const item of cannot) block.append(h("p", { class: "layer-cannot", dataset: { layer: item.id } }, h("span", { class: "layer-cannot-name" }, short(item.label)), " ", item.why));
  // The signs the layers add to the scene stay with the switch, each with what it stands for.
  // A colour that stands for an ion is shown beside the ion's name; the words keep the page's own colours.
  const chips = (list) => h("span", { class: "key-chips" }, list.map((chip) => h("span", { class: "key-chip" }, h("i", { style: `background:${chip.colour}`, "aria-hidden": "true" }), chip.label)));
  const signs = keys.map((item) => h("p", { class: item.chips ? "legend-key legend-key-chips" : "legend-key" }, item.chips ? null : h("span", { class: `key key-${item.key}`, "aria-hidden": "true" }), item.chips ? h("span", {}, chips(item.chips), item.text) : item.text));
  // Many signs fold away under one line, so that the card above the legend keeps its room; once opened they stay open.
  if (signs.length > 3) {
    const fold = h("details", { class: "legend-keys layer-keys", open: this.layerKeysOpen === true, ontoggle: () => (this.layerKeysOpen = fold.open) }, h("summary", {}, "What the layers' signs mean"), signs);
    block.append(fold);
  } else block.append(...signs);
  // What stands behind the layers' numbers is said in the panel, where there is room for it.
  if (details) block.append(h("p", { class: "layer-more" }, h("button", { class: "link-button layer-details", type: "button", onclick: () => emit(this, "cells-select", { id: details }) }, "What stands behind them")));
  return block;
};

customElements.define("cells-legend", CellsLegend);
