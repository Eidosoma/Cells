// The turn of a machine's rotor, as illustration from papers (schema/MACHINES.md, `motion`;
// schema/QUANTITY_LAYERS.md, rule 13, as the coordinator writes it). The user, 16 November
// 2026: "motor, yes it should turn at real life speeds at flux ... except if we slow down the
// flux". So the rotor turns at the rate the machine's file draws it at, slowed only by the
// Cell view's flux (`slow`: 1 is real life, 1,000 is slowed a thousand times). It has no speed
// of its own and no words of its own for the steps of speed: the caller gives both.
//
// The clock is the time that really passed (`real`, from the stage's frameTimes), not the
// frame's capped step, so the stated speed holds on a slow device.
//
// Never stroboscopic. At real-life speed the rotor turns several times in one frame; drawn as
// snapshots, its marks would seem to stand, creep or run backwards: a false direction or a
// false rate. So each set of marks has a limit, in turns a frame: an eighth of a turn for a
// single mark, a quarter of their spacing for a set of like copies (34 blocks round a ring are
// a turn over 34 apart). Above its limit a set is not drawn, and its swept form is: the marks
// smeared round, a body of revolution with no angle that could be read. Over the half step
// below the limit the two fade into each other, so nothing pops; there the marks still turn
// exactly as fast as the rate says, and the right way. The arrowhead shows the way throughout.
// The words never say that it is too fast to follow (the user, 16 November 2026).

import { placeAlong } from "../lenses/machine_parts.js";

export const BLUR = { single: 0.125, set: 0.25, fade: 0.5 };
const TURN = Math.PI * 2;

/** How far the rotor turns in one frame, in turns, at a rate (turns a second), a slow-down and a frame's real time (ms). */
export const turnsPerFrame = (rate, slow, realMs) => (rate / (slow || 1)) * (Math.max(0, realMs) / 1000);

/**
 * How sharply a set of marks is drawn for a step a frame (in turns): 1 drawn as marks, 0 not
 * drawn (its swept form instead), and between them a smooth fade. `period` is the turn over
 * the set's like copies (1 for a single mark).
 */
export function sharpness(step, period, blur = BLUR) {
  const limit = period >= 1 ? blur.single : blur.set * period, start = limit * blur.fade;
  if (step <= start) return 1;
  if (step >= limit) return 0;
  const t = (step - start) / (limit - start);
  return 1 - t * t * (3 - 2 * t);
}

/** The rotor's rate as the file draws it, in turns a second, and its top rate. */
export function ratesOf(machine) {
  const rotor = machine.motion?.rotor || {};
  return { drawn: rotor.drawn?.turns_per_s ?? rotor.rate?.most_turns_per_s ?? 0, top: rotor.rate?.most_turns_per_s ?? null, as: rotor.drawn?.as || null };
}

/**
 * What the picture says of the machine's motion (rule 3 and rule 13): that it is an
 * illustration and no run, and that Cells has no model of it; the way it turns and where it is
 * seen from; and the speed: real life, or the slow-down in force in the caller's words.
 * `turning` is false where the rotor stands (the machine is not the thing shown, the page was
 * opened still, the visitor asks for less motion).
 */
export function statementOf(machine, { turning = false, slow = 1, slowSaid = null } = {}) {
  const rotor = machine.motion?.rotor;
  const name = `this ${machine.called || machine.label.toLowerCase()}`;
  if (!rotor) return [`Illustration: Cells has no model of ${name}`];
  const { drawn, top, as } = ratesOf(machine);
  const seen = rotor.seen_from?.short, when = rotor.when;
  if (!seen || !when) throw new Error("the machine's file gives no short words for where its turn is seen from and when it turns that way");
  const count = (value) => Number(value).toLocaleString("en-US");
  const speed = `about ${count(drawn)} turns a second${as ? `, as ${as}` : ""}${top ? `; up to ${count(top)}, its top speed` : ""}`;
  const upper = (words) => `${words[0].toUpperCase()}${words.slice(1)}`;
  if (!turning) return [`Illustration: Cells has no model of ${name}`, `${upper(when)} it turns ${rotor.way}, ${seen} · shown still`, `In life ${speed}`];
  // The words for a slow-down are the flux's: this module has none of its own.
  if (slow > 1 && !slowSaid) throw new Error("a slowed machine's words need the flux's own words for its slow-down");
  return [`Illustration: not a run · Cells has no model of ${name}`, `Turning as ${when}: ${rotor.way}, ${seen}`, !(slow > 1) ? `At real-life speed: ${speed}` : `${upper(slowSaid)}: in life ${speed}`];
}

/** The rotor's motion on a built machine (machine_parts.js, buildMachine). */
export class MachineMotion {
  constructor(built) {
    this.built = built;
    this.machine = built.machine;
    this.rate = ratesOf(this.machine).drawn;
    this.blur = { ...BLUR, ...(this.machine.motion?.rotor?.blur || {}) };
    this.angle = 0; // radians, positive about the outward axis: counter-clockwise to an eye outside the cell
    this.turning = false;
    this.slow = 1;
    this.frameMs = 1000 / 60; // a frame's real time, smoothed
    this.lastMs = 0; // the real time of the frame last drawn
    this.sharp = new Map(); // set -> how sharply it is drawn now
    // Each set's objects get materials of their own, so that fading them touches nothing else.
    for (const set of built.sets) {
      for (const object of [...set.objects, set.blur]) {
        object.material = object.material.clone();
        object.material.transparent = true;
        object.material.userData = { ...object.material.userData, base: object.material.opacity ?? 1 };
      }
    }
    this.apply();
  }

  /** Turning or standing, at the flux's slow-down. */
  set({ turning = this.turning, slow = this.slow } = {}) {
    this.turning = Boolean(turning);
    this.slow = slow > 0 ? slow : 1;
    this.apply();
  }

  /**
   * The step a frame now, in turns: the larger of the smoothed frame's and this frame's own, so
   * that one long frame (a device that stalls) never draws marks that have moved further than
   * their limit since the frame before.
   */
  get step() {
    return this.turning ? Math.max(turnsPerFrame(this.rate, this.slow, this.frameMs), turnsPerFrame(this.rate, this.slow, this.lastMs)) : 0;
  }

  /** One frame: the angle moves on by the real time that passed. Returns whether it moves. */
  update(dt, time, real = dt) {
    if (!this.turning) return false;
    this.lastMs = Math.max(0, real);
    if (real > 0) this.frameMs += (real - this.frameMs) * 0.25;
    this.angle = (this.angle + (TURN * this.rate * Math.max(0, real)) / 1000 / this.slow) % TURN;
    this.apply();
    return true;
  }

  apply() {
    const { built } = this;
    built.spin.rotation.y = this.angle;
    built.afterSpin.rotation.y = this.angle;
    for (const line of built.lineSets) placeAlong(line.mesh, built.curve, { ...line, angle: this.angle });
    for (const set of built.sets) {
      if (set.about === "line" && set.place && !built.lineSets.some((line) => set.objects.includes(line.mesh))) placeAlong(set.objects[0], set.curve, { ...set.place, angle: this.angle });
      const sharp = this.turning ? sharpness(this.step, set.period, this.blur) : 1;
      this.sharp.set(set, sharp);
      for (const object of set.objects) {
        object.visible = sharp > 0.001;
        object.material.opacity = object.material.userData.base * sharp;
      }
      set.blur.visible = sharp < 0.999;
      set.blur.material.opacity = set.blur.material.userData.base * (1 - sharp);
    }
  }

  /** What the picture says now; `slowSaid` is the flux's own words for its slow-down. */
  statement(slowSaid = null) {
    return statementOf(this.machine, { turning: this.turning, slow: this.slow, slowSaid });
  }
}
