// A closer view of a machine of the species' cell, in the Cell view (schema/MACHINES.md).
// The user, 16 November 2026: "look closer sounds good", and of the flagellar motor: "yes it
// should turn at real life speeds at flux ... except if we slow down the flux".
//
// "Look closer" in the panel of the foot a machine stands at (or the machine's stop on the
// scale rail, or `machine=<id>` in the address) fetches the machine's file, which is published
// beside the page, builds the machine at the foot pressed (else the one that faces the camera
// most; machine_parts.js builds it), and flies the camera there from the side that foot faces,
// framing it in the part of the picture a panel leaves. As the camera comes close the cell fades out and the machine fades in: the cell is
// drawn schematic, its shells at the picture's own spacing, so the two are never seen together
// whole. The machine is drawn at its true size, upright (outside up), turned so that the wedge
// that opens its envelope faces the camera. Flying out again (the rail, "Back to the cell",
// Escape, or zooming out far enough) brings the cell back.
//
// The machine's motion is its flux (schema/QUANTITY_LAYERS.md, rule 13): it turns while the
// machine is what the visitor looks at (opened by the visitor, not by the address), or while
// the Flux switch shows all; it stands when the address opened it, on a page opened still, and
// for a visitor who asks for less motion. It turns at real-life speed, slowed only by the Cell
// view's flux slow-down, which it reads in one place (`speed`), with the flux's own words.
// What the picture says of it goes through the flux's statement, so the picture has one.
//
// Nothing here belongs to one machine or one species: the file says what is drawn, and Cells
// has no model of any machine drawn here.

import * as THREE from "../three.js";
import { buildMachine, describeMachine, describeMachinePart } from "./machine_parts.js";
import { MachineMotion } from "../layers/machine_motion.js";
import { loadBeside } from "./protein_shelves.js";

/** The rail's stop for a machine, among the levels of the Cell view. */
export const MACHINE_STOP = "machine";
const FLIGHT = 1700; // milliseconds of the flight in and out

/** How close the camera may come while a closer view is open, in micrometres. */
export const LEAST_DISTANCE = 0.01;
// How the machine is framed: about this much of it, in micrometres, tall and wide, seen a little from above
// and a little to one side of the wedge that opens its envelope.
const FRAME = { tall: 0.17, wide: 0.1, middle: 0.042, polar: 1.12, aside: 0.28 };
// The cell gives way to the machine between these multiples of the machine's framing distance; beyond
// the last the closer view ends by itself.
const VEIL = { near: 1.35, far: 2.7, ends: 3.2 };
// What each role of a part wears: a token of the page's palette (checked with the others), how opaque, and
// whether it is glass. A mark and its swept form wear the page's high-contrast neutral against the rotor.
const ROLES = {
  membrane: { token: "bioMembrane", opacity: 0.32, glass: true },
  wall: { token: "ghost", opacity: 0.36, glass: true },
  rotor: { token: "bioProtein", opacity: 1 },
  stator: { token: "bioMito", opacity: 1 },
  bearing: { token: "edge", opacity: 1 },
  export: { token: "bioIon", opacity: 1 },
  mark: { token: "contrast", opacity: 1 },
  swept: { token: "contrast", opacity: 0.3, glass: true },
  arrow: { token: "fg", opacity: 1 },
};
const smooth = (a, b, x) => {
  const t = Math.min(1, Math.max(0, (x - a) / (b - a)));
  return t * t * (3 - 2 * t);
};

/** The colour a role wears in a palette: a token, or for marks the neutral that stands out on the rotor in that theme. */
export function roleColour(role, palette) {
  const token = (ROLES[role] || ROLES.rotor).token;
  if (token === "contrast") return palette.dark ? palette.fg : palette.bgRaised;
  return palette[token] || palette.ghost || "#888888";
}

/** Of a part's proteins, a little lighter or darker by their place among the part's own: a protein is told by its panel, not its hue. */
const shadeOf = (index) => [0, 0.08, -0.08, 0.14, -0.14][index % 5];

/** A text with each of its lines broken at spaces to at most about `width` characters. */
export const wrapLines = (text, width) =>
  text
    .split("\n")
    .map((line) => {
      const rows = [];
      let row = "";
      for (const word of line.split(" ")) {
        if (row && row.length + 1 + word.length > width) {
          rows.push(row);
          row = word;
        } else row = row ? `${row} ${word}` : word;
      }
      if (row) rows.push(row);
      return rows.join("\n");
    })
    .join("\n");

/** The widths the statement's lines are broken to, widest first: the picture shows the first that has room. */
const STATEMENT_WIDTHS = [110, 84, 64, 50, 40];

export class MachineView {
  constructor(lens) {
    this.lens = lens;
    this.files = new Map(); // file -> the machine's data, or the promise of it
    this.entry = null; // the scene's entry for the machine shown: { id, label, called, at, file }
    this.data = null; // its file
    this.built = null;
    this.motion = null;
    this.zone = null;
    this.open = false; // in the closer view (or flying out of it)
    this.leaving = false;
    this.visitor = false; // the visitor opened it (not the address): it turns
    this.level = 2;
    this.foot = null; // { at, out } in world units: where the machine stands
    this.azimuth = 0;
    this.distance = 1; // the framing distance, in micrometres
    this.fade = 0;
    this.materials = [];
    this.ids = new Set();
    this.hit = null; // where the visitor last pressed a foot
    this.said = null;
    this.turningNow = false;
    this.slowNow = 1;
  }

  get stage() {
    return this.lens.stage;
  }

  /** The machines the species' entry in the scene names: { id, label, called, at, file }. */
  entries() {
    return this.lens.species?.machines || [];
  }

  /** The machine that stands at a base (a flagellum's foot), or null. */
  entryAt(baseId) {
    return this.entries().find((entry) => entry.at?.base === baseId) || null;
  }

  /** The door "Look closer" for a piece of scenery that is the foot of such a machine; null otherwise. */
  door(item) {
    const entry = item?.kind === "base" ? this.entryAt(item.base?.id) : null;
    return entry ? { label: "Look closer", look: "closer", machine: entry.id } : null;
  }

  /** The rail's stops for the machines: one for the first, among the levels. */
  railStops() {
    const entry = this.entries()[0];
    return entry ? [{ id: MACHINE_STOP, label: entry.label, title: `A closer view of the ${entry.label.toLowerCase()}, drawn from published sizes: an illustration. Cells has no model of it.` }] : [];
  }

  /** The visitor pressed something: where, so that "Look closer" goes to the foot pressed. */
  picked(hit) {
    if (hit?.id && hit.point) this.hit = { id: hit.id, point: hit.point.clone() };
  }

  /** The feet the cell drew for the machine's appendage, in world units. */
  feet(entry) {
    const lens = this.lens, cell = lens.cells?.[lens.sizeMode];
    const item = (cell?.scenery || []).find((piece) => piece.kind === "base" && piece.base?.id === entry.at?.base);
    return (item?.feet || []).map((foot) => ({ at: foot.at.clone().multiplyScalar(lens.u), out: foot.out.clone(), id: item.id }));
  }

  /** The foot to stand the machine at: the one nearest where the visitor pressed it, else the one that faces the camera most. */
  chooseFoot(entry) {
    const feet = this.feet(entry);
    if (!feet.length) return null;
    if (this.hit && feet.some((foot) => foot.id === this.hit.id)) {
      const near = this.hit.point;
      return feet.reduce((best, foot) => (foot.at.distanceTo(near) < best.at.distanceTo(near) ? foot : best));
    }
    const camera = this.stage.camera.position;
    const facing = (foot) => foot.out.dot(camera.clone().sub(foot.at).normalize());
    return feet.reduce((best, foot) => (facing(foot) > facing(best) ? foot : best));
  }

  /** The camera's azimuth for a foot: from the side the foot faces, so that the flight in stays outside the cell; else as the camera stands. */
  azimuthFor(foot) {
    const across = Math.hypot(foot.out.x, foot.out.z);
    return across > 0.35 ? Math.atan2(foot.out.x, foot.out.z) : this.stage.rig.azimuth;
  }

  /** The machine's file, fetched once (published beside the page, or carried in it). */
  load(entry) {
    if (!this.files.has(entry.file)) this.files.set(entry.file, loadBeside(entry.file).then((data) => (this.files.set(entry.file, data), data)));
    return Promise.resolve(this.files.get(entry.file));
  }

  /**
   * Look closer: fetch, build and fly in. `address` is true where the page's address asked for
   * it (the machine then stands until the visitor chooses); `detail` a level. Resolves to
   * whether the machine is now shown.
   */
  async lookCloser(id, { address = false, detail = null } = {}) {
    const entry = this.entries().find((item) => item.id === id) || (id ? null : this.entries()[0]);
    if (!entry) return false;
    let data;
    try {
      data = await this.load(entry);
    } catch (error) {
      console.warn(`machine ${entry.id}: ${error.message}`);
      return false;
    }
    if (this.lens.species?.machines?.every((item) => item !== entry)) return false; // the species changed meanwhile
    const foot = this.chooseFoot(entry);
    if (!foot) return false;
    if ([1, 2, 3].includes(Number(detail))) this.level = Number(detail);
    this.entry = entry;
    this.data = data;
    this.foot = foot;
    this.visitor = !address;
    this.addressed = address;
    this.azimuth = this.azimuthFor(foot);
    this.build();
    this.open = true;
    this.leaving = false;
    this.framedFor = this.insetKey();
    // While the view is open the camera may come as close as the machine asks (the lens keeps
    // this in its fades): lifted here before the flight too, because a flight with less motion
    // asked for (or on a still page) arrives at once, and would stop at the cell's own limit.
    if (this.stage.rig.limits) this.stage.rig.limits.minDistance = Math.min(this.stage.rig.limits.minDistance, LEAST_DISTANCE);
    this.stage.rig.flyTo(this.frameView(), FLIGHT);
    this.lens.buildLabels();
    this.lens.fades(true);
    this.sync(true);
    this.lens.onChrome?.();
    return true;
  }

  /** The camera's view that frames the machine on the current screen. */
  /** The panels over the picture, as a key: the frame is worked out for these. */
  insetKey() {
    const { right = 0, bottom = 0 } = this.stage.insets || {};
    return `${Math.round(right)},${Math.round(bottom)}`;
  }

  /**
   * A panel opened or closed over the picture (the machine's own panel after the rail's stop or
   * the address, a sheet closed on a phone) while the motor stands framed or is flown to: it is
   * framed again in what the panel leaves. Where the visitor has moved the camera, it stays.
   */
  reframe() {
    if (!this.open || this.leaving || !this.foot) return;
    const key = this.insetKey();
    if (key === this.framedFor) return;
    this.framedFor = key;
    const rig = this.stage.rig, flight = rig.flight;
    if (!flight && Math.abs(rig.distance - this.distance) > 0.02 * this.distance) return;
    rig.flyTo(this.frameView(), flight ? Math.max(600, flight.duration - flight.elapsed) : 600);
  }

  frameView() {
    const { camera, insets = {}, width = 0, height = 0 } = this.stage;
    const half = Math.tan((camera.fov * Math.PI) / 360);
    // A panel over the picture (a sheet below on a phone, a card to the right) leaves part of it: the machine is framed in that part.
    const free = (inset, size) => (size > 0 ? Math.max(0.35, 1 - (inset || 0) / size) : 1);
    this.distance = Math.max(FRAME.tall / 2 / (half * free(insets.bottom, height)), FRAME.wide / 2 / (half * camera.aspect * free(insets.right, width))) * 1.08;
    const target = this.foot.at.clone().add(new THREE.Vector3(0, FRAME.middle, 0));
    return { target, distance: this.distance, azimuth: this.azimuth, polar: FRAME.polar };
  }

  /** The machine at its level, built anew at the foot, in a zone of the lens's own. */
  build() {
    this.takeDown();
    const lens = this.lens;
    this.zone ??= lens.zone("machine");
    const ctx = {
      material: (role, options = {}) => this.material(role, options),
      add: (object, id) => this.register(object, id),
    };
    this.built = buildMachine(ctx, this.data, { level: this.level });
    const root = this.built.root;
    root.position.copy(this.foot.at);
    // Upright, outside up, and turned so that the wedge that opens its envelope faces the camera, a little to one side.
    root.rotation.y = this.azimuth - FRAME.aside;
    this.zone.root.add(root);
    this.motion = new MachineMotion(this.built);
    // The motion gave each set of marks materials of its own: those are what a highlight and the palette must reach.
    for (const set of this.built.sets) for (const object of [...set.objects, set.blur]) this.materials.push(object.material);
    this.collect();
    this.applyPalette(this.stage.palette || {});
    this.motion.setFade(this.fade);
    this.applyFade(this.fade, true);
  }

  material(role, options) {
    const look = ROLES[role] || ROLES.rotor;
    const material = new THREE.MeshStandardMaterial({ roughness: look.glass ? 0.3 : 0.5, metalness: 0, transparent: true, opacity: look.opacity, depthWrite: !look.glass, side: look.glass ? THREE.DoubleSide : THREE.FrontSide });
    material.userData = { ...options, role, base: look.opacity };
    this.materials.push(material);
    return material;
  }

  /** An object the machine put in the picture: chosen under its id, or passed through. Glass lets a press reach what is behind it. */
  register(object, id) {
    if (id) {
      object.userData.pick = id;
      this.ids.add(id);
      const role = object.material?.userData?.role;
      if (role === "membrane" || role === "wall") object.userData.seeThrough = true;
    } else object.userData.unpickable = true;
  }

  /** The lens lights a chosen piece of scenery by its materials: the machine's parts are lit the same way. */
  collect() {
    const looks = this.lens.sceneryLooks;
    for (const id of this.ids) looks.delete(id);
    this.built.root.traverse((object) => {
      let id = null;
      for (let node = object; node && !id; node = node.parent) if (typeof node.userData.pick === "string") id = node.userData.pick;
      if (!id || !object.material) return;
      if (!looks.has(id)) looks.set(id, new Set());
      looks.get(id).add(object.material);
    });
  }

  /** Take the machine down (another level, another species, or the lens goes). */
  takeDown() {
    for (const id of this.ids) this.lens.sceneryLooks.delete(id);
    this.ids.clear();
    if (this.built) {
      this.built.root.removeFromParent();
      this.built.root.traverse((object) => object.geometry?.dispose());
    }
    for (const material of this.materials) material.dispose();
    this.materials = [];
    this.built = null;
    this.motion = null;
  }

  /** The lens disposed of its zones (another species): nothing of the machine is left. */
  clear() {
    this.takeDown();
    this.zone = null;
    this.open = this.leaving = false;
    this.entry = this.data = this.foot = null;
    this.fade = 0;
    this.holdLook(false);
  }

  /** Leave the closer view: fly to a stop of the cell's (the cell by default); the cell comes back as the camera goes out. */
  leave(view) {
    if (!this.open) return false;
    this.leaving = true;
    this.visitor = false;
    if (view) this.stage.rig.flyTo(view, FLIGHT);
    this.sync(true);
    this.lens.onChrome?.();
    return true;
  }

  /** The closer view has ended: the camera is out, or the visitor zoomed out of it. */
  end() {
    this.open = this.leaving = false;
    this.sync(true);
    this.lens.onMode?.(); // a panel of a part of the machine no longer belongs to the picture
    this.lens.onChrome?.();
  }

  /** How far the machine is faded in, for a camera this far away: 0 where the closer view is not open. */
  veil(distance) {
    if (!this.open || !this.built) return 0;
    return 1 - smooth(VEIL.near * this.distance, VEIL.far * this.distance, distance);
  }

  /** The lens faded the machine's zone: its materials, its marks and its names follow. */
  applyFade(fade, force = false) {
    if (!force && Math.abs(fade - this.fade) < 0.004) return;
    const said = this.fade >= 0.5;
    this.fade = fade;
    const sets = new Set(this.built ? this.built.sets.flatMap((set) => [...set.objects, set.blur].map((object) => object.material)) : []);
    for (const material of this.materials) if (!sets.has(material)) material.opacity = material.userData.base * fade;
    this.motion?.setFade(fade);
    if (this.zone) this.zone.root.visible = fade > 0.01;
    // The picture's statement says the machine's words from half way in (statement()): written again as it crosses.
    if (said !== fade >= 0.5) this.lens.flux?.words?.();
  }

  /** The lens's fades ran: end the closer view where the camera has gone out of it. */
  watch(distance) {
    if (!this.open || this.stage.rig.flight) return;
    if (distance > VEIL.ends * this.distance) this.end();
  }

  // ------------------------------------------------------------ motion

  /** Whether nothing may move: the visitor asks for less motion, or the picture is a still one. */
  still() {
    return Boolean(this.stage.reducedMotion || this.stage.rig?.instant);
  }

  /** Whether the rotor turns now: the closer view shows, and the visitor opened it or the Flux switch shows all, and motion is allowed. */
  get turning() {
    return Boolean(this.open && !this.leaving && this.built && !this.still() && (this.visitor || this.lens.flux.on));
  }

  /** The speed: the Cell view's flux's, in one place, with the flux's own words for it. */
  speed() {
    const flux = this.lens.flux;
    return { slow: flux.slow, said: flux.slowSaid() };
  }

  /** The visitor chose something through the page: an address's view turns from here on, as a part chosen does. */
  chosen() {
    if (!this.open || this.leaving) return;
    this.visitor = true;
    this.sync(); // the panel, the legend and the statement follow at once, not at the next frame
  }

  /** The page's address chose a part as it opened: that is no choice of the visitor's, and the machine stands. */
  hold() {
    if (!this.open || !this.addressed) return;
    this.visitor = false;
    this.sync(); // so that a panel drawn in between, while the choice counted as the visitor's, says it stands
  }

  /** Bring the motion and what is said of it in line with the state: turning or not, the slow-down. */
  sync(force = false) {
    if (!this.motion) {
      this.holdLook(false);
      if (force) this.lens.flux.words();
      return;
    }
    const turning = this.turning, { slow } = this.speed();
    if (!force && turning === this.turningNow && slow === this.slowNow) return;
    this.turningNow = turning;
    this.slowNow = slow;
    this.motion.set({ turning, slow });
    this.holdLook(turning);
    this.lens.flux.words(); // the picture's statement is the flux's, and says the machine's words while it shows
    this.lens.onChrome?.(); // the legend's Speed row is offered while it turns
    if (this.has(this.lens.selected)) this.lens.onPanel?.(); // the open panel's notice and words follow
  }

  /** While the rotor turns it holds the motion channel: the look's own motion stands (rule 12). */
  holdLook(on) {
    const decoration = this.stage?.decoration;
    if (!decoration) return;
    if (on && !this.holding) decoration.pause("machine");
    if (!on && this.holding) decoration.resume("machine");
    this.holding = on;
  }

  /** Once a frame while the lens is shown. Returns whether anything of the machine moves. */
  update(dt, time, real) {
    if (!this.built) return false;
    this.sync();
    this.reframe();
    const moving = this.motion.update(dt, time, real);
    if (this.open) this.lens.flux.pin();
    return moving || this.leaving;
  }

  // ------------------------------------------------------------ what the page says

  /** What the picture says while the machine shows, in the flux statement's form: { notice, ways }; null while it does not. */
  statement() {
    if (!this.open || this.leaving || !this.motion || this.fade < 0.5) return null;
    const { said } = this.speed();
    const lines = this.motion.statement(said);
    const whole = lines.slice(1).join("\n");
    return { notice: lines[0], ways: [...new Set([whole, ...STATEMENT_WIDTHS.map((width) => wrapLines(whole, width))])] };
  }

  /** What the legend's Flux block says while the machine shows: { turning, keys, hint, example }; null while it does not. */
  legend() {
    if (!this.open || this.leaving || !this.motion) return null;
    const lines = this.motion.statement(this.speed().said);
    const turning = this.turning;
    const keys = [
      { key: "way", text: `${lines[1]}. The arrowhead shows the way` },
      { key: "time", text: lines[2] },
      { key: "bead", text: "At real-life speed a turning part's marks are drawn smeared round, as the eye would see them; slowed, they turn" },
    ];
    const name = `The ${this.data.called || this.data.label.toLowerCase()}`;
    const why = this.still() ? `${name} stands: this device asks for less motion, or the picture is a still one.` : `${name} stands: the page's address opened this view. Choose a part, or show all with the switch, to see it turn.`;
    return { turning, keys, hint: turning ? null : why, example: turning ? lines[0].split(" · ")[0] : null };
  }

  /** The rail's level, the card's detail switch and its note, while the closer view is open. */
  chrome() {
    if (!this.open || this.leaving) return null;
    return {
      detail: { active: this.level, options: (this.data.levels || []).map((item) => [item.id, item.label]) },
      note: `Drawn to scale from published sizes, as simple shapes, not structures, and upright: outside the cell is up. Each part's panel says where its sizes come from, and in which organism they were measured.`,
    };
  }

  /** Another level of detail: built again where it stands. */
  setDetail(level) {
    const next = Number(level);
    if (!this.built || ![1, 2, 3].includes(next) || next === this.level) return;
    this.level = next;
    this.build();
    this.turningNow = !this.turning; // the new motion takes the state afresh
    this.sync();
    this.lens.buildLabels();
    this.lens.onChrome?.();
    this.lens.onOpen?.(); // the machine's own panel lists the parts of this level
  }

  /** Whether an id is the machine's or one of its parts or layers, while the closer view is open. */
  has(id) {
    if (!this.open || !this.data || typeof id !== "string") return false;
    if (id === `machine:${this.data.id}`) return true;
    const part = id.startsWith(`machine:${this.data.id}:`) ? id.slice(`machine:${this.data.id}:`.length) : null;
    return Boolean(part && [...this.data.parts, ...(this.data.layers || [])].some((item) => item.id === part));
  }

  /** The panel of the machine, or of one of its parts, with the door back to the cell. */
  describe(id) {
    if (!this.has(id)) return null;
    const species = this.lens.species, capability = this.lens.model.get("cap.machines") || null;
    const back = { label: "Back to the cell", look: "back" };
    // While it turns the panel carries the picture's notice too, for a narrow screen whose sheet covers the picture (rule 13).
    const notice = (panel) => (this.turning ? { ...panel, chips: panel.chips.map((chip) => (chip.label === "Illustration" ? { ...chip, label: "Illustration: not a run" } : chip)) } : panel);
    if (id === `machine:${this.data.id}`) {
      const words = this.motion ? this.motion.statement(this.speed().said) : [];
      return notice(describeMachine(this.data, { species, capability, level: this.level, words, doors: [back] }));
    }
    const panel = describeMachinePart(this.data, id.split(":").at(-1), { species, capability });
    return panel ? notice({ ...panel, doors: [...panel.doors, back] }) : null;
  }

  /** The names of the parts drawn at this level, on the picture; they fade with the machine. */
  label(labels) {
    if (!this.zone || !this.built) return;
    this.zone.labels = [];
    this.built.root.updateMatrixWorld(true);
    const narrow = this.stage.width < 600;
    for (const item of this.built.items) {
      if (item.layer && narrow) continue; // on a phone the envelope's names give way to the parts'
      const anchor = this.built.root.localToWorld(item.anchor.clone());
      const label = labels.add({ id: item.id, text: item.label.replace(/ \(.*\)$/, ""), anchor, priority: item.layer ? 35 : 60, kind: "part", lift: 4 });
      label.hidden = this.fade < 0.55;
      this.zone.labels.push(label);
    }
  }

  applyPalette(palette) {
    for (const material of this.materials) {
      const role = material.userData.role;
      material.color.set(roleColour(role, palette));
      if (material.userData.protein && material.userData.part) {
        const part = this.data?.parts.find((item) => item.id === material.userData.part);
        const index = Math.max(0, (part?.proteins || []).findIndex((protein) => protein.id === material.userData.protein));
        material.color.offsetHSL(0, 0, shadeOf(index));
      }
    }
    this.stage?.invalidate();
  }
}
