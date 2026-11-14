// <cells-viewer>: the whole viewer as one custom element. Give it a scene (a JSON
// script child, the `scene` property or a `src` URL) and it draws it, with a lens
// switch, a legend, a list of parts and a detail panel.
//
//   <cells-viewer lens="cell"><script type="application/json">{...}</script></cells-viewer>
//
// Events: "cells-ready" once drawn; "cells-selected" with { id } when the selection changes.

import { css } from "./styles.js";
import { h, formatDate } from "./dom.js";
import "./legend.js";
import "./index.js";
import "./panel.js";
import { SceneModel } from "../scene/model.js";
import { Stage } from "../core/stage.js";
import { LabelLayer } from "../core/labels.js";
import { StackLens } from "../lenses/stack.js";
import { CellLens } from "../lenses/cell.js";

const LENSES = [
  { id: "cell", label: "Cell and scales", make: (stage, model, labels) => new CellLens(stage, model, labels) },
  { id: "engine", label: "Engine", make: (stage, model, labels) => new StackLens(stage, model, labels) },
];

class CellsViewer extends HTMLElement {
  static get observedAttributes() {
    return ["lens"];
  }

  constructor() {
    super();
    this.state = { lens: null, selected: null, isolate: null, legendOpen: false, indexOpen: false };
    this.lenses = new Map();
  }

  connectedCallback() {
    if (this.shadowRoot) return;
    this.attachShadow({ mode: "open" });
    this.buildChrome();
    this.loadScene().then(
      (scene) => this.start(scene),
      (error) => this.fail(`The map's data could not be read (${error.message}).`)
    );
  }

  disconnectedCallback() {
    this.stage?.dispose();
  }

  attributeChangedCallback(name, _old, value) {
    if (name === "lens" && this.model && value && value !== this.state.lens) this.setLens(value);
  }

  // ------------------------------------------------------------ loading

  async loadScene() {
    if (this.scene) return this.scene;
    const inline = this.querySelector('script[type="application/json"]');
    if (inline) return JSON.parse(inline.textContent);
    const src = this.getAttribute("src");
    if (src) {
      const response = await fetch(src);
      if (!response.ok) throw new Error(`${src}: ${response.status}`);
      return response.json();
    }
    throw new Error("no scene given");
  }

  buildChrome() {
    const root = this.shadowRoot;
    this.canvas = h("canvas", { tabIndex: 0, role: "img", "aria-label": "3D map of the Cells simulator. The list of parts gives the same content as text." });
    this.labelBox = h("div", { class: "labels" });
    this.switchBox = h("div", { class: "switch", role: "group", "aria-label": "View" });
    this.stamp = h("span", { class: "stamp" });
    this.indexButton = h("button", { class: "pill-button", type: "button", "aria-pressed": "false", onclick: () => this.toggleIndex() }, "List");
    this.legend = h("cells-legend", { class: "card" });
    this.panel = h("cells-panel", { class: "card", hidden: true });
    this.index = h("cells-index", { class: "card", hidden: true });
    this.caveat = h("p", { class: "caveat", hidden: true });
    this.rail = h("nav", { class: "rail card", hidden: true, "aria-label": "Scale" });
    this.hint = h("p", { class: "hint" }, "Drag to turn · scroll to zoom · click a part");
    this.fallback = h("p", { class: "fallback", hidden: true });
    this.frame = h(
      "div",
      { class: "frame", style: "position:absolute;inset:0" },
      h("div", { class: "stage" }, this.canvas, this.labelBox),
      h("header", { class: "bar" }, h("div", { class: "brand" }, h("b", {}, "Cells"), h("span", {}, "Architecture map")), this.switchBox, h("div", { class: "bar-end" }, this.stamp, this.indexButton)),
      this.hint,
      this.caveat,
      this.rail,
      this.legend,
      this.index,
      this.panel,
      this.fallback
    );
    root.append(h("style", {}, css), this.frame);
    root.addEventListener("cells-select", (event) => this.select(event.detail.id, event.detail));
    root.addEventListener("cells-isolate", (event) => this.setIsolate(event.detail));
    root.addEventListener("cells-together", (event) => this.current?.setTogether?.(event.detail));
    root.addEventListener("cells-legend-toggle", () => {
      this.state.legendOpen = !this.state.legendOpen;
      this.renderLegend();
    });
  }

  start(scene) {
    try {
      this.model = new SceneModel(scene);
    } catch (error) {
      this.fail(error.message);
      return;
    }
    const meta = this.model.meta;
    this.stamp.textContent = [meta.as_of ? `As of ${formatDate(meta.as_of)}` : "", meta.revision ? `main ${meta.revision}` : ""].filter(Boolean).join(" · ");
    for (const lens of LENSES) {
      this.switchBox.append(h("button", { type: "button", dataset: { lens: lens.id }, "aria-pressed": "false", onclick: () => this.setLens(lens.id, true) }, lens.label));
    }
    try {
      this.stage = new Stage({ canvas: this.canvas, host: this });
    } catch (error) {
      this.stage = null;
    }
    if (this.stage) {
      this.labels = new LabelLayer(this.labelBox, this.stage, (id) => this.select(id, { fly: false }));
      this.stage.afterRender.add(() => this.labels.layout());
      this.stage.onTick((dt, time) => this.current?.update(dt, time) || false);
      this.stage.onPalette((palette) => {
        for (const lens of this.lenses.values()) lens.applyPalette(palette);
      });
      this.listen();
      document.fonts?.ready.then(() => {
        this.labels.measure();
        this.stage.invalidate();
      });
    } else {
      this.fallback.hidden = false;
      this.fallback.textContent = "3D drawing is not available in this browser. The list below gives the same content as text.";
      this.hint.hidden = true;
      this.state.indexOpen = true;
    }
    const query = new URLSearchParams(location.search);
    // "still" turns transitions off, so a screenshot shows the settled state.
    if (query.get("still")) this.frame.classList.add("is-still");
    const wanted = query.get("lens") || location.hash.slice(1) || this.getAttribute("lens") || LENSES[0].id;
    this.setLens(LENSES.some((lens) => lens.id === wanted) ? wanted : LENSES[0].id);
    if (query.get("scale")) this.current?.goToScale?.(query.get("scale"), true);
    if (query.get("isolate")) this.setIsolate(query.get("isolate"));
    if (query.get("select")) this.select(query.get("select"), { fly: true });
    if (query.get("index")) this.toggleIndex(true);
    window.addEventListener("hashchange", () => {
      const name = location.hash.slice(1);
      if (LENSES.some((lens) => lens.id === name) && name !== this.state.lens) this.setLens(name);
    });
    this.dispatchEvent(new CustomEvent("cells-ready", { bubbles: true, composed: true }));
  }

  fail(message) {
    this.fallback.hidden = false;
    this.fallback.textContent = message;
    this.hint.hidden = true;
  }

  // ------------------------------------------------------------ lenses

  setLens(id, fromUser = false) {
    const spec = LENSES.find((lens) => lens.id === id);
    if (!spec || !this.model) return;
    this.current?.deactivate();
    this.state.lens = id;
    this.state.isolate = null;
    if (this.stage) {
      if (!this.lenses.has(id)) {
        const lens = spec.make(this.stage, this.model, this.labels);
        lens.onChrome = () => this.renderChrome();
        this.lenses.set(id, lens);
      }
      this.current = this.lenses.get(id);
      this.current.activate();
      this.current.setIsolate(null);
      this.current.setSelection(this.current.has(this.state.selected) ? this.state.selected : null);
    }
    if (!this.shows(this.state.selected)) this.state.selected = null;
    for (const button of this.switchBox.children) button.setAttribute("aria-pressed", String(button.dataset.lens === id));
    if (fromUser && location.hash.slice(1) !== id) {
      try {
        history.replaceState(null, "", `#${id}`);
      } catch {
        location.hash = id;
      }
    }
    this.renderChrome();
    this.renderPanel();
    this.stage?.invalidate();
  }

  /** The parts the current lens shows, with or without a stage. */
  shownEntities() {
    if (this.current) return this.current.entities();
    return this.state.lens === "cell" ? this.model.entities.filter((entity) => entity.group === "biology") : this.model.entities.filter((entity) => entity.group !== "biology");
  }

  shows(id) {
    return Boolean(id) && this.shownEntities().some((entity) => entity.id === id);
  }

  sections() {
    if (this.current) return this.current.sections();
    const groups = new Map();
    for (const entity of this.shownEntities()) {
      const key = entity.group === "biology" ? entity.scale || entity.kind : entity.group;
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(entity);
    }
    return [...groups].map(([key, entities]) => ({ label: this.model.groups.find((group) => group.id === key)?.label || key, entities }));
  }

  // ------------------------------------------------------------ state changes

  select(id, { fly = false } = {}) {
    if (id && !this.model.get(id)) return;
    if (id && !this.shows(id)) {
      // The part lives in the other lens: go there.
      const other = LENSES.find((lens) => lens.id !== this.state.lens);
      this.state.selected = id;
      this.setLens(other.id, true);
      if (!this.shows(id)) this.state.selected = null;
    }
    this.state.selected = id && this.shows(id) ? id : null;
    this.current?.setSelection(this.state.selected);
    if (fly && this.state.selected) this.current?.focus(this.state.selected);
    if (this.state.selected && this.state.indexOpen && this.clientWidth < 760) this.toggleIndex(false);
    this.renderPanel();
    this.renderIndex();
    this.dispatchEvent(new CustomEvent("cells-selected", { detail: { id: this.state.selected }, bubbles: true, composed: true }));
  }

  setIsolate(status) {
    this.state.isolate = status || null;
    this.current?.setIsolate(this.state.isolate);
    this.renderLegend();
  }

  toggleIndex(force) {
    this.state.indexOpen = force ?? !this.state.indexOpen;
    this.index.hidden = !this.state.indexOpen;
    this.indexButton.setAttribute("aria-pressed", String(this.state.indexOpen));
    this.renderIndex();
    if (this.state.indexOpen) this.index.querySelector("input")?.focus({ preventScroll: true });
  }

  // ------------------------------------------------------------ rendering the interface

  renderChrome() {
    this.renderLegend();
    this.renderIndex();
    const chrome = this.current?.chrome?.() || {};
    this.caveat.hidden = !chrome.caveat;
    this.hint.hidden = Boolean(chrome.caveat) || !this.stage;
    this.caveat.textContent = chrome.caveat || "";
    this.rail.hidden = !chrome.rail;
    if (chrome.rail) {
      this.rail.replaceChildren(
        h("span", { class: "rail-title" }, "Scale"),
        ...chrome.rail.map((stop) =>
          h("button", { type: "button", "aria-pressed": String(stop.id === chrome.railActive), title: stop.title || "", onclick: () => this.current.goToScale(stop.id) }, stop.label)
        )
      );
    }
  }

  renderLegend() {
    const counts = new Map();
    for (const entity of this.shownEntities()) if (entity.status) counts.set(entity.status, (counts.get(entity.status) || 0) + 1);
    const chrome = this.current?.chrome?.() || {};
    this.legend.render({ model: this.model, counts, isolate: this.state.isolate, lens: this.state.lens, open: this.state.legendOpen, together: chrome.together, togetherActive: chrome.togetherActive });
  }

  renderIndex() {
    if (this.state.indexOpen) this.index.render({ sections: this.sections(), selected: this.state.selected });
  }

  renderPanel() {
    this.panel.show({ model: this.model, entity: this.state.selected ? this.model.get(this.state.selected) : null });
    this.frame.classList.toggle("has-panel", Boolean(this.state.selected));
    if (this.stage) {
      const open = Boolean(this.state.selected);
      const narrow = this.clientWidth < 760;
      this.stage.setInsets(open ? (narrow ? { bottom: this.panel.offsetHeight } : { right: this.panel.offsetWidth + 16 }) : {});
    }
  }

  // ------------------------------------------------------------ pointer and keys

  listen() {
    const canvas = this.canvas;
    let pending = null;
    canvas.addEventListener("pointermove", (event) => {
      if (event.buttons || event.pointerType === "touch") return;
      pending = { x: event.clientX, y: event.clientY };
      requestAnimationFrame(() => {
        if (!pending) return;
        const hit = this.stage.pick(pending.x, pending.y, this.current.pickRoots);
        pending = null;
        this.current.setHover(hit?.id || null);
        canvas.style.cursor = hit ? "pointer" : "grab";
      });
    });
    canvas.addEventListener("pointerleave", () => this.current?.setHover(null));
    canvas.addEventListener("pointerdown", () => this.hint.classList.add("is-off"), { once: true });
    canvas.addEventListener("wheel", () => this.hint.classList.add("is-off"), { once: true, passive: true });
    canvas.addEventListener("pointerup", (event) => {
      if (this.stage.rig.dragged || event.button > 0) return;
      const hit = this.stage.pick(event.clientX, event.clientY, this.current.pickRoots);
      this.select(hit?.id || null);
    });
    canvas.addEventListener("keydown", (event) => {
      if (this.stage.rig.nudge(event.key)) event.preventDefault();
    });
    this.shadowRoot.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        if (this.state.selected) this.select(null);
        else if (this.state.indexOpen) this.toggleIndex(false);
      }
    });
  }
}

customElements.define("cells-viewer", CellsViewer);
