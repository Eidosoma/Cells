// <cells-legend>: what the forms and colours mean. Clicking a status shows only that status.

import { h, emit, statusSwatch } from "./dom.js";

class CellsLegend extends HTMLElement {
  render({ model, counts, isolate, lens, open, together, togetherActive }) {
    this.replaceChildren();
    const items = model.raw.statuses.map((status) => {
      const count = counts.get(status.id) || 0;
      return h(
        "button",
        {
          class: "legend-item" + (isolate === status.id ? " is-on" : "") + (count ? "" : " is-empty"),
          type: "button",
          title: status.description,
          "aria-pressed": isolate === status.id ? "true" : "false",
          onclick: () => emit(this, "cells-isolate", isolate === status.id ? null : status.id),
        },
        statusSwatch(status.id),
        h("span", { class: "legend-label" }, status.label),
        h("span", { class: "legend-count" }, String(count))
      );
    });
    const body = h("div", { class: "legend-body" }, items);
    if (together?.length) {
      // Which parts run together in one model today: the answer to "is this one whole cell yet?"
      body.append(
        h("p", { class: "legend-title" }, "Runs together in"),
        ...together.map((group) =>
          h(
            "button",
            {
              class: "legend-item legend-group" + (togetherActive === group.id ? " is-on" : ""),
              type: "button",
              title: group.title,
              "aria-pressed": togetherActive === group.id ? "true" : "false",
              onclick: () => emit(this, "cells-together", togetherActive === group.id ? null : group.id),
            },
            h("span", { class: "legend-radio", "aria-hidden": "true" }),
            h("span", { class: "legend-label" }, group.label)
          )
        )
      );
    }
    if (lens === "cell") {
      body.append(
        h("p", { class: "legend-note" }, statusSwatch("illustration"), "Grey outlines and lines are drawn for orientation only.")
      );
    }
    this.append(
      h(
        "button",
        { class: "legend-toggle", type: "button", "aria-expanded": open ? "true" : "false", onclick: () => emit(this, "cells-legend-toggle") },
        h("span", {}, "Status"),
        h("span", { class: "chevron", "aria-hidden": "true" })
      ),
      body
    );
    this.classList.toggle("is-open", Boolean(open));
  }
}

customElements.define("cells-legend", CellsLegend);
