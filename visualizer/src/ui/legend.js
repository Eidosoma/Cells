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
   *            cannot: [{ id, label, why }], strength: { options: [{ id, label, on }] }, keys: [{ key, text, chips }], hint, details,
   *            time: { label, options: [{ id, label, title, on }] }, example } or null:
   *          the switch for quantity layers (schema/QUANTITY_LAYERS.md): one layer on each channel, the signs
   *          the layers add to the scene (a key may list `chips`, [{ colour, label }]: each ion's colour beside its name),
   *          a hint on how to see a layer that waits for a cell to be chosen, and the id of the panel that says
   *          what stands behind them; `time` is the slow-down of a layer that moves (true speed, or slowed), and
   *          `example` the words an example run keeps in the legend ("Example: invented numbers"), or an illustration in the
   *          Cell view ("Illustration: not a run"); `compact` the one line under which a view with little room keeps the
   *          signs, the `cannot` entries and the door to the panel (the Cell view's flux), with the channel's name beside its options
   * folded   the keys and the note start closed (a short window)
   * layersFirst  the switch for layers stands first (a phone with a panel open, where the legend has little room)
   * lead     words that open the legend, before its first block (on a phone, the protein atlas's caveat), or none
   */
  render(chrome) {
    // The same words and the same switches as were drawn last: nothing is drawn again. Drawing
    // them again replaces every button, which loses the place a visitor had scrolled to, and a
    // press that has begun on a button that is then replaced never arrives. While a press is
    // held inside the legend, a change waits until it is let go. (Seen on 16 November 2026: a
    // real press on the Flux switch did not take while the view, flying back from a part, was
    // still reporting changes; frames that come fast make it more likely, not less.)
    let said = null;
    try {
      said = JSON.stringify(chrome ?? null);
    } catch {
      said = null; // what cannot be written out is drawn every time, as before
    }
    if (said !== null && said === this.said && this.firstChild) return;
    if (this.pressed) {
      this.waiting = chrome;
      return;
    }
    this.said = said;
    this.waiting = null;
    this.draw(chrome ?? {});
  }
  connectedCallback() {
    if (this.letGo) return;
    this.letGo = () => {
      clearTimeout(this.holding);
      if (!this.pressed) return;
      this.pressed = false;
      // What waited is drawn once the press's own click has been dealt with.
      setTimeout(() => {
        if (this.waiting && !this.pressed) this.render(this.waiting);
      }, 0);
    };
    this.addEventListener("pointerdown", (event) => {
      // A select (Colour) opens a list of its own, whose release the page may never see: it is not held for.
      if (event.target?.closest?.("select")) return;
      this.pressed = true;
      // A press let go where the page cannot see it (outside the window) must not hold changes back for good.
      clearTimeout(this.holding);
      this.holding = setTimeout(this.letGo, 2000);
    });
    window.addEventListener("pointerup", this.letGo);
    window.addEventListener("pointercancel", this.letGo);
  }
  disconnectedCallback() {
    if (!this.letGo) return;
    clearTimeout(this.holding);
    window.removeEventListener("pointerup", this.letGo);
    window.removeEventListener("pointercancel", this.letGo);
    this.letGo = null;
    this.pressed = false;
  }
  draw({ title, items = [], isolate, open, filter, findings, note, scale, keys, layers, folded = false, layersFirst = false, colour = null, lead = null }) {
    // Drawn again while its Colour select has the keyboard, the new select takes it back, so that a second key reaches it.
    const hadColour = this.getRootNode()?.activeElement?.id === "cells-own-colour";
    this.replaceChildren();
    // What colour carries, where a view offers a choice (the protein atlas's own proteins: docs/ATLAS_LOOK.md):
    // chosen at the head of the block that names the colours, which then has a title of its own.
    const chooser = colour?.options?.length
      ? h(
          "label",
          { class: "legend-colour" },
          h("span", { class: "seg-label" }, "Colour"),
          (() => {
            // Escape at the select (closing its list) is the select's own: it does not also step the atlas's trail back.
            const select = h("select", { id: "cells-own-colour", class: "run-select", onchange: () => emit(this, "cells-own-colour", select.value), onkeydown: (event) => event.key === "Escape" && event.stopPropagation() }, colour.options.map(([value, label]) => h("option", { value, selected: value === colour.active }, label)));
            return select;
          })()
        )
      : null;
    const rows = items.map((item) =>
      h(
        "button",
        {
          // A key with no count (a model system's view, src/ui/entry_views.js) is neither empty nor counted.
          class: "legend-item" + (isolate === item.id ? " is-on" : "") + (item.count || item.count === undefined ? "" : " is-empty"),
          type: "button",
          title: item.description,
          "aria-pressed": isolate === item.id ? "true" : "false",
          onclick: () => emit(this, "cells-isolate", isolate === item.id ? null : item.id),
        },
        statusSwatch(item.swatch),
        h("span", { class: "legend-label" }, item.label),
        item.count === undefined ? null : h("span", { class: "legend-count" }, String(item.count))
      )
    );
    const body = h("div", { class: "legend-body" }, lead ? h("p", { class: "legend-lead" }, lead) : null, chooser, chooser ? h("p", { class: "legend-title legend-colour-title" }, title) : null, scale ? this.scale(scale) : null, rows);
    if (layers?.rows?.length || layers?.cannot?.length) {
      const block = this.layers(layers);
      if (layersFirst) body.prepend(block);
      else body.append(block);
    }
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
    if (hadColour) this.querySelector("#cells-own-colour")?.focus({ preventScroll: true });
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
CellsLegend.prototype.layers = function ({ title, rows = [], cannot = [], compact = null, strength, keys = [], hint = null, details = null, time = null, example = null }) {
  const short = (label) => label.replace(/^Membrane /, "").replace(/^./, (letter) => letter.toUpperCase());
  const segment = (options, press) =>
    h(
      "span",
      // Each option is as wide as its own words, and what room is left is shared: a long name is not cut while "Off" has room to spare.
      { class: "seg layer-seg", style: `grid-template-columns: repeat(${options.length}, minmax(0, auto))` },
      options.map((option) => h("button", { type: "button", "aria-pressed": String(Boolean(option.on)), "aria-busy": option.busy ? "true" : null, title: option.title || null, dataset: { layer: option.id ?? "" }, onclick: () => press(option) }, option.busy ? "Fetching…" : short(option.label)))
    );
  // A run that offers many channels has each channel's name beside its options, on one line, so that the legend stays short.
  const block = h("div", { class: rows.length >= 5 || compact ? "legend-layers is-dense" : "legend-layers" }, h("p", { class: "legend-title" }, title || "Layers"));
  // A run whose numbers are invented says so for as long as it is shown (rule 6). In a view with little room the
  // switch comes first, so that it is in reach where the legend is capped and scrolls; the notice stands under it.
  const notice = example ? h("p", { class: "layer-example", role: "status" }, example) : null;
  if (notice && !compact) block.append(notice);
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
  if (notice && compact) block.append(notice);
  // The time a layer that moves keeps: true speed as it opens, with a slow-down beside it (rule 3).
  if (time?.kind === "slider") block.append(this.speedSlider(time));
  else if (time) block.append(h("div", { class: "layer-row", role: "group", "aria-label": "How fast the beads' time runs", dataset: { channel: "time" } }, h("span", { class: "layer-channel" }, time.label), segment(time.options, (option) => !option.on && emit(this, "cells-slow", option.id))));
  // A layer that is on and waits for a cell to be chosen says how it is seen.
  if (hint) block.append(h("p", { class: "layer-hint", role: "status" }, hint));
  const lacking = cannot.map((item) => h("p", { class: "layer-cannot", dataset: { layer: item.id } }, h("span", { class: "layer-cannot-name" }, short(item.label)), " ", item.why));
  // The signs the layers add to the scene stay with the switch, each with what it stands for.
  // A colour that stands for an ion is shown beside the ion's name; the words keep the page's own colours.
  const chips = (list) => h("span", { class: "key-chips" }, list.map((chip) => h("span", { class: "key-chip" }, h("i", { style: `background:${chip.colour}`, "aria-hidden": "true" }), chip.label)));
  const signs = keys.map((item) => h("p", { class: item.chips ? "legend-key legend-key-chips" : "legend-key" }, item.chips ? null : h("span", { class: `key key-${item.key}`, "aria-hidden": "true" }), item.chips ? h("span", {}, chips(item.chips), item.text) : item.text));
  // A view with little room for its legend (the Cell view, whose card stands above it) keeps the signs, what is not
  // drawn and the door to the panel under one line, named by `compact`; once opened it stays open.
  if (compact) {
    const door = details ? h("p", { class: "layer-more" }, h("button", { class: "link-button layer-details", type: "button", onclick: () => emit(this, "cells-select", { id: details }) }, "What stands behind them")) : null;
    const inside = [...signs, ...lacking, door].filter(Boolean);
    if (inside.length) {
      const fold = h("details", { class: "legend-keys layer-keys", open: this.layerKeysOpen === true, ontoggle: () => (this.layerKeysOpen = fold.open) }, h("summary", {}, compact), inside);
      block.append(fold);
    }
    return block;
  }
  // Many layers a run cannot feed fold away under one line that says how many; inside, each is named with its reason. Once opened they stay open.
  if (lacking.length > 2) {
    const fold = h("details", { class: "legend-keys layer-cannots", open: this.cannotOpen === true, ontoggle: () => (this.cannotOpen = fold.open) }, h("summary", {}, `${lacking.length} layers this run cannot feed`), lacking);
    block.append(fold);
  } else block.append(...lacking);
  // Many signs fold away under one line, so that the card above the legend keeps its room; once opened they stay open.
  if (signs.length > 3) {
    const fold = h("details", { class: "legend-keys layer-keys", open: this.layerKeysOpen === true, ontoggle: () => (this.layerKeysOpen = fold.open) }, h("summary", {}, "What the layers' signs mean"), signs);
    block.append(fold);
  } else block.append(...signs);
  // What stands behind the layers' numbers is said in the panel, where there is room for it.
  if (details) block.append(h("p", { class: "layer-more" }, h("button", { class: "link-button layer-details", type: "button", onclick: () => emit(this, "cells-select", { id: details }) }, "What stands behind them")));
  return block;
};

/**
 * The Speed row as a slider (the Cell view's flux, layers/cellflux.js, speedRow): `time` is { label, value (0 to 1),
 * marks: [{ at, label }], slowAt(position), short(position), words(position) }. True speed at its start; its marks
 * stand under it on one line, each with its words but the end, which has its tick alone. Dragged, it tells the page at once (`cells-slow` with `live`), so that the picture
 * follows the hand; let go, it tells it once more, and the legend is written again. Arrow keys step it, Home and End
 * go to its ends; a screen reader hears the speed in words. At least 44 px tall to the touch.
 */
CellsLegend.prototype.speedSlider = function (time) {
  const now = h("span", { class: "speed-now", style: "font-variant-numeric: tabular-nums; font-weight: 600; min-width: 7.5em; text-align: right; color: var(--fg)" }, time.short(time.value));
  const input = h("input", {
    type: "range",
    class: "speed-slider",
    min: "0",
    max: "1",
    step: "0.005",
    value: String(time.value),
    "aria-label": "Speed of what flows",
    "aria-valuetext": time.words(time.value),
    title: time.words(time.value),
    style: "width: 100%; height: 44px; margin: 0; accent-color: var(--accent); background: transparent; cursor: pointer",
  });
  const tell = (live) => {
    const position = Number(input.value);
    input.setAttribute("aria-valuetext", time.words(position));
    input.title = time.words(position);
    now.textContent = time.short(position);
    emit(this, "cells-slow", { slow: time.slowAt(position), live });
  };
  // Let go after a press or a drag, the legend is written again (its words follow the speed). Moved by the keys, it is
  // written again only when the slider loses the focus, so that the keys keep working on the slider the hand is on.
  let pressed = false, keyed = false;
  input.addEventListener("pointerdown", () => (pressed = true));
  input.addEventListener("input", () => tell(true));
  input.addEventListener("change", () => {
    if (pressed) {
      pressed = false;
      tell(false);
    } else keyed = true;
  });
  input.addEventListener("blur", () => {
    if (!keyed) return;
    keyed = false;
    tell(false);
  });
  // The marks: a tick at each, and under it the words of the start and of the two marks between (a thousandfold at the
  // middle, a millionfold at three quarters: the user, 17 November 2026). They keep to one line: the first stands inside
  // the row's start, a mark past two thirds of the way leans back from its tick so that its words end inside the row,
  // and the end has its tick alone (its speed is said beside the row's name once the slider is there).
  const last = time.marks.length - 1;
  const lean = (mark, k) => (k === 0 ? "0" : k === last ? "-100%" : mark.at > 2 / 3 ? "-12px" : "-50%");
  const tick = (mark, k) => (k === 0 ? "left: 0" : k === last ? "right: 0" : mark.at > 2 / 3 ? "left: 12px" : "left: 50%");
  const marks = h(
    "div",
    { class: "speed-marks", "aria-hidden": "true", style: "position: relative; height: 16px; margin: -10px 8px 0; font-size: 10.5px; line-height: 1.2; color: var(--muted)" },
    time.marks.map((mark, k) =>
      h(
        "span",
        { style: `position: absolute; top: 2px; left: ${(mark.at * 100).toFixed(2)}%; transform: translateX(${lean(mark, k)}); white-space: nowrap; padding: 0 1px; min-width: 1px; min-height: 1em` },
        h("i", { style: `position: absolute; ${tick(mark, k)}; top: -2px; width: 1px; height: 3px; background: currentColor` }),
        k === last ? "" : mark.label
      )
    )
  );
  // Its name and the speed in force on one line; the slider under them, the whole width of the legend.
  return h(
    "div",
    { class: "layer-row speed-row", role: "group", "aria-label": "How fast the time of what flows runs", dataset: { channel: "time" }, style: "display: block; padding: 2px 8px 0" },
    h("div", { style: "display: flex; justify-content: space-between; align-items: baseline; gap: 8px" }, h("span", { class: "layer-channel" }, time.label), now),
    input,
    marks
  );
};

customElements.define("cells-legend", CellsLegend);
