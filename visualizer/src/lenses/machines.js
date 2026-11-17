// The Machines view: a catalogue of the molecular machines of the species shown
// (schema/MACHINE_CATALOGUE.md). Asked for on 17 November 2026: a tab of its own, gathered by
// species as the proteins were, in a design of its own.
//
// The machines lie on a bench in trays, one tray for each thing they do. A machine with a
// published size is a simple shape at that size, every one at the same scale (one unit is ten
// nanometres), with a scale bar etched on the bench; a machine with no size in hand is a card
// with its name, the same for all, and the legend says a card is not to scale. Choosing a machine
// lifts it and lights it; a machine with a closer view (the flagellar motor) is drawn from its
// own file (machine_parts.js), as an outline among the others and with its parts when chosen,
// its subunits a step further, as its closer view in the Cell view draws it. Every level is an
// illustration, and the panel says what the record states Cells models of it, and nothing else.
//
// Every visual difference stands for one thing (MARKS, below); the bench, the trays' rims and
// the scale bar's line are the room. No colour, glow or height is a status.

import * as THREE from "../three.js";
import { makeEnvironment, makeStudio } from "../core/environment.js";
import { disposeTree } from "../core/stage.js";
import { fitView, plaqueMesh } from "./laws_marks.js";
import { buildMachine, describeMachinePart } from "./machine_parts.js";
import { loadBeside } from "./protein_shelves.js";
import { IONS, PREFIX, kindOf } from "./machines_data.js";
import { catalogueOf, describe as describeItem, sections as listSections, SWATCH, groupSwatch } from "./machines_card.js";
import { layoutOf, CARD, TRAY, BENCH, UNIT_NM } from "./machines_layout.js";

/** The look this view asks of the stage (core/look.js), as the Laws library's: natural colours under filmic light. */
export const MACHINES_LOOK = { rich: true, filmic: true, exposure: 1.04, contact: true, reach: 0.5, shade: 0.55 };
/** Each group's colour: a token of the page's palette (page.css), one for each thing the machines do. */
export const GROUP_HUE = { proteins: "bioRibosome", genes: "bioNucleus", atp: "bioFuel", ions: "bioIon", membranes: "bioEr", breaking: "bioSignal", moving: "bioMito" };
/** What each role of a machine file's part wears (as its closer view, machine_view.js, dresses it). */
const ROLE_HUE = { membrane: ["bioMembrane", 0.32, true], wall: ["ghost", 0.36, true], rotor: ["bioProtein", 1], stator: ["bioMito", 1], bearing: ["edge", 1], export: ["bioIon", 1], mark: ["fg", 1], swept: ["fg", 0.3, true], arrow: ["fg", 1] };
const VIEW = { azimuth: 0.12, polar: 0.98 };
const LIFT = 0.7; // how far a chosen machine rises from its tray
const MACHINE_SCALE = 1000 / UNIT_NM; // a machine file is drawn in micrometres; here one unit is ten nanometres
const now = () => (typeof performance !== "undefined" ? performance.now() : Date.now());
const columnsFor = (stage) => (stage.width && stage.height && stage.width < stage.height * 0.9 ? 1 : 3);

/** What each visual difference stands for: the legend's words. `when` says when a mark is drawn at all. */
export const MARKS = [
  { id: SWATCH.sized, label: "A shape: drawn to scale from a published size", description: "A simple shape at the size a paper gives, every one at the same scale: the scale bar on the bench is 100 nm. Shapes, not structures.", when: (lens) => lens.counts.sized > 0 },
  { id: SWATCH.card, label: "A card: no size in hand, not to scale", description: "A machine whose size no source in hand gives: a card with its name, the same size for all. It is a label, not a shape.", when: (lens) => lens.counts.cards > 0 },
  { id: "mach-found", label: "Forward: found; faint: not found", description: "While a search is set, the machines it finds stand as they are and the rest fade.", when: (lens) => Boolean(lens.query) },
  { id: SWATCH.chosen, label: "Blue light: your choice", description: "The machine you chose rises from its tray and is lit.", when: () => true },
];
export const MACHINES_NOTE = "The bench, the trays and the scale bar's line are the room, and stand for nothing; a tray's colour is the group's.";

export class MachinesLens {
  constructor(stage, model, labels) {
    this.id = "machines";
    this.stage = stage;
    this.model = model;
    this.labels = labels;
    this.catalogue = catalogueOf(model.raw);
    this.species = null;
    this.root = new THREE.Group();
    this.selected = null;
    this.query = "";
    this.level = 2; // the level a chosen machine with a closer view is drawn at
    this.machines = new Map(); // a machine file's data, by its page id, once read
    this.measured = {};
    this.lifts = new Map();
    this.active = false;
    this.columns = columnsFor(stage);
    this.wantsLeftRoom = true; // the viewer leaves the bench clear of its cards on the left (stage.setInsets left), as for the Laws library
    this.materials = this.makeMaterials();
    this.counts = { machines: 0, sized: 0, cards: 0, laws: 0, groups: 0 };
  }

  // ------------------------------------------------------------ materials

  makeMaterials() {
    const standard = (options) => new THREE.MeshStandardMaterial({ roughness: 0.5, metalness: 0.05, ...options });
    const materials = {
      bench: standard({ roughness: 0.66, metalness: 0.08 }),
      tray: standard({ roughness: 0.4, metalness: 0.2, envMapIntensity: 0.9 }),
      card: standard({ roughness: 0.42, metalness: 0.08 }),
      tab: standard({ roughness: 0.4 }),
      scale: new THREE.MeshBasicMaterial({ toneMapped: false }),
      lit: new THREE.MeshStandardMaterial({ color: 0x000000, roughness: 0.5, metalness: 0, emissiveIntensity: 0.85, envMapIntensity: 0.4, toneMapped: false }),
      groups: new Map(),
    };
    materials.lit.userData.noContact = true;
    materials.scale.userData.noContact = true;
    return materials;
  }

  groupMaterial(group) {
    if (!this.materials.groups.has(group)) this.materials.groups.set(group, new THREE.MeshStandardMaterial({ roughness: 0.38, metalness: 0.06, envMapIntensity: 1 }));
    return this.materials.groups.get(group);
  }

  // ------------------------------------------------------------ the picture

  /** The species shown: its machines are laid out again, and a choice that is not among them is let go. */
  setSpecies(id) {
    if (!id || id === this.species) return;
    this.species = id;
    this.measured = {};
    if (this.selected && !this.has(this.selected)) this.selected = null;
    this.build();
    if (this.active) this.afterBuild(true);
    this.onChrome?.();
  }

  item(id) {
    return this.catalogue && this.species ? this.catalogue.item(this.species, id) : null;
  }

  /** The machine a part's id belongs to (`machine:<kind>:<part>`), while that machine is drawn with its parts. */
  partOf(id) {
    const kind = kindOf(id);
    if (!kind || id === `${PREFIX}${kind}`) return null;
    const owner = `${PREFIX}${kind}`;
    const built = this.built?.get(owner);
    return built && built.level >= 2 && built.ids.has(id) ? owner : null;
  }

  build() {
    if (this.labels && this.active) this.labels.clear();
    for (const child of [...this.root.children]) {
      this.root.remove(child);
      if (child.userData.keep) continue;
      child.traverse((object) => {
        object.geometry?.dispose?.();
        if (object.material && object.material.map) object.material.map.dispose();
        if (object.material?.userData?.own) object.material.dispose();
      });
    }
    this.built = new Map();
    this.lifts.clear();
    const items = this.catalogue && this.species ? this.catalogue.of(this.species) : [];
    this.counts = this.catalogue && this.species ? this.catalogue.counts(this.species) : this.counts;
    this.layout = layoutOf(items, this.catalogue?.groups || [], { columns: this.columns, measured: this.measured, ions: IONS });
    const { trays, items: placed, bench, scale } = this.layout;
    // The bench and the trays: the room.
    const benchMesh = new THREE.Mesh(new THREE.BoxGeometry(bench.w, BENCH.h, bench.d), this.materials.bench);
    benchMesh.position.set(bench.x, -BENCH.h / 2, bench.z);
    benchMesh.userData.unpickable = true;
    this.root.add(benchMesh);
    this.trayMeshes = [];
    for (const tray of trays) {
      const group = new THREE.Group();
      const floor = new THREE.Mesh(new THREE.BoxGeometry(tray.w, 0.3, tray.d), this.materials.tray);
      floor.position.set(tray.x, 0.15, tray.z);
      group.add(floor);
      // The rim: four low walls; the back one in the group's colour.
      const wall = (w, d, x, z, material) => {
        const mesh = new THREE.Mesh(new THREE.BoxGeometry(w, TRAY.h, d), material);
        mesh.position.set(x, TRAY.h / 2, z);
        group.add(mesh);
      };
      const t = 0.45;
      wall(tray.w, t, tray.x, tray.z - tray.d / 2 + t / 2, this.groupMaterial(tray.group));
      wall(tray.w, t, tray.x, tray.z + tray.d / 2 - t / 2, this.materials.tray);
      wall(t, tray.d, tray.x - tray.w / 2 + t / 2, tray.z, this.materials.tray);
      wall(t, tray.d, tray.x + tray.w / 2 - t / 2, tray.z, this.materials.tray);
      group.userData.unpickable = true;
      this.root.add(group);
      this.trayMeshes.push(group);
    }
    // The cards: one body and one coloured tab each, as instances; picked by their instance.
    const cards = placed.filter((entry) => entry.type === "card");
    this.cardList = cards;
    const body = new THREE.InstancedMesh(new THREE.BoxGeometry(1, 1, 1), this.materials.card, Math.max(1, cards.length));
    const tab = new THREE.InstancedMesh(new THREE.BoxGeometry(1, 1, 1), this.materials.tab, Math.max(1, cards.length));
    body.count = tab.count = cards.length;
    for (const mesh of [body, tab]) {
      mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
      mesh.instanceColor = new THREE.InstancedBufferAttribute(new Float32Array(Math.max(1, cards.length) * 3).fill(1), 3);
      mesh.userData.pick = (hit) => cards[hit.instanceId]?.id || null;
      this.root.add(mesh);
    }
    this.cardBody = body;
    this.cardTab = tab;
    this.placeCards();
    // The shapes: each its own mesh, at its size; a machine with a file is built from it once it is read.
    this.shapeMeshes = new Map();
    for (const entry of placed.filter((value) => value.type === "shape")) {
      const holder = new THREE.Group();
      holder.position.set(entry.x, entry.y, entry.z);
      holder.userData.pick = entry.id;
      const shape = entry.shape;
      if (shape.kind === "ellipsoid") {
        const mesh = new THREE.Mesh(new THREE.SphereGeometry(0.5, 40, 28), this.groupMaterial(entry.group));
        mesh.scale.set(shape.w, shape.h, shape.d);
        mesh.position.y = shape.h / 2;
        holder.add(mesh);
      } else if (shape.kind === "rod") {
        const mesh = new THREE.Mesh(new THREE.CapsuleGeometry(shape.radius, Math.max(0.01, shape.length - 2 * shape.radius), 12, 32), this.groupMaterial(entry.group));
        mesh.rotation.z = Math.PI / 2;
        mesh.position.y = shape.radius;
        holder.add(mesh);
      } else if (shape.kind === "machine") {
        this.buildMachineAt(entry, holder);
      }
      this.root.add(holder);
      this.shapeMeshes.set(entry.id, { entry, holder });
    }
    // The names written on the cards, lying flat, and on each tray's head; the scale bar and its words.
    this.writeNames();
    if (scale) {
      const bar = new THREE.Mesh(new THREE.BoxGeometry(scale.length, 0.08, 0.4), this.materials.scale);
      bar.position.set(scale.x + scale.length / 2, 0.04, scale.z);
      bar.userData.unpickable = true;
      this.root.add(bar);
      this.scaleBar = bar;
    } else this.scaleBar = null;
    this.applyColours();
  }

  /** A machine drawn from its own file, at the level it is shown at: an outline among the others, its parts when chosen. */
  buildMachineAt(entry, holder) {
    const data = this.machines.get(entry.id);
    if (!data) {
      this.readMachine(entry);
      return;
    }
    const level = this.selected === entry.id ? this.level : 1;
    const ids = new Set();
    const layers = new Set((data.layers || []).map((layer) => `${PREFIX}${data.id}:${layer.id}`));
    const ctx = {
      material: (role) => {
        const [hue, opacity, glass] = ROLE_HUE[role] || ROLE_HUE.rotor;
        const material = new THREE.MeshStandardMaterial({ roughness: glass ? 0.3 : 0.5, metalness: 0, transparent: opacity < 1, opacity, depthWrite: !glass, side: glass ? THREE.DoubleSide : THREE.FrontSide });
        material.userData = { own: true, hue, role };
        return material;
      },
      add: (object, id) => {
        // Among the other machines the envelope it sits in is left out: the trays are not a cell. Its parts are chosen under their own ids.
        if (layers.has(id)) object.visible = level >= 2;
        if (id && level >= 2) {
          object.userData.pick = id;
          ids.add(id);
        } else object.userData.unpickable = level >= 2 && !id;
      },
    };
    const built = buildMachine(ctx, data, { level });
    const group = new THREE.Group();
    group.add(built.root || built);
    group.scale.setScalar(MACHINE_SCALE);
    // Standing on the tray: its lowest point on the tray's floor, its axis up.
    const box = new THREE.Box3();
    group.updateMatrixWorld(true);
    group.traverseVisible((object) => object.isMesh && box.expandByObject(object));
    if (!box.isEmpty()) group.position.y = -box.min.y;
    holder.add(group);
    this.paint(group);
    this.built.set(entry.id, { level, ids, group });
    if (!this.measured[entry.id] && !box.isEmpty()) {
      const size = box.getSize(new THREE.Vector3());
      this.measured[entry.id] = { w: Math.max(size.x, 1), d: Math.max(size.z, 1), h: Math.max(size.y, 1) };
      this.relayout = true; // laid out again with its true size, at the next frame
    }
  }

  /** Reads a machine's file from beside the page (as its closer view does), then builds it where it stands. */
  readMachine(entry) {
    if (this.reading?.has(entry.id)) return;
    (this.reading ??= new Set()).add(entry.id);
    loadBeside(entry.shape.file)
      .then((data) => {
        this.machines.set(entry.id, data);
        this.reading.delete(entry.id);
        const shown = this.shapeMeshes?.get(entry.id);
        if (shown) this.buildMachineAt(shown.entry, shown.holder);
        this.stage.invalidate?.();
      })
      .catch(() => this.reading.delete(entry.id));
  }

  /** The machine file's materials take their colours from the palette, as the other shapes do. */
  paint(group) {
    const palette = this.stage.palette || {};
    group.traverse((object) => {
      const material = object.material;
      if (material?.userData?.hue && palette[material.userData.hue]) material.color.set(palette[material.userData.hue]);
    });
  }

  placeCards() {
    const dummy = new THREE.Object3D();
    this.cardList.forEach((entry, index) => {
      const lift = this.lifts.get(entry.id) || 0;
      dummy.position.set(entry.x, entry.y + entry.h / 2 + lift, entry.z);
      dummy.scale.set(entry.w, entry.h, entry.d);
      dummy.updateMatrix();
      this.cardBody.setMatrixAt(index, dummy.matrix);
      dummy.position.set(entry.x - entry.w / 2 + 0.55, entry.y + entry.h / 2 + 0.03 + lift, entry.z);
      dummy.scale.set(0.9, entry.h + 0.06, entry.d - 0.2);
      dummy.updateMatrix();
      this.cardTab.setMatrixAt(index, dummy.matrix);
    });
    this.cardBody.instanceMatrix.needsUpdate = this.cardTab.instanceMatrix.needsUpdate = true;
    this.cardBody.computeBoundingSphere();
    this.cardTab.computeBoundingSphere();
  }

  writeNames() {
    const palette = this.stage.palette || {};
    if (this.flatNames) {
      this.root.remove(this.flatNames);
      this.flatNames.material.map?.dispose();
      this.flatNames.material.dispose();
      this.flatNames.geometry.dispose();
    }
    const plaques = [];
    const fit = (text, width, most) => Math.min(most, width / Math.max(1, text.length * 0.56));
    for (const entry of this.cardList) {
      const text = entry.item.short || entry.item.label;
      // Written on the card as it lies: a card that rises (chosen) is named by the page's label above it, so the names are not written again each frame.
      plaques.push({ text, x: entry.x + 0.55, y: -entry.z, z: entry.y + entry.h + 0.02, h: fit(text, entry.w - 1.6, 1.15), align: "center", tone: "strong" });
    }
    for (const tray of this.layout.trays) {
      plaques.push({ text: tray.label, x: tray.x - tray.w / 2 + 1.2, y: -(tray.z + tray.d / 2 - TRAY.head / 2 - 0.2), z: 0.32, h: 1.3, align: "left", tone: "strong" });
    }
    if (this.layout.scale) plaques.push({ text: `${this.layout.scale.nm} nm`, x: this.layout.scale.x + this.layout.scale.length + 0.8, y: -this.layout.scale.z, z: 0.02, h: 1.1, align: "left", tone: "soft" });
    this.flatNames = plaqueMesh(plaques, palette);
    if (this.flatNames) {
      this.flatNames.rotation.x = -Math.PI / 2;
      this.root.add(this.flatNames);
    }
  }

  /** After a build while the view is shown: its labels, and its opening view where nothing is chosen. */
  afterBuild(reframe) {
    this.buildLabels();
    this.refresh();
    if (reframe && !this.selected) this.stage.rig?.setView(this.homeView());
  }

  // ------------------------------------------------------------ the lens interface

  /** A machine of the species shown or one of its parts; or a machine of the catalogue the species lacks, whose panel says which species have it. */
  has(id) {
    if (!id) return false;
    if (this.item(id) || this.partOf(id)) return true;
    const kind = kindOf(id);
    return Boolean(this.catalogue && (kind ? id === `${PREFIX}${kind}` && this.catalogue.kinds.has(kind) : this.catalogue.speciesWith(id).length));
  }

  describe(id) {
    const owner = this.partOf(id);
    if (owner) {
      const data = this.machines.get(owner);
      const panel = describeMachinePart(data, id.split(":").at(-1), { species: (this.model.raw.species || []).find((item) => item.id === this.species) || null });
      return panel ? { ...panel, doors: [...(panel.doors || []), { label: "Back to the machine", lens: "machines", value: owner }] } : null;
    }
    return describeItem(this.catalogue, this.species, id, { scene: this.model.raw, level: this.built?.get(id)?.level ?? null });
  }

  entities() {
    return this.sections().flatMap((section) => section.entities);
  }

  sections() {
    return listSections(this.catalogue, this.species);
  }

  get pickRoots() {
    return [this.root];
  }

  speciesChoice() {
    const species = (this.model.raw.species || []).filter((item) => this.catalogue?.species.includes(item.id) || (this.model.raw.proteins?.atlases || []).some((atlas) => atlas.id === item.id));
    return species.length > 1 ? { options: species.map((item) => [item.id, item.label, item.organism]), active: this.species } : null;
  }

  chrome() {
    const counts = this.counts;
    const label = (this.model.raw.species || []).find((item) => item.id === this.species)?.label || this.species;
    const chosen = this.item(this.selected) || (this.partOf(this.selected) ? this.item(this.partOf(this.selected)) : null);
    const levels = chosen?.entry?.closer?.levels;
    const shown = MARKS.filter((mark) => mark.when(this));
    const found = this.query ? (this.catalogue?.of(this.species) || []).filter((item) => this.catalogue.passes(item, this.query)).length : 0;
    const count = { [SWATCH.sized]: counts.sized, [SWATCH.card]: counts.cards, "mach-found": found, [SWATCH.chosen]: this.layout?.items.some((item) => item.id === this.selected) ? 1 : 0 };
    const groups = (this.catalogue?.groups || []).filter((group) => this.catalogue.inGroup(this.species, group.id).length);
    return {
      card: {
        heading: "Machines",
        species: this.speciesChoice(),
        find: { label: "Find a machine", placeholder: "Find a machine or a gene", value: this.query },
        marks: groups.length > 1 ? { label: "Group", options: [["all", "All groups"], ...groups.map((group) => [group.id, group.label])], active: this.focusGroup || "all" } : null,
        modes: levels ? { label: "Detail", options: levels.map((level) => [String(level.id), level.label]), active: String(this.built?.get(chosen.id)?.level ?? this.level) } : null,
        notice: counts.sized ? null : `No machine of ${label} has a size in hand: each is a card, not a shape.`,
        stats: [[counts.machines, "machines"], [counts.sized, "drawn to scale"], [counts.laws, "in the law inventory"]],
        text: `Illustration: simple shapes from published sizes, not structures, and cards where no size is in hand. No machine here is in the engine. The membrane machines in the last tray are units of the law inventory; each panel says what the inventory states of its laws, and which of them an active model declares.`,
        sources: [
          { name: "The species' files and their own proteins", holds: "which machines each species has, how many, and the proteins its data marks with each (tools/build_catalogue.py)", licence: "each source's own, named in each panel; the files are the project's own, MIT" },
          { name: "Sizes", holds: "from the species' files, each with its sources (the attachment organelle's length), and from the flagellar motor's own file", licence: "each source's own, named in each panel" },
          { name: "The law inventory", holds: "its units that are protein assemblies, as the Protein atlas lists them; its leaks and permeabilities are not machines and are left out", licence: "the project's own, MIT" },
        ],
      },
      legend: {
        title: "What the marks stand for",
        items: [...shown.map((mark) => ({ id: mark.id, label: mark.label, description: mark.description, count: count[mark.id] ?? 0, swatch: mark.id })), ...groups.map((group) => ({ id: groupSwatch(group.id), label: group.label, description: group.plain, count: this.catalogue.inGroup(this.species, group.id).length, swatch: groupSwatch(group.id) }))],
        note: { swatch: "mach-room", text: MACHINES_NOTE },
      },
      stamp: "Illustration",
    };
  }

  activate() {
    const { stage } = this;
    this.active = true;
    stage.scene.add(this.root);
    if (!this.layout) this.build();
    if (stage.sun) {
      stage.sun.castShadow = false;
      stage.sun.position.set(this.layout.bounds.maxX * 0.6, 120, 90);
      stage.sun.target?.position.set(0, 0, this.layout.bench.z);
    }
    stage.dress?.(MACHINES_LOOK);
    this.light();
    this.stopLook ??= stage.look?.onChange?.(() => this.active && this.light());
    if (!this.stopRestore && stage.canvas?.addEventListener) {
      // A lost context that comes back: the names are written again and sent again.
      const restored = () => {
        this.flatNames?.userData.repaint?.();
        stage.invalidate?.();
      };
      stage.canvas.addEventListener("webglcontextrestored", restored);
      this.stopRestore = () => stage.canvas.removeEventListener("webglcontextrestored", restored);
    }
    if (stage.rig) {
      stage.rig.limits = { minDistance: 2, maxDistance: 900, minPolar: 0.2, maxPolar: Math.PI / 2 - 0.05 };
      stage.rig.setView(this.homeView());
      this.homeHeld = { insets: JSON.stringify(stage.insets || {}), until: now() + 2500 };
    }
    this.afterBuild(false);
  }

  light() {
    const { stage } = this;
    if (!stage.renderer || !stage.scene) return;
    const dark = stage.palette?.dark;
    const studio = stage.look?.on?.("reflections") ? (this.studio ??= makeStudio(stage.renderer)) : null;
    this.environment ??= makeEnvironment(stage.renderer);
    stage.scene.environment = studio || this.environment;
    stage.scene.environmentIntensity = dark ? 0.8 : 0.95;
    if (stage.sky) stage.sky.intensity = dark ? 0.9 : 1.3;
    if (stage.sun) stage.sun.intensity = dark ? 2 : 1.8;
  }

  deactivate() {
    const { stage } = this;
    this.active = false;
    stage.dress?.({ rich: false });
    stage.scene.remove(this.root);
    if (stage.scene) stage.scene.environment = null;
    stage.applyPalette?.();
    this.labels.clear();
  }

  /** The opening view: the whole bench, fitted to what the page's cards and panel leave of the screen. */
  homeView() {
    const { bounds } = this.layout;
    const box = new THREE.Box3(new THREE.Vector3(bounds.minX, 0, bounds.minZ), new THREE.Vector3(bounds.maxX, Math.min(bounds.maxY, 12), bounds.maxZ));
    return this.fitOnScreen(box, 0.04);
  }

  fitOnScreen(box, margin) {
    const { stage } = this, { right = 0, bottom = 0, left = 0 } = stage.insets || {};
    const width = stage.width || 1600, height = stage.height || 1000, fov = stage.camera?.fov || 34;
    const seen = Math.max(0.2, (height - bottom) / height);
    const narrowed = (2 * Math.atan(Math.tan((fov * Math.PI) / 360) * seen) * 180) / Math.PI;
    return fitView(box, { fov: narrowed, aspect: Math.max(0.3, (width - right - left) / Math.max(1, height - bottom)), ...VIEW, margin });
  }

  /** Each shape drawn to scale has its name on the picture; a card's is written on it. The chosen machine's too. */
  buildLabels() {
    const labels = this.labels;
    if (!labels || !this.active) return;
    labels.clear();
    for (const { entry } of this.shapeMeshes?.values() || []) {
      labels.add({ id: entry.id, text: entry.item.label, anchor: new THREE.Vector3(entry.x, entry.y + entry.h + 0.6 + (this.lifts.get(entry.id) || 0), entry.z), priority: 700, kind: "part", lift: 2 });
    }
    const chosen = this.cardList?.find((entry) => entry.id === this.selected);
    if (chosen) labels.add({ id: chosen.id, text: chosen.item.label, anchor: new THREE.Vector3(chosen.x, chosen.y + LIFT + 0.8, chosen.z), priority: 2000, kind: "part", lift: 10 });
  }

  setSelection(id) {
    const owner = this.partOf(id);
    const next = id && this.has(id) ? id : null;
    const before = this.selected;
    this.selected = owner ? owner : next;
    this.selectedPart = owner ? id : null;
    // A machine with a file is drawn with its parts while it is chosen, as an outline again when it is let go.
    const rebuild = [before, this.selected].filter((value, index, all) => value && all.indexOf(value) === index && this.shapeMeshes?.get(value)?.entry.shape.kind === "machine");
    if (before !== this.selected && !owner) this.level = 2;
    for (const value of rebuild) this.rebuildMachine(value);
    this.refresh();
    if (before !== this.selected) this.onChrome?.(); // the card's Detail is offered while a machine with levels is chosen
  }

  rebuildMachine(id) {
    const shown = this.shapeMeshes?.get(id);
    if (!shown) return;
    for (const child of [...shown.holder.children]) {
      shown.holder.remove(child);
      disposeTree(child);
    }
    this.built.delete(id);
    this.buildMachineAt(shown.entry, shown.holder);
  }

  setHover() {}

  setIsolate() {}

  /** The card's Detail: the level a chosen machine with a closer view is drawn at. */
  setMode(value) {
    const level = Number(value);
    if (![1, 2, 3].includes(level) || level === this.level) return;
    this.level = level;
    if (this.selected) this.rebuildMachine(this.selected);
    this.refresh();
    this.onChrome?.();
    this.onOpen?.();
  }

  /** The card's Group: the camera goes to that tray, and back to the whole bench when it is let go. */
  setMark(value) {
    this.focusGroup = value && value !== "all" ? value : null;
    this.onChrome?.();
    if (!this.active) return;
    const tray = this.layout.trays.find((item) => item.group === this.focusGroup);
    if (tray) this.flyToBox(new THREE.Box3(new THREE.Vector3(tray.x - tray.w / 2, 0, tray.z - tray.d / 2), new THREE.Vector3(tray.x + tray.w / 2, 4, tray.z + tray.d / 2)));
    else this.stage.rig?.flyTo?.(this.homeView(), 900);
  }

  /** A door from another view (the viewer's openDoor, `value`): the machine it names is chosen. */
  setFinding(id) {
    if (id && this.has(id)) this.onShown?.(id);
  }

  back() {
    return false;
  }

  setQuery(text) {
    const before = Boolean(this.query);
    this.query = String(text || "");
    this.refresh();
    if (before !== Boolean(this.query)) this.onChrome?.();
  }

  /** Colours, lifts and fades: what is chosen and what a search finds. */
  refresh() {
    if (!this.layout) return;
    const passes = (item) => !this.query || this.catalogue.passes(item, this.query);
    for (const entry of this.layout.items) this.liftTarget(entry.id, entry.id === this.selected ? LIFT : 0);
    this.applyColours(passes);
    if (this.active) this.buildLabels();
    this.stage.invalidate?.();
  }

  liftTarget(id, value) {
    (this.targets ??= new Map()).set(id, value);
  }

  applyColours(passes = () => true) {
    const palette = this.stage.palette || {};
    const tone = (value, fallback = "#888888") => new THREE.Color(value || fallback);
    const faint = (colour) => colour.clone().lerp(tone(palette.bg, "#ffffff"), 0.72);
    for (const [group, material] of this.materials.groups) material.color.copy(tone(palette[GROUP_HUE[group]] || palette.ghost));
    this.materials.card.color.set(0xffffff);
    this.materials.tab.color.set(0xffffff);
    if (this.cardList) {
      this.cardList.forEach((entry, index) => {
        const chosen = entry.id === this.selected, found = passes(entry.item);
        const body = chosen ? tone(palette.accent) : tone(palette.dark ? palette.plateEdge : palette.plate, "#f4f7f9");
        const tab = chosen ? tone(palette.accent) : tone(palette[GROUP_HUE[entry.group]] || palette.ghost);
        this.cardBody.setColorAt(index, found ? body : faint(body));
        this.cardTab.setColorAt(index, found ? tab : faint(tab));
      });
      if (this.cardBody.instanceColor) this.cardBody.instanceColor.needsUpdate = true;
      if (this.cardTab.instanceColor) this.cardTab.instanceColor.needsUpdate = true;
    }
    for (const { entry, holder } of this.shapeMeshes?.values() || []) {
      const chosen = entry.id === this.selected && entry.shape.kind !== "machine", found = passes(entry.item);
      holder.traverse((object) => {
        if (!object.isMesh) return;
        if (entry.shape.kind !== "machine") object.material = chosen ? this.materials.lit : this.groupMaterial(entry.group);
        object.material.transparent = !found || object.material.userData?.base < 1 || object.material.opacity < 1;
        if (!found) object.material.opacity = 0.25;
        else if (entry.shape.kind !== "machine") object.material.opacity = 1;
      });
    }
    if (palette.accent) this.materials.lit.emissive.set(palette.accent);
    this.materials.tray.color.copy(tone(palette.dark ? palette.plate : palette.plateEdge, "#dfe6eb"));
    this.materials.bench.color.copy(tone(palette.dark ? palette.bg : palette.plate, "#eef2f5"));
    this.materials.scale.color.copy(tone(palette.fg, "#12283a"));
  }

  /** A move toward what was chosen: its shape or card with its neighbours in the tray. */
  focus(id) {
    const owner = this.partOf(id) || id;
    const entry = this.layout?.items.find((item) => item.id === owner);
    if (!entry) return;
    const pad = entry.type === "card" ? 6 : Math.max(2, Math.max(entry.w, entry.h) * 0.6);
    const box = new THREE.Box3(new THREE.Vector3(entry.x - entry.w / 2 - pad, entry.y, entry.z - entry.d / 2 - pad), new THREE.Vector3(entry.x + entry.w / 2 + pad, entry.y + entry.h + LIFT + 1, entry.z + entry.d / 2 + pad));
    this.flyToBox(box);
  }

  flyToBox(box) {
    const { stage } = this, rig = stage.rig;
    if (!rig?.flyTo || box.isEmpty()) return;
    this.homeHeld = null;
    const view = this.fitOnScreen(box, 0.1);
    rig.flyTo(view, 1000);
    this.focused = { box: box.clone(), insets: JSON.stringify(stage.insets || {}), until: now() + 1600 };
  }

  update(dt = 16) {
    if (this.stage.width && this.stage.height && columnsFor(this.stage) !== this.columns) {
      this.columns = columnsFor(this.stage);
      this.build();
      this.afterBuild(true);
      return true;
    }
    if (this.relayout) {
      this.relayout = false;
      this.build();
      this.afterBuild(!this.selected);
      return true;
    }
    const held = this.homeHeld, insets = JSON.stringify(this.stage.insets || {});
    if (held && !this.selected && now() < held.until && held.insets !== insets) {
      held.insets = insets;
      this.stage.rig?.setView?.(this.homeView());
    }
    const focused = this.focused;
    if (focused && now() < focused.until && focused.insets !== insets) this.flyToBox(focused.box);
    // The chosen machine rises; the others settle.
    const k = this.stage.reducedMotion ? 1 : Math.min(1, (dt / 1000) * 9);
    let moving = false, cards = false;
    for (const [id, target] of this.targets || []) {
      const at = this.lifts.get(id) || 0;
      if (Math.abs(target - at) < 1e-3) {
        if (at !== target) this.lifts.set(id, target);
        else continue;
      } else {
        this.lifts.set(id, at + (target - at) * k);
        moving = true;
      }
      const shape = this.shapeMeshes?.get(id);
      if (shape) shape.holder.position.y = shape.entry.y + this.lifts.get(id);
      else cards = true;
    }
    if (cards) this.placeCards();
    return moving;
  }

  applyPalette(palette) {
    this.palette = palette;
    if (!this.layout) return;
    this.applyColours((item) => !this.query || this.catalogue.passes(item, this.query));
    for (const { group } of this.built?.values() || []) this.paint(group);
    if (this.active) this.writeNames();
  }

  /** What one frame costs to draw, counted from the scene: draws and triangles of every visible thing. */
  cost() {
    let draws = 0, triangles = 0;
    this.root.traverseVisible((object) => {
      if (!(object.isMesh || object.isLine || object.isPoints)) return;
      const instances = object.isInstancedMesh ? object.count : 1;
      if (instances === 0) return;
      draws += 1;
      const geometry = object.geometry;
      if (object.isMesh) triangles += ((geometry.index ? geometry.index.count : geometry.attributes.position.count) / 3) * instances;
    });
    return { draws, triangles: Math.round(triangles) };
  }

  dispose() {
    this.stopLook?.();
    this.stopRestore?.();
    disposeTree(this.root);
    this.environment?.dispose?.();
    this.studio?.dispose?.();
  }
}
