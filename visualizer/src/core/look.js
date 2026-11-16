// The look of a scene at rest: which of the seven effects are drawn, what a device that
// cannot keep up gives up, and the clock of what moves only for decoration.
//
// The user chose the effects on 15 November 2026, from a page of options
// (docs/FLUX_AND_LOOK.md): studio reflections, filmic light, soft translucency, contact
// shade, crowd drift, surface texture and membrane shimmer. Bloom is kept for flux.
//
// Nothing here draws. The stage owns one Look and one Decoration; a lens that wants the
// rich look says so while it is shown (the Cell view does), and reads from the Look which
// effects are on. The other views never ask, so they keep the look they had.
//
// For whoever builds flux (schema/QUANTITY_LAYERS.md, rule 12: decoration never moves with
// a direction, and stops while a layer on the motion channel shows):
//   stage.decoration.pause("flux")    the drift and the shimmer hold still
//   stage.decoration.resume("flux")   and move again, unless something else holds them
//   stage.setBloom(0.6)               bloom on, at that strength; stage.setBloom(0) is off
//                                     (options: { radius: 0 to 1, how wide; floor: how bright a thing must be })
//   stage.glow(object)                what the bloom shines from, with all it holds (core/passes.js);
//   stage.glow(object, false)         and no longer. Nothing shines that was not marked.
// A mark that carries data stays out of the look by its own material:
//   material.toneMapped = false            filmic light leaves its colour as its legend shows it
//   material.userData.noContact = true     it casts no contact shade and is not shaded as a surface
// One limit: contact shade is laid over the finished picture, so where a mark lies in front
// of a shaded crease of solid parts, the crease's shade dims the mark's pixels too (by a few
// parts in a hundred; never where nothing solid lies behind it). A layer whose colour is a
// quantity can ask the view to leave contact shade out while it shows (the `contact` word of
// stage.dress), or the marks can be drawn after the passes: that hook is not built yet.

/** The effects, in the order the page lists them. `cost` says what a frame pays for one. */
export const EFFECTS = [
  { id: "reflections", label: "Studio reflections", cost: "none in a frame: the surroundings are prepared once" },
  { id: "filmic", label: "Filmic light", cost: "a few lines in each lit surface's shader" },
  { id: "translucency", label: "Soft translucency", cost: "a few lines in the shader of the parts it is on" },
  { id: "contact", label: "Contact shade", cost: "the solid parts drawn once more, two passes at the shade's own size, and one over the screen" },
  { id: "texture", label: "Surface texture", cost: "four samples of a noise in the shader of the parts it is on" },
  { id: "drift", label: "Crowd drift", cost: "six sines for each point of the crowd" },
  { id: "shimmer", label: "Membrane shimmer", cost: "three samples of a noise over the membrane" },
];
const IDS = EFFECTS.map((effect) => effect.id);

/**
 * What a device that cannot keep the picture moving gives up, a step at a time: contact
 * shade at half size, then off; then the rest of what costs something in each frame.
 * Studio reflections and filmic light cost nothing to speak of, so they stay. `contact`
 * is the size of the contact shade's pictures, in screen pixels of the page for each of
 * theirs; `says` is what the page says while the step holds.
 */
export const STEPS = [
  { id: "all", contact: 1, off: [], says: null },
  { id: "contact at half size", contact: 0.5, off: [], says: "Contact shade is drawn at half size: this device could not keep the picture moving smoothly with all of it." },
  { id: "no contact shade", contact: 0, off: ["contact"], says: "Contact shade is off: this device could not keep the picture moving smoothly with it." },
  { id: "light", contact: 0, off: ["contact", "texture", "translucency", "shimmer", "drift"], says: "Only studio reflections and filmic light are on: this device could not keep the picture moving smoothly with the rest." },
];

// Where the middle frame of WINDOW frames is slower than this, the picture is not moving
// smoothly: under 25 frames a second. The middle one, not the mean: a few long frames
// while shaders compile or a part is built say nothing of the device. And 25, not 30: a
// browser that saves power may hold a page to 30 frames a second, which is no fault to answer.
export const SLOW_MS = 40;
export const WINDOW = 45;
// After a change, this many frames are let pass before the next judgement: shaders compile.
export const SETTLE = 30;

export class Look {
  constructor() {
    this.choice = "rich"; // what the visitor chose: "rich" or "plain"
    this.held = false; // every chosen effect stays on whatever the frame rate
    this.step = 0; // how far down STEPS the device has gone
    this.manual = new Map(); // an effect switched by hand in the trial: id -> on
    this.trial = false; // whether the trial's readout is asked for
    this.wanted = false; // whether the view now shown wants the rich look at all
    this.listeners = new Set();
    this.times = [];
    this.wait = SETTLE;
  }

  /** Calls back whenever what is drawn may have changed. Returns how to stop it. */
  onChange(callback) {
    this.listeners.add(callback);
    return () => this.listeners.delete(callback);
  }

  changed() {
    this.times.length = 0;
    this.wait = SETTLE;
    for (const callback of this.listeners) callback(this);
  }

  /**
   * The visitor's choice. "plain" is the look as it was; "rich" is the seven effects, with
   * the device's fallback; "full" is rich and held: every effect stays on whatever the
   * frame rate, for pictures and for judging on a device. Choosing again starts afresh:
   * a device that had stepped down tries all of it once more.
   */
  choose(word) {
    if (!["rich", "plain", "full"].includes(word)) return false;
    this.choice = word === "plain" ? "plain" : "rich";
    this.held = word === "full";
    this.step = 0;
    this.manual.clear();
    this.changed();
    return true;
  }

  /** A view says whether it wants the rich look while it is shown. */
  want(wanted) {
    if (this.wanted === Boolean(wanted)) return;
    this.wanted = Boolean(wanted);
    this.changed();
  }

  /** Switch one effect by hand (the trial). From then on the device's fallback rests: the visitor is judging. */
  set(effect, on) {
    if (!IDS.includes(effect)) return;
    this.manual.set(effect, Boolean(on));
    this.held = true;
    this.changed();
  }

  get rich() {
    return this.wanted && this.choice === "rich";
  }

  /** Whether an effect is drawn now. */
  on(effect) {
    if (!this.rich) return false;
    if (this.manual.has(effect)) return this.manual.get(effect);
    return !STEPS[this.step].off.includes(effect);
  }

  /** The size of the contact shade's pictures: 1, 0.5, or 0 where it is off. */
  get contact() {
    if (!this.on("contact")) return 0;
    return STEPS[this.step].contact || 1;
  }

  /** What the page must say of the look as it now is, or null where all that was chosen is drawn. */
  says() {
    if (!this.rich || this.held) return null;
    return STEPS[this.step].says;
  }

  /** The effects drawn now, by id. */
  drawn() {
    return IDS.filter((id) => this.on(id));
  }

  /**
   * One frame took this long, in milliseconds, while the picture was moving. Returns true
   * where the device has just stepped down. It only ever steps down: a slow device is
   * not made to try again until the visitor chooses the look anew.
   */
  frame(milliseconds) {
    if (!this.rich || this.held || this.step >= STEPS.length - 1) return false;
    if (!(milliseconds > 0)) return false;
    if (this.wait > 0) {
      this.wait -= 1;
      return false;
    }
    this.times.push(milliseconds);
    if (this.times.length < WINDOW) return false;
    const middle = this.times.sort((a, b) => a - b)[Math.floor(this.times.length / 2)];
    this.times.length = 0;
    if (middle <= SLOW_MS) return false;
    this.step += 1;
    this.changed();
    return true;
  }
}

/**
 * The clock of what moves for decoration only (a drifting crowd, a shimmering membrane).
 * It stands still for a visitor who asks for less motion, and while anything holds it:
 * flux holds it for as long as flux shows, so that only data moves then.
 */
export class Decoration {
  constructor({ still = false } = {}) {
    this.time = 0; // seconds of decoration shown so far
    this.still = still; // the visitor asks for less motion
    this.holds = new Set();
  }

  pause(reason = "paused") {
    this.holds.add(reason);
  }

  resume(reason = "paused") {
    this.holds.delete(reason);
  }

  get moving() {
    return !this.still && this.holds.size === 0;
  }

  /** Advance by a frame of dt milliseconds. Returns whether decoration is moving. */
  tick(dt) {
    if (!this.moving) return false;
    this.time += dt / 1000;
    return true;
  }
}
