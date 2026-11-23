// One view standing alone, on a page of its own (tools/build_view_page.mjs): the page's stage
// with the view in it, its panel (a bottom sheet on a phone), its legend, its search and the
// choices its card offers. It shows a view before the view is on the map's page, and it gives
// the view the same calls the viewer gives every view (setSelection, then focus, then the
// panel and the room the panel takes), so what it shows is what the viewer will show.
//
// A view's mount module (src/standalone/<view>.js) calls mountView({ make, styles }) with how
// to make the view; nothing here knows which view it is. The page carries its data as JSON
// blocks: the scene (data-standalone="scene") and each further file (data-standalone-into="key",
// put into the scene under that key, as the viewer's build carries it).

import { css } from "../ui/styles.js";
import { h, statusSwatch } from "../ui/dom.js";
import "../ui/panel.js";
import "../ui/timeline.js";
import { SceneModel } from "../scene/model.js";
import { Stage } from "../core/stage.js";
import { LabelLayer } from "../core/labels.js";

/** The words the page says on itself, always: the tool writes them in the page's notice. */
export const NOTICE = "One view of Cells, standing alone";

const NARROW = 700;

const STYLE = `
:host { display: block; position: absolute; inset: 0; }
.frame { position: absolute; inset: 0; }
.bar-card { position: absolute; left: 12px; top: 12px; right: auto; z-index: 5; padding: 8px 10px; display: flex; flex-wrap: wrap; gap: 8px 10px; align-items: center; max-width: calc(100% - 24px); box-sizing: border-box; }
.bar-card b { font-weight: 600; }
.bar-card input, .bar-card select { font: inherit; font-size: 13px; padding: 5px 8px; border-radius: 8px; border: 1px solid var(--line); background: var(--bg); color: var(--fg); min-width: 0; }
.bar-card input { width: 170px; }
.bar-card select { max-width: 210px; }
cells-panel { position: absolute; right: 12px; top: 12px; bottom: 12px; width: min(400px, 46vw); overflow: auto; z-index: 6; }
.legend-card { position: absolute; left: 12px; bottom: 12px; z-index: 5; padding: 8px 12px; width: min(320px, calc(100% - 24px)); max-height: calc(100% - 96px); overflow: auto; box-sizing: border-box; font-size: 12px; line-height: 1.3; }
.legend-card summary { cursor: pointer; font-weight: 600; }
.legend-card ul { list-style: none; margin: 6px 0 2px; padding: 0; display: grid; gap: 5px; }
.legend-card li { display: flex; gap: 8px; align-items: center; }
.legend-card li b { margin-left: auto; font-weight: 500; color: var(--muted); font-variant-numeric: tabular-nums; }
.legend-card p { margin: 6px 0 0; color: var(--muted); }
/* A view that keeps a clock (its chrome gives a timeline) has the page's timeline at the foot. */
.frame cells-timeline { left: 344px; right: 12px; bottom: 12px; max-width: none; margin: 0; z-index: 5; }
.frame.has-panel cells-timeline { right: calc(min(400px, 46vw) + 24px); }
@media (max-width: 1000px) { .frame.has-timeline .legend-card { bottom: 84px; } .frame cells-timeline { left: 12px; } }
@media (max-width: ${NARROW}px) {
  .bar-card { left: 8px; right: 8px; top: 8px; max-width: none; flex-wrap: nowrap; gap: 6px; padding: 6px 8px; }
  .frame cells-timeline, .frame.has-panel cells-timeline { left: 8px; right: 8px; bottom: 8px; }
  .frame.has-timeline .legend-card { bottom: 76px; }
  .frame.has-timeline cells-panel { bottom: 76px; max-height: 40%; }
  .bar-card b { flex: none; font-size: 13px; }
  .bar-card input { flex: 1 1 0; width: auto; }
  .bar-card select { flex: 1 1 0; max-width: none; }
  .bar-card .wide-only { display: none; }
  cells-panel { left: 8px; right: 8px; top: auto; bottom: 8px; width: auto; max-height: 46%; }
  .legend-card { left: 8px; bottom: 8px; width: auto; max-width: calc(100% - 16px); }
}
`;

/** The page's data: the scene, with each further file put into it under its key. */
export function readData(root = document) {
  const block = root.querySelector('script[data-standalone="scene"]');
  if (!block) throw new Error("the page carries no scene");
  const scene = JSON.parse(block.textContent);
  for (const more of root.querySelectorAll("script[data-standalone-into]")) scene[more.dataset.standaloneInto] = JSON.parse(more.textContent);
  return scene;
}

/** Registers <cells-standalone>, which mounts the view `make` returns. */
export function mountView({ make, styles = "" }) {
  class StandaloneView extends HTMLElement {
    connectedCallback() {
      if (this.stage) return;
      this.model = new SceneModel(readData(document));
      this.replaceChildren();
      const root = this.attachShadow({ mode: "open" });
      this.canvas = h("canvas", { tabIndex: 0, role: "img", "aria-label": "The view" });
      this.labelBox = h("div", { class: "labels" });
      this.panel = h("cells-panel", { class: "card", hidden: true });
      this.bar = h("div", { class: "card bar-card" });
      this.legendBox = h("details", { class: "card legend-card" });
      this.timeline = h("cells-timeline", { class: "card", hidden: true });
      this.frame = h("div", { class: "frame" }, this.canvas, this.labelBox, this.bar, this.legendBox, this.timeline, this.panel);
      root.append(h("style", {}, css + styles + STYLE), this.frame);
      this.stage = new Stage({ canvas: this.canvas, host: this });
      this.labels = new LabelLayer(this.labelBox, this.stage);
      this.stage.afterRender.add(() => this.labels.layout());
      this.lens = make(this.stage, this.model, this.labels);
      this.stage.onTick((dt, time, real) => this.lens.update?.(dt, time, real));
      this.stage.onPalette((palette) => this.lens.applyPalette?.(palette));
      this.lens.onChrome = () => this.renderChrome();
      if (this.lens.address) this.lens.onAddress = () => {
        try {
          const url = new URL(location.href);
          for (const [key, value] of Object.entries(this.lens.address())) {
            if (value) url.searchParams.set(key, value);
            else url.searchParams.delete(key);
          }
          history.replaceState(null, "", url);
        } catch {} // A preview frame may keep its address read-only.
      };
      this.lens.activate();
      this.lens.restore?.(new URLSearchParams(location.search));
      this.canvas.setAttribute("aria-label", this.lens.chrome?.().card?.heading || "The view");
      this.renderBar();
      this.renderChrome();
      this.wire();
      this.stage.invalidate();
      window.__standalone = this;
    }

    /** The card's title, the search (where the view has one) and its choices, as small controls. */
    renderBar() {
      const card = this.lens.chrome?.().card || {};
      const parts = [h("b", {}, card.heading || "")];
      if (typeof this.lens.setQuery === "function") {
        this.find = h("input", { type: "search", placeholder: "Find", "aria-label": `Find in ${card.heading || "the view"}`, oninput: () => this.lens.setQuery(this.find.value) });
        parts.push(this.find);
      }
      const choose = (spec, call) => {
        if (!spec?.options?.length || typeof call !== "function") return null;
        const select = h("select", { "aria-label": spec.label, onchange: () => call.call(this.lens, select.value) }, ...spec.options.map(([value, label]) => h("option", { value }, label)));
        select.value = spec.active || spec.options[0][0];
        return select;
      };
      // A view with levels of its own (the viewer gives them in its level switch) chooses them here first.
      const levels = typeof this.lens.levels === "function" ? this.lens.levels() : null;
      this.levelSelect = levels?.length > 1 ? choose({ label: "Level", options: levels.map((level) => [level.id, level.label]), active: levels.find((level) => level.active)?.id }, this.lens.setLevel) : null;
      this.markSelect = choose(card.marks, this.lens.setMark);
      this.modeSelect = choose(card.modes, this.lens.setMode);
      // On a phone the bar keeps to one row: the title, the search and the first choice.
      const chosen = [this.levelSelect, this.markSelect, this.modeSelect].filter(Boolean);
      for (const select of chosen.slice(1)) select.classList.add("wide-only");
      parts.push(...chosen);
      this.bar.replaceChildren(...parts);
    }

    /** The legend card, from the view's chrome: what each mark drawn now stands for. */
    renderChrome() {
      const chrome = this.lens.chrome?.() || {};
      if (this.lens.id === "laws" && chrome.card?.own) {
        this.bar.replaceChildren(h("b", {}, chrome.card.heading), chrome.back ? h("button",{type:"button",onclick:()=>this.lens.back()},chrome.back) : h("span"), ...chrome.card.own());
      }
      this.timeline.hidden = !chrome.timeline;
      this.frame.classList.toggle("has-timeline", Boolean(chrome.timeline));
      if (chrome.timeline) this.timeline.bind(chrome.timeline.player, chrome.timeline);
      if (this.levelSelect) this.levelSelect.value = this.lens.levels().find((level) => level.active)?.id || this.levelSelect.value;
      const legend = chrome.legend;
      this.legendBox.hidden = !legend || (this.lens.selected && this.narrow());
      if (!legend) return;
      const open = this.legendBox.open;
      this.legendBox.replaceChildren(
        h("summary", {}, legend.title || "Legend"),
        h("ul", {}, ...(legend.items || []).map((item) => h("li", { title: item.description || "" }, statusSwatch(item.swatch), h("span", {}, item.label), item.count === undefined ? null : h("b", {}, String(item.count))))),
        legend.note ? h("p", {}, legend.note.text) : null
      );
      this.legendBox.open = open;
    }

    narrow() {
      return this.clientWidth <= NARROW;
    }

    wire() {
      const chrome = () => this.lens.chrome?.() || {};
      let down = null;
      this.canvas.addEventListener("pointerdown", (event) => (down = { x: event.clientX, y: event.clientY }));
      this.labelBox.addEventListener("pointerdown", (event) => {
        const label = event.target.closest("[data-label]");
        if (!label || event.button > 0) return;
        down = { x: event.clientX, y: event.clientY, label: label.dataset.label };
        this.stage.rig.down(event);
        event.preventDefault();
      });
      this.labelBox.addEventListener("wheel", (event) => this.stage.rig.wheel(event), { passive: false });
      this.canvas.addEventListener("pointerup", (event) => {
        const start = down;
        down = null;
        if (!start || event.button > 0 || this.stage.rig.dragged || Math.hypot(event.clientX - start.x, event.clientY - start.y) > 5) return;
        const id = start.label || this.stage.pick(event.clientX, event.clientY, this.lens.pickRoots)?.id;
        if (!this.lens.openOnMap?.(id)) this.select(id || null);
      });
      this.canvas.addEventListener("pointermove", (event) => this.lens.setHover?.(this.stage.pick(event.clientX, event.clientY, this.lens.pickRoots)?.id || null));
      // As the viewer gives keys to a view (src/ui/viewer.js): ] or Page Down to the next part, [ or Page Up to the one before; the arrows turn the camera.
      this.canvas.addEventListener("keydown", (event) => {
        const step = { "]": 1, PageDown: 1, "[": -1, PageUp: -1 }[event.key];
        if (step && this.lens.step) {
          this.select(this.lens.step(step));
          event.preventDefault();
        } else if (this.stage.rig.nudge?.(event.key)) event.preventDefault();
        if (event.key === "Escape") this.select(null);
        if (event.key === " " && chrome().timeline) { chrome().timeline.player.toggle(); event.preventDefault(); }
      });
      // The panel's own links and close button choose through the page's event.
      this.shadowRoot.addEventListener("cells-select", (event) => {
        event.stopPropagation();
        this.select(event.detail?.id || null);
      });
    }

    /** In the viewer's order (viewer.js select, then renderPanel): the choice, the move, the panel, then the room it takes. */
    select(id) {
      const chosen = id && this.lens.has?.(id) ? id : null;
      this.lens.setSelection(chosen);
      if (chosen) this.lens.focus?.(chosen);
      else if (this.lens.homeView) this.stage.rig.flyTo(this.lens.homeView(), 900);
      this.panel.show({ model: this.model, entity: chosen ? this.lens.describe(chosen) : null });
      const narrow = this.narrow();
      if (chosen) this.legendBox.open = false;
      this.renderChrome();
      this.frame.classList.toggle("has-panel", Boolean(chosen));
      this.stage.setInsets(chosen ? (narrow ? { bottom: this.panel.offsetHeight + 8 } : { right: this.panel.offsetWidth + 16 }) : {});
      this.stage.invalidate();
    }
  }
  if (!customElements.get("cells-standalone")) customElements.define("cells-standalone", StandaloneView);
}
