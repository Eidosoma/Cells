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
    this.viewCard = h("div", { class: "view card", hidden: true });
    this.scaleLine = h("span", { class: "scalebar-line" });
    this.scaleText = h("span", { class: "scalebar-text" });
    this.scaleBar = h("div", { class: "scalebar", hidden: true }, this.scaleLine, this.scaleText);
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
      this.viewCard,
      this.scaleBar,
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
      this.labels.blocked = () => this.blockedRects();
      this.stage.afterRender.add(() => this.labels.layout());
      this.stage.afterRender.add(() => this.updateScaleBar());
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
    if (query.get("size")) this.current?.setSizeMode?.(query.get("size"));
    if (query.get("colour")) this.current?.setColourBy?.(query.get("colour"));
    if (query.get("scale")) this.current?.goToScale?.(query.get("scale"), true);
    if (this.stage && (query.get("azimuth") || query.get("polar") || query.get("distance"))) {
      const view = {};
      for (const name of ["azimuth", "polar", "distance"]) if (query.get(name)) view[name] = Number(query.get(name));
      this.stage.rig.setView(view);
    }
    if (query.get("isolate")) this.setIsolate(query.get("isolate"));
    if (query.get("together")) this.current?.setTogether?.(query.get("together"));
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
    this.viewCard.hidden = !chrome.view;
    if (chrome.view) {
      this.viewCard.replaceChildren(
        this.segmented("Colour", [["biology", "Biology"], ["status", "Status"]], chrome.view.colour, (value) => this.current.setColourBy(value)),
        this.segmented("Sizes", [["schematic", "Schematic"], ["real", "To scale"]], chrome.view.size, (value) => this.current.setSizeMode(value)),
        h("p", { class: "view-note" }, chrome.view.size === "real" ? "Sizes and numbers nearer a real cell, about 20 µm across. Dots stand for what is too small to see; counts are indicative." : "Parts are enlarged and few, so each can be seen.")
      );
    }
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

  segmented(label, options, active, onPick) {
    return h(
      "div",
      { class: "seg-row" },
      h("span", { class: "seg-label" }, label),
      h(
        "div",
        { class: "seg", role: "group", "aria-label": label },
        options.map(([value, text]) => h("button", { type: "button", "aria-pressed": String(value === active), onclick: () => onPick(value) }, text))
      )
    );
  }

  /** Panels that labels must not run under, in the viewer's own coordinates. */
  blockedRects() {
    const origin = this.getBoundingClientRect();
    return [this.legend, this.viewCard, this.rail, this.panel, this.index]
      .filter((element) => !element.hidden)
      .map((element) => element.getBoundingClientRect())
      .filter((rect) => rect.width && rect.height)
      .map((rect) => ({ left: rect.left - origin.left, top: rect.top - origin.top, right: rect.right - origin.left, bottom: rect.bottom - origin.top }));
  }

  /** A bar of a round physical length at the distance the camera is looking at. */
  updateScaleBar() {
    const info = this.current?.scaleInfo?.();
    let key = "none", width = 0, text = "";
    if (info?.micronsPerUnit) {
      const { camera, rig, height } = this.stage;
      const pixelsPerMicron = height / (2 * rig.distance * Math.tan((camera.fov * Math.PI) / 360)) / info.micronsPerUnit;
      const most = 150 / pixelsPerMicron; // the longest bar we would draw, in micrometres
      const power = Math.pow(10, Math.floor(Math.log10(most)));
      const length = [5, 2, 1].map((step) => step * power).find((value) => value <= most) ?? power;
      width = Math.round(length * pixelsPerMicron);
      const size = length >= 10000 ? `${length / 10000} cm` : length >= 1000 ? `${length / 1000} mm` : length >= 1 ? `${length} µm` : `${Math.round(length * 1000)} nm`;
      text = info.note ? `${size} · ${info.note}` : size;
      key = `${width}|${text}`;
    } else if (info?.note) {
      text = info.note;
      key = text;
    }
    if (key === this.scaleKey) return;
    this.scaleKey = key;
    this.scaleBar.hidden = key === "none";
    this.scaleLine.hidden = !width;
    this.scaleLine.style.width = `${width}px`;
    this.scaleText.textContent = text;
  }

  renderLegend() {
    const counts = new Map();
    for (const entity of this.shownEntities()) if (entity.status) counts.set(entity.status, (counts.get(entity.status) || 0) + 1);
    const chrome = this.current?.chrome?.() || {};
    this.legend.render({ model: this.model, counts, isolate: this.state.isolate, lens: this.state.lens, open: this.state.legendOpen, together: chrome.together, togetherActive: chrome.togetherActive, view: chrome.view });
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
      const label = this.pressedLabel;
      this.pressedLabel = null;
      if (this.stage.rig.dragged || event.button > 0) return;
      if (label) {
        this.select(label);
        return;
      }
      const hit = this.stage.pick(event.clientX, event.clientY, this.current.pickRoots);
      this.select(hit?.id || null);
    });
    // Labels lie over the canvas. A press on one is handed to the camera control, which
    // captures the pointer on the canvas: a drag turns the view, a plain click selects the label.
    const labels = this.labelBox;
    labels.addEventListener("pointerdown", (event) => {
      const button = event.target.closest("[data-label]");
      if (!button || event.button > 0) return;
      this.pressedLabel = button.dataset.label;
      this.hint.classList.add("is-off");
      this.stage.rig.down(event);
      event.preventDefault();
    });
    labels.addEventListener("wheel", (event) => this.stage.rig.wheel(event), { passive: false });
    labels.addEventListener("pointerover", (event) => {
      const button = event.target.closest("[data-label]");
      if (button && !event.buttons) this.current?.setHover(button.dataset.label);
    });
    labels.addEventListener("pointerout", (event) => {
      if (event.target.closest("[data-label]") && !event.buttons) this.current?.setHover(null);
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
