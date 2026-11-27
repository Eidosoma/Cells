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
import { loadBeside } from "../lenses/protein_shelves.js";
import { ReplayLens } from "../lenses/replay.js";
import { canonicalAddress } from "../lenses/laws_data.js";
import { makeLawsView } from "../lenses/laws_star.js";
import { doorsFor as lawsDoors, textSections as lawsSections, textDescribe as lawsDescribe } from "../lenses/laws_card.js";
import { LAWS_CSS } from "../lenses/laws_styles.js";
import { MachinesLens } from "../lenses/machines.js";
import { doorsFor as machinesDoors, textSections as machinesSections, textDescribe as machinesDescribe, present as machinesPresent, owns as machinesOwn } from "../lenses/machines_card.js";
import { MACHINES_CSS } from "../lenses/machines_styles.js";
import { Catalogue } from "../replay/catalogue.js";
import { chartOf, tableOf, armWords, unitSign } from "../replay/sweep.js";
import { renderAtlasNav } from "./atlas_nav.js";
import { modelSystemOf, modelSystems, switchRows, switchSections } from "../scene/entries.js";
import { speciesAt, stageFromAddress, writeStage } from "../scene/life_stages.js";
import { makeEntryLens, entryTab } from "./entry_views.js";
import { makeTissueLens } from "../lenses/tissue_line.js";
import { isPart, partDoors, openingPart } from "./tissue_part.js";
import { LandingLens, LANDING_CSS } from "./landing.js";
import { CARD } from "../replay/landing.js";
import "./model_views.js"; // the views of model systems, each registered beside itself
import { busyReasons } from "../core/busy.js";
import { readHost } from "../core/host.js";
import { AboutPart, ABOUT_CSS } from "./about.js";

// The views, in the order of the switch. "label" is a tab's title, "short" its title on a narrow screen: each is
// stated here and nowhere else (the checks and tests read them from this list). A view keeps its own name in prose
// (the Cell view, the Protein atlas, the Laws library); only its tab is titled here. The titles and their order were
// decided on 17 November 2026.
// "needs" says what the scene must hold for the view to be offered.
// From this width up the species switch stands in the bar; below it, in the view's card.
const SPECIES_IN_BAR = 1000;

const LENSES = [
  { id: "cell", label: "Scope", short: "Scope", make: (stage, model, labels) => new CellLens(stage, model, labels) },
  // The Machines catalogue (schema/MACHINE_CATALOGUE.md), by species. "present": how it shows a part of another view's that it holds too (a unit with laws).
  { id: "machines", label: "Machines", short: "Machines", needs: (scene) => scene.catalogue?.entries?.length || Object.keys(scene.catalogue?.benches || {}).length, owns: machinesOwn, doorsFor: machinesDoors, textSections: machinesSections, textDescribe: machinesDescribe, present: machinesPresent, styles: MACHINES_CSS, make: (stage, model, labels) => new MachinesLens(stage, model, labels) },
  { id: "proteins", label: "Proteins", short: "Proteins", needs: (scene) => scene.proteins, make: (stage, model, labels) => new ProteinLens(stage, model, labels) },
  { id: "engine", label: "Engine", short: "Engine", make: (stage, model, labels) => new StackLens(stage, model, labels) },
  // The Laws library (schema/LAWS_LIBRARY.md). "owns": the ids it makes itself, so that an address or a link from
  // another view opens it; "doorsFor": the doors it offers on other views' parts; "textSections" and "textDescribe":
  // its list and panel where no 3D can be drawn; "styles": its legend's swatches.
  { id: "laws", label: "Laws", short: "Laws", needs: (scene) => scene.laws?.pieces?.length, owns: (id) => id.startsWith("laws:"), doorsFor: lawsDoors, textSections: lawsSections, textDescribe: lawsDescribe, styles: LAWS_CSS, make: makeLawsView },
  // "hidden": a page exported without the Experiments view keeps its replays, since the cell view's flux reads a species' looping run from them.
  // It opens on its landing, a page of cards (src/ui/landing.js), whose styles it brings.
  { id: "experiments", label: "Experiments", short: "Runs", needs: (scene) => scene.replays?.runs?.length && !scene.replays.hidden, styles: LANDING_CSS, make: (stage, model, labels) => new ReplayLens(stage, model, labels) },
];

class CellsViewer extends HTMLElement {
  static get observedAttributes() {
    return ["lens"];
  }

  connectedCallback() {
    if (this.connection) return;
    this.connection = new AbortController();
    const { signal } = this.connection;
    // "species" is the one species the page shows: the levels and the cell of the cell view and the
    // species' side of the protein atlas follow it. It stays while the page is open. "atlas" is
    // the same choice under its earlier name.
    // "stage" is the life stage the Scope view shows the species at, where its file gives stages (schema/SPECIES_STAGES.md).
    this.state = { lens: null, selected: null, isolate: null, legendOpen: false, indexOpen: false, railOpen: false, viewOpen: false, species: null, atlas: null, example: null, part: null, landing: false, stage: null };
    this.lenses = new Map();
    this.navigation = 0;
    // What the page's host allows (src/core/host.js): the site's releases say so in a block of their own; without one, as on the artifact.
    this.host = readHost(this.ownerDocument);
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    this.buildChrome();
    this.loadScene(signal).then(
      (scene) => { if (!signal.aborted) this.start(scene); },
      (error) => { if (!signal.aborted) this.fail(`The map's data could not be read (${error.message}).`); }
    );
  }

  disconnectedCallback() {
    if (!this.connection) return;
    this.connection.abort();
    this.closeSpecies({ focus: false });
    this.about.closeLine({ keep: false });
    this.current?.deactivate();
    this.current = null;
    for (const lens of this.lenses.values()) lens.dispose?.();
    this.lenses.clear();
    this.landingView?.dispose();
    this.stage?.dispose();
    this.stage = this.model = this.labels = this.landingView = null;
    this.panelEvidence = null;
    this.atlasNav = this.speciesList = this.speciesVeil = this.speciesMenu = null;
    this.scaleKey = this.widthSeen = this.centredWidth = this.narrowSeen = undefined;
    this.openedCard = this.sweepPicked = this.pressedLabel = null;
    this.shadowRoot.replaceChildren();
    this.connection = null;
  }

  attributeChangedCallback(name, _old, value) {
    if (name === "lens" && this.model && value && value !== this.state.lens) this.setLens(value);
  }

  // ------------------------------------------------------------ loading

  async loadScene(signal) {
    if (this.scene) return this.scene;
    const inline = this.querySelector('script[type="application/json"]');
    if (inline) return JSON.parse(inline.textContent);
    const src = this.getAttribute("src");
    if (src) {
      const response = await fetch(src, { signal });
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
    this.switchBox.addEventListener("scroll", () => this.fadeTabs(), { passive: true });
    this.speciesBox = h("div", { class: "species", hidden: true });
    this.stamp = h("span", { class: "stamp" });
    this.indexButton = h("button", { class: "pill-button", type: "button", "aria-pressed": "false", onclick: () => this.toggleIndex() }, "List");
    // About (src/ui/about.js): its button after List, the name in the bar's corner as a second way to it, and the line under the bar.
    this.about = new AboutPart(this);
    this.legend = h("cells-legend", { class: "card" });
    this.panel = h("cells-panel", { class: "card", hidden: true });
    this.index = h("cells-index", { class: "card", hidden: true });
    this.caveat = h("p", { class: "caveat", hidden: true });
    this.rail = h("nav", { class: "rail card", id: "cells-rail", hidden: true, "aria-label": "Scale" });
    // On a phone the rail folds behind this button, which names the level shown (styles.js); a wide window does not show it.
    this.railToggle = h("button", { class: "rail-toggle card", type: "button", hidden: true, "aria-expanded": "false", "aria-controls": "cells-rail", onclick: () => this.toggleRail() });
    this.viewCard = h("div", { class: "view card", id: "cells-view", hidden: true });
    // In every view the Experiments tab opens from its landing (a run, a part, a model system's view), one control in one
    // place, under the bar at the left, leads back to all experiments; the view's card stands under it (styles.js .has-back).
    this.backButton = h("button", { class: "exp-back pill-button", type: "button", hidden: true, "aria-label": "All experiments", onclick: () => this.state.lens === "experiments" ? this.showLanding() : this.current?.back?.() }, h("span", { class: "exp-back-chevron", "aria-hidden": "true" }), h("span", {}, "All experiments"));
    // A sweep's chart, where the experiment shown has one: a card of its own at the right of a wide window (on a phone it stands in the experiment's card).
    this.sweepCard = h("section", { class: "sweep-card card", hidden: true, "aria-label": "Sweep" });
    // On a phone with a panel open the view's card folds behind this button under the bar, so that the picture keeps
    // its room above the panel; a press opens the card over the picture (styles.js). Elsewhere it is not shown.
    this.viewToggle = h("button", { class: "view-toggle card", type: "button", hidden: true, "aria-expanded": "false", "aria-controls": "cells-view", onclick: () => this.toggleViewCard() });
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
      // The first-visit line under the view's names (src/ui/about.js): it yields to them, and every card stands over it.
      h("div", { class: "stage" }, this.canvas, this.about.line, this.labelBox),
      (this.bar = h("header", { class: "bar" }, h("div", { class: "brand" }, this.about.brand), this.switchBox, this.speciesBox, h("div", { class: "bar-end" }, this.stamp, this.indexButton, this.about.button))),
      this.hint,
      this.caveat,
      this.timeline,
      this.railToggle,
      this.rail,
      this.viewToggle,
      this.viewCard,
      this.backButton,
      this.sweepCard,
      this.scaleBar,
      this.legend,
      this.index,
      this.panel,
      this.fallback
    );
    root.append(h("style", {}, css + ABOUT_CSS + LENSES.map((lens) => lens.styles || "").join("")), this.frame);
    const listen = (name, handler) => root.addEventListener(name, handler, { signal: this.connection.signal });
    listen("cells-select", (event) => this.select(event.detail.id, event.detail));
    listen("cells-isolate", (event) => this.setIsolate(event.detail));
    listen("cells-together", (event) => this.current?.setTogether?.(event.detail));
    listen("cells-finding", (event) => this.current?.setFinding?.(event.detail));
    listen("cells-door", (event) => this.openDoor(event.detail));
    // A species' bench of the Machines catalogue read from beside the page: the list, the panel and the card read it again.
    globalThis.addEventListener?.("cells-bench", () => {
      if (!this.model) return;
      this.renderIndex();
      this.renderPanel();
      this.renderChrome();
    }, { signal: this.connection.signal });
    // The protein atlas: what colour carries on a species' own proteins (its legend's "Colour").
    listen("cells-own-colour", (event) => this.current?.setOwnColour?.(event.detail));
    // Quantity layers of a replay: which layer holds a channel, and how strongly the marks are drawn.
    listen("cells-layer", (event) => this.current?.setLayer?.(event.detail.id, event.detail.on));
    listen("cells-strength", (event) => this.current?.setStrength?.(event.detail));
    listen("cells-slow", (event) => this.current?.setSlow?.(event.detail));
    listen("cells-legend-toggle", () => {
      this.state.legendOpen = !this.state.legendOpen;
      // On a phone the legend's sheet and a view's card never lie over each other: opening the one folds the other.
      if (this.state.legendOpen && this.clientWidth < 760 && this.state.viewOpen) this.toggleViewCard(false);
      this.renderLegend();
      this.cardsMoved();
    });
  }

  start(scene) {
    const { signal } = this.connection;
    const observe = (target, handler) => {
      const observer = new ResizeObserver(handler);
      observer.observe(target);
      signal.addEventListener("abort", () => observer.disconnect(), { once: true });
    };
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
          { type: "button", dataset: { lens: lens.id }, "aria-pressed": "false", "aria-label": lens.label, onclick: () => (lens.id === "experiments" && this.state.lens === "experiments" && !this.state.landing ? this.showLanding() : this.setLens(lens.id, true)) },
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
      this.stage.onTick((dt, time, real) => this.current?.update(dt, time, real) || false);
      this.stage.onPalette((palette) => {
        for (const lens of this.lenses.values()) lens.applyPalette(palette);
        this.landingView?.applyPalette(palette); // its stills, for the theme
      });
      this.listen();
      // The species switch moves between the bar and the card as the window crosses a width.
      observe(this, () => {
        if (this.clientWidth !== this.widthSeen) {
          this.widthSeen = this.clientWidth;
          // A fold of a narrow window (the rail's, the card's) ends when the window is no longer narrow.
          if (this.clientWidth >= 760 && (this.state.railOpen || this.state.viewOpen)) {
            this.toggleRail(false);
            this.toggleViewCard(false);
          }
          this.renderChrome(); // the switch may fit the bar again, or no longer
          // The picture's room at the sides is a wide window's (renderPanel sets it): crossing into or out of a narrow
          // window, it is set again, so a narrow window keeps no room the wide one left for the cards.
          const narrow = this.clientWidth < 760;
          if (this.narrowSeen !== undefined && this.narrowSeen !== narrow) this.renderPanel();
          this.narrowSeen = narrow;
        } else this.fitCard();
      });
      // On a phone the panel is a sheet along the bottom: what stands on its top edge follows its height.
      observe(this.panel, () => this.placeSheet());
      // And the rail's button stands under the bar, however many rows the bar takes (a longer first tab may wrap it).
      document.fonts?.ready.then(() => {
        if (signal.aborted) return;
        this.labels.measure();
        this.renderChrome(); // words are as wide as they will be only now: the species switch may fit the bar, or no longer
        this.stage.invalidate();
      });
    } else {
      this.fallback.hidden = false;
      this.fallback.textContent = "3D drawing is not available in this browser. The list below gives the same content as text.";
      this.hint.hidden = true;
      this.state.indexOpen = true;
      // The Experiments tab's landing stands under the bar with no 3D stage too.
    }
    observe(this.bar, () => this.style.setProperty("--bar-height", `${this.bar.offsetHeight}px`));
    const query = new URLSearchParams(location.search);
    // "still" turns transitions off, so a screenshot shows the settled state.
    if (query.get("still")) {
      this.frame.classList.add("is-still");
      if (this.stage) this.stage.rig.instant = true;
    }
    // An entry of the switch (schema/ENTRIES.md): `entry=`, or `species=` and `atlas=` as before; `cell=` a cell type of the species shown.
    const entered = query.get("entry") || query.get("species") || query.get("atlas") || (query.get("cell") ? this.state.species : null);
    if (entered) this.setEntry(query.get("cell") && !entered.includes(".") && this.speciesChoices().includes(entered) ? `${entered}.${query.get("cell")}` : entered);
    // A life stage of the species (`stage=`, schema/SPECIES_STAGES.md), shown when the Scope view is.
    this.state.stage = query.get("stage") || null;
    // The resting look (core/look.js): "look=plain" is the look as it was, "look=full" holds every
    // effect on; "fps=1" shows the frame rate with a switch for each effect, for judging on a device.
    if (this.stage && query.get("look")) this.stage.look.choose(query.get("look"));
    if (this.stage && query.get("fps")) this.stage.look.trial = true;
    // "frames=1": a small readout at the foot of the picture of the frames the device really draws (core/stage.js).
    if (this.stage && query.get("frames")) this.stage.showFrames(this.frame);
    const wanted = this.addressLens() || this.getAttribute("lens") || this.views[0].id;
    // A model system's view in the Experiments tab's place, from its list (`example=gard`; showExample).
    if (this.replays.doors.some((door) => door.entry === query.get("example"))) this.state.example = query.get("example");
    else if (isPart(this.model.raw.replays, query.get("part"))) this.state.part = query.get("part"); // a part of an example (showPart)
    // The Experiments tab opens on its landing, a page of cards (decided on 18 November 2026), unless the address names
    // something of a view of its own: a run, a record, layers or their strength (the runs' view); a time, play, or a cell of
    // the tumour tissue (its part, as before); or, in this tab, anything else to choose than a card's detail (`card:`).
    else {
      const own = ["run", "record", "layers", "strength"].some((key) => query.get(key)), select = query.get("select") || "";
      const named = wanted === "experiments" && ((select && !select.startsWith(CARD)) || query.get("time") || query.get("play"));
      if (!own && !named) this.state.landing = true;
      else if (!own && !(wanted === "experiments" && select && !select.startsWith("tissue:"))) this.state.part = openingPart(this.model.raw.replays);
    }
    this.setLens(this.views.some((lens) => lens.id === wanted) ? wanted : this.views[0].id);
    if (wanted === "laws") this.current?.restore?.(query);
    // A stage named and not drawn cannot be entered: its card opens, over the species at the stage it opens on.
    const named = query.get("stage") && this.lenses.get("cell") ? stageFromAddress(query.get("stage"), this.lenses.get("cell").file).open : null;
    if (named && this.state.lens === "cell") this.select(`stage:${this.lenses.get("cell").file.id}.${named}`);
    if (query.get("size")) this.current?.setSizeMode?.(query.get("size"));
    // The protein atlas: the units of Cells' law inventory ("units") or the species' own proteins ("own").
    if (query.get("show") && !(wanted === "laws" && this.current?.restore)) this.current?.setMode?.(query.get("show"), { user: true });
    if (query.get("colour")) this.current?.setColourBy?.(query.get("colour"));
    if (query.get("scale")) this.current?.goToScale?.(query.get("scale"), true);
    if (query.get("isolate")) this.setIsolate(query.get("isolate"));
    if (query.get("together")) this.current?.setTogether?.(query.get("together"));
    if (query.get("finding")) this.current?.setFinding?.(query.get("finding"));
    // A replay: which run, where the playhead stands, which record colours the sheet.
    if (query.get("time")) this.current?.seek?.(Number(query.get("time")));
    const navigation = this.navigation;
    const stillOpening = () => !signal.aborted && this.navigation === navigation;
    const settle = () => {
      if (!stillOpening()) return;
      if (query.get("record")) this.current?.setRecord?.(query.get("record"));
      // Quantity layers: "layers=junction-drops,-voltage-relief" switches the first on and the second off; "strength=bold".
      if (query.get("strength")) this.current?.setStrength?.(query.get("strength"));
      if (query.get("layers")) this.current?.setLayers?.(query.get("layers"));
      const choose = () => {
        const selection = query.get("select");
        const conflictingLens = query.get("lens") && query.get("lens") !== wanted;
        if (selection && (!conflictingLens || this.shows(selection))) {
          this.select(query.get("select"), { fly: true });
          // A part the address names is chosen as the page opens; what a view shows only at a visitor's own choice (flux in the Cell view) waits for one.
          this.current?.openedWith?.(this.state.selected);
        }
        // A stated camera angle or distance has the last word, also over the flight to a selected part.
        if (this.stage && (query.get("azimuth") || query.get("polar") || query.get("distance"))) {
          const view = {};
          for (const name of ["azimuth", "polar", "distance"]) if (query.get(name)) view[name] = Number(query.get(name));
          this.stage.rig.setView(view);
        }
      };
      // A machine's closer view (schema/MACHINES.md): "machine=<id>", with "detail=1|2|3". It stands until the visitor chooses.
      const machine = query.get("machine") && this.current?.lookCloser ? this.current.lookCloser(query.get("machine"), { address: true, detail: query.get("detail") }) : null;
      if (machine?.then) {
        machine.then((shown) => {
          if (!stillOpening()) return;
          if (shown && !query.get("select")) {
            this.select(`machine:${query.get("machine")}`);
            this.current?.openedWith?.(this.state.selected);
          }
          choose();
        });
      } else choose();
    };
    // A view that loads its data first (a run) is ready a moment later; the others are ready now. The run the address names
    // (`run=`, or a run of the view chosen by `select=run:`) is the one shown and fetched, and not the view's opening run first.
    const chosen = query.get("select")?.startsWith("run:") && this.current?.has?.(query.get("select")) ? query.get("select").slice("run:".length) : null;
    const loading = query.get("run") || chosen ? this.current?.show?.(query.get("run") || chosen) : this.current?.ready;
    if (loading?.then) loading.then(settle).then(() => stillOpening() && query.get("play") && this.current?.player?.play());
    else settle();
    if (query.get("index")) this.toggleIndex(true);
    window.addEventListener("hashchange", () => {
      const name = this.addressLens();
      if (name && name !== this.state.lens) this.setLens(name);
    }, { signal });
    this.about.start();
    this.dispatchEvent(new CustomEvent("cells-ready", { bubbles: true, composed: true }));
  }

  fail(message) {
    this.fallback.hidden = false;
    this.fallback.textContent = message;
    this.hint.hidden = true;
  }

  /** What the page is busy with, in words (src/core/busy.js): none at rest. Read-only, for the check tools' waits. */
  busy() {
    return busyReasons(this);
  }

  // ------------------------------------------------------------ lenses

  setLens(id, fromUser = false, selection = null) {
    const spec = this.views?.find((lens) => lens.id === id);
    if (!spec || !this.model) return;
    this.navigation++;
    const changed = this.state.lens !== id;
    this.current?.deactivate();
    if (this.state.lens !== id && this.state.viewOpen) this.toggleViewCard(false); // a phone's folded card starts folded in the next view
    this.state.lens = id;
    this.state.isolate = null;
    if (id === "experiments" && this.state.landing) {
      // The landing needs no 3D stage: it is made where none can be drawn too.
      this.current = this.landingLens();
      this.current.activate();
      this.current.setSelection(this.current.has(this.state.selected) ? this.state.selected : null);
    } else if (this.stage) {
      // A model system shown in the switch takes the Cell view's place (src/ui/entry_views.js): its card at once, its own view once its runs are read.
      // So does one the Experiments tab's list opens (showExample): the same view, in that tab's place.
      const entry = id === "cell" ? modelSystemOf(this.model.raw, this.state.model) : id === "experiments" && this.state.example ? modelSystemOf(this.model.raw, this.state.example) : null;
      // A part of an example (the gap-junction example's tissue line: showPart) takes the tab's place too, with a view of its own.
      const part = !entry && id === "experiments" && this.state.part ? this.state.part : null;
      const key = entry ? `model:${entry.id}` : part ? `part:${part}` : id;
      if (!this.lenses.has(key)) {
        const made = entry ? makeEntryLens(this.stage, this.model, this.labels, entry, { root: this.shadowRoot, autoplay: !this.frame.classList.contains("is-still"), signal: this.connection.signal }) : null;
        made?.ready?.then((view) => {
          if (!view) return;
          if (this.lenses.get(key) === made.lens) this.swapLens(key, view);
          else view.dispose?.();
        });
        // From a part, its networks: the whole's opening run, not whatever run the runs' view held last (another card's).
        const whole = part ? (this.model.raw.replays?.experiments || []).find((item) => item.id === part)?.part_of : null;
        const lens = made ? made.lens : part ? makeTissueLens(this.stage, this.model, this.labels, part, { root: this.shadowRoot, back: () => this.showExample(null, { run: whole ? this.replays.openingRun(whole) : null }), open: (id) => this.showPart(id) }) : spec.make(this.stage, this.model, this.labels);
        lens.onChrome = () => {
          if (this.current === lens) this.renderChrome();
        };
        if (lens.address && id === "laws") lens.onAddress = () => {
          if (this.current === lens) this.writeAddress({ laws: lens.address(), select: lens.selected });
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
        // A view that showed something the visitor asked for by a control of its own (a machine's closer view, from the scale rail): its panel opens.
        lens.onShown = (shown) => {
          if (this.current === lens && shown) this.select(shown);
        };
        // The Scope view showed the species at another of its life stages, as the visitor chose on its strip.
        lens.onStage = (stage) => {
          if (this.current === lens) this.stageChosen(stage);
        };
        this.lenses.set(key, lens);
      }
      this.current = this.lenses.get(key);
      this.current.setSpecies?.(this.lensSpecies(id));
      if (this.state.stage) this.current.setStage?.(this.state.stage);
      this.current.setCellType?.(this.state.cellType);
      this.current.setAtlas?.(id === "proteins" ? this.proteinAtlasId() : this.state.species);
      this.current.activate();
      this.current.setIsolate(null);
      this.current.setSelection(this.current.has(this.state.selected) ? this.state.selected : null);
    } else this.current = null;
    if (!this.shows(this.state.selected)) this.state.selected = null;
    for (const button of this.switchBox.children) button.setAttribute("aria-pressed", String(button.dataset.lens === id));
    this.showPressedTab();
    if (fromUser) this.writeAddress({ lens: id, select: changed ? selection : undefined, laws: id === "laws" ? this.current?.address?.() : undefined });
    this.renderChrome();
    this.renderPanel();
    this.stage?.invalidate();
  }

  /** The parts the current lens shows, with or without a stage. */
  shownEntities() {
    if (this.current) return this.current.entities();
    if (this.state.lens === "experiments") return this.replays.entities();
    // A view that makes its own parts gives them as text where no 3D can be drawn (the Laws library).
    const text = this.views.find((view) => view.id === this.state.lens)?.textSections;
    if (text) return text(this.model.raw, this.lensSpecies()).flatMap((section) => section.entities);
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
    let entity = this.model.get(id) || this.current?.describe?.(id) || (this.state.lens === "experiments" ? this.replays.describe(id) : null) || (!this.current ? this.views.find((view) => view.owns?.(id))?.textDescribe?.(this.model.raw, id, this.lensSpecies()) : null) || null;
    // A part of another view's that the view shown holds too (a unit with laws, in the Machines catalogue): as that view shows it.
    const present = this.views.find((view) => view.id === this.state.lens)?.present;
    if (entity && present) entity = present(entity, this.model.raw, this.lensSpecies());
    // A door another view offers on this part (the Laws library on an Engine view box that holds its pieces), after the view's own doors.
    const offered = entity ? this.views.filter((view) => view.id !== this.state.lens && view.doorsFor).flatMap((view) => view.doorsFor(entity, this.model.raw, { species: this.lensSpecies(view.id) })) : [];
    // A part is shown as the chosen species has it: a unit with that species' side of the atlas,
    // a level under the species' name for it.
    const linkedEntry = entity && modelSystems(this.model.raw).find(item => item.view?.engine_part === entity.id);
    if (linkedEntry && this.state.lens === "engine") entity = {...entity, doors:[...(entity.doors || []),
      {label:"Open the 3D organism view",lens:"cell",entry:linkedEntry.id},
      {label:"Open the organism's Protein catalogue",lens:"proteins",entry:linkedEntry.id,show:"own"},
      ...(linkedEntry.view.machine_bench ? [{label:"Open the organism's Machines catalogue",lens:"machines",entry:linkedEntry.id}] : []),
    ]};
    const shown = this.state.lens === "proteins" ? (this.current?.asShown ? this.current.asShown(entity) : inSpecies(entity, this.model.raw.proteins, this.state.species)) : this.state.lens === "cell" && this.current?.inSpecies ? this.current.inSpecies(entity) : entity;
    return shown && offered.length ? { ...shown, doors: [...(shown.doors || []), ...offered] } : shown;
  }

  sections() {
    if (this.current) return this.current.sections();
    if (this.state.lens === "experiments") return this.replays.sections();
    const text = this.views.find((view) => view.id === this.state.lens)?.textSections;
    if (text) return text(this.model.raw, this.lensSpecies());
    const groups = new Map();
    for (const part of this.shownEntities()) {
      const entity = this.state.lens === "proteins" ? inSpecies(part, this.model.raw.proteins, this.state.species) : part;
      const key = entity.eyebrow || (entity.group === "biology" ? entity.scale || entity.kind : entity.group);
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(entity);
    }
    return [...groups].map(([key, entities]) => ({ label: this.model.groups.find((group) => group.id === key)?.label || key, entities }));
  }

  /**
   * A door from a part of one view into another view: open that view and show there what the
   * door names. The foot of a flagellum opens the Protein atlas on the species' own proteins
   * ("show": which of the atlas's two drawings) with one set of them picked out (a mark and its value);
   * a structure of the cell opens it on the shelf of its membrane ("shelf"), with no set picked out.
   */
  openDoor({ lens, show, mark, value, shelf, ids, look, machine, select, find, card, entry }) {
    // A replay's card on the Experiments landing, from its detail: the view the card opens (openCard).
    if (card && this.landingView?.byId?.has(card)) {
      const opened = this.landingView.opened(card);
      if (opened) this.openCard(opened, this.landingView.byId.get(card));
      return;
    }
    // A closer view of a machine (Look closer), in the view shown or, from the Machines catalogue, in the Cell view; or back out of it.
    if (look === "closer") {
      if (lens && lens !== this.state.lens && this.views.some((view) => view.id === lens)) {
        this.select(null);
        this.setLens(lens, true);
      }
      const view = this.current;
      Promise.resolve(view?.lookCloser?.(machine)).then((shown) => shown && this.current === view && this.select(`machine:${machine}`));
      return;
    }
    if (look === "back") {
      this.select(null);
      this.current?.back?.();
      return;
    }
    if (!this.views.some((view) => view.id === lens)) return;
    if (entry) this.setEntry(entry, { user:true });
    this.select(null);
    this.setLens(lens, true);
    const view = this.current;
    Promise.resolve(show && view?.setMode ? view.setMode(show, { user: true }) : view?.ready).then(() => {
      if (this.current !== view) return; // another view was chosen meanwhile
      if (mark) view.setMark?.(mark);
      if (value !== undefined) view.setFinding?.(String(value));
      // Of the set picked out, only the proteins the door names (a machine's part: schema/MACHINES.md).
      if (ids?.length) view.pickIds?.(ids);
      if (shelf !== undefined) {
        view.setMark?.(null); // a set picked out before would stand in the way of the shelf
        view.setFinding?.(shelf);
      }
      // A part the door names in the view it opens (the Machines catalogue's door to a unit in the atlas, or to a part of the cell).
      if (select) this.select(select, { fly: true });
      // A protein the door names (a machine's chain, by its accession): the view's own search finds it, and it opens on it.
      if (find && view?.searchOwn && view?.reveal)
        Promise.resolve(view.searchOwn(find)).then((found) => {
          const hit = (found?.proteins || []).find((item) => String(item.id) === String(find));
          if (hit && this.current === view) view.reveal(hit);
        });
      this.renderChrome();
    });
  }

  // ------------------------------------------------------------ state changes

  select(id, { fly = false, waited = false } = {}) {
    id = canonicalAddress(id, this.model.raw.laws?.viewer_ids?.aliases);
    if (id?.startsWith("laws:")) id = this.lenses.get("laws")?.canonical?.(id) || id;
    if (this.state.about) this.about.toggle(false, { from: false }); // a choice closes About, as it closes any panel
    // An id a view makes itself (laws:…), named by an address or a link from another view: that view opens first.
    // The view shown keeps an id it holds itself (a machine's closer view in the Cell view keeps `machine:<id>`).
    const owner = id && !this.current?.has?.(id) && this.views?.find((view) => view.owns?.(id));
    if (owner && owner.id !== this.state.lens) this.setLens(owner.id, true, id);
    // A view still reading what would name it (a species' bench of machines, for a part of one): the choice waits for it, once.
    const view = this.current, waiting = id && !waited ? view?.waitsFor?.(id) : null;
    if (waiting) {
      waiting.then(() => this.current === view && this.select(id, { fly, waited: true }));
      return;
    }
    if (id && !this.lookup(id)) return;
    if (id && !this.shows(id)) {
      if (!this.model.get(id)) return; // a part of a view that is not the one shown
      // The part lives in another view: go there.
      const home = this.model.lensOf(this.model.get(id));
      if (home === this.state.lens || !this.views.some((lens) => lens.id === home)) return;
      this.state.selected = id;
      this.setLens(home, true, id);
      if (!this.shows(id)) this.state.selected = null;
    }
    const held = this.state.selected;
    this.state.selected = id && this.shows(id) ? id : null;
    this.current?.chosen?.(); // a choice made through the page: what a view holds back as the page opens (see openedWith) waits no longer
    this.current?.setSelection(this.state.selected);
    // Letting go of everything also lets go of what a view has open (a family of proteins).
    if (!this.state.selected) this.current?.letGo?.(held);
    if (fly && this.state.selected) this.current?.focus(this.state.selected);
    if (this.state.selected && this.state.indexOpen && this.clientWidth < 760) this.toggleIndex(false);
    this.renderPanel();
    this.renderIndex();
    // On the landing a card's detail has an address of its own (writeAddress).
    if (this.state.lens === "experiments" && this.state.landing && held !== this.state.selected && (held?.startsWith(CARD) || this.state.selected?.startsWith(CARD))) this.writeAddress({ select: this.state.selected?.startsWith(CARD) ? this.state.selected : null });
    this.dispatchEvent(new CustomEvent("cells-selected", { detail: { id: this.state.selected }, bubbles: true, composed: true }));
  }

  setIsolate(status) {
    this.state.isolate = status || null;
    this.current?.setIsolate(this.state.isolate);
    this.renderLegend();
  }

  /** A model system can link to its organism's separately sourced catalogue. */
  proteinAtlasId() {
    const id = modelSystemOf(this.model?.raw, this.state.model)?.view?.protein_atlas;
    return this.model.raw.proteins?.shelves?.some(shelf => shelf.id === id) ? id : this.state.species;
  }

  /** The Machines lens can use a model system's associated organism bench. */
  lensSpecies(lens = this.state.lens) {
    if (lens === "machines") {
      const bench = modelSystemOf(this.model?.raw, this.state.model)?.view?.machine_bench;
      if (this.model.raw.catalogue?.benches?.[bench]) return bench;
    }
    return this.state.species;
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
    this.state.stage = null; // a life stage is a species' own: another species opens on its own
    this.state.species = this.state.atlas = id;
    this.dataset.species = this.dataset.atlas = id;
    for (const [key, lens] of this.lenses) {
      lens.setSpecies?.(this.lensSpecies(key));
      lens.setAtlas?.(key === "proteins" ? this.proteinAtlasId() : id);
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

  /**
   * The Experiments tab shows a model system's own view in its place (`id`, the entry's: GARD's pair, its levels, its clock,
   * its panels), opened from the tab's list, which stands at the head of its card; null shows the tab's runs again, and `run`
   * one of them where the run shown is of another experiment. The species switch, the first tab and the address's `entry=`
   * are the switch's, and stay as they are.
   */
  showExample(id, { run = null } = {}) {
    const example = (id && this.replays.doors.some((item) => item.entry === id) && modelSystemOf(this.model?.raw, id)?.id) || null;
    if (example !== this.state.example || this.state.part || this.state.landing) {
      this.state.example = example;
      this.state.part = null; // a part shown gives the tab back too
      this.state.landing = false;
      if (this.state.lens === "experiments") this.setLens("experiments");
    }
    const lens = this.current, shown = lens?.catalogue?.byId.get(lens.runId);
    if (!example && run && lens?.show && shown?.experiment !== lens.catalogue.byId.get(run)?.experiment) lens.show(run);
  }

  /** A part of an example in the Experiments tab's place (src/lenses/tissue_line.js), opened from the example's card; null gives the tab back. */
  showPart(id) {
    const part = isPart(this.model?.raw?.replays, id) ? id : null;
    if (part === this.state.part && !this.state.example && !this.state.landing) return;
    this.state.example = null;
    this.state.part = part;
    this.state.landing = false;
    if (this.state.selected && !this.current?.has?.(this.state.selected)) this.state.selected = null;
    if (this.state.lens === "experiments") this.setLens("experiments");
  }

  // ------------------------------------------------------------ the Experiments tab's landing (src/ui/landing.js)

  /** The landing, made once: its page of cards stands over the stage, under the bar and the panel. */
  landingLens() {
    if (this.landingView) return this.landingView;
    const raw = this.model.raw;
    const view = new LandingLens({
      replays: raw.replays,
      open: (opened, card) => this.openCard(opened, card),
      choose: (id) => this.select(id),
      openLens: (lens) => {
        this.select(null);
        this.setLens(lens, true);
      },
      sourceUrl: (source) => this.model.sourceUrl(source),
      // A card's part on the Engine map: a door into the view that holds it, where the scene has it.
      door: (part) => {
        const entity = this.model.get(part), lens = entity ? this.model.lensOf(entity) : null;
        const view_ = this.views.find((item) => item.id === lens);
        return view_ ? { lens, select: part, label: lens === "engine" ? "Its part on the Engine map" : `Its part in the ${view_.label} tab` } : null;
      },
      statuses: new Set((raw.statuses || []).map((status) => status.id)),
      lensLabel: (lens) => this.views.find((item) => item.id === lens)?.label || null,
    });
    view.onChrome = () => this.current === view && this.renderChrome();
    view.onPanel = () => this.current === view && (this.renderIndex(), this.renderPanel());
    view.setTheme(this.stage?.palette ? Boolean(this.stage.palette.dark) : getComputedStyle(this).getPropertyValue("--is-dark").trim() === "1");
    this.frame.insertBefore(view.box, this.hint); // after the bar: under it, and after it for the keyboard
    this.landingView = view;
    return view;
  }

  /** A replay's card pressed on the landing: the view that exists for it, as the tab opens it (src/replay/landing.js, opensOf). */
  openCard(opened, card = null) {
    if (!opened) return;
    this.openedCard = card?.id || null;
    this.state.landing = false;
    this.state.example = opened.example || null;
    this.state.part = opened.part || null;
    this.state.selected = null;
    this.setLens("experiments", true);
    if (opened.run) this.current?.show?.(opened.run);
    // The view's own address (run=, part=, example=) is not written: a view may change what it shows by its own controls.
    this.writeAddress({ select: null, views: true });
  }

  /** Back to all experiments (the control under the bar, or the tab pressed again): the landing, where it was left. */
  showLanding() {
    if (this.state.landing && this.state.lens === "experiments") return;
    this.state.landing = true;
    this.state.example = null;
    this.state.part = null;
    this.state.selected = null;
    this.setLens("experiments", true);
    // A run left for the landing lets its drawing go; the runs it keeps (ReplayLens.keep) stay for the way back to it.
    for (const lens of this.lenses.values()) lens.rest?.();
    this.writeAddress({ select: null, views: true });
    // The keyboard comes back to the card it left from, its band open first.
    this.landingView?.returnTo(this.openedCard);
  }

  /** Read both published forms. A recognised tab fragment is the most recent choice on older links that carry both. */
  addressLens() {
    const url = new URL(location.href);
    return [url.hash.slice(1), url.searchParams.get("lens")].find((id) => this.views.some((view) => view.id === id));
  }

  /**
   * The page's own address follows the landing's own state, as it follows the switch's entry (writeEntry): a card's detail
   * is `select=card:<id>`, written as it opens and taken away as it closes or the tab is left; going back to the landing,
   * or opening a view from a card, takes away what an address of a view left in it (run=, part=, example=, time=, …). The
   * tab writes its name as a fragment and retires an earlier lens query. A view opened from a card writes no address of its
   * own (a view changes what it shows by its own controls). In a frame that keeps its address (a published artifact's)
   * nothing is written and nothing breaks; there only the outer link's #name reaches the page, read as a view's id alone.
   */
  writeAddress({ lens, select = undefined, views = false, laws } = {}) {
    try {
      const url = new URL(location.href);
      if (lens) {
        url.searchParams.delete("lens");
        url.hash = lens;
      }
      if (views) for (const key of ["run", "part", "example", "time", "record", "layers", "strength", "play"]) url.searchParams.delete(key);
      if (lens && lens !== "laws") for (const key of ["lawModel", "lawFamily", "lawOrigin", "lawWhere", "lawRelation", "lawTrail", "trace", "compare"]) url.searchParams.delete(key);
      if (laws) {
        if (["declared", "design", "all"].includes(url.searchParams.get("show"))) url.searchParams.delete("show");
        for (const [key, value] of Object.entries(laws)) {
          if (value) url.searchParams.set(key, value);
          else url.searchParams.delete(key);
        }
      }
      if (select === null || (views && !select)) url.searchParams.delete("select");
      else if (select) url.searchParams.set("select", select);
      history.replaceState(null, "", url);
    } catch {
      // A frame that keeps its address: the choice holds while the page is open.
      if (lens && location.hash.slice(1) !== lens) location.hash = lens;
    }
  }

  // ------------------------------------------------------------ the switch's entries (schema/ENTRIES.md)

  /**
   * Show an entry of the switch: a species, as setSpecies does (`<species>.<type>` also chooses
   * a cell type of it), or a model system, which takes the Cell view's place with a view of its
   * own (src/ui/entry_views.js). The other views keep the species last shown.
   */
  setEntry(id, { user = false } = {}) {
    const [speciesId, typeId] = String(id || "").split(".");
    const entry = modelSystemOf(this.model?.raw, id);
    const was = this.state.model;
    if (entry) {
      if (was === entry.id) return;
      this.state.model = entry.id;
      this.dataset.entry = entry.id;
    } else {
      if (!this.speciesChoices().includes(speciesId)) return;
      this.state.model = null;
      delete this.dataset.entry;
      // A species' row shows its default cell type; a type's row ("<species>.<type>") that type.
      this.state.cellType = typeId || null;
      this.setSpecies(speciesId);
      this.lenses.get("cell")?.setCellType?.(this.state.cellType);
    }
    this.lenses.get("proteins")?.setAtlas?.(this.proteinAtlasId());
    const machines = this.lenses.get("machines");
    machines?.setSpecies(this.lensSpecies("machines"));
    if (this.current === machines && machines && !machines.has(this.state.selected)) this.state.selected = null;
    this.nameFirstTab();
    if (this.state.selected?.startsWith("model:") || (entry && this.state.selected?.startsWith("species:"))) this.state.selected = entry ? `model:${entry.id}` : null;
    // Shown in the Cell view's place: the view follows the entry (a phone's folded card starts folded in it, as in the next view).
    if ((entry || was) && this.state.lens === "cell" && this.state.viewOpen) this.toggleViewCard(false);
    if ((entry || was) && this.state.lens === "cell") this.setLens("cell");
    else {
      this.renderChrome();
      this.renderPanel();
    }
    if (user) this.writeEntry();
    this.dispatchEvent(new CustomEvent("cells-entry", { detail: { id: entry ? entry.id : speciesId, kind: entry ? "model system" : "species" }, bubbles: true, composed: true }));
  }

  /** The first tab's name: the Cell view's, or the view of the model system shown. */
  nameFirstTab() {
    const button = this.switchBox?.querySelector('[data-lens="cell"]');
    if (!button) return;
    const entry = modelSystemOf(this.model?.raw, this.state.model);
    const name = entry ? entryTab(entry) : this.views.find((lens) => lens.id === "cell");
    button.querySelector(".long").textContent = name.label;
    button.querySelector(".short").textContent = name.short;
    button.setAttribute("aria-label", name.label);
  }

  /**
   * The address names the entry chosen (`entry=`), a cell type that is not its species' default (`cell=`), and a life
   * stage that is not the one the species opens on (`stage=`, schema/SPECIES_STAGES.md).
   */
  writeEntry() {
    try {
      const url = new URL(location.href);
      for (const key of ["entry", "species", "atlas", "cell"]) url.searchParams.delete(key);
      url.searchParams.set("entry", this.state.model || this.state.species);
      const cell = this.lenses.get("cell");
      if (!this.state.model && cell?.cellType && !cell.cellType.own) url.searchParams.set("cell", cell.cellType.id);
      writeStage(url.searchParams, this.state.model ? null : cell?.file, cell?.stageShown);
      history.replaceState(null, "", url);
    } catch {
      // A page in a frame that keeps its address: the choice holds while the page is open.
    }
  }

  /** The life stage the species is shown at, where it is not its file's own: from the Scope view, or else as the address asks. */
  stageAt() {
    const cell = this.lenses.get("cell");
    if (cell?.file) return cell.species?.stage || null;
    const file = (this.model?.raw.species || []).find((item) => item.id === this.state.species);
    const asked = file ? stageFromAddress(this.state.stage, file).stage : null;
    return asked ? speciesAt(file, asked)?.stage || null : null;
  }

  /** The visitor chose another life stage on the Scope view's strip: the address and the panel follow it. */
  stageChosen(stage) {
    this.state.stage = stage;
    this.writeEntry();
    if (this.state.selected && !this.shows(this.state.selected)) this.state.selected = null;
    this.renderPanel();
    this.dispatchEvent(new CustomEvent("cells-stage", { detail: { species: this.state.species, stage }, bubbles: true, composed: true }));
  }

  /** A model system's own view, once its runs are read, in place of its card; it is given the calls setLens gives a lens. */
  swapLens(key, view) {
    const card = this.lenses.get(key);
    const both = () => this.current === view && (this.renderChrome(), this.renderPanel());
    view.onChrome = () => this.current === view && this.renderChrome();
    view.onPanel = () => this.current === view && this.renderPanel();
    view.onMode = () => this.current === view && ((this.state.isolate = null), this.state.selected && !this.shows(this.state.selected) && (this.state.selected = null), both());
    view.onOpen = both;
    view.onShown = (shown) => this.current === view && shown && this.select(shown);
    this.lenses.set(key, view);
    if (card?.levelChosen) view.goToScale?.(card.level); // a level chosen on the card (or by the address) holds
    if (this.current !== card) return;
    card.deactivate();
    this.current = view;
    view.setSpecies?.(this.state.species);
    view.activate();
    view.setIsolate?.(null);
    view.setSelection?.(view.has?.(this.state.selected) ? this.state.selected : null);
    if (!this.shows(this.state.selected)) this.state.selected = null;
    both();
    this.stage?.invalidate();
  }

  /**
   * What a view's chrome says, with the page's entries: the switch lists the model systems
   * beside the species, under their headings, and names the model system shown; the Protein
   * atlas says that a model system has no proteins of a species.
   */
  withEntries(chrome) {
    const entry = modelSystemOf(this.model?.raw, this.state.model);
    const base = chrome.view?.species || chrome.card?.species || null;
    // The switch goes where a view shows it, and into the model system's own view in the first tab's place; no other view gains it.
    if (!base && !(entry && chrome.card && this.state.lens === "cell")) return chrome;
    const options = [...(base?.options || (this.model.raw.species || []).map((item) => [item.id, item.label, item.organism])), ...modelSystems(this.model.raw).map((item) => [item.id, item.label, item.is])];
    // A species with more than one cell type: the row of the type shown is the switch's, and a type not the species' own gives its own word.
    const type = !entry && base?.cellTypes?.length > 1 ? base.cellTypes.find((item) => item.id === base.cellType) : null;
    const species = entry ? { ...base, options, active: entry.id, organism: entry.is, plain: entry.plain, modelled: entry.modelled, cellTypes: null, model: true } : { ...base, options, row: type ? `${base.active}.${type.id}` : base.active, ...(type && !type.own && type.modelled ? { modelled: type.modelled } : {}) };
    const out = { ...chrome };
    if (chrome.view?.species) out.view = { ...chrome.view, species };
    if (chrome.card) out.card = { ...chrome.card, species };
    if (entry && this.state.lens === "proteins" && this.proteinAtlasId() === this.state.species) out.caveat = [`${entry.label} is a model system, not an organism: it has no proteins of a species. The atlas shows the units of Cells' law inventory, as for ${this.model.raw.species?.find((item) => item.id === this.state.species)?.label || "the species last shown"}.`, chrome.caveat].filter(Boolean).join(" ");
    // At a life stage that is not its file's own, the Protein atlas and the Machines bench say that they are the organism's.
    const at = !entry ? this.stageAt() : null;
    if (at && (this.state.lens === "proteins" || this.state.lens === "machines")) {
      const file = this.model.raw.species?.find((item) => item.id === this.state.species), name = file?.organism || file?.label || "the species";
      const stage = `${at.label}${at.index && at.system ? ` (${at.system.short} ${at.index})` : ""}`;
      out.caveat = [this.state.lens === "proteins" ? `The atlas holds the proteins of ${name} as an organism: which of them are made at the stage ${stage} is not in its data.` : `The catalogue holds the machines of ${name} as an organism: which of them a cell holds at the stage ${stage} is not in its data.`, chrome.caveat].filter(Boolean).join(" ");
    }
    if (entry && this.state.lens === "machines" && this.lensSpecies() === this.state.species) out.caveat = [`The catalogue shows the machine records for ${this.model.raw.species?.find((item) => item.id === this.state.species)?.label || "the species last shown"}.`, chrome.caveat].filter(Boolean).join(" ");
    return out;
  }

  toggleIndex(force) {
    this.state.indexOpen = force ?? !this.state.indexOpen;
    this.index.hidden = !this.state.indexOpen;
    this.frame.classList.toggle("has-index", !this.index.hidden); // on a wide window the landing's cards leave it room
    this.indexButton.setAttribute("aria-pressed", String(this.state.indexOpen));
    this.renderIndex();
    if (this.state.indexOpen) this.index.querySelector("input")?.focus({ preventScroll: true });
  }

  // ------------------------------------------------------------ rendering the interface

  renderChrome() {
    this.renderLegend();
    this.renderIndex();
    const chrome = this.withEntries(this.current?.chrome?.() || {});
    // The protein atlas says which of its two drawings is shown; no other view has such a thing.
    if (this.state.lens === "proteins" && this.current?.mode) this.dataset.show = this.current.mode;
    else delete this.dataset.show;
    // A caveat on the picture, or what a view is doing (loading a run, or why it could not).
    const words = chrome.caveat || chrome.status || "";
    // On a phone the protein atlas's caveat stands at the head of the legend's sheet, not over the picture (renderLegend).
    this.frame.classList.toggle("caveat-in-legend", this.caveatInLegend(chrome));
    this.caveat.hidden = !words;
    this.hint.hidden = Boolean(words) || Boolean(chrome.quiet) || !this.stage;
    // A phone is touched, not pointed at: its hint names the touch's own moves (the camera control takes a pinch).
    this.hint.textContent = this.clientWidth < 760 ? "Drag to turn · pinch to zoom · tap a part" : "Drag to turn · scroll to zoom · click a part";
    this.caveat.textContent = words;
    this.caveat.classList.toggle("is-status", Boolean(chrome.status));
    // A view whose data has its own date says so in place of the map's.
    this.stamp.textContent = chrome.stamp || this.mapStamp;
    // The protein atlas's trail, search and map of the stack (src/ui/atlas_nav.js), while its own proteins are shown.
    renderAtlasNav(this, this.state.lens === "proteins" ? chrome.nav || null : null);
    this.renderSpecies(chrome);
    this.viewCard.hidden = !chrome.view && !chrome.card && !chrome.run;
    // The way back to all experiments, in every view the tab opens from its landing.
    const backLabel = this.state.lens === "experiments" && !this.state.landing ? "All experiments" : chrome.back;
    const back = Boolean(backLabel);
    if (back) { this.backButton.lastElementChild.textContent = backLabel; this.backButton.setAttribute("aria-label", backLabel); }
    this.backButton.hidden = !back;
    this.frame.classList.toggle("has-back", back);
    this.frame.classList.toggle("on-landing", this.state.lens === "experiments" && this.state.landing);
    // The picture lies under the page of cards: the keyboard does not stop on it there.
    const onLanding = this.state.lens === "experiments" && this.state.landing;
    this.canvas.tabIndex = onLanding ? -1 : 0;
    // Where no 3D can be drawn, the page's note on it and the list it opens stand over the views, not over the landing's cards.
    if (!this.stage) {
      this.fallback.hidden = onLanding;
      this.index.hidden = onLanding || !this.state.indexOpen;
      this.frame.classList.toggle("has-index", !this.index.hidden);
    }
    if (back) this.frame.style.setProperty("--back-width", `${Math.ceil(this.backButton.getBoundingClientRect().width)}px`);
    this.viewToggle.hidden = this.viewCard.hidden;
    const switches = chrome.view ? [chrome.view.species && !this.speciesInBar ? "species" : null, "colour", (chrome.view.sizes || ["schematic", "real"]).length > 1 && !chrome.view.machine ? "sizes" : null, chrome.view.machine ? "detail" : null].filter(Boolean) : [];
    // On a phone a view's card folds to one line saying what is shown (styles.js .card-folds): the protein atlas's, the Laws
    // library's, a model system's in the Cell view's place. The Cell view's card and a replay's keep their own phone layouts.
    this.frame.classList.toggle("card-folds", this.clientWidth < 760 && Boolean(chrome.card) && !chrome.run && !chrome.view);
    // A model system's card in the first tab's place (its own view's, or the card that stands in for it): on a phone it shows its choices.
    const example = this.state.lens === "experiments" && Boolean(this.state.example || this.state.part) && Boolean(chrome.card);
    const modelCard = (this.state.lens === "cell" && Boolean(chrome.card?.species?.model)) || example;
    // Its stamp (a long line of the runs it plays) is shortened clear of the card, the whole line in its title (styles.js).
    this.bar.classList.toggle("tab-example", example);
    // A part of an example draws its pictures up to the bar, so its stamp never drops to a second row over them (styles.js).
    this.bar.classList.toggle("tab-part", example && Boolean(this.state.part));
    this.stamp.title = example ? this.stamp.textContent : "";
    this.frame.classList.toggle("model-card", modelCard);
    // A view whose picture reaches the page's top edge (the origin view's water) gives the bar's words a ground to stand on (styles.js).
    this.frame.classList.toggle("bar-ground", Boolean(this.current?.drawsUnderBar));
    // The folded line says what is shown: the card's heading, and the drawing chosen where there is a choice ("Cells' 48 units"; not "All").
    // A model system's line names it alone: its packing is the picture's choice, not what is shown.
    const mode = this.clientWidth < 760 && chrome.card?.modes && !chrome.nav && !modelCard && chrome.card.modes.active !== "all" ? chrome.card.modes.options.find(([value]) => value === chrome.card.modes.active)?.[1] : null;
    const folded = chrome.run ? "Experiment and run" : chrome.view ? switches.join(", ").replace(/, (?=[^,]*$)/, " and ").replace(/^./, (letter) => letter.toUpperCase()) : [chrome.card?.heading, mode].filter(Boolean).join(" · ");
    this.viewToggle.replaceChildren(h("span", {}, folded), h("span", { class: "chevron", "aria-hidden": "true" }));
    this.viewToggle.removeAttribute("aria-label"); // set again by fitFolded where the line had to be shortened
    this.viewCard.classList.toggle("view-card", Boolean(chrome.card || chrome.run));
    this.viewCard.classList.toggle("run-card", Boolean(chrome.run));
    // A view that plays an example says so in its legend (`legend.example`) and on its picture. Opened on a phone its card
    // may cover the mark on the picture, so the card carries the words itself there (styles.js .view-notice; rule 11 of
    // schema/QUANTITY_LAYERS.md, as the Cell view's card does for an illustrated flux).
    const marked = chrome.card && chrome.legend?.example ? [h("p", { class: "layer-example view-notice", role: "status" }, chrome.legend.example)] : [];
    // (The tab's list of experiments stood at the head of this card until 18 November 2026: the landing is the list now.)
    if (chrome.card) this.viewCard.replaceChildren(...marked, ...this.card(chrome.card));
    if (chrome.run) this.viewCard.replaceChildren(...this.runCard(chrome.run));
    // A sweep's chart beside the picture on a wide window, out of the experiment's card, which the legend leaves little room.
    const sweeps = chrome.run?.sweeps || [], wide = this.clientWidth >= 760;
    this.sweepCard.hidden = !(sweeps.length && wide);
    this.frame.classList.toggle("has-sweep", !this.sweepCard.hidden);
    if (!this.sweepCard.hidden) this.sweepCard.replaceChildren(...this.sweepsShown(sweeps, (id) => (this.state.selected?.startsWith("run:") ? this.select(`run:${id}`) : this.current.show(id)), chrome.run.units));
    // A replay brings its playhead.
    this.timeline.hidden = !chrome.timeline;
    this.frame.classList.toggle("has-timeline", Boolean(chrome.timeline));
    this.frame.classList.toggle("has-stages", Boolean(chrome.timeline?.onStop)); // a species' life stages (styles.js)
    if (chrome.timeline) this.timeline.bind(chrome.timeline.player, chrome.timeline);
    else this.timeline.unbind?.();
    if (chrome.view) {
      const view = chrome.view, species = view.species;
      const sizes = view.sizes || ["schematic", "real"];
      const width = view.across >= 1 ? `${Number(view.across.toPrecision(1))} µm` : `${Number((view.across * 1000).toPrecision(1))} nm`;
      // The lens may give the words for the cell shown (a bacterium's: a short line, with a link to the panel that says
      // in full what each mode draws of it); else these.
      const own = view.sizeNote;
      const sized =
        own?.text ||
        (view.size === "real"
          ? `Sizes and numbers nearer a real cell, about ${width} across. Dots stand for what is too small to see; counts are indicative.`
          : "Parts are enlarged and few, so each can be seen.");
      // On a narrow window the species switch stands here, at the head of the card.
      const here = species && !this.speciesInBar;
      this.viewCard.replaceChildren(
        ...[
          // Opened over a panel on a phone the card covers the picture's statement: it carries the notice itself, as the legend does (rule 11).
          chrome.flux?.example ? h("p", { class: "layer-example view-notice", role: "status" }, chrome.flux.example) : null,
          here ? this.speciesRow(species) : null,
          here ? h("p", { class: "species-line" }, this.speciesState(species)) : null,
          this.segmented("Colour", [["biology", "Biology"], ["status", "Status"]], view.colour, (value) => this.current.setColourBy(value)),
          sizes.length > 1 && !view.machine ? this.segmented("Sizes", [["schematic", "Schematic"], ["real", "To scale"]], view.size, (value) => this.current.setSizeMode(value)) : null,
          // In a machine's closer view: how much of it is drawn, and what the picture is.
          view.machine ? this.segmented("Detail", view.machine.detail.options.map(([value, label]) => [value, label]), view.machine.detail.active, (value) => this.current.setDetail(value)) : null,
          h("p", { class: "view-note" }, view.machine ? view.machine.note : [sized, own?.open ? [" ", h("button", { class: "link-button", type: "button", onclick: () => this.select(own.open) }, own.more)] : null]),
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
    this.rail.hidden = this.railToggle.hidden = !chrome.rail;
    this.frame.classList.toggle("rail-beside-panel", Boolean(chrome.rail && chrome.railBesidePanel)); // the rail stays beside an open panel (styles.js)
    if (!chrome.rail) this.toggleRail(false);
    if (chrome.rail) {
      this.rail.replaceChildren(
        h("span", { class: "rail-title" }, chrome.railTitle || "Scale"),
        ...chrome.rail.map((stop) =>
          h(
            "button",
            {
              type: "button",
              dataset: { stop: stop.id },
              "aria-pressed": String(stop.id === chrome.railActive),
              title: stop.title || "",
              onclick: () => {
                this.current.goToScale(stop.id);
                // Folded on a phone, the rail closes once a level is chosen; the focus goes back to its button.
                if (this.state.railOpen) {
                  this.toggleRail(false);
                  this.railToggle.focus({ preventScroll: true });
                }
              },
            },
            stop.label
          )
        ),
        // A species of single cells has no further levels: the rail says so in the species' words.
        ...(chrome.railNote ? [h("p", { class: "rail-note" }, chrome.railNote)] : [])
      );
      const active = chrome.rail.find((stop) => stop.id === chrome.railActive) || chrome.rail[0];
      this.railToggle.replaceChildren(h("span", { class: "seg-label" }, chrome.railTitle || "Scale"), h("span", {}, active?.label || ""), h("span", { class: "chevron", "aria-hidden": "true" }));
      this.railToggle.setAttribute("aria-label", `${chrome.railTitle || "Scale"}: ${active?.label || ""}. Press for the other levels.`);
    }
    // The folded line is fitted once the rail's button beside it has its words.
    this.frame.classList.remove("rail-under");
    if (this.clientWidth < 760) this.fitFolded(chrome.card?.heading || "");
    this.fitCard();
    this.fitBar();
  }

  /**
   * On a phone the bar keeps to one row, whatever the first tab is called (a model system's view)
   * and whichever font has arrived: where it would wrap, it is squeezed in steps (styles.js,
   * data-squeeze): tighter switches, a smaller name, the name put out of sight (still read out),
   * smaller words, and last the tabs' row scrolls sideways inside the bar, its cut edges fading (decided
   * 17 November 2026, for six tabs on a phone). A wide window is never squeezed.
   */
  fitBar() {
    const bar = this.bar, box = this.switchBox, before = bar.dataset.squeeze || "", kept = box.scrollLeft;
    delete bar.dataset.squeeze;
    if (this.clientWidth < 760) {
      const oneRow = () => {
        const rects = [...bar.children].filter((element) => !element.hidden && element.getClientRects().length).map((element) => element.getBoundingClientRect()).filter((rect) => rect.width > 1);
        return rects.every((a) => rects.every((b) => a.top < b.bottom - 1 && b.top < a.bottom - 1));
      };
      const steps = ["1", "1 2", "1 2 3", "1 2 3 4", "1 2 3 4 5"];
      for (let step = 0; step < steps.length && !oneRow(); step++) bar.dataset.squeeze = steps[step];
    }
    // The tab of the view shown is brought into sight when the row first scrolls or the window's width changes;
    // otherwise the row keeps where it was (a visitor's own scroll of it holds when the chrome is drawn again).
    if ((bar.dataset.squeeze || "") !== before || this.centredWidth !== this.clientWidth) this.showPressedTab();
    else {
      box.scrollLeft = kept;
      this.fadeTabs();
    }
  }

  /** Where the tabs' row scrolls (a narrow phone): the tab of the view shown stands in the middle of what is seen, and each cut edge fades. */
  showPressedTab() {
    const box = this.switchBox, button = box?.querySelector('[aria-pressed="true"]');
    if (!box) return;
    if (button && box.scrollWidth > box.clientWidth + 1) {
      const b = button.getBoundingClientRect(), r = box.getBoundingClientRect();
      box.scrollLeft += (b.left + b.right) / 2 - (r.left + r.right) / 2;
    }
    this.centredWidth = this.clientWidth;
    this.fadeTabs();
  }

  fadeTabs() {
    const box = this.switchBox, more = box.scrollWidth - box.clientWidth;
    box.style.setProperty("--fade-l", more > 1 && box.scrollLeft > 1 ? "28px" : "0px");
    box.style.setProperty("--fade-r", more > 1 && box.scrollLeft < more - 1 ? "28px" : "0px");
  }

  /**
   * The folded card's line on a phone never cuts a word: where it does not fit it says the heading alone, then fewer of its
   * words. Beside the rail's button (a model system's levels) it keeps 8 px clear of it; where the heading alone would still
   * meet the button, the button steps under the line (styles.js .rail-under), and the line keeps its words.
   */
  fitFolded(heading) {
    const line = this.viewToggle.firstChild;
    if (!line || this.viewToggle.hidden || !this.viewToggle.getClientRects().length) return;
    const rail = !this.railToggle.hidden && this.railToggle.getClientRects().length ? this.railToggle : null;
    const cut = () => line.scrollWidth > line.clientWidth + 1;
    const meets = () => Boolean(rail) && !this.frame.classList.contains("rail-under") && this.viewToggle.getBoundingClientRect().right > rail.getBoundingClientRect().left - 8;
    if (!cut() && !meets()) return;
    const full = line.textContent;
    if (heading && line.textContent !== heading) line.textContent = heading;
    if (meets()) this.frame.classList.add("rail-under");
    const words = line.textContent.split(" ");
    while (cut() && words.length > 1) {
      words.pop();
      line.textContent = `${words.join(" ")}…`;
    }
    if (line.textContent !== full) this.viewToggle.setAttribute("aria-label", full);
  }

  /** On a phone the protein atlas's caveat (not what a view is doing: loading, or why it could not) stands in the legend's sheet. */
  caveatInLegend(chrome) {
    return this.clientWidth < 760 && this.state.lens === "proteins" && Boolean(chrome.caveat) && !chrome.status && !this.legend.hidden;
  }

  /** Open or close the view's card, folded on a phone while a panel is open. */
  toggleViewCard(force) {
    const open = force ?? !this.state.viewOpen, was = this.state.viewOpen;
    this.state.viewOpen = open;
    if (open && this.state.legendOpen && this.clientWidth < 760) {
      this.state.legendOpen = false;
      this.renderLegend();
    }
    // A phone's folded card and folded rail open under the same band: one opened closes the other.
    if (open && this.state.railOpen && this.clientWidth < 760 && this.frame.classList.contains("card-folds")) this.toggleRail(false);
    this.frame.classList.toggle("view-open", open);
    this.viewToggle.classList.toggle("is-open", open);
    this.viewToggle.setAttribute("aria-expanded", String(open));
    if (open !== Boolean(was)) this.cardsMoved();
  }

  /** Open or close the folded rail of a phone. */
  toggleRail(force) {
    const open = force ?? !this.state.railOpen, was = this.state.railOpen;
    if (open && this.state.viewOpen && this.clientWidth < 760 && this.frame.classList.contains("card-folds")) this.toggleViewCard(false);
    this.state.railOpen = open;
    this.frame.classList.toggle("rail-open", open);
    this.railToggle.classList.toggle("is-open", open);
    this.railToggle.setAttribute("aria-expanded", String(open));
    if (open !== Boolean(was)) this.cardsMoved();
  }

  /**
   * A card over the picture opened or closed (the folded card, the rail, the legend; only when one did): a view that keeps
   * something clear of the cards (the origin view's example mark) places it again, and a frame is drawn for it though nothing moves.
   */
  cardsMoved() {
    this.current?.cardsMoved?.();
    this.stage?.invalidate();
  }

  /**
   * The species switch: one control for the whole page, shown in every view that depends on
   * the species. On a wide window it stands in the bar; on a narrow one, at the head of the
   * view's card. It takes any number of species.
   */
  renderSpecies(chrome) {
    const species = chrome.view?.species || chrome.card?.species || null;
    // The control is drawn afresh: its list, if open, stays with the new button; with no
    // control left to belong to (another view), it closes. A visitor whose focus was on the
    // button keeps it on the new one: the chrome is drawn again whenever a view has something
    // new to say (a run arrives, a scale is reached), and the keyboard must not lose its place.
    const held = Boolean(this.speciesButton) && this.shadowRoot.activeElement === this.speciesButton;
    this.speciesButton = null;
    queueMicrotask(() => {
      if (this.speciesMenu?.open && !this.speciesButton?.isConnected) this.closeSpecies({ focus: false });
      else if (held && this.speciesButton?.isConnected && this.shadowRoot.activeElement !== this.speciesButton) this.speciesButton.focus({ preventScroll: true });
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
    // The switch names what it holds: a species, or the model system shown in the first tab's place.
    this.speciesBox.append(h("span", { class: "species-label" }, species.model ? "Model" : "Species"), this.speciesPicker(species), statement);
    const end = this.indexButton.parentElement;
    const words = [...new Set([...(this.model.raw.species || []), ...(this.model.raw.species || []).flatMap((item) => item.cell_types || []), ...modelSystems(this.model.raw)].map((item) => MODELLED[item.modelled?.state] || item.modelled?.state).filter(Boolean))];
    const holds = () =>
      (words.length ? words : [""]).every((word) => {
        statement.textContent = word;
        statement.hidden = !word;
        return this.bar.scrollWidth <= this.bar.clientWidth + 1 && end.scrollWidth <= end.clientWidth + 1;
      });
    // Before the switch gives up its place, the bar is drawn tighter: with the short names of the
    // views and no date (as on a narrower window).
    let fits = false;
    for (const tight of ["", "2"]) {
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
   * The species switch is a dropdown: one button that names the species in view and opens a
   * list of them. It is a list of the page's own and not the browser's select: each row says
   * three things (the species, its organism, what Cells models of it), the rows stand under
   * headings, and the list keeps the page's look in light and dark, on a phone too. The
   * button is a combobox that owns a listbox: the focus stays on the button while the keys
   * move the list's active row, which is what a screen reader announces.
   */
  speciesPicker(species) {
    const menu = (this.speciesMenu ||= { open: false, active: null, typed: "", typedAt: 0 });
    const sections = switchSections(switchRows(this.model.raw, species.options));
    const rows = sections.flatMap((section) => section.groups.flatMap((group) => group.rows));
    const current = rows.find((row) => row.id === (species.row || species.active)) || rows[0];
    // Every name lies in the button, one over the other, so that its width does not change with the species.
    const names = rows.map((row) => h("span", row.id === current.id ? {} : { "aria-hidden": "true" }, row.label));
    const button = h(
      "button",
      { class: "species-pick", type: "button", role: "combobox", "aria-haspopup": "listbox", "aria-controls": "species-list", "aria-expanded": String(menu.open), "aria-label": `${current.kind === "model system" ? "Model system" : "Species"}: ${current.label}`, dataset: { speciesPick: current.id } },
      h("span", { class: "species-pick-name" }, names),
      h("span", { class: "species-pick-caret", "aria-hidden": "true" })
    );
    button.addEventListener("click", () => (menu.open ? this.closeSpecies() : this.openSpecies()));
    button.addEventListener("keydown", (event) => this.speciesKey(event));
    this.speciesButton = button;
    this.speciesShown = { sections, rows, active: current.id };
    // Redrawn while its list was open (a file arrived, the window changed): the list stays, under the new button.
    if (menu.open) queueMicrotask(() => menu.open && this.speciesButton === button && this.showSpecies({ focus: true }));
    return button;
  }

  /** The list of species, built once and filled each time it is shown. */
  speciesListbox() {
    if (this.speciesList) return this.speciesList;
    const list = (this.speciesList = h("div", { class: "species-list", role: "listbox", id: "species-list", "aria-label": modelSystems(this.model.raw).length ? "Species and model systems" : "Species", hidden: true }));
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
        { class: `species-option${row.id === menu.active ? " is-active" : ""}${row.kind === "cell type" ? " is-type" : ""}${row.kind === "model system" ? " is-model" : ""}`, role: "option", id: `species-option-${row.id}`, "aria-selected": String(row.id === shown.active), "aria-label": [row.label, row.organism, row.word].filter(Boolean).join(", "), dataset: { species: row.id, atlas: row.id } },
        h("span", { class: "species-option-name" }, row.label),
        row.word ? h("span", { class: "species-option-state", dataset: { state: row.state } }, row.word) : null,
        row.organism ? h("span", { class: "species-option-organism" }, row.organism) : null
      );
    const heading = (name, top) => name ? h("div", { class: `species-group-name${top ? " is-top" : ""}`, "aria-hidden": "true" }, name) : null;
    list.replaceChildren(...shown.sections.map((section) => {
      const nested = section.groups.some((group) => group.name !== section.name);
      return h("div", { class: "species-section", role: "presentation", dataset: { entrySection: section.name } },
        nested ? heading(section.name, true) : null,
        section.groups.map((group) => h("div", {
          class: `species-group${nested ? " species-subgroup" : ""}`,
          role: "group",
          "aria-label": group.name !== section.name ? `${section.name}, ${group.name}` : group.name || "Other species",
        }, nested && group.name === section.name ? null : heading(group.name, !nested), group.rows.map(option))));
    }));
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
    this.setEntry(id, { user: true });
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
    return h("div", { class: "seg-row seg-species" }, h("span", { class: "seg-label" }, species.model ? "Model" : "Species"), this.speciesPicker(species));
  }

  /** What Cells models of the species shown, in two or three words; pressing it opens all that is said of the species. */
  speciesState(species) {
    const id = species.model ? `model:${species.active}` : `species:${species.active}`;
    return h(
      "button",
      { class: "species-state", type: "button", dataset: { state: species.modelled.state }, "aria-pressed": String(this.state.selected === id), title: species.modelled.text, onclick: () => (species.model && this.state.lens !== "cell" ? (this.setLens("cell", true), this.select(id)) : this.select(this.state.selected === id ? null : id)) },
      MODELLED[species.modelled.state] || species.modelled.state
    );
  }

  /** A view's own summary: headline numbers, what the data is, and where it came from. */
  card({ heading, species, organism, modes, find, notice, open, stats, text, check, marks, choices, method, extra, extraOpen, sources, notCopied, own }) {
    const outside = (url) => /^https:\/\//.test(url || "");
    const read = (date) => (/^\d{4}-\d{2}-\d{2}$/.test(date) ? formatDate(date) : date);
    const lens = this.current;
    // Pressing a button of the card redraws the card, so the focus is put back on the button's successor.
    const again = (selector) => this.viewCard.querySelector(selector)?.focus({ preventScroll: true });
    const choice = marks
      ? h(
          "label",
          { class: "card-marks" },
          h("span", { class: "seg-label" }, marks.label),
          (() => {
            const select = h("select", { id: "cells-mark", class: "run-select", onchange: () => (lens.setMark(select.value), again("#cells-mark")) }, marks.options.map(([value, label]) => h("option", { value, selected: value === marks.active }, label)));
            return select;
          })()
        )
      : null;
    const opened = open
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
      : null;
    return [
      h("p", { class: "card-title" }, heading),
      // A search of what the view draws (the Laws library). Typing may redraw the card: the new field keeps the focus and the caret.
      find
        ? h("input", {
            id: "cells-find",
            class: "run-select card-find",
            type: "search",
            value: find.value || "",
            placeholder: find.placeholder || find.label,
            "aria-label": find.label,
            oninput: (event) => {
              const { value, selectionStart } = event.target;
              lens.setQuery(value);
              const field = this.viewCard.querySelector("#cells-find");
              if (field && field !== event.target) {
                field.focus({ preventScroll: true });
                field.setSelectionRange(selectionStart, selectionStart);
              }
            },
          })
        : null,
      find ? choice : null,
      find ? opened : null,
      // Which species is shown: the page's one switch, here on a narrow window (on a wide one it stands in the bar).
      species && !this.speciesInBar ? this.speciesRow(species) : null,
      // A model system's card (src/lenses/entry_card.js) gives its word under the switch, as the Cell view's card does a species'.
      species?.model && !this.speciesInBar ? h("p", { class: "species-line" }, this.speciesState(species)) : null,
      organism ? h("p", { class: "card-organism" }, organism) : null,
      // The protein atlas: the units of Cells' law inventory, or the species' own proteins.
      modes
        ? h(
            "div",
            // A view whose detail has more than two levels may ask for them in one row (the Machines catalogue's four).
            { class: modes.oneRow ? "seg seg-wide seg-one-row" : "seg seg-wide", role: "group", "aria-label": modes.label, style: modes.oneRow ? `--seg-count: ${modes.options.length}` : null },
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
      // What stands open (a family of proteins), and the way back (a view with a search has it under the search, above).
      find ? null : opened,
      h("div", { class: "stats" }, stats.map(([value, label]) => h("div", { class: "stat" }, h("b", {}, String(value)), h("span", {}, label)))),
      text ? h("p", { class: "card-text" }, text) : null,
      // What a view adds to its card in its own words (the tissue line's picks), made by the view.
      ...(typeof own === "function" ? own() : []),
      check ? h("p", { class: "card-text" }, check) : null,
      // Which of the proteins' marks the legend's last block lists (a view with a search has it beside the search, above).
      find ? null : choice,
      // A model system's view's other choices (src/ui/entry_views.js, `choices`), each as the marks' choice is.
      ...(choices || []).map((item) => {
        const select = h("select", { class: "run-select", dataset: { choice: item.key }, onchange: () => (item.set(select.value), again(`[data-choice="${item.key}"]`)) }, item.options.map(([value, label]) => h("option", { value, selected: value === item.active }, label)));
        return h("label", { class: "card-marks" }, h("span", { class: "seg-label" }, item.label), select);
      }),
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
  /**
   * A sweep's chart (replay/sweep.js): the parameter along it, each readout a line of points, the
   * arm shown marked, the experiment's own reference drawn as rings in the summary's words. Each
   * arm is a button over its points: a press, or Enter on it, shows that arm's run. The same
   * numbers stand in a table under it. Nothing is computed from them and nothing is said of how
   * they compare.
   */
  sweepChart(sweep, pick) {
    const write = (value) => (Math.abs(value) >= 1e4 || (Math.abs(value) < 1e-3 && value !== 0) ? value.toExponential(2) : String(Number(value.toPrecision(4))));
    const chart = chartOf(sweep, { width: 240, height: 140 });
    const { inner } = chart;
    const unit = (item) => (item.unit && item.unit !== "1" ? ` (${unitSign(item.unit)})` : "");
    const lines = sweep.readouts.map((readout, line) => {
      const points = chart.points.filter((point) => point.line === line).sort((p, q) => p.x - q.x);
      return svg("g", { class: `sweep-line sweep-line-${line % 4}` }, points.length > 1 ? svg("polyline", { points: points.map((point) => `${point.x},${point.y}`).join(" "), fill: "none" }) : null, points.map((point) => svg("circle", { cx: point.x, cy: point.y, r: sweep.arms[point.arm].active ? 4.6 : 3.2, class: sweep.arms[point.arm].active ? "sweep-point is-shown" : "sweep-point" })));
    });
    const rings = chart.references.map((point) => svg("circle", { cx: point.x, cy: point.y, r: 6, class: `sweep-ref sweep-line-${point.line % 4}` }));
    const shownArm = sweep.arms.find((arm) => arm.active);
    const band = shownArm ? svg("rect", { x: chart.x(shownArm.parameter) - 7, y: inner.top, width: 14, height: inner.bottom - inner.top, class: "sweep-shown" }) : null;
    const axes = [
      svg("line", { x1: inner.left, y1: inner.bottom, x2: inner.right, y2: inner.bottom, class: "sweep-axis" }),
      svg("line", { x1: inner.left, y1: inner.top, x2: inner.left, y2: inner.bottom, class: "sweep-axis" }),
      ...chart.yTicks.map((tick) => svg("text", { x: inner.left - 4, y: tick.at + 3, "text-anchor": "end", class: "sweep-tick" }, write(tick.value))),
      ...chart.xTicks.map((tick) => svg("text", { x: tick.at, y: inner.bottom + 12, "text-anchor": "middle", class: "sweep-tick" }, write(tick.value))),
      svg("text", { x: (inner.left + inner.right) / 2, y: inner.bottom + 25, "text-anchor": "middle", class: "sweep-axis-label" }, `${sweep.parameter.label}${unit(sweep.parameter)}${sweep.log ? ", log scale" : ""}`),
    ];
    const picture = svg("svg", { viewBox: `0 0 ${chart.width} ${chart.height}`, class: "sweep-svg", role: "img", "aria-label": `${sweep.label}: ${sweep.readouts.map((readout) => readout.label).join(", ")} against ${sweep.parameter.label}` }, band, ...axes, ...rings, ...lines);
    // A button over each arm's column: the press shows its run; an arm with no packaged run is said so and cannot be pressed.
    const buttons = sweep.arms.map((arm) => {
      const at = chart.x(arm.parameter) / chart.width;
      return h("button", { type: "button", class: "sweep-arm", style: `left: calc(${(at * 100).toFixed(3)}% - 11px); top: ${((inner.top / chart.height) * 100).toFixed(3)}%; height: ${(((inner.bottom - inner.top) / chart.height) * 100).toFixed(3)}%`, "aria-pressed": String(arm.active), "aria-label": armWords(sweep, arm, write), title: armWords(sweep, arm, write), disabled: !arm.run, dataset: { arm: arm.arm }, onclick: () => arm.run && !arm.active && pick(arm.run) });
    });
    const key = h("p", { class: "sweep-key" }, sweep.readouts.map((readout, line) => h("span", { class: "sweep-key-item" }, h("i", { class: `sweep-swatch sweep-line-${line % 4}`, "aria-hidden": "true" }), `${readout.label}${unit(readout)}`)), sweep.reference && chart.references.length ? h("span", { class: "sweep-key-item" }, h("i", { class: "sweep-swatch sweep-ring", "aria-hidden": "true" }), sweep.reference.label) : null);
    const table = tableOf(sweep, write);
    return h(
      "div",
      { class: "sweep", role: "group", "aria-label": sweep.label, dataset: { sweep: sweep.id } },
      h("span", { class: "seg-label" }, sweep.label),
      sweep.plain ? h("p", { class: "card-text" }, sweep.plain) : null,
      h("div", { class: "sweep-chart" }, picture, ...buttons),
      key,
      h("p", { class: "card-text sweep-note" }, `Each point is an arm, as the experiment's summary gives it; the arm shown is marked. Press a point to show that arm.${sweep.reference ? ` Rings: ${sweep.reference.label}, as the summary states it.` : ""}`),
      h(
        "details",
        { class: "run-plain sweep-numbers" },
        h("summary", {}, "The numbers as a table"),
        h("table", { class: "sweep-table" }, h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Arm"), table.head.map((cell) => h("th", { scope: "col" }, cell)))), h("tbody", {}, table.rows.map((row) => h("tr", { class: row.active ? "is-shown" : "" }, h("th", { scope: "row" }, row.arm), row.cells.map((cell) => h("td", {}, cell))))))
      )
    );
  }

  /**
   * An experiment's sweeps: the one that holds the run shown is drawn (or the one the visitor chose, until another run is
   * shown); the others are one press away, a row of their names. With one sweep, its chart alone.
   */
  sweepsShown(sweeps, pick, units = null) {
    if (!sweeps.length) return [];
    const holding = sweeps.find((sweep) => sweep.arms.some((arm) => arm.active)) || sweeps[0];
    const runShown = sweeps.flatMap((sweep) => sweep.arms).find((arm) => arm.active)?.run || null;
    if (this.sweepPicked && this.sweepPicked.run !== runShown) this.sweepPicked = null;
    const shown = sweeps.find((sweep) => sweep.id === this.sweepPicked?.id) || holding;
    // The other sweeps are one press away: a list to choose from, their labels being long.
    const choose = sweeps.length > 1
      ? h("label", { class: "sweep-choose" }, h("span", { class: "seg-label" }, `Sweeps · ${sweeps.length}`), (() => {
          const select = h("select", { class: "run-select", "aria-label": "Sweep", onchange: () => {
            // A sweep chosen shows a run of it: the run shown where it is one of its arms, else its first arm with a run.
            const sweep = sweeps.find((item) => item.id === select.value);
            const arm = sweep?.arms.find((item) => item.active) || sweep?.arms.find((item) => item.run);
            this.sweepPicked = { id: select.value, run: arm?.run || runShown };
            if (arm?.run && !arm.active) pick(arm.run);
            else this.renderChrome();
          } }, sweeps.map((sweep) => h("option", { value: sweep.id, selected: sweep.id === shown.id }, `${sweep.label}${sweep === holding && runShown ? " (the run shown)" : ""}`)));
          return select;
        })())
      : null;
    // Where the experiment's runs state one quantity in other units (two forms of a model), the line that says so stands by the chart.
    return [choose, this.sweepChart(shown, pick), units ? h("p", { class: "card-text run-units" }, units) : null].filter(Boolean);
  }

  runCard({ heading, text, outcome, experiment = null, example = false, development = false, runs, klass, ended, colour, details, sweeps = [], units = null }) {
    const lens = this.current;
    // With a run's details open, the details follow the run picked. From a model system's view or a part in the tab's place, a run is shown here again.
    const pick = (id) => (this.state.example || this.state.part ? this.showExample(null, { run: id }) : this.state.selected?.startsWith("run:") ? this.select(`run:${id}`) : lens.show(id));
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
    // The experiment shown, named as what it is: a development run is no experiment, and a sheet of invented numbers is neither.
    // (The tab's list of every experiment stood here until 18 November 2026: the landing is the list now, a press away under the bar.)
    const listPart = [h("p", { class: "eyebrow" }, example ? "Invented numbers" : development ? "Development run" : "Experiment"), h("p", { class: "card-title" }, heading)];
    return [
      ...listPart,
      // A part of this experiment (the tumour tissue's line), shown in the tab's place by a press (showPart): under its name and
      // above its runs, so that it is in sight with them.
      ...partDoors(this.model?.raw?.replays, experiment, (id) => this.showPart(id), { root: this.shadowRoot }),
      // The runs, at the head under its name, so that they are in sight: a few are rows to press; many are a
      // list to choose from, grouped by the sweep that holds them, in the sweeps' order.
      h(
        "div",
        { class: "runs", role: "group", "aria-label": "Runs" },
        h("span", { class: "seg-label" }, runs.length === 1 ? "Run" : `Runs · ${runs.length}`),
        runs.length > 8
          ? (() => {
              const option = (run) => h("option", { value: run.id, selected: run.active }, [[run.title, run.sub].filter(Boolean).join(", "), run.klass ? run.klass.toLowerCase() : "", run.early ? "stopped early" : ""].filter(Boolean).join(" · "));
              const left = new Map(runs.map((run) => [run.id, run])), groups = [];
              for (const sweep of sweeps) {
                const held = sweep.arms.map((arm) => left.get(arm.run)).filter(Boolean);
                held.forEach((run) => left.delete(run.id));
                if (held.length) groups.push([sweep.label, held]);
              }
              if (left.size) groups.push([groups.length ? "Other runs" : null, [...left.values()]]);
              const select = h("select", { id: "cells-run", class: "run-select", "aria-label": "Run", onchange: () => pick(select.value) }, groups.map(([label, list]) => (label ? h("optgroup", { label }, list.map(option)) : list.map(option))));
              return select;
            })()
          : runs.map((run) =>
              h(
                "button",
                { class: "run-row", type: "button", "aria-pressed": String(run.active), title: [run.title, run.sub].filter(Boolean).join(", "), onclick: () => pick(run.id) },
                h("span", { class: "run-name" }, run.title),
                h("span", { class: "run-sub" }, [run.sub, run.klass ? `recorded as ${run.klass.toLowerCase()}` : "", run.early ? "stopped early" : ""].filter(Boolean).join(" · "))
              )
            )
      ),
      units ? h("p", { class: "card-text run-units" }, units) : null,
      // An experiment whose summary lists arms with a parameter and readouts: its chart first, where the card opens.
      ...(this.clientWidth < 760 ? this.sweepsShown(sweeps, pick) : []),
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
      klass
        ? h(
            "div",
            { class: "run-class" },
            h("p", { class: "run-class-line" }, h("span", { class: "seg-label" }, "Recorded class"), h("span", { class: "chip chip-strong", title: klass.description }, klass.label)),
            // The rule and where the class comes from open on request, so the card stays short.
            h("details", { class: "run-class-note" }, h("summary", {}, "What this class means"), h("p", { class: "card-text" }, [klass.description, klass.note].filter(Boolean).join(" ")))
          )
        : null,
      // How this run ended, in the experiment's plain words, and any refusal the run records. A sheet of invented numbers was not run: its line carries no sign of how a run ended.
      ended?.label ? h("p", { class: "card-text run-ended" }, example ? "" : mark(ended.refusal ? "no" : ended.early ? "mixed" : "yes"), ended.label, ended.refusal ? ` Refused: ${ended.refusal}` : "") : null,
      colour ? this.segmented("Colour", colour.options.map(([value, label]) => [value, label.replace(/^Membrane /, "").replace(/^./, (letter) => letter.toUpperCase())]), colour.active, (value) => lens.setRecord(value)) : null,
      h("div", { class: "run-actions" }, h("button", { class: "pill-button pill-small", type: "button", onclick: () => this.select(details) }, "Run details")),
    ].filter(Boolean);
  }

  /**
   * The view's card sits above the legend; it takes the room the legend leaves and scrolls beyond that.
   * The card keeps a least height, and the legend never lies over it: in a short window, or where the
   * page's own font did not arrive and its words run longer, the legend scrolls within what is left.
   */
  fitCard() {
    const card = this.viewCard;
    // A replay's card keeps its head in view above the legend: the experiment's name, its parts and its run chooser (many runs),
    // so that the runs are in sight.
    const list = card.classList.contains("run-card") ? card.querySelector("#cells-run") : null;
    const least = Math.max(150, list ? list.getBoundingClientRect().bottom - card.getBoundingClientRect().top + card.scrollTop + 14 : 0);
    this.placeFoot();
    if (this.clientWidth < 760) {
      // On a phone the cards keep their own heights (styles.js); the legend opens upward from where it stands, as far as the bar.
      card.style.maxHeight = "";
      this.placeSheet();
      return;
    }
    if (card.hidden) {
      card.style.maxHeight = "";
      this.legend.style.maxHeight = "";
      return;
    }
    this.legend.style.maxHeight = `${Math.max(120, this.clientHeight - card.offsetTop - least - 12 - 16)}px`;
    const legend = this.legend.hidden ? 0 : this.legend.offsetHeight + 16;
    card.style.maxHeight = `${Math.max(least, this.clientHeight - card.offsetTop - legend - 12)}px`;
  }

  /**
   * On a phone the panel is a sheet along the bottom. What stands on its top edge (the legend's
   * title, the look's switch, a replay's timeline) is placed by its height (--sheet, styles.js),
   * so that each can still be pressed with the panel open; and the legend, which opens upward,
   * may reach as far as the bar and scrolls within that.
   */
  placeSheet() {
    const narrow = this.clientWidth < 760, open = narrow && !this.panel.hidden;
    if (open) this.frame.style.setProperty("--sheet", `${this.panel.offsetHeight}px`);
    else this.frame.style.removeProperty("--sheet");
    if (!narrow) return;
    if (this.legend.hidden) {
      this.legend.style.maxHeight = "";
      return;
    }
    const origin = this.getBoundingClientRect().top;
    // As far as the bar, or with a panel open as far as the folded card's button under it, which stands in front.
    const over = [this.bar, open && !this.viewToggle.hidden ? this.viewToggle : null, this.backButton.hidden ? null : this.backButton].filter(Boolean).map((element) => element.getBoundingClientRect()).filter((rect) => rect.height > 0);
    const bottom = this.legend.getBoundingClientRect().bottom - origin, top = Math.max(...over.map((rect) => rect.bottom)) - origin + 8;
    this.legend.style.maxHeight = `${Math.max(56, Math.floor(bottom - top))}px`;
  }

  /** The scale bar's words stand clear of the caveat under the picture: where the two would meet (a panel open beside them, long words), the bar moves up over it. */
  placeFoot() {
    const bar = this.scaleBar;
    bar.style.bottom = "";
    if (bar.hidden || this.caveat.hidden) return;
    const a = bar.getBoundingClientRect(), b = this.caveat.getBoundingClientRect();
    if (!a.width || !a.height || !b.width || !b.height) return;
    if (a.left < b.right && a.right > b.left && a.bottom > b.top - 6 && a.top < b.bottom) bar.style.bottom = `${Math.ceil(this.getBoundingClientRect().bottom - b.top + 8)}px`;
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
    // The bar's switches too (on a narrow window the bar may wrap to a second line), the look's switch over the scale
    // bar (which moves up over the caveat where the two would meet, and on a phone stands on a panel's top edge), and
    // on a phone the folded rail's and view card's buttons.
    const look = this.lookBox.hidden ? null : this.lookBox.querySelector(".look-switch");
    return [this.switchBox, this.speciesBox, this.indexButton.parentElement, this.legend, this.viewCard, this.viewToggle, this.backButton, this.rail, this.railToggle, this.panel, this.index, this.timeline, look, this.atlasNav?.trail, this.atlasNav?.map]
      .filter((element) => element && !element.hidden)
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
    this.placeFoot(); // longer words may now meet the caveat
  }

  renderLegend() {
    const chrome = this.current?.chrome?.() || {};
    const base = { isolate: this.state.isolate, open: this.state.legendOpen };
    // Without the 3D stage a replay draws nothing, so it has nothing to explain.
    this.legend.hidden = (this.state.lens === "experiments" && !chrome.legend) || chrome.legend === false; // false: a view with nothing to explain (a model system's card)
    if (this.legend.hidden) return;
    const atlas = this.model.raw.proteins;
    if (chrome.legend || (this.state.lens === "proteins" && atlas)) {
      // The protein atlas: how sure each mapping is, in the inventory's own words.
      const legend = chrome.legend || { title: "Mapping", items: atlas.mappings.map((item) => ({ ...item, swatch: `map-${item.id}` })) };
      // A species' findings add a block. On all but a tall window the evidence block then starts closed, so the card keeps its room.
      const filter = chrome.findings && chrome.filter && this.clientHeight < 1040 ? { ...chrome.filter, folded: true } : chrome.filter;
      // A view may ask for its marks to fold away (a replay whose layers add signs of their own).
      // On a phone the atlas's caveat is the legend's opening words (renderChrome hides it from over the picture).
      const full = this.withEntries(chrome);
      const lead = this.caveatInLegend(full) ? full.caveat : null;
      this.legend.render({ ...base, ...legend, filter, findings: chrome.findings, folded: legend.folded || this.clientHeight < 880, ...(lead ? { lead } : {}) });
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
          : "Colour shows the kind of part, and every part is drawn whole. The dot beside each name is its status; Colour: Status shows what is not built as grey sketches. Clear glass shapes and grey outlines are scenery.";
      note = { swatch: "illustration", text };
    }
    // On a phone with a panel open the legend has little room above the panel: the Flux switch stands first there.
    this.legend.render({ ...base, title: "Status", items, filter, note, layers: chrome.flux || null, layersFirst: this.clientWidth < 760 && Boolean(this.state.selected) });
  }

  renderIndex() {
    if (this.state.indexOpen) this.index.render({ sections: this.sections(), selected: this.state.selected });
  }

  renderPanel() {
    // About stands in the panel's place over the part chosen (src/ui/about.js): closed, that part's panel is back.
    const open = Boolean(this.state.selected) || Boolean(this.state.about);
    const { lens, selected, species, about } = this.state;
    const model = this.model;
    const evidence = !about && (lens === "proteins" || lens === "machines")
      ? model?.requestUnitEvidence(selected, species, (file) => loadBeside(file, { root: this.ownerDocument }))
      : null;
    if (this.panelEvidence !== evidence) {
      this.panelEvidence = evidence;
      if (evidence?.status === "loading") evidence.ready.then(() => {
        if (this.model === model && this.panelEvidence === evidence) this.renderPanel();
      });
    }
    if (about) this.panel.showOwn(this.about.panel());
    else this.panel.show({ model, entity: this.lookup(selected), evidence, retry: () => {
      model.unitEvidence.delete(species);
      this.renderPanel();
    } });
    for (const button of this.shadowRoot.querySelectorAll(".species-state")) button.setAttribute("aria-pressed", String(/^(species|model):[^:]+$/.test(this.state.selected || ""))); // a species' panel, or a model system's own
    const had = this.frame.classList.contains("has-panel");
    this.frame.classList.toggle("has-panel", open);
    if (!open) this.toggleViewCard(false); // the card folds again with the next panel
    if (had !== open && this.clientWidth < 760) this.renderLegend(); // the Flux switch moves to the legend's head, or back
    this.placeSheet();
    this.placeFoot();
    if (this.state.lens === "proteins" && this.current?.mounted) renderAtlasNav(this, this.current.chrome().nav || null); // the trail names what is chosen
    if (this.stage) {
      const narrow = this.clientWidth < 760;
      // On a phone the picture is centred in the band left free: from what stands under the bar (the folded card's button)
      // down to the first of what stands on the sheet's top edge (a replay's timeline, the legend's title, the look's
      // switch) or the sheet itself, so that the chosen part and its name are under none of them.
      let bottom = 0;
      if (narrow && open) {
        const origin = this.getBoundingClientRect().top, shown = (element) => element && !element.hidden && element.getClientRects().length > 0;
        const top = Math.max(0, ...[this.bar, this.viewToggle].filter(shown).map((element) => element.getBoundingClientRect().bottom - origin));
        const look = this.lookBox.hidden ? null : this.lookBox.querySelector(".look-switch");
        const floors = [this.panel, this.timeline, look].filter(shown).map((element) => element.getBoundingClientRect().top - origin);
        if (shown(this.legend)) floors.push(this.legend.getBoundingClientRect().bottom - origin - Math.min(this.legend.offsetHeight, 56)); // its title, open or not
        bottom = Math.max(0, this.clientHeight - top - Math.min(...floors));
      }
      // A replay's sweeps' card at the right of a wide window: the picture has the room between it and the cards on the left (the replay frames its sheet there).
      const sweep = !narrow && !open && !this.sweepCard.hidden && this.sweepCard.getClientRects().length ? this.getBoundingClientRect().right - this.sweepCard.getBoundingClientRect().left + 12 : 0;
      // A view that asks for its room clear of the cards on the left (the Laws library) has it on a wide window.
      const left = !narrow && (this.current?.wantsLeftRoom || sweep) ? Math.max(0, ...[this.viewCard, this.legend].filter((element) => element && !element.hidden && element.getClientRects().length).map((element) => element.getBoundingClientRect().right - this.getBoundingClientRect().left + 12)) : 0;
      this.stage.setInsets({ ...(open ? (narrow ? { bottom } : { right: this.panel.offsetWidth + 16 }) : sweep ? { right: sweep } : {}), ...(left ? { left } : {}) });
      this.current?.roomChanged?.();
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
        if (!pending || canvas !== this.canvas || !this.stage || !this.current) return;
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
        if (!this.current.openOnMap?.(label)) this.select(label);
        return;
      }
      const hit = this.stage.pick(event.clientX, event.clientY, this.current.pickRoots);
      if (this.current.openOnMap?.(hit?.id)) return;
      this.current.picked?.(hit); // where it was pressed: a foot that has a machine is looked at closer there
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
      // A view that steps through its parts (the Laws library): ] or Page Down to the next, [ or Page Up to the one before.
      const step = { "]": 1, PageDown: 1, "[": -1, PageUp: -1 }[event.key];
      if (step && this.current?.step) {
        this.select(this.current.step(step), { fly: true });
        event.preventDefault();
      } else if (this.stage.rig.nudge(event.key)) event.preventDefault();
      else if (event.key === " " && this.current?.player?.run) {
        // In a replay, the space bar plays and pauses.
        this.current.player.toggle();
        event.preventDefault();
      }
    });
    this.shadowRoot.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        if (this.state.railOpen) {
          // The folded rail of a phone closes first, and the focus goes back to its button; so does a view's card opened over a panel.
          this.toggleRail(false);
          this.railToggle.focus({ preventScroll: true });
        } else if (this.state.viewOpen && this.state.selected) {
          this.toggleViewCard(false);
          this.viewToggle.focus({ preventScroll: true });
        } else if (this.state.about) this.about.toggle(false); // About closes first, and the focus goes back to what opened it
        else if (this.current?.escape?.()) return; // the protein atlas's own proteins: one level of its trail back
        else if (this.state.selected) this.select(null);
        else if (this.current?.back?.()) return;
        else if (this.state.indexOpen) this.toggleIndex(false);
      }
    }, { signal: this.connection.signal });
  }
}

customElements.define("cells-viewer", CellsViewer);
