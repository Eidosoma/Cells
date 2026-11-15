// <cells-viewer>: the whole viewer as one custom element. Give it a scene (a JSON
// script child, the `scene` property or a `src` URL) and it draws it, with a lens
// switch, a legend, a list of parts and a detail panel.
//
//   <cells-viewer lens="cell"><script type="application/json">{...}</script></cells-viewer>
//
// Events: "cells-ready" once drawn; "cells-selected" with { id } when the selection changes.

import { css } from "./styles.js";
import { h, formatDate, svg } from "./dom.js";
import "./legend.js";
import "./index.js";
import { item as listed } from "./panel.js";
import "./timeline.js";
import { SceneModel } from "../scene/model.js";
import { Stage } from "../core/stage.js";
import { LabelLayer } from "../core/labels.js";
import { StackLens } from "../lenses/stack.js";
import { CellLens, defaultSpecies, MODELLED } from "../lenses/cell.js";
import { ProteinLens, defaultAtlas, inSpecies } from "../lenses/proteins.js";
import { ReplayLens } from "../lenses/replay.js";
import { Catalogue } from "../replay/catalogue.js";

// The views, in the order of the switch. "short" is the name on a narrow screen.
// "needs" says what the scene must hold for the view to be offered.
// From this width up the species switch stands in the bar; below it, in the view's card.
const SPECIES_IN_BAR = 1000;

const LENSES = [
  { id: "cell", label: "Cell and scales", short: "Cell", make: (stage, model, labels) => new CellLens(stage, model, labels) },
  { id: "proteins", label: "Protein atlas", short: "Proteins", needs: (scene) => scene.proteins, make: (stage, model, labels) => new ProteinLens(stage, model, labels) },
  { id: "experiments", label: "Experiments", short: "Runs", needs: (scene) => scene.replays?.runs?.length, make: (stage, model, labels) => new ReplayLens(stage, model, labels) },
  { id: "engine", label: "Engine", short: "Engine", make: (stage, model, labels) => new StackLens(stage, model, labels) },
];

class CellsViewer extends HTMLElement {
  static get observedAttributes() {
    return ["lens"];
  }

  constructor() {
    super();
    // "species" is the one species the page shows: the levels and the cell of the cell view and the
    // species' side of the protein atlas follow it. It stays while the page is open. "atlas" is
    // the same choice under its earlier name.
    this.state = { lens: null, selected: null, isolate: null, legendOpen: false, indexOpen: false, species: null, atlas: null };
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
    this.speciesBox = h("div", { class: "species", hidden: true });
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
    // The resting look's switch and its few words stand over the scale bar: there they take no room from the labels' column.
    this.lookBox = h("div", { class: "look-box", hidden: true });
    this.scaleBar = h("div", { class: "scalebar", hidden: true }, this.lookBox, this.scaleLine, this.scaleText);
    this.hint = h("p", { class: "hint" }, "Drag to turn · scroll to zoom · click a part");
    this.timeline = h("cells-timeline", { class: "card", hidden: true });
    this.fallback = h("p", { class: "fallback", hidden: true });
    this.frame = h(
      "div",
      { class: "frame", style: "position:absolute;inset:0" },
      h("div", { class: "stage" }, this.canvas, this.labelBox),
      (this.bar = h("header", { class: "bar" }, h("div", { class: "brand" }, h("b", {}, "Cells"), h("span", {}, "Architecture map")), this.switchBox, this.speciesBox, h("div", { class: "bar-end" }, this.stamp, this.indexButton))),
      this.hint,
      this.caveat,
      this.timeline,
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
    root.addEventListener("cells-finding", (event) => this.current?.setFinding?.(event.detail));
    // Quantity layers of a replay: which layer holds a channel, and how strongly the marks are drawn.
    root.addEventListener("cells-layer", (event) => this.current?.setLayer?.(event.detail.id, event.detail.on));
    root.addEventListener("cells-strength", (event) => this.current?.setStrength?.(event.detail));
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
    this.mapStamp = [meta.as_of ? `As of ${formatDate(meta.as_of)}` : "", meta.revision ? `main ${meta.revision}` : ""].filter(Boolean).join(" · ");
    // A view is offered only if the scene holds what it draws.
    this.views = LENSES.filter((lens) => !lens.needs || lens.needs(this.model.raw));
    // The runs that can be replayed, read without the 3D stage so the list works without it.
    this.replays = new Catalogue(this.model.raw.replays);
    // The page opens on the species whose file says so; a scene that names no species opens the
    // protein atlas on the inventory's own.
    this.state.species = defaultSpecies(this.model.raw) ?? defaultAtlas(this.model.raw.proteins);
    this.state.atlas = this.state.species;
    if (this.state.species) this.dataset.species = this.dataset.atlas = this.state.species;
    for (const lens of this.views) {
      this.switchBox.append(
        h(
          "button",
          { type: "button", dataset: { lens: lens.id }, "aria-pressed": "false", "aria-label": lens.label, onclick: () => this.setLens(lens.id, true) },
          h("span", { class: "long" }, lens.label),
          h("span", { class: "short" }, lens.short)
        )
      );
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
      // The species switch moves between the bar and the card as the window crosses a width.
      new ResizeObserver(() => {
        if (this.clientWidth !== this.widthSeen) {
          this.widthSeen = this.clientWidth;
          this.renderChrome(); // the switch may fit the bar again, or no longer
        } else this.fitCard();
      }).observe(this);
      document.fonts?.ready.then(() => {
        this.labels.measure();
        this.renderChrome(); // words are as wide as they will be only now: the species switch may fit the bar, or no longer
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
    if (query.get("still")) {
      this.frame.classList.add("is-still");
      if (this.stage) this.stage.rig.instant = true;
    }
    if (query.get("species") || query.get("atlas")) this.setSpecies(query.get("species") || query.get("atlas"));
    // The resting look (core/look.js): "look=plain" is the look as it was, "look=full" holds every
    // effect on; "fps=1" shows the frame rate with a switch for each effect, for judging on a device.
    if (this.stage && query.get("look")) this.stage.look.choose(query.get("look"));
    if (this.stage && query.get("fps")) this.stage.look.trial = true;
    const wanted = query.get("lens") || location.hash.slice(1) || this.getAttribute("lens") || this.views[0].id;
    this.setLens(this.views.some((lens) => lens.id === wanted) ? wanted : this.views[0].id);
    if (query.get("size")) this.current?.setSizeMode?.(query.get("size"));
    // The protein atlas: the machines Cells has laws for ("units") or the species' own proteins ("own").
    if (query.get("show")) this.current?.setMode?.(query.get("show"), { user: true });
    if (query.get("colour")) this.current?.setColourBy?.(query.get("colour"));
    if (query.get("scale")) this.current?.goToScale?.(query.get("scale"), true);
    if (query.get("isolate")) this.setIsolate(query.get("isolate"));
    if (query.get("together")) this.current?.setTogether?.(query.get("together"));
    if (query.get("finding")) this.current?.setFinding?.(query.get("finding"));
    // A replay: which run, where the playhead stands, which record colours the sheet.
    if (query.get("time")) this.current?.seek?.(Number(query.get("time")));
    const settle = () => {
      if (query.get("record")) this.current?.setRecord?.(query.get("record"));
      // Quantity layers: "layers=junction-drops,-voltage-relief" switches the first on and the second off; "strength=bold".
      if (query.get("strength")) this.current?.setStrength?.(query.get("strength"));
      if (query.get("layers")) this.current?.setLayers?.(query.get("layers"));
      if (query.get("select")) this.select(query.get("select"), { fly: true });
      // A stated camera angle or distance has the last word, also over the flight to a selected part.
      if (this.stage && (query.get("azimuth") || query.get("polar") || query.get("distance"))) {
        const view = {};
        for (const name of ["azimuth", "polar", "distance"]) if (query.get(name)) view[name] = Number(query.get(name));
        this.stage.rig.setView(view);
      }
    };
    // A view that loads its data first (a run) is ready a moment later; the others are ready now.
    const loading = query.get("run") ? this.current?.show?.(query.get("run")) : this.current?.ready;
    if (loading?.then) loading.then(settle).then(() => query.get("play") && this.current?.player?.play());
    else settle();
    if (query.get("index")) this.toggleIndex(true);
    window.addEventListener("hashchange", () => {
      const name = location.hash.slice(1);
      if (this.views.some((lens) => lens.id === name) && name !== this.state.lens) this.setLens(name);
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
    const spec = this.views?.find((lens) => lens.id === id);
    if (!spec || !this.model) return;
    this.current?.deactivate();
    this.state.lens = id;
    this.state.isolate = null;
    if (this.stage) {
      if (!this.lenses.has(id)) {
        const lens = spec.make(this.stage, this.model, this.labels);
        lens.onChrome = () => {
          if (this.current === lens) this.renderChrome();
        };
        // A view whose parts change under an open panel (another run is loaded) asks for it again.
        lens.onPanel = () => {
          if (this.current === lens) this.renderPanel();
        };
        // A view that changes what it draws (the protein atlas: the machines, or the species' own
        // proteins): what was chosen and filtered belonged to the other drawing.
        lens.onMode = () => {
          if (this.current !== lens) return;
          this.state.isolate = null;
          if (this.state.selected && !this.shows(this.state.selected)) this.state.selected = null;
          this.renderChrome();
          this.renderPanel();
        };
        // A view that opened or closed something of its own (a family of proteins): the card, the list and the panel follow.
        lens.onOpen = () => {
          if (this.current !== lens) return;
          this.renderChrome();
          this.renderPanel();
        };
        this.lenses.set(id, lens);
      }
      this.current = this.lenses.get(id);
      this.current.setSpecies?.(this.state.species);
      this.current.setAtlas?.(this.state.species);
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
    if (this.state.lens === "experiments") return this.replays.entities();
    return this.model.inLens(this.state.lens);
  }

  shows(id) {
    if (!id) return false;
    if (this.current) return this.current.has(id);
    return this.shownEntities().some((entity) => entity.id === id);
  }

  /** A part by its id: one of the scene's, or one the current view makes itself (a run, a cell of a run). */
  lookup(id) {
    if (!id) return null;
    const entity = this.model.get(id) || this.current?.describe?.(id) || (this.state.lens === "experiments" ? this.replays.describe(id) : null) || null;
    // A part is shown as the chosen species has it: a unit with that species' side of the atlas,
    // a level under the species' name for it.
    if (this.state.lens === "proteins") return this.current?.asShown ? this.current.asShown(entity) : inSpecies(entity, this.model.raw.proteins, this.state.species);
    return this.state.lens === "cell" && this.current?.inSpecies ? this.current.inSpecies(entity) : entity;
  }

  sections() {
    if (this.current) return this.current.sections();
    if (this.state.lens === "experiments") return this.replays.sections();
    const groups = new Map();
    for (const part of this.shownEntities()) {
      const entity = this.state.lens === "proteins" ? inSpecies(part, this.model.raw.proteins, this.state.species) : part;
      const key = entity.eyebrow || (entity.group === "biology" ? entity.scale || entity.kind : entity.group);
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(entity);
    }
    return [...groups].map(([key, entities]) => ({ label: this.model.groups.find((group) => group.id === key)?.label || key, entities }));
  }

  // ------------------------------------------------------------ state changes

  select(id, { fly = false } = {}) {
    if (id && !this.lookup(id)) return;
    if (id && !this.shows(id)) {
      if (!this.model.get(id)) return; // a part of a view that is not the one shown
      // The part lives in another view: go there.
      const home = this.model.lensOf(this.model.get(id));
      if (home === this.state.lens || !this.views.some((lens) => lens.id === home)) return;
      this.state.selected = id;
      this.setLens(home, true);
      if (!this.shows(id)) this.state.selected = null;
    }
    const held = this.state.selected;
    this.state.selected = id && this.shows(id) ? id : null;
    this.current?.setSelection(this.state.selected);
    // Letting go of everything also lets go of what a view has open (a family of proteins).
    if (!this.state.selected) this.current?.letGo?.(held);
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

  /** The species the page can show: the scene's species, or the atlases of a scene that names none. */
  speciesChoices() {
    const species = this.model?.raw.species || [];
    return (species.length ? species : this.model?.raw.proteins?.atlases || []).map((item) => item.id);
  }

  /**
   * Show another species, in every view that depends on one: the levels and the cell of the
   * cell view, and the species' side of the protein atlas. The choice is kept while the page is open.
   */
  setSpecies(id) {
    if (!this.speciesChoices().includes(id) || id === this.state.species) return;
    this.state.species = this.state.atlas = id;
    this.dataset.species = this.dataset.atlas = id;
    for (const lens of this.lenses.values()) {
      lens.setSpecies?.(id);
      lens.setAtlas?.(id);
    }
    // What the panel says of the species follows the species; a part that has no place in the
    // species now shown is no longer selected.
    if (this.state.selected?.startsWith("species:")) this.state.selected = `species:${id}`;
    if (this.state.selected && !this.shows(this.state.selected)) this.state.selected = null;
    this.current?.setSelection(this.state.selected);
    this.renderChrome();
    this.renderPanel();
    this.stage?.invalidate();
    this.dispatchEvent(new CustomEvent("cells-species", { detail: { id }, bubbles: true, composed: true }));
    this.dispatchEvent(new CustomEvent("cells-atlas", { detail: { id }, bubbles: true, composed: true }));
  }

  /** The same, under the name the protein atlas first gave it. */
  setAtlas(id) {
    this.setSpecies(id);
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
    // The protein atlas says which of its two drawings is shown; no other view has such a thing.
    if (this.state.lens === "proteins" && this.current?.mode) this.dataset.show = this.current.mode;
    else delete this.dataset.show;
    // A caveat on the picture, or what a view is doing (loading a run, or why it could not).
    const words = chrome.caveat || chrome.status || "";
    this.caveat.hidden = !words;
    this.hint.hidden = Boolean(words) || Boolean(chrome.quiet) || !this.stage;
    this.caveat.textContent = words;
    this.caveat.classList.toggle("is-status", Boolean(chrome.status));
    // A view whose data has its own date says so in place of the map's.
    this.stamp.textContent = chrome.stamp || this.mapStamp;
    this.renderSpecies(chrome);
    this.viewCard.hidden = !chrome.view && !chrome.card && !chrome.run;
    this.viewCard.classList.toggle("view-card", Boolean(chrome.card || chrome.run));
    this.viewCard.classList.toggle("run-card", Boolean(chrome.run));
    if (chrome.card) this.viewCard.replaceChildren(...this.card(chrome.card));
    if (chrome.run) this.viewCard.replaceChildren(...this.runCard(chrome.run));
    // A replay brings its playhead.
    this.timeline.hidden = !chrome.timeline;
    this.frame.classList.toggle("has-timeline", Boolean(chrome.timeline));
    if (chrome.timeline) this.timeline.bind(chrome.timeline.player, chrome.timeline);
    else this.timeline.unbind?.();
    if (chrome.view) {
      const view = chrome.view, species = view.species;
      const sizes = view.sizes || ["schematic", "real"];
      const width = view.across >= 1 ? `${Number(view.across.toPrecision(1))} µm` : `${Number((view.across * 1000).toPrecision(1))} nm`;
      const sized =
        sizes.length < 2
          ? `One size mode: a cell about ${width} across is small enough for its molecules to be seen, so the picture is near scale. Membrane proteins are drawn a little enlarged; counts are indicative.`
          : view.size === "real"
            ? `Sizes and numbers nearer a real cell, about ${width} across. Dots stand for what is too small to see; counts are indicative.`
            : "Parts are enlarged and few, so each can be seen.";
      // On a narrow window the species switch stands here, at the head of the card.
      const here = species && !this.speciesInBar;
      this.viewCard.replaceChildren(
        ...[
          here ? this.speciesRow(species) : null,
          here ? h("p", { class: "species-line" }, this.speciesState(species)) : null,
          this.segmented("Colour", [["biology", "Biology"], ["status", "Status"]], view.colour, (value) => this.current.setColourBy(value)),
          sizes.length > 1 ? this.segmented("Sizes", [["schematic", "Schematic"], ["real", "To scale"]], view.size, (value) => this.current.setSizeMode(value)) : null,
          h("p", { class: "view-note" }, sized),
        ].filter(Boolean)
      );
    }
    // The resting look (core/look.js), where the view shown has one: its switch, and what the page says of it.
    const look = chrome.view?.look;
    this.lookBox.hidden = !look;
    if (look) {
      this.lookBox.replaceChildren(
        h("div", { class: "look-switch card" }, this.segmented("Look", [["rich", "Rich"], ["plain", "Plain"]], look.active, (value) => this.current.setLook(value))),
        ...look.notes.map((note) => h("p", { class: "look-note" }, note))
      );
    }
    this.rail.hidden = !chrome.rail;
    if (chrome.rail) {
      this.rail.replaceChildren(
        h("span", { class: "rail-title" }, "Scale"),
        ...chrome.rail.map((stop) =>
          h("button", { type: "button", dataset: { stop: stop.id }, "aria-pressed": String(stop.id === chrome.railActive), title: stop.title || "", onclick: () => this.current.goToScale(stop.id) }, stop.label)
        ),
        // A species of single cells has no further levels: the rail says so in the species' words.
        ...(chrome.railNote ? [h("p", { class: "rail-note" }, chrome.railNote)] : [])
      );
    }
    this.fitCard();
  }

  /**
   * The species switch: one control for the whole page, shown in every view that depends on
   * the species. On a wide window it stands in the bar; on a narrow one, at the head of the
   * view's card. It takes any number of species.
   */
  renderSpecies(chrome) {
    const species = chrome.view?.species || chrome.card?.species || null;
    // The control is drawn afresh: its list, if open, stays with the new button; with no
    // control left to belong to (another view), it closes.
    this.speciesButton = null;
    queueMicrotask(() => {
      if (this.speciesMenu?.open && !this.speciesButton?.isConnected) this.closeSpecies({ focus: false });
    });
    this.speciesInBar = Boolean(species) && this.clientWidth >= SPECIES_IN_BAR;
    this.speciesBox.hidden = !this.speciesInBar;
    this.bar.classList.toggle("with-species", this.speciesInBar);
    this.speciesBox.replaceChildren();
    delete this.bar.dataset.tight;
    if (!this.speciesInBar) return;
    // With many species the bar may not hold the switch: it then stands in the card, as on a narrow
    // window. Its place must not change with the species or the view, so it is settled with each
    // statement a species of this scene would show beside it. The end of the bar gives way first
    // (its stamp shortens), so that is measured too: the List button must stay whole.
    const statement = h("button", { class: "species-state", type: "button" });
    this.speciesBox.append(h("span", { class: "species-label" }, "Species"), this.speciesPicker(species), statement);
    const end = this.indexButton.parentElement;
    const words = [...new Set((this.model.raw.species || []).map((item) => MODELLED[item.modelled?.state] || item.modelled?.state).filter(Boolean))];
    const holds = () =>
      (words.length ? words : [""]).every((word) => {
        statement.textContent = word;
        statement.hidden = !word;
        return this.bar.scrollWidth <= this.bar.clientWidth + 1 && end.scrollWidth <= end.clientWidth + 1;
      });
    // Before the switch gives up its place, the bar is drawn tighter: first without the page's
    // subtitle, then with the short names of the views and no date as well (as on a narrower window).
    let fits = false;
    for (const tight of ["", "1", "2"]) {
      this.bar.dataset.tight = tight;
      fits = holds();
      if (fits) break;
    }
    if (!fits) {
      delete this.bar.dataset.tight;
      this.speciesInBar = false;
      this.speciesBox.hidden = true;
      this.bar.classList.remove("with-species");
      this.speciesBox.replaceChildren();
    } else if (species.modelled) statement.replaceWith(this.speciesState(species));
    else statement.remove();
  }

  /**
   * The species as the list shows them: in the order of the files, under the headings the
   * files give (a species file's `group`; schema/SPECIES.md). Each row says the species'
   * name, its organism, and what Cells models of it.
   */
  speciesRows(species) {
    const said = new Map((this.model.raw.species || []).map((item) => [item.id, item]));
    const rows = species.options.map(([id, label, organism]) => {
      const item = said.get(id) || {};
      const state = item.modelled?.state || null;
      return { id, label, organism: organism || item.organism || "", state, word: state ? MODELLED[state] || state : "", group: item.group || "" };
    });
    // Species with one heading stand together, the headings in the order of their first species; those with none come last.
    const headings = [...new Set(rows.map((row) => row.group).filter(Boolean))];
    return [...headings.flatMap((group) => rows.filter((row) => row.group === group)), ...rows.filter((row) => !row.group)];
  }

  /**
   * The species switch is a dropdown: one button that names the species in view and opens a
   * list of them. It is a list of the page's own and not the browser's select: each row says
   * three things (the species, its organism, what Cells models of it), the rows stand under
   * headings, and the list keeps the page's look in light and dark, on a phone too. The
   * button is a combobox that owns a listbox: the focus stays on the button while the keys
   * move the list's active row, which is what a screen reader announces.
   */
  speciesPicker(species) {
    const menu = (this.speciesMenu ||= { open: false, active: null, typed: "", typedAt: 0 });
    const rows = this.speciesRows(species);
    const current = rows.find((row) => row.id === species.active) || rows[0];
    // Every name lies in the button, one over the other, so that its width does not change with the species.
    const names = rows.map((row) => h("span", row.id === current.id ? {} : { "aria-hidden": "true" }, row.label));
    const button = h(
      "button",
      { class: "species-pick", type: "button", role: "combobox", "aria-haspopup": "listbox", "aria-controls": "species-list", "aria-expanded": String(menu.open), "aria-label": `Species: ${current.label}`, dataset: { speciesPick: current.id } },
      h("span", { class: "species-pick-name" }, names),
      h("span", { class: "species-pick-caret", "aria-hidden": "true" })
    );
    button.addEventListener("click", () => (menu.open ? this.closeSpecies() : this.openSpecies()));
    button.addEventListener("keydown", (event) => this.speciesKey(event));
    this.speciesButton = button;
    this.speciesShown = { rows, active: current.id };
    // Redrawn while its list was open (a file arrived, the window changed): the list stays, under the new button.
    if (menu.open) queueMicrotask(() => menu.open && this.speciesButton === button && this.showSpecies({ focus: true }));
    return button;
  }

  /** The list of species, built once and filled each time it is shown. */
  speciesListbox() {
    if (this.speciesList) return this.speciesList;
    const list = (this.speciesList = h("div", { class: "species-list", role: "listbox", id: "species-list", "aria-label": "Species", hidden: true }));
    // A press on the list must not take the focus from the button, which holds it while the list is open.
    list.addEventListener("mousedown", (event) => event.preventDefault());
    list.addEventListener("pointermove", (event) => {
      const id = event.target.closest?.("[data-species]")?.dataset.species;
      if (id && id !== this.speciesMenu.active) this.moveSpecies(id, { scroll: false });
    });
    list.addEventListener("click", (event) => {
      const id = event.target.closest?.("[data-species]")?.dataset.species;
      if (id) this.chooseSpecies(id);
    });
    // While the list is open a clear sheet lies over the rest of the page: a press beside the
    // list closes it and does nothing else (it does not also pick the part that lay under it).
    const veil = (this.speciesVeil = h("div", { class: "species-veil", hidden: true }));
    veil.addEventListener("mousedown", (event) => event.preventDefault());
    veil.addEventListener("click", () => this.closeSpecies({ focus: false }));
    this.frame.append(veil, list);
    // A press outside the viewer closes it too, and so does leaving the window.
    this.speciesOutside = (event) => {
      const path = event.composedPath();
      if (!path.includes(this.frame)) this.closeSpecies({ focus: false });
    };
    this.speciesAway = () => this.closeSpecies({ focus: false });
    return list;
  }

  /** Fill the list, put it under the button and mark its active row. */
  showSpecies({ focus = false } = {}) {
    const menu = this.speciesMenu, button = this.speciesButton, shown = this.speciesShown;
    if (!menu || !button?.isConnected || !shown) return;
    const list = this.speciesListbox();
    if (!shown.rows.some((row) => row.id === menu.active)) menu.active = shown.active;
    const option = (row) =>
      h(
        "div",
        { class: `species-option${row.id === menu.active ? " is-active" : ""}`, role: "option", id: `species-option-${row.id}`, "aria-selected": String(row.id === shown.active), "aria-label": [row.label, row.organism, row.word].filter(Boolean).join(", "), dataset: { species: row.id, atlas: row.id } },
        h("span", { class: "species-option-name" }, row.label),
        row.word ? h("span", { class: "species-option-state", dataset: { state: row.state } }, row.word) : null,
        row.organism ? h("span", { class: "species-option-organism" }, row.organism) : null
      );
    const headings = [...new Set(shown.rows.map((row) => row.group))];
    list.replaceChildren(
      ...headings.map((group) =>
        h("div", { class: "species-group", role: "group", "aria-label": group || "Other species" }, group ? h("div", { class: "species-group-name", "aria-hidden": "true" }, group) : null, shown.rows.filter((row) => row.group === group).map(option))
      )
    );
    list.hidden = this.speciesVeil.hidden = false;
    // Under the button, within the frame; as wide as its rows need, and no taller than the room below.
    const frame = this.frame.getBoundingClientRect(), at = button.getBoundingClientRect();
    const width = Math.min(Math.max(at.width, 320), frame.width - 16);
    const top = at.bottom - frame.top + 6;
    list.style.width = `${width}px`;
    list.style.left = `${Math.max(8, Math.min(at.left - frame.left, frame.width - width - 8))}px`;
    list.style.top = `${top}px`;
    list.style.maxHeight = `${Math.max(120, frame.height - top - 12)}px`;
    button.setAttribute("aria-expanded", "true");
    button.setAttribute("aria-activedescendant", `species-option-${menu.active}`);
    list.querySelector(".is-active")?.scrollIntoView({ block: "nearest" });
    if (focus && this.shadowRoot.activeElement !== button) button.focus({ preventScroll: true });
  }

  /** Open the list of species, on the species in view or on the one named. */
  openSpecies(active) {
    const menu = this.speciesMenu;
    if (!menu || !this.speciesButton?.isConnected) return;
    menu.open = true;
    menu.active = active || this.speciesShown.active;
    this.showSpecies({ focus: true });
    window.addEventListener("pointerdown", this.speciesOutside, true);
    window.addEventListener("blur", this.speciesAway);
  }

  /** Close it, choosing nothing. The focus goes back to the button unless the visitor went elsewhere. */
  closeSpecies({ focus = true } = {}) {
    const menu = this.speciesMenu;
    if (!menu?.open) return;
    menu.open = false;
    menu.typed = "";
    if (this.speciesList) this.speciesList.hidden = this.speciesVeil.hidden = true;
    window.removeEventListener("pointerdown", this.speciesOutside, true);
    window.removeEventListener("blur", this.speciesAway);
    const button = this.speciesButton;
    if (!button?.isConnected) return;
    button.setAttribute("aria-expanded", "false");
    button.removeAttribute("aria-activedescendant");
    if (focus) button.focus({ preventScroll: true });
  }

  /** Make another row the active one: what the keys and the pointer move, before anything is chosen. */
  moveSpecies(id, { scroll = true } = {}) {
    const menu = this.speciesMenu, list = this.speciesList;
    if (!menu?.open || !list) return;
    menu.active = id;
    for (const row of list.querySelectorAll("[data-species]")) row.classList.toggle("is-active", row.dataset.species === id);
    this.speciesButton?.setAttribute("aria-activedescendant", `species-option-${id}`);
    if (scroll) list.querySelector(".is-active")?.scrollIntoView({ block: "nearest" });
  }

  /** Show the species chosen. The control is redrawn with it, so the focus is put back on its button. */
  chooseSpecies(id) {
    this.closeSpecies({ focus: false });
    this.setSpecies(id);
    this.speciesButton?.focus({ preventScroll: true });
  }

  /** The keys of the dropdown: open, move, choose, close, and a letter to go to a species by its name. */
  speciesKey(event) {
    const menu = this.speciesMenu, rows = this.speciesShown?.rows || [], key = event.key;
    if (!menu || !rows.length || event.ctrlKey || event.metaKey || event.altKey) return;
    const at = rows.findIndex((row) => row.id === menu.active);
    const to = (index) => this.moveSpecies(rows[Math.max(0, Math.min(rows.length - 1, index))].id);
    const letter = () => {
      if (key.length !== 1 || key === " ") return false;
      // Letters typed in quick succession spell the start of a name; one letter again goes to the next that begins with it.
      const now = performance.now();
      menu.typed = now - menu.typedAt < 700 ? menu.typed + key.toLowerCase() : key.toLowerCase();
      menu.typedAt = now;
      // By the name the row shows first; by the organism's name only where no row's own name begins so.
      const begins = (text) => (list) => list.find((row) => row && row.label.toLowerCase().startsWith(text)) || list.find((row) => row && row.organism.toLowerCase().startsWith(text));
      const from = menu.open ? at : rows.findIndex((row) => row.id === this.speciesShown.active);
      const ordered = [...rows.slice(from + 1), ...rows.slice(0, from + 1)];
      const found = (menu.typed.length > 1 && begins(menu.typed)([rows[from], ...ordered])) || begins(menu.typed.at(-1))(ordered);
      if (!found) return true;
      if (menu.open) this.moveSpecies(found.id);
      else this.openSpecies(found.id);
      return true;
    };
    if (!menu.open) {
      if (["Enter", " ", "ArrowDown", "ArrowUp", "Home", "End"].includes(key)) {
        event.preventDefault();
        this.openSpecies(key === "Home" ? rows[0].id : key === "End" ? rows.at(-1).id : undefined);
      } else if (letter()) event.preventDefault();
      return;
    }
    if (key === "Escape") {
      // Closing the list is all Escape does here: it does not also let go of what is selected.
      event.preventDefault();
      event.stopPropagation();
      this.closeSpecies();
    } else if (key === "ArrowDown") (event.preventDefault(), to(at + 1));
    else if (key === "ArrowUp") (event.preventDefault(), to(at - 1));
    else if (key === "Home" || key === "PageUp") (event.preventDefault(), to(0));
    else if (key === "End" || key === "PageDown") (event.preventDefault(), to(rows.length - 1));
    else if (key === "Enter" || key === " ") (event.preventDefault(), this.chooseSpecies(menu.active));
    else if (key === "Tab") this.closeSpecies({ focus: false }); // the focus moves on; nothing is chosen
    else if (letter()) event.preventDefault();
  }

  /** The switch as a row of a card. */
  speciesRow(species) {
    return h("div", { class: "seg-row seg-species" }, h("span", { class: "seg-label" }, "Species"), this.speciesPicker(species));
  }

  /** What Cells models of the species shown, in two or three words; pressing it opens all that is said of the species. */
  speciesState(species) {
    const id = `species:${species.active}`;
    return h(
      "button",
      { class: "species-state", type: "button", dataset: { state: species.modelled.state }, "aria-pressed": String(this.state.selected === id), title: species.modelled.text, onclick: () => this.select(this.state.selected === id ? null : id) },
      MODELLED[species.modelled.state] || species.modelled.state
    );
  }

  /** A view's own summary: headline numbers, what the data is, and where it came from. */
  card({ heading, species, organism, modes, notice, open, stats, text, check, marks, method, extra, extraOpen, sources, notCopied }) {
    const outside = (url) => /^https:\/\//.test(url || "");
    const read = (date) => (/^\d{4}-\d{2}-\d{2}$/.test(date) ? formatDate(date) : date);
    const lens = this.current;
    // Pressing a button of the card redraws the card, so the focus is put back on the button's successor.
    const again = (selector) => this.viewCard.querySelector(selector)?.focus({ preventScroll: true });
    return [
      h("p", { class: "card-title" }, heading),
      // Which species is shown: the page's one switch, here on a narrow window (on a wide one it stands in the bar).
      species && !this.speciesInBar ? this.speciesRow(species) : null,
      organism ? h("p", { class: "card-organism" }, organism) : null,
      // The protein atlas: the machines Cells has laws for, or the species' own proteins.
      modes
        ? h(
            "div",
            { class: "seg seg-wide", role: "group", "aria-label": modes.label },
            modes.options.map(([value, label]) =>
              h(
                "button",
                {
                  type: "button",
                  dataset: { show: value },
                  "aria-pressed": String(value === modes.active),
                  onclick: () => {
                    lens.setMode(value, { user: true });
                    again(`[data-show="${value}"]`);
                  },
                },
                label
              )
            )
          )
        : null,
      // What the view is waiting for, could not read, or does not have.
      notice ? h("p", { class: "card-notice", role: "status" }, notice) : null,
      // What stands open (a family of proteins), and the way back.
      open
        ? h(
            "p",
            { class: "card-open" },
            h("span", { class: "card-open-name" }, h("span", { class: "seg-label" }, "Open"), ` ${open.label} · ${open.count}`),
            h(
              "button",
              {
                class: "pill-button pill-small",
                type: "button",
                dataset: { close: "open" },
                onclick: () => {
                  lens.back();
                  if (this.state.selected) this.select(null);
                },
              },
              "Close"
            )
          )
        : null,
      h("div", { class: "stats" }, stats.map(([value, label]) => h("div", { class: "stat" }, h("b", {}, String(value)), h("span", {}, label)))),
      text ? h("p", { class: "card-text" }, text) : null,
      check ? h("p", { class: "card-text" }, check) : null,
      // Which of the proteins' marks the legend's last block lists.
      marks
        ? h(
            "label",
            { class: "card-marks" },
            h("span", { class: "seg-label" }, marks.label),
            (() => {
              const select = h("select", { id: "cells-mark", class: "run-select", onchange: () => (lens.setMark(select.value), again("#cells-mark")) }, marks.options.map(([value, label]) => h("option", { value, selected: value === marks.active }, label)));
              return select;
            })()
          )
        : null,
      method?.length ? h("details", {}, h("summary", {}, "How it was made"), h("ul", {}, method.map((line) => h("li", {}, line)))) : null,
      // Proteins of the species that bear on the picture but make none of the units drawn.
      extra?.length
        ? h(
            "details",
            { class: "card-more", open: Boolean(extraOpen) },
            h("summary", {}, `${extra.length} more ${extra.length === 1 ? "protein" : "proteins"}, matched to no unit`),
            h("ul", { class: "card-extra" }, extra.map(listed))
          )
        : null,
      h(
        "details",
        {},
        h("summary", {}, "Sources and licences"),
        h(
          "ul",
          {},
          sources.map((source) => {
            const facts = [source.release ? `Release ${source.release}` : "", source.accessed ? `read ${read(source.accessed)}` : "", source.through ? `through ${source.through}` : "", source.licence].filter(Boolean).join(", ");
            return h(
              "li",
              {},
              outside(source.url) ? h("a", { href: source.url, target: "_blank", rel: "noopener" }, source.name) : h("b", {}, source.name),
              // A source that states its class (permissive, non-commercial, no stated terms) shows it, before its own words.
              source.tag ? [" ", h("span", { class: "tag tag-terms", title: source.tag_title || "" }, source.tag)] : null,
              `: ${[source.holds, facts].filter(Boolean).join(". ")}.${source.cite ? ` Cite: ${source.cite}.` : ""}`
            );
          }),
          notCopied ? h("li", {}, notCopied) : null
        )
      ),
    ].filter(Boolean);
  }

  /** A replay's card: the experiment, its runs, and the class the experiment itself records for the run shown. */
  runCard({ heading, text, outcome, experiments = [], runs, klass, ended, colour, details }) {
    const lens = this.current;
    // With a run's details open, the details follow the run picked.
    const pick = (id) => (this.state.selected?.startsWith("run:") ? this.select(`run:${id}`) : lens.show(id));
    const chooser = (id, label, options, active) => {
      const select = h("select", { id, class: "run-select", "aria-label": label, onchange: () => pick(select.value) }, options.map(([value, text_]) => h("option", { value, selected: value === active }, text_)));
      return select;
    };
    // A fact from the record is drawn as a mark with its words beside it, never as a colour alone.
    // The signs are drawn, not typed, so they do not depend on a font having them.
    const SIGNS = { yes: "M4 7.8l2.4 2.4L11 5.2", no: "M4.6 4.6l5.8 5.8M10.4 4.6l-5.8 5.8", mixed: "M7.5 3.4v5M5 5.9h5M5 11.2h5", none: "M4.6 7.5h5.8" };
    const mark = (kind) => h("span", { class: `mark mark-${kind}`, "aria-hidden": "true" }, svg("svg", { viewBox: "0 0 15 15" }, svg("path", { d: SIGNS[kind] })));
    const found = (item) =>
      item
        ? [
            h("span", { class: "fact", title: item.status }, mark(item.judgedMark), item.judgedLabel),
            item.answer ? h("span", { class: "fact" }, mark(item.answerMark), item.label) : null,
          ]
        : [];
    return [
      // Development runs stand under a heading of their own, apart from the experiments: a catalogue entry says `development`.
      ...(() => {
        const row = (item) =>
          h(
            "button",
            { class: "exp-row", type: "button", "aria-pressed": String(item.active), "aria-label": `${item.label}. ${item.outcome?.spoken || ""}`, onclick: () => pick(item.first) },
            h("span", { class: "exp-name" }, item.label),
            h("span", { class: "exp-found" }, found(item.outcome))
          );
        const judged = experiments.filter((item) => !item.development), development = experiments.filter((item) => item.development);
        const group = (list, label) => [h("p", { class: "eyebrow" }, label), h("div", { class: "experiments", role: "group", "aria-label": label }, list.map(row))];
        // Many: a list to choose from, with a development run named as one.
        if (experiments.length > 6) return [h("p", { class: "eyebrow" }, "Experiments"), chooser("cells-experiment", "Experiment", experiments.map((item) => [item.first, `${item.development ? "Development run: " : ""}${item.label}${item.outcome ? ` · ${item.outcome.spoken}` : ""}`]), experiments.find((item) => item.active)?.first)];
        // One: its name. Several: a row each, with what the record says it found.
        if (experiments.length <= 1) return [h("p", { class: "eyebrow" }, development.length ? "Development run" : "Experiment"), h("p", { class: "card-title" }, heading)];
        return [...(judged.length ? group(judged, judged.length > 1 ? "Experiments" : "Experiment") : []), ...(development.length ? group(development, development.length > 1 ? "Development runs" : "Development run") : [])];
      })(),
      // The first sentence says what the experiment asks; the rest is a click away.
      ...(() => {
        const parts = /^(.*?[.?!])\s+(.+)$/s.exec(text || "");
        if (!parts) return [h("p", { class: "card-text run-plain" }, text)];
        return [h("p", { class: "card-text run-lead" }, parts[1]), h("details", { class: "run-plain" }, h("summary", {}, "How it is done"), h("p", { class: "card-text" }, parts[2]))];
      })(),
      // What the experiment found: whether it was judged, and what the answer was, in the record's words.
      outcome
        ? h(
            "div",
            { class: "found" },
            h("span", { class: "seg-label" }, "What it found"),
            h("p", { class: "found-facts" }, found(outcome)),
            h("details", { class: "run-plain" }, h("summary", {}, outcome.status || "In the record's words"), h("p", { class: "card-text" }, outcome.text))
          )
        : null,
      h(
        "div",
        { class: "runs", role: "group", "aria-label": "Runs" },
        h("span", { class: "seg-label" }, runs.length === 1 ? "Run" : `Runs · ${runs.length}`),
        // A few runs are rows to press; many are a list to choose from.
        runs.length > 8
          ? chooser("cells-run", "Run", runs.map((run) => [run.id, [[run.title, run.sub].filter(Boolean).join(", "), run.klass ? run.klass.toLowerCase() : "", run.early ? "stopped early" : ""].filter(Boolean).join(" · ")]), runs.find((run) => run.active)?.id)
          : runs.map((run) =>
              h(
                "button",
                { class: "run-row", type: "button", "aria-pressed": String(run.active), title: [run.title, run.sub].filter(Boolean).join(", "), onclick: () => pick(run.id) },
                h("span", { class: "run-name" }, run.title),
                h("span", { class: "run-sub" }, [run.sub, run.klass ? `recorded as ${run.klass.toLowerCase()}` : "", run.early ? "stopped early" : ""].filter(Boolean).join(" · "))
              )
            )
      ),
      klass
        ? h(
            "div",
            { class: "run-class" },
            h("p", { class: "run-class-line" }, h("span", { class: "seg-label" }, "Recorded class"), h("span", { class: "chip chip-strong", title: klass.description }, klass.label)),
            // The rule and where the class comes from open on request, so the card stays short.
            h("details", { class: "run-class-note" }, h("summary", {}, "What this class means"), h("p", { class: "card-text" }, [klass.description, klass.note].filter(Boolean).join(" ")))
          )
        : null,
      // How this run ended, in the experiment's plain words, and any refusal the run records.
      ended?.label ? h("p", { class: "card-text run-ended" }, mark(ended.refusal ? "no" : ended.early ? "mixed" : "yes"), ended.label, ended.refusal ? ` Refused: ${ended.refusal}` : "") : null,
      colour ? this.segmented("Colour", colour.options.map(([value, label]) => [value, label.replace(/^Membrane /, "").replace(/^./, (letter) => letter.toUpperCase())]), colour.active, (value) => lens.setRecord(value)) : null,
      h("div", { class: "run-actions" }, h("button", { class: "pill-button pill-small", type: "button", onclick: () => this.select(details) }, "Run details")),
    ].filter(Boolean);
  }

  /** The view's card sits above the legend; it takes the room the legend leaves and scrolls beyond that. */
  fitCard() {
    const card = this.viewCard;
    if (card.hidden || this.clientWidth < 760) {
      card.style.maxHeight = "";
      return;
    }
    const legend = this.legend.hidden ? 0 : this.legend.offsetHeight + 16;
    card.style.maxHeight = `${Math.max(150, this.clientHeight - card.offsetTop - legend - 12)}px`;
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
    return [this.legend, this.viewCard, this.rail, this.panel, this.index, this.timeline]
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
    const chrome = this.current?.chrome?.() || {};
    const base = { isolate: this.state.isolate, open: this.state.legendOpen };
    // Without the 3D stage a replay draws nothing, so it has nothing to explain.
    this.legend.hidden = this.state.lens === "experiments" && !chrome.legend;
    if (this.legend.hidden) return;
    const atlas = this.model.raw.proteins;
    if (chrome.legend || (this.state.lens === "proteins" && atlas)) {
      // The protein atlas: how sure each mapping is, in the inventory's own words.
      const legend = chrome.legend || { title: "Mapping", items: atlas.mappings.map((item) => ({ ...item, swatch: `map-${item.id}` })) };
      // A species' findings add a block. On all but a tall window the evidence block then starts closed, so the card keeps its room.
      const filter = chrome.findings && chrome.filter && this.clientHeight < 1040 ? { ...chrome.filter, folded: true } : chrome.filter;
      // A view may ask for its marks to fold away (a replay whose layers add signs of their own).
      this.legend.render({ ...base, ...legend, filter, findings: chrome.findings, folded: legend.folded || this.clientHeight < 880 });
      return;
    }
    const counts = new Map();
    for (const entity of this.shownEntities()) if (entity.status) counts.set(entity.status, (counts.get(entity.status) || 0) + 1);
    const items = this.model.raw.statuses.map((status) => ({ id: status.id, label: status.label, description: status.description, count: counts.get(status.id) || 0, swatch: status.id }));
    // Which parts run together in one model today: the answer to "is this one whole cell yet?"
    const filter = chrome.together?.length ? { title: "Runs together in", items: chrome.together, active: chrome.togetherActive } : null;
    let note = null;
    if (this.state.lens === "cell") {
      const text =
        chrome.view?.colour === "status"
          ? "Colour and form show status. Clear glass shapes and grey lines are scenery."
          : "Colour shows the kind of part. The dot beside each name is its status; planned parts are grey sketches. Clear glass shapes and grey outlines are scenery.";
      note = { swatch: "illustration", text };
    }
    this.legend.render({ ...base, title: "Status", items, filter, note });
  }

  renderIndex() {
    if (this.state.indexOpen) this.index.render({ sections: this.sections(), selected: this.state.selected });
  }

  renderPanel() {
    this.panel.show({ model: this.model, entity: this.lookup(this.state.selected) });
    for (const button of this.shadowRoot.querySelectorAll(".species-state")) button.setAttribute("aria-pressed", String(this.state.selected?.startsWith("species:") || false));
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
      else if (event.key === " " && this.current?.player?.run) {
        // In a replay, the space bar plays and pauses.
        this.current.player.toggle();
        event.preventDefault();
      }
    });
    this.shadowRoot.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        if (this.state.selected) this.select(null);
        else if (this.current?.back?.()) return;
        else if (this.state.indexOpen) this.toggleIndex(false);
      }
    });
  }
}

customElements.define("cells-viewer", CellsViewer);
