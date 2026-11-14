// <cells-trace>: one record of one part over the whole run, as a small line chart in
// the detail panel. It shows the saved records and nothing between them.
//
// One series, so there is no legend: the heading names it. The read-out above the plot
// gives the value at the playhead, or at the record under the pointer; a click moves the
// playhead there. The same values are in the table below the plot.

import { h, svg } from "../ui/dom.js";
import { clock, display, niceDomain, number } from "./format.js";

const W = 328, H = 136;
const PAD = { left: 38, right: 10, top: 16, bottom: 20 };
const TIME_STEPS = [10, 30, 60, 120, 300, 600, 1200, 1800, 3600, 7200];

class CellsTrace extends HTMLElement {
  /**
   * data: { run, record, index, player, title, judged, events: [{ time, label }], extra }
   *   record   the series of the run to plot (never a quantised one)
   *   index    which entity of the record's set
   *   judged   the time of the judged record, or null
   *   levels   [{ value, label }]: values of the record worth a line across the plot (the run's own constants)
 *   events   times marked on the time axis (this part was replaced)
   *   extra    (recordIndex) => more words for the read-out, or null
   */
  set data(data) {
    this.spec = data;
    if (this.isConnected) this.build();
  }

  connectedCallback() {
    if (this.spec) this.build();
  }

  disconnectedCallback() {
    this.spec?.player.removeEventListener("time", this.onTime);
  }

  build() {
    const { run, record, index, player } = this.spec;
    player.removeEventListener("time", this.onTime);
    this.onTime = () => this.place();
    player.addEventListener("time", this.onTime);
    this.shown = display(record);
    // The same limits as the sheet's colour scale, so the chart and the legend agree.
    const nice = niceDomain(record.range[0] * this.shown.factor, record.range[1] * this.shown.factor);
    const domain = { low: nice.low, high: nice.high, step: (nice.high - nice.low) / 2 };
    this.x = (seconds) => PAD.left + ((seconds - run.start) / (run.end - run.start || 1)) * (W - PAD.left - PAD.right);
    this.y = (value) => H - PAD.bottom - ((value - domain.low) / (domain.high - domain.low)) * (H - PAD.top - PAD.bottom);
    this.value = (step) => record.at(step, index) * this.shown.factor;
    this.pinned = null; // a record under the pointer or the keys, shown in place of the playhead's

    const grid = [], labels = [];
    for (let value = domain.low; value <= domain.high + domain.step / 2; value += domain.step) {
      const y = this.y(value);
      grid.push(svg("line", { class: "trace-grid", x1: PAD.left, x2: W - PAD.right, y1: y, y2: y }));
      labels.push(svg("text", { class: "trace-tick", x: PAD.left - 6, y: y + 3.5, "text-anchor": "end" }, number(value, Number.isInteger(value) ? 0 : 1)));
    }
    const span = run.end - run.start;
    const step = TIME_STEPS.find((size) => span / size <= 4.5) || span;
    for (let seconds = Math.ceil(run.start / step) * step; seconds <= run.end + 1e-6; seconds += step) {
      const x = this.x(seconds);
      grid.push(svg("line", { class: "trace-grid", x1: x, x2: x, y1: H - PAD.bottom, y2: H - PAD.bottom + 4 }));
      labels.push(svg("text", { class: "trace-tick", x, y: H - 5, "text-anchor": seconds === run.start ? "start" : "middle" }, seconds === 0 ? "0" : clock(seconds)));
    }

    // The line joins saved records; a record the run does not count as valid breaks it.
    let path = "", open = false;
    for (let k = 0; k < run.count; k++) {
      if (!run.isValid(k)) {
        open = false;
        continue;
      }
      path += `${open ? "L" : "M"}${this.x(run.t[k]).toFixed(1)} ${this.y(this.value(k)).toFixed(1)}`;
      open = true;
    }

    const marks = [];
    const { judged, events = [], levels = [] } = this.spec;
    const lines = levels.filter((level) => level.value * this.shown.factor > domain.low && level.value * this.shown.factor < domain.high);
    for (const level of lines) {
      const y = this.y(level.value * this.shown.factor);
      marks.push(svg("line", { class: "trace-level", x1: PAD.left, x2: W - PAD.right, y1: y, y2: y }, svg("title", {}, level.label)));
    }
    if (Number.isFinite(judged)) {
      const x = this.x(judged);
      marks.push(
        svg("line", { class: "trace-judged", x1: x, x2: x, y1: PAD.top - 3, y2: H - PAD.bottom }),
        svg("text", { class: "trace-tick trace-flag", x: x - 4, y: PAD.top - 6, "text-anchor": "end" }, "judged")
      );
    }
    for (const event of events) {
      const x = this.x(event.time), y = H - PAD.bottom;
      marks.push(svg("path", { class: "trace-event", d: `M${x} ${y - 1}l-4 -7h8z` }, svg("title", {}, `${event.label || "Replaced"} at ${clock(event.time, { precise: true })}`)));
    }

    this.cross = svg("line", { class: "trace-cross", y1: PAD.top - 3, y2: H - PAD.bottom, hidden: true });
    this.crossDot = svg("circle", { class: "trace-dot trace-dot-cross", r: 3.5, hidden: true });
    this.head = svg("line", { class: "trace-head", y1: PAD.top - 3, y2: H - PAD.bottom });
    this.headDot = svg("circle", { class: "trace-dot", r: 4 });
    this.plot = svg(
      "svg",
      { class: "trace-plot", viewBox: `0 0 ${W} ${H}`, role: "img", tabindex: 0, "aria-label": `${this.spec.title} over the run, in ${this.shown.unit || "its unit"}. Arrow keys move along the records; Enter moves the playhead there.` },
      grid,
      labels,
      marks,
      svg("path", { class: "trace-line", d: path }),
      this.head,
      this.headDot,
      this.cross,
      this.crossDot
    );
    this.reading = h("b", { class: "trace-value" });
    this.when = h("span", { class: "trace-when" });
    const key = [];
    if (events.length) key.push(h("span", {}, h("i", { class: "trace-key trace-key-event", "aria-hidden": "true" }), "replaced here"));
    for (const level of lines) {
      key.push(h("span", {}, h("i", { class: "trace-key trace-key-level", "aria-hidden": "true" }), `${number(level.value * this.shown.factor, 1)}${this.shown.unit ? ` ${this.shown.unit}` : ""}: ${level.label}`));
    }
    this.replaceChildren(
      h("h4", { class: "trace-title" }, this.spec.title, this.shown.unit ? h("span", { class: "quiet" }, ` · ${this.shown.unit}`) : null),
      h("p", { class: "trace-read", "aria-live": "off" }, this.reading, this.when),
      this.plot,
      key.length ? h("p", { class: "trace-keys" }, key) : null,
      this.table()
    );

    const nearest = (event) => {
      const box = this.plot.getBoundingClientRect();
      const seconds = run.start + ((((event.clientX - box.left) / box.width) * W - PAD.left) / (W - PAD.left - PAD.right)) * (run.end - run.start);
      const before = run.indexAt(seconds), after = Math.min(run.count - 1, before + 1);
      return Math.abs(run.t[after] - seconds) < Math.abs(seconds - run.t[before]) ? after : before;
    };
    this.plot.addEventListener("pointermove", (event) => this.pin(nearest(event)));
    this.plot.addEventListener("pointerleave", () => this.pin(null));
    this.plot.addEventListener("click", (event) => player.seek(run.t[nearest(event)]));
    this.plot.addEventListener("blur", () => this.pin(null));
    this.plot.addEventListener("keydown", (event) => {
      const at = this.pinned ?? player.index;
      if (event.key === "ArrowLeft") this.pin(Math.max(0, at - 1));
      else if (event.key === "ArrowRight") this.pin(Math.min(run.count - 1, at + 1));
      else if (event.key === "Enter" || event.key === " ") player.seek(run.t[at]);
      else return;
      event.preventDefault();
    });
    this.place();
  }

  /** Show one record's value in place of the playhead's, or go back to the playhead. */
  pin(step) {
    this.pinned = step;
    this.place();
  }

  place() {
    if (!this.spec || !this.head) return;
    const { run, player, extra } = this.spec;
    const playing = player.index;
    const x = this.x(run.t[playing]);
    this.head.setAttribute("x1", x);
    this.head.setAttribute("x2", x);
    const valid = run.isValid(playing);
    this.headDot.toggleAttribute("hidden", !valid);
    if (valid) {
      this.headDot.setAttribute("cx", x);
      this.headDot.setAttribute("cy", this.y(this.value(playing)));
    }
    const pinned = this.pinned;
    this.cross.toggleAttribute("hidden", pinned === null);
    this.crossDot.toggleAttribute("hidden", pinned === null || !run.isValid(pinned));
    if (pinned !== null) {
      const px = this.x(run.t[pinned]);
      this.cross.setAttribute("x1", px);
      this.cross.setAttribute("x2", px);
      this.crossDot.setAttribute("cx", px);
      this.crossDot.setAttribute("cy", this.y(this.value(pinned)));
    }
    const step = pinned ?? playing;
    this.reading.textContent = run.isValid(step) ? `${number(this.value(step), this.shown.decimals)}${this.shown.unit ? ` ${this.shown.unit}` : ""}` : "not a valid record";
    const more = extra ? extra(step) : "";
    this.when.textContent = ` at ${clock(run.t[step], { precise: true })}${pinned === null ? "" : " (under the pointer)"}${more ? ` · ${more}` : ""}`;
  }

  /** The same values as a table, built when it is first opened. */
  table() {
    const { run, events = [] } = this.spec;
    const body = h("tbody", {});
    const details = h(
      "details",
      { class: "trace-table" },
      h("summary", {}, "Values as a table"),
      h("div", { class: "trace-scroll" }, h("table", {}, h("thead", {}, h("tr", {}, h("th", {}, "Time"), h("th", {}, this.spec.title + (this.shown.unit ? ` (${this.shown.unit})` : "")))), body))
    );
    details.addEventListener("toggle", () => {
      if (!details.open || body.childElementCount) return;
      const replaced = new Set(events.map((event) => run.indexAt(event.time)));
      for (let k = 0; k < run.count; k++) {
        body.append(
          h(
            "tr",
            { class: replaced.has(k) ? "is-event" : "" },
            h("td", {}, clock(run.t[k], { precise: true }), replaced.has(k) ? " · then replaced" : ""),
            h("td", {}, run.isValid(k) ? number(this.value(k), this.shown.decimals) : "not valid")
          )
        );
      }
    });
    return details;
  }
}

if (typeof customElements !== "undefined" && !customElements.get("cells-trace")) customElements.define("cells-trace", CellsTrace);
